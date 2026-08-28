"""
CLAUDE-STORAGE-BRIDGE-07 - a byte-request queue fifteen worker processes share.

WHY NOT MEMORY, AND WHY NOT THE DATABASE

Memory was the original mistake and Phase 2 exposed it in production: the
manifest landed in one gunicorn worker and the other fourteen had no idea it
existed. Roughly one request in fifteen saw it, which presents as intermittent
rather than broken - the worst way for something to be wrong.

The database was the obvious correction and is the wrong one. A byte request is
transient coordination, not a governed record; it should die with a project
reset, not survive one (which is the test models.DiagnosticReport's own docstring
sets for what belongs in the database). It also has no audit value once served.

So: the filesystem, under REGISTRY_STORE_PATH - which is exactly where
ingestion.PendingReconcileStore already stages Data Room uploads, including raw
bytes with an expiry sweep. That precedent matters twice: every worker already
shares this directory, and temporary byte staging with an explicit lifecycle is
already a sanctioned pattern here rather than something introduced now.

ONE FILE PER REQUEST, AND WHY THAT SETTLES CONCURRENCY

CaseWorkspaceStore._save_lock is a threading.Lock - process-local, so it
protects nothing across fifteen processes. Optimistic version checking would
work but turns every collision into a retry.

Neither is needed if two workers never write the same file. Each request is its
own JSON document, and every state change is an os.rename between directories:

    pending/<id>.json  --rename-->  claimed/<id>.json  --rename-->  served/<id>.json

rename(2) is atomic and fails if the source is gone, so two workers racing to
claim the same request produce exactly one winner and one FileNotFoundError. No
lock, no version, no retry loop - the filesystem already provides the primitive.

BYTES ARE STAGED, NOT KEPT

A delivered payload is written beside its request and deleted the moment it is
consumed. That is the "temporary working copy where processing genuinely
requires it, with explicit lifecycle" that external custody permits - not a
cache, and never the authoritative copy. The sweep is the backstop for a worker
that dies mid-operation.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from typing import Optional

_QUEUE_SUBDIR = "_bridge_queue"
_PENDING, _CLAIMED, _SERVED = "pending", "claimed", "served"

# A request nobody answers is not a request any more. Long enough for an agent
# on a slow domestic uplink to poll, fetch and return a large drawing; short
# enough that a dead worker's claim frees up while someone still cares.
DEFAULT_REQUEST_TTL_SECONDS = 1800
DEFAULT_CLAIM_TTL_SECONDS = 600


# The closed vocabulary of what a byte request may be FOR.
#
# Deliberately closed. An open-world purpose would let any future caller push
# arbitrary work through the byte queue by naming it - which is a capability
# boundary, not a naming convention. Adding one is a deliberate edit here, where
# the reviewer can see the whole list at once.
PURPOSE_REGISTER_SOURCE = "register_source"
PURPOSE_EXTRACT_TEXT = "extract_text"
PURPOSE_PDF_GEOMETRY = "pdf_geometry"
KNOWN_PURPOSES = (PURPOSE_REGISTER_SOURCE, PURPOSE_EXTRACT_TEXT, PURPOSE_PDF_GEOMETRY)


class BridgeQueueError(Exception):
    """The request cannot be honoured, and the caller must not pretend it can."""


class BridgeQueueStore:
    """Filesystem-backed, worker-agnostic. Holds no state of its own."""

    def __init__(self, store_path: str | Path,
                 request_ttl_seconds: int = DEFAULT_REQUEST_TTL_SECONDS,
                 claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS):
        self.root = Path(store_path) / _QUEUE_SUBDIR
        self.request_ttl = request_ttl_seconds
        self.claim_ttl = claim_ttl_seconds
        for state in (_PENDING, _CLAIMED, _SERVED):
            (self.root / state).mkdir(parents=True, exist_ok=True)

    # -- paths -------------------------------------------------------------
    def _path(self, state: str, request_id: str) -> Path:
        return self.root / state / ("%s.json" % request_id)

    def _payload_path(self, request_id: str) -> Path:
        return self.root / _CLAIMED / ("%s.bytes" % request_id)

    # -- enqueue -----------------------------------------------------------
    def enqueue(self, project_id: str, relative_path: str, purpose: str,
                *, requested_by: str = "system", now: Optional[float] = None) -> dict:
        """Leave a request any worker can later find.

        Refuses an unknown purpose outright rather than storing it and failing
        later: the point of a closed vocabulary is that the boundary is checked
        where it is declared.
        """
        if purpose not in KNOWN_PURPOSES:
            raise BridgeQueueError(
                "%r is not a known byte-request purpose. Known: %s."
                % (purpose, ", ".join(KNOWN_PURPOSES)))
        self.sweep_expired(now=now)
        record = {
            "id": "req-%s" % uuid.uuid4().hex[:16],
            "project_id": project_id,
            "relative_path": relative_path,
            "purpose": purpose,
            "requested_by": requested_by,
            "requested_at": now if now is not None else time.time(),
        }
        self._write(self._path(_PENDING, record["id"]), record)
        return record

    # -- claim (the agent's outbound poll) ---------------------------------
    def claim_pending(self, project_id: str, *, now: Optional[float] = None) -> list[dict]:
        """Atomically take every pending request for ONE project.

        Scoped by project_id read from the record itself, so a poll can never
        collect another project's work even though all projects share this
        directory.
        """
        self.sweep_expired(now=now)
        claimed = []
        for path in sorted((self.root / _PENDING).glob("*.json")):
            record = self._read(path)
            if record is None or record.get("project_id") != project_id:
                continue
            target = self._path(_CLAIMED, record["id"])
            try:
                # THE concurrency primitive. Atomic, and it raises rather than
                # silently succeeding if another worker got there first.
                os.rename(path, target)
            except (FileNotFoundError, OSError):
                continue
            record["claimed_at"] = now if now is not None else time.time()
            self._write(target, record)
            claimed.append(record)
        return claimed

    # -- deliver / consume -------------------------------------------------
    def deliver(self, request_id: str, payload: bytes,
                *, now: Optional[float] = None) -> dict:
        """Stage bytes against a claimed request. Not a cache - see consume."""
        path = self._path(_CLAIMED, request_id)
        record = self._read(path)
        if record is None:
            raise BridgeQueueError(
                "Request %s is not awaiting delivery (unknown, already served, "
                "or expired)." % request_id)
        self._payload_path(request_id).write_bytes(payload)
        record["delivered_at"] = now if now is not None else time.time()
        record["size_bytes"] = len(payload)
        self._write(path, record)
        return record

    def consume(self, request_id: str) -> tuple[dict, bytes]:
        """Take the bytes AND destroy the staged copy, in that order.

        The unlink happens before returning, so a caller that crashes mid-work
        leaves no payload behind. A second consume finds nothing, which is the
        transience guarantee external custody depends on.
        """
        path = self._path(_CLAIMED, request_id)
        record = self._read(path)
        payload_path = self._payload_path(request_id)
        if record is None or not payload_path.is_file():
            raise BridgeQueueError("No delivered payload for request %s." % request_id)
        payload = payload_path.read_bytes()
        payload_path.unlink()
        served = self._path(_SERVED, request_id)
        record["served_at"] = time.time()
        self._write(served, record)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return record, payload

    # -- reads -------------------------------------------------------------
    def pending_for(self, project_id: str) -> list[dict]:
        return self._all_in(_PENDING, project_id)

    def claimed_for(self, project_id: str) -> list[dict]:
        return self._all_in(_CLAIMED, project_id)

    def holds_payload(self, request_id: str) -> bool:
        return self._payload_path(request_id).is_file()

    def _all_in(self, state: str, project_id: str) -> list[dict]:
        found = []
        for path in sorted((self.root / state).glob("*.json")):
            record = self._read(path)
            if record is not None and record.get("project_id") == project_id:
                found.append(record)
        return found

    # -- lifecycle ---------------------------------------------------------
    def sweep_expired(self, *, now: Optional[float] = None) -> int:
        """Drop stale requests and abandoned claims, payloads included.

        A worker that dies holding a claim would otherwise strand that request
        forever; this is the recovery, and it is the same shape
        PendingReconcileStore._sweep_expired already uses.
        """
        moment = now if now is not None else time.time()
        removed = 0
        for state, ttl, stamp in ((_PENDING, self.request_ttl, "requested_at"),
                                  (_CLAIMED, self.claim_ttl, "claimed_at"),
                                  (_SERVED, self.request_ttl, "served_at")):
            for path in (self.root / state).glob("*.json"):
                record = self._read(path)
                if record is None:
                    path.unlink(missing_ok=True)
                    removed += 1
                    continue
                age = moment - float(record.get(stamp) or record.get("requested_at") or 0)
                if age > ttl:
                    self._payload_path(record.get("id", "")).unlink(missing_ok=True)
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    def purge_project(self, project_id: str) -> int:
        """Every trace of one project's queue. Used when an enrolment is
        revoked: bytes must stop moving immediately, though nothing the project
        already KNOWS is touched."""
        removed = 0
        for state in (_PENDING, _CLAIMED, _SERVED):
            for path in list((self.root / state).glob("*.json")):
                record = self._read(path)
                if record is not None and record.get("project_id") == project_id:
                    self._payload_path(record.get("id", "")).unlink(missing_ok=True)
                    path.unlink(missing_ok=True)
                    removed += 1
        return removed

    # -- io ----------------------------------------------------------------
    @staticmethod
    def _write(path: Path, record: dict) -> None:
        """Write via a temp file and rename, so a reader never sees half a
        record - the same reason the rest of this module leans on rename."""
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2), encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _read(path: Path) -> Optional[dict]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # A partially written or deleted record is not an error worth
            # raising into a poll: it is swept and the agent asks again.
            return None
