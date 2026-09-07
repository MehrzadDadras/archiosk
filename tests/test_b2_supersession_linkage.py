"""
B2 - requirement-level supersession linkage, proven end to end from B1.

Every transition below starts from a real B1 assessment that a human accepted,
because that authority transition IS B2's contract. The refusals matter as much
as the successes: a PROPOSED assessment, an ambiguous one, and a clarification
must each be incapable of revising a governed requirement, and a second accepted
change on one predecessor must stop rather than pick a winner.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services import change_application as capp
from services import change_arrival as ca
from services.case_workspace import (
    CHANGE_ARRIVAL_STATE_ACCEPTED,
    CHANGE_ARRIVAL_STATE_REJECTED,
    CHANGE_TYPE_AMENDS,
    CHANGE_TYPE_CLARIFIES,
    CHANGE_TYPE_REVIEW,
    CHANGE_TYPE_SUPERSEDES,
    CaseWorkspaceStore,
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    DOCUMENT_AUTHORITY_INFORMATIONAL,
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_DEPENDS_ON,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_STATUS_SUPERSEDED,
    SOURCE_KIND_PROJECT_DOCUMENT,
)
from services.governance import GovernanceLog


class _B2Base(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_b2_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-b2")

        self.spec = self._source("spec.txt", DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.requirement = self._requirement("R-1", "Dampers shall close on alarm.")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _source(self, name, authority=None):
        path = self.tmp_dir / name
        path.write_text("content of %s" % name, encoding="utf-8")
        return self.store.add_source(
            self.workspace, name=name, file_path=str(path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, document_authority=authority,
            actor="tester", governance_log=self.gov)

    def _requirement(self, ident, text):
        return self.store.register_requirement(
            self.workspace, source_id=self.spec["id"],
            original_requirement_identifier=ident, text_reference=text,
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov)

    def _accepted(self, change_type=CHANGE_TYPE_AMENDS, source=None, target=None):
        """A real B1 assessment, human-accepted - B2's only legitimate input."""
        assessment = ca.propose_change(
            self.store, self.workspace,
            incoming_source_id=(source or self.addendum)["id"],
            target_requirement_id=(target or self.requirement)["id"],
            change_type=change_type, evidence="Addendum 3 item 4.", actor="go",
            governance_log=self.gov)
        self.store.review_change_arrival_assessment(
            self.workspace, assessment["id"], actor="pm",
            outcome=CHANGE_ARRIVAL_STATE_ACCEPTED, governance_log=self.gov)
        return next(a for a in self.workspace.change_arrival_assessments
                    if a["id"] == assessment["id"])


