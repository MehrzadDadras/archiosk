"""CLAUDE-DOCUMENT-SHOP-OCR-READER-01 - the result must match stored evidence.

The defect: `_recovered()` read `content` / `content_type` / `evidence_class`
off `addressable_regions`, where those fields do not exist. A successfully
OCR-read image was therefore told "No text could be read from this image"
while its text sat in `evidence_items`, and its state read Needs attention.

WHY THE ORIGINAL TESTS DID NOT CATCH IT, which decides how these are written:
they built workspace records as hand-made dictionaries in the SAME shape the
reader assumed. A test that shares the code's assumption cannot falsify it.

So every record here is produced by the REAL writer -
`CaseWorkspaceStore.register_pdf_page_structure`, the one production path that
registers page text for both scanned images and PDFs - or by a real ingest.
Nothing below hand-builds a region or an evidence item.
"""
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw, ImageFont

from app import create_app
from services import document_examination as dx
from services import image_intake
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    EVIDENCE_CLASS_DIRECT_SOURCE, EVIDENCE_CLASS_EXTRACTED, CaseWorkspaceStore,
)

FALSE_CLAIM = "No text could be read"

OCR_LINES = ["FIRE DAMPER SCHEDULE", "ROOM 101 DETECTOR FD-1",
             "CLOSE ON ALARM", "SCALE 1 TO 50"]


