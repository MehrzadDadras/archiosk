"""CLAUDE-GO-PERCEPTION-REGION-OCR-01: what was read, AND where it was read from.

Perception produced one unpositioned string per image. GO could report the
characters and had no way to say where on the drawing any of them sat. This
tranche adds coordinates and deliberately nothing else.

The tests below are organised around the three things that could go wrong, in
descending order of how quietly they would go wrong:

1. **The reading changes.** Coordinates are worth nothing if attaching them
   alters what was read. `TheReadingIsUnchanged` pins that the positioned path
   is the same OCR pass asked a second way - one textpage, two questions.

2. **The coordinates are ambiguous.** A bbox that only means something if you
   also know which temporary raster produced it is not an address. PyMuPDF
   opens a 3024x4032 frame as a 2268x3024 page, so this is not hypothetical -
   it is the exact trap. `CoordinatesAreFrameIndependent` pins fractions, and
   pins that the transform is recorded rather than implied.

3. **Positioned text leaks into the customer's result.** The result reader
   selects `content_type == "text"` and joins what it finds with blank lines.
   Hundreds of positioned lines stored as "text" would turn a person's
   examination into a column of fragments. `TheCustomerSurfaceIsUntouched`
   pins the separation.

Every OCR call here is injected. Nothing in this file needs Tesseract
installed, and nothing in it reaches a network - which is also how the
zero-egress assertions stay meaningful rather than aspirational.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services import positioned_text
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceError, CaseWorkspaceStore,
    EVIDENCE_CLASS_EXTRACTED,
)
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


def _png(width=400, height=300, colour=(255, 255, 255)):
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), colour).save(buffer, "PNG")
    return buffer.getvalue()


def _jpeg_with_orientation(tag, width=400, height=300):
    """A JPEG whose EXIF says it is sideways - EXIF 6 is the phone default."""
    from PIL import Image

    image = Image.new("RGB", (width, height), (255, 255, 255))
    exif = image.getexif()
    exif[274] = tag
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def _ocr(words, rect=(300.0, 225.0), text=None, engine="tesseract",
         version="5.0.0"):
    """An injected OCR pass. `words` are PyMuPDF-shaped tuples in page points."""
    def _run(_frame_png, _dpi):
        joined = text if text is not None else " ".join(w[4] for w in words)
        return list(words), rect, engine, version, joined
    return _run


def _word(x0, y0, x1, y1, text, block=0, line=0, word=0):
    return (x0, y0, x1, y1, text, block, line, word)


class TokenLegibility(unittest.TestCase):
    """The garbage rule is the repository's own, not a new invention."""

    def test_it_is_the_same_rule_legible_ratio_already_applies(self):
        from services import raster_extraction

        # Same predicate, verified by agreement on a mixed population rather
        # than by reading both implementations and hoping.
        tokens = ["DAMPER", "FD-1", "a", "//", "|.", "1234", "ab", "N.T.S",
                  "CLOSE", "~", "x7y"]
        mine = [t for t in tokens if positioned_text.is_legible_token(t)]
        expected_ratio = raster_extraction.legible_ratio(" ".join(tokens))
        self.assertAlmostEqual(len(mine) / len(tokens), expected_ratio, places=6)

    def test_obvious_noise_is_not_legible(self):
        for token in ("|", "//", "~", ".:", "-", ""):
            with self.subTest(token=token):
                self.assertFalse(positioned_text.is_legible_token(token))

    def test_real_annotation_tokens_are_legible(self):
        for token in ("DAMPER", "FD-1", "CLOSE", "ALARM", "1200"):
            with self.subTest(token=token):
                self.assertTrue(positioned_text.is_legible_token(token))


class TheReadingIsUnchanged(unittest.TestCase):
    """Coordinates are added to the reading; the reading is not re-done."""

    def test_the_plain_text_is_carried_through_verbatim(self):
        words = [_word(10, 10, 60, 24, "DAMPER"), _word(64, 10, 96, 24, "FD-1")]
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300), ocr=_ocr(words, text="DAMPER FD-1\n"))
        self.assertEqual(got["text"], "DAMPER FD-1\n")

    def test_one_ocr_pass_serves_both_answers(self):
        """Two passes would double a job that already runs 5-21s on a photo."""
        calls = []

        def counting(frame_png, dpi):
            calls.append(dpi)
            return ([_word(1, 1, 40, 12, "PLAN")], (300.0, 225.0),
                    "tesseract", "5.0.0", "PLAN")

        got = positioned_text.read_positioned_lines(_png(), (400, 300), ocr=counting)
        self.assertEqual(len(calls), 1, "the engine must be asked exactly once")
        self.assertTrue(got["text"])
        self.assertEqual(got["line_count"], 1)

    def test_the_engine_is_reported_not_assumed(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(1, 1, 40, 12, "PLAN")], engine="tesseract",
                     version="4.1.1"))
        self.assertEqual(got["engine"], "tesseract")
        self.assertEqual(got["engine_version"], "4.1.1")

    def test_confidence_is_reported_as_unavailable_never_invented(self):
        """The chosen extractor emits none. Saying so beats inventing one."""
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300), ocr=_ocr([_word(1, 1, 40, 12, "PLAN")]))
        self.assertFalse(got["confidence_available"])
        for line in got["lines"]:
            self.assertNotIn("confidence", line)


