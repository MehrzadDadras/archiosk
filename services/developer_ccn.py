"""Bounded Developer Mode Contemplated Change Notice context.

The first CCN slice deliberately uses the existing authenticated session as
the active context carrier and GovernanceLog as the durable lifecycle trace.
It is a developer conversation context, not project evidence and never an
authorization to mutate the application.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re
import uuid


CCN_STATUS_ACTIVE = "active"
CCN_STATUS_FINALIZED = "finalized"
CCN_STATUS_CANCELLED = "cancelled"

# Accept both the chat-friendly command forms `/CCN intent` and
# `/CCN: intent`, while keeping `/CCNfoo` ordinary text.
_COMMAND_RE = re.compile(r"^\s*/ccn(?:(?::\s*|\s+)(.*))?\s*$", re.IGNORECASE | re.DOTALL)
_SUBCOMMANDS = {"status", "show", "compare", "finalize", "cancel"}


def is_ccn_command(text: str) -> bool:
    return bool(_COMMAND_RE.match(text or ""))


def parse_ccn_command(text: str) -> tuple[str, str | None] | None:
    match = _COMMAND_RE.match(text or "")
    if not match:
        return None
    remainder = (match.group(1) or "").strip()
    lowered = remainder.lower()
    if lowered in _SUBCOMMANDS:
        return lowered, None
    return "start", remainder or None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _active(session) -> dict | None:
    ccn = session.get("developer_ccn")
    return ccn if isinstance(ccn, dict) and ccn.get("status") == CCN_STATUS_ACTIVE else None


def _summary(ccn: dict) -> str:
    selected = len(ccn.get("selected_elements") or [])
    return (
        f"{ccn.get('title') or 'Untitled CCN'} — {ccn.get('status')}; "
        f"{selected} selected application object(s)."
    )


def _log(governance_log, *, actor: str, event_type: str, ccn: dict, project_id: str | None = None, payload=None):
    if governance_log is None:
        return
    governance_log.append(
        project_id=project_id,
        event_type=event_type,
        actor=actor,
        role="admin",
        payload={"ccn_id": ccn["id"], "status": ccn.get("status"), **(payload or {})},
        correlation_id=ccn["id"],
    )


def handle_command(text: str, *, session, actor: str, governance_log=None, project_id: str | None = None) -> dict:
    """Handle one native /CCN command without invoking project intelligence."""
    parsed = parse_ccn_command(text)
    if parsed is None:
        raise ValueError("not a CCN command")
    command, argument = parsed
    ccn = _active(session)

    if command == "start":
        if ccn is None:
            title = argument or "Untitled Contemplated Change Notice"
            ccn = {
                "id": str(uuid.uuid4()),
                "title": title[:160],
                "intent": argument or "",
                "status": CCN_STATUS_ACTIVE,
                "created_by": actor,
                "created_at": _now(),
                "selected_elements": [],
                "assessments": [],
                "unresolved_questions": [],
                "final_disposition": None,
            }
            session["developer_ccn"] = ccn
            _log(governance_log, actor=actor, event_type="developer_ccn_created", ccn=ccn, project_id=project_id)
            return {"action_taken": "developer_ccn_started", "reply_text": f"CCN active: {ccn['title']}. Selection is context only; no change is authorized."}
        if argument:
            ccn["intent"] = argument
            ccn["title"] = argument[:160]
            session["developer_ccn"] = ccn
            _log(governance_log, actor=actor, event_type="developer_ccn_intent_updated", ccn=ccn, project_id=project_id)
            return {"action_taken": "developer_ccn_updated", "reply_text": f"CCN intent updated: {ccn['title']}. No change is authorized."}
        return {"action_taken": "developer_ccn_status", "reply_text": f"CCN already active: {_summary(ccn)}"}

    if ccn is None:
        return {"action_taken": "developer_ccn_unavailable", "reply_text": "No active CCN. Use /CCN to create a contemplated-change context."}

    if command in {"status", "show"}:
        return {"action_taken": "developer_ccn_status", "reply_text": f"CCN: {_summary(ccn)} Intent: {ccn.get('intent') or 'not stated'}. Selection remains non-authorizing context."}
    if command == "compare":
        return {"action_taken": "developer_ccn_compare", "reply_text": f"CCN comparison context: current ARCHIOSK state versus contemplated intent '{ccn.get('intent') or ccn.get('title')}'. No implementation has been authorized."}
    if command == "finalize":
        ccn["status"] = CCN_STATUS_FINALIZED
        ccn["final_disposition"] = "ready_for_review"
        ccn["finalized_at"] = _now()
        session["developer_ccn"] = ccn
        _log(governance_log, actor=actor, event_type="developer_ccn_finalized", ccn=ccn, project_id=project_id)
        return {"action_taken": "developer_ccn_finalized", "reply_text": "CCN finalized for review. This does not authorize implementation; use a later governed change instrument."}
    if command == "cancel":
        ccn["status"] = CCN_STATUS_CANCELLED
        ccn["cancelled_at"] = _now()
        session["developer_ccn"] = ccn
        _log(governance_log, actor=actor, event_type="developer_ccn_cancelled", ccn=ccn, project_id=project_id)
        return {"action_taken": "developer_ccn_cancelled", "reply_text": "CCN cancelled. No project or application mutation was performed."}
    raise ValueError(command)


def attach_selected_object(*, session, object_type: str, object_id: str, label: str, project_id: str | None = None, governance_log=None, actor: str = "admin") -> dict | None:
    ccn = _active(session)
    if ccn is None or not object_type or not object_id:
        return None
    element = {
        "object_type": object_type[:80],
        "object_id": object_id[:200],
        "label": (label or object_id)[:200],
        "project_id": project_id,
        "selected_at": _now(),
        "classification": "INVESTIGATE",
    }
    existing = [e for e in ccn.get("selected_elements", []) if not (e.get("object_type") == object_type and e.get("object_id") == object_id and e.get("project_id") == project_id)]
    ccn["selected_elements"] = existing + [element]
    session["developer_ccn"] = ccn
    _log(governance_log, actor=actor, event_type="developer_ccn_object_attached", ccn=ccn, project_id=project_id, payload={"object_type": element["object_type"], "object_id": element["object_id"]})
    return element


def context_for_project(
    session,
    project_id: str | None = None,
    *,
    template_identity: dict | None = None,
) -> dict | None:
    """Return the existing Developer/application context envelope.

    ``template_identity`` is an explicit server-resolved TPL object supplied
    by the caller's page route. It is application context only: it is kept
    alongside CCN/selection state and is never converted into project
    evidence. When no CCN or selection exists, a supplied TPL still gives a
    Developer turn a truthful page context rather than returning ``None``.
    """
    ccn = session.get("developer_ccn")
    if not isinstance(ccn, dict) and template_identity is None:
        return None
    if isinstance(ccn, dict):
        visible = [
            e for e in ccn.get("selected_elements", [])
            if not e.get("project_id") or e.get("project_id") == project_id
        ]
        context = {**ccn, "selected_elements": visible}
    else:
        context = {
            "scope": "application" if project_id is None else "project",
            "status": "template_context",
            "selected_elements": [],
        }
    if template_identity is not None:
        context["template_identity"] = dict(template_identity)
    return context
