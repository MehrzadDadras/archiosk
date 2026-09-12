"""CLAUDE-TORONTO-LIVE-01 - the live readers, proven without a live network.

Every test here is HERMETIC. `services.toronto_planning_source` gives `reader`
no default anywhere, so a test that forgets to supply one raises TypeError rather
than quietly reaching gis.toronto.ca - and `NeverReachesTheNetwork` asserts that
property directly rather than trusting it.

The payloads below are SHAPED like the City's real responses because they were
copied from them, including the parts that surprised us: a MapServer that returns
an empty geometry object while reporting success, and an authoritative zoning
polygon that is one exterior ring with five holes punched out of it.

Two things this file deliberately pins:

1. **The layer NAME is the contract.** `verify_layer` must refuse a drifted
   binding. Layer 18 of the City's planning service is called "Zoning Property
   Summary" and is not the zoning coverage; only a name check separates that trap
   from the real layer 3, "Zoning Area".

2. **Absence must be proven twice.** An empty response is also what a broken
   query returns, so `overlay_finding` may only assert absence when the City's
   own point query finds nothing AND our engine independently computes OUTSIDE
   for every polygon of that layer near the parcel.
"""
from __future__ import annotations

import json
import unittest
import urllib.parse

from services import deterministic_spatial as spatial
from services import planning_authority as authority
from services import toronto_planning_source as source


def _square(x, y, size, clockwise=True):
    """An Esri-style ring. Esri exterior rings wind CLOCKWISE."""
    ring = [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]
    return ring if clockwise else list(reversed(ring))


def _hole(x, y, size):
    return _square(x, y, size, clockwise=False)


class FakeService:
    """A stand-in for the City's ArcGIS, answering by URL shape."""

    def __init__(self, *, layer_names=None, responses=None):
        self.layer_names = layer_names or {}
        self.responses = responses or {}
        self.calls = []

    def __call__(self, url):
        self.calls.append(url)
        path = urllib.parse.urlparse(url).path
        if path.endswith("/query"):
            for key, payload in self.responses.items():
                if key in url:
                    return json.dumps(payload).encode("utf-8")
            return json.dumps({"features": []}).encode("utf-8")
        # A layer-metadata request: ".../MapServer/<id>"
        layer_id = int(path.rstrip("/").rsplit("/", 1)[-1])
        service = path.split("/services/")[1].split("/")[0]
        name = self.layer_names.get((service, layer_id), "Unknown Layer")
        return json.dumps({"name": name, "geometryType": "esriGeometryPolygon",
                           "maxRecordCount": 2000}).encode("utf-8")


REAL_NAMES = {
    ("cot_geospatial27", 101): "Address Point",
    ("cot_geospatial27", 36): "Property Boundary",
    ("cot_geospatial11", 3): "Zoning Area",
    ("cot_geospatial11", 9): "Zoning Height Overlay",
}


class TheLayerNameIsTheContract(unittest.TestCase):
    """A layer id is a position in a shared service, not a stable identifier."""

    def test_a_matching_name_verifies(self):
        reader = FakeService(layer_names=REAL_NAMES)
        verified = source.verify_layer(source.LAYER_ZONING_AREA, reader=reader)
        self.assertEqual(verified["name"], "Zoning Area")
        self.assertEqual(verified["layer_id"], 3)

    def test_a_drifted_name_is_refused_rather_than_answered(self):
        drifted = dict(REAL_NAMES)
        drifted[("cot_geospatial11", 3)] = "Zoning Property Summary"
        reader = FakeService(layer_names=drifted)
        with self.assertRaises(source.LayerIdentityError) as caught:
            source.verify_layer(source.LAYER_ZONING_AREA, reader=reader)
        self.assertIn("Zoning Property Summary", str(caught.exception))

    def test_the_real_trap_is_the_one_that_is_pinned(self):
        """'Zoning Property Summary' is a real layer that is NOT the coverage."""
        self.assertEqual(source.LAYER_ZONING_AREA[1], 3)
        self.assertNotEqual(source.LAYER_ZONING_AREA[1], 18)

    def test_verification_is_cached_so_one_layer_is_asked_once(self):
        reader = FakeService(layer_names=REAL_NAMES)
        cache = {}
        for _ in range(4):
            source.verify_layer(source.LAYER_ZONING_AREA, reader=reader,
                                cache=cache)
        self.assertEqual(len(reader.calls), 1)


