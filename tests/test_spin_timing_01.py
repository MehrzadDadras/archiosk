"""PCA-01: Spin execution timing is durable observational metadata."""

import json
import shutil
import tempfile
import unittest

from services.case_workspace import CaseWorkspaceStore, SPIN_KIND_FIRST


class SpinTimingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("timing-project")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_timing_round_trips_and_is_derived_from_run_boundaries(self):
        run = self.store.record_spin_run(
            self.workspace,
            spin_kind=SPIN_KIND_FIRST,
            actor="tester",
            findings=[],
            source_signature="",
            started_at="2026-08-22T12:00:00+00:00",
        )

        self.assertEqual(run["started_at"], "2026-08-22T12:00:00+00:00")
        self.assertIsNotNone(run["completed_at"])
        self.assertIsInstance(run["duration_ms"], int)
        self.assertGreaterEqual(run["duration_ms"], 0)

        reloaded = self.store.get("timing-project")
        stored = reloaded.spin_runs[0]
        self.assertEqual(stored["started_at"], run["started_at"])
        self.assertEqual(stored["completed_at"], run["completed_at"])
        self.assertEqual(stored["duration_ms"], run["duration_ms"])

    def test_legacy_spin_record_without_timing_remains_readable(self):
        path = self.store.store_path / "timing-project.workspace.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["spin_runs"] = [{
            "id": "legacy-run",
            "project_id": "timing-project",
            "spin_kind": SPIN_KIND_FIRST,
            "created_at": "2026-01-01T00:00:00+00:00",
            "finding_ids": [],
        }]
        path.write_text(json.dumps(payload), encoding="utf-8")

        legacy = self.store.get("timing-project").spin_runs[0]
        self.assertEqual(legacy["id"], "legacy-run")
        self.assertIsNone(legacy.get("started_at"))
        self.assertIsNone(legacy.get("duration_ms"))

    def test_timing_does_not_cross_project_boundaries(self):
        other = self.store.get_or_create("other-project")
        first = self.store.record_spin_run(
            self.workspace, SPIN_KIND_FIRST, "tester", [], "", started_at="2026-08-22T12:00:00+00:00"
        )
        second = self.store.record_spin_run(
            other, SPIN_KIND_FIRST, "tester", [], "", started_at="2026-08-22T13:00:00+00:00"
        )
        self.assertNotEqual(first["project_id"], second["project_id"])
        self.assertEqual(self.store.get("timing-project").spin_runs[0]["started_at"], first["started_at"])
        self.assertEqual(self.store.get("other-project").spin_runs[0]["started_at"], second["started_at"])


if __name__ == "__main__":
    unittest.main()
