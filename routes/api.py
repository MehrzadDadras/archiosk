"""
JSON API for the B-Hive document pipeline (mounted at /api/v1).
"""
from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file
from werkzeug.exceptions import RequestEntityTooLarge

from services.bhive_parser import REQUIREMENT_CATEGORIES
from services.ingestion import UploadError, get_registry, ingest_upload
from services.rfi_export import RFIExportError, build_rfi_docx

api_bp = Blueprint('api', __name__)


@api_bp.errorhandler(RequestEntityTooLarge)
def _file_too_large(_err):
    max_mb = current_app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify(
        error="file_too_large",
        message=f"Upload exceeds the {max_mb}MB limit.",
    ), 413


@api_bp.route('/documents/ingest', methods=['POST'])
def ingest_document():
    try:
        document = ingest_upload(request.files.get('file'), current_app)
    except UploadError as exc:
        return jsonify(error="invalid_upload", message=str(exc)), 400

    return jsonify(document.to_dict()), 201


@api_bp.route('/documents', methods=['GET'])
def list_documents():
    registry = get_registry(current_app)
    return jsonify(project_ids=registry.list_ids())


@api_bp.route('/documents/<project_id>', methods=['GET'])
def get_document(project_id):
    document = get_registry(current_app).get(project_id)
    if document is None:
        return _not_found(project_id)
    return jsonify(document.to_dict())


@api_bp.route('/documents/<project_id>/requirements', methods=['GET'])
def get_requirements(project_id):
    document = get_registry(current_app).get(project_id)
    if document is None:
        return _not_found(project_id)

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
    document = get_registry(current_app).get(project_id)
    if document is None:
        return _not_found(project_id)
    return jsonify(milestones=document.milestones)


@api_bp.route('/documents/<project_id>/consistency', methods=['GET'])
def get_consistency(project_id):
    document = get_registry(current_app).get(project_id)
    if document is None:
        return _not_found(project_id)
    return jsonify(
        checked=document.consistency_checked,
        note=document.consistency_note,
        flags=[f.__dict__ for f in document.consistency_flags],
    )


@api_bp.route('/documents/<project_id>/rfi', methods=['GET'])
def export_rfi(project_id):
    document = get_registry(current_app).get(project_id)
    if document is None:
        return _not_found(project_id)

    try:
        buffer = build_rfi_docx(document)
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


def _not_found(project_id: str):
    return jsonify(
        error="not_found",
        message=f"No document found for project_id '{project_id}'.",
    ), 404