class EsriRingsBecomeGeoJsonOrNothing(unittest.TestCase):
    """Winding order carries the exterior/hole distinction. Read it, don't guess."""

    def test_a_single_clockwise_ring_is_a_polygon(self):
        geometry = source.esri_to_geojson({"rings": [_square(0, 0, 10)]})
        self.assertEqual(geometry["type"], "Polygon")
        self.assertEqual(len(geometry["coordinates"]), 1)

    def test_counter_clockwise_rings_become_holes(self):
        geometry = source.esri_to_geojson(
            {"rings": [_square(0, 0, 100), _hole(20, 20, 10), _hole(50, 50, 5)]})
        self.assertEqual(len(geometry["coordinates"]), 3,
                         "one exterior plus two holes")

    def test_hole_order_in_the_array_does_not_matter(self):
        """The City does not promise the exterior ring comes first."""
        hole_first = source.esri_to_geojson(
            {"rings": [_hole(20, 20, 10), _square(0, 0, 100)]})
        exterior = hole_first["coordinates"][0]
        xs = [p[0] for p in exterior]
        self.assertEqual((min(xs), max(xs)), (0, 100),
                         "the large ring must be read as the exterior")

    def test_two_exteriors_become_a_multipolygon(self):
        geometry = source.esri_to_geojson(
            {"rings": [_square(0, 0, 10), _square(500, 500, 10)]})
        self.assertEqual(geometry["type"], "MultiPolygon")
        self.assertEqual(len(geometry["coordinates"]), 2)

    def test_each_hole_is_assigned_to_the_exterior_that_contains_it(self):
        geometry = source.esri_to_geojson({"rings": [
            _square(0, 0, 100), _square(500, 500, 100),
            _hole(520, 520, 10)]})
        self.assertEqual(geometry["type"], "MultiPolygon")
        self.assertEqual([len(part) for part in geometry["coordinates"]], [1, 2],
                         "the hole belongs to the second part, not the first")

    def test_a_hole_inside_no_exterior_returns_nothing(self):
        """Erasing it would turn an OUTSIDE into an INSIDE. Refuse instead."""
        self.assertIsNone(source.esri_to_geojson({"rings": [
            _square(0, 0, 10), _square(500, 500, 10), _hole(900, 900, 5)]}))

    def test_empty_and_malformed_geometry_return_nothing(self):
        for bad in (None, {}, {"rings": []}, {"rings": [[[0, 0], [1, 1]]]},
                    {"x": 1, "y": 2}):
            self.assertIsNone(source.esri_to_geojson(bad))


