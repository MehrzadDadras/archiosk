"""
CLAUDE-LEFTRAIL-ROUTING-01 - Left-Rail Main / Eye / Tool Routing.

Closes the document-row interaction grammar: document name -> Main
Display (unchanged, pre-existing); Eye icon -> Eye, with active-state
indication and toggle-off on a second click of the already-active icon;
a new Tool icon beside it that switches the right side back to full
Toolbox mode without touching Main.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source structure, the same practical ceiling every
prior Eye/Toolbox stage's own tests use (see test_p40eye1_toolbox_eye_
column.py's own header comment). The live interaction (toggle-off,
replacement, Tool-icon mode switch, Main/Eye independence) was verified
directly on archiosk.com as part of this stage's own required live
proof, not re-asserted here.
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


class LeftRailMarkupTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_eye_send_btn_has_aria_pressed(self):
        match = re.search(r'<button type="button" class="eye-send-btn"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('aria-pressed="false"', match.group(0))

    def test_toolbox_send_btn_exists_beside_eye_send_btn(self):
        eye_idx = self.html.index('class="eye-send-btn"')
        toolbox_idx = self.html.index('class="toolbox-send-btn"')
        # Same row - the Tool icon comes immediately after the Eye icon,
        # before that <li> closes.
        li_close_idx = self.html.index("</li>", eye_idx)
        self.assertLess(eye_idx, toolbox_idx)
        self.assertLess(toolbox_idx, li_close_idx)

    def test_toolbox_send_btn_is_not_a_literal_text_glyph(self):
        match = re.search(r'<button type="button" class="toolbox-send-btn"[^>]*>([^<]*)</button>', self.html)
        self.assertIsNotNone(match)
        glyph = match.group(1).strip()
        self.assertNotEqual(glyph, "T")
        self.assertIn("&#9881;", match.group(0))  # gear glyph, U+2699

    def test_toolbox_send_btn_not_source_scoped(self):
        # Part 3: "not another document destination" - identical action on
        # every row, so it must not carry a per-document data-source-id.
        match = re.search(r'<button type="button" class="toolbox-send-btn"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertNotIn("data-source-id", match.group(0))


class EyePaneRoutingTests(unittest.TestCase):
    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")

    def test_tracks_current_eye_source_id(self):
        self.assertIn("var currentEyeSourceId = null;", self.js)

    def test_update_eye_send_button_states_matches_active_document(self):
        body = self.js[self.js.index("function updateEyeSendButtonStates()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("btn.getAttribute('data-source-id') === currentEyeSourceId", body)
        self.assertIn("setAttribute('aria-pressed'", body)

    def test_eye_send_btn_click_toggles_off_when_already_active(self):
        idx = self.js.rindex("querySelectorAll('.eye-send-btn')")
        body = self.js[idx:idx + 900]
        self.assertIn("if (currentEyeSourceId && currentEyeSourceId === sourceId) {", body)
        self.assertIn("clearDocumentView();", body)

    def test_load_document_sets_current_eye_source_id(self):
        body = self.js[self.js.index("function loadDocument("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("currentEyeSourceId = sourceId;", body)
        self.assertIn("updateEyeSendButtonStates();", body)

    def test_clear_document_view_resets_current_eye_source_id(self):
        body = self.js[self.js.index("function clearDocumentView()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("currentEyeSourceId = null;", body)
        self.assertIn("updateEyeSendButtonStates();", body)

    def test_toolbox_send_btn_clears_eye_and_compare(self):
        idx = self.js.rindex("querySelectorAll('.toolbox-send-btn')")
        body = self.js[idx:idx + 500]
        self.assertIn("clearPreview();", body)
        self.assertIn("clearDocumentView();", body)
        self.assertIn("setCompareActive(false);", body)

    def test_refresh_eye_layout_syncs_toolbox_send_btn_aria_pressed(self):
        body = self.js[self.js.index("function refreshEyeLayout()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("toolbox-send-btn", body)
        self.assertIn("btn.setAttribute('aria-pressed', String(inToolboxMode));", body)


class LeftRailCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_eye_send_btn_active_state_is_restrained(self):
        body = _rule_body(self.css, '.eye-send-btn[aria-pressed="true"]')
        self.assertIn("machine-blue", body)
        self.assertNotIn("border", body.lower())
        self.assertNotIn("box-shadow", body.lower())

    def test_toolbox_send_btn_matches_eye_send_btn_footprint(self):
        eye_body = _rule_body(self.css, ".eye-send-btn")
        toolbox_body = _rule_body(self.css, ".toolbox-send-btn")
        for prop in ("width: 22px", "height: 22px", "border-radius: 4px"):
            self.assertIn(prop, eye_body)
            self.assertIn(prop, toolbox_body)

    def test_toolbox_send_btn_active_state_is_restrained(self):
        body = _rule_body(self.css, '.toolbox-send-btn[aria-pressed="true"]')
        self.assertIn("machine-blue", body)
        self.assertNotIn("border", body.lower())
        self.assertNotIn("box-shadow", body.lower())


if __name__ == "__main__":
    unittest.main()
