"""
CLAUDE-DEVELOPER-COMPOSER-IMAGE-01 - screenshots into the Developer Composer.

Product Owner, live: "I suppose to be able in developer mode take a screen shot
and paste it into Composer so you can see." They reached for the obvious thing
and it was not there - the Developer Composer looked like Composer and accepted
strictly less, which is precisely the drift
tests/test_composer_convergence_01.py exists to catch.

WHAT THIS IS NOT

It is not the workspace Composer's attachment apparatus. No Make-Q, no
Add-to-Q, no capture crop/review, no EXIF/GPS evidence handling - those are
project-evidence flows, and Developer Mode has no project and files nothing.

The image rides ONE turn to the model. It is never written to disk, never
registered as a Source, never given provenance, and never persisted in the
conversation record. Developer Mode is orientation-only and this must not
quietly change that; several tests below exist only to hold that line.

Hermetic: the model boundary is always spied, never called.
"""
from __future__ import annotations

import base64
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS = _REPO_ROOT / "static" / "js" / "developer_composer_image.js"

# A real 1x1 PNG, so the data: URL under test is genuinely an image.
_PNG_B64 = ("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQ"
            "DwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
_PNG_DATA_URL = "data:image/png;base64," + _PNG_B64


def _strip_js_comments(source: str) -> str:
    """Declarations only - every negative assertion below runs against this.

    This module's own header explains that it deliberately excludes Make-Q and
    Add-to-Q, and that sentence satisfies an assertion looking for their
    absence: the prose standing in for the thing it promises is not there.
    """
    import re

    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return "\n".join(line for line in source.splitlines()
                     if not line.strip().startswith("//"))


class _Result:
    """Shape of ProjectQAResult that the route actually reads."""

    def __init__(self, ran=True, answer="I can see the screenshot."):
        self.ran = ran
        self.answer = answer
        self.provider = "spy"
        self.model = "spy-model"
        self.needs_clarification = False
        self.skipped_reason = None
        self.river_actions = []


class ParsingWhatTheClientSends(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")

    def _parse(self, value):
        from routes.portal import _developer_composer_image

        with self.flask_app.test_request_context(
                "/developer-composer", method="POST", data={"image_data_url": value}):
            return _developer_composer_image()

    def test_a_real_png_data_url_is_accepted(self):
        encoded, media_type = self._parse(_PNG_DATA_URL)
        self.assertEqual(media_type, "image/png")
        self.assertEqual(encoded, _PNG_B64)
        base64.b64decode(encoded)  # must be genuinely decodable

    def test_jpeg_is_accepted(self):
        _encoded, media_type = self._parse("data:image/jpeg;base64,/9j/4AAQ")
        self.assertEqual(media_type, "image/jpeg")

    def test_a_non_image_data_url_is_refused(self):
        # An attacker-supplied or mistyped payload must not reach the model as
        # if it were a picture.
        for hostile in ["data:text/html;base64,PHNjcmlwdD4=",
                        "data:application/pdf;base64,JVBER",
                        "javascript:alert(1)",
                        "https://example.com/x.png",
                        "data:image/svg+xml;base64,PHN2Zz4="]:
            with self.subTest(hostile=hostile):
                self.assertEqual(self._parse(hostile), (None, None))

    def test_malformed_input_returns_nothing_rather_than_raising(self):
        # A screenshot that will not parse is a reason to answer the text
        # without it, never to fail the whole turn.
        for bad in ["", "   ", "data:image/png;base64,", "data:image/png"]:
            with self.subTest(bad=bad):
                self.assertEqual(self._parse(bad), (None, None))


class _DeveloperModeCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="dev_admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "dev_admin"
            sess["role"] = "admin"
            sess["developer_mode"] = True

    def _post(self, **data):
        return self.client.post("/developer-composer", data=data)


class TheImageReachesTheModel(_DeveloperModeCase):
    def test_a_pasted_screenshot_is_passed_to_the_shared_gateway(self):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return _Result()

        with patch("routes.portal.answer_application_question", side_effect=spy):
            resp = self._post(message="what is wrong with this screen?",
                              image_data_url=_PNG_DATA_URL)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["image_base64"], _PNG_B64)
        self.assertEqual(calls[0]["image_media_type"], "image/png")

    def test_a_screenshot_alone_is_a_complete_turn(self):
        # Requiring text alongside an image would mean typing "look at this" to
        # say nothing. Before this change an image with no message was dropped
        # at the empty-text guard.
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return _Result()

        with patch("routes.portal.answer_application_question", side_effect=spy):
            resp = self._post(message="", image_data_url=_PNG_DATA_URL)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(len(calls), 1, "an image-only turn was dropped")
        self.assertTrue(calls[0]["question"].strip())
        self.assertEqual(calls[0]["image_base64"], _PNG_B64)

    def test_an_empty_turn_with_no_image_still_does_nothing(self):
        calls = []
        with patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: calls.append(k) or _Result()):
            self._post(message="", image_data_url="")
        self.assertEqual(calls, [])

    def test_the_text_path_is_unchanged_when_no_image_is_attached(self):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return _Result()

        with patch("routes.portal.answer_application_question", side_effect=spy):
            self._post(message="how does ingestion work?")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0]["image_base64"])
        self.assertIsNone(calls[0]["image_media_type"])

    def test_a_malformed_image_still_answers_the_question(self):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return _Result()

        with patch("routes.portal.answer_application_question", side_effect=spy):
            self._post(message="real question", image_data_url="data:text/html;base64,PHA+")
        self.assertEqual(len(calls), 1)
        self.assertIsNone(calls[0]["image_base64"])
        self.assertEqual(calls[0]["question"], "real question")


