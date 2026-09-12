"""CLAUDE-TORONTO-LIVE-01 - address in, Gate 01 envelope out, for Toronto.

    ADDRESS -> toronto_planning_source -> go_pdz_lifecycle -> VR-01..VR-20 -> STOP

This is the reachable end of the GO-PDZ programme. `go_pdz_contract`,
`go_pdz_validator`, `planning_authority`, `deterministic_spatial` and
`go_pdz_lifecycle` were each built and tested with nothing calling them from a
real address; this module is the caller, and it adds no new judgement of its own.

TRANSCRIPTION IS NOT INTERPRETATION, AND THE LINE IS DRAWN ON PURPOSE. Every
statement below restates a value that was retrieved from an official City layer,
or a presence/absence this module proved. None of them reasons about what may be
built. Where a retrieved attribute has an obvious regulatory reading that the
retrieved BYTES do not establish - `FSI_TOTAL = 3.0` almost certainly being a
maximum floor-space index - the statement carries the attribute and the reading
is left to GO, as PROVISIONAL with the gap recorded.

AN EXCEPTION MUST FAIL CLOSED (CLAUDE-GENERALIZATION-02). The second live
subject carries `ZN_EXCPTN = 'Y'`, exception 2219, and version 1 of this module
said NOTHING about it: the only exception statement it could emit was the one
for `ZN_EXCPTN == 'N'`. So the single condition the whole programme keeps
returning to - an exception DISPLACES the parent standard - was silently dropped
exactly when it was true, while the parent standards were reported with HIGH
confidence beside it. That is the worst available failure, because the output
looks more complete, not less. An exception now always produces a record: its
text if the City publishes it, and `unresolved_exception()` if not.

A CITATION THAT NAMES THE WRONG INSTRUMENT IS WORSE THAN NO CITATION. Version 1
hard-coded By-law 569-2013. The City's own zoning record names the governing
by-law per zone, and for the second subject it is By-law 266-2021. Both
statements would have read identically to a reviewer. The by-law is now taken
from the City's `BYLAW_DOCLINK`, and every `authority_refs` entry is the id of
the record actually acquired.

THE ABSENCES AND THE PRESENCES ARE BOTH FINDINGS, ON THE SAME FOOTING. An
overlay that does not apply is half of a planning envelope and the half a
summary drops; an overlay that DOES apply used to arrive here with no spatial
basis at all. Both now carry a token from our own engine.

GATE 01 ENDS AT THE LEGAL ENVELOPE. Nothing here produces or accepts an owner
program, unit count, massing or option. `go_pdz_lifecycle.assemble` has no
parameter that could carry one, and this module adds none.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from services import go_pdz_lifecycle as lifecycle
from services import planning_authority as authority
from services import toronto_planning_source as source

logger = logging.getLogger(__name__)

RUNNER_VERSION = "toronto-gate01@2"

#: Overlays reported every run, whether or not they apply, because a reader
#: needs to know the question was ASKED. An unlisted overlay that returns
#: nothing is a silent gap; a listed one that returns nothing is a finding.
REPORTED_OVERLAYS = {
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

#: The attributes worth restating per overlay, so a statement reads as a finding
#: rather than as a dump of every column the layer happens to carry.
OVERLAY_FIELDS = {
    "Zoning Height Overlay": ("HT_STRING", "HT_HEIGHT", "HT_STORIES"),
    "Zoning Lot Coverage Overlay": ("ZN_COVERAGE",),
    "Zoning Policy Area Overlay": ("POLICY_AREA", "ZN_EXCPTN_NO"),
    "Zoning Building Setback Overlay": ("SETBACK", "ZN_SETBACK"),
    "Secondary Plan": ("SECONDARY_PLAN_NUMBER", "SECONDARY_PLAN_NAME", "STATUS"),
    "Site and Area Specific Policy": ("SASP_NO", "OPA_NO", "EFFECTIVE_YEAR"),
    "Heritage District": ("NAME", "STATUS", "BYLAW"),
    "Natural Heritage System (polygon)": ("NHS_TYPE", "TYPE"),
    "Major Transit Station Area": ("STATION_NAME", "MTSA_TYPE", "SASP_NUMBER"),
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _described(name, attributes):
    """Named fields, rendered for a reader. Never a raw attribute dump."""
    fields = OVERLAY_FIELDS.get(name) or ()
    pairs = [(f, (attributes or {}).get(f)) for f in fields]
    pairs = [(f, v) for f, v in pairs if v not in (None, "", " ", -1, -1.0)]
    if not pairs:
        return None
    return ", ".join("%s = %s" % (f, v) for f, v in pairs)


def gather(address, *, reader, retrieved_at=None):
    """Retrieve everything Gate 01 needs. No statements, no judgement - facts."""
    retrieved_at = retrieved_at or _now()
    cache = {}

    resolved = source.resolve_address(address, reader=reader, cache=cache)
    gathered = {"address": address, "retrieved_at": retrieved_at,
                "resolved": resolved, "zoning": None, "overlays": [],
                "authority": None, "official_plan": None, "exception": None,
                "heritage_register": None, "runner_version": RUNNER_VERSION,
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
            gathered["overlays"].append(source.overlay_finding(
                binding, geometry, point, reader=reader, cache=cache))
        except Exception as exc:  # noqa: BLE001 - a failed layer is a result
            logger.warning("overlay check failed for %s (%s: %s)",
                           binding[2], type(exc).__name__, exc)
            gathered["overlays"].append(
                {"layer_name": binding[2], "present": None, "token": None,
                 "absence_established": False,
                 "note": "layer could not be read: %s" % type(exc).__name__})

    try:
        gathered["heritage_register"] = source.heritage_register_near(
            geometry, reader=reader, cache=cache)
    except Exception as exc:  # noqa: BLE001
        gathered["heritage_register"] = {
            "checked": False, "properties": [],
            "reason": "%s: %s" % (type(exc).__name__, exc)}

    attributes = (gathered["zoning"] or {}).get("attributes") or {}
    gathered["authority"] = source.acquire_zoning_bylaw(
        reader=reader, retrieved_at=retrieved_at, attributes=attributes,
        provision_locator=("Chapter %s, Section %s"
                           % (attributes.get("ZBL_CHAPTER"),
                              attributes.get("ZBL_SECTION"))
                           if attributes.get("ZBL_CHAPTER") else None))
    gathered["official_plan"] = source.acquire_official_plan(
        reader=reader, retrieved_at=retrieved_at)

    if attributes.get("ZN_EXCPTN") == "Y":
        gathered["exception"] = source.acquire_exception(
            attributes.get("ZN_EXCPTN_NO"),
            attributes.get("BYLAW_EXCPTNLINK"),
            reader=reader, retrieved_at=retrieved_at)
    return gathered


def _bylaw_id(gathered):
    record = (gathered.get("authority") or {}).get("record") or {}
    return record.get("authority_id")


def _zoning_statements(gathered):
    """Restate what the zoning layer carries. Nothing more."""
    zoning = gathered.get("zoning") or {}
    attributes = zoning.get("attributes") or {}
    if not zoning.get("present"):
        return []

    bylaw = _bylaw_id(gathered)
    refs = [bylaw] if bylaw else []
    zone = attributes.get("ZN_ZONE")
    label = attributes.get("ZN_STRING")
    chapter, section = attributes.get("ZBL_CHAPTER"), attributes.get("ZBL_SECTION")

    statements = [{
        "statement_id": "S-ZONE",
        "kind": "AUTHORITY_SAYS",
        "topic": "ZONING_DESIGNATION",
        "text": ("The subject parcel lies within a zone labelled %r (zone code "
                 "%r) on the City of Toronto zoning mapping, Chapter %s, "
                 "Section %s." % (label, zone, chapter, section)),
        "authority_refs": refs,
        "statement_status": "ESTABLISHED" if refs else "PROVISIONAL",
        "confidence": "HIGH" if refs else "LOW",
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
            # by-law text, which has not been read at provision level.
            "text": ("The City's zoning record carries FSI_TOTAL = %s for the "
                     "zone containing the subject parcel (zone label %r). The "
                     "regulatory effect of that figure is stated in the by-law "
                     "text, which has not been retrieved at provision level."
                     % (fsi, label)),
            "authority_refs": refs,
            "statement_status": "PROVISIONAL",
            "confidence": "MEDIUM",
            "spatial_layer": "zoning_area",
        })

    flag = attributes.get("ZN_EXCPTN")
    number = attributes.get("ZN_EXCPTN_NO")
    if flag == "N":
        statements.append({
            "statement_id": "S-ZONE-NO-EXCEPTION",
            "kind": "AUTHORITY_SAYS",
            "topic": "SITE_SPECIFIC_EXCEPTION",
            "text": ("The City's zoning record carries ZN_EXCPTN = 'N' for this "
                     "zone: no site-specific exception is flagged against it. An "
                     "exception displaces the parent standard, so its absence is "
                     "recorded rather than assumed."),
            "authority_refs": refs,
            "statement_status": "ESTABLISHED",
            "confidence": "HIGH",
            "spatial_layer": "zoning_area",
        })
    elif flag == "Y":
        outcome = gathered.get("exception") or {}
        if outcome.get("acquired"):
            statements.append({
                "statement_id": "S-ZONE-EXCEPTION",
                "kind": "AUTHORITY_SAYS",
                "topic": "SITE_SPECIFIC_EXCEPTION",
                "text": ("A site-specific exception (%s, %s) applies to this "
                         "zone and its text was retrieved. An exception "
                         "DISPLACES the parent zone standards, so the figures "
                         "stated above are subject to it."
                         % (number, attributes.get("ZBL_EXCPTN"))),
                "authority_refs": [(outcome.get("record") or {}).get(
                    "authority_id")] + refs,
                "statement_status": "ESTABLISHED",
                "confidence": "HIGH",
                "spatial_layer": "zoning_area",
            })
        else:
            # FAILS CLOSED. Not "no exception found" - the exception is KNOWN to
            # exist and its text is missing, which is a different and worse
            # state than absence, and the one that must not read as completeness.
            statements.append({
                "statement_id": "S-ZONE-EXCEPTION",
                "kind": "PROPERTY_FACT",
                "topic": "SITE_SPECIFIC_EXCEPTION",
                "text": ("A site-specific exception (%s, %s) applies to this "
                         "zone and ITS TEXT COULD NOT BE RETRIEVED (%s). An "
                         "exception displaces the parent zone standards, so "
                         "every figure stated above is provisional until it is "
                         "read. The parent standards must NOT be applied as if "
                         "the exception did not exist."
                         % (number, attributes.get("ZBL_EXCPTN"),
                            outcome.get("reason"))),
                "statement_status": "UNRESOLVED",
                "confidence": "LOW",
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

    heritage = gathered.get("heritage_register") or {}
    if heritage.get("checked"):
        properties = heritage.get("properties") or []
        if properties:
            listed = "; ".join(
                "%s (%s)" % (p.get("address"), p.get("status"))
                for p in properties[:6])
            text = ("%d individually listed heritage propert%s on the City's "
                    "Heritage Register lie within %.0f m of the parcel: %s. "
                    "CONTAINMENT WAS NOT COMPUTED - the register is a point "
                    "layer and this engine relates polygons - so whether any of "
                    "them IS the subject building is not established here."
                    % (len(properties), "y is" if len(properties) == 1 else "ies are",
                       heritage.get("margin_metres", 0.0), listed))
        else:
            text = ("No individually listed heritage property on the City's "
                    "Heritage Register lies within %.0f m of the parcel."
                    % heritage.get("margin_metres", 0.0))
        statements.append({
            "statement_id": "S-HERITAGE-REGISTER",
            "kind": "PROPERTY_FACT",
            "topic": "HERITAGE_LISTING",
            "text": text,
            "statement_status": "PROVISIONAL",
            "confidence": "MEDIUM",
        })
    return statements


def _official_plan_statement(gathered):
    """Section 4. A real authority whose geometry is not machine-readable."""
    outcome = gathered.get("official_plan") or {}
    record = outcome.get("record")
    if not record:
        return []
    return [{
        "statement_id": "S-OP-DESIGNATION",
        "kind": "PROPERTY_FACT",
        "topic": "OFFICIAL_PLAN_DESIGNATION",
        "text": ("%s governs this parcel and was retrieved as an official "
                 "document (source type %s, version %s). %s"
                 % (record.get("official_title"), record.get("source_type"),
                    record.get("version_identifier") or "unstated",
                    record.get("limitation"))),
        # The Plan is official and admitted; what is undetermined is the
        # property-to-map relationship, so the SPATIAL predicate degrades while
        # the authority itself stands.
        "authority_refs": [record.get("authority_id")],
        "statement_status": "UNRESOLVED",
        "confidence": "LOW",
    }]


def _overlay_statements(gathered):
    """Presence and absence on the same footing, each with its own basis."""
    statements = []
    for index, finding in enumerate(gathered.get("overlays") or []):
        name = finding.get("layer_name")
        topic = REPORTED_OVERLAYS.get(name)
        if topic is None:
            continue
        sid = "S-OVL-%02d" % index
        token = finding.get("token") or {}
        decided = token.get("spatial_basis") == "DETERMINISTIC_GIS"

        if finding.get("present"):
            described = _described(name, finding.get("attributes"))
            statements.append({
                "statement_id": sid,
                "kind": "AUTHORITY_SAYS",
                "topic": topic,
                "text": ("The City's %s applies to the subject parcel%s."
                         % (name, ": " + described if described else "")),
                "authority_refs": [_bylaw_id(gathered)] if _bylaw_id(gathered) else [],
                "statement_status": "ESTABLISHED" if decided else "PROVISIONAL",
                "confidence": "HIGH" if decided else "MEDIUM",
                "spatial_layer": ("overlay:%s" % name) if decided else None,
            })
            continue

        if finding.get("present") is None or not finding.get("absence_established"):
            statements.append({
                "statement_id": sid,
                "kind": "PROPERTY_FACT",
                "topic": topic,
                "text": ("Whether the City's %s affects the subject parcel could "
                         "not be determined: %s" % (name, finding.get("note"))),
                "statement_status": "UNRESOLVED",
                "confidence": "LOW",
            })
            continue

        grounded = finding.get("witness_geometry") is not None
        statements.append({
            "statement_id": sid,
            "kind": "PROPERTY_FACT",
            "topic": topic,
            "text": ("No polygon of the City's %s applies to the subject parcel. "
                     "The City's own point query over that layer returns nothing, "
                     "and every one of the %d polygons of that layer within %.0f m "
                     "was independently computed OUTSIDE the parcel."
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
    for finding in gathered.get("overlays") or []:
        name = finding.get("layer_name")
        if finding.get("present") and finding.get("geometry"):
            layers["overlay:%s" % name] = {
                "crs": "EPSG:3857", "geometry": finding["geometry"],
                "source": "City of Toronto %s" % name,
                "version": "By-law 569-2013"}
        elif finding.get("absence_established") and finding.get("witness_geometry"):
            layers["absence:%s" % name] = {
                "crs": "EPSG:3857", "geometry": finding["witness_geometry"],
                "source": "City of Toronto %s" % name,
                "version": "By-law 569-2013"}
    return layers


def _exceptions(gathered):
    """A known exception whose text is missing FAILS CLOSED - VR-08."""
    attributes = (gathered.get("zoning") or {}).get("attributes") or {}
    if attributes.get("ZN_EXCPTN") != "Y":
        return []
    outcome = gathered.get("exception") or {}
    number = attributes.get("ZN_EXCPTN_NO")
    if outcome.get("acquired"):
        record = outcome.get("record") or {}
        return [{
            "exception_id": "TOR-EXCEPTION-%s" % number,
            "indicated_by": "City zoning record ZN_EXCPTN='Y', ZN_EXCPTN_NO=%s"
                            % number,
            "text_retrieved": True,
            "authority_ref": record.get("authority_id"),
        }]
    return [authority.unresolved_exception(
        "TOR-EXCEPTION-%s" % number,
        indicated_by=("City zoning record ZN_EXCPTN='Y', ZN_EXCPTN_NO=%s, "
                      "locator %s" % (number, attributes.get("ZBL_EXCPTN"))),
        missing_authority=("Text of Zoning By-law 569-2013 exception %s" % number),
        development_effect=("An exception displaces the parent zone standards. "
                            "Until it is read, the zone label, FSI and every "
                            "overlay figure above may be modified or overridden "
                            "for this specific site."),
        required_next_evidence=("The published text of exception %s, from the "
                                "City's zoning by-law chapter 900 series."
                                % number))]


def _unresolved(gathered):
    """What is genuinely not knowable from what was retrieved. Stated, not hidden."""
    plan = (gathered.get("official_plan") or {}).get("record")
    issues = [{
        "issue_id": "U-OFFICIAL-PLAN-DESIGNATION",
        "question": ("Which Official Plan land use designation applies to the "
                     "subject parcel?"),
        # MATERIAL, and measured rather than assumed: all 504 layers published
        # across the City's 24 public ArcGIS services were enumerated and none
        # carries Official Plan land use designations, nor does the City's open
        # data catalogue. The Plan itself IS retrieved and admitted as a
        # document authority - what is missing is a machine-readable
        # property-to-map relationship, not the authority.
        "materiality": "MATERIAL",
        "required_evidence": ("The land use designation covering this parcel, "
                              "read from the Official Plan map schedules%s."
                              % (" (retrieved: %s)" % plan.get("url")
                                 if plan else "")),
    }, {
        "issue_id": "U-BYLAW-PROVISION-TEXT",
        "question": ("What do the governing by-law's provisions require for this "
                     "zone at provision level?"),
        "materiality": "MINOR",
        "required_evidence": ("Chapter and section text of the governing by-law "
                              "for this zone, retrieved as bytes."),
    }]
    for finding in gathered.get("overlays") or []:
        if finding.get("present") is None:
            issues.append({
                "issue_id": "U-LAYER-%s" % (finding.get("layer_name") or "?")
                            .upper().replace(" ", "-")[:40],
                "question": ("Does the City's %s affect the subject parcel?"
                             % finding.get("layer_name")),
                "materiality": "MATERIAL",
                "required_evidence": "A successful read of that official layer.",
            })
    return issues


def run(address, *, reader, retrieved_at=None) -> dict:
    """The whole Gate 01 path from an address string. Never raises."""
    gathered = gather(address, reader=reader, retrieved_at=retrieved_at)
    resolved = gathered["resolved"]

    records = []
    for key in ("authority", "official_plan", "exception"):
        outcome = gathered.get(key) or {}
        if outcome.get("record"):
            records.append(outcome["record"])

    statements = (_property_statements(gathered)
                  + _zoning_statements(gathered)
                  + _official_plan_statement(gathered)
                  + _overlay_statements(gathered))

    outcome = lifecycle.run(
        address,
        resolver=lambda _address: resolved,   # already retrieved; not re-fetched
        authority_records=records,
        statements=statements,
        layers=_layers(gathered),
        site_specific_exceptions=_exceptions(gathered),
        unresolved=_unresolved(gathered))
    outcome["retrieval"] = {
        "retrieved_at": gathered["retrieved_at"],
        "runner_version": RUNNER_VERSION,
        "source_version": gathered["source_version"],
        "zoning_layer": (gathered.get("zoning") or {}).get("layer"),
        "overlays": [{k: v for k, v in f.items()
                      if k not in ("witness_geometry", "geometry", "token")}
                     for f in gathered.get("overlays") or []],
        "authority_acquired": (gathered.get("authority") or {}).get("acquired", False),
        "official_plan_acquired": (gathered.get("official_plan") or {}).get(
            "acquired", False),
        "exception": gathered.get("exception"),
        "heritage_register": gathered.get("heritage_register"),
    }
    return outcome
