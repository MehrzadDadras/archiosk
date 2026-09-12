"""CLAUDE-GENERALIZATION-02 - the second municipality, deliberately unlike the first.

    ADDRESS -> OFFICIAL CITY GEOMETRY -> OUR OWN DETERMINISTIC ENGINE -> TOKEN

Toronto proved the GO-PDZ path could run. It could not show whether the path
generalized, because everything about it was shaped by one publisher. Mississauga
differs in every dimension that matters, which is why it was chosen:

  ARCHITECTURE      Toronto: an on-prem catalogue of 24 `MapServer` services.
                    Mississauga: a DCAT open-data catalogue on the City's own
                    domain, pointing at hosted ArcGIS Online feature services.

  PARCEL RESOLUTION Toronto: spatial intersection of an address point with the
                    property-boundary polygon.
                    Mississauga: an ATTRIBUTE JOIN on `CITY_PIN`. No geometry is
                    involved in identifying the parcel at all.

  COORDINATE SYSTEM Toronto: everything in EPSG:3857.
                    Mississauga: address and parcel in EPSG:3857, zoning and the
                    Official Plan schedules in EPSG:26917. Within one publisher.

  OFFICIAL PLAN     Toronto: no machine-readable land use designation anywhere in
                    504 published layers - document fallback only.
                    Mississauga: Schedule 10 Land Use Designations is a polygon
                    layer, so the designation is DETERMINISTIC here. The same
                    question, answered by arithmetic in one city and by reading a
                    PDF in the other, is the clearest evidence that the source
                    hierarchy in section 3 is doing real work.

A HOSTING PLATFORM IS NOT AN AUTHORITY - BUT AN OFFICIAL CATALOGUE CAN ATTEST TO
ONE. Mississauga's planning layers are served from `services6.arcgis.com`, which
`planning_authority` classifies SECONDARY, and correctly: that domain also serves
private individuals' re-uploads. What makes these particular services official is
that the City's OWN catalogue, on the City's OWN domain, names them as its
publications. So the catalogue is retrieved first and passed as `attested_by`,
and the classification follows provenance rather than hostname. Neither blanket
rule survives contact with this data: "arcgis.com is official" admits a
hobbyist's layer, and "arcgis.com is never official" discards a real city's real
Official Plan.

ASK ABOUT THE PARCEL, NOT ABOUT THE DOT. The first run of this module asked which
zone covered the ADDRESS POINT, got `RL-62`, and reported it ESTABLISHED with
HIGH confidence. Asking the same layer about the PARCEL returns TWO zones, RL-62
and RL-61: a zone boundary runs through the lot. The engine had already said so -
its token was INTERSECTS rather than INSIDE - and the statement builder wrote
over it. Point queries are retained only to record what sits at the address;
every determination is made against the parcel.

READ-ONLY, AND INJECTABLE ANYWAY. `reader` has no default here either.
"""
from __future__ import annotations

import json
import logging
import urllib.parse

from services import deterministic_spatial as spatial
from services import planning_authority as authority
from services.toronto_planning_source import esri_to_geojson

logger = logging.getLogger(__name__)

SOURCE_VERSION = "mississauga-planning-source@2"

#: The City's own catalogue, on the City's own domain. This is what attests that
#: the hosted services below are municipal publications rather than someone's
#: upload, so it is retrieved before any of them are trusted.
CATALOGUE_URL = "https://data.mississauga.ca/api/feed/dcat-us/1.1.json"

ORG = "https://services6.arcgis.com/hM5ymMLbxIyWTjn2/arcgis/rest/services"

#: (path, expected_layer_name). As in Toronto, THE NAME IS THE CONTRACT.
LAYER_ADDRESS = ("/Address/FeatureServer/0", "Address")
LAYER_PARCEL = ("/Parcel/FeatureServer/0", "Parcel")
LAYER_ZONING = ("/2022_Zoning/FeatureServer/0", "Zoning")
LAYER_LAND_USE = ("/MississaugaOfficialPlan_2010_LandUse_Schedule_10/FeatureServer/1",
                  "MississaugaOfficialPlan_2010_LandUse_Sch10")
