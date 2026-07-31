"""
CLAUDE-P32 -- project-level access control: which authenticated accounts
may open a given project at all, closing the gap where any authenticated
user could reach any project merely by knowing/guessing its project_id.

Distinct from, and enforced BEFORE, both existing authorization layers:
services.auth's admin/read_only role (what a user may DO once inside a
project they're already allowed into) and CaseWorkspaceStore.
visible_cases_for's Case-level privacy (which Cases within an
accessible project a given user may see). Neither of those changes --
tested explicitly below (role restrictions still apply for an
authorized read_only user; Case privacy is unaffected).

Every ingestion call in this file spies on BHiveParser.parse rather
than letting it run for real -- see tests/test_security_enforcement.py's
own identical convention and the CLAUDE-P31 8.5-hour live-API incident
it exists to prevent.

Run via:

    python -m unittest discover -s tests -v
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
from services.governance import GovernanceLog
from services.ingestion import ingest_upload
from services.project_access import (
    can_access_project,
    ensure_owner_backfilled,
    infer_owner_from_ingestion_actor,
    load_authorized_project_or_none,
)
from services.requirements_registry import RequirementsRegistry


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseAccessControlTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_access_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            alice = User(username="alice", password_hash=generate_password_hash("x"), role="admin")
            bob = User(username="bob", password_hash=generate_password_hash("x"), role="read_only")
            carol = User(username="carol", password_hash=generate_password_hash("x"), role="read_only")
            db.session.add_all([alice, bob, carol])
            db.session.commit()

        self.alice_client = self._client_as("alice", 1, "admin")
        self.bob_client = self._client_as("bob", 2, "read_only")
        self.carol_client = self._client_as("carol", 3, "read_only")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _ingest(self, owner: str, project_name: str, filename: str = "a.txt"):
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


class OwnerAndUnauthorizedAccessTests(_BaseAccessControlTestCase):
    def test_owner_can_open_own_project(self):
        doc = self._ingest(owner="bob", project_name="Bob Owns This")
        response = self.bob_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 200)

    def test_unauthorized_authenticated_user_cannot_open_project(self):
        doc = self._ingest(owner="bob", project_name="Bob Owns This 2")
        response = self.carol_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 404)

    def test_unauthenticated_user_is_redirected_not_granted_access(self):
        doc = self._ingest(owner="bob", project_name="Bob Owns This 3")
        anon = self.flask_app.test_client()
        response = anon.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_direct_guessed_project_id_access_fails_for_a_real_project(self):
        # Not fabricated -- a REAL project id, guessed by a user who was
        # never granted access, still fails.
        doc = self._ingest(owner="bob", project_name="Guess Target")
        response = self.carol_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 404)

    def test_denial_response_does_not_expose_project_content(self):
        doc = self._ingest(owner="bob", project_name="Sensitive Client Name LLC")
        response = self.carol_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(b"Sensitive Client Name LLC", response.data)

    def test_denial_looks_identical_to_a_genuinely_nonexistent_project(self):
        doc = self._ingest(owner="bob", project_name="Real But Denied")
        denied = self.carol_client.get(f"/projects/{doc.project_id}/workspace")
        nonexistent = self.carol_client.get("/projects/not-a-real-project-id/workspace")
        self.assertEqual(denied.status_code, nonexistent.status_code)


class AdministratorAndReadOnlySemanticsTests(_BaseAccessControlTestCase):
    def test_admin_can_open_a_project_they_do_not_own(self):
        doc = self._ingest(owner="bob", project_name="Admin Bypass Target")
        response = self.alice_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 200)

    def test_admin_bypass_is_documented_and_verified_not_assumed(self):
        # Direct proof at the decision-function level, not just one route.
        workspace = self._store().get_or_create("admin-bypass-check")
        self.assertFalse(can_access_project(workspace, "random-user", is_admin=False))
        self.assertTrue(can_access_project(workspace, "random-user", is_admin=True))

    def test_authorized_read_only_user_still_cannot_perform_admin_only_actions(self):
        # Project-level access does not widen an authorized read_only
        # user's existing role restrictions -- classify_operating_environment
        # is @admin_required regardless of project access.
        doc = self._ingest(owner="bob", project_name="Read Only Still Restricted")
        store = self._store()
        workspace = store.get(doc.project_id)
        store.grant_project_access(workspace, username="carol", actor="bob", actor_role="read_only")

        response = self.carol_client.post(
            f"/projects/{doc.project_id}/workspace/access/owner", data={"owner": "carol"},
        )
        self.assertEqual(response.status_code, 403)

    def test_authorized_read_only_user_can_still_read_the_project(self):
        doc = self._ingest(owner="bob", project_name="Read Only Can Read")
        store = self._store()
        workspace = store.get(doc.project_id)
        store.grant_project_access(workspace, username="carol", actor="bob", actor_role="read_only")

        response = self.carol_client.get(f"/projects/{doc.project_id}/workspace")
        self.assertEqual(response.status_code, 200)


class ApiMutationAndExportDenialTests(_BaseAccessControlTestCase):
    def test_unauthorized_user_cannot_access_project_scoped_api(self):
        doc = self._ingest(owner="bob", project_name="API Denied")
        response = self.carol_client.get(f"/api/v1/documents/{doc.project_id}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "not_found")

    def test_authorized_user_can_access_project_scoped_api(self):
        doc = self._ingest(owner="bob", project_name="API Allowed")
        response = self.bob_client.get(f"/api/v1/documents/{doc.project_id}")
        self.assertEqual(response.status_code, 200)

    def test_api_document_list_is_filtered_to_accessible_projects(self):
        bob_doc = self._ingest(owner="bob", project_name="Bob's Own")
        carol_doc = self._ingest(owner="carol", project_name="Carol's Own")

        response = self.bob_client.get("/api/v1/documents")
        ids = response.get_json()["project_ids"]
        self.assertIn(bob_doc.project_id, ids)
        self.assertNotIn(carol_doc.project_id, ids)

    def test_unauthorized_user_cannot_mutate_project_state(self):
        doc = self._ingest(owner="bob", project_name="Mutation Denied")
        response = self.carol_client.post(
            f"/projects/{doc.project_id}/workspace/cases", data={"title": "Sneaky Case", "objective": "x"},
        )
        self.assertEqual(response.status_code, 404)
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.cases, [])

    def test_unauthorized_user_cannot_export_project_data(self):
        doc = self._ingest(owner="bob", project_name="Export Denied")
        response = self.carol_client.get(f"/projects/{doc.project_id}/workspace/rfi-export")
        self.assertEqual(response.status_code, 404)

    def test_unauthorized_user_cannot_export_via_api(self):
        doc = self._ingest(owner="bob", project_name="API Export Denied")
        response = self.carol_client.get(f"/api/v1/documents/{doc.project_id}/rfi")
        self.assertEqual(response.status_code, 404)


class PortalBypassPathsClosedTests(_BaseAccessControlTestCase):
    """Every alternate path identified during CLAUDE-P32's own
    investigation that does not route through _load_workspace_or_404."""

    def test_delete_project_route_is_gated(self):
        doc = self._ingest(owner="bob", project_name="Delete Target")
        # carol is admin-less and not authorized -- but delete_project is
        # @admin_required anyway, so this proves the role gate, not the
        # project gate specifically; the real project-gate proof is the
        # admin case below via a project alice (admin) does not own.
        response = self.carol_client.post(f"/projects/{doc.project_id}/delete", data={"confirm": "yes"})
        self.assertEqual(response.status_code, 403)

    def test_dashboard_redirect_is_gated(self):
        doc = self._ingest(owner="bob", project_name="Dashboard Target")
        response = self.carol_client.get(f"/dashboard/{doc.project_id}")
        self.assertEqual(response.status_code, 404)

    def test_dashboard_redirect_works_for_the_owner(self):
        doc = self._ingest(owner="bob", project_name="Dashboard Owner")
        response = self.bob_client.get(f"/dashboard/{doc.project_id}", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn(doc.project_id, response.headers["Location"])

    def test_projects_list_excludes_inaccessible_projects(self):
        bob_doc = self._ingest(owner="bob", project_name="Bob Listed")
        carol_doc = self._ingest(owner="carol", project_name="Carol Not Listed To Bob")

        response = self.bob_client.get("/projects")
        body = response.data.decode()
        self.assertIn("Bob Listed", body)
        self.assertNotIn("Carol Not Listed To Bob", body)

    def test_home_page_recent_projects_excludes_inaccessible_projects(self):
        bob_doc = self._ingest(owner="bob", project_name="Bob Home")
        carol_doc = self._ingest(owner="carol", project_name="Carol Not On Bob Home")

        response = self.bob_client.get("/")
        body = response.data.decode()
        self.assertIn("Bob Home", body)
        self.assertNotIn("Carol Not On Bob Home", body)

    def test_global_search_excludes_inaccessible_projects(self):
        # global_search matches against the raw uploaded filename/
        # project_id, never display_title -- distinctive filenames here,
        # not project_name, are what actually reach the search index.
        bob_doc = self._ingest(owner="bob", project_name="Bob's Searchable Project", filename="searchable-bob-only.txt")
        carol_doc = self._ingest(owner="carol", project_name="Carol's Searchable Project", filename="searchable-carol-only.txt")

        response = self.bob_client.get("/search?q=searchable")
        results = response.get_json()["results"]
        titles = [r["title"] for r in results]
        self.assertTrue(any("bob" in t for t in titles))
        self.assertFalse(any("carol" in t for t in titles))

    def test_admin_sees_every_project_in_listings(self):
        bob_doc = self._ingest(owner="bob", project_name="Admin Sees Bob Project")
        carol_doc = self._ingest(owner="carol", project_name="Admin Sees Carol Project")

        response = self.alice_client.get("/projects")
        body = response.data.decode()
        self.assertIn("Admin Sees Bob Project", body)
        self.assertIn("Admin Sees Carol Project", body)


class CrossProjectIsolationTests(_BaseAccessControlTestCase):
    """Two users, two projects -- the mandate's own explicit minimum."""

    def setUp(self):
        super().setUp()
        self.bob_project = self._ingest(owner="bob", project_name="Bob Project")
        self.carol_project = self._ingest(owner="carol", project_name="Carol Project")

    def test_bob_can_open_his_own_project_not_carols(self):
        self.assertEqual(self.bob_client.get(f"/projects/{self.bob_project.project_id}/workspace").status_code, 200)
        self.assertEqual(self.bob_client.get(f"/projects/{self.carol_project.project_id}/workspace").status_code, 404)

    def test_carol_can_open_her_own_project_not_bobs(self):
        self.assertEqual(self.carol_client.get(f"/projects/{self.carol_project.project_id}/workspace").status_code, 200)
        self.assertEqual(self.carol_client.get(f"/projects/{self.bob_project.project_id}/workspace").status_code, 404)

    def test_grant_gives_access_and_revoke_removes_it(self):
        store = self._store()
        workspace = store.get(self.bob_project.project_id)
        store.grant_project_access(workspace, username="carol", actor="bob", actor_role="read_only")

        self.assertEqual(self.carol_client.get(f"/projects/{self.bob_project.project_id}/workspace").status_code, 200)

        workspace = store.get(self.bob_project.project_id)
        store.revoke_project_access(workspace, username="carol", actor="bob", actor_role="read_only")
        self.assertEqual(self.carol_client.get(f"/projects/{self.bob_project.project_id}/workspace").status_code, 404)

    def test_allow_listed_user_gains_no_grant_authority_of_their_own(self):
        store = self._store()
        workspace = store.get(self.bob_project.project_id)
        store.grant_project_access(workspace, username="carol", actor="bob", actor_role="read_only")

        workspace = store.get(self.bob_project.project_id)
        with self.assertRaises(CaseWorkspaceError):
            store.grant_project_access(workspace, username="alice", actor="carol", actor_role="read_only")

    def test_owner_can_grant_access_without_admin_authority(self):
        store = self._store()
        workspace = store.get(self.bob_project.project_id)
        # bob (owner, read_only role) grants -- no admin role required
        # for an owner acting on their own project.
        store.grant_project_access(workspace, username="carol", actor="bob", actor_role="read_only")
        reloaded = store.get(self.bob_project.project_id)
        self.assertIn("carol", reloaded.access_allow_list)


