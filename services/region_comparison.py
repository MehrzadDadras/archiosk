"""CLAUDE-ANALYZE-BOUNDARY-01 - real per-region pixel comparison.

    THE PROTOTYPE MAY DEPEND ON THE REAL CODE.
    THE REAL CODE MAY NOT DEPEND ON THE PROTOTYPE.

This module exists because that sentence was not true. `compare_region` is
genuine production logic - it decides revision-awareness when a drawing Source
is superseded, and `services/case_workspace.py` calls it on a live path - and it
was living inside `services/drawing_analysis.py`, whose other exports generate
CANNED findings from a fixed library.

Consolidation Blueprint 01 measured the consequence: naming `drawing_analysis`
as the prototype namespace would have placed real, load-bearing comparison logic
inside a module a future operator could reasonably disable. Revision-awareness
would have gone with it, silently, for a reason that has nothing to do with
revision-awareness.

WHAT THIS IS, PRECISELY. A mean-pixel-difference threshold over the same
normalized region in two images. It answers "did the pixels here change" and
nothing else. It is NOT a semantic or content reading of the drawing, and it
never was - that honesty is preserved verbatim from where it was written.

NO SEMANTIC CHANGE WAS MADE IN MOVING IT. Same threshold, same greyscale
conversion, same resize fallback, same "unable_to_determine" on every failure
path including an exception. This is a relocation, not a rewrite.

The returned strings match `services.case_workspace`'s `REGION_STATUS_*`
constants BY VALUE and are deliberately written as literals here: importing that
module would create a cycle, since it is the caller.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

#: Mean absolute greyscale difference at or above which a region counts as
#: changed. Carried across unchanged - see the module docstring.
CHANGED_THRESHOLD = 8

STATUS_UNCHANGED = "unchanged"
STATUS_CHANGED = "changed"
STATUS_UNABLE_TO_DETERMINE = "unable_to_determine"


def region_to_pixel_box(
    region: tuple[float, float, float, float],
    width: int,
    height: int,
) -> tuple[tuple[int, int, int, int], dict]:
    """Normalized (x, y, w, h) fractions -> a pixel crop box plus the fractions.

    Public here because BOTH the real comparison and the prototype generator
    need it, and the dependency has to run prototype -> real rather than the
    reverse.
    """
    x, y, w, h = region
    box = (
        int(x * width),
        int(y * height),
        int((x + w) * width),
        int((y + h) * height),
    )
    normalized = {"x": x, "y": y, "width": w, "height": h}
    return box, normalized


def compare_region(
    old_image_path: Path,
    new_image_path: Path,
    crop_normalized: dict,
) -> str:
    """
    Real (if simple) per-region pixel comparison between two revisions of
    a drawing Source, used for revision-awareness (Prompt 4 #13). This is
    a mean-pixel-difference threshold over the same normalized region in
    both images - not a claim of semantic/content understanding, just an
    honest, checkable "did the pixels here change" signal. Returns one of
    "unchanged" / "changed" / "unable_to_determine" (matching
    services.case_workspace's REGION_STATUS_* constants by value).
    """
    try:
        with Image.open(old_image_path) as old_img, Image.open(new_image_path) as new_img:
            region = (
                crop_normalized["x"],
                crop_normalized["y"],
                crop_normalized["width"],
                crop_normalized["height"],
            )
            old_box, _ = region_to_pixel_box(region, old_img.width, old_img.height)
            new_box, _ = region_to_pixel_box(region, new_img.width, new_img.height)

            old_crop = old_img.convert("L").crop(old_box)
            new_crop = new_img.convert("L").crop(new_box)

            if old_crop.size != new_crop.size:
                if old_crop.size[0] == 0 or old_crop.size[1] == 0:
                    return STATUS_UNABLE_TO_DETERMINE
                new_crop = new_crop.resize(old_crop.size)

            old_pixels = list(old_crop.getdata())
            new_pixels = list(new_crop.getdata())

            if not old_pixels or len(old_pixels) != len(new_pixels):
                return STATUS_UNABLE_TO_DETERMINE

            mean_diff = sum(abs(a - b) for a, b in zip(old_pixels, new_pixels)) / len(old_pixels)
            return STATUS_UNCHANGED if mean_diff < CHANGED_THRESHOLD else STATUS_CHANGED
    except Exception:  # noqa: BLE001 - a comparison failure is "unable to determine", not a crash
        return STATUS_UNABLE_TO_DETERMINE
