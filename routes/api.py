"""
JSON API for the B-Hive document pipeline (mounted at /api/v1).

Authentication: every route in this blueprint requires the same
session-cookie login used by routes/portal.py (services.auth) -- a
caller authenticates via POST /login first (curl -c/-b, or any client
that keeps the session cookie) rather than via a separate API key.
This is the smallest change compatible with the app's existing single
auth mechanism; a dedicated token/key scheme remains a legitimate
future direction (see services/auth.py's docstring) but is a distinct
concern, not required to close the "no auth at all" defect this fixes.

Enforced blueprint-wide via before_request (not a per-route decorator)
specifically so a future new route can't omit it by accident. Role
split mirrors the equivalent HTML routes exactly rather than inventing
a new authorization axis: ingest is the API equivalent of
routes/portal.py's `/upload` (@admin_required); every read route is
the API equivalent of the @login_required dashboard/gateway pages.
"""
from __future__ import annotations

from flask import Blueprint, abort, current_app, jsonify, request, send_file, session
from werkzeug.exceptions import RequestEntityTooLarge

from services.auth import is_admin, is_authenticated
from services.bhive_parser import REQUIREMENT_CATEGORIES
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import OPERATING_ENVIRONMENT_LABELS
from services.governance import GovernanceError
from services.ingestion import UploadError, get_governance_log, get_registry, ingest_upload
from services.rate_limit import limiter
from services.rfi_export import RFIExportError, build_rfi_docx

api_bp = Blueprint('api', __name__)


_ADMIN_ONLY_ENDPOINTS = {
    "api.ingest_document", "api.register_pdf_structure",
    "api.register_spreadsheet_structure_route", "api.edit_spreadsheet_cell",
    "api.register_drawing_structure", "api.create_drawing_region",
}


@api_bp.before_request
def _require_api_auth():
    if not is_authenticated():
        return jsonify(error="unauthorized", message="Authentication required."), 401
    if request.endpoint in _ADMIN_ONLY_ENDPOINTS and not is_admin():
        return jsonify(error="forbidden", message="Admin role required."), 403


@api_bp.errorhandler(RequestEntityTooLarge)
def _file_too_large(_err):
    max_mb = current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify(
        error="file_too_large",
        message=f"Upload exceeds the {max_mb}MB limit.",
    ), 413


@api_bp.route('/documents/ingest', methods=['POST'])
@limiter.limit("20 per hour")
def ingest_document():
    try:
        document = ingest_upload(
            request.files.get('file'),
            current_app,
            operating_environment=request.form.get('operating_environment', ''),
            # CLAUDE-P32: real session identity -- see
            # routes/portal.py's upload() for why this is never
            # request.form.get('actor').
            owner=session.get('username', ''),
            actor=request.form.get('actor'),
            role=request.form.get('role'),
            project_name=request.form.get('project_name'),
        )
    except UploadError as exc:
        return jsonify(error="invalid_upload", message=str(exc)), 400
    except GovernanceError as exc:
        return jsonify(error="invalid_governance_fields", message=str(exc)), 400

    return jsonify(document.to_dict()), 201


def _load_authorized_project_or_404(project_id: str):
    """
    CLAUDE-P32: the shared loader every project-scoped route in this
    blueprint now goes through, wrapping services.project_access.
    load_authorized_project_or_none -- the same centralized decision
    routes/workspace.py's _load_workspace_or_404 uses, translated into
    this blueprint's own JSON 404 shape (via plain abort(404), which
    app.py's error handler already renders as JSON for any /api/ path)
    rather than a second, divergent access-check implementation.
    Deliberately returns the SAME generic 404 whether the project
    doesn't exist or the caller isn't authorized for it -- distinguishing
    the two would let a caller enumerate real project ids by the error
    shape alone.
    """
    from services.project_access import load_authorized_project_or_none

    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    result = load_authorized_project_or_none(
        store, get_registry(current_app), get_governance_log(current_app), project_id,
        session.get("username"), is_admin(),
    )
    if result is None:
        abort(404)
    return result


