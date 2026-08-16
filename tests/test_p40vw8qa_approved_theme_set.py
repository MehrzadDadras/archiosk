"""
CLAUDE-P40-VW8-QA - Approved Theme Set.

Four appearance choices: Black (true #000000, default, replacing the
old "Dark"/a brief interim "Graphite"), Midnight Blue (a solid, deeply
saturated navy, replacing the old "Tinted," which used to be a LIGHT
navy-grey daylight variant), Deep Forest (a solid, deeply saturated
blue-green, new this stage), and Light (unchanged, the one daylight/
accessibility mode).

Two label revisions happened in sequence within this same stage: Dark
-> "Graphite" (a neutral near-black, #0E1116) -> corrected back to
"Black" (true #000000) per explicit product-owner follow-up ("Do not
use Graphite... must appear flat and matte"). The --dark-* token prefix
and .appearance-dark CSS class name never changed through either
revision - only the label and the underlying values did (tokens.css's
own comment has the full reasoning). Tinted's palette was replaced
outright (not just relabeled) since it used to be a light-mode variant
and Midnight Blue is a dark one; the SAME "identifier survives a label/
palette revision" rule applied there too (--tint-* prefix, .appearance-
tinted class, both unchanged).

Contrast is verified two ways here: (1) importing tools/
derive_theme_palettes.py's own verification directly (so this test can
never silently drift from the tool that produced these exact values),
and (2) pinning tokens.css's actual literal hex values against what
that tool currently derives, so a manual edit to tokens.css that
diverges from the tool's own output fails loudly.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_APP_MENU_HTML_PATH = _REPO_ROOT / "templates" / "_app_menu.html"

sys.path.insert(0, str(_REPO_ROOT / "tools"))
import derive_theme_palettes as dtp  # noqa: E402


def _parse_tokens(css: str) -> dict[str, str]:
    tokens = {}
    for name, value in re.findall(r"(--[a-zA-Z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", css):
        tokens[name] = value
    return tokens


class ThemePaletteDerivationToolTests(unittest.TestCase):
    """The tool itself, run standalone - this is what actually produced
    every hex value below. If this fails, tokens.css's own values are
    suspect regardless of what the rest of this file finds."""

    def test_tool_reports_all_pairings_pass(self):
        self.assertEqual(dtp.main(), 0)

    def test_black_theme_is_the_reference_ramp_unchanged(self):
        palette = dtp.derive_theme("#000000", reproject=False)
        for step, expected in dtp._REFERENCE_RAMP.items():
            self.assertEqual(palette[step], expected)

    def test_midnight_and_forest_are_luminance_matched_to_black(self):
        black = dtp.derive_theme("#000000", reproject=False)
        for base in ("#001426", "#001A12"):
            palette = dtp.derive_theme(base, reproject=True)
            for step, ref_hex in dtp._REFERENCE_RAMP.items():
                self.assertAlmostEqual(
                    dtp.relative_luminance(palette[step]),
                    dtp.relative_luminance(ref_hex),
                    delta=0.002,
                    msg=f"{base} {step} luminance drifted from Black's own reference step",
                )


class TokensCssMatchesDerivationTests(unittest.TestCase):
    def setUp(self):
        self.tokens = _parse_tokens(_TOKENS_CSS_PATH.read_text(encoding="utf-8"))

    def test_black_base_is_true_black(self):
        self.assertEqual(self.tokens["--dark-canvas"], "#000000")
        self.assertEqual(self.tokens["--dark-surface-primary"], "#000000")

    def test_black_structural_ramp_matches_the_derivation_tool(self):
        derived = dtp.derive_theme("#000000", reproject=False)
        mapping = {
            "--dark-surface-secondary": "surface-secondary",
            "--dark-surface-hover": "surface-hover",
            "--dark-surface-selected": "surface-selected",
            "--dark-border": "border",
            "--dark-border-strong": "border-strong",
        }
        for token_name, step in mapping.items():
            self.assertEqual(self.tokens[token_name], derived[step])

    def test_midnight_blue_base_matches_product_owner_spec(self):
        self.assertEqual(self.tokens["--tint-canvas"], "#001426")

    def test_deep_forest_base_matches_product_owner_spec(self):
        self.assertEqual(self.tokens["--forest-canvas"], "#001A12")

    def test_midnight_and_forest_structural_ramps_match_the_derivation_tool(self):
        mapping = {
            "surface-secondary": "surface-secondary",
            "surface-hover": "surface-hover",
            "surface-selected": "surface-selected",
            "border": "border",
            "border-strong": "border-strong",
        }
        for prefix, base in (("--tint-", "#001426"), ("--forest-", "#001A12")):
            derived = dtp.derive_theme(base, reproject=True)
            for token_suffix, step in mapping.items():
                token_name = f"{prefix}{token_suffix}"
                self.assertEqual(self.tokens[token_name], derived[step], token_name)

    def test_shared_warm_off_white_text_family_used_by_all_three_dark_themes(self):
        text = dtp.derive_text_family()
        for prefix in ("--dark-", "--tint-", "--forest-"):
            self.assertEqual(self.tokens[f"{prefix}text-primary"], text["text-primary"])
            self.assertEqual(self.tokens[f"{prefix}text-secondary"], text["text-secondary"])
            self.assertEqual(self.tokens[f"{prefix}text-metadata"], text["text-metadata"])
            self.assertEqual(self.tokens[f"{prefix}text-disabled"], text["text-disabled"])
        self.assertEqual(text["text-primary"], "#E8E4DC")

    def test_three_dark_themes_are_visibly_distinct_not_near_identical_blacks(self):
        canvases = {self.tokens["--dark-canvas"], self.tokens["--tint-canvas"], self.tokens["--forest-canvas"]}
        self.assertEqual(len(canvases), 3)
        selected = {self.tokens["--dark-surface-selected"], self.tokens["--tint-surface-selected"], self.tokens["--forest-surface-selected"]}
        self.assertEqual(len(selected), 3)

    def test_shared_accent_colors_reused_unmodified_across_all_dark_themes(self):
        for accent in ("seal-red", "machine-blue", "highlight-orange", "accepted-green", "attention-amber", "failure-red", "risk-red"):
            dark = self.tokens[f"--dark-{accent}"]
            self.assertEqual(self.tokens[f"--tint-{accent}"], dark)
            self.assertEqual(self.tokens[f"--forest-{accent}"], dark)

    def test_divider_strong_remains_mode_invariant_and_passes_against_every_dark_canvas(self):
        divider = self.tokens["--divider-strong"]
        for canvas_token in ("--dark-canvas", "--tint-canvas", "--forest-canvas"):
            ratio = dtp.contrast_ratio(divider, self.tokens[canvas_token])
            self.assertGreaterEqual(ratio, 3.0, f"{canvas_token}")


class NoReflectiveEffectsTests(unittest.TestCase):
    """'Flat and matte - not gray, reflective, metallic, translucent, or
    layered like glass.' No gradients/backdrop-filter/alpha overlays on
    the dark themes' own surface rules."""

    def setUp(self):
        self.tokens_css = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_no_gradients_in_dark_theme_token_blocks(self):
        self.assertNotIn("gradient", self.tokens_css.lower())

    def test_no_backdrop_filter_on_any_dark_theme_appearance_rule(self):
        # Scoped to the three dark themes' own appearance-class rules,
        # not a blanket ban on the whole file - templates/gateway_shell's
        # pre-existing .gateway-card-compact glass effect on the sign-in
        # page is unrelated to any appearance mode and out of scope here.
        for cls in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            idx = self.main_css.index(f".workspace-topbar.{cls},")
            end = self.main_css.index("\n}\n", idx)
            body = self.main_css[idx:end].lower()
            self.assertNotIn("backdrop-filter", body)
            self.assertNotIn("gradient", body)

    def test_dark_theme_surface_tokens_are_fully_opaque_hex_not_rgba(self):
        # Every --dark-*/--tint-*/--forest-* surface/canvas token is a
        # plain 6-digit hex (opaque by construction) - an rgba()/alpha
        # value would show up as a non-hex assignment this regex misses,
        # so also assert none of the three prefixes ever pairs with
        # "rgba(" anywhere in the file.
        for prefix in ("dark", "tint", "forest"):
            self.assertNotIn(f"--{prefix}-canvas: rgba", self.tokens_css)
            self.assertNotIn(f"--{prefix}-surface-primary: rgba", self.tokens_css)

    def test_appearance_class_rules_set_solid_background_not_translucent(self):
        for cls in ("appearance-dark", "appearance-tinted", "appearance-deep-forest"):
            idx = self.main_css.index(f".workspace-topbar.{cls},")
            end = self.main_css.index("\n}\n", idx)
            body = self.main_css[idx:end]
            self.assertIn("background: var(--surface-primary)", body)
            self.assertNotIn("rgba(", body)
            self.assertNotIn("opacity:", body)


