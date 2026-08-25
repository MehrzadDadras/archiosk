"""
CLAUDE-Q-MATERIALS-01 - a Q holds material that is not a photo.

Product Owner: "A Q may need to hold photos; PDFs; drawings; Word documents;
Excel files; specification excerpts; reports; notes... Reuse existing governed
Source/document primitives where they already exist... Do not automatically turn
an attachment into a Finding or authoritative project evidence merely because it
is added to a Q."

WHAT WAS ACTUALLY MISSING

Every material type already had a governed ingestion path, and every one of them
produced an ordinary Source:

    .pdf/.docx/.txt/.csv/.md/.xlsx  -> add_document_source      (project-scoped)
    .png/.jpg/.jpeg as a drawing    -> add_drawing_source       (already attached)
    a Composer photo                -> register_eye_capture     (already attached)
    a note                          -> add_text_record_source   (project-scoped)

The document and text-record paths never attached to anything - deliberately.
add_document_source's own docstring says why: "a Case draws on Sources, it does
not own them." That model is correct and this stage does not change it.

So, for the second time running, what was missing was a VERB, not a container:
one route that says "this Q draws on that Source". These tests are written to
keep it that way - several of them assert the ABSENCE of a Q-specific ingestion
mechanism, because "let a Q hold documents" is exactly the instruction that
produces a parallel upload system when taken at face value.

A second real gap is covered here too: the Q view rendered `kind == "drawing"`
only, so a PDF attached to an investigation went in and vanished. The attachment
was real; the Q just never showed it. A container nobody can see the contents of
is not a container.
"""
from __future__ import annotations

import io
import re
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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ROUTES = _REPO_ROOT / "routes" / "workspace.py"
_CASE_HTML = _REPO_ROOT / "templates" / "case_workspace.html"


class _QMaterialsTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        import tempfile
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_q_materials_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="qm_owner",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.add(User(username="qm_other",
                                password_hash=generate_password_hash("x"), role="user"))
            db.session.commit()

        self.doc = self._ingest()
        self.project_id = self.doc.project_id
        self.client = self._client_as("qm_owner", 1, "admin")

        store = self._store()
        workspace = store.get(self.project_id)
        self.case = store.create_case(
            workspace, title="Settlement Investigation",
            objective="x", created_by="qm_owner",
        )
        self.case_id = self.case["id"]

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _ingest(self, project_name="Q Materials Project"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"c"), filename="rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="qm_owner",
                    project_name=project_name,
                )

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _add_project_source(self, name="Specification 07 92 00.pdf", kind="document"):
        """A Source that exists in the project but belongs to no Q."""
        store = self._store()
        workspace = store.get(self.project_id)
        source = store.add_source(workspace, name=name, kind=kind, file_path=None)
        return source

    def _case_now(self):
        workspace = self._store().get(self.project_id)
        return next(c for c in workspace.cases if c["id"] == self.case_id)

    def _attach(self, source_id, client=None):
        return (client or self.client).post(
            f"/projects/{self.project_id}/workspace/cases/{self.case_id}/attach-source",
            data={"source_id": source_id}, follow_redirects=True,
        )


class NoParallelIngestionWasBuiltTests(unittest.TestCase):
    """The failure mode this instruction invites, asserted as absent."""

    def setUp(self):
        self.routes = _ROUTES.read_text(encoding="utf-8")
        self.attach = self.routes[self.routes.index("def attach_source_to_case_route"):]
        self.attach = self.attach[:self.attach.index("\n@workspace_bp.route")]

    def test_the_attach_route_stores_no_file_itself(self):
        for token in ("write_bytes", "file_storage", "request.files", "secure_filename"):
            self.assertNotIn(token, self.attach, token)

    def test_the_attach_route_reuses_the_existing_primitive(self):
        self.assertIn("store.attach_source_to_case(", self.attach)

    def test_no_q_specific_upload_route_was_added(self):
        for invented in ("q-upload", "case-upload", "investigation-upload", "q_ingest"):
            self.assertNotIn(invented, self.routes, invented)

    def test_document_ingestion_stayed_project_scoped(self):
        # The optional `case` is an attachment convenience, not a re-scoping.
        # A Case draws on Sources; it does not own them.
        doc = self.routes[self.routes.index("def add_document_source"):]
        doc = doc[:doc.index("\n@workspace_bp.route")]
        self.assertIn("OPTIONAL case", doc)
        self.assertIn("attach_source_to_case", doc)


