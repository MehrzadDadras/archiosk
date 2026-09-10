"""CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01 - what are the ENTRIES in that block?

`services/legend_detection.py` answers WHERE a legend appears to be. It stops,
deliberately, at "there appears to be a legend here, and here is why". This
module takes one such candidate region and splits it into PROPOSED ENTRY
SLICES, and stops just as deliberately one step later.

A SLICE IS A CANDIDATE VISUAL EXEMPLAR. NOTHING ELSE.

It is not a confirmed legend entry, not a LegendItem, not a registered meaning,
not a project or discipline convention, and not an authoritative symbol
definition. Slicing does not register meaning: no decision is recorded, no
family is confirmed, no scope is widened, and `resolve_meaning`'s precedence is
never entered. The next stage proposes readings and asks a human; this one only
says "this block appears to contain these entries, in this order, and here is
the text that sits in each".

WHAT POSITIONED OCR CAN AND CANNOT SEE, WHICH DECIDES THE WHOLE SHAPE.

The candidate region is the union of the heading and the ROW TEXT BOXES beneath
it. A drawn symbol produces no text, so it contributes no box - which means the
icon is not directly observable from positioned text at all. Two things ARE
observable, and only these are used:

1. The ROW BAND. A slice's crop box spans the block's full x-extent at the
   entry's own y-extent, so a later reader cropping it sees whatever sits
   beside the label, symbol included. The band is derived, the text box that
   produced it is stored beside it, and the two are never conflated.
2. The INTRA-ROW GAP. When a row reads as "AD    AREA DRAIN", both parts are
   text and the space between them is measurable. A gap materially wider than
   that row's own word spacing is recorded as a candidate visual zone.

Where neither yields anything, `icon_zone` is None WITH A REASON rather than a
guessed box. That is the direction's own "if measurable", answered honestly:
inventing a symbol rectangle where nothing was observed would be exactly the
fabricated certainty this pipeline has refused at every previous stage.

TWO GROUPINGS, BECAUSE A ROW AND AN ENTRY ARE NOT THE SAME THING.

Lines sharing a y-band are ONE ROW - that is what makes "AD" and "AREA DRAIN"
one entry rather than two, and it is why nothing here reads side-by-side text
as a second column. Consecutive ROWS then merge into one ENTRY when the gap
between them is materially tighter than the block's own row pitch, which is
what a wrapped multi-line label looks like. Both rules measure against the
block being read, never against a constant fitted elsewhere.

WHAT IS NOT SUPPORTED IS SAID, NOT GUESSED. Two-column legends, icon-above-text
and nested keys are not detected and not claimed. A row whose structure does
not resolve is marked AMBIGUOUS, and a block that does not resolve at all is
UNRESOLVED - a slice nobody can trust is worse than no slice, and this pipeline
has an established answer for that case: report the weakness, do not tune it
away.
"""
from __future__ import annotations

import logging
import statistics
from typing import Optional

logger = logging.getLogger(__name__)

SLICE_METHOD = "legend_entry_slice"
#: Bump when the RULE changes, so an older slice is never silently compared
#: against a newer one's reasoning. Same discipline as DETECTION_VERSION.
SLICE_VERSION = "legend-slice@1"

#: EvidenceItem.content_type. Distinct from "legend_candidate" and from
#: "positioned_text": this is a claim about a SUBDIVISION of a candidate, and
#: no existing reader should pick it up.
ENTRY_CONTENT_TYPE = "legend_entry_candidate"
ENTRY_REGION_TYPE = "rectangular"

#: How resolved one slice is. Deliberately NOT `LegendItem.status`, whose
#: vocabulary ("proposed"/"confirmed"/"overridden"...) describes a governed
#: record moving through human decisions. A slice is not that record and must
#: not borrow its states, or a later reader will believe a decision exists.
#: `status` stays "candidate_only" on every slice, exactly as the parent
#: candidate carries it, and that is the field that says nothing is registered.
SLICE_PROPOSED = "proposed"
SLICE_AMBIGUOUS = "ambiguous"
SLICE_UNRESOLVED = "unresolved"

OUTCOME_SLICED = "entries_proposed"
OUTCOME_NO_ROWS = "no_rows_under_heading"
OUTCOME_UNRESOLVED = "block_did_not_resolve"

#: Two lines are the SAME ROW when their vertical extents overlap by at least
#: this fraction of the shorter line's height. A shape rule, not a tuned
#: threshold: text set on one baseline overlaps almost completely, and text on
#: the next baseline overlaps hardly at all. Half is the flat middle between
#: two populations that are nowhere near each other.
ROW_OVERLAP_FRACTION = 0.5

