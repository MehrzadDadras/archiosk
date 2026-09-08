"""CLAUDE-BLACK-BOX-LISTING-01: a shared kernel is not a shared identity.

Every listing in this application enumerated the governed store and therefore
called everything in it a Project. That was true while everything in it WAS one.
The Black Box door made it false, and the defect shipped: a container whose whole
premise is "this is not a project" was listed, counted and searched as one.

SHARED KERNEL DOES NOT MEAN SHARED USER-FACING IDENTITY.

Three tests carry the weight:

`test_a_black_box_is_absent_from_every_project_listing` - the defect itself,
asserted across every surface rather than the one helper that was found first.

`test_the_boundary_uses_container_state_not_source_kind` - the wrong fix,
refused. A Project may legitimately hold unclassified sources, so inferring the
operating line from a document's type would repeat the exact class of assumption
that caused this.

`test_a_black_box_is_not_orphaned_by_the_boundary` - excluding a container from
every listing without giving it one of its own is orphaning, not a boundary.
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

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX, CaseWorkspaceStore, SOURCE_KIND_UNCLASSIFIED,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class ListingBoundaryTests(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_listing_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)

        self.project = self._ingest("rfp.pdf", operating_environment=CLIENT_OWNER,
                                    project_name="Conventional Project")
        self.black_box = self._ingest(
            "notes.txt", operating_environment=None,
            container_state=CONTAINER_STATE_BLACK_BOX,
            project_name="A Document Shop Job")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ingest(self, name, **kwargs):
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename=name),
                    self.app, owner="owner", **kwargs)

    def _client(self, role="admin", username="owner"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = role
        return client

    # -- the defect ----------------------------------------------------------

    def test_a_black_box_is_absent_from_every_project_listing(self):
        """Asserted per surface, because one helper was not the whole story.

        `app.py`'s nav rail builds its own list and never went through the
        shared helper, so a fix applied only there would have left the rail -
        which renders on EVERY authenticated page - still leaking.
        """
        client = self._client()
        surfaces = {
            "projects directory": "/projects",
            "project chooser": "/choose-project",
            "home": "/",
        }
        for label, path in surfaces.items():
            response = client.get(path)
            if response.status_code != 200:
                continue
            body = response.get_data(as_text=True)
            with self.subTest(surface=label):
                self.assertNotIn(self.black_box.project_id, body,
                                 "%s listed a Black Box as a Project" % label)
                self.assertNotIn("A Document Shop Job", body)

    def test_a_black_box_does_not_inflate_project_counts(self):
        from routes.portal import _accessible_documents

        with self.app.test_request_context("/"):
            from flask import session
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "admin"
            from services.ingestion import get_registry
            documents = _accessible_documents(get_registry(self.app), self.store)
        ids = {d.project_id for d in documents}
        self.assertIn(self.project.project_id, ids)
        self.assertNotIn(self.black_box.project_id, ids)
        self.assertEqual(len(ids), 1, "the count a Projects surface reports")

    def test_a_black_box_is_not_a_project_in_search(self):
        body = self._client().get("/search?q=Document+Shop+Job").get_data(as_text=True)
        self.assertNotIn(self.black_box.project_id, body)

    def test_the_nav_rail_excludes_a_black_box(self):
        """The rail renders on every authenticated page, error pages included."""
        import app as app_module

        with self.app.test_request_context("/"):
            from flask import session
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "admin"
            recent = app_module._nav_recent_projects(self.app)
        ids = {getattr(item, "project_id", None) or item.get("project_id")
               for item in recent}
        self.assertIn(self.project.project_id, ids)
        self.assertNotIn(self.black_box.project_id, ids)

    # -- the wrong fix, refused ----------------------------------------------

    def test_the_boundary_uses_container_state_not_source_kind(self):
        """A Project may legitimately hold unclassified sources.

        Inferring the operating line from a document's type would repeat the
        exact class of assumption that CLAUDE-BLACK-BOX-D1-01 removed.
        """
        from routes.portal import _matches_listing_scope, LISTING_SCOPE_PROJECTS

        workspace = self.store.get(self.project.project_id)
        for source in workspace.sources:
            source["kind"] = SOURCE_KIND_UNCLASSIFIED
        self.store.save(workspace)

        self.assertTrue(
            _matches_listing_scope(self.store.get(self.project.project_id),
                                   LISTING_SCOPE_PROJECTS),
            "a Project holding only unclassified sources is still a Project")

    def test_a_legacy_container_without_the_field_lists_as_a_project(self):
        from routes.portal import _matches_listing_scope, LISTING_SCOPE_PROJECTS

        workspace = self.store.get(self.project.project_id)
        del workspace.container_state
        self.assertTrue(_matches_listing_scope(workspace, LISTING_SCOPE_PROJECTS),
                        "absence must read as an ordinary Project")

    # -- not orphaned --------------------------------------------------------

    def test_a_black_box_is_not_orphaned_by_the_boundary(self):
        response = self._client().get("/document-shop/jobs")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("A Document Shop Job", body)
        self.assertIn(self.black_box.project_id, body)

    def test_the_jobs_listing_shows_no_conventional_project(self):
        """The LISTING, not the page.

        base.html renders the recent-projects nav rail on every authenticated
        page, and a conventional Project belongs there - scanning the whole
        document would assert about the rail rather than about this listing.
        """
        body = self._client().get("/document-shop/jobs").get_data(as_text=True)
        start = body.index('data-ui-ref="document-shop.jobs.page-title"')
        end = body.index('data-ui-ref="document-shop.jobs.new"')
        listing = body[start:end]
        self.assertNotIn(self.project.project_id, listing)
        self.assertNotIn("Conventional Project", listing)

    def test_the_jobs_listing_carries_no_engagement_vocabulary(self):
        """D2 owns full presentation. This asserts the LISTING invents none."""
        body = self._client().get("/document-shop/jobs").get_data(as_text=True)
        start = body.index('data-ui-ref="document-shop.jobs.page-title"')
        end = body.index('data-ui-ref="document-shop.jobs.new"')
        listing = body[start:end]
        for absent in ("Operating Environment", "Owner /", "Proponent",
                       "procurement", "lifecycle"):
            with self.subTest(word=absent):
                self.assertNotIn(absent, listing)

    def test_a_job_opens_onto_the_as_read_bench(self):
        body = self._client().get("/document-shop/jobs").get_data(as_text=True)
        self.assertIn("/workspace/sources/", body)
        self.assertIn("/understanding", body)

    # -- access control, unchanged -------------------------------------------

    def test_another_user_cannot_discover_a_black_box_through_its_listing(self):
        stranger = self._client(role="read_only", username="stranger")
        response = stranger.get("/document-shop/jobs")
        if response.status_code == 200:
            body = response.get_data(as_text=True)
            self.assertNotIn(self.black_box.project_id, body)
            self.assertNotIn("A Document Shop Job", body)
        else:
            self.assertIn(response.status_code, (302, 401, 403))

    def test_isolation_still_returns_a_generic_404(self):
        stranger = self._client(role="read_only", username="stranger")
        self.assertEqual(
            stranger.get("/projects/%s/workspace" % self.black_box.project_id).status_code,
            404)

    def test_no_second_access_mechanism_was_introduced(self):
        source = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        window = source[source.index("def document_shop_jobs"):]
        window = window[:window.index("@portal_bp.route('/document-shop',")]
        self.assertIn("_accessible_documents", window,
                      "the jobs listing must reach data through the same "
                      "access-filtered helper every Project listing uses")

    # -- conventional projects unchanged -------------------------------------

    def test_conventional_projects_remain_visible(self):
        body = self._client().get("/projects").get_data(as_text=True)
        self.assertIn(self.project.project_id, body)

    def test_removed_project_behaviour_is_unchanged(self):
        from routes.portal import _accessible_documents
        from services.ingestion import get_registry

        workspace = self.store.get(self.project.project_id)
        self.store.remove_project(workspace, actor="owner", actor_role="admin",
                                  reason="test")
        with self.app.test_request_context("/"):
            from flask import session
            session["user_id"] = 1
            session["username"] = "owner"
            session["role"] = "admin"
            registry = get_registry(self.app)
            active = {d.project_id for d in _accessible_documents(registry, self.store)}
            removed = {d.project_id
                       for d in _accessible_documents(registry, self.store,
                                                      include_removed=True)}
        self.assertNotIn(self.project.project_id, active)
        self.assertIn(self.project.project_id, removed)

    def test_help_library_behaviour_is_unchanged(self):
        """Help uses its own historical mechanism and is not refactored here."""
        from services.help_mode import HELP_LIBRARY_PROJECT_ID, is_help_workspace

        self.assertTrue(is_help_workspace(HELP_LIBRARY_PROJECT_ID))
        self.assertFalse(is_help_workspace(self.black_box.project_id),
                         "a Black Box must not be mistaken for a Help workspace "
                         "- two different non-project mechanisms coexist and "
                         "this tranche deliberately converges neither")

    # -- what this tranche did NOT do ----------------------------------------

    def test_no_entitlement_was_widened(self):
        source = (_REPO_ROOT / "routes" / "portal.py").read_text(encoding="utf-8")
        window = source[source.index("def document_shop_jobs"):]
        header = source[:source.index("def document_shop_jobs")]
        self.assertTrue(header.rstrip().endswith("@admin_required"),
                        "the jobs listing holds the same authority as the door")

    def test_name_uniqueness_is_now_owner_scoped(self):
        """Superseded by CLAUDE-BLACK-BOX-OWNER-NAMES-01, not weakened.

        This asserted deployment-wide uniqueness, which was correct while that
        was the rule and while this tranche's job was to prove it had NOT
        changed it. The Product Owner has since scoped names per owner, so the
        assertion follows the decision rather than defending the behaviour it
        superseded.
        """
        source = (_REPO_ROOT / "services" / "ingestion.py").read_text(encoding="utf-8")
        window = source[source.index("def _names_owned_by"):]
        window = window[:window.index("def _reject_if_name_taken")]
        self.assertIn("workspace.owner != owner", window,
                      "the scan must compare against the container's own owner")

    def test_d1_classification_behaviour_is_unchanged(self):
        workspace = self.store.get(self.black_box.project_id)
        self.assertEqual(workspace.sources[0]["kind"], SOURCE_KIND_UNCLASSIFIED)
