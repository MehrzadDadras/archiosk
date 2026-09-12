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


def _point_in_parts(point, parts) -> bool:
    """Inside the union: inside at least one part, honouring that part's holes."""
    return any(_point_in_polygon(point, exterior, holes)
               for exterior, holes in parts)


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


def _point_in_ring(point, ring) -> bool:
    """Ray casting. Exact for a simple closed ring; boundary handled separately."""
    x, y = point[0], point[1]
    inside = False
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


def _point_in_polygon(point, exterior, holes) -> bool:
    """Even-odd with holes, and exact: inside the exterior and inside no hole.

    This is the whole of what admitting holes required. It also answers the case
    version 1 could not distinguish at all - a parcel lying inside a hole is
    genuinely OUTSIDE the polygon, not merely undecidable.
    """
    if not _point_in_ring(point, exterior):
        return False
    return not any(_point_in_ring(point, hole) for hole in holes)


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


def _rings_cross(a, b) -> bool:
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            if _segments_cross(a[i], a[i + 1], b[j], b[j + 1]):
                return True
    return False


def _any_crossing(subject_rings, layer_rings) -> bool:
    """Does any ring of one polygon cross any ring of the other?

    Hole rings are included on BOTH sides. A parcel whose edge clips the edge of
    a hole punched out of a zone genuinely straddles that zone's boundary, even
    though it never touches the exterior ring.
    """
    for a in subject_rings:
        for b in layer_rings:
            if _rings_cross(a, b):
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
    for vertex in subject_vertices:
        if _min_distance_to_polygon(vertex, layer_rings) <= tolerance:
            return _token(RELATION_AMBIGUOUS, REASON_NEAR_BOUNDARY,
                          provenance=provenance)

    crossing = _any_crossing(subject_rings, layer_rings)
    vertices_inside = [_point_in_parts(v, layer_parts) for v in subject_vertices]

    if crossing:
        return _token(RELATION_INTERSECTS, None, provenance=provenance)
    if all(vertices_inside):
        # No crossing and every vertex inside is not yet INSIDE once holes exist:
        # the subject may enclose a hole entirely, so part of what it covers is
        # not in the layer at all.
        layer_hole_vertices = [v for _exterior, holes in layer_parts
                               for hole in holes for v in hole[:-1]]
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
