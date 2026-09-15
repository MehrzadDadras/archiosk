"""CLAUDE-SURVEY-REFERENCE-01 - the process that looks at a source.

    claim (visual queue) -> wait for OCR -> look -> store reading -> derive

DELIBERATELY NOT A CHANGE TO `services/perception_worker.py`. That file's
sha256 is pinned by `docs/records/datum-lifecycle-transition-01.json` as part of
a live verification of `op.datum-corroboration`, and
`services/operational_frontier.py` refuses to apply a verified lifecycle
transition to changed implementation - "Do not silently apply a historical
transition to changed implementation."

A first version of this work DID edit that worker. The frontier reconciler
raised the conflict exactly as designed, the conflict became a `ui_blocker`, and
the Operational Flight Deck went to 503 - caught by four failing tests in the
full gate before anything was deployed. The honest options were to re-perform
the live verification or to leave the file alone; re-pinning the digest would
have re-asserted a verification nobody repeated. Product Owner ruling,
2026-09-15: leave it alone and follow the precedent that
`services/founding_worker.py` already set for this identical conflict.

So visual work got its own queue directory and its own loop, and the perception
worker is byte-identical to the state that was verified.

ONE JOB AT A TIME, like both existing workers and for the same reason: the web
tier is the primary workload on a 6 vCPU host with thirteen Gunicorn workers
already resident. Throughput is not what this buys. What it buys is that
looking at a survey does not occupy a request - the same reasoning that moved
OCR off the request after a customer double-submitted during an eight-second
wait and took a worker with them each time.

THE CLAIM IS FILTERED THREE WAYS, and each guard is cheap:

  - the DIRECTORY already means this loop only sees visual work;
  - `versions=` makes a misfiled job unclaimable rather than mishandled;
  - `ready=` defers a job whose source is still being OCR'd, so the recovered
    text can travel with the image as context. That is a READINESS predicate,
    not a retry - a job waiting its turn has not failed, and must not spend the
    `MAX_ATTEMPTS` budget that exists for jobs that have.

STOPPING THIS SERVICE MUST NOT MAKE THE APPLICATION UNHEALTHY. Uploads still
succeed, perception still runs, jobs accumulate as QUEUED, and they drain when
the worker returns. A visual-examination outage is a delayed reading, never a
broken Document Shop - and never a fabricated one.
"""
from __future__ import annotations

import logging
import signal
import time

from services import perception_jobs, visual_classification

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0


class _Stopped(Exception):
    pass


def run_one(app, jobs=None, worker_id: str = "") -> "dict | None":
    """Claim and examine a single visual job. Returns the record, or None."""
    jobs = jobs or visual_classification.visual_store(
        app.config["REGISTRY_STORE_PATH"])
    worker_id = worker_id or perception_jobs.new_worker_id()

    perception_store = perception_jobs.PerceptionJobStore(
        app.config["REGISTRY_STORE_PATH"])

    job = jobs.claim_next(
        worker_id=worker_id,
        versions=visual_classification.VISUAL_VERSIONS,
        ready=lambda candidate: visual_classification.perception_is_settled(
            perception_store, candidate))
    if job is None:
        return None

    logger.info("visual job %s claimed (source %s)",
                job["job_id"][:12], job.get("source_id"))
    # `examine_source` never raises: every outcome is a job state, so one bad
    # image cannot take this loop down with it.
    return visual_classification.examine_source(app, jobs, job)


def run_forever(app, poll_seconds: float = POLL_SECONDS) -> None:
    """Poll until told to stop. Idle is the normal state, not a fault."""
    jobs = visual_classification.visual_store(app.config["REGISTRY_STORE_PATH"])
    worker_id = perception_jobs.new_worker_id()

    def _stop(_signum, _frame):
        raise _Stopped()

    for received in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(received, _stop)
        except (ValueError, AttributeError):
            # Not the main thread, or a platform without it. A worker that
            # cannot install a handler still works; it just exits less politely.
            pass

    logger.info("visual worker %s started", worker_id)
    try:
        while True:
            try:
                record = run_one(app, jobs, worker_id)
            except _Stopped:
                raise
            except Exception as exc:  # noqa: BLE001 - never exit on one job
                logger.exception("visual worker error (%s)", type(exc).__name__)
                record = None
            if record is None:
                time.sleep(poll_seconds)
    except _Stopped:
        logger.info("visual worker %s stopping", worker_id)


def main() -> None:
    from app import create_app

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    run_forever(create_app("production"))


if __name__ == "__main__":
    main()
