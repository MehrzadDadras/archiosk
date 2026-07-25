"""
Derive an active working Case from an archived one.

Archive is terminal for the OBJECT, not for the WORK: continued
reasoning proceeds through a brand new Case (new identity) carrying
explicit, structural, queryable lineage back to the archived source -
never a reopen/mutation of the archived Case, never a Supersession
(the archived Case remains standing, permanent historical truth), and
never a clone of the archived Case's own history (comments, Findings,
ReviewerValidations, Dispositions, analysis records all stay attached
to the archive exclusively).

Covers CaseWorkspaceStore.derive_case_from_archive and
derived_cases_of. Stdlib unittest only, matching the existing test
convention. Run via:

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
    RELATIONSHIP_TYPE_DERIVED_FROM,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class CaseDerivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_derivation_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-derivation"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md", kind="owner_project_requirements",
        )
        self.case = self.store.create_case(
            self.workspace, title="Investigation", objective="original objective", created_by="owner1",
        )
        self.store.attach_source_to_case(self.workspace, case_id=self.case["id"], source_id=self.source["id"])

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _archive(self):
        return self.store.archive_case(self.workspace, case_id=self.case["id"], actor="owner1")

    def _current_case(self, case_id):
        return self.store._find(self.store.get(self.project_id).cases, case_id)

    def _add_full_history_to_case(self):
        """Every kind of historical contribution this tranche must NOT clone."""
        thread = self.store.create_review_thread(
            self.workspace, title="x", anchor_type="case", anchor_id=self.case["id"],
            created_by="other-user", case_id=self.case["id"],
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
            actor="other-user", message_type="comment", text="an unresolved objection",
        )
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        finding_id = analysis["finding_ids"][0]
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="owner1",
        )
        self.store.record_disposition(
            self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="owner1",
        )
        return thread, finding_id

    # -- identity ------------------------------------------------------------

    def test_derived_case_gets_new_case_id(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertNotEqual(derived["id"], self.case["id"])

    def test_archived_case_id_unchanged(self):
        archived = self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        reloaded = self._current_case(self.case["id"])
        self.assertEqual(reloaded["id"], archived["id"])

    def test_derived_case_references_archive_through_lineage(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["derived_from_case_id"], self.case["id"])

        reloaded = self.store.get(self.project_id)
        matches = [
            r for r in reloaded.relationships
            if r["relationship_type"] == RELATIONSHIP_TYPE_DERIVED_FROM
            and r["from_id"] == derived["id"] and r["to_id"] == self.case["id"]
        ]
        self.assertEqual(len(matches), 1)

    # -- lifecycle -------------------------------------------------------------

    def test_archived_source_remains_archived(self):
        self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(self._current_case(self.case["id"])["status"], CASE_STATUS_ARCHIVED)

    def test_derived_case_begins_open(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["status"], CASE_STATUS_OPEN)

    def test_archived_source_remains_write_protected_after_derivation(self):
        self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_message(self.workspace, case_id=self.case["id"], role="human", text="too late")

    # -- working context ---------------------------------------------------

    def test_title_and_objective_transfer_by_default(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["title"], "Investigation")
        self.assertEqual(derived["objective"], "original objective")

    def test_title_and_objective_can_be_overridden(self):
        self._archive()
        derived = self.store.derive_case_from_archive(
            self.workspace, archived_case_id=self.case["id"], actor="owner1",
            title="Investigation - continued", objective="narrowed objective",
        )
        self.assertEqual(derived["title"], "Investigation - continued")
        self.assertEqual(derived["objective"], "narrowed objective")

    def test_source_references_transfer(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["source_ids"], [self.source["id"]])

    # -- historical contributions do not clone ---------------------------------

    def test_historical_contributions_do_not_clone_onto_derived_case(self):
        thread, finding_id = self._add_full_history_to_case()
        before_workspace = self.store.get(self.project_id)
        review_thread_count_before = len(before_workspace.review_threads)
        review_message_count_before = len(before_workspace.review_messages)
        finding_count_before = len(before_workspace.findings)
        reviewer_validation_count_before = len(before_workspace.reviewer_validations)
        disposition_count_before = len(before_workspace.dispositions)
        analysis_run_count_before = len(before_workspace.analyses)

        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")

        # The derived Case's own record carries none of the archived history.
        self.assertEqual(derived["conversation"], [])
        self.assertEqual(derived["analysis_ids"], [])
        self.assertEqual(derived["finding_ids"], [])
        self.assertEqual(derived["artifact_ids"], [])
        self.assertEqual(derived["activity_ids"], [])

        # Nothing was duplicated at the workspace level either - counts unchanged.
        after_workspace = self.store.get(self.project_id)
        self.assertEqual(len(after_workspace.review_threads), review_thread_count_before)
        self.assertEqual(len(after_workspace.review_messages), review_message_count_before)
        self.assertEqual(len(after_workspace.findings), finding_count_before)
        self.assertEqual(len(after_workspace.reviewer_validations), reviewer_validation_count_before)
        self.assertEqual(len(after_workspace.dispositions), disposition_count_before)
        self.assertEqual(len(after_workspace.analyses), analysis_run_count_before)

        # The archived Case's own history is exactly as it was - still
        # reachable only through it, not through the derived Case.
        archived = self._current_case(self.case["id"])
        self.assertIn(finding_id, archived["finding_ids"])
        self.assertNotIn(finding_id, derived["finding_ids"])

    def test_unresolved_comment_stays_on_archive_not_derived_case(self):
        thread, _ = self._add_full_history_to_case()
        self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")

        reloaded = self.store.get(self.project_id)
        preserved_thread = self.store._find(reloaded.review_threads, thread["id"])
        self.assertEqual(preserved_thread["case_id"], self.case["id"])
        self.assertIsNone(preserved_thread["resolution"])  # still unresolved, still on the archive

    # -- privacy -----------------------------------------------------------

    def test_derived_case_begins_private(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_deriving_from_shared_archive_does_not_publish_derived_case(self):
        self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_deriving_from_collaborative_archive_does_not_publish_derived_case(self):
        self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="owner1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
            objective="x", engine_name="test", engine_version="1.0",
            findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
            trigger=trigger,
        )
        finding_id = analysis["finding_ids"][0]
        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Correct", reviewer="other-user",
        )
        reloaded = self.store.get(self.project_id)
        self.assertEqual(
            self.store._find(reloaded.cases, self.case["id"])["visibility"], CASE_VISIBILITY_COLLABORATIVE,
        )
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["visibility"], CASE_VISIBILITY_PRIVATE)

    def test_archived_case_historical_visibility_unchanged_by_derivation(self):
        self.store.share_case(self.workspace, case_id=self.case["id"], actor="owner1")
        self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        archived = self._current_case(self.case["id"])
        self.assertEqual(archived["visibility"], CASE_VISIBILITY_SHARED)

    # -- lineage -----------------------------------------------------------

    def test_forward_lookup_derived_to_archive(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["derived_from_case_id"], self.case["id"])

    def test_reverse_lookup_archive_to_derived_cases(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        found = self.store.derived_cases_of(self.workspace, self.case["id"])
        self.assertEqual([c["id"] for c in found], [derived["id"]])

    def test_reverse_lookup_supports_multiple_derivations(self):
        self._archive()
        derived_1 = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        derived_2 = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        found_ids = {c["id"] for c in self.store.derived_cases_of(self.workspace, self.case["id"])}
        self.assertEqual(found_ids, {derived_1["id"], derived_2["id"]})

    def test_derivation_is_not_represented_as_supersession(self):
        self._archive()
        self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        reloaded = self.store.get(self.project_id)
        case_supersessions = [
            s for s in reloaded.supersessions
            if s["predecessor_id"] == self.case["id"] or s["successor_id"] == self.case["id"]
        ]
        self.assertEqual(case_supersessions, [])

    # -- authority -----------------------------------------------------------

    def test_owner_can_derive(self):
        self._archive()
        derived = self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(derived["status"], CASE_STATUS_OPEN)

    def test_admin_can_derive_when_owner_unavailable(self):
        self._archive()
        derived = self.store.derive_case_from_archive(
            self.workspace, archived_case_id=self.case["id"], actor="design-manager-x", actor_role="admin",
        )
        self.assertEqual(derived["created_by"], "design-manager-x")

    def test_unauthorized_participant_cannot_derive(self):
        self._archive()
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="other-user")

    def test_read_only_role_does_not_grant_derive_authority(self):
        self._archive()
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(
                self.workspace, archived_case_id=self.case["id"], actor="other-user", actor_role="read_only",
            )

    def test_machine_path_cannot_silently_derive(self):
        """No write path other than derive_case_from_archive itself ever
        creates a Case row with derived_from_case_id set - confirmed by
        exercising a machine-shaped write and checking the Case count/
        lineage state never changes."""
        self._archive()
        case_count_before = len(self.store.get(self.project_id).cases)
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED, triggered_by_actor="some-agent")
        with self.assertRaises(CaseWorkspaceError):
            # record_analysis against the now-archived case is itself rejected -
            # confirming there is no back-door machine write path at all, let
            # alone one that derives a new Case.
            self.store.record_analysis(
                self.workspace, case_id=self.case["id"], source_ids=[self.source["id"]],
                objective="x", engine_name="test", engine_version="1.0",
                findings=[{"statement": "x", "machine_confidence": 0.5, "source_id": self.source["id"]}],
                trigger=trigger,
            )
        self.assertEqual(len(self.store.get(self.project_id).cases), case_count_before)

    # -- failure safety ---------------------------------------------------------

    def test_unauthorized_derivation_creates_no_partial_state(self):
        self._archive()
        case_count_before = len(self.store.get(self.project_id).cases)
        relationship_count_before = len(self.store.get(self.project_id).relationships)
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="other-user")
        workspace_after = self.store.get(self.project_id)
        self.assertEqual(len(workspace_after.cases), case_count_before)
        self.assertEqual(len(workspace_after.relationships), relationship_count_before)

    def test_archived_source_untouched_on_failed_derivation(self):
        self._archive()
        before = dict(self._current_case(self.case["id"]))
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="other-user")
        after = self._current_case(self.case["id"])
        self.assertEqual(after, before)

    def test_deriving_from_nonexistent_case_raises(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(self.workspace, archived_case_id="does-not-exist", actor="owner1")

    def test_deriving_from_non_archived_case_raises_and_creates_no_state(self):
        case_count_before = len(self.store.get(self.project_id).cases)
        with self.assertRaises(CaseWorkspaceError):
            self.store.derive_case_from_archive(self.workspace, archived_case_id=self.case["id"], actor="owner1")
        self.assertEqual(len(self.store.get(self.project_id).cases), case_count_before)
        self.assertEqual(self._current_case(self.case["id"])["status"], CASE_STATUS_OPEN)

    def test_audit_record_created(self):
        self._archive()
        derived = self.store.derive_case_from_archive(
            self.workspace, archived_case_id=self.case["id"], actor="owner1", governance_log=self.gov,
        )
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "case_derived_from_archive"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["derived_case_id"], derived["id"])
        self.assertEqual(events[0].payload["archived_case_id"], self.case["id"])


if __name__ == "__main__":
    unittest.main()
