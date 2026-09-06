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

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_HUMAN_AUTHORED,
    OBSERVATION_AUTHOR_HUMAN,
    ProjectWorkspace,
)

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


# --- Authoring (reviewer-facing) -------------------------------------------
# CLAUDE-HELP-AUTHORING-01. Everything below composes existing primitives:
# a Case to hold the work, an InvestigationStep to hold the question verbatim,
# a WorkProduct(artifact_type="script") with ordered WorkProductSections citing
# Claims. No Help-content object family was created, because none is needed -
# the kernel already has every part, and a parallel family would need its own
# provenance, versioning and staleness rules to be reinvented and kept in step.

HELP_AUTHORING_CASE_TITLE = "Help Library"


def _help_authoring_case(store: CaseWorkspaceStore, workspace: ProjectWorkspace) -> dict:
    """One Case holding Help authoring work, created on first use.

    A Case is required because InvestigationStep is Case-scoped, and the step is
    what carries the originating question verbatim. One shared Case rather than
    one per Script: these are all the same body of work, and a Case per question
    would multiply containers without separating anything.
    """
    for case in workspace.cases:
        if case.get("title") == HELP_AUTHORING_CASE_TITLE:
            return case
    return store.create_case(
        workspace, title=HELP_AUTHORING_CASE_TITLE,
        objective="Author and maintain governed Help Scripts.", created_by="help-authoring",
    )


def create_help_script(
    store: CaseWorkspaceStore, question: str, title: str, actor: str,
    anchor_evidence_id: Optional[str] = None,
) -> dict:
    """Create a DRAFT Help Script for one question.

    Persists content and nothing else. No model call is made here: Save is not
    a model checkpoint, Re-check is. That is the smallest behaviour consistent
    with the trust chain, and it is what makes "no continuous model calls" true
    by construction rather than by restraint.
    """
    question = (question or "").strip()
    title = (title or "").strip()
    if not question:
        raise HelpModeError("A Help Script needs the question it answers.")
    if not title:
        raise HelpModeError("A Help Script needs a title.")

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    case = _help_authoring_case(store, workspace)

    anchor = ({"object_type": "evidence_item", "object_id": anchor_evidence_id}
              if anchor_evidence_id else {"object_type": "case", "object_id": case["id"]})
    step = store.record_investigation_step(
        workspace, case_id=case["id"], step_kind="help_authoring",
        anchor=anchor, question=question, triggered_by_actor=actor,
    )
    script = store.create_work_product(
        workspace, artifact_type="script", title=title, created_by=actor,
        case_id=case["id"], source_investigation_step_id=step["id"],
    )
    return script


def add_help_claim(
    store: CaseWorkspaceStore, script_id: str, statement: str, actor: str,
    evidence_item_ids: Optional[list[str]] = None,
) -> dict:
    """Record a Claim answering THIS Script's question, against THIS Script's step.

    The missing half of authoring, and the structural readiness check is what
    surfaced it: `question_fit` requires a Script to cite a Claim produced by
    its OWN originating question, which is precisely the guard that catches a
    Script assembled from some other question's claims. A reviewer authoring a
    new Help answer therefore needs to record the claim under the question it
    answers - not borrow one recorded against a different investigation.

    That is also the honest reading. "Survival Mode is a lens, not a third kind
    of Spin" IS the answer to "what is Survival Mode, and is it another kind of
    Spin?", so recording it against that question's step says something true
    rather than convenient.

    Claims start `proposed` like every other claim in this kernel - authoring
    one is not adopting it, and REUSABLE still waits for a human to do that
    separately.
    """
    statement = (statement or "").strip()
    if not statement:
        raise HelpModeError("A claim needs a statement.")

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    script = store._find(workspace.work_products, script_id)
    if script is None or script.get("artifact_type") != "script":
        raise HelpModeError("No Help Script %s." % script_id)
    step_id = script.get("source_investigation_step_id")
    if not step_id:
        raise HelpModeError("This Help Script has no originating question to attach a claim to.")

    return store.record_investigation_claim(
        workspace, investigation_step_id=step_id, statement=statement,
        claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
        method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
        confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
        author_type=OBSERVATION_AUTHOR_HUMAN, created_by=actor,
        evidence_links=[{"object_type": "evidence_item", "object_id": eid}
                        for eid in (evidence_item_ids or []) if eid],
    )


