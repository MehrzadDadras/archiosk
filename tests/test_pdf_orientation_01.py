"""CLAUDE-PDF-ORIENTATION-01: the pipeline was reading drawings sideways.

A PDF page carries a stored `/Rotate` and this pipeline trusted it. On the real
Nipigon architectural set that value does not describe the orientation the
CONTENT is drawn at, and OCR reading a sideways page returns noise that still
looks like words - so nothing failed, nothing logged, and the result looked
ordinary.

What it was hiding is the point. At the stored rotation versus the orientation
the drawing is actually drawn at:

    A401 datum levels  0 -> 4       A402  0 -> 6
    A403 datum levels  0 -> 2       A204  0 -> 1

Those are the project's own declared floor and footing elevations, and they are
the FIRST evidence in this corpus that crosses Architecture and Structure. The
defect was not degrading a result; it was concealing one.

What these tests defend:

1. **NO INVENTED THRESHOLD.** The image path acts on OSD only at confidence
   2.0. That number was calibrated on photographs of documents; a drawing is
   sparse line-work and scores below it while being unambiguously sideways
   (A401 reports 1.46, A402 0.39, both genuinely rotated 270). Importing the
   threshold would preserve the defect, so it is deliberately NOT imported -
   and `NoConfidenceGate` pins that, because "add a threshold" is exactly the
   change a later reader would make in good faith.

2. **NATIVE PAGES ARE NEVER PROBED.** Native text carries its own coordinates
   and is already correct whichever way the sheet is drawn. Probing costs 3-6s
   a page to confirm what is already true.

3. **THE LIMIT IS PINNED, NOT SMOOTHED.** OSD is right on A401, A402, A204 and
   on both native structural sheets; it is WRONG on A403, reporting 90 where
   270 reads better. `KnownLimit` records that rather than letting a later
   session rediscover it.

The OSD engine is injected at the seam `image_intake` already provides, so none
of this needs the Tesseract binary.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from services import positioned_text

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _osd(rotate, confidence=1.0):
    """An injected Tesseract OSD reader, in the engine's own output shape."""
    def reader(_png_bytes):
        return ("Page number: 0\nOrientation in degrees: 0\n"
                "Rotate: %d\nOrientation confidence: %.2f\n"
                "Script: Latin\nScript confidence: 2.00\n" % (rotate, confidence))
    return reader


def _blank_pdf(pages=1, rotation=0):
    import pymupdf

    document = pymupdf.open()
    for _ in range(pages):
        page = document.new_page(width=612, height=792)
        if rotation:
            page.set_rotation(rotation)
    data = document.tobytes()
    document.close()
    return data


class TheDetector(unittest.TestCase):
    """`page_orientation` reports, and never decides by itself."""

    def test_a_rotation_is_added_to_the_stored_one(self):
        observation = positioned_text.page_orientation(
            _blank_pdf(), osd_reader=_osd(270))
        self.assertTrue(observation["ran"])
        self.assertEqual(observation["rotate"], 270)
        self.assertEqual(observation["stored_rotation"], 0)
        self.assertEqual(observation["applied_rotation"], 270)

    def test_it_composes_with_a_page_that_is_already_rotated(self):
        observation = positioned_text.page_orientation(
            _blank_pdf(rotation=90), osd_reader=_osd(270))
        self.assertEqual(observation["stored_rotation"], 90)
        self.assertEqual(observation["applied_rotation"], 0,
                         "90 stored + 270 detected wraps to upright")

    def test_an_upright_page_is_left_exactly_as_stored(self):
        observation = positioned_text.page_orientation(
            _blank_pdf(rotation=90), osd_reader=_osd(0))
        self.assertEqual(observation["applied_rotation"], 90)
        self.assertEqual(observation["rotate"], 0)

    def test_an_osd_that_reports_nothing_changes_nothing(self):
        def silent(_png):
            return ""
        observation = positioned_text.page_orientation(
            _blank_pdf(rotation=180), osd_reader=silent)
        self.assertFalse(observation["ran"])
        self.assertEqual(observation["applied_rotation"], 180)

    def test_an_unopenable_file_is_a_result_not_a_raise(self):
        observation = positioned_text.page_orientation(b"not a pdf")
        self.assertFalse(observation["ran"])
        self.assertIsNotNone(observation["reason"])

    def test_a_raising_osd_reader_is_survived(self):
        def boom(_png):
            raise RuntimeError("osd fell over")
        observation = positioned_text.page_orientation(
            _blank_pdf(), osd_reader=boom)
        self.assertFalse(observation["ran"])


