"""
CLAUDE-P31, Part XI -- learning-zone boundary tests: project-private vs.
organization-private vs. shared-ARCHIOSK-improvement separation, the
required-stages-before-approval gate, self-approval prohibition for
shared contributions, and the structural (import-level) proof that a
quality/reviewer-validation rating never reaches this module at all.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import ast
import shutil
import tempfile
import unittest
from pathlib import Path

from services.learning_governance import (
    LearningGovernanceError,
    STAGE_APPROVED,
    STAGE_AUTHORITY_CHECK,
    STAGE_CANDIDATE_SIGNAL,
    STAGE_CONFIDENTIALITY_REVIEW,
    STAGE_ELIGIBILITY_CHECK,
    STAGE_MINIMIZATION,
    STAGE_PERSONAL_INFORMATION_REVIEW,
    STAGE_REJECTED,
    ZONE_ORGANIZATION_PRIVATE,
    ZONE_PROJECT_PRIVATE,
    ZONE_SHARED_ARCHIOSK_IMPROVEMENT,
    advance_stage,
    create_contribution_request,
    decide_contribution,
)
from services.security_governance import SecurityGovernanceStore


class ContributionRequestLifecycleTests(unittest.TestCase):
    def test_new_request_starts_at_candidate_signal(self):
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="A reviewer correction pattern.", requested_by="reviewer1",
        )
        self.assertEqual(request.current_stage, STAGE_CANDIDATE_SIGNAL)
        self.assertEqual(request.completed_stages, [])

    def test_invalid_zone_is_rejected(self):
        with self.assertRaises(LearningGovernanceError):
            create_contribution_request(
                project_id="p1", source_zone="not_a_zone", target_zone=ZONE_ORGANIZATION_PRIVATE,
                candidate_description="x", requested_by="reviewer1",
            )

    def test_approval_requires_every_review_stage_first(self):
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="x", requested_by="reviewer1",
        )
        with self.assertRaises(LearningGovernanceError):
            decide_contribution(request, STAGE_APPROVED, decided_by="sec_officer", rationale="x")

    def test_approval_succeeds_once_all_required_stages_recorded(self):
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="x", requested_by="reviewer1",
        )
        for stage in (
            STAGE_AUTHORITY_CHECK, STAGE_ELIGIBILITY_CHECK, STAGE_CONFIDENTIALITY_REVIEW,
            STAGE_PERSONAL_INFORMATION_REVIEW, STAGE_MINIMIZATION,
        ):
            advance_stage(request, stage, actor="sec_officer")
        decide_contribution(request, STAGE_APPROVED, decided_by="sec_officer", rationale="Reviewed.")
        self.assertEqual(request.current_stage, STAGE_APPROVED)

    def test_rejection_does_not_require_all_stages(self):
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="x", requested_by="reviewer1",
        )
        decide_contribution(request, STAGE_REJECTED, decided_by="sec_officer", rationale="Not eligible.")
        self.assertEqual(request.current_stage, STAGE_REJECTED)

    def test_shared_improvement_contribution_requires_separate_authority_from_requester(self):
        # "Shared contribution requires separate authority" (Part XVII) --
        # the requesting reviewer cannot also be the approver for a
        # SHARED_ARCHIOSK_IMPROVEMENT target.
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_ORGANIZATION_PRIVATE, target_zone=ZONE_SHARED_ARCHIOSK_IMPROVEMENT,
            candidate_description="x", requested_by="reviewer1",
        )
        for stage in (
            STAGE_AUTHORITY_CHECK, STAGE_ELIGIBILITY_CHECK, STAGE_CONFIDENTIALITY_REVIEW,
            STAGE_PERSONAL_INFORMATION_REVIEW, STAGE_MINIMIZATION,
        ):
            advance_stage(request, stage, actor="reviewer1")
        with self.assertRaises(LearningGovernanceError):
            decide_contribution(request, STAGE_APPROVED, decided_by="reviewer1", rationale="Self-approving.")

    def test_shared_improvement_can_be_approved_by_a_different_authority(self):
        request = create_contribution_request(
            project_id="p1", source_zone=ZONE_ORGANIZATION_PRIVATE, target_zone=ZONE_SHARED_ARCHIOSK_IMPROVEMENT,
            candidate_description="x", requested_by="reviewer1",
        )
        for stage in (
            STAGE_AUTHORITY_CHECK, STAGE_ELIGIBILITY_CHECK, STAGE_CONFIDENTIALITY_REVIEW,
            STAGE_PERSONAL_INFORMATION_REVIEW, STAGE_MINIMIZATION,
        ):
            advance_stage(request, stage, actor="reviewer1")
        decide_contribution(request, STAGE_APPROVED, decided_by="sec_officer", rationale="Approved by CISO.")
        self.assertEqual(request.current_stage, STAGE_APPROVED)


class ProjectPrivateVsOrganizationPrivateSeparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_learning_zones_"))
        self.store = SecurityGovernanceStore(self.tmp_dir)
        self.record = self.store.get()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_two_requests_for_the_same_project_stay_independently_tracked_per_target_zone(self):
        org_request = self.store.create_learning_contribution_request(
            self.record, project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="org-private candidate", requested_by="reviewer1",
        )
        shared_request = self.store.create_learning_contribution_request(
            self.record, project_id="p1", source_zone=ZONE_ORGANIZATION_PRIVATE,
            target_zone=ZONE_SHARED_ARCHIOSK_IMPROVEMENT, candidate_description="shared candidate",
            requested_by="reviewer1",
        )
        self.assertNotEqual(org_request["id"], shared_request["id"])
        self.assertEqual(org_request["target_zone"], ZONE_ORGANIZATION_PRIVATE)
        self.assertEqual(shared_request["target_zone"], ZONE_SHARED_ARCHIOSK_IMPROVEMENT)

    def test_approving_organization_private_request_does_not_touch_shared_request(self):
        org_request = self.store.create_learning_contribution_request(
            self.record, project_id="p1", source_zone=ZONE_PROJECT_PRIVATE, target_zone=ZONE_ORGANIZATION_PRIVATE,
            candidate_description="x", requested_by="reviewer1",
        )
        shared_request = self.store.create_learning_contribution_request(
            self.record, project_id="p1", source_zone=ZONE_ORGANIZATION_PRIVATE,
            target_zone=ZONE_SHARED_ARCHIOSK_IMPROVEMENT, candidate_description="y", requested_by="reviewer1",
        )
        for stage in (
            "authority_check", "eligibility_check", "confidentiality_review",
            "personal_information_review", "minimization_or_synthesis",
        ):
            self.store.advance_learning_contribution_stage(self.record, org_request["id"], stage, actor="reviewer1")
        self.store.decide_learning_contribution(
            self.record, org_request["id"], STAGE_APPROVED, decided_by="sec_officer", rationale="ok",
        )
        reloaded_shared = next(r for r in self.record.learning_contribution_requests if r["id"] == shared_request["id"])
        self.assertEqual(reloaded_shared["current_stage"], STAGE_CANDIDATE_SIGNAL)


class QualityRatingDoesNotImplyTrainingConsentTests(unittest.TestCase):
    """Part XI/XVII: structural (not runtime) proof -- no import edge
    exists between case_workspace.py's quality/validation machinery and
    this module, so there is no code path at all connecting a "Correct"
    ReviewerValidation to a learning contribution."""

    def test_case_workspace_does_not_import_learning_governance(self):
        source = Path("services/case_workspace.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
        self.assertNotIn("services.learning_governance", imported_modules)

    def test_learning_governance_does_not_import_case_workspace(self):
        source = Path("services/learning_governance.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)
        self.assertNotIn("services.case_workspace", imported_modules)

    def test_record_reviewer_validation_has_no_learning_contribution_side_effect(self):
        # Direct behavioral confirmation, not just the import-graph
        # check above: recording a "Correct" validation must not create
        # any LearningContributionRequest anywhere.
        import io
        import uuid
        from datetime import datetime, timezone
        from unittest.mock import patch

        import app as app_module
        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.case_workspace import AnalysisTrigger, CaseWorkspaceStore
        from services.environment_capabilities import CLIENT_OWNER
        from services.ingestion import ingest_upload
        from werkzeug.datastructures import FileStorage

        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_quality_no_training_"))
        try:
            flask_app = app_module.create_app("testing")
            flask_app.config["REGISTRY_STORE_PATH"] = str(tmp_dir)

            # CLAUDE-P32: deterministic, network-independent -- see
            # tests/test_security_enforcement.py's own spy pattern and
            # the CLAUDE-P31 8.5-hour live-API incident this convention
            # exists to prevent.
            def fake_parse(self_parser, raw_bytes, filename):
                return ParsedDocument(
                    project_id=str(uuid.uuid4()), filename=filename,
                    ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
                )

            with patch.object(BHiveParser, "parse", fake_parse):
                with flask_app.app_context():
                    document = ingest_upload(
                        FileStorage(stream=io.BytesIO(b"content"), filename="a.txt"), flask_app,
                        operating_environment=CLIENT_OWNER, owner="reviewer1", project_name="Quality No Training",
                    )
            store = CaseWorkspaceStore(tmp_dir)
            workspace = store.get(document.project_id)
            case = store.create_case(workspace, title="Case", objective="x", created_by="reviewer1")
            source = next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")
            trigger = AnalysisTrigger(trigger_type="user_initiated", triggered_by_actor="reviewer1")
            analysis = store.record_analysis(
                workspace, case_id=case["id"], source_ids=[source["id"]], objective="x",
                engine_name="test", engine_version="1.0",
                findings=[{"statement": "x", "machine_confidence": 0.9, "source_id": source["id"]}],
                trigger=trigger,
            )
            finding_id = analysis["finding_ids"][0]
            workspace = store.get(document.project_id)
            store.record_reviewer_validation(workspace, finding_id=finding_id, validation="Correct", reviewer="reviewer1")

            security_store = SecurityGovernanceStore(tmp_dir)
            record = security_store.get()
            self.assertEqual(record.learning_contribution_requests, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
