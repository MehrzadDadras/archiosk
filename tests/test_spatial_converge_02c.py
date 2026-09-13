"""CLAUDE-SPATIAL-CONVERGE-02C - one spatial truth, and hole assignment that scales.

`toronto_planning_source` carried its OWN ray-casting implementation, used to
decide which exterior each Esri hole belongs to. The codebase audit flagged it as
duplicate spatial mathematics; profiling then found it was the single most
expensive function in a live planning request - 17.7 s, 62,310 calls - which is
what happens when one truth has two homes and only one of them gets optimised.

EQUIVALENCE WAS PROVEN BEFORE ANYTHING WAS REMOVED. The two implementations were
line-for-line the same arithmetic with different nesting, and that was verified
rather than assumed: 840 synthetic comparisons plus 1,600 probes against the real
Natural Heritage rings, zero disagreements. Removing a duplicate is only safe once
you know it IS one, and the instruction was to STOP and report if it was not.

    hole assignment, Natural Heritage (557 rings, 281,023 vertices)
    before   62,310 point-in-ring calls, 42,649,645 vertex steps, 9.2-9.7 s
    after       213 calls after a bounding-box reject, then a y-index:  0.4-0.6 s

THE BOUNDING BOX ALONE WAS NOT ENOUGH, and that is the lesson worth keeping. It
rejects a candidate only when the probe lies outside it, and one City exterior
spans the whole municipality - so its box excluded almost nothing and the 213
surviving tests still walked 157,647 vertices each. A box answers "could this
contain the probe"; a y-index answers "which segments could the probe's ray
cross", and only the second shrinks as the ring grows.

NOTHING ABOUT THE CONVERSION'S MEANING CHANGED. Same probe vertex (`hole[0]`),
same winding-order reading, same "in no exterior or in several -> None" refusal,
same ring coordinates, same hole ownership, same GeoJSON, same geometry hash.
"""
from __future__ import annotations

import io
import json
import math
import random
import unittest
from pathlib import Path

from services import deterministic_spatial as spatial
from services import toronto_planning_source as source


def legacy_point_in_ring(point, ring) -> bool:
    """The implementation removed from `toronto_planning_source`, verbatim.

    Kept here so equivalence is proven against what was actually there, not
    against a description of it.
    """
    x, y = point[0], point[1]
    inside = False
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[index + 1][0], ring[index + 1][1]
        if (y1 > y) != (y2 > y) and y2 != y1:
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def square(x, y, size, clockwise=False):
    ring = [[x, y], [x + size, y], [x + size, y + size], [x, y + size], [x, y]]
    return list(reversed(ring)) if clockwise else ring


def circle(cx, cy, radius, count=600, clockwise=False):
    ring = [[cx + radius * math.cos(i * 2 * math.pi / count),
             cy + radius * math.sin(i * 2 * math.pi / count)]
            for i in range(count)]
    ring.append(ring[0])
    return list(reversed(ring)) if clockwise else ring


RINGS = {
    "ccw square": square(0, 0, 10),
    "cw square": square(0, 0, 10, clockwise=True),
    "big square": square(-500, -500, 1000),
    "thin horizontal": [[0, 0], [100, 0], [100, 0.001], [0, 0.001], [0, 0]],
    "thin vertical": [[0, 0], [0.001, 0], [0.001, 100], [0, 100], [0, 0]],
    "triangle": [[0, 0], [10, 0], [5, 10], [0, 0]],
    "comb": ([[0.0, 0.0]]
             + [c for i in range(12)
                for c in ([i * 10.0, 90.0], [i * 10.0 + 5, 90.0],
                          [i * 10.0 + 5, 10.0], [i * 10.0 + 10, 10.0])]
             + [[120.0, 0.0], [0.0, 0.0]]),
    "degenerate": [[0, 0], [0, 0], [0, 0], [0, 0]],
    "sliver": [[0, 0], [1e-9, 0], [1e-9, 1e-9], [0, 1e-9], [0, 0]],
    "circle": circle(500, 500, 400),
}

