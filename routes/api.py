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

from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, request, send_file, session
from werkzeug.exceptions import RequestEntityTooLarge

from services.auth import is_admin, is_authenticated
from services.bhive_parser import REQUIREMENT_CATEGORIES
from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore
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
    "api.save_eye_capture", "api.create_image_marker", "api.export_derivative_crop",
    "api.create_document_snapshot",
    "api.create_relationship", "api.confirm_relationship_route", "api.dispute_relationship_route",
    "api.reject_relationship_route", "api.supersede_relationship_route",
    "api.create_investigation", "api.accept_claim_as_observation", "api.accept_claim_as_finding",
    "api.dispute_claim_route", "api.reject_claim_route", "api.request_claim_specialist_route",
    "api.request_claim_authority_route", "api.supersede_claim_route",
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


# -- CLAUDE-MM5: Image, Screenshot, and Camera Evidence ---------------------
# Three write paths (all admin-gated, _ADMIN_ONLY_ENDPOINTS above): Eye's
# own "Save to project" action (creates a brand-new Source, unlike MM2-MM4's
# own structure-registration routes which all act on an ALREADY-uploaded
# Source), a point-marker annotation (Section 13), and a derivative-crop
# export (Section 12).

@api_bp.route('/documents/<project_id>/eye-capture', methods=['POST'])
def save_eye_capture(project_id):
    """
    Multipart body: `image` (the file field), optional `description`
    (free text, becomes a EVIDENCE_CLASS_USER_ENTERED EvidenceItem
    anchored to the new Source). Section 17: content is validated by
    Pillow BEFORE any file is written to disk or any Source record is
    created - a refused image never leaves a trace.
    """
    from services.image_intelligence import register_eye_capture

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    file_storage = request.files.get('image')
    if file_storage is None or not file_storage.filename:
        return jsonify(error="invalid_image", message="An 'image' file is required."), 400

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    result = register_eye_capture(
        store, workspace, raw_bytes=file_storage.read(), filename=file_storage.filename,
        description=request.form.get('description'), sources_dir=sources_dir,
        actor=session.get('username', 'system'), governance_log=get_governance_log(current_app),
    )
    if result["classification"] != "supported":
        return jsonify(error="invalid_image", message=f"This image was refused: {result['classification']}.",
                       classification=result["classification"]), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/sources/<source_id>/snapshot', methods=['POST'])
