"""
CLAUDE-SNAPSHOT-DUAL-SURFACE-01 - Snapshot follows active document
surface (Main or Eye) and opens as a new Main tab.

Genuinely new capability this stage: a repo-wide search (services/,
routes/, static/js/) found no pre-existing "-01/-02 sequential
document-name-suffix screenshot mechanism" to preserve - confirmed with
the Product Owner directly before building it fresh (see the session's
own AskUserQuestion exchange).

Backend (services/image_intelligence.py's register_document_snapshot,
routes/api.py's create_document_snapshot) is covered with real, hermetic
Flask test-client calls, the same pattern test_mm5_image_intelligence.py
already establishes for register_eye_capture/extract_bounded_crop.
Frontend (pdf_viewer.js's per-surface takeSnapshot, the shared toolbar
button, eye_pane.js's one-shot restore-on-navigate) is covered at the
source-structure level - no real browser tool exists in this
environment (this repo's own established ceiling). The full live flow
(Main-focused snapshot, Eye-focused snapshot with Eye surviving the
navigation, sequential numbering, Compare participation) was verified
directly on archiosk.com as part of this stage's own required live
proof, not re-asserted here.
"""
from __future__ import annotations

import io
import re
import shutil
import tempfile
from pathlib import Path

import unittest

from PIL import Image

from services.case_workspace import (
    CaseWorkspaceStore,
    KNOWN_SOURCE_ORIGIN_TYPES,
    SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT,
)
from services.image_intelligence import ImageIntelligenceError, register_document_snapshot

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_PDF_VIEWER_JS_PATH = _REPO_ROOT / "static" / "js" / "pdf_viewer.js"
_EYE_PANE_JS_PATH = _REPO_ROOT / "static" / "js" / "eye_pane.js"


def _build_png(width: int = 60, height: int = 40, color=(10, 120, 200)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


class RegisterDocumentSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_snapshot_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-snapshot")
        self.parent = self.store.add_source(
            self.workspace, name="RFP-27-114-North-Bayview-Courthouse.pdf",
            file_path=str(self.tmp_dir / "parent.pdf"), kind="drawing",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_first_snapshot_is_named_dash_01(self):
        result = register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=1,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        self.assertEqual(result["name"], "RFP-27-114-North-Bayview-Courthouse-01.png")

    def test_second_snapshot_is_named_dash_02(self):
        register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=1,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        second = register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=2,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        self.assertEqual(second["name"], "RFP-27-114-North-Bayview-Courthouse-02.png")

    def test_snapshot_of_a_snapshot_still_numbers_off_the_original_parent_stem(self):
        # A Snapshot's own name is "<parent-stem>-NN" - taking a Snapshot
        # OF a Snapshot uses ITS OWN name as the new stem (a snapshot IS a
        # real, independent Source), which is honest ("source-01-01" makes
        # its own lineage self-evident) rather than silently collapsing
        # back to the ORIGINAL grandparent's stem.
        first = register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=1,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        second = register_document_snapshot(
            self.store, self.workspace, parent_source_id=first["source_id"], page_number=None,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        self.assertEqual(second["name"], "RFP-27-114-North-Bayview-Courthouse-01-01.png")

    def test_provenance_records_parent_and_page(self):
        result = register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=3,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        snapshot_source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertEqual(snapshot_source["origin_type"], SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT)
        self.assertEqual(snapshot_source["origin_reference"], f"{self.parent['id']}#page=3")

    def test_provenance_without_a_page_number_omits_the_page_fragment(self):
        result = register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=None,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        snapshot_source = self.store._find(self.workspace.sources, result["source_id"])
        self.assertEqual(snapshot_source["origin_reference"], self.parent["id"])

    def test_parent_source_is_never_mutated(self):
        before = dict(self.parent)
        register_document_snapshot(
            self.store, self.workspace, parent_source_id=self.parent["id"], page_number=1,
            raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
        )
        after = self.store._find(self.workspace.sources, self.parent["id"])
        self.assertEqual(before["name"], after["name"])
        self.assertEqual(before["file_path"], after["file_path"])
        self.assertIsNone(before.get("origin_type"))
        self.assertIsNone(after.get("origin_type"))

    def test_unknown_parent_source_raises(self):
        with self.assertRaises(ImageIntelligenceError):
            register_document_snapshot(
                self.store, self.workspace, parent_source_id="does-not-exist", page_number=1,
                raw_bytes=_build_png(), sources_dir=self.tmp_dir, actor="tester",
            )

    def test_malformed_image_bytes_raises(self):
        with self.assertRaises(ImageIntelligenceError):
            register_document_snapshot(
                self.store, self.workspace, parent_source_id=self.parent["id"], page_number=1,
                raw_bytes=b"not a real png", sources_dir=self.tmp_dir, actor="tester",
            )

    def test_document_snapshot_origin_type_is_known(self):
        self.assertIn(SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT, KNOWN_SOURCE_ORIGIN_TYPES)


class SnapshotApiRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_snapshot_api_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "snapshot-api-project"

        document = ParsedDocument(
            project_id=self.project_id, filename="spec.txt", ingested_at="2026-01-01T00:00:00+00:00",
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.workspace.owner = "tester"
        self.parent = self.store.add_source(
            self.workspace, name="drawing-set.pdf", file_path=str(self.tmp_dir / "drawing-set.pdf"), kind="drawing",
        )
        self.store.save(self.workspace)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as_admin(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"
        return client

    def _client_as_viewer(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "viewer"
            sess["role"] = "user"
        return client

    def _data_url(self):
        import base64
        return "data:image/png;base64," + base64.b64encode(_build_png()).decode("ascii")

    def test_snapshot_creates_a_new_source_and_returns_it(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 2},
        )
        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertEqual(body["name"], "drawing-set-01.png")
        self.assertEqual(body["parent_source_id"], self.parent["id"])
        self.assertEqual(body["page_number"], 2)

    def test_snapshot_requires_admin_role(self):
        client = self._client_as_viewer()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 1},
        )
        self.assertEqual(response.status_code, 403)

    def test_snapshot_requires_authentication(self):
        client = self.flask_app.test_client()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 1},
        )
        self.assertEqual(response.status_code, 401)

    def test_snapshot_missing_image_returns_400(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"page": 1},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_image")

    def test_snapshot_unknown_source_returns_400(self):
        client = self._client_as_admin()
        response = client.post(
            f"/api/v1/documents/{self.project_id}/sources/does-not-exist/snapshot",
            json={"image": self._data_url(), "page": 1},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_snapshot")

    def test_two_snapshots_via_api_number_sequentially(self):
        client = self._client_as_admin()
        first = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 1},
        ).get_json()
        second = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 1},
        ).get_json()
        self.assertEqual(first["name"], "drawing-set-01.png")
        self.assertEqual(second["name"], "drawing-set-02.png")

    def test_snapshot_of_a_snapshot_via_api_uses_its_own_name_as_the_new_stem(self):
        client = self._client_as_admin()
        first = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{self.parent['id']}/snapshot",
            json={"image": self._data_url(), "page": 1},
        ).get_json()
        second = client.post(
            f"/api/v1/documents/{self.project_id}/sources/{first['source_id']}/snapshot",
            json={"image": self._data_url(), "page": None},
        )
        self.assertEqual(second.status_code, 201)
        self.assertEqual(second.get_json()["name"], "drawing-set-01-01.png")


