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


def _min_width_blocks(min_width):
    """EVERY @media (min-width: N) block body - the file already has more than
    one at some widths, so taking only the first finds the wrong rules."""
    out, idx = [], 0
    needle = "@media (min-width: %dpx)" % min_width
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


class SourceImageContainmentTests(unittest.TestCase):
    """CLAUDE-DOCUMENT-SHOP-MOBILE-02 - the customer's uploaded image.

    Undefined with no global img rule to fall back on, so a scan or phone photo
    rendered at natural width and scrolled the whole page sideways.
    """

    def test_the_template_still_uses_the_class(self):
        self.assertIn("asread-source-image", RESULT_HTML)

    def test_the_class_is_defined(self):
        self.assertIsNotNone(_rule(".asread-source-image"))

    def test_the_image_cannot_exceed_its_container(self):
        rule = _rule(".asread-source-image")
        self.assertRegex(rule, r"max-width\s*:\s*100%")

    def test_aspect_ratio_is_preserved(self):
        rule = _rule(".asread-source-image")
        self.assertRegex(rule, r"height\s*:\s*auto",
                         "a fixed height would distort the customer's own scan")

    def test_it_does_not_crop_or_hide_anything(self):
        rule = _rule(".asread-source-image")
        for forbidden in ("object-fit: cover", "clip-path", "overflow: hidden",
                          "display: none"):
            self.assertNotIn(forbidden, rule)

    def test_no_global_img_rule_is_relied_on(self):
        self.assertIsNone(_rule("img"),
                          "if a global img rule appears, revisit this")

    def test_project_and_admin_image_styling_is_untouched(self):
        """Scoped to the one class - no shared image selector was changed."""
        for foreign in (".drawing-", ".workspace-", ".thumbnail", ".pdf-page"):
            self.assertNotIn(foreign, _rule(".asread-source-image") or "")


class ResultRowReflowTests(unittest.TestCase):
    """CLAUDE-DOCUMENT-SHOP-MOBILE-03 - label/value rows on a narrow screen."""

    def _dl_rule(self, selector):
        return _rule(selector)

    def test_the_result_uses_definition_lists(self):
        self.assertIn('<dl class="plain-list"', RESULT_HTML)

    def test_the_definition_list_is_defined_for_the_result(self):
        self.assertIsNotNone(_rule("dl.plain-list"),
                             "undefined means the UA default 40px dd indent")

    def test_values_lose_the_inherited_indent(self):
        rule = _rule("dl.plain-list dd")
        self.assertIsNotNone(rule)
        self.assertIn("margin-inline-start", rule)
        self.assertRegex(rule, r"margin-inline-start\s*:\s*0")

    def test_long_values_can_break(self):
        self.assertIn("overflow-wrap", _rule("dl.plain-list dd"))

    def test_portrait_is_stacked_not_columned(self):
        """No grid outside a min-width block: narrow screens stack."""
        base = _rule("dl.plain-list")
        self.assertNotIn("grid-template-columns", base)

    def test_columns_return_by_width_not_by_device(self):
        blocks = [b for b in _min_width_blocks(900) if "dl.plain-list" in b]
        self.assertTrue(blocks, "no wider-screen rule for the result rows")
        self.assertIn("grid-template-columns", blocks[0])

    def test_no_orientation_media_query_is_used(self):
        """Width, never orientation - a phone held sideways is just wider."""
        self.assertNotIn("orientation:", CSS)

    def test_the_jobs_list_grammar_is_not_restyled(self):
        """Same class name, different element - and not part of this finding."""
        self.assertNotIn("ul.plain-list", CSS)

    def test_wording_and_semantics_are_untouched(self):
        for phrase in ("What we can say from the file itself",
                       "What GO made of it", "What we could not establish"):
            self.assertIn(phrase, RESULT_HTML)


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
    #
    # CLAUDE-DOCUMENT-SHOP-MOBILE-03: "plain-list" WAS in this set and should
    # not have been. The UA default for <dd> is margin-inline-start: 40px, which
    # is a real layout effect on a phone - it is what the Product Owner saw as
    # labels and values competing for narrow columns. It is now defined for the
    # <dl> grammar. It remains listed for the <ul> on My documents, which is a
    # different element and genuinely default-safe.
    LAYOUT_NEUTRAL = {"plain-list", "plain-list-item", "np-section-title",
                      "field-label", "field-note"}

    # CLAUDE-DOCUMENT-SHOP-MOBILE-02: this set held "asread-source-image" while
    # that defect was reported-but-unfixed. It is fixed, so the allowance is
    # gone rather than left behind as a hole nobody revisits - which is what
    # the removed test below existed to force.
    KNOWN_REPORTED = set()

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

    def test_no_stale_allowances_remain(self):
        """An exception set that outlives its defect is how a known gap
        becomes an invisible one."""
        self.assertEqual(self.KNOWN_REPORTED, set())


if __name__ == "__main__":
    unittest.main()
