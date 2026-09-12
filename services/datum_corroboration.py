"""CLAUDE-DATUM-CORROBORATION-01 - two disciplines, independently, saying the same thing.

    ARCHITECTURE states a level for a named datum
    STRUCTURE   states a level for the SAME named datum
    the two normalise to the SAME number  ->  CORROBORATED

AN EXACT MATCH MAY CORROBORATE. A MISMATCH MAY NOT ACCUSE.

That asymmetry is the whole design, and it is measured rather than cautious.
Architectural values come from OCR; structural values come from exact native
text. Against the structural register, architectural readings produced 7 exact
matches and 3 near misses - and every near miss is indistinguishable from a real
coordination error by its value alone:

  - `192320` against `192610`, delta -290 mm. It reads like a textbook
    discrepancy. It is `C.L. OF RD.`, the ROAD CENTRELINE - an architecture-only
    datum with no structural counterpart at all, which a nearest-value pairing
    forced onto the closest structural number and turned into a conflict that
    does not exist.
  - `186620` against `186670` (-50) and `191700` against `191500` (+200): a
    single mis-read digit on a six-digit millimetre datum produces a delta of
    exactly the magnitude a genuine error has.

An exact match is SELF-CORROBORATING: a mis-read digit destroys a match, it can
never create one. A mismatch is ambiguous between a mis-read digit, an
architecture-only datum, and a real conflict - so a mismatch is recorded as
UNRESOLVED and nothing is asserted. Product Owner decision of 2026-09-11:
corroboration is authorized, discrepancy assertion from an OCR-derived mismatch
is NOT.

NO NEW VOCABULARY. A corroboration is `RELATIONSHIP_TYPE_CORRESPONDS_TO`, whose
own definition already says it makes no field-versus-design claim, written
through the existing `record_relationship`. Nothing here creates a discrepancy
type, a finding, or a claim.

ASSOCIATION IS POSITIONAL, AND THE ALTERNATIVE WAS MEASURED AND REJECTED.
Reading a name from the text stream near a number returned `PERIMETER BEAM`
against five different values, because a datum block interleaves names and
numbers in reading order. On the page a datum marker is a bubble holding the
value and its qualifier, with the name set immediately alongside: measured on
stored evidence the name sits at a gap of ~0.001 of the frame while the next
candidate is ten times further.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

CORROBORATION_METHOD = "declared_datum_corroboration"
#: Bump when the RULE changes, so an older corroboration is never silently
#: compared against a newer one's reasoning.
CORROBORATION_VERSION = "datum-corroboration@1"

#: A site datum in this corpus is a six-digit millimetre elevation (186670 =
#: 186.670 m) or its metre form (186.67). Bounded deliberately: a three-digit
#: number on a structural sheet is a member size, not a level.
_MM = re.compile(r"^(1[89]\d{4}|20\d{4})$")
_METRE = re.compile(r"^(1[89]\d|20\d)\.(\d{2})$")

#: What a drawing writes beside a level to say WHICH FACE of it is meant.
#: A qualifier is not the datum's name and must never be read as one.
_QUALIFIER = re.compile(r"^(U/S|T/O|U\.S\.|T\.O\.|US|TO|C\.B\.|CB)$", re.IGNORECASE)

#: Words that carry no identity. Kept tiny on purpose - a stop list that grows
#: becomes a way to force two different datums to look like one.
_STOP = {"OF", "THE", "AND"}

#: How far from the value a label may sit, as a multiple of the value box's own
#: width. Measured on stored evidence: a real name sits at 0.27-0.32 of that
#: width and the next candidate at 2.7. This is that separation with room, not a
#: fitted threshold.
NAME_GAP_MULTIPLE = 1.0

#: Shared tokens required before two differently-spelled names are treated as
#: one datum. `EXT ST` and `EXT ST FTG` are the same footing; `PARK FTG` and
#: `PARK SLAB` share only `PARK` and are NOT the same thing.
MIN_SHARED_TOKENS = 2

STATUS_CORROBORATED = "corroborated"
STATUS_UNRESOLVED = "unresolved"


def name_tokens(text: Optional[str]) -> frozenset:
    """A datum name as an ORDER-INSENSITIVE token set.

    Order-insensitive because the two sides do not agree on it: structure writes
    `ELEV. FTG` in exact native text and OCR returns `FTG ELEV` from the same
    label on an architectural sheet. Insisting on a string match would abstain
    on a datum both documents plainly name.
    """
    cleaned = re.sub(r"[^A-Z0-9 ]", " ", (text or "").upper())
    return frozenset(t for t in cleaned.split() if t and t not in _STOP)


def to_millimetres(text: Optional[str]) -> Optional[int]:
    """One unit for one project. Structure states mm, architecture states m.

    A STATED-VALUE normalisation, never a measurement: both numbers are read off
    the drawings as the documents wrote them, and nothing here derives a
    magnitude from page geometry. Product Owner decision of 2026-09-11 (Option
    C) governs, and is untouched.
    """
    candidate = (text or "").strip()
    if _MM.match(candidate):
        return int(candidate)
    match = _METRE.match(candidate)
    if match:
        return int(match.group(1)) * 1000 + int(match.group(2)) * 10
    return None


def _centre_band(a, b):
    """Do two boxes overlap in the axis the text reads along?"""
    return not (a["y"] + a["height"] < b["y"] or b["y"] + b["height"] < a["y"])


def names_beside(value_line, lines) -> list:
    """Every label immediately beside this value, nearest on each side.

    BOTH SIDES, because a real datum carries two labels often enough to matter:
    `192610` is written between `F.F.` and `GR. FL. SLAB`, and both are true
    names for it. Taking only the nearer would silently drop the one the other
    discipline happens to use.
    """
    width = value_line.get("width") or 0.0
    if width <= 0:
        return []
    bound = width * NAME_GAP_MULTIPLE
    best = {}
    for line in lines:
        if line is value_line:
            continue
        text = (line.get("text") or "").strip()
        if not text or _QUALIFIER.match(text):
            continue
        if to_millimetres(text) is not None:
            continue                      # a number is not a name
        if not _centre_band(value_line, line):
            continue
        if line["x"] >= value_line["x"] + width:
            side, gap = "right", line["x"] - (value_line["x"] + width)
        elif line["x"] + (line.get("width") or 0.0) <= value_line["x"]:
            side, gap = "left", value_line["x"] - (line["x"] + (line.get("width") or 0.0))
        else:
            continue
        if gap > bound:
            continue
        if side not in best or gap < best[side][0]:
            best[side] = (gap, line)
    return [{"text": (line.get("text") or "").strip(), "side": side,
             "gap": round(gap, 6), "tokens": name_tokens(line.get("text"))}
            for side, (gap, line) in sorted(best.items())]


def datum_register(workspace, source_id: str) -> list:
    """Every named datum level this Source states, with where it was read.

    Built on the positioned evidence the perception worker already wrote, joined
    page by page through `detail_callout.positioned_pages_for` - the same
    region-to-unit join that is the tenant boundary everywhere else.
    """
    from services import detail_callout

    entries = []
    for page in detail_callout.positioned_pages_for(workspace, source_id):
        lines = page.get("lines") or []
        for line in lines:
            verbatim = (line.get("text") or "").strip()
            millimetres = to_millimetres(verbatim)
            if millimetres is None:
                continue
            names = names_beside(line, lines)
            if not names:
                # A level nobody named is not a datum this system can compare.
                continue
            entries.append({
                "value_mm": millimetres,
                "verbatim": verbatim,
                "unit_as_written": "mm" if _MM.match(verbatim) else "m",
                "names": [n["text"] for n in names],
                "name_tokens": [n["tokens"] for n in names],
                "name_gaps": [n["gap"] for n in names],
                "region_id": line.get("region_id"),
                "structural_unit_id": page["unit"]["id"],
                "page_label": page["unit"].get("label"),
                "extraction_pass": line.get("extraction_pass"),
                "source_id": source_id,
            })
    return entries


def _match_names(left_tokensets, right_tokensets):
    """Are these two datums the SAME declared condition? Abstains on ambiguity."""
    for left in left_tokensets:
        for right in right_tokensets:
            if not left or not right:
                continue
            if left == right:
                return True, "identical declared name"
            shared = left & right
            if len(shared) >= MIN_SHARED_TOKENS and (
                    left <= right or right <= left):
                return True, "one declared name contains the other (%s)" % (
                    " ".join(sorted(shared)))
    return False, None


def corroborate(workspace, left_source_id: str, right_source_id: str) -> dict:
    """Compare two Sources' declared datums. Asserts only on an exact match."""
    left = datum_register(workspace, left_source_id)
    right = datum_register(workspace, right_source_id)
    report = {"method": CORROBORATION_METHOD, "version": CORROBORATION_VERSION,
              "left_source_id": left_source_id, "right_source_id": right_source_id,
              "left_datums": len(left), "right_datums": len(right),
              "corroborated": [], "unresolved": []}

    for a in left:
        candidates = []
        for b in right:
            matched, basis = _match_names(a["name_tokens"], b["name_tokens"])
            if matched:
                candidates.append((b, basis))
        if not candidates:
            continue
        targets = {b["value_mm"] for b, _ in candidates}
        if len(candidates) > 1 and len(targets) > 1:
            # The same declared name resolving to two different stated values is
            # not something to choose between.
            report["unresolved"].append({
                "reason": "ambiguous counterpart",
                "names": a["names"], "value_mm": a["value_mm"],
                "candidate_values": sorted(targets),
                "left": a, "status": STATUS_UNRESOLVED,
            })
            continue
        b, basis = candidates[0]
        if a["value_mm"] == b["value_mm"]:
            report["corroborated"].append({
                "status": STATUS_CORROBORATED,
                "value_mm": a["value_mm"],
                "name_basis": basis,
                "left": a, "right": b,
                "left_verbatim": a["verbatim"], "right_verbatim": b["verbatim"],
                "normalisation": "%s (%s) == %s (%s) -> %d mm"
                                 % (a["verbatim"], a["unit_as_written"],
                                    b["verbatim"], b["unit_as_written"],
                                    a["value_mm"]),
            })
        else:
            # DELIBERATELY NOT A DISCREPANCY. A mismatch is ambiguous between a
            # mis-read digit, a datum only one discipline has, and a real
            # conflict - and the measured near-miss rate makes that ambiguity
            # real rather than theoretical.
            report["unresolved"].append({
                "status": STATUS_UNRESOLVED,
                "reason": "stated values differ; extraction fidelity does not "
                          "yet support a discrepancy claim",
                "names": a["names"], "left_value_mm": a["value_mm"],
                "right_value_mm": b["value_mm"],
                "delta_mm": a["value_mm"] - b["value_mm"],
                "left": a, "right": b,
            })
    return report


