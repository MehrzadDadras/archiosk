"""
Shared upload-handling glue between routes/api.py and routes/portal.py.

Both blueprints accept an uploaded RFP/RFQ and need the same validate ->
parse -> save sequence, so it lives here once rather than being
duplicated (and drifting) across a JSON endpoint and an HTML form handler.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
import json
import logging
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
    KNOWN_SOURCE_DOMAINS,
    SOURCE_DOMAIN_UNKNOWN,
    SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR,
    SOURCE_ORIGIN_TYPE_UPLOAD,
    SPREADSHEET_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    SPREADSHEET_CLASSIFICATION_EXCESSIVE_SIZE,
    SPREADSHEET_CLASSIFICATION_MALFORMED,
    SPREADSHEET_CLASSIFICATION_SUPPORTED,
    CaseWorkspaceStore,
    REQUIREMENT_STATUS_SUPERSEDED,
    REQUIREMENT_STATUS_WITHDRAWN,
)
from services.governance import GovernanceLog
from services.requirements_registry import RequirementsRegistry
from services.security_governance import SecurityGovernanceStore
from services.security_policy import ACTION_EXTERNAL_AI_REQUEST, DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE, evaluate_action

logger = logging.getLogger(__name__)

# This app has no authentication system, so there's no real identity to
# fall back on. These are honest placeholders, not a claim that anyone
# was actually verified -- see services/governance.py.
_DEFAULT_ACTOR = "anonymous"
_DEFAULT_ROLE = "unspecified"
_SOURCE_REFERENCE_EXTRACTOR_VERSION = "declared_reference_v1"


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
    mistake -- the caller decides what to do with this, it doesn't block
    the upload.

    AUD-ENTRY-01A-1: the returned id is for the DEPLOYMENT's own use
    only. It must never be written into either project's governed state,
    returned by a project-scoped route, or otherwise made reachable by a
    member of either project. Two competing bidders holding the same
    issued tender is a normal, expected procurement shape; neither may
    learn of the other from it.
    """
    registry = get_registry(app)
    for pid in registry.list_ids():
        document = registry.get(pid)
        if document is not None and document.original_file_hash == file_hash:
            return pid
    return None


def document_source_payload(
    document: ParsedDocument, source_domain: str = SOURCE_DOMAIN_UNKNOWN,
) -> dict:
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
        "source_domain": source_domain,
    }


def _validated_source_domain(value: str | None) -> str:
    domain = value or SOURCE_DOMAIN_UNKNOWN
    if domain not in KNOWN_SOURCE_DOMAINS:
        raise UploadError("Select a valid source domain.")
    return domain


def existing_project_codes(app: Flask, exclude_project_id: str | None = None) -> set:
    """Every acronym currently in use, for uniqueness checking.

    Scope is deployment-wide, matching how project NAMES are already scoped by
    _reject_if_name_taken - one rule for project identity rather than two
    different ones for its two halves.
    """
    registry = get_registry(app)
    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    codes = set()
    for pid in registry.list_ids():
        if exclude_project_id and pid == exclude_project_id:
            continue
        workspace = store.get(pid)
        if workspace is not None and workspace.project_code:
            codes.add(workspace.project_code.upper())
    return codes


def _resolve_project_code(app: Flask, project_name: str, supplied: str | None) -> str:
    """Validate what the user typed, or derive one they never had to think about."""
    from services.project_code import ProjectCodeError, derive_code, validate_code

    taken = existing_project_codes(app)
    supplied = (supplied or "").strip()
    if supplied:
        try:
            return validate_code(supplied, taken=taken)
        except ProjectCodeError as exc:
            raise UploadError(str(exc)) from exc
    return derive_code(project_name, taken=taken)


def backfill_project_code(app: Flask, store, workspace) -> str | None:
    """Give an existing project an acronym the first time one is needed.

    Same shape as project_access.ensure_owner_backfilled: lazy, idempotent, and
    it writes only when something was genuinely missing. Product Owner
    authorization is explicit that individual generated values need no approval,
    so this does not stop to ask.

    Returns the code, or None if it could not be derived - a project without one
    simply issues no human-readable references yet, which is honest.
    """
    if workspace is None:
        return None
    if workspace.project_code:
        return workspace.project_code
    from services.project_code import ProjectCodeError, derive_code

    name = _display_name_of(get_registry(app).get(workspace.project_id), store) \
        if get_registry(app).get(workspace.project_id) else workspace.display_title
    try:
        code = derive_code(name or workspace.project_id,
                           taken=existing_project_codes(app, exclude_project_id=workspace.project_id))
    except ProjectCodeError:
        return None
    workspace.project_code = code
    store.save(workspace)
    return code


