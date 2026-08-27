"""
Foundation Batch A (Prompt 7) integrity-backbone tests.

Stdlib unittest only - this project has no pytest dependency (see
requirements.txt / tools/dependency_fit.py's minimal-dependency
conventions). Run via:

    python -m unittest discover -s tests -v

or individually:

    python -m unittest tests.test_foundation_batch_a -v
"""
from __future__ import annotations

import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ConcurrentModificationError,
)
from services.governance import GovernanceLog


def _tiny_png_bytes() -> bytes:
    from PIL import Image

    img = Image.new("RGB", (10, 10), (255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class FoundationBatchATests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-1"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -- state versioning ----------------------------------------------------------

    def test_new_workspace_starts_at_version_zero_and_advances(self):
        # get_or_create() always performs one internal save() even for a
        # brand-new workspace (see its docstring), so version is already 1
        # immediately afterward - 0 is the pre-save in-memory default, not
        # anything ever observable from get_or_create's return value.
        workspace = self.store.get_or_create(self.project_id)
        self.assertEqual(workspace.version, 1)
        case = self.store.create_case(workspace, title="Case A", objective="")
        self.assertEqual(workspace.version, 2)
        self.store.add_message(workspace, case["id"], role="human", actor="tester", text="hello")
        self.assertEqual(workspace.version, 3)

    def test_stale_writer_is_rejected_not_silently_overwritten(self):
        """Mirrors Prompt 7 Test A: two readers load at the same version;
        one commits; the other's later write must be rejected, not
        silently clobber what was already committed."""
        self.store.get_or_create(self.project_id)

        reader_a = self.store.get(self.project_id)
        reader_b = self.store.get(self.project_id)
        self.assertEqual(reader_a.version, reader_b.version)

        self.store.create_case(reader_b, title="B's case", objective="")

        with self.assertRaises(ConcurrentModificationError):
            self.store.create_case(reader_a, title="A's case", objective="")

        current = self.store.get(self.project_id)
        titles = [c["title"] for c in current.cases]
        self.assertIn("B's case", titles)
        self.assertNotIn("A's case", titles)

    def test_sequential_saves_on_same_object_do_not_conflict_with_each_other(self):
        workspace = self.store.get_or_create(self.project_id)
        case = self.store.create_case(workspace, title="Case A", objective="")
        self.store.add_message(workspace, case["id"], role="human", actor="tester", text="one")
        self.store.add_message(workspace, case["id"], role="human", actor="tester", text="two")
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.cases[0]["conversation"]), 2)

    def test_atomic_write_leaves_no_temp_file_behind(self):
        workspace = self.store.get_or_create(self.project_id)
        self.store.create_case(workspace, title="Case A", objective="")
        leftovers = list(self.tmp_dir.glob("*.tmp-*"))
        self.assertEqual(leftovers, [])

    def test_legacy_workspace_without_new_fields_loads_with_honest_defaults(self):
        """Simulates a project JSON saved by pre-Foundation-Batch-A code -
        no version/supersessions keys at all."""
        legacy_path = self.tmp_dir / f"{self.project_id}.workspace.json"
        legacy_path.write_text(json.dumps({"project_id": self.project_id}), encoding="utf-8")
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.version, 0)
        self.assertEqual(workspace.supersessions, [])

    # -- Analysis Trigger provenance -------------------------------------------------

    def test_record_analysis_requires_a_trigger(self):
        workspace = self.store.get_or_create(self.project_id)
        case = self.store.create_case(workspace, title="Case A", objective="")
        with self.assertRaises(TypeError):
            self.store.record_analysis(
                workspace, case_id=case["id"], source_ids=[], objective="x",
                engine_name="e", engine_version="1", findings=[],
            )

    def test_analysis_trigger_rejects_unknown_type(self):
        with self.assertRaises(CaseWorkspaceError):
            AnalysisTrigger(trigger_type="not_a_real_trigger_type")

    def test_analysis_trigger_recorded_on_analysis_run(self):
        workspace = self.store.get_or_create(self.project_id)
        case = self.store.create_case(workspace, title="Case A", objective="")
        trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
            trigger_reference_type="conversation_message",
            trigger_reference_id="msg-1",
            triggered_by_actor="tester",
        )
        analysis = self.store.record_analysis(
            workspace, case_id=case["id"], source_ids=[], objective="analyze x",
            engine_name="mock", engine_version="0.0", findings=[], trigger=trigger,
        )
        self.assertEqual(analysis["trigger"]["trigger_type"], ANALYSIS_TRIGGER_USER_INITIATED)
        self.assertEqual(analysis["trigger"]["trigger_reference_id"], "msg-1")

    # -- shared lineage / Supersession primitive --------------------------------------

    def test_source_revision_creates_supersession_and_pointers_agree(self):
        img_bytes = _tiny_png_bytes()
        drawing_path = self.tmp_dir / "drawing.png"
        drawing_path.write_bytes(img_bytes)

        workspace = self.store.get_or_create(self.project_id)
        source = self.store.add_drawing_source(
            workspace, name="drawing.png", file_path=str(drawing_path), width=10, height=10,
        )
        case = self.store.create_case(workspace, title="Case A", objective="")
        self.store.attach_source_to_case(workspace, case["id"], source["id"])

        rev_path = self.tmp_dir / "drawing_rev2.png"
        rev_path.write_bytes(img_bytes)
        new_source, notices, supersession = self.store.register_source_revision(
            workspace, old_source_id=source["id"], name="drawing_rev2.png",
            file_path=str(rev_path), width=10, height=10, actor="tester", reason="test revision",
        )

        self.assertEqual(supersession["predecessor_id"], source["id"])
        self.assertEqual(supersession["successor_id"], new_source["id"])
        self.assertEqual(supersession["authority_class"], "approval_gate:source_revision")

        old_source_record = self.store._find(workspace.sources, source["id"])
        self.assertEqual(old_source_record["superseded_by_source_id"], new_source["id"])
        self.assertEqual(new_source["supersedes_source_id"], source["id"])

        lineage = self.store.supersessions_for(workspace, "source", source["id"])
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["id"], supersession["id"])

    def test_generic_record_supersession_for_future_object_types(self):
        """Prompt 6/7: the same primitive must already work for object
        types Source doesn't know about (e.g. a future TemporalObligation)
        without any code change to this method."""
        workspace = self.store.get_or_create(self.project_id)
        record = self.store.record_supersession(
            workspace, predecessor_type="temporal_obligation", predecessor_id="obl-1",
            successor_type="temporal_obligation", successor_id="obl-2",
            actor="tester", reason="due date extended", authority_class="approval_gate:reschedule",
        )
        lineage = self.store.supersessions_for(workspace, "temporal_obligation", "obl-1")
        self.assertEqual(len(lineage), 1)
        self.assertEqual(lineage[0]["id"], record["id"])


class GovernanceLogEnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_gov_test_"))
        self.log = GovernanceLog(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_existing_call_shape_still_works_unchanged(self):
        event = self.log.append(
            project_id="p1", event_type="case_created", actor="tester", role="admin",
            payload={"case_id": "c1"},
        )
        self.assertIsNone(event.trigger)
        self.assertIsNone(event.correlation_id)

    def test_new_envelope_fields_round_trip(self):
        self.log.append(
            project_id="p1", event_type="findings_applied", actor="tester", role="admin",
            payload={"finding_ids": ["f1"]},
            state_predecessor_version=4,
            state_successor_version=5,
            authority_class="approval_gate:apply",
            correlation_id="apply-1",
            trigger={"trigger_type": "user_initiated"},
        )
        events = self.log.read("p1")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].state_predecessor_version, 4)
        self.assertEqual(events[0].state_successor_version, 5)
        self.assertEqual(events[0].correlation_id, "apply-1")

    def test_legacy_jsonl_line_without_envelope_fields_still_reads(self):
        legacy_line = json.dumps({
            "id": "e1", "project_id": "p1", "event_type": "case_created",
            "actor": "tester", "role": "admin", "payload": {}, "predecessor_id": None,
            "created_at": "2020-01-01T00:00:00+00:00",
        })
        (self.tmp_dir / "p1.governance.jsonl").write_text(legacy_line + "\n", encoding="utf-8")
        events = self.log.read("p1")
        self.assertEqual(len(events), 1)
        self.assertIsNone(events[0].trigger)
        self.assertIsNone(events[0].state_predecessor_version)


if __name__ == "__main__":
    unittest.main()
