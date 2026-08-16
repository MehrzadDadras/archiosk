"""
Bounded GO QA/QC phase-aware pass - Document Context Claims (GO drafts ->
PM reviews/edits -> PM accepts), the Admin Document Mode quality gauge,
and RequirementPhaseAssessment (SOR Requirement + Current Phase
Expectation + Submitted Evidence -> Current Conformance Assessment).

Store-layer logic reuses evaluate_information_sufficiency/compare_maturity
unchanged (see services/case_workspace.py's own "Bounded GO QA/QC phase-
aware pass" section) - this file proves the NEW wiring around those
already-tested functions, not their own math (tests/test_foundation_
batch_e.py already covers that).

Hermetic per this repo's own CLAUDE.md rule: the one test that exercises
GO's real drafting path patches anthropic.Anthropic directly (never a
live call), matching tests/test_ca1d_composer_spine_stage1_schema.py's
own established pattern.

Run via:

    python -m unittest tests.test_go_qac_phase_aware_01 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_EDITED_AI_PROPOSAL,
    DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED,
    DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED,
    DOCUMENT_QUALITY_GAUGE_GOOD,
    DOCUMENT_QUALITY_GAUGE_REVIEW,
    DOCUMENT_QUALITY_GAUGE_WEAK,
    GO_QAC_PHASE_SOURCE_INFERRED,
    GO_QAC_PHASE_SOURCE_PROJECT_DEFINED,
    OBJECT_KIND_DISCIPLINE,
    OBJECT_KIND_REQUIREMENT,
    EXPECTED_KIND_DOCUMENT,
    PDF_CLASSIFICATION_IMAGE_ONLY,
    PDF_CLASSIFICATION_MIXED,
    PDF_CLASSIFICATION_TEXT_NATIVE,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    SUFFICIENCY_CONFLICTING,
    SUFFICIENCY_EXPECTED_AND_FOUND,
    SUFFICIENCY_EXPECTED_NOT_FOUND,
    SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE,
    SUFFICIENCY_NOT_EXPECTED_YET,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    assess_document_context_quality,
)


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class DocumentContextClaimStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="go_qac_claim_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-qac-claim")
        self.source = self.store.add_source(self.workspace, name="Spec.pdf", file_path="spec.pdf", kind="document")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_draft_starts_ai_proposed_and_proposed(self):
        claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "issuer", "Issued by ACME", created_by="GO",
        )
        self.assertEqual(claim["content_class"], CONTENT_CLASS_AI_PROPOSED)
        self.assertEqual(claim["original_statement"], claim["statement"])

    def test_accept_unchanged_preserves_content_class(self):
        claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "issuer", "Issued by ACME", created_by="GO",
        )
        reviewed = self.store.review_document_context_claim(
            self.workspace, claim["id"], actor="pm1", outcome=DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED,
        )
        self.assertEqual(reviewed["content_class"], CONTENT_CLASS_AI_PROPOSED)
        self.assertEqual(reviewed["review_state"], DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED)

    def test_accept_with_edit_promotes_content_class_and_preserves_original(self):
        claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "issuer", "Issued by ACME", created_by="GO",
        )
        reviewed = self.store.review_document_context_claim(
            self.workspace, claim["id"], actor="pm1",
            outcome=DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED, edited_statement="Issued by ACME Ltd.",
        )
        self.assertEqual(reviewed["content_class"], CONTENT_CLASS_EDITED_AI_PROPOSAL)
        self.assertEqual(reviewed["statement"], "Issued by ACME Ltd.")
        self.assertEqual(reviewed["original_statement"], "Issued by ACME")

    def test_reject_does_not_change_content_class(self):
        claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "purpose", "A guess", created_by="GO",
        )
        reviewed = self.store.review_document_context_claim(
            self.workspace, claim["id"], actor="pm1", outcome=DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED,
        )
        self.assertEqual(reviewed["review_state"], DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED)
        self.assertEqual(reviewed["content_class"], CONTENT_CLASS_AI_PROPOSED)

    def test_review_rejects_invalid_outcome(self):
        claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "purpose", "A guess", created_by="GO",
        )
        with self.assertRaises(CaseWorkspaceError):
            self.store.review_document_context_claim(
                self.workspace, claim["id"], actor="pm1", outcome="proposed",
            )

    def test_page_anchor_filters_correctly(self):
        doc_claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "purpose", "Doc-level", created_by="GO",
        )
        page_claim = self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "significance", "Page-level",
            created_by="GO", page_anchor={"page_number": 3},
        )
        doc_only = self.store.document_context_claims_for(self.workspace, self.source["id"], page_anchor=None)
        page_only = self.store.document_context_claims_for(
            self.workspace, self.source["id"], page_anchor={"page_number": 3},
        )
        self.assertEqual([c["id"] for c in doc_only], [doc_claim["id"]])
        self.assertEqual([c["id"] for c in page_only], [page_claim["id"]])

    def test_unknown_source_raises(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.draft_document_context_claim(
                self.workspace, "does-not-exist", "purpose", "x", created_by="GO",
            )

    def test_project_isolation_claims_not_visible_across_projects(self):
        self.store.draft_document_context_claim(
            self.workspace, self.source["id"], "purpose", "Project A claim", created_by="GO",
        )
        other_workspace = self.store.get_or_create("test-project-qac-other")
        self.assertEqual(other_workspace.document_context_claims, [])


class DocumentQualityGaugeTests(unittest.TestCase):
    def test_no_claims_is_review_not_weak_or_good(self):
        result = assess_document_context_quality([])
        self.assertEqual(result["gauge"], DOCUMENT_QUALITY_GAUGE_REVIEW)
        self.assertIsNone(result["possible_cause"])

    def test_all_accepted_unchanged_no_extraction_problem_is_good(self):
        claims = [
            {"content_class": CONTENT_CLASS_AI_PROPOSED, "review_state": DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED}
            for _ in range(3)
        ]
        result = assess_document_context_quality(claims, extraction_signal=PDF_CLASSIFICATION_TEXT_NATIVE)
        self.assertEqual(result["gauge"], DOCUMENT_QUALITY_GAUGE_GOOD)
        self.assertIsNone(result["possible_cause"])

    def test_all_rejected_is_weak_with_real_cause(self):
        claims = [
            {"content_class": CONTENT_CLASS_AI_PROPOSED, "review_state": DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED}
            for _ in range(2)
        ]
        result = assess_document_context_quality(claims)
        self.assertEqual(result["gauge"], DOCUMENT_QUALITY_GAUGE_WEAK)
        self.assertIsNotNone(result["possible_cause"])
        self.assertIn("investigate", result["possible_cause"].lower())

    def test_image_only_source_surfaces_a_grounded_possible_cause(self):
        claims = [
            {"content_class": CONTENT_CLASS_AI_PROPOSED, "review_state": DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED},
        ]
        result = assess_document_context_quality(claims, extraction_signal=PDF_CLASSIFICATION_IMAGE_ONLY)
        # Weak signal surfaces investigation cue without claiming false certainty -
        # gauge degrades from Good and a real, evidenced cause is given, never invented.
        self.assertNotEqual(result["gauge"], DOCUMENT_QUALITY_GAUGE_GOOD)
        self.assertIn("scan", result["possible_cause"].lower())

    def test_good_gauge_never_carries_a_possible_cause(self):
        claims = [
            {"content_class": CONTENT_CLASS_AI_PROPOSED, "review_state": DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED},
        ]
        result = assess_document_context_quality(claims)
        if result["gauge"] == DOCUMENT_QUALITY_GAUGE_GOOD:
            self.assertIsNone(result["possible_cause"])


class ExtractionSignalDerivationTests(unittest.TestCase):
    """Proves the signal is RE-DERIVED from already-persisted MM2 records,
    never a second write path - register_pdf_page_structure itself is
    completely unmodified by this pass."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="go_qac_signal_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-qac-signal")
        self.source = self.store.add_source(self.workspace, name="Scan.pdf", file_path="scan.pdf", kind="document")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_structure_registered_yet_is_none(self):
        self.assertIsNone(self.store.extraction_signal_for_source(self.workspace, self.source["id"]))

    def test_text_native_matches_registration_classification(self):
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages=["Real text."])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_TEXT_NATIVE)
        self.assertEqual(
            self.store.extraction_signal_for_source(self.workspace, self.source["id"]),
            PDF_CLASSIFICATION_TEXT_NATIVE,
        )

    def test_image_only_matches_registration_classification(self):
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages=["", ""])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_IMAGE_ONLY)
        self.assertEqual(
            self.store.extraction_signal_for_source(self.workspace, self.source["id"]),
            PDF_CLASSIFICATION_IMAGE_ONLY,
        )

    def test_mixed_matches_registration_classification(self):
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages=["Real text.", ""])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_MIXED)
        self.assertEqual(
            self.store.extraction_signal_for_source(self.workspace, self.source["id"]),
            PDF_CLASSIFICATION_MIXED,
        )


