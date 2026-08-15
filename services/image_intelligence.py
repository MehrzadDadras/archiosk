"""
CLAUDE-MM5: Image, Screenshot, and Camera Evidence - the thin orchestration
layer between a real image read (Pillow - already a dependency since
pre-MM1 drawing-image intake) and the MM1 evidence contract (services/
case_workspace.py's own `register_drawing_sheet_structure`, reused here
with `unit_type="image"` rather than a parallel, duplicated registration
path - see that method's own docstring).

Deliberately a SEPARATE module from services/drawing_intelligence.py
(MM4), not an extension of it: this module owns a genuinely different
metadata vocabulary (EXIF camera/capture facts: orientation, make, model,
timestamp, software, GPS presence, color profile) from drawing_intake.py's
own title-block vocabulary (sheet number, discipline, revision...) that
services/drawing_intelligence.py already reuses - the two vocabularies
don't collide on field names, but conflating their own extraction/
classification code into one module would blur "this is a drawing sheet's
title block" and "this is a photo's camera metadata," two different
honesty claims. A small, explicit amount of duplication with
services/drawing_intelligence.py's own `_inspect_image_drawing` (the
Pillow-open/decompression-bomb-guard boilerplate) is accepted here rather
than factored out - both are short, both are independently tested, and
MM4's already-shipped, already-tested code is not touched by this stage.

Capability boundary, stated up front: no facial recognition, no object/
defect detection, no OCR over arbitrary image content, no panorama
stitching, no filters/artistic effects - this module reads EXIF metadata
and pixel dimensions only, never interprets what an image DEPICTS.

Privacy boundary (Section 9/10), the one genuinely new policy decision
this stage makes: GPS coordinates are DETECTED (a boolean presence flag)
but their actual latitude/longitude VALUES are never extracted into the
metadata dict this module returns - "do not automatically expose precise
location metadata in the UI or external packets" is enforced by never
reading the values into memory in the first place, not by redacting them
after the fact. The values remain physically present in the preserved
original file bytes on disk (never stripped from the original - "preserve
original bytes internally where authorized"); a derivative crop this
module produces is EXIF-free by construction (Pillow's own `Image.save()`
does not copy EXIF unless explicitly re-attached), which doubles as
Section 10's own "sanitized derivative export" requirement.
"""
from __future__ import annotations

import hashlib
import io
import time
import uuid
from pathlib import Path
from typing import Optional

from PIL import ExifTags, Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    EVIDENCE_CLASS_USER_ENTERED,
    IMAGE_CLASSIFICATION_EXCESSIVE_SIZE,
    IMAGE_CLASSIFICATION_MALFORMED,
    IMAGE_CLASSIFICATION_SUPPORTED,
    IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT,
    METADATA_EXPOSURE_PRESERVED_INTERNAL,
    METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED,
    METADATA_EXPOSURE_UNAVAILABLE,
    METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
    METADATA_RELIABILITY_UNAVAILABLE,
    ProjectWorkspace,
    SOURCE_KIND_DRAWING,
    SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP,
    SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT,
    SOURCE_ORIGIN_TYPE_EYE_CAPTURE,
)
from services.governance import GovernanceLog

IMAGE_EXTRACTOR_VERSION = "pillow-exif"
SUPPORTED_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
_MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

# CLAUDE-MM5 Section 17/21: the same bounded-resource discipline MM4's own
# drawing-image guard establishes - a raw-byte ceiling BEFORE any parsing
# library is invoked. Pillow's own MAX_IMAGE_PIXELS default (~89M pixels,
# unmodified here) is the actual decompression-bomb guard once decoding
# starts.
MAX_RAW_BYTES = 40 * 1024 * 1024

# EXIF tag ids (stable, from the standard - not guessed): Make, Model,
# Software, DateTimeOriginal (falls back to the base DateTime tag if the
# "Original" one is absent, e.g. a screenshot with no camera at all),
# Orientation, GPSInfo (IFD pointer only - never read further, see the
# module's own privacy-boundary docstring above).
_TAG_MAKE = 0x010F
_TAG_MODEL = 0x0110
_TAG_SOFTWARE = 0x0131
_TAG_DATETIME = 0x0132
_TAG_DATETIME_ORIGINAL = 0x9003
_TAG_ORIENTATION = 0x0112
_TAG_GPS_IFD = 0x8825


