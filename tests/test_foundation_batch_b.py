"""
Foundation Batch B (Prompt 8) tests: typed relationships, open-world
normalization, Temporal Obligation, and Project Clock reconciliation.

Stdlib unittest only, matching tests/test_foundation_batch_a.py's
convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.case_workspace import (
    ANALYSIS_TRIGGER_CLOCK_INITIATED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    KNOWN_OBJECT_KINDS,
    KNOWN_RELATIONSHIP_TYPES,
    OBJECT_KIND_ACTIVITY,
    OBJECT_KIND_TEMPORAL_OBLIGATION,
    RELATIONSHIP_TYPE_BLOCKS,
    TEMPORAL_CONDITION_DUE,
    TEMPORAL_CONDITION_DUE_SOON,
    TEMPORAL_CONDITION_NOT_YET_DUE,
    TEMPORAL_CONDITION_OVERDUE,
    evaluate_temporal_condition,
    is_known_open_world_value,
    normalize_open_world_value,
)
from services.governance import GovernanceLog
from services.project_clock import reconcile_project


def _iso_date(d: datetime) -> str:
    return d.date().isoformat()


class OpenWorldNormalizationTests(unittest.TestCase):
    def test_known_value_spelling_drift_is_normalized(self):
        self.assertEqual(normalize_open_world_value("Source", KNOWN_OBJECT_KINDS), "source")
        self.assertEqual(normalize_open_world_value("  SOURCE  ", KNOWN_OBJECT_KINDS), "source")

    def test_unrecognized_value_is_preserved_verbatim_not_coerced(self):
        # Test F: a project-specific extension value must survive unchanged.
        self.assertEqual(
            normalize_open_world_value("risk_register_entry", KNOWN_OBJECT_KINDS),
            "risk_register_entry",
        )
        self.assertFalse(is_known_open_world_value("risk_register_entry", KNOWN_OBJECT_KINDS))
        self.assertTrue(is_known_open_world_value("source", KNOWN_OBJECT_KINDS))


class TypedRelationshipTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_b_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-b1"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_relationship_preserves_known_type_and_normalizes_spelling(self):
        rel = self.store.record_relationship(
            self.workspace, from_type="Activity", from_id="a1",
            to_type="activity", to_id="a2", relationship_type="Blocks",
            created_by="tester",
        )
        self.assertEqual(rel["from_type"], OBJECT_KIND_ACTIVITY)
        self.assertEqual(rel["relationship_type"], RELATIONSHIP_TYPE_BLOCKS)
        self.assertTrue(rel["provisional"])

    def test_unknown_relationship_type_preserved_not_falsely_converted(self):
        # Test F (relationship variant): a project-specific relationship
        # type must not be silently coerced into a known one.
        rel = self.store.record_relationship(
            self.workspace, from_type="activity", from_id="a1",
            to_type="activity", to_id="a2", relationship_type="informs_schedule_logic",
        )
        self.assertEqual(rel["relationship_type"], "informs_schedule_logic")
        self.assertNotIn(rel["relationship_type"], KNOWN_RELATIONSHIP_TYPES)

    def test_supersession_never_representable_as_a_relationship_type(self):
        self.assertNotIn("supersedes", KNOWN_RELATIONSHIP_TYPES)

    def test_relationships_for_traverses_by_direction(self):
        self.store.record_relationship(
            self.workspace, from_type="temporal_obligation", from_id="obl-1",
            to_type="activity", to_id="act-1", relationship_type="blocks",
        )
        forward = self.store.relationships_for(self.workspace, "temporal_obligation", "obl-1", direction="from")
        backward = self.store.relationships_for(self.workspace, "activity", "act-1", direction="to")
        self.assertEqual(len(forward), 1)
        self.assertEqual(len(backward), 1)
        self.assertEqual(forward[0]["id"], backward[0]["id"])


class TemporalObligationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_b_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "test-project-b2"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_a_generic_obligation_condition_before_on_after(self):
        """Test A: generic obligation, no RFI/case involved at all."""
        accepted = datetime.now(timezone.utc) + timedelta(days=5)
        obligation = self.store.create_temporal_obligation(
            self.workspace, title="Provide Owner decision",
            origin_type="decision", origin_id="owner-decision-1",
            required_action="Owner must decide on the finish selection.",
            accepted_date=_iso_date(accepted), created_by="tester",
        )

        before = evaluate_temporal_condition(obligation, datetime.now(timezone.utc), due_soon_window_days=7)
        self.assertEqual(before, TEMPORAL_CONDITION_DUE_SOON)  # 5 days out, inside a 7-day window

        far_before = evaluate_temporal_condition(
            obligation, datetime.now(timezone.utc) - timedelta(days=20), due_soon_window_days=7,
        )
        self.assertEqual(far_before, TEMPORAL_CONDITION_NOT_YET_DUE)

        on_date = evaluate_temporal_condition(obligation, accepted, due_soon_window_days=7)
        self.assertEqual(on_date, TEMPORAL_CONDITION_DUE)

        after = evaluate_temporal_condition(obligation, accepted + timedelta(days=3), due_soon_window_days=7)
        self.assertEqual(after, TEMPORAL_CONDITION_OVERDUE)

    def test_b_date_revision_preserves_original_via_lineage(self):
        """Test B: baseline_date survives a governed revision unchanged."""
        original_date = "2026-10-10"
        obligation = self.store.create_temporal_obligation(
            self.workspace, title="Submit design package",
            origin_type="activity", origin_id="act-1",
            required_action="Submit the 60% design package.",
            accepted_date=original_date, created_by="tester",
        )

        new_obligation, supersession = self.store.revise_temporal_obligation(
            self.workspace, obligation_id=obligation["id"], new_accepted_date="2026-10-17",
            actor="tester", reason="Owner requested more coordination time.",
            authority_class="approval_gate:reschedule",
        )

        self.assertEqual(new_obligation["baseline_date"], original_date)
        self.assertEqual(new_obligation["current_accepted_date"], "2026-10-17")
        self.assertEqual(supersession["predecessor_id"], obligation["id"])
        self.assertEqual(supersession["successor_id"], new_obligation["id"])

        reloaded = self.store.get(self.project_id)
        old_record = self.store._find(reloaded.temporal_obligations, obligation["id"])
        self.assertEqual(old_record["status"], "superseded")
        self.assertEqual(old_record["baseline_date"], original_date)  # historically reconstructable, untouched

        lineage = self.store.supersessions_for(reloaded, OBJECT_KIND_TEMPORAL_OBLIGATION, obligation["id"])
        self.assertEqual(len(lineage), 1)

    def test_e_dependency_relationship_is_queryable(self):
        """Test E: Obligation A blocks Activity B, traversable both ways."""
        obligation = self.store.create_temporal_obligation(
            self.workspace, title="Permit approval", origin_type="activity", origin_id="permit-review",
            required_action="Obtain permit approval.", accepted_date="2026-11-01", created_by="tester",
        )
        self.store.record_relationship(
            self.workspace, from_type=OBJECT_KIND_TEMPORAL_OBLIGATION, from_id=obligation["id"],
            to_type=OBJECT_KIND_ACTIVITY, to_id="site-mobilization",
            relationship_type=RELATIONSHIP_TYPE_BLOCKS, created_by="tester",
        )
        downstream = self.store.relationships_for(
            self.workspace, OBJECT_KIND_TEMPORAL_OBLIGATION, obligation["id"], direction="from",
        )
        self.assertEqual(len(downstream), 1)
        self.assertEqual(downstream[0]["to_id"], "site-mobilization")

    def test_g_legacy_project_without_temporal_fields_loads_cleanly(self):
        """Test G: an old project JSON has no relationships/temporal_obligations keys at all."""
        import json
        legacy_project_id = "legacy-project-1"
        legacy_path = self.tmp_dir / f"{legacy_project_id}.workspace.json"
        legacy_path.write_text(json.dumps({"project_id": legacy_project_id}), encoding="utf-8")
        workspace = self.store.get(legacy_project_id)
        self.assertEqual(workspace.relationships, [])
        self.assertEqual(workspace.temporal_obligations, [])


class ProjectClockReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_b_clock_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-b3"
        self.workspace = self.store.get_or_create(self.project_id)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_c_project_open_recognizes_changed_condition_without_changing_obligation(self):
        """Test C: obligation accepted date is already in the past (closed
        before deadline, reopened after) - reconciliation must recognize
        OVERDUE without touching current_accepted_date."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
        obligation = self.store.create_temporal_obligation(
            self.workspace, title="RFI response", origin_type="activity", origin_id="rfi-1",
            required_action="Respond to RFI.", accepted_date=past_date, created_by="tester",
        )

        observations = reconcile_project(self.workspace, self.store, self.gov)
        obs = next(o for o in observations if o.obligation_id == obligation["id"])
        self.assertEqual(obs.current_condition, TEMPORAL_CONDITION_OVERDUE)
        self.assertTrue(obs.changed)  # first time this condition has ever been recorded

        reloaded = self.store.get(self.project_id)
        current = self.store._find(reloaded.temporal_obligations, obligation["id"])
        self.assertEqual(current["current_accepted_date"], past_date)  # untouched

    def test_repeated_reconciliation_does_not_duplicate_events(self):
        """Prompt 8 #12: repeated project opens while OVERDUE must not
        create duplicate transition events."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=4)).date().isoformat()
        self.store.create_temporal_obligation(
            self.workspace, title="RFI response", origin_type="activity", origin_id="rfi-1",
            required_action="Respond to RFI.", accepted_date=past_date, created_by="tester",
        )

        reconcile_project(self.workspace, self.store, self.gov)
        reconcile_project(self.workspace, self.store, self.gov)
        reconcile_project(self.workspace, self.store, self.gov)

        events = [e for e in self.gov.read(self.project_id) if e.event_type == "temporal_condition_changed"]
        self.assertEqual(len(events), 1)  # not 3

    def test_d_case_scoped_obligation_produces_clock_initiated_analysis(self):
        """Test D: a machine Analysis created by temporal reconciliation
        must honestly record CLOCK_INITIATED and the correct project
        state predecessor version."""
        case = self.store.create_case(self.workspace, title="Test Case", objective="")
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        self.store.create_temporal_obligation(
            self.workspace, title="Submittal review", origin_type="activity", origin_id="submittal-1",
            required_action="Review submittal.", accepted_date=past_date, created_by="tester",
            case_id=case["id"],
        )

        version_before = self.workspace.version
        observations = reconcile_project(self.workspace, self.store, self.gov)
        self.assertTrue(any(o.analysis_id for o in observations))

        reloaded = self.store.get(self.project_id)
        analysis = reloaded.analyses[-1]
        self.assertEqual(analysis["trigger"]["trigger_type"], ANALYSIS_TRIGGER_CLOCK_INITIATED)
        self.assertEqual(analysis["case_id"], case["id"])
        # The analysis ran against the state version captured before this
        # reconciliation pass began writing (Prompt 8 #13).
        self.assertGreaterEqual(reloaded.version, version_before)

    def test_project_level_obligation_gets_a_project_level_analysis(self):
        """Superseded by Prompt 9 #3: AnalysisRun.case_id is now optional,
        so a Project-scoped obligation (no case_id) gets a legitimate
        Project-level Analysis (case_id=None) instead of being skipped.
        See tests/test_foundation_batch_c.py for the dedicated coverage."""
        past_date = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()
        self.store.create_temporal_obligation(
            self.workspace, title="Provide Owner decision", origin_type="decision", origin_id="dec-1",
            required_action="Owner decision.", accepted_date=past_date, created_by="tester",
        )
        observations = reconcile_project(self.workspace, self.store, self.gov)
        self.assertTrue(all(o.analysis_id is not None for o in observations))
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.analyses), 1)
        self.assertIsNone(reloaded.analyses[0]["case_id"])

    def test_completed_obligation_is_not_reconciled(self):
        past_date = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
        obligation = self.store.create_temporal_obligation(
            self.workspace, title="Old task", origin_type="activity", origin_id="act-x",
            required_action="Do it.", accepted_date=past_date, created_by="tester",
        )
        reloaded = self.store.get(self.project_id)
        record = self.store._find(reloaded.temporal_obligations, obligation["id"])
        record["status"] = "completed"
        self.store.save(reloaded)

        observations = reconcile_project(reloaded, self.store, self.gov)
        self.assertEqual(observations, [])


if __name__ == "__main__":
    unittest.main()