def ingest_upload(
    file_storage: Optional[FileStorage],
    app: Flask,
    operating_environment: str,
    owner: str,
    actor: str | None = None,
    role: str | None = None,
    project_name: str | None = None,
    project_code: str | None = None,
    source_domain: str = SOURCE_DOMAIN_UNKNOWN,
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

    source_domain = _validated_source_domain(source_domain)

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
    # CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01: .xlsx is a genuinely
    # eligible Source (see ALLOWED_UPLOAD_EXTENSIONS above), but never as
    # the FOUNDING document specifically - this path calls classify()/
    # _check_consistency() below, which expect prose-shaped extracted
    # text, and a spreadsheet's real structure (sheets/rows/cells) has no
    # honest prose rendering (Section 4's own "do not flatten a workbook
    # into misleading prose", extended here to founding-document
    # classification, not just display). Refused explicitly, with a
    # constructive alternative, rather than left to fail opaquely inside
    # BHiveParser's own extraction.
    if ext == ".xlsx":
        raise UploadError(
            "A spreadsheet (.xlsx) cannot be a project's founding document - its structure isn't "
            "prose suitable for case classification. Upload a PDF/DOCX/TXT/MD as the founding "
            "document, then add this workbook via folder upload or Data Room Reconcile."
        )

    project_name = (project_name or "").strip() or None
    _reject_if_name_taken(app, project_name or filename)

    # CLAUDE-PROJECT-CODE-01: every new project gets a governed acronym, and
    # nobody is made to invent one. A supplied value is validated; an absent one
    # is derived from the project name. Resolved HERE, beside the name-uniqueness
    # check and before any parsing or persistence, so a project is never half
    # created and then rejected for its acronym.
    resolved_project_code = _resolve_project_code(app, project_name or filename, project_code)

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
    #
    # AUD-ENTRY-01A-1: the matching project's id is DELIBERATELY NOT
    # carried into any project-readable state. It used to be written into
    # this project's own `document_ingested` governance payload, which
    # `GET /api/v1/documents/<project_id>/governance` returns verbatim to
    # any authorized member of THIS project - so a competing bidder who
    # independently uploaded the same issued tender could learn, from
    # their own audit trail, both that another ARCHIOSK project holds it
    # and that project's identifier. Constitutional invariant #8 already
    # forbids one project's state transferring into another's "regardless
    # of shared client, company, or physical asset"; identical content is
    # exactly such a shared asset, and it must not become a channel.
    #
    # Nothing read this value - it drove no runtime behavior anywhere in
    # the repository - so it is simply not recorded. The operational
    # signal CLAUDE-P28 wanted is preserved as a server-side log line
    # only, readable by whoever can read the deployment's own logs, never
    # by a project member through any route.
    duplicate_of_project_id = _find_duplicate_content(app, document.original_file_hash)
    if duplicate_of_project_id is not None:
        logger.info(
            "Identical uploaded content already present in another project "
            "(new=%s, existing=%s). Both remain fully isolated; this is recorded "
            "for deployment operators only and is never exposed to either project.",
            document.project_id, duplicate_of_project_id,
        )

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
            # AUD-ENTRY-01A-1: no foreign project identifier here. See the
            # duplicate-detection block above for why.
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
        document.project_id,
        register_document_source=document_source_payload(document, source_domain=source_domain),
    )
    workspace.project_code = resolved_project_code
    store.save(workspace)
    # The founding Source is created by get_or_create rather than the
    # add-document path below.  Reuse the parser's existing deterministic
    # extraction stage to feed the same declared-reference registration seam;
    # unresolved citations remain records and no Relationship is created.
    founding_source = next(
        (source for source in workspace.sources if source.get("name") == document.filename),
        None,
    )
    if founding_source is not None:
        try:
            founding_text = parser._extract(raw_bytes, filename)  # noqa: SLF001 - shared parser seam
        except Exception:  # noqa: BLE001 - a mocked/legacy parser may have accepted bytes the extractor cannot reread
            founding_text = ""
        if founding_text.strip():
            _register_declared_source_references(
                store, workspace, founding_source["id"], founding_text,
                actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
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


def _register_source_content(
    store: CaseWorkspaceStore, workspace, source: dict, raw_bytes: bytes, filename: str,
    parser: BHiveParser, actor: str, governance_log: Optional[GovernanceLog],
) -> tuple[str, Optional[str]]:
    """
    CLAUDE-SPREADSHEET-SOURCE-ELIGIBILITY-01: extracts and registers
    governed evidence for a just-created, non-founding Source, shared by
    ingest_folder_upload and reconcile_data_room_upload (previously two
    near-identical inline blocks). `.xlsx` is routed through the real,
    already-hardened spreadsheet pipeline (services/spreadsheet_
    intelligence.py's inspect_workbook -- macro/zip-bomb/OLE2/malformed
    detection already built in, CLAUDE-MM3) and CaseWorkspaceStore.
    register_spreadsheet_structure (sheet/row/cell evidence) -- never
    BHiveParser, which has no .xlsx branch and would otherwise either
    raise or (worse) silently misread binary zip bytes as prose. Every
    other allowed extension is completely unchanged: BHiveParser._extract
    + register_plain_text_structure, exactly as before this helper
    existed.

    Returns (status, reason): status is "added" or "skipped"; reason is
    None on success or a human-readable explanation on skip. Never
    raises -- a refused/unreadable file is always an honest skip here,
    matching both callers' own existing per-file failure handling.
    """
    if Path(filename).suffix.lower() == ".xlsx":
        from services.spreadsheet_intelligence import (
            inspect_workbook,
            _spreadsheet_extractor_version,  # noqa: SLF001 - same reach-in precedent as parser._extract below
        )
        inspection = inspect_workbook(raw_bytes, filename)
        if inspection["classification"] != SPREADSHEET_CLASSIFICATION_SUPPORTED:
            reason_by_classification = {
                SPREADSHEET_CLASSIFICATION_MALFORMED: "the workbook could not be read (malformed or corrupt)",
                SPREADSHEET_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED: "the workbook is password-protected, macro-enabled, or otherwise unsupported",
                SPREADSHEET_CLASSIFICATION_EXCESSIVE_SIZE: "the workbook exceeds the supported size/dimension limits",
            }
            reason = reason_by_classification.get(inspection["classification"], inspection["classification"])
            return "skipped", f"Registered as a Source, but its content could not be extracted: {reason}."
        store.register_spreadsheet_structure(
            workspace, source_id=source["id"], sheets=inspection["sheets"],
            extractor_version=_spreadsheet_extractor_version(), actor=actor, governance_log=governance_log,
        )
        return "added", None

    try:
        text = parser._extract(raw_bytes, filename)  # noqa: SLF001 - same shared stage ingest_upload's own parse() uses internally
    except ParserError as exc:
        return "skipped", f"Registered as a Source, but its content could not be extracted: {exc}"
    if not text.strip():
        return "skipped", "Registered as a Source, but extraction produced no readable text."

    store.register_plain_text_structure(
        workspace, source_id=source["id"], text=text,
        extractor_version=parser.__class__.__name__, actor=actor, governance_log=governance_log,
    )
    _register_declared_source_references(
        store, workspace, source["id"], text, actor=actor, governance_log=governance_log,
    )
    return "added", None


def _register_declared_source_references(
    store: CaseWorkspaceStore,
    workspace,
    source_id: str,
    text: str,
    actor: str,
    governance_log: Optional[GovernanceLog],
) -> list[dict]:
    """Register citations using the existing bounded SourceReference path.

    Only current governed Requirement identifiers are supplied as section
    targets.  No registry ParsedDocument item, filename, or internal id is
    promoted into a target merely because it is available at ingestion time.
    """
    active_source_ids = {
        source["id"] for source in workspace.sources if not source.get("removed_at")
    }
    known_section_targets = {
        requirement.get("original_requirement_identifier")
        for requirement in workspace.requirements
        if requirement.get("source_id") in active_source_ids
        and requirement.get("status") not in (REQUIREMENT_STATUS_SUPERSEDED, REQUIREMENT_STATUS_WITHDRAWN)
        and requirement.get("original_requirement_identifier")
    }
    return store.extract_and_register_source_references(
        workspace,
        source_id=source_id,
        text=text,
        origin_context={"location_type": "source"},
        known_targets={"section": known_section_targets},
        resolution_method="declared_reference_target_match",
        resolved_target_type="requirement",
        extractor_version=_SOURCE_REFERENCE_EXTRACTOR_VERSION,
        actor=actor,
        governance_log=governance_log,
    )


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
    # CLAUDE-PROJECT-CODE-01: threaded straight through to ingest_upload, which
    # is the one project-creation path either route ends up in - a folder
    # establishes a project exactly like a single file does, so it needs an
    # acronym for exactly the same reason and by the same rules.
    project_code: str | None = None,
    source_domain: str = SOURCE_DOMAIN_UNKNOWN,
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
    source_domain = _validated_source_domain(source_domain)
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
        project_code=project_code,
        source_domain=source_domain,
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
            source_domain=source_domain,
            governance_log=governance_log, actor=actor or _DEFAULT_ACTOR,
        )

        status, reason = _register_source_content(
            store, workspace, source, raw_bytes, filename, parser,
            actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
        )
        results.append({"filename": filename, "relative_path": relative_path, "status": status, "reason": reason})

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

        status, reason = _register_source_content(
            store, workspace, source, raw_bytes, filename, parser,
            actor=actor or _DEFAULT_ACTOR, governance_log=governance_log,
        )
        results.append({
            "filename": filename, "relative_path": relative_path, "status": status, "reason": reason,
            "source_id": source["id"],
        })

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


