"""CLAUDE-GATEWAY-OBSERVABILITY-01 - observe the model exactly.

INSTRUMENTATION ONLY. Not one acceptance decision changes here: what was usable
before is usable now, what was refused is still refused, and these tests assert
that as carefully as they assert the new telemetry.

THE GAP WAS WORSE THAN "NOT EXPOSED". The compiler did surface only
`model_version` and `usage` - but underneath, the gateway DISCARDED the
provider's telemetry on exactly the paths qualification needed it:

    truncated  -> LLMCallOutcome(ran=False, skipped_reason=..., stop_reason=...)
    malformed  -> LLMCallOutcome(ran=False, skipped_reason=...)

No raw text, no usage, no resolved model, and in the malformed case not even a
finish reason. A response that failed took its own evidence with it, which made
a provider's misbehaviour indistinguishable from ours - the one distinction
qualification exists to draw.

STRICT EMISSION IS NOT PARSER RECOVERY. The gateway strips ``` fences before
`json.loads`, and that normalization is deliberately NOT removed here - other
callers depend on it and this tranche may not change semantics. What changes is
that both forms are now preserved, so "the provider emitted clean JSON" and "the
provider emitted a fenced block we salvaged" stop being the same observation.
`normalization_applied` is the flag that separates them.
"""
from __future__ import annotations

import unittest

from services import gateway_model
from services import llm_gateway

FENCE = "```"
USAGE = {"prompt_token_count": 1200, "candidates_token_count": 340,
         "total_token_count": 1540}


def _finish(text, *, truncated=False, usage=USAGE, resolved="gemini-3.8-flash"):
    return llm_gateway._finish_json_outcome(
        text_out=text, stop_reason="MAX_TOKENS" if truncated else "STOP",
        truncated=truncated, log_label="test", provider="gemini",
        model="gemini-3.8-flash", requested_at="2026-09-13T00:00:00Z",
        resolved_model=resolved, usage=usage)


class TelemetrySurvivesEveryEmissionShape(unittest.TestCase):
    """A-F: the five shapes section 5 names, plus usage on a parse failure."""

    def test_A_valid_json(self):
        outcome = _finish('{"a": 1}')
        self.assertTrue(outcome.ran)
        self.assertEqual(outcome.parse_status, llm_gateway.PARSE_OK)
        self.assertFalse(outcome.normalization_applied)
        self.assertEqual(outcome.parsed, {"a": 1})

    def test_B_fenced_json_is_recorded_as_normalized(self):
        outcome = _finish(FENCE + "json\n" + '{"a": 1}' + "\n" + FENCE)
        self.assertTrue(outcome.ran, "fence stripping is pre-existing recovery")
        self.assertTrue(outcome.normalization_applied,
                        "and it must be visible as recovery, not strict emission")
        self.assertIn(FENCE, outcome.raw_text)
        self.assertNotIn(FENCE, outcome.normalized_text)

    def test_C_prose_plus_json_is_malformed_with_its_evidence_kept(self):
        outcome = _finish('Here is the result:\n{"a": 1}')
        self.assertFalse(outcome.ran)
        self.assertIsNone(outcome.parsed)
        self.assertEqual(outcome.parse_status, llm_gateway.PARSE_MALFORMED)
        self.assertIn("Here is the result", outcome.raw_text)
        self.assertTrue(outcome.parse_error)

    def test_D_truncation_is_distinguished_from_malformed(self):
        outcome = _finish('{"a": 1', truncated=True)
        self.assertFalse(outcome.ran)
        self.assertEqual(outcome.parse_status, llm_gateway.PARSE_TRUNCATED)
        self.assertTrue(outcome.truncated)
        self.assertEqual(outcome.stop_reason, "MAX_TOKENS")

    def test_E_malformed_output(self):
        outcome = _finish("not json at all")
        self.assertFalse(outcome.ran)
        self.assertEqual(outcome.parse_status, llm_gateway.PARSE_MALFORMED)
        self.assertFalse(outcome.truncated)

    def test_F_usage_survives_a_parse_failure(self):
        """The regression that made this tranche necessary."""
        for text, truncated in (("not json", False), ('{"a"', True)):
            outcome = _finish(text, truncated=truncated)
            self.assertEqual(outcome.usage, USAGE,
                             "usage must survive an unusable response")
            self.assertIsNotNone(outcome.raw_text)

    def test_G_the_resolved_model_survives_a_parse_failure(self):
        outcome = _finish("not json")
        self.assertEqual(outcome.resolved_model, "gemini-3.8-flash")
        self.assertEqual(outcome.model, "gemini-3.8-flash")
        self.assertEqual(outcome.provider, "gemini")

    def test_H_raw_and_normalized_remain_distinguishable(self):
        fenced = _finish(FENCE + "json\n" + '{"a": 1}' + "\n" + FENCE)
        plain = _finish('{"a": 1}')
        self.assertNotEqual(fenced.raw_text, fenced.normalized_text)
        self.assertEqual(plain.normalized_text, plain.raw_text.strip())
        self.assertTrue(fenced.normalization_applied)
        self.assertFalse(plain.normalization_applied)

    def test_nothing_is_invented_when_the_provider_reports_nothing(self):
        outcome = _finish('{"a": 1}', usage=None, resolved=None)
        self.assertIsNone(outcome.usage)
        self.assertIsNone(outcome.resolved_model)


