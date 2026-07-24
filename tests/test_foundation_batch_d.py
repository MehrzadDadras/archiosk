"""
Foundation Batch D (Prompt 10) tests: ReviewThread, Anchor, ReviewMessage,
Attention, resolution/reopen lifecycle, and structured outcome linkage -
including the full Design-Build departure discussion across all three
outcomes (resolved/waiting/escalated), built on Batch B/C's Relationship
and Analysis substrate.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    ATTENTION_STATUS_PENDING,
    ATTENTION_STATUS_RESPONDED,
    KNOWN_RELATIONSHIP_TYPES,
    MESSAGE_ORIGIN_HUMAN,
    MESSAGE_ORIGIN_MACHINE,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_RELATIONSHIP,
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_SOURCE,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    RELATIONSHIP_TYPE_RESULTED_IN,
    RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE,
    RESOLUTION_OUTCOME_CONFIRMED_ISSUE,
    THREAD_STATUS_OPEN,
    THREAD_STATUS_RESOLVED,
    THREAD_STATUS_REOPENED,
    THREAD_STATUS_WAITING_FOR_RESPONSE,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog


class ReviewThreadBaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_d_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-d1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _add_source(self, name):
        img_path = self.tmp_dir / f"{name}.png"
        Image.new("RGB", (10, 10), (255, 255, 255)).save(img_path)
        return self.store.add_drawing_source(self.workspace, name=f"{name}.png", file_path=str(img_path), width=10, height=10)

    # A
    def test_a_review_thread_creation(self):
        thread = self.store.create_review_thread(
            self.workspace, title="Future expansion strategy", anchor_type="source",
            anchor_id="src-1", created_by="tester", governance_log=self.gov,
        )
        self.assertEqual(thread["status"], THREAD_STATUS_OPEN)
        self.assertEqual(thread["anchor"]["anchor_type"], "source")
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "review_thread_created"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].correlation_id, thread["id"])

    # B
    def test_b_project_level_thread_without_case_id(self):
        thread = self.store.create_review_thread(
            self.workspace, title="Project-wide concern", anchor_type="temporal_obligation",
            anchor_id="obl-1", created_by="tester",
        )
        self.assertIsNone(thread["case_id"])
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.cases, [])  # no Case fabricated

    # C
    def test_c_optional_case_attachment(self):
        case = self.store.create_case(self.workspace, title="Investigation", objective="")
        thread = self.store.create_review_thread(
            self.workspace, title="Case-attached concern", anchor_type="finding",
            anchor_id="f-1", created_by="tester", case_id=case["id"],
        )
        self.assertEqual(thread["case_id"], case["id"])
        threads = self.store.threads_for_case(self.workspace, case["id"])
        self.assertEqual(len(threads), 1)

    # D
    def test_d_anchoring_to_an_existing_relationship(self):
        developed = self._add_source("developed")
        indicative = self._add_source("indicative")
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )
        thread = self.store.create_review_thread(
            self.workspace, title="Future expansion departure", anchor_type=OBJECT_KIND_RELATIONSHIP,
            anchor_id=departure["id"], created_by="tester",
            anchor_description="developed design departs from indicative future-expansion strategy",
        )
        found = self.store.threads_for_anchor(self.workspace, OBJECT_KIND_RELATIONSHIP, departure["id"])
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], thread["id"])

    # E
    def test_e_human_comment(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="critique", text="The indicative arrangement is not necessarily mandatory.",
        )
        self.assertEqual(message["origin"], MESSAGE_ORIGIN_HUMAN)
        self.assertEqual(message["message_type"], "critique")
        self.assertIsNotNone(message["project_state_version"])

    # F
    def test_f_machine_comment_with_analysis_provenance(self):
        case = self.store.create_case(self.workspace, title="c", objective="")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[], objective="x",
            engine_name="mock", engine_version="0.0", findings=[], trigger=trigger,
        )
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        message = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="beehive-analysis-engine",
            message_type="observation",
            text="Developed design materially departs from the indicative future-expansion arrangement.",
            related_analysis_id=analysis["id"],
        )
        self.assertEqual(message["origin"], MESSAGE_ORIGIN_MACHINE)
        self.assertEqual(message["related_analysis_id"], analysis["id"])
        # no hidden reasoning field exists on ReviewMessage at all - only `text`
        self.assertNotIn("chain_of_thought", message)
        self.assertNotIn("reasoning", message)

    # G
    def test_g_reply_threading(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="engine",
            message_type="observation", text="Possible departure noticed.",
        )
        m2 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="question", text="Verify the governing requirement.", reply_to_message_id=m1["id"],
        )
        self.assertEqual(m2["reply_to_message_id"], m1["id"])
        thread_messages = self.store.messages_for_thread(self.workspace, thread["id"])
        self.assertEqual(len(thread_messages), 2)

    # H
    def test_h_attention_request(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="question", text="@Architect confirm vertical expansion feasibility.",
        )
        attention = self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=m1["id"],
            intended_actor="@Architect", created_by="reviewer1", governance_log=self.gov,
        )
        self.assertEqual(attention["intended_actor"], "@Architect")
        self.assertEqual(attention["status"], ATTENTION_STATUS_PENDING)
        reloaded_thread = self.store._find(self.store.get(self.project_id).review_threads, thread["id"])
        self.assertEqual(reloaded_thread["status"], THREAD_STATUS_WAITING_FOR_RESPONSE)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "review_attention_requested"]
        self.assertEqual(len(events), 1)

    # I
    def test_i_attention_creates_no_work_item_or_other_side_effect(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="question", text="@Structural please confirm.",
        )
        before = self.store.get(self.project_id)
        self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=m1["id"],
            intended_actor="@Structural", created_by="reviewer1",
        )
        after = self.store.get(self.project_id)
        # Nothing except attentions + this thread's status changed - no
        # WorkItem-shaped concept exists anywhere in the schema, and no
        # Finding/Disposition/Relationship/AnalysisRun was created either.
        self.assertEqual(len(after.attentions), 1)
        self.assertEqual(before.findings, after.findings)
        self.assertEqual(before.dispositions, after.dispositions)
        self.assertEqual(before.relationships, after.relationships)
        self.assertEqual(before.analyses, after.analyses)

    def test_respond_to_attention_returns_thread_to_under_review(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="question", text="@Architect confirm.",
        )
        attention = self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=m1["id"],
            intended_actor="@Architect", created_by="reviewer1",
        )
        m2 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="architect1",
            message_type="response", text="Confirmed; structural reserve attached.",
            reply_to_message_id=m1["id"],
        )
        self.store.respond_to_attention(self.workspace, attention_id=attention["id"], response_message_id=m2["id"])
        reloaded = self.store.get(self.project_id)
        att = self.store._find(reloaded.attentions, attention["id"])
        self.assertEqual(att["status"], ATTENTION_STATUS_RESPONDED)
        thread_after = self.store._find(reloaded.review_threads, thread["id"])
        self.assertNotEqual(thread_after["status"], THREAD_STATUS_WAITING_FOR_RESPONSE)

    # J
    def test_j_thread_resolution(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        resolved = self.store.resolve_review_thread(
            self.workspace, thread_id=thread["id"], resolution_outcome=RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE,
            summary="Accepted - alternative satisfies requirement.", resolved_by="design_manager",
            governance_log=self.gov,
        )
        self.assertEqual(resolved["status"], THREAD_STATUS_RESOLVED)
        self.assertIsNotNone(resolved["resolution"])
        self.assertEqual(resolved["resolution"]["resolution_outcome"], RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE)
        with self.assertRaises(CaseWorkspaceError):
            self.store.resolve_review_thread(
                self.workspace, thread_id=thread["id"], resolution_outcome="no_issue",
                summary="x", resolved_by="tester",
            )

    # K
    def test_k_reopen_preserves_original_resolution_and_history(self):
        thread = self.store.create_review_thread(
            self.workspace, title="t", anchor_type="source", anchor_id="s-1", created_by="tester",
        )
        self.store.resolve_review_thread(
            self.workspace, thread_id=thread["id"], resolution_outcome="no_issue",
            summary="Initially thought fine.", resolved_by="reviewer1",
        )
        reopened = self.store.reopen_review_thread(
            self.workspace, thread_id=thread["id"], reason="New field condition discovered.",
            actor="reviewer2", governance_log=self.gov,
        )
        self.assertEqual(reopened["status"], THREAD_STATUS_REOPENED)
        self.assertIsNone(reopened["resolution"])
        self.assertEqual(len(reopened["resolution_history"]), 1)
        self.assertEqual(reopened["resolution_history"][0]["resolution"]["summary"], "Initially thought fine.")
        self.assertEqual(reopened["resolution_history"][0]["reopen_reason"], "New field condition discovered.")

        # A second resolution after reopening does not erase the first.
        self.store.resolve_review_thread(
            self.workspace, thread_id=thread["id"], resolution_outcome=RESOLUTION_OUTCOME_CONFIRMED_ISSUE,
            summary="Actually a real issue.", resolved_by="reviewer2",
        )
        final = self.store._find(self.store.get(self.project_id).review_threads, thread["id"])
        self.assertEqual(final["resolution"]["summary"], "Actually a real issue.")
        self.assertEqual(len(final["resolution_history"]), 1)  # still just the one prior resolution
        self.assertEqual(final["resolution_history"][0]["resolution"]["summary"], "Initially thought fine.")

    # O
    def test_o_legacy_json_without_review_thread_fields_loads_cleanly(self):
        import json
        legacy_project_id = "legacy-project-d"
        legacy_path = self.tmp_dir / f"{legacy_project_id}.workspace.json"
        legacy_path.write_text(json.dumps({"project_id": legacy_project_id}), encoding="utf-8")
        workspace = self.store.get(legacy_project_id)
        self.assertEqual(workspace.review_threads, [])
        self.assertEqual(workspace.review_messages, [])
        self.assertEqual(workspace.attentions, [])


class DesignBuildReviewThreadScenarioTests(unittest.TestCase):
    """
    Tests L, M, N: the full Batch-C Design-Build scenario, now with a
    ReviewThread carrying the discussion around the existing provisional
    departs_from Relationship, across all three outcomes.
    """

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_d_scenario_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-d2"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sources(self):
        img_path = self.tmp_dir / "img.png"
        Image.new("RGB", (10, 10), (255, 255, 255)).save(img_path)
        developed = self.store.add_drawing_source(self.workspace, name="developed.png", file_path=str(img_path), width=10, height=10)
        indicative = self.store.add_drawing_source(self.workspace, name="indicative.png", file_path=str(img_path), width=10, height=10)
        return developed, indicative

    # L
    def test_l_resolved_compliant_alternative_creates_no_noncompliance_finding(self):
        developed, indicative = self._sources()
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )

        thread = self.store.create_review_thread(
            self.workspace, title="Future expansion strategy departure", anchor_type=OBJECT_KIND_RELATIONSHIP,
            anchor_id=departure["id"], created_by="tester", governance_log=self.gov,
        )

        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="beehive-analysis-engine",
            message_type="observation",
            text="Developed design materially departs from the indicative future-expansion arrangement.",
        )
        m2 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="critique", text="The indicative arrangement is not necessarily mandatory. Verify R-042.",
            reply_to_message_id=m1["id"],
        )
        m3 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="beehive-analysis-engine",
            message_type="interpretation",
            text="OPR R-042 requires future expansion capacity; direction of expansion is not prescribed.",
            reply_to_message_id=m2["id"], related_object_type=OBJECT_KIND_REQUIREMENT, related_object_id="R-042",
        )
        m4 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="clarification_request",
            text="@Architect provide evidence that vertical expansion can be achieved without compromising operations.",
            reply_to_message_id=m3["id"],
        )
        attention = self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=m4["id"],
            intended_actor="@Architect", created_by="reviewer1", governance_log=self.gov,
        )
        m5 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="architect1",
            message_type="evidence_note", text="Structural reserve and phasing information attached.",
            reply_to_message_id=m4["id"],
        )
        self.store.respond_to_attention(self.workspace, attention_id=attention["id"], response_message_id=m5["id"])

        satisfaction = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id="R-042",
            relationship_type=RELATIONSHIP_TYPE_CORRESPONDS_TO, created_by="architect1", provisional=True, confidence=0.85,
        )

        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="design_manager",
            message_type="resolution_note", text="Accepted. Alternative satisfies the requirement.",
            reply_to_message_id=m5["id"],
        )
        self.store.resolve_review_thread(
            self.workspace, thread_id=thread["id"], resolution_outcome=RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE,
            summary="Vertical expansion accepted as satisfying R-042; westward direction was indicative, not mandatory.",
            resolved_by="design_manager",
            related_evidence_refs=[{"type": "relationship", "id": satisfaction["id"]}],
            governance_log=self.gov,
        )
        final_thread = self.store.link_thread_outcome(
            self.workspace, thread_id=thread["id"], outcome_type="acceptable_alternative", actor="design_manager",
            confirm_relationship_id=departure["id"], reason="Departure confirmed acceptable, not a defect.",
            governance_log=self.gov,
        )

        reloaded = self.store.get(self.project_id)

        # The departure remains historically true, now confirmed rather than merely provisional.
        departure_after = self.store._find(reloaded.relationships, departure["id"])
        self.assertEqual(departure_after["relationship_type"], "departs_from")
        self.assertFalse(departure_after["provisional"])
        self.assertEqual(departure_after["confirmed_by"], "design_manager")

        # No non-compliance Finding anywhere.
        self.assertEqual(reloaded.findings, [])
        self.assertEqual(reloaded.cases, [])  # no Case was ever needed

        thread_after = self.store._find(reloaded.review_threads, thread["id"])
        self.assertEqual(thread_after["status"], THREAD_STATUS_RESOLVED)
        self.assertEqual(len(thread_after["outcome_refs"]), 1)
        self.assertEqual(thread_after["outcome_refs"][0]["confirmed_relationship_id"], departure["id"])

        # Full conversation remains reconstructable, in order, unaltered.
        messages = self.store.messages_for_thread(self.workspace, thread["id"])
        self.assertEqual(len(messages), 6)
        self.assertEqual(messages[0]["origin"], MESSAGE_ORIGIN_MACHINE)
        self.assertEqual(messages[-1]["message_type"], "resolution_note")

        # @Architect was an attention event only - never a WorkItem/responsibility construct (none exists).
        attentions = self.store.attentions_for_thread(self.workspace, thread["id"])
        self.assertEqual(len(attentions), 1)
        self.assertEqual(attentions[0]["intended_actor"], "@Architect")
        self.assertEqual(attentions[0]["status"], ATTENTION_STATUS_RESPONDED)

    # M
    def test_m_waiting_for_response_case_fabricates_nothing(self):
        developed, indicative = self._sources()
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.4,
        )
        thread = self.store.create_review_thread(
            self.workspace, title="Possible mechanical disconnect", anchor_type=OBJECT_KIND_RELATIONSHIP,
            anchor_id=departure["id"], created_by="tester",
        )
        m1 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="beehive-analysis-engine",
            message_type="observation", text="Possible disconnect between ductwork routing and structural depth.",
        )
        m2 = self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN, actor="reviewer1",
            message_type="clarification_request", text="@Mechanical please clarify routing intent.",
            reply_to_message_id=m1["id"],
        )
        self.store.request_attention(
            self.workspace, thread_id=thread["id"], message_id=m2["id"],
            intended_actor="@Mechanical", created_by="reviewer1",
        )
        # No response ever arrives.

        reloaded = self.store.get(self.project_id)
        thread_after = self.store._find(reloaded.review_threads, thread["id"])
        self.assertEqual(thread_after["status"], THREAD_STATUS_WAITING_FOR_RESPONSE)
        self.assertIsNone(thread_after["resolution"])
        self.assertEqual(reloaded.findings, [])  # no Finding fabricated
        self.assertEqual(reloaded.cases, [])  # no Case fabricated
        pending = [a for a in reloaded.attentions if a["status"] == ATTENTION_STATUS_PENDING]
        self.assertEqual(len(pending), 1)  # attention remains visibly outstanding

    # N
    def test_n_genuine_contradiction_links_to_finding_via_full_adjudication(self):
        developed, indicative = self._sources()
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )
        thread = self.store.create_review_thread(
            self.workspace, title="Future expansion strategy departure", anchor_type=OBJECT_KIND_RELATIONSHIP,
            anchor_id=departure["id"], created_by="tester",
        )
        self.store.add_review_message(
            self.workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_MACHINE, actor="beehive-analysis-engine",
            message_type="observation", text="Developed design departs from indicative future-expansion strategy.",
        )

        # Escalation to formal review, exactly as Batch C's Outcome C did.
        case = self.store.create_case(self.workspace, title="Departure Review", objective="Assess R-042 impact")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="reviewer1")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[developed["id"]],
            objective="Assess whether vertical expansion satisfies R-042.",
            engine_name="human-review", engine_version="0.0",
            findings=[{
                "statement": "Vertical expansion cannot satisfy R-042's future horizontal-capacity requirement.",
                "machine_confidence": 0.8, "source_id": developed["id"],
            }],
            trigger=trigger,
        )
        finding_id = analysis["finding_ids"][0]

        # The thread links to the Finding - it does NOT itself adjudicate anything.
        self.store.link_thread_outcome(
            self.workspace, thread_id=thread["id"], outcome_type="escalated_to_finding", actor="reviewer1",
            object_type=OBJECT_KIND_FINDING, object_id=finding_id,
        )

        reloaded = self.store.get(self.project_id)
        finding = self.store._find(reloaded.findings, finding_id)
        self.assertEqual(finding["claim_status"], "provisional")  # NOT yet governed truth

        # Full adjudication still required, unbypassed by the thread.
        self.store.record_reviewer_validation(self.workspace, finding_id=finding_id, validation="Correct", reviewer="reviewer1")
        self.store.record_disposition(self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="reviewer1")
        self.store.apply_findings(self.workspace, finding_ids=[finding_id], applied_by="reviewer1")

        final = self.store.get(self.project_id)
        applied_finding = self.store._find(final.findings, finding_id)
        self.assertEqual(applied_finding["claim_status"], "applied")

        thread_after = self.store._find(final.review_threads, thread["id"])
        outcome = thread_after["outcome_refs"][0]
        self.assertEqual(outcome["object_type"], OBJECT_KIND_FINDING)
        self.assertEqual(outcome["object_id"], finding_id)
        rel = self.store._find(final.relationships, outcome["relationship_id"])
        self.assertEqual(rel["relationship_type"], RELATIONSHIP_TYPE_RESULTED_IN)
        self.assertEqual(rel["from_type"], "review_thread")
        self.assertEqual(rel["to_type"], OBJECT_KIND_FINDING)


if __name__ == "__main__":
    unittest.main()
