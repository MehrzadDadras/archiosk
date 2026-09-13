"""CLAUDE-GO-PDZ-SPATIAL-01 - GO consumes the map. GO does not invent it.

    INSIDE | OUTSIDE | INTERSECTS | AMBIGUOUS   from authoritative geometry only

GO-PDZ's VR-09 refuses an assertive spatial predicate that is not backed by
deterministic geometry, which means something has to actually compute one. This
is that something, and its most important property is not what it can decide but
what it REFUSES to decide.

COMPETENCE IS DECLARED, NOT ASSUMED. The engine below is exact for the case it
covers - simple closed rings WITH HOLES, one coordinate reference system, single
part - and returns AMBIGUOUS the moment a question leaves that envelope. That is
not a placeholder for a better engine. It is the whole design: a planning
determination that quietly guesses is worse than one that says it cannot tell,
because the first is indistinguishable from an answer.

HOLES WERE ADMITTED BY MEASUREMENT, NOT BY AMBITION (CLAUDE-TORONTO-LIVE-01).
Version 1 refused any polygon with a hole, and a test asserted that refusal. The
first real subject retired it: the City of Toronto's authoritative zoning polygon
governing 35 Taber Road is ONE exterior ring of 389 vertices with FIVE holes, and
the nearest hole sits about nine metres from the subject parcel. Refusing that is
not caution - it is refusing every question the engine exists to answer, because
a municipal zone polygon with parks, ravines and differently-zoned islands punched
out of it is the ordinary case rather than the exotic one.

Admitting holes did NOT relax the discipline, because the even-odd rule is exact:
a point is in the polygon when it lies inside the exterior ring and inside no
hole. That is arithmetic with the same primitives already here, not an
approximation. It also buys the case that actually matters - **a parcel sitting
inside a hole is OUTSIDE the zone**, and version 1's blanket refusal could not
distinguish that from a parcel comfortably within it.

MULTIPART WAS ADMITTED THE SAME WAY, ONE STEP LATER. The first live run refused
three of ten authority layers around the subject - including the height overlay,
which is as material as a finding gets - and reported them to the reader as
"could not be determined". That was not true. The City's polygons were fine; THIS
ENGINE declined them. Mislabelling an engine limit as a data ambiguity is worse
than either problem alone, because it sends a reader to look for evidence that
already exists.

Containment against a multipart polygon is not a question about intent after all:
a subject is inside the union when it lies inside some part, and outside it when
it lies outside every part. Same arithmetic, applied per part. What remains
refused is what is genuinely undecidable - invalid rings, CRS mismatch, boundary
proximity, and a subject whose vertices disagree with its own edges.

REPROJECTION IS STILL REFUSED HERE. A CRS mismatch between two geometries
handed to `relate()` is AMBIGUOUS, exactly as before. What changed is only that a
caller may now RECORD that the authority's own service delivered geometry in a
requested CRS, so the provenance says who moved it. An untested transform
written into this module remains the silent error it always was.

WHY STILL NO GEOS. Shapely PASSES `tools/dependency_fit.py` and would add
validity repair, buffering and true boolean overlay. The measured case above
needed NONE of those - it needed holes, which cost thirty lines and no
dependency. Shapely bundles a compiled C library into `requirements.txt`, which
ships to the production host, and the abstention discipline is required whichever
engine runs. `ENGINE` remains the swap point: adopting it later changes this
module and no caller.

EVERY TOKEN CARRIES ITS PROVENANCE. A bare "INSIDE" is unusable in a governed
result: the record has to say which parcel geometry, which authority layer, what
CRS, what operation, and which version of each. `relate()` returns that envelope
rather than a string, and `go_pdz_validator` VR-09 checks the basis rather than
trusting the word.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

ENGINE = "archiosk-exact-ring@3"   # @2 holes, @3 multipart - see docstring

RELATION_INSIDE = "INSIDE"
RELATION_OUTSIDE = "OUTSIDE"
RELATION_INTERSECTS = "INTERSECTS"
RELATION_AMBIGUOUS = "AMBIGUOUS"
RELATION_NOT_APPLICABLE = "NOT_APPLICABLE"

BASIS_DETERMINISTIC = "DETERMINISTIC_GIS"
BASIS_NONE = "NONE"

#: The only coordinate reference systems this engine will compare geometry in.
#: A mismatch is NOT reprojected - reprojection without a tested transform is
#: exactly the silent error this module exists to refuse.
SUPPORTED_CRS = ("EPSG:4326", "EPSG:3857", "EPSG:26917")

#: How close to a boundary a vertex may sit before the answer stops being safe,
#: as a fraction of the subject's own bounding-box diagonal. Municipal parcel and
#: overlay polygons are digitised from different sources at different epochs, so
#: two edges that "should" coincide routinely differ by a small amount; calling
#: that INSIDE or OUTSIDE asserts a precision neither layer has.
BOUNDARY_TOLERANCE_FRACTION = 1e-9

#: Why a question was refused. Returned verbatim so a reader knows whether to
#: fix the data, fix the CRS, or accept that the answer is genuinely unknowable.
REASON_MISSING = "geometry_missing"
REASON_INVALID = "geometry_invalid"
REASON_CRS_MISMATCH = "crs_mismatch"
REASON_CRS_UNSUPPORTED = "crs_unsupported"
REASON_HOLES = "geometry_has_holes_beyond_engine_competence"   # retained: no longer emitted by this engine, see docstring
REASON_MULTIPART = "multipart_geometry_beyond_engine_competence"   # retained: no longer emitted, see docstring
REASON_NEAR_BOUNDARY = "vertex_within_boundary_tolerance"
REASON_CONFLICTING = "conflicting_authoritative_geometry"
REASON_MULTIPLE_PARCELS = "address_resolves_to_multiple_parcels"
REASON_NOT_VECTOR = "source_is_not_vector_geometry"


def geometry_hash(geometry) -> Optional[str]:
    """A stable identifier for a geometry, so a token can name what it measured."""
    if geometry is None:
        return None
    try:
        canonical = json.dumps(geometry, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError):
        return None
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def token_matches(token, *, subject, layer, subject_source=None,
                  layer_source=None, layer_version=None,
                  subject_parcel_count=1, conflicting_layers=False,
                  upstream_transformation=None) -> bool:
    """Is `token` ALREADY the answer `relate()` would produce for these inputs?

    CLAUDE-SPATIAL-DEDUPE-02A. Identity, not resemblance. A token may be reused
    only when every input that can change the answer is provably the same one,
    so this compares the two GEOMETRY HASHES the token already carries plus the
    CRS pair, the source labels, the version, the operation and the engine. No
    reuse is ever decided by layer name, proximity or call order.

    The two guard clauses at the end matter as much as the comparisons: a subject
    that resolved to several parcels and a conflicting-layer condition both make
    `relate` return AMBIGUOUS for reasons that have nothing to do with geometry,
    so a token computed without them is not the answer to this question. Those
    cases fall through and are recomputed.

    This function performs NO geometry. It reads identifiers and compares them.
    """
    if not isinstance(token, dict) or token.get("engine") != ENGINE:
        return False
    if subject_parcel_count is not None and subject_parcel_count > 1:
        return False
    if conflicting_layers:
        return False
    provenance = token.get("provenance")
    if not isinstance(provenance, dict):
        return False
    expected = {
        "subject_geometry_source": subject_source,
        "subject_geometry_id": geometry_hash((subject or {}).get("geometry")),
        "layer_geometry_source": layer_source,
        "layer_geometry_id": geometry_hash((layer or {}).get("geometry")),
        "layer_version": layer_version,
        "subject_crs": (subject or {}).get("crs"),
        "layer_crs": (layer or {}).get("crs"),
        "transformation": upstream_transformation,
        "operation": "ring_containment_and_crossing",
    }
    for key, value in expected.items():
        if provenance.get(key) != value:
            return False
    # A hash of None is None: two missing geometries are not "the same geometry",
    # and reusing a token across them would be reuse by coincidence.
    return (expected["subject_geometry_id"] is not None
            and expected["layer_geometry_id"] is not None)


def _parts(geometry):
    """Every (exterior, holes) pair of a GeoJSON Polygon or MultiPolygon, or None.

    Version 1 read only the FIRST part of a MultiPolygon and reported the count,
    which was safe only because the caller then refused anything with more than
    one. Now that multipart is computed rather than refused, silently dropping
    parts would be the very error the refusal used to prevent.
    """
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return None
    if kind == "Polygon":
        return [(coordinates[0], list(coordinates[1:]))]
    if kind == "MultiPolygon":
        parts = []
        for part in coordinates:
            if not part:
                return None
            parts.append((part[0], list(part[1:])))
        return parts
    return None


def _point_in_parts(point, parts, prepared=None) -> bool:
    """Inside the union: inside at least one part, honouring that part's holes."""
    if prepared is None:
        return any(_point_in_polygon(point, exterior, holes)
                   for exterior, holes in parts)
    for index, (exterior, holes) in enumerate(parts):
        if _point_in_polygon(point, exterior, holes, prepared[index]):
            return True
    return False


