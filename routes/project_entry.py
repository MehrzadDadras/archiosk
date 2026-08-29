"""CLAUDE-RBAC-TOKENS-04 - where an access link actually lands.

The architect's panel emits `/project/<id>?token=<token>`. Without this route
that link would 404, and a management page that hands out dead links is worse
than one that hands out none.

WHAT A STAKEHOLDER SEES: only the sheets their own pass permits. The list is
built by filtering what is on disk through `may_read_discipline`, so a trade
contractor scoped to structural is never even told that an architectural sheet
exists. That is deliberate - a sheet mark is itself information, and a list
that showed refused rows would leak the shape of the drawing set to everyone
holding any pass at all.

The token is NOT put into a session here. It stays in the URL and is presented
on every request, so revocation takes effect on the next click rather than
whenever a session happens to expire.
"""
from __future__ import annotations

import os
from pathlib import Path

from flask import Blueprint, Response, current_app, render_template, request

from services.project_rbac import (
    ProjectAccessRefused,
    authorize_token,
    discipline_for_sheet,
    may_read_discipline,
    note_token_use,
    token_disciplines,
)

project_entry_bp = Blueprint("project_entry", __name__)

_REFUSED_BODY = "Not authorised.\n"


def _refuse() -> Response:
    return Response(_REFUSED_BODY, status=403, mimetype="text/plain")


def _permitted_sheets(token, project_id: str) -> list:
    """Sheet marks on disk that this pass may read, sorted."""
    root = current_app.config.get("PROJECT_ASSET_PATH")
    if not root:
        return []
    folder = (Path(root) / project_id).resolve()
    base = Path(root).resolve()
    if not str(folder).startswith(str(base) + os.sep) or not folder.is_dir():
        return []

    seen = []
    for entry in sorted(folder.iterdir()):
        if not entry.is_file():
            continue
        mark = entry.stem
        discipline = discipline_for_sheet(mark)
        if discipline is None or not may_read_discipline(token, discipline):
            continue
        seen.append({"sheet_id": mark, "discipline": discipline})
    return seen


@project_entry_bp.route("/project/<project_id>")
def project_entry(project_id: str):
    raw_token = (request.args.get("token") or "").strip() or None
    try:
        token = authorize_token(raw_token)
        if token.project_id != project_id:
            raise ProjectAccessRefused("wrong project")
    except ProjectAccessRefused:
        return _refuse()

    note_token_use(token)
    return render_template(
        "project_entry.html",
        project_id=project_id,
        token=raw_token,
        role=token.role,
        label=token.label,
        expires_at=token.expires_at,
        disciplines=token_disciplines(token),
        sheets=_permitted_sheets(token, project_id),
    )
