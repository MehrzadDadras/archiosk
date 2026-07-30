"""
Complete the Human Discussion loop: Attention response + thread
Resolve/Reopen, end-to-end.

Wires CaseWorkspaceStore.respond_to_attention (already implemented,
previously unreachable from any route) into the Case Workspace UI, and
re-confirms the already-wired Resolve/Reopen path continues to work
correctly alongside it. Reuses the hardened object-to-Case
authorization pattern (_attention_case_id -> _require_visible_case) -
never a client-supplied case_id.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class AttentionResponseWorkflowTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_attention_response_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-attention-response"

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

        # CLAUDE-P32: project-level access is a new precondition both
        # sessions need before this class's real subject (Attention/
        # thread Resolve-Reopen) can be exercised -- see
        # tests/test_case_privacy.py's identical setUp comment.
        store = self._store()
        workspace = store.get_or_create(self.project_id)
        store.set_project_owner(workspace, owner="owner1", actor="owner1")
        store.grant_project_access(workspace, username="other-user", actor="owner1", actor_role="read_only")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _create_case(self, client, title="Investigation"):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        return next(c for c in self._store().get(self.project_id).cases if c["title"] == title)

    def _share_case(self, case_id):
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case_id}/share", follow_redirects=True)

    def _create_thread_with_message(self, client, case_id, title="Datum concern", text="Please check this."):
        response = client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/threads",
            data={"title": title, "text": text}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._store().get(self.project_id)
        thread = next(t for t in workspace.review_threads if t["title"] == title)
        message = next(m for m in workspace.review_messages if m["thread_id"] == thread["id"])
        return thread, message

    def _request_attention(self, client, thread_id, message_id, intended_actor):
        response = client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread_id}/attention",
            data={"message_id": message_id, "intended_actor": intended_actor}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = self._store().get(self.project_id)
        return next(a for a in workspace.attentions if a["thread_id"] == thread_id)

    # -- visibility ---------------------------------------------------------

    def test_attention_request_visible_to_authorized_participant(self):
        case = self._create_case(self.owner_client)
        self._share_case(case["id"])
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        self._request_attention(self.owner_client, thread["id"], message["id"], "other-user")

        response = self.other_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("Attention", body)
        self.assertIn("other-user", body)
        self.assertIn("(you)", body)  # rendered from other-user's own session
        self.assertIn("Pending", body)

    # -- respond through the real route -------------------------------------

    def test_respond_to_attention_through_real_route(self):
        case = self._create_case(self.owner_client)
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")

        response_text = "Confirmed and corrected."
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": response_text}, follow_redirects=True,
        )
        workspace = self._store().get(self.project_id)
        thread_response_message = next(
            m for m in workspace.review_messages if m["thread_id"] == thread["id"] and m["text"] == response_text
        )

        result = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": thread_response_message["id"]}, follow_redirects=True,
        )
        self.assertEqual(result.status_code, 200)

        workspace = self._store().get(self.project_id)
        reloaded = next(a for a in workspace.attentions if a["id"] == attention["id"])
        self.assertEqual(reloaded["status"], "responded")
        self.assertEqual(reloaded["responded_message_id"], thread_response_message["id"])

    def test_requesting_and_responding_context_preserved(self):
        case = self._create_case(self.owner_client)
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")

        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/messages",
            data={"text": "Here is my answer."}, follow_redirects=True,
        )
        workspace = self._store().get(self.project_id)
        response_message = next(
            m for m in workspace.review_messages if m["thread_id"] == thread["id"] and m["text"] == "Here is my answer."
        )
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": response_message["id"]}, follow_redirects=True,
        )

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("Responded", body)
        self.assertIn("Here is my answer.", body)
        self.assertIn(attention["created_by"], body)

    # -- privacy / spoofing ------------------------------------------------

    def test_unauthorized_participant_cannot_respond_to_private_case_attention(self):
        case = self._create_case(self.owner_client)  # PRIVATE
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": message["id"]},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        reloaded = next(a for a in workspace.attentions if a["id"] == attention["id"])
        self.assertEqual(reloaded["status"], "pending")

    def test_spoofed_case_id_cannot_launder_attention_response(self):
        attacker_case = self._create_case(self.other_client, title="Attacker's own case")
        victim_case = self._create_case(self.owner_client, title="Victim's private case")
        thread, message = self._create_thread_with_message(self.owner_client, victim_case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")

        response = self.other_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": message["id"], "case_id": attacker_case["id"]},
        )
        self.assertEqual(response.status_code, 404)

        workspace = self._store().get(self.project_id)
        reloaded = next(a for a in workspace.attentions if a["id"] == attention["id"])
        self.assertEqual(reloaded["status"], "pending")

    # -- archive -------------------------------------------------------------

    def test_archived_case_rejects_attention_response(self):
        case = self._create_case(self.owner_client)
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": message["id"]}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)  # rejected via flash+redirect, not a hard 404

        workspace = self._store().get(self.project_id)
        reloaded = next(a for a in workspace.attentions if a["id"] == attention["id"])
        self.assertEqual(reloaded["status"], "pending")

    def test_archived_case_still_shows_historical_attention_readonly(self):
        case = self._create_case(self.owner_client)
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")
        self.owner_client.post(f"/projects/{self.project_id}/workspace/cases/{case['id']}/archive", follow_redirects=True)

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("Attention", body)
        self.assertNotIn("Mark Responded", body)

    # -- resolve/reopen continue to work ------------------------------------

    def test_resolve_and_reopen_thread_still_work(self):
        case = self._create_case(self.owner_client)
        thread, _message = self._create_thread_with_message(self.owner_client, case["id"])

        resolve_response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/resolve",
            data={"resolution_outcome": "no_issue", "summary": "Confirmed fine."}, follow_redirects=True,
        )
        self.assertEqual(resolve_response.status_code, 200)
        workspace = self._store().get(self.project_id)
        resolved = next(t for t in workspace.review_threads if t["id"] == thread["id"])
        self.assertEqual(resolved["status"], "resolved")
        self.assertEqual(resolved["resolution"]["resolution_outcome"], "no_issue")

        reopen_response = self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/reopen",
            data={"reason": "New evidence surfaced."}, follow_redirects=True,
        )
        self.assertEqual(reopen_response.status_code, 200)
        workspace = self._store().get(self.project_id)
        reopened = next(t for t in workspace.review_threads if t["id"] == thread["id"])
        self.assertEqual(reopened["status"], "reopened")
        self.assertIsNone(reopened["resolution"])
        self.assertEqual(len(reopened["resolution_history"]), 1)
        self.assertEqual(reopened["resolution_history"][0]["reopen_reason"], "New evidence surfaced.")

    def test_resolution_history_visible_after_reopen(self):
        case = self._create_case(self.owner_client)
        thread, _message = self._create_thread_with_message(self.owner_client, case["id"])
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/resolve",
            data={"resolution_outcome": "no_issue", "summary": "Confirmed fine."}, follow_redirects=True,
        )
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/threads/{thread['id']}/reopen",
            data={"reason": "New evidence surfaced."}, follow_redirects=True,
        )

        response = self.owner_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("New evidence surfaced.", body)
        self.assertIn("Confirmed fine.", body)

    # -- persistence across a fresh session ---------------------------------

    def test_attention_response_survives_fresh_session(self):
        case = self._create_case(self.owner_client)
        thread, message = self._create_thread_with_message(self.owner_client, case["id"])
        attention = self._request_attention(self.owner_client, thread["id"], message["id"], "owner1")
        self.owner_client.post(
            f"/projects/{self.project_id}/workspace/attentions/{attention['id']}/respond",
            data={"response_message_id": message["id"]}, follow_redirects=True,
        )

        fresh_client = self.flask_app.test_client()
        with fresh_client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "read_only"

        response = fresh_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        body = response.get_data(as_text=True)
        self.assertIn("Responded", body)


if __name__ == "__main__":
    unittest.main()
