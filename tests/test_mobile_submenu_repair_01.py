"""
CLAUDE-MOBILE-SUBMENU-REPAIR-01 - nested menus open where a phone can show them.

Product Owner, live iPhone: "The menu on phone is not stable. Click on menu just
snap to the same page."

WHAT WAS ACTUALLY WRONG

The drawer flattened the TOP-LEVEL menus and stopped there.
`.workspace-menubar-panel` gets `position: static` inside
`html.mobile-nav-open`; `.workspace-menubar-subpanel` never did, so a nested
submenu kept its desktop flyout geometry:

    position: absolute;  left: calc(100% + 0.2rem);  min-width: 200px;

inside a drawer that is `min(86vw, 320px)` wide. On a 390px phone that opens a
200px panel starting roughly 320px from the left edge - entirely off-screen.

So tapping "Admin" appeared to do nothing. The menu was not unstable; it was
opening something the phone could never display, which is indistinguishable
from broken and worse, because the tap registered.

This matters more as of CLAUDE-DEVELOPER-MENU-01, which moved Developer Mode
into its own nested submenu - on a phone that would have been a control you
could reach and then not see.

MEASURED, NOT ASSUMED

The geometry assertions below compute the real numbers rather than trusting
that a rule exists, because "there is a mobile rule for it" was true of the
parent panels and still left the children broken.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_CSS = (Path(__file__).resolve().parent.parent / "static" / "css" / "main.css").read_text(
    encoding="utf-8")
_MENU = (Path(__file__).resolve().parent.parent / "templates" / "_app_menu.html").read_text(
    encoding="utf-8")

_PHONE_BREAKPOINT = 640
_DRAWER_MAX = 320          # width: min(86vw, 320px)
_SUBPANEL_MIN_WIDTH = 200  # .workspace-menubar-subpanel min-width


def _phone_blocks() -> str:
    out = []
    for match in re.finditer(r"@media\s*\(max-width: 640px\)\s*\{", _CSS):
        start = match.end()
        depth, i = 1, start
        while depth and i < len(_CSS):
            depth += (_CSS[i] == "{") - (_CSS[i] == "}")
            i += 1
        out.append(_CSS[start:i])
    return "\n".join(out)


PHONE = _phone_blocks()


def _strip_css_comments(css: str) -> str:
    """Declarations only.

    main.css explains its own popover idiom in prose that names
    `.workspace-layout-options/.workspace-appearance-options`. Searching the raw
    file finds that COMMENT first, walks forward to the next brace, and returns
    a completely unrelated rule - which is exactly how this helper produced a
    confident wrong answer before.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def _rule(css: str, selector: str):
    """The declaration block for a selector, including GROUPED selectors.

    The naive `selector\\s*\\{` pattern only matches a selector that is the last
    one before the brace. Once the flatten became a three-selector group, every
    lookup for the first two silently returned None and four assertions failed
    for a reason that had nothing to do with the CSS. So: find the selector,
    then walk forward to the opening brace, refusing to cross a `}` (which
    would mean the selector was in a different, earlier rule).
    """
    css = _strip_css_comments(css)
    for match in re.finditer(re.escape(selector) + r"(?![-\w])", css):
        rest = css[match.end():]
        brace = rest.find("{")
        if brace == -1:
            continue
        if "}" in rest[:brace]:
            continue
        block = rest[brace + 1:]
        end = block.find("}")
        if end != -1:
            return block[:end]
    return None


class TheDesktopGeometryGenuinelyDidNotFit(unittest.TestCase):
    """The arithmetic that made this a real defect rather than a style nit."""

    def test_the_desktop_subpanel_is_a_flyout(self):
        desktop = _rule(_CSS, ".workspace-menubar-subpanel")
        self.assertIsNotNone(desktop)
        self.assertIn("position: absolute", desktop)
        self.assertIn("left: calc(100% + 0.2rem)", desktop)

    def test_that_flyout_cannot_fit_beside_the_drawer_on_a_real_phone(self):
        # Measured against real device widths, not against the breakpoint. The
        # first version of this test compared 520 to 640 and failed, correctly:
        # between roughly 520px and the 640px breakpoint the flyout DOES fit.
        # It is on actual phones that it cannot, which is where the report came
        # from.
        needed = _DRAWER_MAX + _SUBPANEL_MIN_WIDTH  # 520
        for device, width in [("iPhone SE", 375), ("iPhone 14", 390),
                              ("iPhone 14 Pro Max", 430), ("small Android", 360)]:
            with self.subTest(device=device):
                self.assertGreater(needed, width,
                                   "the flyout fits on %s - re-check whether the "
                                   "flatten is still needed" % device)


