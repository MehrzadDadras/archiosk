"""CLAUDE-FEASIBILITY-EGRESS-02 - one egress boundary, proven rather than asserted.

Version 1 of the compiler built `GoogleModel(provider=GoogleProvider(api_key=...))`
and called Google directly. It worked, which is exactly why it needed catching: a
second production egress path in a repository that deliberately has one, routing
around `services/llm_gateway.py` and therefore around its `AI_CALLS_DISABLED` kill
switch, its timeout policy, its honest-degrade contract, and the provider dispatch
that exists so content cannot reach a provider the caller did not name.

    A BYPASS THAT HAPPENS TO WORK IS STILL A BYPASS.

So the central test here is not that the adapter functions. It is
`ThereIsExactlyOneEgressPath`, which reads the source of the services involved and
fails if a direct provider client is constructed anywhere outside the gateway.

Every test is HERMETIC: `GatewayModel` takes an injectable `caller`, so the
adapter is exercised against a fake gateway and nothing reaches a network.
"""
from __future__ import annotations

import asyncio
import inspect
import re
import json
import unittest

from services import feasibility_compiler as compiler
from services import gateway_model as gateway
from services import go_pdz_contract as contract
from services import llm_gateway


def _outcome(ran=True, parsed=None, raw_text=None, skipped_reason=None,
             provider="gemini", model="gemini-3.8-flash", stop_reason=None):
    return llm_gateway.LLMCallOutcome(
        ran=ran, parsed=parsed, raw_text=raw_text, skipped_reason=skipped_reason,
        stop_reason=stop_reason, provider=provider, model=model,
        requested_at="2026-09-12T00:00:00Z")


class RecordingGateway:
    """Stands in for `llm_gateway.call_provider_json`, recording every call."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def __call__(self, provider, **kwargs):
        self.calls.append(dict(kwargs, provider=provider))
        item = self.outcomes[min(len(self.calls), len(self.outcomes)) - 1]
        if isinstance(item, Exception):
            raise item
        return item


def _request(model, messages, params=None):
    return asyncio.run(model.request(messages, None, params))


class _Part:
    def __init__(self, kind, content):
        self.part_kind = kind
        self.content = content


class _Message:
    def __init__(self, parts, instructions=None):
        self.parts = parts
        self.instructions = instructions


def code_only(module):
    """Source with docstrings and comments stripped.

    The docstrings deliberately NAME the bypass they replaced, so a naive
    substring scan would fail on the very text that records the correction.
    """
    source = inspect.getsource(module)
    source = re.sub(r'"""(?:.|\n)*?"""', "", source)
    source = re.sub(r"#.*", "", source)
    return source


class ThereIsExactlyOneEgressPath(unittest.TestCase):
    """The point of this tranche."""

    def test_the_compiler_constructs_no_provider_client(self):
        code = code_only(compiler)
        for banned in ("GoogleProvider(", "GoogleModel(", "genai.Client(",
                       "anthropic.Anthropic("):
            self.assertNotIn(banned, code,
                             "%s would be a second egress path" % banned)

    def test_the_compiler_imports_no_provider_sdk(self):
        source = inspect.getsource(compiler)
        for banned in ("from pydantic_ai.providers", "from pydantic_ai.models.google",
                       "import google.genai", "from google import genai"):
            self.assertNotIn(banned, source)

    def test_the_adapter_reaches_the_network_only_through_the_gateway(self):
        self.assertIn("from services import llm_gateway",
                      inspect.getsource(gateway))
        code = code_only(gateway)
        for banned in ("urllib.request", "httpx.", "requests.", "genai.Client(",
                       "GoogleProvider("):
            self.assertNotIn(banned, code)

    def test_the_adapters_default_caller_is_the_governed_gateway(self):
        model = gateway.GatewayModel("gemini-3.8-flash")
        self.assertIs(model._caller, llm_gateway.call_provider_json)

    def test_the_adapter_publishes_no_provider_object(self):
        """The gateway is not a PydanticAI Provider and must not pose as one."""
        self.assertIsNone(gateway.GatewayModel("m").provider)

    def test_the_runner_hands_the_agent_a_gateway_model(self):
        recorder = RecordingGateway([_outcome(parsed={"ok": True})])
        runner = compiler.gateway_runner(caller=recorder)
        underlying = runner.agent.model
        self.assertIsInstance(underlying, gateway.GatewayModel)
        self.assertIs(underlying._caller, recorder)


class TheAdapterIsARealPydanticAiModel(unittest.TestCase):
    """Section 2: the framework's own supported extension point, not a fork."""

    def setUp(self):
        if not gateway.PYDANTIC_AI_AVAILABLE:
            self.skipTest("pydantic-ai not installed")

    def test_it_subclasses_the_public_model_base(self):
        from pydantic_ai.models import Model
        self.assertTrue(issubclass(gateway.GatewayModel, Model))
        self.assertIsInstance(gateway.GatewayModel("m"), Model)

    def test_it_satisfies_every_abstract_member(self):
        from pydantic_ai.models import Model
        abstract = sorted(n for n, m in inspect.getmembers(Model)
                          if getattr(m, "__isabstractmethod__", False))
        self.assertEqual(abstract, ["model_name", "request", "system"])
        model = gateway.GatewayModel("gemini-3.8-flash", provider="gemini")
        self.assertEqual(model.model_name, "gemini-3.8-flash")
        self.assertEqual(model.system, "gemini")

    def test_nothing_is_monkey_patched(self):
        source = inspect.getsource(gateway)
        for banned in ("setattr(Model", "Model.request =", "__bases__ ="):
            self.assertNotIn(banned, source)


