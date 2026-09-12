"""CLAUDE-TORONTO-LIVE-01 - address in, Gate 01 envelope out, for Toronto.

    ADDRESS -> toronto_planning_source -> go_pdz_lifecycle -> VR-01..VR-20 -> STOP

This is the reachable end of the GO-PDZ programme. `go_pdz_contract`,
`go_pdz_validator`, `planning_authority`, `deterministic_spatial` and
`go_pdz_lifecycle` were each built and tested with nothing calling them from a
real address; this module is the caller, and it adds no new judgement of its own.

TRANSCRIPTION IS NOT INTERPRETATION, AND THE LINE IS DRAWN ON PURPOSE. Every
statement below restates a value that was retrieved from an official City layer,
or an absence this module proved. None of them reasons about what may be built.
Where a retrieved attribute has an obvious regulatory reading that the retrieved
BYTES do not establish - `FSI_TOTAL = 1.0` almost certainly being a maximum
floor-space index, for instance - the statement carries the attribute and the
reading is left to GO, as a PROVISIONAL statement with the gap recorded. Guessing
there would be the whole failure this contract exists to prevent, in miniature.

THE ABSENCES ARE FINDINGS. An overlay that does not apply is as much a part of a
planning envelope as one that does, and it is the half a summary silently drops.
Each absence here is proved twice - see `toronto_planning_source.overlay_absence`
- and is stated with the geometry it was proved against.

GATE 01 ENDS AT THE LEGAL ENVELOPE. Nothing here produces or accepts an owner
program, unit count, massing or option. `go_pdz_lifecycle.assemble` has no
parameter that could carry one, and this module adds none.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from services import go_pdz_lifecycle as lifecycle
from services import toronto_planning_source as source

logger = logging.getLogger(__name__)

RUNNER_VERSION = "toronto-gate01@1"

#: Absences worth stating even when nothing is found, because a reader needs to
#: know the question was ASKED. An unlisted overlay that returns nothing is a
#: silent gap; a listed one that returns nothing is a finding.
REPORTED_ABSENCES = {
    "Zoning Height Overlay": "HEIGHT_LIMIT",
    "Zoning Lot Coverage Overlay": "LOT_COVERAGE",
    "Zoning Policy Area Overlay": "POLICY_AREA",
    "Zoning Building Setback Overlay": "BUILDING_SETBACK",
    "Zoning Not Part of This Bylaw": "BYLAW_APPLICABILITY",
    "Secondary Plan": "SECONDARY_PLAN",
    "Site and Area Specific Policy": "SITE_SPECIFIC_POLICY",
    "Heritage District": "HERITAGE",
    "Natural Heritage System (polygon)": "NATURAL_HERITAGE",
    "Major Transit Station Area": "TRANSIT_POLICY",
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gather(address, *, reader, retrieved_at=None):
    """Retrieve everything Gate 01 needs. No statements, no judgement - facts."""
    retrieved_at = retrieved_at or _now()
    cache = {}

    resolved = source.resolve_address(address, reader=reader, cache=cache)
    gathered = {"address": address, "retrieved_at": retrieved_at,
                "resolved": resolved, "zoning": None, "absences": [],
                "authority": None, "runner_version": RUNNER_VERSION,
                "source_version": source.SOURCE_VERSION}

    geometry, point = resolved.get("geometry"), resolved.get("point")
    if not geometry or not point:
        gathered["note"] = ("subject geometry was not established; no spatial "
                            "question can be asked of it")
        return gathered

    gathered["zoning"] = source.zoning_at(geometry, point, reader=reader,
                                          cache=cache)
    for binding in source.OVERLAY_LAYERS:
        try:
            gathered["absences"].append(source.overlay_absence(
                binding, geometry, point, reader=reader, cache=cache))
        except Exception as exc:  # noqa: BLE001 - a failed layer is a result
            logger.warning("overlay check failed for %s (%s: %s)",
                           binding[2], type(exc).__name__, exc)
            gathered["absences"].append(
                {"layer_name": binding[2], "present": None,
                 "absence_established": False,
                 "note": "layer could not be read: %s" % type(exc).__name__})

    zoning = gathered["zoning"] or {}
    attributes = zoning.get("attributes") or {}
    gathered["authority"] = source.acquire_zoning_bylaw(
        reader=reader, retrieved_at=retrieved_at,
        provision_locator=("Chapter %s, Section %s"
                           % (attributes.get("ZBL_CHAPTER"),
                              attributes.get("ZBL_SECTION"))
                           if attributes.get("ZBL_CHAPTER") else None))
    return gathered


def _zoning_statements(gathered):
    """Restate what the zoning layer carries. Nothing more."""
    zoning = gathered.get("zoning") or {}
    attributes = zoning.get("attributes") or {}
    if not zoning.get("present"):
        return []

    zone = attributes.get("ZN_ZONE")
    label = attributes.get("ZN_STRING")
    chapter, section = attributes.get("ZBL_CHAPTER"), attributes.get("ZBL_SECTION")
    statements = [{
        "statement_id": "S-ZONE",
        "kind": "AUTHORITY_SAYS",
        "topic": "ZONING_DESIGNATION",
        "text": ("The subject parcel lies within a zone labelled %r (zone code "
                 "%r) on the City of Toronto zoning mapping made under Zoning "
                 "By-law 569-2013, Chapter %s, Section %s."
                 % (label, zone, chapter, section)),
        "authority_refs": ["TOR-ZBL-569-2013"],
        "statement_status": "ESTABLISHED",
        "confidence": "HIGH",
        "spatial_layer": "zoning_area",
    }]

    fsi = attributes.get("FSI_TOTAL")
    if fsi is not None and fsi >= 0:
        statements.append({
            "statement_id": "S-ZONE-FSI",
            "kind": "AUTHORITY_SAYS",
            "topic": "DENSITY",
            # PROVISIONAL on purpose. The City's attribute is retrieved and
            # exact; that it states a regulatory MAXIMUM is a reading of the
            # by-law text, which has not been read.
            "text": ("The City's zoning record carries FSI_TOTAL = %s for the "
                     "zone containing the subject parcel (zone label %r). The "
                     "regulatory effect of that figure is stated in the by-law "
                     "text, which has not been retrieved at provision level."
                     % (fsi, label)),
            "authority_refs": ["TOR-ZBL-569-2013"],
            "statement_status": "PROVISIONAL",
            "confidence": "MEDIUM",
            "spatial_layer": "zoning_area",
        })

    if attributes.get("ZN_EXCPTN") == "N":
        statements.append({
            "statement_id": "S-ZONE-NO-EXCEPTION",
            "kind": "AUTHORITY_SAYS",
            "topic": "SITE_SPECIFIC_EXCEPTION",
            "text": ("The City's zoning record carries ZN_EXCPTN = 'N' for this "
                     "zone: no site-specific exception is flagged against it. An "
                     "exception displaces the parent standard, so its absence is "
                     "recorded rather than assumed."),
            "authority_refs": ["TOR-ZBL-569-2013"],
            "statement_status": "ESTABLISHED",
            "confidence": "HIGH",
            "spatial_layer": "zoning_area",
        })
    return statements


def _property_statements(gathered):
    resolved = gathered.get("resolved") or {}
    statements = []
    if resolved.get("parcel_identifier"):
        statements.append({
            "statement_id": "S-PARCEL",
            "kind": "PROPERTY_FACT",
            "topic": "PARCEL_IDENTITY",
            "text": ("The address resolves to exactly one City of Toronto "
                     "property boundary, %s, on registered plan %s, in ward %s."
                     % (resolved["parcel_identifier"], resolved.get("parcel_plan"),
                        resolved.get("ward"))),
            "statement_status": "ESTABLISHED",
            "confidence": "HIGH",
        })
    if resolved.get("stated_area"):
        statements.append({
            "statement_id": "S-PARCEL-AREA",
            "kind": "PROPERTY_FACT",
            "topic": "SITE_AREA",
            "text": ("The City's parcel record states an area of %s. This is the "
                     "City's stated figure, not a survey."
                     % resolved["stated_area"]),
            "statement_status": "ESTABLISHED",
            "confidence": "MEDIUM",
        })
    return statements


def _absence_statements(gathered):
    """A proven absence is a finding. An unproven one is not asserted."""
    statements = []
    for index, finding in enumerate(gathered.get("absences") or []):
        name = finding.get("layer_name")
        topic = REPORTED_ABSENCES.get(name)
        if topic is None:
            continue
        sid = "S-ABSENT-%02d" % index

        if finding.get("present"):
            statements.append({
                "statement_id": sid,
                "kind": "AUTHORITY_SAYS",
                "topic": topic,
                "text": ("The City's %s layer covers the subject parcel: %s"
                         % (name, finding.get("attributes"))),
                "authority_refs": ["TOR-ZBL-569-2013"],
                "statement_status": "PROVISIONAL",
                "confidence": "MEDIUM",
            })
            continue

        if not finding.get("absence_established"):
            statements.append({
                "statement_id": sid,
                "kind": "PROPERTY_FACT",
                "topic": topic,
                "text": ("Whether the City's %s layer affects the subject parcel "
                         "could not be determined: %s"
                         % (name, finding.get("note"))),
                "statement_status": "UNRESOLVED",
                "confidence": "LOW",
            })
            continue

        grounded = finding.get("witness_geometry") is not None
        statements.append({
            "statement_id": sid,
            "kind": "PROPERTY_FACT",
            "topic": topic,
            "text": ("No polygon of the City's %s layer applies to the subject "
                     "parcel. The City's own point query over that layer returns "
                     "nothing, and every one of the %d polygons of that layer "
                     "within %.0f m was independently computed OUTSIDE the parcel."
                     % (name, finding.get("polygons_in_envelope", 0),
                        finding.get("envelope_metres", 0.0))),
            "statement_status": "ESTABLISHED" if grounded else "PROVISIONAL",
            "confidence": "HIGH" if grounded else "MEDIUM",
            "spatial_layer": ("absence:%s" % name) if grounded else None,
        })
    return [{k: v for k, v in s.items() if v is not None} for s in statements]


def _layers(gathered):
    """Geometry handed to `go_pdz_lifecycle.spatial_context`, which relates it."""
    layers = {}
    zoning = gathered.get("zoning") or {}
    if zoning.get("present") and zoning.get("geometry"):
        layers["zoning_area"] = {
            "crs": "EPSG:3857", "geometry": zoning["geometry"],
            "source": "City of Toronto Zoning Area (cot_geospatial11/3)",
            "version": "By-law 569-2013"}
    for finding in gathered.get("absences") or []:
        if finding.get("absence_established") and finding.get("witness_geometry"):
            layers["absence:%s" % finding["layer_name"]] = {
                "crs": "EPSG:3857", "geometry": finding["witness_geometry"],
                "source": "City of Toronto %s" % finding["layer_name"],
                "version": "By-law 569-2013"}
    return layers


def _unresolved(gathered):
    """What is genuinely not knowable from what was retrieved. Stated, not hidden."""
    issues = [{
        "issue_id": "U-OFFICIAL-PLAN-DESIGNATION",
        "question": ("What Official Plan land use designation applies to the "
                     "subject parcel?"),
        # MATERIAL, and measured rather than assumed: all 504 layers published
        # across the City's 24 public ArcGIS services were enumerated and none
        # carries Official Plan land use designations, nor does the City's open
        # data catalogue. The designation is published as PDF map sheets, which
        # cannot ground a deterministic spatial answer. For an employment-zoned
        # parcel this is decisive rather than incidental: the designation governs
        # conversion policy and the range of permitted uses.
        "materiality": "MATERIAL",
        "required_evidence": ("Official Plan land use designation for the parcel, "
                              "from an authoritative City source that can be "
                              "spatially related to the parcel boundary."),
    }, {
        "issue_id": "U-BYLAW-PROVISION-TEXT",
        "question": ("What do the retrieved by-law's provisions actually require "
                     "for this zone at provision level?"),
        "materiality": "MINOR",
        "required_evidence": ("Chapter and section text of Zoning By-law "
                              "569-2013 for the zone, retrieved as bytes."),
    }]
    for finding in gathered.get("absences") or []:
        if finding.get("present") is None:
            issues.append({
                "issue_id": "U-LAYER-%s" % (finding.get("layer_name") or "?")
                            .upper().replace(" ", "-")[:40],
                "question": ("Does the City's %s layer affect the subject parcel?"
                             % finding.get("layer_name")),
                "materiality": "MATERIAL",
                "required_evidence": "A successful read of that official layer.",
            })
    return issues


def run(address, *, reader, retrieved_at=None) -> dict:
    """The whole Gate 01 path from an address string. Never raises."""
    gathered = gather(address, reader=reader, retrieved_at=retrieved_at)
    resolved = gathered["resolved"]

    authority_outcome = gathered.get("authority") or {}
    authority_records = ([authority_outcome["record"]]
                         if authority_outcome.get("record") else [])

    statements = (_property_statements(gathered) + _zoning_statements(gathered)
                  + _absence_statements(gathered))

    outcome = lifecycle.run(
        address,
        resolver=lambda _address: resolved,   # already retrieved; not re-fetched
        authority_records=authority_records,
        statements=statements,
        layers=_layers(gathered),
        unresolved=_unresolved(gathered))
    outcome["retrieval"] = {
        "retrieved_at": gathered["retrieved_at"],
        "runner_version": RUNNER_VERSION,
        "source_version": gathered["source_version"],
        "zoning_layer": (gathered.get("zoning") or {}).get("layer"),
        "absences": [{k: v for k, v in f.items() if k != "witness_geometry"}
                     for f in gathered.get("absences") or []],
        "authority_acquired": authority_outcome.get("acquired", False),
    }
    return outcome
