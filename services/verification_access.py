"""
CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: a sanctioned, auditable,
ephemeral identity for live-browser verification work, replacing repeated
ad hoc "create a throwaway admin account" attempts that kept hitting the
sandbox's own credential-creation restrictions.

Mirrors services/password_reset.py's own already-shipped, already-trusted
shape closely, on purpose: a single-use, expiring, unguessable token
(secrets.token_urlsafe(32), 256 bits of entropy) whose SHA-256 digest is
the only thing ever persisted (models.VerificationAccessToken). The
difference from password reset is what the token DOES once consumed --
it establishes a real login session directly (services.auth.log_in),
rather than authorizing a password change -- and WHO can create one:
account provisioning in this codebase has always been maintainer-CLI-only
(tools/create_credentials.py's own module docstring: "no self-
registration route"), so token creation lives in tools/manage_
verification_access.py, run by a human with real server access, never by
an automated agent and never through a web route.

Lifecycle, deliberately not persisted at rest: `create_verification_
access` creates the dedicated User row (VERIFICATION_ACCOUNT_USERNAME,
always the same name) fresh if it doesn't already exist, and always
issues a brand-new token. `revoke_verification_access` deletes that User
row entirely (cascading its tokens with it via a plain query, not an ORM
relationship) -- there is nothing left to query for between verification
passes. `is_verification_session()` lets a route/template recognize this
identity without a schema change to `users` (no new column) -- it is
purely a fixed, well-known username check, since there is at most ever
one such account.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import session
from werkzeug.security import generate_password_hash

from models import ROLE_ADMIN, User, VerificationAccessToken, db

logger = logging.getLogger(__name__)

# Fixed, single well-known name -- deliberately not randomized per session,
# so "does a User with this username exist right now" is always the exact,
# simple residue check this stage's own validation requires, and so audit
# log lines across separate verification passes are trivially correlatable
# by username alone.
VERIFICATION_ACCOUNT_USERNAME = "_live_verification_agent"

DEFAULT_TOKEN_TTL_MINUTES = 60


def _now() -> datetime:
    # Same naive-UTC convention as services/password_reset.py's own _now()
    # -- SQLite has no native timezone-aware storage, so a value written
    # tz-aware comes back naive; naive throughout avoids an aware/naive
    # comparison TypeError.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def is_verification_session() -> bool:
    """True if the CURRENT session belongs to the one, well-known
    verification identity -- never true for a real admin's own session,
    since a real admin's username is never this fixed value."""
    return session.get("username") == VERIFICATION_ACCOUNT_USERNAME


def create_verification_access(ttl_minutes: int = DEFAULT_TOKEN_TTL_MINUTES) -> tuple[User, str]:
    """
    CLI-only entry point (tools/manage_verification_access.py) -- never
    called from a web route. Upserts the one, fixed-username verification
    User (role=admin; this codebase has only two roles, ROLE_ADMIN/
    ROLE_READ_ONLY -- see models.py -- so "admin" is the only role capable
    of exercising admin-gated surfaces like Reconcile or Developer Mode,
    the actual reason this mechanism exists) with a genuinely unusable
    random password (never surfaced anywhere -- login for this identity
    is ONLY ever via a verification token, never username/password) and
    issues one fresh, single-use token. Any previously-issued, still-
    unused token for this account is superseded (marked used) first, the
    same "one active token" discipline request_password_reset already
    established, so an old, forgotten link can never be replayed
    alongside a newly-generated one.

    Returns (user, raw_token) -- the CALLER (the CLI script) is
    responsible for printing the resulting one-time URL and NEVER writing
    the raw token to a file, a commit, or a log line.
    """
    user = User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).first()
    if user is None:
        user = User(
            username=VERIFICATION_ACCOUNT_USERNAME,
            password_hash=generate_password_hash(secrets.token_urlsafe(32)),
            role=ROLE_ADMIN,
        )
        db.session.add(user)
        db.session.flush()  # assigns user.id, needed for the token row below
        logger.info("Verification access: created identity %r (user_id=%s).", VERIFICATION_ACCOUNT_USERNAME, user.id)
    else:
        logger.info("Verification access: reusing existing identity %r (user_id=%s).", VERIFICATION_ACCOUNT_USERNAME, user.id)

    VerificationAccessToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": _now()}, synchronize_session=False,
    )

    raw_token = secrets.token_urlsafe(32)
    token_row = VerificationAccessToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=_now() + timedelta(minutes=ttl_minutes),
    )
    db.session.add(token_row)
    db.session.commit()
    logger.info(
        "Verification access: issued token id=%s for user_id=%s, expires in %s minutes.",
        token_row.id, user.id, ttl_minutes,
    )
    return user, raw_token


def get_valid_verification_token(raw_token: str) -> Optional[VerificationAccessToken]:
    """None for missing/unknown/used/expired -- callers never need to
    distinguish which, same reasoning as password_reset.py's own
    get_valid_reset_token (avoids a second place that could leak
    token-state through error-message differences)."""
    if not raw_token:
        return None
    token_row = VerificationAccessToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token_row is None or token_row.used_at is not None or token_row.expires_at < _now():
        return None
    return token_row


def consume_verification_token(token_row: VerificationAccessToken) -> User:
    """Marks the token single-use and returns the User to log in as.
    Does NOT itself call services.auth.log_in -- routes/portal.py's own
    verification_access_login route does that, the same separation
    password_reset.py's complete_password_reset keeps from the route
    that calls it."""
    user = db.session.get(User, token_row.user_id)
    token_row.used_at = _now()
    db.session.commit()
    logger.info("Verification access: token id=%s consumed, session established for user_id=%s.", token_row.id, user.id)
    return user


def revoke_verification_access() -> bool:
    """Deletes the verification User row (and, via the FK query below,
    every token that ever referenced it) entirely -- callable from BOTH
    the CLI (tools/manage_verification_access.py's own `revoke` command,
    the primary maintainer-operated cleanup path) and routes/portal.py's
    admin-gated self-revoke route (so a verification session can end
    itself without requiring a second CLI invocation for the common
    case). Returns True if an account existed and was removed, False if
    there was nothing to clean up -- both are a normal, successful
    outcome, never an error.
    """
    user = User.query.filter_by(username=VERIFICATION_ACCOUNT_USERNAME).first()
    if user is None:
        logger.info("Verification access: revoke requested, no identity currently exists.")
        return False
    VerificationAccessToken.query.filter_by(user_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    logger.info("Verification access: identity %r (user_id=%s) and all its tokens removed.", VERIFICATION_ACCOUNT_USERNAME, user.id)
    return True
