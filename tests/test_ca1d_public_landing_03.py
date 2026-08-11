"""
CLAUDE-CA1D-PUBLIC-LANDING-03 - Signal Prelude + Speak to Archiosk.

Covers what was actually built on top of PUBLIC-LANDING-01/02's already-
deployed motion layer:
  - a brief, one-shot signal-streak prelude before ARCHIOSK's own
    arrival, reduced-motion gated;
  - "Speak to Archiosk" - a landing-page voice-entry path that reuses
    the exact browser-native Web Speech API mechanism, consent wording,
    and hidden-until-feature-detected default already shipped for the
    authenticated composer's own mic button (CLAUDE-POSTCAMEL-VOICE1-
    PRE), routed through a small, deterministic, client-side-only
    keyword lookup - never a generative/LLM call, never a network
    request, never a durable record.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest


class SignalStreakPreludeTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_streak_elements_present_only_on_landing(self):
        """CLAUDE-CA1D-PUBLIC-LANDING-05, Section 6: ONE object only --
        landing-signal-streak-2 removed outright ('no multiple shooting
        lights')."""
        landing_body = self.client.get("/").get_data(as_text=True)
        self.assertIn('landing-signal-streak-1', landing_body)
        self.assertNotIn('landing-signal-streak-2', landing_body)
        self.assertEqual(landing_body.count('landing-signal-streak'), 2)  # base class + the -1 modifier, once each
        self.assertIn('aria-hidden="true"', landing_body)
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn('landing-signal-streak', body)

    def test_streak_css_defines_exactly_one_streak_and_its_keyframe(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        for selector in (".landing-signal-streak", ".landing-signal-streak-1"):
            self.assertIn(selector, css)
        self.assertIn("@keyframes landingSignalStreak1", css)
        self.assertNotIn(".landing-signal-streak-2", css)
        self.assertNotIn("@keyframes landingSignalStreak2", css)

    def test_streak_hidden_outright_under_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-signal-streak { display: none; }", reduced_motion_block)

    def test_wordmark_arrival_delayed_until_after_the_prelude_fully_disappears(self):
        """CLAUDE-CA1D-PUBLIC-LANDING-ANIMATION-CORRECTION-01: the
        wordmark must not begin emerging until strictly after the streak
        (150ms delay + .95s duration = fully gone by 1.1s) has finished
        - a real sequence, not two overlapping effects."""
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        rule_start = css.index(".landing-wordmark {")
        rule_end = css.index("}", rule_start)
        wordmark_rule = css[rule_start:rule_end]
        self.assertIn("landingWordmarkArrival", wordmark_rule)
        self.assertIn("1.3s", wordmark_rule)


class SpeakToArchioskTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_voice_elements_present_only_on_landing_not_explore_or_start_trial(self):
        landing_body = self.client.get("/").get_data(as_text=True)
        for ref in ("landing.voice.button", "landing.voice.status", "landing.voice.result"):
            self.assertIn(f'data-ui-ref="{ref}"', landing_body)
        for path in ("/explore", "/start-trial"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn('data-ui-ref="landing.voice.button"', body)

    def test_voice_button_renders_hidden_by_default_server_side(self):
        """No JS at all -> no false promise of voice input, same
        discipline as the authenticated composer's own mic button."""
        body = self.client.get("/").get_data(as_text=True)
        button_start = body.index('id="landing-voice-button"')
        surrounding = body[max(0, button_start - 200):button_start + 300]
        self.assertIn("hidden", surrounding)
        self.assertIn('type="button"', surrounding)

    def test_voice_button_carries_a_truthful_consent_label(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("processed by your browser only and is never saved", body)

    def test_voice_status_element_renders_empty_with_live_region(self):
        body = self.client.get("/").get_data(as_text=True)
        status_start = body.index('id="landing-voice-status"')
        tag_start = body.rindex('<span', 0, status_start)
        tag_end = body.index('</span>', status_start)
        tag = body[tag_start:tag_end]
        self.assertIn('aria-live="polite"', tag)
        inner_text = body[body.index('>', status_start) + 1:tag_end]
        self.assertEqual(inner_text.strip(), "")

    def test_voice_result_element_hidden_by_default_with_live_region(self):
        body = self.client.get("/").get_data(as_text=True)
        result_start = body.index('id="landing-voice-result"')
        tag_start = body.rindex('<div', 0, result_start)
        surrounding = body[tag_start:result_start + 200]
        self.assertIn('aria-live="polite"', surrounding)
        self.assertIn("hidden", surrounding)

    def test_voice_js_never_calls_recognition_start_outside_the_click_handler(self):
        """Section 5: 'never request microphone permission on page
        load' - recognition.start() lives inside beginListening(), and
        beginListening() itself is only ever invoked from inside the mic
        button's own click handler, never eagerly at setup time."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        voice_section_start = js.index("setUpLandingVoiceInput")
        voice_section = js[voice_section_start:]
        begin_listening_def_start = voice_section.index("function beginListening")
        begin_listening_def_end = voice_section.index("\n    }", begin_listening_def_start)
        begin_listening_body = voice_section[begin_listening_def_start:begin_listening_def_end]
        self.assertIn("recognition.start()", begin_listening_body)
        # Exactly one call site for recognition.start() - never a second,
        # earlier path to it (e.g. eagerly at IIFE setup time).
        self.assertEqual(voice_section.count("recognition.start()"), 1)
        click_handler_start = voice_section.index("addEventListener('click'")
        click_handler_end = voice_section.index("});", click_handler_start)
        self.assertIn("beginListening(useOnDevice);", voice_section[click_handler_start:click_handler_end])
        # No CALL to beginListening(...) anywhere before the click handler
        # - the function's own definition (`function beginListening(...)`)
        # is expected there and is not a call site.
        self.assertNotIn("beginListening(useOnDevice);", voice_section[:click_handler_start])

    def test_voice_js_router_is_bounded_never_a_network_call(self):
        """Section 6/8: a small, deterministic, truthful router - never
        an unconstrained chatbot, never a backend/LLM round trip."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        voice_section_start = js.index("setUpLandingVoiceInput")
        voice_section_end = js.index("})();", voice_section_start) + len("})();")
        voice_section = js[voice_section_start:voice_section_end]
        self.assertIn("DIRECT_NAV", voice_section)
        self.assertIn("INFORMATIONAL", voice_section)
        self.assertIn("FALLBACK", voice_section)
        self.assertNotIn("fetch(", voice_section)
        self.assertNotIn("XMLHttpRequest", voice_section)

    def test_voice_js_hrefs_are_derived_from_real_landing_links_not_hardcoded(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        voice_section = js[js.index("setUpLandingVoiceInput"):]
        self.assertIn('querySelector(\'[data-ui-ref="landing.explore"]\')', voice_section)
        self.assertIn('querySelector(\'[data-ui-ref="landing.start-trial"]\')', voice_section)
        self.assertIn('querySelector(\'[data-ui-ref="landing.sign-in"]\')', voice_section)

    def test_voice_js_skips_setup_gracefully_when_speech_recognition_unsupported(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        voice_section = js[js.index("setUpLandingVoiceInput"):]
        self.assertIn("SpeechRecognitionCtor", voice_section)
        self.assertIn("return", voice_section[:voice_section.index("micButton.hidden = false")])

    def test_voice_pulse_disabled_under_reduced_motion(self):
        css = self.client.get("/static/css/landing.css").get_data(as_text=True)
        reduced_motion_block = css[css.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".landing-voice", reduced_motion_block)
        self.assertIn(".landing-voice-button.voice-input-listening", reduced_motion_block)

    def test_cta_hierarchy_unaffected_voice_is_additional_not_a_replacement(self):
        body = self.client.get("/").get_data(as_text=True)
        for ref in ("landing.explore", "landing.start-trial", "landing.sign-in"):
            self.assertIn(f'data-ui-ref="{ref}"', body)
        # The three real CTAs still render before the voice affordance.
        last_cta = body.index('data-ui-ref="landing.sign-in"')
        voice_index = body.index('id="landing-voice"')
        self.assertLess(last_cta, voice_index)


if __name__ == "__main__":
    unittest.main()
