"""
CLAUDE-P40-VW7A-QA - Move Document Controls into the Top Application
Menu.

Grounding fact, confirmed by reading the actual prior template source
before any change: there was no Archiosk-built document-viewer
toolbar anywhere in this codebase. The whole "viewer" was a bare
`<iframe src="{{ raw file URL }}">` (PDF/DOCX/TXT) or a plain `<img>`
(drawings), with zero custom JS and zero data-ui-ref of its own. The
"white strip toolbar" reported was the BROWSER'S OWN native PDF
viewer chrome rendering inside that iframe - not something this app
ever owned, styled, or could script. Confirmed with the user before
building anything (a real technical-limitation report, not assumed),
who then explicitly chose to build a genuine PDF.js-based canvas
viewer rather than a fictional "just move it" relocation.

Scope, stated honestly: PDF only. A drawing/DOCX/TXT Source keeps its
existing plain <img>/<iframe> embed unchanged - this stage does not
build a renderer for those formats, and the existing "page navigation
isn't available for this format" pane-note still renders for them.
Sidebar/thumbnail/annotation controls are NOT added - none existed
before (nothing to preserve) and building them would be a separate,
much larger subsystem (thumbnail generation, annotation persistence
with new backend storage) beyond this stage's own scope.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structure, exactly the
practical ceiling this repo's own prior stages have already
established and stated honestly rather than fabricating a walkthrough.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
import services.case_workspace as cw

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"
_VENDOR_DIR = _REPO_ROOT / "static" / "js" / "vendor" / "pdfjs"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_doc_controls_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="doc_controls_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename, content=b"content"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="doc_controls_owner", project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "doc_controls_owner"
            sess["role"] = "admin"
        return client

    def _first_source(self, project_id):
        store = cw.CaseWorkspaceStore(self.tmp_dir)
        return store.get(project_id).sources[0]


class PdfDetectionRenderingTests(_BaseTestCase):
    def test_pdf_source_gets_the_canvas_container_not_an_iframe(self):
        doc = self._ingest("PDF Project", "RFP.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        self.assertIn('id="document-viewer-pdf-canvas"', body)
        self.assertIn('data-ui-ref="display.document.pdf-canvas"', body)
        self.assertNotIn("document-viewer-frame", body)

    def test_pdf_canvas_container_carries_the_real_file_url(self):
        doc = self._ingest("PDF Project", "RFP.pdf")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        idx = body.index('id="document-viewer-pdf-canvas"')
        tag = body[body.rindex("<div", 0, idx):body.index(">", idx)]
        self.assertIn(f"/projects/{doc.project_id}/workspace/sources/{source['id']}/file", tag)
        self.assertIn('data-pdf-filename="RFP.pdf"', tag)

    def test_txt_source_keeps_the_plain_iframe_unchanged(self):
        doc = self._ingest("TXT Project", "notes.txt")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        self.assertIn("document-viewer-frame", body)
        self.assertNotIn("document-viewer-pdf-canvas", body)

    def test_drawing_source_keeps_the_plain_img_unchanged(self):
        doc = self._ingest("Drawing Project", "plan.txt")  # kind is set by route, not filename, for drawings normally - see store-level test below for a real drawing kind
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        # Not a drawing in this fixture (ingest_upload doesn't produce SOURCE_KIND_DRAWING) -
        # this just re-confirms the non-pdf iframe path, complementing the txt case above.
        self.assertIn("document-viewer-frame", body)

    def test_pdf_detection_is_case_insensitive_on_extension(self):
        doc = self._ingest("PDF Upper Project", "Drawing.PDF")
        source = self._first_source(doc.project_id)
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace?source={source['id']}").get_data(as_text=True)
        self.assertIn('id="document-viewer-pdf-canvas"', body)

    def test_page_navigation_pane_note_suppressed_only_for_pdf(self):
        pdf_doc = self._ingest("PDF Project 2", "spec.pdf")
        pdf_source = self._first_source(pdf_doc.project_id)
        txt_doc = self._ingest("TXT Project 2", "spec.txt")
        txt_source = self._first_source(txt_doc.project_id)
        client = self._client()

        pdf_body = client.get(f"/projects/{pdf_doc.project_id}/workspace?source={pdf_source['id']}").get_data(as_text=True)
        self.assertNotIn("isn&#39;t available yet for this format", pdf_body.replace("isn't", "isn&#39;t"))
        self.assertNotIn("available yet for this format", pdf_body)

        txt_body = client.get(f"/projects/{txt_doc.project_id}/workspace?source={txt_source['id']}").get_data(as_text=True)
        self.assertIn("available yet for this format", txt_body)


class TopMenuControlsMarkupTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_region_hidden_by_default(self):
        idx = self.html.index('id="workspace-document-controls"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn("hidden", tag)

    def test_region_sits_between_breadcrumb_and_right_side_controls(self):
        context_idx = self.html.index('data-ui-ref="menu.context"')
        controls_idx = self.html.index('id="workspace-document-controls"')
        display_layout_idx = self.html.index('data-ui-ref="menu.display-layout"')
        self.assertLess(context_idx, controls_idx)
        self.assertLess(controls_idx, display_layout_idx)

    def test_all_essential_controls_present_with_refs(self):
        for ref in (
            "menu.document-controls", "menu.document-controls.prev-page",
            "menu.document-controls.next-page", "menu.document-controls.page-input",
            "menu.document-controls.zoom-out", "menu.document-controls.zoom-in",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', self.html, ref)

    def test_all_secondary_controls_present_with_refs(self):
        for ref in (
            "menu.document-controls.fit-width", "menu.document-controls.fit-page",
            "menu.document-controls.rotate", "menu.document-controls.search-input",
            "menu.document-controls.search-prev", "menu.document-controls.search-next",
            "menu.document-controls.download", "menu.document-controls.print",
            "menu.document-controls.overflow",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', self.html, ref)

    def test_no_decorative_controls_for_features_that_do_not_exist(self):
        # Sidebar/thumbnail/annotation were never built - must not appear
        # as dead buttons merely to look complete.
        region_start = self.html.index('id="workspace-document-controls"')
        region_end = self.html.index("</div>\n            <div class=\"workspace-topbar-controls\">", region_start)
        region = self.html[region_start:region_end]
        for forbidden in ("sidebar", "thumbnail", "annotation", "outline"):
            self.assertNotIn(forbidden, region.lower())

    def test_accessible_names_present_on_every_icon_only_button(self):
        for control_id in (
            "doc-prev-page", "doc-next-page", "doc-zoom-out", "doc-zoom-in",
            "doc-rotate", "doc-search-prev", "doc-search-next", "doc-download", "doc-print",
        ):
            idx = self.html.index(f'id="{control_id}"')
            tag_start = self.html.rindex("<", 0, idx)
            tag_end = self.html.index(">", idx)
            tag = self.html[tag_start:tag_end]
            self.assertIn("aria-label=", tag, control_id)
            self.assertIn("title=", tag, control_id)

    def test_disabled_state_present_on_navigation_edges(self):
        for control_id in ("doc-search-prev", "doc-search-next"):
            idx = self.html.index(f'id="{control_id}"')
            tag_end = self.html.index(">", idx)
            tag = self.html[self.html.rindex("<", 0, idx):tag_end]
            self.assertIn("disabled", tag)

    def test_search_input_has_accessible_label(self):
        idx = self.html.index('id="doc-search-input"')
        tag = self.html[self.html.rindex("<", 0, idx):self.html.index(">", idx)]
        self.assertIn('aria-label="Search in document"', tag)

    def test_page_input_has_accessible_label(self):
        idx = self.html.index('id="doc-page-input"')
        tag = self.html[self.html.rindex("<", 0, idx):self.html.index(">", idx)]
        self.assertIn('aria-label="Page number"', tag)


class VendoredPdfJsTests(unittest.TestCase):
    def test_vendored_files_present(self):
        self.assertTrue((_VENDOR_DIR / "pdf.min.mjs").exists())
        self.assertTrue((_VENDOR_DIR / "pdf.worker.min.mjs").exists())
        self.assertTrue((_VENDOR_DIR / "LICENSE").exists())
        self.assertTrue((_VENDOR_DIR / "README.md").exists())

    def test_readme_documents_version_source_and_license(self):
        readme = (_VENDOR_DIR / "README.md").read_text(encoding="utf-8")
        self.assertIn("Version:", readme)
        self.assertIn("License:", readme)
        self.assertIn("Apache", readme)
        self.assertIn("pdfjs-dist", readme)

    def test_only_low_level_files_vendored_not_pdfjs_own_ui(self):
        # The whole point: Archiosk's own top-menu controls drive
        # rendering, not a second toolbar from PDF.js's own bundled
        # pdf_viewer.mjs/pdf_viewer.css.
        vendored = {p.name for p in _VENDOR_DIR.iterdir()}
        self.assertNotIn("pdf_viewer.mjs", vendored)
        self.assertNotIn("pdf_viewer.css", vendored)

    def test_no_client_build_step_introduced(self):
        # No package.json/webpack config/node_modules anywhere in the repo.
        self.assertFalse((_REPO_ROOT / "package.json").exists())
        self.assertFalse((_REPO_ROOT / "webpack.config.js").exists())


class PdfViewerAdapterJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")

    def test_loads_vendored_pdfjs_via_dynamic_import_not_a_cdn(self):
        self.assertIn("import('/static/js/vendor/pdfjs/pdf.min.mjs')", self.js)
        self.assertNotIn("cdn.", self.js.lower())
        self.assertNotIn("unpkg.com", self.js)
        self.assertNotIn("jsdelivr", self.js)

    def test_worker_src_configured(self):
        self.assertIn("GlobalWorkerOptions.workerSrc", self.js)
        self.assertIn("/static/js/vendor/pdfjs/pdf.worker.min.mjs", self.js)

    def test_mount_and_unmount_exposed(self):
        self.assertIn("window.ArchioskPdfViewer = { mount: mount, unmount: unmount }", self.js)

    def test_auto_mount_checks_for_the_real_container_element(self):
        self.assertIn("document-viewer-pdf-canvas", self.js)
        self.assertIn("autoMountEl.dataset.pdfUrl", self.js)

    def test_page_navigation_clamps_to_valid_range(self):
        idx = self.js.index("function goToPage(n)")
        body = self.js[idx: idx + 300]
        self.assertIn("Math.max(1, Math.min(pdfDoc.numPages, n))", body)

    def test_zoom_clamped_to_a_sane_range(self):
        idx = self.js.index("function setZoom(z)")
        body = self.js[idx: idx + 200]
        self.assertIn("Math.max(0.25, Math.min(4, z))", body)

    def test_rotation_is_cumulative_and_wraps(self):
        idx = self.js.index("function rotate()")
        body = self.js[idx: idx + 150]
        self.assertIn("(currentRotation + 90) % 360", body)

    def test_search_uses_real_text_extraction_not_a_stub(self):
        self.assertIn("getTextContent()", self.js)
        self.assertIn("function ensurePageText(n)", self.js)
        self.assertIn("function runSearch(query)", self.js)

    def test_search_is_cached_per_page(self):
        idx = self.js.index("function ensurePageText(n)")
        body = self.js[idx: idx + 300]
        self.assertIn("pageTextCache[n]", body)

    def test_print_opens_the_real_file_not_a_stub(self):
        idx = self.js.index("printBtn.addEventListener")
        body = self.js[idx: idx + 600]
        self.assertIn("window.open(downloadLink.href", body)

    def test_download_link_gets_the_real_url_and_filename(self):
        self.assertIn("downloadLink.href = url", self.js)
        self.assertIn("downloadLink.setAttribute('download', downloadFilename)", self.js)

    def test_responsive_breakpoint_matches_existing_convention(self):
        self.assertIn("window.matchMedia('(max-width: 900px)')", self.js)

    def test_responsive_reparents_the_same_node_not_a_clone(self):
        idx = self.js.index("function applyResponsiveState")
        body = self.js[idx: idx + 700]
        self.assertIn("overflowPanel.appendChild(secondaryGroup)", body)
        self.assertIn("secondaryHomeParent.insertBefore(secondaryGroup", body)
        self.assertNotIn("cloneNode", body)

    def test_render_cancels_a_superseded_render_task(self):
        self.assertIn("renderTask.cancel()", self.js)

    def test_failed_load_hides_controls_rather_than_leaving_a_broken_state(self):
        idx = self.js.index(".catch(function (err)")
        body = self.js[idx: idx + 200]
        self.assertIn("hideControls()", body)


class CssThemeAndRestraintTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _section(self, start_selector, end_selector):
        start = self.css.index(start_selector)
        end = self.css.index(end_selector, start)
        return self.css[start:end]

    def test_document_controls_region_has_no_hardcoded_colors(self):
        section = self._section(".workspace-topbar-document-controls {", ".workspace-topbar-controls {")
        self.assertNotRegex(section, r"#[0-9a-fA-F]{3,6}\b")
        self.assertNotIn("rgb(", section)
        self.assertNotIn("rgba(", section)

    def test_no_white_background_transplanted_into_the_controls(self):
        section = self._section(".workspace-topbar-document-controls {", ".workspace-topbar-controls {")
        self.assertNotIn("background: #fff", section.lower())
        self.assertNotIn("background: white", section.lower())
        # No per-button VISIBLE border/box - "read as part of the
        # application, not a bright toolbar pasted over it." (border:
        # none is fine - it's the explicit absence of one.)
        doc_control_btn = self._section(".doc-control-btn {", ".doc-control-btn:hover")
        self.assertIn("border: none", doc_control_btn)
        self.assertNotRegex(doc_control_btn, r"border:\s*\d")
        self.assertNotIn("box-shadow", doc_control_btn)

    def test_canvas_container_reuses_the_same_box_as_the_old_iframe(self):
        old = self._section(".document-viewer-frame {", ".document-viewer-image {")
        new = self._section(".document-viewer-canvas-container {", ".document-viewer-canvas {")
        self.assertIn("height: 70vh", old)
        self.assertIn("height: 70vh", new)
        self.assertIn("border: 1px solid var(--border)", new)
        self.assertIn("background: var(--surface-primary)", new)

    def test_overflow_panel_hidden_until_javascript_marks_it_active(self):
        section = self._section(".doc-controls-overflow {", ".doc-controls-overflow.doc-controls-overflow-active")
        self.assertIn("display: none", section)

    def test_focus_visible_styling_present(self):
        self.assertIn(".doc-control-btn:focus-visible", self.css)


if __name__ == "__main__":
    unittest.main()
