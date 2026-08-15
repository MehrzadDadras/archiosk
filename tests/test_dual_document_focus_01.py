"""
CLAUDE-DUAL-DOCUMENT-FOCUS-01 - Focus-Routed Toolbar, Eye Toolbox
Thumbnails, and Conditional Eye Layout (addendum A).

Closes the Main/Eye interaction grammar: one shared top document
toolbar whose buttons dispatch to whichever surface (Main Display or
Eye) currently has focus; Eye's own page thumbnails appear inside
Toolbox instead of a permanent secondary list; Eye and its divider
only occupy the right column while Eye actually holds content
(image/saved capture/Project Document/Compare active) - otherwise
Toolbox becomes the full-height right column.

No real browser tool exists in this environment (this repo's own
established ceiling - see test_p40eye1_toolbox_eye_column.py's own
header comment) - coverage here is template/CSS/JS source structure,
the same practical ceiling every prior Eye/Toolbox stage's own tests
already use. The live interaction (focus switching, toolbar resync,
independent page state) was verified directly on archiosk.com as part
of this stage's own required live proof, not re-asserted here.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"
_EYE_PANE_JS_PATH = _REPO_ROOT / "static" / "js" / "eye_pane.js"


def _rule_body(css: str, selector: str) -> str:
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


class ToolboxEyeThumbnailsMarkupTests(unittest.TestCase):
    """Part 2/5/7: Toolbox swaps between its own normal content and Eye's
    own page thumbnails, one visible slot, never both permanently."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_toolbox_normal_content_wrapper_exists(self):
        self.assertIn('id="toolbox-normal-content"', self.html)

    def test_toolbox_eye_thumbnails_panel_exists_and_starts_hidden(self):
        match = re.search(
            r'<div class="toolbox-eye-thumbnails-panel" id="toolbox-eye-thumbnails-panel"([^>]*)>',
            self.html,
        )
        self.assertIsNotNone(match, "toolbox-eye-thumbnails-panel not found")
        self.assertIn("hidden", match.group(1))

    def test_toolbox_eye_thumbnails_list_and_empty_state_exist(self):
        self.assertIn('id="toolbox-eye-thumbnails-list"', self.html)
        self.assertIn('id="toolbox-eye-thumbnails-empty-state"', self.html)
        self.assertIn("thumbnails-list", self.html)

    def test_compare_button_lives_outside_the_swappable_wrapper(self):
        # The Compare toggle must stay reachable regardless of which of
        # #toolbox-normal-content/#toolbox-eye-thumbnails-panel is
        # currently showing (and regardless of addendum A's own
        # .eye-inactive collapse) - it is Eye's primary re-open path.
        compare_idx = self.html.index('id="toolbox-compare-btn"')
        wrapper_idx = self.html.index('id="toolbox-normal-content"')
        self.assertLess(compare_idx, wrapper_idx)


