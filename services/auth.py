"""
Session-based login gate for the web UI (routes/portal.py), backed by the
`User` table (models.py).

Multi-user, two-role model: 'admin' (full access, including /upload) and
'read_only' (dashboard-only). Provisioning is maintainer-CLI-only --
tools/create_credentials.py -- there is no self-registration route.

Session trust, not per-request re-verification: role is read from the
session cookie, not re-queried from the DB on every request. This is a
deliberate tradeoff for a small internal tool with a handful of
maintainer-provisioned accounts: it costs nothing per request, at the
cost that a user who is demoted or deleted mid-session stays effectively
privileged until they log out. Sessions here are default signed-cookie
sessions (no server-side session store), so there is no way to force-
invalidate one specific session -- the only way to force everyone to
re-authenticate immediately is rotating FLASK_SECRET_KEY.

Scope: this gates the HTML pages in routes/portal.py directly via the
login_required/admin_required decorators below. routes/api.py's JSON
endpoints reuse the same is_authenticated()/is_admin() checks, enforced
blueprint-wide via a before_request hook there (see routes/api.py) --
not through these two decorators.

CLAUDE-SESSION-EXPIRY-JSON-01: those decorators no longer produce ONLY a
redirect. A browser still gets the 302 to /login; a script - detected by
wants_json_response() below, on the shape of the request rather than its
path -- gets 401 JSON instead, because fetch() follows a 302 transparently
and then chokes on the login page's HTML. That does not change what
routes/api.py does: its own before_request hook still handles /api/, and
these decorators are still not what gates it.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Optional

from flask import abort, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from models import ROLE_ADMIN, User

logger = logging.getLogger(__name__)


def check_credentials(username: str, password: str) -> Optional[User]:
    """Look up `username` and verify `password` against its stored hash.

    Returns the matching User on success, None otherwise -- deliberately
    generic, doesn't distinguish "no such user", "wrong password", or
    "suspended account". A suspended user gets the exact same
    login-page message as a wrong password, not a distinct "your
    account is suspended" message -- consistent with this module's
    existing refusal to reveal account state beyond authenticated/not.

    CLAUDE-P27-B: the HTTP-facing generic-failure contract above is about
    the RESPONSE only -- the server log (never shown to the requester) is
    a different audience, and distinguishing the three failure reasons
    there has real security-monitoring value with no enumeration cost.
    Previously this whole login path had zero logging of any kind.
    """
    user = User.query.filter_by(username=username).first()
    if user is None:
        logger.warning("Login failed: no account for username %r.", username)
        return None
    if not check_password_hash(user.password_hash, password):
        logger.warning("Login failed: wrong password for username %r.", username)
        return None
    if not user.is_active:
        logger.warning("Login rejected: account %r is suspended.", username)
        return None
    logger.info("Login succeeded for user %r (role=%r).", user.username, user.role)
    return user


def is_authenticated() -> bool:
    return session.get("user_id") is not None


def is_admin() -> bool:
    return session.get("role") == ROLE_ADMIN


def user_can_upload_to_storage() -> bool:
    """
    CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage Grammar &
    Public-Trial Entitlement): the ONE centralized choke point every
    "Upload to Storage" surface (both the New Project folder-upload
    fieldset and Admin -> Project Data Management's own "Add documents
    to project") checks - client-side (grey the control) AND
    server-side (the actual gate on the route itself), so a public-trial
    user cannot bypass a cosmetic UI-only restriction by posting
    directly to the upload route.

    Deliberately, honestly a no-op today: `models.User.ROLES` is
    `(admin, read_only)` only - this codebase has no real public-trial
    account/entitlement concept yet (`services/trial_request.py` is a
    lead-gen "request access" contact-email form, not real account
    provisioning; there is no self-serve signup flow). Every
    authenticated user is entitled to Upload today, so this always
    returns True. When a real trial/managed-plan entitlement distinction
    is built, THIS function (and only this function) needs to change -
    every caller already checks through here rather than re-deriving
    the answer, so nothing else needs to be found and updated.
    """
    return True


def log_in(user: User) -> None:
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role


def log_out() -> None:
    username = session.get("username")
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)
    # CLAUDE-POSTCAMEL-CA1B (Section 11, persistence boundary): this
    # function previously popped only the three auth keys, leaving any
    # `selected_object:{project_id}`/`focused_finding:{project_id}`
    # session state in place - since the browser's session cookie itself
    # isn't cleared, a fresh sign-in in the same browser would silently
    # inherit the PREVIOUS session's "professional context" for any
    # matching project id. A real, found gap: sign-out is meant to be a
    # clean boundary, not merely an auth boundary.
    for key in [k for k in session.keys() if k.startswith("selected_object:") or k.startswith("focused_finding:")]:
        session.pop(key, None)
    if username is not None:
        logger.info("User %r logged out.", username)


def wants_json_response() -> bool:
    """Whether this caller is a script that will call `.json()` on the reply.

    CLAUDE-SESSION-EXPIRY-JSON-01. This is app.py's `_csrf_wants_json()` moved
    here rather than reimplemented, and app.py now delegates to it - the two
    were about to become two copies of one judgement, and a second copy is
    exactly how they drift into disagreeing about the same request.

    Keyed off HOW the client asked, never WHERE. Path tells us nothing: every
    blueprint under /api/ is csrf.exempt, and the workspace fetch() calls that
    need this most are not under /api/ at all.

    X-CSRFToken is the strongest signal and the one that actually fires in this
    codebase - every fetch() in static/js sets it and no rendered <form> can.

    The Accept comparison is deliberately STRICT (`>`, never `>=`): a bare
    `Accept: */*` - curl, and some fetch defaults - scores application/json and
    text/html equally, and treating that tie as "wants JSON" would turn an
    ordinary browser form POST into a JSON reply. That trap is the reason this
    helper exists as one shared implementation instead of a header check
    written inline twice.
    """
    if request.headers.get("X-CSRFToken"):
        return True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True
    if request.is_json:
        return True
    accept = request.accept_mimetypes
    return accept["application/json"] > accept["text/html"]


def _unauthenticated_response():
    """The one place that decides what an unauthenticated caller receives.

    A browser gets the 302 to /login it has always got - that behaviour is
    correct, tested, and deliberately unchanged.

    A script gets 401 JSON carrying the same destination. It previously got the
    302, which is worse than it looks: fetch() follows redirects transparently,
    so the script received 200 and a page of HTML, and `resp.json()` threw a
    parse error. An expired session therefore surfaced as "a network error
    occurred" - a wrong diagnosis of a routine timeout, and precisely the
    failure CLAUDE-CSRF-EXPIRY-01 already fixed for CSRF while leaving it
    unfixed for session expiry.

    401 rather than 302 is the point: it is a status fetch() cannot silently
    swallow, so the client can act on it instead of parsing a login page.
    """
    login_url = url_for("portal.login", next=request.path)
    if wants_json_response():
        return jsonify(error="session_expired", redirect=login_url), 401
    return redirect(login_url)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return _unauthenticated_response()
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Like login_required, but also requires the admin role.

    Implies login_required rather than being stacked alongside it: an
    unauthenticated request is redirected to /login (nothing role-related
    to reject yet); an authenticated-but-read_only request gets a 403 --
    that split is the point of having this as its own decorator.

    CLAUDE-SESSION-EXPIRY-JSON-01 changes only the unauthenticated half. The
    403 for an authenticated-but-read_only caller still renders through
    app.py's own handler; a script hitting THAT has the same .json() problem,
    but it is a different case (a standing authorization decision, not an
    expiring session) and is recorded as unaddressed rather than folded in
    silently.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return _unauthenticated_response()
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapped
