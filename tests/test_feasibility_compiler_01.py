"""CLAUDE-FEASIBILITY-COMPILER-01 - proven with no live model.

Every test here is HERMETIC. `compile_feasibility` takes `runner` with no
default, so a test that forgets to supply one raises TypeError rather than
reaching a provider, and `NothingReachesAProvider` asserts that rather than
trusting it.

The property this file exists to defend is section 10's, and it is the one that
would be easiest to lose by accident:

    STRUCTURAL FAILURE MAY BE RETRIED. SEMANTIC FAILURE MAY NOT.

Retrying malformed JSON is fixing transport. Retrying a VR-01..VR-20 failure is
teaching a model to satisfy the validator, which destroys the only reason the
validator is worth having - so `TheValidatorIsNeverTaught` counts model calls and
proves the number does not rise when the payload is structurally perfect and
semantically wrong.
"""
from __future__ import annotations

import json
import unittest

from services import feasibility_compiler as compiler
from services import go_pdz_contract as contract


def _golden_payload():
    """A structurally valid, VR-clean Gate-01 envelope - 100 Example Avenue."""
    return {
        "contract": contract.CONTRACT_ID,
        "schema_version": contract.SCHEMA_VERSION,
        "gate": contract.GATE_01,
        "next_authorized_gate": contract.GATE_02,
        "subject": {
            "subject_id": "SUBJ-EXAMPLE-1",
            "address_as_given": "100 Example Avenue",
            "normalized_address": "100 Example Ave",
            "parcel_identifier": "PARCEL-1",
            "municipality": "Example City",
            "identity_confidence": "HIGH",
        },
        "authorities": [{
            "authority_id": "EX-ZBL-1",
            "name": "Example City Zoning By-law 1-2020",
            "instrument": "Example City",
            "citation": "Chapter 5",
            "effective_date": "2020-01-01",
            "version_identifier": "1-2020",
            "source_type": "OFFICIAL_MACHINE_READABLE_GEOMETRY",
            "authority_status": "IN_FORCE",
            "retrieved_at": "2026-09-12T00:00:00Z",
            "url": "https://www.toronto.ca/example.pdf",
        }],
        "statements": [{
            "statement_id": "S-ZONE",
            "kind": "AUTHORITY_SAYS",
            "topic": "ZONING_DESIGNATION",
            "text": "The parcel lies within the R1 zone.",
            "authority_refs": ["EX-ZBL-1"],
            "statement_status": "ESTABLISHED",
            "confidence": "HIGH",
            "spatial_relation": "INSIDE",
            "spatial_basis": "DETERMINISTIC_GIS",
            "conflict_refs": [],
            "derived_from": [],
        }],
        "site_specific_exceptions": [],
        "unresolved": [],
        "result_status": "GOVERNED_RESULT",
    }


def _evidence(**overrides):
    base = dict(
        investigation_id="INV-1",
        input_address="100 Example Avenue",
        normalized_address="100 Example Ave",
        parcel_identifier="PARCEL-1",
        municipality="Example City",
        identity_confidence="HIGH",
        spatial_results={"zoning": {"spatial_relation": "INSIDE",
                                    "spatial_basis": "DETERMINISTIC_GIS"}},
        admitted_authorities=[{"authority_id": "EX-ZBL-1",
                               "name": "Example City Zoning By-law 1-2020"}],
        zoning={"zone_code": "R1"},
    )
    base.update(overrides)
    return compiler.FeasibilityEvidence(**base)


