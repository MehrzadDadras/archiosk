"""
CLAUDE-CA1D-COMPOSER-TIMEOUT-FIX-01 - live Product Owner report: a real,
broad "characterize every discrepancy in this project, with 5 fields
each" question failed on production with "Request timed out after 30s."
Reproduced locally against the real reported project: root-caused to
TWO compounding gaps, both fixed here -

  1. services/project_qa.py's max_tokens=1500 was genuinely too small
     for this class of question (the model was cut off mid-JSON,
     stop_reason=max_tokens, before it could finish) - raised to 3000,
     empirically confirmed sufficient against the real project.
  2. services/project_qa.py had NO prompt-size timeout scaling at all,
     unlike services/project_briefing.py, which already fixed the exact
     same failure mode under CLAUDE-P40-B 3.2. The scaling formula is
     promoted out of project_briefing.py's own former private
     `_scale_timeout_for_prompt_size` into
     services/llm_gateway.py's scale_timeout_for_prompt_size (shared,
     not duplicated a second time), reused by both callers.

Confirmed via direct SSH inspection that this deployment's own Gunicorn
worker timeout (150s, deploy/gunicorn.conf.py) and nginx
proxy_read_timeout (150s on location /, deploy/nginx.conf) already had
far more headroom than the old flat 30s application ceiling - so this
fix is purely an application-layer change, no infra config touched.

Run via:

    python -m unittest tests.test_ca1d_composer_timeout_fix_01 -v
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.llm_gateway import scale_timeout_for_prompt_size


def _mock_response(text_out: str, stop_reason: str = "end_turn"):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = stop_reason
    return fake_response


class ScaleTimeoutForPromptSizeTests(unittest.TestCase):
    def test_small_prompt_stays_at_base_timeout(self):
        prompt = "short question" * 10  # well under the 4000-char default floor
        self.assertEqual(scale_timeout_for_prompt_size(30.0, prompt), 30.0)

    def test_large_prompt_scales_up(self):
        prompt = "x" * 14000  # base 4000 + 10000 extra chars
        # default rate 3.0s per extra 1000 chars -> 30 extra seconds
        self.assertEqual(scale_timeout_for_prompt_size(30.0, prompt), 60.0)

    def test_never_exceeds_max_timeout(self):
        prompt = "x" * 1_000_000
        self.assertEqual(scale_timeout_for_prompt_size(30.0, prompt, max_timeout=90.0), 90.0)

    def test_custom_rate_and_base_respected(self):
        prompt = "x" * 5000  # base 4000 + 1000 extra
        result = scale_timeout_for_prompt_size(
            45.0, prompt, base_chars_before_scaling=4000,
            seconds_per_extra_1000_chars=3.0, max_timeout=90.0,
        )
        self.assertEqual(result, 48.0)

    def test_project_briefing_defaults_are_unchanged(self):
        """Behavior-preservation check for the extraction - the exact
        constants project_briefing.py's own private function used to
        hardcode (base 4000 chars, 3.0s/1000 extra chars, 90s max),
        called the same way its own call site now calls the shared
        function."""
        prompt = "x" * 20000  # 16000 extra chars -> 48s added, capped at 90
        result = scale_timeout_for_prompt_size(
            45.0, prompt, base_chars_before_scaling=4000,
            seconds_per_extra_1000_chars=3.0, max_timeout=90.0,
        )
        self.assertEqual(result, 90.0)  # 45 + 48 = 93, capped to 90


class ProjectQATimeoutAndTokenBudgetTests(unittest.TestCase):
    """Exercises services/project_qa.py's answer_project_question
    directly (mocked anthropic.Anthropic - hermetic, per this repo's own
    convention) to prove the fix actually reaches the real call site,
    not just the shared helper in isolation."""

    def test_small_question_stays_close_to_the_30s_base_timeout(self):
        """Not an exact-30.0 assertion - _build_prompt's own fixed
        schema-instruction boilerplate (no evidence at all) is itself
        already ~4.4k chars, just over scale_timeout_for_prompt_size's
        4000-char floor, so even a trivial question scales up by ~1.3s
        (harmless, still nowhere near the large-evidence case below).
        Asserting exactly 30.0 here would be fragile to the prompt's own
        boilerplate length - which will drift as instruction text is
        edited - rather than testing this fix's actual property: a
        small question must NOT scale anywhere near as much as a large
        evidence blob does."""
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "ok", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            from services.project_qa import answer_project_question

            answer_project_question(
                question="What is the deadline?",
                document_filename="rfp.md",
                candidate_requirements=[],
                governed_requirements=[],
                milestones=[],
                api_key="fake-key",
            )
        _, client_kwargs = MockClient.call_args
        self.assertGreaterEqual(client_kwargs["timeout"], 30.0)
        self.assertLess(client_kwargs["timeout"], 40.0)

    def test_large_evidence_blob_scales_the_timeout_up(self):
        # A large candidate_requirements list pushes the built prompt well
        # past the 4000-char scaling floor, mirroring the real reported
        # project (1310 candidate items, 17.8k-char prompt).
        big_candidates = [{"text": f"Requirement text number {i} " * 5, "category": "other"} for i in range(80)]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "ok", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            from services.project_qa import answer_project_question

            answer_project_question(
                question="What discrepancies could prevent this proposal from moving forward?",
                document_filename="rfp.md",
                candidate_requirements=big_candidates,
                governed_requirements=[],
                milestones=[],
                api_key="fake-key",
            )
        _, client_kwargs = MockClient.call_args
        self.assertGreater(client_kwargs["timeout"], 30.0)
        self.assertLessEqual(client_kwargs["timeout"], 90.0)

    def test_explicit_caller_timeout_is_used_as_the_scaling_base(self):
        big_candidates = [{"text": f"Requirement text number {i} " * 5, "category": "other"} for i in range(80)]
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "ok", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            from services.project_qa import answer_project_question

            answer_project_question(
                question="What discrepancies could prevent this proposal from moving forward?",
                document_filename="rfp.md",
                candidate_requirements=big_candidates,
                governed_requirements=[],
                milestones=[],
                api_key="fake-key",
                timeout=50.0,
            )
        _, client_kwargs = MockClient.call_args
        self.assertGreater(client_kwargs["timeout"], 50.0)

    def test_max_tokens_is_3000_not_the_old_1500(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "ok", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            from services.project_qa import answer_project_question

            answer_project_question(
                question="What is the deadline?",
                document_filename="rfp.md",
                candidate_requirements=[],
                governed_requirements=[],
                milestones=[],
                api_key="fake-key",
            )
        _, create_kwargs = MockClient.return_value.messages.create.call_args
        self.assertEqual(create_kwargs["max_tokens"], 3000)

    def test_truncated_response_is_still_reported_honestly(self):
        """Regression guard - raising max_tokens doesn't remove the
        honest-degrade path, it just makes it fire less often. A
        response that STILL gets cut off must still degrade honestly,
        never fabricate a completed answer from a truncated one."""
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "cut off mid', stop_reason="max_tokens",
            )
            from services.project_qa import answer_project_question

            result = answer_project_question(
                question="What is the deadline?",
                document_filename="rfp.md",
                candidate_requirements=[],
                governed_requirements=[],
                milestones=[],
                api_key="fake-key",
            )
        self.assertFalse(result.ran)
        self.assertIn("cut off", result.skipped_reason)


if __name__ == "__main__":
    unittest.main()
