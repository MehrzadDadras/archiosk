"""CLAUDE-DETAIL-CALLOUT-01 - which sheet does this drawing send you to?

    SOURCE A -> declared detail callout -> TARGET SOURCE B

A DECLARED REFERENCE, AND NOTHING BEYOND IT. A resolved callout proves that a
sheet POINTS AT another sheet and that a Source answers to the identity it
names. It does not prove the two describe one physical location, that any value
differs, that a discrepancy exists, or that the two disciplines correspond.
Every one of those is a later family with its own evidence question.

WHY THIS FAMILY, AND WHY NOT GRID. The preceding reconnaissance measured grid
identity across the real corpus and retired it: architectural grid labels are
not recoverable (two OCR reads of the SAME sheet agree on the count of 2 of 11
letters), and the structural grid vocabulary is not discriminative (six of eight
sheets carry an identical `A`-`M`). This family was measured in the same pass
and behaved the opposite way - 58 declared citations, every target resolving.

THE GRAMMAR IS THE ONE THE CORPUS USES, NOT THE CONVENTIONAL ONE. The parser
this repository already had (`_GRID_INTERSECTION_RE`, `_DETAIL_CALLOUT_RE`)
looks for `3/A-501` - a slash. It finds ZERO of these 58, because the real
drafting on this corpus draws a circle split by a VERTICAL line with the detail
number on the LEFT and the sheet token on the RIGHT:

        ( 1 | RS510 )  <- one bubble, two tokens, side by side

Manual inspection of the rendered sheet is what established that, after an
assumed number-above-sheet-below rule measured `dy ~= 0` and failed. The bubble
also carries a filled cut-direction arrowhead, which is not needed to identify
the reference and is not read.

POSITION IS THE DISCRIMINATOR, MEASURED BEFORE ANYTHING WAS BUILT. Over the ten
real structural sheets there are 897 possible number x sheet-token pairings.
The geometry below admits 62 of them - 6.9% - and the admitted set has
dx 0.25-0.27 and dy -0.04..-0.02 sheet-token heights, at a standard deviation
of 0.004 and 0.003. It is not a threshold anybody tuned; it is the width of one
half of a drawn circle, and it separates cleanly because a bubble is a bubble.

WHAT POSITION REJECTS THAT TEXT ORDER ACCEPTED: the scale note. `1 : 50` next
to a title block reads as `50` + `RS501` in text order and is a plausible false
reference; it sits stacked rather than side by side and is refused here.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

CALLOUT_METHOD = "declared_detail_callout"
#: Bump when the RULE changes, so an older registration is never silently
#: compared against a newer one's reasoning.
CALLOUT_VERSION = "detail-callout@1"

#: A detail number: one or two digits, whole-token. A drawing numbers its
#: details 1..n; a four-digit token is a dimension or an elevation, not a detail.
_DETAIL_NUMBER = re.compile(r"^\d{1,2}$")

# -- the measured envelope ---------------------------------------------------
# Offsets are expressed in TARGET-TOKEN HEIGHTS rather than page fractions, so
# the rule survives a sheet at a different size or zoom. Normalising by the
# sheet token rather than by the number is deliberate: a 5-character token has a
# steady glyph height, while a bare "1" does not.
#
# Measured envelope: dx 0.25-0.27, dy -0.04..-0.02. The bounds below are that
# envelope with room either side, NOT a fitted threshold.
DX_MIN = 0.12
DX_MAX = 0.55
DY_MAX = 0.12


def positioned_pages_for(workspace, source_id: str) -> list:
    """Positioned lines WITH their geometry, one entry per page, in page order.

    The geometry-carrying sibling of `sheet_identity.recovered_pages_for`, which
    returns text only and so cannot answer a question about where two tokens sit
    relative to each other. Uses the identical region -> unit join, which is the
    tenant boundary `legend_detection.lines_from_workspace` documents: a stale
    source_id alone must never pull a line in from another Source.

    Page-bounded for the reason CLAUDE-SHEET-INDEX-BOUNDARY-01 established the
    hard way - a candidate assembled from tokens on two different pages is not a
    callout, it is an artifact of reading order.
    """
    from services import positioned_text

    regions = {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])}
    units = {u["id"]: u for u in (getattr(workspace, "structural_units", None) or [])
             if u.get("source_id") == source_id and u.get("unit_type") == "page"}

    by_unit: dict = {}
    for item in (getattr(workspace, "evidence_items", None) or []):
        if item.get("source_id") != source_id:
            continue
        if item.get("content_type") != positioned_text.POSITIONED_CONTENT_TYPE:
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        region = regions.get(item.get("region_id"))
        if region is None:
            continue
        unit = units.get(region.get("structural_unit_id"))
        if unit is None:
            continue
        address = region.get("address") or {}
        by_unit.setdefault(unit["id"], []).append({
            "text": content,
            "x": address.get("x", 0.0), "y": address.get("y", 0.0),
            "width": address.get("width", 0.0), "height": address.get("height", 0.0),
            "extraction_pass": address.get("extraction_pass"),
            "region_id": region["id"],
        })

    pages = []
    for unit in sorted(units.values(),
                       key=lambda u: (u.get("order_index") if u.get("order_index")
                                      is not None else 0)):
        lines = by_unit.get(unit["id"], [])
        lines.sort(key=lambda ln: (ln["y"], ln["x"]))
        pages.append({"unit": unit, "lines": lines})
    return pages


def _centre(line):
    return (line["x"] + line["width"] / 2.0, line["y"] + line["height"] / 2.0)


def positional_basis(number_line, target_line) -> Optional[dict]:
    """The geometry that makes these two tokens ONE callout, or None.

    Returns the numbers a later reader needs to answer "why did ARCHIOSK read
    these as one reference?" without re-deriving them - no score, no confidence,
    just the measured offsets and the envelope they were tested against.
    """
    height = target_line.get("height") or 0.0
    if height <= 0:
        return None
    nx, ny = _centre(number_line)
    tx, ty = _centre(target_line)
    dx = (tx - nx) / height
    dy = (ty - ny) / height
    if not (DX_MIN < dx < DX_MAX and abs(dy) < DY_MAX):
        return None
    return {
        "dx_in_target_heights": round(dx, 4),
        "dy_in_target_heights": round(dy, 4),
        "target_height": round(height, 6),
        "envelope": {"dx_min": DX_MIN, "dx_max": DX_MAX, "dy_max": DY_MAX},
        "number_bbox": {k: number_line[k] for k in ("x", "y", "width", "height")},
        "target_bbox": {k: target_line[k] for k in ("x", "y", "width", "height")},
        "arrangement": "side_by_side_split_bubble",
    }


def callout_candidates(page, known_tokens, *, self_token: Optional[str] = None) -> list:
    """Every (detail number, sheet token) pair on ONE page that the geometry admits.

    `known_tokens` is the set of sheet identities this project actually holds,
    normalised. A token that names no Source is not proposed as a callout at all
    - the same restraint `sheet_identity` applies, for the same reason: a
    reference to nothing is noise, not an unresolved declaration, when the token
    was never a sheet identity in the first place.
    """
    from services import sheet_identity

    lines = page.get("lines") or []
    numbers, targets = [], []
    for line in lines:
        text = (line.get("text") or "").strip()
        if _DETAIL_NUMBER.match(text):
            numbers.append(line)
            continue
        token = sheet_identity.sheet_token(text)
        if token and token in known_tokens:
            targets.append((token, line))

    found = []
    for token, target in targets:
        if self_token and token == self_token:
            # A sheet does not cite itself. Measured, not assumed: the geometry
            # admits the sheet's own number beside a drawing number in its title
            # block, and every one of those is a self-reference.
            continue
        for number in numbers:
            basis = positional_basis(number, target)
            if basis is None:
                continue
            found.append({
                "detail_number": (number.get("text") or "").strip(),
                "sheet_token": token,
                # VERBATIM, in the order a person reads the bubble.
                "reference_text": "%s %s" % ((number.get("text") or "").strip(),
                                             (target.get("text") or "").strip()),
                "target_text": (target.get("text") or "").strip(),
                "positional_basis": basis,
                "extraction_pass": target.get("extraction_pass"),
                "reason": ("a detail number and a sheet token sharing one split "
                           "bubble: offset %.2f target-heights right, %.2f down"
                           % (basis["dx_in_target_heights"],
                              basis["dy_in_target_heights"])),
            })
    return found


def register_detail_callouts(store, workspace, source_id: str, *,
                             actor: str = "system", governance_log=None,
                             dry_run: bool = False) -> dict:
    """Register one Source's declared detail callouts. Returns a report, never raises."""
    from services.case_workspace import (
        CaseWorkspaceError, REFERENCE_TYPE_DETAIL_CALLOUT,
        RESOLUTION_STATUS_RESOLVED_EXACT, RESOLUTION_STATUS_RESOLVED_MULTIPLE,
        RESOLUTION_STATUS_TARGET_NOT_FOUND,
    )
    from services import sheet_identity, view_reference

    report = {"source_id": source_id, "method": CALLOUT_METHOD,
              "version": CALLOUT_VERSION, "boundary": "page",
              "pages_inspected": 0, "candidates": 0, "references_created": 0,
              "resolved": [], "not_found": [], "ambiguous": [], "pages": []}

    source = next((s for s in (getattr(workspace, "sources", None) or [])
                   if s.get("id") == source_id), None)
    if source is None:
        report["reason"] = "source not found"
        return report
    self_tokens = sheet_identity.source_sheet_tokens(source)
    self_token = next(iter(self_tokens), None) if len(self_tokens) == 1 else None

    # SAME-PROJECT AND ACTIVE BY CONSTRUCTION, through the existing rule:
    # `eligible_targets` excludes removed Sources and the citing Source itself.
    index: dict = {}
    for candidate_source in view_reference.eligible_targets(
            store, workspace, exclude_source_id=source_id):
        for token in sheet_identity.source_sheet_tokens(candidate_source):
            index.setdefault(token, []).append(candidate_source["id"])

    pages = positioned_pages_for(workspace, source_id)
    report["pages_inspected"] = len(pages)
    if not index:
        return report

    candidates, known = [], set()
    for page in pages:
        found = callout_candidates(page, set(index), self_token=self_token)
        if found:
            report["pages"].append({
                "structural_unit_id": page["unit"]["id"],
                "label": page["unit"].get("label"),
                "order_index": page["unit"].get("order_index"),
                "candidates": len(found),
            })
        for item in found:
            matched = index.get(item["sheet_token"], [])
            known.update(matched)
            candidates.append({
                "reference_text": item["reference_text"],
                "reference_type": REFERENCE_TYPE_DETAIL_CALLOUT,
                "candidate_targets": list(matched),
                # `list` when several Sources answer to one identity, so the
                # store reports RESOLVED_MULTIPLE rather than quietly choosing.
                "syntactic_form": "list" if len(matched) > 1 else "single",
                "detail_number": item["detail_number"],
                "sheet_token": item["sheet_token"],
                "structural_unit_id": page["unit"]["id"],
                "page_label": page["unit"].get("label"),
                "positional_basis": item["positional_basis"],
                "extraction_pass": item["extraction_pass"],
                "reason": item["reason"],
            })
    report["candidates"] = len(candidates)
    if not candidates:
        return report

    if dry_run:
        for candidate in candidates:
            bucket = ("resolved" if len(candidate["candidate_targets"]) == 1
                      else "ambiguous" if candidate["candidate_targets"]
                      else "not_found")
            report[bucket].append(candidate)
        return report

    text = "\n".join(c["reference_text"] for c in candidates)
    try:
        created = store.extract_and_register_source_references(
            workspace, source_id=source_id, text=text,
            origin_context={"origin": CALLOUT_METHOD,
                            "location_type": "detail_callout",
                            "boundary": "page",
                            "pages": report["pages"]},
            known_targets={REFERENCE_TYPE_DETAIL_CALLOUT: known},
            resolution_method=CALLOUT_METHOD,
            resolved_target_type="source",
            extractor_version=CALLOUT_VERSION,
            candidates=candidates,
            actor=actor, governance_log=governance_log)
    except CaseWorkspaceError as exc:
        report["reason"] = str(exc)
        return report

    report["references_created"] = len(created)
    for reference in created:
        status = reference.get("resolution_status")
        if status == RESOLUTION_STATUS_RESOLVED_EXACT:
            report["resolved"].append(reference)
        elif status == RESOLUTION_STATUS_RESOLVED_MULTIPLE:
            report["ambiguous"].append(reference)
        elif status == RESOLUTION_STATUS_TARGET_NOT_FOUND:
            report["not_found"].append(reference)
    return report


def mutual_edges(workspace) -> dict:
    """Which declared callouts are confirmed from BOTH ends? An OBSERVATION.

    Section 9's rule, and its limit: mutuality is recorded as a property of the
    evidence, never as a validity requirement. A section that cuts through a
    detail is not obliged to be cited back by it, and demanding reciprocity
    would discard real one-way references to manufacture tidiness.
    """
    edges = set()
    by_source = {}
    for reference in (getattr(workspace, "source_references", None) or []):
        if (reference.get("origin_context") or {}).get("origin") != CALLOUT_METHOD:
            continue
        for target in reference.get("resolved_target_ids") or []:
            edges.add((reference["source_id"], target))
            by_source.setdefault(reference["source_id"], set()).add(target)
    mutual = {(a, b) for (a, b) in edges if (b, a) in edges}
    return {"directed": sorted(edges), "directed_count": len(edges),
            "mutual": sorted(mutual), "mutual_count": len(mutual),
            "one_way_count": len(edges) - len(mutual)}
