"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flask import Blueprint, abort, current_app, flash, jsonify, make_response, redirect, render_template, request, session, url_for
from werkzeug.datastructures import FileStorage

from services.auth import (
    admin_required, check_credentials, is_admin, is_authenticated, log_in, log_out, login_required,
    user_can_upload_to_storage,
)
from services.rate_limit import limiter
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
from services.environment_capabilities import (
    OPERATING_ENVIRONMENT_LABELS,
    OPERATING_ENVIRONMENT_SUBTITLES,
    is_valid_operating_environment,
)
from services.project_perspective import entry_choice_view, operating_environment_for
from services.governance import GovernanceError
from services.ingestion import UploadError, get_governance_log, get_registry, ingest_folder_upload, ingest_upload
from services.drawing_intake import (
    CANDIDATE_FIELDS, FIELD_LABELS, PendingUploadStore, STATUS_CONFIRMED, STATUS_CORRECTED, analyze_upload,
)
from services.password_reset import (
    complete_password_reset, get_valid_reset_token, is_dev_fallback_active, request_password_reset,
)
from services.verification_access import (
    consume_verification_token, get_valid_verification_token, is_verification_session,
    revoke_verification_access,
)
from services.requirements_registry import RequirementsRegistry
from services.developer_tools import (
    qualifies_as_synthetic_test_project,
    reset_analysis_state,
    reset_test_project,
)
from services.trial_request import submit_trial_request
from services.developer_ccn import (
    attach_selected_object as attach_developer_object,
    context_for_project as developer_context_for_project,
    handle_command as handle_developer_ccn_command,
    is_ccn_command,
    parse_ccn_command,
)
from services.project_qa import answer_application_question, answer_orientation_question
from services.capability_registry import find_capability_by_phrase
from services.conversation_interpreter import (
    _handle_capability_question,
    _looks_like_capability_question,
)
from services.question_scope import scope_diagnostic
from services.template_identity import identity_for_template_id, template_identity_for_endpoint

portal_bp = Blueprint('portal', __name__)


def _safe_workspace(store: CaseWorkspaceStore, project_id: str):
    """
    Best-effort workspace load for DISPLAY purposes only (project summary
    cards, sidebar names) - never used for anything that writes or governs.
    A workspace file that predates the current schema must not crash an
    entire listing page; _project_summary already tolerates workspace=None
    everywhere, so degrading to "no display_title available yet" for that
    one project is the honest, safe fallback.
    """
    try:
        return store.get(project_id)
    except TypeError:
        return None


def _accessible_documents(registry, store, include_removed: bool = False):
    """
    CLAUDE-P32: every project-LISTING route in this file (index's
    recent-projects, projects_list, global_search) must filter to only
    the accessible set, not merely block direct navigation into an
    unauthorized project -- otherwise a project's filename/metadata
    still leaks through these pages even though opening it 404s.
    Backfills a legacy project's owner the same way
    routes/workspace.py's _load_workspace_or_404 does, so a project
    doesn't sit permanently admin-only just because no one has opened
    its workspace page yet to trigger that backfill.

    CLAUDE-P40-E2: excludes a removed Project (workspace.removed_at)
    from every ordinary listing by default - "Remove Project" (Section
    C) must actually remove it from active Projects/Chats, not just
    hide a button. `include_removed=True` is the one deliberate
    exception, used only by the Removed Projects view below, which
    still goes through this same P32 access filter first - a project
    someone can't already open never becomes visible just because it
    was also removed.
    """
    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    governance_log = get_governance_log(current_app)
    usernames = known_usernames()
    username = session.get("username")
    admin = is_admin()

    documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    accessible = []
    for document in documents:
        # A workspace file that predates the current schema must not
        # take down every project's listing for every user -- fails
        # CLOSED (excluded) on a load error, same reasoning as
        # app.py's _nav_recent_projects fix for the identical risk.
        try:
            workspace = store.get_or_create(document.project_id)
            ensure_owner_backfilled(store, workspace, governance_log, usernames)
            allowed = can_access_project(workspace, username, admin)
            removed = bool(workspace.removed_at)
        except TypeError:
            allowed = False
            removed = False
        if allowed and (removed == include_removed):
            accessible.append(document)
    return accessible


def _require_project_access_or_404(store, project_id: str):
    """Single-project counterpart to _accessible_documents, for the two
    routes below that operate on one project_id directly
    (delete_project, dashboard) rather than listing many."""
    from services.project_access import can_access_project, ensure_owner_backfilled, known_usernames

    workspace = store.get_or_create(project_id)
    ensure_owner_backfilled(store, workspace, get_governance_log(current_app), known_usernames())
    if not can_access_project(workspace, session.get("username"), is_admin()):
        abort(404)
    return workspace


def _project_summary(document, workspace, events) -> dict:
    """
    Shared, read-only project summary used by both the home page's
    recent-projects list and the Projects directory - one real, already-
    governed indicator set, never a fabricated project-health score:
    - requirements_count: len(workspace.requirements) - existing, unmodified.
    - open_rfi_count: RFIDrafts not yet issued - existing status field.
    - pending_attention_count (amber): Attentions still pending response.
    - unresolved_conflict_count (red): the legacy consistency-check's own
      flagged cross-requirement contradictions (document.consistency_flags)
      - the one real "conflict" signal that already exists, not invented.
    - last_activity: the most recent GovernanceLog event's timestamp where
      one exists, else the document's own ingested_at ("created_at").
    No new domain/store methods were added for this - every value above
    comes from an existing, unmodified public read (RequirementsRegistry,
    CaseWorkspaceStore.get, GovernanceLog.read).
    """
    return {
        "project_id": document.project_id,
        "filename": document.filename,
        # Pagescape correction #11: the professional-facing project
        # identity should be its own display_title, not the accident of
        # which document happened to be uploaded first - falls back to
        # filename only until a human sets one via Edit Project Details.
        "display_name": (workspace.display_title if workspace else None) or document.filename,
        "created_at": document.ingested_at,
        "last_activity": events[-1].created_at if events else document.ingested_at,
        "requirements_count": len(workspace.requirements) if workspace else 0,
        "open_rfi_count": (
            len([d for d in workspace.rfi_drafts if d["status"] != "issued"]) if workspace else 0
        ),
        "pending_attention_count": (
            len([a for a in workspace.attentions if a["status"] == "pending"]) if workspace else 0
        ),
        "unresolved_conflict_count": len(document.consistency_flags) if document.consistency_checked else 0,
    }


@portal_bp.route('/developer-mode/toggle', methods=['POST'])
@admin_required
def toggle_developer_mode():
    """
    CLAUDE-DEVELOPER-MODE-COCKPIT-01, Addendum E: the one toggle for this
    stage's orientation-only Developer Mode - a plain reviewer-session
    flag, never project-scoped and never implying Client/Owner,
    Proponent, or any project authority (see app.py's inject_globals,
    the one place this flag is ever read into template context, for the
    is_admin() re-check that also applies at render time). admin_required
    is the existing, real authorization boundary this reuses rather than
    inventing a second one - a non-admin can never reach this route at
    all (403 via admin_required), so developer_mode can never become
    true in their session through any client-side manipulation, unlike a
    localStorage-only toggle (see UI Reference Mode, templates/base.html)
    would allow.

    This stage grants no capability beyond a persistent visual state -
    no terminal, no repo explorer, no editor - so the redirect target
    only needs to be a safe, always-valid page, not "back to exactly
    where you were": Archiosk Home, matching the fixed-destination
    pattern this app's other menu actions already use (Security,
    Operations), not an unprecedented request.referrer-based redirect.
    """
    session['developer_mode'] = not session.get('developer_mode', False)
    if not session['developer_mode']:
        session.pop('developer_ui_reveal', None)
    return redirect(url_for('portal.index'))


@portal_bp.route('/developer-mode/ui-reveal', methods=['POST'])
@admin_required
def toggle_developer_ui_reveal():
    """Toggle the server-backed template identity reveal for this admin session."""
    if not session.get('developer_mode'):
        abort(403)
    session['developer_ui_reveal'] = not session.get('developer_ui_reveal', False)
    return redirect(request.referrer or url_for('portal.index'))


def _require_developer_tools():
    """Server-side second gate for destructive developer tooling."""
    if not is_admin() or not session.get("developer_mode"):
        abort(403)


def _require_developer_composer():
    """Application-level Composer is an admin Developer Mode capability."""
    if not is_admin() or not session.get("developer_mode"):
        abort(403)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _developer_home_chats() -> list[dict]:
    """Read the existing session envelope, migrating the legacy message list."""
    chats = session.get("developer_home_chats")
    if not isinstance(chats, list):
        legacy = session.get("developer_home_messages", [])
        legacy = legacy if isinstance(legacy, list) else []
        now = _utc_now()
        chats = [{"id": str(uuid.uuid4()), "title": "New Developer chat", "created_at": now,
                  "updated_at": now, "messages": legacy[-40:]}]
        session["developer_home_chats"] = chats
        session["developer_home_current_chat_id"] = chats[0]["id"]
    return [chat for chat in chats if isinstance(chat, dict) and isinstance(chat.get("messages", []), list)]


def _developer_current_chat() -> dict:
    chats = _developer_home_chats()
    current_id = session.get("developer_home_current_chat_id")
    chat = next((item for item in chats if item.get("id") == current_id), None)
    if chat is None:
        chat = chats[0]
        session["developer_home_current_chat_id"] = chat["id"]
    session["developer_home_messages"] = chat.get("messages", [])[-40:]
    return chat


def _developer_home_messages() -> list[dict]:
    return list(_developer_current_chat().get("messages", []))


def _record_developer_home_message(role: str, text: str, **extra) -> None:
    chats = _developer_home_chats()
    chat = _developer_current_chat()
    message = {"role": role, "text": text[:4000], "created_at": _utc_now(), **extra}
    chat.setdefault("messages", []).append(message)
    chat["messages"] = chat["messages"][-40:]
    if role == "human" and chat.get("title") == "New Developer chat":
        chat["title"] = text[:80] + ("…" if len(text) > 80 else "")
    chat["updated_at"] = message["created_at"]
    session["developer_home_chats"] = chats[-12:]
    session["developer_home_current_chat_id"] = chat["id"]
    session["developer_home_messages"] = chat["messages"]


def _new_developer_chat() -> dict:
    now = _utc_now()
    chat = {"id": str(uuid.uuid4()), "title": "New Developer chat", "created_at": now,
            "updated_at": now, "messages": []}
    chats = _developer_home_chats()
    session["developer_home_chats"] = (chats + [chat])[-12:]
    session["developer_home_current_chat_id"] = chat["id"]
    session["developer_home_messages"] = []
    return chat


def _attach_pending_application_selection(governance_log, actor: str) -> None:
    """Attach a home selection after /CCN starts, without project scope."""
    pending = session.get("developer_application_selection")
    if not isinstance(pending, dict):
        return
    attach_developer_object(
        session=session,
        object_type=pending.get("object_type", "application_object"),
        object_id=pending.get("object_id", "unknown"),
        label=pending.get("label", "selected application object"),
        project_id=None,
        governance_log=governance_log,
        actor=actor,
    )


def _developer_home_context() -> dict | None:
    """Return active CCN plus pending application selection, if any."""
    context = developer_context_for_project(
        session,
        None,
        template_identity=template_identity_for_endpoint("portal.index"),
    )
    pending = session.get("developer_application_selection")
    if isinstance(pending, dict):
        if context is None:
            context = {
                "scope": "application",
                "status": "selection_only",
                "selected_elements": [],
            }
        context["selected_elements"] = [*context.get("selected_elements", []), pending]
    return context


def _developer_application_reply(text: str, context: dict | None) -> str:
    """Answer bounded, evidence-grounded application-level questions.

    Home has no project evidence, so this responder only states repository
    facts that are stable and directly inspectable. Unknown implementation
    lineage remains an explicit request for a more specific selection.
    """
    lowered = text.lower()
    selected = (context or {}).get("selected_elements", [])
    labels = ", ".join(item.get("label", "selected object") for item in selected[-3:])
    lens = " The active CCN is treated as a contemplated-change lens; nothing is authorized." if (context and context.get("status") == "active") else ""

    # Resolve ordinary conversational deictics before falling back to
    # generic Developer Mode guidance.  The user should be able to continue
    # the original question after identifying the target, not translate it
    # into an internal anchor/schema request.
    if not selected and not ("developer mode" in lowered and ("badge" in lowered or "icon" in lowered or "font" in lowered or "bold" in lowered)):
        ambiguous_match = re.search(r"\b(?:this|that|the)\s+(text|button|panel|icon)\b", lowered)
        if ambiguous_match:
            kind = ambiguous_match.group(1)
            options = {
                "text": "pick it on the screen, type or paste the text here, or tell me which panel it is on",
                "button": "select it, name the button, or tell me which panel or menu it is in",
                "panel": "select it or tell me which panel you mean",
                "icon": "select it, describe it, or tell me where it appears",
            }
            return f"Which {kind} do you mean? You can {options[kind]}." + lens

    explicit_technical_request = any(phrase in lowered for phrase in (
        "show me the css", "show me css", "which file", "what file", "how would i code",
        "code this myself", "edit the css", "edit the template", "implementation instructions",
    ))
    if explicit_technical_request or ("where" in lowered and ("implement" in lowered or "code" in lowered or "control" in lowered)) or ("how" in lowered and "implemented" in lowered):
        return (
            (f"The selected context is {labels}. " if labels else "No application object is selected. ")
            + "I can provide a repository-grounded implementation trace when you explicitly want "
            "the code or file-level path. The current application context does not authorize any "
            "edit."
            + lens
        )
    if ("chat history" in lowered or "conversation history" in lowered) and ("delete" in lowered or "remove" in lowered):
        return (
            "There is no ordinary Developer Composer action that deletes chat history. "
            "Project conversations are persisted with the project workspace; the protected "
            "Developer Tools reset is a separate administrative operation and is not invoked "
            "by a question. I can trace the storage or prepare a contemplated change, but no "
            "mutation is authorized here."
            + lens
        )
    if "project list" in lowered or ("left" in lowered and "project" in lowered):
        return (
            "The project list is rendered by the authenticated Home/Projects routes and their "
            "templates, while workspace navigation is handled separately. Select the project "
            "list surface for an exact implementation trace; this explanation does not change it."
            + lens
        )
    if "test" in lowered or "tests" in lowered:
        return (
            "The Developer Mode/CCN behavior is covered by `tests/test_developer_mode_ccn_01.py` "
            "and the home Composer vertical proof by `tests/test_developer_home_composer_01.py`. "
            "No test execution or mutation is authorized by this question."
            + lens
        )
    if selected:
        return (
            f"{labels.capitalize()} is a reasonable candidate for a bounded change. I would "
            "preserve the existing component and assess the smallest change that achieves the "
            "requested outcome, then verify affected surfaces and focused tests. This is a "
            "recommendation only; conversation and CCN context do not authorize implementation."
            + lens
        )
    return (
        "I can assess that as a proposed bounded change to ARCHIOSK: preserve the existing "
        "component, identify the affected surface and consequences, and verify focused tests. "
        "This is a recommendation only; conversation and CCN context do not authorize "
        "implementation."
        + lens
    )


def _developer_model_reply(text: str, context: dict | None) -> tuple[str | None, dict]:
    """Run the canonical model-backed application conversation seam."""
    result = answer_application_question(
        question=text,
        developer_context=context,
        recent_history=_developer_home_messages(),
        api_key=current_app.config.get("ANTHROPIC_API_KEY"),
        model=current_app.config.get("ANTHROPIC_MODEL"),
    )
    if result.ran and result.answer:
        return result.answer, {
            "provider": result.provider,
            "model": result.model,
            "needs_clarification": result.needs_clarification,
            # Existing application-context envelope only. This is deliberately
            # not stored under ConversationMessage.grounded_in, which is the
            # project Source-grounding field rendered by case_workspace.html.
            "developer_context": context,
        }
    return None, {"model_unavailable": result.skipped_reason}


