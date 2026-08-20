import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone

from services.case_workspace import CaseWorkspaceStore, ProjectWorkspace
from services.bhive_parser import ParsedDocument
from services.developer_tools import reset_analysis_state, reset_test_project
from services.governance import GovernanceLog
from services.requirements_registry import RequirementsRegistry


class DeveloperToolsResetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_dev_tools_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.audit = GovernanceLog(self.tmp)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _workspace(self, synthetic=True):
        workspace = ProjectWorkspace(
            project_id="project-a",
            display_title="Project Smoke Detector (PSD)" if synthetic else "Real Project",
            sources=[{"id": "source-1", "name": "owner.docx", "project_id": "project-a"}],
            structural_units=[{"id": "unit-1"}],
            addressable_regions=[{"id": "region-1"}],
            evidence_items=[{"id": "evidence-1"}],
            spin_runs=[{"id": "run-1", "finding_ids": ["spin-finding-1"]}],
            composer_findings=[
                {"id": "spin-finding-1", "spin_run_id": "run-1"},
                {"id": "human-finding-1"},
            ],
            cases=[{"id": "case-1"}],
            requirements=[{"id": "requirement-1"}],
            project_briefing={"summary": "derived"},
        )
        self.store.save(workspace)
        return workspace

    def test_analysis_reset_preserves_sources_and_evidence_and_is_idempotent(self):
        workspace = self._workspace()
        result = reset_analysis_state(self.store, workspace, self.audit, actor="admin")
        reloaded = self.store.get("project-a")
        self.assertEqual(result["removed_counts"]["spin_runs"], 1)
        self.assertEqual(reloaded.spin_runs, [])
        self.assertEqual(reloaded.composer_findings, [{"id": "human-finding-1"}])
        self.assertEqual(len(reloaded.sources), 1)
        self.assertEqual(reloaded.evidence_items, [{"id": "evidence-1"}])
        self.assertIsNone(reloaded.project_briefing)
        self.assertEqual(self.audit.read("project-a")[-1].event_type, "developer_project_reset")
        reset_analysis_state(self.store, reloaded, self.audit, actor="admin")
        self.assertEqual(self.store.get("project-a").spin_runs, [])

    def test_deep_test_reset_preserves_source_boundary_and_clears_mutable_state(self):
        workspace = self._workspace()
        reset_test_project(self.store, workspace, self.audit, actor="admin")
        reloaded = self.store.get("project-a")
        self.assertEqual(len(reloaded.sources), 1)
        self.assertEqual(len(reloaded.structural_units), 1)
        self.assertEqual(len(reloaded.evidence_items), 1)
        self.assertEqual(reloaded.cases, [])
        self.assertEqual(reloaded.requirements, [])
        self.assertEqual(reloaded.spin_runs, [])
        self.assertEqual(reloaded.composer_findings, [])
        self.assertEqual(self.audit.read("project-a")[-1].payload["reset_type"], "test_project")

    def test_deep_test_reset_rejects_unmarked_project(self):
        workspace = self._workspace(synthetic=False)
        with self.assertRaises(ValueError):
            reset_test_project(self.store, workspace, self.audit, actor="admin")
        self.assertEqual(len(self.store.get("project-a").sources), 1)

    def test_audit_failure_rolls_back_reset(self):
        workspace = self._workspace()
        original = self.store._path_for("project-a").read_bytes()
        failing_audit = type("FailingAudit", (), {"append": lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit"))})()
        with self.assertRaises(RuntimeError):
            reset_analysis_state(self.store, workspace, failing_audit, actor="admin")
        self.assertEqual(self.store._path_for("project-a").read_bytes(), original)
        self.assertEqual(len(self.store.get("project-a").spin_runs), 1)

    def test_developer_tools_requires_admin_and_developer_mode(self):
        import app as app_module
        flask_app = app_module.create_app("testing")
        flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        RequirementsRegistry(self.tmp).save(ParsedDocument(
            project_id="project-a", filename="PSD_Owner_Program.docx",
            ingested_at=datetime.now(timezone.utc).isoformat(),
        ))
        self._workspace()

        ordinary = flask_app.test_client()
        with ordinary.session_transaction() as session:
            session.update({"user_id": 1, "username": "viewer", "role": "read_only", "developer_mode": True})
        self.assertEqual(ordinary.get("/admin/developer-tools").status_code, 403)

        admin_without_mode = flask_app.test_client()
        with admin_without_mode.session_transaction() as session:
            session.update({"user_id": 1, "username": "admin", "role": "admin"})
        self.assertEqual(admin_without_mode.get("/admin/developer-tools").status_code, 403)

        admin = flask_app.test_client()
        with admin.session_transaction() as session:
            session.update({"user_id": 1, "username": "admin", "role": "admin", "developer_mode": True})
        response = admin.get("/admin/developer-tools?project_id=project-a")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Reset Analysis State", response.data)
        self.assertIn(b"Reset Test Project", response.data)


if __name__ == "__main__":
    unittest.main()
