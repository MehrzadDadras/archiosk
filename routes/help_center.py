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

from flask import Blueprint, abort, current_app, jsonify, render_template, request

from services.auth import is_admin, login_required
from services.case_workspace import CaseWorkspaceStore
from services.script_fit import help_status_for, run_script_trust_chain

help_bp = Blueprint("help_center", __name__)

# CLAUDE-HELP-CONCIERGE-01: Help Scripts are ordinary governed WorkProducts, so
# they need a project to live in - but they are about the PRODUCT, not about any
# customer project, and putting them in a real one would make product
# documentation part of that project's evidence corpus. A single reserved
# workspace keeps them governed by exactly the same kernel while belonging to no
# customer project. It is a project id, not a new subsystem: every Script in it
# is a normal WorkProduct read by the normal store.
HELP_LIBRARY_PROJECT_ID = "archiosk-help-library"


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
    return render_template("help/index.html", guides=GUIDES)


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
