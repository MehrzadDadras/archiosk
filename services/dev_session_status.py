"""
CLAUDE-CA1D-LIVE-BRIDGE-01 -- read side of the read-only Claude/agent
session-state bridge (tools/write_dev_session_status.py is the write
side; .claude/settings.json wires the harness's own hooks to it).

Observation only. Nothing in this module -- or anywhere reachable from
it -- writes back to the status file or to the Claude Code session in
any way. That is a deliberate architectural boundary, not an omission:
this stage's own Plan-Mode report designed observation and control as
two different, separately-governed things, and this module implements
only the first.

Content-free by construction: `DevSessionStatus` has no free-text field
at all -- the same discipline services/diagnostics.py's own
TechnicalTelemetry already established for this codebase. `state` is
always one of the three vocabulary values a live hook-payload experiment
actually confirmed (see the Plan-Mode report's SS7) -- this module never
invents a fourth.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

STATE_ACTIVE = "active"
STATE_WAITING_FOR_INPUT = "waiting_for_input"
STATE_UNKNOWN = "unknown"
_VALID_STATES = frozenset({STATE_ACTIVE, STATE_WAITING_FOR_INPUT, STATE_UNKNOWN})


@dataclass
class DevSessionStatus:
    """Every field here is a closed/structural value. There is
    deliberately no field capable of holding conversational content --
    tool_input/prompt/assistant-message text/notification text are never
    read by the write side in the first place (see
    tools/write_dev_session_status.py's own docstring), so there is
    nothing of that kind for this dataclass to expose even if it wanted
    to."""

    state: str
    last_structural_event: Optional[str]
    updated_at: Optional[str]
    session_id: Optional[str]
    pid: Optional[int]


def _pid_is_alive(pid: int) -> bool:
    """Mirrors routes/portal.py's own _pid_is_alive exactly (same
    OpenProcess-on-Windows / os.kill(pid, 0)-on-POSIX idiom, including
    its own documented reasoning: Windows has no reliable os.kill(pid, 0)
    equivalent). Not imported from routes/portal.py -- services/ does not
    depend on routes/ anywhere else in this codebase (the same layering
    services/project_access.py's own docstring already establishes for
    the reverse direction), so the small function is mirrored here
    rather than crossing that boundary for one helper."""
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _default_status_path() -> Path:
    from config import BASE_DIR

    return BASE_DIR / "instance" / "dev_session_status.json"


def read_dev_session_status(path: Optional[Path] = None) -> DevSessionStatus:
    """Never raises. Degrades to STATE_UNKNOWN -- never a guessed richer
    state -- whenever the evidence doesn't actually support more: file
    missing, unreadable, not valid JSON, not a JSON object, an
    unrecognized `state` value, a non-integer `pid`, or a `pid` that no
    longer belongs to a live process (the process that last wrote this
    status is gone, so whatever it last claimed is no longer current)."""
    status_path = path or _default_status_path()

    def _unknown(data: Optional[dict] = None) -> DevSessionStatus:
        data = data or {}
        last_event = data.get("last_structural_event")
        updated_at = data.get("updated_at")
        session_id = data.get("session_id")
        pid_raw = data.get("pid")
        return DevSessionStatus(
            state=STATE_UNKNOWN,
            last_structural_event=last_event if isinstance(last_event, str) else None,
            updated_at=updated_at if isinstance(updated_at, str) else None,
            session_id=session_id if isinstance(session_id, str) else None,
            pid=pid_raw if isinstance(pid_raw, int) else None,
        )

    try:
        raw = status_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return _unknown()

    if not isinstance(data, dict):
        return _unknown()

    state = data.get("state")
    pid_raw = data.get("pid")
    pid: Optional[int] = pid_raw if isinstance(pid_raw, int) else None

    if state not in _VALID_STATES:
        return _unknown(data)

    if pid is None:
        # No verifiable liveness -- can't confirm the writer is still
        # the current session, so this record's currency is unknown.
        return _unknown(data)

    if not _pid_is_alive(pid):
        return _unknown(data)

    last_event = data.get("last_structural_event")
    updated_at = data.get("updated_at")
    session_id = data.get("session_id")

    return DevSessionStatus(
        state=state,
        last_structural_event=last_event if isinstance(last_event, str) else None,
        updated_at=updated_at if isinstance(updated_at, str) else None,
        session_id=session_id if isinstance(session_id, str) else None,
        pid=pid,
    )
