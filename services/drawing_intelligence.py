"""
CLAUDE-MM4: Drawing Intelligence and Orientation-Normalized Comparison -
the thin orchestration layer between a real drawing read (pypdf for a
drawing-oriented PDF, Pillow for a standalone PNG/JPEG) and the MM1
evidence contract (services/case_workspace.py's own
`register_drawing_sheet_structure`/`create_addressable_drawing_region`).
Exists specifically so case_workspace.py does not have to import pypdf or
PIL directly - the same decoupling services/pdf_intelligence.py and
services/spreadsheet_intelligence.py already established for their own
libraries.

Capability boundary, stated up front (reusing services/drawing_intake.py's
own 2026-08-04 repository-grounded audit rather than re-deriving it): no
PDF-to-image rendering, no local OCR, no automatic symbol/room/dimension
recognition, no authoritative measurement from an uncalibrated page or
image. Title-block field extraction reuses drawing_intake.py's own
LABEL: VALUE pattern vocabulary (same technique, applied per-PAGE here
rather than once per whole document, since a multi-sheet drawing set has
a different title block on every sheet - drawing_intake.py's own
aggregate-across-the-whole-document shape is right for ITS use case,
project-identity qualification from a cover sheet, and wrong for this
one).

This module also owns the one piece of genuinely new geometry MM4 needs:
a small, pure, deterministic coordinate-transform pair (`transform_point_
to_display`/`transform_point_to_original`, and their rectangle-shaped
counterparts) describing how a reviewer's rotate/mirror VIEW state maps
between a drawing sheet's ORIGINAL stored frame and whatever the browser
currently renders. Every AddressableRegion this module's own
`create_drawing_region_and_evidence` creates is always stored in the
ORIGINAL frame (Section 7: "citations and evidence anchors remain bound
to original source coordinates") - these functions are how a caller
(the region-creation route, or client-side JS re-implementing the same
composition for live pointer feedback) converts a displayed selection
back into that frame, and how an already-stored region is mapped INTO
whatever transform is currently active for redisplay. No PDF/image
library is needed to reason about this geometry - it operates purely on
normalized 0-1 fractions, which is why it lives here as ordinary
functions rather than as PdfReader/PIL-dependent code.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image, UnidentifiedImageError

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    DRAWING_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    DRAWING_CLASSIFICATION_EXCESSIVE_SIZE,
    DRAWING_CLASSIFICATION_MALFORMED,
    DRAWING_CLASSIFICATION_SUPPORTED,
    EVIDENCE_CLASS_DIRECT_SOURCE,
    METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
    METADATA_RELIABILITY_INFERRED,
    METADATA_RELIABILITY_UNAVAILABLE,
    ProjectWorkspace,
)
from services.drawing_intake import (
    FIELD_LABELS,
    _FIELD_PATTERNS,
    _SHEET_PREFIX_DISCIPLINE,
    _SHEET_PREFIX_RE,
)
from services.governance import GovernanceLog

DRAWING_EXTRACTOR_VERSION_PREFIX = "pypdf"
IMAGE_EXTRACTOR_VERSION_PREFIX = "pillow"

# CLAUDE-MM4 Section 16/20: the same bounded-resource discipline MM3's own
# spreadsheet guard establishes - a page/sheet-count ceiling (a 300-sheet
# drawing set is not a realistic single upload for this prototype stage)
# and a raw-byte ceiling BEFORE any parsing library is even invoked.
MAX_DRAWING_SHEETS = 300
MAX_RAW_BYTES = 75 * 1024 * 1024

ROTATIONS = (0, 90, 180, 270)


class DrawingIntelligenceError(Exception):
    """Raised for a source that cannot even be attempted - not a Source,
    not a project match, or not a supported drawing container format -
    distinct from a drawing that WAS attempted and failed/refused to
    read (see the returned "classification" dict for that case, which is
    not an exception - the same split services/pdf_intelligence.py and
    services/spreadsheet_intelligence.py already establish)."""


# ============================================================================
# Coordinate-transform geometry (Section 7) - pure, deterministic, no I/O.
# ============================================================================

def normalize_rotation(rotation: int) -> int:
    """Folds any integer rotation into one of ROTATIONS (0/90/180/270) by
    taking it modulo 360 and flooring to the nearest lower 90 multiple.
    Never raises - an unusual input (e.g. a PDF's own `/Rotate -90`) is
    normalized rather than rejected; every value this module's own
    callers actually produce is already an exact multiple of 90."""
    return int(rotation) % 360 // 90 * 90 % 360


def _mirror_point(x: float, y: float, mirror_h: bool, mirror_v: bool) -> tuple[float, float]:
    return (1 - x if mirror_h else x, 1 - y if mirror_v else y)


def transform_point_to_display(
    x: float, y: float, rotation: int, mirror_h: bool = False, mirror_v: bool = False,
) -> tuple[float, float]:
    """
    Maps a point in a drawing sheet's ORIGINAL normalized (0-1, origin
    top-left, x right, y down) frame to where it appears in the DISPLAYED
    frame after the given view transform - mirror first, then a clockwise
    rotation by `rotation` degrees (must normalize to one of ROTATIONS).
    This composition order (mirror-then-rotate) is the one this whole
    module's own inverse function assumes; both directions are exercised
    and cross-checked by tests/test_mm4_drawing_intelligence.py's own
    round-trip property (transform_point_to_original(*transform_point_to_
    display(x, y, ...), ...) == (x, y) for every rotation/mirror
    combination).
    """
    rotation = normalize_rotation(rotation)
    mx, my = _mirror_point(x, y, mirror_h, mirror_v)
    if rotation == 0:
        return (mx, my)
    if rotation == 90:
        return (1 - my, mx)
    if rotation == 180:
        return (1 - mx, 1 - my)
    return (my, 1 - mx)  # 270


def transform_point_to_original(
    dx: float, dy: float, rotation: int, mirror_h: bool = False, mirror_v: bool = False,
) -> tuple[float, float]:
    """The exact inverse of transform_point_to_display - recovers the
    ORIGINAL-frame point a reviewer's on-screen click/selection
    corresponds to, given the view transform currently active."""
    rotation = normalize_rotation(rotation)
    if rotation == 0:
        mx, my = dx, dy
    elif rotation == 90:
        mx, my = dy, 1 - dx
    elif rotation == 180:
        mx, my = 1 - dx, 1 - dy
    else:  # 270
        mx, my = 1 - dy, dx
    # Mirroring is its own inverse (flipping twice restores the original),
    # so the same _mirror_point formula recovers x/y from mx/my.
    return _mirror_point(mx, my, mirror_h, mirror_v)


def transform_rect_to_display(
    x: float, y: float, width: float, height: float,
    rotation: int, mirror_h: bool = False, mirror_v: bool = False,
) -> tuple[float, float, float, float]:
    """Maps an axis-aligned rectangle (ORIGINAL frame) to its displayed
    axis-aligned bounding box. Computed via the two opposite corners
    (never assumed to keep the same corner order - a mirror or a 90/270
    rotation can and does swap which transformed corner ends up
    top-left), then min/max - robust for every rotation/mirror
    combination without a separate closed-form per case."""
    x1, y1 = transform_point_to_display(x, y, rotation, mirror_h, mirror_v)
    x2, y2 = transform_point_to_display(x + width, y + height, rotation, mirror_h, mirror_v)
    left, top = min(x1, x2), min(y1, y2)
    return (left, top, abs(x2 - x1), abs(y2 - y1))


def transform_rect_to_original(
    dx: float, dy: float, dwidth: float, dheight: float,
    rotation: int, mirror_h: bool = False, mirror_v: bool = False,
) -> tuple[float, float, float, float]:
    """Inverse of transform_rect_to_display - recovers the ORIGINAL-frame
    rectangle a reviewer's on-screen drag-selection corresponds to."""
    x1, y1 = transform_point_to_original(dx, dy, rotation, mirror_h, mirror_v)
    x2, y2 = transform_point_to_original(dx + dwidth, dy + dheight, rotation, mirror_h, mirror_v)
    left, top = min(x1, x2), min(y1, y2)
    return (left, top, abs(x2 - x1), abs(y2 - y1))


