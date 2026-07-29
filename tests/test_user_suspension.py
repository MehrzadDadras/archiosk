"""
CLAUDE-P27-B: User.is_active -- a suspended account can no longer sign
in (services.auth.check_credentials), but nothing else about the
account is touched. Defaults True so every existing/newly-created
account is unaffected until an operator explicitly suspends one via
tools/create_credentials.py --suspend.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash


class UserSuspensionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_user_suspension_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            active_user = User(
                username="active_user", password_hash=generate_password_hash("correct-pw-123"), role="read_only",
            )
            suspended_user = User(
                username="suspended_user", password_hash=generate_password_hash("correct-pw-123"), role="read_only",
                is_active=False,
            )
            db.session.add_all([active_user, suspended_user])
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_new_user_defaults_to_active(self):
        from models import User, db

        with self.flask_app.app_context():
            user = User(username="brand_new", password_hash=generate_password_hash("x"), role="read_only")
            db.session.add(user)
            db.session.commit()
            self.assertTrue(user.is_active)

    def test_check_credentials_rejects_suspended_user_with_correct_password(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            self.assertIsNone(check_credentials("suspended_user", "correct-pw-123"))

    def test_check_credentials_accepts_active_user_with_correct_password(self):
        from services.auth import check_credentials

        with self.flask_app.app_context():
            user = check_credentials("active_user", "correct-pw-123")
            self.assertIsNotNone(user)
            self.assertEqual(user.username, "active_user")

    def test_login_route_rejects_suspended_user(self):
        response = self.client.post(
            "/login", data={"username": "suspended_user", "password": "correct-pw-123"},
        )
        # Same generic failure shape as a wrong password (routes/portal.py's
        # existing login() re-renders the form with a 401), never redirects
        # into an authenticated area.
        self.assertEqual(response.status_code, 401)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)

    def test_login_route_accepts_active_user(self):
        response = self.client.post(
            "/login", data={"username": "active_user", "password": "correct-pw-123"},
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIn("user_id", sess)


if __name__ == "__main__":
    unittest.main()
