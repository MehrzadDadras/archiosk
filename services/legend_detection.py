"""CLAUDE-GO-PERCEPTION-LEGEND-DETECT-01 - WHERE is the legend block?

`services/legend_of_understanding.py` already asks whether a project explains
its own drawing language, and answers from TEXT MARKERS ALONE: a source name, a
page label, or an already-registered item whose observed text contains the word
"legend". That was the only evidence available when it was written. It cannot
say where on the sheet the legend actually sits, and it cannot tell a real
legend block from a note that mentions one.

Positioned OCR now exists, so a heading has coordinates and the structure
beneath it can be examined. This module adds the second signal and nothing
else.

WHAT THIS PRODUCES IS DETECTION EVIDENCE, AND THE WORD IS LOAD-BEARING.

A candidate region is a place worth looking at. It is not a confirmed legend,
not a dictionary entry, not a LegendItem, not a project convention and not a
symbol meaning. Nothing here registers meaning, and nothing here may be read as
authority - `legend_of_understanding.resolve_meaning`'s precedence is untouched,
and a candidate never enters it. The next tranche slices entries; a later one
proposes readings; a human confirms. This module stops at "there appears to be a
legend here, and here is why I think so."

TWO SIGNALS, BECAUSE ONE IS NOT ENOUGH.

The marker vocabulary is `legend_of_understanding.LEGEND_EVIDENCE_MARKERS`,
reused rather than copied so the two cannot drift into disagreeing about what
announces a legend. But a marker match is only the FIRST signal: "REFER TO THE
LEGEND ON SHEET A-01" contains the word and is a sentence in the general notes.
So a heading must also LOOK like a heading, and must have supporting structure
beneath or beside it, or no candidate is returned.

THE STOP RULE IS THE DRAWING'S OWN TYPOGRAPHY, IN TWO PARTS.

A fixed vertical window is useless on a real sheet: below the LEGEND heading on
a real A-01 it catches 251 lines, nearly all of them the rest of the drawing.
Rows are gathered instead, and gathering stops when a gap gets too large - but
"too large" is not one number, and a single rule was measurably wrong.

A heading is a TITLE, and titles are separated from their lists by title
spacing: on a real photographed sheet the gap from "CIRCULATION LEGEND" to its
first entry is 3.3x the heading's own height, so a tight rule returned zero
rows and missed the legend completely. Row to row, though, a list keeps a
RHYTHM, and a loose rule there does not find more legend - it finds more
drawing, running to 46 and 88 rows on real sheets. So the first gap is measured
against the heading and the rest against the rows, and both scales come from
the sheet being read rather than from a constant fitted to the five
observations available here.

WHAT THE MEASUREMENT COULD NOT DELIVER, STATED PLAINLY. Three photographs of
the same real sheet produce 3, 3 and 1 gathered rows for the same legend - the
entries are widely spaced and OCR reads a different number of them each time.
The rule is deliberately NOT loosened until all three read as SUPPORTED; the
thin one is reported AMBIGUOUS instead. Fitting the geometry until every
observation passed would have tuned it to five samples and called that a law.

NO CONFIDENCE PROBABILITY IS INVENTED.

Support is reported as named strength plus the counts it was derived from, so a
reader can disagree with the judgement while still seeing the evidence. A
number between 0 and 1 would imply a calibration nobody has performed.
"""
from __future__ import annotations

import logging
import statistics
from typing import Optional

logger = logging.getLogger(__name__)

DETECTION_METHOD = "spatial_legend_candidate"
#: Bump when the RULE changes, so an older candidate is never silently compared
#: against a newer one's reasoning.
DETECTION_VERSION = "spatial-legend@1"

#: EvidenceItem.content_type. Deliberately not "text" and not "positioned_text":
#: this is a claim ABOUT a region, and no existing reader should pick it up.
CANDIDATE_CONTENT_TYPE = "legend_candidate"
CANDIDATE_REGION_TYPE = "rectangular"