class TheProviderVocabularyIsTheGatewaysOwn(unittest.TestCase):
    """The mismatch only a real integration surfaces."""

    def test_google_is_translated_to_the_gateways_name(self):
        self.assertEqual(gateway.resolve_provider("google"),
                         llm_gateway.PROVIDER_GEMINI)
        self.assertEqual(gateway.resolve_provider("GEMINI"),
                         llm_gateway.PROVIDER_GEMINI)

    def test_the_compilers_default_is_a_name_the_gateway_knows(self):
        self.assertIn(compiler.resolve_provider_name(),
                      llm_gateway.KNOWN_PROVIDERS)

    def test_an_unmappable_provider_is_refused_not_guessed(self):
        for name in ("openai", "", None, "mistral"):
            with self.assertRaises(gateway.GatewayCapabilityError):
                gateway.resolve_provider(name)

    def test_the_gateway_receives_the_translated_name(self):
        recorder = RecordingGateway([_outcome(parsed={"a": 1})])
        model = gateway.GatewayModel("gemini-3.8-flash", provider="google",
                                     caller=recorder)
        _request(model, [_Message([_Part("user-prompt", "hello")])])
        self.assertEqual(recorder.calls[0]["provider"], llm_gateway.PROVIDER_GEMINI)


class ThePromptIsFlattenedFaithfully(unittest.TestCase):

    def test_instructions_and_system_parts_become_the_system_prompt(self):
        system, user = gateway.flatten_messages([
            _Message([_Part("system-prompt", "be careful")],
                     instructions="compile evidence"),
            _Message([_Part("user-prompt", "the package")]),
        ])
        self.assertIn("compile evidence", system)
        self.assertIn("be careful", system)
        self.assertEqual(user, "the package")

    def test_a_structural_retry_prompt_is_carried_to_the_user_side(self):
        system, user = gateway.flatten_messages([
            _Message([_Part("user-prompt", "first")]),
            _Message([_Part("retry-prompt", "that was not valid JSON")]),
        ])
        self.assertIn("first", user)
        self.assertIn("not valid JSON", user)

    def test_empty_messages_do_not_fabricate_a_prompt(self):
        system, user = gateway.flatten_messages([])
        self.assertIsNone(system)
        self.assertEqual(user, "")

    def test_the_gateway_is_asked_for_the_configured_model(self):
        recorder = RecordingGateway([_outcome(parsed={"a": 1})])
        model = gateway.GatewayModel("gemini-3.8-flash", caller=recorder,
                                     timeout=12.5, max_tokens=4321)
        _request(model, [_Message([_Part("user-prompt", "x")])])
        call = recorder.calls[0]
        self.assertEqual(call["model"], "gemini-3.8-flash")
        self.assertEqual(call["timeout"], 12.5)
        self.assertEqual(call["max_tokens"], 4321)


