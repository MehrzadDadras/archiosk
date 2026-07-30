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


def _reject_if_name_taken(app: Flask, entry_name: str) -> None:
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
    if entry_name in existing_names:
        raise UploadError("Entry names must be unique.")


def _find_duplicate_content(app: Flask, file_hash: str) -> Optional[str]:
    """
    CLAUDE-P28: original_file_hash (SHA-256) was already computed and
    stored on every ingestion (below) but never actually checked against
    anything -- this closes that gap. Returns the project_id of an
    existing project whose original upload has the identical content, or
    None. Deliberately informational, not a hard reject like
    _reject_if_name_taken above: uploading the same source document into
    a second, genuinely separate project is a legitimate real workflow
    (e.g. a shared boilerplate/reference document), not necessarily a
    mistake -- the caller decides what to do with this (see
    ingest_upload's governance-log entry), it doesn't block the upload.
    """
    registry = get_registry(app)
    for pid in registry.list_ids():
        document = registry.get(pid)
        if document is not None and document.original_file_hash == file_hash:
            return pid
    return None


def document_source_payload(document: ParsedDocument) -> dict:
    """
    The register_document_source payload CaseWorkspaceStore.get_or_create
    expects - shared here so ingest_upload (naming a project at creation
    time) and routes/workspace.py's _load_workspace_or_404 (opening a
    Case Workspace for the first time) build the identical dict from one
    place, not two independently-drifting copies.
    """
    return {
        "filename": document.filename,
        "ingested_at": document.ingested_at,
        "requirement_count": len(document.requirements),
        "milestone_count": len(document.milestones),
        "file_path": document.original_file_path,
        "file_hash": document.original_file_hash,
    }


def ingest_upload(
    file_storage: Optional[FileStorage],
    app: Flask,
    actor: str | None = None,
    role: str | None = None,
    project_name: str | None = None,
) -> ParsedDocument:
    """
    Validate, parse, and persist an uploaded RFP/RFQ. Raises UploadError
    on bad input. `project_name`, if given, becomes the project's
    display_title (its visible identity everywhere - sidebar, Projects
    directory, Dashboard, Case Workspace) instead of leaving it as
    whichever filename happened to be uploaded - see pagescape correction
    #11. Optional and backward-compatible: omitted, the project's
    identity is exactly what it always was, the filename.
    """
    if file_storage is None or not file_storage.filename:
        raise UploadError("No file was provided.")

    filename = file_storage.filename
    ext = Path(filename).suffix.lower()
    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    if ext not in allowed:
        raise UploadError(
            f"Unsupported file type '{ext}'. Allowed types: {', '.join(sorted(allowed))}."
        )

    project_name = (project_name or "").strip() or None
    _reject_if_name_taken(app, project_name or filename)

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

    # Checked before this document is saved to the registry (so it can
    # never match itself) -- informational only, see _find_duplicate_content.
    duplicate_of_project_id = _find_duplicate_content(app, document.original_file_hash)

    get_registry(app).save(document)
    governance_log = get_governance_log(app)
    governance_log.append(
        project_id=document.project_id,
        event_type="document_ingested",
        actor=actor or _DEFAULT_ACTOR,
        role=role or _DEFAULT_ROLE,
        payload={
            "filename": document.filename,
            "requirement_count": len(document.requirements),
            "milestone_count": len(document.milestones),
            "duplicate_of_project_id": duplicate_of_project_id,
        },
    )

    if project_name:
        # Creates the Case Workspace eagerly (idempotent - the same
        # get_or_create routes/workspace.py's _load_workspace_or_404 calls
        # on first open; finding it already exists there is the normal,
        # expected case, not a conflict) purely so the chosen name is set
        # from the very first moment the project exists, not left showing
        # the filename until someone happens to open Case Workspace and
        # use Edit Project Details.
        store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
        workspace = store.get_or_create(
            document.project_id, register_document_source=document_source_payload(document),
        )
        store.set_project_details(
            workspace, actor=actor or _DEFAULT_ACTOR, display_title=project_name,
            governance_log=governance_log,
        )

    return document
