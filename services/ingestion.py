"""
Shared upload-handling glue between routes/api.py and routes/portal.py.

Both blueprints accept an uploaded RFP/RFQ and need the same validate ->
parse -> save sequence, so it lives here once rather than being
duplicated (and drifting) across a JSON endpoint and an HTML form handler.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from flask import Flask
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from services.bhive_parser import BHiveParser, ParsedDocument, ParserError
from services.case_workspace import (
    FOLDER_ROOT_DATA_ROOM,
    SOURCE_KIND_PROJECT_DOCUMENT,
    SOURCE_ORIGIN_TYPE_UPLOAD,
    CaseWorkspaceStore,
)
from services.governance import GovernanceLog
from services.requirements_registry import RequirementsRegistry
from services.security_governance import SecurityGovernanceStore
from services.security_policy import ACTION_EXTERNAL_AI_REQUEST, DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE, evaluate_action

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


def reject_if_display_name_taken(app: Flask, entry_name: str, exclude_project_id: str) -> None:
    """
    CLAUDE-P40-B (3.1): the same uniqueness rule _reject_if_name_taken
    enforces at upload time, reused for post-ingestion renaming
    (routes/workspace.py's edit_project_details) - a real gap found
    during this stage's own investigation: renaming an existing Project
    via "Edit Project Details" never checked uniqueness at all, even
    though the identical name is rejected at upload time. Excludes the
    Project being renamed itself (renaming to its own current name, or
    leaving it unchanged, is never a collision). Public (no leading
    underscore) since it's now called from routes/workspace.py, unlike
    _reject_if_name_taken above which stays ingestion-internal.
    """
    registry = get_registry(app)
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    existing_names = {
        _display_name_of(document, store)
        for pid in registry.list_ids()
        if pid != exclude_project_id and (document := registry.get(pid)) is not None
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
    operating_environment: str,
    owner: str,
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

    `operating_environment` (CLAUDE-P29) is REQUIRED, deliberately no
    default -- every caller must explicitly decide, matching the
    product rule that a project cannot exist without one. Validated
    here, before anything is parsed or persisted, so an invalid/missing
    value behaves exactly like a missing file or a bad extension below:
    nothing is left behind. The workspace-creation block near the end
    of this function is what actually locks it onto the project, via
    CaseWorkspaceStore.set_operating_environment -- the one and only
    call site, since this function is the one and only place a project
    is ever created (see services/case_workspace.py's own comment on
    that method for why calling it here is always safe: this function
    always generates a brand-new project_id, so the workspace it
    creates a few lines below is always genuinely new).

    `owner` (CLAUDE-P32) is REQUIRED, deliberately no default and
    deliberately a SEPARATE parameter from `actor` below -- `actor` is
    free text (services/governance.py's own docstring: "No real
    authentication backs actor/role"; a real caller has typed things
    like "Mehrzad Dadras, Design Manager" into it), never safe to use as
    a security-relevant identity. `owner` must be the caller's real,
    already-authenticated `session['username']` (both real call sites,
    routes/portal.py's `upload()` and routes/api.py's `ingest_document()`,
    are `@admin_required` and so always have one) -- passed through to
    CaseWorkspaceStore.set_project_owner immediately after workspace
    creation, the same "locked onto the project at the moment of
    creation" treatment `operating_environment` already gets.
    """
    from services.environment_capabilities import is_valid_operating_environment

    if not is_valid_operating_environment(operating_environment):
        raise UploadError(
            "A valid project operating environment (Client / Owner or "
            "Design-Builder / Proponent) must be selected before a project can be created.",
        )

    if not owner or not owner.strip():
        raise UploadError("A project owner (the authenticated uploader) is required.")

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

    # CLAUDE-P31: the one real enforcement point for "external_ai_request"
    # -- no project exists yet at this moment (this function is the one
    # and only project-creation path), so only the organization-wide
    # baseline/exception apply here, never a project security profile.
    # Reuses BHiveParser's own pre-existing, already-tested kill switch
    # (self.ai_calls_disabled, CLAUDE-P27-B's AI_CALLS_DISABLED env var)
    # rather than adding a second, parallel gate inside bhive_parser.py
    # itself -- both classify() and _check_consistency() already degrade
    # to their existing rule-based/skipped fallback whenever this flag is
    # set, so denying here changes zero lines inside that module.
    security_store = SecurityGovernanceStore(app.config["REGISTRY_STORE_PATH"])
    security_record = security_store.get()
    active_baseline = security_store.active_baseline(security_record)
    ai_decision = evaluate_action(
        ACTION_EXTERNAL_AI_REQUEST,
        baseline_decision=(
            active_baseline["control_decisions"].get(ACTION_EXTERNAL_AI_REQUEST, {}).get("decision")
            if active_baseline else None
        ),
        baseline_version_id=active_baseline["id"] if active_baseline else None,
        active_exception=security_store.active_exception_for(security_record, ACTION_EXTERNAL_AI_REQUEST),
    )
    if ai_decision.decision not in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        parser.ai_calls_disabled = True

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
    # CLAUDE-P31: an audit event for the security decision itself,
    # regardless of outcome -- "denied actions generate audit events"
    # (Part XVII), and equally, an ALLOW decision is recorded so a
    # future self-check can distinguish "external AI ran with no
    # applicable policy" from "external AI ran and nothing was ever
    # evaluated at all."
    governance_log.append(
        project_id=document.project_id,
        event_type="security_decision",
        actor=actor or _DEFAULT_ACTOR,
        role="system",
        payload={
            "action_id": ai_decision.action_id,
            "decision": ai_decision.decision,
            "controlling_layer": ai_decision.controlling_layer,
            "baseline_version_id": ai_decision.baseline_version_id,
        },
    )

    # CLAUDE-P29: the Case Workspace is now ALWAYS created eagerly here
    # (previously only `if project_name:`), because operating_environment
    # has to be locked onto the project at the moment of creation, not
    # left until whoever happens to open Case Workspace first triggers
    # routes/workspace.py's own lazy get_or_create -- that call site has
    # no environment value to give it. Idempotent either way (the same
    # get_or_create that lazy-creation path uses); finding it already
    # exists there afterward is the normal, expected case, not a conflict.
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get_or_create(
        document.project_id, register_document_source=document_source_payload(document),
    )
    store.set_operating_environment(
        workspace, operating_environment, actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
    )
    # CLAUDE-RFP-BOUNDARY-01: lifecycle_stage's own initial-establishment
    # call, at the same project-creation call site operating_environment
    # is locked immediately above -- see ProjectWorkspace.lifecycle_stage's
    # own field comment for why this is a second, distinct method rather
    # than folded into set_operating_environment itself. This one call
    # site covers ingest_folder_upload too, since that function's own
    # founding file always goes through this same ingest_upload.
    store.set_initial_lifecycle_stage(
        workspace, actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
    )
    # CLAUDE-P32: locked onto the project at the moment of creation, the
    # same treatment operating_environment gets immediately above --
    # every new project has a real, deterministic owner from the moment
    # it exists, closing the gap for all future projects; only projects
    # that predate this field need the separate backfill-inference path
    # (services.project_access.ensure_owner_backfilled).
    store.set_project_owner(
        workspace, owner=owner.strip(), actor=owner.strip(), source="admin_assigned",
        governance_log=governance_log,
    )
    if project_name:
        store.set_project_details(
            workspace, actor=actor or _DEFAULT_ACTOR, display_title=project_name,
            governance_log=governance_log,
        )

    return document


def ingest_folder_upload(
    files: list[FileStorage],
    relative_paths: list[str],
    founding_index: int,
    app: Flask,
    operating_environment: str,
    owner: str,
    actor: str | None = None,
    role: str | None = None,
    project_name: str | None = None,
) -> tuple[ParsedDocument, list[dict]]:
    """
    CLAUDE-CA1D-RECEPTION-FIX-01 (folder establishment): establishes a
    project from a folder of files rather than one file. `files` and
    `relative_paths` are parallel lists (relative_paths[i] is a
    webkitRelativePath-style path for files[i], e.g. "exhibits/spec.pdf"
    -- always relative, a local filesystem path on the uploader's own
    machine that this server never sees or stores). `founding_index`
    names which file the CLIENT has already confirmed (or the user
    explicitly picked) as the principal/founding document -- this
    function never infers that itself.

    The founding file goes through the existing, unchanged ingest_upload
    above -- same extraction/classification/registry path a single-file
    establishment always used. Every OTHER eligible file (same
    ALLOWED_UPLOAD_EXTENSIONS/MAX_CONTENT_LENGTH rules as the founding
    document -- no separate, looser bar) is registered as a real
    governed Source (CaseWorkspaceStore.add_source, the same mechanism
    routes/workspace.py's own add_document_source route already uses)
    AND has its own text run through BHiveParser's shared extraction
    stage (_extract -- the same stage the founding document's own
    parse() already uses internally) and persisted as real per-
    paragraph EvidenceItems (register_plain_text_structure) -- so its
    content is genuinely available as project evidence, not a
    filename-only placeholder. A file that fails this per-file step
    (unsupported extension, oversize, unreadable) is skipped and
    reported, never allowed to fail the whole establishment -- the
    founding document having already succeeded means the project
    already exists by that point regardless.

    relative_paths are stored only as Source.origin_reference (display/
    provenance metadata) -- never used to construct an on-disk path;
    the actual stored file always uses the same opaque UUID-prefixed
    naming scheme every other Source in this codebase already uses, so
    a hand-crafted relative_path (".." segments, an absolute path) can
    never influence where anything is actually written on this server.

    Returns (founding_document, results) -- results has one dict per
    NON-founding file: {"filename", "relative_path", "status": "added" |
    "skipped", "reason"} (reason is None when status is "added").
    """
    if not files:
        raise UploadError("No files were provided.")
    if not (0 <= founding_index < len(files)):
        raise UploadError("The founding document selection is invalid.")

    # relative_paths[i] is what travels as files[i].filename client-side
    # (see templates/upload.html's own script - a File is renamed to its
    # webkitRelativePath before submission, so the relative path arrives
    # server-side without a second, order-dependent form field). Reset to
    # just the basename before the founding document goes through the
    # existing, unmodified ingest_upload -- that function's own filename
    # handling (document.filename, name-uniqueness, secure_filename) must
    # see a plain filename here, identical to what a real single-file
    # upload always gave it, never a path fragment.
    files[founding_index].filename = Path(relative_paths[founding_index]).name

    founding_document = ingest_upload(
        files[founding_index], app, operating_environment, owner,
        actor=actor, role=role, project_name=project_name,
    )

    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(founding_document.project_id)
    governance_log = get_governance_log(app)
    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    max_bytes = app.config.get("MAX_CONTENT_LENGTH")
    sources_dir = Path(app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / founding_document.project_id
    sources_dir.mkdir(parents=True, exist_ok=True)

    parser = BHiveParser(
        anthropic_api_key=app.config.get("ANTHROPIC_API_KEY"),
        model=app.config.get("ANTHROPIC_MODEL"),
    )

    results: list[dict] = []
    for index, (file_storage, relative_path) in enumerate(zip(files, relative_paths)):
        if index == founding_index:
            continue
        # The basename only, never the full relative path -- the same
        # fix as the founding document above. relative_path itself is
        # preserved separately, below, as Source.origin_reference.
        filename = Path(relative_path).name if relative_path else "(unnamed file)"
        if not relative_path:
            results.append({"filename": filename, "relative_path": relative_path, "status": "skipped", "reason": "No filename."})
            continue

        ext = Path(filename).suffix.lower()
        if ext not in allowed:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"Unsupported file type '{ext}'.",
            })
            continue

        raw_bytes = file_storage.read()
        if max_bytes and len(raw_bytes) > max_bytes:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"File exceeds the {max_bytes // (1024 * 1024)}MB size limit.",
            })
            continue

        safe_name = secure_filename(filename)
        stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
        stored_path.write_bytes(raw_bytes)

        source = store.add_source(
            workspace, name=safe_name, file_path=str(stored_path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT,
            file_hash=hashlib.sha256(raw_bytes).hexdigest(),
            origin_type=SOURCE_ORIGIN_TYPE_UPLOAD, origin_reference=relative_path,
            governance_log=governance_log, actor=actor or _DEFAULT_ACTOR,
        )

        try:
            text = parser._extract(raw_bytes, filename)  # noqa: SLF001 - same shared stage ingest_upload's own parse() uses internally
        except ParserError as exc:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"Added as a Source, but its content could not be extracted: {exc}",
            })
            continue

        store.register_plain_text_structure(
            workspace, source_id=source["id"], text=text,
            extractor_version=parser.__class__.__name__, actor=actor or _DEFAULT_ACTOR,
            governance_log=governance_log,
        )
        results.append({"filename": filename, "relative_path": relative_path, "status": "added", "reason": None})

    return founding_document, results