@api_bp.route('/documents', methods=['GET'])
def list_documents():
    # CLAUDE-P32: filtered to accessible projects only -- listing every
    # project_id in the deployment regardless of access would leak
    # exactly what the per-project gate below is meant to hide.
    from services.project_access import can_access_project

    registry = get_registry(current_app)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    username = session.get("username")
    admin = is_admin()
    accessible = [
        pid for pid in registry.list_ids()
        if can_access_project(store.get_or_create(pid), username, admin)
    ]
    return jsonify(project_ids=accessible)


@api_bp.route('/documents/<project_id>', methods=['GET'])
def get_document(project_id):
    document, _workspace = _load_authorized_project_or_404(project_id)
    return jsonify(document.to_dict())


@api_bp.route('/documents/<project_id>/requirements', methods=['GET'])
def get_requirements(project_id):
    document, _workspace = _load_authorized_project_or_404(project_id)

    category = request.args.get('category')
    if category and category not in REQUIREMENT_CATEGORIES:
        return jsonify(
            error="invalid_category",
            message=f"'{category}' is not a known category.",
            valid_categories=REQUIREMENT_CATEGORIES,
        ), 400

    requirements = document.requirements
    if category:
        requirements = [r for r in requirements if r.category == category]

    return jsonify(requirements=[r.__dict__ for r in requirements])


@api_bp.route('/documents/<project_id>/milestones', methods=['GET'])
def get_milestones(project_id):
    document, _workspace = _load_authorized_project_or_404(project_id)
    return jsonify(milestones=document.milestones)


@api_bp.route('/documents/<project_id>/consistency', methods=['GET'])
def get_consistency(project_id):
    document, _workspace = _load_authorized_project_or_404(project_id)
    return jsonify(
        checked=document.consistency_checked,
        note=document.consistency_note,
        flags=[f.__dict__ for f in document.consistency_flags],
    )


@api_bp.route('/documents/<project_id>/governance', methods=['GET'])
def get_governance(project_id):
    _document, _workspace = _load_authorized_project_or_404(project_id)
    events = get_governance_log(current_app).read(project_id)
    return jsonify(events=[e.__dict__ for e in events])


# -- CLAUDE-MM1: Multimodal Foundation and Evidence Contract -----------------
# A tightly bounded diagnostic read surface proving the evidence contract is
# reachable through the application's existing JSON API - not a new UI
# (Part 12's own explicit instruction). Read-only; every write path stays a
# direct CaseWorkspaceStore call (services/case_workspace.py), the same as
# every other MM1 method - no route in this file mutates evidence-contract
# state this stage.

