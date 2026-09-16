"""CLAUDE-SURVEY-REFERENCE-02 - the parametric graph, and deterministic geometry.

    THE MODEL IDENTIFIES AND BINDS EVIDENCE. THIS MODULE CONSTRUCTS THE DRAWING.

V1 asked the reader for polygons and drew them. That is a traced diagram: the
curved Castille Avenue frontage arrived as a chain of straight segments because
a polygon is all a polygon can be, and the one number on the sheet that
actually defines that curve - RADIUS 153.76, beside CHORD 139.20 - was captured
as a text observation and then not used for anything.

So the division of labour changes, and only the division:

  - the reader returns a GRAPH - corner nodes, segments with their kind,
    footprints, north, street labels, dimensions and bearings, each with its
    own certainty and its own evidence binding;
  - this module computes the geometry from that graph, deterministically, with
    no model involved. An arc segment carrying a radius becomes a real circular
    arc through its two endpoints.

WHAT DETERMINISTIC BUYS THAT A POLYGON CANNOT

A circle through two known points with a known radius is fully determined up to
which side it bulges, and the sheet says which side. So the frontage is not an
approximation of a curve - it is the curve the surveyor recorded, reconstructed
from its own parameters.

    SCALE IS DERIVED FROM THE SEGMENT'S OWN CHORD, NOT GUESSED.

The nodes are in image fractions and the radius is in survey feet, so the two
have to be related before any arc can be drawn. `_arc_from_chord_and_radius`
derives the scale from THAT SEGMENT's own chord dimension against its own
endpoint separation - self-consistent by construction, needing no sheet scale,
no title-block ratio and no cross-segment assumption.

FIVE REFUSALS, each of which would otherwise make a drawing look finished:

1. NO FORCED CLOSURE. A boundary whose segments do not form a closed ring is
   drawn open, and the gap is reported. V1's polygon could not express "the
   surveyor's chain does not close here", so it always closed.
2. NO INVENTED CURVATURE. An arc segment whose radius was not read is drawn as
   a STRAIGHT line and its curvature is reported unresolved - never a guessed
   bulge.
3. NO GEOMETRICALLY IMPOSSIBLE ARC. A radius smaller than half its own chord
   cannot pass through both endpoints. It is refused and reported, not clamped
   to the minimum that would have worked.
4. NO UNSUPPORTED DIMENSION. A dimension is drawn only where its certainty
   bears a value, and it is drawn as the sheet's own string, never recomputed
   from the reconstructed geometry - a measured 44.09 and a pixel-derived 43.6
   must never be confusable.
5. NO INFERRED NORTH. Absent a read north arrow, no arrow is drawn.

ONE GEOMETRY, TWO EMITTERS. `build_primitives` resolves the graph into plain
primitives once; `emit_svg` and the PDF renderer in `survey_reference` both
consume that list. The review drawing on screen and the exported sheet are
therefore the same geometry by construction, not by two implementations
agreeing.
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from services import visual_examination as vx

logger = logging.getLogger(__name__)

GRAPH_VERSION = "survey-graph-01"

# -- Vocabulary --------------------------------------------------------------

NODE_KINDS = ("property_corner", "monument", "curve_point", "reference")
SEGMENT_KINDS = ("straight", "arc")
BOUNDARY_ROLES = ("street_line", "lot_line", "interior", "easement", "unknown")
FOOTPRINT_KINDS = ("dwelling", "garage", "accessory", "structure")

#: Which side of the travel direction P1->P2 an arc bulges toward.
BULGE_LEFT = "left"
BULGE_RIGHT = "right"
BULGE_SIDES = (BULGE_LEFT, BULGE_RIGHT)

# -- Primitive types the renderers consume -----------------------------------
P_LINE = "line"
P_ARC = "arc"
P_POLYGON = "polygon"
P_POLYLINE = "polyline"
P_LABEL = "label"
P_NORTH = "north"


#: Render layers. A caller asks for the layers it wants and gets exactly those.
#: This is also the whitelist a request from Ask GO is validated against, which
#: is why it is a frozen tuple of plain tokens and not, say, a free-text filter.
LAYER_PROPERTY_BOUNDARY = "property_boundary"
LAYER_NORTH = "north"
LAYER_FOOTPRINTS = "footprints"
LAYER_LABELS = "labels"
#: Interior and easement lines - part of the parcel drawing but NOT the
#: property boundary. Named separately so "give me the property boundary"
#: cannot quietly also hand back an easement.
LAYER_OTHER_LINES = "other_lines"
LAYERS = (LAYER_PROPERTY_BOUNDARY, LAYER_NORTH, LAYER_FOOTPRINTS,
          LAYER_LABELS, LAYER_OTHER_LINES)

#: CLAUDE-SURVEY-STAGE1-01. Stage 1 draws the property boundary and north, and
#: nothing else - buildings, setbacks, easements, notes and the auxiliary text
#: layers are out of scope for this phase by Product Owner direction. The DATA
#: is untouched; it is simply not drawn yet.
STAGE1_LAYERS = (LAYER_PROPERTY_BOUNDARY, LAYER_NORTH)

#: Boundary roles that ARE the property boundary, for the traverse.
BOUNDARY_LAYER_ROLES = ("street_line", "lot_line")

#: Roles that are positively NOT the parcel edge. Everything else - including a
#: run the reader returned without classifying - draws as boundary, because
#: silently dropping an unclassified side loses real geometry and leaves a
#: convincing, emptier drawing.
NON_BOUNDARY_ROLES = ("interior", "easement")


class GraphError(ValueError):
    """A graph that cannot be reduced to geometry at all. Never raised at a
    caller - `normalise_graph` returns refusals as unresolved entries."""


# -- Normalisation -----------------------------------------------------------

def _num(value) -> Optional[float]:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _point(raw) -> Optional[tuple]:
    """A node position as image fractions, or None.

    Out of frame is REFUSED rather than clamped, the same rule
    `visual_examination._clean_polygon` applies: a point outside the picture is
    the signature of a reader extrapolating past what it can see, and clamping
    it would invent a corner.
    """
    x, y = _num((raw or {}).get("x")), _num((raw or {}).get("y"))
    if x is None or y is None:
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        return None
    return (round(x, 5), round(y, 5))


def _certainty(raw) -> str:
    value = str(raw or "").strip().upper()
    return value if value in vx.KNOWN_CERTAINTIES else vx.UNRESOLVED


def _dimension(raw) -> Optional[dict]:
    """A dimension as the SHEET prints it, or None.

    `text` is kept verbatim and is what gets drawn; `value` is the parsed
    number and is used only for arithmetic (deriving an arc's scale). They are
    separate fields because a drawn dimension must be the surveyor's own string
    - 65'-10 1/2" is not 65.875, and printing the second where the sheet says
    the first would be a silent re-measurement.
    """
    if not isinstance(raw, dict):
        return None
    certainty = _certainty(raw.get("certainty"))
    text = str(raw.get("text") or "").strip()
    if certainty not in vx.VALUE_BEARING or not text:
        return None

    # CLAUDE-MUSCLE-F1-01: READING IT AND ATTACHING IT ARE TWO CLAIMS.
    #
    # This is the exact record that carried the defect. On the live Castille
    # sheet `144.12` stored `certainty: RECOVERED`, which was true of reading
    # the digits and unproven of the attachment to LOT LINE 3 - the annotation
    # is merely printed near that run. One field carried both claims and the
    # stronger won silently.
    #
    # `certainty` is kept and still means READ certainty, so every existing
    # consumer keeps its meaning. What is new is that the binding now has its
    # own certainty and its own ceiling, and `bound_certainty` - the weaker of
    # the two - is what anything stating a fact ABOUT THE SEGMENT must use.
    from services import binding

    bound = binding.bind(
        _num(raw.get("value")), read_certainty=certainty,
        bind_basis=binding.BIND_BASIS_PROXIMITY,
        note="annotation printed near the segment; no structural container")
    return {"text": text[:40], "value": _num(raw.get("value")),
            "unit": str(raw.get("unit") or "").strip()[:12],
            "certainty": certainty,
            "read_certainty": certainty,
            "bind_certainty": bound["bind_certainty"],
            "bind_basis": bound["bind_basis"],
            "bound_certainty": bound["bound_certainty"]}


def _bearing(raw) -> Optional[dict]:
    """A bearing as the sheet prints it, PLUS its azimuth where one was read.

    CLAUDE-SURVEY-STAGE1-01. Bearings used to go through `_dimension`, which
    keeps `text` and a scalar `value` and drops everything else - so a numeric
    azimuth could not survive normalisation even once the reader started
    returning one, and a traverse solver would have found no bearings on any
    sheet whatsoever. A bearing is not a length: it needs its own shape.

    `value_degrees` is absent whenever the sheet's bearing could not be read.
    That absence is what makes a run non-computable, and it is meant to.
    """
    if not isinstance(raw, dict):
        return None
    certainty = _certainty(raw.get("certainty"))
    text = str(raw.get("text") or "").strip()
    if certainty not in vx.VALUE_BEARING or not text:
        return None
    azimuth = _num(raw.get("value_degrees"))
    quadrant = str(raw.get("quadrant") or "").strip().upper()[:2]
    return {
        "text": text[:40],
        "value_degrees": None if azimuth is None else round(azimuth % 360.0, 4),
        "quadrant": quadrant if quadrant in ("NE", "SE", "SW", "NW") else "",
        "certainty": certainty,
    }


#: Where a north value came from. Recorded on the value itself, because "8.4
#: degrees" means something different when arithmetic produced it than when a
#: model asserted it, and a reader of the record must be able to tell.
#: HOW A DRAWN LINE CAME TO BE WHERE IT IS. Carried on every boundary
#: primitive so a rendered line can never be mistaken for a surveyed one.
#:
#: `computed_traverse` means the run was laid off from a bearing and a distance
#: the sheet actually prints - a reconstruction of the surveyor's own figures.
#:
#: `observed_graphic_dimension` means it was drawn from where the reader
#: located its corners, carrying whatever dimension the sheet printed. It is an
#: observation OF A DRAWING, not a bearing. Product Owner direction,
#: 2026-09-16: sheets that dimension their lines instead of bearing them are
#: ordinary, not defective, and this flag is what keeps their lines honest -
#: a line so marked must never be read, quoted or exported as a legal bearing.
PROVENANCE_COMPUTED = "computed_traverse"
PROVENANCE_OBSERVED = "observed_graphic_dimension"

NORTH_MEASURED = "measured_pixel_axis"
NORTH_CLAIMED = "model_reading"

#: Each direction word and the arc of angles it covers, as (low, high) in
#: degrees clockwise from image-up. UP straddles 0 and is handled as two arcs.
_DIRECTION_ARCS = {
    "UP": ((337.5, 360.0), (0.0, 22.5)),
    "UP_RIGHT": ((22.5, 67.5),),
    "RIGHT": ((67.5, 112.5),),
    "DOWN_RIGHT": ((112.5, 157.5),),
    "DOWN": ((157.5, 202.5),),
    "DOWN_LEFT": ((202.5, 247.5),),
    "LEFT": ((247.5, 292.5),),
    "UP_LEFT": ((292.5, 337.5),),
}

#: How far outside its arc an angle may sit and still be called agreement.
#: Small on purpose: it exists so a reader who says UP_RIGHT for an angle of
#: exactly 22.5 is not called a liar, NOT to smooth over a real disagreement.
#: The failure this gate was built for - "upward-right" reported as 355 - is
#: 27.5 degrees outside its arc and is nowhere near this.
DIRECTION_TOLERANCE_DEGREES = 5.0


def _arc_distance(degrees: float, word: str) -> float:
    """How far `degrees` sits outside the arc `word` names. 0.0 when inside."""
    best = 360.0
    for low, high in _DIRECTION_ARCS[word]:
        if low <= degrees <= high:
            return 0.0
        for edge in (low, high):
            gap = abs(degrees - edge) % 360.0
            best = min(best, min(gap, 360.0 - gap))
    return best


def _reconcile_north(raw_north) -> tuple:
    """North, from the MEASUREMENT, once the reading corroborates it.

    CLAUDE-SURVEY-STAGE1-02. Product Owner direction, 2026-09-16: the
    deterministic pixel-axis measurement is the source of truth and the model's
    own angle is corroboration only, on a tight threshold.

    WHY IT IS THIS WAY ROUND, AND NOT THE OTHER. The reader described the
    Castille arrow as "pointing upward-right", which is right, and gave 355
    degrees, which is upward-left. Measuring the arrow off the sheet gives 8.4.
    The first repair here was categorical - report a direction word as well as
    an angle, and refuse the pair when they disagree - and that gate would have
    passed this, because 355 and 8.4 sit in the SAME 45-degree sector. A word
    catches a compass pointed at the floor. It cannot catch a mirror-flip about
    vertical, which is the error that actually happened.

    So the order of authority is: measurement, then reading.

      - measured, and the reading agrees within the threshold -> measured wins
      - measured, and the reading disagrees                   -> UNRESOLVED
      - no measurement                                        -> the reading,
        still held to the categorical gate it was already held to

    A DISAGREEMENT IS NEVER RESOLVED BY PREFERRING THE MEASUREMENT. It would be
    easy to argue the arithmetic should simply win. But a measurement of the
    wrong object - a hatch symbol, a logo, a fold in the paper - is arithmetic
    too, and it is wrong with total confidence. The reading is the only
    independent check that the box framed a north arrow at all, so losing that
    check is not a small thing, and the honest output when the two disagree is
    that north is unresolved.

    Returns (north_or_None, refusal_or_None).
    """
    if not isinstance(raw_north, dict):
        return None, None

    certainty = _certainty(raw_north.get("certainty"))
    if certainty not in vx.VALUE_BEARING:
        return None, None

    claimed = _num(raw_north.get("degrees"))
    claimed = None if claimed is None else round(claimed % 360.0, 2)
    measured = _num(raw_north.get("measured_degrees"))
    word = str(raw_north.get("direction") or "").strip().upper()

    if measured is not None and raw_north.get("measured_ok"):
        from services import survey_north

        measured = round(measured % 360.0, 2)
        if claimed is None:
            return {"degrees": measured, "direction": _word_for(measured),
                    "source": NORTH_MEASURED, "claimed_degrees": None,
                    "certainty": certainty}, None
        delta = survey_north.angular_delta(measured, claimed)
        if delta > survey_north.CORROBORATION_DELTA_DEGREES:
            return None, (
                "north arrow is unresolved: measuring the arrow on the sheet "
                "gives %.4g degrees, the reading gave %.4g, and those differ "
                "by %.4g - more than the %.4g allowed. Neither was preferred "
                "over the other" % (measured, claimed, delta,
                                    survey_north.CORROBORATION_DELTA_DEGREES))
        return {"degrees": measured, "direction": _word_for(measured),
                "source": NORTH_MEASURED, "claimed_degrees": claimed,
                "certainty": certainty}, None

    # No measurement: the reading is all there is, held to the categorical gate.
    if claimed is None:
        return None, None
    if not word:
        return {"degrees": claimed, "direction": "", "source": NORTH_CLAIMED,
                "claimed_degrees": claimed, "certainty": certainty}, None
    if word not in _DIRECTION_ARCS:
        return None, ("north arrow direction was reported as %r, which is not "
                      "one of the eight directions" % word[:24])
    outside = _arc_distance(claimed, word)
    if outside > DIRECTION_TOLERANCE_DEGREES:
        return None, ("north arrow is unresolved: it was read as pointing %s "
                      "but its angle was given as %.4g degrees, which is %s - "
                      "the two disagree and neither was preferred over the "
                      "other" % (word.replace("_", "-").lower(), claimed,
                                 _word_for(claimed).replace("_", "-").lower()))
    return {"degrees": claimed, "direction": word, "source": NORTH_CLAIMED,
            "claimed_degrees": claimed, "certainty": certainty}, None


def _word_for(degrees: float) -> str:
    """The direction word an angle falls in. For explaining a conflict."""
    for word in _DIRECTION_ARCS:
        if _arc_distance(degrees, word) == 0.0:
            return word
    return "UP"


#: A traverse closes when its misclosure is small RELATIVE to how far it ran.
#: 1:5000 is the ordinary urban cadastral standard. Expressed as a ratio rather
#: than an absolute distance because a 40m lot and a 4km boundary cannot share
#: one tolerance.
MISCLOSURE_RATIO_LIMIT = 5000.0

#: Below this perimeter a ratio stops meaning anything, so an absolute figure
#: is used instead - in the same units the sheet's own dimensions are in.
MISCLOSURE_ABSOLUTE_FLOOR = 0.05


def _azimuth_of(segment) -> Optional[float]:
    """A segment's whole-circle azimuth in degrees, or None.

    ONLY from a bearing the sheet actually printed. There is deliberately no
    fallback to the angle between two located nodes: that number is derived
    from where the reader thought the corners were, and feeding it into a
    traverse would produce coordinates that LOOK computed while being a
    restatement of the same estimate. A traverse that cannot be computed must
    say so.
    """
    bearing = segment.get("bearing")
    if not isinstance(bearing, dict):
        return None
    if bearing.get("certainty") not in vx.VALUE_BEARING:
        return None
    degrees = _num(bearing.get("value_degrees"))
    return None if degrees is None else degrees % 360.0


def _distance_of(segment) -> Optional[float]:
    """A segment's length from its own printed dimension, or None."""
    dimension = segment.get("dimension")
    if not isinstance(dimension, dict):
        return None
    if dimension.get("certainty") not in vx.VALUE_BEARING:
        return None
    value = _num(dimension.get("value"))
    return value if value and value > 0 else None


def segment_inputs(segment) -> dict:
    """What this segment offers a solver, and what it is missing.

    Reported per segment rather than as one verdict for the parcel, because a
    boundary is usually partly computable and saying "unresolved" about the
    whole of it would throw away the half that is real.
    """
    azimuth = _azimuth_of(segment)
    distance = _distance_of(segment)
    is_arc = segment.get("kind") == "arc"
    radius = _num((segment.get("radius") or {}).get("value"))
    chord = _num((segment.get("chord") or {}).get("value"))
    arc_defined = bool(is_arc and radius and chord)

    missing = []
    if azimuth is None and not arc_defined:
        missing.append("BEARING")
    if distance is None and not arc_defined:
        missing.append("DIMENSION")

    return {
        "id": segment["id"],
        "azimuth": azimuth,
        "distance": distance,
        "arc_defined": arc_defined,
        "radius": radius,
        "chord": chord,
        # Computable means THIS RUN can be laid off from its own numbers.
        "computable": bool((azimuth is not None and distance is not None)
                           or arc_defined),
        "missing": tuple(missing),
    }


def solve_traverse(graph: dict) -> dict:
    """Vertex coordinates computed from the sheet's own bearings and distances.

    CLAUDE-SURVEY-STAGE1-01. THE SOLVER IS DETERMINISTIC AND IT IS ALLOWED TO
    FAIL. It lays each run off from the previous corner using the printed
    bearing and distance; where a run has no such numbers it computes nothing
    for that run and says which input was missing. It never substitutes the
    angle between two located nodes for a bearing the sheet did not print -
    that would dress an estimate up as a computation.

    On the specimen this was built against, NOT ONE of five runs carries a
    bearing; the reading's own unresolved list says "All bearing values". So
    this returns `computed: False` there, and the drawing falls back to located
    corners which are rendered and tagged as such. That is the honest outcome,
    not a shortfall to be papered over.

    Returns {"computed", "points", "segments", "misclosure"}.
    """
    segments = list(graph.get("segments") or [])
    reports = [segment_inputs(s) for s in segments]
    by_id = {r["id"]: r for r in reports}

    boundary = [s for s in segments
                if s.get("boundary") in BOUNDARY_LAYER_ROLES]
    if not boundary:
        return {"computed": False, "points": {}, "segments": reports,
                "misclosure": _no_misclosure("there is no boundary to close")}

    if not all(by_id[s["id"]]["computable"] for s in boundary):
        short = sum(1 for s in boundary if not by_id[s["id"]]["computable"])
        return {"computed": False, "points": {}, "segments": reports,
                "misclosure": _no_misclosure(
                    "%d of %d boundary runs carry no bearing or no distance"
                    % (short, len(boundary)))}

    # Survey convention: azimuth clockwise from north, north is +y.
    # THE START IS CAPTURED HERE, NOT READ BACK LATER. A closed ring ends at
    # the node it began at, so `points[first]` is OVERWRITTEN by the final
    # cursor as the traverse comes round - and reading the start out of the
    # dict afterwards then compares the endpoint with itself and reports zero
    # misclosure for every ring, however badly it closes. The check would have
    # passed everything while looking like it was working.
    start = (0.0, 0.0)
    points = {boundary[0]["from"]: start}
    cursor = (0.0, 0.0)
    perimeter = 0.0
    for segment in boundary:
        report = by_id[segment["id"]]
        length = report["distance"] if report["distance"] else report["chord"]
        if length is None:
            return {"computed": False, "points": {}, "segments": reports,
                    "misclosure": _no_misclosure(
                        "run %s has no length to lay off" % segment["id"])}
        azimuth = report["azimuth"]
        if azimuth is None:
            return {"computed": False, "points": {}, "segments": reports,
                    "misclosure": _no_misclosure(
                        "run %s has no bearing to lay off" % segment["id"])}
        radians = math.radians(azimuth)
        cursor = (cursor[0] + length * math.sin(radians),
                  cursor[1] + length * math.cos(radians))
        points[segment["to"]] = cursor
        perimeter += length

    linear = math.hypot(cursor[0] - start[0], cursor[1] - start[1])
    ratio = (perimeter / linear) if linear > 1e-12 else float("inf")
    closes = (linear <= MISCLOSURE_ABSOLUTE_FLOOR
              or ratio >= MISCLOSURE_RATIO_LIMIT)

    return {
        "computed": True,
        "points": points,
        "segments": reports,
        "misclosure": {
            "computable": True,
            "linear": round(linear, 4),
            "perimeter": round(perimeter, 4),
            # Reported as the denominator of 1:N, which is how a surveyor reads
            # it. Infinite when the traverse closes exactly.
            "ratio": None if ratio == float("inf") else round(ratio, 1),
            "closes": closes,
            "limit": MISCLOSURE_RATIO_LIMIT,
            "reason": None if closes else (
                "misclosure %.4g over a perimeter of %.4g is 1:%.0f, wider "
                "than the 1:%.0f this is held to - the boundary is reported "
                "open rather than adjusted to close"
                % (linear, perimeter, ratio, MISCLOSURE_RATIO_LIMIT)),
        },
    }


def _no_misclosure(reason: str) -> dict:
    return {"computable": False, "linear": None, "perimeter": None,
            "ratio": None, "closes": False, "limit": MISCLOSURE_RATIO_LIMIT,
            "reason": reason}


def normalise_graph(raw) -> dict:
    """Everything the reader returned, reduced to what this module will draw.

    NEVER RAISES. Every refusal becomes an `unresolved` entry, because a graph
    that half-parses must produce a drawing that is honestly partial rather
    than an exception a caller has to decide what to do with.
    """
    raw = raw if isinstance(raw, dict) else {}
    unresolved = []

    nodes = {}
    for entry in (raw.get("nodes") or [])[:200]:
        if not isinstance(entry, dict):
            continue
        node_id = str(entry.get("id") or "").strip()[:24]
        position = _point(entry.get("at") or entry)
        if not node_id or position is None:
            continue
        kind = str(entry.get("kind") or "").strip()
        nodes[node_id] = {
            "id": node_id, "x": position[0], "y": position[1],
            "kind": kind if kind in NODE_KINDS else "property_corner",
            "label": str(entry.get("label") or "").strip()[:48],
            "certainty": _certainty(entry.get("certainty")),
        }

    segments = []
    for entry in (raw.get("segments") or [])[:200]:
        if not isinstance(entry, dict):
            continue
        start, end = str(entry.get("from") or ""), str(entry.get("to") or "")
        if start not in nodes or end not in nodes or start == end:
            continue
        kind = str(entry.get("kind") or "").strip()
        role = str(entry.get("boundary") or "").strip()
        bulge = str(entry.get("bulge_side") or "").strip().lower()
        segments.append({
            "id": str(entry.get("id") or "").strip()[:24] or "S%d" % (len(segments) + 1),
            "from": start, "to": end,
            "kind": kind if kind in SEGMENT_KINDS else "straight",
            "boundary": role if role in BOUNDARY_ROLES else "unknown",
            "label": str(entry.get("label") or "").strip()[:48],
            "dimension": _dimension(entry.get("dimension")),
            "bearing": _bearing(entry.get("bearing")),
            "radius": _dimension(entry.get("radius")),
            "chord": _dimension(entry.get("chord")),
            "bulge_side": bulge if bulge in BULGE_SIDES else None,
            "certainty": _certainty(entry.get("certainty")),
        })

    footprints = []
    for entry in (raw.get("footprints") or [])[:20]:
        if not isinstance(entry, dict):
            continue
        outline = [p for p in (_point(pt) for pt in (entry.get("outline") or [])[:60]) if p]
        if len(outline) < 3:
            continue
        kind = str(entry.get("kind") or "").strip()
        footprints.append({
            "id": str(entry.get("id") or "").strip()[:24] or "B%d" % (len(footprints) + 1),
            "kind": kind if kind in FOOTPRINT_KINDS else "structure",
            "label": str(entry.get("label") or "").strip()[:48],
            "outline": outline,
            "certainty": _certainty(entry.get("certainty")),
        })

    north, north_refusal = _reconcile_north(raw.get("north"))
    if north_refusal:
        unresolved.append(north_refusal)

    streets = []
    for entry in (raw.get("streets") or [])[:12]:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()[:48]
        if not label:
            continue
        along = [s for s in (entry.get("along_segments") or [])[:20] if isinstance(s, str)]
        streets.append({"label": label, "along_segments": along,
                        "certainty": _certainty(entry.get("certainty"))})

    unresolved += [str(u).strip()[:160] for u in (raw.get("unresolved") or [])[:24]
                   if str(u or "").strip()]

    return {"graph_version": GRAPH_VERSION, "nodes": nodes, "segments": segments,
            "footprints": footprints, "north": north, "streets": streets,
            "unresolved": unresolved}


# -- Deterministic geometry --------------------------------------------------

def _arc_from_chord_and_radius(p1, p2, radius_survey, chord_survey, bulge_side):
    """The circular arc through p1 and p2 with the surveyed radius.

    Returns (centre, radius_norm, start_deg, extent_deg) or (None, reason).

    THE SCALE COMES FROM THIS SEGMENT'S OWN CHORD. The endpoints are image
    fractions and the radius is in survey units; relating them needs one
    number, and the chord is the one the sheet prints for exactly this arc. No
    sheet scale, no title-block ratio, no assumption carried from another
    segment.

    The MINOR arc is chosen. On a lot frontage the surveyed chord and radius
    describe the short way round; the major arc would sweep the curve away
    across the whole parcel, which no street frontage does.
    """
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    separation = math.hypot(dx, dy)
    if separation <= 1e-9:
        return None, "the arc's endpoints coincide"
    if not radius_survey or not chord_survey or chord_survey <= 0:
        return None, "the arc has no readable radius and chord"

    scale = separation / float(chord_survey)
    radius = float(radius_survey) * scale
    half = separation / 2.0
    if radius < half - 1e-9:
        # A radius shorter than half its own chord describes no circle through
        # both points. REFUSED rather than clamped: clamping would silently
        # substitute a different curve for the surveyed one.
        return None, ("radius %s is smaller than half its own chord %s - no arc "
                      "can pass through both endpoints"
                      % (radius_survey, chord_survey))

    height = math.sqrt(max(radius * radius - half * half, 0.0))
    mid = ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)
    # Unit normal to the chord. Image space is y-DOWN, so "left of travel" is
    # (dy, -dx) normalised; the sign flip below is the only place that
    # convention matters.
    nx, ny = dy / separation, -dx / separation
    sign = 1.0 if bulge_side == BULGE_LEFT else -1.0
    centre = (mid[0] - sign * nx * height, mid[1] - sign * ny * height)

    start = math.degrees(math.atan2(p1[1] - centre[1], p1[0] - centre[0]))
    end = math.degrees(math.atan2(p2[1] - centre[1], p2[0] - centre[0]))
    extent = (end - start) % 360.0
    if extent > 180.0:
        extent -= 360.0
    return (centre, radius, start, extent), None