def record_corroborations(store, workspace, left_source_id: str,
                          right_source_id: str, *, actor: str = "system",
                          governance_log=None, dry_run: bool = False) -> dict:
    """Write one CORRESPONDS_TO edge per corroborated datum. Never raises.

    PROVISIONAL, because a machine derived it. The edge says two Sources state
    the same value for the same declared datum; it does not say a human has
    agreed, and `provisional=False` is reserved for exactly that elsewhere in
    this store.

    NOTHING IS WRITTEN FOR AN UNRESOLVED PAIR. They are returned in the report
    so a reader can see what was examined and declined, which is the honest
    shape of an abstention - but no governed record asserts them.
    """
    from services.case_workspace import (
        CaseWorkspaceError, RELATIONSHIP_TYPE_CORRESPONDS_TO,
    )

    report = corroborate(workspace, left_source_id, right_source_id)
    report["relationships_created"] = 0
    if dry_run or not report["corroborated"]:
        return report

    existing = {(r.get("from_id"), r.get("to_id"), r.get("relationship_type"))
                for r in (getattr(workspace, "relationships", None) or [])}
    created = []
    for item in report["corroborated"]:
        from_id = item["left"]["region_id"]
        to_id = item["right"]["region_id"]
        if not from_id or not to_id:
            continue
        key = (from_id, to_id, RELATIONSHIP_TYPE_CORRESPONDS_TO)
        if key in existing:
            continue          # exactly-once by re-check, as everywhere else
        try:
            edge = store.record_relationship(
                workspace,
                from_type="addressable_region", from_id=from_id,
                to_type="addressable_region", to_id=to_id,
                relationship_type=RELATIONSHIP_TYPE_CORRESPONDS_TO,
                created_by=actor, provisional=True,
                reason=("%s: both sources state %s for %s [%s]"
                        % (CORROBORATION_VERSION, item["normalisation"],
                           " / ".join(item["left"]["names"]), item["name_basis"])))
            created.append(edge["id"])
            existing.add(key)
        except CaseWorkspaceError as exc:
            logger.warning("corroboration refused for %s -> %s: %s",
                           from_id, to_id, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("corroboration not stored for %s -> %s (%s: %s)",
                           from_id, to_id, type(exc).__name__, exc)

    report["relationships_created"] = len(created)
    report["relationship_ids"] = created
    if governance_log is not None:
        governance_log.append(
            project_id=workspace.project_id,
            event_type="datum_corroboration_recorded",
            actor=actor, role="system",
            payload={
                "left_source_id": left_source_id,
                "right_source_id": right_source_id,
                "corroborated": len(report["corroborated"]),
                "unresolved": len(report["unresolved"]),
                "relationships_created": len(created),
                "method": CORROBORATION_METHOD,
                "version": CORROBORATION_VERSION,
            },
            correlation_id=left_source_id)
    return report