LAYER_CHARACTER_AREA = ("/MOP_CharacterAreaCityStructure/FeatureServer/0", None)
LAYER_INTENSIFICATION = ("/MOP_IntensificationCorridor/FeatureServer/0", None)
LAYER_MTSA_RADIUS = ("/MOP_MajorTransitStationArea500mRadiusCircle/FeatureServer/0",
                     None)
LAYER_GREEN_SYSTEM = ("/MOP_GreenSystem/FeatureServer/0", None)
LAYER_NATURAL_HAZARDS = ("/MOP_NaturalHazards/FeatureServer/0", None)

#: Heritage here is a POLYGON layer - it carries `Shape__Area` - unlike Toronto's
#: Heritage Register, which is points. Containment is therefore computable with
#: the engine already in hand, and reporting mere proximity would understate
#: evidence that exists.
LAYER_HERITAGE = ("/Mississauga_Heritage_Properties/FeatureServer/0", None)

#: Policy layers checked for every subject, with the topic each answers.
OVERLAY_LAYERS = (
    (LAYER_CHARACTER_AREA, "Character Area and City Structure", "URBAN_STRUCTURE"),
    (LAYER_INTENSIFICATION, "Intensification Corridor", "INTENSIFICATION"),
    (LAYER_MTSA_RADIUS, "Major Transit Station Area 500m Radius", "TRANSIT_POLICY"),
    (LAYER_GREEN_SYSTEM, "Green System", "NATURAL_HERITAGE"),
    (LAYER_NATURAL_HAZARDS, "Natural Hazards", "NATURAL_HAZARD"),
)

#: The planning layers are authored in UTM 17N. Everything is requested in it, so
#: the AUTHORITY geometry is never moved and only the subject parcel is
#: reprojected - by the publisher, on request, and recorded as such.
WORKING_CRS = "EPSG:26917"
WORKING_WKID = "26917"
NATIVE_SUBJECT_CRS = "EPSG:3857"
TRANSFORMATION_NOTE = ("EPSG:3857 -> EPSG:26917, performed by the publishing "
                       "service in response to an outSR request; this engine "
                       "performed none")

#: Measured, not guessed. The obvious `/projects-and-strategies/...` paths 404 and
#: the direct consolidation PDF returns 403. A plausible URL that 403s does not
#: fail loudly - it produces an authority record with no bytes, which
#: `may_satisfy_authority_says` then refuses, quietly removing the citation from
#: every statement that needed it. Both of these returned 200 before being written.
ZONING_BYLAW_URL = "https://www.mississauga.ca/portal/residents/zoningbylaw"
OFFICIAL_PLAN_LANDING = ("https://www.mississauga.ca/services-and-programs/"
                         "planning-and-building/mississauga-official-plan/")


class LayerIdentityError(RuntimeError):
    """The service no longer calls this layer what we bound to. Refuse."""


def _read_json(reader, url):
    payload = reader(url)
    if isinstance(payload, (bytes, bytearray)):
        payload = bytes(payload).decode("utf-8", "replace")
    if isinstance(payload, str):
        payload = json.loads(payload)
    if isinstance(payload, dict) and payload.get("error"):
        raise RuntimeError("service error: %s" % json.dumps(payload["error"])[:300])
    return payload


