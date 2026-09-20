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
import math
from pathlib import Path
from typing import Optional
from services.runtime_observation import observed


@observed
def rectify_document_preview(raw_bytes, filename, corners, *, aspect_ratio=1.414214, rotation=0):
    """Explicit four-point display rectification, not a survey geometry upgrade.

    Controls are normalized browser/EXIF-display coordinates in sheet TL, TR,
    BR, BL order. The target rectangle/aspect is an explicit display premise.
    Homography and its inverse belong to spatial_compiler; Pillow only samples.
    """
    from PIL import Image, ImageOps
    from engine import spatial_compiler as geometry
    checked = verify_image_bytes(raw_bytes, filename)
    if checked['status'] != VERIFIED:
        raise ValueError(checked['reason'])
    if (not isinstance(corners, list) or len(corners) != 4
            or any(not isinstance(p, (list, tuple)) or len(p) != 2
                   or any(isinstance(v, bool) or not isinstance(v, (int, float))
                          or not math.isfinite(v) or not 0 <= v <= 1 for v in p) for p in corners)):
        raise ValueError('Four finite, normalized document corners are required.')
    if not math.isfinite(aspect_ratio) or not .2 <= aspect_ratio <= 5 or rotation not in (0, 90, 180, 270):
        raise ValueError('Invalid display aspect or sheet-reading rotation.')
    polygon = geometry.classify_point_in_polygon(corners[0], corners,
        point_space='NORMALIZED_IMAGE', polygon_space='NORMALIZED_IMAGE',
        point_plane='capture', polygon_plane='capture', geometry_level='PROJECTIVE')
    if polygon.get('error'):
        raise ValueError('Document control polygon refused: ' + polygon['error'])
    transform = geometry.estimate_control_homography(corners, [[0,0],[1,0],[1,1],[0,1]],
        source_space='NORMALIZED_IMAGE', target_space='AFFINE_RECTIFIED',
        source_plane='capture', target_plane='document-preview', geometry_level='PROJECTIVE')
    if transform['state'] != 'ESTABLISHED':
        raise ValueError('Document rectification refused: ' + str(transform.get('error')))
    inverse = geometry.invert_homography(transform)
    if inverse['state'] != 'ESTABLISHED':
        raise ValueError('Inverse document transform is unresolved.')
    # EXIF display is exactly what the browser's original view shows. Do not run
    # OCR/OSD here or silently rotate away from the user's supplied controls.
    with Image.open(io.BytesIO(raw_bytes)) as original:
        image = ImageOps.exif_transpose(original).convert('RGB')
    width = round(1600 * min(1, aspect_ratio))
    height = round(width / aspect_ratio)
    matrix = inverse['matrix']
    scale = matrix[2][2]
    if abs(scale) < 1e-12:
        raise ValueError('Preview crosses a projective horizon.')
    a,b,c = [v/scale for v in matrix[0]]
    d,e,f = [v/scale for v in matrix[1]]
    g,h,_ = [v/scale for v in matrix[2]]
    # Refuse a horizon through the output rectangle; never fill it with fiction.
    if min(1, 1+g, 1+h, 1+g+h) <= 1e-8:
        raise ValueError('Preview crosses a projective horizon.')
    sw, sh = image.size
    coefficients = (sw*a/width, sw*b/height, sw*c,
                    sh*d/width, sh*e/height, sh*f, g/width, h/height)
    preview = image.transform((width,height), Image.Transform.PERSPECTIVE,
        coefficients, resample=Image.Resampling.BICUBIC, fillcolor='white')
    if rotation:
        preview = preview.rotate(-rotation, expand=True)
    buffer = io.BytesIO()
    preview.save(buffer, 'PNG')
    return buffer.getvalue(), dict(state='QUALIFIED', geometry_level='PROJECTIVE',
        coordinate_space='DOCUMENT_PREVIEW', capture_frame='EXIF_DISPLAY',
        source_size=[sw,sh], preview_size=list(preview.size), corners=corners,
        transform=transform, display_aspect_ratio=aspect_ratio,
        sheet_reading_rotation=rotation, north_orientation='UNRESOLVED',
        survey_geometry='NOT_ESTABLISHED', authority='NOT_ESTABLISHED',
        qualification='Rectangle/aspect and reading orientation are human display premises. '
                      'Angles, distances, north and legal survey authority are not established.')