@dataclass(frozen=True)
class ReconcileDescriptor:
    """One file as Reconcile needs to see it - never its contents.

    `sha256`/`size_bytes` are Optional for one specific, load-bearing reason:
    the extension check happens BEFORE any read, so a folder containing a 5GB
    ISO never pulls it into memory. A descriptor for a file rejected on its
    extension therefore legitimately has neither, and the classifier reaches the
    same INELIGIBLE verdict without them. Making them mandatory would have
    quietly turned that short-circuit into a full read of every file in the
    folder - a memory regression invisible to every existing test, because no
    test uses a file big enough to notice.
    """

    relative_path: str
    filename: str
    sha256: "Optional[str]" = None
    size_bytes: "Optional[int]" = None


def describe_upload_for_reconcile(
    file_storage: FileStorage, relative_path: str, allowed,
) -> "tuple[ReconcileDescriptor, Optional[bytes]]":
    """Build a descriptor from a real upload, handing the bytes back with it.

    The bytes are returned rather than discarded because the CALLER still needs
    them - preview_data_room_reconcile passes the NEW ones to
    PendingReconcileStore. Reads only once the extension has already passed, so
    the short-circuit above is preserved exactly; None means "never read", which
    is not the same as "empty".
    """
    rel = Path((relative_path or "").replace("\\", "/"))
    filename = rel.name or "(unnamed file)"
    if not relative_path or rel.suffix.lower() not in allowed:
        return ReconcileDescriptor(relative_path, filename), None
    raw_bytes = file_storage.read()
    return (
        ReconcileDescriptor(relative_path, filename,
                            hashlib.sha256(raw_bytes).hexdigest(), len(raw_bytes)),
        raw_bytes,
    )


