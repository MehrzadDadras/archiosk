"""
CLAUDE-P40-E2B1 - Single Launcher Panel and Display-Projected
Directories.

Product correction on top of P40-E2B: that stage left two physical left
panels rendering simultaneously (base.html's global side rail AND
case_workspace.html's own Workspace-local Lists panel), confirmed by the
P40-E2B-QA-CLOSE audit. This stage eliminates the second column
entirely - there is now exactly one left panel (the launcher panel,
base.html, application-shell level), restrained to high-level
orientation and direct launchers (Projects/Documents/Investigations/
Chats/New Project/identity), never a full listing. Clicking a launcher
projects the corresponding directory into Display instead.

No browser/rendering tool exists in this environment - these tests
verify what IS provable without one: server-rendered HTML/attributes,
real route behavior, and the actual CSS rules a browser would apply.
Stated honestly rather than skipped.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import re
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

_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"
_BASE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "base.html"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40e2b1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e2b1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e2b1_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e2b1_owner", project_name="Riverside P40E2B1 Workspace")
        self.project_id = self.doc.project_id

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

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


# ---------------------------------------------------------------------------
# 1-2: exactly one left panel, no Workspace-local Lists column
# ---------------------------------------------------------------------------

class SingleLeftPanelTests(_BaseTestCase):
    def test_exactly_one_left_panel_on_project_home(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertEqual(body.count('id="launcher-panel"'), 1)
        self.assertNotIn("workspace-lists-panel", body)
        self.assertNotIn('class="workspace-pane-lists"', body)

    def test_exactly_one_left_panel_on_investigation_open(self):
        client = self._client_as("p40e2b1_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertEqual(body.count('id="launcher-panel"'), 1)
        self.assertNotIn("workspace-lists-panel", body)

    def test_exactly_one_left_panel_on_every_directory_view(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in ("documents", "investigations", "chats"):
            body = client.get(f"/projects/{self.project_id}/workspace?view={view}").get_data(as_text=True)
            self.assertEqual(body.count('id="launcher-panel"'), 1, f"view={view}")
            self.assertNotIn("workspace-lists-panel", body, f"view={view}")

    def test_exactly_one_left_panel_on_non_workspace_pages(self):
        client = self._client_as("p40e2b1_owner", 1)
        for url in ("/", "/projects", "/upload", "/removed-projects"):
            body = client.get(url).get_data(as_text=True)
            self.assertEqual(body.count('id="launcher-panel"'), 1, url)

    def test_case_workspace_grid_no_longer_declares_a_lists_area(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"lists display toolbox"', css)
        self.assertNotIn("grid-area: lists", css)
        self.assertNotIn(".workspace-pane-lists", css)


# ---------------------------------------------------------------------------
# 3: top bar spans the complete authenticated shell
# ---------------------------------------------------------------------------

class TopBarSpansShellTests(_BaseTestCase):
    def test_top_bar_lives_in_base_html_not_case_workspace(self):
        base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('class="workspace-topbar"', base_html)
        case_workspace_html = (Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html").read_text(encoding="utf-8")
        self.assertNotIn('<div class="workspace-topbar">', case_workspace_html)

    def test_top_bar_renders_identically_on_workspace_and_non_workspace_pages(self):
        client = self._client_as("p40e2b1_owner", 1)
        for url in (f"/projects/{self.project_id}/workspace", "/", "/projects"):
            body = client.get(url).get_data(as_text=True)
            self.assertEqual(body.count('class="workspace-topbar"'), 1, url)

    def test_top_bar_is_a_sibling_of_app_shell_body_not_nested_inside_it(self):
        # Proves the bar structurally spans Launcher/Display/Toolbox
        # (Section F) rather than being confined to one column - it
        # must appear in the DOM before the launcher panel/app-shell-body
        # wrapper opens, not inside it.
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        topbar_pos = body.index('class="workspace-topbar"')
        body_wrapper_pos = body.index('class="app-shell-body"')
        self.assertLess(topbar_pos, body_wrapper_pos)

    def test_display_layout_and_toolbox_toggle_only_appear_within_a_workspace(self):
        client = self._client_as("p40e2b1_owner", 1)
        workspace_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-layout-menu"', workspace_body)
        self.assertIn('id="toolbox-toggle-btn"', workspace_body)

        home_body = client.get("/").get_data(as_text=True)
        self.assertNotIn('id="workspace-layout-menu"', home_body)
        self.assertNotIn('id="toolbox-toggle-btn"', home_body)


# ---------------------------------------------------------------------------
# 4: Project names only appear under Projects
# ---------------------------------------------------------------------------

class ProjectNamesOnlyUnderProjectsTests(_BaseTestCase):
    def test_other_project_names_do_not_leak_into_an_open_workspace(self):
        other = self._ingest(owner="p40e2b1_owner", project_name="A Distinct Other Project Name")
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        # The other Project legitimately appears once, in the launcher's
        # own Projects list - never a second time describing THIS
        # Project's own content.
        self.assertEqual(body.count("A Distinct Other Project Name"), 1)
        launcher_start = body.index('id="launcher-panel"')
        launcher_end = body.index("</nav>", launcher_start)
        self.assertIn("A Distinct Other Project Name", body[launcher_start:launcher_end])


# ---------------------------------------------------------------------------
# 5-6: Documents/Investigations launchers open their directories in Display
# ---------------------------------------------------------------------------

class DirectoryLauncherTests(_BaseTestCase):
    def test_documents_launcher_link_targets_the_documents_directory(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?view=documents"', body)

    def test_documents_directory_lists_sources_and_supports_adding_one(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        self.assertIn("rfp.txt", body)
        self.assertIn('action="/projects/{}/workspace/sources/document"'.format(self.project_id), body)
        self.assertIn("display-division-header-name", body)
        self.assertIn("Documents", body)

    def test_investigations_launcher_link_targets_the_investigations_directory(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?view=investigations"', body)

    def test_investigations_directory_lists_every_authorized_investigation(self):
        client = self._client_as("p40e2b1_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Schedule Conflict Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertIn("Schedule Conflict Review", body)
        self.assertIn('class="case-item', body)

    def test_documents_and_investigations_directories_are_mutually_exclusive_with_project_home(self):
        client = self._client_as("p40e2b1_owner", 1)
        docs_body = client.get(f"/projects/{self.project_id}/workspace?view=documents").get_data(as_text=True)
        self.assertNotIn('class="project-home"', docs_body)
        inv_body = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertNotIn('class="project-home"', inv_body)


# ---------------------------------------------------------------------------
# 7: a new Investigation appears immediately in its directory
# ---------------------------------------------------------------------------

class NewInvestigationAppearsImmediatelyTests(_BaseTestCase):
    def test_new_investigation_appears_in_directory_on_next_visit(self):
        client = self._client_as("p40e2b1_owner", 1)
        before = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertNotIn("Newly Created Investigation", before)

        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Newly Created Investigation", "objective": ""})

        after = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertIn("Newly Created Investigation", after)

    def test_launcher_investigation_count_updates_immediately(self):
        client = self._client_as("p40e2b1_owner", 1)
        before = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('Investigations <span class="launcher-count">0</span>', before)

        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Count Check", "objective": ""})

        after = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('Investigations <span class="launcher-count">1</span>', after)


# ---------------------------------------------------------------------------
# 8: selecting an Investigation activates its content and the shared Chat dock
# ---------------------------------------------------------------------------

class SelectingInvestigationActivatesChatTests(_BaseTestCase):
    def test_selecting_from_the_directory_opens_content_and_the_one_chat_dock(self):
        client = self._client_as("p40e2b1_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Selected Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        directory_body = client.get(f"/projects/{self.project_id}/workspace?view=investigations").get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?case={case_id}"', directory_body)

        opened_body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("<h2>Selected Investigation</h2>", opened_body)
        self.assertEqual(opened_body.count('id="conversation-dock"'), 1)
        self.assertIn(f'data-conversation-scope="case-{case_id}"', opened_body)


# ---------------------------------------------------------------------------
# 9: stable refresh / Back-Forward for every projected directory
# ---------------------------------------------------------------------------

class StableDirectoryUrlTests(_BaseTestCase):
    def test_each_directory_has_its_own_stable_query_url_that_reproduces_on_refetch(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in ("documents", "investigations", "chats"):
            url = f"/projects/{self.project_id}/workspace?view={view}"
            first = client.get(url)
            second = client.get(url)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            # A plain GET on the same URL - the definition of "supports
            # refresh and Back/Forward" for a classic server-rendered
            # page with no client-side router.
            self.assertEqual(first.get_data(as_text=True).count("display-division-header-name"),
                              second.get_data(as_text=True).count("display-division-header-name"))

    def test_unknown_view_value_degrades_to_project_home_not_an_error(self):
        client = self._client_as("p40e2b1_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?view=not-a-real-view")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Project Home", resp.get_data(as_text=True))


# ---------------------------------------------------------------------------
# 10: unauthorized names/counts/content never render
# ---------------------------------------------------------------------------

class AuthorizationFilteringTests(_BaseTestCase):
    def test_outsider_gets_404_not_a_filtered_workspace(self):
        client = self._client_as("p40e2b1_outsider", 2, role="read_only")
        for view in (None, "documents", "investigations", "chats"):
            url = f"/projects/{self.project_id}/workspace" + (f"?view={view}" if view else "")
            resp = client.get(url)
            self.assertEqual(resp.status_code, 404, url)

    def test_private_investigation_not_named_in_investigations_directory(self):
        owner = self._client_as("p40e2b1_owner", 1)
        owner.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": "Confidential Investigation"},
        )
        case_id = self._store().get(self.project_id).cases[0]["id"]
        from services.case_workspace import CaseWorkspaceStore, CASE_VISIBILITY_PRIVATE
        store = self._store()
        workspace = store.get(self.project_id)
        for case in workspace.cases:
            if case["id"] == case_id:
                case["visibility"] = CASE_VISIBILITY_PRIVATE
        store.save(workspace)

        from models import User, db
        with self.flask_app.app_context():
            db.session.add(User(username="p40e2b1_second_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add_all([])
            from services.case_workspace import CaseWorkspaceStore as _CWS
        other = self._client_as("p40e2b1_second_reviewer", 3, role="read_only")
        # A non-owner read_only reviewer with no explicit project access
        # is denied the whole page (P32 deny-by-default) - the private
        # Investigation's name is never reachable via the directory
        # either way, whether via a 404 or a filtered listing.
        resp = other.get(f"/projects/{self.project_id}/workspace?view=investigations")
        self.assertIn(resp.status_code, (403, 404))


# ---------------------------------------------------------------------------
# 11: exactly one Toolbox / Chat dock / composer / Send / Display Layout menu
# ---------------------------------------------------------------------------

class ExactlyOneOfEachTests(_BaseTestCase):
    def _assert_exactly_one_of_each(self, body: str):
        self.assertEqual(body.count('id="workspace-toolbox-panel"'), 1)
        self.assertEqual(body.count('id="conversation-dock"'), 1)
        self.assertEqual(body.count('class="conversation-input-form conversation-dock-composer"'), 1)
        self.assertEqual(body.count(">Send<"), 1)
        self.assertEqual(body.count('id="workspace-layout-menu"'), 1)

    def test_exactly_one_of_each_on_project_home(self):
        client = self._client_as("p40e2b1_owner", 1)
        self._assert_exactly_one_of_each(client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True))

    def test_exactly_one_of_each_on_every_directory_view(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in ("documents", "investigations", "chats"):
            body = client.get(f"/projects/{self.project_id}/workspace?view={view}").get_data(as_text=True)
            self._assert_exactly_one_of_each(body)

    def test_exactly_one_of_each_with_investigation_open(self):
        client = self._client_as("p40e2b1_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Open Investigation", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self._assert_exactly_one_of_each(body)


# ---------------------------------------------------------------------------
# 12: panel collapse/resize/responsive behaviour remains intact
# ---------------------------------------------------------------------------

class PanelBehaviorIntactTests(_BaseTestCase):
    def test_launcher_toggle_and_toolbox_toggle_both_present_and_independent(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="launcher-toggle-btn"', body)
        self.assertIn('id="toolbox-toggle-btn"', body)
        self.assertIn("beehive:panel:launcher", body)
        self.assertIn(f"beehive:panel:toolbox:{self.project_id}", body)

    def test_chat_resize_handle_still_present_in_every_state(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in (None, "documents", "investigations", "chats"):
            url = f"/projects/{self.project_id}/workspace" + (f"?view={view}" if view else "")
            body = client.get(url).get_data(as_text=True)
            self.assertIn('id="conversation-dock-resize-handle"', body, url)

    def test_narrow_screen_drawer_rules_exist_for_both_panels(self):
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("html.launcher-hidden .launcher-panel { display: none; }", css)
        self.assertIn("html.toolbox-hidden .workspace-pane-toolbox {\n    display: none;\n}", css)


# ---------------------------------------------------------------------------
# 13: auth templates remain isolated
# ---------------------------------------------------------------------------

class AuthTemplatesIsolatedTests(_BaseTestCase):
    def test_login_page_has_no_launcher_panel_or_top_bar(self):
        client = self.flask_app.test_client()
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn('id="launcher-panel"', body)
        self.assertNotIn('class="workspace-topbar"', body)

    def test_auth_shell_does_not_extend_base_html(self):
        auth_shell = (Path(__file__).resolve().parent.parent / "templates" / "auth_shell.html").read_text(encoding="utf-8")
        self.assertNotIn('{% extends "base.html"', auth_shell)
        self.assertNotIn('{% extends "gateway_base.html"', auth_shell)


if __name__ == "__main__":
    unittest.main()
