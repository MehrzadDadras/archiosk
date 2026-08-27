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

WHAT IS NOT PERSISTED

The manifest and any in-flight bytes stay in the process-local StorageBridge.
That is a real limitation and is stated plainly rather than implied: a restart
loses the manifest, and the agent's next poll re-establishes it. Persisting the
manifest is a later, separate change - it belongs with the governed Source
record, through the existing Reconcile path, not in a second store invented here.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from services.storage_bridge import (
    DEFAULT_ENROLMENT_TTL_SECONDS,
    BridgeEnrolmentRevoked,
    StorageBridge,
)

# One bridge per project, for the life of this worker process. Deliberately not
# a cache with an eviction policy: it holds a manifest and, briefly, one
# payload, and losing it costs exactly one agent poll.
_BRIDGES: dict[str, StorageBridge] = {}


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


def bridge_for_token(raw_token: str, *, now: Optional[datetime] = None) -> StorageBridge:
    """The ONE route from a credential to a project's bridge.

    There is deliberately no companion that takes a project_id: an agent
    enrolled for one project cannot express a request for another, which is the
    same reasoning visible_cases_for records for Case privacy - the ability was
    removed rather than a check added.
    """
    enrolment = authorise_agent(raw_token, now=now)
    bridge = _BRIDGES.get(enrolment.project_id)
    if bridge is None:
        bridge = StorageBridge(enrolment.project_id)
        _BRIDGES[enrolment.project_id] = bridge
    return bridge


def note_agent_contact(enrolment, *, now: Optional[datetime] = None) -> None:
    """Record that the agent was heard from, for operator visibility only.

    Liveness for PROTOCOL purposes lives on the bridge; this column exists so a
    human can see when a NAS last checked in without reading process memory.
    """
    from models import db

    enrolment.last_seen_at = now or _now()
    db.session.commit()


def reset_bridges_for_testing() -> None:
    """Clear process-local bridge state between tests.

    Named for what it is. A test that inherits another test's manifest would
    pass for the wrong reason, and this module's state is process-global by
    design.
    """
    _BRIDGES.clear()