def reconcile_data_room_upload(
    files: list[FileStorage],
    relative_paths: list[str],
    project_id: str,
    app: Flask,
    actor: str | None = None,
    role: str | None = None,
) -> list[dict]:
    """
    CLAUDE-RFP27-TERRITORY-01: the Data Room discovery/reconciliation
    mechanism (Part 4 of the governing prompt) - reconciles a real,
    browser-selected folder (the SAME `webkitdirectory` shape
    ingest_folder_upload above already parses: files[i]/relative_paths[i]
    are parallel, relative_paths[i] a path local to the uploader's own
    machine, e.g. "01 RFP Documents/01.2 Addenda/Addendum-01.pdf") against
    an EXISTING project's already-registered Sources, rather than
    creating a new project the way ingest_folder_upload does.

    Deliberately read-only/additive, never destructive (Part 4's own
    "do not auto-delete canonical records when a filesystem path
    disappears" - a file present in a PRIOR scan but absent from this one
    is simply not mentioned in the results; nothing about it is touched):

    - Every directory segment in relative_paths becomes a real, governed
      Folder (root=FOLDER_ROOT_DATA_ROOM, via CaseWorkspaceStore.
      ensure_folder_path - the one place allowed to construct that root),
      created idempotently - re-running this against an unchanged folder
      is a safe no-op, never a duplicate.
    - A file whose content hash EXACTLY matches an already-registered
      Source (anywhere in the project, not only ones already in a
      Folder) is treated as the SAME Source, just now known to live at
      this real path - relinked (CaseWorkspaceStore.set_source_folder),
      never duplicated. This is "preserve existing Source identity
      wherever safely possible... do not create duplicate canonical
      Sources merely because earlier files were uploaded from a flat
      ad-hoc location," the governing prompt's own explicit Part 2
      requirement.
    - A genuinely new eligible file is registered exactly like
      ingest_folder_upload's own non-founding files (add_source, real
      BHiveParser._extract, register_plain_text_structure) - so it is
      real, searchable project evidence, not a filename-only stub -
      with folder_id set to its resolved Folder.
    - An ineligible extension, oversize file, or unreadable content is
      reported skipped with a reason, exactly like ingest_folder_upload,
      never silently dropped.

    Returns one dict per file: {"filename", "relative_path", "status":
    "added" | "relinked" | "skipped", "reason", "source_id"}.
    """
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        raise UploadError(f"Project {project_id} was not found.")

    governance_log = get_governance_log(app)
    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    max_bytes = app.config.get("MAX_CONTENT_LENGTH")
    sources_dir = Path(app.config["REGISTRY_STORE_PATH"]) / "workspace_sources" / project_id
    sources_dir.mkdir(parents=True, exist_ok=True)

    parser = BHiveParser(
        anthropic_api_key=app.config.get("ANTHROPIC_API_KEY"),
        model=app.config.get("ANTHROPIC_MODEL"),
    )

    # Re-fetched fresh after every mutating store call below (ensure_folder_
    # path/set_source_folder/add_source all call self.save internally) so
    # each iteration's hash-dedup check sees every Source registered by an
    # EARLIER iteration in this same reconciliation run too, not just the
    # ones that existed before it started.
    results: list[dict] = []
    for file_storage, relative_path in zip(files, relative_paths):
        if not relative_path:
            results.append({"filename": "(unnamed file)", "relative_path": relative_path, "status": "skipped", "reason": "No filename.", "source_id": None})
            continue

        rel = Path(relative_path.replace("\\", "/"))
        filename = rel.name
        directory = "/".join(rel.parts[:-1])

        ext = rel.suffix.lower()
        if ext not in allowed:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"Unsupported file type '{ext}'.", "source_id": None,
            })
            continue

        raw_bytes = file_storage.read()
        if max_bytes and len(raw_bytes) > max_bytes:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"File exceeds the {max_bytes // (1024 * 1024)}MB size limit.", "source_id": None,
            })
            continue

        file_hash = hashlib.sha256(raw_bytes).hexdigest()
        workspace = store.get(project_id)
        folder_id = store.ensure_folder_path(
            workspace, root=FOLDER_ROOT_DATA_ROOM, relative_path=directory,
            actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
        ) if directory else None

        workspace = store.get(project_id)
        existing = next((s for s in workspace.sources if s.get("file_hash") == file_hash), None)
        if existing is not None:
            store.set_source_folder(
                workspace, source_id=existing["id"], folder_id=folder_id,
                actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
            )
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "relinked",
                "reason": f"Byte-identical to already-registered Source \"{existing['name']}\" - relinked, not duplicated.",
                "source_id": existing["id"],
            })
            continue

        safe_name = secure_filename(filename)
        stored_path = sources_dir / f"{uuid.uuid4().hex}_{safe_name}"
        stored_path.write_bytes(raw_bytes)

        source = store.add_source(
            workspace, name=safe_name, file_path=str(stored_path),
            kind=SOURCE_KIND_PROJECT_DOCUMENT, file_hash=file_hash,
            origin_type=SOURCE_ORIGIN_TYPE_UPLOAD, origin_reference=relative_path,
            folder_id=folder_id, governance_log=governance_log, actor=actor or _DEFAULT_ACTOR,
        )

        try:
            text = parser._extract(raw_bytes, filename)  # noqa: SLF001 - same shared stage ingest_upload/ingest_folder_upload's own parse() uses internally
        except ParserError as exc:
            results.append({
                "filename": filename, "relative_path": relative_path, "status": "skipped",
                "reason": f"Registered as a Source, but its content could not be extracted: {exc}",
                "source_id": source["id"],
            })
            continue

        store.register_plain_text_structure(
            workspace, source_id=source["id"], text=text,
            extractor_version=parser.__class__.__name__, actor=actor or _DEFAULT_ACTOR,
            governance_log=governance_log,
        )
        results.append({"filename": filename, "relative_path": relative_path, "status": "added", "reason": None, "source_id": source["id"]})

    return results


