"""GOPILOT CORE step 1 - the turn frame.

    credential -> envelope_set -> current_envelope -> context_ids

A turn's frame says WHO is asking, which authority envelopes that credential can
ever hold, which envelope the page places the turn in, and which governed
objects the page supplies as context. It is data. It decides nothing, grants
nothing and dispatches nothing: `resolve_go_scope` (app.py) still chooses the
Composer's endpoint, and every route's own gate is still the authority.

    Page location is context, never authority.
    Selection supplies context, never permission.

So `envelope_set` comes only from the credential (the session's role and the
Developer Mode overlay), and `current_envelope` only from the page's scope. The
two are never combined into a grant here; a later step checks an intent's
target envelope against `envelope_set`, never against the page.

The STAKEHOLDER_TOKEN envelope is named for completeness and is never produced
from a session: a pass token is a separate credential, resolved only by
services/project_rbac.authorize_token on its own endpoints.
"""
from __future__ import annotations

from typing import Optional

ENVELOPE_APPLICATION = "APPLICATION"
ENVELOPE_PROJECT = "PROJECT"
ENVELOPE_DOCUMENT_SOURCE = "DOCUMENT_SOURCE"
ENVELOPE_INVESTIGATION_STUDY = "INVESTIGATION_STUDY"
ENVELOPE_CUSTOMER_DOCUMENT_SHOP = "CUSTOMER_DOCUMENT_SHOP"
ENVELOPE_STAKEHOLDER_TOKEN = "STAKEHOLDER_TOKEN"
ENVELOPE_DEVELOPER_INSPECT = "DEVELOPER_INSPECT"

CREDENTIAL_SESSION = "session"
CREDENTIAL_ANONYMOUS = "anonymous"

_STAFF_ENVELOPES = frozenset({
    ENVELOPE_APPLICATION, ENVELOPE_PROJECT, ENVELOPE_DOCUMENT_SOURCE,
    ENVELOPE_INVESTIGATION_STUDY,
})
_CUSTOMER_ENVELOPES = frozenset({ENVELOPE_APPLICATION, ENVELOPE_CUSTOMER_DOCUMENT_SHOP})

# resolve_go_scope's scope kinds -> the envelope the page places a turn in.
_SCOPE_ENVELOPE = {
    "APPLICATION": ENVELOPE_APPLICATION,
    "PROJECT": ENVELOPE_PROJECT,
    "SOURCE": ENVELOPE_DOCUMENT_SOURCE,
    "DOCUMENT": ENVELOPE_DOCUMENT_SOURCE,
    "INVESTIGATION": ENVELOPE_INVESTIGATION_STUDY,
    "PLANNING_STUDY": ENVELOPE_INVESTIGATION_STUDY,
}

_CONTEXT_KEYS = ("project_id", "selected_source_id", "case_id", "run_id", "selection_form")


def envelope_set_for(*, authenticated: bool, customer: bool, developer: bool) -> frozenset:
    """What this credential could ever hold. Never widened by a page."""
    if not authenticated:
        return frozenset({ENVELOPE_APPLICATION})
    if customer:
        return _CUSTOMER_ENVELOPES
    if developer:
        return _STAFF_ENVELOPES | {ENVELOPE_DEVELOPER_INSPECT}
    return _STAFF_ENVELOPES


def build_turn_frame(scope_kind: str, *, developer_scope: bool = False,
                     context: Optional[dict] = None) -> dict:
    """The frame for a turn made from a page of `scope_kind`.

    Reads the credential from the existing identity owners (services.auth) and
    nothing else. `context` supplies ids only; ids are context, not authority.
    """
    from flask import session

    from services.auth import is_admin, is_authenticated, user_is_document_shop_customer

    authenticated = is_authenticated()
    customer = authenticated and user_is_document_shop_customer()
    developer = authenticated and is_admin() and bool(session.get("developer_mode"))
    envelope_set = envelope_set_for(authenticated=authenticated, customer=customer,
                                    developer=developer)

    if customer:
        current = (ENVELOPE_CUSTOMER_DOCUMENT_SHOP if scope_kind != "APPLICATION"
                   else ENVELOPE_APPLICATION)
    elif developer and developer_scope:
        current = ENVELOPE_DEVELOPER_INSPECT
    else:
        current = _SCOPE_ENVELOPE.get(scope_kind, ENVELOPE_APPLICATION)

    context = context or {}
    return {
        "credential": CREDENTIAL_SESSION if authenticated else CREDENTIAL_ANONYMOUS,
        "envelope_set": sorted(envelope_set),
        "current_envelope": current,
        "context_ids": {key: context.get(key) for key in _CONTEXT_KEYS if context.get(key)},
    }
