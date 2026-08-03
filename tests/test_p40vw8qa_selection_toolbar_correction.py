"""
CLAUDE-P40-VW8-QA - Selection toolbar correction.

Product-owner report: the text-selection action toolbar was
"permanently visible," horizontal, unreliably connected to the
selection, and appeared to have inactive actions.

Audit finding: the JS (selection tracking, text-quote anchor
computation, viewport-clamped positioning via live `offsetWidth`/
`offsetHeight`, per-action availability toggling, Escape/outside-click/
selection-clear close handling, and all 6 actions - Add Tag/Make
Task/Highlight/Important/Question/Copy - genuinely reaching real
dialogs or `postForm(tagForm.action, ...)`/clipboard calls) was already
correct. The one real defect was CSS: `.conv-selection-toolbar` had no
`[hidden]` override, so its own `display: flex` (equal specificity,
declared later in the cascade) beat the `hidden` attribute the JS was
correctly setting - the exact same bug CLASS as the R3 tokens.css
comment-boundary regression, applied to `[hidden]` instead of a CSS
comment.

Fixed with two rule changes: `.conv-selection-toolbar[hidden] {
display: none; }`, and `flex-direction: column` (one action per row,
per the product-owner's explicit vertical-layout request), plus
`text-align: left` on `.conv-selection-btn` so a column of buttons
reads left-aligned rather than centered.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_UI_MAP_PATH = _REPO_ROOT / "UI_REFERENCE_MAP.md"


class SelectionToolbarCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _rule_body(self, selector: str) -> str:
        idx = self.css.index(selector)
        start = self.css.index("{", idx)
        end = self.css.index("}", start)
        return self.css[start:end]

    def test_hidden_attribute_override_exists(self):
        # The root-cause fix: without this, [hidden] never actually
        # hides the toolbar because the class's own display:flex wins.
        self.assertIn(".conv-selection-toolbar[hidden]", self.css)
        body = self._rule_body(".conv-selection-toolbar[hidden]")
        self.assertIn("display: none", body)

    def test_hidden_override_declared_after_the_base_rule(self):
        # Cascade order matters here (equal specificity) - the
        # override must come AFTER .conv-selection-toolbar's own rule.
        base_idx = self.css.index(".conv-selection-toolbar {")
        hidden_idx = self.css.index(".conv-selection-toolbar[hidden]")
        self.assertGreater(hidden_idx, base_idx)

    def test_toolbar_layout_is_vertical(self):
        body = self._rule_body(".conv-selection-toolbar {")
        self.assertIn("flex-direction: column", body)

    def test_toolbar_still_uses_flex_display_when_visible(self):
        body = self._rule_body(".conv-selection-toolbar {")
        self.assertIn("display: flex", body)

    def test_selection_buttons_left_aligned_for_column_layout(self):
        body = self._rule_body(".conv-selection-btn {")
        self.assertIn("text-align: left", body)

    def test_no_hardcoded_colors_introduced(self):
        body = self._rule_body(".conv-selection-toolbar {")
        self.assertNotIn("#", body)
        self.assertRegex(body, r"var\(--surface-primary\)|surface-primary")


class SelectionToolbarHtmlDefaultStateTests(unittest.TestCase):
    def setUp(self):
        self.html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")

    def test_toolbar_hidden_by_default_in_markup(self):
        idx = self.html.index('id="conv-selection-toolbar"')
        tag_start = self.html.rindex("<div", 0, idx)
        tag_end = self.html.index(">", idx)
        tag = self.html[tag_start:tag_end]
        self.assertIn("hidden", tag)

    def test_all_six_actions_present_with_retained_ui_refs(self):
        for action in ("tag", "task", "highlight", "important", "question", "copy"):
            self.assertIn(f'data-conv-action="{action}"', self.html)
            self.assertIn(f'data-ui-ref="chat.selection-toolbar.{action}"', self.html)


class SelectionToolbarJsWiringTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_positioning_uses_live_measured_dimensions_not_hardcoded(self):
        # Confirms the vertical-layout change can't desync the
        # viewport-clamping math - it reads the toolbar's own rendered
        # size every time, whatever that size currently is.
        self.assertIn("toolbar.offsetWidth", self.js)
        self.assertIn("toolbar.offsetHeight", self.js)

    def test_positioning_clamps_within_viewport_both_axes(self):
        self.assertIn("window.innerWidth", self.js)
        self.assertIn("window.innerHeight", self.js)

    def test_hides_on_escape(self):
        self.assertRegex(self.js, r"e\.key\s*!==?\s*'Escape'[\s\S]{0,400}hideToolbar\(\)")

    def test_hides_when_selection_collapses_or_is_empty(self):
        self.assertIn("sel.isCollapsed", self.js)
        self.assertIn("!text || !text.trim()", self.js)

    def test_hides_when_active_element_is_an_editable_control(self):
        # Selecting inside the composer input/textarea must not summon
        # the toolbar.
        self.assertRegex(
            self.js,
            r"\['INPUT',\s*'TEXTAREA',\s*'SELECT',\s*'BUTTON'\]",
        )

    def test_requires_selection_within_conversation_dock(self):
        self.assertIn("withinConversationDock", self.js)

    def test_highlight_important_question_post_to_real_tag_route_not_decorative(self):
        # These three one-click actions must reach the same backend
        # tag-creation endpoint as the Add Tag dialog - no separate,
        # duplicate system.
        match = re.search(
            r"postForm\(tagForm\.action,\s*Object\.assign\(\{\s*tag_id:\s*builtIn\.id\s*\}",
            self.js,
        )
        self.assertIsNotNone(match)

    def test_copy_uses_real_clipboard_api_with_fallback(self):
        self.assertIn("navigator.clipboard.writeText", self.js)
        self.assertIn("execCommand('copy')", self.js)

    def test_tag_and_task_actions_open_real_dialogs_not_stubs(self):
        self.assertIn("openTagDialog(anchor, quote, btn)", self.js)
        self.assertIn("openTaskDialog(anchor, quote, btn)", self.js)

    def test_mousedown_preserves_selection_before_click_fires(self):
        # Without this, clicking a toolbar button would collapse the
        # selection before the action handler ever reads it.
        idx = self.js.index("toolbar.addEventListener('mousedown'")
        snippet = self.js[idx: idx + 700]
        self.assertIn("e.preventDefault()", snippet)

    def test_outside_click_closes_toolbar_when_selection_gone(self):
        self.assertIn("sel.isCollapsed || !sel.toString().trim()) hideToolbar()", self.js)

    def test_ambiguous_cross_message_selection_disables_source_dependent_actions(self):
        self.assertIn("anchor.ambiguous", self.js)
        idx = self.js.index("function applyToolbarAvailability")
        snippet = self.js[idx: idx + 500]
        self.assertIn("btn.disabled = !usable", snippet)


class SelectionToolbarUiReferenceMapTests(unittest.TestCase):
    def setUp(self):
        self.map_text = _UI_MAP_PATH.read_text(encoding="utf-8")

    def test_all_six_action_identifiers_retained_in_registry(self):
        for action in ("tag", "task", "highlight", "important", "question", "copy"):
            self.assertIn(f"chat.selection-toolbar.{action}", self.map_text)

    def test_toolbar_root_identifier_retained(self):
        self.assertIn("`chat.selection-toolbar`", self.map_text)

    def test_correction_documented_as_moved_reparented_not_a_new_reference(self):
        self.assertIn("moved/reparented", self.map_text)


class NativePopupOverlapCorrectionTests(unittest.TestCase):
    """CLAUDE-P40-VW8-QA: Archiosk's own menu must sit on the opposite
    side of the selection from where a browser/OS-owned selection popup
    (e.g. Edge's mini menu) conventionally appears, and must recompute
    its position (or hide) if the containing panel scrolls or the
    viewport resizes while a selection is held - neither existed
    before this correction."""

    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_positioning_prefers_below_the_selection_first(self):
        idx = self.js.index("function positionToolbar")
        body = self.js[idx: idx + 900]
        below_idx = body.index("rect.bottom + margin")
        above_idx = body.index("rect.top - toolbar.offsetHeight - margin")
        self.assertLess(
            below_idx, above_idx,
            "positionToolbar must compute the below-selection position "
            "before the above-selection fallback",
        )

    def test_no_contextmenu_suppression_exists_for_text_selection(self):
        # The one contextmenu listener in this file is the unrelated
        # Display-division picker - confirms right-click / native
        # context menus are never intercepted anywhere near the
        # selection toolbar, satisfying "preserve browser context
        # menus" / "do not disable right-click globally" for free,
        # because nothing here ever tried to.
        count = self.js.count("addEventListener('contextmenu'")
        self.assertEqual(count, 1)
        idx = self.js.index("addEventListener('contextmenu'")
        preceding = self.js[max(0, idx - 400):idx]
        self.assertIn("division", preceding)

    def test_scroll_and_resize_reposition_or_hide_handler_registered(self):
        self.assertIn(
            "window.addEventListener('scroll', repositionOrHideOnViewportChange, true)",
            self.js,
        )
        self.assertIn(
            "window.addEventListener('resize', repositionOrHideOnViewportChange)",
            self.js,
        )

    def test_scroll_listener_uses_capture_phase(self):
        # 'scroll' does not bubble - without capture:true a window-level
        # listener would never see a scroll on an internal panel like
        # .conversation-thread or <main>.
        idx = self.js.index("window.addEventListener('scroll', repositionOrHideOnViewportChange")
        line = self.js[idx: idx + 100]
        self.assertIn(", true)", line)

    def test_reposition_handler_hides_when_selection_gone(self):
        idx = self.js.index("function repositionOrHideOnViewportChange")
        body = self.js[idx: idx + 500]
        self.assertIn("hideToolbar()", body)

    def test_reposition_handler_reuses_live_selection_rect_not_a_cached_one(self):
        idx = self.js.index("function repositionOrHideOnViewportChange")
        body = self.js[idx: idx + 500]
        self.assertIn("sel.getRangeAt(0).getBoundingClientRect()", body)

    def test_edge_mini_menu_setting_documented_for_the_product_owner(self):
        # The one remaining lever (a native browser setting/policy) must
        # be named explicitly, since this page cannot control it.
        self.assertIn("QuickSearchShowMiniMenu", self.js)
        self.assertIn("edge://settings/appearance", self.js)

    def test_no_browser_detection_or_fake_disable_preference_introduced(self):
        lowered = self.js.lower()
        self.assertNotIn("navigator.useragent", lowered)
        self.assertNotIn("navigator.vendor", lowered)
        self.assertNotIn("disablenativeselection", lowered)
        self.assertNotIn("disablebrowserpopup", lowered)


if __name__ == "__main__":
    unittest.main()
