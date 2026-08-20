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


if __name__ == "__main__":
    unittest.main()
