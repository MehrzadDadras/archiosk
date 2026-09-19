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

from services.runtime_observation import observed
import math
import re
from dataclasses import dataclass, asdict
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

    def __init__(self, message, *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic


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
    segment_length: float = 0.000001
    vector_length: float = 0.000001
    homogeneous_w: float = 1e-12
    matrix_pivot: float = 1e-14
    homography_weak_condition: float = 1e8
    homography_max_condition: float = 1e10
    round_trip: float = 1e-9
    parallel_degrees: float = 0.25
    finite_degrees: float = 1.0
    vp_good_condition: float = 20.0
    vp_degenerate_condition: float = 100.0
    horizon_consistent: float = 0.001
    horizon_weak: float = 0.003


PROJECTIVE_SPACES = ("SOURCE_PIXELS", "NORMALIZED_IMAGE", "AFFINE_RECTIFIED",
                     "EUCLIDEAN_RECTIFIED", "WORLD_SCALED", "RECTIFIED_DISPLAY_PIXELS")
GEOMETRY_LEVELS = ("PROJECTIVE", "AFFINE", "EUCLIDEAN", "METRIC_SCALED")


def _geometry_result(operator, *, source_space=None, target_space=None,
                     source_plane=None, target_plane=None, geometry_level=None,
                     tolerance=ToleranceContext(), uncertainty=None, source=None):
    """Operator payload within the existing geometry owner, not an evidence store."""
    from engine.ifc_volume_validator import numeric_validity
    result = dict(operator=operator, state="UNRESOLVED", error=None, value=None,
        source_space=source_space, target_space=target_space, source_plane=source_plane,
        target_plane=target_plane, geometry_level=geometry_level, conditioning=None,
        uncertainty=uncertainty if uncertainty is not None else {"state": "UNRESOLVED"},
        source=source if source is not None else {}, tolerance_context=asdict(tolerance))
    if source_space not in PROJECTIVE_SPACES or target_space not in PROJECTIVE_SPACES:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if not isinstance(source_plane, str) or not source_plane or not isinstance(target_plane, str) or not target_plane:
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    if geometry_level not in GEOMETRY_LEVELS:
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    bands = asdict(tolerance)
    if (any(numeric_validity(v) != "FINITE" or v <= 0 for v in bands.values())
            or not tolerance.matrix_pivot < 1
            or not tolerance.homogeneous_w < 1
            or not 1 < tolerance.homography_weak_condition < tolerance.homography_max_condition
            or not 0 < tolerance.parallel_degrees < tolerance.finite_degrees < 90
            or not 1 < tolerance.vp_good_condition < tolerance.vp_degenerate_condition
            or not tolerance.horizon_consistent < tolerance.horizon_weak):
        return _geometry_refuse(result, "INVALID_TOLERANCE")
    return result


def _geometry_refuse(result, error, state="UNRESOLVED"):
    result.update(state=state, error=error, value=None)
    return result


def _finite_coordinates(values, size):
    from engine.ifc_volume_validator import numeric_validity
    return (isinstance(values, (tuple, list)) and len(values) == size
            and all(numeric_validity(v) == "FINITE" for v in values))


def vector_usability(vector, **context):
    """Normalize only a usable same-chart Euclidean vector; retain exact zero."""
    result = _geometry_result("vector_usability@1", **context)
    if result["error"]:
        return result
    if result["source_space"] != result["target_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if result["source_plane"] != result["target_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if result["geometry_level"] not in ("EUCLIDEAN", "METRIC_SCALED"):
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    if not any(_finite_coordinates(vector, size) for size in (2, 3)):
        return _geometry_refuse(result, "NON_FINITE_VECTOR")
    length = math.hypot(*vector)
    if not math.isfinite(length):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    if length == 0:
        return _geometry_refuse(result, "ZERO_LENGTH_VECTOR", "DEGENERATE")
    if length <= result["tolerance_context"]["vector_length"]:
        return _geometry_refuse(result, "DEGENERATE_GEOMETRY", "DEGENERATE")
    result.update(state="ESTABLISHED", value=[v / length for v in vector],
                  length=length, conditioning=1.0, premises={"vector": list(vector)})
    return result


def bounded_acos(value, error_bound, **context):
    """Explicit domain intersection gives an interval, never a coerced scalar.

    An error interval crossing the domain boundary is only a conditional weak
    result. The original number and full uncertainty remain in the derivation.
    """
    from engine.ifc_volume_validator import numeric_validity
    result = _geometry_result("bounded_acos@1", **context)
    if result["error"]:
        return result
    if result["source_space"] != result["target_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if result["source_plane"] != result["target_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if result["geometry_level"] not in ("EUCLIDEAN", "METRIC_SCALED"):
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    if any(numeric_validity(v) != "FINITE" for v in (value, error_bound)) or error_bound < 0:
        return _geometry_refuse(result, "INVALID_NUMERIC_DOMAIN")
    lower, upper = value - error_bound, value + error_bound
    if not all(math.isfinite(v) for v in (lower, upper)):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    result["premises"] = {"input": value, "error_bound": error_bound}
    if lower > 1 or upper < -1:
        return _geometry_refuse(result, "INVALID_NUMERIC_DOMAIN")
    # Intersection is recorded explicitly; `value` itself is never clamped.
    interval = [max(-1.0, lower), min(1.0, upper)]
    angles = [math.acos(interval[1]), math.acos(interval[0])]
    result.update(state="ESTABLISHED" if error_bound == 0 else "WEAK",
        value=angles, conditioning=None,
        uncertainty={"input_uncertainty": result["uncertainty"], "input_interval": [lower, upper],
                     "admissible_interval": interval, "angle_interval_radians": angles,
                     "conditional_on_domain": lower < -1 or upper > 1})
    return result


def _inverse_projective_matrix(matrix, tolerance):
    """Three-column elimination on a bounded representative; no external kernel."""
    scale = max(abs(v) for row in matrix for v in row)
    if scale == 0:
        raise ValueError("HOMOGRAPHY_SINGULAR")
    a = [[v / scale for v in row] + [float(i == j) for j in range(3)]
         for i, row in enumerate(matrix)]
    for column in range(3):
        pivot_row = max(range(column, 3), key=lambda i: abs(a[i][column]))
        pivot = a[pivot_row][column]
        if pivot == 0:
            raise ValueError("HOMOGRAPHY_SINGULAR")
        if abs(pivot) <= tolerance.matrix_pivot:
            raise ValueError("HOMOGRAPHY_ILL_CONDITIONED")
        a[column], a[pivot_row] = a[pivot_row], a[column]
        a[column] = [v / pivot for v in a[column]]
        for i in range(3):
            if i != column:
                factor = a[i][column]
                a[i] = [x - factor * y for x, y in zip(a[i], a[column])]
        if not all(math.isfinite(v) for row in a for v in row):
            raise ValueError("NON_FINITE_DERIVED_VALUE")
    inverse = [row[3:] for row in a]
    condition = max(sum(abs(v / scale) for v in row) for row in matrix) * max(
        sum(abs(v) for v in row) for row in inverse)
    if not math.isfinite(condition):
        raise ValueError("NON_FINITE_DERIVED_VALUE")
    return inverse, condition


@observed
def validate_homography(matrix, **context):
    """Typed source-to-target map; infinity-norm conditioning is scale invariant.

    Canonicalization changes a homogeneous representative, never input evidence.
    Matrix shape alone cannot earn rectification or increase geometry level.
    """
    result = _geometry_result("homography_validation@1", **context)
    if result["error"]:
        return result
    if not isinstance(matrix, (list, tuple)) or len(matrix) != 3 or not all(
            _finite_coordinates(row, 3) for row in matrix):
        return _geometry_refuse(result, "INVALID_HOMOGRAPHY", "DEGENERATE")
    tolerance = context.get("tolerance", ToleranceContext())
    scale = max(abs(v) for row in matrix for v in row)
    if scale == 0:
        return _geometry_refuse(result, "HOMOGRAPHY_SINGULAR", "DEGENERATE")
    bounded = [[v / scale for v in row] for row in matrix]
    divisor = bounded[2][2]
    if abs(divisor) <= tolerance.homogeneous_w:
        norm = math.sqrt(math.fsum(v * v for row in bounded for v in row))
        first = next(v for row in bounded for v in row if v != 0)
        divisor = math.copysign(norm, first)
    canonical = [[v / divisor for v in row] for row in bounded]
    try:
        _, condition = _inverse_projective_matrix(canonical, tolerance)
    except ValueError as error:
        return _geometry_refuse(result, str(error), "DEGENERATE")
    result["conditioning"] = condition
    if condition >= tolerance.homography_max_condition:
        return _geometry_refuse(result, "HOMOGRAPHY_ILL_CONDITIONED", "DEGENERATE")
    level = result["geometry_level"]
    ceiling = "PROJECTIVE"
    if canonical[2][0] == canonical[2][1] == 0:
        ceiling = "AFFINE"
        a, b, c, d = canonical[0][0], canonical[0][1], canonical[1][0], canonical[1][1]
        if a * b + c * d == 0 and a * a + c * c == b * b + d * d:
            ceiling = "METRIC_SCALED" if a * a + c * c == 1 else "EUCLIDEAN"
    result.update(state="WEAK" if condition >= tolerance.homography_weak_condition else "ESTABLISHED",
        matrix=canonical, value=canonical, input_geometry_level=level,
        geometry_level=GEOMETRY_LEVELS[min(GEOMETRY_LEVELS.index(level), GEOMETRY_LEVELS.index(ceiling))],
        conditioning_measure="infinity_norm", premises={"matrix": [list(row) for row in matrix]})
    return result


@observed
def estimate_control_homography(source_points, target_points, **context):
    """Four identified coplanar controls, column vectors; no scale estimation.

    Projective frames reuse this owner's 3x3 inverse/product. Correspondence
    identity and target-frame authority are supplied only by the evidence owner.
    The numerical result alone earns no legal, Euclidean or metric authority.
    """
    result = _geometry_result("control_homography@1", **context)
    if result["error"]:
        return result
    tolerance = context.get("tolerance", ToleranceContext())
    if (not isinstance(source_points, (list, tuple)) or not isinstance(target_points, (list, tuple))
            or len(source_points) != 4 or len(target_points) != 4
            or not all(_finite_coordinates(p, 2) for p in [*source_points, *target_points])):
        return _geometry_refuse(result, "FOUR_FINITE_CONTROLS_REQUIRED")
    def frame(points):
        matrix = [[points[col][row] if row < 2 else 1.0 for col in range(3)] for row in range(3)]
        inverse, condition = _inverse_projective_matrix(matrix, tolerance)
        fourth = [*points[3], 1.0]
        scales = [math.fsum(a*b for a,b in zip(row, fourth)) for row in inverse]
        if any(not math.isfinite(v) or abs(v) <= tolerance.matrix_pivot for v in scales):
            raise ValueError("DEGENERATE_CONTROL_FRAME")
        return [[matrix[row][col]*scales[col] for col in range(3)] for row in range(3)], condition
    try:
        source, sc = frame(source_points)
        target, tc = frame(target_points)
        inverse, ic = _inverse_projective_matrix(source, tolerance)
        matrix = _projective_product(target, inverse)
        validated = validate_homography(matrix, **context)
        if validated["state"] != "ESTABLISHED":
            return dict(validated, operator="control_homography@1")
        residuals = []
        inverse_transform = invert_homography(validated, tolerance=tolerance)
        for p, expected in zip(source_points, target_points):
            transformed = transform_homogeneous_point(validated, [*p, 1],
                point_space=context.get("source_space"), point_plane=context.get("source_plane"), tolerance=tolerance)
            if transformed["state"] != "ESTABLISHED":
                return _geometry_refuse(result, "CONTROL_TRANSFORM_UNRESOLVED")
            residual = math.dist(transformed["value"], expected)
            roundtrip = transform_homogeneous_point(inverse_transform, [*transformed["value"], 1],
                point_space=context.get("target_space"), point_plane=context.get("target_plane"), tolerance=tolerance)
            if (not math.isfinite(residual) or residual > tolerance.round_trip
                    or roundtrip["state"] != "ESTABLISHED" or math.dist(roundtrip["value"], p) > tolerance.round_trip):
                return _geometry_refuse(result, "CONTROL_ROUND_TRIP_FAILED")
            residuals.append(residual)
        validated.update(operator="control_homography@1", control_residuals=residuals,
            control_conditioning=max(sc, tc, ic), physical_scale="NOT_ESTABLISHED",
            premises={"source_points": source_points, "target_points": target_points})
        if max(sc, tc, ic) >= tolerance.homography_weak_condition:
            return _geometry_refuse(validated, "CONTROL_FRAME_ILL_CONDITIONED", "WEAK")
        return validated
    except (ValueError, OverflowError, ZeroDivisionError):
        return _geometry_refuse(result, "DEGENERATE_CONTROL_FRAME", "DEGENERATE")


def _recheck_homography(transform, tolerance):
    """Stored result flags never substitute for revalidation at an operator boundary."""
    if not isinstance(transform, dict):
        return _geometry_result("homography_validation@1", tolerance=tolerance)
    result = validate_homography(transform.get("matrix"), tolerance=tolerance,
        **{key: transform.get(key) for key in ("source_space", "target_space", "source_plane",
            "target_plane", "geometry_level", "uncertainty", "source")})
    if transform.get("error"):
        return _geometry_refuse(result, transform["error"], transform.get("state", "UNRESOLVED"))
    if not result["error"] and transform.get("state") not in ("ESTABLISHED", "WEAK"):
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    if not result["error"] and transform.get("state") == "WEAK":
        result["state"] = "WEAK"
    return result


def dehomogenize(point, **context):
    """Scale-invariant W guard; never divides an infinite or near-infinite point."""
    result = _geometry_result("dehomogenization@1", **context)
    if result["error"]:
        return result
    if result["source_space"] != result["target_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if result["source_plane"] != result["target_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if not _finite_coordinates(point, 3):
        return _geometry_refuse(result, "NON_FINITE_POINT")
    scale = max(abs(v) for v in point)
    if scale == 0:
        result["point_kind"] = "DEGENERATE"
        return _geometry_refuse(result, "DEHOMOGENIZATION_UNSTABLE", "DEGENERATE")
    homogeneous = [v / scale for v in point]
    w = homogeneous[2]
    result.update(homogeneous=homogeneous, premises={"homogeneous_point": list(point)})
    if abs(w) <= result["tolerance_context"]["homogeneous_w"]:
        result["point_kind"] = "INFINITE" if w == 0 else "NEAR_INFINITY"
        return _geometry_refuse(result, "DEHOMOGENIZATION_UNSTABLE", "DEGENERATE")
    value = [homogeneous[i] / w for i in (0, 1)]
    if not _finite_coordinates(value, 2):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    result.update(state="ESTABLISHED", value=value, point_kind="FINITE", conditioning=1 / abs(w))
    return result


@observed
def transform_homogeneous_point(transform, point, *, point_space=None, point_plane=None,
                                tolerance=ToleranceContext()):
    result = _recheck_homography(transform, tolerance)
    result["operator"] = "homography_point@1"
    if result["error"]:
        return result
    if point_space != result["source_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if point_plane != result["source_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if not _finite_coordinates(point, 3):
        return _geometry_refuse(result, "NON_FINITE_POINT")
    scale = max(abs(v) for v in point)
    normalized = [v / scale for v in point] if scale else [0., 0., 0.]
    try:
        homogeneous = [math.fsum(a * b for a, b in zip(row, normalized)) for row in result["matrix"]]
    except (ArithmeticError, ValueError):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    projected = dehomogenize(homogeneous, tolerance=tolerance,
        source_space=result["target_space"], target_space=result["target_space"],
        source_plane=result["target_plane"], target_plane=result["target_plane"],
        **{key: result[key] for key in ("geometry_level", "uncertainty", "source")})
    result.update(point_kind=projected.get("point_kind"), homogeneous=projected.get("homogeneous"),
                  dehomogenization_conditioning=projected["conditioning"],
                  premises={"transform": transform, "homogeneous_point": list(point)})
    if projected["error"]:
        return _geometry_refuse(result, projected["error"], projected["state"])
    result["value"] = projected["value"]
    return result


def _projective_product(left, right):
    result = [[math.fsum(left[i][k] * right[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
    if not all(_finite_coordinates(row, 3) for row in result):
        raise ValueError("NON_FINITE_DERIVED_VALUE")
    return result


@observed
def invert_homography(transform, *, tolerance=ToleranceContext()):
    original = _recheck_homography(transform, tolerance)
    if original["error"]:
        original["operator"] = "homography_inverse@1"
        return original
    context = dict(source_space=original["target_space"], target_space=original["source_space"],
        source_plane=original["target_plane"], target_plane=original["source_plane"],
        geometry_level=original["geometry_level"], uncertainty=original["uncertainty"],
        source=original["source"], tolerance=tolerance)
    try:
        inverse, _ = _inverse_projective_matrix(original["matrix"], tolerance)
        result = validate_homography(inverse, **context)
        result["operator"] = "homography_inverse@1"
        if result["error"]:
            return result
        identity = _projective_product(result["matrix"], original["matrix"])
        if identity[2][2] == 0:
            return _geometry_refuse(result, "HOMOGRAPHY_ILL_CONDITIONED", "DEGENERATE")
        residual = max(abs(identity[i][j] / identity[2][2] - float(i == j))
                       for i in range(3) for j in range(3))
        result["round_trip_residual"] = residual
        if not math.isfinite(residual) or residual > tolerance.round_trip:
            return _geometry_refuse(result, "HOMOGRAPHY_ILL_CONDITIONED", "DEGENERATE")
    except (ArithmeticError, ValueError):
        return _geometry_refuse(_geometry_result("homography_inverse@1", **context),
                                "NON_FINITE_DERIVED_VALUE", "DEGENERATE")
    result.update(premises={"transform": transform}, conditioning_history=[original["conditioning"]])
    if original["state"] == "WEAK":
        result["state"] = "WEAK"
    return result


@observed
def compose_homographies(first, second, *, tolerance=ToleranceContext()):
    """AB then BC gives H2 H1; endpoint checks prohibit reversed chart order."""
    a, b = (_recheck_homography(t, tolerance) for t in (first, second))
    result = dict(a, operator="homography_composition@1", value=None,
                  target_space=b["target_space"], target_plane=b["target_plane"])
    for operand in (a, b):
        if operand["error"]:
            return _geometry_refuse(result, operand["error"], operand["state"])
    if a["target_space"] != b["source_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if a["target_plane"] != b["source_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    try:
        matrix = _projective_product(b["matrix"], a["matrix"])
    except (ArithmeticError, ValueError):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    result = validate_homography(matrix, source_space=a["source_space"], target_space=b["target_space"],
        source_plane=a["source_plane"], target_plane=b["target_plane"], tolerance=tolerance,
        geometry_level=GEOMETRY_LEVELS[min(GEOMETRY_LEVELS.index(t["geometry_level"]) for t in (a, b))],
        uncertainty={"premises": [a["uncertainty"], b["uncertainty"]]},
        source={"premises": [a["source"], b["source"]]})
    result.update(operator="homography_composition@1", premises={"first": first, "second": second},
                  conditioning_history=[a["conditioning"], b["conditioning"]])
    if not result["error"] and any(t["state"] == "WEAK" for t in (a, b)):
        result["state"] = "WEAK"
    return result


@observed
def transform_homogeneous_line(transform, line, *, line_space=None, line_plane=None,
                               tolerance=ToleranceContext()):
    """Dual action H^-T l. A line is never passed to the point transform."""
    result = _recheck_homography(transform, tolerance)
    result["operator"] = "homography_line@1"
    if result["error"]:
        return result
    if line_space != result["source_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if line_plane != result["source_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if not _finite_coordinates(line, 3):
        return _geometry_refuse(result, "INVALID_LINE")
    scale = max(abs(v) for v in line)
    if scale == 0:
        return _geometry_refuse(result, "DEGENERATE_GEOMETRY", "DEGENERATE")
    normalized = [v / scale for v in line]
    try:
        inverse, _ = _inverse_projective_matrix(result["matrix"], tolerance)
        dual = [math.fsum(inverse[j][i] * normalized[j] for j in range(3)) for i in range(3)]
    except (ArithmeticError, ValueError):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE")
    scale = max(abs(v) for v in dual)
    if not _finite_coordinates(dual, 3) or scale == 0:
        return _geometry_refuse(result, "DEGENERATE_GEOMETRY", "DEGENERATE")
    result.update(value=[v / scale for v in dual], premises={"transform": transform, "line": list(line)},
                  line_kind="INFINITE" if dual[0] == dual[1] == 0 else "FINITE")
    return result


def classify_vanishing_direction(normal, direction, **context):
    """Classify a direction relative to a picture-plane normal, not a camera fit.

    No station/plane origin is invented, so no finite VP position is claimed.
    A tolerance-band infinity classification is distinct from exact parallelism.
    """
    result = _geometry_result("vanishing_direction@1", **context)
    if result["error"]:
        return result
    if not _finite_coordinates(normal, 3) or not _finite_coordinates(direction, 3):
        return _geometry_refuse(result, "NON_FINITE_VECTOR")
    n, v = vector_usability(normal, **context), vector_usability(direction, **context)
    for operand in (n, v):
        if operand["error"]:
            return _geometry_refuse(result, operand["error"], operand["state"])
    dot = abs(math.fsum(a * b for a, b in zip(n["value"], v["value"])))
    if not math.isfinite(dot) or dot > 1:
        return _geometry_refuse(result, "INVALID_NUMERIC_DOMAIN")
    degrees = math.degrees(math.asin(dot))
    bands = result["tolerance_context"]
    kind = ("INFINITE" if degrees <= bands["parallel_degrees"] else
            "NEAR_INFINITY" if degrees < bands["finite_degrees"] else "FINITE")
    result.update(direction_kind=kind, exact_parallel=dot == 0, angle_to_plane_degrees=degrees,
                  premises={"normal": list(normal), "direction": list(direction)}, finite_vp=None)
    if dot == 0:
        # A valid projective direction at infinity, not an unusable zero vector.
        result.update(state="ESTABLISHED", homogeneous_direction=[*v["value"], 0.0])
        return result
    condition = 1 / dot
    if not math.isfinite(condition):
        return _geometry_refuse(result, "NON_FINITE_DERIVED_VALUE", "DEGENERATE")
    result["conditioning"] = condition
    if condition >= bands["vp_degenerate_condition"]:
        return _geometry_refuse(result, "VANISHING_DIRECTION_UNSTABLE", "DEGENERATE")
    result.update(state="ESTABLISHED" if condition < bands["vp_good_condition"] else "WEAK",
                  value=v["value"] if kind == "FINITE" else None)
    return result


def classify_horizon_residual(residual, *, residual_units=None, **context):
    """Qualification of an observed horizon residual in explicit diagonal units."""
    from engine.ifc_volume_validator import numeric_validity
    result = _geometry_result("horizon_residual@1", **context)
    if result["error"]:
        return result
    if result["source_space"] != result["target_space"]:
        return _geometry_refuse(result, "SPACE_MISMATCH", "INCOMPARABLE")
    if result["source_plane"] != result["target_plane"]:
        return _geometry_refuse(result, "PLANE_MISMATCH", "INCOMPARABLE")
    if residual_units != "IMAGE_DIAGONAL":
        return _geometry_refuse(result, "PREMISE_UNESTABLISHED")
    if numeric_validity(residual) != "FINITE" or residual < 0:
        return _geometry_refuse(result, "INVALID_NUMERIC_DOMAIN")
    bands = result["tolerance_context"]
    result["premises"] = {"residual": residual, "units": residual_units}
    if residual > bands["horizon_weak"]:
        result["consistency"] = "INCONSISTENT"
        return _geometry_refuse(result, "HORIZON_INCONSISTENT")
    weak = residual > bands["horizon_consistent"]
    result.update(state="WEAK" if weak else "ESTABLISHED", value=residual,
                  consistency="WEAK" if weak else "CONSISTENT")
    return result


@observed
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


@observed
def project_point_to_segment(point, a, b, *, point_space=None, segment_space=None,
                             point_plane=None, segment_plane=None, geometry_level=None,
                             tolerance=ToleranceContext(), source=None):
    """Local Euclidean projection, or an explicit refusal; distances use chart units.

    The finite raw parameter is checked BEFORE constraining it to the segment.
    No physical scale or evidentiary authority is earned by this calculation.
    """
    from engine.ifc_volume_validator import numeric_validity
    result = dict(state="UNRESOLVED", error=None, operator="segment_projection@1",
                  coordinate_space=point_space, segment_space=segment_space,
                  plane_id=point_plane, segment_plane_id=segment_plane,
                  geometry_level=geometry_level, tolerance=tolerance.segment_length,
                  source=source or {}, point=None, parameter=None, distance=None,
                  distance_along=None, length=None)
    def refuse(code, state="UNRESOLVED"):
        result.update(error=code, state=state)
        return result
    if not all((point_space, segment_space, point_plane, segment_plane)):
        return refuse("PREMISE_UNESTABLISHED")
    if point_space != segment_space:
        return refuse("INCOMPARABLE_COORDINATE_SPACES", "INCOMPARABLE")
    if point_plane != segment_plane:
        return refuse("PLANE_MISMATCH", "INCOMPARABLE")
    if geometry_level not in ("EUCLIDEAN", "METRIC_SCALED"):
        return refuse("PREMISE_UNESTABLISHED")
    if numeric_validity(tolerance.segment_length) != "FINITE" or tolerance.segment_length < 0:
        return refuse("INVALID_TOLERANCE")
    for p in (point, a, b):
        if not isinstance(p, (tuple, list)) or len(p) != 2:
            return refuse("INVALID_GEOMETRY")
        if any(numeric_validity(v) != "FINITE" for v in p):
            return refuse("INVALID_GEOMETRIC_NUMBER")
    try:
        dx, dy = b[0] - a[0], b[1] - a[1]
        px, py = point[0] - a[0], point[1] - a[1]
        if any(numeric_validity(v) != "FINITE" for v in (dx, dy, px, py)):
            return refuse("NON_FINITE_DERIVED_VALUE")
        length = math.hypot(dx, dy)
        if length == 0:
            return refuse("ZERO_LENGTH_SEGMENT", "DEGENERATE")
        if length <= tolerance.segment_length:
            return refuse("DEGENERATE_GEOMETRY", "DEGENERATE")
        length_sq = math.fsum((dx * dx, dy * dy))
        if numeric_validity(length_sq) != "FINITE":
            return refuse("NON_FINITE_DERIVED_VALUE")
        if length_sq == 0:  # Underflow even with a caller's smaller tolerance.
            return refuse("DEGENERATE_GEOMETRY", "DEGENERATE")
        numerator = math.fsum((px * dx, py * dy))
        if numeric_validity(numerator) != "FINITE":
            return refuse("NON_FINITE_DERIVED_VALUE")
        raw_t = numerator / length_sq
        if numeric_validity(raw_t) != "FINITE":
            return refuse("NON_FINITE_DERIVED_VALUE")
        t = max(0.0, min(1.0, raw_t))
        foot = (a[0] + t * dx, a[1] + t * dy)
        distance = math.dist(point, foot)
        along = t * length
        if any(numeric_validity(v) != "FINITE" for v in (*foot, distance, along, length)):
            return refuse("NON_FINITE_DERIVED_VALUE")
    except (ArithmeticError, ValueError):
        return refuse("NUMERIC_DERIVATION_FAILED")
    result.update(state="ESTABLISHED", point=list(foot), parameter=t,
                  raw_parameter=raw_t, distance=distance, distance_along=along, length=length,
                  premises={"point": list(point), "segment": [list(a), list(b)]})
    return result


def _distance_point_to_segment(point, a, b):
    """Compatibility for compiler callers already in one local Euclidean chart."""
    result = project_point_to_segment(point, a, b, point_space="LOCAL_CARTESIAN",
        segment_space="LOCAL_CARTESIAN", point_plane="local", segment_plane="local",
        geometry_level="EUCLIDEAN")
    if result["state"] != "ESTABLISHED":
        raise SpatialCompilationError("Segment projection refused: " + result["error"], diagnostic=result)
    return result["distance"], result["distance_along"]


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
        # Native vector/text extraction supplies coordinates in one page frame.
        # Unknown or explicitly weakened source premises cannot gain export eligibility.
        native = (document.get("schema_version") == "pdf_geometry_semantics_v1"
                  and plan.get("coordinate_system") == "top_left_origin_y_down")
        geometry_context = {"coordinate_space": "PDF_USER_POINTS",
            "plane_id": "source-page:%s" % plan["page_number"], "geometry_level": "PROJECTIVE",
            "read_certainty": plan.get("read_certainty", "RECOVERED" if native else "UNRESOLVED"),
            "bind_certainty": plan.get("bind_certainty", "RECOVERED" if native else "UNRESOLVED"),
            "bind_basis": "structural", "provenance": document.get("source", {}),
            "contested": plan.get("contested", False),
            "unresolved_counterevidence": plan.get("unresolved_counterevidence", False)}
        from services import binding
        for vector in plan["vectors"]:
            for component in ("read_certainty", "bind_certainty"):
                geometry_context[component] = binding.weaker(geometry_context[component],
                    vector.get(component, geometry_context[component]))
            geometry_context["contested"] |= bool(vector.get("contested"))
            geometry_context["unresolved_counterevidence"] |= bool(vector.get("unresolved_counterevidence"))
        for index, loop in enumerate(loops):
            inside = []
            for label_index, (name, point) in enumerate(labels):
                plane = "source-page:%s" % plan["page_number"]
                relation = classify_point_in_polygon(point, loop,
                    point_space="PDF_USER_POINTS", polygon_space="PDF_USER_POINTS",
                    point_plane=plane, polygon_plane=plane, geometry_level="PROJECTIVE")
                label_certainty = geometry_context["read_certainty"]
                label_binding = geometry_context["bind_certainty"]
                label_contested = geometry_context["contested"]
                label_unresolved_counter = geometry_context["unresolved_counterevidence"]
                for span in plan["text"]:
                    if span["content"].strip() == name:
                        label_certainty = binding.weaker(label_certainty, span.get("read_certainty", label_certainty))
                        label_binding = binding.weaker(label_binding, span.get("bind_certainty", label_binding))
                        label_contested |= bool(span.get("contested"))
                        label_unresolved_counter |= bool(span.get("unresolved_counterevidence"))
                label_containment.append({"label": name, "label_occurrence": label_index,
                    "space_id": "SPACE-%02d" % (index + 1), "source": document.get("source", {}),
                    "read_certainty": label_certainty,
                    "bind_certainty": label_binding, "bind_basis": "structural",
                    "contested": label_contested,
                    "unresolved_counterevidence": label_unresolved_counter,
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
                "geometry_context": dict(geometry_context),
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
        from engine.ifc_volume_validator import numeric_validity
        if any(numeric_validity(v) != "FINITE" for v in (width, max_distance)) or width <= 0 or max_distance < 0:
            raise SpatialCompilationError("Invalid wall placement parameters",
                diagnostic={"state": "UNRESOLVED", "error": "INVALID_GEOMETRIC_NUMBER"})
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
        shift = abs(offset - ideal)
        if any(numeric_validity(v) != "FINITE" for v in (length, ideal, offset, shift)):
            raise SpatialCompilationError("Wall placement refused",
                diagnostic={"state": "UNRESOLVED", "error": "NON_FINITE_DERIVED_VALUE",
                            "wall_id": best.get("id")})
        return best, offset, shift


def compile_to_ifc(document, *, schedule=None, project_name="ARCHIOSK Compiled Model",
                   compiler=None, store=None, workspace=None, evidence_ids=()):
    """Full metabolic bridge: 2D primitives -> model -> IFC 4x3 STEP text."""
    from engine.ifc_volume_validator import IFCVolumeValidator

    model = (compiler or SpatialCompiler()).compile(
        document, schedule=schedule, project_name=project_name)
    return model, IFCVolumeValidator().validate_and_export(model, store=store, workspace=workspace, evidence_ids=evidence_ids)