def build_primitives(graph: dict, include=None) -> dict:
    """The graph resolved into drawable primitives, once, for both renderers.

    Returns {"primitives": [...], "unresolved": [...], "stats": {...}}. All
    coordinates stay image fractions with a top-left origin; each renderer maps
    them into its own frame, so nothing here knows about points, pixels or
    page size.

    `include` names the LAYERS to draw, from `LAYERS`. None means every layer,
    which is what every caller meant before layers existed. Stage 1 callers
    pass `STAGE1_LAYERS` - the property boundary and north, nothing else.

    CLAUDE-SURVEY-STAGE1-01: WHERE THE TRAVERSE COULD NOT BE COMPUTED.
    `solve_traverse` runs here so each run can be marked with what it was
    missing. A run whose bearing or dimension the sheet never gave is drawn
    from its located corners and TAGGED, never quietly drawn as though it had
    been computed. The tag is the difference between a reconstruction and a
    drawing that merely looks like one.
    """
    include = tuple(LAYERS) if include is None else tuple(include)
    traverse = solve_traverse(graph)
    inputs = {r["id"]: r for r in traverse["segments"]}
    nodes = graph.get("nodes") or {}
    unresolved = list(graph.get("unresolved") or [])
    primitives = []
    arcs = straights = 0

    for segment in graph.get("segments") or []:
        # A run the reader walked but did not classify is still a boundary
        # run. Only `interior` and `easement` are positively NOT the parcel
        # edge, so only they are excluded - dropping `unknown` here produced an
        # empty Stage 1 drawing from a graph that had two real sides in it,
        # which is the blank-panel failure all over again.
        wanted = (LAYER_OTHER_LINES
                  if segment["boundary"] in NON_BOUNDARY_ROLES
                  else LAYER_PROPERTY_BOUNDARY)
        if wanted not in include:
            continue
        report = inputs.get(segment["id"]) or {}
        # CLAUDE-SURVEY-STAGE1-02: what this line IS, travelling with the line.
        provenance = (PROVENANCE_COMPUTED if report.get("computable")
                      else PROVENANCE_OBSERVED)
        tags = tuple("[%s UNRESOLVED]" % m for m in report.get("missing", ()))
        p1 = (nodes[segment["from"]]["x"], nodes[segment["from"]]["y"])
        p2 = (nodes[segment["to"]]["x"], nodes[segment["to"]]["y"])
        certain = segment["certainty"] == vx.RECOVERED

        if segment["kind"] == "arc":
            radius = (segment.get("radius") or {}).get("value")
            chord = (segment.get("chord") or {}).get("value")
            resolved, reason = _arc_from_chord_and_radius(
                p1, p2, radius, chord, segment.get("bulge_side") or BULGE_LEFT)
            if resolved is None:
                # NO INVENTED CURVATURE. Drawn straight, and said out loud.
                straights += 1
                primitives.append({"type": P_LINE, "id": segment["id"],
                                   "a": p1, "b": p2, "certain": certain,
                                   "provenance": provenance, "tags": tags,
                                   "role": segment["boundary"],
                                   "label": segment["label"]})
                unresolved.append(
                    "curvature of %s not reconstructed: %s"
                    % (segment.get("label") or segment["id"], reason))
            else:
                centre, radius_norm, start, extent = resolved
                arcs += 1
                primitives.append({
                    "type": P_ARC, "id": segment["id"], "a": p1, "b": p2,
                    "centre": (round(centre[0], 5), round(centre[1], 5)),
                    "radius": round(radius_norm, 5),
                    "start_deg": round(start, 3), "extent_deg": round(extent, 3),
                    "certain": certain, "role": segment["boundary"],
                    "provenance": provenance, "tags": tags,
                    "label": segment["label"],
                    "radius_text": (segment.get("radius") or {}).get("text"),
                    "chord_text": (segment.get("chord") or {}).get("text")})
        else:
            straights += 1
            primitives.append({"type": P_LINE, "id": segment["id"],
                               "a": p1, "b": p2, "certain": certain,
                                   "provenance": provenance, "tags": tags,
                               "role": segment["boundary"],
                               "label": segment["label"]})

        # A dimension is drawn ONLY where the sheet supported one, and always
        # as the sheet's own string.
        dimension = segment.get("dimension")
        if LAYER_LABELS in include and dimension:
            primitives.append({
                "type": P_LABEL, "kind": "dimension", "text": dimension["text"],
                "at": ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                # CLAUDE-MUSCLE-F1-01: the weaker of read and bind. A
                # dimension read perfectly but attached by proximity is drawn
                # as the qualified thing it is.
                "certain": dimension.get("bound_certainty",
                                         dimension["certainty"]) == vx.RECOVERED,
                "for": segment["id"]})
        bearing = segment.get("bearing")
        if LAYER_LABELS in include and bearing:
            primitives.append({
                "type": P_LABEL, "kind": "bearing", "text": bearing["text"],
                "at": ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                "certain": bearing["certainty"] == vx.RECOVERED,
                "for": segment["id"]})

    for footprint in (graph.get("footprints") or []
                      if LAYER_FOOTPRINTS in include else []):
        primitives.append({
            "type": P_POLYGON, "id": footprint["id"], "kind": footprint["kind"],
            "points": footprint["outline"], "label": footprint["label"],
            "certain": footprint["certainty"] == vx.RECOVERED})

    north = graph.get("north") if LAYER_NORTH in include else None
    if north:
        primitives.append({"type": P_NORTH, "degrees": north["degrees"],
                           "certain": north["certainty"] == vx.RECOVERED})

    closure = boundary_closure(graph)
    if closure["gaps"]:
        # NO FORCED CLOSURE. Reported, never stitched.
        unresolved.append(
            "the boundary chain does not close (%d open %s)"
            % (len(closure["gaps"]), "end" if len(closure["gaps"]) == 1 else "ends"))

    return {"primitives": primitives, "unresolved": unresolved,
            "stats": {"arcs": arcs, "straights": straights,
                      "nodes": len(nodes),
                      "footprints": len(graph.get("footprints") or []),
                      # Topological closure: does the chain of runs meet itself.
                      "closed": not closure["gaps"],
                      # CLAUDE-SURVEY-STAGE1-02: and the arithmetic verdict,
                      # which is a different question. A ring can close on the
                      # page and still not close on its own figures - and on a
                      # dimension-only sheet there are no figures to close, so
                      # `computed` is False and that is an ordinary outcome.
                      "computed": traverse["computed"],
                      "misclosure": traverse["misclosure"]}}


