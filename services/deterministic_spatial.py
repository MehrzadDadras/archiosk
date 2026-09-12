"""CLAUDE-GO-PDZ-SPATIAL-01 - GO consumes the map. GO does not invent it.

    INSIDE | OUTSIDE | INTERSECTS | AMBIGUOUS   from authoritative geometry only

GO-PDZ's VR-09 refuses an assertive spatial predicate that is not backed by
deterministic geometry, which means something has to actually compute one. This
is that something, and its most important property is not what it can decide but
what it REFUSES to decide.

COMPETENCE IS DECLARED, NOT ASSUMED. The engine below is exact for the case it
covers - simple closed rings, one coordinate reference system, no holes, no
multipart geometry - and returns AMBIGUOUS the moment a question leaves that
envelope. That is not a placeholder for a better engine. It is the whole design:
a planning determination that quietly guesses at a polygon with holes is worse
than one that says it cannot tell, because the first is indistinguishable from
an answer.

WHY NO GEOS. Shapely PASSES `tools/dependency_fit.py` and would widen competence
to holes, multipart geometry and validity repair. It is deliberately not adopted
here: it bundles a compiled C library into `requirements.txt`, which ships to the
production host, and the abstention discipline above is required whichever engine
runs. `ENGINE` is the swap point - adopting Shapely later changes this module and
no caller.

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

ENGINE = "archiosk-exact-ring@1"

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
REASON_HOLES = "geometry_has_holes_beyond_engine_competence"
REASON_MULTIPART = "multipart_geometry_beyond_engine_competence"
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


def _rings(geometry):
    """(exterior, holes, parts) for a GeoJSON Polygon or MultiPolygon, or None."""
    if not isinstance(geometry, dict):
        return None
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates")
    if not coordinates:
        return None
    if kind == "Polygon":
        return coordinates[0], list(coordinates[1:]), 1
    if kind == "MultiPolygon":
        first = coordinates[0]
        return first[0], list(first[1:]), len(coordinates)
    return None


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
           conflicting_layers=False) -> dict:
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
        "transformation": None,   # none performed, ever - see REASON_CRS_MISMATCH
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

    subject_parts = _rings(subject["geometry"])
    layer_parts = _rings(layer["geometry"])
    if subject_parts is None or layer_parts is None:
        return _token(RELATION_AMBIGUOUS, REASON_NOT_VECTOR,
                      provenance=provenance)

    subject_ring, subject_holes, subject_count = subject_parts
    layer_ring, layer_holes, layer_count = layer_parts

    if not _ring_is_valid(subject_ring) or not _ring_is_valid(layer_ring):
        return _token(RELATION_AMBIGUOUS, REASON_INVALID, provenance=provenance)
    if subject_count > 1 or layer_count > 1:
        return _token(RELATION_AMBIGUOUS, REASON_MULTIPART, provenance=provenance)
    if subject_holes or layer_holes:
        return _token(RELATION_AMBIGUOUS, REASON_HOLES, provenance=provenance)

    # Boundary proximity, measured against the subject's own scale so the
    # tolerance means the same thing in degrees and in metres.
    minx, miny, maxx, maxy = _bbox(subject_ring)
    diagonal = (((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5) or 1.0
    tolerance = diagonal * BOUNDARY_TOLERANCE_FRACTION
    for vertex in subject_ring[:-1]:
        if _min_distance_to_ring(vertex, layer_ring) <= tolerance:
            return _token(RELATION_AMBIGUOUS, REASON_NEAR_BOUNDARY,
                          provenance=provenance)

    crossing = _rings_cross(subject_ring, layer_ring)
    vertices_inside = [_point_in_ring(v, layer_ring) for v in subject_ring[:-1]]

    if crossing:
        return _token(RELATION_INTERSECTS, None, provenance=provenance)
    if all(vertices_inside):
        return _token(RELATION_INSIDE, None, provenance=provenance)
    if not any(vertices_inside):
        # No crossing and no vertex inside still leaves one real case: the layer
        # sitting wholly within the subject. That is an intersection, not a miss.
        if any(_point_in_ring(v, subject_ring) for v in layer_ring[:-1]):
            return _token(RELATION_INTERSECTS, None, provenance=provenance)
        return _token(RELATION_OUTSIDE, None, provenance=provenance)
    # Some in, some out, yet no edge crossing detected - the geometry disagrees
    # with itself, so the honest answer is that this engine cannot tell.
    return _token(RELATION_AMBIGUOUS, REASON_INVALID, provenance=provenance)
