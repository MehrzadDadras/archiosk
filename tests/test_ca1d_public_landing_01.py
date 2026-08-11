"""
CLAUDE-CA1D-PUBLIC-LANDING-01 - Commercial Front Door from the Holodeck
Lineage.

Covers what was actually built: a public, unauthenticated landing page
at "/" (superseding CLAUDE-P40-VW5's own "redirect straight to sign-in"
behavior by explicit later Product Owner decision), an /explore page,
and an honest /start-trial page with no fake submission mechanism -
all served from a new standalone shell (templates/landing_shell.html),
never base.html/auth_shell.html. Existing authenticated behavior at "/"
and direct /login access are both unchanged.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class PublicLandingRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_root_serves_landing_page_for_anonymous_visitor(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("landing-page", body)
        self.assertIn("Archiosk", body)
        self.assertIn("Data Room Intelligence", body)

    def test_landing_page_has_all_three_entry_actions(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-ui-ref="landing.explore"', body)
        self.assertIn('data-ui-ref="landing.start-trial"', body)
        self.assertIn('data-ui-ref="landing.sign-in"', body)
        self.assertIn('href="/explore"', body)
        self.assertIn('href="/start-trial"', body)
        self.assertIn('href="/login"', body)

    def test_landing_page_makes_no_unsupported_capability_claims(self):
        body = self.client.get("/").get_data(as_text=True).lower()
        for forbidden in ("fully automated procurement", "guaranteed compliance", "autonomous decision"):
            self.assertNotIn(forbidden, body)

    def test_landing_page_respects_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        self.assertIn("prefers-reduced-motion", css)
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("prefers-reduced-motion", js)

    def test_explore_page_is_public_and_reachable(self):
        resp = self.client.get("/explore")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("What Archiosk does", body)
        self.assertIn('href="/login"', body)
        self.assertIn('href="/"', body)

    def test_start_trial_page_is_honest_and_has_no_submission_form(self):
        resp = self.client.get("/start-trial")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("isn&rsquo;t self-serve yet", body)
        self.assertNotIn("<form", body)
        self.assertIn('href="/login"', body)

    def test_explore_and_start_trial_never_leak_authenticated_shell(self):
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn("launcher-panel", body)
            self.assertNotIn("workspace-topbar", body)

    def test_direct_login_access_still_works_unchanged(self):
        resp = self.client.get("/login")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("auth-shell-page", body)

    def test_authenticated_root_is_unaffected_by_the_new_landing_page(self):
        from models import User, db
        from werkzeug.security import generate_password_hash
        with self.flask_app.app_context():
            db.session.add(User(username="landing_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "landing_admin"
            sess["role"] = "admin"
        body = client.get("/").get_data(as_text=True)
        self.assertNotIn("landing-page", body)
        self.assertIn("launcher-panel", body)
