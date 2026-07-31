"""
CLAUDE-P40 - source-line reflow: repairs visual line wrapping in
BHiveParser._segment so a sentence spanning multiple physical lines in
a PDF/hard-wrapped-TXT source becomes ONE RequirementItem instead of
being shredded into separate fragments (sometimes independently
classified into different, contradictory categories - confirmed live
against a real ingested document, see this stage's own final report).

Exercises the required source shapes: hard-wrapped prose, numbered/
lettered clause markers, bullets, colon-introduced lists, exceptions,
consecutive separate obligations, hyphenated word breaks vs. real
hyphenated compounds, and the page-break/metadata-gap boundary -
before/after via _segment (pure, no classification) plus a couple of
full .parse() end-to-end checks with the rule-based classifier (no
API key needed, deterministic).

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

import re

from services.bhive_parser import BHiveParser, _reflow_wrapped_lines

_LEADING_BULLET_RE = re.compile(r"^[-*•]\s*")


class ReflowWrappedLinesUnitTests(unittest.TestCase):
    """Direct tests of _reflow_wrapped_lines - no parser instance needed."""

    def _rows(self, *lines: str, start: int = 1) -> list[tuple[int, str, str]]:
        return [
            (start + i, line.strip(), _LEADING_BULLET_RE.sub("", line.strip()))
            for i, line in enumerate(lines)
        ]

    def test_hard_wrapped_two_line_sentence_is_rejoined(self):
        rows = self._rows(
            "The Design-Builder shall provide all labor, materials, and",
            "equipment required to complete the renovation.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        start, end, text = result[0]
        self.assertEqual((start, end), (1, 2))
        self.assertEqual(
            text,
            "The Design-Builder shall provide all labor, materials, and "
            "equipment required to complete the renovation.",
        )

    def test_three_line_wrap_matches_the_real_live_defect(self):
        # The exact sentence observed fragmented into 3 pieces during
        # this stage's own live browser walkthrough.
        rows = self._rows(
            "The Design-Builder shall provide all labor, materials, and equipment required to",
            "complete the Riverside Community Library renovation, including structural",
            "upgrades, mechanical replacement, and accessibility improvements.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        start, end, text = result[0]
        self.assertEqual((start, end), (1, 3))
        self.assertTrue(text.startswith("The Design-Builder shall provide all labor"))
        self.assertTrue(text.endswith("accessibility improvements."))

    def test_numbered_clause_marker_is_never_merged_into_previous_line(self):
        rows = self._rows(
            "Background information follows",  # no terminal punctuation
            "2.1 Proponents shall submit a technical narrative.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[1][2].startswith("2.1 Proponents"))

    def test_lettered_subclause_marker_is_never_merged(self):
        rows = self._rows(
            "The following exceptions apply",
            "(a) work performed under emergency conditions.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)
        self.assertTrue(result[1][2].startswith("(a) work performed"))

    def test_bullet_marker_is_never_merged(self):
        rows = self._rows(
            "Deliverables include the following items",  # no colon, no period
            "- a design narrative describing the proposed methodology",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)

    def test_colon_introduced_list_intro_stays_separate_from_bullet_items(self):
        rows = self._rows(
            "Submission Requirements: Proponents shall submit the following:",
            "- a completed pricing form",
            "- a compliance matrix",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 3)

    def test_consecutive_complete_obligations_are_not_merged(self):
        rows = self._rows(
            "The Design-Builder shall provide all structural drawings.",
            "The Owner shall provide the site survey.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)

    def test_two_capitalized_clauses_without_terminal_punctuation_are_not_merged(self):
        # Malformed/unusual source (missing a period) - the next line
        # still reads as a fresh, capitalized obligation, not a
        # continuation, so it must not be swallowed into the first.
        rows = self._rows(
            "The Design-Builder shall provide all structural drawings",
            "The Owner shall provide the site survey.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)

    def test_hyphenated_word_break_across_lines_is_rejoined_with_no_inserted_space(self):
        # A hyphen directly attached to a letter at line-end is an
        # unambiguous word-break signal - joined with no inserted space,
        # the hyphen itself never stripped (see this module's own
        # comment on why dehyphenation-by-guessing isn't attempted).
        rows = self._rows("All structural steel shall conform to CSA G40.21 350W struc-", "ture.")
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        self.assertIn("struc-ture.", result[0][2])

    def test_real_hyphenated_compound_at_line_end_is_correctly_reconstructed(self):
        # "Design-Builder" wrapping exactly like a word-break hyphen
        # would - the same safe, no-inserted-space join reconstructs the
        # real compound term exactly, never "DesignBuilder" and never
        # left split across two separate items.
        rows = self._rows("The Design-", "Builder shall provide all labor and materials.")
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        self.assertIn("Design-Builder shall provide", result[0][2])
        self.assertNotIn("DesignBuilder", result[0][2])

    def test_exception_clause_wrapped_across_lines_is_rejoined(self):
        rows = self._rows(
            "This requirement does not apply to work performed under emergency conditions,",
            "except where explicitly approved by the Sponsor in writing.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        self.assertIn("except where explicitly approved", result[0][2])

    def test_relative_date_obligation_is_preserved_verbatim_when_wrapped(self):
        rows = self._rows(
            "Substantial performance shall be achieved no later than 18 months",
            "after contract award.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 1)
        self.assertIn("18 months after contract award.", result[0][2])

    def test_gap_in_line_numbers_prevents_a_merge(self):
        # Simulates a page-break/heading/metadata line that _segment
        # already excludes upstream, leaving a real gap in line numbers -
        # the two real paragraph halves around it must not merge.
        rows = [
            (1, "The Design-Builder shall provide all labor, materials, and", "The Design-Builder shall provide all labor, materials, and"),
            (5, "equipment required to complete the work.", "equipment required to complete the work."),
        ]
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)

    def test_max_reflow_lines_safety_cap(self):
        # A pathological run of 20 never-terminated lowercase-continuing
        # lines must not merge into one unbounded chunk.
        rows = self._rows(*(f"word{i} and continues here without end" for i in range(20)))
        result = _reflow_wrapped_lines(rows)
        self.assertGreater(len(result), 1)
        for _start, _end, _text in result:
            pass  # no single group may exceed the cap
        max_line_count = max(end - start + 1 for start, end, _ in result)
        self.assertLessEqual(max_line_count, 12)

    def test_single_line_items_are_unaffected(self):
        rows = self._rows(
            "All structural steel shall conform to CSA G40.21 350W.",
            "Substantial performance shall be achieved within 18 months.",
        )
        result = _reflow_wrapped_lines(rows)
        self.assertEqual(len(result), 2)
        for start, end, _text in result:
            self.assertEqual(start, end)


class SegmentAndParseEndToEndTests(unittest.TestCase):
    """Confirms the reflow pass is actually wired into _segment/parse,
    end to end, using the rule-based classifier (no API key needed)."""

    def setUp(self):
        self.parser = BHiveParser(anthropic_api_key=None)

    def test_segment_returns_an_end_line_map_and_rejoins_wrapped_text(self):
        text = (
            "The Design-Builder shall provide all labor, materials, and equipment required to\n"
            "complete the Riverside Community Library renovation, including structural\n"
            "upgrades, mechanical replacement, and accessibility improvements.\n"
        )
        chunks, tables, end_line_map = self.parser._segment(text)
        self.assertEqual(len(chunks), 1)
        start_line, text_out = chunks[0]
        self.assertEqual(start_line, 1)
        self.assertEqual(end_line_map[start_line], 3)
        self.assertTrue(text_out.endswith("accessibility improvements."))

    def test_table_row_end_line_map_entries_are_identity(self):
        text = "| A | B |\n|---|---|\n| row1a | row1b |\n"
        chunks, tables, end_line_map = self.parser._segment(text)
        table_chunk = next(c for c in chunks if "row1a" in c[1])
        self.assertEqual(end_line_map[table_chunk[0]], table_chunk[0])

    def test_parse_produces_one_requirement_item_for_a_wrapped_sentence(self):
        raw = (
            "The Design-Builder shall provide all labor, materials, and equipment required to\n"
            "complete the Riverside Community Library renovation, including structural\n"
            "upgrades, mechanical replacement, and accessibility improvements.\n"
        ).encode("utf-8")
        document = self.parser.parse(raw, "rfp.txt")
        matches = [r for r in document.requirements if "accessibility improvements" in r.text]
        self.assertEqual(len(matches), 1)
        item = matches[0]
        self.assertEqual(item.source_line, 1)
        self.assertEqual(item.source_line_end, 3)
        self.assertTrue(item.text.startswith("The Design-Builder shall provide all labor"))

    def test_parse_single_line_requirement_has_matching_source_line_end(self):
        raw = b"All structural steel shall conform to CSA G40.21 350W.\n"
        document = self.parser.parse(raw, "rfp.txt")
        self.assertEqual(len(document.requirements), 1)
        item = document.requirements[0]
        self.assertEqual(item.source_line, item.source_line_end)

    def test_parse_does_not_merge_a_bare_numbered_heading_into_the_next_clause(self):
        raw = (
            "Section 2 - Technical Specification\n"
            "2.1 All structural steel shall conform to CSA G40.21 350W.\n"
        ).encode("utf-8")
        document = self.parser.parse(raw, "rfp.txt")
        texts = [r.text for r in document.requirements]
        self.assertFalse(any("Technical Specification 2.1" in t for t in texts))

    def test_reload_from_registry_defaults_source_line_end_for_old_data(self):
        # Old, pre-P40 saved JSON never wrote source_line_end - deserializing
        # via RequirementItem(**item) must not error, and the field must
        # default honestly to None rather than being fabricated.
        from services.bhive_parser import RequirementItem

        old_shape = {"id": "r1", "text": "x", "category": "other", "confidence": 0.5, "source_line": 1}
        item = RequirementItem(**old_shape)
        self.assertIsNone(item.source_line_end)


if __name__ == "__main__":
    unittest.main()
