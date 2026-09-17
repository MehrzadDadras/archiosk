"""CLAUDE-SURVEY-STAGE1-02 - north, measured off the sheet rather than asked for.

    THE ARROW IS A SHAPE. A SHAPE CAN BE MEASURED. ASKING IS THE WEAKER MOVE.

This module exists because of a specific production failure that the obvious
safeguard would not have caught.

On the live Castille sheet the reader described the north arrow as "pointing
upward-right" - which is correct - and in the same breath reported 355 degrees,
which is upward-LEFT. The renderer was faithful and drew 355, so a wrong north
reached a customer looking exactly as confident as a right one.

The first repair was to make the reader report north twice, as an angle and as
a direction word, and refuse the pair when they disagree. That gate is real and
it stays. But measuring the arrow off the sheet showed it points at 8.4 degrees
- and 8.4 and 355 fall in the SAME 45-degree sector. The categorical check
would have passed both. It catches a compass pointed at the floor; it cannot
catch a mirror-flip about vertical, which is the error that actually happened.

    A CATEGORICAL ENCODING CANNOT CATCH A SMALL MIRROR ERROR.
    ARITHMETIC ON THE PIXELS CAN.

So the division of labour moves one step further in the direction
`survey_graph` already argued for. The model LOCATES the arrow - which is
genuinely a perception problem, because a north arrow can be anywhere on a
sheet and looks like many other things. This module MEASURES it, with no model
involved, and its answer is the one that is believed. The model's own angle is
kept only to corroborate, on a tight threshold.

WHY A NEW MODULE. `survey_graph` is pure geometry over a graph and imports no
imaging; putting PIL in it would give the deterministic geometry layer a
dependency on pixels it has never needed. `visual_examination` owns the model
call and the egress audit, and this does neither - it runs entirely on bytes
already in hand, transmits nothing, and must remain obviously free of egress.
`sheet_vision` is PDF/vector work bound to a separate provider grant. None of
the three fits, and the seam this sits on - located symbol in, angle out - is
small and self-contained.

WHAT IT DOES NOT DO. It does not search for the arrow. Given no bounding box it
measures nothing and says so; a whole-sheet hunt for "the dark blob that looks
most like an arrow" is exactly the kind of confident guess this module exists
to replace.

THE PRODUCTION HIERARCHY, and it has exactly two outcomes.

    validated bbox + deterministic measurement  ->  accepted north
    anything else                               ->  UNRESOLVED

There is deliberately no third branch. A fallback to the reader's own angle
used to sit here and it was removed on evidence: the Castille arrow was read
three times under three prompt generations and claimed 355, then 0, then 30
degrees for one unchanging symbol that measures 8.33. Two escalating prompt
versions failed to make the reader return a box at all. So a missing box means
no north, and the cost - a record whose claim happened to be right also loses
its arrow - is accepted, because nothing can tell those records apart.

IF A DETERMINISTIC LOCATOR IS BUILT LATER, three conditions come with it,
recorded here because they are easy to lose and expensive to rediscover:

  - it needs its OWN qualification test across VARIED sheets before it may
    feed this module in production, not a demonstration on one survey;
  - it must NOT assume the symbol lives in a title block or any fixed region
    of the sheet - north arrows sit wherever the drafter put them;
  - a human-supplied box is legitimate for development fixtures and must
    never become a requirement of normal production operation.
"""
from __future__ import annotations

import io
import logging
import math
from typing import Optional

logger = logging.getLogger(__name__)

MEASURE_VERSION = "survey-north-01"

#: How far the model's own angle may sit from the measured one and still be
#: called corroboration. Product Owner direction, 2026-09-16: tight, because a
#: loose threshold turns corroboration into a rubber stamp. The Castille error
#: was 13.4 degrees and must not pass.
CORROBORATION_DELTA_DEGREES = 10.0

REFERENCE_TYPES = ("TRUE_NORTH", "GRID_NORTH", "MAGNETIC_NORTH", "ASSUMED_NORTH", "OTHER", "UNRESOLVED")
SOURCE_TYPES = ("survey_arrow", "title_block", "survey_note", "baseline_bearing")
CONVERSION_CONTENT_TYPE = "survey_north_conversion"


def conversion_snapshot(candidate):
    import hashlib
    import json
    return hashlib.sha256(json.dumps({k: v for k, v in candidate.items()
                                     if k != "validated_conversion"}, sort_keys=True).encode()).hexdigest()


