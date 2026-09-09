"""CLAUDE-GO-PERCEPTION-ORIENTATION-01 - the first perceptual invariant.

    GO'S MACHINE VIEW OF THE SOURCE MUST HAVE THE SAME INTENDED ORIENTATION
    AS THE HUMAN VIEW.

A phone stores a photograph rotated and declares the intended view in EXIF.
Browsers honour that, so the customer sees it upright; PyMuPDF does not, so the
OCR path was reading the stored pixels sideways. Proven on a real customer JPEG
carrying Orientation 6.

These tests deliberately do NOT assert that OCR quality improves. Measured on
the real drawing, correcting orientation did not rescue recognition (0.120 ->
0.139 legible). Orientation is a correctness invariant on its own; claiming a
quality win it does not deliver would be the overclaim this codebase keeps
having to correct.
"""
import io
import unittest

from PIL import Image

from services import image_intake as ii


def _jpeg_with_orientation(value, size=(400, 300)):
    """A real JPEG carrying a real EXIF orientation tag."""
    image = Image.new("RGB", size, (240, 240, 235))
    exif = image.getexif()
    exif[274] = value
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def _jpeg_without_exif(size=(400, 300)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (240, 240, 235)).save(buffer, "JPEG")
    return buffer.getvalue()


def _png(size=(400, 300)):
    buffer = io.BytesIO()
    Image.new("RGB", size, (240, 240, 235)).save(buffer, "PNG")
    return buffer.getvalue()


def _osd(rotate, confidence=12.0, script="Latin"):
    """An injected OSD reader - no Tesseract binary needed by any test."""
    text = ("Page number: 0\nOrientation in degrees: %d\nRotate: %d\n"
            "Orientation confidence: %.2f\nScript: %s\nScript confidence: 4.0\n"
            % (rotate, rotate, confidence, script))
    return lambda _bytes: text


def _no_osd(_bytes):
    raise RuntimeError("tesseract unavailable")


class SourcePreservationTests(unittest.TestCase):
    """SOURCE IS NOT MUTATED - the rule everything else hangs off."""

    def test_original_bytes_are_never_returned_altered_when_upright(self):
        raw = _jpeg_with_orientation(1)
        out = ii.normalise_orientation(raw, "photo.jpg")
        self.assertIs(out["bytes"], raw, "upright image was needlessly re-encoded")
        self.assertFalse(out["observation"]["changed"])

    def test_a_rotated_source_is_transformed_only_in_the_derived_frame(self):
        raw = _jpeg_with_orientation(6)
        out = ii.normalise_orientation(raw, "photo.jpg")
        self.assertTrue(out["observation"]["changed"])
        self.assertNotEqual(out["bytes"], raw)
        # the caller's own bytes object is untouched
        self.assertEqual(raw, _jpeg_with_orientation(6))
        still = Image.open(io.BytesIO(raw))
        self.assertEqual(still.getexif().get(274), 6,
                         "EXIF was rewritten on the source")

    def test_the_derived_frame_is_lossless(self):
        """A JPEG round trip would add artefacts to the pixels the next stage
        is trying to read."""
        out = ii.normalise_orientation(_jpeg_with_orientation(6), "photo.jpg")
        self.assertEqual(Image.open(io.BytesIO(out["bytes"])).format, "PNG")


class ExifAuthorityTests(unittest.TestCase):
    """EXIF is the device's own statement of intended display."""

    def test_orientation_6_becomes_upright(self):
        """The proven customer case: landscape pixels, portrait intent."""
        raw = _jpeg_with_orientation(6, size=(4032 // 8, 3024 // 8))
        out = ii.normalise_orientation(raw, "image.jpg")
        obs = out["observation"]
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_EXIF)
        self.assertEqual(obs["exif_orientation"], 6)
        self.assertEqual(obs["native_size"], [504, 378])
        self.assertEqual(obs["normalised_size"], [378, 504],
                         "dimensions did not transpose")
        self.assertTrue(obs["changed"])

    def test_every_exif_orientation_is_handled(self):
        """Not just 6. Mirrored cases included, because Pillow applies them."""
        expected_transposed = {5, 6, 7, 8}
        for value in range(1, 9):
            with self.subTest(orientation=value):
                out = ii.normalise_orientation(
                    _jpeg_with_orientation(value), "photo.jpg")
                obs = out["observation"]
                self.assertEqual(obs["exif_orientation"], value)
                self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_EXIF)
                if value in expected_transposed:
                    self.assertEqual(obs["normalised_size"], [300, 400])
                else:
                    self.assertEqual(obs["normalised_size"], [400, 300])

    def test_mirrored_orientations_record_the_mirror(self):
        for value in (2, 4, 5, 7):
            with self.subTest(orientation=value):
                obs = ii.normalise_orientation(
                    _jpeg_with_orientation(value), "photo.jpg")["observation"]
                self.assertTrue(obs["applied_mirror"])

    def test_orientation_1_changes_nothing(self):
        obs = ii.normalise_orientation(
            _jpeg_with_orientation(1), "photo.jpg")["observation"]
        self.assertFalse(obs["changed"])
        self.assertEqual(obs["applied_rotation_degrees"], 0)