def catalogue_attestation(*, reader, cache=None) -> dict:
    """Retrieve the City's own catalogue. THIS is what makes the rest official.

    If the catalogue cannot be read, the hosted services stay SECONDARY and every
    finding built on them is bounded accordingly - the correct failure, not a
    blocking one.
    """
    if cache is not None and "attestation" in cache:
        return cache["attestation"]
    try:
        payload = reader(CATALOGUE_URL)
        body = payload.decode("utf-8", "replace") if isinstance(
            payload, (bytes, bytearray)) else str(payload)
        data = json.loads(body)
        datasets = data.get("dataset") or []
        named = sum(1 for entry in datasets
                    for dist in (entry.get("distribution") or [])
                    if ORG in str(dist.get("accessURL") or ""))
        attestation = {
            "attested_by": CATALOGUE_URL,
            "attested": named > 0,
            "datasets": len(datasets),
            "services_named": named,
            "note": ("the City's own catalogue names %d distributions on %s, so "
                     "those services are municipal publications rather than "
                     "third-party uploads" % (named, ORG)),
        }
    except Exception as exc:  # noqa: BLE001 - a failed attestation is a result
        logger.warning("catalogue attestation failed (%s: %s)",
                       type(exc).__name__, exc)
        attestation = {"attested_by": None, "attested": False, "datasets": 0,
                       "services_named": 0,
                       "note": "catalogue could not be read: %s" % type(exc).__name__}
    if cache is not None:
        cache["attestation"] = attestation
    return attestation


def verify_layer(binding, *, reader, cache=None) -> dict:
    """Confirm the service still calls this layer what we bound to."""
    path, expected = binding
    if cache is not None and path in cache:
        return cache[path]
    meta = _read_json(reader, ORG + path + "?f=json")
    actual = meta.get("name")
    if expected is not None and actual != expected:
        raise LayerIdentityError(
            "%s is now %r, expected %r - binding refused" % (path, actual, expected))
    verified = {"path": path, "name": actual,
                "geometry_type": meta.get("geometryType"),
                "native_crs": (meta.get("extent") or {}).get(
                    "spatialReference", {}).get("latestWkid")}
    if cache is not None:
        cache[path] = verified
    return verified


def query_layer(binding, *, reader, cache=None, **params) -> dict:
    verified = verify_layer(binding, reader=reader, cache=cache)
    params.setdefault("f", "json")
    params.setdefault("outFields", "*")
    params.setdefault("outSR", WORKING_WKID)
    url = ORG + binding[0] + "/query?" + urllib.parse.urlencode(params)
    data = _read_json(reader, url)
    return {"layer": verified, "url": url, "features": data.get("features") or []}


def _split_address(address):
    """'5198 Mississauga Road, Mississauga' -> ('5198', 'MISSISSAUGA').

    The City stores the street NAME without its suffix (`STNAME='MISSISSAUGA'`,
    `SUFFIX='RD'`), the opposite shape from Toronto's single `LINEAR_NAME_FULL`
    field - and the reason each municipality needs its own reader rather than a
    shared regex.
    """
    if not address or not isinstance(address, str):
        return None, None
    head = address.split(",")[0].strip()
    parts = head.split()
    if len(parts) < 2 or not parts[0].isdigit():
        return None, None
    return parts[0], parts[1].upper()


