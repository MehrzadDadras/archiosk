"""
CLAUDE-P27-B: services/auth.py previously had zero logging on the login
path at all -- login success and failure (including the three distinct
failure reasons: no such user, wrong password, suspended account) are
now logged server-side, while the HTTP response text stays exactly as
generic as before (see test_user_suspension.py / test_password_reset.py
for that contract) -- these are two different audiences, and only the
log is allowed to be specific.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import logging
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash


class AuthSecurityLoggingTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_auth_logging_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            active_user = User(
                username="logtest_active", password_hash=generate_password_hash("correct-pw-123"), role="read_only",
            )
            suspended_user = User(
                username="logtest_suspended", password_hash=generate_password_hash("correct-pw-123"), role="read_only",
                is_active=False,
            )
            db.session.add_all([active_user, suspended_user])
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_successful_login_logs_at_info(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            with self.assertLogs("services.auth", level="INFO") as captured:
                user = check_credentials("logtest_active", "correct-pw-123")
        self.assertIsNotNone(user)
        self.assertTrue(any("succeeded" in msg and "logtest_active" in msg for msg in captured.output))

    def test_unknown_username_logs_at_warning(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            with self.assertLogs("services.auth", level="WARNING") as captured:
                check_credentials("no_such_user", "whatever")
        self.assertTrue(any("no account" in msg for msg in captured.output))

    def test_wrong_password_logs_at_warning(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            with self.assertLogs("services.auth", level="WARNING") as captured:
                check_credentials("logtest_active", "wrong-password")
        self.assertTrue(any("wrong password" in msg for msg in captured.output))

    def test_suspended_account_logs_at_warning_distinctly(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            with self.assertLogs("services.auth", level="WARNING") as captured:
                check_credentials("logtest_suspended", "correct-pw-123")
        self.assertTrue(any("suspended" in msg for msg in captured.output))

    def test_logout_logs_the_username(self):
        from services.auth import log_in, log_out
        from models import User

        with self.flask_app.test_request_context():
            with self.flask_app.app_context():
                user = User.query.filter_by(username="logtest_active").first()
            log_in(user)
            with self.assertLogs("services.auth", level="INFO") as captured:
                log_out()
        self.assertTrue(any("logtest_active" in msg and "logged out" in msg for msg in captured.output))


if __name__ == "__main__":
    unittest.main()
