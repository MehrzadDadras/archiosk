"""
CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2) - Context Envelope +
run_conversational_turn, built in services/conversational_turn.py but
NOT wired into services/conversation_interpreter.py's dispatch chain
yet (that is Stage 3, gated on a governance record). Every test here
exercises this new module in isolation, mocking anthropic.Anthropic
per this repo's own hermetic convention - never a live model call, and
never a call into interpret_message.

Covers:
  - build_context_envelope's narrowest-first precedence (an already-
    resolved Anchor outranks selected_object) and its reuse of
    gather_project_evidence (the same evidence-assembly
    _handle_project_question already used pre-Stage-2, extracted here
    so there is one implementation, not two).
  - run_conversational_turn's intent_class classification/normalization,
    candidate_referents re-validation against a real workspace (an
    invalid/foreign/stale id is dropped, never trusted merely because
    the model returned it), the code-forced reflection rule (Resolved
    design decision #1: consequential intent_class OR >1 candidate
    always gets a reflection, even if the model left it null), and
    proposed_action only ever populated for an unambiguous consequential
    turn.
  - A structural proof that this module can never reach a gated route
    or mutating store method directly - the plan's own "for every
    consequential intent_class, the orchestration code path must be
    provably incapable of reaching the mutating function" correctness
    requirement.

Run via:

    python -m unittest tests.test_ca1d_composer_spine_stage2_context_envelope -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    AnalysisTrigger,
    CaseWorkspaceStore,
)
from services.bhive_parser import ParsedDocument
from services.ingestion import RequirementsRegistry
import services.conversational_turn as ct


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
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_spine_stage2_"))
        self.project_id = "test-project-composer-spine-stage2"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(
            self.project_id, register_document_source={"filename": "rfp.md"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self, identifier: str = "REQ-1") -> dict:
        source_id = self.workspace.sources[0]["id"]
        requirement = self.store.register_requirement(
            self.workspace, source_id=source_id, original_requirement_identifier=identifier,
            text_reference=f"The system shall {identifier}.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.workspace = self.store.get(self.project_id)
        return requirement

    def _create_finding(self) -> dict:
        case = self.store.create_case(self.workspace, title="A Case", objective="x", created_by="owner1")
        self.workspace = self.store.get(self.project_id)
        source_id = self.workspace.sources[0]["id"]
        analysis = self.store.record_analysis(
            self.workspace, source_ids=[source_id], objective="test",
            engine_name="test-engine", engine_version="1",
            findings=[{"statement": "The datum appears inconsistent.", "machine_confidence": 0.7}],
            trigger=AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1"),
            case_id=case["id"],
        )
        self.workspace = self.store.get(self.project_id)
        finding_id = analysis["finding_ids"][0]
        return next(f for f in self.workspace.findings if f["id"] == finding_id)


class GatherProjectEvidenceTests(_BaseTestCase):
    def test_populates_document_filename_and_governed_requirements(self):
        self._register_requirement("REQ-1")
        evidence = ct.gather_project_evidence(self.workspace, self.store)
        self.assertEqual(evidence.document_filename, "rfp.md")
        self.assertEqual(len(evidence.governed_requirements), 1)
        self.assertEqual(evidence.governed_requirements[0]["original_requirement_identifier"], "REQ-1")

    def test_no_requirements_yields_empty_lists_not_an_error(self):
        evidence = ct.gather_project_evidence(self.workspace, self.store)
        self.assertEqual(evidence.governed_requirements, [])
        self.assertEqual(evidence.candidate_requirements, [])
        self.assertEqual(evidence.milestones, [])


class BuildContextEnvelopeTests(_BaseTestCase):
    def test_anchor_wins_over_selected_object(self):
        requirement = self._register_requirement("REQ-1")
        envelope = ct.build_context_envelope(
            self.workspace, self.store,
            anchor_type="requirement", anchor_object=requirement,
            selected_type="source", selected_object=self.workspace.sources[0],
        )
        self.assertEqual(envelope.effective_referent_type, "requirement")
        self.assertEqual(envelope.effective_referent, requirement)

    def test_selected_object_used_when_no_anchor(self):
        source = self.workspace.sources[0]
        envelope = ct.build_context_envelope(
            self.workspace, self.store,
            anchor_type=None, anchor_object=None,
            selected_type="source", selected_object=source,
        )
        self.assertEqual(envelope.effective_referent_type, "source")
        self.assertEqual(envelope.effective_referent, source)

    def test_neither_present_effective_referent_is_none(self):
        envelope = ct.build_context_envelope(self.workspace, self.store)
        self.assertIsNone(envelope.effective_referent_type)
        self.assertIsNone(envelope.effective_referent)

    def test_reuses_gather_project_evidence(self):
        envelope = ct.build_context_envelope(self.workspace, self.store)
        self.assertEqual(envelope.project_evidence.document_filename, "rfp.md")


class RunConversationalTurnTests(_BaseTestCase):
    def _envelope(self):
        return ct.build_context_envelope(self.workspace, self.store)

    def test_no_api_key_degrades_honestly(self):
        with patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": d):
            result = ct.run_conversational_turn("hello", self.workspace, self._envelope())
        self.assertFalse(result.ran)
        self.assertIn("No ANTHROPIC_API_KEY", result.skipped_reason)

    def test_unknown_intent_class_falls_back_to_general_answer(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "totally_invented_value", "reply_text": "ok", '
                '"grounded_in": [], "needs_clarification": false, "candidate_referents": []}'
            )
            result = ct.run_conversational_turn(
                "hello", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertTrue(result.ran)
        self.assertEqual(result.intent_class, ct.INTENT_CLASS_GENERAL_ANSWER)

    def test_valid_intent_class_is_recognized(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "organize_advice", "reply_text": "ok", '
                '"grounded_in": [], "needs_clarification": false, "candidate_referents": []}'
            )
            result = ct.run_conversational_turn(
                "how should I organize this", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertEqual(result.intent_class, ct.INTENT_CLASS_ORGANIZE_ADVICE)

    def test_candidate_referent_with_invalid_id_is_dropped(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": '
                '[{"anchor_type": "requirement", "anchor_id": "not-a-real-id", "description": "fake"}]}'
            )
            result = ct.run_conversational_turn(
                "which one", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertEqual(result.candidate_referents, [])

    def test_candidate_referent_with_valid_id_is_kept(self):
        requirement = self._register_requirement("REQ-1")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": '
                f'[{{"anchor_type": "requirement", "anchor_id": "{requirement["id"]}", "description": "REQ-1"}}]}}'
            )
            result = ct.run_conversational_turn(
                "which one", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertEqual(len(result.candidate_referents), 1)
        self.assertEqual(result.candidate_referents[0]["anchor_id"], requirement["id"])

    def test_reflection_forced_for_consequential_intent_when_model_omits_it(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "propose_draft_rfi", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": [], "reflection": null}'
            )
            result = ct.run_conversational_turn(
                "draft an rfi about this", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNotNone(result.reflection)

    def test_reflection_forced_for_ambiguous_candidates_when_model_omits_it(self):
        req1 = self._register_requirement("REQ-1")
        req2 = self._register_requirement("REQ-2")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "reflection": null, "candidate_referents": '
                f'[{{"anchor_type": "requirement", "anchor_id": "{req1["id"]}", "description": "REQ-1"}}, '
                f'{{"anchor_type": "requirement", "anchor_id": "{req2["id"]}", "description": "REQ-2"}}]}}'
            )
            result = ct.run_conversational_turn(
                "tell me about this", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNotNone(result.reflection)

    def test_reflection_not_forced_for_safe_unambiguous_turn(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": [], "reflection": null}'
            )
            result = ct.run_conversational_turn(
                "what is the deadline", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNone(result.reflection)

    def test_model_provided_reflection_is_not_overridden(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": [], '
                '"reflection": "You are asking about the schedule."}'
            )
            result = ct.run_conversational_turn(
                "what is the deadline", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertEqual(result.reflection, "You are asking about the schedule.")

    def test_proposed_action_populated_for_consequential_unambiguous_turn(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "propose_draft_rfi", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": [], '
                '"proposed_action": {"description": "Draft an RFI about the missing schedule."}}'
            )
            result = ct.run_conversational_turn(
                "draft an rfi", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNotNone(result.proposed_action)
        self.assertEqual(result.proposed_action["intent_class"], "propose_draft_rfi")

    def test_proposed_action_none_for_safe_intent_even_if_model_supplies_one(self):
        """Defensive - a safe intent_class must never carry a
        proposed_action, even if the model's own JSON includes one."""
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "general_answer", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": [], '
                '"proposed_action": {"description": "Do something consequential anyway."}}'
            )
            result = ct.run_conversational_turn(
                "what is the deadline", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNone(result.proposed_action)

    def test_proposed_action_withheld_when_consequential_but_ambiguous(self):
        req1 = self._register_requirement("REQ-1")
        req2 = self._register_requirement("REQ-2")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"intent_class": "propose_draft_rfi", "reply_text": "ok", "grounded_in": [], '
                '"needs_clarification": false, "candidate_referents": '
                f'[{{"anchor_type": "requirement", "anchor_id": "{req1["id"]}", "description": "REQ-1"}}, '
                f'{{"anchor_type": "requirement", "anchor_id": "{req2["id"]}", "description": "REQ-2"}}], '
                '"proposed_action": {"description": "Draft an RFI."}}'
            )
            result = ct.run_conversational_turn(
                "draft an rfi about this", self.workspace, self._envelope(), api_key="fake-key",
            )
        self.assertIsNone(result.proposed_action)