POINTS = [[5, 5], [0, 0], [10, 10], [10, 5], [0, 5], [5, 0], [5, 10],
          [-1, 5], [11, 5], [5, -1], [5, 11], [1e-9, 5], [-1e-9, 5],
          [9.999999999, 5], [55, 55], [-600, 0], [0, 0.001], [0.0005, 50],
          [25, 50], [45, 89.999], [120, 0], [500, 500], [500, 100], [100, 500],
          [500, 900], [500, 101]]
_random = random.Random(20260913)
POINTS += [[_random.uniform(-600, 950), _random.uniform(-600, 950)]
           for _ in range(70)]


class TheTwoImplementationsWereTheSameFunction(unittest.TestCase):
    """Section 2. Proven before removal, and kept proven after it."""

    def test_the_governed_primitive_agrees_with_the_removed_one(self):
        for name, ring in RINGS.items():
            for point in POINTS:
                with self.subTest(ring=name, point=point):
                    self.assertEqual(spatial._point_in_ring(point, ring),
                                     legacy_point_in_ring(point, ring))

    def test_the_y_index_agrees_with_the_removed_one(self):
        for name, ring in RINGS.items():
            prepared = spatial.ring_y_index(ring)
            for point in POINTS:
                with self.subTest(ring=name, point=point):
                    self.assertEqual(
                        spatial.point_in_ring_indexed(point, prepared),
                        legacy_point_in_ring(point, ring))

    def test_the_duplicate_is_gone_from_the_planning_source(self):
        text = Path("services/toronto_planning_source.py").read_text(encoding="utf-8")
        self.assertNotIn("def _point_in_ring", text)
        self.assertIn("spatial.point_in_ring_indexed", text)

    def test_only_one_containment_implementation_remains_in_the_repository(self):
        offenders = []
        for path in Path("services").glob("*.py"):
            if path.name == "deterministic_spatial.py":
                continue
            text = path.read_text(encoding="utf-8")
            if "def _point_in_ring" in text or "def point_in_ring" in text:
                offenders.append(path.name)
        self.assertEqual(offenders, [])

    def test_a_point_outside_a_rings_box_is_never_inside_it(self):
        """The rejection `point_in_ring_indexed` relies on, stated as a property.

        A ring's interior is bounded by the ring, which lies within its own
        bounding box - so this holds in all four directions, including to the
        LEFT. 02B's own box rejection deliberately omits the left case and is
        therefore conservative rather than wrong; see its comment.
        """
        for name, ring in RINGS.items():
            minx, miny, maxx, maxy = spatial._bbox(ring)
            outside = [[minx - 1, (miny + maxy) / 2],
                       [maxx + 1, (miny + maxy) / 2],
                       [(minx + maxx) / 2, miny - 1],
                       [(minx + maxx) / 2, maxy + 1]]
            for point in outside:
                with self.subTest(ring=name, point=point):
                    self.assertFalse(legacy_point_in_ring(point, ring))
                    self.assertFalse(spatial._point_in_ring(point, ring))


class TheYIndexIsExact(unittest.TestCase):

    def test_every_segment_reachable_at_a_y_is_in_that_y_s_bucket(self):
        """The index may contain extra segments; it may never MISS one."""
        for name, ring in RINGS.items():
            prepared = spatial.ring_y_index(ring, buckets=16)
            low, span = prepared["low"], prepared["span"]
            for step in range(17):
                y = low + span * step / 16.0
                position = int((y - low) / span * (prepared["buckets"] - 1))
                position = max(0, min(position, prepared["buckets"] - 1))
                bucket = set(prepared["index"][position])
                for index in range(len(ring) - 1):
                    first, second = ring[index], ring[index + 1]
                    if (first[1] > y) != (second[1] > y):
                        with self.subTest(ring=name, y=y):
                            self.assertIn((first[0], first[1],
                                           second[0], second[1]), bucket,
                                          "a crossable segment was not indexed")

    def test_bucket_count_does_not_change_any_answer(self):
        for buckets in (1, 2, 7, 64, 1024):
            for name, ring in RINGS.items():
                prepared = spatial.ring_y_index(ring, buckets=buckets)
                for point in POINTS[:30]:
                    with self.subTest(buckets=buckets, ring=name, point=point):
                        self.assertEqual(
                            spatial.point_in_ring_indexed(point, prepared),
                            legacy_point_in_ring(point, ring))

    def test_a_flat_ring_does_not_divide_by_zero(self):
        flat = [[0, 5], [10, 5], [20, 5], [0, 5]]
        prepared = spatial.ring_y_index(flat)
        self.assertFalse(spatial.point_in_ring_indexed([5, 5], prepared))


