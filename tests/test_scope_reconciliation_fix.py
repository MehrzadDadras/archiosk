"""
CLAUDE-P25 - hermetic tests for the structured scope-reconciliation fix
in services/bhive_parser.py: new ConsistencyFlag fields (requirement_a/
b_obligation, requirement_a/b_scope, scopes_overlap, scope_reconciliation_
reasoning) and the deterministic post-validation that drops any flag
lacking scope reasoning or whose own scopes_overlap=False contradicts
including it.

The real, billed controlled experiment that found this limitation and
validated the fix lives in tools/self_test_scope_reconciliation_
experiment.py - hand-run, never invoked by the automated suite. These
tests only prove the prompt carries the new instructions and that
parsing/post-validation behaves correctly - never a real model call.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from services.bhive_parser import BHiveParser, ConsistencyFlag, RequirementItem


class ConsistencyFlagNewFieldDefaultsTests(unittest.TestCase):
    def test_new_scope_fields_have_safe_defaults(self):
        flag = ConsistencyFlag(
            id="x", requirement_a_id="a", requirement_a_text="x",
            requirement_b_id="b", requirement_b_text="y", explanation="z",
        )
        self.assertEqual(flag.requirement_a_obligation, "")
        self.assertEqual(flag.requirement_b_obligation, "")
        self.assertEqual(flag.requirement_a_scope, "")
        self.assertEqual(flag.requirement_b_scope, "")
        self.assertIsNone(flag.scopes_overlap)
        self.assertEqual(flag.scope_reconciliation_reasoning, "")


class ScopeReconciliationPromptTests(unittest.TestCase):
    def _prompt(self) -> str:
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        return BHiveParser._build_consistency_prompt(items)

    def test_structured_scope_steps_present(self):
        prompt = self._prompt()
        self.assertIn("State each requirement's own obligation", prompt)
        self.assertIn("ACTUALLY OVERLAP", prompt)
        self.assertIn("scopes_overlap", prompt)
        self.assertIn("scope_reconciliation_reasoning", prompt)

    def test_all_six_scope_kinds_named(self):
        prompt = self._prompt()
        self.assertIn("occupied vs unoccupied hours", prompt)
        self.assertIn("normal vs emergency/maintenance mode", prompt)
        self.assertIn("one zone/system vs a different one", prompt)
        self.assertIn("temporary vs permanent", prompt)
        self.assertIn("general rule vs a specifically-named exception", prompt)
        self.assertIn("design/rated capability vs a", prompt)

    def test_dense_bundled_clause_warning_present(self):
        prompt = self._prompt()
        self.assertIn("bundles a rating/numeric obligation together with a protocol", prompt)


class ScopeDeterministicPostValidationTests(unittest.TestCase):
    """The actual enforcement: a flag is not accepted merely because the
    model included it in its output."""

    def _mock_response(self, payload) -> MagicMock:
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.stop_reason = "end_turn"
        fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        return fake_response

    def _items(self):
        return [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]

    def test_flag_with_full_scope_reasoning_and_overlap_true_is_accepted(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        payload = [{
            "a": "r1", "b": "r2", "explanation": "conflict",
            "requirement_a_obligation": "r1 requires X", "requirement_b_obligation": "r2 requires not-X",
            "requirement_a_scope": "none stated", "requirement_b_scope": "none stated",
            "scopes_overlap": True,
            "scope_reconciliation_reasoning": "Neither requirement states any temporal, operational, spatial, or conditional limit, so both are unqualified and their scopes fully overlap.",
            "reconciliation_checked": True,
        }]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(self._items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(len(flags), 1)
        self.assertTrue(flags[0].scopes_overlap)
        self.assertIn("fully overlap", flags[0].scope_reconciliation_reasoning)

    def test_flag_missing_scope_reasoning_is_dropped(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        payload = [{
            "a": "r1", "b": "r2", "explanation": "conflict",
            "scopes_overlap": True, "reconciliation_checked": True,
            # scope_reconciliation_reasoning deliberately omitted
        }]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(self._items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])

    def test_flag_with_scopes_overlap_false_is_dropped_even_with_reasoning(self):
        """The exact self-contradiction pattern a real run exposed: the
        model's own structured field says the scopes do NOT overlap, yet
        it included the flag anyway. The code-level guard catches this
        regardless of what the prose reasoning says."""
        parser = BHiveParser(anthropic_api_key="fake-key")
        payload = [{
            "a": "r1", "b": "r2", "explanation": "conflict",
            "requirement_a_scope": "occupied hours only", "requirement_b_scope": "unoccupied hours only",
            "scopes_overlap": False,
            "scope_reconciliation_reasoning": "r1 applies only during occupied hours and r2 only during unoccupied hours - disjoint.",
            "reconciliation_checked": True,
        }]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(self._items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])

    def test_blank_scope_reasoning_string_is_also_dropped(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        payload = [{
            "a": "r1", "b": "r2", "explanation": "conflict",
            "scope_reconciliation_reasoning": "   ", "scopes_overlap": True, "reconciliation_checked": True,
        }]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(self._items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])

    def test_clean_empty_array_response_still_works(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response([])
            flags, checked, note = parser._check_consistency(self._items())  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