logger = logging.getLogger(__name__)


@observed
def transform_document_preview(raw_bytes, filename, action, parameters=None):
    """Sample a derived view; never modify source bytes or infer a real viewpoint."""
    from PIL import Image, ImageOps
    checked = verify_image_bytes(raw_bytes, filename)
    if checked['status'] != VERIFIED:
        raise ValueError(checked['reason'])
    transforms = {
        'ROTATE_90': (Image.Transpose.ROTATE_270, [[0,-1,1],[1,0,0],[0,0,1]]),
        'ROTATE_180': (Image.Transpose.ROTATE_180, [[-1,0,1],[0,-1,1],[0,0,1]]),
        'ROTATE_270': (Image.Transpose.ROTATE_90, [[0,1,0],[-1,0,1],[0,0,1]]),
        'MIRROR_HORIZONTAL': (Image.Transpose.FLIP_LEFT_RIGHT, [[-1,0,1],[0,1,0],[0,0,1]]),
        'MIRROR_VERTICAL': (Image.Transpose.FLIP_TOP_BOTTOM, [[1,0,0],[0,-1,1],[0,0,1]]),
    }
    parameters = parameters or {}
    if not isinstance(parameters, dict):
        raise ValueError('Transform parameters must be an object.')
    if action not in transforms and action not in ('CROP', 'FIT', 'ROTATE_ANGLE'):
        raise ValueError('Unsupported typed view action; no transformation was inferred.')
    with Image.open(io.BytesIO(raw_bytes)) as original:
        parent = ImageOps.exif_transpose(original).convert('RGB')
        if action == 'ROTATE_ANGLE':
            angle = parameters.get('clockwise_degrees')
            if (set(parameters) != {'clockwise_degrees'} or isinstance(angle, bool)
                    or not isinstance(angle, (int, float)) or not math.isfinite(angle) or not -360 <= angle <= 360):
                raise ValueError('Rotation requires finite clockwise_degrees between -360 and 360.')
            preview = parent.rotate(-angle, expand=True, resample=Image.Resampling.BICUBIC, fillcolor='white')
            w, h = parent.size
            ow, oh = preview.size
            cosine, sine = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            matrix = [[cosine*w/ow, -sine*h/ow, .5-(cosine*w-sine*h)/(2*ow)],
                      [sine*w/oh, cosine*h/oh, .5-(sine*w+cosine*h)/(2*oh)], [0,0,1]]
        elif action == 'CROP':
            box = parameters.get('box')
            if (not isinstance(box, list) or len(box) != 4 or any(isinstance(v, bool)
                    or not isinstance(v, (int, float)) or not math.isfinite(v) or not 0 <= v <= 1 for v in box)
                    or box[0] >= box[2] or box[1] >= box[3]):
                raise ValueError('Crop requires box [left, top, right, bottom] in normalized coordinates.')
            w, h = parent.size
            pixels = [round(box[0]*w), round(box[1]*h), round(box[2]*w), round(box[3]*h)]
            if pixels[2] <= pixels[0] or pixels[3] <= pixels[1]:
                raise ValueError('Crop must retain at least one pixel in each dimension.')
            x0,y0,x1,y1 = pixels[0]/w,pixels[1]/h,pixels[2]/w,pixels[3]/h
            matrix = [[1/(x1-x0),0,-x0/(x1-x0)],[0,1/(y1-y0),-y0/(y1-y0)],[0,0,1]]
            parameters = {'requested_box': box, 'pixel_box': pixels}
            preview = parent.crop(tuple(pixels))
        elif action == 'FIT':
            edge = parameters.get('max_edge', 1600)
            if type(edge) is not int or not 16 <= edge <= 2400:
                raise ValueError('Fit max_edge must be an integer between 16 and 2400 pixels.')
            preview = parent.copy()
            preview.thumbnail((edge, edge), Image.Resampling.LANCZOS)
            matrix = [[1,0,0],[0,1,0],[0,0,1]]
            parameters = {'max_edge': edge}
        else:
            if parameters:
                raise ValueError('This discrete transform accepts no additional parameters.')
            operation, matrix = transforms[action]
            preview = parent.transpose(operation)
    buffer = io.BytesIO()
    preview.save(buffer, 'PNG')
    return buffer.getvalue(), dict(type=action, parameters=parameters, matrix=matrix,
        coordinate_space_before='NORMALIZED_EXIF_DISPLAY', coordinate_space_after='NORMALIZED_WORKING_VIEW',
        input_size=list(parent.size), output_size=list(preview.size),
        state='QUALIFIED', authority='NOT_ESTABLISHED', geometry='UNCHANGED',
        text_rendering='ORIGINAL_PIXELS_TRANSFORMED',
        qualification='User-requested display transform. Viewpoint equivalence, north, metric geometry and authority are not established.')

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