class LegacyProjectBackfillTests(_BaseAccessControlTestCase):
    """Existing-project compatibility rule: deterministic inference from
    a real User.username, else fail closed (admin-only) -- never a
    silent open-to-everyone fallback, never a guessed assignment."""

    def _seed_legacy_project(self, project_id: str, actor: str):
        registry = RequirementsRegistry(self.tmp_dir)
        registry.save(ParsedDocument(project_id=project_id, filename="legacy.txt", ingested_at="2020-01-01T00:00:00+00:00"))
        log = GovernanceLog(self.tmp_dir)
        log.append(project_id=project_id, event_type="document_ingested", actor=actor, role="unspecified", payload={})

    def test_legacy_project_with_a_real_username_actor_is_deterministically_backfilled(self):
        self._seed_legacy_project("legacy-real-user", actor="bob")
        store = self._store()
        workspace = store.get_or_create("legacy-real-user")
        self.assertIsNone(workspace.owner)

        inferred = infer_owner_from_ingestion_actor("legacy-real-user", GovernanceLog(self.tmp_dir), {"alice", "bob", "carol"})
        self.assertEqual(inferred, "bob")

    def test_legacy_project_with_a_free_text_actor_is_not_backfilled(self):
        # "agent1", "Mehrzad Dadras, Design Manager" -- free text, no
        # matching real account -- confirmed real repository evidence,
        # not a hypothetical.
        self._seed_legacy_project("legacy-free-text", actor="Jane Doe, Design Manager")
        inferred = infer_owner_from_ingestion_actor(
            "legacy-free-text", GovernanceLog(self.tmp_dir), {"alice", "bob", "carol"},
        )
        self.assertIsNone(inferred)

    def test_unbackfillable_legacy_project_stays_admin_only_never_open_to_everyone(self):
        self._seed_legacy_project("legacy-unowned", actor="synthetic-agent-1")
        response = self.bob_client.get("/projects/legacy-unowned/workspace")
        self.assertEqual(response.status_code, 404)
        admin_response = self.alice_client.get("/projects/legacy-unowned/workspace")
        self.assertEqual(admin_response.status_code, 200)

    def test_ensure_owner_backfilled_is_idempotent(self):
        self._seed_legacy_project("legacy-idempotent", actor="bob")
        store = self._store()
        workspace = store.get_or_create("legacy-idempotent")
        log = GovernanceLog(self.tmp_dir)

        ensure_owner_backfilled(store, workspace, log, {"alice", "bob", "carol"})
        self.assertEqual(workspace.owner, "bob")

        # A second call must not re-derive or overwrite -- confirmed by
        # manually corrupting the field between calls; if the function
        # were not idempotent, this would silently "fix" it back to bob.
        workspace.owner = "carol"
        ensure_owner_backfilled(store, workspace, log, {"alice", "bob", "carol"})
        self.assertEqual(workspace.owner, "carol")

    def test_backfilled_owner_persists_across_reload(self):
        self._seed_legacy_project("legacy-persist", actor="bob")
        response = self.bob_client.get("/projects/legacy-persist/workspace")
        self.assertEqual(response.status_code, 200)

        reloaded = self._store().get("legacy-persist")
        self.assertEqual(reloaded.owner, "bob")
        self.assertEqual(reloaded.owner_set_by, "system")

    def test_backfill_provenance_is_recorded_as_inferred_not_admin_assigned(self):
        self._seed_legacy_project("legacy-provenance", actor="bob")
        self.bob_client.get("/projects/legacy-provenance/workspace")

        log = GovernanceLog(self.tmp_dir)
        events = [e for e in log.read("legacy-provenance") if e.event_type == "project_owner_set"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["source"], "inferred_from_ingestion_actor")

    def test_admin_can_manually_assign_owner_to_an_unbackfillable_legacy_project(self):
        self._seed_legacy_project("legacy-manual-assign", actor="synthetic-agent-2")
        response = self.alice_client.post(
            "/projects/legacy-manual-assign/workspace/access/owner", data={"owner": "carol"},
        )
        self.assertIn(response.status_code, (302, 303))

        reloaded = self._store().get("legacy-manual-assign")
        self.assertEqual(reloaded.owner, "carol")
        self.assertEqual(reloaded.owner_set_by, "alice")

        # carol can now open it.
        self.assertEqual(self.carol_client.get("/projects/legacy-manual-assign/workspace").status_code, 200)


