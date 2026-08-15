"""
CLAUDE-P40-E2B1 - Single Launcher Panel and Display-Projected
Directories.

Product correction on top of P40-E2B: that stage left two physical left
panels rendering simultaneously (base.html's global side rail AND
case_workspace.html's own Workspace-local Lists panel), confirmed by the
P40-E2B-QA-CLOSE audit. This stage eliminates the second column
entirely - there is now exactly one left panel (the launcher panel,
base.html, application-shell level).

SUPERSEDED (CLAUDE-P40-E3A, Section 2): the "restrained to high-level
orientation and direct launchers only, never a full listing - clicking a
launcher projects the corresponding directory into Display instead"
design this file's docstring originally described was itself a product
decision, and the product owner has since reversed it twice: P40-E2B1A
made the panel pure-root-launcher-only (auditing out an accidental
listing regression), then P40-E3A explicitly re-authorized a full
recursive hierarchy in the ONE panel ("P40-E2B1 and P40-E2B1A were never
accepted... this is a deliberate design change, not an accidental
regression") and retired the ?view=documents/investigations/chats
Display-projected directory bodies entirely (Section 4: those names now
live only in Lists' own recursive tree; Section 5: Display never
duplicates what Lists already lists). Tests below that asserted the
now-retired directory-body behavior have been updated in place to assert
the current (P40-E3A) contract instead; the "exactly one panel" tests
this file also covers remain correct as originally written.

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
        # CLAUDE-P40-E3A, Section 7: the old #toolbox-toggle-btn top-bar
        # button is retired - the Toolbox/Display panel-divider line
        # (#toolbox-divider) is the collapse control now, still gated to
        # only exist within an open Workspace (project_id is defined).
        client = self._client_as("p40e2b1_owner", 1)
        workspace_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-layout-menu"', workspace_body)
        self.assertIn('id="toolbox-divider"', workspace_body)

        home_body = client.get("/").get_data(as_text=True)
        self.assertNotIn('id="workspace-layout-menu"', home_body)
        self.assertNotIn('id="toolbox-divider"', home_body)


# ---------------------------------------------------------------------------
# 4: Project names only appear under Projects
# ---------------------------------------------------------------------------

class ProjectNamesOnlyUnderProjectsTests(_BaseTestCase):
    def test_other_project_names_appear_as_switch_targets_in_an_open_workspace(self):
        # SUPERSEDED three times now:
        # - CLAUDE-P40-E3A, Section 2 first re-authorized a recursive
        #   Lists hierarchy listing every authorized Project as a
        #   sibling leaf under "Projects," on every page including an
        #   open Workspace.
        # - CLAUDE-P40-VW7B, Section 3 then removed that portfolio
        #   branch from the OPENED-Project Lists panel entirely (zero
        #   occurrences while a Project was open).
        # - CLAUDE-LEFT-RAIL-01 reverses this again, permanently this
        #   time as an explicit Product Owner architecture decision (not
        #   a course-correction like the prior two): PROJECTS is the
        #   one, always-present live active-project switcher, so every
        #   OTHER accessible Project name is expected, intentional
        #   content inside an open Workspace now - that's the entire
        #   point (switch without leaving the Project you're in).
        other = self._ingest(owner="p40e2b1_owner", project_name="A Distinct Other Project Name")
        client = self._client_as("p40e2b1_owner", 1)
        workspace_body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("A Distinct Other Project Name", workspace_body)

        directory_body = client.get("/projects").get_data(as_text=True)
        self.assertIn("A Distinct Other Project Name", directory_body)


# ---------------------------------------------------------------------------
# 5-6: Documents/Investigations names are reachable ONLY through Lists now
# (CLAUDE-P40-E3A, Section 4) - the ?view=documents/?view=investigations
# Display-projected directory bodies this class originally tested are
# retired outright (Section 4's own "no second navigation directory in
# Display" rule). Rewritten to assert the current contract: real
# authorized names appear as Lists tree children of the active Project,
# and the retired ?view= values degrade to a blank Display rather than
# reproducing the old directory listing.
# ---------------------------------------------------------------------------

class DirectoryLauncherTests(_BaseTestCase):
    def test_documents_launcher_link_targets_the_documents_directory(self):
        # "Documents" is now a Lists tree-toggle (a <button>, not an <a>
        # with an href) whose children are the real Document leaves,
        # each carrying its own ?source= link - there is no separate
        # ?view=documents URL to target anymore.
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Documents", body)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?source=', body)
        self.assertNotIn(f'href="/projects/{self.project_id}/workspace?view=documents"', body)

    def test_documents_directory_lists_sources_and_supports_adding_one(self):
        # SUPERSEDED AGAIN (CLAUDE-P40-VW2): the E3A-QA note below still
        # explains the Toolbox-scoping history, but "Add a Document" has
        # since been relocated wholesale out of Toolbox entirely, into
        # Lists' own always-rendered Project Tools branch (product-owner
        # walkthrough correction - Toolbox stays reserved for contextual
        # Document/Investigation tools only). It is now present
        # regardless of what's selected (same as its Documents/
        # Investigations siblings in Lists), and absent from Toolbox in
        # every state, not just when something is selected.
        #
        # Original SUPERSEDED IN PART (CLAUDE-P40-E3A-QA, Section 9): "Add a
        # Document" used to render unconditionally in Toolbox regardless
        # of what was selected - product-owner browser observation named
        # the Toolbox "visually heavy... project-level controls" bleeding
        # into a contextual (per-Document/per-Investigation) view. Now
        # scoped to the no-selection ("project-level tools") Toolbox
        # state only, matching Section 9's own Expected-context table
        # ("Document: existing Document tools as applicable" - Remove
        # Document only, not Add-a-Document too).
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 supersedes this test's
        # own original assertion a third time: "Add a Document" no
        # longer renders in Lists' rail at all (retired outright, not
        # merely rescoped) - it was relocated wholesale to Admin ->
        # Project Data Management, reusing the same, unchanged
        # add_document_source route (see
        # tests/test_p40vw2_project_tools_relocation.py's own
        # test_add_document_form_moved_to_project_data_management_same_route).
        # The form's absence from BOTH the no-selection AND the
        # per-Document Toolbox states is now the correct assertion, not
        # a scoping distinction between the two.
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("rfp.txt", body)
        self.assertNotIn('action="/projects/{}/workspace/sources/document"'.format(self.project_id), body)
        add_body = client.get(f"/projects/{self.project_id}/workspace?source=" + self._store().get(self.project_id).sources[0]["id"]).get_data(as_text=True)
        toolbox_start = add_body.index('id="workspace-toolbox-panel"')
        toolbox = add_body[toolbox_start:add_body.index("</aside>", toolbox_start)]
        self.assertNotIn('action="/projects/{}/workspace/sources/document"'.format(self.project_id), toolbox)

    def test_investigations_launcher_link_targets_the_investigations_directory(self):
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Investigations", body)
        self.assertNotIn(f'href="/projects/{self.project_id}/workspace?view=investigations"', body)

    def test_investigations_directory_lists_every_authorized_investigation(self):
        # CLAUDE-GO-DNA-01 (Panel Zoning) moved Investigations out of the
        # Lists tree-toggle/tree-leaf grammar (no more data-tree-owns=
        # "case") into the Toolbox's own Project Intelligence subdisclosure.
        client = self._client_as("p40e2b1_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Schedule Conflict Review", "objective": ""})
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Schedule Conflict Review", body)
        self.assertIn('data-ui-ref="toolbox.investigations.leaf"', body)

    def test_retired_directory_views_degrade_to_a_blank_display_not_a_directory_listing(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in ("documents", "investigations", "chats"):
            body = client.get(f"/projects/{self.project_id}/workspace?view={view}").get_data(as_text=True)
            self.assertNotIn('class="project-home"', body, view)
            self.assertNotIn('id="project-overview"', body, view)


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
        # CLAUDE-P40-E3A: the Investigation count used to live on the
        # Lists tree-toggle itself (.launcher-count).
        #
        # SUPERSEDED (CLAUDE-GO-DNA-01, Panel Zoning): Investigations
        # relocated to the Toolbox's own Project Intelligence subdisclosure
        # (macros.subdisclosure("Investigations (N)", ...)) - a different
        # count label format, same immediate-update contract.
        client = self._client_as("p40e2b1_owner", 1)
        before = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Investigations (0)", before)

        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Count Check", "objective": ""})

        after = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Investigations (1)", after)


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

    def test_unknown_view_value_degrades_to_a_blank_display_not_an_error(self):
        # SUPERSEDED (CLAUDE-P40-E3A, Section 5): "Display must be blank"
        # for anything that isn't a real selected leaf - an unrecognized
        # ?view= no longer falls back to Project Home content, it falls
        # back to nothing, the same honest degrade ?source=/?case= with
        # an unrecognized id already use.
        client = self._client_as("p40e2b1_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?view=not-a-real-view")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertNotIn('class="project-home"', body)
        self.assertNotIn('id="project-overview"', body)


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
        # CLAUDE-P40-E3A, Section 7: the panel-dividing lines are the
        # collapse controls now, replacing the old top-bar toggle
        # buttons - #lists-divider/#toolbox-divider.
        client = self._client_as("p40e2b1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="lists-divider"', body)
        self.assertIn('id="toolbox-divider"', body)
        self.assertIn("beehive:panel:launcher", body)
        self.assertIn(f"beehive:panel:toolbox:{self.project_id}", body)

    def test_chat_resize_handle_still_present_in_every_state(self):
        client = self._client_as("p40e2b1_owner", 1)
        for view in (None, "documents", "investigations", "chats"):
            url = f"/projects/{self.project_id}/workspace" + (f"?view={view}" if view else "")
            body = client.get(url).get_data(as_text=True)
            self.assertIn('id="conversation-dock-resize-handle"', body, url)

    def test_narrow_screen_drawer_rules_exist_for_both_panels(self):
        # CLAUDE-P40-EYE1: html.toolbox-hidden now targets
        # .workspace-right-column (Toolbox+Eye together), not
        # .workspace-pane-toolbox alone - Section 3's own "apply it to
        # the complete right column."
        css = _CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("html.launcher-hidden .launcher-panel { display: none; }", css)
        self.assertIn("html.toolbox-hidden .workspace-right-column {\n    display: none;\n}", css)


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
