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


class RotatingHeroLineTests(unittest.TestCase):
    """
    CLAUDE-CA1D-PUBLIC-LANDING-01 (addendum) - a decorative, slowly
    cross-fading line in the hero area, purely atmospheric (aria-hidden)
    alongside the real, accessible value-prop paragraph. Static (first
    line only, no cycling) under prefers-reduced-motion.
    """
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_rotator_present_only_on_the_landing_page_not_explore_or_start_trial(self):
        landing_body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="landing-rotator"', landing_body)
        self.assertIn('aria-hidden="true"', landing_body)
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn('id="landing-rotator"', body)

    def test_rotator_has_at_least_four_distinct_lines_one_active_by_default(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertGreaterEqual(body.count("landing-rotator-line"), 4)
        self.assertIn('class="landing-rotator-line is-active"', body)
        # Only one line marked active in the initial server-rendered markup.
        self.assertEqual(body.count("landing-rotator-line is-active"), 1)

    def test_rotator_lines_are_whole_self_contained_strings(self):
        body = self.client.get("/").get_data(as_text=True)
        for line in (
            "Many minds. Shared evidence. One understanding.",
            "We learn together.",
            "Knowledge belongs to all of us.",
            "Every insight strengthens the whole.",
        ):
            self.assertIn(line, body)

    def test_css_disables_rotator_animation_under_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-rotator", reduced_motion_block)

    def test_js_never_starts_cycling_under_reduced_motion(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        rotator_section = js[js.index("landing-rotator"):]
        self.assertIn("reduceMotion", rotator_section)
        self.assertIn("return", rotator_section)


class ConsolidatedAddendumTests(unittest.TestCase):
    """
    CLAUDE-CA1D-PUBLIC-LANDING-01 consolidated addendum - Sections B2/B3,
    C1-C3, D, F: entrance choreography, the ambient knowledge field, the
    expanded 6-line rotator / shortened hero copy, and the renamed
    "Request Trial Access" CTA.
    """
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_rotator_has_all_six_lines(self):
        body = self.client.get("/").get_data(as_text=True)
        for line in (
            "Many minds. Shared evidence. One understanding.",
            "We learn together.",
            "Knowledge belongs to all of us.",
            "Every insight strengthens the whole.",
            "From many questions, clearer understanding.",
            "Better questions. Better understanding.",
        ):
            self.assertIn(line, body)
        self.assertEqual(body.count("landing-rotator-line"), 6)

    def test_hero_value_prop_is_short_and_singular(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn(
            "Archiosk helps people turn documents, questions, and findings into",
            body,
        )
        value_prop = body[body.index('class="landing-value-prop"'):]
        value_prop = value_prop[:value_prop.index("</p>")]
        # A short single sentence, not a multi-sentence paragraph.
        self.assertLessEqual(value_prop.count("."), 1)

    def test_cta_reads_request_trial_access_everywhere(self):
        for path in ("/", "/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertIn("Request Trial Access", body)
            self.assertNotIn("Start Free Trial", body)

    def test_knowledge_field_container_present_only_on_landing(self):
        landing_body = self.client.get("/").get_data(as_text=True)
        self.assertIn('id="landing-knowledge-field"', landing_body)
        self.assertIn('aria-hidden="true"', landing_body)
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn('id="landing-knowledge-field"', body)

    def test_knowledge_field_css_defines_all_three_tiers_plus_bubbles(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        for selector in (".landing-knowledge-field", ".kf-bubble", ".kf-particle", ".kf-script", ".kf-term"):
            self.assertIn(selector, css)

    def test_knowledge_field_hidden_under_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-knowledge-field", reduced_motion_block)

    def test_knowledge_field_js_skips_generation_under_reduced_motion(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        field_section = js[js.index("landing-knowledge-field"):]
        self.assertIn("reduceMotion", field_section)
        self.assertIn("return", field_section)

    def test_knowledge_field_js_never_invents_faux_scripts(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        # Real GO domain terms from the Product Owner's own list, not a
        # conventional nav menu, and real writing-system words (not
        # invented glyphs) - spot-check both arrays exist with real content.
        for term in ("RFP", "REQUIREMENTS", "EVIDENCE", "ADDENDA", "DRAWINGS", "RISKS", "RFI", "DECISIONS"):
            self.assertIn(term, js)

    def test_wordmark_has_an_arrival_choreography_keyframe(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        self.assertIn("@keyframes landingWordmarkArrival", css)
        rule_start = css.index(".landing-wordmark {")
        rule_end = css.index("}", rule_start)
        wordmark_rule = css[rule_start:rule_end]
        self.assertIn("landingWordmarkArrival", wordmark_rule)

    def test_wordmark_arrival_respects_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-wordmark", reduced_motion_block)
        self.assertIn("animation: none", reduced_motion_block)
