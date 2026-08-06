"""
CLAUDE-P40-VW8-QA - New Investigation Action in Lists.

Product-owner walkthrough evidence: the Investigations root in Lists
has a disclosure chevron and count, but no visible way to START one
from inside that family - the only path was the Overview page's own
buried "+ Start Investigation" subdisclosure.

Adds a real "+ New Investigation" action row, always first inside the
expanded family (present even at zero Investigations - never gated on
count), reusing the existing routes/workspace.py:create_case route/
services.case_workspace.CaseWorkspaceStore.create_case service
unchanged - no parallel Investigation-creation implementation.
Deliberately an <a> action row, never an HTML radio (radios represent
mutually-exclusive choices; this is a command).

No browser-automation tool is connected in this environment (consistent
with every prior VW stage) - keyboard/focus-return behavior is verified
structurally (the toggle's own click listener is bound directly to the
<button data-tree-parent> element, never a delegated listener that
could also catch the sibling action row's clicks - see
JavaScriptStructureTests below), not via a live interaction trace.
"""
from __future__ import annotations

import io
import re
import uuid
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw8qa_newinv_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="newinv_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="newinv_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.flask_app.app_context():
                from services.ingestion import ingest_upload
                self.doc = ingest_upload(
                    _fake_file(b"content", "rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="newinv_owner", project_name="New Investigation Project",
                )
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class ActionRowAvailabilityTests(_BaseTestCase):
    def test_new_investigation_action_present_at_zero_count(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.investigations.new"', body)
        self.assertIn("No Investigations yet.", body)

    def test_new_investigation_action_is_not_a_radio_input(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        match = re.search(r'<a[^>]*data-ui-ref="lists\.project\.investigations\.new"[^>]*>', body)
        self.assertIsNotNone(match)
        self.assertEqual(match.group(0).count("<input"), 0)

    def test_action_row_appears_before_existing_investigations_in_source_order(self):
        client = self._client_as("newinv_owner", 1)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            store.create_case(workspace, title="Existing Investigation", objective="", created_by="newinv_owner")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        new_action_pos = body.index('data-ui-ref="lists.project.investigations.new"')
        existing_leaf_pos = body.index('data-ui-ref="lists.project.investigations.leaf"')
        self.assertLess(new_action_pos, existing_leaf_pos)

    def test_action_row_still_present_with_existing_investigations(self):
        client = self._client_as("newinv_owner", 1)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            store.create_case(workspace, title="Existing Investigation", objective="", created_by="newinv_owner")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.investigations.new"', body)
        self.assertIn("Existing Investigation", body)


class ProjectionTests(_BaseTestCase):
    def test_standalone_new_case_form_renders_create_and_cancel(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.investigations.new.form"', body)
        self.assertIn('data-ui-ref="lists.project.investigations.new.create"', body)
        self.assertIn('data-ui-ref="lists.project.investigations.new.cancel"', body)

    def test_panel_only_new_case_form_omits_back_to_overview_chrome(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case&panel=1").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.investigations.new.form"', body)
        self.assertNotIn("project-home-back", body)

    def test_panel_only_new_case_form_extends_panel_shell_not_full_base(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case&panel=1").get_data(as_text=True)
        self.assertNotIn('id="launcher-panel"', body)

    def test_new_case_form_does_not_render_the_full_management_page(self):
        # Not the Overview page (no accordion/subdisclosure chrome for
        # unrelated Project Home sections) - a focused form only.
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case").get_data(as_text=True)
        self.assertNotIn("Needs Attention", body)
        self.assertNotIn("Requirement Compliance", body)

    def test_a_real_case_selection_takes_priority_over_new_case_view(self):
        client = self._client_as("newinv_owner", 1)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            case = store.create_case(workspace, title="Real Case", objective="", created_by="newinv_owner")
        body = client.get(f"/projects/{self.project_id}/workspace?case={case['id']}&view=new-case").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.project.investigations.new.form"', body)
        self.assertIn("Real Case", body)


class CreationTests(_BaseTestCase):
    def test_valid_submission_creates_exactly_one_investigation(self):
        client = self._client_as("newinv_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Foundation Review", "objective": "Check footing depth", "source": "new-case-form"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/workspace?case=", resp.headers["Location"])
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 1)
            self.assertEqual(workspace.cases[0]["title"], "Foundation Review")

    def test_count_and_leaf_appear_after_creation(self):
        client = self._client_as("newinv_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Foundation Review", "source": "new-case-form"},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('Investigations <span class="launcher-count">1</span>', body)
        self.assertIn("Foundation Review", body)

    def test_new_investigation_added_under_the_same_family(self):
        client = self._client_as("newinv_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Foundation Review", "source": "new-case-form"},
        )
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        investigations_start = body.index('data-ui-ref="lists.project.investigations"')
        investigations_leaf = body.index('data-ui-ref="lists.project.investigations.leaf"')
        rfis_start = body.index('data-ui-ref="lists.project.rfis"')
        self.assertLess(investigations_start, investigations_leaf)
        self.assertLess(investigations_leaf, rfis_start)

    def test_created_investigation_is_selected_per_existing_repository_behavior(self):
        # "Select or open the new Investigation according to existing
        # repository behavior" - the same ?case=<id> redirect
        # create_case already used before this stage.
        client = self._client_as("newinv_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Foundation Review", "source": "new-case-form"},
        )
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            case_id = workspace.cases[0]["id"]
        self.assertIn(f"case={case_id}", resp.headers["Location"])

    def test_panel_projected_success_redirect_preserves_panel_state(self):
        client = self._client_as("newinv_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Foundation Review", "source": "new-case-form", "panel": "1"},
        )
        self.assertIn("panel=1", resp.headers["Location"])


class CancelAndValidationFailureTests(_BaseTestCase):
    def test_empty_title_creates_nothing(self):
        client = self._client_as("newinv_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "", "source": "new-case-form"},
        )
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 0)

    def test_empty_title_redirects_back_to_the_same_focused_form(self):
        client = self._client_as("newinv_owner", 1)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "  ", "source": "new-case-form"},
        )
        self.assertIn("view=new-case", resp.headers["Location"])

    def test_validation_error_is_shown_on_the_new_case_form(self):
        client = self._client_as("newinv_owner", 1)
        client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "", "source": "new-case-form"},
        )
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case").get_data(as_text=True)
        self.assertIn("A Case needs a title.", body)

    def test_cancel_link_points_to_overview_and_creates_nothing(self):
        client = self._client_as("newinv_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=new-case").get_data(as_text=True)
        match = re.search(r'<a[^>]*href="([^"]+)"[^>]*data-ui-ref="lists\.project\.investigations\.new\.cancel"', body)
        self.assertIsNotNone(match)
        self.assertIn("view=overview", match.group(1))
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 0)

    def test_expanding_the_family_alone_creates_no_record(self):
        # Merely GETting the workspace page (which renders the expanded/
        # collapsed family) must never itself create an Investigation.
        client = self._client_as("newinv_owner", 1)
        client.get(f"/projects/{self.project_id}/workspace")
        client.get(f"/projects/{self.project_id}/workspace?case=doesnotexist")
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 0)