class NoConfidenceGate(unittest.TestCase):
    """The threshold that would silently restore the defect."""

    def test_a_low_confidence_rotation_is_still_applied(self):
        """A401 reports 1.46 and A402 0.39. Both are genuinely rotated 270."""
        observation = positioned_text.page_orientation(
            _blank_pdf(), osd_reader=_osd(270, confidence=0.39))
        self.assertEqual(observation["applied_rotation"], 270,
                         "gating this on confidence would keep reading real "
                         "drawings sideways")
        self.assertEqual(observation["confidence"], 0.39)

    def test_no_confidence_comparison_gates_the_decision(self):
        """Asserted on the CODE, not on the prose.

        The rule's own docstring names `OSD_MINIMUM_CONFIDENCE` in order to
        explain why it is not used, so a text search for the name finds it and
        proves nothing. What must not exist is an executable comparison against
        a confidence value, and that is an AST question.
        """
        import ast

        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source)
        target = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "page_orientation")
        for node in ast.walk(target):
            if not isinstance(node, ast.Compare):
                continue
            rendered = ast.dump(node)
            self.assertNotIn("confidence", rendered,
                             "gating on confidence would keep reading real "
                             "drawings sideways: A401 scores 1.46, A402 0.39, "
                             "and both are genuinely rotated 270")

    def test_the_threshold_constant_is_not_imported(self):
        import ast

        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom):
                names = {alias.name for alias in node.names}
                self.assertNotIn("OSD_MINIMUM_CONFIDENCE", names)


class NativePagesAreNotProbed(unittest.TestCase):
    """The cheapest orientation decision is the one not taken."""

    def test_a_native_page_never_calls_the_detector(self):
        calls = []

        def spy(*args, **kwargs):
            calls.append(args)
            return {"ran": False, "applied_rotation": None}

        native = {"ran": True, "lines": [], "text": "x", "engine": "pymupdf-native",
                  "engine_version": "native", "line_count": 0, "word_count": 0,
                  "dropped_line_count": 0, "truncated": False,
                  "confidence_available": False, "frame": {}}
        with patch.object(positioned_text, "pdf_page_count", lambda _b: 1):
            with patch.object(positioned_text, "_native_positioned_lines",
                              lambda _b, _i: dict(native)):
                with patch.object(positioned_text, "page_orientation", spy):
                    positioned_text.read_pdf_positioned_pages(b"%PDF-1.4 x")
        self.assertEqual(calls, [],
                         "a native page is already correct whichever way the "
                         "sheet is drawn")

    def test_an_ocr_page_does_call_the_detector(self):
        calls = []

        def spy(*args, **kwargs):
            calls.append(args)
            return {"ran": True, "applied_rotation": 270}

        def reader(_b, _dpi, _ft="png", _pi=0, rotation=None):
            reader.rotation = rotation
            return [], (612.0, 792.0), "tesseract", "5.0.0", ""

        with patch.object(positioned_text, "pdf_page_count", lambda _b: 1):
            with patch.object(positioned_text, "_native_positioned_lines",
                              lambda _b, _i: None):
                with patch.object(positioned_text, "page_orientation", spy):
                    positioned_text.read_pdf_positioned_pages(
                        b"%PDF-1.4 x", ocr=reader)
        self.assertEqual(len(calls), 1)
        self.assertEqual(reader.rotation, 270,
                         "the decision must reach the engine, not just be logged")