#: A row-to-row gap this fraction of the block's MEDIAN gap or tighter reads as
#: a wrapped continuation of the row above rather than a new entry.
CONTINUATION_FRACTION = 0.5

#: A gap within this much of the continuation boundary, either side, is too
#: close to call, and the entry it produces is marked AMBIGUOUS rather than
#: silently merged or silently split. The boundary is a judgement; a value
#: sitting on it must not be reported as if it were not.
CONTINUATION_UNCERTAIN_BAND = 0.15

#: A block needs this many rows before its median gap means anything. Below it,
#: no continuation merging is attempted at all - a "median" of one or two
#: samples is not a rhythm, and guessing from it would be inventing structure.
MIN_ROWS_FOR_RHYTHM = 4

#: An entry shorter than this fraction of its own block's median row height is
#: not a row of that block. Measured, not anticipated: see the M2_OF_3 note in
#: `slice_candidate`. Judged against the block being read, like every other
#: rule here, so a dense legend and an airy one are each held to their own.
DEGENERATE_HEIGHT_FRACTION = 0.5

#: An intra-row gap must exceed the median of the row's OTHER gaps by this
#: multiple to read as a deliberate visual zone rather than ordinary spacing.
#: The outlier is excluded from its own reference - including it pulls the
#: median toward it, and on a two-part row the median simply IS the gap.
ICON_GAP_MULTIPLE = 2.5

#: ...and must always be at least this multiple of the row's height. A symbol
#: needs room; a gap narrower than the text is tall is spacing, not a symbol
#: cell. This is the ONLY test on a row that carries no usable spacing sample
#: of its own - one gap, or gaps that are all zero on poor OCR.
ICON_GAP_HEIGHT_MULTIPLE = 1.0

EPSILON = 1e-9


def _y_overlap(a: dict, b: dict) -> float:
    """Shared vertical extent as a fraction of the SHORTER line's height."""
    top = max(a["y"], b["y"])
    bottom = min(a["y"] + a["height"], b["y"] + b["height"])
    shorter = min(a["height"], b["height"])
    if shorter <= 0:
        return 0.0
    return max(0.0, bottom - top) / shorter


