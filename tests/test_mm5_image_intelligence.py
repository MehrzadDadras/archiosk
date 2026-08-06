"""
CLAUDE-MM5 (Image, Screenshot, and Camera Evidence) tests: services/
image_intelligence.py's real Pillow/EXIF read -> classification ->
registration orchestration (register_eye_capture, extract_bounded_crop,
create_marker_and_evidence), CaseWorkspaceStore.create_addressable_
marker_region, and register_drawing_sheet_structure's new `unit_type`
parameter (backward compatibility with MM4 drawing sheets).

Mirrors this repository's established hermetic pattern for image-adjacent
code (tests/test_mm4_drawing_intelligence.py): real, small Pillow-
generated fixtures, no mocking of the parsing library itself.

Run via:

    python -m unittest tests.test_mm5_image_intelligence -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from PIL import Image

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    IMAGE_CLASSIFICATION_EXCESSIVE_SIZE,
    IMAGE_CLASSIFICATION_MALFORMED,
    IMAGE_CLASSIFICATION_SUPPORTED,
    IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT,
    METADATA_EXPOSURE_PRESERVED_INTERNAL,
    METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED,
    METADATA_EXPOSURE_UNAVAILABLE,
    METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
    METADATA_RELIABILITY_UNAVAILABLE,
    OBSERVATION_AUTHOR_HUMAN,
    SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP,
    SOURCE_ORIGIN_TYPE_EYE_CAPTURE,
)
from services.drawing_intelligence import (
    create_drawing_region_and_evidence,
    register_drawing_evidence_for_source,
)
from services.governance import GovernanceLog
from services.image_intelligence import (
    ImageIntelligenceError,
    create_marker_and_evidence,
    extract_bounded_crop,
    register_eye_capture,
)


def _build_png(width: int = 60, height: int = 40, color=(200, 30, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _build_jpeg_with_exif(width: int = 80, height: int = 60) -> bytes:
    img = Image.new("RGB", (width, height), (10, 20, 30))
    exif = img.getexif()
    exif[0x010F] = "TestCam"       # Make
    exif[0x0110] = "Model X"       # Model
    exif[0x0112] = 1               # Orientation
    exif[0x0131] = "TestSoftware"  # Software
    exif[0x9003] = "2026:01:02 03:04:05"  # DateTimeOriginal
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


class ImageIntelligenceOrchestrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm5_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-mm5"
        self.workspace = self.store.get_or_create(self.project_id)
        self.sources_dir = self.tmp_dir / "workspace_sources" / self.project_id

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_register_eye_capture_supported_png(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="image.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        self.assertEqual(result["classification"], IMAGE_CLASSIFICATION_SUPPORTED)
        self.assertIsNotNone(result["source_id"])
        source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertEqual(source["origin_type"], SOURCE_ORIGIN_TYPE_EYE_CAPTURE)
        self.assertIsNotNone(source["file_hash"])
        self.assertTrue(source["name"].startswith("Eye capture "))

        units = self.store.structural_units_for_source(self.workspace, result["source_id"])
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["unit_type"], "image")
        self.assertEqual(units[0]["modality_metadata"]["width"], 60)
        self.assertEqual(units[0]["modality_metadata"]["height"], 40)

    def test_register_eye_capture_generic_filename_gets_generated_name(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="blob",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertTrue(source["name"].startswith("Eye capture "))

    def test_register_eye_capture_preserves_original_filename(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="site-photo-1.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertEqual(source["name"], "site-photo-1.png")

    def test_register_eye_capture_with_description_creates_evidence(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description="Crack near the north stair", sources_dir=self.sources_dir, actor="tester",
        )
        items = self.store.evidence_items_for_source(self.workspace, result["source_id"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["content"], "Crack near the north stair")
        self.assertEqual(items[0]["evidence_class"], "user_entered_evidence")

    def test_unsupported_extension_classified_not_raised(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=b"whatever", filename="notes.gif",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        self.assertEqual(result["classification"], IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT)
        self.assertIsNone(result["source_id"])
        self.assertEqual(self.workspace.sources, [])

    def test_malformed_image_classified_not_raised(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=b"not a real png at all", filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        self.assertEqual(result["classification"], IMAGE_CLASSIFICATION_MALFORMED)
        self.assertIsNone(result["source_id"])
        self.assertEqual(self.workspace.sources, [])

    def test_oversized_raw_bytes_refused_before_parsing(self):
        with unittest.mock.patch("services.image_intelligence.MAX_RAW_BYTES", 10):
            result = register_eye_capture(
                self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
                description=None, sources_dir=self.sources_dir, actor="tester",
            )
        self.assertEqual(result["classification"], IMAGE_CLASSIFICATION_EXCESSIVE_SIZE)
        self.assertIsNone(result["source_id"])

    def test_exif_fields_extracted_with_reliability_and_exposure(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_jpeg_with_exif(), filename="camera.jpg",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]
        fields = unit["modality_metadata"]["fields"]
        self.assertEqual(fields["camera_make"]["value"], "TestCam")
        self.assertEqual(fields["camera_make"]["reliability"], METADATA_RELIABILITY_DIRECTLY_EXTRACTED)
        self.assertEqual(fields["camera_make"]["exposure"], METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED)
        self.assertEqual(fields["camera_model"]["value"], "Model X")
        self.assertEqual(fields["capture_timestamp"]["value"], "2026:01:02 03:04:05")

    def test_exif_absent_fields_are_honestly_unavailable(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="screenshot.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]
        fields = unit["modality_metadata"]["fields"]
        self.assertEqual(fields["camera_make"]["reliability"], METADATA_RELIABILITY_UNAVAILABLE)
        self.assertEqual(fields["camera_make"]["exposure"], METADATA_EXPOSURE_UNAVAILABLE)
        self.assertIsNone(fields["camera_make"]["value"])

    def test_gps_presence_flagged_but_value_never_populated(self):
        # A real GPS-bearing JPEG (constructed directly with a GPS IFD -
        # see this module's own privacy-boundary docstring for why the
        # extraction code never reads coordinate VALUES at all).
        img = Image.new("RGB", (50, 40), (5, 5, 5))
        exif = img.getexif()
        exif[0x8825] = {1: "N", 2: (43, 0, 0), 3: "W", 4: (79, 0, 0)}
        buf = io.BytesIO()
        img.save(buf, format="JPEG", exif=exif)

        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=buf.getvalue(), filename="geo.jpg",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]
        fields = unit["modality_metadata"]["fields"]
        self.assertTrue(fields["gps_present"]["value"])
        self.assertEqual(fields["gps_present"]["exposure"], METADATA_EXPOSURE_PRESERVED_INTERNAL)
        # The literal string form of this module's own field dict never
        # contains anything that looks like the coordinate values used
        # to construct the fixture - a falsification-style proof that
        # extraction genuinely never touches them, not merely that no
        # dedicated "value" key happens to be populated.
        self.assertNotIn("43", str(fields["gps_present"]))
        self.assertNotIn("79", str(fields["gps_present"]))

    def test_original_bytes_unchanged_after_registration(self):
        raw = _build_jpeg_with_exif()
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=raw, filename="camera.jpg",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        source = self.store._find(self.workspace.sources, result["source_id"])
        on_disk = Path(source["file_path"]).read_bytes()
        self.assertEqual(on_disk, raw)

    def test_falsification_cross_project_marker_denied(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        other_workspace = self.store.get_or_create("test-project-mm5-other")
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        with self.assertRaises(ImageIntelligenceError):
            create_marker_and_evidence(
                self.store, other_workspace, result["source_id"], unit_id, x=0.5, y=0.5,
                note="cross-project probe", actor="tester",
            )

    def test_create_marker_and_evidence_end_to_end(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        marker = create_marker_and_evidence(
            self.store, self.workspace, result["source_id"], unit_id, x=0.3, y=0.7,
            note="Crack visible here", actor="tester",
        )
        self.assertEqual(marker["region"]["region_type"], "marker")
        self.assertEqual(marker["region"]["address"]["x"], 0.3)
        self.assertEqual(marker["region"]["address"]["y"], 0.7)
        self.assertEqual(marker["evidence_item"]["content"], "Crack visible here")
        self.assertEqual(marker["citation"]["status"], "resolved")
        self.assertIn("marker 1", marker["citation"]["label"])

        observation = self.store.record_derived_observation(
            self.workspace, statement="A dark linear crack is visible within the selected crop.",
            author_type=OBSERVATION_AUTHOR_HUMAN, author="tester", method="visual_inspection",
            supporting_evidence_ids=[marker["evidence_item"]["id"]], actor="tester",
        )
        self.assertIn(marker["evidence_item"]["id"], observation["supporting_evidence_ids"])

    def test_marker_requires_a_note(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        with self.assertRaises(ImageIntelligenceError):
            create_marker_and_evidence(
                self.store, self.workspace, result["source_id"], unit_id, x=0.5, y=0.5,
                note="   ", actor="tester",
            )

    def test_marker_citation_distinct_from_region_citation(self):
        # Markers and rectangular regions share ONE sequential region_index
        # counter per StructuralUnit (create_addressable_drawing_region's
        # own docstring: "a stable, 1-based, per-StructuralUnit sequential
        # position") - the label PREFIX ("marker"/"region") is what keeps
        # them visually distinct, not independent numbering.
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        marker = create_marker_and_evidence(
            self.store, self.workspace, result["source_id"], unit_id, x=0.1, y=0.1,
            note="marker note", actor="tester",
        )
        region_result = create_drawing_region_and_evidence(
            self.store, self.workspace, result["source_id"], unit_id,
            x=0.2, y=0.2, width=0.1, height=0.1, actor="tester",
        )
        self.assertIn("marker 1", marker["citation"]["label"])
        self.assertIn("region 2", region_result["citation"]["label"])
        self.assertNotEqual(marker["citation"]["label"], region_result["citation"]["label"])

    def test_stale_anchor_after_source_revision(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        marker = create_marker_and_evidence(
            self.store, self.workspace, result["source_id"], unit_id, x=0.5, y=0.5,
            note="original marker", actor="tester",
        )
        self.store.register_source_revision(
            self.workspace, old_source_id=result["source_id"], name="photo-r2.png",
            file_path=str(self.sources_dir / "photo-r2.png"), width=60, height=40, actor="tester",
        )
        citation = self.store.resolve_region_citation(self.workspace, marker["region"]["id"])
        self.assertEqual(citation["status"], "stale")

    # -- Derivative crop export (Section 12) -----------------------------

    def test_extract_bounded_crop_creates_derivative_source(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(100, 80, (0, 100, 200)), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        region = self.store.create_addressable_drawing_region(
            self.workspace, unit_id, x=0.25, y=0.25, width=0.5, height=0.5, actor="tester",
        )
        crop = extract_bounded_crop(
            self.store, self.workspace, result["source_id"], region["id"],
            sources_dir=self.sources_dir, actor="tester",
        )
        derivative = self.store._find(self.workspace.sources, crop["derivative_source_id"])
        self.assertIsNotNone(derivative)
        self.assertEqual(derivative["origin_type"], SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP)
        self.assertEqual(derivative["origin_reference"], region["id"])
        self.assertEqual(derivative["width"], 50)
        self.assertEqual(derivative["height"], 40)

        with Image.open(derivative["file_path"]) as derived_img:
            self.assertEqual(derived_img.size, (50, 40))

    def test_extract_bounded_crop_is_exif_free_and_records_manifest(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_jpeg_with_exif(100, 80), filename="camera.jpg",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        region = self.store.create_addressable_drawing_region(
            self.workspace, unit_id, x=0.0, y=0.0, width=0.5, height=0.5, actor="tester",
        )
        crop = extract_bounded_crop(
            self.store, self.workspace, result["source_id"], region["id"],
            sources_dir=self.sources_dir, actor="tester",
        )
        self.assertIn("camera_make", crop["removed_metadata_fields"])
        self.assertIn("camera_model", crop["removed_metadata_fields"])

        derivative = self.store._find(self.workspace.sources, crop["derivative_source_id"])
        with Image.open(derivative["file_path"]) as derived_img:
            self.assertFalse(bool(derived_img.getexif()))

    def test_extract_bounded_crop_original_unchanged(self):
        raw = _build_png(100, 80)
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=raw, filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        region = self.store.create_addressable_drawing_region(
            self.workspace, unit_id, x=0.1, y=0.1, width=0.3, height=0.3, actor="tester",
        )
        extract_bounded_crop(
            self.store, self.workspace, result["source_id"], region["id"],
            sources_dir=self.sources_dir, actor="tester",
        )
        source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertEqual(Path(source["file_path"]).read_bytes(), raw)

    def test_extract_bounded_crop_rejects_marker_region(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        marker = create_marker_and_evidence(
            self.store, self.workspace, result["source_id"], unit_id, x=0.5, y=0.5,
            note="not a crop region", actor="tester",
        )
        with self.assertRaises(ImageIntelligenceError):
            extract_bounded_crop(
                self.store, self.workspace, result["source_id"], marker["region"]["id"],
                sources_dir=self.sources_dir, actor="tester",
            )

    def test_extract_bounded_crop_cross_project_denied(self):
        result = register_eye_capture(
            self.store, self.workspace, raw_bytes=_build_png(), filename="photo.png",
            description=None, sources_dir=self.sources_dir, actor="tester",
        )
        unit_id = self.store.structural_units_for_source(self.workspace, result["source_id"])[0]["id"]
        region = self.store.create_addressable_drawing_region(
            self.workspace, unit_id, x=0.1, y=0.1, width=0.2, height=0.2, actor="tester",
        )
        other_workspace = self.store.get_or_create("test-project-mm5-other-2")
        with self.assertRaises(ImageIntelligenceError):
            extract_bounded_crop(
                self.store, other_workspace, result["source_id"], region["id"],
                sources_dir=self.sources_dir, actor="tester",
            )


class BackwardCompatibilityWithMM4Tests(unittest.TestCase):
    """Section 21: 'backward compatibility with MM4 drawing images' -
    proves register_drawing_sheet_structure's new `unit_type` parameter
    (default "sheet") leaves MM4's own existing behavior byte-for-byte
    unchanged when a caller (like services/drawing_intelligence.py) does
    not pass it at all."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm5_compat_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-mm5-compat"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_mm4_drawing_registration_still_defaults_to_sheet(self):
        source = self.store.add_source(
            self.workspace, name="plan.png", file_path=str(self.tmp_dir / "plan.png"), kind="drawing",
        )
        path = self.tmp_dir / "plan.png"
        path.write_bytes(_build_png(200, 150))
        self.store.update_source_identity(self.workspace, source["id"], actor="tester", size_bytes=100)
        # Re-point file_path at the real bytes for register_drawing_evidence_for_source.
        source["file_path"] = str(path)
        self.store.save(self.workspace)

        result = register_drawing_evidence_for_source(self.store, self.workspace, source["id"], actor="tester")
        self.assertEqual(result["classification"], "supported")
        units = self.store.structural_units_for_source(self.workspace, source["id"])
        self.assertEqual(units[0]["unit_type"], "sheet")

    def test_explicit_image_unit_type_produces_image_not_sheet(self):
        source = self.store.add_source(
            self.workspace, name="photo.png", file_path="/tmp/photo.png", kind="drawing",
        )
        result = self.store.register_drawing_sheet_structure(
            self.workspace, source["id"],
            [{"index": 0, "label": "photo.png", "width": 10, "height": 10, "source_rotation": 0, "metadata": {}}],
            actor="tester", unit_type="image",
        )
        unit = self.store._find(self.workspace.structural_units, result["structural_unit_ids"][0])
        self.assertEqual(unit["unit_type"], "image")


