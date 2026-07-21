"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, redirect, render_template, request, url_for

from services.bhive_parser import REQUIREMENT_CATEGORIES
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


@portal_bp.route('/')
def index():
    return render_template('index.html')


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


@portal_bp.route('/upload', methods=['GET', 'POST'])
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
        )
    except (UploadError, GovernanceError) as exc:
        return render_template(
            'upload.html', max_upload_mb=max_upload_mb, error=str(exc)
        ), 400

    return redirect(url_for('portal.dashboard', project_id=document.project_id))


@portal_bp.route('/dashboard')
@portal_bp.route('/dashboard/<project_id>')
def dashboard(project_id=None):
    if project_id is None:
        return render_template(
            'dashboard.html',
            is_demo=True,
            project_id=None,
            filename='sample_rfp.pdf (demo)',
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

    return render_template(
        'dashboard.html',
        is_demo=False,
        project_id=document.project_id,
        filename=document.filename,
        requirements=[r.__dict__ for r in document.requirements],
        milestones=document.milestones,
        categories=REQUIREMENT_CATEGORIES,
        consistency_flags=[f.__dict__ for f in document.consistency_flags],
        consistency_checked=document.consistency_checked,
        consistency_note=document.consistency_note,
        governance_events=[e.__dict__ for e in reversed(governance_events)],
    )
