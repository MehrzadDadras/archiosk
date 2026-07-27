"""
Snapshot viewing.

CaseWorkspaceStore.create_snapshot was already wired to a real route
(create_project_snapshot), but snapshots_for_project/get_snapshot -
the entire viewing side - had no route or template at all. Project Home
showed only "N Snapshot(s) recorded", a dead end: there was no way to
ever see what a Snapshot actually froze after creating it. This covers
the template-only fix that lists them (workspace.snapshots is already
in the render context - no new route needed).

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class SnapshotViewingTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_snapshot_viewing_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-snapshot"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.add_source(
            self.store.get(self.project_id), name="RFP.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_created_snapshot_is_visible_afterward(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        self.assertIn("No Snapshots recorded yet.", resp.get_data(as_text=True))

        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots",
            data={"label": "Pre-Award baseline", "note": "Before the award decision"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertIn("View Snapshots (1)", body)
        self.assertIn("Pre-Award baseline", body)
        self.assertIn("Before the award decision", body)
        # 2, not 1: the auto-registered RFQ/RFP source plus the one this
        # test added directly.
        self.assertIn("sources: 2", body)

    def test_newest_snapshot_lists_first(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "First snapshot"},
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Second snapshot"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertLess(body.index("Second snapshot"), body.index("First snapshot"))


if __name__ == "__main__":
    unittest.main()
