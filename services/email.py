"""
Optional SMTP email delivery, configured entirely via SMTP_* env vars
(config.py). Stdlib smtplib only -- no new dependency, no cloud service
required (see tools/dependency_fit.py's PASS on this exact shape).

The one caller (services/password_reset.py) already checks
current_app.config["SMTP_HOST"] before calling this at all and falls
back to a dev-only logged link when it's blank -- this module never
needs to decide "is email configured", only "did this one send work".
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from flask import current_app

logger = logging.getLogger(__name__)


def send_email(to_addr: str, subject: str, body: str) -> bool:
    """Best-effort SMTP send. Returns True on success, False on any
    failure -- never raises, so a transient mail-server problem degrades
    to the caller's own fallback rather than a 500 on the request that
    triggered it.

    CLAUDE-P27-B (SMTP finalization): two mutually exclusive transport
    modes, matching how real providers actually offer SMTP -- implicit
    TLS (SMTP_USE_SSL, typically port 465: the whole connection is
    encrypted from the first byte, smtplib.SMTP_SSL) and STARTTLS
    (SMTP_USE_TLS, typically port 587: connect in plaintext, then
    upgrade). Previously only STARTTLS was implemented at all -- a
    provider requiring implicit TLS on port 465 would silently fail
    every send, never a config-time signal (see app.py's
    _validate_production_config, which now warns if both are set at
    once, an invalid combination)."""
    if not to_addr:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["SMTP_FROM"]
    message["To"] = to_addr
    message.set_content(body)

    use_ssl = current_app.config["SMTP_USE_SSL"]
    smtp_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    try:
        with smtp_cls(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=10) as server:
            if current_app.config["SMTP_USE_TLS"] and not use_ssl:
                server.starttls()
            if current_app.config["SMTP_USERNAME"]:
                server.login(current_app.config["SMTP_USERNAME"], current_app.config["SMTP_PASSWORD"])
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError):
        logger.warning("SMTP send to %s failed.", to_addr, exc_info=True)
        return False
