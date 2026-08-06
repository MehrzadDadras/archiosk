"""
CLAUDE-P40-VW7A-QA2 - Complete the PDF Viewer Controls, Thumbnails and
Collapsible Panel Geometry.

A real-browser check of the prior stage (CLAUDE-P40-VW7A-QA) reported
several gaps: the header document-controls didn't visibly connect, no
Thumbnails pane existed, the Chat region extended under the full-height
Lists column, and no annotation tools existed. This stage:

- Vendored PDF.js was switched from the modern `build/` distribution to
  `legacy/build/` (broader browser/JS-engine compatibility) and mount()
  now surfaces a real, visible error instead of failing silently - see
  static/js/vendor/pdfjs/README.md and pdf_viewer.js's own comments.
- The left column (templates/base.html's own <nav class="launcher-panel">)
  now splits into an upper Lists pane and a lower PDF Thumbnails pane,
  with a draggable divider (percentage-based, session-persisted) reusing
  static/js/case_workspace.js's own setUpChatResize pointer-drag idiom.
- static/js/pdf_viewer.js renders real per-page thumbnails lazily (an
  IntersectionObserver) and keeps the current-page thumbnail in sync
  with every goToPage() call regardless of which control triggered it.
- .chat-region (CLAUDE-P40-E3A, Section 9's own "full application
  width" row) is now nested inside a new .workspace-main-column,
  itself Lists' own sibling inside .app-shell-body, instead of being a
  full-width sibling of .app-shell-body itself - a disclosed,
  deliberate narrowing of that earlier rule, not a silent reversal
  (Chat still spans Display+Toolbox). An initial margin-left-based
  attempt at this same fix left an unpainted strip beneath Lists in
  dark Appearance modes (a real-browser follow-up correction) - the
  DOM restructuring above is what actually closed that gap, since
  Lists' own height:100% now covers the same vertical extent Chat's
  row does.
- Shell chrome that sits between the 5 themed surfaces (panel
  dividers/splitters) is not a descendant of any of them and so never
  inherited a surface's own --surface-primary redefinition - "white
  splitter tracks... in the dark theme," a second real-browser
  correction. .app-shell now gets its own appearance class, piggybacked
  on the Menu surface's resolved mode (not a new, separate preference),
  and every divider element has an explicit background instead of
  transparent. .conversation-input-form (the Chat composer) also gained
  padding-bottom (reusing the same --conversation-inset token as its
  own left/right padding) after a real-browser check found it touching
  the viewport edge.
- Real, interactive client-side PDF annotation tools (text/highlight/
  ink, select+delete, undo/redo) were added, with an explicit,
  documented scope boundary: no PDF-writing library is vendored in this
  repo, so there is no Save/Export control - annotations are a draft,
  in-memory overlay only, communicated via #doc-annotation-status and a
  beforeunload warning, never presented as if they persist.

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
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"
_CASE_WORKSPACE_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"
_VENDOR_DIR = _REPO_ROOT / "static" / "js" / "vendor" / "pdfjs"


def _rule_body(css: str, selector: str) -> str:
    """Same helper/convention as tests/test_p40e2b_flexible_workspace_frame.py's
    own _rule_body - kept as its own copy per this codebase's existing
    per-file test-helper pattern."""
    needle = re.compile(re.escape(selector) + r"(?![\w\-\"])")
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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_vw7a2_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw7a2_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename, content=b"content"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="vw7a2_owner", project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "vw7a2_owner"
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class ListsThumbnailsSplitStructureTests(_BaseTestCase):
    def test_lists_pane_and_thumbnails_pane_both_render(self):
        doc = self._ingest("VW7A2 Project 1", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="lists-pane"', body)
        self.assertIn('id="thumbnails-pane"', body)
        self.assertIn('id="lists-thumbnails-divider"', body)
        self.assertIn('id="thumbnails-list"', body)
        self.assertIn('id="thumbnails-maximize-btn"', body)

    def test_thumbnails_pane_and_divider_are_never_hidden(self):
        # CLAUDE-P40-LTH1 (correction): used to be [hidden] by default,
        # revealed only once pdf_viewer.js decided the active Document
        # was a PDF - a product-owner browser review found this meant
        # NO visible split existed at all on every Overview/Investigation/
        # Chat/non-PDF-Document page (Lists silently filled the whole
        # column). Thumbnails is now a permanent structural pane, the
        # same "never [hidden]" treatment CLAUDE-P40-EYE1 already gave
        # Eye relative to Toolbox - see that stage's own test for the
        # analogous assertion.
        doc = self._ingest("VW7A2 Project 2", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="thumbnails-pane"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertNotIn("hidden", tag)
        idx2 = body.index('id="lists-thumbnails-divider"')
        tag2 = body[body.rindex("<div", 0, idx2):body.index(">", idx2)]
        self.assertNotIn("hidden", tag2)

    def test_thumbnails_pane_and_divider_render_even_with_no_document_selected(self):
        # CLAUDE-P40-LTH1, Section 1: "a real structural pane... not
        # thumbnails appended to the bottom of the Lists scroll
        # container" - present on Overview too, not just a Document page.
        doc = self._ingest("VW7A2 Project 2b", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('id="thumbnails-pane"', body)
        self.assertIn('id="lists-thumbnails-divider"', body)
        idx = body.index('id="thumbnails-pane"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertNotIn("hidden", tag)

    def test_divider_has_separator_role_and_orientation(self):
        doc = self._ingest("VW7A2 Project 3", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="lists-thumbnails-divider"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn('role="separator"', tag)
        self.assertIn('aria-orientation="horizontal"', tag)
        self.assertIn('tabindex="0"', tag)

    def test_launcher_panel_own_id_and_collapse_mechanism_unchanged(self):
        # The existing html.launcher-hidden .launcher-panel collapse
        # mechanism (and every test pinning it) must survive this stage's
        # restructuring untouched - Lists/Thumbnails are now nested
        # inside the SAME <nav id="launcher-panel">, not a replacement
        # for it.
        doc = self._ingest("VW7A2 Project 4", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="launcher-panel"', body)
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("display: none", _rule_body(css, "html.launcher-hidden .launcher-panel"))

    def test_maximize_button_is_a_real_toggle_not_decorative(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('aria-pressed="false"', html[html.index('id="thumbnails-maximize-btn"') - 200:html.index('id="thumbnails-maximize-btn"') + 200])


class ListsThumbnailsSplitCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_lists_pane_takes_the_persisted_split_percentage_unconditionally(self):
        # CLAUDE-P40-LTH1 (correction): used to be flex:1 1 auto by
        # default, only taking var(--lists-height) once a JS-added
        # .has-thumbnails class appeared - now unconditional, the same
        # "outer column owns sizing" split .workspace-pane-toolbox
        # already uses relative to Eye (never class-gated).
        body = _rule_body(self.css, ".lists-pane")
        self.assertIn("flex: 0 0 var(--lists-height", body)

    def test_has_thumbnails_class_gating_is_gone(self):
        self.assertNotIn(".launcher-panel.has-thumbnails", self.css)

    def test_thumbnails_pane_and_divider_hidden_rules_are_gone(self):
        # CLAUDE-P40-LTH1: dead CSS once neither element is ever
        # [hidden] again - a regression guard against reintroducing the
        # old show/hide gating instead of removing it outright.
        self.assertNotIn(".thumbnails-pane[hidden]", self.css)
        self.assertNotIn(".lists-thumbnails-divider[hidden]", self.css)

    def test_divider_has_a_real_focus_visible_outline(self):
        # CLAUDE-P40-LTH1, Section 6: "visible focus" - the ::before
        # accent line only changes color/thickness, which alone is not
        # a real focus indicator for a keyboard user. Located via the
        # literal "{" rather than _rule_body's own selector search -
        # ".lists-thumbnails-divider:focus-visible" is also a substring
        # of the EARLIER ".lists-thumbnails-divider:focus-visible::before"
        # compound selector, which _rule_body's generic lookahead does
        # not exclude (a ":" continuation is not blocked), so it would
        # otherwise match that unrelated rule instead.
        start = self.css.index(".lists-thumbnails-divider:focus-visible {")
        body = self.css[start:self.css.index("}", start)]
        self.assertIn("outline:", body)

    def test_divider_uses_border_token_at_rest_and_machine_blue_while_active(self):
        rest = _rule_body(self.css, ".lists-thumbnails-divider::before")
        self.assertIn("var(--border)", rest)
        active = _rule_body(self.css, ".lists-thumbnails-divider.dragging::before")
        self.assertIn("var(--machine-blue)", active)

    def test_no_hardcoded_white_or_beige_gutter_on_new_panes(self):
        for selector in (".thumbnails-pane", ".thumbnails-pane-header", ".lists-thumbnails-divider"):
            body = _rule_body(self.css, selector)
            self.assertNotRegex(body, r"#fff\b|#f5f5dc|beige|white", msg=selector)


class ChatRegionLeftEdgeTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    # SUPERSEDED (CLAUDE-P40-VW7A-QA2, product-owner browser correction):
    # the original fix for "Chat extends underneath Lists" was
    # .chat-region { margin-left: 240px }, offsetting Chat's own box
    # while leaving it a full-width sibling of .app-shell-body. A
    # follow-up real-browser check found this left a strip beneath
    # Lists, for Chat's own row height, painted by NOTHING - reading as
    # a light rectangle in dark Appearance modes, since neither Lists
    # nor the (now-offset) Chat covered it. The real fix nests
    # .chat-region inside a new .workspace-main-column, itself Lists'
    # sibling, so Lists' own height:100% now covers the same vertical
    # extent Chat's row does - no margin-left needed at all, checked
    # below via the tests that replaced this class's old ones.
    def test_chat_region_no_longer_uses_the_superseded_margin_left_hack(self):
        body = _rule_body(self.css, ".chat-region")
        self.assertNotIn("margin-left", body)
        self.assertNotIn("html.launcher-hidden .chat-region", self.css)

    def test_workspace_main_column_rule_exists(self):
        # CLAUDE-P40-EYE1: .workspace-content-row (Display+Toolbox) is
        # retired - Toolbox moved out into its own .workspace-right-
        # column, leaving .app-main as .workspace-main-column's only row
        # content, so the separate row wrapper added nothing and was
        # removed rather than left as dead CSS.
        main_column = _rule_body(self.css, ".workspace-main-column")
        self.assertIn("flex-direction: column", main_column)
        self.assertNotIn(".workspace-content-row {", self.css)


class ChatRegionNestingTests(unittest.TestCase):
    """The structural fix itself, verified against the template SOURCE
    (precise div-nesting is awkward to prove from rendered HTML with a
    plain regex, and this repo's own convention is source/structure
    inspection over a live DOM anyway - see this file's own module
    docstring). Confirms the literal nesting templates/base.html now
    has: .workspace-main-column > [.app-main, .chat-region] - Chat is a
    DESCENDANT of the column that is itself Lists' own sibling, not a
    sibling of .app-shell-body reaching edge-to-edge on its own row (the
    prior, superseded margin-left approach). CLAUDE-P40-EYE1 later moved
    Toolbox out of this same column entirely, into its own sibling
    .workspace-right-column - not re-checked here (see EYE1's own test
    classes), just confirmed not to have disturbed this nesting."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_workspace_main_column_opens_before_app_main_and_chat(self):
        main_column_idx = self.html.index('<div class="workspace-main-column">')
        app_main_idx = self.html.index('<div class="app-main">')
        chat_idx = self.html.index('<div class="chat-region"')
        self.assertLess(main_column_idx, app_main_idx)
        self.assertLess(app_main_idx, chat_idx)

    def test_chat_region_is_the_last_real_child_before_the_column_closes(self):
        # Between chat-region's own closing {% endif %} and the next
        # real element, there must be exactly one </div> close
        # (workspace-main-column) before CLAUDE-P40-EYE1's own right-
        # column block begins - not zero (would mean chat-region escaped
        # back out to being app-shell-body's own sibling again).
        chat_block_end = self.html.index("{% endif %}", self.html.index('<div class="chat-region"'))
        next_marker_idx = self.html.index("{% if project_id is defined and workspace is defined %}", chat_block_end)
        tail = self.html[chat_block_end:next_marker_idx]
        self.assertEqual(tail.count("</div>"), 1)

    def test_no_stray_margin_left_hack_remains_in_the_template(self):
        # A guard against reintroducing the superseded fix instead of
        # relying on the real structural one.
        chat_region_tag_idx = self.html.index('<div class="chat-region"')
        self.assertNotIn("margin-left", self.html[chat_region_tag_idx:chat_region_tag_idx + 200])


class ThumbnailRenderingJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_thumbnail_build_and_render_functions_exist(self):
        self.assertIn("function buildThumbnails(", self.js)
        self.assertIn("function renderThumbnail(", self.js)
        self.assertIn("function clearThumbnails(", self.js)
        self.assertIn("function updateThumbnailCurrent(", self.js)

    def test_thumbnails_use_lazy_intersection_observer(self):
        self.assertIn("IntersectionObserver", self.js)

    def test_thumbnail_click_navigates_via_real_go_to_page_when_a_document_is_mounted(self):
        click_handler = self.js[self.js.index("row.addEventListener('click'"):self.js.index("row.addEventListener('click'") + 250]
        self.assertIn("goToPage(n)", click_handler)

    def test_thumbnail_click_navigates_to_the_document_route_in_remembered_only_mode(self):
        # CLAUDE-P40-LTH1: a remembered Document has no live canvas on
        # THIS page - clicking its thumbnail must be a real navigation
        # (navigateToDocumentPage), not goToPage (which would silently
        # no-op against a null canvas).
        click_handler = self.js[self.js.index("row.addEventListener('click'"):self.js.index("row.addEventListener('click'") + 250]
        self.assertIn("thumbnailsOnlyMode", click_handler)
        self.assertIn("navigateToDocumentPage(n)", click_handler)

    def test_current_page_thumbnail_gets_aria_current(self):
        self.assertIn("row.setAttribute('aria-current'", self.js)

    def test_build_thumbnails_hides_empty_state_and_clear_shows_it(self):
        # CLAUDE-P40-LTH1 (correction): the old cross-script show()/
        # hide() API on the whole PANE is gone (see templates/base.html's
        # own comment) - this file now toggles its own #thumbnails-
        # empty-state element directly, since the pane itself is always
        # visible.
        self.assertNotIn("ArchioskListsThumbnailsSplit", self.js)
        build_fn = self.js[self.js.index("function buildThumbnails("):self.js.index("function updateThumbnailCurrent(")]
        self.assertIn("thumbnailsEmptyState) thumbnailsEmptyState.hidden = true", build_fn)
        clear_fn = self.js[self.js.index("function clearThumbnails("):self.js.index("function buildThumbnails(")]
        self.assertIn("thumbnailsEmptyState) thumbnailsEmptyState.hidden = false", clear_fn)

    def test_update_nav_state_keeps_thumbnails_in_sync_on_every_page_change(self):
        # Section 3: "thumbnail list follows page changes... from
        # scrolling or the top-menu controls" - every goToPage() call
        # (prev/next, page input, search jump, thumbnail click itself)
        # funnels through renderPage -> updateNavState, so this one call
        # site is the actual guarantee, not per-control wiring.
        nav_state_body = self.js[self.js.index("function updateNavState("):self.js.index("function updateNavState(") + 400]
        self.assertIn("updateThumbnailCurrent();", nav_state_body)


class ListsThumbnailsDividerJsTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_show_hide_api_is_gone_now_that_thumbnails_is_permanent(self):
        # CLAUDE-P40-LTH1 (correction): the divider script used to
        # expose window.ArchioskListsThumbnailsSplit.show()/.hide() for
        # pdf_viewer.js to toggle the whole pane's visibility - gone now
        # that the pane is a permanent structural surface (the same
        # "never independently hidden" treatment Eye already has
        # relative to Toolbox); this script now owns ONLY the divider's
        # drag/resize mechanics.
        self.assertNotIn("window.ArchioskListsThumbnailsSplit", self.html)

    def test_divider_persistence_is_session_scoped_not_permanent(self):
        # Section 3: "proportion may persist per session" - a
        # deliberately weaker guarantee than the Lists/Toolbox show/hide
        # preferences (localStorage) above it in the same file.
        self.assertIn("window.sessionStorage.setItem(heightKey", self.html)
        self.assertIn("window.sessionStorage.getItem(heightKey", self.html)

    def test_double_click_restores_default_proportion(self):
        self.assertIn("divider.addEventListener('dblclick', function () { applyPct(DEFAULT_PCT); });", self.html)

    def test_maximize_button_toggles_and_remembers_prior_proportion(self):
        self.assertIn("preMaximizePct = parseFloat", self.html)

    def test_keyboard_arrow_home_end_stepping_present(self):
        divider_script = self.html[self.html.index("var divider = document.getElementById('lists-thumbnails-divider')"):]
        divider_script = divider_script[:divider_script.index("})();")]
        self.assertIn("ArrowUp", divider_script)
        self.assertIn("ArrowDown", divider_script)
        self.assertIn("'Home'", divider_script)
        self.assertIn("'End'", divider_script)


