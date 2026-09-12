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
import re
import urllib.parse
import urllib.request
from typing import Optional

from services import deterministic_spatial as spatial
from services import planning_authority as authority

logger = logging.getLogger(__name__)

SOURCE_VERSION = "toronto-planning-source@2"
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

#: Individually listed heritage properties. A POINT layer, so it is handled
#: apart from the polygon overlays and reported WITHOUT a deterministic
#: containment claim - see `heritage_register_near`.
LAYER_HERITAGE_REGISTER = ("cot_geospatial11", 56, "Heritage Register")

#: The enacting instrument, and the DEFAULT only. The City's zoning record names
#: the by-law that actually governs each zone in `BYLAW_DOCLINK`, and for the
#: second live subject that was `2021/law0266.pdf`, not this one. Citing the
#: enacting by-law for a zone amended eight years later is a false citation that
#: happens to look right, so `zoning_bylaw_url_for` prefers the City's own link.
BYLAW_DOC_BASE = "https://www.toronto.ca/legdocs/bylaws/"
ZONING_BYLAW_URL = BYLAW_DOC_BASE + "2013/law0569.pdf"
ZONING_BYLAW_TITLE = "City of Toronto Zoning By-law 569-2013 (as enacted)"

#: Where the by-law's own chapter and exception pages are published. Measured:
#: the `/zoning/bylaw_amendments/ZBL_NewProvision/` path in the City's own
#: attribute values 404s; `/zoning/` serves them.
ZONING_CHAPTER_BASE = "https://www.toronto.ca/zoning/"

#: The consolidated Official Plan. Section 4's fallback: the land use
#: designation is published only as map schedules inside this document, so the
#: document is retained as a real authority and the DESIGNATION stays
#: undetermined. An authority you cannot compute against is still an authority.
OFFICIAL_PLAN_URL = ("https://www.toronto.ca/city-government/planning-development/"
                     "official-plan-guidelines/official-plan/")
OFFICIAL_PLAN_CHAPTERS_URL = OFFICIAL_PLAN_URL + "chapters-1-5/"
OFFICIAL_PLAN_TITLE = "City of Toronto Official Plan (consolidation)"

#: The consolidation is republished at a new dated path each time it is
#: consolidated, so the link is DISCOVERED from the City's own index page rather
#: than pinned here. Pinning it would silently serve a superseded Plan the moment
#: the City consolidated again - the version would still look retrieved, and
#: would be wrong in the direction that matters.
_CONSOLIDATION_LINK = re.compile(
    r'href="(?P<url>[^"]+\.pdf)"[^>]*>(?P<label>[^<]{0,90})', re.IGNORECASE)


class LayerIdentityError(RuntimeError):
    """The service no longer calls this layer what we bound to. Refuse."""


def live_reader(*, timeout=45, max_bytes=32 * 1024 * 1024, attested_by=None):
    """Build the real HTTP reader. The ONLY place this module touches a network.

    GET only, official hosts only (`planning_authority.classify_source` decides,
    so the allowlist has one definition rather than two), and capped. It returns
    bytes, which is what `planning_authority.acquire` hashes for provenance.

    `attested_by` names an official catalogue that publishes on a hosting
    platform, and it grants READ ACCESS to that platform - nothing more.
    Mississauga serves its zoning and Official Plan schedules from
    `services6.arcgis.com`, so without this the second municipality could not be
    read at all; with it, ACCESS and AUTHORITY stay separate questions. The
    reader may fetch the bytes; whether those bytes can ground a determination is
    decided later, by `classify_source` at record time, and only after the
    catalogue has actually been read and found to name the services. A caller
    who passes a catalogue that names nothing gets the data and a MATERIAL
    unresolved issue, not a promotion.
    """
    def read(url):
        classification = authority.classify_source(url, attested_by=attested_by)
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


def overlay_finding(binding, subject_geometry, point, *, reader, cache=None) -> dict:
    """What this overlay does to the parcel: applies, does not, or undetermined.

    PRESENCE IS MEASURED THE SAME WAY ABSENCE IS. Version 1 asked only whether a
    polygon covered the address POINT and, when one did, reported its raw
    attributes with no spatial basis at all - so a height overlay that genuinely
    governs the site arrived carrying NOT_APPLICABLE, weaker evidence than the
    absences beside it. The geometry is now fetched and related by our own
    engine, so an overlay that applies says INSIDE or INTERSECTS on the same
    footing as one that does not.

    ABSENCE STILL REQUIRES TWO PROOFS. An empty response is also what a broken
    query returns, so the City's own point query must find nothing AND every
    polygon within `ABSENCE_ENVELOPE_METRES` must be computed OUTSIDE. An
    undecidable polygon inside the envelope blocks the claim.
    """
    at_point = query_layer(binding, reader=reader, cache=cache,
                           with_geometry=True,
                           **{"geometry": _point_param(point["x"], point["y"]),
                              "geometryType": "esriGeometryPoint",
                              "spatialRel": "esriSpatialRelIntersects",
                              "inSR": QUERY_WKID})
    if at_point["features"]:
        feature = at_point["features"][0]
        geometry = esri_to_geojson(feature.get("geometry"))
        token = spatial.relate(
            {"crs": WKID_TO_CRS[102100], "geometry": subject_geometry},
            {"crs": WKID_TO_CRS[102100], "geometry": geometry},
            subject_source="City of Toronto Property Boundary",
            layer_source="City of Toronto %s" % binding[2],
            layer_version="By-law 569-2013") if geometry else None
        return {"layer_name": binding[2], "present": True,
                "attributes": feature.get("attributes") or {},
                "geometry": geometry, "token": token,
                "absence_established": False, "url": at_point["url"],
                "note": "overlay covers the subject"}

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
        "layer_name": binding[2], "present": False, "token": None,
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


