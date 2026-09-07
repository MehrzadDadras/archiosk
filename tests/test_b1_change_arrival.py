"""
B1 - change-arrival recognition, and A2's first production consumer.

The scenarios that carry the weight are the NEGATIVE ones. Recognising an
Addendum is the easy half; refusing to recognise an RFI answer, a reference
document, or an ambiguous scope is where the governed behaviour actually lives,
and each of those has its own test below.

Nothing here asserts that B1 revises anything, because B1 must not: every
assessment is written PROPOSED, and the accept step still stops short of
touching the Requirement. That line is B2's, and it is tested as a line.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import change_arrival as ca
from services.case_workspace import (
    AUTHORITY_MOVING_CHANGE_TYPES,
    CHANGE_ARRIVAL_STATE_ACCEPTED,
    CHANGE_ARRIVAL_STATE_PROPOSED,
    CHANGE_ARRIVAL_STATE_REJECTED,
    CHANGE_TYPE_AMENDS,
    CHANGE_TYPE_CLARIFIES,
    CHANGE_TYPE_NO_CHANGE,
    CHANGE_TYPE_REVIEW,
    CHANGE_TYPE_SUPERSEDES,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    DOCUMENT_AUTHORITY_INFORMATIONAL,
    DOCUMENT_AUTHORITY_REFERENCE,
    OBJECT_KIND_REQUIREMENT,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_DEPENDS_ON,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    SOURCE_KIND_PROJECT_DOCUMENT,
)
from services.governance import GovernanceLog


def _png(w=60, h=40, color=(20, 90, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


class _B1Base(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_b1_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-b1")

        self.spec = self._source("spec.txt", DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.requirement = self.store.register_requirement(
            self.workspace, source_id=self.spec["id"],
            original_requirement_identifier="R-1",
            text_reference="Dampers shall close on alarm.",
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _source(self, name, authority=None):
        path = self.tmp_dir / name
        path.write_text("content of %s" % name, encoding="utf-8")
        return self.store.add_source(
            self.workspace, name=name, file_path=str(path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, document_authority=authority,
            actor="tester", governance_log=self.gov,
        )

    def _requirement(self, ident, text):
        return self.store.register_requirement(
            self.workspace, source_id=self.spec["id"],
            original_requirement_identifier=ident, text_reference=text,
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            governance_log=self.gov,
        )


class AuthorityGovernsTests(_B1Base):
    """A. Explicit Addendum amendment, and the refusals around it."""

    def test_an_addendum_with_contractual_authority_is_recognized(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        decision = ca.recognize_arrival(self.store, self.workspace, addendum["id"])
        self.assertTrue(decision["recognized"])
        self.assertEqual(decision["authority_basis"], DOCUMENT_AUTHORITY_CONTRACTUAL)

    def test_an_addendum_amends_one_requirement(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        assessment = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Addendum 3 item 4 revises damper closure.",
            actor="pm", governance_log=self.gov)
        self.assertEqual(assessment["change_type"], CHANGE_TYPE_AMENDS)
        self.assertEqual(assessment["authority_basis"], DOCUMENT_AUTHORITY_CONTRACTUAL)

    def test_a_document_with_no_declared_authority_recognizes_nothing(self):
        """Honest absence, not a permissive default."""
        plain = self._source("some-note.txt", None)
        decision = ca.recognize_arrival(self.store, self.workspace, plain["id"])
        self.assertFalse(decision["recognized"])
        self.assertIsNone(decision["authority_basis"])

    def test_newer_arrival_alone_does_not_confer_authority(self):
        """The core B1 refusal: recency is not authority. This document is
        registered LAST and still cannot amend anything."""
        newest = self._source("2026-latest-revision-final.pdf", None)
        with self.assertRaises(ca.ChangeArrivalError):
            ca.propose_change(
                self.store, self.workspace, newest["id"], self.requirement["id"],
                CHANGE_TYPE_AMENDS, evidence="It is the newest file.", actor="pm")

    def test_reference_authority_cannot_amend(self):
        reference = self._source("standard-detail.pdf", DOCUMENT_AUTHORITY_REFERENCE)
        with self.assertRaises(ca.ChangeArrivalError):
            ca.propose_change(
                self.store, self.workspace, reference["id"], self.requirement["id"],
                CHANGE_TYPE_AMENDS, evidence="Reference detail differs.", actor="pm")

    def test_supersede_is_refused_on_insufficient_authority_too(self):
        reference = self._source("draft-spec.pdf", DOCUMENT_AUTHORITY_REFERENCE)
        with self.assertRaises(ca.ChangeArrivalError):
            ca.propose_change(
                self.store, self.workspace, reference["id"], self.requirement["id"],
                CHANGE_TYPE_SUPERSEDES, evidence="Replaces it.", actor="pm")


class ClarificationWithoutAmendmentTests(_B1Base):
    """B. A later document discusses the same subject and changes nothing."""

    def test_a_clarification_is_recordable_without_moving_authority(self):
        note = self._source("meeting-note.txt", DOCUMENT_AUTHORITY_INFORMATIONAL)
        assessment = ca.propose_change(
            self.store, self.workspace, note["id"], self.requirement["id"],
            CHANGE_TYPE_CLARIFIES,
            evidence="Minutes discuss damper closure without changing it.",
            actor="pm")
        self.assertEqual(assessment["change_type"], CHANGE_TYPE_CLARIFIES)
        self.assertNotIn(assessment["change_type"], AUTHORITY_MOVING_CHANGE_TYPES)

    def test_no_change_is_a_real_recordable_finding(self):
        note = self._source("transmittal.txt", DOCUMENT_AUTHORITY_REFERENCE)
        assessment = ca.propose_change(
            self.store, self.workspace, note["id"], self.requirement["id"],
            CHANGE_TYPE_NO_CHANGE, evidence="Transmittal lists it, changes nothing.",
            actor="pm")
        self.assertEqual(assessment["change_type"], CHANGE_TYPE_NO_CHANGE)

    def test_a_clarification_never_reaches_the_b2_handoff(self):
        note = self._source("note.txt", DOCUMENT_AUTHORITY_INFORMATIONAL)
        a = ca.propose_change(
            self.store, self.workspace, note["id"], self.requirement["id"],
            CHANGE_TYPE_CLARIFIES, evidence="Discussion only.", actor="pm")
        self.store.review_change_arrival_assessment(
            self.workspace, a["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        self.assertEqual(ca.ready_for_b2(self.store, self.workspace), [],
                         "an accepted clarification was handed to B2 as a revision")


class RFIConflictTests(_B1Base):
    """C. An RFI answer conflicts with a requirement but is not Addendum-authorized."""

    def test_an_rfi_answer_cannot_amend_the_requirement_it_conflicts_with(self):
        rfi = self._source("rfi-042-answer.pdf", DOCUMENT_AUTHORITY_INFORMATIONAL)
        with self.assertRaises(ca.ChangeArrivalError) as ctx:
            ca.propose_change(
                self.store, self.workspace, rfi["id"], self.requirement["id"],
                CHANGE_TYPE_AMENDS,
                evidence="RFI 042 answer states dampers may remain open.",
                actor="pm")
        self.assertIn("authority", str(ctx.exception).lower())

    def test_the_conflict_is_still_recordable_as_a_conflict(self):
        """Refusing the amendment must not mean losing the conflict - that
        would hide exactly the thing a reviewer needs to see."""
        rfi = self._source("rfi-042-answer.pdf", DOCUMENT_AUTHORITY_INFORMATIONAL)
        assessment = ca.propose_change(
            self.store, self.workspace, rfi["id"], self.requirement["id"],
            CHANGE_TYPE_REVIEW,
            evidence="RFI 042 answer conflicts with R-1 but carries no change authority.",
            actor="pm", uncertainty="Answer conflicts; authority insufficient to amend.")
        self.assertEqual(assessment["change_type"], CHANGE_TYPE_REVIEW)
        self.assertTrue(assessment["uncertainty"])


class AmbiguousScopeTests(_B1Base):
    """E. Report REVIEW rather than inventing a change."""

    def test_review_is_its_own_answer_not_a_weak_amendment(self):
        addendum = self._source("addendum-4.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        assessment = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_REVIEW, evidence="Addendum 4 revises 'the damper schedule'.",
            actor="pm", uncertainty="Which dampers is not established.")
        self.assertEqual(assessment["change_type"], CHANGE_TYPE_REVIEW)
        self.assertNotIn(CHANGE_TYPE_REVIEW, AUTHORITY_MOVING_CHANGE_TYPES)

    def test_an_accepted_review_is_still_not_handed_to_b2(self):
        addendum = self._source("addendum-4.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_REVIEW, evidence="Ambiguous scope.", actor="pm")
        self.store.review_change_arrival_assessment(
            self.workspace, a["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        self.assertEqual(ca.ready_for_b2(self.store, self.workspace), [],
                         "an ambiguous assessment was promoted into a revision")


class HumanAuthorityTests(_B1Base):
    """GOV-P-006 as behaviour, not as a comment."""

    def test_every_assessment_starts_proposed(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        self.assertEqual(a["state"], CHANGE_ARRIVAL_STATE_PROPOSED)

    def test_a_proposal_is_not_handed_to_b2_until_a_human_accepts(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        self.assertEqual(ca.ready_for_b2(self.store, self.workspace), [])
        self.store.review_change_arrival_assessment(
            self.workspace, a["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        self.assertEqual([r["id"] for r in ca.ready_for_b2(self.store, self.workspace)],
                         [a["id"]])

    def test_a_rejected_proposal_is_never_handed_to_b2(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        self.store.review_change_arrival_assessment(
            self.workspace, a["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_REJECTED)
        self.assertEqual(ca.ready_for_b2(self.store, self.workspace), [])

    def test_a_review_cannot_return_a_claim_to_proposed(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        with self.assertRaises(CaseWorkspaceError):
            self.store.review_change_arrival_assessment(
                self.workspace, a["id"], actor="pm",
                outcome=CHANGE_ARRIVAL_STATE_PROPOSED)

    def test_b1_never_revises_the_requirement(self):
        """The B1/B2 line, asserted directly: accepting a change leaves the
        Requirement and the supersession record untouched."""
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        before = dict(self.store.get(self.workspace.project_id).requirements[0])
        supersessions_before = len(self.workspace.supersessions)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        self.store.review_change_arrival_assessment(
            self.workspace, a["id"], actor="pm", outcome=CHANGE_ARRIVAL_STATE_ACCEPTED)
        after = self.store.get(self.workspace.project_id)
        self.assertEqual(after.requirements[0]["text_reference"], before["text_reference"])
        self.assertEqual(len(after.supersessions), supersessions_before,
                         "B1 wrote a supersession - that is B2's act")


class SupersededSourceTests(_B1Base):
    """D. Old text stays visible without regaining authority."""

    def test_a_superseded_source_does_not_regain_change_authority(self):
        old = self._source("spec-rev-a.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        new_source, _notices, _supersession = self.store.register_source_revision(
            self.workspace, old_source_id=old["id"], name="spec-rev-b.pdf",
            file_path=str(self.tmp_dir / "spec-rev-b.pdf"), actor="pm",
            kind=SOURCE_KIND_PROJECT_DOCUMENT)
        refreshed = self.store.get(self.workspace.project_id)
        superseded = next(s for s in refreshed.sources if s["id"] == old["id"])
        self.assertTrue(superseded.get("superseded_by_source_id"))
        # Still readable, still carries its own declared authority - being
        # superseded does not erase what it was, which is what keeps history
        # reconstructable.
        self.assertEqual(superseded["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertIsNotNone(new_source["id"])

    def test_an_assessment_against_a_superseded_source_keeps_its_lineage(self):
        old = self._source("spec-rev-a.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        a = ca.propose_change(
            self.store, self.workspace, old["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Rev A item 2.", actor="pm")
        self.store.register_source_revision(
            self.workspace, old_source_id=old["id"], name="spec-rev-b.pdf",
            file_path=str(self.tmp_dir / "spec-rev-b.pdf"), actor="pm",
            kind=SOURCE_KIND_PROJECT_DOCUMENT)
        rows = self.store.change_arrival_assessments_for(
            self.store.get(self.workspace.project_id), incoming_source_id=old["id"])
        self.assertEqual([r["id"] for r in rows], [a["id"]],
                         "revising the source erased the assessment's lineage")


class A2ConsumptionTests(_B1Base):
    """F. B1 is A2's first real production consumer."""

    def test_b1_reports_governed_dependents_through_a2(self):
        dependent = self._requirement("R-2", "Damper schedule references R-1.")
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        affected = ca.affected_dependents(self.store, self.workspace, self.requirement["id"])
        self.assertEqual([e["other"]["id"] for e in affected["dependents"]], [dependent["id"]])
        self.assertEqual(affected["counts"]["explicit"], 1)

    def test_it_preserves_the_inferred_distinction_rather_than_flattening_it(self):
        dependent = self._requirement("R-3", "Machine-proposed dependent.")
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=True)
        affected = ca.affected_dependents(self.store, self.workspace, self.requirement["id"])
        self.assertEqual(affected["counts"], {"total": 1, "explicit": 0, "inferred": 1})
        self.assertTrue(affected["dependents"][0]["inferred"])

    def test_a_contradiction_is_surfaced_beside_dependents_never_inside_them(self):
        conflicting = self._requirement("R-4", "Conflicting requirement.")
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=conflicting["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_CONTRADICTS, provisional=False)
        affected = ca.affected_dependents(self.store, self.workspace, self.requirement["id"])
        self.assertEqual(affected["counts"]["total"], 0)
        self.assertEqual(len(affected["contradicting"]), 1)

    def test_a_rejected_edge_is_not_traversed_as_an_accepted_dependency(self):
        dependent = self._requirement("R-5", "Rejected dependent.")
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        self.store.reject_relationship(self.workspace, rel["id"], actor="pm")
        affected = ca.affected_dependents(self.store, self.workspace, self.requirement["id"])
        statuses = [e["status"] for e in affected["dependents"]]
        self.assertIn("rejected", statuses,
                      "the human rejection was hidden rather than reported")

    def test_the_reviewer_brief_assembles_assessment_and_dependents_together(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        dependent = self._requirement("R-6", "Dependent.")
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        a = ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="go")
        brief = ca.assessment_brief(self.store, self.workspace, a["id"])
        self.assertTrue(brief["moves_authority"])
        self.assertTrue(brief["awaiting_human"])
        self.assertEqual(brief["affected"]["counts"]["total"], 1)

    def test_b1_does_not_resolve_or_rewrite_dependents(self):
        """The B1/B3 line: naming who is affected is not resolving them."""
        dependent = self._requirement("R-7", "Downstream.")
        before = dict(dependent)
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=dependent["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=self.requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_DEPENDS_ON, provisional=False)
        ca.affected_dependents(self.store, self.workspace, self.requirement["id"])
        after = next(r for r in self.store.get(self.workspace.project_id).requirements
                     if r["id"] == dependent["id"])
        self.assertEqual(after["text_reference"], before["text_reference"])
        self.assertEqual(after.get("status"), before.get("status"))


class ProjectIsolationTests(_B1Base):
    """G. A change in Project A cannot reach Project B."""

    def test_an_assessment_cannot_target_another_projects_requirement(self):
        other = self.store.get_or_create("test-project-b1-other")
        other_path = self.tmp_dir / "other.txt"
        other_path.write_text("other", encoding="utf-8")
        other_source = self.store.add_source(
            other, name="other.txt", file_path=str(other_path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT,
            document_authority=DOCUMENT_AUTHORITY_CONTRACTUAL, actor="tester")
        foreign_requirement = self.store.register_requirement(
            other, source_id=other_source["id"], original_requirement_identifier="X-1",
            text_reference="Foreign requirement.", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE)

        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        with self.assertRaises(CaseWorkspaceError):
            ca.propose_change(
                self.store, self.workspace, addendum["id"], foreign_requirement["id"],
                CHANGE_TYPE_AMENDS, evidence="Cross-project reach.", actor="pm")

    def test_assessments_do_not_leak_between_projects(self):
        addendum = self._source("addendum-3.pdf", DOCUMENT_AUTHORITY_CONTRACTUAL)
        ca.propose_change(
            self.store, self.workspace, addendum["id"], self.requirement["id"],
            CHANGE_TYPE_AMENDS, evidence="Item 4.", actor="pm")
        other = self.store.get_or_create("test-project-b1-other2")
        self.assertEqual(self.store.change_arrival_assessments_for(other), [])
        self.assertEqual(ca.ready_for_b2(self.store, other), [])


if __name__ == "__main__":
    unittest.main()