def propose_conversions(store, workspace, visual_evidence, graph):
    """Source-reading conversion claims use the existing human review mechanism."""
    import json
    from services.case_workspace import EVIDENCE_CLASS_AI_GENERATED_PROPOSAL
    for candidate in graph.get("north_candidates", []):
        if not isinstance(candidate.get("conversion_to_true"), dict):
            continue
        record = {"candidate_id": candidate.get("id"), "snapshot": conversion_snapshot(candidate),
                  "visual_evidence_id": visual_evidence["id"], "candidate": candidate,
                  "review_obligation": "Establish this signed reference-system conversion, source evidence and applicability to THIS_VIEW; a recorded offset is not proof."}
        row = store.register_evidence_item(workspace, visual_evidence["source_id"],
            EVIDENCE_CLASS_AI_GENERATED_PROPOSAL, json.dumps(record, sort_keys=True), CONVERSION_CONTENT_TYPE,
            actor="visual-worker")
        store.record_evidence_relationship(workspace, "evidence_item", row["id"],
            "evidence_item", visual_evidence["id"], "supports", provisional=True,
            created_by="visual-worker", reason="Proposed North reference conversion")


def resolve_conversions(store, workspace, visual):
    import json
    evidence = {e["id"]: e for e in workspace.evidence_items}
    for candidate in (visual.get("graph") or {}).get("north_candidates", []):
        snapshot = conversion_snapshot(candidate)
        review = {"state": "UNRESOLVED", "evidence_ids": []}
        for edge in workspace.relationships:
            if (edge.get("to_type") != "evidence_item" or edge.get("to_id") != visual.get("evidence_item_id")
                    or edge.get("from_type") != "evidence_item" or edge.get("relationship_type") != "supports"):
                continue
            row = evidence.get(edge["from_id"], {})
            if row.get("content_type") != CONVERSION_CONTENT_TYPE:
                continue
            try:
                record = json.loads(row["content"])
            except (KeyError, TypeError, ValueError):
                continue
            if (record.get("snapshot") != snapshot or record.get("candidate_id") != candidate.get("id")
                    or record.get("visual_evidence_id") != visual.get("evidence_item_id")):
                continue
            accepted = store.resolve_relationship_status(workspace, edge["id"])["status"] == "confirmed" and bool(edge.get("confirmed_by"))
            state = "ESTABLISHED" if accepted else "UNRESOLVED"
            review["state"] = state if not review["evidence_ids"] else (
                "ESTABLISHED" if state == review["state"] == "ESTABLISHED" else "UNRESOLVED")
            review["evidence_ids"].append(row["id"])
        candidate["validated_conversion"] = review
    return visual


def normalise_candidates(raw):
    """Retain readings; a provider cannot supply a successful pixel measurement."""
    from services import binding, survey_graph, visual_examination as vx
    candidates = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        record = {key: str(item.get(key) or "") for key in
                  ("id", "source_type", "reference_type", "reference_text", "provenance", "applicability")}
        record["reference_type"] = record["reference_type"] if record["reference_type"] in REFERENCE_TYPES else "UNRESOLVED"
        record["source_type"] = record["source_type"] if record["source_type"] in SOURCE_TYPES else "UNRESOLVED"
        record.update(binding.bind(survey_graph._num(item.get("degrees")),
            read_certainty=survey_graph._certainty(item.get("read_certainty")),
            bind_basis=item.get("bind_basis", "none"),
            claimed_bind_certainty=survey_graph._certainty(item.get("bind_certainty"))))
        record["degrees"] = record["value"]
        record["certainty"] = record["read_certainty"]
        record["bbox"] = vx._bbox(item.get("source_region"))
        record["source_region"] = dict(record["bbox"])
        record["direction"] = vx._direction_word(item.get("direction"))
        # A separately measured true direction or existing human confirmation
        # establishes conversion; extraction cannot supply review flags.
        record["conversion_to_true"] = item.get("conversion_to_true")
        candidates.append(record)
    return candidates


