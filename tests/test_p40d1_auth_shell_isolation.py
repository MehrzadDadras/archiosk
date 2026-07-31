"""
CLAUDE-P40-D1 - Authentication-surface isolation.

A real product-owner screenshot showed /login rendered inside the
authenticated application shell (full left navigation, real project
names visible) - a non-disclosure/authentication-boundary defect, not
merely styling. Root cause: `login()`'s GET handler rendered
login.html unconditionally regardless of session state, and
login.html/forgot_password.html/reset_password.html all extended
gateway_base.html -> base.html, which renders the real side-rail nav
(querying the live project-listing store) whenever `authenticated` is
true - which it is for an already-signed-in session hitting /login
directly (e.g. a stale bookmark, a second tab).

Fix, two parts:
  - templates/auth_shell.html: a genuinely standalone shell for
    /login, /forgot-password, /reset-password that never extends
    base.html at all - project nav markup does not exist in these
    templates to leak, CSS-hiding is not what makes this safe.
  - app.py's inject_globals(): guards nav_recent_projects/authenticated/
    is_admin for these three routes specifically, so even the context
    data (and the store query that produces it) is absent, not merely
    unrendered.
  - routes/portal.py's login(): an already-authenticated request is
    redirected to the landing route instead of ever rendering the form.
  - routes/portal.py's logout(): returns to the isolated /login page,
    not the general '/' landing page.

Every ingestion call in this file spies on BHiveParser.parse rather
than letting it run for real (see tests/test_project_access_control.py's
own identical convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_DISTINCTIVE_PROJECT_NAME = "Riverside Confidential Bridge Replacement"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseAuthShellTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40d1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="shelluser", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="shelluser", project_name=_DISTINCTIVE_PROJECT_NAME)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "a.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _assert_no_project_or_nav_leakage(self, body: str):
        for marker in (
            _DISTINCTIVE_PROJECT_NAME,
            self.doc.project_id,
            "side-rail", "nav-toggle", "search-toggle",
            "New Project", "Security", "side-rail-tree",
            "app-shell", "app-main",
        ):
            self.assertNotIn(marker, body, f"auth shell page leaked: {marker!r}")


class AnonymousAuthShellIsolationTests(_BaseAuthShellTestCase):
    def test_anonymous_login_contains_no_project_or_nav_data(self):
        resp = self.flask_app.test_client().get("/login")
        self.assertEqual(resp.status_code, 200)
        self._assert_no_project_or_nav_leakage(resp.get_data(as_text=True))

    def test_anonymous_login_does_not_call_the_project_listing_store(self):
        with patch("app._nav_recent_projects") as mock_nav:
            resp = self.flask_app.test_client().get("/login")
        self.assertEqual(resp.status_code, 200)
        mock_nav.assert_not_called()

    def test_anonymous_forgot_password_has_the_same_isolation(self):
        resp = self.flask_app.test_client().get("/forgot-password")
        self.assertEqual(resp.status_code, 200)
        self._assert_no_project_or_nav_leakage(resp.get_data(as_text=True))

    def test_login_card_is_centered_with_no_sidebar_markup(self):
        resp = self.flask_app.test_client().get("/login")
        body = resp.get_data(as_text=True)
        self.assertIn("auth-shell-page", body)
        self.assertNotIn("app-shell", body)
        self.assertIn("Sign in", body)
        self.assertIn("Archiosk", body)
        self.assertIn("Forgot password", body)


class AuthenticatedAuthShellIsolationTests(_BaseAuthShellTestCase):
    """The exact scenario the product-owner screenshot showed: an
    already-authenticated session requesting /login."""

    def test_authenticated_login_redirects_instead_of_rendering_the_form(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/login", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        body = resp.get_data(as_text=True)
        self._assert_no_project_or_nav_leakage(body)

    def test_authenticated_login_does_not_call_the_project_listing_store(self):
        client = self._client_as("shelluser", 1)
        with patch("app._nav_recent_projects") as mock_nav:
            client.get("/login", follow_redirects=False)
        mock_nav.assert_not_called()

    def test_authenticated_login_follows_next_when_same_site(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/login?next=/projects", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/projects"))

    def test_authenticated_login_ignores_an_off_site_next(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/login?next=https://evil.example/steal", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("evil.example", resp.headers["Location"])

    def test_authenticated_forgot_password_still_gets_the_isolated_shell(self):
        # Unlike /login, /forgot-password does not auto-redirect an
        # authenticated session (a legitimate flow: a signed-in user in
        # a stale second tab following a real reset-email link) - it
        # must still be isolated, not merely unauthenticated-only-safe.
        client = self._client_as("shelluser", 1)
        resp = client.get("/forgot-password")
        self.assertEqual(resp.status_code, 200)
        self._assert_no_project_or_nav_leakage(resp.get_data(as_text=True))

    def test_authenticated_forgot_password_does_not_call_the_project_listing_store(self):
        client = self._client_as("shelluser", 1)
        with patch("app._nav_recent_projects") as mock_nav:
            client.get("/forgot-password")
        mock_nav.assert_not_called()


class SignOutAndSessionIsolationTests(_BaseAuthShellTestCase):
    def test_sign_out_returns_the_isolated_sign_in_page(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/logout", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.headers["Location"].endswith("/login"))

        followed = client.get("/logout", follow_redirects=True)
        body = followed.get_data(as_text=True)
        self._assert_no_project_or_nav_leakage(body)
        self.assertIn("Sign in", body)

    def test_sign_out_actually_clears_the_session(self):
        client = self._client_as("shelluser", 1)
        client.get("/logout")
        resp = client.get("/projects", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

    def test_expired_or_missing_session_reaches_the_isolated_shell_without_leakage(self):
        # No session at all (the practical equivalent of an expired
        # signed cookie - Flask's session store is stateless, so an
        # expired session and no session are indistinguishable server-
        # side) hitting a protected route must redirect to the isolated
        # shell, never retain or reveal the previously viewed project.
        client = self.flask_app.test_client()
        resp = client.get(f"/projects/{self.doc.project_id}/workspace", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

        followed = client.get(resp.headers["Location"])
        self._assert_no_project_or_nav_leakage(followed.get_data(as_text=True))


class AuthenticatedShellStillRendersNormallyTests(_BaseAuthShellTestCase):
    """Sanity check: this stage must not have accidentally broken the
    real authenticated app shell for ordinary pages."""

    def test_authenticated_gateway_page_still_shows_the_app_shell(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/gateway")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("app-shell", body)
        self.assertIn("side-rail", body)

    def test_authenticated_home_page_lists_the_real_project(self):
        client = self._client_as("shelluser", 1)
        resp = client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(_DISTINCTIVE_PROJECT_NAME, resp.get_data(as_text=True))


class ProjectAuthorizationUnaffectedTests(_BaseAuthShellTestCase):
    """P32 non-disclosure and project-level authorization must be
    completely unaffected by this stage's template/context changes."""

    def setUp(self):
        super().setUp()
        from models import User, db

        with self.flask_app.app_context():
            db.session.add(User(username="p40d1_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def test_non_owner_still_gets_404_not_disclosure(self):
        client = self._client_as("p40d1_outsider", 2, role="read_only")
        resp = client.get(f"/projects/{self.doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 404)

    def test_owner_access_is_unaffected(self):
        client = self._client_as("shelluser", 1)
        resp = client.get(f"/projects/{self.doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
