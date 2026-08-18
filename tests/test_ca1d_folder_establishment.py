"""
CLAUDE-CA1D-RECEPTION-FIX-01 (addendum) - Project Folder Establishment.

Covers what was actually built: selecting a whole folder to establish a
project (webkitdirectory client-side, no live directory handle/desktop
agent), with every eligible file - not just the founding document -
becoming a real, governed Source whose content is genuinely usable by
GO's chat (services.case_workspace.register_plain_text_structure ->
per-paragraph EvidenceItems -> services.project_qa's additional-document-
evidence prompt section), relative-path provenance preserved via
Source.origin_reference, unsupported/oversize files reported rather than
failing the whole establishment, and duplicate filenames across
different folders disambiguated by relative path.

Every founding-document ingestion spies on BHiveParser.parse (the AI
classification stage) rather than letting it run for real (existing
repo-wide convention) - BHiveParser._extract itself (used for every
OTHER file) is pure local text extraction, no external call, safe to
run for real here.

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
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import UploadError, ingest_folder_upload
from services.project_qa import _build_prompt


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


class _BaseFolderEstablishmentTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_folder_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="folder_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client


class IngestFolderUploadTests(_BaseFolderEstablishmentTestCase):
    def test_founding_document_establishes_project_exactly_as_single_upload_would(self):
        founding = _fake_file(b"This is the RFP scope of work.\n\nSection 2: schedule.", "RFP.txt")
        exhibit = _fake_file(b"Exhibit A content here.\n\nMore exhibit detail.", "exhibits/Exhibit_A.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, exhibit],
                relative_paths=["RFP Package/RFP.txt", "RFP Package/exhibits/Exhibit_A.txt"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
                project_name="Folder RFP Project",
            )
        self.assertEqual(document.filename, "RFP.txt")
        workspace = self._store().get(document.project_id)
        self.assertEqual(workspace.display_title, "Folder RFP Project")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "added")

    def test_non_founding_file_becomes_a_real_source_with_relative_path_provenance(self):
        founding = _fake_file(b"Founding text.", "RFP.txt")
        exhibit = _fake_file(b"Exhibit content, paragraph one.\n\nParagraph two here.", "Exhibit_A.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, exhibit],
                relative_paths=["RFP Package/RFP.txt", "RFP Package/exhibits/Exhibit_A.txt"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
            )
        workspace = self._store().get(document.project_id)
        # CLAUDE-P32/CLAUDE-P40-E2 idiom check: a real governed Source, not
        # a metadata-only placeholder - name/origin_reference/origin_type set.
        sources = [s for s in workspace.sources if s["name"] == "Exhibit_A.txt"]
        self.assertEqual(len(sources), 1)
        source = sources[0]
        self.assertEqual(source["origin_reference"], "RFP Package/exhibits/Exhibit_A.txt")
        self.assertEqual(source["origin_type"], "upload")
        # Never a real filesystem path from the uploader's own machine.
        self.assertNotIn("RFP Package", source["file_path"])

    def test_non_founding_file_content_is_genuinely_extracted_not_metadata_only(self):
        founding = _fake_file(b"Founding text.", "RFP.txt")
        exhibit = _fake_file(b"A very specific sentence about site access requirements.", "Exhibit_A.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, exhibit], relative_paths=["RFP.txt", "Exhibit_A.txt"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
            )
        workspace = self._store().get(document.project_id)
        evidence_texts = [e["content"] for e in workspace.evidence_items]
        self.assertTrue(
            any("site access requirements" in t for t in evidence_texts),
            f"Expected real extracted content among evidence_items, got: {evidence_texts}",
        )

    def test_unsupported_extension_is_skipped_not_fatal(self):
        founding = _fake_file(b"Founding text.", "RFP.txt")
        image = _fake_file(b"\x89PNG fake bytes", "site_photo.png")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, image], relative_paths=["RFP.txt", "site_photo.png"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
            )
        self.assertIsNotNone(document)
        self.assertEqual(results[0]["status"], "skipped")
        self.assertIn("Unsupported", results[0]["reason"])

    def test_oversize_file_is_skipped_not_fatal(self):
        self.flask_app.config["MAX_CONTENT_LENGTH"] = 100  # tiny, for this test only
        founding = _fake_file(b"short", "RFP.txt")
        big = _fake_file(b"x" * 500, "Exhibit_A.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, big], relative_paths=["RFP.txt", "Exhibit_A.txt"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
            )
        self.assertEqual(results[0]["status"], "skipped")
        self.assertIn("size limit", results[0]["reason"])

    def test_duplicate_filenames_disambiguated_by_relative_path(self):
        founding = _fake_file(b"Founding text.", "RFP.txt")
        dup1 = _fake_file(b"First addendum, paragraph text.", "addendum.txt")
        dup2 = _fake_file(b"Second addendum, different paragraph text.", "addendum.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            document, results = ingest_folder_upload(
                files=[founding, dup1, dup2],
                relative_paths=["RFP.txt", "addenda/1/addendum.txt", "addenda/2/addendum.txt"],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="folder_owner",
            )
        workspace = self._store().get(document.project_id)
        same_name_sources = [s for s in workspace.sources if s["name"] == "addendum.txt"]
        self.assertEqual(len(same_name_sources), 2)
        origin_refs = {s["origin_reference"] for s in same_name_sources}
        self.assertEqual(origin_refs, {"addenda/1/addendum.txt", "addenda/2/addendum.txt"})
        self.assertEqual(len(results), 2)
        self.assertTrue(all(r["status"] == "added" for r in results))

    def test_invalid_founding_index_raises(self):
        founding = _fake_file(b"text", "RFP.txt")
        with self.flask_app.app_context():
            with self.assertRaises(UploadError):
                ingest_folder_upload(
                    files=[founding], relative_paths=["RFP.txt"], founding_index=5,
                    app=self.flask_app, operating_environment=CLIENT_OWNER, owner="folder_owner",
                )

    def test_empty_file_list_raises(self):
        with self.flask_app.app_context():
            with self.assertRaises(UploadError):
                ingest_folder_upload(
                    files=[], relative_paths=[], founding_index=0,
                    app=self.flask_app, operating_environment=CLIENT_OWNER, owner="folder_owner",
                )


class RegisterPlainTextStructureTests(_BaseFolderEstablishmentTestCase):
    def test_paragraphs_become_addressable_evidence(self):
        founding = _fake_file(b"Founding.", "RFP.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            from services.ingestion import ingest_upload
            document = ingest_upload(
                founding, self.flask_app, operating_environment=CLIENT_OWNER,
                owner="folder_owner", project_name="Plain Text Structure Test",
            )
            store = self._store()
            workspace = store.get(document.project_id)
            source = store.add_source(
                workspace, name="notes.txt", file_path="/dev/null", kind="project_document",
                actor="folder_owner",
            )
            result = store.register_plain_text_structure(
                workspace, source_id=source["id"],
                text="First paragraph here.\n\nSecond paragraph, distinct text.\n\n   \n\nThird one.",
                actor="folder_owner",
            )
        self.assertEqual(result["paragraph_count"], 3)
        workspace = self._store().get(document.project_id)
        contents = {e["content"] for e in workspace.evidence_items if e["source_id"] == source["id"]}
        self.assertEqual(contents, {"First paragraph here.", "Second paragraph, distinct text.", "Third one."})
        units = [u for u in workspace.structural_units if u["source_id"] == source["id"]]
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0]["unit_type"], "document")


class AdditionalDocumentEvidencePromptTests(unittest.TestCase):
    def test_additional_documents_appear_clearly_labeled_and_bounded(self):
        prompt = _build_prompt(
            question="What does the exhibit say about site access?",
            document_filename="RFP.txt",
            candidate_requirements=[], governed_requirements=[], milestones=[],
            additional_document_evidence=[
                {"filename": "Exhibit_A.txt", "relative_path": "exhibits/Exhibit_A.txt",
                 "excerpts": ["Site access requires a 48-hour notice."]},
            ],
        )
        # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: this section's own
        # heading text changed (the old "Other project documents" single
        # section became a two-part "all names" + "selected excerpts"
        # shape - see that stage's own selection function) - still
        # clearly labeled and bounded, just worded differently.
        self.assertIn("All other project documents by name", prompt)
        self.assertIn("Extracted text for the", prompt)
        self.assertIn("exhibits/Exhibit_A.txt", prompt)
        self.assertIn("Site access requires a 48-hour notice.", prompt)
        # Never conflated with the founding document's own classified requirements.
        self.assertIn("not yet run through requirement classification", prompt)

    def test_no_additional_documents_omits_the_section_entirely(self):
        prompt = _build_prompt(
            question="What is this project about?",
            document_filename="RFP.txt",
            candidate_requirements=[], governed_requirements=[], milestones=[],
            additional_document_evidence=None,
        )
        self.assertNotIn("All other project documents by name", prompt)

    def test_additional_documents_are_bounded_not_unbounded(self):
        many_docs = [
            {"filename": f"doc{i}.txt", "relative_path": f"doc{i}.txt", "excerpts": [f"Excerpt {i}"]}
            for i in range(50)
        ]
        prompt = _build_prompt(
            question="Summarize everything.",
            document_filename="RFP.txt",
            candidate_requirements=[], governed_requirements=[], milestones=[],
            additional_document_evidence=many_docs,
        )
        # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: every document's own
        # NAME is now listed regardless of selection (Section 3/7 honesty
        # - "exists but not selected" must be distinguishable from
        # "doesn't exist") - doc49.txt's NAME legitimately appears, but
        # its EXCERPT content must still never make the bounded,
        # relevance-selected set (15 is the still-enforced ceiling).
        self.assertIn("doc0.txt", prompt)
        self.assertIn("doc49.txt", prompt)  # named, honestly
        self.assertNotIn("Excerpt 49", prompt)  # but its content is not in the selected/bounded set


class UploadFolderRouteTests(_BaseFolderEstablishmentTestCase):
    def _client_as_admin(self):
        return self._client_as("folder_owner", 1, role="admin")

    def test_folder_upload_route_establishes_project_and_reports_skips(self):
        client = self._client_as_admin()
        data = {
            "operating_environment": CLIENT_OWNER,
            "project_name": "Route Folder Test",
            "founding_relative_path": "RFP Package/RFP.txt",
            "folder_files": [
                _fake_file(b"Founding RFP text content.", "RFP Package/RFP.txt"),
                _fake_file(b"Exhibit content, real paragraph text.", "RFP Package/exhibits/Exhibit_A.txt"),
                _fake_file(b"fake image bytes", "RFP Package/photo.png"),
            ],
        }
        with patch.object(BHiveParser, "parse", _fake_parse):
            response = client.post("/upload/folder", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 302)

        registry_dir = self.tmp_dir
        store = CaseWorkspaceStore(registry_dir)
        # Find the project just created via its known display title.
        from services.requirements_registry import RequirementsRegistry
        registry = RequirementsRegistry(registry_dir)
        matches = [registry.get(pid) for pid in registry.list_ids()]
        matches = [m for m in matches if m is not None]
        self.assertEqual(len(matches), 1)
        project_id = matches[0].project_id
        workspace = store.get(project_id)
        self.assertEqual(workspace.display_title, "Route Folder Test")
        names = {s["name"] for s in workspace.sources}
        self.assertIn("Exhibit_A.txt", names)
        self.assertNotIn("photo.png", names)

    def test_folder_upload_route_rejects_mismatched_founding_path(self):
        client = self._client_as_admin()
        data = {
            "operating_environment": CLIENT_OWNER,
            "founding_relative_path": "does-not-match-anything.txt",
            "folder_files": [_fake_file(b"content", "RFP.txt")],
        }
        response = client.post("/upload/folder", data=data, content_type="multipart/form-data")
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"invalid", response.data.lower())

    def test_folder_upload_route_requires_admin(self):
        client = self._client_as("folder_reader", 2, role="read_only")
        data = {
            "operating_environment": CLIENT_OWNER,
            "founding_relative_path": "RFP.txt",
            "folder_files": [_fake_file(b"content", "RFP.txt")],
        }
        response = client.post("/upload/folder", data=data, content_type="multipart/form-data")
        self.assertNotEqual(response.status_code, 302)
