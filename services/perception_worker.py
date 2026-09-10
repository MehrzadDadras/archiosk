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


def _write_positioned_with_retry(store, job, positioned, extractor_version,
                                 governance_log):
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
    """
    if not positioned or not positioned.get("lines"):
        return None

    from services.case_workspace import CaseWorkspaceError

    for attempt in range(CONCURRENT_WRITE_RETRIES):
        workspace = store.get(job["workspace_id"])
        if workspace is None:
            return None
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
        already = [e for e in (getattr(workspace, "evidence_items", None) or [])
                   if e.get("source_id") == job["source_id"]
                   and e.get("content_type") == "positioned_text"]
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
        return jobs.complete(
            job, state=perception_jobs.STATE_COMPLETED,
            extractor=recovered.get("engine"),
            extractor_version=recovered.get("engine_version"),
            evidence_refs=([e["id"] for e in already]
                           + list((replay_positioned or {}).get("evidence_item_ids") or [])))

    outcome, error = _write_evidence_with_retry(
        store, job["workspace_id"], job["source_id"], text,
        extractor_version, governance_log, "perception-worker")
    if error:
        return jobs.release_for_retry(job, reason=error)

    positioned_outcome = _write_positioned_with_retry(
        store, job, positioned, extractor_version, governance_log)

    return jobs.complete(
        job, state=perception_jobs.STATE_COMPLETED,
        extractor=recovered.get("engine"),
        extractor_version=recovered.get("engine_version"),
        evidence_refs=(list((outcome or {}).get("evidence_item_ids") or [])
                       + list((positioned_outcome or {}).get("evidence_item_ids") or [])))


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
