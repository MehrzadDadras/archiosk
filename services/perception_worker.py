"""CLAUDE-GO-PERCEPTION-WORKER-01 - the process that does the looking.

One job at a time, on purpose. The production host is 6 vCPU / 11 GB with no
GPU and thirteen Gunicorn workers already resident; the web tier remains the
primary workload, and throughput is not what this tranche is buying. What it
buys is that an eight-second OCR no longer occupies a request.

NO NEW PERCEPTION CAPABILITY. This runs exactly the orientation-normalised OCR
path that already shipped, in a different place, so the plumbing can be proven
on known behaviour. If the text changes, the move is at fault - not a new
extractor nobody has measured.

    claim -> read source -> perceive -> write evidence -> complete

The worker never accepts a filesystem path from a job record. It is given a
workspace id and a source id and resolves the bytes through the authoritative
store, which is what keeps a job from being able to name someone else's file.
"""
from __future__ import annotations

import logging
import signal
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0

# How many times a workspace write is retried when the customer happens to be
# doing something at the same moment. Renaming an examination or asking GO a
# question while perception runs is ORDINARY, not a conflict, and it must never
# surface to them as a 409.
CONCURRENT_WRITE_RETRIES = 5


class _Stopped(Exception):
    pass


def read_source_bytes(store, workspace_id: str, source_id: str) -> Optional[bytes]:
    """THE relocation seam, and the tenant boundary.

    A filesystem read today; an authenticated fetch when perception moves to a
    separate node. Nothing else in the domain model knows where bytes come
    from, so relocating changes this function and not the Document Shop model.

    The path is resolved from the STORE, never from the job, and is confined
    under the registry root - a job record cannot name an arbitrary file, and
    a source id belonging to another workspace simply is not found here.
    """
    workspace = store.get(workspace_id)
    if workspace is None:
        return None
    source = next((s for s in (workspace.sources or [])
                   if s.get("id") == source_id and not s.get("removed_at")), None)
    if source is None or not source.get("file_path"):
        return None
    path = Path(source["file_path"]).resolve()
    root = Path(store.store_path).resolve()
    if root not in path.parents:
        # A stored path that escapes the registry root is refused outright.
        # Nothing writes such a path today; the check exists so a future record
        # that somehow carries one cannot make the worker read it.
        logger.warning("refusing source outside the registry root: %s", path)
        return None
    if not path.exists():
        return None
    return path.read_bytes()


def _write_evidence_with_retry(store, workspace_id, source_id, text,
                               extractor_version, governance_log, actor):
    """Attach recovered text, tolerating the customer working at the same time.

    CaseWorkspaceStore.save is optimistic-concurrency: it refuses to overwrite
    a record that moved under it. A customer renaming their examination or
    posting a conversation turn mid-job moves it legitimately, so the answer is
    to re-read and re-apply, not to fail the job and not to show anyone a
    write-collision page.
    """
    from services.case_workspace import EVIDENCE_CLASS_EXTRACTED

    last_error = None
    for attempt in range(CONCURRENT_WRITE_RETRIES):
        workspace = store.get(workspace_id)
        if workspace is None:
            return None, "workspace no longer exists"
        try:
            outcome = store.register_pdf_page_structure(
                workspace, source_id=source_id, pages=[text],
                extractor_version=extractor_version, actor=actor,
                governance_log=governance_log,
                evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED})
            return outcome, None
        except Exception as exc:
            last_error = exc
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                raise
            time.sleep(0.2 * (attempt + 1))
    return None, "workspace kept changing: %s" % last_error


def _page_units_for(workspace, source_id):
    """This Source's page StructuralUnits, in the document's own order.

    CLAUDE-GO-PERCEPTION-PDF-OCR-01. `register_pdf_page_structure` creates one
    unit per page and assigns `order_index` from the page's position, so the
    document's order is already recorded and does not need to be re-derived
    from creation time or from a uuid.
    """
    units = [u for u in (getattr(workspace, "structural_units", None) or [])
             if u.get("source_id") == source_id and u.get("unit_type") == "page"]
    units.sort(key=lambda u: (u.get("order_index") if u.get("order_index") is not None
                              else 0))
    return units


def _resolve_unit(workspace, source_id, structural_unit_id):
    """The named page unit, or the Source's first one when none is named.

    One lookup for every stage, so the PDF path cannot bind positioned text to
    page n while legend detection binds to page 1.
    """
    units = _page_units_for(workspace, source_id)
    if structural_unit_id is None:
        return units[0] if units else None
    return next((u for u in units if u.get("id") == structural_unit_id), None)


def _evidence_on_unit(workspace, source_id, unit, content_type):
    """Evidence of this type already attached to THIS page.

    The exactly-once re-check every write stage uses, scoped to one page rather
    than to the whole Source - on a multi-page document the Source-wide form
    would report pages 2..n as an already-completed replay.
    """
    region_ids = {r["id"] for r in (getattr(workspace, "addressable_regions", None) or [])
                  if r.get("structural_unit_id") == unit["id"]}
    return [e for e in (getattr(workspace, "evidence_items", None) or [])
            if e.get("source_id") == source_id
            and e.get("content_type") == content_type
            and e.get("region_id") in region_ids]