# CLAUDE-GO-PERCEPTION-ORIENTATION-01 - the first perceptual invariant.
#
#     GO'S MACHINE VIEW OF THE SOURCE MUST HAVE THE SAME INTENDED ORIENTATION
#     AS THE HUMAN VIEW.
#
# A phone photograph is routinely stored rotated, with an EXIF tag declaring
# how it is meant to be seen. Browsers honour that tag, so the person sees the
# picture upright. PyMuPDF does not, so the OCR path read the stored pixels
# sideways - proven on a real customer JPEG carrying Orientation 6, where the
# as-stored and EXIF-corrected reads returned different text.
#
# THE AUTHORITY RULE, in strict precedence, declared once here:
#
#   1. EXIF orientation (1-8), when present and valid. It is the capturing
#      device's own statement of intended display, and it is what the customer
#      is already looking at in their browser. Matching it is the whole point.
#   2. Tesseract OSD, ONLY when EXIF is absent or unusable. OSD is PERCEPTION
#      EVIDENCE - a reading of the pixels - never authority over a declaration
#      that already exists.
#   3. Stored pixel orientation, used as-is.
#   4. Page-rotation metadata belongs to the PDF path and has no meaning for a
#      standalone raster; it is named here so the precedence is complete, and
#      that path is deliberately untouched by this work.
#
# Because 1 outranks 2, a conflict cannot decide anything - but it can still be
# OBSERVED, and observing it is how a wrong EXIF tag would ever be noticed. A
# caller may ask for OSD alongside EXIF; production does not, because a second
# Tesseract pass costs seconds and would buy evidence nobody acts on.
# A rotation is only applied on OSD's word when OSD is actually confident.
#
# MEASURED, not chosen. Tesseract's orientation confidence on this host:
#
#   real prose, upright / 90 / 180 / 270   -> 10.13 - 10.99, direction CORRECT
#   sparse drawing text                    ->  0.12 - 0.15, direction UNRELIABLE
#
# At 0.15 it reported "rotate 180, script Greek" for an upright English
# drawing, and an earlier build obeyed it and destroyed a clean read. Nearly
# two orders of magnitude separate the two populations, so a floor between
# them is evidence rather than taste. 2.0 sits far above observed noise and far
# below observed signal.
#
# Note the contrast with the recovered-text legibility score this codebase
# deliberately does NOT compute: there, measurement showed noise and signal
# OVERLAPPED (0.434 vs 0.195), so a threshold would have been invented
# certainty. Here they separate cleanly. Same discipline, opposite answer.
OSD_MINIMUM_CONFIDENCE = 2.0