#: A heading is short. Measured on every real legend heading available:
#: "LEGEND" (1 word) and "CIRCULATION LEGEND" (2 words). Four allows a longer
#: real heading such as "MECHANICAL SYMBOL LEGEND" while still excluding the
#: sentence case this exists to reject. It is a heading-shape rule, not a
#: tuned threshold, and the false-positive tests state exactly that.
MAX_HEADING_WORDS = 4

#: How far left or right of the heading a row may start and still be read as
#: part of its block, as a fraction of the frame. MEASURED: at 0.12 the block
#: under a real LEGEND heading on A-01 runs away to 88 rows - it stops being a
#: legend and becomes the left third of the sheet. At 0.08 the same heading
#: bounds at 11 rows, and every other real legend measured bounds too.
SUPPORT_BAND = 0.08

#: THE FIRST GAP IS NOT LIKE THE OTHERS, and treating it as though it were is
#: what a single-rule version got wrong. A heading is a title, and a title is
#: separated from its list by title spacing: on a real photographed sheet the
#: gap from "CIRCULATION LEGEND" to its first entry is 0.0756 against a heading
#: height of 0.0232 - 3.3x - so any tight rule returned ZERO rows and missed the
#: legend entirely. This allowance is measured against the HEADING's height.
HEADING_OFFSET_MULTIPLE = 4.0

#: Row to row, though, a list keeps a rhythm, and that is measured against the
#: ROWS' own height. Kept tight deliberately: at 2.5 and above the block on a
#: real A-01A stops bounding and runs to 46 rows. A loose rhythm does not find
#: more legend, it finds more drawing.
ROW_RHYTHM_MULTIPLE = 2.0

#: At or above this many gathered rows a block reads as a list, and the
#: candidate may be SUPPORTED. Measured: real legends gathered 3, 3, 10 and 11.
MIN_SUPPORTED_ROWS = 3

#: Below this there is no block at all, only a word on a sheet. One row is the
#: floor for an AMBIGUOUS candidate rather than a rejection, because a heading
#: with a little structure under it is a place worth a human's glance - and on
#: one of three photographs of the same real sheet, this legend yields exactly
#: one confidently-gathered row. Reporting that as AMBIGUOUS is honest; forcing
#: it to SUPPORTED by loosening the geometry until all five observations passed
#: would have been fitting the rule to the sample.
MIN_CANDIDATE_ROWS = 1

#: How far off the heading's own line a row may sit and still be read as
#: BESIDE it, in multiples of the heading's height. A row beside a title shares
#: its line; anything further away is elsewhere on the drawing.
BESIDE_VERTICAL_MULTIPLE = 1.5

#: Rightward gathering stops when a horizontal gap exceeds this multiple of the
#: row widths already seen - the horizontal twin of ROW_RHYTHM_MULTIPLE, and
#: the bound whose absence let a real sheet produce a 159-row "legend".
BESIDE_GAP_MULTIPLE = 2.0

#: Gap comparisons are made against a scale times a multiple, and a row sitting
#: EXACTLY on that boundary is common in drafted work - rows one line-height
#: apart, for instance. Without slack, 0.35 - 0.33 evaluates to
#: 0.020000000000000018 and loses to 0.01 * 2.0, so a perfectly regular list
#: ends after one row. Found by a sanity check, not by a test: the fixture
#: happened to sit just inside the boundary and passed while the rule was
#: fragile.
GAP_EPSILON = 1e-9

STRENGTH_SUPPORTED = "supported"
STRENGTH_AMBIGUOUS = "ambiguous"
STRENGTH_UNSUPPORTED = "unsupported"

#: Detection outcomes. "None found" is a real answer and has a name.
OUTCOME_CANDIDATES = "candidates_found"
OUTCOME_NO_HEADING = "no_legend_heading_found"
OUTCOME_NO_SUPPORT = "heading_without_supporting_structure"
OUTCOME_NO_LINES = "no_positioned_text"


def _words(text: Optional[str]) -> int:
    return len((text or "").split())