def _write_positioned_with_retry(store, job, positioned, extractor_version,
                                 governance_log, structural_unit_id=None):
    """Attach positioned lines, and NEVER fail the job for them.

    CLAUDE-GO-PERCEPTION-REGION-OCR-01, safe degradation (Section 16). The
    text evidence has already been written and the examination has already
    succeeded by the time this runs. Coordinates are an addition to that
    result, so every outcome here - no lines found, the frame unreadable, the
    store refusing a bbox, the workspace moving underneath us - returns None
    and leaves a completed examination completed. A source that could be read
    but not located is a weaker result, not a failed one.

    Anchored to the page StructuralUnit the text evidence already created, so
    positioned regions and paragraphs address the SAME frame of the SAME
    source rather than a second, parallel structure that could drift from it.

    PAGE n MUST BIND TO PAGE n. `structural_unit_id` is passed EXPLICITLY by
    the PDF path. Before CLAUDE-GO-PERCEPTION-PDF-OCR-01 this function chose
    the first page unit on the Source itself, which is correct for a
    one-frame image and silently wrong for a multi-page document - every
    page's lines would have landed on page 1, and the geometry would have
    looked entirely plausible while pointing at the wrong sheet. The image
    path keeps the old behaviour by passing None.
    """
    if not positioned or not positioned.get("lines"):
        return None

    from services.case_workspace import CaseWorkspaceError

    for attempt in range(CONCURRENT_WRITE_RETRIES):
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        if structural_unit_id is not None:
            unit = next(
                (u for u in (getattr(workspace, "structural_units", None) or [])
                 if u.get("id") == structural_unit_id
                 and u.get("source_id") == job["source_id"]), None)
        else:
            unit = next(
                (u for u in (getattr(workspace, "structural_units", None) or [])
                 if u.get("source_id") == job["source_id"]
                 and u.get("unit_type") == "page"), None)
        if unit is None:
            logger.info("no page unit for source %s - positioned text not stored",
                        job["source_id"])
            return None
        # EXACTLY-ONCE, by the same re-check the text evidence uses rather than
        # by trusting that a job runs once: a replayed job must not attach a
        # second copy of every line.
        #
        # SCOPED TO THIS UNIT, not to the Source. A per-Source check was right
        # while a Source had exactly one frame; on a multi-page PDF it would
        # have let page 1 write and then reported every later page as an
        # already-done replay, producing a document positioned on its first
        # page only - a wrong result that looks like a successful one.
        region_ids = {r["id"] for r in (getattr(workspace, "addressable_regions", None) or [])
                      if r.get("structural_unit_id") == unit["id"]}
        already = [e for e in (getattr(workspace, "evidence_items", None) or [])
                   if e.get("source_id") == job["source_id"]
                   and e.get("content_type") == "positioned_text"
                   and e.get("region_id") in region_ids]
        if already:
            return {"evidence_item_ids": [e["id"] for e in already],
                    "region_count": len(already), "replayed": True}
        try:
            return store.register_positioned_text_regions(
                workspace, source_id=job["source_id"],
                structural_unit_id=unit["id"],
                lines=positioned["lines"],
                frame=positioned.get("frame"),
                extractor_version=extractor_version,
                actor="perception-worker",
                governance_log=governance_log)
        except CaseWorkspaceError as exc:
            # A refused bbox is a real refusal and must not be retried into
            # existence - the geometry is wrong, and looping cannot fix it.
            logger.warning("positioned text refused for source %s: %s",
                           job["source_id"], exc)
            return None
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                logger.warning("positioned text not stored for source %s (%s: %s)",
                               job["source_id"], type(exc).__name__, exc)
                return None
            time.sleep(0.2 * (attempt + 1))
    logger.warning("positioned text gave up after contention on source %s",
                   job["source_id"])
    return None


