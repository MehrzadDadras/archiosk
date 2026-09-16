"""CLAUDE-SURVEY-STAGE1-02 - north, measured off the sheet rather than asked for.

    THE ARROW IS A SHAPE. A SHAPE CAN BE MEASURED. ASKING IS THE WEAKER MOVE.

This module exists because of a specific production failure that the obvious
safeguard would not have caught.

On the live Castille sheet the reader described the north arrow as "pointing
upward-right" - which is correct - and in the same breath reported 355 degrees,
which is upward-LEFT. The renderer was faithful and drew 355, so a wrong north
reached a customer looking exactly as confident as a right one.

The first repair was to make the reader report north twice, as an angle and as
a direction word, and refuse the pair when they disagree. That gate is real and
it stays. But measuring the arrow off the sheet showed it points at 8.4 degrees
- and 8.4 and 355 fall in the SAME 45-degree sector. The categorical check
would have passed both. It catches a compass pointed at the floor; it cannot
catch a mirror-flip about vertical, which is the error that actually happened.

    A CATEGORICAL ENCODING CANNOT CATCH A SMALL MIRROR ERROR.
    ARITHMETIC ON THE PIXELS CAN.

So the division of labour moves one step further in the direction
`survey_graph` already argued for. The model LOCATES the arrow - which is
genuinely a perception problem, because a north arrow can be anywhere on a
sheet and looks like many other things. This module MEASURES it, with no model
involved, and its answer is the one that is believed. The model's own angle is
kept only to corroborate, on a tight threshold.

WHY A NEW MODULE. `survey_graph` is pure geometry over a graph and imports no
imaging; putting PIL in it would give the deterministic geometry layer a
dependency on pixels it has never needed. `visual_examination` owns the model
call and the egress audit, and this does neither - it runs entirely on bytes
already in hand, transmits nothing, and must remain obviously free of egress.
`sheet_vision` is PDF/vector work bound to a separate provider grant. None of
the three fits, and the seam this sits on - located symbol in, angle out - is
small and self-contained.

WHAT IT DOES NOT DO. It does not search for the arrow. Given no bounding box it
measures nothing and says so; a whole-sheet hunt for "the dark blob that looks
most like an arrow" is exactly the kind of confident guess this module exists
to replace.
"""
from __future__ import annotations

import io
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

MEASURE_VERSION = "survey-north-01"

#: How far the model's own angle may sit from the measured one and still be
#: called corroboration. Product Owner direction, 2026-09-16: tight, because a
#: loose threshold turns corroboration into a rubber stamp. The Castille error
#: was 13.4 degrees and must not pass.
CORROBORATION_DELTA_DEGREES = 10.0

#: A wedge smaller than this is noise - a speck of dust, a fold, a JPEG
#: artefact - and measuring its axis would produce a confident number from
#: nothing.
MIN_WEDGE_PIXELS = 150

#: The solid wedge is much darker than the thin circle outline around it. This
#: threshold keeps the fill and drops the outline, so the axis is the wedge's
#: and not the circle's (a circle has no axis, and fitting one returns noise).
INK_MAX_LEVEL = 70

#: An arrow that fills almost none of its box, or all of it, was not framed.
MIN_FILL_RATIO = 0.01
MAX_FILL_RATIO = 0.70


def _crop_box(size, bbox) -> Optional[tuple]:
    """The bbox as pixel bounds, or None when it is not usable.

    Fractions of the whole image, matching every other coordinate the reader
    returns. Refused rather than clamped when it falls outside the frame: a box
    off the edge means the reader was extrapolating, and a clamped box would
    measure whatever happened to be at the boundary.
    """
    width, height = size
    try:
        x = float(bbox["x"]); y = float(bbox["y"])
        w = float(bbox["w"]); h = float(bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return None
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
        return None
    left, top = int(x * width), int(y * height)
    right, bottom = int((x + w) * width), int((y + h) * height)
    if right - left < 8 or bottom - top < 8:
        return None
    return (left, top, right, bottom)


def measure_north(image_bytes: bytes, bbox) -> dict:
    """The angle the arrow points, in degrees clockwise from image-up.

    `bbox` is where the reader says the arrow is, as image fractions. Returns
    {"ok", "degrees", "pixels", "reason"}. NEVER RAISES - an unmeasurable arrow
    is an outcome the caller reports, not an exception it has to catch, and a
    corrupt or unusual image must not be able to fail an examination that has
    already succeeded at everything else.

    THE METHOD. Inside the box, the solid wedge is isolated by darkness and its
    principal axis found by moments. An axis has two ends and no inherent
    direction, so the sign is settled by shape: the wedge is a triangle with
    its apex at the rose's centre and its wide end at north, so the half with
    the greater perpendicular spread is the end it points at. That is a
    property of how north arrows are drawn, not an assumption about this sheet.
    """
    if not image_bytes:
        return _failed("there are no bytes to measure")
    box = None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as source:
            grey = source.convert("L")
            box = _crop_box(grey.size, bbox)
            if box is None:
                return _failed("no usable bounding box was given for the arrow")
            crop = grey.crop(box)
            pixels = crop.load()
            width, height = crop.size
            points = [(x, y) for x in range(width) for y in range(height)
                      if pixels[x, y] < INK_MAX_LEVEL]
    except Exception as exc:  # noqa: BLE001 - see docstring: never raises
        logger.warning("north could not be measured (%s: %s)",
                       type(exc).__name__, exc)
        return _failed("the image could not be read for measurement")

    count = len(points)
    if count < MIN_WEDGE_PIXELS:
        return _failed("no solid arrow was found inside the marked area")

    fill = count / float(max((box[2] - box[0]) * (box[3] - box[1]), 1))
    if not (MIN_FILL_RATIO <= fill <= MAX_FILL_RATIO):
        return _failed("the marked area does not frame an arrow "
                       "(it is %.0f%% ink)" % (fill * 100.0))

    total = float(count)
    mx = sum(p[0] for p in points) / total
    my = sum(p[1] for p in points) / total
    sxx = sum((p[0] - mx) ** 2 for p in points) / total
    syy = sum((p[1] - my) ** 2 for p in points) / total
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points) / total
    if sxx + syy <= 0:
        return _failed("the arrow has no measurable extent")

    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    vx, vy = math.cos(theta), math.sin(theta)

    def spread(sign: float) -> float:
        half = [p for p in points
                if ((p[0] - mx) * vx + (p[1] - my) * vy) * sign > 0]
        if not half:
            return 0.0
        return sum(abs(-(p[0] - mx) * vy + (p[1] - my) * vx)
                   for p in half) / len(half)

    wide, narrow = spread(1.0), spread(-1.0)
    if abs(wide - narrow) < 1e-9:
        return _failed("the arrow is symmetric, so which end is north "
                       "cannot be told from its shape")
    sign = 1.0 if wide > narrow else -1.0
    dx, dy = vx * sign, vy * sign

    return {"ok": True, "degrees": round(math.degrees(math.atan2(dx, -dy)) % 360.0, 2),
            "pixels": count, "reason": None}


def _failed(reason: str) -> dict:
    return {"ok": False, "degrees": None, "pixels": 0, "reason": reason}


def angular_delta(a: float, b: float) -> float:
    """The smaller angle between two headings, 0..180."""
    gap = abs(float(a) - float(b)) % 360.0
    return min(gap, 360.0 - gap)


def corroborates(measured: float, claimed) -> bool:
    """Whether the reader's own angle backs the measurement up."""
    if claimed is None:
        return False
    return angular_delta(measured, claimed) <= CORROBORATION_DELTA_DEGREES