def prepare_ring(ring, subject_box, tolerance):
    """`(box, band, near)` for one ring, in a SINGLE pass over its segments.

    `band`  segments a ray at any y the subject occupies could cross - the only
            ones that can change containment parity for any subject vertex.
    `near`  segments whose own bounding box comes within `tolerance` of the
            subject's - the only ones that can be within tolerance of it, and the
            only ones that can cross it.

    Both are exclusions by proof. A segment in neither list cannot affect any of
    the three answers, so not computing it changes nothing except the time.

    ONE PASS MATTERS AS MUCH AS THE FILTERS. The first version of this filtered
    proximity per subject vertex, which re-walked 157,647 segments 26 times over
    and left 3.7 s on the table for a geometry whose answer was already decided.
    """
    low, high = subject_box[1], subject_box[3]
    padded = (subject_box[0] - tolerance, subject_box[1] - tolerance,
              subject_box[2] + tolerance, subject_box[3] + tolerance)
    band, near = [], []
    for index in range(len(ring) - 1):
        first, second = ring[index], ring[index + 1]
        x1, y1 = first[0], first[1]
        x2, y2 = second[0], second[1]
        if y1 < y2:
            spans = not (y2 <= low or y1 > high)
        else:
            spans = not (y1 <= low or y2 > high)
        if spans:
            band.append((x1, y1, x2, y2))
        if not (max(x1, x2) < padded[0] or min(x1, x2) > padded[2]
                or max(y1, y2) < padded[1] or min(y1, y2) > padded[3]):
            near.append((first, second))
    return _bbox(ring), band, near