def heading_candidates(lines: list) -> list:
    """Lines that announce a legend AND are shaped like a heading.

    Both halves matter. `_matches_legend_marker` alone accepts a sentence in
    the general notes that happens to mention a legend, which is exactly the
    false positive this tranche is required to reject.
    """
    from services import legend_of_understanding as lou

    found = []
    for index, line in enumerate(lines or []):
        text = (line.get("text") or "").strip()
        if not text:
            continue
        kind = lou._matches_legend_marker(text)
        if not kind:
            continue
        if _words(text) > MAX_HEADING_WORDS:
            # Recorded rather than dropped silently: "the word was there and
            # the line was prose" is a useful thing for a later reader to see.
            found.append({"index": index, "line": line, "marker_kind": kind,
                          "is_heading_shaped": False,
                          "reason": "marker appears inside prose (%d words)" % _words(text)})
            continue
        found.append({"index": index, "line": line, "marker_kind": kind,
                      "is_heading_shaped": True, "reason": None})
    return found


def gather_rows(heading: dict, lines: list, *, band: float = SUPPORT_BAND,
                heading_offset: float = HEADING_OFFSET_MULTIPLE,
                rhythm: float = ROW_RHYTHM_MULTIPLE) -> tuple:
    """Rows belonging to the block under `heading`, and why gathering stopped.

    Scans downward only. A legend that sits to the RIGHT of its heading is
    handled by `rows_beside`, separately, because the two layouts need
    different evidence and conflating them would let either one borrow the
    other's support.
    """
    below = sorted(
        [o for o in lines
         if o.get("y", 0) > heading.get("y", 0) + heading.get("height", 0) * 0.4
         and abs(o.get("x", 0) - heading.get("x", 0)) <= band],
        key=lambda o: o.get("y", 0))
    if not below:
        return [], "nothing within the support band"

    rows: list = []
    previous_y = heading.get("y", 0)
    for row in below:
        gap = row.get("y", 0) - previous_y
        if gap <= 0:
            continue
        if not rows:
            # Title spacing, measured against the heading.
            scale = heading.get("height", 0)
            if scale > 0 and gap > scale * heading_offset + GAP_EPSILON:
                return rows, ("first row %.4f below the heading, more than "
                              "%.1f x its height %.4f"
                              % (gap, heading_offset, scale))
        else:
            # A list's rhythm, measured against the rows themselves.
            scale = statistics.median([r.get("height", 0) for r in rows])
            if scale > 0 and gap > scale * rhythm + GAP_EPSILON:
                return rows, ("gap %.4f exceeded %.1f x row height %.4f"
                              % (gap, rhythm, scale))
        rows.append(row)
        previous_y = row.get("y", 0)
    return rows, "reached the end of the sheet"


def rows_beside(heading: dict, lines: list, *,
                vertical: float = BESIDE_VERTICAL_MULTIPLE,
                rhythm: float = BESIDE_GAP_MULTIPLE) -> list:
    """Rows on the same line to the RIGHT of the heading.

    A legend is sometimes a column beside its title rather than beneath it, so
    this is reported separately from `gather_rows` - a candidate should be able
    to say which layout supported it rather than presenting one kind of
    evidence as the other.

    IT MUST BE BOUNDED IN BOTH DIRECTIONS, and an earlier version was bounded
    in neither. Using the support band as a VERTICAL tolerance and nothing at
    all horizontally, this swept 159 lines across 0.558 of a real A-01 sheet -
    a horizontal swath of drawing, not a legend - and, being larger than the
    correct 11-row block beneath the heading, it won the layout choice and
    produced the only false region in the whole proof.

    So both bounds now come from the sheet's own typography: vertically within
    a small multiple of the heading's height (a row BESIDE a title shares its
    line), and rightward only while the horizontal gaps stay on a rhythm.
    """
    left = heading.get("x", 0) + heading.get("width", 0)
    tolerance = max(heading.get("height", 0) * vertical, 1e-6)
    same_line = sorted(
        [o for o in lines
         if o.get("x", 0) >= left
         and abs(o.get("y", 0) - heading.get("y", 0)) <= tolerance],
        key=lambda o: o.get("x", 0))

    rows: list = []
    previous_right = left
    for row in same_line:
        gap = row.get("x", 0) - previous_right
        if rows:
            scale = statistics.median([r.get("width", 0) for r in rows])
            if scale > 0 and gap > scale * rhythm + GAP_EPSILON:
                break
        rows.append(row)
        previous_right = row.get("x", 0) + row.get("width", 0)
    return rows


