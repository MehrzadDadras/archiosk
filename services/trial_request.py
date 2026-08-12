"""
Trial access request intake (CLAUDE-CA1D-TRIAL-ACCESS-HOTFIX-01): the
smallest safe replacement for the former dead-end /start-trial page,
which offered no way for an interested visitor to actually act.

Deliberately NOT a new persistent PII store and NOT a new external
service: reuses services/email.py's existing best-effort SMTP transport
exactly as services/password_reset.py already does, gated the same
"blank means skip, never error" way SMTP_HOST already is throughout this
app. If TRIAL_REQUEST_NOTIFY_EMAIL is unset, the request still succeeds
(the visitor still gets a truthful acknowledgement) and is still
durably traceable via the application log -- a real record always
exists even before a human configures the notification address.
"""
from __future__ import annotations

import logging

from flask import current_app

from services.email import send_email

logger = logging.getLogger(__name__)


def submit_trial_request(name: str, email: str, message: str) -> None:
    """Best-effort: logs the request unconditionally, then emails
    TRIAL_REQUEST_NOTIFY_EMAIL if one is configured. Never raises -- a
    caller always gets a truthful "request received" outcome regardless
    of whether notification delivery itself succeeds, matching
    send_email()'s own "never a hard dependency" contract."""
    name = (name or "").strip()
    email = (email or "").strip()
    message = (message or "").strip()

    logger.info(
        "Trial access request received (name=%r, email=%r, message_length=%d).",
        name, email, len(message),
    )

    notify_addr = current_app.config.get("TRIAL_REQUEST_NOTIFY_EMAIL")
    if not notify_addr or not current_app.config.get("SMTP_HOST"):
        return

    body_lines = [
        "A new Archiosk trial access request was submitted.",
        "",
        f"Name: {name or '(not provided)'}",
        f"Email: {email or '(not provided)'}",
    ]
    if message:
        body_lines += ["", "Message:", message]

    delivered = send_email(
        to_addr=notify_addr,
        subject="Archiosk trial access request",
        body="\n".join(body_lines),
    )
    if delivered:
        logger.info("Trial access request notification delivered.")
    else:
        logger.warning("Trial access request notification FAILED to send.")
