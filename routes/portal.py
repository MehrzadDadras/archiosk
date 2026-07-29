"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for

from services.auth import admin_required, check_credentials, is_authenticated, log_in, log_out, login_required
from services.rate_limit import limiter
from services.case_workspace import CaseWorkspaceStore
from services.governance import GovernanceError
from services.ingestion import UploadError, get_governance_log, get_registry, ingest_upload
from services.password_reset import (
    complete_password_reset, get_valid_reset_token, is_dev_fallback_active, request_password_reset,
)

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


@portal_bp.route('/')
def index():
    """
    Project-first entry point: "what project are we working on," not a
    marketing page and not "how can I help you today." Anonymous visitors
    see the identity line + sign-in only. Authenticated visitors see a
    small, restrained recent-projects list - see _project_summary for the
    indicator set.
    """
    if not is_authenticated():
        return render_template('index.html', recent_projects=[])

    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    governance_log = get_governance_log(current_app)

    documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    documents.sort(key=lambda d: d.ingested_at, reverse=True)

    recent_projects = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents[:6]
    ]

    return render_template('index.html', recent_projects=recent_projects)


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

    missing_config = []
    if not current_app.config.get('SECRET_KEY'):
        missing_config.append('FLASK_SECRET_KEY')
    if not current_app.config.get('ANTHROPIC_API_KEY'):
        missing_config.append('ANTHROPIC_API_KEY')

    status_code = 200 if registry_ok else 503
    return jsonify(
        status='ok' if registry_ok else 'error',
        checks={'registry_store': 'ok' if registry_ok else 'unreachable'},
        missing_config=missing_config,
    ), status_code


@portal_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("10 per minute", methods=["POST"])
def login():
    if request.method == 'GET':
        return render_template('login.html', error=None)

    username = request.form.get('username', '')
    password = request.form.get('password', '')
    user = check_credentials(username, password)
    if user is not None:
        log_in(user)
        # No specific ?next= target -> land on the project gateway (pick
        # ingest vs. dashboard) rather than jumping straight into one.
        next_url = request.args.get('next') or url_for('portal.gateway')
        # Only follow same-site relative paths -- ?next=https://evil.example
        # would otherwise redirect an authenticated session off-site.
        if not next_url.startswith('/') or next_url.startswith('//'):
            next_url = url_for('portal.gateway')
        return redirect(next_url)

    # Deliberately generic -- doesn't distinguish "no such user" from
    # "wrong password" (there's only one shared username anyway).
    return render_template('login.html', error='Invalid username or password.'), 401


@portal_bp.route('/logout')
def logout():
    log_out()
    return redirect(url_for('portal.index'))


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


@portal_bp.route('/gateway')
@login_required
def gateway():
    """Post-login landing: pick "ingest a new document" vs "view dashboard"
    instead of jumping straight into one, mirroring a project-selection
    style entry point rather than a single default destination."""
    return render_template('gateway.html')


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

    documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
    if query:
        needle = query.lower()
        documents = [
            d for d in documents
            if needle in d.filename.lower() or needle in d.project_id.lower()
        ]

    projects = [
        _project_summary(document, _safe_workspace(store, document.project_id), governance_log.read(document.project_id))
        for document in documents
    ]
    projects.sort(key=_PROJECT_SORT_KEYS[sort], reverse=(sort != 'name'))

    return render_template('projects.html', projects=projects, query=query, sort=sort)


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
    documents = [d for pid in registry.list_ids() if (d := registry.get(pid)) is not None]
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


@portal_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
@limiter.limit("20 per hour", methods=["POST"])
def upload():
    max_upload_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)

    if request.method == 'GET':
        return render_template('upload.html', max_upload_mb=max_upload_mb)

    try:
        document = ingest_upload(
            request.files.get('file'),
            current_app,
            actor=request.form.get('actor'),
            role=request.form.get('role'),
            project_name=request.form.get('project_name'),
        )
    except (UploadError, GovernanceError) as exc:
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb, error=str(exc)
        ), 400

    return redirect(url_for('workspace.show_workspace', project_id=document.project_id))


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
    return redirect(url_for('workspace.show_workspace', project_id=project_id))
