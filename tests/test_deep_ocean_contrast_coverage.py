"""
Deep Ocean contrast coverage - the translucent theme the contrast
harness could not previously see.

tools/check_contrast.py's parse_tokens() only ever matched values of
the form `#RRGGBB`. Every other Appearance (Titanium/Black/Midnight
Blue/Deep Forest) is an opaque flat-hex ramp, so that was sufficient
for four of the five - but Deep Ocean's structural tokens are literal
copies of .gateway-shell's translucent glass (`rgba(10, 35, 42, .55)`
and family, see tokens.css's own CLAUDE-APPEARANCE-SIMPLIFY-01 comment),
and a value that does not match the hex pattern is not skipped loudly:
it simply never enters the token dict at all. The result was a theme
with zero automated contrast coverage that looked, from the outside,
exactly like a theme that passed - no failure, no SKIP line, nothing.

What was added to close it (tools/check_contrast.py):

  * parse_color()      - `#RGB`/`#RRGGBB`/`rgb()`/`rgba()` -> (r,g,b,a)
  * composite_stack()  - source-over alpha compositing over an opaque
                         base: C = a*C_fg + (1-a)*C_bg, per channel,
                         held in float across the whole stack
  * relative_luminance() now RAISES on a translucent color rather than
    silently discarding its alpha - the failure mode this file exists
    to prevent, made unrepresentable.

The base layer is not invented here. It is read out of main.css's own
`.app-shell.appearance-deep-ocean` rule (the literal .landing-page
gradient - .app-shell is the opaque bottom layer everything else floats
above), so a change to that gradient moves these assertions rather than
leaving them measuring a background the app no longer paints.

**The base used is the worst case, not a typical pixel.** Deep Ocean's
foregrounds are all light, so the LIGHTEST attainable backdrop is the
one that produces the lowest ratio. That is the lightest linear-gradient
stop with BOTH radial overlays composited over it at full strength - an
upper bound on lightness, since the two radials are centred at 50% 10%
and 50% 45% and never both reach full strength on the same pixel. Every
ratio asserted below is therefore pessimistic by construction.

That upper bound is what separates this from the figures already
recorded in tokens.css's CLAUDE-DEEP-OCEAN-HUE-CORRECTION-01 comment
(text-primary 15.36:1, text-secondary 10.51:1, text-metadata 7.41:1).
Those were measured against the lightest linear stop ALONE, with the
radial overlays left out; this file reproduces them to within 0.1 when
the overlays are excluded (a direct check on the harness's own math,
below) and then re-measures with the overlays included, which costs
roughly 1.1 points. Both readings clear AAA for primary/secondary; the
recorded numbers are not wrong, they are a different, less conservative
backdrop.

backdrop-filter's blur is not modelled. It redistributes luminance
spatially without materially changing the mean of what sits behind a
panel, and there is no way to express a blur in a contrast ratio - the
compositing above is the part that actually determines the ratio.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from check_contrast import (  # noqa: E402
    composite,
    composite_stack,
    contrast_ratio,
    parse_color,
    parse_tokens,
    relative_luminance,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKENS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"

# Every surface a Deep Ocean text tier can actually render on: the five
# the three-mode matrix already checks (test_p40vw8qa_theme_foreground_
# contrast.py), plus the denser floating-menu fill CLAUDE-MENU-
# FOREGROUND-LAYERING-01 added, which carries menu item text.
_SURFACE_LAYERS = (
    "canvas", "surface-primary", "surface-secondary",
    "surface-hover", "surface-selected", "glass-foreground",
)
_TEXT_TIERS = ("text-primary", "text-secondary", "text-metadata")
_ACCENTS = (
    "seal-red", "machine-blue", "highlight-orange",
    "accepted-green", "attention-amber", "failure-red", "risk-red",
)

# One level of nesting is enough: rgba(...) inside a gradient's argument
# list, and nothing deeper appears in this rule.
_GRADIENT_RE = re.compile(r"(linear|radial)-gradient\(((?:[^()]|\([^()]*\))*)\)")
_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})|rgba?\([^)]*\)")


def _ocean_base_gradient() -> tuple[list[str], list[str]]:
    """(opaque linear stops, translucent radial overlays) as main.css
    actually declares them, top-listed first."""
    css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
    # `\{` immediately after the compound selector: the descendant rule
    # `.app-shell.appearance-deep-ocean .display-divisions` and the
    # combined `.app-shell.appearance-deep-ocean,` selector list both
    # continue with something else, so neither is matched here.
    rule = re.search(r"\.app-shell\.appearance-deep-ocean\s*\{([^}]*)\}", css, re.S)
    assert rule is not None, ".app-shell.appearance-deep-ocean rule not found in main.css"
    stops: list[str] = []
    overlays: list[str] = []
    for kind, args in _GRADIENT_RE.findall(rule.group(1)):
        (stops if kind == "linear" else overlays).extend(_COLOR_RE.findall(args))
    return stops, overlays


def _worst_case_base() -> str:
    """The lightest backdrop Deep Ocean's glass can sit on - see this
    module's docstring for why lightest is the worst case."""
    stops, overlays = _ocean_base_gradient()
    lightest = max(stops, key=relative_luminance)
    # `background` paints the first-listed layer on TOP, so compositing
    # bottom-first means applying the overlays in reverse.
    return composite_stack(lightest, *reversed(overlays))