def resolve_true_north(graph):
    """Resolve typed, applicable, independently measured evidence without averaging."""
    from services import binding, survey_graph
    candidates = graph.get("north_candidates") or []
    result = {"state": "UNRESOLVED", "reference_type": "TRUE_NORTH", "degrees": None,
              "candidates": candidates, "conversions": [], "premises": [],
              "reason": "No established true-North direction for this view",
              "tolerance_degrees": CORROBORATION_DELTA_DEGREES}
    measured = []
    blocking = False
    for candidate in candidates:
        kind = candidate.get("reference_type", "UNRESOLVED")
        north, refusal = survey_graph._reconcile_north(candidate)
        usable = (north is not None and binding.bound_certainty(candidate) == "RECOVERED"
                  and candidate.get("source_type") in ("survey_arrow", "title_block")
                  and candidate.get("applicability") == "THIS_VIEW"
                  and bool(candidate.get("source_region")) and bool(candidate.get("provenance"))
                  and bool(candidate.get("reference_text")))
        result["premises"].append({"candidate_id": candidate.get("id"), "reference_type": kind,
                                  "state": "ESTABLISHED" if usable else "UNRESOLVED",
                                  "reason": refusal, "source_region": candidate.get("source_region")})
        if kind == "TRUE_NORTH" and not usable:
            blocking = True
        if usable:
            measured.append((candidate, north["degrees"]))
    true = [(c, angle) for c, angle in measured if c.get("reference_type") == "TRUE_NORTH"]
    for candidate, angle in measured:
        conversion = candidate.get("conversion_to_true")
        if not isinstance(conversion, dict) or candidate.get("reference_type") not in ("GRID_NORTH", "MAGNETIC_NORTH", "ASSUMED_NORTH"):
            continue
        offset = survey_graph._num(conversion.get("clockwise_image_offset_degrees"))
        if ((candidate.get("validated_conversion") or {}).get("state") == "ESTABLISHED"
                and conversion.get("from") == candidate.get("reference_type")
                and conversion.get("to") == "TRUE_NORTH" and conversion.get("applicability") == "THIS_VIEW"
                and conversion.get("provenance") and offset is not None
                and binding.bound_certainty(conversion) == "RECOVERED"):
            true.append((candidate, (angle + offset) % 360))
            result["conversions"].append(dict(conversion, state="ESTABLISHED",
                candidate_id=candidate.get("id"), proof=candidate["validated_conversion"]))
    if not true or blocking:
        return result
    if any(angular_delta(a, b) > CORROBORATION_DELTA_DEGREES for _, a in true for _, b in true):
        result["reason"] = "Conflicting true-North candidates; no priority or averaging resolves conflict"
        return result
    # Keep an actual measurement, not a new synthetic average.
    anchor, angle = true[0]
    result.update(state="ESTABLISHED", degrees=angle, reason="Corroborated applicable true-North measurement")
    for candidate, other_angle in measured:
        kind = candidate.get("reference_type")
        if kind in ("GRID_NORTH", "MAGNETIC_NORTH", "ASSUMED_NORTH"):
            result["conversions"].append({"from": kind, "to": "TRUE_NORTH",
                "candidate_id": candidate.get("id"), "true_candidate_id": anchor.get("id"),
                "clockwise_image_offset_degrees": (angle - other_angle + 180) % 360 - 180,
                "operator": "difference_of_established_same_view_directions", "state": "ESTABLISHED",
                "scope": "observed_image_directions_only", "numerical_status": "APPROXIMATE"})
    return result


def directional_observation(observation):
    """Conservative legacy admission guard; recognition does not establish North."""
    import re
    if observation.get("directional_reference") in REFERENCE_TYPES[:-1]:
        return True
    if observation.get("key") in ("north", "bearings"):
        return True
    if observation.get("key") in ("address", "streets", "surveyor", "plan_number", "plan_date"):
        return False  # A proper street/address name is not a directional claim.
    return bool(re.search(r"\b(?:north|south|east|west)(?:ern|ward|wards|east|west)?\b|\b[NS]\s*\d", observation.get("value", ""), re.I))


def admits_true_direction(observation, resolution):
    # A resolved arrow does not silently retype an unrelated grid-relative claim.
    return (resolution["state"] == "ESTABLISHED"
            and observation.get("directional_reference") == "TRUE_NORTH")

#: A wedge smaller than this is noise - a speck of dust, a fold, a JPEG
#: artefact - and measuring its axis would produce a confident number from
#: nothing.
MIN_WEDGE_PIXELS = 150

#: The solid wedge is much darker than the thin circle outline around it. This
#: threshold keeps the fill and drops the outline, so the axis is the wedge's
#: and not the circle's (a circle has no axis, and fitting one returns noise).
INK_MAX_LEVEL = 70

#: An arrow that fills almost none of its box, or all of it, was not framed.
MIN_FILL_RATIO = 0.01
MAX_FILL_RATIO = 0.70


