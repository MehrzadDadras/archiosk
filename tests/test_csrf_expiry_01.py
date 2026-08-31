"""
CLAUDE-CSRF-EXPIRY-01: an expired or missing CSRF token is a routine idle
session, not a fault, and must not reach the user as Flask-WTF's raw
"Bad Request - The CSRF token has expired" 400 page.

Two audiences, one handler (app.py::_register_error_handlers::csrf_expired):

  - a rendered browser FORM gets a flash and a redirect to sign-in;
  - a page-level fetch() gets structured JSON, because it called
    resp.json() and an HTML redirect would make that throw - which is how
    an expired token previously surfaced as the generic "a network error
    occurred" catch in static/js.

Every test here re-enables CSRF. It is disabled under TestingConfig
(WTF_CSRF_ENABLED=False, config.py) so the suite's hundreds of tokenless
POSTs still work, and it must be patched on the config CLASS before
create_app() runs - the same constraint tests/test_csrf_protection.py
already documents.

/login is the POST target throughout: it is a real non-exempt route that
needs no prior authentication, so each test exercises the handler without
first building a project fixture.

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

_CREDS = {"username": "csrf_expiry_admin", "password": "correct-pw-123"}


class CsrfExpiryHandlerTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        with patch.object(config.TestingConfig, "WTF_CSRF_ENABLED", True):
            self.flask_app = app_module.create_app("testing")

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_csrf_expiry_"))
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            from models import User, db

            db.session.add(User(
                username=_CREDS["username"],
                password_hash=generate_password_hash(_CREDS["password"]),
                role="admin",
            ))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _post(self, **kwargs):
        return self.client.post("/login", data=dict(_CREDS), **kwargs)

    def _is_signed_in(self) -> bool:
        with self.client.session_transaction() as sess:
            return "user_id" in sess

    # -- the HTML branch ---------------------------------------------------

    def test_form_post_redirects_to_login_instead_of_raw_400(self):
        response = self._post()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_form_post_flashes_the_expiry_notice(self):
        self._post()
        with self.client.session_transaction() as sess:
            flashes = sess.get("_flashes") or []
        self.assertEqual(
            flashes, [("error", "Your session expired. Please sign in again.")],
        )

    def test_same_site_referrer_is_preserved_as_next(self):
        response = self._post(headers={"Referer": "http://localhost/projects"})
        self.assertEqual(response.headers["Location"], "/login?next=/projects")

    def test_offsite_referrer_is_never_used_as_next(self):
        # An open redirect would be a worse defect than the raw 400 this
        # handler replaced. portal.login's own _resolve_next_url() would
        # also reject it; this asserts the outer half of that pair.
        response = self._post(headers={"Referer": "https://evil.example/x"})
        self.assertEqual(response.headers["Location"], "/login")

    def test_protocol_relative_referrer_is_rejected(self):
        response = self._post(headers={"Referer": "//evil.example/x"})
        self.assertEqual(response.headers["Location"], "/login")

    # -- the JSON branch ---------------------------------------------------

    def test_fetch_with_stale_csrf_header_gets_structured_json(self):
        # The real case: static/js sets X-CSRFToken on every fetch() and
        # then calls resp.json(). A redirect here is what produced the
        # bogus "network error" message this stage removes.
        response = self._post(headers={"X-CSRFToken": "stale-token"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.headers["Content-Type"].split(";")[0], "application/json")
        self.assertEqual(
            response.get_json(),
            {"error": "csrf_expired", "message": "CSRF token missing or expired"},
        )

    def test_explicit_json_accept_gets_json(self):
        response = self._post(headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "csrf_expired")

    def test_xhr_header_gets_json(self):
        response = self._post(headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "csrf_expired")

    def test_wildcard_accept_stays_html(self):
        # `Accept: */*` scores application/json and text/html EQUALLY, so
        # the comparison in _csrf_wants_json() is strict. A non-strict one
        # would turn every ordinary form POST from a client that sends */*
        # into a JSON reply the browser cannot render.
        response = self._post(headers={"Accept": "*/*"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    def test_browser_accept_stays_html(self):
        response = self._post(headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.assertEqual(response.status_code, 302)

    # -- protection itself is unchanged ------------------------------------

    def test_no_branch_of_the_handler_authenticates_the_session(self):
        """The handler must never become a way around CSRF.

        Both branches are checked, on separate clients, because a friendly
        error path is exactly where an accidental bypass would hide: the
        request already reached a handler that returns 2xx/3xx rather than
        aborting.
        """
        for label, kwargs in (
            ("html form", {}),
            ("fetch with stale token", {"headers": {"X-CSRFToken": "stale-token"}}),
            ("json accept", {"headers": {"Accept": "application/json"}}),
        ):
            with self.subTest(branch=label):
                self.client = self.flask_app.test_client()
                self._post(**kwargs)
                self.assertFalse(
                    self._is_signed_in(),
                    f"CSRF rejection via {label} must not establish a session",
                )

    def test_handler_is_registered_for_csrf_error_specifically(self):
        """Registered against CSRFError, not a blanket 400.

        CSRFError subclasses werkzeug BadRequest, so Flask files it under
        HTTP code 400 keyed by the exception CLASS - which is what makes
        this assertable. Registering the generic BadRequest instead would
        also swallow every ordinary validation fault and report it to the
        user as an expired session: a worse diagnosis than the raw page
        this handler replaces, and silent, because such a build would still
        pass every behavioural test above.
        """
        from flask_wtf.csrf import CSRFError
        from werkzeug.exceptions import BadRequest

        by_code = self.flask_app.error_handler_spec[None]
        self.assertIn(400, by_code, "no 400-class handler is registered at all")
        self.assertIn(CSRFError, by_code[400])
        self.assertNotIn(
            BadRequest, by_code[400],
            "a blanket BadRequest handler would mislabel ordinary 400s as expired sessions",
        )


if __name__ == "__main__":
    unittest.main()