class OsdSubordinateTests(unittest.TestCase):
    """OSD is perception EVIDENCE. It decides only where EXIF is silent."""

    def test_osd_is_used_when_there_is_no_exif(self):
        out = ii.normalise_orientation(
            _jpeg_without_exif(), "scan.jpg", osd_reader=_osd(90))
        obs = out["observation"]
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_OSD)
        self.assertEqual(obs["applied_rotation_degrees"], 90)
        self.assertEqual(obs["normalised_size"], [300, 400])
        self.assertTrue(obs["changed"])

    def test_osd_evidence_is_recorded_with_its_engine(self):
        obs = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=_osd(180, confidence=7.5))["observation"]
        self.assertEqual(obs["osd"]["rotate"], 180)
        self.assertEqual(obs["osd"]["confidence"], 7.5)
        self.assertEqual(obs["osd"]["script"], "Latin")
        self.assertTrue(obs["osd"]["engine"])

    def test_exif_outranks_a_disagreeing_osd(self):
        """The declared rule, exercised on the conflict it exists for."""
        out = ii.normalise_orientation(
            _jpeg_with_orientation(6), "photo.jpg",
            osd_reader=_osd(90), observe_osd=True)
        obs = out["observation"]
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_EXIF)
        self.assertEqual(obs["applied_rotation_degrees"], 270,
                         "OSD overrode an authoritative EXIF tag")
        self.assertTrue(obs["conflict"], "the disagreement was not recorded")

    def test_agreement_is_not_reported_as_conflict(self):
        obs = ii.normalise_orientation(
            _jpeg_with_orientation(6), "photo.jpg",
            osd_reader=_osd(270), observe_osd=True)["observation"]
        self.assertFalse(obs["conflict"])

    def test_production_does_not_pay_for_osd_when_exif_decides(self):
        """A second Tesseract pass costs seconds and would buy nothing."""
        calls = []

        def counting(_bytes):
            calls.append(1)
            return _osd(90)(_bytes)

        ii.normalise_orientation(_jpeg_with_orientation(6), "photo.jpg")
        self.assertEqual(calls, [], "OSD ran although EXIF already decided")


class OsdConfidenceFloorTests(unittest.TestCase):
    """A guess that rotates the customer's drawing is worse than doing nothing.

    Measured on this host: real prose scores 10.13-10.99 and gets the direction
    right; sparse drawing text scores 0.12-0.15 and does not. An earlier build
    with no floor obeyed a 0.15-confidence "rotate 180, script Greek" reading of
    an upright English drawing and destroyed a clean OCR result.
    """

    def test_a_low_confidence_reading_is_refused(self):
        out = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=_osd(180, confidence=0.15))
        obs = out["observation"]
        self.assertFalse(obs["changed"], "rotated on a guess")
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_STORED)
        self.assertIn("below", obs["reason"] or "")

    def test_a_confident_reading_is_applied(self):
        obs = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=_osd(90, confidence=10.5))["observation"]
        self.assertTrue(obs["changed"])
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_OSD)

    def test_the_refusal_is_recorded_not_silent(self):
        obs = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=_osd(270, confidence=0.4))["observation"]
        self.assertIsNotNone(obs["osd"])
        self.assertEqual(obs["osd"]["rotate"], 270)
        self.assertIsNotNone(obs["reason"])

    def test_a_missing_confidence_is_treated_as_no_confidence(self):
        def no_confidence(_bytes):
            return "Rotate: 90\nScript: Latin\n"

        obs = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=no_confidence)["observation"]
        self.assertFalse(obs["changed"])

    def test_the_floor_sits_between_the_measured_populations(self):
        self.assertGreater(ii.OSD_MINIMUM_CONFIDENCE, 0.15)
        self.assertLess(ii.OSD_MINIMUM_CONFIDENCE, 10.13)