class AlphaCompositingPrimitiveTests(unittest.TestCase):
    """The new harness pieces themselves, on values whose answers are
    known independently of this repository's palette."""

    def test_parse_color_accepts_both_hex_lengths_and_both_functional_forms(self):
        self.assertEqual(parse_color("#FFC400"), (255.0, 196.0, 0.0, 1.0))
        self.assertEqual(parse_color("#fff"), (255.0, 255.0, 255.0, 1.0))
        self.assertEqual(parse_color("rgb(230, 244, 255)"), (230.0, 244.0, 255.0, 1.0))
        self.assertEqual(parse_color("rgba(10, 35, 42, .55)"), (10.0, 35.0, 42.0, 0.55))
        self.assertEqual(parse_color("rgba(0, 0, 0, 0)"), (0.0, 0.0, 0.0, 0.0))

    def test_parse_color_rejects_anything_it_cannot_measure(self):
        for value in ("transparent", "var(--bee-yellow)", "0 24px 70px rgba(1, 8, 14, .5)"):
            with self.assertRaises(ValueError, msg=value):
                parse_color(value)

    def test_composite_is_the_standard_source_over_formula(self):
        # 50% white over black -> the exact midpoint, 127.5 -> #80.
        self.assertEqual(composite("rgba(255, 255, 255, .5)", "#000000"), "#808080")
        # a = 1 keeps the foreground; a = 0 keeps the background.
        self.assertEqual(composite("rgba(255, 0, 0, 1)", "#000000"), "#FF0000")
        self.assertEqual(composite("rgba(255, 0, 0, 0)", "#0A232A"), "#0A232A")
        # .25 of 255 over 0 -> 63.75 -> 64 -> 0x40, per channel.
        self.assertEqual(composite("rgba(255, 255, 255, .25)", "#000000"), "#404040")

    def test_composite_stack_rounds_once_not_once_per_layer(self):
        # Two .5 white layers over black: 127.5, then 191.25 -> #BF.
        # Rounding each step instead would give 128 then 191.5 -> #C0.
        self.assertEqual(
            composite_stack("#000000", "rgba(255, 255, 255, .5)", "rgba(255, 255, 255, .5)"),
            "#BFBFBF",
        )

    def test_composite_stack_refuses_a_translucent_base(self):
        with self.assertRaises(ValueError):
            composite_stack("rgba(10, 35, 42, .55)", "rgba(255, 255, 255, .5)")

    def test_relative_luminance_refuses_a_translucent_color(self):
        # The whole point: a translucent token must not be measurable as
        # if its alpha were 1. This is the silent-skip failure mode from
        # the module docstring, converted into a loud one.
        with self.assertRaises(ValueError):
            relative_luminance("rgba(230, 244, 255, .72)")
        self.assertGreater(relative_luminance("rgb(230, 244, 255)"), 0.5)


class TokenParsingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tokens = parse_tokens(_TOKENS_PATH)

    def test_translucent_ocean_tokens_are_now_parsed_at_all(self):
        # Before this stage every one of these was absent from the dict.
        for name in _SURFACE_LAYERS + _TEXT_TIERS:
            self.assertIn(f"--ocean-{name}", self.tokens, name)

    def test_alpha_is_preserved_verbatim_not_normalized_away(self):
        self.assertEqual(self.tokens["--ocean-surface-primary"], "rgba(10, 35, 42, .55)")
        self.assertEqual(self.tokens["--ocean-text-primary"], "rgb(230, 244, 255)")

    def test_opaque_hex_tokens_are_unaffected(self):
        self.assertEqual(self.tokens["--bee-yellow"], "#FFC400")
        self.assertEqual(self.tokens["--ocean-seal-red"], "#E5756C")

    def test_composite_declarations_are_not_mistaken_for_colors(self):
        # --ocean-glow is a box-shadow (`0 24px 70px rgba(1, 8, 14, .5)`)
        # and --ocean-glass-blur is a length - picking the rgba() out of
        # the middle of the first would register a shadow as a surface.
        self.assertNotIn("--ocean-glow", self.tokens)
        self.assertNotIn("--ocean-glass-blur", self.tokens)

    def test_every_parsed_token_is_actually_measurable(self):
        # A future token in a notation parse_color() does not handle
        # must fail here, not disappear from the audit the way the whole
        # ocean family previously did.
        for name, value in self.tokens.items():
            parse_color(value)


class DeepOceanBaseLayerTests(unittest.TestCase):
    """The composite base is read from main.css, not restated here."""

    def test_gradient_is_read_from_the_app_shell_rule(self):
        stops, overlays = _ocean_base_gradient()
        self.assertEqual(len(stops), 3, stops)
        self.assertEqual(len(overlays), 2, overlays)

    def test_linear_stops_are_opaque_and_radial_overlays_are_not(self):
        stops, overlays = _ocean_base_gradient()
        for stop in stops:
            self.assertEqual(parse_color(stop)[3], 1.0, stop)
        for overlay in overlays:
            self.assertLess(parse_color(overlay)[3], 1.0, overlay)

    def test_worst_case_base_is_lighter_than_every_raw_gradient_stop(self):
        stops, _ = _ocean_base_gradient()
        base_luminance = relative_luminance(_worst_case_base())
        for stop in stops:
            self.assertGreater(base_luminance, relative_luminance(stop), stop)

    def test_harness_reproduces_the_recorded_hue_correction_figures(self):
        # tokens.css's CLAUDE-DEEP-OCEAN-HUE-CORRECTION-01 comment
        # records 15.36 / 10.51 / 7.41, measured against the lightest
        # linear stop with the radial overlays left out. Reproducing
        # those numbers on that same backdrop is an independent check on
        # this harness's arithmetic - they were computed elsewhere,
        # before any of this code existed.
        tokens = parse_tokens(_TOKENS_PATH)
        stops, _ = _ocean_base_gradient()
        surface = composite_stack(max(stops, key=relative_luminance), tokens["--ocean-surface-primary"])
        for tier, recorded in (("text-primary", 15.36), ("text-secondary", 10.51), ("text-metadata", 7.41)):
            measured = contrast_ratio(composite_stack(surface, tokens[f"--ocean-{tier}"]), surface)
            self.assertAlmostEqual(measured, recorded, delta=0.1, msg=f"{tier}: {measured:.2f} vs {recorded}")


