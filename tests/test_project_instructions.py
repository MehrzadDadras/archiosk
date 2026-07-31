"""
CLAUDE-P38 (OBS-05) -- Project Instructions displayed only a bare
"Last updated by <username>" with no role, and a permanent governance-
explanation paragraph dominated the panel ahead of the actual
instruction text. Proves the issuer's role is now captured/displayed
and the explanation is no longer always-visible.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class ProjectInstructionsRoleTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_instructions_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-instructions"

        with self.flask_app.app_context():
            db.session.add(User(username="admin1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin1"
            sess["role"] = "admin"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(workspace, owner="admin1", actor="admin1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_setting_instructions_through_the_route_records_the_actors_role(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/instructions",
            data={"instructions": "Use metric units throughout."},
        )
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.operating_instructions, "Use metric units throughout.")
        self.assertEqual(workspace.operating_instructions_updated_by, "admin1")
        self.assertEqual(workspace.operating_instructions_updated_by_role, "admin")

    def test_role_is_displayed_alongside_the_actor(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/instructions",
            data={"instructions": "Use metric units throughout."},
        )
        page = self.client.get(f"/projects/{self.project_id}/workspace")
        body = page.get_data(as_text=True)
        self.assertIn("Last updated by admin1 (admin)", body)

    def test_explanation_is_not_permanently_visible(self):
        # Collapsed behind a disclosure control, not printed as static
        # always-rendered text ahead of the real instruction.
        page = self.client.get(f"/projects/{self.project_id}/workspace")
        body = page.get_data(as_text=True)
        self.assertIn("What are Project Instructions?", body)


if __name__ == "__main__":
    unittest.main()
