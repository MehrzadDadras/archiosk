"""
Selective Adopt / Carry-Forward: explicit human-controlled carry-forward
of specific historical items from an archived Case into its own derived
active successor.

"History remains where it happened. What still matters may be
deliberately carried forward." Archive preserves the past, Derive
creates the future, Adopt decides what deliberately crosses the bridge
- nothing crosses automatically. Covers
CaseWorkspaceStore.adopt_finding_into_case,
adopt_review_message_into_case, and carried_forward_adoptions_for_case.

Only two object types are supported this tranche - Finding and
ReviewMessage - deliberately narrow; Disposition, ReviewerValidation,
RequirementAdjudication, AnalysisRun, and Attention are NOT adoptable
(see services/case_workspace.py's adopt_* docstrings and the tranche
report for why).

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
    CARRIED_FORWARD_OBJECT_TYPE_FINDING,
    CARRIED_FORWARD_OBJECT_TYPE_REVIEW_MESSAGE,
    CASE_VISIBILITY_PRIVATE,
    FINDING_STATUS_PROVISIONAL,
    MESSAGE_ORIGIN_HUMAN,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class CaseAdoptionTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_adoption_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-adoption"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )
        self.case = self.store.create_case(
            self.workspace, title="Investigation", objective="original objective", created_by="owner1",
        )

        # A Finding, authored/validated by a specific person at a specific time.
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "beam undersized per drawing S-101", "machine_confidence": 0.7, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.source_finding_id = analysis["finding_ids"][0]
        self.store.record_reviewer_validation(
            self.workspace, finding_id=self.source_finding_id, validation="Correct", reviewer="departed-reviewer",
        )

        # An unresolved comment, authored by someone who may no longer be reachable.
        thread = self.store.create_review_thread(
            self.workspace, title="Structural concern", anchor_type="case", anchor_id=self.case["id"],
            created_by="departed-contractor", case_id=self.case["id"],
        )
        self.source_thread_id = thread["id"]
        self.source_message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="departed-contractor", message_type="comment", text="I never got a straight answer on this beam.",
        )

        self.archived_case = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.derived_case = self.store.derive_case_from_archive(
            self.workspace, archived_case_id=self.case["id"], actor="owner1",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _current_case(self, case_id):
        return self.store._find(self.store.get(self.project_id).cases, case_id)

    def _current_finding(self, finding_id):
        return self.store._find(self.store.get(self.project_id).findings, finding_id)

    def _current_message(self, message_id):
        return self.store._find(self.store.get(self.project_id).review_messages, message_id)

    # -- selection -----------------------------------------------------------

    def test_nothing_carries_forward_automatically_upon_derivation(self):
        self.assertEqual(self.derived_case["finding_ids"], [])
        self.assertEqual(
            self.store.carried_forward_adoptions_for_case(self.workspace, self.derived_case["id"]), [],
        )

    def test_authorized_human_may_adopt_a_finding(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertEqual(adopted["case_id"], self.derived_case["id"])

    def test_authorized_human_may_adopt_a_review_message(self):
        adopted = self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertEqual(adopted["actor"], "owner1")

    def test_unsupported_object_types_have_no_adoption_path(self):
        """Deliberately narrow scope: Disposition/ReviewerValidation/
        RequirementAdjudication/AnalysisRun/Attention have no adopt_*
        method at all - the object scope is closed by omission, not by
        a runtime type-check that could silently expand later."""
        adoption_methods = {name for name in dir(self.store) if name.startswith("adopt_")}
        self.assertEqual(
            adoption_methods, {"adopt_finding_into_case", "adopt_review_message_into_case"},
        )

    # -- historical preservation ---------------------------------------------

    def test_source_finding_unchanged_after_adoption(self):
        before = dict(self._current_finding(self.source_finding_id))
        self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        after = self._current_finding(self.source_finding_id)
        self.assertEqual(after, before)

    def test_source_message_unchanged_after_adoption(self):
        before = dict(self._current_message(self.source_message["id"]))
        self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        after = self._current_message(self.source_message["id"])
        self.assertEqual(after, before)

    def test_archived_case_unchanged_after_adoption(self):
        before = dict(self._current_case(self.case["id"]))
        self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        after = self._current_case(self.case["id"])
        self.assertEqual(after, before)

    def test_original_author_and_time_unchanged(self):
        self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        original = self._current_message(self.source_message["id"])
        self.assertEqual(original["actor"], "departed-contractor")
        self.assertEqual(original["created_at"], self.source_message["created_at"])

    # -- active successor ---------------------------------------------------

    def test_adopted_finding_gets_new_id_in_target_case(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertNotEqual(adopted["id"], self.source_finding_id)
        self.assertEqual(adopted["case_id"], self.derived_case["id"])
        self.assertIn(adopted["id"], self._current_case(self.derived_case["id"])["finding_ids"])

    def test_adopted_message_gets_new_id_in_new_thread_on_target_case(self):
        adopted = self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertNotEqual(adopted["id"], self.source_message["id"])
        reloaded = self.store.get(self.project_id)
        new_thread = self.store._find(reloaded.review_threads, adopted["thread_id"])
        self.assertEqual(new_thread["case_id"], self.derived_case["id"])

    def test_adopting_actor_and_time_recorded_on_finding_adoption(self):
        self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        adoptions = self.store.carried_forward_adoptions_for_case(self.workspace, self.derived_case["id"])
        self.assertEqual(len(adoptions), 1)
        self.assertEqual(adoptions[0]["adopted_by"], "owner1")
        self.assertIsNotNone(adoptions[0]["adopted_at"])

    def test_lineage_points_to_historical_item_in_source_case(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        adoptions = self.store.carried_forward_adoptions_for_case(self.workspace, self.derived_case["id"])
        self.assertEqual(adoptions[0]["source_case_id"], self.case["id"])
        self.assertEqual(adoptions[0]["source_object_id"], self.source_finding_id)
        self.assertEqual(adoptions[0]["successor_object_id"], adopted["id"])
        self.assertEqual(adoptions[0]["object_type"], CARRIED_FORWARD_OBJECT_TYPE_FINDING)

    def test_message_lineage_recorded(self):
        adopted = self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        adoptions = self.store.carried_forward_adoptions_for_case(self.workspace, self.derived_case["id"])
        self.assertEqual(adoptions[0]["object_type"], CARRIED_FORWARD_OBJECT_TYPE_REVIEW_MESSAGE)
        self.assertEqual(adoptions[0]["source_object_id"], self.source_message["id"])
        self.assertEqual(adoptions[0]["successor_object_id"], adopted["id"])

    # -- comments ---------------------------------------------------------

    def test_unresolved_predecessor_comment_remains_on_archive(self):
        self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        reloaded = self.store.get(self.project_id)
        original_thread = self.store._find(reloaded.review_threads, self.source_thread_id)
        self.assertEqual(original_thread["case_id"], self.case["id"])
        self.assertIsNone(original_thread["resolution"])

    def test_carry_forward_does_not_falsely_attribute_authorship(self):
        adopted = self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertEqual(adopted["actor"], "owner1")
        self.assertNotEqual(adopted["actor"], "departed-contractor")
        self.assertIn("departed-contractor", adopted["text"])  # original voice still visible, just not misattributed

    def test_former_commenter_not_required_to_participate(self):
        # departed-contractor never acts again; owner1 alone carries the concern forward.
        adopted = self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1", note="still relevant, revisit with new grading plan",
        )
        self.assertIn("still relevant", adopted["text"])

    # -- findings ------------------------------------------------------------

    def test_adopted_finding_does_not_become_authoritative(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        self.assertEqual(adopted["claim_status"], FINDING_STATUS_PROVISIONAL)
        # No ReviewerValidation/Disposition was fabricated for the new Finding.
        reloaded = self.store.get(self.project_id)
        validations = [v for v in reloaded.reviewer_validations if v["finding_id"] == adopted["id"]]
        dispositions = [d for d in reloaded.dispositions if d["finding_id"] == adopted["id"]]
        self.assertEqual(validations, [])
        self.assertEqual(dispositions, [])

    def test_renewed_validation_still_required_before_disposition(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_disposition(
                self.workspace, finding_id=adopted["id"], disposition="Confirmed", reviewer="owner1",
            )
        # Recording a fresh validation against the CURRENT evidence works normally.
        self.store.record_reviewer_validation(
            self.workspace, finding_id=adopted["id"], validation="Correct", reviewer="owner1",
        )
        self.store.record_disposition(
            self.workspace, finding_id=adopted["id"], disposition="Confirmed", reviewer="owner1",
        )

    # -- privacy ---------------------------------------------------------------

    def test_target_case_remains_private_after_adoption(self):
        self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        reloaded = self._current_case(self.derived_case["id"])
        self.assertEqual(reloaded["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_adoption_does_not_alter_archived_case_visibility(self):
        before_visibility = self._current_case(self.case["id"])["visibility"]
        self.store.adopt_review_message_into_case(
            self.workspace, source_message_id=self.source_message["id"],
            target_case_id=self.derived_case["id"], actor="owner1",
        )
        after_visibility = self._current_case(self.case["id"])["visibility"]
        self.assertEqual(before_visibility, after_visibility)

    # -- authority -----------------------------------------------------------

    def test_unauthorized_participant_cannot_adopt(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=self.source_finding_id,
                target_case_id=self.derived_case["id"], actor="random-other-user",
            )

    def test_admin_can_adopt_on_behalf_of_target_owner(self):
        adopted = self.store.adopt_finding_into_case(
            self.workspace, source_finding_id=self.source_finding_id,
            target_case_id=self.derived_case["id"], actor="design-manager-x", actor_role="admin",
        )
        self.assertEqual(adopted["case_id"], self.derived_case["id"])

    def test_read_only_role_does_not_grant_adopt_authority(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=self.source_finding_id,
                target_case_id=self.derived_case["id"], actor="random-other-user", actor_role="read_only",
            )

    def test_cannot_adopt_into_an_unrelated_case(self):
        unrelated_case = self.store.create_case(
            self.workspace, title="Unrelated", objective="x", created_by="owner1",
        )
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=self.source_finding_id,
                target_case_id=unrelated_case["id"], actor="owner1",
            )

    def test_machine_path_cannot_silently_adopt(self):
        """No write path other than adopt_finding_into_case/
        adopt_review_message_into_case itself ever creates a
        CarriedForwardAdoption row - confirmed by exercising a
        machine-shaped write against the target Case and checking
        nothing was carried forward as a side effect."""
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED, triggered_by_actor="some-agent")
        self.store.record_analysis(
            self.workspace, case_id=self.derived_case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "unrelated new finding", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.assertEqual(
            self.store.carried_forward_adoptions_for_case(self.workspace, self.derived_case["id"]), [],
        )

    # -- failure safety ---------------------------------------------------------

    def test_failed_finding_adoption_leaves_no_partial_state(self):
        finding_count_before = len(self.store.get(self.project_id).findings)
        analysis_count_before = len(self.store.get(self.project_id).analyses)
        adoption_count_before = len(self.store.get(self.project_id).carried_forward_adoptions)
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=self.source_finding_id,
                target_case_id=self.derived_case["id"], actor="random-other-user",
            )
        after = self.store.get(self.project_id)
        self.assertEqual(len(after.findings), finding_count_before)
        self.assertEqual(len(after.analyses), analysis_count_before)
        self.assertEqual(len(after.carried_forward_adoptions), adoption_count_before)

    def test_failed_message_adoption_leaves_no_partial_state(self):
        thread_count_before = len(self.store.get(self.project_id).review_threads)
        message_count_before = len(self.store.get(self.project_id).review_messages)
        adoption_count_before = len(self.store.get(self.project_id).carried_forward_adoptions)
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_review_message_into_case(
                self.workspace, source_message_id=self.source_message["id"],
                target_case_id=self.derived_case["id"], actor="random-other-user",
            )
        after = self.store.get(self.project_id)
        self.assertEqual(len(after.review_threads), thread_count_before)
        self.assertEqual(len(after.review_messages), message_count_before)
        self.assertEqual(len(after.carried_forward_adoptions), adoption_count_before)

    def test_adopting_from_nonarchived_case_rejected(self):
        active_case = self.store.create_case(self.workspace, title="Active", objective="x", created_by="owner1")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=active_case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=analysis["finding_ids"][0],
                target_case_id=self.derived_case["id"], actor="owner1",
            )

    def test_adopting_into_archived_target_rejected(self):
        second_derived = self.store.derive_case_from_archive(
            self.workspace, archived_case_id=self.case["id"], actor="owner1",
        )
        self.store.archive_case(self.workspace, case_id=second_derived["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id=self.source_finding_id,
                target_case_id=second_derived["id"], actor="owner1",
            )

    def test_adopting_nonexistent_finding_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_finding_into_case(
                self.workspace, source_finding_id="does-not-exist",
                target_case_id=self.derived_case["id"], actor="owner1",
            )

    def test_adopting_nonexistent_message_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.adopt_review_message_into_case(
                self.workspace, source_message_id="does-not-exist",
                target_case_id=self.derived_case["id"], actor="owner1",
            )


if __name__ == "__main__":
    unittest.main()
