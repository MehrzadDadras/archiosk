"""
CLAUDE-LANDING-SONIC-01 - the ARCHIOSK startup cue. EXPERIMENTAL.

Product Owner: "a brief, original ARCHIOSK sonic identity... Treat automatic
playback carefully... play once on a deliberate app/landing launch where
platform rules permit; do not replay on every internal navigation; do not loop;
do not interrupt Composer use; respect device/browser audio restrictions;
provide a simple way to mute/disable it if needed; do not request microphone
permission; do not couple it to voice/TTS."

Almost everything asserted here is a PROHIBITION, and that is the point. The
risk with an unrequested sound is not that it fails to play - a silent cue costs
nobody anything - it is that it plays when it should not, plays again and again,
survives being switched off, reaches for a microphone, or quietly resurrects the
spoken welcome the Product Owner explicitly retired in aec1b04 ("Do not play an
automatic welcome sound. Do not automatically speak ARCHIOSK... Voice must
remain opt-in").

So this file mostly proves the cue CANNOT do things.

What it deliberately does NOT prove: that the cue is audible on any real device,
or that it sounds good. Neither is checkable here - the first is a platform
behaviour that only a physical phone can demonstrate, and the second is the
Product Owner's to judge. Nothing in this file should be read as acceptance.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CUE_PATH = _REPO_ROOT / "static" / "js" / "sonic_cue.js"
_LANDING_PATH = _REPO_ROOT / "templates" / "landing.html"
_LANDING_SHELL_PATH = _REPO_ROOT / "templates" / "landing_shell.html"
_LANDING_CSS_PATH = _REPO_ROOT / "static" / "css" / "landing.css"
_VOICE_INPUT_PATH = _REPO_ROOT / "static" / "js" / "voice_input.js"


def _strip_js_comments(source: str) -> str:
    """Drop // and /* */ comments before any scan.

    sonic_cue.js's own header quotes the retired spoken welcome, names
    speechSynthesis, and names getUserMedia - all tokens asserted absent below.
    Scanning raw source would let the explanation of a prohibition satisfy the
    test for that prohibition, which has happened in this repository before.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", source)


class CueIsNotVoiceTests(unittest.TestCase):
    """The retired spoken welcome must not come back through this door."""

    def setUp(self):
        self.code = _strip_js_comments(_CUE_PATH.read_text(encoding="utf-8"))

    def test_nothing_here_can_speak(self):
        for token in ("speechSynthesis", "SpeechSynthesisUtterance", "utterance", "voice.lang"):
            self.assertNotIn(token, self.code, token)

    def test_nothing_here_can_listen(self):
        # "do not request microphone permission" - and a startup cue that
        # triggered a permission prompt on launch would be the single worst
        # first impression this application could make.
        for token in ("getUserMedia", "SpeechRecognition", "MediaRecorder", "mediaDevices"):
            self.assertNotIn(token, self.code, token)

    def test_it_is_not_coupled_to_the_voice_subsystem(self):
        # "do not create a parallel voice/audio subsystem" cuts both ways: this
        # must not duplicate voice_input.js, and it must not reach into it.
        self.assertNotIn("ArchioskVoiceInput", self.code)
        self.assertNotIn("landing-voice", self.code)

    def test_the_voice_input_engine_was_left_alone(self):
        voice = _VOICE_INPUT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("ArchioskSonicCue", voice)
        self.assertNotIn("sonic", voice.lower().replace("supersonic", ""))


