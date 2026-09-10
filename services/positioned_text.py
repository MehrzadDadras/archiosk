"""CLAUDE-GO-PERCEPTION-REGION-OCR-01 - what was read, and where it was read from.

Until now perception produced ONE UNPOSITIONED STRING per image. GO could say
what characters came back and had no way to say where on the drawing any of
them sat. This adds the second half - coordinates - and nothing else.

WHAT THIS DELIBERATELY IS NOT, because each was measurable and each was
rejected on the measurement rather than on taste:

- **Not a new reading.** The words come from the SAME PyMuPDF
  `get_textpage_ocr` call the shipped path already used, asked a second way.
  Verified on three real stored sources: 295 -> 295 and 866 -> 866 characters,
  character for character. Coordinates were added; the perception was not.
  That is the whole point - if the text changes, this module is at fault.

  It very nearly did. An earlier draft re-encoded every frame to PNG before
  reading it, which is the tidier thing to hand an OCR engine, and on an
  unrotated JPEG it recovered 9,548 characters where the shipped path recovers
  4,953 - at a HIGHER legible ratio, 0.631 against 0.426. A real improvement,
  found by accident, and deliberately not taken here: this tranche is
  authorized to attach coordinates, and quietly changing what every existing
  customer photograph yields is a different change that deserves its own
  measurement and its own decision. `services/image_intake.py` therefore hands
  over exactly the bytes and filetype `extract_image_text` would have. The
  finding is recorded rather than acted on.

- **Not a Tesseract TSV pipeline.** TSV carries per-word confidence and
  PyMuPDF does not, so TSV looked like the "least lossy" answer. Measured over
  four real sources it returned 0, 76, 623 and 0 words against PyMuPDF's 114,
  180, 1053 and 2152 - zero on half of them. Losing every word to keep a
  confidence number is not less lossy. Confidence is therefore NOT AVAILABLE
  here, and the module says so rather than inventing one.

- **Not a region second pass.** The measured PDF result (region + `--psm 4`
  doubling legibility on a title block) does not transfer to a photograph: a
  second pass over the blocks the first pass found recovered 0 words in 16.7
  extra seconds on the real drawing. `services/raster_extraction.py`'s region
  path stays what it is - a PDF path - and is not bent into an image path on
  the strength of a result measured somewhere else.

- **Not a confidence threshold.** Where confidence was available, a floor made
  things WORSE on the noisy source: keeping only conf>=30 dropped 74% of words
  and took legible-ratio 0.449 -> 0.290. Populations overlap; there is no
  separating value; none is invented.

COORDINATES ARE FRACTIONS, ON PURPOSE. PyMuPDF opens a PNG as a page whose
rect is the pixel size scaled by 72/96 - a 3024x4032 frame becomes a
2268x3024 page. Storing those numbers would be storing coordinates that only
mean anything if you also know which raster produced them, which is precisely
the ambiguity that makes a stored bbox worthless later. Every coordinate that
leaves this module is a 0-1 fraction of the ORIENTATION-NORMALIZED frame, and
the transform that produced it is reported alongside so the whole chain
original -> normalized -> OCR frame -> fraction stays reconstructible.
"""
from __future__ import annotations

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)

#: EvidenceItem.content_type for a positioned line. Deliberately NOT "text":
#: services/document_examination.py's own reader selects `content_type ==
#: "text"` and joins what it finds with blank lines to build the customer's
#: preview. Storing hundreds of positioned lines as "text" would turn that
#: preview into a column of disconnected fragments - the customer surface
#: regressing as a side effect of a storage change underneath it. A distinct
#: type keeps the two layers apart with no change to that reader at all.
POSITIONED_CONTENT_TYPE = "positioned_text"

#: The region shape. `create_addressable_drawing_region`'s own vocabulary,
#: reused rather than a new one - a positioned line IS a rectangular region of
#: the frame, which is exactly what that region type already means.
POSITIONED_REGION_TYPE = "rectangular"