ORIENTATION_AUTHORITY_EXIF = "exif"
ORIENTATION_AUTHORITY_OSD = "osd"
ORIENTATION_AUTHORITY_STORED = "stored_pixels"
ORIENTATION_AUTHORITY_UNRESOLVED = "unresolved"

# The eight EXIF orientation values as the transform each one means. Pillow's
# exif_transpose applies all eight including the mirrored ones; this table is
# for REPORTING what was applied, never for doing it by hand.
_EXIF_ORIENTATION_MEANING = {
    1: (0, False), 2: (0, True), 3: (180, False), 4: (180, True),
    5: (90, True), 6: (270, False), 7: (270, True), 8: (90, False),
}


def _osd_observation(raw_bytes, reader=None):
    """Ask Tesseract which way up it thinks the page is. Never raises.

    `--psm 0` is orientation and script detection only - no recognition - and
    the `osd` traineddata it needs is already installed on this host. Returned
    as evidence with its engine named, exactly like any other extractor output.
    """
    observation = {"ran": False, "rotate": None, "confidence": None,
                   "script": None, "engine": None, "reason": None}
    try:
        import os
        import shutil
        import subprocess
        import tempfile

        if reader is not None:
            raw_output = reader(raw_bytes)
            observation["engine"] = "injected reader"
        else:
            binary = shutil.which("tesseract")
            if not binary:
                observation["reason"] = "no tesseract binary"
                return observation
            with tempfile.TemporaryDirectory(prefix="archiosk-osd-") as directory:
                image_path = os.path.join(directory, "frame.png")
                with open(image_path, "wb") as handle:
                    handle.write(raw_bytes)
                completed = subprocess.run(
                    [binary, image_path, "stdout", "--psm", "0"],
                    capture_output=True, text=True, timeout=60)
                raw_output = completed.stdout or ""
                observation["engine"] = "tesseract osd"
        for line in (raw_output or "").splitlines():
            key, _, value = line.partition(":")
            key, value = key.strip().lower(), value.strip()
            if key == "rotate":
                observation["rotate"] = int(value)
            elif key == "orientation confidence":
                observation["confidence"] = float(value)
            elif key == "script":
                observation["script"] = value
        observation["ran"] = observation["rotate"] is not None
        if not observation["ran"] and not observation["reason"]:
            observation["reason"] = "no orientation reported"
    except Exception as exc:  # never raises: an unreadable page is an outcome
        observation["reason"] = "%s: %s" % (type(exc).__name__, exc)
    return observation


