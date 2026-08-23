"""CLAUDE-RECEPTION-VOICE-01 - the public Reception voice identity.

Intended character: young, energetic, intelligent, clear, curious - warm
without being bubbly, confident without being corporate. Young mission-control
intelligence, not an executive assistant or a theatrical sci-fi character.

What can and cannot be tested here is worth stating plainly. Voice CHARACTER is
subjective and depends on the visitor's own device, so it is evaluated
manually and reported, never asserted. What is asserted is everything
objective: that a voice is actually chosen rather than left to the platform
default, that the delivery parameters express energy rather than the previous
sleepy setting, that no persona name is hard-coded before one is accepted, and
that the whole thing degrades instead of failing where the platform cannot
oblige.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING_JS = ROOT / "static" / "js" / "landing.js"


def _js() -> str:
    return LANDING_JS.read_text(encoding="utf-8")


def _config_block() -> str:
    js = _js()
    start = js.index("var RECEPTION_VOICE = {")
    return js[start: js.index("};", start)]


class ReceptionVoiceIsConfiguredCentrallyTests(unittest.TestCase):
    def test_there_is_one_voice_configuration_block(self):
        self.assertEqual(_js().count("var RECEPTION_VOICE = {"), 1)

    def test_the_utterance_actually_receives_a_chosen_voice(self):
        """Previously no voice was set at all, so every visitor heard whatever
        their platform defaulted to - male on several of them."""
        js = _js()
        self.assertIn("applyReceptionVoice(utterance)", js)
        self.assertIn("utterance.voice = voice", js)

    def test_voice_selection_is_not_patched_per_response(self):
        """One authoritative seam, not per-reply styling."""
        self.assertEqual(_js().count("function applyReceptionVoice"), 1)
        self.assertEqual(_js().count("new SpeechSynthesisUtterance"), 1)


class VoiceCharacterParametersTests(unittest.TestCase):
    def test_delivery_is_energetic_rather_than_slow(self):
        """The previous rate was 0.95 - below natural, which read as a sleepy
        narrator rather than an alert one."""
        rate = float(re.search(r"rate:\s*([\d.]+)", _config_block()).group(1))
        self.assertGreater(rate, 1.0)
        self.assertLess(rate, 1.25, "faster than this stops being intelligible")

    def test_pitch_reads_young_without_becoming_childish(self):
        pitch = float(re.search(r"pitch:\s*([\d.]+)", _config_block()).group(1))
        self.assertGreater(pitch, 1.0)
        self.assertLess(pitch, 1.3, "overdriven pitch produces the bubbly delivery this rules out")

    def test_the_old_sleepy_setting_is_gone(self):
        self.assertNotIn("utterance.rate = 0.95", _js())

    def test_english_locales_are_preferred_without_a_strong_regional_lock(self):
        """Energy and clarity matter more than accent, so several English
        locales are acceptable rather than one enforced regional preset."""
        block = _config_block()
        langs = re.findall(r"'(en-[A-Z]{2}|en)'", block)
        self.assertGreaterEqual(len(langs), 3)
        self.assertIn("en-GB", langs)
        self.assertIn("en-CA", langs)


class NoPersonaNameIsLockedTests(unittest.TestCase):
    """A feminine sci-fi-style name has been discussed but none accepted."""

    def test_the_identity_can_receive_a_name_later(self):
        self.assertRegex(_config_block(), r"name:\s*null")

    def test_no_candidate_name_is_hard_coded_as_product_truth(self):
        js = _js().lower()
        for candidate in ("vera", "mira"):
            with self.subTest(candidate=candidate):
                self.assertNotRegex(js, r"\bname:\s*'" + candidate)
                self.assertNotIn(f"'{candidate}'", js)


class GracefulDegradationTests(unittest.TestCase):
    def test_voice_enumeration_failure_does_not_break_the_greeting(self):
        js = _js()
        block = js[js.index("function pickReceptionVoice"): js.index("function applyReceptionVoice")]
        self.assertIn("try {", block)
        self.assertIn("catch", block)
        self.assertIn("return null", block)

    def test_the_asynchronous_voice_list_is_warmed(self):
        """getVoices() returns an empty list on first call in most engines,
        which is the usual reason a chosen voice silently never applies."""
        self.assertIn("voiceschanged", _js())

    def test_an_unrecognized_device_voice_is_left_to_the_platform(self):
        """Gender is never guessed from an unfamiliar voice name."""
        js = _js()
        block = js[js.index("function pickReceptionVoice"): js.index("function applyReceptionVoice")]
        self.assertIn("/female/i", block)


class PronunciationSurvivesTests(unittest.TestCase):
    def test_archiosk_is_still_spoken_phonetically(self):
        self.assertIn("Ar-kee-osk", _js())

    def test_the_phonetic_spelling_is_still_audio_only(self):
        import app as app_module

        body = app_module.create_app("testing").test_client().get("/").get_data(as_text=True)
        self.assertNotIn("Ar-kee-osk", body)


if __name__ == "__main__":
    unittest.main()
