"""
CLAUDE-P40-VW8-QA-R3 - Restore Distinct Dark, Tinted and Light Appearance
Modes.

Root cause, found by direct investigation (not guessed): CSS comments
cannot contain a literal `*/` ANYWHERE in their text, including inside
ordinary prose - a comment this stage's own earlier Theme Foreground
Contrast Addendum added to static/css/tokens.css read "...the
--text-*/--canvas/--surface-primary names it reads are the Light..." -
the adjacent `*` (end of a wildcard-notation token name) and `/` (a
separator) accidentally formed a literal `*/`, which every real CSS
parser (not just a naive one) treats as the comment's actual end. That
silently truncated a much longer intended comment mid-sentence,
demoting everything after it - including the real `:root { --dark-
canvas: ... }` block a few lines later - to un-parseable "selector"
text, which a browser's CSS error recovery then discards as one
invalid rule. Net effect: every `--dark-*`/`--tint-*` token this
specific comment's premature termination swallowed was NEVER DEFINED
in the browser's custom-property registry at all - `var(--dark-canvas)`
inside `.app-main.appearance-dark` etc. then resolved to nothing,
falling back to `background`'s initial value (transparent), letting
the Light canvas underneath show through. Exactly "Dark and Tinted
appear the same" / "the application remains visually Light" - the
product owner's own reported symptom, and NOT a bug in the JS toggle
logic (verified separately, by actually EXECUTING the real script
against a faithful DOM simulation - see the dedicated class below) or
in cascade specificity (also verified - the compound `.app-main.
appearance-dark` selector is correctly higher-specificity than the
plain `.app-main` base rule).

A second, pre-existing (not introduced this session, but real and now
also fixed) instance of the exact same defect already existed at
tokens.css's own "visual pressure" comment ("--review-state-*/
--evidence-*/verdict badge").

Fixed by inserting a space between the wildcard `*` and the following
`/` in both comments (`--text-* / --canvas` instead of `--text-*/
--canvas`) - a wording change only, zero effect on any token VALUE.

This file's real contribution is the regression guard: a comment-
boundary integrity check that would have caught this before it ever
shipped, plus a computed-value check that proves Light/Dark/Tinted
resolve to genuinely distinct background/foreground pairs - not merely
that the right radio button ends up checked (checked-state was never
the bug; the addendum's own explicit instruction is not to accept a
test that only proves that).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TOKENS_CSS_PATH = _REPO_ROOT / "static" / "css" / "tokens.css"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"


def _real_comment_spans(css_source: str) -> list[tuple[int, int]]:
    """Simulates exactly how a real (non-nested-comment) CSS tokenizer
    scans /* ... */ - find the FIRST '*/' after every '/*', not the
    intended/logical one. This is deliberately the SAME naive algorithm
    a browser uses (CSS comments cannot nest, by spec), which is
    exactly what makes an accidental mid-prose '*/' dangerous."""
    spans = []
    i, n = 0, len(css_source)
    while i < n - 1:
        if css_source[i] == "/" and css_source[i + 1] == "*":
            end = css_source.find("*/", i + 2)
            if end == -1:
                spans.append((i, n))
                break
            spans.append((i, end + 2))
            i = end + 2
        else:
            i += 1
    return spans


def _outside_comment_source(css_source: str) -> str:
    """Everything NOT inside a (correctly, non-nested-comment-scanned)
    comment span - i.e. what a real browser would actually try to parse
    as CSS rules. If a comment is truncated early by an accidental
    '*/', the "rest" of what the author intended as comment prose ends
    up IN this string, mixed in with real selectors/declarations - the
    structural signature this test looks for."""
    spans = _real_comment_spans(css_source)
    out = []
    cursor = 0
    for start, end in spans:
        out.append(css_source[cursor:start])
        cursor = end
    out.append(css_source[cursor:])
    return "".join(out)


class CommentBoundaryIntegrityTests(unittest.TestCase):
    """The actual regression guard: would have failed before this
    stage's fix, passes after it. Prevents this exact bug class (an
    accidental literal '*/' inside comment prose silently truncating a
    much longer intended comment) from recurring in either stylesheet."""

    def test_tokens_css_has_no_prematurely_terminated_comment(self):
        self._assert_no_orphaned_css_root_or_rule_tokens(_TOKENS_CSS_PATH)

    def test_main_css_has_no_prematurely_terminated_comment(self):
        self._assert_no_orphaned_css_root_or_rule_tokens(_MAIN_CSS_PATH)

    def _assert_no_orphaned_css_root_or_rule_tokens(self, path: Path):
        source = path.read_text(encoding="utf-8")
        outside = _outside_comment_source(source)
        # If a comment is truncated early, the leftover fragment of its
        # own prose - ordinary sentences - ends up sitting in "real CSS"
        # territory. Prose reliably contains words no legitimate CSS
        # selector/declaration ever contains outside a comment/string;
        # their presence outside every real comment span is the direct
        # signature of exactly this bug.
        prose_markers = (" the ", " and ", " this ", " that ", " for ", " is ", " was ")
        offenders = [m for m in prose_markers if m in outside]
        self.assertEqual(
            offenders, [],
            f"{path.name}: prose text found outside any comment span - a comment is being "
            f"terminated early by an accidental literal '*/' inside its own text. Offending "
            f"markers: {offenders}",
        )

    def test_every_dark_and_tint_token_is_actually_defined_at_root_scope(self):
        # Direct, end-to-end proof that the specific tokens this bug
        # swallowed are genuinely present as real :root declarations -
        # not just "no prose leaked," but "the tokens are really there."
        source = _TOKENS_CSS_PATH.read_text(encoding="utf-8")
        outside = _outside_comment_source(source)
        # Every actual CSS declaration (a real one, never inside a
        # comment) is outside every comment span by construction - scan
        # THAT text for the token definitions.
        for token in (
            "--dark-canvas", "--dark-surface-primary", "--dark-text-primary",
            "--tint-canvas", "--tint-surface-primary", "--tint-text-primary",
        ):
            self.assertIn(f"{token}:", outside, f"{token} is not defined outside any comment span")


class ComputedValueDistinctnessTests(unittest.TestCase):
    """Not 'is the Dark radio checked' - the actual computed background/
    color a browser would resolve for each surface x mode combination,
    via a real (small, but faithful) CSS custom-property cascade
    simulation over the ACTUAL shipped files. Proves Light, Dark, and
    Tinted are genuinely, visibly distinct - the addendum's own explicit
    requirement."""

    @classmethod
    def setUpClass(cls):
        tokens_source = re.sub(r"/\*.*?\*/", "", _TOKENS_CSS_PATH.read_text(encoding="utf-8"), flags=re.DOTALL)
        main_source = re.sub(r"/\*.*?\*/", "", _MAIN_CSS_PATH.read_text(encoding="utf-8"), flags=re.DOTALL)
        # Safe to use the simple (non-nested-comment-aware) stripper
        # here ONLY because CommentBoundaryIntegrityTests above already
        # proves no comment truncates early in the real files - by the
        # time this class runs, source and stripped-source agree.
        cls.rules = cls._parse_rules(tokens_source) + cls._parse_rules(main_source)

    @staticmethod
    def _parse_rules(css: str) -> list[tuple[str, dict]]:
        rules = []
        for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css, re.DOTALL):
            selector = m.group(1).strip()
            decls = {}
            for decl in m.group(2).split(";"):
                decl = decl.strip()
                if ":" not in decl:
                    continue
                prop, _, value = decl.partition(":")
                decls[prop.strip()] = value.strip()
            rules.append((selector, decls))
        return rules

    def _vars_for(self, class_list: set[str]) -> dict[str, str]:
        scope = {}
        for selector, decls in self.rules:
            for sel in selector.split(","):
                sel = sel.strip()
                if sel == ":root":
                    matches = True
                else:
                    classes = re.findall(r"\.([a-zA-Z0-9_-]+)", sel)
                    matches = bool(classes) and all(c in class_list for c in classes)
                if matches:
                    for prop, value in decls.items():
                        if prop.startswith("--"):
                            scope[prop] = value
        return scope

    def _resolve(self, value: str, scope: dict, depth: int = 0) -> str:
        if depth > 20:
            return value
        m = re.fullmatch(r"var\((--[a-zA-Z0-9_-]+)\)", value.strip())
        if not m:
            return value
        name = m.group(1)
        if name not in scope:
            return f"UNRESOLVED({name})"
        return self._resolve(scope[name], scope, depth + 1)

    def _computed_background_color(self, surface_class: str, mode_class: str | None) -> tuple[str, str]:
        class_list = {surface_class} | ({mode_class} if mode_class else set())
        scope = self._vars_for(class_list)
        bg = color = None
        for selector, decls in self.rules:
            for sel in selector.split(","):
                sel = sel.strip()
                classes = re.findall(r"\.([a-zA-Z0-9_-]+)", sel)
                if classes and all(c in class_list for c in classes):
                    if "background" in decls:
                        bg = decls["background"]
                    if "color" in decls:
                        color = decls["color"]
        return (
            self._resolve(bg, scope) if bg else None,
            self._resolve(color, scope) if color else None,
        )

    _SURFACES = ("workspace-topbar", "launcher-panel", "app-main", "workspace-pane-toolbox", "chat-region")

    def test_dark_mode_resolves_to_the_approved_black_background_on_every_surface(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): .appearance-dark is
        # "Black" - a brief interim "Graphite" (#0E1116, neutral near-
        # black) was itself corrected back to true #000000 per explicit
        # product-owner follow-up ("Do not use Graphite... must appear
        # flat and matte"), restoring VW6's own original literal value.
        for surface in self._SURFACES:
            bg, _color = self._computed_background_color(surface, "appearance-dark")
            self.assertIsNotNone(bg, surface)
            self.assertNotIn("UNRESOLVED", bg, f"{surface}.appearance-dark background did not resolve: {bg}")
            self.assertEqual(bg.upper(), "#000000", f"{surface}.appearance-dark (Black) background is {bg}, expected #000000")

    def test_dark_mode_resolves_to_the_approved_warm_off_white_foreground_on_every_surface(self):
        # CLAUDE-P40-VW8-QA: primary dark-theme text is the shared warm
        # off-white #E8E4DC (product-owner spec), not pure #FFFFFF - the
        # one part of the interim Graphite revision the follow-up
        # correction explicitly kept.
        for surface in self._SURFACES:
            _bg, color = self._computed_background_color(surface, "appearance-dark")
            self.assertIsNotNone(color, surface)
            self.assertNotIn("UNRESOLVED", color)
            self.assertEqual(color.upper(), "#E8E4DC", f"{surface}.appearance-dark (Black) color is {color}, expected #E8E4DC")

    def test_tinted_mode_resolves_to_a_genuinely_dark_navy_background_on_every_surface(self):
        # CLAUDE-P40-VW8-QA: .appearance-tinted is now "Midnight Blue" -
        # a DEEP navy dark theme (#0B1B2B, product-owner spec), the
        # opposite direction from the earlier VW6/VW8-QA light-navy
        # "Tinted" this test used to pin (r > 180 / "genuinely light").
        for surface in self._SURFACES:
            bg, _color = self._computed_background_color(surface, "appearance-tinted")
            self.assertIsNotNone(bg, surface)
            self.assertNotIn("UNRESOLVED", bg)
            r = int(bg[1:3], 16)
            self.assertLess(r, 40, f"{surface}.appearance-tinted (Midnight Blue) background {bg} is not dark")

    def test_dark_and_tinted_backgrounds_are_never_the_same_value(self):
        for surface in self._SURFACES:
            dark_bg, _ = self._computed_background_color(surface, "appearance-dark")
            tint_bg, _ = self._computed_background_color(surface, "appearance-tinted")
            self.assertNotEqual(dark_bg, tint_bg, f"{surface}: Dark and Tinted resolve to the identical background {dark_bg}")

    def test_dark_and_tinted_foregrounds_are_deliberately_the_same_shared_family(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set) inverted this stage's
        # own original invariant on purpose: "Continue using readable
        # warm off-white foreground text on the dark themes" and "derive
        # the complete supporting palette from shared tokens" together
        # mean Black/Midnight Blue/Deep Forest share ONE text family
        # (#E8E4DC and its derived tiers) by design, not three
        # independently-tuned ones - distinctness between the three dark
        # themes comes entirely from their BACKGROUNDS (see
        # test_dark_and_tinted_backgrounds_are_never_the_same_value
        # above, still real and still checked), never their foregrounds.
        for surface in self._SURFACES:
            _, dark_color = self._computed_background_color(surface, "appearance-dark")
            _, tint_color = self._computed_background_color(surface, "appearance-tinted")
            self.assertEqual(dark_color, tint_color, f"{surface}: Black and Midnight Blue must share the same warm off-white text family")

    def test_light_dark_and_tinted_are_three_genuinely_distinct_backgrounds(self):
        for surface in self._SURFACES:
            # Light is the surface's own base rule (no mode class).
            light_scope = self._vars_for({surface})
            light_bg_raw = next(
                (decls.get("background") for sel, decls in self.rules
                 if sel.strip() == surface.replace("-", "-") and "background" in decls),
                None,
            )
            # Fall back to --surface-primary directly if the base rule
            # itself declares no literal background (matches .app-main's
            # own real shape - a pure layout wrapper).
            light_bg = self._resolve(light_bg_raw, light_scope) if light_bg_raw else self._resolve("var(--surface-primary)", light_scope)
            dark_bg, _ = self._computed_background_color(surface, "appearance-dark")
            tint_bg, _ = self._computed_background_color(surface, "appearance-tinted")
            values = {light_bg, dark_bg, tint_bg}
            self.assertEqual(len(values), 3, f"{surface}: expected 3 distinct backgrounds, got {values}")


class JavaScriptToggleLogicTests(unittest.TestCase):
    """The JS class-toggle mechanism itself was verified correct during
    this stage's own investigation (executed against a faithful DOM
    simulation - not this repository's normal test infrastructure, so
    not re-run here) - this class instead pins down the structural
    properties that made that verification meaningful, as a permanent
    source-level guard."""

    def setUp(self):
        self.source = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_apply_mode_toggles_dark_and_tinted_as_mutually_exclusive(self):
        # CLAUDE-P40-VW8-QA (Approved Theme Set): applyMode moved to
        # window.__applyStoredAppearanceMode (an earlier script block,
        # shared with the pre-paint pass) and now checks the current
        # mode-value vocabulary (black/midnight-blue), not the old
        # dark/tinted stored values.
        script_start = self.source.index("window.__applyStoredAppearanceMode = function (el, mode)")
        script = self.source[script_start:script_start + 400]
        self.assertIn("classList.toggle('appearance-dark', mode === 'black')", script)
        self.assertIn("classList.toggle('appearance-tinted', mode === 'midnight-blue')", script)

    def test_set_surface_mode_is_the_single_place_a_mode_is_ever_applied(self):
        # Exactly one CALL site of applyMode (the definition itself is
        # the other match) - the "All" handler and individual radio
        # handlers both route through setSurfaceMode, never a second,
        # divergent code path.
        self.assertEqual(self.source.count("if (el) applyMode(el, mode)"), 1)

    def test_all_handler_applies_to_every_one_of_the_five_surfaces(self):
        script_start = self.source.index("allRadios.forEach(function (radio) {\n                radio.addEventListener")
        script = self.source[script_start:script_start + 400]
        self.assertIn("surfaceKeys.forEach(function (key) { setSurfaceMode(key, mode); })", script)

    def test_viewer_iframe_content_is_never_recolored_by_appearance_css(self):
        # Section: "Do not invert, recolor or otherwise alter the
        # original contents of an uploaded PDF, drawing or image." - no
        # filter/invert/hue-rotate CSS rule targets the embedded
        # document viewer at all.
        main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("filter: invert", main_css)
        self.assertNotIn("filter:invert", main_css)


if __name__ == "__main__":
    unittest.main()