class TheAdapterRefusesToPretend(unittest.TestCase):
    """A model that silently drops its tools is worse than one with none."""

    class _Params:
        def __init__(self, **kwargs):
            self.function_tools = kwargs.get("function_tools", [])
            self.output_tools = kwargs.get("output_tools", [])
            self.native_tools = kwargs.get("native_tools", [])
            self.instruction_parts = []

    def test_function_tools_are_refused(self):
        model = gateway.GatewayModel("m", caller=RecordingGateway([_outcome()]))
        with self.assertRaises(gateway.GatewayCapabilityError):
            _request(model, [_Message([_Part("user-prompt", "x")])],
                     self._Params(function_tools=["a_tool"]))

    def test_output_tools_are_refused(self):
        model = gateway.GatewayModel("m", caller=RecordingGateway([_outcome()]))
        with self.assertRaises(gateway.GatewayCapabilityError):
            _request(model, [_Message([_Part("user-prompt", "x")])],
                     self._Params(output_tools=["final_result"]))

    def test_no_tools_is_the_normal_case_and_passes(self):
        recorder = RecordingGateway([_outcome(parsed={"ok": 1})])
        model = gateway.GatewayModel("m", caller=recorder)
        response = _request(model, [_Message([_Part("user-prompt", "x")])],
                            self._Params())
        self.assertEqual(len(recorder.calls), 1)
        self.assertTrue(response.parts)


class DegradationIsCarriedNotInvented(unittest.TestCase):
    """Section 11: the gateway's own reason survives all the way up."""

    def _compile_through_gateway(self, outcomes):
        recorder = RecordingGateway(outcomes)
        runner = compiler.gateway_runner(caller=recorder)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        return compiler.compile_feasibility(evidence, runner=runner), recorder

    def test_a_missing_key_becomes_a_named_credential_stop(self):
        outcome, recorder = self._compile_through_gateway(
            [_outcome(ran=False, skipped_reason="no GEMINI_API_KEY configured")])
        self.assertEqual(outcome.failure_reason,
                         compiler.PROVIDER_CREDENTIAL_REQUIRED)
        self.assertEqual(len(recorder.calls), 1, "not retried pointlessly")
        self.assertIsNone(outcome.go_pdz_payload)

    def test_the_kill_switch_is_a_configuration_state_not_a_crash(self):
        outcome, _ = self._compile_through_gateway(
            [_outcome(ran=False, skipped_reason="AI_CALLS_DISABLED is set")])
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_PROVIDER_CONFIG)
        self.assertFalse(outcome.promotable)

    def test_an_absent_sdk_is_reported_as_unavailable(self):
        outcome, _ = self._compile_through_gateway(
            [_outcome(ran=False, skipped_reason="google-genai is not installed")])
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_MODEL_UNAVAILABLE)

    def test_ran_true_with_no_content_is_not_treated_as_an_answer(self):
        model = gateway.GatewayModel(
            "m", caller=RecordingGateway([_outcome(parsed=None, raw_text=None)]))
        with self.assertRaises(gateway.GatewayUnavailable):
            _request(model, [_Message([_Part("user-prompt", "x")])])

    def test_no_failure_path_produces_a_payload(self):
        for reason in ("no GEMINI_API_KEY", "AI_CALLS_DISABLED is set",
                       "google-genai is not installed", "timed out"):
            outcome, _ = self._compile_through_gateway(
                [_outcome(ran=False, skipped_reason=reason)])
            self.assertIsNone(outcome.go_pdz_payload, reason)
            self.assertFalse(outcome.promotable, reason)
            self.assertFalse(outcome.semantic_validation_valid, reason)


