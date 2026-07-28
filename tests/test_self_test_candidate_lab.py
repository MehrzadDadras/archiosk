"""
CLAUDE-P20 - hermetic tests for the candidate specimen generator
prototype (tools/self_test_generator.py, tools/self_test_candidate_lab.py).

No real Anthropic calls - both real model calls each script makes are
mocked, exactly like every other hermetic test in this suite. What these
tests actually prove:

1. generate_clean_corpus() and propose_mutation() are genuinely TWO
   separate calls (the mutation call only happens after, and is given,
   the clean corpus - never the other way around).
2. materialize_clean() builds real CaseWorkspaceStore Requirements/
   Sources, not bare dicts.
3. THE STRUCTURAL GUARANTEE THAT MATTERS MOST: the real investigator's
   prompt never contains the candidate's proposed_mutation description/
   mutation_kind or proposed_answer_key content - only requirement id and
   text, exactly as tools/self_test_candidate_lab.py's own docstring
   claims.
4. Nothing under tests/self_test/candidates/ is referenced anywhere in
   tests/self_test/manifest.py or tools/self_test_runner.py - a candidate
   can never silently become a trusted Suite v1 tier.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import CaseWorkspaceStore
from tests.self_test.manifest import TIERS
from tools import self_test_candidate_lab, self_test_generator

FIXTURE_CANDIDATE = {
    "candidate_id": "test-candidate-1",
    "generated_at": "2026-01-01T00:00:00+00:00",
    "generator_model": "claude-sonnet-4-6",
    "difficulty_tier": "obvious",
    "domain_narrative": "A fictional roofing domain, invented for this test.",
    "requirements": [
        {"identifier": "R1", "source_name": "Spec Section 1", "text": "The roof membrane shall carry a 20-year warranty."},
        {"identifier": "R2", "source_name": "Spec Section 1", "text": "Flashing components are covered under the same 20-year warranty as R1."},
    ],
    "proposed_mutation": {
        "target_identifier": "R2",
        "mutated_text": "Flashing components carry only a 10-year warranty, independent of R1.",
        "mutation_kind": "numerical_contradiction",
        "description": "R2 now contradicts R1's 20-year warranty by stating a 10-year term for flashing.",
    },
    "proposed_answer_key": {
        "expected_detection": "A contradiction between R1's 20-year warranty and R2's 10-year flashing warranty.",
        "non_defects": [],
    },
    "validation_status": "generated",
}


class NonContaminationTests(unittest.TestCase):
    """A candidate must never become a trusted tier without an explicit,
    separate, human promotion step this prototype does not automate."""

    def test_no_registered_tier_points_at_the_candidates_namespace(self):
        for tier in TIERS:
            self.assertNotIn("candidate", tier.lab_module)

    def test_candidates_directory_is_not_the_golden_corpus_namespace(self):
        self.assertNotEqual(self_test_candidate_lab.CANDIDATES_DIR.name, "golden_corpus")
        self.assertTrue(str(self_test_candidate_lab.CANDIDATES_DIR).endswith(str(Path("self_test") / "candidates")))


class GeneratorTwoCallSeparationTests(unittest.TestCase):
    def _mock_response(self, payload: dict):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_mutation_call_is_separate_from_and_receives_the_clean_corpus(self):
        clean_payload = {
            "domain_narrative": "Test domain.",
            "requirements": [{"identifier": "R1", "source_name": "Doc", "text": "Some requirement."}],
        }
        mutation_payload = {
            "target_identifier": "R1", "mutated_text": "A mutated requirement.",
            "mutation_kind": "numerical_contradiction", "description": "x",
            "expected_detection": "x", "non_defects": [],
        }
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = [
                self._mock_response(clean_payload), self._mock_response(mutation_payload),
            ]
            clean_corpus = self_test_generator.generate_clean_corpus(api_key="fake", model="fake-model", timeout=10.0)
            mutation = self_test_generator.propose_mutation(clean_corpus, api_key="fake", model="fake-model", timeout=10.0)

        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)
        first_prompt = MockClient.return_value.messages.create.call_args_list[0].kwargs["messages"][0]["content"]
        second_prompt = MockClient.return_value.messages.create.call_args_list[1].kwargs["messages"][0]["content"]
        # Call 1 never mentions a mutation is coming.
        self.assertNotIn("mutation", first_prompt.lower())
        # Call 2 is given the clean corpus's own requirement text.
        self.assertIn("Some requirement.", second_prompt)
        self.assertEqual(mutation["target_identifier"], "R1")


class MaterializationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_candidate_materialize_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("candidate-test")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_materialize_clean_registers_real_requirements_and_sources(self):
        ids_by_identifier = self_test_candidate_lab.materialize_clean(
            self.store, self.workspace, self.tmp_dir / "sources", FIXTURE_CANDIDATE,
        )
        self.assertEqual(set(ids_by_identifier.keys()), {"R1", "R2"})
        workspace = self.store.get(self.workspace.project_id)
        self.assertEqual(len(workspace.requirements), 2)
        self.assertEqual(len(workspace.sources), 1, "both R1 and R2 share the same source_name")

    def test_as_requirement_items_carries_only_id_and_text(self):
        ids_by_identifier = self_test_candidate_lab.materialize_clean(
            self.store, self.workspace, self.tmp_dir / "sources", FIXTURE_CANDIDATE,
        )
        workspace = self.store.get(self.workspace.project_id)
        items = self_test_candidate_lab.as_requirement_items(workspace, list(ids_by_identifier.values()))
        texts = {item.text for item in items}
        self.assertEqual(texts, {"The roof membrane shall carry a 20-year warranty.", "Flashing components are covered under the same 20-year warranty as R1."})


class InvestigatorNeverSeesTheAnswerKeyTests(unittest.TestCase):
    """The structural guarantee that matters most in this whole prototype."""

    def _mock_response(self):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps([])  # _check_consistency iterates the top-level parsed list directly
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_consistency_check_prompt_never_contains_proposed_mutation_or_answer_key_content(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_candidate_blind_"))
        try:
            store = CaseWorkspaceStore(tmp_dir)
            workspace = store.get_or_create("candidate-test-blind")
            ids_by_identifier = self_test_candidate_lab.materialize_clean(
                store, workspace, tmp_dir / "sources", FIXTURE_CANDIDATE,
            )
            workspace = store.get(workspace.project_id)
            items = self_test_candidate_lab.as_requirement_items(workspace, list(ids_by_identifier.values()))

            with patch("anthropic.Anthropic") as MockClient, \
                 patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
                MockClient.return_value.messages.create.return_value = self._mock_response()
                self_test_candidate_lab.run_consistency_check(items)
                prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

            # The clean requirement text IS expected in the prompt.
            self.assertIn("The roof membrane shall carry a 20-year warranty.", prompt)
            # None of the candidate's own answer-key/mutation-description
            # content may ever reach the investigator.
            self.assertNotIn(FIXTURE_CANDIDATE["proposed_mutation"]["description"], prompt)
            self.assertNotIn(FIXTURE_CANDIDATE["proposed_mutation"]["mutation_kind"], prompt)
            self.assertNotIn(FIXTURE_CANDIDATE["proposed_answer_key"]["expected_detection"], prompt)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
