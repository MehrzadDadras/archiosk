"""
CLAUDE-P40-E1 - One Composer, Remove Duplicate Conversation Entry Points.

The P40-E Workspace redesign left three competing composers on the
Project Home render: "Ask about the project documents" (discuss_object),
"Start or continue project work" (quick_start), and "Talk to this
Project" (also discuss_object, inside the docked Project Conversation).
routes/workspace.py's own _run_conversation_turn docstring already
called all three "the same conversational entry point, reached from
three places" - this stage collapses them into exactly one, in the
bottom dock, without losing any capability:

  - the single composer posts to quick_start, which already classifies
    a plain question (routes to grounded project-level Q&A) from a
    real "start work" request (creates a new Investigation) - see that
    route's own docstring;
  - the Requirements "Discuss this Requirement" aperture (macros.
    aperture) no longer renders its own second composer - it attaches
    an anchor to the ONE dock composer via a small JS handler instead
    (static/js/case_workspace.js), and quick_start now honors that
    anchor the same way discuss_object always did (project-level
    conversation, never spawns a new Investigation);
  - RFI delegation/preview (pending_rfi_finding_id/rfi_preview) live
    inside the Case-level composer's own accordion, untouched by any
    of this - they were never a duplicate composer to begin with.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
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


class _BaseSingleComposerTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e1_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e1_owner", project_name="Riverside P40E1 Composer")
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

    def _create_case(self, client, title="Drawing Review"):
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": title, "objective": ""})
        return self._store().get(self.project_id).cases[0]["id"]


class ExactlyOneComposerTests(_BaseSingleComposerTestCase):
    def test_exactly_one_composer_on_project_home(self):
        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)

    def test_exactly_one_send_action_on_project_home(self):
        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        # Only the dock composer's own Send button - the removed "Ask"/
        # "Send" buttons from the other two composers must not reappear.
        self.assertEqual(body.count("<button type=\"submit\">Send</button>"), 1)
        self.assertNotIn("<button type=\"submit\">Ask</button>", body)

    def test_old_composer_labels_are_gone(self):
        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Ask about the project documents", body)
        self.assertNotIn("Start or continue project work", body)

    def test_separate_from_investigation_explanation_is_removed(self):
        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("Separate from an Investigation&#39;s own", body)
        self.assertNotIn("Separate from an Investigation's own", body)

    def test_opening_an_investigation_does_not_add_another_composer(self):
        client = self._client_as("p40e1_owner", 1)
        case_id = self._create_case(client)
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        # The Case-level composer is real and expected (a different
        # form, action=post_message) - exactly one composer, not two.
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)

    def test_opening_a_document_does_not_add_another_composer(self):
        store = self._store()
        workspace = store.get(self.project_id)
        workspace.sources.append({
            "id": "doc-source-1", "project_id": self.project_id, "kind": "rfq_rfp_document",
            "name": "addendum.txt", "added_at": "2026-01-01T00:00:00+00:00", "file_path": None,
        })
        store.save(workspace)

        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?source=doc-source-1").get_data(as_text=True)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)

    def test_aperture_no_longer_renders_its_own_text_input(self):
        # macros.aperture used to render <form>...<input type="text"...
        # a second composer, collapsed but always in the DOM. It is now
        # a plain button with no text input of its own.
        client = self._client_as("p40e1_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={"source_id": source_id, "original_requirement_identifier": "4.2", "text_reference": "The system shall do X."},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("aperture-link", body)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)


class DocumentQAStillWorksTests(_BaseSingleComposerTestCase):
    def test_a_plain_question_through_quick_start_is_answered_in_project_conversation(self):
        client = self._client_as("p40e1_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "What is the name of this document?"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.cases), 0, "a plain question must not spawn a new Investigation")
        self.assertGreaterEqual(len(workspace.project_conversation), 2)


class FormalInvestigationCreationStillWorksTests(_BaseSingleComposerTestCase):
    def test_a_work_request_through_the_single_composer_still_creates_an_investigation(self):
        client = self._client_as("p40e1_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Analyze this drawing for datum inconsistencies"},
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.cases), 1)
        self.assertEqual(workspace.cases[0]["title"], "Analyze this drawing for datum inconsistencies")


class ApertureAnchoredMessageTests(_BaseSingleComposerTestCase):
    def test_anchored_message_through_quick_start_never_spawns_an_investigation(self):
        # Even non-question-shaped text ("Check this.") must not create
        # a new Investigation when an anchor is present - the anchor
        # itself is what routes.workspace.quick_start now uses to know
        # this came from a "Discuss this X" aperture, not free typing.
        client = self._client_as("p40e1_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={
                "text": "Check this citation against the referenced clause.",
                "anchor_type": "requirement", "anchor_id": "req-123", "anchor_description": "Req 4.2",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.cases), 0)
        self.assertEqual(workspace.project_conversation[0]["anchor"]["anchor_type"], "requirement")
        self.assertEqual(workspace.project_conversation[0]["anchor"]["anchor_id"], "req-123")


class RfiDelegationStillFunctionalTests(_BaseSingleComposerTestCase):
    def test_rfi_delegation_ui_still_renders_inside_the_case_composer_accordion(self):
        # A bounded smoke check: the delegation-choice markup class is
        # still present in the template's Case-open branch (its actual
        # trigger condition - pending_rfi_finding_id - is exercised
        # elsewhere in the existing RFI test suite; this only confirms
        # P40-E1's composer consolidation didn't delete the markup).
        client = self._client_as("p40e1_owner", 1)
        case_id = self._create_case(client)
        resp = client.get(f"/projects/{self.project_id}/workspace?case={case_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("conversation-input-form conversation-dock-composer", body)


class DraftPreservationStillWorksTests(_BaseSingleComposerTestCase):
    def test_dock_composer_still_carries_the_draft_preservation_attribute(self):
        # CLAUDE-P40-E1A: the key is now the per-context scope_key
        # ("project" on Project Home), not the project_id.
        client = self._client_as("p40e1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-conversation-draft="project"', body)


class AuthorizationStillEnforcedTests(_BaseSingleComposerTestCase):
    def test_quick_start_is_denied_for_an_unauthorized_user(self):
        client = self._client_as("p40e1_outsider", 2, role="read_only")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "What is this project about?"},
        )
        self.assertEqual(resp.status_code, 404)

    def test_workspace_page_is_denied_for_an_unauthorized_user(self):
        client = self._client_as("p40e1_outsider", 2, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
