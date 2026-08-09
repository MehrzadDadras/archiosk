"""
CLAUDE-POSTCAMEL-COMM-I4A - OPR-2.5 corrective tranche.

`CaseWorkspaceStore.register_source_revision` was drawing-only
(`kind` hardcoded to `SOURCE_KIND_DRAWING`, `width`/`height` required) -
a real, self-disclosed (MM2's own STATUS.md row) gap: no non-drawing
Source (an RFP/specification/text record) could be formally revised or
superseded at all. This tranche generalizes the store method (`kind`
now defaults to the old Source's own kind, `width`/`height` now
Optional) and adds a new, non-Case-scoped route
(`revise_document_source`) exposing it through the ordinary product for
the three Source kinds `revise_source` (drawing-only) cannot serve.

Run via:

    python -m unittest tests.test_comm_i4a_source_revision_generalization -v
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
from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    SOURCE_KIND_DRAWING,
    SOURCE_KIND_PROJECT_DOCUMENT,
    SOURCE_KIND_TEXT_RECORD,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


# ---------------------------------------------------------------------------
# Store-layer: generalized register_source_revision
# ---------------------------------------------------------------------------

class GeneralizedSourceRevisionStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_comm_i4a_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "comm-i4a-project"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _text_source(self, workspace, name="opr.txt", content=b"Revision A text"):
        path = self.tmp_dir / name
        path.write_bytes(content)
        return self.store.add_source(
            workspace, name=name, file_path=str(path), kind=SOURCE_KIND_PROJECT_DOCUMENT,
            actor="tester",
        )

    def test_non_drawing_revision_preserves_old_sources_kind_by_default(self):
        workspace = self.store.get_or_create(self.project_id)
        old = self._text_source(workspace)

        rev_path = self.tmp_dir / "opr_rev_b.txt"
        rev_path.write_bytes(b"Revision B text")
        new_source, notices, supersession = self.store.register_source_revision(
            workspace, old_source_id=old["id"], name="opr_rev_b.txt",
            file_path=str(rev_path), actor="tester", reason="Revision B",
        )

        self.assertEqual(new_source["kind"], SOURCE_KIND_PROJECT_DOCUMENT)
        self.assertIsNone(new_source["width"])
        self.assertIsNone(new_source["height"])
        self.assertEqual(supersession["predecessor_id"], old["id"])
        self.assertEqual(supersession["successor_id"], new_source["id"])

    def test_text_record_revision_stays_a_text_record(self):
        workspace = self.store.get_or_create(self.project_id)
        note_path = self.tmp_dir / "note.txt"
        note_path.write_text("Site visit note - draft", encoding="utf-8")
        old = self.store.add_source(
            workspace, name="Site visit note", file_path=str(note_path),
            kind=SOURCE_KIND_TEXT_RECORD, actor="tester",
        )

        rev_path = self.tmp_dir / "note_corrected.txt"
        rev_path.write_text("Site visit note - corrected", encoding="utf-8")
        new_source, _, _ = self.store.register_source_revision(
            workspace, old_source_id=old["id"], name="Site visit note (corrected)",
            file_path=str(rev_path), actor="tester",
        )
        self.assertEqual(new_source["kind"], SOURCE_KIND_TEXT_RECORD)

    def test_old_source_never_mutated_and_historical_evidence_does_not_auto_migrate(self):
        """The requirement's own governing case: Source A must remain
        durable/inspectable, Source B gets its own identity, and a
        Requirement already anchored to Source A keeps resolving to A -
        it is never silently repointed at B."""
        workspace = self.store.get_or_create(self.project_id)
        old = self._text_source(workspace, content=b"OPR-2.5 original text")
        requirement = self.store.register_requirement(
            workspace, source_id=old["id"], original_requirement_identifier="OPR-TEST-1",
            text_reference="Original clause text", created_by="tester",
            registration_method="human_registered",
        )

        rev_path = self.tmp_dir / "opr_rev.txt"
        rev_path.write_bytes(b"OPR-2.5 revised text")
        new_source, _, _ = self.store.register_source_revision(
            workspace, old_source_id=old["id"], name="opr_rev.txt",
            file_path=str(rev_path), actor="tester",
        )

        old_after = self.store._find(workspace.sources, old["id"])
        self.assertEqual(old_after["name"], old["name"])
        self.assertEqual(old_after["file_path"], old["file_path"])
        self.assertEqual(old_after["superseded_by_source_id"], new_source["id"])

        requirement_after = self.store._find(workspace.requirements, requirement["id"])
        self.assertEqual(
            requirement_after["source_id"], old["id"],
            "historical Requirement evidence must keep resolving to the Source "
            "version it was actually based on, never silently repointed at the "
            "newer revision",
        )

    def test_revising_an_already_superseded_source_is_rejected(self):
        """Prevents an accidental fork: revise the LATEST version, not an
        earlier one that already has a successor."""
        workspace = self.store.get_or_create(self.project_id)
        old = self._text_source(workspace)
        rev_path = self.tmp_dir / "rev1.txt"
        rev_path.write_bytes(b"rev 1")
        self.store.register_source_revision(
            workspace, old_source_id=old["id"], name="rev1.txt",
            file_path=str(rev_path), actor="tester",
        )

        rev2_path = self.tmp_dir / "rev2.txt"
        rev2_path.write_bytes(b"rev 2")
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_source_revision(
                workspace, old_source_id=old["id"], name="rev2.txt",
                file_path=str(rev2_path), actor="tester",
            )

    def test_cross_project_supersession_is_structurally_impossible(self):
        """Not a new guard - _find only ever searches the loaded
        workspace's own .sources list, so a Source id belonging to a
        different project's workspace is simply absent, exactly like any
        other cross-project Source lookup in this codebase."""
        workspace_a = self.store.get_or_create("comm-i4a-project-a")
        workspace_b = self.store.get_or_create("comm-i4a-project-b")
        source_b = self._text_source(workspace_b, name="b.txt")

        rev_path = self.tmp_dir / "cross.txt"
        rev_path.write_bytes(b"cross-project attempt")
        with self.assertRaises(CaseWorkspaceError):
            self.store.register_source_revision(
                workspace_a, old_source_id=source_b["id"], name="cross.txt",
                file_path=str(rev_path), actor="tester",
            )

    def test_existing_drawing_revision_path_unaffected(self):
        """Regression guard: the pre-existing drawing call shape (explicit
        width/height, implicit drawing kind) must still work identically."""
        from PIL import Image

        img = Image.new("RGB", (10, 10), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_bytes = buf.getvalue()

        drawing_path = self.tmp_dir / "drawing.png"
        drawing_path.write_bytes(img_bytes)
        workspace = self.store.get_or_create(self.project_id)
        source = self.store.add_drawing_source(
            workspace, name="drawing.png", file_path=str(drawing_path), width=10, height=10,
        )

        rev_path = self.tmp_dir / "drawing_rev2.png"
        rev_path.write_bytes(img_bytes)
        new_source, _, supersession = self.store.register_source_revision(
            workspace, old_source_id=source["id"], name="drawing_rev2.png",
            file_path=str(rev_path), width=10, height=10, actor="tester",
        )
        self.assertEqual(new_source["kind"], SOURCE_KIND_DRAWING)
        self.assertEqual(new_source["width"], 10)
        self.assertEqual(supersession["authority_class"], "approval_gate:source_revision")


# ---------------------------------------------------------------------------
# Route-layer: the ordinary product pathway
# ---------------------------------------------------------------------------

class ReviseDocumentSourceRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_comm_i4a_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="i4a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="i4a_owner", project_name="COMM-I4A Revision Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
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
            sess["username"] = "i4a_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _add_project_document(self, client) -> str:
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": _fake_file(b"Revision A of the specification", "spec.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        return next(s["id"] for s in workspace.sources if s["name"] == "spec.txt")

    def test_revise_document_source_end_to_end_through_the_real_route(self):
        client = self._client()
        source_id = self._add_project_document(client)

        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/revise-document",
            data={
                "document": _fake_file(b"Revision B of the specification", "spec_rev_b.txt"),
                "confirm": "session",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 302)

        workspace = self._store().get(self.project_id)
        old_source = next(s for s in workspace.sources if s["id"] == source_id)
        self.assertIsNotNone(old_source["superseded_by_source_id"])
        new_source = next(s for s in workspace.sources if s["id"] == old_source["superseded_by_source_id"])
        self.assertEqual(new_source["name"], "spec_rev_b.txt")
        self.assertEqual(new_source["kind"], SOURCE_KIND_PROJECT_DOCUMENT)
        # historical Source is durable and inspectable, unchanged
        self.assertTrue(Path(old_source["file_path"]).exists())
        self.assertEqual(Path(old_source["file_path"]).read_bytes(), b"Revision A of the specification")

    def test_revise_document_source_refuses_a_drawing_source(self):
        client = self._client()
        store = self._store()
        workspace = store.get(self.project_id)
        drawing_dir = self.tmp_dir / "workspace_sources" / self.project_id
        drawing_dir.mkdir(parents=True, exist_ok=True)
        drawing_path = drawing_dir / "d.png"
        from PIL import Image
        Image.new("RGB", (4, 4)).save(drawing_path)
        drawing_source = store.add_drawing_source(
            workspace, name="d.png", file_path=str(drawing_path), width=4, height=4,
        )

        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/{drawing_source['id']}/revise-document",
            data={"document": _fake_file(b"not an image", "x.txt"), "confirm": "session"},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 302)
        workspace_after = self._store().get(self.project_id)
        drawing_after = next(s for s in workspace_after.sources if s["id"] == drawing_source["id"])
        self.assertIsNone(drawing_after["superseded_by_source_id"])

    def test_revise_document_source_rejects_unsupported_extension(self):
        client = self._client()
        source_id = self._add_project_document(client)
        resp = client.post(
            f"/projects/{self.project_id}/workspace/sources/{source_id}/revise-document",
            data={"document": _fake_file(b"binary", "malware.exe"), "confirm": "session"},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self._store().get(self.project_id)
        source_after = next(s for s in workspace.sources if s["id"] == source_id)
        self.assertIsNone(source_after["superseded_by_source_id"])


if __name__ == "__main__":
    unittest.main()
