"""
Foundation Batch E (Prompt 12) tests: ExpectedInformationProfile,
ExpectationItem, DesignMaturity/EstimateMaturity, and the derived
Observed-vs-Expected Information Sufficiency evaluator.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    EXPECTATION_BINDINGNESS_EXPECTED,
    EXPECTATION_BINDINGNESS_INFERRED,
    EXPECTATION_BINDINGNESS_MANDATORY,
    EXPECTATION_ITEM_STATUS_NOT_APPLICABLE,
    MATURITY_TYPE_DESIGN,
    MATURITY_TYPE_ESTIMATE,
    OBJECT_KIND_DISCIPLINE,
    OBJECT_KIND_PACKAGE,
    OBJECT_KIND_PROJECT,
    PROFILE_STATUS_ACTIVE,
    PROFILE_STATUS_SUPERSEDED,
    SUFFICIENCY_AUTHORITY_OR_VERSION_UNCERTAIN,
    SUFFICIENCY_CONFLICTING,
    SUFFICIENCY_EXPECTATION_MAY_NOT_APPLY,
    SUFFICIENCY_EXPECTED_AND_FOUND,
    SUFFICIENCY_EXPECTED_NOT_FOUND,
    SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE,
    SUFFICIENCY_INACCESSIBLE,
    SUFFICIENCY_NOT_EXPECTED_YET,
    SUFFICIENCY_SUPERSEDED,
    TEMPORAL_CONDITION_NOT_YET_DUE,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    compare_maturity,
    evaluate_information_sufficiency,
)
from services.governance import GovernanceLog


class ExpectedInformationProfileTests(unittest.TestCase):
    """Tests A, B, E, P."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_e_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-e1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # A
    def test_a_expected_information_profile_creation(self):
        profile = self.store.create_expected_information_profile(
            self.workspace, title="Architecture expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="architecture", created_by="tester", governance_log=self.gov,
        )
        self.assertEqual(profile["status"], PROFILE_STATUS_ACTIVE)
        self.assertEqual(profile["scope_type"], OBJECT_KIND_DISCIPLINE)
        item = self.store.add_expectation_item(
            self.workspace, profile_id=profile["id"], expected_kind="document",
            description="Developed floor plans", created_by="tester",
            bindingness=EXPECTATION_BINDINGNESS_EXPECTED, expected_maturity="design_development",
        )
        self.assertEqual(item["bindingness"], EXPECTATION_BINDINGNESS_EXPECTED)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "expected_information_profile_created"]
        self.assertEqual(len(events), 1)

    # B
    def test_b_multiple_scoped_profiles_within_one_project(self):
        arch = self.store.create_expected_information_profile(
            self.workspace, title="Architecture", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="architecture", created_by="tester",
        )
        struct = self.store.create_expected_information_profile(
            self.workspace, title="Structure", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="structure", created_by="tester",
        )
        project_wide = self.store.create_expected_information_profile(
            self.workspace, title="Project-wide estimating expectations", scope_type=OBJECT_KIND_PROJECT,
            scope_id=self.project_id, created_by="tester",
        )
        self.assertEqual(len(self.store.profiles_for_scope(self.workspace, OBJECT_KIND_DISCIPLINE, "architecture")), 1)
        self.assertEqual(len(self.store.profiles_for_scope(self.workspace, OBJECT_KIND_DISCIPLINE, "structure")), 1)
        self.assertEqual(len(self.store.profiles_for_project(self.workspace)), 3)
        self.assertNotEqual(arch["id"], struct["id"])
        self.assertNotEqual(struct["id"], project_wide["id"])

    # E
    def test_e_mandatory_vs_expected_vs_inferred_authority(self):
        profile = self.store.create_expected_information_profile(
            self.workspace, title="Estimating", scope_type=OBJECT_KIND_PROJECT,
            scope_id=self.project_id, created_by="tester",
        )
        mandatory_item = self.store.add_expectation_item(
            self.workspace, profile_id=profile["id"], expected_kind="document",
            description="Current cost estimate", created_by="tester",
            bindingness=EXPECTATION_BINDINGNESS_MANDATORY, authority_source="contract_clause_7.2",
        )
        inferred_item = self.store.add_expectation_item(
            self.workspace, profile_id=profile["id"], expected_kind="analysis",
            description="A benchmark comparison would typically help here", created_by="tester",
            bindingness=EXPECTATION_BINDINGNESS_INFERRED, authority_source="machine_inferred",
        )
        self.assertEqual(mandatory_item["bindingness"], EXPECTATION_BINDINGNESS_MANDATORY)
        self.assertEqual(inferred_item["bindingness"], EXPECTATION_BINDINGNESS_INFERRED)
        # A machine-inferred expectation must never present the same
        # strength as a contractual one - distinct, unequal values.
        self.assertNotEqual(mandatory_item["bindingness"], inferred_item["bindingness"])

    # P
    def test_p_project_specific_expectation_supersedes_generic_default(self):
        default_profile = self.store.create_expected_information_profile(
            self.workspace, title="Default estimating expectations", scope_type=OBJECT_KIND_PROJECT,
            scope_id=self.project_id, created_by="beehive-default",
        )
        self.store.add_expectation_item(
            self.workspace, profile_id=default_profile["id"], expected_kind="document",
            description="Estimate expected at every major design milestone including 60%",
            created_by="beehive-default", bindingness=EXPECTATION_BINDINGNESS_EXPECTED,
        )

        new_profile, supersession = self.store.revise_expected_information_profile(
            self.workspace, profile_id=default_profile["id"], actor="design_manager",
            reason="This project issues estimates only at Proposal, 75%, and IFC.",
            authority_class="design_manager_override",
            new_items=[],
            governance_log=self.gov,
        )
        self.store.add_expectation_item(
            self.workspace, profile_id=new_profile["id"], expected_kind="document",
            description="Estimate expected at Proposal, 75%, and IFC only",
            created_by="design_manager", bindingness=EXPECTATION_BINDINGNESS_MANDATORY,
            authority_source="design_manager_directive",
        )

        reloaded = self.store.get(self.project_id)
        old_profile = self.store._find(reloaded.expected_information_profiles, default_profile["id"])
        self.assertEqual(old_profile["status"], PROFILE_STATUS_SUPERSEDED)
        # The original default expectation remains historically present, not deleted.
        self.assertTrue(len(old_profile["items"]) >= 1)

        active = self.store.profiles_for_scope(self.workspace, OBJECT_KIND_PROJECT, self.project_id)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["id"], new_profile["id"])

        lineage = self.store.supersessions_for(reloaded, "expected_information_profile", default_profile["id"])
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["reason"], "This project issues estimates only at Proposal, 75%, and IFC.")


