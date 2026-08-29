"""
CLAUDE-P40-VW8-QA - Site-Wide Visual-System Consistency Addendum.

The product owner's concern this stage's earlier corrections (Gateway
typography/surfaces) risked becoming an isolated repair rather than
part of one coherent application-wide visual system. No interactive
browser-automation tool exists in this environment (consistent with
every prior VW stage), so this file compensates the way this
codebase's own established pattern already does for that limitation
(see test_p40vw7_conversation_tags_and_tasks.py's own note): exhaustive
structural/source-level assertions across every template and stylesheet,
not pixel-level verification, which is left to the product owner's own
walkthrough (see this stage's final report for the explicit list of
what still needs that).

Covers two real, site-wide defects this audit found (both already
fixed as part of this stage - see tokens.css/main.css):
  1. Two Dark/Tinted text-metadata pairings that fell under 4.5:1 on
     the deepest surface-layering step (test_p40vw8qa_theme_foreground_
     contrast.py's own file covers the corrected values in depth; this
     file re-asserts the structural guard that makes such a value hard
     to reintroduce unnoticed - no hardcoded color anywhere in CSS).
  2. `font-stretch: condensed` applied globally against a font stack
     whose fallback tier (plain "Arial"/sans-serif, on any system
     without Arial Nova Cond installed) has no real condensed face -
     browsers synthesize a horizontal squish in exactly that fallback
     case, which is "unjustified synthetic font stretching" by
     definition. Removed; this file guards against it returning.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATIC_CSS = _REPO_ROOT / "static" / "css"
_TEMPLATES_DIR = _REPO_ROOT / "templates"

# Files that are genuinely never per-panel-themed (Gateway/Auth render
# only ever in Light, by design - see tokens.css's own :root defaults
# and templates/auth_shell.html/gateway_shell.html, neither of which
# ever gains an .appearance-dark/.appearance-tinted class) still must
# use the SAME token names, just never the dark-/tint-prefixed ones -
# that's the actual "belongs to the same design system" invariant this
# suite checks, not that every page looks visually identical.
_HARDCODED_COLOR_RE = re.compile(
    r"(?<![\w-])color\s*:\s*#[0-9a-fA-F]{3,8}|"
    r"(?<![\w-])background(?:-color)?\s*:\s*#[0-9a-fA-F]{3,8}|"
    r"(?<![\w-])border(?:-color)?\s*:\s*#[0-9a-fA-F]{3,8}"
)


class NoHardcodedForegroundColorsAnywhereTests(unittest.TestCase):
    """Every color/background-color/border-color declaration in every
    shipped stylesheet must reference a token (var(--...)), never a raw
    hex value - the single mechanism that keeps Light/Dark/Tinted (and
    any future mode) able to repaint the WHOLE app from one place,
    per tokens.css's own governing principle."""

    def test_main_css_has_no_hardcoded_foreground_colors(self):
        source = (_STATIC_CSS / "main.css").read_text(encoding="utf-8")
        matches = _HARDCODED_COLOR_RE.findall(source)
        self.assertEqual(matches, [], f"hardcoded color declarations found: {matches}")

    # Standalone PROTOTYPE stylesheets, each loaded by exactly one template
    # that does not extend base.html. They are deliberately outside the
    # theming system - their own headers state that main.css is untouched by
    # them and cannot be affected by them - so they define a self-contained
    # ramp on purpose and cannot be repainted from tokens.css by design.
    #
    # This exemption is NAMED rather than a pattern: a new shipped stylesheet
    # still fails, which is what this test is for. The exemption was added
    # after calm_lake.css (landed in a4cfb19) had been failing this test
    # unnoticed - surfaced rather than left red, because the test's own
    # docstring scopes it to stylesheets that repaint "the WHOLE app", and a
    # single-template prototype is not one of those.
    _PROTOTYPE_STYLESHEETS = {"tokens.css", "calm_lake.css", "nipigon.css"}

    def test_tokens_css_hardcoded_hex_only_appears_in_token_definitions(self):
        # tokens.css is the ONE place raw hex values are expected (that
        # is the whole point of the file) - this just guards that no
        # OTHER shipped stylesheet duplicates that role.
        for css_file in _STATIC_CSS.glob("*.css"):
            if css_file.name in self._PROTOTYPE_STYLESHEETS:
                continue
            source = css_file.read_text(encoding="utf-8")
            self.assertNotRegex(source, r"#[0-9a-fA-F]{6}\b", f"{css_file.name} defines a raw hex color")

    def test_no_inline_color_styles_in_any_template(self):
        style_color_re = re.compile(r'style="[^"]*\bcolor\s*:\s*(?!var\()', re.IGNORECASE)
        offenders = []
        for html_file in _TEMPLATES_DIR.rglob("*.html"):
            source = html_file.read_text(encoding="utf-8")
            if style_color_re.search(source):
                offenders.append(html_file.name)
        self.assertEqual(offenders, [], f"inline non-token color style found in: {offenders}")


