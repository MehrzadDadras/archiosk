"""CLAUDE-FINDING-CAPTURE-01 - preserve what was actually looked at.

SCREENSHOT CAPTURE != AUTHORITY. Product Owner, 2026-09-22.

When an investigation records a material claim against a region of a drawing,
the pixels it was reading are recoverable today only by going back to the
original and trusting that the region still means what it meant. That is fine
until the original is superseded, and then the claim survives while the thing
it was about does not.

This captures the region as a derivative image at the moment the claim is made,
through `image_intelligence.extract_bounded_crop` - the EXISTING capability,
called rather than reimplemented. That function already produces a real
governed Source with `origin_type=derivative_crop`, `origin_reference=<region
id>`, its own sha256, an EXIF-stripped derivative and a governance-log entry.
Nothing here re-does any of it.

WHAT A CAPTURE IS. Evidence of observation: this is what the engine was looking
at, at this time. It is NOT evidence that the reading was correct, and it
confers no authority on the claim it accompanies - a capture is a photograph of
a page, and a photograph of a page has never made the page true. The derivative
is an ordinary Source; it carries no evidence class, no validation status and no
adoption state of its own.

BOUNDED, AND HONEST WHEN IT CANNOT RUN. `extract_bounded_crop` requires a
rectangular region over a source with readable image bytes. Most claims do not
have that - a text span in a PDF, a table cell, a region on a source stored
without a file. Those are the ordinary case, not failures. Every skip returns a
named reason and NOTHING is raised, because a claim must never fail to be
recorded because its illustration could not be made. That is the same
degradation contract `services/sheet_vision.py` already follows: the governed
result completes either way, and the enrichment says honestly why it is absent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from services.case_workspace import (
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_EVIDENCE_ITEM,
    CaseWorkspaceStore,
    ProjectWorkspace,
)

# Named skip reasons. A caller that surfaces "no capture" to a reviewer should
# be able to say which of these it was, because "no rectangular region" and
# "the file is missing" call for completely different responses.
SKIPPED_NO_CAPTURE_DIR = "no_capture_directory_configured"
SKIPPED_NO_REGION = "no_region_anchor_on_this_claim"
SKIPPED_REGION_NOT_RECTANGULAR = "region_is_not_rectangular"
SKIPPED_NO_STORED_FILE = "source_has_no_stored_original"
SKIPPED_UNREADABLE = "stored_original_could_not_be_read"

# A claim can cite several endpoints. Capturing every one of them would turn a
# three-relationship investigation into a dozen derivative Sources nobody asked
# for, so the first capturable region wins and the rest are left alone. The
# claim's own evidence_links remain the complete record of what it rests on;
# this is an illustration of one of them, and does not pretend to be a survey
# of all of them.
_MAX_CAPTURES_PER_CLAIM = 1


def _rectangular_regions_of(workspace: ProjectWorkspace, claim: dict) -> list[tuple[str, str]]:
    """(source_id, region_id) for each cited endpoint that could be cropped."""
    found: list[tuple[str, str]] = []
    for link in claim.get("evidence_links") or []:
        kind, ident = link.get("object_type"), link.get("object_id")
        region_id = None
        if kind == OBJECT_KIND_ADDRESSABLE_REGION:
            region_id = ident
        elif kind == OBJECT_KIND_EVIDENCE_ITEM:
            item = next((e for e in workspace.evidence_items if e["id"] == ident), None)
            region_id = (item or {}).get("region_id")
        if not region_id:
            continue
        region = next((r for r in workspace.addressable_regions
                       if r["id"] == region_id), None)
        if region is None or region.get("region_type") != "rectangular":
            continue
        unit = next((u for u in workspace.structural_units
                     if u["id"] == region.get("structural_unit_id")), None)
        if unit is None:
            continue
        found.append((unit["source_id"], region_id))
    return found


def capture_claim_region(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    claim_id: str,
    capture_dir: Optional[Path],
    actor: str = "system",
    governance_log=None,
) -> dict:
    """Capture the region a claim rests on, or say plainly why it could not.

    Returns `{"captured": bool, "source_id", "region_id",
    "derivative_source_id", "skipped_reason"}`. NEVER RAISES: the claim is
    already recorded by the time this runs, and an illustration that fails must
    not retroactively endanger it.
    """
    result = {"captured": False, "claim_id": claim_id, "source_id": None,
              "region_id": None, "derivative_source_id": None,
              "skipped_reason": None}

    if capture_dir is None:
        result["skipped_reason"] = SKIPPED_NO_CAPTURE_DIR
        return result

    claim = next((c for c in workspace.claims if c["id"] == claim_id), None)
    if claim is None:
        result["skipped_reason"] = SKIPPED_NO_REGION
        return result

    candidates = _rectangular_regions_of(workspace, claim)
    if not candidates:
        # Distinguish "cites no region at all" from "cites one we cannot crop",
        # because only the second is worth a reviewer's attention.
        cites_a_region = any(
            (link.get("object_type") == OBJECT_KIND_ADDRESSABLE_REGION)
            or (link.get("object_type") == OBJECT_KIND_EVIDENCE_ITEM
                and next((e.get("region_id") for e in workspace.evidence_items
                          if e["id"] == link.get("object_id")), None))
            for link in claim.get("evidence_links") or [])
        result["skipped_reason"] = (SKIPPED_REGION_NOT_RECTANGULAR
                                    if cites_a_region else SKIPPED_NO_REGION)
        return result

    from services.image_intelligence import ImageIntelligenceError, extract_bounded_crop

    for source_id, region_id in candidates[:_MAX_CAPTURES_PER_CLAIM]:
        result["source_id"], result["region_id"] = source_id, region_id
        source = next((s for s in workspace.sources if s["id"] == source_id), None)
        if source is None or not source.get("file_path"):
            result["skipped_reason"] = SKIPPED_NO_STORED_FILE
            return result
        try:
            crop = extract_bounded_crop(
                store, workspace, source_id=source_id, region_id=region_id,
                sources_dir=Path(capture_dir), actor=actor,
                governance_log=governance_log)
        except (ImageIntelligenceError, OSError):
            # Including a missing file on disk, an unreadable image, and a
            # region whose address does not describe a box.
            result["skipped_reason"] = SKIPPED_UNREADABLE
            return result
        result["captured"] = True
        result["derivative_source_id"] = crop["derivative_source_id"]
        result["derivative_checksum"] = crop.get("derivative_checksum")
        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="claim_region_captured",
                actor=actor, role="machine",
                payload={"claim_id": claim_id, "region_id": region_id,
                         "source_id": source_id,
                         "derivative_source_id": result["derivative_source_id"],
                         "note": "Observation capture. Not authority for the claim."},
                correlation_id=claim_id)
        return result

    return result