class CoordinatesAreFrameIndependent(unittest.TestCase):
    """The trap this tranche exists to avoid, pinned."""

    def _read(self, words, rect, frame):
        return positioned_text.read_positioned_lines(
            _png(), frame, ocr=_ocr(words, rect=rect))

    def test_a_bbox_is_a_fraction_of_the_normalised_frame(self):
        # Page rect deliberately UNEQUAL to the frame - this is the real
        # PyMuPDF behaviour (3024x4032 frame -> 2268x3024 page).
        got = self._read([_word(0, 0, 1134.0, 1512.0, "HALF")],
                         rect=(2268.0, 3024.0), frame=(3024, 4032))
        line = got["lines"][0]
        self.assertAlmostEqual(line["x"], 0.0)
        self.assertAlmostEqual(line["y"], 0.0)
        self.assertAlmostEqual(line["width"], 0.5, places=6)
        self.assertAlmostEqual(line["height"], 0.5, places=6)

    def test_the_same_geometry_gives_the_same_fraction_at_any_raster_size(self):
        """A coordinate that survives a change of raster is a real address."""
        small = self._read([_word(0, 0, 100.0, 50.0, "MARK")],
                           rect=(200.0, 100.0), frame=(800, 400))
        large = self._read([_word(0, 0, 400.0, 200.0, "MARK")],
                           rect=(800.0, 400.0), frame=(800, 400))
        for key in ("x", "y", "width", "height"):
            with self.subTest(key=key):
                self.assertAlmostEqual(small["lines"][0][key],
                                       large["lines"][0][key], places=6)

    def test_the_transform_is_recorded_rather_than_implied(self):
        got = self._read([_word(0, 0, 100.0, 50.0, "MARK")],
                         rect=(2268.0, 3024.0), frame=(3024, 4032))
        frame = got["frame"]
        self.assertEqual(frame["normalised_size"], [3024, 4032])
        self.assertEqual(frame["ocr_frame_size"], [2268.0, 3024.0])
        self.assertAlmostEqual(frame["px_per_ocr_unit"][0], 4.0 / 3.0, places=6)
        self.assertAlmostEqual(frame["px_per_ocr_unit"][1], 4.0 / 3.0, places=6)
        self.assertEqual(frame["coordinate_space"], "fraction_of_normalised_frame")

    def test_every_bbox_lies_inside_the_frame(self):
        got = self._read(
            [_word(0, 0, 2268.0, 3024.0, "FULLPAGE"),
             _word(2000.0, 2900.0, 2268.0, 3024.0, "CORNER")],
            rect=(2268.0, 3024.0), frame=(3024, 4032))
        for line in got["lines"]:
            with self.subTest(text=line["text"]):
                self.assertGreaterEqual(line["x"], 0.0)
                self.assertGreaterEqual(line["y"], 0.0)
                self.assertLessEqual(line["x"] + line["width"], 1.0 + 1e-9)
                self.assertLessEqual(line["y"] + line["height"], 1.0 + 1e-9)

    def test_a_zero_extent_line_is_dropped_not_stored(self):
        """A box you cannot point at is not an address."""
        got = self._read([_word(10.0, 10.0, 10.0, 10.0, "FLAT")],
                         rect=(200.0, 100.0), frame=(200, 100))
        self.assertEqual(got["line_count"], 0)
        self.assertEqual(got["dropped_line_count"], 1)


