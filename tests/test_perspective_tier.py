"""
CLAUDE-P17 - hermetic tests for the perspective-sensitive risk/opportunity
tier: Golden Corpus construction (real store calls - Participants,
Requirements, Sources) and requirement_investigation.py's three new
prompt guardrails (anti-zero-sum, perspective-neutral obligation,
ambiguity honesty) actually reaching the model prompt. Proven with a
mocked model call. The real, billed, blind model run against this exact
corpus is tools/self_test_lab_005_perspective.py - hand-run, never
invoked by the automated suite.

Perspective-mechanics coverage (convergence, disagreement, route wiring,
navigation-membrane badges) already lives in tests/test_perspective_
assessment.py from CLAUDE-P12R/P13 and is deliberately not repeated
here - this file covers only what CLAUDE-P17 actually added.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    PARTICIPANT_ROLE_DESIGN_BUILDER,
    PARTICIPANT_ROLE_OWNER,
    CaseWorkspaceStore,
)
from services.requirement_investigation import investigate_requirement
from tests.self_test.golden_corpus_perspective import build_perspective_golden_corpus


class PerspectiveGoldenCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_perspective_corpus_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_registers_two_real_participants_and_five_requirements(self):
        corpus = build_perspective_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = corpus["workspace"]
        self.assertEqual(len(workspace.participants), 2)
        self.assertEqual(len(workspace.requirements), 5)
        self.assertEqual(corpus["owner"]["role_type"], PARTICIPANT_ROLE_OWNER)
        self.assertEqual(corpus["design_builder"]["role_type"], PARTICIPANT_ROLE_DESIGN_BUILDER)

    def test_every_requirement_has_its_own_real_source(self):
        corpus = build_perspective_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = corpus["workspace"]
        source_ids = {r["source_id"] for r in workspace.requirements}
        self.assertEqual(len(source_ids), 5)


class ProspectiveGuardrailPromptTests(unittest.TestCase):
    """
    Proves the three CLAUDE-P17 guardrails reach the real prompt sent to
    the model whenever a represented_party is given - not asserting on
    exact wording (that's free to be edited), just that each guardrail's
    substance is present, via requirement_investigation._build_prompt
    (exercised through the public investigate_requirement entry point,
    same as every other test in this file, mocking only the network
    call).
    """

    def _mock_response(self, payload: dict):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = __import__("json").dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def _run_and_capture_prompt(self, represented_party: dict) -> str:
        requirement = {
            "id": "req-1", "original_requirement_identifier": "Section 1", "status": "active",
            "text_reference": "The Design-Builder shall be responsible for X.",
        }
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.8, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": False,
                "risk_polarity": "risk", "risk_confidence": 0.7, "risk_reasoning": "x",
            })
            investigate_requirement(
                question="How should I read this?", requirement=requirement,
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                represented_party=represented_party, api_key="fake-key-for-test",
            )
            return MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

    def test_anti_zero_sum_guardrail_present(self):
        prompt = self._run_and_capture_prompt({"name": "Aurora Infrastructure Partners", "role_type": "design_builder"})
        self.assertIn("zero-sum", prompt)
        self.assertIn("does NOT imply", prompt)

    def test_perspective_neutral_obligation_guardrail_present(self):
        prompt = self._run_and_capture_prompt({"name": "Meridian Transit Authority", "role_type": "owner"})
        self.assertIn("life-safety", prompt)
        self.assertIn("commercial 'opportunity'", prompt)

    def test_ambiguity_honesty_guardrail_present(self):
        prompt = self._run_and_capture_prompt({"name": "Meridian Transit Authority", "role_type": "owner"})
        self.assertIn("low risk_confidence", prompt)
        self.assertIn("genuine allocation ambiguity", prompt)

    def test_no_represented_party_means_no_guardrail_text_at_all(self):
        requirement = {
            "id": "req-1", "original_requirement_identifier": "Section 1", "status": "active",
            "text_reference": "The Design-Builder shall be responsible for X.",
        }
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.8, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": False,
            })
            investigate_requirement(
                question="What does this mean?", requirement=requirement,
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                represented_party=None, api_key="fake-key-for-test",
            )
            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertNotIn("zero-sum", prompt)
        self.assertNotIn("life-safety", prompt)


if __name__ == "__main__":
    unittest.main()
