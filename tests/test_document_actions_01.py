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

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class DocumentActionsTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_document_actions_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    _file(b"owner baseline", "owner-program.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Document Actions Fixture",
                )
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.source = self.store.get(self.project_id).sources[0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="owner", role="read_only"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = role
        return client

    @property
    def workspace_url(self):
        return f"/projects/{self.project_id}/workspace?source={self.source['id']}"

    @property
    def replace_url(self):
        return f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/replace"

    @property
    def remove_url(self):
        return f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/remove"

    def test_action_bar_and_document_menu_share_canonical_routes(self):
        body = self._client().get(self.workspace_url).get_data(as_text=True)
        download = f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/file?download=1"
        self.assertIn('data-ui-ref="display.document.actions"', body)
        self.assertIn('data-ui-ref="display.document.download"', body)
        self.assertIn('data-ui-ref="display.document.replace"', body)
        self.assertIn('data-ui-ref="display.document.remove"', body)
        self.assertIn('data-ui-ref="menu.document.download"', body)
        self.assertIn('data-ui-ref="menu.document.replace"', body)
        self.assertIn('data-ui-ref="menu.document.remove"', body)
        self.assertEqual(body.count(f'href="{download}"'), 2)
        self.assertEqual(body.count(f'href="{self.replace_url}"'), 2)
        self.assertEqual(body.count(f'action="{self.remove_url}"'), 3)  # action bar, menu, canonical Toolbox

    def test_replace_selection_is_read_only_and_names_selected_document(self):
        path = self.tmp / f"{self.project_id}.workspace.json"
        before = path.read_bytes()
        response = self._client().get(self.replace_url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Replace owner-program.txt", response.get_data(as_text=True))
        self.assertEqual(before, path.read_bytes())

    def test_replace_uses_supersession_and_redirects_to_new_source(self):
        response = self._client().post(
            f"/projects/{self.project_id}/workspace/sources/{self.source['id']}/revise-document",
            data={"document": _file(b"revision two", "owner-program-rev2.txt"), "confirm": "once"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        workspace = self.store.get(self.project_id)
        old = next(item for item in workspace.sources if item["id"] == self.source["id"])
        new = next(item for item in workspace.sources if item.get("supersedes_source_id") == old["id"])
        self.assertEqual(old["superseded_by_source_id"], new["id"])
        self.assertTrue(Path(old["file_path"]).exists())
        self.assertEqual(Path(old["file_path"]).read_bytes(), b"owner baseline")
        self.assertIn(f"source={new['id']}", response.headers["Location"])
        self.assertEqual(len(workspace.supersessions), 1)

    def test_remove_uses_existing_confirmation_and_soft_removal(self):
        client = self._client()
        confirmation = client.post(self.remove_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertIn("Remove &ldquo;owner-program.txt&rdquo;?", confirmation.get_data(as_text=True))
        response = client.post(self.remove_url, data={"confirm": "yes"})
        self.assertEqual(response.status_code, 302)
        source = self.store.get(self.project_id).sources[0]
        self.assertIsNotNone(source["removed_at"])
        self.assertTrue(Path(source["file_path"]).exists())

    def test_non_owner_sees_remove_disabled_and_direct_write_is_denied(self):
        workspace = self.store.get(self.project_id)
        self.store.grant_project_access(workspace, "reviewer", actor="owner", actor_role="admin")
        client = self._client("reviewer", "read_only")
        body = client.get(self.workspace_url).get_data(as_text=True)
        self.assertNotIn('data-ui-ref="display.document.remove"', body)
        client.post(self.remove_url, data={"confirm": "yes"})
        self.assertIsNone(self.store.get(self.project_id).sources[0]["removed_at"])

    def test_cross_project_source_is_not_available(self):
        response = self._client().get(
            f"/projects/{self.project_id}/workspace/sources/not-in-project/replace"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
