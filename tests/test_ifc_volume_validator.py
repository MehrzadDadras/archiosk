import re

import pytest

from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator, polygon_region
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
    text = IFCVolumeValidator().export(room_model)
    assert text.startswith("ISO-10303-21;")
    assert "IFCPROJECT(" in text and "IFCSPACE(" in text
    assert "IFCWALLSTANDARDCASE(" in text and "IFCOPENINGELEMENT(" in text
    assert "IFCRELVOIDSELEMENT(" in text


def test_step_headers_relationships_and_coordinate_bounds(room_model):
    text = IFCVolumeValidator().validate_and_export(room_model)
    assert "FILE_SCHEMA(('IFC4X3'));" in text
    assert "IFCRELAGGREGATES(" in text
    assert "IFCRELCONTAINEDINSPATIALSTRUCTURE(" in text
    assert "0.0" in text and "120.0" in text and "80.0" in text and "144.0" in text
    assert re.search(r"#\d+=IFCCARTESIANPOINT", text)


def test_open_bounds_and_self_intersection_are_rejected(room_model):
    room_model["spaces"][0]["boundary_polygon_2d"].pop()
    with pytest.raises(IFCValidationError, match="closed"):
        IFCVolumeValidator().export(room_model)


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
        assert "IFCSPACE(" in IFCVolumeValidator().export(room_model)
    else:
        with pytest.raises(IFCValidationError):
            IFCVolumeValidator().export(room_model)


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
            IFCVolumeValidator().export(room_model)


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
        IFCVolumeValidator().export(room_model)


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
        IFCVolumeValidator().export(room_model)
