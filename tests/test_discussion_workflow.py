"""
Product Acceleration - Human Discussion UI: end-to-end workflow tests.

Exercises the newly-wired ReviewThread/ReviewMessage/Attention routes
(create_thread, add_thread_message, request_thread_attention,
resolve_thread, reopen_thread) through real HTTP requests against a real
Flask app + test client, using genuinely separate authenticated sessions
where the scenario requires it - proving the discussion capability is
actually usable end to end, respects the existing Case
Private/Shared/Collaborative/Archived lifecycle exactly through the
already-governed backend paths (no logic reproduced in the route/
template layer), and that the one visibility gap this tranche
identified and fixed (routes trusting a client-supplied case_id instead
of the thread's own recorded case_id) actually holds.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CASE_VISIBILITY_COLLABORATIVE, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class DiscussionWorkflowTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_discussion_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-discussion"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        self.owner_client = self.flask_app.test_client()
        with self.owner_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        self.other_client = self.flask_app.test_client()
        with self.other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "other-user"
            sess["role"] = "read_only"

        # CLAUDE-P32: see tests/test_case_privacy.py's identical setUp
        # comment -- project-level access is a new precondition both
        # sessions need before this class's real subject (Discussion/
        # Attention) can be exercised.
        store = self._store()
        workspace = store.get_or_create(self.project_id)
        store.set_project_owner(workspace, owner="owner1", actor="owner1")
        store.grant_project_access(workspace, username="other-user", actor="owner1", actor_role="read_only")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _create_case(self, client=None, title="Investigation"):
        client = client or self.owner_client
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._store().get(self.project_id)
        return next(c for c in workspace.cases if c["title"] == title)

    def _share_case(self, case_id):
        workspace = self._store().get(self.project_id)
        self._store().share_case(workspace, case_id=case_id, actor="owner1")

    def _create_thread(self, client, case_id, title="Datum concern", text="Does this line up with A101?"):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/threads",
            data={"title": title, "text": text}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._store().get(self.project_id)
        return next(t for t in workspace.review_threads if t["title"] == title)

    # -- discussion ----------------------------------------------------------

    def test_owner_can_create_discussion(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"])
        self.assertEqual(thread["created_by"], "owner1")
        self.assertEqual(thread["case_id"], case["id"])

    def test_opening_comment_persisted_as_human_message(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"], text="Please double-check this dimension.")
        workspace = self._store().get(self.project_id)
        messages = [m for m in workspace.review_messages if m["thread_id"] == thread["id"]]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["origin"], "human")
        self.assertEqual(messages[0]["actor"], "owner1")
        self.assertEqual(messages[0]["text"], "Please double-check this dimension.")

    def test_another_authorized_participant_can_see_and_respond(self):
        case = self._create_case()
        self._share_case(case["id"])
        thread = self._create_thread(self.owner_client, case["id"])

        view_response = self.other_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertEqual(view_response.status_code, 200)
        self.assertIn(thread["title"], view_response.get_data(as_text=True))

        reply_response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "Confirmed, it's off by 2 inches."}, follow_redirects=True,
        )
        self.assertEqual(reply_response.status_code, 200)

        workspace = self._store().get(self.project_id)
        messages = [m for m in workspace.review_messages if m["thread_id"] == thread["id"]]
        self.assertEqual(len(messages), 2)
        reply = messages[1]
        self.assertEqual(reply["actor"], "other-user")
        self.assertEqual(reply["origin"], "human")
        self.assertIsNotNone(reply["created_at"])

    def test_discussion_survives_reopen_as_a_fresh_session(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"], text="Original concern text.")

        fresh_client = self.flask_app.test_client()
        with fresh_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        response = fresh_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn(thread["title"], body)
        self.assertIn("Original concern text.", body)

    # -- collaboration threshold ---------------------------------------------

    def test_non_owner_human_reply_crosses_collaboration_threshold(self):
        case = self._create_case()
        self._share_case(case["id"])
        thread = self._create_thread(self.owner_client, case["id"])

        self.other_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "A genuine non-owner contribution."}, follow_redirects=True,
        )

        workspace = self._store().get(self.project_id)
        reloaded = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertEqual(reloaded["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_merely_viewing_does_not_cross_threshold(self):
        case = self._create_case()
        self._share_case(case["id"])
        self._create_thread(self.owner_client, case["id"])

        self.other_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")

        workspace = self._store().get(self.project_id)
        reloaded = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertNotEqual(reloaded["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    # -- privacy -----------------------------------------------------------

    def test_unauthorized_participant_cannot_see_private_case_discussion(self):
        case = self._create_case()  # stays PRIVATE - never shared
        thread = self._create_thread(self.owner_client, case["id"])

        response = self.other_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        # Private Case falls back to the other user's own default case
        # selection - the thread title must not leak into their page at all.
        self.assertNotIn(thread["title"], body)

    def test_unauthorized_participant_cannot_post_into_private_case_via_direct_route(self):
        case = self._create_case()  # PRIVATE
        thread = self._create_thread(self.owner_client, case["id"])

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "trying to sneak in"},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        messages = [m for m in workspace.review_messages if m["thread_id"] == thread["id"]]
        self.assertEqual(len(messages), 1)  # only the original opening comment

    def test_direct_route_bypass_via_spoofed_case_id_fails(self):
        """The route must derive authorization from the thread's OWN
        recorded case_id, never a client-supplied hidden form field -
        submitting a case_id the attacker legitimately owns must not
        smuggle a write into a Private thread belonging to someone else."""
        private_case = self._create_case(title="Private one")
        thread = self._create_thread(self.owner_client, private_case["id"])
        other_owned_case = self._create_case(client=self.other_client, title="Other users own case")

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "spoofed", "case_id": other_owned_case["id"]},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        messages = [m for m in workspace.review_messages if m["thread_id"] == thread["id"]]
        self.assertEqual(len(messages), 1)

    # -- archive -------------------------------------------------------------

    def test_archived_discussion_remains_readable(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"], text="Unresolved concern before archive.")
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn(thread["title"], body)
        self.assertIn("Unresolved concern before archive.", body)

    def test_posting_into_archived_case_fails(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"])
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "too late"}, follow_redirects=True,
        )

        workspace = self._store().get(self.project_id)
        messages = [m for m in workspace.review_messages if m["thread_id"] == thread["id"]]
        self.assertEqual(len(messages), 1)  # only the pre-archive opening comment

    def test_archived_case_ui_offers_no_write_controls(self):
        case = self._create_case()
        self._create_thread(self.owner_client, case["id"])
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertNotIn('name="resolution_outcome"', body)
        self.assertNotIn("+ Start a discussion", body)

    # -- attention -----------------------------------------------------------

    def test_attention_request_created_through_ui(self):
        case = self._create_case()
        self._share_case(case["id"])
        thread = self._create_thread(self.owner_client, case["id"])
        workspace = self._store().get(self.project_id)
        message_id = next(m for m in workspace.review_messages if m["thread_id"] == thread["id"])["id"]

        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/attention",
            data={"message_id": message_id, "intended_actor": "other-user"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = self._store().get(self.project_id)
        attentions = [a for a in workspace.attentions if a["thread_id"] == thread["id"]]
        self.assertEqual(len(attentions), 1)
        self.assertEqual(attentions[0]["intended_actor"], "other-user")
        self.assertEqual(attentions[0]["created_by"], "owner1")

    def test_unauthorized_participant_cannot_request_attention_on_private_case(self):
        case = self._create_case()  # PRIVATE
        thread = self._create_thread(self.owner_client, case["id"])
        workspace = self._store().get(self.project_id)
        message_id = next(m for m in workspace.review_messages if m["thread_id"] == thread["id"])["id"]

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/attention",
            data={"message_id": message_id, "intended_actor": "owner1"},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.attentions, [])

    # -- carry-forward ---------------------------------------------------------

    def test_derived_case_does_not_show_predecessor_discussion(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"], text="Predecessor concern.")
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/derive", follow_redirects=True)

        workspace = self._store().get(self.project_id)
        derived_case = next(c for c in workspace.cases if c.get("derived_from_case_id") == case["id"])

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={derived_case['id']}")
        body = response.get_data(as_text=True)
        self.assertNotIn(thread["title"], body)
        self.assertNotIn("Predecessor concern.", body)
        self.assertIn("No discussion yet on this Investigation.", body)

    def test_carried_forward_message_is_distinguishable_from_a_fresh_one(self):
        case = self._create_case()
        thread = self._create_thread(self.owner_client, case["id"], text="Predecessor concern to reconsider.")
        workspace = self._store().get(self.project_id)
        source_message_id = next(m for m in workspace.review_messages if m["thread_id"] == thread["id"])["id"]

        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/derive", follow_redirects=True)
        workspace = self._store().get(self.project_id)
        derived_case = next(c for c in workspace.cases if c.get("derived_from_case_id") == case["id"])

        self._store().adopt_review_message_into_case(
            self._store().get(self.project_id),
            source_message_id=source_message_id, target_case_id=derived_case["id"], actor="owner1",
        )

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={derived_case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("Carried forward from an archived predecessor Investigation", body)
        self.assertIn("Predecessor concern to reconsider.", body)


if __name__ == "__main__":
    unittest.main()
