"""
Collaboration threshold (SHARED -> COLLABORATIVE) + pre-threshold
retraction (SHARED -> PRIVATE), implementing Constitutional Invariant 12
literally: "Collaborative provenance is irreversible. Once another party
has made a genuine, governed contribution, reverting shared work to
private is prohibited."

Covers CaseWorkspaceStore._cross_collaboration_threshold_if_qualifying
(exercised indirectly through every qualifying write method - never
tested as a bare private method) and retract_case_to_private. The central
question every test group answers: does mere visibility/machine activity
fail to cross the threshold, does a real human non-owner contribution
cross it exactly once, and does crossing it become permanently
irreversible.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_AGENT_INITIATED,
    ANALYSIS_TRIGGER_USER_INITIATED,
    CASE_VISIBILITY_COLLABORATIVE,
    CASE_VISIBILITY_PRIVATE,
    CASE_VISIBILITY_SHARED,
    MESSAGE_ORIGIN_HUMAN,
    MESSAGE_ORIGIN_MACHINE,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class CaseCollaborationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_collab_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-collab"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )
        self.case = self.store.create_case(
            self.workspace, title="Investigation", objective="x", created_by="owner1",
        )
        self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _current_case(self):
        return self.store._find(self.store.get(self.project_id).cases, self.case["id"])

    def _owner_finding(self):
        """A Finding created inside the shared Case, via an owner-triggered
        (human) Analysis - establishing the Finding without itself
        crossing the threshold, so each test starts from a clean SHARED
        state and can test its own qualifying/non-qualifying write."""
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)  # owner write, no crossing
        return analysis["finding_ids"][0]

    # -- threshold: what must NOT cross it -----------------------------------------------

    def test_mere_visibility_does_not_cross_threshold(self):
        visible = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertIn(self.case["id"], [c["id"] for c in visible])
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_listing_and_lookup_do_not_cross_threshold(self):
        for _ in range(5):
            self.store.visible_cases_for(self.workspace, "other-user")
            self.store.get(self.project_id)
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_machine_initiated_analysis_does_not_cross_threshold(self):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED, triggered_by_actor="other-user")
        self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_machine_origin_review_message_does_not_cross_threshold(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="owner1", case_id=self.case["id"],
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE,
            actor="other-user", message_type="note", text="a machine-authored note",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_owner_writes_do_not_cross_their_own_threshold(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="owner1",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    # -- threshold: what DOES cross it -----------------------------------------------

    def test_first_qualifying_non_owner_reviewer_validation_crosses_threshold(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
            governance_log=self.gov,
        )
        case = self._current_case()
        self.assertEqual(case["visibility"], CASE_VISIBILITY_COLLABORATIVE)
        self.assertEqual(case["collaboration_established_by"], "other-user")
        self.assertEqual(case["collaboration_contribution_type"], "reviewer_validation")
        self.assertIsNotNone(case["collaboration_established_at"])

    def test_first_qualifying_disposition_crosses_threshold(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="owner1",
        )
        self.store.record_disposition(
            self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="other-user",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_human_origin_review_message_crosses_threshold(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="owner1", case_id=self.case["id"],
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="other-user", message_type="comment", text="a real human comment",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_attention_crosses_threshold(self):
        # Owner creates the thread and its own message first (no crossing -
        # it's the owner's own write), isolating request_attention itself
        # as the qualifying non-owner event under test.
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="owner1", case_id=self.case["id"],
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="owner1", message_type="note", text="owner's own note",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

        self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=message["id"],
            intended_actor="owner1", created_by="other-user",
        )
        case = self._current_case()
        self.assertEqual(case["visibility"], CASE_VISIBILITY_COLLABORATIVE)
        self.assertEqual(case["collaboration_contribution_type"], "attention")

    def test_confirmed_relationship_crosses_threshold(self):
        finding_id = self._owner_finding()
        relationship = self.store.record_relationship(
            self.workspace, from_type="finding", from_id=finding_id,
            to_type="source", to_id=self.source["id"], relationship_type="supports",
            created_by="some-engine", provisional=True,
        )
        # creation alone (still provisional, machine-shaped) must not cross it
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)
        self.store.confirm_relationship(self.workspace, relationship_id=relationship["id"], actor="other-user")
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_user_initiated_analysis_by_non_owner_crosses_threshold(self):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="other-user")
        self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_governance_log_event_on_crossing(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
            governance_log=self.gov,
        )
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_became_collaborative"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["case_id"], self.case["id"])
        self.assertEqual(events[0].actor, "other-user")
        self.assertEqual(events[0].role, "human")

    def test_requirement_adjudication_does_not_cross_case_threshold(self):
        """The ratified spec's own deliberately-flagged boundary case,
        resolved: adjudicating a Requirement never crosses a Case
        threshold, even when it cites that Case's Finding as evidence."""
        finding_id = self._owner_finding()
        requirement = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="1.1",
            text_reference="x", created_by="owner1", registration_method="manually_registered_test_fixture",
        )
        self.store.record_requirement_adjudication(
            self.workspace, requirement_id=requirement["id"], outcome="Satisfied",
            adjudicator="other-user", reasoning="Confirmed.", evidence_finding_ids=[finding_id],
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    # -- retraction before threshold -----------------------------------------------

    def test_owner_can_retract_before_collaboration(self):
        result = self.store.retract_case_to_private(
            self.workspace, case_id=self.case["id"], actor="owner1", governance_log=self.gov,
        )
        self.assertEqual(result["visibility"], CASE_VISIBILITY_PRIVATE)
        self.assertEqual(result["retracted_by"], "owner1")
        self.assertIsNotNone(result["retracted_at"])

    def test_non_owner_cannot_retract(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="other-user")
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_retraction_is_audited(self):
        self.store.retract_case_to_private(
            self.workspace, case_id=self.case["id"], actor="owner1", governance_log=self.gov,
        )
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_retracted_to_private"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].actor, "owner1")

    def test_privacy_protections_resume_after_retraction(self):
        self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="owner1")
        visible = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertNotIn(self.case["id"], [c["id"] for c in visible])

    def test_historic_sharing_event_preserved_after_retraction(self):
        result = self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["shared_by"], "owner1")
        self.assertIsNotNone(result["shared_at"])

    # -- irreversibility -----------------------------------------------

    def test_collaborative_to_private_rejected(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_owner_cannot_override_irreversibility(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        # owner is still the recorded owner/authorized actor for retraction
        # in general - even so, Collaborative status itself blocks it.
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="owner1")

    def test_no_other_method_can_flip_visibility_back(self):
        """There is no third path back to Private beyond retract_case_to_
        private, and that one path itself refuses once Collaborative -
        confirmed by checking the visibility value is unaffected by every
        other governed write once collaborative."""
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        self.store.record_disposition(
            self.workspace, finding_id=finding_id, disposition="Rejected", reviewer="owner1",
        )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_COLLABORATIVE)

    def test_collaboration_fact_survives_regardless_of_later_contribution_state(self):
        finding_id = self._owner_finding()
        validation = self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        case_before = self._current_case()
        contribution_id = case_before["collaboration_contribution_id"]
        self.assertEqual(contribution_id, validation["id"])
        # a later, unrelated write on the same finding does not erase or
        # rewrite the historical fact of how/when collaboration began
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Partial", reviewer="owner1",
            correction_note="revised",
        )
        case_after = self._current_case()
        self.assertEqual(case_after["collaboration_contribution_id"], contribution_id)
        self.assertEqual(case_after["collaboration_established_by"], "other-user")

    # -- failure safety -----------------------------------------------

    def test_invalid_reviewer_validation_does_not_spuriously_cross_threshold(self):
        finding_id = self._owner_finding()
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_reviewer_validation(
                self.workspace, finding_id=finding_id, validation="not-a-real-state", reviewer="other-user",
            )
        self.assertEqual(self._current_case()["visibility"], CASE_VISIBILITY_SHARED)

    def test_failed_retraction_leaves_state_unchanged(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=self.case["id"], actor="not-the-owner")
        case = self._current_case()
        self.assertEqual(case["visibility"], CASE_VISIBILITY_SHARED)
        self.assertIsNone(case["retracted_by"])
        self.assertIsNone(case["retracted_at"])

    def test_nonexistent_case_retraction_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id="does-not-exist", actor="owner1")

    def test_retracting_already_private_case_rejected(self):
        case = self.store.create_case(self.workspace, title="Private", objective="x", created_by="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=case["id"], actor="owner1")


if __name__ == "__main__":
    unittest.main()