def normalise_orientation(raw_bytes, filename, *, osd_reader=None,
                          observe_osd=False):
    """The frame GO should look at, and a full account of how it was chosen.

    NEVER MUTATES THE SOURCE. The original bytes are returned untouched
    whenever no transform is required, and where one is applied the returned
    bytes are a DERIVED PROCESSING REPRESENTATION - the stored file, its EXIF
    and its checksum are not rewritten by anything here.
    """
    observation = {
        "authority": ORIENTATION_AUTHORITY_STORED,
        "exif_orientation": None,
        "osd": None,
        "applied_rotation_degrees": 0,
        "applied_mirror": False,
        "native_size": None,
        "normalised_size": None,
        "changed": False,
        "conflict": False,
        "reason": None,
    }
    try:
        from PIL import Image, ImageOps
    except Exception as exc:
        observation["authority"] = ORIENTATION_AUTHORITY_UNRESOLVED
        observation["reason"] = "imaging library unavailable: %s" % exc
        return {"bytes": raw_bytes, "observation": observation}

    try:
        image = Image.open(io.BytesIO(raw_bytes))
        image.load()
    except Exception as exc:
        # verify_image_bytes is the gate that refuses undecodable uploads; if
        # one reaches here anyway, orientation is unresolved and the original
        # bytes continue untouched rather than anything being invented.
        observation["authority"] = ORIENTATION_AUTHORITY_UNRESOLVED
        observation["reason"] = "not decodable: %s: %s" % (type(exc).__name__, exc)
        return {"bytes": raw_bytes, "observation": observation}

    observation["native_size"] = list(image.size)
    observation["normalised_size"] = list(image.size)

    exif_value = None
    try:
        exif = image.getexif()
        raw_value = exif.get(274) if exif else None
        if isinstance(raw_value, int) and raw_value in _EXIF_ORIENTATION_MEANING:
            exif_value = raw_value
        elif raw_value is not None:
            observation["reason"] = "unusable EXIF orientation %r" % (raw_value,)
    except Exception as exc:
        observation["reason"] = "EXIF unreadable: %s" % exc
    observation["exif_orientation"] = exif_value

    # OSD runs only where it can decide something, or when a caller explicitly
    # asks for it as evidence beside EXIF. Production does neither when EXIF
    # already resolves the frame - a second Tesseract pass costs seconds.
    if exif_value is None or observe_osd or osd_reader is not None:
        observation["osd"] = _osd_observation(raw_bytes, reader=osd_reader)

    osd = observation["osd"] or {}

    if exif_value is not None:
        rotation, mirror = _EXIF_ORIENTATION_MEANING[exif_value]
        observation["authority"] = ORIENTATION_AUTHORITY_EXIF
        # EXIF outranks OSD, so this decides nothing - it records that the two
        # signals disagreed, which is the only way a wrong tag becomes visible.
        if osd.get("ran") and (osd.get("rotate") or 0) % 360 != rotation % 360:
            observation["conflict"] = True
        if rotation or mirror:
            try:
                upright = ImageOps.exif_transpose(image)
                observation["applied_rotation_degrees"] = rotation
                observation["applied_mirror"] = mirror
                observation["normalised_size"] = list(upright.size)
                observation["changed"] = True
                return {"bytes": _encode_frame(upright), "observation": observation}
            except Exception as exc:
                observation["authority"] = ORIENTATION_AUTHORITY_UNRESOLVED
                observation["reason"] = "transform failed: %s" % exc
        return {"bytes": raw_bytes, "observation": observation}

    if osd.get("ran") and (osd.get("rotate") or 0) % 360:
        confidence = osd.get("confidence")
        if confidence is None or confidence < OSD_MINIMUM_CONFIDENCE:
            # Below the floor this is a guess, and a guess that rotates the
            # customer's drawing is worse than leaving it alone. Recorded so
            # the refusal is visible rather than looking like OSD never ran.
            observation["reason"] = (
                "OSD confidence %s below %.1f - rotation not applied"
                % (confidence, OSD_MINIMUM_CONFIDENCE))
            return {"bytes": raw_bytes, "observation": observation}
        rotation = osd["rotate"] % 360
        try:
            # OSD reports how far the page must be turned to come upright.
            upright = image.rotate(-rotation, expand=True)
            observation["authority"] = ORIENTATION_AUTHORITY_OSD
            observation["applied_rotation_degrees"] = rotation
            observation["normalised_size"] = list(upright.size)
            observation["changed"] = True
            return {"bytes": _encode_frame(upright), "observation": observation}
        except Exception as exc:
            observation["authority"] = ORIENTATION_AUTHORITY_UNRESOLVED
            observation["reason"] = "transform failed: %s" % exc

    return {"bytes": raw_bytes, "observation": observation}


def _encode_frame(image):
    """The derived processing frame.

    PNG, so the perception layer never reads a re-compressed copy of the
    customer's picture: a JPEG round trip would add artefacts to the very
    pixels the next stage is trying to read. compress_level=1 because this
    frame is consumed immediately and never stored.
    """
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "PNG", compress_level=1)
    return buffer.getvalue()


#: The one working-frame container. Every frame handed to perception is a
#: lossless PNG, whatever arrived and whatever happened to it on the way.
WORKING_FRAME_FILETYPE = "png"


