"""MORPHOSIS SLICE 1 - FILE > New Sandbox. See services/sandbox.py.

Three routes, none of which creates governed work:

    GET  /sandbox           the clean start state, or the current Sandbox
                            (?new=1 starts clean - it only forgets which Sandbox
                            this browser was showing; it deletes nothing)
    POST /sandbox/turn      the ONE canonical Composer's endpoint in Sandbox
                            scope (resolve_go_scope points it here)
    POST /sandbox/landing   the person's decision on a recommended landing:
                            continue in the Sandbox, or start a Planning Study

A Planning Study always lives in a project (the planning owner requires one),
so a Planning Study landing offers three explicit choices:

    Use Existing Project   a project the person can already open, chosen from
                           the planning owner's OWN access-scoped list; goes to
                           the Planning & Zoning entry with that project
    Create New Project     the EXISTING New Project owner (portal.upload), with
                           only the Sandbox id carried; once that owner has
                           created the project and prepared its briefing, the
                           person is returned to the Planning & Zoning entry
    Continue in Sandbox    creates nothing

No project-less study, no automatic project. The Planning & Zoning entry's own
submit is the explicit act that runs live municipal retrieval - never here.
"""
from __future__ import annotations

from flask import (Blueprint, abort, current_app, flash, redirect, render_template, request,
                   session, url_for)

from services.auth import is_admin, login_required, user_is_document_shop_customer
from services import sandbox as sb

sandbox_bp = Blueprint("sandbox", __name__)

_SESSION_KEY = "sandbox_id"
# A New Project being created FOR a Sandbox: {"sandbox_id", "project_id"}. The
# project id is bound only by a creation whose own form carried the marker.
_RESUME_KEY = "sandbox_resume"
RESUME_FIELD = "sandbox_resume"


def _store() -> sb.SandboxStore:
    return sb.SandboxStore(current_app.config["REGISTRY_STORE_PATH"])


def _staff_only():
    # The Sandbox lands in staff envelopes (a Planning Study); a Document Shop
    # customer's application path is My Documents, unchanged.
    if user_is_document_shop_customer():
        abort(404)


def _accessible_projects() -> list:
    """The planning owner's own access-scoped project list - never a second one."""
    from routes.planning_zoning import _study_projects
    return _study_projects()


def pending_resume_id():
    """The Sandbox a New Project form is being filled for, while none is bound yet."""
    resume = session.get(_RESUME_KEY) or {}
    return resume.get("sandbox_id") if not resume.get("project_id") else None


def bind_created_project(project_id: str) -> None:
    """Called by the New Project owner right after it creates a project. Binds
    the project to the pending Sandbox resume ONLY when this very submission
    carried the matching marker - an unrelated project never gets pulled in."""
    submitted = (request.form.get(RESUME_FIELD) or "").strip()
    if submitted and submitted == pending_resume_id():
        session[_RESUME_KEY] = {"sandbox_id": submitted, "project_id": project_id}


def resume_redirect(project_id: str):
    """Where the New Project flow hands over once it is finished with a project:
    back to the Planning & Zoning entry, for a project created for a Sandbox;
    None otherwise, so the caller keeps its own destination."""
    resume = session.get(_RESUME_KEY) or {}
    if resume.get("project_id") != project_id:
        return None
    session.pop(_RESUME_KEY, None)
    return redirect(url_for("planning_zoning.planning_zoning",
                            sandbox=resume["sandbox_id"], project_id=project_id))


def _current():
    sandbox_id = session.get(_SESSION_KEY)
    if not sandbox_id:
        return None
    return _store().get(session.get("username"), sandbox_id)


@sandbox_bp.route("/sandbox", methods=["GET"])
@login_required
def home():
    _staff_only()
    if request.args.get("new"):
        session.pop(_SESSION_KEY, None)
        return redirect(url_for("sandbox.home"))
    record = _current()
    latest = record["turns"][-1] if record and record["turns"] else None
    offers_study = bool(latest and (latest.get("reply") or {}).get("landing"))
    return render_template("sandbox.html", sandbox=record, clean_surface=True, latest=latest,
                           projects=_accessible_projects() if offers_study else [],
                           can_create_project=is_admin())