def fit_to_frame(resolved: dict, margin: float = 0.06) -> dict:
    """Scale the reconstruction to fill its panel, uniformly. DETERMINISTIC.

    The node coordinates are fractions of the SOURCE IMAGE, and a survey
    photographed on a desk occupies a fraction of that image - on the Castille
    sheet the drawing area is roughly a third of the photograph, the rest being
    margin, title block and carpet. Drawn raw, the reconstruction is a postage
    stamp in the middle of an empty panel, which is unreadable for the one job
    it has: being compared against the source.

        UNIFORM SCALE, SO NOTHING IS RESHAPED.

    x and y are scaled by the SAME factor and then centred. Every angle, every
    proportion and every relative position is preserved exactly; only the
    overall size and position change. A non-uniform fit would make the drawing
    fill the panel by distorting the parcel, which is the one thing a survey
    reference must not do.

    This is a VIEW transform, not a change to the evidence. The stored graph
    keeps the coordinates the reader reported; this runs at render time, so a
    later improvement to fitting does not require rewriting stored records.
    """
    points = []
    for item in resolved.get("primitives") or []:
        if item["type"] == P_LINE:
            points.extend([item["a"], item["b"]])
        elif item["type"] == P_ARC:
            points.extend([item["a"], item["b"]])
            # The arc can bow beyond its endpoints, so its extreme is included
            # rather than assumed to lie on the chord.
            centre, radius = item["centre"], item["radius"]
            start, extent = item["start_deg"], item["extent_deg"]
            mid = math.radians(start + extent / 2.0)
            points.append((centre[0] + radius * math.cos(mid),
                           centre[1] + radius * math.sin(mid)))
        elif item["type"] == P_POLYGON:
            points.extend(item["points"])
    if len(points) < 2:
        return resolved

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    span_x, span_y = max_x - min_x, max_y - min_y
    if span_x <= 1e-9 and span_y <= 1e-9:
        return resolved

    usable = 1.0 - 2.0 * margin
    scale = min(usable / span_x if span_x > 1e-9 else 1e9,
                usable / span_y if span_y > 1e-9 else 1e9)
    offset_x = margin + (usable - span_x * scale) / 2.0
    offset_y = margin + (usable - span_y * scale) / 2.0

    def place(pair):
        return (round(offset_x + (pair[0] - min_x) * scale, 5),
                round(offset_y + (pair[1] - min_y) * scale, 5))

    fitted = []
    for item in resolved["primitives"]:
        moved = dict(item)
        if item["type"] in (P_LINE, P_ARC):
            moved["a"], moved["b"] = place(item["a"]), place(item["b"])
            if item["type"] == P_ARC:
                moved["centre"] = place(item["centre"])
                moved["radius"] = round(item["radius"] * scale, 5)
        elif item["type"] == P_POLYGON:
            moved["points"] = [place(p) for p in item["points"]]
        elif item["type"] == P_LABEL:
            moved["at"] = place(item["at"])
        fitted.append(moved)

    out = dict(resolved)
    out["primitives"] = fitted
    out["fit"] = {"scale": round(scale, 5), "source_extent": [min_x, min_y, max_x, max_y]}
    return out