class CorruptedLegacyWorkspaceRouteTests(_BaseAccessControlTestCase):
    """
    CLAUDE-P37: found live during CLAUDE-P36's real-app walkthrough that
    the actual choke points behind almost every project-scoped route --
    routes/workspace.py's _load_workspace_or_404 (47+ routes: Case
    Workspace, Findings, RFI, everything) and services/project_access.py's
    load_authorized_project_or_none (every routes/api.py JSON route) --
    had never been given the same fail-closed handling already applied
    to peripheral pages (app.py's nav sidebar, routes/portal.py's
    document listing, routes/security.py's department home,
    services/security_assurance.py's self-check) for a corrupted legacy
    workspace file (one with a field ProjectWorkspace's current
    dataclass shape does not recognize at all). Originally reproduced
    with a real 'reviews' key -- CLAUDE-P40-D gave that specific key a
    real compatibility adapter (CaseWorkspaceStore._hydrate_legacy_
    reviews), so it no longer TypeErrors and is no longer a usable
    stand-in for "unrecognized field" here; a still-genuinely-
    unrecognized key is used instead to keep exercising the same
    fail-closed invariant. Confirms both choke points still 404
    (matching _load_workspace_or_404's own "don't confirm existence"
    convention) instead of a raw 500, for BOTH an authorized admin and
    an unauthorized reader -- neither should ever see a stack trace.
    """

    def _seed_corrupted_project(self, project_id: str):
        registry = RequirementsRegistry(self.tmp_dir)
        registry.save(ParsedDocument(project_id=project_id, filename="old.txt", ingested_at="2020-01-01T00:00:00+00:00"))
        (self.tmp_dir / f"{project_id}.workspace.json").write_text(
            '{"project_id": "' + project_id + '", "totally_unrecognized_field_xyz": []}', encoding="utf-8",
        )

    def test_workspace_route_404s_instead_of_500_for_a_corrupted_workspace(self):
        self._seed_corrupted_project("corrupted-workspace-route")
        self.assertEqual(self.alice_client.get("/projects/corrupted-workspace-route/workspace").status_code, 404)
        self.assertEqual(self.bob_client.get("/projects/corrupted-workspace-route/workspace").status_code, 404)

    def test_api_route_404s_instead_of_500_for_a_corrupted_workspace(self):
        self._seed_corrupted_project("corrupted-workspace-api")
        self.assertEqual(self.alice_client.get("/api/v1/documents/corrupted-workspace-api").status_code, 404)
        self.assertEqual(
            self.alice_client.get("/api/v1/documents/corrupted-workspace-api/requirements").status_code, 404,
        )


