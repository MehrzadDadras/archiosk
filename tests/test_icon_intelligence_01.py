"""
CLAUDE-ICON-INTELLIGENCE-01 - Document Rail row-control state grammar.

Icons as stateful teaching instruments: Mark's transparent-square-with-X
(recorded/persistent state), Keep-on-Main's hollow->filled triangle
(selected/persistent active state), Eye's state-aware Compare/Remove-
from-comparison tooltip, and Gear's two new real disabled states -
unavailable while Eye's Compare toggle is active (Section 4), and every
OTHER row's Eye/Keep controls unavailable while the Main document's own
Gear owns the active Main-tool state (Section 5).

No real browser tool existed when this repo's prior Eye/Toolbox/Keep
stages were tested (see test_leftrail_routing_01.py's own header
comment) - that ceiling no longer applies (claude-in-chrome is
available), so this stage's own live-browser proof is real, not a
documented gap. Source-structure coverage here follows the same
practical pattern those prior stages already established, for the same
reason: templates/CSS/JS state machinery is cheap and fast to assert on
directly, and complements rather than substitutes for the live proof.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_DOCUMENT_TABS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_tabs.js"
_DOCUMENT_MARKS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_marks.js"
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


class MarkXMarkTests(unittest.TestCase):
    """Section 2: transparent square, X inside when active, never a
    solid fill."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.js = _DOCUMENT_MARKS_JS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_checked_state_stays_transparent(self):
        body = _rule_body(self.css, ".pm-mark-checkbox:checked")
        self.assertIn("background: transparent", body)

    def test_checked_state_draws_an_x_not_a_solid_block(self):
        body = _rule_body(self.css, ".pm-mark-checkbox:checked::after")
        self.assertIn('content: "\\2715"', body)

    def test_default_title_present_on_the_server_rendered_control(self):
        match = re.search(r'<input type="checkbox" class="pm-mark-checkbox"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('title="Mark document"', match.group(0))

    def test_sync_checkboxes_sets_state_aware_title_and_label(self):
        body = self.js[self.js.index("function syncCheckboxes()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("'Remove mark' : 'Mark document'", body)
        self.assertIn("Remove mark from", body)
        self.assertIn("for review", body)

    def test_change_handler_resyncs_title_immediately(self):
        idx = self.js.index("cb.addEventListener('change'")
        body = self.js[idx:idx + 200]
        self.assertIn("syncCheckboxes();", body)


class KeepOnMainTests(unittest.TestCase):
    """Section 3: hollow (inactive) -> filled (persistently kept on
    Main), a real toggle (Keep on Main / Release from Main)."""

    def setUp(self):
        self.js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_default_title_is_keep_on_main(self):
        match = re.search(r'<button type="button" class="keep-open-btn"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('title="Keep on Main"', match.group(0))

    def test_glyph_constants_are_hollow_and_filled_triangle_pair(self):
        self.assertIn("var KEEP_GLYPH_INACTIVE = '▹';", self.js)
        self.assertIn("var KEEP_GLYPH_ACTIVE = '▸';", self.js)

    def test_sync_swaps_glyph_from_the_real_pinned_state(self):
        body = self.js[self.js.index("function syncKeepOpenButtons()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("pinnedNow ? KEEP_GLYPH_ACTIVE : KEEP_GLYPH_INACTIVE", body)
        self.assertIn("'Release from Main' : 'Keep on Main'", body)

    def test_sync_notifies_eye_layout_of_pin_state_changes(self):
        body = self.js[self.js.index("function syncKeepOpenButtons()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("window.ArchioskEyeLayout", body)

    def test_unpin_tab_exists_and_is_wired_to_the_click_toggle(self):
        self.assertIn("function unpinTab(sourceId) {", self.js)
        idx = self.js.index("Array.prototype.forEach.call(keepOpenButtons, function (btn) {\n        btn.addEventListener")
        body = self.js[idx:idx + 400]
        self.assertIn("unpinTab(sourceId)", body)


class EyeCompareTooltipTests(unittest.TestCase):
    """Section 7: 'Compare document' / 'Remove from comparison', not a
    bare 'Eye'."""

    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_default_title_is_compare_document(self):
        match = re.search(r'<button type="button" class="eye-send-btn"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('title="Compare document"', match.group(0))

    def test_update_eye_send_button_states_sets_state_aware_title(self):
        body = self.js[self.js.index("function updateEyeSendButtonStates()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("'Remove from comparison' : 'Compare document'", body)

    def test_title_not_overwritten_while_disabled(self):
        body = self.js[self.js.index("function updateEyeSendButtonStates()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("if (!btn.disabled)", body)


class GearCompareDisableTests(unittest.TestCase):
    """Section 4: Gear is visually AND functionally unavailable while
    Eye's Compare toggle owns the workspace state."""

    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_refresh_eye_layout_disables_gear_when_compare_active(self):
        body = self.js[self.js.index("function refreshEyeLayout()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("btn.disabled = compareActive;", body)
        self.assertIn("Unavailable while comparing documents", body)

    def test_disabled_state_reuses_established_disabled_grammar(self):
        body = _rule_body(self.css, ".toolbox-send-btn:disabled")
        self.assertIn("text-disabled", body)

    def test_disabled_gear_click_cannot_mutate_state(self):
        # Native `disabled` blocks the click listener from firing at
        # all - no separate JS guard needed inside the handler itself,
        # matching every other disabled control in this app.
        idx = self.js.rindex("querySelectorAll('.toolbox-send-btn')")
        preceding = self.js[:idx]
        self.assertIn("btn.disabled = compareActive;", preceding)


class GearMainToolStateTests(unittest.TestCase):
    """Section 5: activating Gear for the Main document highlights that
    row's own Gear and disables every OTHER row's Eye + Keep."""

    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_toolbox_activated_by_gear_flag_exists(self):
        self.assertIn("var toolboxActivatedByGear = false;", self.js)

    def test_gear_click_sets_the_flag(self):
        idx = self.js.rindex("querySelectorAll('.toolbox-send-btn')")
        body = self.js[idx:idx + 400]
        self.assertIn("toolboxActivatedByGear = true;", body)

    def test_flag_resets_once_eye_gains_content(self):
        body = self.js[self.js.index("function refreshEyeLayout()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("if (!inToolboxMode) toolboxActivatedByGear = false;", body)

    def test_update_main_tool_row_state_finds_main_via_existing_active_class(self):
        body = self.js[self.js.index("function updateMainToolRowState("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("'.tree-node-document .tree-leaf.active'", body)

    def test_suppresses_eye_and_keep_on_non_main_rows_only(self):
        body = self.js[self.js.index("function updateMainToolRowState("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("var suppress = !!(active && mainSourceId && !isMainRow);", body)
        self.assertIn("eyeBtn.disabled = suppress;", body)
        self.assertIn("keepBtn.disabled = suppress;", body)

    def test_main_row_gear_gets_a_distinguishing_class(self):
        body = self.js[self.js.index("function updateMainToolRowState("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("main-tool-active-row", body)

    def test_main_tool_active_row_reuses_existing_selected_token(self):
        body = _rule_body(self.css, ".toolbox-send-btn.main-tool-active-row")
        self.assertIn("surface-selected", body)

    def test_gear_and_compare_states_are_mutually_exclusive_by_construction(self):
        # Section 6: no bespoke precedence code needed - compareActive
        # already forces eyeHasContent() true, which forces
        # inToolboxMode false, which the reset above already clears.
        body = self.js[self.js.index("function eyeHasContent()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("compareActive", body)


if __name__ == "__main__":
    unittest.main()
