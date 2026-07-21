"""
Generates a Request for Information (RFI) .docx from a document's flagged
cross-requirement contradictions (see BHiveParser's consistency-check stage).
"""
from __future__ import annotations

import io

import docx

from services.bhive_parser import ParsedDocument


class RFIExportError(Exception):
    """Raised when a document has nothing to export."""


def build_rfi_docx(document: ParsedDocument) -> io.BytesIO:
    if not document.consistency_flags:
        reason = (
            "No flagged contradictions to export."
            if document.consistency_checked
            else "Consistency check hasn't run for this document."
        )
        raise RFIExportError(reason)

    output = docx.Document()

    output.add_heading(f"Request for Information — {document.filename}", level=1)

    meta = output.add_paragraph()
    meta.add_run("Project ID: ").bold = True
    meta.add_run(f"{document.project_id}\n")
    meta.add_run("Ingested: ").bold = True
    meta.add_run(f"{document.ingested_at}\n")
    meta.add_run("Flagged items: ").bold = True
    meta.add_run(str(len(document.consistency_flags)))

    for i, flag in enumerate(document.consistency_flags, start=1):
        output.add_heading(f"RFI-{i:03d}", level=2)

        p = output.add_paragraph()
        p.add_run("Requirement A: ").bold = True
        p.add_run(flag.requirement_a_text)

        p = output.add_paragraph()
        p.add_run("Requirement B: ").bold = True
        p.add_run(flag.requirement_b_text)

        p = output.add_paragraph()
        p.add_run("Flagged discrepancy: ").bold = True
        p.add_run(flag.explanation)

    buffer = io.BytesIO()
    output.save(buffer)
    buffer.seek(0)
    return buffer