def _ocr_fair_png():
    """Large, high-contrast, real font - a fair chance for any engine."""
    img = Image.new("RGB", (1400, 800), (255, 255, 255))
    d = ImageDraw.Draw(img)
    font = None
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            font = ImageFont.truetype(path, 64)
            break
        except Exception:
            continue
    for i, line in enumerate(OCR_LINES):
        d.text((90, 90 + i * 150), line, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _blank_png():
    buf = io.BytesIO()
    Image.new("RGB", (900, 600), (250, 250, 250)).save(buf, "PNG")
    return buf.getvalue()


def _doc(**kw):
    base = dict(project_id="p", filename="scan.png",
                ingested_at=datetime.now(timezone.utc).isoformat())
    base.update(kw)
    return ParsedDocument(**base)


class StoredShapeTests(unittest.TestCase):
    """What the REAL writer persists, asserted directly."""

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ocr_reader_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.ws = self.store.get_or_create(str(uuid.uuid4()))
        # Registered through the real API. Hand-appending a source dict was the
        # same class of error this whole tranche exists to correct - a record
        # built to the shape a reader expects rather than the shape the system
        # writes (add_source fills project_id, which a hand-made dict omitted).
        self.source_id = self._add_source("scan.png")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add_source(self, name):
        source = self.store.add_source(
            self.ws, name=name, file_path=str(self.tmp / name),
            kind="unclassified", actor="test")
        self.ws = self.store.get(self.ws.project_id)
        return source["id"] if isinstance(source, dict) else source

    def _register(self, pages, source_id=None, evidence_class=EVIDENCE_CLASS_EXTRACTED,
                  extractor="tesseract 4.1.1"):
        self.store.register_pdf_page_structure(
            self.ws, source_id=source_id or self.source_id, pages=pages,
            extractor_version=extractor, actor="test",
            evidence_class_by_page={i: evidence_class for i in range(len(pages))})
        self.ws = self.store.get(self.ws.project_id)

    # -- the shape itself ---------------------------------------------------

    def test_the_writer_puts_content_on_evidence_not_on_the_region(self):
        """The exact fact the defect got wrong, pinned against the real writer."""
        self._register(["FIRE DAMPER SCHEDULE"])
        region = self.ws.addressable_regions[0]
        evidence = self.ws.evidence_items[0]
        self.assertNotIn("content", region,
                         "a region carries addressing, never content")
        self.assertNotIn("content_type", region)
        self.assertEqual(evidence["content_type"], "text")
        self.assertIn("FIRE DAMPER", evidence["content"])
        self.assertEqual(evidence["region_id"], region["id"])
        self.assertEqual(evidence["source_id"], self.source_id)
        self.assertEqual(evidence["extractor_version"], "tesseract 4.1.1")

    def test_the_reader_finds_what_the_writer_stored(self):
        self._register(["FIRE DAMPER SCHEDULE\n\nROOM 101 DETECTOR FD-1"])
        got = dx._recovered(self.ws, self.source_id)
        self.assertEqual(got["passage_count"], 2)
        self.assertTrue(got["was_recovered"])
        self.assertIn("tesseract 4.1.1", got["read_by"])
        self.assertIn("FIRE DAMPER", got["preview"])

    def test_recovered_text_alone_is_limited_recovery_not_result_ready(self):
        """RETARGETED, CLAUDE-DOCUMENT-SHOP-FLOW-01.

        This asserted RESULT_READY the moment any passage existed. A Product
        Owner phone photo then produced "Result ready - 14,306 characters
        recovered" beside "No interpretation was reached", with OCR noise under
        a heading promising a reading. Text arriving is not a result; text
        arriving AND something being concluded from it is.

        What the test still protects is unchanged and is the reason it exists:
        recovered text must be SEEN by the reader (the bug it was written for
        was text being invisible). It is seen - the state now reflects it
        honestly instead of overclaiming.
        """
        self._register(["FIRE DAMPER SCHEDULE"])
        self.assertEqual(dx.state_of(_doc(), self.ws), dx.STATE_READ_NOT_INTERPRETED)
        self.assertTrue(dx._recovered(self.ws, self.source_id)["passage_count"])

    def test_the_result_no_longer_denies_text_it_holds(self):
        self._register(["FIRE DAMPER SCHEDULE"])
        result = dx.build_result(_doc(), self.ws, display_name="Scan")
        rendered = " ".join(
            i["label"] + " " + i["value"]
            for group in ("established", "interpretation", "not_established")
            for i in result[group])
        self.assertNotIn(FALSE_CLAIM, rendered)
        self.assertIn("Text recovered", rendered)
        self.assertIn("read from the image by tesseract 4.1.1", rendered)
        # Limited recovery, not Result ready: the text is reported, and nothing
        # was concluded from it. See the retargeted state test above.
        self.assertEqual(result["state"], dx.STATE_READ_NOT_INTERPRETED)
        self.assertIn("FIRE DAMPER", result["preview_text"])

    def test_direct_source_text_is_not_described_as_recovered_from_an_image(self):
        """A PDF's own text layer is the document speaking, not a reading."""
        self._register(["The contractor shall provide detection."],
                       evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
                       extractor="pypdf")
        got = dx._recovered(self.ws, self.source_id)
        self.assertFalse(got["was_recovered"])
        self.assertTrue(got["is_direct_source"])
        result = dx.build_result(_doc(filename="spec.pdf"), self.ws,
                                 display_name="Spec")
        rendered = " ".join(i["label"] + " " + i["value"] for i in result["established"])
        self.assertIn("carried by the document itself", rendered)
        self.assertNotIn("read from the image", rendered)

    # -- genuinely unreadable, preserved ------------------------------------

    def test_a_source_with_no_evidence_still_needs_attention(self):
        result = dx.build_result(_doc(text_extraction_status="no_native_text"),
                                 self.ws, display_name="Blank")
        self.assertEqual(result["state"], dx.STATE_NEEDS_ATTENTION)
        labels = " ".join(i["label"] for i in result["not_established"])
        self.assertIn(FALSE_CLAIM, labels,
                      "a genuinely unreadable image must still say so plainly")

    def test_whitespace_only_evidence_is_not_counted_as_recovered(self):
        self._register(["   \n\n   "])
        self.assertEqual(dx._recovered(self.ws, self.source_id)["passage_count"], 0)

    # -- Section 8: evidence scoping ----------------------------------------

    def test_evidence_from_another_source_never_appears_in_this_result(self):
        """Not ownership isolation - evidence-scoping correctness.

        Both sources live in ONE workspace belonging to ONE customer, so no
        access check can help here. Only correct scoping keeps them apart.
        """
        other_id = self._add_source("other.png")
        self._register(["SOURCE A CONFIDENTIAL SCHEDULE"])
        self._register(["SOURCE B UNRELATED CONTENT"], source_id=other_id)

        a = dx._recovered(self.ws, self.source_id)
        b = dx._recovered(self.ws, other_id)
        self.assertIn("SOURCE A", a["preview"])
        self.assertNotIn("SOURCE B", a["preview"])
        self.assertIn("SOURCE B", b["preview"])
        self.assertNotIn("SOURCE A", b["preview"])
        self.assertEqual(a["passage_count"], 1)
        self.assertEqual(b["passage_count"], 1)

        result = dx.build_result(_doc(), self.ws, display_name="A")
        self.assertNotIn("SOURCE B", result["preview_text"])

    def test_pages_are_read_in_order(self):
        self._register(["FIRST PAGE", "SECOND PAGE", "THIRD PAGE"])
        preview = dx._recovered(self.ws, self.source_id)["preview"]
        self.assertLess(preview.index("FIRST"), preview.index("SECOND"))
        self.assertLess(preview.index("SECOND"), preview.index("THIRD"))


class RealOcrIngestTests(unittest.TestCase):
    """The whole path: real image -> real OCR -> real registration -> result.

    Skipped where no OCR engine is installed, which is the same honest
    degradation the raster path already applies - never a fabricated pass.
    """

    def setUp(self):
        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_ocr_live_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, data, filename):
        from werkzeug.datastructures import FileStorage
        from services.case_workspace import CONTAINER_STATE_BLACK_BOX
        from services.ingestion import ingest_upload

        def fake_parse(_p, raw, name):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=name,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test", text_extraction_status="no_native_text")

        with patch.object(BHiveParser, "parse", fake_parse):
            return ingest_upload(
                FileStorage(stream=io.BytesIO(data), filename=filename),
                self.app, operating_environment=None,
                container_state=CONTAINER_STATE_BLACK_BOX, owner="tester")

    def test_a_real_ocr_read_image_reports_its_text_to_the_customer(self):
        probe = image_intake.extract_image_text(_ocr_fair_png(), "scan.png")
        if not probe.get("ran") or not (probe.get("text") or "").strip():
            self.skipTest("no OCR engine available: %r" % probe.get("reason"))

        document = self._ingest(_ocr_fair_png(), "fire-damper-schedule.png")
        store = CaseWorkspaceStore(self.app.config["REGISTRY_STORE_PATH"])
        workspace = store.get(document.project_id)

        # the evidence really is where production puts it
        evidence = [e for e in workspace.evidence_items
                    if e.get("content_type") == "text"]
        self.assertTrue(evidence, "real OCR produced no stored evidence")
        self.assertTrue(any("DAMPER" in (e.get("content") or "") for e in evidence))

        result = dx.build_result(document, workspace, display_name="Scan")
        rendered = " ".join(
            i["label"] + " " + i["value"]
            for group in ("established", "interpretation", "not_established")
            for i in result[group])
        self.assertNotIn(FALSE_CLAIM, rendered)
        self.assertEqual(result["state"], dx.STATE_READ_NOT_INTERPRETED)
        self.assertIn("DAMPER", result["preview_text"])

    def test_a_genuinely_blank_image_still_says_it_could_not_be_read(self):
        document = self._ingest(_blank_png(), "blank-scan.png")
        store = CaseWorkspaceStore(self.app.config["REGISTRY_STORE_PATH"])
        workspace = store.get(document.project_id)
        result = dx.build_result(document, workspace, display_name="Blank")
        self.assertEqual(result["state"], dx.STATE_NEEDS_ATTENTION)
        self.assertIn(FALSE_CLAIM,
                      " ".join(i["label"] for i in result["not_established"]))


if __name__ == "__main__":
    unittest.main()
