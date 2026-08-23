"""Focused coverage for persisted Spin timestamp presentation."""
from __future__ import annotations

import json
import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "case_workspace.html"
ROUTE = ROOT / "routes" / "workspace.py"
SCRIPT = ROOT / "static" / "js" / "spin_timestamps.js"


def _node_format(value: str) -> dict[str, str]:
    command = (
        "const fs=require('fs'),vm=require('vm');"
        f"const code=fs.readFileSync({json.dumps(str(SCRIPT))},'utf8');"
        "const context={window:{}};vm.runInNewContext(code,context);"
        f"const input={json.dumps(value)};"
        "process.stdout.write(JSON.stringify({input,output:context.window.ArchioskSpinTimestamps.format(input)}));"
    )
    env = os.environ.copy()
    env["TZ"] = "America/Toronto"
    result = subprocess.run(
        ["node", "-e", command], check=True, capture_output=True,
        text=True, encoding="utf-8", env=env,
    )
    return json.loads(result.stdout)


class SpinTimestampDisplayTests(unittest.TestCase):
    def test_all_visible_spin_surfaces_carry_persisted_timestamp_markers(self):
        body = TEMPLATE.read_text(encoding="utf-8")
        self.assertGreaterEqual(body.count('data-spin-timestamp="'), 3)
        self.assertIn("Latest:", body)
        self.assertIn("First Spin of", body)
        self.assertIn("{{ run.kind_label }}", body)

    def test_local_hour_and_minute_are_displayed(self):
        result = _node_format("2026-08-20T18:47:00+00:00")
        self.assertEqual(result["output"], "2026-08-20 · 2:47 PM")
        self.assertEqual(result["input"], "2026-08-20T18:47:00+00:00")

    def test_utc_timestamp_crossing_local_day_uses_local_date(self):
        result = _node_format("2026-08-20T02:47:00+00:00")
        self.assertEqual(result["output"], "2026-08-19 · 10:47 PM")

    def test_same_day_runs_remain_distinguishable(self):
        first = _node_format("2026-08-20T18:47:00+00:00")["output"]
        second = _node_format("2026-08-20T19:12:00+00:00")["output"]
        self.assertNotEqual(first, second)
        self.assertIn("2:47 PM", first)
        self.assertIn("3:12 PM", second)

    def test_server_ordering_still_uses_persisted_created_at(self):
        route = ROUTE.read_text(encoding="utf-8")
        self.assertIn("sorted(workspace.spin_runs, key=lambda r: r.get(\"created_at\") or \"\", reverse=True)", route)
        self.assertIn('data-spin-timestamp="{{ run.created_at }}"', TEMPLATE.read_text(encoding="utf-8"))

    def test_first_delta_labels_and_counts_are_unchanged(self):
        body = TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("Run First Spin", body)
        self.assertIn("Run Delta Spin", body)
        self.assertIn("finding(s)", body)
        self.assertIn("{{ selected_spin_run_view.findings|length }}", body)


