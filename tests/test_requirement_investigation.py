"""
CLAUDE-P04 - Real Requirement investigation: Requirements as the single
proving ground for genuine reasoning behind the Conversation aperture.

Two layers tested here:
  - RequirementInvestigationServiceTests: the real Anthropic-call service
    (services/requirement_investigation.py) directly, with the network
    call itself mocked (standard practice for testing an external-API
    integration) - proving the prompt/parsing/degradation code is
    correct, not claiming a live model was actually reached.
  - RequirementInvestigationInterpreterTests: the honest, CURRENT,
    un-mocked behavior of this deployment (no ANTHROPIC_API_KEY
    configured - see .env) through the full route stack, plus one
    mocked-key test proving the real Finding-creation path is wired
    correctly end to end.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.bhive_parser import ParsedDocument
from services.case_workspace import REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, CaseWorkspaceStore
from services.requirement_investigation import investigate_requirement
from services.requirements_registry import RequirementsRegistry

_BASE_REQUIREMENT = {
    "id": "r1",
    "text_reference": "Contractor shall provide as-built drawings.",
    "original_requirement_identifier": "Section 3.1",
    "source_id": "s1",
}
_EMPTY_EVIDENCE = {"findings": [], "relationships": [], "accepted_knowledge": []}


class RequirementInvestigationServiceTests(unittest.TestCase):
    def test_no_api_key_returns_an_honest_skip_not_a_fabricated_result(self):
        result = investigate_requirement(
            question="Why is this like this?",
            requirement=_BASE_REQUIREMENT,
            adjudication_history=[],
            evidence=_EMPTY_EVIDENCE,
            api_key="",
        )
        self.assertFalse(result.ran)
        self.assertIsNone(result.assessment)
        self.assertIn("ANTHROPIC_API_KEY", result.skipped_reason)

    def _mock_response(self, text_out: str):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = text_out
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_real_call_parses_the_model_json_output_correctly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(
                '{"assessment": "The requirement is satisfied per CR-17.", '
                '"confidence": 0.82, "supporting_points": ["CR-17 clarification"], '
                '"open_questions": [], "needs_human_judgment": false}'
            )
            result = investigate_requirement(
                question="Why is this like this?",
                requirement=_BASE_REQUIREMENT,
                adjudication_history=[],
                evidence=_EMPTY_EVIDENCE,
                api_key="fake-key-for-test",
            )

        self.assertTrue(result.ran)
        self.assertEqual(result.assessment, "The requirement is satisfied per CR-17.")
        self.assertAlmostEqual(result.confidence, 0.82)
        self.assertFalse(result.needs_human_judgment)
        self.assertEqual(result.supporting_points, ["CR-17 clarification"])

    def test_markdown_fenced_json_is_still_parsed(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(
                '```json\n{"assessment": "Unclear from the evidence given.", '
                '"confidence": 0.3, "supporting_points": [], '
                '"open_questions": ["No adjudication on record"], '
                '"needs_human_judgment": true}\n```'
            )
            result = investigate_requirement(
                question="Check this",
                requirement=_BASE_REQUIREMENT,
                adjudication_history=[],
                evidence=_EMPTY_EVIDENCE,
                api_key="fake-key-for-test",
            )

        self.assertTrue(result.ran)
        self.assertTrue(result.needs_human_judgment)
        self.assertEqual(result.open_questions, ["No adjudication on record"])

    def test_malformed_model_output_degrades_honestly_not_silently(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response("not json at all")
            result = investigate_requirement(
                question="Check this",
                requirement=_BASE_REQUIREMENT,
                adjudication_history=[],
                evidence=_EMPTY_EVIDENCE,
                api_key="fake-key-for-test",
            )

        self.assertFalse(result.ran)
        self.assertIn("malformed", result.skipped_reason.lower())

    def test_api_exception_degrades_honestly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("network exploded")
            result = investigate_requirement(
                question="Check this",
                requirement=_BASE_REQUIREMENT,
                adjudication_history=[],
                evidence=_EMPTY_EVIDENCE,
                api_key="fake-key-for-test",
            )

        self.assertFalse(result.ran)
        self.assertIn("error occurred", result.skipped_reason.lower())


class RequirementInvestigationInterpreterTests(unittest.TestCase):
    """
    Exercises the full route stack. Deliberately does NOT set
    ANTHROPIC_API_KEY for most of these - this deployment genuinely has
    none configured (see .env), so the honest-decline path exercised
    here IS this feature's real, current, live behavior, not a
    simulation of it.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_requirement_investigation_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-requirement-investigation"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self):
        self.client.get(f"/projects/{self.project_id}/workspace")
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def _create_case(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Investigate Section 3.1", "objective": "x"},
        )
        self.assertEqual(resp.status_code, 302)
        return self.store.get(self.project_id).cases[0]

    def test_investigation_question_without_a_case_offers_escalation_not_a_fabricated_answer(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Why is this like this?",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        self.assertIn("Start an Investigation from this", resp.get_data(as_text=True))

    def test_investigation_question_inside_a_case_declines_honestly_with_no_api_key(self):
        requirement = self._register_requirement()
        case = self._create_case()
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/messages",
            data={"text": "Check this"},
        )
        self.assertEqual(resp.status_code, 302)

        # post_message doesn't currently pass an anchor from the Case
        # composer - post directly through the store to attach one, the
        # same shape discuss_object builds, to isolate the interpreter's
        # own behavior from that separate, unfinished wiring gap.
        workspace = self.store.get(self.project_id)
        from services.conversation_interpreter import interpret_message
        from services.case_workspace import CaseWorkspaceStore as _Store

        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        result = interpret_message(
            text="Check this",
            workspace=workspace,
            case=case,
            store=self.store,
            artifacts_dir=artifacts_dir,
            reviewer="owner1",
            focused_finding_id=None,
            anchor={"anchor_type": "requirement", "anchor_id": requirement["id"], "description": "Section 3.1"},
        )
        self.assertEqual(result.action_taken, "investigation_unavailable")
        self.assertIn("ANTHROPIC_API_KEY", result.reply_text)
        # No Finding was fabricated from this.
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.findings, [])

    def test_investigation_question_with_a_different_anchor_type_falls_back_to_acknowledgment(self):
        case = self._create_case()
        workspace = self.store.get(self.project_id)
        from services.conversation_interpreter import interpret_message

        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        result = interpret_message(
            text="Why is this like this?",
            workspace=workspace,
            case=case,
            store=self.store,
            artifacts_dir=artifacts_dir,
            reviewer="owner1",
            focused_finding_id=None,
            anchor={"anchor_type": "source", "anchor_id": "some-source-id", "description": "a Source"},
        )
        # Not a Case-shaped decline, not a real investigation - a Source
        # anchor is out of this feature's proving-ground scope.
        self.assertEqual(result.action_taken, "anchor_acknowledged")

    def test_real_investigation_creates_a_provisional_finding_with_a_mocked_model(self):
        requirement = self._register_requirement()
        case = self._create_case()
        workspace = self.store.get(self.project_id)
        case = next(c for c in workspace.cases if c["id"] == case["id"])

        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = (
            '{"assessment": "No conflicting evidence is on record for this Requirement.", '
            '"confidence": 0.55, "supporting_points": [], '
            '"open_questions": ["No adjudication has been recorded yet"], '
            '"needs_human_judgment": true}'
        )
        fake_response = MagicMock()
        fake_response.content = [fake_block]

        from services.conversation_interpreter import interpret_message

        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = fake_response
            result = interpret_message(
                text="Check this",
                workspace=workspace,
                case=case,
                store=self.store,
                artifacts_dir=artifacts_dir,
                reviewer="owner1",
                focused_finding_id=None,
                anchor={"anchor_type": "requirement", "anchor_id": requirement["id"], "description": "Section 3.1"},
            )

        self.assertTrue(result.action_taken.startswith("analysis:"))
        self.assertIn("55%", result.reply_text)
        self.assertIn("No adjudication has been recorded yet", result.reply_text)
        self.assertIn("professional judgment", result.reply_text)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.findings), 1)
        finding = workspace.findings[0]
        self.assertEqual(finding["case_id"], case["id"])
        self.assertEqual(finding["claim_status"], "provisional")
        self.assertIn("No conflicting evidence", finding["statement"])
        self.assertAlmostEqual(finding["machine_confidence"], 0.55)

        analysis = workspace.analyses[0]
        self.assertEqual(analysis["engine_name"], "anthropic-requirement-investigation")


if __name__ == "__main__":
    unittest.main()