class SafeDegradationTests(unittest.TestCase):
    """Preserve source, record the gap, continue - never invent, never crash."""

    def test_no_exif_and_no_osd_leaves_the_frame_alone(self):
        raw = _jpeg_without_exif()
        out = ii.normalise_orientation(raw, "scan.jpg", osd_reader=_no_osd)
        obs = out["observation"]
        self.assertIs(out["bytes"], raw)
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_STORED)
        self.assertFalse(obs["changed"])
        self.assertIsNotNone(obs["osd"]["reason"])

    def test_osd_reporting_nothing_usable_leaves_the_frame_alone(self):
        out = ii.normalise_orientation(
            _png(), "scan.png", osd_reader=lambda _b: "Script: Latin\n")
        self.assertFalse(out["observation"]["changed"])
        self.assertFalse(out["observation"]["osd"]["ran"])

    def test_malformed_exif_is_recorded_not_obeyed(self):
        image = Image.new("RGB", (400, 300), (240, 240, 235))
        exif = image.getexif()
        exif[274] = 99  # outside 1-8
        buffer = io.BytesIO()
        image.save(buffer, "JPEG", exif=exif)
        obs = ii.normalise_orientation(
            buffer.getvalue(), "photo.jpg", osd_reader=_no_osd)["observation"]
        self.assertIsNone(obs["exif_orientation"])
        self.assertIn("unusable EXIF", obs["reason"] or "")
        self.assertFalse(obs["changed"])

    def test_undecodable_bytes_do_not_raise(self):
        out = ii.normalise_orientation(b"not an image at all", "broken.jpg")
        obs = out["observation"]
        self.assertEqual(obs["authority"], ii.ORIENTATION_AUTHORITY_UNRESOLVED)
        self.assertIs(out["bytes"], b"not an image at all")
        self.assertIn("not decodable", obs["reason"])

    def test_empty_bytes_do_not_raise(self):
        out = ii.normalise_orientation(b"", "empty.jpg")
        self.assertEqual(out["observation"]["authority"],
                         ii.ORIENTATION_AUTHORITY_UNRESOLVED)


class ExtractorIntegrationTests(unittest.TestCase):
    """The OCR adapter must consume the normalised frame and report how."""

    def test_the_extractor_reports_its_orientation_provenance(self):
        captured = {}

        def fake_pages(raw, indices, filetype=None, engine=None):
            captured["bytes"] = raw
            captured["filetype"] = filetype
            return {"ran": True, "status": "readable", "engine": "test",
                    "engine_version": "1", "reason": None, "pages": {0: "text"}}

        from services import raster_extraction
        original = raster_extraction.extract_raster_pages
        raster_extraction.extract_raster_pages = fake_pages
        try:
            result = ii.extract_image_text(_jpeg_with_orientation(6), "image.jpg")
        finally:
            raster_extraction.extract_raster_pages = original

        self.assertIn("orientation", result)
        self.assertEqual(result["orientation"]["authority"],
                         ii.ORIENTATION_AUTHORITY_EXIF)
        self.assertTrue(result["orientation"]["changed"])
        self.assertEqual(captured["filetype"], "png",
                         "a transformed frame must be described as what it is")
        self.assertEqual(Image.open(io.BytesIO(captured["bytes"])).size, (300, 400),
                         "the extractor did not receive upright pixels")

    def test_an_upright_image_reaches_the_extractor_untouched(self):
        captured = {}

        def fake_pages(raw, indices, filetype=None, engine=None):
            captured["bytes"] = raw
            captured["filetype"] = filetype
            return {"ran": True, "status": "readable", "engine": "test",
                    "engine_version": "1", "reason": None, "pages": {0: ""}}

        from services import raster_extraction
        original = raster_extraction.extract_raster_pages
        raster_extraction.extract_raster_pages = fake_pages
        try:
            raw = _jpeg_with_orientation(1)
            ii.extract_image_text(raw, "image.jpg")
        finally:
            raster_extraction.extract_raster_pages = original
        self.assertIs(captured["bytes"], raw)
        self.assertEqual(captured["filetype"], "jpeg")


if __name__ == "__main__":
    unittest.main()
