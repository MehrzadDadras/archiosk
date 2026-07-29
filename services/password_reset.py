"""
Self-service password reset (CLAUDE-P28): forgot-password request ->
emailed (or, outside production, logged) single-use token -> new
password. See routes/portal.py's forgot_password/reset_password for the
HTTP-facing side of this.

Token model (models.PasswordResetToken): the raw token
(secrets.token_urlsafe(32), 256 bits of entropy) exists only in memory
and in the link handed to the caller -- only its SHA-256 digest is ever
persisted, the same "never store the real secret" shape as
User.password_hash never storing a plain password. A read of the
database (or a backup of it) never yields a directly usable token.

Neutral by design: request_password_reset() takes exactly the same
observable action (return None, no exception, same log shape modulo the
message text) whether or not the email matches an account, so
routes/portal.py can show the identical confirmation message either
way - never revealing account existence.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from flask import current_app
from werkzeug.security import generate_password_hash

from models import PasswordResetToken, User, db
from services.email import send_email

logger = logging.getLogger(__name__)

RESET_TOKEN_TTL_MINUTES = 30


def _now() -> datetime:
    # PasswordResetToken's DateTime columns are plain (SQLite has no
    # native timezone-aware storage, so a value written as tz-aware comes
    # back naive) - naive UTC throughout this module so a stored value
    # can always be compared directly to "now" without an aware/naive
    # TypeError.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _find_user_by_email(email: str) -> Optional[User]:
    email = (email or "").strip().lower()
    if not email:
        return None
    return User.query.filter(db.func.lower(User.email) == email).first()


def is_dev_fallback_active() -> bool:
    """
    Structural gate, not a single env flag someone could leave mis-set:
    only DevelopmentConfig/TestingConfig ever have DEBUG or TESTING true
    (config.py) - ProductionConfig has neither, so the dev-only fallback
    below is unreachable in production regardless of whether SMTP_HOST
    also happens to be blank there. Exported so routes/portal.py can
    show the same "check the server log" hint without duplicating this
    gate.
    """
    return bool(current_app.debug or current_app.testing)


def request_password_reset(email: str, base_url: str) -> Optional[str]:
    """
    Returns the raw reset URL ONLY when every one of these holds: a real
    account matched, SMTP didn't actually deliver it (either unconfigured
    or a real send failure), and is_dev_fallback_active() (never true
    under ProductionConfig). Every other case - no match; SMTP genuinely
    delivered - returns None.

    This return value is the one deliberate, explicit exception to
    "never reveal account existence": routes/portal.py is allowed to
    render it directly on the page, but ONLY in that same dev/testing
    gate, and its own user-facing CONFIRMATION MESSAGE must still never
    vary with this return value or with whether a match happened -
    only with whether SMTP is configured at all (a fact identical for
    every request, not tied to any one email) - see that route's own
    comment for why per-request delivery outcome can't safely drive the
    message text without reintroducing an enumeration oracle.
    """
    user = _find_user_by_email(email)
    if user is None:
        logger.info("Password reset requested for an email with no matching account.")
        return None

    # Single active token per user: an earlier, still-unused request is
    # superseded rather than left valid alongside the new one.
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": _now()}, synchronize_session=False,
    )

    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(raw_token),
        expires_at=_now() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    db.session.add(token_row)
    db.session.commit()

    reset_url = f"{base_url.rstrip('/')}/reset-password?token={raw_token}"
    logger.info("Password reset requested for user %r (token id=%s).", user.username, token_row.id)

    delivered = False
    if current_app.config.get("SMTP_HOST"):
        delivered = send_email(
            to_addr=user.email,
            subject="Archiosk password reset",
            body=(
                f"A password reset was requested for your Archiosk account ({user.username}).\n\n"
                f"Reset your password: {reset_url}\n\n"
                f"This link expires in {RESET_TOKEN_TTL_MINUTES} minutes and can only be used once. "
                "If you didn't request this, you can ignore this message."
            ),
        )
        # Explicit success AND failure logging - never inferred from the
        # absence of a warning. This is the one place delivery outcome is
        # ever reported; the HTTP response never reflects it (see above).
        if delivered:
            logger.info("Password reset email delivered to user %r.", user.username)
        else:
            logger.warning("Password reset email FAILED to send to user %r.", user.username)

    if delivered:
        return None

    if is_dev_fallback_active():
        logger.warning(
            "DEV-ONLY password reset link (email not sent) for user %r: %s", user.username, reset_url,
        )
        return reset_url

    return None


def get_valid_reset_token(raw_token: str) -> Optional[PasswordResetToken]:
    """None for missing/unknown/used/expired - callers never need to
    distinguish which, avoiding a second place that could leak
    account-existence/state through error-message differences."""
    if not raw_token:
        return None
    token_row = PasswordResetToken.query.filter_by(token_hash=_hash_token(raw_token)).first()
    if token_row is None or token_row.used_at is not None or token_row.expires_at < _now():
        return None
    return token_row


def complete_password_reset(token_row: PasswordResetToken, new_password: str) -> None:
    user = db.session.get(User, token_row.user_id)
    user.password_hash = generate_password_hash(new_password)
    token_row.used_at = _now()
    db.session.commit()
    logger.info("Password reset completed for user %r (token id=%s).", user.username, token_row.id)
