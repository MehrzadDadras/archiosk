"""
CLAUDE-MOBILE-MENU-REPAIR-01 - the phone menu stops being a transplant.

Product Owner, live iPhone report: the File menu "occupies most of the
viewport", "leaves an unusable strip of the underlying Composer visible",
"exposes the desktop hierarchy", "disabled or low-value desktop commands consume
scarce mobile space", and "the interaction is not composed for thumb use".

WHAT THE INVESTIGATION FOUND, AND WHAT IT DID NOT

A mobile drawer ALREADY existed and worked: .workspace-menubar is hidden on
mobile and reopens as a fixed left drawer, with a toggle, Escape, close-on-choose
and outside-tap dismiss all wired in workspace_trays.js. Its own CSS comment
cites an earlier Product Owner iPhone screenshot, so this surface had been
repaired once before.

So the defect was never "no mobile treatment". It was that the drawer CONTAINED
the desktop menu unchanged - eight menus, sixty-one items, thirteen of them
disabled, at desktop row height.

These tests protect three bounded corrections and, just as importantly, the
boundary around them: desktop is untouched, no capability is removed, and the
open product question - which menus belong on a phone at all - is deliberately
NOT answered here.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CSS = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
_MENU = (_REPO_ROOT / "templates" / "_app_menu.html").read_text(encoding="utf-8")
_TRAYS = (_REPO_ROOT / "static" / "js" / "workspace_trays.js").read_text(encoding="utf-8")


def _mobile_block() -> str:
    """Every @media (max-width: 640px) block that carries this repair."""
    out = []
    for match in re.finditer(r"@media\s*\(max-width: 640px\)\s*\{", _CSS):
        start = match.end()
        depth, i = 1, start
        while depth and i < len(_CSS):
            depth += (_CSS[i] == "{") - (_CSS[i] == "}")
            i += 1
        out.append(_CSS[start:i])
    return "\n".join(out)


MOBILE = _mobile_block()


def _repair_region() -> str:
    """ONLY the rules this stage added.

    Slicing from the marker to the end of the concatenated mobile blocks swept
    in unrelated later rules and made three assertions test other people's CSS.
    The region ends at the last selector this repair introduced.
    """
    start = MOBILE.index("CLAUDE-MOBILE-MENU-REPAIR-01")
    last = MOBILE.index('html.mobile-nav-open .workspace-menubar-item[aria-disabled="true"]', start)
    return MOBILE[start:MOBILE.index("}", MOBILE.index("display: none", last)) + 1]


REPAIR = _repair_region()


class TheCorrectionsAreMobileOnlyTests(unittest.TestCase):
    """Desktop behaviour must be unchanged - that was the explicit boundary."""

    def test_every_new_rule_lives_inside_the_mobile_breakpoint(self):
        self.assertIn("CLAUDE-MOBILE-MENU-REPAIR-01", MOBILE)
        # And nowhere else: a stray copy outside the media query would change
        # the desktop menu, which was explicitly to be preserved.
        self.assertEqual(_CSS.count("CLAUDE-MOBILE-MENU-REPAIR-01"), 1)

    def test_every_new_rule_is_scoped_to_the_open_drawer(self):
        # html.mobile-nav-open is the drawer state. A rule scoped only to the
        # breakpoint would also apply on a phone with the drawer CLOSED.
        for selector in re.findall(r"\n    ([^\n{]*)\{", REPAIR):
            selector = selector.strip()
            if not selector or selector.startswith(("@", "/*")):
                continue
            for part in selector.split(","):
                part = part.strip()
                if part:
                    self.assertIn("mobile-nav-open", part, part)

    def test_the_desktop_panel_rule_is_untouched(self):
        # The base rule is the one NOT scoped to the drawer state.
        panels = re.findall(r"(?<!open )\.workspace-menubar-panel\s*\{[^}]*\}", _CSS)
        panel = next((re.match(r"[\s\S]*", p) for p in panels if "absolute" in p), None)
        self.assertIsNotNone(panel, "base panel rule not found")
        self.assertIn("position: absolute", panel.group(0))
        self.assertIn("min-width: 220px", panel.group(0))


class ItIsDrivenWithAThumbTests(unittest.TestCase):
    def test_menu_items_get_a_real_touch_target(self):
        rule = re.search(
            r"html\.mobile-nav-open \.workspace-menubar-item\s*\{[^}]*\}", MOBILE)
        self.assertIsNotNone(rule, "no mobile sizing for menu items")
        height = re.search(r"min-height:\s*(\d+)px", rule.group(0))
        self.assertIsNotNone(height)
        self.assertGreaterEqual(int(height.group(1)), 44)

    def test_it_reuses_the_shells_own_touch_standard(self):
        # 44px is already this codebase's target elsewhere; this is not a new
        # number invented for the menu.
        # Examples from THIS stylesheet only - the landing sound toggle lives in
        # landing.css, which this file does not read.
        for established in (".composer-attach", ".capture-review-use"):
            rule = re.search(re.escape(established) + r"[^{]*\{[^}]*\}", _CSS)
            self.assertIsNotNone(rule, established)
            self.assertIn("44px", rule.group(0), established)


class TheStripReadsAsDismissNotAsBreakageTests(unittest.TestCase):
    def test_a_scrim_covers_the_work_behind_the_drawer(self):
        rule = re.search(r"html\.mobile-nav-open body::after\s*\{[^}]*\}", MOBILE)
        self.assertIsNotNone(rule, "no backdrop behind the drawer")
        self.assertIn("position: fixed", rule.group(0))
        self.assertIn("inset: 0", rule.group(0))

    def test_the_scrim_sits_below_the_drawer(self):
        scrim = re.search(r"html\.mobile-nav-open body::after\s*\{[^}]*\}", MOBILE).group(0)
        scrim_z = int(re.search(r"z-index:\s*(\d+)", scrim).group(1))
        drawer = re.search(r"html\.mobile-nav-open \.workspace-menubar\s*\{[^}]*\}", MOBILE).group(0)
        drawer_z = int(re.search(r"z-index:\s*(\d+)", drawer).group(1))
        self.assertLess(scrim_z, drawer_z)

    def test_the_existing_dismiss_behaviour_still_works_through_it(self):
        # A pseudo-element is not an event target, so the tap lands on <body>
        # and workspace_trays.js's outside-click handler still closes the
        # drawer. The scrim reveals that behaviour; it must not replace it.
        self.assertIn("mobile-nav-open", _TRAYS)
        handler = _TRAYS[_TRAYS.index("A tap on the work behind the drawer"):]
        handler = handler[:handler.index("}\n")]
        self.assertIn("setOpen(false)", handler)

    def test_no_new_dom_node_was_introduced(self):
        for invented in ("mobile-nav-backdrop", "menu-scrim", "drawer-overlay"):
            self.assertNotIn(invented, _MENU, invented)
            self.assertNotIn(invented, _TRAYS, invented)


class UnusableItemsAreHiddenNotCapabilitiesRemovedTests(unittest.TestCase):
    def test_disabled_items_are_hidden_in_the_drawer(self):
        rule = re.search(
            r"html\.mobile-nav-open \.workspace-menubar-item-disabled[^{]*\{[^}]*\}", MOBILE)
        self.assertIsNotNone(rule)
        self.assertIn("display: none", rule.group(0))

    def test_the_aria_disabled_form_is_covered_too(self):
        # The markup uses both a class and aria-disabled; missing either would
        # leave half the noise behind.
        self.assertIn('aria-disabled="true"', REPAIR)

    def test_nothing_enabled_is_hidden(self):
        # The repair must not remove a working control. Only the disabled
        # selectors carry display:none.
        for rule in re.finditer(r"([^{}]+)\{([^}]*)\}", REPAIR):
            if "display: none" in rule.group(2):
                self.assertIn("disabled", rule.group(1))

    def test_the_markup_still_contains_every_menu_and_item(self):
        # Capability is untouched: the same eight menus and the same items are
        # still rendered, and still present on desktop.
        self.assertEqual(_MENU.count('<details class="workspace-menubar-menu"'), 8)
        self.assertGreaterEqual(_MENU.count("workspace-menubar-item"), 60)

    def test_no_menu_was_deleted_from_the_template(self):
        for menu in ("menu.file", "menu.edit", "menu.view", "menu.document",
                     "menu.tools", "menu.window", "menu.help", "menu.archiosk"):
            self.assertIn(f'data-ui-ref="{menu}"', _MENU, menu)


class TheOpenQuestionIsLeftOpenTests(unittest.TestCase):
    """Which menus belong on a phone is a product decision, not a CSS one."""

    def test_no_top_level_menu_is_hidden_on_mobile(self):
        for menu_class in ("menu.window", "menu.help", "menu.edit"):
            self.assertNotIn(menu_class, REPAIR, menu_class)

    def test_the_repair_did_not_invent_a_second_mobile_menu(self):
        for invented in ("mobile-menu", "phone-nav", "bottom-sheet-menu"):
            self.assertNotIn(invented, _CSS, invented)
            self.assertNotIn(invented, _MENU, invented)


if __name__ == "__main__":
    unittest.main()
