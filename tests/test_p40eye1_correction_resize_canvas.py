"""
CLAUDE-P40-EYE1 (product-owner browser correction) - Horizontal
Expansion and Scalable Canvas.

A real-browser screenshot found three further gaps in the just-shipped
EYE1 right column: (1) the column's own left edge was a fixed width,
not a draggable splitter; (2) "Maximize Eye" only ever changed the
Toolbox/Eye height split, never the column's own width; (3) a
dropped/pasted image rendered as a small, fixed-size thumbnail inside a
much larger Eye area instead of a real, responsive zoom/pan canvas.

Fixes, all within EYE1's own scope (Section 4's boundary - no EYE2
annotation/AI/attachment/persistence features):

- .workspace-right-column's width is now `var(--right-column-width,
  min(340px, 30vw))`, driven by a new mouse-draggable/keyboard-operable
  resize handle on the EXISTING #toolbox-divider (which keeps its own
  click-to-collapse/show behavior - a real drag is distinguished from a
  plain click via a movement threshold plus a capture-phase click
  interceptor). Practical minimums enforced both in the drag-clamp
  logic and as a CSS floor on .workspace-main-column (the centre
  column). Persisted via localStorage, per-Project.
- "Maximize Eye" (#eye-maximize-btn) now drives BOTH --toolbox-height
  (existing) and --right-column-width (new, via the drag script's own
  exposed window.ArchioskRightColumnWidth API) - collapsing Toolbox and
  expanding the column to the largest practical width in one action,
  with an exact two-dimensional restore. The maximized width is
  deliberately never persisted, so a mid-maximize reload can't trap the
  reviewer in that state.
- static/js/eye_pane.js was rewritten: the small fixed <img> preview is
  replaced by a real canvas (#eye-canvas) with Fit/zoom-in/zoom-out/
  Actual-size/Reset controls, focused-wheel zoom, and native-scroll-
  based panning (the image is sized to its own real scaled pixel
  dimensions, never CSS max-width/height percentages, so there is no
  stretching or distortion at any zoom level). A ResizeObserver on the
  viewport recalculates Fit automatically on any container resize -
  Toolbox/Eye divider drag, right-column width drag, or Eye maximize -
  but only while still in "fit" mode, never overriding a deliberate
  manual zoom.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structure.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
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


class RightColumnWidthDragTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_right_column_width_is_a_css_custom_property(self):
        rule = re.search(r"^\.workspace-right-column\s*\{[^}]*\}", self.css, re.M | re.S)
        self.assertIsNotNone(rule)
        self.assertIn("var(--right-column-width, min(340px, 30vw))", rule.group(0))

    def test_toolbox_divider_gets_resize_cursor_and_dragging_accent(self):
        body = _rule_body(self.css, ".panel-divider-toolbox")
        self.assertIn("ew-resize", body)
        dragging = _rule_body(self.css, ".panel-divider-toolbox.dragging::before")
        self.assertIn("var(--machine-blue)", dragging)

    def test_drag_script_present_with_mouse_and_keyboard_support(self):
        self.assertIn("var mainColumn = document.querySelector('.workspace-main-column')", self.html)
        script = self.html[self.html.index("var mainColumn = document.querySelector('.workspace-main-column')"):]
        script = script[:script.index("window.ArchioskRightColumnWidth")]
        self.assertIn("pointerdown", script)
        self.assertIn("pointermove", script)
        self.assertIn("'ArrowLeft'", script)
        self.assertIn("'ArrowRight'", script)

    def test_dragging_left_widens_the_column(self):
        # deltaPx = dragStartX - e.clientX means moving the pointer LEFT
        # (smaller clientX) produces a POSITIVE deltaPx, which is ADDED
        # to the starting width - i.e. widens. Confirmed by source
        # inspection since no real pointer events can be simulated here.
        self.assertIn("var deltaPx = dragStartX - e.clientX;", self.html)
        self.assertIn("applyWidth(dragStartWidth + deltaPx);", self.html)

    def test_a_real_drag_suppresses_the_pre_existing_click_toggle(self):
        self.assertIn("if (Math.abs(deltaPx) > DRAG_THRESHOLD) dragMoved = true;", self.html)
        self.assertIn("if (dragMoved) justDragged = true;", self.html)
        # Capture phase (third arg true) - fires before the bubble-phase
        # click-toggle handler regardless of script registration order.
        self.assertIn("}, true);", self.html)

    def test_practical_minimums_enforced_for_both_columns(self):
        self.assertIn("var RIGHT_MIN = 260;", self.html)
        self.assertIn("var CENTRE_MIN = 320;", self.html)
        body = _rule_body(self.css, ".workspace-main-column")
        self.assertIn("min-width: 320px", body)

    def test_width_persisted_per_project_via_localstorage(self):
        self.assertIn("var widthKey = 'beehive:panel:right-column-width:{{ project_id }}';", self.html)
        self.assertIn("window.localStorage.setItem(widthKey", self.html)

    def test_hidden_right_column_still_releases_all_width_regardless_of_stored_width(self):
        # display:none on the column overrides its own width entirely -
        # a stored/dragged --right-column-width value can never leak
        # into the hidden state as leftover reserved space.
        self.assertIn("display: none", _rule_body(self.css, "html.toolbox-hidden .workspace-right-column"))

    def test_no_opacity_used(self):
        for selector in (".panel-divider-toolbox", ".workspace-right-column"):
            body = _rule_body(self.css, selector)
            self.assertNotIn("opacity", body, selector)


class EyeMaximizeTwoDimensionalTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_eye_maximize_has_its_own_dedicated_handler(self):
        self.assertIn("function toggleEyeMaximize()", self.html)
        self.assertIn("eyeMaximizeBtn.addEventListener('click', toggleEyeMaximize);", self.html)

    def test_maximize_controls_both_height_and_width(self):
        fn = self.html[self.html.index("function toggleEyeMaximize()"):self.html.index("if (eyeMaximizeBtn)")]
        self.assertIn("applyPct(MIN_PCT);", fn)  # collapses Toolbox height
        self.assertIn("window.ArchioskRightColumnWidth.maxForMaximize()", fn)  # expands column width

    def test_restore_reverts_both_dimensions_exactly(self):
        fn = self.html[self.html.index("function toggleEyeMaximize()"):self.html.index("if (eyeMaximizeBtn)")]
        self.assertIn("applyPct(preMaximizePct != null ? preMaximizePct : DEFAULT_PCT);", fn)
        self.assertIn("preMaximizeWidth != null ? preMaximizeWidth : window.ArchioskRightColumnWidth.DEFAULT_WIDTH", fn)

    def test_maximized_width_is_never_persisted_no_trap_on_reload(self):
        fn = self.html[self.html.index("function toggleEyeMaximize()"):self.html.index("if (eyeMaximizeBtn)")]
        self.assertIn("window.ArchioskRightColumnWidth.apply(window.ArchioskRightColumnWidth.maxForMaximize(), false, true);", fn)

    def test_restore_eye_button_provides_a_clear_way_out(self):
        self.assertIn("eyeMaximizeBtn.textContent = 'Restore Eye';", self.html)
        self.assertIn("eyeMaximizeBtn.setAttribute('aria-label', 'Restore Eye');", self.html)

    def test_conflicting_toolbox_maximize_is_reset_first(self):
        fn = self.html[self.html.index("function toggleEyeMaximize()"):self.html.index("if (eyeMaximizeBtn)")]
        self.assertIn("if (maximizeBtn && maximizeBtn.getAttribute('aria-pressed') === 'true')", fn)


class ResponsiveCanvasMarkupTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_canvas_and_controls_render_hidden_by_default(self):
        idx = self.html.index('id="eye-canvas"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn("hidden", tag)

    def test_all_required_view_controls_present(self):
        for control_id in (
            "eye-canvas-zoom-out", "eye-canvas-zoom-in", "eye-canvas-zoom-level",
            "eye-canvas-fit", "eye-canvas-actual", "eye-canvas-reset",
            "eye-canvas-remove", "eye-canvas-viewport", "eye-canvas-image",
        ):
            self.assertIn(f'id="{control_id}"', self.html, control_id)

    def test_canvas_stays_inside_the_same_drop_paste_zone(self):
        # So dropping/pasting a NEW image while one is already shown
        # replaces it, rather than needing a second drop zone.
        drop_idx = self.html.index('id="eye-drop-target"')
        canvas_idx = self.html.index('id="eye-canvas"')
        viewport_idx = self.html.index('id="eye-canvas-viewport"')
        self.assertLess(drop_idx, canvas_idx)
        self.assertLess(canvas_idx, viewport_idx)

    def test_viewport_is_keyboard_focusable_for_wheel_zoom_when_focused(self):
        idx = self.html.index('id="eye-canvas-viewport"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn('tabindex="0"', tag)


class ResponsiveCanvasCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_canvas_fills_available_space_not_a_small_thumbnail(self):
        body = _rule_body(self.css, ".eye-canvas")
        self.assertIn("align-self: stretch", body)
        self.assertIn("flex: 1 1 auto", body)

    def test_viewport_uses_native_scroll_for_panning(self):
        body = _rule_body(self.css, ".eye-canvas-viewport")
        self.assertIn("overflow: auto", body)

    def test_image_has_no_percentage_based_max_size_that_would_distort(self):
        # The old fixed-thumbnail approach used max-width/max-height
        # percentages + object-fit; the real canvas sets explicit pixel
        # width/height from JS instead (scale * natural dimensions), so
        # the CSS rule itself should carry no competing sizing rules.
        body = _rule_body(self.css, ".eye-canvas-image")
        self.assertNotIn("max-width", body)
        self.assertNotIn("object-fit", body)

    def test_no_opacity_used_anywhere_in_canvas_rules(self):
        for selector in (".eye-canvas", ".eye-canvas-toolbar", ".eye-canvas-btn", ".eye-canvas-viewport", ".eye-canvas-image"):
            body = _rule_body(self.css, selector)
            self.assertNotIn("opacity", body, selector)

    def test_canvas_viewport_background_is_a_theme_token(self):
        body = _rule_body(self.css, ".eye-canvas-viewport")
        self.assertIn("var(--surface-primary)", body)


class EyePaneJsCanvasTests(unittest.TestCase):
    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")
        self.code_only = self.js[self.js.index("*/") + 2:]

    def test_fit_zoom_actual_reset_functions_exist(self):
        for fn in ("function computeFitScale(", "function setFit(", "function setActualSize(", "function zoomBy(", "function applyScale("):
            self.assertIn(fn, self.js)

    def test_fit_preserves_aspect_ratio_via_min_of_both_axes(self):
        fn_body = self.js[self.js.index("function computeFitScale("):self.js.index("function centerScroll(")]
        self.assertIn("Math.min(viewport.clientWidth / naturalWidth, viewport.clientHeight / naturalHeight)", fn_body)

    def test_scale_is_clamped_within_practical_bounds(self):
        self.assertIn("var MIN_SCALE = 0.05;", self.js)
        self.assertIn("var MAX_SCALE = 8;", self.js)
        apply_scale_fn = self.js[self.js.index("function applyScale("):self.js.index("function setFit(")]
        self.assertIn("Math.max(MIN_SCALE, Math.min(MAX_SCALE, scale))", apply_scale_fn)

    def test_image_dimensions_set_from_natural_size_times_scale_no_distortion(self):
        apply_scale_fn = self.js[self.js.index("function applyScale("):self.js.index("function setFit(")]
        self.assertIn("naturalWidth * currentScale", apply_scale_fn)
        self.assertIn("naturalHeight * currentScale", apply_scale_fn)

    def test_wheel_zoom_only_when_viewport_focused(self):
        wheel_section = self.js[self.js.index("addEventListener('wheel'"):]
        self.assertIn("document.activeElement !== viewport", wheel_section)

    def test_resize_observer_recalculates_fit_but_only_in_fit_mode(self):
        fn_body = self.js[self.js.index("function watchResize("):self.js.index("function showCanvas(")]
        self.assertIn("ResizeObserver", fn_body)
        self.assertIn("if (mode === 'fit') applyScale(computeFitScale());", fn_body)

    def test_manual_zoom_switches_mode_so_resize_does_not_override_it(self):
        zoom_by_fn = self.js[self.js.index("function zoomBy("):self.js.index("function watchResize(")]
        self.assertIn("mode = 'manual';", zoom_by_fn)
        actual_size_fn = self.js[self.js.index("function setActualSize("):self.js.index("function zoomBy(")]
        self.assertIn("mode = 'manual';", actual_size_fn)

    def test_reset_and_fit_both_return_to_fit_mode(self):
        self.assertIn("if (fitBtn) fitBtn.addEventListener('click', setFit);", self.js)
        # CLAUDE-MM5: Reset now also clears the new view-only rotate/mirror
        # state (Section 4/11) alongside the original fit-mode reset - both
        # still happen on the SAME click, just via a small wrapper instead
        # of setFit directly.
        reset_wiring = self.js[self.js.index("if (resetBtn)"):self.js.index("if (rotateBtn)")]
        self.assertIn("setFit();", reset_wiring)
        self.assertIn("resetOrientation();", reset_wiring)

    def test_remove_control_clears_canvas_state_and_returns_to_empty(self):
        clear_fn = self.js[self.js.index("function clearPreview("):self.js.index("function handleFile(")]
        self.assertIn("canvas.hidden = true;", clear_fn)
        self.assertIn("emptyState.hidden = false;", clear_fn)

    def test_preview_is_client_side_only_until_the_reviewer_explicitly_saves(self):
        # CLAUDE-MM5 Section 7: "Save to project" is now a real, intended
        # network action - the EYE1-era "never sent anywhere" invariant is
        # narrowed to its real, still-true form: PASTING/DROPPING an image
        # (handleFile - reading it via FileReader into an in-memory data:
        # URL) never itself triggers a network call. fetch() exists in
        # this file now, but only inside saveToProject, reached solely by
        # an explicit click on #eye-save-btn.
        self.assertNotIn("XMLHttpRequest", self.code_only)
        self.assertIn("FileReader", self.code_only)
        handle_file_fn = self.js[self.js.index("function handleFile("):self.js.index("dropTarget.addEventListener('dragover'")]
        self.assertNotIn("fetch(", handle_file_fn)
        save_fn = self.js[self.js.index("function saveToProject("):self.js.index("// -------- Zoom / fit / pan")]
        self.assertIn("fetch(", save_fn)

    def test_non_image_input_still_shows_a_real_error(self):
        self.assertIn("Only images are supported here.", self.js)
        self.assertIn("Clipboard did not contain an image.", self.js)

    def test_no_scope_creep_beyond_mm5(self):
        # CLAUDE-MM5 (2026-08-06) is the explicitly authorized "next
        # stage" this EYE1-era guard was written to prevent building
        # early - "persist"/"annotate"/"ingest" are now legitimately
        # present (Save to project, marker annotations, eye-capture
        # registration). The boundary this test protects is narrowed to
        # what MM5's OWN governing prompt still defers (Section 24):
        # chat/terminal attachment and any external AI call remain
        # genuinely out of scope.
        for forbidden in ("chat-attach", "terminal-attach", "anthropic"):
            self.assertNotIn(forbidden.lower(), self.code_only.lower(), forbidden)


if __name__ == "__main__":
    unittest.main()