class TheModelIsToldAnImageIsPresent(unittest.TestCase):
    """A vision turn whose prompt never mentions the image answers as if blind."""

    def _prompt_for(self, image_base64):
        import services.project_qa as qa

        captured = {}

        class _Outcome:
            ran = True
            parsed = {"answer": "ok"}
            skipped_reason = None
            provider = "spy"
            model = "spy-model"
            requested_at = "2026-08-26T00:00:00Z"

        def spy(**kwargs):
            captured.update(kwargs)
            return _Outcome()

        with patch.object(qa, "call_llm_json", side_effect=spy):
            qa.answer_application_question("what is this?", image_base64=image_base64,
                                           image_media_type="image/png")
        return captured

    def test_the_prompt_names_the_attached_image(self):
        captured = self._prompt_for(_PNG_B64)
        self.assertIn("image is attached", captured["user_prompt"].lower())
        self.assertEqual(captured["image_base64"], _PNG_B64)

    def test_it_is_told_to_say_when_the_image_does_not_show_the_answer(self):
        captured = self._prompt_for(_PNG_B64)
        self.assertIn("does not show", captured["user_prompt"].lower())

    def test_the_text_only_prompt_gains_nothing(self):
        captured = self._prompt_for(None)
        self.assertNotIn("image is attached", captured["user_prompt"].lower())
        self.assertIsNone(captured["image_base64"])


class TheExternalAiGateActuallyBlocks(_DeveloperModeCase):
    """Asserting the gate exists is not the same as asserting it works."""

    def test_a_denied_policy_stops_the_image_reaching_the_model(self):
        calls = []

        def spy(**kwargs):
            calls.append(kwargs)
            return _Result()

        with patch("routes.portal._project_less_external_ai_allowed", lambda: False), \
             patch("routes.portal.answer_application_question", side_effect=spy):
            self._post(message="what is on this screen?", image_data_url=_PNG_DATA_URL)
        self.assertEqual(len(calls), 1, "the turn should still happen")
        self.assertIsNone(calls[0]["image_base64"],
                          "the image was transmitted despite a denied policy")

    def test_the_question_is_still_answered_when_the_image_is_denied(self):
        # Honest degradation: dropping the picture is right, punishing the user
        # for a policy they cannot see is not.
        calls = []
        with patch("routes.portal._project_less_external_ai_allowed", lambda: False), \
             patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: calls.append(k) or _Result()):
            resp = self._post(message="how does ingestion work?", image_data_url=_PNG_DATA_URL)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(calls[0]["question"], "how does ingestion work?")

    def test_an_allowed_policy_lets_it_through(self):
        calls = []
        with patch("routes.portal._project_less_external_ai_allowed", lambda: True), \
             patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: calls.append(k) or _Result()):
            self._post(message="look", image_data_url=_PNG_DATA_URL)
        self.assertEqual(calls[0]["image_base64"], _PNG_B64)


