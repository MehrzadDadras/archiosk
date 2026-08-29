"""CLAUDE-RBAC-TOKENS-04 — the architect provisions access before anyone arrives.

WHO MAY REACH THIS, AND WHY IT IS NOT THE SAME QUESTION AS DRAWING ACCESS

The Product Owner's Decision 4 says a platform admin does NOT implicitly bypass
project drawing confidentiality, and `services/project_rbac.py` enforces exactly
that: no session, admin or otherwise, gets a sheet.

This surface is different in kind. It issues and withdraws credentials; it never
renders drawing content. Nothing on this page shows what is on a sheet — only
sheet *marks* the architect themselves chose to scope a pass to. So it is gated
the way every other administrative surface in this application is: a real
authenticated session that may open this project (`can_access_project`), which
is admin or the project's owner.

That separation is the point, and it is asserted by a test: an admin can hand
out a pass and still cannot read a drawing. Managing access is not the same
capability as having it.

WHAT THE RAW TOKEN DOES, AND DOES NOT, TOUCH

The generated token is shown exactly once, in the response to the POST that
created it. It is deliberately NOT flashed: `flash()` puts its message in the
session cookie, which would write a live credential into the architect's own
browser storage and into any log that captures cookies. Rendered once, held
nowhere.
"""
from __future__ import annotations

from datetime import datetime, timezone

from flask import (
    Blueprint, abort, current_app, redirect, render_template, request, url_for
)

from services.auth import login_required
from services.project_access import can_access_project
from services.project_rbac import (
    DISCIPLINES,
    ProjectAccessRefused,
    ROLE_ENGINEER,
    ROLE_PROJECT_OWNER,
    ROLE_TRADE,
    issue_token,
    list_all_tokens,
    revoke_token,
)

project_manage_bp = Blueprint("project_manage", __name__)

# Only these three may be handed out from this form. `architect` is excluded
# because this page IS the architect's own authority — a form that mints
# another architect pass is a privilege-escalation control wearing a form
# label. `platform_admin` is excluded because it grants no drawing access at
# all, so issuing one from a project page would be issuing nothing.
ISSUABLE_ROLES = (ROLE_PROJECT_OWNER, ROLE_ENGINEER, ROLE_TRADE)

# Presets the directive named, plus the custom date the form also accepts.
EXPIRY_PRESETS = {
    "8h": 8 * 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
}
DEFAULT_PRESET = "24h"


def _current_username() -> str | None:
    from flask import session

    return session.get("username")


def _guard(project_id: str):
    """Refuse anyone who may not administer this project.

    Uses the SAME `can_access_project` every other project surface uses, rather
    than a second rule invented here — one access question should have one
    answer, and a bespoke check on an administrative page is how the two drift.
    """
    from services.auth import is_admin
    from services.case_workspace import CaseWorkspaceStore

    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = store.get_or_create(project_id)
    if not can_access_project(workspace, _current_username(), is_admin()):
        abort(403)
    return workspace


def _parse_expiry(form) -> tuple[int | None, datetime | None]:
    """Return `(ttl_seconds, explicit_datetime)` — exactly one of them set.

    A custom date is honoured as a DATE, expiring at the end of that day in
    UTC. Reading "Jan 21, 2027" and expiring at 00:00 on the 21st would cut a
    pass a full day short of what the architect wrote down, which is the kind
    of off-by-one that gets discovered by a subcontractor standing on a site.
    """
    custom = (form.get("expires_on") or "").strip()
    if custom:
        try:
            day = datetime.strptime(custom, "%Y-%m-%d")
        except ValueError:
            raise ProjectAccessRefused("unparseable date")
        return None, day.replace(hour=23, minute=59, second=59,
                                 tzinfo=timezone.utc)

    preset = (form.get("expires_in") or DEFAULT_PRESET).strip()
    if preset not in EXPIRY_PRESETS:
        raise ProjectAccessRefused("unknown preset")
    return EXPIRY_PRESETS[preset], None


@project_manage_bp.route("/project/<project_id>/manage/access", methods=["GET"])
@login_required
def manage_access(project_id: str):
    _guard(project_id)
    return render_template(
        "project_access_manage.html",
        project_id=project_id,
        issuable_roles=ISSUABLE_ROLES,
        disciplines=DISCIPLINES,
        expiry_presets=list(EXPIRY_PRESETS.keys()),
        passes=list_all_tokens(project_id),
        issued_link=None,
        issued_label=None,
        error=None,
    )


@project_manage_bp.route("/project/<project_id>/manage/access", methods=["POST"])
@login_required
def create_access_pass(project_id: str):
    _guard(project_id)

    label = (request.form.get("label") or "").strip()
    role = (request.form.get("role") or "").strip()
    disciplines = request.form.getlist("disciplines")

    error = None
    issued_link = None
    issued_label = None

    try:
        if not label:
            raise ProjectAccessRefused("a pass with no name cannot be audited")
        if role not in ISSUABLE_ROLES:
            raise ProjectAccessRefused("role not issuable here")
        ttl_seconds, explicit = _parse_expiry(request.form)

        row, raw_token = issue_token(
            project_id, role,
            label=label,
            actor=_current_username(),
            disciplines=disciplines or None,
            ttl_seconds=ttl_seconds if ttl_seconds is not None else 0,
            expires_at=explicit,
        )
        # Shown ONCE, here, in this response. Never flashed - see the module
        # docstring: flash() would write a live credential into a cookie.
        issued_link = url_for("project_entry.project_entry",
                              project_id=project_id, token=raw_token)
        issued_label = row.label
    except ProjectAccessRefused:
        # One message. The form is behind an authenticated administrative gate,
        # so this is a usability message rather than a security boundary - but
        # it still says what to fix without echoing back what was submitted.
        error = ("That pass could not be issued. Check the role, the scope, "
                 "and that the expiry is in the future.")

    return render_template(
        "project_access_manage.html",
        project_id=project_id,
        issuable_roles=ISSUABLE_ROLES,
        disciplines=DISCIPLINES,
        expiry_presets=list(EXPIRY_PRESETS.keys()),
        passes=list_all_tokens(project_id),
        issued_link=issued_link,
        issued_label=issued_label,
        error=error,
    ), (200 if issued_link else 400)


@project_manage_bp.route("/project/<project_id>/manage/access/<int:token_id>/revoke",
                         methods=["POST"])
@login_required
def revoke_access_pass(project_id: str, token_id: int):
    """Withdraw one pass. Effective on the very next request, by construction:
    `authorize_token` reads `revoked_at` on every call, so there is no cache or
    session to expire first."""
    from models import ProjectAccessToken, db

    _guard(project_id)
    row = db.session.get(ProjectAccessToken, token_id)
    # A pass belonging to another project must not be revocable from this
    # project's page, or the page becomes a lever on projects it does not own.
    if row is None or row.project_id != project_id:
        abort(403)
    revoke_token(token_id, actor=_current_username())
    return redirect(url_for("project_manage.manage_access", project_id=project_id))
