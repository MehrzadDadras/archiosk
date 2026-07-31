"""
CLAUDE-P31 -- the Security Department workspace: written-policy
ingestion, policy-statement/control-mapping recording, governed Q&A,
baseline draft/acknowledge/activate lifecycle, exceptions, per-project
security profile assignment, and assurance (activity feed + self-check).

Admin-only throughout (@admin_required) -- this codebase has no
dedicated "security officer" role distinct from admin (same reasoning
routes/workspace.py's classify_operating_environment already used for
CLAUDE-P29's equivalent one-time-establishment route).

Classic form-POST -> redirect -> re-render, matching every other
blueprint in this app -- no client-side build step, no fetch/JSON layer.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from werkzeug.utils import secure_filename

from services.auth import admin_required
from services.case_workspace import CaseWorkspaceStore
from services.governance import GovernanceLog
from services.ingestion import get_registry
from services.learning_governance import (
    KNOWN_STAGES,
    LEARNING_ZONES,
    LearningGovernanceError,
    STAGE_APPROVED,
    STAGE_REJECTED,
)
from services.security_assurance import aggregate_security_activity, run_security_self_check
from services.security_governance import (
    KNOWN_CONTROL_SOURCES,
    KNOWN_QA_STATUSES,
    SecurityGovernanceError,
    SecurityGovernanceStore,
)
from services.security_policy import (
    GOVERNED_ACTIONS,
    INFORMATION_CLASSIFICATIONS,
    KNOWN_DECISIONS,
    MANDATORY_FLOOR_PROTECTIONS,
    SECURITY_CLAIMS_REGISTRY,
)

security_bp = Blueprint("security", __name__, url_prefix="/security")


def _store() -> SecurityGovernanceStore:
    return SecurityGovernanceStore(current_app.config["REGISTRY_STORE_PATH"])


def _actor() -> str:
    from flask import session

    return session.get("username") or "anonymous"


def _log() -> GovernanceLog:
    return GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])


@security_bp.route("/")
@admin_required
def department_home():
    store = _store()
    record = store.get()
    registry = get_registry(current_app)

    activity = aggregate_security_activity(registry, _log)[:50]
    self_check_findings = run_security_self_check(
        registry, lambda: CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), store, record,
    )
    projects = [
        {"project_id": pid, "document": doc}
        for pid in registry.list_ids()
        if (doc := registry.get(pid)) is not None
    ]
    case_store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    # CLAUDE-P36: same fail-closed handling as app.py's _nav_recent_
    # projects and routes/portal.py's _accessible_documents (CLAUDE-P32) --
    # a corrupted legacy workspace file (missing fields ProjectWorkspace's
    # current dataclass shape requires, e.g. the pre-existing real
    # instance/registry/ 'reviews'-key incompatibility) must not crash
    # this page for every admin merely because one such project exists
    # on disk. The template already renders "legacy"/"not set" for a
    # None entry (security_department.html's own ws=project_profiles.get(...)
    # guard), so excluding just this one lookup is enough -- the project
    # still appears in the list, only its profile controls degrade.
    project_profiles = {}
    for p in projects:
        try:
            project_profiles[p["project_id"]] = case_store.get(p["project_id"])
        except TypeError:
            project_profiles[p["project_id"]] = None

    return render_template(
        "security_department.html",
        source_policies=record.source_policies,
        policy_statements=record.policy_statements,
        proposed_controls=record.proposed_controls,
        qa_entries=record.qa_entries,
        baselines=list(reversed(record.baselines)),
        active_baseline=store.active_baseline(record),
        exceptions=record.exceptions,
        learning_requests=record.learning_contribution_requests,
        activity=activity,
        self_check_findings=self_check_findings,
        governed_actions=GOVERNED_ACTIONS,
        known_decisions=KNOWN_DECISIONS,
        known_control_sources=KNOWN_CONTROL_SOURCES,
        known_qa_statuses=KNOWN_QA_STATUSES,
        classifications=INFORMATION_CLASSIFICATIONS,
        mandatory_floor_protections=MANDATORY_FLOOR_PROTECTIONS,
        security_claims_registry=SECURITY_CLAIMS_REGISTRY,
        learning_zones=LEARNING_ZONES,
        learning_stages=KNOWN_STAGES,
        projects=projects,
        project_profiles=project_profiles,
    )


# -- source policies + statements -------------------------------------------

@security_bp.route("/policies", methods=["POST"])
@admin_required
def record_source_policy():
    store = _store()
    record = store.get()

    title = (request.form.get("title") or "").strip()
    issuing_organization = (request.form.get("issuing_organization") or "").strip()

    file_path = None
    file_hash = None
    uploaded = request.files.get("policy_file")
    if uploaded and uploaded.filename:
        raw_bytes = uploaded.read()
        policies_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "security_policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(uploaded.filename)
        stored_path = policies_dir / f"{uuid.uuid4().hex}_{safe_name}"
        stored_path.write_bytes(raw_bytes)
        file_path = str(stored_path)
        file_hash = hashlib.sha256(raw_bytes).hexdigest()

    try:
        store.record_source_policy(
            record, title=title, issuing_organization=issuing_organization, ingested_by=_actor(),
            file_path=file_path, file_hash=file_hash,
            policy_owner=(request.form.get("policy_owner") or "").strip() or None,
            approving_authority=(request.form.get("approving_authority") or "").strip() or None,
            version=(request.form.get("version") or "").strip() or None,
            effective_date=(request.form.get("effective_date") or "").strip() or None,
            jurisdiction=(request.form.get("jurisdiction") or "").strip() or None,
            classification=(request.form.get("classification") or "").strip() or None,
        )
        flash("Source policy recorded.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/policies/<policy_id>/statements", methods=["POST"])
@admin_required
def record_policy_statement(policy_id):
    store = _store()
    record = store.get()
    try:
        store.record_policy_statement(
            record, source_policy_id=policy_id, clause_text=request.form.get("clause_text") or "",
            extracted_by=_actor(), clause_reference=(request.form.get("clause_reference") or "").strip() or None,
        )
        flash("Policy statement recorded.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/controls/propose", methods=["POST"])
@admin_required
def propose_control():
    store = _store()
    record = store.get()
    try:
        store.propose_control(
            record, action_id=request.form.get("action_id") or "",
            proposed_decision=request.form.get("proposed_decision") or "",
            rationale=request.form.get("rationale") or "", proposed_by=_actor(),
            source_type=request.form.get("source_type") or "",
            source_id=(request.form.get("source_id") or "").strip() or None,
            ambiguity_note=(request.form.get("ambiguity_note") or "").strip() or None,
        )
        flash("Control proposal recorded.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


# -- Q&A ----------------------------------------------------------------

@security_bp.route("/qa", methods=["POST"])
@admin_required
def record_qa_entry():
    store = _store()
    record = store.get()
    try:
        store.record_qa_entry(
            record, question=request.form.get("question") or "", answer=request.form.get("answer") or "",
            responding_person=request.form.get("responding_person") or "", authority=request.form.get("authority") or "",
            status=request.form.get("status") or "unresolved",
            supporting_source=(request.form.get("supporting_source") or "").strip() or None,
            scope=(request.form.get("scope") or "").strip() or None,
            effective_date=(request.form.get("effective_date") or "").strip() or None,
        )
        flash("Q&A entry recorded.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/qa/<qa_entry_id>/approve", methods=["POST"])
@admin_required
def approve_qa_entry(qa_entry_id):
    store = _store()
    record = store.get()
    try:
        store.approve_qa_entry(record, qa_entry_id, approved_by=_actor())
        flash("Q&A entry approved.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


# -- baselines -----------------------------------------------------------

@security_bp.route("/baselines", methods=["POST"])
@admin_required
def create_baseline():
    store = _store()
    record = store.get()
    store.create_baseline_draft(record, created_by=_actor())
    flash("Baseline draft created.", "success")
    return redirect(url_for("security.department_home"))


@security_bp.route("/baselines/<baseline_id>/controls", methods=["POST"])
@admin_required
def add_baseline_control(baseline_id):
    store = _store()
    record = store.get()
    try:
        store.add_control_decision(
            record, baseline_id=baseline_id, action_id=request.form.get("action_id") or "",
            decision=request.form.get("decision") or "", source_type=request.form.get("source_type") or "",
            actor=_actor(), source_id=(request.form.get("source_id") or "").strip() or None,
            rationale=(request.form.get("rationale") or "").strip() or None,
        )
        flash("Control decision added to baseline.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/baselines/<baseline_id>/acknowledge-impact", methods=["POST"])
@admin_required
def acknowledge_baseline_impact(baseline_id):
    store = _store()
    record = store.get()
    try:
        store.acknowledge_capability_impact(record, baseline_id, actor=_actor())
        flash("Capability impact acknowledged.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/baselines/<baseline_id>/activate", methods=["POST"])
@admin_required
def activate_baseline(baseline_id):
    store = _store()
    record = store.get()
    try:
        store.activate_baseline(record, baseline_id, actor=_actor())
        flash("Baseline activated.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/baselines/<baseline_id>/withdraw", methods=["POST"])
@admin_required
def withdraw_baseline(baseline_id):
    store = _store()
    record = store.get()
    try:
        store.withdraw_baseline(record, baseline_id, actor=_actor())
        flash("Baseline withdrawn.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


# -- exceptions -----------------------------------------------------------

@security_bp.route("/exceptions", methods=["POST"])
@admin_required
def grant_exception():
    store = _store()
    record = store.get()
    try:
        store.grant_exception(
            record, action_id=request.form.get("action_id") or "", decision=request.form.get("decision") or "",
            rationale=request.form.get("rationale") or "", granted_by=_actor(),
            expires_at=(request.form.get("expires_at") or "").strip() or None,
            project_id=(request.form.get("project_id") or "").strip() or None,
        )
        flash("Exception granted.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/exceptions/<exception_id>/revoke", methods=["POST"])
@admin_required
def revoke_exception(exception_id):
    store = _store()
    record = store.get()
    try:
        store.revoke_exception(record, exception_id)
        flash("Exception revoked.", "success")
    except SecurityGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


# -- project security profile ----------------------------------------------

@security_bp.route("/projects/<project_id>/profile", methods=["POST"])
@admin_required
def set_project_profile(project_id):
    case_store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = case_store.get_or_create(project_id)
    try:
        case_store.set_project_security_profile(
            workspace, security_profile=request.form.get("security_profile") or "", actor=_actor(), governance_log=_log(),
        )
        flash("Project security profile updated.", "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


# -- learning contribution requests -----------------------------------------

@security_bp.route("/learning-requests", methods=["POST"])
@admin_required
def create_learning_request():
    store = _store()
    record = store.get()
    try:
        store.create_learning_contribution_request(
            record, project_id=request.form.get("project_id") or "", source_zone=request.form.get("source_zone") or "",
            target_zone=request.form.get("target_zone") or "",
            candidate_description=request.form.get("candidate_description") or "", requested_by=_actor(),
        )
        flash("Learning contribution request recorded.", "success")
    except LearningGovernanceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/learning-requests/<request_id>/advance", methods=["POST"])
@admin_required
def advance_learning_request(request_id):
    store = _store()
    record = store.get()
    try:
        store.advance_learning_contribution_stage(
            record, request_id=request_id, stage=request.form.get("stage") or "", actor=_actor(),
        )
        flash("Learning contribution stage recorded.", "success")
    except (LearningGovernanceError, SecurityGovernanceError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))


@security_bp.route("/learning-requests/<request_id>/decide", methods=["POST"])
@admin_required
def decide_learning_request(request_id):
    store = _store()
    record = store.get()
    decision = request.form.get("decision") or ""
    if decision not in (STAGE_APPROVED, STAGE_REJECTED):
        flash("Invalid decision.", "error")
        return redirect(url_for("security.department_home"))
    try:
        store.decide_learning_contribution(
            record, request_id=request_id, decision=decision, decided_by=_actor(),
            rationale=request.form.get("rationale") or "",
        )
        flash("Learning contribution decision recorded.", "success")
    except (LearningGovernanceError, SecurityGovernanceError) as exc:
        flash(str(exc), "error")
    return redirect(url_for("security.department_home"))