def _support(rows: list, heading: dict) -> dict:
    """The counts a strength judgement is made from, reported alongside it."""
    if not rows:
        return {"row_count": 0, "short_label_count": 0, "left_x_spread": None,
                "gap_median": None, "row_height_median": None}
    xs = [r.get("x", 0) for r in rows]
    ys = sorted(r.get("y", 0) for r in rows)
    gaps = [b - a for a, b in zip(ys, ys[1:])]
    return {
        "row_count": len(rows),
        "short_label_count": sum(1 for r in rows if _words(r.get("text")) <= 5),
        "left_x_spread": (statistics.pstdev(xs) if len(xs) > 1 else 0.0),
        "gap_median": (statistics.median(gaps) if gaps else None),
        "row_height_median": statistics.median([r.get("height", 0) for r in rows]),
    }


def _bounds(members: list) -> Optional[dict]:
    """The smallest box containing everything, clamped into the frame."""
    if not members:
        return None
    x0 = max(0.0, min(m.get("x", 0) for m in members))
    y0 = max(0.0, min(m.get("y", 0) for m in members))
    x1 = min(1.0, max(m.get("x", 0) + m.get("width", 0) for m in members))
    y1 = min(1.0, max(m.get("y", 0) + m.get("height", 0) for m in members))
    if x1 <= x0 or y1 <= y0:
        return None
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def detect_candidates(lines: list, *, source_id: Optional[str] = None,
                      structural_unit_id: Optional[str] = None) -> dict:
    """Find candidate legend regions in one frame's positioned lines.

    Pure and frame-agnostic: it takes lines already expressed as 0-1 fractions
    and returns candidates in the same space, so it neither opens an image nor
    cares which kind of source produced them. Nothing is written here.

    ZERO candidates is a first-class result. A sheet that does not explain its
    own symbols must not be given a legend because sheets usually have one -
    `find_legend_evidence` already states that rule for text evidence and it
    holds identically here.
    """
    if not lines:
        return {"outcome": OUTCOME_NO_LINES, "candidates": [], "rejected": [],
                "detection_method": DETECTION_METHOD,
                "detection_version": DETECTION_VERSION}

    headings = heading_candidates(lines)
    if not headings:
        return {"outcome": OUTCOME_NO_HEADING, "candidates": [], "rejected": [],
                "detection_method": DETECTION_METHOD,
                "detection_version": DETECTION_VERSION}

    candidates: list = []
    rejected: list = []

    for entry in headings:
        heading = entry["line"]
        heading_text = (heading.get("text") or "").strip()
        if not entry["is_heading_shaped"]:
            rejected.append({"heading_text": heading_text,
                             "marker_kind": entry["marker_kind"],
                             "reason": entry["reason"]})
            continue

        below, stop_reason = gather_rows(heading, lines)
        beside = rows_beside(heading, lines)

        # BELOW IS THE MEASURED LAYOUT; BESIDE IS A FALLBACK.
        #
        # Every real legend available here - a photographed CIRCULATION LEGEND
        # and two A-01 sheets - sits BELOW its heading, and the vertical rule
        # bounds all three. There is no real example of a beside-layout legend
        # to measure against, and on dense CAD sheets the horizontal band is
        # crowded with small OCR fragments: taking whichever side had more rows
        # gave A-01 a 159-row "legend" across half the sheet, and bounding that
        # in both directions still left A-01A with 82. Both beat the correct
        # block beneath the heading, so the larger side is not the better
        # signal - it is the denser one.
        #
        # So `beside` is consulted only when `below` did not find a block at
        # all. A legend arranged beside its title is still findable; a crowded
        # row of fragments can no longer outvote a real column.
        if len(below) >= MIN_SUPPORTED_ROWS or not beside:
            layout, rows = "below", below
        else:
            layout, rows = "beside", beside
        support = _support(rows, heading)

        if support["row_count"] < MIN_CANDIDATE_ROWS:
            rejected.append({
                "heading_text": heading_text,
                "marker_kind": entry["marker_kind"],
                "reason": ("only %d supporting row(s); a heading alone is not a "
                           "legend" % support["row_count"]),
                "region": _bounds([heading]),
            })
            continue

        region = _bounds([heading] + rows)
        if region is None:
            rejected.append({"heading_text": heading_text,
                             "marker_kind": entry["marker_kind"],
                             "reason": "supporting rows produced no usable bounds"})
            continue

        # STRENGTH, NOT PROBABILITY. Supported means the block reads as a list:
        # enough rows, and most of them short the way legend labels are. Where
        # the rows are there but do not read that way, the honest answer is
        # AMBIGUOUS - a place worth a human's glance, not a finding.
        mostly_short = support["short_label_count"] >= max(
            2, int(support["row_count"] * 0.6))
        enough_rows = support["row_count"] >= MIN_SUPPORTED_ROWS
        if enough_rows and mostly_short:
            strength = STRENGTH_SUPPORTED
            reason = ("%d rows gathered under a heading, %d of them short labels"
                      % (support["row_count"], support["short_label_count"]))
        elif not enough_rows:
            strength = STRENGTH_AMBIGUOUS
            reason = ("a legend heading with only %d row(s) of structure under "
                      "it; worth a look, not a finding" % support["row_count"])
        else:
            strength = STRENGTH_AMBIGUOUS
            reason = ("%d rows gathered but only %d read as short labels; the "
                      "structure may be prose rather than a legend"
                      % (support["row_count"], support["short_label_count"]))

        candidates.append({
            "source_id": source_id,
            "structural_unit_id": structural_unit_id,
            "region": region,
            "heading": {
                "text": heading_text,
                "marker_kind": entry["marker_kind"],
                "x": heading.get("x"), "y": heading.get("y"),
                "width": heading.get("width"), "height": heading.get("height"),
            },
            "layout": layout,
            "spatial_support": dict(support, stop_reason=stop_reason,
                                    rows_below=len(below), rows_beside=len(beside)),
            "supporting_row_texts": [(r.get("text") or "")[:120] for r in rows[:12]],
            "strength": strength,
            "reason": reason,
            "detection_method": DETECTION_METHOD,
            "detection_version": DETECTION_VERSION,
            # Said in the record itself, not only in a docstring, because this
            # value is what a later reader will act on.
            "status": "candidate_only",
        })

    outcome = OUTCOME_CANDIDATES if candidates else (
        OUTCOME_NO_SUPPORT if rejected else OUTCOME_NO_HEADING)
    return {"outcome": outcome, "candidates": candidates, "rejected": rejected,
            "detection_method": DETECTION_METHOD,
            "detection_version": DETECTION_VERSION}


