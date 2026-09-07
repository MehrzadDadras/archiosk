"""
CLAUDE-RASTER-OCR-01 - raster/OCR fallback for image-only PDFs.

THE FIXTURE IS REAL, THE ENGINE IS INJECTED

`_raster_pdf()` builds a genuine raster PDF: text is drawn, the page is
rendered to a pixmap, and the pixmap alone is placed in a fresh document. pypdf
then extracts nothing from it, because there genuinely is no text layer - the
same condition the real project drawing hit. That half is not simulated.

The OCR ENGINE is injected at `extract_raster_pages`'s own seam, because
Tesseract is an optional runtime binary and a test suite that only passes on
machines where someone installed it is not a regression test. This mirrors how
`google-genai` is already handled: drive the seam, and assert the honest
degrade when the dependency is absent.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services import raster_extraction as rx
from services.bhive_parser import BHiveParser
from services.case_workspace import CaseWorkspaceStore, SOURCE_KIND_PROJECT_DOCUMENT
from services.governance import GovernanceLog
from services.ingestion import _register_source_content


def _vector_pdf(pages: list) -> bytes:
    """A normal digital PDF WITH a text layer."""
    doc = pymupdf.open()
    for body in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), body, fontsize=11)
    out = doc.tobytes()
    doc.close()
    return out


def _raster_pdf(pages: list, rotate: int = 0) -> bytes:
    """A genuine image-only PDF - drawn, rendered, and re-embedded as pixels."""
    drawn = pymupdf.open()
    for body in pages:
        page = drawn.new_page(width=595, height=842)
        page.insert_text((72, 100), body, fontsize=14, rotate=rotate)

    rasterised = pymupdf.open()
    for index in range(drawn.page_count):
        pix = drawn.load_page(index).get_pixmap(dpi=110)
        page = rasterised.new_page(width=pix.width, height=pix.height)
        page.insert_image(pymupdf.Rect(0, 0, pix.width, pix.height),
                          stream=pix.tobytes("png"))
    out = rasterised.tobytes()
    drawn.close()
    rasterised.close()
    return out


class _FakePage:
    def __init__(self, text):
        self._text = text

    def get_textpage_ocr(self, dpi=200, full=True):
        return object()

    def get_text(self, textpage=None):
        return self._text


class _FakeDoc:
    def __init__(self, texts):
        self._texts = texts
        self.page_count = len(texts)

    def load_page(self, index):
        text = self._texts[index]
        if isinstance(text, Exception):
            raise text
        return _FakePage(text)

    def close(self):
        pass


class _FakeEngine:
    """Stands in for the pymupdf module at the injected seam."""

    def __init__(self, texts):
        self._texts = texts

    def open(self, stream=None, filetype=None):
        return _FakeDoc(self._texts)


def _engine(texts, name="tesseract", version="5.3.0"):
    return (name, version, _FakeEngine(texts))


class TriggerTests(unittest.TestCase):
    """B. The fallback must run only when it is actually needed."""

    def test_a_page_with_a_real_text_layer_does_not_trigger_fallback(self):
        self.assertEqual(rx.needs_raster_fallback(["A-101 GROUND FLOOR PLAN, GENERAL NOTES"]), [])

    def test_an_empty_page_triggers_fallback(self):
        self.assertEqual(rx.needs_raster_fallback([""]), [0])

    def test_a_stray_artefact_character_is_not_a_text_layer(self):
        """pypdf often yields a ligature or stamp fragment from a scan; treating
        that as a text layer is how a raster page silently skips its fallback."""
        self.assertEqual(rx.needs_raster_fallback(["  \n f "]), [0])

    def test_a_mixed_document_triggers_only_on_its_image_pages(self):
        pages = ["A-101 TITLE SHEET WITH REAL TEXT", "", "A-103 MORE REAL TEXT HERE"]
        self.assertEqual(rx.needs_raster_fallback(pages), [1])


class RealRasterFixtureTests(unittest.TestCase):
    """J. The fixture genuinely has no text layer."""

    def test_the_synthetic_raster_pdf_yields_no_native_text(self):
        raw = _raster_pdf(["A-101 GROUND FLOOR PLAN"])
        pages = BHiveParser.extract_pdf_pages(raw)
        self.assertEqual(rx.needs_raster_fallback(pages), [0],
                         "the fixture still carries a text layer, so it proves nothing")

    def test_the_vector_control_does_yield_native_text(self):
        """Guard-the-guard: if both fixtures were empty the trigger tests would
        pass for the wrong reason."""
        raw = _vector_pdf(["A-101 GROUND FLOOR PLAN GENERAL NOTES"])
        pages = BHiveParser.extract_pdf_pages(raw)
        self.assertEqual(rx.needs_raster_fallback(pages), [])


class ExtractionTests(unittest.TestCase):

    def test_recovered_text_is_returned_per_page(self):
        raw = _raster_pdf(["A-101 GROUND FLOOR PLAN"])
        result = rx.extract_raster_pages(raw, [0], engine=_engine(["A-101 GROUND FLOOR PLAN"]))
        self.assertTrue(result["ran"])
        self.assertEqual(result["status"], rx.RASTER_STATUS_READABLE)
        self.assertIn("A-101", result["pages"][0])
        self.assertEqual(result["engine"], "tesseract")
        self.assertEqual(result["engine_version"], "5.3.0")

    def test_a_partially_readable_document_is_review_needed_not_readable(self):
        raw = _raster_pdf(["one", "two"])
        result = rx.extract_raster_pages(raw, [0, 1], engine=_engine(["A-101 PLAN", ""]))
        self.assertEqual(result["status"], rx.RASTER_STATUS_REVIEW_NEEDED)
        self.assertEqual(list(result["pages"]), [0])

    def test_an_unreadable_document_says_so_rather_than_inventing_text(self):
        raw = _raster_pdf(["blurred"])
        result = rx.extract_raster_pages(raw, [0], engine=_engine([""]))
        self.assertEqual(result["status"], rx.RASTER_STATUS_UNREADABLE)
        self.assertEqual(result["pages"], {})
        self.assertTrue(result["reason"])

    def test_one_failing_page_does_not_lose_the_others(self):
        raw = _raster_pdf(["a", "b"])
        result = rx.extract_raster_pages(
            raw, [0, 1], engine=_engine([RuntimeError("render failed"), "A-102 RECOVERED"]))
        self.assertEqual(list(result["pages"]), [1])
        self.assertEqual(result["status"], rx.RASTER_STATUS_REVIEW_NEEDED)

    def test_an_absent_engine_degrades_honestly(self):
        """The live condition on any host without Tesseract installed."""
        raw = _raster_pdf(["A-101"])
        result = rx.extract_raster_pages(raw, [0], engine=None)
        availability = rx.ocr_availability()
        if availability["available"]:
            self.skipTest("Tesseract is installed on this host; nothing to degrade.")
        self.assertFalse(result["ran"])
        self.assertEqual(result["status"], rx.RASTER_STATUS_UNREADABLE)
        self.assertIn("Tesseract", result["reason"])
        self.assertEqual(result["pages"], {})

    def test_availability_never_raises(self):
        self.assertIn("available", rx.ocr_availability())


class DeduplicationTests(unittest.TestCase):
    """C, and item 13: native always wins; no page carries two extractions."""

    def test_native_text_is_never_overwritten_by_ocr(self):
        merged = rx.merge_pages(["REAL NATIVE TEXT ON THIS PAGE", ""],
                                {0: "OCR VERSION", 1: "OCR RECOVERED"})
        self.assertEqual(merged[0], "REAL NATIVE TEXT ON THIS PAGE")
        self.assertEqual(merged[1], "OCR RECOVERED")

    def test_an_out_of_range_page_is_ignored(self):
        self.assertEqual(rx.merge_pages([""], {5: "nowhere"}), [""])


class IngestionIntegrationTests(unittest.TestCase):
    """L. The derived content enters the SAME governed path native text uses."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_ocr_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-ocr")
        self.parser = BHiveParser(anthropic_api_key=None)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _source(self, name):
        path = self.tmp_dir / name
        path.write_bytes(b"placeholder")
        return self.store.add_source(
            self.workspace, name=name, file_path=str(path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, actor="tester")

    def _register(self, raw, name="drawing.pdf"):
        source = self._source(name)
        status, reason = _register_source_content(
            self.store, self.workspace, source, raw, name, self.parser,
            actor="tester", governance_log=self.gov)
        return source, status, reason

    def test_a_native_pdf_is_unaffected_by_the_fallback(self):
        """A. Native extraction behaviour must not change."""
        raw = _vector_pdf(["A-101 GROUND FLOOR PLAN WITH REAL EMBEDDED TEXT"])
        _source, status, reason = self._register(raw, "vector.pdf")
        self.assertEqual(status, "added")
        self.assertIsNone(reason)

    def test_a_raster_pdf_without_an_engine_fails_honestly(self):
        """D. The live condition today: no OCR engine installed."""
        if rx.ocr_availability()["available"]:
            self.skipTest("Tesseract is installed on this host.")
        raw = _raster_pdf(["A-101 GROUND FLOOR PLAN"])
        _source, status, reason = self._register(raw, "raster.pdf")
        self.assertEqual(status, "skipped")
        self.assertTrue(reason)
        self.assertNotIn("no readable text", reason,
                         "a raster drawing was reported as an unreadable document")

    def test_the_source_is_still_registered_when_extraction_fails(self):
        raw = _raster_pdf(["A-101"])
        source, status, _reason = self._register(raw, "raster2.pdf")
        refreshed = self.store.get(self.workspace.project_id)
        self.assertTrue(any(s["id"] == source["id"] for s in refreshed.sources),
                        "the original Source was lost when extraction failed")

    def test_a_mixed_pdf_registers_its_readable_pages(self):
        """C. Native pages survive even when the image pages cannot be read."""
        if rx.ocr_availability()["available"]:
            self.skipTest("Tesseract is installed; this asserts the no-engine path.")
        vector = pymupdf.open(stream=_vector_pdf(["A-101 REAL TEXT PAGE ONE HERE"]),
                              filetype="pdf")
        raster = pymupdf.open(stream=_raster_pdf(["A-102 IMAGE ONLY"]), filetype="pdf")
        vector.insert_pdf(raster)
        raw = vector.tobytes()
        vector.close()
        raster.close()

        source, status, _reason = self._register(raw, "mixed.pdf")
        self.assertEqual(status, "added",
                         "a partly-readable document was discarded entirely")
        refreshed = self.store.get(self.workspace.project_id)
        units = [u for u in refreshed.structural_units if u["source_id"] == source["id"]]
        self.assertEqual(len(units), 2,
                         "an image-only page lost its identity as a real page")

    def test_reprocessing_the_same_bytes_creates_no_duplicate_evidence(self):
        """G. Same file twice - each registration is its own Source, and neither
        gains duplicate evidence for the same page."""
        raw = _vector_pdf(["A-101 REAL TEXT FOR THE DUPLICATE CHECK"])
        first, _s1, _r1 = self._register(raw, "dup-a.pdf")
        refreshed = self.store.get(self.workspace.project_id)
        first_units = len([u for u in refreshed.structural_units
                           if u["source_id"] == first["id"]])
        self.workspace = refreshed
        second, _s2, _r2 = self._register(raw, "dup-b.pdf")
        final = self.store.get(self.workspace.project_id)
        self.assertEqual(
            len([u for u in final.structural_units if u["source_id"] == first["id"]]),
            first_units, "re-registering duplicated the first Source's evidence")
        self.assertNotEqual(first["id"], second["id"])

    def test_cross_project_isolation(self):
        """H."""
        raw = _vector_pdf(["A-101 ISOLATION CHECK REAL TEXT"])
        self._register(raw, "iso.pdf")
        other = self.store.get_or_create("test-project-ocr-other")
        self.assertEqual(other.sources, [])
        self.assertEqual(other.structural_units, [])


class ProvenanceTests(unittest.TestCase):
    """E. Recovered text must be distinguishable from native text."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_ocr_prov_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-ocr-prov")
        self.parser = BHiveParser(anthropic_api_key=None)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_the_extractor_version_names_the_ocr_engine(self):
        """The one string that tells a reader this text was READ, not written -
        driven through the real ingestion helper with an injected engine."""
        from services import ingestion
        raw = _raster_pdf(["A-101 GROUND FLOOR PLAN"])
        path = self.tmp_dir / "ocr.pdf"
        path.write_bytes(raw)
        source = self.store.add_source(
            self.workspace, name="ocr.pdf", file_path=str(path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, actor="tester")

        real = rx.extract_raster_pages

        def fake_extract(raw_bytes, indices, dpi=rx.RENDER_DPI, engine=None):
            return real(raw_bytes, indices, dpi=dpi,
                        engine=_engine(["A-101 GROUND FLOOR PLAN RECOVERED"]))

        rx.extract_raster_pages = fake_extract
        try:
            status, _reason = ingestion._register_source_content(
                self.store, self.workspace, source, raw, "ocr.pdf", self.parser,
                actor="tester", governance_log=self.gov)
        finally:
            rx.extract_raster_pages = real

        self.assertEqual(status, "added")
        refreshed = self.store.get(self.workspace.project_id)
        evidence = [e for e in refreshed.evidence_items if e["source_id"] == source["id"]]
        self.assertTrue(evidence, "no evidence was registered from recovered text")
        self.assertTrue(
            any("tesseract" in (e.get("extractor_version") or "") for e in evidence),
            "recovered text was not marked as OCR-derived")

    def test_the_original_source_bytes_are_never_modified(self):
        raw = _raster_pdf(["A-101"])
        path = self.tmp_dir / "immutable.pdf"
        path.write_bytes(raw)
        before = path.read_bytes()
        source = self.store.add_source(
            self.workspace, name="immutable.pdf", file_path=str(path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, actor="tester")
        from services import ingestion
        ingestion._register_source_content(
            self.store, self.workspace, source, raw, "immutable.pdf", self.parser,
            actor="tester", governance_log=self.gov)
        self.assertEqual(path.read_bytes(), before,
                         "extraction modified the original document")


class UserMessageTests(unittest.TestCase):
    """G (UX). Three honest outcomes, none of them silent."""

    def test_each_status_has_its_own_message(self):
        messages = {
            rx.user_message(rx.RASTER_STATUS_READABLE, 2, 2),
            rx.user_message(rx.RASTER_STATUS_REVIEW_NEEDED, 1, 2),
            rx.user_message(rx.RASTER_STATUS_UNREADABLE, 0, 2),
        }
        self.assertEqual(len(messages), 3)

    def test_the_success_message_still_warns_that_review_may_be_needed(self):
        self.assertIn("review", rx.user_message(rx.RASTER_STATUS_READABLE, 1, 1).lower())


if __name__ == "__main__":
    unittest.main()
