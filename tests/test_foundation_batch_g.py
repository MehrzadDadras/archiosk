"""
Foundation Batch G tests: Snapshot / Freeze / State Comparison - the
capability Prompt 14's own adjudication concluded was needed after
manually building an equivalent bundle by hand for the NREOCRC baseline
(see tests/fixtures/nreocrc/baseline_snapshot_001/snapshot_001.json).

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import fields as dataclass_fields
from pathlib import Path

from services.case_workspace import (
    KNOWN_OBJECT_KINDS,
    OBJECT_KIND_SNAPSHOT,
    ProjectWorkspace,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    compare_snapshot_reference_lists,
)
from services.governance import GovernanceLog


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_g_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-g1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_one_of_everything(self):
        source = self.store.add_source(
            self.workspace, name="doc.md", file_path="/tmp/doc.md", kind="owner_project_requirements",
            actor="tester",
        )
        requirement = self.store.register_requirement(
            self.workspace, source_id=source["id"], original_requirement_identifier="12.1",
            text_reference="Test requirement text.", created_by="tester",
            registration_method="manually_registered_test_fixture",
        )
        return source, requirement

    # A - object kind vocabulary carries "snapshot"
    def test_a_object_kind_snapshot_is_known(self):
        self.assertIn(OBJECT_KIND_SNAPSHOT, KNOWN_OBJECT_KINDS)

    # B - basic creation captures the current version and a real id
    def test_b_create_snapshot_basic(self):
        self.store.add_source(self.workspace, name="doc.md", file_path="/tmp/doc.md", kind="owner_project_requirements")
        version_before = self.workspace.version

        snapshot = self.store.create_snapshot(self.workspace, label="Baseline", created_by="tester")

        self.assertTrue(snapshot["id"])
        self.assertEqual(snapshot["project_id"], self.project_id)
        self.assertEqual(snapshot["label"], "Baseline")
        self.assertEqual(snapshot["project_state_version"], version_before)
        self.assertIn("frozen_at", snapshot)
        self.assertEqual(snapshot["created_by"], "tester")

    # C - generic capture: every list on ProjectWorkspace (except project_id/
    # version/snapshots) is represented, and a populated list's ids are
    # captured, without this test needing to know each list's name in advance.
    def test_c_generic_capture_covers_every_governed_list(self):
        source, requirement = self._register_one_of_everything()
        snapshot = self.store.create_snapshot(self.workspace, label="Full state", created_by="tester")

        # Matches _snapshot_reference_lists' own criterion (list-typed
        # fields only) rather than a hardcoded name exclusion, so a future
        # non-list field (e.g. Prompt 3's starred/display_title/
        # operating_instructions) doesn't false-fail this test the way a
        # name-only exclusion would.
        expected_list_names = {
            f.name for f in dataclass_fields(ProjectWorkspace)
            if f.name not in ("project_id", "version", "snapshots")
            and isinstance(getattr(self.workspace, f.name), list)
        }
        self.assertEqual(set(snapshot["reference_lists"].keys()), expected_list_names)
        self.assertEqual(snapshot["reference_lists"]["sources"], [source["id"]])
        self.assertEqual(snapshot["reference_lists"]["requirements"], [requirement["id"]])
        # An empty governed list is still represented, just as an empty list.
        self.assertEqual(snapshot["reference_lists"]["findings"], [])

    # D - a future governed list added to ProjectWorkspace is automatically
    # captured with no change needed to Snapshot/create_snapshot themselves.
    def test_d_capture_is_generic_not_hardcoded(self):
        self.workspace.sources.append({"id": "manually-added", "note": "simulates a future list type"})
        snapshot = self.store.create_snapshot(self.workspace, label="Generic check", created_by="tester")
        self.assertIn("manually-added", snapshot["reference_lists"]["sources"])

    # E - immutability: no update/mutation method exists for Snapshot.
    def test_e_no_update_method_exists(self):
        self.assertFalse(hasattr(self.store, "update_snapshot"))
        self.assertFalse(hasattr(self.store, "revise_snapshot"))

    # F - a Snapshot persists across reload (real flat-JSON persistence, not
    # just an in-memory object).
    def test_f_snapshot_persists_across_reload(self):
        snapshot = self.store.create_snapshot(self.workspace, label="Persisted", created_by="tester")
        reloaded = self.store.get(self.project_id)
        found = self.store.get_snapshot(reloaded, snapshot["id"])
        self.assertIsNotNone(found)
        self.assertEqual(found["label"], "Persisted")

    # G - snapshots_for_project / get_snapshot
    def test_g_snapshots_for_project_and_get_snapshot(self):
        s1 = self.store.create_snapshot(self.workspace, label="One", created_by="tester")
        s2 = self.store.create_snapshot(self.workspace, label="Two", created_by="tester")
        all_snapshots = self.store.snapshots_for_project(self.workspace)
        self.assertEqual({s["id"] for s in all_snapshots}, {s1["id"], s2["id"]})
        self.assertEqual(self.store.get_snapshot(self.workspace, s1["id"])["label"], "One")
        self.assertIsNone(self.store.get_snapshot(self.workspace, "does-not-exist"))

    # H - resolve_snapshot_objects returns the current live records for the
    # ids a Snapshot froze a reference to.
    def test_h_resolve_snapshot_objects(self):
        source, requirement = self._register_one_of_everything()
        snapshot = self.store.create_snapshot(self.workspace, label="Resolve check", created_by="tester")

        resolved_sources = self.store.resolve_snapshot_objects(self.workspace, snapshot["id"], "sources")
        resolved_requirements = self.store.resolve_snapshot_objects(self.workspace, snapshot["id"], "requirements")

        self.assertEqual([s["id"] for s in resolved_sources], [source["id"]])
        self.assertEqual([r["id"] for r in resolved_requirements], [requirement["id"]])

    # I - resolve_snapshot_objects reflects CURRENT content for in-place-
    # mutated fields, not frozen content - the documented, honest limitation
    # of the reference-based (not copy-based) design.
    def test_i_resolved_objects_reflect_current_not_frozen_content(self):
        source, requirement = self._register_one_of_everything()
        snapshot = self.store.create_snapshot(self.workspace, label="Before status change", created_by="tester")

        self.store.set_requirement_status(self.workspace, requirement["id"], "withdrawn", actor="tester")

        resolved = self.store.resolve_snapshot_objects(self.workspace, snapshot["id"], "requirements")
        self.assertEqual(resolved[0]["status"], "withdrawn")

    # J - unknown snapshot id / unknown list name both raise clearly.
    def test_j_resolve_snapshot_objects_errors(self):
        snapshot = self.store.create_snapshot(self.workspace, label="Error check", created_by="tester")
        with self.assertRaises(CaseWorkspaceError):
            self.store.resolve_snapshot_objects(self.workspace, "does-not-exist", "sources")
        with self.assertRaises(CaseWorkspaceError):
            self.store.resolve_snapshot_objects(self.workspace, snapshot["id"], "not_a_real_list")

    # K - compare_snapshots: added ids show up in "added_in_b", nothing in
    # "removed_in_b" since this architecture's lists are append-only.
    def test_k_compare_snapshots_added_ids(self):
        source, _ = self._register_one_of_everything()
        snap_a = self.store.create_snapshot(self.workspace, label="Before", created_by="tester")

        new_requirement = self.store.register_requirement(
            self.workspace, source_id=source["id"], original_requirement_identifier="4.6",
            text_reference="Second requirement.", created_by="tester",
            registration_method="manually_registered_test_fixture",
        )
        snap_b = self.store.create_snapshot(self.workspace, label="After", created_by="tester")

        comparison = self.store.compare_snapshots(self.workspace, snap_a["id"], snap_b["id"])
        self.assertEqual(comparison["requirements"]["added_in_b"], [new_requirement["id"]])
        self.assertEqual(comparison["requirements"]["removed_in_b"], [])
        self.assertEqual(comparison["requirements"]["count_a"], 1)
        self.assertEqual(comparison["requirements"]["count_b"], 2)
        # Unaffected lists show no change.
        self.assertEqual(comparison["sources"]["added_in_b"], [])

    # L - compare_snapshots with unknown ids raises.
    def test_l_compare_snapshots_unknown_id(self):
        snap = self.store.create_snapshot(self.workspace, label="Solo", created_by="tester")
        with self.assertRaises(CaseWorkspaceError):
            self.store.compare_snapshots(self.workspace, snap["id"], "does-not-exist")

    # M - the pure compare_snapshot_reference_lists function works directly
    # on plain dicts (no store/workspace needed) - testable in isolation.
    def test_m_pure_comparison_function(self):
        snapshot_a = {"reference_lists": {"sources": ["s1"], "requirements": ["r1"]}}
        snapshot_b = {"reference_lists": {"sources": ["s1", "s2"], "requirements": []}}
        result = compare_snapshot_reference_lists(snapshot_a, snapshot_b)
        self.assertEqual(result["sources"]["added_in_b"], ["s2"])
        self.assertEqual(result["requirements"]["removed_in_b"], ["r1"])

    # N - governance_log receives a snapshot_created event when supplied.
    def test_n_governance_log_event(self):
        snapshot = self.store.create_snapshot(
            self.workspace, label="Governed", created_by="tester", governance_log=self.gov,
        )
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "snapshot_created"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].correlation_id, snapshot["id"])

    # O - note is optional and honestly absent when not supplied.
    def test_o_note_optional(self):
        snapshot = self.store.create_snapshot(self.workspace, label="No note", created_by="tester")
        self.assertIsNone(snapshot["note"])
        snapshot_with_note = self.store.create_snapshot(
            self.workspace, label="With note", created_by="tester", note="Pre-Batch-F re-ingestion baseline.",
        )
        self.assertEqual(snapshot_with_note["note"], "Pre-Batch-F re-ingestion baseline.")

    # P - a legacy workspace saved before Batch G (no "snapshots" key at all
    # in its JSON) loads cleanly with an empty list, same pattern as every
    # prior batch's own legacy-compatibility guarantee.
    def test_p_legacy_workspace_without_snapshots_key_loads(self):
        import json
        legacy_project_id = "legacy-project-g"
        legacy_data = {"project_id": legacy_project_id, "version": 3, "sources": []}
        path = self.tmp_dir / f"{legacy_project_id}.workspace.json"
        path.write_text(json.dumps(legacy_data), encoding="utf-8")

        loaded = self.store.get(legacy_project_id)
        self.assertEqual(loaded.snapshots, [])
        snapshot = self.store.create_snapshot(loaded, label="First real snapshot", created_by="tester")
        self.assertEqual(snapshot["project_state_version"], 3)


if __name__ == "__main__":
    unittest.main()
