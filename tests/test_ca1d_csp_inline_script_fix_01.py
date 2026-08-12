"""
CLAUDE-CA1D-CSP-INLINE-SCRIPT-FIX-01 - nonce-based Content-Security-Policy
owned by Flask.

Root cause fixed: deploy/nginx.conf's own Content-Security-Policy header
(default-src 'self', no 'unsafe-inline') silently blocked every inline
<script> tag on every page in production -- confirmed via a live-browser
comparison (works with no CSP on the local dev server, fails identically
to a real user report against archiosk.com) and already independently
diagnosed once before for a narrower case
(tests/test_ca1d_reception_fix_01.py's login-password-toggle fix, which
externalized just that one script). This generalizes properly: app.py's
get_csp_nonce()/set_csp_header mint a fresh nonce per request, every
remaining inline <script> tag carries nonce="{{ csp_nonce }}", and the
response's own Content-Security-Policy header advertises the identical
nonce via script-src -- something a static nginx header structurally
cannot do (it can't vary per request).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest


class CspNonceHeaderTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def _nonce_from_header(self, resp):
        header = resp.headers.get("Content-Security-Policy", "")
        match = re.search(r"'nonce-([^']+)'", header)
        self.assertIsNotNone(match, f"no nonce in CSP header: {header!r}")
        return match.group(1)

    def test_every_response_carries_a_csp_header_with_script_src_nonce(self):
        for path in ("/login", "/explore", "/start-trial"):
            resp = self.client.get(path)
            header = resp.headers.get("Content-Security-Policy", "")
            self.assertIn("default-src 'self'", header)
            self.assertIn("script-src 'self' 'nonce-", header)

    def test_header_nonce_matches_every_inline_script_tag_in_the_same_response(self):
        resp = self.client.get("/login")
        nonce = self._nonce_from_header(resp)
        body = resp.get_data(as_text=True)
        inline_script_nonces = re.findall(r'<script nonce="([^"]+)">', body)
        self.assertTrue(inline_script_nonces, "expected at least one inline <script nonce=...> tag")
        for found in inline_script_nonces:
            self.assertEqual(found, nonce)

    def test_no_bare_inline_script_tag_remains_anywhere_in_the_response(self):
        """A <script> tag with neither src= nor nonce= is exactly the
        shape that CSP silently drops in production -- this is the
        regression this whole tranche exists to prevent."""
        for path in ("/login", "/explore", "/gateway"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotRegex(body, r"<script>\s*\n", f"bare inline <script> found on {path}")

    def test_two_separate_requests_get_two_different_nonces(self):
        # A per-request nonce, not a fixed/hardcoded one -- reusing the
        # same nonce across requests would let an attacker who ever
        # learns it replay it against a different response.
        first = self._nonce_from_header(self.client.get("/login"))
        second = self._nonce_from_header(self.client.get("/login"))
        self.assertNotEqual(first, second)


class CsrfAutoInjectionStillWorksTests(unittest.TestCase):
    """The concrete, externally-observable symptom this bug caused: a
    real browser POST to /upload failed with "The CSRF token is
    missing" because base.html's own CSRF-auto-inject script (relied on
    by ~15 templates with no literal csrf_token() field of their own,
    including upload.html) never ran in production."""

    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="csp_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "csp_admin"
            sess["role"] = "admin"

    def test_upload_page_inline_csrf_script_carries_the_response_nonce(self):
        resp = self.client.get("/upload")
        header = resp.headers.get("Content-Security-Policy", "")
        match = re.search(r"'nonce-([^']+)'", header)
        self.assertIsNotNone(match)
        body = resp.get_data(as_text=True)
        self.assertIn(f'nonce="{match.group(1)}"', body)
        # The CSRF-injection script itself (base.html) must be one of
        # the nonced scripts on this page -- upload.html has no literal
        # csrf_token() field of its own, so this is its only source.
        self.assertIn("centralized CSRF token injection", body)


if __name__ == "__main__":
    unittest.main()