class NestedMenusAreFlattenedInTheDrawer(unittest.TestCase):
    def test_the_submenu_container_is_no_longer_a_positioning_context(self):
        rule = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-submenu")
        self.assertIsNotNone(rule, "nested submenus are still position: relative on a phone")
        self.assertIn("position: static", rule)

    def test_the_subpanel_is_flattened_into_the_drawer(self):
        rule = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-subpanel")
        self.assertIsNotNone(rule, "the nested panel still uses desktop flyout geometry")
        self.assertIn("position: static", rule)

    def test_the_offsets_that_pushed_it_off_screen_are_cleared(self):
        # position: static alone leaves top/left inert but present; clearing
        # them says what is meant and survives a later position change.
        rule = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-subpanel")
        self.assertIn("left: auto", rule)
        self.assertIn("top: auto", rule)

    def test_the_minimum_width_no_longer_forces_it_wider_than_the_drawer(self):
        rule = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-subpanel")
        self.assertIn("min-width: 0", rule)

    def test_nesting_stays_legible_once_flattened(self):
        # A flattened submenu that looks identical to its parent list is a
        # different kind of confusing.
        rule = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-subpanel")
        self.assertIn("padding-left", rule)

    def test_it_is_treated_the_same_way_as_its_parent(self):
        # The parents were already flattened; the children were simply missed.
        parent = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-panel")
        child = _rule(PHONE, "html.mobile-nav-open .workspace-menubar-subpanel")
        for shared in ["position: static", "min-width: 0", "box-shadow: none", "border: none"]:
            with self.subTest(declaration=shared):
                self.assertIn(shared, parent)
                self.assertIn(shared, child)


class DesktopIsUntouched(unittest.TestCase):
    def test_the_flatten_lives_only_in_the_phone_breakpoint(self):
        selector = "html.mobile-nav-open .workspace-menubar-subpanel"
        self.assertEqual(_CSS.count(selector), PHONE.count(selector))
        self.assertEqual(PHONE.count(selector), 1)

    def test_the_desktop_flyout_rule_still_exists(self):
        # Flattening the drawer must not have removed the geometry that makes
        # nested menus work with a cursor.
        outside_count = _CSS.count(".workspace-menubar-subpanel {")
        self.assertGreaterEqual(outside_count, 1)


class EveryNestedMenuBenefits(unittest.TestCase):
    """Fixed for the construct, not for one menu."""

    def test_both_nested_submenus_use_the_repaired_classes(self):
        submenus = re.findall(r'<details class="workspace-menubar-submenu" data-ui-ref="([^"]+)"', _MENU)
        self.assertIn("menu.archiosk.admin", submenus)
        self.assertIn("menu.archiosk.developer", submenus)

    # Every class a nested submenu uses for its panel. Appearance and Display
    # Layout predate the shared .workspace-menubar-subpanel and kept their own.
    _PANEL_CLASSES = ("workspace-menubar-subpanel", "workspace-appearance-options",
                      "workspace-layout-options")

    def test_every_nested_submenu_has_a_panel_the_flatten_reaches(self):
        # This is the assertion that found the real second defect. Counting the
        # exact string `class="workspace-menubar-subpanel"` said 3 of 4; being
        # class-aware said 4 of 6, and the missing two were Appearance and
        # Display Layout - absolutely positioned, no mobile reset, and NOT
        # covered by a flatten written for the shared class alone.
        opens = len(re.findall(r'<details[^>]*class="[^"]*\bworkspace-menubar-submenu\b', _MENU))
        panels = sum(
            len(re.findall(r'<div[^>]*class="[^"]*\b%s\b' % cls, _MENU))
            for cls in self._PANEL_CLASSES)
        self.assertEqual(opens, panels,
                         "a nested submenu uses a panel class the mobile flatten "
                         "does not cover - add it to the rule and to _PANEL_CLASSES")
        self.assertGreaterEqual(opens, 6)

    def test_the_flatten_covers_every_panel_class(self):
        rule_block = PHONE[PHONE.index("html.mobile-nav-open .workspace-menubar-subpanel"):]
        rule_block = rule_block[:rule_block.index("}") + 1]
        for cls in self._PANEL_CLASSES:
            with self.subTest(panel_class=cls):
                self.assertIn(cls, rule_block)

    def test_the_custom_panels_really_needed_it(self):
        # Not flattened defensively: both are genuinely absolute on desktop, and
        # removing position:relative from their parent submenu would otherwise
        # have detached them onto the fixed drawer.
        for cls in ("workspace-appearance-options", "workspace-layout-options"):
            with self.subTest(panel_class=cls):
                # The DESKTOP rule is the first occurrence - the mobile one is
                # prefixed with html.mobile-nav-open, so a bare ".cls" lookup
                # finds the desktop declaration. Not string-subtracting PHONE
                # from _CSS: PHONE is a join of several blocks and appears
                # nowhere verbatim, so that subtraction removes nothing.
                desktop = _rule(_CSS, "." + cls)
                self.assertIsNotNone(desktop, cls)
                self.assertIn("position: absolute", desktop)


if __name__ == "__main__":
    unittest.main()