class TheEngineNowDecidesTheRealTopology(unittest.TestCase):
    """SUPERSEDES `test_holes_are_beyond_competence`.

    That test asserted version 1's blanket refusal of any polygon with a hole.
    The first real subject retired it: Toronto's authoritative zoning polygon for
    35 Taber Road is one exterior ring of 389 vertices with five holes. Refusing
    that refuses the ordinary case, and the even-odd rule decides it exactly.
    """

    def _relate(self, subject, layer):
        return spatial.relate({"crs": "EPSG:3857", "geometry": subject},
                              {"crs": "EPSG:3857", "geometry": layer})

    def test_a_parcel_in_a_holed_zone_is_inside(self):
        zone = source.esri_to_geojson(
            {"rings": [_square(0, 0, 1000), _hole(200, 200, 100)]})
        parcel = source.esri_to_geojson({"rings": [_square(600, 600, 30)]})
        token = self._relate(parcel, zone)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["spatial_basis"], spatial.BASIS_DETERMINISTIC)
        self.assertEqual(token["provenance"]["layer_hole_count"], 1)

    def test_a_parcel_inside_a_hole_is_outside_the_zone(self):
        """The case version 1 could not distinguish from any other hole case."""
        zone = source.esri_to_geojson(
            {"rings": [_square(0, 0, 1000), _hole(200, 200, 300)]})
        parcel = source.esri_to_geojson({"rings": [_square(300, 300, 40)]})
        token = self._relate(parcel, zone)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_OUTSIDE,
                         "a parcel in a hole is genuinely not in the zone")

    def test_a_parcel_straddling_a_hole_edge_intersects(self):
        zone = source.esri_to_geojson(
            {"rings": [_square(0, 0, 1000), _hole(200, 200, 300)]})
        parcel = source.esri_to_geojson({"rings": [_square(150, 150, 100)]})
        self.assertEqual(self._relate(parcel, zone)["spatial_relation"],
                         spatial.RELATION_INTERSECTS,
                         "a hole edge is a boundary of the zone")

    def test_a_parcel_enclosing_a_whole_hole_intersects(self):
        zone = source.esri_to_geojson(
            {"rings": [_square(0, 0, 1000), _hole(400, 400, 20)]})
        parcel = source.esri_to_geojson({"rings": [_square(300, 300, 300)]})
        self.assertEqual(self._relate(parcel, zone)["spatial_relation"],
                         spatial.RELATION_INTERSECTS,
                         "part of what the parcel covers is not in the zone")

    def test_a_parcel_inside_one_part_of_a_multipart_layer_is_inside(self):
        """Inside the union means inside some part. Arithmetic, not intent."""
        layer = source.esri_to_geojson(
            {"rings": [_square(0, 0, 100), _square(500, 500, 100)]})
        parcel = source.esri_to_geojson({"rings": [_square(520, 520, 20)]})
        token = self._relate(parcel, layer)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_INSIDE)
        self.assertEqual(token["provenance"]["layer_part_count"], 2)

    def test_a_parcel_in_the_gap_between_parts_is_outside(self):
        layer = source.esri_to_geojson(
            {"rings": [_square(0, 0, 100), _square(500, 500, 100)]})
        parcel = source.esri_to_geojson({"rings": [_square(250, 250, 20)]})
        self.assertEqual(self._relate(parcel, layer)["spatial_relation"],
                         spatial.RELATION_OUTSIDE)

    def test_a_parcel_straddling_one_part_intersects(self):
        layer = source.esri_to_geojson(
            {"rings": [_square(0, 0, 100), _square(500, 500, 100)]})
        parcel = source.esri_to_geojson({"rings": [_square(80, 80, 60)]})
        self.assertEqual(self._relate(parcel, layer)["spatial_relation"],
                         spatial.RELATION_INTERSECTS)

    def test_a_hole_in_a_far_part_does_not_affect_the_near_part(self):
        """Parts keep their own holes; a dropped or misassigned hole would lie."""
        layer = source.esri_to_geojson({"rings": [
            _square(0, 0, 100), _square(500, 500, 100), _hole(520, 520, 60)]})
        near = source.esri_to_geojson({"rings": [_square(40, 40, 20)]})
        self.assertEqual(self._relate(near, layer)["spatial_relation"],
                         spatial.RELATION_INSIDE)
        in_hole = source.esri_to_geojson({"rings": [_square(540, 540, 20)]})
        self.assertEqual(self._relate(in_hole, layer)["spatial_relation"],
                         spatial.RELATION_OUTSIDE)

    def test_a_malformed_hole_is_refused_not_silently_dropped(self):
        """A vanished hole turns an OUTSIDE into an INSIDE. Refuse instead."""
        broken = {"type": "Polygon", "coordinates": [
            [[0, 0], [0, 1000], [1000, 1000], [1000, 0], [0, 0]],
            [[200, 200], [200, 300]]]}
        token = self._relate(
            source.esri_to_geojson({"rings": [_square(600, 600, 30)]}), broken)
        self.assertEqual(token["spatial_relation"], spatial.RELATION_AMBIGUOUS)
        self.assertEqual(token["reason"], spatial.REASON_INVALID)


