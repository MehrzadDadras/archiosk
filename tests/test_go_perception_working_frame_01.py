"""CLAUDE-GO-PERCEPTION-WORKING-FRAME-01: the frame is a decision, not a side-effect.

The defect was never a quality defect. `normalise_orientation` re-encodes to PNG
when it rotates and passes the original bytes through when it does not, and the
callers then derived `filetype` from that same fact — so the SAME photograph of
the SAME drawing was read through a different container depending on which way
up the phone was held. The container is not cosmetic: measured on three real
drawing rasters, the pixels PyMuPDF finally hands the OCR engine differ between
the two by 20–56% of the frame, maximum per-channel delta 147.

WHAT THE MEASUREMENT ACTUALLY SAID, because it is not what the tranche expected.
The recorded 4,953 → 9,548 character result came from a customer JPEG that is
not on this machine and **did not reproduce**. On three real rasters delivered
as JPEG a lossless frame gave **+7.8%, −3.7% and −11.5%** characters — mixed and
source-dependent. What it did do is improve the downstream answer on two of
three (A-01 gained a SUPPORTED `LEGEND` candidate it did not find at all;
M2_OF_3 gained `LEGENDS:`) and degrade it on none. On an already-PNG source the
re-encode is provably a no-op: every metric moved 0.0% on all three sources.

So these tests defend DETERMINISM AND EQUAL TREATMENT, which is what the
evidence supports — not a quality claim it does not.
"""
from __future__ import annotations

import ast
import io
import unittest
from pathlib import Path

from PIL import Image

from services import image_intake as ii

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _image_bytes(fmt, size=(400, 300), orientation=None, colour=(240, 240, 240)):
    image = Image.new("RGB", size, colour)
    buffer = io.BytesIO()
    if orientation is not None and fmt == "JPEG":
        exif = image.getexif()
        exif[274] = orientation
        image.save(buffer, fmt, exif=exif.tobytes())
    else:
        image.save(buffer, fmt)
    return buffer.getvalue()


def _frame_for(raw, filename):
    normalised = ii.normalise_orientation(raw, filename)
    return ii.working_frame(normalised, filename)


class TheFrameNoLongerDependsOnRotation(unittest.TestCase):
    """The defect, stated as the product sentence."""

    def test_an_upright_jpeg_and_a_rotated_jpeg_get_the_same_container(self):
        upright, _ = _frame_for(_image_bytes("JPEG", orientation=1), "p.jpg")
        rotated, _ = _frame_for(_image_bytes("JPEG", orientation=6), "p.jpg")
        self.assertEqual(Image.open(io.BytesIO(upright)).format, "PNG")
        self.assertEqual(Image.open(io.BytesIO(rotated)).format, "PNG")

    def test_every_supported_input_yields_one_declared_filetype(self):
        for name, raw in (("p.jpg", _image_bytes("JPEG", orientation=1)),
                          ("p.jpeg", _image_bytes("JPEG", orientation=6)),
                          ("p.png", _image_bytes("PNG"))):
            with self.subTest(source=name):
                _frame, filetype = _frame_for(raw, name)
                self.assertEqual(filetype, ii.WORKING_FRAME_FILETYPE)

    def test_the_frame_decision_is_not_conditional_on_rotation_anywhere(self):
        """The literal shape of the defect, so it cannot quietly come back."""
        source = (_REPO_ROOT / "services" / "image_intake.py").read_text(
            encoding="utf-8")
        self.assertNotIn('"png" if (ext == ".png" or orientation["changed"]) else "jpeg"',
                         source)
        self.assertEqual(source.count("frame, filetype = working_frame("), 1)
        self.assertEqual(source.count("frame_bytes, filetype = working_frame("), 1)


class OrientationIsUnaffected(unittest.TestCase):
    """A and B are now separate decisions; A must not have moved."""

    def test_an_upright_image_is_still_not_rotated(self):
        out = ii.normalise_orientation(_image_bytes("JPEG", orientation=1), "p.jpg")
        self.assertFalse(out["observation"]["changed"])
        self.assertEqual(out["observation"]["applied_rotation_degrees"], 0)

    def test_a_rotated_image_is_still_uprighted(self):
        out = ii.normalise_orientation(
            _image_bytes("JPEG", size=(400, 300), orientation=6), "p.jpg")
        self.assertTrue(out["observation"]["changed"])
        self.assertEqual(Image.open(io.BytesIO(out["bytes"])).size, (300, 400))

    def test_normalise_orientation_still_passes_an_upright_source_through(self):
        """Its own contract is unchanged - the working frame is built AFTER it,
        so source preservation is still proven at the earlier boundary."""
        raw = _image_bytes("JPEG", orientation=1)
        self.assertIs(ii.normalise_orientation(raw, "p.jpg")["bytes"], raw)


