"""
CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION - CSS-source coverage for the two
pieces of this correction round that are pure presentation (no route/
service behavior to exercise through the test client): reduced visual
chrome on the fourth-beat operational-action controls (Section 17) and
the quieter composer treatment (Section 18), plus a source-level check
that the shared highlight/focus grammar (Section 11-14) still
distinguishes PERSISTENT highlight from TEMPORARY source-return focus
after the two "reduce highlight strength" refinement passes.

Route/service-level coverage for River Action Stack, task-anchor
precision, and the Eye-panel fix already lives in
tests/test_ca1d_river_po01_action_stack.py and
tests/test_ca1d_river_po02_provenance_precision.py - not duplicated
here.

Run via:

    python -m unittest tests.test_ca1d_river_po02_consolidation -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


class ActionControlChromeTests(unittest.TestCase):
    """Section 17: line-based separation, not a full pill, for the
    fourth-beat controls specifically - Finding review's own
    .review-btn pill (an unrelated, deliberate review decision) must be
    untouched."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_operational_action_buttons_lose_the_full_pill_box(self):
        block = self.css[self.css.index(".conv-operational-actions .review-btn {"):]
        block = block[: block.index("}") + 1]
        self.assertIn("border: none", block)
        self.assertIn("background: transparent", block)
        self.assertIn("border-radius: 0", block)

    def test_operational_action_buttons_still_signal_interactivity_on_hover(self):
        # "Reduce visual chrome" must not mean "looks like plain text" -
        # a hover state still has to exist.
        start = self.css.index(".conv-operational-actions .review-btn:hover")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("border-bottom-color: currentColor", block)

    def test_adjacent_actions_get_a_side_rule_not_a_second_box(self):
        start = self.css.index(".conv-operational-action-form:not(:first-child)")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("border-left", block)

    def test_finding_review_pill_is_untouched_by_this_correction(self):
        # The base .review-btn rule (Finding accept/reject/needs_evidence/
        # correction/seal) must still be the original enclosed pill - the
        # override above is scoped to .conv-operational-actions only.
        start = self.css.index(".review-btn {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("border-radius: 999px", block)

    def test_operational_action_buttons_keep_a_real_click_target(self):
        block = self.css[self.css.index(".conv-operational-actions .review-btn {"):]
        block = block[: block.index("}") + 1]
        match = re.search(r"padding:\s*([\d.]+)rem", block)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(float(match.group(1)), 0.3)


class ComposerChromeTests(unittest.TestCase):
    """Section 18: the input reads as a lane (top+bottom rule only,
    CLAUDE-CA1D-COMPOSER-LINE-01 - was bottom-only), Send stays a real,
    filled commit control - "make the smallest shared styling
    correction," not a full composer redesign."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_composer_input_no_longer_has_an_all_around_box(self):
        start = self.css.index('.conversation-input-form input[type="text"] {')
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("border: none", block)
        # CLAUDE-CA1D-COMPOSER-LINE-01: a live product-owner refinement -
        # the lane's top and bottom rules now reuse --machine-blue (the
        # existing ARCHIOSK chat-identity color, already used elsewhere
        # on this same Chat surface) instead of the neutral --border,
        # and gained a matching top rule (was bottom-only).
        self.assertIn('border-top: 1px solid var(--machine-blue)', block)
        self.assertIn('border-bottom: 1px solid var(--machine-blue)', block)
        self.assertIn("border-radius: 0", block)
        # Still just two thin hairlines, never a filled/tinted surface.
        self.assertIn("background: transparent", block)

    def test_composer_input_focus_still_visually_indicated(self):
        # CLAUDE-CA1D-COMPOSER-LINE-01: the composer's own dedicated
        # `:focus { border-bottom-color: var(--machine-blue) }` override
        # is gone - now genuinely redundant, since the lane's resting
        # state is already permanently --machine-blue (top AND bottom).
        # Focus is still visually indicated, just via the pre-existing
        # GLOBAL input:focus-visible outline rule this file already
        # declares for every input/button/link, unchanged by this
        # correction.
        start = self.css.index("a:focus-visible, button:focus-visible, input:focus-visible")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("outline: 2px solid var(--machine-blue)", block)
        # And the composer-specific override is genuinely gone, not just
        # renamed - the resting-state assertion above is what carries
        # this rule's old job now.
        self.assertNotIn('.conversation-input-form input[type="text"]:focus', self.css)

    def test_send_button_remains_a_real_filled_commit_control(self):
        # Section 19's own restraint: only the input needed correcting -
        # Send staying visually distinct is deliberate, not an oversight.
        start = self.css.index(".conversation-input-form button {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("background: var(--text-primary)", block)


class HighlightFocusGrammarDistinctionTests(unittest.TestCase):
    """Sections 11-14: PERSISTENT highlight and TEMPORARY source-return
    focus must remain two distinguishable mechanisms, each internally
    coherent (contrast-safe text, reduced-motion fallback), even after
    two rounds of "reduce highlight strength.\""""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_persistent_highlight_sets_explicit_readable_foreground(self):
        start = self.css.index(".tag-highlight-inline {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("color: var(--text-primary)", block)

    def test_persistent_highlight_background_is_translucent_not_opaque(self):
        start = self.css.index(".tag-highlight-inline {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("color-mix(", block)
        self.assertIn("transparent", block)

    def test_temporary_focus_is_animated_and_persistent_highlight_is_not(self):
        # The distinguishing mechanism between the two states: temporary
        # focus decays via a keyframe animation; persistent highlight is
        # a stable, unanimated fill.
        persistent_block_start = self.css.index(".tag-highlight-inline {")
        persistent_block = self.css[persistent_block_start:]
        persistent_block = persistent_block[: persistent_block.index("}") + 1]
        self.assertNotIn("animation", persistent_block)

        temp_block_start = self.css.index(".conv-source-flash {")
        temp_block = self.css[temp_block_start:]
        temp_block = temp_block[: temp_block.index("}") + 1]
        self.assertIn("animation: conv-source-flash-fade", temp_block)

    def test_temporary_focus_peak_alpha_is_lower_than_persistent_highlight(self):
        # PO refinement round 2 ("never resemble a persistent selected
        # block"): the flash's own resting fill must read as quieter
        # than the deliberately-chosen persistent mark, not stronger.
        persistent_match = re.search(
            r"\.tag-highlight-inline \{[^}]*color-mix\(in srgb, var\(--tagcolor-yellow\) (\d+)%",
            self.css,
        )
        flash_match = re.search(
            r"0% \{\s*background: color-mix\(in srgb, var\(--highlight-orange\) (\d+)%",
            self.css,
        )
        self.assertIsNotNone(persistent_match)
        self.assertIsNotNone(flash_match)
        self.assertLess(int(flash_match.group(1)), int(persistent_match.group(1)))

    def test_temporary_focus_reduced_motion_fallback_stays_translucent(self):
        start = self.css.index("@media (prefers-reduced-motion: reduce) {\n    .conv-source-flash {")
        block = self.css[start:]
        block = block[: block.index("}\n}") + 3]
        self.assertIn("color-mix(", block)
        self.assertIn("animation: none", block)


class TaskCheckboxChromeTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_checkbox_is_a_real_native_checkbox_not_a_div(self):
        self.assertIn(".task-checkbox {", self.css)
        start = self.css.index(".task-checkbox {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("appearance: none", block)

    def test_checkbox_checked_state_uses_the_accepted_green_semantic_token(self):
        start = self.css.index(".task-checkbox:checked {")
        block = self.css[start:]
        block = block[: block.index("}") + 1]
        self.assertIn("var(--accepted-green)", block)


if __name__ == "__main__":
    unittest.main()
