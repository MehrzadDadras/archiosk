"""
Shared upload-handling glue between routes/api.py and routes/portal.py.

Both blueprints accept an uploaded RFP/RFQ and need the same validate ->
parse -> save sequence, so it lives here once rather than being
duplicated (and drifting) across a JSON endpoint and an HTML form handler.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from flask import Flask
from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument, ParserError
from services.requirements_registry import RequirementsRegistry


class UploadError(Exception):
    """Raised for invalid uploads (missing file, bad extension, unparsable content)."""


def get_registry(app: Flask) -> RequirementsRegistry:
    return RequirementsRegistry(app.config["REGISTRY_STORE_PATH"])


def ingest_upload(file_storage: Optional[FileStorage], app: Flask) -> ParsedDocument:
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

    raw_bytes = file_storage.read()
    parser = BHiveParser(
        anthropic_api_key=app.config.get("ANTHROPIC_API_KEY"),
        model=app.config.get("ANTHROPIC_MODEL"),
    )
    try:
        document = parser.parse(raw_bytes, filename)
    except ParserError as exc:
        raise UploadError(str(exc)) from exc

    get_registry(app).save(document)
    return document
