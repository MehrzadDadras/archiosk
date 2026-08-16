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
import json
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
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from PIL import Image
from werkzeug.utils import secure_filename

from services.auth import admin_required, is_admin, login_required, user_can_upload_to_storage
from services.case_workspace import (
    ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
    ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
    ANALYSIS_TRIGGER_USER_INITIATED,
    BUILT_IN_TAGS,
    CASE_OUTCOME_STATES,
    CASE_ORIGIN_AUTONOMOUS,
    CASE_STATUS_ARCHIVED,
    CONTENT_CLASS_DETERMINISTIC_CALCULATION,
    CONTENT_CLASS_HUMAN_AUTHORED,
    CONVERSATION_ANCHOR_SCOPE_CASE,
    CONVERSATION_ANCHOR_SCOPE_GUIDANCE,
    CONVERSATION_ANCHOR_SCOPE_PROJECT,
    CONVERSATION_GUIDANCE_PROJECT_INTRO,
    DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED,
    DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED,
    KNOWN_DOCUMENT_CONTEXT_FIELDS,
    FOLDER_ROOT_DATA_ROOM,
    FOLDER_ROOT_DESIGN_BUILDER,
    KNOWN_FOLDER_ROOTS,
    GO_NO_GO_DECISIONS,
    KNOWN_ADJUDICATION_ATTRIBUTIONS,
    KNOWN_CONTENT_CLASSES,
    KNOWN_CONVERSATION_ANCHOR_SCOPES,
    KNOWN_PARTICIPANT_ROLES,
    KNOWN_PERSPECTIVE_POLARITIES,
    KNOWN_RESOLUTION_OUTCOMES,
    MESSAGE_ORIGIN_HUMAN,
    OBJECT_KIND_CASE,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_REQUIREMENT,
    PERSPECTIVE_ORIGIN_HUMAN,
    REQUIREMENT_ADJUDICATION_NOT_SATISFIED,
    REQUIREMENT_ADJUDICATION_OUTCOMES,
    REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED,
    REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    REQUIREMENT_STATUS_SUPERSEDED,
    SOURCE_KIND_DRAWING,
    SOURCE_KIND_PROJECT_DOCUMENT,
    SOURCE_KIND_TEXT_RECORD,
    TAG_COLOR_PALETTE,
    TASK_STATUS_COMPLETED,
    Anchor,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DISPOSITIONS,
    OperatingEnvironmentAlreadySetError,
    REVIEWER_VALIDATION_STATES,
    resolve_requirement_adjudication_attribution,
    assess_document_context_quality,
)
from services.environment_capabilities import (
    OPERATING_ENVIRONMENT_LABELS,
    allowed_participant_roles,
    capability_availability,
    capability_denial_reason,
    decision_stages_for_environment,
    is_valid_operating_environment,
)
from services.document_context_intelligence import draft_document_context_claims
from services.conversation_interpreter import (
    _looks_like_contextual_reference,
    _looks_like_conversational_utterance,
    _looks_like_orientation_request,
    _looks_like_project_question,
    _looks_like_what_next,
    _resolve_anchor_object,
    compute_organize_groups,
    interpret_message,
)
from services.governance import GovernanceLog
from services.ingestion import UploadError, document_source_payload, get_registry, reconcile_data_room_upload, reject_if_display_name_taken
from services.investigation_snapshot import build_archive_snapshot
from services.project_clock import open_project
from services.rfi_export import RFIExportError, build_rfi_docx, build_rfi_draft_docx
from services.work_product_export import WorkProductExportError, export_work_product
from models import User

workspace_bp = Blueprint("workspace", __name__)

# CLAUDE-SPIN-00A: representative, deliberately noncanonical prototype
# discipline labels for the Spin container comparison exercise only -
# never written into any real project's own data, never treated as a
# governed concept (contrast with the real, stored `operating_environment`
# or `participant` roles elsewhere in this module). Kept here, at the
# route layer, rather than in services/case_workspace.py, specifically so
# it never reads as part of the domain model.
SPIN_PROTOTYPE_DISCIPLINES = (
    "Architecture", "Structural", "Mechanical", "Electrical", "Plumbing",
    "Civil", "Landscape", "Interior Design", "Fire Protection", "Security",
    "AV / IT", "Specifications", "Commissioning",
)

ALLOWED_DRAWING_EXTENSIONS = {".png", ".jpg", ".jpeg"}
# CLAUDE-MM3: .xlsx added here (Add Documents, an existing-project Source),
# deliberately NOT to ingestion.py's own ALLOWED_UPLOAD_EXTENSIONS (project
# creation) - a spreadsheet is not an RFP/RFQ-shaped text document, and
# routing it through BHiveParser's requirement-extraction/classification
# pipeline (already flagged, across many prior stages, as fragile and
# adversarially-tuned) would be exactly the kind of forced-fit this stage's
# own "do not force all spreadsheet work into native records" caution
# argues against. A project must already exist (from an ordinary text
# document) before a workbook can be added - the same precedent drawing/
# image intake already established for a different non-text format.
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".txt", ".csv", ".md", ".xlsx"}

# CLAUDE-P40-VW8-QA1 (Governed Display Tab System sufficiency review): the
# registered vocabulary of "stable Display kinds" - a Project-level
# singleton surface with no open/close, no pinning, no tab-strip pill
# (show_workspace's own ?view= comment below explains why this is
# deliberately NOT a second browsable directory in Display). Overview is
# the only one implemented today; this dict is what the ?view= whitelist
# below AND the shared breadcrumb/division-0-header label both derive
# from. Before this stage, "Overview" was three independent string
# literals (the whitelist tuple, base.html's breadcrumb, case_workspace
# .html's division header) that had to be kept in sync by hand with
# nothing enforcing it - this is the single source of truth a second
# stable kind (e.g. a future dedicated Files Display tab) would register
# into, so adding one is one new entry here, not three independently-
# maintained literals. Registering a key here does NOT give it any real
# content - see the dedicated `directory_view == 'overview'` branches in
# case_workspace.html for that; this dict controls only the kind's name/
# identity, never what renders inside it.
STABLE_DIRECTORY_KINDS = {
    "overview": "Overview",
    # CLAUDE-P40-VW9 (Governed Files Display and Project File
    # Architecture): the first real second entry in this registry -
    # exactly the extension point CLAUDE-P40-VW8-QA1 built this dict
    # for. A Project-level stable singleton, same shape as Overview (no
    # tab-strip pill, no duplicate-open concept) - its own content
    # branch below (`directory_view == 'files'`) renders the two
    # governed sibling roots (Data Room, Design-Builder Workspace).
    "files": "Files",
    # CLAUDE-POSTCAMEL-ROOT-I1: Requirements was a real, fully governed,
    # already-IMPLEMENTED project object (register/promote/adjudicate/
    # revise all pre-existing and unchanged by this stage) with NO
    # navigable home of its own - reachable only by scrolling Overview's
    # own accordion stack. Same stable-singleton shape as Files above
    # (Project-scoped, no per-instance id, no duplicate-open concept).
    # Its own content branch below (`directory_view == 'requirements'`)
    # is the exact same accordion markup Overview used to render
    # in-place - a relocation, not a reimplementation; every view
    # variable (requirements_view/compliance_rollup/
    # unpromoted_requirement_items/revisited_requirements_count) was
    # already computed unconditionally on every render, so no new
    # computation was needed to give it a real URL.
    "requirements": "Requirements",
}

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

# CLAUDE-POSTCAMEL-COMM-I5A: display-only labels for
# resolve_requirement_adjudication_attribution's three real return
# values - never a fourth "looks human by default" option.
_ADJUDICATION_ATTRIBUTION_LABELS = {
    ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED: "Human-reviewed",
    ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT: "Agent assessment",
}


def _with_attribution_label(adjudication: dict) -> dict:
    attribution = resolve_requirement_adjudication_attribution(adjudication)
    return {
        **adjudication,
        "attribution_label": _ADJUDICATION_ATTRIBUTION_LABELS.get(attribution, "Unknown/legacy provenance"),
    }


def _store() -> CaseWorkspaceStore:
    return CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])


def _json_script_safe(value) -> str:
    """CLAUDE-P40-E2B, Section D: for embedding inside a
    <script type="application/json"> data island (the Display-division
    picker's own source list) - a Source name is user-controlled (an
    uploaded filename, or a text-record title), so a plain json.dumps
    is not enough on its own; escaping "<"/">"/"&" as \\uXXXX prevents
    a name containing "</script>" from ever breaking out of the tag,
    the standard mitigation for JSON embedded in HTML."""
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def _reviewer() -> str:
    return session.get("username") or "anonymous"


def _log() -> GovernanceLog:
    return GovernanceLog(current_app.config["REGISTRY_STORE_PATH"])