@portal_bp.route('/developer-composer', methods=['POST'])
@login_required
def developer_home_composer():
    """Handle the Developer Mode Composer when no project is open.

    This is intentionally application-scoped: it uses the same native CCN
    service as workspace Composer turns, but never fabricates a project_id or
    invokes project evidence interpretation.
    """
    _require_developer_composer()
    text = (request.form.get("message") or "").strip()[:4000]
    if not text:
        return redirect(url_for("portal.index"))
    if request.form.get("project_id"):
        abort(400)

    context = _developer_home_context()
    diagnostic = scope_diagnostic(text, context)
    governance_log = get_governance_log(current_app)
    actor = session.get("username") or "admin"
    if is_ccn_command(text):
        parsed_command = parse_ccn_command(text)
        result = handle_developer_ccn_command(
            text, session=session, actor=actor, governance_log=governance_log, project_id=None,
        )
        _attach_pending_application_selection(governance_log, actor)
        context = _developer_home_context()
        reply = result["reply_text"]
        model_metadata = {}
        # State-only commands remain deterministic. A start command carrying
        # an actual intent also receives a substantive model turn; the
        # acknowledgement is not allowed to swallow the user's proposition.
        if parsed_command and parsed_command[0] == "start" and parsed_command[1]:
            model_reply, model_metadata = _developer_model_reply(
                parsed_command[1], context,
            )
            if model_reply:
                reply = reply + "\n\n" + model_reply
                result["action_taken"] = result["action_taken"] + ":model_answered"
            else:
                reply = reply + "\n\n" + _developer_application_reply(text, context)
        _record_developer_home_message("human", text, developer_context=context, scope_diagnostic=diagnostic)
        _record_developer_home_message("system", reply, action_taken=result["action_taken"], **model_metadata)
        return redirect(url_for("portal.index"))

    reply, model_metadata = _developer_model_reply(text, context)
    action = "developer_application_model_answered"
    if not reply:
        reply = _developer_application_reply(text, context)
        action = "developer_application_model_unavailable"
    _record_developer_home_message("human", text, developer_context=context, scope_diagnostic=diagnostic)
    _record_developer_home_message("system", reply, action_taken=action, **model_metadata)
    return redirect(url_for("portal.index"))


@portal_bp.route('/developer-composer/context', methods=['POST'])
@login_required
def developer_home_context():
    """Attach one application-level home object as conversational context."""
    _require_developer_composer()
    if request.form.get("project_id"):
        abort(400)
    object_type = (request.form.get("object_type") or "application_object").strip()[:80]
    object_id = (request.form.get("object_id") or "").strip()[:200]
    label = (request.form.get("label") or object_id).strip()[:200]
    if not object_id:
        abort(400)
    if object_type == "template_surface":
        identity = identity_for_template_id(object_id)
        if not identity or label != f"{identity['template_id']} · {identity['name']}":
            abort(400)
        label = f"{identity['template_id']} · {identity['name']}"
    selection = {"object_type": object_type, "object_id": object_id, "label": label, "project_id": None}
    session["developer_application_selection"] = selection
    if isinstance(session.get("developer_ccn"), dict) and session["developer_ccn"].get("status") == "active":
        attach_developer_object(
            session=session, object_type=object_type, object_id=object_id, label=label,
            project_id=None, governance_log=get_governance_log(current_app),
            actor=session.get("username") or "admin",
        )
    return redirect(url_for("portal.index"))


@portal_bp.route('/developer-composer/new-chat', methods=['POST'])
@login_required
def developer_home_new_chat():
    _require_developer_composer()
    _new_developer_chat()
    return redirect(url_for("portal.index"))


@portal_bp.route('/developer-composer/select-chat', methods=['POST'])
@login_required
def developer_home_select_chat():
    _require_developer_composer()
    chat_id = request.form.get("chat_id")
    if not any(item.get("id") == chat_id for item in _developer_home_chats()):
        abort(404)
    session["developer_home_current_chat_id"] = chat_id
    _developer_current_chat()
    return redirect(url_for("portal.index"))


@portal_bp.route('/developer-composer/delete-chat', methods=['POST'])
@login_required
def developer_home_delete_chat():
    _require_developer_composer()
    if request.form.get("confirmation") != "DELETE CHAT":
        abort(400)
    chats = _developer_home_chats()
    chat_id = request.form.get("chat_id") or session.get("developer_home_current_chat_id")
    target = next((item for item in chats if item.get("id") == chat_id), None)
    if target is None:
        abort(404)
    remaining = [item for item in chats if item.get("id") != chat_id]
    if not remaining:
        now = _utc_now()
        remaining = [{"id": str(uuid.uuid4()), "title": "New Developer chat", "created_at": now,
                      "updated_at": now, "messages": []}]
    session["developer_home_chats"] = remaining
    session["developer_home_current_chat_id"] = remaining[-1]["id"]
    session["developer_home_messages"] = remaining[-1].get("messages", [])
    get_governance_log(current_app).append(
        project_id=None, event_type="developer_chat_deleted", actor=session.get("username") or "admin",
        role=session.get("role") or "admin", payload={"conversation_id": chat_id, "outcome": "deleted"},
    )
    return redirect(url_for("portal.index"))


def _developer_tool_projects():
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    projects = []
    for project_id in registry.list_ids():
        workspace = _safe_workspace(store, project_id)
        document = registry.get(project_id)
        if workspace is None or document is None:
            continue
        projects.append({
            "project_id": project_id,
            "name": workspace.display_title or document.filename,
            "environment": workspace.operating_environment or "unclassified",
            "removed": bool(workspace.removed_at),
            "synthetic": qualifies_as_synthetic_test_project(workspace),
        })
    return sorted(projects, key=lambda item: item["name"].lower())


@portal_bp.route('/admin/developer-tools', methods=['GET'])
@admin_required
def developer_tools():
    """Admin + explicit Developer Mode surface for repeatable test resets."""
    _require_developer_tools()
    projects = _developer_tool_projects()
    selected_id = request.args.get("project_id", "")
    selected = next((item for item in projects if item["project_id"] == selected_id), None)
    return render_template("developer_tools.html", projects=projects, selected=selected)


@portal_bp.route('/admin/developer-tools/reset-analysis', methods=['POST'])
@admin_required
def developer_reset_analysis():
    _require_developer_tools()
    project_id = (request.form.get("project_id") or "").strip()
    if request.form.get("confirmation") != "RESET ANALYSIS STATE":
        flash("Type RESET ANALYSIS STATE exactly to confirm - nothing was reset.", "error")
        return redirect(url_for("portal.developer_tools", project_id=project_id))
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        abort(404)
    try:
        result = reset_analysis_state(store, workspace, get_governance_log(current_app), actor=session.get("username") or "unknown")
    except Exception:
        current_app.logger.exception("Developer analysis reset failed for %s", project_id)
        flash("Analysis reset failed; the project was rolled back.", "error")
    else:
        flash(f"Analysis state reset. Removed counts: {result['removed_counts']}.", "success")
    return redirect(url_for("portal.developer_tools", project_id=project_id))


@portal_bp.route('/admin/developer-tools/reset-test-project', methods=['POST'])
@admin_required
def developer_reset_test_project():
    _require_developer_tools()
    project_id = (request.form.get("project_id") or "").strip()
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        abort(404)
    expected = f"RESET TEST PROJECT: {workspace.display_title or project_id}"
    if request.form.get("confirmation") != expected:
        flash(f'Type "{expected}" exactly to confirm - nothing was reset.', "error")
        return redirect(url_for("portal.developer_tools", project_id=project_id))
    try:
        result = reset_test_project(store, workspace, get_governance_log(current_app), actor=session.get("username") or "unknown")
    except ValueError as exc:
        flash(str(exc), "error")
    except Exception:
        current_app.logger.exception("Developer test-project reset failed for %s", project_id)
        flash("Test-project reset failed; the project was rolled back.", "error")
    else:
        flash(f"Synthetic test project reset. Removed counts: {result['removed_counts']}.", "success")
    return redirect(url_for("portal.developer_tools", project_id=project_id))


# -- CLAUDE-DIAGNOSTIC-BRIDGE-01: capture a live problem where it happened -----
# Product Owner: "there is no Product Owner/Admin mechanism inside ARCHIOSK to
# send a live product issue directly to the development agent with the relevant
# application context."
#
# @admin_required, not merely @login_required, and that IS the critical boundary
# the Product Owner named: "this must not become a general user -> coding-agent
# channel." An ordinary project user cannot reach these routes at all.
#
# Nothing here transmits anything. ARCHIOSK cannot call a development agent -
# one runs on an operator's own machine when a human starts it - so capture
# writes an inert row that a Claude Code session reads when asked. The receipt
# says "recorded as", never "sent to Claude", because the second would be false.
@portal_bp.route("/developer/diagnostics", methods=["POST"])
@admin_required
def capture_diagnostic():
    """Record one live product problem, with the context the app already knows."""
    from services.diagnostic_report import record

    summary = (request.form.get("summary") or "").strip()
    if not summary:
        flash("Describe the problem before sending it for investigation.", "error")
        return redirect(request.referrer or url_for("portal.index"))

    report = record(
        reported_by=session.get("username") or "unknown",
        summary=summary,
        detail=request.form.get("detail"),
        # The surface the reviewer was ACTUALLY on, taken from the referrer
        # rather than asked for - "do not require the Product Owner to manually
        # reconstruct information the application already knows."
        surface=(request.form.get("surface") or request.referrer or None),
        project_id=(request.form.get("project_id") or None),
        case_id=(request.form.get("case_id") or None),
        trace=request.form.get("trace"),
    )
    flash(
        f"Recorded as diagnostic {report.id}. It is waiting to be investigated - "
        "nothing has been transmitted anywhere.",
        "success",
    )
    return redirect(request.referrer or url_for("portal.index"))


@portal_bp.route("/developer/diagnostics")
@admin_required
def list_diagnostics():
    """Read-only. Investigating, changing code and deploying are separate acts,
    and none of them can be started from this page."""
    from services.diagnostic_report import list_reports

    return render_template("diagnostics.html", reports=list_reports())


# -- CLAUDE-MOBILE-PWA-01: installability ---------------------------------
# Product Owner: "ARCHIOSK should be addable/installable to the phone home
# screen; the installed app launches directly into ARCHIOSK; users should not
# need to reinstall to receive updates."
#
# Served from the SITE ROOT rather than /static/, which is a requirement and
# not a preference: a service worker's scope is its own URL path, so one served
# from /static/sw.js could only ever control /static/*. And both are rendered
# through Jinja so STATIC_VERSION reaches them - that version is baked into the
# worker's cache name, and is the entire mechanism by which an installed phone
# stops using the previous build.
@portal_bp.route("/sw.js")
def service_worker():
    """The service worker, at root scope so it can control the application."""
    response = make_response(render_template("sw.js"))
    response.headers["Content-Type"] = "application/javascript"
    # The worker itself must never be cached, or a deploy could not replace it
    # and the "no frozen shell" guarantee would rest on a stale file.
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@portal_bp.route("/manifest.webmanifest")
def web_manifest():
    """What makes ARCHIOSK installable, and what the icon opens into."""
    response = make_response(render_template("manifest.webmanifest"))
    response.headers["Content-Type"] = "application/manifest+json"
    return response


@portal_bp.route('/')
def index():
    """
    Project-first entry point: "what project are we working on," not a
    marketing page and not "how can I help you today." Authenticated
    visitors see a small, restrained recent-projects list - see
    _project_summary for the indicator set.

    CLAUDE-P40-VW5: an anonymous visit used to render this same
    template's own "identity line + sign-in link" branch, then was
    changed to redirect straight to Sign-in instead ("a fresh
    unauthenticated visit to the normal application entry route must
    begin at Sign-in").

    CLAUDE-CA1D-PUBLIC-LANDING-01: superseded by a new, explicit
    Product Owner decision - archiosk.com's root now needs to be a real
    public front door for a first-time stranger, not an immediate
    redirect to a bare credentials form. Renders the new public landing
    page (templates/landing.html, its own standalone shell - never
    base.html/auth_shell.html) instead of redirecting. Authenticated
    behavior below is completely unchanged; Sign In on that landing
    page still goes straight to portal.login, so direct /login access
    and the existing authentication flow are both fully preserved.

    CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: this is now
    ALSO the consolidated post-sign-in destination (see
    _resolve_next_url, below, and the retired /gateway route further
    down this file) - base.html's own shell already rendered correctly
    with no project open on this exact route before this stage (proven,
    not assumed: this route, /projects, and /upload all already did),
    so consolidating onto it needed no new project-less-shell work, only
    real content for the state itself. The one genuinely new piece is
    the operating-environment entry sequence the Product Owner's own
    disposition requires: establish/derive the user's authorized
    operating environment(s) -> show that environment's own projects ->
    enter a project -> GO orients. `?environment=<value>` is how a
    multi-environment user's explicit choice (or a returning single-
    environment user's own bookmark/link) reaches this route - resolved
    ONLY against `accessible_environments` below, so an unauthorized or
    stale value simply falls back to "ask," never a silent bypass.
    """
    if not is_authenticated():
        return render_template('landing.html')

    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    # CLAUDE-ENTRY-SIMPLIFY-01: the two-card "Choose where you'd like to
    # work" gate is RETIRED, and nothing replaces it here.
    #
    # It looked like a governed choice and was not one. It filtered these six
    # rows for one page load, persisted nothing, granted no authority, set no
    # account role, and was forgotten on the next request - while asking the
    # user, in the product's own voice, to pick a side. A surface must not
    # appear to carry authority it does not have.
    #
    # It also only ever appeared for people whose projects span BOTH
    # environments, which in practice means admins - so the one population
    # that most needs a fast way into their work got an extra door.
    #
    # Entry is now literally the accepted principle again: sign in -> see the
    # projects you can access -> open one. Genuinely useful environment
    # FILTERING did not disappear; it moved to projects_list, where it sits
    # beside search and sort and reads as what it is. See GO-NEUTRAL-ENTRY-01,
    # whose principle this restores rather than reinterprets.
    accessible_environments = _accessible_operating_environments(registry, store)

    # Retiring the gate must not cost the one genuinely useful thing it did:
    # pre-selecting /upload's operating-environment radio so an admin who only
    # ever works one side is not re-answering a settled question. Presetting
    # from an UNAMBIGUOUS fact (they have projects in exactly one environment)
    # rather than from a choice we asked them to make is the same convenience
    # without the false question - and it stays a pre-selection only: /upload's
    # own radio and confirmation checkbox remain the real commissioning step,
    # never bypassed. With more than one environment in play there is nothing
    # to infer, so nothing is preset.
    preset_environment = accessible_environments[0] if len(accessible_environments) == 1 else None

    accessible = _accessible_documents(registry, store)
    workspaces_by_project = {
        document.project_id: _safe_workspace(store, document.project_id)
        for document in accessible
    }
    documents = sorted(accessible, key=lambda d: d.ingested_at, reverse=True)
    recent_projects = [
        _project_summary(document, workspaces_by_project[document.project_id], governance_log.read(document.project_id))
        for document in documents[:6]
    ]

    return render_template(
        'index.html',
        accessible_environments=accessible_environments,
        preset_environment=preset_environment,
        operating_environment_labels=OPERATING_ENVIRONMENT_LABELS,
        operating_environment_subtitles=OPERATING_ENVIRONMENT_SUBTITLES,
        recent_projects=recent_projects,
        developer_home_messages=_developer_home_messages() if is_admin() and session.get("developer_mode") else [],
        developer_home_chats=_developer_home_chats() if is_admin() and session.get("developer_mode") else [],
        developer_home_current_chat_id=session.get("developer_home_current_chat_id") if is_admin() and session.get("developer_mode") else None,
        developer_home_ccn_context=(_developer_home_context()
                                    if is_admin() and session.get("developer_mode") else None),
        developer_application_selection=(session.get("developer_application_selection")
                                         if is_admin() and session.get("developer_mode") else None),
    )


