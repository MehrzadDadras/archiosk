"""CLAUDE-MOBILE-Q-TRIAL-01 Section 6 - voice is opt-in, the mic is findable.

Two requirements that pull against each other, which is why they are guarded
together in one file rather than separately.

The Product Owner's iPhone testing produced both halves at once:

    "Do not play an automatic welcome sound. Do not automatically speak
    ARCHIOSK. The current brand pronunciation is not accepted and wrong
    pronunciation creates distrust. Voice must remain opt-in."

    "However, the mic should be discoverable. Provide a restrained silent
    visual cue in the Composer... never looks like active listening... does
    not request mic permission... respects reduced-motion settings.
    READY and LISTENING states must be clearly distinct."

So: nothing may speak, and yet the microphone must announce itself. The
resolution is that the announcement is silent, visual, once, and shaped so it
cannot be mistaken for the recording state.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS_DIR = ROOT / "static" / "js"
VOICE_JS = (JS_DIR / "voice_input.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
CSS_NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _strip_js_comments(src: str) -> str:
    """Guards here are about behaviour, and this file's comments quote the
    Product Owner's prohibitions verbatim - so a naive "token is absent"
    assertion would be satisfied by the prose forbidding the thing."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<![:\w])//.*$", "", src, flags=re.M)


VOICE_CODE = _strip_js_comments(VOICE_JS)


class NothingSpeaksAnywhereTests(unittest.TestCase):
    def test_no_static_script_can_produce_speech(self):
        """The retirement is repository-wide, not landing-page-local. A second
        synthesis seam appearing in any other script would reintroduce exactly
        what was withdrawn."""
        offenders = []
        for path in JS_DIR.rglob("*.js"):
            body = _strip_js_comments(path.read_text(encoding="utf-8"))
            if "SpeechSynthesisUtterance" in body or "speechSynthesis" in body:
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_recognition_survives_because_input_was_never_the_problem(self):
        """Retiring OUTPUT must not cost the push-to-talk INPUT path, which is
        already opt-in behind a real press."""
        self.assertIn("SpeechRecognitionCtor", VOICE_CODE)


class TheMicAnnouncesItselfSilentlyTests(unittest.TestCase):
    def test_a_cue_is_armed_at_the_moment_the_mic_becomes_available(self):
        """It rides the existing `micButton.hidden = false` seam - the one
        point that already means "this browser can do voice" - rather than a
        second capability check that could disagree with it."""
        self.assertIn("micButton.hidden = false;", VOICE_CODE)
        self.assertIn("announceAvailabilityOnce(micButton)", VOICE_CODE)

    def test_it_lives_in_the_shared_engine_so_every_mic_gets_it_once(self):
        """voice_input.js backs the Composer, Gateway and Sign-In mics. Put
        the cue anywhere else and it would need writing three times."""
        self.assertIn("window.ArchioskVoiceInput", VOICE_JS)
        for other in ("case_workspace.js", "landing.js"):
            body = _strip_js_comments((JS_DIR / other).read_text(encoding="utf-8"))
            self.assertNotIn("announceAvailabilityOnce", body)

    def test_the_cue_is_silent(self):
        """It is a class name and a CSS keyframe. Nothing audible."""
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        for forbidden in ("Audio", "play(", "speak", "SpeechSynthesis", "sound"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, block)

    def test_it_never_asks_for_the_microphone(self):
        """Discoverability must not cost a permission prompt - a prompt is the
        opposite of opt-in."""
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        for forbidden in ("getUserMedia", "mediaDevices", "new SpeechRecognition", "recognition.start"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, block)

    def test_it_happens_once_per_reviewer_not_once_per_page_load(self):
        self.assertIn("'beehive:voice-cue-seen'", VOICE_CODE)
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        self.assertIn("localStorage.getItem(CUE_SEEN_KEY)", block)
        self.assertIn("localStorage.setItem(CUE_SEEN_KEY", block)

    def test_pressing_the_mic_spends_the_cue_immediately(self):
        """A cue that has done its job should stop animating."""
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        self.assertIn("'animationend'", block)
        self.assertIn("'pointerdown'", block)
        self.assertIn("{ once: true }", block)

    def test_reduced_motion_suppresses_it_outright(self):
        """This codebase's established convention is to skip non-essential
        ambient effects, not to slow them down."""
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        self.assertIn("prefers-reduced-motion: reduce", block)
        self.assertRegex(
            CSS_NO_COMMENTS,
            r"@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*\.voice-input-available-cue::after\s*\{\s*animation:\s*none",
        )

    def test_storage_being_unavailable_does_not_kill_the_affordance(self):
        """Private browsing should cost the memory of the cue, not the cue."""
        block = VOICE_CODE[VOICE_CODE.index("function announceAvailabilityOnce"):]
        block = block[: block.index("function setUpVoiceInput")]
        self.assertIn("seen = false;", block)


class ReadyIsNotListeningTests(unittest.TestCase):
    """"READY and LISTENING states must be clearly distinct." They share no
    visual property, and the distinction is enforced by a rule rather than
    left to the two states never coinciding."""

    def _rule(self, selector: str) -> str:
        body = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index(selector) + len(selector):]
        return body[: body.index("}")]

    def test_listening_is_a_solid_fill(self):
        rule = self._rule(".voice-input-button.voice-input-listening {")
        self.assertIn("--attention-amber", rule)
        self.assertNotIn("animation", rule)

    def test_ready_is_a_thin_ring_in_a_different_colour(self):
        rule = self._rule(".voice-input-button.voice-input-available-cue::after {")
        self.assertIn("--machine-blue", rule)
        self.assertIn("animation:", rule)
        self.assertNotIn("--attention-amber", rule)
        # A ring around the control, never a fill of it.
        self.assertNotIn("background", rule)

    def test_the_ready_ring_cannot_render_while_listening(self):
        """Structural, not conventional: even if both classes were somehow set
        at once, the ring is cancelled."""
        rule = self._rule(".voice-input-button.voice-input-listening::after {")
        self.assertIn("display: none", rule)

    def test_the_ready_cue_extinguishes_itself(self):
        """Listening persists while held; READY must not persist at all, or it
        becomes ambient decoration rather than a one-time hint."""
        rule = self._rule(".voice-input-button.voice-input-available-cue::after {")
        self.assertRegex(rule, r"animation:[^;]*\s\d+;")   # a finite iteration count
        self.assertNotIn("infinite", rule)


if __name__ == "__main__":
    unittest.main()
