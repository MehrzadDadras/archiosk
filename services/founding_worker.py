"""CLAUDE-FOUNDING-ASYNC-01 - the process that classifies a founded document.

    claim (founding queue) -> verify digest -> parse -> file the record -> complete

DELIBERATELY NOT A CHANGE TO `services/perception_worker.py`. That file's sha256
is pinned by `docs/records/datum-lifecycle-transition-01.json` as part of a live
verification of `op.datum-corroboration`, and `services/operational_frontier.py`
refuses to apply a verified lifecycle transition to changed implementation -
"Do not silently apply a historical transition to changed implementation."

A first version of this work did edit that worker, to filter claims by kind and
dispatch. The frontier reconciler correctly raised the conflict. The honest
options were to re-perform the live verification or to leave the file alone;
re-pinning the digest would have re-asserted a verification nobody repeated. So
founding work got its own queue directory and its own loop, and the perception
worker is byte-identical to the state that was verified.

ONE JOB AT A TIME, like the perception worker and for the same reason: the web
tier is the primary workload on a 6 vCPU host with thirteen Gunicorn workers
already resident. Throughput is not what this buys. What it buys is that
classifying a large document no longer occupies a request.

THE CLAIM IS FILTERED AS WELL AS NAMESPACED. The directory already means this
loop only sees founding work, so the `versions` filter is belt-and-braces: it
makes a misfiled job unclaimable rather than mishandled. Two cheap guards for a
failure that would otherwise be silent.
"""
from __future__ import annotations

import logging
import signal
import time

from services import founding_classification, perception_jobs

logger = logging.getLogger(__name__)

POLL_SECONDS = 2.0


class _Stopped(Exception):
    pass


def run_one(app, jobs=None, worker_id: str = "") -> "dict | None":
    """Claim and classify a single founding job. Returns the record, or None."""
    jobs = jobs or founding_classification.founding_store(
        app.config["REGISTRY_STORE_PATH"])
    worker_id = worker_id or perception_jobs.new_worker_id()

    job = jobs.claim_next(worker_id=worker_id,
                          versions=founding_classification.FOUNDING_VERSIONS)
    if job is None:
        return None

    logger.info("founding job %s claimed (source %s)",
                job["job_id"][:12], job.get("source_id"))
    # `classify_source` never raises: every outcome is a job state, so a bad
    # document cannot take this loop down with it.
    return founding_classification.classify_source(app, jobs, job)


def run_forever(app, poll_seconds: float = POLL_SECONDS) -> None:
    """Poll until told to stop. Idle is the normal state, not a fault."""
    jobs = founding_classification.founding_store(
        app.config["REGISTRY_STORE_PATH"])
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

    logger.info("founding worker %s started", worker_id)
    try:
        while True:
            try:
                record = run_one(app, jobs, worker_id)
            except _Stopped:
                raise
            except Exception as exc:              # noqa: BLE001 - never exit on one job
                logger.exception("founding worker error (%s)", type(exc).__name__)
                record = None
            if record is None:
                time.sleep(poll_seconds)
    except _Stopped:
        logger.info("founding worker %s stopping", worker_id)


def main() -> None:
    from app import create_app

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    run_forever(create_app("production"))


if __name__ == "__main__":
    main()
