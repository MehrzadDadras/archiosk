"""
CLAUDE-P11 - hypothesis survival and investigation quality: CaseOutcome
is the one place a Case's own hypothesis is ever declared confirmed,
defeated, duplicate, or irrelevant - always a human act, never machine-
populated. investigation_quality_rollup_for_project is the system-health
signal: is Archiosk generating useful investigative hypotheses, counted
only from Cases opened by escalating a machine-recognized question
(case_origin_anchor), never from a Case a human opened outright.

A dedicated test class (ArchitecturalBoundaryTests) asserts, by source
inspection, that nothing in the reasoning/interpretation code path reads
CaseOutcome or the rollup back - "BEEHIVE may learn how to investigate
without learning what to believe" is a property of what ISN'T wired
here, and that property is worth guarding explicitly, not just by
convention.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
import pytest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import (
    CASE_OUTCOME_CONFIRMED,
    CASE_OUTCOME_DEFEATED,
    CASE_OUTCOME_DUPLICATE,
    CASE_OUTCOME_IRRELEVANT,
    CASE_OUTCOME_STATE_UNRESOLVED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry


class CaseOutcomeStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_outcome_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")
        self.case = self.store.create_case(self.workspace, title="Investigate X", objective="", created_by="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_a_fresh_case_is_unresolved(self):
        self.assertEqual(self.store.case_outcome_state(self.workspace, self.case["id"]), CASE_OUTCOME_STATE_UNRESOLVED)
        self.assertIsNone(self.store.latest_case_outcome_for(self.workspace, self.case["id"]))

    def test_recording_a_confirmed_outcome(self):
        self.store.record_case_outcome(
            self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_CONFIRMED,
            reasoning="Evidence held up under review.", recorded_by="owner1",
        )
        self.assertEqual(self.store.case_outcome_state(self.workspace, self.case["id"]), CASE_OUTCOME_CONFIRMED)

    def test_outcome_requires_reasoning(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_case_outcome(
                self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_CONFIRMED,
                reasoning="   ", recorded_by="owner1",
            )

    def test_unrecognized_outcome_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_case_outcome(
                self.workspace, case_id=self.case["id"], outcome="probably-fine",
                reasoning="x", recorded_by="owner1",
            )

    def test_duplicate_requires_a_target_case(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_case_outcome(
                self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_DUPLICATE,
                reasoning="Same question as another Case.", recorded_by="owner1",
            )

    def test_duplicate_target_must_exist(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_case_outcome(
                self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_DUPLICATE,
                reasoning="Same question.", recorded_by="owner1", duplicate_of_case_id="nonexistent",
            )

    def test_duplicate_with_a_real_target_succeeds(self):
        other = self.store.create_case(self.workspace, title="Investigate Y", objective="", created_by="owner1")
        record = self.store.record_case_outcome(
            self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_DUPLICATE,
            reasoning="Same underlying question as the other Case.", recorded_by="owner1",
            duplicate_of_case_id=other["id"],
        )
        self.assertEqual(record["duplicate_of_case_id"], other["id"])

    def test_later_outcome_supersedes_in_effect_but_both_remain_on_record(self):
        self.store.record_case_outcome(
            self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_DEFEATED,
            reasoning="Initially looked contradicted.", recorded_by="owner1",
        )
        self.store.record_case_outcome(
            self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_CONFIRMED,
            reasoning="Reopened - new evidence confirmed it after all.", recorded_by="owner1",
        )
        self.assertEqual(self.store.case_outcome_state(self.workspace, self.case["id"]), CASE_OUTCOME_CONFIRMED)
        self.assertEqual(len(self.store.case_outcomes_for(self.workspace, self.case["id"])), 2)

    def test_irrelevant_outcome_recorded(self):
        self.store.record_case_outcome(
            self.workspace, case_id=self.case["id"], outcome=CASE_OUTCOME_IRRELEVANT,
            reasoning="This never should have been flagged as worth investigating.", recorded_by="owner1",
        )
        self.assertEqual(self.store.case_outcome_state(self.workspace, self.case["id"]), CASE_OUTCOME_IRRELEVANT)


class InvestigationQualityRollupTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_quality_rollup_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _anchored_case(self, outcome=None):
        case = self.store.create_case(self.workspace, title="Anchored", objective="", created_by="owner1")
        self.store.add_message(
            self.workspace, case["id"], role="human", text="Something is wrong here",
            anchor={"anchor_type": "requirement", "anchor_id": "req-1"}, actor="owner1",
        )
        if outcome:
            self.store.record_case_outcome(
                self.workspace, case_id=case["id"], outcome=outcome, reasoning="x", recorded_by="owner1",
            )
        return case

    def _unanchored_case(self, outcome=None):
        case = self.store.create_case(self.workspace, title="Plain", objective="", created_by="owner1")
        self.store.add_message(self.workspace, case["id"], role="human", text="hello", actor="owner1")
        if outcome:
            self.store.record_case_outcome(
                self.workspace, case_id=case["id"], outcome=outcome, reasoning="x", recorded_by="owner1",
            )
        return case

    def test_case_with_no_conversation_at_all_has_no_origin_anchor(self):
        case = self.store.create_case(self.workspace, title="Empty", objective="", created_by="owner1")
        self.assertIsNone(self.store.case_origin_anchor(self.workspace, case))

    def test_anchored_and_unanchored_cases_are_bucketed_separately(self):
        self._anchored_case(outcome=CASE_OUTCOME_CONFIRMED)
        self._anchored_case(outcome=CASE_OUTCOME_DEFEATED)
        self._unanchored_case()  # unresolved, and must not count toward the anchored bucket

        rollup = self.store.investigation_quality_rollup_for_project(self.workspace)
        self.assertEqual(rollup["anchored_by_type"]["requirement"][CASE_OUTCOME_CONFIRMED], 1)
        self.assertEqual(rollup["anchored_by_type"]["requirement"][CASE_OUTCOME_DEFEATED], 1)
        self.assertEqual(rollup["unanchored"][CASE_OUTCOME_STATE_UNRESOLVED], 1)
        # The unanchored Case must not leak into the anchored bucket's count.
        self.assertEqual(sum(rollup["anchored_by_type"]["requirement"].values()), 2)

    def test_unresolved_anchored_cases_are_counted_honestly_not_hidden(self):
        self._anchored_case()  # no outcome recorded
        rollup = self.store.investigation_quality_rollup_for_project(self.workspace)
        self.assertEqual(rollup["anchored_by_type"]["requirement"][CASE_OUTCOME_STATE_UNRESOLVED], 1)

    def test_empty_project_has_empty_rollup(self):
        rollup = self.store.investigation_quality_rollup_for_project(self.workspace)
        self.assertEqual(rollup, {"anchored_by_type": {}, "autonomous_by_type": {}, "unanchored": {}})


class ArchitecturalBoundaryTests(unittest.TestCase):
    """
    Guards "BEEHIVE may learn how to investigate without learning what to
    believe": the reasoning/interpretation code path must never read
    CaseOutcome or the quality rollup back - this is a property of what
    ISN'T wired, checked here by source inspection so a future change
    can't silently cross that line without a test noticing.
    """

    def test_requirement_investigation_service_never_references_case_outcome(self):
        import services.requirement_investigation as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CaseOutcome", source)
        self.assertNotIn("case_outcome", source)
        self.assertNotIn("investigation_quality", source)

    def test_conversation_interpreter_never_references_case_outcome(self):
        import services.conversation_interpreter as module
        source = Path(module.__file__).read_text(encoding="utf-8")
        self.assertNotIn("CaseOutcome", source)
        self.assertNotIn("case_outcome", source)
        self.assertNotIn("investigation_quality", source)


class CaseOutcomeRouteAndRenderTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_outcome_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-case-outcome"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    @pytest.mark.legacy_route_diagnostic
    def test_recording_an_outcome_through_the_route_and_seeing_the_badge(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Investigate Z", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]

        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/outcome",
            data={"outcome": CASE_OUTCOME_DEFEATED, "reasoning": "Evidence contradicted the hypothesis."},
        )
        self.assertEqual(resp.status_code, 302)

        page = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = page.get_data(as_text=True)
        self.assertIn(CASE_OUTCOME_DEFEATED, body)

    @pytest.mark.legacy_route_diagnostic
    def test_invalid_outcome_flashes_an_error_and_records_nothing(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Investigate Z", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]

        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/outcome",
            data={"outcome": "not-a-real-outcome", "reasoning": "x"},
        )
        self.assertEqual(self.store.case_outcomes_for(self.store.get(self.project_id), case["id"]), [])

    def test_investigation_quality_accordion_renders_the_rollup(self):
        requirement = self.store.register_requirement(
            self.store.get(self.project_id),
            source_id=self.store.get(self.project_id).sources[0]["id"],
            original_requirement_identifier="Section 1",
            text_reference="Some clause.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Check this",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 1",
            },
        )
        workspace = self.store.get(self.project_id)
        system_message = workspace.project_conversation[1]
        message_id = system_message["action_taken"].split(":", 1)[1]
        resp = self.client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")
        case_id = resp.headers["Location"].rsplit("case=", 1)[1]

        self.store.record_case_outcome(
            self.store.get(self.project_id), case_id=case_id,
            outcome=CASE_OUTCOME_IRRELEVANT,
            reasoning="Never should have flagged this.", recorded_by="owner1",
        )

        page = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = page.get_data(as_text=True)
        self.assertIn("Investigation Quality", body)
        self.assertIn("requirement-anchored, human-accepted (1)", body)
        self.assertIn(CASE_OUTCOME_IRRELEVANT, body)


if __name__ == "__main__":
    unittest.main()
