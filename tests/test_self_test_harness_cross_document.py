"""
CLAUDE-P14 - hermetic tests for the cross-document self-test tier's own
plumbing (real CaseWorkspaceStore registration, the real Supersession-
tracked mutation, and the evaluator's both-anchors check together).
Uses a real, throwaway CaseWorkspaceStore (fast, in-process, no network)
- NOT a mocked consistency-check result this time, since the point here
is proving the GOLDEN CORPUS + MUTATION machinery is correct, which
needs no model call at all. The real, billed, blind model run against
this exact corpus is tools/self_test_lab_002_cross_document.py - a
separate, hand-run exercise, never invoked by the automated suite.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ConsistencyFlag
from services.case_workspace import CaseWorkspaceStore
from tests.self_test.evaluator import evaluate
from tests.self_test.golden_corpus_cross_document import (
    APPENDIX_TEXT,
    RFP_TEXT,
    build_cross_document_golden_project,
)
from tests.self_test.mutations_cross_document import (
    MUTATED_APPENDIX_TEXT,
    apply_cross_document_inconsistency,
)


class CrossDocumentGoldenCorpusTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_cross_document_golden_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _build(self):
        return build_cross_document_golden_project(
            self.store, project_id="proj-x", sources_dir=self.tmp_dir / "sources",
        )

    def test_two_real_separate_sources_are_registered(self):
        project = self._build()
        workspace = project["workspace"]
        self.assertEqual(len(workspace.sources), 2)
        self.assertNotEqual(project["rfp_source_id"], project["appendix_source_id"])

    def test_each_requirement_points_at_its_own_source(self):
        project = self._build()
        workspace = project["workspace"]
        rfp_req = next(r for r in workspace.requirements if r["id"] == project["rfp_requirement_id"])
        appendix_req = next(r for r in workspace.requirements if r["id"] == project["appendix_requirement_id"])
        self.assertEqual(rfp_req["source_id"], project["rfp_source_id"])
        self.assertEqual(appendix_req["source_id"], project["appendix_source_id"])

    def test_both_requirements_state_96_hours_before_any_mutation(self):
        project = self._build()
        workspace = project["workspace"]
        for req_id in (project["rfp_requirement_id"], project["appendix_requirement_id"]):
            req = next(r for r in workspace.requirements if r["id"] == req_id)
            self.assertIn("96 hours", req["text_reference"])

    def test_fresh_project_every_call(self):
        project_a = self._build()
        project_b = build_cross_document_golden_project(
            self.store, project_id="proj-y", sources_dir=self.tmp_dir / "sources_2",
        )
        self.assertNotEqual(project_a["rfp_requirement_id"], project_b["rfp_requirement_id"])


class CrossDocumentMutationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_cross_document_mutation_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project = build_cross_document_golden_project(
            self.store, project_id="proj-x", sources_dir=self.tmp_dir / "sources",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_only_the_appendix_requirement_is_revised(self):
        answer_key = apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)

        rfp_req = next(r for r in workspace.requirements if r["id"] == self.project["rfp_requirement_id"])
        self.assertIn("96 hours", rfp_req["text_reference"])
        self.assertEqual(rfp_req["status"], "active")

    def test_original_appendix_requirement_becomes_superseded_not_deleted(self):
        apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)
        original = next(r for r in workspace.requirements if r["id"] == self.project["appendix_requirement_id"])
        self.assertEqual(original["status"], "superseded")
        self.assertIn("96 hours", original["text_reference"])

    def test_answer_key_points_at_the_new_current_successor_id(self):
        answer_key = apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)
        successor = next(r for r in workspace.requirements if r["id"] == answer_key.secondary_location)
        self.assertIn("72 hours", successor["text_reference"])
        self.assertEqual(successor["status"], "active")
        self.assertNotEqual(answer_key.secondary_location, self.project["appendix_requirement_id"])

    def test_answer_key_location_is_the_untouched_rfp_requirement(self):
        answer_key = apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )
        self.assertEqual(answer_key.location, self.project["rfp_requirement_id"])

    def test_a_real_supersession_record_exists(self):
        apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )
        workspace = self.store.get(self.project["workspace"].project_id)
        supersessions = [
            s for s in workspace.supersessions if s["predecessor_id"] == self.project["appendix_requirement_id"]
        ]
        self.assertEqual(len(supersessions), 1)


class CrossDocumentEvaluationTests(unittest.TestCase):
    """Proves the evaluator correctly grades a REALISTIC flag shape for
    this tier (both real, freshly-minted ids) without needing a real
    model call - the actual model call is proven separately, for real,
    by tools/self_test_lab_002_cross_document.py."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_cross_document_eval_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project = build_cross_document_golden_project(
            self.store, project_id="proj-x", sources_dir=self.tmp_dir / "sources",
        )
        self.answer_key = apply_cross_document_inconsistency(
            self.store, self.project["workspace"], self.project["rfp_requirement_id"],
            self.project["appendix_requirement_id"],
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_a_correctly_targeted_flag_is_fully_caught(self):
        flag = ConsistencyFlag(
            id="f1", requirement_a_id=self.project["rfp_requirement_id"], requirement_a_text=RFP_TEXT,
            requirement_b_id=self.answer_key.secondary_location, requirement_b_text=MUTATED_APPENDIX_TEXT,
            explanation="96h vs 72h mismatch.",
        )
        result = evaluate(flags=[flag], answer_key=[self.answer_key])
        self.assertEqual(result.caught, [self.answer_key.mutation_id])
        self.assertEqual(result.both_anchors_correct, [self.answer_key.mutation_id])

    def test_citing_the_stale_superseded_appendix_id_does_not_fully_match(self):
        """If a flag cited the OLD (now-superseded) appendix id instead
        of the real current one, that's a real, meaningful miss on the
        both-anchors question - not something to paper over."""
        flag = ConsistencyFlag(
            id="f2", requirement_a_id=self.project["rfp_requirement_id"], requirement_a_text=RFP_TEXT,
            requirement_b_id=self.project["appendix_requirement_id"], requirement_b_text="stale reference",
            explanation="Cites the frozen predecessor, not the live successor.",
        )
        result = evaluate(flags=[flag], answer_key=[self.answer_key])
        self.assertEqual(result.both_anchors_correct, [])


if __name__ == "__main__":
    unittest.main()