class Grouping(unittest.TestCase):
    """Words become lines; lines keep enough to be pointed at."""

    def test_words_on_one_line_become_one_region(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 60, 24, "CLOSE", block=0, line=0),
                      _word(64, 10, 96, 24, "ON", block=0, line=0),
                      _word(100, 10, 150, 24, "ALARM", block=0, line=0)]))
        self.assertEqual(got["line_count"], 1)
        self.assertEqual(got["lines"][0]["text"], "CLOSE ON ALARM")
        self.assertEqual(got["lines"][0]["word_count"], 3)

    def test_the_line_box_encloses_all_of_its_words(self):
        got = positioned_text.read_positioned_lines(
            _png(), (300, 225),
            ocr=_ocr([_word(10, 20, 60, 40, "AAA"), _word(80, 15, 150, 45, "BBB")],
                     rect=(300.0, 225.0)))
        line = got["lines"][0]
        self.assertAlmostEqual(line["x"] * 300.0, 10.0, places=3)
        self.assertAlmostEqual(line["y"] * 225.0, 15.0, places=3)
        self.assertAlmostEqual((line["x"] + line["width"]) * 300.0, 150.0, places=3)
        self.assertAlmostEqual((line["y"] + line["height"]) * 225.0, 45.0, places=3)

    def test_separate_lines_stay_separate(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 60, 24, "FIRST", block=0, line=0),
                      _word(10, 30, 60, 44, "SECOND", block=0, line=1)]))
        self.assertEqual(got["line_count"], 2)

    def test_separate_blocks_stay_separate_even_on_the_same_line_number(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 60, 24, "LEFT", block=0, line=0),
                      _word(200, 10, 260, 24, "RIGHT", block=1, line=0)]))
        self.assertEqual(got["line_count"], 2)

    def test_reading_order_is_preserved(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 60, 24, "ONE", block=0, line=0),
                      _word(10, 30, 60, 44, "TWO", block=0, line=1),
                      _word(10, 50, 60, 64, "THREE", block=0, line=2)]))
        self.assertEqual([l["text"] for l in got["lines"]], ["ONE", "TWO", "THREE"])


class GarbageControl(unittest.TestCase):
    """Lots of OCR tokens must not become lots of meaningful evidence."""

    def test_a_line_with_no_legible_token_is_dropped(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 20, 24, "|", block=0, line=0),
                      _word(24, 10, 34, 24, "//", block=0, line=0)]))
        self.assertEqual(got["line_count"], 0)
        self.assertEqual(got["dropped_line_count"], 1)

    def test_a_line_with_one_legible_token_survives_with_its_noise(self):
        """The noise is context, not a separate finding - the line is the unit."""
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 20, 24, "|", block=0, line=0),
                      _word(24, 10, 80, 24, "DAMPER", block=0, line=0)]))
        self.assertEqual(got["line_count"], 1)
        self.assertEqual(got["lines"][0]["text"], "| DAMPER")

    def test_what_was_dropped_is_counted_not_silently_discarded(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 20, 24, "|", block=0, line=0),
                      _word(10, 30, 80, 44, "REAL", block=0, line=1),
                      _word(10, 50, 20, 64, "~", block=0, line=2)]))
        self.assertEqual(got["line_count"], 1)
        self.assertEqual(got["dropped_line_count"], 2)

    def test_no_confidence_threshold_is_applied_anywhere(self):
        """Measured: a floor made the noisy source WORSE (0.449 -> 0.290)."""
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#"))
        self.assertNotIn("conf >=", code)
        self.assertNotIn("confidence >", code)
        self.assertNotIn("MIN_CONFIDENCE", code)

    def test_the_runaway_guard_is_far_above_the_largest_real_source(self):
        """A guard, not a quality threshold - the largest measured was 636."""
        self.assertGreater(positioned_text.MAX_STORED_LINES, 636 * 2)

    def test_truncation_is_reported_rather_than_hidden(self):
        words = [_word(0, i * 2, 50, i * 2 + 1, "LINE%d" % i, block=0, line=i)
                 for i in range(positioned_text.MAX_STORED_LINES + 10)]
        got = positioned_text.read_positioned_lines(
            _png(), (400, 6000), ocr=_ocr(words, rect=(400.0, 6000.0)))
        self.assertTrue(got["truncated"])
        self.assertLessEqual(got["line_count"], positioned_text.MAX_STORED_LINES)


class SafeDegradation(unittest.TestCase):
    """A failed read is a result, never a crash."""

    def test_an_engine_that_raises_returns_a_result(self):
        def boom(_frame, _dpi):
            raise RuntimeError("no engine here")

        got = positioned_text.read_positioned_lines(_png(), (400, 300), ocr=boom)
        self.assertFalse(got["ran"])
        self.assertEqual(got["lines"], [])
        self.assertIn("positioned OCR failed", got["reason"])

    def test_an_empty_reading_is_an_honest_nothing(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300), ocr=_ocr([], text=""))
        self.assertTrue(got["ran"])
        self.assertEqual(got["line_count"], 0)
        self.assertEqual(got["text"], "")

    def test_a_malformed_word_tuple_is_skipped_not_fatal(self):
        def short(_frame, _dpi):
            return ([(1, 2, 3)], (300.0, 225.0), "tesseract", "5.0.0", "")

        got = positioned_text.read_positioned_lines(_png(), (400, 300), ocr=short)
        self.assertTrue(got["ran"])
        self.assertEqual(got["line_count"], 0)