#: Render resolution handed to the OCR engine. The value the shipped path
#: already uses (raster_extraction.RENDER_DPI); repeated here as an explicit
#: argument rather than inherited silently, because it is part of the
#: coordinate story and a reader should not have to go and find it.
OCR_RENDER_DPI = 200

#: A runaway guard, and honestly nothing more. The largest real source measured
#: produced 636 lines; this sits far above that so it never trims a genuine
#: reading, and exists only so a pathological frame cannot append an unbounded
#: number of records to a workspace that is rewritten in full on every save.
#: It is NOT a quality threshold and must never be described as one - when it
#: trips, that fact is recorded rather than the excess being silently dropped.
MAX_STORED_LINES = 2000


def is_legible_token(token: str) -> bool:
    """The repository's own token test, lifted from `legible_ratio`.

    Not a new heuristic - the identical rule
    services/raster_extraction.py:legible_ratio already applies to compare
    readings honestly, applied here to decide what is worth STORING. Reused
    rather than re-derived so the two can never drift into disagreeing about
    what a legible token is.
    """
    if not token:
        return False
    return (len(token) >= 3
            and sum(c.isalnum() for c in token) >= max(3, int(len(token) * 0.7)))


def _default_ocr(frame_bytes: bytes, dpi: int, filetype: str = "png"):
    """The real engine. Isolated so tests never need the binary installed.

    Returns `(words, page_rect, engine, version)` where `words` is PyMuPDF's
    own `(x0, y0, x1, y1, text, block, line, word)` tuples in PAGE POINTS.
    """
    from services import raster_extraction

    engine, version, pymupdf = raster_extraction._ocr_engine()
    tessdata = (raster_extraction.tessdata_path(pymupdf)
                if hasattr(pymupdf, "get_tessdata") else None)
    document = pymupdf.open(stream=frame_bytes, filetype=filetype)
    try:
        page = document.load_page(0)
        rect = (float(page.rect.width), float(page.rect.height))
        textpage = page.get_textpage_ocr(
            dpi=dpi, full=True, **({"tessdata": tessdata} if tessdata else {}))
        # ONE OCR pass, asked twice. `get_text(textpage=...)` and
        # `get_text("words", textpage=...)` both read the textpage that was
        # already produced - the plain text and the positioned words cost one
        # extraction between them, not two. Running the engine a second time
        # for coordinates would have doubled a job that already takes 5-21s.
        plain = page.get_text(textpage=textpage) or ""
        words = [tuple(w) for w in page.get_text("words", textpage=textpage)]
        return words, rect, engine, version, plain
    finally:
        try:
            document.close()
        except Exception:  # pragma: no cover - close failure is not a result
            pass


def _call_ocr(reader, frame_bytes: bytes, dpi: int, filetype: str):
    """Call the OCR seam, tolerating a reader that predates `filetype`.

    Tests inject two-argument readers, and they should not all have to change
    because the production path learned to keep a JPEG a JPEG.
    """
    try:
        return reader(frame_bytes, dpi, filetype)
    except TypeError:
        return reader(frame_bytes, dpi)