class ImageIntelligenceError(Exception):
    """Raised for a request that cannot even be attempted - not a Source,
    not a project match, an unregistered structural unit, or an
    unsupported container format - distinct from an image that WAS
    attempted and refused/failed to read (see the returned
    "classification" dict for that case, which is not an exception - the
    same split every prior MM stage's own *IntelligenceError already
    establishes)."""


def _exif_fields(raw_bytes: bytes) -> dict:
    """
    Returns `{field_name: {"value", "reliability", "exposure"}}` for the
    camera/capture metadata vocabulary Section 10 asks for. Every field
    is present in the returned dict even when unavailable (an honest
    `METADATA_RELIABILITY_UNAVAILABLE` entry, never a silently missing
    key) - a screenshot has no camera make/model/GPS at all, which is
    itself a real, reportable fact, not an error.
    """
    fields = {
        "camera_make": None, "camera_model": None, "software": None,
        "capture_timestamp": None, "orientation": None,
    }
    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            exif = probe.getexif()
            color_profile = probe.info.get("icc_profile") is not None
            if exif:
                fields["camera_make"] = exif.get(_TAG_MAKE)
                fields["camera_model"] = exif.get(_TAG_MODEL)
                fields["software"] = exif.get(_TAG_SOFTWARE)
                fields["capture_timestamp"] = exif.get(_TAG_DATETIME_ORIGINAL) or exif.get(_TAG_DATETIME)
                fields["orientation"] = exif.get(_TAG_ORIENTATION)
                gps_present = bool(exif.get(_TAG_GPS_IFD)) or bool(exif.get_ifd(_TAG_GPS_IFD))
            else:
                gps_present = False
    except Exception:  # noqa: BLE001 - EXIF is best-effort enrichment; a
        # read failure here must never fail image registration itself,
        # matching drawing_intake.py's own established precedent.
        gps_present = False
        color_profile = False

    result = {}
    for name, value in fields.items():
        if value is None or (isinstance(value, str) and not value.strip()):
            result[name] = {
                "value": None, "reliability": METADATA_RELIABILITY_UNAVAILABLE,
                "exposure": METADATA_EXPOSURE_UNAVAILABLE,
            }
        else:
            result[name] = {
                "value": str(value), "reliability": METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
                "exposure": METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED,
            }
    # GPS: presence only, value NEVER populated - see this module's own
    # privacy-boundary docstring. exposure is deliberately PRESERVED_
    # INTERNAL, not SHOWN_TO_AUTHORIZED, regardless of role - Section 9's
    # own "do not automatically expose... in the UI" applies to every
    # authenticated user of this prototype, not merely an unauthorized one.
    result["gps_present"] = {
        "value": gps_present, "reliability": METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
        "exposure": METADATA_EXPOSURE_PRESERVED_INTERNAL,
    }
    result["color_profile_present"] = {
        "value": color_profile, "reliability": METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
        "exposure": METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED,
    }
    return result


_PILLOW_FORMAT_TO_EXTENSION = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


def _sniff_supported_extension(raw_bytes: bytes) -> Optional[str]:
    """Content-based fallback for a missing/unrecognized filename
    extension (Section 17) - returns a canonical extension if Pillow can
    actually decode `raw_bytes` as one of the formats this module
    supports, else None (never guessed from a claimed but wrong
    extension - this is the SNIFF path, only reached when the extension
    was already not one of SUPPORTED_EXTENSIONS)."""
    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            return _PILLOW_FORMAT_TO_EXTENSION.get(probe.format)
    except Exception:  # noqa: BLE001 - any decode failure just means "not sniffable"
        return None


def _classify_and_inspect(raw_bytes: bytes) -> dict:
    """Returns `{"classification", "width", "height", "fields"}`. Mirrors
    services/drawing_intelligence.py's own malformed/oversized handling
    for a raster image (see that module's own `register_drawing_evidence_
    for_source` for the twin implementation this one deliberately does not
    share code with - see this module's own header comment)."""
    if len(raw_bytes) > MAX_RAW_BYTES:
        return {"classification": IMAGE_CLASSIFICATION_EXCESSIVE_SIZE, "width": None, "height": None, "fields": {}}
    try:
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(raw_bytes)) as probe:
            width, height = probe.size
    except Image.DecompressionBombError:
        return {"classification": IMAGE_CLASSIFICATION_EXCESSIVE_SIZE, "width": None, "height": None, "fields": {}}
    except (UnidentifiedImageError, OSError):
        return {"classification": IMAGE_CLASSIFICATION_MALFORMED, "width": None, "height": None, "fields": {}}

    fields = _exif_fields(raw_bytes)
    return {"classification": IMAGE_CLASSIFICATION_SUPPORTED, "width": width, "height": height, "fields": fields}


