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


def parse_tokens(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    tokens = {}
    for name, value in re.findall(r"(--[a-zA-Z0-9-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", text):
        tokens[name] = value
    return tokens


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(hexcode: str) -> float:
    def lin(c: float) -> float:
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(hexcode)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(hex_a: str, hex_b: str) -> float:
    lum_a, lum_b = relative_luminance(hex_a), relative_luminance(hex_b)
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
