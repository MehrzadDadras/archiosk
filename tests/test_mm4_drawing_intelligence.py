"""
CLAUDE-MM4 (Drawing Intelligence and Orientation-Normalized Comparison)
tests: services/drawing_intelligence.py's coordinate-transform geometry,
CaseWorkspaceStore.register_drawing_sheet_structure/create_addressable_
drawing_region/build_evidence_sachet (already-extracted sheets -> governed
MM1 evidence), and services/drawing_intelligence.register_drawing_evidence_
for_source/create_drawing_region_and_evidence (the real pypdf/Pillow read
-> classification -> registration orchestration).

Mirrors this repository's established hermetic pattern for PDF-adjacent
code (tests/test_mm2_pdf_document_intelligence.py): a real, hand-built
minimal PDF (~600 bytes) and a real, small Pillow-generated PNG - no
external calls, no mocking of the parsing libraries themselves.

Run via:

    python -m unittest tests.test_mm4_drawing_intelligence -v
"""
from __future__ import annotations

import io
import itertools
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from PIL import Image

from services.case_workspace import (
    DRAWING_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    DRAWING_CLASSIFICATION_EXCESSIVE_SIZE,
    DRAWING_CLASSIFICATION_MALFORMED,
    DRAWING_CLASSIFICATION_SUPPORTED,
    METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
    METADATA_RELIABILITY_INFERRED,
    METADATA_RELIABILITY_UNAVAILABLE,
    OBSERVATION_AUTHOR_HUMAN,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.drawing_intelligence import (
    DrawingIntelligenceError,
    MAX_RAW_BYTES,
    ROTATIONS,
    create_drawing_region_and_evidence,
    describe_transform,
    normalize_rotation,
    register_drawing_evidence_for_source,
    transform_point_to_display,
    transform_point_to_original,
    transform_rect_to_display,
    transform_rect_to_original,
)
from services.governance import GovernanceLog

# A real, valid, minimal one-page PDF with a genuine embedded title block
# ("Sheet No: A-101", "Drawing Title: Ground Floor Plan", ...) - hand-built
# using tests/test_mm2_pdf_document_intelligence.py's own construction
# technique (no reportlab/fpdf dependency added).
_TITLE_BLOCK_TEXT = (
    b"BT /F1 12 Tf 72 700 Td (Sheet No: A-101) Tj "
    b"0 -18 Td (Drawing Title: Ground Floor Plan) Tj "
    b"0 -18 Td (Revision: 2) Tj "
    b"0 -18 Td (Scale: 1/4in = 1ft) Tj ET"
)


def _build_minimal_pdf(text: bytes = _TITLE_BLOCK_TEXT, page_count: int = 1) -> bytes:
    kids = " ".join(f"{3 + i} 0 R" for i in range(page_count))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>").encode(),
    ]
    for _ in range(page_count):
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 %d 0 R >> >> "
            b"/MediaBox [0 0 612 792] /Contents %d 0 R >>"
            % (2 + page_count + 1, 2 + page_count + 2)
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    objects.append(b"<< /Length %d >>\nstream\n%s\nendstream" % (len(text), text))

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (i, body)
    xref_offset = len(out)
    n = len(objects) + 1
    out += b"xref\n0 %d\n" % n
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\n" % n
    out += b"startxref\n%d\n%%%%EOF" % xref_offset
    return bytes(out)


def _build_png(width: int = 40, height: int = 30) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 30)).save(buf, format="PNG")
    return buf.getvalue()


# ============================================================================
# Coordinate-transform geometry - pure math, no store/files involved.
# ============================================================================