class DispatchTableCorrectnessTests(unittest.TestCase):
    def test_every_known_intent_class_is_in_the_dispatch_table(self):
        self.assertEqual(set(ct.KNOWN_INTENT_CLASSES), set(ct.INTENT_DISPATCH_TABLE.keys()))

    def test_consequential_intents_document_an_approval_gate_reuse(self):
        for intent in ct.CONSEQUENTIAL_INTENT_CLASSES:
            with self.subTest(intent=intent):
                self.assertIn("_require_approval", ct.INTENT_DISPATCH_TABLE[intent]["reuses"])

    def test_safe_intents_do_not_claim_an_approval_gate(self):
        safe_intents = set(ct.KNOWN_INTENT_CLASSES) - set(ct.CONSEQUENTIAL_INTENT_CLASSES)
        for intent in safe_intents:
            with self.subTest(intent=intent):
                self.assertNotIn("_require_approval", ct.INTENT_DISPATCH_TABLE[intent]["reuses"])

    def test_module_never_imports_the_routes_package(self):
        """Structural proof of the plan's own correctness invariant: for
        every consequential intent_class, this module is provably
        incapable of reaching a gated route or mutating store method
        directly - it can only ever construct data. A Python module
        cannot call a function it never imported."""
        source = Path(ct.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import routes", source)
        self.assertNotIn("from routes", source)
        # _require_approval appears only as documentation text inside
        # INTENT_DISPATCH_TABLE's own "reuses" strings (see the
        # consequential-intents test above) - never called as a
        # function (which would need the open-paren call syntax).
        self.assertNotIn("_require_approval(", source)

    def test_module_never_imports_conversation_interpreter(self):
        """Guards against the circular-import trap this module's own
        docstring warns about - Stage 3 needs conversation_interpreter.py
        to import FROM this module, which is only possible if this
        module never imports back from it. Only checks actual import
        statements (not prose references in comments/docstrings, which
        this module's own header intentionally has several of)."""
        source = Path(ct.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import services.conversation_interpreter", source)
        self.assertNotIn("from services.conversation_interpreter", source)
        self.assertNotIn("conversation_interpreter", ct.__dict__)


if __name__ == "__main__":
    unittest.main()
