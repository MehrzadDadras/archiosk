"""
Raster/OCR fallback - recovering text from image-only PDFs.

WHERE THIS SITS, AND WHY IT IS NOT A "VISION SPIN"

Spin is a review/analysis consumer: it reads governed evidence. A drawing that
produced no evidence is not a Spin problem, it is an EXTRACTION problem, and it
has to be solved upstream or every downstream consumer inherits the same hole.
So this module runs during ingestion, feeds the same governed registration path
native extraction uses, and Spin never learns that anything unusual happened.

PER PAGE, NOT PER DOCUMENT - WHICH IS ALSO THE DE-DUPLICATION RULE

`BHiveParser.extract_pdf_pages` already returns per-page native text. The
fallback therefore asks a much narrower question than "did this document fail":
it asks, of each page, "did THIS page yield text?" and renders only the pages
that did not.

That is what makes a mixed PDF work - a vector title sheet and a scanned detail
in one file each get the right treatment - and it is also why duplicate evidence
is structurally impossible rather than something to de-duplicate afterwards.
Native text and OCR text can never describe the same page, because a page with
native text is never rendered. Native always wins where it exists; this module
cannot overwrite it.

DERIVED EVIDENCE, NEVER THE SOURCE

The original PDF is never modified, re-saved or replaced. OCR output is DERIVED:
it is registered with the OCR engine as `created_by`, the engine version as
`extractor_version`, and a confidence, so a reader can always tell recovered
text from text the document actually contained. CURRENT STATE MUST NOT LAUNDER
SOURCE ORIGIN - a recovered string is a reading of an image, not something the
document says.

AN ABSENT ENGINE IS AN HONEST OUTCOME

The OCR engine is an optional runtime dependency behind `_ocr_engine()`, the
same seam-and-degrade shape `services/llm_gateway.py:_import_google_genai`
already uses for `google-genai`. When it is missing the fallback reports
UNREADABLE with the reason naming the missing engine. It never guesses, never
fabricates text, and never turns "I could not read this" into silence.

WHAT THIS DELIBERATELY DOES NOT DO

It recovers TEXT. It does not reconstruct geometry, vectorise, redraw, or infer
anything about the drawing. OCR text is not CAD, and a module that blurred the
two would be making a claim about the drawing that nobody measured.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)

#: Read-time status for recovered content. Deliberately three states, not a
#: boolean: "we read something but you should check it" is the common and most
#: dangerous case, and it needs a name of its own.
RASTER_STATUS_READABLE = "readable"
RASTER_STATUS_REVIEW_NEEDED = "review_needed"
RASTER_STATUS_UNREADABLE = "unreadable"

#: A page carrying less than this many non-whitespace characters of native text
#: is treated as having no usable text layer. A scanned page often yields a
#: stray ligature or a stamp artefact from pypdf; one or two characters is not a
#: text layer, and treating it as one is how a raster page silently skips the
#: fallback it needed.
MIN_USABLE_NATIVE_CHARS = 12

#: Below this, recovered text is REVIEW_NEEDED rather than READABLE. It is a
#: reporting threshold only - nothing is discarded for being low confidence,
#: because discarding it would hide the fact that the page was hard to read.
CONFIDENCE_REVIEW_THRESHOLD = 0.70

#: Render resolution. High enough for the small annotation text on a drawing,
#: low enough that a large sheet set does not exhaust memory.
RENDER_DPI = 200

ENGINE_TESSERACT = "tesseract"


class RasterExtractionUnavailable(Exception):
    """No OCR engine is installed. An honest condition, not a failure."""


def page_has_usable_text(text: Optional[str]) -> bool:
    """Does this page carry a real native text layer?"""
    return len((text or "").strip()) >= MIN_USABLE_NATIVE_CHARS


def needs_raster_fallback(native_pages: list) -> list:
    """Indices of the pages with no usable native text.

    An empty list means every page was readable natively and this module must
    not run at all - the native path stays authoritative wherever it worked.
    """
    return [i for i, text in enumerate(native_pages or []) if not page_has_usable_text(text)]


def _ocr_engine():
    """The optional OCR seam. Returns (engine_name, version, ocr_callable).

    PyMuPDF is already a pinned dependency and can both rasterise a page and
    drive Tesseract through `get_textpage_ocr`, so the Python dependency graph
    gains NOTHING here - which mattered: the alternative pure-pip engine pulls
    onnxruntime, opencv, shapely and protobuf (~89 MB) and has no cp310
    manylinux wheel for the production interpreter.

    What it does require is the Tesseract binary. Raising rather than returning
    a stub keeps the absence loud at exactly one place.
    """
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - pymupdf is pinned
        raise RasterExtractionUnavailable(
            "PyMuPDF is not installed, so PDF pages cannot be rendered.") from exc

    try:
        have = pymupdf.TOOLS.tesseract_version()
    except Exception:
        have = None
    if not have:
        raise RasterExtractionUnavailable(
            "The Tesseract OCR engine is not installed on this host, so an "
            "image-only page cannot be read. Install tesseract-ocr and set "
            "TESSDATA_PREFIX.")
    return ENGINE_TESSERACT, str(have), pymupdf


def ocr_availability() -> dict:
    """Can this host run the fallback at all? Safe to call anywhere."""
    try:
        engine, version, _ = _ocr_engine()
        return {"available": True, "engine": engine, "engine_version": version, "reason": None}
    except RasterExtractionUnavailable as exc:
        return {"available": False, "engine": None, "engine_version": None,
                "reason": str(exc)}


def extract_raster_pages(raw_bytes: bytes, page_indices: list, *,
                         dpi: int = RENDER_DPI, engine=None) -> dict:
    """Render the named pages and read them. Never raises.

    `engine` is injectable so tests drive this at the seam rather than
    depending on a binary being installed on whichever machine runs them - the
    same discipline every other external boundary in this repository uses.
    """
    try:
        engine_name, engine_version, pymupdf = engine or _ocr_engine()
    except RasterExtractionUnavailable as exc:
        return {"ran": False, "status": RASTER_STATUS_UNREADABLE, "pages": {},
                "engine": None, "engine_version": None, "reason": str(exc)}

    recovered, failures = {}, []
    try:
        document = pymupdf.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001 - an unreadable PDF is a result, not a crash
        logger.warning("Raster fallback could not open the PDF: %s", exc)
        return {"ran": False, "status": RASTER_STATUS_UNREADABLE, "pages": {},
                "engine": engine_name, "engine_version": engine_version,
                "reason": "The PDF could not be opened for rendering."}

    try:
        for index in page_indices:
            if index < 0 or index >= document.page_count:
                continue
            try:
                page = document.load_page(index)
                textpage = page.get_textpage_ocr(dpi=dpi, full=True)
                text = page.get_text(textpage=textpage) or ""
            except Exception as exc:  # noqa: BLE001 - one bad page must not lose the rest
                logger.warning("Raster fallback failed on page %d: %s", index, exc)
                failures.append(index)
                continue
            if text.strip():
                recovered[index] = text
    finally:
        try:
            document.close()
        except Exception:  # pragma: no cover
            pass

    if not recovered:
        return {"ran": True, "status": RASTER_STATUS_UNREADABLE, "pages": {},
                "engine": engine_name, "engine_version": engine_version,
                "reason": ("Image-based extraction could not recover sufficient "
                           "readable information from this document.")}

    status = (RASTER_STATUS_READABLE
              if len(recovered) == len(page_indices) and not failures
              else RASTER_STATUS_REVIEW_NEEDED)
    return {"ran": True, "status": status, "pages": recovered,
            "engine": engine_name, "engine_version": engine_version,
            "failed_pages": failures, "reason": None}


def merge_pages(native_pages: list, recovered: dict) -> list:
    """Native text where it exists, recovered text only where it did not.

    The de-duplication rule, expressed as the one place it can be enforced: a
    page index present in `native_pages` with usable text is never overwritten,
    so the same page can never carry two extractions.
    """
    merged = list(native_pages or [])
    for index, text in (recovered or {}).items():
        if 0 <= index < len(merged) and not page_has_usable_text(merged[index]):
            merged[index] = text
    return merged


def user_message(status: str, recovered_count: int, total_pages: int) -> str:
    """The honest sentence for each outcome, in the existing UX register."""
    if status == RASTER_STATUS_READABLE:
        return ("Raster drawing detected. ARCHIOSK used image-based text extraction. "
                "Original drawing preserved. Extracted text may require review.")
    if status == RASTER_STATUS_REVIEW_NEEDED:
        return ("Raster drawing processed with limited readable content (%d of %d "
                "image pages). Review extracted annotations before relying on them."
                % (recovered_count, total_pages))
    return ("Drawing registered, but image-based extraction could not recover "
            "sufficient readable information.")
