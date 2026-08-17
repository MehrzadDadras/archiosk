"""
CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01 - Spreadsheet Source Eligibility.

Covers the actual gap this stage found and closed: services/spreadsheet_
intelligence.py (CLAUDE-MM3) already existed as a real, hardened .xlsx
read/classify pipeline, and routes/workspace.py's own ALLOWED_DOCUMENT_
EXTENSIONS already allowed adding .xlsx to an EXISTING project - but
config.py's ALLOWED_UPLOAD_EXTENSIONS (the gate for new-project/folder-
upload/Data-Room-Reconcile eligibility, services/ingestion.py) had never
been revisited to include it, a legacy scope gap rather than a security
boundary or parser limitation.

This file does NOT re-test spreadsheet_intelligence.py's own parsing/
security internals (macro detection, zip-bomb bounds, malformed/
encrypted classification, formula preservation, etc.) - those are
already exhaustively covered by tests/test_mm3_spreadsheet_intelligence.py
and reused here unchanged. This file covers only the NEW integration
surface: config.py's extension list, services/ingestion.py's extension
branch (_register_source_content), and Reconcile's classification of a
real .xlsx once that gate is open.

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

import openpyxl
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import (
    RECONCILE_STATUS_NEW,
    RECONCILE_STATUS_UNCHANGED,
    UploadError,
    ingest_folder_upload,
    ingest_upload,
    preview_data_room_reconcile,
    reconcile_data_room_upload,
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _fake_parse(self_parser, raw_bytes, filename_):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename_,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
    )


def _real_xlsx_bytes(sheet_rows: dict[str, list[list]] | None = None) -> bytes:
    """A genuine, openpyxl-written .xlsx - never fabricated/fake bytes,
    matching this repo's own established convention (see CONTINUATION_
    CHECKPOINT.md's MM9 live-verification note) for exercising the real
    parser rather than a stub."""
    wb = openpyxl.Workbook()
    sheet_rows = sheet_rows or {"Unresolved Owner Decisions": [
        ["Decision", "Status"],
        ["Confirm courtroom ceiling height", "unresolved"],
        ["Approve holding-cell finish", "unresolved"],
    ]}
    first = True
    for name, rows in sheet_rows.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = name
        for row in rows:
            ws.append(row)
        first = False
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class _BaseSpreadsheetEligibilityTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_xlsx_source_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="xlsx_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _establish(self, extra_files=(), extra_relative_paths=()):
        founding = _fake_file(b"RFP scope of work.", "RFP.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            return ingest_folder_upload(
                files=[founding, *extra_files],
                relative_paths=["RFP.txt", *extra_relative_paths],
                founding_index=0, app=self.flask_app,
                operating_environment=CLIENT_OWNER, owner="xlsx_owner",
                project_name="Spreadsheet Eligibility Project",
            )


class FolderUploadSpreadsheetTests(_BaseSpreadsheetEligibilityTestCase):
    def test_A_valid_xlsx_becomes_an_eligible_governed_source(self):
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        document, results = self._establish([workbook], ["owner-reference.xlsx"])
        self.assertEqual(results[0]["status"], "added")
        workspace = self._store().get(document.project_id)
        sources = [s for s in workspace.sources if s["name"] == "owner-reference.xlsx"]
        self.assertEqual(len(sources), 1)
        # A real StructuralUnit (worksheet), not a paragraph - proves the
        # spreadsheet path (register_spreadsheet_structure), not
        # BHiveParser's plain-text path, actually ran.
        units = [u for u in workspace.structural_units if u["source_id"] == sources[0]["id"]]
        self.assertTrue(any(u["unit_type"] == "worksheet" for u in units))

    def test_B_malformed_workbook_is_skipped_safely_not_fatal(self):
        bad = _fake_file(b"not a real zip/xlsx at all", "corrupt.xlsx")
        document, results = self._establish([bad], ["corrupt.xlsx"])
        self.assertIsNotNone(document)
        result = next(r for r in results if r["filename"] == "corrupt.xlsx")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("could not be extracted", result["reason"])
        # Still registered as a real Source (matches PDF/DOCX's own
        # "added as a Source, content extraction failed separately"
        # precedent) - never silently dropped.
        workspace = self._store().get(document.project_id)
        self.assertTrue(any(s["name"] == "corrupt.xlsx" for s in workspace.sources))

    def test_C_macro_enabled_xlsm_remains_excluded(self):
        macro_file = _fake_file(_real_xlsx_bytes(), "budget.xlsm")
        document, results = self._establish([macro_file], ["budget.xlsm"])
        result = next(r for r in results if r["filename"] == "budget.xlsm")
        self.assertEqual(result["status"], "skipped")
        self.assertIn("Unsupported file type", result["reason"])

    def test_I_relative_path_provenance_preserved_for_a_workbook(self):
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        document, _results = self._establish([workbook], ["data-room/owner-reference.xlsx"])
        workspace = self._store().get(document.project_id)
        source = next(s for s in workspace.sources if s["name"] == "owner-reference.xlsx")
        self.assertEqual(source["origin_reference"], "data-room/owner-reference.xlsx")
        self.assertEqual(source["origin_type"], "upload")

    def test_H_workbook_content_is_genuinely_grounded_evidence(self):
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        document, _results = self._establish([workbook], ["owner-reference.xlsx"])
        workspace = self._store().get(document.project_id)
        evidence_texts = [e.get("content", "") for e in workspace.evidence_items]
        self.assertTrue(
            any("Confirm courtroom ceiling height" in t for t in evidence_texts),
            f"Expected real workbook row content among evidence_items, got: {evidence_texts}",
        )

    def test_H_gather_project_evidence_feeds_workbook_content_to_go(self):
        # CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01 Section 7: proves what
        # actually reaches GO's own grounding prompt (services.
        # conversational_turn.gather_project_evidence), hermetically - no
        # live Anthropic call, matching this repo's own established
        # "spy on external calls" discipline. gather_project_evidence is
        # completely format-agnostic (iterates workspace.evidence_items
        # generically), so this is a real, not incidental, proof.
        from services.conversational_turn import gather_project_evidence

        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        document, _results = self._establish([workbook], ["owner-reference.xlsx"])
        store = self._store()
        workspace = store.get(document.project_id)

        evidence = gather_project_evidence(workspace, store)
        matching = [
            e for e in evidence.additional_document_evidence
            if e["filename"] == "owner-reference.xlsx"
        ]
        self.assertEqual(len(matching), 1)
        self.assertTrue(
            any("Confirm courtroom ceiling height" in excerpt for excerpt in matching[0]["excerpts"]),
            f"Expected the workbook's own row content in GO's grounding evidence, got: {matching[0]['excerpts']}",
        )

    def test_G_spreadsheet_in_one_project_is_invisible_to_another(self):
        workbook_a = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        doc_a, _ = self._establish([workbook_a], ["owner-reference.xlsx"])

        founding_b = _fake_file(b"Second project founding text.", "RFP2.txt")
        with self.flask_app.app_context(), patch.object(BHiveParser, "parse", _fake_parse):
            doc_b, _ = ingest_folder_upload(
                files=[founding_b], relative_paths=["RFP2.txt"], founding_index=0,
                app=self.flask_app, operating_environment=CLIENT_OWNER, owner="xlsx_owner",
                project_name="Second Isolated Project",
            )
        workspace_b = self._store().get(doc_b.project_id)
        self.assertFalse(any(s["name"] == "owner-reference.xlsx" for s in workspace_b.sources))
        self.assertNotEqual(doc_a.project_id, doc_b.project_id)

    def test_J_existing_pdf_docx_txt_csv_md_ingestion_unaffected(self):
        exhibit = _fake_file(b"Ordinary exhibit paragraph content here.", "Exhibit_A.txt")
        document, results = self._establish([exhibit], ["Exhibit_A.txt"])
        self.assertEqual(results[0]["status"], "added")
        workspace = self._store().get(document.project_id)
        evidence_texts = [e.get("content", "") for e in workspace.evidence_items]
        self.assertTrue(any("Ordinary exhibit paragraph" in t for t in evidence_texts))


class FoundingDocumentSpreadsheetGuardTests(_BaseSpreadsheetEligibilityTestCase):
    def test_xlsx_refused_as_a_single_file_founding_document(self):
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        with self.flask_app.app_context():
            with self.assertRaises(UploadError) as ctx:
                ingest_upload(
                    workbook, self.flask_app, operating_environment=CLIENT_OWNER,
                    owner="xlsx_owner", project_name="Bad Founding Doc Project",
                )
        self.assertIn("founding document", str(ctx.exception))

    def test_xlsx_refused_as_the_founding_file_within_a_folder_upload(self):
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        other = _fake_file(b"some other text", "notes.txt")
        with self.flask_app.app_context():
            with self.assertRaises(UploadError):
                ingest_folder_upload(
                    files=[workbook, other], relative_paths=["owner-reference.xlsx", "notes.txt"],
                    founding_index=0, app=self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="xlsx_owner",
                )


class ReconcileSpreadsheetTests(_BaseSpreadsheetEligibilityTestCase):
    def test_E_reconcile_classifies_a_new_workbook_as_eligible(self):
        document, _results = self._establish()
        workbook = _fake_file(_real_xlsx_bytes(), "owner-reference.xlsx")
        with self.flask_app.app_context():
            report, new_eligible = preview_data_room_reconcile(
                files=[workbook], relative_paths=["owner-reference.xlsx"],
                project_id=document.project_id, app=self.flask_app,
            )
        self.assertEqual(report["summary"]["new"], 1)
        self.assertEqual(report["summary"]["ineligible"], 0)
        self.assertEqual(len(new_eligible), 1)
        new_item = report["by_status"][RECONCILE_STATUS_NEW][0]
        self.assertEqual(new_item["relative_path"], "owner-reference.xlsx")

    def test_D_and_F_confirmed_workbook_then_repeat_reconcile_is_stable(self):
        document, _results = self._establish()
        raw = _real_xlsx_bytes()

        with self.flask_app.app_context():
            add_results = reconcile_data_room_upload(
                files=[_fake_file(raw, "owner-reference.xlsx")],
                relative_paths=["owner-reference.xlsx"],
                project_id=document.project_id, app=self.flask_app,
            )
        self.assertEqual(add_results[0]["status"], "added")
        workspace = self._store().get(document.project_id)
        matching_sources = [s for s in workspace.sources if s["name"] == "owner-reference.xlsx"]
        self.assertEqual(len(matching_sources), 1, "duplicate spreadsheet Source created")

        # F - repeat Reconcile against the identical corpus must be stable/idempotent.
        with self.flask_app.app_context():
            report, new_eligible = preview_data_room_reconcile(
                files=[_fake_file(raw, "owner-reference.xlsx")],
                relative_paths=["owner-reference.xlsx"],
                project_id=document.project_id, app=self.flask_app,
            )
        self.assertEqual(report["summary"]["new"], 0)
        self.assertEqual(report["summary"]["unchanged"], 1)
        self.assertEqual(len(new_eligible), 0)
        unchanged_item = report["by_status"][RECONCILE_STATUS_UNCHANGED][0]
        self.assertEqual(unchanged_item["relative_path"], "owner-reference.xlsx")


if __name__ == "__main__":
    unittest.main()