def _load_workspace_or_404(project_id: str, allow_removed: bool = False):
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

    CLAUDE-P40-E2A, Section A: authorization and lifecycle are different
    checks. An authorized (P32-passing) caller reaching a REMOVED
    project's route is redirected here to the one tombstone view
    (show_workspace itself, which renders "Project removed" instead of
    the active Workspace when it detects this) rather than being allowed
    to continue into whatever mutation/read that route was about to do -
    this is the single choke point every child Document/Investigation
    route already passes through, so blocking here means every one of
    them inherits the removed state automatically, with no per-route
    change needed. `allow_removed=True` is the deliberate, narrow
    exception, used only by show_workspace itself (to render the
    tombstone) and restore_project_route (the one action that must keep
    working on a removed project). An unauthorized caller still gets the
    existing fail-closed 404 above, unaffected by any of this - the
    removed-state check only runs for a caller who already passed P32.
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

    if workspace.removed_at and not allow_removed:
        flash("This Project has been removed. Restore it to resume work.", "error")
        abort(redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview")))

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


def _work_product_case_id(workspace, work_product_id):
    """The WorkProduct's OWN recorded case_id (may legitimately be None -
    a Project-level work product), looked up server-side for the same
    reason as _finding_case_id/_rfi_draft_case_id: a route keyed by
    work_product_id must never trust a caller-supplied case_id for its
    own authorization decision."""
    work_product = next((w for w in workspace.work_products if w["id"] == work_product_id), None)
    return work_product.get("case_id") if work_product else None


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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
    document, store, workspace = _load_workspace_or_404(project_id, allow_removed=True)

    # CLAUDE-P40-E2A, Section A: a removed Project's authorized direct
    # URL shows a restrained tombstone, never the active Workspace -
    # returned here, before any of the active-workspace computation
    # below runs (findings_view/active_case/etc. would be meaningless
    # for a Project that's out of active use). Restoration is the one
    # action offered; every other mutation an authorized user might try
    # is already blocked one layer down, at _load_workspace_or_404
    # itself (see that function's own docstring).
    if workspace.removed_at:
        return render_template(
            "project_removed.html",
            project_id=project_id,
            display_name=(workspace.display_title or document.filename),
            removed_at=workspace.removed_at,
            removed_by=workspace.removed_by,
            removal_reason=workspace.removal_reason,
        )

    # CLAUDE-P40-E: ?source=<id> opens a document/drawing directly inside
    # the Workspace pane (Section D) - resolved only against THIS
    # already-authorized project's own workspace.sources (never a raw
    # id trusted from the query string on its own), so project
    # authorization is enforced the same way every other object on this
    # page already is. None (not 404) for an unknown/foreign id - same
    # "degrade to nothing selected" convention preview_finding_id and
    # the Snapshot query params below already use, not a hard error for
    # a stale/guessed link.
    selected_source_id = request.args.get("source")
    selected_source = next(
        (s for s in workspace.sources if s["id"] == selected_source_id), None,
    ) if selected_source_id else None

    # Bounded GO QA/QC pass (Section 4/11): Admin Document Mode data for
    # the active Source - computed only for admins, never for an ordinary
    # PM/reviewer page load ("ordinary PM/user-facing document view
    # should remain simple"). Document-level claims only here (page_
    # anchor=None) - a page-scoped view is explicitly deferred, this pass
    # only preserves the anchor for a future rollup, it does not build one.
    document_context_claims_view = []
    document_context_quality = None
    if selected_source and is_admin():
        # document_context_claims_for's own default (page_anchor=None)
        # already means "document-level only" - no post-filter needed here.
        document_context_claims_view = store.document_context_claims_for(workspace, selected_source["id"])
        document_context_quality = assess_document_context_quality(
            document_context_claims_view,
            extraction_signal=store.extraction_signal_for_source(workspace, selected_source["id"]),
        )

    # CLAUDE-SPIN-00A: an explicit, session-less, unpersisted request flag -
    # deliberately NOT routed through _set_persisted_selection below (this
    # is a container/interaction-selection prototype, not a real project
    # selection; nothing here should survive as "professional context").
    # Reuses the exact same already-authorized `document`/`workspace`
    # this route already loaded - no new authorization surface.
    spin_mode = request.args.get("spin") == "1"

    # CLAUDE-POSTCAMEL-CA1B (Section 2/3): same "?<id> selection, resolved
    # only against THIS already-authorized project's own workspace list,
    # None for an unknown/foreign id" convention as ?source= above -
    # gives Requirement/Finding the same real, bookmarkable, project-
    # scoped selection Source already had, rather than a second, bespoke
    # mechanism.
    selected_requirement_id = request.args.get("requirement")
    selected_requirement = next(
        (r for r in workspace.requirements if r["id"] == selected_requirement_id), None,
    ) if selected_requirement_id else None

    selected_finding_id = request.args.get("finding")
    selected_finding = next(
        (f for f in workspace.findings if f["id"] == selected_finding_id), None,
    ) if selected_finding_id else None

    # CLAUDE-POSTCAMEL-CA1B (Section 5, context precedence): visiting a
    # real ?source=/?requirement=/?finding= URL is an explicit current
    # selection - it persists as this Project's "professional context"
    # (session-scoped, mirroring the pre-existing focused_finding:
    # pattern) so it survives ordinary navigation away and back, not
    # merely this one request. Only one wins per visit - Source first
    # (existing precedent), matching this route's own established "a
    # real selection always wins over ?view=" precedence note below.
    if selected_source is not None:
        _set_persisted_selection(project_id, "source", selected_source["id"])
    elif selected_requirement is not None:
        _set_persisted_selection(project_id, "requirement", selected_requirement["id"])
    elif selected_finding is not None:
        _set_persisted_selection(project_id, "finding", selected_finding["id"])

    # CLAUDE-POSTCAMEL-CA1B (Section 8, selection visibility): a small,
    # truthful "what does ARCHIOSK consider selected" label - resolved
    # read-time, every render, through the same real per-workspace
    # lookup the conversational layer itself uses
    # (_resolve_anchor_object), so a stale/deleted persisted selection
    # never renders as if it still existed (Section 2's own "does not
    # silently preserve stale selection after deletion/removal").
    current_context = None
    _persisted = _get_persisted_selection(project_id)
    if _persisted:
        _ctx_type, _ctx_object = _resolve_anchor_object(workspace, _persisted)
        if _ctx_object is not None:
            if _ctx_type == "requirement":
                current_context = {"type": "Requirement", "label": _ctx_object["original_requirement_identifier"]}
            elif _ctx_type == "finding":
                current_context = {"type": "Finding", "label": _ctx_object["statement"][:60]}
            elif _ctx_type == "source":
                current_context = {"type": "Source", "label": _ctx_object["name"]}

    # CLAUDE-MM8: ?work_product=<id> opens a governed work product
    # directly inside the Workspace pane, same "?<id> selection, resolved
    # only against THIS already-authorized project's own workspace list,
    # None (not 404) for an unknown/foreign id" convention selected_source
    # already established above.
    selected_work_product_id = request.args.get("work_product")
    selected_work_product = next(
        (w for w in workspace.work_products if w["id"] == selected_work_product_id), None,
    ) if selected_work_product_id else None
    selected_work_product_status = (
        store.resolve_work_product_status(workspace, selected_work_product_id)
        if selected_work_product else None
    )
    selected_work_product_stale = (
        store.stale_evidence_for_work_product(workspace, selected_work_product_id)
        if selected_work_product else None
    )

    # CLAUDE-P40-E3A, Section 5: "Overview" is now the one remaining leaf
    # that projects real content into Display via this ?view= query-string
    # vocabulary - Documents/Investigations/RFIs/Chats used to be separate
    # ?view= directory bodies here too (CLAUDE-P40-E2B1) but are removed
    # outright now that their names live only in Lists' own recursive
    # hierarchy (base.html) - showing them here as well would be the "second
    # navigation directory in Display" Section 4 explicitly forbids. A real
    # ?case=/?source= selection always wins over ?view=overview (Display
    # must show whichever leaf was actually clicked). Unknown/stale values
    # (including the three retired ones, for any old bookmark/link) degrade
    # to no directory - Display renders genuinely blank, matching Section
    # 5's own "if no leaf or action is selected" rule, the same honest
    # degrade convention selected_source/active_case already use.
    directory_view = request.args.get("view")
    # CLAUDE-P40-VW8-QA (New Investigation Action in Lists): a focused
    # CREATE FORM, not a browsable directory - deliberately a separate
    # flag from directory_view (never itself a value directory_view can
    # take), so it can never be mistaken for, or accidentally widen, the
    # "?view= is the one directory vocabulary, Overview only" rule the
    # comment above this one already establishes. Same precedence rules
    # as directory_view below (a real ?case=/?source= selection wins).
    show_new_case_form = request.args.get("view") == "new-case"
    # CLAUDE-POSTCAMEL-INVESTIGATION-AR1: same shape as show_new_case_form
    # immediately above - a focused CHOOSER, not a browsable directory,
    # so it stays its own flag rather than a directory_view value (see
    # that flag's own comment on why "+ New Investigation" already
    # avoided directory_view for exactly this reason).
    show_continue_from_archive = request.args.get("view") == "continue-from-archive"
    if directory_view not in STABLE_DIRECTORY_KINDS:
        directory_view = None
    # CLAUDE-P40-VW8-QA1: the one shared label breadcrumb/division-header
    # both read (see STABLE_DIRECTORY_KINDS' own comment above) - None
    # whenever directory_view itself is None, matching every other
    # "nothing selected" degrade in this route.
    directory_view_label = STABLE_DIRECTORY_KINDS.get(directory_view)

    # CLAUDE-P40-VW7B: "panel" rendering - the exact same authorization,
    # data computation, and Division-0 content this route already
    # produces, wrapped in templates/panel_shell.html (a minimal
    # standalone document) instead of base.html's full application
    # shell. This is what makes "a leaf selection projects into the
    # active Display" honest for an Investigation/Overview the same way
    # it already was for a Document (a real file, embedded via a plain
    # <iframe src=...>) - static/js/case_workspace.js's own
    # ArchioskDisplay.populateDivision builds an <iframe> pointing at
    # this same URL with &panel=1 appended, for whichever non-zero
    # Display is currently the active target. No new route, no
    # duplicated access-control logic: an unauthorized request to
    # ?panel=1 fails at the exact same _load_workspace_or_404 call
    # above that already gates every other view of this same data.
    panel_only = request.args.get("panel") == "1"

    # CLAUDE-P40-E3A follow-through: every Project-level (non-case/source-
    # scoped) POST handler in this module that used to redirect back to a
    # bare show_workspace(project_id=...) - which, before this stage,
    # landed on Project Home by default - now explicitly passes
    # view="overview" instead, so the reviewer actually sees the result of
    # the action they just took (the updated Sources list, the new star
    # state, the saved instructions, ...) rather than the new blank
    # default. This is a required consequence of Section 5's "blank
    # unless a leaf is selected" rule, not a new feature: without it, a
    # completed action would silently redirect into a blank Display with
    # no visible confirmation beyond the flash message.

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

    # A real ?case=/?source= selection always takes priority over a bare
    # directory view - see the ?view= comment above.
    if active_case is not None or selected_source is not None:
        directory_view = None
        directory_view_label = None
        show_new_case_form = False
        show_continue_from_archive = False

    # CLAUDE-P40-VW9: Files - the Design-Builder Workspace's own
    # "which folder is currently open" browsing state, resolved only
    # when Files is actually the active directory view (the same
    # "only ever resolved against this already-authorized workspace's
    # own records, never a raw trusted id" convention selected_source/
    # active_case already use above). An unknown/stale/foreign
    # ?folder= degrades honestly to the Design-Builder Workspace root
    # - never a crash, never a lookup that leaks another Project's own
    # data, matching this route's own established degrade convention
    # throughout.
    open_folder = None
    folder_ancestors: list = []
    design_builder_children: list = []
    design_builder_move_targets: dict = {}
    data_room_sources: list = []
    open_data_room_folder = None
    data_room_folder_ancestors: list = []
    data_room_children: list = []
    data_room_folder_sources: list = []
    data_room_unfiled_sources: list = []
    if directory_view == "files":
        requested_folder_id = request.args.get("folder")
        if requested_folder_id:
            candidate = next(
                (
                    f for f in workspace.folders
                    if f["id"] == requested_folder_id and f["root"] == FOLDER_ROOT_DESIGN_BUILDER
                    and not f.get("removed_at")
                ),
                None,
            )
            open_folder = candidate
        folder_ancestors = store._folder_path(workspace, open_folder["id"] if open_folder else None)
        open_folder_id = open_folder["id"] if open_folder else None
        design_builder_children = sorted(
            (
                f for f in workspace.folders
                if f["root"] == FOLDER_ROOT_DESIGN_BUILDER and f.get("parent_folder_id") == open_folder_id
                and not f.get("removed_at")
            ),
            key=lambda f: f["name"].lower(),
        )
        # Data Room compatibility view (Section 7): every existing
        # active Source, exactly as Documents already lists them -
        # never reclassified, never assigned a folder, never
        # duplicated. Honest about what this is: the pre-Files system's
        # own existing Documents, not the future issued hierarchy.
        data_room_sources = [s for s in workspace.sources if not s.get("removed_at")]

        # CLAUDE-RFP27-TERRITORY-01 (Part 3/5): the real, governed Data
        # Room hierarchy, once CaseWorkspaceStore.ensure_folder_path/
        # reconcile_data_room_upload have actually populated it - read-
        # only navigation (no rename/move/delete controls, unlike Design-
        # Builder above: this root is externally issued, never reorganized
        # from inside ARCHIOSK - create_folder's own docstring). Same
        # `?data_room_folder=<id>` query-param idiom as Design-Builder's
        # own `?folder=<id>`, deliberately a SEPARATE param so the two
        # roots' own navigation states never collide when both are
        # rendered on the same page.
        requested_data_room_folder_id = request.args.get("data_room_folder")
        if requested_data_room_folder_id:
            dr_candidate = next(
                (
                    f for f in workspace.folders
                    if f["id"] == requested_data_room_folder_id and f["root"] == FOLDER_ROOT_DATA_ROOM
                    and not f.get("removed_at")
                ),
                None,
            )
            open_data_room_folder = dr_candidate
        data_room_folder_ancestors = store._folder_path(workspace, open_data_room_folder["id"] if open_data_room_folder else None)
        open_data_room_folder_id = open_data_room_folder["id"] if open_data_room_folder else None
        data_room_children = sorted(
            (
                f for f in workspace.folders
                if f["root"] == FOLDER_ROOT_DATA_ROOM and f.get("parent_folder_id") == open_data_room_folder_id
                and not f.get("removed_at")
            ),
            key=lambda f: f["name"].lower(),
        )
        data_room_folder_sources = [
            s for s in data_room_sources if s.get("folder_id") == open_data_room_folder_id
        ] if open_data_room_folder_id else []
        # Root-level only: Sources with no folder_id at all - the exact
        # "existing pre-Files identity, not yet organized" compatibility
        # set Section 7 originally introduced, now honestly scoped to
        # ONLY the still-unfiled subset rather than every Source.
        data_room_unfiled_sources = [s for s in data_room_sources if not s.get("folder_id")]

        # Move-target candidates per visible folder row: every OTHER
        # active Design-Builder folder in the project, excluding the
        # folder itself and its own descendants (Section 5's own
        # "prevent invalid cycles") - computed server-side so the
        # picker never even OFFERS an invalid destination, on top of
        # move_folder's own independent, authoritative re-validation.
        all_active_design_builder_folders = sorted(
            (f for f in workspace.folders if f["root"] == FOLDER_ROOT_DESIGN_BUILDER and not f.get("removed_at")),
            key=lambda f: f["name"].lower(),
        )
        # CLAUDE-P40-VW9A (Files Cockpit Close-Out, A2): sibling-scoped
        # uniqueness (CaseWorkspaceStore._reject_if_sibling_folder_name_
        # taken) means two DIFFERENT branches can legitimately hold a
        # same-named folder - the picker used to show bare candidate
        # names, so those pairs were visually indistinguishable even
        # though the submitted <option value> (folder id) was always
        # correct underneath. path_label is a display-only breadcrumb
        # (root-most first, via the same store._folder_path() the
        # in-page breadcrumb above already uses) built fresh here, never
        # written back onto the candidate dict - the authoritative
        # target is still, and only, the id.
        design_builder_move_targets = {
            child["id"]: [
                {
                    "id": candidate["id"],
                    "path_label": " › ".join(
                        ancestor["name"] for ancestor in store._folder_path(workspace, candidate["id"])
                    ),
                }
                for candidate in all_active_design_builder_folders
                if candidate["id"] != child["id"]
                and candidate["id"] not in store._folder_descendant_ids(workspace, child["id"])
            ]
            for child in design_builder_children
        }

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

    # CLAUDE-POSTCAMEL-INVESTIGATION-AR1: the "Continue from Archive"
    # chooser's own list - archived Cases this reviewer can see (already
    # Case-privacy-filtered by visible_cases_for above). `workspace` is
    # already this one Project's own loaded CaseWorkspaceStore state, so
    # there is structurally no query here that could reach an archived
    # Case belonging to a different Project. A cheap finding count per
    # archived Case, computed once here rather than once per template row.
    archived_visible_cases = [c for c in visible_cases if c["status"] == CASE_STATUS_ARCHIVED]
    case_finding_counts = {
        c["id"]: sum(1 for f in workspace.findings if f["case_id"] == c["id"])
        for c in archived_visible_cases
    }

    # CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01: computed unconditionally, like
    # open_visible_cases/archived_visible_cases above - the top-bar
    # Project Context control (templates/base.html) must stay reachable
    # from every workspace surface, not just Overview, so every render
    # of this route needs these two view-model values available.
    project_context_entries = store.project_context_entries_for(workspace)
    current_project_context = project_context_entries[-1] if project_context_entries else None
    project_context_history = list(reversed(project_context_entries[:-1]))

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

    # CLAUDE-GO-RIGHT-PANEL-01: the project-scoped, Composer-emitted
    # counterpart to the Case-scoped findings_view above - see
    # services.case_workspace.ComposerFinding's own docstring for why
    # these are a distinct object. Newest-first, matching how every
    # other reverse-chronological list in this Toolbox already orders
    # (Investigations, RFIs) - a PM cares about the most recently
    # surfaced characterization first. Sequential display numbers
    # (F-001, F-002, ...) are computed here from stable creation order
    # (oldest first) rather than stored on the record itself - display
    # numbering is a presentation concern, not part of the record's own
    # identity (the real id is still the UUID).
    composer_findings_view = [
        {**cf, "display_id": f"F-{idx:03d}"}
        for idx, cf in enumerate(workspace.composer_findings, start=1)
    ][::-1]

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
            "latest_adjudication": (
                _with_attribution_label(evidence["adjudication"]) if evidence["adjudication"] else None
            ),
            # Full history, not just latest - the data was always
            # non-destructively preserved (requirement_adjudications_for
            # already existed, unused by any route or template); this was
            # a rendering gap, not a storage gap. Surfacing it is the
            # "what has this project already taught us to re-check" view:
            # honest re-display of what actually happened, not a new
            # inferred pattern/suggestion layered on top of it.
            "adjudication_history": [
                _with_attribution_label(a)
                for a in store.requirement_adjudications_for(workspace, requirement["id"])
            ],
            "evidence_findings": evidence_findings_view,
            "evidence_relationships": evidence_relationships_view,
            # Bounded GO QA/QC pass (Section 1-3): the Requirement's own
            # latest phase-aware conformance assessment, if GO has ever
            # produced one - a passive read (requirement_phase_assessments_
            # for is never called automatically on page load; a new
            # assessment only happens via the explicit "Assess phase
            # conformance" action below), so this adds no per-request cost
            # to a Requirement nothing has assessed yet. None entirely for
            # a non-admin - this is Admin Document Mode data.
            "latest_phase_assessment": (
                store.latest_requirement_phase_assessment_for(workspace, requirement["id"])
                if is_admin() else None
            ),
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

    # CLAUDE-POSTCAMEL-ROOT-I2: Requirements 3.3 Compliance rollup - a
    # projection over the SAME requirements_view/compliance_rollup already
    # computed above, never a second compliance record and never a new
    # field on Requirement. Two buckets, kept explicitly separate per
    # ROOT-A2's own "unknown is not non-compliant" rule: awaiting_review
    # (no RequirementAdjudication on file yet) must never be folded into
    # attention (an adverse/uncertain human determination - Not Satisfied/
    # Partially Satisfied). Satisfied/Not Applicable/Accepted Alternative
    # are settled and deliberately get no source breakdown of their own -
    # only the two buckets a reviewer actually needs to act on do (source
    # awareness scoped to what's operationally useful, not applied
    # everywhere merely because it's possible).
    _COMPLIANCE_ATTENTION_OUTCOMES = (
        REQUIREMENT_ADJUDICATION_NOT_SATISFIED,
        REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED,
    )
    _compliance_source_lookup = {s["id"]: s for s in store.active_sources(workspace)}

    def _compliance_source_breakdown(rows):
        counts: dict[str, int] = {}
        for row in rows:
            source_id = row["requirement"]["source_id"]
            counts[source_id] = counts.get(source_id, 0) + 1
        breakdown = [
            {
                "source_id": source_id,
                "name": _compliance_source_lookup[source_id]["name"]
                if source_id in _compliance_source_lookup else "(removed Source)",
                "count": count,
            }
            for source_id, count in counts.items()
        ]
        breakdown.sort(key=lambda entry: entry["count"], reverse=True)
        return breakdown

    _awaiting_review_rows = [
        row for row in requirements_view
        if row["adjudication_state"] == REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED
    ]
    _attention_rows = [
        row for row in requirements_view
        if row["adjudication_state"] in _COMPLIANCE_ATTENTION_OUTCOMES
    ]
    compliance_view = {
        "total": len(requirements_view),
        "awaiting_review_count": len(_awaiting_review_rows),
        "attention_count": len(_attention_rows),
        "awaiting_review_by_source": _compliance_source_breakdown(_awaiting_review_rows),
        "attention_by_source": _compliance_source_breakdown(_attention_rows),
        # The exact, real vocabulary values (never re-typed literals in the
        # template) - a drill-through link built from these always matches
        # a real requirement_adjudication_state exactly.
        "awaiting_review_state": REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED,
        "attention_states": list(_COMPLIANCE_ATTENTION_OUTCOMES),
    }

    # Drill-through (compliance summary -> underlying Requirements): an
    # optional ?status= filter narrows which rows the "Governed
    # Requirements" detail list below actually renders. compliance_view/
    # compliance_rollup above always reflect the TRUE, unfiltered project
    # totals regardless of this filter, so the summary can never be made
    # to lie by a stale filter link. Absent ?status=, every governed
    # Requirement renders exactly as before this change - ROOT-I1's own
    # existing tests depend on that default being unchanged.
    compliance_status_filter = request.args.get("status")
    if compliance_status_filter:
        requirements_view_display = [
            row for row in requirements_view if row["adjudication_state"] == compliance_status_filter
        ]
    else:
        requirements_view_display = requirements_view

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

    # CLAUDE-MM8: Lists' own Work Products branch - same Case-privacy
    # filter as RFIs above, plus Project-level work products (case_id is
    # None), which carry no Case to hide behind and are visible to anyone
    # who can already see this Project.
    work_products_view = sorted(
        (w for w in workspace.work_products if not w.get("case_id") or w["case_id"] in visible_case_ids),
        key=lambda w: w["modified_at"], reverse=True,
    )

    # CLAUDE-P40-VW7: Tasks/Tags read-side views for the Lists Tasks/Tags
    # branches - navigation URL and source-availability computed once
    # here (never in the template) so "Source unavailable" (Section 4's
    # own explicit requirement) is decided against the SAME workspace
    # state being rendered, not re-derived client-side.
    tasks_view = sorted(
        (
            {**task, "source_url": _conversation_source_url(project_id, task["source_anchor"]),
             "source_available": store.resolve_conversation_anchor(workspace, task["source_anchor"])}
            for task in workspace.tasks
        ),
        key=lambda row: row["created_at"], reverse=True,
    )
    tasks_open_view = [t for t in tasks_view if t["status"] != TASK_STATUS_COMPLETED]
    tasks_completed_view = [t for t in tasks_view if t["status"] == TASK_STATUS_COMPLETED]

    _tag_groups_by_id: dict[str, dict] = {}
    for occ in workspace.tag_occurrences:
        tag = store.resolve_tag(workspace, occ["tag_id"])
        if tag is None:
            continue  # defensive - a tag_id that no longer resolves is never shown, never crashes
        group = _tag_groups_by_id.setdefault(occ["tag_id"], {"tag": tag, "occurrences": []})
        group["occurrences"].append({
            **occ,
            "source_url": _conversation_source_url(project_id, occ["source_anchor"]),
            "source_available": store.resolve_conversation_anchor(workspace, occ["source_anchor"]),
        })
    tag_groups_view = sorted(_tag_groups_by_id.values(), key=lambda g: g["tag"]["name"].lower())
    tag_occurrences_total = sum(len(g["occurrences"]) for g in tag_groups_view)
    available_tags_view = list(BUILT_IN_TAGS.values()) + store.list_custom_tags(workspace)

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
        open_visible_cases=open_visible_cases,
        archived_visible_cases=archived_visible_cases,
        case_finding_counts=case_finding_counts,
        active_case=active_case,
        selected_source=selected_source,
        current_context=current_context,
        directory_view=directory_view,
        directory_view_label=directory_view_label,
        open_folder=open_folder,
        folder_ancestors=folder_ancestors,
        design_builder_children=design_builder_children,
        design_builder_move_targets=design_builder_move_targets,
        data_room_sources=data_room_sources,
        open_data_room_folder=open_data_room_folder,
        data_room_folder_ancestors=data_room_folder_ancestors,
        data_room_children=data_room_children,
        data_room_folder_sources=data_room_folder_sources,
        data_room_unfiled_sources=data_room_unfiled_sources,
        show_new_case_form=show_new_case_form,
        show_continue_from_archive=show_continue_from_archive,
        current_project_context=current_project_context,
        project_context_history=project_context_history,
        needs_attention_view=needs_attention_view,
        findings_view=findings_view,
        composer_findings_view=composer_findings_view,
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
        requirements_view_display=requirements_view_display,
        compliance_rollup=compliance_rollup,
        compliance_view=compliance_view,
        compliance_status_filter=compliance_status_filter,
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
        work_products_view=work_products_view,
        selected_work_product=selected_work_product,
        selected_work_product_status=selected_work_product_status,
        selected_work_product_stale=selected_work_product_stale,
        known_content_classes=KNOWN_CONTENT_CLASSES,
        document_context_claims_view=document_context_claims_view,
        document_context_quality=document_context_quality,
        document_context_claim_accepted=DOCUMENT_CONTEXT_CLAIM_STATE_ACCEPTED,
        document_context_claim_rejected=DOCUMENT_CONTEXT_CLAIM_STATE_REJECTED,
        tasks_view=tasks_view,
        tasks_open_view=tasks_open_view,
        tasks_completed_view=tasks_completed_view,
        tag_groups_view=tag_groups_view,
        tag_occurrences_total=tag_occurrences_total,
        available_tags_view=available_tags_view,
        tag_color_palette=TAG_COLOR_PALETTE,
        conversation_guidance_key=CONVERSATION_GUIDANCE_PROJECT_INTRO,
        recent_focus_view=recent_focus_view,
        threads_view=threads_view,
        known_usernames=known_usernames,
        resolution_outcomes=KNOWN_RESOLUTION_OUTCOMES,
        project_home_summary=project_home_summary,
        since_last_visit=since_last_visit,
        project_conversation_view=project_conversation_view,
        project_conversation_count=len(workspace.project_conversation),
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
        # CLAUDE-P40-E2: "Remove Document" only changes LISTING/AI-context
        # visibility, never the underlying record (see CaseWorkspaceStore.
        # remove_source's own docstring) - the nav Sources list and the
        # Toolbox both read active_sources, never workspace.sources
        # directly, so a removed Document quietly stops appearing without
        # its record, id, or any Finding/Requirement that cites it changing
        # at all. removed_sources feeds the Toolbox's own "Removed
        # Documents" tool.
        active_sources=CaseWorkspaceStore.active_sources(workspace),
        removed_sources=CaseWorkspaceStore.removed_sources(workspace),
        is_project_removed=bool(workspace.removed_at),
        # CLAUDE-P40-E2B, Section D: the Display-division picker's own
        # client-side data source - see _json_script_safe's own
        # docstring. file_url is already resolved through the SAME
        # authorized source_file route every ?source= view uses.
        # CLAUDE-P40-LTH1: "is_pdf" added (same file_path.lower().
        # endswith('.pdf') test templates/case_workspace.html's own
        # Display branch already uses to decide whether to render the
        # PDF canvas) so static/js/pdf_viewer.js can validate a
        # remembered "last-viewed Document" against this SAME
        # authorized/Project-scoped list before attempting to load its
        # thumbnails on a page with no active Document selection - never
        # a second, separately-trusted source of truth about which
        # Sources exist or are a PDF.
        active_sources_json=_json_script_safe([
            {
                "id": s["id"],
                "name": s["name"],
                "kind": s["kind"],
                "file_url": url_for("workspace.source_file", project_id=project_id, source_id=s["id"]),
                "is_pdf": bool(s.get("file_path") and s["file_path"].lower().endswith(".pdf")),
            }
            for s in CaseWorkspaceStore.active_sources(workspace)
        ]),
        # CLAUDE-P40-VW7B, Section 8: the Investigation Attention strip's
        # own client-side data source - the SAME authorized/privacy-
        # filtered `visible_cases` list already computed above (never a
        # second, separately-trusted lookup of workspace.cases). Only
        # the fields the strip and the capacity-interruption dialog
        # actually need to render truthfully: no fabricated urgency or
        # confidence signal (Section 8's own explicit prohibition) -
        # "status" is the real CASE_STATUS_OPEN/CASE_STATUS_ARCHIVED
        # value, "created_by" lets the client decide whether to offer
        # the real archive_case action (still authorization-checked
        # server-side regardless - a client-side guess is only ever a
        # UX nicety here, never the actual boundary).
        visible_cases_json=_json_script_safe([
            {
                "id": c["id"],
                "title": c["title"],
                "status": c["status"],
                "created_by": c.get("created_by"),
            }
            for c in visible_cases
        ]),
        panel_only=panel_only,
        spin_mode=spin_mode,
        spin_disciplines=SPIN_PROTOTYPE_DISCIPLINES,
    )


