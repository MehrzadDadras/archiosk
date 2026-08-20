"""
CLAUDE-P40-DTAB1 - Preview, Pinned, Colored, Renamed, and Hidden
Document Display Tabs.

A bounded implementation of a tabbed main Display for Documents, letting
a reviewer maintain several Document working surfaces in Display
(similar to named Excel sheets) without repeatedly losing the current
Document and viewing position. Document-only scope (Section 2) - never
Investigations/RFIs/Chats/Tasks/Tags/Toolbox/Eye.

Architecture, grounded in the actual repository (Section 1's own
design-review requirement): this is a full-page-reload app (routes/
workspace.py's show_workspace, no client-side router) - a tab is a real
<a href="?source=<id>">, so activating one is a genuine navigation, not
client-side routing invented for this stage. Stable URLs and browser
Back/Forward keep working exactly as before. Tab metadata (pinned/
hidden/alias/color) is a pure client-side workspace preference -
localStorage (pinned/hidden tabs, survive reload) and sessionStorage
(the one replaceable preview tab), keyed by BOTH username and Project id
so switching accounts or Projects never leaks another workspace's tabs.
Every persisted entry is revalidated on every load against
#workspace-active-sources-data (the SAME authorized JSON island
populateDivision already reads) - no new backend endpoint, no schema
migration, no business-data mutation anywhere.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structure, the same practical
ceiling this repo's prior stages have already established and stated
honestly rather than fabricating a walkthrough.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_DOCUMENT_TABS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_tabs.js"
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(r"(?<![\w-])" + re.escape(selector) + r"(?![\w\-\":])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_dtab1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="dtab1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="dtab1_other", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename, content=b"content", owner="dtab1_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self, username="dtab1_owner", user_id=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class RepositoryGroundingTests(unittest.TestCase):
    """Section 1: no new backend surface, no migration - purely additive
    client-side + template work."""

    def test_no_new_route_or_endpoint_added_for_tabs(self):
        routes_source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertNotIn("document_tabs", routes_source.lower().replace("_", "-").replace("-", "_"))

    def test_no_migration_file_added(self):
        migrations_dir = _REPO_ROOT / "migrations"
        if not migrations_dir.exists():
            return
        # No migration file should mention tabs - this stage is a pure
        # client-side preference, never a schema change.
        for path in migrations_dir.rglob("*.py"):
            self.assertNotIn("document_tab", path.read_text(encoding="utf-8").lower())


class TabStripMarkupTests(_BaseTestCase):
    def test_tab_strip_renders_for_documents_page(self):
        doc = self._ingest("DTAB1 Project 1", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        self.assertIn('id="document-tab-strip"', body)
        self.assertIn('id="document-tab-list"', body)
        self.assertIn('role="tablist"', body)
        self.assertIn('id="document-tabs-overflow"', body)

    def test_tab_strip_hidden_by_default_server_side(self):
        # Populated entirely client-side - server always renders it
        # [hidden], JS reveals it once real tabs exist.
        doc = self._ingest("DTAB1 Project 2", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="document-tab-strip"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn("hidden", tag)

    def test_tab_strip_carries_project_and_selected_source_data(self):
        doc = self._ingest("DTAB1 Project 3", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        idx = body.index('id="document-tab-strip"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn(f'data-project-id="{doc.project_id}"', tag)
        self.assertIn(f'data-selected-source-id="{source["id"]}"', tag)

    def test_tab_strip_absent_outside_an_open_workspace(self):
        client = self._client()
        for url in ("/", "/projects", "/upload"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn('id="document-tab-strip"', body, url)

    def test_tab_strip_suppressed_inside_a_panel(self):
        doc = self._ingest("DTAB1 Panel Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}&panel=1").get_data(as_text=True)
        self.assertNotIn('id="document-tab-strip"', body)

    def test_document_tabs_js_only_loaded_outside_panels(self):
        doc = self._ingest("DTAB1 Script Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        normal_body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        panel_body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}&panel=1").get_data(as_text=True)
        self.assertIn("js/document_tabs.js", normal_body)
        self.assertNotIn("js/document_tabs.js", panel_body)

    def test_pdf_canvas_carries_source_id_for_per_tab_state(self):
        doc = self._ingest("DTAB1 Canvas Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        idx = body.index('id="document-viewer-pdf-canvas"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn(f'data-source-id="{source["id"]}"', tag)


class TabStripCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_tab_list_supports_horizontal_overflow(self):
        body = _rule_body(self.css, ".document-tab-list")
        self.assertIn("overflow-x: auto", body)

    def test_tab_list_uses_themed_scrollbar(self):
        # CLAUDE-PANEL-CALM-02: quiet/transparent by default now, themed
        # only on :hover of the rail itself (a real Product Owner report
        # asked every panel-owned scrollbar/overflow rail to behave this
        # way) - the real theme token this test guards is still there,
        # just on the :hover variant. The WebKit rules also moved into a
        # shared combined block further down the file (with .attention-
        # strip-list, which uses the identical pattern) rather than
        # sitting immediately after this base rule.
        body = _rule_body(self.css, ".document-tab-list")
        self.assertIn("scrollbar-color: transparent transparent", body)
        hover_body = _rule_body(self.css, ".document-tab-list:hover")
        self.assertIn("scrollbar-color:", hover_body)
        self.assertIn("var(--surface-primary)", hover_body)
        self.assertIn("::-webkit-scrollbar", self.css)
        self.assertIn(".document-tab-list::-webkit-scrollbar", self.css)

    def test_active_tab_has_non_color_cue(self):
        # Section 8: "the active tab must also use shape, underline,
        # border, weight, or another non-color cue."
        body = _rule_body(self.css, '.document-tab[aria-selected="true"]')
        self.assertIn("font-weight: 600", body)
        self.assertIn("border-bottom: 2px solid var(--machine-blue)", body)

    def test_preview_tab_distinguished_without_color(self):
        # Section 4: italic label + dashed underline, neither a color.
        empty_body = _rule_body(self.css, ".document-tab.document-tab-preview .document-tab-label")
        self.assertIn("font-style: italic", empty_body)
        dashed_body = _rule_body(self.css, '.document-tab.document-tab-preview[aria-selected="true"]')
        self.assertIn("border-bottom-style: dashed", dashed_body)

    def test_curated_color_accent_is_a_top_stripe_not_full_fill(self):
        # Color is an accent only (Section 8's own "not the sole
        # indication... of state") - a thin top border, not a background
        # fill that would compete with the active/hover states above.
        for color in ("gold", "turquoise", "lapis", "terracotta", "green", "purple"):
            body = _rule_body(self.css, f'.document-tab[data-tab-color="{color}"]')
            self.assertIn(f"var(--tabcolor-{color})", body)
        base_body = _rule_body(self.css, ".document-tab")
        self.assertIn("border-top: 3px solid var(--document-tab-accent, transparent)", base_body)

    def test_no_opacity_used_anywhere_in_tab_strip_rules(self):
        strip_start = self.css.index("/* CLAUDE-P40-DTAB1: the Document tab strip")
        strip_end = self.css.index("CLAUDE-P40-E3A, Section 6: the shared right-click context menu", strip_start)
        section = self.css[strip_start:strip_end]
        self.assertNotIn("opacity", section)

    def test_all_tabs_overflow_control_present_and_themed(self):
        body = _rule_body(self.css, ".document-tabs-overflow-summary")
        self.assertIn("var(--border)", body)
        self.assertIn("var(--text-secondary)", body)


class TabColorTokenTests(unittest.TestCase):
    def setUp(self):
        self.tokens = _TOKENS_CSS_PATH.read_text(encoding="utf-8")

    def test_curated_palette_has_all_seven_theme_variants(self):
        for prefix in ("", "dark-", "tint-", "forest-"):
            for color in ("gold", "turquoise", "lapis", "terracotta", "green", "purple"):
                self.assertIn(f"--{prefix}tabcolor-{color}:", self.tokens, f"{prefix}{color}")

    def test_no_eighth_neutral_color_token_minted(self):
        # "Neutral/Default" means no tab-color styling applied - not an
        # 8th curated hue.
        self.assertNotIn("tabcolor-neutral", self.tokens)
        self.assertNotIn("tabcolor-default", self.tokens)

    def test_contrast_verified_via_the_real_tool_not_eyeballed(self):
        import subprocess
        import sys
        result = subprocess.run(
            [sys.executable, str(_REPO_ROOT / "tools" / "check_contrast.py")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ALL PAIRINGS PASS", result.stdout)
        self.assertIn("tab color:", result.stdout)


class DocumentTabsJsCoreTests(unittest.TestCase):
    def setUp(self):
        self.js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        # Header comment's own prose documents fetch()/XMLHttpRequest by
        # name (stating neither is called) - strip it before checking
        # for a real call site, same pattern as this file's own PDF/Eye
        # equivalents this session.
        self.code_only = self.js[self.js.index("*/") + 2:]

    def test_username_and_project_scoped_storage_keys(self):
        # Section 11: no cross-account leakage.
        self.assertIn("var PINNED_KEY = 'beehive:tabs:pinned:' + username + ':' + projectId;", self.js)
        self.assertIn("var PREVIEW_KEY = 'beehive:tabs:preview:' + username + ':' + projectId;", self.js)

    def test_pinned_is_localstorage_preview_is_sessionstorage(self):
        # Section 5: pinned "persist across navigation and browser
        # reload" (localStorage). Section 4: preview "not persisted
        # across sessions" (sessionStorage).
        self.assertIn("window.localStorage.getItem(PINNED_KEY)", self.js)
        self.assertIn("window.localStorage.setItem(PINNED_KEY", self.js)
        self.assertIn("window.sessionStorage.getItem(PREVIEW_KEY)", self.js)
        self.assertIn("window.sessionStorage.setItem(PREVIEW_KEY", self.js)

    def test_reconciliation_revalidates_against_authorized_active_sources(self):
        # Section 5/11: "a stale, removed, or unauthorized Document must
        # not be exposed through restored tab metadata."
        self.assertIn("document.getElementById('workspace-active-sources-data')", self.js)
        self.assertIn("var pinned = loadPinned().filter(function (entry) { return !!activeById[entry.id]; });", self.js)
        self.assertIn("if (preview && !activeById[preview.id]) { preview = null; }", self.js)

    def test_tabs_are_real_links_not_client_side_routing(self):
        self.assertIn("a.href = baseUrl + '?source=' + encodeURIComponent(source.id);", self.js)

    def test_no_fetch_or_xhr_anywhere(self):
        self.assertNotIn("fetch(", self.code_only)
        self.assertNotIn("XMLHttpRequest", self.code_only)

    def test_no_duplicate_active_tab_activating_existing_updates_lastactive(self):
        # A source that matches an existing pinned entry updates that
        # SAME entry (never creates a second one) - the actual mechanism
        # that prevents a duplicate tab for one Document.
        self.assertIn("var existingPinned = findPinned(selectedSourceId);", self.js)
        self.assertIn("existingPinned.lastActiveAt = Date.now();", self.js)

    def test_pin_replaces_preview_not_duplicates(self):
        fn = self.js[self.js.index("function pinTab("):self.js.index("function normalizedAlias(")]
        self.assertIn("if (preview && preview.id === sourceId) { preview = null; savePreview(null); }", fn)

    def test_double_click_preview_converts_to_pinned(self):
        self.assertIn("if (isPreview) pinTab(source.id);", self.js)

    def test_alias_validation_rejects_empty_and_duplicate(self):
        fn = self.js[self.js.index("function renameTab("):self.js.index("function restoreOriginalName(")]
        self.assertIn("if (!alias) return", fn)
        self.assertIn("if (aliasInUse(alias, sourceId)) return", fn)

    def test_rename_auto_pins_a_preview_tab(self):
        fn = self.js[self.js.index("function renameTab("):self.js.index("function restoreOriginalName(")]
        self.assertIn("if (!findPinned(sourceId)) pinTab(sourceId);", fn)

    def test_color_auto_pins_a_preview_tab(self):
        fn = self.js[self.js.index("function setTabColor("):self.js.index("function mostRecentVisibleFallback(")]
        self.assertIn("if (!findPinned(sourceId)) pinTab(sourceId);", fn)

    def test_restore_original_name_clears_alias_only(self):
        fn = self.js[self.js.index("function restoreOriginalName("):self.js.index("function setTabColor(")]
        self.assertIn("entry.alias = null;", fn)

    def test_default_color_action_clears_color(self):
        self.assertIn("addItem('Default Color', function () { setTabColor(source.id, null); });", self.js)

    def test_hide_preserves_alias_color_pin_state(self):
        fn = self.js[self.js.index("function hideTab("):self.js.index("function unhideTab(")]
        self.assertIn("entry.hidden = true;", fn)
        self.assertNotIn("entry.alias", fn)
        self.assertNotIn("entry.color", fn)

    def test_hidden_active_tab_falls_back_mru_then_preview_then_empty(self):
        fn = self.js[self.js.index("function activateFallback("):self.js.index("function hideTab(")]
        self.assertIn("mostRecentVisibleFallback", fn)
        self.assertIn("preview", fn)
        self.assertIn("navigateToEmpty();", fn)

    def test_unhide_restores_to_visible_strip_and_activates(self):
        fn = self.js[self.js.index("function unhideTab("):self.js.index("function closeTab(")]
        self.assertIn("entry.hidden = false;", fn)
        self.assertIn("navigateTo(sourceId);", fn)

    def test_close_removes_only_workspace_state_never_the_document(self):
        fn = self.js[self.js.index("function closeTab("):self.js.index("function closeOthers(")]
        self.assertNotIn("fetch(", fn)
        self.assertNotIn("remove_document", fn)
        self.assertIn("pinned.splice(idx, 1)", fn)

    def test_no_false_dirty_warning_on_close(self):
        self.assertNotIn("beforeunload", self.js)
        self.assertNotIn("unsaved", self.js.lower())

    def test_close_others_keeps_only_the_one_tab(self):
        fn = self.js[self.js.index("function closeOthers("):self.js.index("function closeAllTabs(")]
        self.assertIn("pinned = keep ? [keep] : [];", fn)

    def test_roving_tabindex_and_arrow_key_navigation(self):
        start = self.js.index("function onTabKeydown(")
        fn = self.js[start:self.js.index("render();", start)]
        self.assertIn("ArrowRight", fn)
        self.assertIn("ArrowLeft", fn)
        self.assertIn("'Home'", fn)
        self.assertIn("'End'", fn)
        self.assertIn("t.setAttribute('tabindex', '-1')", fn)

    def test_space_key_activates_a_tab(self):
        self.assertIn("else if (e.key === ' ') { e.preventDefault(); tabEl.click(); }", self.js)

    def test_tab_role_and_aria_selected_set(self):
        self.assertIn("a.setAttribute('role', 'tab');", self.js)
        self.assertIn("a.setAttribute('aria-selected', String(isActive));", self.js)

    def test_alias_does_not_replace_accessible_document_identity(self):
        # Section 12: "do not replace the actual Document accessible
        # name with its decorative color or UI-reference badge" - the
        # accessible name includes the ORIGINAL name even when aliased.
        self.assertIn("accessibleName = alias ? (alias + ', originally ' + source.name) : source.name;", self.js)

    def test_original_name_reachable_via_title_and_show_original_action(self):
        self.assertIn("if (alias) a.title = 'Original name: ' + source.name;", self.js)
        self.assertIn("addItem('Show Original Document Name'", self.js)

    def test_menu_actions_gated_by_current_state(self):
        # Section 10: "do not show actions that are meaningless for the
        # current state."
        menu_fn = self.js[self.js.index("function openTabMenu("):self.js.index("document.addEventListener('mousedown'")]
        self.assertIn("if (isPreview) {\n            addItem('Keep Open'", menu_fn)
        self.assertIn("if (entry && entry.alias) {\n            addItem('Restore Original Name'", menu_fn)
        self.assertIn("if (entry && entry.color) {\n            addItem('Default Color'", menu_fn)
        self.assertIn("if (!isPreview) {\n            addItem('Hide Tab'", menu_fn)

    def test_no_prompt_used_real_inline_input_instead(self):
        self.assertNotIn("window.prompt(", self.code_only)
        self.assertIn("document-tab-rename-input", self.js)

    def test_no_scope_creep_beyond_dtab1(self):
        for forbidden in ("tab-group", "split-pane", "cross-project", "development-terminal", "dt1"):
            self.assertNotIn(forbidden, self.js.lower().replace("_", "-"))


class PdfViewerStatePersistenceTests(unittest.TestCase):
    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_view_state_key_scoped_by_username_project_and_source(self):
        fn = self.js[self.js.index("function viewStateKey("):self.js.index("function loadViewState(")]
        self.assertIn("'beehive:docview:' + username + ':' + projectId + ':' + sourceId", fn)

    def test_saved_state_includes_required_fields(self):
        fn = self.js[self.js.index("function saveViewStateNow("):self.js.index("function saveViewStateSoon(")]
        for field in ("page:", "zoom:", "rotation:", "scrollLeft:", "scrollTop:", "searchQuery:"):
            self.assertIn(field, fn)

    def test_mount_accepts_source_id_and_restores_saved_state(self):
        mount_fn = self.js[self.js.index("function mount(url, canvasContainer, downloadFilename, sourceId)"):self.js.index("function unmount(")]
        self.assertIn("var saved = loadViewState(currentSourceId);", mount_fn)
        self.assertIn("currentPage = hasSavedPage ? saved.page : 1;", mount_fn)

    def test_zoom_page_rotation_changes_trigger_debounced_save(self):
        for fn_name in ("function goToPage(", "function setZoom(", "function rotate("):
            fn = self.js[self.js.index(fn_name):]
            fn = fn[:fn.index("\n    }\n")]
            self.assertIn("saveViewStateSoon();", fn, fn_name)

    def test_scroll_position_persisted_via_container_scroll_listener(self):
        self.assertIn("canvasContainer.addEventListener('scroll', saveViewStateSoon);", self.js)

    def test_state_flushed_synchronously_on_pagehide(self):
        pagehide = self.js[self.js.index("window.addEventListener('pagehide'"):]
        pagehide = pagehide[:pagehide.index("});") + 3]
        self.assertIn("Object.keys(surfaces).forEach", pagehide)
        self.assertIn("surfaces[n].saveViewStateNow();", pagehide)

    def test_auto_mount_passes_source_id_from_dom(self):
        self.assertIn("autoMountEl.dataset.sourceId || ''", self.js)

    def test_restored_search_query_does_not_auto_navigate(self):
        # Section 6's own "where safe and appropriate" - restoring the
        # query text is safe; auto-re-running it could silently jump
        # away from the just-restored page, which is not.
        mount_fn = self.js[self.js.index("function mount(url, canvasContainer, downloadFilename, sourceId)"):self.js.index("function unmount(")]
        self.assertIn("searchInput.value = (saved && saved.searchQuery) || '';", mount_fn)
        self.assertNotIn("runSearch(saved.searchQuery)", mount_fn)


class AccountIsolationTests(_BaseTestCase):
    """Section 11: 'logout/login behavior must not leak tab names or
    Document identities to another account.' document_tabs.js derives
    its storage-key username segment from .workspace-user-name's own
    rendered text (see DocumentTabsJsCoreTests.test_username_and_
    project_scoped_storage_keys) - this confirms that text is genuinely
    different per authenticated account, which is what makes two
    accounts on the same browser profile land on two DIFFERENT
    localStorage keys rather than sharing one."""

    def test_workspace_user_name_reflects_the_actual_authenticated_account(self):
        doc = self._ingest("DTAB1 Account Isolation Project", "spec.pdf")
        owner_body = self._client(username="dtab1_owner", user_id=1).get(
            f"/projects/{doc.project_id}/workspace"
        ).get_data(as_text=True)
        other_body = self._client(username="dtab1_other", user_id=2).get(
            f"/projects/{doc.project_id}/workspace"
        ).get_data(as_text=True)
        self.assertIn("dtab1_owner", owner_body)
        self.assertIn("dtab1_other", other_body)
        # The two rendered pages must not cross-contaminate: owner's own
        # page never shows the other account's name in the identity
        # slot, and vice versa - the actual precondition the storage-key
        # scoping in document_tabs.js relies on to isolate tabs.
        owner_name_idx = owner_body.index('class="workspace-user-name"')
        owner_name_tag = owner_body[owner_name_idx:owner_body.index("</span>", owner_name_idx)]
        self.assertIn("dtab1_owner", owner_name_tag)
        self.assertNotIn("dtab1_other", owner_name_tag)


class ExistingBehaviorPreservedTests(_BaseTestCase):
    def test_lists_hierarchy_still_present(self):
        # CLAUDE-P40-VW7B: an open Project's own Lists hierarchy is now
        # `lists.project.self` and its family branch directly - the
        # portfolio-level `lists.projects` root no longer renders at all
        # while a Project is open (Section 3's own removal of the
        # portfolio from the opened workspace).
        doc = self._ingest("DTAB1 Preserve Project", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.self"', body)
        self.assertNotIn('data-ui-ref="lists.project.documents"', body)
        self.assertIn('class="tree-children project-source-tree"', body)
        self.assertIn('data-ui-ref="lists.project.documents.leaf"', body)

    def test_lists_thumbnails_split_still_present(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="lists-pane"', html)
        self.assertIn('id="thumbnails-pane"', html)

    def test_toolbox_and_eye_still_present(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="workspace-right-column"', html)
        self.assertIn('id="eye-pane"', html)

    def test_pdf_document_controls_still_present(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="workspace-document-controls"', html)

    def test_chat_composer_bottom_margin_still_intact(self):
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, ".conversation-input-form")
        self.assertIn("padding-bottom: var(--conversation-inset)", body)

    def test_display_chat_and_toolbox_eye_resize_still_present(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("var mainColumn = document.querySelector('.workspace-main-column')", html)
        self.assertIn("var divider = document.getElementById('toolbox-eye-divider')", html)

    def test_project_access_authorization_unchanged(self):
        # A foreign/removed source id still degrades to None, never a
        # tab-driven bypass - the SAME show_workspace resolution DTAB1's
        # own design review found and reused, untouched by this stage.
        routes_source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertIn(
            "selected_source = next(\n        (s for s in workspace.sources if s[\"id\"] == selected_source_id), None,\n    ) if selected_source_id else None",
            routes_source,
        )


class RemovedUnauthorizedDocumentRejectionTests(unittest.TestCase):
    def test_active_sources_json_is_the_only_source_of_truth_for_tabs(self):
        # A removed/foreign Document's id simply won't appear in
        # active_sources - reconciliation drops any locally-stored tab
        # entry whose id isn't in that authorized set, so a stale tab
        # can never resolve to a removed or unauthorized Document.
        js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("activeSources.forEach(function (s) { activeById[s.id] = s; });", js)
        self.assertIn("pinned = loadPinned().filter(function (entry) { return !!activeById[entry.id]; });", js)


if __name__ == "__main__":
    unittest.main()
