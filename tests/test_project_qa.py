"""
CLAUDE-P38 (OBS-01) -- real, grounded, read-only project-level Q&A.

Two layers, matching tests/test_requirement_investigation.py's own
split:
  - ProjectQAServiceTests: services/project_qa.py directly, network
    call mocked (standard practice for testing an external-API
    integration).
  - ProjectQAInterpreterTests: the real route stack (discuss_object),
    proving the "Talk to this Project..." composer's own promise --
    ordinary read-only project questions get answered, not rejected as
    an unrecognized action -- and that the same CLAUDE-P36 external-AI
    policy gate applies here too.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.project_qa import answer_project_question
from services.requirements_registry import RequirementsRegistry


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ProjectQAServiceTests(unittest.TestCase):
    def test_no_api_key_returns_an_honest_skip_not_a_fabricated_result(self):
        result = answer_project_question(
            question="What are the objectives of this RFP?",
            document_filename="rfp.txt", candidate_requirements=[], governed_requirements=[],
            milestones=[], api_key="",
        )
        self.assertFalse(result.ran)
        self.assertIsNone(result.answer)
        self.assertIn("ANTHROPIC_API_KEY", result.skipped_reason)

    def test_real_call_parses_the_model_json_output_correctly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "The scope covers structural upgrades per Section 1.", '
                '"grounded_in": ["Section 1 - Scope of Work"], "not_covered": "", '
                '"needs_clarification": false}'
            )
            result = answer_project_question(
                question="What is the scope?", document_filename="rfp.txt",
                candidate_requirements=[{"text": "The Design-Builder shall provide all labor...", "category": "scope_of_work"}],
                governed_requirements=[], milestones=[], api_key="fake-key-for-test",
            )
        self.assertTrue(result.ran)
        self.assertIn("structural upgrades", result.answer)
        self.assertEqual(result.grounded_in, ["Section 1 - Scope of Work"])
        self.assertFalse(result.needs_clarification)
        self.assertEqual(result.provider, "anthropic")
        self.assertTrue(result.model)

    def test_insufficient_evidence_is_reported_not_guessed(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "This project'"'"'s extracted evidence does not state a total contract value.", '
                '"grounded_in": [], "not_covered": "Total contract value is not present in the extracted evidence.", '
                '"needs_clarification": true}'
            )
            result = answer_project_question(
                question="What is the total contract value?", document_filename="rfp.txt",
                candidate_requirements=[], governed_requirements=[], milestones=[], api_key="fake-key-for-test",
            )
        self.assertTrue(result.ran)
        self.assertTrue(result.needs_clarification)
        self.assertIn("not present", result.not_covered)

    def test_api_exception_degrades_honestly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("network exploded")
            result = answer_project_question(
                question="Summarize this project", document_filename="rfp.txt",
                candidate_requirements=[], governed_requirements=[], milestones=[], api_key="fake-key-for-test",
            )
        self.assertFalse(result.ran)
        self.assertIn("error occurred", result.skipped_reason.lower())


class ProjectQAInterpreterTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_qa_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-qa"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="The Design-Builder shall provide all labor and materials.", category="scope_of_work", confidence=0.9, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.store.get(self.project_id), owner="owner1", actor="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_ordinary_project_question_is_answered_not_rejected_as_unrecognized(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "The scope covers labor and materials per the extracted item.", '
                '"grounded_in": ["scope_of_work item"], "not_covered": "", "needs_clarification": false}'
            )
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What are the objectives of this RFP?"},
                follow_redirects=True,
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("scope covers labor and materials", body)
        self.assertNotIn("I didn't recognize an action", body)

    def test_unrelated_stray_message_still_gets_the_honest_unrecognized_reply(self):
        # No API key configured (create_app("testing") clears it) and the
        # message doesn't look like a question at all -- must not trigger
        # a real model call or claim anything was answered.
        with patch("anthropic.Anthropic") as MockClient:
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "asdf"},
                follow_redirects=True,
            )
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)
        self.assertIn("I didn&#39;t recognize an action", resp.get_data(as_text=True))

    def test_missing_api_key_gives_an_honest_degrade_not_a_fabricated_answer(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "What are the key requirements?"},
            follow_redirects=True,
        )
        body = resp.get_data(as_text=True)
        self.assertIn("ANTHROPIC_API_KEY", body)
        self.assertIn("Nothing was fabricated", body)

    def test_drawing_specific_action_is_still_recognized_unchanged(self):
        # Existing governed action paths (needs_case escalation for a
        # Case-shaped command) must not be disturbed by the new fallback.
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "Analyze this drawing for clashes"},
            follow_redirects=True,
        )
        self.assertIn("Start an Investigation from this", resp.get_data(as_text=True))

    def test_project_question_denied_by_active_baseline_makes_zero_provider_calls(self):
        from services.security_governance import CONTROL_SOURCE_ARCHIOSK_DEFAULT, SecurityGovernanceStore
        from services.security_policy import ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY

        security_store = SecurityGovernanceStore(self.tmp_dir)
        record = security_store.get()
        baseline = security_store.create_baseline_draft(record, created_by="owner1")
        security_store.add_control_decision(
            record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_DENY,
            source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="owner1",
        )
        security_store.acknowledge_capability_impact(record, baseline["id"], actor="owner1")
        security_store.activate_baseline(record, baseline["id"], actor="owner1")

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What are the objectives of this RFP?"},
                follow_redirects=True,
            )
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)
        self.assertIn("not permitted by this", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
