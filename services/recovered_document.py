"""CLAUDE-DOCX-FROM-RECOVERED-01 - the scans, as one Word document.

Asked live in Document View, over four scanned pages: "can you read it and turn
it to one word document?" GO replied with its analysis summary. It was not
being obtuse - the typed-action menu it is offered
(capability_registry.DOCUMENT_VIEW_ACTION_IDS) held four view-only actions
(rotate, mirror, fit, align north) and nothing that produces a document, and
its contract says a command must be null unless the user asked for an
AVAILABLE action. With an empty menu, prose was the only move left.

WHAT THIS MODULE IS, AND IS NOT

It is assembly. It gathers already-recovered text, in order, and hands it to
services/document_export.py - the writer this product already uses for every
.docx it produces. There is no second extractor, no second OCR path, no second
writer. Two existing owners are reused verbatim:

    document_examination._recovered(workspace, source_id)  WHAT WAS READ
    document_export.build(document, "docx")                HOW IT IS WRITTEN

RECOVERY IS CHECKED BEFORE ANYTHING IS WRITTEN, and the check is the reason
this module exists as its own step rather than inline in the executor. A
scanned page that produced no text must not become a silently missing page in
a Word file the reviewer then sends to somebody. If any requested source has no
recovered passages, nothing is written at all and the caller is told which
pages and what to do about it. An incomplete document is worse than no
document, because its gaps are invisible once it leaves here.

NOTHING IS INVENTED. Every paragraph in the output came from an EvidenceItem;
the only text this module adds is structural - the title, a per-source heading,
and a provenance line stating what the file is and what it is not.

THE ORIGINALS ARE UNTOUCHED. The result is a NEW derivative Source, the same
mechanism image_intelligence.extract_bounded_crop and the Survey Reference
already use, carrying origin_type/origin_reference back to what it was built
from - so it is downloadable through the existing source_file route and
requires no new endpoint, and so a reader can always get back to the scans.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path
from typing import Optional

# How much recovered text a source needs before it counts as readable. One
# passage is enough: a page legitimately holding a single line is not a
# failure. Zero is the only condition that is.
_MIN_PASSAGES = 1


class RecoveredDocumentError(Exception):
    """Refusal to write a document that would misrepresent its sources."""


def readiness(workspace, source_ids) -> dict:
    """Which of these sources have usable recovered text, and which do not.

    Returned whole rather than as a boolean, because the caller has to be able
    to say WHICH page is missing - "some pages could not be read" is not an
    answer anybody can act on.
    """
    from services import document_examination as dx

    sources_by_id = {s["id"]: s for s in (workspace.sources or [])}
    ready, missing = [], []
    for source_id in source_ids:
        source = sources_by_id.get(source_id)
        if source is None or source.get("removed_at"):
            missing.append({"source_id": source_id, "name": None,
                            "reason": "the source is no longer available"})
            continue
        recovered = dx._recovered(workspace, source_id)
        entry = {
            "source_id": source_id,
            "name": source.get("name"),
            "page_count": recovered.get("page_count", 0),
            "passage_count": recovered.get("passage_count", 0),
            "character_count": recovered.get("character_count", 0),
            "passages": recovered.get("passages") or [],
            "was_recovered": recovered.get("was_recovered"),
            "is_direct_source": recovered.get("is_direct_source"),
            "read_by": recovered.get("read_by") or [],
        }
        if entry["passage_count"] >= _MIN_PASSAGES:
            ready.append(entry)
        else:
            entry["reason"] = "no text has been recovered from it yet"
            missing.append(entry)
    return {"ready": ready, "missing": missing,
            "complete": bool(ready) and not missing}


def ordered_source_ids(workspace) -> list[str]:
    """Every live source in the order the reviewer added them.

    A SOURCE WITH NO intake_order SORTS FIRST, and that is not a tie-break
    detail - it is the founding page. Verified against the live Existentialism
    case: its four scans carry intake_order None, 1, 2, 3, because the founding
    upload creates the case and `attach_document_shop_sources` numbers only what
    is attached afterwards. Treating None as "unknown, put it last" produced the
    order 2, 3, 4, 1 - the first page of the document at the end of it.

    That is also what Source.intake_order's own comment means by "None ... reads
    correctly as 'no stated order'": a record with nothing stated came before
    the numbering existed, or before the attachments did. Either way it precedes
    them.

    Ties break on added_at and then stored position, NEVER on the filename. The
    numbering docstring in services/ingestion.py is explicit about why: a phone
    hands over `image.jpg` five times, so a filename carries no order and often
    no distinction at all.
    """
    live = [s for s in (workspace.sources or []) if not s.get("removed_at")]
    return [
        s["id"] for index, s in sorted(
            enumerate(live),
            key=lambda pair: (
                pair[1].get("intake_order") if pair[1].get("intake_order") is not None else -1,
                pair[1].get("added_at") or "",
                pair[0],
            ))
    ]


def build_export_document(workspace, state: dict, *, title: Optional[str] = None):
    """An ExportDocument of the recovered text, in source order.

    Uses document_export's own container so the .docx, .pdf and .xlsx writers
    cannot disagree about what this document contains.
    """
    from services.document_export import ExportDocument

    heading = title or (workspace.display_title or "Recovered document")
    document = ExportDocument(
        title=heading,
        subtitle="Text recovered from the uploaded source pages",
        preamble=[
            "This document contains text recovered from the source pages listed "
            "below, in the order they were added. It is a transcription of what "
            "was read, not an interpretation of it, and it establishes no "
            "project fact on its own - the original uploads remain the evidence.",
        ])

    for entry in state["ready"]:
        document.preamble.append("")
        document.preamble.append(entry["name"] or entry["source_id"])
        read_by = ", ".join(entry["read_by"]) if entry["read_by"] else None
        origin = ("read from the image by " + read_by) if entry.get("was_recovered") and read_by else (
            "text carried by the document itself" if entry.get("is_direct_source") else None)
        if origin:
            document.preamble.append("(" + origin + ")")
        document.preamble.extend(entry["passages"])

    return document


def create(store, workspace, source_ids, *, actor, sources_dir, governance_log=None,
           title: Optional[str] = None) -> dict:
    """Write one .docx from the recovered text of `source_ids`.

    Raises RecoveredDocumentError, with the unreadable sources named, rather
    than writing a document with holes in it.
    """
    from services.case_workspace import SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP  # noqa: F401  (existence check)
    from services.document_export import build

    if not source_ids:
        raise RecoveredDocumentError("There are no source pages to build from.")

    state = readiness(workspace, source_ids)
    if state["missing"]:
        names = ", ".join(entry.get("name") or entry["source_id"] for entry in state["missing"])
        raise RecoveredDocumentError(
            "No document was created, because text has not been recovered from: "
            + names + ". Re-run the examination on those pages first - writing "
            "the document now would leave them silently missing from it.")

    document = build_export_document(workspace, state, title=title)
    payload = build(document, "docx").getvalue()

    sources_dir = Path(sources_dir)
    sources_dir.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch for ch in (title or workspace.display_title or "recovered-document")
                   if ch.isalnum() or ch in " -_").strip() or "recovered-document"
    stored = sources_dir / (uuid.uuid4().hex + "_" + safe.replace(" ", "_") + ".docx")
    stored.write_bytes(payload)

    derivative = store.add_source(
        workspace, name=safe + ".docx", file_path=str(stored), kind="project_document",
        file_hash=hashlib.sha256(payload).hexdigest(),
        origin_type="derived_recovered_document",
        origin_reference=",".join(source_ids),
        actor=actor, governance_log=governance_log)

    return {
        "source_id": derivative["id"],
        "name": derivative["name"],
        "built_from": [entry["source_id"] for entry in state["ready"]],
        "page_count": sum(entry["page_count"] for entry in state["ready"]),
        "passage_count": sum(entry["passage_count"] for entry in state["ready"]),
        "character_count": sum(entry["character_count"] for entry in state["ready"]),
    }