@sandbox_bp.route("/sandbox/turn", methods=["POST"])
@login_required
def turn():
    _staff_only()
    text = (request.form.get("text") or "").strip()[:4000]

    from routes.portal import _project_less_external_ai_allowed, gopilot_turn_labels
    from services import composer_image

    # The canonical Composer's attachment, through the ONE governed image intake
    # (PNG/JPEG/GIF/WebP, 5MB, base64) with this project-less surface's external-AI
    # gate. Nothing is written to disk, registered, or kept beyond its identity.
    image = composer_image.from_request(request.form, policy_allowed=_project_less_external_ai_allowed)
    attached = image.sent
    image_base64, image_media_type = (image.base64, image.media_type) if image.accepted else (None, None)
    if attached and not image.accepted:
        flash(image.reason + " The text was sent without it.", "error")
    if not text and image_base64:
        text = "What should I make of this?"
    if not text:
        return redirect(url_for("sandbox.home"))

    labels = gopilot_turn_labels("APPLICATION", text)
    store = _store()
    username = session.get("username")
    record = _current() or store.start(username)
    session[_SESSION_KEY] = record["id"]

    history = [t["text"] for t in record["turns"]]
    model_allowed = _project_less_external_ai_allowed()
    organization = sb.organize(
        text, history,
        model_allowed=model_allowed,
        api_key=current_app.config.get("ANTHROPIC_API_KEY"),
        model=current_app.config.get("ANTHROPIC_MODEL"),
        image_base64=image_base64, image_media_type=image_media_type,
    )
    attachments = []
    if image_base64:
        attachments.append(sb.attachment_identity(
            image_base64, image_media_type,
            analysed=model_allowed and organization.get("source") == "model"))
    elif attached:
        # Received but refused (type, size or policy): said, never silently dropped.
        attachments.append({"kind": "image", "status": "not accepted", "analysed": False,
                            "canonical": False})
    reply = {
        "organization": organization,
        "external": sb.external_check(text, history),
        "landing": sb.recommend_landing(text, history),
        "intent": ((labels or {}).get("intent") or {}).get("envelope"),
        "attachments": attachments,
        "canonical": False,
    }
    store.add_turn(username, record["id"], text, reply)
    return redirect(url_for("sandbox.home", _anchor="sandbox-latest"))


@sandbox_bp.route("/sandbox/landing", methods=["POST"])
@login_required
def landing():
    _staff_only()
    record = _current()
    if record is None or record["id"] != request.form.get("sandbox_id"):
        abort(404)
    choice = request.form.get("choice")
    if choice == sb.DECISION_CONTINUE:
        _store().record_decision(session.get("username"), record["id"], choice)
        flash("Staying in the Sandbox. Nothing was created.", "success")
        return redirect(url_for("sandbox.home", _anchor="sandbox-latest"))
    if choice not in (sb.DECISION_EXISTING_PROJECT, sb.DECISION_NEW_PROJECT):
        abort(400)
    latest = record["turns"][-1]["reply"] if record["turns"] else {}
    if not (latest or {}).get("landing"):
        abort(409)
    if choice == sb.DECISION_EXISTING_PROJECT:
        project_id = (request.form.get("project_id") or "").strip()
        if project_id not in {p["id"] for p in _accessible_projects()}:
            abort(404)          # not a project this person can open - never confirmed
        _store().record_decision(session.get("username"), record["id"], choice)
        return redirect(url_for("planning_zoning.planning_zoning", sandbox=record["id"],
                                project_id=project_id))
    # Create New Project: the existing owner decides who may create one.
    if not is_admin():
        abort(403)
    _store().record_decision(session.get("username"), record["id"], choice)
    session[_RESUME_KEY] = {"sandbox_id": record["id"], "project_id": None}
    return redirect(url_for("portal.upload", sandbox=record["id"]))