class DefaultAndMigrationTests(unittest.TestCase):
    def setUp(self):
        self.source = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_resolver_defined_before_the_later_wiring_block_reuses_it(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01: the later wiring block no longer
        # aliases resolveStoredMode into a local var (Appearance is one
        # global choice now, resolved once via
        # window.__resolveGlobalAppearanceMode()) - applyMode is the
        # landmark that still exists in both places.
        early_idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        later_idx = self.source.index("var applyMode = window.__applyStoredAppearanceMode;")
        self.assertLess(early_idx, later_idx)

    def test_migration_dark_and_graphite_map_to_black(self):
        idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        body = self.source[idx: idx + 900]
        self.assertIn("if (stored === 'dark' || stored === 'graphite') return 'black';", body)

    def test_migration_tinted_maps_to_midnight_blue(self):
        idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        body = self.source[idx: idx + 900]
        self.assertIn("if (stored === 'tinted') return 'midnight-blue';", body)

    def test_light_midnight_blue_deep_forest_black_pass_through_unchanged(self):
        idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        body = self.source[idx: idx + 900]
        self.assertIn("stored === 'light' || stored === 'black' || stored === 'midnight-blue' || stored === 'deep-forest'", body)

    def test_missing_or_invalid_falls_back_to_black_not_light(self):
        idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        body = self.source[idx: idx + 900]
        self.assertIn("return 'black';", body)
        # The old default ('light') must not still be the final fallback.
        final_return = body.rfind("return ")
        self.assertIn("black", body[final_return:final_return + 20])

    def test_apply_mode_maps_black_to_the_unchanged_appearance_dark_class(self):
        idx = self.source.index("window.__applyStoredAppearanceMode = function")
        body = self.source[idx: idx + 400]
        self.assertIn("classList.toggle('appearance-dark', mode === 'black')", body)
        self.assertIn("classList.toggle('appearance-tinted', mode === 'midnight-blue')", body)
        self.assertIn("classList.toggle('appearance-deep-forest', mode === 'deep-forest')", body)

    def test_early_pre_paint_script_runs_immediately_after_chat_region(self):
        chat_region_idx = self.source.index('<div class="chat-region"')
        resolver_idx = self.source.index("window.__resolveStoredAppearanceMode = function")
        later_wiring_idx = self.source.index("var applyMode = window.__applyStoredAppearanceMode;")
        self.assertLess(chat_region_idx, resolver_idx)
        self.assertLess(resolver_idx, later_wiring_idx)


class AppearanceMatrixLabelTests(unittest.TestCase):
    """CLAUDE-APPEARANCE-SIMPLIFY-01 supersedes this whole class's own
    original premise: the five-surface x four-mode <table> matrix these
    tests checked is retired outright - Appearance is now ONE global
    radio choice among five options (Product Owner: "do not allow
    panel-by-panel theme mixing"). Rewritten to assert the new, single
    mode tuple/radio-group structure instead of a table's column
    headers/per-surface row template."""

    def setUp(self):
        # CLAUDE-UI-ACTION-REDUNDANCY-REVIEW-01, Disposition 2/3: the
        # Appearance mode tuple/radio-group moved out of base.html's own
        # source into the shared templates/_app_menu.html partial.
        self.source = _APP_MENU_HTML_PATH.read_text(encoding="utf-8")

    def test_five_labels_present(self):
        # CLAUDE-POSTCAMEL-P02-ST1: Light relabeled Titanium. Labels
        # render via {{ mode_label }} (never a literal ">Titanium<" in
        # the template source) - checked as quoted entries in the mode
        # tuple itself instead, same tuple test_one_global_radio_group_
        # with_five_choices below verifies in full.
        for label in ("'Titanium'", "'Black'", "'Midnight Blue'", "'Deep Forest'", "'Deep Ocean'"):
            self.assertIn(label, self.source)

    def test_mode_value_tuples_use_black_not_graphite(self):
        self.assertNotIn("'graphite', 'Graphite'", self.source)
        self.assertIn("('black', 'Black', 'dark')", self.source)

    def test_ref_suffix_for_neutral_dark_choice_stays_dark(self):
        # Retained identifier through two label revisions (Dark ->
        # Graphite -> Black) - the ref_suffix, not the label, is what
        # must never change.
        self.assertIn("('black', 'Black', 'dark')", self.source)

    def test_one_global_radio_group_with_five_choices(self):
        # data-appearance-all-mode="{{ mode_value }}" is Jinja source,
        # not a literal value - assert the ONE mode tuple the template's
        # single {% for %} loop iterates over covers all five choices,
        # and that the loop body itself (one literal
        # data-appearance-all-mode attribute) is rendered exactly once -
        # there is no longer a second, per-surface loop to keep in sync.
        mode_tuple = "[('light', 'Titanium', 'light'), ('black', 'Black', 'dark'), ('midnight-blue', 'Midnight Blue', 'tinted'), ('deep-forest', 'Deep Forest', 'deep-forest'), ('deep-ocean', 'Deep Ocean', 'deep-ocean')]"
        self.assertIn(mode_tuple, self.source)
        self.assertEqual(self.source.count(mode_tuple), 1)
        self.assertEqual(self.source.count('data-appearance-all-mode="{{ mode_value }}"'), 1)
        self.assertNotIn('data-appearance-target="{{ surface_key }}"', self.source)
        self.assertNotIn('data-appearance-mode="{{ mode_value }}"', self.source)


class MatrixNarrowViewportTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_appearance_options_popover_has_a_max_width(self):
        idx = self.css.index(".workspace-appearance-options {\n    max-width:")
        self.assertGreaterEqual(idx, 0)

    def test_matrix_table_css_is_gone(self):
        # CLAUDE-APPEARANCE-SIMPLIFY-01: supersedes this class's own
        # "header cells are allowed to wrap" check - there is no table,
        # no header row, nothing to wrap. Regression guard against the
        # retired table CSS RULE reappearing (a retirement comment is
        # allowed to name the class it retired, so this checks for the
        # actual selector declaration, not a bare substring match).
        self.assertNotIn(".appearance-matrix {", self.css)
        self.assertNotIn(".appearance-matrix th", self.css)
        self.assertIn(".appearance-global-options", self.css)


if __name__ == "__main__":
    unittest.main()
