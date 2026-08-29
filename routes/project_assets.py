"""CLAUDE-RBAC-TOKENS-01 — the only path to a drawing sheet's bytes.

WHY THIS ROUTE EXISTS AT ALL

Sheets used to live under `static/`, and Flask serves that tree with no
authorization whatsoever. Measured, before any of this was written:

    GET /static/nipigon/A204.svg   ->  200, unauthenticated

A role check on a route sitting beside a world-readable directory is
authorization theatre: the tests pass and nobody is stopped, because the file
is still one URL away. So project sheets live under `instance/project_assets/`
(config `PROJECT_ASSET_PATH`, deliberately outside `static/`) and this is the
only way to reach them.

WHAT IT DOES NOT DO

It does not consult `services/project_access.py`. That module answers "may
this account OPEN this project", and its first line is `if is_admin: return
True`. Drawing confidentiality is a different question with a different answer
— see `services/project_rbac.py`'s own header, and the Product Owner's
Decision 4. A session, admin or otherwise, grants nothing here; only a project
token does.

EVERY REFUSAL IS 403 WITH THE SAME BODY. Unknown token, expired, revoked,
wrong project, wrong discipline, unreadable sheet mark, and a project that does
not exist all look identical from outside. A 404 for "no such project" against
a 403 for "wrong project" would confirm which projects exist to anyone holding
any token at all.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, request, send_file

from services.project_rbac import (
    OUT_OF_LEAGUE_MESSAGE,
    ProjectAccessRefused,
    authorize_sheet,
    note_token_use,
    record_escalation,
    suggest_for_friction,
)

project_assets_bp = Blueprint("project_assets", __name__)

TOKEN_HEADER = "X-Project-Token"

# Extensions a sheet may be stored as. A closed list: whatever else ends up in
# that directory is not servable, so a stray file cannot become a download.
SHEET_SUFFIXES = (".svg", ".pdf", ".png")

_MIME = {".svg": "image/svg+xml", ".pdf": "application/pdf", ".png": "image/png"}

# A CONSTANT refusal body, byte-for-byte identical every time.
#
# `abort(403)` renders the application's own error PAGE, which carries a fresh
# CSRF token and CSP nonce per request - so two refusals differ, and a test
# that they are indistinguishable cannot pass even when the underlying
# behaviour is correct. Worse, it is 40KB of HTML delivered to an <img> tag.
#
# Serving a fixed plain-text body makes the property real rather than
# approximately true: unknown, expired, revoked, wrong project and wrong
# discipline are now identical down to the byte.
_REFUSED_BODY = "Not authorised.\n"
_ABSENT_BODY = "No such sheet.\n"


def _refuse() -> Response:
    return Response(_REFUSED_BODY, status=403, mimetype="text/plain")


def _absent() -> Response:
    return Response(_ABSENT_BODY, status=404, mimetype="text/plain")


def _asset_root() -> Path:
    configured = current_app.config.get("PROJECT_ASSET_PATH")
    if not configured:
        return None
    return Path(configured)


def _presented_token() -> str | None:
    """Header first, then an explicit query parameter.

    The query form exists because an <img src> cannot set a header, which is
    exactly how a drawing gets displayed. It is a real exposure trade-off: a
    token in a URL lands in browser history and any proxy log. It is accepted
    here, narrowly, because these tokens are project-scoped, discipline-scoped,
    expiring and instantly revocable — and recorded so the trade-off is visible
    rather than discovered later.
    """
    header = request.headers.get(TOKEN_HEADER)
    if header:
        return header.strip()
    return (request.args.get("token") or "").strip() or None


@project_assets_bp.route("/project/<project_id>/sheet/<path:sheet_id>")
def project_sheet(project_id: str, sheet_id: str):
    """Serve one sheet, or refuse identically for every reason."""
    try:
        token = authorize_sheet(_presented_token(), project_id, sheet_id)
    except ProjectAccessRefused:
        return _refuse()

    # CONTAINMENT AFTER RESOLUTION, not pattern-matching before it. `<path:>`
    # accepts slashes, and a caller-supplied name can carry `..`, encoded
    # separators, or an absolute path. Rejecting suspicious-looking strings is
    # a guessing game; resolving the path and then requiring it to sit inside
    # this project's own directory is a fact. Same discipline as
    # tools/storage_bridge_agent.py's own root containment.
    configured_root = _asset_root()
    if configured_root is None:
        return _refuse()
    root = configured_root.resolve()
    project_dir = (root / project_id).resolve()
    if not str(project_dir).startswith(str(root) + os.sep):
        return _refuse()

    for suffix in SHEET_SUFFIXES:
        candidate = (project_dir / f"{sheet_id}{suffix}").resolve()
        if not str(candidate).startswith(str(project_dir) + os.sep):
            continue                      # escaped its own project - not ours
        if candidate.is_file():
            note_token_use(token)
            return send_file(candidate, mimetype=_MIME.get(suffix))

    # A sheet the bearer WAS entitled to read, that does not exist. 404 is
    # honest here and leaks nothing: authorization already passed, so this
    # bearer is entitled to know the difference between "not yours" and "not
    # here" within their own project.
    return _absent()


@project_assets_bp.route("/project/<project_id>/friction", methods=["POST"])
def project_friction(project_id: str):
    """A stuck person, and what can honestly be offered them.

    Returns a DETERMINISTIC suggestion built from what the page already knows
    (a callout that reads `1/A801` names its own target), or nothing. No model
    is called: this trigger fires on three taps, and an LLM on a noisy trigger
    could name a sheet that does not exist. See suggest_for_friction.

    Authorised like everything else here - a friction report is still a
    statement about a project, and an unauthenticated one would let anyone
    probe which sheet ids produce a suggestion.
    """
    payload = request.get_json(silent=True) or {}
    try:
        token = authorize_sheet(
            _presented_token(), project_id, payload.get("sheet_id") or "")
    except ProjectAccessRefused:
        return _refuse()

    note_token_use(token)
    suggestion = suggest_for_friction(
        (payload.get("signal") or "").strip(),
        {"callout_target": payload.get("callout_target")},
    )
    # `suggestion: null` is a real, useful answer: nothing honest to offer.
    return jsonify({"suggestion": suggestion})


@project_assets_bp.route("/project/<project_id>/escalation", methods=["POST"])
def project_escalation(project_id: str):
    """GO could not answer. Say so plainly and put it in front of a human.

    The reply carries the Product Owner's exact words. Every authority fact on
    the stored row - which project, which role - is copied from the token by
    record_escalation, never from this payload.
    """
    payload = request.get_json(silent=True) or {}
    raw_token = _presented_token()

    # The project in the URL must be the token's own, checked before anything
    # is written, for the same reason a sheet request is.
    try:
        from services.project_rbac import authorize_token

        token = authorize_token(raw_token)
        if token.project_id != project_id:
            raise ProjectAccessRefused("refused")
        escalation = record_escalation(
            raw_token,
            query_text=payload.get("query") or "",
            sheet_id=payload.get("sheet_id") or None,
            view_box=payload.get("view_box") or None,
            friction_signal=payload.get("signal") or None,
        )
    except ProjectAccessRefused:
        return _refuse()

    return jsonify({
        "message": OUT_OF_LEAGUE_MESSAGE,
        "escalation_id": escalation.id,
        "status": "queued",
    }), 202
