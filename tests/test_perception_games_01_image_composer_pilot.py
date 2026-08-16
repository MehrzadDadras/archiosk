"""
CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01 - bounded vision pilot.

Document-set Image Search's own known no-match state -> "Not found" ->
"Open in Composer" -> ONE real vision-capable Composer turn -> zero
automatic persistence. See routes/workspace.py's open_image_in_composer
and governance/specified-unbuilt/navigation-context-operational-map.md's
Perception Games round for the full architectural record this pilot is
grounded in.

Hermetic throughout (CLAUDE.md's own testing discipline): the real
Anthropic client is never constructed - anthropic.Anthropic is patched at
the same boundary tests/test_ca1a_context_completion.py's own precedent
already established for services.llm_gateway.call_llm_json.

Run via:

    python -m unittest tests.test_perception_games_01_image_composer_pilot -v
"""
from __future__ import annotations

import base64
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry

# A minimal, real 1x1 PNG - small enough to stay well under the route's
# own 5MB ceiling, real enough to round-trip through base64 encode/decode
# exactly like a genuine pasted screenshot would.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42Y"
    "AAAAASUVORK5CYII="
)
_TINY_PNG_DATA_URL = "data:image/png;base64," + base64.b64encode(_TINY_PNG).decode()


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_perception_games_01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-perception-01"

        with self.flask_app.app_context():
            db.session.add(User(username="mehrzad", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="The system shall do a thing.", category="other", confidence=0.6, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "mehrzad"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.set_project_owner(self.store.get(self.project_id), owner="mehrzad", actor="mehrzad")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _post(self, **form):
        return self.client.post(
            f"/projects/{self.project_id}/workspace/image-search/open-in-composer",
            data=form,
        )


class GameAEndToEndTests(_BaseTestCase):
    """Game A - a known-unrelated image, end to end."""

    def test_known_unrelated_image_gets_a_real_interpretation_with_zero_persistence(self):
        sources_before = len(self.store.get(self.project_id).sources)
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"reply": "This looks like a small test PNG, not project-related content."}'
            )
            resp = self._post(image_data_url=_TINY_PNG_DATA_URL)

        self.assertEqual(resp.status_code, 302)
        self.assertIn(f"/projects/{self.project_id}/workspace", resp.headers["Location"])

        workspace = self.store.get(self.project_id)
        convo = workspace.project_conversation
        self.assertEqual(len(convo), 2, "expected exactly one human + one system message")
        self.assertEqual(convo[0]["role"], "human")
        self.assertEqual(convo[1]["role"], "system")
        self.assertEqual(convo[1]["text"], "This looks like a small test PNG, not project-related content.")
        self.assertEqual(convo[1]["action_taken"], "image_search_composer_interpretation")

        # Zero automatic persistence: the human placeholder never contains
        # the actual image bytes/base64, and no Source was registered.
        self.assertNotIn("base64", convo[0]["text"])
        self.assertNotIn(base64.b64encode(_TINY_PNG).decode()[:20], convo[0]["text"])
        self.assertEqual(len(workspace.sources), sources_before, "no new Source was registered")

        # The real vision content block actually reached the model call.
        sent_content = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIsInstance(sent_content, list)
        self.assertEqual(sent_content[0]["type"], "image")
        self.assertEqual(sent_content[0]["source"]["media_type"], "image/png")


class GracefulDegradationTests(_BaseTestCase):
    def test_missing_image_data_url_flashes_and_redirects_without_creating_messages(self):
        resp = self._post()
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.project_conversation), 0)

    def test_malformed_data_url_is_rejected(self):
        resp = self._post(image_data_url="not-a-real-data-url")
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.project_conversation), 0)

    def test_oversized_image_is_rejected_before_any_model_call(self):
        oversized = "data:image/png;base64," + ("A" * 8_000_000)
        with patch("anthropic.Anthropic") as MockClient:
            resp = self._post(image_data_url=oversized)
            MockClient.return_value.messages.create.assert_not_called()
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.project_conversation), 0)

    def test_model_call_failure_still_gets_an_honest_reply_and_redirect(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            import anthropic
            MockClient.return_value.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
            resp = self._post(image_data_url=_TINY_PNG_DATA_URL)

        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        convo = workspace.project_conversation
        self.assertEqual(len(convo), 2)
        self.assertIn("couldn't look at the image", convo[1]["text"])


class SecurityPolicyGateTests(_BaseTestCase):
    def test_denied_policy_blocks_the_model_call_and_gives_an_honest_denial_reply(self):
        fake_decision = MagicMock(decision="deny", controlling_layer="organization_baseline", reason="Test denial.")
        with patch("routes.workspace._evaluate_security_action", return_value=fake_decision), \
             patch("anthropic.Anthropic") as MockClient:
            resp = self._post(image_data_url=_TINY_PNG_DATA_URL)
            MockClient.return_value.messages.create.assert_not_called()

        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        convo = workspace.project_conversation
        self.assertEqual(len(convo), 2)
        self.assertIn("not permitted", convo[1]["text"])
        self.assertIn("Nothing was transmitted", convo[1]["text"])


class CaseScopedRoutingTests(_BaseTestCase):
    def test_valid_case_id_lands_the_exchange_in_that_cases_conversation(self):
        workspace = self.store.get(self.project_id)
        case = self.store.create_case(workspace, title="A Real Investigation", objective="", created_by="mehrzad")

        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response('{"reply": "Noted."}')
            resp = self._post(image_data_url=_TINY_PNG_DATA_URL, case=case["id"])

        self.assertIn(f"case={case['id']}", resp.headers["Location"])
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.project_conversation), 0)
        reloaded_case = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertEqual(len(reloaded_case["conversation"]), 2)

    def test_a_case_id_belonging_to_no_visible_case_is_rejected(self):
        resp = self._post(image_data_url=_TINY_PNG_DATA_URL, case="does-not-exist")
        self.assertEqual(resp.status_code, 404)


if __name__ == "__main__":
    unittest.main()