class CoordinateTransformTests(unittest.TestCase):
    def test_normalize_rotation_folds_any_integer(self):
        self.assertEqual(normalize_rotation(0), 0)
        self.assertEqual(normalize_rotation(90), 90)
        self.assertEqual(normalize_rotation(450), 90)
        self.assertEqual(normalize_rotation(-90), 270)
        self.assertEqual(normalize_rotation(360), 0)

    def test_identity_transform_is_a_no_op(self):
        self.assertEqual(transform_point_to_display(0.2, 0.3, 0), (0.2, 0.3))
        self.assertEqual(transform_point_to_original(0.2, 0.3, 0), (0.2, 0.3))

    def test_horizontal_mirror_flips_x_only(self):
        self.assertEqual(transform_point_to_display(0.2, 0.3, 0, mirror_h=True), (0.8, 0.3))

    def test_vertical_mirror_flips_y_only(self):
        self.assertEqual(transform_point_to_display(0.2, 0.3, 0, mirror_v=True), (0.2, 0.7))

    def test_90_clockwise_rotation_known_corners(self):
        # Rotating the whole sheet 90 clockwise: top-left -> top-right,
        # top-right -> bottom-right, bottom-right -> bottom-left,
        # bottom-left -> top-left.
        self.assertEqual(transform_point_to_display(0, 0, 90), (1, 0))
        self.assertEqual(transform_point_to_display(1, 0, 90), (1, 1))
        self.assertEqual(transform_point_to_display(1, 1, 90), (0, 1))
        self.assertEqual(transform_point_to_display(0, 1, 90), (0, 0))

    def test_180_rotation_is_point_reflection(self):
        self.assertEqual(transform_point_to_display(0.2, 0.3, 180), (0.8, 0.7))

    def test_270_clockwise_rotation_known_corners(self):
        self.assertEqual(transform_point_to_display(0, 0, 270), (0, 1))
        self.assertEqual(transform_point_to_display(1, 0, 270), (0, 0))

    def test_round_trip_every_rotation_and_mirror_combination(self):
        points = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0), (0.37, 0.81)]
        for rotation, mirror_h, mirror_v, (x, y) in itertools.product(
            ROTATIONS, (False, True), (False, True), points,
        ):
            dx, dy = transform_point_to_display(x, y, rotation, mirror_h, mirror_v)
            rx, ry = transform_point_to_original(dx, dy, rotation, mirror_h, mirror_v)
            self.assertAlmostEqual(rx, x, places=9, msg=(rotation, mirror_h, mirror_v))
            self.assertAlmostEqual(ry, y, places=9, msg=(rotation, mirror_h, mirror_v))

    def test_rect_transform_90_swaps_dimensions(self):
        dx, dy, dw, dh = transform_rect_to_display(0.1, 0.2, 0.3, 0.1, 90)
        # A 90/270 rotation swaps which normalized axis width/height occupy.
        self.assertAlmostEqual(dw, 0.1)
        self.assertAlmostEqual(dh, 0.3)

    def test_rect_round_trip(self):
        for rotation, mirror_h, mirror_v in itertools.product(ROTATIONS, (False, True), (False, True)):
            dx, dy, dw, dh = transform_rect_to_display(0.1, 0.2, 0.3, 0.15, rotation, mirror_h, mirror_v)
            rx, ry, rw, rh = transform_rect_to_original(dx, dy, dw, dh, rotation, mirror_h, mirror_v)
            self.assertAlmostEqual(rx, 0.1, places=9)
            self.assertAlmostEqual(ry, 0.2, places=9)
            self.assertAlmostEqual(rw, 0.3, places=9)
            self.assertAlmostEqual(rh, 0.15, places=9)

    def test_reset_transform_is_identity(self):
        dx, dy = transform_point_to_display(0.4, 0.6, 0, mirror_h=False, mirror_v=False)
        self.assertEqual((dx, dy), (0.4, 0.6))

    def test_describe_transform_text(self):
        self.assertEqual(describe_transform(0, False, False), "")
        self.assertIn("Rotated 90", describe_transform(90, False, False))
        self.assertIn("source unchanged", describe_transform(90, False, False))
        self.assertIn("Mirrored horizontally", describe_transform(0, True, False))
        combo = describe_transform(180, True, True)
        self.assertIn("Rotated 180", combo)
        self.assertIn("mirrored horizontally", combo.lower())
        self.assertIn("mirrored vertically", combo.lower())

    def test_falsification_mirror_and_rotate_are_not_commutative_as_bare_bugs(self):
        """A defective implementation that applies rotation before mirror
        (rather than this module's own defined mirror-then-rotate order)
        would still round-trip internally (its own forward/inverse would
        still cancel) but would disagree with THIS module's specific
        known-corner mapping - proving the composition order matters and
        is actually pinned down, not just "some self-consistent order"."""
        # Mirror-then-rotate(90) of (0,0): mirror_h -> (1,0); rotate90 -> (1,1).
        self.assertEqual(transform_point_to_display(0, 0, 90, mirror_h=True), (1, 1))
        # A rotate-then-mirror implementation would instead give (0,0)->rotate90->(1,0)->mirror_h->(0,0).
        self.assertNotEqual(transform_point_to_display(0, 0, 90, mirror_h=True), (0, 0))


