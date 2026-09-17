"""CLAUDE-SURVEY-REFERENCE-01 - visual examination as its own bounded queue.

    ENQUEUE AT INTAKE -> WAIT FOR OCR -> LOOK -> STORE -> DERIVE

WHY THIS IS A SEPARATE QUEUE AND NOT THREE LINES IN THE PERCEPTION WORKER

Because `services/perception_worker.py` is byte-pinned. Its sha256 is recorded
in `docs/records/datum-lifecycle-transition-01.json` as part of a LIVE
verification of `op.datum-corroboration`, and `services/operational_frontier.py`
re-hashes the file on every projection: a mismatch becomes a conflict, the
conflict becomes a `ui_blocker`, and the Operational Flight Deck returns 503.

A first version of this work DID edit that worker, and the guard fired exactly
as designed - the gate went red on four flight-deck tests. The honest options
were to re-perform the live verification or to leave the file alone. Re-pinning
the digest would have re-asserted a verification nobody repeated. Product Owner
ruling, 2026-09-15: leave it alone and follow the precedent.

That precedent is `services/founding_classification.py` + `services/
founding_worker.py`, which reached this same conflict and resolved it the same
way. This module is deliberately its sibling in shape: same store class, same
identity model, same lease and retry semantics, its own queue directory, its
own loop. Nothing here is a second job system.

    A CAPABILITY THAT CANNOT BE WIRED WITHOUT BREAKING A VERIFIED INVARIANT
    GETS ITS OWN WIRE, NOT A WEAKER INVARIANT.

ORDERING WITHOUT COUPLING

Visual examination reads better when the source's OCR text is available to
carry as context - a title block the model can see but not resolve is often
perfectly legible to the engine, and vice versa. The two queues are
independent, so nothing guarantees that order by construction.

It is expressed as a READINESS PREDICATE rather than a retry:
`perception_is_settled` refuses to claim a visual job whose source still has an
open perception job, so the job stays QUEUED and is offered again next poll.
`release_for_retry` would have spent the `MAX_ATTEMPTS` budget - which exists so
a job that kills its worker reaches FAILED rather than looping - on scheduling.

AND IT IS A PREFERENCE, NOT A PRECONDITION. A source whose perception FAILED,
or which never had a perception job at all, is examined anyway with no OCR text:
`visual_examination.build_user_prompt` handles that case explicitly, and the
whole point of this tranche is that absence of text is not absence of evidence.

PROVENANCE OF READ-BACK EVIDENCE

Product Owner, explicitly: "Preserve provenance when visual examination reads
OCR/evidence back from the registry rather than receiving it in-process."

In-process, the OCR text arrived as a local variable from the same run. Here it
is read back out of `evidence_items`, which is a different provenance claim and
is recorded as one: `ocr_context` on the stored record names the evidence item
ids it was assembled from, the extractor that produced them, and states that it
was read back from the registry rather than produced in this run. A reader can
therefore tell which text the model actually saw, and where it came from.
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from pathlib import Path
from typing import Optional

from services import perception_jobs

logger = logging.getLogger(__name__)

#: The kind of work, and therefore the job identity namespace. Bumping this is
#: how a re-examination becomes an explicit new run rather than a silent
#: overwrite - the same contract `perception_jobs.PROCESSING_VERSION` carries.
# CLAUDE-SURVEY-REFERENCE-REPAIR-01: THE PROMPT GENERATION IS PART OF THE
# JOB'S IDENTITY, because a job id that ignores it can never be re-run.
#
# A visual job id is sha256(workspace + source + source_sha256 +
# processing_version). This constant was the processing_version and it stayed
# at @1 while the prompt went visual-examination-01 -> -02 and learned to
# return a boundary graph. Same inputs, same digest, job already `completed` -
# so the parametric reconstruction shipped, deployed, passed its suite, and
# COULD NOT REACH A SINGLE EXISTING SOURCE. The live Castille record was still
# being served a V1 reading with no graph in it, which is what put an empty
# panel on the Product Owner's screen.
#
# Tying the two together means the next prompt generation gets a new identity
# by construction rather than by someone remembering to bump this line.
VISUAL_VERSION = "visual-examination@4"

#: ITS OWN QUEUE DIRECTORY, which is what keeps the deployed perception worker
#: from ever seeing this work. That worker claims the oldest claimable job in
#: ITS directory, and before `versions=` existed it did so with no filter at
#: all - so a visual job sitting there would have been claimed and run through
#: OCR, producing a confident empty result over a survey.
VISUAL_JOBS_SUBDIR = "visual_jobs"

#: Every processing version whose completed job still counts as a finished
#: examination. The CURRENT one is what new work is enqueued under; the older
#: ones are here so that bumping the generation does not re-open 54 settled
#: live records as "waiting to be examined" - their readings are real, they are
#: simply from an earlier prompt. Re-examination is a deliberate act, not a
#: side effect of a deploy.
VISUAL_VERSION_HISTORY = ("visual-examination@1", "visual-examination@2",
                          "visual-examination@3")
VISUAL_VERSIONS = frozenset({VISUAL_VERSION, *VISUAL_VERSION_HISTORY})

#: Why a visual job did not produce a reading. Named, because "processing
#: failed" tells nobody whether to retry, replace the file, or wait.
REASON_SOURCE_MISSING = "the Source record for this job no longer exists"
REASON_BYTES_MISSING = "the stored file for this Source could not be read"
REASON_ALREADY_EXAMINED = "this Source already carries a visual reading"
REASON_NOT_VISUAL = "this file has no visual representation to examine"


def visual_store(registry_store_path) -> "perception_jobs.PerceptionJobStore":
    """The visual queue. Same store class, same identity model, own directory."""
    return perception_jobs.PerceptionJobStore(registry_store_path,
                                              subdir=VISUAL_JOBS_SUBDIR)


def enqueue_for_source(jobs, *, workspace_id: str, source_id: str,
                       source_sha256: str, source_name: str = "",
                       intake_order: Optional[int] = None) -> dict:
    """Queue visual examination for an already-stored Source.

    Reuses `PerceptionJobStore.enqueue` verbatim under this module's own
    processing version, so identity and deduplication are the ones already
    proven in production. A duplicate enqueue, a worker restart, a redeploy and
    a retry therefore cannot produce two runs of the same looking.
    """
    return jobs.enqueue(
        workspace_id=workspace_id, source_id=source_id,
        source_sha256=source_sha256, source_name=source_name,
        intake_order=intake_order, processing_version=VISUAL_VERSION)


def is_visual_job(job) -> bool:
    return (job or {}).get("processing_version") == VISUAL_VERSION


def perception_is_settled(perception_jobs_store, job) -> bool:
    """Has this source's OCR finished, one way or the other?

    True also when there is NO perception job - a source that will never be
    OCR'd must not wait forever for text that is not coming. Only an OPEN job
    defers, and only so its text can travel as context.
    """
    record = perception_jobs_store.latest_for_source(job.get("workspace_id"),
                                                     job.get("source_id"))
    if record is None:
        return True
    return record.get("state") not in (perception_jobs.STATE_QUEUED,
                                       perception_jobs.STATE_RUNNING)


def _source_of(workspace, source_id: str) -> Optional[dict]:
    for source in getattr(workspace, "sources", None) or []:
        if source.get("id") == source_id and not source.get("removed_at"):
            return source
    return None


def recovered_ocr_context(workspace, source_id: str) -> dict:
    """The OCR text this source already carries, WITH its provenance.

    Reuses `document_examination._recovered`'s own scoping rather than a second
    query, so the text the model is given cannot include evidence the result
    page itself would not show.

    Returns the text plus the evidence item ids it came from, so the stored
    reading can say exactly which recorded text the model saw. That is the
    difference this module has to carry: in-process the text was a local
    variable from the same run; here it is a claim about stored records.
    """
    from services.case_workspace import (
        EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_EXTRACTED,
    )
    from services import document_examination as dx

    units = dx._page_units(workspace, source_id)
    regions = dx._regions_for(workspace, {u["id"] for u in units})
    items = [
        e for e in (getattr(workspace, "evidence_items", None) or [])
        if e.get("source_id") == source_id
        and e.get("content_type") == "text"
        and (e.get("content") or "").strip()
        and e.get("region_id") in regions
    ]

    def _address(item):
        addr = (regions[item["region_id"]].get("address") or {})
        return (addr.get("page_index") or 0, addr.get("paragraph_index") or 0)

    items.sort(key=_address)
    classes = {e.get("evidence_class") for e in items if e.get("evidence_class")}
    return {
        "text": "\n\n".join(e["content"] for e in items),
        "evidence_item_ids": [e["id"] for e in items],
        "extractor_versions": sorted({e.get("extractor_version") for e in items
                                      if e.get("extractor_version")}),
        # Said explicitly rather than inferred from the absence of anything
        # else: this text was NOT produced by the run that is about to use it.
        "read_back_from_registry": True,
        "was_recovered_by_ocr": EVIDENCE_CLASS_EXTRACTED in classes,
        "is_direct_source": EVIDENCE_CLASS_DIRECT_SOURCE in classes,
    }


def generation_of(version) -> str:
    """The trailing generation of a version string, or "".

    CLAUDE-SURVEY-REFERENCE-REPAIR-02. "visual-examination-02" -> "02",
    "visual-examination@2" -> "2". Both spellings exist because one names a
    PROMPT and the other a PROCESSING VERSION, and they have to be comparable:
    the whole defect being repaired here is those two drifting apart.
    """
    # THE FIRST TOKEN ONLY. A stored visual reading records its extractor as
    # "visual-examination-02 claude-sonnet-4-6" - the prompt version AND the
    # model that ran it. Reading the trailing digits of the whole string finds
    # the model's version, not the prompt's, and the exactly-once guard then
    # matches nothing and lets a replay through. That is a re-transmission of
    # the customer's survey, so it is the failure worth being careful about,
    # and a test pins it.
    text = str(version or "").strip().split()
    head = text[0] if text else ""
    for separator in ("@", "-"):
        if separator in head:
            tail = head.rsplit(separator, 1)[-1]
            if tail.isdigit():
                return str(int(tail))
    return ""


def _existing_evidence_of_type(workspace, source_id, content_type, *,
                               generation=None):
    """Evidence of one kind against a Source, optionally of ONE GENERATION.

    CLAUDE-SURVEY-REFERENCE-REPAIR-02: the generation filter is the difference
    between refusing a REPLAY and refusing an UPGRADE. Unfiltered, this
    function answered "has this source ever been looked at?", and the
    exactly-once guard above it therefore refused a second-generation
    examination as though it were a duplicate of the first. It is not: the
    prompt changed, and what it can return changed with it.
    """
    items = [e for e in (getattr(workspace, "evidence_items", None) or [])
             if e.get("source_id") == source_id
             and e.get("content_type") == content_type]
    if generation is None:
        return items
    return [e for e in items
            if generation_of(e.get("extractor_version")) == generation]


def resolve_external_ai_decision(app, workspace):
    """The external-AI gate for THIS workspace, resolved at the point of use.

    The same four lookups `routes/workspace.py`'s `_evaluate_security_action`
    performs, duplicated for the reason that function itself gives for
    duplicating them off `services/ingestion.py`: the boilerplate is four lines
    and a shared helper would have to thread a Flask app context through a
    worker that deliberately has none.

    RESOLVED HERE, never inherited. A project that forbids external AI must not
    have its survey transmitted because the job happened to be claimed by a
    loop that did not ask.
    """
    from services.security_governance import SecurityGovernanceStore
    from services.security_policy import (
        ACTION_EXTERNAL_AI_REQUEST, evaluate_action, profile_decision_for,
    )

    security_store = SecurityGovernanceStore(app.config["REGISTRY_STORE_PATH"])
    record = security_store.get()
    baseline = security_store.active_baseline(record)
    classification = getattr(workspace, "security_profile", None)
    return evaluate_action(
        ACTION_EXTERNAL_AI_REQUEST,
        classification=classification,
        baseline_decision=(
            baseline["control_decisions"].get(ACTION_EXTERNAL_AI_REQUEST, {}).get("decision")
            if baseline else None),
        baseline_version_id=baseline["id"] if baseline else None,
        profile_decision=profile_decision_for(classification, ACTION_EXTERNAL_AI_REQUEST),
        active_exception=security_store.active_exception_for(
            record, ACTION_EXTERNAL_AI_REQUEST, project_id=workspace.project_id),
    )


def _frame_for(raw: bytes, name: str) -> tuple:
    """(bytes, filename, page_number, spatial_digest_source) for one source.

    An image is its own frame. A PDF is rasterised page 1, and its LOCAL vector
    geometry is read alongside - see `_local_spatial_digest`.
    """
    from services import source_identity

    identity = source_identity.identify(raw[:source_identity.HEAD_BYTES], name)
    if identity["family"] == source_identity.FAMILY_PDF:
        raster = _pdf_page_raster(raw, 1)
        if raster is None:
            return None, None, 1, False
        return raster, "%s-page1.png" % Path(name or "source").stem, 1, True
    if source_identity.is_raster_image(identity):
        # The extension the image reader needs, which is not necessarily the
        # one on the job: everything downstream keys off the suffix, so a name
        # that lost its own is given the one its bytes establish.
        from services import image_intake

        if not image_intake.is_supported_image(name) and identity["media_type"]:
            name = "%s%s" % (Path(name or "source").stem or "source",
                             ".png" if identity["media_type"] == "image/png" else ".jpg")
        return raw, name, 1, False
    return None, None, 1, False


def _pdf_page_raster(raw: bytes, page_number: int = 1) -> Optional[bytes]:
    """One PDF page as PNG bytes, bounded. Returns None rather than raising.

    The bounds are `sheet_vision`'s own - imported rather than restated,
    because a second set of rasterization limits that drifted from the first
    would be a decompression-bomb surface nobody was watching. The PIXEL bound
    is checked BEFORE rasterizing, from declared geometry, for the reason
    `render_sheet_page` gives: checking output size afterwards is no defence,
    because by then the buffer has been allocated.
    """
    import pymupdf

    from services import sheet_vision

    dpi = sheet_vision.DEFAULT_RENDER_DPI
    try:
        with pymupdf.open(stream=raw, filetype="pdf") as document:
            if page_number > len(document):
                return None
            page = document[page_number - 1]
            rect = page.rect
            if (rect.width > sheet_vision.MAX_PAGE_DIMENSION_POINTS
                    or rect.height > sheet_vision.MAX_PAGE_DIMENSION_POINTS):
                logger.warning("refusing an absurd page geometry: %.0f x %.0f pt",
                               rect.width, rect.height)
                return None
            projected = (rect.width / 72.0 * dpi) * (rect.height / 72.0 * dpi)
            if projected > sheet_vision.MAX_RENDER_PIXELS:
                logger.warning("refusing a %.0fMP page render", projected / 1_000_000)
                return None
            return page.get_pixmap(dpi=dpi).tobytes("png")
    except Exception as exc:  # noqa: BLE001 - an unreadable page is a result
        logger.warning("could not rasterise page %d (%s: %s)",
                       page_number, type(exc).__name__, exc)
        return None


def _local_spatial_digest(source: dict) -> str:
    """`sheet_vision`'s LOCAL, no-network spatial read of a PDF's first page.

    CLAUDE-SURVEY-REFERENCE-01, and the reason this exists at all:
    `services/sheet_vision.py` was built, hardened and live-verified, and then
    called by NOTHING. Its property 1 is "spatial-first" - PyMuPDF vector paths
    and positioned text spans, extracted locally, transmitting nothing - which
    is exactly the evidence a vector survey PDF has and a raster does not.

        A CAPABILITY THAT EXISTS BUT IS UNREACHABLE IS AN INTEGRATION GAP
        BEFORE IT IS AN ARCHITECTURE GAP.

    `build_egress_digest` is reused verbatim, and that matters for more than
    tidiness: it is the ALLOWLIST that keeps the filename, the document hash,
    font names and every identifier off the wire. Rebuilding a digest here
    would have rebuilt that decision too, badly.

    Returns "" for anything it cannot read locally - a scan has no spans and no
    vectors, which is a fact about the document, not a failure.
    """
    from services import sheet_vision

    path = (source or {}).get("file_path")
    if not path:
        return ""
    try:
        geometry = sheet_vision.extract_sheet_geometry(path, page_number=1)
    except Exception as exc:  # noqa: BLE001 - an unreadable sheet is a result
        logger.info("no local sheet geometry for %s (%s: %s)",
                    (source or {}).get("id"), type(exc).__name__, exc)
        return ""
    if not geometry.text_span_count and not geometry.vector_count:
        return ""
    return sheet_vision.build_egress_digest(geometry)


def examine_source(app, jobs, job: dict, *, store=None, governance_log=None) -> dict:
    """Run visual examination for one job. NEVER RAISES.

    Returns the job record as `complete()` left it, so the worker loop treats
    this exactly like any other job outcome.
    """
    from services import survey_reference, visual_examination as vx
    from services.case_workspace import CaseWorkspaceStore
    from services.ingestion import get_governance_log

    store = store or CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    if governance_log is None:
        governance_log = get_governance_log(app)

    workspace = store.get(job.get("workspace_id"))
    source = _source_of(workspace, job.get("source_id")) if workspace else None
    if source is None:
        # Not retryable: a removed Source will not come back.
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason=REASON_SOURCE_MISSING)

    # EXACTLY-ONCE by re-check, the same discipline every other write stage
    # uses. A replayed job must not transmit the customer's survey again, and
    # must not mint a second Survey Reference.
    #
    # CLAUDE-SURVEY-REFERENCE-REPAIR-02: PER GENERATION, not per Source.
    #
    # This guard is real and stays: without it a replayed job re-sends the
    # customer's survey to an external service, which is the one thing this
    # module must never do twice for the same work. But it asked "has this
    # Source ever been looked at?", and so it refused an UPGRADED PROMPT as if
    # it were a duplicate of the reading that prompt was written to replace.
    #
    # That is the second half of the defect the Product Owner found. The job
    # identity was fixed first, so a new generation reached the worker at all -
    # and then this line turned it away with `egress = none` and "this Source
    # already carries a visual reading". A capability cannot reach a record
    # through two gates when only one of them was opened.
    #
    # Same generation is still a replay and is still refused.
    if _existing_evidence_of_type(workspace, job["source_id"], vx.VISUAL_CONTENT_TYPE,
                                  generation=generation_of(vx.VISUAL_PROMPT_VERSION)):
        return jobs.complete(job, state=perception_jobs.STATE_COMPLETED,
                             extractor="visual-examination",
                             failure_reason=REASON_ALREADY_EXAMINED)

    raw = _read_source_bytes(store, workspace, source)
    if raw is None:
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason=REASON_BYTES_MISSING)

    from services import drawing_segmentation
    try:
        drawing_segmentation.examine_title_blocks(
            store, workspace, source["id"], raw, governance_log=governance_log)
        workspace = store.get(job["workspace_id"]) or workspace
    except Exception as exc:
        logger.warning("title-block examination failed for %s: %s", source["id"], exc)

    frame, frame_name, page_number, is_pdf = _frame_for(
        raw, job.get("source_name") or source.get("name") or "")
    if frame is None:
        return jobs.complete(job, state=perception_jobs.STATE_NEEDS_ATTENTION,
                             failure_reason=REASON_NOT_VISUAL)

    ocr = recovered_ocr_context(workspace, job["source_id"])
    decision = resolve_external_ai_decision(app, workspace)
    visual = vx.examine(
        frame, frame_name,
        decision=decision,
        api_key=app.config.get("ANTHROPIC_API_KEY"),
        model=app.config.get("ANTHROPIC_MODEL"),
        ocr_text=ocr["text"],
        context=source.get("name") or "",
        source_sha256=job.get("source_sha256"),
        spatial_digest=_local_spatial_digest(source) if is_pdf else "")

    if governance_log is not None:
        # Recorded on EVERY outcome, refusals included. "We declined to look at
        # this" is exactly as much a fact worth holding as "we looked".
        governance_log.append(
            project_id=job["workspace_id"], event_type=vx.VISUAL_EVENT_TYPE,
            actor="visual-worker", role="system",
            payload=dict(visual.audit.as_payload(),
                         source_id=job["source_id"], job_id=job["job_id"],
                         page_number=page_number,
                         ocr_evidence_item_ids=ocr["evidence_item_ids"],
                         ocr_read_back_from_registry=ocr["read_back_from_registry"]),
            correlation_id=job["source_id"])

    if not visual.ran:
        return jobs.complete(job, state=perception_jobs.STATE_NEEDS_ATTENTION,
                             extractor="visual-examination",
                             extractor_version=visual.prompt_version,
                             failure_reason=visual.skipped_reason)

    stored = _store_visual_record(store, job, visual, ocr, governance_log)
    if stored is None:
        return jobs.complete(job, state=perception_jobs.STATE_NEEDS_ATTENTION,
                             extractor="visual-examination",
                             extractor_version=visual.prompt_version,
                             failure_reason="the visual reading could not be stored")

    refs = [stored["id"]]
    if survey_reference.is_survey_like(visual):
        reference = _build_survey_reference(
            app, store, job, visual, governance_log,
            source=source, page_number=page_number)
        if reference and reference.get("evidence_item_id"):
            refs.append(reference["evidence_item_id"])

    if not visual.established_anything:
        # Ran, established nothing. A fact about the picture, not a fault - and
        # the reading is still stored, because "GO looked and could not make
        # anything out" is itself worth recording.
        return jobs.complete(job, state=perception_jobs.STATE_NEEDS_ATTENTION,
                             extractor="visual-examination",
                             extractor_version=visual.prompt_version,
                             evidence_refs=refs,
                             failure_reason="nothing legible was found in this image")

    # CLAUDE-MUSCLE-ACTIVATION-01: the five muscles get their production
    # caller here, at the end of an examination that has already succeeded.
    #
    # THIS IS THE DOOR, NOT A NEW SERVICE. Subject keys, supersessions and
    # manifest gaps are written through primitives that already existed -
    # register_evidence_item, record_evidence_relationship, record_supersession.
    # The natural home would be `perception_worker`, where sheet indexes are
    # already registered and `not_found` is already computed and discarded,
    # but that file's bytes are pinned by the flight-deck digest guard, so the
    # hook lives on this end of the same examination instead.
    #
    # It never raises: the reading is worth more than the enrichment, and a
    # malformed clause must not fail an examination that has already earned
    # its result.
    try:
        from services import package_muscles

        package_muscles.activate(
            store, store.get(job["workspace_id"]) or workspace,
            job["source_id"],
            extra_text=_observation_text(visual),
            governance_log=governance_log)
    except Exception as exc:  # noqa: BLE001
        logger.warning("package muscles did not activate for %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)

    return jobs.complete(job, state=perception_jobs.STATE_COMPLETED,
                         extractor="visual-examination",
                         extractor_version=visual.prompt_version,
                         evidence_refs=refs)


def _read_source_bytes(store, workspace, source) -> Optional[bytes]:
    """The stored bytes, confined under the registry root.

    The same tenant boundary `perception_worker.read_source_bytes` enforces,
    and for the same reason: a job record must never be able to name a file.
    The path is resolved from the STORE and refused if it escapes the root.
    """
    if not source.get("file_path"):
        return None
    path = Path(source["file_path"]).resolve()
    root = Path(store.store_path).resolve()
    if root not in path.parents:
        logger.warning("refusing source outside the registry root: %s", path)
        return None
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except OSError as exc:
        logger.warning("could not read source bytes (%s)", exc)
        return None


def _store_visual_record(store, job, visual, ocr, governance_log):
    """The visual reading, as ONE evidence item. Never raises.

    ONE ITEM, not one per observation. The reading is a single act with a
    single provenance - one model, one prompt version, one frame - and
    splitting it would make a partial write possible, where half a reading
    could be attributed to a whole one.

    EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, deliberately and not negotiably. A
    vision model's reading of a survey is a proposal about that survey; the
    Camel programme's own "no silent AI-to-authoritative promotion" rule is
    exactly what this class exists to carry.
    """
    import time as _time

    from services.case_workspace import (
        CaseWorkspaceError, EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
    )
    from services import visual_examination as vx

    record = visual.as_record()
    # THE PROVENANCE OF THE CONTEXT, carried on the reading itself.
    record["ocr_context"] = {
        "evidence_item_ids": ocr["evidence_item_ids"],
        "extractor_versions": ocr["extractor_versions"],
        "read_back_from_registry": ocr["read_back_from_registry"],
        "character_count": len(ocr["text"]),
        "was_recovered_by_ocr": ocr["was_recovered_by_ocr"],
    }

    for attempt in range(5):
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        try:
            return store.register_evidence_item(
                workspace, source_id=job["source_id"],
                evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
                content=json.dumps(record, sort_keys=True),
                content_type=vx.VISUAL_CONTENT_TYPE,
                extractor_version="%s %s" % (visual.prompt_version,
                                             visual.model or "unrecorded"),
                actor="visual-worker", governance_log=governance_log)
        except CaseWorkspaceError as exc:
            logger.warning("visual reading refused for %s: %s", job["source_id"], exc)
            return None
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                logger.warning("visual reading not stored for %s (%s: %s)",
                               job["source_id"], type(exc).__name__, exc)
                return None
            _time.sleep(0.2 * (attempt + 1))
    return None


def _decoded_reference(row):
    """One stored Survey Reference record, or None if it will not parse.

    A malformed row must not be able to stop a re-examination - the worst case
    is that its generation reads as unknown and a fresh reference is built,
    which is the safe direction.
    """
    import json

    try:
        decoded = json.loads(row.get("content") or "")
    except (TypeError, ValueError):
        return None
    return decoded if isinstance(decoded, dict) else None


def _observation_text(visual) -> str:
    """What the reading SAW, as text a subject extractor can read.

    A tag printed on a drawing reaches the evidence graph through the visual
    observations rather than through OCR, so without this a schedule row read
    by vision would never share a subject key with the specification clause
    that names the same unit - which is the entire point of F3.
    """
    parts = []
    for observation in (getattr(visual, "observations", None) or []):
        value = observation.get("value") if isinstance(observation, dict) else None
        if value:
            parts.append(str(value))
    return chr(10).join(parts)


def _build_survey_reference(app, store, job, visual, governance_log, *,
                            source=None, page_number=1):
    """Compose, store and register the Survey Reference. Never raises.

    THE DERIVED ARTIFACT IS A SOURCE, with `origin_type="derived_reference"`
    and `origin_reference` naming the survey it came from - the mechanism
    `image_intelligence.extract_bounded_crop` already established. That is what
    makes save and reopen not a feature: a stored Source is already durable,
    already downloadable through the existing governed route, and already
    carries its own hash.

    THE ORIGINAL IS NOT TOUCHED. Nothing here writes to the parent Source's
    bytes, name, hash or path.
    """
    import time as _time

    from werkzeug.utils import secure_filename

    from services import survey_reference
    from services.case_workspace import (
        EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, SOURCE_KIND_DRAWING,
        SOURCE_ORIGIN_TYPE_DERIVED_REFERENCE,
    )

    workspace = store.get(job["workspace_id"])
    if workspace is None:
        return None

    # CLAUDE-SURVEY-REFERENCE-REPAIR-02: one Survey Reference PER GENERATION.
    #
    # `REFERENCE_VERSION` does not move when the PROMPT does, so the generation
    # of a reference is the generation of the reading it was derived from -
    # which is recorded inside the reference itself. A second reference from
    # the same reading is a duplicate and is refused exactly as before; a
    # reference from a newer reading is the point of re-examining.
    current = generation_of(visual.prompt_version)
    superseded_id = None
    for row in _existing_evidence_of_type(workspace, job["source_id"],
                                          survey_reference.REFERENCE_CONTENT_TYPE):
        previous = _decoded_reference(row)
        if generation_of((previous or {}).get("prompt_version")) == current:
            return None
        if (previous or {}).get("derived_source_id"):
            superseded_id = previous["derived_source_id"]

    display_name = (source or {}).get("name") or ""
    # THE ORIGINAL FILENAME, never the display name. Provenance hangs off the
    # evidence's identity; the work-item name is a label and can change.
    original_filename = (Path((source or {}).get("file_path") or "").name
                         or job.get("source_name") or "")

    try:
        reference = survey_reference.derive(
            visual, project_id=job["workspace_id"], source_id=job["source_id"],
            source_filename=original_filename,
            source_sha256=job.get("source_sha256"),
            pages_used=[page_number], display_name=display_name,
            frame_size=visual.audit.frame_size)
        pdf_bytes = survey_reference.render_pdf(reference)
    except Exception as exc:  # noqa: BLE001 - a failed derivative is not a failed read
        logger.warning("survey reference could not be composed for %s (%s: %s)",
                       job["source_id"], type(exc).__name__, exc)
        return None

    artifact_name = survey_reference.artifact_filename(display_name)
    sources_dir = (Path(app.config["REGISTRY_STORE_PATH"]) / "workspace_sources"
                   / job["workspace_id"])
    try:
        sources_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = sources_dir / ("%s_%s" % (uuid.uuid4().hex,
                                                  secure_filename(artifact_name)))
        artifact_path.write_bytes(pdf_bytes)
    except OSError as exc:
        logger.warning("survey reference could not be stored for %s (%s)",
                       job["source_id"], exc)
        return None

    reference["artifact_filename"] = artifact_name
    reference["artifact_sha256"] = hashlib.sha256(pdf_bytes).hexdigest()
    reference["artifact_bytes"] = len(pdf_bytes)

    derived = None
    for attempt in range(5):
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        try:
            derived = store.add_source(
                workspace, name=artifact_name, file_path=str(artifact_path),
                kind=SOURCE_KIND_DRAWING, file_hash=reference["artifact_sha256"],
                origin_type=SOURCE_ORIGIN_TYPE_DERIVED_REFERENCE,
                origin_reference=job["source_id"],
                actor="visual-worker", governance_log=governance_log)
            break
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                logger.warning("survey reference source not added for %s (%s: %s)",
                               job["source_id"], type(exc).__name__, exc)
                return None
            _time.sleep(0.2 * (attempt + 1))
    if derived is None:
        return None

    # CLAUDE-SURVEY-REFERENCE-REPAIR-02: a rebuilt reference SUPERSEDES its
    # predecessor rather than sitting beside it. Two PDFs of the same parcel,
    # differing only by which prompt read it, is exactly the ambiguity a
    # governed record exists to prevent.
    #
    # Written as a revision LINK rather than through `add_source` because that
    # method has no such parameter - `revise_source` owns the replace-a-file
    # flow and this is not that: nothing about the original changed, a second
    # derivative was produced from a better reading of it. Failure to link is
    # logged and never fatal; an unlinked extra PDF is untidy, a lost Survey
    # Reference is not.
    if superseded_id:
        for attempt in range(5):
            try:
                current_ws = store.get(job["workspace_id"])
                rows = {s["id"]: s for s in (current_ws.sources or [])}
                old_row, new_row = rows.get(superseded_id), rows.get(derived["id"])
                if not old_row or not new_row:
                    break
                if old_row.get("superseded_by_source_id"):
                    break
                old_row["superseded_by_source_id"] = derived["id"]
                new_row["supersedes_source_id"] = superseded_id
                store.save(current_ws)
                break
            except Exception as exc:  # noqa: BLE001
                if type(exc).__name__ not in ("ConcurrentModificationError",
                                              "WriteCollisionError"):
                    logger.warning("survey reference revision not linked for %s (%s: %s)",
                                   job["source_id"], type(exc).__name__, exc)
                    break
                _time.sleep(0.2 * (attempt + 1))

    reference["derived_source_id"] = derived["id"]

    for attempt in range(5):
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
        try:
            evidence = store.register_evidence_item(
                workspace, source_id=job["source_id"],
                evidence_class=EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
                content=json.dumps(reference, sort_keys=True),
                content_type=survey_reference.REFERENCE_CONTENT_TYPE,
                extractor_version=survey_reference.REFERENCE_VERSION,
                actor="visual-worker", governance_log=governance_log)
            reference["evidence_item_id"] = evidence["id"]
            break
        except Exception as exc:  # noqa: BLE001
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                logger.warning("survey reference not registered for %s (%s: %s)",
                               job["source_id"], type(exc).__name__, exc)
                break
            _time.sleep(0.2 * (attempt + 1))

    if governance_log is not None:
        governance_log.append(
            project_id=job["workspace_id"],
            event_type="survey_reference_composed",
            actor="visual-worker", role="system",
            payload={
                "source_id": job["source_id"],
                "derived_source_id": reference.get("derived_source_id"),
                "artifact_sha256": reference["artifact_sha256"],
                "artifact_bytes": reference["artifact_bytes"],
                "source_sha256": reference.get("source_sha256"),
                "recovered_count": len(reference.get("recovered") or []),
                "partial_count": len(reference.get("partially_recovered") or []),
                "unresolved_count": len(reference.get("unresolved") or []),
                "reference_version": survey_reference.REFERENCE_VERSION,
                "prompt_version": reference.get("prompt_version"),
                "model": reference.get("model"),
            },
            correlation_id=job["source_id"])
    logger.info("survey reference composed for %s (%d recovered, %d unresolved)",
                job["source_id"], len(reference.get("recovered") or []),
                len(reference.get("unresolved") or []))
    return reference
