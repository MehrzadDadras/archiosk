"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, request, url_for

from services.auth import admin_required, check_credentials, is_authenticated, log_in, log_out, login_required
from services.bhive_parser import REQUIREMENT_CATEGORIES
from services.case_workspace import CaseWorkspaceStore
from services.governance import GovernanceError
from services.ingestion import UploadError, get_governance_log, get_registry, ingest_upload

portal_bp = Blueprint('portal', __name__)

# Shown on GET /dashboard (no project_id yet) so the UI is visible before
# anyone has ingested a real document — see README "Without an ingested doc".
_DEMO_MILESTONES = [
    {"id": "demo-1", "label": "Submit pre-qualification packet", "status": "done", "source_line": 4},
    {"id": "demo-2", "label": "Site walkthrough deadline", "status": "done", "source_line": 12},
    {"id": "demo-3", "label": "Final proposal due", "status": "active", "source_line": 30},
    {"id": "demo-4", "label": "Award notification", "status": "pending", "source_line": 41},
]

_DEMO_REQUIREMENTS = [
    {"id": "demo-r1", "text": "Contractor shall provide licensed and insured labor.",
     "category": "compliance_legal", "confidence": 0.7, "source_line": 6},
    {"id": "demo-r2", "text": "Work shall include demolition and site preparation.",
     "category": "scope_of_work", "confidence": 0.68, "source_line": 9},
    {"id": "demo-r3", "text": "Proposal must include an itemized cost breakdown.",
     "category": "budget_commercial", "confidence": 0.72, "source_line": 18},
    {"id": "demo-r4", "text": "Materials shall comply with ASTM specifications.",
     "category": "technical_specification", "confidence": 0.66, "source_line": 22},
    {"id": "demo-r5", "text": "Submissions must be received by 5:00 PM on the due date.",
     "category": "submission_instruction", "confidence": 0.7, "source_line": 28},
    {"id": "demo-r6", "text": "Proposals will be evaluated on cost, schedule, and experience.",
     "category": "evaluation_criteria", "confidence": 0.75, "source_line": 33},
]


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

    return redirect(url_for('portal.dashboard', project_id=document.project_id))


@portal_bp.route('/dashboard')
@portal_bp.route('/dashboard/<project_id>')
@login_required
def dashboard(project_id=None):
    if project_id is None:
        return render_template(
            'dashboard.html',
            is_demo=True,
            project_id=None,
            filename='sample_rfp.pdf (demo)',
            display_name='sample_rfp.pdf (demo)',
            requirements=_DEMO_REQUIREMENTS,
            milestones=_DEMO_MILESTONES,
            categories=REQUIREMENT_CATEGORIES,
            consistency_flags=[],
            consistency_checked=False,
            consistency_note='Demo data — the consistency check requires a real document and an Anthropic API key.',
            governance_events=[],
        )

    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    governance_events = get_governance_log(current_app).read(project_id)
    # Pagescape correction #11/#12: resolve the same display_title the
    # Case Workspace already supports (Edit Project Details) so the
    # legacy Dashboard shows the professional's chosen project identity
    # too, not just whichever filename was ingested first - a read-only
    # lookup, no CaseWorkspaceStore write happens on a GET.
    workspace = _safe_workspace(CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"]), project_id)
    display_name = (workspace.display_title if workspace else None) or document.filename

    return render_template(
        'dashboard.html',
        is_demo=False,
        project_id=document.project_id,
        filename=document.filename,
        display_name=display_name,
        requirements=[r.__dict__ for r in document.requirements],
        milestones=document.milestones,
        categories=REQUIREMENT_CATEGORIES,
        consistency_flags=[f.__dict__ for f in document.consistency_flags],
        consistency_checked=document.consistency_checked,
        consistency_note=document.consistency_note,
        governance_events=[e.__dict__ for e in reversed(governance_events)],
    )
