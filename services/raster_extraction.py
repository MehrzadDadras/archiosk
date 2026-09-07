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

import glob
import logging
import os
import shutil
import subprocess
import tempfile
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

#: Region renders go higher than whole-page renders. A region is a small
#: fraction of a 42x30in sheet, so the pixel cost is affordable where it is not
#: for the full page - and annotation text is exactly where the extra
#: resolution decides whether a character is legible at all.
REGION_RENDER_DPI = 300

#: Tesseract page segmentation mode for a region. 4 ("a single column of text of
#: variable sizes") measured best on a real title block: legible-token ratio
#: 0.50 against 0.23 for the default and 0.23 for psm 6. Not a tuned threshold -
#: a documented mode chosen from a recorded comparison, and overridable.
DEFAULT_REGION_PSM = 4

#: A region is small; a minute is generous and stops a pathological render from
#: hanging an ingestion.
REGION_OCR_TIMEOUT_SECONDS = 60

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


def tessdata_path(pymupdf_module) -> Optional[str]:
    """Where Tesseract's language data lives, or None.

    Resolved and passed EXPLICITLY to `get_textpage_ocr` rather than relying on
    the service environment carrying `TESSDATA_PREFIX`. Mutating a running
    service's environment to make a feature work is the kind of invisible
    coupling that survives until the day someone restarts it differently.
    """
    try:
        found = pymupdf_module.get_tessdata()
        if found:
            return str(found)
    except Exception:
        pass
    for candidate in sorted(glob.glob("/usr/share/tesseract-ocr/*/tessdata")):
        if os.path.isdir(candidate):
            return candidate
    prefix = os.environ.get("TESSDATA_PREFIX")
    if prefix and os.path.isdir(prefix):
        return prefix
    return None


def _ocr_engine():
    """The optional OCR seam. Returns (engine_name, version, pymupdf module).

    PyMuPDF is already a pinned dependency and can both rasterise a page and
    drive Tesseract through `get_textpage_ocr`, so the Python dependency graph
    gains NOTHING here - which mattered: the pure-pip alternative pulls
    onnxruntime, opencv, shapely and protobuf (~89 MB) and has no cp310
    manylinux wheel for the production interpreter.

    Availability is decided by the ACTUAL executable, not by a PyMuPDF helper.
    An earlier version of this check asked `pymupdf.TOOLS.tesseract_version()`,
    which does not exist in PyMuPDF 1.28.2 on either dev or production - so it
    reported "no engine" unconditionally, and would have kept reporting it after
    Tesseract was correctly installed. The tests still passed because they
    asserted the degrade path, and the degrade path was firing for the wrong
    reason. Probing the binary is the check that cannot be wrong in that way.
    """
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - pymupdf is pinned
        raise RasterExtractionUnavailable(
            "PyMuPDF is not installed, so PDF pages cannot be rendered.") from exc

    if not hasattr(pymupdf.Page, "get_textpage_ocr"):  # pragma: no cover
        raise RasterExtractionUnavailable(
            "This PyMuPDF build cannot drive OCR (no get_textpage_ocr).")

    executable = shutil.which("tesseract")
    if not executable:
        raise RasterExtractionUnavailable(
            "The Tesseract OCR engine is not installed on this host, so an "
            "image-only page cannot be read. Install tesseract-ocr "
            "(deploy/DEPLOYMENT.md section 7A).")

    if tessdata_path(pymupdf) is None:
        raise RasterExtractionUnavailable(
            "Tesseract is installed but its language data could not be found. "
            "Set TESSDATA_PREFIX to the tessdata directory.")

    version = "unknown"
    try:
        completed = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, timeout=10)
        first = (completed.stdout or completed.stderr or "").strip().splitlines()
        if first:
            parts = first[0].split()
            version = parts[1] if len(parts) > 1 else first[0]
    except Exception:  # noqa: BLE001 - an unreadable version is not a failure
        pass
    return ENGINE_TESSERACT, version, pymupdf


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

    tessdata = tessdata_path(pymupdf) if hasattr(pymupdf, "get_tessdata") else None
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
                textpage = page.get_textpage_ocr(
                    dpi=dpi, full=True, **({"tessdata": tessdata} if tessdata else {}))
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


