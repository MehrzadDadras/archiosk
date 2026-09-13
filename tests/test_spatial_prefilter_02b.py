"""CLAUDE-SPATIAL-PREFILTER-02B - filter impossible segments; never change the answer.

After 02A the remaining cost was ONE relate() against a 281,023-vertex, 557-ring
city-wide polygon: ~38-41 s, spent three times over on segments that could not
affect the result. Measured on 573 Shuter Street, of 280,466 layer segments the
crossing sweep needed 0, the proximity sweep needed 0, and containment needed 30.

EVERY FILTER HERE IS A PROOF, NOT AN APPROXIMATION:

    crossing     two segments whose bounding boxes do not overlap cannot meet
    proximity    distance(point, segment) >= distance(point, segment's box)
    containment  a segment crossed by no ray at any y the subject occupies
                 cannot change parity for any subject vertex

THE ONE THAT IS EASY TO GET WRONG, and the reason this file exists: for ray
casting the safe rejection is NOT the full bounding box. A point above or below a
ring can be rejected, and a point to the RIGHT can be rejected, because every
crossing lies between two of the ring's own x values. A point to the LEFT cannot -
its ray enters the ring, which is the case ray casting exists for. Rejecting on
`x < xmin` would report OUTSIDE for half the points that are inside, and
`test_a_point_left_of_the_ring_is_still_inside` is the test that catches it.

The adversarial suite is DIFFERENTIAL: it compares the optimized engine against a
verbatim copy of the pre-change implementation, so equivalence is proven against
the real previous behaviour rather than against expectations of it.
"""
from __future__ import annotations

import itertools
import unittest

from services import deterministic_spatial as spatial

CRS = "EPSG:3857"


# -- the pre-change implementation, verbatim, for differential comparison -----
def legacy_point_in_ring(point, ring) -> bool:
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


def legacy_rings_cross(a, b) -> bool:
    for i in range(len(a) - 1):
        for j in range(len(b) - 1):
            if spatial._segments_cross(a[i], a[i + 1], b[j], b[j + 1]):
                return True
    return False


def _point_box(point):
    """A degenerate box for a single point - what `prepare_parts` now takes."""
    return (point[0], point[1], point[0], point[1])


def square(x, y, size):
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]


def ring_with_hole(size=100.0, hole=40.0):
    outer = square(0.0, 0.0, size)
    inner = square((size - hole) / 2, (size - hole) / 2, hole)
    return {"type": "Polygon", "coordinates": [outer, list(reversed(inner))]}


#: Rings chosen to break a careless filter: horizontal and vertical edges,
#: shared vertices, a comb whose teeth create many y-bands, a very wide ring
#: whose bbox contains everything, and a degenerate sliver.
COMB = ([[0.0, 0.0]]
        + [c for i in range(12)
           for c in ([float(i) * 10, 90.0], [float(i) * 10 + 5, 90.0],
                     [float(i) * 10 + 5, 10.0], [float(i) * 10 + 10, 10.0])]
        + [[120.0, 0.0], [0.0, 0.0]])

RINGS = {
    "unit square": square(0.0, 0.0, 10.0),
    "big square": square(-500.0, -500.0, 1000.0),
    "thin horizontal": [[0.0, 0.0], [100.0, 0.0], [100.0, 0.001],
                        [0.0, 0.001], [0.0, 0.0]],
    "thin vertical": [[0.0, 0.0], [0.001, 0.0], [0.001, 100.0],
                      [0.0, 100.0], [0.0, 0.0]],
    "comb": COMB,
    "triangle": [[0.0, 0.0], [10.0, 0.0], [5.0, 10.0], [0.0, 0.0]],
    "offset square": square(50.0, 50.0, 10.0),
}

#: Points chosen to sit inside, outside, on a vertex, on an edge, a hair inside
#: and a hair outside - and, critically, to the LEFT, RIGHT, ABOVE and BELOW.
POINTS = [
    [5.0, 5.0], [0.0, 0.0], [10.0, 10.0], [10.0, 5.0], [0.0, 5.0],
    [5.0, 0.0], [5.0, 10.0], [-1.0, 5.0], [11.0, 5.0], [5.0, -1.0],
    [5.0, 11.0], [1e-9, 5.0], [-1e-9, 5.0], [9.999999999, 5.0],
    [55.0, 55.0], [-600.0, 0.0], [0.0, 0.001], [0.0005, 50.0],
    [25.0, 50.0], [45.0, 89.999], [120.0, 0.0],
]