@portal_bp.route('/health')
def health():
    """Liveness/readiness probe for the load balancer and systemd.

    Un-prefixed and unauthenticated by design so it stays stable across
    /api/v1 version bumps. Checks the registry store (the app's only
    real runtime dependency) rather than the Anthropic API, since a
    slow/unreachable model API shouldn't take the whole app out of
    rotation — BHiveParser already degrades to rule-based classification.
    """
    try:
        get_registry(current_app).list_ids()
        registry_ok = True
    except OSError:
        registry_ok = False

    # CLAUDE-P40-E2A2: distinct from plain unreachability - a registry
    # that IS reachable but that automatic Reset/Restore recovery could
    # not resolve safely (see app.py's _register_registry_guard, which
    # already fails every OTHER route closed against this).
    recovery_failed = bool(current_app.config.get('REGISTRY_RECOVERY_FAILED'))

    missing_config = []
    if not current_app.config.get('SECRET_KEY'):
        missing_config.append('FLASK_SECRET_KEY')
    if not current_app.config.get('ANTHROPIC_API_KEY'):
        missing_config.append('ANTHROPIC_API_KEY')

    status_code = 200 if (registry_ok and not recovery_failed) else 503
    return jsonify(
        status='ok' if (registry_ok and not recovery_failed) else 'error',
        checks={
            'registry_store': 'ok' if registry_ok else 'unreachable',
            'registry_recovery': 'failed' if recovery_failed else 'ok',
        },
        missing_config=missing_config,
    ), status_code


def _resolve_next_url() -> str:
    """?next= target after a successful/already-satisfied login.

    CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: was
    portal.gateway - that route now only redirects here (see gateway(),
    below), so pointing new logins at it directly skips a pointless
    extra hop. portal.index is now the one consolidated post-sign-in
    destination: it establishes/derives the user's operating environment
    and shows that environment's projects itself.

    Only follows same-site relative paths -- ?next=https://evil.example
    would otherwise redirect an authenticated session off-site."""
    next_url = request.args.get('next') or url_for('portal.index')
    if not next_url.startswith('/') or next_url.startswith('//'):
        next_url = url_for('portal.index')
    return next_url


@portal_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    # CLAUDE-P40-D1: an already-authenticated session must never be
    # shown the sign-in form at all - it previously rendered login.html
    # with the real authenticated app shell (nav, real project names)
    # wrapped around it, since nothing here checked session state
    # before rendering. Checked before either branch below, so it also
    # covers a stray POST from an already-authenticated session.
    if is_authenticated():
        return redirect(_resolve_next_url())

    if request.method == 'GET':
        return render_template('login.html', error=None)

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    user = check_credentials(username, password)
    if user is not None:
        log_in(user)
        return redirect(_resolve_next_url())

    # Deliberately generic -- doesn't distinguish "no such user" from
    # "wrong password" (there's only one shared username anyway).
    return render_template('login.html', error='Invalid username or password.'), 401


@portal_bp.route('/logout')
def logout():
    log_out()
    # CLAUDE-P40-D1: was portal.index (the marketing/zero-state page) -
    # sign-out shall return to the isolated sign-in page itself, not a
    # page that merely also happens to be safe for an anonymous visitor.
    return redirect(url_for('portal.login'))


@portal_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def forgot_password():
    """
    CLAUDE-P28: the self-service recovery path referenced by login.html's
    "Forgot password?" link.

    The confirmation MESSAGE text is decided purely from whether SMTP is
    configured at all (current_app.config['SMTP_HOST'], a fact identical
    for every single request) - never from whether this particular email
    matched an account, and never from whether this particular delivery
    attempt actually succeeded. Conditioning the message on per-request
    outcome would reintroduce an enumeration oracle: a real account's
    delivery genuinely failing (SMTP down) would then read differently
    than "no such account" (no delivery ever attempted), letting an
    attacker distinguish the two by probing during any SMTP outage. Real
    per-request delivery success/failure is reported in the server log
    only (services/password_reset.py) - see CLAUDE-P29 for this
    reasoning in full.

    dev_reset_link is the one deliberate exception: on a real match, in
    dev/testing only, with SMTP not having delivered it, the raw link is
    rendered directly on THIS page (clearly labelled, never in
    production) instead of only being logged - convenience, not a
    change to the message contract above. Renders directly rather than
    redirecting (unlike this file's other POST handlers) specifically
    so dev_reset_link can reach the response without being stashed
    anywhere persistent (a session/cookie) in between.
    """
    if request.method == 'GET':
        return render_template('forgot_password.html')

    dev_reset_link = request_password_reset(request.form.get('email', ''), base_url=request.host_url)

    if current_app.config.get('SMTP_HOST'):
        message = "If an account with that email exists, a password reset email has been sent."
    else:
        message = (
            "If an account with that email exists, a password reset has been initiated. "
            "Email delivery isn't configured in this environment."
        )
    flash(message, 'success')

    # Checked again here (request_password_reset already gates this) so a
    # future change to that function can't silently start leaking a real
    # reset link into a production response just by returning one.
    if dev_reset_link and is_dev_fallback_active():
        return render_template('forgot_password.html', dev_reset_link=dev_reset_link)
    return render_template('forgot_password.html')


@portal_bp.route('/reset-password', methods=['GET', 'POST'])
@limiter.limit("10 per hour", methods=["POST"])
def reset_password():
    """
    The link a reset email (or the dev-only log fallback) points at.
    Deliberately one generic "invalid or expired" outcome for every
    invalid case (missing/unknown/already-used/expired token) - never
    distinguishing which, for the same account-existence/state reason
    request_password_reset never distinguishes "no such account" from
    "wrong password" elsewhere in this file.
    """
    token = request.args.get('token') if request.method == 'GET' else request.form.get('token')
    token_row = get_valid_reset_token(token or '')

    if token_row is None:
        flash("This reset link is invalid or has expired. Request a new one below.", 'error')
        return redirect(url_for('portal.forgot_password'))

    if request.method == 'GET':
        return render_template('reset_password.html', token=token)

    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')
    if len(new_password) < 8:
        flash("Choose a password at least 8 characters long.", 'error')
        return render_template('reset_password.html', token=token), 400
    if new_password != confirm_password:
        flash("Those passwords didn't match.", 'error')
        return render_template('reset_password.html', token=token), 400

    complete_password_reset(token_row, new_password)
    flash("Your password has been updated. Sign in with your new password.", 'success')
    return redirect(url_for('portal.login'))


@portal_bp.route('/verification-access/<token>')
@limiter.limit("10 per hour")
def verification_access_login(token):
    """
    CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01: the one-time link
    tools/manage_verification_access.py's `create` command prints.
    Deliberately public/unauthenticated-reachable -- establishing a
    session FROM one is the entire point, the same shape reset_password
    above already uses safely for an equally sensitive action (this
    codebase already trusts "safe because the token is unguessable,
    single-use, and short-lived", not "safe because a login gate sits in
    front of it"). One generic "invalid or expired" outcome for every
    invalid case, matching reset_password's own refusal to distinguish
    missing/unknown/used/expired.
    """
    token_row = get_valid_verification_token(token)
    if token_row is None:
        flash("This verification link is invalid or has expired.", 'error')
        return redirect(url_for('portal.login'))

    user = consume_verification_token(token_row)
    log_in(user)
    flash(
        "Signed in as a temporary live-verification identity - no real project authority. "
        "End this session (Sign out, or the self-revoke action) when verification is done.",
        'success',
    )
    return redirect(_resolve_next_url())


@portal_bp.route('/verification-access/end', methods=['POST'])
@admin_required
def verification_access_end():
    """
    Self-revoke: lets the verification identity's OWN session end and
    delete itself in one step, without requiring a maintainer to run the
    CLI's `revoke` command for the common case. Scoped narrowly -- only
    ever acts when the CURRENT session actually IS the verification
    identity (is_verification_session()), never a general "delete any
    account" capability a real admin could point at someone else's
    account. A real admin hitting this route by mistake gets a plain
    403, not a silent no-op that could look like it worked.
    """
    if not is_verification_session():
        abort(403)
    revoke_verification_access()
    log_out()
    flash("Verification access ended and removed.", 'success')
    return redirect(url_for('portal.login'))


def _accessible_operating_environments(registry, store: CaseWorkspaceStore) -> list[str]:
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: the set of
    operating_environment values genuinely present among the CURRENT
    user's own access-scoped projects - reuses _accessible_documents/
    _safe_workspace verbatim (no new authorization surface, no new
    User field), a pure read-time derivation, never persisted (the
    same "never inferred, never stored redundantly" discipline
    environment_capabilities.py's own module docstring already
    establishes for the field itself). A project with no workspace
    record or an unset/legacy environment contributes nothing here -
    this only ever reports real, already-established values, never a
    guess.

    Governance note - READ THE TWO IDENTIFIERS CAREFULLY, they differ by
    one prefix and are NOT the same record:

      - GO-NEUTRAL-ENTRY-01 is the governance PROGRAMME record
        (governance/prompt-depository/), which holds the accepted
        PRINCIPLE. It is APPROVED, its own header says "Superseded by:
        None", and nothing below supersedes it. That principle is
        intact here: this function grants no authority, persists
        nothing, and never partitions the product by category.
      - CLAUDE-GO-NEUTRAL-ENTRY-01 is the IMPLEMENTATION stage that
        first delivered it.

    What was superseded is a narrow sub-decision of the IMPLEMENTATION
    stage, not the principle. Entry-time environment derivation was
    previously ruled out by CLAUDE-GO-NEUTRAL-ENTRY-01 ("the user
    enters ARCHIOSK, not a stakeholder category" - Gateway's own
    project list stopped being partitioned by environment because of
    that decision). The Product Owner's own
    CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01 disposition
    (Disposition B, recorded in commit cea176b: "this narrowly
    supersedes the entry-specific portion of CLAUDE-GO-NEUTRAL-ENTRY-01
    only ... That decision's broader principle is preserved; only entry
    sequencing changes") explicitly and NARROWLY supersedes THAT
    sub-decision, for this one purpose - establishing/deriving the
    user's governed operating side before showing their project list at
    authenticated entry. The programme record's own Lineage field
    already names that later work as "surface evolution", so the two
    records agree; only their subjects differ.

    This paragraph is this explicit because its earlier, shorter form
    was read as claiming the PRINCIPLE had been superseded, which it
    never said and which would not be true.

    It is not a return to arbitrary Client/DB categorization
    throughout the product: choose_project's own unfiltered default
    stays unfiltered, and this function itself never partitions
    anything - it only reports which side(s) a user is already
    authorized for, so the caller can decide whether to ask.
    """
    documents = _accessible_documents(registry, store)
    environments: set[str] = set()
    for document in documents:
        workspace = _safe_workspace(store, document.project_id)
        if workspace and workspace.operating_environment:
            environments.add(workspace.operating_environment)
    return sorted(environments)


def _environment_projects(registry, store: CaseWorkspaceStore, environment_filter: str = '') -> list[dict]:
    """The same access-scoped project summary shape `choose_project`
    builds (Section 12/CLAUDE-CA1D-PROJECT-GATEWAY-LABELS-01), reused
    here via the same `_accessible_documents`/`_safe_workspace`
    primitives - no new authorization surface.

    CLAUDE-GO-NEUTRAL-ENTRY-01: `environment_filter` defaults to ''
    (unfiltered - every accessible project, regardless of operating
    environment) - the same convention `choose_project`'s own optional
    `?environment=` deep link already established, adopted here as the
    default rather than a special case. `gateway()` used to call this
    twice (once per environment) to build two separate front-door
    lists; the Product Owner's own "the user enters ARCHIOSK, not a
    stakeholder category" direction replaced that with ONE unfiltered
    call - operating_environment is still a real, still-required,
    still-locked-at-creation project fact (unchanged - see
    CaseWorkspaceStore.set_operating_environment/
    correct_operating_environment), it now simply never partitions the
    Gateway's own project list. The optional filter argument is kept
    (not removed) since `choose_project`'s own `?environment=` deep
    link still legitimately uses the equivalent narrowing inline."""
    documents = _accessible_documents(registry, store)
    projects = []
    for document in documents:
        workspace = _safe_workspace(store, document.project_id)
        if environment_filter and (not workspace or workspace.operating_environment != environment_filter):
            continue
        projects.append({
            "project_id": document.project_id,
            "display_name": (workspace.display_title if workspace else None) or document.filename,
            "last_activity": document.ingested_at,
        })
    projects.sort(key=lambda p: p["display_name"].lower())
    return projects


@portal_bp.route('/about')
@login_required
def about():
    """CLAUDE-APP-MENU-01: the Archiosk application menu's own "About" item
    - honest, static facts already shown elsewhere (gateway.html's own
    footer: "Flat-JSON registry" / "Static build v{{ static_version }}"),
    never fabricated version/build metadata this app doesn't actually
    track (no packaged release number, no git commit exposed to the
    running process)."""
    return render_template('about.html')


@portal_bp.route('/gateway')
@login_required
def gateway():
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: this route
    used to render the separate authenticated Gateway shell
    (gateway.html/gateway_base.html/gateway_shell.html) as its own
    post-sign-in landing page. The Product Owner's own disposition
    consolidated that landing state onto portal.index, which now does
    everything this route used to (establish/derive operating
    environment, show that environment's projects, orient a no-project
    user) without a separate shell. This route is kept - not deleted -
    as a redirect only: any bookmark, saved link, or external reference
    to /gateway keeps working rather than 404ing, matching this
    project's own "canonical home first, verify, then retire redundant
    location" sequencing discipline. gateway_base.html/gateway_shell.html
    themselves are UNCHANGED and still legitimately used elsewhere (the
    Vestibule's project_chooser.html still extends them) - only this
    route's own rendering responsibility moved.
    """
    return redirect(url_for('portal.index'))


_GATEWAY_NEW_PROJECT_PATTERN = re.compile(r"new project|create a project|start a project", re.IGNORECASE)


def _classify_gateway_orientation(message: str, projects: list[dict], can_create_project: bool) -> dict:
    """CLAUDE-VOICE-CONSISTENCY-01: a small, deterministic, rule-based
    orientation responder for the Project Gateway's own composer -
    Level 2/3 of the future Voice authority ladder only (governance/
    specified-unbuilt/voice-conversational-presence.md, Section 6:
    Suggest / Reversible local action - "navigate, open, scroll, select
    ... no durable mutation"). Deliberately NOT services/
    conversation_interpreter.py's interpret_message: that function
    requires an already-open project's own CaseWorkspaceStore and
    speaks with real project evidence/authority. Nothing here ever
    opens one or claims project truth - constitutional-invariants.md
    #8 ("project boundaries are strict") holds by construction, not by
    convention. `projects` is the same access-scoped list `gateway()`
    itself renders (`_environment_projects`) - matching against it,
    never a second listing/authorization mechanism.

    Returns {"kind": "navigate"|"info", "url": ..., "text": ...}.
    """
    lowered = message.strip().lower()
    if not lowered:
        return {"kind": "info", "text": "Say a project name to open it, or “new project” to start one."}

    for project in projects:
        name = project["display_name"].lower()
        if name and (name in lowered or lowered in name):
            return {
                "kind": "navigate",
                "url": url_for('workspace.show_workspace', project_id=project["project_id"]),
                "text": f"Opening {project['display_name']}…",
            }

    if can_create_project and _GATEWAY_NEW_PROJECT_PATTERN.search(lowered):
        return {"kind": "navigate", "url": url_for('portal.upload'), "text": "Opening New Project…"}

    # CLAUDE-GO-GATEWAY-COGNITION-01: what used to be here was a single canned
    # sentence offering to open a project, returned for every message that was
    # not navigation - so a real question got a non-sequitur, which reads as
    # not having listened. The navigation rules above keep first refusal;
    # only this fallback changed.

    # 1. Deterministic and instant: a capability question needs no project and
    #    no model, and already answers with numbered steps.
    capability = find_capability_by_phrase(lowered)
    if capability is not None and _looks_like_capability_question(lowered):
        return {"kind": "info", "text": _handle_capability_question(capability).reply_text}

    # 2. The Gateway's OWN seam (CLAUDE-GO-GATEWAY-COGNITION-02). The first
    #    version of this used answer_application_question, which is a DEVELOPER
    #    MODE function - its system prompt casts the model as a Developer Mode
    #    assistant and its user prompt carries repository internals. That was
    #    wrong on a surface any signed-in user reaches, and the "outside
    #    ARCHIOSK's application scope" preface was its visible symptom.
    #    answer_orientation_question takes no workspace, no store and no
    #    repository facts, so it can reach neither project state nor internals.
    if len(lowered.split()) >= 3:
        try:
            answer = answer_orientation_question(
                question=message.strip(),
                api_key=current_app.config.get("ANTHROPIC_API_KEY"),
                model=current_app.config.get("ANTHROPIC_MODEL"),
            )
        except Exception:  # noqa: BLE001 - a stub surface must never 500
            answer = None
        if answer is not None and answer.ran and answer.answer:
            return {"kind": "info", "text": answer.answer}

    # 3. Honest about scope, rather than redirecting. Saying what this surface
    #    can do is fine; implying it answered is not.
    return {
        "kind": "info",
        "text": (
            "That is not something I can help with - I work on construction and "
            "design project material, and from here I can open one of your projects "
            "or start a new one. Open a project and I can work with its documents."
        ),
    }


# CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum H: keyword ->
# canned-answer pairs for the five questions the Product Owner's own
# prompt names verbatim. Same authority-ladder scope as
# _classify_gateway_orientation above (Level 2/3 only - explain, never
# choose a consequential setting on the user's behalf) and the same
# deterministic, no-AI-call shape - this is genuinely a different
# domain (form-field meaning, not project navigation), so it's its own
# small classifier rather than overloading the navigation one with
# unrelated matching logic.
_ESTABLISH_PROJECT_HELP_ANSWERS = (
    (
        ("environment", "owner", "proponent", "design-builder", "design builder", "side", "which one"),
        "Client / Owner is for preparing and issuing the RFP; Design-Builder / Proponent is for reviewing and "
        "responding to one already issued. Choose the side that describes your role in this specific project.",
    ),
    (
        ("connect", "link", "storage"),
        "You can connect or upload documents now, or add them later from File > Add Document once the project "
        "exists. Link to Storage is shown but not yet available; Upload to Storage copies documents in now.",
    ),
    (
        ("change", "wrong", "mistake"),
        "No - the operating environment is locked permanently once the project is created. If you choose the "
        "wrong one, you'll need to create a new project in the correct environment.",
    ),
    (
        ("name", "call it", "title", "rename"),
        "Project name is optional - it defaults to the file or folder name if you leave it blank. It must be "
        "unique, and you can change it later from the project's own settings.",
    ),
)


def _classify_establish_project_help(message: str) -> dict:
    """CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Addendum H: a
    small, rule-based responder for the New Project / Establish a
    Project form's own project-less Composer widget - explains field
    meaning/consequences, never silently chooses a consequential
    setting (operating environment, storage connection) on the user's
    behalf. Every answer here is grounded in this form's own real,
    current copy/behavior (templates/upload.html) - never a claim the
    form itself doesn't already make.
    """
    lowered = message.strip().lower()
    if not lowered:
        return {"kind": "info", "text": "Ask about the operating environment, connecting documents, or naming your project."}

    for keywords, answer in _ESTABLISH_PROJECT_HELP_ANSWERS:
        if any(keyword in lowered for keyword in keywords):
            return {"kind": "info", "text": answer}

    return {
        "kind": "info",
        "text": "I can explain the operating environment choice, whether it can change later, connecting "
                "documents, or naming your project - ask about any of those.",
    }


def _project_less_external_ai_allowed() -> bool:
    """CLAUDE-ESTABLISH-HELPDESK-01: the external-AI gate, resolved for a
    surface that has no project.

    routes/workspace.py's _evaluate_security_action resolves this against the
    organization baseline AND the project's own security_profile. There is no
    project here, so there is no profile to look up - and the honest resolution
    is the baseline alone with profile_decision=None, which the most-restrictive
    -wins resolver can only treat as equal to or STRICTER than a project-scoped
    call. A missing project profile must never read as permission.

    GOV-D-001 records that this path reaches the model, and that the gate must
    cover it explicitly rather than by inheritance. This function is that
    explicit coverage.
    """
    from services.security_governance import SecurityGovernanceStore
    from services.security_policy import (
        ACTION_EXTERNAL_AI_REQUEST, DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE,
        evaluate_action,
    )

    try:
        security_store = SecurityGovernanceStore(current_app.config["REGISTRY_STORE_PATH"])
        security_record = security_store.get()
        active_baseline = security_store.active_baseline(security_record)
        decision = evaluate_action(
            ACTION_EXTERNAL_AI_REQUEST,
            baseline_decision=(
                active_baseline["control_decisions"].get(
                    ACTION_EXTERNAL_AI_REQUEST, {}).get("decision")
                if active_baseline else None
            ),
            baseline_version_id=active_baseline["id"] if active_baseline else None,
            # No project, so no security_profile and no project-scoped
            # exception to look up. Both omitted rather than guessed - the
            # most-restrictive-wins resolver then treats this as equal to or
            # stricter than a project-scoped call, never looser.
            profile_decision=None,
        )
    except Exception:
        # Fail closed. An unreadable security record is not permission.
        return False
    return decision.decision in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE)


