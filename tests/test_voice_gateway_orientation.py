"""
CLAUDE-VOICE-CONSISTENCY-01 - Project Gateway orientation composer/voice.

Covers routes/portal.py's _classify_gateway_orientation/gateway_orientation
(the new, small, rule-based responder backing the Gateway's mic/text
composer) and the markup/JS wiring on templates/gateway.html. Deliberately
proves this endpoint never reaches services/conversation_interpreter.py's
interpret_message or opens a CaseWorkspaceStore for conversational
reasoning - the whole point of keeping this at Level 2/3 of the future
Voice authority ladder (governance/specified-unbuilt/
voice-conversational-presence.md) rather than the real GO interpreter.

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from routes.portal import _classify_establish_project_help, _classify_gateway_orientation
from services.bhive_parser import BHiveParser, ParsedDocument
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class ClassifyGatewayOrientationTests(unittest.TestCase):
    """_classify_gateway_orientation calls url_for for a "navigate" reply,
    which needs a request context even outside a real request."""

    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.ctx = self.flask_app.test_request_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

        self.projects = [
            {"project_id": "proj-1", "display_name": "Riverside Water Treatment RFP", "last_activity": "x"},
            {"project_id": "proj-2", "display_name": "North Bayview Courthouse", "last_activity": "x"},
        ]

    def test_empty_message_is_info_not_navigate(self):
        reply = _classify_gateway_orientation("", self.projects, can_create_project=True)
        self.assertEqual(reply["kind"], "info")

    def test_matching_project_name_navigates_to_it(self):
        reply = _classify_gateway_orientation("open riverside water treatment rfp", self.projects, can_create_project=True)
        self.assertEqual(reply["kind"], "navigate")
        self.assertIn("proj-1", reply["url"])

    def test_partial_project_name_still_matches(self):
        reply = _classify_gateway_orientation("north bayview", self.projects, can_create_project=True)
        self.assertEqual(reply["kind"], "navigate")
        self.assertIn("proj-2", reply["url"])

    def test_new_project_intent_navigates_when_admin(self):
        reply = _classify_gateway_orientation("start a new project", self.projects, can_create_project=True)
        self.assertEqual(reply["kind"], "navigate")
        self.assertIn("upload", reply["url"])

    def test_new_project_intent_is_info_only_when_not_admin(self):
        # Matches routes/portal.py's own admin-gating of "New Project" on
        # the rendered Gateway cards - the voice/text path must not offer
        # a capability the visible UI already hides from this user.
        reply = _classify_gateway_orientation("start a new project", self.projects, can_create_project=False)
        self.assertEqual(reply["kind"], "info")

    def test_unrecognized_message_is_info_with_no_url(self):
        reply = _classify_gateway_orientation("what is the weather", self.projects, can_create_project=True)
        self.assertEqual(reply["kind"], "info")
        self.assertNotIn("url", reply)

    def test_no_project_ever_matches_by_accident_on_empty_list(self):
        reply = _classify_gateway_orientation("anything at all", [], can_create_project=True)
        self.assertEqual(reply["kind"], "info")


class ClassifyEstablishProjectHelpTests(unittest.TestCase):
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum H: the
    New Project / Establish a Project form's own project-less help
    classifier - a genuinely different domain from
    _classify_gateway_orientation (explains this form's own fields,
    never navigates to a project), so it never opens a
    CaseWorkspaceStore or reaches interpret_message either - it doesn't
    even take a `projects` argument."""

    def test_empty_message_is_info_with_a_prompt(self):
        reply = _classify_establish_project_help("")
        self.assertEqual(reply["kind"], "info")
        self.assertTrue(reply["text"])

    def test_environment_question_explains_both_sides_without_choosing(self):
        reply = _classify_establish_project_help("which operating environment should I choose?")
        self.assertEqual(reply["kind"], "info")
        self.assertIn("Owner", reply["text"])
        self.assertIn("Proponent", reply["text"])

    def test_change_later_question_is_answered_truthfully(self):
        reply = _classify_establish_project_help("can I change this later?")
        self.assertIn("locked permanently", reply["text"])

    def test_connect_documents_question_explains_link_vs_upload(self):
        reply = _classify_establish_project_help("should I connect documents now or later?")
        self.assertIn("Link to Storage", reply["text"])

    def test_naming_question_is_answered(self):
        reply = _classify_establish_project_help("what should I name this project?")
        self.assertIn("optional", reply["text"])

    def test_unrecognized_message_falls_back_to_a_menu_of_topics(self):
        reply = _classify_establish_project_help("what is the weather")
        self.assertEqual(reply["kind"], "info")
        self.assertNotIn("url", reply)

    def test_never_returns_a_navigate_reply(self):
        # This widget must never submit the real form or redirect the
        # user on its own - it only ever explains.
        for message in ("environment", "change later", "connect documents", "name", "", "anything"):
            reply = _classify_establish_project_help(message)
            self.assertEqual(reply["kind"], "info", message)


class GatewayOrientationRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_voice_gateway_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False

        with self.flask_app.app_context():
            db.session.add(User(username="voice_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="voice_reader", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt", environment: str = "client_owner"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=environment, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def test_route_requires_authentication(self):
        client = self.flask_app.test_client()
        resp = client.post("/gateway/orientation", data={"message": "hello"})
        self.assertIn(resp.status_code, (302, 401, 403))

    def test_route_returns_json_reply(self):
        client = self._client_as("voice_owner", 1)
        resp = client.post("/gateway/orientation", data={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn(data["kind"], ("info", "navigate"))

    def test_route_never_calls_the_real_go_interpreter(self):
        # The whole point of this endpoint: it must stay at Level 2/3 of
        # the voice authority ladder, never the real GO interpreter,
        # which requires an already-open project's own CaseWorkspaceStore
        # and speaks with real project evidence/authority.
        client = self._client_as("voice_owner", 1)
        with patch("services.conversation_interpreter.interpret_message") as mock_interpret:
            resp = client.post("/gateway/orientation", data={"message": "what does this project say about drainage"})
            self.assertEqual(resp.status_code, 200)
            mock_interpret.assert_not_called()

    def test_route_matches_a_real_accessible_project_and_navigates(self):
        doc = self._ingest(owner="voice_owner", project_name="Riverside Project")
        client = self._client_as("voice_owner", 1)
        resp = client.post("/gateway/orientation", data={"message": "open riverside project"})
        data = resp.get_json()
        self.assertEqual(data["kind"], "navigate")
        self.assertIn(doc.project_id, data["url"])

    def test_route_never_leaks_a_project_the_user_cannot_access(self):
        self._ingest(owner="voice_owner", project_name="Private Owner Project")
        outsider = self._client_as("voice_reader", 2, role="read_only")
        resp = outsider.post("/gateway/orientation", data={"message": "open private owner project"})
        data = resp.get_json()
        self.assertEqual(data["kind"], "info")

    def test_establish_project_context_routes_to_the_help_classifier_not_navigation(self):
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum H: a
        # project genuinely named "environment" would otherwise match
        # _classify_gateway_orientation's own substring project-name
        # matcher and navigate - context=establish-project must route
        # to the field-explanation classifier instead, never navigation.
        self._ingest(owner="voice_owner", project_name="Environment Test Project")
        client = self._client_as("voice_owner", 1)
        resp = client.post("/gateway/orientation", data={"message": "which environment should I choose", "context": "establish-project"})
        data = resp.get_json()
        self.assertEqual(data["kind"], "info")
        self.assertIn("Owner", data["text"])

    def test_omitted_context_keeps_the_original_navigation_behavior(self):
        doc = self._ingest(owner="voice_owner", project_name="Riverside Project")
        client = self._client_as("voice_owner", 1)
        resp = client.post("/gateway/orientation", data={"message": "open riverside project"})
        data = resp.get_json()
        self.assertEqual(data["kind"], "navigate")
        self.assertIn(doc.project_id, data["url"])


class GatewayOrientationMarkupTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="voice_markup_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "voice_markup_owner"
            sess["role"] = "admin"

    def test_index_page_has_orientation_composer_and_voice_button(self):
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: ported
        # from the retired gateway.html to the consolidated / (index.html)
        # entry page - same backend route, same voice wiring, new element
        # ids/refs only (index.* rather than gateway.*).
        body = self.client.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn('data-ui-ref="index.orientation.form"', body)
        self.assertIn('data-ui-ref="index.orientation.voice"', body)
        self.assertIn('data-ui-ref="index.orientation.submit"', body)
        self.assertIn('id="index-orientation-reply"', body)

    def test_voice_button_hidden_by_default_server_side(self):
        body = self.client.get("/", follow_redirects=True).get_data(as_text=True)
        voice_button_start = body.index('id="index-orientation-voice"')
        button_open_tag = body.rindex("<button", 0, voice_button_start)
        button_close_tag = body.index(">", voice_button_start)
        self.assertIn("hidden", body[button_open_tag:button_close_tag])

    def test_shared_voice_engine_script_loads_before_the_page_wires_it_up(self):
        # Regression guard: voice_input.js defines window.ArchioskVoiceInput
        # synchronously at parse time - if its <script> tag rendered AFTER
        # index.html's own inline script that calls it, the call would
        # silently no-op on every browser (not just unsupported ones),
        # since window.ArchioskVoiceInput wouldn't exist yet.
        body = self.client.get("/", follow_redirects=True).get_data(as_text=True)
        self.assertIn("voice_input.js", body)
        voice_engine_idx = body.index("voice_input.js")
        wiring_call_idx = body.index("window.ArchioskVoiceInput({")
        self.assertLess(voice_engine_idx, wiring_call_idx)

    def test_project_chooser_does_not_get_the_orientation_composer(self):
        # project_chooser.html never had this composer and still doesn't -
        # it's specific to the consolidated / entry page now.
        body = self.client.get("/projects/choose").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="index.orientation.form"', body)

    def test_upload_page_has_a_collapsible_help_composer_with_establish_project_context(self):
        # CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum H.
        body = self.client.get("/upload").get_data(as_text=True)
        self.assertIn('data-ui-ref="upload.help"', body)
        self.assertIn('data-ui-ref="upload.help.form"', body)
        self.assertIn('data-ui-ref="upload.help.submit"', body)
        self.assertIn('name="context" value="establish-project"', body)
        # Collapsed by default - a real <details> with no `open` attribute
        # - so it never obscures the form fields beneath it.
        details_idx = body.rindex("<details", 0, body.index('data-ui-ref="upload.help"'))
        details_tag = body[details_idx:body.index(">", details_idx)]
        self.assertNotIn(" open", details_tag)

    def test_upload_help_composer_never_appears_elsewhere(self):
        # The real, canonical in-project Composer (case_workspace.html)
        # and the consolidated entry page must never gain this
        # establish-project-specific widget - it's genuinely scoped to
        # this one form, not a variant reused elsewhere.
        for path in ("/projects", "/"):
            body = self.client.get(path).get_data(as_text=True)
            self.assertNotIn('data-ui-ref="upload.help"', body, path)


if __name__ == "__main__":
    unittest.main()