@workspace_bp.route("/projects/<project_id>/workspace/cases", methods=["POST"])
@login_required
def create_case(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)

    # CLAUDE-P40-VW8-QA (New Investigation Action in Lists): this route
    # is unchanged/reused as-is (no parallel Investigation-creation
    # implementation) - the one addition is remembering whether the
    # SUBMITTING form came from the focused "+ New Investigation"
    # projection (a hidden field the new form below sets) so a
    # validation failure re-projects that SAME focused form instead of
    # the pre-existing Overview subdisclosure's own "?view=overview"
    # target. `panel` is preserved the same way VW7B's own panel_only
    # convention already works everywhere else - present only when the
    # request actually originated inside a projected iframe.
    from_new_case_form = request.form.get("source") == "new-case-form"
    panel_only = request.form.get("panel") == "1"
    extra_args = {"panel": "1"} if panel_only else {}

    title = (request.form.get("title") or "").strip()
    objective = (request.form.get("objective") or "").strip()
    if not title:
        flash("A Case needs a title.", "error")
        if from_new_case_form:
            return redirect(url_for("workspace.show_workspace", project_id=project_id, view="new-case", **extra_args))
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    case = store.create_case(workspace, title=title, objective=objective, created_by=_reviewer())

    _log().append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title, "visibility": case["visibility"]},
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"], **extra_args))


