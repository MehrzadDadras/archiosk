"""
CLAUDE-DRAWING-SEGMENTATION-01 - region OCR, scale parsing, and the multi-scale
multi-orientation sheet.

WHAT IS REAL HERE AND WHAT IS INJECTED

The FIXTURE is real: `_multi_view_sheet` draws four views at different scales and
orientations plus a title block, then rasterises the whole thing, so pypdf reads
nothing from it - the same condition the real E1 drawing hit.

The OCR ENGINE is injected at the `reader` seam. Tesseract is an optional runtime
binary, and a suite that only passes where someone installed it is not a
regression test. The seam takes (png_bytes, psm, tessdata), so the tests can also
assert that the page segmentation mode is actually being passed through - which
matters, because that mode is what doubled legibility on the real sheet.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services import derived_view as dv
from services import drawing_segmentation as seg
from services import raster_extraction as rx
from services.case_workspace import (
    CaseWorkspaceStore,
    SCALE_METHOD_MANUAL_CONFIRMATION,
    SCALE_METHOD_PRINTED_NOTATION,
    SCALE_STATE_INFORMATIVE,
    SCALE_STATE_QUANTITATIVE,
    SCALE_STATE_REVIEW_NEEDED,
    SOURCE_KIND_DRAWING,
)
from services.governance import GovernanceLog

#: Landscape sheet, roughly ARCH D proportions in points.
SHEET_WIDTH, SHEET_HEIGHT = 1224.0, 864.0


def _multi_view_sheet() -> bytes:
    """A REAL raster sheet: four views at different scales/orientations, a title
    block, and no text layer at all."""
    drawn = pymupdf.open()
    page = drawn.new_page(width=SHEET_WIDTH, height=SHEET_HEIGHT)
    page.insert_text((60, 80), "OVERALL FLOOR PLAN   SCALE 1:100", fontsize=13)
    page.insert_text((60, 400), "ENLARGED PLAN   SCALE 1:50", fontsize=13)
    page.insert_text((640, 80), "SECTION A-A   SCALE 1:20", fontsize=13, rotate=90)
    page.insert_text((640, 400), "TYPICAL DETAIL   N.T.S.", fontsize=13)
    page.insert_text((980, 760), "A-101  GROUND FLOOR PLAN", fontsize=12)
    page.insert_text((980, 790), "PROJECT 212109   REV 3", fontsize=11)
    page.insert_text((300, 300), "N", fontsize=20)

    rasterised = pymupdf.open()
    pix = drawn.load_page(0).get_pixmap(dpi=96)
    out_page = rasterised.new_page(width=SHEET_WIDTH, height=SHEET_HEIGHT)
    out_page.insert_image(pymupdf.Rect(0, 0, SHEET_WIDTH, SHEET_HEIGHT),
                          stream=pix.tobytes("png"))
    raw = rasterised.tobytes()
    drawn.close()
    rasterised.close()
    return raw


def _reader(text_by_call=None, default="", record=None):
    """An injected OCR engine. Records the psm it was handed."""
    calls = {"n": 0}

    def read(png_bytes, psm, tessdata):
        if record is not None:
            record.append({"psm": psm, "bytes": len(png_bytes), "tessdata": tessdata})
        index = calls["n"]
        calls["n"] += 1
        if isinstance(text_by_call, (list, tuple)):
            return text_by_call[index] if index < len(text_by_call) else default
        return text_by_call if text_by_call is not None else default

    return read


def _engine():
    return (rx.ENGINE_TESSERACT, "4.1.1", pymupdf)


class ScaleParsingTests(unittest.TestCase):
    """Deterministic parsing. Never inference, never QUANTITATIVE."""

    def test_metric_notation_is_read_but_only_as_review_needed(self):
        parsed = seg.parse_scale_notation("OVERALL FLOOR PLAN  SCALE 1:100")
        self.assertEqual(parsed["scale_value"], 100.0)
        self.assertEqual(parsed["scale_state"], SCALE_STATE_REVIEW_NEEDED)
        self.assertEqual(parsed["unit_system"], "metric")

    def test_a_parsed_scale_is_never_quantitative(self):
        """OCR of a scan cannot authorise measurement - 1:100 and 1:400 differ
        by one character."""
        for text in ("SCALE 1:50", "1 : 200", 'SCALE 1/4" = 1\'-0"'):
            with self.subTest(text=text):
                self.assertNotEqual(seg.parse_scale_notation(text)["scale_state"],
                                    SCALE_STATE_QUANTITATIVE)

    def test_nts_is_informative_not_missing(self):
        for text in ("TYPICAL DETAIL N.T.S.", "NOT TO SCALE", "detail nts"):
            with self.subTest(text=text):
                parsed = seg.parse_scale_notation(text)
                self.assertEqual(parsed["scale_state"], SCALE_STATE_INFORMATIVE)
                self.assertEqual(parsed["scale_notation"], "NTS")

    def test_imperial_notation_converts_correctly(self):
        parsed = seg.parse_scale_notation('SCALE 1/4" = 1\'-0"')
        self.assertEqual(parsed["scale_value"], 48.0)
        self.assertEqual(parsed["unit_system"], "imperial")

    def test_text_with_no_scale_returns_nothing_rather_than_a_default(self):
        self.assertIsNone(seg.parse_scale_notation("GENERAL NOTES"))
        self.assertIsNone(seg.parse_scale_notation(""))


class TitleBlockConventionTests(unittest.TestCase):
    """A convention, offered as candidates - never a detection."""

    def test_both_conventions_are_offered_rather_than_one_guessed(self):
        candidates = seg.propose_title_block_candidates(SHEET_WIDTH, SHEET_HEIGHT)
        self.assertEqual({c["convention"] for c in candidates},
                         {seg.TITLE_BLOCK_RIGHT_STRIP, seg.TITLE_BLOCK_BOTTOM_STRIP})

    def test_candidate_confidence_is_low_because_it_is_only_a_convention(self):
        for candidate in seg.propose_title_block_candidates(SHEET_WIDTH, SHEET_HEIGHT):
            self.assertLessEqual(candidate["confidence"], 0.5)

    def test_candidates_are_inside_the_page(self):
        for candidate in seg.propose_title_block_candidates(SHEET_WIDTH, SHEET_HEIGHT):
            x0, y0, x1, y1 = candidate["rect"]
            self.assertGreaterEqual(x0, 0)
            self.assertGreaterEqual(y0, 0)
            self.assertLessEqual(x1, SHEET_WIDTH)
            self.assertLessEqual(y1, SHEET_HEIGHT)


class RegionOcrTests(unittest.TestCase):
    """The measured finding: region + page-segmentation-mode, not region alone."""

    def setUp(self):
        self.raw = _multi_view_sheet()

    def test_the_fixture_really_has_no_text_layer(self):
        from services.bhive_parser import BHiveParser
        pages = BHiveParser.extract_pdf_pages(self.raw)
        self.assertEqual(rx.needs_raster_fallback(pages), [0],
                         "the fixture still has a text layer, so it proves nothing")

    def test_the_page_segmentation_mode_is_actually_passed_to_the_engine(self):
        """This is what doubled legibility on the real sheet - if it silently
        stopped being passed, nothing else here would notice."""
        record = []
        seg.read_region(self.raw, 0, (0, 0, 100, 100), psm=11,
                        engine=_engine(), reader=_reader("TEXT", record=record))
        self.assertEqual(record[0]["psm"], 11)

    def test_the_default_mode_is_the_measured_one(self):
        record = []
        seg.read_region(self.raw, 0, (0, 0, 100, 100),
                        engine=_engine(), reader=_reader("TEXT", record=record))
        self.assertEqual(record[0]["psm"], rx.DEFAULT_REGION_PSM)

    def test_legibility_separates_real_text_from_noise(self):
        noise = "_- Suse Sa ae ctmaat ies cr a io - so"
        real = "LOCATION 1860 ALSTEP DRIVE MISSISSAUGA ONTARIO"
        self.assertGreater(rx.legible_ratio(real), rx.legible_ratio(noise) * 2)

    def test_the_best_reading_is_chosen_by_legibility_not_length(self):
        readings = [
            {"ran": True, "text": "a b c d e f g h i j k l m n o p", "legible_ratio": 0.1},
            {"ran": True, "text": "GROUND FLOOR PLAN", "legible_ratio": 0.9},
        ]
        self.assertEqual(seg.best_reading(readings)["text"], "GROUND FLOOR PLAN")

    def test_no_usable_reading_returns_none_rather_than_noise(self):
        self.assertIsNone(seg.best_reading([{"ran": False, "text": ""}]))

    def test_the_region_rect_and_rotation_are_reported_back(self):
        result = seg.read_region(self.raw, 0, (10, 20, 110, 120), rotate=90,
                                 engine=_engine(), reader=_reader("X"))
        self.assertEqual(result["rect"], [10, 20, 110, 120])
        self.assertEqual(result["rotate"], 90)


class SegmentSheetTests(unittest.TestCase):
    """6A/6E. Candidates become governed DerivedViews that inherit identity."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_seg_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-seg")
        self.raw = _multi_view_sheet()

        path = self.tmp_dir / "A-101.pdf"
        path.write_bytes(self.raw)
        self.source = self.store.add_source(
            self.workspace, name="A-101.pdf", file_path=str(path),
            kind=SOURCE_KIND_DRAWING, document_id="A-101", revision="3",
            issuer="Dadras Architects", actor="tester")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, self.source["id"],
            [{"index": 0, "label": "A-101 GROUND FLOOR PLAN",
              "width": SHEET_WIDTH, "height": SHEET_HEIGHT,
              "source_rotation": 0, "metadata": {"discipline": "architectural"}}],
            actor="tester")
        self.page_unit_id = registered["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _segment(self, text="A-101 GROUND FLOOR PLAN  SCALE 1:100", **kw):
        return seg.segment_sheet(
            self.store, self.workspace, self.source["id"], self.page_unit_id,
            self.raw, 0, SHEET_WIDTH, SHEET_HEIGHT, actor="tester",
            engine=_engine(), reader=_reader(text), **kw)

    def test_it_creates_governed_derived_views_for_each_candidate(self):
        result = self._segment()
        self.assertEqual(len(result["candidates"]), 2)
        stored = self.store.derived_views_for(
            self.workspace, page_structural_unit_id=self.page_unit_id)
        self.assertEqual(len(stored), 2)

    def test_each_view_inherits_the_sheet_title_block(self):
        result = self._segment()
        for candidate in result["candidates"]:
            inherited = candidate["derived_view"]["inherited_title_block"]
            self.assertEqual(inherited["document_id"], "A-101")
            self.assertEqual(inherited["revision"], "3")
            self.assertEqual(inherited["sheet_fields"]["discipline"], "architectural")

    def test_a_parsed_scale_lands_on_the_view_as_review_needed(self):
        result = self._segment(text="OVERALL FLOOR PLAN SCALE 1:100")
        view = result["candidates"][0]["derived_view"]
        self.assertEqual(view["scale_value"], 100.0)
        self.assertEqual(view["scale_state"], SCALE_STATE_REVIEW_NEEDED)
        self.assertFalse(dv.may_measure(view)[0])

    def test_an_nts_reading_lands_as_informative_and_stays_readable(self):
        result = self._segment(text="TYPICAL DETAIL N.T.S.")
        view = result["candidates"][0]["derived_view"]
        self.assertEqual(view["scale_state"], SCALE_STATE_INFORMATIVE)
        self.assertFalse(dv.may_measure(view)[0])
        self.assertTrue(dv.may_use_semantically(view)[0])

    def test_a_view_with_no_scale_text_stays_unknown_rather_than_guessing(self):
        result = self._segment(text="GENERAL NOTES AND LEGEND")
        self.assertEqual(result["candidates"][0]["derived_view"]["scale_state"], "unknown")

    def test_segmentation_never_produces_a_quantitative_view(self):
        """Only a human may authorise measurement."""
        result = self._segment(text="SCALE 1:50")
        for candidate in result["candidates"]:
            self.assertNotEqual(candidate["derived_view"]["scale_state"],
                                SCALE_STATE_QUANTITATIVE)

    def test_a_human_confirmation_is_what_makes_a_view_quantitative(self):
        confirmed = self.store.create_derived_view(
            self.workspace, source_id=self.source["id"],
            page_structural_unit_id=self.page_unit_id,
            region={"x": 0, "y": 0, "width": 100, "height": 100},
            derivation_reason="human confirmed overall plan", actor="pm",
            scale_state=SCALE_STATE_QUANTITATIVE, scale_value=100.0,
            scale_notation="1:100", scale_method=SCALE_METHOD_MANUAL_CONFIRMATION,
            unit_system="metric")
        self.assertTrue(dv.may_measure(confirmed)[0])

    def test_the_authoritative_pdf_is_not_modified_by_segmentation(self):
        path = self.tmp_dir / "A-101.pdf"
        before = path.read_bytes()
        self._segment()
        self.assertEqual(path.read_bytes(), before)

    def test_rotations_are_tried_and_the_best_is_recorded(self):
        result = seg.segment_sheet(
            self.store, self.workspace, self.source["id"], self.page_unit_id,
            self.raw, 0, SHEET_WIDTH, SHEET_HEIGHT, actor="tester",
            rotations=(0, 90), engine=_engine(),
            reader=_reader(["noise x y", "SECTION A-A SCALE 1:20",
                            "noise x y", "SECTION A-A SCALE 1:20"]))
        best = result["candidates"][0]
        self.assertIn("SECTION", (best["reading"]["text"] or ""))

    def test_one_view_cannot_contaminate_anothers_scale(self):
        """Two candidates read differently must not share a scale."""
        result = seg.segment_sheet(
            self.store, self.workspace, self.source["id"], self.page_unit_id,
            self.raw, 0, SHEET_WIDTH, SHEET_HEIGHT, actor="tester",
            engine=_engine(), reader=_reader(["PLAN SCALE 1:100", "DETAIL N.T.S."]))
        states = [c["derived_view"]["scale_state"] for c in result["candidates"]]
        self.assertEqual(states, [SCALE_STATE_REVIEW_NEEDED, SCALE_STATE_INFORMATIVE])
        values = [c["derived_view"]["scale_value"] for c in result["candidates"]]
        self.assertEqual(values, [100.0, None])

    def test_views_from_one_sheet_do_not_share_a_north(self):
        """Nothing here detects North, so every view must stay UNKNOWN rather
        than inheriting a neighbour's."""
        result = self._segment()
        for candidate in result["candidates"]:
            self.assertEqual(candidate["derived_view"]["north_state"], "unknown")

    def test_cross_project_isolation(self):
        self._segment()
        other = self.store.get_or_create("test-project-seg-other")
        self.assertEqual(self.store.derived_views_for(other), [])


if __name__ == "__main__":
    unittest.main()