class SupersedesTests(_B2Base):
    """A. Accepted SUPERSEDES creates predecessor -> successor lineage."""

    def test_it_creates_a_successor_and_a_supersession(self):
        a = self._accepted(CHANGE_TYPE_SUPERSEDES)
        result = capp.apply_accepted_change(
            self.store, self.workspace, a["id"], actor="pm", governance_log=self.gov)
        self.assertTrue(result["applied"])
        self.assertEqual(result["predecessor_id"], self.requirement["id"])
        self.assertNotEqual(result["successor_id"], self.requirement["id"])
        self.assertTrue(result["supersession_id"])

    def test_the_predecessor_is_marked_superseded_not_deleted(self):
        a = self._accepted(CHANGE_TYPE_SUPERSEDES)
        capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        old = next(r for r in refreshed.requirements if r["id"] == self.requirement["id"])
        self.assertEqual(old["status"], REQUIREMENT_STATUS_SUPERSEDED)
        self.assertEqual(old["text_reference"], "Dampers shall close on alarm.")

    def test_the_supersession_records_the_authority_it_rested_on(self):
        a = self._accepted(CHANGE_TYPE_SUPERSEDES)
        result = capp.apply_accepted_change(
            self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        s = next(x for x in refreshed.supersessions if x["id"] == result["supersession_id"])
        self.assertEqual(s["authority_class"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertIn(a["id"], s["reason"])
        self.assertIn(CHANGE_TYPE_SUPERSEDES, s["reason"])


class AmendsTests(_B2Base):
    """B. Accepted AMENDS preserves prior state and creates a governed successor."""

    def test_an_amendment_creates_a_successor_rather_than_editing_in_place(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(
            self.store, self.workspace, a["id"], actor="pm",
            text_reference="Dampers shall close on alarm within 10 seconds.")
        refreshed = self.store.get(self.workspace.project_id)
        old = next(r for r in refreshed.requirements if r["id"] == self.requirement["id"])
        new = next(r for r in refreshed.requirements if r["id"] == result["successor_id"])
        self.assertEqual(old["text_reference"], "Dampers shall close on alarm.")
        self.assertEqual(new["text_reference"],
                         "Dampers shall close on alarm within 10 seconds.")

    def test_unchanged_fields_carry_forward(self):
        """An amendment is a revision, not a retyped requirement."""
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(
            self.store, self.workspace, a["id"], actor="pm",
            text_reference="Amended text.")
        refreshed = self.store.get(self.workspace.project_id)
        new = next(r for r in refreshed.requirements if r["id"] == result["successor_id"])
        self.assertEqual(new["original_requirement_identifier"],
                         self.requirement["original_requirement_identifier"])

    def test_amends_and_supersedes_both_preserve_genealogy(self):
        """They differ in provenance, not in mechanism - and the record says
        which one it was."""
        for change_type in (CHANGE_TYPE_AMENDS, CHANGE_TYPE_SUPERSEDES):
            with self.subTest(change_type=change_type):
                target = self._requirement("R-%s" % change_type, "Target for %s" % change_type)
                a = self._accepted(change_type, target=target)
                result = capp.apply_accepted_change(
                    self.store, self.workspace, a["id"], actor="pm")
                refreshed = self.store.get(self.workspace.project_id)
                s = next(x for x in refreshed.supersessions
                         if x["id"] == result["supersession_id"])
                self.assertIn(change_type, s["reason"])
                self.assertTrue(any(r["id"] == target["id"] for r in refreshed.requirements))


class AuthorityGateTests(_B2Base):
    """C, D. Only an accepted, authority-moving change may revise anything."""

    def test_a_proposed_assessment_cannot_trigger_b2(self):
        assessment = ca.propose_change(
            self.store, self.workspace, self.addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(
                self.store, self.workspace, assessment["id"], actor="pm")

    def test_a_rejected_assessment_cannot_trigger_b2(self):
        assessment = ca.propose_change(
            self.store, self.workspace, self.addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        self.store.review_change_arrival_assessment(
            self.workspace, assessment["id"], actor="pm",
            outcome=CHANGE_ARRIVAL_STATE_REJECTED)
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(
                self.store, self.workspace, assessment["id"], actor="pm")

    def test_an_accepted_review_cannot_trigger_b2(self):
        a = self._accepted(CHANGE_TYPE_REVIEW)
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")

    def test_an_accepted_clarification_cannot_trigger_b2(self):
        note = self._source("note.txt", DOCUMENT_AUTHORITY_INFORMATIONAL)
        a = self._accepted(CHANGE_TYPE_CLARIFIES, source=note)
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")

    def test_a_refused_application_writes_nothing(self):
        a = self._accepted(CHANGE_TYPE_REVIEW)
        before = len(self.workspace.supersessions), len(self.workspace.requirements)
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        self.assertEqual((len(refreshed.supersessions), len(refreshed.requirements)), before)


class HistoricalReconstructionTests(_B2Base):
    """E, F. History survives, and current state is derived rather than stored."""

    def test_the_old_requirement_remains_fully_reconstructable(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(
            self.store, self.workspace, a["id"], actor="pm",
            text_reference="Replaced text.")
        lineage = capp.lineage_of(
            self.store, self.store.get(self.workspace.project_id), self.requirement["id"])
        self.assertEqual(lineage["this"]["text_reference"], "Dampers shall close on alarm.")
        self.assertFalse(lineage["is_current"])
        self.assertEqual(lineage["replaced_by"], result["successor_id"])
        self.assertEqual(lineage["chain"][0]["actor"], "pm")
        self.assertEqual(lineage["chain"][0]["authority_class"],
                         DOCUMENT_AUTHORITY_CONTRACTUAL)

    def test_current_resolves_from_the_predecessors_id(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        lineage = capp.lineage_of(self.store, refreshed, self.requirement["id"])
        self.assertEqual(lineage["current"]["id"], result["successor_id"])

    def test_a_two_step_chain_is_walkable_end_to_end(self):
        # Created BEFORE the first transition: adding a Source to the stale
        # in-memory workspace after reloading would both hide it from the
        # reloaded copy and risk saving over the transition just applied.
        second_addendum = self._source("addendum-4.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a1 = self._accepted(CHANGE_TYPE_AMENDS)
        first = capp.apply_accepted_change(self.store, self.workspace, a1["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        a2 = ca.propose_change(
            self.store, refreshed, second_addendum["id"], first["successor_id"],
            CHANGE_TYPE_AMENDS, evidence="Addendum 4.", actor="go")
        self.store.review_change_arrival_assessment(
            refreshed, a2["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        second = capp.apply_accepted_change(self.store, refreshed, a2["id"], actor="pm")

        final = self.store.get(self.workspace.project_id)
        lineage = capp.lineage_of(self.store, final, self.requirement["id"])
        self.assertEqual(len(lineage["chain"]), 2)
        self.assertEqual(lineage["current"]["id"], second["successor_id"])

    def test_current_is_not_inferred_from_recency(self):
        """A newer requirement with no supersession link does not become
        current merely by existing later."""
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        self._requirement("R-99", "A newer unrelated requirement.")
        refreshed = self.store.get(self.workspace.project_id)
        lineage = capp.lineage_of(self.store, refreshed, self.requirement["id"])
        self.assertEqual(lineage["current"]["id"], result["successor_id"])


class IdempotencyTests(_B2Base):
    """G. Applying twice must not split the world."""

    def test_reapplying_returns_the_existing_transition(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        first = capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        again = capp.apply_accepted_change(self.store, refreshed, a["id"], actor="pm")
        self.assertTrue(again["already_applied"])
        self.assertFalse(again["applied"])
        self.assertEqual(again["successor_id"], first["successor_id"])
        self.assertEqual(again["supersession_id"], first["supersession_id"])

    def test_reapplying_creates_no_duplicate_records(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        after_first = self.store.get(self.workspace.project_id)
        counts = (len(after_first.requirements), len(after_first.supersessions))
        capp.apply_accepted_change(self.store, after_first, a["id"], actor="pm")
        after_second = self.store.get(self.workspace.project_id)
        self.assertEqual(
            (len(after_second.requirements), len(after_second.supersessions)), counts)

    def test_the_assessment_records_what_it_produced(self):
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        stamped = next(x for x in refreshed.change_arrival_assessments if x["id"] == a["id"])
        self.assertEqual(stamped["applied_supersession_id"], result["supersession_id"])
        self.assertEqual(stamped["applied_successor_id"], result["successor_id"])
        self.assertEqual(stamped["applied_by"], "pm")


class ConflictTests(_B2Base):
    """I. Two accepted changes on one predecessor must not resolve by recency."""

    def _two_competing_accepted(self):
        a1 = self._accepted(CHANGE_TYPE_AMENDS)
        other = self._source("addendum-4.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a2 = ca.propose_change(
            self.store, self.workspace, other["id"], self.requirement["id"],
            CHANGE_TYPE_SUPERSEDES, evidence="Addendum 4 replaces it.", actor="go")
        self.store.review_change_arrival_assessment(
            self.workspace, a2["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        return a1, a2

    def test_a_second_accepted_change_on_one_predecessor_is_refused(self):
        a1, a2 = self._two_competing_accepted()
        capp.apply_accepted_change(self.store, self.workspace, a1["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        with self.assertRaises(capp.ChangeApplicationConflict):
            capp.apply_accepted_change(self.store, refreshed, a2["id"], actor="pm")

    def test_the_conflict_does_not_split_the_current_state_head(self):
        a1, a2 = self._two_competing_accepted()
        capp.apply_accepted_change(self.store, self.workspace, a1["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        try:
            capp.apply_accepted_change(self.store, refreshed, a2["id"], actor="pm")
        except capp.ChangeApplicationConflict:
            pass
        final = self.store.get(self.workspace.project_id)
        heads = [s for s in final.supersessions
                 if s["predecessor_id"] == self.requirement["id"]]
        self.assertEqual(len(heads), 1, "the predecessor gained a second successor")

    def test_the_blocked_change_is_surfaced_not_silently_skipped(self):
        a1, a2 = self._two_competing_accepted()
        capp.apply_accepted_change(self.store, self.workspace, a1["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        blocked = capp.pending_conflicts(self.store, refreshed)
        self.assertEqual([b["assessment_id"] for b in blocked], [a2["id"]])
        self.assertIn("human", blocked[0]["needs"])

    def test_an_older_addendum_applied_later_does_not_win_by_arriving_last(self):
        """Order of processing must not decide authority."""
        a1, a2 = self._two_competing_accepted()
        capp.apply_accepted_change(self.store, self.workspace, a2["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        with self.assertRaises(capp.ChangeApplicationConflict):
            capp.apply_accepted_change(self.store, refreshed, a1["id"], actor="pm")


class A2DependencyBehaviourTests(_B2Base):
    """H. Dependencies must not migrate to the successor."""

    def _dependent_on_requirement(self):
        dependent = self._requirement("R-DEP", "Depends on R-1.")
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        return dependent

    def test_no_successor_dependency_edge_is_manufactured(self):
        dependent = self._dependent_on_requirement()
        a = self._accepted(CHANGE_TYPE_AMENDS)
        result = capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        migrated = [r for r in refreshed.relationships
                    if r["to_id"] == result["successor_id"]]
        self.assertEqual(migrated, [],
                         "B2 invented a dependency edge on the successor")
        self.assertTrue(any(r["id"] == dependent["id"] for r in refreshed.requirements))

    def test_the_predecessors_dependency_edge_is_preserved(self):
        self._dependent_on_requirement()
        a = self._accepted(CHANGE_TYPE_AMENDS)
        capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed = self.store.get(self.workspace.project_id)
        kept = [r for r in refreshed.relationships if r["to_id"] == self.requirement["id"]]
        self.assertEqual(len(kept), 1)

    def test_the_brief_shows_dependents_without_acting_on_them(self):
        dependent = self._dependent_on_requirement()
        a = self._accepted(CHANGE_TYPE_AMENDS)
        brief = capp.transition_brief(self.store, self.workspace, a["id"])
        self.assertTrue(brief["applicable"])
        self.assertEqual([e["other"]["id"] for e in brief["affected"]["dependents"]],
                         [dependent["id"]])
        refreshed = self.store.get(self.workspace.project_id)
        self.assertEqual(len(refreshed.supersessions), 0,
                         "reading a brief performed a transition")


class ProjectIsolationTests(_B2Base):
    """J. Cross-project isolation."""

    def test_another_projects_assessment_is_not_visible_or_applicable(self):
        other = self.store.get_or_create("test-project-b2-other")
        a = self._accepted(CHANGE_TYPE_AMENDS)
        with self.assertRaises(capp.ChangeApplicationError):
            capp.apply_accepted_change(self.store, other, a["id"], actor="pm")
        self.assertEqual(capp.pending_conflicts(self.store, other), [])

    def test_a_transition_in_one_project_leaves_the_other_untouched(self):
        other = self.store.get_or_create("test-project-b2-other2")
        before = len(other.supersessions)
        a = self._accepted(CHANGE_TYPE_AMENDS)
        capp.apply_accepted_change(self.store, self.workspace, a["id"], actor="pm")
        refreshed_other = self.store.get("test-project-b2-other2")
        self.assertEqual(len(refreshed_other.supersessions), before)
        self.assertEqual(refreshed_other.requirements, [])


if __name__ == "__main__":
    unittest.main()
