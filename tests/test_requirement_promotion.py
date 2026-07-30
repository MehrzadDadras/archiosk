"""
Requirement Item Promotion Bridge + minimal Requirement route wiring
(ratified governance baseline, governance/specified-unbuilt/
investigation-lifecycle-extensions.md).

Covers CaseWorkspaceStore.promote_requirement_item() directly (the
finalized promotion contract: never infer source_id, preserve
confidence/reasoning-context/trigger/provenance, create the requirement
and its accompanying Finding/AnalysisRun as one atomic governed write,
never touch RequirementAdjudication) and the two minimal Flask routes
that make it and record_requirement_adjudication reachable from the
application layer, exercising the store's own validation rather than
bypassing it.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
    REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
    REQUIREMENT_STATUS_ACTIVE,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog
from services.requirements_registry import RequirementsRegistry


class PromoteRequirementItemTests(unittest.TestCase):
    """Store-layer tests for CaseWorkspaceStore.promote_requirement_item."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_promote_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.project_id = "test-project-promote"
        self.workspace = self.store.get_or_create(self.project_id)
        self.source = self.store.add_source(
            self.workspace, name="RFP.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )
        self.case = self.store.create_case(
            self.workspace, title="Requirement Review", objective="Promote extracted items",
        )
        self.item = {
            "id": "req-item-1",
            "text": "Standby power shall provide no less than 96 hours of operation.",
            "category": "Electrical",
            "confidence": 0.82,
            "source_line": 42,
        }
        self.trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _promote(self, **overrides):
        kwargs = dict(
            case_id=self.case["id"],
            source_id=self.source["id"],
            requirement_item=self.item,
            actor="tester",
            trigger=self.trigger,
            governance_log=self.gov,
        )
        kwargs.update(overrides)
        return self.store.promote_requirement_item(self.workspace, **kwargs)

    # A - successful promotion
    def test_a_successful_promotion(self):
        result = self._promote()
        self.assertIn("requirement", result)
        self.assertIn("finding", result)
        self.assertIn("analysis", result)
        self.assertEqual(result["requirement"]["original_requirement_identifier"], "req-item-1")
        self.assertEqual(result["requirement"]["text_reference"], self.item["text"])
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.requirements), 1)
        self.assertEqual(len(reloaded.findings), 1)
        self.assertEqual(len(reloaded.analyses), 1)

    # B - explicit source_id required, no default, no inference path exists
    def test_b_source_id_cannot_be_omitted(self):
        with self.assertRaises(TypeError):
            self.store.promote_requirement_item(
                self.workspace, case_id=self.case["id"], requirement_item=self.item,
                actor="tester", trigger=self.trigger,
            )

    # C - invalid/nonexistent Source rejected
    def test_c_nonexistent_source_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self._promote(source_id="does-not-exist")

    # D - confidence preserved
    def test_d_confidence_preserved(self):
        result = self._promote()
        self.assertEqual(result["finding"]["machine_confidence"], 0.82)

    # E - reasoning/context preserved (RequirementItem carries no separate
    # free-text rationale of its own - Finding.statement and AnalysisRun.
    # objective are the only "reasoning"-shaped content this bridge has
    # to preserve, and both must survive intact)
    def test_e_reasoning_context_preserved(self):
        result = self._promote()
        self.assertEqual(result["finding"]["statement"], self.item["text"])
        self.assertIn("req-item-1", result["analysis"]["objective"])

    # F - AnalysisTrigger preserved/created correctly
    def test_f_trigger_preserved(self):
        result = self._promote()
        self.assertEqual(result["analysis"]["trigger"]["trigger_type"], ANALYSIS_TRIGGER_USER_INITIATED)
        self.assertEqual(result["analysis"]["trigger"]["triggered_by_actor"], "tester")

    # G - accompanying Finding linkage (Finding <-> AnalysisRun <-> Case)
    def test_g_finding_linked_to_analysis_and_case(self):
        result = self._promote()
        finding_id = result["finding"]["id"]
        analysis_id = result["analysis"]["id"]
        self.assertIn(finding_id, result["analysis"]["finding_ids"])
        self.assertEqual(result["finding"]["analysis_id"], analysis_id)
        reloaded = self.store.get(self.project_id)
        case = self.store._find(reloaded.cases, self.case["id"])
        self.assertIn(finding_id, case["finding_ids"])
        self.assertIn(analysis_id, case["analysis_ids"])

    # H - promoting actor / provenance preserved
    def test_h_actor_and_registration_method_preserved(self):
        result = self._promote(actor="reviewer-x")
        self.assertEqual(result["requirement"]["created_by"], "reviewer-x")
        self.assertEqual(result["requirement"]["registration_method"], REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED)
        self.assertEqual(result["requirement"]["source_id"], self.source["id"])

    # I - no silent authority escalation
    def test_i_no_silent_authority_escalation(self):
        result = self._promote()
        req_id = result["requirement"]["id"]
        self.assertEqual(result["requirement"]["status"], REQUIREMENT_STATUS_ACTIVE)
        self.assertEqual(
            self.store.requirement_adjudication_state(self.workspace, req_id),
            REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
        )

    # J - the promoted Requirement still requires the normal adjudication process
    def test_j_promoted_requirement_still_requires_adjudication(self):
        result = self._promote()
        req_id = result["requirement"]["id"]
        self.assertEqual(self.store.requirement_adjudications_for(self.workspace, req_id), [])
        self.store.record_requirement_adjudication(
            self.workspace, requirement_id=req_id, outcome="Satisfied",
            adjudicator="tester", reasoning="Confirmed against as-built drawings.",
        )
        self.assertEqual(self.store.requirement_adjudication_state(self.workspace, req_id), "Satisfied")

    # K - failure leaves no partially-created governed state
    def test_k_invalid_source_leaves_no_partial_state(self):
        before = self.store.get(self.project_id)
        before_counts = (len(before.requirements), len(before.findings), len(before.analyses))
        with self.assertRaises(CaseWorkspaceError):
            self._promote(source_id="does-not-exist")
        after = self.store.get(self.project_id)
        after_counts = (len(after.requirements), len(after.findings), len(after.analyses))
        self.assertEqual(before_counts, after_counts)

    def test_k2_missing_case_leaves_no_partial_state(self):
        before = self.store.get(self.project_id)
        before_counts = (len(before.requirements), len(before.findings), len(before.analyses))
        with self.assertRaises(CaseWorkspaceError):
            self._promote(case_id="does-not-exist")
        after = self.store.get(self.project_id)
        after_counts = (len(after.requirements), len(after.findings), len(after.analyses))
        self.assertEqual(before_counts, after_counts)

    def test_k3_missing_required_item_field_leaves_no_partial_state(self):
        before = self.store.get(self.project_id)
        before_counts = (len(before.requirements), len(before.findings), len(before.analyses))
        incomplete_item = {"id": "req-item-2", "category": "Electrical"}  # no text/confidence
        with self.assertRaises(CaseWorkspaceError):
            self._promote(requirement_item=incomplete_item)
        after = self.store.get(self.project_id)
        after_counts = (len(after.requirements), len(after.findings), len(after.analyses))
        self.assertEqual(before_counts, after_counts)

    def test_governance_log_event_recorded(self):
        result = self._promote()
        events = [e for e in self.gov.read(self.project_id) if e.event_type == "requirement_item_promoted"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].payload["requirement_id"], result["requirement"]["id"])


