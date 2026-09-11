"""CLAUDE-SHEET-IDENTITY-REGISTER-01: which sheets does this project declare?

    DRAWING INDEX ENTRY -> PROJECT SHEET IDENTITY -> ACTUAL SOURCE

What these tests defend, in the order the mistakes would be made:

1. **IDENTITY IS NOT RELATIONSHIP MEANING.** Resolving an index entry proves the
   project declares a sheet and a Source answers to it. It proves nothing about
   conflict, callouts, shared location or differing values. `IdentityOnly` pins
   that no discrepancy, magnitude or `Relationship` is emitted.

2. **ABSTENTION IS THE FALSE-POSITIVE FILTER.** The real index yields dates
   (`JAN18`), Canadian postal codes (`M2K`, `L4B`, `N6A`) and OCR garbage
   (`Ae0s`, `ft92s`) that all match a sheet-identifier shape. None names a
   Source, so none produces a link. Nothing is scored and nothing is tuned —
   measured on the real corpus at **48 resolved, 0 ambiguous, 90 abstained**.

3. **THE GENERAL PARSER IS NOT WIDENED.** A bare `A101` in prose is still not a
   sheet citation, and the `known_sheets` consumption rule that prevents false
   orphan tags still governs every text going through
   `parse_source_reference_text`. Only a caller that KNOWS it is reading an
   index supplies its own candidates.
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

from services import sheet_identity as si
from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CONTAINER_STATE_BLACK_BOX,
    REFERENCE_TYPE_SHEET,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_RESOLVED_MULTIPLE,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
    CaseWorkspaceStore,
)
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent

INDEX_TEXT = """
DRAWING INDEX
A101 SITE PLAN
A204 GROUND FLOOR PLAN
S301 FRAMING
JAN18
M2K
"""


def _fake_parse(_parser, _raw, filename):
    return ParsedDocument(
        project_id=str(uuid.uuid4()), filename=filename,
        ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test")


class TokenExtraction(unittest.TestCase):
    """Conservative by construction: whole word or nothing."""

    def test_a_project_prefixed_filename_yields_its_sheet_token(self):
        self.assertEqual(
            si.source_sheet_tokens({"name": "212109 A101 SITE PLAN.pdf"}), {"A101"})

    def test_a_simple_sheet_filename_yields_its_token(self):
        for name, token in (("A-01.pdf", "A01"), ("S-01.pdf", "S01"),
                            ("E1.pdf", "E1"), ("A101.pdf", "A101")):
            with self.subTest(name=name):
                self.assertEqual(si.source_sheet_tokens({"name": name}), {token})

    def test_spelling_variants_are_one_identity(self):
        for spelling in ("A-01", "A 01", "a01"):
            with self.subTest(spelling=spelling):
                self.assertEqual(si.normalise_sheet_token(spelling), "A01")

    def test_a_word_that_merely_contains_a_token_is_not_one(self):
        """`XA101` is deliberately NOT in this list: three-letter discipline
        prefixes are real, so it is a valid sheet shape and indistinguishable
        from one. Resolution filters it if no Source answers to it — which is
        the whole design, and why the shape rule does not need to be clever."""
        for text in ("A101B2", "A101-DETAIL", "REV-A101-2", "A1012345"):
            with self.subTest(text=text):
                self.assertIsNone(si.sheet_token(text))

    def test_a_filename_with_two_sheet_shaped_words_abstains(self):
        """An identity that needs a guess is not an identity."""
        self.assertEqual(
            si.source_sheet_tokens({"name": "A101 and A102 combined.pdf"}), set())

    def test_a_document_with_no_sheet_token_yields_nothing(self):
        for name in ("Geotechnical-Investigation-Report-Rev02-SCANNED.pdf",
                     "README.pdf", "notes.txt"):
            with self.subTest(name=name):
                self.assertEqual(si.source_sheet_tokens({"name": name}), set())


class IndexRecognition(unittest.TestCase):

    def test_an_index_is_recognised_by_its_heading(self):
        for heading in ("DRAWING INDEX", "Sheet Index", "LIST OF DRAWINGS",
                        "drawing list"):
            with self.subTest(heading=heading):
                self.assertTrue(si.looks_like_index("%s\nA101" % heading))

    def test_text_with_no_index_heading_is_not_read_as_an_index(self):
        """A page is recognised as an index, never assumed to be one."""
        self.assertFalse(si.looks_like_index("GROUND FLOOR PLAN\nA101\nA102"))
        self.assertEqual(si.index_entries("GROUND FLOOR PLAN\nA101"), [])

    def test_index_entries_preserve_the_verbatim_declared_text(self):
        entries = si.index_entries(INDEX_TEXT)
        texts = {e["reference_text"] for e in entries}
        self.assertIn("A101", texts)
        self.assertIn("JAN18", texts, "a false candidate is still read verbatim")

    def test_the_same_identifier_is_not_emitted_twice(self):
        entries = si.index_entries("DRAWING INDEX\nA101\nA101\nA-101")
        self.assertEqual(len([e for e in entries if e["sheet_token"] == "A101"]), 1)


class _RegisterCase(unittest.TestCase):

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_sheetid_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.store = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"index"), filename="index.txt"),
                    self.app, owner="t", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Sheet Identity")
        self.project_id = self.document.project_id
        self.index_source = self.store.get(self.project_id).sources[0]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _add(self, name, removed=False):
        workspace = self.store.get(self.project_id)
        source = self.store.add_source(workspace, name=name, file_path=None,
                                       kind="unclassified", actor="t")
        if removed:
            workspace = self.store.get(self.project_id)
            self.store.remove_source(workspace, source["id"], actor="t",
                                     reason="superseded")
        return source

    def _register(self, text=INDEX_TEXT, dry_run=False):
        workspace = self.store.get(self.project_id)
        with patch.object(si, "recovered_text_for", lambda *_a, **_k: text):
            return si.register_sheet_index(
                self.store, workspace, self.index_source["id"],
                actor="t", dry_run=dry_run)

    def _refs(self):
        return self.store.source_references_for_source(
            self.store.get(self.project_id), self.index_source["id"])


class Resolution(_RegisterCase):

    def test_an_index_entry_resolves_to_the_source_that_answers_to_it(self):
        self._add("212109 A101 SITE PLAN.pdf")
        report = self._register()
        self.assertEqual(len(report["resolved"]), 1)
        resolved = report["resolved"][0]
        self.assertEqual(resolved["reference_text"], "A101")
        self.assertEqual(resolved["resolution_status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(resolved["resolved_target_type"], "source")

    def test_a_date_shaped_candidate_creates_no_link(self):
        """`JAN18` matches a sheet shape and names no Source. Measured on the
        real index, where 90 such candidates all correctly abstained."""
        self._add("212109 A101 SITE PLAN.pdf")
        report = self._register()
        not_found = {r["reference_text"] for r in report["not_found"]}
        self.assertIn("JAN18", not_found)
        for reference in report["not_found"]:
            with self.subTest(text=reference["reference_text"]):
                self.assertEqual(reference["resolved_target_ids"], [])

    def test_a_postal_code_shaped_candidate_creates_no_link(self):
        self._add("212109 A101 SITE PLAN.pdf")
        report = self._register()
        self.assertIn("M2K", {r["reference_text"] for r in report["not_found"]})

    def test_an_entry_with_no_source_present_stays_unresolved(self):
        self._add("212109 A101 SITE PLAN.pdf")
        report = self._register()
        self.assertIn("S301", {r["reference_text"] for r in report["not_found"]})

    def test_two_sources_answering_to_one_identifier_are_not_chosen_between(self):
        self._add("212109 A101 SITE PLAN.pdf")
        self._add("A101.pdf")
        report = self._register()
        self.assertTrue(report["ambiguous"])
        ambiguous = report["ambiguous"][0]
        self.assertEqual(ambiguous["resolution_status"],
                         RESOLUTION_STATUS_RESOLVED_MULTIPLE)
        self.assertEqual(len(ambiguous["resolved_target_ids"]), 2)

    def test_a_removed_source_does_not_become_the_identity_target(self):
        """`eligible_targets` already excludes removed Sources, so a stale one
        cannot silently become the active target."""
        self._add("212109 A101 SITE PLAN.pdf", removed=True)
        report = self._register()
        self.assertEqual(report["resolved"], [])
        self.assertIn("A101", {r["reference_text"] for r in report["not_found"]})

    def test_a_source_from_another_project_is_unreachable(self):
        other = CaseWorkspaceStore(self.tmp)
        with patch.object(BHiveParser, "parse", _fake_parse):
            with self.app.app_context():
                foreign = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"x"), filename="other.txt"),
                    self.app, owner="t", operating_environment=None,
                    container_state=CONTAINER_STATE_BLACK_BOX,
                    project_name="Other")
        workspace = other.get(foreign.project_id)
        other.add_source(workspace, name="212109 A101 SITE PLAN.pdf",
                         file_path=None, kind="unclassified", actor="t")
        report = self._register()
        self.assertEqual(report["resolved"], [],
                         "a Source in another project must be unreachable")

    def test_the_index_source_does_not_resolve_to_itself(self):
        report = self._register(text="DRAWING INDEX\nA101")
        self.assertEqual(report["resolved"], [])

    def test_a_dry_run_writes_nothing(self):
        self._add("212109 A101 SITE PLAN.pdf")
        report = self._register(dry_run=True)
        self.assertTrue(report["resolved"])
        self.assertEqual(self._refs(), [])


class Provenance(_RegisterCase):

    def test_every_record_says_where_it_came_from_and_why(self):
        self._add("212109 A101 SITE PLAN.pdf")
        self._register()
        references = self._refs()
        self.assertTrue(references)
        for reference in references:
            with self.subTest(ref=reference["reference_text"]):
                self.assertEqual(reference["origin_context"]["origin"],
                                 si.REGISTER_METHOD)
                self.assertEqual(reference["origin_context"]["location_type"],
                                 "drawing_index")
                self.assertEqual(reference["extractor_version"], si.REGISTER_VERSION)
                self.assertEqual(reference["reference_type"], REFERENCE_TYPE_SHEET)
                self.assertTrue(reference["reference_text"])

    def test_the_declared_text_is_never_rewritten(self):
        self._add("212109 A101 SITE PLAN.pdf")
        self._register()
        texts = {r["reference_text"] for r in self._refs()}
        self.assertIn("A101", texts)
        self.assertNotIn("212109 A101 SITE PLAN.pdf", texts,
                         "the index said A101; the record must say what it said")

    def test_registration_is_idempotent(self):
        self._add("212109 A101 SITE PLAN.pdf")
        self._register()
        first = len(self._refs())
        self._register()
        self.assertEqual(len(self._refs()), first)


class IdentityOnly(unittest.TestCase):
    """Identity is not reference, relationship meaning, or discrepancy."""

    def test_no_relationship_is_created(self):
        import ast

        tree = ast.parse((_REPO_ROOT / "services" / "sheet_identity.py").read_text(
            encoding="utf-8"))
        called = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Name):
                    called.add(func.id)
                elif isinstance(func, ast.Attribute):
                    called.add(func.attr)
        for forbidden in ("record_evidence_relationship", "record_relationship",
                          "confirm_relationship", "record_investigation_claim"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, called)

    def test_no_magnitude_scale_or_discrepancy_vocabulary(self):
        source = (_REPO_ROOT / "services" / "sheet_identity.py").read_text(
            encoding="utf-8")
        window = source[source.index("def register_sheet_index"):]
        for forbidden in ("discrepanc", "deviates_from", "contradicts",
                          "scale_value", "calibrat", "millimet", "magnitude"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, window)

    def test_no_external_egress(self):
        source = (_REPO_ROOT / "services" / "sheet_identity.py").read_text(
            encoding="utf-8")
        for forbidden in ("requests", "urlopen", "httpx", "socket",
                          "call_gemini_json", "read_sheet", "llm_gateway"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


class TheGeneralParserIsNotWidened(unittest.TestCase):
    """The bare-token rejection exists for a reason and is still in force."""

    def test_a_bare_token_in_prose_is_still_not_a_sheet_citation(self):
        from services.case_workspace import parse_source_reference_text

        candidates = parse_source_reference_text(
            "The wall assembly A101 shall be installed per manufacturer.",
            include_drawing_tokens=False)
        self.assertEqual([c for c in candidates
                          if c["reference_type"] == REFERENCE_TYPE_SHEET], [])

    def test_a_keyword_led_citation_still_reads_as_before(self):
        from services.case_workspace import parse_source_reference_text

        candidates = parse_source_reference_text("See Drawing A-501 for detail.")
        sheets = [c for c in candidates if c["reference_type"] == REFERENCE_TYPE_SHEET]
        self.assertEqual(len(sheets), 1)
        self.assertEqual(sheets[0]["candidate_targets"], ["A-501"])

    def test_the_known_sheets_consumption_rule_is_intact(self):
        """A sheet naming ITSELF must not become a schedule-mark orphan."""
        from services.case_workspace import parse_source_reference_text

        candidates = parse_source_reference_text(
            "A-101", include_drawing_tokens=True, known_sheets={"A-101"})
        self.assertEqual(candidates, [])

    def test_supplying_candidates_is_opt_in_and_the_default_path_parses(self):
        source = (_REPO_ROOT / "services" / "case_workspace.py").read_text(
            encoding="utf-8")
        self.assertIn("if candidates is None:", source)
        self.assertIn("candidates: Optional[list[dict]] = None,", source)


if __name__ == "__main__":
    unittest.main()