def _detect_legend_candidates(store, job, positioned, governance_log,
                              structural_unit_id=None):
    """Look for a legend block, and NEVER fail the job for it.

    CLAUDE-GO-PERCEPTION-LEGEND-DETECT-01. This runs after the positioned text
    has already been written and the examination has already succeeded. A
    candidate legend region is DETECTION EVIDENCE - a place worth looking at -
    so every failure here returns None and leaves a completed examination
    completed, exactly as the positioned write does.

    Stored through the store's EXISTING single-item writers rather than a new
    batch method: a sheet yields none, one or a couple of candidates, so the
    per-call save that made 508 positioned lines unaffordable costs nothing
    here, and adding a second batch registrar for two rows would be inventing
    an abstraction the volume does not justify.
    """
    from services import legend_detection
    from services.case_workspace import EVIDENCE_CLASS_EXTRACTED

    if not positioned or not positioned.get("lines"):
        return None

    try:
        detection = legend_detection.detect_candidates(
            positioned["lines"], source_id=job["source_id"])
    except Exception as exc:  # noqa: BLE001 - detection is an addition, never a gate
        logger.warning("legend detection raised for source %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)
        return None

    if governance_log is not None:
        # Recorded even when nothing was found. "This sheet does not explain
        # its own symbols" is a real finding about a drawing set, and a log
        # that only records successes cannot answer how often that is true.
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="legend_candidates_detected",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "outcome": detection.get("outcome"),
                "candidate_count": len(detection.get("candidates") or []),
                "rejected_count": len(detection.get("rejected") or []),
                "detection_method": detection.get("detection_method"),
                "detection_version": detection.get("detection_version"),
            },
            correlation_id=job["source_id"])

    candidates = detection.get("candidates") or []
    if not candidates:
        return detection

    from services.case_workspace import CaseWorkspaceError

    workspace = store.get(job["workspace_id"])
    if workspace is None:
        return detection
    unit = _resolve_unit(workspace, job["source_id"], structural_unit_id)
    if unit is None:
        return detection

    # EXACTLY-ONCE by re-check, the same discipline the evidence writes use,
    # and scoped to THIS page so a multi-page PDF is not stopped after its first.
    already = _evidence_on_unit(workspace, job["source_id"], unit,
                                legend_detection.CANDIDATE_CONTENT_TYPE)
    if already:
        return detection

    stored = []
    for candidate in candidates:
        region_box = candidate["region"]
        region = None
        try:
            workspace = store.get(job["workspace_id"])
            region = store.create_addressable_region(
                workspace, structural_unit_id=unit["id"],
                region_type=legend_detection.CANDIDATE_REGION_TYPE,
                address={
                    "x": region_box["x"], "y": region_box["y"],
                    "width": region_box["width"], "height": region_box["height"],
                    # What this region IS, carried on the region itself so a
                    # reader never has to infer it from the evidence beside it.
                    "detection": legend_detection.CANDIDATE_CONTENT_TYPE,
                    "detection_method": candidate["detection_method"],
                    "detection_version": candidate["detection_version"],
                    "heading_text": candidate["heading"]["text"],
                    "marker_kind": candidate["heading"]["marker_kind"],
                    "layout": candidate["layout"],
                    "strength": candidate["strength"],
                    "reason": candidate["reason"],
                    "row_count": candidate["spatial_support"].get("row_count"),
                    "short_label_count":
                        candidate["spatial_support"].get("short_label_count"),
                    "stop_reason": candidate["spatial_support"].get("stop_reason"),
                    # Said in the record, not only in a docstring.
                    "status": candidate["status"],
                },
                actor="perception-worker", governance_log=governance_log)
            workspace = store.get(job["workspace_id"])
            evidence = store.register_evidence_item(
                workspace, source_id=job["source_id"],
                evidence_class=EVIDENCE_CLASS_EXTRACTED,
                # The heading is what was READ. No meaning is asserted, and the
                # strength sits beside it rather than inside the claim.
                content=candidate["heading"]["text"],
                content_type=legend_detection.CANDIDATE_CONTENT_TYPE,
                region_id=region["id"],
                extractor_version=candidate["detection_version"],
                actor="perception-worker", governance_log=governance_log)
            stored.append(evidence["id"])
            # CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01 needs the PARENT region id
            # to hang slices from, and this is the only place it exists.
            # Carried on the candidate rather than returned separately so a
            # slice can never be attached to the wrong block.
            candidate["stored_region_id"] = region["id"]
        except CaseWorkspaceError as exc:
            logger.warning("legend candidate refused for source %s: %s",
                           job["source_id"], exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("legend candidate not stored for source %s (%s: %s)",
                           job["source_id"], type(exc).__name__, exc)

    detection["stored_evidence_item_ids"] = stored
    return detection


def _slice_legend_candidates(store, job, detection, positioned, governance_log,
                             structural_unit_id=None):
    """Split each stored candidate into PROPOSED entry slices. Never a gate.

    CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01. Runs after detection has already
    stored its candidates and the examination has already succeeded, and
    returns None on every failure - a slice is a convenience for a later
    reviewer, and a completed examination stays completed without it.

    NOTHING HERE REGISTERS MEANING. One child AddressableRegion per proposed
    entry, hung off the candidate's own region via the store's existing
    `parent_region_id`, plus one EvidenceItem carrying the text that was READ
    in it. No LegendItem is created, no decision is recorded, no family is
    confirmed and no scope exists to widen - the store methods that could do
    any of those are not called and not imported.

    STORED THROUGH THE EXISTING SINGLE-ITEM WRITERS, measured rather than
    assumed: see the tranche's own timing note. A real block yields entries in
    the tens, not the hundreds that made `register_positioned_text_regions`
    necessary, and a second batch registrar for that volume would be an
    abstraction the measurement does not justify.
    """
    from services import legend_slicing
    from services.case_workspace import CaseWorkspaceError, EVIDENCE_CLASS_EXTRACTED

    if not detection or not positioned or not positioned.get("lines"):
        return None
    candidates = [c for c in (detection.get("candidates") or [])
                  if c.get("stored_region_id")]
    if not candidates:
        return None

    workspace = store.get(job["workspace_id"])
    if workspace is None:
        return None
    unit = _resolve_unit(workspace, job["source_id"], structural_unit_id)
    if unit is None:
        return None

    # EXACTLY-ONCE by re-check, the same discipline every other write here uses,
    # scoped to THIS page for the same reason detection's is.
    already = _evidence_on_unit(workspace, job["source_id"], unit,
                                legend_slicing.ENTRY_CONTENT_TYPE)
    if already:
        return None

    results = []
    for candidate in candidates:
        try:
            sliced = legend_slicing.slice_candidate(candidate, positioned["lines"])
        except Exception as exc:  # noqa: BLE001 - slicing is an addition, never a gate
            logger.warning("legend slicing raised for source %s (%s: %s)",
                           job["source_id"], type(exc).__name__, exc)
            continue

        if governance_log is not None:
            # Recorded even when a block did not resolve. "This legend could
            # not be subdivided" is a real fact about a drawing, and a log that
            # only records successes cannot say how often it happens.
            governance_log.append(
                project_id=job["workspace_id"],
                event_type="legend_entries_proposed",
                actor="perception-worker", role="system",
                payload={
                    "source_id": job["source_id"],
                    "parent_region_id": candidate["stored_region_id"],
                    "outcome": sliced.get("outcome"),
                    "entry_count": sliced.get("entry_count"),
                    "row_count": sliced.get("row_count"),
                    "rhythm_established": sliced.get("rhythm_established"),
                    "slice_method": sliced.get("slice_method"),
                    "slice_version": sliced.get("slice_version"),
                },
                correlation_id=job["source_id"])

        stored = []
        for entry in sliced.get("entries") or []:
            box = entry["region"]
            try:
                workspace = store.get(job["workspace_id"])
                region = store.create_addressable_region(
                    workspace, structural_unit_id=unit["id"],
                    region_type=legend_slicing.ENTRY_REGION_TYPE,
                    # The whole point of the child link: a slice detached from
                    # the block it came from is a rectangle with no provenance.
                    parent_region_id=candidate["stored_region_id"],
                    address={
                        "x": box["x"], "y": box["y"],
                        "width": box["width"], "height": box["height"],
                        "detection": legend_slicing.ENTRY_CONTENT_TYPE,
                        "slice_method": entry["slice_method"],
                        "slice_version": entry["slice_version"],
                        # ORDER IS PERSISTED, never re-derived later from a
                        # UUID, a creation time or a filename.
                        "entry_index": entry["entry_index"],
                        "text_bbox": entry["text_bbox"],
                        "icon_zone": entry["icon_zone"],
                        "icon_zone_reason": entry["icon_zone_reason"],
                        "row_count": entry["row_count"],
                        "text_part_count": entry["text_part_count"],
                        "slice_resolution": entry["slice_resolution"],
                        "reason": entry["reason"],
                        "parent_heading_text": candidate["heading"]["text"],
                        "parent_strength": candidate["strength"],
                        "status": entry["status"],
                    },
                    actor="perception-worker", governance_log=governance_log)
                workspace = store.get(job["workspace_id"])
                evidence = store.register_evidence_item(
                    workspace, source_id=job["source_id"],
                    evidence_class=EVIDENCE_CLASS_EXTRACTED,
                    # WHAT WAS READ, not what it means. This stays observed
                    # text; turning it into a declared meaning is the next
                    # tranche's question and needs a human in it.
                    content=entry["observed_text"],
                    content_type=legend_slicing.ENTRY_CONTENT_TYPE,
                    region_id=region["id"],
                    extractor_version=entry["slice_version"],
                    actor="perception-worker", governance_log=governance_log)
                stored.append(evidence["id"])
            except CaseWorkspaceError as exc:
                logger.warning("legend entry refused for source %s: %s",
                               job["source_id"], exc)
            except Exception as exc:  # noqa: BLE001
                logger.warning("legend entry not stored for source %s (%s: %s)",
                               job["source_id"], type(exc).__name__, exc)
        sliced["stored_evidence_item_ids"] = stored
        results.append(sliced)

    return results


def _register_sheet_index(store, job, governance_log, record):
    """Register declared sheet identities, strictly downstream of a DONE job.

    CLAUDE-SHEET-IDENTITY-WIRING-01. `register_sheet_index` was built, tested
    and deployed with no application caller at all - reachable only by direct
    service invocation, which is not a workflow. This is the whole of the
    wiring: one stage, in the lifecycle point where page evidence exists.

    RUNS AFTER THE JOB IS ALREADY TERMINAL, which is why failure isolation here
    is STRUCTURAL rather than promised. `record` is the completed job record;
    the perception evidence is already written and the job is already marked
    completed before this function is entered. Nothing it can do - raise,
    refuse, or write badly - can turn a successful examination into a failed
    one, because there is no longer a job in flight to fail.

    NO SECOND READ OF THE DOCUMENT. Candidates come from
    `recovered_pages_for`, which reads the evidence the job just wrote to the
    workspace. The bytes are not re-opened, no page is re-OCR'd, and the
    incremental cost is a workspace scan rather than a perception pass.

    CALLED ONLY WHEN JUSTIFIED, and the justification is the existing
    recognition rule: `register_sheet_index` inspects each page, returns
    `is_index=False` for a document whose pages announce no sheet list, and
    writes nothing. An ordinary drawing sheet no-ops here. Abstention is
    preserved exactly as it was measured - nothing is scored and nothing tuned.

    IDEMPOTENT THROUGH THE STORE'S OWN RULE, not a new one:
    `extract_and_register_source_references` keys an existing reference on
    (source_id, reference_text, reference_type, origin_context), and this
    caller's origin_context is derived from the Source's own page units, which
    are registered once. A revisited Source therefore re-resolves and creates
    nothing.
    """
    from services import perception_jobs, sheet_identity

    if not record or record.get("state") != perception_jobs.STATE_COMPLETED:
        return None

    try:
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        report = sheet_identity.register_sheet_index(
            store, workspace, job["source_id"],
            actor="perception-worker", governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001 - the examination is already complete
        # SURFACED, NOT SWALLOWED. The one thing that must not happen is a
        # silent "this source is unreadable" for a document whose drawing
        # evidence was produced perfectly well.
        logger.warning("sheet index registration raised for source %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)
        if governance_log is not None:
            governance_log.append(
                project_id=job["workspace_id"],
                event_type="sheet_index_registration_failed",
                actor="perception-worker", role="system",
                payload={"source_id": job["source_id"],
                         "error_type": type(exc).__name__,
                         "error": str(exc),
                         "perception_state": record.get("state")},
                correlation_id=job["source_id"])
        return None

    if governance_log is not None:
        # Recorded even when the document was not an index. "This source
        # declares no sheet list" is a real fact about a drawing set, and a log
        # that only records index pages cannot say how rare one is.
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="sheet_index_registered",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "is_index": report.get("is_index"),
                "boundary": report.get("boundary"),
                "pages_inspected": report.get("pages_inspected"),
                "index_pages": report.get("index_pages"),
                "candidates": report.get("candidates"),
                "references_created": report.get("references_created"),
                "resolved": len(report.get("resolved") or []),
                "ambiguous": len(report.get("ambiguous") or []),
                "not_found": len(report.get("not_found") or []),
                "method": report.get("method"),
                "version": report.get("version"),
                "reason": report.get("reason"),
            },
            correlation_id=job["source_id"])
    return report


def _register_detail_callouts(store, job, governance_log, record):
    """Register declared detail callouts, strictly downstream of a DONE job.

    CLAUDE-DETAIL-CALLOUT-01, and deliberately the SAME shape as
    `_register_sheet_index`: a bounded downstream capability that runs after the
    job record is already terminal, so failure isolation is structural rather
    than promised. There is no job in flight for it to fail.

    NO SECOND READ. Candidates come from the positioned evidence the job just
    wrote, joined page by page. The bytes are not reopened and no page is
    re-OCR'd.

    JUSTIFIED, NOT BLIND. `register_detail_callouts` proposes nothing unless a
    detail number and a sheet token that names a REAL Source share one split
    bubble. An ordinary sheet with no callouts registers nothing.
    """
    from services import detail_callout, perception_jobs

    if not record or record.get("state") != perception_jobs.STATE_COMPLETED:
        return None

    try:
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        report = detail_callout.register_detail_callouts(
            store, workspace, job["source_id"],
            actor="perception-worker", governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001 - the examination is already complete
        logger.warning("detail callout registration raised for source %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)
        if governance_log is not None:
            governance_log.append(
                project_id=job["workspace_id"],
                event_type="detail_callout_registration_failed",
                actor="perception-worker", role="system",
                payload={"source_id": job["source_id"],
                         "error_type": type(exc).__name__, "error": str(exc),
                         "perception_state": record.get("state")},
                correlation_id=job["source_id"])
        return None

    if governance_log is not None:
        # Recorded even when a sheet declares nothing. "This drawing points
        # nowhere" is a real fact about a set, and a log that records only
        # successes cannot say how common it is.
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="detail_callouts_registered",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "boundary": report.get("boundary"),
                "pages_inspected": report.get("pages_inspected"),
                "pages": report.get("pages"),
                "candidates": report.get("candidates"),
                "references_created": report.get("references_created"),
                "resolved": len(report.get("resolved") or []),
                "ambiguous": len(report.get("ambiguous") or []),
                "not_found": len(report.get("not_found") or []),
                "method": report.get("method"),
                "version": report.get("version"),
                "reason": report.get("reason"),
            },
            correlation_id=job["source_id"])
    return report


def _corroborate_datums(store, job, governance_log, record):
    """Corroborate this sheet's declared datums against the sheets already read.

    CLAUDE-DATUM-CORROBORATION-WIRING-01, and it closes an integration gap I
    created: `record_corroborations` shipped implemented, deployed and proven on
    the real corpus with NO application caller - every corroboration that
    existed had been produced by a scratchpad script rather than by ARCHIOSK.
    That is the exact pattern the master plan section 2 exists to catch, and it
    is the second time this programme has produced it.

    WHY HERE. A corroboration needs TWO sources, and the worker sees one job at
    a time - so the moment a sheet's datum evidence lands is the first moment its
    counterparts can be known. This runs after the job record is already
    terminal, which is why failure isolation is structural rather than promised:
    there is no job in flight left to fail.

    BOUNDED BY THE CHEAPEST TEST FIRST. Most sheets state no datum at all, so
    this asks THIS source's register before it asks anyone else's, and does
    nothing at all when the answer is empty. Only a sheet that actually declares
    a level pays for the pairwise comparison.

    NOTHING NEW IS ASSERTED. The claim boundary is unchanged and is not restated
    here because it lives in one place: an exact match may corroborate, a
    mismatch stays UNRESOLVED and writes nothing. No claim, finding or
    discrepancy writer is reachable from this path.
    """
    from services import datum_corroboration, perception_jobs

    if not record or record.get("state") != perception_jobs.STATE_COMPLETED:
        return None

    try:
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        mine = datum_corroboration.datum_register(workspace, job["source_id"])
        if not mine:
            # This sheet declares no datum. The commonest case, and the one that
            # must cost nothing.
            return None
        # EVERY REGISTER BUILT ONCE. Reading one back costs a walk of the whole
        # workspace evidence list, and rebuilding it per pair is what took the
        # full gate from ~11 minutes to 22:22 on the tranche that introduced
        # this stage.
        others = datum_corroboration.registers_for(
            workspace, exclude_source_id=job["source_id"])
        counterparts = list(others)
        reports = []
        for other in counterparts:
            workspace = store.get(job["workspace_id"])
            if workspace is None:
                break
            reports.append(datum_corroboration.record_corroborations(
                store, workspace, job["source_id"], other,
                actor="perception-worker", governance_log=governance_log,
                left_register=mine, right_register=others[other]))
    except Exception as exc:  # noqa: BLE001 - the examination is already complete
        logger.warning("datum corroboration raised for source %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)
        if governance_log is not None:
            governance_log.append(
                project_id=job["workspace_id"],
                event_type="datum_corroboration_failed",
                actor="perception-worker", role="system",
                payload={"source_id": job["source_id"],
                         "error_type": type(exc).__name__, "error": str(exc),
                         "perception_state": record.get("state")},
                correlation_id=job["source_id"])
        return None

    corroborated = sum(len(r.get("corroborated") or []) for r in reports)
    unresolved = sum(len(r.get("unresolved") or []) for r in reports)
    created = sum(r.get("relationships_created") or 0 for r in reports)
    if governance_log is not None:
        # Recorded even when nothing corroborated. "These two sheets state the
        # same datum differently" is a real fact about a drawing set, and an
        # abstention a reader cannot see is indistinguishable from not looking.
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="datum_corroboration_completed",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "datums_declared": len(mine),
                "counterpart_sources": len(counterparts),
                "corroborated": corroborated,
                "unresolved": unresolved,
                "relationships_created": created,
                "method": datum_corroboration.CORROBORATION_METHOD,
                "version": datum_corroboration.CORROBORATION_VERSION,
            },
            correlation_id=job["source_id"])
    return {"datums": len(mine), "counterparts": len(counterparts),
            "corroborated": corroborated, "unresolved": unresolved,
            "relationships_created": created, "reports": reports}