def _tesseract_reader(png_bytes: bytes, psm: int, tessdata: Optional[str]) -> str:
    """Run Tesseract over one rendered region and return its text.

    Shells to the binary rather than using PyMuPDF's in-process OCR because the
    page segmentation mode has to be settable, and neither `get_textpage_ocr`
    nor `pdfocr_tobytes` exposes it. That is not a preference: on the real E1
    sheet, the same region read at the default mode scored 0.23 on legible
    tokens and at `--psm 4` scored 0.50.
    """
    with tempfile.TemporaryDirectory(prefix="archiosk-ocr-") as directory:
        image_path = os.path.join(directory, "region.png")
        with open(image_path, "wb") as handle:
            handle.write(png_bytes)
        environment = dict(os.environ)
        if tessdata:
            environment["TESSDATA_PREFIX"] = tessdata
        completed = subprocess.run(
            [shutil.which("tesseract") or "tesseract", image_path, "stdout",
             "--psm", str(psm)],
            capture_output=True, text=True, timeout=REGION_OCR_TIMEOUT_SECONDS,
            env=environment)
        return completed.stdout or ""


def extract_region_text(raw_bytes: bytes, page_index: int, rect, *,
                        dpi: int = REGION_RENDER_DPI, rotate: int = 0,
                        psm: int = DEFAULT_REGION_PSM,
                        engine=None, reader=None) -> dict:
    """OCR ONE region of a page, in source-page coordinates. Never raises.

    Whole-sheet OCR of a large drawing is close to worthless: measured on the
    real 42x30in E-size sheet it returned 2,598 characters at a legible-token
    ratio of 0.17 - length that reads as success and is almost entirely
    fragments.

    Two things fix it, and they were measured separately so the credit lands on
    the right one. Narrowing to a REGION took legibility 0.17 -> 0.23 and cut the
    time roughly fourfold. Setting the page segmentation mode took it 0.23 ->
    0.50. The region is necessary; the mode is what actually doubles it.

    `rect` stays in SOURCE PAGE coordinates and the document is never modified;
    `rotate` is applied to the RENDER only, which is how a sideways sheet is read
    without rotating the authoritative page. `reader` is the injectable OCR seam
    so tests never need the binary installed.
    """
    try:
        engine_name, engine_version, pymupdf = engine or _ocr_engine()
    except RasterExtractionUnavailable as exc:
        return {"ran": False, "text": "", "engine": None, "engine_version": None,
                "reason": str(exc), "rect": list(rect), "page_index": page_index,
                "rotate": rotate, "psm": psm}

    tessdata = tessdata_path(pymupdf) if hasattr(pymupdf, "get_tessdata") else None
    try:
        document = pymupdf.open(stream=raw_bytes, filetype="pdf")
    except Exception as exc:  # noqa: BLE001
        return {"ran": False, "text": "", "engine": engine_name,
                "engine_version": engine_version,
                "reason": "The PDF could not be opened (%s)." % type(exc).__name__,
                "rect": list(rect), "page_index": page_index, "rotate": rotate,
                "psm": psm}

    try:
        page = document.load_page(page_index)
        matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
        if rotate:
            matrix = matrix * pymupdf.Matrix(rotate)
        pixmap = page.get_pixmap(matrix=matrix, clip=pymupdf.Rect(*rect))
        png_bytes = pixmap.tobytes("png")
        text = (reader or _tesseract_reader)(png_bytes, psm, tessdata) or ""
    except Exception as exc:  # noqa: BLE001 - a failed region is a result
        logger.warning("Region OCR failed on page %d: %s", page_index, exc)
        return {"ran": False, "text": "", "engine": engine_name,
                "engine_version": engine_version,
                "reason": "Region OCR failed (%s)." % type(exc).__name__,
                "rect": list(rect), "page_index": page_index, "rotate": rotate,
                "psm": psm}
    finally:
        try:
            document.close()
        except Exception:  # pragma: no cover
            pass

    return {"ran": True, "text": text, "engine": engine_name,
            "engine_version": engine_version, "reason": None,
            "rect": list(rect), "page_index": page_index, "rotate": rotate,
            "dpi": dpi, "psm": psm}


def legible_ratio(text: str) -> float:
    """Share of tokens that look like real words or codes rather than noise.

    A blunt, deterministic signal - NOT a quality score and never used to accept
    or reject content. It exists so region OCR and whole-sheet OCR can be
    COMPARED honestly: "2,598 characters" sounds like success until you see that
    almost none of the tokens are words.
    """
    tokens = [t for t in (text or "").split() if t]
    if not tokens:
        return 0.0
    legible = sum(
        1 for t in tokens
        if len(t) >= 3 and sum(c.isalnum() for c in t) >= max(3, int(len(t) * 0.7)))
    return legible / len(tokens)


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
