"""
CLAUDE-MM2 (PDF and Document Intelligence) tests: CaseWorkspaceStore.
register_pdf_page_structure (already-extracted pages -> governed MM1
evidence) and services/pdf_intelligence.register_pdf_evidence_for_source
(the real pypdf read -> classification -> registration orchestration).

Mirrors this repository's established hermetic pattern for PDF-adjacent
code (tests/test_p40vw8qa_r2a_drawing_intake.py): mock BHiveParser.
extract_pdf_pages for orchestration-level tests rather than shipping real
PDF binary fixtures, EXCEPT one deliberate full-stack test using a real,
hand-built, minimal valid PDF (~600 bytes, embedded below) to prove the
real pypdf call path end-to-end at least once.

Run via:

    python -m unittest tests.test_mm2_pdf_document_intelligence -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pypdf.errors import PdfReadError

from services.bhive_parser import BHiveParser
from services.case_workspace import (
    EVIDENCE_CLASS_DIRECT_SOURCE,
    KNOWN_PDF_CLASSIFICATIONS,
    OBSERVATION_AUTHOR_HUMAN,
    PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    PDF_CLASSIFICATION_EXTRACTION_FAILED,
    PDF_CLASSIFICATION_IMAGE_ONLY,
    PDF_CLASSIFICATION_MIXED,
    PDF_CLASSIFICATION_TEXT_NATIVE,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ConcurrentModificationError,
)
from services.governance import GovernanceLog
from services.pdf_intelligence import PdfIntelligenceError, register_pdf_evidence_for_source

# A real, valid, minimal one-page PDF with genuine embedded text ("Hello MM2
# World") - hand-built (no reportlab/fpdf dependency added), used for the
# one deliberate real-file test below. Confirmed to parse correctly with
# the installed pypdf during this stage's own development.
_REAL_MINIMAL_PDF_TEXT = b"BT /F1 24 Tf 72 100 Td (Hello MM2 World) Tj ET"


def _build_minimal_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> "
        b"/MediaBox [0 0 300 144] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(_REAL_MINIMAL_PDF_TEXT), _REAL_MINIMAL_PDF_TEXT),
    ]
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


class PdfPageStructureStoreTests(unittest.TestCase):
    """CaseWorkspaceStore.register_pdf_page_structure - already-extracted
    pages in, governed StructuralUnit/AddressableRegion/EvidenceItem out.
    No pypdf/PDF bytes involved at this layer, mirroring register_table_
    evidence's own already-parsed-input shape."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm2_store_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm2"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="spec.pdf", file_path="/tmp/spec.pdf", kind="project_document",
        )
        self.other_workspace = self.store.get_or_create("test-project-mm2-other")
        self.other_source = self.store.add_source(
            self.other_workspace, name="other.pdf", file_path="/tmp/other.pdf", kind="project_document",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_page_structural_units_and_ordering(self):
        pages = ["Page one text.", "Page two text.", "Page three text."]
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages, actor="tester")
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_TEXT_NATIVE)
        self.assertEqual(len(result["structural_unit_ids"]), 3)
        units = self.store.structural_units_for_source(self.workspace, self.source["id"])
        self.assertEqual(len(units), 3)
        ordered = sorted(units, key=lambda u: u["order_index"])
        self.assertEqual([u["order_index"] for u in ordered], [0, 1, 2])
        self.assertEqual([u["label"] for u in ordered], ["Page 1", "Page 2", "Page 3"])
        # Ordinal is not identity - reordering never changes id.
        self.assertEqual(len({u["id"] for u in units}), 3)

    def test_addressable_region_identity_and_page_linkage(self):
        pages = ["First paragraph.\n\nSecond paragraph."]
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages)
        self.assertEqual(len(result["addressable_region_ids"]), 2)
        unit_id = result["structural_unit_ids"][0]
        regions = self.store.regions_for_structural_unit(self.workspace, unit_id)
        self.assertEqual(len(regions), 2)
        for region in regions:
            self.assertEqual(region["structural_unit_id"], unit_id)
            self.assertEqual(region["region_type"], "paragraph")
        addresses = sorted(r["address"]["paragraph_index"] for r in regions)
        self.assertEqual(addresses, [0, 1])

    def test_extracted_text_to_page_linkage_in_evidence(self):
        pages = ["Alpha content.", "Beta content."]
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages, actor="tester")
        evidence = [self.store.get_evidence_item(self.workspace, eid) for eid in result["evidence_item_ids"]]
        contents = sorted(e["content"] for e in evidence)
        self.assertEqual(contents, ["Alpha content.", "Beta content."])
        for e in evidence:
            self.assertEqual(e["evidence_class"], EVIDENCE_CLASS_DIRECT_SOURCE)
            self.assertEqual(e["source_id"], self.source["id"])
            self.assertEqual(e["created_by"], "tester")
            region = self.store.get_addressable_region(self.workspace, e["region_id"])
            self.assertIsNotNone(region)

    def test_pdf_classification_text_native_image_only_mixed(self):
        self.assertEqual(
            self.store.register_pdf_page_structure(self.workspace, self.source["id"], ["real text"])["classification"],
            PDF_CLASSIFICATION_TEXT_NATIVE,
        )
        source2 = self.store.add_source(self.workspace, name="scan.pdf", file_path="/tmp/scan.pdf", kind="project_document")
        self.assertEqual(
            self.store.register_pdf_page_structure(self.workspace, source2["id"], ["", "   "])["classification"],
            PDF_CLASSIFICATION_IMAGE_ONLY,
        )
        source3 = self.store.add_source(self.workspace, name="mixed.pdf", file_path="/tmp/mixed.pdf", kind="project_document")
        self.assertEqual(
            self.store.register_pdf_page_structure(self.workspace, source3["id"], ["real text", ""])["classification"],
            PDF_CLASSIFICATION_MIXED,
        )
        self.assertEqual(set(KNOWN_PDF_CLASSIFICATIONS), {
            PDF_CLASSIFICATION_TEXT_NATIVE, PDF_CLASSIFICATION_IMAGE_ONLY, PDF_CLASSIFICATION_MIXED,
            PDF_CLASSIFICATION_EXTRACTION_FAILED, PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
        })

    def test_image_only_page_still_gets_a_real_structural_unit(self):
        """Section 11: 'do not claim no usable document merely because
        text is absent' - a page with no text is still a real, addressable
        StructuralUnit, just with zero regions/evidence."""
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], ["", ""])
        self.assertEqual(len(result["structural_unit_ids"]), 2)
        self.assertEqual(result["addressable_region_ids"], [])
        self.assertEqual(result["evidence_item_ids"], [])

    def test_citation_rendering_page_and_paragraph(self):
        pages = ["", "Second page paragraph one.\n\nSecond page paragraph two."]
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages)
        region_id = result["addressable_region_ids"][1]
        citation = self.store.resolve_region_citation(self.workspace, region_id)
        self.assertEqual(citation["status"], "resolved")
        self.assertIn("spec.pdf", citation["label"])
        self.assertIn("Page 2", citation["label"])
        self.assertIn("paragraph 2", citation["label"])

    def test_source_version_binding_stale_citation_on_supersession(self):
        pages = ["Original content."]
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], pages)
        region_id = result["addressable_region_ids"][0]
        self.store.register_source_revision(
            self.workspace, self.source["id"], name="spec-v2.pdf", file_path="/tmp/spec-v2.pdf",
            width=0, height=0, actor="tester",
        )
        citation = self.store.resolve_region_citation(self.workspace, region_id)
        self.assertEqual(citation["status"], "stale")
        self.assertIn("superseded_by_source_id", citation)
        # The old citation is PRESERVED, not destroyed - label still renders.
        self.assertIn("spec.pdf", citation["label"])

    def test_broken_unresolved_anchor_states(self):
        self.assertEqual(
            self.store.resolve_region_citation(self.workspace, "does-not-exist")["status"], "unavailable",
        )
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], ["text"])
        region_id = result["addressable_region_ids"][0]
        live_source = self.store._find(self.workspace.sources, self.source["id"])
        live_source["removed_at"] = "2026-08-06T00:00:00+00:00"
        self.store.save(self.workspace)
        self.assertEqual(self.store.resolve_region_citation(self.workspace, region_id)["status"], "unavailable")

    def test_cross_project_denial(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_pdf_page_structure(self.workspace, self.other_source["id"], ["text"])
        # Falsification: a foreign region is honestly "unavailable" from
        # this project's own workspace, never resolved against the wrong
        # project's structural unit/source.
        foreign_result = self.store.register_pdf_page_structure(self.other_workspace, self.other_source["id"], ["x"])
        foreign_region_id = foreign_result["addressable_region_ids"][0]
        self.assertEqual(
            self.store.resolve_region_citation(self.workspace, foreign_region_id)["status"], "unavailable",
        )

    def test_falsification_cross_project_guard_is_real(self):
        """Prove register_pdf_page_structure's own project_id check is
        load-bearing, not incidental - a version that skips it (calling
        the same dataclasses/append/save sequence directly, bypassing the
        real guarded method) succeeds where the real method correctly
        raises, mirroring the identical falsification MM1's own
        DerivedObservation tests already established."""
        from dataclasses import asdict
        from services.case_workspace import StructuralUnit, _new_id, _now

        def unguarded_register(workspace, source_id, pages):
            unit = StructuralUnit(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                unit_type="page", order_index=0, created_at=_now(), created_by="tester",
                label="Page 1",
            )
            workspace.structural_units.append(asdict(unit))
            self.store.save(workspace)
            return unit.id

        unit_id = unguarded_register(self.workspace, self.other_source["id"], ["x"])
        self.assertTrue(unit_id)  # the unguarded bypass "succeeded" against a foreign source id
        # ... but the real, guarded method correctly rejects the same input.
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_pdf_page_structure(self.workspace, self.other_source["id"], ["x"])

    def test_persistence_round_trip(self):
        result = self.store.register_pdf_page_structure(self.workspace, self.source["id"], ["p1", "p2"], actor="tester")
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.structural_units), 2)
        self.assertEqual(len(reloaded.evidence_items), 2)
        self.assertEqual(reloaded.structural_units[0]["id"], result["structural_unit_ids"][0])

    def test_backward_compatibility_legacy_workspace(self):
        """A pre-MM1/MM2 workspace JSON simply lacks the new keys and
        loads with the empty-list default - same convention every prior
        addition already establishes."""
        import json
        path = self.store._path_for(self.project_id)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("structural_units", "addressable_regions", "evidence_items"):
            data.pop(key, None)
        path.write_text(json.dumps(data), encoding="utf-8")
        reloaded = self.store.get(self.project_id)
        result = self.store.register_pdf_page_structure(reloaded, self.source["id"], ["text"])
        self.assertTrue(result["structural_unit_ids"])

    def test_concurrent_modification_is_detected(self):
        copy_a = self.store.get(self.project_id)
        copy_b = self.store.get(self.project_id)
        self.store.register_pdf_page_structure(copy_a, self.source["id"], ["a"])
        with self.assertRaises(ConcurrentModificationError):
            self.store.register_pdf_page_structure(copy_b, self.source["id"], ["b"])

    def test_direct_evidence_vs_derived_observation_via_real_pdf_flow(self):
        """Section 14: use real MM2 evidence to exercise, not merge, the
        Finding/DerivedObservation distinction. A DerivedObservation built
        from PDF-sourced EvidenceItems stays clearly distinguishable from
        the evidence itself."""
        result = self.store.register_pdf_page_structure(
            self.workspace, self.source["id"], ["The contractor shall provide tempered glazing."],
        )
        evidence_id = result["evidence_item_ids"][0]
        observation = self.store.record_derived_observation(
            self.workspace, statement="This page imposes a tempered-glazing requirement.",
            author_type=OBSERVATION_AUTHOR_HUMAN, author="tester", method="manual review",
            supporting_evidence_ids=[evidence_id],
        )
        self.assertIn(evidence_id, observation["supporting_evidence_ids"])
        evidence = self.store.get_evidence_item(self.workspace, evidence_id)
        self.assertNotIn("author_type", evidence)
        self.assertNotIn("supporting_evidence_ids", evidence)