def _run_pdf_job(app, jobs, store, job, raw, governance_log):
    """Perceive a PDF, page by page, binding page n to page n.

    CLAUDE-GO-PERCEPTION-PDF-OCR-01. The real drawing corpus is predominantly
    raster - of every real sheet available to this project, all but one carry no
    native text layer at all - so a pipeline that positions only standalone
    images cannot see the documents clients actually send. `ingestion` has been
    enqueueing perception jobs for PDFs all along; they were terminating at a
    file-type gate.

    NO SECOND OCR PASS. Each page is read exactly as an image frame is: one
    `get_textpage_ocr`, asked twice for plain text and word boxes. The geometry
    recovered here was already being produced and thrown away.

    NO MAGNITUDE, NO TRANSFORM, NO VIEWPORT. Every coordinate stays a fraction
    of the page it was read from, which is the existing convention and the
    reason nothing here needs a scale. Product Owner decision of 2026-09-11
    (Option C) governs: identity-first, and physical magnitude is not derived
    from page geometry.
    """
    from services import perception_jobs, positioned_text
    from services.case_workspace import EVIDENCE_CLASS_EXTRACTED

    read = positioned_text.read_pdf_positioned_pages(raw)
    if not read.get("ran"):
        return jobs.complete(
            job, state=perception_jobs.STATE_NEEDS_ATTENTION,
            failure_reason=read.get("reason") or "no page of this PDF could be read")

    pages = read.get("pages") or []
    page_texts = [(p.get("text") or "") for p in pages]
    if not any(t.strip() for t in page_texts):
        # Ran, established nothing. A fact about the document, not a fault -
        # the same answer the image path gives for an unreadable photograph.
        return jobs.complete(
            job, state=perception_jobs.STATE_NEEDS_ATTENTION,
            failure_reason="no readable text was recovered from any page")

    engine = next((p.get("engine") for p in pages if p.get("engine")), None)
    engine_version = next((p.get("engine_version") for p in pages
                           if p.get("engine_version")), None)
    extractor_version = "%s %s" % (engine, engine_version)

    # PAGE STRUCTURE IS REGISTERED ONCE, AND ONLY IF IT IS NOT ALREADY THERE.
    # A Project-path PDF had its pages registered during ingestion; a Document
    # Shop PDF did not. Registering a second time would give one Source two
    # parallel page structures, and every later stage would have to guess which
    # one it meant.
    workspace = store.get(job["workspace_id"])
    if workspace is None:
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason="workspace no longer exists")
    if not _page_units_for(workspace, job["source_id"]):
        _outcome, error = _write_pdf_pages_with_retry(
            store, job["workspace_id"], job["source_id"], page_texts,
            extractor_version, governance_log, EVIDENCE_CLASS_EXTRACTED)
        if error:
            return jobs.release_for_retry(job, reason=error)

    workspace = store.get(job["workspace_id"])
    units = _page_units_for(workspace, job["source_id"])
    evidence_refs, positioned_pages = [], 0

    for index, page in enumerate(pages):
        if index >= len(units):
            # Fewer units than pages read. Reported rather than silently
            # dropped: binding a page to a unit that is not its own is the one
            # failure this tranche exists to prevent.
            logger.warning("source %s: page %d has no structural unit - skipped",
                           job["source_id"], index)
            break
        unit_id = units[index]["id"]
        outcome = _write_positioned_with_retry(
            store, job, page, extractor_version, governance_log,
            structural_unit_id=unit_id)
        if outcome:
            positioned_pages += 1
            evidence_refs.extend(outcome.get("evidence_item_ids") or [])

        detection = _detect_legend_candidates(
            store, job, page, governance_log, structural_unit_id=unit_id)
        _slice_legend_candidates(
            store, job, detection, page, governance_log,
            structural_unit_id=unit_id)

    if governance_log is not None:
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="pdf_pages_perceived",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "page_count": read.get("page_count"),
                "pages_read": len(pages),
                "pages_positioned": positioned_pages,
                # Said out loud so a short result is never mistaken for a
                # complete one.
                "pages_skipped_over_bound": read.get("skipped_pages"),
                "max_pages": positioned_text.MAX_PDF_PAGES,
                "extractor_version": extractor_version,
                "processing_location": job.get("processing_location"),
                "egress": job.get("egress"),
            },
            correlation_id=job["source_id"])

    record = jobs.complete(
        job, state=perception_jobs.STATE_COMPLETED,
        extractor=engine, extractor_version=engine_version,
        evidence_refs=evidence_refs)
    # CLAUDE-SHEET-IDENTITY-WIRING-01: does this document declare which sheets
    # the project HAS? Downstream of the completed record on purpose.
    _register_sheet_index(store, job, governance_log, record)
    # CLAUDE-DETAIL-CALLOUT-01: and which sheets does it POINT AT?
    _register_detail_callouts(store, job, governance_log, record)
    # CLAUDE-DATUM-CORROBORATION-WIRING-01: and do its declared levels agree
    # with what the sheets already read say?
    _corroborate_datums(store, job, governance_log, record)
    return record


