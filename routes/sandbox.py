"""MORPHOSIS SLICE 1 - FILE > New Sandbox. See services/sandbox.py.

Sandbox routes:

    GET  /sandbox           the clean start state, or the current Sandbox
                            (?new=1 starts clean - it only forgets which Sandbox
                            this browser was showing; it deletes nothing)
    POST /sandbox/turn      the ONE canonical Composer's endpoint in Sandbox
                            scope (resolve_go_scope points it here)
    POST /sandbox/move      presentation-only position change, with the same
                            owner scope and optimistic revision boundary
    POST /sandbox/landing   the person's decision on a recommended landing:
                            continue in the Sandbox, or start a Planning Study
    GET  /sandbox/media/<object_id>
                            LIQUID SANDBOX: one retained image object of the
                            owner's own current Sandbox (provisional media)

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

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request,
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
    return sb.SandboxStore(current_app.config["REGISTRY_STORE_PATH"],
                           current_app.config["SANDBOX_MEDIA_PATH"])


# STORAGE HARDENING: every page that can write carries the owner's Sandbox token
# as it stood when the page was drawn. A stale tab's write is refused, not merged.
TOKEN_FIELD = "sandbox_base"


def _refuse(refused: Exception):
    flash(str(refused), "error")
    return redirect(url_for("sandbox.home"))


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
                           sandbox_base=_store().token(session.get("username")),
                           projects=_accessible_projects() if offers_study else [],
                           can_create_project=is_admin(), object_label=sb.object_label)


@sandbox_bp.route("/sandbox/move", methods=["POST"])
@login_required
def move():
    _staff_only()
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid position request."), 400
    try:
        record = _store().move_object(
            session.get("username"), session.get(_SESSION_KEY), data.get("object_id"),
            data.get("x"), data.get("y"), expected=data.get(TOKEN_FIELD) or "")
    except sb.SandboxConflict as error:
        return jsonify(error=str(error)), 409
    except sb.SandboxRefused as error:
        return jsonify(error=str(error)), 400
    response = jsonify(sandbox_base=sb.SandboxStore._token_of(record))
    response.headers["Cache-Control"] = "no-store"
    return response


@sandbox_bp.route("/sandbox/turn", methods=["POST"])
@login_required
def turn():
    _staff_only()
    text = (request.form.get("text") or "").strip()[:4000]

    from routes.portal import _project_less_external_ai_allowed, gopilot_turn_labels
    from services import composer_image

    # The canonical Composer's attachment, through the ONE governed image intake
    # (PNG/JPEG/GIF/WebP, 5MB, base64) with this project-less surface's external-AI
    # gate. Accepted bytes are retained only by the provisional Sandbox owner.
    image = composer_image.from_request(request.form, policy_allowed=_project_less_external_ai_allowed)
    attached = image.sent
    image_base64, image_media_type = (image.base64, image.media_type) if image.accepted else (None, None)

    # LIQUID SANDBOX: the objects the person selected, as context. GOV-P-001 -
    # the host fixes the selection: only ids in the owner's OWN current Sandbox
    # survive, and selecting changes context only, never what is permitted.
    store = _store()
    username = session.get("username")
    # A page drawn before another tab changed this Sandbox is refused here -
    # before anything is sent to the model or kept.
    base = request.form.get(TOKEN_FIELD) or ""
    if base != store.token(username):
        return _refuse(sb.SandboxConflict(
            "This Sandbox changed in another tab or window. Refresh to see the latest, then send "
            "again. Nothing from this message was kept or sent."))
    existing = _current()
    try:
        selected, ignored = sb.resolve_selection(existing, request.form.getlist("object_id"))
    except sb.SandboxRefused as refused:
        return _refuse(refused)

    typed = bool(text)
    if not text and image_base64:
        text = "What should I make of this?"
    if not text and selected:
        text = "What should I make of the selected objects?"
    if not text:
        return redirect(url_for("sandbox.home"))
    try:
        store.check_capacity(existing, note=typed,
                             image_bytes=int(len(image_base64) * 3 / 4) if image_base64 else 0)
    except sb.SandboxRefused as refused:
        flash(str(refused), "error")                  # refused BEFORE anything is sent or kept
        return redirect(url_for("sandbox.home"))
    if attached and not image.accepted:
        flash(image.reason + " The text was sent without it.", "error")
    if ignored:
        flash("%d selected item%s not in this Sandbox and %s ignored." % (
            ignored, " was" if ignored == 1 else "s were", "was" if ignored == 1 else "were"), "error")

    labels = gopilot_turn_labels("APPLICATION", text)
    try:
        record = existing or store.start(username, expected=base)
    except sb.SandboxRefused as refused:
        return _refuse(refused)
    session[_SESSION_KEY] = record["id"]
    expected = base if existing else sb.SandboxStore._token_of(record)

    history = [t["text"] for t in record["turns"]]
    model_allowed = _project_less_external_ai_allowed()
    # Selected images' retained bytes travel only when the same project-less
    # external-AI gate that governs an attached image allows it.
    selected_images = []
    selected_image_ids = []
    if model_allowed:
        import base64 as _b64
        for obj in selected:
            raw = store.read_media(username, obj)
            if raw is not None:
                selected_image_ids.append(obj["id"])
                selected_images.append((_b64.b64encode(raw).decode("ascii"),
                                        obj["content"]["media"]["media_type"]))
    organization = sb.organize(
        text, history,
        model_allowed=model_allowed,
        api_key=current_app.config.get("ANTHROPIC_API_KEY"),
        model=current_app.config.get("ANTHROPIC_MODEL"),
        image_base64=image_base64, image_media_type=image_media_type,
        selected=selected, selected_images=selected_images, selected_image_ids=selected_image_ids,
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
        "context": {"selected": [obj["id"] for obj in selected], "ignored": ignored},
        "canonical": False,
    }
    try:
        store.add_turn(username, record["id"], text, reply, note=typed,
                       image=(image_base64, image_media_type) if image_base64 else None,
                       text_arrival=request.form.get("text_arrival"),
                       image_arrival=request.form.get("image_arrival"),
                       selected=[obj["id"] for obj in selected], expected=expected)
    except sb.SandboxRefused as refused:          # a cap, or a tab that wrote while the model ran
        flash(str(refused), "error")
        return redirect(url_for("sandbox.home"))
    return redirect(url_for("sandbox.home", _anchor="sandbox-latest"))


@sandbox_bp.route("/sandbox/media/<object_id>", methods=["GET"])
@login_required
def media(object_id):
    """One retained image of the owner's OWN current Sandbox - never anyone else's,
    never a project's. Provisional media has no other way out."""
    _staff_only()
    record = _current()
    obj = next((o for o in (record or {}).get("objects") or [] if o["id"] == object_id), None)
    raw = _store().read_media(session.get("username"), obj) if obj else None
    if raw is None:
        abort(404)
    from flask import Response
    response = Response(raw, mimetype=obj["content"]["media"]["media_type"])
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Content-Disposition"] = "inline"
    return response


def _decide(record, choice):
    _store().record_decision(session.get("username"), record["id"], choice,
                             expected=request.form.get(TOKEN_FIELD) or "")


@sandbox_bp.route("/sandbox/landing", methods=["POST"])
@login_required
def landing():
    _staff_only()
    record = _current()
    if record is None or record["id"] != request.form.get("sandbox_id"):
        abort(404)
    choice = request.form.get("choice")
    try:
        return _landing(record, choice)
    except sb.SandboxRefused as refused:          # a stale tab chose on an older Sandbox
        return _refuse(refused)


def _landing(record, choice):
    if choice == sb.DECISION_CONTINUE:
        _decide(record, choice)
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
        _decide(record, choice)
        return redirect(url_for("planning_zoning.planning_zoning", sandbox=record["id"],
                                project_id=project_id))
    # Create New Project: the existing owner decides who may create one.
    if not is_admin():
        abort(403)
    _decide(record, choice)
    session[_RESUME_KEY] = {"sandbox_id": record["id"], "project_id": None}
    return redirect(url_for("portal.upload", sandbox=record["id"]))
