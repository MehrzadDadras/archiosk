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

from services.bhive_parser import BHiveParser, ParsedDocument, ParserError
from services.case_workspace import CaseWorkspaceStore, SPIN_KIND_FIRST
from services.conversational_turn import gather_project_evidence
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
from services.llm_gateway import LLMCallOutcome
from services.spin import run_spin


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class AddDocumentsSpinReadabilityTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_add_documents_spin_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    _file(b"owner baseline", "owner-program.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Add Documents Spin Fixture",
                )
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _client(self, username="owner"):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = username
            session["role"] = "read_only"
        return client

    def _add_document(self, name="stage-one.docx", content=b"docx bytes", extracted=None):
        extracted = extracted or "Preliminary basis\n\nFire and smoke strategy is in development."
        with patch.object(BHiveParser, "_extract", return_value=extracted):
            return self._client().post(
                f"/projects/{self.project_id}/workspace/sources/document",
                data={"document": _file(content, name)}, content_type="multipart/form-data",
                follow_redirects=True,
            )

    def test_add_documents_registers_spin_readable_evidence_on_same_source(self):
        before_ids = {source["id"] for source in self.store.get(self.project_id).sources}
        response = self._add_document()
        self.assertEqual(response.status_code, 200)
        self.assertIn("processed as Spin-readable project evidence", response.get_data(as_text=True))

        workspace = self.store.get(self.project_id)
        added = [source for source in workspace.sources if source["id"] not in before_ids]
        self.assertEqual(len(added), 1)
        source = added[0]
        self.assertTrue(source["file_hash"])
        self.assertEqual(sum(u["source_id"] == source["id"] for u in workspace.structural_units), 1)
        self.assertGreater(sum(e["source_id"] == source["id"] for e in workspace.evidence_items), 0)
        unit_ids = {u["id"] for u in workspace.structural_units if u["source_id"] == source["id"]}
        self.assertGreater(sum(r["structural_unit_id"] in unit_ids for r in workspace.addressable_regions), 0)

        evidence = gather_project_evidence(workspace, self.store)
        supplied = {item["source_id"]: item for item in evidence.additional_document_evidence}
        self.assertIn(source["id"], supplied)
        self.assertIn("Fire and smoke strategy", " ".join(supplied[source["id"]]["excerpts"]))

    def test_extraction_failure_is_truthful_and_does_not_duplicate_source(self):
        before_count = len(self.store.get(self.project_id).sources)
        with patch.object(BHiveParser, "_extract", side_effect=ParserError("unreadable DOCX")):
            response = self._client().post(
                f"/projects/{self.project_id}/workspace/sources/document",
                data={"document": _file(b"bad", "unreadable.docx")},
                content_type="multipart/form-data", follow_redirects=True,
            )
        body = response.get_data(as_text=True)
        self.assertIn("Document registered, but its content could not be processed", body)
        self.assertIn("Spin cannot read this document yet", body)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.sources), before_count + 1)
        failed = [s for s in workspace.sources if s["name"] == "unreadable.docx"]
        self.assertEqual(len(failed), 1)
        self.assertFalse(any(e["source_id"] == failed[0]["id"] for e in workspace.evidence_items))

    def test_removed_and_superseded_sources_do_not_enter_current_project_evidence(self):
        self._add_document("old.docx", extracted="Old superseded content")
        self._add_document("removed.docx", extracted="Removed content")
        workspace = self.store.get(self.project_id)
        old = next(s for s in workspace.sources if s["name"] == "old.docx")
        removed = next(s for s in workspace.sources if s["name"] == "removed.docx")
        current, _notices, _supersession = self.store.register_source_revision(
            workspace, old_source_id=old["id"], name="current.docx",
            file_path=old["file_path"], actor="owner",
        )
        self.store.register_plain_text_structure(
            workspace, current["id"], "Current replacement content", actor="owner",
        )
        self.store.remove_source(workspace, removed["id"], actor="owner")
        workspace = self.store.get(self.project_id)

        current_ids = {s["id"] for s in self.store.spin_current_sources(workspace)}
        self.assertNotIn(old["id"], current_ids)
        self.assertNotIn(removed["id"], current_ids)
        self.assertIn(current["id"], current_ids)
        self.assertEqual(set(self.store.source_signature_for(workspace).split(",")), current_ids)
        evidence_ids = {e["source_id"] for e in gather_project_evidence(workspace, self.store).additional_document_evidence}
        self.assertNotIn(old["id"], evidence_ids)
        self.assertNotIn(removed["id"], evidence_ids)
        self.assertIn(current["id"], evidence_ids)

    def test_registered_fingerprint_and_actual_spin_evidence_scope_are_distinct(self):
        self._add_document("readable.docx", extracted="Readable evidence")
        workspace = self.store.get(self.project_id)
        readable = next(s for s in workspace.sources if s["name"] == "readable.docx")
        evidence_less = self.store.add_source(
            workspace, name="evidence-less.docx", file_path=readable["file_path"],
            kind=readable["kind"], actor="owner",
        )
        workspace = self.store.get(self.project_id)
        evidence = gather_project_evidence(workspace, self.store)
        registered_ids = set(self.store.source_signature_for(workspace).split(","))
        self.assertIn(evidence_less["id"], registered_ids)

        with patch("services.spin.call_llm_json", return_value=LLMCallOutcome(
            ran=True, parsed={"findings": [], "helix_assessments": []},
        )):
            result = run_spin(
                SPIN_KIND_FIRST, evidence.document_filename, evidence.candidate_requirements,
                evidence.governed_requirements, evidence.milestones,
                additional_document_evidence=evidence.additional_document_evidence,
                primary_source_id=evidence.primary_source_id,
            )
        self.assertTrue(result.ran)
        self.assertIn(readable["id"], result.evidence_source_ids)
        self.assertNotIn(evidence_less["id"], result.evidence_source_ids)

        run = self.store.record_spin_run(
            workspace, spin_kind=SPIN_KIND_FIRST, actor="owner", findings=[],
            source_signature=self.store.source_signature_for(workspace),
            scoped_source_ids=result.evidence_source_ids,
        )
        self.assertEqual(run["scoped_source_ids"], result.evidence_source_ids)
        self.assertNotEqual(set(run["scoped_source_ids"]), registered_ids)

    def test_cross_project_add_is_denied(self):
        response = self._client("intruder").post(
            f"/projects/{self.project_id}/workspace/sources/document",
            data={"document": _file(b"bytes", "cross.docx")},
            content_type="multipart/form-data",
        )
        self.assertIn(response.status_code, (403, 404))
        self.assertFalse(any(
            source["name"] == "cross.docx"
            for source in self.store.get(self.project_id).sources
        ))


if __name__ == "__main__":
    unittest.main()