@api_bp.route('/documents/<project_id>/structural-units', methods=['GET'])
def list_structural_units(project_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    source_id = request.args.get('source_id')
    if source_id:
        units = store.structural_units_for_source(workspace, source_id)
    else:
        units = workspace.structural_units
    return jsonify(structural_units=units)


@api_bp.route('/documents/<project_id>/evidence', methods=['GET'])
def list_evidence_items(project_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    source_id = request.args.get('source_id')
    if source_id:
        items = store.evidence_items_for_source(workspace, source_id)
    else:
        items = workspace.evidence_items
    return jsonify(evidence_items=items)


@api_bp.route('/documents/<project_id>/citations/<region_id>', methods=['GET'])
def get_region_citation(project_id, region_id):
    """
    Resolves an AddressableRegion into the citation contract's own
    human-readable rendering (Section 7) - `{"status": "resolved", ...}`
    or the honest `{"status": "unavailable", ...}` broken-anchor state,
    never a 404/500 for a region that simply no longer resolves (that
    would conflate "this region id was never real/not in this project"
    with "this region existed but its Source is currently unavailable" -
    two different facts callers need to distinguish).
    """
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return jsonify(store.resolve_region_citation(workspace, region_id))


# -- CLAUDE-MM2: PDF and Document Intelligence -------------------------------
# The one write path this stage adds - triggers a real PDF read (services/
# pdf_intelligence.py) and registers the result as governed MM1 evidence.
# Admin-gated (_ADMIN_ONLY_ENDPOINTS above), the same authority level
# services/ingestion.py's own ingest_document already uses for anything
# that creates governed project records from a file.

@api_bp.route('/documents/<project_id>/sources/<source_id>/pdf-structure', methods=['POST'])
def register_pdf_structure(project_id, source_id):
    """
    Reads the named Source's own already-persisted PDF bytes and registers
    page StructuralUnits + paragraph AddressableRegions/EvidenceItems.
    Idempotent only in the sense that calling it twice creates two
    independent sets of records (no dedup) - matching register_table_
    evidence's own precedent (Batch J) of leaving re-registration
    detection to a future stage, not silently guessing intent here.
    """
    from services.pdf_intelligence import PdfIntelligenceError, register_pdf_evidence_for_source

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    try:
        result = register_pdf_evidence_for_source(
            store, workspace, source_id, actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except PdfIntelligenceError as exc:
        return jsonify(error="invalid_source", message=str(exc)), 400
    return jsonify(result), 201


# -- CLAUDE-MM3: Spreadsheet and Structured-Data Intelligence ---------------
# Two write paths, both admin-gated (_ADMIN_ONLY_ENDPOINTS above): the
# read/classify/register trigger (mirrors pdf-structure exactly) and the
# one bounded single-cell edit this stage implements (services/
# spreadsheet_intelligence.py's own explicit, narrow restrictions - no
# formula editing, concurrency-checked via expected_file_hash).

@api_bp.route('/documents/<project_id>/sources/<source_id>/spreadsheet-structure', methods=['POST'])
def register_spreadsheet_structure_route(project_id, source_id):
    from services.spreadsheet_intelligence import (
        SpreadsheetIntelligenceError, register_spreadsheet_evidence_for_source,
    )

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    try:
        result = register_spreadsheet_evidence_for_source(
            store, workspace, source_id, actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except SpreadsheetIntelligenceError as exc:
        return jsonify(error="invalid_source", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/sources/<source_id>/spreadsheet-cell', methods=['POST'])
def edit_spreadsheet_cell(project_id, source_id):
    """
    JSON body: `{"sheet_name", "cell_ref", "value", "expected_file_hash"}`
    (the last optional, but recommended - see apply_bounded_cell_edit's
    own docstring on the race it closes). Every rejection reason (not a
    Source, not .xlsx, formula cell, stale hash, bad cell reference) comes
    back as the same `error="invalid_edit"` shape with a human-readable
    `message` - never a raw traceback, never a partial/corrupted write.
    """
    from services.spreadsheet_intelligence import SpreadsheetIntelligenceError, apply_bounded_cell_edit

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    sheet_name = body.get('sheet_name')
    cell_ref = body.get('cell_ref')
    value = body.get('value')
    if not sheet_name or not cell_ref:
        return jsonify(error="invalid_edit", message="'sheet_name' and 'cell_ref' are required."), 400
    try:
        result = apply_bounded_cell_edit(
            store, workspace, source_id, sheet_name=sheet_name, cell_ref=cell_ref, new_value=value,
            expected_file_hash=body.get('expected_file_hash'),
            actor=session.get('username', 'system'), governance_log=get_governance_log(current_app),
        )
    except SpreadsheetIntelligenceError as exc:
        return jsonify(error="invalid_edit", message=str(exc)), 400
    return jsonify(result), 200


# -- CLAUDE-MM4: Drawing Intelligence and Orientation-Normalized Comparison -
# Two write paths (admin-gated, _ADMIN_ONLY_ENDPOINTS below): the read/
# classify/register trigger (mirrors pdf-structure/spreadsheet-structure
# exactly) and the bounded region-creation path (Section 4/6 - "select or
# define an addressable drawing region; create direct evidence anchored to
# that region"). The evidence-sachet route is read-only and NOT admin-
# gated, matching get_region_citation's own authority level - assembling
# an already-governed evidence packet for an authenticated project member
# to inspect is not a write.

@api_bp.route('/documents/<project_id>/sources/<source_id>/drawing-structure', methods=['POST'])
def register_drawing_structure(project_id, source_id):
    """
    Reads the named Source's own already-persisted drawing bytes (a
    drawing-oriented .pdf or a standalone .png/.jpg/.jpeg) and registers
    one StructuralUnit per sheet. Idempotent only in the sense that
    calling it twice creates two independent sets of records (no dedup) -
    matching register_pdf_structure/register_spreadsheet_structure_route's
    own precedent above.
    """
    from services.drawing_intelligence import DrawingIntelligenceError, register_drawing_evidence_for_source

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    try:
        result = register_drawing_evidence_for_source(
            store, workspace, source_id, actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except DrawingIntelligenceError as exc:
        return jsonify(error="invalid_source", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/sources/<source_id>/drawing-regions', methods=['POST'])
def create_drawing_region(project_id, source_id):
    """
    JSON body: `{"structural_unit_id", "x", "y", "width", "height",
    "note"}` - x/y/width/height are normalized 0-1 fractions of the
    sheet's own ORIGINAL (unrotated, unmirrored) width/height; a caller
    driving this from a transformed on-screen selection is responsible
    for converting first (services/drawing_intelligence.py's own
    transform_rect_to_original). `note` is optional free text.
    """
    from services.drawing_intelligence import DrawingIntelligenceError, create_drawing_region_and_evidence

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    structural_unit_id = body.get('structural_unit_id')
    if not structural_unit_id:
        return jsonify(error="invalid_region", message="'structural_unit_id' is required."), 400
    try:
        x, y, width, height = (float(body.get(k)) for k in ('x', 'y', 'width', 'height'))
    except (TypeError, ValueError):
        return jsonify(error="invalid_region", message="'x'/'y'/'width'/'height' must all be numbers."), 400
    try:
        result = create_drawing_region_and_evidence(
            store, workspace, source_id, structural_unit_id, x=x, y=y, width=width, height=height,
            note=body.get('note'), actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except DrawingIntelligenceError as exc:
        return jsonify(error="invalid_region", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/regions/<region_id>/evidence-sachet', methods=['GET'])
def get_evidence_sachet(project_id, region_id):
    """
    Section 14: the Governed Evidence Sachet - a read-time-assembled,
    allow-listed evidence packet for ONE region (its sheet, its sibling
    regions on that same sheet, its citation, its Source's own
    sensitivity), never the whole drawing set or the whole project. See
    CaseWorkspaceStore.build_evidence_sachet's own docstring for the full
    contract. `?task=` is optional free text carried through unchanged.
    """
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    sachet = store.build_evidence_sachet(workspace, region_id, task_description=request.args.get('task'))
    return jsonify(sachet)


@api_bp.route('/documents/<project_id>/rfi', methods=['GET'])
def export_rfi(project_id):
    document, workspace = _load_authorized_project_or_404(project_id)
    environment_label = OPERATING_ENVIRONMENT_LABELS.get(workspace.operating_environment)

    try:
        buffer = build_rfi_docx(document, operating_environment_label=environment_label)
    except RFIExportError as exc:
        return jsonify(error="nothing_to_export", message=str(exc)), 409

    return send_file(
        buffer,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name=f"RFI-{project_id}.docx",
    )


@api_bp.route('/categories', methods=['GET'])
def list_categories():
    return jsonify(categories=REQUIREMENT_CATEGORIES)
