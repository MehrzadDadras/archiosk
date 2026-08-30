"""
CLAUDE-MM2: PDF and Document Intelligence - the thin orchestration layer
between a real PDF read (services/bhive_parser.py's `extract_pdf_pages`,
the one real pypdf call site) and the MM1 evidence contract (services/
case_workspace.py's `register_pdf_page_structure`). Exists specifically so
case_workspace.py does not have to import bhive_parser.py - the same
decoupling `promote_requirement_item()`'s own docstring already states as
a deliberate, standing architectural rule, not something this stage is
free to quietly relax.

Capability boundary, reused not re-derived: services/drawing_intake.py's
own repository-grounded audit (2026-08-04, CLAUDE-P40-VW8-QA-R2A)
established, and this stage re-confirmed at the time, that PDF-to-image
rendering and local OCR were NOT available in this environment (no
pypdfium2/PyMuPDF/pdf2image, no pytesseract, no tesseract OS binary) -
see that module's own header comment for the full audit and for its
2026-08-29 partial supersession: `pymupdf` IS a pinned dependency today
(engine/pdf_extractor.py uses it for vector geometry and positioned text
spans), so the rendering LIBRARY is present even though local OCR still
is not. This module's own boundary is unchanged by that: it still makes
no attempt at either, and an image-only PDF is classified honestly,
never silently downgraded to "unsupported" or upgraded with fabricated
text.
"""
from __future__ import annotations

from typing import Optional

from pypdf.errors import FileNotDecryptedError, PyPdfError, WrongPasswordError

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    PDF_CLASSIFICATION_EXTRACTION_FAILED,
    ProjectWorkspace,
)
from services.governance import GovernanceLog

PDF_EXTRACTOR_VERSION_PREFIX = "pypdf"


class PdfIntelligenceError(Exception):
    """Raised for a source that cannot even be attempted - not a Source,
    not a project match, or not a .pdf - distinct from a PDF that WAS
    attempted and failed to read (see the returned "classification"
    dict below for that case, which is not an exception)."""


def _pypdf_version() -> str:
    import pypdf

    return f"{PDF_EXTRACTOR_VERSION_PREFIX}:{pypdf.__version__}"


def register_pdf_evidence_for_source(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    source_id: str,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Loads the named Source's own persisted original bytes (Source.file_path
    - see services/ingestion.py's own "persist the ORIGINAL uploaded bytes"
    comment for why this is reliably present for any Source ingested
    through ingest_upload/add_document_source), reads it as a PDF, and
    registers the result as governed MM1 evidence.

    Returns `{"classification", "page_count", ...}` on ANY outcome,
    including a failed read - PDF_CLASSIFICATION_EXTRACTION_FAILED and
    PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED are both real, honest
    return values, never exceptions, since "this PDF could not be read"
    is exactly the kind of fact Section 11 requires reporting plainly,
    not hiding behind a 500. PdfIntelligenceError is raised only for a
    caller error (bad source_id, wrong project, not a PDF at all) - the
    same "cannot even be attempted" vs. "attempted and failed" distinction
    this module's own docstring states.
    """
    source = store._find(workspace.sources, source_id)
    if source is None or source["project_id"] != workspace.project_id:
        raise PdfIntelligenceError(f"Source {source_id} was not found.")

    file_path = source.get("file_path")
    if not file_path:
        raise PdfIntelligenceError(f"Source {source_id} has no stored original file to read.")

    name = source.get("name") or ""
    if not name.lower().endswith(".pdf"):
        raise PdfIntelligenceError(f"Source {source_id} ('{name}') is not a PDF.")

    from pathlib import Path

    path = Path(file_path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise PdfIntelligenceError(f"Source {source_id}'s stored file could not be read: {exc}") from exc

    extractor_version = _pypdf_version()

    # CLAUDE-MM2 (Section 12): parser failures must not corrupt the Source
    # record - every branch below either returns a real, honest
    # classification or re-raises as PdfIntelligenceError; nothing here
    # ever mutates `source` before a successful read, so a failed read
    # leaves the existing Source record completely untouched.
    from services.bhive_parser import BHiveParser

    try:
        pages = BHiveParser.extract_pdf_pages(raw_bytes)
    except (FileNotDecryptedError, WrongPasswordError):
        return {
            "classification": PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
            "page_count": None, "structural_unit_ids": [], "addressable_region_ids": [],
            "evidence_item_ids": [],
        }
    except PyPdfError:
        return {
            "classification": PDF_CLASSIFICATION_EXTRACTION_FAILED,
            "page_count": None, "structural_unit_ids": [], "addressable_region_ids": [],
            "evidence_item_ids": [],
        }
    except Exception:  # noqa: BLE001 - matches drawing_intake.py's own precedent:
        # a corrupt/adversarial PDF can raise something outside pypdf's own
        # exception hierarchy (a malformed stream tripping a lower-level
        # library error) - still an honest "could not read this file",
        # never a 500 that corrupts or crashes the caller.
        return {
            "classification": PDF_CLASSIFICATION_EXTRACTION_FAILED,
            "page_count": None, "structural_unit_ids": [], "addressable_region_ids": [],
            "evidence_item_ids": [],
        }

    result = store.register_pdf_page_structure(
        workspace, source_id, pages, extractor_version=extractor_version,
        actor=actor, governance_log=governance_log,
    )

    try:
        store.update_source_identity(
            workspace, source_id, actor=actor, mime_type="application/pdf",
            size_bytes=len(raw_bytes), extractor_version=extractor_version,
            governance_log=governance_log,
        )
    except CaseWorkspaceError:
        # Structure registration already succeeded and was already saved;
        # a Source-metadata backfill failing after that is not reason to
        # discard the real, already-persisted evidence records.
        pass

    return result
