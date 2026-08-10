"""
CLAUDE-CA1D-LIVE-BRIDGE-01 -- write side of the read-only Claude/agent
session-state bridge. Observation only; there is no reverse channel
anywhere in this file or invoked by it -- see this stage's own Plan-Mode
report for why that boundary is deliberate, not an oversight.

Invoked once per confirmed hook event by .claude/settings.json (never a
background/daemon process -- one short-lived invocation per event, exits
immediately, matching this repo's own "no background worker/task-queue
infrastructure" constraint, tools/dependency_fit.py). stdlib-only,
deliberately: no repo import (config.py pulls in python-dotenv, a
non-stdlib dependency, so BASE_DIR is recomputed here rather than
imported -- the same tools/backup_data.py convention, minus that one
import).

Structurally content-free by construction, not by redaction: this script
never parses hook stdin at all (the harness's own hook payload carries
tool_input/prompt/last_assistant_message/notification text -- none of it
is ever read into a Python value here, so there is nothing to redact).
session_id/pid come from the process environment (CLAUDE_CODE_SESSION_ID/
CLAUDE_PID), already scoped to just this session -- confirmed real via
this stage's own live hook-payload experiment (Plan-Mode report, SS7).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent
STATUS_PATH = BASE_DIR / "instance" / "dev_session_status.json"

SCHEMA_VERSION = 1

STATE_ACTIVE = "active"
STATE_WAITING_FOR_INPUT = "waiting_for_input"

# Evidence-confirmed vocabulary only (Plan-Mode report SS7) -- "ended" and
# "blocked" are not mapped here at all, deliberately: real events (Session
# End/PermissionRequest) were never independently observed firing this
# stage, so this bridge makes no claim about them rather than guessing.
_ACTIVE_EVENTS = frozenset({
    "UserPromptSubmit", "PreToolUse", "PostToolUse", "PostToolUseFailure",
    "SubagentStart",
})
_WAITING_EVENTS = frozenset({"Stop", "Notification"})
# SubagentStop is deliberately in NEITHER set -- see resolve_state()'s own
# docstring for why forcing it either way would be evidence-contradicting,
# not merely simplifying.


def resolve_state(event_name: str, read_prior_state) -> Optional[str]:
    """Pure event-to-state mapping. `read_prior_state` is a zero-arg
    callable returning the previously-persisted state (or STATE_ACTIVE if
    none is available) -- injected rather than read directly here so this
    function stays trivially testable against synthetic prior states.

    Returns None for any event outside the confirmed vocabulary (the
    caller does nothing in that case -- never guesses a state for an
    event this bridge hasn't earned evidence for).

    SubagentStop is the one event that must NOT unconditionally set
    `active` or `waiting_for_input`: this stage's own live experiment
    caught a real background SubagentStop firing three minutes into an
    otherwise-idle period (Plan-Mode report SS7) -- treating it as
    "active" would have falsely un-idled a session that was genuinely
    just waiting for the next prompt. It also must not assume
    `waiting_for_input`, since a subagent finishing mid-turn (the
    ordinary case) does not mean the parent turn just ended -- only a
    real `Stop` means that. So it carries the existing state forward
    unchanged, which is also exactly what "an unmatched SubagentStop
    must not corrupt the status model" requires: with no prior state
    available at all (e.g. the very first event this bridge ever sees is
    an orphaned SubagentStop), the safe assumption is `active` -- SOME
    session activity is evidently underway even if this bridge missed
    how it started."""
    if event_name in _ACTIVE_EVENTS:
        return STATE_ACTIVE
    if event_name in _WAITING_EVENTS:
        return STATE_WAITING_FOR_INPUT
    if event_name == "SubagentStop":
        return read_prior_state()
    return None


def read_prior_state_from_file(path: Path) -> str:
    """Best-effort read of just the `state` field -- the only thing
    SubagentStop's mapping needs from a previous write. Never raises;
    any problem (missing file, malformed JSON, unrecognized value) falls
    back to STATE_ACTIVE, the same safe default resolve_state()'s own
    docstring names for a prior-state-unavailable SubagentStop."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        state = data.get("state")
        if state in (STATE_ACTIVE, STATE_WAITING_FOR_INPUT, "unknown"):
            return state
    except Exception:
        pass
    return STATE_ACTIVE


def build_payload(event_name: str, state: str, session_id: Optional[str], pid: Optional[int], now: Optional[str] = None) -> dict:
    """The complete, whitelisted schema -- five fields, nothing else.
    Every value here is either a closed enum, an opaque identifier
    (session_id/pid), or a timestamp -- never conversational content.
    Deliberately NOT including a process-start-time field: routes/
    portal.py's own _pid_is_alive precedent (the idiom this bridge's read
    side reuses) is a plain PID-liveness check with no PID-reuse
    cross-check either, so matching that established precedent was
    chosen over adding a field nothing else in this codebase uses."""
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "pid": pid,
        "state": state,
        "last_structural_event": event_name,
        "updated_at": now or datetime.now(timezone.utc).isoformat(),
    }


def atomic_write(path: Path, payload: dict) -> None:
    """Temp-file-then-os.replace -- a concurrent reader never observes a
    partially-written file. Does not attempt cross-process locking for
    read-modify-write races between two near-simultaneous hook
    invocations (e.g. a genuinely parallel subagent) -- a disclosed,
    accepted limitation for observational telemetry, not a correctness
    guarantee this bridge makes; see the Plan-Mode report's own
    completion note."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".dev_session_status.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(0)
    event_name = sys.argv[1]

    # Drain stdin without ever parsing it. The harness's own hook payload
    # (tool_input/prompt/last_assistant_message/notification text) may be
    # sitting here -- this script has no code path that turns any of it
    # into a Python value, let alone persists it. Draining (not just
    # ignoring) avoids leaving the harness's own writer blocked on a full
    # pipe if it's watching for the reader to consume its output.
    try:
        if not sys.stdin.isatty():
            sys.stdin.read()
    except Exception:
        pass

    state = resolve_state(event_name, lambda: read_prior_state_from_file(STATUS_PATH))
    if state is None:
        sys.exit(0)  # outside the confirmed vocabulary -- do nothing

    session_id = os.environ.get("CLAUDE_CODE_SESSION_ID")
    pid_raw = os.environ.get("CLAUDE_PID")
    try:
        pid = int(pid_raw) if pid_raw else None
    except ValueError:
        pid = None

    payload = build_payload(event_name, state, session_id, pid)
    try:
        atomic_write(STATUS_PATH, payload)
    except Exception:
        pass  # a telemetry write must never fail the harness's own hook dispatch
    sys.exit(0)


if __name__ == "__main__":
    main()
