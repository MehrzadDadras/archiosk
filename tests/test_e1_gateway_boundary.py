"""
E1 — every model call goes through the gateway, and construction cannot 500.

WHAT THIS CLOSES

On 2026-09-06 a drifted httpx raised
`TypeError: Client.__init__() got an unexpected keyword argument 'proxies'`
from inside the Anthropic SDK, and `/help/studio/generate` returned a 500. That
was never a Help defect: EVERY AI call site in this application constructed its
client BEFORE its try block and guarded only `messages.create`. The audit found
8 such sites. The dependency drift had broken every AI capability for a week and
nothing surfaced it until one new feature happened to exercise the path.

The gateway had the same defect at its own construction, so migrating call sites
into it would NOT have fixed anything on its own. Both halves were needed.

WHAT IS ASSERTED HERE

The negative: no module outside the gateway constructs a provider client. And
the behaviour: construction failure degrades to the workflow's own honest
"could not run" result rather than an exception. That distinction is the whole
point of E1 — an infrastructure failure must never be indistinguishable from a
model verdict.

No test here reaches the network.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path
from unittest.mock import patch

from services.llm_gateway import LLMCallOutcome, anthropic_client, call_llm_json

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATEWAY = _REPO_ROOT / "services" / "llm_gateway.py"

# The exact SDK failure that reached production.
_DRIFT = TypeError("Client.__init__() got an unexpected keyword argument 'proxies'")


class NoDirectProviderConstructionTests(unittest.TestCase):
    """The carry-through guard. A new bypass must fail here, not in production."""

    def test_only_the_gateway_constructs_a_provider_client(self):
        offenders = []
        for path in sorted((_REPO_ROOT / "services").glob("*.py")) + \
                sorted((_REPO_ROOT / "routes").glob("*.py")):
            if path.name == "llm_gateway.py":
                continue
            source = path.read_text(encoding="utf-8")
            # Strings and comments are stripped so prose about the boundary
            # cannot fail this test - only real calls count.
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                f = node.func
                name = getattr(f, "attr", None) or getattr(f, "id", None)
                if name in {"Anthropic", "Client"} and isinstance(f, ast.Attribute):
                    owner = getattr(f.value, "id", "")
                    if owner in {"anthropic", "genai"}:
                        offenders.append("%s:%d" % (path.name, node.lineno))
        self.assertEqual(offenders, [],
                         "provider client constructed outside the gateway: %s" % offenders)

    def test_the_gateway_itself_still_constructs_both_providers(self):
        """Guard-the-guard: if the scan above passed because nothing constructs
        anything anywhere, that is a broken test, not a clean codebase."""
        source = _GATEWAY.read_text(encoding="utf-8")
        self.assertIn("anthropic.Anthropic(", source)
        self.assertIn("genai.Client(", source)


class ConstructionFailureDegradesTests(unittest.TestCase):

    def test_the_helper_returns_a_degraded_outcome_not_an_exception(self):
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            client, failure = anthropic_client("key", 5.0, "probe")
        self.assertIsNone(client)
        self.assertIsInstance(failure, LLMCallOutcome)
        self.assertFalse(failure.ran)
        self.assertTrue(failure.skipped_reason)

    def test_call_llm_json_degrades_on_construction_failure(self):
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            outcome = call_llm_json("prompt", api_key="key")
        self.assertFalse(outcome.ran)
        self.assertIsNone(outcome.parsed)

    def test_a_degraded_outcome_never_fabricates_a_result(self):
        """`ran=False` must mean no content at all - the contract the whole
        trust chain leans on."""
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            outcome = call_llm_json("prompt", api_key="key")
        self.assertIsNone(outcome.parsed)
        self.assertIsNone(outcome.raw_text)
        self.assertIsNotNone(outcome.skipped_reason)


class MigratedCallSitesDegradeTests(unittest.TestCase):
    """Each migrated workflow returns its OWN honest no-result shape."""

    def test_question_fit_degrades_rather_than_raising(self):
        from services.cross_modal_investigation import assess_question_fit
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            result = assess_question_fit(question="q?", script_text="s", api_key="key")
        self.assertFalse(result.ran)
        self.assertEqual(result.outcome, "review_needed")

    def test_evidence_consistency_degrades_rather_than_raising(self):
        from services.cross_modal_investigation import assess_evidence_consistency
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            result = assess_evidence_consistency(
                pairs=[{"unit_id": "u", "text": "t", "claims": ["c"]}], api_key="key")
        self.assertFalse(result.ran)
        self.assertEqual(result.outcome, "review_needed")

    def test_scenario_compilation_degrades_rather_than_raising(self):
        from services.cross_modal_investigation import compile_help_scenario
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            result = compile_help_scenario("scenario", [{"id": "e1", "text": "t"}],
                                           api_key="key")
        self.assertFalse(result.ran)
        self.assertEqual(result.scenes, ())

    def test_claim_synthesis_degrades_rather_than_raising(self):
        from services.cross_modal_investigation import propose_ai_assisted_claim
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            result = propose_ai_assisted_claim(
                question="q?", evidence_summaries=[{"id": "e", "text": "t"}], api_key="key")
        self.assertFalse(result.ran)
        self.assertIsNotNone(result.skipped_reason)

    def test_requirement_classification_falls_back_to_rules(self):
        """bhive_parser keeps its own bespoke batch loop; only construction is
        shared. A construction failure degrades to exactly what a first-batch
        timeout already degraded to - rule-based classification."""
        from services.bhive_parser import BHiveParser
        parser = BHiveParser(anthropic_api_key="key")
        with patch("anthropic.Anthropic", side_effect=_DRIFT):
            items = parser._classify_with_model([(1, "The Contractor shall submit shop drawings.")])
        self.assertIsInstance(items, list)


class SuccessPathUnchangedTests(unittest.TestCase):

    def test_a_successful_call_still_parses_and_records_provenance(self):
        from unittest.mock import MagicMock
        block = MagicMock(); block.type = "text"; block.text = '{"outcome": "pass", "reason": "ok"}'
        response = MagicMock(); response.content = [block]; response.stop_reason = "end_turn"
        client = MagicMock(); client.messages.create.return_value = response
        with patch("anthropic.Anthropic", MagicMock(return_value=client)):
            outcome = call_llm_json("prompt", api_key="key", model="m")
        self.assertTrue(outcome.ran)
        self.assertEqual(outcome.parsed["outcome"], "pass")
        self.assertEqual(outcome.provider, "anthropic")
        self.assertEqual(outcome.model, "m")
        self.assertIsNotNone(outcome.requested_at)


if __name__ == "__main__":
    unittest.main()
