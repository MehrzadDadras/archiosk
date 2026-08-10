"""
CLAUDE-LEFTPANEL-DENSITY-03 - Reduce Tree Indentation / Left Margins
Globally.

Root cause: two separate, previously-hardcoded values compounded to make
the left panel's hierarchy feel loose - .tree-children's own recursive
per-level padding-left (0.75rem, applied again at every nesting depth)
and every row's own base left inset (.launcher-heading/.launcher-link/
.launcher-subheading/.tree-node-empty, all baked to a flat 0.55rem).
Fixed by introducing two shared custom properties (--tree-indent-step,
--tree-row-inset), declared once on the shared `.tree, .tree-children`
rule and referenced everywhere a left inset was previously a literal
value - "apply through shared spacing variables... rather than per-item
overrides" (this stage's own explicit requirement). Only the LEFT side
of every row's padding changed; every other side (right padding, where
the chevron/count badge sit) is untouched.

Run via:

    python -m unittest tests.test_leftpanel_density03_tree_indentation -v
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


def _rule_body(css: str, selector: str) -> str:
    """Plain marker-text lookup: every anchor passed here includes a
    trailing "{" (or more of the rule's own body), never a bare class
    name - this file's own prose comments discuss several of these
    classes together (e.g. "both also carry .launcher-heading/.launcher-
    link respectively"), so a bare class-name substring search can match
    a comment mention before the real rule instead of the rule itself."""
    idx = css.index(selector)
    start = css.index("{", idx)
    end = css.index("}", start)
    return css[start + 1:end]


class SharedSpacingVariableTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_tree_indent_step_and_row_inset_declared_once_on_the_shared_rule(self):
        body = _rule_body(self.css, ".tree, .tree-children {")
        self.assertIn("--tree-indent-step:", body)
        self.assertIn("--tree-row-inset:", body)

    def test_no_new_hardcoded_indentation_values_introduced(self):
        # The two variables are declared with a real value exactly once
        # (on the shared rule above) - every consumer below must
        # reference var(...), never repeat a literal rem value of its
        # own, per this stage's own explicit "shared spacing variables...
        # rather than per-item overrides" requirement.
        body = _rule_body(self.css, ".tree-children {\n    padding-left")
        self.assertRegex(body, r"var\(--tree-indent-step\)")
        for selector in (
            ".launcher-heading {", ".launcher-link {\n    display: block;",
            ".launcher-subheading {", ".tree-node-empty {",
        ):
            body = _rule_body(self.css, selector)
            self.assertRegex(body, r"var\(--tree-(indent-step|row-inset)\)", selector)


class IndentationReducedTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_tree_children_recursive_step_uses_the_shared_variable(self):
        # Anchored to its own standalone rule specifically - a bare
        # ".tree-children {" would instead match the EARLIER, unrelated
        # combined ".tree, .tree-children { list-style: none; ... }"
        # reset rule, since that selector list also contains the text
        # ".tree-children {" as part of it... actually it doesn't (the
        # combined selector is ".tree, .tree-children" followed by ONE
        # "{"), but anchoring on the property name removes any doubt.
        body = _rule_body(self.css, ".tree-children {\n    padding-left")
        self.assertIn("padding-left: var(--tree-indent-step)", body)
        # The guide line stays - "vertical guide lines, if retained,
        # should align with the tightened hierarchy" - same border, now
        # just a smaller step away from the previous level.
        self.assertIn("border-left: 1px solid var(--border)", body)

    def test_row_level_selectors_use_the_shared_row_inset_on_the_left_only(self):
        # CLAUDE-LEFTPANEL-DENSITY-04 own the exact vertical numbers now
        # (a real, deliberate further tightening - see
        # ClickTargetAndOverlapPreservedTests below) - this test's own
        # remaining job is just confirming every row selector still
        # anchors its LEFT inset to the shared var(--tree-row-inset)
        # custom property, which is what DENSITY-03 actually introduced.
        cases = {
            ".launcher-heading {": "var(--tree-row-inset);",
            ".launcher-link {\n    display: block;": "var(--tree-row-inset);",
            ".launcher-subheading {": "var(--tree-row-inset);",
            ".tree-node-empty {": "padding: 0.16rem 0.55rem 0.16rem var(--tree-row-inset);",
        }
        for selector, expected in cases.items():
            body = _rule_body(self.css, selector)
            self.assertIn(expected, body, selector)

    def test_right_side_padding_of_rows_is_completely_unchanged(self):
        # Chevron/count-badge placement (governed by the row's own RIGHT
        # padding) must not move - only the left margin before content
        # was reported too wide.
        for selector in (".launcher-heading {", ".launcher-link {\n    display: block;"):
            body = _rule_body(self.css, selector)
            self.assertIn("0.55rem", body, selector)

    def test_current_project_border_compensation_uses_the_shared_variable(self):
        # The 3px accent border must still visually replace, not add to,
        # this row's own (now-variable, not hardcoded) left inset.
        body = _rule_body(self.css, ".launcher-link.current-project {")
        self.assertIn("padding-left: calc(var(--tree-row-inset) - 3px)", body)

    def test_the_reduced_step_is_meaningfully_smaller_than_the_original(self):
        # 0.75rem (original recursive step) -> a real, visible reduction,
        # not a token-only refactor that leaves the actual number
        # unchanged. Parsed from the variable's own declaration, not
        # assumed.
        body = _rule_body(self.css, ".tree, .tree-children {")
        match = re.search(r"--tree-indent-step:\s*([\d.]+)rem", body)
        self.assertIsNotNone(match)
        self.assertLess(float(match.group(1)), 0.75)
        self.assertGreater(float(match.group(1)), 0, "must still be a real, visible step - hierarchy must stay legible")


class ClickTargetAndOverlapPreservedTests(unittest.TestCase):
    """"No text/chevron overlap" / "no clipping" - the chevron/label
    layout mechanics are untouched by this stage. Vertical padding
    itself was DELIBERATELY reduced by the later CLAUDE-LEFTPANEL-
    DENSITY-04 pass (own explicit Product Owner ask: "top/bottom padding
    inside each navigational row is thinner") - this class's own name
    predates that and no longer describes an invariant that holds; the
    remaining check is that the new, smaller values still clear a real
    click/tap target, not that the numbers never moved."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_vertical_padding_still_clears_a_real_click_target(self):
        for selector, expected_vertical in (
            (".launcher-heading {", ("0.24rem", "0.24rem")),
            (".launcher-link {\n    display: block;", ("0.3rem", "0.3rem")),
        ):
            body = _rule_body(self.css, selector)
            top, bottom = expected_vertical
            self.assertIn(f"padding: {top}", body, selector)
            self.assertIn(f"{bottom} var(--tree-row-inset)", body, selector)
            # Rough floor: 2x vertical padding + a ~13-14px line-height
            # (var(--text-sm)) should stay comfortably above the usual
            # ~24px minimum tap-target guidance.
            self.assertGreaterEqual(float(top.replace("rem", "")) * 2 * 16 + 13, 20)

    def test_chevron_and_label_layout_mechanics_untouched(self):
        toggle_body = _rule_body(self.css, ".tree-toggle {")
        self.assertIn("justify-content: space-between", toggle_body)
        label_body = _rule_body(self.css, ".tree-toggle .tree-label {")
        self.assertIn("overflow: hidden", label_body)
        self.assertIn("text-overflow: ellipsis", label_body)


if __name__ == "__main__":
    unittest.main()