class SpinTimingDisplayTruthfulnessTests(unittest.TestCase):
    """CLAUDE-SPIN-TIMING-DISPLAY-01.

    The history partial used to append an unconditional "(start time and
    duration are not separately recorded)" note to every run's Completed
    line. That became false once CODEX-NORTH-STAR-PCA-01 began persisting
    started_at/completed_at/duration_ms on SpinRun - the fields already
    reached the template, so the UI was simply asserting their absence
    while rendering a record that contained them.

    These render the real partial rather than asserting on template text,
    so they check what a reader actually sees. run.ran is False in the
    fixtures purely to short-circuit the findings section, which needs a
    populated run_report; the timing line under test renders before that
    branch either way.
    """

    PARTIAL = ROOT / "templates" / "_spin_run_detail.html"
    STALE = "start time and duration are not separately recorded"
    FALLBACK = "(timing not recorded for this earlier run)"

    def _render(self, run):
        import app as app_module

        flask_app = app_module.create_app("testing")
        with flask_app.test_request_context():
            template = flask_app.jinja_env.get_template("_spin_run_detail.html")
            return template.render(run=run, run_report={}, project_id="proj-1")

    def _timed_run(self, **overrides):
        """Timing values from the real live run recorded in PCA-01: 101.1s."""
        run = {
            "id": "run-timed",
            "kind_label": "First Spin",
            "created_at": "2026-08-23T03:24:47+00:00",
            "started_at": "2026-08-23T03:23:06+00:00",
            "completed_at": "2026-08-23T03:24:47+00:00",
            "duration_ms": 101106,
            "ran": False,
            "skipped_reason": "irrelevant to the timing line under test",
        }
        run.update(overrides)
        return run

    def _legacy_run(self):
        """A record written before timing existed.

        The keys are ABSENT, not None - workspace.spin_runs is a raw
        list[dict] with no dataclass rehydration, so this is exactly how a
        legacy record reaches the template.
        """
        return {
            "id": "run-legacy",
            "kind_label": "First Spin",
            "created_at": "2026-01-04T11:00:00+00:00",
            "ran": False,
            "skipped_reason": "irrelevant to the timing line under test",
        }

    def test_timed_run_renders_its_started_timestamp(self):
        body = self._render(self._timed_run())
        self.assertIn("Started:", body)
        self.assertIn('data-spin-timestamp="2026-08-23T03:23:06+00:00"', body)

    def test_timed_run_renders_its_duration_in_seconds(self):
        body = self._render(self._timed_run())
        self.assertIn("Duration:", body)
        self.assertIn("101.1 s", body)

    def test_started_is_localized_by_the_same_mechanism_as_completed(self):
        """Both stamps must be picked up by static/js/spin_timestamps.js."""
        body = self._render(self._timed_run())
        self.assertIn('data-spin-timestamp="2026-08-23T03:24:47+00:00"', body)  # Completed
        self.assertIn('data-spin-timestamp="2026-08-23T03:23:06+00:00"', body)  # Started

    def test_stale_sentence_never_renders_for_a_timed_run(self):
        body = self._render(self._timed_run())
        self.assertNotIn(self.STALE, body)
        self.assertNotIn(self.FALLBACK, body)

    def test_legacy_run_states_the_limitation_is_historical(self):
        """Absence is attributed to the old record, not to the product."""
        body = self._render(self._legacy_run())
        self.assertIn(self.FALLBACK, body)
        self.assertNotIn(self.STALE, body)
        self.assertNotIn("Duration:", body)
        self.assertNotIn("Started:", body)

    def test_a_zero_millisecond_run_is_reported_not_hidden(self):
        """duration_ms may legitimately be 0; a truthiness test would
        misreport that as 'not recorded'."""
        body = self._render(self._timed_run(duration_ms=0))
        self.assertIn("0.0 s", body)
        self.assertNotIn(self.FALLBACK, body)

    def test_a_run_missing_only_started_at_falls_back_rather_than_guessing(self):
        """completed_at must never be used to fabricate a start time."""
        run = self._timed_run()
        del run["started_at"]
        body = self._render(run)
        self.assertIn(self.FALLBACK, body)
        self.assertNotIn("Started:", body)

    def test_completed_line_is_unchanged(self):
        for run in (self._timed_run(), self._legacy_run()):
            with self.subTest(run=run["id"]):
                body = self._render(run)
                self.assertIn("Completed:", body)
                self.assertIn('data-spin-timestamp="%s"' % run["created_at"], body)

    def test_presentation_does_not_mutate_the_run(self):
        """Display is display: rendering must not touch Spin data."""
        run = self._timed_run()
        before = dict(run)
        self._render(run)
        self.assertEqual(run, before)

    def test_stale_sentence_is_gone_from_the_live_partial(self):
        """Scoped to the partial: case_workspace.html keeps a copy inside a
        deliberately dead `{% if false %}` block, retained for the
        compact-history preservation tests and out of scope here."""
        self.assertNotIn(self.STALE, self.PARTIAL.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
