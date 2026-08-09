"""
CLAUDE-POSTCAMEL-CA1 - Conversational Apprenticeship / Project-Aware
Operational Agent.

WB1-CLOSE established the real baseline this stage builds on: stateless
per-turn model calls, no system-role behavioral contract, no bounded
conversation continuity, and a hardcoded "I didn't recognize an action"
dead end with no concrete next step.

This tranche implements, as the smallest safe bounded slice:
  - a centralized system-role behavioral contract for the one real,
    grounded Project Q&A model call (services/project_qa.py);
  - a bounded (last 6 messages), project/case-isolated recent-history
    window fed into that same call for conversational continuity;
  - a fully deterministic (no model call) Project Orientation feature,
    sparse vs. established, with real next-step links only;
  - a small, deterministic, server-computed next-step-offer mechanism
    (ConversationMessage.next_steps) rendered as real navigation links,
    never model-generated prose interpreted as a command;
  - a real routing bug fix: quick_start previously had no way to route
    an orientation request ("orient me") anywhere but a brand-new,
    surprise Case, exactly the failure mode this same route's own
    docstring already named for plain questions before CLAUDE-P40-B.

Run via:

    python -m unittest tests.test_ca1_conversational_apprenticeship -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.conversation_interpreter import _looks_like_orientation_request
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


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
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="ca1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="ca1_owner", project_name="CA1 Conversational Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "ca1_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _quick_start(self, client, text: str):
        return client.post(
            f"/projects/{self.project_id}/workspace/quick-start", data={"text": text},
        )

    def _discuss(self, client, text: str):
        return client.post(
            f"/projects/{self.project_id}/workspace/discuss", data={"text": text},
        )


class OrientationPhraseDetectionTests(unittest.TestCase):
    def test_recognizes_expected_phrasings(self):
        for phrase in ("orient me", "What's here?", "what do I have", "give me an overview", "Where do I start?"):
            self.assertTrue(_looks_like_orientation_request(phrase.lower()), phrase)

    def test_does_not_recognize_an_ordinary_question(self):
        self.assertFalse(_looks_like_orientation_request("what are the objectives of this rfp?"))


class SparseProjectOrientationTests(_BaseTestCase):
    def test_sparse_orientation_names_the_real_source_count(self):
        client = self._client()
        self._quick_start(client, "orient me")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("one registered project source", body)

    def test_sparse_orientation_offers_a_real_open_files_link(self):
        client = self._client()
        self._quick_start(client, "orient me")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("Open Files", body)
        self.assertIn(f"/projects/{self.project_id}/workspace?view=files", body)

    def test_orientation_does_not_create_a_surprise_case(self):
        """Regression guard for the real routing bug this stage found and
        fixed: quick_start previously had no branch for an orientation
        request, so it silently created a brand-new Case titled "orient
        me" - exactly the failure mode CLAUDE-P40-B already fixed for
        plain questions."""
        client = self._client()
        self._quick_start(client, "orient me")
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.cases, [])

    def test_orientation_works_regardless_of_api_key_presence(self):
        """Fully deterministic - orientation never imports or calls
        `anthropic` at all, so it must succeed identically whether or
        not ANTHROPIC_API_KEY happens to be configured (unlike
        Project Q&A). Not asserting the key is absent here - CLAUDE.md's
        own documented gotcha: a real key in .env survives
        create_app("testing")'s env-clearing, since config.py's class
        attribute is fixed at first import."""
        client = self._client()
        resp = self._quick_start(client, "orient me")
        self.assertEqual(resp.status_code, 302)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("registered project source", body)


class EstablishedProjectOrientationTests(_BaseTestCase):
    def _register_requirement(self, client, identifier: str):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={
                "source_id": source_id, "original_requirement_identifier": identifier,
                "text_reference": f"The system shall {identifier}.",
            },
        )

    def test_established_orientation_differs_from_sparse(self):
        client = self._client()
        self._register_requirement(client, "REQ-1")
        self._quick_start(client, "what's here")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("governed Requirement(s) on record", body)
        self.assertIn("Open Requirements", body)
        self.assertIn("Open Overview", body)
        self.assertNotIn("one registered project source", body)


class BehavioralContractAndContinuityTests(_BaseTestCase):
    def test_system_role_behavioral_contract_is_sent(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "This is a test project.", "grounded_in": [], '
                '"not_covered": "", "needs_clarification": false}'
            )
            client = self._client()
            self.flask_app.config["ANTHROPIC_API_KEY"] = "fake-key-for-test"
            with patch("services.project_qa.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
                self._quick_start(client, "What is this project about?")

            call_kwargs = MockClient.return_value.messages.create.call_args.kwargs
            self.assertIn("system", call_kwargs)
            self.assertIn("ARCHIOSK Go", call_kwargs["system"])
            self.assertIn("never invent", call_kwargs["system"].lower().replace("never invent", "never invent"))

    def test_second_question_includes_bounded_recent_history(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.project_qa.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "First answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            client = self._client()
            self._quick_start(client, "What is the scope of this project?")

            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "Second answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            self._quick_start(client, "What about the schedule?")

            second_call_prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertIn("Recent conversation", second_call_prompt)
            self.assertIn("What is the scope of this project?", second_call_prompt)
            self.assertIn("First answer.", second_call_prompt)

    def test_recent_history_never_crosses_projects(self):
        other_doc = self._ingest(owner="ca1_owner", project_name="CA1 Other Project")
        other_project_id = other_doc.project_id

        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.project_qa.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "Answer about project A.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            client = self._client()
            self._quick_start(client, "What is unique to project A only?")

            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "Answer about project B.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            client.post(
                f"/projects/{other_project_id}/workspace/quick-start",
                data={"text": "What is happening in this other project?"},
            )

            second_call_prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertNotIn("What is unique to project A only?", second_call_prompt)
            self.assertNotIn("Answer about project A.", second_call_prompt)


class FailureFallbackNextStepTests(_BaseTestCase):
    def test_unrecognized_message_offers_a_real_next_step(self):
        client = self._client()
        self._discuss(client, "purple monkey dishwasher")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("recognize an action in that message", body)
        self.assertIn("Open Files", body)
        self.assertIn(f"/projects/{self.project_id}/workspace?view=files", body)

    def test_unrecognized_message_mentions_orientation_as_an_option(self):
        client = self._client()
        self._discuss(client, "purple monkey dishwasher")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("orient me", body)


if __name__ == "__main__":
    unittest.main()
