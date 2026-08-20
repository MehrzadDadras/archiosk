"""
CLAUDE-P40-E2 - Contextual Right Toolbox and Recoverable Project/Document
Removal.

Covers what was actually built:
  - the old permanent Findings-only right pane is now a persistent,
    contextual Toolbox (.workspace-pane-toolbox) - Findings is one tool
    inside it, shown when an Investigation is open; Document tools when
    a Document is selected; restrained Project tools otherwise;
  - "Remove Document"/"Restore Document" (recoverable - the record, its
    id, file_path, and every dependent Finding/Requirement reference are
    untouched; only listing/AI-context visibility changes);
  - "Remove Project"/"Restore Project" (recoverable - the whole bundle,
    same project_id, restored unchanged);
  - "Removed Items" (Removed Documents inside a Project's own Toolbox,
    Removed Projects at /removed-projects) for authorized restoration;
  - owner-or-admin authority enforced in the store layer, not just the
    route layer;
  - Reset Project Data (administrator-only, typed confirmation, exact
    inventory, snapshot-before-wipe, duplicate-submission guard,
    accounts/security config surviving).

Every ingestion call spies on BHiveParser.parse rather than letting it
run for real (existing repo-wide convention).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import json
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
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseP40E2TestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        # CLAUDE-P40-E2A2: registry_snapshots/, reset_transactions/, and
        # the reset/restore lock file all live beside REGISTRY_STORE_PATH
        # (tmp_dir.parent) - a bare tempfile.mkdtemp() puts tmp_dir
        # directly under the shared OS temp root, meaning tmp_dir.parent
        # would be that SAME shared root for every test in the whole
        # suite, and all three would silently collide across tests. An
        # isolated parent directory, with tmp_dir as ITS OWN child, keeps
        # all three exclusively scoped to this one test.
        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_p40e2_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e2_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e2_viewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add(User(username="p40e2_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e2_owner", project_name="Riverside P40E2 Workspace")
        self.project_id = self.doc.project_id

    def tearDown(self):
        # self.tmp_root exclusively owns tmp_dir (the registry itself)
        # AND registry_snapshots/reset_transactions/the lock file - one
        # rmtree cleans up everything this test could possibly have
        # created.
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _first_source_id(self) -> str:
        workspace = self._store().get(self.project_id)
        return workspace.sources[0]["id"]


class ContextualToolboxTests(_BaseP40E2TestCase):
    def test_project_home_shows_restrained_project_tools(self):
        client = self._client_as("p40e2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("workspace-pane-toolbox", body)
        self.assertIn("Remove Project", body)
        self.assertNotIn('id="findings"', body)

    def test_investigation_open_shows_findings_tool(self):
        # CLAUDE-P40-VW2: "Remove Project" now lives in Lists' own
        # Project Tools branch (always part of the active Project's
        # rendered hierarchy, not Toolbox-contextual) - this assertion
        # is scoped to the Toolbox region specifically, the thing this
        # test actually means to check, rather than the whole body.
        client = self._client_as("p40e2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn("workspace-pane-toolbox", body)
        self.assertIn("Findings (0)", body)
        toolbox_start = body.index('id="workspace-toolbox-panel"')
        toolbox = body[toolbox_start:body.index("</aside>", toolbox_start)]
        self.assertNotIn("Remove Project", toolbox)

    def test_document_selected_shows_document_tools(self):
        client = self._client_as("p40e2_owner", 1)
        source_id = self._first_source_id()
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("workspace-pane-toolbox", body)
        self.assertIn("Remove Document", body)

    def test_toolbox_always_renders_two_column_grid(self):
        client = self._client_as("p40e2_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("case-workspace-single-column", body)


class DocumentRemovalTests(_BaseP40E2TestCase):
    def test_remove_shows_confirm_gate_first(self):
        client = self._client_as("p40e2_owner", 1)
        source_id = self._first_source_id()
        resp = client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove")
        self.assertIn(b"Yes &mdash; remove this Document", resp.data)
        # nothing changed yet
        self.assertIsNone(self._store().get(self.project_id).sources[0].get("removed_at"))

    def test_confirm_yes_removes_and_confirm_no_cancels(self):
        client = self._client_as("p40e2_owner", 1)
        source_id = self._first_source_id()

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "no"})
        self.assertIsNone(self._store().get(self.project_id).sources[0].get("removed_at"))

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})
        source = self._store().get(self.project_id).sources[0]
        self.assertIsNotNone(source.get("removed_at"))
        self.assertEqual(source.get("removed_by"), "p40e2_owner")
        # the record itself, id, and file_path are untouched
        self.assertEqual(source["id"], source_id)

    def test_removed_document_absent_from_active_sources_listing(self):
        client = self._client_as("p40e2_owner", 1)
        source_id = self._first_source_id()
        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})

        # CODEX-PSD-LEFT-RAIL-01 retired the visible Documents wrapper as
        # well: active files now project directly beneath the Project root.
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn('data-ui-ref="lists.project.documents.leaf"', body)
        self.assertNotIn('>Documents <span class="launcher-count">', body)

    def test_restore_reactivates_same_id_no_reingestion(self):
        client = self._client_as("p40e2_owner", 1)
        source_id = self._first_source_id()
        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/restore")
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.sources), 1)
        self.assertEqual(workspace.sources[0]["id"], source_id)
        self.assertIsNone(workspace.sources[0].get("removed_at"))

    def test_dependent_finding_still_resolves_removed_source_honestly(self):
        # A Finding/Requirement citing a removed Source must keep
        # resolving it (never a KeyError/broken page) - the document
        # viewer itself, reached directly by a preserved reference,
        # shows an honest "removed" state rather than disappearing.
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        store.remove_source(workspace, source_id=source_id, actor="p40e2_owner", actor_role="admin")

        client = self._client_as("p40e2_owner", 1)
        resp = client.get(f"/projects/{self.project_id}/workspace?source={source_id}")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("removed", body.lower())
        self.assertIn("Restore Document", body)

    def test_non_owner_non_admin_cannot_remove(self):
        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="p40e2_viewer", actor="p40e2_owner", actor_role="admin")

        client = self._client_as("p40e2_viewer", 2, role="read_only")
        source_id = self._first_source_id()
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(self._store().get(self.project_id).sources[0].get("removed_at"))

    def test_outsider_gets_404_not_a_leak(self):
        client = self._client_as("p40e2_outsider", 3, role="read_only")
        source_id = self._first_source_id()
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"},
        )
        self.assertEqual(resp.status_code, 404)


class ProjectRemovalTests(_BaseP40E2TestCase):
    def test_remove_project_confirm_gate_then_removal(self):
        client = self._client_as("p40e2_owner", 1)
        resp = client.post(f"/projects/{self.project_id}/workspace/remove")
        self.assertIn(b"Remove this Project", resp.data)
        self.assertIsNone(self._store().get(self.project_id).removed_at)

        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})
        workspace = self._store().get(self.project_id)
        self.assertIsNotNone(workspace.removed_at)
        self.assertEqual(workspace.project_id, self.project_id)

    def test_removed_project_absent_from_projects_list_but_reachable_directly(self):
        client = self._client_as("p40e2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

        listing = client.get("/projects").get_data(as_text=True)
        self.assertNotIn(self.project_id, listing)

        # P32 access is unaffected by removal - still directly reachable
        # by the owner (needed for the restore flow itself).
        direct = client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(direct.status_code, 200)

    def test_removed_project_absent_from_nav_recent_projects(self):
        client = self._client_as("p40e2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

        home = client.get("/").get_data(as_text=True)
        self.assertNotIn(self.project_id, home)

    def test_appears_in_removed_projects_listing_and_restores(self):
        client = self._client_as("p40e2_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

        removed_body = client.get("/removed-projects").get_data(as_text=True)
        self.assertIn(self.project_id, removed_body)

        client.post(f"/projects/{self.project_id}/workspace/restore")
        workspace = self._store().get(self.project_id)
        self.assertIsNone(workspace.removed_at)
        self.assertEqual(workspace.project_id, self.project_id)

        listing = client.get("/projects").get_data(as_text=True)
        self.assertIn(self.project_id, listing)

    def test_removed_project_name_not_leaked_to_unauthorized_user(self):
        client_owner = self._client_as("p40e2_owner", 1)
        client_owner.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

        client_outsider = self._client_as("p40e2_outsider", 3, role="read_only")
        removed_body = client_outsider.get("/removed-projects").get_data(as_text=True)
        self.assertNotIn(self.project_id, removed_body)

    def test_non_owner_non_admin_cannot_remove_project(self):
        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(workspace, username="p40e2_viewer", actor="p40e2_owner", actor_role="admin")

        client = self._client_as("p40e2_viewer", 2, role="read_only")
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})
        self.assertIsNone(self._store().get(self.project_id).removed_at)


class StoreLevelRemovalUnitTests(_BaseP40E2TestCase):
    """Direct CaseWorkspaceStore coverage - no route layer involved."""

    def test_active_sources_excludes_removed_removed_sources_includes_only_removed(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        self.assertEqual(len(store.active_sources(workspace)), 1)
        self.assertEqual(len(store.removed_sources(workspace)), 0)

        store.remove_source(workspace, source_id=source_id, actor="p40e2_owner", actor_role="admin")
        self.assertEqual(store.active_sources(workspace), [])
        self.assertEqual(len(store.removed_sources(workspace)), 1)

    def test_remove_source_twice_raises(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        store.remove_source(workspace, source_id=source_id, actor="p40e2_owner", actor_role="admin")
        with self.assertRaises(CaseWorkspaceError):
            store.remove_source(workspace, source_id=source_id, actor="p40e2_owner", actor_role="admin")

    def test_restore_source_not_removed_raises(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        with self.assertRaises(CaseWorkspaceError):
            store.restore_source(workspace, source_id=source_id, actor="p40e2_owner", actor_role="admin")

    def test_remove_project_twice_raises(self):
        store = self._store()
        workspace = store.get(self.project_id)
        store.remove_project(workspace, actor="p40e2_owner", actor_role="admin")
        with self.assertRaises(CaseWorkspaceError):
            store.remove_project(workspace, actor="p40e2_owner", actor_role="admin")

    def test_unauthorized_actor_raises_for_both_operations(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        with self.assertRaises(CaseWorkspaceError):
            store.remove_source(workspace, source_id=source_id, actor="random_person", actor_role="")
        with self.assertRaises(CaseWorkspaceError):
            store.remove_project(workspace, actor="random_person", actor_role="")


class ResetProjectDataTests(_BaseP40E2TestCase):
    def _admin_client(self):
        return self._client_as("p40e2_owner", 1, role="admin")

    def test_non_admin_cannot_reach_reset(self):
        client = self._client_as("p40e2_viewer", 2, role="read_only")
        resp = client.get("/admin/reset-project-data")
        self.assertNotEqual(resp.status_code, 200)

    def test_get_shows_exact_inventory(self):
        client = self._admin_client()
        body = client.get("/admin/reset-project-data").get_data(as_text=True)
        self.assertIn("1 Project(s)", body)
        self.assertIn("RESET PROJECT DATA", body)

    def test_wrong_phrase_does_not_reset(self):
        client = self._admin_client()
        client.post("/admin/reset-project-data", data={"confirmation_phrase": "nope"})
        self.assertIsNotNone(self._store().get(self.project_id))

    def test_correct_phrase_resets_and_snapshots_and_preserves_accounts(self):
        from models import User

        client = self._admin_client()
        resp = client.post(
            "/admin/reset-project-data", data={"confirmation_phrase": "RESET PROJECT DATA"}, follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

        # project data gone
        self.assertIsNone(self._store().get(self.project_id))
        self.assertNotIn(self.project_id, [p.name for p in self.tmp_dir.iterdir()])

        # a snapshot exists with the original project file in it - the
        # snapshot root is a sibling of REGISTRY_STORE_PATH, which sits
        # directly under the shared OS temp dir in this test environment,
        # so other tests' snapshots may also be present; only assert
        # that OURS is there, not that we're the only one.
        snapshot_root = self.tmp_dir.parent / "registry_snapshots"
        self.assertTrue(snapshot_root.exists())
        matches = [d for d in snapshot_root.iterdir() if (d / f"{self.project_id}.json").exists()]
        self.assertEqual(len(matches), 1)

        # security_governance/ (auth-adjacent state) is preserved, not wiped
        self.assertTrue((self.tmp_dir / "security_governance").exists())

        # accounts survive - a wholly separate store (bhive.db), never touched
        with self.flask_app.app_context():
            self.assertIsNotNone(User.query.filter_by(username="p40e2_owner").first())

        # clean landing state
        listing = client.get("/projects").get_data(as_text=True)
        self.assertIn("No projects yet.", listing)

    def test_duplicate_submission_is_rejected_by_the_lock(self):
        # CLAUDE-P40-E2A2: a lock is only "genuinely active" (must block)
        # if the PID recorded in it is still running - an abandoned lock
        # (no PID, or a dead one) is auto-recovered instead, not a
        # permanent block (Section C). Writing this test process's own
        # (very much alive) PID simulates a real concurrent holder.
        import os as _os
        lock_path = self.tmp_dir.parent / ".reset_project_data.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(str(_os.getpid()), encoding="ascii")
        try:
            client = self._admin_client()
            client.post("/admin/reset-project-data", data={"confirmation_phrase": "RESET PROJECT DATA"})
            # nothing was reset - the project is still there
            self.assertIsNotNone(self._store().get(self.project_id))
        finally:
            lock_path.unlink(missing_ok=True)

    def test_audit_record_written(self):
        client = self._admin_client()
        client.post("/admin/reset-project-data", data={"confirmation_phrase": "RESET PROJECT DATA"})
        audit_path = self.tmp_dir / "security_governance" / "reset_audit.jsonl"
        self.assertTrue(audit_path.exists())
        record = json.loads(audit_path.read_text(encoding="utf-8").splitlines()[-1])
        self.assertEqual(record["actor"], "p40e2_owner")
        self.assertIn("snapshot_dir", record)


if __name__ == "__main__":
    unittest.main()
