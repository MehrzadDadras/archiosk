"""Compile 2D drawing vectors into a parametric 3D building model.

CLAUDE-SPATIAL-COMPILER-01. The middle stage of the metabolic bridge:

    PDFVectorExtractor  ->  SpatialCompiler  ->  IFCVolumeValidator
    (2D primitives)         (topology + lift)    (IFC 4x3 STEP)

WHAT THIS IS AND IS NOT

It is a geometric compiler. It reads primitives that a drawing already contains -
closed perimeter loops, room labels, datum lines, door tags - and lifts them into
volumes. It does not interpret, infer intent, or repair a drawing. Where the
evidence is silent it says so in `warnings` rather than inventing a value, and
where the drawing contradicts itself it compiles what is DRAWN and records the
contradiction. A compiler that quietly corrects its input produces a model nobody
can trace back to the document it came from.

THE TWO ASSUMPTIONS THAT ARE NOT IN THE DRAWING

Wall thickness and door leaf width are not dimensioned anywhere in the source
set. Both are therefore parameters with declared defaults, and both are echoed
into the compiled model's `assumptions` so a downstream reader can see that they
were supplied rather than measured. Door width can instead be derived from a door
schedule, but only with an explicit points-per-foot scale - which is itself
derived from the section's own datums, never from the title block's declared
scale (on the proving corpus those two disagree by a factor of 1.5).

COORDINATE HANDEDNESS

PDFVectorExtractor reports `top_left_origin_y_down`. Extruding that directly
would mirror the building - a defect no validator here would catch, because a
mirrored polygon is still closed, still simple, and still positive-area. So Y is
flipped about the page height, restoring PDF user space (bottom-left, Y up), and
every emitted loop is normalised counter-clockwise for IFC profile convention.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Optional

_MM_PER_FOOT = 304.8

# Not measurable in the source set - see the module docstring.
DEFAULT_WALL_THICKNESS_POINTS = 6.0
DEFAULT_DOOR_WIDTH_POINTS = 36.0

_SHEET_ID_RE = re.compile(r"^[A-Z]{1,3}-\d{1,3}[A-Z]?$")
_DOOR_TAG_RE = re.compile(r"^([A-Z]{1,3}-\d{1,3}[A-Z]?)$")
_ELEVATION_RE = re.compile(r"(-?\d+)'-(\d+)\"")


class SpatialCompilationError(ValueError):
    """Raised when the drawing cannot be compiled into a coherent volume."""


# --------------------------------------------------------------------------
# geometry primitives
# --------------------------------------------------------------------------

def _key(point, tol=3):
    return (round(point[0], tol), round(point[1], tol))


def signed_area(polygon) -> float:
    """Shoelace. Positive is counter-clockwise in a Y-up frame."""
    total = 0.0
    for (x0, y0), (x1, y1) in zip(polygon, list(polygon[1:]) + [polygon[0]]):
        total += x0 * y1 - x1 * y0
    return total / 2.0


def ensure_ccw(polygon):
    return list(polygon) if signed_area(polygon) > 0 else list(reversed(polygon))


@dataclass(frozen=True)
class ToleranceContext:
    """Boundary band in declared chart units, not physical or survey uncertainty.

    Default matches the compiler's six-decimal point representation. Other
    charts require calibrated tolerances; numerical precision is not certainty.
    """
    boundary_distance: float = 0.000001


def classify_point_in_polygon(point, polygon, *, point_space=None, polygon_space=None,
                              point_plane=None, polygon_plane=None, geometry_level=None,
                              tolerance=ToleranceContext()):
    """Strict containment in one declared chart/plane; no implicit conversion.

    Vertices describe a polygon, not an unverified chain of strokes. A valid
    nonsingular planar chart is a caller premise. No metric/physical claim is
    derived from chart distances used for numerical boundary exclusion.
    """
    from services import deterministic_spatial as spatial
    result = {"state": "UNRESOLVED", "operator": "strict_point_in_polygon@1",
              "coordinate_space": point_space, "polygon_space": polygon_space,
              "plane_id": point_plane, "polygon_plane_id": polygon_plane,
              "geometry_level": geometry_level, "minimum_level": "PROJECTIVE",
              "tolerance": getattr(tolerance, "boundary_distance", None),
              "boundary_distance": None, "accuracy": "UNRESOLVED", "error": None}
    def refuse(code):
        result["error"] = code
        return result
    if not point_space or not polygon_space or not point_plane or not polygon_plane:
        return refuse("PREMISE_UNESTABLISHED")
    if point_space != polygon_space:
        return refuse("INCOMPARABLE_COORDINATE_SPACES")
    if point_plane != polygon_plane:
        return refuse("PLANE_MISMATCH")
    if geometry_level not in ("PROJECTIVE", "AFFINE", "EUCLIDEAN", "METRIC_SCALED"):
        return refuse("PREMISE_UNESTABLISHED")
    band = result["tolerance"]
    if isinstance(band, bool) or not isinstance(band, (float, int)) or not math.isfinite(band) or band < 0:
        return refuse("INVALID_TOLERANCE")
    def valid_point(p):
        return (isinstance(p, (tuple, list)) and len(p) == 2
                and all(isinstance(v, (float, int)) and not isinstance(v, bool)
                        and math.isfinite(v) for v in p))
    if not valid_point(point) or not isinstance(polygon, (tuple, list)) or not all(valid_point(p) for p in polygon):
        return refuse("INVALID_GEOMETRY")
    ring = [tuple(p) for p in polygon]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring.pop()
    if len(ring) < 3 or len(set(ring)) != len(ring):
        return refuse("DEGENERATE_POLYGON")
    edges = list(zip(ring, ring[1:] + ring[:1]))
    if any(math.dist(a, b) <= band for a, b in edges):
        return refuse("DEGENERATE_POLYGON")
    for i, (a, b) in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if spatial._segments_cross(a, b, *edges[j]):
                return refuse("DEGENERATE_POLYGON")
    # Translate to avoid large-origin cancellation in shoelace arithmetic.
    area = abs(signed_area([(x - ring[0][0], y - ring[0][1]) for x, y in ring]))
    perimeter = sum(math.dist(a, b) for a, b in edges)
    if not math.isfinite(area) or not math.isfinite(perimeter) or area <= band * perimeter:
        return refuse("DEGENERATE_POLYGON")
    distance = min(spatial._distance_point_to_segment(point, a, b) for a, b in edges)
    if not math.isfinite(distance):
        return refuse("INVALID_GEOMETRY")
    result.update(point=list(point), polygon=[list(p) for p in ring], boundary_distance=distance,
                  accuracy="EXACT" if distance == 0 else "APPROXIMATE")
    if distance <= band:
        result["state"] = "ON_BOUNDARY"
    else:
        result["state"] = "INSIDE" if spatial._point_in_ring(point, ring + [ring[0]]) else "OUTSIDE"
    return result


def point_in_polygon(point, polygon) -> bool:
    """Legacy local Cartesian polygon predicate: only strict INSIDE is true.

    Existing callers supply one local XY frame. New cross-view callers must
    use the explicit-space classifier, not this compatibility wrapper.
    """
    return classify_point_in_polygon(point, polygon, point_space="LOCAL_CARTESIAN",
        polygon_space="LOCAL_CARTESIAN", point_plane="local", polygon_plane="local",
        geometry_level="EUCLIDEAN")["state"] == "INSIDE"


def _distance_point_to_segment(point, a, b):
    """Perpendicular distance, plus how far along the segment the foot lands."""
    (px, py), (ax, ay), (bx, by) = point, a, b
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.dist(point, a), 0.0
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    foot = (ax + t * dx, ay + t * dy)
    return math.dist(point, foot), t * math.sqrt(length_sq)


def assemble_loops(segments: Iterable, tolerance: float = 0.5) -> list[list[tuple]]:
    """Chain raw segments into closed loops by endpoint adjacency.

    A drawing does not hand over polygons; it hands over strokes. Rectangles are
    decomposed into their four edges before reaching here precisely so that the
    same assembler serves both - a set of loose perimeter lines and an already
    closed shape follow one code path, and there is no second, untested route
    for the harder case.

    Open chains are DISCARDED, not closed by joining their loose ends. A gap in a
    perimeter means the drawing did not enclose that space, and silently sealing
    it would manufacture a room.
    """
    remaining = []
    for a, b in segments:
        if _key(a) != _key(b):
            remaining.append((tuple(a), tuple(b)))

    loops: list[list[tuple]] = []
    while remaining:
        start, current = remaining.pop(0)
        chain = [start, current]
        extended = True
        while extended and _key(chain[0]) != _key(chain[-1]):
            extended = False
            for index, (a, b) in enumerate(remaining):
                if math.dist(chain[-1], a) <= tolerance:
                    chain.append(b)
                elif math.dist(chain[-1], b) <= tolerance:
                    chain.append(a)
                else:
                    continue
                remaining.pop(index)
                extended = True
                break
        if _key(chain[0]) == _key(chain[-1]) and len(chain) >= 4:
            loops.append(ensure_ccw(chain[:-1]))
    return loops


# --------------------------------------------------------------------------
# reading the drawing
# --------------------------------------------------------------------------

def _sheet_id(page) -> Optional[str]:
    """The bottom-left sheet stamp - the lowest short token on the sheet."""
    stamps = [(s["centroid_points"]["y"], s["content"].strip()) for s in page["text"]
              if _SHEET_ID_RE.match(s["content"].strip())]
    return max(stamps)[1] if stamps else None


def _is_gridline(vector) -> bool:
    dash = vector.get("dash")
    return bool(dash) and dash != "[] 0"


def _segments_of(page, include_dashed=False) -> list[tuple]:
    segments = []
    for vector in page["vectors"]:
        if not include_dashed and _is_gridline(vector):
            continue
        points = vector.get("points")
        if not points:
            continue
        if vector["geometry_type"] == "rect":
            ring = [tuple(p) for p in points]
            segments.extend(zip(ring, ring[1:] + ring[:1]))
        elif vector["geometry_type"] == "line" and len(points) == 2:
            segments.append((tuple(points[0]), tuple(points[1])))
    return segments


def read_datums(page) -> list[dict]:
    """Level markers bound to the datum LINE they annotate, not to their own
    label centroid - a glyph's centre moves with its own width."""
    lines = sorted({round(v["points"][0][1], 3) for v in page["vectors"]
                    if v["geometry_type"] == "line"
                    and abs(v["points"][0][1] - v["points"][1][1]) < 0.01
                    and abs(v["points"][1][0] - v["points"][0][0]) > 300})
    if not lines:
        return []
    datums = []
    for span in page["text"]:
        content = span["content"]
        match = _ELEVATION_RE.search(content)
        if "EL." not in content or not match:
            continue
        y = span["centroid_points"]["y"]
        datums.append({
            "name": content.split("/")[0].strip(),
            "label_elevation_feet": int(match.group(1)) + int(match.group(2)) / 12.0,
            "line_y": min(lines, key=lambda line: abs(line - y)),
        })
    # lowest on the sheet (largest y) first
    return sorted(datums, key=lambda d: -d["line_y"])


