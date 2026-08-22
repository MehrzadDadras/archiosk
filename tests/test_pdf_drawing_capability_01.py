"""Focused contracts for PDF drawing capability gating.

These tests intentionally inspect the small renderer seam rather than attempt
to run a browser: the server-side structural-unit and MM6/MM7 contracts are
covered by their existing lanes.
"""

from pathlib import Path
import unittest


PDF_VIEWER = Path(__file__).parents[1] / "static" / "js" / "pdf_viewer.js"
WORKSPACE_TEMPLATE = Path(__file__).parents[1] / "templates" / "case_workspace.html"
IMAGE_VIEWER = Path(__file__).parents[1] / "static" / "js" / "drawing_image_viewer.js"


class PdfDrawingCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf = PDF_VIEWER.read_text(encoding="utf-8")
        cls.template = WORKSPACE_TEMPLATE.read_text(encoding="utf-8")
        cls.image = IMAGE_VIEWER.read_text(encoding="utf-8")

    def test_sheet_is_the_only_structural_capability_predicate(self):
        self.assertIn("function hasSheetEvidence(units)", self.pdf)
        self.assertIn("unit.unit_type === 'sheet'", self.pdf)
        self.assertIn("hasSheetEvidence(units)", self.pdf)
        self.assertNotIn("is_drawing", self.pdf)
        self.assertNotIn("drawing-capable", self.pdf)

    def test_predicate_cases_are_explicitly_represented(self):
        # The deterministic predicate is array-safe and checks only sheet;
        # document-only and empty structural-unit payloads therefore remain
        # unavailable while mixed payloads are available.
        self.assertIn("Array.isArray(units)", self.pdf)
        self.assertIn("if (!available)", self.pdf)
        self.assertIn("unit.unit_type === 'sheet'", self.pdf)

    def test_pdf_surface_uses_existing_evidence_item_anchor(self):
        self.assertIn("result.body.evidence_item && result.body.evidence_item.id", self.pdf)
        self.assertIn("from_type: 'evidence_item', from_id: evidenceId", self.pdf)
        self.assertIn("anchor_object_type: 'evidence_item', anchor_object_id: evidenceId", self.pdf)
        self.assertIn("/relationships?object_type=evidence_item", self.pdf)
        self.assertIn("/investigations", self.pdf)

    def test_relationship_actions_remain_explicit_and_server_gated(self):
        self.assertIn("/relationships/' + encodeURIComponent(rel.id) + '/' + verb", self.pdf)
        self.assertIn("['confirm', 'dispute', 'reject']", self.pdf)
        self.assertIn("method: 'POST'", self.pdf)

    def test_viewer_and_source_classification_contracts_are_unchanged(self):
        self.assertIn("data-pdf-url", self.template)
        self.assertIn("data-source-id", self.template)
        self.assertIn("drawing_image_viewer.js", self.template)
        self.assertIn("window.ArchioskPdfViewer", self.pdf)
        self.assertNotIn("source.kind =", self.pdf)
        self.assertIn("function mount(imgEl)", self.image)

    def test_capability_is_limited_to_existing_main_pdf_surface(self):
        self.assertIn("if (name !== 'main' || !currentCanvasContainer) return;", self.pdf)
        self.assertIn("drawingCapabilityPanel", self.pdf)
        self.assertIn("drawingCapabilityEvidenceId = null", self.pdf)


if __name__ == "__main__":
    unittest.main()
