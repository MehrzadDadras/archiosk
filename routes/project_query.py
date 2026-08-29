"""CLAUDE-TRIAL-SAFE-LANDING-01 — the one route that spends trial allowance.

WHY THE GATE LIVES HERE AND NOT INSIDE THE VIEWER

The safe landing message promises that running out of fuel still lets you get
home. That promise is kept structurally rather than by discipline: this is the
ONLY route that consults `services/trial_allowance.py`, and it is not the route
that serves sheets, lists them, reports friction, or escalates to a human. Those
live in `routes/project_assets.py` and `routes/project_entry.py` and do not
import the meter at all — so no quota state can make a drawing stop opening,
because there is no code path through which it could.

THE ORDER OF OPERATIONS IS THE FEATURE

    admission -> model call -> append

`consume_query` is asked BEFORE the model runs and its answer decides whether
the model runs at all. When the answer is FINAL, the model still runs and the
response is delivered COMPLETE, with the courtesy message appended after it.
Cutting somebody off mid-thought is the exact failure this exists to prevent,
so the query that crosses the line is the one that gets answered properly.

When the answer is EXHAUSTED, `_invoke_model` is never reached. A test asserts
that with a spy rather than trusting the branch, because "we do not call the
API any more" is a claim about a cost and a data boundary, not a preference.
"""
from __future__ import annotations

from flask import Blueprint, Response, current_app, jsonify, request

from services.project_rbac import (
    ProjectAccessRefused,
    authorize_token,
    discipline_for_sheet,
    may_read_discipline,
    note_token_use,
    scope_ai_context,
)
from services.trial_allowance import (
    STATE_EXHAUSTED,
    apply_to_answer,
    byok_key_present,
    consume_query,
    safe_landing_payload,
    usage,
)

project_query_bp = Blueprint("project_query", __name__)

_REFUSED_BODY = "Not authorised.\n"


def _refuse() -> Response:
    return Response(_REFUSED_BODY, status=403, mimetype="text/plain")


def _workspace(project_id: str):
    from services.case_workspace import CaseWorkspaceStore

    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return store.get_or_create(project_id)


def _invoke_model(question: str, context: list) -> str:
    """The outbound call. Replaced wholesale in tests by a spy.

    Deliberately the narrowest possible function: everything about admission,
    scoping and the safe landing happens outside it, so a test can assert the
    model was NOT reached without stubbing the surrounding logic too.
    """
    from services.llm_gateway import call_llm_json

    marks = ", ".join(sheet.get("sheet_id", "") for sheet in context) or "none"
    result = call_llm_json(
        prompt=f"Sheets in scope: {marks}\n\nQuestion: {question}",
        schema_hint='{"answer": "string"}',
    )
    if isinstance(result, dict):
        return result.get("answer") or ""
    return ""


@project_query_bp.route("/project/<project_id>/ask", methods=["POST"])
def project_ask(project_id: str):
    payload = request.get_json(silent=True) or {}
    raw_token = (request.headers.get("X-Project-Token")
                 or request.args.get("token") or "").strip() or None

    try:
        token = authorize_token(raw_token)
        if token.project_id != project_id:
            raise ProjectAccessRefused("wrong project")
    except ProjectAccessRefused:
        return _refuse()

    question = (payload.get("question") or "").strip()
    if not question:
        return _refuse()

    note_token_use(token)
    workspace = _workspace(project_id)

    limit = current_app.config.get("TRIAL_QUERY_ALLOWANCE", 0)
    admin_email = current_app.config.get("ADMIN_CONTACT_EMAIL", "")
    byok = byok_key_present(workspace)

    state = consume_query(project_id, limit=limit, byok=byok)

    landing = safe_landing_payload(
        project_id=project_id,
        project_name=getattr(workspace, "project_name", None) or project_id,
        organization=getattr(workspace, "owner", None),
        admin_email=admin_email,
    )

    if state == STATE_EXHAUSTED:
        # No model. Not "a model call that returns nothing" - the function is
        # not reached, which is what makes this a cost boundary rather than a
        # cosmetic one.
        body = apply_to_answer("", state, landing)
        body["usage"] = usage(project_id, limit=limit)
        return jsonify(body), 200

    # Context is scoped to what THIS bearer may read, before the prompt is
    # built - an authorization boundary that holds over HTTP and leaks through
    # a model is not a boundary. See services/project_rbac.scope_ai_context.
    sheets = payload.get("sheets") or []
    permitted = scope_ai_context(token, sheets)

    answer = _invoke_model(question, permitted)

    body = apply_to_answer(answer, state, landing)
    # The vector coordinates travel with the answer, and travel on the FINAL
    # query too: "deliver the full response and the viewBox" is the whole point
    # of finishing the last query rather than truncating it.
    body["view_box"] = payload.get("view_box")
    body["sheets_in_scope"] = [s.get("sheet_id") for s in permitted]
    body["usage"] = usage(project_id, limit=limit)
    return jsonify(body), 200