def working_frame(normalised: dict, filename: str):
    """The frame perception reads, decided EXPLICITLY. Returns (bytes, filetype).

    CLAUDE-GO-PERCEPTION-WORKING-FRAME-01. The defect this repairs is not a
    quality defect - it is that the frame's REPRESENTATION was an accident of
    something unrelated. `normalise_orientation` re-encodes to PNG when it
    rotates and passes the original bytes through when it does not, and the
    caller then set `filetype` from that same fact. So the SAME photograph, of
    the SAME drawing, was read through a different container depending on which
    way up the phone was held - and the container is not cosmetic: measured on
    three real drawing rasters, the pixels PyMuPDF finally hands the OCR engine
    differ between the two by 20-56% of the frame, with a maximum per-channel
    delta of 147. Two identical images must not be read differently because one
    of them needed rotating.

    THE QUALITY CLAIM THAT PROMPTED THIS TRANCHE DID NOT REPRODUCE, and saying
    so is part of the repair. The recorded 4,953 -> 9,548 character result came
    from a customer JPEG that is not on this machine. Measured on three real
    rasters delivered as JPEG, a lossless frame gave +7.8%, -3.7% and -11.5%
    characters - mixed, source-dependent, and no systematic win. What it DID do
    is improve the downstream answer on two of the three (A-01 gained a
    SUPPORTED `LEGEND` candidate it did not previously find at all, M2_OF_3
    gained `LEGENDS:`) and degrade it on none. On an already-PNG source the
    re-encode is provably a no-op: every metric moved 0.0% across all three.

    So the justification is DETERMINISM AND EQUAL TREATMENT, not a quality
    improvement - and one deterministic rule is enough. Choosing per source
    would mean reading every image twice to find out which container won, which
    is a real doubling of the most expensive step in the pipeline for a benefit
    this measurement cannot establish.

    NOTHING IS ENHANCED. No sharpening, denoising, thresholding, rescaling or
    model runs here. The frame is the same pixels in a container that does not
    depend on rotation.
    """
    from PIL import Image

    frame = normalised["bytes"]
    if normalised["observation"].get("changed"):
        # Already a lossless PNG: `normalise_orientation` encodes what it
        # rotated. Re-encoding it a second time would cost work to change
        # nothing.
        return frame, WORKING_FRAME_FILETYPE
    if (Path(filename or "").suffix.lower() == ".png"):
        # Already lossless, and the control measurement proves a round trip
        # changes literally nothing - 0.0% on every metric on three real
        # sources. Passing it through is the same frame for less work.
        return frame, WORKING_FRAME_FILETYPE
    try:
        image = Image.open(io.BytesIO(frame))
        image.load()
    except Exception as exc:  # noqa: BLE001 - an undecodable frame is a result
        logger.warning("working frame could not be decoded (%s: %s); "
                       "reading the stored bytes as-is",
                       type(exc).__name__, exc)
        # HONEST DEGRADATION, not a failure. A frame that cannot be decoded
        # here would not survive the extractor either; handing over what
        # arrived keeps the old behaviour rather than turning a readable-ish
        # image into no reading at all.
        return frame, "jpeg"
    return _encode_frame(image), WORKING_FRAME_FILETYPE


def extract_image_text(raw_bytes: bytes, filename: str, *, engine=None,
                       osd_reader=None) -> dict:
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

    # CLAUDE-GO-PERCEPTION-ORIENTATION-01: read the frame the PERSON sees. The
    # stored source is untouched; this is a derived processing frame only.
    normalised = normalise_orientation(raw_bytes, filename, osd_reader=osd_reader)
    orientation = normalised["observation"]
    # CLAUDE-GO-PERCEPTION-WORKING-FRAME-01: an explicit decision now, not a
    # by-product of whether this image happened to need rotating.
    frame, filetype = working_frame(normalised, filename)

    result = raster_extraction.extract_raster_pages(
        frame, [0], filetype=filetype, engine=engine)
    pages = result.get("pages") or {}
    return {
        "ran": result.get("ran", False),
        "status": result.get("status"),
        "engine": result.get("engine"),
        "engine_version": result.get("engine_version"),
        "reason": result.get("reason"),
        # How the frame this text was read from was arrived at, so a reader can
        # reconstruct original -> observation -> transform -> extractor.
        "orientation": orientation,
        # Empty string, never a fabricated placeholder - an image that yielded
        # nothing yielded nothing, and As-Read must be able to say so.
        "text": pages.get(0, ""),
    }


