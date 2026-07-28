"""
CLAUDE-P19 - hermetic tests for the Golden Laboratory Suite v1 regression
plumbing: the manifest (tests/self_test/manifest.py), the run-record
schema (tests/self_test/run_record.py), and the common runner (tools/
self_test_runner.py). No real Anthropic calls here - tier modules'
run_tier() functions are monkeypatched with fixed SpecimenResult lists,
exactly the way every other hermetic test in this suite mocks the
Anthropic client rather than calling it.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import importlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.self_test.manifest import TIERS, tier_by_id
from tests.self_test.mutation_schema import DIFFICULTY_TIERS
from tests.self_test.run_record import SpecimenResult, SuiteRun
from tools import self_test_runner


class ManifestTests(unittest.TestCase):
    def test_all_six_difficulty_tiers_are_registered_exactly_once(self):
        registered_ids = [t.tier_id for t in TIERS]
        self.assertEqual(sorted(registered_ids), sorted(DIFFICULTY_TIERS))
        self.assertEqual(len(registered_ids), len(set(registered_ids)))

    def test_every_registered_lab_module_actually_exposes_run_tier(self):
        for tier in TIERS:
            module = importlib.import_module(tier.lab_module)
            self.assertTrue(callable(getattr(module, "run_tier", None)), tier.lab_module)

    def test_tier_by_id_raises_for_unknown_tier(self):
        with self.assertRaises(KeyError):
            tier_by_id("not-a-real-tier")

    def test_manifest_carries_no_answer_key_content(self):
        # The manifest is pure routing metadata (tier id -> lab module
        # dotted path) - it must never itself become a second place an
        # answer key could leak from, alongside mutation_schema.py's own
        # investigator-blindness discipline.
        for tier in TIERS:
            self.assertFalse(hasattr(tier, "answer_key"))
            self.assertFalse(hasattr(tier, "expected_detection"))


class SpecimenResultPassedTests(unittest.TestCase):
    def _base(self, **overrides) -> SpecimenResult:
        defaults = dict(
            tier_id="obvious", specimen_id="x", description="x",
            production_reasoning_path="x", corpus_version="1.0",
        )
        defaults.update(overrides)
        return SpecimenResult(**defaults)

    def test_did_not_run_is_always_false(self):
        self.assertFalse(self._base(ran=False).passed())

    def test_qualitative_only_is_none_even_with_other_fields_set(self):
        s = self._base(requires_qualitative_read=True, caught=True)
        self.assertIsNone(s.passed())

    def test_no_signal_at_all_is_none(self):
        self.assertIsNone(self._base().passed())

    def test_clean_baseline_with_only_false_positives_correctly_fails(self):
        # No caught/anchor_correctness/etc set (nothing to "catch" on a
        # clean baseline) - only false_positives populated. This must
        # still yield a real False verdict, not None (a common trap: see
        # run_record.py's own has_signal fix).
        s = self._base(false_positives=["spurious flag"])
        self.assertFalse(s.passed())

    def test_clean_baseline_with_no_false_positives_passes(self):
        s = self._base(false_positives=[])
        # Still no signal at all (caught=None, false_positives=[]) - must
        # be None, not a fabricated True.
        self.assertIsNone(s.passed())

    def test_all_relevant_dims_true_and_no_false_positives_passes(self):
        s = self._base(caught=True, anchor_correctness=True)
        self.assertTrue(s.passed())

    def test_one_relevant_dim_false_fails_even_if_others_true(self):
        s = self._base(caught=True, anchor_correctness=False)
        self.assertFalse(s.passed())

    def test_malformed_output_fails_even_with_true_dims(self):
        s = self._base(caught=True, malformed_or_truncated_output=True)
        self.assertFalse(s.passed())


class SuiteRunDimensionSummaryTests(unittest.TestCase):
    def test_dimension_summary_never_collapses_to_one_score(self):
        specimens = [
            SpecimenResult(
                tier_id="obvious", specimen_id="a", description="x", production_reasoning_path="x",
                corpus_version="1.0", caught=True, model_call_count=1, latency_seconds=1.5,
            ),
            SpecimenResult(
                tier_id="semantic", specimen_id="b", description="x", production_reasoning_path="x",
                corpus_version="1.0", caught=False, false_positives=["spurious"], model_call_count=2, latency_seconds=2.0,
            ),
            SpecimenResult(
                tier_id="lifecycle", specimen_id="c", description="x", production_reasoning_path="x",
                corpus_version="1.0", requires_qualitative_read=True, model_call_count=1, latency_seconds=0.5,
            ),
        ]
        run = SuiteRun(
            run_id="r1", suite_version="golden_laboratory_suite_v1", started_at="t0", completed_at="t1",
            tiers_executed=["obvious", "semantic", "lifecycle"], app_model_default="claude-sonnet-4-6",
            specimens=[s.__dict__ for s in specimens],
        )
        summary = run.dimension_summary()
        self.assertEqual(summary["caught"]["applicable"], 2)
        self.assertEqual(summary["caught"]["true"], 1)
        self.assertEqual(summary["caught"]["false"], 1)
        self.assertEqual(summary["false_positives_total"], 1)
        self.assertEqual(summary["qualitative_only_total"], 1)
        self.assertEqual(summary["model_call_count_total"], 4)
        self.assertAlmostEqual(summary["latency_seconds_total"], 4.0)
        # Multiple independent keys, not one aggregate - the tier's own requirement.
        self.assertGreater(len(summary), 5)

    def test_suite_run_round_trips_through_json(self):
        specimen = SpecimenResult(
            tier_id="obvious", specimen_id="a", description="x", production_reasoning_path="x", corpus_version="1.0",
        )
        run = SuiteRun(
            run_id="r1", suite_version="golden_laboratory_suite_v1", started_at="t0", completed_at="t1",
            tiers_executed=["obvious"], app_model_default="claude-sonnet-4-6", specimens=[specimen.__dict__],
        )
        raw = json.loads(json.dumps(run.to_dict()))
        self.assertEqual(raw["run_id"], "r1")
        self.assertEqual(raw["specimens"][0]["specimen_id"], "a")


class RunnerTests(unittest.TestCase):
    """Mocks each tier's run_tier() - no real Anthropic calls."""

    def setUp(self):
        self.tmp_runs_dir = Path(tempfile.mkdtemp(prefix="beehive_test_runs_"))

    def tearDown(self):
        shutil.rmtree(self.tmp_runs_dir, ignore_errors=True)

    def _fake_run_tier_for(self, tier_id: str):
        def _fake():
            return [SpecimenResult(
                tier_id=tier_id, specimen_id=f"{tier_id}-fake", description="fake specimen",
                production_reasoning_path="fake", corpus_version="1.0", caught=True, model_call_count=1,
            )]
        return _fake

    def test_run_suite_selects_only_requested_tiers(self):
        with patch("importlib.import_module") as mock_import:
            def side_effect(dotted_path):
                for tier in TIERS:
                    if tier.lab_module == dotted_path:
                        fake_module = type("FakeModule", (), {"run_tier": staticmethod(self._fake_run_tier_for(tier.tier_id))})
                        return fake_module
                raise AssertionError(f"unexpected import: {dotted_path}")
            mock_import.side_effect = side_effect

            run = self_test_runner.run_suite(tier_ids=["obvious", "lifecycle"])

        self.assertEqual(run.tiers_executed, ["obvious", "lifecycle"])
        self.assertEqual(len(run.specimens), 2)
        self.assertEqual(run.suite_version, "golden_laboratory_suite_v1")

    def test_run_suite_rejects_unknown_tier(self):
        with self.assertRaises(ValueError):
            self_test_runner.run_suite(tier_ids=["not-a-real-tier"])

    def test_persist_run_writes_a_readable_json_file(self):
        run = SuiteRun(
            run_id="r1", suite_version="golden_laboratory_suite_v1", started_at="2026-01-01T00:00:00+00:00",
            completed_at="2026-01-01T00:01:00+00:00", tiers_executed=["obvious"], app_model_default="claude-sonnet-4-6",
            specimens=[SpecimenResult(
                tier_id="obvious", specimen_id="x", description="x", production_reasoning_path="x", corpus_version="1.0",
            ).__dict__],
        )
        with patch.object(self_test_runner, "RUNS_DIR", self.tmp_runs_dir):
            path = self_test_runner.persist_run(run)
        self.assertTrue(path.exists())
        loaded = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(loaded["run_id"], "r1")

    def test_print_summary_does_not_raise(self):
        run = SuiteRun(
            run_id="r1", suite_version="golden_laboratory_suite_v1", started_at="t0", completed_at="t1",
            tiers_executed=["obvious"], app_model_default="claude-sonnet-4-6",
            specimens=[SpecimenResult(
                tier_id="obvious", specimen_id="x", description="x", production_reasoning_path="x",
                corpus_version="1.0", caught=True, false_positives=["oops"],
            ).__dict__],
        )
        self_test_runner.print_summary(run)  # must not raise


if __name__ == "__main__":
    unittest.main()