def read_positioned_lines(frame_bytes: bytes, frame_size, *,
                          filetype: str = "png",
                          dpi: int = OCR_RENDER_DPI, ocr=None) -> dict:
    """Read one normalized frame into positioned LINES. Never raises.

    `frame_size` is the orientation-normalized frame's own pixel size, and is
    the frame every returned coordinate is a fraction OF.

    Lines rather than words, decided by measurement rather than preference.
    Word-level regions for one real source came to 1,679 KB of JSON against
    502 KB for lines - and the largest workspace record anywhere in this system
    is 1,005 KB, rewritten in full on every save. Line geometry answers every
    interaction the viewer seam will actually need (hover a line, highlight it,
    click it, ask about it); word geometry costs 3.3x the store to answer none
    of them yet. The word count per line is kept so a later tranche can tell
    whether re-reading for word boxes is worth it.
    """
    result = {
        "ran": False, "engine": None, "engine_version": None, "reason": None,
        "text": "", "lines": [], "line_count": 0, "word_count": 0,
        "dropped_line_count": 0, "truncated": False,
        "confidence_available": False,
        "frame": None,
    }
    try:
        words, rect, engine, version, plain = _call_ocr(
            ocr or _default_ocr, frame_bytes, dpi, filetype)
    except Exception as exc:  # noqa: BLE001 - an unreadable frame is a result
        logger.warning("positioned OCR failed: %s: %s", type(exc).__name__, exc)
        result["reason"] = "positioned OCR failed (%s)" % type(exc).__name__
        return result

    result["ran"] = True
    result["engine"] = engine
    result["engine_version"] = version
    result["text"] = plain or ""

    frame_w, frame_h = (float(frame_size[0]), float(frame_size[1]))
    rect_w, rect_h = (float(rect[0]) or 1.0, float(rect[1]) or 1.0)
    result["frame"] = {
        "normalised_size": [int(frame_w), int(frame_h)],
        "ocr_frame_size": [rect_w, rect_h],
        # The factor that made this necessary, recorded rather than implied.
        # Coordinates below are already fractions, so nothing downstream needs
        # to apply this - it is here so the chain can be audited, and so a
        # future engine with a different convention is visibly different.
        "px_per_ocr_unit": [frame_w / rect_w, frame_h / rect_h],
        "render_dpi": dpi,
        "coordinate_space": "fraction_of_normalised_frame",
    }

    grouped: dict = {}
    order: list = []
    for word in words:
        if len(word) < 8:
            continue
        x0, y0, x1, y1, text, block_no, line_no, _word_no = word[:8]
        if not (text or "").strip():
            continue
        key = (block_no, line_no)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
        grouped[key].append((float(x0), float(y0), float(x1), float(y1), text))
        result["word_count"] += 1

    lines = []
    for key in order:
        items = grouped[key]
        text = " ".join(t for *_, t in items).strip()
        if not text:
            continue
        # GARBAGE CONTROL. A line survives if ANY of its tokens passes the
        # repository's own legible test. Measured over four real sources this
        # keeps 80% of lines on a clean scan and 13% on the noise-dominated
        # photograph - which is the correct asymmetry, and the reason the rule
        # is a per-token test rather than a per-source one. It is not a
        # quality claim about what survives; it is a refusal to store what is
        # obviously not text at all.
        if not any(is_legible_token(t) for *_, t in items):
            result["dropped_line_count"] += 1
            continue
        # Clamped to the OCR frame BEFORE the fraction is taken, not after.
        # Clamping x and width independently afterwards can produce
        # x + width > 1 - a box that leaves the drawing - and the store is
        # right to refuse those. Constraining the corners here means the
        # fractions below cannot express one.
        x0 = max(0.0, min(rect_w, min(a for a, _, _, _, _ in items)))
        y0 = max(0.0, min(rect_h, min(b for _, b, _, _, _ in items)))
        x1 = max(0.0, min(rect_w, max(c for _, _, c, _, _ in items)))
        y1 = max(0.0, min(rect_h, max(d for _, _, _, d, _ in items)))
        lines.append({
            "x": max(0.0, min(1.0, x0 / rect_w)),
            "y": max(0.0, min(1.0, y0 / rect_h)),
            "width": max(0.0, min(1.0, (x1 - x0) / rect_w)),
            "height": max(0.0, min(1.0, (y1 - y0) / rect_h)),
            "text": text,
            "word_count": len(items),
            "block_index": int(key[0]),
            "line_index": int(key[1]),
        })

    if len(lines) > MAX_STORED_LINES:
        result["truncated"] = True
        lines = lines[:MAX_STORED_LINES]

    # A zero-extent line is a real OCR outcome and an unusable region: the
    # store refuses non-positive width/height, and it should - a box you
    # cannot point at is not an address. Dropped here with the rest rather
    # than raising at the write.
    usable = [ln for ln in lines if ln["width"] > 0 and ln["height"] > 0]
    result["dropped_line_count"] += len(lines) - len(usable)
    result["lines"] = usable
    result["line_count"] = len(usable)
    return result
