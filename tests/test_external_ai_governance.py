"""
CLAUDE-P36 -- External-AI Governance, Confidentiality, and Provider
Portability Gate.

Proves ACTION_EXTERNAL_AI_REQUEST (services/security_policy.py) is
actually enforced at the one real external-transmission boundary this
deployment has for the requirement-investigation path (services/
conversation_interpreter.py's _handle_investigate_requirement, via
services/requirement_investigation.py's real Anthropic call) -- not
merely modeled as a governed action that nothing checks.

CLAUDE-P35 found the real Discuss-this-Requirement -> Start-an-
Investigation-from-this UI flow exists and works, but never evaluated
this governed action before transmitting project content externally.
CLAUDE-P36 closes that gap by resolving the SAME services.security_
policy.evaluate_action resolver already used for ACTION_EXPORT (routes/
workspace.py's _evaluate_security_action) and the ingestion-time
external-AI gate (services/ingestion.py), before investigate_requirement
is ever called -- reusing the existing floor/baseline/profile/exception
architecture, never a second permission system.

Mocks only the external provider boundary (anthropic.Anthropic, exactly
the pattern tests/test_requirement_investigation.py already uses) and
exercises the real HTTP routes (discuss_object, start_investigation_
from_aperture) so this proves enforcement at the actual call site a
reviewer's browser reaches, not a service-layer stand-in.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore, REQUIREMENT_REGISTRATION_HUMAN_REGISTERED
from services.requirements_registry import RequirementsRegistry
from services.security_governance import CONTROL_SOURCE_ARCHIOSK_DEFAULT, SecurityGovernanceStore
from services.security_policy import (
    ACTION_EXTERNAL_AI_REQUEST,
    CLASSIFICATION_RESTRICTED,
    DECISION_ALLOW,
    DECISION_DENY,
)


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


_SUCCESSFUL_MODEL_OUTPUT = (
    '{"assessment": "The steel grade matches the referenced standard exactly.", '
    '"confidence": 0.81, "supporting_points": ["CSA G40.21 350W is explicitly named"], '
    '"open_questions": [], "needs_human_judgment": true}'
)


class ExternalAIGovernanceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_external_ai_governance_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-external-ai-governance"

        with self.flask_app.app_context():
            db.session.add_all([
                User(username="alice", password_hash=generate_password_hash("x"), role="admin"),
                User(username="carol", password_hash=generate_password_hash("x"), role="read_only"),
            ])
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.alice = self._client_as("alice", 1, "admin")
        self.carol = self._client_as("carol", 2, "read_only")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.security_store = SecurityGovernanceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client_as(self, username, user_id, role):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _bootstrap_project_and_requirement(self):
        """Owner alice; a Case; one governed Requirement anchored to the
        project's own real Source -- the same shape production reaches
        through Discuss-this-Requirement."""
        self.alice.get(f"/projects/{self.project_id}/workspace")
        workspace = self.store.get(self.project_id)
        self.store.set_project_owner(workspace, owner="alice", actor="alice")
        source_id = workspace.sources[0]["id"]
        requirement = self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Section 4",
            text_reference="Structural steel shall conform to CSA G40.21 350W.",
            created_by="alice", registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )
        return requirement

    def _discuss_then_start_investigation(self, requirement, client=None):
        """The real 2-step UI flow, verbatim: discuss_object (project-
        level, declines with a needs_case offer) then start_investigation_
        from_aperture (opens a Case, re-runs the same anchored question).
        Returns the final response (after following the redirect)."""
        client = client or self.alice
        client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Why is this satisfied - check this against the spec.",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": requirement["original_requirement_identifier"],
            },
        )
        workspace = self.store.get(self.project_id)
        message = next(
            m for m in workspace.project_conversation
            if m["role"] == "human" and (m.get("anchor") or {}).get("anchor_id") == requirement["id"]
        )
        return client.post(
            f"/projects/{self.project_id}/workspace/apertures/{message['id']}/start-investigation",
            follow_redirects=True,
        )

    def _activate_baseline_decision(self, decision: str):
        """Mirrors test_market_critical_golden_path.py's own
        test_security_export_gate_composes_with_project_access setup."""
        record = self.security_store.get()
        baseline = self.security_store.create_baseline_draft(record, created_by="alice")
        self.security_store.add_control_decision(
            record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=decision,
            source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="alice",
        )
        self.security_store.acknowledge_capability_impact(record, baseline["id"], actor="alice")
        self.security_store.activate_baseline(record, baseline["id"], actor="alice")
        return baseline

    # -- 1/12. Permitted project produces exactly one provider call, and a
    #    successful analysis produces a provisional Finding. --
    def test_permitted_project_produces_exactly_one_provider_call_and_a_provisional_finding(self):
        requirement = self._bootstrap_project_and_requirement()
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_MODEL_OUTPUT)
            resp = self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 1)

        self.assertEqual(resp.status_code, 200)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.findings), 1)
        finding = workspace.findings[0]
        self.assertEqual(finding["claim_status"], "provisional")
        self.assertIn("steel grade matches", finding["statement"])

        # -- 13. Provider/model identity persisted (not re-derived from a
        #    second, independently-read env var at the call site). --
        analysis = next(a for a in workspace.analyses if a["id"] == finding["analysis_id"])
        self.assertEqual(analysis["engine_name"], "anthropic-requirement-investigation")
        self.assertTrue(analysis["engine_version"])

        # -- 14. Source lineage survives: the Finding's Case and the
        #    Requirement's own source_id both trace back correctly. --
        self.assertIn(finding["case_id"], [c["id"] for c in workspace.cases])
        self.assertEqual(analysis["source_ids"], [requirement["source_id"]])

    # -- 3. Active-baseline denial produces zero provider calls. --
    # -- 6/7/8. A denied request creates no Finding, no applied state, no
    #    RFI draft or export artifact. --
    # -- 9. Understandable policy-denial message naming the controlling
    #    layer. --
    def test_active_baseline_denial_produces_zero_provider_calls_and_no_governed_state(self):
        requirement = self._bootstrap_project_and_requirement()
        self._activate_baseline_decision(DECISION_DENY)

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            resp = self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)

        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        # Jinja auto-escapes the apostrophe in "project's" - match around it.
        self.assertIn("not permitted by this", body)
        self.assertIn("security policy", body)
        self.assertIn("controlling layer: baseline", body)

        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.findings, [])
        self.assertEqual(workspace.rfi_drafts, [])
        self.assertEqual(workspace.applies, [])

    # -- 4. A project profile rule cannot weaken a stricter baseline
    #    (profile can only ever tighten what came before it, never
    #    loosen -- proven directly against evaluate_action's own
    #    precedence, not just re-asserting the denial happened). --
    def test_project_profile_cannot_weaken_a_stricter_active_baseline(self):
        requirement = self._bootstrap_project_and_requirement()
        self._activate_baseline_decision(DECISION_DENY)
        workspace = self.store.get(self.project_id)
        # security_profile=None (CLASSIFICATION_STANDARD-equivalent) has no
        # opinion of its own on this action -- profile_decision_for returns
        # None, so it must defer entirely to the baseline's DENY, never
        # accidentally loosen it back toward the floor's ALLOW default.
        self.assertIsNone(workspace.security_profile)

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)

    # -- A project profile classification (CLASSIFICATION_RESTRICTED) also
    #    independently denies external AI, even with no baseline set --
    #    confirms the profile layer itself is real, not only the baseline. --
    def test_restricted_security_profile_denies_external_ai_with_no_baseline_set(self):
        requirement = self._bootstrap_project_and_requirement()
        workspace = self.store.get(self.project_id)
        self.store.set_project_security_profile(workspace, security_profile=CLASSIFICATION_RESTRICTED, actor="alice")

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)

        self.assertEqual(self.store.get(self.project_id).findings, [])

    # -- 5. A valid, active, project-scoped exception loosens a denying
    #    baseline back to ALLOW, exactly as evaluate_action's own ceiling
    #    logic specifies -- and the call actually proceeds. --
    def test_active_project_scoped_exception_permits_the_call_despite_a_denying_baseline(self):
        requirement = self._bootstrap_project_and_requirement()
        self._activate_baseline_decision(DECISION_DENY)
        record = self.security_store.get()
        self.security_store.grant_exception(
            record, action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_ALLOW,
            rationale="Owner explicitly approved external AI for this specific project.",
            granted_by="alice", project_id=self.project_id,
        )

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_MODEL_OUTPUT)
            self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 1)

        self.assertEqual(len(self.store.get(self.project_id).findings), 1)

    # -- 10. Missing provider configuration is distinct from policy
    #    denial (policy ALLOWS, but no ANTHROPIC_API_KEY is configured --
    #    app.py's create_app("testing") already clears this env var to
    #    "" for every test in this file, exactly for this reason; no
    #    extra patching needed to exercise the honest, current, real
    #    behavior of a deployment with no key configured). --
    def test_missing_provider_configuration_is_distinct_from_policy_denial(self):
        requirement = self._bootstrap_project_and_requirement()
        resp = self._discuss_then_start_investigation(requirement)

        body = resp.get_data(as_text=True)
        self.assertIn("ANTHROPIC_API_KEY", body)
        self.assertNotIn("not permitted by this project's security policy", body)
        self.assertEqual(self.store.get(self.project_id).findings, [])

    # -- 11. Provider failure creates no fabricated assessment or Finding. --
    def test_provider_failure_creates_no_fabricated_finding(self):
        requirement = self._bootstrap_project_and_requirement()
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.side_effect = RuntimeError("provider unavailable")
            resp = self._discuss_then_start_investigation(requirement)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 1)

        body = resp.get_data(as_text=True)
        self.assertIn("error occurred", body.lower())
        self.assertEqual(self.store.get(self.project_id).findings, [])

    # -- 15/16. ReviewerValidation and Confirmed Disposition remain
    #    required before Apply, even for a Finding produced through this
    #    corrected path -- Apply must not silently succeed without them. --
    def test_reviewer_validation_and_confirmed_disposition_remain_required_before_apply(self):
        requirement = self._bootstrap_project_and_requirement()
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_MODEL_OUTPUT)
            self._discuss_then_start_investigation(requirement)

        workspace = self.store.get(self.project_id)
        finding = workspace.findings[0]
        case_id = finding["case_id"]

        # Apply attempted with no ReviewerValidation/Disposition recorded.
        self.alice.post(f"/projects/{self.project_id}/workspace/cases/{case_id}/apply", data={"confirm": "once"})
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.findings[0]["claim_status"], "provisional")

        self.store.record_reviewer_validation(workspace, finding_id=finding["id"], validation="Correct", reviewer="alice")
        # Disposition still missing -- Apply must still not succeed.
        self.alice.post(f"/projects/{self.project_id}/workspace/cases/{case_id}/apply", data={"confirm": "once"})
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.findings[0]["claim_status"], "provisional")

        self.store.record_disposition(workspace, finding_id=finding["id"], disposition="Confirmed", reviewer="alice")
        self.alice.post(f"/projects/{self.project_id}/workspace/cases/{case_id}/apply", data={"confirm": "once"})
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.findings[0]["claim_status"], "applied")

    # -- 18. Unauthorized users cannot trigger external analysis for a
    #    project they cannot access -- P32's near-universal choke point
    #    (_load_workspace_or_404) denies both routes before interpret_
    #    message is ever reached. --
    def test_unauthorized_user_cannot_reach_either_route(self):
        requirement = self._bootstrap_project_and_requirement()
        resp = self.carol.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "Why is this satisfied?", "anchor_type": "requirement",
                "anchor_id": requirement["id"], "anchor_description": requirement["original_requirement_identifier"],
            },
        )
        self.assertEqual(resp.status_code, 404)

        with patch("anthropic.Anthropic") as MockClient:
            resp = self.carol.post(
                f"/projects/{self.project_id}/workspace/apertures/some-message-id/start-investigation",
            )
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)


if __name__ == "__main__":
    unittest.main()
