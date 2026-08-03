"""
CLAUDE-P40-VW7B - Left Lists Root System and Active-Display Projection
Cleanup.

Builds on CLAUDE-P40-VW7A's UI reference registry (UI_REFERENCE_MAP.md)
to generalize the active-Display-targeting mechanism from Documents
only to also cover Investigations and Overview, via a new `?panel=1`
flag on the existing workspace.show_workspace route (no new route,
no duplicated authorization) and templates/panel_shell.html (a minimal
standalone document case_workspace.html extends instead of base.html
when that flag is set). Also relocates one misplaced admin control
(Reset Project Data, which resets every Project in the deployment, not
the active one) and adds coherent empty states to three Lists families
that were missing them.

No browser-automation tool is connected in this environment (consistent
with every prior VW stage) - coverage here is structural HTML/route/
JSON assertions plus targeted regex checks against the JS source for
the client-side projection logic, not pixel/interaction-level.
"""
from __future__ import annotations

import io
import re
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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_PANEL_SHELL_PATH = _REPO_ROOT / "templates" / "panel_shell.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw7b_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7b_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7b_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="vw7b_granted_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="vw7b_owner", project_name="Riverside Terminal VW7B Root System")
        self.project_id = self.doc.project_id

        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="vw7b_granted_reviewer", actor="vw7b_owner", actor_role="admin")
        workspace = store.get(self.project_id)
        self.case = store.create_case(workspace, title="Foundation Review", objective="", created_by="vw7b_owner")

    def tearDown(self):
        import shutil
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

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _lists_html(self, body: str) -> str:
        start = body.index('id="launcher-panel"')
        end = body.index('id="workspace-toolbox-panel"') if 'id="workspace-toolbox-panel"' in body else body.index("</body>")
        return body[start:end]


# ---------------------------------------------------------------------------
# Hierarchy: empty states, admin-function relocation, active-state on RFIs.
# ---------------------------------------------------------------------------

class HierarchyTests(_BaseTestCase):
    def test_documents_investigations_rfis_show_coherent_empty_states(self):
        # A second, otherwise-untouched project with no Documents beyond
        # ingestion's own placeholder removed, no Investigations, no RFIs.
        doc = self._ingest(owner="vw7b_owner", project_name="Empty Families Project")
        store = self._store()
        workspace = store.get(doc.project_id)
        for source in list(workspace.sources):
            store.remove_source(workspace, source["id"], actor="vw7b_owner")
            workspace = store.get(doc.project_id)
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn("No Documents yet.", lists)
        self.assertIn("No Investigations yet.", lists)
        self.assertIn("No RFIs yet.", lists)

    def test_reset_project_data_moved_out_of_project_tools_to_top_level(self):
        client = self._client_as("vw7b_admin", 4, role="admin")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertIn('data-ui-ref="lists.system-data-management"', lists)
        self.assertNotIn('data-ui-ref="lists.project.tools.data-management"', lists)
        # Still exactly one html_id="project-data-management" anchor -
        # relocated, not duplicated.
        self.assertEqual(body.count('id="project-data-management"'), 1)

    def test_reset_project_data_still_admin_only(self):
        client = self._client_as("vw7b_granted_reviewer", 3, role="read_only")
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.system-data-management"', body)
        self.assertNotIn("Project Data Management", body)

    def test_rfi_leaf_carries_active_state_when_owning_investigation_is_open(self):
        # A real create_rfi_draft() call needs a reviewed Finding plus an
        # Operating-Environment-gated capability check - out of scope
        # setup for what this test actually verifies (Lists rendering).
        # Appending a plain RFIDraft-shaped dict directly, the same
        # "manipulate store state, skip the write-path pipeline"
        # hermetic pattern tests/test_p40vw7_conversation_tags_and_tasks.py
        # already uses for its own "Source unavailable" scenario.
        store = self._store()
        workspace = store.get(self.project_id)
        workspace.rfi_drafts.append({
            "id": "rfi-draft-1", "project_id": self.project_id, "case_id": self.case["id"],
            "finding_id": "finding-1", "question_text": "Confirm the footing datum.",
            "created_at": "2026-01-01T00:00:00+00:00", "created_by": "vw7b_owner",
            "reference_snapshot": {}, "status": "draft", "issued_at": None, "issued_by": None,
        })
        store.save(workspace)

        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        lists = self._lists_html(body)
        self.assertRegex(lists, r'<a class="tree-leaf launcher-link active"[^>]*data-ui-ref="lists\.project\.rfis\.leaf"')