def classify_reconcile_descriptors(
    descriptors: list, project_id: str, app: Flask,
) -> tuple[dict, list]:
    """The byte-free half of Reconcile. Returns `(report, new_descriptors)`.

    CLAUDE-RECONCILE-DESCRIPTORS-01. Every classification rule below, and the
    ORDER they are applied in, is the code that used to live inline in
    preview_data_room_reconcile - MOVED, not rewritten. That matters: a private
    storage manifest and a browser-selected folder must be judged by one
    standard, and a second implementation would drift from this one the first
    time either changed.

    Reconcile only ever needed three facts about a file - extension, size and
    content hash - and read bytes solely to derive the last two. A manifest
    already carries both, so the classification a Data Room folder gets is
    available for storage ARCHIOSK never touches.
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
    # CLAUDE-EXTERNAL-CUSTODY-01: the origin types whose origin_reference means
    # A PATH. That is what this filter was always selecting for - it is not an
    # upload-only rule. origin_reference is meaning-depends-on-origin-type by
    # design: for derivative_crop/eye_capture/document_snapshot it holds a
    # PARENT SOURCE ID, and matching those against relative paths would be
    # nonsense. external_connector's reference is a project-relative path, so it
    # belongs here for the same reason upload does.
    #
    # Without it a modified external file matches nothing by path and is
    # reported NEW, which would re-register it as a duplicate Source instead of
    # recognizing a known identity whose content changed - the opposite of
    # preserving Reconcile semantics.
    path_bearing_origins = (SOURCE_ORIGIN_TYPE_UPLOAD, SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR)
    by_origin_ref = {
        s["origin_reference"]: s for s in active_sources
        if s.get("origin_type") in path_bearing_origins and s.get("origin_reference")
    }

    items: dict[str, list[dict]] = {status: [] for status in KNOWN_RECONCILE_STATUSES}
    new_descriptors: list = []
    seen_origin_refs: set[str] = set()
    seen_hashes_this_scan: set[str] = set()

    for descriptor in descriptors:
        relative_path = descriptor.relative_path
        filename = descriptor.filename
        if not relative_path:
            items[RECONCILE_STATUS_INELIGIBLE].append(
                {"filename": "(unnamed file)", "relative_path": relative_path, "reason": "No filename."}
            )
            continue

        ext = Path(relative_path.replace("\\", "/")).suffix.lower()

        if ext not in allowed:
            items[RECONCILE_STATUS_INELIGIBLE].append({
                "filename": filename, "relative_path": relative_path,
                "reason": f"Unsupported file type '{ext}'.",
            })
            continue

        if max_bytes and descriptor.size_bytes is not None and descriptor.size_bytes > max_bytes:
            items[RECONCILE_STATUS_INELIGIBLE].append({
                "filename": filename, "relative_path": relative_path,
                "reason": f"File exceeds the {max_bytes // (1024 * 1024)}MB size limit.",
            })
            continue

        file_hash = descriptor.sha256
        if file_hash is None:
            # An eligible extension with no hash means the descriptor's
            # source could not supply one. Reported rather than guessed at:
            # every remaining rule depends on content identity.
            items[RECONCILE_STATUS_INELIGIBLE].append({
                "filename": filename, "relative_path": relative_path,
                "reason": "No content hash was available for this file.",
            })
            continue

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
        new_descriptors.append(descriptor)

    for origin_ref, source in by_origin_ref.items():
        if origin_ref not in seen_origin_refs:
            items[RECONCILE_STATUS_MISSING].append({
                "source_id": source["id"], "source_name": source["name"], "origin_reference": origin_ref,
            })

    summary = {status: len(items[status]) for status in KNOWN_RECONCILE_STATUSES}
    summary["total_scanned"] = len(descriptors)

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
    return report, new_descriptors


def preview_data_room_reconcile(
    files: list[FileStorage], relative_paths: list[str], project_id: str, app: Flask,
) -> tuple[dict, list[tuple[str, str, bytes]]]:
    """Unchanged signature, unchanged return, unchanged verdicts.

    Now a thin adapter: it builds descriptors from the uploads UP FRONT, hands
    them to classify_reconcile_descriptors, and reattaches the bytes for exactly
    the files classified NEW - which is the only thing the caller ever wanted
    them for (PendingReconcileStore.create).

    Kept as the Data Room's entry point rather than making every route build
    descriptors: the routes have no reason to learn a new vocabulary for a
    refactor that exists to serve a different caller entirely.
    """
    allowed = app.config["ALLOWED_UPLOAD_EXTENSIONS"]
    descriptors, bytes_by_path = [], {}
    for file_storage, relative_path in zip(files, relative_paths):
        descriptor, raw_bytes = describe_upload_for_reconcile(
            file_storage, relative_path, allowed)
        descriptors.append(descriptor)
        if raw_bytes is not None:
            bytes_by_path[relative_path] = raw_bytes

    report, new_descriptors = classify_reconcile_descriptors(descriptors, project_id, app)
    new_eligible_files = [
        (d.relative_path, d.filename, bytes_by_path[d.relative_path])
        for d in new_descriptors if d.relative_path in bytes_by_path
    ]
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