def boundary_closure(graph: dict) -> dict:
    """Which boundary nodes are used once rather than twice.

    A closed ring touches every node exactly twice. This does not repair
    anything - it reports, so the drawing can be honestly open and the reader
    can be told where.
    """
    counts = {}
    for segment in graph.get("segments") or []:
        if segment["boundary"] not in ("street_line", "lot_line"):
            continue
        for key in ("from", "to"):
            counts[segment[key]] = counts.get(segment[key], 0) + 1
    return {"gaps": sorted(n for n, c in counts.items() if c == 1),
            "node_use": counts}


# -- SVG emitter (the review drawing) ----------------------------------------

_SVG_STYLE = {
    "street_line": ("#1f2933", 2.4),
    "lot_line": ("#1f2933", 1.6),
    "interior": ("#6b7785", 1.0),
    "easement": ("#6b7785", 1.0),
    "unknown": ("#6b7785", 1.2),
}


def emit_svg(resolved: dict, width: int = 560, height: int = 420,
             frame_size=None) -> str:
    """The plan as inline SVG, for the side-by-side review.

    NATIVE SVG GEOMETRY - `<path>` with `L` and `A` commands, never an
    `<image>`. An arc stays an arc in the markup, so what the Product Owner
    compares against the photograph is the reconstruction itself rather than a
    picture of it.

    The source's aspect ratio is letterboxed, so the drawing sits in the same
    proportions as the original beside it and the two can be read against each
    other.
    """
    from html import escape

    inset = 12.0
    box_w, box_h = width - 2 * inset, height - 2 * inset
    plot_w, plot_h = box_w, box_h
    if frame_size and len(frame_size) == 2 and frame_size[0] and frame_size[1]:
        aspect = float(frame_size[0]) / float(frame_size[1])
        if box_w / box_h > aspect:
            plot_w = box_h * aspect
        else:
            plot_h = box_w / aspect
    ox = inset + (box_w - plot_w) / 2.0
    oy = inset + (box_h - plot_h) / 2.0

    def sx(x):
        return ox + x * plot_w

    def sy(y):
        return oy + y * plot_h

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" '
        'width="100%%" role="img" aria-label="Reconstructed survey plan" '
        'class="sr-plan-svg">' % (width, height),
        '<rect x="0" y="0" width="%d" height="%d" fill="#ffffff" stroke="#cfd6dd"/>'
        % (width, height),
    ]

    for item in resolved["primitives"]:
        kind = item["type"]
        if kind == P_POLYGON:
            points = " ".join("%.2f,%.2f" % (sx(p[0]), sy(p[1])) for p in item["points"])
            dash = "" if item["certain"] else ' stroke-dasharray="4 3"'
            parts.append('<polygon points="%s" fill="#d8dee4" stroke="#1f2933" '
                         'stroke-width="1.2"%s/>' % (points, dash))
        elif kind == P_LINE:
            colour, weight = _SVG_STYLE.get(item["role"], _SVG_STYLE["unknown"])
            dash = "" if item["certain"] else ' stroke-dasharray="5 4"'
            parts.append('<path d="M %.2f %.2f L %.2f %.2f" fill="none" stroke="%s" '
                         'stroke-width="%.1f"%s/>'
                         % (sx(item["a"][0]), sy(item["a"][1]),
                            sx(item["b"][0]), sy(item["b"][1]), colour, weight, dash))
        elif kind == P_ARC:
            colour, weight = _SVG_STYLE.get(item["role"], _SVG_STYLE["unknown"])
            dash = "" if item["certain"] else ' stroke-dasharray="5 4"'
            # A TRUE SVG ARC. rx/ry are the scaled radius; the sweep flag is
            # the sign of the extent, so the curve bends the way the sheet says.
            rx = item["radius"] * plot_w
            ry = item["radius"] * plot_h
            sweep = 1 if item["extent_deg"] > 0 else 0
            large = 1 if abs(item["extent_deg"]) > 180 else 0
            parts.append('<path d="M %.2f %.2f A %.2f %.2f 0 %d %d %.2f %.2f" '
                         'fill="none" stroke="%s" stroke-width="%.1f"%s/>'
                         % (sx(item["a"][0]), sy(item["a"][1]), rx, ry, large, sweep,
                            sx(item["b"][0]), sy(item["b"][1]), colour, weight, dash))
        elif kind == P_LABEL:
            style = "#1f2933" if item["certain"] else "#6b7785"
            parts.append('<text x="%.2f" y="%.2f" font-size="8" fill="%s" '
                         'text-anchor="middle">%s</text>'
                         % (sx(item["at"][0]), sy(item["at"][1]) - 2,
                            style, escape(item["text"])))
        elif kind == P_NORTH:
            cx, cy, r = width - 34.0, 34.0, 13.0
            angle = math.radians(90.0 - item["degrees"])
            tip = (cx + r * math.cos(angle), cy - r * math.sin(angle))
            left = (cx + r * 0.4 * math.cos(angle + 2.5), cy - r * 0.4 * math.sin(angle + 2.5))
            right = (cx + r * 0.4 * math.cos(angle - 2.5), cy - r * 0.4 * math.sin(angle - 2.5))
            parts.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="none" '
                         'stroke="#1f2933" stroke-width="0.8"/>' % (cx, cy, r))
            parts.append('<path d="M %.2f %.2f L %.2f %.2f L %.2f %.2f L %.2f %.2f Z" '
                         'fill="#1f2933" stroke="#1f2933" stroke-width="0.6"/>'
                         % (tip[0], tip[1], left[0], left[1], cx, cy, right[0], right[1]))
            parts.append('<text x="%.1f" y="%.1f" font-size="7" font-weight="bold" '
                         'fill="#1f2933" text-anchor="middle">N</text>'
                         % (cx, cy + r + 8))

    # Footprint labels last, and BELOW the polygon when they will not fit
    # inside it - the same rule the PDF renderer applies, for the same reason:
    # on the Castille sheet a garage label is wider than the garage and ran
    # through the dwelling label beside it.
    for item in resolved["primitives"]:
        if item["type"] != P_POLYGON or not item.get("label"):
            continue
        xs = [sx(p[0]) for p in item["points"]]
        ys = [sy(p[1]) for p in item["points"]]
        label = item["label"][:34]
        # No font metrics here, so width is estimated at 0.5em per character -
        # deliberately generous, because pushing a label out unnecessarily is a
        # smaller fault than overlapping one.
        estimated = len(label) * 7.5 * 0.5
        cx = sum(xs) / len(xs)
        cy = (sum(ys) / len(ys)) if estimated <= (max(xs) - min(xs)) - 4 else max(ys) + 9
        parts.append('<text x="%.2f" y="%.2f" font-size="7.5" fill="#1f2933" '
                     'text-anchor="middle">%s</text>' % (cx, cy, escape(label)))

    parts.append("</svg>")
    return "".join(parts)
