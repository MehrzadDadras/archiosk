"""
CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum - Storage Grammar &
Public-Trial Entitlement Clarification.

Covers the addendum's own Parts 1-6/8:
  - "Connect Documents" replaces the long HYBRID-ENTRY-01 disclaimer with
    a plain Link-vs-Upload choice (upload.html).
  - Link to Storage is shown but honestly, permanently disabled - no
    genuine linked-storage mechanism exists yet, and it is never
    disguised as available.
  - Upload to Storage is the same, unchanged folder-upload mechanism
    (CLAUDE-CA1D-FOLDER-ESTABLISH-CLARITY-01), gated by the new
    services.auth.user_can_upload_to_storage() choke point - both
    client-side (greyed control) and server-side (a real abort(403) on
    the route itself, not merely cosmetic).
  - The same grammar/greying is reused on Admin -> Project Data
    Management's own "Add documents to project" section
    (templates/reset_project_data.html).
  - user_can_upload_to_storage() is a single, centralized, honestly-
    documented no-op today (every real user is entitled) - these tests
    prove today's behavior is unchanged for real users, AND that the
    entitlement choke point genuinely blocks a direct POST when
    monkeypatched to return False (the only way to exercise Part 6's
    "not merely cosmetic" requirement without a real trial-account
    concept existing yet).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_UPLOAD_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "upload.html"
_RESET_PROJECT_DATA_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "reset_project_data.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        import shutil
        import tempfile
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_storage_grammar_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="sg_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self._rmtree = shutil.rmtree

    def tearDown(self):
        self._rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

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


# ---------------------------------------------------------------------------
# upload.html - explicit source-domain connection grammar.
# ---------------------------------------------------------------------------

class UploadPageStorageGrammarTests(_BaseTestCase):
    def test_hero_copy_is_the_short_addendum_sentence_not_the_old_disclaimer(self):
        client = self._client_as("sg_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn("Choose how this Project's documents connect to Archiosk.", body)
        self.assertNotIn("Kept available for establishing a project from a full", body)

    def test_three_source_domains_are_present(self):
        client = self._client_as("sg_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn("Connect Client Data Room", body)
        self.assertIn("Connect Your Workspace", body)
        self.assertIn("Add External References", body)
        self.assertIn('data-source-domain="CLIENT_ISSUED"', body)
        self.assertIn('data-source-domain="TEAM_WORKSPACE"', body)
        self.assertIn('data-source-domain="EXTERNAL_REFERENCE"', body)

    def test_upload_option_present_and_functional_for_a_real_entitled_user(self):
        client = self._client_as("sg_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        client_button = body.index('data-source-domain="CLIENT_ISSUED"')
        client_button_end = body.index(">", client_button)
        self.assertNotIn("disabled", body[client_button:client_button_end])
        self.assertNotIn('data-ui-ref="upload.storage.upload.disabled-reason"', body)

    def test_domain_copy_preserves_authority_boundaries(self):
        client = self._client_as("sg_admin", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn("Requirements and information received from the party that engaged you.", body)
        self.assertIn("Your team's developing work", body)
        self.assertIn("non-project-authority reference material", body)


class UploadEntitlementGreyingTests(_BaseTestCase):
    def test_upload_option_greys_and_shows_reason_when_not_entitled(self):
        with patch("routes.portal.user_can_upload_to_storage", return_value=False):
            client = self._client_as("sg_admin", 1)
            body = client.get("/upload").get_data(as_text=True)
        self.assertIn('data-ui-ref="upload.storage.upload.disabled-reason"', body)
        self.assertIn("Not available in public trial", body)
        for domain in ("CLIENT_ISSUED", "TEAM_WORKSPACE", "EXTERNAL_REFERENCE"):
            button_start = body.index(f'data-source-domain="{domain}"')
            button_end = body.index(">", button_start)
            self.assertIn("disabled", body[button_start:button_end])

    def test_domain_buttons_are_enabled_when_entitled(self):
        with patch("routes.portal.user_can_upload_to_storage", return_value=True):
            client = self._client_as("sg_admin", 1)
            body = client.get("/upload").get_data(as_text=True)
        for domain in ("CLIENT_ISSUED", "TEAM_WORKSPACE", "EXTERNAL_REFERENCE"):
            button_start = body.index(f'data-source-domain="{domain}"')
            button_end = body.index(">", button_start)
            self.assertNotIn("disabled", body[button_start:button_end])


# ---------------------------------------------------------------------------
# Server-side enforcement: a direct POST must be blocked, not merely the
# UI greyed - Part 6's own explicit requirement.
# ---------------------------------------------------------------------------

class ServerSideEnforcementTests(_BaseTestCase):
    def test_upload_folder_post_succeeds_today_real_users_are_entitled(self):
        client = self._client_as("sg_admin", 1)
        response = client.post(
            "/upload/folder",
            data={
                "operating_environment": CLIENT_OWNER,
                "founding_relative_path": "Folder/rfp.txt",
                "folder_files": [_fake_file(b"content", "Folder/rfp.txt")],
            },
            content_type="multipart/form-data",
        )
        # Never a 403 for a real, entitled (today: every real) user -
        # whatever the ingestion outcome, entitlement itself must not be
        # what blocks this.
        self.assertNotEqual(response.status_code, 403)

    def test_upload_folder_post_blocked_when_not_entitled_even_without_ui(self):
        # The exact scenario Part 6 names: a caller posts directly to the
        # route, bypassing the greyed-out UI entirely. Only provable
        # today via monkeypatching, since no real trial account exists.
        with patch("routes.portal.user_can_upload_to_storage", return_value=False):
            client = self._client_as("sg_admin", 1)
            response = client.post(
                "/upload/folder",
                data={
                    "operating_environment": CLIENT_OWNER,
                    "founding_relative_path": "Folder/rfp.txt",
                    "folder_files": [_fake_file(b"content", "Folder/rfp.txt")],
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 403)

    def test_add_document_source_post_blocked_when_not_entitled(self):
        doc = self._ingest(owner="sg_admin", project_name="Storage Grammar PDM Project")
        with patch("routes.workspace.user_can_upload_to_storage", return_value=False):
            client = self._client_as("sg_admin", 1)
            response = client.post(
                f"/projects/{doc.project_id}/workspace/sources/document",
                data={"document": _fake_file(b"content", "extra.txt")},
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 403)

    def test_add_document_source_post_succeeds_today_real_users_are_entitled(self):
        doc = self._ingest(owner="sg_admin", project_name="Storage Grammar PDM Project Two")
        client = self._client_as("sg_admin", 1)
        response = client.post(
            f"/projects/{doc.project_id}/workspace/sources/document",
            data={"document": _fake_file(b"content", "extra.txt")},
            content_type="multipart/form-data",
        )
        self.assertNotEqual(response.status_code, 403)


# ---------------------------------------------------------------------------
# Project Data Management's "Add documents to project" reuses the same
# grammar/greying (Part 8).
# ---------------------------------------------------------------------------

class ProjectDataManagementStorageGrammarTests(_BaseTestCase):
    def test_add_documents_section_functional_for_a_real_entitled_user(self):
        doc = self._ingest(owner="sg_admin", project_name="Storage Grammar PDM Project Three")
        client = self._client_as("sg_admin", 1)
        body = client.get(f"/admin/reset-project-data?project_id={doc.project_id}").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="pdm.add-documents.disabled-reason"', body)
        file_start = body.index('data-ui-ref="pdm.add-documents.file"')
        tag_start = body.rindex("<input", 0, file_start)
        tag_end = body.index(">", tag_start)
        self.assertNotIn("disabled", body[tag_start:tag_end])

    def test_add_documents_section_greys_and_shows_reason_when_not_entitled(self):
        doc = self._ingest(owner="sg_admin", project_name="Storage Grammar PDM Project Four")
        with patch("routes.portal.user_can_upload_to_storage", return_value=False):
            client = self._client_as("sg_admin", 1)
            body = client.get(f"/admin/reset-project-data?project_id={doc.project_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="pdm.add-documents.disabled-reason"', body)
        self.assertIn("Not available in public trial", body)
        file_start = body.index('data-ui-ref="pdm.add-documents.file"')
        tag_start = body.rindex("<input", 0, file_start)
        tag_end = body.index(">", tag_start)
        self.assertIn("disabled", body[tag_start:tag_end])


# ---------------------------------------------------------------------------
# services.auth.user_can_upload_to_storage() itself - the choke point.
# ---------------------------------------------------------------------------

class UploadEntitlementFunctionTests(unittest.TestCase):
    def test_honest_no_op_returns_true_today(self):
        from services.auth import user_can_upload_to_storage
        self.assertTrue(user_can_upload_to_storage())
