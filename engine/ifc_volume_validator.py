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


class IFCVolumeValidator:
    """Validate parametric spaces/walls and emit a minimal IFC4X3 STEP file."""

    def validate(self, model: dict[str, Any]) -> None:
        if not isinstance(model, dict) or not isinstance(model.get("project_name"), str):
            raise IFCValidationError("project_name must be a string")
        levels = {level.get("name") for level in model.get("levels", [])}
        for space in model.get("spaces", []):
            polygon = [_point(p) for p in space.get("boundary_polygon_2d", [])]
            if len(polygon) < 4 or not _close(polygon[0], polygon[-1]):
                raise IFCValidationError(f"space {space.get('id')} boundary polygon must be closed")
            if float(space.get("height", 0)) <= 0:
                raise IFCValidationError(f"space {space.get('id')} extrusion height must be positive")
            if space.get("level") not in levels:
                raise IFCValidationError(f"space {space.get('id')} references unknown level")
            edges = list(zip(polygon, polygon[1:]))
            for i, edge in enumerate(edges):
                for j, other in enumerate(edges):
                    if j <= i or j in (i - 1, i + 1) or (i == 0 and j == len(edges) - 1):
                        continue
                    if _segments_intersect(*edge, *other):
                        raise IFCValidationError(f"space {space.get('id')} boundary polygon self-intersects")
        for wall in model.get("walls", []):
            baseline = [_point(p) for p in wall.get("baseline", [])]
            if len(baseline) != 2:
                raise IFCValidationError(f"wall {wall.get('id')} baseline must have two points")
            length = math.dist(*baseline)
            height = float(wall.get("height", 0))
            if length <= 0 or height <= 0 or float(wall.get("thickness", 0)) <= 0:
                raise IFCValidationError(f"wall {wall.get('id')} dimensions must be positive")
            for opening in wall.get("openings", []):
                offset, width, opening_height = (float(opening.get(k, 0)) for k in ("offset", "width", "height"))
                if offset < 0 or width <= 0 or offset + width > length + 1e-9:
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