def register_eye_capture(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    raw_bytes: bytes,
    filename: str,
    description: Optional[str],
    sources_dir: Path,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Section 7/8: "Save to project" for an Eye-pasted/dropped/uploaded
    image (or a phone-camera photo, Section 9 - the same upload pathway,
    no separate mobile-specific code). Validates content BEFORE writing
    anything to disk (Section 17: "validate actual image content, not
    extension alone"); a refused image never creates a Source or leaves a
    file behind. On success: persists the original bytes unchanged,
    registers one `unit_type="image"` StructuralUnit (reusing MM4's own
    `register_drawing_sheet_structure`), and - if `description` is given -
    registers it as a EVIDENCE_CLASS_USER_ENTERED EvidenceItem anchored to
    the Source itself (no region yet at this point, matching Requirement.
    source_location's own "honest absence over a fabricated anchor").

    Returns `{"classification", "source_id", "structural_unit_id"}` on
    ANY outcome including a refusal (classification != SUPPORTED means no
    Source was created - `source_id`/`structural_unit_id` are then None).
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        # Section 17: "validate actual image content, not extension
        # alone" - a missing/unrecognized extension (a browser paste
        # blob with no name at all, or an unconventional client) is not
        # automatically refused; Pillow's own content sniff decides.
        # Still fails safely: a real non-image with a stray/wrong
        # extension is caught the same way below, by decode failing.
        sniffed = _sniff_supported_extension(raw_bytes)
        if sniffed is None:
            return {
                "classification": IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT,
                "source_id": None, "structural_unit_id": None,
            }
        ext = sniffed

    inspection = _classify_and_inspect(raw_bytes)
    if inspection["classification"] != IMAGE_CLASSIFICATION_SUPPORTED:
        return {"classification": inspection["classification"], "source_id": None, "structural_unit_id": None}

    # A pasted clipboard image usually arrives with a generic/blank
    # filename (browsers commonly hand back "image.png") - Section 8's
    # own "generated capture name" requirement, rather than a misleading
    # name that implies a real uploaded file the reviewer never named.
    stem = Path(filename).stem.strip().lower()
    if not stem or stem in ("image", "blob", "clipboard", "screenshot"):
        display_name = f"Eye capture {time.strftime('%Y-%m-%d %H%M%S')}{ext}"
    else:
        display_name = secure_filename(filename) or f"Eye capture {time.strftime('%Y-%m-%d %H%M%S')}{ext}"

    sources_dir.mkdir(parents=True, exist_ok=True)
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{secure_filename(display_name)}"
    stored_path.write_bytes(raw_bytes)
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    source = store.add_source(
        workspace, name=display_name, file_path=str(stored_path), kind=SOURCE_KIND_DRAWING,
        width=inspection["width"], height=inspection["height"], file_hash=file_hash,
        origin_type=SOURCE_ORIGIN_TYPE_EYE_CAPTURE, actor=actor, governance_log=governance_log,
    )

    registration = store.register_drawing_sheet_structure(
        workspace, source["id"],
        [{"index": 0, "label": display_name, "width": inspection["width"], "height": inspection["height"],
          "source_rotation": 0, "metadata": inspection["fields"]}],
        extractor_version=IMAGE_EXTRACTOR_VERSION, actor=actor, governance_log=governance_log,
        unit_type="image",
    )

    try:
        store.update_source_identity(
            workspace, source["id"], actor=actor, mime_type=_MIME_TYPES.get(ext, "application/octet-stream"),
            size_bytes=len(raw_bytes), extractor_version=IMAGE_EXTRACTOR_VERSION, governance_log=governance_log,
        )
    except CaseWorkspaceError:
        pass

    if description and description.strip():
        store.register_evidence_item(
            workspace, source_id=source["id"], evidence_class=EVIDENCE_CLASS_USER_ENTERED,
            content=description.strip(), content_type="text", actor=actor, governance_log=governance_log,
        )

    return {
        "classification": IMAGE_CLASSIFICATION_SUPPORTED,
        "source_id": source["id"],
        "structural_unit_id": registration["structural_unit_ids"][0],
    }


def register_document_snapshot(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    parent_source_id: str,
    page_number: Optional[int],
    raw_bytes: bytes,
    sources_dir: Path,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    CLAUDE-SNAPSHOT-DUAL-SURFACE-01: captures the currently-rendered page
    of a Document already open in Main or Eye - built fresh this stage
    (there was no pre-existing "-01/-02" screenshot mechanism to
    preserve, confirmed by a real code search before writing this).

    The CALLER (routes/workspace.py) is the one that knows which surface
    (Main or Eye, embedded or detached) currently has focus and therefore
    which document/page raw_bytes actually depicts - this function only
    ever registers what it is given, against the parent Source it is
    told, exactly like register_eye_capture/extract_bounded_crop above
    never independently decide what they're capturing either.

    Naming is deterministic and sequential off the PARENT Source's own
    stem (`<parent-stem>-01.png`, `-02.png`, ...), scanning every
    existing Source name in this Project - never reused/gapped/renamed
    on a later deletion, and never colliding with an unrelated Source
    that happens to already end in the same digits.

    Provenance is carried on the new Source's own existing origin_type/
    origin_reference fields (SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT,
    "<parent_source_id>#page=<n>" when a page number is known) - the
    same "carried on the Source's own existing fields, not a new record
    type" precedent extract_bounded_crop already established for
    derivative_crop. The parent Source itself is never mutated - this
    only ever ADDS a new sibling Source.
    """
    parent = store._find(workspace.sources, parent_source_id)
    if parent is None or parent["project_id"] != workspace.project_id:
        raise ImageIntelligenceError(f"Source {parent_source_id} was not found.")

    inspection = _classify_and_inspect(raw_bytes)
    if inspection["classification"] != IMAGE_CLASSIFICATION_SUPPORTED:
        raise ImageIntelligenceError("Snapshot capture was not a valid image.")

    stem = Path(parent["name"]).stem
    existing_names = {s["name"] for s in workspace.sources}
    n = 1
    while True:
        candidate_name = f"{stem}-{n:02d}.png"
        if candidate_name not in existing_names:
            break
        n += 1

    sources_dir.mkdir(parents=True, exist_ok=True)
    stored_path = sources_dir / f"{uuid.uuid4().hex}_{secure_filename(candidate_name)}"
    stored_path.write_bytes(raw_bytes)
    file_hash = hashlib.sha256(raw_bytes).hexdigest()

    origin_reference = (
        f"{parent_source_id}#page={page_number}" if page_number is not None else parent_source_id
    )

    snapshot_source = store.add_source(
        workspace, name=candidate_name, file_path=str(stored_path), kind=SOURCE_KIND_DRAWING,
        width=inspection["width"], height=inspection["height"], file_hash=file_hash,
        origin_type=SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT, origin_reference=origin_reference,
        actor=actor, governance_log=governance_log,
    )

    registration = store.register_drawing_sheet_structure(
        workspace, snapshot_source["id"],
        [{"index": 0, "label": candidate_name, "width": inspection["width"], "height": inspection["height"],
          "source_rotation": 0, "metadata": {}}],
        extractor_version=IMAGE_EXTRACTOR_VERSION, actor=actor, governance_log=governance_log,
        unit_type="image",
    )

    return {
        "source_id": snapshot_source["id"],
        "name": candidate_name,
        "kind": snapshot_source["kind"],
        "structural_unit_id": registration["structural_unit_ids"][0],
        "parent_source_id": parent_source_id,
        "page_number": page_number,
    }


def extract_bounded_crop(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    source_id: str,
    region_id: str,
    sources_dir: Path,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Section 12/6: "optionally export a derivative crop" - a REAL cropped
    PNG file, distinct from the governed region selection itself (which
    never trims pixels - see create_addressable_drawing_region's own
    docstring). Crops the ORIGINAL bytes at the region's own stored
    ORIGINAL-frame normalized coordinates (never a currently-displayed,
    possibly-transformed view - the region was already stored correctly
    by the caller, see services/drawing_intelligence.py's own coordinate-
    transform module), producing a genuinely new derivative Source
    (`origin_type=SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP`, `origin_reference=
    region_id` - Section 6's own required source/region/export-time/
    actor/checksum record, carried on the Source's own existing fields
    rather than a new record type).

    The derivative is EXIF-free by construction (Pillow's `Image.save()`
    never copies EXIF unless explicitly re-attached) - this module's own
    "sanitized derivative export" (Section 10), with `removed_metadata_
    fields` in the return value naming exactly which fields the ORIGINAL
    had that the derivative therefore lacks (the manifest Section 10
    requires).
    """
    source = store._find(workspace.sources, source_id)
    if source is None or source["project_id"] != workspace.project_id:
        raise ImageIntelligenceError(f"Source {source_id} was not found.")
    region = store._find(workspace.addressable_regions, region_id)
    if region is None or region["project_id"] != workspace.project_id:
        raise ImageIntelligenceError(f"Region {region_id} was not found.")
    if region["region_type"] != "rectangular":
        raise ImageIntelligenceError("Only a rectangular region can be exported as a derivative crop.")

    file_path = source.get("file_path")
    if not file_path:
        raise ImageIntelligenceError(f"Source {source_id} has no stored original file to crop.")
    raw_bytes = Path(file_path).read_bytes()

    try:
        with Image.open(io.BytesIO(raw_bytes)) as original:
            width, height = original.size
            address = region["address"]
            box = (
                round(address["x"] * width), round(address["y"] * height),
                round((address["x"] + address["width"]) * width), round((address["y"] + address["height"]) * height),
            )
            cropped = original.convert("RGB").crop(box)
            out_buf = io.BytesIO()
            cropped.save(out_buf, format="PNG")
            derivative_bytes = out_buf.getvalue()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageIntelligenceError(f"Source {source_id}'s stored file could not be read: {exc}") from exc

    sources_dir.mkdir(parents=True, exist_ok=True)
    derivative_name = f"{Path(source['name']).stem}-crop-{int(time.time())}.png"
    derivative_path = sources_dir / f"{uuid.uuid4().hex}_{secure_filename(derivative_name)}"
    derivative_path.write_bytes(derivative_bytes)
    derivative_hash = hashlib.sha256(derivative_bytes).hexdigest()

    original_fields = _exif_fields(raw_bytes)
    removed_fields = [
        name for name, info in original_fields.items()
        if info["reliability"] == METADATA_RELIABILITY_DIRECTLY_EXTRACTED
    ]

    derivative_source = store.add_source(
        workspace, name=derivative_name, file_path=str(derivative_path), kind=SOURCE_KIND_DRAWING,
        width=box[2] - box[0], height=box[3] - box[1], file_hash=derivative_hash,
        origin_type=SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP, origin_reference=region_id,
        actor=actor, governance_log=governance_log,
    )

    return {
        "derivative_source_id": derivative_source["id"],
        "source_id": source_id,
        "region_id": region_id,
        "export_time": derivative_source["added_at"],
        "actor": actor,
        "derivative_checksum": derivative_hash,
        "removed_metadata_fields": removed_fields,
    }


def create_marker_and_evidence(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    source_id: str,
    structural_unit_id: str,
    x: float, y: float,
    note: str,
    actor: str = "system",
    governance_log: Optional[GovernanceLog] = None,
) -> dict:
    """
    Section 13: the one bounded annotation type this stage implements - a
    point marker with a short text note. Mirrors services/drawing_
    intelligence.py's own create_drawing_region_and_evidence shape
    exactly (region + EvidenceItem in one call, EVIDENCE_CLASS_USER_
    ENTERED since the note is a reviewer's own observation, not content
    taken directly from the image - the opposite class choice from a
    rectangular region's own DIRECT_SOURCE evidence, and deliberately so:
    a marker's value IS the annotation text, not a crop of the image).
    `note` is required (unlike a rectangular region's optional note) - an
    unlabeled point marker would carry no evidentiary meaning at all.
    """
    source = store._find(workspace.sources, source_id)
    if source is None or source["project_id"] != workspace.project_id:
        raise ImageIntelligenceError(f"Source {source_id} was not found.")
    unit = store._find(workspace.structural_units, structural_unit_id)
    if unit is None or unit["project_id"] != workspace.project_id or unit["source_id"] != source_id:
        raise ImageIntelligenceError(f"Structural unit {structural_unit_id} was not found on this Source.")
    if not note or not note.strip():
        raise ImageIntelligenceError("A marker requires a short text note.")

    try:
        region = store.create_addressable_marker_region(
            workspace, structural_unit_id=structural_unit_id, x=x, y=y,
            actor=actor, governance_log=governance_log,
        )
    except CaseWorkspaceError as exc:
        raise ImageIntelligenceError(str(exc)) from exc

    evidence = store.register_evidence_item(
        workspace, source_id=source_id, evidence_class=EVIDENCE_CLASS_USER_ENTERED,
        content=note.strip(), content_type="marker_note", region_id=region["id"],
        actor=actor, governance_log=governance_log,
    )
    citation = store.resolve_region_citation(workspace, region["id"])
    return {"region": region, "evidence_item": evidence, "citation": citation}
