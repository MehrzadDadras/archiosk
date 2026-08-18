"""
CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01 - relevance-scored Composer
evidence selection, replacing the old plain-registration-order slice
(services.conversational_turn.select_relevant_document_evidence).

Root cause this replaces: additional_document_evidence was always built
in Source-registration order, and every prompt-builder took a plain
[:15] slice of it - a document registered after the first 15 could
NEVER reach Composer's grounding prompt regardless of relevance,
recency, or being the exact document the reviewer named. Reproduced
live on North Bayview (CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01 +
CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01): a real question naming
a real, recently-registered workbook produced an honest-but-wrong
"not present in any of the extracted documents" answer.

Covers both the unit-level scoring model and the governing prompt's own
"North Bayview proof games" A-H, using synthetic evidence shaped exactly
like gather_project_evidence's own real output (not a different shape a
real caller would never produce).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from services.conversational_turn import (
    _is_explicit_name_match,
    _significant_words,
    select_relevant_document_evidence,
)


def _doc(filename, excerpts, source_id=None, added_at=None, document_authority=None, relative_path=None):
    return {
        "filename": filename,
        "relative_path": relative_path,
        "excerpts": excerpts,
        "source_id": source_id or filename,
        "added_at": added_at,
        "document_authority": document_authority,
    }


class ScoringPrimitivesTests(unittest.TestCase):
    def test_significant_words_drops_stopwords_and_short_tokens(self):
        words = _significant_words("What is the RFP schedule?")
        self.assertNotIn("what", words)
        self.assertNotIn("is", words)
        self.assertNotIn("the", words)
        self.assertIn("rfp", words)
        self.assertIn("schedule", words)

    def test_explicit_match_requires_both_count_and_ratio(self):
        # A short, generic filename ("rfi-log") should not "explicitly
        # match" a question that only shares one incidental word with it.
        doc_words = _significant_words("rfi-log-v4")
        question_words = _significant_words("What does the log say about drainage?")
        self.assertFalse(_is_explicit_name_match(doc_words, question_words))

        # Most of the filename's own distinguishing words present -> match.
        full_question_words = _significant_words("What's in the rfi log v4?")
        self.assertTrue(_is_explicit_name_match(doc_words, full_question_words))


class SelectionModelTests(unittest.TestCase):
    """Game A - explicit newest workbook (unit-level version, no real
    ingestion needed to prove the scoring model itself)."""

    def test_explicitly_named_document_registered_last_still_selected(self):
        docs = [_doc(f"filler-{i}.pdf", [f"filler content {i}"], added_at=f"2026-01-{i:02d}T00:00:00")
                for i in range(1, 20)]
        docs.append(_doc(
            "north-bayview-owner-reference-space-program-v1.0.xlsx",
            ["A='UD-001'; B='Facility-wide distribution of the 58 courtrooms by type'; C='PROPOSED'"],
            added_at="2026-08-17T00:00:00",
        ))
        selected = select_relevant_document_evidence(
            docs, "What unresolved Owner decisions are recorded in the North Bayview Owner Reference Space Program?",
        )
        names = [d["filename"] for d in selected]
        self.assertIn("north-bayview-owner-reference-space-program-v1.0.xlsx", names)

    def test_priority_document_gets_the_large_excerpt_allowance_not_just_first_eight(self):
        many_rows = [f"A='UD-{i:03d}'; B='item {i}'; C='PROPOSED'" for i in range(1, 81)]
        docs = [_doc("north-bayview-owner-reference-space-program-v1.0.xlsx", many_rows)]
        selected = select_relevant_document_evidence(
            docs, "What unresolved Owner decisions are recorded in the North Bayview Owner Reference Space Program?",
        )
        self.assertEqual(len(selected[0]["excerpts"]), 80)
        self.assertIn("UD-080", selected[0]["excerpts"][-1])  # the LAST row, not cut off

    def test_non_priority_document_still_gets_the_bounded_default_excerpt_cap(self):
        many_rows = [f"row {i} about drainage" for i in range(1, 50)]
        docs = [
            _doc("unrelated-report.pdf", many_rows),
            _doc("north-bayview-owner-reference-space-program-v1.0.xlsx", ["UD-001 courtroom allocation"]),
        ]
        selected = select_relevant_document_evidence(
            docs, "What unresolved Owner decisions are recorded in the North Bayview Owner Reference Space Program?",
        )
        unrelated = next(d for d in selected if d["filename"] == "unrelated-report.pdf")
        self.assertEqual(len(unrelated["excerpts"]), 8)  # unchanged default, not the 80-row allowance


class GameBOldGoverningRfpTests(unittest.TestCase):
    def test_older_authoritative_document_still_retrieved_when_relevant(self):
        docs = [_doc(
            "RFP-27-114-North-Bayview-Courthouse.pdf",
            ["Section 14: Payment mechanism and performance security requirements."],
            added_at="2026-01-01T00:00:00",  # oldest
        )]
        for i in range(1, 30):
            docs.append(_doc(f"newer-doc-{i}.pdf", [f"unrelated content {i}"], added_at=f"2026-08-{i % 28 + 1:02d}T00:00:00"))
        selected = select_relevant_document_evidence(docs, "What does the RFP say about the payment mechanism?")
        names = [d["filename"] for d in selected]
        self.assertIn("RFP-27-114-North-Bayview-Courthouse.pdf", names)


class GameCAddendumSpecificTests(unittest.TestCase):
    def test_named_addendum_wins_over_registration_order(self):
        docs = [
            _doc("Addendum-01.pdf", ["Addendum 1 clarifies site access hours."], added_at="2026-01-01T00:00:00"),
            _doc("Addendum-02.pdf", ["Addendum 2 revises the courtroom count to 58."], added_at="2026-01-02T00:00:00"),
            _doc("Addendum-03.pdf", ["Addendum 3 extends the submission deadline."], added_at="2026-01-03T00:00:00"),
        ]
        selected = select_relevant_document_evidence(docs, "What does Addendum 2 change about the courtroom count?")
        self.assertEqual(selected[0]["filename"], "Addendum-02.pdf")  # highest-scored, first in the list


class GameDAmbiguousBroadQuestionTests(unittest.TestCase):
    def test_broad_question_still_returns_a_bounded_non_empty_set(self):
        docs = [_doc(f"doc-{i}.pdf", [f"content {i}"], added_at=f"2026-01-{i:02d}T00:00:00") for i in range(1, 30)]
        selected = select_relevant_document_evidence(docs, "Tell me about this project.")
        self.assertGreater(len(selected), 0)
        self.assertLessEqual(len(selected), 15)  # the default cap, never unbounded


class GameECurrentOpenDocumentTests(unittest.TestCase):
    def test_currently_open_source_selected_even_without_being_named(self):
        docs = [_doc(f"filler-{i}.pdf", [f"content {i}"], source_id=f"src-{i}", added_at=f"2026-01-{i:02d}T00:00:00")
                for i in range(1, 20)]
        docs.append(_doc("financial-model-template-v1.xlsx", ["Row: Summary tab"], source_id="src-open"))
        selected = select_relevant_document_evidence(
            docs, "What does this show?", selected_source_id="src-open",
        )
        self.assertIn("financial-model-template-v1.xlsx", [d["filename"] for d in selected])

    def test_currently_open_source_also_matchable_by_name_when_id_unavailable(self):
        docs = [_doc(f"filler-{i}.pdf", [f"content {i}"]) for i in range(1, 20)]
        docs.append(_doc("financial-model-template-v1.xlsx", ["Row: Summary tab"]))
        selected = select_relevant_document_evidence(
            docs, "What does this show?", selected_source_name="financial-model-template-v1.xlsx",
        )
        self.assertIn("financial-model-template-v1.xlsx", [d["filename"] for d in selected])


class GameF40PlusDocumentProjectTests(unittest.TestCase):
    def test_evidence_beyond_position_15_is_selectable(self):
        docs = [_doc(f"doc-{i}.pdf", [f"unrelated filler content {i}"], added_at=f"2026-01-{(i % 28) + 1:02d}T00:00:00")
                for i in range(1, 41)]
        # Position 36 of 40 - well past the old hard [:15] cutoff.
        docs.insert(35, _doc(
            "north-bayview-owner-reference-space-program-v1.0.xlsx",
            ["UD-001 unresolved owner decision about courtroom allocation"],
        ))
        selected = select_relevant_document_evidence(
            docs, "What unresolved Owner decisions are recorded in the North Bayview Owner Reference Space Program?",
        )
        self.assertIn("north-bayview-owner-reference-space-program-v1.0.xlsx", [d["filename"] for d in selected])


class GameGProjectIsolationTests(unittest.TestCase):
    def test_selection_never_reaches_outside_the_list_it_was_given(self):
        # By construction: this function has no project/store access of
        # its own - it operates ONLY on the list passed in. A caller that
        # (correctly, as every real caller already does) builds that list
        # from a single workspace's own evidence_items structurally
        # cannot leak another project's evidence into it.
        project_a_docs = [_doc("a-only.pdf", ["Project A content"])]
        project_b_docs = [_doc("b-only.pdf", ["Project B content"])]
        selected_a = select_relevant_document_evidence(project_a_docs, "Tell me about this project.")
        selected_b = select_relevant_document_evidence(project_b_docs, "Tell me about this project.")
        self.assertEqual([d["filename"] for d in selected_a], ["a-only.pdf"])
        self.assertEqual([d["filename"] for d in selected_b], ["b-only.pdf"])


class GameHNoHallucinatedAuthorityTests(unittest.TestCase):
    def test_proposed_status_text_passes_through_excerpts_unmodified(self):
        raw_excerpt = "A='UD-001'; B='Facility-wide distribution'; C='PROPOSED'; D='No binding source'"
        docs = [_doc("north-bayview-owner-reference-space-program-v1.0.xlsx", [raw_excerpt])]
        selected = select_relevant_document_evidence(
            docs, "What unresolved Owner decisions are recorded in the North Bayview Owner Reference Space Program?",
        )
        self.assertEqual(selected[0]["excerpts"][0], raw_excerpt)  # byte-for-byte, never rewritten

    def test_behavioral_contract_states_authority_is_not_upgraded_by_selection(self):
        from services.project_qa import BEHAVIORAL_CONTRACT
        from services.conversational_turn import CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT
        for contract in (BEHAVIORAL_CONTRACT, CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT):
            self.assertIn("non-binding", contract)
            self.assertIn("never present it as a confirmed requirement", contract)


class AllDocumentNamesHonestyTests(unittest.TestCase):
    """Section 3/7: every document's name is discoverable even if its
    excerpts didn't make the selected set, so GO can say "exists but
    insufficient content" rather than implying non-existence."""

    def test_prompt_lists_every_document_name_even_when_not_selected(self):
        from services.project_qa import _build_prompt

        docs = [_doc(f"filler-{i}.pdf", [f"content {i}"], relative_path=f"filler-{i}.pdf") for i in range(1, 20)]
        prompt = _build_prompt(
            question="What unresolved Owner decisions are recorded?",
            document_filename="RFP.pdf",
            candidate_requirements=[], governed_requirements=[], milestones=[],
            additional_document_evidence=docs,
        )
        for i in range(1, 20):
            self.assertIn(f"filler-{i}.pdf", prompt)  # named, even the ones whose excerpts got cut


if __name__ == "__main__":
    unittest.main()