def _bounds(members: list) -> Optional[dict]:
    """Smallest box containing everything, clamped into the frame."""
    if not members:
        return None
    x0 = max(0.0, min(m["x"] for m in members))
    y0 = max(0.0, min(m["y"] for m in members))
    x1 = min(1.0, max(m["x"] + m["width"] for m in members))
    y1 = min(1.0, max(m["y"] + m["height"] for m in members))
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return None
    return {"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0}


def _same_line(a: dict, b: dict) -> bool:
    """Whether two line records describe the same physical line."""
    return (abs(a.get("x", 0) - b.get("x", 0)) < 1e-6
            and abs(a.get("y", 0) - b.get("y", 0)) < 1e-6
            and (a.get("text") or "") == (b.get("text") or ""))


def lines_within(region: dict, lines: list, *, heading: Optional[dict] = None) -> list:
    """The block's own lines: the region's VERTICAL span, from its left edge.

    NOT SIMPLE CONTAINMENT, AND THE REASON IS A REAL PROPERTY OF THE UPSTREAM
    RECORD. `legend_detection.gather_rows` walks downward and skips any line
    whose gap to the previous one is zero or less - so of "AD    AREA DRAIN",
    both on one baseline, only the FIRST survives into the gathered rows. The
    candidate region is the union of what survived, which means it can end well
    to the left of the descriptions that belong to it. Slicing inside that box
    would see a column of two-letter codes and call it the legend.

    So the vertical span is taken from the region - that part is sound, it is
    exactly the block detection found - and the horizontal extent is recovered
    per row by `bound_row_extent` below, bounded by the sheet's own typography
    rather than by a box that was never meant to carry it.

    Nothing LEFT of the region is admitted: the block's left edge is the one
    horizontal fact the region does establish.
    """
    x0, y0 = region["x"], region["y"]
    y1 = y0 + region["height"]
    inside = []
    for line in lines or []:
        try:
            cy = line["y"] + line["height"] / 2.0
        except (KeyError, TypeError):
            continue
        if not (y0 - EPSILON <= cy <= y1 + EPSILON):
            continue
        if line.get("x", 0) < x0 - EPSILON:
            continue
        if heading is not None and _same_line(line, heading):
            continue
        if not (line.get("text") or "").strip():
            continue
        inside.append(line)
    inside.sort(key=lambda line: (line["y"], line["x"]))
    return inside


def bound_row_extent(row: dict) -> dict:
    """Trim a row rightward where the sheet's own spacing says it ended.

    Admitting a whole y-band would let a row run across the drawing beside the
    legend, which is precisely the failure `rows_beside` was rebuilt to stop.
    The stop rule is `gather_rows`'s, turned on its side, and for the same
    physical reason it has two parts:

    THE FIRST GAP IS A DIFFERENT THING FROM THE REST. Between a code and its
    description sits the symbol cell - the widest deliberate space on the row -
    while the gaps after that are word spacing inside one label. Measuring both
    against one number would either cut every row at its symbol or let every
    row run into the drawing.

    Both multiples are imported from `legend_detection` rather than restated,
    so the two modules cannot drift into disagreeing about what a rhythm is.
    """
    from services.legend_detection import BESIDE_GAP_MULTIPLE, HEADING_OFFSET_MULTIPLE

    members = sorted(row["members"], key=lambda line: line["x"])
    if len(members) < 2:
        return dict(row, members=members, trimmed=0)

    kept = [members[0]]
    dropped = 0
    for index, member in enumerate(members[1:]):
        previous = kept[-1]
        gap = member["x"] - (previous["x"] + previous["width"])
        if index == 0:
            allowed = previous["height"] * HEADING_OFFSET_MULTIPLE
        else:
            scale = statistics.median([m["width"] for m in kept])
            allowed = scale * BESIDE_GAP_MULTIPLE
        if gap > allowed + EPSILON:
            dropped = len(members) - len(kept)
            break
        kept.append(member)
    return dict(row, members=kept, trimmed=dropped)


def group_rows(lines: list) -> list:
    """Lines sharing a y-band become one ROW, in reading order.

    THIS IS WHAT STOPS A CODE COLUMN BEING READ AS A SECOND COLUMN. A legend
    row is very often "AD    AREA DRAIN", which OCR returns as two boxes on one
    baseline. Grouping by vertical overlap first makes that one row with two
    parts - which is what it physically is - so nothing downstream has to
    decide whether the sheet has columns.
    """
    rows: list = []
    for line in sorted(lines, key=lambda line: (line["y"], line["x"])):
        placed = False
        for row in rows:
            if _y_overlap(row["members"][0], line) >= ROW_OVERLAP_FRACTION:
                row["members"].append(line)
                placed = True
                break
        if not placed:
            rows.append({"members": [line]})
    for row in rows:
        row["members"].sort(key=lambda line: line["x"])
        row["bounds"] = _bounds(row["members"])
        row["text"] = " ".join((m.get("text") or "").strip() for m in row["members"]).strip()
    rows.sort(key=lambda row: row["bounds"]["y"])
    return rows


def _row_gaps(rows: list) -> list:
    """Vertical gap from each row's bottom to the next row's top."""
    gaps = []
    for previous, current in zip(rows, rows[1:]):
        top = current["bounds"]["y"]
        bottom = previous["bounds"]["y"] + previous["bounds"]["height"]
        gaps.append(max(0.0, top - bottom))
    return gaps


def group_entries(rows: list) -> dict:
    """Consecutive rows merge into one ENTRY when the gap reads as a wrap.

    A wrapped label sits TIGHTER against the line above it than one entry sits
    against the next. The comparison is against this block's own median gap, so
    a widely-spaced legend and a dense one are each judged by their own rhythm
    rather than by a constant measured on some other sheet.

    Below MIN_ROWS_FOR_RHYTHM there is no median worth the name and no merging
    is attempted - every row becomes its own entry, and the block records that
    its grouping rests on too few rows to be sure of.
    """
    if not rows:
        return {"entries": [], "median_gap": None, "rhythm": False}

    gaps = _row_gaps(rows)
    rhythm = len(rows) >= MIN_ROWS_FOR_RHYTHM and any(g > EPSILON for g in gaps)
    median_gap = statistics.median(gaps) if gaps else None

    entries: list = []
    current = {"rows": [rows[0]], "uncertain": False}
    for index, row in enumerate(rows[1:]):
        gap = gaps[index]
        merge, uncertain = False, False
        if rhythm and median_gap and median_gap > EPSILON:
            ratio = gap / median_gap
            merge = ratio <= CONTINUATION_FRACTION
            uncertain = abs(ratio - CONTINUATION_FRACTION) <= CONTINUATION_UNCERTAIN_BAND
        if merge:
            current["rows"].append(row)
            current["uncertain"] = current["uncertain"] or uncertain
        else:
            entries.append(current)
            current = {"rows": [row], "uncertain": uncertain}
    entries.append(current)
    return {"entries": entries, "median_gap": median_gap, "rhythm": rhythm}


def icon_zone_for(row: dict) -> dict:
    """The measurable visual gap inside one row, or an honest None.

    ONLY A SPATIAL RELATIONSHIP IS RECORDED. This says "there is an unusually
    wide space here, beside this text" and never "the symbol in it means X".

    Requires at least two text parts on the row, because a gap needs two edges
    to be measured between. A single-part row - the common case for a text-only
    entry, and for any row whose symbol was never OCR'd - returns None with the
    reason, which is a different and much more useful answer than a box drawn
    where nothing was seen.
    """
    members = row["members"]
    if len(members) < 2:
        return {"zone": None,
                "reason": "only one text part on this row; no gap has two edges"}

    gaps = []
    for previous, current in zip(members, members[1:]):
        left = previous["x"] + previous["width"]
        gaps.append({"x": left, "width": max(0.0, current["x"] - left)})
    widest = max(gaps, key=lambda g: g["width"])
    height = row["bounds"]["height"]

    # THE OUTLIER MUST NOT SIT IN ITS OWN REFERENCE. Comparing the widest gap
    # against a median that includes it pulls the median toward it, and on the
    # commonest legend row of all - exactly two parts, "AD  AREA DRAIN" - the
    # median IS that single gap, so the test could never fire. Found by a test,
    # against the real two-part shape, after the first version silently
    # reported no visual zone on the layout it was written for.
    others = [g["width"] for g in gaps if g is not widest]
    height_ok = widest["width"] >= height * ICON_GAP_HEIGHT_MULTIPLE
    if not height_ok:
        return {"zone": None,
                "reason": ("widest intra-row gap %.4f is narrower than the row "
                           "is tall (%.4f); spacing, not a symbol cell"
                           % (widest["width"], height))}

    # Gaps of zero are not a spacing sample. Poor OCR on M2_OF_3 returns
    # overlapping fragments whose gaps are all 0.0000, and quoting "2.5x a
    # median of 0.0000" in the record would be a comparison that did not
    # happen. Those rows fall to the height-only basis and say so.
    ordinary = statistics.median(others) if others else 0.0
    if ordinary > EPSILON:
        if widest["width"] < ordinary * ICON_GAP_MULTIPLE:
            return {"zone": None,
                    "reason": ("widest intra-row gap %.4f is ordinary spacing "
                               "for this row (other gaps median %.4f)"
                               % (widest["width"], ordinary))}
        basis = ("exceeds %.1fx the row's other gaps (median %.4f) and %.1fx "
                 "its height %.4f" % (ICON_GAP_MULTIPLE, ordinary,
                                      ICON_GAP_HEIGHT_MULTIPLE, height))
    else:
        # No usable sample of this row's own ordinary spacing - either one gap,
        # or gaps that are all zero. Height is the only honest reference left,
        # and the record says that rather than implying a comparison that was
        # never made.
        basis = ("exceeds %.1fx the row height %.4f; this row carries no usable "
                 "in-row spacing sample to compare it against"
                 % (ICON_GAP_HEIGHT_MULTIPLE, height))

    return {
        "zone": {"x": widest["x"], "y": row["bounds"]["y"],
                 "width": widest["width"], "height": height},
        "reason": "gap %.4f %s" % (widest["width"], basis),
    }


def slice_candidate(candidate: dict, lines: list) -> dict:
    """Split ONE candidate legend region into proposed entry slices.

    Pure and frame-agnostic, like `detect_candidates`: 0-1 fractions in, 0-1
    fractions out, nothing opened and nothing written. Zero entries is a
    first-class result.
    """
    region = candidate.get("region") or {}
    if not region:
        return _empty(OUTCOME_NO_ROWS, "candidate carries no region")

    heading_line = None
    heading = candidate.get("heading") or {}
    if heading.get("x") is not None:
        heading_line = {"x": heading.get("x"), "y": heading.get("y"),
                        "width": heading.get("width"), "height": heading.get("height"),
                        "text": heading.get("text")}

    block_lines = lines_within(region, lines, heading=heading_line)
    if not block_lines:
        return _empty(OUTCOME_NO_ROWS,
                      "no positioned text inside the candidate region")

    rows = [bound_row_extent(row) for row in group_rows(block_lines)]
    for row in rows:
        row["bounds"] = _bounds(row["members"])
        row["text"] = " ".join((m.get("text") or "").strip()
                               for m in row["members"]).strip()
    rows = [row for row in rows if row["bounds"] is not None]
    grouped = group_entries(rows)
    median_row_height = (statistics.median([r["bounds"]["height"] for r in rows])
                         if rows else None)

    entries = []
    for index, entry in enumerate(grouped["entries"]):
        entry_rows = entry["rows"]
        text_bbox = _bounds([r["bounds"] for r in entry_rows])
        if text_bbox is None:
            continue

        # THE ROW BAND IS THE CROP BOX, and it is derived rather than read: it
        # spans the block's full width at this entry's own height, so whatever
        # sits beside the label - a symbol OCR never saw - is inside it. The
        # text box that was actually read is kept beside it and the two are
        # never conflated.
        band = {"x": region["x"], "y": text_bbox["y"],
                "width": region["width"], "height": text_bbox["height"]}

        zones = [icon_zone_for(row) for row in entry_rows]
        measured = [z for z in zones if z["zone"] is not None]
        icon_zone = measured[0]["zone"] if measured else None
        icon_reason = (measured[0]["reason"] if measured
                       else zones[0]["reason"] if zones else "no rows")

        multi_line = len(entry_rows) > 1
        parts = sum(len(row["members"]) for row in entry_rows)
        # MEASURED ON A REAL SHEET, NOT ANTICIPATED. On M2_OF_3 - a 2000-era
        # scan whose OCR text layer is genuinely poor - the block produced an
        # entry of height 0.0012 whose whole text was a single backslash, and
        # it was being reported as cleanly PROPOSED beside real rows. A row an
        # order of magnitude shorter than its own block's rows is not an entry,
        # and text with no letter or digit in it is not a label. Both are
        # judged against THIS block rather than a constant.
        degenerate = None
        if median_row_height and text_bbox["height"] < median_row_height * DEGENERATE_HEIGHT_FRACTION:
            degenerate = ("row height %.4f is far below the block's own median "
                          "%.4f" % (text_bbox["height"], median_row_height))
        elif not any(ch.isalnum() for ch in (
                " ".join(row["text"] for row in entry_rows))):
            degenerate = "no letter or digit was read in this entry"

        if degenerate:
            resolution = SLICE_AMBIGUOUS
            reason = degenerate
        elif entry["uncertain"]:
            resolution = SLICE_AMBIGUOUS
            reason = ("row spacing sat on the continuation boundary; whether "
                      "this is one entry or two is not resolved by the geometry")
        elif multi_line and not grouped["rhythm"]:
            resolution = SLICE_AMBIGUOUS
            reason = "grouped across rows without an established block rhythm"
        elif parts > 3:
            resolution = SLICE_AMBIGUOUS
            reason = ("%d separate text parts on this entry; the internal "
                      "structure is not resolved" % parts)
        else:
            resolution = SLICE_PROPOSED
            reason = ("one entry across %d row(s), %d text part(s)"
                      % (len(entry_rows), parts))

        entries.append({
            "entry_index": index,
            "region": band,
            "text_bbox": text_bbox,
            "observed_text": " ".join(row["text"] for row in entry_rows).strip(),
            "row_texts": [row["text"] for row in entry_rows],
            "row_count": len(entry_rows),
            "text_part_count": parts,
            "icon_zone": icon_zone,
            "icon_zone_reason": icon_reason,
            "slice_resolution": resolution,
            "reason": reason,
            "slice_method": SLICE_METHOD,
            "slice_version": SLICE_VERSION,
            # Carried from the parent, unchanged. This is the field that says
            # nothing here is registered, and it is stated in the record rather
            # than only in a docstring.
            "status": "candidate_only",
        })

    if not entries:
        return _empty(OUTCOME_NO_ROWS, "rows produced no usable bounds")

    # A BLOCK THAT DID NOT RESOLVE SAYS SO. Where every entry came out
    # ambiguous there is no useful subdivision to hand forward, and reporting
    # one anyway would dress uncertainty as structure.
    unresolved = all(e["slice_resolution"] == SLICE_AMBIGUOUS for e in entries)
    outcome = OUTCOME_UNRESOLVED if unresolved else OUTCOME_SLICED
    if unresolved:
        for entry in entries:
            entry["slice_resolution"] = SLICE_UNRESOLVED

    return {
        "outcome": outcome,
        "entries": entries,
        "row_count": len(rows),
        "entry_count": len(entries),
        "median_row_gap": grouped["median_gap"],
        "rhythm_established": grouped["rhythm"],
        "slice_method": SLICE_METHOD,
        "slice_version": SLICE_VERSION,
    }


def _empty(outcome: str, reason: str) -> dict:
    return {"outcome": outcome, "entries": [], "row_count": 0, "entry_count": 0,
            "median_row_gap": None, "rhythm_established": False, "reason": reason,
            "slice_method": SLICE_METHOD, "slice_version": SLICE_VERSION}
