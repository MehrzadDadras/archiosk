"""
Foundation Batch F (Prompt 15) tests: Source document identity/provenance
and the first-class Requirement primitive - built directly from the
NREOCRC Corpus State 001 gaps identified in Prompts 13/14.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    KNOWN_REQUIREMENT_CLASSIFICATIONS,
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_SOURCE,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    REQUIREMENT_CLASSIFICATION_INDICATIVE,
    REQUIREMENT_CLASSIFICATION_MANDATORY,
    REQUIREMENT_LOCATION_TYPE_FIGURE,
    REQUIREMENT_LOCATION_TYPE_SECTION,
    REQUIREMENT_LOCATION_TYPE_TABLE_ROW,
    REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_STATUS_ACTIVE,
    REQUIREMENT_STATUS_SUPERSEDED,
    SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    validate_requirement_location_citation,
)
from services.governance import GovernanceLog


class SourceIdentityTests(unittest.TestCase):
    """Tests A, B, C, D."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_f_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-f1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # A
    def test_a_source_with_full_document_identity(self):
        source = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001.md", file_path="/tmp/x.md",
            kind="owner_project_requirements",
            document_id="NREOCRC-OPR-001", revision="0", issue_date="2026-12-08",
            issuer="North River Infrastructure Corporation",
            document_status="ISSUED WITH RFP — CONTRACTUAL DOCUMENT",
            document_authority=DOCUMENT_AUTHORITY_CONTRACTUAL,
            file_hash="0109f49a8dc0bd75ab7612f87e5b23d4af8d129633c3815f8917e8fafb47ed6f",
            origin_type=SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
            origin_reference="tests/fixtures/nreocrc/immutable_original/NREOCRC-OPR-001.md",
            governance_log=self.gov, actor="tester",
        )
        self.assertEqual(source["document_id"], "NREOCRC-OPR-001")
        self.assertEqual(source["revision"], "0")
        self.assertEqual(source["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertEqual(source["origin_type"], SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "source_registered"]
        self.assertEqual(len(events), 1)

    # B
    def test_b_legacy_source_without_document_identity_loads(self):
        import json
        legacy_project_id = "legacy-project-f"
        legacy_source = {
            "id": "s1", "project_id": legacy_project_id, "kind": "drawing", "name": "old.png",
            "added_at": "2020-01-01T00:00:00+00:00", "file_path": "old.png", "width": 100, "height": 100,
        }
        (self.tmp_dir / f"{legacy_project_id}.workspace.json").write_text(
            json.dumps({"project_id": legacy_project_id, "sources": [legacy_source]}), encoding="utf-8",
        )
        workspace = self.store.get(legacy_project_id)
        self.assertEqual(workspace.sources[0]["name"], "old.png")
        # Nested dicts (unlike ProjectWorkspace itself) are never rehydrated
        # through the Source dataclass, so a genuinely legacy dict simply
        # lacks the key entirely - honest absence means `.get()` returns
        # None, not that the key silently appears. Bracket access would
        # KeyError, which is the correct, expected signal that this Source
        # predates the new fields.
        self.assertIsNone(workspace.sources[0].get("document_id"))
        self.assertIsNone(workspace.sources[0].get("file_hash"))

    # C
    def test_c_file_identity_distinct_from_document_identity(self):
        source = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001.md", file_path="/tmp/x.md",
            kind="owner_project_requirements", document_id="NREOCRC-OPR-001", revision="0",
        )
        # A later revision keeps the same document_id but is a different
        # file/name/hash entirely (Prompt 15 #3).
        source_rev1 = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001-rev1.md", file_path="/tmp/y.md",
            kind="owner_project_requirements", document_id="NREOCRC-OPR-001", revision="1",
            file_hash="different_hash_entirely",
        )
        self.assertEqual(source["document_id"], source_rev1["document_id"])
        self.assertNotEqual(source["name"], source_rev1["name"])
        self.assertNotEqual(source["revision"], source_rev1["revision"])

    # D
    def test_d_source_authority_preserved(self):
        source = self.store.add_source(
            self.workspace, name="x.md", file_path="/tmp/x.md", kind="owner_project_requirements",
            document_authority="Contractual",  # spelling drift on a known value
        )
        self.assertEqual(source["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)


class RequirementTests(unittest.TestCase):
    """Tests E, F, G, H, I, J, K, L, M, N, O, P, Q."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_f_req_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-f2"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001.md", file_path="/tmp/x.md",
            kind="owner_project_requirements", document_id="NREOCRC-OPR-001",
            document_authority=DOCUMENT_AUTHORITY_CONTRACTUAL,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # E, F
    def test_e_f_requirement_creation_and_stable_identity(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.1",
            text_reference="Standby power generation... no less than 96 hours without refuelling.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_MANDATORY,
            governance_log=self.gov,
        )
        self.assertTrue(req["id"])  # BEEHIVE's own stable internal id exists
        self.assertEqual(req["original_requirement_identifier"], "12.1")  # source's own numbering preserved
        self.assertNotEqual(req["id"], "12.1")  # the two identities are genuinely distinct
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "requirement_registered"]
        self.assertEqual(len(events), 1)

    # G
    def test_g_requirement_source_location_provenance(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.1",
            text_reference="96-hour standby operation", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            source_location={"location_type": "Section", "value": "12.1"},  # spelling drift, should normalize
        )
        self.assertEqual(req["source_location"]["location_type"], REQUIREMENT_LOCATION_TYPE_SECTION)
        self.assertEqual(req["source_location"]["value"], "12.1")

    # H
    def test_h_requirement_authority_distinct_from_source_authority(self):
        # Source is uniformly Contractual (set in setUp), but this specific
        # clause is Indicative - both must coexist without collapsing.
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="4.6",
            text_reference="Three preliminary site concepts... not required to adopt any Option.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_INDICATIVE,
        )
        reloaded = self.store.get(self.project_id)
        source_after = self.store._find(reloaded.sources, self.source["id"])
        self.assertEqual(source_after["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertEqual(req["classification"], REQUIREMENT_CLASSIFICATION_INDICATIVE)
        self.assertNotEqual(source_after["document_authority"], req["classification"])

    # I
    def test_i_mandatory_vs_indicative_classification(self):
        mandatory = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.1",
            text_reference="96-hour standby operation", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_MANDATORY,
        )
        indicative = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="4.6",
            text_reference="Preliminary site concepts", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_INDICATIVE,
        )
        self.assertNotEqual(mandatory["classification"], indicative["classification"])

    # J
    def test_j_unknown_project_specific_classification_preserved(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="X-1",
            text_reference="A project-specific classification not in the canonical set.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification="owner_reserved_special",
        )
        self.assertEqual(req["classification"], "owner_reserved_special")
        self.assertNotIn("owner_reserved_special", KNOWN_REQUIREMENT_CLASSIFICATIONS)

    # K
    def test_k_requirement_connected_to_table_evidence(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"],
            original_requirement_identifier="Appendix OPR-1 Row 20",
            text_reference="Situational Awareness / Media Briefing Room - bridges Secure and Controlled Zones.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            source_location={"location_type": "table_row", "table_id": "Appendix OPR-1", "row": 20},
        )
        self.assertEqual(req["source_location"]["location_type"], REQUIREMENT_LOCATION_TYPE_TABLE_ROW)
        self.assertEqual(req["source_location"]["table_id"], "Appendix OPR-1")

    # L
    def test_l_requirement_connected_to_figure_evidence(self):
        figure_source = self.store.add_source(
            self.workspace, name="FIG-2-1.svg", file_path="/tmp/fig1.svg", kind="drawing",
            width=900, height=620, document_id="NREOCRC-OPR-001 / Figure OPR-2.1",
        )
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="5.2",
            text_reference="Interior organization shall reflect zoning... illustrated in Figure OPR-2.1.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            source_location={"location_type": "figure", "value": "Figure OPR-2.1"},
        )
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_REQUIREMENT, from_id=req["id"],
            to_type=OBJECT_KIND_SOURCE, to_id=figure_source["id"],
            relationship_type=RELATIONSHIP_TYPE_CORRESPONDS_TO, created_by="tester", confidence=0.95,
        )
        self.assertEqual(rel["from_id"], req["id"])
        self.assertEqual(rel["to_id"], figure_source["id"])
        self.assertEqual(req["source_location"]["location_type"], REQUIREMENT_LOCATION_TYPE_FIGURE)

    # M
    def test_m_requirement_superseded_without_deleting_predecessor(self):
        original = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="6.1",
            text_reference="Accessibility standard citation to be confirmed in the Data Room.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        revised, supersession = self.store.revise_requirement(
            self.workspace, requirement_id=original["id"], actor="tester",
            reason="Addendum 1 confirmed the accessibility standard citation.",
            authority_class="addendum:1",
            text_reference="Accessibility standard: City of North River Accessibility Design Standard, 2023 ed., Section 4.2.",
            governance_log=self.gov,
        )
        reloaded = self.store.get(self.project_id)
        original_after = self.store._find(reloaded.requirements, original["id"])
        self.assertEqual(original_after["status"], REQUIREMENT_STATUS_SUPERSEDED)
        self.assertIn("to be confirmed", original_after["text_reference"])  # predecessor preserved, unedited
        self.assertEqual(revised["status"], REQUIREMENT_STATUS_ACTIVE)
        self.assertIn("Section 4.2", revised["text_reference"])
        lineage = self.store.supersessions_for(reloaded, OBJECT_KIND_REQUIREMENT, original["id"])
        self.assertEqual(len(lineage), 1)
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "requirement_superseded"]
        self.assertEqual(len(events), 1)

    # N
    def test_n_requirement_status_distinct_from_compliance_outcome(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="9.1",
            text_reference="Structural system shall remain operational following design-basis events.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        self.assertEqual(req["status"], REQUIREMENT_STATUS_ACTIVE)
        # No compliance-shaped value exists in the status vocabulary at all.
        with self.assertRaises(CaseWorkspaceError):
            self.store.set_requirement_status(self.workspace, req["id"], "non_compliant", actor="tester")

    # O
    def test_o_machine_vs_manual_registration_provenance(self):
        manual = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.1",
            text_reference="x", created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        machine = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="12.2",
            text_reference="y", created_by="bhive-parser",
            registration_method=REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
        )
        self.assertEqual(manual["registration_method"], REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE)
        self.assertEqual(machine["registration_method"], REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED)
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_requirement(
                self.workspace, source_id=self.source["id"], original_requirement_identifier="12.3",
                text_reference="z", created_by="tester", registration_method="not_a_real_method",
            )

    # P
    def test_p_no_requirement_fabricated_from_legacy_finding(self):
        """Legacy projects with Findings but no Requirements must not have
        Requirements synthesized from them on load."""
        import json
        legacy_project_id = "legacy-project-f2"
        legacy_data = {
            "project_id": legacy_project_id,
            "findings": [{"id": "f1", "project_id": legacy_project_id, "case_id": "c1",
                          "analysis_id": "a1", "statement": "x", "machine_confidence": 0.5,
                          "created_at": "2020-01-01T00:00:00+00:00", "claim_status": "provisional"}],
        }
        (self.tmp_dir / f"{legacy_project_id}.workspace.json").write_text(json.dumps(legacy_data), encoding="utf-8")
        workspace = self.store.get(legacy_project_id)
        self.assertEqual(workspace.requirements, [])
        self.assertEqual(len(workspace.findings), 1)  # the Finding itself is untouched

    # Q
    def test_q_citation_validation_detects_mismatched_location(self):
        source_text = (
            "12.3 The standby power system... shall not be rendered inoperable... "
            "including flood conditions associated with the Site context described in Section 4.5."
        )
        # The Prompt 13 defect: a citation claiming "Section 4.3" when the
        # text actually names "Section 4.5".
        self.assertFalse(validate_requirement_location_citation(source_text, "Section 4.3"))
        self.assertTrue(validate_requirement_location_citation(source_text, "Section 4.5"))


class NREOCRCRepresentativeTests(unittest.TestCase):
    """Prompt 15 #27: OPR 12.1, OPR 4.6, Appendix OPR-1 Row 20 - generic
    architecture only, no production rules naming these specific clauses."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_f_nreocrc_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-f3"
        self.workspace = self.store.get_or_create(self.project_id)
        self.opr_source = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001.md", file_path="/tmp/opr.md",
            kind="owner_project_requirements", document_id="NREOCRC-OPR-001", revision="0",
            issue_date="2026-12-08", issuer="North River Infrastructure Corporation",
            document_status="ISSUED WITH RFP — CONTRACTUAL DOCUMENT",
            document_authority=DOCUMENT_AUTHORITY_CONTRACTUAL,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_opr_12_1_standby_power(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.opr_source["id"], original_requirement_identifier="12.1",
            text_reference="Standby power generation capacity sufficient... no less than 96 hours without refuelling.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_MANDATORY,
            source_location={"location_type": "clause", "value": "12.1"},
        )
        self.assertEqual(self.opr_source["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertEqual(req["classification"], REQUIREMENT_CLASSIFICATION_MANDATORY)
        self.assertEqual(req["original_requirement_identifier"], "12.1")

    def test_opr_4_6_indicative_within_contractual_document(self):
        req = self.store.register_requirement(
            self.workspace, source_id=self.opr_source["id"], original_requirement_identifier="4.6",
            text_reference="Three preliminary site and building placement concepts... not required to adopt any Option.",
            created_by="tester", registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
            classification=REQUIREMENT_CLASSIFICATION_INDICATIVE,
        )
        # Document is Contractual as a whole; this specific clause is Indicative.
        self.assertEqual(self.opr_source["document_authority"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertEqual(req["classification"], REQUIREMENT_CLASSIFICATION_INDICATIVE)

    def test_appendix_opr_1_row_20_table_provenance_without_fake_extraction(self):
        """Confirms the generic architecture CAN represent this - does not
        claim automatic table extraction occurred, per Prompt 15 #27's
        explicit instruction not to fake parser capability."""
        req = self.store.register_requirement(
            self.workspace, source_id=self.opr_source["id"],
            original_requirement_identifier="Appendix OPR-1 Row 20",
            text_reference=(
                "Situational Awareness / Media Briefing Room - Security Level: Secure/Controlled "
                "interface. Access control at both boundaries. Room bridges Secure and Controlled "
                "Zones - see Section 14."
            ),
            created_by="tester",
            registration_method=REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,  # honest: hand-transcribed, not parsed
            source_location={"location_type": "table_row", "table_id": "Appendix OPR-1", "row": 20},
            applicability="Secure/Controlled zone boundary space",
        )
        self.assertEqual(req["registration_method"], REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE)
        self.assertEqual(req["source_location"]["location_type"], REQUIREMENT_LOCATION_TYPE_TABLE_ROW)
        self.assertEqual(req["source_location"]["row"], 20)


if __name__ == "__main__":
    unittest.main()
