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
    triggered it."""
    if not to_addr:
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = current_app.config["SMTP_FROM"]
    message["To"] = to_addr
    message.set_content(body)

    try:
        with smtplib.SMTP(current_app.config["SMTP_HOST"], current_app.config["SMTP_PORT"], timeout=10) as server:
            if current_app.config["SMTP_USE_TLS"]:
                server.starttls()
            if current_app.config["SMTP_USERNAME"]:
                server.login(current_app.config["SMTP_USERNAME"], current_app.config["SMTP_PASSWORD"])
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError):
        logger.warning("SMTP send to %s failed.", to_addr, exc_info=True)
        return False
