"""CLAUDE-GO-PERCEPTION-PDF-OCR-01: the sources clients actually send.

The real ARCHIOSK drawing corpus is predominantly raster. Of every real sheet
available to this project, all but one carries no native text layer at all — so
a pipeline that positions only STANDALONE IMAGES cannot see a real drawing set.
`ingestion` has been enqueueing perception jobs for PDFs all along; they were
terminating at a file-type gate.

What these tests defend, in the order the mistakes would be made:

1. **PAGE n MUST BIND TO PAGE n.** The pre-existing writer took the Source's
   FIRST page unit. That is correct for a one-frame image and silently wrong for
   a document: every page's lines would have landed on page 1, with geometry
   that looks entirely plausible while pointing at the wrong sheet. `PageBinding`
   is the largest class here on purpose, and it is the reason this tranche
   exists at all.

2. **The exactly-once re-check must be per PAGE, not per Source.** Scoped to the
   Source, page 1 writes and every later page reports an already-done replay —
   producing a document positioned on its first page only, which is a wrong
   result wearing a successful one's clothes.

3. **No second OCR pass, no magnitude.** The word boxes recovered here were
   already being produced and discarded. Nothing derives a physical dimension
   from page geometry: Product Owner decision 2026-09-11, Option C.

The OCR engine is injected at the same seam every other perception test uses, so
none of this needs Tesseract, a real PDF render, or a network.
"""
from __future__ import annotations

import ast
import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services import perception_worker, positioned_text
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, EVIDENCE_CLASS_EXTRACTED, CaseWorkspaceStore,
)
from services.ingestion import attach_document_shop_sources, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _words_for(page_index, count=4):
    """PyMuPDF-shaped word tuples: (x0, y0, x1, y1, text, block, line, word).

    The text names its own page, which is what makes a mis-binding visible
    rather than merely possible.
    """
    words = []
    for i in range(count):
        y = 100.0 + i * 40.0
        words.append((100.0, y, 300.0, y + 20.0,
                      "PAGE%dLINE%d" % (page_index, i), i, 0, 0))
    return words


class _PdfCase(unittest.TestCase):
    """A PDF Source whose OCR is injected, one deterministic page at a time."""

    PAGES = 3

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_pdf_ocr_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        self.read_pages = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ocr(self, pages=None, fail_on=()):
        """A reader with the production arity, recording which pages were asked."""
        pages = self.PAGES if pages is None else pages

        def reader(frame_bytes, dpi, filetype="png", page_index=0):
            self.read_pages.append(page_index)
            if page_index in fail_on:
                raise RuntimeError("page %d is unreadable" % page_index)
            words = _words_for(page_index)
            plain = "\n".join(w[4] for w in words)
            return words, (612.0, 792.0), "tesseract", "5.0.0", plain

        return reader

    def _ingest_pdf(self, name="sheets.pdf"):
        """Through the path that ALREADY enqueues PDFs.

        `ingest_upload` (the founding-document path) enqueues a perception job
        only for an image founding source; `attach_document_shop_sources` -
        the multi-source examination path - enqueues for every accepted file
        regardless of type. That is where PDFs have been queueing up and
        dead-ending at the worker's file-type gate, so it is the path this
        tranche has to be proven on.
        """
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"founding"), filename="job.txt"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="PDF Perception Job")
                workspace = self.store.get(document.project_id)
                attach_document_shop_sources(
                    self.app, workspace,
                    [FileStorage(stream=io.BytesIO(b"%PDF-1.4 fake"), filename=name)],
                    owner="cust")
        return document

    def _run(self, document, pages=None, fail_on=(), page_count=None):
        from services import perception_jobs

        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        count = self.PAGES if page_count is None else page_count
        with patch.object(positioned_text, "pdf_page_count", lambda _b: count):
            with patch.object(positioned_text, "_default_ocr",
                              self._ocr(pages=pages, fail_on=fail_on)):
                return perception_worker.run_one(self.app, jobs, "test-worker")

    # -- helpers -------------------------------------------------------------

    def _pdf_source_id(self, document):
        workspace = self.store.get(document.project_id)
        return next(s["id"] for s in workspace.sources
                    if (s.get("name") or "").lower().endswith(".pdf"))

    def _units(self, document):
        workspace = self.store.get(document.project_id)
        return perception_worker._page_units_for(workspace, self._pdf_source_id(document))

    def _positioned_by_unit(self, document):
        """{unit_id: [recovered text, ...]} for positioned evidence only."""
        workspace = self.store.get(document.project_id)
        regions = {r["id"]: r for r in workspace.addressable_regions}
        out = {}
        for item in workspace.evidence_items:
            if item.get("content_type") != positioned_text.POSITIONED_CONTENT_TYPE:
                continue
            region = regions.get(item.get("region_id"))
            if region is None:
                continue
            out.setdefault(region["structural_unit_id"], []).append(item["content"])
        return out


