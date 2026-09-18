"""Small, headless validator/exporter for parametric IFC 4x3 volumes.

The writer deliberately emits only the entities needed by this contract. It
does not attempt to be a general CAD kernel; validation is performed before
any STEP text is produced.
"""
from __future__ import annotations

import math
from typing import Any


class IFCValidationError(ValueError):
    """Raised when a supplied volume cannot be represented safely."""

    def __init__(self, message, *, diagnostic=None):
        super().__init__(message)
        self.diagnostic = diagnostic


def numeric_validity(value):
    """Strict geometric scalar admission, without coercion or replacement."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "UNRESOLVED"
    try:
        return "FINITE" if math.isfinite(value) else "NON_FINITE"
    except OverflowError:
        # A mathematical integer may be finite but unusable in this float engine.
        return "UNRESOLVED"


def _require_finite(value, field, *, source=None, stage="input"):
    state = numeric_validity(value)
    if state != "FINITE":
        diagnostic = {"state": "UNRESOLVED", "numeric_state": state,
                      "code": "INVALID_GEOMETRIC_NUMBER", "field": field,
                      "stage": stage, "source": source or {}}
        # Never describe the invalid token as a measured quantity or mutate it.
        raise IFCValidationError(f"Invalid geometry: {state} at {field} ({stage})",
                                 diagnostic=diagnostic)
    return value


def _numeric_inputs(model):
    """One admission boundary for every numeric field used by IFC geometry."""
    source = model.get("source", {})
    def scalar(row, key, path):
        _require_finite(row.get(key) if isinstance(row, dict) else None, path + "." + key, source=source)
    def points(rows, path):
        if not isinstance(rows, (list, tuple)):
            _require_finite(None, path, source=source)
        for i, point in enumerate(rows):
            for key in ("x", "y"):
                scalar(point, key, f"{path}[{i}]")
    for i, level in enumerate(model.get("levels", [])):
        scalar(level, "elevation", f"levels[{i}]")
        for key in ("label_elevation_feet", "measured_elevation_feet"):
            if level.get(key) is not None:
                scalar(level, key, f"levels[{i}]")
    derived = model.get("derived") or {}
    for key in ("points_per_foot", "declared_points_per_foot", "storey_height_points", "door_head_height_points"):
        if derived.get(key) is not None:
            scalar(derived, key, "derived")
    for i, space in enumerate(model.get("spaces", [])):
        scalar(space, "height", f"spaces[{i}]")
        points(space.get("boundary_polygon_2d", []), f"spaces[{i}].boundary_polygon_2d")
    for i, wall in enumerate(model.get("walls", [])):
        path = f"walls[{i}]"
        for key in ("height", "thickness"):
            scalar(wall, key, path)
        points(wall.get("baseline", []), path + ".baseline")
        for j, opening in enumerate(wall.get("openings", [])):
            for key in ("offset", "width", "height"):
                scalar(opening, key, f"{path}.openings[{j}]")
    for i, evidence in enumerate(model.get("label_containment", [])):
        for j, value in enumerate((evidence.get("relation") or {}).get("point") or []):
            _require_finite(value, f"label_containment[{i}].point[{j}]", source=source)


def _numeric_derivation(operation, field, source):
    """Arithmetic/domain failure is a refusal with provenance, never a fallback."""
    try:
        return operation()
    except (ArithmeticError, ValueError) as error:
        raise IFCValidationError(f"Invalid geometry: unresolved numeric derivation at {field}",
            diagnostic={"state": "UNRESOLVED", "numeric_state": "UNRESOLVED",
                        "code": "NUMERIC_DERIVATION_FAILED", "field": field,
                        "stage": "derived", "source": source or {}}) from error


def _point(p: dict[str, Any]) -> tuple[float, float]:
    return float(p["x"]), float(p["y"])


def _close(a, b, eps=1e-9):
    return abs(a[0] - b[0]) <= eps and abs(a[1] - b[1]) <= eps


def _cross(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_intersect(a, b, c, d):
    def orient(p, q, r):
        value = _cross(p, q, r)
        return (value > 1e-9) - (value < -1e-9)

    def on_segment(p, q, r):
        return (min(p[0], r[0]) - 1e-9 <= q[0] <= max(p[0], r[0]) + 1e-9
                and min(p[1], r[1]) - 1e-9 <= q[1] <= max(p[1], r[1]) + 1e-9)

    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return True
    return ((o1 == 0 and on_segment(a, c, b)) or (o2 == 0 and on_segment(a, d, b))
            or (o3 == 0 and on_segment(c, a, d)) or (o4 == 0 and on_segment(c, b, d)))


class _Step:
    def __init__(self):
        self.entities: list[tuple[int, str, tuple[Any, ...]]] = []

    def add(self, kind: str, *args: Any) -> int:
        def check(value, path):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                _require_finite(value, path, stage="STEP emission")
            elif isinstance(value, (tuple, list)):
                for index, child in enumerate(value):
                    check(child, f"{path}[{index}]")
        check(args, kind)
        ident = len(self.entities) + 1
        self.entities.append((ident, kind, args))
        return ident

    def ref(self, ident: int) -> str:
        return f"#{ident}"

    @staticmethod
    def value(value: Any) -> str:
        if value is None:
            return "$"
        if isinstance(value, bool):
            return ".T." if value else ".F."
        if isinstance(value, str):
            if value.startswith("#") or (value.startswith(".") and value.endswith(".")):
                return value
            return "'" + value.replace("'", "''") + "'"
        if isinstance(value, (tuple, list)):
            return "(" + ",".join(_Step.value(v) for v in value) + ")"
        return str(value)

    def render(self, project_name: str) -> str:
        lines = ["ISO-10303-21;", "HEADER;",
                 "FILE_DESCRIPTION(('ARCHIOSK IFC volume export'),'2;1');",
                 "FILE_NAME('archiosk.ifc','2026-01-01T00:00:00',('ARCHIOSK'),('ARCHIOSK'),'ARCHIOSK IFC exporter','ARCHIOSK','');",
                 "FILE_SCHEMA(('IFC4X3'));", "ENDSEC;", "DATA;"]
        for ident, kind, args in self.entities:
            lines.append(f"#{ident}={kind}(" + ",".join(self.value(a) for a in args) + ");")
        lines.extend(["ENDSEC;", "END-ISO-10303-21;"])
        return "\n".join(lines) + "\n"


class PDFVolumeValidator:  # compatibility alias is intentionally not exported
    pass


def polygon_region(space, *, tolerance=None):
    """Classify, without repairing, an explicitly closed same-plane polygon.

    Reuse compiler boundary validation and its centralized chart tolerance.
    A valid region establishes geometry only, never a semantic space identity.
    """
    from engine.spatial_compiler import ToleranceContext, classify_point_in_polygon, signed_area
    from services import binding, deterministic_spatial
    tolerance = ToleranceContext() if tolerance is None else tolerance
    context = space.get("geometry_context") or {}
    result = {"state": "UNRESOLVED", "operator": "polygon_region@1", "context": context,
              "signed_area": None, "absolute_area": None, "area_tolerance": None,
              "distance_tolerance": tolerance.boundary_distance, "error": None}
    def finish(state, error=None):
        result.update(state=state, error=error)
        return result
    if (binding.bound_certainty(context) != "RECOVERED" or not context.get("provenance")
            or context.get("contested") or context.get("unresolved_counterevidence")):
        return finish("UNRESOLVED", "PREMISE_UNESTABLISHED")
    raw = space.get("boundary_polygon_2d")
    if not isinstance(raw, list) or any(not isinstance(p, dict) for p in raw):
        return finish("UNRESOLVED", "INVALID_GEOMETRY")
    if not context.get("coordinate_space") or not context.get("plane_id"):
        return finish("UNRESOLVED", "PREMISE_UNESTABLISHED")
    for p in raw:
        if any(p.get(k, context.get(k)) != "RECOVERED" for k in ("read_certainty", "bind_certainty")):
            return finish("UNRESOLVED", "PREMISE_UNESTABLISHED")
        if p.get("coordinate_space", context["coordinate_space"]) != context["coordinate_space"]:
            return finish("UNRESOLVED", "INCOMPARABLE_COORDINATE_SPACES")
        if p.get("plane_id", context["plane_id"]) != context["plane_id"]:
            return finish("UNRESOLVED", "PLANE_MISMATCH")
    if any(not all(isinstance(p.get(k), (int, float)) and not isinstance(p.get(k), bool)
                   and math.isfinite(p[k]) for k in ("x", "y")) for p in raw):
        return finish("UNRESOLVED", "INVALID_GEOMETRY")
    polygon = [(p["x"], p["y"]) for p in raw]
    if len(set(polygon)) < 3:
        return finish("INSUFFICIENT_VERTICES")
    if polygon[0] != polygon[-1]:
        return finish("UNRESOLVED", "POLYGON_NOT_CLOSED")
    ring = polygon[:-1]
    if len(set(ring)) != len(ring):
        return finish("DEGENERATE", "DUPLICATE_VERTEX")
    # Reuse the boundary classifier for chart/level/tolerance and simple-region checks.
    check = classify_point_in_polygon(ring[0], polygon,
        point_space=context["coordinate_space"], polygon_space=context["coordinate_space"],
        point_plane=context["plane_id"], polygon_plane=context["plane_id"],
        geometry_level=context.get("geometry_level"), tolerance=tolerance)
    if check["error"] not in (None, "DEGENERATE_POLYGON"):
        return finish("UNRESOLVED", check["error"])
    edges = list(zip(ring, ring[1:] + ring[:1]))
    band = tolerance.boundary_distance
    origin = ring[0]
    relative = [(x - origin[0], y - origin[1]) for x, y in ring]
    area = signed_area(relative)
    perimeter = sum(math.dist(a, b) for a, b in edges)
    result.update(signed_area=area, absolute_area=abs(area), area_tolerance=band * perimeter)
    if not math.isfinite(area) or not math.isfinite(perimeter):
        return finish("UNRESOLVED", "NUMERICAL_DEGENERACY")
    far = max(ring, key=lambda p: math.dist(origin, p))
    baseline = math.dist(origin, far)
    if baseline <= band or any(math.dist(a, b) <= band for a, b in edges):
        return finish("DEGENERATE", "ZERO_EXTENT_OR_EDGE")
    if all(abs(signed_area([(0, 0), (far[0] - origin[0], far[1] - origin[1]), p])) * 2
           <= band * baseline for p in relative):
        return finish("COLLINEAR")
    for i, edge in enumerate(edges):
        for j in range(i + 1, len(edges)):
            if j == i + 1 or (i == 0 and j == len(edges) - 1):
                continue
            if deterministic_spatial._segments_cross(*edge, *edges[j]):
                return finish("SELF_INTERSECTING")
    if area == 0:
        return finish("ZERO_AREA")
    if abs(area) <= result["area_tolerance"] or check["state"] != "ON_BOUNDARY":
        return finish("DEGENERATE")
    return finish("VALID_REGION")


def _semantic_binding_established(model, space):
    """Recompute strict label binding from retained occurrence evidence."""
    from engine.spatial_compiler import classify_point_in_polygon
    from services import binding
    context = space["geometry_context"]
    polygon = [_point(p) for p in space["boundary_polygon_2d"]]
    inside = []
    for evidence in model.get("label_containment", []):
        if evidence.get("space_id") != space.get("id"):
            continue
        if (not model.get("source") or evidence.get("source") != model["source"]
                or binding.bound_certainty(evidence) != "RECOVERED"
                or evidence.get("contested") or evidence.get("unresolved_counterevidence")):
            return False
        relation = evidence.get("relation") or {}
        check = classify_point_in_polygon(relation.get("point"), polygon,
            point_space=relation.get("coordinate_space"), polygon_space=context["coordinate_space"],
            point_plane=relation.get("plane_id"), polygon_plane=context["plane_id"],
            geometry_level=context.get("geometry_level"))
        if check["state"] in ("ON_BOUNDARY", "UNRESOLVED"):
            return False
        if check["state"] == "INSIDE":
            inside.append(evidence.get("label"))
    return len(inside) == 1 and bool(inside[0]) and inside[0] == space.get("name")


class IFCVolumeValidator:
    """Validate parametric spaces/walls and emit a minimal IFC4X3 STEP file."""

    def export_evidence(self, model, store, workspace, evidence_item_id):
        """Apply one scoped, governed result, then use the existing IFC gate.

        This adapter is for evidence-backed callers. Trust is re-read here;
        neither a caller's cached approval nor EvidenceItem storage authorizes
        export. The supplied candidate is copied, never repaired in place.
        """
        import copy
        from engine.spatial_compiler import SpatialCompiler, SpatialCompilationError

        governed = store.project_geometry_evidence(workspace, evidence_item_id)
        record = governed["record"]
        def refuse(errors, state=None):
            codes = set(errors)
            if codes & {"EVIDENCE_CONFLICT", "STALE_EVIDENCE"}:
                export_state = "IFC_BLOCKED_EVIDENCE"
            elif codes & {"SPACE_MISMATCH", "PLANE_MISMATCH"}:
                export_state = "IFC_BLOCKED_COORDINATE_SPACE"
            elif codes & {"NON_FINITE_DIMENSION", "NON_FINITE_POINT", "NON_FINITE_SEGMENT", "NON_FINITE_POLYGON"}:
                export_state = "IFC_BLOCKED_NON_FINITE"
            elif codes & {"ZERO_LENGTH_SEGMENT", "DEGENERATE_GEOMETRY", "HOMOGRAPHY_SINGULAR",
                          "HOMOGRAPHY_ILL_CONDITIONED", "DEHOMOGENIZATION_UNSTABLE"}:
                export_state = "IFC_BLOCKED_DEGENERATE_GEOMETRY"
            elif codes & {"SEMANTIC_BINDING_UNRESOLVED", "PREMISE_UNESTABLISHED"}:
                export_state = "IFC_BLOCKED_SEMANTIC_BINDING"
            else:
                export_state = "IFC_BLOCKED_EVIDENCE"
            raise IFCValidationError("Scoped geometry evidence does not authorize IFC export",
                diagnostic={"state": state or governed["state"], "errors": list(errors),
                            "export_state": export_state, "evidence_item_id": evidence_item_id})
        if governed["state"] == "WEAK" and not governed["errors"]:
            raise IFCValidationError("Conditional geometry is not an established IFC measurement",
                diagnostic={"state": "WEAK", "errors": [], "export_state": "IFC_UNRESOLVED",
                            "evidence_item_id": evidence_item_id})
        if governed["state"] not in ("FINITE", "ESTABLISHED") or governed["errors"]:
            refuse(governed["errors"] or ["PREMISE_UNESTABLISHED"])
        derivation = record.get("derivation") or {}
        if (derivation.get("operator") == "homography_point@1"
                and derivation.get("geometry_level") not in ("EUCLIDEAN", "METRIC_SCALED")):
            refuse(["PREMISE_UNESTABLISHED"])
        candidate = copy.deepcopy(model)
        field = record.get("field")
        owners = [row for row in candidate.get("spaces", []) + candidate.get("walls", [])
                  if row.get("id") == record.get("object_id")]
        if len(owners) != 1:
            refuse(["SEMANTIC_BINDING_UNRESOLVED"])
        owner = owners[0]
        context = owner.get("geometry_context") or {}
        if context.get("coordinate_space") != record.get("coordinate_space"):
            refuse(["SPACE_MISMATCH"])
        if context.get("plane_id") != record.get("plane_id"):
            refuse(["PLANE_MISMATCH"])
        value = governed["value"]
        if field in ("height", "thickness"):
            owner[field] = value
        elif field in ("point", "endpoint"):
            owner["baseline"][0 if field == "point" else 1] = dict(zip(("x", "y"), value))
        elif field == "polygon":
            owner["boundary_polygon_2d"] = [dict(zip(("x", "y"), point)) for point in value]
        elif field in ("projection", "wall"):
            premises = (record.get("derivation") or {}).get("premises") or {}
            baseline = [[p["x"], p["y"]] for p in owner.get("baseline", [])]
            if baseline != premises.get("segment") or not owner.get("openings"):
                refuse(["PREMISE_UNESTABLISHED"])
            try:
                host, offset, shift = SpatialCompiler._host_wall(
                    premises["point"], [owner], owner["openings"][0]["width"])
            except SpatialCompilationError as error:
                refuse([(error.diagnostic or {}).get("error", "PREMISE_UNESTABLISHED")])
            if host is None:
                refuse(["PREMISE_UNESTABLISHED"])
            owner["openings"][0]["offset"] = offset
        else:
            refuse(["PREMISE_UNESTABLISHED"])
        return self.export(candidate)

    def validate(self, model: dict[str, Any]) -> None:
        if not isinstance(model, dict) or not isinstance(model.get("project_name"), str):
            raise IFCValidationError("project_name must be a string")
        _numeric_inputs(model)
        source = model.get("source", {})
        levels = {level.get("name") for level in model.get("levels", [])}
        for space in model.get("spaces", []):
            region = _numeric_derivation(lambda: polygon_region(space),
                f"space {space.get('id')} polygon", source)
            for quantity in ("signed_area", "absolute_area", "area_tolerance"):
                if region.get(quantity) is not None:
                    _require_finite(region[quantity], f"space {space.get('id')} {quantity}",
                                    source=source, stage="derived")
            if region["state"] != "VALID_REGION":
                raise IFCValidationError(f"space {space.get('id')} boundary must be a valid closed region: {region['state']} / {region['error']}")
            if not _numeric_derivation(lambda: _semantic_binding_established(model, space),
                                       f"space {space.get('id')} semantic containment", source):
                raise IFCValidationError(f"space {space.get('id')} semantic binding UNRESOLVED")
            if float(space.get("height", 0)) <= 0:
                raise IFCValidationError(f"space {space.get('id')} extrusion height must be positive")
            if space.get("level") not in levels:
                raise IFCValidationError(f"space {space.get('id')} references unknown level")
        for wall in model.get("walls", []):
            baseline = [_point(p) for p in wall.get("baseline", [])]
            if len(baseline) != 2:
                raise IFCValidationError(f"wall {wall.get('id')} baseline must have two points")
            length = math.dist(*baseline)
            _require_finite(length, f"wall {wall.get('id')} derived length", source=source, stage="derived")
            height = float(wall.get("height", 0))
            if length <= 0 or height <= 0 or float(wall.get("thickness", 0)) <= 0:
                raise IFCValidationError(f"wall {wall.get('id')} dimensions must be positive")
            for opening in wall.get("openings", []):
                offset, width, opening_height = (float(opening.get(k, 0)) for k in ("offset", "width", "height"))
                extent = _require_finite(offset + width, f"opening {opening.get('id')} derived extent",
                                         source=source, stage="derived")
                if offset < 0 or width <= 0 or extent > length + 1e-9:
                    raise IFCValidationError(f"opening {opening.get('id')} exceeds wall length bounds")
                if opening_height <= 0 or opening_height > height + 1e-9:
                    raise IFCValidationError(f"opening {opening.get('id')} exceeds wall height bounds")

    def export(self, model: dict[str, Any]) -> str:
        self.validate(model)
        step = _Step()
        origin = step.add("IFCCARTESIANPOINT", ((0.0, 0.0, 0.0),))
        axis = step.add("IFCDIRECTION", ((0.0, 0.0, 1.0),))
        ref = step.add("IFCDIRECTION", ((1.0, 0.0, 0.0),))
        placement = step.add("IFCAXIS2PLACEMENT3D", (step.ref(origin), step.ref(axis), step.ref(ref)))
        context = step.add("IFCGEOMETRICREPRESENTATIONCONTEXT", "Model", 3, 1e-5, step.ref(origin), step.ref(axis), step.ref(ref))
        units = step.add("IFCUNITASSIGNMENT", ())
        project = step.add("IFCPROJECT", "ARCHIOSK-PROJECT", None, model["project_name"], None, None, None, (step.ref(context),), step.ref(units))
        site = step.add("IFCSITE", "ARCHIOSK-SITE", None, model["project_name"] + " Site", None, None, None, None, None, None, None, None, None, None)
        building = step.add("IFCBUILDING", "ARCHIOSK-BUILDING", None, model["project_name"], None, None, None, None, None, None, None, None, None, None)
        level_entities = {}
        for level in model.get("levels", []):
            level_entities[level["name"]] = step.add("IFCBUILDINGSTOREY", level["name"], None, level["name"], None, None, None, None, float(level["elevation"]))
        step.add("IFCRELAGGREGATES", "REL-PROJECT-SITE", None, None, step.ref(project), (step.ref(site),))
        step.add("IFCRELAGGREGATES", "REL-SITE-BUILDING", None, None, step.ref(site), (step.ref(building),))
        step.add("IFCRELAGGREGATES", "REL-BUILDING-LEVELS", None, None, step.ref(building), tuple(step.ref(v) for v in level_entities.values()))
        for space in model.get("spaces", []):
            points = [_point(p) for p in space["boundary_polygon_2d"][:-1]]
            point_refs = tuple(step.ref(step.add("IFCCARTESIANPOINT", ((x, y, 0.0),))) for x, y in points)
            polyline = step.add("IFCPOLYLINE", (point_refs + (point_refs[0],)))
            profile = step.add("IFCARBITRARYCLOSEDPROFILEDEF", ".AREA.", None, step.ref(polyline))
            solid = step.add("IFCEXTRUDEDAREASOLID", step.ref(profile), step.ref(placement), step.ref(axis), float(space["height"]))
            shape = step.add("IFCSHAPEREPRESENTATION", step.ref(context), "Body", "SweptSolid", (step.ref(solid),))
            representation = step.add("IFCPRODUCTDEFINITIONSHAPE", None, None, (step.ref(shape),))
            entity = step.add("IFCSPACE", space["id"], None, space["name"], None, None, step.ref(placement), step.ref(representation), None, None)
            step.add("IFCRELCONTAINEDINSPATIALSTRUCTURE", "REL-CONTAIN-" + space["id"], None, None, (step.ref(entity),), step.ref(level_entities[space["level"]]))
        for wall in model.get("walls", []):
            a, b = [_point(p) for p in wall["baseline"]]
            length = math.dist((a[0], a[1]), (b[0], b[1]))
            wall_profile = step.add("IFCRECTANGLEPROFILEDEF", ".AREA.", None, float(wall["thickness"]), float(wall["height"]))
            wall_solid = step.add("IFCEXTRUDEDAREASOLID", step.ref(wall_profile), step.ref(placement), step.ref(axis), length)
            wall_shape = step.add("IFCSHAPEREPRESENTATION", step.ref(context), "Body", "SweptSolid", (step.ref(wall_solid),))
            wall_repr = step.add("IFCPRODUCTDEFINITIONSHAPE", None, None, (step.ref(wall_shape),))
            wall_entity = step.add("IFCWALLSTANDARDCASE", wall["id"], None, wall["id"], None, None, step.ref(placement), step.ref(wall_repr), None)
            for opening in wall.get("openings", []):
                op_profile = step.add("IFCRECTANGLEPROFILEDEF", ".AREA.", None, float(opening["width"]), float(opening["height"]))
                op_solid = step.add("IFCEXTRUDEDAREASOLID", step.ref(op_profile), step.ref(placement), step.ref(axis), float(opening["height"]))
                op_shape = step.add("IFCSHAPEREPRESENTATION", step.ref(context), "Body", "SweptSolid", (step.ref(op_solid),))
                op_repr = step.add("IFCPRODUCTDEFINITIONSHAPE", None, None, (step.ref(op_shape),))
                op = step.add("IFCOPENINGELEMENT", opening["id"], None, opening["id"], None, None, step.ref(placement), step.ref(op_repr), None)
                step.add("IFCRELVOIDSELEMENT", "REL-VOID-" + opening["id"], None, None, step.ref(wall_entity), step.ref(op))
        return step.render(model["project_name"])

    def validate_and_export(self, model: dict[str, Any]) -> str:
        return self.export(model)