class OrientationIsConsumed(unittest.TestCase):
    """OCR reads the frame the PERSON sees, never the sideways pixels."""

    def test_an_exif_6_photo_is_read_in_its_upright_frame(self):
        from services import image_intake

        seen = {}

        def spy(frame_png, dpi):
            from PIL import Image
            seen["size"] = Image.open(io.BytesIO(frame_png)).size
            return ([_word(1, 1, 40, 12, "PLAN")], (300.0, 400.0),
                    "tesseract", "5.0.0", "PLAN")

        got = image_intake.extract_image_positioned_text(
            _jpeg_with_orientation(6, width=400, height=300), "image.jpg", ocr=spy)
        # 400x300 tagged EXIF 6 is upright at 300x400.
        self.assertEqual(seen["size"], (300, 400))
        self.assertEqual(got["frame"]["normalised_size"], [300, 400])
        self.assertEqual(got["orientation"]["applied_rotation_degrees"], 270)

    def test_a_non_rotated_image_keeps_its_own_frame(self):
        from services import image_intake

        seen = {}

        def spy(frame_png, dpi):
            from PIL import Image
            seen["size"] = Image.open(io.BytesIO(frame_png)).size
            return ([_word(1, 1, 40, 12, "PLAN")], (300.0, 225.0),
                    "tesseract", "5.0.0", "PLAN")

        got = image_intake.extract_image_positioned_text(_png(400, 300), "a.png",
                                                         ocr=spy)
        self.assertEqual(seen["size"], (400, 300))
        self.assertEqual(got["frame"]["normalised_size"], [400, 300])
        self.assertEqual(got["orientation"]["applied_rotation_degrees"], 0)

    def test_the_stored_source_is_never_rewritten(self):
        from services import image_intake

        raw = _jpeg_with_orientation(6)
        before = bytes(raw)
        image_intake.extract_image_positioned_text(
            raw, "image.jpg",
            ocr=_ocr([_word(1, 1, 40, 12, "PLAN")], rect=(225.0, 300.0)))
        self.assertEqual(raw, before)


