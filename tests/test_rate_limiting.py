"""
CLAUDE-P27-B: /login, /forgot-password, /reset-password, /upload, and
/api/v1/documents/ingest previously had no throttling at all --
credential stuffing, reset-spam, and repeated-upload denial-of-wallet
were all unlimited. services/rate_limit.py's Flask-Limiter instance
(in-memory storage, single process -- see that module's own docstring
for the multi-worker caveat) is disabled under TestingConfig
(RATELIMIT_ENABLED=False, config.py) so the rest of the suite's real
HTTP requests across many test methods never accumulate toward a
shared limit. These tests explicitly re-enable it and reset the
limiter's storage first, since it's a process-wide singleton that
would otherwise carry state between test methods too.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from werkzeug.security import generate_password_hash


class RateLimitingTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.rate_limit import limiter

        # RATELIMIT_ENABLED is read once, at limiter.init_app(app) time
        # (inside create_app) -- toggling app.config after the fact is
        # too late, the storage backend is already skipped by then. Must
        # patch the config CLASS before create_app("testing") runs.
        with patch.object(config.TestingConfig, "RATELIMIT_ENABLED", True):
            self.flask_app = app_module.create_app("testing")

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_rate_limit_"))
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            limiter.reset()
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            from models import User, db

            admin = User(
                username="ratelimit_admin", password_hash=generate_password_hash("correct-pw-123"), role="admin",
            )
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        from services.rate_limit import limiter

        with self.flask_app.app_context():
            limiter.reset()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_login_is_throttled_after_ten_attempts_per_minute(self):
        statuses = [
            self.client.post("/login", data={"username": "nobody", "password": "wrong"}).status_code
            for _ in range(11)
        ]
        self.assertNotIn(429, statuses[:10])
        self.assertEqual(statuses[10], 429)

    def test_forgot_password_is_throttled_after_five_attempts_per_hour(self):
        statuses = [
            self.client.post("/forgot-password", data={"email": "nobody@example.com"}).status_code
            for _ in range(6)
        ]
        self.assertNotIn(429, statuses[:5])
        self.assertEqual(statuses[5], 429)

    def test_reset_password_is_throttled_after_ten_attempts_per_hour(self):
        statuses = [
            self.client.post(
                "/reset-password?token=bogus", data={"password": "x", "confirm_password": "x"},
            ).status_code
            for _ in range(11)
        ]
        self.assertNotIn(429, statuses[:10])
        self.assertEqual(statuses[10], 429)

    def test_upload_is_throttled_after_twenty_attempts_per_hour(self):
        self.client.post("/login", data={"username": "ratelimit_admin", "password": "correct-pw-123"})
        statuses = [self.client.post("/upload", data={}).status_code for _ in range(21)]
        self.assertNotIn(429, statuses[:20])
        self.assertEqual(statuses[20], 429)

    def test_api_ingest_is_throttled_after_twenty_attempts_per_hour(self):
        self.client.post("/login", data={"username": "ratelimit_admin", "password": "correct-pw-123"})
        statuses = [self.client.post("/api/v1/documents/ingest", data={}).status_code for _ in range(21)]
        self.assertNotIn(429, statuses[:20])
        self.assertEqual(statuses[20], 429)

    def test_get_requests_are_never_throttled(self):
        # The limiter decorators on /login, /forgot-password,
        # /reset-password are all methods=["POST"] -- rendering the
        # forms themselves (GET) must stay unlimited.
        statuses = [self.client.get("/login").status_code for _ in range(15)]
        self.assertNotIn(429, statuses)


if __name__ == "__main__":
    unittest.main()
