"""
CLAUDE-P15 - hermetic tests for the supersession/Addendum tier: the new
CaseWorkspaceStore.current_requirement_for/requirement_predecessor
forward/backward Supersession walks, the corpus/mutation construction
(real revise_requirement calls, real Supersession records), and
requirement_investigation.py's Supersession-awareness extension (status
always stated, related_requirements + flagged_stale_ids) - proven with a
MOCKED model call. The real, billed, blind model run against this exact
corpus is tools/self_test_lab_003_supersession.py - hand-run, never
invoked by the automated suite.

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

from services.case_workspace import CaseWorkspaceStore, REQUIREMENT_REGISTRATION_HUMAN_REGISTERED
from services.requirement_investigation import investigate_requirement
from tests.self_test.golden_corpus_supersession import build_supersession_golden_project
from tests.self_test.mutations_supersession import (
    build_partial_supersession_project,
    build_stale_downstream_project,
)


class SupersessionWalkStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_supersession_walk_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")
        self.source = self.store.add_source(
            self.workspace, name="Src", file_path="x.txt", kind="text_record", actor="test",
        )
        self.original = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="R1",
            text_reference="96 hours", created_by="test",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_current_requirement_for_an_unrevised_requirement_is_itself(self):
        current = self.store.current_requirement_for(self.workspace, self.original["id"])
        self.assertEqual(current["id"], self.original["id"])

    def test_current_requirement_for_a_superseded_id_resolves_to_the_successor(self):
        successor, _ = self.store.revise_requirement(
            self.workspace, requirement_id=self.original["id"], actor="test",
            reason="revised", text_reference="120 hours",
        )
        current = self.store.current_requirement_for(self.workspace, self.original["id"])
        self.assertEqual(current["id"], successor["id"])
        self.assertEqual(current["text_reference"], "120 hours")

    def test_current_requirement_for_walks_a_chain_of_multiple_revisions(self):
        successor_1, _ = self.store.revise_requirement(
            self.workspace, requirement_id=self.original["id"], actor="test",
            reason="rev 1", text_reference="120 hours",
        )
        successor_2, _ = self.store.revise_requirement(
            self.workspace, requirement_id=successor_1["id"], actor="test",
            reason="rev 2", text_reference="144 hours",
        )
        current = self.store.current_requirement_for(self.workspace, self.original["id"])
        self.assertEqual(current["id"], successor_2["id"])

    def test_current_requirement_for_nonexistent_id_returns_none(self):
        self.assertIsNone(self.store.current_requirement_for(self.workspace, "nonexistent"))

    def test_requirement_predecessor_of_an_original_is_none(self):
        self.assertIsNone(self.store.requirement_predecessor(self.workspace, self.original["id"]))

    def test_requirement_predecessor_of_a_successor_is_the_original(self):
        successor, _ = self.store.revise_requirement(
            self.workspace, requirement_id=self.original["id"], actor="test",
            reason="revised", text_reference="120 hours",
        )
        predecessor = self.store.requirement_predecessor(self.workspace, successor["id"])
        self.assertEqual(predecessor["id"], self.original["id"])


class SupersessionGoldenCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_supersession_corpus_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clean_baseline_has_a_real_supersession_chain(self):
        project = build_supersession_golden_project(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = project["workspace"]

        original = next(r for r in workspace.requirements if r["id"] == project["original_rfp_requirement_id"])
        current = next(r for r in workspace.requirements if r["id"] == project["current_rfp_requirement_id"])
        self.assertEqual(original["status"], "superseded")
        self.assertIn("96 hours", original["text_reference"])
        self.assertEqual(current["status"], "active")
        self.assertIn("120 hours", current["text_reference"])

    def test_clean_baseline_appendix_correctly_reflects_current_value(self):
        project = build_supersession_golden_project(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = project["workspace"]
        appendix = next(r for r in workspace.requirements if r["id"] == project["appendix_requirement_id"])
        self.assertIn("120 hours", appendix["text_reference"])
        self.assertEqual(appendix["status"], "active")

    def test_stale_downstream_project_appendix_is_stale(self):
        project = build_stale_downstream_project(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = project["workspace"]
        appendix = next(r for r in workspace.requirements if r["id"] == project["appendix_requirement_id"])
        self.assertIn("96 hours", appendix["text_reference"])
        self.assertEqual(appendix["status"], "active")  # active, but stale relative to governing text

    def test_stale_downstream_answer_key_points_at_the_current_rfp_and_the_appendix(self):
        project = build_stale_downstream_project(self.store, "proj-x", self.tmp_dir / "sources")
        answer_key = project["answer_key"]
        self.assertEqual(answer_key.location, project["current_rfp_requirement_id"])
        self.assertEqual(answer_key.secondary_location, project["appendix_requirement_id"])

    def test_partial_supersession_carries_the_unaffected_clause_forward_verbatim(self):
        project = build_partial_supersession_project(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = project["workspace"]
        current = next(r for r in workspace.requirements if r["id"] == project["current_requirement_id"])
        self.assertIn("120 hours", current["text_reference"])
        self.assertIn("50-year structural service life", current["text_reference"])


class RequirementInvestigationSupersessionPromptTests(unittest.TestCase):
    """Proves the prompt-building/parsing extension with a mocked model
    call - the real call is proven separately by the lab script."""

    def _mock_response(self, payload: dict):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_status_is_always_stated_even_with_no_related_requirements(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.5, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": True,
            })
            investigate_requirement(
                question="q", requirement={"id": "r1", "text_reference": "x", "status": "superseded"},
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                api_key="fake-key-for-test",
            )
            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertIn("This Requirement's own status: superseded.", prompt)

    def test_related_requirements_are_shown_with_their_own_status(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.5, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": True, "flagged_stale_ids": [],
            })
            investigate_requirement(
                question="q", requirement={"id": "r1", "text_reference": "120h", "status": "active"},
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                related_requirements=[
                    {"id": "r0", "original_requirement_identifier": "R0", "text_reference": "96h", "status": "superseded"},
                ],
                api_key="fake-key-for-test",
            )
            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertIn("[r0]", prompt)
            self.assertIn("status: superseded", prompt)
            self.assertIn("PRESERVED", prompt.upper())

    def test_flagged_stale_ids_parsed_only_when_related_requirements_given(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.5, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": True, "flagged_stale_ids": ["r0"],
            })
            result = investigate_requirement(
                question="q", requirement={"id": "r1", "text_reference": "120h", "status": "active"},
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                related_requirements=[
                    {"id": "r0", "original_requirement_identifier": "R0", "text_reference": "96h", "status": "active"},
                ],
                api_key="fake-key-for-test",
            )
            self.assertEqual(result.flagged_stale_ids, ["r0"])

    def test_flagged_stale_ids_absent_without_related_requirements(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.5, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": True,
            })
            result = investigate_requirement(
                question="q", requirement={"id": "r1", "text_reference": "x", "status": "active"},
                adjudication_history=[], evidence={"findings": [], "relationships": [], "accepted_knowledge": []},
                api_key="fake-key-for-test",
            )
            self.assertEqual(result.flagged_stale_ids, [])


if __name__ == "__main__":
    unittest.main()