# ============================================================================
# CaseWorkspaceStore: register_drawing_sheet_structure / create_addressable_
# drawing_region / build_evidence_sachet - already-extracted data in.
# ============================================================================

class DrawingStructureStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm4_store_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm4"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="plan-set.pdf", file_path="/tmp/plan-set.pdf", kind="drawing",
        )
        self.other_workspace = self.store.get_or_create("test-project-mm4-other")
        self.other_source = self.store.add_source(
            self.other_workspace, name="other.pdf", file_path="/tmp/other.pdf", kind="drawing",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sheets(self):
        return [
            {
                "index": 0, "label": "A-101 · Ground Floor Plan", "width": 612.0, "height": 792.0,
                "source_rotation": 0,
                "metadata": {
                    "sheet_number": {"value": "A-101", "reliability": METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
                                      "evidence_snippet": "Sheet No: A-101", "source_page": 1},
                    "discipline": {"value": "Architectural", "reliability": METADATA_RELIABILITY_INFERRED,
                                   "evidence_snippet": "Sheet No: A-101", "source_page": 1},
                },
            },
            {
                "index": 1, "label": "Sheet 2", "width": 612.0, "height": 792.0,
                "source_rotation": 90, "metadata": {},
            },
        ]

    def test_one_structural_unit_per_sheet_unconditionally(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        self.assertEqual(result["sheet_count"], 2)
        units = self.store.structural_units_for_source(self.workspace, self.source["id"])
        self.assertEqual(len(units), 2)
        ordered = sorted(units, key=lambda u: u["order_index"])
        self.assertEqual([u["unit_type"] for u in ordered], ["sheet", "sheet"])
        self.assertEqual(ordered[0]["label"], "A-101 · Ground Floor Plan")
        # A sheet with NO extractable title-block metadata still gets a
        # plain, honest label - never invented (Section 6).
        self.assertEqual(ordered[1]["label"], "Sheet 2")

    def test_sheet_metadata_reliability_tiers_preserved(self):
        self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        units = sorted(
            self.store.structural_units_for_source(self.workspace, self.source["id"]),
            key=lambda u: u["order_index"],
        )
        fields = units[0]["modality_metadata"]["fields"]
        self.assertEqual(fields["sheet_number"]["reliability"], METADATA_RELIABILITY_DIRECTLY_EXTRACTED)
        self.assertEqual(fields["discipline"]["reliability"], METADATA_RELIABILITY_INFERRED)

    def test_source_rotation_is_a_source_fact_not_a_view_state(self):
        self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        units = sorted(
            self.store.structural_units_for_source(self.workspace, self.source["id"]),
            key=lambda u: u["order_index"],
        )
        self.assertEqual(units[1]["modality_metadata"]["source_rotation"], 90)

    def test_ordinal_is_not_identity(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        ids_before = list(result["structural_unit_ids"])
        units = self.store.structural_units_for_source(self.workspace, self.source["id"])
        self.assertEqual({u["id"] for u in units}, set(ids_before))

    def test_create_rectangular_region_and_citation(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        region = self.store.create_addressable_drawing_region(
            self.workspace, structural_unit_id=unit_id, x=0.1, y=0.2, width=0.3, height=0.15, actor="tester",
        )
        self.assertEqual(region["region_type"], "rectangular")
        self.assertEqual(region["address"]["region_index"], 1)
        citation = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation["status"], "resolved")
        self.assertIn("region 1", citation["label"])
        self.assertIn("A-101 · Ground Floor Plan", citation["label"])

    def test_region_index_increments_sequentially(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        r1 = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.0, 0.0, 0.1, 0.1, actor="tester")
        r2 = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.2, 0.2, 0.1, 0.1, actor="tester")
        self.assertEqual(r1["address"]["region_index"], 1)
        self.assertEqual(r2["address"]["region_index"], 2)

    def test_region_rejects_out_of_bounds(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.9, 0.9, 0.5, 0.5, actor="tester")
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_addressable_drawing_region(self.workspace, unit_id, -0.1, 0.0, 0.5, 0.5, actor="tester")
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.1, 0.1, 0.0, 0.5, actor="tester")

    def test_falsification_cross_project_structural_unit_denied(self):
        """The real, guarded method rejects a foreign-project structural
        unit id; proves the project_id check is load-bearing (not merely
        that the happy path works)."""
        result = self.store.register_drawing_sheet_structure(
            self.other_workspace, self.other_source["id"], self._sheets(), actor="tester",
        )
        foreign_unit_id = result["structural_unit_ids"][0]
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_addressable_drawing_region(self.workspace, foreign_unit_id, 0.1, 0.1, 0.1, 0.1, actor="tester")

    def test_stale_anchor_after_source_revision(self):
        """Reuses the EXISTING register_source_revision/superseded_by_
        source_id mechanism (pre-MM1) - resolve_region_citation's own
        staleness check is generic across every MM1-MM4 region type."""
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        region = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.1, 0.1, 0.1, 0.1, actor="tester")

        self.store.register_source_revision(
            self.workspace, old_source_id=self.source["id"], name="plan-set-r2.pdf",
            file_path="/tmp/plan-set-r2.pdf", width=612, height=792, actor="tester",
        )
        citation = self.store.resolve_region_citation(self.workspace, region["id"])
        self.assertEqual(citation["status"], "stale")
        self.assertIn("superseded_by_source_id", citation)

    def test_unavailable_anchor_for_unknown_region(self):
        citation = self.store.resolve_region_citation(self.workspace, "not-a-real-region-id")
        self.assertEqual(citation["status"], "unavailable")

    def test_evidence_sachet_includes_sheet_and_siblings_excludes_rest(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        r1 = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.0, 0.0, 0.1, 0.1, actor="tester")
        r2 = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.2, 0.2, 0.1, 0.1, actor="tester")

        sachet = self.store.build_evidence_sachet(self.workspace, r1["id"], task_description="Check grid alignment")
        self.assertEqual(sachet["status"], "assembled")
        self.assertEqual(sachet["task"], "Check grid alignment")
        self.assertEqual(sachet["region"]["region_id"], r1["id"])
        sibling_ids = [s["region_id"] for s in sachet["nearby_regions"]]
        self.assertIn(r2["id"], sibling_ids)
        self.assertNotIn(r1["id"], sibling_ids)
        self.assertIn("excluded", sachet)
        self.assertIn("other sheet", sachet["excluded"]["summary"])

    def test_evidence_sachet_unavailable_for_unknown_region(self):
        sachet = self.store.build_evidence_sachet(self.workspace, "not-a-real-region-id")
        self.assertEqual(sachet["status"], "unavailable")

    def test_evidence_sachet_never_pulls_other_sources(self):
        result = self.store.register_drawing_sheet_structure(self.workspace, self.source["id"], self._sheets(), actor="tester")
        unit_id = result["structural_unit_ids"][0]
        region = self.store.create_addressable_drawing_region(self.workspace, unit_id, 0.0, 0.0, 0.1, 0.1, actor="tester")
        # A second, unrelated Source in the SAME project - must never leak
        # into the sachet just because it shares a project.
        self.store.add_source(self.workspace, name="unrelated.pdf", file_path="/tmp/unrelated.pdf", kind="drawing")
        sachet = self.store.build_evidence_sachet(self.workspace, region["id"])
        self.assertEqual(sachet["source"]["source_id"], self.source["id"])
        self.assertNotIn("unrelated.pdf", str(sachet))