class PageBinding(_PdfCase):
    """The defect this tranche exists to fix."""

    def test_every_page_gets_its_own_positioned_evidence(self):
        document = self._ingest_pdf()
        record = self._run(document)
        self.assertEqual(record["state"], "completed")
        by_unit = self._positioned_by_unit(document)
        self.assertEqual(len(by_unit), self.PAGES,
                         "each page must carry its own positioned evidence")

    def test_page_n_evidence_lands_on_page_n_not_on_page_one(self):
        """The text names its own page, so a mis-binding cannot hide."""
        document = self._ingest_pdf()
        self._run(document)
        units = self._units(document)
        by_unit = self._positioned_by_unit(document)
        for index, unit in enumerate(units):
            with self.subTest(page=index):
                texts = by_unit.get(unit["id"], [])
                self.assertTrue(texts, "page %d stored nothing" % index)
                for text in texts:
                    self.assertIn("PAGE%d" % index, text,
                                  "page %d carries another page's text" % index)

    def test_no_page_unit_receives_another_pages_lines(self):
        document = self._ingest_pdf()
        self._run(document)
        for unit_id, texts in self._positioned_by_unit(document).items():
            prefixes = {t.split("LINE")[0] for t in texts}
            with self.subTest(unit=unit_id):
                self.assertEqual(len(prefixes), 1,
                                 "one unit holds lines from %s" % prefixes)

    def test_units_are_ordered_by_the_documents_own_order(self):
        document = self._ingest_pdf()
        self._run(document)
        orders = [u.get("order_index") for u in self._units(document)]
        self.assertEqual(orders, sorted(orders))

    def test_every_page_of_the_pdf_is_actually_read(self):
        document = self._ingest_pdf()
        self._run(document)
        self.assertEqual(sorted(set(self.read_pages)), list(range(self.PAGES)))


class ExactlyOncePerPage(_PdfCase):

    def test_a_replayed_job_adds_no_second_copy(self):
        document = self._ingest_pdf()
        self._run(document)
        before = sum(len(v) for v in self._positioned_by_unit(document).values())

        workspace = self.store.get(document.project_id)
        job = {"workspace_id": document.project_id,
               "source_id": self._pdf_source_id(document)}
        units = self._units(document)
        page = {"lines": [{"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.02,
                           "text": "REPLAY"}], "frame": None}
        perception_worker._write_positioned_with_retry(
            self.store, job, page, "tesseract 5.0.0", None,
            structural_unit_id=units[0]["id"])

        after = sum(len(v) for v in self._positioned_by_unit(document).values())
        self.assertEqual(after, before)

    def test_the_recheck_is_scoped_to_the_page_not_the_source(self):
        """Source-scoped, page 1 writes and pages 2..n report a false replay."""
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        window = source[source.index("def _evidence_on_unit"):]
        window = window[:window.index("\ndef ", 10)]
        self.assertIn("structural_unit_id", window)
        self.assertIn("region_id", window)


class TheGateIsNarrowedNotOpened(_PdfCase):

    def test_a_pdf_now_flows_through_the_worker(self):
        document = self._ingest_pdf()
        record = self._run(document)
        self.assertEqual(record["state"], "completed")

    def test_an_unsupported_file_type_still_terminates_honestly(self):
        from services import perception_jobs

        document = self._ingest_pdf(name="schedule.docx")
        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        record = perception_worker.run_one(self.app, jobs, "test-worker")
        self.assertEqual(record["state"], "needs_attention")
        self.assertIn("no perception path", record.get("failure_reason") or "")

    def test_the_image_path_is_not_routed_through_the_pdf_branch(self):
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        self.assertIn('name.lower().endswith(".pdf")', source)
        self.assertIn("if not image_intake.is_supported_image(name):", source)