class TheStore(unittest.TestCase):
    """Governed storage of positioned text - existing model, one save."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_posn_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="a.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Positioned Job")
        self.workspace = self.store.get(self.document.project_id)
        self.source_id = self.workspace.sources[0]["id"]
        self.unit = self.store.register_pdf_page_structure(
            self.workspace, source_id=self.source_id, pages=["hello"],
            actor="test")["structural_unit_ids"][0]
        self.workspace = self.store.get(self.document.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _lines(self, n=2):
        # Inside the frame by construction. The store refuses anything that
        # is not, which is the behaviour a separate test pins deliberately.
        return [{"x": (i % 10) / 20.0, "y": (i % 7) / 20.0,
                 "width": 0.05, "height": 0.02,
                 "text": "LINE %d" % i, "word_count": 2} for i in range(1, n + 1)]

    def test_it_writes_one_region_and_one_evidence_item_per_line(self):
        out = self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id,
            structural_unit_id=self.unit, lines=self._lines(3),
            extractor_version="tesseract 5.0.0", actor="perception-worker")
        self.assertEqual(out["region_count"], 3)
        self.assertEqual(len(out["evidence_item_ids"]), 3)

    def test_it_saves_once_not_once_per_line(self):
        """508 lines meant 508 full JSON rewrites through the per-item writer."""
        saves = []
        real_save = CaseWorkspaceStore.save

        def counting(store_self, workspace, *a, **kw):
            saves.append(1)
            return real_save(store_self, workspace, *a, **kw)

        with patch.object(CaseWorkspaceStore, "save", counting):
            self.store.register_positioned_text_regions(
                self.workspace, source_id=self.source_id,
                structural_unit_id=self.unit, lines=self._lines(25),
                actor="perception-worker")
        self.assertEqual(len(saves), 1)

    def test_positioned_evidence_is_extracted_never_direct_source(self):
        """A reading of an image is not the document speaking."""
        self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id,
            structural_unit_id=self.unit, lines=self._lines(2),
            actor="perception-worker")
        fresh = self.store.get(self.document.project_id)
        positioned = [e for e in fresh.evidence_items
                      if e["content_type"] == "positioned_text"]
        self.assertTrue(positioned)
        for item in positioned:
            self.assertEqual(item["evidence_class"], EVIDENCE_CLASS_EXTRACTED)

    def test_the_region_carries_geometry_and_the_evidence_carries_text(self):
        """The store's own division: where is not what."""
        self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id,
            structural_unit_id=self.unit, lines=self._lines(1),
            actor="perception-worker")
        fresh = self.store.get(self.document.project_id)
        region = [r for r in fresh.addressable_regions
                  if r["region_type"] == "rectangular"][0]
        self.assertIn("x", region["address"])
        self.assertNotIn("text", region["address"])
        evidence = [e for e in fresh.evidence_items
                    if e["content_type"] == "positioned_text"][0]
        self.assertEqual(evidence["region_id"], region["id"])
        self.assertTrue(evidence["content"])

    def test_the_chain_source_to_unit_to_region_to_evidence_is_traceable(self):
        self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id,
            structural_unit_id=self.unit, lines=self._lines(1),
            actor="perception-worker")
        fresh = self.store.get(self.document.project_id)
        evidence = [e for e in fresh.evidence_items
                    if e["content_type"] == "positioned_text"][0]
        region = next(r for r in fresh.addressable_regions
                      if r["id"] == evidence["region_id"])
        unit = next(u for u in fresh.structural_units
                    if u["id"] == region["structural_unit_id"])
        self.assertEqual(evidence["source_id"], self.source_id)
        self.assertEqual(unit["source_id"], self.source_id)

    def test_the_coordinate_frame_is_recorded_once_on_the_unit(self):
        frame = {"normalised_size": [3024, 4032], "ocr_frame_size": [2268.0, 3024.0],
                 "px_per_ocr_unit": [4 / 3, 4 / 3], "render_dpi": 200,
                 "coordinate_space": "fraction_of_normalised_frame"}
        self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id,
            structural_unit_id=self.unit, lines=self._lines(2), frame=frame,
            actor="perception-worker")
        fresh = self.store.get(self.document.project_id)
        unit = next(u for u in fresh.structural_units if u["id"] == self.unit)
        stored = (unit.get("modality_metadata") or {}).get("perception_frame")
        self.assertEqual(stored["normalised_size"], [3024, 4032])
        self.assertEqual(stored["coordinate_space"], "fraction_of_normalised_frame")

    def test_a_bbox_outside_the_frame_is_refused_not_clamped(self):
        """A box that cannot be trusted to lie on the drawing is worse than none."""
        for bad in ({"x": 1.2, "y": 0.1, "width": 0.1, "height": 0.1, "text": "X"},
                    {"x": 0.9, "y": 0.1, "width": 0.5, "height": 0.1, "text": "X"},
                    {"x": -0.1, "y": 0.1, "width": 0.1, "height": 0.1, "text": "X"},
                    {"x": 0.1, "y": 0.1, "width": 0.0, "height": 0.1, "text": "X"}):
            with self.subTest(bad=bad):
                out = self.store.register_positioned_text_regions(
                    self.workspace, source_id=self.source_id,
                    structural_unit_id=self.unit, lines=[bad],
                    actor="perception-worker")
                self.assertEqual(out["region_count"], 0, "an untrusted box was stored")
                self.assertEqual(out["rejected_count"], 1)

    def test_one_bad_box_does_not_cost_the_source_its_good_ones(self):
        """§16 partial success. Refusing the untrustworthy is not refusing all."""
        out = self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id, structural_unit_id=self.unit,
            lines=[{"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1, "text": "GOOD"},
                   {"x": 9.0, "y": 0.1, "width": 0.1, "height": 0.1, "text": "BAD"},
                   {"x": 0.3, "y": 0.3, "width": 0.1, "height": 0.1, "text": "ALSO GOOD"}],
            actor="perception-worker")
        self.assertEqual(out["region_count"], 2)
        self.assertEqual(out["rejected_count"], 1)
        fresh = self.store.get(self.document.project_id)
        stored = sorted(e["content"] for e in fresh.evidence_items
                        if e["content_type"] == "positioned_text")
        self.assertEqual(stored, ["ALSO GOOD", "GOOD"])

    def test_what_was_refused_is_reported_with_a_reason(self):
        out = self.store.register_positioned_text_regions(
            self.workspace, source_id=self.source_id, structural_unit_id=self.unit,
            lines=[{"x": 9.0, "y": 0.1, "width": 0.1, "height": 0.1, "text": "BAD"}],
            actor="perception-worker")
        self.assertEqual(len(out["rejected"]), 1)
        self.assertIn("reason", out["rejected"][0])
        self.assertIn("index", out["rejected"][0])

    def test_a_unit_belonging_to_another_source_is_refused(self):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                other = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="b.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Other Job")
        other_ws = self.store.get(other.project_id)
        other_unit = self.store.register_pdf_page_structure(
            other_ws, source_id=other_ws.sources[0]["id"], pages=["x"],
            actor="test")["structural_unit_ids"][0]
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_positioned_text_regions(
                self.workspace, source_id=self.source_id,
                structural_unit_id=other_unit, lines=self._lines(1),
                actor="perception-worker")


