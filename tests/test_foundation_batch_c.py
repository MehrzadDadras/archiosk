"""
Foundation Batch C (Prompt 9) tests: Project-level Analysis, the
open_project() lifecycle operation, and the Design-Build departure
demonstration using Batch B's typed Relationship substrate - no new
domain object, per the accepted pre-Batch-C architectural review.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_CLOCK_INITIATED,
    ANALYSIS_TRIGGER_USER_INITIATED,
    KNOWN_RELATIONSHIP_TYPES,
    OBJECT_KIND_SOURCE,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog
from services.project_clock import open_project


class ProjectLevelAnalysisTests(unittest.TestCase):
    """Tests A, B, C, D, I."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_c_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-c1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_a_existing_case_scoped_analysis_still_works(self):
        case = self.store.create_case(self.workspace, title="Case A", objective="")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[], objective="analyze x",
            engine_name="mock", engine_version="0.0", findings=[], trigger=trigger,
        )
        self.assertEqual(analysis["case_id"], case["id"])
        reloaded = self.store.get(self.project_id)
        self.assertIn(analysis["id"], reloaded.cases[0]["analysis_ids"])

    def test_b_project_level_analysis_works_with_no_case_id(self):
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        analysis = self.store.record_analysis(
            self.workspace, source_ids=[], objective="project-wide check",
            engine_name="mock", engine_version="0.0", findings=[], trigger=trigger,
        )
        self.assertIsNone(analysis["case_id"])
        self.assertEqual(analysis["project_id"], self.project_id)
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.analyses), 1)
        self.assertEqual(reloaded.cases, [])  # no Case was fabricated

    def test_project_level_analysis_rejects_real_findings(self):
        """Prompt 9 #2's stated extension boundary: Finding/Artifact stay
        Case-scoped this batch, so a Project-level Analysis must not
        smuggle real Findings through with no Case to attach them to."""
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED)
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_analysis(
                self.workspace, source_ids=[], objective="x", engine_name="mock",
                engine_version="0.0",
                findings=[{"statement": "should not be allowed", "machine_confidence": 0.5}],
                trigger=trigger,
            )

    def test_c_clock_initiated_project_analysis_no_case(self):
        """Prompt 9 #3: a Project milestone with no Investigation Case
        must still produce a CLOCK_INITIATED Project Analysis."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        self.store.create_temporal_obligation(
            self.workspace, title="Proposal Submission", origin_type="activity", origin_id="proposal-1",
            required_action="Submit the proposal.", accepted_date=past_date, created_by="tester",
        )
        observations = open_project(self.workspace, self.store, self.gov)
        self.assertTrue(any(o.analysis_id for o in observations))

        reloaded = self.store.get(self.project_id)
        analysis = reloaded.analyses[-1]
        self.assertIsNone(analysis["case_id"])  # no artificial Case created
        self.assertEqual(analysis["trigger"]["trigger_type"], ANALYSIS_TRIGGER_CLOCK_INITIATED)
        self.assertEqual(analysis["finding_ids"], [])
        self.assertEqual(reloaded.cases, [])  # still no Case anywhere in the project

    def test_d_repeated_project_open_is_idempotent(self):
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        self.store.create_temporal_obligation(
            self.workspace, title="Proposal Submission", origin_type="activity", origin_id="proposal-1",
            required_action="Submit the proposal.", accepted_date=past_date, created_by="tester",
        )
        open_project(self.workspace, self.store, self.gov)
        open_project(self.workspace, self.store, self.gov)
        open_project(self.workspace, self.store, self.gov)

        events = [e for e in self.gov.read(self.project_id) if e.event_type == "temporal_condition_changed"]
        analyses_events = [e for e in self.gov.read(self.project_id) if e.event_type == "analysis_started"]
        self.assertEqual(len(events), 1)
        self.assertEqual(len(analyses_events), 1)
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.analyses), 1)  # not 3

    def test_i_legacy_json_without_case_id_field_present_still_reads(self):
        """An AnalysisRun dict from before this batch always had a real
        case_id value (it was required) - confirms relaxing the field to
        Optional doesn't break loading records that still have it set."""
        import json
        legacy_project_id = "legacy-project-c"
        legacy_analysis = {
            "id": "a1", "project_id": legacy_project_id, "case_id": "c1",
            "source_ids": [], "objective": "x", "engine_name": "e", "engine_version": "1",
            "started_at": "2020-01-01T00:00:00+00:00", "completed_at": "2020-01-01T00:00:01+00:00",
            "finding_ids": [], "prior_corrections_considered": 0,
        }
        legacy_data = {"project_id": legacy_project_id, "analyses": [legacy_analysis],
                       "cases": [{"id": "c1", "project_id": legacy_project_id, "title": "t", "objective": "",
                                  "created_at": "2020-01-01T00:00:00+00:00", "status": "open",
                                  "source_ids": [], "conversation": [], "analysis_ids": ["a1"],
                                  "finding_ids": [], "artifact_ids": []}]}
        (self.tmp_dir / f"{legacy_project_id}.workspace.json").write_text(json.dumps(legacy_data), encoding="utf-8")
        workspace = self.store.get(legacy_project_id)
        self.assertEqual(workspace.analyses[0]["case_id"], "c1")


