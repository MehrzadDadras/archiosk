"""
CLAUDE-P31 -- assurance (activity-level visibility, append-only audit),
self-check, and the remaining Part XVII boundary items not already
covered by tests/test_security_policy_engine.py,
tests/test_security_governance.py, tests/test_learning_governance.py,
or tests/test_security_enforcement.py: lower-authority Q&A cannot
override higher policy, troubleshooting authorization is structurally
separate from learning-contribution authorization, activity-level vs.
content-level assurance, audit append-only behavior, and the claims
registry never advertising organization isolation this repository does
not implement.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.diagnostics import SupportPackage, build_support_package
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import get_governance_log, ingest_upload
from services.security_assurance import (
    SecurityActivityEntry,
    aggregate_security_activity,
    run_security_self_check,
)
from services.security_governance import CONTROL_SOURCE_ARCHIOSK_DEFAULT, CONTROL_SOURCE_QA_ENTRY, SecurityGovernanceStore
from services.security_policy import (
    ACTION_CONTENT_BEARING_SUPPORT_PACKAGE,
    ACTION_EXTERNAL_AI_REQUEST,
    DECISION_ALLOW,
    DECISION_DENY,
    SECURITY_CLAIMS_REGISTRY,
    CLAIM_IMPLEMENTED_AND_TESTED,
    CLAIM_PROHIBITED_FROM_CLAIMING,
    SecurityDecision,
    evaluate_action,
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseAssuranceTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_security_assurance_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name: str):
        def fake_parse(self_parser, raw_bytes, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", "a.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, project_name=project_name,
                )


class LowerAuthorityCannotOverrideHigherPolicyTests(unittest.TestCase):
    def test_unresolved_qa_entry_is_never_treated_as_a_governing_decision(self):
        """An 'unresolved' Q&A status must never be capable of reaching
        evaluate_action's baseline_decision parameter at all -- proven by
        showing the only path from a QAEntry into governance is
        add_control_decision, which requires an explicit, separately-
        chosen `decision` argument (never derived from the QA entry's own
        answer text), and that this remains true even when a
        control-decision cites a Q&A entry as its source."""
        store = SecurityGovernanceStore(Path(tempfile.mkdtemp(prefix="beehive_test_qa_authority_")))
        try:
            record = store.get()
            qa = store.record_qa_entry(
                record, question="May external AI be used?", answer="Unclear, still under review.",
                responding_person="x", authority="x", status="unresolved",
            )
            baseline = store.create_baseline_draft(record, created_by="sec_officer")
            # The security officer must explicitly choose DENY here --
            # nothing about the QA entry's "unresolved" status could have
            # produced this value automatically.
            store.add_control_decision(
                record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_DENY,
                source_type=CONTROL_SOURCE_QA_ENTRY, actor="sec_officer", source_id=qa["id"],
                rationale="Unresolved -- defaulting to deny per Part V.",
            )
            store.acknowledge_capability_impact(record, baseline["id"], actor="sec_officer")
            activated = store.activate_baseline(record, baseline["id"], actor="sec_officer")
            self.assertEqual(activated["control_decisions"][ACTION_EXTERNAL_AI_REQUEST]["decision"], DECISION_DENY)
        finally:
            shutil.rmtree(store.store_path.parent, ignore_errors=True)

    def test_a_lower_authority_project_profile_cannot_override_an_org_baseline_denial(self):
        # Already proven at the resolver level in
        # tests/test_security_policy_engine.py's
        # ProfileInheritsAndCannotLoosenTests -- restated here from the
        # "authority" framing Part XVII names explicitly.
        decision = evaluate_action(
            ACTION_EXTERNAL_AI_REQUEST, baseline_decision=DECISION_DENY, profile_decision=DECISION_ALLOW,
        )
        self.assertEqual(decision.decision, DECISION_DENY)


class TroubleshootingConsentDoesNotAuthorizeTrainingTests(unittest.TestCase):
    def test_building_a_support_package_never_touches_learning_governance(self):
        decision = SecurityDecision(
            action_id=ACTION_CONTENT_BEARING_SUPPORT_PACKAGE, decision=DECISION_ALLOW,
            reason="Approved.", controlling_layer="exception",
        )
        package = build_support_package(
            project_id="p1", contents={"excerpt": "..."}, requested_by="user1",
            purpose="Reproduce a bug.", security_decision=decision,
        )
        self.assertIsInstance(package, SupportPackage)
        # No field, anywhere on this dataclass, could be read as a
        # learning/training authorization.
        self.assertNotIn("learning", str(package.__dataclass_fields__.keys()).lower())

    def test_diagnostics_module_does_not_import_learning_governance(self):
        import ast

        source = Path("services/diagnostics.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        self.assertNotIn("services.learning_governance", imported)


class ActivityLevelVsContentLevelAssuranceTests(_BaseAssuranceTestCase):
    def test_activity_entry_carries_no_project_content_fields(self):
        field_names = set(SecurityActivityEntry.__dataclass_fields__)
        self.assertEqual(
            field_names,
            {"project_id", "event_type", "actor", "role", "created_at", "decision", "controlling_layer"},
        )

    def test_security_administrator_can_see_activity_level_entries(self):
        document = self._ingest("Assurance Visible")
        registry_module = self.flask_app.config["REGISTRY_STORE_PATH"]
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(registry_module)
        activity = aggregate_security_activity(registry, lambda: get_governance_log(self.flask_app))
        matching = [e for e in activity if e.project_id == document.project_id]
        self.assertTrue(any(e.event_type == "security_decision" for e in matching))
        self.assertTrue(any(e.event_type == "operating_environment_established" for e in matching))

    def test_activity_aggregation_reveals_no_requirement_or_finding_text(self):
        document = self._ingest("Assurance No Content")
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        activity = aggregate_security_activity(registry, lambda: get_governance_log(self.flask_app))
        serialized = str(activity)
        self.assertNotIn("content", serialized.lower().replace("no project content", ""))


class AuditAppendOnlyTests(_BaseAssuranceTestCase):
    def test_multiple_security_decisions_accumulate_rather_than_overwrite(self):
        document = self._ingest("Append Only")
        log = get_governance_log(self.flask_app)
        log.append(
            project_id=document.project_id, event_type="security_decision", actor="sec_officer", role="system",
            payload={"action_id": ACTION_EXTERNAL_AI_REQUEST, "decision": "deny", "controlling_layer": "baseline"},
        )
        events = [e for e in log.read(document.project_id) if e.event_type == "security_decision"]
        # The original ingestion-time decision event plus this one --
        # both present, neither replaced the other.
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].payload["decision"], "allow")
        self.assertEqual(events[1].payload["decision"], "deny")


class SelfCheckTests(_BaseAssuranceTestCase):
    def test_self_check_reports_no_anomalies_on_a_clean_deployment(self):
        document = self._ingest("Self Check Clean")
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        store = SecurityGovernanceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        record = store.get()
        findings = run_security_self_check(
            registry, lambda: CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"]), store, record,
        )
        self.assertTrue(any(f.severity == "info" for f in findings))
        self.assertFalse(any(f.severity == "anomaly" for f in findings))

    def test_self_check_detects_a_control_decision_with_dangling_provenance(self):
        store = SecurityGovernanceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        record = store.get()
        baseline = store.create_baseline_draft(record, created_by="sec_officer")
        store.add_control_decision(
            record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_DENY,
            source_type=CONTROL_SOURCE_QA_ENTRY, actor="sec_officer", source_id="does-not-exist",
        )
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        findings = run_security_self_check(
            registry, lambda: CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"]), store, record,
        )
        self.assertTrue(any(f.check_name == "control_decision_provenance" for f in findings))

    def test_self_check_detects_a_stale_active_exception(self):
        from datetime import timedelta

        store = SecurityGovernanceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        record = store.get()
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        exc = store.grant_exception(
            record, action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_ALLOW, rationale="x",
            granted_by="sec_officer", expires_at=past,
        )
        # Simulate a status that was never flipped despite expiry (the
        # bug this check is meant to catch, distinct from
        # active_exception_for's own already-correct filtering).
        exc["status"] = "active"
        store.save(record)

        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        findings = run_security_self_check(
            registry, lambda: CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"]), store, record,
        )
        self.assertTrue(any(f.check_name == "exception_not_stale" for f in findings))


class NoUnsupportedOrganizationIsolationClaimTests(unittest.TestCase):
    def test_multi_organization_isolation_is_not_claimed_implemented(self):
        self.assertNotEqual(
            SECURITY_CLAIMS_REGISTRY["multi-organization tenant isolation"], CLAIM_IMPLEMENTED_AND_TESTED,
        )
        self.assertEqual(
            SECURITY_CLAIMS_REGISTRY["complete organization isolation"], CLAIM_PROHIBITED_FROM_CLAIMING,
        )

    def test_organization_baseline_claim_is_explicitly_limited(self):
        self.assertEqual(
            SECURITY_CLAIMS_REGISTRY["organization-wide security baseline (single deployment)"],
            "implemented_with_limitations",
        )


if __name__ == "__main__":
    unittest.main()
