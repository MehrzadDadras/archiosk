"""CLAUDE-FOUNDING-ASYNC-01 - founding classification, moved off the request.

    CHUNKS -> STREAMED VERIFIED ASSEMBLY -> PROJECT + SOURCE -> JOB -> READY

WHAT THIS CHANGES, STATED PLAINLY, BECAUSE IT IS NOT A REFACTOR

Today `ingest_upload` PARSES BEFORE IT CREATES. A `ParserError` becomes an
`UploadError` and nothing is written - no project, no Source, no bytes. Founding
classification is therefore a GATE: a document that cannot be classified does not
become a project at all.

This module converts that gate into an ENRICHMENT for the staged path. The
project and the Source exist as soon as the assembled bytes are verified, and
classification runs afterwards as a job. That is a real change in authority
semantics, explicitly authorized by the Product Owner, and the safety it trades
for is paid back in exactly one way: THE INCOMPLETE STATE IS EXPLICIT AND
LOAD-BEARING. A Source whose founding job has not completed is not represented as
classified anywhere - `document_examination.source_state` already reports
`queued`/`processing` from job facts and already says "job facts outrank evidence
facts while a job is open".

    A SAFELY STORED SOURCE IS NOT A FULLY CLASSIFIED SOURCE.

PERCEPTION AND FOUNDING ARE NOT EQUIVALENT, AND THE DIRECTION WAS RIGHT TO ASK

Both are asynchronous jobs over one Source, so the substrate is shared. The
LIFECYCLE AUTHORITY is not:

  - a perception job is an ENRICHMENT. It adds OCR text, orientation and legend
    candidates to a Source that already stands on its own. A failed perception
    job leaves a usable Source.
  - founding classification currently DECIDES WHETHER THE PROJECT EXISTS. Its
    output - requirements, tables, consistency flags - is the `ParsedDocument`
    that `RequirementsRegistry` holds as the project's record.

So this module composes with `PerceptionJobStore` rather than inventing a second
job system, but it does NOT pretend the two kinds of work mean the same thing.
The store separates them by `processing_version`, which its own docstring already
establishes as the mechanism for "an explicit new run" - one more version is one
more kind of work, with its own identity, its own retries and its own handler.

NO NEW LIFECYCLE VOCABULARY. Searched before writing: the user-facing states the
direction asks for already exist and are already job-aware.

    UPLOADING      the staging manifest - no Source exists yet
    ASSEMBLING     `ChunkedUploadStore.assemble`'s `.assembling` temp file
    PROCESSING     document_examination.STATE_QUEUED / STATE_PROCESSING
    READY          document_examination.STATE_RESULT_READY
    FAILED         STATE_COULD_NOT_COMPLETE / STATE_NEEDS_ATTENTION
    RETRYING       perception_jobs attempt_count + release_for_retry

IDEMPOTENCY IS INHERITED, NOT REIMPLEMENTED. A job's id is
`sha256(workspace_id + source_id + source_sha256 + processing_version)` and the
file NAME is the deduplication, so a duplicate enqueue, a worker restart, a
redeploy and a retry cannot produce two runs of the same founding work. The
assembled file is written once by `assemble()` under a `.assembling` temp name
and renamed only when complete and size-checked, so a retry re-reads bytes that
are already final - it never re-assembles and never produces a second Source.

WHAT THIS MODULE DOES NOT DO: it does not touch the synchronous path. All five
`ingest_upload` callers are unchanged, and the 60 MB front door remains the
fallback until this is proven equivalent. Create, verify, cut over, delete - in
that order.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Optional

from services import perception_jobs

logger = logging.getLogger(__name__)

#: The kind of work, and therefore the job identity namespace. Bumping this is
#: how a re-classification becomes an explicit new run rather than a silent
#: overwrite - the same contract `perception_jobs.PROCESSING_VERSION` carries.
FOUNDING_VERSION = "founding-classification@1"

#: FOUNDING WORK HAS ITS OWN QUEUE DIRECTORY, which is what keeps the deployed
#: perception worker from ever seeing it. That worker claims the oldest claimable
#: job in ITS directory with no filter, so a founding job sitting there would be
#: claimed and run through OCR - producing a confident empty result over a
#: specification and marking the job complete.
#:
#: Namespaced rather than filtered because filtering meant editing
#: `services/perception_worker.py`, whose sha256 is pinned by
#: `docs/records/datum-lifecycle-transition-01.json` as part of a live
#: verification. See `PerceptionJobStore.__init__` for the full reasoning.
FOUNDING_JOBS_SUBDIR = "founding_jobs"

PERCEPTION_VERSIONS = frozenset({perception_jobs.PROCESSING_VERSION})
FOUNDING_VERSIONS = frozenset({FOUNDING_VERSION})


def founding_store(registry_store_path) -> "perception_jobs.PerceptionJobStore":
    """The founding queue. Same store class, same identity model, own directory."""
    return perception_jobs.PerceptionJobStore(registry_store_path,
                                             subdir=FOUNDING_JOBS_SUBDIR)

#: Why a founding job did not produce a classification. Named, because
#: "processing failed" is what the person currently gets and it tells them
#: nothing about whether to retry, replace the file, or wait.
REASON_SOURCE_MISSING = "the Source record for this job no longer exists"
REASON_FILE_MISSING = "the assembled file for this Source is not on disk"
REASON_DIGEST_MISMATCH = ("the file on disk no longer matches the digest recorded "
                          "at assembly")
REASON_PARSE_FAILED = "the document could not be classified"


class FoundingClassificationError(RuntimeError):
    """A founding job could not be completed. Never raised at a caller."""


def enqueue_for_source(jobs, *, workspace_id: str, source_id: str,
                       source_sha256: str, source_name: str = "",
                       intake_order: Optional[int] = None) -> dict:
    """Queue founding classification for an already-stored Source.

    Called AFTER the bytes are final. Reuses `PerceptionJobStore.enqueue`
    verbatim, only under this module's own processing version, so the identity
    and deduplication behaviour are the ones already proven in production.
    """
    return jobs.enqueue(
        workspace_id=workspace_id, source_id=source_id,
        source_sha256=source_sha256, source_name=source_name,
        intake_order=intake_order, processing_version=FOUNDING_VERSION)


def is_founding_job(job) -> bool:
    return (job or {}).get("processing_version") == FOUNDING_VERSION


def _source_of(workspace, source_id: str) -> Optional[dict]:
    for source in getattr(workspace, "sources", None) or []:
        if source.get("id") == source_id and not source.get("removed_at"):
            return source
    return None


def _file_digest(path: Path) -> str:
    """Streamed, because the whole point is files too large to hold at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def classify_source(app, jobs, job: dict, *, parser=None, registry=None,
                    store=None) -> dict:
    """Run founding classification for one job. NEVER RAISES.

    Returns the job record as `complete()` or `release_for_retry()` left it, so
    the worker loop treats this exactly like any other job outcome.

    THE DIGEST IS RE-VERIFIED BEFORE PARSING, and that is not paranoia about our
    own code - it is what makes a retry safe. A job can be claimed again after a
    worker died, a lease expired or the host restarted, and the only thing that
    makes re-reading the file sound is proof that the bytes are still the bytes
    the job was created for. A mismatch is a FAILURE rather than a fresh parse:
    silently classifying different content under the same job identity would put
    a result on the record that no evidence supports.
    """
    from services.bhive_parser import BHiveParser, ParserError
    from services.case_workspace import CaseWorkspaceStore
    from services.requirements_registry import RequirementsRegistry

    store = store or CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    registry = registry or RequirementsRegistry(app.config["REGISTRY_STORE_PATH"])
    parser = parser or BHiveParser()

    workspace_id = job.get("workspace_id")
    source_id = job.get("source_id")
    workspace = store.get(workspace_id)
    source = _source_of(workspace, source_id) if workspace else None

    if source is None:
        # Not retryable: a removed Source will not come back, and retrying would
        # burn two more attempts to reach the same conclusion.
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason=REASON_SOURCE_MISSING)

    path = Path(source.get("file_path") or "")
    if not source.get("file_path") or not path.is_file():
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason=REASON_FILE_MISSING)

    expected = (job.get("source_sha256") or "").strip().lower()
    actual = _file_digest(path)
    if expected and actual != expected:
        logger.warning("founding job %s digest mismatch (expected %s, found %s)",
                       job.get("job_id"), expected[:12], actual[:12])
        return jobs.complete(job, state=perception_jobs.STATE_FAILED,
                             failure_reason=REASON_DIGEST_MISMATCH)

    raw_bytes = path.read_bytes()
    original_name = source.get("origin_reference") or source.get("name") or path.name

    try:
        document = parser.parse(raw_bytes, original_name)
    except ParserError as exc:
        # RELEASED FOR RETRY, NOT FAILED. A parse can fail for reasons that pass
        # - a classification provider timing out is the common one - and the
        # attempt ceiling is what stops that looping. A document that genuinely
        # cannot be classified reaches FAILED on the third attempt, with the
        # Source and its bytes still intact.
        logger.info("founding classification failed for %s (%s)", source_id, exc)
        return jobs.release_for_retry(job, reason="%s: %s" % (REASON_PARSE_FAILED,
                                                             exc))
    except Exception as exc:                      # noqa: BLE001 - never escape
        logger.warning("founding classification raised for %s (%s: %s)",
                       source_id, type(exc).__name__, exc)
        return jobs.release_for_retry(
            job, reason="%s: %s" % (REASON_PARSE_FAILED, type(exc).__name__))

    # THE PROJECT ID IS THE ONE THAT ALREADY EXISTS. `parse` mints its own on a
    # fresh ParsedDocument, and letting that reach the registry would file this
    # document's classification under a project nobody can open.
    document.project_id = workspace_id
    document.original_file_path = str(path)
    document.original_file_hash = actual
    registry.save(document)

    logger.info("founding classification complete for %s (%d requirements)",
                source_id, len(document.requirements or []))
    return jobs.complete(job, state=perception_jobs.STATE_COMPLETED,
                         extractor="bhive-parser",
                         extractor_version=getattr(document, "parser_version", None))


def equivalence_fields(document) -> dict:
    """The fields founding must produce identically however it was run.

    Used by the equivalence tests rather than described in prose, so "materially
    equivalent" is a comparison somebody can run instead of a claim somebody
    made. Deliberately EXCLUDES `ingested_at` and `project_id`: one is a
    timestamp that differs between any two runs, and the other differs by
    design - the async path files under a project that already exists.
    """
    document = document or None
    if document is None:
        return {}
    return {
        "filename": getattr(document, "filename", None),
        "requirement_count": len(getattr(document, "requirements", None) or []),
        "requirement_texts": [getattr(r, "text", None)
                              for r in (getattr(document, "requirements", None) or [])],
        "requirement_categories": [getattr(r, "category", None)
                                   for r in (getattr(document, "requirements", None) or [])],
        "milestones": getattr(document, "milestones", None) or [],
        "table_count": len(getattr(document, "tables", None) or []),
        "consistency_checked": getattr(document, "consistency_checked", None),
        "consistency_flag_count": len(getattr(document, "consistency_flags", None) or []),
        "parser_version": getattr(document, "parser_version", None),
        "original_file_hash": getattr(document, "original_file_hash", None),
    }