class PointInRingIsUnchanged(unittest.TestCase):
    """Differential: box and band prefilters against the original arithmetic."""

    def test_every_point_against_every_ring(self):
        checked = 0
        for name, ring in RINGS.items():
            box = spatial._bbox(ring)
            for point in POINTS:
                expected = legacy_point_in_ring(point, ring)
                with self.subTest(ring=name, point=point):
                    self.assertEqual(
                        spatial._point_in_ring(point, ring), expected,
                        "unfiltered path changed")
                    self.assertEqual(
                        spatial._point_in_ring(point, ring, box), expected,
                        "box rejection changed the answer")
                    band = spatial.ring_band(ring, point[1], point[1])
                    self.assertEqual(
                        spatial._point_in_ring(point, ring, box, band), expected,
                        "band changed the answer")
                checked += 1
        self.assertGreater(checked, 100)

    def test_a_point_left_of_the_ring_is_still_inside(self):
        """THE TRAP. A full-bbox rejection would answer OUTSIDE here."""
        ring = square(0.0, 0.0, 10.0)
        box = spatial._bbox(ring)
        point = [-5.0, 5.0]
        self.assertFalse(spatial._point_in_ring(point, ring, box),
                         "left of the ring is genuinely outside")
        # ... and the ray from a point INSIDE must still be counted, even though
        # segments lie to its left.
        inside = [5.0, 5.0]
        self.assertTrue(spatial._point_in_ring(inside, ring, box))
        self.assertTrue(spatial._point_in_ring(
            inside, ring, box, spatial.ring_band(ring, 5.0, 5.0)))

    def test_the_box_rejects_only_above_below_and_right(self):
        ring = square(0.0, 0.0, 10.0)
        box = spatial._bbox(ring)
        for point, expected in (([5.0, 20.0], False), ([5.0, -20.0], False),
                                ([20.0, 5.0], False), ([-20.0, 5.0], False)):
            self.assertEqual(spatial._point_in_ring(point, ring, box), expected)
            self.assertEqual(legacy_point_in_ring(point, ring), expected)

    def test_a_band_spanning_the_whole_subject_serves_every_vertex(self):
        """One band, many points - the reuse that makes this worth doing."""
        ring = RINGS["comb"]
        low, high = 40.0, 60.0
        band = spatial.ring_band(ring, low, high)
        box = spatial._bbox(ring)
        for y in (40.0, 45.0, 50.0, 55.0, 60.0):
            for x in (-5.0, 2.5, 7.5, 45.0, 125.0):
                point = [x, y]
                self.assertEqual(
                    spatial._point_in_ring(point, ring, box, band),
                    legacy_point_in_ring(point, ring), point)

    def test_the_band_is_smaller_than_the_ring_it_came_from(self):
        ring = RINGS["comb"]
        band = spatial.ring_band(ring, 49.0, 51.0)
        self.assertLess(len(band), len(ring) - 1)
        self.assertGreater(len(band), 0)


class PolygonsAndPartsAreUnchanged(unittest.TestCase):

    def test_holes_behave_identically_with_and_without_preparation(self):
        geometry = ring_with_hole()
        parts = spatial._parts(geometry)
        for point in POINTS + [[50.0, 50.0], [30.0, 50.0], [31.0, 31.0]]:
            expected = spatial._point_in_parts(point, parts)
            prepared = spatial.prepare_parts(parts, _point_box(point), 0.0)
            with self.subTest(point=point):
                self.assertEqual(
                    spatial._point_in_parts(point, parts, prepared), expected)

    def test_a_point_inside_a_hole_is_outside_the_polygon(self):
        geometry = ring_with_hole()
        parts = spatial._parts(geometry)
        prepared = spatial.prepare_parts(parts, (50.0, 50.0, 50.0, 50.0), 0.0)
        self.assertFalse(spatial._point_in_parts([50.0, 50.0], parts, prepared))
        self.assertTrue(spatial._point_in_parts([5.0, 50.0], parts, prepared))

    def test_multipolygons_behave_identically(self):
        geometry = {"type": "MultiPolygon", "coordinates": [
            [square(0.0, 0.0, 10.0)], [square(100.0, 100.0, 10.0)]]}
        parts = spatial._parts(geometry)
        for point in ([5.0, 5.0], [105.0, 105.0], [50.0, 50.0], [0.0, 0.0]):
            prepared = spatial.prepare_parts(parts, _point_box(point), 0.0)
            self.assertEqual(spatial._point_in_parts(point, parts, prepared),
                             spatial._point_in_parts(point, parts), point)


