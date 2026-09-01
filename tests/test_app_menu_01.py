"""
CLAUDE-APP-MENU-01 - the ARCHIOSK application menu bar (Archiosk | File |
Edit | View | Document | Tools | Window | Help), top-left, above the
working surfaces.

Command reuse is the central invariant this stage introduces: every menu
item either navigates to a real existing route, clicks a real existing
control by id (data-reuse-control, static/js/app_menu.js), or calls one
of a small named set of real actions (data-action) - never a second
implementation of a command that already exists elsewhere. These tests
follow the same practical split test_icon_intelligence_01.py already
established: static structure/JS-source checks for the state grammar
(cheap, precise), plus live-rendered checks (via the app test client,
same _BaseTestCase shape as test_p40vw7a_ui_reference_map.py) for
authorization-aware presence/absence.
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
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
# CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the menu bar's
# own markup was extracted out of base.html into this shared partial
# ({% include %}d by both base.html and gateway_shell.html) - static
# structure checks below read this file, not base.html, for anything
# menu-bar-shaped. base.html itself still holds the data-reuse-control
# TARGET ids (doc-print, doc-annotate-*, toolbox-compare-btn, etc.),
# which live in the document-controls/Toolbox regions, not the menu.
_APP_MENU_HTML_PATH = _REPO_ROOT / "templates" / "_app_menu.html"
_APP_MENU_JS_PATH = _REPO_ROOT / "static" / "js" / "app_menu.js"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


# ---------------------------------------------------------------------------
# Static structure: menu grammar, order, and command-reuse wiring.
# ---------------------------------------------------------------------------

class MenuGrammarTests(unittest.TestCase):
    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_top_level_menu_order(self):
        # Product Owner's own required grammar: Archiosk | File | Edit |
        # View | Document | Tools | Window | Help - "Batch" deliberately
        # omitted (see UI_REFERENCE_MAP.md's own menu.file/.../menu.help
        # row and the completion report's "Inventive improvements"
        # section: no genuine multi-document action exists on an
        # already-registered project today).
        expected = ["menu.archiosk", "menu.file", "menu.edit", "menu.view",
                    "menu.document", "menu.tools", "menu.window", "menu.help"]
        bar_start = self.html.index('data-ui-ref="menu.bar"')
        bar_end = self.html.index("</nav>", bar_start)
        bar_html = self.html[bar_start:bar_end]
        positions = [(bar_html.index(f'data-ui-ref="{ref}"'), ref) for ref in expected]
        self.assertEqual([ref for _pos, ref in sorted(positions)], expected)
        self.assertNotIn('data-ui-ref="menu.batch"', bar_html)

    def test_archiosk_summary_styled_identically_to_its_neighbors(self):
        # Product Owner, explicit: "not a separate logo" - the Archiosk
        # entry is a plain menu item, same class as File/Edit/View/...
        for ref in ("menu.archiosk", "menu.file", "menu.edit", "menu.view",
                    "menu.document", "menu.tools", "menu.window", "menu.help"):
            idx = self.html.index(f'data-ui-ref="{ref}"')
            summary = re.search(r'<summary class="([^"]+)">', self.html[idx:idx + 200])
            self.assertIsNotNone(summary, ref)
            self.assertEqual(summary.group(1), "workspace-topbar-btn", ref)

    def test_menu_bar_renders_before_any_workspace_gated_content(self):
        # The bar itself must be reachable outside any {% if project_id
        # is defined and workspace is defined %} gate - every
        # authenticated page, project-less or not.
        bar_idx = self.html.index('data-ui-ref="menu.bar"')
        first_project_gate_idx = self.html.index("{% if project_id is defined and workspace is defined %}")
        self.assertLess(bar_idx, first_project_gate_idx)


class CommandReuseTests(unittest.TestCase):
    """Section 15's own no-command-duplication requirement: every
    data-reuse-control target must be a real control id that actually
    exists in base.html (the data-reuse-control attributes themselves
    live in the shared _app_menu.html partial; their real targets - the
    document-controls toolbar, Toolbox's Compare button - stay in
    base.html, unmoved by the CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01
    extraction)."""

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_every_reuse_control_target_id_exists_in_the_template(self):
        targets = set(re.findall(r'data-reuse-control="([a-z0-9\-]+)"', self.html))
        self.assertTrue(targets, "expected at least one data-reuse-control target")
        ids_in_template = set(re.findall(r' id="([a-z0-9\-]+)"', self.base_html))
        missing = targets - ids_in_template
        self.assertEqual(missing, set(), f"data-reuse-control targets with no matching id in base.html: {missing}")

    def test_known_reuse_targets_are_the_expected_pre_existing_controls(self):
        targets = set(re.findall(r'data-reuse-control="([a-z0-9\-]+)"', self.html))
        expected = {
            "doc-print", "doc-annotate-undo", "doc-annotate-redo", "doc-annotate-delete",
            "doc-zoom-in", "doc-zoom-out", "doc-fit-width", "doc-fit-page",
            "doc-annotate-text", "doc-annotate-highlight", "doc-annotate-ink",
            "doc-annotate-select", "doc-region-select", "toolbox-compare-btn",
            # CLAUDE-DOCUMENT-MENU-01: Document > Rotate Clockwise reuses the
            # viewer's own rotate button (templates/base.html, id="doc-rotate")
            # rather than reimplementing rotation. It satisfies this test's own
            # requirement - a PRE-EXISTING control - and the set stays exact, so
            # an unknown target still fails here.
            "doc-rotate",
            # CLAUDE-WINDOW-MENU-01: Window > Panels > Thumbnails reuses the
            # Lists column's own maximize button (templates/base.html,
            # id="thumbnails-maximize-btn") rather than a second implementation.
            # A real pre-existing control, which is what this test requires.
            "thumbnails-maximize-btn",
        }
        self.assertEqual(targets, expected)

    def test_data_action_names_are_all_implemented_in_app_menu_js(self):
        html_actions = set(re.findall(r'data-action="([a-z\-]+)"', self.html))
        js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")
        implemented = set(re.findall(r"^\s*'([a-z\-]+)': function", js, re.MULTILINE))
        missing = html_actions - implemented
        self.assertEqual(missing, set(), f"data-action names with no handler in app_menu.js: {missing}")


class KeyboardShortcutsPanelTests(unittest.TestCase):
    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_panel_lists_only_shortcuts_that_are_genuinely_wired(self):
        idx = self.html.index('id="app-menu-keyboard-shortcuts"')
        panel = self.html[idx:self.html.index("</div>", idx)]
        self.assertIn("Escape", panel)
        self.assertIn("first / last open Document tab", panel)
        self.assertNotIn("Ctrl", panel)
        self.assertNotIn("Cmd", panel)

    def test_panel_hidden_by_default(self):
        idx = self.html.index('id="app-menu-keyboard-shortcuts"')
        tag = self.html[idx:self.html.index(">", idx)]
        self.assertIn("hidden", tag)


# ---------------------------------------------------------------------------
# app_menu.js: Escape/outside-click/one-at-a-time behavior, state sync.
# ---------------------------------------------------------------------------

class MenuJsBehaviorTests(unittest.TestCase):
    def setUp(self):
        self.js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")

    def test_scoped_to_workspace_topbar_only(self):
        self.assertIn("document.querySelector('.workspace-topbar')", self.js)

    def test_escape_closes_the_deepest_open_menu_not_everything_at_once(self):
        idx = self.js.index("e.key !== 'Escape'")
        body = self.js[idx:idx + 700]
        self.assertIn("deepest", body)

    def test_opening_one_menu_closes_siblings_not_ancestors(self):
        self.assertIn("function closeOthers(current)", self.js)
        idx = self.js.index("function closeOthers(current)")
        body = self.js[idx:idx + 300]
        self.assertIn("d.contains(current) || current.contains(d)", body)

    def test_outside_click_closes_open_menus(self):
        idx = self.js.index("document.addEventListener('click'")
        body = self.js[idx:idx + 200]
        self.assertIn("!d.contains(e.target)", body)

    def test_sync_menu_state_mirrors_real_control_disabled_state(self):
        idx = self.js.index("function syncMenuState()")
        body = self.js[idx:self.js.index("\n    }\n", idx)]
        self.assertIn("real.disabled", body)
        self.assertIn("item.disabled = !available", body)

    def test_disabled_items_never_get_a_second_independent_flag(self):
        # The one enabled/disabled source of truth is the real control's
        # own .disabled - syncMenuState re-derives it every open, never
        # stores a separate boolean that could drift.
        idx = self.js.index("function syncMenuState()")
        body = self.js[idx:self.js.index("\n    }\n", idx)]
        self.assertNotIn("localStorage", body)

    def test_exit_guarded_by_unsaved_input_check_not_unconditional(self):
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 4: the
        # guard is now guardDeparture(), one canonical mechanism reused
        # by every justified departure link (menu.archiosk.exit,
        # menu.account.sign-out, gateway.account.sign-out) - not a
        # single inline handler on exitLink alone any more.
        self.assertIn("function hasUnsavedInput()", self.js)
        idx = self.js.index("function guardDeparture(link)")
        body = self.js[idx:idx + 400]
        self.assertIn("hasUnsavedInput()", body)
        self.assertIn("window.confirm(", body)
        self.assertIn("guardDeparture(byRef('menu.archiosk.exit'))", self.js)
        self.assertIn("guardDeparture(byRef('menu.account.sign-out'))", self.js)


class MenubarCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_menubar_positioning_rules_exist(self):
        self.assertIn(".workspace-menubar {", self.css)
        self.assertIn(".workspace-menubar-panel {", self.css)
        self.assertIn(".workspace-menubar-subpanel {", self.css)

    def test_disabled_items_get_visibly_different_styling(self):
        idx = self.css.index(".workspace-menubar-item:disabled")
        body = self.css[idx:idx + 400]
        self.assertIn("--text-disabled", body)

    def test_relocated_appearance_and_layout_keep_their_original_classes(self):
        # A prior bug in this same pass: dropping workspace-appearance-menu/
        # workspace-layout-menu in favor of only the new submenu class
        # would have broken position:relative for those panels and the
        # test_p40e3a_qa_reconciliation.py / test_p40vw6_theme_correction.py
        # verbatim 3-selector CSS string. Guard both directions here.
        self.assertIn(".workspace-layout-options,\n.workspace-appearance-options,\n.workspace-user-options {", self.css)


class IdentityMarkAndActivityIndicatorTests(unittest.TestCase):
    """CLAUDE-ARCHIOSK-IDENTITY-ACTIVITY-INDICATOR-01 - originally a
    stationary identity mark PLUS a three-dot working indicator, both
    structurally distinct from the Archiosk menu item itself (Section 1:
    neither may substitute for the other).

    CLAUDE-LETTERMARK-PURGE-01 retired the mark half on 2026-08-30: at the
    16px it rendered at here it read as a bowtie beside the word "Archiosk"
    it sat next to. The activity indicator is untouched and every assertion
    about it below is unchanged - Section 1's separation still holds, with
    one of the two things it separated now absent rather than merged.
    """

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")

    def test_the_retired_mark_has_not_returned(self):
        # CLAUDE-LETTERMARK-PURGE-01. Four tests stood here asserting the
        # mark's macro, its position before the nav, its decorative-only
        # semantics and its separation from the indicator. They are replaced
        # by one guard rather than deleted silently: the risk now is not that
        # the mark is wrong, it is that a future session reintroduces it.
        self.assertNotIn("workspace-app-mark", self.html)
        self.assertNotIn("archiosk_mark", self.html)
        self.assertNotIn(".workspace-app-mark", self.css)

    def test_activity_indicator_still_sits_before_the_nav(self):
        # Was asserted relative to the mark; now asserted on its own terms.
        # The indicator's placement was never a consequence of the mark's.
        activity_idx = self.html.index('id="workspace-app-activity"')
        self.assertLess(activity_idx, self.html.index('class="workspace-menubar"'))
        self.assertLess(activity_idx, self.html.index('data-ui-ref="menu.archiosk"'))

    def test_activity_indicator_hidden_by_default_with_three_dots(self):
        idx = self.html.index('id="workspace-app-activity"')
        tag = self.html[idx - 30:idx + 200]
        self.assertIn("hidden", tag)
        block_end = self.html.index("</span>", idx)
        block = self.html[idx:block_end]
        self.assertEqual(block.count('class="workspace-app-activity-dot"'), 3)

    def test_activity_indicator_has_truthful_idle_tooltip_and_no_click_handler(self):
        idx = self.html.index('id="workspace-app-activity"')
        tag = self.html[idx - 30:idx + 250]
        self.assertIn('title="GO idle"', tag)
        self.assertIn('aria-label="GO idle"', tag)
        self.assertNotIn("<button", tag)
        self.assertNotIn("<a ", tag)
        self.assertNotIn("onclick", tag)

    def test_css_uses_machine_blue_not_a_new_semantic_color(self):
        idx = self.css.index(".workspace-app-activity-dot {")
        body = self.css[idx:idx + 300]
        self.assertIn("var(--machine-blue)", body)

    def test_animation_respects_reduced_motion(self):
        idx = self.css.index("@keyframes workspace-app-activity-fall")
        after = self.css[idx:idx + 1200]
        self.assertIn("prefers-reduced-motion", after)
        self.assertIn("animation: none", after)

    def test_animation_reads_top_to_middle_to_bottom(self):
        idx = self.css.index(".workspace-app-activity.working .workspace-app-activity-dot:nth-child(2)")
        body = self.css[idx:idx + 400]
        self.assertIn("animation-delay: 0.3s", body)
        idx3 = self.css.index(".workspace-app-activity.working .workspace-app-activity-dot:nth-child(3)")
        body3 = self.css[idx3:idx3 + 400]
        self.assertIn("animation-delay: 0.6s", body3)

    def test_js_activation_reuses_the_existing_composer_execution_signal(self):
        # The SAME handler that already sets dock-composer-execution-status
        # also drives the indicator - never a second "GO is working"
        # mechanism, never a client-side timer.
        js = (_REPO_ROOT / "static" / "js" / "case_workspace.js").read_text(encoding="utf-8")
        idx = js.index("const executionStatus = document.getElementById('dock-composer-execution-status')")
        block = js[idx:idx + 1200]
        self.assertIn("getElementById('workspace-app-activity')", block)
        self.assertIn("appActivity.hidden = false", block)
        self.assertIn("classList.add('working')", block)
        self.assertNotIn("setInterval", block)
        self.assertNotIn("setTimeout", block)


# ---------------------------------------------------------------------------
# Live rendering: authorization-aware presence/absence via the real app.
# ---------------------------------------------------------------------------

class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_app_menu_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="menu_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="menu_reviewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner, project_name, operating_environment=CLIENT_OWNER, filename="rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"content"), filename=filename), self.flask_app,
                    operating_environment=operating_environment, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)


class MenuRendersEverywhereTests(_BaseTestCase):
    def test_menu_bar_renders_on_a_project_less_page(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        for ref in ("menu.bar", "menu.archiosk", "menu.file", "menu.edit",
                    "menu.view", "menu.document", "menu.tools", "menu.window", "menu.help"):
            self.assertIn(f'data-ui-ref="{ref}"', body, ref)

    def test_appearance_renders_on_a_project_less_page_display_layout_does_not(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.appearance"', body)
        self.assertNotIn('data-ui-ref="menu.display-layout"', body)

    def test_activity_indicator_renders_on_every_authenticated_page(self):
        # CLAUDE-LETTERMARK-PURGE-01: was "identity mark AND activity
        # indicator". The mark is retired, so this asserts the half that
        # survives - and that the retired half really is gone from a rendered
        # page, not merely from the template source.
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('class="workspace-app-mark"', body)
        self.assertIn('id="workspace-app-activity"', body)
        idx = body.index('id="workspace-app-activity"')
        self.assertIn("hidden", body[idx - 20:idx + 200])

    def test_menu_bar_renders_inside_an_open_project_too(self):
        doc = self._ingest(owner="menu_owner", project_name="North Bayview Menu Test")
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.bar"', body)
        self.assertIn('data-ui-ref="menu.display-layout"', body)


class AboutRouteTests(_BaseTestCase):
    def test_about_route_returns_real_static_facts(self):
        client = self._client_as("menu_owner", 1)
        resp = client.get("/about")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Flat-JSON registry", body)

    def test_about_link_in_menu_points_at_the_real_route(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.archiosk.about"')
        tag = body[idx:idx + 60]
        self.assertIn('href="/about"', tag)


class AdminMenuTests(_BaseTestCase):
    def test_admin_submenu_present_for_admin(self):
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.archiosk.admin"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.new-project"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.security"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.operations"', body)
        self.assertIn('data-ui-ref="menu.archiosk.admin.project-data-management"', body)

    def test_admin_submenu_absent_for_non_admin(self):
        client = self._client_as("menu_reviewer", 2, role="read_only")
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.archiosk.admin"', body)


class PublishMenuCommandTests(_BaseTestCase):
    """Section 12/16: Publish RFP only ever appears for an Owner project
    still in PRE_PUBLICATION - never a second publication implementation,
    never surfaced in a Proponent workspace or a published Owner one."""

    def test_publish_absent_without_an_open_project(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.file.publish-rfp"', body)

    def test_publish_present_for_owner_pre_publication_project(self):
        doc = self._ingest(owner="menu_owner", project_name="Owner Pre-Pub Menu Test", operating_environment=CLIENT_OWNER)
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.publish-rfp"', body)

    def test_publish_absent_for_proponent_project(self):
        doc = self._ingest(owner="menu_owner", project_name="Proponent Menu Test", operating_environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.file.publish-rfp"', body)

    def test_publish_absent_once_owner_project_is_published(self):
        doc = self._ingest(owner="menu_owner", project_name="Owner Published Menu Test", operating_environment=CLIENT_OWNER)
        store = self._store()
        workspace = store.get(doc.project_id)
        source_id = workspace.sources[0]["id"]
        store.publish_procurement_package(workspace, [source_id], source_id, actor="menu_owner")
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.file.publish-rfp"', body)

    def test_publish_absent_for_non_admin_actor_on_an_otherwise_eligible_project(self):
        # CLAUDE-FILE-PUBLISH-RFP-01: a real non-admin (read_only) actor on
        # a project that IS an eligible Owner pre-publication project (the
        # only other gate this command checks) must not see an
        # enabled-looking command that dead-ends on click - the Toolbox
        # panel it scrolls to is itself is_admin-gated and won't exist in
        # this actor's DOM at all. Reuses the same menu_reviewer/read_only
        # actor this file's own _BaseTestCase.setUp already creates.
        doc = self._ingest(owner="menu_owner", project_name="Owner Pre-Pub Non-Admin Menu Test", operating_environment=CLIENT_OWNER)
        client = self._client_as("menu_reviewer", 2, role="read_only")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.file.publish-rfp"', body)


class DocumentAndExportMenuTests(_BaseTestCase):
    def test_document_menu_shows_placeholder_with_no_selection(self):
        doc = self._ingest(owner="menu_owner", project_name="Doc Menu Placeholder Test")
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.document.none"', body)
        self.assertNotIn('data-ui-ref="menu.document.context"', body)

    def test_document_menu_shows_context_command_with_a_selection(self):
        doc = self._ingest(owner="menu_owner", project_name="Doc Menu Selected Test")
        store = self._store()
        source_id = store.get(doc.project_id).sources[0]["id"]
        client = self._client_as("menu_owner", 1)
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.document.context"', body)
        self.assertNotIn('data-ui-ref="menu.document.none"', body)

    def test_export_placeholder_without_a_project_real_export_within_one(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.export.none"', body)
        self.assertNotIn('data-ui-ref="menu.file.export.rfi"', body)

        doc = self._ingest(owner="menu_owner", project_name="Export Menu Test")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.export.rfi"', body)
        self.assertNotIn('data-ui-ref="menu.file.export.none"', body)


class FileMenuNewOpenProjectTests(_BaseTestCase):
    """CLAUDE-FILE-MENU-CANONICAL-COMMANDS-01: File > New Project / Open
    Project must reuse the exact same routes every other entry point
    into these actions already uses - never a second implementation -
    and must be truthfully permission-aware."""

    def test_new_project_present_and_targets_upload_for_admin(self):
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.file.new-project"')
        tag = body[idx - 10:idx + 80]
        self.assertIn('href="/upload"', tag)
        self.assertNotIn('data-ui-ref="menu.file.new-project.none"', body)

    def test_new_project_disabled_for_non_admin(self):
        client = self._client_as("menu_reviewer", 2, role="read_only")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.new-project.none"', body)
        self.assertNotIn('data-ui-ref="menu.file.new-project"', body)

    def test_open_project_is_a_direct_chooser_not_a_link_to_the_full_vestibule(self):
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum G: the
        # ref itself is now a <details> submenu, not a plain <a href> to
        # portal.choose_project - project_chooser.html/choose_project()
        # are unchanged and stay reachable elsewhere (menu.context.
        # switch-project), just no longer what File > Open Project opens.
        doc = self._ingest(owner="menu_owner", project_name="Open Project Direct Test")
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        idx = body.index('data-ui-ref="menu.file.open-project"')
        tag = body[idx - 70:idx + 60]
        self.assertIn("<details", tag)
        self.assertNotIn("/projects/choose", body[idx:idx + 400])
        self.assertIn('data-ui-ref="menu.file.open-project.item"', body)
        self.assertIn(f'href="/projects/{doc.project_id}/workspace"', body)

    def test_open_project_rows_open_immediately_no_radio_or_second_button(self):
        self._ingest(owner="menu_owner", project_name="Open Project No Radio Test")
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        panel_idx = body.index('data-ui-ref="menu.file.open-project"')
        panel = body[panel_idx:body.index("</details>", panel_idx)]
        self.assertNotIn('type="radio"', panel)
        self.assertNotIn("Open Project</button>", panel)

    def test_open_project_scoped_to_current_projects_environment_when_one_is_open(self):
        owner_doc = self._ingest(owner="menu_owner", project_name="Owner Scope Test", operating_environment=CLIENT_OWNER)
        proponent_doc = self._ingest(owner="menu_owner", project_name="Proponent Scope Test", operating_environment=DESIGN_BUILDER_PROPONENT)
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get(f"/projects/{owner_doc.project_id}/workspace").get_data(as_text=True)
        panel_idx = body.index('data-ui-ref="menu.file.open-project"')
        panel = body[panel_idx:body.index("</details>", panel_idx)]
        self.assertIn(f'href="/projects/{owner_doc.project_id}/workspace"', panel)
        self.assertNotIn(f'href="/projects/{proponent_doc.project_id}/workspace"', panel)

    def test_open_project_empty_state_is_truthful_and_offers_new_project_to_admin(self):
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.open-project.empty"', body)
        self.assertIn('data-ui-ref="menu.file.open-project.new-project"', body)

    def test_open_project_empty_state_offers_no_new_project_link_to_non_admin(self):
        client = self._client_as("menu_reviewer", 2, role="read_only")
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.file.open-project.empty"', body)
        self.assertNotIn('data-ui-ref="menu.file.open-project.new-project"', body)

    def test_new_project_and_open_project_never_duplicate_a_second_implementation(self):
        # Same routes as the pre-existing Archiosk > Admin > New Project
        # and the breadcrumb's own Switch Project link - never a
        # second, parallel project-creation/project-open code path.
        client = self._client_as("menu_owner", 1, role="admin")
        body = client.get("/projects").get_data(as_text=True)
        new_project_idx = body.index('data-ui-ref="menu.file.new-project"')
        admin_new_project_idx = body.index('data-ui-ref="menu.archiosk.admin.new-project"')
        self.assertIn('href="/upload"', body[new_project_idx - 10:new_project_idx + 80])
        self.assertIn('href="/upload"', body[admin_new_project_idx - 10:admin_new_project_idx + 80])

    def test_open_project_search_hidden_below_six_choices_present_above(self):
        client = self._client_as("menu_owner", 1, role="admin")
        for i in range(5):
            self._ingest(owner="menu_owner", project_name=f"Search Threshold {i}")
        body = client.get("/projects").get_data(as_text=True)
        panel_idx = body.index('data-ui-ref="menu.file.open-project"')
        panel = body[panel_idx:body.index("</details>", panel_idx)]
        self.assertIn('data-ui-ref="menu.file.open-project.search"', panel)
        search_idx = panel.index('data-ui-ref="menu.file.open-project.search"')
        search_tag = panel[search_idx:panel.index(">", search_idx)]
        self.assertIn("hidden", search_tag)

        self._ingest(owner="menu_owner", project_name="Search Threshold 6")
        body = client.get("/projects").get_data(as_text=True)
        panel_idx = body.index('data-ui-ref="menu.file.open-project"')
        panel = body[panel_idx:body.index("</details>", panel_idx)]
        search_idx = panel.index('data-ui-ref="menu.file.open-project.search"')
        search_tag = panel[search_idx:panel.index(">", search_idx)]
        self.assertNotIn("hidden", search_tag)


class OpenProjectMenuFilterJsTests(unittest.TestCase):
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum G: the
    search input filters the already-rendered, already-authorized rows
    client-side only - never a second fetch/authorization check."""

    def setUp(self):
        self.js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")

    def test_filter_reads_the_search_input_and_hides_non_matching_rows(self):
        self.assertIn("workspace-open-project-search", self.js)
        idx = self.js.index("workspace-open-project-search")
        body = self.js[idx:idx + 700]
        self.assertIn("workspace-open-project-item", body)
        self.assertIn("addEventListener('input'", body)
        self.assertIn(".hidden = !visible", body)

    def test_filter_never_removes_rows_from_the_dom(self):
        idx = self.js.index("workspace-open-project-search")
        body = self.js[idx:idx + 700]
        self.assertNotIn("removeChild", body)
        self.assertNotIn(".remove()", body)