class RequirementRouteWiringTests(unittest.TestCase):
    """
    L - route wiring exercises the existing store-layer validation rather
    than bypassing it: hits the real Flask routes (promote + adjudicate)
    through the test client, backed by real CaseWorkspaceStore/
    RequirementsRegistry state, and confirms rejected input is rejected
    by the same rules the store layer already enforces.
    """

    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_promote_routes_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "read_only"

        self.project_id = "test-project-promote-route"
        item = RequirementItem(
            id="req-item-1", text="Egress doors shall be self-closing.",
            category="Life Safety", confidence=0.75, source_line=10,
        )
        document = ParsedDocument(
            project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[item],
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(
            self.project_id,
            register_document_source={
                "filename": "rfp.md", "ingested_at": document.ingested_at,
                "requirement_count": 1, "milestone_count": 0,
            },
        )
        # CLAUDE-P32: single-session fixture -- see
        # tests/test_case_privacy.py's setUp comment for the general
        # reasoning (only an owner needed here, no second session).
        store.set_project_owner(workspace, owner="tester", actor="tester")
        self.source_id = workspace.sources[0]["id"]
        # created_by must match the session these tests actually act as
        # ("tester") - an ownerless private Case is invisible to everyone
        # under the existing Case-visibility model (visible_cases_for),
        # which the route layer now also enforces on the promote route.
        case = store.create_case(workspace, title="Review", objective="Promote items", created_by="tester")
        self.case_id = case["id"]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _promote_url(self, item_id="req-item-1"):
        return f"/projects/{self.project_id}/workspace/cases/{self.case_id}/requirement-items/{item_id}/promote"

    def _adjudicate_url(self, requirement_id):
        return f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate"

    def test_promote_route_requires_source_id(self):
        response = self.client.post(self._promote_url(), data={}, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        workspace = CaseWorkspaceStore(self.tmp_dir).get(self.project_id)
        self.assertEqual(len(workspace.requirements), 0)

    def test_promote_route_creates_governed_requirement(self):
        response = self.client.post(
            self._promote_url(), data={"source_id": self.source_id}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = CaseWorkspaceStore(self.tmp_dir).get(self.project_id)
        self.assertEqual(len(workspace.requirements), 1)
        self.assertEqual(workspace.requirements[0]["original_requirement_identifier"], "req-item-1")
        self.assertEqual(workspace.requirements[0]["registration_method"], REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED)

    def test_promote_route_unknown_item_404s(self):
        response = self.client.post(
            self._promote_url(item_id="does-not-exist"), data={"source_id": self.source_id},
        )
        self.assertEqual(response.status_code, 404)

    def test_adjudicate_route_rejects_invalid_outcome_via_store_validation(self):
        self.client.post(self._promote_url(), data={"source_id": self.source_id})
        store = CaseWorkspaceStore(self.tmp_dir)
        requirement_id = store.get(self.project_id).requirements[0]["id"]

        response = self.client.post(
            self._adjudicate_url(requirement_id),
            data={"outcome": "not-a-real-outcome", "reasoning": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = store.get(self.project_id)
        self.assertEqual(store.requirement_adjudications_for(workspace, requirement_id), [])

    def test_adjudicate_route_records_valid_adjudication(self):
        self.client.post(self._promote_url(), data={"source_id": self.source_id})
        store = CaseWorkspaceStore(self.tmp_dir)
        requirement_id = store.get(self.project_id).requirements[0]["id"]

        response = self.client.post(
            self._adjudicate_url(requirement_id),
            data={"outcome": "Satisfied", "reasoning": "Verified against as-built drawings."},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        workspace = store.get(self.project_id)
        self.assertEqual(store.requirement_adjudication_state(workspace, requirement_id), "Satisfied")


if __name__ == "__main__":
    unittest.main()