# -- Data Room reconciliation preview (CLAUDE-DATA-ROOM-RECONCILE-01) --------
# `reconcile_data_room_upload` above is real and correct for the one thing
# it already does (compare-and-register in a single request), but it never
# gave the reviewer a chance to see what would happen before it happened -
# real evidence this stage's own North Bayview proof case surfaced (a
# newly-added .xlsx workbook needed to be classified and explained, not
# silently registered or silently dropped). This module adds a genuinely
# read-only comparison pass, plus a small staging store so a reviewer's
# "Add N new document(s)" decision is a SEPARATE, later request -
# `reconcile_data_room_upload` itself is unchanged and still the thing that
# actually performs registration, called again (idempotently - hash-dedup
# makes a second call over the same files safe) only once approved. Not a
# parallel Source registry: every comparison here reads workspace.sources
# directly, the same single source of truth every other Source-aware route
# already uses.
RECONCILE_STATUS_UNCHANGED = "unchanged"
RECONCILE_STATUS_NEW = "new"
RECONCILE_STATUS_MODIFIED = "modified"
RECONCILE_STATUS_MISSING = "missing"
RECONCILE_STATUS_RENAMED = "renamed"
RECONCILE_STATUS_INELIGIBLE = "ineligible"
RECONCILE_STATUS_AMBIGUOUS = "ambiguous"
KNOWN_RECONCILE_STATUSES = (
    RECONCILE_STATUS_UNCHANGED, RECONCILE_STATUS_NEW, RECONCILE_STATUS_MODIFIED,
    RECONCILE_STATUS_MISSING, RECONCILE_STATUS_RENAMED, RECONCILE_STATUS_INELIGIBLE,
    RECONCILE_STATUS_AMBIGUOUS,
)


