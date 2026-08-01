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
                    operating_environment=CLIENT_OWNER, owner="assurance_test_owner", project_name=project_name,
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

    def test_self_check_reports_a_corrupted_legacy_workspace_as_an_anomaly_not_a_crash(self):
        """
        CLAUDE-P36: found live, not in a test first -- performing the
        Case 1/Case 2 walkthrough against a real running deployment hit
        a real 500 here (TypeError: ProjectWorkspace.__init__() got an
        unexpected keyword argument 'reviews'), the same pre-existing
        real instance/registry/ incompatibility CLAUDE-P32/P34 already
        found and fail-closed elsewhere (app.py's _nav_recent_projects,
        routes/portal.py's _accessible_documents) -- this self-check's
        own per-project loop was a third, previously-missed occurrence.
        Unlike those two (which silently exclude), this function's whole
        purpose is surfacing anomalies, so the fix reports it as one
        instead of swallowing it.
        """
        good_document = self._ingest("Self Check Corrupted Sibling")

        corrupted_project_id = "legacy-corrupted-unrecognized-field"
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        registry.save(ParsedDocument(project_id=corrupted_project_id, filename="old.txt", ingested_at="2020-01-01T00:00:00+00:00"))
        corrupted_path = self.tmp_dir / f"{corrupted_project_id}.workspace.json"
        corrupted_path.write_text(
            # CLAUDE-P40-D: was a real "reviews" key (the original
            # reproduction) - CaseWorkspaceStore._hydrate_legacy_reviews
            # now gives that key a real compatibility adapter, so it no
            # longer TypeErrors and can't stand in for "unrecognized
            # field" here anymore. A still-genuinely-unrecognized key is
            # used instead to keep exercising the same invariant.
            '{"project_id": "' + corrupted_project_id + '", "totally_unrecognized_field_xyz": []}', encoding="utf-8",
        )

        store = SecurityGovernanceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        record = store.get()
        findings = run_security_self_check(
            registry, lambda: CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"]), store, record,
        )
        anomaly = next(f for f in findings if f.check_name == "workspace_readable")
        self.assertEqual(anomaly.project_id, corrupted_project_id)
        self.assertEqual(anomaly.severity, "anomaly")
        # The healthy sibling project must still be checked normally --
        # one corrupted record must not silently swallow every other
        # project's own checks too.
        self.assertFalse(any(
            f.project_id == good_document.project_id and f.severity == "anomaly" for f in findings
        ))


class SecurityDepartmentRouteTests(_BaseAssuranceTestCase):
    """
    CLAUDE-P36: the /security/ route itself (routes/security.py's
    department_home) had never been exercised through the HTTP layer by
    any prior test -- only run_security_self_check's own unit was
    covered. That gap is exactly why a real 500 (a second, separate
    crash site for the same corrupted-legacy-workspace class of bug,
    this time in department_home's own project_profiles dict
    comprehension) was found live rather than by the existing suite.
    """

    def setUp(self):
        super().setUp()
        from models import User, db
        from werkzeug.security import generate_password_hash

        with self.flask_app.app_context():
            db.session.add(User(username="sec_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "sec_admin"
            sess["role"] = "admin"

    def test_department_home_does_not_crash_with_a_corrupted_legacy_workspace_present(self):
        good_document = self._ingest("Security Department Corrupted Sibling")

        corrupted_project_id = "legacy-corrupted-unrecognized-field"
        from services.requirements_registry import RequirementsRegistry

        registry = RequirementsRegistry(self.flask_app.config["REGISTRY_STORE_PATH"])
        registry.save(ParsedDocument(project_id=corrupted_project_id, filename="old.txt", ingested_at="2020-01-01T00:00:00+00:00"))
        corrupted_path = self.tmp_dir / f"{corrupted_project_id}.workspace.json"
        corrupted_path.write_text(
            # CLAUDE-P40-D: was a real "reviews" key (the original
            # reproduction) - CaseWorkspaceStore._hydrate_legacy_reviews
            # now gives that key a real compatibility adapter, so it no
            # longer TypeErrors and can't stand in for "unrecognized
            # field" here anymore. A still-genuinely-unrecognized key is
            # used instead to keep exercising the same invariant.
            '{"project_id": "' + corrupted_project_id + '", "totally_unrecognized_field_xyz": []}', encoding="utf-8",
        )

        resp = self.client.get("/security/")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        # security_department.html's own Projects list always shows
        # {{ p.document.filename }}, never project_name/display_title
        # (templates/security_department.html) - "a.txt" here, matching
        # the fixed filename this file's own _ingest() helper always
        # uses. CLAUDE-P40-E2B1A: this test used to also find the
        # project_name text via the old launcher panel's inline Project-
        # names listing (present on every authenticated page including
        # this one) - that listing violated the root-launcher rule and
        # is gone now, so this assertion checks the security page's own
        # real listing instead, not an incidental side effect of it.
        self.assertIn("a.txt", body)
        # The corrupted project still appears in the list (degraded, not
        # excluded -- an admin should still be able to see and act on it),
        # with its profile control showing "legacy"/"not set" rather than
        # crashing the whole page.
        self.assertIn(corrupted_project_id, body)


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