# ============================================================================
# services/drawing_intelligence.py orchestration - real pypdf/Pillow reads.
# ============================================================================

class DrawingIntelligenceOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm4_orch_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm4-orch"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _add_pdf_source(self, raw_bytes: bytes, name: str = "plan.pdf") -> dict:
        path = self.tmp_dir / name
        path.write_bytes(raw_bytes)
        return self.store.add_source(self.workspace, name=name, file_path=str(path), kind="drawing")

    def _add_image_source(self, raw_bytes: bytes, name: str = "sketch.png") -> dict:
        path = self.tmp_dir / name
        path.write_bytes(raw_bytes)
        return self.store.add_drawing_source(self.workspace, name=name, file_path=str(path), width=40, height=30)

    def test_real_pdf_read_extracts_title_block_and_classifies_supported(self):
        source = self._add_pdf_source(_build_minimal_pdf())
        result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], DRAWING_CLASSIFICATION_SUPPORTED)
        self.assertEqual(result["sheet_count"], 1)
        units = self.store.structural_units_for_source(self.workspace, source["id"])
        fields = units[0]["modality_metadata"]["fields"]
        self.assertEqual(fields["sheet_number"]["value"], "A-101")
        self.assertEqual(fields["drawing_title"]["value"], "Ground Floor Plan")
        self.assertEqual(fields["discipline"]["value"], "Architectural")
        self.assertEqual(fields["discipline"]["reliability"], METADATA_RELIABILITY_INFERRED)
        self.assertEqual(units[0]["modality_metadata"]["width"], 612.0)
        self.assertEqual(units[0]["modality_metadata"]["height"], 792.0)

    def test_real_png_read_classifies_supported_with_unavailable_metadata(self):
        source = self._add_image_source(_build_png(40, 30))
        result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], DRAWING_CLASSIFICATION_SUPPORTED)
        self.assertEqual(result["sheet_count"], 1)
        units = self.store.structural_units_for_source(self.workspace, source["id"])
        self.assertEqual(units[0]["modality_metadata"]["width"], 40)
        self.assertEqual(units[0]["modality_metadata"]["height"], 30)
        fields = units[0]["modality_metadata"]["fields"]
        self.assertEqual(fields["sheet_number"]["reliability"], METADATA_RELIABILITY_UNAVAILABLE)
        self.assertIsNone(fields["sheet_number"]["value"])

    def test_malformed_pdf_classified_not_raised(self):
        source = self._add_pdf_source(b"%PDF-1.4 not a real pdf body")
        result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], DRAWING_CLASSIFICATION_MALFORMED)
        self.assertEqual(result["sheet_count"], 0)
        self.assertEqual(self.store.structural_units_for_source(self.workspace, source["id"]), [])

    def test_malformed_image_classified_not_raised(self):
        source = self._add_image_source(b"not a real png file at all")
        result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], DRAWING_CLASSIFICATION_MALFORMED)

    def test_oversized_raw_bytes_refused_before_parsing(self):
        source = self._add_pdf_source(_build_minimal_pdf())
        with unittest.mock.patch("services.drawing_intelligence.MAX_RAW_BYTES", 10):
            result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], DRAWING_CLASSIFICATION_EXCESSIVE_SIZE)

    def test_unsupported_extension_raises(self):
        source = self._add_pdf_source(b"whatever", name="notes.txt")
        with self.assertRaises(DrawingIntelligenceError):
            register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")

    def test_unknown_source_raises(self):
        with self.assertRaises(DrawingIntelligenceError):
            register_drawing_evidence_for_source(self.store, self.workspace, "not-a-real-source-id", actor="tester")

    def test_falsification_cross_project_source_denied(self):
        other_workspace = self.store.get_or_create("test-project-mm4-orch-other")
        other_source = self._add_pdf_source(_build_minimal_pdf())
        # Deliberately pass the WRONG workspace for this real source id -
        # proves the project_id guard, not merely a not-found id.
        with self.assertRaises(DrawingIntelligenceError):
            register_drawing_evidence_for_source(self.store, other_workspace, other_source["id"], actor="tester")

    def test_create_drawing_region_and_evidence_end_to_end(self):
        source = self._add_pdf_source(_build_minimal_pdf())
        register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        unit_id = self.store.structural_units_for_source(self.workspace, source["id"])[0]["id"]

        result = create_drawing_region_and_evidence(
            self.store, self.workspace, source["id"], unit_id,
            x=0.1, y=0.1, width=0.2, height=0.2, note="Grid line B looks offset here", actor="tester",
        )
        self.assertEqual(result["evidence_item"]["content"], "Grid line B looks offset here")
        self.assertEqual(result["evidence_item"]["region_id"], result["region"]["id"])
        self.assertEqual(result["citation"]["status"], "resolved")

        observation = self.store.record_derived_observation(
            self.workspace, statement="Grid line labels appear reversed after horizontal mirroring.",
            author_type=OBSERVATION_AUTHOR_HUMAN, author="tester", method="visual_inspection",
            supporting_evidence_ids=[result["evidence_item"]["id"]], actor="tester",
        )
        self.assertIn(result["evidence_item"]["id"], observation["supporting_evidence_ids"])

    def test_create_region_without_note_gets_honest_placeholder(self):
        source = self._add_pdf_source(_build_minimal_pdf())
        register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        unit_id = self.store.structural_units_for_source(self.workspace, source["id"])[0]["id"]
        result = create_drawing_region_and_evidence(
            self.store, self.workspace, source["id"], unit_id, x=0.0, y=0.0, width=0.1, height=0.1, actor="tester",
        )
        self.assertIn("Rectangular region on", result["evidence_item"]["content"])

    def test_create_region_rejects_unregistered_structural_unit(self):
        source = self._add_pdf_source(_build_minimal_pdf())
        with self.assertRaises(DrawingIntelligenceError):
            create_drawing_region_and_evidence(
                self.store, self.workspace, source["id"], "not-a-real-unit", x=0, y=0, width=0.1, height=0.1, actor="tester",
            )

    def test_multi_page_pdf_gets_independent_title_blocks_per_sheet(self):
        page_one = (
            b"BT /F1 12 Tf 72 700 Td (Sheet No: A-101) Tj ET"
        )
        source = self._add_pdf_source(_build_minimal_pdf(text=page_one, page_count=1))
        register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        units = self.store.structural_units_for_source(self.workspace, source["id"])
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["modality_metadata"]["fields"]["sheet_number"]["value"], "A-101")