class RequirementPhaseAssessmentTests(unittest.TestCase):
    """Section 12's core validation list: #7 phase represented, #8
    Expected-later vs Below-phase-expectation distinguished, #9 missing
    evidence != automatic Nonconforming, #10 project-defined overrides
    generic assumption."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="go_qac_phase_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-qac-phase")
        self.source = self.store.add_source(self.workspace, name="Spec.pdf", file_path="spec.pdf", kind="document")
        self.requirement = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="1.1",
            text_reference="The roof shall have a slope of at least 2%.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
            subject_domain="Structural",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_project_profile_is_inferred_phase_source(self):
        # #10 (inverse case): with no project-defined profile at all,
        # the assessment honestly marks itself inferred/secondary.
        result = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[], created_by="GO",
        )
        self.assertEqual(result["phase_source"], GO_QAC_PHASE_SOURCE_INFERRED)
        self.assertIsNone(result["expectation_item_id"])

    def test_missing_evidence_is_expected_not_found_never_conflicting(self):
        # #9: absence of evidence must never collapse into a conflict/
        # nonconformance outcome - it is its own distinct state.
        result = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[], created_by="GO",
        )
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTED_NOT_FOUND)
        self.assertNotEqual(result["outcome"], SUFFICIENCY_CONFLICTING)

    def test_project_defined_profile_overrides_generic_assumption(self):
        # #10: once the project defines a real expectation, it is used -
        # subject_domain "Structural" matches scope_id "structural"
        # case-insensitively.
        self.store.record_design_maturity(
            self.workspace, OBJECT_KIND_DISCIPLINE, "structural", "schematic", created_by="pm1",
        )
        profile = self.store.create_expected_information_profile(
            self.workspace, title="Structural expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="structural", created_by="pm1",
        )
        self.store.add_expectation_item(
            self.workspace, profile["id"], expected_kind=EXPECTED_KIND_DOCUMENT,
            description="Structural calcs", created_by="pm1", expected_maturity="design_development",
            related_object_type=OBJECT_KIND_REQUIREMENT, related_object_id=self.requirement["id"],
        )
        result = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[{"resolution_level": "concept"}], created_by="GO",
        )
        self.assertEqual(result["phase_source"], GO_QAC_PHASE_SOURCE_PROJECT_DEFINED)
        self.assertIsNotNone(result["expectation_item_id"])

    def test_expected_later_and_below_phase_expectation_are_distinguishable(self):
        # #8: the two outcomes must remain distinct - "not yet due"
        # (Expected later) is never conflated with "found but the wrong
        # stage" (Below phase expectation).
        self.store.record_design_maturity(
            self.workspace, OBJECT_KIND_DISCIPLINE, "structural", "schematic", created_by="pm1",
        )
        profile = self.store.create_expected_information_profile(
            self.workspace, title="Structural expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="structural", created_by="pm1",
        )
        self.store.add_expectation_item(
            self.workspace, profile["id"], expected_kind=EXPECTED_KIND_DOCUMENT,
            description="Structural calcs", created_by="pm1", expected_maturity="design_development",
            related_object_type=OBJECT_KIND_REQUIREMENT, related_object_id=self.requirement["id"],
        )
        below_expectation = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[{"resolution_level": "concept"}], created_by="GO",
        )
        sufficient = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[{"resolution_level": "design_development"}], created_by="GO",
        )
        self.assertEqual(below_expectation["outcome"], SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE)
        self.assertEqual(sufficient["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        self.assertNotEqual(below_expectation["outcome"], sufficient["outcome"])

    def test_trajectory_is_full_append_only_history(self):
        # #3: 30%->60%->90%->IFC trajectory preservation - every
        # assessment stays, in order, nothing overwritten.
        first = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[], created_by="GO",
        )
        second = self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[{"resolution_level": "concept"}], created_by="GO",
        )
        history = self.store.requirement_phase_assessments_for(self.workspace, self.requirement["id"])
        self.assertEqual([h["id"] for h in history], [first["id"], second["id"]])
        self.assertEqual(
            self.store.latest_requirement_phase_assessment_for(self.workspace, self.requirement["id"])["id"],
            second["id"],
        )

    def test_unknown_requirement_raises(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.assess_requirement_phase_conformance(
                self.workspace, "does-not-exist", observed=[], created_by="GO",
            )

    def test_never_writes_a_requirement_adjudication(self):
        # Section 8/governance: a GO phase assessment must never become a
        # RequirementAdjudication on its own - only the pre-existing,
        # unmodified human adjudication route does that.
        self.store.assess_requirement_phase_conformance(
            self.workspace, self.requirement["id"], observed=[], created_by="GO",
        )
        self.assertEqual(self.workspace.requirement_adjudications, [])


class DraftDocumentContextClaimsIntelligenceTests(unittest.TestCase):
    """The one hermetic AI-call test - GO drafting Document Context claims
    from real (fixture) evidence text. Never calls the real Anthropic API
    (patch("anthropic.Anthropic"), matching this repo's own established
    pattern)."""

    def test_go_can_draft_from_evidence_with_directly_evidenced_vs_inferred_distinguishable(self):
        from services.document_context_intelligence import draft_document_context_claims

        fake_response = _mock_response(
            '[{"field_kind": "issuer", "statement": "Issued by ACME Engineering", '
            '"directly_evidenced": true}, '
            '{"field_kind": "significance", "statement": "Appears to govern roof design", '
            '"directly_evidenced": false}]'
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = fake_response
            result = draft_document_context_claims("Spec.pdf", "Issued by ACME Engineering, Rev 2.")

        self.assertTrue(result["ran"])
        self.assertEqual(len(result["claims"]), 2)
        evidenced = [c for c in result["claims"] if c["directly_evidenced"]]
        inferred = [c for c in result["claims"] if not c["directly_evidenced"]]
        self.assertEqual(len(evidenced), 1)
        self.assertEqual(len(inferred), 1)
        self.assertNotEqual(evidenced[0]["statement"], inferred[0]["statement"])

    def test_no_evidence_text_never_fabricates_a_claim(self):
        from services.document_context_intelligence import draft_document_context_claims
        result = draft_document_context_claims("Spec.pdf", "")
        self.assertFalse(result["ran"])
        self.assertEqual(result["claims"], [])
        self.assertIsNotNone(result["skipped_reason"])

    def test_no_api_key_degrades_honestly_never_fabricates(self):
        from services.document_context_intelligence import draft_document_context_claims
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            import os
            old = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                result = draft_document_context_claims("Spec.pdf", "Real evidence text here.")
            finally:
                if old is not None:
                    os.environ["ANTHROPIC_API_KEY"] = old
        self.assertFalse(result["ran"])
        self.assertEqual(result["claims"], [])


class AdminDocumentModeRouteTests(unittest.TestCase):
    """Section 12 #5/#11: Admin mode shows restrained quality signals;
    normal user-facing document mode stays uncluttered. #12: project
    isolation/governance untouched (routes reuse the existing
    _load_workspace_or_404/admin_required machinery, nothing new)."""

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="go_qac_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-qac-route"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(self.project_id)
        # CLAUDE-P32 project-level access: a non-admin session needs real
        # project membership to pass _load_workspace_or_404 - matching
        # tests/test_requirement_promotion.py's own route-test setUp.
        store.set_project_owner(workspace, owner="tester", actor="tester")
        self.source = store.add_source(workspace, name="Spec.pdf", file_path="spec.pdf", kind="document")
        store.draft_document_context_claim(
            workspace, self.source["id"], "issuer", "Issued by ACME", created_by="GO",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = role
        return client

    def _workspace_url(self):
        return f"/projects/{self.project_id}/workspace?source={self.source['id']}"

    def test_admin_sees_admin_document_mode_panel(self):
        response = self._client_as("admin").get(self._workspace_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"admin-document-mode-panel", response.data)
        self.assertIn(b"Issued by ACME", response.data)

    def test_ordinary_reviewer_never_sees_admin_document_mode_panel(self):
        response = self._client_as("read_only").get(self._workspace_url())
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"admin-document-mode-panel", response.data)
        # The pre-existing, ordinary, purely-human Document Context panel
        # must still render identically either way.
        self.assertIn(b"document-context-panel", response.data)

    def test_ordinary_reviewer_cannot_reach_review_route(self):
        client = self._client_as("read_only")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        claim_id = workspace.document_context_claims[0]["id"]
        response = client.post(
            f"/projects/{self.project_id}/workspace/document-context-claims/{claim_id}/review",
            data={"outcome": "accepted", "source_id": self.source["id"]},
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_can_review_a_claim_via_the_route(self):
        client = self._client_as("admin")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        claim_id = workspace.document_context_claims[0]["id"]
        response = client.post(
            f"/projects/{self.project_id}/workspace/document-context-claims/{claim_id}/review",
            data={"outcome": "accepted", "source_id": self.source["id"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = CaseWorkspaceStore(self.tmp_dir).get(self.project_id)
        self.assertEqual(workspace.document_context_claims[0]["review_state"], "accepted")

    def test_draft_route_honest_failure_with_no_api_key_configured(self):
        # Hermetic: no anthropic patch here on purpose - proves the route
        # degrades honestly (flash + redirect, no claim fabricated) when
        # this test environment has no real ANTHROPIC_API_KEY, rather than
        # asserting anything about a live call.
        client = self._client_as("admin")
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}, clear=False):
            import os
            old = os.environ.pop("ANTHROPIC_API_KEY", None)
            try:
                response = client.post(
                    f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/document-context-claims/draft",
                    data={}, follow_redirects=True,
                )
            finally:
                if old is not None:
                    os.environ["ANTHROPIC_API_KEY"] = old
        self.assertEqual(response.status_code, 200)
        workspace = CaseWorkspaceStore(self.tmp_dir).get(self.project_id)
        # Still exactly the one claim seeded in setUp - nothing fabricated.
        self.assertEqual(len(workspace.document_context_claims), 1)


if __name__ == "__main__":
    unittest.main()