class PdfIntelligenceOrchestrationTests(unittest.TestCase):
    """services/pdf_intelligence.register_pdf_evidence_for_source - the
    real pypdf read boundary. Mocks BHiveParser.extract_pdf_pages for
    every case except test_real_pdf_file_end_to_end below."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm2_orch_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm2-orch"
        self.workspace = self.store.get_or_create(self.project_id)
        self.pdf_path = self.tmp_dir / "doc.pdf"
        self.pdf_path.write_bytes(b"%PDF-1.4 placeholder bytes")
        self.source = self.store.add_source(
            self.workspace, name="doc.pdf", file_path=str(self.pdf_path), kind="project_document",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_text_native_classification_and_metadata_backfill(self):
        with patch.object(BHiveParser, "extract_pdf_pages", staticmethod(lambda raw: ["Real page text."])):
            result = register_pdf_evidence_for_source(self.store, self.workspace, self.source["id"], actor="tester")
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_TEXT_NATIVE)
        reloaded = self.store.get(self.project_id)
        source = self.store._find(reloaded.sources, self.source["id"])
        self.assertEqual(source["mime_type"], "application/pdf")
        self.assertEqual(source["size_bytes"], len(b"%PDF-1.4 placeholder bytes"))
        self.assertTrue(source["extractor_version"].startswith("pypdf:"))

    def test_image_only_classification(self):
        with patch.object(BHiveParser, "extract_pdf_pages", staticmethod(lambda raw: ["", ""])):
            result = register_pdf_evidence_for_source(self.store, self.workspace, self.source["id"])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_IMAGE_ONLY)

    def test_encrypted_pdf_classification_without_corrupting_source(self):
        from pypdf.errors import FileNotDecryptedError

        def _raise(raw):
            raise FileNotDecryptedError("encrypted")

        with patch.object(BHiveParser, "extract_pdf_pages", staticmethod(_raise)):
            result = register_pdf_evidence_for_source(self.store, self.workspace, self.source["id"])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED)
        # Parser failure must not corrupt the Source record - it's still
        # exactly as it was, no partial/fabricated metadata written.
        reloaded = self.store.get(self.project_id)
        source = self.store._find(reloaded.sources, self.source["id"])
        self.assertIsNone(source.get("mime_type"))
        self.assertEqual(reloaded.structural_units, [])

    def test_malformed_pdf_classification_without_corrupting_source(self):
        def _raise(raw):
            raise PdfReadError("malformed")

        with patch.object(BHiveParser, "extract_pdf_pages", staticmethod(_raise)):
            result = register_pdf_evidence_for_source(self.store, self.workspace, self.source["id"])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_EXTRACTION_FAILED)
        reloaded = self.store.get(self.project_id)
        self.assertEqual(reloaded.structural_units, [])

    def test_falsification_unexpected_exception_still_classified_not_crashed(self):
        """Prove the broad except Exception fallback is real: an error
        type outside pypdf's own hierarchy is still honestly classified,
        never a raw 500-shaped crash."""
        def _raise(raw):
            raise ValueError("some lower-level stream corruption")

        with patch.object(BHiveParser, "extract_pdf_pages", staticmethod(_raise)):
            result = register_pdf_evidence_for_source(self.store, self.workspace, self.source["id"])
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_EXTRACTION_FAILED)

    def test_non_pdf_source_is_rejected(self):
        txt_source = self.store.add_source(
            self.workspace, name="notes.txt", file_path=str(self.tmp_dir / "notes.txt"), kind="project_document",
        )
        with self.assertRaises(PdfIntelligenceError):
            register_pdf_evidence_for_source(self.store, self.workspace, txt_source["id"])

    def test_source_with_no_stored_file_is_rejected(self):
        no_file_source = self.store.add_source(
            self.workspace, name="ghost.pdf", file_path=None, kind="project_document",
        )
        with self.assertRaises(PdfIntelligenceError):
            register_pdf_evidence_for_source(self.store, self.workspace, no_file_source["id"])

    def test_cross_project_source_is_rejected(self):
        other_workspace = self.store.get_or_create("test-project-mm2-orch-other")
        other_source = self.store.add_source(
            other_workspace, name="other.pdf", file_path=str(self.pdf_path), kind="project_document",
        )
        with self.assertRaises(PdfIntelligenceError):
            register_pdf_evidence_for_source(self.store, self.workspace, other_source["id"])

    def test_real_pdf_file_end_to_end(self):
        """The one deliberate real-file test - a genuine, hand-built,
        valid PDF with real embedded text, read through the real,
        unmocked pypdf call path."""
        real_pdf_path = self.tmp_dir / "real.pdf"
        real_pdf_path.write_bytes(_build_minimal_pdf())
        real_source = self.store.add_source(
            self.workspace, name="real.pdf", file_path=str(real_pdf_path), kind="project_document",
        )
        result = register_pdf_evidence_for_source(self.store, self.workspace, real_source["id"], actor="tester")
        self.assertEqual(result["classification"], PDF_CLASSIFICATION_TEXT_NATIVE)
        reloaded = self.store.get(self.project_id)
        evidence = [e for e in reloaded.evidence_items if e["source_id"] == real_source["id"]]
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["content"], "Hello MM2 World")
        region_id = evidence[0]["region_id"]
        citation = self.store.resolve_region_citation(reloaded, region_id)
        self.assertEqual(citation["status"], "resolved")
        self.assertEqual(citation["label"], "real.pdf · Page 1 · paragraph 1")


if __name__ == "__main__":
    unittest.main()
