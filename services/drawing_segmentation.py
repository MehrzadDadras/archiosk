"""
CLAUDE-DRAWING-SEGMENTATION-01 - stop treating a drawing sheet as one image.

WHY THIS EXISTS, AND WHAT WAS ACTUALLY MEASURED

Whole-sheet OCR of the real E1 drawing (42x30in, 12000x16298px) returned 2,598
characters at a legible-token ratio of 0.17 - length that looks like success and
is almost entirely fragments.

Two variables were then measured separately on the same sheet, because
conflating them would have credited the wrong one:

  REGION alone (no page-segmentation-mode control)  0.23, and ~4x faster
  REGION plus --psm 4                               0.50

So the region is necessary but not sufficient: the page segmentation mode is
what roughly doubles legibility, and PyMuPDF's `get_textpage_ocr` /
`pdfocr_tobytes` expose no way to set it. That is why OCR here shells to the
Tesseract binary with an explicit `--psm` rather than using the in-process
wrapper the whole-page fallback uses.

An earlier note in this repository claimed region OCR alone recovered the
project address. That reading had in fact used `--psm 6` via a direct call, so
the credit belonged to the mode, not the region. Recorded because the corrected
attribution is the useful part.

WHAT THIS PROPOSES, AND WHAT IT REFUSES TO ASSERT

Everything here is a CANDIDATE. `propose_title_block_candidates` uses drafting
convention - title blocks sit in the right-hand strip or along the bottom - and
that is a convention, not a detection. So candidates are written as DerivedViews
with the convention recorded as `derivation_reason`, a low confidence, and a
scale state that is never QUANTITATIVE. Nothing here authorises measurement.

`parse_scale_notation` is deterministic text parsing, not inference: it reads
"1:100" or "NTS" out of a string. But its INPUT is OCR of a scanned drawing,
which is exactly the unreliable source that must not become fact - so a parsed
scale is always REVIEW_NEEDED, never KNOWN, regardless of how clean the match
looked. Only a human confirmation moves it, and that arrives through
`CaseWorkspaceStore.override_derived_view` carrying
SCALE_METHOD_MANUAL_CONFIRMATION.

WHAT THIS DELIBERATELY DOES NOT DO

No north-arrow detection, no view-type classification, no wall/door/equipment
recognition, no vectorisation. Those are semantic recognition and they follow
segmentation being trustworthy, not the other way round. A north arrow found by
a symbol matcher would be evidence; nothing here produces it, and the
DerivedView's north fields stay UNKNOWN until something that actually looked
supplies one with a method.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from services import raster_extraction
from services.case_workspace import (
    SCALE_METHOD_PRINTED_NOTATION,
    SCALE_STATE_INFORMATIVE,
    SCALE_STATE_REVIEW_NEEDED,
    SCALE_STATE_UNKNOWN,
)

logger = logging.getLogger(__name__)

#: Where title blocks sit by drafting convention. A CONVENTION, not a detector -
#: each candidate is proposed and must be confirmed, never asserted.
TITLE_BLOCK_RIGHT_STRIP = "right_strip"
TITLE_BLOCK_BOTTOM_STRIP = "bottom_strip"

#: Fraction of the sheet each convention occupies. Deliberately generous: a
#: candidate that clips the title block is worse than one carrying some
#: neighbouring linework, because OCR tolerates extra context far better than it
#: tolerates a cut-off string.
TITLE_BLOCK_STRIP_FRACTION = 0.22

#: Confidence attached to a convention-based candidate. Low on purpose - it
#: reflects "this is where title blocks usually are", which is a weak claim
#: about THIS sheet.
CONVENTION_CONFIDENCE = 0.3

_METRIC_SCALE = re.compile(r"\b1\s*[:：]\s*(\d{1,5})\b")
_IMPERIAL_SCALE = re.compile(
    r"(\d+(?:\s*/\s*\d+)?)\s*\"?\s*=\s*(\d+)\s*'\s*-?\s*(\d+)?\s*\"?", re.IGNORECASE)
_NTS = re.compile(r"\bN\.?\s*T\.?\s*S\.?\b|\bNOT\s+TO\s+SCALE\b", re.IGNORECASE)


def propose_title_block_candidates(page_width: float, page_height: float) -> list:
    """Convention-based title-block regions, in SOURCE PAGE coordinates.

    Returns both the right-hand strip and the bottom strip rather than choosing:
    which one a sheet uses depends on the office, and guessing between them would
    be inventing a fact about this drawing. A caller OCRs both and keeps what
    reads.
    """
    right = TITLE_BLOCK_STRIP_FRACTION * page_width
    bottom = TITLE_BLOCK_STRIP_FRACTION * page_height
    return [
        {"convention": TITLE_BLOCK_RIGHT_STRIP,
         "rect": (page_width - right, 0.0, page_width, page_height),
         "confidence": CONVENTION_CONFIDENCE},
        {"convention": TITLE_BLOCK_BOTTOM_STRIP,
         "rect": (0.0, page_height - bottom, page_width, page_height),
         "confidence": CONVENTION_CONFIDENCE},
    ]


def parse_scale_notation(text: Optional[str]) -> Optional[dict]:
    """Read a scale out of text. Deterministic parsing, never inference.

    A parsed metric or imperial scale is ALWAYS review_needed, never
    quantitative - because the input is OCR of a scanned drawing, and a
    clean-looking regex match on dirty text is exactly the false confidence this
    layer exists to avoid. `1:100` and `1:400` differ by one character. Only a
    human confirmation carrying SCALE_METHOD_MANUAL_CONFIRMATION may make a view
    QUANTITATIVE.

    NTS resolves to INFORMATIVE rather than to a missing scale: the drawing is
    asserting that no scale applies, which is a statement of intent, not an
    absence. Such a view stays fully usable for notes, labels and coordination -
    it is simply never measured.
    """
    if not text:
        return None

    if _NTS.search(text):
        return {"scale_state": SCALE_STATE_INFORMATIVE, "scale_value": None,
                "scale_notation": "NTS", "scale_method": SCALE_METHOD_PRINTED_NOTATION,
                "unit_system": None, "scale_confidence": 0.5}

    metric = _METRIC_SCALE.search(text)
    if metric:
        return {"scale_state": SCALE_STATE_REVIEW_NEEDED,
                "scale_value": float(metric.group(1)),
                "scale_notation": "1:%s" % metric.group(1),
                "scale_method": SCALE_METHOD_PRINTED_NOTATION,
                "unit_system": "metric", "scale_confidence": 0.5}

    imperial = _IMPERIAL_SCALE.search(text)
    if imperial:
        inches = imperial.group(1).replace(" ", "")
        try:
            if "/" in inches:
                numerator, denominator = inches.split("/")
                drawn = float(numerator) / float(denominator)
            else:
                drawn = float(inches)
        except (ValueError, ZeroDivisionError):
            return None
        if drawn <= 0:
            return None
        feet = float(imperial.group(2))
        extra_inches = float(imperial.group(3) or 0)
        real_inches = feet * 12.0 + extra_inches
        return {"scale_state": SCALE_STATE_REVIEW_NEEDED,
                "scale_value": real_inches / drawn,
                "scale_notation": imperial.group(0).strip(),
                "scale_method": SCALE_METHOD_PRINTED_NOTATION,
                "unit_system": "imperial", "scale_confidence": 0.4}
    return None


def read_region(raw_bytes: bytes, page_index: int, rect, *, rotate: int = 0,
                dpi: int = raster_extraction.REGION_RENDER_DPI,
                psm: int = raster_extraction.DEFAULT_REGION_PSM,
                engine=None, reader=None) -> dict:
    """OCR one region and report how legible the result actually was.

    `legible_ratio` is attached so a caller can COMPARE readings rather than
    trusting a character count - the measured failure mode on a real sheet was
    thousands of characters of noise, which looks like success by length alone.
    """
    result = raster_extraction.extract_region_text(
        raw_bytes, page_index, rect, dpi=dpi, rotate=rotate, psm=psm,
        engine=engine, reader=reader)
    result["legible_ratio"] = raster_extraction.legible_ratio(result.get("text"))
    return result


def best_reading(readings: list) -> Optional[dict]:
    """The most legible of several readings of the same thing.

    Used to choose between title-block conventions and between rotations. It
    picks by legibility rather than length, because length rewards exactly the
    noise this layer exists to reject.
    """
    usable = [r for r in (readings or []) if r.get("ran") and (r.get("text") or "").strip()]
    if not usable:
        return None
    return max(usable, key=lambda r: (r.get("legible_ratio", 0.0), len(r.get("text") or "")))


def segment_sheet(store, workspace, source_id: str, page_structural_unit_id: str,
                  raw_bytes: bytes, page_index: int, page_width: float,
                  page_height: float, actor: str, *, rotations=(0,),
                  engine=None, reader=None, governance_log=None) -> dict:
    """Propose title-block DerivedViews for one page, and read them.

    Creates GOVERNED CANDIDATES, not conclusions: each DerivedView records the
    convention that produced it, its low confidence, and a scale state that is
    never KNOWN. The authoritative PDF is not opened for writing, not split and
    not rotated - `rotations` is applied to the render only, which is how a
    sideways sheet is read without touching the document.

    Returns the candidates with their readings so a caller (or a human) can see
    what each convention actually recovered.
    """
    candidates = propose_title_block_candidates(page_width, page_height)
    created = []

    for candidate in candidates:
        readings = [read_region(raw_bytes, page_index, candidate["rect"],
                                rotate=rotation, engine=engine, reader=reader)
                    for rotation in rotations]
        best = best_reading(readings)
        text = (best or {}).get("text") or ""
        scale = parse_scale_notation(text) or {}

        view = store.create_derived_view(
            workspace,
            source_id=source_id,
            page_structural_unit_id=page_structural_unit_id,
            region={"x": candidate["rect"][0], "y": candidate["rect"][1],
                    "width": candidate["rect"][2] - candidate["rect"][0],
                    "height": candidate["rect"][3] - candidate["rect"][1],
                    "page_index": page_index},
            derivation_reason="title-block candidate (%s convention)" % candidate["convention"],
            actor=actor,
            scale_state=scale.get("scale_state", SCALE_STATE_UNKNOWN),
            scale_value=scale.get("scale_value"),
            scale_notation=scale.get("scale_notation"),
            scale_method=scale.get("scale_method"),
            scale_confidence=scale.get("scale_confidence"),
            unit_system=scale.get("unit_system"),
            source_rotation_degrees=float((best or {}).get("rotate") or 0),
            normalized_rotation_degrees=0.0,
            governance_log=governance_log,
        )
        created.append({
            "derived_view": view,
            "convention": candidate["convention"],
            "reading": best,
            "legible_ratio": (best or {}).get("legible_ratio", 0.0),
            "characters": len(text.strip()),
            "scale_parsed": bool(scale),
        })

    return {
        "source_id": source_id,
        "page_structural_unit_id": page_structural_unit_id,
        "page_index": page_index,
        "candidates": created,
        "best_convention": (max(created, key=lambda c: c["legible_ratio"])["convention"]
                            if created else None),
    }