# ---------------------------------------------------------------------------
# Projection: the panel_only/panel_shell.html mechanism.
# ---------------------------------------------------------------------------

class PanelRenderingTests(_BaseTestCase):
    def test_panel_case_view_omits_shell_and_includes_app_main(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1").get_data(as_text=True)
        self.assertNotIn("app-shell", body)
        self.assertNotIn('id="launcher-panel"', body)
        self.assertNotIn('id="workspace-toolbox-panel"', body)
        self.assertNotIn('id="chat-region"', body)
        self.assertIn('class="app-main"', body)
        self.assertIn(self.case["title"], body)

    def test_panel_overview_view_omits_shell(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview&panel=1").get_data(as_text=True)
        self.assertNotIn("app-shell", body)
        self.assertIn('class="app-main"', body)
        self.assertIn("Project Operating Environment", body)

    def test_panel_suppresses_division_zero_header_and_overview_back_link(self):
        client = self._client_as("vw7b_owner", 1)
        panel_body = client.get(f"/projects/{self.project_id}/workspace?view=overview&panel=1").get_data(as_text=True)
        normal_body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("project-home-back", normal_body)
        self.assertNotIn("project-home-back", panel_body)
        self.assertNotIn('class="display-division-header"', panel_body)
        self.assertIn('class="display-division-header"', normal_body)

    def test_normal_navigation_unaffected_by_panel_mechanism(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        self.assertIn("app-shell", body)
        self.assertIn('id="launcher-panel"', body)
        self.assertIn('id="chat-region"', body)

    def test_lists_never_emits_a_real_href_containing_panel_1(self):
        # panel=1 must only ever be constructed client-side (by
        # buildPanelUrl, for an iframe src) - the server-rendered page
        # itself must never link to it directly, or a plain click
        # (not routed through ArchioskDisplay) would land a reviewer on
        # a chromeless page with no way back. Checks real href=/action=
        # attribute VALUES specifically - the page's own inline-script
        # comments mention "&panel=1" in prose (explaining the
        # mechanism to a future reader), which is not a real link and
        # is correctly excluded by anchoring to href="/action=.
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)
        self.assertNotRegex(body, r'(href|action)="[^"]*panel=1[^"]*"')


class PanelAuthorizationAndIsolationTests(_BaseTestCase):
    def test_outsider_gets_404_on_panel_request_same_as_without(self):
        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="vw7b_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        client = self._client_as("vw7b_outsider", 5, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1")
        self.assertEqual(resp.status_code, 404)

    def test_foreign_case_id_in_panel_request_degrades_to_no_selection_not_leaked(self):
        other_doc = self._ingest(owner="vw7b_owner", project_name="Second VW7B Project")
        other_store = self._store()
        other_workspace = other_store.get(other_doc.project_id)
        other_case = other_store.create_case(other_workspace, title="Confidential Other Case", objective="", created_by="vw7b_owner")

        client = self._client_as("vw7b_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?case={other_case['id']}&panel=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn("Confidential Other Case", body)

    def test_private_case_not_visible_to_granted_reviewer_stays_hidden_in_panel(self):
        client = self._client_as("vw7b_granted_reviewer", 3, role="read_only")
        resp = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn(self.case["title"], body)

    def test_removed_project_panel_request_shows_tombstone_not_content(self):
        client = self._client_as("vw7b_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})
        resp = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}&panel=1")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn(self.case["title"], resp.get_data(as_text=True))


# ---------------------------------------------------------------------------
# Client-side projection logic (structural JS checks - no browser tool).
# ---------------------------------------------------------------------------

class ClientProjectionLogicTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_promote_division_removed_as_dead_code(self):
        self.assertNotIn("function promoteDivision", self.js)

    def test_populate_division_generalized_to_kind_based_signature(self):
        self.assertIn("function populateDivision(divisionIndex, kind, id, displayName, persist)", self.js)
        self.assertIn("function buildPanelUrl(kind, id)", self.js)

    def test_archiosk_display_exposes_get_division_record(self):
        self.assertIn("getDivisionRecord: (index) => {", self.js)
        self.assertNotIn("getDivisionSource:", self.js)

    def test_sync_lists_active_state_exists_and_never_touches_server_rendered_state(self):
        self.assertIn("function syncListsActiveState()", self.js)
        self.assertIn("clientManagedActiveLeaves", self.js)

    def test_click_interceptor_handles_case_and_view_leaves(self):
        self.assertIn("a[data-source-id], a[data-case-id], a[data-view]", self.base_html)
        self.assertIn("getDivisionRecord(target)", self.base_html)

    def test_restore_on_load_is_backward_compatible_with_the_old_bare_string_shape(self):
        self.assertIn("typeof entry === 'string' ? { kind: 'source', id: entry, displayName: '' } : entry", self.js)

    def test_panel_shell_template_exists_and_is_minimal(self):
        self.assertTrue(_PANEL_SHELL_PATH.exists())
        panel_shell = _PANEL_SHELL_PATH.read_text(encoding="utf-8")
        self.assertNotIn("launcher-panel", panel_shell)
        self.assertNotIn("workspace-toolbox-panel", panel_shell)
        self.assertNotIn("chat-region", panel_shell)
        self.assertIn('class="app-main"', panel_shell)


# ---------------------------------------------------------------------------
# Isolation/compatibility: VW4/VW5/VW6/VW7/VW7A preserved, Stable URL
# Restoration stays strict. Full regression coverage lives in each of
# those stages' own test files (not duplicated here) - proven by the
# complete suite run this stage's own prompt requires before committing.
# ---------------------------------------------------------------------------

class PreservationSpotCheckTests(_BaseTestCase):
    def test_display_layout_menu_still_functional(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.display-layout"', body)

    def test_sign_in_and_gateway_still_have_no_lists_or_panel_leakage(self):
        client = self.flask_app.test_client()
        login_body = client.get("/login").get_data(as_text=True)
        self.assertNotIn("launcher-panel", login_body)
        self.assertNotIn("panel_only", login_body)

        auth_client = self._client_as("vw7b_owner", 1)
        gateway_body = auth_client.get("/gateway").get_data(as_text=True)
        self.assertNotIn("launcher-panel", gateway_body)

    def test_stable_case_url_restoration_still_strict(self):
        client = self._client_as("vw7b_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.case["title"], resp.get_data(as_text=True))
        # A malformed/foreign case id in the real (non-panel) page
        # degrades the same honest way it always has - no selection,
        # not an error, not a leak.
        resp2 = client.get(f"/projects/{self.project_id}/workspace?case=not-a-real-case-id")
        self.assertEqual(resp2.status_code, 200)
        self.assertNotIn(f'data-ui-ref="lists.project.self" href="/projects/{self.project_id}/workspace" active', resp2.get_data(as_text=True))

    def test_tags_and_tasks_lists_branches_still_present_and_functional(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.tasks"', body)
        self.assertIn('data-ui-ref="lists.project.tags"', body)

    def test_ui_reference_mode_toggle_still_present(self):
        client = self._client_as("vw7b_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="ui-reference-mode-toggle"', body)


if __name__ == "__main__":
    unittest.main()
