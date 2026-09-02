"""
Foundation Batch J (Prompt 18) tests: Structured Tabular Evidence
(Table/TableRow/cells) and Generic Source-Reference Resolution
(SourceReference + parser/resolver) - built directly from the concrete
architectural weakness the Snapshot 002 experiment exposed: tables could
be parsed but not referenced as reusable governed evidence, and explicit
document citations ("Sections 10 through 14") could not be normalized
into structured, existence-checked references.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from services.bhive_parser import BHiveParser
from services.case_workspace import (
    KNOWN_OBJECT_KINDS,
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_TABLE,
    OBJECT_KIND_TABLE_ROW,
    OBJECT_KIND_TABLE_CELL,
    RELATIONSHIP_TYPE_REFERENCES,
    RELATIONSHIP_TYPE_SUPPORTS,
    RESOLUTION_STATUS_AMBIGUOUS,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_RESOLVED_MULTIPLE,
    RESOLUTION_STATUS_RESOLVED_RANGE,
    RESOLUTION_STATUS_PARTIALLY_RESOLVED,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
    RESOLUTION_STATUS_UNKNOWN,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    ProjectWorkspace,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    _MAX_SOURCE_REFERENCES_PER_SOURCE,
    check_citation_against_resolved_references,
    parse_source_reference_text,
    parse_table_cell_value,
    resolve_source_reference_candidate,
)
from services.governance import GovernanceLog
from services.ingestion import _register_source_content
from services.conversational_turn import gather_project_evidence

NREOCRC_PATH = Path(__file__).parent / "fixtures" / "nreocrc" / "immutable_original" / "NREOCRC-OPR-001.md"

_SAMPLE_TABLE = {
    "headers": ["#", "Functional Group", "Room / Space", "Qty", "Net Area (m²) each", "Dept. Area Subtotal (m²)"],
    "rows": [
        ["1", "Public / Community", "Public Lobby & Reception", "1", "120", "—"],
        ["4", "Public / Community", "Public Washrooms", "2", "45", "570"],
        ["20", "Emergency Operations Centre", "Situational Awareness / Media Briefing Room", "1", "65", ""],
    ],
    "start_line": 100, "end_line": 103,
}


class StructuredTabularEvidenceTests(unittest.TestCase):
    """Tests A-K."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_j_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-j1"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="doc.md", file_path="/tmp/doc.md", kind="owner_project_requirements",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # A - Table identity
    def test_a_table_identity(self):
        table, rows = self.store.register_table_evidence(
            self.workspace, self.source["id"], _SAMPLE_TABLE,
            extraction_engine="bhive_parser", extraction_version="1.0", actor="tester",
        )
        self.assertTrue(table["id"])
        self.assertEqual(table["project_id"], self.project_id)
        self.assertEqual(table["source_id"], self.source["id"])
        self.assertEqual(table["headers"], _SAMPLE_TABLE["headers"])
        self.assertEqual(table["source_location"], {"start_line": 100, "end_line": 103})
        self.assertEqual(table["extraction_engine"], "bhive_parser")
        self.assertEqual(table["extraction_version"], "1.0")
        self.assertIn("table", KNOWN_OBJECT_KINDS)
        self.assertEqual(OBJECT_KIND_TABLE, "table")
        # A second table registered from the same source gets independent identity.
        table2, _ = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        self.assertNotEqual(table["id"], table2["id"])

    # B - Row identity
    def test_b_row_identity(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r["row_index"] for r in rows], [0, 1, 2])
        self.assertEqual(rows[2]["source_row_identifier"], "20")  # the "#" column value, not row_index
        self.assertEqual(rows[2]["table_id"], table["id"])
        self.assertEqual(rows[2]["source_location"], {"line": 104})  # start_line(100) + 2 + row_index(2)
        row20 = self.store.get_table_row(self.workspace, rows[2]["id"])
        self.assertEqual(row20["id"], rows[2]["id"])
        self.assertIsNone(self.store.get_table_row(self.workspace, "does-not-exist"))

    # C - Cell identity
    def test_c_cell_identity(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        row20 = rows[2]
        cell_ids = [c["id"] for c in row20["cells"]]
        self.assertEqual(len(cell_ids), len(set(cell_ids)))  # all distinct
        area_cell = next(c for c in row20["cells"] if c["header"] == "Net Area (m²) each")
        resolved = self.store.resolve_table_cell(self.workspace, area_cell["id"])
        self.assertEqual(resolved["raw_value"], "65")
        self.assertIsNone(self.store.resolve_table_cell(self.workspace, "does-not-exist"))

    # D - source provenance
    def test_d_source_provenance(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE, actor="tester")
        self.assertEqual(table["created_by"], "tester")
        self.assertEqual(self.store.tables_for_source(self.workspace, self.source["id"])[0]["id"], table["id"])
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_table_evidence(self.workspace, "does-not-exist", _SAMPLE_TABLE)

    # E - raw + parsed value both preserved
    def test_e_raw_and_parsed_value_preserved(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        subtotal_cell = next(c for c in rows[1]["cells"] if c["header"] == "Dept. Area Subtotal (m²)")
        self.assertEqual(subtotal_cell["raw_value"], "570")  # never discarded
        self.assertEqual(subtotal_cell["parsed_value"], 570.0)
        # A comma-formatted raw value still parses correctly and keeps its raw form.
        parsed, qualifier = parse_table_cell_value("1,120")
        self.assertEqual(parsed, 1120.0)
        self.assertIsNone(qualifier)

    # F - qualifier preservation
    def test_f_qualifier_preservation(self):
        for raw, expected_qualifier in [("TBD", "TBD"), ("approx.", "approx."), ("included in subtotal", "included in subtotal")]:
            parsed, qualifier = parse_table_cell_value(raw)
            self.assertIsNone(parsed, f"{raw!r} must not produce a numeric value")
            self.assertEqual(qualifier, expected_qualifier)

    # G - blank / em-dash handling (never coerced to zero)
    def test_g_blank_and_em_dash_never_zero(self):
        for raw in ("", "—", "-", "–"):
            parsed, qualifier = parse_table_cell_value(raw)
            self.assertIsNone(parsed)
            self.assertIsNotNone(qualifier)
            self.assertNotEqual(parsed, 0)

    # H - Requirement -> Table Row linkage (via existing Relationship substrate)
    def test_h_requirement_to_table_row_linkage(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        row20 = rows[2]
        requirement = self.store.register_requirement(
            self.workspace, source_id=self.source["id"], original_requirement_identifier="Appendix X, Row 20",
            text_reference="Situational Awareness / Media Briefing Room - boundary space.",
            created_by="tester", registration_method="derived_from_structured_source",
        )
        rel = self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_TABLE_ROW, from_id=row20["id"],
            to_type=OBJECT_KIND_REQUIREMENT, to_id=requirement["id"],
            relationship_type=RELATIONSHIP_TYPE_SUPPORTS, created_by="tester",
        )
        self.assertEqual(rel["from_type"], OBJECT_KIND_TABLE_ROW)
        self.assertEqual(rel["from_id"], row20["id"])
        self.assertEqual(rel["to_id"], requirement["id"])
        # Not every row automatically becomes a Requirement (Prompt 18 #11) -
        # only 1 of the 3 sample rows was registered as one.
        self.assertEqual(len(self.workspace.requirements), 1)

    # I - ReviewThread anchor -> Table Row (no ReviewThread redesign needed)
    def test_i_review_thread_anchors_to_table_row(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        row20 = rows[2]
        thread = self.store.create_review_thread(
            self.workspace, title="Row 20 boundary-zone check",
            anchor_type=OBJECT_KIND_TABLE_ROW, anchor_id=row20["id"],
            anchor_source_id=self.source["id"], created_by="tester",
        )
        self.assertEqual(thread["anchor"]["anchor_type"], OBJECT_KIND_TABLE_ROW)
        self.assertEqual(thread["anchor"]["anchor_id"], row20["id"])
        found = self.store.threads_for_anchor(self.workspace, OBJECT_KIND_TABLE_ROW, row20["id"])
        self.assertEqual(found[0]["id"], thread["id"])

    # J - Analysis consuming Table evidence (a real AnalysisRun/Finding referencing the Table)
    def test_j_analysis_consumes_table_evidence(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        case = self.store.create_case(self.workspace, title="Table reconciliation", objective="Check subtotals.")
        rel = self.store.record_relationship(
            self.workspace, from_type="analysis_objective", from_id="reconciliation",
            to_type=OBJECT_KIND_TABLE, to_id=table["id"],
            relationship_type=RELATIONSHIP_TYPE_REFERENCES, created_by="tester",
        )
        self.assertEqual(rel["to_type"], OBJECT_KIND_TABLE)
        self.assertEqual(rel["to_id"], table["id"])

    # K - generic arithmetic reconciliation using Table evidence
    def test_k_reconciliation_over_table_evidence(self):
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], _SAMPLE_TABLE)
        result = self.store.reconcile_table(self.workspace, table["id"])
        self.assertIsNotNone(result)
        public_group = next(g for g in result["groups"] if g["group"] == "Public / Community")
        self.assertEqual(public_group["computed_from_line_items"], 120 + 90)  # 120 + (2*45)
        self.assertEqual(public_group["stated_subtotal"], 570.0)
        self.assertFalse(public_group["matches"])
        eoc_group = next(g for g in result["groups"] if g["group"] == "Emergency Operations Centre")
        self.assertIsNone(eoc_group["stated_subtotal"])
        self.assertIsNone(eoc_group["matches"])  # no data to compare, not a false mismatch
        with self.assertRaises(CaseWorkspaceError):
            self.store.reconcile_table(self.workspace, "does-not-exist")

    # legacy compatibility: a table lacking the expected columns reconciles to None honestly.
    def test_reconciliation_returns_none_for_non_matching_shape(self):
        odd_table = {"headers": ["Name", "Value"], "rows": [["a", "1"]], "start_line": 1, "end_line": 3}
        table, rows = self.store.register_table_evidence(self.workspace, self.source["id"], odd_table)
        self.assertIsNone(self.store.reconcile_table(self.workspace, table["id"]))


class SourceReferenceTests(unittest.TestCase):
    """Tests L-U."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_j2_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-j2"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="doc.md", file_path="/tmp/doc.md", kind="owner_project_requirements",
        )
        self.known = {
            "section": {"4.1", "4.2", "4.3", "4.4", "4.5", "4.6", "12.1", "12.2", "12.3", "14"},
            "figure": {"OPR-2.1", "OPR-2.2"},
        }

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # L - single-section reference resolution
    def test_l_single_section_resolution(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "described in Section 4.5.",
            origin_context={"location_type": "clause", "section": "12.3"}, known_targets=self.known,
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["resolution_status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(refs[0]["resolved_target_ids"], ["4.5"])
        self.assertEqual(refs[0]["reference_type"], "section")

    # M - section-range resolution
    def test_m_section_range_resolution(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"],
            "exceeding the requirements of Sections 12.1 through 12.3 will be considered favourably.",
            origin_context={"location_type": "clause", "section": "12.4"}, known_targets=self.known,
        )
        self.assertEqual(refs[0]["resolution_status"], RESOLUTION_STATUS_RESOLVED_RANGE)
        self.assertEqual(refs[0]["resolved_target_ids"], ["12.1", "12.2", "12.3"])

    # N - multiple/list reference resolution
    def test_n_multiple_reference_resolution(self):
        candidates = parse_source_reference_text("Figures OPR-2.1 and OPR-2.2 both apply.")
        self.assertEqual(candidates[0]["syntactic_form"], "list")
        resolved = resolve_source_reference_candidate(candidates[0], self.known)
        self.assertEqual(resolved["resolution_status"], RESOLUTION_STATUS_RESOLVED_MULTIPLE)
        self.assertEqual(set(resolved["resolved_targets"]), {"OPR-2.1", "OPR-2.2"})

    # O - row-range resolution
    def test_o_row_range_resolution(self):
        candidates = parse_source_reference_text("Rows 15-20 are excluded from this calculation.")
        self.assertEqual(candidates[0]["reference_type"], "table_row")
        self.assertEqual(candidates[0]["candidate_targets"], ["15", "16", "17", "18", "19", "20"])
        self.assertEqual(candidates[0]["syntactic_form"], "range")

    # P - Figure reference resolution
    def test_p_figure_reference_resolution(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "as illustrated in Figure OPR-2.1.",
            origin_context={"location_type": "clause", "section": "5.2"}, known_targets=self.known,
        )
        self.assertEqual(refs[0]["reference_type"], "figure")
        self.assertEqual(refs[0]["resolution_status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(refs[0]["resolved_target_ids"], ["OPR-2.1"])

    # Q - unresolved reference preservation (no known_targets supplied at all)
    def test_q_unresolved_reference_preserved_not_discarded(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "see Section 99.9 for details.",
            origin_context={"location_type": "clause", "section": "1.1"},
        )
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["resolution_status"], RESOLUTION_STATUS_UNKNOWN)
        self.assertEqual(refs[0]["reference_text"], "Section 99.9")

    # R - ambiguous reference preservation
    def test_r_ambiguous_reference_preserved(self):
        candidate = {"reference_type": "section", "candidate_targets": ["Alpha", "Beta"], "syntactic_form": "ambiguous"}
        resolved = resolve_source_reference_candidate(candidate, self.known)
        self.assertEqual(resolved["resolution_status"], RESOLUTION_STATUS_AMBIGUOUS)
        self.assertEqual(resolved["resolved_targets"], [])

    # S - original citation text preserved even when resolution fails entirely
    def test_s_original_citation_text_preserved(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "per Section 999 (nonexistent).",
            origin_context={"location_type": "clause", "section": "1.1"}, known_targets=self.known,
        )
        self.assertEqual(refs[0]["resolution_status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)
        self.assertEqual(refs[0]["reference_text"], "Section 999")  # verbatim, not discarded

    # T - explicit-reference graph traversal
    def test_t_explicit_reference_graph_traversal(self):
        self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "described in Section 4.5.",
            origin_context={"location_type": "clause", "section": "12.3"}, known_targets=self.known,
        )
        self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "as per Section 4.5 again.",
            origin_context={"location_type": "clause", "section": "9.4"}, known_targets=self.known,
        )
        incoming = self.store.source_references_to_target(self.workspace, "4.5")
        self.assertEqual(len(incoming), 2)
        self.assertEqual({r["origin_context"]["section"] for r in incoming}, {"12.3", "9.4"})
        outgoing = self.store.source_references_for_source(self.workspace, self.source["id"])
        self.assertEqual(len(outgoing), 2)

    # U - generic wrong-citation detection (reproduces the Prompt 13/17 defect class generically)
    def test_u_generic_wrong_citation_detection(self):
        text_123 = "flood conditions associated with the Site context described in Section 4.5."
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], text_123,
            origin_context={"location_type": "clause", "section": "12.3"}, known_targets=self.known,
        )
        self.assertEqual(check_citation_against_resolved_references("4.5", refs), "VALID")
        self.assertEqual(check_citation_against_resolved_references("4.3", refs), "MISMATCH")
        self.assertEqual(check_citation_against_resolved_references("4.5", []), "UNVERIFIABLE")

    def test_v2_idempotent_registration_is_scoped_to_source_and_origin(self):
        origin = {"location_type": "source"}
        first = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "See Section 4.3.", origin,
            known_targets=self.known, resolution_method="declared_reference_target_match",
            resolved_target_type="requirement", extractor_version="declared_reference_v1",
            governance_log=self.gov,
        )
        second = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "See Section 4.3.", origin,
            known_targets=self.known, resolution_method="declared_reference_target_match",
            resolved_target_type="requirement", extractor_version="declared_reference_v1",
            governance_log=self.gov,
        )
        other_source = self.store.add_source(
            self.workspace, name="other.md", file_path="/tmp/other.md", kind="owner_project_requirements",
        )
        separate = self.store.extract_and_register_source_references(
            self.workspace, other_source["id"], "See Section 4.3.", origin,
            known_targets=self.known,
        )
        self.assertEqual(len(first), 1)
        self.assertEqual(second, [])
        self.assertEqual(len(separate), 1)
        self.assertEqual(first[0]["resolution_method"], "declared_reference_target_match")
        self.assertEqual(first[0]["extractor_version"], "declared_reference_v1")
        self.assertEqual(first[0]["resolved_target_type"], "requirement")

    def test_v2_per_source_cap_is_logged_without_silent_truncation(self):
        text = " ".join(f"Section {index}.1." for index in range(1, _MAX_SOURCE_REFERENCES_PER_SOURCE + 6))
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], text,
            {"location_type": "source"}, known_targets={"section": set()}, governance_log=self.gov,
        )
        self.assertEqual(len(refs), _MAX_SOURCE_REFERENCES_PER_SOURCE)
        truncation = [event for event in self.gov.read(self.project_id)
                      if event.event_type == "source_reference_extraction_truncated"]
        self.assertEqual(len(truncation), 1)
        self.assertEqual(truncation[0].payload["supplied_count"], _MAX_SOURCE_REFERENCES_PER_SOURCE + 5)
        self.assertEqual(truncation[0].payload["retained_count"], _MAX_SOURCE_REFERENCES_PER_SOURCE)
        self.assertEqual(truncation[0].payload["omitted_count"], 5)

    def test_v2_ingestion_seam_registers_references_without_relationships(self):
        class _Parser:
            def _extract(self, raw_bytes, filename):
                return "Refer to Section 4.3."

        before_relationships = list(self.workspace.relationships)
        status, reason = _register_source_content(
            self.store, self.workspace, self.source, b"ignored", "doc.md", _Parser(),
            actor="system", governance_log=self.gov,
        )
        self.assertEqual((status, reason), ("added", None))
        refs = self.store.source_references_for_source(self.workspace, self.source["id"])
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["reference_text"], "Section 4.3")
        self.assertEqual(self.workspace.relationships, before_relationships)

    def test_declared_missing_reference_is_not_promoted_to_source_or_evidence(self):
        class _Parser:
            def _extract(self, raw_bytes, filename):
                return "Refer to Section 99.9."

        source_ids_before = {source["id"] for source in self.workspace.sources}
        status, reason = _register_source_content(
            self.store, self.workspace, self.source, b"physical bytes", "doc.md", _Parser(),
            actor="system", governance_log=self.gov,
        )

        self.assertEqual((status, reason), ("added", None))
        self.assertEqual({source["id"] for source in self.workspace.sources}, source_ids_before)
        self.assertEqual(len(self.workspace.source_references), 1)
        self.assertEqual(self.workspace.source_references[0]["resolution_status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)
        self.assertEqual({item["source_id"] for item in self.workspace.evidence_items}, {self.source["id"]})

    def test_declared_missing_reference_adds_no_spin_document(self):
        class _Parser:
            def _extract(self, raw_bytes, filename):
                return "Refer to Section 99.9."

        _register_source_content(
            self.store, self.workspace, self.source, b"physical bytes", "doc.md", _Parser(),
            actor="system", governance_log=self.gov,
        )

        evidence = gather_project_evidence(self.workspace, self.store)
        self.assertEqual(len(evidence.additional_document_evidence), 1)
        self.assertEqual(evidence.additional_document_evidence[0]["source_id"], self.source["id"])

    def test_physical_source_extracted_evidence_remains_spin_eligible(self):
        class _Parser:
            def _extract(self, raw_bytes, filename):
                return "Physical project evidence without a declared citation."

        status, reason = _register_source_content(
            self.store, self.workspace, self.source, b"physical bytes", "doc.md", _Parser(),
            actor="system", governance_log=self.gov,
        )

        evidence = gather_project_evidence(self.workspace, self.store)
        self.assertEqual((status, reason), ("added", None))
        self.assertEqual(
            evidence.additional_document_evidence[0]["excerpts"],
            ["Physical project evidence without a declared citation."],
        )

    def test_v3_read_time_resolution_tracks_current_requirements_without_mutation(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "See Section 4.3.",
            {"location_type": "source"}, known_targets={"section": set()},
        )
        reference_id = refs[0]["id"]
        stored_before = deepcopy(refs[0])
        current_before = self.store.resolve_source_reference_status(self.workspace, reference_id)
        self.assertEqual(current_before["resolution_status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)

        self.store.register_requirement(
            self.workspace, self.source["id"], "4.3", "Section 4.3 requirement", "tester",
            REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        current_after = self.store.resolve_source_reference_status(self.workspace, reference_id)
        self.assertEqual(current_after["resolution_status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(current_after["resolved_target_ids"], ["4.3"])
        self.assertEqual(self.store.get_source_reference(self.workspace, reference_id), stored_before)
        self.assertEqual(self.workspace.relationships, [])

    def test_v3_read_time_partial_and_superseded_target_changes_are_honest(self):
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], "See Sections 4.3 and 4.4.",
            {"location_type": "source"}, known_targets={"section": set()},
        )
        reference_id = refs[0]["id"]
        self.store.register_requirement(
            self.workspace, self.source["id"], "4.3", "Section 4.3 requirement", "tester",
            REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        partial = self.store.resolve_source_reference_status(self.workspace, reference_id)
        self.assertEqual(partial["resolution_status"], RESOLUTION_STATUS_PARTIALLY_RESOLVED)
        self.assertEqual(partial["resolved_target_ids"], ["4.3"])

        requirement = self.store.register_requirement(
            self.workspace, self.source["id"], "4.4", "Section 4.4 requirement", "tester",
            REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
        )
        resolved = self.store.resolve_source_reference_status(self.workspace, reference_id)
        self.assertEqual(resolved["resolution_status"], RESOLUTION_STATUS_RESOLVED_MULTIPLE)
        self.store.set_requirement_status(self.workspace, requirement["id"], "superseded", "tester")
        after_supersession = self.store.resolve_source_reference_status(self.workspace, reference_id)
        self.assertEqual(after_supersession["resolution_status"], RESOLUTION_STATUS_PARTIALLY_RESOLVED)
        self.assertEqual(after_supersession["resolved_target_ids"], ["4.3"])

    def test_v3_unknown_source_reference_id_is_unresolved(self):
        result = self.store.resolve_source_reference_status(self.workspace, "missing-reference")
        self.assertEqual(result, {"status": "unresolved", "source_reference_id": "missing-reference"})


class NREOCRCRegressionTests(unittest.TestCase):
    """
    Tests V-X: real-corpus regression tests (not a re-ingestion experiment,
    not a Snapshot 003 - just verifying the new generic capability against
    the same real, immutable file used throughout this project). Reads
    the corpus read-only; never modifies it.
    """

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_j3_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("nreocrc-batch-j")
        self.source = self.store.add_source(
            self.workspace, name="NREOCRC-OPR-001.md", file_path=str(NREOCRC_PATH), kind="owner_project_requirements",
        )
        raw_bytes = NREOCRC_PATH.read_bytes()
        self.raw_text = raw_bytes.decode("utf-8")
        self.raw_lines = self.raw_text.splitlines()
        parser = BHiveParser(anthropic_api_key=None)
        self.parsed_document = parser.parse(raw_bytes, "NREOCRC-OPR-001.md")
        self.fp_table_raw = next(
            t for t in self.parsed_document.tables
            if "Functional Group" in t["headers"] and any("Subtotal" in h for h in t["headers"])
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # V - NREOCRC Row-20 structural reference
    def test_v_row_20_structural_reference(self):
        table, rows = self.store.register_table_evidence(
            self.workspace, self.source["id"], self.fp_table_raw, raw_lines=self.raw_lines,
        )
        row20 = next(r for r in rows if r["source_row_identifier"] == "20")
        notes_cell = next(c for c in row20["cells"] if c["header"] == "Notes")
        self.assertIn("Room bridges Secure and Controlled Zones", notes_cell["raw_value"])

        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], notes_cell["raw_value"],
            origin_context={"location_type": "table_row", "table_row_id": row20["id"]},
            known_targets={"section": {"14"}},
        )
        section_refs = [r for r in refs if r["reference_type"] == "section"]
        self.assertEqual(len(section_refs), 1)
        self.assertEqual(section_refs[0]["resolution_status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(section_refs[0]["resolved_target_ids"], ["14"])
        # No compliance conclusion is drawn - only that the citation resolves.
        self.assertNotIn("compliance", str(refs).lower())

    # W - NREOCRC range-reference regression (12.4's real "Sections 12.1 through 12.3")
    def test_w_range_reference_regression(self):
        clause_124 = next(
            line for line in self.raw_lines
            if line.strip().startswith("**12.4**")
        )
        self.assertIn("Sections 12.1 through 12.3", clause_124)

        known = {"section": {"12.1", "12.2", "12.3", "12.4"}}
        refs = self.store.extract_and_register_source_references(
            self.workspace, self.source["id"], clause_124,
            origin_context={"location_type": "clause", "section": "12.4"}, known_targets=known,
        )
        section_refs = [r for r in refs if r["reference_type"] == "section"]
        self.assertEqual(len(section_refs), 1)
        self.assertEqual(section_refs[0]["resolution_status"], RESOLUTION_STATUS_RESOLVED_RANGE)
        self.assertEqual(section_refs[0]["resolved_target_ids"], ["12.1", "12.2", "12.3"])

    # X - NREOCRC arithmetic analysis works through structured Table evidence,
    # not direct ParsedDocument.tables access.
    def test_x_arithmetic_regression_through_table_evidence(self):
        table, rows = self.store.register_table_evidence(
            self.workspace, self.source["id"], self.fp_table_raw, raw_lines=self.raw_lines,
        )
        # Deliberately do NOT touch self.fp_table_raw / self.parsed_document.tables
        # again below - reconcile_table operates only on the registered,
        # governed Table/TableRow evidence by id.
        result = self.store.reconcile_table(self.workspace, table["id"])

        expected = {
            "Public / Community": (615.0, 570.0),
            "Municipal Administration": (534.0, 850.0),
            "Emergency Operations Centre": (731.0, 1120.0),
            "Communications": (175.0, 175.0),
            "Standby Power & Building Services": (545.0, 545.0),
            "Vehicle / Service": (410.0, 460.0),
            "Support": (195.0, 260.0),
        }
        by_group = {g["group"]: g for g in result["groups"]}
        for group, (computed, stated) in expected.items():
            self.assertEqual(by_group[group]["computed_from_line_items"], computed, group)
            self.assertEqual(by_group[group]["stated_subtotal"], stated, group)

        self.assertEqual(result["total_from_line_items"], 3205.0)
        self.assertEqual(result["total_from_stated_subtotals"], 3980.0)
        self.assertEqual(result["mismatched_group_count"], 5)


class LegacyCompatibilityTests(unittest.TestCase):
    """Test Y (partial - the full suite run is the real Y): a workspace
    saved before Batch J (no tables/table_rows/source_references keys at
    all) loads cleanly with empty lists."""

    def test_legacy_workspace_without_batch_j_fields_loads(self):
        import json
        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_j4_"))
        try:
            store = CaseWorkspaceStore(tmp_dir)
            legacy_data = {"project_id": "legacy-project-j", "version": 5, "sources": []}
            (tmp_dir / "legacy-project-j.workspace.json").write_text(json.dumps(legacy_data), encoding="utf-8")

            loaded = store.get("legacy-project-j")
            self.assertEqual(loaded.tables, [])
            self.assertEqual(loaded.table_rows, [])
            self.assertEqual(loaded.source_references, [])

            # A legacy ReviewThread anchored to Source + location dict
            # (the pre-Batch-J pattern) remains fully readable.
            source = store.add_source(loaded, name="old.md", file_path="/tmp/old.md", kind="owner_project_requirements")
            thread = store.create_review_thread(
                loaded, title="Old-style anchor", anchor_type=OBJECT_KIND_SOURCE, anchor_id=source["id"],
                anchor_location={"location_type": "table", "table_start_line": 10}, created_by="tester",
            )
            self.assertEqual(thread["anchor"]["anchor_type"], OBJECT_KIND_SOURCE)
            self.assertEqual(thread["anchor"]["location"]["table_start_line"], 10)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
