"""
CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION, Section B - "Internal-first
document opening."

Selecting a project document already displayed it inside the
Workspace pane for formats with a genuine in-app renderer (drawing
`<img>`, PDF `<canvas>`, XLSX `<iframe>`) - but any OTHER format
(.txt/.docx/etc, no dedicated branch) fell back to the SAME
`<iframe src=workspace.source_file>` those two use, even though most
browsers cannot render those formats inline. Loading that URL inside
an iframe silently triggered an OS-level download the moment the
Source was selected - "browser/OS behavior interrupts forward
movement," exactly the live defect this stage's own Section B names.

Fixed with a calm, honest in-app card (`display.document.no-preview`)
plus two explicit secondary actions - "Open externally"
(`as_attachment=False`, browser decides) and "Download"
(`?download=1`, forces `as_attachment=True`) - both hitting the SAME,
otherwise-unchanged `workspace.source_file` route. Drawing/PDF/XLSX
Sources are completely untouched by this correction.

Run via:

    python -m unittest tests.test_ca1d_river_po02_document_opening -v
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
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class DocumentOpeningTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_po02_doc_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="po02_doc_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="po02_doc_owner", project_name="Riverside PO02 Doc Workspace", filename="rfp.txt")
        self.project_id = self.doc.project_id
        self.client = self._client_as("po02_doc_owner", 1)
        self.source_id = CaseWorkspaceStore(self.tmp_dir).get(self.project_id).sources[0]["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"the real document content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def test_unsupported_format_shows_the_in_app_card_not_an_iframe(self):
        body = self.client.get(f"/projects/{self.project_id}/workspace?source={self.source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document.no-preview"', body)
        self.assertNotIn("document-viewer-frame", body)

    def test_card_offers_both_explicit_secondary_actions(self):
        body = self.client.get(f"/projects/{self.project_id}/workspace?source={self.source_id}").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.document.open-externally"', body)
        self.assertIn('data-ui-ref="display.document.download"', body)

    def test_open_externally_link_does_not_force_a_download(self):
        body = self.client.get(f"/projects/{self.project_id}/workspace?source={self.source_id}").get_data(as_text=True)
        start = body.index('data-ui-ref="display.document.open-externally"')
        end = body.index("</a>", start)
        tag = body[start:end]
        self.assertNotIn("download=1", tag)
        self.assertIn('target="_blank"', tag)

    def test_download_link_includes_the_download_query_param(self):
        body = self.client.get(f"/projects/{self.project_id}/workspace?source={self.source_id}").get_data(as_text=True)
        start = body.index('data-ui-ref="display.document.download"')
        end = body.index("</a>", start)
        tag = body[start:end]
        self.assertIn("download=1", tag)

    def test_source_file_route_default_is_inline_not_attachment(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace/sources/{self.source_id}/file")
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("inline", disposition)
        self.assertNotIn("attachment", disposition)

    def test_source_file_route_with_download_param_forces_attachment(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace/sources/{self.source_id}/file?download=1")
        self.assertEqual(resp.status_code, 200)
        disposition = resp.headers.get("Content-Disposition", "")
        self.assertIn("attachment", disposition)

    def test_both_urls_serve_the_same_real_file_content(self):
        inline = self.client.get(f"/projects/{self.project_id}/workspace/sources/{self.source_id}/file")
        download = self.client.get(f"/projects/{self.project_id}/workspace/sources/{self.source_id}/file?download=1")
        self.assertEqual(inline.data, download.data)
        self.assertEqual(inline.data, b"the real document content")


if __name__ == "__main__":
    unittest.main()