def preview_data_room_reconcile(
    files: list[FileStorage], relative_paths: list[str], project_id: str, app: Flask,
) -> tuple[dict, list[tuple[str, str, bytes]]]:
    """
    Read-only comparison of a real, browser-selected folder against this
    project's already-registered Sources - never calls add_source,
    set_source_folder, or ensure_folder_path. Returns `(report,
    new_eligible_files)`: `report` is JSON-serializable (summary counts +
    one list per non-empty classification, `unchanged` reported as a count
    only - Section 10's own "avoid flooding... emphasize exceptions, not
    unchanged inventory"); `new_eligible_files` is `(relative_path,
    filename, raw_bytes)` for exactly the files a confirm step could safely
    register, handed to `PendingReconcileStore.create` by the caller.

    Classification, in the order each file is actually checked:
    - INELIGIBLE: unsupported extension or oversize (same rules
      reconcile_data_room_upload already enforces - never a second,
      looser or stricter bar).
    - AMBIGUOUS: identical content to another file already seen earlier in
      THIS SAME scan - never guessed as a rename/duplicate, surfaced for a
      human to look at instead.
    - UNCHANGED / RENAMED: content hash matches an already-registered,
      active Source. Same relative_path as that Source's own
      origin_reference -> UNCHANGED; a different one -> RENAMED (content
      identity is what's defensible here, not path guessing).
    - MODIFIED: no content-hash match, but relative_path matches an
      already-registered Source's own origin_reference - a known identity
      whose content has changed. Never auto-registered as a second Source
      and never overwrites the first - Section 7's own explicit
      requirement; a human decision this pass does not yet offer an action
      for.
    - NEW: neither content nor path matches anything already registered -
      genuinely new, eligible evidence.

    After the scan, any already-registered Source (origin_type=upload,
    removed_at=None, a real origin_reference) whose origin_reference was
    never matched by ANY file in this scan (neither by path nor by
    content) is MISSING - never deleted, never mutated, only reported
    (Section 7's own "do not delete it... flag the relationship as
    missing/unavailable... preserve historical evidence").
    """
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        raise UploadError(f"Project {project_id} was not found.")

    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    max_bytes = app.config.get("MAX_CONTENT_LENGTH")

    # Removed (soft-deleted) Sources are deliberately excluded from
    # comparison - a human already decided that Source is no longer
    # active project evidence; a Reconcile scan re-surfacing it as
    # "missing" or silently re-matching it would second-guess that
    # decision, not respect it.
    active_sources = [s for s in workspace.sources if not s.get("removed_at")]
    by_hash = {s["file_hash"]: s for s in active_sources if s.get("file_hash")}
    by_origin_ref = {
        s["origin_reference"]: s for s in active_sources
        if s.get("origin_type") == SOURCE_ORIGIN_TYPE_UPLOAD and s.get("origin_reference")
    }

    items: dict[str, list[dict]] = {status: [] for status in KNOWN_RECONCILE_STATUSES}
    new_eligible_files: list[tuple[str, str, bytes]] = []
    seen_origin_refs: set[str] = set()
    seen_hashes_this_scan: set[str] = set()

    for file_storage, relative_path in zip(files, relative_paths):
        if not relative_path:
            items[RECONCILE_STATUS_INELIGIBLE].append(
                {"filename": "(unnamed file)", "relative_path": relative_path, "reason": "No filename."}
            )
            continue

        rel = Path(relative_path.replace("\\", "/"))
        filename = rel.name
        ext = rel.suffix.lower()

        if ext not in allowed:
            items[RECONCILE_STATUS_INELIGIBLE].append({
                "filename": filename, "relative_path": relative_path,
                "reason": f"Unsupported file type '{ext}'.",
            })
            continue

        raw_bytes = file_storage.read()
        if max_bytes and len(raw_bytes) > max_bytes:
            items[RECONCILE_STATUS_INELIGIBLE].append({
                "filename": filename, "relative_path": relative_path,
                "reason": f"File exceeds the {max_bytes // (1024 * 1024)}MB size limit.",
            })
            continue

        file_hash = hashlib.sha256(raw_bytes).hexdigest()

        if file_hash in seen_hashes_this_scan:
            items[RECONCILE_STATUS_AMBIGUOUS].append({
                "filename": filename, "relative_path": relative_path,
                "reason": "Identical content to another file already scanned in this same folder - possible duplicate, not guessed as a rename.",
            })
            continue
        seen_hashes_this_scan.add(file_hash)

        existing_by_hash = by_hash.get(file_hash)
        if existing_by_hash is not None:
            seen_origin_refs.add(existing_by_hash.get("origin_reference"))
            if existing_by_hash.get("origin_reference") == relative_path:
                items[RECONCILE_STATUS_UNCHANGED].append({
                    "filename": filename, "relative_path": relative_path,
                    "source_id": existing_by_hash["id"], "source_name": existing_by_hash["name"],
                })
            else:
                items[RECONCILE_STATUS_RENAMED].append({
                    "filename": filename, "relative_path": relative_path,
                    "source_id": existing_by_hash["id"], "source_name": existing_by_hash["name"],
                    "previous_relative_path": existing_by_hash.get("origin_reference"),
                })
            continue

        existing_by_path = by_origin_ref.get(relative_path)
        if existing_by_path is not None:
            seen_origin_refs.add(relative_path)
            items[RECONCILE_STATUS_MODIFIED].append({
                "filename": filename, "relative_path": relative_path,
                "source_id": existing_by_path["id"], "source_name": existing_by_path["name"],
            })
            continue

        items[RECONCILE_STATUS_NEW].append({"filename": filename, "relative_path": relative_path})
        new_eligible_files.append((relative_path, filename, raw_bytes))

    for origin_ref, source in by_origin_ref.items():
        if origin_ref not in seen_origin_refs:
            items[RECONCILE_STATUS_MISSING].append({
                "source_id": source["id"], "source_name": source["name"], "origin_reference": origin_ref,
            })

    summary = {status: len(items[status]) for status in KNOWN_RECONCILE_STATUSES}
    summary["total_scanned"] = len(relative_paths)

    report = {
        "project_id": project_id,
        "created_at": time.time(),
        "summary": summary,
        # Deliberately "by_status", not "items" - a dict literally has its
        # own .items() method, and Jinja's dot-access resolves an
        # attribute (the bound method) before falling back to key access,
        # so `report.items.new` in a template would silently see that
        # method object, never this dict's own "new" key. A real bug this
        # stage's own test suite caught, not guessed in advance.
        "by_status": items,
    }
    return report, new_eligible_files