class AttachingExistingMaterialTests(_QMaterialsTestCase):
    def test_a_document_source_can_be_filed_in_a_q(self):
        source = self._add_project_source()
        self.assertNotIn(source["id"], self._case_now()["source_ids"])
        self._attach(source["id"])
        self.assertIn(source["id"], self._case_now()["source_ids"])

    def test_several_material_types_accumulate_in_one_q(self):
        kinds = [("Spec 07 92 00.pdf", "document"), ("Risk register.xlsx", "document"),
                 ("Site note", "text_record"), ("A-101 Plan", "drawing")]
        for name, kind in kinds:
            self._attach(self._add_project_source(name, kind)["id"])
        self.assertEqual(len(self._case_now()["source_ids"]), len(kinds))

    def test_attaching_twice_does_not_double_file_it(self):
        source = self._add_project_source()
        self._attach(source["id"])
        self._attach(source["id"])
        self.assertEqual(self._case_now()["source_ids"].count(source["id"]), 1)

    def test_the_source_is_not_moved_or_copied_into_the_q(self):
        # Attaching records that this Q DRAWS ON the Source. The Source remains
        # a project Source, reachable from elsewhere and unduplicated.
        source = self._add_project_source()
        self._attach(source["id"])
        workspace = self._store().get(self.project_id)
        matching = [s for s in workspace.sources if s["id"] == source["id"]]
        self.assertEqual(len(matching), 1)


class AttachingIsNotConcludingTests(_QMaterialsTestCase):
    def test_attaching_creates_no_finding(self):
        self._attach(self._add_project_source()["id"])
        self.assertEqual(self._store().get(self.project_id).findings, [])

    def test_attaching_creates_no_claim_or_adjudication(self):
        self._attach(self._add_project_source()["id"])
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.claims, [])
        self.assertEqual(workspace.requirement_adjudications, [])

    def test_the_confirmation_says_filed_not_concluded(self):
        source = self._add_project_source()
        body = self._attach(source["id"]).get_data(as_text=True)
        self.assertIn("not concluded from", body)


class AuthorizationTests(_QMaterialsTestCase):
    def test_an_unknown_source_id_is_refused_not_disclosed(self):
        response = self._attach("no-such-source-id")
        self.assertEqual(response.status_code, 200)
        self.assertIn("not available in this project", response.get_data(as_text=True))
        self.assertEqual(self._case_now()["source_ids"], [])

    def test_a_source_from_another_project_cannot_be_attached(self):
        # A genuinely separate project - names must be unique per environment.
        other = self._ingest(project_name="A Different Project Entirely")
        store = self._store()
        other_ws = store.get(other.project_id)
        foreign = store.add_source(other_ws, name="Other project spec.pdf",
                                   kind="document", file_path=None)
        self._attach(foreign["id"])
        self.assertNotIn(foreign["id"], self._case_now()["source_ids"])

    def test_the_route_is_gated_by_case_visibility(self):
        routes = _ROUTES.read_text(encoding="utf-8")
        attach = routes[routes.index("def attach_source_to_case_route"):]
        attach = attach[:attach.index("\n@workspace_bp.route")]
        self.assertIn("_require_visible_case(store, workspace, case_id)", attach)

    def test_an_anonymous_request_cannot_attach(self):
        anon = self.flask_app.test_client()
        source = self._add_project_source()
        response = anon.post(
            f"/projects/{self.project_id}/workspace/cases/{self.case_id}/attach-source",
            data={"source_id": source["id"]}, follow_redirects=False,
        )
        self.assertIn(response.status_code, (301, 302, 303, 401, 403, 404))
        self.assertNotIn(source["id"], self._case_now()["source_ids"])


class TheQShowsWhatItHoldsTests(_QMaterialsTestCase):
    """Before this stage the Q rendered drawings only - material vanished."""

    def test_the_materials_list_is_not_filtered_to_drawings(self):
        markup = _CASE_HTML.read_text(encoding="utf-8")
        block = markup[markup.index("toolbox.q-materials"):]
        block = block[:block.index("toolbox.investigation-findings")]
        self.assertIn("active_case.source_ids", block)
        self.assertNotIn('"kind", "equalto", "drawing"', block)

    def test_an_attached_document_is_visible_in_the_q(self):
        source = self._add_project_source(name="Specification 07 92 00.pdf")
        self._attach(source["id"])
        body = self.client.get(
            f"/projects/{self.project_id}/workspace?case={self.case_id}"
        ).get_data(as_text=True)
        listing = body[body.index("toolbox.q-materials.list"):]
        listing = listing[:listing.index("</ul>")]
        self.assertIn("Specification 07 92 00.pdf", listing)

    def test_an_empty_q_says_so_honestly(self):
        body = self.client.get(
            f"/projects/{self.project_id}/workspace?case={self.case_id}"
        ).get_data(as_text=True)
        self.assertIn("Nothing filed in this investigation yet", body)

    def test_already_attached_material_is_not_offered_again(self):
        source = self._add_project_source(name="Only Once.pdf")
        self._attach(source["id"])
        body = self.client.get(
            f"/projects/{self.project_id}/workspace?case={self.case_id}"
        ).get_data(as_text=True)
        if "toolbox.q-materials.attach-select" in body:
            select = body[body.index("toolbox.q-materials.attach-select"):]
            select = select[:select.index("</select>")]
            self.assertNotIn(source["id"], select)


if __name__ == "__main__":
    unittest.main()