def _write_pdf_pages_with_retry(store, workspace_id, source_id, page_texts,
                                extractor_version, governance_log,
                                evidence_class):
    """Register one page unit per page, tolerating a concurrent customer.

    The multi-page sibling of `_write_evidence_with_retry`, which registers the
    single synthetic page an image gets. Same retry discipline, same reason.
    """
    last_error = None
    for attempt in range(CONCURRENT_WRITE_RETRIES):
        workspace = store.get(workspace_id)
        if workspace is None:
            return None, "workspace no longer exists"
        try:
            outcome = store.register_pdf_page_structure(
                workspace, source_id=source_id, pages=page_texts,
                extractor_version=extractor_version, actor="perception-worker",
                governance_log=governance_log,
                evidence_class_by_page={index: evidence_class
                                        for index in range(len(page_texts))})
            return outcome, None
        except Exception as exc:
            last_error = exc
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                raise
            time.sleep(0.2 * (attempt + 1))
    return None, "workspace kept changing: %s" % last_error


def run_one(app, jobs, worker_id: str) -> Optional[dict]:
    """Claim and process a single job. Returns the terminal record, or None."""
    from services import image_intake, perception_jobs
    from services.case_workspace import CaseWorkspaceStore
    from services.ingestion import get_governance_log

    job = jobs.claim_next(worker_id=worker_id)
    if job is None:
        return None

    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(app)
    logger.info("perception job %s claimed (source %s)",
                job["job_id"][:12], job.get("source_id"))

    raw = read_source_bytes(store, job["workspace_id"], job["source_id"])
    if raw is None:
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason="source bytes unavailable")

    name = job.get("source_name") or ""
    # CLAUDE-GO-PERCEPTION-PDF-OCR-01: PDFs have their own path now. The gate
    # is NARROWED, not opened - a .docx or .xlsx still terminates honestly
    # below, because neither has a perception path and pretending otherwise
    # would turn "we cannot look at this" into a silent empty result.
    if name.lower().endswith(".pdf"):
        return _run_pdf_job(app, jobs, store, job, raw, governance_log)

    if not image_intake.is_supported_image(name):
        # Honest, not a fault: there is no perception path for this file type
        # beyond the founding parse that already ran in the request.
        return jobs.complete(
            job, state=perception_jobs.STATE_NEEDS_ATTENTION,
            failure_reason="no perception path for this file type yet")

    # CLAUDE-GO-PERCEPTION-REGION-OCR-01: the positioned read, which is the
    # SAME reading with coordinates attached - one OCR pass produces both, so
    # this does not lengthen the job. If it fails for any reason the
    # unpositioned path still runs, because knowing WHERE text is must never
    # become a precondition for knowing THAT it is there.
    positioned = None
    try:
        recovered = image_intake.extract_image_positioned_text(raw, name)
        positioned = recovered
    except Exception as exc:
        logger.warning("positioned read failed on job %s (%s: %s) - falling "
                       "back to the unpositioned path",
                       job["job_id"][:12], type(exc).__name__, exc)
        try:
            recovered = image_intake.extract_image_text(raw, name)
        except Exception as exc2:
            logger.exception("perception job %s raised", job["job_id"][:12])
            return jobs.release_for_retry(
                job, reason="%s: %s" % (type(exc2).__name__, exc2))

    orientation = recovered.get("orientation") or {}
    if governance_log is not None:
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="image_orientation_observed",
            actor="perception-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "job_id": job["job_id"],
                "authority": orientation.get("authority"),
                "exif_orientation": orientation.get("exif_orientation"),
                "applied_rotation_degrees": orientation.get("applied_rotation_degrees"),
                "applied_mirror": orientation.get("applied_mirror"),
                "native_size": orientation.get("native_size"),
                "normalised_size": orientation.get("normalised_size"),
                "changed": orientation.get("changed"),
                "conflict": orientation.get("conflict"),
                "osd": orientation.get("osd"),
                "reason": orientation.get("reason"),
                "source_file_hash": job.get("source_sha256"),
                "processing_location": job.get("processing_location"),
                "egress": job.get("egress"),
            },
        )

    text = (recovered.get("text") or "").strip()
    extractor_version = "%s %s" % (recovered.get("engine"),
                                   recovered.get("engine_version"))

    if not text:
        # Ran, established nothing. A fact about the picture, not a fault.
        return jobs.complete(
            job, state=perception_jobs.STATE_NEEDS_ATTENTION,
            extractor=recovered.get("engine"),
            extractor_version=recovered.get("engine_version"),
            failure_reason=recovered.get("reason"))

    # EXACTLY-ONCE by re-check rather than by hope: a replay of a job whose
    # evidence already landed must not attach it twice.
    workspace = store.get(job["workspace_id"])
    already = [e for e in (getattr(workspace, "evidence_items", None) or [])
               if e.get("source_id") == job["source_id"]
               and e.get("content_type") == "text"]
    if already:
        # The text landed on an earlier run. Coordinates may not have - every
        # source examined before this tranche has text and no geometry - so
        # the positioned write still runs here. It is idempotent by its own
        # re-check, so a genuine replay adds nothing twice.
        replay_positioned = _write_positioned_with_retry(
            store, job, positioned, extractor_version, governance_log)
        record = jobs.complete(
            job, state=perception_jobs.STATE_COMPLETED,
            extractor=recovered.get("engine"),
            extractor_version=recovered.get("engine_version"),
            evidence_refs=([e["id"] for e in already]
                           + list((replay_positioned or {}).get("evidence_item_ids") or [])))
        # A genuine replay reaches here, which is exactly where idempotency has
        # to hold: this re-runs registration and must create nothing.
        _register_sheet_index(store, job, governance_log, record)
        _register_detail_callouts(store, job, governance_log, record)
        _corroborate_datums(store, job, governance_log, record)
        return record

    outcome, error = _write_evidence_with_retry(
        store, job["workspace_id"], job["source_id"], text,
        extractor_version, governance_log, "perception-worker")
    if error:
        return jobs.release_for_retry(job, reason=error)

    positioned_outcome = _write_positioned_with_retry(
        store, job, positioned, extractor_version, governance_log)

    # CLAUDE-GO-PERCEPTION-LEGEND-DETECT-01: where does this sheet explain its
    # own symbols? Detection only - nothing here registers a meaning.
    detection = _detect_legend_candidates(store, job, positioned, governance_log)

    # CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01: and what are the ENTRIES in that
    # block? Proposal only - still nothing registered, still no human decision.
    _slice_legend_candidates(store, job, detection, positioned, governance_log)

    record = jobs.complete(
        job, state=perception_jobs.STATE_COMPLETED,
        extractor=recovered.get("engine"),
        extractor_version=recovered.get("engine_version"),
        evidence_refs=(list((outcome or {}).get("evidence_item_ids") or [])
                       + list((positioned_outcome or {}).get("evidence_item_ids") or [])))
    # A scanned index sheet is a single page, and the image path registers one
    # synthetic page unit for it - so the same page boundary applies here.
    _register_sheet_index(store, job, governance_log, record)
    _register_detail_callouts(store, job, governance_log, record)
    _corroborate_datums(store, job, governance_log, record)
    return record


def serve(app=None, *, poll_seconds: float = POLL_SECONDS, once: bool = False):
    """The loop. Restart-safe by construction: all state is on disk."""
    from services import perception_jobs

    if app is None:
        from app import create_app
        app = create_app()

    worker_id = perception_jobs.new_worker_id()
    jobs = perception_jobs.PerceptionJobStore(app.config["REGISTRY_STORE_PATH"])
    logger.info("perception worker %s starting", worker_id)

    stopping = {"now": False}

    def _stop(_signum, _frame):
        # Finish the job in hand rather than abandoning it mid-write; the
        # lease would recover it anyway, but a clean exit avoids the retry.
        logger.info("perception worker %s stopping after this job", worker_id)
        stopping["now"] = True

    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is not None:
            try:
                signal.signal(sig, _stop)
            except (ValueError, OSError):
                pass  # not the main thread, e.g. under test

    while True:
        try:
            with app.app_context():
                done = run_one(app, jobs, worker_id)
        except Exception:
            logger.exception("perception worker loop error")
            done = None
        if once:
            return done
        if stopping["now"]:
            return done
        if done is None:
            time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    serve()
