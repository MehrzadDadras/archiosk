"""
CLAUDE-P40-E1A - Single Conversation Dock, Investigation Listing, and
User-Facing Terminology Correction.

Real browser evidence found P40-E1 left the dock only partially
unified: an open Investigation still rendered its own accordion
(#conversation), structurally separate from Project Home's
(#project-conversation), even though only one ever appeared at once -
different html_id, different position in the DOM (nested inside the
Investigation's own content pane vs. deep inside Project Home's
"Project State" section), so switching context looked like a
different chatbox, not the same dock. Fixed by relocating BOTH to one
shared physical position (outside the .case-workspace grid) through
one macro (macros.conversation_dock, templates/_macros.html) - same
html_id ("conversation-dock") and structure every time, content
supplied per call site.

Also: a newly created Investigation's name didn't appear under WORK in
the unified nav (only a bare count did) - fixed by listing every
authorized Investigation's own title there (services.case_workspace.
CaseWorkspaceStore.visible_cases_for's own P32/Case-privacy-filtered
list, never re-derived or widened). And "Case" terminology was still
visible in the creation form and several scattered strings - renamed
throughout, without touching the internal Case domain model/identifiers
(routes, store methods, dataclass field names are all unchanged).

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseDockTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e1a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e1a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e1a_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e1a_owner", project_name="Riverside P40E1A Dock")
        self.project_id = self.doc.project_id

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _create_investigation(self, client, title="Draft 1"):
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": title, "objective": ""})
        return self._store().get(self.project_id).cases[0]["id"]


class OneComposerPerContextTests(_BaseDockTestCase):
    def test_project_context_has_exactly_one_composer_and_one_send(self):
        client = self._client_as("p40e1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count("<button type=\"submit\">Send</button>"), 1)

    def test_investigation_context_has_exactly_one_composer_and_one_send(self):
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client)
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count("<button type=\"submit\">Send</button>"), 1)


class OnePhysicalDockTests(_BaseDockTestCase):
    def test_same_html_id_and_dock_class_in_both_contexts(self):
        # "the same dock switches context" - same html_id/structure
        # whether targeting the Project or an Investigation.
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client)

        project_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        case_body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)

        self.assertIn('id="conversation-dock"', project_body)
        self.assertIn('id="conversation-dock"', case_body)
        self.assertNotIn('id="project-conversation"', project_body)
        self.assertNotIn('id="conversation"', case_body.replace('id="conversation-dock"', ''))

    def test_dock_heading_shows_the_investigation_name_when_switched(self):
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client, title="Draft 1")
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("Draft 1", body)


class SeparateHistoriesTests(_BaseDockTestCase):
    def test_project_and_investigation_conversations_stay_separate_records(self):
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client)

        client.post(f"/projects/{self.project_id}/workspace/quick-start", data={"text": "What is this document about?"})
        client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": "Analyze this drawing for datum inconsistencies"},
        )

        workspace = self._store().get(self.project_id)
        investigation = next(c for c in workspace.cases if c["id"] == case_id)
        self.assertTrue(any("document about" in m["text"] for m in workspace.project_conversation))
        self.assertTrue(any("datum inconsistencies" in m["text"] for m in investigation["conversation"]))
        # Not merged into one record - each message list only has its own.
        self.assertFalse(any("datum inconsistencies" in m["text"] for m in workspace.project_conversation))
        self.assertFalse(any("document about" in m["text"] for m in investigation["conversation"]))


class ContextSwitchingTests(_BaseDockTestCase):
    def test_switching_context_changes_which_thread_the_dock_targets(self):
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client)

        project_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        case_body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)

        self.assertIn(f'action="/projects/{self.project_id}/workspace/quick-start"', project_body)
        self.assertIn(f'action="/projects/{self.project_id}/workspace/cases/{case_id}/messages"', case_body)


class StaleUnauthorizedPostingTests(_BaseDockTestCase):
    def test_posting_to_an_unauthorized_investigation_is_denied(self):
        owner_client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(owner_client)

        outsider_client = self._client_as("p40e1a_outsider", 2, role="read_only")
        resp = outsider_client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": "Should not be allowed."},
        )
        self.assertEqual(resp.status_code, 404)

        workspace = self._store().get(self.project_id)
        investigation = next(c for c in workspace.cases if c["id"] == case_id)
        self.assertFalse(any("Should not be allowed" in m["text"] for m in investigation["conversation"]))

    def test_posting_to_a_nonexistent_investigation_id_is_rejected(self):
        client = self._client_as("p40e1a_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases/does-not-exist/messages",
            data={"text": "Stale reference."},
        )
        self.assertEqual(resp.status_code, 404)


class DraftAndScrollPerThreadTests(_BaseDockTestCase):
    def test_draft_and_scroll_keys_are_scoped_per_context(self):
        client = self._client_as("p40e1a_owner", 1)
        case_id = self._create_investigation(client)

        project_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        case_body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)

        self.assertIn('data-conversation-draft="project"', project_body)
        self.assertIn('data-conversation-scope="project"', project_body)
        self.assertIn(f'data-conversation-draft="case-{case_id}"', case_body)
        self.assertIn(f'data-conversation-scope="case-{case_id}"', case_body)


class InvestigationListingTests(_BaseDockTestCase):
    def test_every_authorized_investigation_title_is_listed_under_work(self):
        client = self._client_as("p40e1a_owner", 1)
        self._create_investigation(client, title="Draft 1")
        client2 = self._client_as("p40e1a_owner", 1)
        client2.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Schedule Conflict Review", "objective": ""})

        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Draft 1", body)
        self.assertIn("Schedule Conflict Review", body)
        self.assertIn("side-rail-project-sublink", body)

    def test_newly_created_investigation_appears_immediately_and_becomes_active(self):
        client = self._client_as("p40e1a_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Draft 1", "objective": ""},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Draft 1", body)
        # Became the active Investigation - its own content pane, not
        # just a nav entry, opened in the main Display panel.
        self.assertIn('class="workspace-pane workspace-pane-conversation"', body)
        self.assertIn("<h2>Draft 1</h2>", body)
        self.assertIn('side-rail-project-sublink active"', body)


class UnauthorizedInvestigationsHiddenTests(_BaseDockTestCase):
    def test_unauthorized_user_sees_no_investigation_names_or_counts(self):
        owner_client = self._client_as("p40e1a_owner", 1)
        self._create_investigation(owner_client, title="Confidential Draft")

        outsider_client = self._client_as("p40e1a_outsider", 2, role="read_only")
        resp = outsider_client.get(f"/projects/{self.project_id}/workspace")
        # P32 deny-by-default: not on the project's owner/allow-list -
        # the whole page 404s, so nothing (including the nav) leaks.
        self.assertEqual(resp.status_code, 404)

    def test_allow_listed_but_case_private_investigation_is_not_named_in_nav(self):
        # A Case-private Investigation (CASE_VISIBILITY_PRIVATE, the
        # default) created by one project-authorized user must not be
        # named to a DIFFERENT project-authorized user in the nav -
        # visible_cases_for's own Case-level privacy filter, not just
        # P32 project-level access.
        from services.case_workspace import CaseWorkspaceStore

        owner_client = self._client_as("p40e1a_owner", 1)
        self._create_investigation(owner_client, title="Private To Owner")

        store = self._store()
        workspace = store.get(self.project_id)
        workspace.access_allow_list.append("p40e1a_outsider")
        store.save(workspace)

        allow_listed_client = self._client_as("p40e1a_outsider", 2, role="read_only")
        resp = allow_listed_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Private To Owner", resp.get_data(as_text=True))


class NoCaseTerminologyTests(_BaseDockTestCase):
    def test_creation_form_says_investigation_not_case(self):
        client = self._client_as("p40e1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("New Investigation", body)
        self.assertIn("Investigation title", body)
        self.assertIn("Create Investigation", body)
        self.assertNotIn("New Case", body)
        self.assertNotIn("Case title", body)
        self.assertNotIn(">Create Case<", body)

    def test_workspace_heading_and_accordion_say_investigation_not_case(self):
        client = self._client_as("p40e1a_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Investigations (", body)
        self.assertNotIn("Cases (", body)
        self.assertNotIn("Case Workspace", body)


class LegacyCaseRecordsStillLoadTests(_BaseDockTestCase):
    """P40-D2's own invariant, re-verified after this stage's dock/nav
    changes: a legacy Case (no visibility key) must still load and must
    not have its record structurally rewritten by a normal GET."""

    def test_legacy_case_loads_and_get_does_not_mutate_the_record(self):
        workspace = self._store().get(self.project_id)
        workspace.cases.append({
            "id": "legacy-investigation-no-visibility", "project_id": self.project_id, "title": "Legacy Investigation",
            "objective": "", "created_at": "2020-01-01T00:00:00+00:00", "status": "open",
            "source_ids": [], "finding_ids": [], "analysis_ids": [], "artifact_ids": [], "activity_ids": [],
            "conversation": [],
        })
        self._store().save(workspace)
        before_raw = json.loads((self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8"))

        client = self._client_as("p40e1a_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?case=legacy-investigation-no-visibility")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Legacy Investigation", resp.get_data(as_text=True))

        after_raw = json.loads((self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8"))
        changed_keys = {k for k in set(before_raw) | set(after_raw) if before_raw.get(k) != after_raw.get(k)}
        self.assertTrue(changed_keys.issubset({"last_viewed_by"}), changed_keys)


if __name__ == "__main__":
    unittest.main()