class InvalidRemainsInvalid(unittest.TestCase):
    """Section 3, asserted rather than assumed."""

    def test_only_strictly_parseable_or_fence_recovered_output_is_usable(self):
        usable = {
            '{"a": 1}': True,
            FENCE + "json\n" + '{"a": 1}' + "\n" + FENCE: True,
            'Here is the result:\n{"a": 1}': False,
            "not json at all": False,
            "": False,
        }
        for text, expected in usable.items():
            outcome = _finish(text)
            self.assertEqual(outcome.ran, expected, text[:30])
            self.assertEqual(outcome.parsed is not None, expected, text[:30])

    def test_a_truncated_response_is_never_partially_salvaged(self):
        outcome = _finish('{"a": 1, "b": ', truncated=True)
        self.assertFalse(outcome.ran)
        self.assertIsNone(outcome.parsed)

    def test_the_skipped_reasons_are_unchanged(self):
        """Other callers key on these strings; instrumentation may not move them."""
        self.assertEqual(_finish("nope").skipped_reason,
                         "Model returned malformed output.")
        self.assertEqual(_finish("{", truncated=True).skipped_reason,
                         "Model's response was cut off before it finished (max_tokens).")


class TheAdapterCarriesItAcrossTheBoundary(unittest.TestCase):

    def test_a_failed_call_raises_with_its_telemetry_attached(self):
        outcome = _finish("not json")
        error = gateway_model.GatewayUnavailable(
            outcome.skipped_reason, provider=outcome.provider,
            model=outcome.model,
            telemetry=gateway_model._telemetry_of(outcome))
        self.assertEqual(error.telemetry["parse_status"],
                         llm_gateway.PARSE_MALFORMED)
        self.assertEqual(error.telemetry["usage"], USAGE)
        self.assertIn("not json", error.telemetry["raw_text"])

    def test_telemetry_degrades_on_an_object_that_lacks_the_fields(self):
        """Test doubles written before these fields existed must not explode."""
        class Old:
            ran = True
        telemetry = gateway_model._telemetry_of(Old())
        self.assertEqual(set(telemetry), set(gateway_model.TELEMETRY_FIELDS))
        self.assertIsNone(telemetry["parse_status"])

    def test_an_unavailable_gateway_without_telemetry_still_constructs(self):
        error = gateway_model.GatewayUnavailable("no key")
        self.assertEqual(error.telemetry, {})


class TheCompilerEnvelopeShape(unittest.TestCase):
    """Section 4."""

    def setUp(self):
        from services import feasibility_compiler as compiler
        self.compiler = compiler
        self.envelope = compiler._diagnostics(
            requested_provider="gemini", requested_model="gemini-3.8-flash",
            telemetry=gateway_model._telemetry_of(_finish('{"a": 1}')),
            parsed={"a": 1})

    def test_every_named_field_is_present(self):
        for field in ("REQUESTED_PROVIDER", "REQUESTED_MODEL",
                      "RESOLVED_PROVIDER", "RESOLVED_MODEL", "MODEL_VERSION",
                      "RAW_PROVIDER_TEXT", "NORMALIZED_PARSE_INPUT",
                      "STOP_REASON", "TRUNCATED", "INPUT_TOKENS",
                      "OUTPUT_TOKENS", "TOTAL_TOKENS", "PARSE_STATUS",
                      "PARSE_ERROR", "PARSED_PAYLOAD"):
            self.assertIn(field, self.envelope, field)

    def test_requested_and_resolved_are_separate_facts(self):
        self.assertEqual(self.envelope["REQUESTED_MODEL"], "gemini-3.8-flash")
        self.assertEqual(self.envelope["RESOLVED_MODEL"], "gemini-3.8-flash")
        envelope = self.compiler._diagnostics(
            requested_provider="gemini", requested_model="gemini-3.8-flash",
            telemetry={"resolved_model": "gemini-2.5-flash"})
        self.assertNotEqual(envelope["REQUESTED_MODEL"],
                            envelope["RESOLVED_MODEL"],
                            "a substitution must be visible, never silent")

    def test_token_counts_are_read_not_invented(self):
        self.assertEqual(self.envelope["INPUT_TOKENS"], 1200)
        self.assertEqual(self.envelope["OUTPUT_TOKENS"], 340)
        self.assertEqual(self.envelope["TOTAL_TOKENS"], 1540)
        empty = self.compiler._diagnostics(
            requested_provider="gemini", requested_model="m", telemetry={})
        self.assertIsNone(empty["INPUT_TOKENS"],
                          "absent is absent - never a fabricated zero")

    def test_the_outcome_carries_diagnostics_on_every_path(self):
        self.assertIn("diagnostics",
                      self.compiler.CompilerOutcome.__dataclass_fields__)


class TheTrustBoundaryHolds(unittest.TestCase):
    """Section 7 - raw text is evidence, never a result."""

    def test_raw_text_never_reaches_validation_or_a_finding(self):
        import inspect
        source = inspect.getsource(self.compiler_module().compile_feasibility)
        self.assertIn("validator.validate(governed)", source)
        # The only thing validated is the parsed, structurally-checked payload.
        self.assertNotIn("RAW_PROVIDER_TEXT", source)
        self.assertNotIn("raw_text", source)

    def test_diagnostics_are_not_an_input_to_promotion(self):
        import inspect
        from services import relation_binding
        source = inspect.getsource(relation_binding)
        for name in ("diagnostics", "RAW_PROVIDER_TEXT", "parse_status",
                     "normalized_text"):
            self.assertNotIn(name, source,
                             "promotion may not read provider telemetry")

    def compiler_module(self):
        from services import feasibility_compiler as compiler
        return compiler


if __name__ == "__main__":
    unittest.main()