def derive_points_per_foot(datums) -> tuple[Optional[float], list[str]]:
    """The scale the datums themselves agree on, by majority.

    Deliberately NOT the title block's declared scale: a declaration is a claim
    about the drawing, while the spacing between datum lines is the drawing. On
    the proving corpus the two disagree by a factor of 1.5, and every derived
    dimension would inherit that error.
    """
    if len(datums) < 2:
        return None, ["fewer than two datums - no scale could be derived"]
    base = datums[0]
    votes: dict[float, list[str]] = {}
    for datum in datums[1:]:
        rise = datum["label_elevation_feet"] - base["label_elevation_feet"]
        if rise == 0:
            continue
        scale = round((base["line_y"] - datum["line_y"]) / rise, 4)
        votes.setdefault(scale, []).append(datum["name"])
    if not votes:
        return None, ["datums carry no usable elevation difference"]
    best = max(votes, key=lambda s: len(votes[s]))
    warnings = []
    for scale, names in votes.items():
        if scale != best:
            for name in names:
                expected = base["line_y"] - (
                    dict((d["name"], d) for d in datums)[name]["label_elevation_feet"]
                    - base["label_elevation_feet"]) * best
                actual = dict((d["name"], d) for d in datums)[name]["line_y"]
                warnings.append(
                    "datum %s is inconsistent with the %.4f pt/ft the other datums "
                    "agree on: label places it at y=%.2f, it is drawn at y=%.2f "
                    "(%+.2f pt, %+.2f ft)"
                    % (name, best, expected, actual, actual - expected,
                       (expected - actual) / best))
    return best, warnings