# -- Project Home: star, details, instructions, project-level Sources, Snapshot ----

@workspace_bp.route("/projects/<project_id>/workspace/star", methods=["POST"])
@login_required
def toggle_star(project_id):
    """Personal bookmark only - see CaseWorkspaceStore.set_starred. No
    governance meaning, no GovernanceLog event (Prompt 3 #3)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    store.set_starred(workspace, not workspace.starred)
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))
    if status == "require_approval" and (request.form.get("confirm") or "").strip() != "once":
        flash(
            f"AI Project Briefing awaits approval (controlling layer: {decision.controlling_layer}) "
            f"- {decision.reason} Use the approval action to proceed.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    # CLAUDE-P38-D2: duplicate-call/idempotency guard - a refresh, a
    # second reviewer, or the interstitial's own auto-submit firing
    # twice must never start a second real, billed call while one is
    # already in flight.
    if store.generation_in_progress_for(workspace):
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    from dataclasses import asdict

    workspace = store.get(project_id)  # re-fetch: version may have advanced since load
    store.set_project_briefing(
        workspace, briefing=asdict(result), source_signature=store.source_signature_for(workspace),
        actor=_reviewer(), governance_log=_log(),
    )
    flash("Project briefing generated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    store.set_project_details(
        workspace,
        actor=_reviewer(),
        display_title=new_display_title,
        display_description=(request.form.get("display_description") or "").strip(),
        governance_log=_log(),
    )
    flash("Project details updated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/context", methods=["POST"])
@login_required
def add_project_context_entry_route(project_id):
    """CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01: records a new CURRENT Project
    Context entry - see CaseWorkspaceStore.add_project_context_entry.
    Reachable from the top-bar Project Context control on every
    workspace page (templates/base.html), so this always redirects back
    to Overview afterward - the same "land somewhere the reviewer can
    actually see the result" convention edit_operating_instructions
    above already follows, not a new pattern. Open to any authenticated
    Project member, same authority level as Operating Instructions -
    Project Context is collaborative orientation, not owner-locked
    evidence."""
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        store.add_project_context_entry(
            workspace,
            text=(request.form.get("text") or ""),
            actor=_reviewer(),
            actor_role=session.get("role"),
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    flash("Project Context updated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/context", methods=["POST"])
@login_required
def set_document_context_route(project_id, source_id):
    """CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01: Document Context - human-
    supplied orientation on ONE Source, kept explicitly independent of
    Project Context (see CaseWorkspaceStore.set_source_note's own
    docstring). Open to any authenticated Project member, matching
    Operating Instructions/Project Context's own authority level -
    annotative/descriptive text, not a lifecycle action like Remove
    Document (which stays owner-or-admin, unchanged)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        store.set_source_note(
            workspace, source_id=source_id,
            text=(request.form.get("text") or ""),
            actor=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))

    flash("Document Context updated.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/document-context-claims/draft", methods=["POST"])