def _establish_project_reply(message: str) -> dict:
    """CLAUDE-ESTABLISH-HELPDESK-01: the registry help desk (GOV-D-001).

    Was _classify_establish_project_help alone - a keyword lookup table that
    answered a fixed FAQ and returned the same deflection for everything else,
    including every real question anyone actually asks. The Product Owner's own
    two questions both landed on that deflection, which is what "a false
    Composer" meant.

    The table is NOT deleted. It is the fallback whenever the model cannot or
    may not run - unconfigured key, external-AI denied by policy, an API
    failure. A surface that degrades to a real FAQ answer is better than one
    that degrades to an error, and this keeps the pre-existing behaviour
    reachable rather than replacing it with a dependency.

    Commits nothing either way: no project, no Source, no governance-log entry,
    no persisted conversation, no persisted document.
    """
    from services.establish_help_desk import advise, extract_candidate_text

    document_text = ""
    document_name = ""
    candidate = request.files.get("candidate_document")
    if candidate is not None and candidate.filename:
        # Read in memory only. Never saved, never handed to ingestion, never
        # given provenance - it is not evidence, it is something being shown to
        # GO across a desk before anything is filed.
        document_name = candidate.filename
        max_bytes = current_app.config.get("MAX_UPLOAD_MB", 25) * 1024 * 1024
        raw = candidate.read(max_bytes + 1)
        if len(raw) <= max_bytes:
            document_text = extract_candidate_text(raw, document_name)
        del raw

    if not _project_less_external_ai_allowed():
        return _classify_establish_project_help(message)

    result = advise(message, document_text=document_text, document_name=document_name)
    if not result.ran:
        return _classify_establish_project_help(message)
    return {"kind": "info", "text": result.text, "read_document": result.read_document}


@portal_bp.route('/gateway/orientation', methods=['POST'])
@login_required
# GOV-D-001 recorded, as an accepted cost, that a project-less surface reaching
# the model widens cost and attack surface and "must be covered by rate limiting
# and the external-AI policy gate explicitly, not by inheritance". This is the
# rate-limiting half; _project_less_external_ai_allowed is the other half.
@limiter.limit("30 per hour", methods=["POST"])
def gateway_orientation():
    """CLAUDE-VOICE-CONSISTENCY-01: backend for the project-less
    Composer/orientation surface - see _classify_gateway_orientation's
    own comment for the authority-ladder/scope reasoning. Authenticated
    but deliberately requires no project_id - the one project-less
    conversational surface, and it stays that way by never touching
    CaseWorkspaceStore's conversational path.

    CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01, Option C: the URL
    itself is unchanged (still /gateway/orientation - the endpoint is
    an internal action, not user-facing navigation, so renaming it
    would be pure churn), but its caller is now index.html's
    no-project/orientation state rather than the retired gateway.html.
    Optional ?environment= scopes project matching to one operating
    environment. CLAUDE-ENTRY-SIMPLIFY-01: index.html NO LONGER SENDS IT -
    the entry gate that resolved a side was retired, so there is no
    resolved side to pass. This endpoint is unchanged and still honours
    the parameter if some future caller supplies it; with it omitted, GO
    matches across every project the user can already reach, which is
    this endpoint's own documented fallback and is what neutral entry
    means here.

    That is NOT a weakening of project isolation: matching has always been
    against the caller's own access-scoped project list, never a second
    listing mechanism, so a user can only ever be navigated to a project
    they were already authorized to open. What the parameter narrowed was
    presentation, not authority.

    Addendum H: optional ?context=establish-project routes to a SECOND,
    genuinely different classifier (_classify_establish_project_help) -
    upload.html's own composer widget sets this, since "explain this
    form's own fields" is a different domain than "navigate to a
    project", not a variant worth cramming into the same matching
    logic. Any other/omitted context value keeps the original
    navigation behavior, unchanged.
    """
    message = (request.form.get('message') or '')[:500]
    context = request.form.get('context', '')
    if context == 'establish-project':
        return jsonify(_establish_project_reply(message))

    environment = request.form.get('environment', '')
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    environment_filter = environment if is_valid_operating_environment(environment) else ''
    projects = _environment_projects(registry, store, environment_filter=environment_filter)
    reply = _classify_gateway_orientation(message, projects, can_create_project=is_admin())
    return jsonify(reply)


@portal_bp.route('/explore')
def explore():
    """
    CLAUDE-CA1D-PUBLIC-LANDING-01: public, unauthenticated - a stranger
    reads this specifically to decide whether to sign up or sign in, so
    it can never require either first. Deliberately not gated on
    is_authenticated() at all (unlike index() above, which branches on
    it) - there is nothing here an authenticated user shouldn't also be
    able to read.
    """
    return render_template('explore.html')


@portal_bp.route('/start-trial', methods=['GET', 'POST'])
@limiter.limit("5 per hour", methods=["POST"])
def start_trial():
    """
    CLAUDE-CA1D-PUBLIC-LANDING-01: public, unauthenticated.

    CLAUDE-CA1D-TRIAL-ACCESS-HOTFIX-01: the former version of this page
    was a dead end -- honest about not being self-serve, but offering no
    actionable path for an interested visitor. Still deliberately honest
    (never claims self-service signup or an already-created account
    exists), but now accepts a real, minimal request (email required;
    name/message optional) and hands it to services/trial_request.py,
    which reuses the existing best-effort SMTP transport -- no new
    persistent PII store, no new external service, no new account
    creation. Same rate limit as /forgot-password (5 per hour), the
    established precedent for a public, unauthenticated, spam-prone
    form on this route file.
    """
    if request.method == 'GET':
        return render_template('start_trial.html')

    name = request.form.get('name', '')
    email = request.form.get('email', '').strip()
    message = request.form.get('message', '')

    # Deliberately minimal validation -- enough to have a real way to
    # contact the visitor back, nothing more. No email-format library,
    # just the same "must actually look like an email" bar this app
    # already accepts elsewhere for a plain HTML5 email input.
    if not email or '@' not in email or email.startswith('@') or email.endswith('@'):
        return render_template(
            'start_trial.html', error="Enter a valid email address.", name=name, email=email, message=message,
        ), 400

    submit_trial_request(name=name, email=email, message=message)
    return render_template('start_trial.html', submitted=True)


_PROJECT_SORT_KEYS = {
    "last_updated": lambda p: p["last_activity"],
    "name": lambda p: p["display_name"].lower(),
    "created": lambda p: p["created_at"],
}


@portal_bp.route('/projects')
@login_required
def projects_list():
    """The project directory: every previously ingested project, so a
    returning user can find and reopen one without already knowing its
    project_id or having bookmarked its dashboard URL. Before this route
    existed, the only way back into a project was the redirect landed on
    right after uploading it -- there was no way to "reopen tomorrow"
    through the UI at all.

    Search and sort are both server-side over fields the application
    already has (filename/project_id, and the same last-updated/created
    timestamps _project_summary already computes for the home page) - no
    new metadata or search index was introduced.
    """
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    query = request.args.get('q', '').strip()
    sort = request.args.get('sort', 'last_updated')
    if sort not in _PROJECT_SORT_KEYS:
        sort = 'last_updated'

    documents = _accessible_documents(registry, store)
    workspaces_by_project = {
        document.project_id: _safe_workspace(store, document.project_id)
        for document in documents
    }

    # CLAUDE-ENTRY-SIMPLIFY-01: operating-environment filtering lives HERE now,
    # not at entry. Same derivation as before (only environments genuinely
    # present among this user's own accessible projects, never a guess), and
    # the same "resolve only against what you can already reach" rule - an
    # unauthorized or stale value falls back to showing everything rather than
    # silently narrowing or bypassing anything.
    #
    # The difference is what it MEANS to the person using it. Beside search and
    # sort, on a directory the user chose to open, this is plainly a filter. In
    # front of the door it read as a governed choice of side. The mechanism did
    # not change; the claim it makes did.
    accessible_environments = sorted({
        workspace.operating_environment
        for workspace in workspaces_by_project.values()
        if workspace and workspace.operating_environment
    })
    environment = request.args.get('environment', '').strip()
    if environment not in accessible_environments:
        environment = ''
    if environment:
        documents = [
            d for d in documents
            if workspaces_by_project[d.project_id]
            and workspaces_by_project[d.project_id].operating_environment == environment
        ]

    if query:
        needle = query.lower()
        documents = [
            d for d in documents
            if needle in d.filename.lower() or needle in d.project_id.lower()
        ]

    projects = [
        _project_summary(document, workspaces_by_project[document.project_id], governance_log.read(document.project_id))
        for document in documents
    ]
    projects.sort(key=_PROJECT_SORT_KEYS[sort], reverse=(sort != 'name'))

    return render_template(
        'projects.html', projects=projects, query=query, sort=sort,
        environment=environment,
        accessible_environments=accessible_environments,
        operating_environment_labels=OPERATING_ENVIRONMENT_LABELS,
    )