def _declared_scale_points_per_foot(page) -> Optional[float]:
    for span in page["text"]:
        match = re.search(r'SCALE:\s*(\d+)/(\d+)"\s*=\s*1\'', span["content"])
        if match:
            return 72.0 * int(match.group(1)) / int(match.group(2))
    return None


# --------------------------------------------------------------------------
# the compiler
# --------------------------------------------------------------------------

class SpatialCompiler:
    """Lift a 2D drawing set into a parametric model an IFC exporter accepts."""

    schema_version = "spatial_compilation_v1"

    def __init__(self, wall_thickness=DEFAULT_WALL_THICKNESS_POINTS,
                 default_door_width=DEFAULT_DOOR_WIDTH_POINTS):
        self.wall_thickness = wall_thickness
        self.default_door_width = default_door_width

    # -- sheet selection ---------------------------------------------------
    @staticmethod
    def _find_plan(document):
        for page in document["pages"]:
            if any("PLAN" in s["content"].upper() and "FOUNDATION" not in s["content"].upper()
                   for s in page["text"]) and any(
                       v["geometry_type"] == "rect" for v in page["vectors"]):
                return page
        return None

    @staticmethod
    def _find_section(document):
        for page in document["pages"]:
            if any("EL." in s["content"] for s in page["text"]):
                return page
        return None

    # -- compilation -------------------------------------------------------
    def compile(self, document: dict, *, project_name: str = "ARCHIOSK Compiled Model",
                schedule: Optional[list[dict]] = None,
                plan_page: Optional[int] = None,
                section_page: Optional[int] = None) -> dict[str, Any]:
        pages = {p["page_number"]: p for p in document["pages"]}
        plan = pages[plan_page] if plan_page else self._find_plan(document)
        section = pages[section_page] if section_page else self._find_section(document)
        if plan is None:
            raise SpatialCompilationError("no floor plan sheet found in the document")
        if section is None:
            raise SpatialCompilationError(
                "no section sheet with level datums found - there is no evidence "
                "of storey height, and guessing one would invent the building's "
                "third dimension")

        warnings: list[str] = []
        datums = read_datums(section)
        points_per_foot, scale_warnings = derive_points_per_foot(datums)
        warnings.extend(scale_warnings)

        declared = _declared_scale_points_per_foot(section)
        if declared and points_per_foot and abs(declared - points_per_foot) > 1e-6:
            warnings.append(
                "sheet %s declares %.2f pt/ft but its datums are drawn at %.2f pt/ft; "
                "the drawn geometry is used" % (_sheet_id(section), declared, points_per_foot))

        if len(datums) < 2:
            raise SpatialCompilationError("at least two level datums are required to extrude")
        base, above = datums[0], datums[1]
        storey_height = base["line_y"] - above["line_y"]
        if storey_height <= 0:
            raise SpatialCompilationError("level datums do not rise")

        # -- levels, elevations measured rather than believed ---------------
        levels = []
        for datum in datums:
            measured = base["line_y"] - datum["line_y"]
            levels.append({
                "name": datum["name"],
                "elevation": measured,
                "label_elevation_feet": datum["label_elevation_feet"],
                "measured_elevation_feet": (measured / points_per_foot) if points_per_foot else None,
            })

        # -- spaces ---------------------------------------------------------
        height_points = plan["height_points"]

        def lift(point):
            """Top-left Y-down -> PDF user space Y-up. Skipping this mirrors the
            building, and every downstream check would still pass."""
            return (round(point[0], 6), round(height_points - point[1], 6))

        loops = [ensure_ccw([lift(p) for p in loop])
                 for loop in assemble_loops(_segments_of(plan))]
        labels = self._room_labels(plan, lift)

        spaces, bound_labels, label_containment = [], set(), []
        for index, loop in enumerate(loops):
            inside = []
            for label_index, (name, point) in enumerate(labels):
                plane = "source-page:%s" % plan["page_number"]
                relation = classify_point_in_polygon(point, loop,
                    point_space="PDF_USER_POINTS", polygon_space="PDF_USER_POINTS",
                    point_plane=plane, polygon_plane=plane, geometry_level="PROJECTIVE")
                label_containment.append({"label": name, "label_occurrence": label_index,
                    "space_id": "SPACE-%02d" % (index + 1), "source": document.get("source", {}),
                    "page_number": plan["page_number"], "relation": relation})
                if relation["state"] == "INSIDE":
                    inside.append(name)
                elif relation["state"] in ("ON_BOUNDARY", "UNRESOLVED"):
                    warnings.append("room label %r containment %s for loop %d; not bound (tolerance %s PDF points)"
                                    % (name, relation["state"], index, relation["tolerance"]))
            bound_labels.update(inside)
            if len(inside) > 1:
                warnings.append("loop %d contains %d room labels (%s) - binding is ambiguous"
                                % (index, len(inside), ", ".join(sorted(inside))))
            name = sorted(inside)[0] if inside else "UNNAMED SPACE %d" % (index + 1)
            if not inside:
                warnings.append("loop %d encloses no room label and is compiled unnamed" % index)
            spaces.append({
                "id": "SPACE-%02d" % (index + 1),
                "name": name,
                "level": base["name"],
                "height": storey_height,
                "boundary_polygon_2d": [{"x": x, "y": y} for x, y in loop + [loop[0]]],
            })
        for name, _point in labels:
            if name not in bound_labels:
                warnings.append("room label %r falls inside no compiled loop" % name)

        # -- walls, one per unique loop edge --------------------------------
        walls, seen = [], {}
        for loop in loops:
            ring = loop + [loop[0]]
            for a, b in zip(ring, ring[1:]):
                edge = tuple(sorted([_key(a), _key(b)]))
                if edge in seen:
                    continue
                seen[edge] = True
                walls.append({
                    "id": "WALL-%02d" % (len(walls) + 1),
                    "baseline": [{"x": edge[0][0], "y": edge[0][1]},
                                 {"x": edge[1][0], "y": edge[1][1]}],
                    "height": storey_height,
                    "thickness": self.wall_thickness,
                    "openings": [],
                })

        # -- door openings ---------------------------------------------------
        head_height = self._door_head_height(section, points_per_foot)
        if head_height is None:
            head_height = storey_height / 2.0
            warnings.append("no door head dimension found on the section; openings "
                            "use half the storey height and are NOT evidence-derived")
        widths = self._schedule_widths(schedule, points_per_foot)

        for mark, point in self._door_tags(plan, lift):
            width = widths.get(mark)
            if width is None:
                width = self.default_door_width
                warnings.append("door %s has no schedule row; nominal width %.1f pt assumed"
                                % (mark, width))
            host, offset, shifted = self._host_wall(point, walls, width)
            if host is None:
                warnings.append("door %s at (%.1f, %.1f) is not adjacent to any wall and "
                                "was not placed" % (mark, point[0], point[1]))
                continue
            if shifted > 0.01:
                # The tag sits so near a corner that a leaf of this width will
                # not fit where it is drawn. Moving it silently would put a door
                # somewhere the drawing does not.
                warnings.append(
                    "door %s was shifted %.1f pt along %s to keep the opening "
                    "inside the wall - it is tagged closer to the corner than a "
                    "%.1f pt leaf allows" % (mark, shifted, host["id"], width))
            host["openings"].append({
                "id": mark, "offset": round(offset, 6),
                "width": round(width, 6),
                "height": min(head_height, host["height"]),
            })

        return {
            "project_name": project_name,
            "schema_version": self.schema_version,
            "levels": levels,
            "spaces": spaces,
            "label_containment": label_containment,
            "walls": walls,
            "source": document.get("source", {}),
            "derived": {
                "plan_sheet": _sheet_id(plan),
                "section_sheet": _sheet_id(section),
                "points_per_foot": points_per_foot,
                "declared_points_per_foot": declared,
                "storey_height_points": storey_height,
                "door_head_height_points": head_height,
            },
            "assumptions": {
                "wall_thickness_points": self.wall_thickness,
                "default_door_width_points": self.default_door_width,
                "note": "not dimensioned in the source drawings",
            },
            "warnings": warnings,
        }

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _room_labels(plan, lift):
        labels = []
        for span in plan["text"]:
            content = span["content"].strip()
            if (len(content) > 4 and content.upper() == content and "|" not in content
                    and not _SHEET_ID_RE.match(content) and "PLAN" not in content
                    and any(c.isalpha() for c in content) and not any(c.isdigit() for c in content)):
                centroid = span["centroid_points"]
                labels.append((content, lift((centroid["x"], centroid["y"]))))
        return labels

    @staticmethod
    def _door_tags(plan, lift):
        tags = []
        for span in plan["text"]:
            content = span["content"].strip()
            match = _DOOR_TAG_RE.match(content)
            if match and content != _sheet_id(plan):
                centroid = span["centroid_points"]
                tags.append((match.group(1), lift((centroid["x"], centroid["y"]))))
        return tags

    @staticmethod
    def _door_head_height(section, points_per_foot):
        """A head dimension written as points is taken verbatim; one written in
        feet is converted with the DERIVED scale."""
        for span in section["text"]:
            match = re.search(r"(\d+(?:\.\d+)?)\s*pt", span["content"])
            if match:
                return float(match.group(1))
        for span in section["text"]:
            if "HEAD" in span["content"].upper():
                feet = _ELEVATION_RE.search(span["content"])
                if feet and points_per_foot:
                    return (int(feet.group(1)) + int(feet.group(2)) / 12.0) * points_per_foot
        return None

    @staticmethod
    def _schedule_widths(schedule, points_per_foot):
        if not schedule or not points_per_foot:
            return {}
        widths = {}
        for row in schedule:
            size = (row.get("Size") or "").split("x")
            mark = (row.get("Mark") or "").strip()
            if mark and size and size[0].strip().isdigit():
                widths[mark] = float(size[0].strip()) / _MM_PER_FOOT * points_per_foot
        return widths

    @staticmethod
    def _host_wall(point, walls, width, max_distance=24.0):
        best, best_distance, best_offset = None, None, 0.0
        for wall in walls:
            a = (wall["baseline"][0]["x"], wall["baseline"][0]["y"])
            b = (wall["baseline"][1]["x"], wall["baseline"][1]["y"])
            distance, along = _distance_point_to_segment(point, a, b)
            if math.dist(a, b) < width:
                continue
            if best_distance is None or distance < best_distance:
                best, best_distance, best_offset = wall, distance, along
        if best is None or best_distance > max_distance:
            return None, 0.0, 0.0
        a = (best["baseline"][0]["x"], best["baseline"][0]["y"])
        b = (best["baseline"][1]["x"], best["baseline"][1]["y"])
        length = math.dist(a, b)
        ideal = best_offset - width / 2.0
        offset = min(max(ideal, 0.0), length - width)
        return best, offset, abs(offset - ideal)


def compile_to_ifc(document, *, schedule=None, project_name="ARCHIOSK Compiled Model",
                   compiler=None):
    """Full metabolic bridge: 2D primitives -> model -> IFC 4x3 STEP text."""
    from engine.ifc_volume_validator import IFCVolumeValidator

    model = (compiler or SpatialCompiler()).compile(
        document, schedule=schedule, project_name=project_name)
    return model, IFCVolumeValidator().validate_and_export(model)