class DraggingAccentClassTests(unittest.TestCase):
    def test_chat_handle_toggles_dragging_class(self):
        js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("handle.classList.add('dragging')", js)
        self.assertIn("handle.classList.remove('dragging')", js)
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("var(--machine-blue)", _rule_body(css, ".conversation-dock-resize-handle.dragging::before"))

    def test_lists_thumbnails_divider_toggles_dragging_class(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn("divider.classList.add('dragging')", html)
        self.assertIn("divider.classList.remove('dragging')", html)


class AnnotationToolsMarkupTests(_BaseTestCase):
    def test_annotation_tool_buttons_render_for_pdf(self):
        doc = self._ingest("VW7A2 Annotate Project", "spec.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        for control_id in (
            "doc-annotate-text", "doc-annotate-highlight", "doc-annotate-ink",
            "doc-annotate-select", "doc-annotate-delete", "doc-annotate-undo",
            "doc-annotate-redo", "doc-annotation-status",
        ):
            self.assertIn(f'id="{control_id}"', body)

    def test_annotation_tools_start_unpressed_and_disabled_where_applicable(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        idx = html.index('id="doc-annotate-text"')
        tag = html[html.rindex("<button", 0, idx):html.index(">", idx)]
        self.assertIn('aria-pressed="false"', tag)
        for control_id in ("doc-annotate-delete", "doc-annotate-undo", "doc-annotate-redo"):
            i = html.index(f'id="{control_id}"')
            btn_tag = html[html.rindex("<button", 0, i):html.index(">", i)]
            self.assertIn("disabled", btn_tag)

    def test_no_save_or_export_control_exists_the_disclosed_boundary(self):
        # Section 4's own explicit permission: stop and report the exact
        # technical boundary rather than ship a nonfunctional control. No
        # PDF-writing library is vendored in this repo (see
        # static/js/vendor/pdfjs/README.md - rendering only) so there is
        # deliberately no Save/Export button to click.
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn('id="doc-annotate-save"', html)
        self.assertNotIn('id="doc-annotate-export"', html)
        self.assertNotIn('id="doc-annotation-save"', html)


class AnnotationJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_core_annotation_functions_exist(self):
        for fn in (
            "function addAnnotation(", "function removeAnnotation(",
            "function undo(", "function redo(", "function hitTestAnnotation(",
            "function redrawAnnotations(", "function setActiveTool(",
            "function openTextAnnotationInput(",
        ):
            self.assertIn(fn, self.js)

    def test_annotations_stored_in_pdf_space_not_raw_pixels(self):
        self.assertIn("convertToPdfPoint", self.js)
        self.assertIn("convertToViewportPoint", self.js)

    def test_annotation_state_is_reset_on_every_mount_and_unmount(self):
        self.assertIn("resetAnnotationState();", self.js)
        mount_fn = self.js[self.js.index("function mount("):self.js.index("function unmount(")]
        self.assertIn("resetAnnotationState();", mount_fn)

    def test_original_document_is_never_written_to(self):
        # Annotations themselves are still purely in-memory (the
        # annotationsByPage map / canvas overlay) - never POSTed anywhere.
        # CLAUDE-MM4 added real fetch() calls, but only to the NEW,
        # separate /drawing-structure (registers StructuralUnits) and
        # /drawing-regions (creates a governed AddressableRegion +
        # EvidenceItem) API routes - neither ever writes to the Source's
        # own original file bytes. The real invariant this test protects
        # is narrower than "no fetch() anywhere": the Document's own
        # file-serving download link/route is never a fetch() TARGET.
        self.assertNotIn("XMLHttpRequest", self.js)
        self.assertNotIn("fetch(downloadLink", self.js)
        self.assertIn("/drawing-structure", self.js)
        self.assertIn("/drawing-regions", self.js)

    def test_unsaved_changes_are_surfaced_and_warned_on_unload(self):
        self.assertIn("Unsaved annotations", self.js)
        self.assertIn("beforeunload", self.js)
        self.assertIn("e.preventDefault();", self.js)

    def test_undo_redo_stacks_are_real_not_decorative(self):
        undo_fn = self.js[self.js.index("function undo("):self.js.index("function redo(")]
        self.assertIn("undoStack.pop()", undo_fn)
        self.assertIn("redoStack.push(entry)", undo_fn)

    def test_escape_cancels_the_active_tool(self):
        self.assertIn("e.key === 'Escape' && activeTool", self.js)

    def test_select_tool_only_acts_when_active(self):
        pointerdown_fn = self.js[self.js.index("function onOverlayPointerDown("):self.js.index("function onOverlayPointerMove(")]
        self.assertIn("if (!activeTool || !currentViewport) return;", pointerdown_fn)


class PdfJsLegacyBuildTests(unittest.TestCase):
    def test_readme_documents_the_legacy_build_switch(self):
        readme = (_VENDOR_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("legacy/build/pdf.min.mjs", readme)
        self.assertIn("legacy/build/pdf.worker.min.mjs", readme)
        self.assertIn("CLAUDE-P40-VW7A-QA2", readme)

    def test_vendored_files_exist(self):
        self.assertTrue((_VENDOR_DIR / "pdf.min.mjs").exists())
        self.assertTrue((_VENDOR_DIR / "pdf.worker.min.mjs").exists())

    def test_load_error_is_visible_not_silent(self):
        js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        self.assertIn("function showLoadError(", js)
        self.assertIn("could not be opened in the viewer", js)


class LeftColumnFullHeightBackgroundTests(unittest.TestCase):
    """Product-owner browser correction: a light rectangle was visible
    beneath Lists in dark Appearance modes. Root cause was .chat-region
    being a full-width sibling of .app-shell-body (its own row, below
    Lists' own row) - fixed by nesting Chat inside .workspace-main-column,
    itself Lists' sibling, so Lists' height:100% now covers Chat's row
    too. See ChatRegionNestingTests above for the DOM-structure half of
    this; this class covers the CSS/scrollbar half."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_app_shell_has_a_real_background(self):
        body = _rule_body(self.css, ".app-shell")
        self.assertIn("var(--surface-primary)", body)

    def test_lists_and_thumbnails_scroll_regions_have_themed_scrollbar_color(self):
        for selector in (".lists-pane", ".thumbnails-list"):
            body = _rule_body(self.css, selector)
            self.assertIn("scrollbar-color:", body)
            self.assertIn("var(--border-strong)", body)
            self.assertIn("var(--surface-primary)", body)


class AppearanceControlledSplitterTests(unittest.TestCase):
    """Product-owner browser correction: "white splitter tracks... in
    the dark theme." Dividers/gutters are shell chrome (siblings of the
    5 themed surfaces, not descendants of any one), so they never picked
    up a surface's own --surface-primary redefinition. Fixed via a 6th,
    piggybacked appearance class on .app-shell itself (sourced from the
    Menu surface's own resolved mode, not a new separate preference)
    plus a real (non-transparent) background on every divider element."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_panel_divider_background_is_a_token_not_transparent(self):
        body = _rule_body(self.css, ".panel-divider")
        self.assertIn("var(--surface-primary)", body)
        declaration = re.search(r"background:\s*[^;]+;", body).group(0)
        self.assertNotIn("transparent", declaration)

    def test_lists_thumbnails_divider_background_is_a_token_not_transparent(self):
        body = _rule_body(self.css, ".lists-thumbnails-divider")
        self.assertIn("var(--surface-primary)", body)
        declaration = re.search(r"background:\s*[^;]+;", body).group(0)
        self.assertNotIn("transparent", declaration)

    def test_conversation_dock_resize_handle_has_a_real_background(self):
        body = _rule_body(self.css, ".conversation-dock-resize-handle")
        self.assertIn("var(--surface-primary)", body)

    def test_app_shell_is_actually_in_the_combined_appearance_selector_lists(self):
        # Regression guard for a real bug found during a later product-
        # owner browser correction (CLAUDE-P40-EYE1's own "thick white/
        # cream strips" report): the JS piggyback above (test_app_shell_
        # gets_a_piggybacked_appearance_class_early) toggles .appearance-
        # dark/-tinted/-deep-forest on .app-shell, but that class did
        # NOTHING until .app-shell was also added to the three combined
        # CSS selector lists that actually redefine --surface-primary/
        # --canvas/etc. per mode - the JS-only half of the fix was
        # shipped without this CSS-only half, so .app-shell's own
        # background always resolved to the unthemed Light default in
        # every dark mode, regardless of the class being present.
        for mode in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            self.assertIn(f".app-shell.{mode}", self.css, mode)

    def test_no_opacity_based_parent_trick_used_for_any_divider(self):
        for selector in (".panel-divider", ".lists-thumbnails-divider", ".conversation-dock-resize-handle", ".app-shell"):
            body = _rule_body(self.css, selector)
            self.assertNotIn("opacity", body, selector)

    def test_app_shell_gets_a_piggybacked_appearance_class_early(self):
        # The pre-paint script (avoids a flash of the wrong shell color).
        early_script = self.html[self.html.index("window.__resolveStoredAppearanceMode"):self.html.index("</script>", self.html.index("window.__resolveStoredAppearanceMode"))]
        self.assertIn("document.querySelector('.app-shell')", early_script)
        self.assertIn("if (key === 'menu')", early_script)

    def test_app_shell_class_stays_in_sync_on_live_menu_changes(self):
        # The main Appearance-menu wiring script, not just first paint -
        # switching Menu's own mode (individually or via "All") later.
        self.assertIn("function setSurfaceMode(key, mode, persist)", self.html)
        set_surface_mode_fn = self.html[self.html.index("function setSurfaceMode(key, mode, persist)"):]
        set_surface_mode_fn = set_surface_mode_fn[:set_surface_mode_fn.index("var radios = document.querySelectorAll")]
        self.assertIn("if (key === 'menu')", set_surface_mode_fn)
        self.assertIn("document.querySelector('.app-shell')", set_surface_mode_fn)

    def test_dividers_still_have_a_distinct_accent_only_on_hover_focus_or_drag(self):
        # The base background fix must not have swallowed the existing
        # discoverability accent - :hover/:focus-visible/.dragging still
        # need to paint var(--machine-blue) on the accent line itself.
        for selector in (".panel-divider:hover::before", ".panel-divider:focus-visible::before"):
            body = _rule_body(self.css, selector)
            self.assertIn("var(--machine-blue)", body)


class ChatComposerBottomMarginTests(unittest.TestCase):
    """Product-owner browser correction: the composer row (input + Send)
    touched the viewport/application-frame edge - no bottom spacing
    existed at all, only left/right."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_composer_form_has_bottom_padding_matching_its_own_horizontal_inset(self):
        body = _rule_body(self.css, ".conversation-input-form")
        self.assertIn("padding-bottom: var(--conversation-inset)", body)
        self.assertIn("padding-left: var(--conversation-inset)", body)
        self.assertIn("padding-right: var(--conversation-inset)", body)

    def test_bottom_padding_is_not_scoped_to_a_single_viewport_or_chat_height(self):
        # Real, unconditional padding on the flex item itself - not
        # something a narrow-viewport override or a specific
        # --chat-height value could silently undo.
        rule_start = self.css.index(".conversation-input-form {")
        self.assertNotIn("@media", self.css[max(0, rule_start - 400):rule_start])


if __name__ == "__main__":
    unittest.main()
