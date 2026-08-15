"""
Derives a dark-appearance surface/border ramp for a new theme base
color by LUMINANCE-MATCHING each structural step (surface-secondary/
hover/selected/border/border-strong) to the corresponding step in the
original, already contrast-verified Black ramp (#000000-based),
solving for the lightness that reproduces the SAME relative luminance
at the new hue/saturation - not simply reusing the same raw HSL
lightness number. This matters because relative luminance is hue-
dependent (green reaches a given luminance at a much lower raw
lightness than blue does, at the same saturation - see WCAG's
0.2126R + 0.7152G + 0.0722B weighting) - reusing raw lightness across
hues silently produced far lower contrast for a saturated green ramp
than the identical-looking blue one (Deep Forest failed 4.5:1 against
its own surface-selected the first time this was tried; luminance-
matching fixes that structurally instead of hand-tuning one more
special case).

This is how Midnight Blue (#001426) and Deep Forest (#001A12) were
derived for CLAUDE-P40-VW8-QA's Approved Theme Set (Black restored as
the neutral dark default, replacing the interim "Graphite" - see
tokens.css's own comment on that reversal). Border/border-strong use a
lower saturation than the surface steps (0.55/0.60 vs the base's own,
often much higher, saturation) so ordinary panel boundaries stay quiet
even when the theme's own background is vividly saturated - see the
panel-border-hierarchy correction this stage also made.

Usage:
    python tools/derive_theme_palettes.py
"""
from __future__ import annotations

import colorsys

# The relative-luminance TARGETS to reproduce - taken from the
# ORIGINAL, already contrast-verified #000000-based Black ramp. Every
# other dark theme's structural steps solve for the lightness that
# reproduces these same luminances at ITS OWN hue/saturation, so every
# dark theme carries identical contrast guarantees by construction.
_REFERENCE_RAMP = {
    "surface-secondary": "#252118",
    "surface-hover": "#373125",
    "surface-selected": "#50432B",
    "border": "#6E6349",
    "border-strong": "#837454",
}

# Saturation to use for the surface steps of a NEW (non-Black) theme -
# None means "use the base color's own saturation" (Black itself stays
# at whatever its near-zero saturation naturally is). Border/border-
# strong are deliberately less saturated than the surfaces even when
# the base color is vividly saturated - quiet ordinary boundaries,
# vivid solid surfaces.
_SURFACE_SATURATION = None  # base color's own saturation
_BORDER_SATURATION = 0.55
_BORDER_STRONG_SATURATION = 0.60

# Shared warm off-white dark-theme text family (product-owner spec,
# CLAUDE-P40-VW8-QA) - ONE text family reused by every dark appearance
# choice, not independently tuned per theme. text-metadata's ratio
# (0.77) is specifically the value that clears 4.5:1 against the
# reference ramp's own surface-selected (#50432B) - the tightest
# pairing in the whole matrix; every luminance-matched theme inherits
# the same margin by construction.
_TEXT_PRIMARY_HEX = "#E8E4DC"
_TEXT_RATIOS = {
    "text-primary": 1.0,
    "text-secondary": 0.820,
    "text-metadata": 0.77,
    "text-disabled": 0.461,  # exempt from the 4.5:1 floor - see tokens.css's own comment
}

# Per-theme base color. Black is the reference ramp itself (identity -
# no reprojection needed). Midnight Blue / Deep Forest reproject onto
# their own base hue via luminance-matching.
THEMES = {
    "black": {"base": "#000000", "reproject": False},
    "midnight": {"base": "#001426", "reproject": True},
    "forest": {"base": "#001A12", "reproject": True},
    # CLAUDE-APPEARANCE-SIMPLIFY-01: "Deep Ocean" is deliberately NOT
    # listed here. Product Owner correction, twice: the first
    # luminance-matched-from-a-flat-color attempt read "too close to
    # Midnight Blue," and the explicit follow-up instruction was
    # "adapt Gateway page for deepocean appearance" - so Deep Ocean's
    # own tokens (tokens.css) are a literal, direct copy of
    # templates/gateway_shell.html's own already-shipped, already-
    # visually-approved .gateway-shell token block (static/css/
    # main.css), not a NEW palette this tool derives. This tool's own
    # method (luminance-match a flat hex to Black's ramp) doesn't apply
    # to a translucent-glass palette in the first place - it estimates
    # relative_luminance() from three OPAQUE RGB channels, which is not
    # equivalent to what an rgba() value actually renders as once
    # composited over a blurred background.
}