class MenuDeboxedFrameTests(unittest.TestCase):
    """CLAUDE-MENU-DEBOXING-01: the top-menu triggers no longer sit
    inside a permanently-visible box - the border is reserved (same
    1px, transparent) so hover/focus/open never shift layout, and
    becomes genuinely visible only on a real state (hover, keyboard
    focus, or a truthfully-tracked open menu)."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")

    def test_border_is_transparent_at_rest_not_absent(self):
        idx = self.css.index(".workspace-topbar-btn {")
        body = self.css[idx:self.css.index("}", idx)]
        self.assertIn("border: 1px solid transparent;", body)

    def test_hover_and_expanded_state_still_reveal_a_real_border(self):
        idx = self.css.index(".workspace-topbar-btn:hover,")
        body = self.css[idx:self.css.index("}", idx)]
        self.assertIn('[aria-expanded="true"]', body)
        self.assertIn("border-color: var(--border-strong);", body)

    def test_focus_visible_also_reveals_the_border(self):
        idx = self.css.index(".workspace-topbar-btn:focus-visible")
        body = self.css[idx:self.css.index("}", idx)]
        self.assertIn("border-color: var(--border-strong);", body)

    def test_aria_expanded_is_now_genuinely_synced_not_dead_css(self):
        # Before this stage, [aria-expanded="true"] matched nothing -
        # native <details>/<summary> never sets it, and nothing in this
        # codebase's JS did either for the menu bar specifically.
        idx = self.js.index("topbar.addEventListener('toggle'")
        body = self.js[idx:idx + 1000]
        self.assertIn("querySelector(':scope > summary')", body)
        self.assertIn("setAttribute('aria-expanded', String(target.open))", body)


class DeveloperModeTests(_BaseTestCase):
    """CLAUDE-DEVELOPER-MODE-COCKPIT-01, Addendum E: orientation-only
    Developer Mode - a real, session-based, admin_required-gated toggle,
    never a client-only/localStorage mechanism a non-admin could spoof."""

    def _toggle(self, client):
        return client.post("/developer-mode/toggle")

    def test_menu_item_absent_for_non_admin(self):
        doc = self._ingest(owner="menu_owner", project_name="Dev Mode Non-Admin Menu Test")
        client = self._client_as("menu_reviewer", 2, role="read_only")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        # CLAUDE-DEVELOPER-MENU-01: the toggle moved from the Admin submenu to
        # its own "Developer Mode" submenu, and the ref moved with it. Updated
        # rather than left pointing at the old value - an absence assertion
        # against a ref that no longer exists anywhere passes for the wrong
        # reason and would stop protecting non-admins entirely.
        self.assertNotIn('data-ui-ref="menu.archiosk.developer.mode-toggle"', body)
        self.assertNotIn('data-ui-ref="menu.archiosk.developer"', body)

    def test_toggle_route_rejects_non_admin(self):
        client = self._client_as("menu_reviewer", 2, role="read_only")
        resp = self._toggle(client)
        self.assertEqual(resp.status_code, 403)

    def test_toggle_route_requires_login(self):
        client = self.flask_app.test_client()
        resp = self._toggle(client)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_off_by_default_for_admin(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn("Enter Developer Mode", body)
        self.assertNotIn("Exit Developer Mode", body)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)

    def test_admin_can_toggle_on_and_badge_appears_everywhere(self):
        client = self._client_as("menu_owner", 1)
        resp = self._toggle(client)
        self.assertEqual(resp.status_code, 302)

        # Project-less page.
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertIn('role="status"', body)
        self.assertIn(">DEVELOPER MODE<", body)
        self.assertIn("Exit Developer Mode", body)
        self.assertNotIn("Enter Developer Mode", body)

        # A real open Project - still visible, and does not sit inside
        # the project-context breadcrumb (no project authority implied).
        doc = self._ingest(owner="menu_owner", project_name="Dev Mode Badge Project Test")
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertIn(">DEVELOPER MODE<", body)

    def test_toggle_off_again_removes_the_badge(self):
        client = self._client_as("menu_owner", 1)
        self._toggle(client)
        self._toggle(client)
        body = client.get("/projects").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertIn("Enter Developer Mode", body)

    def test_badge_absent_on_standalone_auth_pages_even_when_on(self):
        client = self._client_as("menu_owner", 1)
        self._toggle(client)
        # /login renders auth_shell.html, not the workspace menu bar at
        # all - same standalone-auth-page guard is_admin itself already
        # gets in app.py's inject_globals.
        body = client.get("/login").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)

    def test_does_not_grant_or_imply_any_project_authority(self):
        # A read_only user's own session can never carry developer_mode
        # at all (the toggle route already rejects them) - this test
        # proves the converse too: an admin's own developer_mode=True
        # never changes what a DIFFERENT, non-admin session can do or
        # see on a real project.
        doc = self._ingest(owner="menu_owner", project_name="Dev Mode Authority Test", operating_environment=CLIENT_OWNER)
        admin_client = self._client_as("menu_owner", 1)
        self._toggle(admin_client)

        reviewer_client = self._client_as("menu_reviewer", 2, role="read_only")
        body = reviewer_client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="menu.developer-mode-badge"', body)
        self.assertNotIn('data-ui-ref="menu.file.publish-rfp"', body)



class AllProjectsMenuEntryTests(_BaseTestCase):
    """CLAUDE-MENU-ALL-PROJECTS-01 - the directory had no menu entry at all.

    Before this, `portal.projects_list` was reachable only from the landing
    page's own `index.projects-directory` link and from a "← Projects" link
    inside an already-open workspace. A reviewer who had navigated away from `/`
    with no project open had to edit the URL. That was found while investigating
    a proposal to REMOVE the landing-page link as redundant - it was not
    redundant, it was the only one.
    """

    def _menu_body(self, role):
        username = "menu_owner" if role == "admin" else "menu_reviewer"
        user_id = 1 if role == "admin" else 2
        client = self._client_as(username, user_id, role=role)
        return client.get("/projects").get_data(as_text=True)

    def test_the_file_menu_offers_all_projects(self):
        body = self._menu_body("admin")
        self.assertIn('data-ui-ref="menu.file.all-projects"', body)

    def test_it_points_at_the_projects_directory(self):
        """Asserted against the anchor TAG. `/projects` appears elsewhere in the
        document, so a bare substring check over the body would pass even if
        this control pointed somewhere else."""
        body = self._menu_body("admin")
        tag = re.search(r'<a[^>]*data-ui-ref="menu\.file\.all-projects"[^>]*>', body)
        self.assertIsNotNone(tag, "the All Projects entry did not render")
        self.assertIn('href="/projects"', tag.group(0))

    def test_it_is_NOT_admin_gated(self):
        """Deliberately unlike `menu.file.new-project` beside it.

        portal.projects_list is @login_required and already access-filtered per
        reviewer, so a read_only user reaching their own projects here is shown
        nothing the directory would not show them anyway. Gating it would remove
        a reviewer's only menu route to their own project list.
        """
        body = self._menu_body("read_only")
        self.assertIn('data-ui-ref="menu.file.all-projects"', body)

    def test_new_project_beside_it_REMAINS_admin_gated(self):
        # The two live together; this guards against a future edit widening the
        # wrong one by copying its neighbour.
        body = self._menu_body("read_only")
        self.assertNotIn('data-ui-ref="menu.file.new-project"', body)

    def test_it_sits_above_the_separator_with_open_project(self):
        """Grouping is the point, not decoration: All Projects and Open Project
        both answer "which project am I working on", while everything past the
        rule acts on the Document already open."""
        body = self._menu_body("admin")
        all_projects = body.index('data-ui-ref="menu.file.all-projects"')
        add_document = body.index('data-ui-ref="menu.file.add-document')
        self.assertLess(all_projects, add_document)



class HomeLabelTests(unittest.TestCase):
    """CLAUDE-MENU-HOME-LABEL-01 - visible text shortened, accessible name kept."""

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def _home_tag(self):
        idx = self.html.index('data-ui-ref="menu.archiosk.home"')
        return self.html[self.html.rindex("<a", 0, idx):self.html.index("</a>", idx) + 4]

    def test_the_visible_label_is_just_home(self):
        # Inside a menu already titled "Archiosk", "Archiosk Home" said the word
        # twice.
        tag = self._home_tag()
        self.assertTrue(tag.endswith(">Home</a>"), tag)

    def test_the_accessible_name_deliberately_stays_archiosk_home(self):
        """NOT an oversight, and not to be "tidied" to match the visible text.

        CLAUDE-P40-BRAND1 records why: the mark is aria-hidden, so without this
        the computed name would be bare "Home" with no indication of which home.
        WCAG 2.5.3 (Label in Name) is satisfied because the accessible name
        still CONTAINS the visible label. Shortening it would trade an
        accessibility property for a symmetry nobody experiences.
        """
        self.assertIn('aria-label="Archiosk Home"', self._home_tag())

    def test_it_still_routes_to_the_landing_page(self):
        self.assertIn("url_for('portal.index')", self._home_tag())


class DocumentMenuTests(unittest.TestCase):
    """CLAUDE-DOCUMENT-MENU-01.

    Asserted against the template SOURCE rather than a rendered page, following
    test_p40brand1_brand_mark.py: the active-document branch needs a selected
    Source, and what these guard is the markup contract, not the selection
    machinery that puts a document there.
    """

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_the_empty_state_names_the_action_not_only_the_state(self):
        idx = self.html.index('data-ui-ref="menu.document.none"')
        tag = self.html[self.html.rindex("<span", 0, idx):self.html.index("</span>", idx)]
        self.assertIn("Document Properties", tag)
        self.assertIn("No document active", tag)

    def test_the_old_no_document_selected_wording_is_gone(self):
        # Scoped to the ELEMENT. The phrase survives in a Jinja comment that
        # records what the label used to say, and Jinja strips comments from
        # rendered output - so a whole-file assertion would fail on the
        # explanation rather than on the thing being explained.
        idx = self.html.index('data-ui-ref="menu.document.none"')
        tag = self.html[self.html.rindex("<span", 0, idx):self.html.index("</span>", idx)]
        self.assertNotIn("No document selected", tag)

    def test_rotate_clockwise_REUSES_the_viewer_control(self):
        """It must click #doc-rotate, never reimplement rotation.

        A second implementation would be a second source of truth for
        currentRotation, and the view-state persistence (saveViewStateSoon)
        hangs off the real control.
        """
        idx = self.html.index('data-ui-ref="menu.document.rotate-cw"')
        tag = self.html[self.html.rindex("<button", 0, idx):self.html.index("</button>", idx)]
        self.assertIn('data-reuse-control="doc-rotate"', tag)
        self.assertIn("Rotate Clockwise", tag)

    def test_there_is_no_counter_clockwise_entry_claiming_to_work(self):
        # pdf_viewer.js's rotate() is `currentRotation + 90` only, and
        # updateOrientationStatus() hardcodes "clockwise". An entry here would
        # be a control with nothing behind it.
        self.assertNotIn("Rotate Counterclockwise", self.html)
        self.assertNotIn("Rotate Counter-Clockwise", self.html)

    def test_document_properties_is_DISABLED_because_the_modal_does_not_exist(self):
        """The load-bearing one.

        An enabled item wired to nothing is worse than no item: a control that
        does nothing when clicked teaches the reviewer the menu is unreliable,
        and they cannot distinguish that from a control that is merely slow.
        This must stay disabled until the modal is actually built.
        """
        idx = self.html.index('data-ui-ref="menu.document.properties-disabled"')
        tag = self.html[self.html.rindex("<span", 0, idx):self.html.index("</span>", idx)]
        self.assertIn('aria-disabled="true"', tag)
        self.assertIn("workspace-menubar-item-disabled", tag)
        self.assertIn("not yet available", tag)

    def test_the_properties_item_is_a_span_not_an_actionable_control(self):
        # A <button>/<a> would be focusable and clickable even while styled
        # disabled; a <span aria-disabled> cannot be activated at all.
        idx = self.html.index('data-ui-ref="menu.document.properties-disabled"')
        opening = self.html.rindex("<", 0, idx)
        self.assertTrue(self.html[opening:opening + 5] == "<span",
                        self.html[opening:opening + 40])



class ToolsMenuStubTests(unittest.TestCase):
    """CLAUDE-TOOLS-MENU-STUBS-01 - six signposted tools, none of them built.

    The value of these tests is not that the items exist; it is that they stay
    DISABLED until the engines behind them do. An enabled measurement tool is
    the dangerous case: a takeoff on an uncalibrated sheet would return a
    number, and a number on a drawing is read as a dimension.
    """

    STUBS = ("calibrate-scale", "linear-takeoff", "area-takeoff",
             "sheet-diff", "extract-sheet-index", "export-redlines")

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def _tag(self, ref):
        idx = self.html.index('data-ui-ref="menu.tools.%s"' % ref)
        return self.html[self.html.rindex("<", 0, idx):self.html.index("</span>", idx)]

    def test_every_stub_is_present(self):
        for ref in self.STUBS:
            with self.subTest(ref=ref):
                self.assertIn('data-ui-ref="menu.tools.%s"' % ref, self.html)

    def test_every_stub_is_disabled_and_says_so(self):
        for ref in self.STUBS:
            with self.subTest(ref=ref):
                tag = self._tag(ref)
                self.assertIn('aria-disabled="true"', tag)
                self.assertIn("workspace-menubar-item-disabled", tag)
                self.assertIn("not yet available", tag)

    def test_every_stub_is_a_span_so_it_cannot_be_activated(self):
        # A <button> or <a> stays focusable and clickable even when styled
        # disabled; a <span aria-disabled> cannot be activated at all.
        for ref in self.STUBS:
            with self.subTest(ref=ref):
                self.assertTrue(self._tag(ref).startswith("<span"), ref)

    def test_no_stub_carries_an_action_or_reuse_hook(self):
        """The load-bearing one.

        data-action and data-reuse-control are what app_menu.js binds to. A stub
        carrying either would fire something, which is precisely what "not yet
        available" promises it will not do.
        """
        for ref in self.STUBS:
            with self.subTest(ref=ref):
                tag = self._tag(ref)
                self.assertNotIn("data-action", tag)
                self.assertNotIn("data-reuse-control", tag)

    def test_the_title_names_the_blocker_rather_than_repeating_the_label(self):
        # Hovering should explain WHY it is unavailable, not restate THAT.
        self.assertIn("No calibration engine yet", self._tag("calibrate-scale"))
        self.assertIn("Requires calibration first", self._tag("linear-takeoff"))
        self.assertIn("no on-demand sheet-index tool", self._tag("extract-sheet-index"))

    def test_the_existing_annotation_tools_are_untouched_and_still_wired(self):
        # The five real tools must keep their reuse hooks - this change adds
        # beside them, it does not restructure them.
        for ref, control in (("annotate-text", "doc-annotate-text"),
                             ("annotate-highlight", "doc-annotate-highlight"),
                             ("annotate-ink", "doc-annotate-ink"),
                             ("annotate-select", "doc-annotate-select"),
                             ("region-select", "doc-region-select")):
            with self.subTest(ref=ref):
                idx = self.html.index('data-ui-ref="menu.tools.%s"' % ref)
                tag = self.html[self.html.rindex("<button", 0, idx):self.html.index("</button>", idx)]
                self.assertIn('data-reuse-control="%s"' % control, tag)

    def test_the_three_groups_are_separated_by_dividers(self):
        start = self.html.index('data-ui-ref="menu.tools"')
        block = self.html[start:self.html.index("</details>", start)]
        self.assertEqual(block.count("workspace-menubar-separator"), 2,
                         "expected exactly two dividers: annotation | measurement | analysis")


if __name__ == "__main__":
    unittest.main()


class MenuShortcutSlotTests(unittest.TestCase):
    """CLAUDE-MENU-SHORTCUT-SLOTS-01 - the slots exist; the hints do not yet.

    The layout is infrastructure for accelerators that are not implemented. The
    test that matters is the SECOND one: it fails the moment somebody renders a
    <kbd> without a keybinding behind it.
    """

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_the_slot_styles_exist(self):
        self.assertIn(".menu-item-icon {", self.css)
        self.assertIn(".menu-shortcut {", self.css)

    def test_no_accelerator_is_rendered_while_none_is_bound(self):
        """The load-bearing assertion.

        There is no Ctrl/Alt keybinding anywhere in static/js - the only
        modifier usage is shiftKey for shift-Enter. A <kbd> in the menu today
        would promise a keystroke that does nothing, which is the same defect as
        an enabled control with no handler, multiplied across every item that
        carries one.

        When shortcuts ARE implemented, this test should be updated to assert
        that every rendered <kbd> corresponds to a real binding - not deleted.
        """
        self.assertNotIn("menu-shortcut", self.html,
                         "a shortcut hint was rendered, but no accelerator is "
                         "bound in static/js - see the class docstring")

    def test_the_layout_is_opt_in_so_existing_items_are_unchanged(self):
        """A global block->flex switch would restyle every menu item in the app
        on reasoning alone; this could not be verified in a browser, so it is
        scoped to items that contain a slot - of which there are currently
        none."""
        self.assertIn(".workspace-menubar-item:has(.menu-item-icon)", self.css)
        self.assertIn(".workspace-menubar-item:has(.menu-shortcut)", self.css)
        # The base rule keeps its original display.
        idx = self.css.index(".workspace-menubar-item {")
        base = self.css[idx:self.css.index("}", idx)]
        self.assertIn("display: block", base)

    def test_the_accelerator_uses_a_label_token_not_the_disabled_token(self):
        # --text-disabled means "this control does not work". An accelerator is
        # a quiet label; using that token would make every shortcut read broken.
        idx = self.css.index(".menu-shortcut {")
        rule = self.css[idx:self.css.index("}", idx)]
        # Strip CSS comments before asserting: the rule's own comment EXPLAINS
        # why --text-disabled is wrong here, so a raw substring check would
        # fail on the explanation rather than on a declaration.
        declarations = re.sub(r"/\*.*?\*/", "", rule, flags=re.S)
        self.assertIn("var(--text-metadata)", declarations)
        self.assertNotIn("--text-disabled", declarations)
