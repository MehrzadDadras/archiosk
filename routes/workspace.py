"""
Case Workspace routes — the Project / Case / Source / Artifact /
Analysis / Finding / Review / Apply interaction surface. Mounted
alongside the existing portal/api blueprints. Case Workspace is now the
one authoritative project view - the legacy Dashboard (routes/portal.py's
dashboard()) is retired and redirects here.

Classic Flask form-POST -> redirect -> re-render throughout, matching the
rest of this app (no client-side build step, no fetch/JSON layer) — see
tools/dependency_fit.py's no-client-build rule.

Two distinct human-authority mechanisms live here, kept conceptually and
implementationally separate (Prompt 4 #10):

- Approval Gate (_require_approval): "Yes once / Yes for this session /
  No" for consequential, governance-affecting actions (Apply, RFI Issue,
  registering a Source revision).
- Delegation Choice: "Do it for me / Show me the proposed action first /
  Cancel" for the RFI-drafting conversational flow - how much of the
  drafting work the reviewer wants to see before it happens.
"""
from __future__ import annotations

import io
import mimetypes
import uuid
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from PIL import Image
from werkzeug.utils import secure_filename

from services.auth import admin_required, login_required
from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    CASE_OUTCOME_STATES,
    CASE_ORIGIN_AUTONOMOUS,
    GO_NO_GO_DECISIONS,
    KNOWN_PARTICIPANT_ROLES,
    KNOWN_PERSPECTIVE_POLARITIES,
    KNOWN_RESOLUTION_OUTCOMES,
    MESSAGE_ORIGIN_HUMAN,
    OBJECT_KIND_CASE,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_REQUIREMENT,
    PERSPECTIVE_ORIGIN_HUMAN,
    REQUIREMENT_ADJUDICATION_OUTCOMES,
    REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    REQUIREMENT_STATUS_SUPERSEDED,
    SOURCE_KIND_PROJECT_DOCUMENT,
    SOURCE_KIND_TEXT_RECORD,
    Anchor,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DISPOSITIONS,
    OperatingEnvironmentAlreadySetError,
    REVIEWER_VALIDATION_STATES,
)
from services.environment_capabilities import (
    OPERATING_ENVIRONMENT_LABELS,
    allowed_participant_roles,
    capability_availability,
    capability_denial_reason,
    decision_stages_for_environment,
    is_valid_operating_environment,
)
from services.conversation_interpreter import _looks_like_project_question, interpret_message
from services.governance import GovernanceLog
from services.ingestion import UploadError, document_source_payload, get_registry, reject_if_display_name_taken
from services.project_clock import open_project
from services.rfi_export import RFIExportError, build_rfi_docx, build_rfi_draft_docx
from models import User

workspace_bp = Blueprint("workspace", __name__)

ALLOWED_DRAWING_EXTENSIONS = {".png", ".jpg", ".jpeg"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md"}

# Requirement-evidence explainability: maps the EXISTING, already-governed
# Relationship.relationship_type vocabulary (case_workspace.py's
# KNOWN_RELATIONSHIP_TYPES) onto the workspace's own already-documented
# 4-color semantic language (static/css/main.css's "Case Workspace semantic
# color language": green=accepted/supported, red=rejected/contradiction,
# amber=needs evidence/uncertain, cyan=machine/reference/linkage) - no new
# truth-status vocabulary invented, purely a display mapping.
_RELATIONSHIP_COLOR_CLASS = {
    "supports": "green",
    "corresponds_to": "green",
    "implements": "green",
    "contradicts": "red",
    "blocks": "red",
    "qualifies": "amber",
    "affects": "amber",
    "references": "cyan",
    "depicts": "cyan",
    "depends_on": "cyan",
    "resulted_in": "cyan",
    "derived_from": "cyan",
    "carried_forward_from": "cyan",
}


def _store() -> CaseWorkspaceStore:
    return CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])


def _reviewer() -> str:
    return session.get("username") or "anonymous"


def _log() -> GovernanceLog:
    return GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])


def _load_workspace_or_404(project_id: str):
    """
    CLAUDE-P32: the near-universal choke point every route in this file
    reaches project data through (47 of this blueprint's 50 routes
    already called this before this stage; export_rfi -- the one
    exception -- was refactored to call it too, see below). Project-level
    access is checked here immediately after the workspace is loaded/
    backfilled, BEFORE this function returns -- 404, not 403, matching
    _require_visible_case's own established "don't confirm existence to
    a non-member" convention, applied one layer up from Case privacy to
    project-level access itself.
    """
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    store = _store()
    # CLAUDE-P37: a corrupted legacy workspace file (missing a field
    # ProjectWorkspace's current dataclass shape requires) must 404 here,
    # not 500 -- the exact same "don't confirm existence to a non-member"
    # convention this function already applies to an unauthorized caller,
    # now also applied to a request this deployment itself can't honestly
    # serve. Found live during CLAUDE-P36's real-app walkthrough that this
    # near-universal choke point (47+ of this blueprint's own routes) had
    # never been given the same fail-closed handling already applied
    # elsewhere (app.py's _nav_recent_projects, routes/portal.py's
    # _accessible_documents, routes/security.py's department_home,
    # services/security_assurance.py's self-check) for this identical,
    # already-diagnosed defect class.
    try:
        workspace = store.get_or_create(
            project_id, register_document_source=document_source_payload(document),
        )
    except TypeError:
        abort(404)

    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    ensure_owner_backfilled(store, workspace, _log(), known_usernames())
    if not can_access_project(workspace, session.get("username"), session.get("role") == "admin"):
        abort(404)

    return document, store, workspace


def _thread_case_id(workspace, thread_id):
    """The thread's OWN recorded case_id, looked up server-side - never
    trust a client-supplied hidden `case_id` form field for an
    authorization decision (a caller could submit a case_id they own
    alongside a thread_id belonging to someone else's Private Case).
    Returns None both when the thread doesn't exist (the caller's own
    subsequent store-layer call already raises a real not-found error)
    and when it exists but has no Case anchor at all."""
    thread = next((t for t in workspace.review_threads if t["id"] == thread_id), None)
    return thread.get("case_id") if thread else None


def _finding_case_id(workspace, finding_id):
    """The Finding's OWN recorded case_id, looked up server-side - same
    reasoning as _thread_case_id: a route keyed by finding_id must never
    trust a separate, client-supplied case_id form field for its
    authorization decision (validate_finding/set_disposition/
    create_rfi_draft all take finding_id as the real write target;
    case_id in their forms was historically only ever used for the
    redirect/log line, never checked)."""
    finding = next((f for f in workspace.findings if f["id"] == finding_id), None)
    return finding.get("case_id") if finding else None


def _rfi_draft_case_id(workspace, draft_id):
    """The RFIDraft's OWN recorded case_id (itself always server-derived
    from its Finding's case_id at creation time - see
    CaseWorkspaceStore.create_rfi_draft - never from a caller-supplied
    value), looked up server-side for the same reason as
    _thread_case_id/_finding_case_id."""
    draft = next((d for d in workspace.rfi_drafts if d["id"] == draft_id), None)
    return draft.get("case_id") if draft else None


def _attention_case_id(workspace, attention_id):
    """An Attention carries no case_id of its own (see Attention's own
    docstring) - its real Case is its thread's Case, one hop through
    _thread_case_id. Same reasoning as the other _*_case_id helpers:
    never trust a caller-supplied case_id for this route's authorization
    decision."""
    attention = next((a for a in workspace.attentions if a["id"] == attention_id), None)
    if attention is None:
        return None
    return _thread_case_id(workspace, attention["thread_id"])


def _require_visible_case(store: CaseWorkspaceStore, workspace, case_id) -> None:
    """
    The one authorization check every Case-scoped write/download route in
    this file now runs before acting: derive the real Case (from the URL,
    or - for routes keyed by a finding/thread/RFI-draft id instead -
    server-side via _finding_case_id/_thread_case_id/_rfi_draft_case_id,
    never a client-supplied hidden form field) and verify the requester
    may actually see it. `None` is a legitimate no-op (a Project-level
    write, or a Requirement, which has no Case of its own at all - see
    current/kernel-object-model.md's "Case"/"Requirement" entries). A
    visible-but-nonexistent case_id is left to the caller's own
    subsequent lookup - this only ever adds an additional rejection for a
    real Case the requester is not allowed to see, mirroring
    _require_case_not_archived's own "additional reason, never replaces
    the normal check" shape.
    """
    if not case_id:
        return
    visible_ids = {c["id"] for c in store.visible_cases_for(workspace, _reviewer())}
    if case_id not in visible_ids:
        abort(404)


def _require_capability(workspace, capability_id: str, project_id: str, case_id=None):
    """
    CLAUDE-P30: the shared enforcement point for every environment-gated
    capability (services.environment_capabilities.CAPABILITY_REGISTRY) --
    mirrors _require_visible_case's own shape (a route-layer check that
    can never be weaker than what the template already hid) rather than
    each route writing its own if-environment branch and denial message.
    Returns None if the caller should proceed, or a redirect (with a
    flashed, centrally-produced denial reason) if it must not.
    """
    if capability_availability(capability_id, workspace.operating_environment):
        return None
    flash(capability_denial_reason(capability_id, workspace.operating_environment), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


def _evaluate_security_action(workspace, action_id: str):
    """
    CLAUDE-P31: the one route-layer entry point into
    services.security_policy.evaluate_action for this project -- looks
    up the active organization baseline/exception plus this project's
    own security_profile classification, then resolves them exactly the
    same way services/ingestion.py's ingestion-time gate already does
    (the two share the resolver, not the lookup boilerplate, but the
    boilerplate itself is short enough that duplicating the four lookup
    lines here was judged clearer than a shared helper needing a Flask
    app-context parameter threaded through services/ingestion.py too).
    """
    from services.security_governance import SecurityGovernanceStore
    from services.security_policy import evaluate_action, profile_decision_for

    security_store = SecurityGovernanceStore(current_app.config["REGISTRY_STORE_PATH"])
    security_record = security_store.get()
    active_baseline = security_store.active_baseline(security_record)
    return evaluate_action(
        action_id,
        classification=workspace.security_profile,
        baseline_decision=(
            active_baseline["control_decisions"].get(action_id, {}).get("decision")
            if active_baseline else None
        ),
        baseline_version_id=active_baseline["id"] if active_baseline else None,
        profile_decision=profile_decision_for(workspace.security_profile, action_id),
        active_exception=security_store.active_exception_for(
            security_record, action_id, project_id=workspace.project_id,
        ),
    )


def _require_export_allowed(workspace, project_id: str):
    """
    Returns None if export should proceed, or a redirect (flashed
    denial, naming the controlling policy layer per Part VIII's
    user-facing-notice requirement) if it must not. DECISION_ALLOW and
    DECISION_ALLOW_APPROVED_ROUTE both proceed (this stage has no
    separate "approved route" UI step to gate behind -- an activated
    exception already IS that approved route, see
    services.security_governance.SecurityGovernanceStore.grant_exception);
    everything else (REQUIRE_APPROVAL/ISOLATE/DENY/UNSUPPORTED) blocks.
    """
    from services.security_policy import ACTION_EXPORT, DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE

    decision = _evaluate_security_action(workspace, ACTION_EXPORT)
    if decision.decision in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        return None
    flash(
        f"Export is not available for this project under its current security policy "
        f"({decision.reason}). Decision: {decision.decision.replace('_', ' ')}.",
        "error",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


# -- Approval Gate ---------------------------------------------------------------

def _is_approved_for_session(action_class: str) -> bool:
    return action_class in session.get("approved_action_classes", [])


def _approve_for_session(action_class: str) -> None:
    approved = session.get("approved_action_classes", [])
    if action_class not in approved:
        approved.append(action_class)
    session["approved_action_classes"] = approved


def _require_approval(action_class: str, description: str, project_id: str, case_id: str):
    """
    Returns None if the caller should proceed with the action now, or a
    rendered confirmation page if it must pause first. Consequential,
    governance-affecting actions only (Apply, RFI Issue, Source
    revision) - never ordinary navigation or Analysis.
    """
    confirm = request.form.get("confirm")

    if _is_approved_for_session(action_class):
        return None
    if confirm == "once":
        return None
    if confirm == "session":
        _approve_for_session(action_class)
        return None
    if confirm == "no":
        flash("Cancelled - no change was made.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    return render_template(
        "confirm_action.html",
        description=description,
        action_url=request.url,
        project_id=project_id,
        case_id=case_id,
    )


@workspace_bp.route("/projects/<project_id>/workspace")
@login_required
def show_workspace(project_id):
    document, store, workspace = _load_workspace_or_404(project_id)

    # Prompt 8/9: Project Open -> temporal reconciliation, now called
    # through the explicitly named open_project() operation rather than
    # inlining reconcile_project() here (Prompt 9 #4) - this route is
    # still the only caller today, but the operation itself no longer
    # conceptually belongs to "what GET does". This makes a GET request
    # capable of writing (a governance event, and occasionally a thin
    # CLOCK_INITIATED Analysis) where GET requests were previously pure
    # reads - an honest, small semantic shift documented in the Foundation
    # Batch B/C reports. Never lets a reconciliation failure break the
    # page: this is incidental background work triggered by a page view,
    # not something the reviewer explicitly asked for, so a rare
    # stale-write conflict here is skipped for this render rather than
    # surfaced as a broken page.
    try:
        open_project(workspace, store, _log())
    except CaseWorkspaceError:
        pass

    # Case privacy enforcement point (ratified governance baseline): every
    # listing, default-selection, and explicit ?case= lookup below resolves
    # against visible_cases, never the raw workspace.cases list - a Case
    # this reviewer cannot see must never become active_case, appear in the
    # sidebar count/list, or be reachable by guessing/typing its id into
    # the query string. See CaseWorkspaceStore.visible_cases_for.
    visible_cases = store.visible_cases_for(workspace, _reviewer())
    visible_case_ids = {c["id"] for c in visible_cases}

    # Prompt 3 (Project Home): opening a Project no longer auto-jumps into
    # its first Case - a Project with Cases now lands on Project Home just
    # like a brand-new one, and a Case is only ever entered through an
    # explicit ?case= (a real link: "Open Investigation", a Project Home
    # composer submission, an existing bookmark). Everything below that
    # depends on active_case already degrades to its own honest empty
    # state when active_case is None (findings_view=[], threads_view=[],
    # etc.) - this is the one behavioral change that makes Project Home
    # the default landing state, not a new rendering path of its own.
    active_case_id = request.args.get("case")
    active_case = next((c for c in visible_cases if c["id"] == active_case_id), None)

    # Project-wide "Needs Attention": every unresolved Finding (not yet
    # "applied") across every non-archived visible Case, not just
    # whichever one is currently open. Real, recorded user gap: the
    # Cedar Harbour walkthrough asked for exactly this - "a central page
    # that compiles all discrepancies within the project so we can do
    # the adjustment centrally... clicking on the highlighted issue
    # takes us to [it]" - and it was never built. The count alone
    # already existed (project_home_summary, below, reused this same
    # filter) but only as a number, and only on Project Home - once any
    # Case was open, visibility into every OTHER Case's unresolved work
    # disappeared entirely. Computed unconditionally now, not gated on
    # active_case being None, and grouped by Case (in visible_cases'
    # already-open-before-archived order) rather than given its own new
    # priority ranking - the same restraint as the open, not-yet-fixed
    # findings_view ordering question below: which Finding matters most
    # is a review-state judgment call, not a geometry one.
    open_visible_cases = [c for c in visible_cases if c["status"] != "archived"]
    needs_attention_view = []
    for case in open_visible_cases:
        case_unresolved = [
            f for f in workspace.findings
            if f["case_id"] == case["id"] and f["claim_status"] != "applied"
        ]
        if case_unresolved:
            needs_attention_view.append({"case": case, "findings": case_unresolved})

    # CLAUDE-P11: this reviewer's own visible Cases' recorded hypothesis
    # verdicts (or the derived "unresolved" when none is recorded yet) -
    # keyed by case_id so the Cases list can show a badge without a
    # per-case query each time it's rendered.
    case_outcome_states = {c["id"]: store.case_outcome_state(workspace, c["id"]) for c in visible_cases}

    # CLAUDE-P13R: which visible Cases the machine opened entirely on its
    # own (case_origin_kind), so the Cases list can flag them plainly -
    # opening one is never itself authority (see CaseOutcome), but a
    # reviewer should always be able to tell at a glance that no human
    # decided this was worth investigating.
    case_origin_kinds = {c["id"]: store.case_origin_kind(workspace, c) for c in visible_cases}

    # Project Home's compact "Active Work" summary - project-wide (across
    # every Case this reviewer can see), computed only when actually
    # needed (Project Home is showing) since it's an extra pass over
    # workspace.findings that a Case-focused render has no use for.
    # "Unresolved" / "Awaiting Pass" reuse existing, already-governed
    # fields (Finding.claim_status, Disposition) - no new status
    # vocabulary invented for this summary.
    project_home_summary = None
    if active_case is None:
        visible_findings = [f for f in workspace.findings if f["case_id"] in visible_case_ids]
        unresolved_findings = [f for f in visible_findings if f["claim_status"] != "applied"]
        awaiting_pass = [
            f for f in unresolved_findings
            if store.latest_disposition(workspace, f["id"]) is None
        ]
        project_home_summary = {
            "investigations_count": len(open_visible_cases),
            "unresolved_findings_count": len(unresolved_findings),
            "awaiting_pass_count": len(awaiting_pass),
            "open_cases": open_visible_cases,
        }

    # "What has just changed?" - a returning reviewer currently has no way
    # to know what's new without re-reading the whole History log
    # themselves. Read the OLD marker before overwriting it (so this
    # render can still say what changed since THAT visit, not since the
    # one about to be recorded), count real governance events since
    # then, then record now as the new marker. Deliberately just a count
    # + timestamp, not per-item "new" tags scattered across every
    # accordion - a small, honest signal rather than a bigger UI change
    # made as a side effect of this one.
    # The project-level conversational aperture (no Case): messages posted
    # against the Project itself, or anchored to a project-level object
    # (a Requirement's "Discuss this" affordance) rather than any one
    # Investigation. Only ever shown on Project Home - Case conversation
    # stays exactly where it already was, embedded on the Case itself.
    project_conversation_view = None
    if active_case is None:
        project_conversation_view = store.project_conversation_for(workspace)

    # Snapshot read-side (CLAUDE-P27): the list itself was already wired
    # directly off workspace.snapshots (no route needed - see the "View
    # Snapshots" subdisclosure below), but resolve_snapshot_objects/
    # compare_snapshots had no caller anywhere. Project Home only, same
    # gating as project_conversation_view above - a Snapshot is a
    # project-wide concept with no Case scope of its own. A bad/stale id
    # in the query string (typed, or a Snapshot from before this reviewer
    # had access) degrades to "nothing to show" rather than a 404/500,
    # matching preview_finding_id's guard pattern below.
    opened_snapshot_view = None
    snapshot_compare_view = None
    if active_case is None:
        open_snapshot_id = request.args.get("snapshot")
        if open_snapshot_id:
            snapshot = store.get_snapshot(workspace, open_snapshot_id)
            if snapshot is not None:
                lists_view = []
                for list_name, ids in snapshot["reference_lists"].items():
                    if not ids:
                        continue
                    resolved = store.resolve_snapshot_objects(workspace, open_snapshot_id, list_name)
                    # resolved_count can be less than frozen_count if a
                    # referenced record no longer exists in the current
                    # list it was frozen from - resolve_snapshot_objects
                    # itself is silent about this (see its own docstring
                    # on resolving to CURRENT content), so this is the
                    # only place that count ever gets surfaced.
                    lists_view.append({
                        "list_name": list_name,
                        "frozen_count": len(ids),
                        "resolved_count": len(resolved),
                        "unresolved_count": len(ids) - len(resolved),
                    })
                opened_snapshot_view = {"snapshot": snapshot, "lists": lists_view}

        compare_a_id = request.args.get("compare_a")
        compare_b_id = request.args.get("compare_b")
        if compare_a_id and compare_b_id:
            snapshot_a = store.get_snapshot(workspace, compare_a_id)
            snapshot_b = store.get_snapshot(workspace, compare_b_id)
            if snapshot_a is not None and snapshot_b is not None:
                comparison = store.compare_snapshots(workspace, compare_a_id, compare_b_id)
                comparison_rows = []
                for list_name, counts in comparison.items():
                    if counts["count_a"] == 0 and counts["count_b"] == 0:
                        continue
                    comparison_rows.append({
                        "list_name": list_name,
                        "count_a": counts["count_a"],
                        "count_b": counts["count_b"],
                        "added": counts["added_in_b"],
                        "removed": counts["removed_in_b"],
                        # compare_snapshot_reference_lists (services/
                        # case_workspace.py) only returns added/removed -
                        # unchanged is derived here, not a new stored
                        # concept: count_a minus what b no longer has.
                        "unchanged": counts["count_a"] - len(counts["removed_in_b"]),
                    })
                snapshot_compare_view = {
                    "snapshot_a": snapshot_a,
                    "snapshot_b": snapshot_b,
                    "rows": comparison_rows,
                }

    # Read before any write below touches it - this is also the boundary
    # visual pressure (below) uses to tell "settled, and already known to
    # you" apart from "settled, but news to you since your last visit" -
    # the same global "what's new" marker, reused rather than a second,
    # separately-invented time threshold.
    previous_visit_at = workspace.last_viewed_by.get(_reviewer())

    since_last_visit = None
    if active_case is None:
        if previous_visit_at is not None:
            new_event_count = sum(
                1 for e in _log().read(project_id) if e.created_at > previous_visit_at
            )
            since_last_visit = {"previous_visit_at": previous_visit_at, "new_event_count": new_event_count}
        # CLAUDE-P40-D2: was workspace.last_viewed_by[...] = ...; store.save
        # (workspace) - save()'s asdict(workspace) serializes the COMPLETE
        # in-memory object, silently persisting legacy compatibility
        # hydration (and every other dataclass default) as a byproduct of
        # a plain view. record_last_viewed patches only last_viewed_by
        # into the raw on-disk JSON - see its own docstring.
        store.record_last_viewed(workspace, _reviewer())

    focused_finding_id = session.get(f"focused_finding:{project_id}")

    # OPEN, NOT YET JUSTIFIED TO FIX: findings_view (and requirements_view,
    # below) render in active_case["finding_ids"] / governed_requirements
    # order - i.e. whatever order they were created/registered in, not
    # sorted by what needs attention. A finding still awaiting review sits
    # wherever it was created, not ahead of ones already Confirmed/Applied.
    # Same class of bug as the Case Workspace pane-priority fix, but a real
    # fix here means choosing a review-state priority ranking, which is a
    # workflow/domain judgment call this project has historically made
    # deliberately (see the Reviewer Validation / Disposition / Adjudication
    # model) - not something to decide as a side effect of a geometry pass.
    findings_view = []
    applied_count = 0
    awaiting_apply_count = 0

    if active_case is not None:
        for finding_id in active_case["finding_ids"]:
            finding = next(f for f in workspace.findings if f["id"] == finding_id)
            artifact = None
            if finding.get("artifact_id"):
                artifact = next(
                    (a for a in workspace.artifacts if a["id"] == finding["artifact_id"]), None
                )
            latest_validation = store.latest_reviewer_validation(workspace, finding_id)
            latest_disposition = store.latest_disposition(workspace, finding_id)
            review_state = store.review_state_for_finding(workspace, finding_id)

            if finding["claim_status"] == "applied":
                applied_count += 1
            elif latest_disposition is not None and latest_disposition["disposition"] == "Confirmed":
                awaiting_apply_count += 1

            findings_view.append(
                {
                    "finding": finding,
                    "artifact": artifact,
                    "review_state": review_state,
                    "reviewer_validations": store.reviewer_validations_for_finding(workspace, finding_id),
                    "latest_validation": latest_validation,
                    "latest_disposition": latest_disposition,
                    "rfi_drafts": [
                        d for d in store.rfi_drafts_for_case(workspace, active_case["id"])
                        if d["finding_id"] == finding_id
                    ],
                    # CLAUDE-P08: the auditable worklist entry behind this
                    # Finding, if a real investigation produced it - None
                    # for every mock drawing-analysis Finding, which never
                    # records one.
                    "investigation_step": store.investigation_step_for_analysis(
                        workspace, finding["analysis_id"]
                    ),
                }
            )

    pending_rfi_finding_id = None
    if active_case is not None and active_case["conversation"]:
        last_message = active_case["conversation"][-1]
        action_taken = last_message.get("action_taken") or ""
        if action_taken.startswith("rfi_intent:"):
            pending_rfi_finding_id = action_taken.split(":", 1)[1]

    rfi_preview = None
    preview_finding_id = request.args.get("preview_finding_id")
    if preview_finding_id:
        # Indirect-identifier guard: a finding_id typed/guessed into the
        # query string must not bypass Case privacy - only build the
        # preview if the finding actually belongs to a Case this reviewer
        # can see.
        preview_finding = next((f for f in workspace.findings if f["id"] == preview_finding_id), None)
        visible_case_ids = {c["id"] for c in visible_cases}
        if preview_finding is not None and preview_finding.get("case_id") in visible_case_ids:
            try:
                rfi_preview = store.build_reference_snapshot(workspace, preview_finding_id)
            except CaseWorkspaceError:
                rfi_preview = None

    revision_notices = (
        store.revision_notices_for_case(workspace, active_case["id"]) if active_case else []
    )

    # Requirement promotion/adjudication: Requirement is project-scoped
    # (no case_id of its own - see current/kernel-object-model.md), so
    # this view-model is built once per page render regardless of which
    # Case is active. `original_requirement_identifier` is the one field
    # that ties a governed Requirement back to the RequirementItem it was
    # promoted from (see promote_requirement_item) - used here only to
    # keep an already-promoted item off the "not yet promoted" list, not
    # as a general-purpose lookup key.
    governed_requirements = store.requirements_for_project(workspace)
    promoted_item_ids = {r["original_requirement_identifier"] for r in governed_requirements}
    unpromoted_requirement_items = [
        item for item in document.requirements if item.id not in promoted_item_ids
    ]

    # Explainability, not a new compliance engine: for each Requirement,
    # resolve what a human already cited as evidence when adjudicating it
    # (requirement_evidence, reusing the existing evidence_finding_ids/
    # evidence_relationship_ids link) plus any AcceptedKnowledge derived
    # from those same Findings. A Finding's own statement/Case title is
    # only ever rendered here if its Case is in THIS requester's own
    # visible_cases - the store layer's query is Case-visibility-blind by
    # design (it's a pure project-level read), so the redaction decision
    # belongs here, the one place that actually knows who's asking.
    # (visible_case_ids computed once, above, alongside visible_cases.)
    #
    # revise_requirement (services/case_workspace.py) was fully built and
    # tested - the real, governed way to represent an Addendum amending a
    # Requirement's text, per the method's own documented intent ("An
    # Addendum amending/qualifying/superseding an earlier requirement is
    # exactly this call") - but had no route at all. Wiring it means the
    # main list must stop showing a Requirement's now-superseded
    # predecessors as if they were separate, still-current entries -
    # governed_requirements itself is deliberately unfiltered (needed
    # whole, above, for promoted_item_ids), so the filter happens only
    # here, at display time.
    def _requirement_revision_history(requirement_id):
        history = []
        current_id = requirement_id
        while True:
            predecessor_supersession = next(
                (
                    s for s in workspace.supersessions
                    if s["successor_type"] == OBJECT_KIND_REQUIREMENT and s["successor_id"] == current_id
                ),
                None,
            )
            if predecessor_supersession is None:
                break
            predecessor = next(
                (r for r in governed_requirements if r["id"] == predecessor_supersession["predecessor_id"]), None,
            )
            if predecessor is None:
                break
            history.append({"requirement": predecessor, "supersession": predecessor_supersession})
            current_id = predecessor["id"]
        return history

    # CLAUDE-P12R: which Participant THIS reviewer currently represents -
    # a personal setting (store.represented_party_for), not a governed
    # fact. None until they've explicitly set one; nothing below treats
    # that as an error, only as "no perspective to show yet."
    represented_party = store.represented_party_for(workspace, _reviewer())

    requirements_view = []
    for requirement in governed_requirements:
        if requirement["status"] == REQUIREMENT_STATUS_SUPERSEDED:
            continue
        evidence = store.requirement_evidence(workspace, requirement["id"])
        evidence_findings_view = []
        for finding in evidence["findings"]:
            if finding.get("case_id") in visible_case_ids:
                case = next((c for c in workspace.cases if c["id"] == finding["case_id"]), None)
                evidence_findings_view.append({
                    "visible": True,
                    "statement": finding["statement"],
                    "claim_status": finding["claim_status"],
                    "case_title": case["title"] if case else None,
                })
            else:
                evidence_findings_view.append({"visible": False})
        evidence_relationships_view = [
            {
                "relationship_type": relationship["relationship_type"],
                "from_type": relationship["from_type"],
                "to_type": relationship["to_type"],
                "color_class": _RELATIONSHIP_COLOR_CLASS.get(relationship["relationship_type"], "cyan"),
            }
            for relationship in evidence["relationships"]
        ]
        requirements_view.append({
            "requirement": requirement,
            "revision_history": _requirement_revision_history(requirement["id"]),
            "adjudication_state": store.requirement_adjudication_state(workspace, requirement["id"]),
            "latest_adjudication": evidence["adjudication"],
            # Full history, not just latest - the data was always
            # non-destructively preserved (requirement_adjudications_for
            # already existed, unused by any route or template); this was
            # a rendering gap, not a storage gap. Surfacing it is the
            # "what has this project already taught us to re-check" view:
            # honest re-display of what actually happened, not a new
            # inferred pattern/suggestion layered on top of it.
            "adjudication_history": store.requirement_adjudications_for(workspace, requirement["id"]),
            "evidence_findings": evidence_findings_view,
            "evidence_relationships": evidence_relationships_view,
            # AcceptedKnowledge is deliberately project-wide, not Case-gated,
            # by the same pre-existing design as the "Accepted Knowledge"
            # panel itself (Apply is the explicit human act that graduates a
            # Finding's substance into project knowledge, independent of its
            # source Case's own visibility) - not re-decided here.
            "accepted_knowledge": evidence["accepted_knowledge"],
            # CLAUDE-P12R: the represented reviewer's own mark vs. the
            # machine's independently-reached one, for the SAME
            # Requirement+Participant - None entirely when no represented
            # party is set, never a guess at what it would be.
            "perspective": (
                store.perspective_convergence_for(
                    workspace, OBJECT_KIND_REQUIREMENT, requirement["id"], represented_party["id"],
                )
                if represented_party else None
            ),
        })

    # Compliance rollup: a transparent count of ACTUAL requirement_
    # adjudication_state values (REQUIREMENT_ADJUDICATION_STATE_NOT_YET_
    # ASSESSED or one of REQUIREMENT_ADJUDICATION_OUTCOMES) - never a new
    # invented compliance score. Ordinary dict, insertion order matches
    # first-seen order so a re-render is stable rather than jittering.
    compliance_rollup: dict[str, int] = {}
    for row in requirements_view:
        state = row["adjudication_state"]
        compliance_rollup[state] = compliance_rollup.get(state, 0) + 1

    # Plain, structural fact, not a synthesized "pattern" or suggestion:
    # how many governed Requirements have needed more than one
    # Adjudication. Says nothing about outcomes or why - purely a count,
    # answering "how much has this project already had to re-check its
    # own conclusions" at a glance.
    revisited_requirements_count = sum(1 for row in requirements_view if len(row["adjudication_history"]) > 1)

    # Recent provenance, visible from inside the workspace itself rather
    # than only on the separate legacy dashboard - most-recent-first,
    # capped so the sidebar stays scannable rather than becoming its own
    # unbounded log viewer.
    _all_governance_events = list(reversed(_log().read(project_id)))
    recent_governance_events = _all_governance_events[:25]
    # CLAUDE-P38 (OBS-12): total count (unbounded by the display cap
    # above) so a compact summary state can honestly say "N events,
    # latest ..." without implying only 25 ever happened.
    history_total_count = len(_all_governance_events)

    # TemporalObligation (services/case_workspace.py) was fully built
    # (create/revise/list/evaluate_temporal_condition) but never wired to
    # any route - the real, tested replacement for the old milestone
    # lattice, which was dropped for being non-functional (see the
    # Dashboard-retirement commit). Project-wide, not Case-filtered
    # (temporal_obligations_for_project takes no case_id), same as
    # History above. Sorted by actual urgency - explicit priority, not
    # creation order - since this is exactly a "what needs attention"
    # list: overdue first, then due, due soon, not yet due, and the
    # three terminal statuses last (nothing to act on there).
    _CONDITION_PRIORITY = {
        "overdue": 0, "due": 1, "due_soon": 2, "not_yet_due": 3,
        "completed": 4, "cancelled": 4, "superseded": 4,
    }
    temporal_obligations_view = sorted(
        (
            {"obligation": ob, "condition": store.temporal_condition_for(workspace, ob["id"])}
            for ob in store.temporal_obligations_for_project(workspace)
        ),
        key=lambda row: _CONDITION_PRIORITY.get(row["condition"], 3),
    )

    # CLAUDE-P38 (OBS-11): Key Dates only ever showed manually-created
    # TemporalObligations, even though the parser already extracts
    # schedule-related lines from the source document itself
    # (document.milestones, via BHiveParser._derive_milestones) -- that
    # data existed but was never surfaced anywhere in the workspace.
    # Deliberately kept separate from temporal_obligations_view, not
    # merged into it: these are unconfirmed extracted candidates (no
    # date-parsing/fixed-vs-relative classification exists yet - see
    # _derive_milestones' own narrow shape), never promoted into a real
    # governed TemporalObligation automatically.
    source_milestones_view = list(document.milestones)

    # CLAUDE-P38-B: deterministic sections cost nothing to recompute on
    # every render (no AI call - see deterministic_sections' own
    # docstring), unlike the real synthesis cached on
    # workspace.project_briefing below. Only ever shown on Project Home
    # (no active_case) - the opening briefing is a project-wide concept,
    # same gating as project_conversation_view/Snapshot above.
    briefing_deterministic = None
    briefing_stale = False
    briefing_ai_status = None
    briefing_ai_decision = None
    briefing_generation_in_progress = False
    briefing_has_evidence = False
    if active_case is None:
        from services.project_briefing import deterministic_sections

        briefing_deterministic = deterministic_sections(
            [{"text": r.text, "category": r.category} for r in document.requirements],
            list(document.milestones),
        )
        if workspace.project_briefing is not None:
            briefing_stale = workspace.project_briefing_source_signature != store.source_signature_for(workspace)
        briefing_ai_status, briefing_ai_decision = _project_briefing_ai_status(workspace)
        briefing_generation_in_progress = store.generation_in_progress_for(workspace)
        # Same "evidence presence, not workspace.sources alone" rule as
        # preparing_project_briefing below - the originally-ingested
        # document never gets its own Source record.
        briefing_has_evidence = bool(document.requirements or document.milestones or workspace.sources)

    # CLAUDE-P38 (OBS-08): RFI drafts were only ever visible per-Finding,
    # inside whichever Case happened to be open (row.rfi_drafts, the
    # Findings accordion) - there was no project-wide place to see every
    # RFI regardless of which Case produced it, or its lifecycle state.
    # No new domain concept: workspace.rfi_drafts already carries every
    # field needed (status/question_text/created_by/issued_by/...) -
    # this is purely a project-wide read-side view, case title resolved
    # once here rather than repeated per-row logic in the template.
    # Filtered to visible_cases only - same Case-privacy discipline the
    # Findings section already applies (a Finding's Case title is only
    # ever rendered if that Case is in THIS requester's own
    # visible_cases); an RFI belonging to a Case this reviewer can't see
    # must not leak that Case's existence or title here either.
    _visible_case_titles_by_id = {c["id"]: c["title"] for c in visible_cases}
    rfi_drafts_view = sorted(
        (
            {"draft": d, "case_title": _visible_case_titles_by_id[d["case_id"]]}
            for d in workspace.rfi_drafts
            if d["case_id"] in visible_case_ids
        ),
        key=lambda row: row["draft"]["created_at"], reverse=True,
    )

    # "Where did I leave off?" - the contextual-companion continuity
    # trail: this reviewer's own recent anchored conversation (from
    # store.recent_anchors_for, itself derived purely from existing
    # ConversationMessage records - no separate "memory" store to drift
    # out of sync). Shown regardless of active_case (like Needs
    # Attention) since the whole point is to stay reachable even while
    # deep inside one Investigation. Only anchor_type == "requirement"
    # is resolved to a real current-state label today (the only aperture
    # that exists yet); anything else falls back to its own recorded
    # description rather than guessing.
    recent_focus_view = []
    for message in store.recent_anchors_for(workspace, _reviewer(), visible_case_ids):
        anchor = message["anchor"]
        label = anchor.get("description") or anchor.get("anchor_id")
        current_state = None
        changed_since = False
        if anchor["anchor_type"] == "requirement":
            req_row = next(
                (r for r in requirements_view if r["requirement"]["id"] == anchor["anchor_id"]), None,
            )
            if req_row is not None:
                label = req_row["requirement"]["text_reference"][:60]
                current_state = req_row["adjudication_state"]
                changed_since = any(
                    a["adjudicated_at"] > message["created_at"] for a in req_row["adjudication_history"]
                ) or any(
                    e["supersession"]["authorized_at"] > message["created_at"]
                    for e in req_row["revision_history"]
                )
        recent_focus_view.append({
            "anchor": anchor,
            "label": label,
            "current_state": current_state,
            "changed_since": changed_since,
            "created_at": message["created_at"],
            "case_id": message.get("case_id"),
        })

    # CLAUDE-P11: the system-health signal - is Archiosk generating useful
    # investigative hypotheses, not "how many Cases exist." Computed
    # unconditionally (like Needs Attention/Recent Focus) so it stays
    # reachable from inside a Case too, not just Project Home.
    investigation_quality_view = store.investigation_quality_rollup_for_project(workspace)

    # Visual pressure ("stable geometry, variable emphasis" - never
    # existence or position): a governed Requirement recedes to quieter
    # text ONLY when it is (a) settled - adjudicated at all, not still
    # Not Yet Assessed, (b) that settlement is old news, not new since
    # THIS reviewer's own last visit (previous_visit_at, above - the
    # same boundary since_last_visit already uses, not a second
    # invented time threshold), and (c) it isn't the object this
    # reviewer is personally still engaged with right now (recent_focus_
    # anchor_ids, below) - actively focused-on work never quiets down
    # just because its formal state happens to be settled. Every
    # Requirement still renders, in the same place, in the same order;
    # only its text token changes (see .pressure-quiet in main.css).
    recent_focus_anchor_ids = {row["anchor"]["anchor_id"] for row in recent_focus_view}
    for row in requirements_view:
        activity_timestamps = [
            a["adjudicated_at"] for a in row["adjudication_history"]
        ] + [
            e["supersession"]["authorized_at"] for e in row["revision_history"]
        ]
        latest_activity_at = max(activity_timestamps) if activity_timestamps else row["requirement"]["created_at"]
        is_settled = row["adjudication_state"] != REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED
        is_old_news = previous_visit_at is not None and latest_activity_at <= previous_visit_at
        is_currently_focused = row["requirement"]["id"] in recent_focus_anchor_ids
        row["quiet"] = is_settled and is_old_news and not is_currently_focused

    # Human discussion (ReviewThread/ReviewMessage/Attention), scoped to
    # whichever Case is active - same read/write boundary as everything
    # else on this page (a thread only ever appears here if its own
    # case_id equals active_case's id, so a Private Case's discussion is
    # exactly as invisible to a non-owner as its Findings already are).
    # Same open, not-yet-justified-to-fix ordering gap as findings_view
    # above: store.threads_for_case returns creation order, not (e.g.)
    # threads with a pending Attention first - confirmed here to be a
    # systemic characteristic of CaseWorkspaceStore's flat, append-only
    # lists, not an isolated oversight in findings_view alone.
    threads_view = []
    if active_case is not None:
        for thread in store.threads_for_case(workspace, active_case["id"]):
            messages = store.messages_for_thread(workspace, thread["id"])
            messages_by_id = {m["id"]: m for m in messages}
            attentions_view = [
                {
                    "attention": attention,
                    "about_message": messages_by_id.get(attention["message_id"]),
                    "response_message": messages_by_id.get(attention.get("responded_message_id")),
                }
                for attention in store.attentions_for_thread(workspace, thread["id"])
            ]
            threads_view.append({
                "thread": thread,
                "messages": messages,
                "attentions": attentions_view,
            })

    # Attention's `intended_actor` is free text in the domain model (see
    # Attention's own docstring - people/roles are not a closed
    # vocabulary), but a real registered-user list already exists and is
    # safe to offer as a convenience: it names no project, reveals no
    # Case's existence or visibility, only who is a registered account at
    # all - the "narrowest honest UI supported by the current data model"
    # rather than either a fabricated directory or a bare free-text box.
    known_usernames = sorted(u.username for u in User.query.all())

    # Accepted Knowledge drill-back: which Finding/Case it came from
    # (already-stored source_finding_id/source_case_id, just not
    # rendered before) and which Requirement(s), if any, currently cite
    # that same Finding as adjudication evidence (requirements_evidenced_
    # by_finding - the same evidence_finding_ids link, read in reverse).
    # Deliberately not Case-visibility-filtered here - AcceptedKnowledge
    # is already project-wide by the pre-existing design of Apply itself
    # (see the Accepted Knowledge panel's own long-standing copy above),
    # not a new decision made in this tranche.
    accepted_knowledge_view = []
    for item in reversed(store.knowledge_for_project(workspace)):
        source_case = next((c for c in workspace.cases if c["id"] == item.get("source_case_id")), None)
        accepted_knowledge_view.append({
            "item": item,
            "source_case_title": source_case["title"] if source_case else None,
            "linked_requirements": store.requirements_evidenced_by_finding(workspace, item.get("source_finding_id")),
        })

    # CLAUDE-P38 (OBS-02): a compact, project-wide rollup for the
    # Accepted Knowledge empty state - "0 accepted, but why" - reusing
    # claim_status (already on every raw Finding dict, no Case-scoped
    # join needed) rather than the heavier per-Case findings_view
    # resolution below, which exists to support review actions, not a
    # project-wide summary count.
    project_findings_applied_count = sum(1 for f in workspace.findings if f["claim_status"] == "applied")
    project_findings_awaiting_count = len(workspace.findings) - project_findings_applied_count

    return render_template(
        "case_workspace.html",
        document=document,
        workspace=workspace,
        visible_cases=visible_cases,
        active_case=active_case,
        needs_attention_view=needs_attention_view,
        findings_view=findings_view,
        focused_finding_id=focused_finding_id,
        applied_count=applied_count,
        awaiting_apply_count=awaiting_apply_count,
        project_id=project_id,
        reviewer_validation_states=REVIEWER_VALIDATION_STATES,
        dispositions=DISPOSITIONS,
        pending_rfi_finding_id=pending_rfi_finding_id,
        rfi_preview=rfi_preview,
        preview_finding_id=preview_finding_id,
        revision_notices=revision_notices,
        accepted_knowledge=accepted_knowledge_view,
        project_findings_applied_count=project_findings_applied_count,
        project_findings_awaiting_count=project_findings_awaiting_count,
        activities=store.activities_for_case(workspace, active_case["id"]) if active_case else [],
        unpromoted_requirement_items=unpromoted_requirement_items,
        requirements_view=requirements_view,
        compliance_rollup=compliance_rollup,
        revisited_requirements_count=revisited_requirements_count,
        adjudication_outcomes=REQUIREMENT_ADJUDICATION_OUTCOMES,
        recent_governance_events=recent_governance_events,
        history_total_count=history_total_count,
        temporal_obligations_view=temporal_obligations_view,
        source_milestones_view=source_milestones_view,
        briefing_deterministic=briefing_deterministic,
        briefing_stale=briefing_stale,
        briefing_ai_status=briefing_ai_status,
        briefing_ai_decision=briefing_ai_decision,
        briefing_generation_in_progress=briefing_generation_in_progress,
        briefing_has_evidence=briefing_has_evidence,
        rfi_drafts_view=rfi_drafts_view,
        recent_focus_view=recent_focus_view,
        threads_view=threads_view,
        known_usernames=known_usernames,
        resolution_outcomes=KNOWN_RESOLUTION_OUTCOMES,
        project_home_summary=project_home_summary,
        since_last_visit=since_last_visit,
        project_conversation_view=project_conversation_view,
        opened_snapshot_view=opened_snapshot_view,
        snapshot_compare_view=snapshot_compare_view,
        case_outcome_states=case_outcome_states,
        case_origin_kinds=case_origin_kinds,
        case_origin_autonomous=CASE_ORIGIN_AUTONOMOUS,
        case_outcome_options=CASE_OUTCOME_STATES,
        investigation_quality_view=investigation_quality_view,
        participants_view=store.participants_for_project(workspace),
        represented_party=represented_party,
        # CLAUDE-P29: gated by the project's locked operating_environment
        # once one is set -- a Client project should not be able to
        # register a design_builder participant and reason from their
        # position, which would defeat locking the project at all. Falls
        # back to the full open set for a legacy project with no
        # environment established yet (environment_capabilities.py's own
        # documented contract), so nothing pre-existing breaks.
        participant_role_options=allowed_participant_roles(workspace.operating_environment) or KNOWN_PARTICIPANT_ROLES,
        perspective_polarity_options=KNOWN_PERSPECTIVE_POLARITIES,
        operating_environment=workspace.operating_environment,
        operating_environment_label=OPERATING_ENVIRONMENT_LABELS.get(workspace.operating_environment),
        operating_environments=OPERATING_ENVIRONMENT_LABELS,
        # CLAUDE-P30: template-layer visibility only -- the routes
        # themselves (_require_capability) are the real enforcement,
        # never these two flags alone. See environment_capabilities.py's
        # "rfi_originate"/"rfi_respond" registry entries.
        can_originate_rfi=capability_availability("rfi_originate", workspace.operating_environment),
        can_respond_rfi=capability_availability("rfi_respond", workspace.operating_environment),
        # Unlike rfi_originate/rfi_respond/participant_registration, "go_no_go"
        # has no sensible ungated fallback for a legacy/unclassified project --
        # there is no vocabulary to validate against without a locked
        # environment (see decision_stages_for_environment, which raises for
        # None). So this flag additionally requires operating_environment to
        # be set, deliberately narrower than capability_availability's usual
        # "None means ungated" default.
        go_no_go_capability_available=(
            capability_availability("go_no_go", workspace.operating_environment)
            and workspace.operating_environment is not None
        ),
        go_no_go_assessments=store.go_no_go_assessments_for_project(workspace),
        go_no_go_decisions=GO_NO_GO_DECISIONS,
        go_no_go_stage_options=(
            decision_stages_for_environment(workspace.operating_environment)
            if workspace.operating_environment else ()
        ),
        # CLAUDE-P32: project-level access control display -- read-only
        # info plus the owner/grant/revoke forms case_workspace.html
        # shows only to the owner or an admin (is_admin already reaches
        # the template via app.py's own context processor).
        project_owner=workspace.owner,
        project_access_allow_list=workspace.access_allow_list,
        is_project_owner=(workspace.owner is not None and workspace.owner == _reviewer()),
    )


@workspace_bp.route("/projects/<project_id>/workspace/cases", methods=["POST"])
@login_required
def create_case(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    title = (request.form.get("title") or "").strip()
    objective = (request.form.get("objective") or "").strip()
    if not title:
        flash("A Case needs a title.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    case = store.create_case(workspace, title=title, objective=objective, created_by=_reviewer())

    _log().append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title, "visibility": case["visibility"]},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"]))


# -- Project Home: star, details, instructions, project-level Sources, Snapshot ----

@workspace_bp.route("/projects/<project_id>/workspace/star", methods=["POST"])
@login_required
def toggle_star(project_id):
    """Personal bookmark only - see CaseWorkspaceStore.set_starred. No
    governance meaning, no GovernanceLog event (Prompt 3 #3)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    store.set_starred(workspace, not workspace.starred)
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


def _project_briefing_ai_status(workspace) -> tuple[str, object]:
    """
    CLAUDE-P38-D2: the one place that turns a raw SecurityDecision into
    the three states this feature actually treats differently -
    "allow" (ALLOW/ALLOW_APPROVED_ROUTE - proceed automatically),
    "require_approval" (a real, distinct action: proceed only once a
    human explicitly confirms THIS request), and "denied" (ISOLATE/DENY
    - no action this feature can offer either way; both mean "cannot
    proceed", so they share a state, but the resolved decision/
    controlling_layer are still returned for an honest message, never
    collapsed into identical copy regardless of which one it was).
    Read-only - safe to call from a GET handler.
    """
    from services.security_policy import (
        ACTION_EXTERNAL_AI_REQUEST, DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE, DECISION_REQUIRE_APPROVAL,
    )

    decision = _evaluate_security_action(workspace, ACTION_EXTERNAL_AI_REQUEST)
    if decision.decision in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        return "allow", decision
    if decision.decision == DECISION_REQUIRE_APPROVAL:
        return "require_approval", decision
    return "denied", decision


@workspace_bp.route("/projects/<project_id>/workspace/briefing/generate", methods=["POST"])
@login_required
def generate_project_briefing_route(project_id):
    """
    CLAUDE-P38-D2: called automatically (via the auto-submitting
    "Preparing your Project Briefing..." interstitial - see
    show_workspace/preparing_project_briefing below) when policy allows
    without approval, and explicitly otherwise (an approval click when
    REQUIRE_APPROVAL, or a manual Regenerate). Policy-gated through the
    same ACTION_EXTERNAL_AI_REQUEST resolver every other real external-
    AI call site in this app uses - this governed action is never
    bypassed, only the UX around when this route gets called changed.

    `confirm=once` is this feature's own version of the Approval Gate
    vocabulary CLAUDE.md documents for other consequential actions
    (Apply, Issue RFI) - required only when the resolved decision is
    REQUIRE_APPROVAL, so a human explicitly authorizes THIS specific
    request rather than the route silently proceeding merely because
    the org-wide policy doesn't outright deny it.
    """
    document, store, workspace = _load_workspace_or_404(project_id)

    status, decision = _project_briefing_ai_status(workspace)
    if status == "denied":
        flash(
            f"A project briefing cannot be generated: external AI is not permitted by "
            f"this project's security policy (controlling layer: {decision.controlling_layer}).",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id))
    if status == "require_approval" and (request.form.get("confirm") or "").strip() != "once":
        flash(
            f"AI Project Briefing awaits approval (controlling layer: {decision.controlling_layer}) "
            f"- {decision.reason} Use the approval action to proceed.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    # CLAUDE-P38-D2: duplicate-call/idempotency guard - a refresh, a
    # second reviewer, or the interstitial's own auto-submit firing
    # twice must never start a second real, billed call while one is
    # already in flight.
    if store.generation_in_progress_for(workspace):
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    store.start_project_briefing_generation(workspace, actor=_reviewer())

    from services.project_briefing import generate_project_briefing

    result = generate_project_briefing(
        document_filename=document.filename,
        candidate_requirements=[{"text": r.text, "category": r.category} for r in document.requirements],
        governed_requirements=list(workspace.requirements),
        milestones=list(document.milestones),
    )
    if not result.ran:
        # CLAUDE-P40-B (3.2): no flash here anymore - the persistent
        # inline "Generation failed - Retry" state (case_workspace.html,
        # driven by workspace.project_briefing_last_failure_reason,
        # set two lines below) already tells the reviewer the same
        # thing with a clear recovery action. A flash of the identical
        # message on top of that, confirmed via a real product-owner
        # walkthrough, read as the same failure reported twice
        # ("Project briefing could not be generated: Request timed out
        # after 30s." immediately above "Generation failed. Request
        # timed out after 30s.") for no added information.
        workspace = store.get(project_id)
        store.record_project_briefing_failure(workspace, reason=result.skipped_reason or "Unknown failure.")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    from dataclasses import asdict

    workspace = store.get(project_id)  # re-fetch: version may have advanced since load
    store.set_project_briefing(
        workspace, briefing=asdict(result), source_signature=store.source_signature_for(workspace),
        actor=_reviewer(), governance_log=_log(),
    )
    flash("Project briefing generated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/briefing/preparing")
@login_required
def preparing_project_briefing(project_id):
    """
    CLAUDE-P38-D2: the "Preparing your Project Briefing..." interstitial
    - a real, rendered, visible page (per this stage's own "a page that
    opens empty and waits for a hidden user action is not acceptable"
    instruction), not a background job. Reached right after ingestion
    (services/ingestion.py redirects here instead of straight to the
    workspace, only when there's real work for it to do) and auto-
    submits a POST to generate_project_briefing_route via a small
    inline script - synchronous generation, a visible waiting state
    instead of a blocking upload request. This is the ONLY safe
    lightweight option evaluated (see this stage's own final report,
    Section B): background-worker infrastructure fails tools/
    dependency_fit.py's own established constraint outright (no queue/
    worker infra anywhere in this deployment's process model), and this
    app has no async runtime either - a real Gunicorn worker recycling
    mid-thread would leave an unsupervised, unrecoverable job with no
    process left to finish or clean it up.
    """
    document, store, workspace = _load_workspace_or_404(project_id)
    status, _decision = _project_briefing_ai_status(workspace)

    # "Is there anything to brief from" is evidence-presence, not
    # workspace.sources specifically - the originally-ingested document
    # itself never gets a Source record (only later manually-added
    # material does; see Source/add_source), so gating on
    # workspace.sources alone would make this interstitial skip straight
    # past automatic generation on literally every fresh upload, the
    # opposite of what this stage requires. document.requirements/
    # milestones is what deterministic_sections and the AI prompt itself
    # actually consume - that's the real signal.
    has_evidence = bool(document.requirements or document.milestones or workspace.sources)

    # Nothing to prepare - go straight to the workspace rather than
    # showing an interstitial for a state it can't do anything about.
    # A prior failure also skips the interstitial - the workspace's own
    # "Generation failed - Retry" state is the honest next step, not a
    # second silent automatic attempt (this stage's own "do not
    # regenerate when a previous generation failed... without user
    # intervention" rule).
    if (
        workspace.project_briefing is not None
        or status != "allow"
        or not has_evidence
        or workspace.project_briefing_last_failure_reason is not None
    ):
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    return render_template("preparing_project_briefing.html", project_id=project_id, document=document)


@workspace_bp.route("/projects/<project_id>/workspace/details", methods=["POST"])
@login_required
def edit_project_details(project_id):
    """Overflow menu -> Edit Project Details (Prompt 3 #3) - presentation
    only, see CaseWorkspaceStore.set_project_details.

    CLAUDE-P40-B (3.1): a real gap found during this stage's own
    investigation - renaming here never checked uniqueness at all, even
    though the identical name is rejected outright at upload time
    (services.ingestion._reject_if_name_taken). A rename could silently
    make two Projects collide on the same effective display name.
    Checked against the EFFECTIVE name the rename would produce (a
    blank display_title falls back to the filename, same as
    services.ingestion._display_name_of already does), not the raw
    form value.
    """
    document, store, workspace = _load_workspace_or_404(project_id)
    new_display_title = (request.form.get("display_title") or "").strip()
    effective_name = new_display_title or document.filename

    try:
        reject_if_display_name_taken(current_app, effective_name, exclude_project_id=project_id)
    except UploadError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    store.set_project_details(
        workspace,
        actor=_reviewer(),
        display_title=new_display_title,
        display_description=(request.form.get("display_description") or "").strip(),
        governance_log=_log(),
    )
    flash("Project details updated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/instructions", methods=["POST"])
@login_required
def edit_operating_instructions(project_id):
    """Project Instructions + (Prompt 3 #7) - human guidance explicitly
    subordinate to governance. See
    CaseWorkspaceStore.set_operating_instructions."""
    _, store, workspace = _load_workspace_or_404(project_id)
    store.set_operating_instructions(
        workspace,
        text=(request.form.get("instructions") or "").strip(),
        actor=_reviewer(),
        governance_log=_log(),
        actor_role=session.get("role"),
    )
    flash("Project Operating Instructions updated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/classify-environment", methods=["POST"])
@admin_required
def classify_operating_environment(project_id):
    """
    CLAUDE-P29: one-time establishment of Project Operating Environment
    for a legacy project (created before this field existed) -- NOT a
    Client<->Proponent conversion route. See CaseWorkspaceStore.
    set_operating_environment's own docstring: this calls the exact
    same single gate creation uses, which refuses outright if the
    project already has a non-None environment -- so this route cannot
    be used to change an already-classified project's environment
    either, new or legacy. Admin-only, matching the same authority
    level as original project creation (routes/portal.py's /upload is
    also @admin_required). CLAUDE-P32 later added a real project-level
    "owner" concept (see set_project_owner/classify_project_owner
    below) -- this route's own authority choice predates that and is
    unaffected by it; both remain admin-only for the same reason.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    operating_environment = (request.form.get("operating_environment") or "").strip()
    if not is_valid_operating_environment(operating_environment):
        flash("Select a valid project operating environment.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    try:
        store.set_operating_environment(
            workspace, operating_environment, actor=_reviewer(), governance_log=_log(),
        )
    except OperatingEnvironmentAlreadySetError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    flash(
        f"Project operating environment established: "
        f"{OPERATING_ENVIRONMENT_LABELS[operating_environment]}.", "success",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/access/owner", methods=["POST"])
@admin_required
def set_project_owner_route(project_id):
    """
    CLAUDE-P32: (re-)establishes a project's owner -- admin-only, unlike
    Case-level ownership which is set once at creation and never
    reassigned. This IS reassignable (see ProjectWorkspace.owner's own
    comment for why: a wrong backfill inference, or a departing team
    member, must be recoverable) but only ever by an admin, never by the
    current owner or an allow-listed user. Legacy projects reach this
    same route via the "not yet established" panel in case_workspace.html
    -- there is no separate "classify" route, unlike operating_environment,
    because reassignment is intentionally allowed here.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    new_owner = (request.form.get("owner") or "").strip()
    if not new_owner:
        flash("A username is required to set the project owner.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))
    if new_owner not in {u.username for u in User.query.all()}:
        flash(f"{new_owner!r} is not a registered account.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    store.set_project_owner(workspace, owner=new_owner, actor=_reviewer(), governance_log=_log())
    flash(f"Project owner set to {new_owner!r}.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/access/grant", methods=["POST"])
@login_required
def grant_project_access_route(project_id):
    """CLAUDE-P32: owner-or-admin authority, enforced inside
    CaseWorkspaceStore.grant_project_access itself (the same
    owner-or-admin pattern archive_case/derive_case already
    established) -- reachable by any authenticated user so a non-owner,
    non-admin request produces the store's own real error message
    rather than being silently hidden by a route-level role check that
    would just duplicate that logic."""
    _, store, workspace = _load_workspace_or_404(project_id)

    username = (request.form.get("username") or "").strip()
    if username and username not in {u.username for u in User.query.all()}:
        flash(f"{username!r} is not a registered account.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    try:
        store.grant_project_access(
            workspace, username=username, actor=_reviewer(), actor_role=session.get("role") or "",
            governance_log=_log(),
        )
        flash(f"Access granted to {username!r}.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/access/revoke", methods=["POST"])
@login_required
def revoke_project_access_route(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    username = (request.form.get("username") or "").strip()
    try:
        store.revoke_project_access(
            workspace, username=username, actor=_reviewer(), actor_role=session.get("role") or "",
            governance_log=_log(),
        )
        flash(f"Access revoked for {username!r}.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/sources/document", methods=["POST"])
@login_required
def add_document_source(project_id):
    """
    Project Sources + -> Add Documents (Prompt 3 #8). Project-scoped, not
    Case-scoped: CaseWorkspaceStore.add_source itself takes no case_id -
    a Case draws on Sources, it does not own them.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    file_storage = request.files.get("document")
    if file_storage is None or not file_storage.filename:
        flash("Choose a document to add as a Project Source.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        flash(f"Unsupported document format '{ext}'.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(file_storage.read())

    store.add_source(
        workspace,
        name=safe_name,
        file_path=str(stored_path),
        kind=SOURCE_KIND_PROJECT_DOCUMENT,
        actor=_reviewer(),
        governance_log=_log(),
    )
    flash("Document added as a Project Source.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/sources/text-record", methods=["POST"])
@login_required
def add_text_record_source(project_id):
    """
    Project Sources + -> Add Text Record (Prompt 3 #8): a meeting note,
    site observation, telephone instruction, or other textual evidence,
    made a first-class provenance-bearing Project Source rather than
    disposable chat text (Prompt 3 #10).
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    if not title or not content:
        flash("A Text Record needs both a title and content.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(title) or "text-record"
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}.txt"
    stored_path.write_text(content, encoding="utf-8")

    store.add_source(
        workspace,
        name=title,
        file_path=str(stored_path),
        kind=SOURCE_KIND_TEXT_RECORD,
        actor=_reviewer(),
        governance_log=_log(),
    )
    flash("Text Record added as a Project Source.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/snapshots", methods=["POST"])
@login_required
def create_project_snapshot(project_id):
    """Active Work -> Create Snapshot (Prompt 3 #9) - freezes a governed
    reference to current Project state. See
    CaseWorkspaceStore.create_snapshot (existing, unmodified)."""
    _, store, workspace = _load_workspace_or_404(project_id)

    label = (request.form.get("label") or "").strip()
    if not label:
        flash("A Snapshot needs a label.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    store.create_snapshot(
        workspace,
        label=label,
        created_by=_reviewer(),
        note=(request.form.get("note") or "").strip() or None,
        governance_log=_log(),
    )
    flash("Snapshot created.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/share", methods=["POST"])
@login_required
def share_case(project_id, case_id):
    """Explicit, human-authorized Private -> Shared transition only -
    see CaseWorkspaceStore.share_case. The machine never performs this;
    this route only ever forwards a real, authenticated human's own
    request to share their own Case."""
    _, store, workspace = _load_workspace_or_404(project_id)

    try:
        store.share_case(workspace, case_id=case_id, actor=_reviewer(), governance_log=_log())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Case shared.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/retract", methods=["POST"])
@login_required
def retract_case(project_id, case_id):
    """Explicit, human-authorized Shared -> Private retraction, only
    before the collaboration threshold - see
    CaseWorkspaceStore.retract_case_to_private. Rejected outright by the
    store layer once the Case is Collaborative (Constitutional Invariant
    12); this route does not attempt its own separate check, so there is
    exactly one place irreversibility is enforced, not two that could
    drift apart."""
    _, store, workspace = _load_workspace_or_404(project_id)

    try:
        store.retract_case_to_private(workspace, case_id=case_id, actor=_reviewer(), governance_log=_log())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Case retracted to private.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/archive", methods=["POST"])
@login_required
def archive_case(project_id, case_id):
    """Terminal/frozen Case status - see CaseWorkspaceStore.archive_case.
    Owner or admin-role only; the machine never performs this. Passes the
    real session role through so the store layer's owner-or-admin
    authority check (the narrowest existing legitimate pattern - no new
    role architecture) can recognize a Design Manager/admin override
    without this route inventing its own separate authorization logic."""
    _, store, workspace = _load_workspace_or_404(project_id)

    try:
        store.archive_case(
            workspace, case_id=case_id, actor=_reviewer(),
            actor_role=session.get("role"), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Case archived.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/derive", methods=["POST"])
@login_required
def derive_case(project_id, case_id):
    """Create a new active Case derived from an archived one - see
    CaseWorkspaceStore.derive_case_from_archive. Owner or admin-role only,
    same narrow authority pattern as archive_case; the machine never
    performs this. `case_id` here is the ARCHIVED source Case; on success
    the user is redirected into the newly created derived Case, not the
    archived one, since that new Case is where continued work happens."""
    _, store, workspace = _load_workspace_or_404(project_id)

    try:
        new_case = store.derive_case_from_archive(
            workspace, archived_case_id=case_id, actor=_reviewer(),
            actor_role=session.get("role"), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("New active Case derived from archive.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=new_case["id"]))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/outcome", methods=["POST"])
@login_required
def record_case_outcome_route(project_id, case_id):
    """
    CLAUDE-P11: a human's verdict on whether this Case's own hypothesis
    held up - see CaseWorkspaceStore.record_case_outcome and CaseOutcome's
    own docstring on why this is the one place that verdict is ever
    recorded, and why it is never machine-populated.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    outcome = (request.form.get("outcome") or "").strip()
    reasoning = (request.form.get("reasoning") or "").strip()
    duplicate_of_case_id = (request.form.get("duplicate_of_case_id") or "").strip() or None

    try:
        store.record_case_outcome(
            workspace, case_id=case_id, outcome=outcome, reasoning=reasoning,
            recorded_by=_reviewer(), duplicate_of_case_id=duplicate_of_case_id,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Investigation outcome recorded.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/adopt-finding", methods=["POST"])
@login_required
def adopt_finding(project_id, case_id):
    """Selectively carry one historical Finding from its archived Case
    forward into `case_id` (the derived active Case) - see
    CaseWorkspaceStore.adopt_finding_into_case. Owner or admin-role only
    on the TARGET Case; the machine never performs this. Nothing is
    carried forward automatically - this route only ever acts on a
    specific `finding_id` an authorized human explicitly submitted."""
    _, store, workspace = _load_workspace_or_404(project_id)
    finding_id = request.form.get("finding_id", "").strip()

    try:
        store.adopt_finding_into_case(
            workspace, source_finding_id=finding_id, target_case_id=case_id,
            actor=_reviewer(), actor_role=session.get("role"), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Finding carried forward for renewed review.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/adopt-message", methods=["POST"])
@login_required
def adopt_review_message(project_id, case_id):
    """Selectively carry one historical review comment from its archived
    Case forward into `case_id` (the derived active Case) - see
    CaseWorkspaceStore.adopt_review_message_into_case. Owner or
    admin-role only on the TARGET Case; the machine never performs this.
    The original commenter is never recorded as the author of the new
    active item - see the store method's own docstring."""
    _, store, workspace = _load_workspace_or_404(project_id)
    message_id = request.form.get("message_id", "").strip()
    note = request.form.get("note", "").strip() or None

    try:
        store.adopt_review_message_into_case(
            workspace, source_message_id=message_id, target_case_id=case_id,
            actor=_reviewer(), actor_role=session.get("role"), note=note, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Review comment carried forward for renewed consideration.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


# -- human discussion: ReviewThread / ReviewMessage / Attention --------------------

@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/threads", methods=["POST"])
@login_required
def create_thread(project_id, case_id):
    """Start a new discussion on the active Case, or optionally anchored
    to one of its Findings - see CaseWorkspaceStore.create_review_thread.
    Anyone who can see this Case may start a discussion on it (the same
    boundary reads already enforce, not a stricter owner-only rule -
    ordinary collaborative participation is not a Case-lifecycle
    transition the way Archive/Derive/Adopt are)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    title = (request.form.get("title") or "").strip()
    if not title:
        flash("A discussion needs a title.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    related_finding_id = request.form.get("related_finding_id") or None
    if related_finding_id:
        anchor_type, anchor_id = OBJECT_KIND_FINDING, related_finding_id
    else:
        anchor_type, anchor_id = OBJECT_KIND_CASE, case_id

    try:
        thread = store.create_review_thread(
            workspace, title=title, anchor_type=anchor_type, anchor_id=anchor_id,
            created_by=_reviewer(), case_id=case_id, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    opening_text = (request.form.get("text") or "").strip()
    if opening_text:
        try:
            store.add_review_message(
                workspace, thread_id=thread["id"], origin=MESSAGE_ORIGIN_HUMAN,
                actor=_reviewer(), message_type="observation", text=opening_text,
                related_finding_id=related_finding_id, governance_log=_log(),
            )
        except CaseWorkspaceError as exc:
            flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/temporal-obligations", methods=["POST"])
@login_required
def create_temporal_obligation_route(project_id, case_id):
    """
    First route wiring for CaseWorkspaceStore.create_temporal_obligation -
    previously fully implemented and tested but never reachable through
    the UI at all. Scoped to Case-originated obligations only for this
    first pass (origin_type=case, origin_id=case_id, matching the
    class's own primary documented example - "RFI response dates,
    submittal review periods"); project-level obligations with no
    originating Case (the class docstring's other documented example,
    a project-wide risk-reassessment date) are a real, valid future
    extension, deliberately not built here - scope kept to what has
    a clear, unambiguous origin.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    title = (request.form.get("title") or "").strip()
    required_action = (request.form.get("required_action") or "").strip()
    accepted_date = (request.form.get("accepted_date") or "").strip()
    responsible_actor = (request.form.get("responsible_actor") or "").strip() or None
    if not title or not required_action or not accepted_date:
        flash("A key date needs a title, the action required, and a date.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        datetime.fromisoformat(accepted_date)
    except ValueError:
        flash("That date isn't valid.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    store.create_temporal_obligation(
        workspace, title=title, origin_type=OBJECT_KIND_CASE, origin_id=case_id,
        required_action=required_action, accepted_date=accepted_date,
        created_by=_reviewer(), case_id=case_id, responsible_actor=responsible_actor,
    )
    _log().append(
        project_id=project_id, event_type="temporal_obligation_created",
        actor=_reviewer(), role=session.get("role") or "unspecified",
        payload={"case_id": case_id, "title": title, "accepted_date": accepted_date},
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/threads/<thread_id>/messages", methods=["POST"])
@login_required
def add_thread_message(project_id, thread_id):
    """Reply within an existing discussion - always origin=human, since
    this form only exists for a real authenticated person to use; there
    is no machine caller of this route. See
    CaseWorkspaceStore.add_review_message for the collaboration-
    threshold crossing this triggers automatically on a non-owner's
    first qualifying contribution to a SHARED Case - that logic is not
    reproduced here, only invoked."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _thread_case_id(workspace, thread_id)
    _require_visible_case(store, workspace, case_id)

    text = (request.form.get("text") or "").strip()
    if not text:
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.add_review_message(
            workspace, thread_id=thread_id, origin=MESSAGE_ORIGIN_HUMAN,
            actor=_reviewer(), message_type="response", text=text,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/threads/<thread_id>/attention", methods=["POST"])
@login_required
def request_thread_attention(project_id, thread_id):
    """The equivalent of "please look at this" against one specific
    message - see CaseWorkspaceStore.request_attention. Deliberately a
    governed in-project request only: no email, push notification, or
    presence/availability tracking exists anywhere in this codebase, and
    none is added here."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _thread_case_id(workspace, thread_id)
    _require_visible_case(store, workspace, case_id)

    message_id = request.form.get("message_id", "").strip()
    intended_actor = (request.form.get("intended_actor") or "").strip()
    if not message_id or not intended_actor:
        flash("Choose a message and who should attend to it.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.request_attention(
            workspace, thread_id=thread_id, message_id=message_id,
            intended_actor=intended_actor, created_by=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/attentions/<attention_id>/respond", methods=["POST"])
@login_required
def respond_to_attention_route(project_id, attention_id):
    """Completes the existing Attention loop - see
    CaseWorkspaceStore.respond_to_attention. The response IS an existing
    ReviewMessage already posted in the thread (chosen by the responder,
    never free text captured here) - Attention has no separate
    acknowledgment-only path built in the domain model (`acknowledged_at`/
    ATTENTION_STATUS_ACKNOWLEDGED exist in the vocabulary but no method
    ever sets them), so this route only ever exposes the one capability
    that's actually implemented: marking an Attention responded against
    a real message."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _attention_case_id(workspace, attention_id)
    _require_visible_case(store, workspace, case_id)

    response_message_id = request.form.get("response_message_id", "").strip()
    if not response_message_id:
        flash("Choose which message answers this attention request.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.respond_to_attention(workspace, attention_id=attention_id, response_message_id=response_message_id)
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="attention_responded",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"attention_id": attention_id, "response_message_id": response_message_id},
    )

    flash("Attention marked as responded.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/threads/<thread_id>/resolve", methods=["POST"])
@login_required
def resolve_thread(project_id, thread_id):
    """See CaseWorkspaceStore.resolve_review_thread - additive only,
    never rewrites or removes a single existing message. Unresolved
    discussion is never required to be resolved for any reason other
    than an explicit human choice to do so here."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _thread_case_id(workspace, thread_id)
    _require_visible_case(store, workspace, case_id)

    resolution_outcome = request.form.get("resolution_outcome", "").strip()
    summary = (request.form.get("summary") or "").strip()
    if not resolution_outcome or not summary:
        flash("A resolution needs both an outcome and a summary.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.resolve_review_thread(
            workspace, thread_id=thread_id, resolution_outcome=resolution_outcome,
            summary=summary, resolved_by=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/threads/<thread_id>/reopen", methods=["POST"])
@login_required
def reopen_thread(project_id, thread_id):
    """See CaseWorkspaceStore.reopen_review_thread - the prior resolution
    is pushed onto resolution_history, never erased."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _thread_case_id(workspace, thread_id)
    _require_visible_case(store, workspace, case_id)

    reason = (request.form.get("reason") or "").strip()
    if not reason:
        flash("Reopening a resolved discussion needs a reason.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.reopen_review_thread(
            workspace, thread_id=thread_id, reason=reason, actor=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/sources", methods=["POST"])
@login_required
def add_drawing_source(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    file_storage = request.files.get("drawing")
    if file_storage is None or not file_storage.filename:
        flash("Choose an image file to add as a drawing Source.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_DRAWING_EXTENSIONS:
        flash(
            f"Unsupported drawing format '{ext}'. Use PNG or JPG for this prototype.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)

    safe_name = secure_filename(file_storage.filename)
    raw_bytes = file_storage.read()

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            width, height = probe.size
    except OSError:
        flash("That file could not be read as an image.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    # Prompt 5 #7 fix: "a Source is not its filename" - the ORIGINAL
    # filename is kept only as the display `name`; the on-disk path uses
    # an opaque prefix so two uploads sharing a filename in the same
    # Project can never silently overwrite each other's binary (a real
    # gap identified during Prompt 4's multi-agent verification pass).
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(raw_bytes)

    source = store.add_drawing_source(
        workspace,
        name=safe_name,
        file_path=str(stored_path),
        width=width,
        height=height,
    )

    try:
        store.attach_source_to_case(workspace, case_id, source["id"])
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/file")
@login_required
def source_file(project_id, source_id):
    """
    Opens/downloads a Source's own stored file - the direct answer to
    "where is the document I uploaded" (pagescape correction #10). A
    read operation, not a write. Sources are project-scoped, not
    Case-scoped (see kernel-object-model.md's "Case"/"Source" entries -
    a Case draws on Sources, it does not own them), so this is gated on
    the same login_required boundary as the rest of the Case Workspace,
    not a per-Case visibility check. 404s honestly (not a fabricated
    empty file) when the Source has no stored file at all - true for
    every legacy-ingested document from before services/ingestion.py
    started persisting the original upload.
    """
    _, _, workspace = _load_workspace_or_404(project_id)

    source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if source is None or not source.get("file_path"):
        abort(404)

    file_path = Path(source["file_path"])
    if not file_path.exists():
        abort(404)

    mimetype, _ = mimetypes.guess_type(source["name"])
    return send_file(
        file_path,
        mimetype=mimetype or "application/octet-stream",
        as_attachment=False,
        download_name=source["name"],
    )


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/revise", methods=["POST"])
@login_required
def revise_source(project_id, source_id):
    """Registers a new revision of an existing drawing Source. Never
    replaces the old Source or any Artifact/Finding derived from it -
    only adds a visible 'Reference update detected' notice per affected
    Case (Prompt 4 #13). Gated behind the Approval Gate since it's a
    governance-affecting action (it can surface findings as possibly
    stale)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = request.form.get("case_id")

    gate = _require_approval(
        "source_revision",
        "Register a new revision of this drawing Source. The original Source "
        "and every Finding/Artifact derived from it will be preserved unchanged; "
        "a Reference Update notice will be added to this Case instead.",
        project_id,
        case_id,
    )
    if gate is not None:
        return gate

    file_storage = request.files.get("drawing")
    if file_storage is None or not file_storage.filename:
        flash("Choose an image file for the new revision.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    raw_bytes = file_storage.read()

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            width, height = probe.size
    except OSError:
        flash("That file could not be read as an image.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(raw_bytes)

    predecessor_version = workspace.version
    try:
        new_source, notices, supersession = store.register_source_revision(
            workspace,
            old_source_id=source_id,
            name=safe_name,
            file_path=str(stored_path),
            width=width,
            height=height,
            actor=_reviewer(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="source_revised",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"old_source_id": source_id, "new_source_id": new_source["id"]},
        state_predecessor_version=predecessor_version,
        state_successor_version=workspace.version,
        authority_class="approval_gate:source_revision",
        correlation_id=supersession["id"],
    )

    flash(
        f"New revision registered as a separate Source. {len(notices)} Case(s) "
        "now show a Reference Update notice - nothing was silently replaced.",
        "success",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


def _run_conversation_turn(
    project_id: str, store: CaseWorkspaceStore, workspace, case: Optional[dict], text: str,
    anchor: Optional[dict] = None,
) -> None:
    """
    Posts a human message (into `case`'s conversation, or
    workspace.project_conversation if `case` is None), interprets it
    (Analysis/focus/compare/RFI-intent/correction via
    services.conversation_interpreter.interpret_message), and posts the
    resulting system reply. The shared turn logic behind an existing
    Case's composer (post_message), Project Home's central composer
    (quick_start - creates a Case first for anything that isn't a plain
    question, per CLAUDE-P40-B 3.5; still called with case=None for a
    plain question, same as discuss_object), and a project-level
    aperture with no Case at all (discuss_object) - the same
    conversational entry point, reached from three places.

    `anchor` (Anchor shape - anchor_type/anchor_id/source_id/location/
    description) records what the sender was actually looking at,
    independent of which conversation this lands in - see
    ConversationMessage's own docstring. Only ever set on the human
    message; the system's reply isn't "about" anything itself, it's a
    response to one.
    """
    case_id = case["id"] if case is not None else None
    human_message = store.add_message(
        workspace, case_id, role="human", text=text, anchor=anchor, actor=_reviewer(),
    )

    artifacts_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_artifacts"
    focused_finding_id = session.get(f"focused_finding:{project_id}")

    result = interpret_message(
        text=text,
        workspace=workspace,
        case=case,
        store=store,
        artifacts_dir=artifacts_dir,
        reviewer=_reviewer(),
        focused_finding_id=focused_finding_id,
        triggering_message_id=human_message["id"],
        anchor=anchor,
        governance_log=_log(),
    )

    store.add_message(
        workspace,
        case_id,
        role="system",
        text=result.reply_text,
        action_taken=result.action_taken,
        grounded_in=result.grounded_in,
    )

    if result.focused_finding_id is not None:
        session[f"focused_finding:{project_id}"] = result.focused_finding_id

    # Prompt 7: give the analysis its own event in the shared provenance
    # envelope, distinct from the AnalysisRun.trigger recorded on the
    # domain object itself (Prompt 6 #5 - event != domain object). Only
    # logged when an Analysis actually ran; every other conversational
    # action (focus, compare, correction, RFI intent) already has its own
    # honest action_taken label without needing a governance event here.
    if result.action_taken.startswith("analysis:"):
        analysis_id = result.action_taken.split(":", 1)[1]
        _log().append(
            project_id=project_id,
            event_type="analysis_started",
            actor=_reviewer(),
            role=session.get("role") or "unspecified",
            payload={"case_id": case_id, "analysis_id": analysis_id},
            trigger={
                "trigger_type": "user_initiated",
                "trigger_reference_type": "conversation_message",
                "trigger_reference_id": human_message["id"],
            },
            correlation_id=analysis_id,
        )


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/messages", methods=["POST"])
@login_required
def post_message(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None:
        abort(404)

    text = (request.form.get("text") or "").strip()
    if not text:
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _run_conversation_turn(project_id, store, workspace, case, text)

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/quick-start", methods=["POST"])
@login_required
def quick_start(project_id):
    """
    Project Home's central composer (Prompt 3 #4): "What are we working
    on?" Creates a new Case - "New Working Context / Investigation Entry"
    in Prompt 3 #19's Claude<->BEEHIVE mapping - titled from the user's
    own opening text, using the same CaseWorkspaceStore.create_case every
    other Case-creation path already uses, then runs the same
    conversation turn as an existing Case's composer
    (_run_conversation_turn) so the user's actual request becomes the new
    Case's first message rather than being discarded.

    CLAUDE-P40-B (3.5): EXCEPT when the text is a plain factual question
    (_looks_like_project_question - the same heuristic
    workspace.discuss_object's own reply-routing already trusts) - a
    real product-owner walkthrough found a simple lookup ("What is the
    name of this document?") typed into this composer silently created
    a whole new formal Investigation to hold it. This was already a
    named, open concern in ConversationMessage's own docstring ("forcing
    one into existence just to hold a message is exactly the surprise
    quick_start currently causes"). A question routes through the same
    case=None project-level conversation workspace.discuss_object uses
    instead - no Case, same real grounded-Q&A answer. Anything that
    doesn't read as a plain question (a real "start work" request, an
    "Analyze...", "Compare...", etc.) is completely unaffected - still
    creates a Case exactly as before.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Describe what you want to work on to start.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    if _looks_like_project_question(text.lower()):
        _run_conversation_turn(project_id, store, workspace, None, text)
        return redirect(url_for("workspace.show_workspace", project_id=project_id) + "#project-conversation")

    title = text if len(text) <= 80 else text[:77] + "..."
    case = store.create_case(workspace, title=title, objective="", created_by=_reviewer())

    _log().append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title, "visibility": case["visibility"]},
    )

    _run_conversation_turn(project_id, store, workspace, case, text)

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"]))


@workspace_bp.route("/projects/<project_id>/workspace/discuss", methods=["POST"])
@login_required
def discuss_object(project_id):
    """
    A project-level conversational aperture (no Case): the reviewer was
    looking at some governed, project-level object - a Requirement today,
    others later - and starts talking about it without first opening an
    Investigation. Posts into workspace.project_conversation (case=None,
    via the same _run_conversation_turn every other composer uses) with
    an Anchor naming what was in view, so the reply and everything
    downstream can honestly refer back to it - see ConversationMessage's
    own docstring on why this is a second list, not a migration.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    text = (request.form.get("text") or "").strip()
    if not text:
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    anchor_type = (request.form.get("anchor_type") or "").strip()
    anchor_id = (request.form.get("anchor_id") or "").strip()
    anchor = None
    if anchor_type and anchor_id:
        anchor = asdict(Anchor(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            description=(request.form.get("anchor_description") or None),
        ))

    _run_conversation_turn(project_id, store, workspace, None, text, anchor=anchor)

    # CLAUDE-P40-B (3.5): without a fragment, a plain redirect lands the
    # reviewer at the top of Project Home with no indication a reply
    # exists or where to find it - Project Conversation is collapsed by
    # default. The #project-conversation fragment (real html_id, added
    # in Batch A) makes the browser scroll there AND triggers the
    # already-built auto-open-on-anchor script, the same mechanism
    # Batch A's "View all" links now rely on - not a new destination-
    # tracking system, the same one used twice.
    return redirect(url_for("workspace.show_workspace", project_id=project_id) + "#project-conversation")


@workspace_bp.route("/projects/<project_id>/workspace/apertures/<message_id>/start-investigation", methods=["POST"])
@login_required
def start_investigation_from_aperture(project_id, message_id):
    """
    The "contextual aperture -> Conversation -> Investigation" escalation:
    a project-level message interpret_message honestly declined
    (action_taken="needs_case:<this message's id>") because no
    Investigation was open when a Case-shaped action (Analyze/evidence/
    Compare/correction) was recognized. Rather than silently creating a
    Case at message time, the decline itself carries the offer; this is
    what happens when the reviewer accepts it - start a real Case,
    titled from what they were looking at, and re-run their own original
    text (with its Anchor still attached) as that Case's first message,
    so the Case-bound action they actually asked for can now really run.
    The original project-level message is left exactly as it was -
    append-only, like every other record here - not deleted or moved;
    store.recent_anchors_for will simply prefer this newer, Case-attached
    one once it exists (same anchor, later timestamp).
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    message = next((m for m in workspace.project_conversation if m["id"] == message_id), None)
    if message is None:
        abort(404)

    anchor = message.get("anchor")
    title_source = (anchor or {}).get("description") or message["text"]
    title = title_source if len(title_source) <= 80 else title_source[:77] + "..."
    case = store.create_case(workspace, title=title, objective="", created_by=_reviewer())

    _log().append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title, "visibility": case["visibility"]},
    )

    _run_conversation_turn(project_id, store, workspace, case, message["text"], anchor=anchor)

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"]))


@workspace_bp.route("/projects/<project_id>/workspace/findings/<finding_id>/validate", methods=["POST"])
@login_required
def validate_finding(project_id, finding_id):
    """Records a Reviewer Validation (Correct/Incorrect/Partial/Needs
    Evidence/Not Applicable) - distinct from Disposition, see
    /disposition below."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _finding_case_id(workspace, finding_id)
    _require_visible_case(store, workspace, case_id)

    validation = request.form.get("validation")
    correction_note = request.form.get("correction_note") or None

    try:
        store.record_reviewer_validation(
            workspace,
            finding_id=finding_id,
            validation=validation,
            reviewer=_reviewer(),
            correction_note=correction_note,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="finding_reviewed",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"finding_id": finding_id, "reviewer_validation": validation},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/findings/<finding_id>/disposition", methods=["POST"])
@login_required
def set_disposition(project_id, finding_id):
    """Records a Disposition (Confirmed/Rejected/Deferred/Known Pending
    Acceptance/Known Accepted) - the thing Apply actually checks. Kept
    separate from Reviewer Validation: validating accuracy and deciding
    what happens next are two different questions."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _finding_case_id(workspace, finding_id)
    _require_visible_case(store, workspace, case_id)

    disposition = request.form.get("disposition")

    try:
        store.record_disposition(
            workspace,
            finding_id=finding_id,
            disposition=disposition,
            reviewer=_reviewer(),
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="finding_reviewed",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"finding_id": finding_id, "disposition": disposition},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route(
    "/projects/<project_id>/workspace/cases/<case_id>/requirement-items/<requirement_item_id>/promote",
    methods=["POST"],
)
@login_required
def promote_requirement_item_route(project_id, case_id, requirement_item_id):
    """Bridges one extracted RequirementItem (services/bhive_parser.py's
    legacy extraction pipeline) into a governed Requirement. See
    CaseWorkspaceStore.promote_requirement_item and
    governance/specified-unbuilt/investigation-lifecycle-extensions.md
    for the finalized promotion contract this route exercises unchanged
    - it never infers source_id, it only forwards what the form
    explicitly asserts."""
    document, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    item = next((r for r in document.requirements if r.id == requirement_item_id), None)
    if item is None:
        abort(404)

    source_id = request.form.get("source_id")
    if not source_id:
        flash(
            "Select the Source this requirement was actually extracted from before promoting it.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    trigger = AnalysisTrigger(
        trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
        triggered_by_actor=_reviewer(),
    )

    try:
        result = store.promote_requirement_item(
            workspace,
            case_id=case_id,
            source_id=source_id,
            requirement_item=asdict(item),
            actor=_reviewer(),
            trigger=trigger,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash(
        f"Promoted requirement item {requirement_item_id} to governed "
        f"Requirement {result['requirement']['id']}.",
        "success",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/register", methods=["POST"])
@login_required
def register_requirement_route(project_id):
    """
    Manually register a Requirement directly from any Source - governed
    or legacy, drawing or document - with no Finding and no Investigation
    involved. This is the gap the Cedar Harbour discovery journey actually
    found: CaseWorkspaceStore.register_requirement already existed,
    already correctly took no case_id (Requirement is project-scoped, and
    this path produces no accompanying Finding the way
    promote_requirement_item deliberately does), but had no route at all -
    a real reviewer had no way to assert "this Requirement's text lives in
    this Source" for anything the legacy extractor never touched (which is
    everything added after the first upload). Deliberately NOT
    Case-scoped, matching the store method's own signature exactly, not a
    judgment call layered on top of it.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    source_id = request.form.get("source_id")
    original_requirement_identifier = (request.form.get("original_requirement_identifier") or "").strip()
    text_reference = (request.form.get("text_reference") or "").strip()

    if not source_id or not original_requirement_identifier or not text_reference:
        flash("A registered Requirement needs a Source, a clause/identifier, and its text.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    try:
        store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier=original_requirement_identifier,
            text_reference=text_reference,
            created_by=_reviewer(),
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    flash("Requirement registered.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/<requirement_id>/adjudicate", methods=["POST"])
@login_required
def adjudicate_requirement(project_id, requirement_id):
    """Records a RequirementAdjudication (Foundation Batch K) - the human
    compliance determination against a governed Requirement, distinct
    from Finding Disposition. See
    CaseWorkspaceStore.record_requirement_adjudication."""
    _, store, workspace = _load_workspace_or_404(project_id)

    outcome = request.form.get("outcome")
    reasoning = request.form.get("reasoning")
    case_id = request.form.get("case_id")
    evidence_finding_ids = [v for v in request.form.getlist("evidence_finding_id") if v]
    evidence_relationship_ids = [v for v in request.form.getlist("evidence_relationship_id") if v]

    try:
        store.record_requirement_adjudication(
            workspace,
            requirement_id=requirement_id,
            outcome=outcome,
            adjudicator=_reviewer(),
            reasoning=reasoning,
            evidence_finding_ids=evidence_finding_ids or None,
            evidence_relationship_ids=evidence_relationship_ids or None,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/<requirement_id>/revise", methods=["POST"])
@login_required
def revise_requirement_route(project_id, requirement_id):
    """
    First route wiring for CaseWorkspaceStore.revise_requirement -
    previously fully implemented and tested but unreachable through the
    UI. Scoped to the one case the method's own docstring names as its
    primary purpose ("An Addendum amending/qualifying/superseding an
    earlier requirement is exactly this call") - only text_reference is
    exposed as an override here, not every optional Requirement field
    revise_requirement's **overrides accepts. A revision that needs to
    also change classification/subject_domain/etc. isn't blocked by
    this route (the store method still accepts those kwargs), it's just
    not reachable from this first, narrower form.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    text_reference = (request.form.get("text_reference") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    authority_class = (request.form.get("authority_class") or "").strip() or None
    if not text_reference or not reason:
        flash("A revision needs the new text and a reason (e.g. which Addendum).", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    try:
        store.revise_requirement(
            workspace, requirement_id=requirement_id, actor=_reviewer(),
            reason=reason, authority_class=authority_class,
            governance_log=_log(), text_reference=text_reference,
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/participants", methods=["POST"])
@login_required
def register_participant_route(project_id):
    """CLAUDE-P12R: register a project party (Owner/Design-Builder/
    Proponent/etc.) - see CaseWorkspaceStore.record_participant."""
    _, store, workspace = _load_workspace_or_404(project_id)

    name = (request.form.get("name") or "").strip()
    role_type = (request.form.get("role_type") or "").strip()
    note = (request.form.get("note") or "").strip() or None
    if not name or not role_type:
        flash("A Participant needs a name and a role.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    # CLAUDE-P29: server-side enforcement of the same gating the
    # participant_role_options passed to the template already reflects
    # -- a directly forged role_type outside the locked environment's
    # allowed set must be rejected here too, not just hidden in the UI.
    allowed_roles = allowed_participant_roles(workspace.operating_environment)
    if allowed_roles is not None and role_type not in allowed_roles:
        flash(
            f"{role_type!r} is not a valid participant role in this project's "
            f"{OPERATING_ENVIRONMENT_LABELS.get(workspace.operating_environment, 'locked')} environment.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    try:
        store.record_participant(
            workspace, name=name, role_type=role_type, created_by=_reviewer(),
            note=note, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/go-no-go", methods=["POST"])
@login_required
def record_go_no_go(project_id):
    """
    CLAUDE-P30: "go_no_go" in environment_capabilities.py's registry --
    a shared decision-record shape, validated against whichever
    decision-stage vocabulary this project's own locked environment
    actually uses (CaseWorkspaceStore.record_go_no_go_decision itself
    enforces this; the capability gate below only controls whether the
    form/route is reachable at all for a legacy/unclassified project).

    CLAUDE-P38 (OBS-04): until this stage, ANY authenticated participant
    (including read_only) could record the actual decision - a
    management action presented as an ordinary participant one. Real
    decision authority is now admin-only, server-side enforced here
    (not merely hidden in the template), matching the same admin-only
    precedent already established for every other consequential,
    one-way project action in this app (Security Department, operating-
    environment classification). A non-admin gets a clear flash, not a
    bare 403 - go_no_go stays reachable to read via the same page,
    unlike admin_required's harder redirect/403 split.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    gate = _require_capability(workspace, "go_no_go", project_id)
    if gate is not None:
        return gate

    if session.get("role") != "admin":
        flash(
            "Only an admin can record a Go/No-Go decision. Share your input through "
            "this project's Conversation so it's on record for whoever does.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    decision_stage = (request.form.get("decision_stage") or "").strip()
    decision = (request.form.get("decision") or "").strip()
    rationale = (request.form.get("rationale") or "").strip()
    anomalies = [line.strip() for line in (request.form.get("anomalies") or "").splitlines() if line.strip()]

    try:
        store.record_go_no_go_decision(
            workspace, decision_stage=decision_stage, decision=decision, rationale=rationale,
            decided_by=_reviewer(), anomalies=anomalies, governance_log=_log(),
            decided_by_role=session.get("role"),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    flash("Go/No-Go decision recorded.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/represented-party", methods=["POST"])
@login_required
def set_represented_party_route(project_id):
    """
    CLAUDE-P12R: which Participant THIS reviewer represents in this
    Project - a personal setting (see CaseWorkspaceStore.
    set_represented_party), not a governed fact. Setting/changing this
    never touches any Requirement, Finding, or existing Perspective
    Assessment - it only affects what a NEW machine investigation is
    asked to assess going forward.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    participant_id = (request.form.get("participant_id") or "").strip()
    try:
        store.set_represented_party(workspace, reviewer=_reviewer(), participant_id=participant_id)
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/<requirement_id>/perspective", methods=["POST"])
@login_required
def record_perspective_assessment_route(project_id, requirement_id):
    """
    CLAUDE-P12R: a human's own risk/opportunity mark on a Requirement,
    FROM their currently-represented Participant's position - see
    CaseWorkspaceStore.record_perspective_assessment and Perspective
    Assessment's own docstring on why this is never inferred from
    anything but this explicit, intentional act.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    represented_party = store.represented_party_for(workspace, _reviewer())
    if represented_party is None:
        flash("Set who you represent in this Project before marking a perspective.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    polarity = (request.form.get("polarity") or "").strip()
    reasoning = (request.form.get("reasoning") or "").strip()

    try:
        store.record_perspective_assessment(
            workspace,
            anchor=asdict(Anchor(anchor_type=OBJECT_KIND_REQUIREMENT, anchor_id=requirement_id)),
            participant_id=represented_party["id"],
            polarity=polarity,
            origin=PERSPECTIVE_ORIGIN_HUMAN,
            reasoning=reasoning,
            recorded_by=_reviewer(),
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/apply", methods=["POST"])
@login_required
def apply_findings(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None:
        abort(404)

    # Only Findings with a Disposition of "Confirmed", and not already
    # applied, are eligible -- Apply never runs off an unreviewed Finding
    # or ReviewerValidation alone, and never re-applies something already
    # governed.
    eligible = [
        f["id"]
        for f in workspace.findings
        if f["id"] in case["finding_ids"]
        and f["claim_status"] != "applied"
        and (store.latest_disposition(workspace, f["id"]) or {}).get("disposition") == "Confirmed"
    ]

    if not eligible:
        flash("No Confirmed, unapplied Findings to apply in this Case.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    gate = _require_approval(
        "apply",
        f'Apply {len(eligible)} Confirmed Finding(s) to governed project state within Case "{case["title"]}". '
        "This cannot be reviewed again afterward.",
        project_id,
        case_id,
    )
    if gate is not None:
        return gate

    predecessor_version = workspace.version
    try:
        apply_record = store.apply_findings(
            workspace,
            finding_ids=eligible,
            applied_by=_reviewer(),
            target=f'Applied within Case "{case["title"]}".',
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="findings_applied",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"finding_ids": eligible, "case_id": case_id},
        state_predecessor_version=predecessor_version,
        state_successor_version=workspace.version,
        authority_class="approval_gate:apply",
        correlation_id=apply_record["id"],
    )

    flash(f"{len(eligible)} Finding(s) applied to governed project state.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


# -- RFI drafts (automatic provenance + Delegation Choice) --------------------------

@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/rfi-drafts/cancel", methods=["POST"])
@login_required
def cancel_rfi_intent(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)
    store.add_message(workspace, case_id, role="system", text="RFI draft request cancelled.", action_taken="rfi_cancelled")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/rfi-drafts/preview", methods=["POST"])
@login_required
def preview_rfi_draft(project_id, case_id):
    """Delegation Choice: 'Show me the proposed action first'. Computes
    and displays the auto-inherited reference bundle WITHOUT creating
    the draft yet."""
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)
    gate = _require_capability(workspace, "rfi_originate", project_id, case_id)
    if gate is not None:
        return gate
    finding_id = request.form.get("finding_id")
    store.add_message(
        workspace, case_id, role="system",
        text="Here is the reference bundle BEEHIVE would inherit for this RFI draft. "
             "Review it below, then create the draft if it looks right.",
        action_taken="rfi_preview_shown",
    )
    return redirect(
        url_for("workspace.show_workspace", project_id=project_id, case=case_id, preview_finding_id=finding_id)
    )


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/rfi-drafts", methods=["POST"])
@login_required
def create_rfi_draft(project_id, case_id):
    """Delegation Choice: 'Do it for me' (question_text may be blank, to
    be filled in after) or the follow-up create step after a preview."""
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)
    gate = _require_capability(workspace, "rfi_originate", project_id, case_id)
    if gate is not None:
        return gate
    finding_id = request.form.get("finding_id")
    question_text = request.form.get("question_text") or ""

    # The draft's real case attribution comes from the Finding itself
    # (CaseWorkspaceStore.create_rfi_draft sets case_id=finding["case_id"],
    # never from this route's own case_id param) - a visible case_id in
    # the URL must not become cover for drafting an RFI against a Finding
    # that actually belongs to a different, private Case.
    _require_visible_case(store, workspace, _finding_case_id(workspace, finding_id))

    try:
        draft = store.create_rfi_draft(
            workspace, finding_id=finding_id, question_text=question_text, created_by=_reviewer(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    store.add_message(
        workspace, case_id, role="system",
        text="RFI draft created with inherited references. Edit the question and issue when ready.",
        action_taken=f"rfi_draft_created:{draft['id']}",
    )

    _log().append(
        project_id=project_id,
        event_type="rfi_draft_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"rfi_draft_id": draft["id"], "finding_id": finding_id},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/rfi-drafts/<draft_id>/question", methods=["POST"])
@login_required
def update_rfi_question(project_id, draft_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _rfi_draft_case_id(workspace, draft_id)
    _require_visible_case(store, workspace, case_id)
    gate = _require_capability(workspace, "rfi_originate", project_id, case_id)
    if gate is not None:
        return gate

    try:
        store.update_rfi_draft_question(
            workspace, draft_id=draft_id, question_text=request.form.get("question_text") or "",
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/rfi-drafts/<draft_id>/issue", methods=["POST"])
@login_required
def issue_rfi_draft(project_id, draft_id):
    """The reviewer controls the actual question/content and final
    issuance - Issue is a separate, explicit, Approval-Gated action from
    drafting."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _rfi_draft_case_id(workspace, draft_id)
    _require_visible_case(store, workspace, case_id)
    capability_gate = _require_capability(workspace, "rfi_originate", project_id, case_id)
    if capability_gate is not None:
        return capability_gate

    draft = next((d for d in workspace.rfi_drafts if d["id"] == draft_id), None)
    if draft is None:
        abort(404)

    gate = _require_approval(
        "rfi_issue",
        f'Issue this RFI draft (referencing Finding from Case "{draft["reference_snapshot"].get("case_title")}"). '
        "Once issued it cannot be un-issued.",
        project_id,
        case_id,
    )
    if gate is not None:
        return gate

    try:
        store.issue_rfi_draft(workspace, draft_id=draft_id, issued_by=_reviewer())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    _log().append(
        project_id=project_id,
        event_type="rfi_issued",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"rfi_draft_id": draft_id},
    )

    flash("RFI issued.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/rfi-drafts/<draft_id>/respond", methods=["POST"])
@login_required
def respond_to_rfi_draft(project_id, draft_id):
    """
    CLAUDE-P30: the Client/Owner-side counterpart to issue_rfi_draft --
    "rfi_respond" in environment_capabilities.py's registry. A
    Design-Builder/Proponent project (or an unauthorized attempt against
    a Client/Owner project's own question via this route) is rejected by
    _require_capability before store.respond_to_rfi_draft is ever called.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _rfi_draft_case_id(workspace, draft_id)
    _require_visible_case(store, workspace, case_id)
    gate = _require_capability(workspace, "rfi_respond", project_id, case_id)
    if gate is not None:
        return gate

    try:
        store.respond_to_rfi_draft(
            workspace, draft_id=draft_id, response_text=request.form.get("response_text") or "",
            responded_by=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("RFI response recorded.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/rfi-drafts/<draft_id>/export")
@login_required
def export_rfi_draft(project_id, draft_id):
    """
    Downloads one governed per-Finding RFIDraft as a professional .docx -
    see services.rfi_export.build_rfi_draft_docx. Deliberately NOT the
    same exporter as the project-wide consistency-flag RFI
    (workspace.export_rfi) - that mechanism has nothing to do with any
    specific Finding/Case, and feeding a governed RFIDraft through it
    would misrepresent what the document actually is.

    A read operation, not a write: the draft's real case_id is derived
    server-side (never a client-supplied value) and checked against
    visible_cases_for exactly like every other hardened Case-scoped
    route, but _require_case_not_archived is deliberately NOT called
    here - an already-issued historical RFI belonging to an archived
    Case remains readable/exportable wherever the requester is already
    authorized to read that Case (Archive is terminal for new
    contributions, not for reading what already happened). Export can
    never broaden visibility: an invisible Case's draft 404s exactly
    like any other invisible-Case object.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _rfi_draft_case_id(workspace, draft_id)
    _require_visible_case(store, workspace, case_id)
    export_gate = _require_export_allowed(workspace, project_id)
    if export_gate is not None:
        return export_gate

    draft = next((d for d in workspace.rfi_drafts if d["id"] == draft_id), None)
    if draft is None:
        abort(404)

    buffer = build_rfi_draft_docx(
        draft, operating_environment_label=OPERATING_ENVIRONMENT_LABELS.get(workspace.operating_environment),
    )
    status_label = draft["status"] if draft["status"] in ("issued", "answered") else "draft"
    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"RFI-{draft['id'][:8]}-{status_label}.docx",
    )


@workspace_bp.route("/projects/<project_id>/workspace/artifacts/<artifact_id>/image")
@login_required
def artifact_image(project_id, artifact_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    artifact = next((a for a in workspace.artifacts if a["id"] == artifact_id), None)
    if artifact is None or not artifact.get("image_path"):
        abort(404)

    # Indirect-identifier guard, same reasoning as the preview_finding_id
    # check above: an artifact_id typed/guessed directly must not bypass
    # Case privacy just because it skips the case listing/switcher.
    visible_case_ids = {c["id"] for c in store.visible_cases_for(workspace, _reviewer())}
    if artifact.get("case_id") not in visible_case_ids:
        abort(404)

    image_path = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_artifacts" / artifact["image_path"]
    if not image_path.exists():
        abort(404)

    return send_file(image_path, mimetype="image/png")


@workspace_bp.route("/projects/<project_id>/workspace/rfi-export")
@login_required
def export_rfi(project_id):
    """
    Authenticated surface for the one existing RFI exporter
    (services.rfi_export.build_rfi_docx) - reused verbatim, not
    reimplemented. routes/api.py's own /documents/<project_id>/rfi
    already calls this same function; that JSON API blueprint now
    requires the same session login as this route does (CLAUDE-P27-B,
    routes/api.py's before_request hook) -- this route predates that
    fix and its docstring describing the old unauthenticated state was
    stale (corrected here, CLAUDE-P29). This route still exists in its
    own right so a link surfaced from inside Case Workspace stays a
    same-blueprint, same-URL-scheme link rather than reaching across
    into /api/v1.

    Project-scoped, not Case-scoped: the underlying RFI is built from
    the legacy consistency-check pipeline's flagged contradictions
    (ParsedDocument.consistency_flags), which has no Case/visibility
    concept of its own. CLAUDE-P32: previously the one route in this
    blueprint that bypassed _load_workspace_or_404 (a direct
    get_registry/_store().get double-lookup) -- refactored to use the
    same loader every other route already does, closing that gap; the
    "any authenticated user may view" claim this docstring used to make
    is no longer true and has been removed, not merely reworded.
    """
    document, store, workspace = _load_workspace_or_404(project_id)
    environment_label = OPERATING_ENVIRONMENT_LABELS.get(workspace.operating_environment)

    export_gate = _require_export_allowed(workspace, project_id)
    if export_gate is not None:
        return export_gate

    try:
        buffer = build_rfi_docx(document, operating_environment_label=environment_label)
    except RFIExportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"RFI-{project_id}.docx",
    )
