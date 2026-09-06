"""CLAUDE-HELP-CENTER-01 - where the long explanations live instead.

WHY THIS EXISTS. The operational surfaces were growing paragraphs. An access
panel that explains token security in four sentences is a panel a superintendent
reads once and then scrolls past forever, and every line of it competes with the
control they actually came for. Desks carry concise labels and a [?]; the
reasoning lives here.

WHAT IS AND IS NOT DOCUMENTED HERE. Only capabilities that exist. Where a guide
describes something not built, it SAYS SO in the guide rather than describing it
in the present tense - documentation that describes an unbuilt feature is
indistinguishable from a lie to the person reading it on a site.

Authenticated, not public: these guides name real project surfaces and role
scopes, and the sign-in page is deliberately isolated from exactly that kind of
content (see templates/auth_shell.html and CLAUDE-P40-D1).
"""
from __future__ import annotations

from flask import (
    Blueprint, abort, current_app, flash, jsonify, redirect,
    render_template, request, session, url_for,
)

from services.auth import is_admin, login_required
from services.case_workspace import CaseWorkspaceStore
from services.help_mode import (
    add_help_claim,
    add_help_script_scene,
    create_help_script,
    help_script_detail,
    list_help_scripts,
    HELP_LIBRARY_PROJECT_ID,
    HelpContext,
    HelpModeError,
    propose_project_transition,
    read_help_conversation,
    record_help_message,
)
from services.case_workspace import SCRIPT_VALIDATION_VALIDATED
from services.script_fit import help_status_for, run_script_trust_chain

help_bp = Blueprint("help_center", __name__)

# CLAUDE-HELP-CONCIERGE-01 / CLAUDE-HELP-MODE-01: the reserved workspace ids now
# live in services/help_mode.py, which owns the Help/Project boundary. Re-exported
# here because this module's existing routes and tests already import it from
# here, and two definitions of a reserved id is exactly how they drift apart.


def _help_store() -> CaseWorkspaceStore:
    """The same construction routes/workspace.py uses - one store, one path."""
    return CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])


def _external_ai_decision(workspace) -> str:
    """Resolve ACTION_EXTERNAL_AI_REQUEST for the Help library.

    The caller resolves policy and services/script_fit.py enforces it - the same
    split every other external-AI call site in this app uses. Policy is read
    here rather than inside the chain so the chain stays Flask-free and
    testable.
    """
    from services.security_governance import SecurityGovernanceStore
    from services.security_policy import (
        ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY, evaluate_action, profile_decision_for,
    )

    try:
        # The same four lookup lines routes/workspace.py's own
        # _evaluate_security_action uses, and for the reason its docstring
        # already gives: the resolver is shared, the boilerplate is short
        # enough that threading a Flask-app-context helper through would be
        # worse than repeating it.
        security_store = SecurityGovernanceStore(current_app.config["REGISTRY_STORE_PATH"])
        record = security_store.get()
        active_baseline = security_store.active_baseline(record)
        decision = evaluate_action(
            ACTION_EXTERNAL_AI_REQUEST,
            classification=workspace.security_profile,
            baseline_decision=(
                active_baseline["control_decisions"].get(
                    ACTION_EXTERNAL_AI_REQUEST, {}).get("decision")
                if active_baseline else None
            ),
            baseline_version_id=active_baseline["id"] if active_baseline else None,
            profile_decision=profile_decision_for(
                workspace.security_profile, ACTION_EXTERNAL_AI_REQUEST),
            active_exception=security_store.active_exception_for(
                record, ACTION_EXTERNAL_AI_REQUEST, project_id=workspace.project_id,
            ),
        )
        return decision.decision
    except Exception:  # noqa: BLE001
        # A policy layer that cannot answer is not permission. Denying here
        # degrades the chain to "check could not run", which is honest, rather
        # than silently calling a model the policy might forbid.
        current_app.logger.warning("Help concierge: policy resolution failed.", exc_info=True)
        return DECISION_DENY