class SemanticFailureStillNeverRetries(unittest.TestCase):
    """Re-proven THROUGH THE GATEWAY, not just through a bare runner."""

    def _payload(self, valid=True):
        from tests.test_feasibility_compiler_01 import _golden_payload
        payload = _golden_payload()
        if not valid:
            payload["statements"][0]["authority_refs"] = []
        return payload

    def test_one_gateway_call_for_a_vr_invalid_payload(self):
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps(self._payload(valid=False))),
            _outcome(raw_text=json.dumps(self._payload(valid=True))),
        ])
        runner = compiler.gateway_runner(caller=recorder)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        outcome = compiler.compile_feasibility(evidence, runner=runner)
        self.assertEqual(len(recorder.calls), 1,
                         "a second gateway call would be the validator teaching "
                         "the model the answer")
        self.assertFalse(outcome.promotable)
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_SEMANTIC)
        self.assertIsNotNone(outcome.go_pdz_payload)

    def test_a_clean_payload_compiles_through_the_gateway(self):
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps(self._payload(valid=True)))])
        runner = compiler.gateway_runner(caller=recorder)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        outcome = compiler.compile_feasibility(evidence, runner=runner)
        self.assertTrue(outcome.typed_output_valid)
        self.assertTrue(outcome.promotable)
        self.assertEqual(len(recorder.calls), 1)

    def test_a_malformed_payload_retries_through_the_gateway_and_stops(self):
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps({"not": "a contract"})),
            _outcome(raw_text=json.dumps({"still": "not"})),
            _outcome(raw_text=json.dumps(self._payload(valid=True))),
        ])
        runner = compiler.gateway_runner(caller=recorder)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        outcome = compiler.compile_feasibility(evidence, runner=runner)
        self.assertEqual(len(recorder.calls), compiler.MAX_STRUCTURAL_ATTEMPTS)
        self.assertFalse(outcome.typed_output_valid)


class GovernanceStaysOutsideTheFramework(unittest.TestCase):
    """Section 3."""

    def test_an_unauthorized_decision_stops_before_any_call(self):
        recorder = RecordingGateway([_outcome(parsed={"a": 1})])
        runner = compiler.gateway_runner(caller=recorder)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        outcome = compiler.compile_feasibility(
            evidence, runner=runner, authorization={"decision": "deny"})
        self.assertEqual(len(recorder.calls), 0, "denied means never sent")
        self.assertEqual(outcome.failure_reason, compiler.FAILURE_PROVIDER_CONFIG)
        self.assertIsNone(outcome.go_pdz_payload)

    def test_require_approval_is_not_an_allow(self):
        recorder = RecordingGateway([_outcome(parsed={"a": 1})])
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner, authorization={"decision": "require_approval"})
        self.assertEqual(len(recorder.calls), 0)
        self.assertIsNotNone(outcome.failure_reason)

    def test_an_allowing_decision_proceeds(self):
        from tests.test_feasibility_compiler_01 import _golden_payload
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps(_golden_payload()))])
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner, authorization={"decision": "allow"})
        self.assertEqual(len(recorder.calls), 1)
        self.assertTrue(outcome.promotable)

    def test_the_adapter_itself_decides_no_governance(self):
        """It inherits the gateway's declared silence on the subject."""
        code = code_only(gateway)
        self.assertNotIn("security_policy", code)
        self.assertNotIn("evaluate_action", code)

    def test_the_allowing_set_matches_the_policy_vocabulary(self):
        from services import security_policy
        for decision in compiler.ALLOWING_DECISIONS:
            self.assertIn(decision, security_policy.KNOWN_DECISIONS)
        self.assertNotIn(security_policy.DECISION_DENY,
                         compiler.ALLOWING_DECISIONS)
        self.assertNotIn(security_policy.DECISION_REQUIRE_APPROVAL,
                         compiler.ALLOWING_DECISIONS)


