"""
CLAUDE-EXTERNAL-CUSTODY-01 - a governed Source whose authoritative bytes
ARCHIOSK does not keep.

THE ONE PROPERTY THIS PROVES

    ARCHIOSK can govern and analyze a Source without permanently retaining the
    authoritative source bytes.

Everything else about the Source is unchanged: identity, hash, provenance,
Reconcile behaviour, evidence anchors, relationships. Only custody of the
original file moves.

WHAT WAS TRUE BEFORE

services/ingestion.py performs `stored_path.write_bytes(raw_bytes)` and records
an absolute `Source.file_path` under REGISTRY_STORE_PATH/workspace_sources/.
Every governed Source therefore implied "ARCHIOSK holds these bytes". That is
the single assumption this module relaxes - deliberately, opt-in, and for
sources registered through this path only.

HOW CUSTODY IS DISTINGUISHED

Not with a new boolean. A stored flag can drift out of agreement with reality;
these two facts cannot, because they ARE the reality:

    origin_type == "external_connector"   and   file_path is None

`external_connector` is not invented here. It has existed unwired in
KNOWN_SOURCE_ORIGIN_TYPES since Prompt 15 #4 and is named in three governance
records as the intended extension point for exactly this. Wiring it is the
missing verb; there is no new noun.

WHAT IS NOT CHANGED

Ordinary uploaded Sources keep absolute file_path and origin_type="upload" and
mean exactly what they meant before. Nothing here alters them, and a test
asserts it.

TERMINOLOGY, WHICH MATTERS HERE

An externally STORED project source is not EXTERNAL EVIDENCE. A drawing on the
project owner's own storage is an authoritative project document that happens to
live at a different address; its evidentiary status is untouched, and
GO-EXTERNAL-VESTIBULE-01's admission boundary is a separate concern this module
must not be read as reaching.

SECURITY

Local filesystem only. No network, no credentials, no ports, no SMB, no vendor
concepts. Path resolution refuses to leave the configured root.
"""
from __future__ import annotations

import hashlib
import io
from pathlib import Path, PurePosixPath
from typing import Iterator, Optional

from services.case_workspace import (
    SOURCE_KIND_PROJECT_DOCUMENT, SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR,
)


class ExternalSourceError(Exception):
    """The external file cannot be used, and the caller must not pretend it can."""


class ExternalSourceUnavailable(ExternalSourceError):
    """The source is registered and governed, but its bytes are not reachable
    right now.

    Deliberately its own type. "Currently unavailable" and "deliberately
    removed" are different facts about a project, and collapsing them is how a
    governed record starts lying - bug-eye-data-room-source-continuity.md's own
    "never silently deleting governed relationships because a Source can't
    currently be found".
    """


class ExternalSourceForbidden(ExternalSourceError):
    """The storage is reachable and the file is there - and it refused us.

    CLAUDE-EXTERNAL-CUSTODY-03. A third fact, and the reason it gets its own
    type rather than folding into ExternalSourceUnavailable: the advice differs.
    "Reconnect the storage and try again" is actively wrong when the NAS is
    plugged in and answering, and a permission was withdrawn. One will heal by
    itself; the other needs a person to restore access, and telling someone to
    wait for that is telling them to wait forever.

    Same reasoning that already separates "currently unavailable" from
    "deliberately removed" - collapsing two different facts about a project is
    how a governed record starts lying. This is a SIBLING under
    ExternalSourceError, deliberately not a parallel hierarchy: one vocabulary
    for one subject.
    """


def normalize_relative_reference(relative_path: str) -> str:
    """Store a POSIX-style, root-relative reference - never a machine path.

    `Drawings/A101.pdf`, never `C:\\Users\\...\\A101.pdf` and never
    `\\\\10.0.0.148\\Public\\...`. IP addresses change, drive letters differ per
    machine, and a collaborator's mapping is not the owner's. The durable
    identity is (governed root) + (relative reference); the absolute path is
    only ever a resolution result, computed at the moment of access.
    """
    cleaned = (relative_path or "").strip().replace("\\", "/").lstrip("/")
    parts = [p for p in PurePosixPath(cleaned).parts if p not in ("", ".")]
    if not parts:
        raise ExternalSourceError("An external source reference cannot be empty.")
    if any(p == ".." for p in parts):
        raise ExternalSourceError("An external source reference cannot traverse upward.")
    return str(PurePosixPath(*parts))


def resolve_within_root(root: str, relative_path: str) -> Path:
    """Resolve a reference against the governed root, refusing to escape it.

    Checked after resolution rather than before, so symlinks and `..` embedded
    anywhere in the chain are both caught - a prefix test on the raw string
    would pass for a path that resolves outside.
    """
    if not root:
        raise ExternalSourceError("This project has no external storage root configured.")
    reference = normalize_relative_reference(relative_path)
    root_path = Path(root).expanduser().resolve()
    candidate = (root_path / reference).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise ExternalSourceError("Resolved outside the configured storage root.") from exc
    return candidate