# A closed set. A help route that renders any template name it is handed is a
# template-injection surface, and "guides" is not a directory anyone should be
# able to walk.
GUIDES = {
    "new-project": {
        "template": "help/new_project.html",
        "title": "New Project",
        "summary": "Project naming, acronym rules, references, and persistence.",
    },
    "field-access-passes": {
        "template": "help/field_access_passes.html",
        "title": "Field access passes",
        "summary": "Roles, discipline scope, expiry, QR onboarding and revocation.",
    },
    "spatial-coordination": {
        "template": "help/spatial_coordination.html",
        "title": "Spatial coordination",
        "summary": "Split-pane comparison, vector framing, and where a claim came from.",
    },
    "spin-and-survival-modes": {
        "template": "help/spin_and_survival_modes.html",
        "title": "Spin & Survival Mode",
        "summary": "First Spin, Delta Spin, and the Survival lens - what each is for.",
    },
    "building-box-meetings": {
        "template": "help/building_box_meetings.html",
        "title": "Building Box in meetings",
        "summary": "Running a trailer meeting from a Building Box pass.",
    },
    # CLAUDE-UPLOAD-COPY-TO-HELP-01: the three that let the upload and Data
    # Room surfaces carry a label and a [?] instead of paragraphs.
    "drawing-ingestion": {
        "template": "help/drawing_ingestion.html",
        "title": "Drawing ingestion & baselines",
        "summary": "Exporting vector PDFs from Revit/CAD, and organising an issued set.",
    },
    "what-is-reconciliation": {
        "template": "help/what_is_reconciliation.html",
        "title": "What is Reconciliation?",
        "summary": "Compare a folder against what is registered, read the report, then approve.",
    },
    "file-types-and-limits": {
        "template": "help/file_types_and_limits.html",
        "title": "File types & limits",
        "summary": "Accepted formats, size limits, and how large files upload in pieces.",
    },
}


@help_bp.route("/help")
@login_required
def index():
    # can_author gates a link, never access - authoring_index re-checks for
    # itself. A hidden link is not authorization, and a template that has to
    # be right for a route to be safe is one edit away from not being.
    return render_template("help/index.html", guides=GUIDES, can_author=is_admin())


@help_bp.route("/help/<guide>")
@login_required
def guide(guide: str):
    entry = GUIDES.get(guide)
    if entry is None:
        abort(404)
    return render_template(entry["template"], guide_key=guide, guides=GUIDES,
                           title=entry["title"])


# --- Help concierge: the governed answer path ------------------------------
# CLAUDE-HELP-CONCIERGE-01. The trust chain runs at MEANINGFUL CHECKPOINTS, never
# continuously: on save of a candidate Script, on submit for review, and on an
# explicit reviewer Re-check. It deliberately does not run while someone types -
# a material edit retires the prior verdicts by design (see
# resolve_script_readiness), so an edit-triggered chain would cost two model
# calls per keystroke and tell nobody anything they could act on yet.


def _run_chain(store, workspace, script_id: str) -> dict:
    """One checkpoint run, plus the reader-facing translation."""
    chain = run_script_trust_chain(
        store, workspace, work_product_id=script_id,
        policy_decision=_external_ai_decision(workspace),
    )
    status = help_status_for(
        {"readiness": chain["readiness"], "checks": chain["checks"]},
        could_not_run=chain["could_not_run"],
    )
    return {"chain": chain, "status": status}


@help_bp.route("/help/scripts/<script_id>/status")
@login_required
def script_status(script_id):
    """What a Help reader is told: one status, and the answer only if REUSABLE.

    The gate machinery is deliberately absent from this response. A reader is
    not troubleshooting seven checks; they need to know whether they can rely on
    what they are reading. `checks` is included only for an admin, who is the
    only person for whom "which of seven" is actionable.
    """
    store = _help_store()
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    script = store.get_work_product(workspace, script_id)
    if script is None or script.get("artifact_type") != "script":
        abort(404)

    readiness = store.resolve_script_readiness(workspace, script_id)
    status = help_status_for(readiness)

    body = {
        "script_id": script_id,
        "question": readiness.get("question"),
        "status": status["status"],
        "label": status["label"],
    }
    if status["answerable"]:
        from services.script_fit import script_narrative_text

        body["answer"] = script_narrative_text(script)
    if is_admin():
        body["checks"] = readiness["checks"]
        body["reasons"] = readiness["reasons"]
    return jsonify(body)


@help_bp.route("/help/scripts/<script_id>/recheck", methods=["POST"])
@login_required
def script_recheck(script_id):
    """The reviewer's explicit Re-check - the manual half of the hybrid model.

    Admin-gated because it spends real external-AI calls, and because the
    detailed gate results it returns are reviewer material. It records verdicts
    and nothing else: no validation, no adoption, no promotion. Those remain
    separate human acts, which is GOV-P-006's whole point.
    """
    if not is_admin():
        abort(403)
    store = _help_store()
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    if store.get_work_product(workspace, script_id) is None:
        abort(404)

    result = _run_chain(store, workspace, script_id)
    return jsonify({
        "script_id": script_id,
        "status": result["status"]["status"],
        "label": result["status"]["label"],
        "readiness": result["chain"]["readiness"],
        "checks": result["chain"]["checks"],
        "blocked_by": result["chain"]["blocked_by"],
        "could_not_run": result["chain"]["could_not_run"],
    })