class TheCredentialStatusIsReportedNotWorkedAround(unittest.TestCase):
    """Section 5."""

    def test_status_names_the_stop_without_revealing_anything(self):
        status = compiler.credential_status("gemini")
        self.assertEqual(status["provider"], "gemini")
        self.assertIn("credential_present", status)
        self.assertNotIn("api_key", status)
        self.assertNotIn("key", json.dumps(status).replace("credential_present", ""))

    def test_no_credential_is_ever_defaulted_or_generated(self):
        source = inspect.getsource(compiler.resolve_credential)
        self.assertIn("os.getenv", source)
        for banned in ("secrets.", "uuid", "= \"sk-", "= 'sk-"):
            self.assertNotIn(banned, source)

    def test_the_variable_consulted_is_the_one_the_app_already_governs(self):
        source = inspect.getsource(compiler.resolve_credential)
        self.assertIn("GEMINI_API_KEY", source)
        self.assertIn("ANTHROPIC_API_KEY", source)


class TheCurrentModelIsRequestedWithNoSilentFallback(unittest.TestCase):
    """CLAUDE-FEASIBILITY-MODEL-03, section 1 and 2.

    The gateway's Gemini path resolves `model or os.getenv("GEMINI_MODEL",
    DEFAULT_GEMINI_MODEL)`. So handing it `model=None` is not neutral - it is a
    silent downgrade to gemini-2.5-flash, which is exactly what section 1
    forbids. These tests prove an explicit model always arrives.
    """

    def _compile(self, **kwargs):
        from tests.test_feasibility_compiler_01 import _golden_payload
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps(_golden_payload()))])
        runner = compiler.gateway_runner(caller=recorder, **kwargs)
        evidence = compiler.FeasibilityEvidence(
            investigation_id="INV-1", input_address="100 Example Avenue")
        outcome = compiler.compile_feasibility(evidence, runner=runner)
        return outcome, recorder

    def test_the_gateway_receives_the_current_model_explicitly(self):
        _outcome_, recorder = self._compile()
        self.assertEqual(recorder.calls[0]["model"], "gemini-3.8-flash")

    def test_the_gateway_is_never_handed_none(self):
        _outcome_, recorder = self._compile()
        self.assertIsNotNone(recorder.calls[0]["model"],
                             "None would let the gateway resolve its own default")

    def test_the_feasibility_model_is_not_the_gateways_default(self):
        """Section 2: the two must be independently configurable."""
        self.assertNotEqual(compiler.resolve_model(),
                            llm_gateway.DEFAULT_GEMINI_MODEL)
        self.assertEqual(llm_gateway.DEFAULT_GEMINI_MODEL, "gemini-2.5-flash")

    def test_the_gateways_default_is_left_alone(self):
        """A production caller (sheet_vision) passes model=None and relies on it."""
        import config
        self.assertEqual(config.BaseConfig.GEMINI_MODEL, "gemini-2.5-flash")
        self.assertEqual(config.BaseConfig.FEASIBILITY_MODEL, "gemini-3.8-flash")

    def test_no_configured_model_raises_rather_than_defaulting(self):
        original = compiler.resolve_model
        compiler.resolve_model = lambda: ""
        try:
            with self.assertRaises(RuntimeError):
                compiler.gateway_runner(caller=RecordingGateway([_outcome()]))
        finally:
            compiler.resolve_model = original

    def test_the_model_is_resolved_at_call_time_not_import_time(self):
        """`.env` is read by config at ITS import; a module-level getenv in the
        compiler could run first and silently use a stale literal."""
        source = inspect.getsource(compiler.resolve_model)
        self.assertIn("_config()", source)
        module_source = code_only(compiler)
        self.assertNotIn('os.getenv("FEASIBILITY_MODEL"', module_source.split(
            "def resolve_model")[0])

    def test_the_configuration_reports_where_each_value_came_from(self):
        configuration = compiler.model_configuration()
        self.assertEqual(configuration["model"], "gemini-3.8-flash")
        self.assertEqual(configuration["provider"], "gemini")
        self.assertIn("config.", configuration["model_source"])
        self.assertEqual(configuration["gateway_default_model_not_used"],
                         "gemini-2.5-flash")

    def test_a_model_the_provider_rejects_is_its_own_named_stop(self):
        """CURRENT_MODEL_UNAVAILABLE, distinct from a missing credential: 'we
        have no key' and 'the key works and that model does not exist' call for
        different actions."""
        recorder = RecordingGateway([_outcome(
            ran=False,
            skipped_reason="models/gemini-3.8-flash is not found for API version")])
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertEqual(outcome.failure_reason,
                         compiler.CURRENT_MODEL_UNAVAILABLE)
        self.assertIsNone(outcome.go_pdz_payload)

    def test_the_credential_status_names_where_to_populate_it(self):
        status = compiler.credential_status()
        self.assertEqual(status["status"], compiler.PROVIDER_CREDENTIAL_REQUIRED
                         if not status["credential_present"] else "READY")
        self.assertIn("GEMINI_API_KEY", status["credential_location"])