def add_help_script_scene(
    store: CaseWorkspaceStore, script_id: str, text: str, actor: str,
    claim_ids: Optional[list[str]] = None, content_class: str = CONTENT_CLASS_HUMAN_AUTHORED,
) -> dict:
    """Append one narrative unit, citing the Claims it rests on.

    Citations are validated by the kernel against really-persisted Claims in
    this workspace, so a Help Script cannot cite something that does not exist -
    the same no-laundering guarantee project work products already have.
    """
    if not (text or "").strip():
        raise HelpModeError("A narrative unit needs text.")
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    links = [{"object_type": "claim", "object_id": cid} for cid in (claim_ids or []) if cid]
    return store.add_work_product_section(
        workspace, work_product_id=script_id, section_type="scene",
        content={"text": text.strip()}, content_class=content_class,
        author=actor, evidence_links=links,
    )


def list_help_scripts(store: CaseWorkspaceStore) -> list[dict]:
    """Every Help Script with its derived readiness - never a stored status."""
    from services.script_fit import help_status_for

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    rows = []
    for script in workspace.work_products:
        if script.get("artifact_type") != "script":
            continue
        readiness = store.resolve_script_readiness(workspace, script["id"])
        status = help_status_for(readiness)
        rows.append({
            "id": script["id"],
            "title": script.get("title"),
            "question": readiness.get("question"),
            "readiness": readiness["readiness"],
            "status": status["status"],
            "label": status["label"],
        })
    return rows


def help_script_detail(store: CaseWorkspaceStore, script_id: str) -> Optional[dict]:
    """Everything a reviewer needs to judge one Script, and nothing a reader does.

    Includes which recorded verdicts still APPLY versus which have gone stale -
    a reviewer looking at an edited Script needs to know the difference between
    "checked and fine" and "checked, then changed", and the readiness value
    alone cannot say which.
    """
    from services.script_fit import help_status_for

    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    script = store._find(workspace.work_products, script_id)
    if script is None or script.get("artifact_type") != "script":
        return None

    readiness = store.resolve_script_readiness(workspace, script_id)
    applicable_fit = store._applicable_script_record(script, "script_fit_verdicts")
    applicable_consistency = store._applicable_script_record(script, "script_consistency_verdicts")
    applicable_validation = store._applicable_script_record(script, "script_validations")

    scenes = sorted(
        (s for s in script.get("sections", []) if not s.get("removed")),
        key=lambda s: s.get("order_index", 0),
    )
    return {
        "id": script_id,
        "title": script.get("title"),
        "question": readiness.get("question"),
        "state": script.get("state"),
        "scenes": [{
            "id": s["id"],
            "order_index": s.get("order_index"),
            "section_type": s.get("section_type"),
            "text": s.get("content", {}).get("text"),
            "content_class": s.get("content_class"),
            "claim_ids": [l["object_id"] for l in s.get("evidence_links", [])
                          if l.get("object_type") == "claim"],
        } for s in scenes],
        "readiness": readiness["readiness"],
        "checks": readiness["checks"],
        "reasons": readiness["reasons"],
        "status": help_status_for(readiness),
        "verdicts": {
            "question_fit": applicable_fit,
            "evidence_consistency": applicable_consistency,
            "validation": applicable_validation,
        },
        "stale": {
            "question_fit": applicable_fit is None and bool(script.get("script_fit_verdicts")),
            "evidence_consistency": (applicable_consistency is None
                                     and bool(script.get("script_consistency_verdicts"))),
            "validation": (applicable_validation is None
                           and bool(script.get("script_validations"))),
        },
        # Only claims recorded against THIS Script's own question. Offering
        # another question's claims would invite a Script that fails
        # question_fit for a reason the reviewer could not see from here.
        "available_claims": [
            {"id": c["id"], "statement": c.get("statement"),
             "claim_class": c.get("claim_class"), "adoption_state": c.get("adoption_state")}
            for c in workspace.claims
            if c.get("investigation_step_id") == script.get("source_investigation_step_id")
        ],
        "available_evidence": [
            {"id": e["id"], "excerpt": str(e.get("content", ""))[:160]}
            for e in workspace.evidence_items
        ],
    }