def _crop_box(size, bbox) -> Optional[tuple]:
    """The bbox as pixel bounds, or None when it is not usable.

    Fractions of the whole image, matching every other coordinate the reader
    returns. Refused rather than clamped when it falls outside the frame: a box
    off the edge means the reader was extrapolating, and a clamped box would
    measure whatever happened to be at the boundary.
    """
    width, height = size
    try:
        x = float(bbox["x"]); y = float(bbox["y"])
        w = float(bbox["w"]); h = float(bbox["h"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(v) for v in (x, y, w, h)):
        return None
    if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > 1.0001 or y + h > 1.0001:
        return None
    left, top = int(x * width), int(y * height)
    right, bottom = int((x + w) * width), int((y + h) * height)
    if right - left < 8 or bottom - top < 8:
        return None
    return (left, top, right, bottom)


def measure_north(image_bytes: bytes, bbox) -> dict:
    """The angle the arrow points, in degrees clockwise from image-up.

    `bbox` is where the reader says the arrow is, as image fractions. Returns
    {"ok", "degrees", "pixels", "reason"}. NEVER RAISES - an unmeasurable arrow
    is an outcome the caller reports, not an exception it has to catch, and a
    corrupt or unusual image must not be able to fail an examination that has
    already succeeded at everything else.

    THE METHOD. Inside the box, the solid wedge is isolated by darkness and its
    principal axis found by moments. An axis has two ends and no inherent
    direction, so the sign is settled by shape: the wedge is a triangle with
    its apex at the rose's centre and its wide end at north, so the half with
    the greater perpendicular spread is the end it points at. That is a
    property of how north arrows are drawn, not an assumption about this sheet.
    """
    if not image_bytes:
        return _failed("there are no bytes to measure")
    box = None
    try:
        from PIL import Image

        with Image.open(io.BytesIO(image_bytes)) as source:
            grey = source.convert("L")
            box = _crop_box(grey.size, bbox)
            if box is None:
                return _failed("no usable bounding box was given for the arrow")
            crop = grey.crop(box)
            pixels = crop.load()
            width, height = crop.size
            points = [(x, y) for x in range(width) for y in range(height)
                      if pixels[x, y] < INK_MAX_LEVEL]
    except Exception as exc:  # noqa: BLE001 - see docstring: never raises
        logger.warning("north could not be measured (%s: %s)",
                       type(exc).__name__, exc)
        return _failed("the image could not be read for measurement")

    count = len(points)
    if count < MIN_WEDGE_PIXELS:
        return _failed("no solid arrow was found inside the marked area")

    fill = count / float(max((box[2] - box[0]) * (box[3] - box[1]), 1))
    if not (MIN_FILL_RATIO <= fill <= MAX_FILL_RATIO):
        return _failed("the marked area does not frame an arrow "
                       "(it is %.0f%% ink)" % (fill * 100.0))

    total = float(count)
    mx = sum(p[0] for p in points) / total
    my = sum(p[1] for p in points) / total
    sxx = sum((p[0] - mx) ** 2 for p in points) / total
    syy = sum((p[1] - my) ** 2 for p in points) / total
    sxy = sum((p[0] - mx) * (p[1] - my) for p in points) / total
    if sxx + syy <= 0:
        return _failed("the arrow has no measurable extent")

    theta = 0.5 * math.atan2(2 * sxy, sxx - syy)
    vx, vy = math.cos(theta), math.sin(theta)

    def spread(sign: float) -> float:
        half = [p for p in points
                if ((p[0] - mx) * vx + (p[1] - my) * vy) * sign > 0]
        if not half:
            return 0.0
        return sum(abs(-(p[0] - mx) * vy + (p[1] - my) * vx)
                   for p in half) / len(half)

    wide, narrow = spread(1.0), spread(-1.0)
    if abs(wide - narrow) < 1e-9:
        return _failed("the arrow is symmetric, so which end is north "
                       "cannot be told from its shape")
    sign = 1.0 if wide > narrow else -1.0
    dx, dy = vx * sign, vy * sign

    return {"ok": True, "degrees": round(math.degrees(math.atan2(dx, -dy)) % 360.0, 2),
            "pixels": count, "reason": None}


def _failed(reason: str) -> dict:
    return {"ok": False, "degrees": None, "pixels": 0, "reason": reason}


def angular_delta(a: float, b: float) -> float:
    """The smaller angle between two headings, 0..180."""
    gap = abs(float(a) - float(b)) % 360.0
    return min(gap, 360.0 - gap)


def corroborates(measured: float, claimed) -> bool:
    """Whether the reader's own angle backs the measurement up."""
    if claimed is None:
        return False
    return angular_delta(measured, claimed) <= CORROBORATION_DELTA_DEGREES
