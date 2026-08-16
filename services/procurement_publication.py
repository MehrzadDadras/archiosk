"""
CLAUDE-RFP-BOUNDARY-01: builds the Published Procurement Instrument export
artifact -- a plain zip of exactly the Owner-selected Source files, nothing
else. Deliberately separate from CaseWorkspaceStore.publish_procurement_
package (services/case_workspace.py), which owns the governed state
transition and audit log, the same way services/rfi_export.py's
build_rfi_docx is separate from the ReviewerValidation/RFI-draft governed
methods that produce its inputs -- this module only ever turns already-
selected, already-governed data into a bounded output artifact; it never
decides what belongs in the package.

Deliberately NO manifest file inside the zip. publish_procurement_package's
own governance-log payload already carries the provenance fields (document_
id/revision/issuer/document_status/document_authority, founding_source_id)
for the publish-confirmation screen to render -- bundling that as a text
file inside the same folder a human then re-uploads via services.ingestion.
ingest_folder_upload would get it ingested as a real Source/EvidenceItem in
the receiving Proponent project, polluting the evidence corpus GO retrieves
from with publication bookkeeping instead of RFP content.
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path


class PublicationExportError(Exception):
    """
    Raised when a selected Source's file cannot actually be exported --
    missing on disk (should never happen for a Source that just passed
    CaseWorkspaceStore.publish_procurement_package's own checks, but this
    module trusts nothing about the filesystem it doesn't verify itself).
    Mirrors services/rfi_export.py's own RFIExportError shape: an honest
    "nothing real to export" distinct from a generic exception.
    """


def build_published_package_zip(sources: list[dict]) -> bytes:
    """
    `sources` is the already-validated, already-selected list of Source
    dicts CaseWorkspaceStore.publish_procurement_package returns -- this
    function trusts their eligibility completely (removed_at absence,
    file_path presence) rather than re-deriving it, the same "governed
    state decides, export module only renders" split build_rfi_docx
    already establishes for RFI drafts. It does independently verify each
    file still exists on disk at export time, since that can change
    between the two calls.
    """
    if not sources:
        raise PublicationExportError("No Sources were selected to publish.")

    buf = io.BytesIO()
    used_names: set[str] = set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for source in sources:
            raw_path = source.get("file_path")
            file_path = Path(raw_path) if raw_path else None
            if file_path is None or not file_path.exists():
                raise PublicationExportError(
                    f"Source {source.get('id')!r} ({source.get('name')!r}) has no file to export."
                )
            arcname = _unique_name(source.get("name") or file_path.name, used_names)
            zf.write(file_path, arcname=arcname)

    return buf.getvalue()


def _unique_name(name: str, used_names: set[str]) -> str:
    """
    Two distinct Sources could share a filename (revision history,
    same-named exhibits added from different folders) -- this exists only
    to keep the zip's own flat namespace collision-free, never to change
    what's actually inside a Source's own governed `name` field.
    """
    if name not in used_names:
        used_names.add(name)
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 2
    while f"{stem} ({n}){suffix}" in used_names:
        n += 1
    candidate = f"{stem} ({n}){suffix}"
    used_names.add(candidate)
    return candidate