# Shared dark-mode accent colors - reused unmodified by every dark
# theme, re-verified at 3:1 against each one's own canvas rather than
# re-picked per theme.
_SHARED_ACCENTS = {
    "seal-red": "#E5756C",
    "machine-blue": "#7EB7D3",
    "highlight-orange": "#E59C6C",
    "accepted-green": "#8AC696",
    "attention-amber": "#E5B26C",
    "failure-red": "#DD7F73",
    "risk-red": "#E4826D",
}


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#" + "".join(f"{max(0, min(255, round(c))):02X}" for c in rgb)


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


def hls_of(hexcode: str) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in hex_to_rgb(hexcode))
    return colorsys.rgb_to_hls(r, g, b)


def hex_at(h: float, l: float, s: float) -> str:
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def _solve_lightness_for_luminance(h: float, s: float, target_lum: float, lo: float = 0.0, hi: float = 0.6, iters: int = 40) -> float:
    for _ in range(iters):
        mid = (lo + hi) / 2
        if relative_luminance(hex_at(h, mid, s)) < target_lum:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def derive_text_family() -> dict[str, str]:
    h0, l0, s0 = hls_of(_TEXT_PRIMARY_HEX)
    return {
        name: (_TEXT_PRIMARY_HEX if ratio == 1.0 else hex_at(h0, l0 * ratio, s0))
        for name, ratio in _TEXT_RATIOS.items()
    }


def derive_theme(base_hex: str, reproject: bool) -> dict[str, str]:
    palette = {"canvas": base_hex, "surface-primary": base_hex}
    if not reproject:
        palette.update(_REFERENCE_RAMP)
        return palette
    h, _, base_s = hls_of(base_hex)
    for step, ref_hex in _REFERENCE_RAMP.items():
        target_lum = relative_luminance(ref_hex)
        if step in ("border", "border-strong"):
            s = _BORDER_STRONG_SATURATION if step == "border-strong" else _BORDER_SATURATION
        else:
            s = _SURFACE_SATURATION if _SURFACE_SATURATION is not None else base_s
        l = _solve_lightness_for_luminance(h, s, target_lum)
        palette[step] = hex_at(h, l, s)
    return palette


def main() -> int:
    text = derive_text_family()
    print("shared text family:", text)
    print()

    all_pass = True
    for theme_name, spec in THEMES.items():
        palette = derive_theme(spec["base"], spec["reproject"])
        print(f"== {theme_name} ({spec['base']}) ==")
        for key, value in palette.items():
            print(f"  {key:20s} {value}")
        for text_name, text_hex in text.items():
            need = 4.5 if text_name != "text-disabled" else 0.0
            for surface_name in ("canvas", "surface-secondary", "surface-hover", "surface-selected"):
                ratio = contrast_ratio(text_hex, palette[surface_name])
                status = "PASS" if ratio >= need else "FAIL"
                if status == "FAIL":
                    all_pass = False
                    print(f"  FAIL {text_name} vs {surface_name}: {ratio:.2f}:1 (need {need}:1)")
        for accent_name, accent_hex in _SHARED_ACCENTS.items():
            ratio = contrast_ratio(accent_hex, palette["canvas"])
            if ratio < 3.0:
                all_pass = False
                print(f"  FAIL {accent_name} vs canvas: {ratio:.2f}:1 (need 3.0:1)")
        for step in ("border", "border-strong"):
            ratio = contrast_ratio(palette[step], palette["canvas"])
            print(f"  info {step} vs canvas: {ratio:.2f}:1")
        print()

    print("ALL REQUIRED PAIRINGS PASS" if all_pass else "CONTRAST FAILURES FOUND - see above")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
