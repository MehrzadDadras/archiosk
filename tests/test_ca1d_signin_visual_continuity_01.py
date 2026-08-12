"""
CLAUDE-CA1D-SIGNIN-VISUAL-CONTINUITY-01 - Make Sign In visually belong
to the same public front door.

Covers the reuse of the existing deep-ocean background mechanism
(landing.css's .landing-page/.landing-field-canvas, previously only on
/, /explore, /start-trial) for the standalone auth shell (/login,
/forgot-password, /reset-password) -- the canvas particle-field IIFE
was extracted from landing.js into static/js/ocean_field.js so the auth
shell can reuse it without landing.js's other landing-page-specific
behaviors (knowledge field, spoken welcome, voice input).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class SignInVisualContinuityTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_login_page_loads_landing_css(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn("css/landing.css", body)

    def test_login_page_has_the_ocean_background_markup(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('class="auth-shell-page landing-page"', body)
        self.assertIn('id="landing-field-canvas"', body)

    def test_login_page_no_longer_has_the_old_blueprint_grid(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertNotIn("blueprint-grid", body)

    def test_login_page_loads_ocean_field_js_not_the_full_landing_js(self):
        """The auth shell must reuse only the shared background script,
        never landing.js itself -- loading landing.js here would also
        fire the spoken welcome greeting and other landing-page-only
        behaviors on a sign-in page."""
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn("js/ocean_field.js", body)
        self.assertNotIn("js/landing.js", body)

    def test_login_page_still_has_every_existing_signin_control(self):
        body = self.client.get("/login").get_data(as_text=True)
        for ref in (
            "auth.signin.username", "auth.signin.password",
            "auth.signin.password-toggle", "auth.signin.submit",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body)
        self.assertIn('href="/forgot-password"', body)

    def test_forgot_password_shares_the_same_treatment(self):
        """The shared auth_shell.html means every sign-in-family page
        gets this consistently, not just /login. (/reset-password
        redirects to /forgot-password without a real, valid token -
        exercised separately in services/password_reset.py's own
        tests, not duplicated here.)"""
        body = self.client.get("/forgot-password").get_data(as_text=True)
        self.assertIn("css/landing.css", body)
        self.assertIn('id="landing-field-canvas"', body)
        self.assertNotIn("blueprint-grid", body)

    def test_authentication_behavior_is_unchanged(self):
        """A pure visual-continuity correction must not touch auth
        logic - a wrong password still fails exactly as before (401,
        same as this route's own pre-existing behavior)."""
        resp = self.client.post("/login", data={"username": "nobody", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)
        self.assertIn("Invalid", resp.get_data(as_text=True))


class OceanFieldSharedScriptTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_ocean_field_js_contains_the_canvas_particle_field(self):
        js = self.client.get("/static/js/ocean_field.js").get_data(as_text=True)
        self.assertIn("landing-field-canvas", js)
        self.assertIn("requestAnimationFrame", js)
        self.assertIn("reduceMotion", js)

    def test_ocean_field_js_still_respects_reduced_motion(self):
        js = self.client.get("/static/js/ocean_field.js").get_data(as_text=True)
        self.assertIn("prefers-reduced-motion", js)
        self.assertIn("is-static", js)

    def test_landing_js_no_longer_duplicates_the_canvas_field(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertNotIn("function buildPoints", js)
        self.assertNotIn("function drawField", js)

    def test_landing_page_loads_ocean_field_before_landing_js(self):
        body = self.client.get("/").get_data(as_text=True)
        ocean_index = body.index("js/ocean_field.js")
        landing_index = body.index("js/landing.js")
        self.assertLess(ocean_index, landing_index)

    def test_explore_and_start_trial_still_render_the_canvas(self):
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn('id="landing-field-canvas"', body)
            self.assertIn("js/ocean_field.js", body)


class GatewayCardReThemeTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_gateway_card_compact_redefines_the_text_and_surface_tokens(self):
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        rule_start = css.index(".gateway-card-compact {")
        rule_end = css.index("}", rule_start)
        rule = css[rule_start:rule_end]
        for token in ("--text-primary", "--surface-primary", "--border", "--failure-red"):
            self.assertIn(token, rule)

    def test_card_and_footer_sit_above_the_canvas(self):
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        self.assertIn(".auth-shell-page .gateway-card", css)
        self.assertIn("z-index: 2", css)

    def test_gateway_card_wide_and_plain_gateway_card_unaffected(self):
        """The post-login Gateway (gateway.html/project_chooser.html)
        must keep its original light theme - only .gateway-card-compact
        (the auth_shell.html family) is re-themed."""
        css = self.client.get("/static/css/main.css").get_data(as_text=True)
        wide_rule_start = css.index(".gateway-card-wide {")
        wide_rule_end = css.index("}", wide_rule_start)
        wide_rule = css[wide_rule_start:wide_rule_end]
        self.assertNotIn("--text-primary", wide_rule)


if __name__ == "__main__":
    unittest.main()