def resolve_address(address, *, reader, cache=None) -> dict:
    """Address point, then the parcel it names. NO GEOMETRY IS USED to find it.

    Mississauga's address record carries `CITY_PIN`, the parcel's own identifier,
    so the parcel is retrieved by ATTRIBUTE JOIN. That is a stronger identity
    claim than a spatial intersection - the publisher's own statement that this
    address belongs to this parcel, rather than our inference that a point fell
    inside a polygon.
    """
    number, street = _split_address(address)
    if not number or not street:
        return {"parcel_count": 0, "resolution_note": "address could not be parsed"}

    where = "STNO='%s' AND UPPER(STNAME) LIKE '%s%%'" % (
        number.replace("'", "''"), street.replace("'", "''"))
    points = query_layer(LAYER_ADDRESS, reader=reader, cache=cache,
                         where=where, returnGeometry="true")
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
    pin = attributes.get("CITY_PIN")
    resolved = {
        "subject_id": "MISS-ADDR-%s" % attributes.get("ADDR_ID"),
        "normalized_address": attributes.get("FULLNAME"),
        "municipality": "City of Mississauga",
        "ward": attributes.get("WARD"),
        "city_pin": pin,
        "point": {"x": geometry.get("x"), "y": geometry.get("y")},
        "crs": WORKING_CRS,
        "source": "City of Mississauga Parcel (CITY_PIN attribute join)",
        "address_source": "City of Mississauga Address",
        "resolution_method": "attribute join on CITY_PIN",
        "upstream_transformation": TRANSFORMATION_NOTE,
    }
    if pin is None:
        resolved["parcel_count"] = 0
        resolved["resolution_note"] = "address point carries no CITY_PIN"
        return resolved

    parcels = query_layer(LAYER_PARCEL, reader=reader, cache=cache,
                          where="CITY_PIN=%s" % int(pin), returnGeometry="true")
    parcel_features = parcels["features"]
    resolved["parcel_count"] = len(parcel_features)
    if len(parcel_features) != 1:
        resolved["resolution_note"] = ("CITY_PIN %s matched %d parcels"
                                       % (pin, len(parcel_features)))
        return resolved

    parcel_attributes = parcel_features[0].get("attributes") or {}
    resolved.update({
        "parcel_identifier": "MISS-PIN-%s" % pin,
        "stated_area": ("%s sq.m (GIS_AREA)" % parcel_attributes.get("GIS_AREA")
                        if parcel_attributes.get("GIS_AREA") is not None else None),
        "geometry": esri_to_geojson(parcel_features[0].get("geometry")),
    })
    if resolved["geometry"] is None:
        resolved["resolution_note"] = (
            "parcel geometry is unreadable; rings could not be resolved into an "
            "exterior/hole structure without guessing")
    return resolved


def _relate(subject_geometry, layer_geometry, *, layer_source, layer_version=None):
    return spatial.relate(
        {"crs": WORKING_CRS, "geometry": subject_geometry},
        {"crs": WORKING_CRS, "geometry": layer_geometry},
        subject_source="City of Mississauga Parcel",
        layer_source=layer_source, layer_version=layer_version,
        upstream_transformation=TRANSFORMATION_NOTE)


def _at_point(binding, subject_geometry, point, label, *, reader, cache=None):
    """What sits at the address dot. Recorded, never used as the determination."""
    found = query_layer(
        binding, reader=reader, cache=cache, returnGeometry="true",
        **{"geometry": json.dumps({"x": point["x"], "y": point["y"],
                                   "spatialReference": {"wkid": 26917}}),
           "geometryType": "esriGeometryPoint",
           "spatialRel": "esriSpatialRelIntersects", "inSR": WORKING_WKID})
    if not found["features"]:
        return {"layer_name": label, "present": False, "token": None,
                "attributes": None, "url": found["url"]}
    feature = found["features"][0]
    geometry = esri_to_geojson(feature.get("geometry"))
    token = None
    if geometry:
        token = _relate(subject_geometry, geometry,
                        layer_source="City of Mississauga %s" % label)
    return {"layer_name": label, "present": True, "token": token,
            "attributes": feature.get("attributes") or {},
            "geometry": geometry, "url": found["url"]}


def _at_parcel(binding, subject_geometry, label, *, reader, cache=None) -> list:
    """Every polygon of a layer that touches the PARCEL, not just the address point.

    "What is at this dot" and "what governs this property" are different
    questions, and they diverge exactly when a boundary runs through the lot -
    which is the case that matters most.
    """
    ring = ((subject_geometry or {}).get("coordinates") or [[]])[0]
    if not ring:
        return []
    found = query_layer(
        binding, reader=reader, cache=cache, returnGeometry="true",
        **{"geometry": json.dumps({"rings": [[list(p) for p in ring]],
                                   "spatialReference": {"wkid": 26917}}),
           "geometryType": "esriGeometryPolygon",
           "spatialRel": "esriSpatialRelIntersects", "inSR": WORKING_WKID})
    findings = []
    for feature in found["features"]:
        geometry = esri_to_geojson(feature.get("geometry"))
        token = None
        if geometry:
            token = _relate(subject_geometry, geometry,
                            layer_source="City of Mississauga %s" % label)
        findings.append({"layer_name": label, "present": True, "token": token,
                         "attributes": feature.get("attributes") or {},
                         "geometry": geometry, "url": found["url"]})
    return findings


