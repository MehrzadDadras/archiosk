"""
CLAUDE-P18 - hermetic tests for the lifecycle-migration tier. Two kinds
of claim, deliberately kept separate:

1. DETERMINISTIC RECONSTRUCTION - "what currently governs, given any id
   in the chain" and "what did this used to be" are answered ONLY by
   calling the real store methods (current_requirement_for,
   requirement_predecessor, relationships_for) against real Golden
   Corpus records. No model call is needed to prove this, and none is
   used here - this is the actual, mechanical backbone of "governed
   project memory over time," provable on every run, for free.

2. PRODUCTION WIRING - proves conversation_interpreter.py's CLAUDE-P18
   fix (a Relationship pointing at a Requirement that has ITSELF since
   been superseded now also surfaces that Requirement's CURRENT
   successor, not just its stale text) actually reaches the real model
   prompt, via a mocked Anthropic call - the same pattern as every prior
   tier's ProductionWiringTests.

The real, billed, blind model run for the judgment-requiring dimensions
(contractual-vs-physical, risk migration, late-evidence revision, missing
links) is tools/self_test_lab_006_lifecycle.py - hand-run, never invoked
by the automated suite.

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

from services.bhive_parser import ParsedDocument
from services.case_workspace import (
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_IMPLEMENTS,
    RELATIONSHIP_TYPE_SUPPORTS,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry
from tests.self_test.golden_corpus_lifecycle import build_clean_lifecycle_golden_corpus
from tests.self_test.mutations_lifecycle import (
    build_contract_vs_physical_project,
    build_missing_corrective_link_project,
    build_stale_downstream_design_project,
)


class LifecycleGoldenCorpusConstructionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_lifecycle_corpus_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_clean_corpus_registers_nine_requirements_and_real_provenance(self):
        corpus = build_clean_lifecycle_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = corpus["workspace"]
        # intent, rfp, addendum, proposal, cr17, design_30, calc_60, submittal, commissioning
        self.assertEqual(len(workspace.requirements), 9)
        source_ids = {r["source_id"] for r in workspace.requirements}
        self.assertEqual(len(source_ids), 9, "every stage must have its own real Source")

    def test_two_real_participants_and_a_case_exist(self):
        corpus = build_clean_lifecycle_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = corpus["workspace"]
        self.assertEqual(len(workspace.participants), 2)
        self.assertEqual(len(workspace.cases), 1)

    def test_corrective_action_activity_is_recorded(self):
        corpus = build_clean_lifecycle_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")
        workspace = self.store.get(corpus["workspace"].project_id)
        self.assertEqual(len(workspace.activities), 1)
        self.assertEqual(workspace.activities[0]["kind"], "corrective-action")


class DeterministicReconstructionTests(unittest.TestCase):
    """
    The actual core claim of this tier: "governed project memory over
    time" is provable with zero model calls, purely from real store
    methods against real Supersession/Relationship records.
    """

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_lifecycle_reconstruct_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.corpus = build_clean_lifecycle_golden_corpus(self.store, "proj-x", self.tmp_dir / "sources")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_current_governing_requirement_from_every_point_in_the_authority_chain(self):
        for start_id in (self.corpus["rfp_72_id"], self.corpus["addendum_96_id"], self.corpus["cr17_96_id"]):
            current = self.store.current_requirement_for(self.corpus["workspace"], start_id)
            self.assertEqual(current["id"], self.corpus["cr17_96_id"], f"starting from {start_id}")

    def test_current_best_evidence_from_every_point_in_the_evidence_chain(self):
        for start_id in (
            self.corpus["design_30_id"], self.corpus["calc_60_id"],
            self.corpus["submittal_94_id"], self.corpus["commissioning_98_id"],
        ):
            current = self.store.current_requirement_for(self.corpus["workspace"], start_id)
            self.assertEqual(current["id"], self.corpus["commissioning_98_id"], f"starting from {start_id}")

    def test_backward_walk_reconstructs_predecessor_at_every_hop(self):
        workspace = self.corpus["workspace"]
        self.assertEqual(
            self.store.requirement_predecessor(workspace, self.corpus["cr17_96_id"])["id"],
            self.corpus["addendum_96_id"],
        )
        self.assertEqual(
            self.store.requirement_predecessor(workspace, self.corpus["addendum_96_id"])["id"],
            self.corpus["rfp_72_id"],
        )
        self.assertIsNone(self.store.requirement_predecessor(workspace, self.corpus["rfp_72_id"]))
        self.assertEqual(
            self.store.requirement_predecessor(workspace, self.corpus["commissioning_98_id"])["id"],
            self.corpus["submittal_94_id"],
        )

    def test_stale_intermediate_records_are_marked_superseded_but_never_deleted(self):
        workspace = self.corpus["workspace"]
        rfp = next(r for r in workspace.requirements if r["id"] == self.corpus["rfp_72_id"])
        submittal = next(r for r in workspace.requirements if r["id"] == self.corpus["submittal_94_id"])
        commissioning = next(r for r in workspace.requirements if r["id"] == self.corpus["commissioning_98_id"])
        self.assertEqual(rfp["status"], "superseded")
        self.assertIn("72 hours", rfp["text_reference"])
        self.assertEqual(submittal["status"], "superseded")
        self.assertIn("94 hours", submittal["text_reference"], "the shortfall must remain readable, not rewritten")
        self.assertEqual(commissioning["status"], "active")

    def test_proposal_is_active_but_never_governing_and_never_superseded(self):
        # The Proposal was never itself the governing record, so it has no
        # predecessor/successor of its own - distinguishing "historically
        # non-governing" from "formerly governing, now superseded" is a
        # different signal than status alone.
        workspace = self.corpus["workspace"]
        proposal = next(r for r in workspace.requirements if r["id"] == self.corpus["proposal_72_id"])
        self.assertEqual(proposal["status"], "active")
        self.assertIsNone(self.store.requirement_predecessor(workspace, self.corpus["proposal_72_id"]))
        self.assertEqual(
            self.store.current_requirement_for(workspace, self.corpus["proposal_72_id"])["id"],
            self.corpus["proposal_72_id"],
        )

    def test_relationships_correctly_wired_across_the_whole_chain(self):
        workspace = self.corpus["workspace"]
        rfp_rels = self.store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, self.corpus["rfp_72_id"])
        self.assertTrue(any(r["relationship_type"] == RELATIONSHIP_TYPE_IMPLEMENTS for r in rfp_rels))

        proposal_rels = self.store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, self.corpus["proposal_72_id"])
        contradicts = [r for r in proposal_rels if r["relationship_type"] == RELATIONSHIP_TYPE_CONTRADICTS]
        self.assertEqual(len(contradicts), 1)
        self.assertEqual(contradicts[0]["to_id"], self.corpus["addendum_96_id"], "points at the stale Addendum record")

        commissioning_rels = self.store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, self.corpus["commissioning_98_id"])
        self.assertTrue(any(r["relationship_type"] == RELATIONSHIP_TYPE_SUPPORTS for r in commissioning_rels))

    def test_snapshot_freezes_ids_not_field_values_per_its_own_documented_limitation(self):
        """
        Snapshot's own docstring is explicit: it freezes WHICH ids
        existed, never the field values on records mutated in place -
        and Requirement.status is exactly such a field. Take a Snapshot
        AFTER the clean corpus is complete (rfp_72 is by now superseded);
        resolving the Snapshot's reference back to that same id must
        show its CURRENT status, not what it was at freeze time - proving
        why CLAUDE-P18 Case E relies on immutable Finding/InvestigationStep
        text for point-in-time reasoning, never on resolving a Snapshot.
        """
        workspace = self.corpus["workspace"]
        snapshot = self.store.create_snapshot(workspace, label="Post-Commissioning", created_by="self-test-lab")
        self.assertIn(self.corpus["rfp_72_id"], snapshot["reference_lists"]["requirements"])
        resolved = self.store.resolve_snapshot_objects(workspace, snapshot["id"], "requirements")
        resolved_rfp = next(r for r in resolved if r["id"] == self.corpus["rfp_72_id"])
        self.assertEqual(resolved_rfp["status"], "superseded")


class MutationConstructionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_lifecycle_mutations_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_case_a_stale_design_contradicts_current_governing_requirement(self):
        project = build_stale_downstream_design_project(self.store, "proj-a", self.tmp_dir / "a")
        workspace = project["workspace"]
        rels = self.store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, project["stale_design_30_id"])
        self.assertEqual(rels[0]["relationship_type"], RELATIONSHIP_TYPE_CONTRADICTS)
        self.assertEqual(rels[0]["to_id"], project["cr17_96_id"])

    def test_case_b_stops_at_submittal_with_no_correction_or_commissioning(self):
        project = build_contract_vs_physical_project(self.store, "proj-b", self.tmp_dir / "b")
        workspace = project["workspace"]
        self.assertEqual(len(workspace.activities), 0)
        submittal = next(r for r in workspace.requirements if r["id"] == project["submittal_94_id"])
        self.assertEqual(submittal["status"], "active", "the submittal IS the current evidence in this truncated chain")

    def test_case_f_commissioning_has_no_supersession_link_back_to_submittal(self):
        project = build_missing_corrective_link_project(self.store, "proj-f", self.tmp_dir / "f")
        workspace = project["workspace"]
        self.assertIsNone(self.store.requirement_predecessor(workspace, project["standalone_commissioning_id"]))
        submittal = next(r for r in workspace.requirements if r["id"] == project["submittal_94_id"])
        self.assertEqual(submittal["status"], "active", "never superseded - nothing on record resolved it")
        self.assertEqual(len(workspace.activities), 0)


class TransitiveSupersessionWiringTests(unittest.TestCase):
    """
    CLAUDE-P18: proves conversation_interpreter.py's new fix - a
    Relationship pointing at a Requirement that has ITSELF since been
    superseded also surfaces that Requirement's CURRENT successor - reaches
    the real production prompt, via the real /discuss + start-investigation
    route, mocking only the network call.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_transitive_wiring_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-transitive-wiring"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _mock_response(self, payload: dict):
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def test_relationship_to_a_since_superseded_requirement_also_surfaces_its_current_successor(self):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        addendum = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Addendum 3",
            text_reference="96 hours.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        cr17, _ = self.store.revise_requirement(
            workspace, requirement_id=addendum["id"], actor="owner1", reason="CR-17",
            text_reference="96 hours, contractual, no Contract Price adjustment.",
        )
        proposal = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Proposal",
            text_reference="Design-Builder proposes 72 hours.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.store.record_relationship(
            workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=proposal["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=addendum["id"],
            relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, created_by="owner1",
        )

        self.store.create_case(workspace, title="Case A", objective="x", created_by="owner1")

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = self._mock_response({
                "assessment": "x", "confidence": 0.8, "supporting_points": [],
                "open_questions": [], "needs_human_judgment": False, "flagged_stale_ids": [],
            })
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={
                    "text": "Check this", "anchor_type": "requirement",
                    "anchor_id": proposal["id"], "anchor_description": "Proposal",
                },
            )
            workspace = self.store.get(self.project_id)
            system_message = workspace.project_conversation[-1]
            message_id = system_message["action_taken"].split(":", 1)[1]
            self.client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")

            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]

        # The stale Addendum text must still appear (it's the direct
        # relationship target) - AND the CR-17 text it was itself
        # superseded by must ALSO appear, per the CLAUDE-P18 fix.
        self.assertIn("96 hours.", prompt)
        self.assertIn("contractual, no Contract Price adjustment", prompt)
        self.assertIn("CURRENT governing successor", prompt)


if __name__ == "__main__":
    unittest.main()