def prepare_parts(parts, subject_box, tolerance):
    """`prepare_ring` for every ring, `[exterior] + holes` order, per part."""
    return [[prepare_ring(ring, subject_box, tolerance)
             for ring in [exterior] + list(holes)]
            for exterior, holes in parts]


def _all_rings(parts):
    rings = []
    for exterior, holes in parts:
        rings.append(exterior)
        rings.extend(holes)
    return rings


def _ring_is_valid(ring) -> bool:
    """A ring this engine will compute on: closed, planar, at least a triangle."""
    if not isinstance(ring, (list, tuple)) or len(ring) < 4:
        return False
    for point in ring:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            return False
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in point[:2]):
            return False
    if tuple(ring[0][:2]) != tuple(ring[-1][:2]):
        return False
    return True


def _bbox(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def ring_band(ring, low, high):
    """The segments of `ring` that could be crossed by a ray at any y in [low, high].

    CLAUDE-SPATIAL-PREFILTER-02B. The ray test below fires only when
    `min(y1, y2) <= y < max(y1, y2)`. A segment for which no y in the band
    satisfies that cannot change the answer for ANY point in the band, so it is
    excluded - not approximated, excluded, because its contribution is provably
    zero.

    The band is the SUBJECT's own y-range, so one pass over the ring serves every
    subject vertex. Measured on 573 Shuter Street: the Natural Heritage ring
    holds 157,647 segments and 30 of them can matter.

    Returns a flat list of `(x1, y1, x2, y2)`, which is also why this is worth
    doing twice over: the tuples are unpacked once here rather than indexed four
    times per point inside the hot loop.
    """
    band = []
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[index + 1][0], ring[index + 1][1]
        if y1 < y2:
            if y2 <= low or y1 > high:
                continue
        else:
            if y1 <= low or y2 > high:
                continue
        band.append((x1, y1, x2, y2))
    return band


def _point_in_ring(point, ring, box=None, band=None) -> bool:
    """Ray casting. Exact for a simple closed ring; boundary handled separately.

    `box` and `band` are OPTIONAL PREFILTERS and change no arithmetic. With
    neither, this is the original function line for line.

    THE BOX REJECTION IS NOT THE WHOLE BOX, and that is the part worth reading
    twice. A point ABOVE or BELOW the ring cannot satisfy `(y1 > y) != (y2 > y)`
    for any segment, and a point to the RIGHT of the ring cannot satisfy
    `x < crossing`, since every crossing lies between two of the ring's own x
    values. But a point to the LEFT is exactly the case ray casting exists for -
    its ray enters the ring - so `x < xmin` must NOT reject. Using the full
    bounding box here would report OUTSIDE for half the points that are inside.
    """
    x, y = point[0], point[1]
    if box is not None:
        minx, miny, maxx, maxy = box
        if y < miny or y > maxy or x > maxx:
            return False
    inside = False
    if band is not None:
        for x1, y1, x2, y2 in band:
            if (y1 > y) != (y2 > y):
                if y2 != y1:
                    crossing = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    if x < crossing:
                        inside = not inside
        return inside
    count = len(ring) - 1
    for index in range(count):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[index + 1][0], ring[index + 1][1]
        if (y1 > y) != (y2 > y):
            if y2 != y1:
                crossing = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                if x < crossing:
                    inside = not inside
    return inside


def _point_in_polygon(point, exterior, holes, prepared=None) -> bool:
    """Even-odd with holes, and exact: inside the exterior and inside no hole.

    This is the whole of what admitting holes required. It also answers the case
    version 1 could not distinguish at all - a parcel lying inside a hole is
    genuinely OUTSIDE the polygon, not merely undecidable.

    `prepared` carries one `(box, band)` per ring in `[exterior] + holes` order.
    """
    if prepared is None:
        if not _point_in_ring(point, exterior):
            return False
        return not any(_point_in_ring(point, hole) for hole in holes)
    box, band, _near = prepared[0]
    if not _point_in_ring(point, exterior, box, band):
        return False
    for index, hole in enumerate(holes):
        box, band, _near = prepared[index + 1]
        if _point_in_ring(point, hole, box, band):
            return False
    return True


def _distance_point_to_segment(point, a, b) -> float:
    px, py = point[0], point[1]
    ax, ay, bx, by = a[0], a[1], b[0], b[1]
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5


def _min_distance_to_ring(point, ring) -> float:
    return min(_distance_point_to_segment(point, ring[i], ring[i + 1])
               for i in range(len(ring) - 1))


def _min_distance_to_polygon(point, rings) -> float:
    """Nearest approach to ANY ring. A hole edge is a boundary too."""
    return min(_min_distance_to_ring(point, ring) for ring in rings)


def _within_tolerance_prepared(point, prepared, tolerance) -> bool:
    """Is `point` within `tolerance` of any prepared ring's edges?

    Walks only the `near` set, which was built once for the whole subject.
    """
    for _box, _band, near in prepared:
        for first, second in near:
            if _distance_point_to_segment(point, first, second) <= tolerance:
                return True
    return False


def _crossing_prepared(subject_rings, subject_boxes, prepared) -> bool:
    """Does any subject ring cross any prepared layer ring?

    Only the `near` segments can cross the subject at all, so the quadratic pair
    loop runs over those instead of over every segment in the layer.
    """
    for index, ring in enumerate(subject_rings):
        box = subject_boxes[index]
        for _layer_box, _band, near in prepared:
            for first, second in near:
                if (max(first[0], second[0]) < box[0]
                        or min(first[0], second[0]) > box[2]
                        or max(first[1], second[1]) < box[1]
                        or min(first[1], second[1]) > box[3]):
                    continue
                for position in range(len(ring) - 1):
                    if _segments_cross(ring[position], ring[position + 1],
                                       first, second):
                        return True
    return False


def _within_tolerance(point, rings, tolerance, boxes=None) -> bool:
    """Is `point` within `tolerance` of any ring edge?

    The caller only ever needed this BOOLEAN - `_min_distance_to_polygon` was
    computing an exact minimum across 280,466 segments so that one comparison
    could be made against it. Asking the question directly lets a segment be
    skipped the moment its bounding box is further away than the tolerance,
    which is exact: the distance from a point to a segment is never less than
    the distance from that point to the segment's own bounding box.

    `_min_distance_to_polygon` is deliberately left in place and unchanged - it
    is a different question, and something may still want the number.
    """
    x, y = point[0], point[1]
    for index, ring in enumerate(rings):
        if boxes is not None:
            minx, miny, maxx, maxy = boxes[index]
            if (x < minx - tolerance or x > maxx + tolerance
                    or y < miny - tolerance or y > maxy + tolerance):
                continue
        for position in range(len(ring) - 1):
            a, b = ring[position], ring[position + 1]
            if (x < min(a[0], b[0]) - tolerance
                    or x > max(a[0], b[0]) + tolerance
                    or y < min(a[1], b[1]) - tolerance
                    or y > max(a[1], b[1]) + tolerance):
                continue
            if _distance_point_to_segment(point, a, b) <= tolerance:
                return True
    return False


def _segments_cross(p1, p2, p3, p4) -> bool:
    def orient(a, b, c):
        value = ((b[1] - a[1]) * (c[0] - b[0])) - ((b[0] - a[0]) * (c[1] - b[1]))
        if value > 0:
            return 1
        if value < 0:
            return -1
        return 0

    def on_segment(a, b, c):
        return (min(a[0], c[0]) <= b[0] <= max(a[0], c[0])
                and min(a[1], c[1]) <= b[1] <= max(a[1], c[1]))

    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    if o1 != o2 and o3 != o4:
        return True
    if o1 == 0 and on_segment(p1, p3, p2):
        return True
    if o2 == 0 and on_segment(p1, p4, p2):
        return True
    if o3 == 0 and on_segment(p3, p1, p4):
        return True
    if o4 == 0 and on_segment(p3, p2, p4):
        return True
    return False


def _rings_cross(a, b, box_a=None, box_b=None) -> bool:
    """Does any segment of `a` cross any segment of `b`?

    The optional boxes reject work that cannot produce a crossing: two segments
    whose bounding boxes do not overlap cannot intersect, which is exact rather
    than heuristic. `box_a` is the whole of ring `a`, so a segment of `b` outside
    it cannot cross ANY segment of `a`.
    """
    if box_a is not None and box_b is not None and _boxes_apart(box_a, box_b, 0.0):
        return False
    for j in range(len(b) - 1):
        x1, y1 = b[j][0], b[j][1]
        x2, y2 = b[j + 1][0], b[j + 1][1]
        if box_a is not None:
            if (max(x1, x2) < box_a[0] or min(x1, x2) > box_a[2]
                    or max(y1, y2) < box_a[1] or min(y1, y2) > box_a[3]):
                continue
        for i in range(len(a) - 1):
            if _segments_cross(a[i], a[i + 1], b[j], b[j + 1]):
                return True
    return False


def _boxes_apart(one, two, pad) -> bool:
    """Do these boxes stay further apart than `pad` in some axis?

    True means no point of one can lie within `pad` of any point of the other,
    which is what makes rejection safe rather than approximate.
    """
    return (one[2] + pad < two[0] or two[2] + pad < one[0]
            or one[3] + pad < two[1] or two[3] + pad < one[1])


def _any_crossing(subject_rings, layer_rings,
                  subject_boxes=None, layer_boxes=None) -> bool:
    """Does any ring of one polygon cross any ring of the other?

    Hole rings are included on BOTH sides. A parcel whose edge clips the edge of
    a hole punched out of a zone genuinely straddles that zone's boundary, even
    though it never touches the exterior ring.
    """
    for index_a, a in enumerate(subject_rings):
        box_a = subject_boxes[index_a] if subject_boxes else None
        for index_b, b in enumerate(layer_rings):
            box_b = layer_boxes[index_b] if layer_boxes else None
            if _rings_cross(a, b, box_a, box_b):
                return True
    return False


def _token(relation, reason=None, **extra):
    token = {
        "spatial_relation": relation,
        "spatial_basis": (BASIS_DETERMINISTIC
                          if relation in (RELATION_INSIDE, RELATION_OUTSIDE,
                                          RELATION_INTERSECTS)
                          else BASIS_NONE),
        "engine": ENGINE,
        "reason": reason,
    }
    token.update(extra)
    return token


def relate(subject, layer, *, subject_source=None, layer_source=None,
           layer_version=None, subject_parcel_count=1,
           conflicting_layers=False, upstream_transformation=None) -> dict:
    """Where does `subject` sit relative to `layer`? Never raises.

    `subject` and `layer` are `{"crs": "EPSG:...", "geometry": <GeoJSON>}`.
    Returns a token carrying the relation, its basis, the provenance of both
    geometries, and - when the answer is AMBIGUOUS - the reason it was refused.

    THE REFUSALS ARE THE FEATURE. Section 10's edge conditions each have a named
    outcome here rather than a best guess: missing or invalid geometry, a CRS
    mismatch or an unsupported CRS, holes or multipart geometry beyond this
    engine's competence, a vertex sitting within boundary tolerance, conflicting
    official layers, and an address that resolved to more than one parcel.
    """
    subject = subject or {}
    layer = layer or {}
    provenance = {
        "subject_geometry_source": subject_source,
        "subject_geometry_id": geometry_hash(subject.get("geometry")),
        "layer_geometry_source": layer_source,
        "layer_geometry_id": geometry_hash(layer.get("geometry")),
        "layer_version": layer_version,
        "subject_crs": subject.get("crs"),
        "layer_crs": layer.get("crs"),
        # THIS ENGINE NEVER REPROJECTS. `transformation` records a reprojection
        # performed UPSTREAM, by the publishing authority, when geometry was
        # requested in a CRS other than the one the layer is authored in - which
        # Mississauga's data makes unavoidable: its address and parcel layers are
        # published in EPSG:3857 and its zoning and Official Plan schedules in
        # EPSG:26917, so SOMETHING has to move before they can be compared. It
        # is the publisher's own service that moves it, on request, and saying
        # so is the difference between a transparent comparison and a silent one.
        # None still means what it always meant: nothing was transformed.
        "transformation": upstream_transformation,
        "transformed_by": ("publishing authority (outSR request)"
                           if upstream_transformation else None),
        "operation": "ring_containment_and_crossing",
    }

    # An address that resolved to several parcels has no single subject, so there
    # is nothing to be inside of.
    if subject_parcel_count is not None and subject_parcel_count > 1:
        return _token(RELATION_AMBIGUOUS, REASON_MULTIPLE_PARCELS,
                      provenance=provenance,
                      parcel_count=subject_parcel_count)
    if conflicting_layers:
        return _token(RELATION_AMBIGUOUS, REASON_CONFLICTING,
                      provenance=provenance)

    if subject.get("geometry") is None or layer.get("geometry") is None:
        return _token(RELATION_AMBIGUOUS, REASON_MISSING, provenance=provenance)

    subject_crs, layer_crs = subject.get("crs"), layer.get("crs")
    if subject_crs not in SUPPORTED_CRS or layer_crs not in SUPPORTED_CRS:
        return _token(RELATION_AMBIGUOUS, REASON_CRS_UNSUPPORTED,
                      provenance=provenance)
    if subject_crs != layer_crs:
        # NOT reprojected. A transform applied without a tested implementation
        # is precisely the silent error this module exists to refuse.
        return _token(RELATION_AMBIGUOUS, REASON_CRS_MISMATCH,
                      provenance=provenance)

    subject_parts = _parts(subject["geometry"])
    layer_parts = _parts(layer["geometry"])
    if subject_parts is None or layer_parts is None:
        return _token(RELATION_AMBIGUOUS, REASON_NOT_VECTOR,
                      provenance=provenance)

    subject_rings = _all_rings(subject_parts)
    layer_rings = _all_rings(layer_parts)

    # EVERY ring must be computable - exteriors and holes, in every part. A
    # malformed hole that silently vanished from the even-odd test would turn an
    # OUTSIDE into an INSIDE, and a dropped part would do the same; both are the
    # exact class of quiet error this module exists to refuse.
    if not all(_ring_is_valid(ring) for ring in subject_rings + layer_rings):
        return _token(RELATION_AMBIGUOUS, REASON_INVALID, provenance=provenance)

    provenance["subject_part_count"] = len(subject_parts)
    provenance["layer_part_count"] = len(layer_parts)
    provenance["subject_hole_count"] = sum(len(h) for _e, h in subject_parts)
    provenance["layer_hole_count"] = sum(len(h) for _e, h in layer_parts)

    # Boundary proximity, measured against the subject's own scale so the
    # tolerance means the same thing in degrees and in metres. Every ring counts:
    # a hole edge is a boundary of the zone just as much as an outer edge is.
    subject_exterior = subject_parts[0][0]
    minx, miny, maxx, maxy = _bbox(subject_exterior)
    diagonal = (((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5) or 1.0
    tolerance = diagonal * BOUNDARY_TOLERANCE_FRACTION
    subject_vertices = [v for exterior, _holes in subject_parts
                        for v in exterior[:-1]]

    # CLAUDE-SPATIAL-PREFILTER-02B. ONE pass over each side's rings, producing a
    # bounding box per ring and - for the layer - the segments that could be
    # crossed by a ray at any y the subject occupies. Every filter below is a
    # proof that a segment cannot affect the answer, never an approximation of
    # its effect: measured on 573 Shuter Street, the crossing sweep needed 0 of
    # 280,466 layer segments, the proximity sweep 0, and containment 30.
    subject_boxes = [_bbox(ring) for ring in subject_rings]
    subject_box = (min(box[0] for box in subject_boxes),
                   min(box[1] for box in subject_boxes),
                   max(box[2] for box in subject_boxes),
                   max(box[3] for box in subject_boxes))
    layer_prepared = prepare_parts(layer_parts, subject_box, tolerance)
    flat_prepared = [ring for part in layer_prepared for ring in part]

    for vertex in subject_vertices:
        if _within_tolerance_prepared(vertex, flat_prepared, tolerance):
            return _token(RELATION_AMBIGUOUS, REASON_NEAR_BOUNDARY,
                          provenance=provenance)

    crossing = _crossing_prepared(subject_rings, subject_boxes, flat_prepared)
    vertices_inside = [_point_in_parts(v, layer_parts, layer_prepared)
                       for v in subject_vertices]

    if crossing:
        return _token(RELATION_INTERSECTS, None, provenance=provenance)
    if all(vertices_inside):
        # No crossing and every vertex inside is not yet INSIDE once holes exist:
        # the subject may enclose a hole entirely, so part of what it covers is
        # not in the layer at all.
        layer_hole_vertices = [v for _exterior, holes in layer_parts
                               for hole in holes for v in hole[:-1]]
        # The SUBJECT is the small side here, so it gets no band: a band is only
        # worth building when the ring being tested is large.
        if any(_point_in_parts(v, subject_parts) for v in layer_hole_vertices):
            return _token(RELATION_INTERSECTS, None, provenance=provenance)
        return _token(RELATION_INSIDE, None, provenance=provenance)
    if not any(vertices_inside):
        # No crossing and no vertex inside still leaves two real cases: the layer
        # sitting wholly within the subject, which is an intersection rather than
        # a miss - and the subject sitting wholly within a HOLE, which is a
        # genuine OUTSIDE and the case version 1 could not see at all.
        layer_exterior_vertices = [v for exterior, _holes in layer_parts
                                   for v in exterior[:-1]]
        if any(_point_in_parts(v, subject_parts) for v in layer_exterior_vertices):
            return _token(RELATION_INTERSECTS, None, provenance=provenance)
        return _token(RELATION_OUTSIDE, None, provenance=provenance)
    # Some in, some out, yet no edge crossing detected - the geometry disagrees
    # with itself, so the honest answer is that this engine cannot tell.
    return _token(RELATION_AMBIGUOUS, REASON_INVALID, provenance=provenance)