def zoning_at(subject_geometry, point, *, reader, cache=None) -> dict:
    """Every zone touching the parcel. SPLIT ZONING IS THE CASE THAT MATTERS.

    See the module docstring: asking the point returns one zone, asking the
    parcel returns two. A split-zoned lot is decisive for what can be built, so
    all zones are returned and the caller must handle more than one.
    """
    findings = _at_parcel(LAYER_ZONING, subject_geometry, "Zoning",
                          reader=reader, cache=cache)
    at_point = _at_point(LAYER_ZONING, subject_geometry, point, "Zoning",
                         reader=reader, cache=cache)
    return {"layer_name": "Zoning", "zones": findings,
            "zone_count": len(findings),
            "at_address_point": at_point.get("attributes"),
            "present": bool(findings),
            "split": len(findings) > 1}


def land_use_at(subject_geometry, point, *, reader, cache=None) -> dict:
    """Official Plan Schedule 10 designation - MACHINE-READABLE here.

    This is the question Toronto could not answer by computation at all. The same
    determination, deterministic in one municipality and a PDF in the other, is
    what the source hierarchy exists to express.
    """
    findings = _at_parcel(LAYER_LAND_USE, subject_geometry,
                          "Official Plan Schedule 10 Land Use Designations",
                          reader=reader, cache=cache)
    return {"layer_name": "Official Plan Schedule 10 Land Use Designations",
            "designations": findings, "designation_count": len(findings),
            "present": bool(findings), "split": len(findings) > 1,
            "attributes": (findings[0].get("attributes") if findings else None),
            "geometry": (findings[0].get("geometry") if findings else None),
            "token": (findings[0].get("token") if findings else None)}


def overlay_findings(subject_geometry, point, *, reader, cache=None) -> list:
    findings = []
    for binding, label, topic in OVERLAY_LAYERS:
        try:
            touching = _at_parcel(binding, subject_geometry, label,
                                  reader=reader, cache=cache)
            if touching:
                finding = touching[0]
                finding["touching"] = len(touching)
            else:
                finding = {"layer_name": label, "present": False, "token": None,
                           "attributes": None, "touching": 0}
        except Exception as exc:  # noqa: BLE001 - a failed layer is a result
            logger.warning("overlay failed for %s (%s: %s)", label,
                           type(exc).__name__, exc)
            finding = {"layer_name": label, "present": None, "token": None,
                       "note": "layer could not be read: %s" % type(exc).__name__}
        finding["topic"] = topic
        findings.append(finding)
    return findings


def heritage_at(subject_geometry, *, reader, cache=None) -> dict:
    """Listed heritage properties, RELATED not merely counted.

    Measured correction: `Mississauga_Heritage_Properties` carries `Shape__Area`
    - it is a POLYGON layer, not the point layer Toronto's register is. The first
    run reported "17 listed properties within 60 m, containment not computed"
    when containment was computable all along with the engine already in hand.
    Proximity was not a limitation of the evidence; it was a limitation of the
    question being asked. No new competence was added for this.
    """
    try:
        findings = _at_parcel(LAYER_HERITAGE, subject_geometry,
                              "Heritage Properties", reader=reader, cache=cache)
    except Exception as exc:  # noqa: BLE001
        return {"checked": False, "covering": [], "touching": 0,
                "reason": "%s: %s" % (type(exc).__name__, exc)}
    covering = [f for f in findings
                if (f.get("token") or {}).get("spatial_relation")
                in (spatial.RELATION_INSIDE, spatial.RELATION_INTERSECTS)]
    return {"checked": True, "touching": len(findings), "covering": covering,
            "basis": "deterministic containment computed by this engine"}