@admin_required
def draft_document_context_claims_route(project_id, source_id):
    """
    Bounded GO QA/QC pass (Section 5): GO drafts Document Context claims
    from this Source's already-extracted EvidenceItem text (never the
    model's own world knowledge - see services.document_context_
    intelligence's own docstring). Admin-only, same authority level every
    prior modality-intelligence write route (MM2-MM6) already uses -
    this is Admin Document Mode's own calibration action, not an ordinary
    PM one. A no-key/timeout/malformed-output failure flashes the honest
    reason and drafts nothing - never a fabricated claim.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if source is None:
        flash("Source not found.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    evidence_text = "\n\n".join(
        e["content"] for e in workspace.evidence_items
        if e["source_id"] == source_id and e.get("content_type") == "text" and e.get("content")
    )
    result = draft_document_context_claims(source["name"], evidence_text)
    if not result["ran"]:
        flash(f"Could not draft Document Context: {result['skipped_reason']}", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))

    for claim in result["claims"]:
        store.draft_document_context_claim(
            workspace, source_id, claim["field_kind"], claim["statement"],
            created_by="GO", governance_log=_log(),
        )
    flash(f"GO drafted {len(result['claims'])} Document Context claim(s) for review.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))


@workspace_bp.route("/projects/<project_id>/workspace/document-context-claims/<claim_id>/review", methods=["POST"])
@admin_required
def review_document_context_claim_route(project_id, claim_id):
    """The one PM-facing disposition action for a GO-drafted Document
    Context claim - accept (as-is or with edits) or reject. See
    CaseWorkspaceStore.review_document_context_claim; this route is a
    thin form-to-store bridge, no logic of its own."""
    _, store, workspace = _load_workspace_or_404(project_id)
    outcome = request.form.get("outcome")
    edited_statement = request.form.get("statement")
    source_id = request.form.get("source_id")

    try:
        store.review_document_context_claim(
            workspace, claim_id, actor=_reviewer(), outcome=outcome,
            edited_statement=edited_statement, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/<requirement_id>/assess-phase", methods=["POST"])
@admin_required
def assess_requirement_phase_route(project_id, requirement_id):
    """
    Bounded GO QA/QC pass (Section 1-3): triggers ONE
    RequirementPhaseAssessment via CaseWorkspaceStore.assess_requirement_
    phase_conformance - "SOR Requirement + Current Phase Expectation +
    Submitted Evidence -> Current Conformance Assessment." Admin-only
    (Admin Document Mode calibration action, not an ordinary PM one).

    `evidence_found`/`resolution_level` are this bounded pass's own
    deliberately minimal stand-in for a full evidence picker (out of
    scope - see this pass's own report) - a real evidence-reconciliation
    UI is explicitly deferred to a future increment, matching
    evaluate_information_sufficiency's own existing "observed is the
    caller's explicit input, never auto-discovered" contract.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    evidence_found = request.form.get("evidence_found") == "on"
    resolution_level = (request.form.get("resolution_level") or "").strip() or None
    observed = [{"resolution_level": resolution_level}] if evidence_found else []

    try:
        store.assess_requirement_phase_conformance(
            workspace, requirement_id, observed=observed, created_by="GO", governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    try:
        store.set_operating_environment(
            workspace, operating_environment, actor=_reviewer(), governance_log=_log(),
        )
    except OperatingEnvironmentAlreadySetError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    flash(
        f"Project operating environment established: "
        f"{OPERATING_ENVIRONMENT_LABELS[operating_environment]}.", "success",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/correct-environment", methods=["POST"])
@admin_required
def correct_operating_environment(project_id):
    """
    CLAUDE-VOICE27-MISCLASS-01: a real Product Owner report - a project
    created and worked on from the Design-Builder/Proponent side had
    been classified Client/Owner at creation (an RFP is routinely
    received and worked FROM the Proponent side; being an RFP is not
    evidence the current team issued it). classify_operating_environment
    above is the one-time FIRST establishment for a legacy project with
    no value yet - it structurally cannot fix an already-set-but-wrong
    value (CaseWorkspaceStore.set_operating_environment's own lock).
    This is the separate, harder-to-reach correction path for that case
    - see CaseWorkspaceStore.correct_operating_environment's own
    docstring for the full reasoning. Admin-only, matching every other
    project-level correction route in this file; requires a real reason
    so the audit trail always records WHY, not just that a locked value
    moved.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    operating_environment = (request.form.get("operating_environment") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if not is_valid_operating_environment(operating_environment):
        flash("Select a valid project operating environment.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    try:
        store.correct_operating_environment(
            workspace, operating_environment, actor=_reviewer(), reason=reason, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    flash(
        f"Project operating environment corrected to: "
        f"{OPERATING_ENVIRONMENT_LABELS[operating_environment]}.", "success",
    )
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))
    if new_owner not in {u.username for u in User.query.all()}:
        flash(f"{new_owner!r} is not a registered account.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    store.set_project_owner(workspace, owner=new_owner, actor=_reviewer(), governance_log=_log())
    flash(f"Project owner set to {new_owner!r}.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    try:
        store.grant_project_access(
            workspace, username=username, actor=_reviewer(), actor_role=session.get("role") or "",
            governance_log=_log(),
        )
        flash(f"Access granted to {username!r}.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


# -- CLAUDE-P40-E2: recoverable removal (Document/Project), not deletion ----

@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/remove", methods=["POST"])
@login_required
def remove_document_route(project_id, source_id):
    """"Remove Document" (Section B/C) - a simple confirm=yes/no gate,
    the same idiom routes/portal.py's delete_project already uses for a
    consequential-but-not-governed action, deliberately NOT the
    Approval Gate's confirm=once|session|no vocabulary (CLAUDE.md's own
    "two different confirm vocabularies" note - Remove is closer in
    kind to Delete than to Apply/RFI-Issue)."""
    _, store, workspace = _load_workspace_or_404(project_id)
    source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if source is None:
        abort(404)

    confirm = request.form.get("confirm")
    if confirm == "no":
        flash("Cancelled - the Document was not removed.", "success")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))
    if confirm != "yes":
        return render_template(
            "confirm_remove_document.html",
            source_name=source["name"],
            action_url=request.url,
            project_id=project_id,
        )

    try:
        store.remove_source(
            workspace, source_id=source_id, actor=_reviewer(), actor_role=session.get("role") or "",
            reason=(request.form.get("reason") or None), governance_log=_log(),
        )
        flash(f'"{source["name"]}" removed - restore it any time from Removed Items.', "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/restore", methods=["POST"])
@login_required
def restore_document_route(project_id, source_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        source = store.restore_source(
            workspace, source_id=source_id, actor=_reviewer(), actor_role=session.get("role") or "",
            governance_log=_log(),
        )
        flash(f'"{source["name"]}" restored.', "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, source=source_id))


@workspace_bp.route("/projects/<project_id>/workspace/remove", methods=["POST"])
@login_required
def remove_project_route(project_id):
    """"Remove Project" (Section B/C) - a completely separate,
    recoverable action from routes/portal.py's delete_project
    (permanent, unchanged). Same confirm=yes/no gate as Document
    removal above."""
    _, store, workspace = _load_workspace_or_404(project_id)

    confirm = request.form.get("confirm")
    if confirm == "no":
        flash("Cancelled - the Project was not removed.", "success")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))
    if confirm != "yes":
        return render_template(
            "confirm_remove_project.html",
            action_url=request.url,
            project_id=project_id,
        )

    try:
        store.remove_project(
            workspace, actor=_reviewer(), actor_role=session.get("role") or "",
            reason=(request.form.get("reason") or None), governance_log=_log(),
        )
        flash("Project removed - restore it any time from Removed Projects.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))
    return redirect(url_for("portal.projects_list"))


@workspace_bp.route("/projects/<project_id>/workspace/restore", methods=["POST"])
@login_required
def restore_project_route(project_id):
    # allow_removed=True - this is the one action a removed Project's
    # tombstone must still be able to reach.
    _, store, workspace = _load_workspace_or_404(project_id, allow_removed=True)
    try:
        store.restore_project(workspace, actor=_reviewer(), actor_role=session.get("role") or "", governance_log=_log())
        flash("Project restored.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


# -- CLAUDE-P40-VW9: Files - Design-Builder Workspace folders --------------
# Every route below operates ONLY on FOLDER_ROOT_DESIGN_BUILDER folders -
# the store-layer methods themselves have no way to reach
# FOLDER_ROOT_DATA_ROOM at all (Section 4's own "do not allow ordinary
# Design-Builder working-folder actions to silently modify [the Data
# Room]"). No owner/admin gate (matching create_task/create_custom_tag's
# own precedent - see CaseWorkspaceStore.create_folder's own docstring
# for the reasoning); `_load_workspace_or_404` (project-level access) is
# the one and only authorization check every route below relies on, the
# same "no new authorization path" discipline this stage's own governing
# prompt requires.

def _files_redirect(project_id, folder_id=None):
    if folder_id:
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="files", folder=folder_id))
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="files"))


@workspace_bp.route("/projects/<project_id>/workspace/folders", methods=["POST"])
@login_required
def create_folder_route(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    name = request.form.get("name") or ""
    parent_folder_id = request.form.get("parent_folder_id") or None
    try:
        folder = store.create_folder(
            workspace, name=name, parent_folder_id=parent_folder_id,
            actor=_reviewer(), governance_log=_log(),
        )
        flash(f'Folder "{folder["name"]}" created.', "success")
        return _files_redirect(project_id, folder["parent_folder_id"])
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return _files_redirect(project_id, parent_folder_id)


@workspace_bp.route("/projects/<project_id>/workspace/folders/register-paths", methods=["POST"])
@admin_required
def register_folder_paths_route(project_id):
    """CLAUDE-RFP27-TERRITORY-01 (Part 3/4): registers real, meaningful
    project-territory folders that have ZERO files today - the one case
    a file upload structurally can never report (browsers never emit a
    File for an empty directory, so reconcile_data_room_upload_route
    below can never learn an empty folder exists). Admin-gated - unlike
    the collaborative "+ New Folder" (create_folder_route above), this
    is an explicit, deliberate declaration of real external project
    structure, not ordinary working-folder organization. `root` is an
    explicit, required human choice (never inferred) - CaseWorkspaceStore.
    ensure_folder_path is the one place allowed to construct a Data Room
    Folder; this route is simply its second real caller, alongside
    reconcile_data_room_upload_route's own per-file directory segments."""
    _, store, workspace = _load_workspace_or_404(project_id)
    root = request.form.get("root") or ""
    if root not in KNOWN_FOLDER_ROOTS:
        flash("Choose a valid folder root.", "error")
        return _files_redirect(project_id)

    raw_paths = (request.form.get("paths") or "").splitlines()
    created = []
    for line in raw_paths:
        line = line.strip()
        if not line:
            continue
        store.ensure_folder_path(workspace, root=root, relative_path=line, actor=_reviewer(), governance_log=_log())
        created.append(line)
        workspace = store.get(project_id)

    if created:
        flash(f"Registered {len(created)} folder path(s).", "success")
    else:
        flash("No folder paths were given.", "error")
    return _files_redirect(project_id)


@workspace_bp.route("/projects/<project_id>/workspace/data-room/reconcile", methods=["POST"])
@admin_required
def reconcile_data_room_route(project_id):
    """CLAUDE-RFP27-TERRITORY-01 (Part 4): the Data Room discovery/
    reconciliation action - "local/external project territory changes
    -> ARCHIOSK discovers the change." Deterministic, explicit-Refresh
    (never automatic background polling/filesystem-watching - the
    governing prompt's own "prefer deterministic, read-only discovery
    before aggressive automation"), reusing the exact same browser
    folder-select convention `portal.upload`'s own folder mode already
    established (files renamed to their own webkitRelativePath client-
    side before submission - see templates/upload.html's own script -
    so relative_paths is derived the same way portal.py's own folder-
    upload handler already derives it: [f.filename for f in files]).
    Admin-gated: registers real project evidence and can relink existing
    Source identity, a consequential, project-wide action, not ordinary
    per-Document housekeeping."""
    _, store, workspace = _load_workspace_or_404(project_id)
    files = [f for f in request.files.getlist("folder_files") if f and f.filename]
    if not files:
        flash("No folder was selected.", "error")
        return _files_redirect(project_id)
    relative_paths = [f.filename for f in files]

    try:
        results = reconcile_data_room_upload(
            files, relative_paths, project_id, current_app,
            actor=_reviewer(), role=session.get("role"),
        )
    except UploadError as exc:
        flash(str(exc), "error")
        return _files_redirect(project_id)

    added = [r for r in results if r["status"] == "added"]
    relinked = [r for r in results if r["status"] == "relinked"]
    skipped = [r for r in results if r["status"] == "skipped"]
    summary = f"Data Room reconciled: {len(added)} added, {len(relinked)} relinked (not duplicated), {len(skipped)} skipped."
    flash(summary, "success" if (added or relinked) else "error")
    if skipped:
        flash("Skipped: " + "; ".join(f'{r["filename"]} ({r["reason"]})' for r in skipped[:5]), "error")
    return _files_redirect(project_id)


@workspace_bp.route("/projects/<project_id>/workspace/organize/create-structure", methods=["POST"])
@login_required
def apply_organize_structure(project_id):
    """
    CLAUDE-POSTCAMEL-CA1C (Sections 5/6/17): the real action behind
    conversation_interpreter.py's own "Create this structure" offer -
    recomputes the EXACT SAME real, project-grounded group list
    (compute_organize_groups, the one shared source of truth also used
    for the conversational proposal, so what was shown is exactly what
    gets created) and creates each one as a real, governed Design-
    Builder Workspace Folder via the existing, unmodified
    store.create_folder. Idempotent by design: a group whose name is
    already taken (CaseWorkspaceError) is silently skipped rather than
    failing the whole batch, so re-clicking this after a partial
    success (or after manually creating one of the same names) is safe.
    Never touches the Data Room, never touches the originating Source -
    the same governed-Folder mechanism "+ New Folder" already uses.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    groups = compute_organize_groups(store, workspace)
    created, skipped = [], []
    for group_name in groups:
        try:
            store.create_folder(workspace, name=group_name, actor=_reviewer(), governance_log=_log())
            created.append(group_name)
        except CaseWorkspaceError:
            skipped.append(group_name)

    if created:
        flash(f"Created {len(created)} folder(s): {', '.join(created)}.", "success")
    if skipped:
        flash(f"Already existed, left unchanged: {', '.join(skipped)}.", "error")
    if not created and not skipped:
        flash("No grounded structure was available to create.", "error")
    return _files_redirect(project_id)


@workspace_bp.route("/projects/<project_id>/workspace/folders/<folder_id>/rename", methods=["POST"])
@login_required
def rename_folder_route(project_id, folder_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    new_name = request.form.get("name") or ""
    current = next((f for f in workspace.folders if f["id"] == folder_id), None)
    parent_folder_id = current.get("parent_folder_id") if current else None
    try:
        folder = store.rename_folder(workspace, folder_id=folder_id, new_name=new_name, actor=_reviewer(), governance_log=_log())
        flash(f'Folder renamed to "{folder["name"]}".', "success")
        return _files_redirect(project_id, folder["parent_folder_id"])
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return _files_redirect(project_id, parent_folder_id)


@workspace_bp.route("/projects/<project_id>/workspace/folders/<folder_id>/move", methods=["POST"])
@login_required
def move_folder_route(project_id, folder_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    new_parent_folder_id = request.form.get("parent_folder_id") or None
    current = next((f for f in workspace.folders if f["id"] == folder_id), None)
    origin_parent_folder_id = current.get("parent_folder_id") if current else None
    try:
        folder = store.move_folder(
            workspace, folder_id=folder_id, new_parent_folder_id=new_parent_folder_id,
            actor=_reviewer(), governance_log=_log(),
        )
        flash(f'Folder "{folder["name"]}" moved.', "success")
        return _files_redirect(project_id, folder["parent_folder_id"])
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return _files_redirect(project_id, origin_parent_folder_id)


@workspace_bp.route("/projects/<project_id>/workspace/folders/<folder_id>/delete", methods=["POST"])
@login_required
def delete_folder_route(project_id, folder_id):
    """The lighter confirm=yes/no gate (matching remove_document_route/
    remove_project_route above), not the Approval Gate - deleting an
    EMPTY organizational folder is consequential-but-not-governed, the
    same category CLAUDE.md's own "two different confirm vocabularies"
    note already places Remove Document/Remove Project in."""
    _, store, workspace = _load_workspace_or_404(project_id)
    folder = next((f for f in workspace.folders if f["id"] == folder_id), None)
    if folder is None:
        abort(404)
    parent_folder_id = folder.get("parent_folder_id")

    confirm = request.form.get("confirm")
    if confirm == "no":
        flash("Cancelled - the folder was not deleted.", "success")
        return _files_redirect(project_id, folder_id)
    if confirm != "yes":
        return render_template(
            "confirm_delete_folder.html",
            folder_name=folder["name"],
            action_url=request.url,
            project_id=project_id,
            parent_folder_id=parent_folder_id,
        )

    try:
        store.delete_folder(workspace, folder_id=folder_id, actor=_reviewer(), governance_log=_log())
        flash(f'Folder "{folder["name"]}" deleted.', "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return _files_redirect(project_id, parent_folder_id)


@workspace_bp.route("/projects/<project_id>/workspace/sources/document", methods=["POST"])
@login_required
def add_document_source(project_id):
    """
    Project Sources + -> Add Documents (Prompt 3 #8). Project-scoped, not
    Case-scoped: CaseWorkspaceStore.add_source itself takes no case_id -
    a Case draws on Sources, it does not own them.

    CLAUDE-P40-E3A: this form and its two siblings below now live in
    Toolbox (relocated from the retired ?view=documents Display body -
    Section 4/8), so every redirect here goes back to the bare Workspace
    URL - Display renders blank (Section 5, nothing selected) while
    Toolbox still shows the same Add-a-Document tool right where the
    reviewer just used it, not a stale directory listing that no longer
    exists.

    CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage Grammar &
    Public-Trial Entitlement, Part 6/8): this is the second of the two
    named "Upload to Storage" surfaces (the other is
    routes/portal.py::upload_folder) - real server-side enforcement, not
    merely the Project Data Management page's own greying. Deliberately
    does NOT touch this route's existing @login_required-only
    authorization level (see governance/deferred-reserved/
    reservations.md item 13 - a separate, already-recorded residual;
    Part H of the base CONSOLIDATION-01 prompt says leave it alone).
    """
    if not user_can_upload_to_storage():
        abort(403)

    _, store, workspace = _load_workspace_or_404(project_id)

    file_storage = request.files.get("document")
    if file_storage is None or not file_storage.filename:
        flash("Choose a document to add as a Project Source.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        flash(f"Unsupported document format '{ext}'.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    store.create_snapshot(
        workspace,
        label=label,
        created_by=_reviewer(),
        note=(request.form.get("note") or "").strip() or None,
        governance_log=_log(),
    )
    flash("Snapshot created.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/archive/confirm", methods=["GET"])
@login_required
def confirm_archive_case(project_id, case_id):
    """CLAUDE-POSTCAMEL-INVESTIGATION-AR1: the discoverable "Archive
    Investigation" affordance's confirmation step. Deliberately a
    separate GET route rendering its own page, rather than adding a
    confirm=yes/no parameter to the existing POST /archive route below -
    that route is also the Attention-Capacity dialog's "Conclude"
    trigger (CLAUDE-P40-VW7B), and that existing path must keep working
    exactly as it does today (Section 14: "one archive mechanism,
    multiple legitimate triggers", not one mechanism whose contract
    changes for every caller). This page's own form posts to that same
    unmodified /archive route.

    Not itself the authority check (archive_case below still owns
    that) - only decides whether to show the button as actionable, so a
    reviewer who cannot actually archive this Case is told so before
    clicking through rather than after."""
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None or case.get("status") == CASE_STATUS_ARCHIVED:
        abort(404)

    is_owner = case.get("created_by") is not None and _reviewer() == case["created_by"]
    is_admin = session.get("role") == "admin"

    return render_template(
        "confirm_archive_case.html", project_id=project_id, case=case,
        can_archive=(is_owner or is_admin),
    )


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/archive", methods=["POST"])
@login_required
def archive_case(project_id, case_id):
    """Terminal/frozen Case status - see CaseWorkspaceStore.archive_case.
    Owner or admin-role only; the machine never performs this. Passes the
    real session role through so the store layer's owner-or-admin
    authority check (the narrowest existing legitimate pattern - no new
    role architecture) can recognize a Design Manager/admin override
    without this route inventing its own separate authorization logic.

    CLAUDE-P40-VW7B: optional `next_case` form field - when the
    Attention-capacity dialog (Section 9) uses "Conclude" to free a
    fifth position, the reviewer's real intent was to open a DIFFERENT
    Investigation, not to land back on the one they just archived. No
    prior caller passed this (grep confirms archive_case had no real UI
    trigger anywhere before this stage), so its absence is fully
    backward compatible - falls through to the original behavior.
    Validated the same way every other Case reference on this route
    already is (against this reviewer's own visible_cases, via
    CaseWorkspaceStore.visible_cases_for) - never a raw, unchecked
    redirect target."""
    _, store, workspace = _load_workspace_or_404(project_id)

    next_case_id = request.form.get("next_case", "").strip()
    if next_case_id:
        visible_case_ids = {c["id"] for c in store.visible_cases_for(workspace, _reviewer())}
        if next_case_id not in visible_case_ids:
            next_case_id = ""

    try:
        store.archive_case(
            workspace, case_id=case_id, actor=_reviewer(),
            actor_role=session.get("role"), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    flash("Case archived.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=next_case_id or case_id))


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


@workspace_bp.route("/projects/<project_id>/workspace/cases/<case_id>/snapshot", methods=["POST"])
@login_required
def snapshot_archived_case(project_id, case_id):
    """CLAUDE-POSTCAMEL-INVESTIGATION-AR1 Smart Snapshot: a read-only,
    ephemeral orientation recap of an ARCHIVED Case, requested from the
    "Continue from Archive" chooser before a reviewer decides whether to
    derive from it. See services.investigation_snapshot's own docstring
    for the grounding/non-mutation contract this route must preserve.

    Deliberately writes NOTHING - no ConversationMessage (this never
    calls _run_conversation_turn/add_message), no Finding, no Task, no
    Work Product, no GovernanceLog entry (Section 10: "Snapshot assists
    recall; it does not create authority" - requesting a recap is not
    itself a governed action). The response is JSON, rendered into an
    ephemeral page fragment by the caller and never persisted."""
    _, store, workspace = _load_workspace_or_404(project_id)
    _require_visible_case(store, workspace, case_id)

    case = next((c for c in workspace.cases if c["id"] == case_id), None)
    if case is None or case.get("status") != CASE_STATUS_ARCHIVED:
        abort(404)

    findings = [f for f in workspace.findings if f["case_id"] == case_id]
    conversation = case.get("conversation", [])

    result = build_archive_snapshot(case, findings, conversation)
    return jsonify({
        "ran": result.ran,
        "summary": result.summary,
        "grounded_in": result.grounded_in,
        "not_covered": result.not_covered,
        "skipped_reason": result.skipped_reason,
    })


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
            f"Unsupported drawing format '{ext}'. Use PNG or JPG for a drawing Source.",
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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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

    CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION (Section B, "internal-first
    document opening"): `?download=1` is the one explicit, deliberate
    way to get `as_attachment=True` (a real Content-Disposition:
    attachment, forcing a Save dialog) from this same route/file -
    used only by the Display pane's own "Download" secondary action for
    a format with no in-app viewer (see case_workspace.html's document
    branch). The default (no query param) stays `as_attachment=False`
    exactly as before, for the genuinely in-app viewers (image/PDF/
    XLSX embeds) and for the new "Open externally" secondary action,
    which deliberately leaves the browser's own handling in charge
    rather than forcing a download it might not need.
    """
    _, _, workspace = _load_workspace_or_404(project_id)

    source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if source is None or not source.get("file_path"):
        abort(404)
    # CLAUDE-P40-E2A, Section A: "ordinary document-viewer and processing
    # routes must not treat it as active" - a removed Source's own file
    # is never served here, even to an authorized caller who somehow
    # still has the direct URL (a stale tab, a bookmark). The file on
    # disk is completely untouched by this - restoring the Source makes
    # this route work again with no re-upload.
    if source.get("removed_at"):
        abort(404)

    file_path = Path(source["file_path"])
    if not file_path.exists():
        abort(404)

    mimetype, _ = mimetypes.guess_type(source["name"])
    return send_file(
        file_path,
        mimetype=mimetype or "application/octet-stream",
        as_attachment=bool(request.args.get("download")),
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

    # CLAUDE-P40-E2A, Section A: "document processing routes must not
    # treat it as active" - registering a new revision IS processing;
    # blocked while the Source is removed, restore it first.
    existing_source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if existing_source is not None and existing_source.get("removed_at"):
        flash("This Source has been removed. Restore it before registering a new revision.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

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


@workspace_bp.route("/projects/<project_id>/workspace/sources/<source_id>/revise-document", methods=["POST"])
@login_required
def revise_document_source(project_id, source_id):
    """
    CLAUDE-POSTCAMEL-COMM-I4A: OPR-2.5's own corrective tranche. Mirrors
    `revise_source` above exactly (never replaces the old Source, only
    registers a new one and a Supersession record; gated behind the same
    Approval Gate action class since it is the same governance-affecting
    action) but for the three Source kinds `revise_source` cannot serve
    at all - `project_document`, `rfq_rfp_document`, `text_record` - a
    revised RFP/specification/addendum, not a revised drawing. Source is
    project-scoped, not Case-scoped (its own docstring), so this route
    deliberately does not require a `case_id` the way the drawing route
    does; any Case that already cites the old Source still gets a
    RevisionNotice regardless, via register_source_revision's own
    Case-lookup, unchanged.
    """
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = request.form.get("case_id") or None

    existing_source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if existing_source is None:
        abort(404)
    if existing_source.get("removed_at"):
        flash("This Source has been removed. Restore it before registering a new revision.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))
    if existing_source["kind"] == SOURCE_KIND_DRAWING:
        flash("Use the drawing revision control for this Source.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    gate = _require_approval(
        "source_revision",
        "Register a new revision of this document Source. The original Source "
        "and every Finding/Requirement/Case that cites it will be preserved "
        "unchanged; a Reference Update notice will be added to any Case that "
        "used it instead.",
        project_id,
        case_id,
    )
    if gate is not None:
        return gate

    file_storage = request.files.get("document")
    if file_storage is None or not file_storage.filename:
        flash("Choose a document for the new revision.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    ext = Path(file_storage.filename).suffix.lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        flash(f"Unsupported document format '{ext}'.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file_storage.filename)
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(file_storage.read())

    predecessor_version = workspace.version
    try:
        new_source, notices, supersession = store.register_source_revision(
            workspace,
            old_source_id=source_id,
            name=safe_name,
            file_path=str(stored_path),
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


# CLAUDE-POSTCAMEL-CA1B (Section 4, unified professional-context
# envelope): a single, project-scoped "what is the PM currently working
# with" slot - deliberately ONE slot, not one per object type, so a new
# explicit selection of any kind naturally replaces whatever was there
# before (Section 6's own "Finding B wins" requirement) rather than
# requiring separate stale-vs-fresh reconciliation logic. Session-based,
# same persistence characteristics as the pre-existing
# focused_finding:{project_id} key this mirrors - not a governed
# CaseWorkspaceStore field, because a selection is emphatically not
# Project truth (Section 17). Stored in the same shape as Anchor
# (anchor_type/anchor_id) so it can be passed anywhere an anchor already
# is, without a second shape.
_SELECTABLE_OBJECT_TYPES = frozenset({"requirement", "finding", "source"})


def _selected_object_session_key(project_id: str) -> str:
    return f"selected_object:{project_id}"


def _get_persisted_selection(project_id: str) -> Optional[dict]:
    return session.get(_selected_object_session_key(project_id))


def _set_persisted_selection(project_id: str, anchor_type: str, anchor_id: str) -> None:
    if anchor_type in _SELECTABLE_OBJECT_TYPES and anchor_id:
        session[_selected_object_session_key(project_id)] = {
            "anchor_type": anchor_type, "anchor_id": anchor_id,
        }


def _clear_persisted_selection(project_id: str) -> None:
    session.pop(_selected_object_session_key(project_id), None)


def _run_conversation_turn(
    project_id: str, store: CaseWorkspaceStore, workspace, case: Optional[dict], text: str,
    anchor: Optional[dict] = None, current_view: Optional[str] = None,
    selected_source_id: Optional[str] = None,
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

    CLAUDE-POSTCAMEL-CA1A (Sections 2/3): `current_view`/
    `selected_source_id` are the real, already-project-scoped
    `directory_view`/`selected_source.id` values `show_workspace` itself
    computed for the page the composer was submitted from - passed
    through here unvalidated (interpret_message re-validates both
    against THIS workspace before trusting either; never assume a
    client-submitted hidden field is honest just because this route
    happened to render it that way originally).

    CLAUDE-POSTCAMEL-CA1B (Section 5, context precedence): an anchor
    attached to THIS message is the freshest, most explicit signal, so
    it both answers this turn AND becomes the persisted "professional
    context" for whatever comes next (Section 6's own "a new explicit
    selection replaces the old one" requirement) - never the reverse
    (a stale persisted selection never overrides a fresh anchor).
    """
    case_id = case["id"] if case is not None else None
    human_message = store.add_message(
        workspace, case_id, role="human", text=text, anchor=anchor, actor=_reviewer(),
        selected_source_id=selected_source_id, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
    )

    artifacts_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_artifacts"
    focused_finding_id = session.get(f"focused_finding:{project_id}")

    if anchor is not None:
        _set_persisted_selection(project_id, anchor.get("anchor_type"), anchor.get("anchor_id"))
    persisted_selection = _get_persisted_selection(project_id)

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
        current_view=current_view,
        selected_source_id=selected_source_id,
        selected_object=persisted_selection,
    )

    store.add_message(
        workspace,
        case_id,
        role="system",
        text=result.reply_text,
        action_taken=result.action_taken,
        grounded_in=result.grounded_in,
        next_steps=result.next_steps,
        organize_source_id=result.organize_source_id,
        operational_actions=result.operational_actions,
        river_actions=result.river_actions,
        content_class=result.content_class,
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

    _run_conversation_turn(
        project_id, store, workspace, case, text,
        current_view=request.form.get("current_view"),
        selected_source_id=request.form.get("selected_source_id"),
    )

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

    CLAUDE-P40-E1: this is now also the ONE Workspace composer's actual
    route (the separate "Ask about the project documents"/discuss_object
    composer and the plain "Start or continue project work" composer
    were removed as duplicate entry points into this same underlying
    mechanism - see _run_conversation_turn's own docstring, which
    already called all three "the same conversational entry point").
    Optional anchor_type/anchor_id/anchor_description form fields (set
    by static/js/case_workspace.js when a "Discuss this X" link
    elsewhere on the page is clicked, matching discuss_object's own
    anchor shape) mean an anchored message ALWAYS lands in the
    project-level conversation with that anchor attached, the same as
    discuss_object always did - a "Discuss this Requirement" click must
    never accidentally spawn a new Investigation just because its text
    doesn't happen to read as a question.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Describe what you want to work on to start.", "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    anchor_type = (request.form.get("anchor_type") or "").strip()
    anchor_id = (request.form.get("anchor_id") or "").strip()
    anchor = None
    if anchor_type and anchor_id:
        anchor = asdict(Anchor(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            description=(request.form.get("anchor_description") or None),
        ))

    # CLAUDE-POSTCAMEL-CA1: an orientation request ("orient me", "what's
    # here") is exactly as read-only/project-level as a plain question -
    # without this, typing it into the main composer would silently
    # create a brand-new Case/Investigation titled "orient me", the same
    # kind of surprise this route's own docstring already names for
    # plain factual questions.
    current_view = request.form.get("current_view")
    selected_source_id = request.form.get("selected_source_id")

    # CLAUDE-POSTCAMEL-CA1A: a contextual-reference phrase ("tell me
    # about this", "show me the evidence for this", ...) or a "what
    # should I do next" question is exactly as read-only/project-level
    # as orientation already is - without this, typing either into the
    # main composer would silently create a brand-new surprise Case
    # (found live, during this stage's own Walkthrough B), the same
    # class of bug CA1 already fixed once for orientation itself.
    # CLAUDE-CA1C-CONV-FIX-02: checked FIRST in this OR-chain, deliberately
    # ahead of `anchor is not None` too - a real Product Owner typed
    # "hello"/"hello hello" into this exact composer and watched it create
    # a brand-new Investigation, which then immediately tripped the four-
    # Investigation attention limit's own "Attention is full" dialog, just
    # to say hello. None of the FOUR existing exemptions below recognize a
    # bare greeting (they are all specifically about questions/
    # orientation/contextual-reference/next-steps) - this is the durable
    # gate that principle was missing, not one more literal phrase bolted
    # onto an unrelated existing check. "Conversation != Investigation":
    # an Investigation requires actual investigative intent, never merely
    # any text typed into this composer.
    lowered_text = text.lower()
    if (
        _looks_like_conversational_utterance(lowered_text)
        or anchor is not None
        or _looks_like_project_question(lowered_text)
        or _looks_like_orientation_request(lowered_text)
        or _looks_like_contextual_reference(lowered_text)
        or _looks_like_what_next(lowered_text)
    ):
        _run_conversation_turn(
            project_id, store, workspace, None, text, anchor=anchor,
            current_view=current_view, selected_source_id=selected_source_id,
        )
        # CLAUDE-CA1C-UX-FIX-01: no "#conversation-dock" fragment - it used
        # to (per this route's sibling below) rely on a browser-native
        # anchor-scroll to reveal the reply, but the dock stopped being a
        # <details> element back in P40-E2B (it's a plain <div> now), so
        # static/js/case_workspace.js's own hash-driven "open the collapsed
        # ancestor" logic (which only matches `details.accordion-section`)
        # never actually fired for it - the fragment was purely triggering
        # the browser's own default scroll-into-view, which targets this
        # panel's own (sticky, bottom-pinned) top edge, not the newest
        # message. That native scroll raced the JS's own deliberate
        # scroll-to-newest logic below, on a container with `scroll-
        # behavior: smooth` - two competing smooth-scrolls landing short of
        # the real bottom (the live-reported bug). One explicit owner now:
        # the JS's own justSent-flagged scroll-to-bottom, nothing native.
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    title = text if len(text) <= 80 else text[:77] + "..."
    case = store.create_case(workspace, title=title, objective="", created_by=_reviewer())

    _log().append(
        project_id=project_id,
        event_type="case_created",
        actor=_reviewer(),
        role=session.get("role") or "unspecified",
        payload={"case_id": case["id"], "title": title, "visibility": case["visibility"]},
    )

    _run_conversation_turn(
        project_id, store, workspace, case, text,
        current_view=current_view, selected_source_id=selected_source_id,
    )

    return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case["id"]))


# ---------------------------------------------------------------------
# CLAUDE-P40-VW7: project-scoped conversation Tags/Highlights/Tasks.
#
# All five routes below share the same shape: _load_workspace_or_404
# (the same P32 project-access/removed-state choke point every other
# route in this blueprint already uses - see that function's own
# docstring) is the ENTIRE authorization boundary; no separate Tag/
# Task-specific access rule exists, matching the prompt's own "the same
# Project owner, allow-list, and admin-bypass rules governing the
# source conversation must govern its Tasks and Tags" instruction.
# JSON responses (not a redirect) because Section 7's own explicit
# requirement is that Lists updates immediately, without a reload - the
# one deliberate, bounded exception to this app's usual full-page-
# reload convention (see static/js/case_workspace.js's own comment on
# the fetch() calls that hit these routes, and tools/dependency_fit.py,
# consulted before introducing it: fetch() itself required no new
# dependency and passed every existing architectural constraint clean).
# CSRF is still fully enforced (Flask-WTF's CSRFProtect checks the
# X-CSRFToken header on these exactly the way it checks the hidden
# csrf_token field on every other POST in this app - see that JS
# comment for where the header value comes from).
# ---------------------------------------------------------------------

def _conversation_source_url(project_id: str, source_anchor: dict) -> str:
    """The one URL that reopens Project Conversation (bare workspace URL
    - the project-level conversation renders whenever no Investigation
    is open, unconditionally, per CLAUDE-P40-E3A) or an Investigation's
    own conversation (?case=), scrolled/flashed to the exact anchored
    message via the #conv-source-<id> fragment static/js/
    case_workspace.js reads on load (Section 4's own "navigate to and
    scroll the source into view / visibly identify the exact anchored
    passage" requirement) - never a second, ambiguous navigation
    mechanism."""
    scope = source_anchor.get("scope")
    if scope == CONVERSATION_ANCHOR_SCOPE_CASE:
        base = url_for("workspace.show_workspace", project_id=project_id, case=source_anchor.get("case_id"))
        fragment = f"conv-source-{source_anchor.get('message_id')}"
    elif scope == CONVERSATION_ANCHOR_SCOPE_GUIDANCE:
        base = url_for("workspace.show_workspace", project_id=project_id)
        fragment = "conv-source-guidance"
    else:
        base = url_for("workspace.show_workspace", project_id=project_id)
        fragment = f"conv-source-{source_anchor.get('message_id')}"
    return f"{base}#{fragment}"


def _source_anchor_from_form() -> dict:
    def _int_or_none(raw):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    return {
        "scope": (request.form.get("anchor_scope") or "").strip(),
        "case_id": (request.form.get("anchor_case_id") or "").strip() or None,
        "message_id": (request.form.get("anchor_message_id") or "").strip() or None,
        "guidance_key": (request.form.get("anchor_guidance_key") or "").strip() or None,
        "start_offset": _int_or_none(request.form.get("anchor_start_offset")),
        "end_offset": _int_or_none(request.form.get("anchor_end_offset")),
        "quote": request.form.get("anchor_quote") or "",
        "prefix": request.form.get("anchor_prefix") or "",
        "suffix": request.form.get("anchor_suffix") or "",
    }


def _tag_counts(workspace) -> dict:
    occurrences = workspace.tag_occurrences
    groups: dict[str, dict] = {}
    for occ in occurrences:
        bucket = groups.setdefault(occ["tag_id"], {"count": 0})
        bucket["count"] += 1
    return {"total": len(occurrences), "by_tag": {tag_id: g["count"] for tag_id, g in groups.items()}}


def _task_counts(workspace) -> dict:
    tasks = workspace.tasks
    open_count = sum(1 for t in tasks if t["status"] != TASK_STATUS_COMPLETED)
    return {"total": len(tasks), "open": open_count, "completed": len(tasks) - open_count}


@workspace_bp.route("/projects/<project_id>/workspace/tags", methods=["POST"])
@login_required
def add_tag_occurrence_route(project_id):
    """Add Tag / Highlight / Important / Question - one route for all
    four toolbar actions (Section 5's own "Highlight is honestly just
    another built-in tag" design - see BUILT_IN_TAGS). `tag_id` selects
    an existing tag (built-in or custom); `new_tag_name`+`new_tag_color`
    creates (or, on a normalized-name match, reuses) a custom tag first."""
    _, store, workspace = _load_workspace_or_404(project_id)

    tag_id = (request.form.get("tag_id") or "").strip()
    new_tag_name = (request.form.get("new_tag_name") or "").strip()
    new_tag_color = (request.form.get("new_tag_color") or "").strip()

    try:
        if not tag_id and new_tag_name:
            tag = store.create_custom_tag(workspace, new_tag_name, new_tag_color, actor=_reviewer())
            workspace = store.get(project_id)
            tag_id = tag["id"]
        elif not tag_id:
            return jsonify({"ok": False, "error": "A tag is required."}), 400

        occurrence = store.add_tag_occurrence(workspace, tag_id, _source_anchor_from_form(), actor=_reviewer())
    except CaseWorkspaceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    workspace = store.get(project_id)
    tag = store.resolve_tag(workspace, tag_id)
    return jsonify({
        "ok": True,
        "occurrence": occurrence,
        "tag": tag,
        "counts": _tag_counts(workspace),
    })


@workspace_bp.route("/projects/<project_id>/workspace/tags/<occurrence_id>/remove", methods=["POST"])
@login_required
def remove_tag_occurrence_route(project_id, occurrence_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        store.remove_tag_occurrence(workspace, occurrence_id)
    except CaseWorkspaceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 404

    workspace = store.get(project_id)
    return jsonify({"ok": True, "counts": _tag_counts(workspace)})


@workspace_bp.route("/projects/<project_id>/workspace/tags/for-selection", methods=["GET"])
@login_required
def tag_occurrences_for_selection_route(project_id):
    """CLAUDE-P40-VW8-QA (selection-toolbar reversibility correction):
    read-only lookup of every occurrence (built-in or custom Tag) whose
    range OVERLAPS the given [start_offset, end_offset) window on this
    exact source anchor - the client-side complement to app.py's own
    `hotlinks` filter, which only ever draws ONE <mark> per position
    when occurrences overlap (Section 11's own documented "first-
    starting wins" resolution). A live text selection can span an
    occurrence that lost that resolution and never got its own visible
    <mark> at all - this endpoint is the only reliable way the
    contextual selection menu can know "multiple Tags are attached
    here" in that case, not scraping rendered DOM. Never creates or
    mutates anything; same authorization boundary as every other
    workspace read (login + project access via _load_workspace_or_404)."""
    _, store, workspace = _load_workspace_or_404(project_id)

    def _int_or_none(raw):
        try:
            return int(raw)
        except (TypeError, ValueError):
            return None

    scope = (request.args.get("anchor_scope") or "").strip()
    case_id = (request.args.get("anchor_case_id") or "").strip() or None
    message_id = (request.args.get("anchor_message_id") or "").strip() or None
    guidance_key = (request.args.get("anchor_guidance_key") or "").strip() or None
    start_offset = _int_or_none(request.args.get("anchor_start_offset"))
    end_offset = _int_or_none(request.args.get("anchor_end_offset"))
    if scope not in KNOWN_CONVERSATION_ANCHOR_SCOPES or start_offset is None or end_offset is None or end_offset <= start_offset:
        return jsonify({"ok": False, "error": "A valid selection anchor is required."}), 400

    applied = []
    for occ in workspace.tag_occurrences:
        anchor = occ["source_anchor"]
        if anchor.get("scope") != scope:
            continue
        if scope == CONVERSATION_ANCHOR_SCOPE_CASE and anchor.get("case_id") != case_id:
            continue
        if scope == CONVERSATION_ANCHOR_SCOPE_GUIDANCE:
            if anchor.get("guidance_key") != guidance_key:
                continue
        elif anchor.get("message_id") != message_id:
            continue
        occ_start, occ_end = anchor.get("start_offset"), anchor.get("end_offset")
        if occ_start is None or occ_end is None:
            continue
        # Overlap, not containment - a selection partially covering an
        # existing tagged range must still surface it as removable
        # (Section "Selection precision": "Partial overlap with a
        # tagged range").
        if occ_start >= end_offset or occ_end <= start_offset:
            continue
        tag = store.resolve_tag(workspace, occ["tag_id"])
        if tag is None:
            continue
        applied.append({
            "occurrence_id": occ["id"],
            "tag_id": tag["id"],
            "tag_name": tag["name"],
            "tag_color": tag["color"],
            "start_offset": occ_start,
            "end_offset": occ_end,
        })
    applied.sort(key=lambda a: a["start_offset"])
    return jsonify({"ok": True, "applied": applied})


@workspace_bp.route("/projects/<project_id>/workspace/tasks", methods=["POST"])
@login_required
def create_task_route(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    title = request.form.get("title") or ""
    try:
        task = store.create_task(workspace, _source_anchor_from_form(), title=title, actor=_reviewer())
    except CaseWorkspaceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    workspace = store.get(project_id)
    return jsonify({"ok": True, "task": task, "counts": _task_counts(workspace)})


@workspace_bp.route("/projects/<project_id>/workspace/tasks/<task_id>/complete", methods=["POST"])
@login_required
def complete_task_route(project_id, task_id):
    """Unlike Tag/Task CREATION (Section 12's own explicit "confirm Tasks
    and Tags appear immediately in Lists" browser-verification step),
    nothing requires completion/reopening to update without a reload -
    a classic form-POST + redirect, this app's normal convention for
    every other mutation, is simpler and lower-risk than extending the
    fetch()-based live-DOM-patch machinery to also move a Task between
    the Open/Completed groups client-side."""
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        store.complete_task(workspace, task_id, actor=_reviewer())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/tasks/<task_id>/reopen", methods=["POST"])
@login_required
def reopen_task_route(project_id, task_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    try:
        store.reopen_task(workspace, task_id, actor=_reviewer())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    anchor_type = (request.form.get("anchor_type") or "").strip()
    anchor_id = (request.form.get("anchor_id") or "").strip()
    anchor = None
    if anchor_type and anchor_id:
        anchor = asdict(Anchor(
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            description=(request.form.get("anchor_description") or None),
        ))

    _run_conversation_turn(
        project_id, store, workspace, None, text, anchor=anchor,
        current_view=request.form.get("current_view"),
        selected_source_id=request.form.get("selected_source_id"),
    )

    # CLAUDE-P40-B (3.5)'s original rationale here (a "#conversation-dock"
    # fragment, so the reviewer lands on the reply instead of the top of
    # Project Home) stopped being true once P40-E2B turned the dock from a
    # collapsible <details> into an always-visible <div> - the fragment's
    # only remaining effect was the browser's own native anchor-scroll,
    # which targets this sticky, bottom-pinned panel's own top edge, not
    # the newest message, and fights the JS's own scroll-to-newest logic
    # on a `scroll-behavior: smooth` container (CLAUDE-CA1C-UX-FIX-01: the
    # live-reported "starts too high, stops short" bug). Removed - the
    # dock is always on screen already (nothing to "land on" it for), and
    # static/js/case_workspace.js's own justSent-flagged logic is now the
    # one, sole owner of scrolling this conversation to its newest entry.
    return redirect(url_for("workspace.show_workspace", project_id=project_id))


@workspace_bp.route("/projects/<project_id>/workspace/context/clear", methods=["POST"])
@login_required
def clear_selected_context(project_id):
    """
    CLAUDE-POSTCAMEL-CA1B (Section 9, clear-selection behavior): the
    one explicit, PM-initiated way to clear the persisted "professional
    context" slot (Requirement/Finding/Source) - _load_workspace_or_404
    is the entire authorization boundary here, same as every other
    project-scoped route; there is nothing else to validate since
    clearing a session key cannot leak or corrupt anything.
    """
    _load_workspace_or_404(project_id)
    _clear_persisted_selection(project_id)
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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

    # CLAUDE-POSTCAMEL-CA1A: the original message's own selected_source_id
    # (if any) must be replayed the same way its anchor already is -
    # found live, during this stage's own Walkthrough A, that omitting
    # this silently changed the answer on re-run (a Source-selection-
    # grounded reply became an honest-but-wrong "nothing selected" reply
    # the second time, purely because this one field wasn't carried
    # forward - exactly the "inconsistent action availability" this
    # stage's own Latent Regression Watch warns against).
    _run_conversation_turn(
        project_id, store, workspace, case, message["text"], anchor=anchor,
        selected_source_id=message.get("selected_source_id"),
    )

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
    # CLAUDE-CA1D-ATTENTION-STATE-02: must run AFTER the finding_reviewed
    # event above, not before - see record_item_reviewed's own docstring
    # for why the ordering is load-bearing for has_unreviewed_change's
    # correctness (this reviewer's own action must not immediately look
    # unreviewed again against their own just-created audit event).
    store.record_item_reviewed(workspace, reviewer=_reviewer(), object_id=finding_id)

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
    # CLAUDE-CA1D-ATTENTION-STATE-02: must run AFTER the finding_reviewed
    # event above - see validate_finding's identical comment and
    # record_item_reviewed's own docstring.
    store.record_item_reviewed(workspace, reviewer=_reviewer(), object_id=finding_id)

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    flash("Requirement registered.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


@workspace_bp.route("/projects/<project_id>/workspace/requirements/<requirement_id>/adjudicate", methods=["POST"])
@login_required
def adjudicate_requirement(project_id, requirement_id):
    """Records a RequirementAdjudication (Foundation Batch K) - the
    compliance determination against a governed Requirement, distinct
    from Finding Disposition. See
    CaseWorkspaceStore.record_requirement_adjudication.

    CLAUDE-POSTCAMEL-COMM-I5A: `attribution` is REQUIRED here, at the
    real product-facing route, even though the store method itself
    treats it as optional (backward-compatible with pre-existing direct
    callers) - this is the actual boundary this correction enforces: no
    adjudication reaches governed state through the ordinary pathway
    without an explicit, self-declared choice between "I am a human
    reviewer personally recording my own judgment" and "this is an
    agent/automated assessment", never a silent default to either.
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    outcome = request.form.get("outcome")
    reasoning = request.form.get("reasoning")
    case_id = request.form.get("case_id")
    attribution = request.form.get("attribution")
    evidence_finding_ids = [v for v in request.form.getlist("evidence_finding_id") if v]
    evidence_relationship_ids = [v for v in request.form.getlist("evidence_relationship_id") if v]

    if attribution not in KNOWN_ADJUDICATION_ATTRIBUTIONS:
        flash(
            "An adjudication must explicitly state whether it reflects your own "
            "personal review or an agent/automated assessment - choose one.",
            "error",
        )
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id))

    try:
        store.record_requirement_adjudication(
            workspace,
            requirement_id=requirement_id,
            outcome=outcome,
            adjudicator=_reviewer(),
            reasoning=reasoning,
            evidence_finding_ids=evidence_finding_ids or None,
            evidence_relationship_ids=evidence_relationship_ids or None,
            attribution=attribution,
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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    try:
        store.revise_requirement(
            workspace, requirement_id=requirement_id, actor=_reviewer(),
            reason=reason, authority_class=authority_class,
            governance_log=_log(), text_reference=text_reference,
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    try:
        store.record_participant(
            workspace, name=name, role_type=role_type, created_by=_reviewer(),
            note=note, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    flash("Go/No-Go decision recorded.", "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

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
    return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))


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
    store.add_message(
        workspace, case_id, role="system", text="RFI draft request cancelled.",
        action_taken="rfi_cancelled", content_class=CONTENT_CLASS_DETERMINISTIC_CALCULATION,
    )
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
        action_taken="rfi_preview_shown", content_class=CONTENT_CLASS_DETERMINISTIC_CALCULATION,
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
        action_taken=f"rfi_draft_created:{draft['id']}", content_class=CONTENT_CLASS_DETERMINISTIC_CALCULATION,
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


# -- CLAUDE-MM8: Governed Creation, Editing, Review, and Accountable -------
# Work Products. Classic form-POST + redirect throughout, matching RFI's
# own established precedent exactly (not MM6/MM7's fetch()-based JSON
# convention) - Part 21's own instruction to treat RFI as one proof of
# this stage's own architecture, not a separate pattern. Works with
# JavaScript disabled, matching this codebase's own accessibility
# precedent (e.g. "+ New Investigation" - a real <a href>/<form>, not a
# JS-only affordance).

_WORK_PRODUCT_SECTION_FIELDS = {
    "risk": ("description", "probability", "impact", "mitigation", "owner"),
    "team_member": ("name", "role", "company", "contact"),
    "narrative": ("text",),
}


def _work_product_section_content_from_form(section_type: str) -> dict:
    fields = _WORK_PRODUCT_SECTION_FIELDS.get(section_type, ("text",))
    return {f: request.form.get(f, "").strip() for f in fields if (request.form.get(f) or "").strip()}


def _work_product_evidence_links_from_form() -> list[dict]:
    """A section's own evidence citations, submitted as parallel
    `evidence_type`/`evidence_id` repeated form fields (one pair per
    citation row) - the same bounded, no-JS-required shape the content
    fields above use, rather than a single free-text field a user could
    fill with anything."""
    types = request.form.getlist("evidence_type")
    ids = request.form.getlist("evidence_id")
    return [
        {"object_type": t.strip(), "object_id": i.strip()}
        for t, i in zip(types, ids) if t.strip() and i.strip()
    ]


@workspace_bp.route("/projects/<project_id>/workspace/work-products", methods=["POST"])
@login_required
def create_work_product(project_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = request.form.get("case_id") or None
    _require_visible_case(store, workspace, case_id)

    try:
        work_product = store.create_work_product(
            workspace, artifact_type=request.form.get("artifact_type") or "report",
            title=request.form.get("title") or "", created_by=_reviewer(), case_id=case_id,
            source_finding_id=request.form.get("source_finding_id") or None,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, case=case_id, view="overview" if not case_id else None))

    flash(f'Work product "{work_product["title"]}" created as a draft.', "success")
    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product["id"]))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/sections", methods=["POST"])
@login_required
def add_work_product_section(project_id, work_product_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    section_type = request.form.get("section_type") or "narrative"
    try:
        store.add_work_product_section(
            workspace, work_product_id, section_type=section_type,
            content=_work_product_section_content_from_form(section_type),
            content_class=request.form.get("content_class") or "human_authored", author=_reviewer(),
            evidence_links=_work_product_evidence_links_from_form(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/sections/<section_id>", methods=["POST"])
@login_required
def edit_work_product_section(project_id, work_product_id, section_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    work_product = store.get_work_product(workspace, work_product_id)
    section = next((s for s in work_product["sections"] if s["id"] == section_id), None) if work_product else None
    if section is None:
        abort(404)

    try:
        store.edit_work_product_section(
            workspace, work_product_id, section_id,
            content=_work_product_section_content_from_form(section["section_type"]),
            actor=_reviewer(), reason=request.form.get("reason") or None, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/sections/<section_id>/accept", methods=["POST"])
@login_required
def accept_work_product_section(project_id, work_product_id, section_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        store.accept_work_product_section(workspace, work_product_id, section_id, actor=_reviewer(), governance_log=_log())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/sections/<section_id>/remove", methods=["POST"])
@login_required
def remove_work_product_section(project_id, work_product_id, section_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        store.remove_work_product_section(
            workspace, work_product_id, section_id, actor=_reviewer(),
            reason=request.form.get("reason") or None, governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/sections/reorder", methods=["POST"])
@login_required
def reorder_work_product_sections(project_id, work_product_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        store.reorder_work_product_sections(
            workspace, work_product_id, request.form.getlist("section_id"), actor=_reviewer(), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/review", methods=["POST"])
@login_required
def review_work_product(project_id, work_product_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        store.record_work_product_review(
            workspace, work_product_id, reviewer=_reviewer(), role=session.get("role") or "unspecified",
            decision=request.form.get("decision") or "revisions_required",
            comments=request.form.get("comments") or None, conditions=request.form.get("conditions") or None,
            unresolved_contradiction=bool(request.form.get("unresolved_contradiction")), governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/approve-for-issue", methods=["POST"])
@login_required
def approve_work_product_for_issue(project_id, work_product_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        store.approve_work_product_for_issue(workspace, work_product_id, actor=_reviewer(), governance_log=_log())
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/issue", methods=["POST"])
@login_required
def issue_work_product(project_id, work_product_id):
    """Section 7/18's own point of no return - Approval-Gated exactly
    like RFI issue (services.rfi_export's own issue_rfi_draft), since
    both are consequential, irreversible-in-effect actions ("once issued
    it cannot be un-issued")."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    work_product = store.get_work_product(workspace, work_product_id)
    if work_product is None:
        abort(404)

    gate = _require_approval(
        "work_product_issue",
        f'Issue "{work_product["title"]}" (v{work_product["version"]}). Once issued it cannot be un-issued - '
        "further changes require creating a new revision.",
        project_id, case_id,
    )
    if gate is not None:
        return gate

    try:
        store.issue_work_product(workspace, work_product_id, actor=_reviewer(), governance_log=_log())
        flash("Work product issued.", "success")
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")

    return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/revise", methods=["POST"])
@login_required
def revise_work_product(project_id, work_product_id):
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)

    try:
        result = store.revise_work_product(
            workspace, work_product_id, actor=_reviewer(), reason=request.form.get("reason") or None,
            governance_log=_log(),
        )
    except CaseWorkspaceError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))

    flash("New revision created - the previously issued version remains unchanged and recoverable.", "success")
    return redirect(url_for(
        "workspace.show_workspace", project_id=project_id, work_product=result["new_work_product"]["id"],
    ))


@workspace_bp.route("/projects/<project_id>/workspace/work-products/<work_product_id>/export.<export_format>")
@login_required
def export_work_product_route(project_id, work_product_id, export_format):
    """A read operation, matching export_rfi_draft's own precedent
    exactly: Case-visibility-checked but NOT archived-state-checked (an
    issued work product belonging to an archived Case remains readable/
    exportable), gated by the same ACTION_EXPORT policy every other
    export route in this file already uses."""
    _, store, workspace = _load_workspace_or_404(project_id)
    case_id = _work_product_case_id(workspace, work_product_id)
    _require_visible_case(store, workspace, case_id)
    export_gate = _require_export_allowed(workspace, project_id)
    if export_gate is not None:
        return export_gate

    work_product = store.get_work_product(workspace, work_product_id)
    if work_product is None:
        abort(404)

    try:
        buffer, checksum = export_work_product(work_product, export_format)
    except WorkProductExportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id, work_product=work_product_id))

    store.record_work_product_export(
        workspace, work_product_id, export_format=export_format, exported_by=_reviewer(),
        checksum=checksum, governance_log=_log(),
    )

    mimetypes_by_format = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    status_label = "issued" if work_product["state"] == "issued" else "draft"
    return send_file(
        buffer, mimetype=mimetypes_by_format[export_format], as_attachment=True,
        download_name=f"{work_product['artifact_type']}-{work_product['id'][:8]}-v{work_product['version']}-{status_label}.{export_format}",
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
        return redirect(url_for("workspace.show_workspace", project_id=project_id, view="overview"))

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"RFI-{project_id}.docx",
    )
