"""
CLAUDE-P40-E2A - Removed-State Containment and Reset-Recovery Proof.

P40-E2 built recoverable removal and a Reset Project Data snapshot, but
left two acceptance gaps: (1) an authorized user could still reach a
removed Project's/Document's ordinary active routes (authorization and
lifecycle are different checks), and (2) Reset Project Data proved
snapshot CREATION but never RESTORATION. This stage closes both.

Every test here exercises the real, hermetic filesystem persistence
layer (a fresh tempfile.mkdtemp() REGISTRY_STORE_PATH per test, real
CaseWorkspaceStore/RequirementsRegistry reads and writes, real
shutil.copytree/os.rename during reset/restore) - nothing about the
storage layer itself is mocked. Only BHiveParser.parse is stubbed, the
same repo-wide convention every other test file here uses to avoid a
real Anthropic API call.

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
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        # CLAUDE-P40-E2A2: registry_snapshots/, reset_transactions/, and
        # the reset/restore lock file all live beside REGISTRY_STORE_PATH
        # (tmp_dir.parent) - a bare tempfile.mkdtemp() puts tmp_dir
        # directly under the shared OS temp root, meaning tmp_dir.parent
        # would be that SAME shared root for every test in the whole
        # suite, and all three would silently collide across tests (and
        # across any other tool/script's temp usage). An isolated parent
        # directory, with tmp_dir as ITS OWN child, keeps all three
        # exclusively scoped to this one test.
        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_p40e2a_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e2a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="p40e2a_viewer", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.add(User(username="p40e2a_outsider", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()

        self.doc = self._ingest(owner="p40e2a_owner", project_name="Riverside P40E2A Workspace")
        self.project_id = self.doc.project_id

    def tearDown(self):
        # self.tmp_root exclusively owns tmp_dir (the registry itself)
        # AND registry_snapshots/reset_transactions/the lock file - one
        # rmtree cleans up everything this test could possibly have
        # created, with nothing left behind for a later test to collide
        # with.
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
        return self._store().get(self.project_id).sources[0]["id"]


# ---------------------------------------------------------------------------
# Section A: removed-Project containment
# ---------------------------------------------------------------------------

class RemovedProjectContainmentTests(_BaseTestCase):
    def _remove_project(self, client):
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

    def test_show_workspace_renders_tombstone_not_active_workspace(self):
        client = self._client_as("p40e2a_owner", 1)
        self._remove_project(client)

        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Project removed", body)
        self.assertIn("Restore Project", body)
        # the active Workspace's own distinctive content must not render -
        # BUCKET-B FIX (CLAUDE-P40-E3A): base.html's Toolbox/Chat shell
        # containers were gated on bare "project_id is defined", which
        # project_removed.html also sets - narrowed to "project_id is
        # defined and workspace is defined" (project_removed.html never
        # passes workspace) so the containers themselves are absent here
        # too, matching Section 12's "removed-state containment". Checked
        # against the actual container tag, not a bare substring - the
        # appearance-menu script's own querySelector('.workspace-pane-
        # toolbox') is harmless unconditional JS, not a containment leak.
        self.assertNotIn('id="workspace-toolbox-panel"', body)
        self.assertNotIn('id="chat-region"', body)
        self.assertNotIn("Sources (", body)

    def test_chat_posting_blocked(self):
        client = self._client_as("p40e2a_owner", 1)
        self._remove_project(client)

        workspace = self._store().get(self.project_id)
        client.post(f"/projects/{self.project_id}/workspace/quick-start", data={"text": "hello"})
        after = self._store().get(self.project_id)
        self.assertEqual(len(after.project_conversation), len(workspace.project_conversation))

    def test_investigation_creation_blocked(self):
        client = self._client_as("p40e2a_owner", 1)
        self._remove_project(client)

        resp = client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Should not exist", "objective": ""})
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.cases, [])

    def test_document_add_blocked(self):
        client = self._client_as("p40e2a_owner", 1)
        self._remove_project(client)

        before_count = len(self._store().get(self.project_id).sources)
        client.post(
            f"/projects/{self.project_id}/workspace/sources/text-record",
            data={"title": "Should not be added", "content": "x"},
        )
        after_count = len(self._store().get(self.project_id).sources)
        self.assertEqual(before_count, after_count)

    def test_document_level_remove_restore_blocked_while_project_removed(self):
        client = self._client_as("p40e2a_owner", 1)
        source_id = self._first_source_id()
        self._remove_project(client)

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})
        source = self._store().get(self.project_id).sources[0]
        self.assertIsNone(source.get("removed_at"))

    def test_authorized_owner_gets_tombstone_unauthorized_outsider_gets_404(self):
        owner_client = self._client_as("p40e2a_owner", 1)
        self._remove_project(owner_client)

        owner_resp = owner_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(owner_resp.status_code, 200)
        self.assertIn(b"Project removed", owner_resp.data)

        outsider_client = self._client_as("p40e2a_outsider", 3, role="read_only")
        outsider_resp = outsider_client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(outsider_resp.status_code, 404)
        self.assertNotIn(self.doc.filename.encode(), outsider_resp.data)

    def test_restore_project_route_itself_still_reachable(self):
        client = self._client_as("p40e2a_owner", 1)
        self._remove_project(client)

        resp = client.post(f"/projects/{self.project_id}/workspace/restore")
        self.assertEqual(resp.status_code, 302)
        self.assertIsNone(self._store().get(self.project_id).removed_at)

        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertNotIn("<title>Project removed", body)
        self.assertIn("workspace-pane-toolbox", body)

    def test_restore_returns_the_complete_bundle_unchanged(self):
        client = self._client_as("p40e2a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        case_id = self._store().get(self.project_id).cases[0]["id"]

        self._remove_project(client)
        client.post(f"/projects/{self.project_id}/workspace/restore")

        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.project_id, self.project_id)
        self.assertEqual(len(workspace.cases), 1)
        self.assertEqual(workspace.cases[0]["id"], case_id)
        self.assertEqual(len(workspace.sources), 1)


# ---------------------------------------------------------------------------
# Section A: removed-Document containment
# ---------------------------------------------------------------------------

class RemovedDocumentContainmentTests(_BaseTestCase):
    def test_document_viewer_shows_tombstone_not_content(self):
        client = self._client_as("p40e2a_owner", 1)
        source_id = self._first_source_id()
        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})

        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        self.assertIn("This Document has been removed", body)
        self.assertIn("Restore Document", body)
        self.assertNotIn("document-viewer-frame", body)
        self.assertNotIn("document-viewer-image", body)

    def test_source_file_route_refuses_to_serve_removed_document(self):
        client = self._client_as("p40e2a_owner", 1)
        source_id = self._first_source_id()

        # give it a real on-disk file first, so a 404 can only be
        # attributed to the removed-state guard, not "file never existed"
        workspace = self._store().get(self.project_id)
        real_file = self.tmp_dir / "real_upload.txt"
        real_file.write_bytes(b"the real content")
        workspace.sources[0]["file_path"] = str(real_file)
        self._store().save(workspace)

        before = client.get(f"/projects/{self.project_id}/workspace/sources/{source_id}/file")
        self.assertEqual(before.status_code, 200)

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})
        during = client.get(f"/projects/{self.project_id}/workspace/sources/{source_id}/file")
        self.assertEqual(during.status_code, 404)

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/restore")
        after = client.get(f"/projects/{self.project_id}/workspace/sources/{source_id}/file")
        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.data, b"the real content")

    def test_restore_returns_same_id_and_content(self):
        client = self._client_as("p40e2a_owner", 1)
        source_id = self._first_source_id()
        original = dict(self._store().get(self.project_id).sources[0])

        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})
        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/restore")

        restored = self._store().get(self.project_id).sources[0]
        self.assertEqual(restored["id"], original["id"])
        self.assertEqual(restored["name"], original["name"])
        self.assertEqual(restored["kind"], original["kind"])
        self.assertIsNone(restored.get("removed_at"))

    def test_new_requirement_registration_against_removed_source_blocked(self):
        client = self._client_as("p40e2a_owner", 1)
        source_id = self._first_source_id()
        client.post(f"/projects/{self.project_id}/workspace/sources/{source_id}/remove", data={"confirm": "yes"})

        resp = client.post(
            f"/projects/{self.project_id}/workspace/requirements/register",
            data={
                "source_id": source_id,
                "original_requirement_identifier": "X-1",
                "text_reference": "Some clause",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self._store().get(self.project_id).requirements, [])

    def test_existing_dependent_reference_still_resolves_removed_source_honestly(self):
        store = self._store()
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="X-1",
            text_reference="Some clause", created_by="p40e2a_owner", registration_method="human_registered",
        )
        store.remove_source(workspace, source_id=source_id, actor="p40e2a_owner", actor_role="admin")

        client = self._client_as("p40e2a_owner", 1)
        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements render on their own
        # page now, not Overview.
        body = client.get(f"/projects/{self.project_id}/workspace?view=requirements").get_data(as_text=True)
        # the pre-existing Requirement citing the removed Source must
        # still be present and renderable, not silently dropped/broken
        self.assertIn("Some clause", body)


# ---------------------------------------------------------------------------
# Removed content absent from lists/counts/search/AI context
# ---------------------------------------------------------------------------

class RemovedContentAbsentFromActiveSurfacesTests(_BaseTestCase):
    def test_removed_project_absent_from_search(self):
        client = self._client_as("p40e2a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/remove", data={"confirm": "yes"})

        resp = client.get(f"/search?q={self.doc.filename}")
        data = resp.get_json()
        self.assertEqual(data["results"], [])

    def test_removed_drawing_source_excluded_from_analyze_ai_context(self):
        store = self._store()
        workspace = store.get(self.project_id)
        workspace.sources.append({
            "id": "drawing-1", "project_id": self.project_id, "kind": "drawing",
            "name": "plan.png", "added_at": "2026-01-01T00:00:00+00:00", "file_path": None,
        })
        store.save(workspace)

        client = self._client_as("p40e2a_owner", 1)
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        workspace = store.get(self.project_id)
        case_id = workspace.cases[0]["id"]
        workspace.cases[0]["source_ids"] = ["drawing-1"]
        store.save(workspace)

        store.remove_source(workspace, source_id="drawing-1", actor="p40e2a_owner", actor_role="admin")

        resp = client.post(
            f"/projects/{self.project_id}/workspace/cases/{case_id}/messages",
            data={"text": "Analyze this drawing for datum inconsistencies"},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = store.get(self.project_id)
        last_message = workspace.cases[0]["conversation"][-1]
        self.assertIn("no drawing Source", last_message["text"])


# ---------------------------------------------------------------------------
# Section B: reset-snapshot restoration
# ---------------------------------------------------------------------------

class ResetSnapshotRestorationTests(_BaseTestCase):
    def _admin_client(self):
        return self._client_as("p40e2a_owner", 1, role="admin")

    def _do_reset(self, client):
        return client.post("/admin/reset-project-data", data={"confirmation_phrase": "RESET PROJECT DATA"})

    def _latest_snapshot_id(self):
        # Scoped by actor AND by actually containing this test's own
        # project record - registry_snapshots/ lives in the shared OS
        # temp root, so other tests' snapshots (same actor username,
        # different project_id) can otherwise be newer and get picked
        # up here by mistake. A "reset" snapshot of THIS project always
        # contains "<project_id>.json" among its checksums; a later
        # "pre_restore_safety" snapshot of the already-reset (empty)
        # store correctly does NOT, and is excluded here.
        snapshot_root = self.tmp_dir.parent / "registry_snapshots"
        candidates = []
        for d in snapshot_root.iterdir():
            manifest_path = d / "_snapshot_manifest.snapshot"
            if not d.is_dir() or not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("actor") != "p40e2a_owner":
                continue
            if f"{self.project_id}.json" not in manifest.get("checksums", {}):
                continue
            candidates.append(d)
        candidates.sort(key=lambda d: (d / "_snapshot_manifest.snapshot").stat().st_mtime)
        return candidates[-1].name

    def test_reset_creates_a_complete_checksummed_snapshot(self):
        client = self._admin_client()
        self._do_reset(client)

        snapshot_id = self._latest_snapshot_id()
        snapshot_dir = self.tmp_dir.parent / "registry_snapshots" / snapshot_id
        manifest = json.loads((snapshot_dir / "_snapshot_manifest.snapshot").read_text(encoding="utf-8"))

        self.assertEqual(manifest["kind"], "reset")
        self.assertEqual(manifest["actor"], "p40e2a_owner")
        self.assertGreater(manifest["file_count"], 0)
        self.assertTrue((snapshot_dir / f"{self.project_id}.json").exists())
        # every recorded checksum matches the real file right now
        import hashlib
        for rel_path, expected in manifest["checksums"].items():
            actual = hashlib.sha256((snapshot_dir / rel_path).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, rel_path)

    def test_snapshot_appears_in_listing(self):
        client = self._admin_client()
        self._do_reset(client)

        body = client.get("/admin/reset-project-data/snapshots").get_data(as_text=True)
        self.assertIn("reset", body)
        self.assertIn("p40e2a_owner", body)
        self.assertIn("1 Project(s)", body)

    def test_restore_recovers_byte_equivalent_records_and_relationships(self):
        client = self._admin_client()
        client.post(f"/projects/{self.project_id}/workspace/cases", data={"title": "Drawing Review", "objective": ""})
        original_workspace_json = (self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8")
        original_registry_json = (self.tmp_dir / f"{self.project_id}.json").read_text(encoding="utf-8")

        self._do_reset(client)
        self.assertIsNone(self._store().get(self.project_id))

        snapshot_id = self._latest_snapshot_id()
        preview = client.get(f"/admin/reset-project-data/snapshots/{snapshot_id}/restore").get_data(as_text=True)
        self.assertIn("Verified", preview)
        self.assertIn("1 Project(s)", preview)

        resp = client.post(
            f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"}, follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)

        restored_workspace = self._store().get(self.project_id)
        self.assertIsNotNone(restored_workspace)
        self.assertEqual(len(restored_workspace.cases), 1)
        self.assertEqual(restored_workspace.cases[0]["title"], "Drawing Review")

        self.assertEqual(
            (self.tmp_dir / f"{self.project_id}.workspace.json").read_text(encoding="utf-8"),
            original_workspace_json,
        )
        self.assertEqual(
            (self.tmp_dir / f"{self.project_id}.json").read_text(encoding="utf-8"),
            original_registry_json,
        )

    def test_restore_takes_its_own_safety_snapshot_of_pre_restore_state(self):
        client = self._admin_client()
        self._do_reset(client)
        reset_snapshot_id = self._latest_snapshot_id()

        # Reset already returned to a clean state - restoring now
        # should snapshot THAT clean state as a safety copy first.
        before_snapshot_count = len(list((self.tmp_dir.parent / "registry_snapshots").iterdir()))
        client.post(
            f"/admin/reset-project-data/snapshots/{reset_snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"},
        )
        after_snapshot_count = len(list((self.tmp_dir.parent / "registry_snapshots").iterdir()))
        self.assertEqual(after_snapshot_count, before_snapshot_count + 1)

        body = client.get("/admin/reset-project-data/snapshots").get_data(as_text=True)
        self.assertIn("pre_restore_safety", body)

    def test_corrupted_snapshot_fails_integrity_check_and_is_refused(self):
        client = self._admin_client()
        self._do_reset(client)
        snapshot_id = self._latest_snapshot_id()
        snapshot_dir = self.tmp_dir.parent / "registry_snapshots" / snapshot_id

        # corrupt the snapshot's own copy of the project record after
        # the manifest already recorded its real checksum
        (snapshot_dir / f"{self.project_id}.json").write_text('{"tampered": true}', encoding="utf-8")

        preview = client.get(f"/admin/reset-project-data/snapshots/{snapshot_id}/restore").get_data(as_text=True)
        self.assertIn("Integrity check failed", preview)
        self.assertNotIn(">Restore this Snapshot<", preview)

        resp = client.post(
            f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"},
        )
        # nothing restored - the live store is still the clean post-reset state
        self.assertIsNone(self._store().get(self.project_id))
        self.assertEqual(resp.status_code, 302)

    def test_duplicate_restore_submission_rejected_by_shared_lock(self):
        client = self._admin_client()
        self._do_reset(client)
        snapshot_id = self._latest_snapshot_id()

        # CLAUDE-P40-E2A2: a lock only blocks when the PID recorded in
        # it is genuinely still running (Section C) - this test's own
        # (alive) PID simulates a real concurrent holder, not an
        # abandoned one that automatic recovery would clear instead.
        import os as _os
        lock_path = self.tmp_dir.parent / ".reset_project_data.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(str(_os.getpid()), encoding="ascii")
        try:
            client.post(
                f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
                data={"confirmation_phrase": "RESTORE SNAPSHOT"},
            )
            # nothing restored while the lock was held
            self.assertIsNone(self._store().get(self.project_id))
        finally:
            lock_path.unlink(missing_ok=True)

    def test_restore_leaves_no_partial_registry_when_snapshot_is_bad(self):
        """A failed restore (bad snapshot) must not leave the live
        store touched at all - not even partially wiped."""
        client = self._admin_client()
        self._do_reset(client)
        snapshot_id = self._latest_snapshot_id()
        snapshot_dir = self.tmp_dir.parent / "registry_snapshots" / snapshot_id
        (snapshot_dir / f"{self.project_id}.json").write_text('{"tampered": true}', encoding="utf-8")

        live_files_before = sorted(p.name for p in self.tmp_dir.iterdir())
        client.post(
            f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"},
        )
        live_files_after = sorted(p.name for p in self.tmp_dir.iterdir())
        self.assertEqual(live_files_before, live_files_after)

    def test_restore_preserves_accounts_and_current_security_governance(self):
        from models import User

        client = self._admin_client()
        # Give security_governance/ some live state to prove it survives
        # restore untouched (never reverted to the snapshot's old copy).
        sec_dir = self.tmp_dir / "security_governance"
        sec_dir.mkdir(parents=True, exist_ok=True)
        (sec_dir / "reset_audit.jsonl").write_text('{"marker": "pre-restore-live-state"}\n', encoding="utf-8")

        self._do_reset(client)
        snapshot_id = self._latest_snapshot_id()
        client.post(
            f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"},
        )

        with self.flask_app.app_context():
            self.assertIsNotNone(User.query.filter_by(username="p40e2a_owner").first())

        audit_text = (self.tmp_dir / "security_governance" / "reset_audit.jsonl").read_text(encoding="utf-8")
        self.assertIn("pre-restore-live-state", audit_text)
        self.assertIn("snapshot_restored", audit_text)

    def test_non_admin_cannot_list_or_restore_snapshots(self):
        client = self._client_as("p40e2a_viewer", 2, role="read_only")
        self.assertNotEqual(client.get("/admin/reset-project-data/snapshots").status_code, 200)
        self.assertNotEqual(client.get("/admin/reset-project-data/snapshots/anything/restore").status_code, 200)

    def test_snapshot_id_path_traversal_rejected(self):
        client = self._admin_client()
        resp = client.get("/admin/reset-project-data/snapshots/..%2F..%2Fetc/restore")
        self.assertEqual(resp.status_code, 404)

    def test_reset_and_restore_succeed_past_windows_max_path(self):
        """
        CLAUDE-P40-E2A1: a real, LIVE isolated-process run of Reset
        Project Data (a completely separate Flask process against a
        temporary isolated registry, driven over real HTTP - not this
        pytest suite) hit a real shutil.Error([WinError 3]) the moment a
        snapshot's own extra directory level (registry_snapshots/
        <stamp>/) pushed an already-long workspace_sources/<project_id>/
        <filename> path past Windows' classic 260-character MAX_PATH -
        not an artifact of that verification's own temp path (its
        SHORTER, un-nested original file wrote and read back fine at
        seed time). Reproduced here deterministically: a filename length
        computed so the ORIGINAL Source path stays under 260 chars
        (ingestion/display must keep working normally) while the SAME
        path, nested one level deeper the way a snapshot always is,
        exceeds it (proving the bug this test targets, not some other
        failure) - both bounds computed from this test's own actual temp
        directory length, not hardcoded, so the test stays meaningful
        regardless of where the OS puts its temp folder.
        """
        store = self._store()
        workspace = store.get(self.project_id)
        project_id = self.project_id

        sources_dir = self.tmp_dir / "workspace_sources" / project_id
        sources_dir.mkdir(parents=True, exist_ok=True)

        # Aim the original path at ~250 chars (comfortably under 260)
        # and let the snapshot's own extra ~50+ chars of nesting
        # (registry_snapshots/<~40-char stamp>/) push it over.
        base_len = len(str(sources_dir)) + 1  # +1 for the path separator before the filename
        filename_len = max(20, 250 - base_len)
        long_name = ("a" * filename_len) + ".txt"
        target = sources_dir / long_name
        original_path_len = len(str(target))
        self.assertLess(original_path_len, 260, "test setup itself would exceed MAX_PATH - not what this test targets")
        target.write_bytes(b"long path content")
        from routes.portal import _sha256_of, _win_long_path
        original_checksum = _sha256_of(target)

        workspace.sources.append({
            "id": "long-path-source", "project_id": project_id, "kind": "rfq_rfp_document",
            "name": long_name, "added_at": "2026-01-01T00:00:00+00:00", "file_path": str(target),
        })
        store.save(workspace)

        client = self._admin_client()
        reset_resp = client.post("/admin/reset-project-data", data={"confirmation_phrase": "RESET PROJECT DATA"})
        self.assertEqual(reset_resp.status_code, 302)
        self.assertIsNone(self._store().get(project_id), "reset must succeed even with a long-path Source")

        # Plain pathlib .exists()/.read_bytes() are themselves subject to
        # the exact same >260-char MAX_PATH limitation this test targets
        # (confirmed live - the whole reason routes/portal.py's
        # _win_long_path helper exists), so verifying the snapshot's own
        # copy has to go through that same long-path-safe open, not a
        # plain pathlib call that would give a false negative here.
        snapshot_id = self._latest_snapshot_id()
        snapshot_dir = self.tmp_dir.parent / "registry_snapshots" / snapshot_id
        restored_file = snapshot_dir / "workspace_sources" / project_id / long_name
        self.assertGreater(len(str(restored_file)), 260, "test setup did not actually exercise the >260-char case")
        with open(_win_long_path(restored_file), "rb") as fh:
            self.assertEqual(fh.read(), b"long path content")
        self.assertEqual(
            _sha256_of(restored_file), original_checksum,
            "snapshot's copy of the long-path file must match the original byte-for-byte",
        )

        restore_resp = client.post(
            f"/admin/reset-project-data/snapshots/{snapshot_id}/restore",
            data={"confirmation_phrase": "RESTORE SNAPSHOT"},
        )
        self.assertEqual(restore_resp.status_code, 302)

        restored_workspace = self._store().get(project_id)
        self.assertIsNotNone(restored_workspace)
        restored_source = next(s for s in restored_workspace.sources if s["id"] == "long-path-source")
        self.assertEqual(Path(restored_source["file_path"]).read_bytes(), b"long path content")


if __name__ == "__main__":
    unittest.main()
