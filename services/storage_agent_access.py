"""
CLAUDE-STORAGE-BRIDGE-03 - durable enrolment for the outbound storage bridge.

WHY THIS MODULE EXISTS SEPARATELY FROM services/storage_bridge.py

That module is the protocol, and it deliberately imports nothing from `models`,
`routes` or Flask - the same framework-decoupling services/case_workspace.py
maintains, and for the same reason: the protocol's correctness should be
testable without a database, an app context or a migration.

So this is the bridging layer, exactly the role services/project_access.py plays
between case_workspace and models.User. It knows about both sides; neither of
them knows about it.

WHAT IS PERSISTED, AND WHAT CANNOT BE

Only `token_hash`. The raw token is returned once from `enrol_agent` and exists
nowhere afterwards - not in the row, not in a log, not in this module's memory.
StorageAgentEnrolment has no column capable of holding a NAS credential either,
which is deliberate: the agent authenticates ITSELF to ARCHIOSK, and how it
reaches its own storage never crosses the boundary.

WHAT WAS WRONG UNTIL CLAUDE-STORAGE-BRIDGE-07

The manifest and in-flight bytes lived in a process-local dict. Phase 2 proved in
production why that could not stand: fifteen gunicorn workers, one of which held
the manifest, so roughly one request in fifteen could see it. That reads as
intermittent rather than broken, and byte retrieval could not work at all.

Both are now durable and worker-agnostic. The manifest lives on the project
record (ProjectWorkspace.external_manifest - project data, dies with the project)
and the byte queue on the filesystem (services/bridge_queue.py - transient
coordination, shared by every worker). No module-level mutable state remains
here, and a test asserts that by AST rather than trusting it.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from services.external_source import ExternalSourceError
from services.storage_bridge import (
    DEFAULT_ENROLMENT_TTL_SECONDS,
    BridgeEnrolmentRevoked,
)

def _hash_token(raw_token: str) -> str:
    return hashlib.sha256((raw_token or "").encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enrol_agent(project_id: str, agent_label: str, *, actor: Optional[str] = None,
                ttl_seconds: int = DEFAULT_ENROLMENT_TTL_SECONDS) -> tuple[object, str]:
    """Issue an enrolment. The raw token is returned ONCE and never stored.

    Called by a maintainer, never by a web route that a stranger can reach -
    the same provisioning discipline verification_access.py already follows.
    """
    from models import StorageAgentEnrolment, db

    raw_token = secrets.token_urlsafe(32)
    enrolment = StorageAgentEnrolment(
        project_id=project_id,
        agent_label=agent_label,
        token_hash=_hash_token(raw_token),
        created_at=_now(),
        created_by=actor,
        expires_at=_now() + timedelta(seconds=ttl_seconds),
    )
    db.session.add(enrolment)
    db.session.commit()
    return enrolment, raw_token


def revoke_agent(project_id: str, agent_label: str, *,
                 actor: Optional[str] = None) -> int:
    """Withdraw a credential. The row stays; only `revoked_at` is set.

    Revoking is not deleting. Bytes stop arriving; the project never forgets
    what it knew, and the record of who could read it survives.
    """
    from models import StorageAgentEnrolment, db

    live = StorageAgentEnrolment.query.filter_by(
        project_id=project_id, agent_label=agent_label, revoked_at=None).all()
    for enrolment in live:
        enrolment.revoked_at = _now()
        enrolment.revoked_by = actor
    db.session.commit()
    if live:
        # Bytes must stop moving immediately. Nothing the project already KNOWS
        # is touched - the manifest, hashes and every derivative stay exactly
        # where they are; only work in flight is dropped.
        try:
            _queue().purge_project(project_id)
        except RuntimeError:
            pass          # no app context (CLI revoke) - the sweep will collect it
    return len(live)


def authorise_agent(raw_token: str, *, now: Optional[datetime] = None):
    """Resolve a presented token to its enrolment, or refuse.

    Unknown, expired and revoked are all refused with the SAME exception and
    message. Distinguishing them would tell someone holding no valid credential
    whether a project has an agent at all.
    """
    from models import StorageAgentEnrolment

    moment = now or _now()
    enrolment = StorageAgentEnrolment.query.filter_by(
        token_hash=_hash_token(raw_token)).first()
    refusal = BridgeEnrolmentRevoked("This storage agent is not authorised.")
    if enrolment is None or enrolment.revoked_at is not None:
        raise refusal
    expires_at = enrolment.expires_at
    if expires_at.tzinfo is None:            # SQLite hands back naive datetimes
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if moment > expires_at:
        raise refusal
    return enrolment


def _store(app=None):
    from flask import current_app

    from services.case_workspace import CaseWorkspaceStore

    application = app or current_app
    return CaseWorkspaceStore(application.config["REGISTRY_STORE_PATH"])


def _queue(app=None):
    from flask import current_app

    from services.bridge_queue import BridgeQueueStore

    application = app or current_app
    return BridgeQueueStore(application.config["REGISTRY_STORE_PATH"])


def record_manifest_for_token(raw_token: str, entries, *, app=None,
                              now: Optional[datetime] = None) -> str:
    """Persist what the agent reported, against the token's own project.

    There is deliberately no companion taking a project_id: an agent enrolled for
    one project cannot express a request for another, which is the same reasoning
    visible_cases_for records for Case privacy - the ability was removed rather
    than a check added.
    """
    from services.storage_bridge import manifest_digest

    enrolment = authorise_agent(raw_token, now=now)
    store = _store(app)
    workspace = store.get(enrolment.project_id)
    if workspace is None:
        raise ExternalSourceError(
            "Project %s no longer exists; its agent should be revoked."
            % enrolment.project_id)
    digest = manifest_digest(entries)
    store.record_external_manifest(
        workspace, [e.as_dict() for e in entries], digest,
        actor="storage-agent:%s" % enrolment.agent_label)
    return digest


def manifest_entries_for(project_id: str, *, app=None) -> list:
    """The last reported manifest, readable by ANY worker."""
    from services.storage_bridge import ManifestEntry

    workspace = _store(app).get(project_id)
    if workspace is None:
        return []
    return [ManifestEntry.from_dict(row) for row in workspace.external_manifest]


def descriptors_for_manifest(project_id: str, *, app=None) -> list:
    """ManifestEntry -> ReconcileDescriptor, the whole point of Slice A.

    Lives HERE rather than in ingestion or storage_bridge so neither of those
    gains a dependency on the other: this module already bridges the two worlds
    and is where the coupling was deliberately confined. Reconcile then judges a
    manifest by exactly the rules it applies to a browser-selected folder, with
    no bytes and no second classifier.
    """
    from services.ingestion import ReconcileDescriptor

    return [
        ReconcileDescriptor(
            relative_path=entry.relative_path,
            filename=entry.relative_path.rsplit("/", 1)[-1],
            sha256=entry.sha256,
            size_bytes=entry.size_bytes,
        )
        for entry in manifest_entries_for(project_id, app=app)
    ]


def request_bytes(project_id: str, relative_path: str, purpose: str, *,
                  requested_by: str = "system", app=None) -> dict:
    """Enqueue a byte request, refusing any path the manifest never mentioned.

    ARCHIOSK asking for a file it has no evidence of would be guessing at the
    private side's contents, and would hand the agent an arbitrary path to go
    looking for - a traversal vector by proxy.
    """
    known = {entry.relative_path for entry in manifest_entries_for(project_id, app=app)}
    if relative_path not in known:
        raise ExternalSourceError(
            "%s is not in this project's last manifest; ARCHIOSK will not ask "
            "the agent for a path it has no evidence of." % relative_path)
    return _queue(app).enqueue(project_id, relative_path, purpose,
                               requested_by=requested_by)


def claim_pending_for_token(raw_token: str, *, app=None,
                            now: Optional[datetime] = None) -> list[dict]:
    enrolment = authorise_agent(raw_token, now=now)
    return _queue(app).claim_pending(enrolment.project_id)


def deliver_for_token(raw_token: str, request_id: str, payload: bytes, *,
                      app=None, now: Optional[datetime] = None) -> dict:
    """Accept bytes, verified against the manifest before they are staged.

    A delivery whose bytes do not hash to what the manifest advertised is
    refused as an ERROR rather than a retryable condition: retrying a wrong
    payload just fetches it again, more confidently.
    """
    import hashlib

    enrolment = authorise_agent(raw_token, now=now)
    queue = _queue(app)
    claimed = {record["id"]: record for record in queue.claimed_for(enrolment.project_id)}
    record = claimed.get(request_id)
    if record is None:
        raise ExternalSourceError(
            "Request %s is not awaiting delivery for this project." % request_id)
    expected = {entry.relative_path: entry.sha256
                for entry in manifest_entries_for(enrolment.project_id, app=app)}
    advertised = expected.get(record["relative_path"])
    actual = hashlib.sha256(payload).hexdigest()
    if advertised and advertised != actual:
        raise ExternalSourceError(
            "Delivered bytes for %s hash to %s but the manifest says %s."
            % (record["relative_path"], actual, advertised))
    return queue.deliver(request_id, payload)


def note_agent_contact(enrolment, *, now: Optional[datetime] = None) -> None:
    """Record that the agent was heard from, for operator visibility only.

    Liveness for PROTOCOL purposes lives on the bridge; this column exists so a
    human can see when a NAS last checked in without reading process memory.
    """
    from models import db

    enrolment.last_seen_at = now or _now()
    db.session.commit()


def reset_bridges_for_testing(app=None) -> None:
    """Clear durable queue state between tests.

    Kept under its original name so existing callers do not change, but it no
    longer clears a module global - there is none. A test that inherited another
    test's queued requests would pass for the wrong reason.
    """
    import shutil

    from flask import current_app

    try:
        application = app or current_app
        root = Path(application.config["REGISTRY_STORE_PATH"]) / "_bridge_queue"
    except RuntimeError:
        return
    shutil.rmtree(root, ignore_errors=True)
