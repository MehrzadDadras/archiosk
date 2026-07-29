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
not through these two decorators, since a JSON API needs a 401/403
response rather than the redirect-to-/login these produce.
"""
from __future__ import annotations

import logging
from functools import wraps
from typing import Optional

from flask import abort, redirect, request, session, url_for
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


def log_in(user: User) -> None:
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role


def log_out() -> None:
    username = session.get("username")
    session.pop("user_id", None)
    session.pop("username", None)
    session.pop("role", None)
    if username is not None:
        logger.info("User %r logged out.", username)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("portal.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    """Like login_required, but also requires the admin role.

    Implies login_required rather than being stacked alongside it: an
    unauthenticated request is redirected to /login (nothing role-related
    to reject yet); an authenticated-but-read_only request gets a 403 --
    that split is the point of having this as its own decorator.
    """
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("portal.login", next=request.path))
        if not is_admin():
            abort(403)
        return view(*args, **kwargs)
    return wrapped