class Degradation(_PdfCase):

    def test_an_unopenable_pdf_needs_attention_rather_than_failing(self):
        document = self._ingest_pdf()
        record = self._run(document, page_count=0)
        self.assertEqual(record["state"], "needs_attention")

    def test_a_pdf_that_reads_as_empty_needs_attention(self):
        from services import perception_jobs

        def silent(frame_bytes, dpi, filetype="png", page_index=0):
            return [], (612.0, 792.0), "tesseract", "5.0.0", ""

        document = self._ingest_pdf()
        jobs = perception_jobs.PerceptionJobStore(
            self.app.config["REGISTRY_STORE_PATH"])
        with patch.object(positioned_text, "pdf_page_count", lambda _b: 2):
            with patch.object(positioned_text, "_default_ocr", silent):
                record = perception_worker.run_one(self.app, jobs, "test-worker")
        self.assertEqual(record["state"], "needs_attention")

    def test_one_unreadable_page_does_not_lose_the_others(self):
        document = self._ingest_pdf()
        record = self._run(document, fail_on=(1,))
        self.assertEqual(record["state"], "completed")
        by_unit = self._positioned_by_unit(document)
        self.assertEqual(len(by_unit), 2, "the two readable pages must survive")

    def test_the_page_bound_is_reported_rather_than_silently_applied(self):
        read = positioned_text.read_pdf_positioned_pages(
            b"x", ocr=self._ocr(), max_pages=2)
        with patch.object(positioned_text, "pdf_page_count", lambda _b: 5):
            read = positioned_text.read_pdf_positioned_pages(
                b"x", ocr=self._ocr(), max_pages=2)
        self.assertEqual(read["page_count"], 5)
        self.assertEqual(len(read["pages"]), 2)
        self.assertEqual(read["skipped_pages"], 3)


class Geometry(_PdfCase):

    def test_every_stored_box_is_a_fraction_inside_the_page(self):
        document = self._ingest_pdf()
        self._run(document)
        workspace = self.store.get(document.project_id)
        boxes = [r["address"] for r in workspace.addressable_regions
                 if "x" in (r.get("address") or {})]
        self.assertTrue(boxes)
        for address in boxes:
            with self.subTest(address=address):
                self.assertGreaterEqual(address["x"], 0.0)
                self.assertGreaterEqual(address["y"], 0.0)
                self.assertLessEqual(address["x"] + address["width"], 1.0 + 1e-9)
                self.assertLessEqual(address["y"] + address["height"], 1.0 + 1e-9)

    def test_a_page_is_its_own_frame_rather_than_a_zero_sized_one(self):
        """Recording 0x0 and a factor of zero would put a false step in the
        very chain `px_per_ocr_unit` exists to preserve."""
        read = positioned_text.read_positioned_lines(
            b"x", (0, 0), filetype="pdf", ocr=self._ocr())
        frame = read["frame"]
        self.assertEqual(frame["normalised_size"], [612, 792])
        self.assertEqual(frame["px_per_ocr_unit"], [1.0, 1.0])

    def test_an_image_frame_still_records_its_own_separate_frame(self):
        read = positioned_text.read_positioned_lines(
            b"x", (1224, 1584), filetype="png", ocr=self._ocr())
        frame = read["frame"]
        self.assertEqual(frame["normalised_size"], [1224, 1584])
        self.assertEqual(frame["px_per_ocr_unit"], [2.0, 2.0])