class TheCustomerSurfaceIsUntouched(unittest.TestCase):
    """§20: positioned evidence sits UNDER the product, not in it."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_posn_ui_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="a.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Surface Job")
        workspace = self.store.get(self.document.project_id)
        self.source_id = workspace.sources[0]["id"]
        self.unit = self.store.register_pdf_page_structure(
            workspace, source_id=self.source_id,
            pages=["The damper closes on alarm."], actor="test",
            evidence_class_by_page={0: EVIDENCE_CLASS_EXTRACTED},
        )["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _preview(self):
        from services import document_examination

        workspace = self.store.get(self.document.project_id)
        return document_examination._recovered(workspace, self.source_id)

    def test_the_preview_is_identical_before_and_after_positioned_text(self):
        before = self._preview()
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=self.source_id, structural_unit_id=self.unit,
            lines=[{"x": (i % 10) / 20.0, "y": (i % 7) / 20.0,
                    "width": 0.05, "height": 0.02,
                    "text": "FRAGMENT %d" % i} for i in range(1, 40)],
            actor="perception-worker")
        after = self._preview()
        self.assertEqual(before["preview"], after["preview"])
        self.assertEqual(before["passage_count"], after["passage_count"])
        self.assertEqual(before["character_count"], after["character_count"])

    def test_positioned_content_type_is_not_text(self):
        """This is the mechanism that keeps the two layers apart."""
        self.assertNotEqual(positioned_text.POSITIONED_CONTENT_TYPE, "text")

    def test_the_page_count_does_not_grow_with_positioned_regions(self):
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=self.source_id, structural_unit_id=self.unit,
            lines=[{"x": 0.1, "y": 0.2, "width": 0.05, "height": 0.02,
                    "text": "ONE"}], actor="perception-worker")
        self.assertEqual(self._preview()["page_count"], 1)


class TheWorker(unittest.TestCase):
    """§15: the work happens in the worker, and never fails the examination."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_posn_w_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _job(self, name="a.png", project_name="Worker Job"):
        from services import perception_jobs

        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename=name),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name=project_name)
        workspace = self.store.get(document.project_id)
        jobs = perception_jobs.PerceptionJobStore(self.app.config["REGISTRY_STORE_PATH"])
        return document, workspace, jobs

    def _reading(self, lines):
        return {
            "ran": True, "status": "readable", "engine": "tesseract",
            "engine_version": "5.0.0", "reason": None,
            "orientation": {"authority": "stored_pixels", "changed": False,
                            "applied_rotation_degrees": 0, "exif_orientation": None,
                            "normalised_size": [400, 300], "native_size": [400, 300],
                            "applied_mirror": False, "conflict": False, "osd": None,
                            "reason": None},
            "text": "The damper closes on alarm.",
            "lines": lines, "line_count": len(lines), "word_count": len(lines) * 2,
            "dropped_line_count": 0, "truncated": False,
            "confidence_available": False,
            "frame": {"normalised_size": [400, 300], "ocr_frame_size": [300.0, 225.0],
                      "px_per_ocr_unit": [4 / 3, 4 / 3], "render_dpi": 200,
                      "coordinate_space": "fraction_of_normalised_frame"},
        }

    def _run(self, reading):
        from services import perception_worker

        document, workspace, jobs = self._job()
        with patch("services.image_intake.extract_image_positioned_text",
                   lambda *a, **kw: reading):
            record = perception_worker.run_one(self.app, jobs, "test-worker")
        return document, jobs, record

    def test_a_successful_job_stores_positioned_evidence(self):
        lines = [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05,
                  "text": "CLOSE ON ALARM"}]
        document, jobs, record = self._run(self._reading(lines))
        self.assertEqual(record["state"], "completed")
        fresh = self.store.get(document.project_id)
        positioned = [e for e in fresh.evidence_items
                      if e["content_type"] == "positioned_text"]
        self.assertEqual(len(positioned), 1)
        self.assertEqual(positioned[0]["content"], "CLOSE ON ALARM")

    def test_the_text_evidence_still_lands_exactly_as_before(self):
        document, jobs, record = self._run(self._reading(
            [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05, "text": "X-RAY"}]))
        fresh = self.store.get(document.project_id)
        plain = [e for e in fresh.evidence_items if e["content_type"] == "text"]
        self.assertTrue(plain)
        self.assertIn("damper", plain[0]["content"])

    def test_no_lines_does_not_fail_the_examination(self):
        document, jobs, record = self._run(self._reading([]))
        self.assertEqual(record["state"], "completed")
        fresh = self.store.get(document.project_id)
        self.assertTrue([e for e in fresh.evidence_items
                         if e["content_type"] == "text"])

    def test_a_refused_bbox_does_not_fail_the_examination(self):
        """Safe degradation: read but not located is weaker, not failed."""
        bad = [{"x": 4.0, "y": 0.2, "width": 0.3, "height": 0.05, "text": "OFF"}]
        document, jobs, record = self._run(self._reading(bad))
        self.assertEqual(record["state"], "completed")
        fresh = self.store.get(document.project_id)
        self.assertTrue([e for e in fresh.evidence_items
                         if e["content_type"] == "text"])
        self.assertFalse([e for e in fresh.evidence_items
                          if e["content_type"] == "positioned_text"])

    def test_a_partly_unusable_reading_keeps_the_usable_half(self):
        """§16: partial success survives all the way through the worker."""
        mixed = [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05, "text": "KEPT"},
                 {"x": 7.0, "y": 0.2, "width": 0.3, "height": 0.05, "text": "LOST"}]
        document, jobs, record = self._run(self._reading(mixed))
        self.assertEqual(record["state"], "completed")
        fresh = self.store.get(document.project_id)
        stored = [e["content"] for e in fresh.evidence_items
                  if e["content_type"] == "positioned_text"]
        self.assertEqual(stored, ["KEPT"])

    def test_a_positioned_read_that_raises_falls_back_to_the_shipped_path(self):
        from services import perception_worker

        document, workspace, jobs = self._job()

        def boom(*_a, **_kw):
            raise RuntimeError("positioned path exploded")

        fallback = {"ran": True, "status": "readable", "engine": "tesseract",
                    "engine_version": "5.0.0", "reason": None,
                    "orientation": {"authority": "stored_pixels", "changed": False},
                    "text": "fallback text"}
        with patch("services.image_intake.extract_image_positioned_text", boom):
            with patch("services.image_intake.extract_image_text",
                       lambda *a, **kw: fallback):
                record = perception_worker.run_one(self.app, jobs, "test-worker")
        self.assertEqual(record["state"], "completed")
        fresh = self.store.get(document.project_id)
        self.assertTrue([e for e in fresh.evidence_items
                         if e["content_type"] == "text"])

    def test_a_replayed_job_does_not_duplicate_positioned_evidence(self):
        from services import perception_jobs, perception_worker

        lines = [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.05, "text": "ONCE"}]
        document, workspace, jobs = self._job()
        reading = self._reading(lines)
        with patch("services.image_intake.extract_image_positioned_text",
                   lambda *a, **kw: reading):
            perception_worker.run_one(self.app, jobs, "test-worker")
            source_id = self.store.get(document.project_id).sources[0]["id"]
            jobs.enqueue(workspace_id=document.project_id, source_id=source_id,
                         source_name="a.png", source_sha256="x" * 64)
            perception_worker.run_one(self.app, jobs, "test-worker")
        fresh = self.store.get(document.project_id)
        positioned = [e for e in fresh.evidence_items
                      if e["content_type"] == "positioned_text"]
        self.assertEqual(len(positioned), 1, "a replay must not attach a second copy")

    def test_positioned_work_happens_in_the_worker_not_the_request(self):
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        self.assertNotIn("extract_image_positioned_text", source)
        self.assertNotIn("read_positioned_lines", source)
        routes = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        self.assertNotIn("extract_image_positioned_text", routes)
        self.assertNotIn("read_positioned_lines", routes)


