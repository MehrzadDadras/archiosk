import re

import pytest

from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator


@pytest.fixture
def room_model():
    return {
        "project_name": "IFC Test Project",
        "levels": [{"name": "LEVEL 1", "elevation": 0.0}],
        "spaces": [{"id": "SPACE-ENTRY", "name": "ENTRY/LOBBY", "level": "LEVEL 1", "height": 144.0,
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
