"""
Append-only governance/audit-trail log for project state changes.

Adapted from an external "Phase 1 constitutional guardrails" proposal into
this app's real Python/Flask/flat-JSON-file stack -- there's no
TypeScript/IndexedDB frontend here, so the log lives alongside the existing
RequirementsRegistry as one JSON Lines file per project.

Honesty note: this app has no authentication system. `actor`/`role` are
free-text fields supplied by the caller and recorded as given -- this is a
presence check (something was provided), not real authorization or
identity verification. Treat entries as a labeled audit trail, not as
cryptographic proof of who actually took an action.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class GovernanceError(Exception):
    """Raised when an event is missing a field governance requires."""


@dataclass
class GovernanceEvent:
    id: str
    project_id: str
    event_type: str
    actor: str
    role: str
    payload: dict[str, Any]
    predecessor_id: Optional[str]
    created_at: str


class GovernanceLog:
    """
    One append-only .jsonl file per project. A correction never edits or
    removes a prior line -- it's recorded as a new event whose
    `predecessor_id` points back at the event being corrected. There is
    deliberately no update()/delete(): the only write operation this class
    exposes is append(), and it always opens the file in append mode, so a
    bug here can't silently rewrite or drop history the way a
    read-modify-rewrite-the-whole-file approach could.
    """

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)

    def append(
        self,
        project_id: str,
        event_type: str,
        actor: str,
        role: str,
        payload: dict[str, Any] | None = None,
        predecessor_id: str | None = None,
    ) -> GovernanceEvent:
        if not actor or not actor.strip():
            raise GovernanceError("An actor is required to record a governance event.")
        if not role or not role.strip():
            raise GovernanceError("A role is required to record a governance event.")

        event = GovernanceEvent(
            id=str(uuid.uuid4()),
            project_id=project_id,
            event_type=event_type,
            actor=actor.strip(),
            role=role.strip(),
            payload=payload or {},
            predecessor_id=predecessor_id,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with self._path_for(project_id).open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(event)) + "\n")

        return event

    def read(self, project_id: str) -> list[GovernanceEvent]:
        """All events for a project, in append (chronological) order."""
        path = self._path_for(project_id)
        if not path.exists():
            return []

        events = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    events.append(GovernanceEvent(**json.loads(line)))
        return events

    def _path_for(self, project_id: str) -> Path:
        return self.store_path / f"{project_id}.governance.jsonl"
