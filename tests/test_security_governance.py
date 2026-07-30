"""
CLAUDE-P31 -- services.security_governance.SecurityGovernanceStore
lifecycle tests: source policy vs. Q&A distinction, Q&A authority/scope
recording, control-decision provenance, draft-vs-active baseline
governance, capability-impact acknowledgement gating activation,
baseline supersession, and exception expiry.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.security_governance import (
    BASELINE_STATUS_ACTIVE,
    BASELINE_STATUS_DRAFT,
    BASELINE_STATUS_SUPERSEDED,
    BASELINE_STATUS_UNDER_REVIEW,
    CONTROL_SOURCE_ARCHIOSK_DEFAULT,
    CONTROL_SOURCE_POLICY_STATEMENT,
    CONTROL_SOURCE_QA_ENTRY,
    QA_STATUS_AUTHORIZED_ANSWER,
    QA_STATUS_PROVISIONAL_PENDING_APPROVAL,
    QA_STATUS_UNRESOLVED,
    SecurityGovernanceError,
    SecurityGovernanceStore,
)
from services.security_policy import ACTION_EXPORT, ACTION_EXTERNAL_AI_REQUEST, DECISION_ALLOW, DECISION_DENY


class _BaseSecurityGovernanceTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_security_governance_"))
        self.store = SecurityGovernanceStore(self.tmp_dir)
        self.record = self.store.get()

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)


class SourcePolicyVsQATests(_BaseSecurityGovernanceTestCase):
    def test_source_policy_and_qa_entry_are_structurally_distinct_records(self):
        policy = self.store.record_source_policy(
            self.record, title="IT Security Policy", issuing_organization="City of Example",
            ingested_by="sec_officer",
        )
        qa = self.store.record_qa_entry(
            self.record, question="Is external AI permitted?", answer="No.",
            responding_person="CISO", authority="Chief Information Security Officer",
        )
        self.assertIn(policy["id"], {p["id"] for p in self.record.source_policies})
        self.assertNotIn(policy["id"], {q["id"] for q in self.record.qa_entries})
        self.assertIn(qa["id"], {q["id"] for q in self.record.qa_entries})
        self.assertNotIn(qa["id"], {p["id"] for p in self.record.source_policies})

    def test_qa_entry_records_authority_and_scope(self):
        qa = self.store.record_qa_entry(
            self.record, question="May prompts be retained?", answer="No, ephemeral only.",
            responding_person="Jane Officer", authority="Security Officer", scope="all_projects",
        )
        self.assertEqual(qa["authority"], "Security Officer")
        self.assertEqual(qa["scope"], "all_projects")
        self.assertEqual(qa["responding_person"], "Jane Officer")

    def test_qa_entry_status_defaults_unresolved(self):
        qa = self.store.record_qa_entry(
            self.record, question="Unanswered question", answer="", responding_person="x", authority="x",
        )
        self.assertEqual(qa["status"], QA_STATUS_UNRESOLVED)

    def test_provisional_qa_entry_can_be_approved(self):
        qa = self.store.record_qa_entry(
            self.record, question="q", answer="a", responding_person="x", authority="x",
            status=QA_STATUS_PROVISIONAL_PENDING_APPROVAL,
        )
        approved = self.store.approve_qa_entry(self.record, qa["id"], approved_by="sec_admin")
        self.assertEqual(approved["status"], QA_STATUS_AUTHORIZED_ANSWER)
        self.assertEqual(approved["approved_by"], "sec_admin")
        self.assertIsNotNone(approved["approved_at"])


class ControlProvenanceTests(_BaseSecurityGovernanceTestCase):
    def test_policy_statement_sourced_control_requires_source_id(self):
        with self.assertRaises(SecurityGovernanceError):
            self.store.propose_control(
                self.record, action_id=ACTION_EXTERNAL_AI_REQUEST, proposed_decision=DECISION_DENY,
                rationale="x", proposed_by="sec_officer", source_type=CONTROL_SOURCE_POLICY_STATEMENT,
                source_id=None,
            )

    def test_archiosk_default_sourced_control_does_not_require_source_id(self):
        control = self.store.propose_control(
            self.record, action_id=ACTION_EXTERNAL_AI_REQUEST, proposed_decision=DECISION_DENY,
            rationale="Recommended default.", proposed_by="archiosk", source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT,
        )
        self.assertEqual(control["source_type"], CONTROL_SOURCE_ARCHIOSK_DEFAULT)
        self.assertIsNone(control["source_id"])

    def test_control_proposal_preserves_provenance_back_to_policy_statement(self):
        policy = self.store.record_source_policy(
            self.record, title="Policy", issuing_organization="Org", ingested_by="sec_officer",
        )
        statement = self.store.record_policy_statement(
            self.record, source_policy_id=policy["id"], clause_text="Restricted info stays internal.",
            extracted_by="sec_officer",
        )
        control = self.store.propose_control(
            self.record, action_id=ACTION_EXTERNAL_AI_REQUEST, proposed_decision=DECISION_DENY,
            rationale="Clause 3", proposed_by="sec_officer", source_type=CONTROL_SOURCE_POLICY_STATEMENT,
            source_id=statement["id"],
        )
        self.assertEqual(control["source_id"], statement["id"])
        self.assertEqual(control["source_type"], CONTROL_SOURCE_POLICY_STATEMENT)

    def test_baseline_control_decision_from_qa_entry_preserves_provenance(self):
        qa = self.store.record_qa_entry(
            self.record, question="q", answer="a", responding_person="x", authority="x",
        )
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        updated = self.store.add_control_decision(
            self.record, baseline_id=baseline["id"], action_id=ACTION_EXPORT, decision=DECISION_DENY,
            source_type=CONTROL_SOURCE_QA_ENTRY, actor="sec_officer", source_id=qa["id"],
        )
        self.assertEqual(updated["control_decisions"][ACTION_EXPORT]["source_id"], qa["id"])
        self.assertEqual(updated["control_decisions"][ACTION_EXPORT]["source_type"], CONTROL_SOURCE_QA_ENTRY)


class BaselineRatificationLifecycleTests(_BaseSecurityGovernanceTestCase):
    def test_new_baseline_starts_draft(self):
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.assertEqual(baseline["status"], BASELINE_STATUS_DRAFT)

    def test_draft_baseline_does_not_govern_active_actions(self):
        # active_baseline() is what evaluate_action's callers actually
        # consult -- a draft (even with control decisions already added)
        # must not be returned by it.
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.add_control_decision(
            self.record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_DENY,
            source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="sec_officer",
        )
        self.assertIsNone(self.store.active_baseline(self.record))

    def test_activation_requires_capability_impact_acknowledgement_first(self):
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        with self.assertRaises(SecurityGovernanceError):
            self.store.activate_baseline(self.record, baseline["id"], actor="sec_officer")

    def test_acknowledging_impact_moves_draft_to_under_review(self):
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        updated = self.store.acknowledge_capability_impact(self.record, baseline["id"], actor="sec_officer")
        self.assertEqual(updated["status"], BASELINE_STATUS_UNDER_REVIEW)
        self.assertEqual(updated["capability_impact_acknowledged_by"], "sec_officer")

    def test_approved_baseline_can_be_activated(self):
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.acknowledge_capability_impact(self.record, baseline["id"], actor="sec_officer")
        activated = self.store.activate_baseline(self.record, baseline["id"], actor="sec_officer")
        self.assertEqual(activated["status"], BASELINE_STATUS_ACTIVE)
        self.assertIsNotNone(activated["activated_at"])
        self.assertIsNotNone(activated["effective_date"])

    def test_activating_a_new_baseline_supersedes_the_previous_active_one(self):
        first = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.acknowledge_capability_impact(self.record, first["id"], actor="sec_officer")
        self.store.activate_baseline(self.record, first["id"], actor="sec_officer")

        second = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.acknowledge_capability_impact(self.record, second["id"], actor="sec_officer")
        self.store.activate_baseline(self.record, second["id"], actor="sec_officer")

        reloaded_first = next(b for b in self.record.baselines if b["id"] == first["id"])
        self.assertEqual(reloaded_first["status"], BASELINE_STATUS_SUPERSEDED)
        self.assertIsNotNone(reloaded_first["superseded_at"])
        self.assertEqual(self.store.active_baseline(self.record)["id"], second["id"])

    def test_baseline_history_preserved_not_deleted(self):
        first = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.acknowledge_capability_impact(self.record, first["id"], actor="sec_officer")
        self.store.activate_baseline(self.record, first["id"], actor="sec_officer")
        self.assertEqual(len(self.record.baselines), 1)
        self.assertEqual(self.record.baselines[0]["id"], first["id"])

    def test_cannot_add_control_decision_to_an_already_active_baseline(self):
        baseline = self.store.create_baseline_draft(self.record, created_by="sec_officer")
        self.store.acknowledge_capability_impact(self.record, baseline["id"], actor="sec_officer")
        self.store.activate_baseline(self.record, baseline["id"], actor="sec_officer")
        with self.assertRaises(SecurityGovernanceError):
            self.store.add_control_decision(
                self.record, baseline_id=baseline["id"], action_id=ACTION_EXPORT, decision=DECISION_DENY,
                source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="sec_officer",
            )


class ExceptionExpiryTests(_BaseSecurityGovernanceTestCase):
    def test_active_non_expired_exception_is_returned(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        self.store.grant_exception(
            self.record, action_id=ACTION_EXPORT, decision=DECISION_ALLOW, rationale="x",
            granted_by="sec_officer", expires_at=future,
        )
        found = self.store.active_exception_for(self.record, ACTION_EXPORT)
        self.assertIsNotNone(found)

    def test_expired_exception_is_not_returned(self):
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        self.store.grant_exception(
            self.record, action_id=ACTION_EXPORT, decision=DECISION_ALLOW, rationale="x",
            granted_by="sec_officer", expires_at=past,
        )
        found = self.store.active_exception_for(self.record, ACTION_EXPORT)
        self.assertIsNone(found)

    def test_revoked_exception_is_not_returned_even_if_unexpired(self):
        future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        exc = self.store.grant_exception(
            self.record, action_id=ACTION_EXPORT, decision=DECISION_ALLOW, rationale="x",
            granted_by="sec_officer", expires_at=future,
        )
        self.store.revoke_exception(self.record, exc["id"])
        self.assertIsNone(self.store.active_exception_for(self.record, ACTION_EXPORT))

    def test_project_scoped_exception_takes_precedence_over_org_wide_for_that_project(self):
        self.store.grant_exception(
            self.record, action_id=ACTION_EXPORT, decision=DECISION_ALLOW, rationale="org-wide",
            granted_by="sec_officer", project_id=None,
        )
        self.store.grant_exception(
            self.record, action_id=ACTION_EXPORT, decision=DECISION_ALLOW, rationale="project-specific",
            granted_by="sec_officer", project_id="proj-1",
        )
        found = self.store.active_exception_for(self.record, ACTION_EXPORT, project_id="proj-1")
        self.assertEqual(found["rationale"], "project-specific")


if __name__ == "__main__":
    unittest.main()
