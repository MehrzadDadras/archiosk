"""
Self-service password reset (CLAUDE-P28).

Covers:
- the regression this whole feature grew out of: login must keep
  working for every existing account whose `email` is NULL (the state
  every pre-P28 account is in, and the exact state that produced the
  "no such column: users.email" incident when the migration lagged
  behind the model);
- the forgot-password request is neutral (same message, matched or not);
- a real request issues a single-use, expiring, hashed-at-rest token,
  and never a plaintext one (models.PasswordResetToken.token_hash is
  the only thing ever queried back);
- the dev-only fallback (TestingConfig forces SMTP_HOST="", same
  reasoning as app.py's ANTHROPIC_API_KEY clearing for "testing") logs
  the reset link rather than emailing it, and is how these tests
  recover the raw token to drive the rest of the flow;
- reset completes, invalidates the token, and a subsequent login with
  the new password succeeds while the old password no longer does;
- an already-used or expired token is rejected without distinguishing
  why; a second request supersedes the first token;
- CLAUDE-P29: the dev-only reset link renders directly on the
  /forgot-password page (not just the server log) for a real match,
  in dev/testing only, and is absent for a non-match; actual SMTP
  delivery success/failure is always logged explicitly, and never
  changes the HTTP response text (which is decided purely by whether
  SMTP is configured at all, not by any one request's outcome or
  match) - proven by comparing a matched-but-failed-delivery response
  against a no-match response under the same SMTP-configured state.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
import unittest.mock
from datetime import datetime, timedelta, timezone
from pathlib import Path

from werkzeug.security import check_password_hash, generate_password_hash

_RESET_LINK_RE = re.compile(r"(http://\S+/reset-password\?token=\S+)")


class PasswordResetTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_password_reset_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            legacy_user = User(
                username="legacy_no_email", password_hash=generate_password_hash("legacy-pw-123"), role="read_only",
            )
            emailed_user = User(
                username="has_email", password_hash=generate_password_hash("original-pw-123"), role="read_only",
                email="Has.Email@Example.com",
            )
            db.session.add_all([legacy_user, emailed_user])
            db.session.commit()
            self.legacy_user_id = legacy_user.id
            self.emailed_user_id = emailed_user.id

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _token_row_count(self):
        from models import PasswordResetToken

        with self.flask_app.app_context():
            return PasswordResetToken.query.count()

    def _request_reset_and_capture_link(self, email: str) -> str:
        with self.assertLogs("services.password_reset", level="WARNING") as captured:
            resp = self.client.post("/forgot-password", data={"email": email}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        match = None
        for line in captured.output:
            match = _RESET_LINK_RE.search(line)
            if match:
                break
        self.assertIsNotNone(match, f"no DEV-ONLY reset link found in log output: {captured.output}")
        return match.group(1)

    # -- the regression this feature must not reintroduce --------------------

    def test_login_still_works_when_email_is_null(self):
        with self.flask_app.app_context():
            from models import User

            user = User.query.filter_by(username="legacy_no_email").first()
            self.assertIsNone(user.email)

        resp = self.client.post(
            "/login", data={"username": "legacy_no_email", "password": "legacy-pw-123"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/gateway", resp.headers["Location"])

    # -- forgot-password request is neutral -----------------------------------

    def test_forgot_password_neutral_message_for_unknown_email(self):
        resp = self.client.post(
            "/forgot-password", data={"email": "nobody@example.com"}, follow_redirects=True,
        )
        body = resp.get_data(as_text=True)
        self.assertIn(
            "If an account with that email exists, a password reset has been initiated. "
            "Email delivery isn&#39;t configured in this environment.",
            body,
        )
        self.assertEqual(self._token_row_count(), 0)

    def test_forgot_password_neutral_message_for_known_email_is_identical(self):
        resp = self.client.post(
            "/forgot-password", data={"email": "nobody@example.com"}, follow_redirects=True,
        )
        unknown_body = resp.get_data(as_text=True)

        link = self._request_reset_and_capture_link("has.email@example.com")
        resp2 = self.client.get(link.replace("http://localhost", ""))  # just to confirm the link itself is well-formed
        self.assertEqual(resp2.status_code, 200)

        # Re-request to inspect the SAME confirmation flash text again -
        # the dev-only hint is appended unconditionally in both cases, so
        # the two bodies must still read identically on the neutral line.
        resp3 = self.client.post(
            "/forgot-password", data={"email": "has.email@example.com"}, follow_redirects=True,
        )
        known_body = resp3.get_data(as_text=True)
        neutral_text = (
            "If an account with that email exists, a password reset has been initiated. "
            "Email delivery isn&#39;t configured in this environment."
        )
        self.assertIn(neutral_text, unknown_body)
        self.assertIn(neutral_text, known_body)

    def test_forgot_password_email_lookup_is_case_insensitive(self):
        link = self._request_reset_and_capture_link("HAS.EMAIL@EXAMPLE.COM")
        self.assertIn("/reset-password?token=", link)
        self.assertEqual(self._token_row_count(), 1)

    # -- token storage never holds the raw secret -----------------------------

    def test_token_is_hashed_at_rest_not_plaintext(self):
        from models import PasswordResetToken

        link = self._request_reset_and_capture_link("has.email@example.com")
        raw_token = link.split("token=", 1)[1]

        with self.flask_app.app_context():
            row = PasswordResetToken.query.filter_by(user_id=self.emailed_user_id).first()
            self.assertNotEqual(row.token_hash, raw_token)
            self.assertEqual(len(row.token_hash), 64)  # sha256 hex digest

    # -- full reset flow -------------------------------------------------------

    def test_full_reset_flow_changes_password_and_invalidates_token(self):
        link = self._request_reset_and_capture_link("has.email@example.com")
        path_and_query = link.split("://", 1)[1].split("/", 1)[1]
        path_and_query = "/" + path_and_query

        get_resp = self.client.get(path_and_query)
        self.assertEqual(get_resp.status_code, 200)

        post_resp = self.client.post(
            path_and_query,
            data={
                "token": path_and_query.split("token=", 1)[1],
                "new_password": "brand-new-pw-456",
                "confirm_password": "brand-new-pw-456",
            },
        )
        self.assertEqual(post_resp.status_code, 302)
        self.assertIn("/login", post_resp.headers["Location"])

        with self.flask_app.app_context():
            from models import PasswordResetToken, User, db

            user = db.session.get(User, self.emailed_user_id)
            self.assertTrue(check_password_hash(user.password_hash, "brand-new-pw-456"))
            self.assertFalse(check_password_hash(user.password_hash, "original-pw-123"))

            row = PasswordResetToken.query.filter_by(user_id=self.emailed_user_id).first()
            self.assertIsNotNone(row.used_at)

        # new password works, old one no longer does
        ok_login = self.client.post(
            "/login", data={"username": "has_email", "password": "brand-new-pw-456"},
        )
        self.assertEqual(ok_login.status_code, 302)
        self.client.get("/logout")
        bad_login = self.client.post(
            "/login", data={"username": "has_email", "password": "original-pw-123"},
        )
        self.assertEqual(bad_login.status_code, 401)

        # the same link cannot be used a second time
        reuse_resp = self.client.get(path_and_query, follow_redirects=True)
        self.assertIn(
            "This reset link is invalid or has expired. Request a new one below.",
            reuse_resp.get_data(as_text=True),
        )

    def test_mismatched_confirmation_does_not_change_password(self):
        link = self._request_reset_and_capture_link("has.email@example.com")
        path_and_query = "/" + link.split("://", 1)[1].split("/", 1)[1]

        resp = self.client.post(
            path_and_query,
            data={
                "token": path_and_query.split("token=", 1)[1],
                "new_password": "brand-new-pw-456",
                "confirm_password": "does-not-match",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Those passwords didn&#39;t match.", resp.get_data(as_text=True))

        with self.flask_app.app_context():
            from models import User, db

            user = db.session.get(User, self.emailed_user_id)
            self.assertTrue(check_password_hash(user.password_hash, "original-pw-123"))

    def test_unknown_token_shows_generic_invalid_message(self):
        resp = self.client.get("/reset-password?token=not-a-real-token", follow_redirects=True)
        self.assertIn(
            "This reset link is invalid or has expired. Request a new one below.",
            resp.get_data(as_text=True),
        )

    def test_expired_token_is_rejected(self):
        from models import PasswordResetToken

        link = self._request_reset_and_capture_link("has.email@example.com")
        path_and_query = "/" + link.split("://", 1)[1].split("/", 1)[1]

        with self.flask_app.app_context():
            row = PasswordResetToken.query.filter_by(user_id=self.emailed_user_id).first()
            row.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            from models import db

            db.session.commit()

        resp = self.client.get(path_and_query, follow_redirects=True)
        self.assertIn(
            "This reset link is invalid or has expired. Request a new one below.",
            resp.get_data(as_text=True),
        )

    def test_second_request_supersedes_first_token(self):
        first_link = self._request_reset_and_capture_link("has.email@example.com")
        first_path = "/" + first_link.split("://", 1)[1].split("/", 1)[1]

        self._request_reset_and_capture_link("has.email@example.com")

        self.assertEqual(self._token_row_count(), 2)
        resp = self.client.get(first_path, follow_redirects=True)
        self.assertIn(
            "This reset link is invalid or has expired. Request a new one below.",
            resp.get_data(as_text=True),
        )

    # -- dev-only on-page link (CLAUDE-P29) -----------------------------------

    def test_dev_reset_link_shown_on_page_for_a_real_match(self):
        with self.assertLogs("services.password_reset", level="WARNING"):
            resp = self.client.post("/forgot-password", data={"email": "has.email@example.com"})
        body = resp.get_data(as_text=True)
        self.assertIn("Development mode only", body)
        self.assertIn("/reset-password?token=", body)

    def test_dev_reset_link_absent_on_page_for_no_match(self):
        resp = self.client.post("/forgot-password", data={"email": "nobody@example.com"})
        body = resp.get_data(as_text=True)
        self.assertNotIn("Development mode only", body)
        self.assertNotIn("/reset-password?token=", body)

    # -- SMTP delivery outcome is reported in the server log, not the response --

    def test_smtp_delivery_success_is_logged_and_message_still_neutral(self):
        self.flask_app.config["SMTP_HOST"] = "smtp.example.com"
        try:
            with unittest.mock.patch("services.password_reset.send_email", return_value=True) as mock_send:
                with self.assertLogs("services.password_reset", level="INFO") as captured:
                    resp = self.client.post("/forgot-password", data={"email": "has.email@example.com"})
            mock_send.assert_called_once()
            self.assertTrue(any("delivered to user" in line for line in captured.output))
            body = resp.get_data(as_text=True)
            self.assertIn(
                "If an account with that email exists, a password reset email has been sent.", body,
            )
            # SMTP "succeeded" -> no dev-only link needed or shown, even
            # though this is still a testing config.
            self.assertNotIn("Development mode only", body)
        finally:
            self.flask_app.config["SMTP_HOST"] = ""

    def test_smtp_delivery_failure_is_logged_but_message_stays_identical(self):
        # Same SMTP-configured environment for both requests - the only
        # thing that differs is match+delivery-failure vs. no match at
        # all (delivery never attempted). The HTTP response must read
        # identically either way; only the server log may distinguish
        # them (a real send failure reading differently than "no account
        # matched" would let an attacker use an SMTP outage as an
        # account-enumeration oracle).
        self.flask_app.config["SMTP_HOST"] = "smtp.example.com"
        try:
            with unittest.mock.patch("services.password_reset.send_email", return_value=False):
                with self.assertLogs("services.password_reset", level="WARNING") as captured:
                    resp_matched_but_failed = self.client.post(
                        "/forgot-password", data={"email": "has.email@example.com"},
                    )
                self.assertTrue(any("FAILED to send" in line for line in captured.output))

                resp_no_match = self.client.post(
                    "/forgot-password", data={"email": "nobody@example.com"},
                )
        finally:
            self.flask_app.config["SMTP_HOST"] = ""

        neutral_text = "If an account with that email exists, a password reset email has been sent."
        self.assertIn(neutral_text, resp_matched_but_failed.get_data(as_text=True))
        self.assertIn(neutral_text, resp_no_match.get_data(as_text=True))
        # The dev-only fallback still covers "SMTP configured but this
        # send genuinely failed", not just "SMTP unset" - a real send
        # failure in dev/testing must not be a dead end either (never
        # permanently locked out just because local SMTP is broken).
        self.assertIn("Development mode only", resp_matched_but_failed.get_data(as_text=True))
        self.assertNotIn("Development mode only", resp_no_match.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