class PlaybackRestraintTests(unittest.TestCase):
    def setUp(self):
        self.code = _strip_js_comments(_CUE_PATH.read_text(encoding="utf-8"))

    def test_it_cannot_loop(self):
        # Every oscillator is explicitly stopped, and nothing schedules a repeat.
        self.assertNotIn("loop", self.code)
        self.assertNotIn("setInterval", self.code)
        self.assertEqual(self.code.count(".start("), self.code.count(".stop("))

    def test_it_plays_at_most_once_per_session(self):
        # sessionStorage, not localStorage: it must survive internal navigation
        # within one visit and NOT survive closing the app, or a cold launch
        # would be silent forever after the first one.
        self.assertIn("sessionStorage", self.code)
        self.assertRegex(self.code, r"PLAYED_KEY\s*=\s*'archiosk:sonic-cue-played'")
        self.assertIn("alreadyPlayedThisSession()", self.code)

    def test_the_played_flag_is_set_before_any_sound_is_made(self):
        # If synthesis threw after the oscillators started, a flag set
        # afterwards would leave the cue armed to fire again on the next page.
        play = self.code[self.code.index("function play()"):]
        play = play[:play.index("\n    }")]
        self.assertLess(play.index("markPlayed()"), play.index("synthesise(context)"))

    def test_a_muted_cue_never_creates_an_audio_context(self):
        # Not merely silent - absent. An AudioContext opened and then not used
        # still shows a phone an audio indicator.
        checked = 0
        for function in ("function play()", "function arm()", "function onGesture()"):
            body = self.code[self.code.index(function):]
            body = body[:body.index("\n    }")]
            self.assertIn("isMuted()", body, function)
            if "new AudioCtx()" not in body:
                # arm() deliberately constructs nothing at all - it only
                # registers listeners - which satisfies this more strongly,
                # not less.
                continue
            self.assertLess(body.index("isMuted()"), body.index("new AudioCtx()"), function)
            checked += 1
        self.assertGreater(checked, 0, "no function actually constructs a context")

    def test_reduced_motion_silences_it_entirely(self):
        start = self.code[self.code.index("function start()"):]
        start = start[:start.index("\n    }")]
        self.assertIn("prefers-reduced-motion: reduce", start)
        self.assertLess(start.index("prefers-reduced-motion"), start.index("play()"))

    def test_the_cue_is_short(self):
        # "approximately 1-2 seconds", and "avoid becoming annoying" is mostly a
        # statement about length. Longest scheduled stop, from the numbers.
        arrival = 0.50
        tail = max(0.85, 0.75, 0.55) + 0.05
        self.assertLessEqual(arrival + tail, 2.0)

    def test_the_audio_context_is_released_after_the_cue(self):
        self.assertIn("ctx.close()", self.code)

    def test_peak_amplitude_stays_modest(self):
        # A startup cue that is loud once is a cue people disable forever.
        peaks = [float(m) for m in re.findall(r"envelope\((0\.\d+)", self.code)]
        # The arrival voices carry their peak as the second element of each
        # [frequency, peak, release] triple.
        gains = [float(m[1]) for m in re.findall(r"\[(\d+(?:\.\d+)?), (0\.\d+), (0\.\d+)\]", self.code)]
        self.assertTrue(peaks, "no envelope peaks found")
        self.assertTrue(gains, "no arrival voices found")
        for peak in peaks + gains:
            self.assertLessEqual(peak, 0.2)
        # And the whole cue is scaled down again by the master gain.
        master = float(re.search(r"master\.gain\.value = (0\.\d+)", self.code).group(1))
        self.assertLessEqual(master, 0.6)


class PlatformRestrictionsAreRespectedTests(unittest.TestCase):
    """No autoplay workaround. If the platform says no, the cue waits."""

    def setUp(self):
        self.code = _strip_js_comments(_CUE_PATH.read_text(encoding="utf-8"))

    def test_a_suspended_context_is_never_forced_to_play(self):
        play = self.code[self.code.index("function play()"):]
        play = play[:play.index("\n    }")]
        self.assertIn("state === 'suspended'", play)
        self.assertLess(play.index("state === 'suspended'"), play.index("synthesise(context)"))

    def test_resume_is_only_ever_called_from_a_gesture_handler(self):
        # iOS resumes an AudioContext only inside a real user-gesture handler.
        # A resume() anywhere else is either dead code or an attempted
        # workaround, and both are worth failing on.
        for match in re.finditer(r"context\.resume\(\)", self.code):
            preceding = self.code[:match.start()]
            enclosing = max(
                preceding.rfind("function onGesture()"),
                preceding.rfind("function onGesturePreview()"),
            )
            self.assertGreater(enclosing, 0, "resume() outside a gesture handler")

    def test_there_is_no_silent_unlock_trick(self):
        # The common workaround - play a silent buffer to unlock audio - is
        # exactly the "workaround that violates expected browser behavior" the
        # mission rules out.
        for token in ("createBuffer", "silent", "unlock", "0.wav", "base64"):
            self.assertNotIn(token, self.code, token)

    def test_gesture_listeners_are_removed_after_firing(self):
        # A listener left on document in capture phase for the life of the page
        # is a real cost on every subsequent tap.
        self.assertIn("removeEventListener", self.code)
        on_gesture = self.code[self.code.index("function onGesture()"):]
        on_gesture = on_gesture[:on_gesture.index("\n    }")]
        self.assertIn("disarm()", on_gesture)

    def test_storage_access_never_throws(self):
        # Private mode throws on window.localStorage access itself, before any
        # getItem - which would break the landing page, not just the sound.
        self.assertIn("function storage(kind)", self.code)
        self.assertGreaterEqual(self.code.count("catch (error)"), 6)