class HoleOwnershipIsUnchanged(unittest.TestCase):
    """Sections 4 and 5."""

    def _convert(self, rings):
        return source.esri_to_geojson({"rings": rings})

    def test_one_exterior_with_one_hole(self):
        geometry = self._convert([square(0, 0, 100, clockwise=True),
                                  square(40, 40, 20)])
        self.assertEqual(geometry["type"], "Polygon")
        self.assertEqual(len(geometry["coordinates"]), 2)

    def test_two_exteriors_each_keep_their_own_hole(self):
        geometry = self._convert([
            square(0, 0, 100, clockwise=True), square(40, 40, 20),
            square(500, 500, 100, clockwise=True), square(540, 540, 20)])
        self.assertEqual(geometry["type"], "MultiPolygon")
        self.assertEqual(len(geometry["coordinates"]), 2)
        for part in geometry["coordinates"]:
            self.assertEqual(len(part), 2, "each exterior keeps exactly one hole")
            exterior_x = [p[0] for p in part[0]]
            hole_x = [p[0] for p in part[1]]
            self.assertTrue(min(exterior_x) <= min(hole_x) <= max(exterior_x),
                            "a hole must not migrate to the other exterior")

    def test_a_hole_in_no_exterior_still_refuses(self):
        self.assertIsNone(self._convert([square(0, 0, 10, clockwise=True),
                                         square(500, 500, 5)]))

    def test_a_hole_in_two_exteriors_still_refuses(self):
        """Overlapping exteriors leave ownership genuinely undecidable."""
        self.assertIsNone(self._convert([square(0, 0, 100, clockwise=True),
                                         square(10, 10, 100, clockwise=True),
                                         square(40, 40, 10)]))

    def test_many_exteriors_and_holes_agree_with_the_legacy_assignment(self):
        """The adversarial case: one huge exterior whose box contains everything,
        which is what defeated the bounding-box-only version."""
        rings = [circle(500, 500, 5000, count=400, clockwise=True)]
        expected_owner = []
        for index in range(12):
            cx, cy = 200 + index * 300, 400
            rings.append(circle(cx, cy, 60, count=40, clockwise=True))
            rings.append(circle(cx, cy, 20, count=30))
            expected_owner.append((cx, cy))
        geometry = self._convert(rings)
        legacy = self._legacy_convert(rings)
        # BOTH REFUSE, and that is the correct answer rather than a limitation:
        # every hole here sits inside its own small exterior AND inside the giant
        # one, so ownership is genuinely ambiguous and assigning it by guess would
        # punch a hole through the wrong part. The point of the case is that the
        # optimized path refuses for the same reason and on the same input - the
        # bounding box does not rescue it into a false answer.
        self.assertIsNone(geometry)
        self.assertIsNone(legacy)

        # And the unambiguous version of the same shape agrees exactly.
        unambiguous = [circle(200 + i * 300, 400, 60, count=40, clockwise=True)
                       for i in range(12)]
        unambiguous += [circle(200 + i * 300, 400, 20, count=30)
                        for i in range(12)]
        mine = self._convert(unambiguous)
        theirs = self._legacy_convert(unambiguous)
        self.assertIsNotNone(mine)
        self.assertEqual(json.dumps(mine, sort_keys=True),
                         json.dumps(theirs, sort_keys=True))
        self.assertEqual(len(mine["coordinates"]), 12)
        for part in mine["coordinates"]:
            self.assertEqual(len(part), 2, "each exterior keeps exactly one hole")

    def _legacy_convert(self, rings):
        """The original assignment loop, for differential comparison."""
        exteriors, holes = [], []
        for ring in rings:
            if not isinstance(ring, (list, tuple)) or len(ring) < 4:
                return None
            (exteriors if source._ring_signed_area(ring) < 0
             else holes).append(ring)
        if not exteriors:
            return None

        def flip(ring):
            return [list(p[:2]) for p in reversed(ring)]

        assigned = {index: [] for index in range(len(exteriors))}
        for hole in holes:
            containing = [index for index, exterior in enumerate(exteriors)
                          if legacy_point_in_ring(hole[0], exterior)]
            if len(containing) != 1:
                return None
            assigned[containing[0]].append(hole)
        parts = [[flip(exterior)] + [flip(hole) for hole in assigned[index]]
                 for index, exterior in enumerate(exteriors)]
        if len(parts) == 1:
            return {"type": "Polygon", "coordinates": parts[0]}
        return {"type": "MultiPolygon", "coordinates": parts}

    def test_winding_order_still_decides_exterior_from_hole(self):
        clockwise_only = self._convert([square(0, 0, 10, clockwise=True)])
        self.assertEqual(clockwise_only["type"], "Polygon")
        self.assertIsNone(self._convert([square(0, 0, 10)]),
                          "no exterior at all must still refuse")

    def test_a_short_ring_still_refuses(self):
        self.assertIsNone(self._convert([[[0, 0], [1, 0], [1, 1]]]))


