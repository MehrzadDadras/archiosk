"""
CLAUDE-MOBILE-DOCUMENT-CONVERGENCE-01 - on a phone, the open document becomes
the job.

Product Owner, live iPhone: opening a drawing buries the evidence beneath
project chrome, repeated document identity, the document heading,
document-management controls, Document Context, viewer controls, Toolbox and
Composer.

THE PART THAT WAS MEASURABLE

Identity repetition. `.workspace-pane-document` is nested INSIDE the same
`.display-division-primary` that carries `.display-division-header`, so the
filename renders in the division header and again as the pane's own <h2>, one
above the other, on one screen - with the document tab strip carrying it a
third time. That nesting was verified against the template rather than assumed,
and it is what makes the <h2> redundant rather than merely repetitive.

WHAT THIS STAGE IS NOT

It removes no capability and hides no governed action. Download, Replace and
Remove stay visible and tappable; they stop occupying three stacked rows.
Document Context is untouched - it was already a collapsed <details>, so it was
never a permanent consumer of vertical space, and its durable, attributed,
governance-logged write is exactly what CA1 Section AC says must stay a control.

Desktop is untouched: every rule is inside the phone breakpoint, asserted below.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CSS = (_REPO_ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
_WORKSPACE = (_REPO_ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")

_MARKER = "CLAUDE-MOBILE-DOCUMENT-CONVERGENCE-01"


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


def _strip_comments(css: str) -> str:
    """Declarations only.

    Every negative assertion below runs against this. A comment explaining
    that the repair must not touch `main:has(...)` contains the string
    `main:has(...)`, and would satisfy an assertNotIn looking for the rule
    itself - the prose standing in for the thing it promises is absent.
    """
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


PHONE = _phone_blocks()
REPAIR = PHONE[PHONE.index(_MARKER):]
REPAIR_CODE = _strip_comments(REPAIR)


class DesktopIsUntouchedTests(unittest.TestCase):
    def test_the_whole_repair_lives_in_the_phone_breakpoint(self):
        self.assertIn(_MARKER, PHONE)
        self.assertEqual(_CSS.count(_MARKER), 1)

    def test_the_heading_is_not_hidden_globally(self):
        # A .workspace-pane-document > h2 { display: none } outside the
        # breakpoint would remove the document title on desktop, where no
        # division header sits above it in the same way. Counted rather than
        # subtracted: PHONE is a join of several blocks and never appears in
        # the file verbatim, so a str.replace() of it silently removes nothing
        # and the assertion passes on the whole file - a test that can only
        # pass. Occurrences inside the breakpoint must equal occurrences in
        # the file.
        selector = ".workspace-pane-document > h2"
        self.assertEqual(_CSS.count(selector), PHONE.count(selector))
        self.assertEqual(PHONE.count(selector), 1)


class OneIdentityNotThreeTests(unittest.TestCase):
    def test_the_redundant_heading_is_suppressed_on_mobile(self):
        rule = re.search(r"\.workspace-pane-document > h2\s*\{[^}]*\}", REPAIR)
        self.assertIsNotNone(rule, "the duplicated filename heading is still shown")
        self.assertIn("display: none", rule.group(0))

    def test_the_nesting_that_makes_it_redundant_still_holds(self):
        # If the pane ever moves OUT of the division that carries the header,
        # this repair silently removes the only identity on the screen. Assert
        # the structural fact the repair depends on.
        header_at = _WORKSPACE.index("display-division-header")
        pane_at = _WORKSPACE.index('class="workspace-pane workspace-pane-document"')
        self.assertLess(header_at, pane_at,
                        "the document pane no longer sits below the division header")

    def test_the_informative_label_is_kept(self):
        # "PDF, superseded by a later revision" is information the header does
        # not carry - suppressing it would lose meaning, not repetition.
        self.assertNotIn("workspace-pane-label", REPAIR_CODE)
        self.assertIn("workspace-pane-label", _WORKSPACE)


class GovernedActionsStayReachableTests(unittest.TestCase):
    """A consequential action must never be hidden to tidy a screen."""

    def test_document_actions_are_not_hidden(self):
        # ::-webkit-scrollbar is excluded by name, not by loosening the
        # assertion: it legitimately carries display:none because it hides the
        # SCROLLBAR, not the actions. A real display:none on the row itself
        # must still fail this.
        actions = re.findall(
            r"\.workspace-pane-document \.document-primary-actions([^{]*)\{([^}]*)\}",
            REPAIR_CODE)
        self.assertTrue(actions, "no mobile treatment for the document actions")
        checked = 0
        for suffix, declarations in actions:
            if "scrollbar" in suffix:
                continue
            checked += 1
            self.assertNotIn("display: none", declarations)
        self.assertTrue(checked, "only the scrollbar rule was found")

    def test_they_are_compacted_to_one_scrollable_row(self):
        rule = re.search(
            r"\.workspace-pane-document \.document-primary-actions\s*\{[^}]*\}", REPAIR)
        self.assertIn("flex-wrap: nowrap", rule.group(0))
        self.assertIn("overflow-x: auto", rule.group(0))

    def test_the_remove_action_is_still_rendered(self):
        self.assertIn("display.document.remove", _WORKSPACE)

    def test_document_context_is_untouched(self):
        # Already a collapsed <details>, so never a permanent space consumer -
        # and its governed write is exactly what CA1 Section AC protects.
        self.assertNotIn("document-context", REPAIR_CODE)
        self.assertIn('<details class="document-context-panel"', _WORKSPACE)
        self.assertIn("set_document_context_route", _WORKSPACE)


class TheEvidenceTakesTheSpaceTests(unittest.TestCase):
    def test_the_viewer_gets_a_height_floor(self):
        rule = re.search(r"\.workspace-pane-document \.document-viewer-canvas-container[^{]*\{[^}]*\}",
                         REPAIR_CODE)
        self.assertIsNotNone(rule, "the viewer has no mobile height floor")
        self.assertIn("min-height", rule.group(0))

    def test_it_is_a_floor_not_a_fixed_height(self):
        # A fixed height would stop the viewer growing and would fight the
        # internal scroll region that main:has(...) hands it.
        rule = re.search(r"\.workspace-pane-document \.document-viewer-canvas-container[^{]*\{[^}]*\}",
                         REPAIR_CODE).group(0)
        self.assertNotIn("height:", rule.replace("min-height:", ""))
        self.assertNotIn("max-height", rule)

    def test_the_internal_scroll_region_is_preserved(self):
        # "The document moves. The workspace does not." Removing the outer
        # scroll context is a prior, separate decision this must not disturb.
        self.assertIn("main:has(.document-viewer-canvas-container)", _CSS)
        self.assertNotIn("main:has", REPAIR_CODE)


class ThePreviousMobileRepairSurvivesTests(unittest.TestCase):
    def test_the_menu_repair_is_still_present(self):
        self.assertIn("CLAUDE-MOBILE-MENU-REPAIR-01", _CSS)

    def test_its_three_corrections_are_intact(self):
        menu = PHONE[PHONE.index("CLAUDE-MOBILE-MENU-REPAIR-01"):PHONE.index(_MARKER)]
        self.assertIn("min-height: 44px", menu)
        self.assertIn("body::after", menu)
        self.assertIn('aria-disabled="true"', menu)


if __name__ == "__main__":
    unittest.main()
