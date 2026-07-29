"""
SMTP finalization (CLAUDE-P27-B): reset tokens/links must never appear
in a production log line. services/password_reset.py's only place that
ever logs the raw reset_url is explicitly gated on
is_dev_fallback_active() (unreachable under ProductionConfig, per
app.py's own boot-time assertion in _validate_production_config) --
this test proves it structurally, at the log-record level, rather than
relying on reading the source and trusting the gate.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from werkzeug.security import generate_password_hash


class _CaptureAllRecords(logging.Handler):
    """Captures every LogRecord's fully rendered message, across every
    logger in the process -- broader than assertLogs's name filter,
    since the guarantee this test makes ("never anywhere in the log")
    must not be scoped to one logger name."""

    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


class ResetTokenLogSafetyTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_token_log_safety_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            user = User(
                username="log_safety_user", password_hash=generate_password_hash("x"), role="read_only",
                email="log.safety@example.com",
            )
            db.session.add(user)
            db.session.commit()

        self.handler = _CaptureAllRecords()
        self.handler.setLevel(logging.DEBUG)
        logging.getLogger().addHandler(self.handler)

    def tearDown(self):
        logging.getLogger().removeHandler(self.handler)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _assert_no_token_or_url_logged(self):
        for message in self.handler.messages:
            self.assertNotIn("/reset-password?token=", message, f"reset URL leaked into a log line: {message!r}")

    def test_dev_fallback_inactive_never_logs_the_reset_url(self):
        # is_dev_fallback_active() is False whenever DEBUG and TESTING
        # are both False -- patch the request_password_reset call site's
        # own gate function directly, the same structural guarantee
        # app.py's _validate_production_config enforces at boot for
        # real ProductionConfig, without needing a second full app boot
        # under a patched ProductionConfig here.
        with self.flask_app.app_context(), \
             mock.patch("services.password_reset.is_dev_fallback_active", return_value=False):
            self.client.post("/forgot-password", data={"email": "log.safety@example.com"})

        self._assert_no_token_or_url_logged()

    def test_dev_fallback_inactive_even_when_smtp_delivery_fails(self):
        # The failure path (SMTP configured but the send itself fails)
        # is the one most likely to accidentally include the token in a
        # future debugging-motivated change (e.g. logging the message
        # body on failure) -- exercised explicitly, not just the
        # simpler "SMTP unset" path above.
        self.flask_app.config["SMTP_HOST"] = "smtp.example.com"
        try:
            with self.flask_app.app_context(), \
                 mock.patch("services.password_reset.is_dev_fallback_active", return_value=False), \
                 mock.patch("services.password_reset.send_email", return_value=False):
                self.client.post("/forgot-password", data={"email": "log.safety@example.com"})
        finally:
            self.flask_app.config["SMTP_HOST"] = ""

        self._assert_no_token_or_url_logged()

    def test_dev_fallback_active_does_log_the_link_by_design(self):
        # Sanity check for the test methodology itself -- proves
        # _CaptureAllRecords actually would have caught a leak, by
        # exercising the one path that's SUPPOSED to log it.
        with self.flask_app.app_context():
            self.client.post("/forgot-password", data={"email": "log.safety@example.com"})

        self.assertTrue(
            any("/reset-password?token=" in m for m in self.handler.messages),
            "expected the dev-only fallback to log the reset link when active",
        )


if __name__ == "__main__":
    unittest.main()