class MultiSourceIsolation(unittest.TestCase):
    """§14: coordinates never cross a Source boundary."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_posn_ms_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(_png()), filename="one.png"),
                    self.app, owner="cust", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Multi Job")
        workspace = self.store.get(self.document.project_id)
        self.first = workspace.sources[0]["id"]
        self.second = self.store.add_source(
            workspace, name="two.png", file_path="", kind="image",
            actor="test")["id"]
        workspace = self.store.get(self.document.project_id)
        self.unit_one = self.store.register_pdf_page_structure(
            workspace, source_id=self.first, pages=["one"], actor="test",
        )["structural_unit_ids"][0]
        workspace = self.store.get(self.document.project_id)
        self.unit_two = self.store.register_pdf_page_structure(
            workspace, source_id=self.second, pages=["two"], actor="test",
        )["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_each_source_keeps_its_own_positioned_evidence(self):
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=self.first, structural_unit_id=self.unit_one,
            lines=[{"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1, "text": "FIRST"}],
            actor="perception-worker")
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=self.second, structural_unit_id=self.unit_two,
            lines=[{"x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1, "text": "SECOND"}],
            actor="perception-worker")

        fresh = self.store.get(self.document.project_id)
        for source_id, expected in ((self.first, "FIRST"), (self.second, "SECOND")):
            with self.subTest(source=expected):
                items = [e for e in fresh.evidence_items
                         if e["content_type"] == "positioned_text"
                         and e["source_id"] == source_id]
                self.assertEqual([i["content"] for i in items], [expected])

    def test_one_source_failing_leaves_the_others_evidence_intact(self):
        workspace = self.store.get(self.document.project_id)
        self.store.register_positioned_text_regions(
            workspace, source_id=self.first, structural_unit_id=self.unit_one,
            lines=[{"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1, "text": "KEPT"}],
            actor="perception-worker")
        workspace = self.store.get(self.document.project_id)
        out = self.store.register_positioned_text_regions(
            workspace, source_id=self.second, structural_unit_id=self.unit_two,
            lines=[{"x": 9.0, "y": 0.1, "width": 0.1, "height": 0.1, "text": "BAD"}],
            actor="perception-worker")
        self.assertEqual(out["region_count"], 0)
        self.assertEqual(out["rejected_count"], 1)
        fresh = self.store.get(self.document.project_id)
        kept = [e for e in fresh.evidence_items
                if e["content_type"] == "positioned_text"]
        self.assertEqual([k["content"] for k in kept], ["KEPT"],
                         "the first source's coordinates must survive the "
                         "second source's unusable geometry")


class ZeroImageEgress(unittest.TestCase):
    """§17: no raster, crop or frame may reach any external provider."""

    def test_the_perception_modules_never_reach_a_provider(self):
        for name in ("positioned_text.py", "image_intake.py", "perception_worker.py"):
            source = (_REPO_ROOT / "services" / name).read_text(encoding="utf-8")
            with self.subTest(module=name):
                for forbidden in ("llm_gateway", "anthropic", "Anthropic",
                                  "gemini", "requests.post", "urllib.request",
                                  "httpx", "image_base64"):
                    self.assertNotIn(forbidden, source)

    def test_the_ocr_seam_is_the_only_way_bytes_leave_the_module(self):
        """A frame goes to the injected reader and nowhere else."""
        captured = []

        def spy(frame_png, dpi):
            captured.append(frame_png)
            return ([], (300.0, 225.0), "tesseract", "5.0.0", "")

        positioned_text.read_positioned_lines(_png(), (400, 300), ocr=spy)
        self.assertEqual(len(captured), 1)

    def test_the_default_engine_is_the_local_binary(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        self.assertIn("raster_extraction._ocr_engine", source)


class NoInterpretationWasAdded(unittest.TestCase):
    """§12/§2: this establishes WHERE text is, not what the drawing means."""

    def test_no_semantic_role_vocabulary_was_introduced(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        code = "\n".join(line for line in source.splitlines()
                         if not line.strip().startswith("#")
                         and not line.strip().startswith('"'))
        for role in ("room_name", "door_tag", "dimension_value", "title_block",
                     "ROOM_NAME", "DOOR_TAG"):
            with self.subTest(role=role):
                self.assertNotIn(role, code)

    def test_no_symbol_or_geometry_recognition_was_added(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        for forbidden in ("cv2", "contour", "hough", "detect_symbol",
                          "classify_shape"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_evidence_is_a_line_of_text_and_a_box_and_nothing_more(self):
        got = positioned_text.read_positioned_lines(
            _png(), (400, 300),
            ocr=_ocr([_word(10, 10, 60, 24, "DAMPER")]))
        self.assertEqual(
            set(got["lines"][0]),
            {"x", "y", "width", "height", "text", "word_count",
             "block_index", "line_index"})


if __name__ == "__main__":
    unittest.main()
