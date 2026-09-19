"""Shared evaluation adapters to the existing geometry owners.

The fixture qualifier and protected evaluation surface use the same adapter.
The candidate is an explicitly controlled evaluation input, never project data.
No expected result, fixture assertion, or new mathematical operator lives here.
"""
import copy
import json
from pathlib import Path

DIRECTORY = Path(__file__).resolve().parents[1] / "tests/fixtures/rule7"

def evaluation_controls():
    """Versioned controlled inputs; expected outcomes are never executed here."""
    suite=json.loads((DIRECTORY / "rule7_fixture_map.v1.json").read_text(encoding="utf-8"))
    return {item["fixture_id"]: {"inputs":item["inputs"],"category":item["category"]} for item in suite["fixtures"]}

class QualificationFailure(AssertionError):
    def __init__(self, message, observations=None):
        super().__init__(message)
        self.observations = observations or {}

def decode(value):
    if isinstance(value, str) and value in ("NaN", "+Infinity", "-Infinity"):
        return float({"NaN": "nan", "+Infinity": "inf", "-Infinity": "-inf"}[value])
    if isinstance(value, list):
        return [decode(v) for v in value]
    if isinstance(value, dict):
        return {k: decode(v) for k, v in value.items()}
    return value


# These are absent mathematical capabilities, not failed adapters. Keep this
# explicit and narrow: an unknown kind still fails qualification.
MISSING_OPERATORS = {}


class MissingOperator(QualificationFailure):
    pass


def candidate_for(inputs):
    """Put source inputs in the existing IFC candidate, in their declared chart."""
    model = json.loads((DIRECTORY / "ifc_candidate.v1.json").read_text())
    kind, value = inputs["kind"], decode(inputs["value"])
    context = {key: inputs[key] for key in ("coordinate_space", "plane_id", "geometry_level",
                                            "read_certainty", "bind_certainty", "provenance")}
    for owner in model["spaces"] + model["walls"]:
        owner["geometry_context"] = dict(context)
    model["label_containment"][0]["relation"].update(
        coordinate_space=inputs["coordinate_space"], plane_id=inputs["plane_id"])
    field = {"weak_binding": "height", "contested": "height", "stale": "height",
             "unbound": "height", "zero_area": "polygon", "homography": "point"}.get(kind, kind)
    owner = model["spaces"][0] if field in ("height", "polygon") else model["walls"][0]
    if field in ("height", "thickness"):
        owner[field] = value
    elif field in ("point", "endpoint") and kind != "homography":
        owner["baseline"][0 if field == "point" else 1] = dict(zip(("x", "y"), value))
    elif field == "polygon":
        owner["boundary_polygon_2d"] = [dict(zip(("x", "y"), point)) for point in value]
    elif field in ("projection", "wall"):
        owner["baseline"] = [dict(zip(("x", "y"), value[key])) for key in ("a", "b")]
        # Declared fixture opening, not a clamped dimension or measured width.
        owner["openings"][0].update(width=value.get("width", 2), offset=0)
    if kind == "unbound":
        model["label_containment"] = []
    return model, owner, field


