"""
HTML pages: marketing home, upload form, and the Agility Engine dashboard.
"""
from __future__ import annotations

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from services.bhive_parser import REQUIREMENT_CATEGORIES
from services.ingestion import UploadError, get_registry, ingest_upload

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


@portal_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    max_upload_mb = current_app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)

    if request.method == 'GET':
        return render_template('upload.html', max_upload_mb=max_upload_mb)

    try:
        document = ingest_upload(request.files.get('file'), current_app)
    except UploadError as exc:
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
        )

    document = get_registry(current_app).get(project_id)
    if document is None:
        abort(404)

    return render_template(
        'dashboard.html',
        is_demo=False,
        project_id=document.project_id,
        filename=document.filename,
        requirements=[r.__dict__ for r in document.requirements],
        milestones=document.milestones,
        categories=REQUIREMENT_CATEGORIES,
    )