def zoning_bylaw_url_for(attributes) -> tuple:
    """(url, authority_id, title) for the by-law that ACTUALLY governs this zone.

    The City records it per zone in `BYLAW_DOCLINK`. The first live subject
    carried `2013/law0569.pdf` and the second `2021/law0266.pdf`; hard-coding the
    enacting by-law was therefore correct once and wrong immediately after, while
    looking equally plausible both times. A citation that names the wrong
    instrument is worse than no citation, because it survives review.
    """
    doclink = (attributes or {}).get("BYLAW_DOCLINK")
    if not doclink or not isinstance(doclink, str):
        return ZONING_BYLAW_URL, "TOR-ZBL-569-2013", ZONING_BYLAW_TITLE
    doclink = doclink.lstrip("/")
    number = doclink.rsplit("/", 1)[-1]          # law0266.pdf
    year = doclink.split("/")[0] if "/" in doclink else None
    digits = "".join(c for c in number if c.isdigit()).lstrip("0") or number
    identifier = "TOR-BYLAW-%s-%s" % (digits, year) if year else "TOR-BYLAW-" + digits
    title = ("City of Toronto By-law %s-%s (as published by the City for this zone)"
             % (digits, year) if year else "City of Toronto By-law " + digits)
    return BYLAW_DOC_BASE + doclink, identifier, title


def acquire_zoning_bylaw(*, reader, retrieved_at, attributes=None,
                         effective_date=None, provision_locator=None) -> dict:
    """Retrieve the governing by-law so the record holds bytes, not a paraphrase."""
    url, identifier, title = zoning_bylaw_url_for(attributes)
    return authority.acquire(
        url, fetcher=reader,
        authority_id=identifier,
        issuing_authority="City of Toronto",
        official_title=title,
        retrieved_at=retrieved_at,
        effective_date=effective_date,
        version_identifier=identifier.replace("TOR-BYLAW-", "").replace(
            "TOR-ZBL-", ""),
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Toronto",
        spatial_scope="City of Toronto",
        provision_locator=provision_locator,
        source_type=authority.SOURCE_TYPE_MACHINE_READABLE,
        retained_representation=url)


def discover_official_plan(*, reader) -> dict:
    """Find the CURRENT consolidation from the City's own index page.

    Returns `{url, version}`. The version is the City's own link label - "June
    2026 Consolidation" - so the record states the edition the City is
    publishing today rather than one this module believed in when it was written.
    """
    try:
        payload = reader(OFFICIAL_PLAN_CHAPTERS_URL)
    except Exception as exc:  # noqa: BLE001 - discovery failure is a result
        logger.warning("official plan discovery failed (%s: %s)",
                       type(exc).__name__, exc)
        return {"url": OFFICIAL_PLAN_URL, "version": None,
                "note": "consolidation link not discovered; index page retained"}
    body = payload.decode("utf-8", "replace") if isinstance(
        payload, (bytes, bytearray)) else str(payload)
    for match in _CONSOLIDATION_LINK.finditer(body):
        url, label = match.group("url"), (match.group("label") or "").strip()
        if "consolidat" in (url + label).lower():
            return {"url": url, "version": label or None}
    return {"url": OFFICIAL_PLAN_URL, "version": None,
            "note": "no consolidation link on the index page; index retained"}