def read_external_bytes(root: str, relative_path: str) -> bytes:
    """Read the authoritative file. TRANSIENT - the caller must not persist it.

    Raises ExternalSourceUnavailable rather than returning empty bytes when the
    file is gone: "fail honestly if external bytes are needed later and
    unavailable", never fabricate analysis from nothing while presenting the
    source as current.
    """
    path = resolve_within_root(root, relative_path)
    try:
        present = path.is_file()
    except PermissionError as exc:
        # A revoked DIRECTORY denies the stat, so the file's own existence
        # cannot even be asked. That is refusal, not absence.
        raise ExternalSourceForbidden(
            "Access to %s was refused by the storage." % relative_path) from exc
    if not present:
        raise ExternalSourceUnavailable(
            "The authoritative file is not reachable at %s right now." % relative_path)
    try:
        return path.read_bytes()
    except PermissionError as exc:
        # Checked before OSError, which PermissionError subclasses - the order
        # is load-bearing, not stylistic.
        raise ExternalSourceForbidden(
            "Access to %s was refused by the storage." % relative_path) from exc
    except OSError as exc:
        raise ExternalSourceUnavailable(str(exc)) from exc


def iter_external_files(root: str) -> Iterator[str]:
    """Every file under the governed root, as normalized relative references."""
    root_path = Path(root).expanduser().resolve()
    try:
        reachable = root_path.is_dir()
    except PermissionError as exc:
        raise ExternalSourceForbidden(
            "Access to the storage root was refused: %s" % root) from exc
    if not reachable:
        raise ExternalSourceUnavailable("The storage root is not reachable: %s" % root)
    try:
        entries = sorted(root_path.rglob("*"))
    except PermissionError as exc:
        raise ExternalSourceForbidden(
            "Access to the storage root was refused: %s" % root) from exc
    for path in entries:
        if path.is_file():
            yield normalize_relative_reference(str(path.relative_to(root_path)))


def source_bytes_are_externally_held(source: dict) -> bool:
    """Does ARCHIOSK hold this Source's authoritative bytes, or does it not?

    Derived from the record rather than stored beside it, so it cannot disagree
    with the record it describes.
    """
    return (source.get("origin_type") == SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR
            and not source.get("file_path"))


def external_source_for_reference(workspace, relative_path: str) -> Optional[dict]:
    reference = normalize_relative_reference(relative_path)
    for source in workspace.sources:
        if source.get("removed_at"):
            continue
        if (source_bytes_are_externally_held(source)
                and source.get("origin_reference") == reference):
            return source
    return None


def register_external_source(
    store, workspace, relative_path: str, *, root: Optional[str] = None,
    kind: str = SOURCE_KIND_PROJECT_DOCUMENT, extract_text: bool = True,
) -> dict:
    """Register an externally held file as a governed Source.

    Reads the bytes, derives everything ARCHIOSK needs from them, and then lets
    them go. Nothing is written to workspace_sources/ and `file_path` stays
    None - which, with origin_type=external_connector, is the whole custody
    claim.

    The extracted text is returned to the caller rather than written here: this
    module registers and derives, and persistence of downstream derivatives
    belongs to the existing seams that already own it, not to a second
    ingestion path.
    """
    storage_root = root or workspace.external_storage_root
    reference = normalize_relative_reference(relative_path)
    raw_bytes = read_external_bytes(storage_root, reference)

    name = PurePosixPath(reference).name
    source = store.add_source(
        workspace,
        name=name,
        # No ARCHIOSK-held copy. This None IS the proof.
        file_path=None,
        kind=kind,
        origin_type=SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR,
        origin_reference=reference,
        file_hash=hashlib.sha256(raw_bytes).hexdigest(),
    )
    # mime_type/size_bytes are real Source fields but add_source does not accept
    # them, and widening its signature is more than this proof needs. The hash
    # already proves the bytes were genuinely read, which is the claim under
    # test; carrying the rest is a later, separate change.

    extracted_text = ""
    if extract_text:
        try:
            from services.bhive_parser import BHiveParser

            extracted_text = BHiveParser()._extract(raw_bytes, name) or ""
        except Exception:
            # An unreadable format is not a registration failure - the Source is
            # still governed, still hashed, still reconcilable. It simply has no
            # text derivative, which is honest rather than fatal.
            extracted_text = ""

    # The transient copy ends here: raw_bytes goes out of scope and was never
    # written anywhere. Made explicit so a later edit that persists it has to
    # delete this line and mean it.
    del raw_bytes
    return {"source": source, "extracted_text": extracted_text}


def reconcile_external_root(app, project_id: str, root: Optional[str] = None):
    """Reconcile the governed root using the EXISTING Reconcile machinery.

    Deliberately not a second synchronization mechanism. It reads the folder
    from disk instead of from a browser upload and hands the same
    (files, relative_paths) pair to preview_data_room_reconcile completely
    unchanged - so unchanged/modified/renamed/missing/ambiguous/ineligible are
    decided by the code that already owns those semantics, and this path cannot
    drift away from what the Data Room does.
    """
    from werkzeug.datastructures import FileStorage

    from services.case_workspace import CaseWorkspaceStore
    from services.ingestion import preview_data_room_reconcile

    store = CaseWorkspaceStore(app.config["REGISTRY_STORE_PATH"])
    workspace = store.get(project_id)
    if workspace is None:
        raise ExternalSourceError("Project %s was not found." % project_id)

    storage_root = root or workspace.external_storage_root
    if not storage_root:
        raise ExternalSourceError("This project has no external storage root configured.")

    files, relative_paths = [], []
    for reference in iter_external_files(storage_root):
        path = resolve_within_root(storage_root, reference)
        files.append(FileStorage(stream=io.BytesIO(path.read_bytes()), filename=reference))
        relative_paths.append(reference)

    return preview_data_room_reconcile(files, relative_paths, project_id, app)