class MuteControlTests(unittest.TestCase):
    def setUp(self):
        self.code = _strip_js_comments(_CUE_PATH.read_text(encoding="utf-8"))
        self.landing = _LANDING_PATH.read_text(encoding="utf-8")
        self.css = _LANDING_CSS_PATH.read_text(encoding="utf-8")

    def test_the_control_is_a_real_button(self):
        button = re.search(r"<button[^>]*id=\"landing-sound-toggle\"[^>]*>", self.landing, re.S)
        self.assertIsNotNone(button, "no mute control in landing.html")
        self.assertIn('type="button"', button.group(0))
        self.assertIn("aria-pressed", button.group(0))
        self.assertIn("hidden", button.group(0))

    def test_it_is_revealed_only_where_web_audio_exists(self):
        wire = self.code[self.code.index("function wireToggle()"):]
        wire = wire[:wire.index("\n    }")]
        self.assertIn("!AudioCtx", wire)
        self.assertIn("button.hidden = false", wire)

    def test_the_preference_persists_across_visits(self):
        # localStorage for the PREFERENCE (it must outlive the session) and
        # sessionStorage for the once-per-launch flag - two different lifetimes,
        # deliberately not one store.
        self.assertRegex(self.code, r"MUTED_KEY\s*=\s*'archiosk:sonic-cue-muted'")
        muted = self.code[self.code.index("function isMuted()"):]
        muted = muted[:muted.index("\n    }")]
        self.assertIn("localStorage", muted)

    def test_muting_disarms_a_pending_cue(self):
        # Switching it off while it is waiting for a gesture must actually stop
        # it, not merely stop the next one.
        click = self.code[self.code.index("button.addEventListener('click'"):]
        click = click[:click.index("\n        });")]
        self.assertIn("disarm()", click)

    def test_the_control_carries_its_state_in_words(self):
        render = self.code[self.code.index("function render()"):]
        render = render[:render.index("\n        }")]
        self.assertIn("aria-label", render)
        self.assertIn("aria-pressed", render)

    def test_the_control_has_a_touch_sized_target(self):
        rule = re.search(r"\.landing-sound-toggle\s*\{[^}]*\}", self.css)
        self.assertIsNotNone(rule, "no .landing-sound-toggle rule in landing.css")
        width = int(re.search(r"width:\s*(\d+)px", rule.group(0)).group(1))
        height = int(re.search(r"height:\s*(\d+)px", rule.group(0)).group(1))
        self.assertGreaterEqual(min(width, height), 40)

    def test_the_control_clears_the_home_indicator(self):
        rule = re.search(r"\.landing-sound-toggle\s*\{[^}]*\}", self.css)
        self.assertIn("safe-area-inset-bottom", rule.group(0))

    def test_the_control_has_a_visible_focus_state(self):
        self.assertIn(".landing-sound-toggle:focus-visible", self.css)


class ScopeTests(unittest.TestCase):
    """"Do not interrupt Composer use" - enforced by where the file is loaded."""

    def test_the_cue_loads_on_the_landing_shell_only(self):
        for name in ("landing_shell.html", "auth_shell.html", "gateway_shell.html", "base.html"):
            source = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            expected = name == "landing_shell.html"
            self.assertEqual("sonic_cue.js" in source, expected, name)

    def test_the_authenticated_shell_cannot_reach_it(self):
        # The Composer lives under base.html. If the cue were ever loaded there
        # it could fire mid-sentence, which is the specific thing prohibited.
        base = (_REPO_ROOT / "templates" / "base.html").read_text(encoding="utf-8")
        self.assertNotIn("ArchioskSonicCue", base)
        self.assertNotIn("sonic", base.lower())


class LandingPageStillWorksTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_the_landing_page_renders_with_the_cue_wired(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("sonic_cue.js", html)
        self.assertIn('id="landing-sound-toggle"', html)

    def test_the_control_ships_hidden(self):
        # Server-rendered hidden, so a browser with no Web Audio - and a visitor
        # with JavaScript disabled - never sees a control for a sound that
        # cannot happen.
        html = self.client.get("/").get_data(as_text=True)
        button = re.search(r"<button[^>]*id=\"landing-sound-toggle\"[^>]*>", html, re.S)
        self.assertIn("hidden", button.group(0))

    def test_the_cue_script_is_served_and_versioned(self):
        html = self.client.get("/").get_data(as_text=True)
        src = re.search(r'src="([^"]*sonic_cue\.js[^"]*)"', html).group(1)
        self.assertIn("?v=", src)
        self.assertEqual(self.client.get(src.split("?")[0]).status_code, 200)

    def test_sign_in_is_unaffected(self):
        # "no effect on login" - and the sign-in page must not have acquired a
        # startup sound along the way.
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("sonic_cue.js", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