def lines_from_workspace(workspace, source_id: str) -> list:
    """Positioned lines already stored for a Source, in fraction space.

    Reads what `register_positioned_text_regions` wrote - evidence of type
    `positioned_text` joined to its region's geometry - so detection can run
    over a Source that was perceived earlier without re-reading the image.
    """
    from services import positioned_text

    regions = {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])}
    units = {u["id"]: u for u in (getattr(workspace, "structural_units", None) or [])}
    lines = []
    for item in (getattr(workspace, "evidence_items", None) or []):
        if item.get("source_id") != source_id:
            continue
        if item.get("content_type") != positioned_text.POSITIONED_CONTENT_TYPE:
            continue
        region = regions.get(item.get("region_id"))
        if region is None:
            continue
        unit = units.get(region.get("structural_unit_id"))
        # The region join is the tenant boundary, exactly as it is in
        # document_examination._recovered: a stale source_id alone must not be
        # able to pull a line in from another Source.
        if unit is None or unit.get("source_id") != source_id:
            continue
        address = region.get("address") or {}
        lines.append({
            "x": address.get("x", 0.0), "y": address.get("y", 0.0),
            "width": address.get("width", 0.0), "height": address.get("height", 0.0),
            "text": item.get("content") or "",
        })
    lines.sort(key=lambda line: (line["y"], line["x"]))
    return lines