class NoSecondPassNoMagnitude(_PdfCase):

    def test_one_ocr_call_per_page_and_no_more(self):
        document = self._ingest_pdf()
        self._run(document)
        self.assertEqual(len(self.read_pages), self.PAGES,
                         "a page must be OCR'd exactly once: %s" % self.read_pages)

    def test_raster_extraction_is_left_alone(self):
        """It owns INGESTION-time text recovery; perception-time geometry is
        this module's. Reaching into it would give one concern two owners.

        Checked as a CALL via the AST, not as a word: this function's own
        docstring names `extract_raster_pages` precisely to say it is NOT used,
        and a text scan would catch the explanation instead of the behaviour.
        That exact self-match has bitten this repository before.
        """
        tree = ast.parse((_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8"))
        target = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "read_pdf_positioned_pages")
        called = set()
        for child in ast.walk(target):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        self.assertNotIn("extract_raster_pages", called)
        self.assertNotIn("extract_region_text", called)
        self.assertIn("read_positioned_lines", called)

    def test_no_magnitude_scale_or_transform_is_derived(self):
        """Product Owner decision 2026-09-11, Option C: identity-first, and
        physical magnitude is not derived from page geometry."""
        tree = ast.parse((_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8"))
        target = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "_run_pdf_job")
        called = set()
        for child in ast.walk(target):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        for forbidden in ("create_derived_view", "may_measure", "parse_scale_notation",
                          "to_view_coordinates", "to_source_coordinates",
                          "may_compare_spatially", "segment_sheet"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)

    def test_no_image_leaves_the_machine(self):
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        window = source[source.index("def _run_pdf_job"):]
        window = window[:window.index("\ndef _write_pdf_pages_with_retry")]
        for forbidden in ("requests", "urlopen", "httpx", "call_gemini_json",
                          "read_sheet", "sheet_vision", "base64"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, window)


class SourcePreservation(_PdfCase):

    def test_the_stored_pdf_is_untouched(self):
        document = self._ingest_pdf()
        workspace = self.store.get(document.project_id)
        path = Path(next(s for s in workspace.sources
                         if (s.get("name") or "").endswith(".pdf"))["file_path"])
        before = path.read_bytes()
        self._run(document)
        self.assertEqual(path.read_bytes(), before)

    def test_recovered_text_is_extracted_evidence_never_the_document_speaking(self):
        document = self._ingest_pdf()
        self._run(document)
        workspace = self.store.get(document.project_id)
        # Scoped to the PDF. The founding .txt Source in this fixture carries
        # its own evidence from a different path with its own class, and
        # sweeping it in would make this assert something this tranche neither
        # changed nor is claiming.
        source_id = self._pdf_source_id(document)
        recovered = [e for e in workspace.evidence_items
                     if e.get("source_id") == source_id
                     and e.get("content_type") in
                     ("text", positioned_text.POSITIONED_CONTENT_TYPE)]
        self.assertTrue(recovered)
        for item in recovered:
            with self.subTest(item=item["id"]):
                self.assertEqual(item["evidence_class"], EVIDENCE_CLASS_EXTRACTED)

    def test_the_run_is_recorded_in_the_governance_log(self):
        document = self._ingest_pdf()
        self._run(document)
        log = Path(self.tmp) / ("%s.governance.jsonl" % document.project_id)
        self.assertIn("pdf_pages_perceived", log.read_text(encoding="utf-8"))


class TheImagePathIsUnchanged(unittest.TestCase):
    """A tranche that quietly changes what every existing photograph yields is
    the failure the region-OCR tranche already refused once."""

    def test_the_default_page_index_is_zero_everywhere(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        self.assertIn("page_index: int = 0", source)
        self.assertIn("def read_positioned_lines(frame_bytes: bytes, frame_size, *,",
                      source)

    def test_a_reader_that_predates_page_index_still_works(self):
        """Tests inject two- and three-argument readers; they must not all have
        to change because production learned to ask for page n."""
        def two_arg(frame_bytes, dpi):
            return [], (10.0, 10.0), "e", "v", ""

        def three_arg(frame_bytes, dpi, filetype):
            return [], (10.0, 10.0), "e", "v", ""

        for reader in (two_arg, three_arg):
            with self.subTest(reader=reader.__name__):
                out = positioned_text.read_positioned_lines(b"x", (10, 10), ocr=reader)
                self.assertTrue(out["ran"])

    def test_a_type_error_inside_a_reader_is_not_swallowed_as_arity(self):
        """A bare except TypeError around every arity would retry a real fault
        with fewer arguments and report a confusing signature error instead."""
        def explodes(frame_bytes, dpi, filetype="png", page_index=0):
            raise TypeError("something inside the reader is wrong")

        out = positioned_text.read_positioned_lines(b"x", (10, 10), ocr=explodes)
        self.assertFalse(out["ran"])
        self.assertIn("TypeError", out["reason"] or "")


if __name__ == "__main__":
    unittest.main()