class MaturityTests(unittest.TestCase):
    """Tests C, D, Q, R."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_e_maturity_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-e2"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # C
    def test_c_design_maturity_open_world_behavior(self):
        known = self.store.record_design_maturity(
            self.workspace, scope_type=OBJECT_KIND_DISCIPLINE, scope_id="architecture",
            value="Design_Development", created_by="tester",  # spelling drift on a known value
        )
        self.assertEqual(known["value"], "design_development")  # normalized

        custom = self.store.record_design_maturity(
            self.workspace, scope_type=OBJECT_KIND_DISCIPLINE, scope_id="mechanical",
            value="Integrated Systems Gate B", created_by="tester",  # unrecognized, project-specific
        )
        self.assertEqual(custom["value"], "Integrated Systems Gate B")  # preserved verbatim, not coerced

    # D
    def test_d_estimate_maturity_independent_of_design_maturity(self):
        self.store.record_design_maturity(
            self.workspace, scope_type=OBJECT_KIND_PROJECT, scope_id=self.project_id,
            value="design_development", created_by="tester",  # 30%-ish equivalent
        )
        self.store.record_estimate_maturity(
            self.workspace, scope_type=OBJECT_KIND_PROJECT, scope_id=self.project_id,
            value="elemental", created_by="tester",
        )
        design = self.store.maturity_for_scope(self.workspace, MATURITY_TYPE_DESIGN, OBJECT_KIND_PROJECT, self.project_id)
        estimate = self.store.maturity_for_scope(self.workspace, MATURITY_TYPE_ESTIMATE, OBJECT_KIND_PROJECT, self.project_id)
        self.assertEqual(design["value"], "design_development")
        self.assertEqual(estimate["value"], "elemental")
        self.assertNotEqual(design["maturity_type"], estimate["maturity_type"])

        # Revising one dimension must never touch the other.
        self.store.revise_maturity(self.workspace, design["id"], "tender", actor="tester")
        reloaded = self.store.get(self.project_id)
        estimate_after = self.store.maturity_for_scope(reloaded, MATURITY_TYPE_ESTIMATE, OBJECT_KIND_PROJECT, self.project_id)
        self.assertEqual(estimate_after["value"], "elemental")  # unchanged

    # Q
    def test_q_package_discipline_maturities_differ_within_same_project(self):
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "architecture", "design_development", "tester")
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "structure", "issued_for_construction", "tester")
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "mechanical", "schematic", "tester")
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_PACKAGE, "early-works", "issued_for_construction", "tester")

        arch = self.store.maturity_for_scope(self.workspace, MATURITY_TYPE_DESIGN, OBJECT_KIND_DISCIPLINE, "architecture")
        structure = self.store.maturity_for_scope(self.workspace, MATURITY_TYPE_DESIGN, OBJECT_KIND_DISCIPLINE, "structure")
        mechanical = self.store.maturity_for_scope(self.workspace, MATURITY_TYPE_DESIGN, OBJECT_KIND_DISCIPLINE, "mechanical")
        self.assertNotEqual(arch["value"], structure["value"])
        self.assertNotEqual(structure["value"], mechanical["value"])
        # No single global project maturity exists anywhere in this model.

    # R
    def test_r_unknown_custom_maturity_does_not_force_known_profile(self):
        result = compare_maturity("Integrated Systems Gate B", "design_development")
        self.assertIsNone(result)  # honest "cannot determine", not a guessed ordering
        result2 = compare_maturity("schematic", "tender")
        self.assertEqual(result2, -1)  # both known - real comparison


class InformationSufficiencyEvaluatorTests(unittest.TestCase):
    """Tests F, G, H, I, J, K, L, M, N, O, S - pure evaluator tests, no store needed."""

    def _item(self, **overrides):
        base = {
            "id": "item-1", "expected_kind": "document", "description": "x",
            "status": "active", "expected_maturity": None, "bindingness": "expected",
        }
        base.update(overrides)
        return base

    # G
    def test_g_expected_and_found(self):
        item = self._item(expected_maturity="design_development")
        observed = [{"object_type": "source", "object_id": "s1", "resolution_level": "tender"}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)

    # H
    def test_h_expected_not_found(self):
        item = self._item()
        result = evaluate_information_sufficiency(item, observed=[])
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTED_NOT_FOUND)

    # I / Case B from Prompt 12 sec 9 (late-stage under-resolution)
    def test_i_found_but_insufficient_for_stage(self):
        item = self._item(description="Facade system definition", expected_maturity="issued_for_construction")
        observed = [{"object_type": "source", "object_id": "s1", "resolution_level": "concept"}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE)

    # F / Case A from Prompt 12 sec 9 (appropriate early uncertainty)
    def test_f_case_a_appropriate_early_uncertainty_is_not_flagged(self):
        item = self._item(description="Mechanical system narrative", expected_maturity="schematic")
        observed = [{"object_type": "source", "object_id": "s1", "resolution_level": "schematic"}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)  # not flagged merely for being early-stage

    # J
    def test_j_not_expected_yet(self):
        item = self._item()
        result = evaluate_information_sufficiency(item, observed=[], milestone_condition=TEMPORAL_CONDITION_NOT_YET_DUE)
        self.assertEqual(result["outcome"], SUFFICIENCY_NOT_EXPECTED_YET)

    # K
    def test_k_not_applicable_expectation(self):
        item = self._item(status=EXPECTATION_ITEM_STATUS_NOT_APPLICABLE)
        result = evaluate_information_sufficiency(item, observed=[])
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTATION_MAY_NOT_APPLY)

    # L
    def test_l_inaccessible_evidence(self):
        item = self._item()
        observed = [{"object_type": "source", "object_id": "s1", "accessible": False}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_INACCESSIBLE)

    # M
    def test_m_superseded_evidence(self):
        item = self._item()
        observed = [{"object_type": "source", "object_id": "s1", "superseded": True}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_SUPERSEDED)

    # N
    def test_n_conflicting_current_evidence(self):
        item = self._item()
        observed = [
            {"object_type": "source", "object_id": "s1", "conflicts": True},
            {"object_type": "source", "object_id": "s2", "conflicts": True},
        ]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_CONFLICTING)

    def test_authority_or_version_uncertain(self):
        item = self._item()
        observed = [{"object_type": "source", "object_id": "s1", "authority_confidence": "uncertain"}]
        result = evaluate_information_sufficiency(item, observed)
        self.assertEqual(result["outcome"], SUFFICIENCY_AUTHORITY_OR_VERSION_UNCERTAIN)

    # O / Test 20 - document found but expected internal information absent.
    # Modeled as TWO separate ExpectationItems for the same conceptual
    # "estimate" - a document-level item and a content-level item - rather
    # than special-casing "content within a document" in the evaluator.
    def test_o_document_found_but_expected_content_absent(self):
        document_item = self._item(id="doc-item", expected_kind="document", description="Current cost estimate")
        content_item = self._item(
            id="content-item", expected_kind="information_within_document",
            description="Basis of Estimate", related_object_type="source", related_object_id="estimate-rev4",
        )
        document_observed = [{"object_type": "source", "object_id": "estimate-rev4", "resolution_level": None}]
        content_observed = []  # the Basis of Estimate itself was never located

        doc_result = evaluate_information_sufficiency(document_item, document_observed)
        content_result = evaluate_information_sufficiency(content_item, content_observed)

        self.assertEqual(doc_result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        self.assertEqual(content_result["outcome"], SUFFICIENCY_EXPECTED_NOT_FOUND)

    # R (evaluator side) - indeterminate maturity comparison is flagged honestly, not silently resolved.
    def test_r_indeterminate_maturity_comparison_is_flagged_not_guessed(self):
        item = self._item(expected_maturity="Integrated Systems Gate B")  # unknown, project-specific
        observed = [{"object_type": "source", "object_id": "s1", "resolution_level": "schematic"}]  # known
        result = evaluate_information_sufficiency(item, observed)
        # A hard fact (something was found) is not overridden by an
        # indeterminate maturity comparison, but the indeterminacy is
        # honestly surfaced rather than silently resolved either way.
        self.assertEqual(result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        self.assertIn("indeterminate", result["detail"].get("maturity_comparison", ""))

    # S
    def test_s_legacy_project_without_profiles_still_loads(self):
        import json
        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_e_legacy_"))
        try:
            store = CaseWorkspaceStore(tmp_dir)
            legacy_project_id = "legacy-project-e"
            (tmp_dir / f"{legacy_project_id}.workspace.json").write_text(
                json.dumps({"project_id": legacy_project_id}), encoding="utf-8",
            )
            workspace = store.get(legacy_project_id)
            self.assertEqual(workspace.expected_information_profiles, [])
            self.assertEqual(workspace.maturity_records, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class DesignBuildStageAdjustedScenarioTest(unittest.TestCase):
    """The representative test from Prompt 12 sec 18: Architecture/Structure
    at 60%, Mechanical at 30%, an estimate stale relative to the 60%
    milestone - proving the shadow comparison without creating a Finding,
    Risk, Work Item, or ReviewThread."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_e_scenario_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-e3"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_stage_adjusted_design_build_comparison(self):
        # Current maturities.
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "architecture", "tender", "tester")
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "structure", "tender", "tester")
        self.store.record_design_maturity(self.workspace, OBJECT_KIND_DISCIPLINE, "mechanical", "schematic", "tester")
        self.store.record_estimate_maturity(self.workspace, OBJECT_KIND_PROJECT, self.project_id, "elemental", "tester")

        # Expected Information Profiles per discipline + project-wide estimating.
        arch_profile = self.store.create_expected_information_profile(
            self.workspace, title="Architecture expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="architecture", created_by="tester",
        )
        arch_item = self.store.add_expectation_item(
            self.workspace, profile_id=arch_profile["id"], expected_kind="document",
            description="Developed floor plans and major systems", created_by="tester",
            expected_maturity="tender",
        )

        struct_profile = self.store.create_expected_information_profile(
            self.workspace, title="Structure expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="structure", created_by="tester",
        )
        struct_item = self.store.add_expectation_item(
            self.workspace, profile_id=struct_profile["id"], expected_kind="document",
            description="Primary structural system and major foundation assumptions", created_by="tester",
            expected_maturity="tender",
        )

        mech_profile = self.store.create_expected_information_profile(
            self.workspace, title="Mechanical expectations", scope_type=OBJECT_KIND_DISCIPLINE,
            scope_id="mechanical", created_by="tester",
        )
        mech_item = self.store.add_expectation_item(
            self.workspace, profile_id=mech_profile["id"], expected_kind="document",
            description="System narrative / preliminary system basis", created_by="tester",
            expected_maturity="schematic",  # NOT final equipment selections - deliberately modest expectation
        )

        estimate_profile = self.store.create_expected_information_profile(
            self.workspace, title="Estimating expectations", scope_type=OBJECT_KIND_PROJECT,
            scope_id=self.project_id, created_by="tester",
        )
        estimate_item = self.store.add_expectation_item(
            self.workspace, profile_id=estimate_profile["id"], expected_kind="document",
            description="Current cost estimate reflecting post-60% design", created_by="tester",
            expected_maturity="tender",
        )

        # Observed reality.
        arch_result = evaluate_information_sufficiency(
            arch_item, observed=[{"object_type": "source", "object_id": "arch-60", "resolution_level": "tender"}],
        )
        struct_result = evaluate_information_sufficiency(
            struct_item, observed=[{"object_type": "source", "object_id": "struct-60", "resolution_level": "tender"}],
        )
        mech_result = evaluate_information_sufficiency(
            mech_item, observed=[{"object_type": "source", "object_id": "mech-narrative", "resolution_level": "schematic"}],
        )
        # Only the OLD 30%-basis estimate exists - its own resolution
        # level (tied to when it was produced) no longer matches what's
        # now expected post-60%-design.
        estimate_result = evaluate_information_sufficiency(
            estimate_item, observed=[{"object_type": "source", "object_id": "estimate-30", "resolution_level": "schematic"}],
        )

        self.assertEqual(arch_result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        self.assertEqual(struct_result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        # Mechanical is stage-appropriate DESPITE its lower design maturity -
        # not penalized for being at an earlier stage than Architecture/Structure.
        self.assertEqual(mech_result["outcome"], SUFFICIENCY_EXPECTED_AND_FOUND)
        # The stale estimate is recognized as insufficient for the current
        # (post-60%) expected state.
        self.assertEqual(estimate_result["outcome"], SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE)

        # No Finding, Risk, Work Item, or ReviewThread was created anywhere
        # in this workspace merely by running the comparison.
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.findings, [])
        self.assertEqual(reloaded.review_threads, [])
        self.assertEqual(reloaded.cases, [])


if __name__ == "__main__":
    unittest.main()
