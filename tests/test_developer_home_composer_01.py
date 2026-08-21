"""Focused proof for the application-level Developer Composer on Home."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from services.llm_gateway import LLMCallOutcome
from services.project_qa import ProjectQAResult
from services.project_qa import answer_application_question


class DeveloperHomeComposerTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_home_ccn_"))
        self.app = app_module.create_app("testing")
        self.app.config.update(REGISTRY_STORE_PATH=str(self.tmp), TESTING=True)
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess.update({"user_id": 1, "username": "admin", "role": "admin"})

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _developer(self, enabled=True):
        with self.client.session_transaction() as sess:
            sess["developer_mode"] = enabled

    def test_normal_home_keeps_orientation_without_developer_composer(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'data-ui-ref="developer.home.composer"', response.data)
        self.assertIn(b'data-ui-ref="index.orientation.form"', response.data)

    def test_developer_home_has_one_composer_and_no_gateway_ask_form(self):
        self._developer()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.count(b'data-ui-ref="developer.home.composer.form"'), 1)
        self.assertNotIn(b'data-ui-ref="index.orientation.form"', response.data)
        self.assertNotIn(b'Open a project, or ask what you can do here', response.data)
        self.assertIn(b'data-ui-ref="developer.home.composer"', response.data)

    def test_developer_home_composer_has_canonical_microphone_and_voice_status(self):
        self._developer()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="developer-home-composer-voice"', response.data)
        self.assertIn(b'data-ui-ref="developer.home.composer.voice"', response.data)
        self.assertIn(b'id="developer-home-composer-voice-status"', response.data)
        self.assertIn(b"window.ArchioskVoiceInput", response.data)
        self.assertIn(b"developer-home-composer-voice", response.data)
        self.assertIn(b"developer-home-composer-voice-status", response.data)

    def test_developer_home_project_navigation_remains_available_as_links(self):
        self._developer()
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'data-ui-ref="index.orientation.form"', response.data)
        self.assertIn(b'data-ui-ref="developer.home.composer.form"', response.data)

    def test_home_ccn_is_application_scoped_and_lifecycle_works(self):
        self._developer()
        response = self.client.get("/")
        self.assertIn(b'data-ui-ref="developer.home.composer"', response.data)

        response = self.client.post("/developer-composer", data={"message": "/CCN inspect the project list"})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess["developer_ccn"]["id"])
            self.assertEqual(sess["developer_ccn"].get("project_id"), None)

        for command in ("/CCN status", "/CCN show"):
            self.client.post("/developer-composer", data={"message": command})
        response = self.client.get("/")
        self.assertIn(b"CCN:", response.data)
        self.assertIn(b"CCN status", response.data)

        self.client.post("/developer-composer", data={"message": "/CCN cancel"})
        response = self.client.get("/")
        self.assertNotIn(b'data-ui-ref="developer.ccn.active"', response.data)

    def test_inline_ccn_intent_accepts_space_and_colon_forms(self):
        self._developer()
        for command, expected in (
            ("/CCN Make the Developer Mode badge bold", "Make the Developer Mode badge bold"),
            ("/CCN: Move project selection into one interface", "Move project selection into one interface"),
        ):
            self.client.post("/developer-composer", data={"message": "/CCN cancel"})
            self.client.post("/developer-composer", data={"message": command})
            with self.client.session_transaction() as sess:
                self.assertEqual(sess["developer_ccn"]["intent"], expected)

    def test_ordinary_developer_question_is_answered_without_ccn(self):
        self._developer()
        unavailable = ProjectQAResult(ran=False, skipped_reason="test")
        with patch("routes.portal.answer_application_question", return_value=unavailable):
            response = self.client.post(
                "/developer-composer", data={"message": "How can we change the font for this icon: DEVELOPER MODE to make it bold?"}
            )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            reply = sess["developer_home_messages"][-1]["text"]
        self.assertIn("templates/_app_menu.html", reply)
        self.assertIn("font-weight: 700", reply)
        self.assertNotIn("Select an ARCHIOSK surface or use /CCN", reply)

    def test_ordinary_question_keeps_active_ccn_as_a_lens(self):
        self._developer()
        unavailable = ProjectQAResult(ran=False, skipped_reason="test")
        with patch("routes.portal.answer_application_question", return_value=unavailable):
            self.client.post("/developer-composer", data={"message": "/CCN: Make the badge bold"})
            self.client.post("/developer-composer", data={"message": "How is the Developer Mode badge implemented?"})
        with self.client.session_transaction() as sess:
            reply = sess["developer_home_messages"][-1]["text"]
        self.assertIn("templates/_app_menu.html", reply)
        self.assertIn("active CCN", reply)

    def test_ambiguous_application_objects_get_natural_context_options(self):
        self._developer()
        examples = {
            "How can I change this text?": ("Which text do you mean?", "type or paste the text"),
            "Can I move this button?": ("Which button do you mean?", "name the button"),
            "Why is this panel so large?": ("Which panel do you mean?", "tell me which panel"),
            "How do I recolor this icon?": ("Which icon do you mean?", "describe it"),
        }
        unavailable = ProjectQAResult(ran=False, skipped_reason="test")
        with patch("routes.portal.answer_application_question", return_value=unavailable):
            for question, expected in examples.items():
                self.client.post("/developer-composer", data={"message": question})
                with self.client.session_transaction() as sess:
                    reply = sess["developer_home_messages"][-1]["text"]
                self.assertIn(expected[0], reply)
                self.assertIn(expected[1], reply)
                self.assertNotIn("Selection required", reply)

    def test_normal_developer_question_has_substantive_chat_history_answer(self):
        self._developer()
        unavailable = ProjectQAResult(ran=False, skipped_reason="test")
        with patch("routes.portal.answer_application_question", return_value=unavailable):
            self.client.post("/developer-composer", data={"message": "How can we delete the chat history?"})
        with self.client.session_transaction() as sess:
            reply = sess["developer_home_messages"][-1]["text"]
        self.assertIn("no ordinary Developer Composer action", reply)
        self.assertIn("no mutation is authorized", reply)

    def test_shared_composer_keyboard_contract_covers_home_and_workspace(self):
        from pathlib import Path

        root = Path(__file__).parents[1]
        script = (root / "static/js/developer_composer_input.js").read_text(encoding="utf-8")
        macro = (root / "templates/_macros.html").read_text(encoding="utf-8")
        home = (root / "templates/index.html").read_text(encoding="utf-8")
        self.assertIn("event.shiftKey", script)
        self.assertIn("event.isComposing", script)
        self.assertIn("requestSubmit", script)
        self.assertIn("data-developer-composer-form", macro)
        self.assertIn("data-developer-composer-form", home)
        self.assertIn("<textarea", macro)
        self.assertIn("<textarea", home)

    def test_ordinary_home_message_reaches_canonical_model_adapter_with_history_and_context(self):
        self._developer()
        self.client.post(
            "/developer-composer/context",
            data={"object_type": "application_surface", "object_id": "project-list", "label": "Project list"},
        )
        fake = ProjectQAResult(ran=True, answer="Model-backed application answer.", provider="fake", model="test")
        with patch("routes.portal.answer_application_question", return_value=fake) as call:
            self.client.post("/developer-composer", data={"message": "What does this do?"})
        self.assertEqual(call.call_count, 1)
        kwargs = call.call_args.kwargs
        self.assertEqual(kwargs["question"], "What does this do?")
        self.assertIsNone(kwargs.get("project_id"))
        self.assertEqual(kwargs["developer_context"]["selected_elements"][0]["object_id"], "project-list")
        self.assertEqual(kwargs["recent_history"], [])

    def test_inline_ccn_intent_also_reaches_model_adapter(self):
        self._developer()
        fake = ProjectQAResult(ran=True, answer="Substantive CCN analysis.", provider="fake", model="test")
        with patch("routes.portal.answer_application_question", return_value=fake) as call:
            self.client.post("/developer-composer", data={"message": "/CCN: change this application surface"})
        self.assertEqual(call.call_count, 1)
        self.assertEqual(call.call_args.kwargs["question"], "change this application surface")
        with self.client.session_transaction() as sess:
            self.assertIn("Substantive CCN analysis.", sess["developer_home_messages"][-1]["text"])

    def test_application_adapter_supplies_context_and_history_to_shared_model_gateway(self):
        outcome = LLMCallOutcome(
            ran=True,
            parsed={"answer": "Model answer", "grounded_in": ["selected surface"], "needs_clarification": False},
            provider="fake",
            model="test",
        )
        context = {
            "status": "active",
            "intent": "Inspect the badge",
            "selected_elements": [{"object_type": "application_surface", "object_id": "badge", "label": "Developer Mode badge"}],
        }
        history = [{"role": "human", "text": "How is this implemented?"}, {"role": "system", "text": "It is a session badge."}]
        with patch("services.project_qa.call_llm_json", return_value=outcome) as call:
            result = answer_application_question("Can it be bold?", context, history, api_key="test-key")
        self.assertTrue(result.ran)
        self.assertEqual(result.answer, "Model answer")
        prompt = call.call_args.kwargs["user_prompt"]
        self.assertIn("Developer Mode badge", prompt)
        self.assertIn("Inspect the badge", prompt)
        self.assertIn("How is this implemented?", prompt)
        self.assertIn("Can it be bold?", prompt)
        self.assertNotIn("project_id", prompt)

    def test_home_selection_attaches_application_object_without_authorizing_mutation(self):
        self._developer()
        response = self.client.post(
            "/developer-composer/context",
            data={"object_type": "application_surface", "object_id": "project-list", "label": "Project list"},
        )
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertIsNone(sess["developer_application_selection"]["project_id"])
        self.client.post("/developer-composer", data={"message": "/CCN inspect this"})
        with self.client.session_transaction() as sess:
            elements = sess["developer_ccn"]["selected_elements"]
            self.assertEqual(elements[0]["object_id"], "project-list")
            self.assertIsNone(elements[0]["project_id"])
            self.assertEqual(elements[0]["classification"], "INVESTIGATE")

    def test_project_binding_is_rejected_and_non_admin_cannot_use_client_state(self):
        self._developer()
        self.assertEqual(
            self.client.post("/developer-composer", data={"message": "/CCN", "project_id": "project-a"}).status_code,
            400,
        )
        with self.client.session_transaction() as sess:
            sess.update({"role": "member", "developer_mode": True})
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertNotIn(b'data-ui-ref="developer.home.composer"', self.client.get("/").data)
        self.assertEqual(self.client.post("/developer-composer", data={"message": "/CCN"}).status_code, 403)


if __name__ == "__main__":
    unittest.main()
