"""
Snapshot viewing.

CaseWorkspaceStore.create_snapshot was already wired to a real route
(create_project_snapshot), but snapshots_for_project/get_snapshot -
the entire viewing side - had no route or template at all. Project Home
showed only "N Snapshot(s) recorded", a dead end: there was no way to
ever see what a Snapshot actually froze after creating it. This covers
the template-only fix that lists them (workspace.snapshots is already
in the render context - no new route needed).

CLAUDE-P27 extends this file to cover the two remaining reads:
resolve_snapshot_objects (open one Snapshot's resolved detail, via
?snapshot=<id> on the existing show_workspace route) and
compare_snapshots (via ?compare_a=<id>&compare_b=<id>). Both reuse
show_workspace/case_workspace.html rather than a new route or template,
the same "?case=<id> opens inline" pattern already used for Cases.

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
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.add_source(
            self.store.get(self.project_id), name="RFP.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_created_snapshot_is_visible_afterward(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("No Snapshots recorded yet.", resp.get_data(as_text=True))

        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots",
            data={"label": "Pre-Award baseline", "note": "Before the award decision"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
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
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertLess(body.index("Second snapshot"), body.index("First snapshot"))

    def test_open_snapshot_shows_identity_and_resolved_counts(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Pre-Award baseline"},
        )
        workspace = self.store.get(self.project_id)
        snapshot_id = workspace.snapshots[0]["id"]

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview&snapshot={snapshot_id}")
        body = resp.get_data(as_text=True)
        self.assertIn("project state version", body)
        # 2 of 2: the auto-registered RFQ/RFP source plus the one setUp
        # added directly, both still resolving to current records.
        self.assertIn("sources: 2 of 2 resolve to current records", body)
        self.assertNotIn("no longer resolvable", body)

    def test_open_unknown_snapshot_id_is_silently_ignored(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace?snapshot=does-not-exist")
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("project state version", resp.get_data(as_text=True))

    def test_open_snapshot_discloses_unresolvable_reference(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Baseline"},
        )
        workspace = self.store.get(self.project_id)
        snapshot_id = workspace.snapshots[0]["id"]
        self.assertEqual(len(workspace.snapshots[0]["reference_lists"]["sources"]), 2)

        # Append-only architecture means a frozen id normally never stops
        # resolving - simulate the honest edge case resolve_snapshot_objects
        # itself documents (CURRENT content, not a guarantee the id still
        # exists) by removing a source record directly, bypassing any route.
        workspace.sources.pop()
        self.store.save(workspace)

        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview&snapshot={snapshot_id}")
        body = resp.get_data(as_text=True)
        self.assertIn("sources: 1 of 2 resolve to current records", body)
        self.assertIn("1 no longer resolvable", body)

    def test_compare_two_snapshots_shows_added_and_unchanged(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "First"},
        )
        workspace = self.store.get(self.project_id)
        first_id = workspace.snapshots[0]["id"]

        self.store.add_source(
            workspace, name="Addendum1.pdf", file_path="/tmp/addendum1.pdf",
            kind="owner_project_requirements",
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Second"},
        )
        workspace = self.store.get(self.project_id)
        second_id = next(s["id"] for s in workspace.snapshots if s["label"] == "Second")

        resp = self.client.get(
            f"/projects/{self.project_id}/workspace?view=overview&compare_a={first_id}&compare_b={second_id}"
        )
        body = resp.get_data(as_text=True)
        self.assertIn("First", body)
        self.assertIn("Second", body)
        self.assertIn("sources: 2 &rarr; 3", body)
        self.assertIn("2 unchanged", body)
        self.assertIn("1 added", body)
        self.assertNotIn("removed", body.split("sources:", 1)[1].split("</li>", 1)[0])

    def test_compare_with_unknown_id_is_silently_ignored(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Only one"},
        )
        workspace = self.store.get(self.project_id)
        real_id = workspace.snapshots[0]["id"]

        resp = self.client.get(
            f"/projects/{self.project_id}/workspace?compare_a={real_id}&compare_b=does-not-exist"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn("Structural comparison only", resp.get_data(as_text=True))

    def test_snapshot_open_and_compare_are_project_home_only(self):
        self.client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "An Investigation"})
        workspace = self.store.get(self.project_id)
        case_id = workspace.cases[0]["id"]
        self.client.post(
            f"/projects/{self.project_id}/workspace/snapshots", data={"label": "Baseline"},
        )
        workspace = self.store.get(self.project_id)
        snapshot_id = workspace.snapshots[0]["id"]

        resp = self.client.get(
            f"/projects/{self.project_id}/workspace?case={case_id}&snapshot={snapshot_id}"
        )
        self.assertNotIn("project state version", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
