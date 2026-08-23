"""CLAUDE-REMOVED-API-01 - removal suspends ordinary project-data access.

An audit found that routes/api.py's central loader,
``_load_authorized_project_or_404``, checked authentication and project
membership but never ``workspace.removed_at``. routes/workspace.py's own
``_load_workspace_or_404`` has blocked removed state for the HTML surface
since CLAUDE-P40-E2A; the JSON API simply never grew the equivalent check.
The consequence was that a formerly authorized non-admin could keep reading
retained project state - requirements, evidence, governance history,
relationships, structural units - after the project was removed.

The policy these tests hold:

    Removal suspends ordinary project-data access.
    Recovery authority does not preserve evidence-reading authority.

Four actors, each asserted after removal:

    A. admin                    - retains governed access; restore works
    B. non-admin owner          - loses ordinary data reads; keeps recovery
    C. former authorized member - loses everything, including the tombstone
    D. never-authorized user    - unchanged, fail-closed, non-disclosing

Plus a restore round trip proving removal is reversible state and not a
destructive migration: the same project id, sources, requirements and
governance history come back.

Every ingestion call spies on BHiveParser.parse rather than letting it run
for real (repo-wide convention - no external boundary is reachable here).
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
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

# Substantive project-data reads that all go through the corrected central
# loader. These are asserted as a set rather than one representative route,
# because the whole point of the repair is that the boundary is central.
SUBSTANTIVE_READS = (
    "",                     # project/document detail
    "/requirements",
    "/milestones",
    "/consistency",
    "/governance",
    "/structural-units",
    "/evidence",
    "/relationships",
)

UNKNOWN_PROJECT_ID = "00000000-0000-4000-8000-000000000000"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _RemovedProjectBoundaryCase(unittest.TestCase):
    """One project, removed, seen through four different sets of eyes."""

    def setUp(self):
        import app as app_module
        from models import User, db

        # Isolated parent so registry_snapshots/, reset_transactions/ and the
        # lock file (all siblings of REGISTRY_STORE_PATH) cannot collide with
        # other tests - same reasoning as tests/test_p40e2_toolbox_and_removal.py.
        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_rmapi_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            for name, role in (
                ("rm_admin", "admin"),
                ("rm_owner", "read_only"),
                ("rm_member", "read_only"),
                ("rm_outsider", "read_only"),
            ):
                db.session.add(User(
                    username=name, password_hash=generate_password_hash("x"), role=role,
                ))
            db.session.commit()

        self.doc = self._ingest(owner="rm_owner", project_name="Riverside Removal Boundary")
        self.project_id = self.doc.project_id

        # The former authorized non-owner: a real allow-list member.
        store = self._store()
        workspace = store.get(self.project_id)
        store.grant_project_access(
            workspace, username="rm_member", actor="rm_owner", actor_role="admin",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    # -- fixtures ---------------------------------------------------------

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

    def _client(self, username, role="read_only"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = username
            sess["role"] = role
        return client

    def _admin(self):
        return self._client("rm_admin", role="admin")

    def _remove_project(self):
        store = self._store()
        workspace = store.get(self.project_id)
        from services.governance import GovernanceLog

        with self.flask_app.app_context():
            store.remove_project(
                workspace, actor="rm_owner", actor_role="read_only",
                governance_log=GovernanceLog(self.flask_app.config["REGISTRY_STORE_PATH"]),
            )

    def _listing(self, client):
        response = client.get("/api/v1/documents")
        self.assertEqual(response.status_code, 200)
        return response.get_json()["project_ids"]

    def _assert_substantive_reads_denied(self, client, actor):
        for suffix in SUBSTANTIVE_READS:
            with self.subTest(actor=actor, route=suffix or "/detail"):
                response = client.get(f"/api/v1/documents/{self.project_id}{suffix}")
                self.assertEqual(
                    response.status_code, 404,
                    f"{actor} must not read a removed project through {suffix or 'detail'}",
                )


class ActorAdminTests(_RemovedProjectBoundaryCase):
    """A. Admin retains governed access required for administration/recovery."""

    def test_admin_still_reads_a_removed_project(self):
        self._remove_project()
        client = self._admin()
        for suffix in SUBSTANTIVE_READS:
            with self.subTest(route=suffix or "/detail"):
                response = client.get(f"/api/v1/documents/{self.project_id}{suffix}")
                self.assertNotEqual(
                    response.status_code, 404,
                    "the intentional admin bypass must be preserved",
                )

    def test_admin_listing_behaviour_is_unchanged(self):
        self._remove_project()
        self.assertIn(self.project_id, self._listing(self._admin()))

    def test_owner_and_admin_keep_the_direct_tombstone(self):
        """Narrowing disclosure must not break the recovery path itself."""
        self._remove_project()
        for username, role in (("rm_owner", "read_only"), ("rm_admin", "admin")):
            with self.subTest(actor=username):
                response = self._client(username, role=role).get(
                    f"/projects/{self.project_id}/workspace?view=overview")
                self.assertEqual(response.status_code, 200)

    def test_admin_sees_the_tombstone_and_can_restore(self):
        self._remove_project()
        client = self._admin()
        self.assertIn(self.project_id, client.get("/removed-projects").get_data(as_text=True))
        client.post(f"/projects/{self.project_id}/workspace/restore")
        self.assertIsNone(self._store().get(self.project_id).removed_at)


class ActorNonAdminOwnerTests(_RemovedProjectBoundaryCase):
    """B. The owner keeps recovery authority, and loses reading authority."""

    def test_removed_project_leaves_the_ordinary_api_listing(self):
        client = self._client("rm_owner")
        self.assertIn(self.project_id, self._listing(client))
        self._remove_project()
        self.assertNotIn(self.project_id, self._listing(client))

    def test_owner_cannot_read_removed_project_data(self):
        """Recovery authority is not evidence-reading authority."""
        self._remove_project()
        self._assert_substantive_reads_denied(self._client("rm_owner"), "owner")

    def test_owner_keeps_the_minimal_recovery_surface(self):
        self._remove_project()
        body = self._client("rm_owner").get("/removed-projects").get_data(as_text=True)
        self.assertIn(self.project_id, body)

    def test_owner_can_still_restore(self):
        self._remove_project()
        self._client("rm_owner").post(f"/projects/{self.project_id}/workspace/restore")
        self.assertIsNone(self._store().get(self.project_id).removed_at)

    def test_ordinary_access_returns_after_restore(self):
        self._remove_project()
        client = self._client("rm_owner")
        self.assertEqual(client.get(f"/api/v1/documents/{self.project_id}").status_code, 404)

        client.post(f"/projects/{self.project_id}/workspace/restore")

        self.assertIn(self.project_id, self._listing(client))
        self.assertEqual(client.get(f"/api/v1/documents/{self.project_id}").status_code, 200)


class ActorFormerMemberTests(_RemovedProjectBoundaryCase):
    """C. A former authorized non-owner loses ordinary access entirely."""

    def test_absent_from_the_ordinary_listing(self):
        client = self._client("rm_member")
        self.assertIn(self.project_id, self._listing(client))
        self._remove_project()
        self.assertNotIn(self.project_id, self._listing(client))

    def test_direct_known_uuid_access_is_denied(self):
        self._remove_project()
        self._assert_substantive_reads_denied(self._client("rm_member"), "former member")

    def test_absent_from_the_recovery_surface(self):
        """Membership is not recovery authority, so the tombstone -- and the
        removal timestamp, remover and project name it carries -- is not
        theirs to see."""
        self._remove_project()
        body = self._client("rm_member").get("/removed-projects").get_data(as_text=True)
        self.assertNotIn(self.project_id, body)

    def test_restore_is_denied(self):
        self._remove_project()
        self._client("rm_member").post(f"/projects/{self.project_id}/workspace/restore")
        self.assertIsNotNone(
            self._store().get(self.project_id).removed_at,
            "a former member must not be able to restore",
        )

    def test_direct_tombstone_url_is_not_a_bypass_of_the_listing(self):
        """Narrowing only /removed-projects would leave the same metadata --
        name, removal timestamp, remover, reason -- one URL away."""
        self._remove_project()
        response = self._client("rm_member").get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 404)
        body = response.get_data(as_text=True)
        self.assertNotIn("Riverside Removal Boundary", body)
        self.assertNotIn("rm_owner", body)

    def test_store_layer_refuses_the_restore_independently(self):
        """Defence in depth: the route is not the only thing saying no."""
        self._remove_project()
        store = self._store()
        with self.assertRaises(CaseWorkspaceError):
            with self.flask_app.app_context():
                from services.governance import GovernanceLog

                store.restore_project(
                    store.get(self.project_id), actor="rm_member", actor_role="read_only",
                    governance_log=GovernanceLog(self.flask_app.config["REGISTRY_STORE_PATH"]),
                )


class ActorNeverAuthorizedTests(_RemovedProjectBoundaryCase):
    """D. Behaviour is unchanged: fail-closed and non-disclosing."""

    def test_listing_never_contained_it(self):
        client = self._client("rm_outsider")
        self.assertNotIn(self.project_id, self._listing(client))
        self._remove_project()
        self.assertNotIn(self.project_id, self._listing(client))

    def test_direct_uuid_denied_before_and_after_removal(self):
        client = self._client("rm_outsider")
        self._assert_substantive_reads_denied(client, "outsider (active)")
        self._remove_project()
        self._assert_substantive_reads_denied(client, "outsider (removed)")

    def test_removed_project_is_indistinguishable_from_an_unknown_one(self):
        """The response class must not disclose that the project exists."""
        self._remove_project()
        for username in ("rm_outsider", "rm_member"):
            client = self._client(username)
            removed = client.get(f"/api/v1/documents/{self.project_id}")
            unknown = client.get(f"/api/v1/documents/{UNKNOWN_PROJECT_ID}")
            with self.subTest(actor=username):
                self.assertEqual(removed.status_code, unknown.status_code)
                self.assertEqual(removed.get_data(), unknown.get_data())

    def test_restore_is_denied(self):
        self._remove_project()
        self._client("rm_outsider").post(f"/projects/{self.project_id}/workspace/restore")
        self.assertIsNotNone(self._store().get(self.project_id).removed_at)


class RestoreRoundTripTests(_RemovedProjectBoundaryCase):
    """Removal is reversible state, not a destructive migration."""

    def _snapshot(self):
        workspace = self._store().get(self.project_id)
        from services.governance import GovernanceLog

        with self.flask_app.app_context():
            events = GovernanceLog(self.flask_app.config["REGISTRY_STORE_PATH"]).read(self.project_id)
        return {
            "project_id": workspace.project_id,
            "sources": [s.get("id") for s in workspace.sources],
            "requirements": len(workspace.requirements),
            "cases": len(workspace.cases),
            "findings": len(workspace.findings),
            "relationships": len(workspace.relationships),
            "governance_events": len(events),
        }

    def test_active_removed_restored_preserves_the_same_project(self):
        before = self._snapshot()
        self.assertTrue(before["sources"], "fixture must have at least one Source")

        self._remove_project()
        owner = self._client("rm_owner")
        self.assertEqual(owner.get(f"/api/v1/documents/{self.project_id}").status_code, 404)

        owner.post(f"/projects/{self.project_id}/workspace/restore")
        after = self._snapshot()

        self.assertEqual(after["project_id"], before["project_id"], "same project, never a clone")
        self.assertEqual(after["sources"], before["sources"])
        for key in ("requirements", "cases", "findings", "relationships"):
            with self.subTest(preserved=key):
                self.assertEqual(after[key], before[key])
        # Governance history only ever grows - removal and restoration are
        # themselves recorded events, never a rewrite of what came before.
        self.assertGreaterEqual(after["governance_events"], before["governance_events"])

    def test_nothing_was_physically_deleted_while_removed(self):
        before = self._snapshot()
        self._remove_project()
        during = self._snapshot()
        self.assertEqual(during["sources"], before["sources"])
        self.assertEqual(during["requirements"], before["requirements"])


if __name__ == "__main__":
    unittest.main()
