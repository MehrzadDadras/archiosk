"""CLAUDE-SURVEY-REFERENCE-01 - what kind of file is this, really.

The answer used to come from the DISPLAY NAME, and that is the whole of the
reported defect's first symptom. `document_shop_intake` assigns a work-item
display name ("226104 1 Castille") after the batch is complete, deliberately -
the project name is the work's identity, the filename is the evidence's. A
reader that then asks the display name for a file extension gets none, and a
JPEG survey is reported as

    Kind of file: a file of type unknown

with every downstream image branch skipped, because nothing downstream believed
it was an image either.

    A FILE'S TYPE IS A PROPERTY OF ITS BYTES, NOT OF WHAT ANYONE CALLED IT.

So this module reads the signature. The extension is consulted only as a
fallback, and when it is, `identified_from` says so rather than letting a guess
wear the same face as a reading.

CLOSED VOCABULARY, ON PURPOSE. `mimetypes.guess_type` knows hundreds of types
including active ones and answers from a filename; routes/workspace.py already
refuses it for exactly that reason and keeps its own closed map. This module is
the same decision applied to the question one layer earlier, and the two agree
because the set of things this application can hold is small and known.

NOT A SECOND VERIFICATION PATH. `image_intake.verify_image_bytes` remains the
gate that decides whether an image may be stored and decoded - signature,
structure, declared geometry, byte ceiling. This asks a narrower question, of
an already-stored file, for a reader: what is it. It never admits, refuses or
decodes anything.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

#: Enough bytes for every signature below, and few enough that identifying a
#: 40 MB photograph costs a header read rather than a file read.
HEAD_BYTES = 512

FAMILY_RASTER_IMAGE = "raster_image"
FAMILY_PDF = "pdf"
FAMILY_WORD_DOCUMENT = "word_document"
FAMILY_SPREADSHEET = "spreadsheet"
FAMILY_TEXT = "text"
FAMILY_UNKNOWN = "unknown"

IDENTIFIED_FROM_CONTENT = "content"
IDENTIFIED_FROM_EXTENSION = "extension"
IDENTIFIED_FROM_NOTHING = "nothing"

#: Plain language, for a person who uploaded a file. The same register
#: `document_examination` has always used - "an image (JPEG)", not "image/jpeg".
_LABELS = {
    "image/png": "an image (PNG)",
    "image/jpeg": "an image (JPEG)",
    "application/pdf": "a PDF document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        "a Word document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        "an Excel workbook",
    "text/plain": "a plain text file",
    "text/csv": "a comma-separated data file",
    "text/markdown": "a text document",
}

_FAMILIES = {
    "image/png": FAMILY_RASTER_IMAGE,
    "image/jpeg": FAMILY_RASTER_IMAGE,
    "application/pdf": FAMILY_PDF,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        FAMILY_WORD_DOCUMENT,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        FAMILY_SPREADSHEET,
    "text/plain": FAMILY_TEXT,
    "text/csv": FAMILY_TEXT,
    "text/markdown": FAMILY_TEXT,
}

_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".md": "text/markdown",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PDF_SIGNATURE = b"%PDF-"
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")


def _sniff(head: bytes) -> Optional[str]:
    """The media type the BYTES establish, or None.

    A .docx and a .xlsx are both zip containers, and the first local file
    header does not reliably name which - so a zip resolves to None here and
    the extension decides, which is honest about where that answer came from.
    """
    if not head:
        return None
    if head.startswith(_PNG_SIGNATURE):
        return "image/png"
    if head.startswith(_JPEG_SIGNATURE):
        return "image/jpeg"
    if head.startswith(_PDF_SIGNATURE):
        return "application/pdf"
    if any(head.startswith(signature) for signature in _ZIP_SIGNATURES):
        return None
    return None


def identify(head: bytes, filename: str = "") -> dict:
    """What this file is. NEVER RAISES.

    Returns {"media_type", "family", "label", "identified_from", "extension"}.
    `media_type` is None only when neither the bytes nor the extension say
    anything, and `label` then names the extension rather than the word
    "unknown" on its own - "a file of type .heic" is a real answer; "unknown"
    is the absence of one.
    """
    extension = Path(filename or "").suffix.lower()
    sniffed = _sniff(head or b"")
    if sniffed:
        media_type, identified_from = sniffed, IDENTIFIED_FROM_CONTENT
    elif extension in _BY_EXTENSION:
        media_type, identified_from = _BY_EXTENSION[extension], IDENTIFIED_FROM_EXTENSION
    else:
        media_type, identified_from = None, IDENTIFIED_FROM_NOTHING

    if media_type is None:
        label = ("a file of type %s" % extension) if extension else "a file of an unrecognised type"
        return {"media_type": None, "family": FAMILY_UNKNOWN, "label": label,
                "identified_from": identified_from, "extension": extension}

    return {
        "media_type": media_type,
        "family": _FAMILIES.get(media_type, FAMILY_UNKNOWN),
        "label": _LABELS.get(media_type, media_type),
        "identified_from": identified_from,
        "extension": extension,
    }


def identify_path(path) -> dict:
    """`identify` for a stored file, reading only its head. Never raises."""
    candidate = Path(path or "")
    try:
        with candidate.open("rb") as handle:
            head = handle.read(HEAD_BYTES)
    except OSError:
        head = b""
    return identify(head, candidate.name)


def is_raster_image(identity: dict) -> bool:
    return (identity or {}).get("family") == FAMILY_RASTER_IMAGE
