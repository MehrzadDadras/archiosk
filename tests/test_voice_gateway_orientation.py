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

from routes.portal import _classify_gateway_orientation
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

    def test_gateway_page_has_orientation_composer_and_voice_button(self):
        body = self.client.get("/gateway").get_data(as_text=True)
        self.assertIn('data-ui-ref="gateway.orientation.form"', body)
        self.assertIn('data-ui-ref="gateway.orientation.voice"', body)
        self.assertIn('data-ui-ref="gateway.orientation.submit"', body)
        self.assertIn('id="gateway-orientation-reply"', body)

    def test_voice_button_hidden_by_default_server_side(self):
        body = self.client.get("/gateway").get_data(as_text=True)
        voice_button_start = body.index('id="gateway-orientation-voice"')
        button_open_tag = body.rindex("<button", 0, voice_button_start)
        button_close_tag = body.index(">", voice_button_start)
        self.assertIn("hidden", body[button_open_tag:button_close_tag])

    def test_shared_voice_engine_script_loads_before_the_page_wires_it_up(self):
        # Regression guard: voice_input.js defines window.ArchioskVoiceInput
        # synchronously at parse time - if its <script> tag rendered AFTER
        # gateway.html's own inline script that calls it, the call would
        # silently no-op on every browser (not just unsupported ones),
        # since window.ArchioskVoiceInput wouldn't exist yet.
        body = self.client.get("/gateway").get_data(as_text=True)
        self.assertIn("voice_input.js", body)
        voice_engine_idx = body.index("voice_input.js")
        wiring_call_idx = body.index("window.ArchioskVoiceInput({")
        self.assertLess(voice_engine_idx, wiring_call_idx)

    def test_project_chooser_does_not_get_the_orientation_composer(self):
        # Scoped to gateway.html only (the "Begin a session" screen the
        # Product Owner actually named) - project_chooser.html overrides
        # the same gateway_section_heading block with its own heading.
        body = self.client.get("/projects/choose").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="gateway.orientation.form"', body)


if __name__ == "__main__":
    unittest.main()