class NoDuplicateCreationTests(_BaseTestCase):
    def test_two_distinct_submissions_create_two_distinct_investigations(self):
        client = self._client_as("newinv_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "First", "source": "new-case-form"})
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Second", "source": "new-case-form"})
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 2)
            titles = {c["title"] for c in workspace.cases}
            self.assertEqual(titles, {"First", "Second"})

    def test_a_single_submission_never_creates_more_than_one_record(self):
        client = self._client_as("newinv_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Only One", "source": "new-case-form"})
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 1)


class AuthorizationTests(_BaseTestCase):
    def test_unauthenticated_request_cannot_reach_new_case_form(self):
        client = self.flask_app.test_client()
        resp = client.get(f"/projects/{self.project_id}/workspace?view=new-case")
        self.assertEqual(resp.status_code, 302)

    def test_unauthenticated_request_cannot_create_an_investigation(self):
        client = self.flask_app.test_client()
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Sneaky", "source": "new-case-form"})
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 0)

    def test_a_stranger_without_project_access_cannot_create_an_investigation(self):
        client = self._client_as("newinv_reader", 2, role="read_only")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Unauthorized Investigation", "source": "new-case-form"},
        )
        self.assertEqual(resp.status_code, 404)
        with self.flask_app.app_context():
            from services.case_workspace import CaseWorkspaceStore
            store = CaseWorkspaceStore(self.tmp_dir)
            workspace = store.get(self.project_id)
            self.assertEqual(len(workspace.cases), 0)


class JavaScriptStructureTests(unittest.TestCase):
    """No browser-automation tool is connected - these pin down the
    structural properties that make 'clicking + New Investigation
    cannot accidentally collapse the family' and 'projects into Display'
    true, without a live interaction trace."""

    def setUp(self):
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_tree_toggle_click_listener_is_bound_directly_to_the_toggle_button(self):
        # Not a delegated listener on the parent <li> or <ul> that could
        # also fire for a click on the sibling action row.
        idx = self.base_html.index("root.querySelectorAll('[data-tree-parent]').forEach(function (toggle) {")
        window = self.base_html[idx:idx + 1200]
        self.assertIn("toggle.addEventListener('click'", window)

    def test_click_interceptor_recognizes_data_new_case(self):
        self.assertIn("a[data-new-case]", self.base_html)
        self.assertIn("kind = 'new-case'", self.base_html)

    def test_populate_division_handles_new_case_kind(self):
        # CLAUDE-P40-VW8-QA1: populateDivision's own kind === 'case' ||
        # kind === 'overview' || kind === 'new-case' chain was generalized
        # into one shared PANEL_KINDS registry lookup (see that table's own
        # header comment in case_workspace.js) - 'new-case' is handled
        # because it is a registered key in that table, not because
        # populateDivision itself names it.
        populate_idx = self.js.index("function populateDivision(")
        # CLAUDE-MM4 widened this window (was 1200) - see the matching
        # comment in tests/test_p40vw8qa1_stable_surface_extension_point.py.
        populate_body = self.js[populate_idx:populate_idx + 2200]
        self.assertIn("PANEL_KINDS[kind]", populate_body)
        table_idx = self.js.index("const PANEL_KINDS = {")
        table = self.js[table_idx:self.js.index("\n        };", table_idx)]
        self.assertIn("'new-case':", table)

    def test_build_panel_url_maps_new_case_to_the_view_query_param(self):
        # CLAUDE-P40-VW8-QA1: buildPanelUrl itself now just delegates to
        # whichever PANEL_KINDS entry matches - the 'new-case' -> ?view=
        # mapping lives in that entry's own buildQuery, not in
        # buildPanelUrl's own body.
        table_idx = self.js.index("const PANEL_KINDS = {")
        table = self.js[table_idx:self.js.index("\n        };", table_idx)]
        entry_idx = table.index("'new-case':")
        entry = table[entry_idx:entry_idx + 200]
        self.assertIn("'view'", entry)
        self.assertIn("'new-case'", entry)


if __name__ == "__main__":
    unittest.main()