def acquire_geospatial_publication(*, reader, retrieved_at, attestation) -> dict:
    """Record the HOSTED SERVICE itself as an attested authority.

    This is where the attestation becomes visible in the result rather than
    staying an implementation detail. Every deterministic finding rests on
    polygons served from a platform that also hosts private uploads; what makes
    these municipal is the City's own catalogue naming them, so the catalogue is
    carried as `attested_by` and a reader can see, without leaving the document,
    why a hosted URL was allowed to ground a determination.
    """
    return authority.acquire(
        ORG + LAYER_ZONING[0], fetcher=reader,
        authority_id="MISS-GEOSPATIAL-PUBLICATION",
        issuing_authority="City of Mississauga",
        official_title="City of Mississauga published geospatial services "
                       "(zoning, parcel, address, Official Plan schedules)",
        retrieved_at=retrieved_at,
        version_identifier="2022 Zoning / MOP 2010 Schedule 10",
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Mississauga",
        spatial_scope="City of Mississauga",
        source_type=authority.SOURCE_TYPE_MACHINE_READABLE,
        attested_by=(attestation or {}).get("attested_by"),
        property_to_map_basis="deterministic containment computed by this engine",
        basis_confidence="HIGH",
        limitation=(attestation or {}).get("note"),
        retained_representation=ORG + LAYER_ZONING[0])


def acquire_zoning_bylaw(*, reader, retrieved_at, attestation=None) -> dict:
    """Zoning By-law 0225-2007, from the page the City actually serves."""
    return authority.acquire(
        ZONING_BYLAW_URL, fetcher=reader,
        authority_id="MISS-ZBL-0225-2007",
        issuing_authority="City of Mississauga",
        official_title="City of Mississauga Zoning By-law 0225-2007 "
                       "(City zoning by-law publication)",
        retrieved_at=retrieved_at,
        version_identifier="0225-2007",
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Mississauga",
        spatial_scope="City of Mississauga",
        source_type=authority.SOURCE_TYPE_CONSOLIDATED_DOCUMENT,
        limitation=("the by-law publication is retained as bytes; provision-level "
                    "requirements for this zone were not extracted"),
        retained_representation=ZONING_BYLAW_URL)


def acquire_official_plan(*, reader, retrieved_at, attestation=None) -> dict:
    """Mississauga Official Plan - and here the SCHEDULE is machine-readable.

    `source_type` is therefore MACHINE_READABLE rather than a map schedule, which
    is what lets a designation finding here carry a deterministic predicate while
    the equivalent Toronto finding cannot. The distinction is recorded on the
    authority, not decided in the statement builder.
    """
    attested = (attestation or {}).get("attested_by")
    return authority.acquire(
        OFFICIAL_PLAN_LANDING, fetcher=reader,
        authority_id="MISS-OFFICIAL-PLAN",
        issuing_authority="City of Mississauga",
        official_title="Mississauga Official Plan (2010), Schedule 10 Land Use "
                       "Designations",
        retrieved_at=retrieved_at,
        version_identifier="2010, Schedule 10",
        applicability=authority.APPLICABILITY_CURRENT,
        jurisdiction="City of Mississauga",
        spatial_scope="City of Mississauga",
        provision_locator="Schedule 10 Land Use Designations",
        source_type=authority.SOURCE_TYPE_MACHINE_READABLE,
        property_to_map_basis=("deterministic containment of the parcel in the "
                              "published Schedule 10 polygon"),
        basis_confidence="HIGH",
        limitation=("the designation polygon is authoritative for mapping; "
                    "policy text governing the designation was not extracted%s"
                    % (" (services attested by %s)" % attested if attested else "")),
        retained_representation=OFFICIAL_PLAN_LANDING)
