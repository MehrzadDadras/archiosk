"""
CLAUDE-VOICE-CONSISTENCY-01 - Sign-In pre-authentication voice.

Covers templates/login.html's new mic control and static/js/login.js's
new client-side-only voice-intent handling (mirrors static/js/landing.js's
own DIRECT_NAV pattern - Level 2/3 of the future Voice authority ladder
only, governance/specified-unbuilt/voice-conversational-presence.md).
No server round-trip exists for this feature at all, so these tests are
markup/JS-source checks (same practical ceiling test_signin_eye_
visibility_01.py already established for this file), not live speech
recognition (impossible to exercise headlessly anyway).
"""
from __future__ import annotations

import unittest
from pathlib import Path


class SigninVoiceMarkupTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_login_page_has_voice_button_and_status(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('data-ui-ref="auth.signin.voice"', body)
        self.assertIn('data-ui-ref="auth.signin.voice.status"', body)
        self.assertIn('id="signin-voice"', body)
        self.assertIn('id="signin-voice-status"', body)

    def test_voice_button_hidden_by_default_server_side(self):
        body = self.client.get("/login").get_data(as_text=True)
        voice_button_start = body.index('id="signin-voice"')
        button_open_tag = body.rindex("<button", 0, voice_button_start)
        button_close_tag = body.index(">", voice_button_start)
        attr_tokens = body[button_open_tag:button_close_tag].replace("=", " ").split()
        self.assertIn("hidden", attr_tokens)

    def test_forgot_password_link_has_a_stable_id_for_the_voice_command(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('id="forgot-password-link"', body)

    def test_voice_engine_script_loads_before_login_js(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn("voice_input.js", body)
        voice_engine_idx = body.index("voice_input.js")
        login_js_idx = body.index("login.js")
        self.assertLess(voice_engine_idx, login_js_idx)

    def test_password_field_is_never_referenced_as_a_voice_dictation_target(self):
        # The password input's own id must never appear as a fill target
        # in login.js - voice here only ever matches fixed commands, it
        # never dictates into any credential field.
        login_js = Path("static/js/login.js").read_text(encoding="utf-8")
        self.assertNotIn("passwordInput.value =", login_js)


class LoginJsVoiceBehaviorTests(unittest.TestCase):
    """Source-level checks on static/js/login.js's new voice-intent
    handling - the same practical ceiling as browser automation for a
    Web Speech API feature that can't be exercised headlessly."""

    def setUp(self):
        self.login_js = Path("static/js/login.js").read_text(encoding="utf-8")

    def test_never_auto_submits_the_form_from_voice(self):
        self.assertNotIn(".submit()", self.login_js)
        self.assertNotIn("signInButton.click()", self.login_js)

    def test_never_performs_text_to_speech_or_reads_back_field_values(self):
        self.assertNotIn("speechSynthesis", self.login_js)
        self.assertNotIn("SpeechSynthesisUtterance", self.login_js)

    def test_uses_the_shared_voice_engine_not_a_third_copy(self):
        self.assertIn("window.ArchioskVoiceInput(", self.login_js)
        # A third copy of the full SpeechRecognition wiring (constructor,
        # error map, on-device availability check) must never come back -
        # that's exactly what the shared engine in voice_input.js exists
        # to prevent.
        self.assertNotIn("new SpeechRecognitionCtor", self.login_js)
        self.assertNotIn("webkitSpeechRecognition", self.login_js)

    def test_forgot_password_and_sign_in_commands_are_present(self):
        self.assertIn("forgot", self.login_js.lower())
        self.assertIn("sign in", self.login_js.lower())


class VoiceInputEngineSourceTests(unittest.TestCase):
    """The shared engine itself (static/js/voice_input.js) - guards the
    consolidation this stage did (case_workspace.js no longer has its own
    copy) and its no-network-call/no-auto-submit contract."""

    def setUp(self):
        self.voice_input_js = Path("static/js/voice_input.js").read_text(encoding="utf-8")
        self.case_workspace_js = Path("static/js/case_workspace.js").read_text(encoding="utf-8")

    def test_engine_never_makes_a_network_call(self):
        self.assertNotIn("fetch(", self.voice_input_js)
        self.assertNotIn("XMLHttpRequest", self.voice_input_js)

    def test_exposes_one_global_entry_point(self):
        self.assertIn("window.ArchioskVoiceInput", self.voice_input_js)

    def test_case_workspace_js_no_longer_duplicates_the_recognition_wiring(self):
        self.assertNotIn("new SpeechRecognitionCtor", self.case_workspace_js)
        self.assertIn("window.ArchioskVoiceInput(", self.case_workspace_js)


if __name__ == "__main__":
    unittest.main()
