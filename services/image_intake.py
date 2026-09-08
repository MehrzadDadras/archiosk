"""CLAUDE-BLACK-BOX-IMAGE-INTAKE-01 - a standalone image at the intake door.

IMAGE INTAKE DOES NOT IMPLY IMAGE EGRESS.

Nothing in this module makes a network call, and nothing in it may be extended
to. A scanned page is exactly the material a customer brings to a Document Shop
and exactly the material they would least expect to leave the building. Local
decoding and local OCR are what this authorizes; sending pixels to a vision
provider remains a separate, separately-granted decision that lives in
services/sheet_vision.py behind its own conjunctive gate.

WHAT THIS IS FOR, AND WHAT IT REFUSES

An uploaded file arrives as bytes with a name attached, and the name is the
least trustworthy thing about it. `verify_image_bytes` never consults the
extension for truth: it reads the magic signature, decodes with Pillow's own
verify(), and bounds the DECLARED pixel geometry BEFORE any full decode - the
same pre-flight ordering services/sheet_vision.py's own bounded rasterization
established, and for the same reason. Checking size after decoding is checking
the bomb after it has gone off.

DELIBERATELY NOT A MIME FRAMEWORK

Three formats, one decoder, one signature table. PNG and JPEG only; TIFF is
excluded because multi-frame handling is a genuinely different problem and is
its own future tranche, not a flag on this one.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

#: The only founding image formats this tranche admits. TIFF/HEIC/WEBP/BMP/SVG
#: are all deliberately absent - see the module docstring.
IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})

#: Magic signatures, checked against the bytes rather than the filename.
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"

#: Matches services/image_intelligence.py's own MAX_RAW_BYTES rather than
#: inventing a second number - one image-size rule for this application, and a
#: reader who changes one will find the other named here.
MAX_IMAGE_BYTES = 40 * 1024 * 1024

#: Pillow's own default decompression-bomb guard is ~89M pixels and is NOT
#: relaxed anywhere here. This lower bound is the intake policy: a 50-megapixel
#: scan is already far beyond a document page, and refusing early means the
#: full decode never runs.
MAX_IMAGE_PIXELS = 50_000_000

#: A single dimension beyond this is a malformed or hostile header long before
#: it is a real scan.
MAX_IMAGE_DIMENSION = 30_000

VERIFIED = "verified"
REJECTED_NOT_AN_IMAGE = "not_an_image"
REJECTED_SIGNATURE_MISMATCH = "signature_mismatch"
REJECTED_TOO_MANY_BYTES = "too_many_bytes"
REJECTED_TOO_MANY_PIXELS = "too_many_pixels"
REJECTED_MALFORMED = "malformed"

#: One sentence per refusal, stated in the reader's terms. Never leaks a
#: library exception, a path, or an internal limit name.
_REASONS = {
    REJECTED_NOT_AN_IMAGE:
        "That file is not a PNG or JPEG image, whatever its name says.",
    REJECTED_SIGNATURE_MISMATCH:
        "That file's contents do not match its extension.",
    REJECTED_TOO_MANY_BYTES:
        "That image is too large to accept.",
    REJECTED_TOO_MANY_PIXELS:
        "That image's dimensions are beyond what can be processed safely.",
    REJECTED_MALFORMED:
        "That image could not be read - it may be incomplete or corrupt.",
}


def is_supported_image(filename: str) -> bool:
    """Does this NAME claim to be a supported image? Never proof of content."""
    return Path(filename or "").suffix.lower() in IMAGE_EXTENSIONS


def rejection_reason(status: str) -> Optional[str]:
    return _REASONS.get(status)


def _signature_matches(raw_bytes: bytes, ext: str) -> bool:
    if ext == ".png":
        return raw_bytes.startswith(_PNG_SIGNATURE)
    return raw_bytes.startswith(_JPEG_SIGNATURE)


def verify_image_bytes(raw_bytes: bytes, filename: str) -> dict:
    """Is this really the image it claims to be, and is it safe to decode?

    Returns {"status", "reason", "format", "width", "height"} and NEVER raises.
    A hostile upload is a result, not an exception - the same discipline
    services/spreadsheet_intelligence.py's inspect_workbook already uses for
    the equivalent question about a workbook.

    Order matters and is deliberate:
      1. byte ceiling, before anything touches a decoder;
      2. magic signature, so a renamed executable never reaches Pillow;
      3. Pillow verify(), which parses headers without decoding pixel data;
      4. declared geometry bounds, BEFORE any full decode.
    """
    ext = Path(filename or "").suffix.lower()
    empty = {"format": None, "width": None, "height": None}

    if ext not in IMAGE_EXTENSIONS:
        return {"status": REJECTED_NOT_AN_IMAGE,
                "reason": _REASONS[REJECTED_NOT_AN_IMAGE], **empty}
    if not raw_bytes:
        return {"status": REJECTED_MALFORMED,
                "reason": _REASONS[REJECTED_MALFORMED], **empty}
    if len(raw_bytes) > MAX_IMAGE_BYTES:
        return {"status": REJECTED_TOO_MANY_BYTES,
                "reason": _REASONS[REJECTED_TOO_MANY_BYTES], **empty}
    if not _signature_matches(raw_bytes, ext):
        return {"status": REJECTED_SIGNATURE_MISMATCH,
                "reason": _REASONS[REJECTED_SIGNATURE_MISMATCH], **empty}

    try:
        from PIL import Image
    except Exception:  # pragma: no cover - Pillow is a hard dependency
        return {"status": REJECTED_MALFORMED,
                "reason": _REASONS[REJECTED_MALFORMED], **empty}

    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            declared_format = (probe.format or "").upper()
            width, height = probe.size
            # verify() parses structure and detects truncation WITHOUT
            # decoding the pixel data - which is the whole point of doing it
            # before the bounds check below has let anything expensive happen.
            probe.verify()
    except Exception as exc:  # noqa: BLE001 - a bad image is a result
        logger.info("Image intake rejected %r: %s", filename, exc.__class__.__name__)
        return {"status": REJECTED_MALFORMED,
                "reason": _REASONS[REJECTED_MALFORMED], **empty}

    if declared_format not in ("PNG", "JPEG"):
        # An unsupported type wearing a supported extension - e.g. a GIF or
        # WEBP renamed to .png. The signature check above catches most, this
        # catches the rest by asking the decoder what it actually parsed.
        return {"status": REJECTED_SIGNATURE_MISMATCH,
                "reason": _REASONS[REJECTED_SIGNATURE_MISMATCH], **empty}

    if (width or 0) > MAX_IMAGE_DIMENSION or (height or 0) > MAX_IMAGE_DIMENSION \
            or (width or 0) * (height or 0) > MAX_IMAGE_PIXELS:
        return {"status": REJECTED_TOO_MANY_PIXELS,
                "reason": _REASONS[REJECTED_TOO_MANY_PIXELS],
                "format": declared_format, "width": width, "height": height}

    return {"status": VERIFIED, "reason": None, "format": declared_format,
            "width": width, "height": height}


def extract_image_text(raw_bytes: bytes, filename: str, *, engine=None) -> dict:
    """Local OCR over a standalone image. Never raises, never egresses.

    A bounded ADAPTER, not a second pipeline: it hands the bytes to
    services/raster_extraction.py's existing governed path with the image's own
    filetype instead of "pdf", so engine resolution, tessdata discovery, the
    derived-evidence contract and the honest "no engine installed" outcome are
    all the ones already built and tested for scanned PDFs.

    Returns the same shape that module returns, with `text` flattened for the
    single frame an image has.
    """
    from services import raster_extraction

    ext = Path(filename or "").suffix.lower()
    filetype = "png" if ext == ".png" else "jpeg"
    result = raster_extraction.extract_raster_pages(
        raw_bytes, [0], filetype=filetype, engine=engine)
    pages = result.get("pages") or {}
    return {
        "ran": result.get("ran", False),
        "status": result.get("status"),
        "engine": result.get("engine"),
        "engine_version": result.get("engine_version"),
        "reason": result.get("reason"),
        # Empty string, never a fabricated placeholder - an image that yielded
        # nothing yielded nothing, and As-Read must be able to say so.
        "text": pages.get(0, ""),
    }