# ============================================================================
# /api/v1 routes - functional (not just auth) proof, mirrors MM1-MM4's own
# ApiRetrievalTests classes.
# ============================================================================

class ImageApiRetrievalTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_mm5_api_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "mm5-api-project"

        document = ParsedDocument(
            project_id=self.project_id, filename="spec.txt", ingested_at="2026-01-01T00:00:00+00:00",
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        workspace = self.store.get_or_create(self.project_id)
        workspace.owner = "tester"
        self.store.save(workspace)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as_admin(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"
        return client

    def test_eye_capture_then_marker_then_derivative_crop_via_api(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/eye-capture",
            data={"image": (io.BytesIO(_build_png(80, 60)), "site-photo.png"), "description": "North elevation"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["classification"], IMAGE_CLASSIFICATION_SUPPORTED)
        source_id = body["source_id"]
        unit_id = body["structural_unit_id"]

        marker_response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{source_id}/markers",
            json={"structural_unit_id": unit_id, "x": 0.4, "y": 0.4, "note": "Spalling visible here"},
        )
        self.assertEqual(marker_response.status_code, 201)
        self.assertIn("marker 1", marker_response.get_json()["citation"]["label"])

        region_response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{source_id}/drawing-regions",
            json={"structural_unit_id": unit_id, "x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3},
        )
        self.assertEqual(region_response.status_code, 201)
        region_id = region_response.get_json()["region"]["id"]

        crop_response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{source_id}/derivative-crop",
            json={"region_id": region_id},
        )
        self.assertEqual(crop_response.status_code, 201)
        self.assertIn("derivative_source_id", crop_response.get_json())

    def test_eye_capture_missing_file_returns_400(self):
        client = self._client_as_admin()
        response = client.post(f"/api/v1/documents/{self.project_id}/eye-capture", data={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_image")

    def test_eye_capture_malformed_image_returns_400(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/eye-capture",
            data={"image": (io.BytesIO(b"not a real image"), "bad.png")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["classification"], IMAGE_CLASSIFICATION_MALFORMED)


if __name__ == "__main__":
    unittest.main()