def describe_transform(rotation: int, mirror_h: bool = False, mirror_v: bool = False) -> str:
    """Section 7's own required visible status text - "Mirrored
    horizontally - source unchanged" / "Rotated 90 clockwise - source
    unchanged" - composed honestly from whatever is actually active,
    never a static label. Returns None-equivalent (empty string) only
    when the view is at its reset/identity state, so a caller can treat
    an empty string as "no banner needed"."""
    parts = []
    if rotation % 360:
        parts.append(f"Rotated {normalize_rotation(rotation)}° clockwise")
    if mirror_h:
        parts.append("mirrored horizontally")
    if mirror_v:
        parts.append("mirrored vertically")
    if not parts:
        return ""
    return " and ".join(parts).capitalize() + " — source unchanged"


# ============================================================================
# Title-block field extraction (Section 10) - per-PAGE, reusing
# drawing_intake.py's own field-pattern vocabulary (not a second, drifting
# copy of the regexes).
# ============================================================================

def _title_block_fields_for_page(page_text: str, page_number: int) -> dict:
    """
    Returns `{field_name: {"value", "reliability", "evidence_snippet",
    "source_page"}}` for exactly the fields drawing_intake.py's own
    _FIELD_PATTERNS recognizes on THIS one page - deliberately per-page
    (unlike drawing_intake.py's own aggregate-first-match-wins shape),
    since a multi-sheet drawing set has one independent title block per
    sheet. A field genuinely absent from this page's text is simply
    absent from the returned dict (Section 10: "do not silently promote
    OCR-like or heuristic extraction into fact" - callers render a
    missing key as METADATA_RELIABILITY_UNAVAILABLE, never a guess).
    """
    fields: dict = {}
    for line in page_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        for field_name, patterns in _FIELD_PATTERNS.items():
            if field_name in fields:
                continue
            for pattern in patterns:
                match = pattern.match(stripped)
                if not match:
                    continue
                value = match.group("value").strip().strip(",;")
                if not value:
                    continue
                fields[field_name] = {
                    "value": value,
                    "reliability": METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
                    "evidence_snippet": stripped,
                    "source_page": page_number,
                }
                break

    if "discipline" not in fields and "sheet_number" in fields:
        m = _SHEET_PREFIX_RE.match(fields["sheet_number"]["value"].strip().upper())
        if m:
            discipline_name = _SHEET_PREFIX_DISCIPLINE.get(m.group(1))
            if discipline_name:
                fields["discipline"] = {
                    "value": discipline_name,
                    "reliability": METADATA_RELIABILITY_INFERRED,
                    "evidence_snippet": fields["sheet_number"]["evidence_snippet"],
                    "source_page": page_number,
                }
    return fields


