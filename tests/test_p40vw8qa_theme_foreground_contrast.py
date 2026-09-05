"""
CLAUDE-P40-VW8-QA - Theme Foreground Contrast Addendum.

tools/check_contrast.py's own REQUIRED_PAIRINGS list only ever checked
LIGHT-mode token pairings (--text-*/--canvas/--surface-primary are the
Light :root names; Dark/Tinted use separately-prefixed names
(--dark-*/--tint-*) that script never parsed). This stage's product-
owner walkthrough reported Light text as under-contrasted and Tinted
foreground as uncoordinated - auditing the FULL text-tier x surface-
tier matrix for all three modes directly (same relative-luminance math
as tools/check_contrast.py, run against every combination a mode's own
text can actually sit on: canvas, surface-primary, surface-secondary,
surface-hover, surface-selected) found Light itself fully compliant,
but two real sub-4.5:1 failures neither that script nor any prior
stage's spot checks had caught: --dark-text-metadata on --dark-surface-
selected, and --tint-text-metadata on --tint-surface-hover/-selected -
both corrected in tokens.css. This file pins the corrected matrix down
as a running regression test, and also verifies the actual per-surface
CSS-scoping mechanism (main.css's .appearance-dark/.appearance-tinted
rules) redefines the complete set of tokens the three text tiers and
seven semantic accents depend on - not just the two or three checked in
the original VW6 test file.

Deep Forest added afterwards (2026-09-05). It was NOT absent because it
postdates this file - it shipped in this same VW8-QA stage, and
test_p40vw8qa_approved_theme_set.py has always derived and pinned its
ramp. It was simply never added to the matrix here, so the one file
that measures every text tier against every surface layer measured
three of the four opaque Appearances. Nothing needed to change to
support it: --forest-* is a flat-hex ramp like the other three, and
_mode_tokens() was already prefix-driven. It passes everywhere, with
the tightest cell in the whole four-mode matrix at 4.71:1
(--forest-text-metadata on --forest-surface-selected, against the 4.5
floor). The fifth Appearance, Deep Ocean, is deliberately NOT here: its
tokens are translucent rgba() glass and its ratios only exist once
composited over a base layer, which needs a different harness -
tests/test_deep_ocean_contrast_coverage.py owns that one.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_contrast import contrast_ratio, parse_tokens  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKENS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"

_TEXT_TIERS = ("text-primary", "text-secondary", "text-metadata")
_SURFACE_LAYERS = ("canvas", "surface-primary", "surface-secondary", "surface-hover", "surface-selected")


def _mode_tokens(tokens: dict, prefix: str) -> dict:
    def get(name: str) -> str:
        key = f"--{prefix}{name}" if prefix else f"--{name}"
        return tokens[key]

    return {
        "canvas": get("canvas"),
        "surface-primary": get("surface-primary"),
        "surface-secondary": get("surface-secondary"),
        "surface-hover": get("surface-hover"),
        "surface-selected": get("surface-selected"),
        "text-primary": get("text-primary"),
        "text-secondary": get("text-secondary"),
        "text-metadata": get("text-metadata"),
    }


class FullModeMatrixContrastTests(unittest.TestCase):
    """Every text tier against every surface layer it can actually
    render on, for all four OPAQUE Appearance modes - not just canvas/
    surface-primary (tools/check_contrast.py's own, Light-only, subset)."""

    @classmethod
    def setUpClass(cls):
        raw = parse_tokens(_TOKENS_PATH)
        cls.modes = {
            "Light": _mode_tokens(raw, ""),
            "Dark": _mode_tokens(raw, "dark-"),
            "Tinted": _mode_tokens(raw, "tint-"),
            "Deep Forest": _mode_tokens(raw, "forest-"),
        }

    def test_every_text_tier_meets_aa_against_every_surface_layer_in_every_mode(self):
        failures = []
        for mode_name, tokens in self.modes.items():
            for text_tier in _TEXT_TIERS:
                for surface in _SURFACE_LAYERS:
                    ratio = contrast_ratio(tokens[text_tier], tokens[surface])
                    if ratio < 4.5:
                        failures.append(
                            f"{mode_name} {text_tier} ({tokens[text_tier]}) on {surface} "
                            f"({tokens[surface]}): {ratio:.2f}:1 (need 4.5:1)"
                        )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_light_mode_foreground_is_dark_and_readable(self):
        # The addendum's own framing: Light must be a genuinely dark,
        # near-black foreground, not merely AA-legal.
        tokens = self.modes["Light"]
        ratio = contrast_ratio(tokens["text-primary"], tokens["surface-primary"])
        self.assertGreaterEqual(ratio, 7.0, "Light text-primary should read as clearly dark ink, not merely passing")

    def test_dark_mode_foreground_is_light_and_readable(self):
        tokens = self.modes["Dark"]
        ratio = contrast_ratio(tokens["text-primary"], tokens["surface-primary"])
        self.assertGreaterEqual(ratio, 7.0)

    def test_tinted_mode_foreground_is_light_and_readable(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set) inverted Tinted's own
        # polarity on purpose: "Tinted" (now labeled "Midnight Blue") was
        # a light navy-grey daylight variant when this test was first
        # written (needing a DARK foreground) and is now one of the
        # three DARK appearance choices (a solid, deeply saturated navy,
        # #001426) - it needs a LIGHT foreground, the same shared warm
        # off-white family Black/Deep Forest use, not a dark charcoal.
        tokens = self.modes["Tinted"]
        ratio = contrast_ratio(tokens["text-primary"], tokens["surface-primary"])
        self.assertGreaterEqual(ratio, 7.0)
        # "light" - luminance well above the mid-point, not just AA-passing.
        from check_contrast import relative_luminance
        self.assertGreater(relative_luminance(tokens["text-primary"]), 0.5)

    def test_deep_forest_mode_foreground_is_light_and_readable(self):
        # Same two assertions Black/Midnight Blue are held to above -
        # Deep Forest is the third of the three opaque DARK appearances
        # and shares their warm off-white foreground family.
        tokens = self.modes["Deep Forest"]
        ratio = contrast_ratio(tokens["text-primary"], tokens["surface-primary"])
        self.assertGreaterEqual(ratio, 7.0)
        from check_contrast import relative_luminance
        self.assertGreater(relative_luminance(tokens["text-primary"]), 0.5)

    def test_metadata_tier_still_visibly_dimmer_than_secondary_tier(self):
        # The two corrected values must not have been darkened/lightened
        # so far they stop reading as the quietest tier (Section
        # requirement: "may be visually quieter but must remain
        # readable" - quieter is still required, not just readable).
        # "Quieter" means closer to the surface it sits on - contrast
        # ratio against surface-primary is the theme-agnostic measure
        # (Light/Tinted: metadata is lighter than secondary; Dark:
        # metadata is dimmer/less-white than secondary - both mean
        # "lower contrast against its own surface").
        for mode_name, tokens in self.modes.items():
            ratio_secondary = contrast_ratio(tokens["text-secondary"], tokens["surface-primary"])
            ratio_metadata = contrast_ratio(tokens["text-metadata"], tokens["surface-primary"])
            self.assertLess(ratio_metadata, ratio_secondary, mode_name)


class SemanticAccentContrastTests(unittest.TestCase):
    """The seven semantic accents (seal-red, machine-blue, ...), each
    against their own mode's canvas/surface-primary - the badge/link/
    accent-text pairing threshold (3:1), for all four opaque modes.

    Deep Forest's accent hexes are asserted equal to Black's elsewhere
    (test_p40vw8qa_approved_theme_set.py), but its canvas is not black
    (#001A12), so these are genuinely different measurements, not a
    restatement of the Black rows."""

    _ACCENTS = (
        "seal-red", "machine-blue", "highlight-orange",
        "accepted-green", "attention-amber", "failure-red", "risk-red",
    )

    @classmethod
    def setUpClass(cls):
        cls.tokens = parse_tokens(_TOKENS_PATH)

    def test_every_accent_meets_3_to_1_against_canvas_and_surface_in_every_mode(self):
        failures = []
        for mode_name, prefix in (
            ("Light", ""), ("Dark", "dark-"), ("Tinted", "tint-"), ("Deep Forest", "forest-"),
        ):
            canvas = self.tokens[f"--{prefix}canvas"] if prefix else self.tokens["--canvas"]
            surface = self.tokens[f"--{prefix}surface-primary"] if prefix else self.tokens["--surface-primary"]
            for accent in self._ACCENTS:
                key = f"--{prefix}{accent}" if prefix else f"--{accent}"
                fg = self.tokens[key]
                for bg_name, bg in (("canvas", canvas), ("surface-primary", surface)):
                    ratio = contrast_ratio(fg, bg)
                    if ratio < 3.0:
                        failures.append(f"{mode_name} {accent} ({fg}) on {bg_name} ({bg}): {ratio:.2f}:1")
        self.assertEqual(failures, [], "\n".join(failures))


class PerSurfaceScopingCompletenessTests(unittest.TestCase):
    """main.css's .appearance-dark/.appearance-tinted rules must
    redefine the COMPLETE set of foreground-relevant tokens on all 5
    owned surface roots - a partial redefinition would leave some
    descendant rendering with a mismatched mode's color (the exact
    'inherit an unsuitable color from another theme' failure mode the
    addendum names)."""

    _REQUIRED_REDEFINED_TOKENS = (
        "--canvas", "--surface-primary", "--surface-secondary",
        "--surface-hover", "--surface-selected", "--border", "--border-strong",
        "--text-primary", "--text-secondary", "--text-metadata", "--text-disabled",
        "--seal-red", "--machine-blue", "--highlight-orange",
        "--accepted-green", "--attention-amber", "--failure-red", "--risk-red",
    )
    # CLAUDE-P40-EYE1: the Toolbox surface's own painted root moved to
    # .workspace-right-column (the new full-height column containing
    # Toolbox AND Eye) - see that stage's own comment in main.css.
    _OWNED_SURFACE_SELECTORS = (
        ".workspace-topbar", ".launcher-panel", ".app-main",
        ".workspace-right-column", ".chat-region",
    )

    @classmethod
    def setUpClass(cls):
        cls.source = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _scoping_block(self, mode_class: str) -> str:
        marker = f".appearance-{mode_class} {{"
        # Find the rule block whose selector list contains all 5 owned
        # surfaces compounded with this mode class - the rule this
        # test cares about, not any other incidental use of the class.
        idx = self.source.index(f".workspace-topbar.appearance-{mode_class}")
        block_start = self.source.index("{", idx)
        block_end = self.source.index("}", block_start)
        selectors = self.source[max(0, idx - 5):block_start]
        body = self.source[block_start:block_end]
        return selectors + body

    def test_dark_scoping_redefines_every_owned_surface_and_every_required_token(self):
        block = self._scoping_block("dark")
        for surface in self._OWNED_SURFACE_SELECTORS:
            self.assertIn(f"{surface}.appearance-dark", block)
        for token in self._REQUIRED_REDEFINED_TOKENS:
            self.assertIn(f"{token}: var(--dark-{token.lstrip('-')})", block)

    def test_tinted_scoping_redefines_every_owned_surface_and_every_required_token(self):
        block = self._scoping_block("tinted")
        for surface in self._OWNED_SURFACE_SELECTORS:
            self.assertIn(f"{surface}.appearance-tinted", block)
        for token in self._REQUIRED_REDEFINED_TOKENS:
            self.assertIn(f"{token}: var(--tint-{token.lstrip('-')})", block)


if __name__ == "__main__":
    unittest.main()
