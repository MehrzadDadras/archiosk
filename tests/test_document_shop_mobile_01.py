"""CLAUDE-DOCUMENT-SHOP-MOBILE-01 - the customer surface on a phone.

Two defects, both introduced by referencing a CSS class that existed nowhere:

  .asread-recovered-text  - recovered OCR text in a <pre> with no rule and no
                            global `pre` rule either, so it kept the browser
                            default `white-space: pre` and pushed the whole
                            page sideways on a phone.
  .customer-topbar        - a customer's ENTIRE navigation (the application
                            menubar is suppressed for them), laid out with
                            space-between and no wrap or breakpoint.

These assert the RULES exist and say the right thing. They are not a rendering
proof - no headless browser runs here, and a real phone pass is still owed.
What they do prevent is the rule silently disappearing again, which is exactly
how both defects arrived.
"""
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
CSS = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
RESULT_HTML = (_REPO_ROOT / "templates" / "document_shop_result.html").read_text(encoding="utf-8")
BASE_HTML = (_REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")


def _rule(selector, css=CSS):
    """The declaration block for a selector, or None."""
    m = re.search(r"(?m)^\s*%s\s*\{([^}]*)\}" % re.escape(selector), css)
    return m.group(1) if m else None


def _media_blocks(max_width):
    """Every @media (max-width: N) block body in main.css."""
    out = []
    needle = "@media (max-width: %dpx)" % max_width
    idx = 0
    while True:
        i = CSS.find(needle, idx)
        if i == -1:
            return out
        depth, j = 0, CSS.index("{", i)
        start = j
        while True:
            if CSS[j] == "{":
                depth += 1
            elif CSS[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        out.append(CSS[start:j])
        idx = j


class RecoveredTextWrappingTests(unittest.TestCase):
    def test_the_template_still_uses_the_class_these_rules_style(self):
        self.assertIn("asread-recovered-text", RESULT_HTML)

    def test_the_class_is_actually_defined(self):
        """The whole defect in one assertion: it was referenced, never defined."""
        self.assertIsNotNone(_rule(".asread-recovered-text"),
                             "recovered text has no stylesheet rule; a <pre> "
                             "with no rule does not wrap")

    def test_long_lines_wrap_instead_of_widening_the_page(self):
        rule = _rule(".asread-recovered-text")
        self.assertIn("pre-wrap", rule,
                      "must preserve the engine's own line breaks AND wrap")
        self.assertIn("overflow-wrap", rule,
                      "an unbroken run wider than the screen still needs a break")

    def test_the_block_is_bounded_to_its_column(self):
        rule = _rule(".asread-recovered-text")
        self.assertIn("max-width", rule)
        self.assertIn("100%", rule)

    def test_any_scrolling_is_the_blocks_own_not_the_pages(self):
        rule = _rule(".asread-recovered-text")
        if "overflow-x" in rule:
            self.assertRegex(rule, r"overflow-x\s*:\s*auto")

    def test_no_global_pre_rule_is_relied_on(self):
        """There is none, which is why the missing class was fatal."""
        self.assertIsNone(_rule("pre"),
                          "if a global pre rule is ever added, revisit this")


class CustomerTopBarMobileTests(unittest.TestCase):
    def test_the_bar_has_a_small_screen_rule(self):
        blocks = _media_blocks(560)
        self.assertTrue(blocks, "the 560px breakpoint should exist already")
        self.assertTrue(any(".customer-topbar" in b for b in blocks),
                        "a customer's only navigation has no phone rule")

    def test_it_wraps_or_stacks_rather_than_clipping(self):
        block = next(b for b in _media_blocks(560) if ".customer-topbar" in b)
        self.assertIn("flex-wrap", block)
        self.assertNotIn("display: none", block,
                         "navigation must never be hidden to fit")

    def test_all_three_destinations_survive(self):
        """Hiding one to make room would be the wrong fix, so pin them."""
        for ref in ("shell.customer.home", "shell.customer.documents",
                    "shell.customer.signout"):
            self.assertIn('data-ui-ref="%s"' % ref, BASE_HTML)

    def test_the_project_shell_is_untouched_by_the_mobile_rule(self):
        """Scoped to the customer bar - admin/read_only navigation is a
        different element and must not be restyled by this fix."""
        block = next(b for b in _media_blocks(560) if ".customer-topbar" in b)
        for foreign in (".workspace-menubar", ".launcher-panel",
                        ".tray-switcher", ".workspace-topbar {"):
            self.assertNotIn(foreign, block)

    def test_the_base_rule_is_still_present_for_wider_screens(self):
        self.assertIsNotNone(_rule(".customer-topbar"))
        self.assertIsNotNone(_rule(".customer-topbar-links"))


class ReferencedClassesResolveTests(unittest.TestCase):
    """Section 3 carried through, bounded to the customer surface.

    Not a CSS-lint framework: three named templates, and only classes whose
    ABSENCE changes layout. Layout-neutral names are listed and allowed, so
    this test says what it protects instead of failing on cosmetics.
    """

    # Undefined today, and each one is a plain block or inline element whose
    # default rendering already wraps - no layout consequence on a phone.
    LAYOUT_NEUTRAL = {"plain-list", "plain-list-item", "np-section-title",
                      "field-label", "field-note"}

    # Undefined, and DOES change layout: an unbounded image is wider than a
    # phone. Reported to the Product Owner rather than fixed - this tranche was
    # authorized for two defects, and broadening was explicitly excluded.
    KNOWN_REPORTED = {"asread-source-image"}

    def test_no_new_layout_affecting_class_goes_undefined(self):
        defined = set(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", CSS))
        for name in ("document_shop_result.html", "document_shop_jobs.html",
                     "document_shop_intake.html"):
            html = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            used = {c for attr in re.findall(r'class="([^"]*)"', html)
                    for c in attr.split() if "{" not in c}
            missing = used - defined - self.LAYOUT_NEUTRAL - self.KNOWN_REPORTED
            with self.subTest(template=name):
                self.assertEqual(
                    missing, set(),
                    "class referenced but never defined: %s. Either define it "
                    "or, if its absence genuinely changes no layout, add it to "
                    "LAYOUT_NEUTRAL with that reasoning." % sorted(missing))

    def test_the_reported_gap_is_still_only_the_one_we_named(self):
        """If asread-source-image ever gets defined, delete it from the
        exception rather than leaving a stale allowance behind."""
        defined = set(re.findall(r"\.([A-Za-z][A-Za-z0-9_-]*)", CSS))
        self.assertNotIn("asread-source-image", defined,
                         "now defined - remove it from KNOWN_REPORTED")


if __name__ == "__main__":
    unittest.main()