class AddressResolution(unittest.TestCase):

    def _reader(self, address_features, parcel_features):
        return FakeService(layer_names=REAL_NAMES, responses={
            "cot_geospatial27/FeatureServer/101/query":
                {"features": address_features,
                 "spatialReference": {"wkid": 102100}},
            "cot_geospatial27/FeatureServer/36/query":
                {"features": parcel_features,
                 "spatialReference": {"wkid": 102100}},
        })

    ADDRESS = [{"attributes": {"ADDRESS_POINT_ID": 9655872,
                               "ADDRESS_FULL": "35 Taber Rd",
                               "WARD_NAME": "Etobicoke North"},
                "geometry": {"x": -8858454.18, "y": 5421997.83}}]
    PARCEL = [{"attributes": {"PARCELID": 5229145, "PLAN_NAME": "07358",
                              "STATEDAREA": "2302.788208 sq.m"},
               "geometry": {"rings": [_square(-8858500, 5421950, 90)]}}]

    def test_one_address_and_one_parcel_resolves(self):
        resolved = source.resolve_address(
            "35 Taber Road, Etobicoke, Toronto",
            reader=self._reader(self.ADDRESS, self.PARCEL))
        self.assertEqual(resolved["parcel_count"], 1)
        self.assertEqual(resolved["parcel_identifier"], "TOR-PARCEL-5229145")
        self.assertEqual(resolved["normalized_address"], "35 Taber Rd")
        self.assertEqual(resolved["crs"], "EPSG:3857")
        self.assertEqual(resolved["geometry"]["type"], "Polygon")

    def test_the_street_suffix_is_not_used_for_matching(self):
        """The City stores 'Taber Rd'; a person writes 'Taber Road'."""
        self.assertEqual(source._split_address("35 Taber Road, Toronto"),
                         ("35", "Taber"))
        self.assertEqual(source._split_address("35 Taber Rd"), ("35", "Taber"))

    def test_an_unparseable_address_resolves_to_nothing(self):
        for bad in (None, "", "Toronto", "Taber Road", 35):
            self.assertEqual(source._split_address(bad), (None, None))

    def test_no_address_match_yields_zero_parcels(self):
        resolved = source.resolve_address(
            "9999 Nowhere Street, Toronto", reader=self._reader([], []))
        self.assertEqual(resolved["parcel_count"], 0)
        self.assertIn("no official City address point", resolved["resolution_note"])

    def test_several_address_points_is_not_one_subject(self):
        resolved = source.resolve_address(
            "35 Taber Road", reader=self._reader(self.ADDRESS * 3, self.PARCEL))
        self.assertEqual(resolved["parcel_count"], 3)
        self.assertNotIn("parcel_identifier", resolved)

    def test_several_parcels_carries_no_subject_geometry(self):
        resolved = source.resolve_address(
            "35 Taber Road", reader=self._reader(self.ADDRESS, self.PARCEL * 2))
        self.assertEqual(resolved["parcel_count"], 2)
        self.assertIsNone(resolved.get("geometry"))

    def test_a_multipart_parcel_is_carried_through_not_discarded(self):
        """A parcel in two pieces either side of a lane is a real parcel."""
        multipart = [{"attributes": {"PARCELID": 1},
                      "geometry": {"rings": [_square(0, 0, 10),
                                             _square(500, 500, 10)]}}]
        resolved = source.resolve_address(
            "35 Taber Road", reader=self._reader(self.ADDRESS, multipart))
        self.assertEqual(resolved["geometry"]["type"], "MultiPolygon")
        self.assertNotIn("resolution_note", resolved)

    def test_unreadable_parcel_geometry_is_reported_not_guessed(self):
        orphaned = [{"attributes": {"PARCELID": 1},
                     "geometry": {"rings": [_square(0, 0, 10),
                                            _hole(900, 900, 5)]}}]
        resolved = source.resolve_address(
            "35 Taber Road", reader=self._reader(self.ADDRESS, orphaned))
        self.assertIsNone(resolved["geometry"])
        self.assertIn("unreadable", resolved["resolution_note"])