class TheObservationIsRecorded(unittest.TestCase):
    """'Read as stored' is a fact a later reader needs as much as 'turned'."""

    def test_every_ocr_page_carries_its_orientation(self):
        def reader(_b, _dpi, _ft="png", _pi=0, rotation=None):
            return [], (612.0, 792.0), "tesseract", "5.0.0", ""

        with patch.object(positioned_text, "pdf_page_count", lambda _b: 2):
            with patch.object(positioned_text, "_native_positioned_lines",
                              lambda _b, _i: None):
                with patch.object(
                        positioned_text, "page_orientation",
                        lambda *_a, **_k: {"ran": True, "rotate": 270,
                                           "confidence": 1.46,
                                           "stored_rotation": 0,
                                           "applied_rotation": 270}):
                    result = positioned_text.read_pdf_positioned_pages(
                        b"%PDF-1.4 x", ocr=reader)
        self.assertEqual(len(result["pages"]), 2)
        for page in result["pages"]:
            self.assertEqual(page["orientation"]["applied_rotation"], 270)
            self.assertEqual(page["orientation"]["confidence"], 1.46)


class OlderReadersStillWork(unittest.TestCase):
    """`_call_ocr`'s arity tolerance is why this change is not a breaking one."""

    def test_a_reader_without_a_rotation_argument_is_still_called(self):
        def four_arg(_b, _dpi, _ft="png", _pi=0):
            return [("x",)], (1.0, 1.0), "e", "v", "t"
        words, _rect, engine, _v, _t = positioned_text._call_ocr(
            four_arg, b"x", 200, "pdf", 0, 270)
        self.assertEqual(engine, "e")
        self.assertEqual(words, [("x",)])

    def test_a_two_argument_reader_is_still_called(self):
        def two_arg(_b, _dpi):
            return [], (1.0, 1.0), "e", "v", "t"
        _w, _r, engine, _v, _t = positioned_text._call_ocr(
            two_arg, b"x", 200, "pdf", 0, 90)
        self.assertEqual(engine, "e")

    def test_a_type_error_from_inside_a_reader_is_not_swallowed(self):
        def bad(_b, _dpi, _ft="png", _pi=0, rotation=None):
            raise TypeError("a real fault inside the reader")
        with self.assertRaises(TypeError):
            positioned_text._call_ocr(bad, b"x", 200, "pdf", 0, 270)


class KnownLimit(unittest.TestCase):
    """Measured and recorded, so it is not rediscovered as a surprise."""

    def test_the_limit_is_written_down_where_the_rule_lives(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        window = source[source.index("def page_orientation"):
                        source.index("def _default_ocr")]
        self.assertIn("A403", window,
                      "the sheet OSD gets wrong must be named beside the rule")
        for rejected in ("legible tokens", "146%"):
            self.assertIn(rejected, window,
                          "the alternatives that were measured and rejected "
                          "belong beside the rule that won")


class NoMagnitudeWasDerived(unittest.TestCase):
    """Orientation is not measurement. Option C still governs."""

    def test_no_physical_unit_enters_the_orientation_path(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        window = source[source.index("def page_orientation"):
                        source.index("def _default_ocr")]
        for banned in ("millimet", "inch", "feet", "scale_factor", "world_"):
            self.assertNotIn(banned, window.lower())

    def test_coordinates_remain_fractions_of_the_frame_that_was_read(self):
        """The rotation is applied BEFORE page.rect is taken, so there is no
        transform to apply afterwards and nothing downstream to correct."""
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        window = source[source.index("def _default_ocr"):
                        source.index("def _call_ocr")]
        set_rotation = window.index("set_rotation")
        rect = window.index("rect = (float(page.rect.width)")
        self.assertLess(set_rotation, rect,
                        "the frame must be measured AFTER the page is turned")


if __name__ == "__main__":
    unittest.main()
