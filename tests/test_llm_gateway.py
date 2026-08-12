"""
CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0) - services/llm_gateway.py's own
call_llm_json in isolation. This is the shared boundary extracted from
what used to be three independently duplicated client-setup/error-
handling/JSON-parsing copies (services/requirement_investigation.py,
services/project_qa.py, services/project_briefing.py) - these tests
prove the extraction preserved every one of those modules' own existing
degrade-safe behaviors (no key / timeout / malformed / truncated), one
implementation instead of three.

Follows this repo's own hermetic convention exactly
(tests/test_external_ai_governance.py's patch("anthropic.Anthropic")
pattern) - never a live model call.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.llm_gateway import call_llm_json, resolve_timeout_from_env


def _mock_response(text_out: str, stop_reason: str = "end_turn"):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = stop_reason
    return fake_response


class CallLlmJsonTests(unittest.TestCase):
    def test_no_api_key_skips_without_calling_the_model(self):
        with patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": d):
            outcome = call_llm_json(user_prompt="hello", log_label="Test call")
        self.assertFalse(outcome.ran)
        self.assertIn("No ANTHROPIC_API_KEY", outcome.skipped_reason)
        self.assertIn("Test call", outcome.skipped_reason)

    def test_successful_call_returns_parsed_json_and_provenance(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "ok", "grounded_in": []}'
            )
            outcome = call_llm_json(
                user_prompt="hello", system_prompt="be helpful",
                api_key="fake-key", model="fake-model", timeout=5.0,
            )
        self.assertTrue(outcome.ran)
        self.assertEqual(outcome.parsed, {"answer": "ok", "grounded_in": []})
        self.assertEqual(outcome.raw_text, '{"answer": "ok", "grounded_in": []}')
        self.assertEqual(outcome.provider, "anthropic")
        self.assertEqual(outcome.model, "fake-model")
        self.assertIsNotNone(outcome.requested_at)
        # system= only passed through when a system_prompt was actually given.
        _, kwargs = MockClient.return_value.messages.create.call_args
        self.assertEqual(kwargs["system"], "be helpful")

    def test_no_system_prompt_is_not_sent(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response('{"a": 1}')
            call_llm_json(user_prompt="hello", api_key="fake-key")
        _, kwargs = MockClient.return_value.messages.create.call_args
        self.assertNotIn("system", kwargs)

    def test_fenced_json_is_stripped(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '```json\n{"answer": "ok"}\n```'
            )
            outcome = call_llm_json(user_prompt="hello", api_key="fake-key")
        self.assertTrue(outcome.ran)
        self.assertEqual(outcome.parsed, {"answer": "ok"})

    def test_timeout_degrades_honestly(self):
        import anthropic

        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = anthropic.APITimeoutError(request=MagicMock())
            outcome = call_llm_json(user_prompt="hello", api_key="fake-key", timeout=7.0)
        self.assertFalse(outcome.ran)
        self.assertIn("timed out after 7s", outcome.skipped_reason)

    def test_generic_exception_degrades_honestly_never_raises(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("boom")
            outcome = call_llm_json(user_prompt="hello", api_key="fake-key")
        self.assertFalse(outcome.ran)
        self.assertEqual(outcome.skipped_reason, "An error occurred calling the model.")

    def test_malformed_json_degrades_honestly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response("not json at all")
            outcome = call_llm_json(user_prompt="hello", api_key="fake-key")
        self.assertFalse(outcome.ran)
        self.assertEqual(outcome.skipped_reason, "Model returned malformed output.")

    def test_truncation_at_max_tokens_is_distinguished_from_generic_malformed(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "cut off mid', stop_reason="max_tokens",
            )
            outcome = call_llm_json(user_prompt="hello", api_key="fake-key")
        self.assertFalse(outcome.ran)
        self.assertIn("cut off", outcome.skipped_reason)
        self.assertEqual(outcome.stop_reason, "max_tokens")

    def test_explicit_timeout_is_used_as_is_never_re_resolved(self):
        """A caller (e.g. project_briefing.py's own prompt-size scaling)
        that already resolved/scaled its own timeout must have that exact
        value used - call_llm_json must not silently re-derive a fresh
        env default and discard it."""
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv") as mock_getenv:
            MockClient.return_value.messages.create.return_value = _mock_response('{"a": 1}')
            call_llm_json(user_prompt="hello", api_key="fake-key", timeout=42.0)
        # ANTHROPIC_TIMEOUT_SECONDS must never be consulted when an
        # explicit timeout was already given.
        for call in mock_getenv.call_args_list:
            self.assertNotEqual(call.args[0] if call.args else None, "ANTHROPIC_TIMEOUT_SECONDS")
        _, client_kwargs = MockClient.call_args
        self.assertEqual(client_kwargs["timeout"], 42.0)


class ResolveTimeoutFromEnvTests(unittest.TestCase):
    def test_explicit_value_wins(self):
        self.assertEqual(resolve_timeout_from_env(12.0, 30.0), 12.0)

    def test_falls_back_to_env_default(self):
        with patch("services.llm_gateway.os.getenv", return_value="99"):
            self.assertEqual(resolve_timeout_from_env(None, 30.0), 99.0)

    def test_falls_back_to_provided_default_when_env_unset(self):
        with patch("services.llm_gateway.os.getenv", side_effect=lambda k, d: d):
            self.assertEqual(resolve_timeout_from_env(None, 30.0), 30.0)


if __name__ == "__main__":
    unittest.main()
