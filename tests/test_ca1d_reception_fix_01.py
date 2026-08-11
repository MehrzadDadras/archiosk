"""
CLAUDE-CA1D-RECEPTION-FIX-01 - Live Reception / First-Entry Corrections.

Covers what was actually changed, discovered during a live Zero-Founder
walkthrough of the deployed accepted build:
  - login password reveal/hide toggle (client-side only, no auth change);
  - a restrained, access-filtered hint on a no-match active-project
    search pointing at Removed Projects, only when a removed Project
    the current user can already see actually matches;
  - the "Projects" nav chevron now also expands on /removed-projects,
    matching its existing behavior on a single removed Project's own
    tombstone page and on /projects;
  - "Back to Projects" reworded to "Back to Active Projects" on both
    removed-Project pages, to disambiguate from Removed Projects
    (destination unchanged - portal.projects_list);
  - project_chooser.html's true empty state now names the Project
    Gateway as where to start a new Project.

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


class LoginPasswordToggleTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_login_page_has_password_toggle_default_hidden(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('id="password-toggle"', body)
        self.assertIn('type="password" id="password"', body)
        self.assertIn('aria-pressed="false"', body)
        self.assertIn('aria-label="Show password"', body)
        self.assertIn("password-toggle-icon-show", body)
        self.assertIn("password-toggle-icon-hide", body)

    def test_password_toggle_button_is_not_a_submit_button(self):
        # Must never accidentally submit the sign-in form on click/Enter.
        body = self.client.get("/login").get_data(as_text=True)
        toggle_start = body.index('id="password-toggle"')
        button_open_tag = body.rindex("<button", 0, toggle_start)
        self.assertIn('type="button"', body[button_open_tag:toggle_start])


class _BaseReceptionFixTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_reception_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="rf_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="rf_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

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


class RemovedProjectDiscoverabilityHintTests(_BaseReceptionFixTestCase):
    # Search (both the pre-existing active-project search and this new
    # hint, which deliberately reuses its exact needle logic) matches
    # against document filename/project_id, NOT workspace.display_title
    # -- ingest_upload's own `project_name` becomes display_title, a
    # separate field. Filenames below are chosen to match the query
    # string for that reason, not project_name.
    def test_hint_shown_when_only_a_removed_project_matches(self):
        doc = self._ingest(owner="rf_owner", project_name="Riverside Project", filename="Test2.txt")
        client = self._client_as("rf_owner", 1)
        client.post(f"/projects/{doc.project_id}/workspace/remove", data={"confirm": "yes"})

        body = client.get("/projects/choose?q=Test2").get_data(as_text=True)
        self.assertIn("No active projects match", body)
        self.assertIn("It may be under", body)
        self.assertIn('data-ui-ref="gateway.chooser.removed-match-hint"', body)
        self.assertIn('href="/removed-projects"', body)

    def test_no_hint_when_nothing_matches_at_all(self):
        self._ingest(owner="rf_owner", project_name="Unrelated Active Project", filename="unrelated.txt")
        client = self._client_as("rf_owner", 1)

        body = client.get("/projects/choose?q=totally-nonexistent-xyz").get_data(as_text=True)
        self.assertIn("No active projects match", body)
        self.assertNotIn("It may be under", body)

    def test_no_hint_when_active_match_exists(self):
        # A real, findable match must never be shadowed by the hint path.
        doc = self._ingest(owner="rf_owner", project_name="Riverside Project", filename="Test2.txt")
        client = self._client_as("rf_owner", 1)

        body = client.get("/projects/choose?q=Test2").get_data(as_text=True)
        self.assertNotIn("No active projects match", body)
        self.assertNotIn("It may be under", body)
        self.assertIn(doc.project_id, body)

    def test_hint_does_not_leak_a_removed_project_the_user_cannot_access(self):
        # CLAUDE-P32/CLAUDE-P40-E2: removal never changes access - the hint
        # must go through the exact same access filter, not a raw name
        # search, or it would leak the *existence* of an unauthorized
        # removed Project through the hint alone.
        doc = self._ingest(owner="rf_owner", project_name="Riverside Project", filename="Test2.txt")
        owner_client = self._client_as("rf_owner", 1)
        owner_client.post(f"/projects/{doc.project_id}/workspace/remove", data={"confirm": "yes"})

        outsider_client = self._client_as("rf_outsider", 2, role="read_only")
        body = outsider_client.get("/projects/choose?q=Test2").get_data(as_text=True)
        self.assertIn("No active projects match", body)
        self.assertNotIn("It may be under", body)

    def test_true_empty_state_points_to_gateway(self):
        client = self._client_as("rf_owner", 1)
        body = client.get("/projects/choose").get_data(as_text=True)
        self.assertIn("No projects yet.", body)
        self.assertIn("Project Gateway", body)


class RemovedProjectNavAndWordingTests(_BaseReceptionFixTestCase):
    def test_removed_projects_list_chevron_expanded(self):
        client = self._client_as("rf_owner", 1)
        body = client.get("/removed-projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.projects"', body)
        toggle_start = body.index('data-ui-ref="lists.projects"')
        button_open_tag = body.rindex("<button", 0, toggle_start)
        button_close = body.index(">", toggle_start)
        button_tag = body[button_open_tag:button_close]
        self.assertIn('aria-expanded="true"', button_tag)

    def test_removed_project_tombstone_back_link_says_active_projects(self):
        doc = self._ingest(owner="rf_owner", project_name="Test2 Riverside Project")
        client = self._client_as("rf_owner", 1)
        client.post(f"/projects/{doc.project_id}/workspace/remove", data={"confirm": "yes"})

        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Back to Active Projects", body)
        self.assertNotIn(">\n    &larr; Back to Projects<", body)

    def test_removed_projects_listing_back_link_says_active_projects(self):
        client = self._client_as("rf_owner", 1)
        body = client.get("/removed-projects").get_data(as_text=True)
        self.assertIn("Back to Active Projects", body)


class UploadReceptionCopyTests(_BaseReceptionFixTestCase):
    def test_upload_copy_preserves_required_facts(self):
        client = self._client_as("rf_owner", 1)
        body = client.get("/upload").get_data(as_text=True)
        self.assertIn("Establish a Project", body)
        self.assertIn("PDF, DOCX, TXT, CSV, MD", body)
        self.assertIn("MB", body)
        self.assertIn("Scanned drawings", body)
        self.assertIn("native", body)
        self.assertIn("images", body)
