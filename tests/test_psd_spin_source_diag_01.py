from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore, SOURCE_KIND_PROJECT_DOCUMENT
from services.requirements_registry import RequirementsRegistry


class SpinSourceSignatureDiagnosticTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_spin_source_diag_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "project-a"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id,
            filename="owner-program.docx",
            ingested_at="2026-08-19T00:00:00+00:00",
        ))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        workspace = self.store.get_or_create(self.project_id)
        self.active = self.store.add_source(
            workspace, name="owner-program.docx", file_path="owner-program.docx",
            kind=SOURCE_KIND_PROJECT_DOCUMENT, origin_type="upload",
        )
        workspace = self.store.get(self.project_id)
        self.removed = self.store.add_source(
            workspace, name="earlier-copy.docx", file_path="earlier-copy.docx",
            kind=SOURCE_KIND_PROJECT_DOCUMENT, origin_type="upload",
        )
        workspace = self.store.get(self.project_id)
        self.store.remove_source(workspace, self.removed["id"], actor="admin", actor_role="admin")
        workspace = self.store.get(self.project_id)
        signature = f'{self.active["id"]},{self.removed["id"]}'
        self.run = self.store.record_spin_run(
            workspace, spin_kind="first_spin", actor="admin", findings=[],
            source_signature=signature,
        )
        self.path = (
            f"/api/v1/documents/{self.project_id}/spin-runs/"
            f"{self.run['id']}/source-signature"
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self, role: str, username: str = "admin"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = role
        return client

    def test_non_admin_is_forbidden(self):
        response = self._client("read_only", "reader").get(self.path)
        self.assertEqual(response.status_code, 403)

    def test_admin_sees_exact_signature_and_truthful_removed_state_without_write(self):
        workspace_path = self.tmp_dir / f"{self.project_id}.workspace.json"
        before = workspace_path.read_bytes()
        response = self._client("admin").get(self.path)
        after = workspace_path.read_bytes()

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        expected = f'{self.active["id"]},{self.removed["id"]}'
        self.assertEqual(payload["spin_run"]["source_signature"], expected)
        self.assertEqual(payload["spin_run"]["project_id"], self.project_id)
        self.assertEqual([item["source_id"] for item in payload["sources"]], expected.split(","))
        self.assertTrue(payload["sources"][0]["active"])
        self.assertTrue(payload["sources"][0]["included_in_active_sources"])
        self.assertFalse(payload["sources"][1]["active"])
        self.assertFalse(payload["sources"][1]["included_in_active_sources"])
        self.assertIsNotNone(payload["sources"][1]["removed_at"])
        self.assertEqual(before, after)

    def test_foreign_source_id_is_not_resolved_across_projects(self):
        other_id = "project-b"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=other_id, filename="secret.docx",
            ingested_at="2026-08-19T00:00:00+00:00",
        ))
        other_workspace = self.store.get_or_create(other_id)
        foreign = self.store.add_source(
            other_workspace, name="secret.docx", file_path="secret.docx",
            kind=SOURCE_KIND_PROJECT_DOCUMENT,
        )
        workspace = self.store.get(self.project_id)
        run = self.store.record_spin_run(
            workspace, spin_kind="first_spin", actor="admin", findings=[],
            source_signature=foreign["id"],
        )
        response = self._client("admin").get(
            f"/api/v1/documents/{self.project_id}/spin-runs/{run['id']}/source-signature"
        )
        item = response.get_json()["sources"][0]
        self.assertEqual(item["resolution"], "UNRESOLVED SOURCE ID")
        self.assertIsNone(item["project_id"])
        self.assertIsNone(item["name"])

    def test_unknown_run_is_not_disclosed(self):
        response = self._client("admin").get(
            f"/api/v1/documents/{self.project_id}/spin-runs/not-real/source-signature"
        )
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
