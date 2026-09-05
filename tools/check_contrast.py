"""
Verifies every text/background color pairing in static/css/tokens.css
meets WCAG AA contrast (4.5:1 for normal text, 3:1 for the badge/large-
text pairings named below) - a maintainer-run check, not part of the
running app.

This project's own color-grammar discipline ("readability is the floor,
not the target") was previously verified ad hoc: a throwaway colorsys
script, re-typed from scratch each time a color changed. Reusable now,
so the next color change (or a future named mode/theme file - see
tokens.css's own header) gets checked the same rigorous way without
re-deriving the contrast math.

Both color notations tokens.css actually uses are handled: `#RRGGBB`
and `rgb()`/`rgba()`. The second matters because Deep Ocean's structural
tokens are translucent glass, and alpha is not something a contrast
ratio can be computed from directly - composite_stack() resolves it
against the layer underneath, and relative_luminance() refuses a
translucent color outright rather than quietly measuring it as if its
alpha were 1.

REQUIRED_PAIRINGS below remains a Light-mode subset by design. The
per-theme matrices live with the tests that own them:
tests/test_p40vw8qa_theme_foreground_contrast.py for the three opaque
dark modes, tests/test_deep_ocean_contrast_coverage.py for the
composited Deep Ocean one.

Usage:
    python tools/check_contrast.py [path/to/tokens.css]

Exits non-zero if any required pairing falls below its threshold.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DEFAULT_TOKENS_PATH = Path(__file__).resolve().parents[1] / "static" / "css" / "tokens.css"

# (foreground token, background token, minimum ratio, what this pairing is)
# Every text-* token against the two surfaces it actually appears on
# (canvas directly, and surface-primary for panels/cards/dialogs), plus
# each semantic color against both - these are the pairings this app
# actually renders, not an exhaustive cross-product of every token
# against every other one.
REQUIRED_PAIRINGS = [
    ("--text-primary", "--canvas", 4.5, "primary text on the app background"),
    ("--text-primary", "--surface-primary", 4.5, "primary text on panels/cards"),
    ("--text-secondary", "--canvas", 4.5, "secondary text on the app background"),
    ("--text-secondary", "--surface-primary", 4.5, "secondary text on panels/cards"),
    ("--text-metadata", "--canvas", 4.5, "metadata text on the app background"),
    ("--text-metadata", "--surface-primary", 4.5, "metadata text on panels/cards"),
    ("--seal-red", "--canvas", 3.0, "seal-red accent/badge text"),
    ("--seal-red", "--seal-red-tint", 3.0, "seal-red on its own tint"),
    ("--machine-blue", "--canvas", 3.0, "machine-blue accent/badge text"),
    ("--machine-blue", "--machine-blue-tint", 3.0, "machine-blue on its own tint"),
    ("--highlight-orange", "--surface-primary", 3.0, "highlight-orange badge text"),
    ("--accepted-green", "--canvas", 3.0, "accepted-green accent/badge text"),
    ("--accepted-green", "--accepted-green-tint", 3.0, "accepted-green on its own tint"),
    ("--attention-amber", "--canvas", 3.0, "attention-amber accent/badge text"),
    ("--attention-amber", "--attention-amber-tint", 3.0, "attention-amber on its own tint"),
    ("--failure-red", "--canvas", 3.0, "failure-red accent/badge text"),
    ("--failure-red", "--failure-red-tint", 3.0, "failure-red on its own tint"),
    ("--risk-red", "--canvas", 3.0, "risk-red accent/badge text"),
    ("--risk-red", "--surface-primary", 3.0, "risk-red on panels/cards"),
    ("--risk-red", "--risk-red-tint", 3.0, "risk-red on its own tint"),

    # CLAUDE-P40-DTAB1: curated Document-tab organizational accents -
    # checked as accent/badge text (3.0, same threshold as the other
    # accent colors above) against each theme's own canvas AND
    # surface-primary (a tab sits on the Display surface, not the raw
    # canvas, but both are checked since the tab strip's own background
    # may resolve to either depending on surrounding context).
    ("--tabcolor-gold", "--canvas", 3.0, "tab color: gold (Light)"),
    ("--tabcolor-gold", "--surface-primary", 3.0, "tab color: gold on panels (Light)"),
    ("--tabcolor-turquoise", "--canvas", 3.0, "tab color: turquoise (Light)"),
    ("--tabcolor-turquoise", "--surface-primary", 3.0, "tab color: turquoise on panels (Light)"),
    ("--tabcolor-lapis", "--canvas", 3.0, "tab color: lapis (Light)"),
    ("--tabcolor-lapis", "--surface-primary", 3.0, "tab color: lapis on panels (Light)"),
    ("--tabcolor-terracotta", "--canvas", 3.0, "tab color: terracotta (Light)"),
    ("--tabcolor-terracotta", "--surface-primary", 3.0, "tab color: terracotta on panels (Light)"),
    ("--tabcolor-green", "--canvas", 3.0, "tab color: green (Light)"),
    ("--tabcolor-green", "--surface-primary", 3.0, "tab color: green on panels (Light)"),
    ("--tabcolor-purple", "--canvas", 3.0, "tab color: purple (Light)"),
    ("--tabcolor-purple", "--surface-primary", 3.0, "tab color: purple on panels (Light)"),

    ("--dark-tabcolor-gold", "--dark-canvas", 3.0, "tab color: gold (Black)"),
    ("--dark-tabcolor-turquoise", "--dark-canvas", 3.0, "tab color: turquoise (Black)"),
    ("--dark-tabcolor-lapis", "--dark-canvas", 3.0, "tab color: lapis (Black)"),
    ("--dark-tabcolor-terracotta", "--dark-canvas", 3.0, "tab color: terracotta (Black)"),
    ("--dark-tabcolor-green", "--dark-canvas", 3.0, "tab color: green (Black)"),
    ("--dark-tabcolor-purple", "--dark-canvas", 3.0, "tab color: purple (Black)"),

    ("--tint-tabcolor-gold", "--tint-canvas", 3.0, "tab color: gold (Midnight Blue)"),
    ("--tint-tabcolor-turquoise", "--tint-canvas", 3.0, "tab color: turquoise (Midnight Blue)"),
    ("--tint-tabcolor-lapis", "--tint-canvas", 3.0, "tab color: lapis (Midnight Blue)"),
    ("--tint-tabcolor-terracotta", "--tint-canvas", 3.0, "tab color: terracotta (Midnight Blue)"),
    ("--tint-tabcolor-green", "--tint-canvas", 3.0, "tab color: green (Midnight Blue)"),
    ("--tint-tabcolor-purple", "--tint-canvas", 3.0, "tab color: purple (Midnight Blue)"),

    ("--forest-tabcolor-gold", "--forest-canvas", 3.0, "tab color: gold (Deep Forest)"),
    ("--forest-tabcolor-turquoise", "--forest-canvas", 3.0, "tab color: turquoise (Deep Forest)"),
    ("--forest-tabcolor-lapis", "--forest-canvas", 3.0, "tab color: lapis (Deep Forest)"),
    ("--forest-tabcolor-terracotta", "--forest-canvas", 3.0, "tab color: terracotta (Deep Forest)"),
    ("--forest-tabcolor-green", "--forest-canvas", 3.0, "tab color: green (Deep Forest)"),
    ("--forest-tabcolor-purple", "--forest-canvas", 3.0, "tab color: purple (Deep Forest)"),

    # CLAUDE-P40-BRAND1: the header brand mark/wordmark - held to the
    # STRICTER 4.5:1 normal-text floor (not the 3.0 accent/badge one
    # above), since "Archiosk" is small, always-visible prose-adjacent
    # text, not an occasional badge - the same threshold --text-primary/
    # --text-secondary are held to elsewhere in this file.
    ("--brand-gold", "--canvas", 4.5, "brand mark/wordmark (Light)"),
    ("--dark-brand-gold", "--dark-canvas", 4.5, "brand mark/wordmark (Black)"),
    ("--tint-brand-gold", "--tint-canvas", 4.5, "brand mark/wordmark (Midnight Blue)"),
    ("--forest-brand-gold", "--forest-canvas", 4.5, "brand mark/wordmark (Deep Forest)"),
]


# A token whose ENTIRE value is one color literal - a hex triple, or an
# rgb()/rgba() functional value. Anchoring on the whole value (rather
# than searching for a color anywhere in it) is what keeps composite
# declarations out: --ocean-glow's value is `0 24px 70px rgba(1, 8, 14,
# .5)`, a box-shadow, and picking its rgba() out of the middle would
# register a shadow offset as if it were a surface color.
_TOKEN_RE = re.compile(
    r"(--[a-zA-Z0-9-]+)\s*:\s*(#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})|rgba?\([^)]*\))\s*;"
)
_HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\Z")
_FUNCTIONAL_RE = re.compile(
    r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?\)\Z"
)


def parse_tokens(path: Path) -> dict[str, str]:
    """Every custom property whose value is a single color literal.

    Both notations are returned as written, NOT normalized to hex - an
    rgba() value carries an alpha that a hex string cannot, and losing
    it silently is precisely how a translucent theme gets audited as if
    it were opaque. Composite it first (see composite_stack()).
    """
    text = path.read_text(encoding="utf-8")
    return {name: value for name, value in _TOKEN_RE.findall(text)}


def parse_color(value: str) -> tuple[float, float, float, float]:
    """(r, g, b, alpha) - channels 0-255, alpha 0-1.

    Accepts `#RGB`, `#RRGGBB`, `rgb(r, g, b)` and `rgba(r, g, b, a)`.
    """
    value = value.strip()
    if _HEX_RE.fullmatch(value):
        h = value.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
        return float(r), float(g), float(b), 1.0
    match = _FUNCTIONAL_RE.fullmatch(value)
    if match:
        r, g, b, a = match.groups()
        return float(r), float(g), float(b), 1.0 if a is None else float(a)
    raise ValueError(f"unrecognized color literal: {value!r}")


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    return "#" + "".join(f"{min(255, max(0, round(c))):02X}" for c in (r, g, b))


def composite_stack(base: str, *layers: str) -> str:
    """Paint each layer over `base`, bottom-first, and return the opaque
    result as `#RRGGBB`.

    Standard source-over alpha compositing, per channel:

        C_composite = alpha * C_foreground + (1 - alpha) * C_background

    `base` must be opaque - it is the thing everything else floats
    above, and there is no defined color behind it to blend into.
    Channels stay in float across the whole stack and are rounded once
    at the end, so a three-layer stack does not accumulate three
    roundings.
    """
    r, g, b, a = parse_color(base)
    if a < 1.0:
        raise ValueError(
            f"composite_stack() needs an OPAQUE base, got {base!r} (alpha {a}) - "
            "name the layer underneath it and pass that as the base instead"
        )
    for layer in layers:
        lr, lg, lb, la = parse_color(layer)
        r = la * lr + (1 - la) * r
        g = la * lg + (1 - la) * g
        b = la * lb + (1 - la) * b
    return _rgb_to_hex(r, g, b)


def composite(foreground: str, background: str) -> str:
    """One layer over one opaque background - composite_stack() for the
    common two-layer case."""
    return composite_stack(background, foreground)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    r, g, b, _ = parse_color(h)
    return int(r), int(g), int(b)


def relative_luminance(color: str) -> float:
    def lin(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b, a = parse_color(color)
    if a < 1.0:
        # Deliberately loud rather than approximating alpha away: WCAG
        # relative luminance is defined for an opaque RGB triple, and a
        # translucent token's real luminance depends entirely on what it
        # is sitting on. tokens.css's own --ocean-* family says the same
        # thing in prose; this makes it unrepresentable in code.
        raise ValueError(
            f"{color!r} is translucent (alpha {a}) - relative luminance is undefined "
            "until it is composited over its background (see composite_stack())"
        )
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(color_a: str, color_b: str) -> float:
    lum_a, lum_b = relative_luminance(color_a), relative_luminance(color_b)
    lighter, darker = max(lum_a, lum_b), min(lum_a, lum_b)
    return (lighter + 0.05) / (darker + 0.05)


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_TOKENS_PATH
    tokens = parse_tokens(path)

    all_pass = True
    for fg_name, bg_name, minimum, description in REQUIRED_PAIRINGS:
        fg, bg = tokens.get(fg_name), tokens.get(bg_name)
        if fg is None or bg is None:
            print(f"SKIP  {fg_name} vs {bg_name} ({description}) - token not found in {path.name}")
            continue
        ratio = contrast_ratio(fg, bg)
        status = "PASS" if ratio >= minimum else "FAIL"
        if status == "FAIL":
            all_pass = False
        print(f"{status}  {ratio:5.2f}:1 (need {minimum}:1)  {fg_name} ({fg}) vs {bg_name} ({bg}) - {description}")

    print()
    print("ALL PAIRINGS PASS" if all_pass else "CONTRAST FAILURES FOUND - see above")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
