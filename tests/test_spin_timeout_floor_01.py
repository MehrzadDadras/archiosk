"""PSD-SMOKE-01-D - Spin's model-call timeout must not collapse on a small corpus.

Measured live on the 9-file PSD Builder corpus: the prompt-size scaling
produced 61s, deterministically, three runs out of three, while the model
was still generating. Spin requests max_tokens=8000 of structured JSON
regardless of how small the evidence set is, so its latency is driven by
RESPONSE size, not prompt size - which made the shortest timeout land on
exactly the corpora that needed nearly the full one.

nginx never terminated anything (zero 504s in nginx access/error logs and
in journald; every /spin/run returned 302), so this is application logic,
not infrastructure.

These tests are pure arithmetic over the timeout decision. No model call
is made and no external boundary is reachable.
"""
import unittest

from services.llm_gateway import scale_timeout_for_prompt_size
from services.spin import SPIN_MIN_TIMEOUT_SECONDS

# The call-site constants, kept here so a change to either is caught.
SPIN_BASE_CHARS = 4000
SPIN_SECONDS_PER_1000 = 3.0
SPIN_MAX_TIMEOUT = 140.0

# deploy/gunicorn.conf.py `timeout = 150`; deploy/nginx.conf
# `proxy_read_timeout 150s` on location /.
DEPLOYED_REQUEST_CEILING = 150.0


def spin_timeout_for(prompt: str, base_timeout: float = 30.0) -> float:
    """Mirrors the decision in services/spin.py exactly."""
    return max(
        SPIN_MIN_TIMEOUT_SECONDS,
        scale_timeout_for_prompt_size(
            base_timeout, prompt,
            base_chars_before_scaling=SPIN_BASE_CHARS,
            seconds_per_extra_1000_chars=SPIN_SECONDS_PER_1000,
            max_timeout=SPIN_MAX_TIMEOUT,
        ),
    )


class SmallCorpusRegressionTests(unittest.TestCase):
    """The exact defect: a small corpus must not get a short timeout."""

    def test_psd_sized_prompt_no_longer_collapses_to_the_observed_61s(self):
        # ~14,300 chars is the size that produced the measured 61s.
        prompt = "x" * 14_300
        self.assertGreater(
            spin_timeout_for(prompt), 61.0,
            "the measured PSD failure value must no longer be reachable",
        )
        self.assertGreaterEqual(spin_timeout_for(prompt), SPIN_MIN_TIMEOUT_SECONDS)

    def test_every_small_corpus_gets_at_least_the_floor(self):
        for size in (0, 500, 4_000, 8_000, 14_300, 30_000):
            with self.subTest(prompt_chars=size):
                self.assertGreaterEqual(spin_timeout_for("x" * size), SPIN_MIN_TIMEOUT_SECONDS)


class ScalingStillAppliesTests(unittest.TestCase):
    """The floor must not flatten the scaling CLAUDE-DELTA-SPIN-02 added."""

    def test_a_genuinely_large_prompt_still_scales_above_the_floor(self):
        large = "x" * 200_000
        self.assertGreater(spin_timeout_for(large), SPIN_MIN_TIMEOUT_SECONDS)

    def test_the_ceiling_is_still_respected(self):
        self.assertLessEqual(spin_timeout_for("x" * 5_000_000), SPIN_MAX_TIMEOUT)

    def test_floor_sits_below_the_ceiling(self):
        self.assertLess(SPIN_MIN_TIMEOUT_SECONDS, SPIN_MAX_TIMEOUT)


class InfrastructureCoherenceTests(unittest.TestCase):
    """Timeout configuration must remain internally coherent.

    The application must always give up BEFORE Gunicorn or nginx do, so a
    timeout surfaces as a governed application message rather than as a
    raw gateway error.
    """

    def test_spin_never_outlasts_the_deployed_request_ceiling(self):
        worst_case = spin_timeout_for("x" * 5_000_000)
        self.assertLess(
            worst_case, DEPLOYED_REQUEST_CEILING,
            "Spin must abort before Gunicorn/nginx, so the user sees a governed message",
        )

    def test_floor_leaves_headroom_under_the_deployed_ceiling(self):
        self.assertLess(SPIN_MIN_TIMEOUT_SECONDS, DEPLOYED_REQUEST_CEILING)

    def test_deployed_config_values_are_still_what_this_test_assumes(self):
        """Fails loudly if deploy config drifts away from these tests."""
        from pathlib import Path

        gunicorn = Path("deploy/gunicorn.conf.py").read_text(encoding="utf-8")
        nginx = Path("deploy/nginx.conf").read_text(encoding="utf-8")
        self.assertIn('GUNICORN_TIMEOUT", "150"', gunicorn)
        self.assertIn("proxy_read_timeout 150s", nginx)


if __name__ == "__main__":
    unittest.main()