# --- Help / Learning Mode ---------------------------------------------------
# CLAUDE-HELP-MODE-01. Entering Help does not enter the project. These routes
# never receive a project workspace and never write to one; the isolation is the
# same one the kernel already enforces between two customer projects, because to
# the kernel that is exactly what this is.


def _help_context_from_request(payload: dict) -> HelpContext:
    """Build the Help context from what the client sent.

    Only four fields are read. Anything project-shaped in the payload is
    refused rather than ignored - see assert_context_is_help_shaped - because a
    caller that sent it has misunderstood the boundary and should hear so.
    """
    from services.help_mode import assert_context_is_help_shaped

    assert_context_is_help_shaped(payload.get("context") or {})
    context = payload.get("context") or {}
    return HelpContext(
        page=context.get("page"),
        control=context.get("control"),
        app_version=current_app.config.get("STATIC_VERSION"),
        role="admin" if is_admin() else "user",
    )


@help_bp.route("/help/mode/ask", methods=["POST"])
@login_required
def help_mode_ask():
    """Ask a question in Help / Learning Mode.

    The answer comes from the governed Help Library and nowhere else. The
    project the user happens to have open is not consulted, not recorded, and
    not reachable from here: this handler is given no project id and builds no
    project workspace.
    """
    from flask import session

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "A question is required."}), 400

    username = session.get("username")
    store = _help_store()
    try:
        context = _help_context_from_request(payload)
        record_help_message(store, username, author=username, body=question, context=context)
    except HelpModeError as exc:
        return jsonify({"error": str(exc)}), 400

    # The answer: a REUSABLE Help Script for this question, or an honest
    # nothing. Help never invents an answer when the library has none - the
    # same discipline the Help Center's own guides already state.
    library = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    answer = None
    for script in library.work_products:
        if script.get("artifact_type") != "script":
            continue
        readiness = store.resolve_script_readiness(library, script["id"])
        status = help_status_for(readiness)
        if status["answerable"] and (readiness.get("question") or "").strip() == question:
            from services.script_fit import script_narrative_text

            answer = {"script_id": script["id"], "text": script_narrative_text(script)}
            break

    if answer is not None:
        record_help_message(store, username, author="help", body=answer["text"])

    return jsonify({
        "mode": "help",
        "question": question,
        "answer": answer,
        "context": context.to_dict(),
        "project_context_used": False,
    })


@help_bp.route("/help/mode/history")
@login_required
def help_mode_history():
    """This user's Help history. Separate storage, separate from project chat."""
    from flask import session

    return jsonify({
        "mode": "help",
        "messages": read_help_conversation(_help_store(), session.get("username")),
    })


@help_bp.route("/help/mode/transition", methods=["POST"])
@login_required
def help_mode_transition():
    """Offer to continue a project-specific question in Project Mode.

    This returns an OFFER. It transfers nothing, and says so explicitly in the
    response rather than leaving a reader to infer it. Accepting is a separate
    act by the user, in the project's own conversation, where project evidence
    legitimately applies.
    """
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    if not question:
        return jsonify({"error": "A question is required."}), 400
    return jsonify(propose_project_transition(question, payload.get("project_id")))


# --- Help Script authoring (reviewer surface) -------------------------------
# CLAUDE-HELP-AUTHORING-01. The smallest surface that removes the need for a
# scratchpad script. Admin-gated throughout: authoring governed Help content is
# a reviewer act, and Re-check spends real external-AI calls.
#
# SAVE IS NOT A MODEL CHECKPOINT. Creating or editing persists content and
# nothing else - no model call is made. Re-check is the deliberate action that
# spends calls. That is what makes "no continuous model calls" true by
# construction rather than by restraint, and it costs nothing in safety: a
# material edit already retires the prior verdicts, so an edited Script cannot
# read as checked while it waits for its re-check.


def _require_reviewer():
    if not is_admin():
        abort(403)


@help_bp.route("/help/authoring")
@login_required
def authoring_index():
    """Every Help Script and its DERIVED status. No stored status anywhere."""
    _require_reviewer()
    return render_template("help/authoring_index.html",
                           scripts=list_help_scripts(_help_store()),
                           guides=GUIDES)


