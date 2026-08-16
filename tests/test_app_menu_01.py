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
    """CLAUDE-ARCHIOSK-IDENTITY-ACTIVITY-INDICATOR-01 - stationary identity
    mark + three-dot working indicator, both structurally distinct from
    the Archiosk menu item itself (Section 1: neither may substitute for
    the other)."""

    def setUp(self):
        self.html = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.js = _APP_MENU_JS_PATH.read_text(encoding="utf-8")

    def test_mark_reuses_the_one_existing_archiosk_mark_macro(self):
        # Not a new brand asset - macros.archiosk_mark() verbatim.
        idx = self.html.index('class="workspace-app-mark"')
        tag = self.html[idx - 40:idx + 200]
        self.assertIn("macros.archiosk_mark(", tag)

    def test_mark_sits_before_the_nav_not_inside_any_menu_item(self):
        mark_idx = self.html.index('class="workspace-app-mark"')
        nav_idx = self.html.index('class="workspace-menubar"')
        archiosk_menu_idx = self.html.index('data-ui-ref="menu.archiosk"')
        self.assertLess(mark_idx, nav_idx)
        self.assertLess(mark_idx, archiosk_menu_idx)
        # Not inside any <details>/<summary> - no menu semantics of its own.
        span = self.html[mark_idx - 10:mark_idx + 5]
        self.assertNotIn("<details", span)
        self.assertNotIn("<summary", span)

    def test_mark_is_decorative_not_a_second_tab_stop(self):
        idx = self.html.index('class="workspace-app-mark"')
        tag = self.html[idx - 10:idx + 100]
        self.assertIn('aria-hidden="true"', tag)
        self.assertNotIn("<a ", tag)
        self.assertNotIn("href=", tag)

    def test_activity_indicator_is_a_separate_element_from_the_mark(self):
        mark_idx = self.html.index('class="workspace-app-mark"')
        activity_idx = self.html.index('id="workspace-app-activity"')
        self.assertLess(mark_idx, activity_idx)
        self.assertLess(activity_idx, self.html.index('class="workspace-menubar"'))

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

    def test_identity_mark_and_activity_indicator_render_on_every_authenticated_page(self):
        client = self._client_as("menu_owner", 1)
        body = client.get("/projects").get_data(as_text=True)
        self.assertIn('class="workspace-app-mark"', body)
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


if __name__ == "__main__":
    unittest.main()
