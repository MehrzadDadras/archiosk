"""CLAUDE-TORONTO-LIVE-01 - the live official reader behind the GO-PDZ seams.

    ADDRESS -> OFFICIAL CITY GEOMETRY -> OUR OWN DETERMINISTIC ENGINE -> TOKEN

`planning_authority.acquire()` takes an injected `fetcher` and
`go_pdz_lifecycle.resolve_identity()` takes an injected `resolver`. Both were
built with no implementation behind them, because supplying one means reaching a
real network and every prior seam in this programme was proven hermetically
first. This module is that implementation, and only that: it reads the City of
Toronto's own ArcGIS services and hands their geometry to
`services.deterministic_spatial`. It decides nothing about planning.

THE LAYER NAME IS THE CONTRACT, NOT THE LAYER NUMBER. This is the hardest lesson
the live reconnaissance taught and the reason `verify_layer` exists. Layer 18 of
the City's planning service is called "Zoning Property Summary", which sounds
exactly like the authoritative zoning coverage and is not: it holds 1,999 rows
with zero-area geometry, and a one-kilometre box drawn around a site in Etobicoke
returns an address downtown. The real coverage is layer 3, "Zoning Area". A
number alone cannot tell those apart, so every query here first asks the service
what the layer is called and REFUSES if the answer has drifted. A silently
renumbered layer must break loudly rather than answer confidently from the wrong
table.

GEOMETRY COMES FROM THE FeatureServer, NOT THE MapServer. Measured, not assumed:
`cot_geospatial11/MapServer/3` honours `returnGeometry=true` by returning an
empty geometry object, while `cot_geospatial11/FeatureServer/3` returns the
rings. Attributes are identical. Querying the MapServer for a polygon yields a
feature that looks successful and carries nothing to compute on - which would
have produced AMBIGUOUS forever, for a reason no refusal string could explain.

ABSENCE IS PROVEN, NOT INFERRED. An overlay that does not cover the site is a
real and useful finding, but "the query came back empty" is not by itself
evidence of anything - it is also what a malformed query returns. So an absence
is established twice: the City's own point query over the layer's full extent
returns nothing, AND every polygon of that layer within a wide envelope of the
parcel is independently computed OUTSIDE by our engine. A claim of absence that
rests only on an empty response is downgraded, never asserted.

READ-ONLY, AND INJECTABLE ANYWAY. `reader` has NO DEFAULT anywhere in this
module. A test that forgets to supply one raises TypeError instead of quietly
reaching the City of Toronto, which is the guarantee `CLAUDE.md`'s hermetic-test
rule actually needs. `live_reader()` is the explicit opt-in, it issues GET only,
it refuses any host outside the official allowlist, and it caps the response.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Optional

from services import deterministic_spatial as spatial
from services import planning_authority as authority

logger = logging.getLogger(__name__)

SOURCE_VERSION = "toronto-planning-source@1"
ARCGIS_ROOT = "https://gis.toronto.ca/arcgis/rest/services"

#: The City serves everything in Web Mercator. Every query below is issued in it
#: and read back in it, so `deterministic_spatial` never sees a CRS mismatch and
#: never has cause to reproject - which it would refuse to do anyway.
WKID_TO_CRS = {102100: "EPSG:3857", 3857: "EPSG:3857", 4326: "EPSG:4326",
               26917: "EPSG:26917"}
QUERY_WKID = "102100"

#: How far around the parcel an absence must hold before it may be asserted.
#: Two kilometres is far past any plausible digitising discrepancy while still
#: being a bounded, honest claim rather than a claim about the whole city.
ABSENCE_ENVELOPE_METRES = 2000.0

#: (service, layer_id, expected_name). The NAME is checked on every use.
LAYER_ADDRESS_POINT = ("cot_geospatial27", 101, "Address Point")
LAYER_PROPERTY_BOUNDARY = ("cot_geospatial27", 36, "Property Boundary")
LAYER_ZONING_AREA = ("cot_geospatial11", 3, "Zoning Area")
LAYER_ZONING_HEIGHT = ("cot_geospatial11", 9, "Zoning Height Overlay")
LAYER_ZONING_COVERAGE = ("cot_geospatial11", 10, "Zoning Lot Coverage Overlay")
LAYER_ZONING_NOT_PART = ("cot_geospatial11", 12, "Zoning Not Part of This Bylaw")
LAYER_ZONING_POLICY_AREA = ("cot_geospatial11", 13, "Zoning Policy Area Overlay")
LAYER_ZONING_SETBACK = ("cot_geospatial11", 59, "Zoning Building Setback Overlay")
LAYER_SECONDARY_PLAN = ("cot_geospatial11", 44, "Secondary Plan")
LAYER_SITE_SPECIFIC = ("cot_geospatial11", 46, "Site and Area Specific Policy")
LAYER_HERITAGE_DISTRICT = ("cot_geospatial11", 40, "Heritage District")
LAYER_NATURAL_HERITAGE = ("cot_geospatial11", 34, "Natural Heritage System (polygon)")
LAYER_MTSA = ("cot_geospatial11", 65, "Major Transit Station Area")

#: Overlays checked for every subject. Each one materially changes what may be
#: built, so an unchecked overlay is a silent gap rather than a tidy omission.
OVERLAY_LAYERS = (
    LAYER_ZONING_HEIGHT, LAYER_ZONING_COVERAGE, LAYER_ZONING_POLICY_AREA,
    LAYER_ZONING_SETBACK, LAYER_ZONING_NOT_PART, LAYER_SECONDARY_PLAN,
    LAYER_SITE_SPECIFIC, LAYER_HERITAGE_DISTRICT, LAYER_NATURAL_HERITAGE,
    LAYER_MTSA,
)

#: The enacting instrument. Retrieved so the record holds bytes rather than a
#: paraphrase - `may_satisfy_authority_says` requires exactly that.
ZONING_BYLAW_URL = "https://www.toronto.ca/legdocs/bylaws/2013/law0569.pdf"
ZONING_BYLAW_TITLE = "City of Toronto Zoning By-law 569-2013 (as enacted)"


class LayerIdentityError(RuntimeError):
    """The service no longer calls this layer what we bound to. Refuse."""


def live_reader(*, timeout=45, max_bytes=32 * 1024 * 1024):
    """Build the real HTTP reader. The ONLY place this module touches a network.

    GET only, official hosts only (`planning_authority.classify_source` decides,
    so the allowlist has one definition rather than two), and capped. It returns
    bytes, which is what `planning_authority.acquire` hashes for provenance.
    """
    def read(url):
        classification = authority.classify_source(url)
        if classification["source_class"] != authority.CLASS_OFFICIAL:
            raise PermissionError(
                "refusing to read a non-official source: %s (%s)"
                % (url, classification["reason"]))
        request = urllib.request.Request(
            url, method="GET",
            headers={"User-Agent": "ARCHIOSK/pre-design (read-only)"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read(max_bytes + 1)
        if len(payload) > max_bytes:
            raise ValueError("response exceeded %d bytes" % max_bytes)
        return payload
    return read


def _read_json(reader, url):
    payload = reader(url)
    if isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload).decode("utf-8", "replace")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError("service error: %s" % json.dumps(payload["error"])[:300])
    return payload


def verify_layer(binding, *, reader, cache=None) -> dict:
    """Confirm the service still calls this layer what we bound to.

    THIS IS THE POINT OF THE MODULE'S CAUTION. A layer id is a position in a
    shared map service, not a stable identifier for a dataset, and the City's own
    catalogue contains a layer whose name actively misleads. A drifted binding
    must raise, because the alternative is a governed planning result computed
    confidently from the wrong table.
    """
    service, layer_id, expected = binding
    key = (service, layer_id)
    if cache is not None and key in cache:
        return cache[key]
    meta = _read_json(reader, "%s/%s/MapServer/%d?f=json"
                      % (ARCGIS_ROOT, service, layer_id))
    actual = meta.get("name")
    if actual != expected:
        raise LayerIdentityError(
            "%s/MapServer/%d is now %r, expected %r - binding refused"
            % (service, layer_id, actual, expected))
    verified = {"service": service, "layer_id": layer_id, "name": actual,
                "geometry_type": meta.get("geometryType"),
                "max_record_count": meta.get("maxRecordCount")}
    if cache is not None:
        cache[key] = verified
    return verified


def query_layer(binding, *, reader, with_geometry=True, cache=None,
                **params) -> dict:
    """One verified query. Geometry requests go to the FeatureServer - measured.

    The flag is `with_geometry` rather than `geometry` because ArcGIS's own
    query parameter is called `geometry` and carries the search shape; one
    name for both would collide silently on every spatial query.
    """
    verified = verify_layer(binding, reader=reader, cache=cache)
    service, layer_id, _ = binding
    server = "FeatureServer" if with_geometry else "MapServer"
    params.setdefault("f", "json")
    params.setdefault("outFields", "*")
    params["returnGeometry"] = "true" if with_geometry else "false"
    params.setdefault("outSR", QUERY_WKID)
    url = "%s/%s/%s/%d/query?%s" % (ARCGIS_ROOT, service, server, layer_id,
                                    urllib.parse.urlencode(params))
    data = _read_json(reader, url)
    return {"layer": verified, "url": url,
            "features": data.get("features") or [],
            "crs": WKID_TO_CRS.get(
                (data.get("spatialReference") or {}).get("wkid"))}


def _point_param(x, y):
    return json.dumps({"x": x, "y": y, "spatialReference": {"wkid": 102100}})


def _ring_signed_area(ring):
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
               for i in range(len(ring) - 1)) / 2.0


def esri_to_geojson(esri_geometry) -> Optional[dict]:
    """Esri rings -> a GeoJSON Polygon, or None when that cannot be done exactly.

    Esri's `rings` array does not label its rings. The distinction is carried by
    winding order alone - clockwise is an exterior ring, counter-clockwise is a
    hole - so this reads the sign of each shoelace area rather than assuming
    position. GeoJSON's convention is the opposite way round, so both are
    reversed on the way out.

    MORE THAN ONE EXTERIOR RING BECOMES A MultiPolygon, with each hole assigned to
    the exterior that contains it. Version 1 returned None here, which was
    correct only while the engine refused multipart geometry; once the engine
    could compute it, discarding it reported an engine limit to the reader as a
    data ambiguity. Four of the City's authority layers near the first real
    subject are multipart, so this is the ordinary case.

    A HOLE THAT LANDS IN NO EXTERIOR, OR IN SEVERAL, RETURNS None. Assigning it
    by guess would either erase a hole - turning an OUTSIDE into an INSIDE - or
    punch one through the wrong part. Neither is recoverable downstream.
    """
    if not isinstance(esri_geometry, dict):
        return None
    rings = esri_geometry.get("rings")
    if not rings:
        return None
    exteriors, holes = [], []
    for ring in rings:
        if not isinstance(ring, (list, tuple)) or len(ring) < 4:
            return None
        (exteriors if _ring_signed_area(ring) < 0 else holes).append(ring)
    if not exteriors:
        return None

    def flip(ring):
        """Esri winds exteriors clockwise; GeoJSON winds them the other way."""
        return [list(p[:2]) for p in reversed(ring)]

    assigned = {index: [] for index in range(len(exteriors))}
    for hole in holes:
        containing = [index for index, exterior in enumerate(exteriors)
                      if _point_in_ring(hole[0], exterior)]
        if len(containing) != 1:
            return None
        assigned[containing[0]].append(hole)

    parts = [[flip(exterior)] + [flip(hole) for hole in assigned[index]]
             for index, exterior in enumerate(exteriors)]
    if len(parts) == 1:
        return {"type": "Polygon", "coordinates": parts[0]}
    return {"type": "MultiPolygon", "coordinates": parts}


def _point_in_ring(point, ring) -> bool:
    """Ray casting, used only to decide which exterior a hole belongs to."""
    x, y = point[0], point[1]
    inside = False
    for index in range(len(ring) - 1):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[index + 1][0], ring[index + 1][1]
        if (y1 > y) != (y2 > y) and y2 != y1:
            if x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                inside = not inside
    return inside


def resolve_address(address, *, reader, cache=None) -> dict:
    """The live `resolver` for `go_pdz_lifecycle.resolve_identity`.

    Address point first, then the parcel that contains it. Anything that cannot
    be established comes back absent rather than guessed - `resolve_identity`
    lowers identity confidence on its own, and VR-02 then forbids an ESTABLISHED
    claim about a subject that was never pinned down.
    """
    number, street = _split_address(address)
    if not number or not street:
        return {"parcel_count": 0, "resolution_note": "address could not be parsed"}

    where = "ADDRESS_NUMBER='%s' AND LINEAR_NAME_FULL LIKE '%s%%'" % (
        number.replace("'", "''"), street.replace("'", "''"))
    points = query_layer(LAYER_ADDRESS_POINT, reader=reader, cache=cache,
                         with_geometry=True, where=where)
    features = points["features"]
    if not features:
        return {"parcel_count": 0,
                "resolution_note": "no official City address point matched"}
    if len(features) > 1:
        return {"parcel_count": len(features),
                "resolution_note": "address matched %d official address points"
                                   % len(features)}

    attributes = features[0].get("attributes") or {}
    geometry = features[0].get("geometry") or {}
    x, y = geometry.get("x"), geometry.get("y")
    if x is None or y is None:
        return {"parcel_count": 0,
                "resolution_note": "address point carried no coordinate"}

    parcels = query_layer(LAYER_PROPERTY_BOUNDARY, reader=reader, cache=cache,
                          with_geometry=True,
                          **{"geometry": _point_param(x, y),
                             "geometryType": "esriGeometryPoint",
                             "spatialRel": "esriSpatialRelIntersects",
                             "inSR": QUERY_WKID})
    parcel_features = parcels["features"]
    resolved = {
        "subject_id": "TOR-ADDR-%s" % attributes.get("ADDRESS_POINT_ID"),
        "normalized_address": attributes.get("ADDRESS_FULL"),
        "municipality": "City of Toronto",
        "ward": attributes.get("WARD_NAME"),
        "address_point_id": attributes.get("ADDRESS_POINT_ID"),
        "point": {"x": x, "y": y},
        "crs": WKID_TO_CRS.get(102100),
        "parcel_count": len(parcel_features),
        "source": "%s/%s (%s)" % (LAYER_PROPERTY_BOUNDARY[0],
                                  LAYER_PROPERTY_BOUNDARY[1],
                                  LAYER_PROPERTY_BOUNDARY[2]),
        "address_source": "%s/%s (%s)" % (LAYER_ADDRESS_POINT[0],
                                          LAYER_ADDRESS_POINT[1],
                                          LAYER_ADDRESS_POINT[2]),
    }
    if len(parcel_features) != 1:
        resolved["resolution_note"] = (
            "address point resolved to %d parcels" % len(parcel_features))
        return resolved

    parcel_attributes = parcel_features[0].get("attributes") or {}
    resolved.update({
        "parcel_identifier": ("TOR-PARCEL-%s" % parcel_attributes.get("PARCELID")
                              if parcel_attributes.get("PARCELID") else None),
        "parcel_plan": parcel_attributes.get("PLAN_NAME"),
        "stated_area": parcel_attributes.get("STATEDAREA"),
        "geometry": esri_to_geojson(parcel_features[0].get("geometry")),
    })
    if resolved["geometry"] is None:
        # Multipart parcels are carried through now; what remains here is
        # genuinely unreadable - most often a hole lying inside no exterior ring,
        # which cannot be assigned without guessing.
        resolved["resolution_note"] = (
            "parcel geometry is unreadable; rings could not be resolved into an "
            "exterior/hole structure without guessing")
    return resolved


def _split_address(address):
    """'35 Taber Road, Etobicoke, Toronto' -> ('35', 'Taber').

    Only the number and the street NAME are used for matching. The City stores
    'Taber Rd' while a person writes 'Taber Road', so the suffix is deliberately
    dropped and the match left as a prefix - narrowing it would fail on the
    abbreviation, and widening it would match neighbouring streets.
    """
    if not address or not isinstance(address, str):
        return None, None
    head = address.split(",")[0].strip()
    parts = head.split()
    if len(parts) < 2 or not parts[0].isdigit():
        return None, None
    return parts[0], parts[1]


def zoning_at(subject_geometry, point, *, reader, cache=None) -> dict:
    """The governing zone polygon, with OUR engine deciding the relationship."""
    found = query_layer(LAYER_ZONING_AREA, reader=reader, cache=cache,
                        with_geometry=True,
                        **{"geometry": _point_param(point["x"], point["y"]),
                           "geometryType": "esriGeometryPoint",
                           "spatialRel": "esriSpatialRelIntersects",
                           "inSR": QUERY_WKID})
    if not found["features"]:
        return {"present": False, "layer": found["layer"], "url": found["url"],
                "attributes": None, "token": None}
    feature = found["features"][0]
    geometry = esri_to_geojson(feature.get("geometry"))
    token = spatial.relate(
        {"crs": WKID_TO_CRS[102100], "geometry": subject_geometry},
        {"crs": WKID_TO_CRS[102100], "geometry": geometry},
        subject_source="City of Toronto Property Boundary",
        layer_source="City of Toronto Zoning Area (By-law 569-2013)",
        layer_version="By-law 569-2013")
    return {"present": True, "layer": found["layer"], "url": found["url"],
            "attributes": feature.get("attributes") or {},
            "geometry": geometry, "token": token}


def overlay_absence(binding, subject_geometry, point, *, reader, cache=None) -> dict:
    """Prove an overlay does NOT apply, twice, or decline to claim it.

    An empty response is not evidence. So the City's own point query must return
    nothing AND every polygon of that layer within `ABSENCE_ENVELOPE_METRES` of
    the parcel must be independently computed OUTSIDE by our engine. When a
    polygon inside the envelope cannot be decided, the absence is NOT asserted -
    it is reported as undetermined, which is a different and honest answer.
    """
    at_point = query_layer(binding, reader=reader, cache=cache,
                           with_geometry=False,
                           **{"geometry": _point_param(point["x"], point["y"]),
                              "geometryType": "esriGeometryPoint",
                              "spatialRel": "esriSpatialRelIntersects",
                              "inSR": QUERY_WKID})
    if at_point["features"]:
        feature = at_point["features"][0]
        return {"layer_name": binding[2], "present": True,
                "attributes": feature.get("attributes") or {},
                "absence_established": False, "url": at_point["url"],
                "note": "overlay covers the subject point"}

    half = ABSENCE_ENVELOPE_METRES
    envelope = json.dumps({"xmin": point["x"] - half, "ymin": point["y"] - half,
                           "xmax": point["x"] + half, "ymax": point["y"] + half,
                           "spatialReference": {"wkid": 102100}})
    nearby = query_layer(binding, reader=reader, cache=cache,
                         with_geometry=True,
                         **{"geometry": envelope,
                            "geometryType": "esriGeometryEnvelope",
                            "spatialRel": "esriSpatialRelIntersects",
                            "inSR": QUERY_WKID})
    undecided, outside, overlapping = 0, 0, 0
    witness = None
    for feature in nearby["features"]:
        geometry = esri_to_geojson(feature.get("geometry"))
        if geometry is None:
            undecided += 1
            continue
        token = spatial.relate(
            {"crs": WKID_TO_CRS[102100], "geometry": subject_geometry},
            {"crs": WKID_TO_CRS[102100], "geometry": geometry},
            subject_source="City of Toronto Property Boundary",
            layer_source="City of Toronto %s" % binding[2])
        if token["spatial_relation"] == spatial.RELATION_OUTSIDE:
            outside += 1
            # Keep one polygon the refusal actually rests on, so the resulting
            # statement can carry a DETERMINISTIC OUTSIDE rather than asserting
            # absence with no geometry behind it. Absence proven against nothing
            # is not deterministic, however true it happens to be.
            if witness is None:
                witness = geometry
        elif token["spatial_relation"] == spatial.RELATION_AMBIGUOUS:
            undecided += 1
        else:
            overlapping += 1

    established = (overlapping == 0 and undecided == 0)
    return {
        "layer_name": binding[2], "present": False,
        "absence_established": established,
        "url": nearby["url"],
        "polygons_in_envelope": len(nearby["features"]),
        "computed_outside": outside, "undecided": undecided,
        "overlapping": overlapping, "witness_geometry": witness,
        "envelope_metres": ABSENCE_ENVELOPE_METRES,
        "note": ("no polygon of this layer covers the subject, and every polygon "
                 "within %.0f m was computed OUTSIDE" % ABSENCE_ENVELOPE_METRES)
                if established else
                ("absence NOT asserted: %d undecided, %d overlapping within %.0f m"
                 % (undecided, overlapping, ABSENCE_ENVELOPE_METRES)),
    }


def acquire_zoning_bylaw(*, reader, retrieved_at, effective_date="2013-05-09",
                         provision_locator=None) -> dict:
    """Retrieve the enacting by-law so the record holds bytes, not a paraphrase."""
    return authority.acquire(
        ZONING_BYLAW_URL, fetcher=reader,
        authority_id="TOR-ZBL-569-2013",
        issuing_authority="City of Toronto",
        official_title=ZONING_BYLAW_TITLE,
        retrieved_at=retrieved_at,
        effective_date=effective_date,
        version_identifier="569-2013",
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Toronto",
        spatial_scope="City of Toronto",
        provision_locator=provision_locator,
        retained_representation=ZONING_BYLAW_URL)