@help_bp.route("/help/authoring/scripts", methods=["POST"])
@login_required
def authoring_create():
    """Create a DRAFT Help Script. Persists content; spends no model call."""
    _require_reviewer()
    try:
        script = create_help_script(
            _help_store(),
            question=request.form.get("question", ""),
            title=request.form.get("title", ""),
            actor=session.get("username", "reviewer"),
        )
    except HelpModeError as exc:
        flash(str(exc), "error")
        return redirect(url_for("help_center.authoring_index"))
    return redirect(url_for("help_center.authoring_edit", script_id=script["id"]))


@help_bp.route("/help/authoring/scripts/<script_id>")
@login_required
def authoring_edit(script_id):
    """The editor: the Script, its scenes, the claims available to cite, and
    the reviewer detail a reader never sees - which verdicts still apply, which
    have gone stale, and what is blocking."""
    _require_reviewer()
    detail = help_script_detail(_help_store(), script_id)
    if detail is None:
        abort(404)
    return render_template("help/authoring_edit.html", script=detail, guides=GUIDES)


@help_bp.route("/help/authoring/scripts/<script_id>/scenes", methods=["POST"])
@login_required
def authoring_add_scene(script_id):
    """Add a narrative unit citing the claims it rests on. Save only."""
    _require_reviewer()
    store = _help_store()
    if help_script_detail(store, script_id) is None:
        abort(404)
    try:
        add_help_script_scene(
            store, script_id=script_id,
            text=request.form.get("text", ""),
            actor=session.get("username", "reviewer"),
            claim_ids=request.form.getlist("claim_ids"),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer, not swallowed
        flash(str(exc), "error")
    return redirect(url_for("help_center.authoring_edit", script_id=script_id))


@help_bp.route("/help/authoring/scripts/<script_id>/claims", methods=["POST"])
@login_required
def authoring_add_claim(script_id):
    """Record a Claim answering this Script's own question.

    Save only - no model call. The claim starts `proposed`; authoring one is not
    adopting it, and REUSABLE still waits for that separate human act.
    """
    _require_reviewer()
    store = _help_store()
    if help_script_detail(store, script_id) is None:
        abort(404)
    try:
        add_help_claim(
            store, script_id=script_id,
            statement=request.form.get("statement", ""),
            actor=session.get("username", "reviewer"),
            evidence_item_ids=request.form.getlist("evidence_item_ids"),
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer
        flash(str(exc), "error")
    return redirect(url_for("help_center.authoring_edit", script_id=script_id))


@help_bp.route("/help/authoring/scripts/<script_id>/recheck", methods=["POST"])
@login_required
def authoring_recheck(script_id):
    """Re-check from the editor, and come back to the editor.

    Deliberately a sibling of the JSON `script_recheck` rather than content
    negotiation on it. They run the identical chain via `_run_chain` and differ
    only in what they hand back: one serves the concierge, which wants the
    detailed result; this one serves a person who pressed a button and needs to
    be returned to the page they pressed it on. Branching a single route on an
    Accept header would have made the reviewer's outcome depend on a header they
    never see, which is how a button silently starts rendering JSON.
    """
    _require_reviewer()
    store = _help_store()
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    if store.get_work_product(workspace, script_id) is None:
        abort(404)

    result = _run_chain(store, workspace, script_id)
    chain = result["chain"]
    flash(f"Re-checked: {result['status']['label']}.", "info")
    # Say which stage stopped it, not merely that something did - "blocked" with
    # no name sends the reviewer back to re-read the whole Script.
    for stage in chain.get("could_not_run") or []:
        flash(f"Could not run: {stage}. This is not a pass.", "error")
    if chain.get("blocked_by"):
        flash(f"Blocked by: {chain['blocked_by']}.", "error")
    return redirect(url_for("help_center.authoring_edit", script_id=script_id))


@help_bp.route("/help/authoring/scripts/<script_id>/validate", methods=["POST"])
@login_required
def authoring_validate(script_id):
    """The human authority transition, and the only one.

    Deliberately separate from Re-check and from claim adoption: a reviewer
    validating the writing is not the same act as accepting the claims beneath
    it, and collapsing them would let one click do both. Readiness is still
    derived - this records a decision, it does not set a state.
    """
    _require_reviewer()
    store = _help_store()
    workspace = store.get_or_create(HELP_LIBRARY_PROJECT_ID)
    if store.get_work_product(workspace, script_id) is None:
        abort(404)
    decision = request.form.get("decision", SCRIPT_VALIDATION_VALIDATED)
    try:
        store.record_script_validation(
            workspace, work_product_id=script_id, decision=decision,
            actor=session.get("username", "reviewer"),
            comments=request.form.get("comments") or None,
        )
    except Exception as exc:  # noqa: BLE001
        flash(str(exc), "error")
    return redirect(url_for("help_center.authoring_edit", script_id=script_id))
