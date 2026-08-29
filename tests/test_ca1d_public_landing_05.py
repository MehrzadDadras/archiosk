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


class NothingSpeaksWithoutBeingAskedTests(unittest.TestCase):
    """CLAUDE-MOBILE-Q-TRIAL-01, Section 6 retired the automatic spoken
    welcome this class used to guard.

    Product Owner, explicit: "Do not play an automatic welcome sound. Do not
    automatically speak ARCHIOSK. The current brand pronunciation is not
    accepted and wrong pronunciation creates distrust. Voice must remain
    opt-in."

    Inverted rather than deleted. The risk worth guarding is no longer "the
    greeting might break" but "the greeting might come back", and an empty
    space in the suite guards nothing.
    """

    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_the_landing_page_has_no_speech_synthesis_at_all(self):
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        for gone in ("setUpSpokenWelcome", "SpeechSynthesisUtterance",
                     "speechSynthesis", "speakGreeting"):
            with self.subTest(token=gone):
                self.assertNotIn(gone, js)

    def test_the_rejected_pronunciation_is_not_kept_on_disk(self):
        """Retiring the trigger but leaving the phonetic spelling behind would
        preserve the exact thing that was rejected, ready to be re-armed."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertNotIn("Ar-kee-osk", js)
        self.assertNotIn("RECEPTION_VOICE", js)

    def test_no_page_load_timer_or_first_gesture_can_start_audio(self):
        """Both old delivery paths - the immediate attempt and the
        first-interaction fallback - are gone, not merely disconnected."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertNotIn("window.setTimeout(speakGreeting", js)
        self.assertNotIn("archiosk-welcome-spoken", js)

    def test_voice_input_survives_because_it_is_opt_in(self):
        """"Voice must remain opt-in" retires OUTPUT, not INPUT. Push-to-talk
        recognition is already gated behind a real press and never speaks.

        CLAUDE-VOICE-CONSISTENCY-02: the landing page still has recognition,
        it just no longer carries its own copy of the recogniser - so the
        surviving INPUT path is asserted through the seam it now uses."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        self.assertIn("window.ArchioskVoiceInput", js)
        engine = self.client.get("/static/js/voice_input.js").get_data(as_text=True)
        self.assertIn("SpeechRecognitionCtor", engine)

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

    @staticmethod
    def _end_handler(js):
        """The block that decides what a finished sentence MEANS.

        CLAUDE-VOICE-CONSISTENCY-02 moved this out of a locally-owned
        `recognition.addEventListener('end')` and into the `onEnd` callback
        the shared engine invokes. Same code, same ordering requirement, one
        recogniser instead of two - so these tests follow it rather than
        asserting where it used to sit."""
        start = js.index("onEnd: function ()")
        return js[start:js.index("\n        },", start)]

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
        end_handler = self._end_handler(js)
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
        end_handler = self._end_handler(js)
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
        """CLAUDE-CA1D-LANDING-BALANCE-01 replaced the single wide
        uniform-range side band with an equal-thirds AMBIENT_BANDS_LEFT
        model (see tests/test_ca1d_landing_balance_01.py for that
        tranche's own dedicated coverage) - this still only needs to
        confirm the center column itself stays excluded from ambient
        placement."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        spawn_start = js.index("function spawn(")
        spawn_end = js.index("field.appendChild(el);", spawn_start)
        spawn_body = js[spawn_start:spawn_end]
        self.assertIn("leftBand", spawn_body)
        self.assertIn("pickAmbientLeftVw()", spawn_body)
        self.assertIn("CENTER_MIN_VW - 2", js)  # innermost ambient sub-band boundary

    def test_vent_positions_sit_outside_the_quiet_center_band(self):
        """CLAUDE-CA1D-LANDING-BALANCE-01 moved VENTS further toward
        the true edges (was 12/88) - still just confirming they sit
        well clear of the CENTER_MIN_VW/CENTER_MAX_VW column."""
        js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        vents_line = js[js.index("var VENTS"):js.index("var VENTS") + 60]
        self.assertIn("7", vents_line)
        self.assertIn("93", vents_line)


class SpokenNavigationSurvivesTranscriptionTests(unittest.TestCase):
    """CLAUDE-LANDING-VOICE-VARIANTS-01. A Product Owner SPOKE "sign in" to the
    landing page and got the fallback card: "I'm not sure yet - here's a quick
    look at what Archiosk does."

    The recogniser returned "sing in", which is what every recogniser does with
    that phrase, and the pattern required the exact spelling. The same failure
    as "Goodmorning" earlier the same week: an exact-phrase list meeting real
    human input.

    These assert the PATTERN text rather than running JS, which this suite
    cannot do - but the pattern is the thing that was wrong.
    """

    def setUp(self):
        import app as app_module
        self.client = app_module.create_app("testing").test_client()
        self.js = self.client.get("/static/js/landing.js").get_data(as_text=True)
        block = self.js[self.js.index("var DIRECT_NAV = ["):]
        self.direct_nav = block[: block.index("];")]

    def _signin_pattern(self):
        import re

        line = next(l for l in self.direct_nav.splitlines() if "SIGNIN_HREF" in l)
        return re.compile(line[line.index("/") + 1: line.rindex("/i")], re.I)

    def test_the_homophone_that_was_reported_now_matches(self):
        self.assertTrue(self._signin_pattern().search("sing in"))

    def test_the_original_spelling_still_matches(self):
        """The first attempt at this fix wrote s[iy]ng? - which matches "sing"
        and NOT "sign", fixing the reported case by breaking the one that
        already worked. sign is s-i-g-n; sing is s-i-n-g."""
        self.assertTrue(self._signin_pattern().search("sign in"))

    def test_separator_variants_match(self):
        for spoken in ("signin", "sign-in", "Sign in.", "log in", "log me in", "my account"):
            with self.subTest(transcript=spoken):
                self.assertTrue(self._signin_pattern().search(spoken))

    def test_sign_up_is_not_claimed_by_sign_in(self):
        """A one-letter difference that means the opposite thing - and the
        widened pattern must not swallow it."""
        self.assertFalse(self._signin_pattern().search("sign up"))

    def test_no_new_destination_was_added(self):
        """The boundary of three safe, local, reversible destinations is
        unchanged - only the spellings that reach them."""
        self.assertEqual(self.direct_nav.count("href:"), 3)


if __name__ == "__main__":
    unittest.main()