class SourcePreservation(unittest.TestCase):

    def test_the_callers_bytes_are_never_altered(self):
        for name, raw in (("p.jpg", _image_bytes("JPEG", orientation=1)),
                          ("p.jpg", _image_bytes("JPEG", orientation=6)),
                          ("p.png", _image_bytes("PNG"))):
            with self.subTest(source=name):
                before = bytes(raw)
                _frame_for(raw, name)
                self.assertEqual(raw, before)

    def test_the_working_frame_is_derived_and_carries_the_same_pixels(self):
        raw = _image_bytes("JPEG", size=(320, 240), orientation=1)
        frame, _ = _frame_for(raw, "p.jpg")
        self.assertNotEqual(frame, raw, "a derived frame, not the source")
        self.assertEqual(Image.open(io.BytesIO(frame)).size,
                         Image.open(io.BytesIO(raw)).size)


class NoEnhancementNoEgressNoMagnitude(unittest.TestCase):

    def test_the_frame_is_re_containered_and_nothing_else(self):
        """No sharpening, denoising, thresholding, rescaling or model run."""
        tree = ast.parse((_REPO_ROOT / "services" / "image_intake.py").read_text(
            encoding="utf-8"))
        target = next(node for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      and node.name == "working_frame")
        called = set()
        for child in ast.walk(target):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        for forbidden in ("filter", "resize", "thumbnail", "point", "autocontrast",
                          "equalize", "sharpen", "UnsharpMask", "MedianFilter",
                          "convert_to_grayscale", "binarize"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)
        self.assertIn("_encode_frame", called)

    def test_no_network_call_exists_in_the_module(self):
        source = (_REPO_ROOT / "services" / "image_intake.py").read_text(
            encoding="utf-8")
        for forbidden in ("requests", "urlopen", "httpx", "socket",
                          "call_gemini_json", "read_sheet"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_no_magnitude_or_scale_is_derived(self):
        source = (_REPO_ROOT / "services" / "image_intake.py").read_text(
            encoding="utf-8")
        window = source[source.index("def working_frame"):]
        window = window[:window.index("\ndef ", 10)]
        for forbidden in ("scale_value", "mm", "millimet", "calibrat",
                          "measure_", "magnitude"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, window)


class HonestDegradation(unittest.TestCase):

    def test_an_undecodable_frame_falls_back_rather_than_failing(self):
        """A frame that cannot be decoded here would not survive the extractor
        either; handing over what arrived keeps the old behaviour rather than
        turning a marginal image into no reading at all."""
        normalised = {"bytes": b"not really an image",
                      "observation": {"changed": False}}
        frame, filetype = ii.working_frame(normalised, "p.jpg")
        self.assertEqual(frame, b"not really an image")
        self.assertEqual(filetype, "jpeg")

    def test_an_already_png_source_is_passed_through_without_re_encoding(self):
        """Measured: a PNG round trip moved every metric 0.0% on three real
        sources, so the work would buy nothing."""
        raw = _image_bytes("PNG")
        normalised = ii.normalise_orientation(raw, "p.png")
        frame, _ = ii.working_frame(normalised, "p.png")
        self.assertIs(frame, normalised["bytes"])

    def test_a_rotated_frame_is_not_encoded_a_second_time(self):
        raw = _image_bytes("JPEG", orientation=6)
        normalised = ii.normalise_orientation(raw, "p.jpg")
        frame, _ = ii.working_frame(normalised, "p.jpg")
        self.assertIs(frame, normalised["bytes"],
                      "normalise_orientation already produced a lossless frame")


class PhaseOneAIsUnaffected(unittest.TestCase):
    """The PDF path does not use the image working frame at all."""

    def test_the_pdf_reader_does_not_call_working_frame(self):
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
        self.assertNotIn("working_frame", called)
        self.assertNotIn("normalise_orientation", called)

    def test_the_native_pdf_text_path_is_untouched(self):
        source = (_REPO_ROOT / "services" / "positioned_text.py").read_text(
            encoding="utf-8")
        self.assertIn("def _native_positioned_lines", source)
        self.assertIn("page_has_usable_text", source)

    def test_the_worker_pdf_branch_does_not_reach_image_intake_frames(self):
        source = (_REPO_ROOT / "services" / "perception_worker.py").read_text(
            encoding="utf-8")
        window = source[source.index("def _run_pdf_job"):]
        window = window[:window.index("\ndef _write_pdf_pages_with_retry")]
        self.assertNotIn("working_frame", window)
        self.assertNotIn("normalise_orientation", window)


if __name__ == "__main__":
    unittest.main()
