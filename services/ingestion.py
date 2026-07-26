"""
Shared upload-handling glue between routes/api.py and routes/portal.py.

Both blueprints accept an uploaded RFP/RFQ and need the same validate ->
parse -> save sequence, so it lives here once rather than being
duplicated (and drifting) across a JSON endpoint and an HTML form handler.
"""
from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.bhive_parser import BHiveParser, ParsedDocument, ParserError
from services.case_workspace import CaseWorkspaceStore
from services.governance import GovernanceLog
from services.requirements_registry import RequirementsRegistry

# This app has no authentication system, so there's no real identity to
# fall back on. These are honest placeholders, not a claim that anyone
# was actually verified -- see services/governance.py.
_DEFAULT_ACTOR = "anonymous"
_DEFAULT_ROLE = "unspecified"


class UploadError(Exception):
    """Raised for invalid uploads (missing file, bad extension, unparsable content)."""


def get_registry(app: Flask) -> RequirementsRegistry:
    return RequirementsRegistry(app.config["REGISTRY_STORE_PATH"])


def get_governance_log(app: Flask) -> GovernanceLog:
    # Same store as the registry -- one .governance.jsonl file per project
    # alongside that project's .json record.
    return GovernanceLog(app.config["REGISTRY_STORE_PATH"])


def _display_name_of(document: ParsedDocument, store: CaseWorkspaceStore) -> str:
    """
    A project's effective visible identity - its own display_title once a
    human has set one (see CaseWorkspaceStore.set_project_details), else
    the filename it was ingested under. A workspace file that predates the
    current schema must not block every future upload; degrades to the
    plain filename for that one project rather than raising.
    """
    try:
        workspace = store.get(document.project_id)
    except TypeError:
        workspace = None
    return (workspace.display_title if workspace else None) or document.filename


def _reject_if_name_taken(app: Flask, filename: str) -> None:
    """
    Project Entry Rule: entry names must be unique. Checked against every
    existing project's current effective display name (not just raw
    filenames) so a name collision is caught even if the earlier project
    was later given a custom display_title matching the new upload.
    """
    registry = get_registry(app)
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    existing_names = {
        _display_name_of(document, store)
        for pid in registry.list_ids()
        if (document := registry.get(pid)) is not None
    }
    if filename in existing_names:
        raise UploadError("Entry names must be unique.")


def ingest_upload(
    file_storage: Optional[FileStorage],
    app: Flask,
    actor: str | None = None,
    role: str | None = None,
) -> ParsedDocument:
    """Validate, parse, and persist an uploaded RFP/RFQ. Raises UploadError on bad input."""
    if file_storage is None or not file_storage.filename:
        raise UploadError("No file was provided.")

    filename = file_storage.filename
    ext = Path(filename).suffix.lower()
    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    if ext not in allowed:
        raise UploadError(
            f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(allowed))}."
        )

    _reject_if_name_taken(app, filename)

    raw_bytes = file_storage.read()
    parser = BHiveParser(
        anthropic_api_key=app.config.get("ANTHROPIC_API_KEY"),
        model=app.config.get("ANTHROPIC_MODEL"),
    )
    try:
        document = parser.parse(raw_bytes, filename)
    except ParserError as exc:
        raise UploadError(str(exc)) from exc

    # Persist the ORIGINAL uploaded bytes, not just what the parser
    # extracted from them - the same "a Source is not its filename"
    # discipline routes/workspace.py already applies to governed drawing/
    # document Sources (opaque-prefixed name, original kept only as the
    # display label). Written into the same workspace_sources/<project_id>
    # directory Case Workspace's own add_document_source already uses, so
    # there is one storage location for every project-held file, legacy
    # or governed. Written only after a successful parse, matching the
    # existing behavior of leaving nothing behind on a failed parse.
    sources_dir = Path(app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / document.project_id
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(filename)
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
    stored_path.write_bytes(raw_bytes)
    document.original_file_path = str(stored_path)
    document.original_file_hash = hashlib.sha256(raw_bytes).hexdigest()

    get_registry(app).save(document)
    get_governance_log(app).append(
        project_id=document.project_id,
        event_type="document_ingested",
        actor=actor or _DEFAULT_ACTOR,
        role=role or _DEFAULT_ROLE,
        payload={
            "filename": document.filename,
            "requirement_count": len(document.requirements),
            "milestone_count": len(document.milestones),
        },
    )
    return document
