"""
CLAUDE-P26 - hermetic tests for the structured-output reliability fix in
services/bhive_parser.py's _check_consistency: classification-based
parsing (services/consistency_response_parser.py) instead of a single
strict json.loads, plus one bounded retry when the response is
genuinely unresolvable (multiple materially conflicting JSON blocks, or
no recoverable JSON at all).

The real, billed controlled experiment that investigated this and ruled
out tool-use as a fix lives in tools/self_test_structured_output_
reliability_experiment.py - hand-run, never invoked by the automated
suite. These tests only prove the parsing/retry logic behaves correctly
against mocked responses - never a real model call.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from services.bhive_parser import BHiveParser, RequirementItem


def _mock_response(text: str, stop_reason: str = "end_turn") -> MagicMock:
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = stop_reason
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return fake_response


def _items() -> list[RequirementItem]:
    return [
        RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
        RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
    ]


VALID_FLAG_JSON = json.dumps([{
    "a": "r1", "b": "r2", "explanation": "conflict",
    "requirement_a_evidence": "x", "requirement_b_evidence": "y",
    "requirement_a_obligation": "o1", "requirement_b_obligation": "o2",
    "requirement_a_scope": "none stated", "requirement_b_scope": "none stated",
    "scopes_overlap": True, "scope_reconciliation_reasoning": "both unqualified, fully overlap",
    "reconciliation_checked": True,
}])


class ValidJsonPlusHarmlessProseTests(unittest.TestCase):
    """The exact real pattern this investigation found: previously
    discarded outright by strict json.loads, now correctly recovered."""

    def test_trailing_self_correction_prose_after_empty_array_is_accepted(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        text = "[]\n\nWait - I need to reconsider. The scopes are disjoint, so this is correct."
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(text)
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])
        MockClient.return_value.messages.create.assert_called_once()  # no retry needed

    def test_trailing_prose_after_a_real_flag_is_accepted_and_flag_parsed(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        text = f"{VALID_FLAG_JSON}\n\nThat's my final answer."
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(text)
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(len(flags), 1)
        MockClient.return_value.messages.create.assert_called_once()


class MultipleEquivalentBlocksTests(unittest.TestCase):
    def test_two_empty_arrays_with_reconsideration_between_them_use_the_last(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        text = "[]\n\nActually wait, let me double check.\n\n[]"
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(text)
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])
        MockClient.return_value.messages.create.assert_called_once()


class ConflictingBlocksTriggerBoundedRetryTests(unittest.TestCase):
    def test_conflicting_blocks_retry_once_and_use_the_clean_retry_result(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        first_text = f"{VALID_FLAG_JSON}\n\nWait, reconsidering...\n\n[]"  # differing conclusions
        second_text = "[]"  # retry comes back clean and unambiguous
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = [
                _mock_response(first_text), _mock_response(second_text),
            ]
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)

    def test_conflicting_blocks_both_attempts_stay_unresolved_gives_up_gracefully(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        conflicting_text = f"{VALID_FLAG_JSON}\n\nWait, reconsidering...\n\n[]"
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = [
                _mock_response(conflicting_text), _mock_response(conflicting_text),
            ]
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertFalse(checked)
        self.assertEqual(flags, [])
        self.assertEqual(note, "Skipped: model returned invalid output after one retry.")
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)

    def test_unusable_output_retries_and_recovers(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = [
                _mock_response("I could not determine any contradictions."),  # UNUSABLE
                _mock_response("[]"),
            ]
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)

    def test_unusable_both_attempts_gives_up_gracefully_without_crashing(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                "I could not determine any contradictions."
            )
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertFalse(checked)
        self.assertEqual(flags, [])
        self.assertEqual(note, "Skipped: model returned invalid output after one retry.")
        self.assertEqual(MockClient.return_value.messages.create.call_count, 2)


class TruncatedButRepairableTests(unittest.TestCase):
    def test_truncated_trailing_array_is_repaired_without_retrying(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        truncated = VALID_FLAG_JSON[:-1]  # drop the final closing "]"
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(truncated)
            flags, checked, note = parser._check_consistency(_items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(len(flags), 1)
        MockClient.return_value.messages.create.assert_called_once()  # repaired in place, no retry needed


class UsageSinkProvenanceTests(unittest.TestCase):
    def test_usage_sink_records_category_and_no_retry_when_first_attempt_resolves(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response("[]")
            sink: dict = {}
            parser._check_consistency(_items(), usage_sink=sink)  # noqa: SLF001
        self.assertEqual(sink["response_category"], "single_valid_json")
        self.assertFalse(sink["retried"])
        self.assertIsNone(sink["retry_original_category"])
        self.assertIsNone(sink["raw_response_text_first_attempt"])

    def test_usage_sink_records_retry_provenance_including_first_attempt_raw_text(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        conflicting_text = f"{VALID_FLAG_JSON}\n\nWait, reconsidering...\n\n[]"
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = [
                _mock_response(conflicting_text), _mock_response("[]"),
            ]
            sink: dict = {}
            parser._check_consistency(_items(), usage_sink=sink)  # noqa: SLF001
        self.assertTrue(sink["retried"])
        self.assertEqual(sink["retry_original_category"], "multiple_conflicting_json")
        self.assertEqual(sink["raw_response_text_first_attempt"], conflicting_text)
        self.assertEqual(sink["raw_response_text"], "[]")
        self.assertEqual(sink["response_category"], "single_valid_json")


if __name__ == "__main__":
    unittest.main()