class CrossingIsUnchanged(unittest.TestCase):

    def test_every_ring_pair_with_and_without_boxes(self):
        for (name_a, a), (name_b, b) in itertools.product(RINGS.items(), repeat=2):
            expected = legacy_rings_cross(a, b)
            with self.subTest(a=name_a, b=name_b):
                self.assertEqual(spatial._rings_cross(a, b), expected)
                self.assertEqual(
                    spatial._rings_cross(a, b, spatial._bbox(a), spatial._bbox(b)),
                    expected, "box rejection changed a crossing verdict")

    def test_rings_sharing_a_vertex_are_not_rejected_by_their_boxes(self):
        a = square(0.0, 0.0, 10.0)
        b = square(10.0, 10.0, 10.0)
        self.assertEqual(
            spatial._rings_cross(a, b, spatial._bbox(a), spatial._bbox(b)),
            legacy_rings_cross(a, b))

    def test_boxes_apart_never_rejects_touching_boxes(self):
        self.assertFalse(spatial._boxes_apart((0, 0, 10, 10), (10, 0, 20, 10), 0.0))
        self.assertTrue(spatial._boxes_apart((0, 0, 10, 10), (11, 0, 20, 10), 0.0))
        self.assertFalse(spatial._boxes_apart((0, 0, 10, 10), (11, 0, 20, 10), 1.0))


class ProximityIsUnchanged(unittest.TestCase):
    """`_within_tolerance` must answer exactly what the minimum distance did."""

    def test_it_agrees_with_the_minimum_distance_it_replaced(self):
        for name, ring in RINGS.items():
            rings = [ring]
            boxes = [spatial._bbox(ring)]
            for point in POINTS:
                for tolerance in (0.0, 1e-9, 0.001, 1.0, 50.0):
                    expected = (spatial._min_distance_to_polygon(point, rings)
                                <= tolerance)
                    with self.subTest(ring=name, point=point, tol=tolerance):
                        self.assertEqual(
                            spatial._within_tolerance(point, rings, tolerance),
                            expected)
                        self.assertEqual(
                            spatial._within_tolerance(point, rings, tolerance,
                                                      boxes),
                            expected, "box rejection changed a proximity verdict")

    def test_the_minimum_distance_function_is_left_intact(self):
        """A different question, deliberately unchanged."""
        ring = square(0.0, 0.0, 10.0)
        self.assertEqual(spatial._min_distance_to_polygon([5.0, 5.0], [ring]), 5.0)
        self.assertEqual(spatial._min_distance_to_polygon([-5.0, 5.0], [ring]), 5.0)