class AbsenceMustBeProvenTwice(unittest.TestCase):
    """An empty response is also what a broken query returns."""

    POINT = {"x": 0.0, "y": 0.0}
    SUBJECT = {"type": "Polygon",
               "coordinates": [[[-10, -10], [-10, 10], [10, 10], [10, -10],
                                [-10, -10]]]}

    def _reader(self, point_features, nearby_features):
        """Point and envelope queries both hit the FeatureServer now, so the
        fake distinguishes them the way the real service would - by the
        geometryType the caller asked with."""
        return FakeService(
            layer_names={("cot_geospatial11", 9): "Zoning Height Overlay"},
            responses={"esriGeometryPoint": {"features": point_features},
                       "esriGeometryEnvelope": {"features": nearby_features}})

    def test_a_covering_overlay_is_reported_present_WITH_A_TOKEN(self):
        """Version 1 reported a covering overlay with NO spatial basis at all,
        so a height limit that genuinely governs the site arrived as weaker
        evidence than the absences beside it."""
        covering = [{"attributes": {"HT_STRING": "HT 14.0"},
                     "geometry": {"rings": [_square(-500, -500, 1000)]}}]
        finding = source.overlay_finding(
            source.LAYER_ZONING_HEIGHT, self.SUBJECT, self.POINT,
            reader=self._reader(covering, []))
        self.assertTrue(finding["present"])
        self.assertFalse(finding["absence_established"])
        self.assertEqual(finding["attributes"]["HT_STRING"], "HT 14.0")
        self.assertEqual(finding["token"]["spatial_relation"],
                         spatial.RELATION_INSIDE)
        self.assertEqual(finding["token"]["spatial_basis"],
                         spatial.BASIS_DETERMINISTIC)

    def test_absence_is_established_when_every_nearby_polygon_is_outside(self):
        nearby = [{"attributes": {}, "geometry": {"rings": [_square(500, 500, 50)]}},
                  {"attributes": {}, "geometry": {"rings": [_square(900, 900, 50)]}}]
        finding = source.overlay_finding(
            source.LAYER_ZONING_HEIGHT, self.SUBJECT, self.POINT,
            reader=self._reader([], nearby))
        self.assertTrue(finding["absence_established"])
        self.assertEqual(finding["computed_outside"], 2)
        self.assertEqual(finding["undecided"], 0)

    def test_an_empty_envelope_still_establishes_absence(self):
        finding = source.overlay_finding(
            source.LAYER_ZONING_HEIGHT, self.SUBJECT, self.POINT,
            reader=self._reader([], []))
        self.assertTrue(finding["absence_established"])
        self.assertEqual(finding["polygons_in_envelope"], 0)

    def test_an_undecidable_nearby_polygon_blocks_the_claim(self):
        """Our engine could not decide, so absence is NOT asserted.

        The fixture is an ORPHANED HOLE - one that lies inside no exterior ring.
        Multipart geometry used to serve here and no longer can: the engine
        computes it exactly now, so using it would test nothing.
        """
        orphaned = [{"attributes": {},
                     "geometry": {"rings": [_square(500, 500, 50),
                                            _hole(2000, 2000, 10)]}}]
        finding = source.overlay_finding(
            source.LAYER_ZONING_HEIGHT, self.SUBJECT, self.POINT,
            reader=self._reader([], orphaned))
        self.assertFalse(finding["absence_established"])
        self.assertEqual(finding["undecided"], 1)
        self.assertIn("absence NOT asserted", finding["note"])

    def test_an_overlapping_nearby_polygon_contradicts_the_point_query(self):
        """The City said no and our engine says yes. Do not assert absence."""
        overlapping = [{"attributes": {},
                        "geometry": {"rings": [_square(-5, -5, 50)]}}]
        finding = source.overlay_finding(
            source.LAYER_ZONING_HEIGHT, self.SUBJECT, self.POINT,
            reader=self._reader([], overlapping))
        self.assertFalse(finding["absence_established"])
        self.assertEqual(finding["overlapping"], 1)


