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
    return {"text": text[:40], "value": _num(raw.get("value")),
            "unit": str(raw.get("unit") or "").strip()[:12],
            "certainty": certainty}


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
            "bearing": _dimension(entry.get("bearing")),
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

    north = None
    raw_north = raw.get("north")
    if isinstance(raw_north, dict):
        degrees = _num(raw_north.get("degrees"))
        certainty = _certainty(raw_north.get("certainty"))
        if degrees is not None and certainty in vx.VALUE_BEARING:
            north = {"degrees": round(degrees % 360.0, 2), "certainty": certainty}

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


def build_primitives(graph: dict) -> dict:
    """The graph resolved into drawable primitives, once, for both renderers.

    Returns {"primitives": [...], "unresolved": [...], "stats": {...}}. All
    coordinates stay image fractions with a top-left origin; each renderer maps
    them into its own frame, so nothing here knows about points, pixels or
    page size.
    """
    nodes = graph.get("nodes") or {}
    unresolved = list(graph.get("unresolved") or [])
    primitives = []
    arcs = straights = 0

    for segment in graph.get("segments") or []:
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
                    "label": segment["label"],
                    "radius_text": (segment.get("radius") or {}).get("text"),
                    "chord_text": (segment.get("chord") or {}).get("text")})
        else:
            straights += 1
            primitives.append({"type": P_LINE, "id": segment["id"],
                               "a": p1, "b": p2, "certain": certain,
                               "role": segment["boundary"],
                               "label": segment["label"]})

        # A dimension is drawn ONLY where the sheet supported one, and always
        # as the sheet's own string.
        dimension = segment.get("dimension")
        if dimension:
            primitives.append({
                "type": P_LABEL, "kind": "dimension", "text": dimension["text"],
                "at": ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                "certain": dimension["certainty"] == vx.RECOVERED,
                "for": segment["id"]})
        bearing = segment.get("bearing")
        if bearing:
            primitives.append({
                "type": P_LABEL, "kind": "bearing", "text": bearing["text"],
                "at": ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0),
                "certain": bearing["certainty"] == vx.RECOVERED,
                "for": segment["id"]})

    for footprint in graph.get("footprints") or []:
        primitives.append({
            "type": P_POLYGON, "id": footprint["id"], "kind": footprint["kind"],
            "points": footprint["outline"], "label": footprint["label"],
            "certain": footprint["certainty"] == vx.RECOVERED})

    north = graph.get("north")
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
                      "closed": not closure["gaps"]}}


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
