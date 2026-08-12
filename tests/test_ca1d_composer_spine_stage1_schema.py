"""
CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 1) - the additive `content_class`/
`candidate_referents` schema on ConversationMessage, and the stamping
rule applied at every existing add_message call site (see the plan's
own Section 5): human messages -> CONTENT_CLASS_HUMAN_AUTHORED;
server-templated fast-path replies -> CONTENT_CLASS_DETERMINISTIC_
CALCULATION (InterpretationResult's own default); _handle_contextual_
reference's resolved-anchor branches (quote stored fields verbatim) ->
CONTENT_CLASS_DIRECT_EVIDENCE_REFERENCE; any reply built from a real
call_llm_json response -> CONTENT_CLASS_AI_PROPOSED.

Changes no live behavior by itself - purely additive instrumentation
for the not-yet-wired-in Stage 2/3 orchestrator. Follows this repo's
own hermetic convention (patch("anthropic.Anthropic"), never a live
model call) for the two AI-proposed cases.

Run via:

    python -m unittest tests.test_ca1d_composer_spine_stage1_schema -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_DETERMINISTIC_CALCULATION,
    CONTENT_CLASS_DIRECT_EVIDENCE_REFERENCE,
    CONTENT_CLASS_HUMAN_AUTHORED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ConversationMessage,
)
from services.ingestion import RequirementsRegistry
from services.bhive_parser import ParsedDocument


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ConversationMessageSchemaTests(unittest.TestCase):
    def test_new_fields_default_safely_for_old_persisted_messages(self):
        message = ConversationMessage(id="m1", role="human", text="hi", created_at="2026-01-01T00:00:00+00:00")
        self.assertIsNone(message.content_class)
        self.assertEqual(message.candidate_referents, [])


class AddMessageValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_spine_stage1_"))
        self.project_id = "test-project-composer-spine-stage1"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_unrecognized_content_class_is_rejected(self):
        workspace = self.store.get(self.project_id)
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(
                workspace, None, role="system", text="x", content_class="not_a_real_class",
            )

    def test_valid_content_class_persists_on_project_level_message(self):
        workspace = self.store.get(self.project_id)
        self.store.add_message(
            workspace, None, role="human", text="hi", content_class=CONTENT_CLASS_HUMAN_AUTHORED,
        )
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.project_conversation[-1]["content_class"], CONTENT_CLASS_HUMAN_AUTHORED)

    def test_valid_content_class_persists_on_case_scoped_message(self):
        workspace = self.store.get(self.project_id)
        case = self.store.create_case(workspace, title="A Case", objective="x", created_by="owner1")
        workspace = self.store.get(self.project_id)
        self.store.add_message(
            workspace, case["id"], role="system", text="x", content_class=CONTENT_CLASS_DETERMINISTIC_CALCULATION,
        )
        workspace = self.store.get(self.project_id)
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertEqual(case["conversation"][-1]["content_class"], CONTENT_CLASS_DETERMINISTIC_CALCULATION)

    def test_candidate_referents_round_trips(self):
        workspace = self.store.get(self.project_id)
        candidates = [{"anchor_type": "requirement", "anchor_id": "req-1", "description": "REQ-1"}]
        self.store.add_message(workspace, None, role="system", text="x", candidate_referents=candidates)
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.project_conversation[-1]["candidate_referents"], candidates)

    def test_omitted_content_class_stays_none(self):
        workspace = self.store.get(self.project_id)
        self.store.add_message(workspace, None, role="system", text="x")
        workspace = self.store.get(self.project_id)
        self.assertIsNone(workspace.project_conversation[-1]["content_class"])


class InterpreterContentClassStampingTests(unittest.TestCase):
    """
    Exercises the full route stack (mirrors
    tests/test_requirement_investigation.py's own
    RequirementInvestigationInterpreterTests setup) to prove
    _run_conversation_turn actually stamps content_class as designed,
    not merely that InterpretationResult carries the right default.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_spine_stage1_routes_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-spine-stage1-routes"

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

    def test_human_message_stamped_human_authored(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "thanks, noted"},
        )
        workspace = self.store.get(self.project_id)
        human_message = workspace.project_conversation[-2]
        self.assertEqual(human_message["role"], "human")
        self.assertEqual(human_message["content_class"], CONTENT_CLASS_HUMAN_AUTHORED)

    def test_unanchored_contextual_reference_defaults_to_deterministic(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={"text": "tell me about this"},
        )
        workspace = self.store.get(self.project_id)
        system_reply = workspace.project_conversation[-1]
        self.assertEqual(system_reply["action_taken"], "contextual_reference_unavailable")
        self.assertEqual(system_reply["content_class"], CONTENT_CLASS_DETERMINISTIC_CALCULATION)

    def test_resolved_requirement_anchor_stamped_direct_evidence_reference(self):
        requirement = self._register_requirement()
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "tell me about this",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        workspace = self.store.get(self.project_id)
        system_reply = workspace.project_conversation[-1]
        self.assertIn("Section 3.1", system_reply["text"])
        self.assertEqual(system_reply["content_class"], CONTENT_CLASS_DIRECT_EVIDENCE_REFERENCE)

    def test_real_investigation_success_stamped_ai_proposed(self):
        requirement = self._register_requirement()
        case = self._create_case()
        workspace = self.store.get(self.project_id)
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        self.store.add_message(
            workspace, case["id"], role="human", text="Check this", actor="owner1",
            anchor={"anchor_type": "requirement", "anchor_id": requirement["id"], "description": "Section 3.1"},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED,
        )

        fake_response = _mock_response(
            '{"assessment": "No conflicting evidence is on record for this Requirement.", '
            '"confidence": 0.55, "supporting_points": [], '
            '"open_questions": ["No adjudication has been recorded yet"], '
            '"needs_human_judgment": true}'
        )

        from services.conversation_interpreter import interpret_message

        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = fake_response
            result = interpret_message(
                text="Check this",
                workspace=self.store.get(self.project_id),
                case=case,
                store=self.store,
                artifacts_dir=artifacts_dir,
                reviewer="owner1",
                focused_finding_id=None,
                anchor={"anchor_type": "requirement", "anchor_id": requirement["id"], "description": "Section 3.1"},
            )

        self.assertTrue(result.action_taken.startswith("analysis:"))
        self.assertEqual(result.content_class, CONTENT_CLASS_AI_PROPOSED)

    def test_project_question_answered_stamped_ai_proposed(self):
        fake_response = _mock_response(
            '{"answer": "This is a test project.", "grounded_in": [], '
            '"not_covered": "", "needs_clarification": false}'
        )
        from services.conversation_interpreter import interpret_message

        self.client.get(f"/projects/{self.project_id}/workspace")
        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        workspace = self.store.get(self.project_id)
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = fake_response
            result = interpret_message(
                text="What is this project about?",
                workspace=workspace,
                case=None,
                store=self.store,
                artifacts_dir=artifacts_dir,
                reviewer="owner1",
                focused_finding_id=None,
                anchor=None,
            )
        self.assertEqual(result.action_taken, "project_qa_answered")
        self.assertEqual(result.content_class, CONTENT_CLASS_AI_PROPOSED)

    def test_rfi_cancel_reply_stamped_deterministic(self):
        case = self._create_case()
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/rfi-drafts/cancel",
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        case = next(c for c in workspace.cases if c["id"] == case["id"])
        self.assertEqual(case["conversation"][-1]["action_taken"], "rfi_cancelled")
        self.assertEqual(case["conversation"][-1]["content_class"], CONTENT_CLASS_DETERMINISTIC_CALCULATION)


if __name__ == "__main__":
    unittest.main()
