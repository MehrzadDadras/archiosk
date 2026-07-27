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
from datetime import datetime, timezone
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
    KNOWN_RESOLUTION_OUTCOMES,
    MESSAGE_ORIGIN_HUMAN,
    OBJECT_KIND_CASE,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_REQUIREMENT,
    REQUIREMENT_ADJUDICATION_OUTCOMES,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
    REQUIREMENT_STATUS_SUPERSEDED,
    SOURCE_KIND_PROJECT_DOCUMENT,
    SOURCE_KIND_TEXT_RECORD,
    Anchor,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DISPOSITIONS,
    REVIEWER_VALIDATION_STATES,
)
from services.conversation_interpreter import interpret_message
from services.governance import GovernanceLog
from services.ingestion import document_source_payload, get_registry
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
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    store = _store()
    workspace = store.get_or_create(
        project_id, register_document_source=document_source_payload(document),
    )
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

    since_last_visit = None
    if active_case is None:
        previous_visit_at = workspace.last_viewed_by.get(_reviewer())
        if previous_visit_at is not None:
            new_event_count = sum(
                1 for e in _log().read(project_id) if e.created_at > previous_visit_at
            )
            since_last_visit = {"previous_visit_at": previous_visit_at, "new_event_count": new_event_count}
        workspace.last_viewed_by[_reviewer()] = datetime.now(timezone.utc).isoformat()
        store.save(workspace)

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
    recent_governance_events = list(reversed(_log().read(project_id)))[:25]

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
        activities=store.activities_for_case(workspace, active_case["id"]) if active_case else [],
        unpromoted_requirement_items=unpromoted_requirement_items,
        requirements_view=requirements_view,
        compliance_rollup=compliance_rollup,
        revisited_requirements_count=revisited_requirements_count,
        adjudication_outcomes=REQUIREMENT_ADJUDICATION_OUTCOMES,
        recent_governance_events=recent_governance_events,
        temporal_obligations_view=temporal_obligations_view,
        threads_view=threads_view,
        known_usernames=known_usernames,
        resolution_outcomes=KNOWN_RESOLUTION_OUTCOMES,
        project_home_summary=project_home_summary,
        since_last_visit=since_last_visit,
        project_conversation_view=project_conversation_view,
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


@workspace_bp.route("/projects/<project_id>/workspace/details", methods=["POST"])
@login_required
def edit_project_details(project_id):
    """Overflow menu -> Edit Project Details (Prompt 3 #3) - presentation
    only, see CaseWorkspaceStore.set_project_details."""
    _, store, workspace = _load_workspace_or_404(project_id)
    store.set_project_details(
        workspace,
        actor=_reviewer(),
        display_title=(request.form.get("display_title") or "").strip(),
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
    )
    flash("Project Operating Instructions updated.", "success")
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
    (quick_start, which still always creates a Case first - unchanged),
    and a project-level aperture with no Case at all (discuss_object) -
    the same conversational entry point, reached from three places.

    `anchor` (Anchor shape - anchor_type/anchor_id/source_id/location/
    description) records what the sender was actually looking at,
    independent of which conversation this lands in - see
    ConversationMessage's own docstring. Only ever set on the human
    message; the system's reply isn't "about" anything itself, it's a
    response to one.
    """
    case_id = case["id"] if case is not None else None
    human_message = store.add_message(workspace, case_id, role="human", text=text, anchor=anchor)

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
    """
    _, store, workspace = _load_workspace_or_404(project_id)

    text = (request.form.get("text") or "").strip()
    if not text:
        flash("Describe what you want to work on to start.", "error")
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

    return redirect(url_for("workspace.show_workspace", project_id=project_id))


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

    draft = next((d for d in workspace.rfi_drafts if d["id"] == draft_id), None)
    if draft is None:
        abort(404)

    buffer = build_rfi_draft_docx(draft)
    status_label = "issued" if draft["status"] == "issued" else "draft"
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
    already calls this same function, but that JSON API blueprint is
    deliberately unauthenticated (see services/auth.py's own docstring:
    "token/key-based API auth is a different concern from a session-
    cookie login gate"), a pre-existing, documented design boundary this
    route doesn't touch or remove. This route exists so that a link
    surfaced from inside the (login-gated) Case Workspace never itself
    becomes an unauthenticated download path merely because it's
    convenient to link to the existing one.

    Project-scoped, not Case-scoped: the underlying RFI is built from
    the legacy consistency-check pipeline's flagged contradictions
    (ParsedDocument.consistency_flags), which has no Case/visibility
    concept of its own - the same access rule this route's own
    accordion (RFI Export, in case_workspace.html) already relies on:
    any authenticated user may view/download, since there is no
    per-project membership model in this legacy pipeline to check
    against.
    """
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    try:
        buffer = build_rfi_docx(document)
    except RFIExportError as exc:
        flash(str(exc), "error")
        return redirect(url_for("workspace.show_workspace", project_id=project_id))

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"RFI-{project_id}.docx",
    )
