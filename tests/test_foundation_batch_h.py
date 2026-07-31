"""
Foundation Batch H tests: table-aware extraction (.md + GFM tables) in
BHiveParser - the concrete gap named in the NREOCRC baseline adjudication
(Prompt 14): BHiveParser could not read .md files at all, and had no
notion of tables, so a document like NREOCRC-OPR-001.md's Functional
Program (a table of per-department room areas) was invisible to it
beyond meaningless per-line fragments.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

from services.bhive_parser import BHiveParser, ParsedDocument, extract_markdown_tables
from services.requirements_registry import RequirementsRegistry

NREOCRC_PATH = Path(__file__).parent / "fixtures" / "nreocrc" / "immutable_original" / "NREOCRC-OPR-001.md"


class MarkdownTableParserTests(unittest.TestCase):
    """Tests A-G: the pure extract_markdown_tables() function."""

    # A
    def test_a_simple_two_column_table(self):
        text = "| Field | Detail |\n|---|---|\n| Document ID | NREOCRC-OPR-001 |\n"
        tables = extract_markdown_tables(text)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["headers"], ["Field", "Detail"])
        self.assertEqual(tables[0]["rows"], [["Document ID", "NREOCRC-OPR-001"]])
        self.assertEqual(tables[0]["start_line"], 1)
        self.assertEqual(tables[0]["end_line"], 3)

    # B
    def test_b_alignment_row_variants_accepted(self):
        text = "| A | B | C |\n|:---|---:|:---:|\n| 1 | 2 | 3 |\n"
        tables = extract_markdown_tables(text)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["rows"], [["1", "2", "3"]])

    # C
    def test_c_empty_cells_preserved_not_dropped(self):
        text = "| A | B | C |\n|---|---|---|\n| 1 | | 3 |\n"
        tables = extract_markdown_tables(text)
        self.assertEqual(tables[0]["rows"], [["1", "", "3"]])

    # D
    def test_d_short_row_padded_not_fabricated(self):
        text = "| A | B | C |\n|---|---|---|\n| 1 | 2 |\n"
        tables = extract_markdown_tables(text)
        self.assertEqual(tables[0]["rows"], [["1", "2", ""]])

    # E
    def test_e_table_with_zero_data_rows(self):
        text = "| A | B |\n|---|---|\nSome unrelated paragraph.\n"
        tables = extract_markdown_tables(text)
        self.assertEqual(len(tables), 1)
        self.assertEqual(tables[0]["rows"], [])
        self.assertEqual(tables[0]["end_line"], 2)

    # F
    def test_f_multiple_tables_and_non_table_content(self):
        text = (
            "Intro paragraph, not a table.\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n\n"
            "Some prose between tables.\n\n"
            "| X | Y | Z |\n|---|---|---|\n| a | b | c |\n"
        )
        tables = extract_markdown_tables(text)
        self.assertEqual(len(tables), 2)
        self.assertEqual(tables[0]["headers"], ["A", "B"])
        self.assertEqual(tables[1]["headers"], ["X", "Y", "Z"])

    # G
    def test_g_lines_without_pipes_are_not_tables(self):
        text = "Just an ordinary paragraph.\nAnother line here.\n---\nA horizontal rule above.\n"
        self.assertEqual(extract_markdown_tables(text), [])


class SegmentTableAwarenessTests(unittest.TestCase):
    """Tests H-L: _segment excludes raw table lines and produces
    header-labeled row chunks; excludes ATX headings."""

    def setUp(self):
        self.parser = BHiveParser(anthropic_api_key=None)

    # H
    def test_h_raw_table_lines_excluded_from_naive_chunks(self):
        text = (
            "## Functional Program\n\n"
            "| Functional Group | Room / Space | Net Area (m2) |\n"
            "|---|---|---|\n"
            "| Public / Community | Public Lobby & Reception | 120 |\n"
        )
        chunks, tables, _ = self.parser._segment(text)
        self.assertEqual(len(tables), 1)
        chunk_texts = [c[1] for c in chunks]
        # The raw pipe-delimited row must never appear verbatim.
        self.assertFalse(any(t.startswith("| Public / Community |") for t in chunk_texts))
        # A header-labeled reconstruction must appear instead.
        self.assertTrue(any("Functional Group: Public / Community" in t for t in chunk_texts))
        self.assertTrue(any("Room / Space: Public Lobby & Reception" in t for t in chunk_texts))
        self.assertTrue(any("Net Area (m2): 120" in t for t in chunk_texts))

    # I
    def test_i_atx_heading_excluded(self):
        text = "## 12.1 Standby Power and Backup Systems\n\nContractor shall comply with this section.\n"
        chunks, _, _ = self.parser._segment(text)
        chunk_texts = [c[1] for c in chunks]
        self.assertFalse(any("Standby Power" in t for t in chunk_texts))
        self.assertTrue(any("Contractor shall comply" in t for t in chunk_texts))

    # J
    def test_j_row_chunk_line_numbers_match_source(self):
        text = "| A | B |\n|---|---|\n| row1a | row1b |\n| row2a | row2b |\n"
        chunks, _, _ = self.parser._segment(text)
        by_line = dict(chunks)
        self.assertIn("A: row1a | B: row1b", by_line[3])
        self.assertIn("A: row2a | B: row2b", by_line[4])

    # K
    def test_k_non_table_documents_are_unaffected(self):
        text = (
            b"Contractor shall provide licensed and insured labor for all work.\n"
            b"Work shall include demolition and site preparation.\n"
        ).decode("utf-8")
        chunks, tables, _ = self.parser._segment(text)
        self.assertEqual(tables, [])
        self.assertEqual(len(chunks), 2)

    # L
    def test_l_empty_header_column_skipped_in_label_not_whole_row(self):
        text = "|  | B |\n|---|---|\n| x | y |\n"
        chunks, _, _ = self.parser._segment(text)
        self.assertEqual(chunks[0][1], "B: y")


class MarkdownEndToEndTests(unittest.TestCase):
    """Tests M-P: full .parse() with a .md filename, including against
    the real, immutable NREOCRC corpus document (read-only - never
    modified)."""

    def setUp(self):
        self.parser = BHiveParser(anthropic_api_key=None)

    # M
    def test_m_md_extension_is_accepted(self):
        raw = "Contractor shall comply with applicable ASTM specifications.\n".encode("utf-8")
        document = self.parser.parse(raw, "sample.md")
        self.assertIsInstance(document, ParsedDocument)
        self.assertTrue(len(document.requirements) >= 1)

    # N
    def test_n_parse_includes_tables_field(self):
        raw = "| Field | Detail |\n|---|---|\n| Document ID | TEST-001 |\n".encode("utf-8")
        document = self.parser.parse(raw, "sample.md")
        self.assertEqual(len(document.tables), 1)
        self.assertEqual(document.tables[0]["headers"], ["Field", "Detail"])

    # O - real corpus file, byte-for-byte as committed, never modified here.
    def test_o_real_nreocrc_document_functional_program_table_extracted(self):
        raw_bytes = NREOCRC_PATH.read_bytes()
        document = self.parser.parse(raw_bytes, "NREOCRC-OPR-001.md")

        functional_program_tables = [
            t for t in document.tables
            if t["headers"][:2] == ["#", "Functional Group"]
        ]
        self.assertEqual(len(functional_program_tables), 1)
        table = functional_program_tables[0]

        # Row 20 (Prompt 13/14's own named case) is present with its real,
        # unmodified content - not fabricated to make this test pass.
        row_20 = next(r for r in table["rows"] if r[0] == "20")
        self.assertEqual(row_20[2], "Situational Awareness / Media Briefing Room")
        self.assertEqual(row_20[4], "65")

        # Confirms this closes the concrete adjudication gap: the row is
        # now real, structured, queryable data (headers[i] -> row[i]),
        # not lost inside an unparsed block of text.
        header_index = {name: i for i, name in enumerate(table["headers"])}
        self.assertEqual(row_20[header_index["Net Area (m²) each"]], "65")

    # P - the same table's rows are also present in the classify-ready
    # chunk stream, header-labeled, not as raw pipe syntax.
    def test_p_real_nreocrc_functional_program_rows_are_readable_chunks(self):
        raw_bytes = NREOCRC_PATH.read_bytes()
        text = raw_bytes.decode("utf-8")
        chunks, _, _ = self.parser._segment(text)
        chunk_texts = [c[1] for c in chunks]
        self.assertTrue(any("Room / Space: Public Lobby & Reception" in t for t in chunk_texts))
        self.assertFalse(any(t.strip().startswith("| 1 | Public / Community |") for t in chunk_texts))


class UploadReachabilityTests(unittest.TestCase):
    """
    Test R: the extraction capability above is worthless if the real
    upload path rejects .md before ever calling the parser - confirms
    config.ALLOWED_UPLOAD_EXTENSIONS actually allows it through, not just
    that BHiveParser can handle the bytes if somehow reached.
    """

    def test_r_md_reaches_the_parser_through_the_real_upload_path(self):
        import io

        import app as app_module

        flask_app = app_module.create_app("testing")
        self.assertIn(".md", flask_app.config["ALLOWED_UPLOAD_EXTENSIONS"])

        client = flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "read_only"

        data = {
            "file": (io.BytesIO(b"Contractor shall comply with applicable ASTM specifications.\n"), "sample.md"),
        }
        response = client.post("/upload", data=data, content_type="multipart/form-data")
        self.assertNotEqual(response.status_code, 400)


class RequirementsRegistryBackwardCompatibilityTests(unittest.TestCase):
    """Test Q: a document saved before Batch H (no "tables" key at all in
    its persisted JSON) loads cleanly with an empty tables list."""

    def test_q_legacy_document_without_tables_key_loads(self):
        import json
        import shutil
        import tempfile

        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_h_"))
        try:
            registry = RequirementsRegistry(tmp_dir)
            legacy_data = {
                "project_id": "legacy-project-h",
                "filename": "old.txt",
                "ingested_at": "2020-01-01T00:00:00+00:00",
                "requirements": [],
                "milestones": [],
                "consistency_flags": [],
                "consistency_checked": False,
                "consistency_note": None,
            }
            (tmp_dir / "legacy-project-h.json").write_text(json.dumps(legacy_data), encoding="utf-8")

            document = registry.get("legacy-project-h")
            self.assertEqual(document.tables, [])
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
