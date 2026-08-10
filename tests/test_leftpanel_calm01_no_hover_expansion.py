"""
CLAUDE-LEFTPANEL-CALM-01 - Remove Hover Expansion and Reveal Scrollbar
Only on Panel Hover.

Root cause (found by reading templates/base.html's own recursive Lists-
hierarchy script, not guessed): a real Product Owner report named the
left panel ("Project Territory") specifically as "too agitated" - every
[data-tree-parent] branch had `node.addEventListener('mouseenter', ...)`
/ `mouseleave` handlers that opened/closed its own `.tree-children`
purely from the mouse passing over it, independent of any click. Removed
outright - structure now changes ONLY via the toggle's own real <button>
click (which already fires on keyboard Enter/Space too, for free, since
it's a real, focusable, native control - no separate keyboard-activation
code was ever needed for that).

This file cannot execute real mouse/keyboard events (no browser runtime
in this suite) - coverage here is JS/CSS source inspection, the same
discipline this codebase already uses for this class of client-only fix
(see e.g. tests/test_p40vw7b_vestibule_and_attention.py's own
AttentionJsSourceTests). Live behavior was verified separately, in a
real browser, against :5000 (see this stage's own closing report).

Run via:

    python -m unittest tests.test_leftpanel_calm01_no_hover_expansion -v
"""
from __future__ import annotations

from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


class NoHoverDrivenStructureChangeTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_tree_node_no_longer_listens_for_mouseenter_or_mouseleave(self):
        """The exact root cause: hover alone must never open/expand/reveal
        a folder or subfolder - these two listeners were the entire
        mechanism that did so, and are removed, not merely dampened."""
        self.assertNotIn("node.addEventListener('mouseenter'", self.html)
        self.assertNotIn("node.addEventListener('mouseleave'", self.html)

    def test_no_mouseenter_or_mouseover_anywhere_near_the_tree_script(self):
        # Broader guard than the exact-string check above - anchored to
        # the recursive Lists hierarchy's own script block specifically
        # (identified by its real, load-bearing data-tree-root guard), so
        # a future edit that renames the listener target variable still
        # can't quietly reintroduce hover-driven disclosure here.
        start = self.html.index("var root = document.querySelector('[data-tree-root]');")
        end = self.html.index("})();", start)
        tree_script = self.html[start:end]
        self.assertNotIn("mouseenter", tree_script)
        self.assertNotIn("mouseover", tree_script)

    def test_expand_collapse_still_reachable_via_a_real_click_only(self):
        # setOpen (the one function that actually mutates data-tree-open)
        # must still be called from the toggle's click handler - the fix
        # removes ONE trigger (hover), not the mechanism itself.
        self.assertIn("toggle.addEventListener('click', function () {", self.html)
        self.assertIn("setOpen(pinned);", self.html)

    def test_tree_toggle_is_a_real_button_so_keyboard_activation_is_native(self):
        """"Keyboard Enter/Space -> deliberate activation" is satisfied by
        construction, not by a separate keydown handler this stage would
        otherwise have to add: every [data-tree-parent] control is a real
        <button type="button">, which already fires 'click' for both
        Enter and Space per native HTML semantics - "keyboard focus alone
        does not activate or expand" holds precisely because focus and
        activation are different events for a real button, and this file
        never listens for focus at all."""
        idx = 0
        found_any = False
        while True:
            idx = self.html.find("data-tree-parent", idx)
            if idx == -1:
                break
            found_any = True
            tag_start = self.html.rindex("<", 0, idx)
            tag = self.html[tag_start:self.html.index(">", idx)]
            self.assertTrue(tag.startswith("<button"), tag)
            idx += 1
        self.assertTrue(found_any, "no [data-tree-parent] elements found at all")

    def test_no_focus_driven_activation_in_the_tree_script(self):
        start = self.html.index("var root = document.querySelector('[data-tree-root]');")
        end = self.html.index("})();", start)
        tree_script = self.html[start:end]
        self.assertNotIn("addEventListener('focus'", tree_script)
        self.assertNotIn("addEventListener('focusin'", tree_script)

    def test_leaf_items_are_plain_links_never_activated_by_hover(self):
        # Leaves navigate via ordinary <a href> - there is no separate
        # "select on hover" mechanism for items either (never was, and
        # this stage's own audit confirms nothing added one). The tree
        # script's only leaf-aware code is isDescendantActive's own
        # read-only .tree-leaf.active lookup (used to decide whether
        # collapsing a parent should clear Display) - it never adds a
        # listener to a leaf itself.
        start = self.html.index("var root = document.querySelector('[data-tree-root]');")
        end = self.html.index("})();", start)
        tree_script = self.html[start:end]
        self.assertNotIn("tree-leaf'", tree_script)
        self.assertIn(".tree-leaf.active", tree_script)
        self.assertIn("Leaves (plain <a>) always just navigate normally", self.html)


class LeftPanelScrollbarHoverOnlyTests(unittest.TestCase):
    """Server-rendered/CSS half of the fix - see
    tests/test_p40eye1_scrollbar_theming.py's own
    LeftPanelScrollbarHoverRevealTests for the full, detailed CSS-rule
    assertions this class deliberately does not duplicate; these are the
    higher-level "no layout shift" checks.

    CLAUDE-PANEL-CALM-02: the Product Owner confirmed this fix and asked
    for the identical treatment on every other panel - .lists-pane is no
    longer a special case split out from the rest (see
    tests/test_p40eye1_scrollbar_theming.py's own
    AllPanelsScrollbarHoverRevealTests, which supersedes what used to be
    "every OTHER container is unaffected" here). What's still specific to
    THIS panel is only its overflow mechanics and gutter width, below."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_lists_pane_overflow_mechanics_unchanged(self):
        # The actual scroll/overflow behavior (mouse wheel, touchpad,
        # keyboard, and any assistive-tech scrolling all go through the
        # browser's own native overflow handling) must be completely
        # untouched - only scrollbar PAINTING changes.
        idx = self.css.index(".lists-pane {")
        body = self.css[idx:self.css.index("}", idx)]
        self.assertIn("overflow-y: auto", body)

    def test_scrollbar_gutter_width_reserved_unconditionally_no_layout_shift(self):
        # width/height stay in the SAME always-applied rule regardless of
        # hover state - nothing about the reveal is conditional on a
        # dimension, only on a color, which is what guarantees no layout
        # shift when it fades in or out. .lists-pane is now part of the
        # shared combined-selector width/height rule (CLAUDE-PANEL-CALM-02
        # merged it back in) rather than having its own standalone one.
        idx = self.css.index(".lists-pane::-webkit-scrollbar,")
        full_rule = self.css[idx:self.css.index("}", idx)]
        self.assertIn("width: 10px", full_rule)
        self.assertNotIn("display: none", full_rule)


if __name__ == "__main__":
    unittest.main()
