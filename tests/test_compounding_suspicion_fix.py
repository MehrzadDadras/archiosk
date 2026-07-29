"""
CLAUDE-P23 - hermetic tests for the compounding-suspicion production fix
in services/bhive_parser.py: verbatim per-pair evidence, an explicit
reconciliation-checked field, and a party/role-label guardrail extending
the existing wording guardrail.

The real, billed controlled experiment that found and confirmed this fix
lives in tools/self_test_compounding_suspicion_experiment.py - hand-run,
never invoked by the automated suite. These tests only prove the prompt
carries the new instructions and that parsing handles both the new
fields and older-shaped (pre-CLAUDE-P23) mocked responses without
breaking - never a real model call.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from services.bhive_parser import BHiveParser, ConsistencyFlag, RequirementItem


class ConsistencyFlagBackwardCompatibilityTests(unittest.TestCase):
    def test_new_fields_have_safe_defaults(self):
        flag = ConsistencyFlag(
            id="x", requirement_a_id="a", requirement_a_text="x",
            requirement_b_id="b", requirement_b_text="y", explanation="z",
        )
        self.assertEqual(flag.requirement_a_evidence, "")
        self.assertEqual(flag.requirement_b_evidence, "")
        self.assertFalse(flag.reconciliation_checked)


class ConsistencyPromptGuardrailTests(unittest.TestCase):
    def _prompt(self) -> str:
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        return BHiveParser._build_consistency_prompt(items)

    def test_requires_verbatim_evidence_and_reconciliation_check(self):
        prompt = self._prompt()
        self.assertIn("VERBATIM", prompt)
        self.assertIn("reconciliation_checked", prompt)
        self.assertIn("requirement_a_evidence", prompt)
        self.assertIn("requirement_b_evidence", prompt)

    def test_explanation_must_be_grounded_in_quoted_evidence(self):
        prompt = self._prompt()
        self.assertIn("must describe ONLY what the", prompt)

    def test_party_role_label_guardrail_present(self):
        prompt = self._prompt()
        self.assertIn("PARTY OR ROLE labels", prompt)
        self.assertIn("Design-Builder", prompt)

    def test_order_independence_instruction_present(self):
        prompt = self._prompt()
        self.assertIn("distance from another in this list is never itself evidence", prompt)


class ConsistencyCheckParsingTests(unittest.TestCase):
    def _mock_response(self, payload) -> MagicMock:
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        fake_response.stop_reason = "end_turn"
        fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        return fake_response

    def test_parses_new_fields_when_present(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        payload = [{
            "a": "r1", "b": "r2", "requirement_a_evidence": "quote a", "requirement_b_evidence": "quote b",
            "reconciliation_checked": True,
            "scope_reconciliation_reasoning": "no scope qualifier stated in either requirement",
            "scopes_overlap": True, "explanation": "conflict",
        }]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(items)  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(len(flags), 1)
        self.assertEqual(flags[0].requirement_a_evidence, "quote a")
        self.assertEqual(flags[0].requirement_b_evidence, "quote b")
        self.assertTrue(flags[0].reconciliation_checked)

    def test_older_shaped_response_without_scope_reasoning_is_dropped_not_crashed(self):
        """CLAUDE-P25: a response shaped like every pre-CLAUDE-P25 test
        fixture (a/b/explanation/reconciliation_checked, no scope
        reasoning) must not crash the parser - but the flag itself is now
        deterministically dropped, since it never states which scope
        dimensions were checked. 'no crash' and 'no longer accepted
        without scope reasoning' are both true at once."""
        parser = BHiveParser(anthropic_api_key="fake-key")
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        payload = [{"a": "r1", "b": "r2", "explanation": "conflict", "reconciliation_checked": True}]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response(payload)
            flags, checked, note = parser._check_consistency(items)  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])

    def test_usage_sink_captures_prompt_tokens_and_latency(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response([])
            sink: dict = {}
            parser._check_consistency(items, usage_sink=sink)  # noqa: SLF001
        self.assertIn("prompt", sink)
        self.assertEqual(sink["input_tokens"], 100)
        self.assertEqual(sink["output_tokens"], 50)
        self.assertIsNotNone(sink["latency_seconds"])

    def test_usage_sink_none_by_default_does_not_change_behavior(self):
        parser = BHiveParser(anthropic_api_key="fake-key")
        items = [
            RequirementItem(id="r1", text="x", category="a", confidence=0.9, source_line=0),
            RequirementItem(id="r2", text="y", category="a", confidence=0.9, source_line=0),
        ]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = self._mock_response([])
            flags, checked, note = parser._check_consistency(items)  # noqa: SLF001
        self.assertTrue(checked)
        self.assertEqual(flags, [])


if __name__ == "__main__":
    unittest.main()
