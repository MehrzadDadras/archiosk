"""
CLAUDE-P32 -- project-level access control: which authenticated accounts
may open a given project at all. Answers a question no existing
mechanism answered: `services.case_workspace.CaseWorkspaceStore.
visible_cases_for` governs Case-level privacy *within* a project a user
already reached; `services.auth`'s login_required/admin_required governs
whether a session is authenticated at all and what role it has. Neither
ever asked "may THIS account open THIS project."

Honesty boundary, matching every other module in this repository's
CLAUDE-P29/P30/P31 sequence: this is project-level access control
within ONE deployment, not multi-organization tenancy. There is still
no `Organization` concept anywhere in this codebase (see
`governance/specified-unbuilt/tenancy-and-project-authorization.md`,
still unimplemented) -- an "owner" here is a real `models.User.username`
value, nothing more. See `services/security_policy.py`'s
`SECURITY_CLAIMS_REGISTRY` for the claim this module may and may not
support.

Deliberately NOT imported by `services/case_workspace.py` itself (which
does not import `models`, preserving its existing framework-decoupling
-- see `CaseWorkspaceStore.archive_case`'s own docstring for the
established precedent of taking authority facts as plain
caller-supplied values instead). This module sits one layer above it,
free to import `models.User` for the one thing that actually needs
real identity verification: backfill inference for legacy projects.
"""
from __future__ import annotations

from typing import Optional


def can_access_project(workspace, username: Optional[str], is_admin: bool) -> bool:
    """
    The one centralized decision every route-layer loader below calls
    into. `workspace.owner is None` (not yet established -- a legacy
    project, or a brand-new one somehow reached before creation
    finished) fails CLOSED: only an admin may access it, never "anyone,"
    the deliberate opposite of every other None-means-ungated field in
    this codebase (services.environment_capabilities.
    allowed_participant_roles, services.security_policy.
    capability_availability) -- those default open because there was a
    real pre-existing behavior to preserve; this one has no such
    precedent to preserve, since no project-level access check existed
    before this module.
    """
    if is_admin:
        return True
    if workspace is None or not username:
        return False
    if workspace.owner == username:
        return True
    return username in workspace.access_allow_list


def infer_owner_from_ingestion_actor(project_id: str, governance_log, known_usernames: set) -> Optional[str]:
    """
    Deterministic-only backfill inference for a legacy project (one
    ingested before this module existed, so `workspace.owner` is still
    `None`): a project's own first `document_ingested` governance
    event's `actor` field is checked for an EXACT match against a real
    `models.User.username` -- never a fuzzy/best-effort guess. Most
    `actor` values in this codebase are free text with no real identity
    behind them at all (services/governance.py's own docstring: "No real
    authentication backs actor/role -- they're free-text fields recorded
    as given, not verified identity") -- confirmed directly against this
    repository's own local project data, where three of six existing
    projects have an `actor` of "agent1"/"agent2"/a human's free-typed
    display name, none of which correspond to a real account. Those stay
    unowned (admin-only) rather than being silently assigned to a
    plausible-looking but unverified string.
    """
    events = governance_log.read(project_id)
    ingest_event = next((e for e in events if e.event_type == "document_ingested"), None)
    if ingest_event is None:
        return None
    return ingest_event.actor if ingest_event.actor in known_usernames else None


def ensure_owner_backfilled(store, workspace, governance_log, known_usernames: set) -> None:
    """
    Idempotent: once `workspace.owner` is set (by this function or the
    normal admin-assignment route), never touched again by this
    function. A GET request causing this incidental governed write
    mirrors `routes/workspace.py`'s own pre-existing `open_project`
    precedent inside `show_workspace` (temporal reconciliation), not a
    new pattern introduced here.
    """
    if workspace.owner is not None:
        return
    inferred = infer_owner_from_ingestion_actor(workspace.project_id, governance_log, known_usernames)
    if inferred is not None:
        store.set_project_owner(
            workspace, owner=inferred, actor="system",
            source="inferred_from_ingestion_actor", governance_log=governance_log,
        )


def known_usernames() -> set:
    """The only place this module reaches into `models.User` -- kept as
    its own function so every call site shares one query shape rather
    than each re-deriving `{u.username for u in User.query.all()}`."""
    from models import User

    return {u.username for u in User.query.all()}


def load_authorized_project_or_none(store, registry, governance_log, project_id: str, username: Optional[str], is_admin: bool):
    """
    The single centralized routine every blueprint's own thin loader
    wraps (Part "Architecture Boundary": one centralized authorization
    decision, thin call-site enforcement). Returns `(document, workspace)`
    if the project exists AND `username`/`is_admin` may access it, else
    `None` -- callers translate `None` into whatever 404/redirect shape
    their own blueprint uses (an HTML redirect vs. a JSON 404 body), but
    the actual "may they see it" decision is made exactly once, here.
    """
    document = registry.get(project_id)
    if document is None:
        return None

    # CLAUDE-P37: a corrupted legacy workspace file must read as "not
    # accessible" (None), the same as a genuinely nonexistent or
    # unauthorized project -- not an uncaught TypeError. This is the
    # shared routine routes/api.py's whole blueprint calls through
    # _load_authorized_project_or_404, so leaving this unguarded exposed
    # every JSON API route to the same already-diagnosed defect class
    # routes/workspace.py's own loader, app.py's nav sidebar, routes/
    # portal.py's document listing, routes/security.py's department
    # home, and services/security_assurance.py's self-check were all
    # separately hardened against.
    try:
        workspace = store.get_or_create(project_id)
    except TypeError:
        return None
    ensure_owner_backfilled(store, workspace, governance_log, known_usernames())
    if not can_access_project(workspace, username, is_admin):
        return None
    return document, workspace