# CLAUDE-DATA-ROOM-RECONCILE-01: same flat-JSON + sibling-raw-bytes-file
# staging pattern services/drawing_intake.py's own PendingUploadStore
# already established for the single-file "analyze, then confirm" flow -
# pluralized here (a reconciliation preview may have zero to many new
# eligible files, not exactly one), never a database table, never Flask
# session (raw bytes have no business round-tripping through a signed
# cookie). Deliberately a SEPARATE subdirectory/class from
# PendingUploadStore rather than a generalized one - the two manifests
# hold genuinely different shapes (drawing-intake candidates vs. a full
# reconciliation report), and this codebase's own established practice
# (see reconcile_data_room_upload's own docstring) is to duplicate a
# short, already-proven shape at a second call site rather than force a
# shared abstraction across two things that happen to look similar today
# but may diverge tomorrow.
_RECONCILE_STAGING_SUBDIR = "pending_reconciles"
_RECONCILE_STAGING_TTL_SECONDS = 24 * 60 * 60


class PendingReconcileStore:
    def __init__(self, store_path: str | Path):
        self.dir = Path(store_path) / _RECONCILE_STAGING_SUBDIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def create(
        self, project_id: str, report: dict, new_eligible_files: list[tuple[str, str, bytes]],
        actor: Optional[str], role: Optional[str],
    ) -> str:
        self._sweep_expired()
        staging_id = uuid.uuid4().hex
        staged_dir = self.dir / staging_id
        staged_dir.mkdir(parents=True, exist_ok=True)

        staged_files = []
        for index, (relative_path, filename, raw_bytes) in enumerate(new_eligible_files):
            safe_name = secure_filename(filename)
            raw_path = staged_dir / f"{index}_{safe_name}"
            raw_path.write_bytes(raw_bytes)
            staged_files.append({"relative_path": relative_path, "filename": filename, "raw_path": str(raw_path)})

        manifest = {
            "staging_id": staging_id,
            "project_id": project_id,
            "created_at": time.time(),
            "report": report,
            "staged_files": staged_files,
            "actor": actor,
            "role": role,
        }
        self._manifest_path(staging_id).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        return staging_id

    def get(self, staging_id: str) -> Optional[dict]:
        path = self._manifest_path(staging_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def get_new_eligible_files(self, staging_id: str) -> list[tuple[str, str, bytes]]:
        manifest = self.get(staging_id)
        if manifest is None:
            return []
        result = []
        for entry in manifest["staged_files"]:
            raw_path = Path(entry["raw_path"])
            if not raw_path.exists():
                continue
            result.append((entry["relative_path"], entry["filename"], raw_path.read_bytes()))
        return result

    def discard(self, staging_id: str) -> None:
        manifest = self.get(staging_id)
        if manifest is None:
            return
        for entry in manifest["staged_files"]:
            Path(entry["raw_path"]).unlink(missing_ok=True)
        staged_dir = self.dir / secure_filename(staging_id)
        if staged_dir.exists():
            try:
                staged_dir.rmdir()
            except OSError:
                pass  # not empty (unexpected extra file) - leave it, never fail the request over cleanup
        self._manifest_path(staging_id).unlink(missing_ok=True)

    def _manifest_path(self, staging_id: str) -> Path:
        # staging_id is always our own uuid4().hex output (never taken
        # from a request path segment without validation upstream) -
        # still defensively confined via secure_filename, same discipline
        # PendingUploadStore's own _manifest_path already established.
        return self.dir / f"{secure_filename(staging_id)}.json"

    def _sweep_expired(self) -> None:
        """Best-effort cleanup of abandoned reconciliation previews (a
        reviewer who ran Reconcile but never confirmed or discarded) -
        runs opportunistically on the next create(), matching
        PendingUploadStore's own established discipline exactly - no
        background worker/cron (this codebase deliberately has none)."""
        now = time.time()
        for manifest_path in self.dir.glob("*.json"):
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                created_at = manifest.get("created_at", 0)
            except (OSError, ValueError):
                created_at = 0
            if now - created_at > _RECONCILE_STAGING_TTL_SECONDS:
                self.discard(manifest.get("staging_id") or manifest_path.stem)