def acquire_official_plan(*, reader, retrieved_at) -> dict:
    """Section 4. The Official Plan as a DOCUMENT authority, not a geometry one.

    ABSENCE OF GEOMETRY IS NOT ABSENCE OF AUTHORITY. None of the 504 layers the
    City publishes carries a land use designation; it exists as map schedules
    inside the consolidated Plan. Treating that as a dead end would discard the
    governing instrument because it is the wrong FILE FORMAT, which is the
    opposite of a planning judgement. So the Plan is retrieved and admitted as a
    real authority, and what degrades is the SPATIAL claim: `source_type` is a
    map schedule, `supports_deterministic_spatial` is False, and nothing
    downstream can mint an INSIDE from it.
    """
    discovered = discover_official_plan(reader=reader)
    return authority.acquire(
        discovered["url"], fetcher=reader,
        authority_id="TOR-OFFICIAL-PLAN",
        issuing_authority="City of Toronto",
        official_title="%s%s" % (OFFICIAL_PLAN_TITLE,
                                 " - " + discovered["version"]
                                 if discovered.get("version") else ""),
        retrieved_at=retrieved_at,
        version_identifier=discovered.get("version"),
        effective_date=discovered.get("version"),
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Toronto",
        spatial_scope="City of Toronto",
        provision_locator="Land Use Plan map schedules",
        source_type=authority.SOURCE_TYPE_MAP_SCHEDULE,
        property_to_map_basis=None,
        basis_confidence="LOW",
        limitation=("Land use designation is published only as map schedules; no "
                    "polygon layer exists, so the designation covering this "
                    "parcel was not determined by computation and is not "
                    "asserted."),
        retained_representation=discovered["url"])


def acquire_exception(exception_number, locator, *, reader, retrieved_at) -> dict:
    """Retrieve a site-specific exception AND VERIFY THE PROVISION IS IN IT.

    RETRIEVAL IS NOT THE TEST. The City's own attribute points at
    `Chapter900_11.htm#900.11.10(2219)`; that page returns 200 and 56 KB and
    contains no exception numbers at all - it is a shell. Accepting those bytes
    as "the exception text" would produce a record with a real hash, a real URL,
    a real 200, and none of the provision it claims to carry. So the exception
    number must actually APPEAR in what came back, or this fails closed.
    """
    if not locator:
        return {"acquired": False, "reason": "no exception locator published",
                "record": None, "url": None}
    url = ZONING_CHAPTER_BASE + str(locator).lstrip("/")
    try:
        payload = reader(url.split("#")[0])
    except Exception as exc:  # noqa: BLE001 - a failed retrieval is a result
        return {"acquired": False, "url": url, "record": None,
                "reason": "%s: %s" % (type(exc).__name__, exc)}

    body = payload.decode("utf-8", "replace") if isinstance(
        payload, (bytes, bytearray)) else str(payload)
    marker = "(%s)" % exception_number
    if marker not in body:
        return {
            "acquired": False, "url": url, "record": None,
            "reason": ("the page was retrieved (%d bytes) but does not contain "
                       "exception %s - the provision text is not published at "
                       "this locator" % (len(body), exception_number)),
        }
    return authority.acquire(
        url.split("#")[0], fetcher=lambda _u: payload,
        authority_id="TOR-ZBL-EXCEPTION-%s" % exception_number,
        issuing_authority="City of Toronto",
        official_title="Zoning By-law 569-2013 exception %s" % exception_number,
        retrieved_at=retrieved_at,
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Toronto",
        provision_locator=str(locator),
        source_type=authority.SOURCE_TYPE_POLICY_DOCUMENT,
        retained_representation=url)


def heritage_register_near(subject_geometry, *, reader, cache=None,
                           margin_metres=60.0) -> dict:
    """Individually listed heritage properties near the parcel. NOT a containment.

    The register is a POINT layer, and this engine relates polygons. Deciding
    whether a listed point falls inside the parcel would need point-in-polygon
    competence, and NO MEASURED CASE HAS DEMANDED IT - neither live subject has a
    listed property within 60 m. So the capability is deliberately not built, and
    this reports proximity with the limitation stated rather than leaving an
    individually listed building unmentioned. A silent gap is the worse failure:
    a heritage listing on the site changes what may be done to the building.
    """
    ring = ((subject_geometry or {}).get("coordinates") or [[]])[0]
    if not ring:
        return {"checked": False, "reason": "no subject ring", "properties": []}
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    envelope = json.dumps({"xmin": min(xs) - margin_metres,
                           "ymin": min(ys) - margin_metres,
                           "xmax": max(xs) + margin_metres,
                           "ymax": max(ys) + margin_metres,
                           "spatialReference": {"wkid": 102100}})
    found = query_layer(LAYER_HERITAGE_REGISTER, reader=reader, cache=cache,
                        with_geometry=False,
                        **{"geometry": envelope,
                           "geometryType": "esriGeometryEnvelope",
                           "spatialRel": "esriSpatialRelIntersects",
                           "inSR": QUERY_WKID})
    properties = [{"address": (f.get("attributes") or {}).get("ADDRESS"),
                   "status": (f.get("attributes") or {}).get("STATUS"),
                   "bylaw": (f.get("attributes") or {}).get("BYLAW")}
                  for f in found["features"]]
    return {"checked": True, "margin_metres": margin_metres,
            "properties": properties, "url": found["url"],
            "limitation": ("proximity within %.0f m of the parcel envelope; "
                           "containment was NOT computed" % margin_metres)}