def _sheet_label(fields: dict, page_number: int) -> str:
    """Section 6: 'do not invent sheet numbers or titles when they cannot
    be extracted reliably' - falls back to a plain, honest 'Sheet N' only
    when neither a real sheet_number nor drawing_title was extracted."""
    number = fields.get("sheet_number", {}).get("value")
    title = fields.get("drawing_title", {}).get("value")
    if number and title:
        return f"{number} · {title}"
    if number:
        return number
    if title:
        return title
    return f"Sheet {page_number}"


# ============================================================================
# Orchestration
# ============================================================================

def _pdf_extractor_version() -> str:
    import pypdf

    return f"{DRAWING_EXTRACTOR_VERSION_PREFIX}:{pypdf.__version__}"


def _inspect_pdf_drawing(raw_bytes: bytes) -> dict:
    from pypdf import PdfReader
    from pypdf.errors import FileNotDecryptedError, PyPdfError, WrongPasswordError

    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        page_count = len(reader.pages)
    except (FileNotDecryptedError, WrongPasswordError):
        return {"classification": DRAWING_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED, "sheets": []}
    except PyPdfError:
        return {"classification": DRAWING_CLASSIFICATION_MALFORMED, "sheets": []}
    except Exception:  # noqa: BLE001 - matches pdf_intelligence.py's own precedent:
        # a corrupt/adversarial PDF can raise something outside pypdf's own
        # exception hierarchy - still an honest "could not read this file".
        return {"classification": DRAWING_CLASSIFICATION_MALFORMED, "sheets": []}

    if page_count > MAX_DRAWING_SHEETS:
        return {"classification": DRAWING_CLASSIFICATION_EXCESSIVE_SIZE, "sheets": []}

    sheets = []
    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:  # noqa: BLE001 - one unreadable page must not fail the whole set
            text = ""
        fields = _title_block_fields_for_page(text, index + 1)
        box = page.mediabox
        width = float(box.width) if box is not None else None
        height = float(box.height) if box is not None else None
        # pypdf's own `/Rotate` is already a 0/90/180/270-shaped clockwise
        # value per the PDF spec itself (Section 6's own "rotation" fact
        # ABOUT the source, distinct from the reviewer's view-only state).
        source_rotation = normalize_rotation(int(page.get("/Rotate", 0) or 0))
        sheets.append({
            "index": index, "label": _sheet_label(fields, index + 1),
            "width": width, "height": height, "source_rotation": source_rotation,
            "metadata": fields,
        })

    return {"classification": DRAWING_CLASSIFICATION_SUPPORTED, "sheets": sheets}