def run_validator(inputs, *, store=None, workspace=None, source_evidence=None, model=None):
    from engine.ifc_volume_validator import numeric_validity, polygon_region, _semantic_binding_established
    from engine.spatial_compiler import project_point_to_segment, SpatialCompiler, SpatialCompilationError
    from services import binding
    kind, value = inputs["kind"], decode(inputs["value"])
    if kind in MISSING_OPERATORS:
        raise MissingOperator(MISSING_OPERATORS[kind])
    record = {k: copy.deepcopy(inputs[k]) for k in ("coordinate_space", "provenance", "read_certainty", "bind_certainty")}
    def finish(state, output, errors, derivation=None):
        record.update(state=state, value=output, errors=errors,
            derivation=derivation or {"operator": "numeric_validity@1", "operator_version": "1",
                "tolerance_context": {"policy": "strict_finiteness", "tolerance": None}})
        return record
    if kind == "homography":
        from engine.spatial_compiler import validate_homography, transform_homogeneous_point
        # These map controls declare a same-chart/same-plane transformation.
        # Cross-chart operator controls supply both endpoints explicitly.
        transform = validate_homography(value["matrix"], source_space=inputs["coordinate_space"],
            target_space=inputs["coordinate_space"], source_plane=inputs["plane_id"],
            target_plane=inputs["plane_id"], geometry_level=inputs["geometry_level"],
            uncertainty=inputs.get("uncertainty"), source=inputs["provenance"])
        result = transform_homogeneous_point(transform, value["point"],
            point_space=inputs["coordinate_space"], point_plane=inputs["plane_id"])
        return finish(result["state"], result["value"], [result["error"]] if result["error"] else [], result)
    if kind in ("vector", "domain"):
        from engine.spatial_compiler import vector_usability, bounded_acos
        operation = vector_usability if kind == "vector" else bounded_acos
        arguments = (value,) if kind == "vector" else (value["value"], value["error_bound"])
        if kind == "domain" and value.get("operation") != "acos":
            raise QualificationFailure("UNWIRED_DOMAIN_OPERATION")
        result = operation(*arguments, source_space=inputs["coordinate_space"],
            target_space=inputs["coordinate_space"], source_plane=inputs["plane_id"],
            target_plane=inputs["plane_id"], geometry_level=inputs["geometry_level"],
            source=inputs["provenance"], uncertainty=inputs.get("uncertainty"))
        return finish(result["state"], result["value"], [result["error"]] if result["error"] else [], result)
    if kind in ("height", "thickness", "weak_binding", "contested", "stale", "unbound"):
        state = numeric_validity(value)
        if state != "FINITE":
            return finish(state, None, ["NON_FINITE_DIMENSION"])
        if binding.bound_certainty(inputs) != "RECOVERED":
            return finish("PARTIALLY_RECOVERED", None, ["PREMISE_UNESTABLISHED"])
        trust = store.explain_evidence_trust(workspace, source_evidence["id"])
        if trust["confirmed_counterevidence"]:
            return finish("CONTESTED", None, ["EVIDENCE_CONFLICT"])
        if trust["currentness"]["status"] != "current":
            return finish("UNRESOLVED", None, ["STALE_EVIDENCE"])
        if not _semantic_binding_established(model, model["spaces"][0]):
            return finish("UNRESOLVED", None, ["SEMANTIC_BINDING_UNRESOLVED"],
                          {"operator": "semantic_binding@1", "operator_version": "1"})
        return finish("FINITE", value, [])
    if kind in ("point", "endpoint", "polygon", "zero_area"):
        points = value if kind in ("polygon", "zero_area") else [value]
        states = [numeric_validity(v) for point in points for v in point]
        if any(state != "FINITE" for state in states):
            code = {"point": "NON_FINITE_POINT", "endpoint": "NON_FINITE_SEGMENT",
                    "polygon": "NON_FINITE_POLYGON", "zero_area": "NON_FINITE_POLYGON"}[kind]
            return finish("NON_FINITE" if "NON_FINITE" in states else "UNRESOLVED", None, [code])
        if kind in ("polygon", "zero_area"):
            region = polygon_region(model["spaces"][0])
            if region["state"] != "VALID_REGION":
                return finish("DEGENERATE", None, ["DEGENERATE_GEOMETRY"], region)
            return finish("ESTABLISHED", value, [], region)
        return finish("FINITE", value, [])
    if kind == "projection":
        result = project_point_to_segment(value["point"], value["a"], value["b"],
            point_space=inputs["coordinate_space"], segment_space=value.get("segment_space", inputs["coordinate_space"]),
            point_plane=inputs["plane_id"], segment_plane=value.get("segment_plane", inputs["plane_id"]),
            geometry_level=inputs["geometry_level"], source=inputs["provenance"])
        error = {"INCOMPARABLE_COORDINATE_SPACES": "SPACE_MISMATCH"}.get(result["error"], result["error"])
        return finish(result["state"], result["point"], [error] if error else [], result)
    if kind == "wall":
        try:
            host, offset, shift = SpatialCompiler._host_wall(value["point"], model["walls"], value["width"])
        except SpatialCompilationError as error:
            diagnostic = error.diagnostic
            return finish(diagnostic["state"], None, [diagnostic["error"]], diagnostic)
        return finish("ESTABLISHED" if host else "UNRESOLVED", [offset, shift] if host else None,
                      [] if host else ["PREMISE_UNESTABLISHED"],
                      {"operator": "wall_host@1", "premises": {"point": value["point"], "segment": [value["a"], value["b"]]}})
    raise QualificationFailure("UNWIRED_VALIDATOR: " + kind)


