"""Focused acceptance for CODEX-HELIX-QA-ABSORPTION-01."""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import CaseWorkspaceStore, SPIN_KIND_FIRST
from services.spin import _build_prompt, _parse_helix_assessments


def _item(**overrides):
    item = {
        "interface": "Main shaft / opening / riser",
        "spin_axis": "horizontal",
        "strands": ["Architecture", "Structure", "Mechanical"],
        "claimed_maturity": "DD package",
        "maturity_source": "Project QA plan section 4",
        "expectation_state": "mandatory_stage_fit",
        "expectation_rationale": "Primary interfaces are required in this package.",
        "dimension_relationship_class": "exact_fit",
        "observed_evidence": [{
            "source_reference": "S-103 sheet 3",
            "revision": "Rev 2",
            "region": "opening note 4",
            "observed_value": "2000 mm",
            "confidence": "direct",
        }],
        "assessment": "dimension_conflict",
        "consequence": "The evidenced riser may not fit.",
        "uncertainty": "A later structural issue may exist outside the corpus.",
        "evidence_sufficiency": "directly_supportable",
        "follow_on_game": "Revision Propagation Game",
        "governed_question": "Has the later opening requirement been incorporated?",
    }
    item.update(overrides)
    return item


class HelixAssessmentParsingTests(unittest.TestCase):
    def test_asserting_assessment_without_observed_evidence_is_dropped(self):
        for assessment in (
            "converged", "dimension_conflict", "positional_conflict",
            "semantic_mismatch", "handshake_deficit", "propagation_lag",
            "stage_maturity_mismatch",
        ):
            self.assertEqual(
                _parse_helix_assessments([_item(assessment=assessment, observed_evidence=[])]),
                [],
                assessment,
            )

    def test_asserting_assessment_with_missing_evidence_key_is_dropped(self):
        item = _item(assessment="converged")
        item.pop("observed_evidence")
        self.assertEqual(_parse_helix_assessments([item]), [])

    def test_asserting_assessment_with_insufficient_evidence_type_is_dropped(self):
        self.assertEqual(_parse_helix_assessments([_item(
            assessment="converged", evidence_sufficiency="evidence_type_insufficient",
        )]), [])

    def test_abstaining_assessments_may_remain_evidence_free(self):
        for assessment in ("evidence_unavailable", "residual_ambiguity", "legitimate_deferred"):
            parsed = _parse_helix_assessments([_item(assessment=assessment, observed_evidence=[])])
            self.assertEqual(len(parsed), 1, assessment)
            self.assertEqual(parsed[0]["assessment"], assessment)

    def test_asserting_assessment_with_real_evidence_is_retained(self):
        parsed = _parse_helix_assessments([_item(assessment="converged")])
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["assessment"], "converged")

    def test_mandatory_conflict_retains_dimension_and_revision_provenance(self):
        result = _parse_helix_assessments([_item()])
        self.assertEqual(result[0]["expectation_state"], "mandatory_stage_fit")
        self.assertEqual(result[0]["assessment"], "dimension_conflict")
        self.assertEqual(result[0]["dimension_relationship_class"], "exact_fit")
        self.assertEqual(result[0]["observed_evidence"][0]["revision"], "Rev 2")
        self.assertEqual(result[0]["observed_evidence"][0]["source_reference"], "S-103 sheet 3")

    def test_legitimate_early_stage_looseness_is_not_converted_to_failure(self):
        result = _parse_helix_assessments([_item(
            expectation_state="planned_deferred", assessment="legitimate_deferred",
            claimed_maturity="concept design", dimension_relationship_class="envelope_reservation",
        )])
        self.assertEqual(result[0]["assessment"], "legitimate_deferred")
        self.assertEqual(result[0]["expectation_state"], "planned_deferred")

    def test_missing_dependent_strand_differs_from_legitimate_deferral(self):
        missing = _parse_helix_assessments([_item(
            assessment="evidence_unavailable", observed_evidence=[],
        )])[0]
        deferred = _parse_helix_assessments([_item(
            expectation_state="planned_deferred", assessment="legitimate_deferred",
        )])[0]
        self.assertNotEqual(missing["assessment"], deferred["assessment"])
        self.assertNotEqual(missing["expectation_state"], deferred["expectation_state"])

    def test_horizontal_longitudinal_and_both_are_distinguishable(self):
        result = _parse_helix_assessments([
            _item(spin_axis="horizontal"),
            _item(interface="RFP to current room programme", spin_axis="longitudinal"),
            _item(interface="Changed door/security interface", spin_axis="both"),
        ])
        self.assertEqual([r["spin_axis"] for r in result], ["horizontal", "longitudinal", "both"])

    def test_evidence_type_insufficiency_preserves_uncertainty(self):
        result = _parse_helix_assessments([_item(
            assessment="evidence_unavailable",
            evidence_sufficiency="evidence_type_insufficient",
            uncertainty="Compound 3D geometry requires an IFC/model source.",
        )])[0]
        self.assertEqual(result["evidence_sufficiency"], "evidence_type_insufficient")
        self.assertIn("IFC", result["uncertainty"])

    def test_unknown_model_vocabularies_are_rejected_not_promoted(self):
        self.assertEqual(_parse_helix_assessments([_item(assessment="health_score_82")]), [])
        parsed = _parse_helix_assessments([_item(dimension_relationship_class="always_structure_wins")])
        self.assertIsNone(parsed[0]["dimension_relationship_class"])


class HelixPromptTests(unittest.TestCase):
    def test_prompt_uses_project_context_and_rejects_universal_rules(self):
        prompt = _build_prompt(
            SPIN_KIND_FIRST, "rfp.pdf", [], [], [],
            maturity_context=[{"scope_type": "discipline", "scope_id": "Structure", "value": "IFC", "effective_at": "2026-08-01", "status": "active"}],
            expectation_context=[{"scope_type": "discipline", "scope_id": "Structure", "description": "Primary openings", "expected_maturity": "IFC", "status": "active"}],
        )
        self.assertIn("Project-recorded maturity context", prompt)
        self.assertIn("Structure = IFC", prompt)
        self.assertIn("planned deferral is not failure", prompt)
        self.assertIn("evidence_type_insufficient", prompt)
        self.assertIn("never universal LOD/tolerance rules", prompt)
        self.assertNotIn("30% = LOD 200", prompt)
        self.assertNotIn("Structure > Mechanical", prompt)
        self.assertNotIn("Helix Health Score", prompt)


class HelixPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="helix_qa_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("helix-project")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_assessment_persists_on_originating_spin_run(self):
        assessment = _parse_helix_assessments([_item()])[0]
        run = self.store.record_spin_run(
            self.workspace, spin_kind=SPIN_KIND_FIRST, actor="owner",
            findings=[], source_signature="", helix_assessments=[assessment],
        )
        self.assertEqual(run["helix_assessments"][0]["interface"], assessment["interface"])
        reloaded = self.store.get("helix-project")
        self.assertEqual(reloaded.spin_runs[0]["helix_assessments"][0]["spin_axis"], "horizontal")


if __name__ == "__main__":
    unittest.main()