class DeepOceanCompositedContrastTests(unittest.TestCase):
    """The real audit: every text tier on every glass surface, each
    composited over the worst-case base."""

    @classmethod
    def setUpClass(cls):
        cls.tokens = parse_tokens(_TOKENS_PATH)
        cls.base = _worst_case_base()
        cls.surfaces = {
            name: composite_stack(cls.base, cls.tokens[f"--ocean-{name}"])
            for name in _SURFACE_LAYERS
        }

    def _ratio(self, fg_token: str, surface_name: str) -> float:
        surface = self.surfaces[surface_name]
        return contrast_ratio(composite_stack(surface, self.tokens[fg_token]), surface)

    def test_every_text_tier_meets_aa_against_every_glass_surface(self):
        failures = []
        for tier in _TEXT_TIERS:
            for surface_name in _SURFACE_LAYERS:
                ratio = self._ratio(f"--ocean-{tier}", surface_name)
                if ratio < 4.5:
                    failures.append(
                        f"Deep Ocean {tier} ({self.tokens['--ocean-' + tier]}) on {surface_name} "
                        f"({self.surfaces[surface_name]} composited over {self.base}): "
                        f"{ratio:.2f}:1 (need 4.5:1)"
                    )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_deep_ocean_foreground_is_light_and_readable(self):
        # Same two assertions the three opaque dark modes are held to
        # (test_p40vw8qa_theme_foreground_contrast.py): AAA on the
        # primary panel surface, and a genuinely light foreground.
        self.assertGreaterEqual(self._ratio("--ocean-text-primary", "surface-primary"), 7.0)
        self.assertGreater(relative_luminance(self.tokens["--ocean-text-primary"]), 0.5)

    def test_metadata_tier_stays_quieter_than_secondary_tier(self):
        self.assertLess(
            self._ratio("--ocean-text-metadata", "surface-primary"),
            self._ratio("--ocean-text-secondary", "surface-primary"),
        )

    def test_every_accent_meets_3_to_1_on_canvas_and_surface_primary(self):
        failures = []
        for accent in _ACCENTS:
            for surface_name in ("canvas", "surface-primary"):
                ratio = self._ratio(f"--ocean-{accent}", surface_name)
                if ratio < 3.0:
                    failures.append(
                        f"Deep Ocean {accent} ({self.tokens['--ocean-' + accent]}) on "
                        f"{surface_name} ({self.surfaces[surface_name]}): {ratio:.2f}:1"
                    )
        self.assertEqual(failures, [], "\n".join(failures))

    def test_document_tab_colors_meet_3_to_1_on_the_display_surface(self):
        failures = []
        for hue in ("gold", "turquoise", "lapis", "terracotta", "green", "purple"):
            for surface_name in ("canvas", "surface-primary"):
                ratio = self._ratio(f"--ocean-tabcolor-{hue}", surface_name)
                if ratio < 3.0:
                    failures.append(f"Deep Ocean tabcolor-{hue} on {surface_name}: {ratio:.2f}:1")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_brand_mark_meets_the_stricter_4_5_floor(self):
        # check_contrast.py's REQUIRED_PAIRINGS holds the other four
        # themes' --*-brand-gold to 4.5 ("small, always-visible prose-
        # adjacent text, not an occasional badge"). Deep Ocean's is
        # absent from that list because its value is `var(--bee-yellow)`,
        # not a literal - resolved one level here rather than restated,
        # so a change to either token is caught.
        raw = re.search(
            r"--ocean-brand-gold:\s*var\((--[a-zA-Z0-9-]+)\)\s*;",
            _TOKENS_PATH.read_text(encoding="utf-8"),
        )
        self.assertIsNotNone(raw, "--ocean-brand-gold is no longer a var() reference")
        gold = self.tokens[raw.group(1)]
        for surface_name in ("canvas", "surface-primary"):
            surface = self.surfaces[surface_name]
            ratio = contrast_ratio(composite_stack(surface, gold), surface)
            self.assertGreaterEqual(ratio, 4.5, f"brand mark on {surface_name}: {ratio:.2f}:1")


if __name__ == "__main__":
    unittest.main()