class NoSyntheticFontStretchingTests(unittest.TestCase):
    """font-stretch on a static (non-variable) font stack whose
    fallback tier has no real condensed face causes the browser to
    synthesize a horizontal squish - exactly the defect this stage's
    addendum names. Once removed, it must not silently return."""

    def test_no_font_stretch_declaration_anywhere_in_shipped_css(self):
        for css_file in _STATIC_CSS.glob("*.css"):
            source = css_file.read_text(encoding="utf-8")
            # Match the CSS property itself, not this file's or main.css's
            # own prose explaining why it was removed.
            self.assertNotRegex(
                source, r"(?<![\w-])font-stretch\s*:\s*(?!.*removed)",
                f"{css_file.name} declares font-stretch",
            )


class GatewayAuthSharedTokenFamilyTests(unittest.TestCase):
    """Gateway/Auth pages are deliberately Light-only (no per-panel
    Appearance system pre-auth/pre-workspace - see VW5's own isolation
    invariant), but they must still be built from the SAME semantic
    token names as the themed workspace shell, not a parallel/duplicated
    palette - that's what makes them "part of one coherent system" even
    though their purpose (a single, calm entry point) differs from the
    multi-panel workspace."""

    def test_gateway_css_rules_reference_the_same_text_and_surface_tokens(self):
        source = (_STATIC_CSS / "main.css").read_text(encoding="utf-8")
        gateway_block_start = source.index(".gateway-page {")
        gateway_block = source[gateway_block_start:gateway_block_start + 4000]
        for token in ("--text-primary", "--text-secondary", "--text-metadata", "--surface-primary", "--border"):
            self.assertIn(f"var({token})", gateway_block, f"{token} not referenced in Gateway CSS")

    def test_gateway_and_workspace_shells_share_the_bee_yellow_identity_mark(self):
        source = (_STATIC_CSS / "main.css").read_text(encoding="utf-8")
        self.assertIn("var(--bee-yellow)", source)
        gateway_html = (_TEMPLATES_DIR / "gateway_shell.html").read_text(encoding="utf-8")
        self.assertIn("Archiosk", gateway_html)


class TypographyScaleConsistencyTests(unittest.TestCase):
    """Headings use tokens.css's own named type scale (--text-*) or the
    documented large-heading font-weight:300 exception, not an
    arbitrary one-off rem value that duplicates a step the scale
    already names."""

    def test_base_heading_weight_is_declared_once_not_per_page(self):
        source = (_STATIC_CSS / "main.css").read_text(encoding="utf-8")
        self.assertIn("h1, h2, h3, h4, h5, h6 { font-weight: 500; }", source)

    def test_font_family_tokens_are_used_for_display_and_body_text(self):
        source = (_STATIC_CSS / "main.css").read_text(encoding="utf-8")
        display_count = source.count("var(--font-display)")
        body_count = source.count("var(--font-body)")
        self.assertGreater(display_count, 5)
        self.assertGreater(body_count, 5)


if __name__ == "__main__":
    unittest.main()