class NothingIsPersisted(_DeveloperModeCase):
    """Developer Mode is orientation-only and files nothing. That must hold."""

    def test_the_screenshot_is_not_written_to_disk(self):
        store = Path(self.flask_app.config["REGISTRY_STORE_PATH"])
        raw = base64.b64decode(_PNG_B64)
        with patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: _Result()):
            self._post(message="see this", image_data_url=_PNG_DATA_URL)
        for path in store.rglob("*"):
            if path.is_file():
                self.assertNotIn(raw, path.read_bytes(),
                                 "the screenshot bytes were persisted at %s" % path)

    def test_the_data_url_is_not_stored_in_the_conversation_record(self):
        with patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: _Result()):
            self._post(message="see this", image_data_url=_PNG_DATA_URL)
        with self.client.session_transaction() as sess:
            recorded = str(sess.get("developer_home_messages", ""))
        self.assertNotIn(_PNG_B64, recorded)
        self.assertNotIn("data:image", recorded)

    def test_no_source_is_registered_by_a_developer_turn(self):
        with patch("routes.portal.answer_application_question",
                   side_effect=lambda **k: _Result()), \
             patch("services.case_workspace.CaseWorkspaceStore.add_source") as add_source:
            self._post(message="see this", image_data_url=_PNG_DATA_URL)
        add_source.assert_not_called()


class TheClientSharesTheNormalizationBoundary(unittest.TestCase):
    """Both doors into the same vision capability must prepare images the same
    way, or a photo succeeds or fails purely by which surface received it."""

    def setUp(self):
        self.source = _JS.read_text(encoding="utf-8")

    def test_it_reuses_the_shared_prepare_primitive(self):
        self.assertIn("window.ArchioskPrepareImage", self.source)

    def test_it_does_not_reimplement_resizing(self):
        # If this file ever grows its own canvas/quality loop, the two surfaces
        # have started disagreeing about what is too big.
        code = _strip_js_comments(self.source)
        for reimplementation in ["createElement('canvas')", "toDataURL", "MAX_EDGE"]:
            self.assertNotIn(reimplementation, code)

    def test_it_binds_paste_to_the_composer_not_the_document(self):
        # A paste meant for another field on Home must not be swallowed.
        self.assertIn("messageBox.addEventListener('paste'", self.source)
        self.assertNotIn("document.addEventListener('paste'", self.source)

    def test_it_clears_the_attachment_after_submit(self):
        self.assertIn("form.addEventListener('submit'", self.source)

    def test_the_markup_offers_both_a_picker_and_a_hidden_transport_field(self):
        # 3ab9477 moved the Developer Composer off authenticated `/` and onto
        # the protected /admin/developer-tools surface. The control itself is
        # unchanged - same ids, same hidden transport field - so this is a
        # path correction, not a narrowed assertion.
        markup = (_REPO_ROOT / "templates" / "developer_tools.html").read_text(encoding="utf-8")
        self.assertIn('id="developer-home-composer-image"', markup)
        self.assertIn('name="image_data_url"', markup)
        self.assertIn('accept="image/*"', markup)

    def test_it_does_not_import_project_evidence_flows(self):
        # Make-Q / Add-to-Q / capture review are project-evidence concerns and
        # have no meaning on a surface that files nothing.
        code = _strip_js_comments(self.source).lower()
        for project_only in ["make-q", "add-to-q", "capture-review", "register_eye_capture"]:
            self.assertNotIn(project_only, code)


if __name__ == "__main__":
    unittest.main()
