"""
CLAUDE-SPATIAL-COMPILER-01 - 2D drawing vectors compiled into IFC 4x3 volume.

    PDFVectorExtractor  ->  SpatialCompiler  ->  IFCVolumeValidator

WHAT THESE TESTS ARE ACTUALLY DEFENDING

Three classes of failure, none of which any downstream validator can catch:

1. A MIRRORED BUILDING. PDFVectorExtractor reports `top_left_origin_y_down`.
   Extruding that frame directly produces a model that is closed, simple,
   positive-area, exports cleanly, and is reflected. Every check passes and the
   building is wrong. So the lift is asserted against known coordinates.

2. AN INVENTED ROOM. The loop assembler joins strokes by adjacency. If it closed
   open chains by connecting loose ends it would emit a space the drawing never
   enclosed. Open chains must be discarded, and that is tested directly.

3. A SILENTLY CORRECTED DRAWING. The proving corpus contradicts itself in two
   ways already found by blind audit - LEVEL 3's label disagrees with where it is
   drawn, and the title block declares a scale 1.5x what the datums use. The
   compiler must compile what is DRAWN and say so, not quietly pick a winner.
   That the compiler rediscovers both, from geometry alone, is asserted below.

The scale is derived from the section's own datum spacing by majority agreement,
never from the declared scale - which on this corpus is the wrong one.
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

import pytest

from engine.ifc_volume_validator import IFCValidationError, IFCVolumeValidator
from engine.pdf_extractor import PDFVectorExtractor
from engine.spatial_compiler import (
    SpatialCompilationError,
    SpatialCompiler,
    assemble_loops,
    compile_to_ifc,
    derive_points_per_foot,
    ensure_ccw,
    point_in_polygon,
    signed_area,
)

_CORPUS = Path(__file__).resolve().parent / "fixtures" / "metabolic_bridge" / "builder_corpus"
_PDF = _CORPUS / "Drawings_Set.pdf"

# Measured from the corpus, not assumed by it.
_PAGE_HEIGHT = 792.0
_STOREY_POINTS = 144.0          # LEVEL 1 -> LEVEL 2
_POINTS_PER_FOOT = 12.0         # what three of four datums agree on
_DECLARED_PER_FOOT = 18.0       # what the title block claims
_DOOR_HEAD_POINTS = 84.0


@pytest.fixture(scope="module")
def document():
    return PDFVectorExtractor().extract_document(str(_PDF))


@pytest.fixture(scope="module")
def schedule():
    with open(_CORPUS / "Door_Schedule.csv", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


@pytest.fixture(scope="module")
def bridge(document, schedule):
    return compile_to_ifc(document, schedule=schedule, project_name="Metabolic Bridge")


@pytest.fixture(scope="module")
def compiled(document, schedule):
    return SpatialCompiler().compile(document, schedule=schedule,
                                     project_name="Metabolic Bridge")


# ---------------------------------------------------------------------------
# geometry primitives
# ---------------------------------------------------------------------------

class TestLoopAssembly:
    SQUARE = [((0, 0), (10, 0)), ((10, 0), (10, 10)),
              ((10, 10), (0, 10)), ((0, 10), (0, 0))]

    def test_loose_segments_become_one_closed_loop(self):
        loops = assemble_loops(self.SQUARE)
        assert len(loops) == 1
        assert len(loops[0]) == 4

    def test_segment_order_does_not_matter(self):
        shuffled = [self.SQUARE[2], self.SQUARE[0], self.SQUARE[3], self.SQUARE[1]]
        assert len(assemble_loops(shuffled)[0]) == 4

    def test_segment_direction_does_not_matter(self):
        # A drafter's stroke direction is arbitrary; the topology is not.
        flipped = [(b, a) for a, b in self.SQUARE]
        assert len(assemble_loops(flipped)) == 1

    def test_an_open_chain_is_discarded_not_sealed(self):
        # The failure this prevents: inventing a room the drawing never enclosed.
        assert assemble_loops(self.SQUARE[:-1]) == []

    def test_two_disjoint_squares_yield_two_loops(self):
        second = [((100, 100), (110, 100)), ((110, 100), (110, 110)),
                  ((110, 110), (100, 110)), ((100, 110), (100, 100))]
        assert len(assemble_loops(self.SQUARE + second)) == 2

    def test_zero_length_segments_are_ignored(self):
        assert len(assemble_loops(self.SQUARE + [((5, 5), (5, 5))])) == 1


class TestWinding:
    CW = [(0, 0), (0, 10), (10, 10), (10, 0)]

    def test_signed_area_sign_distinguishes_winding(self):
        assert signed_area(self.CW) < 0
        assert signed_area(list(reversed(self.CW))) > 0

    def test_ensure_ccw_normalises_without_changing_the_shape(self):
        made = ensure_ccw(self.CW)
        assert signed_area(made) > 0
        assert set(made) == set(self.CW)

    def test_an_already_ccw_polygon_is_left_alone(self):
        ccw = list(reversed(self.CW))
        assert ensure_ccw(ccw) == ccw


class TestPointInPolygon:
    SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]

    def test_interior_point_is_contained(self):
        assert point_in_polygon((5, 5), self.SQUARE)

    def test_exterior_point_is_not(self):
        assert not point_in_polygon((15, 5), self.SQUARE)
        assert not point_in_polygon((-1, 5), self.SQUARE)

    def test_a_closed_ring_is_accepted_too(self):
        assert point_in_polygon((5, 5), self.SQUARE + [self.SQUARE[0]])

    def test_containment_is_not_a_bounding_box_test(self):
        # An L-shape: the bbox corner is outside the actual polygon. A bbox
        # shortcut would bind a label to the wrong room.
        el = [(0, 0), (10, 0), (10, 4), (4, 4), (4, 10), (0, 10)]
        assert point_in_polygon((2, 2), el)
        assert not point_in_polygon((8, 8), el)


class TestScaleDerivation:
    def test_the_majority_of_datums_sets_the_scale(self):
        datums = [{"name": "L1", "label_elevation_feet": 0.0, "line_y": 500.0},
                  {"name": "L2", "label_elevation_feet": 12.0, "line_y": 356.0},
                  {"name": "ROOF", "label_elevation_feet": 17.0, "line_y": 296.0},
                  {"name": "L3", "label_elevation_feet": 24.0, "line_y": 236.0}]
        scale, warnings = derive_points_per_foot(datums)
        assert scale == 12.0
        assert len(warnings) == 1
        assert "L3" in warnings[0]

    def test_a_fully_consistent_set_warns_about_nothing(self):
        datums = [{"name": "L1", "label_elevation_feet": 0.0, "line_y": 500.0},
                  {"name": "L2", "label_elevation_feet": 10.0, "line_y": 380.0}]
        assert derive_points_per_foot(datums) == (12.0, [])

    def test_a_single_datum_cannot_establish_a_scale(self):
        scale, warnings = derive_points_per_foot(
            [{"name": "L1", "label_elevation_feet": 0.0, "line_y": 500.0}])
        assert scale is None and warnings


# ---------------------------------------------------------------------------
# compilation against the real corpus
# ---------------------------------------------------------------------------

class TestSheetAndScaleDiscovery:
    def test_it_finds_the_plan_and_the_section_itself(self, compiled):
        assert compiled["derived"]["plan_sheet"] == "A-101"
        assert compiled["derived"]["section_sheet"] == "A-201"

    def test_the_drawn_scale_is_used_not_the_declared_one(self, compiled):
        assert compiled["derived"]["points_per_foot"] == _POINTS_PER_FOOT
        assert compiled["derived"]["declared_points_per_foot"] == _DECLARED_PER_FOOT

    def test_the_scale_contradiction_is_reported_not_resolved_silently(self, compiled):
        assert any("declares 18.00 pt/ft" in w and "drawn at 12.00 pt/ft" in w
                   for w in compiled["warnings"])

    def test_the_level_3_datum_contradiction_is_rediscovered_from_geometry(self, compiled):
        # Found independently by the Phase 2 blind audit. The compiler must reach
        # the same conclusion from the drawing alone.
        hits = [w for w in compiled["warnings"] if "LEVEL 3" in w]
        assert len(hits) == 1
        assert "+24.00 pt" in hits[0] and "-2.00 ft" in hits[0]

    def test_level_elevations_are_measured_not_believed(self, compiled):
        levels = {level["name"]: level for level in compiled["levels"]}
        assert levels["LEVEL 2"]["measured_elevation_feet"] == 12.0
        assert levels["ROOF"]["measured_elevation_feet"] == 17.0
        # The label says 24; the drawing says 22. Both are kept.
        assert levels["LEVEL 3"]["label_elevation_feet"] == 24.0
        assert levels["LEVEL 3"]["measured_elevation_feet"] == 22.0


class TestVerticalLift:
    def test_the_storey_height_is_the_level_1_to_2_delta(self, compiled):
        assert compiled["derived"]["storey_height_points"] == _STOREY_POINTS
        assert all(space["height"] == _STOREY_POINTS for space in compiled["spaces"])

    def test_the_model_is_not_mirrored(self, compiled):
        # The defect this exists for: the extractor is Y-DOWN. A room drawn at
        # plan y 130..300 must land at 492..662, not stay at 130..300.
        entry = next(s for s in compiled["spaces"] if "ENTRY" in s["name"])
        ys = [p["y"] for p in entry["boundary_polygon_2d"]]
        assert min(ys) == _PAGE_HEIGHT - 300.0
        assert max(ys) == _PAGE_HEIGHT - 130.0

    def test_the_x_axis_is_untouched_by_the_lift(self, compiled):
        entry = next(s for s in compiled["spaces"] if "ENTRY" in s["name"])
        xs = [p["x"] for p in entry["boundary_polygon_2d"]]
        assert (min(xs), max(xs)) == (100.0, 250.0)

    def test_every_emitted_loop_is_counter_clockwise(self, compiled):
        for space in compiled["spaces"]:
            ring = [(p["x"], p["y"]) for p in space["boundary_polygon_2d"][:-1]]
            assert signed_area(ring) > 0, space["id"]


class TestRoomBinding:
    def test_every_room_label_binds_to_its_own_loop(self, compiled):
        assert sorted(s["name"] for s in compiled["spaces"]) == [
            "CORRIDOR", "ELECTRICAL", "ENTRY / LOBBY", "MECHANICAL"]

    def test_binding_is_containment_not_proximity(self, compiled):
        # ELECTRICAL and MECHANICAL sit at the same height on the sheet and
        # differ only in x. A nearest-label rule would be a coin flip.
        electrical = next(s for s in compiled["spaces"] if s["name"] == "ELECTRICAL")
        xs = [p["x"] for p in electrical["boundary_polygon_2d"]]
        assert max(xs) <= 250.0

    def test_no_space_is_left_unnamed(self, compiled):
        assert not [s for s in compiled["spaces"] if s["name"].startswith("UNNAMED")]
        assert not [w for w in compiled["warnings"] if "falls inside no compiled loop" in w]


class TestVoidExtraction:
    def test_the_head_height_comes_from_the_section(self, compiled):
        assert compiled["derived"]["door_head_height_points"] == _DOOR_HEAD_POINTS

    def test_every_tagged_door_is_placed_in_a_wall(self, compiled):
        placed = {o["id"] for w in compiled["walls"] for o in w["openings"]}
        assert placed == {"D-101", "D-102", "D-103", "D-104", "D-106"}

    def test_a_width_is_derived_from_the_schedule_where_one_exists(self, compiled):
        opening = next(o for w in compiled["walls"] for o in w["openings"]
                       if o["id"] == "D-101")
        # 1010 mm at 12.0 pt/ft
        assert opening["width"] == pytest.approx(1010 / 304.8 * 12.0, abs=1e-3)

    def test_the_orphan_tag_falls_back_and_says_so(self, compiled):
        # D-106 is the orphan door found by the Phase 1 blind audit: tagged on
        # the plan, defined by no schedule row. It must still compile, with the
        # assumption declared rather than buried.
        opening = next(o for w in compiled["walls"] for o in w["openings"]
                       if o["id"] == "D-106")
        assert opening["width"] == 36.0
        assert any("D-106 has no schedule row" in w for w in compiled["warnings"])

    def test_openings_stay_inside_their_host_wall(self, compiled):
        import math

        for wall in compiled["walls"]:
            a = (wall["baseline"][0]["x"], wall["baseline"][0]["y"])
            b = (wall["baseline"][1]["x"], wall["baseline"][1]["y"])
            length = math.dist(a, b)
            for opening in wall["openings"]:
                assert opening["offset"] >= 0
                assert opening["offset"] + opening["width"] <= length + 1e-9
                assert 0 < opening["height"] <= wall["height"]

    def test_shifting_a_door_to_fit_is_reported(self, compiled):
        # Clamping moves a door away from where it was tagged. Doing that
        # silently would put an opening somewhere the drawing does not.
        shifted = [w for w in compiled["warnings"] if "was shifted" in w]
        assert shifted
        for warning in shifted:
            assert re.search(r"shifted \d+\.\d pt along WALL-\d+", warning)


class TestRefusalWhenEvidenceIsAbsent:
    def test_a_set_with_no_section_will_not_compile(self, document):
        # Without datums there is no evidence of storey height, and inventing one
        # would fabricate the building's third dimension.
        plan_only = {"pages": [p for p in document["pages"] if p["page_number"] == 1],
                     "schema_version": document["schema_version"], "source": {}}
        with pytest.raises(SpatialCompilationError, match="section"):
            SpatialCompiler().compile(plan_only)

    def test_a_set_with_no_plan_will_not_compile(self, document):
        section_only = {"pages": [p for p in document["pages"] if p["page_number"] == 4],
                        "schema_version": document["schema_version"], "source": {}}
        with pytest.raises(SpatialCompilationError, match="floor plan"):
            SpatialCompiler().compile(section_only)


class TestAssumptionsAreDeclared:
    def test_undimensioned_values_are_visible_in_the_output(self, compiled):
        assumptions = compiled["assumptions"]
        assert assumptions["wall_thickness_points"] == 6.0
        assert assumptions["default_door_width_points"] == 36.0
        assert "not dimensioned" in assumptions["note"]

    def test_the_source_document_is_carried_through(self, compiled):
        assert compiled["source"]["filename"] == "Drawings_Set.pdf"
        assert len(compiled["source"]["sha256"]) == 64


# ---------------------------------------------------------------------------
# the whole bridge
# ---------------------------------------------------------------------------

class TestEndToEndToIFC:
    def test_the_compiled_model_satisfies_the_validator(self, compiled):
        # The contract between the two stages. If this fails the compiler is
        # emitting geometry the exporter cannot represent.
        IFCVolumeValidator().validate(compiled)

    def test_it_produces_a_well_formed_step_file(self, bridge):
        _model, ifc = bridge
        assert ifc.startswith("ISO-10303-21;")
        assert ifc.rstrip().endswith("END-ISO-10303-21;")
        assert "FILE_SCHEMA(('IFC4X3'));" in ifc

    def test_the_spatial_hierarchy_is_present(self, bridge):
        _model, ifc = bridge
        for entity in ("IFCPROJECT(", "IFCSITE(", "IFCBUILDING(",
                       "IFCBUILDINGSTOREY(", "IFCRELAGGREGATES("):
            assert entity in ifc

    def test_every_room_became_a_space_with_a_swept_solid(self, bridge):
        model, ifc = bridge
        assert ifc.count("IFCSPACE(") == len(model["spaces"]) == 4
        assert ifc.count("IFCEXTRUDEDAREASOLID(") >= 4
        assert "IFCARBITRARYCLOSEDPROFILEDEF(" in ifc

    def test_every_door_became_a_void_in_a_wall(self, bridge):
        model, ifc = bridge
        openings = [o for w in model["walls"] for o in w["openings"]]
        assert ifc.count("IFCOPENINGELEMENT(") == len(openings) == 5
        assert ifc.count("IFCRELVOIDSELEMENT(") == len(openings)

    def test_the_room_names_survive_into_the_ifc(self, bridge):
        _model, ifc = bridge
        for room in ("ENTRY / LOBBY", "CORRIDOR", "ELECTRICAL", "MECHANICAL"):
            assert room in ifc

    def test_all_four_levels_reach_the_ifc(self, bridge):
        _model, ifc = bridge
        assert ifc.count("IFCBUILDINGSTOREY(") == 4
        for level in ("LEVEL 1", "LEVEL 2", "LEVEL 3", "ROOF"):
            assert level in ifc

    def test_every_step_reference_resolves(self, bridge):
        # A dangling #n would make the file unopenable while still looking fine.
        _model, ifc = bridge
        declared = {int(m) for m in re.findall(r"^#(\d+)=", ifc, re.M)}
        used = {int(m) for m in re.findall(r"#(\d+)", ifc)}
        assert used - declared == set()

    def test_a_broken_model_is_refused_rather_than_exported(self, compiled):
        broken = dict(compiled)
        broken["spaces"] = [dict(compiled["spaces"][0])]
        broken["spaces"][0] = {**broken["spaces"][0], "height": 0.0}
        with pytest.raises(IFCValidationError):
            IFCVolumeValidator().export(broken)
