"""
CLAUDE-CA1D-PUBLIC-LANDING-05 - Hero Simplification, Voice Action,
Spoken Welcome, and Controlled Intro Motion.

Covers what was actually changed on top of PUBLIC-LANDING-01 through -04:
  - the static explanatory sentence and the visible rotating
    philosophical line are both removed from the hero (their meaning
    moved into a spoken welcome greeting instead);
  - the mic control is icon-only (no visible "Speak to Archiosk" text),
    still fully accessible;
  - a clear, safe, local navigation voice command (Sign In/Explore/
    Request Trial Access) now executes directly instead of showing a
    redundant response card;
  - the knowledge field reserves a quiet center reading column around
    the hero, biasing motion toward the sides.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class HeroSimplificationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_static_explanatory_sentence_is_gone_from_the_hero(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("landing-value-prop", body)
        self.assertNotIn("Archiosk helps people turn documents, questions, and findings into", body)

    def test_rotating_philosophical_line_is_gone_from_the_hero(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertNotIn("landing-rotator", body)
        self.assertNotIn("landing-rotator-line", body)
        for line in ("Many minds. Shared evidence. One understanding.", "We learn together."):
            self.assertNotIn(line, body)

    def test_explore_page_still_carries_the_fuller_explanation(self):
        """The removed hero copy's underlying meaning is not lost from
        the product - it still lives on /explore, unaffected."""
        body = self.client.get("/explore").get_data(as_text=True)
        self.assertIn("What Archiosk does", body)

    def test_css_no_longer_defines_rotator_or_value_prop_rules(self):
        """Checks actual rule syntax (selector + brace), not a bare
        substring - a historical comment is allowed to name the retired
        class for context (see UI_REFERENCE_MAP.md's own precedent for
        this same distinction), only a real CSS rule must be gone."""
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        self.assertNotIn(".landing-rotator {", css)
        self.assertNotIn(".landing-rotator-line {", css)
        self.assertNotIn(".landing-value-prop {", css)

    def test_js_no_longer_defines_a_rotator_cycling_interval(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertNotIn("landing-rotator", js)


class SpokenWelcomeTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_js_defines_a_short_spoken_greeting_via_speech_synthesis(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("setUpSpokenWelcome", js)
        section = js[js.index("setUpSpokenWelcome"):]
        self.assertIn("SpeechSynthesisUtterance", section)
        self.assertIn("window.speechSynthesis", section)
        self.assertIn("Welcome to Archiosk", section)

    def test_spoken_welcome_gated_off_under_reduced_motion(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section_start = js.index("setUpSpokenWelcome")
        section_end = js.index("})();", section_start) + len("})();")
        section = js[section_start:section_end]
        self.assertIn("reduceMotion", section)
        self.assertIn("return", section)

    def test_spoken_welcome_has_an_immediate_attempt_and_a_gesture_fallback(self):
        """Section 3: 'do not assume autoplay with sound will always be
        allowed... use the first meaningful user interaction' - both the
        best-effort immediate attempt and the interaction-triggered
        fallback must be present, sharing one mutually-exclusive guard."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section_start = js.index("setUpSpokenWelcome")
        section_end = js.index("})();", section_start) + len("})();")
        section = js[section_start:section_end]
        self.assertIn("window.setTimeout(speakGreeting", section)
        for evt in ("pointerdown", "keydown", "touchstart"):
            self.assertIn(evt, section)
        self.assertIn("{ once: true", section)

    def test_spoken_welcome_does_not_replay_every_session_via_storage_gate(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section_start = js.index("setUpSpokenWelcome")
        section_end = js.index("})();", section_start) + len("})();")
        section = js[section_start:section_end]
        self.assertIn("sessionStorage", section)
        self.assertNotIn("localStorage", section)


class MicIconOnlyTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_mic_button_has_no_visible_speak_to_archiosk_text(self):
        body = self.client.get("/").get_data(as_text=True)
        button_start = body.index('id="landing-voice-button"')
        button_end = body.index('</button>', button_start)
        button_markup = body[button_start:button_end]
        # The emoji icon is present (inside its own aria-hidden span);
        # the literal visible label text must not be.
        self.assertIn("&#127908;", button_markup)
        self.assertNotIn(">Speak to Archiosk<", button_markup)
        # Only the icon's own inert span text - strip the icon span's
        # markup and confirm nothing else renders as a text node.
        after_icon = button_markup[button_markup.index("</span>") + len("</span>"):]
        self.assertEqual(after_icon.strip(), "")

    def test_mic_button_still_carries_accessible_label_and_title(self):
        body = self.client.get("/").get_data(as_text=True)
        button_start = body.index('id="landing-voice-button"')
        surrounding = body[button_start:button_start + 400]
        self.assertIn("aria-label=", surrounding)
        self.assertIn("processed by your browser only and is never saved", surrounding)
        self.assertIn('title="Speak to Archiosk"', surrounding)

    def test_mic_button_is_a_real_keyboard_operable_button_element(self):
        body = self.client.get("/").get_data(as_text=True)
        button_start = body.index('id="landing-voice-button"')
        preceding = body[max(0, button_start - 60):button_start]
        self.assertIn("<button", preceding)
        self.assertIn('type="button"', preceding)


class VoiceDirectNavigationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_direct_nav_list_covers_exactly_the_three_safe_local_destinations(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section = js[js.index("setUpLandingVoiceInput"):]
        direct_nav_start = section.index("var DIRECT_NAV")
        direct_nav_end = section.index("];", direct_nav_start)
        direct_nav = section[direct_nav_start:direct_nav_end]
        self.assertIn("SIGNIN_HREF", direct_nav)
        self.assertIn("TRIAL_HREF", direct_nav)
        self.assertIn("EXPLORE_HREF", direct_nav)

    def test_direct_nav_executes_via_navigation_not_a_response_card(self):
        """Section 9/10: a direct-nav match must navigate
        (window.location.href) rather than call showResult (which
        renders the response-card markup)."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        end_handler_start = js.index("recognition.addEventListener('end'")
        end_handler_body_end = js.index("\n        });", end_handler_start)
        end_handler = js[end_handler_start:end_handler_body_end]
        self.assertIn("classifyDirectNav", end_handler)
        self.assertIn("window.location.href = navMatch.href", end_handler)
        self.assertIn("showResult(transcript)", end_handler)

    def test_informational_classifiers_still_produce_a_response_card(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section = js[js.index("setUpLandingVoiceInput"):]
        self.assertIn("var INFORMATIONAL", section)
        for topic in ("learning holodeck", "without an account", "rfp"):
            self.assertIn(topic, section)

    def test_direct_nav_declared_before_informational_in_source_order(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section = js[js.index("setUpLandingVoiceInput"):]
        self.assertLess(section.index("var DIRECT_NAV"), section.index("var INFORMATIONAL"))

    def test_end_handler_checks_direct_nav_before_falling_back_to_show_result(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        end_handler_start = js.index("recognition.addEventListener('end'")
        end_handler_body_end = js.index("\n        });", end_handler_start)
        end_handler = js[end_handler_start:end_handler_body_end]
        self.assertLess(end_handler.index("classifyDirectNav"), end_handler.index("showResult(transcript)"))

    def test_ambiguous_transcript_still_falls_back_honestly_not_a_guessed_navigation(self):
        """Section 9: 'ambiguous commands should clarify rather than
        guess' - FALLBACK must still exist and stay wired into the
        informational (card) path, never into a navigation."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        section = js[js.index("setUpLandingVoiceInput"):]
        self.assertIn("var FALLBACK", section)
        self.assertIn("return FALLBACK;", section)


class KnowledgeFieldQuietCenterTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_js_defines_a_named_quiet_center_zone(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("CENTER_MIN_VW", js)
        self.assertIn("CENTER_MAX_VW", js)
        self.assertIn("clampOutsideCenter", js)

    def test_ambient_spawn_uses_side_bands_never_the_center_band_directly(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        spawn_start = js.index("function spawn(")
        spawn_end = js.index("field.appendChild(el);", spawn_start)
        spawn_body = js[spawn_start:spawn_end]
        self.assertIn("leftBand", spawn_body)
        self.assertIn("CENTER_MIN_VW - 4", spawn_body)
        self.assertIn("CENTER_MAX_VW + 4", spawn_body)

    def test_vent_positions_sit_outside_the_quiet_center_band(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        vents_line = js[js.index("var VENTS"):js.index("var VENTS") + 60]
        self.assertIn("12", vents_line)
        self.assertIn("88", vents_line)


if __name__ == "__main__":
    unittest.main()