@portal_bp.route('/projects/choose')
@login_required
def choose_project():
    """CLAUDE-P40-VW8-QA, Section 12: a focused existing-Project chooser -
    Gateway's own "Open an existing project" used to lead straight to
    `projects_list` (the full management directory: search, sort,
    per-project Delete forms, inside base.html's own full authenticated
    Lists shell) instead of a simple "which Project did you mean"
    picker. Reuses the exact same authorized data (_accessible_documents/
    _project_summary, already access-scoped - no new authorization
    surface) but renders inside gateway_shell.html (via
    templates/project_chooser.html extending gateway_base.html, the
    SAME minimal shell Gateway itself uses) - no Lists panel, no sort/
    delete controls, no Removed-Projects link. Deliberately the smallest
    coherent addition: one route, one template, reusing existing data -
    `projects_list`/`projects.html` are UNCHANGED and remain the real
    "administrative management" destination (Section 12's own "may
    remain available through its proper separate route"), still
    reachable directly by URL.

    CLAUDE-P40-VW7B: this same route/template is now also the Project
    Vestibule (Section 4) - the least-disruptive repository-compatible
    choice, since it already renders exactly what a Vestibule needs
    (authorized-only, one row per Project, no Lists/Toolbox/Display/
    Chat) and nothing else in this codebase comes closer. The one
    addition is an OPTIONAL `?current=<project_id>` - set only by the
    header's own "Switch Project" link (templates/base.html's
    workspace-topbar-context) when a Foreground Project is actually
    open, never a new piece of persisted state (this app has no
    server-tracked "current project" concept - see that template's own
    comment on why "Foreground Project" is deliberately just whichever
    project_id the current URL names, nothing more). Resolved through
    the SAME already-access-filtered `documents` list below, never a
    second, separately-trusted lookup - an unauthorized, stale, or
    unrelated `current` value simply fails to match anything and the
    Vestibule falls back to its plain "no current Project" rendering,
    exactly as if the parameter had been omitted (never a 404 - this is
    a soft display hint, not an authorization boundary of its own).
    """
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])

    query = request.args.get('q', '').strip()
    # CLAUDE-CA1D-PROJECT-GATEWAY-LABELS-01: an OPTIONAL ?environment=
    # deep link from the Gateway's own two context groups (gateway.html)
    # -- filters the SAME already-access-scoped `documents` list below
    # by each Project's own locked ProjectWorkspace.operating_environment,
    # never a second, separately-authorized lookup. Silently ignored
    # (falls back to the plain, unfiltered chooser) when absent or not
    # one of the two real environment values -- a soft display filter,
    # never an authorization boundary of its own, same treatment this
    # route's own `current` param already gets.
    environment_filter = request.args.get('environment', '').strip()
    if not is_valid_operating_environment(environment_filter):
        environment_filter = ''
    documents = _accessible_documents(registry, store)
    removed_match = False
    if query:
        needle = query.lower()
        documents = [
            d for d in documents
            if needle in d.filename.lower() or needle in d.project_id.lower()
        ]
        if not documents:
            # CLAUDE-CA1D-RECEPTION-FIX-01: a live walkthrough found a
            # user searching a removed Project's name here got a bare
            # "no match" with no hint it exists under Removed Projects
            # (the permanent link below is easy to miss when scanning
            # for a search result specifically). Reuses the same
            # already-P32-filtered _accessible_documents call this
            # route already trusts elsewhere -- never a second,
            # separately-authorized lookup, so this can't surface a
            # removed Project the current user couldn't already open.
            removed_documents = _accessible_documents(registry, store, include_removed=True)
            removed_match = any(
                needle in d.filename.lower() or needle in d.project_id.lower()
                for d in removed_documents
            )

    projects = []
    for document in documents:
        workspace = _safe_workspace(store, document.project_id)
        if environment_filter and (not workspace or workspace.operating_environment != environment_filter):
            continue
        projects.append({
            "project_id": document.project_id,
            "display_name": (workspace.display_title if workspace else None) or document.filename,
            "last_activity": document.ingested_at,
        })
    projects.sort(key=lambda p: p["display_name"].lower())

    current_project_id = request.args.get('current', '').strip()
    current_project = next((p for p in projects if p["project_id"] == current_project_id), None) if current_project_id else None
    if current_project is not None:
        projects = [p for p in projects if p["project_id"] != current_project_id]

    return render_template(
        'project_chooser.html', projects=projects, query=query, current_project=current_project,
        removed_match=removed_match, environment_filter=environment_filter,
        environment_label=OPERATING_ENVIRONMENT_LABELS.get(environment_filter),
    )


@portal_bp.route('/removed-projects')
@login_required
def removed_projects():
    """CLAUDE-P40-E2, Section B: "Removed Projects" - where an
    authorized user restores a whole Project removed via
    workspace.remove_project_route. A removed Project's own workspace
    page stays directly reachable to an authorized user (removal never
    changes P32 access, only listing visibility - see
    _accessible_documents), but nothing in the ordinary nav links to it
    any more once removed; this page is the deliberate, explicit way
    back to it."""
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    documents = _accessible_documents(registry, store, include_removed=True)

    # CLAUDE-REMOVED-API-01: narrowed to the actors who can actually act
    # on a tombstone. Restore has ALWAYS been owner-or-admin, enforced in
    # the store layer (CaseWorkspaceStore.restore_project raises for
    # anyone else), but this page listed every removed project to every
    # former member -- so a non-owner who could not restore still saw the
    # project's name, its removal timestamp and who removed it. That is
    # precisely the retained metadata removal is meant to stop
    # disclosing. The predicate below is the store's own existing
    # authority rule, reused rather than reinvented: no new role model,
    # and no change to who may restore.
    username = session.get("username")
    admin = is_admin()

    def _may_recover(document):
        workspace = _safe_workspace(store, document.project_id)
        return admin or (workspace is not None and workspace.owner == username)

    documents = [document for document in documents if _may_recover(document)]
    removed = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents
    ]
    for row, document in zip(removed, documents):
        workspace = _safe_workspace(store, document.project_id)
        row["removed_at"] = workspace.removed_at if workspace else None
        row["removed_by"] = workspace.removed_by if workspace else None

    return render_template('removed_projects.html', removed=removed)


def _delete_project_files(app, project_id: str) -> None:
    """
    Permanently removes every stored artifact for a project - the legacy
    RequirementsRegistry record, its GovernanceLog, its CaseWorkspaceStore
    workspace, and any project-scoped uploaded files. Deliberately NOT a
    governed operation: no Supersession, no Snapshot, nothing preserved -
    this exists for removing unwanted/duplicate/test project entries
    (Project Entry Rule), never for real project history, which is why it
    carries its own honest confirmation wording rather than reusing the
    Approval Gate's "this changes governed project state" framing (this
    is the opposite of a governed state change - it's erasure).
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    for suffix in (".json", ".governance.jsonl", ".workspace.json"):
        (store_path / f"{project_id}{suffix}").unlink(missing_ok=True)

    sources_dir = store_path / "workspace_sources" / project_id
    if sources_dir.exists():
        shutil.rmtree(sources_dir)


@portal_bp.route('/projects/<project_id>/delete', methods=['POST'])
@admin_required
def delete_project(project_id):
    """
    Same confirm-gate idiom already used for consequential actions
    elsewhere in this app (submit once with no `confirm` value -> shown
    the gate; submit again with confirm=yes/no -> acted on) - not a new
    pattern, just this route's own honestly-worded version of it, since
    deletion is not a governed action the existing Approval Gate wording
    could accurately describe.
    """
    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)
    # CLAUDE-P32: this route is already @admin_required, so an admin
    # session always passes this gate -- kept here anyway for defense in
    # depth and consistency with every other project-scoped route, not
    # because a non-admin could otherwise reach this route at all.
    _require_project_access_or_404(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), project_id)

    confirm = request.form.get('confirm')
    if confirm == 'no':
        flash('Deletion cancelled - no change was made.', 'success')
        return redirect(url_for('portal.projects_list'))
    if confirm != 'yes':
        return render_template(
            'confirm_delete_project.html', project_id=project_id, filename=document.filename,
        )

    _delete_project_files(current_app, project_id)
    flash(f'Project "{document.filename}" permanently deleted.', 'success')
    return redirect(url_for('portal.projects_list'))


# -- CLAUDE-P40-E2/E2A, Section D/B: Reset Project Data (administrator-only
# clean test reset) and reset-snapshot restoration ------------------------
#
# Every snapshot this module creates (a Reset's own pre-wipe copy, or a
# Restore's own pre-restore safety copy) carries a manifest -
# SNAPSHOT_MANIFEST_FILENAME, written inside the snapshot directory
# itself - recording who/when/what-kind and a sha256 checksum of every
# file, so a later restore can PROVE the snapshot it's about to use is
# exactly what was captured, not silently corrupted or partially copied.

RESET_CONFIRMATION_PHRASE = "RESET PROJECT DATA"
RESTORE_CONFIRMATION_PHRASE = "RESTORE SNAPSHOT"

# Deliberately NOT ".json" - RequirementsRegistry.list_ids() globs "*.json"
# directly against whatever store_path it's given (see that module's own
# comment on why ".workspace.json" needs its own exclusion), and this
# manifest lives inside snapshot directories that get inventoried the
# exact same way a live store does (_inventory_from_store_path below). A
# ".json" name here would be misread as a bogus extra "project".
SNAPSHOT_MANIFEST_FILENAME = "_snapshot_manifest.snapshot"


def _win_long_path(path: Path) -> str:
    """
    CLAUDE-P40-E2A1: a real, live isolated-process run of Reset Project
    Data raised `shutil.Error([WinError 3] The system cannot find the
    path specified)` from `shutil.copytree` the moment a snapshot's own
    directory (registry_snapshots/<stamp>/) added one more level of
    nesting on top of an already-deep `workspace_sources/<project_id>/
    <hash>_<filename>` path - not an artifact of that verification
    environment (its shorter, un-nested source path copied fine at
    ingestion time), a genuine Windows MAX_PATH (260 character) limit
    that any sufficiently long REGISTRY_STORE_PATH/filename combination
    can hit in the real deployment too, snapshot-nesting or not.

    The Windows-sanctioned fix without any OS-level configuration
    change (a `LongPathsEnabled` registry/group-policy opt-in cannot be
    assumed present on a given deployment host) is the `\\\\?\\`
    extended-length prefix, which raises the effective limit to ~32,767
    characters for that one call. Applied at the exact point every
    shutil/os call in this snapshot/reset/restore code path touches the
    filesystem - never earlier, since `\\\\?\\`-prefixed strings skip
    normal path normalization (they must already be absolute, backslash-
    separated, with no `..` segments) and would break ordinary Path
    methods (`.relative_to`, `.name`, glob) used everywhere else in this
    module. A no-op (returns the plain resolved path) on any other OS.
    """
    resolved = str(path.resolve())
    if os.name != "nt" or resolved.startswith("\\\\?\\"):
        return resolved
    return "\\\\?\\" + resolved


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_win_long_path(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_from_store_path(store_path: Path) -> dict:
    """Exact counts of everything under an arbitrary registry store
    directory - every Project (active or removed), and the Documents/
    Investigations/Findings/Requirements inside them. Works identically
    against the live store (Reset's own preview) or a snapshot's copy
    (the snapshot-listing/restore-preview pages), since both are just
    RequirementsRegistry/CaseWorkspaceStore-shaped directories."""
    registry = RequirementsRegistry(str(store_path))
    store = CaseWorkspaceStore(str(store_path))
    inventory = {"projects": 0, "documents": 0, "investigations": 0, "findings": 0, "requirements": 0}
    for project_id in registry.list_ids():
        document = registry.get(project_id)
        if document is None:
            continue
        inventory["projects"] += 1
        workspace = _safe_workspace(store, project_id)
        if workspace is None:
            continue
        inventory["documents"] += len(workspace.sources)
        inventory["investigations"] += len(workspace.cases)
        inventory["findings"] += len(workspace.findings)
        inventory["requirements"] += len(workspace.requirements)
    return inventory


def _project_data_inventory(app) -> dict:
    return _inventory_from_store_path(Path(app.config["REGISTRY_STORE_PATH"]))


def _walk_root(dir_path: Path) -> Path:
    """
    CLAUDE-P40-E2A2, Section D: a plain Path.rglob("*") - unlike
    shutil.copytree/os.rename, which _win_long_path already covers -
    SILENTLY OMITS files past Windows' 260-character MAX_PATH from its
    results (confirmed live, not assumed: a real registry_snapshots/
    <stamp>/workspace_sources/<project_id>/<hash>_<filename> path at
    286 characters was invisible to rglob() while still being a real,
    readable file on disk - the exact same class of bug _win_long_path
    was written for, in a walk this stage's own new checksum machinery
    added and initially missed applying it to). Returns a Path wrapping
    the \\\\?\\-prefixed string, so every path .rglob() yields from it
    is already long-path-safe and .relative_to(this) still works
    normally (pathlib's relative_to is purely lexical, unaffected by
    the prefix)."""
    return Path(_win_long_path(dir_path))


def _checksums_for_dir(dir_path: Path, exclude_names: tuple[str, ...] = ()) -> dict[str, str]:
    """sha256 of every real file under dir_path, keyed by its path
    relative to dir_path - the one shared basis both a snapshot's own
    manifest and a live-registry post-transaction verification are
    built from (CLAUDE-P40-E2A2), so "does this directory match what
    was expected" is always the same comparison regardless of which
    directory is being checked."""
    root = _walk_root(dir_path)
    return {
        str(path.relative_to(root).as_posix()): _sha256_of(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name not in exclude_names
    }


def _verify_directory_against_checksums(
    dir_path: Path, expected_checksums: dict[str, str], exclude_names: tuple[str, ...] = (),
) -> tuple[bool, list[str]]:
    """Recomputes checksums of every file CURRENTLY under dir_path and
    compares against expected_checksums - a missing file, a changed
    file, or an unexplained extra file are all reported. Used both for
    a snapshot verifying itself against its own manifest
    (_verify_snapshot_integrity) and for a transaction verifying the
    LIVE registry against the manifest it recorded before making any
    change (_run_registry_transaction / recovery)."""
    if not dir_path.exists():
        return False, ["Directory does not exist."]
    root = _walk_root(dir_path)
    current_files = {
        str(path.relative_to(root).as_posix())
        for path in root.rglob("*")
        if path.is_file() and path.name not in exclude_names
    }
    problems = []
    for rel_path, expected_hash in expected_checksums.items():
        if rel_path not in current_files:
            problems.append(f"Missing file: {rel_path}")
            continue
        if _sha256_of(dir_path / rel_path) != expected_hash:
            problems.append(f"Checksum mismatch: {rel_path}")
    for rel_path in sorted(current_files - set(expected_checksums.keys())):
        problems.append(f"Unexpected extra file (not in manifest): {rel_path}")
    return (len(problems) == 0), problems


def _create_snapshot(store_path: Path, snapshot_root: Path, actor: str, kind: str) -> Path:
    """
    Copies the whole store_path tree into a new timestamped directory
    under snapshot_root, then writes SNAPSHOT_MANIFEST_FILENAME inside
    that same directory: actor/time/kind, the inventory computed once
    at creation time, and a sha256 checksum of every real file (recorded
    BEFORE the manifest itself is written, so the manifest never has to
    describe its own checksum). `kind` distinguishes a Reset Project
    Data snapshot ("reset") from a pre-restore safety snapshot
    ("pre_restore_safety") taken automatically by a restore - both are
    ordinary, equally restorable snapshots; `kind` is a label for the
    listing page, not a behavioral difference.
    """
    snapshot_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    snapshot_dir = snapshot_root / stamp
    shutil.copytree(_win_long_path(store_path), _win_long_path(snapshot_dir))

    checksums = _checksums_for_dir(snapshot_dir)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "kind": kind,
        "inventory": _inventory_from_store_path(snapshot_dir),
        "file_count": len(checksums),
        "checksums": checksums,
    }
    with open(_win_long_path(snapshot_dir / SNAPSHOT_MANIFEST_FILENAME), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(manifest, indent=2))
    return snapshot_dir


def _verify_snapshot_integrity(snapshot_dir: Path) -> tuple[bool, list[str]]:
    """Recomputes checksums of every file CURRENTLY in snapshot_dir and
    compares against what its own manifest recorded at creation time -
    Section B: "verifies the snapshot manifest and checksums before
    restoration". A missing file, a changed file, or an unexplained
    extra file are all reported; restoration never proceeds if this
    returns any problems."""
    manifest_path = snapshot_dir / SNAPSHOT_MANIFEST_FILENAME
    if not manifest_path.exists():
        return False, ["No manifest found for this snapshot - cannot verify integrity."]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"Manifest could not be read: {exc}"]
    return _verify_directory_against_checksums(
        snapshot_dir, manifest.get("checksums", {}), exclude_names=(SNAPSHOT_MANIFEST_FILENAME,),
    )


def _list_snapshots(app) -> list[dict]:
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    if not snapshot_root.exists():
        return []
    rows = []
    for entry in snapshot_root.iterdir():
        if not entry.is_dir():
            continue
        manifest_path = entry / SNAPSHOT_MANIFEST_FILENAME
        if not manifest_path.exists():
            # Not a manifest-bearing snapshot (a directory that predates
            # this stage, or something unrelated left in the same
            # parent folder) - skip rather than guess at its shape.
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        rows.append({
            "snapshot_id": entry.name,
            "created_at": manifest.get("created_at"),
            "actor": manifest.get("actor"),
            "kind": manifest.get("kind"),
            "inventory": manifest.get("inventory", {}),
            "file_count": manifest.get("file_count"),
        })
    rows.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return rows


def _resolve_snapshot_dir(snapshot_root: Path, snapshot_id: str) -> Optional[Path]:
    """`snapshot_id` arrives as a raw URL segment - validated against
    path traversal two ways (a plain substring check, and confirming
    the resolved path actually lives inside snapshot_root) before it's
    ever used to build a filesystem path, matching this codebase's
    existing "never trust a raw id from the request" discipline
    (see e.g. show_workspace's own ?source= handling)."""
    if not snapshot_id or "/" in snapshot_id or "\\" in snapshot_id or ".." in snapshot_id:
        return None
    candidate = (snapshot_root / snapshot_id).resolve()
    try:
        candidate.relative_to(snapshot_root.resolve())
    except ValueError:
        return None
    if not candidate.is_dir() or not (candidate / SNAPSHOT_MANIFEST_FILENAME).exists():
        return None
    return candidate


def _pid_is_alive(pid: int) -> bool:
    """Cross-platform "is this process still running" check, used only
    to decide whether a lock file is genuinely still held (Section C:
    "a second process cannot clear a genuinely active lock") vs
    abandoned by a crash. Windows has no os.kill(pid, 0) equivalent
    (Python's os.kill on Windows does not reliably support signal 0),
    so this uses OpenProcess directly via ctypes on Windows and the
    standard os.kill(pid, 0) probe on POSIX - no extra dependency
    either way."""
    if os.name == "nt":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, just not owned by us
    return True


def _lock_owner_pid(lock_path: Path) -> Optional[int]:
    try:
        content = lock_path.read_text(encoding="ascii").strip()
        return int(content) if content else None
    except (OSError, ValueError):
        return None


def _lock_is_stale(lock_path: Path) -> bool:
    """True only if the lock file exists but does NOT correspond to a
    currently-running process - safe for recovery to clear on its own.
    False if the lock doesn't exist (nothing to clear) or genuinely
    belongs to a live process (never touched - Section C)."""
    if not lock_path.exists():
        return False
    pid = _lock_owner_pid(lock_path)
    if pid is None:
        return True  # unparseable/legacy lock content - treat as stale
    return not _pid_is_alive(pid)


def _acquire_lock(lock_path: Path) -> bool:
    """os.O_EXCL is the actual race guard - atomic at the OS level, so
    exactly one concurrent caller ever succeeds regardless of how many
    ask at once (Section C: "an active transaction cannot be raced").
    The PID written into it is ONLY ever used later to tell a genuinely
    live process apart from an abandoned one (_lock_is_stale) - it is
    not itself part of the race guard."""
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    os.write(fd, str(os.getpid()).encode("ascii"))
    os.close(fd)
    return True


def _lock_info(lock_path: Path) -> Optional[dict]:
    """Section E/B: "safely handles interruption and stale duplicate-
    submission locks" - a lock left behind by a crashed/interrupted
    reset or restore blocks new ones (correct - never race two against
    the same store), but must not be a silent, unexplained wall. Shows
    how long it's been held and whether it's stale (its owning process
    is no longer running) so an administrator can tell "this is normal,
    wait" from "this is stuck, recovery will clear it automatically" -
    clearing a genuinely live lock is never exposed as an in-app
    override button, which would defeat the guard's own purpose; a
    STALE one is cleared automatically by recovery, not by a button
    either (see _recover_interrupted_transactions)."""
    if not lock_path.exists():
        return None
    return {
        "age_seconds": int(time.time() - lock_path.stat().st_mtime),
        "stale": _lock_is_stale(lock_path),
    }


# -- CLAUDE-P40-E2A2, Section A/B: durable transaction journal + automatic
# crash recovery ------------------------------------------------------------
#
# Confirmed absent before this stage by direct code search (no journal,
# no PREPARED/LIVE_MOVED/etc. states, no automatic recovery anywhere in
# this repository) - implemented now. Reset and Restore both now go
# through ONE journal-backed executor (_run_registry_transaction) using
# the identical staged-build-then-atomic-swap pattern. Reset previously
# wiped store_path IN PLACE, file by file - Section E's "cannot leave a
# partially active registry" applies just as much to Reset as to
# Restore, so Reset no longer mutates the live directory directly at
# all; it builds the "clean" result off to the side first, exactly like
# Restore already did, so an interruption during EITHER operation is
# recoverable by the identical mechanism.

_JOURNAL_DIR_NAME = "reset_transactions"
_TXN_TERMINAL_STATES = {"ROLLED_BACK", "RECOVERED", "FAILED"}


class RegistryTransactionError(Exception):
    """Raised when a transaction's own post-swap verification fails -
    the live registry has been left at STAGED_INSTALLED, unresolved,
    for the next recovery pass to fix (never rolled back inline here -
    see _recover_one_transaction's STAGED_INSTALLED case, the identical
    path a real crash at this point would use)."""


class _DeliberateTestInterruption(Exception):
    """CLAUDE-P40-E2A2, Section E: raised ONLY when a caller explicitly
    passes _test_interrupt_after to _run_registry_transaction - no
    route ever passes this argument, so this is never reachable from
    any real request. Lets a test stop a transaction at an exact named
    checkpoint (leaving the journal/filesystem in exactly that state)
    and then prove _recover_interrupted_transactions brings it back to
    a single, verified state."""
    def __init__(self, checkpoint: str):
        super().__init__(f"deliberate test interruption after {checkpoint}")
        self.checkpoint = checkpoint


def _journal_dir(store_path: Path) -> Path:
    # A sibling of store_path, never inside it - the journal must
    # survive regardless of which of store_path's two renames a crash
    # lands between, so it can describe what happened either way.
    return store_path.parent / _JOURNAL_DIR_NAME


def _new_txn_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]


def _journal_path(store_path: Path, txn_id: str) -> Path:
    return _journal_dir(store_path) / f"{txn_id}.journal.json"


def _write_journal(journal_path: Path, entry: dict) -> None:
    """Atomic journal write: the full new content is built in a temp
    file beside the journal, then os.replace'd into place - os.replace
    is atomic on both Windows and POSIX (unlike plain os.rename on
    Windows, which fails outright if the destination already exists),
    so a reader never observes a half-written journal, and a crash
    mid-write leaves the OLD, still-valid journal content in place,
    never a corrupt one."""
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = journal_path.with_name(journal_path.name + f".tmp{os.getpid()}")
    with open(_win_long_path(tmp_path), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, indent=2))
    os.replace(_win_long_path(tmp_path), _win_long_path(journal_path))