class NeverReachesTheNetwork(unittest.TestCase):
    """The hermetic guarantee, asserted rather than trusted."""

    def test_no_reader_has_a_default(self):
        import inspect
        for name in ("verify_layer", "query_layer", "resolve_address",
                     "zoning_at", "overlay_finding", "acquire_zoning_bylaw",
                     "acquire_official_plan", "acquire_exception",
                     "heritage_register_near", "discover_official_plan"):
            signature = inspect.signature(getattr(source, name))
            parameter = signature.parameters.get("reader")
            self.assertIsNotNone(parameter, "%s must take a reader" % name)
            self.assertIs(parameter.default, inspect.Parameter.empty,
                          "%s: a default reader would let a forgetful test reach "
                          "the City of Toronto" % name)

    def test_the_live_reader_refuses_a_non_official_host(self):
        read = source.live_reader()
        for url in ("https://housesigma.com/zoning",
                    "https://someconsultant.example.com/report.pdf",
                    "file:///etc/passwd"):
            with self.assertRaises(PermissionError):
                read(url)

    def test_the_live_reader_accepts_only_official_hosts(self):
        for url in (source.ARCGIS_ROOT, source.ZONING_BYLAW_URL):
            self.assertEqual(authority.classify_source(url)["source_class"],
                             authority.CLASS_OFFICIAL)

    def test_every_query_goes_through_verification_first(self):
        reader = FakeService(layer_names=REAL_NAMES, responses={
            "FeatureServer/3/query": {"features": []}})
        source.query_layer(source.LAYER_ZONING_AREA, reader=reader, where="1=1")
        self.assertEqual(len(reader.calls), 2)
        self.assertNotIn("/query", reader.calls[0],
                         "the layer identity is checked before it is trusted")

    def test_geometry_queries_use_the_featureserver(self):
        """Measured: the MapServer returns an empty geometry object instead."""
        reader = FakeService(layer_names=REAL_NAMES, responses={
            "FeatureServer/3/query": {"features": []}})
        source.query_layer(source.LAYER_ZONING_AREA, reader=reader,
                           with_geometry=True, where="1=1")
        self.assertIn("/FeatureServer/3/query", reader.calls[-1])

    def test_attribute_only_queries_use_the_mapserver(self):
        reader = FakeService(layer_names=REAL_NAMES, responses={
            "MapServer/3/query": {"features": []}})
        source.query_layer(source.LAYER_ZONING_AREA, reader=reader,
                           with_geometry=False, where="1=1")
        self.assertIn("/MapServer/3/query", reader.calls[-1])


class TheAuthorityRecordHoldsBytes(unittest.TestCase):

    def test_a_retrieved_bylaw_can_ground_authority_says(self):
        outcome = source.acquire_zoning_bylaw(
            reader=lambda url: b"%PDF-1.4 By-law 569-2013",
            retrieved_at="2026-09-12T00:00:00Z")
        self.assertTrue(outcome["acquired"])
        record = outcome["record"]
        self.assertEqual(record["source_class"], authority.CLASS_OFFICIAL)
        self.assertTrue(record["provenance_hash"].startswith("sha256:"))
        self.assertTrue(authority.may_satisfy_authority_says(record))

    def test_a_failed_retrieval_cannot_ground_authority_says(self):
        def refuse(url):
            raise OSError("timed out")
        outcome = source.acquire_zoning_bylaw(
            reader=refuse, retrieved_at="2026-09-12T00:00:00Z")
        self.assertFalse(outcome["acquired"])
        self.assertIsNone(outcome["record"])

    def test_the_bylaw_url_is_the_city_not_a_summary_of_it(self):
        self.assertIn("toronto.ca", source.ZONING_BYLAW_URL)
        self.assertTrue(source.ZONING_BYLAW_URL.endswith("law0569.pdf"))


if __name__ == "__main__":
    unittest.main()
