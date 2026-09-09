"""CLAUDE-DOCUMENT-SHOP-RESULT-01 - what the customer is actually handed.

A PRESENTATION layer over governed state that already exists. It runs no
analysis, calls no provider, writes nothing, and introduces no second
As-Read: `ingest_upload` already parses every accepted document and already
runs local OCR over an accepted image, and every fact below is read back from
what those two paths recorded. The defect this closes was never missing
processing - it was that the processing had no customer-facing surface, so a
person who uploaded a document was sent to the analyst bench instead and told
"As-Read has not started on this source".

    SIMPLE OUTSIDE. GOVERNED INSIDE.

Three things this deliberately does NOT do:

- **It does not invent a status transition.** Examination is synchronous
  inside the upload request, so by the time any record exists it has already
  finished. There is therefore no honest PENDING/PROCESSING state to show, and
  inventing one would be a status unsupported by any record. `state_of` returns
  only outcomes that a stored record can actually establish.
- **It does not fabricate an interpretation.** Where the pipeline established
  nothing, this says so by name rather than rendering an empty section that
  reads like a finished answer.
- **It does not translate governed vocabulary into the record.** As-Read,
  Spin, marks, vectorisation and sheet grammar stay exactly where they are;
  they are simply not what a Document Shop customer is shown.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

# What a person is told about their job, and the only three outcomes a stored
# record can support. Ordered worst-last so a listing can sort by concern.
STATE_RESULT_READY = "result_ready"
STATE_READ_NOT_INTERPRETED = "read_not_interpreted"
STATE_NEEDS_ATTENTION = "needs_attention"
STATE_COULD_NOT_COMPLETE = "could_not_complete"

# CLAUDE-GO-PERCEPTION-WORKER-01: two states that only became TRUE when the
# work actually moved off the request.
#
# This module previously refused to render "Processing", and that refusal was
# right: examination ran inside the upload request, so by the time any record
# existed it had finished, and a pending state would have been a status no
# record could support. Asynchronous perception creates the record that makes
# it true. The rule did not change - the facts did.
STATE_QUEUED = "queued"
STATE_PROCESSING = "processing"

STATE_LABELS = {
    STATE_QUEUED: "Waiting to be examined",
    STATE_PROCESSING: "Being examined",
    STATE_RESULT_READY: "Result ready",
    STATE_READ_NOT_INTERPRETED: "Read, not interpreted",
    STATE_NEEDS_ATTENTION: "Needs attention",
    STATE_COULD_NOT_COMPLETE: "Could not complete",
}

# Ordered worst-last: an aggregate takes the LEAST settled state among its
# sources, so an examination never looks finished while part of it is not.
_AGGREGATE_PRECEDENCE = (
    STATE_COULD_NOT_COMPLETE,
    STATE_QUEUED,
    STATE_PROCESSING,
    STATE_NEEDS_ATTENTION,
    STATE_READ_NOT_INTERPRETED,
    STATE_RESULT_READY,
)

# Plain-language equivalents. The key is the file's own extension, so nothing
# here claims to know what the document IS - only what kind of file arrived.
_MATERIAL_BY_EXT = {
    ".pdf": "a PDF document",
    ".docx": "a Word document",
    ".txt": "a plain text file",
    ".md": "a text document",
    ".csv": "a comma-separated data file",
    ".png": "an image (PNG)",
    ".jpg": "an image (JPEG)",
    ".jpeg": "an image (JPEG)",
}

_IMAGE_EXTS = {".png", ".jpg", ".jpeg"}


def _ext(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def _live_sources(workspace) -> list[dict]:
    return [s for s in (getattr(workspace, "sources", None) or [])
            if not s.get("removed_at")]


def _page_units(workspace, source_id: str) -> list[dict]:
    return [u for u in (getattr(workspace, "structural_units", None) or [])
            if u.get("source_id") == source_id and u.get("unit_type") == "page"]


def _regions_for(workspace, unit_ids: set) -> dict:
    """The addressing records for this source's pages, keyed by id.

    A region carries WHERE something is (`region_type`, `address` with
    page_index/paragraph_index) and nothing about what it says. That division
    is the storage model, and this reader follows it rather than asking a
    region for content it was never given.
    """
    return {r["id"]: r for r in (getattr(workspace, "addressable_regions", None) or [])
            if r.get("structural_unit_id") in unit_ids}


def _recovered(workspace, source_id: str) -> dict:
    """Text held against this Source, and HOW it got there.

    CLAUDE-DOCUMENT-SHOP-OCR-READER-01. This function previously read
    `content` / `content_type` / `evidence_class` off `addressable_regions`,
    where none of those fields exist. The storage model, confirmed against real
    production records rather than inferred from a function's parameter names:

        Source
          -> StructuralUnit   (unit_type="page", source_id)      WHICH PAGE
          -> AddressableRegion(structural_unit_id, address)       WHERE ON IT
          -> EvidenceItem     (source_id, region_id, content,     WHAT IT SAYS
                               content_type, evidence_class,
                               extractor_version)

    The consequence of reading the wrong record was not a blank section: a
    successfully OCR-read image was told "No text could be read from this
    image" while its text sat in evidence_items, and its state read Needs
    attention. A customer-facing contradiction of the system's own evidence.

    Scoped three ways, deliberately, because this text is customer material:
    only this workspace (we are handed one), only evidence whose own
    `source_id` matches, and only evidence anchored to a region belonging to a
    page unit OF that source. `source_id` alone would be enough today; the
    region join means a future record that carries a stale or absent source_id
    still cannot cross a source boundary.
    """
    from services.case_workspace import (
        EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_EXTRACTED,
    )

    units = _page_units(workspace, source_id)
    regions = _regions_for(workspace, {u["id"] for u in units})
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
    passages = [e["content"] for e in items]
    classes = {e.get("evidence_class") for e in items if e.get("evidence_class")}
    engines = {e.get("extractor_version") for e in items if e.get("extractor_version")}
    return {
        "page_count": len(units),
        "passage_count": len(passages),
        "character_count": sum(len(p) for p in passages),
        "preview": "\n\n".join(passages[:3])[:1200],
        # OCR-recovered text is a READING of an image; text a document carries
        # is the document speaking. The evidence class already records which,
        # so this reports it rather than guessing from the engine's name.
        "was_recovered": EVIDENCE_CLASS_EXTRACTED in classes,
        "is_direct_source": EVIDENCE_CLASS_DIRECT_SOURCE in classes,
        "read_by": sorted(e for e in engines if e),
    }


def _reached_an_interpretation(document) -> bool:
    """Did the examination conclude ANYTHING beyond "here are some characters"?

    Requirements, tables and a completed consistency check are the three things
    that produce a "What GO made of it" line. If none of them happened, nothing
    was interpreted - however many characters came back.
    """
    return bool(getattr(document, "requirements", None)
                or getattr(document, "tables", None)
                or getattr(document, "consistency_checked", False))


def _job_state_for(jobs, workspace_id, source_id):
    """What the PERSISTED job says about this source, or None if there is none.

    Historical containers pre-date the job store entirely; for them there is no
    job and the answer must come from the evidence, exactly as before. A
    missing job is not a pending job.
    """
    if jobs is None:
        return None
    try:
        record = jobs.latest_for_source(workspace_id, source_id)
    except Exception:
        return None
    if record is None:
        return None
    return record.get("state")


def source_state(document, workspace, source_id, *, jobs=None) -> str:
    """One Source's honest state.

    Job facts outrank evidence facts while a job is open: a source that has not
    been looked at yet must never render as "Read, not interpreted", which
    would be a statement about a reading that has not happened.
    """
    from services import perception_jobs as pj

    job_state = _job_state_for(jobs, getattr(workspace, "project_id", ""), source_id)
    if job_state == pj.STATE_QUEUED:
        return STATE_QUEUED
    if job_state == pj.STATE_RUNNING:
        return STATE_PROCESSING
    if job_state == pj.STATE_FAILED:
        return STATE_NEEDS_ATTENTION

    recovered = _recovered(workspace, source_id)
    if recovered["passage_count"]:
        return (STATE_RESULT_READY if _reached_an_interpretation(document)
                else STATE_READ_NOT_INTERPRETED)
    if _reached_an_interpretation(document):
        return STATE_RESULT_READY
    return STATE_NEEDS_ATTENTION


def state_of(document, workspace, *, jobs=None) -> str:
    """The job's outcome, derived only from what is actually recorded.

    CLAUDE-DOCUMENT-SHOP-FLOW-01. This used to return "Result ready" the moment
    ANY passage existed. A Product Owner phone photo of a drawing then produced
    a page reading "Result ready - 14,306 characters recovered" beside "No
    interpretation was reached", with pages of OCR noise under a heading that
    said "Some of what was read". Confident gibberish, which is the one thing
    this surface exists not to be.

    The fix is NOT a text-quality score. Measured against real production
    evidence, a word-like-token ratio does not separate noise from signal:
    the pure-noise photo scored 0.434 while a legitimate low-yield scan scored
    0.195 and a clean control 0.636. A threshold there would be invented
    certainty dressed as a measurement.

    So the state is derived from what the records already establish: text came
    back, and nothing was concluded from it.

    IT IS DELIBERATELY NOT CALLED "LIMITED RECOVERY". That was the first
    attempt, and a live proof caught it overclaiming in the opposite direction:
    a clean photograph whose text OCR read perfectly - "FIRE DAMPER SCHEDULE /
    ROOM 101 DETECTOR FD-1" - was labelled Limited recovery and captioned "could
    not be made sense of", which is false. An IMAGE never reaches an
    interpretation at all, because the parser finds no native text in one, so
    that state applies to every image equally and cannot mean the recovery went
    badly.

    "Read, not interpreted" is what actually happened, and it is true of the
    clean photograph and the dense drawing alike. Which of the two a person is
    holding is visible in the recovered text itself, which is shown to them -
    and judging that for them would need the quality score this refuses to
    invent.
    """
    sources = _live_sources(workspace)
    if document is None or not sources:
        return STATE_COULD_NOT_COMPLETE

    # CLAUDE-GO-PERCEPTION-MULTISOURCE-01: an examination holds ONE OR MORE
    # sources, and its state is the LEAST settled among them. Five photographs
    # with two done and three waiting is not "ready" - and one that failed must
    # not erase the four that succeeded, which is why failure is not simply
    # propagated upward either.
    states = [source_state(document, workspace, s["id"], jobs=jobs)
              for s in sources]
    for candidate in _AGGREGATE_PRECEDENCE:
        if candidate in states:
            return candidate
    return STATE_NEEDS_ATTENTION


def build_result(document, workspace, *, display_name: str, jobs=None) -> dict[str, Any]:
    """Everything the Document Examination Result page renders.

    Returns plain data, so the template makes no decisions and nothing here
    depends on Flask. The three-way split the record keeps - established from
    the source, GO's reading of it, and what was not established - is built
    here rather than in markup, because it is a claim about evidence.
    """
    sources = _live_sources(workspace)
    source = sources[0] if sources else None
    filename = (source or {}).get("name") or getattr(document, "filename", "") or ""
    ext = _ext(filename)
    recovered = _recovered(workspace, source["id"]) if source else {
        "page_count": 0, "passage_count": 0, "character_count": 0,
        "preview": "", "was_recovered": False, "is_direct_source": False,
        "read_by": [],
    }

    established: list[dict[str, str]] = []
    interpretation: list[dict[str, str]] = []
    not_established: list[dict[str, str]] = []

    established.append({
        "label": "File received",
        "value": "%s, received %s" % (filename, (getattr(document, "ingested_at", "") or "")[:10]),
    })
    established.append({
        "label": "Kind of file",
        "value": _MATERIAL_BY_EXT.get(ext, "a file of type %s" % (ext or "unknown")),
    })
    if getattr(document, "original_file_hash", None):
        established.append({
            "label": "Stored unchanged",
            "value": "The original you uploaded is kept exactly as it arrived "
                     "(checksum %s…)." % document.original_file_hash[:12],
        })

    if recovered["passage_count"]:
        # How the text arrived is part of the claim, not decoration: one is the
        # document speaking, the other is a machine reading a picture of it.
        if recovered["was_recovered"]:
            how = (" — read from the image by %s" % ", ".join(recovered["read_by"]))                 if recovered["read_by"] else " — read from the image"
        else:
            how = " — carried by the document itself"
        established.append({
            "label": "Text recovered" if recovered["was_recovered"] else "Text read",
            "value": "%d passage%s across %d page%s (%d characters)%s." % (
                recovered["passage_count"], "" if recovered["passage_count"] == 1 else "s",
                max(recovered["page_count"], 1), "" if recovered["page_count"] == 1 else "s",
                recovered["character_count"], how,
            ),
        })
        if not _reached_an_interpretation(document):
            # Said HERE, beside the character count, because the count on its
            # own reads as success. 14,306 characters of nothing is still
            # nothing, and the customer should not have to infer that.
            not_established.append({
                "label": "Nothing has been concluded from the recovered text",
                "value": (
                    "The text below was read off your file and is shown exactly "
                    "as the engine produced it. Nothing has been worked out from "
                    "it. Photographing a drawing often returns marks and "
                    "fragments as well as words - linework and symbols get read "
                    "as stray characters - so it is shown for you to judge "
                    "rather than summarised for you."
                    if recovered["was_recovered"] else
                    "Text came back, but nothing has been concluded from it."
                ),
            })

    requirements = list(getattr(document, "requirements", None) or [])
    tables = list(getattr(document, "tables", None) or [])
    if requirements:
        interpretation.append({
            "label": "Statements identified",
            "value": "GO picked out %d passage%s that read as obligations or "
                     "requirements. These are GO's reading of the text, not a "
                     "quotation of it." % (len(requirements),
                                           "" if len(requirements) == 1 else "s"),
        })
    if tables:
        interpretation.append({
            "label": "Tables found",
            "value": "%d table%s recognised in the layout." % (
                len(tables), "" if len(tables) == 1 else "s"),
        })

    flags = list(getattr(document, "consistency_flags", None) or [])
    if getattr(document, "consistency_checked", False):
        interpretation.append({
            "label": "Internal consistency",
            "value": ("%d point%s worth a second look." % (
                len(flags), "" if len(flags) == 1 else "s")) if flags
            else "Nothing inconsistent stood out.",
        })
    else:
        not_established.append({
            "label": "Internal consistency was not checked",
            "value": getattr(document, "consistency_note", None)
            or "This document was not compared against itself for contradictions.",
        })

    if ext in _IMAGE_EXTS and not recovered["passage_count"]:
        not_established.append({
            "label": "No text could be read from this image",
            "value": "An image carries no text of its own, and the text-recognition "
                     "step did not recover any. The picture itself is kept and can "
                     "be viewed below.",
        })
    elif getattr(document, "text_extraction_status", "") == "no_native_text":
        not_established.append({
            "label": "This file has no text layer",
            "value": "It appears to be a scan or picture rather than a document with "
                     "selectable text, so there was nothing to read directly.",
        })
    elif not recovered["passage_count"] and not requirements:
        not_established.append({
            "label": "Nothing was recovered from this file",
            "value": "The file was received and stored, but no readable content came "
                     "out of it.",
        })

    if not interpretation and not recovered["passage_count"]:
        # Only when there is genuinely nothing. Where text DID come back, the
        # sharper line above already says so and this one would repeat it in
        # vaguer words.
        not_established.append({
            "label": "No interpretation was reached",
            "value": "There was not enough recovered content for GO to say what this "
                     "document requires or describes.",
        })

    state = state_of(document, workspace, jobs=jobs)
    # CLAUDE-DOCUMENT-SHOP-FLOW-01: a photograph of a drawing yields marks and
    # fragments, not sentences. When nothing was concluded from them, the page
    # must present them AS fragments - the old heading "Some of what was read"
    # framed pages of OCR noise as a reading, which is what made a working
    # examination read as gibberish.
    fragmentary = state == STATE_READ_NOT_INTERPRETED
    return {
        "name": display_name,
        "fragmentary": fragmentary,
        "state": state,
        "state_label": STATE_LABELS[state],
        "filename": filename,
        "received_at": getattr(document, "ingested_at", "") or "",
        "source_id": (source or {}).get("id"),
        "is_image": ext in _IMAGE_EXTS,
        "established": established,
        "interpretation": interpretation,
        "not_established": not_established,
        "preview_text": recovered["preview"],
        "sources": _source_rows(document, workspace, jobs=jobs),
        # While anything is still queued or running, the page must not present
        # the raw-text block or the "nothing was concluded" grammar: both are
        # statements about a completed reading.
        "pending": state in (STATE_QUEUED, STATE_PROCESSING),
    }


def _source_rows(document, workspace, *, jobs=None) -> list[dict[str, Any]]:
    """One row per Source, in the order the CUSTOMER chose.

    intake_order when the record states one; list position otherwise, which is
    what every container created before that field existed has. Never a
    filename, never a completion time, never a UUID.
    """
    rows = []
    for index, source in enumerate(_live_sources(workspace)):
        recovered = _recovered(workspace, source["id"])
        state = source_state(document, workspace, source["id"], jobs=jobs)
        order = source.get("intake_order")
        rows.append({
            "source_id": source["id"],
            "name": source.get("name") or "",
            "order": index if order is None else order,
            "state": state,
            "state_label": STATE_LABELS[state],
            "is_image": _ext(source.get("name") or "") in _IMAGE_EXTS,
            "passage_count": recovered["passage_count"],
            "character_count": recovered["character_count"],
            "read_by": recovered["read_by"],
            "preview": recovered["preview"],
            "pending": state in (STATE_QUEUED, STATE_PROCESSING),
        })
    rows.sort(key=lambda r: r["order"])
    return rows


def summarise_job(document, workspace, *, display_name: str,
                  project_id: str, jobs=None) -> dict[str, Any]:
    """One row in My Documents. Same state function as the result page uses,
    so a listing can never disagree with the page it links to."""
    sources = _live_sources(workspace)
    state = state_of(document, workspace, jobs=jobs)
    first: Optional[dict] = sources[0] if sources else None
    per_source = [source_state(document, workspace, s["id"], jobs=jobs)
                  for s in sources]
    settled = len([x for x in per_source
                   if x not in (STATE_QUEUED, STATE_PROCESSING)])
    return {
        "project_id": project_id,
        "name": display_name,
        "added_at": getattr(document, "ingested_at", "") or "",
        "source_count": len(sources),
        "first_source_id": (first or {}).get("id"),
        "state": state,
        "state_label": STATE_LABELS[state],
        # "Processing 2 of 5" - real counts from real job records, never a
        # progress bar animating over nothing.
        "settled_count": settled,
        "pending_count": len(sources) - settled,
    }
