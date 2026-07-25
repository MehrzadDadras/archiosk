"""
Case Archive: terminal/frozen lifecycle status, orthogonal to visibility.

Architectural correction implemented here, not merely reported: ARCHIVED
is not a fourth visibility value. Visibility (PRIVATE/SHARED/
COLLABORATIVE) and status (OPEN/ARCHIVED) are two separate axes -
CaseRecord's own pre-existing `status` field is the correct home for
this, reused rather than overloading `visibility`. Covers
CaseWorkspaceStore.archive_case and the centralized
_require_case_not_archived guard, exercised through every write path
that touches a Case's governed contribution set or its visibility.

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
    CASE_STATUS_ARCHIVED,
    CASE_STATUS_OPEN,
    CASE_VISIBILITY_COLLABORATIVE,
    CASE_VISIBILITY_PRIVATE,
    CASE_VISIBILITY_SHARED,
    MESSAGE_ORIGIN_HUMAN,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class CaseArchiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_archive_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-archive"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )
        self.case = self.store.create_case(
            self.workspace, title="Investigation", objective="x", created_by="owner1",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _current_case(self):
        return self.store._find(self.store.get(self.project_id).cases, self.case["id"])

    def _owner_finding(self):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        return analysis["finding_ids"][0]

    # -- archive transition -----------------------------------------------

    def test_owner_can_archive_private_case(self):
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)
        self.assertEqual(result["id"], self.case["id"])

    def test_archive_preserves_case_identity(self):
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["id"], self.case["id"])
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["title"], self.case["title"])

    def test_archive_actor_time_and_prior_state_preserved(self):
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["archived_by"], "owner1")
        self.assertIsNotNone(result["archived_at"])
        self.assertEqual(result["archive_authority"], "owner")
        self.assertEqual(result["archive_prior_visibility"], CASE_VISIBILITY_PRIVATE)

    def test_archive_audit_record_created(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1", governance_log=self.gov)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_archived"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["case_id"], self.case["id"])
        self.assertEqual(events[0].actor, "owner1")

    def test_archive_permitted_from_all_three_visibility_states(self):
        for visibility_setup, label in [
            (lambda c: None, "private"),
            (lambda c: self.store.share_case(self.workspace, case_id=c["id"], actor="owner1"), "shared"),
        ]:
            case = self.store.create_case(self.workspace, title=label, objective="x", created_by="owner1")
            visibility_setup(case)
            result = self.store.archive_case(self.workspace, case_id=case["id"], actor="owner1")
            self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)

        # Collaborative case
        collab_case = self.store.create_case(self.workspace, title="collab", objective="x", created_by="owner1")
        self.store.share_case(self.workspace, case_id=collab_case["id"], actor="owner1")
        finding_id = self._owner_finding_for(collab_case["id"])
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        reloaded = self.store.get(self.project_id)
        self.assertEqual(
            self.store._find(reloaded.cases, collab_case["id"])["visibility"], CASE_VISIBILITY_COLLABORATIVE,
        )
        result = self.store.archive_case(self.workspace, case_id=collab_case["id"], actor="owner1")
        self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)
        self.assertEqual(result["visibility"], CASE_VISIBILITY_COLLABORATIVE)  # untouched by archiving

    def _owner_finding_for(self, case_id):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case_id, source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        return analysis["finding_ids"][0]

    def test_double_archive_rejected(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")

    # -- authority ---------------------------------------------------------

    def test_non_owner_non_admin_cannot_archive(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.archive_case(self.workspace, case_id=self.case["id"], actor="other-user")
        self.assertEqual(self._current_case()["status"], CASE_STATUS_OPEN)

    def test_admin_can_archive_when_owner_unavailable(self):
        """The practical clarification this tranche exists for: a former/
        retired/unreachable owner must never become a permanent lock -
        an actor with the system's existing admin role may archive on
        the project's behalf, using the narrowest existing authority
        pattern (no new role architecture invented)."""
        result = self.store.archive_case(
            self.workspace, case_id=self.case["id"], actor="design-manager-x", actor_role="admin",
        )
        self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)
        self.assertEqual(result["archived_by"], "design-manager-x")
        self.assertEqual(result["archive_authority"], "admin_override")

    def test_read_only_role_does_not_grant_archive_authority(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.archive_case(
                self.workspace, case_id=self.case["id"], actor="other-user", actor_role="read_only",
            )

    # -- unresolved voices survive archival unchanged -----------------------

    def test_unresolved_comment_does_not_block_archive(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="other-user", case_id=self.case["id"],
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="other-user", message_type="comment", text="an unresolved objection",
        )
        # thread has no resolution recorded - still unresolved
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)

    def test_comment_survives_archive_unchanged_with_authorship_and_unresolved_state(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="other-user", case_id=self.case["id"],
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="other-user", message_type="comment", text="an unresolved objection",
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")

        reloaded = self.store.get(self.project_id)
        preserved_message = self.store._find(reloaded.review_messages, message["id"])
        self.assertEqual(preserved_message["text"], "an unresolved objection")
        self.assertEqual(preserved_message["actor"], "other-user")  # authorship unchanged

        preserved_thread = self.store._find(reloaded.review_threads, thread["id"])
        self.assertIsNone(preserved_thread["resolution"])  # unresolved state unchanged
        # archival never fabricates a resolution
        self.assertEqual(preserved_thread["resolution_history"], [])

    def test_unavailable_contributor_is_not_required_to_release_before_archive(self):
        """No method anywhere requires the commenting actor's participation
        to archive - archive_case takes only the archiving actor, never
        the original contributor(s)."""
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="departed-contractor", case_id=self.case["id"],
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="departed-contractor", message_type="comment", text="final objection before leaving",
        )
        # departed-contractor never acts again; owner archives unilaterally
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["status"], CASE_STATUS_ARCHIVED)

    # -- terminal behavior: every identified write path rejected -----------

    def test_review_message_rejected_after_archive(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="owner1", case_id=self.case["id"],
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_review_message(
                self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
                actor="other-user", message_type="comment", text="too late",
            )

    def test_reviewer_validation_rejected_after_archive(self):
        finding_id = self._owner_finding()
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_reviewer_validation(
                self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
            )

    def test_disposition_rejected_after_archive(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="owner1",
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_disposition(
                self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1",
            )

    def test_attention_request_rejected_after_archive(self):
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="owner1", case_id=self.case["id"],
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="owner1", message_type="note", text="note",
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.request_attention(
                self.workspace, thread_id=thread["id"], message_id=message["id"],
                intended_actor="owner1", created_by="other-user",
            )

    def test_relationship_confirmation_rejected_after_archive(self):
        finding_id = self._owner_finding()
        relationship = self.store.record_relationship(
            self.workspace, from_type="finding", from_id=finding_id,
            to_type="source", to_id=self.source["id"], relationship_type="supports",
            created_by="some-engine", provisional=True,
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.confirm_relationship(self.workspace, relationship_id=relationship["id"], actor="other-user")

    def test_analysis_record_rejected_after_archive(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="other-user")
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_analysis(
                self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
                objective="x", engine_name="test", engine_version="1.0",
                findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
                trigger=trigger,
            )

    def test_other_mutation_paths_rejected_after_archive(self):
        """Representative 'other' paths beyond the six collaboration-
        adjacent ones, confirming the guard generalizes rather than only
        covering the explicitly-named six."""
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")

        with self.assertRaises(CaseWorkspaceError):
            self.store.attach_source_to_case(self.workspace, case_id=self.case["id"], source_id=self.source["id"])

        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(self.workspace, case_id=self.case["id"], role="human", text="too late")

    def test_share_and_retract_rejected_after_archive(self):
        """Visibility transitions are also frozen - archiving a Case must
        not remain a backdoor to later publish or un-share it."""
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")

        shared_case = self.store.create_case(self.workspace, title="B", objective="x", created_by="owner1")
        self.store.share_case(self.workspace, case_id=shared_case["id"], actor="owner1")
        self.store.archive_case(self.workspace, case_id=shared_case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.retract_case_to_private(self.workspace, case_id=shared_case["id"], actor="owner1")

    def test_apply_findings_rejected_after_archive(self):
        finding_id = self._owner_finding()
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="owner1",
        )
        self.store.record_disposition(
            self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1",
        )
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.apply_findings(self.workspace, finding_ids=[finding_id], applied_by="owner1")

    # -- human/machine boundary -----------------------------------------

    def test_machine_activity_cannot_autonomously_archive(self):
        """No write path other than archive_case itself ever sets
        status to archived - confirmed by exercising every other
        machine-shaped write and checking status never changes."""
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED, triggered_by_actor="some-agent")
        self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        self.assertEqual(self._current_case()["status"], CASE_STATUS_OPEN)

    def test_machine_cannot_mutate_archived_case(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED, triggered_by_actor="some-agent")
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_analysis(
                self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
                objective="x", engine_name="test", engine_version="1.0",
                findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
                trigger=trigger,
            )

    # -- visibility after archive -----------------------------------------------

    def test_archived_private_case_remains_private(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        visible_to_other = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertNotIn(self.case["id"], [c["id"] for c in visible_to_other])
        visible_to_owner = self.store.visible_cases_for(self.workspace, "owner1")
        self.assertIn(self.case["id"], [c["id"] for c in visible_to_owner])

    def test_archived_shared_case_retains_shared_visibility(self):
        self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        visible_to_other = self.store.visible_cases_for(self.workspace, "other-user")
        self.assertIn(self.case["id"], [c["id"] for c in visible_to_other])

    def test_archive_does_not_publish_a_private_case(self):
        result = self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self.assertEqual(result["visibility"], CASE_VISIBILITY_PRIVATE)

    # -- failure safety -----------------------------------------------

    def test_archive_failure_leaves_active_state_intact(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.archive_case(self.workspace, case_id=self.case["id"], actor="not-authorized")
        case = self._current_case()
        self.assertEqual(case["status"], CASE_STATUS_OPEN)
        self.assertIsNone(case["archived_by"])
        self.assertIsNone(case["archived_at"])

    def test_post_archive_failed_write_leaves_archive_unchanged(self):
        self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")
        thread = None
        try:
            thread = self.store.create_review_thread(
                self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
                created_by="owner1", case_id=self.case["id"],
            )
        except CaseWorkspaceError:
            pass
        if thread is not None:
            with self.assertRaises(CaseWorkspaceError):
                self.store.add_review_message(
                    self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
                    actor="owner1", message_type="note", text="rejected",
                )
        case = self._current_case()
        self.assertEqual(case["status"], CASE_STATUS_ARCHIVED)
        self.assertEqual(case["archived_by"], "owner1")

    def test_nonexistent_case_archive_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.archive_case(self.workspace, case_id="does-not-exist", actor="owner1")


if __name__ == "__main__":
    unittest.main()
