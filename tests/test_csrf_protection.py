"""
CLAUDE-P27-B: every state-changing route was previously unprotected
against CSRF. CSRFProtect (app.py) plus templates/base.html's
centralized token-injection script (every POST <form> gets a hidden
csrf_token field, added once in one place rather than at each of the
50+ individual <form method="post"> occurrences across this app's
templates).

Disabled under TestingConfig (WTF_CSRF_ENABLED=False, config.py) so
the rest of the suite's hundreds of existing real HTTP POSTs -- none
of which carry a token -- aren't all broken by this. These tests
explicitly re-enable it (must patch the config CLASS before
create_app() runs -- WTF_CSRF_ENABLED, like RATELIMIT_ENABLED, is only
read once at extension-init time, not per request).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import config
from werkzeug.security import generate_password_hash

_CSRF_META_RE = re.compile(r'<meta name="csrf-token" content="([^"]+)">')


class CsrfProtectionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        with patch.object(config.TestingConfig, "WTF_CSRF_ENABLED", True):
            self.flask_app = app_module.create_app("testing")

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_csrf_"))
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            from models import User, db

            admin = User(
                username="csrf_admin", password_hash=generate_password_hash("correct-pw-123"), role="admin",
            )
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _real_token(self) -> str:
        html = self.client.get("/login").get_data(as_text=True)
        match = _CSRF_META_RE.search(html)
        self.assertIsNotNone(match, "expected <meta name=\"csrf-token\"> on every page")
        return match.group(1)

    def test_post_without_token_is_rejected(self):
        response = self.client.post(
            "/login", data={"username": "csrf_admin", "password": "correct-pw-123"},
        )
        self.assertEqual(response.status_code, 400)

    def test_post_with_real_token_succeeds(self):
        token = self._real_token()
        response = self.client.post(
            "/login", data={"username": "csrf_admin", "password": "correct-pw-123", "csrf_token": token},
        )
        self.assertEqual(response.status_code, 302)

    def test_post_with_wrong_token_is_rejected(self):
        response = self.client.post(
            "/login",
            data={"username": "csrf_admin", "password": "correct-pw-123", "csrf_token": "not-the-real-token"},
        )
        self.assertEqual(response.status_code, 400)

    def test_every_page_exposes_the_csrf_meta_tag(self):
        # base.html's <head> is unconditional -- must be present even
        # pre-auth (login page), not only inside the authenticated shell.
        html = self.client.get("/login").get_data(as_text=True)
        self.assertRegex(html, _CSRF_META_RE)

    def test_api_v1_route_is_exempt_from_csrf(self):
        # Documented curl/script usage (README, CLAUDE-P27-B Step 1) --
        # must keep working with just the session cookie, no CSRF token.
        self.client.post("/login", data={"username": "csrf_admin", "password": "correct-pw-123", "csrf_token": self._real_token()})
        response = self.client.post("/api/v1/documents/ingest", data={})
        # 400 (invalid_upload -- no file attached) proves auth+CSRF both
        # passed and the route's OWN validation ran; a CSRF rejection
        # would be 400 with Flask-WTF's own generic HTML error page
        # instead of this route's JSON error body.
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_upload")


if __name__ == "__main__":
    unittest.main()
