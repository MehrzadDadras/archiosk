import re

import pytest

from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator, polygon_region, numeric_validity
from engine.spatial_compiler import ToleranceContext


@pytest.fixture
def room_model():
    return {
        "project_name": "IFC Test Project",
        "source": {"filename": "synthetic-ifc-region", "fixture_version": "2.0.0"},
        "label_containment": [{"label": "ENTRY/LOBBY", "space_id": "SPACE-ENTRY",
            "source": {"filename": "synthetic-ifc-region", "fixture_version": "2.0.0"},
            "read_certainty": "RECOVERED", "bind_certainty": "RECOVERED", "bind_basis": "structural",
            "relation": {"point": [10, 10], "coordinate_space": "PDF_USER_POINTS", "plane_id": "sheet:1"}}],
        "levels": [{"name": "LEVEL 1", "elevation": 0.0}],
        "spaces": [{"id": "SPACE-ENTRY", "name": "ENTRY/LOBBY", "level": "LEVEL 1", "height": 144.0,
                    "geometry_context": {"coordinate_space": "PDF_USER_POINTS", "plane_id": "sheet:1",
                        "geometry_level": "PROJECTIVE", "read_certainty": "RECOVERED",
                        "bind_certainty": "RECOVERED", "bind_basis": "structural", "provenance": "synthetic fixture v2"},
                    "boundary_polygon_2d": [{"x": 0, "y": 0}, {"x": 120, "y": 0}, {"x": 120, "y": 80}, {"x": 0, "y": 80}, {"x": 0, "y": 0}]}],
        "walls": [{"id": "WALL-01", "baseline": [{"x": 0, "y": 0}, {"x": 120, "y": 0}], "thickness": 6.0,
                   "height": 144.0, "openings": [{"id": "DOOR-01", "offset": 30.0, "width": 36.0, "height": 84.0}]}],
    }


def test_room_and_wall_export_to_ifc(room_model):
    text = IFCVolumeValidator().export_numeric_diagnostic(room_model)
    assert text.startswith("ISO-10303-21;")
    assert "IFCPROJECT(" in text and "IFCSPACE(" in text
    assert "IFCWALLSTANDARDCASE(" in text and "IFCOPENINGELEMENT(" in text
    assert "IFCRELVOIDSELEMENT(" in text


def test_step_headers_relationships_and_coordinate_bounds(room_model):
    text = IFCVolumeValidator().export_numeric_diagnostic(room_model)
    assert "FILE_SCHEMA(('IFC4X3'));" in text
    assert "IFCRELAGGREGATES(" in text
    assert "IFCRELCONTAINEDINSPATIALSTRUCTURE(" in text
    assert "0.0" in text and "120.0" in text and "80.0" in text and "144.0" in text
    assert re.search(r"#\d+=IFCCARTESIANPOINT", text)


def test_open_bounds_and_self_intersection_are_rejected(room_model):
    room_model["spaces"][0]["boundary_polygon_2d"].pop()
    with pytest.raises(IFCValidationError, match="closed"):
        IFCVolumeValidator().export_numeric_diagnostic(room_model)


@pytest.mark.parametrize("points,established", [
    ([(0, 0), (120, 0), (0, 80), (0, 0)], True),
    ([(0, 0), (120, 0), (0, 80)], False),
    ([(0, 0), (120, 80), (0, 80), (120, 0), (0, 0)], False),
    ([(0, 0), (60, 0), (120, 0), (0, 0)], False),
])
def test_rule7_closed_chain_must_establish_a_region_before_volume_export(room_model, points, established):
    """Closure alone is insufficient: a collinear loop encloses no region.

    Synthetic same-plane drawing coordinates; the existing export consumer must
    refuse open, self-crossing and zero-area constructions, not emit a volume.
    """
    room_model["spaces"][0]["boundary_polygon_2d"] = [{"x": x, "y": y} for x, y in points]
    if established:
        assert "IFCSPACE(" in IFCVolumeValidator().export_numeric_diagnostic(room_model)
    else:
        with pytest.raises(IFCValidationError):
            IFCVolumeValidator().export_numeric_diagnostic(room_model)