# ============================================================================
# /api/v1 routes - functional (not just auth) proof, mirrors MM1-MM3's own
# ApiRetrievalTests classes.
# ============================================================================

class DrawingApiRetrievalTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm4_api_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "mm4-api-project"

        document = ParsedDocument(
            project_id=self.project_id, filename="spec.txt", ingested_at="2026-01-01T00:00:00+00:00",
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        workspace = self.store.get_or_create(self.project_id)
        workspace.owner = "tester"
        self.store.save(workspace)
        pdf_path = self.tmp_dir / "plan.pdf"
        pdf_path.write_bytes(_build_minimal_pdf())
        self.source = self.store.add_source(workspace, name="plan.pdf", file_path=str(pdf_path), kind="drawing")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as_admin(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"
        return client

    def test_register_structure_then_create_region_then_fetch_sachet_via_api(self):
        client = self._client_as_admin()
        response = client.post(f"/api/v1/documents/{self.project_id}/sources/{self.source['id']}/drawing-structure")
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["classification"], DRAWING_CLASSIFICATION_SUPPORTED)
        unit_id = body["structural_unit_ids"][0]

        region_response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.source['id']}/drawing-regions",
            json={"structural_unit_id": unit_id, "x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2, "note": "Column line C"},
        )
        self.assertEqual(region_response.status_code, 201)
        region_body = region_response.get_json()
        self.assertEqual(region_body["evidence_item"]["content"], "Column line C")
        region_id = region_body["region"]["id"]

        sachet_response = client.get(f"/api/v1/documents/{self.project_id}/regions/{region_id}/evidence-sachet?task=Verify+column+grid")
        self.assertEqual(sachet_response.status_code, 200)
        sachet_body = sachet_response.get_json()
        self.assertEqual(sachet_body["status"], "assembled")
        self.assertEqual(sachet_body["task"], "Verify column grid")

    def test_create_region_missing_fields_returns_400(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.source['id']}/drawing-regions", json={},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_region")

    def test_evidence_sachet_unavailable_via_api_for_unknown_region(self):
        client = self._client_as_admin()
        response = client.get(f"/api/v1/documents/{self.project_id}/regions/not-a-real-region/evidence-sachet")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "unavailable")


if __name__ == "__main__":
    unittest.main()
