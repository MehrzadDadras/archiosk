"""
CLAUDE-POSTCAMEL-META-T01 - Territory Before Ontology.

Overview previously jumped straight from Access/Environment to Needs
Attention (governed-intelligence content) with no mention anywhere of
the reviewer's own registered material - a brand-new project's first
screen said nothing about "what is here" before exposing "what does
Archiosk know about it." This adds a small, honest "Project Territory"
projection pointer (no new domain object, no fabricated hierarchy) and
strengthens two pieces of copy (the entry-point upload page, and
Design-Builder Workspace's own explanatory text) to state directly that
Archiosk does not require moving, duplicating, or reorganizing a
project's real files.

Run via:

    python -m unittest tests.test_meta_t01_territory_before_ontology -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
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
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_meta_t01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="t01_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="t01_owner", project_name="META-T01 Territory Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "t01_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


class ProjectTerritoryOverviewTests(_BaseTestCase):
    def test_project_territory_accordion_present_on_overview(self):
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn("Project Territory", body)
        self.assertIn('data-ui-ref="display.overview.files-link"', body)
        self.assertIn("Open Files", body)

    def test_project_territory_shows_honest_registered_count(self):
        client = self._client()
        # The founding upload itself already registers as a Source (1);
        # add a second real Source and confirm the count honestly reflects
        # both, not a fixed/hardcoded number.
        before = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        before_count = int(before.split("Document(s)/Source(s) registered")[0].split()[-1])

        client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": _fake_file(b"spec content", "spec.txt")},
            content_type="multipart/form-data",
        )
        after = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        after_count = int(after.split("Document(s)/Source(s) registered")[0].split()[-1])
        self.assertEqual(after_count, before_count + 1)

    def test_project_territory_never_claims_files_are_moved_or_duplicated(self):
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        # Reformatted onto several source lines in the template (an
        # established pattern this repo's own tests already follow for
        # multi-line copy - see test_project_home.py) - checked as a
        # fragment guaranteed to be on one source line, not one
        # exact-whitespace string spanning the wrap.
        self.assertIn("Archiosk does not require you to move, duplicate, or reorganize", body)

    def test_project_territory_renders_before_needs_attention(self):
        """Progressive disclosure: 'what is here' before 'what does Archiosk
        know about it' - Territory must appear earlier in the document than
        the first governed-intelligence accordion."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        territory_index = body.index("Project Territory")
        needs_attention_index = body.index("Needs Attention")
        self.assertLess(territory_index, needs_attention_index)


class DesignBuilderWorkspaceCopyTests(_BaseTestCase):
    def test_design_builder_workspace_states_recreation_is_optional(self):
        """This copy lives inside the collapsed '+ New Folder' disclosure
        (moved there after a real-browser regression test proved
        always-visible copy above the folder list broke folder-row
        click-reachability - see the template's own comment) - a <details>
        element's content is always present in the raw HTML response, only
        visually collapsed, so it is still found here without expanding
        anything (same established pattern as test_project_home.py's own
        note on this)."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn("This is optional - nothing about working in Archiosk", body)
        self.assertIn("requires recreating your project's real Data Room or", body)

    def test_data_room_and_design_builder_remain_distinct(self):
        """Unchanged mechanism guard: Territory-Before-Ontology copy changes
        must not blur the two governed sibling roots together."""
        client = self._client()
        body = client.get(f"/projects/{self.project_id}/workspace?view=files").get_data(as_text=True)
        self.assertIn('data-ui-ref="display.files.data-room"', body)
        self.assertIn('data-ui-ref="display.files.design-builder"', body)


class UploadEntryPointCopyTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_meta_t01_upload_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="t01_upload", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "t01_upload"
            sess["role"] = "admin"
        return client

    def test_upload_page_states_territory_before_ontology_framing(self):
        client = self._client()
        body = client.get("/upload").get_data(as_text=True)
        # CLAUDE-POSTCAMEL-META-T01-RC1: "Open a Project" was corrected to
        # "Establish a Project" - it collided with the actual mechanism
        # ("+ New Project" always creates a fresh record, never reopens
        # an existing one).
        self.assertIn("Establish a Project", body)
        # CLAUDE-HYBRID-ENTRY-01: META-T01's own original claim here -
        # "your files stay wherever they already are" - was found to be
        # false of BOTH establishment mechanisms on this page (both
        # permanently upload a copy to Archiosk's own server; see
        # services/ingestion.py's ingest_upload/ingest_folder_upload).
        # This test originally asserted that now-false claim; rewritten
        # to assert the corrected, honest copy instead of silently
        # dropping coverage of this paragraph.
        #
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage
        # Grammar) supersedes HYBRID-ENTRY-01's own longer copy in turn -
        # replaced by a short framing sentence plus the Link-vs-Upload
        # choice itself (Part 1: "do not fill the normal surface with
        # lengthy custody explanations"). The underlying invariant this
        # test protects - never claim files stay in place when they
        # don't, for whichever mechanism is actually offered - is now
        # carried by the Link option's own honest "not yet configured"
        # label (see tests/test_storage_grammar_01_link_upload_
        # entitlement.py) rather than by this exact sentence.
        self.assertIn("Choose how this Project's documents connect to Archiosk.", body)
        self.assertNotIn("your files stay wherever they already are", body)

    def test_upload_page_still_carries_every_required_ui_reference(self):
        """Regression guard: the copy reframe must not drop any existing
        data-ui-ref the pre-existing test suite already depends on."""
        client = self._client()
        body = client.get("/upload").get_data(as_text=True)
        for ref in (
            "upload.limits", "upload.limits.formats", "upload.file", "upload.project-name",
            "upload.submit", "upload.operating-environment.client_owner",
            "upload.operating-environment.design_builder_proponent",
        ):
            self.assertIn(f'data-ui-ref="{ref}"', body)


if __name__ == "__main__":
    unittest.main()