def extract_image_positioned_text(raw_bytes: bytes, filename: str, *,
                                  ocr=None, osd_reader=None) -> dict:
    """The same reading as `extract_image_text`, with coordinates attached.

    CLAUDE-GO-PERCEPTION-REGION-OCR-01. A SIBLING of the function above, not a
    replacement for it, and not a second pipeline: both normalise orientation
    the same way and both hand the same derived frame to the same engine. What
    differs is only that this one also asks where each line was.

    It costs ONE OCR pass, not two. services/positioned_text.py builds a single
    PyMuPDF textpage and reads the plain text and the positioned words off that
    same object, so attaching coordinates does not lengthen a job that already
    runs 5-21 seconds on a real photograph.

    Verified against production before being relied on, over three real stored
    sources: 295 -> 295, 866 -> 866 and 4,953 -> 4,953 characters, character
    for character, at identical legible ratios. Coordinates were added; the
    perception was not changed. The comment below records the one place that
    was nearly untrue and what was done about it.

    Returns `extract_image_text`'s shape plus `lines`, `frame`, and the counts,
    so a caller that only wants text can use it interchangeably.
    """
    from PIL import Image

    from services import positioned_text

    normalised = normalise_orientation(raw_bytes, filename, osd_reader=osd_reader)
    orientation = normalised["observation"]

    # THE SAME BYTES AND THE SAME FILETYPE `extract_image_text` HANDS OVER -
    # still true, and now true of one explicit decision instead of two copies
    # of a conditional.
    #
    # CLAUDE-GO-PERCEPTION-WORKING-FRAME-01 took the bounded tranche the note
    # that stood here asked for. What it found is not what that note predicted:
    # the 4,953 -> 9,548 result came from a customer JPEG that is not on this
    # machine and DID NOT REPRODUCE on three real drawing rasters, which gave
    # +7.8%, -3.7% and -11.5% characters. The frame rule changed anyway,
    # because the defect was never really about quality - it was that the SAME
    # photograph was read through a different container depending on whether it
    # needed rotating, and the container moves 20-56% of the pixels the engine
    # finally sees. See `working_frame` for the full reasoning.
    frame_bytes, filetype = working_frame(normalised, filename)
    frame_size = orientation.get("normalised_size")
    try:
        image = Image.open(io.BytesIO(frame_bytes))
        image.load()
        frame_size = list(image.size)
    except Exception as exc:  # noqa: BLE001 - an undecodable frame is a result
        return {
            "ran": False, "status": None, "engine": None, "engine_version": None,
            "reason": "the frame could not be decoded (%s)" % type(exc).__name__,
            "orientation": orientation, "text": "", "lines": [],
            "line_count": 0, "word_count": 0, "dropped_line_count": 0,
            "truncated": False, "frame": None, "confidence_available": False,
        }

    read = positioned_text.read_positioned_lines(
        frame_bytes, frame_size, filetype=filetype, ocr=ocr)

    text = (read.get("text") or "")
    return {
        "ran": read.get("ran", False),
        # The same three-state vocabulary raster_extraction uses, derived the
        # same way: something readable, or an honest nothing. No new states.
        "status": ("readable" if text.strip() else "unreadable"),
        "engine": read.get("engine"),
        "engine_version": read.get("engine_version"),
        "reason": read.get("reason"),
        "orientation": orientation,
        "text": text,
        "lines": read.get("lines") or [],
        "line_count": read.get("line_count", 0),
        "word_count": read.get("word_count", 0),
        "dropped_line_count": read.get("dropped_line_count", 0),
        "truncated": read.get("truncated", False),
        "confidence_available": read.get("confidence_available", False),
        "frame": read.get("frame"),
    }