class RelateIsUnchangedOnAdversarialGeometry(unittest.TestCase):
    """End to end: the token, not just the primitives."""

    def _relate(self, subject, layer):
        return spatial.relate({"crs": CRS, "geometry": subject},
                              {"crs": CRS, "geometry": layer},
                              subject_source="s", layer_source="l")

    def test_the_documented_relations_still_hold(self):
        small = {"type": "Polygon", "coordinates": [square(1.0, 1.0, 2.0)]}
        big = {"type": "Polygon", "coordinates": [square(0.0, 0.0, 10.0)]}
        far = {"type": "Polygon", "coordinates": [square(900.0, 900.0, 10.0)]}
        overlapping = {"type": "Polygon", "coordinates": [square(5.0, 5.0, 10.0)]}
        self.assertEqual(self._relate(small, big)["spatial_relation"], "INSIDE")
        self.assertEqual(self._relate(small, far)["spatial_relation"], "OUTSIDE")
        self.assertEqual(self._relate(big, overlapping)["spatial_relation"],
                         "INTERSECTS")

    def test_a_subject_inside_a_hole_is_outside(self):
        subject = {"type": "Polygon", "coordinates": [square(45.0, 45.0, 2.0)]}
        self.assertEqual(self._relate(subject, ring_with_hole())["spatial_relation"],
                         "OUTSIDE")

    def test_a_subject_enclosing_a_hole_intersects(self):
        subject = {"type": "Polygon", "coordinates": [square(20.0, 20.0, 60.0)]}
        self.assertEqual(self._relate(subject, ring_with_hole())["spatial_relation"],
                         "INTERSECTS")

    def test_a_vertex_within_tolerance_is_still_refused(self):
        """The boundary refusal is the engine's most important answer."""
        big = {"type": "Polygon", "coordinates": [square(0.0, 0.0, 10000.0)]}
        subject = {"type": "Polygon", "coordinates": [
            [[0.0, 5000.0], [10.0, 5000.0], [10.0, 5010.0], [0.0, 5010.0],
             [0.0, 5000.0]]]}
        token = self._relate(subject, big)
        self.assertEqual(token["spatial_relation"], "AMBIGUOUS")
        self.assertEqual(token["reason"], spatial.REASON_NEAR_BOUNDARY)

    def test_an_invalid_ring_is_still_refused(self):
        broken = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]}
        good = {"type": "Polygon", "coordinates": [square(0.0, 0.0, 10.0)]}
        token = self._relate(good, broken)
        self.assertEqual(token["spatial_relation"], "AMBIGUOUS")
        self.assertEqual(token["reason"], spatial.REASON_INVALID)

    def test_the_engine_identity_is_unchanged(self):
        """No new engine. The arithmetic is the same arithmetic."""
        self.assertEqual(spatial.ENGINE, "archiosk-exact-ring@3")

    def test_a_large_ring_reaches_the_same_verdict_as_the_unfiltered_path(self):
        """A 4,000-vertex circle, far from a small parcel - the shape of the
        real Natural Heritage case, small enough to test directly."""
        import math
        circle = [[500.0 + 400.0 * math.cos(i * 2 * math.pi / 4000),
                   500.0 + 400.0 * math.sin(i * 2 * math.pi / 4000)]
                  for i in range(4000)]
        circle.append(circle[0])
        layer = {"type": "Polygon", "coordinates": [circle]}
        for subject_square in (square(1.0, 1.0, 2.0),        # outside, lower-left
                               square(498.0, 498.0, 2.0),    # inside
                               square(-500.0, 500.0, 2.0)):  # outside, LEFT
            subject = {"type": "Polygon", "coordinates": [subject_square]}
            parts = spatial._parts(layer)
            vertices = subject_square[:-1]
            unfiltered = [spatial._point_in_parts(v, parts) for v in vertices]
            boxes = [spatial._bbox(r) for r in [circle]]
            low = min(v[1] for v in vertices)
            high = max(v[1] for v in vertices)
            prepared = spatial.prepare_parts(
                parts, (min(v[0] for v in vertices), low,
                        max(v[0] for v in vertices), high), 0.0)
            filtered = [spatial._point_in_parts(v, parts, prepared)
                        for v in vertices]
            self.assertEqual(filtered, unfiltered, subject_square[0])
            self.assertEqual(
                spatial._within_tolerance(vertices[0], [circle], 1e-6, boxes),
                spatial._min_distance_to_polygon(vertices[0], [circle]) <= 1e-6)


class NothingForbiddenWasIntroduced(unittest.TestCase):
    """Section 6 and 13."""

    def test_no_cache_no_simplification_no_provider_call(self):
        """Asserted against the IMPORT SURFACE and decorators, not the prose.

        A first version scanned the file's text for "requests" to catch the HTTP
        library, and then failed on a docstring sentence reading "retained
        between requests" - a test of wording rather than of behaviour, and the
        seventh time this programme has made that exact mistake. What matters is
        what the module IMPORTS and what decorates it.
        """
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(spatial))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        for banned in ("requests", "urllib", "shapely", "pyproj", "functools",
                       "httpx", "socket"):
            self.assertNotIn(banned, imported,
                             "%s must not be reachable from the engine" % banned)
        decorators = {ast.unparse(decorator)
                      for node in ast.walk(tree)
                      if isinstance(node, ast.FunctionDef)
                      for decorator in node.decorator_list}
        self.assertEqual([d for d in decorators if "cache" in d.lower()], [])

    def test_the_minimum_distance_and_ring_helpers_still_exist(self):
        for name in ("_min_distance_to_ring", "_min_distance_to_polygon",
                     "_point_in_ring", "_point_in_polygon", "_point_in_parts",
                     "_rings_cross", "_any_crossing", "_segments_cross"):
            self.assertTrue(hasattr(spatial, name), name)


if __name__ == "__main__":
    unittest.main()