class CountingRunner:
    """Records every model call so retry behaviour can be counted, not assumed."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, instructions, evidence, attempt):
        self.calls.append({"attempt": attempt, "evidence": evidence,
                           "instructions": instructions})
        item = self.responses[min(len(self.calls), len(self.responses)) - 1]
        if isinstance(item, Exception):
            raise item
        return item


class TheGoldenSyntheticCase(unittest.TestCase):
    """Section 16B."""

    def test_a_clean_payload_compiles_and_is_promotable(self):
        runner = CountingRunner([_golden_payload()])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertTrue(outcome.typed_output_valid)
        self.assertTrue(outcome.semantic_validation_valid)
        self.assertTrue(outcome.promotable)
        self.assertEqual(outcome.semantic_error_count, 0)
        self.assertIsNone(outcome.failure_reason)
        self.assertEqual(outcome.attempt_count, 1)

    def test_the_envelope_carries_the_provenance_section_13_requires(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([_golden_payload()]))
        self.assertEqual(outcome.compiler_version, compiler.COMPILER_VERSION)
        self.assertEqual(outcome.provider, compiler.resolve_provider_name())
        self.assertEqual(outcome.model, compiler.resolve_model())
        self.assertEqual(outcome.schema_version, contract.SCHEMA_VERSION)
        self.assertTrue(outcome.validator_version)
        self.assertTrue(outcome.input_evidence_sha256.startswith("sha256:"))
        self.assertTrue(outcome.output_payload_sha256.startswith("sha256:"))
        self.assertIsNotNone(outcome.executed_at)
        self.assertIsNotNone(outcome.timing_seconds)

    def test_no_hidden_reasoning_is_stored(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([_golden_payload()]))
        blob = json.dumps(outcome.as_dict(), default=str).lower()
        for banned in ("chain_of_thought", "chain-of-thought", "reasoning_trace",
                       "thinking"):
            self.assertNotIn(banned, blob)


class TheValidatorIsNeverTaught(unittest.TestCase):
    """Section 10 and 16C. THE rule of this module."""

    def _vr_invalid(self):
        """Structurally perfect, semantically wrong: AUTHORITY_SAYS with no
        authority (VR-04), and HIGH confidence resting on nothing (VR-07)."""
        payload = _golden_payload()
        payload["statements"][0]["authority_refs"] = []
        return payload

    def test_a_semantic_failure_is_not_retried(self):
        runner = CountingRunner([self._vr_invalid(), _golden_payload()])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertEqual(len(runner.calls), 1,
                         "the model must be called ONCE; a second call would be "
                         "the validator teaching it the answer")
        self.assertEqual(outcome.attempt_count, 1)

    def test_a_semantic_failure_is_not_promotable(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([self._vr_invalid()]))
        self.assertTrue(outcome.typed_output_valid, "the shape was fine")
        self.assertFalse(outcome.semantic_validation_valid)
        self.assertFalse(outcome.promotable)
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_SEMANTIC)

    def test_the_original_payload_and_diagnostics_are_preserved(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([self._vr_invalid()]))
        self.assertIsNotNone(outcome.go_pdz_payload,
                             "the model's own result is evidence, not rubbish")
        self.assertEqual(outcome.go_pdz_payload["statements"][0]["authority_refs"],
                         [])
        rules = {f.get("rule_id")
                 for f in (outcome.validation_result or {}).get("findings") or []}
        self.assertIn("VR-04", rules)
        self.assertGreater(outcome.semantic_error_count, 0)

    def test_the_exact_vr_failures_are_retained_not_summarised(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([self._vr_invalid()]))
        findings = (outcome.validation_result or {}).get("findings") or []
        self.assertTrue(findings)
        for finding in findings:
            self.assertIn("rule_id", finding)
            self.assertIn("path", finding)


class StructuralRetryIsBoundedAndReal(unittest.TestCase):
    """Section 10 A-D."""

    def test_a_malformed_payload_is_retried_then_succeeds(self):
        runner = CountingRunner([{"not": "a contract"}, _golden_payload()])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertEqual(len(runner.calls), 2)
        self.assertEqual(outcome.attempt_count, 2)
        self.assertTrue(outcome.promotable)

    def test_the_retry_ceiling_is_honoured(self):
        runner = CountingRunner([{"bad": 1}, {"bad": 2}, _golden_payload()])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertEqual(len(runner.calls), compiler.MAX_STRUCTURAL_ATTEMPTS)
        self.assertFalse(outcome.typed_output_valid)
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_SCHEMA)

    def test_the_ceiling_is_small_and_explicit(self):
        self.assertLessEqual(compiler.MAX_STRUCTURAL_ATTEMPTS, 2)

    def test_a_non_document_return_is_structural_not_semantic(self):
        runner = CountingRunner(["a string, not a document"])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner,
                                               max_attempts=1)
        self.assertFalse(outcome.typed_output_valid)
        self.assertIn(outcome.failure_reason,
                      (compiler.FAILURE_STRUCTURAL, compiler.FAILURE_SCHEMA))
        self.assertIsNone(outcome.go_pdz_payload)


class FailureModesAreResultsNotExceptions(unittest.TestCase):
    """Section 14. Every one, and none of them escapes."""

    def _fails_with(self, exc):
        return compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([exc]), max_attempts=2)

    def test_a_missing_credential_is_its_own_named_stop(self):
        """Section 5: PROVIDER_CREDENTIAL_REQUIRED, not a generic failure - so a
        blocked live probe is distinguishable from a broken one."""
        outcome = self._fails_with(RuntimeError("no GEMINI_API_KEY configured"))
        self.assertEqual(outcome.failure_reason,
                         compiler.PROVIDER_CREDENTIAL_REQUIRED)

    def test_a_timeout_is_a_timeout(self):
        outcome = self._fails_with(TimeoutError("deadline exceeded"))
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_MODEL_TIMEOUT)

    def test_a_rate_limit_is_a_rate_limit(self):
        outcome = self._fails_with(RuntimeError("429 rate limit exceeded"))
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_MODEL_RATE_LIMIT)

    def test_an_unavailable_provider_is_not_retried_pointlessly(self):
        runner = CountingRunner([ConnectionError("service unreachable")])
        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_MODEL_UNAVAILABLE)
        self.assertEqual(len(runner.calls), 1,
                         "a dead provider is not a structural problem")

    def test_a_failure_yields_no_payload_and_no_promotion(self):
        outcome = self._fails_with(RuntimeError("boom"))
        self.assertIsNone(outcome.go_pdz_payload)
        self.assertFalse(outcome.promotable)
        self.assertFalse(outcome.semantic_validation_valid)


class TheContextIsBounded(unittest.TestCase):
    """Section 6. What is absent is the design."""

    def test_owner_program_cannot_reach_the_model(self):
        for forbidden in ("owner_program", "budget", "unit_count", "massing",
                          "design_options"):
            evidence = _evidence(zoning={forbidden: "smuggled"})
            outcome = compiler.compile_feasibility(
                evidence, runner=CountingRunner([_golden_payload()]))
            self.assertEqual(outcome.failure_reason, compiler.FAILURE_EVIDENCE,
                             forbidden)
            self.assertIsNone(outcome.go_pdz_payload)

    def test_a_store_handle_cannot_reach_the_model(self):
        evidence = _evidence(provenance={"registry": "/instance/store"})
        outcome = compiler.compile_feasibility(
            evidence, runner=CountingRunner([_golden_payload()]))
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_EVIDENCE)

    def test_the_runner_receives_only_the_serialised_evidence(self):
        runner = CountingRunner([_golden_payload()])
        evidence = _evidence()
        compiler.compile_feasibility(evidence, runner=runner)
        seen = runner.calls[0]["evidence"]
        self.assertEqual(set(seen), set(evidence.for_model()))
        self.assertNotIn("store", seen)

    def test_missing_identity_is_refused_before_any_model_call(self):
        runner = CountingRunner([_golden_payload()])
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="", input_address=""),
            runner=runner)
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_EVIDENCE)
        self.assertEqual(len(runner.calls), 0, "do not pay for a doomed call")


class TheEvidenceHashProvesWhatWasSeen(unittest.TestCase):
    """Section 12."""

    def test_the_hash_is_stable_across_key_order(self):
        one = compiler.evidence_hash({"a": 1, "b": [1, 2]})
        two = compiler.evidence_hash({"b": [1, 2], "a": 1})
        self.assertEqual(one, two)

    def test_different_evidence_hashes_differently(self):
        self.assertNotEqual(compiler.evidence_hash({"a": 1}),
                            compiler.evidence_hash({"a": 2}))

    def test_the_hash_covers_the_evidence_actually_sent(self):
        runner = CountingRunner([_golden_payload()])
        evidence = _evidence()
        outcome = compiler.compile_feasibility(evidence, runner=runner)
        self.assertEqual(outcome.input_evidence_sha256,
                         compiler.evidence_hash(runner.calls[0]["evidence"]))


class NothingReachesAProvider(unittest.TestCase):
    """The hermetic guarantee, and the tool surface."""

    def test_runner_has_no_default(self):
        import inspect
        parameter = inspect.signature(
            compiler.compile_feasibility).parameters.get("runner")
        self.assertIsNotNone(parameter)
        self.assertIs(parameter.default, inspect.Parameter.empty)

    def test_the_agent_is_given_zero_tools(self):
        """Section 9: the bounded context already contains everything."""
        import inspect
        source = inspect.getsource(compiler.gateway_runner)
        self.assertIn("tools=()", source)
        self.assertIn("retries=0", source)

    def test_no_network_or_shell_tool_is_defined_anywhere(self):
        import inspect
        source = inspect.getsource(compiler)
        for banned in ("def search", "def fetch_url", "def run_shell",
                       "def read_file", "def execute_sql"):
            self.assertNotIn(banned, source)

    def test_no_credential_is_reported_not_worked_around(self):
        """Building the runner no longer needs a key - the GATEWAY owns that
        decision, and reports it as a named status rather than an exception."""
        status = compiler.credential_status()
        self.assertIn("credential_present", status)
        self.assertIn(status["status"],
                      ("READY", compiler.PROVIDER_CREDENTIAL_REQUIRED))

    def test_the_model_is_configuration_driven_not_hard_coded(self):
        """The provider name is the GATEWAY's vocabulary, not the SDK's - version
        1 said "google", which llm_gateway would have rejected outright."""
        from services import llm_gateway
        self.assertEqual(compiler.resolve_provider_name(), "gemini")
        self.assertIn(compiler.resolve_provider_name(),
                      llm_gateway.KNOWN_PROVIDERS)
        self.assertEqual(compiler.resolve_model(), "gemini-3.8-flash")
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([_golden_payload()]),
            provider="other", model="some-other-model")
        self.assertEqual(outcome.provider, "other")
        self.assertEqual(outcome.model, "some-other-model")

    def test_no_latest_alias_is_used(self):
        self.assertNotIn("latest", compiler.resolve_model())


class NoCanonicalMutation(unittest.TestCase):
    """Section 15."""

    def test_the_compiler_imports_no_store_or_model_module(self):
        import inspect
        source = inspect.getsource(compiler)
        for banned in ("import models", "from models", "case_workspace",
                       "requirements_registry", "session.commit", "db.session"):
            self.assertNotIn(banned, source)

    def test_compiling_returns_a_candidate_not_a_promotion(self):
        outcome = compiler.compile_feasibility(
            _evidence(), runner=CountingRunner([_golden_payload()]))
        self.assertIn("promotable", outcome.as_dict())
        self.assertNotIn("promoted", outcome.as_dict())


class WithPydanticAisOwnTestModel(unittest.TestCase):
    """Section 16A: the framework's supported fake, not a hand-rolled one."""

    def setUp(self):
        try:
            from pydantic_ai import Agent          # noqa: F401
            from pydantic_ai.models.function import FunctionModel  # noqa: F401
        except Exception as exc:  # noqa: BLE001
            self.skipTest("pydantic-ai unavailable: %s" % exc)

    def test_a_function_model_agent_drives_the_compiler_end_to_end(self):
        from pydantic_ai import Agent
        from pydantic_ai.models.function import AgentInfo, FunctionModel
        from pydantic_ai.messages import ModelResponse, TextPart

        payload = _golden_payload()

        def respond(messages, info: AgentInfo) -> ModelResponse:
            return ModelResponse(parts=[TextPart(json.dumps(payload))])

        agent = Agent(FunctionModel(respond), output_type=str,
                      instructions=compiler.INSTRUCTIONS, retries=0)

        def runner(instructions, evidence, attempt):
            return json.loads(agent.run_sync("compile").output)

        outcome = compiler.compile_feasibility(_evidence(), runner=runner)
        self.assertTrue(outcome.promotable)
        self.assertTrue(outcome.typed_output_valid)

    def test_the_current_api_uses_output_type_not_result_type(self):
        """Section 24: the deprecation the directive warned about."""
        import inspect
        from pydantic_ai import Agent
        parameters = inspect.signature(Agent.__init__).parameters
        self.assertIn("output_type", parameters)
        self.assertNotIn("result_type", parameters)


if __name__ == "__main__":
    unittest.main()