def _inspect_image_drawing(width: Optional[int], height: Optional[int]) -> dict:
    """A standalone raster drawing has exactly one sheet, no page-scoped
    title-block text layer to mine (Section 15: OCR is out of scope this
    stage) - every title-block field is honestly METADATA_RELIABILITY_
    UNAVAILABLE rather than silently absent, so a reviewer sees WHY, not
    just a blank panel."""
    fields = {
        name: {"value": None, "reliability": METADATA_RELIABILITY_UNAVAILABLE,
               "evidence_snippet": None, "source_page": None}
        for name in FIELD_LABELS
    }
    return {
        "classification": DRAWING_CLASSIFICATION_SUPPORTED,
        "sheets": [{
            "index": 0, "label": "Sheet 1", "width": width, "height": height,
            "source_rotation": 0, "metadata": fields,
        }],
    }


def register_drawing_evidence_for_source(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    source_id: str,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Loads the named Source's own persisted original bytes, classifies and
    reads it as a drawing (a drawing-oriented .pdf via pypdf, or a
    standalone .png/.jpg/.jpeg via Pillow - Section 5's own supported-
    format list), and registers the result as governed MM1 evidence
    (`register_drawing_sheet_structure`).

    Returns `{"classification", "sheet_count", "structural_unit_ids"}` on
    ANY outcome, including a refused/failed read - the same honest-return-
    value-not-exception shape services/pdf_intelligence.py and services/
    spreadsheet_intelligence.py already establish. DrawingIntelligenceError
    is raised only for a caller error (bad source_id, wrong project, an
    unsupported container format entirely) - the "cannot even be
    attempted" vs. "attempted and refused" distinction those modules'
    own docstrings already state.
    """
    source = store._find(workspace.sources, source_id)
    if source is None or source["project_id"] != workspace.project_id:
        raise DrawingIntelligenceError(f"Source {source_id} was not found.")

    file_path = source.get("file_path")
    if not file_path:
        raise DrawingIntelligenceError(f"Source {source_id} has no stored original file to read.")

    name = source.get("name") or ""
    ext = Path(name).suffix.lower()
    if ext not in (".pdf", ".png", ".jpg", ".jpeg"):
        raise DrawingIntelligenceError(
            f"Source {source_id} ('{name}') is not a supported drawing format (.pdf, .png, .jpg, .jpeg)."
        )

    path = Path(file_path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise DrawingIntelligenceError(f"Source {source_id}'s stored file could not be read: {exc}") from exc

    if len(raw_bytes) > MAX_RAW_BYTES:
        result = {"classification": DRAWING_CLASSIFICATION_EXCESSIVE_SIZE, "sheets": []}
    elif ext == ".pdf":
        result = _inspect_pdf_drawing(raw_bytes)
    else:
        try:
            with Image.open(io.BytesIO(raw_bytes)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(raw_bytes)) as probe:
                width, height = probe.size
        except Image.DecompressionBombError:
            result = {"classification": DRAWING_CLASSIFICATION_EXCESSIVE_SIZE, "sheets": []}
        except (UnidentifiedImageError, OSError):
            result = {"classification": DRAWING_CLASSIFICATION_MALFORMED, "sheets": []}
        else:
            result = _inspect_image_drawing(width, height)

    extractor_version = _pdf_extractor_version() if ext == ".pdf" else IMAGE_EXTRACTOR_VERSION_PREFIX

    if result["classification"] != DRAWING_CLASSIFICATION_SUPPORTED:
        return {
            "classification": result["classification"], "sheet_count": 0,
            "structural_unit_ids": [],
        }

    registration = store.register_drawing_sheet_structure(
        workspace, source_id, result["sheets"], extractor_version=extractor_version,
        actor=actor, governance_log=governance_log,
    )

    try:
        store.update_source_identity(
            workspace, source_id, actor=actor,
            mime_type="application/pdf" if ext == ".pdf" else f"image/{ext.lstrip('.')}",
            size_bytes=len(raw_bytes), extractor_version=extractor_version,
            governance_log=governance_log,
        )
    except CaseWorkspaceError:
        # Structure registration already succeeded and was already saved;
        # a Source-metadata backfill failing after that is not reason to
        # discard the real, already-persisted evidence records.
        pass

    return {
        "classification": result["classification"],
        "sheet_count": len(result["sheets"]),
        "structural_unit_ids": registration["structural_unit_ids"],
    }


def create_drawing_region_and_evidence(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    source_id: str,
    structural_unit_id: str,
    x: float, y: float, width: float, height: float,
    note: Optional[str] = None,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Section 4: "select or define an addressable drawing region; create
    direct evidence anchored to that region" - one call creating both.
    The region itself IS a portion of the Source (a crop of it), so its
    evidence is EVIDENCE_CLASS_DIRECT_SOURCE (the same class MM2/MM3's own
    page-paragraph/row evidence uses for content taken directly from the
    Source, never EVIDENCE_CLASS_USER_ENTERED - the reviewer is pointing
    at existing drawing content, not typing a new fact). `note`, if
    given, becomes the evidence's own human-readable content; otherwise a
    plain, honest placeholder naming the sheet is used - never a
    fabricated description of what the region shows.
    """
    source = store._find(workspace.sources, source_id)
    if source is None or source["project_id"] != workspace.project_id:
        raise DrawingIntelligenceError(f"Source {source_id} was not found.")

    unit = store._find(workspace.structural_units, structural_unit_id)
    if unit is None or unit["project_id"] != workspace.project_id or unit["source_id"] != source_id:
        raise DrawingIntelligenceError(f"Structural unit {structural_unit_id} was not found on this Source.")

    try:
        region = store.create_addressable_drawing_region(
            workspace, structural_unit_id=structural_unit_id, x=x, y=y, width=width, height=height,
            actor=actor, governance_log=governance_log,
        )
    except CaseWorkspaceError as exc:
        raise DrawingIntelligenceError(str(exc)) from exc

    sheet_label = unit.get("label") or "this sheet"
    content = note.strip() if note and note.strip() else f"Rectangular region on {sheet_label}"

    evidence = store.register_evidence_item(
        workspace, source_id=source_id, evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE,
        content=content, content_type="drawing_region", region_id=region["id"],
        actor=actor, governance_log=governance_log,
    )

    citation = store.resolve_region_citation(workspace, region["id"])

    return {"region": region, "evidence_item": evidence, "citation": citation}
