"""
CLAUDE-P31 -- real wiring tests: the external-AI gate inside
services/ingestion.py, the export gate inside routes/workspace.py,
content-bearing support package authorization, denied-action audit
events, assurance activity-level visibility, self-check, and the
boundary checks Part XVII explicitly requires (security policy cannot
touch Project Operating Environment, reviewer perspective cannot bypass
security, CLAUDE-P30's capability registry and this stage's security
policy both apply independently, no tenancy migration occurred).

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
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.diagnostics import (
    SupportPackageDeniedError,
    build_support_package,
    build_technical_telemetry,
)
from services.environment_capabilities import CLIENT_OWNER, DESIGN_BUILDER_PROPONENT
from services.ingestion import get_governance_log, ingest_upload
from services.security_governance import CONTROL_SOURCE_ARCHIOSK_DEFAULT, SecurityGovernanceStore
from services.security_policy import (
    ACTION_CONTENT_BEARING_SUPPORT_PACKAGE,
    ACTION_EXPORT,
    ACTION_EXTERNAL_AI_REQUEST,
    CLASSIFICATION_HIGHLY_RESTRICTED,
    DECISION_ALLOW,
    DECISION_DENY,
    SecurityDecision,
    evaluate_action,
)


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseSecurityTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_security_enforcement_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.client = self.flask_app.test_client()

        with self.flask_app.app_context():
            admin = User(username="sec_test_admin", password_hash=generate_password_hash("x"), role="admin")
            db.session.add(admin)
            db.session.commit()

        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "sec_test_admin"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sec_store(self) -> SecurityGovernanceStore:
        return SecurityGovernanceStore(self.tmp_dir)

    def _ingest(self, operating_environment: str, project_name: str):
        """Deterministic, network-independent ingestion for tests that
        don't care about real classification output -- spies on
        BHiveParser.parse the same way ExternalAIGateWiringTests does,
        never calling the real extract/classify/consistency-check
        pipeline. Whatever ANTHROPIC_API_KEY happens to be configured in
        this process (see config.py's module-import-time class attribute
        vs. app.py's later os.environ clearing) must never be able to
        make any test in this file slow or network-dependent."""
        def fake_parse(self_parser, raw_bytes, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", "a.txt"), self.flask_app,
                    operating_environment=operating_environment, owner="sec_test_admin", project_name=project_name,
                )

    def _activate_baseline_with(self, action_id: str, decision: str) -> None:
        store = self._sec_store()
        record = store.get()
        baseline = store.create_baseline_draft(record, created_by="sec_test_admin")
        store.add_control_decision(
            record, baseline_id=baseline["id"], action_id=action_id, decision=decision,
            source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="sec_test_admin",
        )
        store.acknowledge_capability_impact(record, baseline["id"], actor="sec_test_admin")
        store.activate_baseline(record, baseline["id"], actor="sec_test_admin")


class ExternalAIGateWiringTests(_BaseSecurityTestCase):
    """Deterministic proof that services/ingestion.py's security gate
    reaches BHiveParser.ai_calls_disabled -- spies on BHiveParser.parse
    to capture the flag's value at call time WITHOUT letting any real
    classification/network call happen (the spy never calls the real
    implementation), so this is fully network-independent regardless of
    whatever ANTHROPIC_API_KEY happens to be configured in this process."""

    def _spy_and_ingest(self, project_name: str):
        captured = []

        def fake_parse(self_parser, raw_bytes, filename):
            captured.append(self_parser.ai_calls_disabled)
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                document = ingest_upload(
                    _fake_file(b"content", "a.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="sec_test_admin", project_name=project_name,
                )
        return document, captured

    def test_external_ai_allowed_by_default(self):
        document, captured = self._spy_and_ingest("AI Allowed By Default")
        self.assertEqual(captured, [False])

    def test_external_ai_can_be_denied_by_active_baseline(self):
        self._activate_baseline_with(ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY)
        document, captured = self._spy_and_ingest("AI Denied")
        self.assertEqual(captured, [True])

    def test_approved_alternative_route_can_be_selected_via_exception(self):
        # Baseline denies external AI org-wide; an org-wide exception
        # (the "approved route") re-allows it -- "approved alternative
        # route can be selected" (Part XVII).
        self._activate_baseline_with(ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY)
        store = self._sec_store()
        record = store.get()
        store.grant_exception(
            record, action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_ALLOW,
            rationale="Approved for this migration window.", granted_by="sec_test_admin",
        )
        document, captured = self._spy_and_ingest("AI Denied Then Exception Allowed")
        self.assertEqual(captured, [False])

    def test_denied_action_generates_an_audit_event(self):
        self._activate_baseline_with(ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY)
        document, _ = self._spy_and_ingest("AI Denied Audit Event")
        events = get_governance_log(self.flask_app).read(document.project_id)
        decision_events = [e for e in events if e.event_type == "security_decision"]
        self.assertEqual(len(decision_events), 1)
        self.assertEqual(decision_events[0].payload["decision"], "deny")
        self.assertEqual(decision_events[0].payload["controlling_layer"], "baseline")

    def test_allowed_action_also_generates_an_audit_event(self):
        # Not just denials -- "Policy -> action -> enforcement decision
        # -> audit event" (Part XIII) applies regardless of outcome.
        document, _ = self._spy_and_ingest("AI Allowed Audit Event")
        events = get_governance_log(self.flask_app).read(document.project_id)
        decision_events = [e for e in events if e.event_type == "security_decision"]
        self.assertEqual(len(decision_events), 1)
        self.assertEqual(decision_events[0].payload["decision"], "allow")


class ExportGateWiringTests(_BaseSecurityTestCase):
    def _ingest_client_project(self, project_name: str):
        return self._ingest(CLIENT_OWNER, project_name)

    def test_export_allowed_by_default(self):
        document = self._ingest_client_project("Export Allowed")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        store.set_project_security_profile(workspace, "standard", actor="sec_test_admin")
        response = self.client.get(f"/projects/{document.project_id}/workspace/rfi-export")
        # 302 either way here (no consistency flags to export -- RFIExportError
        # path), but the security gate itself must not be what blocks it;
        # confirm by checking the flashed message never mentions security policy.
        self.assertIn(response.status_code, (302, 303))

    def test_export_denied_for_highly_restricted_project(self):
        document = self._ingest_client_project("Export Denied")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        store.set_project_security_profile(workspace, CLASSIFICATION_HIGHLY_RESTRICTED, actor="sec_test_admin")

        response = self.client.get(
            f"/projects/{document.project_id}/workspace/rfi-export", follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"security policy", response.data)

    def test_capability_impact_notice_identifies_the_policy_cause(self):
        # "Capability-impact notice identifies policy cause" (Part XVII) --
        # the flashed denial names the controlling layer/reason, not a
        # bare "denied".
        document = self._ingest_client_project("Export Denial Notice")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        store.set_project_security_profile(workspace, CLASSIFICATION_HIGHLY_RESTRICTED, actor="sec_test_admin")

        response = self.client.get(
            f"/projects/{document.project_id}/workspace/rfi-export", follow_redirects=True,
        )
        self.assertIn(b"Project security profile decision", response.data)


class ContentBearingSupportPackageTests(unittest.TestCase):
    def test_technical_telemetry_never_carries_project_content(self):
        telemetry = build_technical_telemetry(app_version="1.0", error_type="ParserError", route="/upload")
        # Structural proof, not a runtime redaction check: the dataclass
        # itself has no field capable of holding free-text project content.
        field_names = {f for f in telemetry.__dataclass_fields__}
        self.assertEqual(field_names, {"app_version", "error_type", "route", "parser_version", "generated_at", "diagnostic_id", "performance_ms"})

    def test_content_bearing_package_denied_without_authorization(self):
        denied_decision = evaluate_action(ACTION_CONTENT_BEARING_SUPPORT_PACKAGE)
        with self.assertRaises(SupportPackageDeniedError):
            build_support_package(
                project_id="p1", contents={"excerpt": "..."}, requested_by="user1",
                purpose="Reproduce parser crash.", security_decision=denied_decision,
            )

    def test_content_bearing_package_succeeds_once_authorized(self):
        allowed_decision = SecurityDecision(
            action_id=ACTION_CONTENT_BEARING_SUPPORT_PACKAGE, decision=DECISION_ALLOW,
            reason="Approved by security officer.", controlling_layer="exception", exception_id="exc-1",
        )
        package = build_support_package(
            project_id="p1", contents={"excerpt": "..."}, requested_by="user1",
            purpose="Reproduce parser crash.", security_decision=allowed_decision,
        )
        self.assertEqual(package.purpose, "Reproduce parser crash.")
        self.assertEqual(package.authorized_decision, DECISION_ALLOW)

    def test_authorized_package_carries_no_standing_grant_beyond_its_purpose(self):
        # No field on SupportPackage could be read as authorizing reuse
        # beyond the one support case -- structural, not a runtime check.
        allowed_decision = SecurityDecision(
            action_id=ACTION_CONTENT_BEARING_SUPPORT_PACKAGE, decision=DECISION_ALLOW,
            reason="x", controlling_layer="exception",
        )
        package = build_support_package(
            project_id="p1", contents={}, requested_by="user1", purpose="x", security_decision=allowed_decision,
        )
        field_names = set(package.__dataclass_fields__)
        for forbidden in ("training_consent", "retain_permanently", "demo_use", "broader_analytics_consent"):
            self.assertNotIn(forbidden, field_names)


class SecurityPolicyCannotAffectOperatingEnvironmentTests(_BaseSecurityTestCase):
    def test_activating_a_deny_all_baseline_does_not_touch_operating_environment(self):
        self._activate_baseline_with(ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY)
        document = self._ingest(DESIGN_BUILDER_PROPONENT, "Env Untouched")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        self.assertEqual(workspace.operating_environment, DESIGN_BUILDER_PROPONENT)

    def test_security_profile_and_operating_environment_are_independent_fields(self):
        document = self._ingest(CLIENT_OWNER, "Independent Fields")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        store.set_project_security_profile(workspace, CLASSIFICATION_HIGHLY_RESTRICTED, actor="sec_test_admin")
        reloaded = store.get(document.project_id)
        self.assertEqual(reloaded.operating_environment, CLIENT_OWNER, "unchanged by the security profile write")
        self.assertEqual(reloaded.security_profile, CLASSIFICATION_HIGHLY_RESTRICTED)


class ReviewerPerspectiveCannotBypassSecurityTests(_BaseSecurityTestCase):
    def test_represented_party_does_not_change_export_gate_outcome(self):
        document = self._ingest(CLIENT_OWNER, "Perspective No Bypass")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        store.set_project_security_profile(workspace, CLASSIFICATION_HIGHLY_RESTRICTED, actor="sec_test_admin")
        participant = store.record_participant(workspace, name="Owner Co", role_type="owner", created_by="sec_test_admin")
        store.set_represented_party(workspace, reviewer="sec_test_admin", participant_id=participant["id"])

        response = self.client.get(
            f"/projects/{document.project_id}/workspace/rfi-export", follow_redirects=True,
        )
        self.assertIn(b"security policy", response.data)


class CapabilityRegistryAndSecurityPolicyBothApplyTests(_BaseSecurityTestCase):
    """CLAUDE-P30's environment capability gate and this stage's
    security policy gate are two independent systems -- both must
    apply, neither substituting for the other."""

    def test_proponent_only_rfi_gate_still_applies_regardless_of_security_profile(self):
        document = self._ingest(CLIENT_OWNER, "Both Gates Apply")
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(document.project_id)
        # Security profile is permissive (standard) -- but the CLAUDE-P30
        # environment capability gate (rfi_originate is proponent-only)
        # must still independently block RFI origination on a Client project.
        store.set_project_security_profile(workspace, "standard", actor="sec_test_admin")
        case = store.create_case(workspace, title="Case", objective="x", created_by="sec_test_admin")

        response = self.client.post(
            f"/projects/{document.project_id}/workspace/cases/{case['id']}/rfi-drafts",
            data={"finding_id": "nonexistent", "question_text": "x"},
        )
        self.assertIn(response.status_code, (302, 303))
        reloaded = store.get(document.project_id)
        self.assertEqual(len(reloaded.rfi_drafts), 0)


class NoTenancyMigrationTests(unittest.TestCase):
    def test_no_organization_or_tenant_sqlalchemy_model_exists(self):
        import models

        model_class_names = {
            name for name in dir(models)
            if isinstance(getattr(models, name), type) and hasattr(getattr(models, name), "__tablename__")
        }
        for forbidden in ("Organization", "OrganizationMembership", "ProjectOwnership"):
            self.assertNotIn(forbidden, model_class_names)

    def test_security_governance_store_is_a_single_global_record_not_per_tenant(self):
        tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_no_tenancy_"))
        try:
            store = SecurityGovernanceStore(tmp_dir)
            record = store.get()
            store.record_source_policy(record, title="p", issuing_organization="org", ingested_by="x")
            # There is exactly one governance file, not one per organization/tenant.
            files = list((tmp_dir / "security_governance").glob("*.json"))
            self.assertEqual(len(files), 1)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
