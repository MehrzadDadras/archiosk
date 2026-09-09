"""CLAUDE-GO-PERCEPTION-WORKER-01 - one perception job per Source.

Perception used to run inside the Gunicorn request: ~8 seconds of OCR on a
12MP photograph, on a 13-worker tier with nothing behind it. A customer once
double-submitted during a 7-second wait and took a worker with them each time.
This store is where that work goes instead.

WHAT THIS IS NOT. Not a workflow engine, not a broker, not a scheduler. One
job = one Source at one processing version, and the only verbs are enqueue,
claim, complete, fail and reclaim. `tools/dependency_fit.py` already settles
that this project stays off broker infrastructure, so jobs are flat JSON beside
the records they describe - same directory, same ownership, same backup path,
atomic temp-file-and-rename, exactly as CaseWorkspaceStore already writes.

IDENTITY IS THE IDEMPOTENCY. A job's id is derived, not allocated:

    sha256(workspace_id + source_id + source_sha256 + processing_version)

so the file NAME is the deduplication. A repeated POST, a worker restart, a
web retry, a crash and a deployment restart cannot produce a different name for
the same work, and none of them needs a check that someone could forget to
write. Asking for the work again under a NEW processing_version is a different
id and therefore an explicit new run, with the earlier evidence left intact.
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

# States, and only states an implementation fact can support.
STATE_QUEUED = "queued"
STATE_RUNNING = "running"
STATE_COMPLETED = "completed"
STATE_NEEDS_ATTENTION = "needs_attention"
STATE_FAILED = "failed"

TERMINAL_STATES = frozenset({STATE_COMPLETED, STATE_NEEDS_ATTENTION, STATE_FAILED})
OPEN_STATES = frozenset({STATE_QUEUED, STATE_RUNNING})

# NEEDS_ATTENTION is deliberately distinct from FAILED. "Perception ran and
# established nothing" is a fact about the document; "perception did not run"
# is a fault in the system. Collapsing them is how a blank photograph would
# come to look like an outage.

MAX_ATTEMPTS = 3

# How long a claim is honoured before another worker may take the job. Long
# enough that a slow 12MP OCR is never stolen mid-flight; short enough that a
# killed worker does not wedge a customer's document for an afternoon.
LEASE_SECONDS = 600

# Bumping this is how a re-examination is requested. It is part of the job
# identity, so a new value is a new job rather than a silent overwrite.
PROCESSING_VERSION = "orientation-ocr@1"

# This tranche is local-only, and every job says so in its own record rather
# than relying on the absence of evidence to the contrary.
EGRESS_NONE = "none"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def job_identity(workspace_id: str, source_id: str, source_sha256: str,
                 processing_version: str = PROCESSING_VERSION) -> str:
    """The whole idempotency model, in one deterministic function."""
    digest = hashlib.sha256()
    for part in (workspace_id, source_id, source_sha256, processing_version):
        digest.update((part or "").encode("utf-8"))
        digest.update(b"\x00")
    return digest.hexdigest()


class PerceptionJobStore:
    """Flat-JSON job records, one file per job.

    Deliberately mirrors CaseWorkspaceStore's write discipline - atomic
    temp-file-and-rename, no partial file ever visible at the real path - so
    a crash mid-write cannot leave a job record that parses as half a truth.
    """

    def __init__(self, registry_store_path):
        self.root = Path(registry_store_path) / "perception_jobs"
        self._lock = threading.Lock()

    # -- paths ---------------------------------------------------------------

    def _path(self, job_id: str) -> Path:
        return self.root / ("%s.json" % job_id)

    def _write(self, record: dict) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(record["job_id"])
        handle, temporary = tempfile.mkstemp(dir=str(self.root), suffix=".tmp")
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(record, stream, indent=2, sort_keys=True)
            Path(temporary).replace(path)
        finally:
            if Path(temporary).exists():
                Path(temporary).unlink()
        return record

    # -- reads ---------------------------------------------------------------

    def get(self, job_id: str) -> Optional[dict]:
        path = self._path(job_id)
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # A record that will not parse is not a reason to take the queue
            # down; it is reported by list_all's own skip and stays on disk
            # for inspection rather than being silently repaired.
            return None

    def list_all(self) -> list[dict]:
        if not self.root.exists():
            return []
        found = []
        for path in sorted(self.root.glob("*.json")):
            try:
                found.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
        return found

    def for_workspace(self, workspace_id: str) -> list[dict]:
        return [j for j in self.list_all() if j.get("workspace_id") == workspace_id]

    def for_source(self, workspace_id: str, source_id: str) -> list[dict]:
        return [j for j in self.for_workspace(workspace_id)
                if j.get("source_id") == source_id]

    def latest_for_source(self, workspace_id: str, source_id: str) -> Optional[dict]:
        jobs = sorted(self.for_source(workspace_id, source_id),
                      key=lambda j: j.get("created_at") or "")
        return jobs[-1] if jobs else None

    # -- writes --------------------------------------------------------------

    def enqueue(self, *, workspace_id: str, source_id: str, source_sha256: str,
                source_name: str = "", intake_order: Optional[int] = None,
                processing_version: str = PROCESSING_VERSION) -> dict:
        """Create the job, or return the one that already exists.

        Not "create if absent" as a check-then-act - the identity IS the file
        name, so a second call for the same work simply finds it there. There
        is no window between the check and the write for a duplicate to slip
        through.
        """
        job_id = job_identity(workspace_id, source_id, source_sha256,
                              processing_version)
        with self._lock:
            existing = self.get(job_id)
            if existing is not None:
                return existing
            return self._write({
                "job_id": job_id,
                "workspace_id": workspace_id,
                "source_id": source_id,
                "source_sha256": source_sha256,
                "source_name": source_name,
                "intake_order": intake_order,
                "processing_version": processing_version,
                "state": STATE_QUEUED,
                "attempt_count": 0,
                "created_at": _now(),
                "claimed_at": None,
                "claimed_by": None,
                "completed_at": None,
                "processing_location": socket.gethostname(),
                "extractor": None,
                "extractor_version": None,
                "evidence_refs": [],
                "failure_reason": None,
                "egress": EGRESS_NONE,
            })

    def claim_next(self, *, worker_id: str) -> Optional[dict]:
        """Take the oldest claimable job, or None.

        Claimable means QUEUED, or RUNNING with an expired lease - a worker
        that was killed mid-job must not wedge that Source forever. Reclaiming
        increments attempt_count, so a job that reliably kills its worker
        reaches FAILED rather than looping.
        """
        with self._lock:
            cutoff = datetime.now(timezone.utc) - timedelta(seconds=LEASE_SECONDS)
            candidates = []
            for job in self.list_all():
                if job.get("state") == STATE_QUEUED:
                    candidates.append(job)
                elif job.get("state") == STATE_RUNNING:
                    claimed = job.get("claimed_at")
                    if not claimed:
                        candidates.append(job)
                        continue
                    try:
                        when = datetime.fromisoformat(claimed)
                        if when.tzinfo is None:
                            when = when.replace(tzinfo=timezone.utc)
                        if when < cutoff:
                            candidates.append(job)
                    except Exception:
                        candidates.append(job)
            if not candidates:
                return None
            candidates.sort(key=lambda j: j.get("created_at") or "")
            job = candidates[0]
            if job.get("attempt_count", 0) >= MAX_ATTEMPTS:
                # Burn it rather than hand it out again, and return nothing so
                # the caller does not mistake a retired job for work to do.
                job["state"] = STATE_FAILED
                job["failure_reason"] = (
                    "retry ceiling of %d reached" % MAX_ATTEMPTS)
                job["completed_at"] = _now()
                self._write(job)
                return None
            job["state"] = STATE_RUNNING
            job["attempt_count"] = job.get("attempt_count", 0) + 1
            job["claimed_at"] = _now()
            job["claimed_by"] = worker_id
            return self._write(job)

    def complete(self, job: dict, *, state: str, extractor: Optional[str] = None,
                 extractor_version: Optional[str] = None,
                 evidence_refs: Optional[list] = None,
                 failure_reason: Optional[str] = None) -> dict:
        if state not in TERMINAL_STATES:
            raise ValueError("not a terminal state: %r" % state)
        with self._lock:
            current = self.get(job["job_id"]) or job
            current["state"] = state
            current["completed_at"] = _now()
            current["extractor"] = extractor
            current["extractor_version"] = extractor_version
            current["evidence_refs"] = list(evidence_refs or [])
            current["failure_reason"] = failure_reason
            return self._write(current)

    def release_for_retry(self, job: dict, *, reason: str) -> dict:
        """Put a job back rather than burning it, when the failure looks
        transient. attempt_count already advanced at claim time, so this can
        never loop unboundedly."""
        with self._lock:
            current = self.get(job["job_id"]) or job
            if current.get("attempt_count", 0) >= MAX_ATTEMPTS:
                current["state"] = STATE_FAILED
                current["completed_at"] = _now()
            else:
                current["state"] = STATE_QUEUED
                current["claimed_at"] = None
                current["claimed_by"] = None
            current["failure_reason"] = reason
            return self._write(current)

    # -- observability -------------------------------------------------------

    def queue_depth(self) -> dict:
        """Worker health, reported separately from web health on purpose: the
        application must stay usable, and report itself usable, while no
        perception worker is running at all."""
        jobs = self.list_all()
        queued = [j for j in jobs if j.get("state") == STATE_QUEUED]
        running = [j for j in jobs if j.get("state") == STATE_RUNNING]
        oldest = min((j.get("created_at") or "" for j in queued), default=None)
        return {
            "queued": len(queued),
            "running": len(running),
            "completed": len([j for j in jobs if j.get("state") == STATE_COMPLETED]),
            "needs_attention": len([j for j in jobs if j.get("state") == STATE_NEEDS_ATTENTION]),
            "failed": len([j for j in jobs if j.get("state") == STATE_FAILED]),
            "oldest_queued_at": oldest,
            "current": [j.get("job_id") for j in running],
        }


def new_worker_id() -> str:
    return "%s:%d:%s" % (socket.gethostname(), os.getpid(), uuid.uuid4().hex[:8])