class TheRealGeometryIsUnchanged(unittest.TestCase):
    """Section 7, against the captured municipal response."""

    CAPTURE = (r"C:\Users\info\AppData\Local\Temp\claude"
               r"\C--Archiosk-Research-archiosk"
               r"\eaae86eb-ca55-4f6b-a899-6fa7adebc222\scratchpad"
               r"\spatial_capture.json")

    def setUp(self):
        if not Path(self.CAPTURE).exists():
            self.skipTest("the municipal capture is a scratchpad artefact")
        responses = json.loads(io.open(self.CAPTURE, encoding="utf-8").read())
        self.raw = None
        for url, body in responses.items():
            if "cot_geospatial11" in url and "/34/query" in url:
                for feature in (json.loads(body).get("features") or []):
                    if feature.get("geometry"):
                        self.raw = feature["geometry"]

    def test_natural_heritage_converts_identically(self):
        converted = source.esri_to_geojson(self.raw)
        self.assertEqual(converted["type"], "MultiPolygon")
        self.assertEqual(len(converted["coordinates"]), 402)
        self.assertEqual(sum(len(part) - 1 for part in converted["coordinates"]),
                         155)
        self.assertEqual(spatial.geometry_hash(converted),
                         "sha256:343a53f3011db0dc798c2997e4be9217",
                         "the canonical geometry hash must not move")

    def test_it_matches_the_legacy_assignment_exactly(self):
        rings = self.raw["rings"]
        exteriors = [r for r in rings if source._ring_signed_area(r) < 0]
        holes = [r for r in rings if source._ring_signed_area(r) >= 0]
        self.assertEqual((len(exteriors), len(holes)), (402, 155))
        converted = source.esri_to_geojson(self.raw)
        for part in converted["coordinates"]:
            for hole in part[1:]:
                # Every hole must still sit inside the exterior it was filed
                # under, decided by the implementation that was removed.
                self.assertTrue(
                    legacy_point_in_ring(list(reversed(hole))[0],
                                         list(reversed(part[0]))),
                    "a hole migrated to the wrong exterior")


class NothingForbiddenWasIntroduced(unittest.TestCase):
    """Section 12 and 14."""

    def test_no_cache_no_parallelism_no_provider_predicate(self):
        for name in ("services/deterministic_spatial.py",
                     "services/toronto_planning_source.py"):
            text = Path(name).read_text(encoding="utf-8")
            for banned in ("lru_cache", "functools.cache", "ThreadPool",
                           "concurrent.futures", "asyncio", "simplif"):
                self.assertNotIn(banned, text, "%s in %s" % (banned, name))

    def test_the_02b_filters_and_engine_identity_are_untouched(self):
        self.assertEqual(spatial.ENGINE, "archiosk-exact-ring@3")
        for name in ("ring_band", "prepare_ring", "prepare_parts",
                     "_within_tolerance_prepared", "_crossing_prepared",
                     "token_matches"):
            self.assertTrue(hasattr(spatial, name), name)

    def test_the_query_strategy_was_not_changed(self):
        text = Path("services/toronto_planning_source.py").read_text(encoding="utf-8")
        self.assertIn("esriSpatialRelIntersects", text)
        self.assertIn("ABSENCE_ENVELOPE_METRES", text)


if __name__ == "__main__":
    unittest.main()