class SnapshotFrontendStructureTests(unittest.TestCase):
    def setUp(self):
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.pdf_viewer_js = _PDF_VIEWER_JS_PATH.read_text(encoding="utf-8")
        self.eye_pane_js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")

    def test_snapshot_button_lives_in_the_shared_toolbar(self):
        self.assertIn('id="doc-snapshot"', self.base_html)
        self.assertIn('id="doc-snapshot-status"', self.base_html)

    def test_each_surface_exposes_take_snapshot(self):
        self.assertIn("takeSnapshot: takeSnapshot,", self.pdf_viewer_js)
        self.assertIn("function takeSnapshot()", self.pdf_viewer_js)

    def test_snapshot_click_handler_dispatches_to_focused_surface(self):
        idx = self.pdf_viewer_js.index("snapshotBtn.addEventListener")
        body = self.pdf_viewer_js[idx:idx + 1500]
        self.assertIn("var s = getFocused();", body)
        self.assertIn("s.takeSnapshot()", body)

    def test_snapshot_navigates_via_the_same_document_open_mechanism(self):
        idx = self.pdf_viewer_js.index("snapshotBtn.addEventListener")
        body = self.pdf_viewer_js[idx:idx + 1800]
        self.assertIn("data-base-url", body)
        self.assertIn("?source=", body)

    def test_eye_triggered_snapshot_stashes_restore_state_before_navigating(self):
        idx = self.pdf_viewer_js.index("snapshotBtn.addEventListener")
        body = self.pdf_viewer_js[idx:idx + 1800]
        self.assertIn("wasEye", body)
        self.assertIn("beehive:eye:pending-restore:", body)
        self.assertIn("getRestoreState", body)

    def test_eye_pane_exposes_get_restore_state(self):
        self.assertIn("getRestoreState: getRestoreState", self.eye_pane_js)
        body = self.eye_pane_js[self.eye_pane_js.index("function getRestoreState()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("if (!currentEyeSourceId) return null;", body)

    def test_eye_pane_restores_pending_state_once_on_load(self):
        idx = self.eye_pane_js.index("restorePendingEyeStateIfAny")
        body = self.eye_pane_js[idx:idx + 900]
        self.assertIn("sessionStorage.getItem(key)", body)
        self.assertIn("sessionStorage.removeItem(key)", body)
        self.assertIn("loadDocument(state.sourceId, state.name, state.kind, state.projectId);", body)


if __name__ == "__main__":
    unittest.main()
