"""
CLAUDE-P26 - hermetic tests for tests/self_test/structured_output_
classifier.py. Pure text fixtures, no network calls, no model.
"""
from __future__ import annotations

import unittest

from services.consistency_response_parser import (
    MALFORMED_BUT_REPAIRABLE,
    MULTIPLE_CONFLICTING_JSON,
    MULTIPLE_EQUIVALENT_JSON,
    SINGLE_VALID_JSON,
    UNUSABLE,
    VALID_JSON_THEN_HARMLESS_PROSE,
    classify_response,
)


class SingleValidJsonTests(unittest.TestCase):
    def test_empty_array_is_single_valid(self):
        result = classify_response("[]")
        self.assertEqual(result.category, SINGLE_VALID_JSON)
        self.assertEqual(result.resolved_value, [])

    def test_array_with_entries_is_single_valid(self):
        text = '[{"a": "r1", "b": "r2", "scopes_overlap": true}]'
        result = classify_response(text)
        self.assertEqual(result.category, SINGLE_VALID_JSON)
        self.assertEqual(result.resolved_value, [{"a": "r1", "b": "r2", "scopes_overlap": True}])

    def test_code_fenced_array_is_single_valid(self):
        text = '```json\n[{"a": "r1", "b": "r2", "scopes_overlap": true}]\n```'
        result = classify_response(text)
        self.assertEqual(result.category, SINGLE_VALID_JSON)

    def test_brackets_inside_quoted_evidence_do_not_break_scanning(self):
        text = '[{"a": "r1", "b": "r2", "requirement_a_evidence": "rated for [40, 45] degF"}]'
        result = classify_response(text)
        self.assertEqual(result.category, SINGLE_VALID_JSON)
        self.assertEqual(result.resolved_value[0]["requirement_a_evidence"], "rated for [40, 45] degF")


class ValidJsonThenHarmlessProseTests(unittest.TestCase):
    def test_trailing_prose_after_valid_array_is_harmless(self):
        text = '[]\n\nWait - I need to reconsider. Actually the scopes are disjoint, so this is correct.'
        result = classify_response(text)
        self.assertEqual(result.category, VALID_JSON_THEN_HARMLESS_PROSE)
        self.assertEqual(result.resolved_value, [])

    def test_leading_prose_before_valid_array_is_harmless(self):
        text = 'Let me check each pair carefully.\n\n[]'
        result = classify_response(text)
        self.assertEqual(result.category, VALID_JSON_THEN_HARMLESS_PROSE)
        self.assertEqual(result.resolved_value, [])


class MultipleEquivalentJsonTests(unittest.TestCase):
    def test_two_empty_arrays_are_equivalent(self):
        text = '[]\n\nWait, let me reconsider.\n\n[]'
        result = classify_response(text)
        self.assertEqual(result.category, MULTIPLE_EQUIVALENT_JSON)
        self.assertEqual(result.resolved_value, [])

    def test_two_arrays_with_same_flagged_pair_and_overlap_are_equivalent(self):
        block = '[{"a": "r1", "b": "r2", "scopes_overlap": false}]'
        text = f'{block}\n\nActually let me restate that.\n\n{block}'
        result = classify_response(text)
        self.assertEqual(result.category, MULTIPLE_EQUIVALENT_JSON)
        # The LAST equivalent block is used as the model's settled answer.
        self.assertEqual(result.resolved_value, [{"a": "r1", "b": "r2", "scopes_overlap": False}])


class MultipleConflictingJsonTests(unittest.TestCase):
    def test_differing_conclusions_are_conflicting_and_unresolved(self):
        first = '[{"a": "r1", "b": "r2", "scopes_overlap": false}]'
        second = '[]'
        text = f'{first}\n\nWait, reconsidering...\n\n{second}'
        result = classify_response(text)
        self.assertEqual(result.category, MULTIPLE_CONFLICTING_JSON)
        self.assertIsNone(result.resolved_value, "must not silently pick a side when conclusions differ")

    def test_differing_scopes_overlap_on_same_pair_is_conflicting(self):
        first = '[{"a": "r1", "b": "r2", "scopes_overlap": true}]'
        second = '[{"a": "r1", "b": "r2", "scopes_overlap": false}]'
        text = f'{first}\n\n{second}'
        result = classify_response(text)
        self.assertEqual(result.category, MULTIPLE_CONFLICTING_JSON)
        self.assertIsNone(result.resolved_value)


class MalformedButRepairableTests(unittest.TestCase):
    def test_truncated_array_missing_closing_bracket_is_repaired(self):
        text = '[{"a": "r1", "b": "r2", "scopes_overlap": false}'  # cut off mid-array, no closing ]
        result = classify_response(text)
        self.assertEqual(result.category, MALFORMED_BUT_REPAIRABLE)
        self.assertEqual(result.repaired_value, [{"a": "r1", "b": "r2", "scopes_overlap": False}])

    def test_truncated_second_object_is_trimmed_back_to_last_complete_one(self):
        text = (
            '[{"a": "r1", "b": "r2", "scopes_overlap": false}, '
            '{"a": "r3", "b": "r4", "scopes_overlap": tr'  # truncated mid-value
        )
        result = classify_response(text)
        self.assertEqual(result.category, MALFORMED_BUT_REPAIRABLE)
        self.assertEqual(result.repaired_value, [{"a": "r1", "b": "r2", "scopes_overlap": False}])


class UnusableTests(unittest.TestCase):
    def test_pure_prose_with_no_brackets_is_unusable(self):
        result = classify_response("I could not determine any contradictions in this batch.")
        self.assertEqual(result.category, UNUSABLE)
        self.assertIsNone(result.resolved_value)

    def test_truncated_with_no_complete_object_at_all_is_unusable(self):
        text = '[{"a": "r1", "b": "r2", "scopes_overlap": fal'  # cut off before even one object closes
        result = classify_response(text)
        self.assertEqual(result.category, UNUSABLE)


if __name__ == "__main__":
    unittest.main()