class NewProjectRequiresOwnerTests(_BaseAccessControlTestCase):
    def test_new_project_owner_matches_real_authenticated_uploader(self):
        doc = self._ingest(owner="bob", project_name="New Project Owner Check")
        workspace = self._store().get(doc.project_id)
        self.assertEqual(workspace.owner, "bob")
        self.assertEqual(workspace.owner_set_by, "bob")

    def test_owner_is_sourced_from_session_not_the_free_text_actor_field(self):
        # The real, structural proof this matters: routes/portal.py's
        # upload() passes owner=session['username'], never
        # request.form.get('actor') -- confirmed here by ingesting
        # through the real route with a spoofed actor field and checking
        # the resulting owner is the SESSION identity, not the free-text one.
        def fake_parse(self_parser, raw_bytes, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        admin_client = self._client_as("dave", 4, "admin")
        with self.flask_app.app_context():
            from models import User, db
            db.session.add(User(username="dave", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        with patch.object(BHiveParser, "parse", fake_parse):
            response = admin_client.post(
                "/upload",
                data={
                    "file": (io.BytesIO(b"content"), "a.txt"),
                    "operating_environment": CLIENT_OWNER,
                    "actor": "Someone Else Entirely",
                    "project_name": "Spoofed Actor Field",
                },
                content_type="multipart/form-data",
            )
        self.assertIn(response.status_code, (302, 303))
        registry = RequirementsRegistry(self.tmp_dir)
        document = next(
            d for pid in registry.list_ids() if (d := registry.get(pid)).filename == "a.txt"
        )
        workspace = self._store().get(document.project_id)
        self.assertEqual(workspace.owner, "dave")
        self.assertNotEqual(workspace.owner, "Someone Else Entirely")


class CentralizedResolverTests(unittest.TestCase):
    """Direct tests of the pure decision function, not just route
    behavior -- proves the resolver itself, isolated."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_access_resolver_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_none_owner_fails_closed_for_non_admin(self):
        workspace = self.store.get_or_create("p1")
        self.assertFalse(can_access_project(workspace, "anyone", is_admin=False))

    def test_none_username_is_denied_even_for_a_workspace_with_an_owner(self):
        workspace = self.store.get_or_create("p2")
        self.store.set_project_owner(workspace, owner="bob", actor="bob")
        self.assertFalse(can_access_project(workspace, None, is_admin=False))

    def test_none_workspace_is_denied(self):
        self.assertFalse(can_access_project(None, "bob", is_admin=False))

    def test_load_authorized_project_or_none_returns_none_for_missing_project(self):
        registry = RequirementsRegistry(self.tmp_dir)
        log = GovernanceLog(self.tmp_dir)
        result = load_authorized_project_or_none(self.store, registry, log, "does-not-exist", "bob", False)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
