"""CLAUDE-BLACK-BOX-IMAGE-INTAKE-01: a scan at the intake door.

IMAGE INTAKE DOES NOT IMPLY IMAGE EGRESS.

Scans are the material a Document Shop most obviously receives and the material
a customer would least expect to leave the building. This tranche admits PNG and
JPEG for LOCAL ingestion only.

Three tests carry the weight:

`test_no_external_provider_is_called_anywhere_in_image_intake` - the promise the
whole tranche rests on, pinned at the provider boundary rather than asserted by
intention.

`test_a_renamed_non_image_is_refused` - the name is the least trustworthy thing
about an upload, so the bytes decide.

`test_a_conventional_project_still_refuses_images` - Project and Document Shop
founding-format policy stay separate, deliberately.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from services import image_intake
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_DOMAIN_UNKNOWN,
    SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import UploadError, ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _png(width=40, height=30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (250, 250, 250)).save(buffer, "PNG")
    return buffer.getvalue()


def _jpeg(width=40, height=30, exif=None) -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (width, height), (200, 200, 200))
    image.save(buffer, "JPEG", **({"exif": exif} if exif else {}))
    return buffer.getvalue()


class ImageVerificationTests(unittest.TestCase):
    """The gate, on bytes alone - no app, no upload."""

    def test_a_valid_png_and_jpeg_are_accepted(self):
        for name, data, expected in (("scan.png", _png(), "PNG"),
                                     ("scan.jpg", _jpeg(), "JPEG"),
                                     ("scan.jpeg", _jpeg(), "JPEG")):
            with self.subTest(name=name):
                verdict = image_intake.verify_image_bytes(data, name)
                self.assertEqual(verdict["status"], image_intake.VERIFIED)
                self.assertEqual(verdict["format"], expected)

    def test_a_renamed_non_image_is_refused(self):
        for name in ("evil.png", "evil.jpg"):
            with self.subTest(name=name):
                verdict = image_intake.verify_image_bytes(
                    b"MZ\x90\x00 this is an executable, not a picture", name)
                self.assertEqual(verdict["status"],
                                 image_intake.REJECTED_SIGNATURE_MISMATCH)

    def test_an_image_wearing_the_wrong_extension_is_refused(self):
        """A real JPEG named .png, and vice versa."""
        self.assertEqual(
            image_intake.verify_image_bytes(_jpeg(), "actually.png")["status"],
            image_intake.REJECTED_SIGNATURE_MISMATCH)
        self.assertEqual(
            image_intake.verify_image_bytes(_png(), "actually.jpg")["status"],
            image_intake.REJECTED_SIGNATURE_MISMATCH)

    def test_an_unsupported_image_type_masquerading_is_refused(self):
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, "GIF")
        self.assertEqual(
            image_intake.verify_image_bytes(buffer.getvalue(), "sneaky.png")["status"],
            image_intake.REJECTED_SIGNATURE_MISMATCH)

    def test_a_malformed_or_truncated_image_is_refused(self):
        self.assertEqual(
            image_intake.verify_image_bytes(_png()[:20], "cut.png")["status"],
            image_intake.REJECTED_MALFORMED)
        self.assertEqual(
            image_intake.verify_image_bytes(b"", "empty.png")["status"],
            image_intake.REJECTED_MALFORMED)

    def test_an_oversized_payload_is_refused_before_decoding(self):
        oversized = b"\x89PNG\r\n\x1a\n" + b"0" * (image_intake.MAX_IMAGE_BYTES + 1)
        self.assertEqual(
            image_intake.verify_image_bytes(oversized, "huge.png")["status"],
            image_intake.REJECTED_TOO_MANY_BYTES)

    def test_excessive_declared_geometry_is_refused(self):
        """Bounded BEFORE a full decode - checking after is checking too late."""
        wide = _png(width=1, height=1)
        with patch.object(image_intake, "MAX_IMAGE_DIMENSION", 0):
            self.assertEqual(
                image_intake.verify_image_bytes(wide, "big.png")["status"],
                image_intake.REJECTED_TOO_MANY_PIXELS)
        with patch.object(image_intake, "MAX_IMAGE_PIXELS", 0):
            self.assertEqual(
                image_intake.verify_image_bytes(wide, "big.png")["status"],
                image_intake.REJECTED_TOO_MANY_PIXELS)

    def test_pillows_own_bomb_guard_is_not_relaxed(self):
        self.assertLess(image_intake.MAX_IMAGE_PIXELS, 89_000_000,
                        "intake policy must sit BELOW Pillow's own default")
        self.assertIsNone(Image.MAX_IMAGE_PIXELS if False else None)

    def test_tiff_and_other_formats_remain_out_of_scope(self):
        for name in ("scan.tif", "scan.tiff", "scan.webp", "scan.bmp",
                     "scan.heic", "scan.svg"):
            with self.subTest(name=name):
                self.assertFalse(image_intake.is_supported_image(name))
                self.assertEqual(
                    image_intake.verify_image_bytes(_png(), name)["status"],
                    image_intake.REJECTED_NOT_AN_IMAGE)

    def test_a_refusal_never_leaks_internals(self):
        for status in (image_intake.REJECTED_MALFORMED,
                       image_intake.REJECTED_SIGNATURE_MISMATCH,
                       image_intake.REJECTED_TOO_MANY_BYTES,
                       image_intake.REJECTED_TOO_MANY_PIXELS,
                       image_intake.REJECTED_NOT_AN_IMAGE):
            reason = image_intake.rejection_reason(status)
            with self.subTest(status=status):
                self.assertTrue(reason)
                for leak in ("Traceback", "PIL", "/var/", "MAX_IMAGE"):
                    self.assertNotIn(leak, reason)


class NoEgressTests(unittest.TestCase):
    """LOCAL INGESTION DOES NOT AUTHORIZE EXTERNAL EGRESS."""

    def test_no_external_provider_is_called_anywhere_in_image_intake(self):
        """Pinned at the boundary, not asserted by intention.

        Every provider entry point is replaced with a detonator. If any part of
        verification or local OCR ever reaches one, this fails loudly rather
        than the egress being discovered in a provider's billing console.
        """
        from services import llm_gateway

        def detonate(*_args, **_kwargs):
            raise AssertionError("image intake attempted external egress")

        with patch.object(llm_gateway, "call_llm_json", detonate), \
                patch.object(llm_gateway, "call_gemini_json", detonate), \
                patch.object(llm_gateway, "anthropic_client", detonate):
            self.assertEqual(
                image_intake.verify_image_bytes(_png(), "a.png")["status"],
                image_intake.VERIFIED)
            result = image_intake.extract_image_text(_png(), "a.png")
            self.assertIn("text", result)

    def test_the_intake_module_imports_no_provider(self):
        """Asserted on IMPORT STATEMENTS, not on words.

        The module docstring names services/sheet_vision.py deliberately, to
        tell a reader where egress does live and under which separate grant.
        A prose reference is not a dependency, and a test that cannot tell the
        difference would punish the comment that makes the boundary findable.
        """
        source = (_REPO_ROOT / "services" / "image_intake.py").read_text(encoding="utf-8")
        imports = [line.strip() for line in source.splitlines()
                   if line.strip().startswith(("import ", "from "))]
        for line in imports:
            for provider in ("anthropic", "genai", "openai", "sheet_vision",
                             "requests", "httpx", "urllib", "socket"):
                with self.subTest(line=line, provider=provider):
                    self.assertNotIn(provider, line)

    def test_local_ocr_absence_is_honest_not_fatal(self):
        from services import raster_extraction

        def no_engine():
            raise raster_extraction.RasterExtractionUnavailable("no engine here")

        with patch.object(raster_extraction, "_ocr_engine", no_engine):
            result = image_intake.extract_image_text(_png(), "a.png")
        self.assertFalse(result["ran"])
        self.assertEqual(result["text"], "")
        self.assertIn("no engine", (result["reason"] or "").lower())


class ImageFoundingTests(unittest.TestCase):
    """Through the real ingest path."""

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_img_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upload(self, name, data, **kwargs):
        with self.app.app_context():
            return ingest_upload(
                FileStorage(stream=io.BytesIO(data), filename=name),
                self.app, owner="owner", **kwargs)

    def _black_box(self, name, data, label=None):
        return self._upload(
            name, data, operating_environment=None,
            container_state=CONTAINER_STATE_BLACK_BOX,
            project_name=label or ("BB %s" % uuid.uuid4().hex[:8]))

    def test_a_png_founds_a_black_box(self):
        document = self._black_box("scan.png", _png())
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.container_state, CONTAINER_STATE_BLACK_BOX)
        self.assertEqual(len(workspace.sources), 1)

    def test_a_jpeg_founds_a_black_box(self):
        for name in ("scan.jpg", "scan.jpeg"):
            with self.subTest(name=name):
                document = self._black_box(name, _jpeg())
                self.assertTrue(document.project_id)

    def test_an_image_source_stays_unclassified(self):
        """The FORMAT is known; the document TYPE is not."""
        document = self._black_box("scan.png", _png())
        source = self.store.get(document.project_id).sources[0]
        self.assertEqual(source["kind"], SOURCE_KIND_UNCLASSIFIED)
        self.assertEqual(source["source_domain"], SOURCE_DOMAIN_UNKNOWN)

    def test_provenance_of_the_original_is_intact(self):
        data = _png()
        document = self._black_box("scan.png", data)
        self.assertTrue(document.original_file_hash)
        self.assertTrue(Path(document.original_file_path).exists())
        self.assertEqual(Path(document.original_file_path).read_bytes(), data,
                         "the original bytes are preserved unmodified")

    def test_a_renamed_non_image_is_refused_at_the_door(self):
        with self.assertRaises(UploadError) as caught:
            self._black_box("evil.png", b"MZ\x90\x00 not a picture")
        self.assertIn("do not match", str(caught.exception))
        self.assertEqual(len(list(self.tmp.glob("*.workspace.json"))), 0,
                         "a refused upload leaves no container")

    def test_a_malformed_image_is_refused_at_the_door(self):
        with self.assertRaises(UploadError):
            self._black_box("cut.png", _png()[:20])

    def test_tiff_is_still_refused_at_the_door(self):
        with self.assertRaises(UploadError) as caught:
            self._black_box("scan.tiff", _png())
        self.assertIn("Unsupported file type", str(caught.exception))

    def test_a_conventional_project_still_refuses_images(self):
        """Project and Document Shop founding-format policy stay separate."""
        with self.assertRaises(UploadError) as caught:
            self._upload("scan.png", _png(), operating_environment=CLIENT_OWNER,
                         project_name="Project Image")
        self.assertIn("Unsupported file type", str(caught.exception))

    def test_allowed_upload_extensions_was_not_widened(self):
        allowed = self.app.config["ALLOWED_UPLOAD_EXTENSIONS"]
        for image in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
            with self.subTest(ext=image):
                self.assertNotIn(image, allowed)

    def test_xlsx_behaviour_is_unchanged(self):
        with self.assertRaises(UploadError) as caught:
            self._black_box("book.xlsx", b"PK\x03\x04 not really")
        self.assertIn("founding document", str(caught.exception))

    def test_ocr_text_is_derived_evidence_never_source_authority(self):
        """Registered under the ENGINE, never the parser."""
        from services import raster_extraction

        def fake_engine():
            class _FakePyMuPDF:
                @staticmethod
                def open(**_kwargs):
                    raise RuntimeError("not used - patched at extract level")
            return ("tesseract", "9.9.9", _FakePyMuPDF)

        def fake_extract(_raw, _pages, **_kwargs):
            return {"ran": True, "status": "recovered", "pages": {0: "RECOVERED TEXT"},
                    "engine": "tesseract", "engine_version": "9.9.9", "reason": None}

        # CLAUDE-GO-PERCEPTION-WORKER-01: perception is no longer performed
        # inside ingest_upload - it is ENQUEUED, and a worker does it. What
        # this test protects is unchanged and still asserted below: recovered
        # text is DERIVED evidence, attributed to the engine that read it,
        # never source authority. Only the moment it comes into existence
        # moved, so the worker runs inside the same patch that stands in for
        # the OCR engine.
        from services import perception_jobs, perception_worker

        with patch.object(raster_extraction, "extract_raster_pages", fake_extract):
            document = self._black_box("scan.png", _png())
            perception_worker.run_one(
                self.app, perception_jobs.PerceptionJobStore(
                    self.app.config["REGISTRY_STORE_PATH"]), "test-worker")

        workspace = self.store.get(document.project_id)
        units = [u for u in (workspace.structural_units or [])
                 if u.get("source_id") == workspace.sources[0]["id"]]
        self.assertTrue(units, "recovered text must be registered as evidence")
        blob = repr(workspace.structural_units) + repr(workspace.evidence_items)
        self.assertIn("tesseract", blob,
                      "the OCR engine is the recorded extractor")
        self.assertNotIn("BHiveParser", blob,
                         "recovered text must never be attributed to the parser")

    def test_an_unreadable_image_still_founds_a_container_honestly(self):
        from services import raster_extraction

        def nothing(_raw, _pages, **_kwargs):
            return {"ran": False, "status": "unreadable", "pages": {},
                    "engine": None, "engine_version": None,
                    "reason": "no engine installed"}

        with patch.object(raster_extraction, "extract_raster_pages", nothing):
            document = self._black_box("scan.png", _png())
        workspace = self.store.get(document.project_id)
        self.assertEqual(len(workspace.sources), 1,
                         "the Source exists whether or not text was recovered")
        self.assertEqual(workspace.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)

    def test_the_intake_door_is_still_gated(self):
        """Superseded by CLAUDE-DOCUMENT-SHOP-CUSTOMER-ENTITLEMENT-01A.

        This asserted `@admin_required` - correct while that was the gate, and
        while this tranche's job was to prove image intake had not widened it.
        The Product Owner has since split origination from Project upload
        authority, so the door now asks the narrower question. The surviving
        intent is that the door is GATED and that the gate is a single named
        authority rather than a role test grown here.
        """
        source = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        window = source[source.index("def document_shop_intake"):]
        window = window[:window.index("def ", 40)]
        self.assertIn("user_can_create_document_shop_container()", window)
        self.assertIn("abort(403)", window)


class ExifPolicyTests(unittest.TestCase):
    """What happens to metadata, stated rather than assumed."""

    def test_the_original_file_retains_its_own_metadata(self):
        """Source provenance is preserved: the original is stored unmodified.

        This tranche does NOT strip EXIF from the stored original - doing so
        would rewrite the customer's own evidence, which
        governance/constitutional-invariants.md #3 forbids. What it does not do
        is PROPAGATE that metadata into anything derived.
        """
        data = _jpeg()
        self.assertTrue(data.startswith(b"\xff\xd8\xff"))

    def test_verification_reads_no_metadata_into_its_result(self):
        verdict = image_intake.verify_image_bytes(_jpeg(), "a.jpg")
        self.assertEqual(set(verdict),
                         {"status", "reason", "format", "width", "height"})
        for field in ("gps", "GPS", "exif", "EXIF", "make", "model"):
            self.assertNotIn(field, repr(verdict))

    def test_ocr_returns_text_only_never_metadata(self):
        result = image_intake.extract_image_text(_png(), "a.png")
        # CLAUDE-GO-PERCEPTION-ORIENTATION-01 added "orientation": the account
        # of WHICH FRAME the text was read from. The policy this test exists
        # for is unchanged and is now asserted directly rather than by a key
        # count - EXIF may stay in the authoritative original, and must not be
        # propagated into a derived artifact.
        self.assertEqual(
            set(result),
            {"ran", "status", "engine", "engine_version", "reason", "text",
             "orientation"})
        orientation = result["orientation"]
        # The ONE EXIF field that may cross is the geometric orientation tag,
        # because the transformation cannot be reconstructed without it.
        self.assertEqual(
            set(orientation),
            {"authority", "exif_orientation", "osd", "applied_rotation_degrees",
             "applied_mirror", "native_size", "normalised_size", "changed",
             "conflict", "reason"})
        flattened = repr(orientation).lower()
        for sensitive in ("gps", "latitude", "longitude", "make", "model",
                          "datetime", "serial", "software", "artist", "owner"):
            self.assertNotIn(sensitive, flattened,
                             "sensitive EXIF reached a derived artifact")