class DesignBuildDepartureDemonstrationTests(unittest.TestCase):
    """
    Tests E, F, G, H: the Design-Build departure scenario (Prompt 9 §5-7),
    represented entirely with Batch B's existing typed Relationship
    substrate plus the existing Finding/ReviewerValidation/Disposition/
    Apply machinery - no new schema, per the accepted architectural review.
    """

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_c_db_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-c2"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_indicative_and_developed_sources(self):
        img_path = self.tmp_dir / "img.png"
        from PIL import Image
        Image.new("RGB", (10, 10), (255, 255, 255)).save(img_path)
        indicative = self.store.add_drawing_source(
            self.workspace, name="indicative_site_plan.png", file_path=str(img_path), width=10, height=10,
        )
        developed = self.store.add_drawing_source(
            self.workspace, name="developed_design.png", file_path=str(img_path), width=10, height=10,
        )
        return indicative, developed

    def test_e_provisional_departs_from_relationship_exists_without_a_finding(self):
        indicative, developed = self._register_indicative_and_developed_sources()

        departure = self.store.record_relationship(
            self.workspace,
            from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from",  # open-world extension type - not in the canonical vocabulary
            created_by="tester", provisional=True, confidence=0.5,
        )

        self.assertTrue(departure["provisional"])
        self.assertEqual(departure["relationship_type"], "departs_from")
        self.assertNotIn("departs_from", KNOWN_RELATIONSHIP_TYPES)  # preserved verbatim, not coerced

        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.findings, [])  # noticing a departure never itself creates a Finding
        self.assertEqual(reloaded.cases, [])  # nor does it require a Case to exist

    def test_f_compliant_alternative_preserves_departure_and_adds_no_noncompliance_finding(self):
        """Outcome A: evidence shows the vertical alternative satisfies the
        requirement. The departure stays on record, unchanged; a SEPARATE
        relationship records satisfaction; no non-compliance Finding
        appears anywhere."""
        indicative, developed = self._register_indicative_and_developed_sources()
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )

        satisfaction = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type="requirement", to_id="R-042",  # open-world object kind, not in KNOWN_OBJECT_KINDS
            relationship_type=RELATIONSHIP_TYPE_CORRESPONDS_TO,  # a canonical type
            created_by="tester", provisional=True, confidence=0.85,
        )

        reloaded = self.store.get(self.project_id)
        still_there = self.store._find(reloaded.relationships, departure["id"])
        self.assertIsNotNone(still_there)  # the departure is historically true and was never deleted
        self.assertEqual(still_there["relationship_type"], "departs_from")
        self.assertIsNotNone(self.store._find(reloaded.relationships, satisfaction["id"]))
        self.assertEqual(reloaded.findings, [])  # a compliant alternative creates no non-compliance Finding

    def test_g_needs_evidence_does_not_fabricate_compliance_or_noncompliance(self):
        """Outcome B: evidence is insufficient either way. Default
        behavior records nothing further and leaves the departure
        provisional/unresolved (Prompt 9 §7's stated preference). If a
        reviewer explicitly escalates to formal review, the resulting
        Finding must honestly carry "Needs Evidence", never a confirmed
        failure, and must not be Applicable."""
        indicative, developed = self._register_indicative_and_developed_sources()
        departure = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )

        # Default: no escalation happens merely because evidence is thin.
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.findings, [])
        still_provisional = self.store._find(reloaded.relationships, departure["id"])
        self.assertTrue(still_provisional["provisional"])  # remains unresolved, neither confirmed nor denied

        # If a reviewer DOES escalate to formal review:
        case = self.store.create_case(self.workspace, title="Departure Review", objective="Assess R-042 impact")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
        analysis = self.store.record_analysis(
            self.workspace, case_id=case["id"], source_ids=[developed["id"]],
            objective="Assess whether vertical expansion satisfies R-042.",
            engine_name="human-review", engine_version="0.0",
            findings=[{
                "statement": "Vertical expansion departs from indicative westward strategy; "
                             "R-042 compliance not yet established.",
                "machine_confidence": 0.5, "source_id": developed["id"],
            }],
            trigger=trigger,
        )
        finding_id = analysis["finding_ids"][0]

        self.store.record_reviewer_validation(
            self.workspace, finding_id=finding_id, validation="Needs Evidence", reviewer="tester",
        )
        self.assertEqual(self.store.review_state_for_finding(self.workspace, finding_id), "Not Verified")

        self.store.record_disposition(self.workspace, finding_id=finding_id, disposition="Deferred", reviewer="tester")
        latest_disposition = self.store.latest_disposition(self.workspace, finding_id)
        self.assertEqual(latest_disposition["disposition"], "Deferred")

        # Not authoritative truth - Apply must refuse a non-Confirmed disposition.
        with self.assertRaises(CaseWorkspaceError):
            self.store.apply_findings(self.workspace, finding_ids=[finding_id], applied_by="tester")

    def test_h_genuine_noncompliance_requires_finding_and_full_adjudication(self):
        """Outcome C: further evidence establishes genuine non-compliance.
        Only now does a Finding get Confirmed and Applied, becoming
        governed truth (Accepted Knowledge) through the ordinary path."""
        indicative, developed = self._register_indicative_and_developed_sources()
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_SOURCE, from_id=developed["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=indicative["id"],
            relationship_type="departs_from", created_by="tester", provisional=True, confidence=0.5,
        )

        case = self.store.create_case(self.workspace, title="Departure Review", objective="Assess R-042 impact")
        trigger = AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester")
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

        self.store.record_reviewer_validation(self.workspace, finding_id=finding_id, validation="Correct", reviewer="tester")
        self.store.record_disposition(self.workspace, finding_id=finding_id, disposition="Confirmed", reviewer="tester")
        self.store.apply_findings(self.workspace, finding_ids=[finding_id], applied_by="tester")

        reloaded = self.store.get(self.project_id)
        applied_finding = self.store._find(reloaded.findings, finding_id)
        self.assertEqual(applied_finding["claim_status"], "applied")
        knowledge = self.store.knowledge_for_project(reloaded)
        self.assertTrue(any(k["source_finding_id"] == finding_id for k in knowledge))


if __name__ == "__main__":
    unittest.main()
