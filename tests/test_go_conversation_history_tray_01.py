"""CLAUDE-GO-CONVERSATION-HISTORY-TRAY-01 - conversations, under the Composer.

Product Owner: "Since the phone screen is small put the chat histories list
under the Composer in a tray."

The list already existed - it is the Toolbox's Investigations pane - but on a
phone that sits behind a tray switch and a scroll, which is the compressed-
cockpit problem this whole mobile effort exists to remove. Switching
conversations is something you do FROM a conversation, so the list belongs
where the conversation is.

What these tests mostly guard is what it must NOT become: a second navigation
model, a second place that can create or destroy things, or something that
takes the screen back from the work it was meant to give it to.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACROS = (ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
CSS_NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _dock_macro() -> str:
    start = MACROS.index("{% macro conversation_dock")
    return MACROS[start: MACROS.index("{% endmacro %}", start)]


class ItSitsUnderTheComposerTests(unittest.TestCase):
    def test_the_tray_is_inside_the_dock(self):
        self.assertIn("conversation-history-tray", _dock_macro())

    def test_it_comes_after_the_composer_form(self):
        """"Under the Composer" - above it would push the input down the
        screen, which is the opposite of what a small screen needs."""
        dock = _dock_macro()
        self.assertLess(
            dock.index("conversation-dock-composer"),
            dock.index("conversation-history-tray"),
        )

    def test_both_conversations_get_it(self):
        """An Investigation and the project conversation are both places you
        might want to switch away from."""
        self.assertEqual(WORKSPACE.count("conversations=open_visible_cases"), 2)


class ItCostsNothingWhenUnusedTests(unittest.TestCase):
    def test_it_is_closed_by_default(self):
        dock = _dock_macro()
        block = dock[dock.index("conversation-history-tray"):]
        block = block[: block.index(">")]
        self.assertNotIn("open", block)

    def test_it_is_a_native_disclosure_with_no_script(self):
        """No JavaScript, no state of its own, and it still works with
        scripting unavailable."""
        dock = _dock_macro()
        self.assertIn("<details class=\"conversation-history-tray\"", dock)
        self.assertIn("<summary", dock)
        for js in (ROOT / "static" / "js").glob("*.js"):
            with self.subTest(script=js.name):
                self.assertNotIn("conversation-history-tray", js.read_text(encoding="utf-8"))

    def test_the_list_cannot_push_the_input_off_the_screen(self):
        """The one element here allowed to grow is capped - a tray that ate
        the composer would cause the problem it was built to solve."""
        rule = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index(".conversation-history-list {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("max-height", rule)
        self.assertIn("overflow-y: auto", rule)
        self.assertIn("overscroll-behavior: contain", rule)

    def test_its_targets_are_touch_sized(self):
        for selector in (".conversation-history-summary {", ".conversation-history-item {"):
            with self.subTest(selector=selector):
                rule = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index(selector):]
                rule = rule[: rule.index("}")]
                self.assertIn("min-height: 40px", rule)


class ItIsNavigationAndNothingElseTests(unittest.TestCase):
    def test_it_reuses_the_existing_links(self):
        """Same ?case=<id> the Toolbox pane already uses - not a second
        navigation model."""
        dock = _dock_macro()
        self.assertIn("workspace.show_workspace", dock[dock.index("conversation-history-tray"):])

    def test_it_can_create_rename_or_remove_nothing(self):
        tray = _dock_macro()[_dock_macro().index("conversation-history-tray"):]
        for forbidden in ("method=\"post\"", "archive_case", "create", "delete", "<form"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, tray)

    def test_it_says_where_you_are(self):
        tray = _dock_macro()[_dock_macro().index("conversation-history-tray"):]
        self.assertIn("conversation-history-current", tray)

    def test_an_empty_list_is_stated_rather_than_left_blank(self):
        tray = _dock_macro()[_dock_macro().index("conversation-history-tray"):]
        self.assertIn("No other conversations yet.", tray)


if __name__ == "__main__":
    unittest.main()
