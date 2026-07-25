"""
Foundation Batch K (Prompt 19) tests: Requirement Adjudication - the
human REQUIREMENT-level compliance record, distinct from Disposition
(a Finding-scoped workflow decision) and from Requirement.status
(existence/lifecycle only). Built directly from the scope determined by
this batch's own orientation pass: reuse Finding/ReviewerValidation/
Disposition/Relationship as evidence, add exactly one new append-only
record and its derived-absence state.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    KNOWN_OBJECT_KINDS,
    OBJECT_KIND_REQUIREMENT_ADJUDICATION,
    OBJECT_KIND_SOURCE,
    REQUIREMENT_ADJUDICATION_ACCEPTED_ALTERNATIVE,
    REQUIREMENT_ADJUDICATION_NOT_APPLICABLE,
    REQUIREMENT_ADJUDICATION_NOT_SATISFIED,
    REQUIREMENT_ADJUDICATION_OUTCOMES,
    REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED,
    REQUIREMENT_ADJUDICATION_SATISFIED,
    REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_STATUS_ACTIVE,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class RequirementAdjudicationTests(unittest.TestCase):
    """Tests A-K."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_k_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-k1"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="OPR-001.md", file_path="/tmp/opr.md",
            kind="owner_project_requirements",
        )
        self.requirement = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.1",
            text_reference="Standby power generation shall provide no less than 96 hours "
                            "of operation without refuelling.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _record_finding(self, statement="Generator sizing calc shows 72h autonomy, not 96h."):
        case = self.store.create_case(self.workspace, title="R-12.1 Review", objective="Assess standby power")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[self.source["id"]],
            objective="Assess standby power against R-12.1", engine_name="human-review", engine_version="0.0",
            findings=[{"statement": statement, "machine_confidence": 0.7, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        return analysis["finding_ids"][0]

    # A - Requirement Adjudication is a distinct object kind, not folded into Disposition
    def test_a_object_kind_registered(self):
        self.assertIn(OBJECT_KIND_REQUIREMENT_ADJUDICATION, KNOWN_OBJECT_KINDS)

    # B - basic recording, closed outcome vocabulary enforced
    def test_b_record_adjudication_requires_known_outcome(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                self.workspace, requirement_id=self.requirement["id"],
                outcome="compliant", adjudicator="tester", reasoning="x",
            )

    # C - reasoning is mandatory, not defaulted (ADR-032-R05/R06 honesty machinery)
    def test_c_reasoning_required(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                self.workspace, requirement_id=self.requirement["id"],
                outcome=REQUIREMENT_ADJUDICATION_SATISFIED, adjudicator="tester", reasoning="   ",
            )

    # D - a Requirement never requires a Finding to exist - "Not Applicable"
    # needs no evidence at all.
    def test_d_not_applicable_needs_no_evidence(self):
        record = self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_NOT_APPLICABLE, adjudicator="tester",
            reasoning="This standby-power clause does not apply to the demolition-only package.",
        )
        self.assertEqual(record["evidence_finding_ids"], [])
        self.assertEqual(record["outcome"], REQUIREMENT_ADJUDICATION_NOT_APPLICABLE)

    # E - absence of any adjudication is a DERIVED state, never a stored row
    def test_e_absence_is_derived_not_stored(self):
        state = self.store.requirement_adjudication_state(self.workspace, self.requirement["id"])
        self.assertEqual(state, REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED)
        self.assertEqual(self.store.requirement_adjudications_for(self.workspace, self.requirement["id"]), [])
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.requirement_adjudications, [])

    # F - a real adjudication citing Finding evidence
    def test_f_adjudication_with_finding_evidence(self):
        finding_id = self._record_finding()
        record = self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_NOT_SATISFIED, adjudicator="tester",
            reasoning="Generator sizing calc demonstrates only 72 of the required 96 hours.",
            evidence_finding_ids=[finding_id],
            governance_log=self.gov,
        )
        self.assertEqual(record["evidence_finding_ids"], [finding_id])
        self.assertEqual(
            self.store.requirement_adjudication_state(self.workspace, self.requirement["id"]),
            REQUIREMENT_ADJUDICATION_NOT_SATISFIED,
        )
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "requirement_adjudicated"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].role, "human")

    # G - citing a nonexistent Finding is rejected, not silently accepted
    def test_g_unknown_evidence_finding_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                self.workspace, requirement_id=self.requirement["id"],
                outcome=REQUIREMENT_ADJUDICATION_SATISFIED, adjudicator="tester",
                reasoning="x", evidence_finding_ids=["does-not-exist"],
            )

    # H - unknown Requirement is rejected
    def test_h_unknown_requirement_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                self.workspace, requirement_id="does-not-exist",
                outcome=REQUIREMENT_ADJUDICATION_SATISFIED, adjudicator="tester", reasoning="x",
            )

    # I - append-only: a later adjudication supersedes the earlier one in
    # EFFECT (latest wins) without deleting the prior record.
    def test_i_append_only_history_preserved(self):
        finding_id = self._record_finding()
        first = self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_NOT_SATISFIED, adjudicator="reviewer1",
            reasoning="Initial read: sizing calc shows only 72h.", evidence_finding_ids=[finding_id],
        )
        second = self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_ACCEPTED_ALTERNATIVE, adjudicator="reviewer2",
            reasoning="Owner accepted 72h autonomy plus a confirmed refuelling contract as an alternative.",
        )
        history = self.store.requirement_adjudications_for(self.workspace, self.requirement["id"])
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["id"], first["id"])
        self.assertEqual(history[1]["id"], second["id"])
        self.assertEqual(
            self.store.latest_requirement_adjudication_for(self.workspace, self.requirement["id"])["id"],
            second["id"],
        )
        self.assertEqual(
            self.store.requirement_adjudication_state(self.workspace, self.requirement["id"]),
            REQUIREMENT_ADJUDICATION_ACCEPTED_ALTERNATIVE,
        )

    # J - Requirement.status is never touched by adjudication (the two
    # layers stay separate, per set_requirement_status's own denylist).
    def test_j_requirement_status_untouched_by_adjudication(self):
        self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_NOT_SATISFIED, adjudicator="tester",
            reasoning="Sizing calc shows only 72h.",
        )
        reloaded = self.store.get(self.project_id)
        requirement_after = self.store._find(reloaded.requirements, self.requirement["id"])
        self.assertEqual(requirement_after["status"], REQUIREMENT_STATUS_ACTIVE)

    # K - Relationship evidence is validated too, and Partially Satisfied
    # is a real, distinct outcome from Not Satisfied.
    def test_k_relationship_evidence_and_partial_outcome(self):
        relationship = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=self.source["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=self.source["id"],
            relationship_type="supports", created_by="tester",
        )
        record = self.store.record_requirement_adjudication(
            self.workspace, requirement_id=self.requirement["id"],
            outcome=REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED, adjudicator="tester",
            reasoning="Autonomy requirement met; fuel-quality testing evidence still outstanding.",
            evidence_relationship_ids=[relationship["id"]],
        )
        self.assertEqual(record["evidence_relationship_ids"], [relationship["id"]])
        self.assertIn(REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED, REQUIREMENT_ADJUDICATION_OUTCOMES)
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_requirement_adjudication(
                self.workspace, requirement_id=self.requirement["id"],
                outcome=REQUIREMENT_ADJUDICATION_SATISFIED, adjudicator="tester",
                reasoning="x", evidence_relationship_ids=["does-not-exist"],
            )


if __name__ == "__main__":
    unittest.main()
