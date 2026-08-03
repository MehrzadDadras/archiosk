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
  width" row) now stops at the Lists column's own width via
  margin-left, a disclosed, deliberate narrowing of that earlier rule,
  not a silent reversal - it still spans Display+Toolbox, and collapses
  to 0 the moment html.launcher-hidden or a narrow viewport removes
  Lists from the layout.
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

    def test_thumbnails_pane_and_divider_hidden_by_default(self):
        doc = self._ingest("VW7A2 Project 2", "spec.pdf")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        idx = body.index('id="thumbnails-pane"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn("hidden", tag)
        idx2 = body.index('id="lists-thumbnails-divider"')
        tag2 = body[body.rindex("<div", 0, idx2):body.index(">", idx2)]
        self.assertIn("hidden", tag2)

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

    def test_lists_pane_fills_column_by_default(self):
        body = _rule_body(self.css, ".lists-pane")
        self.assertIn("flex: 1 1 auto", body)

    def test_has_thumbnails_class_yields_the_column_to_thumbnails(self):
        body = _rule_body(self.css, ".launcher-panel.has-thumbnails .lists-pane")
        self.assertIn("var(--lists-height", body)

    def test_thumbnails_pane_hidden_rule_is_display_none(self):
        self.assertIn("display: none", _rule_body(self.css, ".thumbnails-pane[hidden]"))

    def test_divider_hidden_rule_is_display_none(self):
        self.assertIn("display: none", _rule_body(self.css, ".lists-thumbnails-divider[hidden]"))

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

    def test_chat_region_offsets_past_the_lists_column(self):
        body = _rule_body(self.css, ".chat-region")
        self.assertIn("margin-left: 240px", body)

    def test_chat_region_offset_collapses_when_lists_hidden(self):
        body = _rule_body(self.css, "html.launcher-hidden .chat-region")
        self.assertIn("margin-left: 0", body)

    def test_chat_region_offset_collapses_on_narrow_viewport(self):
        media_idx = self.css.index("@media (max-width: 640px)")
        # There are two such blocks (.launcher-panel's own, above, and
        # this stage's new .chat-region one) - just confirm a
        # .chat-region rule with margin-left: 0 exists somewhere after
        # the first narrow-viewport breakpoint.
        tail = self.css[media_idx:]
        self.assertIn(".chat-region { margin-left: 0; }", tail)


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

    def test_thumbnail_click_navigates_via_real_go_to_page(self):
        self.assertIn("goToPage(parseInt(this.dataset.page, 10))", self.js)

    def test_current_page_thumbnail_gets_aria_current(self):
        self.assertIn("row.setAttribute('aria-current'", self.js)

    def test_build_thumbnails_shows_the_split_and_clear_hides_it(self):
        self.assertIn("window.ArchioskListsThumbnailsSplit) window.ArchioskListsThumbnailsSplit.show()", self.js)
        self.assertIn("window.ArchioskListsThumbnailsSplit) window.ArchioskListsThumbnailsSplit.hide()", self.js)

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

    def test_divider_exposes_show_hide_api_for_pdf_viewer(self):
        self.assertIn("window.ArchioskListsThumbnailsSplit = {", self.html)
        self.assertIn("show: function ()", self.html)
        self.assertIn("hide: function ()", self.html)

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
        # The only write target anywhere near mount() is the in-memory
        # annotationsByPage map / the canvas overlay - no fetch/XHR/form
        # submission back to the Document's own file route exists in
        # this file at all.
        self.assertNotIn("fetch(", self.js)
        self.assertNotIn("XMLHttpRequest", self.js)

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


if __name__ == "__main__":
    unittest.main()