class TheOutputBudgetWasMeasuredNotChosen(unittest.TestCase):
    """CLAUDE-FEASIBILITY-MODEL-03, from the first live probe.

    The gateway's 4000-token call budget let the first live 35 Taber replay fit
    and report promotable; the SECOND run of the identical probe was truncated
    mid-statement. Measured afterwards: that document costs 2,381 candidate plus
    1,342 thought tokens - just under the old cap, which is exactly why it
    passed once and failed once. A budget that turns on luck is a coin toss.
    """

    def test_the_budget_is_resolved_from_config_at_call_time(self):
        import config
        self.assertEqual(str(config.BaseConfig.FEASIBILITY_MAX_OUTPUT_TOKENS),
                         "16000")
        self.assertEqual(compiler.resolve_max_output_tokens(), 16000)

    def test_the_budget_reaches_the_gateway(self):
        from tests.test_feasibility_compiler_01 import _golden_payload
        recorder = RecordingGateway([
            _outcome(raw_text=json.dumps(_golden_payload()))])
        runner = compiler.gateway_runner(caller=recorder)
        compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertEqual(recorder.calls[0]["max_tokens"],
                         compiler.resolve_max_output_tokens())

    def test_a_nonsense_budget_falls_back_to_a_usable_floor(self):
        import os
        original = os.environ.get("FEASIBILITY_MAX_OUTPUT_TOKENS")
        try:
            os.environ["FEASIBILITY_MAX_OUTPUT_TOKENS"] = "not-a-number"
            self.assertGreaterEqual(compiler.resolve_max_output_tokens(), 1000)
        finally:
            if original is None:
                os.environ.pop("FEASIBILITY_MAX_OUTPUT_TOKENS", None)
            else:
                os.environ["FEASIBILITY_MAX_OUTPUT_TOKENS"] = original

    def test_truncation_is_its_own_named_failure(self):
        """Not MODEL_UNAVAILABLE: the model and key are fine and the document was
        simply longer than the budget."""
        recorder = RecordingGateway([_outcome(
            ran=False,
            skipped_reason="Model's response was cut off before it finished "
                           "(max_tokens).")])
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertEqual(outcome.failure_reason,
                         compiler.FAILURE_OUTPUT_TRUNCATED)

    def test_truncation_is_not_retried_against_the_same_wall(self):
        recorder = RecordingGateway([_outcome(
            ran=False, skipped_reason="cut off before it finished (max_tokens)")])
        runner = compiler.gateway_runner(caller=recorder)
        compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertEqual(len(recorder.calls), 1,
                         "retrying without raising the budget burns a call on "
                         "the same wall")

    def test_a_truncated_response_never_becomes_a_partial_document(self):
        recorder = RecordingGateway([_outcome(
            ran=False, skipped_reason="max_tokens")])
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertIsNone(outcome.go_pdz_payload)
        self.assertFalse(outcome.promotable)


