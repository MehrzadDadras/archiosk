"""
CLAUDE-P13R - autonomous investigation, begun opportunistically inside
reasoning Archiosk is already legitimately performing (a real
requirement_investigation.py call), never from a free-running scheduler.

Case creation is not authority: an autonomous Case only ever asserts
"there is enough here to investigate" (see CaseOutcome, built earlier,
which remains the only place a hypothesis is confirmed or defeated -
untouched by this file). Bounded by AUTONOMOUS_BRANCH_CONFIDENCE_THRESHOLD
and CaseWorkspaceStore.can_open_autonomous_case_for's two stop conditions
(a project-wide cap, a same-anchor duplicate check) - both checked BEFORE
anything is created, proven here rather than just asserted.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.bhive_parser import ParsedDocument
from services.case_workspace import (
    AUTONOMOUS_INVESTIGATOR_ACTOR,
    CASE_ORIGIN_ANCHOR_ESCALATED,
    CASE_ORIGIN_AUTONOMOUS,
    CASE_ORIGIN_DIRECT,
    MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT,
    OBJECT_KIND_REQUIREMENT,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    CaseWorkspaceStore,
)
from services.requirements_registry import RequirementsRegistry


class CaseOriginKindStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_case_origin_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_direct_case(self):
        case = self.store.create_case(self.workspace, title="X", objective="x", created_by="owner1")
        self.assertEqual(self.store.case_origin_kind(self.workspace, case), CASE_ORIGIN_DIRECT)

    def test_anchor_escalated_case(self):
        case = self.store.create_case(self.workspace, title="X", objective="x", created_by="owner1")
        self.store.add_message(
            self.workspace, case["id"], role="human", text="hi",
            anchor={"anchor_type": "requirement", "anchor_id": "req-1"}, actor="owner1",
        )
        case = next(c for c in self.workspace.cases if c["id"] == case["id"])
        self.assertEqual(self.store.case_origin_kind(self.workspace, case), CASE_ORIGIN_ANCHOR_ESCALATED)

    def test_autonomous_case(self):
        anchor = {"anchor_type": "requirement", "anchor_id": "req-1"}
        case = self.store.create_autonomous_case(self.workspace, title="X", objective="Something odd", anchor=anchor)
        self.assertEqual(self.store.case_origin_kind(self.workspace, case), CASE_ORIGIN_AUTONOMOUS)
        self.assertEqual(case["created_by"], AUTONOMOUS_INVESTIGATOR_ACTOR)
        self.assertEqual(len(case["conversation"]), 1)
        self.assertEqual(case["conversation"][0]["role"], "system")
        self.assertIsNone(case["conversation"][0]["actor"])
        self.assertEqual(case["conversation"][0]["anchor"], anchor)


class AutonomousStopConditionsTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_stop_conditions_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("proj-x")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_can_open_when_nothing_exists(self):
        anchor = {"anchor_type": "requirement", "anchor_id": "req-1"}
        self.assertTrue(self.store.can_open_autonomous_case_for(self.workspace, anchor))

    def test_same_anchor_duplicate_is_blocked(self):
        anchor = {"anchor_type": "requirement", "anchor_id": "req-1"}
        self.store.create_autonomous_case(self.workspace, title="X", objective="x", anchor=anchor)
        self.assertFalse(self.store.can_open_autonomous_case_for(self.workspace, anchor))

    def test_different_anchor_is_not_blocked_by_an_unrelated_one(self):
        anchor_a = {"anchor_type": "requirement", "anchor_id": "req-1"}
        anchor_b = {"anchor_type": "requirement", "anchor_id": "req-2"}
        self.store.create_autonomous_case(self.workspace, title="X", objective="x", anchor=anchor_a)
        self.assertTrue(self.store.can_open_autonomous_case_for(self.workspace, anchor_b))

    def test_global_cap_is_enforced(self):
        for i in range(MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT):
            self.store.create_autonomous_case(
                self.workspace, title=f"X{i}", objective="x",
                anchor={"anchor_type": "requirement", "anchor_id": f"req-{i}"},
            )
        new_anchor = {"anchor_type": "requirement", "anchor_id": "req-new"}
        self.assertFalse(self.store.can_open_autonomous_case_for(self.workspace, new_anchor))

    def test_archived_autonomous_cases_do_not_count_against_the_cap(self):
        for i in range(MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT):
            case = self.store.create_autonomous_case(
                self.workspace, title=f"X{i}", objective="x",
                anchor={"anchor_type": "requirement", "anchor_id": f"req-{i}"},
            )
            self.store.archive_case(self.workspace, case_id=case["id"], actor="owner1", actor_role="admin")
        new_anchor = {"anchor_type": "requirement", "anchor_id": "req-new"}
        self.assertTrue(self.store.can_open_autonomous_case_for(self.workspace, new_anchor))


class OpportunisticBranchingIntegrationTests(unittest.TestCase):
    """Full route stack, real (mocked) model - proves the branch fires
    only when confidence clears the threshold and stop conditions pass."""

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_branching_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-branching"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.", created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def _fake_response(self, **overrides):
        payload = {
            "assessment": "Base answer.", "confidence": 0.7, "supporting_points": [],
            "open_questions": [], "needs_human_judgment": True,
        }
        payload.update(overrides)
        fake_block = MagicMock()
        fake_block.type = "text"
        fake_block.text = json.dumps(payload)
        fake_response = MagicMock()
        fake_response.content = [fake_block]
        return fake_response

    def _ask_via_case(self, requirement):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Something is wrong here", "anchor_type": "requirement",
                "anchor_id": requirement["id"], "anchor_description": "Section 3.1",
            },
        )
        workspace = self.store.get(self.project_id)
        system_message = workspace.project_conversation[-1]
        message_id = system_message["action_taken"].split(":", 1)[1]
        return self.client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")

    def test_high_confidence_branch_opens_a_new_case(self):
        requirement = self._register_requirement()
        response = self._fake_response(
            suggested_branch="The cited fuel-storage bylaw reference appears nowhere else in this project.",
            suggested_branch_confidence=0.9,
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = response
            self._ask_via_case(requirement)

        workspace = self.store.get(self.project_id)
        autonomous_cases = [c for c in workspace.cases if c["created_by"] == AUTONOMOUS_INVESTIGATOR_ACTOR]
        self.assertEqual(len(autonomous_cases), 1)
        self.assertIn("fuel-storage bylaw", autonomous_cases[0]["objective"])

    def test_low_confidence_branch_does_not_open_a_case(self):
        requirement = self._register_requirement()
        response = self._fake_response(
            suggested_branch="Might be worth a look, not sure.", suggested_branch_confidence=0.4,
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = response
            self._ask_via_case(requirement)

        workspace = self.store.get(self.project_id)
        autonomous_cases = [c for c in workspace.cases if c["created_by"] == AUTONOMOUS_INVESTIGATOR_ACTOR]
        self.assertEqual(autonomous_cases, [])

    def test_no_suggested_branch_means_no_case(self):
        requirement = self._register_requirement()
        response = self._fake_response()  # no suggested_branch key at all
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = response
            self._ask_via_case(requirement)

        workspace = self.store.get(self.project_id)
        autonomous_cases = [c for c in workspace.cases if c["created_by"] == AUTONOMOUS_INVESTIGATOR_ACTOR]
        self.assertEqual(autonomous_cases, [])

    def test_governance_log_records_autonomous_origin(self):
        requirement = self._register_requirement()
        response = self._fake_response(
            suggested_branch="A separately-investigable concern.", suggested_branch_confidence=0.95,
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = response
            self._ask_via_case(requirement)

        from services.governance import GovernanceLog
        events = GovernanceLog(self.tmp_dir).read(self.project_id)
        autonomous_events = [
            e for e in events if e.event_type == "case_created" and e.payload.get("origin") == CASE_ORIGIN_AUTONOMOUS
        ]
        self.assertEqual(len(autonomous_events), 1)
        self.assertEqual(autonomous_events[0].actor, AUTONOMOUS_INVESTIGATOR_ACTOR)

    def test_quality_rollup_buckets_autonomous_separately_from_anchor_escalated(self):
        requirement = self._register_requirement()
        response = self._fake_response(
            suggested_branch="A separately-investigable concern.", suggested_branch_confidence=0.95,
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = response
            self._ask_via_case(requirement)

        workspace = self.store.get(self.project_id)
        rollup = self.store.investigation_quality_rollup_for_project(workspace)
        # One anchor-escalated Case (the human-accepted escalation) and one
        # autonomous Case (the opportunistic branch) - never merged together.
        self.assertEqual(sum(rollup["anchored_by_type"]["requirement"].values()), 1)
        self.assertEqual(sum(rollup["autonomous_by_type"]["requirement"].values()), 1)


if __name__ == "__main__":
    unittest.main()