class ScriptLoadOrderTests(unittest.TestCase):
    """pdf_viewer.js must load (and define window.ArchioskPdfViewer)
    before eye_pane.js's own IIFE runs and calls createSurface - a real
    load-order bug this stage found and fixed (pdf_viewer.js used to
    load later, via case_workspace.html's own extra_scripts block)."""

    def test_pdf_viewer_script_precedes_eye_pane_script_in_base_html(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        pdf_viewer_idx = html.index("js/pdf_viewer.js")
        eye_pane_idx = html.index("js/eye_pane.js")
        self.assertLess(pdf_viewer_idx, eye_pane_idx)

    def test_case_workspace_no_longer_double_loads_pdf_viewer_on_main_path(self):
        html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")
        # Exactly one remaining <script> tag, gated to the panel_only
        # branch (where base.html - and therefore its own copy - never
        # applies). Comments referencing the file elsewhere don't count.
        tags = re.findall(r'<script src="[^"]*pdf_viewer\.js[^"]*"', html)
        self.assertEqual(len(tags), 1)
        idx = html.index(tags[0])
        preceding = html[:idx]
        self.assertIn("{% else %}", preceding[-1200:])


class PdfViewerFactoryTests(unittest.TestCase):
    """Part 3: the single-document engine is now a reusable factory so
    Main and Eye can each hold an independent PDF instance."""

    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_defines_create_pdf_surface_factory(self):
        self.assertIn("function createPdfSurface(name, thumbnailsList, thumbnailsEmptyState)", self.js)

    def test_exposes_create_surface_on_public_api(self):
        self.assertIn("createSurface: createPdfSurface", self.js)

    def test_main_surface_created_via_factory(self):
        self.assertIn("createPdfSurface('main',", self.js)

    def test_focus_state_is_global_and_toolbar_dispatches_to_focused_surface(self):
        self.assertIn("window.__activeDocumentSurface", self.js)
        self.assertIn("function getFocused() { return surfaces[window.__activeDocumentSurface]; }", self.js)

    def test_annotation_and_region_tools_are_main_only(self):
        # Part 3's own disclosed scope boundary (see this file's header
        # comment) - annotation/region toolbar buttons always dispatch to
        # surfaces.main, never getFocused().
        self.assertIn("var m = surfaces.main; if (m) m.setActiveTool(btn.dataset.tool);", self.js)
        self.assertIn("if (name !== 'main') return;", self.js)

    def test_apply_focus_indication_disables_annotation_tools_when_not_main(self):
        body = self.js[self.js.index("function applyFocusIndication()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("annotationToolButtons.forEach(function (btn) { btn.disabled = !isMain; });", body)

    def test_apply_focus_indication_toggles_surface_focused_class(self):
        body = self.js[self.js.index("function applyFocusIndication()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("classList.toggle('surface-focused', isMain)", body)
        self.assertIn("classList.toggle('surface-focused', !isMain)", body)

    def test_thumbnails_panel_visibility_reflects_eye_hasdoc(self):
        self.assertIn("var eyeHasDoc = !!(eyeSurface && eyeSurface.hasDoc());", self.js)
        self.assertIn("toolboxEyeThumbnailsPanel.hidden = !eyeHasDoc;", self.js)
        self.assertIn("toolboxNormalContent.hidden = eyeHasDoc;", self.js)

    def test_thumbnails_panel_visibility_notifies_eye_layout(self):
        self.assertIn("if (window.ArchioskEyeLayout) window.ArchioskEyeLayout.refresh();", self.js)


class EyePaneIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")

    def test_eye_surface_created_via_shared_factory_not_a_mini_renderer(self):
        self.assertIn("window.ArchioskPdfViewer.createSurface(", self.js)
        self.assertIn("'eye',", self.js)
        # The old feature-poor, independent-of-pdf_viewer.js mini-renderer
        # this replaced must be gone, not left dead alongside the new path.
        self.assertNotIn("function renderEyePdf(", self.js)

    def test_eye_pdf_thumbnails_target_toolbox_not_the_lists_rail(self):
        self.assertIn("document.getElementById('toolbox-eye-thumbnails-list')", self.js)
        self.assertIn("document.getElementById('toolbox-eye-thumbnails-empty-state')", self.js)

    def test_eye_has_content_includes_compare_image_saved_and_document(self):
        body = self.js[self.js.index("function eyeHasContent()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("compareActive || hasImage || hasSaved || hasDocument", body)

    def test_refresh_eye_layout_toggles_eye_inactive_on_right_column(self):
        body = self.js[self.js.index("function refreshEyeLayout()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("workspace-right-column", body)
        self.assertIn("classList.toggle('eye-inactive', !eyeDetached && !eyeHasContent())", body)

    def test_eye_layout_refresh_exposed_globally_for_pdf_viewer_to_call(self):
        self.assertIn("window.ArchioskEyeLayout = { refresh: refreshEyeLayout };", self.js)

    def test_clear_document_view_restores_empty_state_hidden_flag(self):
        # Regression guard for the bug this stage's own live verification
        # caught: clearDocumentView() used to leave #eye-drop-target-empty
        # permanently [hidden] after a Document was cleared.
        body = self.js[self.js.index("function clearDocumentView()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("emptyState.hidden = false", body)
        self.assertIn("noteEl.hidden = false", body)

    def test_compare_toggle_refreshes_layout(self):
        body = self.js[self.js.index("function setCompareActive("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("refreshEyeLayout();", body)


class ConditionalEyeLayoutCssTests(unittest.TestCase):
    """Addendum A: no comparison = Toolbox owns the right column."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_eye_inactive_hides_eye_pane_and_divider(self):
        body = _rule_body(self.css, ".workspace-right-column.eye-inactive .eye-pane,\n.workspace-right-column.eye-inactive .toolbox-eye-divider")
        self.assertIn("display: none", body)

    def test_eye_inactive_expands_toolbox_to_fill_column(self):
        body = _rule_body(self.css, ".workspace-right-column.eye-inactive .workspace-pane-toolbox")
        self.assertIn("flex: 1 1 auto", body)

    def test_toolbox_eye_thumbnails_panel_respects_hidden_attribute(self):
        # Regression guard for the bug this stage's own live verification
        # caught: an author `display` declaration on this selector beat
        # the UA stylesheet's [hidden] rule, so the panel always rendered
        # even server-rendered `hidden`.
        body = _rule_body(self.css, ".toolbox-eye-thumbnails-panel[hidden]")
        self.assertIn("display: none", body)

    def test_surface_focused_indication_defined_for_both_surfaces(self):
        eye_body = _rule_body(self.css, ".eye-pane.surface-focused .eye-pane-header h2")
        display_body = _rule_body(self.css, ".workspace-pane-display.surface-focused .display-division-header-name")
        for body in (eye_body, display_body):
            self.assertIn("machine-blue", body)
            self.assertNotIn("border", body.lower())  # Part 4: no heavy border/bright box


if __name__ == "__main__":
    unittest.main()