def create_document_snapshot(project_id, source_id):
    """
    CLAUDE-SNAPSHOT-DUAL-SURFACE-01: `<source_id>` is the PARENT Document
    being captured - the caller (static/js/pdf_viewer.js's own
    takeSnapshot(), called via whichever surface, Main or Eye, currently
    owns the shared toolbar) already resolved which document/page that
    is BEFORE this request is made; this route never infers it from rail
    selection or "last opened."

    JSON body: `{"image": "data:image/png;base64,...", "page": <int|null>}`
    - a rendered-canvas capture, not a raw file upload, so no `request.
    files` multipart handling (contrast with save_eye_capture above).
    """
    import base64

    from services.image_intelligence import ImageIntelligenceError, register_document_snapshot

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    data_url = body.get('image')
    if not data_url or not isinstance(data_url, str) or ';base64,' not in data_url:
        return jsonify(error="invalid_image", message="An 'image' data URL is required."), 400
    page = body.get('page')
    if page is not None:
        try:
            page = int(page)
        except (TypeError, ValueError):
            return jsonify(error="invalid_page", message="'page' must be an integer when given."), 400
    try:
        raw_bytes = base64.b64decode(data_url.split(';base64,', 1)[1], validate=True)
    except (ValueError, TypeError):
        return jsonify(error="invalid_image", message="'image' was not valid base64."), 400

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    try:
        result = register_document_snapshot(
            store, workspace, parent_source_id=source_id, page_number=page, raw_bytes=raw_bytes,
            sources_dir=sources_dir, actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except ImageIntelligenceError as exc:
        return jsonify(error="invalid_snapshot", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/sources/<source_id>/markers', methods=['POST'])
def create_image_marker(project_id, source_id):
    """JSON body: `{"structural_unit_id", "x", "y", "note"}` - Section 13's
    one bounded annotation type, a point marker with a required short
    text note."""
    from services.image_intelligence import ImageIntelligenceError, create_marker_and_evidence

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    structural_unit_id = body.get('structural_unit_id')
    note = body.get('note')
    if not structural_unit_id or not note:
        return jsonify(error="invalid_marker", message="'structural_unit_id' and 'note' are required."), 400
    try:
        x, y = float(body.get('x')), float(body.get('y'))
    except (TypeError, ValueError):
        return jsonify(error="invalid_marker", message="'x'/'y' must both be numbers."), 400
    try:
        result = create_marker_and_evidence(
            store, workspace, source_id, structural_unit_id, x=x, y=y, note=note,
            actor=session.get('username', 'system'), governance_log=get_governance_log(current_app),
        )
    except ImageIntelligenceError as exc:
        return jsonify(error="invalid_marker", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/sources/<source_id>/derivative-crop', methods=['POST'])
def export_derivative_crop(project_id, source_id):
    """JSON body: `{"region_id"}` - crops the ORIGINAL image at that
    region's already-stored, original-frame coordinates and registers the
    result as a new, EXIF-free derivative Source (Section 12/10)."""
    from services.image_intelligence import ImageIntelligenceError, extract_bounded_crop

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    region_id = body.get('region_id')
    if not region_id:
        return jsonify(error="invalid_crop", message="'region_id' is required."), 400

    sources_dir = Path(current_app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    try:
        result = extract_bounded_crop(
            store, workspace, source_id, region_id, sources_dir=sources_dir,
            actor=session.get('username', 'system'), governance_log=get_governance_log(current_app),
        )
    except ImageIntelligenceError as exc:
        return jsonify(error="invalid_crop", message=str(exc)), 400
    return jsonify(result), 201


# -- CLAUDE-MM6: Cross-Document and Cross-Modal Relationship River ----------
# Write paths (admin-gated, _ADMIN_ONLY_ENDPOINTS below): create, confirm,
# dispute, reject, supersede. Read paths (not admin-gated, matching the
# citation/evidence-sachet routes' own authority level - inspecting
# already-governed relationships is not a write): list-for-object, resolve
# status, the relationship evidence sachet, and the evidence trust
# explanation.

@api_bp.route('/documents/<project_id>/relationships', methods=['POST'])
def create_relationship(project_id):
    """
    JSON body: `{"from_type", "from_id", "to_type", "to_id",
    "relationship_type", "reason", "provisional", "confidence"}` -
    `from_type`/`to_type` are validated against the MM1-MM5 evidence-
    contract object kinds this stage supports (see CaseWorkspaceStore.
    _MM6_ENDPOINT_LISTS); both endpoints must already exist in THIS
    project or the request is refused (Section 6/16 - "do not permit
    arbitrary cross-project endpoints"). `provisional` defaults to True
    (Section 20: "AI may propose a link but must not silently establish
    it as governed fact") - pass `provisional: false` only for a genuine,
    immediate human-confirmed link.
    """
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    required = ('from_type', 'from_id', 'to_type', 'to_id', 'relationship_type')
    if any(not body.get(field) for field in required):
        return jsonify(error="invalid_relationship", message="'from_type'/'from_id'/'to_type'/'to_id'/'relationship_type' are all required."), 400
    try:
        relationship = store.record_evidence_relationship(
            workspace, from_type=body['from_type'], from_id=body['from_id'],
            to_type=body['to_type'], to_id=body['to_id'], relationship_type=body['relationship_type'],
            reason=body.get('reason'), created_by=session.get('username', 'system'),
            provisional=body.get('provisional', True), confidence=body.get('confidence'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_relationship", message=str(exc)), 400
    return jsonify(relationship), 201


@api_bp.route('/documents/<project_id>/relationships', methods=['GET'])
def list_relationships(project_id):
    """`?object_type=&object_id=&direction=from|to|both` (default both)."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    object_type = request.args.get('object_type')
    object_id = request.args.get('object_id')
    if not object_type or not object_id:
        return jsonify(error="invalid_query", message="'object_type' and 'object_id' are both required."), 400
    direction = request.args.get('direction', 'both')
    relationships = store.relationships_for(workspace, object_type, object_id, direction=direction)
    return jsonify(relationships=relationships)


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/status', methods=['GET'])
def get_relationship_status(project_id, relationship_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return jsonify(store.resolve_relationship_status(workspace, relationship_id))


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/confirm', methods=['POST'])
def confirm_relationship_route(project_id, relationship_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    try:
        relationship = store.confirm_relationship(
            workspace, relationship_id, actor=session.get('username', 'system'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_relationship", message=str(exc)), 400
    return jsonify(relationship), 200


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/dispute', methods=['POST'])
def dispute_relationship_route(project_id, relationship_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        relationship = store.dispute_relationship(
            workspace, relationship_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_relationship", message=str(exc)), 400
    return jsonify(relationship), 200


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/reject', methods=['POST'])
def reject_relationship_route(project_id, relationship_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        relationship = store.reject_relationship(
            workspace, relationship_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_relationship", message=str(exc)), 400
    return jsonify(relationship), 200


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/supersede', methods=['POST'])
def supersede_relationship_route(project_id, relationship_id):
    """JSON body: `{"to_type", "to_id", "relationship_type", "reason",
    "from_type", "from_id"}` - `from_type`/`from_id` optional, defaulting
    to the original relationship's own FROM endpoint (Section 15)."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    required = ('to_type', 'to_id', 'relationship_type', 'reason')
    if any(not body.get(field) for field in required):
        return jsonify(error="invalid_relationship", message="'to_type'/'to_id'/'relationship_type'/'reason' are all required."), 400
    try:
        result = store.supersede_relationship(
            workspace, relationship_id, to_type=body['to_type'], to_id=body['to_id'],
            relationship_type=body['relationship_type'], reason=body['reason'],
            actor=session.get('username', 'system'), from_type=body.get('from_type'), from_id=body.get('from_id'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_relationship", message=str(exc)), 400
    return jsonify(result), 201


@api_bp.route('/documents/<project_id>/relationships/<relationship_id>/sachet', methods=['GET'])
def get_relationship_sachet(project_id, relationship_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    sachet = store.build_relationship_sachet(workspace, relationship_id, task_description=request.args.get('task'))
    return jsonify(sachet)


@api_bp.route('/documents/<project_id>/evidence/<evidence_item_id>/trust', methods=['GET'])
def get_evidence_trust(project_id, evidence_item_id):
    """The Trustworthy Answer Contract's own 'Why should I trust this?'
    endpoint (Section 10)."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return jsonify(store.explain_evidence_trust(workspace, evidence_item_id))


# -- CLAUDE-MM7: Governed Investigation, Analytical Reasoning, and ----------
# Trustworthy Answers. Write paths (admin-gated, _ADMIN_ONLY_ENDPOINTS
# above): create an investigation, adopt a claim as observation/Finding,
# dispute/reject a claim, request specialist/authority review, supersede a
# claim. Read paths (not admin-gated, matching the relationship/evidence-
# trust routes' own authority level): the Trustworthy Answer Contract /
# "Why should I trust this?" payload, the investigation evidence sachet, and
# one claim's own resolved status.

@api_bp.route('/documents/<project_id>/investigations', methods=['POST'])
def create_investigation(project_id):
    """
    JSON body: `{"question", "case_id", "anchor_object_type",
    "anchor_object_id", "unresolvable_aspects"?}` - runs a real,
    deterministic cross-modal investigation (services/cross_modal_
    investigation.py) anchored on an already-governed MM1-MM6 object,
    walking every real Relationship it participates in and recording
    one Claim per contradiction/stale-endpoint/ordinary-support found
    (Section 19). `unresolvable_aspects` is an optional list of things
    this question touches that no evidence in this project could
    settle - each becomes its own honest abstention claim (Section 8).
    """
    from services.cross_modal_investigation import CrossModalInvestigationError, investigate_cross_modal_question

    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    required = ('question', 'case_id', 'anchor_object_type', 'anchor_object_id')
    if any(not body.get(field) for field in required):
        return jsonify(
            error="invalid_investigation",
            message="'question'/'case_id'/'anchor_object_type'/'anchor_object_id' are all required.",
        ), 400
    try:
        result = investigate_cross_modal_question(
            store, workspace, question=body['question'], case_id=body['case_id'],
            anchor_object_type=body['anchor_object_type'], anchor_object_id=body['anchor_object_id'],
            actor=session.get('username', 'system'), unresolvable_aspects=body.get('unresolvable_aspects'),
            governance_log=get_governance_log(current_app),
        )
    except CrossModalInvestigationError as exc:
        return jsonify(error="invalid_investigation", message=str(exc)), 400
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_investigation", message=str(exc)), 400
    return jsonify({
        "investigation_step": result["investigation_step"],
        "claim_ids": result["claim_ids"],
    }), 201


@api_bp.route('/documents/<project_id>/investigations/<investigation_step_id>/answer', methods=['GET'])
def get_investigation_answer(project_id, investigation_step_id):
    """The Trustworthy Answer Contract AND 'Why should I trust this?'
    payload (Section 5/6) - one assembly serving both."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return jsonify(store.explain_investigation_answer(workspace, investigation_step_id))


@api_bp.route('/documents/<project_id>/investigations/<investigation_step_id>/sachet', methods=['GET'])
def get_investigation_sachet(project_id, investigation_step_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    sachet = store.build_investigation_evidence_sachet(workspace, investigation_step_id, task_description=request.args.get('task'))
    return jsonify(sachet)


@api_bp.route('/documents/<project_id>/claims/<claim_id>/status', methods=['GET'])
def get_claim_status(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    return jsonify(store.resolve_claim_status(workspace, claim_id))


@api_bp.route('/documents/<project_id>/claims/<claim_id>/accept-observation', methods=['POST'])
def accept_claim_as_observation(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        result = store.accept_claim_as_observation(
            workspace, claim_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(result), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/accept-finding', methods=['POST'])
def accept_claim_as_finding(project_id, claim_id):
    """JSON body: `{"case_id", "reason"?}` - `case_id` required since
    Finding remains Case-scoped everywhere else in this codebase."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    if not body.get('case_id'):
        return jsonify(error="invalid_claim", message="'case_id' is required."), 400
    try:
        result = store.accept_claim_as_finding(
            workspace, claim_id, actor=session.get('username', 'system'), case_id=body['case_id'],
            reason=body.get('reason'), governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(result), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/dispute', methods=['POST'])
def dispute_claim_route(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        claim = store.dispute_claim(
            workspace, claim_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(claim), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/reject', methods=['POST'])
def reject_claim_route(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        claim = store.reject_claim(
            workspace, claim_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(claim), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/request-specialist', methods=['POST'])
def request_claim_specialist_route(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        claim = store.request_claim_specialist_review(
            workspace, claim_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(claim), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/request-authority', methods=['POST'])
def request_claim_authority_route(project_id, claim_id):
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    try:
        claim = store.request_claim_authority(
            workspace, claim_id, actor=session.get('username', 'system'), reason=body.get('reason'),
            governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(claim), 200


@api_bp.route('/documents/<project_id>/claims/<claim_id>/supersede', methods=['POST'])
def supersede_claim_route(project_id, claim_id):
    """JSON body: `{"statement", "claim_class", "method",
    "confidence_state", "author_type", "reason", "evidence_links"?}` -
    `evidence_links` optional, defaulting to the original claim's own
    (Section 16: a correction may keep the same evidence and only
    change the statement/classification, or supply new evidence)."""
    _document, workspace = _load_authorized_project_or_404(project_id)
    store = CaseWorkspaceStore(current_app.config["REGISTRY_STORE_PATH"])
    body = request.get_json(silent=True) or {}
    required = ('statement', 'claim_class', 'method', 'confidence_state', 'author_type', 'reason')
    if any(not body.get(field) for field in required):
        return jsonify(
            error="invalid_claim",
            message="'statement'/'claim_class'/'method'/'confidence_state'/'author_type'/'reason' are all required.",
        ), 400
    try:
        result = store.supersede_claim(
            workspace, claim_id, statement=body['statement'], claim_class=body['claim_class'],
            method=body['method'], confidence_state=body['confidence_state'], author_type=body['author_type'],
            reason=body['reason'], actor=session.get('username', 'system'),
            evidence_links=body.get('evidence_links'), governance_log=get_governance_log(current_app),
        )
    except CaseWorkspaceError as exc:
        return jsonify(error="invalid_claim", message=str(exc)), 400
    return jsonify(result), 201


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
