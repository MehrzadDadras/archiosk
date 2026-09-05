"""
Help / Learning Mode — learning the application, without touching the project.

A user in Help is learning how ARCHIOSK works. That conversation must not
contaminate the project they happen to have open: not its evidence, claims,
decisions, WorkProducts, conversation, memory, or provenance.

WHY THIS NEEDS ALMOST NO NEW ARCHITECTURE

The strongest isolation guarantee in this codebase already exists and is
constitutional: **project boundaries are strict** (`constitutional-invariants.md`
#8), a `ProjectWorkspace` is exactly one project, conversation already lives in
`ProjectWorkspace.project_conversation`, and `_resolve_mm6_endpoint` already
refuses any object whose `project_id` does not match. So Help Mode is not a
second conversation platform - it is a conversation held in a workspace that is
not the user's project. Every protection the kernel already enforces between two
customer projects applies unchanged between Help and a project, because to the
kernel that is all this is.

TWO RESERVED NAMESPACES, BOTH ORDINARY WORKSPACES

    archiosk-help-library            authored Help Scripts. Shared, admin-authored,
                                     the thing readers consume.
    archiosk-help-session-<user>     one user's Help conversation. Private by the
                                     same mechanism that keeps two customers apart.

Per-user rather than one shared Help workspace, deliberately: readers asking
questions must not accumulate in the authoring library, and one reader's
questions are not another's to read. Making the session a workspace gets that
privacy from project isolation rather than from a new permission check that
would have to be remembered at every call site.

WHAT HELP MAY KNOW

`HelpContext` carries the page, the control being looked at, the application
version, and the user's role. It has no field for a project id, a source, a
claim, or a case - **the boundary is the dataclass**, not a rule someone applies
when populating it. A caller cannot accidentally pass project evidence into Help
because there is nowhere in the structure to put it.

WHAT HELP MAY NEVER DO

Nothing said or generated here becomes project evidence, a claim, a decision,
project memory, a WorkProduct, or a task. Not by default and not by
configuration: this module writes to the Help session workspace and nowhere
else, and it holds no reference to a project workspace to write to.

THE TRANSITION IS THE USER'S, ALWAYS

When a question turns project-specific - "how does Survival Mode apply to THIS
project's smoke-control review?" - Help does not quietly reach for the project.
It offers to continue in Project Mode. `propose_project_transition` returns an
offer; accepting it is a separate act by the user in the project's own
conversation, where project context legitimately applies. Nothing is carried
across automatically, because carrying it across silently is exactly the
contamination this module exists to prevent.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Optional

from services.case_workspace import CaseWorkspaceStore, ProjectWorkspace

# The authored Help Scripts readers consume. Shared and admin-authored.
HELP_LIBRARY_PROJECT_ID = "archiosk-help-library"

# One Help conversation per user, isolated by the same mechanism that isolates
# two customer projects from each other.
HELP_SESSION_PREFIX = "archiosk-help-session-"

HELP_SCOPE = "help"

# Anything a caller might be tempted to hand Help "just for context". Named so
# the refusal can be specific rather than a silent drop - a caller passing
# project evidence into Help has misunderstood something, and should be told.
_FORBIDDEN_CONTEXT_KEYS = (
    "project_id", "source_id", "claim_id", "case_id", "evidence", "evidence_links",
    "work_product_id", "finding_id", "requirement_id", "conversation", "memory",
)


class HelpModeError(Exception):
    """A Help interaction tried to reach something outside Help."""


@dataclass
class HelpContext:
    """What Help is allowed to know about where the user is standing.

    Application-shaped, never project-shaped. There is deliberately no field
    for a project, a source, a claim or a case: the boundary is enforced by the
    structure rather than by remembering not to populate it.

    `role` is included because an explanation legitimately differs for an admin
    and a field user; it is a fact about the person, not about the project.
    """

    page: Optional[str] = None
    control: Optional[str] = None
    app_version: Optional[str] = None
    role: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}


def help_session_project_id(username: str) -> str:
    """The reserved workspace id holding one user's Help conversation."""
    if not (username or "").strip():
        raise HelpModeError("A Help conversation needs to belong to someone.")
    safe = "".join(c for c in username.strip().lower() if c.isalnum() or c in "-_.")
    if not safe:
        raise HelpModeError("Username %r has no characters usable in a workspace id." % username)
    return HELP_SESSION_PREFIX + safe


def is_help_workspace(project_id: str) -> bool:
    """True for the Help library and any Help session workspace.

    Used to keep Help workspaces out of project listings and to refuse
    project-shaped operations against them.
    """
    return project_id == HELP_LIBRARY_PROJECT_ID or str(project_id).startswith(HELP_SESSION_PREFIX)


def assert_context_is_help_shaped(context: dict) -> dict:
    """Refuse a context carrying project material, loudly.

    Silently dropping the key would be worse: the caller would keep believing
    Help had been given project context, and the next person to read the code
    would have to guess whether that was intended.
    """
    offending = sorted(k for k in (context or {}) if k in _FORBIDDEN_CONTEXT_KEYS)
    if offending:
        raise HelpModeError(
            "Help context may not carry project material (%s). Help explains the "
            "application; a project-specific question needs an explicit transition "
            "to Project Mode." % ", ".join(offending)
        )
    return context or {}


def record_help_message(
    store: CaseWorkspaceStore,
    username: str,
    author: str,
    body: str,
    context: Optional[HelpContext] = None,
) -> dict:
    """Append one message to this user's Help conversation.

    Writes to the Help session workspace and nowhere else. This function is
    given no project workspace, so there is no path from a Help message to a
    project record - the same structural argument the assessment functions use.
    """
    if not (body or "").strip():
        raise HelpModeError("A Help message needs a body.")

    payload = assert_context_is_help_shaped(context.to_dict() if context else {})
    workspace = store.get_or_create(help_session_project_id(username))
    message = {
        "id": _new_message_id(),
        "author": author,
        "body": body,
        "scope": HELP_SCOPE,
        "help_context": payload,
        "created_at": _timestamp(),
    }
    workspace.project_conversation.append(message)
    store.save(workspace)
    return message


def read_help_conversation(store: CaseWorkspaceStore, username: str) -> list[dict]:
    """This user's Help history. Never anyone else's, never a project's."""
    workspace = store.get_or_create(help_session_project_id(username))
    return list(workspace.project_conversation)


def propose_project_transition(question: str, project_id: Optional[str]) -> dict:
    """The offer, when a Help question turns project-specific.

    Returns an offer and carries nothing. Accepting it is a separate act by the
    user, in the project's own conversation, where project context legitimately
    applies. Nothing from the Help conversation is transferred by this call, and
    nothing is transferred by accepting it either - the user re-asks in a place
    where the answer may use project evidence.

    `transferred` is always an empty list, and is returned rather than omitted
    so a caller reading this response cannot mistake silence for "nothing to
    report" when it means "nothing moved, by design".
    """
    return {
        "offer": "Continue this in Project Mode?",
        "question": question,
        "project_id": project_id,
        "transferred": [],
        "reason": (
            "Help explains the application and does not read project evidence. "
            "Continuing in Project Mode answers the same question with this "
            "project's own evidence, in the project's own record."
        ),
    }


def _new_message_id() -> str:
    import uuid

    return uuid.uuid4().hex


def _timestamp() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