def _read_journal(journal_path: Path) -> Optional[dict]:
    try:
        return json.loads(journal_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _journal_is_terminal(entry: dict) -> bool:
    state = entry.get("state")
    if state in _TXN_TERMINAL_STATES:
        return True
    return state == "VERIFIED" and bool(entry.get("cleanup_done"))


def _append_journal_history(entry: dict, state: str) -> None:
    entry["state"] = state
    entry.setdefault("history", []).append({"state": state, "at": datetime.now(timezone.utc).isoformat()})


def _run_registry_transaction(
    app, operation: str, actor: str, target_snapshot_dir: Optional[Path] = None,
    _test_interrupt_after: Optional[str] = None,
) -> dict:
    """
    The ONE journal-backed executor for both Reset Project Data
    ("reset") and Restore Snapshot ("restore"):

      1. PREPARED          - journal written FIRST, before any
                              destructive action, naming every path
                              this transaction will touch.
      2. a safety snapshot of the CURRENT live state is taken (kind=
         "reset" or "pre_restore_safety", unchanged in spirit from
         before this stage) and recorded into the journal.
      3. staged_dir is built completely, off to the side - a failure
         here never touches live_path at all.
      4. os.rename(live_path, old_path)            -> LIVE_MOVED
      5. os.rename(staged_dir, live_path)           -> STAGED_INSTALLED
      6. live_path re-verified against the checksums staged_dir was
         built to match                             -> VERIFIED
      7. rmtree(old_path)                           -> cleanup_done=True

    The journal directory is a sibling of store_path, untouched by
    either rename, so it survives to describe exactly what this
    transaction was doing regardless of where a crash lands.

    CLAUDE-P40-E2A2, Section D (Windows audit, empirically determined,
    not assumed): step 4's os.rename(live_path, old_path) requires NO
    open file handle anywhere inside live_path - a plain open(path,
    "rb") on a file inside the registry (default sharing flags, no
    FILE_SHARE_DELETE) blocks renaming the CONTAINING directory with
    PermissionError ([WinError 5] Access is denied). POSIX rename has
    no such restriction. This is safe, not silently corrupting: step 4
    is the FIRST destructive action, so a PermissionError there means
    old_path was never created and live_path was never touched - the
    journal is left at PREPARED, and recovery (once whatever held the
    handle releases it or the holding process is gone) finds a
    completely untouched registry and simply discards the unused
    staged directory (see _recover_one_transaction's Case A). staged_dir
    and old_path are always siblings of live_path (same parent
    directory, hence guaranteed same volume - asserted directly by
    tests, not merely assumed), which is what makes each individual
    os.rename atomic in the first place; a cross-volume REGISTRY_STORE_
    PATH configuration is not supported by this design.

    Never contains credentials or unvalidated user input: `actor` is a
    username string (not a credential), and every path recorded is
    server-computed from REGISTRY_STORE_PATH plus internally-generated
    UUIDs/timestamps. The one value that ever originates from a request
    (`snapshot_id` in the restore route) is already resolved to a
    validated, existing snapshot directory (_resolve_snapshot_dir)
    BEFORE it reaches this function as `target_snapshot_dir` - never a
    raw, unvalidated user-controlled path.

    `_test_interrupt_after` is a test-only fault-injection hook
    (CLAUDE-P40-E2A2, Section E) - see _DeliberateTestInterruption.
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    txn_id = _new_txn_id()
    journal_path = _journal_path(store_path, txn_id)

    token = uuid.uuid4().hex[:8]
    staged_dir = store_path.parent / f".{store_path.name}.staged_{token}"
    old_path = store_path.parent / f".{store_path.name}.old_{token}"

    def _checkpoint(name: str) -> None:
        if _test_interrupt_after == name:
            raise _DeliberateTestInterruption(name)

    entry = {
        "txn_id": txn_id,
        "operation": operation,
        "actor": actor,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "live_path": str(store_path),
        "staged_path": str(staged_dir),
        "old_path": str(old_path),
        "safety_backup_path": None,
        "target_snapshot_dir": str(target_snapshot_dir) if target_snapshot_dir else None,
        "expected_checksums": None,
        "state": "PREPARED",
        "cleanup_done": False,
        "history": [],
        "recovery": None,
    }
    _append_journal_history(entry, "PREPARED")
    _write_journal(journal_path, entry)
    _checkpoint("PREPARED")

    safety_snapshot_dir = _create_snapshot(
        store_path, snapshot_root, actor=actor,
        kind=("pre_restore_safety" if operation == "restore" else "reset"),
    )
    entry["safety_backup_path"] = str(safety_snapshot_dir)
    _write_journal(journal_path, entry)
    _checkpoint("SAFETY_SNAPSHOT_CREATED")

    staged_dir.mkdir(parents=True)
    if operation == "restore":
        for source_entry in target_snapshot_dir.iterdir():
            if source_entry.name in (SNAPSHOT_MANIFEST_FILENAME, "security_governance"):
                continue
            dest = staged_dir / source_entry.name
            if source_entry.is_dir():
                shutil.copytree(_win_long_path(source_entry), _win_long_path(dest))
            else:
                shutil.copy2(_win_long_path(source_entry), _win_long_path(dest))
    # operation == "reset": staged_dir starts empty - nothing to copy in.

    # security_governance/ ALWAYS comes from the CURRENT live store,
    # never the snapshot/target, for both operations - accounts and
    # security state are never reverted by either Reset or Restore.
    live_security_dir = store_path / "security_governance"
    if live_security_dir.exists():
        shutil.copytree(_win_long_path(live_security_dir), _win_long_path(staged_dir / "security_governance"))

    expected_checksums = _checksums_for_dir(staged_dir)
    entry["expected_checksums"] = expected_checksums
    _write_journal(journal_path, entry)

    os.rename(_win_long_path(store_path), _win_long_path(old_path))
    _append_journal_history(entry, "LIVE_MOVED")
    _write_journal(journal_path, entry)
    _checkpoint("LIVE_MOVED")

    os.rename(_win_long_path(staged_dir), _win_long_path(store_path))
    _append_journal_history(entry, "STAGED_INSTALLED")
    _write_journal(journal_path, entry)
    _checkpoint("STAGED_INSTALLED")

    _checkpoint("VERIFICATION_BEGUN")
    ok, problems = _verify_directory_against_checksums(store_path, expected_checksums)
    if not ok:
        # Left at STAGED_INSTALLED, unresolved - the identical path a
        # real crash at this exact point would leave behind, handled by
        # _recover_one_transaction's STAGED_INSTALLED case, not an ad
        # hoc rollback inline here.
        raise RegistryTransactionError(
            f"Post-transaction verification failed: {'; '.join(problems)}. "
            "The registry has been left for automatic recovery to resolve."
        )

    _append_journal_history(entry, "VERIFIED")
    _write_journal(journal_path, entry)
    _checkpoint("VERIFIED")

    shutil.rmtree(_win_long_path(old_path), ignore_errors=True)
    entry["cleanup_done"] = True
    _write_journal(journal_path, entry)
    _checkpoint("CLEANUP_DONE")

    audit_dir = store_path / "security_governance"
    audit_dir.mkdir(parents=True, exist_ok=True)
    with open(_win_long_path(audit_dir / "reset_audit.jsonl"), "a", encoding="utf-8") as fh:
        audit_record = {
            "event": ("snapshot_restored" if operation == "restore" else "reset"),
            "actor": actor,
            "at": datetime.now(timezone.utc).isoformat(),
            "txn_id": txn_id,
            "snapshot_dir": str(safety_snapshot_dir),
            "safety_snapshot_dir": str(safety_snapshot_dir),
        }
        if operation == "restore":
            audit_record["restored_snapshot_dir"] = str(target_snapshot_dir)
        fh.write(json.dumps(audit_record) + "\n")

    return {"txn_id": txn_id, "safety_snapshot_dir": safety_snapshot_dir}


def _recover_one_transaction(store_path: Path, entry: dict, journal_path: Path) -> dict:
    """
    Ground truth is always what's ACTUALLY on disk right now - a crash
    can happen at literally any point, so disk state is inspected
    directly to decide what happened; the journal is read only to know
    which paths this transaction was using and what the installed
    result should check out against (expected_checksums). Produces
    exactly one complete, verified live registry - either the pre-
    transaction state (ROLLED_BACK) or the fully-installed target
    state (RECOVERED) - never a mixture; FAILED only when neither can
    be established safely.
    """
    live_path = Path(entry["live_path"])
    staged_path = Path(entry["staged_path"])
    old_path = Path(entry["old_path"])
    expected_checksums = entry.get("expected_checksums")

    diagnostics = {
        "txn_id": entry["txn_id"],
        "journal_state": entry.get("state"),
        "live_exists": live_path.exists(),
        "staged_exists": staged_path.exists(),
        "old_exists": old_path.exists(),
    }

    def _finalize(outcome: str, action: str, extra: Optional[dict] = None) -> dict:
        _append_journal_history(entry, outcome)
        entry["recovery"] = {
            "resumed_at": datetime.now(timezone.utc).isoformat(),
            "action_taken": action,
            "diagnostics": {**diagnostics, **(extra or {})},
        }
        if outcome != "FAILED":
            entry["cleanup_done"] = True
        _write_journal(journal_path, entry)
        return {
            "outcome": outcome, "txn_id": entry["txn_id"], "action": action,
            "diagnostics": entry["recovery"]["diagnostics"],
        }

    # Case A: neither rename happened yet - live_path is still the
    # ORIGINAL pre-transaction content (old_path was never created).
    # Nothing on the live side needs touching; discard any partially-
    # built staged_dir.
    if not old_path.exists() and live_path.exists():
        if staged_path.exists():
            shutil.rmtree(_win_long_path(staged_path), ignore_errors=True)
        return _finalize("ROLLED_BACK", "live registry was never touched - discarded any partially-built staged directory")

    # Case B: the FIRST rename happened (live_path -> old_path) but the
    # second may not have - live_path is currently missing.
    if old_path.exists() and not live_path.exists():
        if staged_path.exists() and expected_checksums is not None:
            ok, problems = _verify_directory_against_checksums(staged_path, expected_checksums)
            if ok:
                os.rename(_win_long_path(staged_path), _win_long_path(live_path))
                ok2, problems2 = _verify_directory_against_checksums(live_path, expected_checksums)
                if ok2:
                    shutil.rmtree(_win_long_path(old_path), ignore_errors=True)
                    return _finalize("RECOVERED", "completed the swap - staged target verified and installed")
                # Installed but somehow doesn't verify post-install
                # (the rename itself cannot alter content, so this is
                # essentially unreachable) - move it back out of the
                # way rather than leave something unverified live.
                os.rename(_win_long_path(live_path), _win_long_path(staged_path))
                diagnostics["post_install_problems"] = problems2
                diagnostics["quarantined_staged_at"] = str(staged_path)
            else:
                diagnostics["staged_problems"] = problems
        # Staged copy missing or failed verification - fall back to the
        # known pre-transaction registry.
        os.rename(_win_long_path(old_path), _win_long_path(live_path))
        return _finalize("ROLLED_BACK", "restored the pre-transaction registry - staged target was missing or failed verification")

    # Case C: BOTH renames happened - live_path already holds the NEW
    # content; old_path (the previous content) is either still sitting
    # there awaiting cleanup, or verification/cleanup didn't finish.
    if live_path.exists():
        if expected_checksums is not None:
            ok, problems = _verify_directory_against_checksums(live_path, expected_checksums)
        else:
            ok, problems = True, []
        if ok:
            if old_path.exists():
                shutil.rmtree(_win_long_path(old_path), ignore_errors=True)
            return _finalize("RECOVERED", "live registry already matched the target - completed verification and cleanup")
        diagnostics["problems"] = problems
        if old_path.exists():
            # The installed copy is wrong; the pre-transaction copy is
            # still intact one level over - quarantine the bad copy and
            # restore the known-good one rather than leave a bad
            # registry live.
            quarantine_path = store_path.parent / f".{store_path.name}.quarantined_{uuid.uuid4().hex[:8]}"
            os.rename(_win_long_path(live_path), _win_long_path(quarantine_path))
            os.rename(_win_long_path(old_path), _win_long_path(live_path))
            diagnostics["quarantined_bad_copy_at"] = str(quarantine_path)
            return _finalize("ROLLED_BACK", "installed registry failed verification - quarantined it and restored the pre-transaction registry")
        return _finalize("FAILED", "installed registry failed verification and no pre-transaction copy is available to fall back to")

    # Neither live_path nor old_path exists - refuse to guess.
    return _finalize("FAILED", "no live or pre-transaction registry directory found - manual review required")


def _recover_interrupted_transactions(app) -> dict:
    """
    CLAUDE-P40-E2A2, Section B: runs (1) once per application boot,
    before any route can read the registry (called from app.py's
    create_app, before the app is returned), and (2) again at the top
    of both reset_project_data and restore_reset_snapshot, so a
    long-running process that never restarts still self-heals lazily,
    not just at boot.

    Never touches anything if the lock belongs to a genuinely live
    process (Section C: "a second process cannot clear a genuinely
    active lock") - recovering a transaction out from under the process
    still actively running it would be exactly the race this guards
    against. The lock itself is only ever cleared here once every
    non-terminal journal has reached a terminal state (Section C:
    "cleanup occurs only after verified completion or rollback").

    If any transaction cannot be resolved safely, sets
    app.config["REGISTRY_RECOVERY_FAILED"] (with diagnostics) rather
    than guessing - see app.py's _register_registry_guard, which fails
    the whole application closed against a missing/mixed/unverified
    registry when this is set, per this stage's own instruction not to
    start the application against exactly that.
    """
    store_path = Path(app.config["REGISTRY_STORE_PATH"])
    lock_path = store_path.parent / ".reset_project_data.lock"

    if lock_path.exists() and not _lock_is_stale(lock_path):
        return {"skipped": "active_lock", "recovered": [], "failed": []}

    journal_dir = _journal_dir(store_path)
    recovered: list[dict] = []
    failed: list[dict] = []
    if journal_dir.exists():
        for journal_path in sorted(journal_dir.glob("*.journal.json")):
            entry = _read_journal(journal_path)
            if entry is None or _journal_is_terminal(entry):
                continue
            result = _recover_one_transaction(store_path, entry, journal_path)
            if result["outcome"] == "FAILED":
                failed.append(result)
                app.config["REGISTRY_RECOVERY_FAILED"] = True
                app.config.setdefault("REGISTRY_RECOVERY_DIAGNOSTICS", []).append(result)
            else:
                recovered.append(result)

    if lock_path.exists() and _lock_is_stale(lock_path) and not failed:
        lock_path.unlink(missing_ok=True)

    return {"recovered": recovered, "failed": failed}


def _run_transaction_or_leave_for_recovery(
    app, lock_path: Path, operation: str, actor: str, target_snapshot_dir: Optional[Path] = None,
) -> tuple[bool, str]:
    """Runs the transaction; on success, clears the lock. On ANY
    failure (verification failure or an unexpected exception mid-swap),
    deliberately leaves the lock in place - Section B/C: "clear the
    lock only after recovery reaches a safe terminal state" - the next
    call to _recover_interrupted_transactions (the very next request to
    either admin page, or the next app restart) resolves it and clears
    the lock itself."""
    try:
        _run_registry_transaction(app, operation=operation, actor=actor, target_snapshot_dir=target_snapshot_dir)
    except RegistryTransactionError as exc:
        return False, (
            f"{operation.capitalize()} could not be verified and has been left for "
            f"automatic recovery on the next attempt: {exc}"
        )
    except Exception as exc:  # noqa: BLE001 - deliberately broad: any failure here
        # must leave the lock for recovery, never silently clear it
        # over an unresolved transaction (see this function's own
        # docstring).
        return False, (
            f"{operation.capitalize()} failed unexpectedly and has been left for "
            f"automatic recovery on the next attempt: {exc}"
        )
    lock_path.unlink(missing_ok=True)
    return True, ""


@portal_bp.route('/admin/reset-project-data', methods=['GET', 'POST'])
@admin_required
def reset_project_data():
    """
    GET shows the exact inventory and a typed-confirmation form. POST
    requires the confirmation phrase to match exactly, and is guarded
    against duplicate submission by an atomic lock file (os.O_EXCL - the
    first request to create it wins; a second, concurrent or
    double-clicked request sees FileExistsError and is told a reset is
    already running, rather than racing a second reset) - Section E:
    "make operations atomic or safely recoverable" /
    "prevent duplicate submission". The SAME lock file also guards
    restore_reset_snapshot below, so a reset and a restore against this
    store can never run concurrently either. Both GET and POST first
    run _recover_interrupted_transactions, so visiting this page alone
    is enough to self-heal a stuck prior operation.
    """
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    # Deliberately a sibling of store_path, not inside it - so the lock
    # file itself is never swept into a snapshot or the transaction's
    # own directory swap.
    lock_path = store_path.parent / ".reset_project_data.lock"

    _recover_interrupted_transactions(current_app)

    if request.method == 'GET':
        # CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01: "Project Data
        # Management" (this page's new identity - see
        # templates/reset_project_data.html's own header comment) is
        # now project-aware, via an OPTIONAL ?project_id= the Account
        # menu's own link supplies when reached from an open Project's
        # page. This is purely additive to the existing, unchanged,
        # deployment-wide reset below - active_project is None (and the
        # Add/Archive sections render an honest "no active project"
        # state) whenever no project_id is given, or the given one is
        # invalid/inaccessible - reuses the SAME centralized
        # authorization routine every other blueprint's loader wraps,
        # not a new access-control surface.
        active_project = None
        requested_project_id = request.args.get('project_id')
        if requested_project_id:
            from services.project_access import load_authorized_project_or_none
            registry = get_registry(current_app)
            store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
            governance_log = get_governance_log(current_app)
            result = load_authorized_project_or_none(
                store, registry, governance_log, requested_project_id, session.get('username'), is_admin(),
            )
            if result is not None:
                document, workspace = result
                if not workspace.removed_at:
                    active_project = {
                        "project_id": requested_project_id,
                        "display_name": workspace.display_title or document.filename,
                        "active_sources": CaseWorkspaceStore.active_sources(workspace),
                        "removed_sources": CaseWorkspaceStore.removed_sources(workspace),
                    }
        return render_template(
            'reset_project_data.html',
            inventory=_project_data_inventory(current_app),
            confirmation_phrase=RESET_CONFIRMATION_PHRASE,
            lock_info=_lock_info(lock_path),
            recovery_failed=current_app.config.get("REGISTRY_RECOVERY_FAILED", False),
            active_project=active_project,
            upload_entitled=user_can_upload_to_storage(),
        )

    if current_app.config.get("REGISTRY_RECOVERY_FAILED"):
        flash('The registry needs administrator attention before Reset can run again.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    if lock_path.exists():
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    typed = (request.form.get('confirmation_phrase') or '').strip()
    if typed != RESET_CONFIRMATION_PHRASE:
        flash(f'Type "{RESET_CONFIRMATION_PHRASE}" exactly to confirm - nothing was reset.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    if not _acquire_lock(lock_path):
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.reset_project_data'))

    ok, message = _run_transaction_or_leave_for_recovery(
        current_app, lock_path, operation="reset", actor=session.get('username') or 'unknown',
    )
    if ok:
        flash('Project data reset - the Workspace is clean. Everything that was here was snapshotted first.', 'success')
    else:
        flash(message, 'error')

    return redirect(url_for('portal.projects_list'))


@portal_bp.route('/admin/reset-project-data/snapshots')
@admin_required
def list_reset_snapshots():
    """CLAUDE-P40-E2A, Section B: "lists available reset snapshots by
    timestamp, actor and inventory" - every snapshot _create_snapshot
    has ever written (both Reset Project Data's own, and any prior
    restore's automatic pre_restore_safety copy), newest first."""
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    lock_path = store_path.parent / ".reset_project_data.lock"
    _recover_interrupted_transactions(current_app)
    return render_template(
        'reset_snapshots.html',
        snapshots=_list_snapshots(current_app),
        lock_info=_lock_info(lock_path),
        recovery_failed=current_app.config.get("REGISTRY_RECOVERY_FAILED", False),
    )


@portal_bp.route('/admin/reset-project-data/snapshots/<snapshot_id>/restore', methods=['GET', 'POST'])
@admin_required
def restore_reset_snapshot(snapshot_id):
    """
    GET verifies the snapshot's own checksums, previews what restoring
    it would replace (the CURRENT live inventory) against what it would
    bring back (the snapshot's own recorded inventory), and shows the
    typed-confirmation form - refused if integrity verification failed.
    POST re-verifies (never trusts the GET-time check alone), requires
    the confirmation phrase, and is guarded by the same lock file
    reset_project_data uses. Both GET and POST first run
    _recover_interrupted_transactions.
    """
    store_path = Path(current_app.config["REGISTRY_STORE_PATH"])
    snapshot_root = store_path.parent / "registry_snapshots"
    lock_path = store_path.parent / ".reset_project_data.lock"

    _recover_interrupted_transactions(current_app)

    snapshot_dir = _resolve_snapshot_dir(snapshot_root, snapshot_id)
    if snapshot_dir is None:
        abort(404)

    if request.method == 'GET':
        try:
            manifest = json.loads((snapshot_dir / SNAPSHOT_MANIFEST_FILENAME).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            manifest = {}
        ok, problems = _verify_snapshot_integrity(snapshot_dir)
        return render_template(
            'restore_snapshot.html',
            snapshot_id=snapshot_id,
            manifest=manifest,
            integrity_ok=ok,
            integrity_problems=problems,
            current_inventory=_project_data_inventory(current_app),
            confirmation_phrase=RESTORE_CONFIRMATION_PHRASE,
            lock_info=_lock_info(lock_path),
            recovery_failed=current_app.config.get("REGISTRY_RECOVERY_FAILED", False),
        )

    if current_app.config.get("REGISTRY_RECOVERY_FAILED"):
        flash('The registry needs administrator attention before Restore can run again.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    if lock_path.exists():
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    typed = (request.form.get('confirmation_phrase') or '').strip()
    if typed != RESTORE_CONFIRMATION_PHRASE:
        flash(f'Type "{RESTORE_CONFIRMATION_PHRASE}" exactly to confirm - nothing was restored.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    # Re-verified here (never trusts the GET-time check alone) BEFORE
    # acquiring the lock or starting the transaction - a corrupt target
    # snapshot must never even begin a swap.
    ok, problems = _verify_snapshot_integrity(snapshot_dir)
    if not ok:
        flash('Snapshot failed integrity verification - nothing was restored: ' + '; '.join(problems), 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    if not _acquire_lock(lock_path):
        flash('A Reset or Restore is already in progress - please wait for it to finish.', 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    ok, message = _run_transaction_or_leave_for_recovery(
        current_app, lock_path, operation="restore", actor=session.get('username') or 'unknown',
        target_snapshot_dir=snapshot_dir,
    )
    if ok:
        flash('Snapshot restored. A safety snapshot of what was live just before this was also taken.', 'success')
    else:
        flash(message, 'error')
        return redirect(url_for('portal.restore_reset_snapshot', snapshot_id=snapshot_id))

    return redirect(url_for('portal.projects_list'))

@portal_bp.route('/search')
@login_required
def global_search():
    """
    Global search overlay's backend (UI design-development pass: sidebar
    header / search). Projects are the one real, already-indexed,
    cross-project searchable object in this application today - the same
    filename/project_id substring match the Projects directory's own
    search already uses (see projects_list above), just exposed as JSON
    for the overlay instead of a full-page GET.

    The result shape (kind/title/subtitle/url) is deliberately generic so
    Requirements/Investigations/Findings/RFIs/etc. can become real search
    sources later without changing this shape or the overlay's rendering
    - this route must never claim search coverage the backend doesn't
    actually have.
    """
    query = (request.args.get('q') or '').strip()
    if not query:
        return jsonify(results=[])

    needle = query.lower()
    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    documents = _accessible_documents(registry, store)
    matches = [
        d for d in documents
        if needle in d.filename.lower() or needle in d.project_id.lower()
    ][:20]

    results = [
        {
            "kind": "Project",
            "title": d.filename,
            "subtitle": d.project_id,
            "url": url_for('workspace.show_workspace', project_id=d.project_id),
        }
        for d in matches
    ]
    return jsonify(results=results)


def _posted_retained_by() -> str | None:
    """The upstream answer belonging to the position actually chosen.

    Each position renders its own select (`retained_by__<choice>`) so a visitor
    is never offered a relationship that does not apply to them. Only the
    chosen position's answer is read; a stale value left in another group by a
    visitor who changed their mind is ignored rather than mistakenly attached.
    The legacy flat `retained_by` field is still honoured for direct posters.
    """
    choice = request.form.get('entry_choice')
    if choice:
        scoped = request.form.get(f'retained_by__{choice}')
        if scoped:
            return scoped
    return request.form.get('retained_by') or None


def _resolved_operating_environment() -> str:
    """CLAUDE-ENTRY-REDUNDANCY-01: the environment for this creation request.

    Live review found the form asking two adjacent questions - the operating
    environment and the project position - which put the same words
    ("Client / Owner") in two boxes meaning different things and exposed an
    internal abstraction as a user decision. The redundant USER DECISION is
    removed here; the internal semantic distinction is not. operating
    environment remains its own locked, required, governed field - it is simply
    derived from the position the user actually declared rather than asked for
    twice.

    Falls back to an explicitly posted value whenever a position was not
    declared or cannot resolve one. That keeps every existing caller working
    unchanged - 84 test files and both non-browser creation paths post this
    field directly - and it means an unresolved consultant position surfaces as
    the ordinary "required" validation rather than being quietly guessed. The
    field is locked at creation and irreversible, so guessing it wrong would
    cost the user their whole project.
    """
    derived = operating_environment_for(
        request.form.get('entry_choice'), _posted_retained_by(),
    )
    if derived:
        return derived
    return request.form.get('operating_environment', '')


def _establish_perspective(project_id: str, entry_choice: str | None, retained_by: str | None) -> None:
    """CLAUDE-PERSPECTIVE-GATE-04: record the declared working position.

    Called immediately after a project is created, on every creation path, so
    a project established through the confirm step or a folder carries the same
    declaration as one established directly. Deliberately kept out of
    ingest_upload's own signature: that function has many callers, and the
    position is a route-layer declaration by the person creating the project,
    not an ingestion concern.

    Silently does nothing when no choice was made. That is the honest legacy
    state -- a project with no declared perspective, which is exactly what
    every project created before this gate existed has. It is never guessed.

    A rejected value must not destroy a successfully-created project: the
    project and its evidence are already real and intact, so a bad declaration
    is dropped rather than raised. Nothing downstream depends on it, because
    perspective is context, never authority.
    """
    if not entry_choice:
        return
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        return
    actor = session.get("username", "") or "system"
    governance_log = get_governance_log(current_app)
    try:
        store.set_project_perspective(
            workspace, entry_choice=entry_choice, actor=actor,
            retained_by=retained_by or None, governance_log=governance_log,
        )
        return
    except CaseWorkspaceError:
        pass

    # An upstream relationship that does not belong to this position must not
    # cost the user their position as well. The two declarations are separable,
    # so the position is recorded and the mismatched relationship is simply not
    # -- rather than being coerced into whatever would have been valid, which
    # would be guessing.
    try:
        store.set_project_perspective(
            workspace, entry_choice=entry_choice, actor=actor,
            retained_by=None, governance_log=governance_log,
        )
        current_app.logger.info(
            "Dropped mismatched upstream relationship for %s: choice=%r retained_by=%r",
            project_id, entry_choice, retained_by,
        )
    except CaseWorkspaceError:
        current_app.logger.info(
            "Rejected project entry declaration for %s: choice=%r", project_id, entry_choice,
        )


def _pending_upload_store() -> PendingUploadStore:
    return PendingUploadStore(current_app.config["REGISTRY_STORE_PATH"])


@portal_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def upload():
    max_upload_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)

    if request.method == 'GET':
        # CLAUDE-P29: an optional ?environment= deep link from the two
        # gateway entrance cards pre-selects the radio -- convenience
        # only, the POST below validates independently regardless of
        # how the form was reached or what was pre-selected.
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb,
            selected_environment=request.args.get('environment'),
            operating_environments=OPERATING_ENVIRONMENT_LABELS,
            entry_choices=entry_choice_view(),
            upload_entitled=user_can_upload_to_storage(),
        )

    file_storage = request.files.get('file')
    if file_storage is None or not file_storage.filename:
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb, error="No file was provided.",
            selected_environment=request.form.get('operating_environment'),
            operating_environments=OPERATING_ENVIRONMENT_LABELS,
            entry_choices=entry_choice_view(),
        ), 400

    # CLAUDE-P40-VW8-QA-R2A: staging-time analysis ONLY (native-text/
    # candidate extraction - see services/drawing_intake.py's own
    # header for exactly what this does and doesn't do; no external
    # call of any kind happens here). A plain RFP/RFQ with no drawing-
    # like candidates and real native text behaves EXACTLY as before -
    # straight to ingest_upload, no new step in the way. Only a request
    # with something genuinely worth confirming (a candidate found, or
    # an image-only PDF that needs an honest capability report) is
    # routed through the new confirm step.
    filename = file_storage.filename
    raw_bytes = file_storage.read()
    file_storage.stream.seek(0)
    intake = analyze_upload(raw_bytes, filename)

    entered_project_name = request.form.get('project_name')
    if not intake.candidates and intake.text_extraction_status == "extracted":
        try:
            document = ingest_upload(
                file_storage,
                current_app,
                operating_environment=_resolved_operating_environment(),
                # CLAUDE-P32: the real, already-authenticated session identity
                # (this route is @admin_required) -- never request.form.get
                # ('actor'), which is free text a caller could type anything
                # into (see ingest_upload's own docstring for why the two
                # must stay separate).
                owner=session.get('username', ''),
                actor=request.form.get('actor'),
                role=request.form.get('role'),
                project_name=entered_project_name,
            )
        except (UploadError, GovernanceError) as exc:
            return render_template(
                'upload.html', max_upload_mb=max_upload_mb, error=str(exc),
                selected_environment=request.form.get('operating_environment'),
                operating_environments=OPERATING_ENVIRONMENT_LABELS,
                entry_choices=entry_choice_view(),
            ), 400

        # CLAUDE-P38-D2: routes through the "Preparing your Project
        # Briefing..." interstitial rather than straight to the workspace -
        # that route itself redirects straight through when there's nothing
        # to prepare (AI not allowed/already approval-gated/no Sources), so
        # this is always safe to do unconditionally here.
        _establish_perspective(
            document.project_id,
            request.form.get('entry_choice'), _posted_retained_by(),
        )

        return redirect(url_for('workspace.preparing_project_briefing', project_id=document.project_id))

    operating_environment = _resolved_operating_environment()
    staging_id = _pending_upload_store().create(
        raw_bytes=raw_bytes, filename=filename, candidates=intake.candidates,
        text_extraction_status=intake.text_extraction_status,
        operating_environment=operating_environment, owner=session.get('username', ''),
        actor=request.form.get('actor'), role=request.form.get('role'),
        entered_project_name=entered_project_name,
        entry_choice=request.form.get('entry_choice'),
        retained_by=_posted_retained_by(),
    )
    return redirect(url_for('portal.upload_confirm', staging_id=staging_id))


@portal_bp.route('/upload/folder', methods=['POST'])
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def upload_folder():
    """
    CLAUDE-CA1D-RECEPTION-FIX-01: establishes a project from a whole
    folder rather than one file. The browser-side folder picker
    (webkitdirectory) attaches each file's original relative path as
    ITS OWN filename before submission (see upload.html's own script) -
    request.files.getlist('folder_files')[i].filename IS the relative
    path here, e.g. "RFP Package/exhibits/spec.pdf", never a raw
    filesystem path this server ever had independent access to. The
    founding document is never inferred here -- `founding_relative_path`
    must exactly match one of the submitted files' own filenames,
    something only the client-side confirmation step could have set;
    an unmatched value fails closed with a real error, never a guess.

    Deliberately skips the single-file path's scanned-drawing-candidate
    staging/confirm interstitial (analyze_upload/PendingUploadStore,
    above) for the founding document -- extending that flow to a
    multi-file establishment is real additional scope this tranche
    does not cover; noted as a residual, not a silent behavior change
    a reviewer would have no way to notice.

    CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01 addendum (Storage Grammar &
    Public-Trial Entitlement, Part 6): the real server-side gate -
    upload.html greys the picker/submit when not entitled, but that's
    cosmetic only; this abort(403) is what actually stops a direct POST
    here from bypassing it.
    """
    if not user_can_upload_to_storage():
        abort(403)

    max_upload_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    common_context = dict(
        max_upload_mb=max_upload_mb,
        selected_environment=request.form.get('operating_environment'),
        operating_environments=OPERATING_ENVIRONMENT_LABELS,
        entry_choices=entry_choice_view(),
    )

    files = request.files.getlist('folder_files')
    files = [f for f in files if f and f.filename]
    if not files:
        return render_template('upload.html', error="No folder was selected.", **common_context), 400

    relative_paths = [f.filename for f in files]
    founding_relative_path = request.form.get('founding_relative_path', '')
    try:
        founding_index = relative_paths.index(founding_relative_path)
    except ValueError:
        return render_template(
            'upload.html', error="The principal document selection is invalid. Please choose the folder again.",
            **common_context,
        ), 400

    try:
        document, results = ingest_folder_upload(
            files, relative_paths, founding_index, current_app,
            operating_environment=_resolved_operating_environment(),
            owner=session.get('username', ''),
            actor=request.form.get('actor'), role=request.form.get('role'),
            project_name=request.form.get('project_name'),
            # CLAUDE-PROJECT-CODE-01: blank is normal and safe - ingest_upload
            # derives one from the project name. The field exists so the user
            # CAN choose, never so they must.
            project_code=request.form.get('project_code'),
        )
    except (UploadError, GovernanceError) as exc:
        return render_template('upload.html', error=str(exc), **common_context), 400

    _establish_perspective(
        document.project_id,
        request.form.get('entry_choice'), _posted_retained_by(),
    )

    added = [r for r in results if r["status"] == "added"]
    skipped = [r for r in results if r["status"] == "skipped"]
    if added:
        flash(f"Established with {len(added)} additional document(s) from the folder.", "success")
    if skipped:
        flash(
            "Not added (" + str(len(skipped)) + "): " +
            "; ".join(f"{r['relative_path']} - {r['reason']}" for r in skipped),
            "error",
        )

    return redirect(url_for('workspace.preparing_project_briefing', project_id=document.project_id))


@portal_bp.route('/upload/confirm/<staging_id>', methods=['GET', 'POST'])
@admin_required
def upload_confirm(staging_id):
    store = _pending_upload_store()
    manifest = store.get(staging_id)
    if manifest is None:
        abort(404)
    # A staged upload is a per-reviewer scratch area, not a shared
    # authorization surface - the same admin who started it (or any
    # other admin, matching this route's own @admin_required, the
    # identical gate /upload already uses) can confirm/discard it, but
    # nothing about it is exposed to a non-admin session at all.

    candidates_by_field = {c["field"]: c for c in manifest["candidates"]}
    name_conflict = (
        manifest.get("entered_project_name")
        and candidates_by_field.get("project_name")
        and manifest["entered_project_name"].strip() != candidates_by_field["project_name"]["value"].strip()
    )

    if request.method == 'GET':
        return render_template(
            'upload_confirm.html', manifest=manifest, staging_id=staging_id,
            candidate_fields=CANDIDATE_FIELDS, field_labels=FIELD_LABELS,
            candidates_by_field=candidates_by_field, name_conflict=name_conflict,
        )

    # POST: build the confirmed/corrected field set from the submitted
    # form. Every field the reviewer sees is editable (a machine
    # candidate is a PROPOSAL, never authoritative on its own - Section
    # 5's "machine proposes, human confirms or corrects") - status is
    # "confirmed" when the submitted value matches the original
    # candidate exactly, "corrected" when the reviewer changed it.
    confirmed_fields = []
    for field_name in CANDIDATE_FIELDS:
        submitted = (request.form.get(f"field_{field_name}") or "").strip()
        if not submitted:
            continue
        original = candidates_by_field.get(field_name)
        status = STATUS_CONFIRMED if original and original["value"].strip() == submitted else STATUS_CORRECTED
        confirmed_fields.append({
            "field": field_name, "value": submitted, "status": status,
            "original_candidate": original,
        })

    if name_conflict:
        choice = request.form.get('project_name_choice', '')
        if choice == 'entered':
            final_project_name = manifest["entered_project_name"]
        elif choice == 'candidate':
            final_project_name = candidates_by_field["project_name"]["value"]
        elif choice == 'custom':
            final_project_name = (request.form.get('project_name_custom') or '').strip()
        else:
            return render_template(
                'upload_confirm.html', manifest=manifest, staging_id=staging_id,
                candidate_fields=CANDIDATE_FIELDS, field_labels=FIELD_LABELS,
                candidates_by_field=candidates_by_field, name_conflict=name_conflict,
                error="Choose which Project name to use before continuing.",
            ), 400
    else:
        final_project_name = next(
            (f["value"] for f in confirmed_fields if f["field"] == "project_name"),
            manifest.get("entered_project_name"),
        )

    raw_bytes = store.get_raw_bytes(staging_id)
    if raw_bytes is None:
        abort(404)

    file_storage = FileStorage(stream=io.BytesIO(raw_bytes), filename=manifest["filename"])

    try:
        document = ingest_upload(
            file_storage, current_app,
            operating_environment=manifest["operating_environment"],
            owner=manifest["owner"], actor=manifest.get("actor"), role=manifest.get("role"),
            project_name=final_project_name,
        )
    except (UploadError, GovernanceError) as exc:
        return render_template(
            'upload_confirm.html', manifest=manifest, staging_id=staging_id,
            candidate_fields=CANDIDATE_FIELDS, field_labels=FIELD_LABELS,
            candidates_by_field=candidates_by_field, name_conflict=name_conflict,
            error=str(exc),
        ), 400

    # CLAUDE-P40-VW8-QA-R2A Section 4/5: "Archiosk records the evidence
    # and decision" - every candidate's original machine-proposed value
    # alongside what the reviewer actually confirmed/corrected, and
    # (when applicable) which of the two conflicting Project names was
    # chosen. A NEW governance_log event, not a mutation of
    # document_ingested's own existing payload - append-only, matching
    # every other governance event in this codebase.
    _establish_perspective(
        document.project_id,
        manifest.get("entry_choice"), manifest.get("retained_by"),
    )

    governance_log = get_governance_log(current_app)
    governance_log.append(
        project_id=document.project_id, event_type="drawing_metadata_candidates_confirmed",
        actor=manifest.get("actor") or "system", role=manifest.get("role") or "system",
        payload={
            "text_extraction_status": manifest["text_extraction_status"],
            "candidates_offered": manifest["candidates"],
            "fields_confirmed": confirmed_fields,
            "project_name_conflict": bool(name_conflict),
            "project_name_choice": request.form.get('project_name_choice') if name_conflict else None,
        },
    )

    store.discard(staging_id)
    return redirect(url_for('workspace.preparing_project_briefing', project_id=document.project_id))


@portal_bp.route('/upload/confirm/<staging_id>/discard', methods=['POST'])
@admin_required
def upload_confirm_discard(staging_id):
    _pending_upload_store().discard(staging_id)
    return redirect(url_for('portal.upload'))


@portal_bp.route('/dashboard')
@portal_bp.route('/dashboard/<project_id>')
@login_required
def dashboard(project_id=None):
    """
    Retired as a real page - Case Workspace is now the one authoritative
    project view (it already showed everything the legacy Dashboard did:
    extracted-not-governed Requirements, governed Requirements, RFI
    Export with the actual flagged-contradiction cards, History/audit
    trail). The one piece deliberately NOT carried forward is the
    milestone lattice: _derive_milestones (bhive_parser.py) only ever
    produces status="pending" for real projects - "done"/"active" only
    ever appeared in this route's own hardcoded demo data - so it never
    reflected real project state and there was nothing genuine to port.

    Kept as a redirect, not deleted outright, so an old bookmark or
    external link to /dashboard/<id> still lands somewhere real instead
    of 404ing.
    """
    if project_id is None:
        return redirect(url_for('portal.projects_list'))

    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)
    # CLAUDE-P32: checked here too (not just relying on the redirect
    # target's own gate) so a denied request 404s directly rather than
    # bouncing through an extra redirect first.
    _require_project_access_or_404(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), project_id)
    return redirect(url_for('workspace.show_workspace', project_id=project_id))
