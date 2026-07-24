"""
Case Workspace routes — the experimental Project / Case / Source /
Artifact / Analysis / Finding / Review / Apply interaction prototype
(Prompt 4). Mounted alongside the existing portal/api blueprints; changes
nothing about the existing upload -> dashboard pipeline, which keeps
working exactly as before.

Classic Flask form-POST -> redirect -> re-render throughout, matching the
rest of this app (no client-side build step, no fetch/JSON layer) — see
tools/dependency_fit.py's no-client-build rule.
"""
from __future__ import annotations

import io
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
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.conversation_interpreter import interpret_message
from services.governance import GovernanceLog
from services.ingestion import get_registry

workspace_bp = Blueprint("workspace", __name__)

ALLOWED_DRAWING_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _store() -> CaseWorkspaceStore:
    return CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])


def _reviewer() -> str:
    return session.get("username") or "anonymous"


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


@workspace_bp.route("/projects/<project_id>/workspace")
@login_required
def show_workspace(project_id):
    document, store, workspace = _load_workspace_or_404(project_id)

    active_case_id = request.args.get("case") or (
        workspace.cases[0]["id"] if workspace.cases else None
    )
    active_case = next((c for c in workspace.cases if c["id"] == active_case_id), None)

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
            latest_review = store.latest_review(workspace, finding_id)

            if finding["claim_status"] == "applied":
                applied_count += 1
            elif latest_review is not None and latest_review["decision"] == "accept":
                awaiting_apply_count += 1

            findings_view.append(
                {
                    "finding": finding,
                    "artifact": artifact,
                    "reviews": store.reviews_for_finding(workspace, finding_id),
                    "latest_review": latest_review,
                }
            )

    return render_template(
        "case_workspace.html",
        document=document,
        workspace=workspace,
        active_case=active_case,
        findings_view=findings_view,
        focused_finding_id=focused_finding_id,
        applied_count=applied_count,
        awaiting_apply_count=awaiting_apply_count,
        project_id=project_id,
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

    case = store.create_case(workspace, title=title, objective=objective)

    log = GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])
    log.append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"]))


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

    stored_path = sources_dir / safe_name
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

    store.add_message(workspace, case_id, role="human", text=text)

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

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/findings/<finding_id>/review", methods=["POST"])
@login_required
def review_finding(project_id, finding_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    decision = request.form.get("decision")
    note = request.form.get("note") or None
    case_id = request.form.get("case_id")

    try:
        store.record_review(
            workspace,
            finding_id=finding_id,
            decision=decision,
            reviewer=_reviewer(),
            note=note,
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    log = GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])
    log.append(
        project_id=project_id,
        event_type="finding_reviewed",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"finding_id": finding_id, "decision": decision},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/apply", methods=["POST"])
@login_required
def apply_findings(project_id, case_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None:
        abort(404)

    # Only findings with an "accept" as their LATEST review, and not
    # already applied, are eligible -- Apply never runs off a stale or
    # superseded review, and never re-applies something already governed.
    eligible = [
        f["id"]
        for f in workspace.findings
        if f["id"] in case["finding_ids"]
        and f["claim_status"] != "applied"
        and (store.latest_review(workspace, f["id"]) or {}).get("decision") == "accept"
    ]

    if not eligible:
        flash("No accepted, unapplied Findings to apply in this Case.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.apply_findings(
            workspace,
            finding_ids=eligible,
            applied_by=_reviewer(),
            target=f'Applied within Case "{case["title"]}".',
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    log = GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])
    log.append(
        project_id=project_id,
        event_type="findings_applied",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"finding_ids": eligible, "case_id": case_id},
    )

    flash(f"{len(eligible)} Finding(s) applied to governed project state.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))


@workspace_bp.route("/projects/<project_id>/workspace/artifacts/<artifact_id>/image")
@login_required
def artifact_image(project_id, artifact_id):
    _, _store_unused, workspace = _load_workspace_or_404(project_id)

    artifact = next((a for a in workspace.artifacts if a["id"] == artifact_id), None)
    if artifact is None or not artifact.get("image_path"):
        abort(404)

    image_path = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_artifacts" / artifact["image_path"]
    if not image_path.exists():
        abort(404)

    return send_file(image_path, mimetype="image/png")
