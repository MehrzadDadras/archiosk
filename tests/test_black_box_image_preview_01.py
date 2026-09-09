"""CLAUDE-BLACK-BOX-IMAGE-PREVIEW-01: let a person see what they uploaded.

Image intake closed the door; this closes the gap it left. A customer could
upload a scan, reach the As-Read bench, and never see the thing they had
brought - which for a blank or unreadable page left the surface showing almost
nothing.

AUTHORITATIVE SOURCE MAY BE VISUALLY PRESENTED WITHOUT TRANSFORMING ITS
GOVERNED STATUS. DISPLAY DOES NOT AUTHORIZE EXTERNAL PROCESSING.

Three tests carry the weight:

`test_the_content_type_comes_from_the_bytes_not_the_name` - an inline image
response is exactly where trusting an extension becomes stored XSS.

`test_another_owner_cannot_preview_your_image` - the preview inherits the
project boundary rather than acquiring rules of its own.

`test_viewing_an_image_calls_no_provider` - DISPLAY DOES NOT AUTHORIZE EXTERNAL
PROCESSING, pinned rather than intended.
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

from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _png(width=40, height=30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (250, 250, 250)).save(buffer, "PNG")
    return buffer.getvalue()


def _jpeg(width=40, height=30) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 200, 200)).save(buffer, "JPEG")
    return buffer.getvalue()


class ImagePreviewTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_preview_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

        self.png_bytes = _png()
        self.png_doc = self._black_box("scan.png", self.png_bytes, "PNG job")
        self.jpeg_doc = self._black_box("scan.jpg", _jpeg(), "JPEG job")
        self.text_doc = self._black_box("notes.txt", b"a plain note", "Text job")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _upload(self, name, data, label, **kwargs):
        with self.app.app_context():
            return ingest_upload(
                FileStorage(stream=io.BytesIO(data), filename=name),
                self.app, owner="owner", project_name=label, **kwargs)

    def _black_box(self, name, data, label):
        return self._upload(name, data, "%s %s" % (label, uuid.uuid4().hex[:6]),
                            operating_environment=None,
                            container_state=CONTAINER_STATE_BLACK_BOX)

    def _client(self, role="admin", username="owner"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = role
        return client

    def _source_id(self, document):
        return self.store.get(document.project_id).sources[0]["id"]

    def _url(self, document):
        return "/projects/%s/workspace/sources/%s/image" % (
            document.project_id, self._source_id(document))

    # -- it serves the authoritative image -----------------------------------

    def test_an_authorized_viewer_can_preview_a_png(self):
        response = self._client().get(self._url(self.png_doc))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/png")

    def test_an_authorized_viewer_can_preview_a_jpeg(self):
        response = self._client().get(self._url(self.jpeg_doc))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")

    def test_the_bytes_are_served_unmutated(self):
        """The authoritative source, not a recompressed substitute."""
        response = self._client().get(self._url(self.png_doc))
        self.assertEqual(response.get_data(), self.png_bytes)

    def test_the_content_type_comes_from_the_bytes_not_the_name(self):
        """An inline image response is where trusting an extension turns into
        stored XSS, so the header is built from what the decoder actually
        found."""
        workspace = self.store.get(self.png_doc.project_id)
        source = workspace.sources[0]
        # The governed record now claims a .jpg name over genuine PNG bytes.
        source["name"] = "actually.jpg"
        self.store.save(workspace)
        response = self._client().get(self._url(self.png_doc))
        self.assertEqual(response.status_code, 404,
                         "a record whose name and bytes disagree serves nothing")

    def test_response_headers_refuse_sniffing(self):
        """nosniff here; the CSP is the application's own.

        A per-response CSP was tried and removed: app.py's after_request sets
        the application policy and overwrites anything set at route level, so
        the header would have read as protection that was not actually there.
        """
        response = self._client().get(self._url(self.png_doc))
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertIn("img-src 'self'",
                      response.headers.get("Content-Security-Policy", ""))

    # -- access boundary ------------------------------------------------------

    def test_an_unauthenticated_visitor_is_refused(self):
        response = self.app.test_client().get(self._url(self.png_doc))
        self.assertIn(response.status_code, (302, 401, 403))

    def test_another_owner_cannot_preview_your_image(self):
        stranger = self._client(role="read_only", username="stranger")
        self.assertEqual(stranger.get(self._url(self.png_doc)).status_code, 404,
                         "a generic 404, never a distinguishable refusal")

    def test_a_source_from_another_container_is_not_reachable(self):
        """Belongs-to is authorisation, not convenience."""
        mismatched = "/projects/%s/workspace/sources/%s/image" % (
            self.png_doc.project_id, self._source_id(self.jpeg_doc))
        self.assertEqual(self._client().get(mismatched).status_code, 404)

    def test_an_unknown_source_id_is_indistinguishable_from_a_forbidden_one(self):
        unknown = "/projects/%s/workspace/sources/%s/image" % (
            self.png_doc.project_id, uuid.uuid4())
        self.assertEqual(self._client().get(unknown).status_code, 404)

    def test_the_route_reuses_the_existing_project_loader(self):
        source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        window = source[source.index("def source_image("):]
        window = window[:window.index("@workspace_bp.route", 10)]
        self.assertIn("_load_workspace_or_404", window,
                      "no second access-control framework")

    # -- what it refuses to serve --------------------------------------------

    def test_a_non_image_source_cannot_use_this_route(self):
        self.assertEqual(self._client().get(self._url(self.text_doc)).status_code, 404)

    def test_a_removed_source_is_not_served(self):
        workspace = self.store.get(self.png_doc.project_id)
        workspace.sources[0]["removed_at"] = "2026-09-08T00:00:00+00:00"
        self.store.save(workspace)
        self.assertEqual(self._client().get(self._url(self.png_doc)).status_code, 404)

    def test_a_path_outside_the_store_is_refused(self):
        """The path is governed, never user-supplied - this is the second lock."""
        workspace = self.store.get(self.png_doc.project_id)
        workspace.sources[0]["file_path"] = "/etc/passwd"
        self.store.save(workspace)
        self.assertEqual(self._client().get(self._url(self.png_doc)).status_code, 404)

    def test_a_traversal_style_path_is_refused(self):
        workspace = self.store.get(self.png_doc.project_id)
        workspace.sources[0]["file_path"] = str(
            Path(self.tmp) / ".." / ".." / "etc" / "passwd")
        self.store.save(workspace)
        self.assertEqual(self._client().get(self._url(self.png_doc)).status_code, 404)

    def test_a_missing_file_is_an_honest_404_not_a_fabricated_preview(self):
        workspace = self.store.get(self.png_doc.project_id)
        Path(workspace.sources[0]["file_path"]).unlink()
        self.assertEqual(self._client().get(self._url(self.png_doc)).status_code, 404)

    # -- the bench surface ----------------------------------------------------

    def test_the_bench_shows_the_preview_for_an_image_source(self):
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.png_doc.project_id, self._source_id(self.png_doc))
        ).get_data(as_text=True)
        self.assertIn('data-ui-ref="drawing-understanding.source-image"', body)
        self.assertIn(self._url(self.png_doc), body)
        self.assertIn("Source image", body)

    def test_the_bench_shows_no_preview_for_a_non_image_source(self):
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.text_doc.project_id, self._source_id(self.text_doc))
        ).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="drawing-understanding.source-image"', body)

    def test_the_preview_does_not_overlay_or_substitute_recovered_text(self):
        """SOURCE and DERIVED stay distinct - no OCR painted onto the pixels."""
        template = (_REPO_ROOT / "templates" / "drawing_understanding.html").read_text(
            encoding="utf-8")
        figure = template[template.index('data-ui-ref="drawing-understanding.source-image"'):]
        figure = figure[:figure.index("</figure>")]
        for forbidden in ("ocr_text", "recovered_text", "position:absolute",
                          "canvas", "annotation"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, figure)

    def test_no_exif_fields_are_exposed_on_the_bench(self):
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.jpeg_doc.project_id, self._source_id(self.jpeg_doc))
        ).get_data(as_text=True)
        for field in ("GPSInfo", "GPS ", "EXIF", "Exif", "camera make"):
            with self.subTest(field=field):
                self.assertNotIn(field, body)

    # -- egress ---------------------------------------------------------------

    def test_viewing_an_image_calls_no_provider(self):
        from services import llm_gateway

        def detonate(*_args, **_kwargs):
            raise AssertionError("image preview attempted external egress")

        with patch.object(llm_gateway, "call_llm_json", detonate), \
                patch.object(llm_gateway, "call_gemini_json", detonate), \
                patch.object(llm_gateway, "anthropic_client", detonate):
            response = self._client().get(self._url(self.png_doc))
            bench = self._client().get(
                "/projects/%s/workspace/sources/%s/understanding"
                % (self.png_doc.project_id, self._source_id(self.png_doc)))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(bench.status_code, 200)

    def test_the_preview_loads_no_external_origin(self):
        body = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.png_doc.project_id, self._source_id(self.png_doc))
        ).get_data(as_text=True)
        figure = body[body.index('data-ui-ref="drawing-understanding.source-image"'):]
        figure = figure[:figure.index("</figure>")]
        for external in ("http://", "https://", "//cdn", "data:"):
            with self.subTest(external=external):
                self.assertNotIn(external, figure)

    # -- nothing else moved ---------------------------------------------------

    def test_governed_records_are_unchanged_by_viewing(self):
        before = self.store.get(self.png_doc.project_id)
        version_before = before.version
        self._client().get(self._url(self.png_doc))
        after = self.store.get(self.png_doc.project_id)
        self.assertEqual(after.version, version_before, "display mutates nothing")
        self.assertEqual(after.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)

    def test_a_conventional_project_is_unaffected(self):
        document = self._upload("rfp.txt", b"An ordinary founding document.",
                                "Real Project", operating_environment=CLIENT_OWNER)
        workspace = self.store.get(document.project_id)
        self.assertEqual(workspace.container_state, None)
        body = self._client().get("/projects").get_data(as_text=True)
        self.assertIn(document.project_id, body)

    def test_this_tranche_created_no_general_file_serving_endpoint(self):
        """A pre-existing `/file` route already serves stored sources.

        It shares this route's access boundary but types its response from
        `mimetypes.guess_type(source["name"])` - the FILENAME - which is
        exactly what an image preview must not do, since an inline response is
        where a wrong content type becomes stored XSS. That is why this tranche
        added a narrower, byte-verified image route rather than reusing it, and
        why it did not add any further general endpoint of its own.
        """
        rules = {str(rule) for rule in self.app.url_map.iter_rules()}
        for invented in ("/projects/<project_id>/workspace/sources/<source_id>/raw",
                         "/projects/<project_id>/workspace/sources/<source_id>/download",
                         "/projects/<project_id>/workspace/files/<path:filename>"):
            self.assertNotIn(invented, rules)
        source = (_REPO_ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        window = source[source.index("def source_image("):]
        window = window[:window.index("@workspace_bp.route", 10)]
        self.assertNotIn("guess_type", window,
                         "content type must come from the bytes, never the name")