class RequestedAndResolvedAreDifferentFacts(unittest.TestCase):
    """Section 5. The provider reports both; this boundary used to drop one.

    I reported "provider exposed no resolved model" after the first live probe.
    That was wrong in ATTRIBUTION: the Gemini response carries `model_version`
    and `usage_metadata`, and `llm_gateway` read neither - it echoed back the
    model the caller ASKED for. An ARCHIOSK limitation presented as a provider
    limitation is the worse of the two, because it stops you looking.
    """

    def test_the_outcome_can_carry_what_the_provider_reported(self):
        fields = llm_gateway.LLMCallOutcome.__dataclass_fields__
        self.assertIn("resolved_model", fields)
        self.assertIn("usage", fields)

    def test_both_new_fields_default_to_none_for_existing_callers(self):
        outcome = llm_gateway.LLMCallOutcome(ran=True)
        self.assertIsNone(outcome.resolved_model)
        self.assertIsNone(outcome.usage)

    def test_the_envelope_separates_requested_from_resolved(self):
        from tests.test_feasibility_compiler_01 import _golden_payload
        recorder = RecordingGateway([_outcome(
            raw_text=json.dumps(_golden_payload()),
            model="gemini-3.8-flash")])
        recorder.outcomes[0].resolved_model = "gemini-3.8-flash-002"
        recorder.outcomes[0].usage = {"total_token_count": 9476}
        runner = compiler.gateway_runner(caller=recorder)
        outcome = compiler.compile_feasibility(
            compiler.FeasibilityEvidence(investigation_id="I", input_address="A"),
            runner=runner)
        self.assertEqual(outcome.model, "gemini-3.8-flash",
                         "the envelope's `model` is what was REQUESTED")
        self.assertEqual(outcome.model_version, "gemini-3.8-flash-002",
                         "`model_version` is what the provider REPORTED")

    def test_usage_carries_only_named_integer_counts(self):
        """Safe operational metadata; never prompt or response content."""
        source = inspect.getsource(llm_gateway._gemini_usage)
        self.assertIn("prompt_token_count", source)
        self.assertIn("isinstance(value, int)", source)
        for banned in ("model_dump", "__dict__", "vars(usage)"):
            self.assertNotIn(banned, source)


class TheModelIsToldTheContractItMustSatisfy(unittest.TestCase):
    """The first live probe failed here, and it was the harness's fault.

    gemini-3.8-flash produced a careful document - right statement kinds, the
    supplied authority cited, the deterministic token respected, nothing invented
    - using field names it had to guess, because the instructions named none of
    the contract's keys and `output_type=str` enforced nothing. It was asked to
    hit a target it was never shown.
    """

    def test_the_prompt_is_generated_from_the_canonical_schema(self):
        prompt = compiler.output_contract_prompt()
        self.assertIn(json.dumps(contract.SCHEMA, indent=1, sort_keys=True),
                      prompt, "the canonical schema itself, not a restatement")

    def test_there_is_no_competing_duplicate_schema(self):
        """Section 7: reuse go_pdz_contract, do not fork it."""
        code = code_only(compiler)
        self.assertNotIn('"required": [', code)
        self.assertIn("contract.SCHEMA", code)

    def test_the_prompt_names_the_keys_the_model_previously_guessed(self):
        prompt = compiler.output_contract_prompt()
        for key in ("contract", "schema_version", "next_authorized_gate",
                    "subject", "authorities", "statements", "result_status",
                    "site_specific_exceptions", "statement_id", "spatial_basis"):
            self.assertIn(key, prompt, key)

    def test_the_prompt_pins_the_const_values(self):
        prompt = compiler.output_contract_prompt()
        self.assertIn(contract.CONTRACT_ID, prompt)
        self.assertIn(contract.GATE_01, prompt)
        self.assertIn(contract.GATE_02, prompt)
        self.assertIn("GOVERNED_RESULT", prompt)

    def test_a_structural_retry_says_only_that_the_shape_was_wrong(self):
        """It must never become a channel for VR findings."""
        source = inspect.getsource(compiler.gateway_runner)
        self.assertIn("did not match the schema", source)
        for banned in ("VR-", "validator", "findings"):
            self.assertNotIn(banned, source)


if __name__ == "__main__":
    unittest.main()
