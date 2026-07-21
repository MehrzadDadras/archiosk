"""
Session-based login gate for the web UI (routes/portal.py).

Single shared credential, not a multi-user account system -- there's no
user database anywhere in this app. AUTH_USERNAME/AUTH_PASSWORD_HASH being
unset means the gate is locked to everyone, not open to everyone: an
unconfigured gate must fail closed, or upgrading to this code would
silently leave /upload and /dashboard unprotected.

Scope: this only gates the HTML pages in routes/portal.py.
routes/api.py's JSON endpoints are untouched -- token/key-based API auth
is a different concern from a session-cookie login gate and wasn't part
of this ask.
"""
from __future__ import annotations

from functools import wraps

from flask import current_app, redirect, request, session, url_for
from werkzeug.security import check_password_hash


def check_credentials(username: str, password: str) -> bool:
    expected_username = current_app.config.get("AUTH_USERNAME", "")
    expected_hash = current_app.config.get("AUTH_PASSWORD_HASH", "")

    if not expected_username or not expected_hash:
        return False

    return username == expected_username and check_password_hash(expected_hash, password)


def is_authenticated() -> bool:
    return bool(session.get("authenticated"))


def log_in(username: str) -> None:
    session["authenticated"] = True
    session["username"] = username


def log_out() -> None:
    session.pop("authenticated", None)
    session.pop("username", None)


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("portal.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped
