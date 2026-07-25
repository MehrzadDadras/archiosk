"""
Case Workspace routes — the experimental Project / Case / Source /
Artifact / Analysis / Finding / Review / Apply interaction prototype.
Mounted alongside the existing portal/api blueprints; changes nothing
about the existing upload -> dashboard pipeline, which keeps working
exactly as before.

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
import uuid
from dataclasses import asdict
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

from services.auth import login_required
from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DISPOSITIONS,
    REVIEWER_VALIDATION_STATES,
)
from services.conversation_interpreter import interpret_message
from services.governance import GovernanceLog
from services.ingestion import get_registry
from services.project_clock import open_project

workspace_bp = Blueprint("workspace", __name__)

ALLOWED_DRAWING_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _store() -> CaseWorkspaceStore:
    return CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])


def _reviewer() -> str:
    return session.get("username") or "anonymous"


def _log() -> GovernanceLog:
    return GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])


def _load_workspace_or_404(project_id: str):
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    store = _store()
    workspace = store.get_or_create(
        project_id,
        register_document_source={
            "filename": document.filename,
            "ingested_at": document.ingested_at,
            "requirement_count": len(document.requirements),
            "milestone_count": len(document.milestones),
        },
    )
    return document, store, workspace


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

    active_case_id = request.args.get("case") or (
        visible_cases[0]["id"] if visible_cases else None
    )
    active_case = next((c for c in visible_cases if c["id"] == active_case_id), None)

    focused_finding_id = session.get(f"focused_finding:{project_id}")

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

    return render_template(
        "case_workspace.html",
        document=document,
        workspace=workspace,
        visible_cases=visible_cases,
        active_case=active_case,
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
        knowledge_count=len(store.knowledge_for_project(workspace)),
        activities=store.activities_for_case(workspace, active_case["id"]) if active_case else [],
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


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/sources", methods=["POST"])
@login_required
def add_drawing_source(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)

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


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/messages", methods=["POST"])
@login_required
def post_message(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None:
        abort(404)

    text = (request.form.get("text") or "").strip()
    if not text:
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    human_message = store.add_message(workspace, case_id, role="human", text=text)

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
    )

    store.add_message(
        workspace,
        case_id,
        role="system",
        text=result.reply_text,
        action_taken=result.action_taken,
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

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/findings/<finding_id>/validate", methods=["POST"])
@login_required
def validate_finding(project_id, finding_id):
    """Records a Reviewer Validation (Correct/Incorrect/Partial/Needs
    Evidence/Not Applicable) - distinct from Disposition, see
    /disposition below."""
    _, store, workspace = _load_workspace_or_404(project_id)

    validation = request.form.get("validation")
    correction_note = request.form.get("correction_note") or None
    case_id = request.form.get("case_id")

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

    disposition = request.form.get("disposition")
    case_id = request.form.get("case_id")

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


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/apply", methods=["POST"])
@login_required
def apply_findings(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)

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
    store.add_message(workspace, case_id, role="system", text="RFI draft request cancelled.", action_taken="rfi_cancelled")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/rfi-drafts/preview", methods=["POST"])
@login_required
def preview_rfi_draft(project_id, case_id):
    """Delegation Choice: 'Show me the proposed action first'. Computes
    and displays the auto-inherited reference bundle WITHOUT creating
    the draft yet."""
    _, store, workspace = _load_workspace_or_404(project_id)
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
    finding_id = request.form.get("finding_id")
    question_text = request.form.get("question_text") or ""

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
    case_id = request.form.get("case_id")
    draft = next((d for d in workspace.rfi_drafts if d["id"] == draft_id), None)
    if draft is None:
        abort(404)
    draft["question_text"] = request.form.get("question_text") or ""
    store.save(workspace)
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/rfi-drafts/<draft_id>/issue", methods=["POST"])
@login_required
def issue_rfi_draft(project_id, draft_id):
    """The reviewer controls the actual question/content and final
    issuance - Issue is a separate, explicit, Approval-Gated action from
    drafting."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = request.form.get("case_id")

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