@pytest.mark.parametrize("points,state", [
    ([(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], "VALID_REGION"),
    ([(0, 0), (10, 0), (0, 10), (0, 0)], "VALID_REGION"),
    ([(0, 0), (5, 0), (10, 0), (0, 0)], "COLLINEAR"),
    ([(0, 0), (3, 0), (6, 0), (10, 0), (0, 0)], "COLLINEAR"),
    ([(0, 0), (10, 0), (0, 0)], "INSUFFICIENT_VERTICES"),
    ([(0, 0), (10, 0), (10, 0), (0, 10), (0, 0)], "DEGENERATE"),
    ([(0, 0), (10, 0), (10, 0.0000015), (0, 0.0000015), (0, 0)], "DEGENERATE"),
    ([(0, 0), (10, 10), (0, 10), (10, 0), (0, 0)], "SELF_INTERSECTING"),
])
def test_polygon_states_keep_topology_separate_from_area(room_model, points, state):
    space = room_model["spaces"][0]
    space["boundary_polygon_2d"] = [{"x": x, "y": y} for x, y in points]
    result = polygon_region(space)
    assert result["state"] == state
    assert result["distance_tolerance"] == ToleranceContext().boundary_distance
    if state != "VALID_REGION":
        with pytest.raises(IFCValidationError):
            IFCVolumeValidator().export_numeric_diagnostic(room_model)


@pytest.mark.parametrize("mutation,error", [
    ("space_mismatch", "INCOMPARABLE_COORDINATE_SPACES"),
    ("plane_mismatch", "PLANE_MISMATCH"),
    ("uncertain_geometry", "PREMISE_UNESTABLISHED"),
    ("uncertain_vertex", "PREMISE_UNESTABLISHED"),
    ("contested_geometry", "PREMISE_UNESTABLISHED"),
    ("missing_context", "PREMISE_UNESTABLISHED"),
])
def test_polygon_premises_cannot_be_promoted_by_area(room_model, mutation, error):
    space = room_model["spaces"][0]
    if mutation == "space_mismatch":
        space["boundary_polygon_2d"][1]["coordinate_space"] = "SOURCE_PIXELS"
    elif mutation == "plane_mismatch":
        space["boundary_polygon_2d"][1]["plane_id"] = "sheet:2"
    elif mutation == "uncertain_vertex":
        space["boundary_polygon_2d"][1]["bind_certainty"] = "PARTIALLY_RECOVERED"
    elif mutation == "uncertain_geometry":
        space["geometry_context"]["read_certainty"] = "PARTIALLY_RECOVERED"
    elif mutation == "contested_geometry":
        space["geometry_context"]["contested"] = True
    else:
        space.pop("geometry_context")
    assert polygon_region(space)["error"] == error
    with pytest.raises(IFCValidationError):
        IFCVolumeValidator().export_numeric_diagnostic(room_model)


@pytest.mark.parametrize("mutation", ["name_only", "edge_label", "uncertain_label", "contested_label", "wrong_plane"])
def test_valid_geometry_does_not_establish_semantic_identity(room_model, mutation):
    assert polygon_region(room_model["spaces"][0])["state"] == "VALID_REGION"
    evidence = room_model["label_containment"][0]
    if mutation == "name_only":
        room_model["label_containment"] = []
    elif mutation == "edge_label":
        evidence["relation"].update(point=[0, 10], state="INSIDE")  # cached conclusion cannot win
    elif mutation == "uncertain_label":
        evidence["read_certainty"] = "UNRESOLVED"
    elif mutation == "contested_label":
        evidence["contested"] = True
    else:
        evidence["relation"]["plane_id"] = "sheet:2"
    with pytest.raises(IFCValidationError, match="semantic binding"):
        IFCVolumeValidator().export_numeric_diagnostic(room_model)


@pytest.mark.parametrize("field", ["space_height", "wall_thickness", "wall_endpoint", "wall_height",
    "wall_ax", "wall_ay", "wall_by", "polygon_x", "polygon_y", "level", "opening_width",
    "opening_offset", "opening_height", "label_point", "derived_scale"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_rule7_nonfinite_dimensions_cannot_earn_a_volume(room_model, field, value):
    """Valid planar region + unresolved extrusion does not prove a valid volume."""
    assert polygon_region(room_model["spaces"][0])["state"] == "VALID_REGION"
    if field == "space_height":
        room_model["spaces"][0]["height"] = value
    elif field == "wall_thickness":
        room_model["walls"][0]["thickness"] = value
    elif field == "wall_endpoint":
        room_model["walls"][0]["baseline"][1]["x"] = value
    elif field == "wall_height":
        room_model["walls"][0]["height"] = value
    elif field.startswith("wall_"):
        endpoint, coordinate = field[-2:]
        room_model["walls"][0]["baseline"][0 if endpoint == "a" else 1][coordinate] = value
    elif field.startswith("polygon_"):
        room_model["spaces"][0]["boundary_polygon_2d"][1][field[-1]] = value
    elif field == "level":
        room_model["levels"][0]["elevation"] = value
    elif field.startswith("opening_"):
        room_model["walls"][0]["openings"][0][field.removeprefix("opening_")] = value
    elif field == "label_point":
        room_model["label_containment"][0]["relation"]["point"][0] = value
    else:
        room_model["derived"] = {"points_per_foot": value}
    import json
    before = json.dumps(room_model, sort_keys=True)
    with pytest.raises(IFCValidationError) as failure:
        IFCVolumeValidator().export_numeric_diagnostic(room_model)
    diagnostic = failure.value.diagnostic
    assert diagnostic["numeric_state"] == "NON_FINITE"
    assert diagnostic["state"] == "UNRESOLVED"
    assert diagnostic["source"] == room_model["source"]
    assert diagnostic["field"]
    json.dumps(diagnostic, allow_nan=False)
    assert json.dumps(room_model, sort_keys=True) == before  # no normalization or replacement
    assert "nan" not in str(failure.value).lower()
    assert "infinity" not in str(failure.value).lower()


@pytest.mark.parametrize("value,state", [(1.0, "FINITE"), (0, "FINITE"), (-1, "FINITE"),
    (float("nan"), "NON_FINITE"), (float("inf"), "NON_FINITE"), (float("-inf"), "NON_FINITE"),
    (None, "UNRESOLVED"), (True, "UNRESOLVED"), ("NaN", "UNRESOLVED"), ("1.0", "UNRESOLVED"),
    (10**400, "UNRESOLVED")])
def test_numeric_validity_is_strict_and_does_not_coerce(value, state):
    assert numeric_validity(value) == state


@pytest.mark.parametrize("case", ["wall_length", "opening_extent", "containment_distance"])
def test_finite_inputs_with_nonfinite_derivation_are_refused(room_model, case):
    if case == "wall_length":
        room_model["walls"][0]["baseline"] = [{"x": -1e308, "y": 0}, {"x": 1e308, "y": 0}]
    elif case == "opening_extent":
        room_model["walls"][0]["baseline"][1]["x"] = 1e308
        room_model["walls"][0]["openings"][0].update(offset=1e308, width=1e308)
    else:
        room_model["label_containment"][0]["relation"]["point"] = [1e308, 1e308]
    with pytest.raises(IFCValidationError) as failure:
        IFCVolumeValidator().export_numeric_diagnostic(room_model)
    assert failure.value.diagnostic["stage"] == "derived"
    assert failure.value.diagnostic["source"] == room_model["source"]


def test_step_emission_checks_derived_numeric_outputs_before_storage():
    from engine.ifc_volume_validator import _Step
    step = _Step()
    with pytest.raises(IFCValidationError) as failure:
        step.add("IFCCARTESIANPOINT", ((1.0, float("inf"), 0.0),))
    assert failure.value.diagnostic["stage"] == "STEP emission"
    assert not step.entities
