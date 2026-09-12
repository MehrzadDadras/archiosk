"""CLAUDE-GENERALIZATION-02 - address in, Gate 01 envelope out, for Mississauga.

    ADDRESS -> mississauga_planning_source -> go_pdz_lifecycle -> VR-01..VR-20 -> STOP

The second municipal runner. It exists to answer one question the Toronto runner
could not: does the GO-PDZ path depend on how Toronto happens to publish data?

WHAT IS SHARED IS THE PART THAT MATTERS. `go_pdz_contract`, `go_pdz_validator`,
`planning_authority`, `deterministic_spatial` and `go_pdz_lifecycle` are used
here unchanged - the contract, the twenty rules, the authority classification,
the geometry engine and the assembly. What is NOT shared is the reader and the
statement wording, because field names, layer names, parcel-resolution strategy
and coordinate systems are all genuinely different. That split is the finding:
the governed machinery generalized, the source adapter did not, and the source
adapter is the cheap half.

THE SAME QUESTION, ANSWERED TWO WAYS. Toronto publishes no machine-readable
Official Plan land use designation across 504 layers, so the Toronto runner
retains the consolidated Plan as a document and leaves the designation
UNRESOLVED. Mississauga publishes Schedule 10 as polygons, so the same finding
here is ESTABLISHED on a deterministic token. Neither runner decides that -
`source_type` on the authority record does, which is what keeps the hierarchy in
section 3 a property of the evidence rather than of the municipality.

A CONVERGENCE CANDIDATE, DELIBERATELY NOT TAKEN YET. This module and
`toronto_gate01` now share the shape of their statement assembly. Two specimens
is not a pattern, and extracting a shared assembler from two would bake
Toronto's and Mississauga's accidents into an abstraction a third municipality
would immediately strain. The duplication is recorded rather than removed.

GATE 01 ENDS AT THE LEGAL ENVELOPE, here as everywhere.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from services import go_pdz_lifecycle as lifecycle
from services import mississauga_planning_source as source

logger = logging.getLogger(__name__)

RUNNER_VERSION = "mississauga-gate01@1"


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gather(address, *, reader, retrieved_at=None):
    retrieved_at = retrieved_at or _now()
    cache = {}
    attestation = source.catalogue_attestation(reader=reader, cache=cache)
    resolved = source.resolve_address(address, reader=reader, cache=cache)
    gathered = {"address": address, "retrieved_at": retrieved_at,
                "attestation": attestation, "resolved": resolved,
                "zoning": None, "land_use": None, "overlays": [],
                "heritage": None, "authority": None, "official_plan": None,
                "publication": None, "runner_version": RUNNER_VERSION,
                "source_version": source.SOURCE_VERSION}

    geometry, point = resolved.get("geometry"), resolved.get("point")
    if not geometry or not point:
        gathered["note"] = ("subject geometry was not established; no spatial "
                            "question can be asked of it")
        return gathered

    gathered["zoning"] = source.zoning_at(geometry, point, reader=reader,
                                          cache=cache)
    gathered["land_use"] = source.land_use_at(geometry, point, reader=reader,
                                              cache=cache)
    gathered["overlays"] = source.overlay_findings(geometry, point, reader=reader,
                                                   cache=cache)
    gathered["heritage"] = source.heritage_at(geometry, reader=reader,
                                              cache=cache)
    gathered["authority"] = source.acquire_zoning_bylaw(
        reader=reader, retrieved_at=retrieved_at, attestation=attestation)
    gathered["official_plan"] = source.acquire_official_plan(
        reader=reader, retrieved_at=retrieved_at, attestation=attestation)
    gathered["publication"] = source.acquire_geospatial_publication(
        reader=reader, retrieved_at=retrieved_at, attestation=attestation)
    return gathered


def _ids(gathered, *keys):
    out = []
    for key in keys:
        record = (gathered.get(key) or {}).get("record") or {}
        if record.get("authority_id"):
            out.append(record["authority_id"])
    return out


def _decided(finding):
    return (finding or {}).get("token", {}) and \
        finding["token"].get("spatial_basis") == "DETERMINISTIC_GIS"


def _statements(gathered):
    resolved = gathered.get("resolved") or {}
    statements = []

    if resolved.get("parcel_identifier"):
        statements.append({
            "statement_id": "S-PARCEL",
            "kind": "PROPERTY_FACT",
            "topic": "PARCEL_IDENTITY",
            "text": ("The address resolves to exactly one City of Mississauga "
                     "parcel, %s, in ward %s. The parcel was identified by an "
                     "ATTRIBUTE JOIN on the City's own CITY_PIN, not by spatial "
                     "inference - the publisher's own statement that this "
                     "address belongs to this parcel."
                     % (resolved["parcel_identifier"], resolved.get("ward"))),
            "statement_status": "ESTABLISHED",
            "confidence": "HIGH",
        })
    if resolved.get("stated_area"):
        statements.append({
            "statement_id": "S-PARCEL-AREA",
            "kind": "PROPERTY_FACT",
            "topic": "SITE_AREA",
            "text": ("The City's parcel record states an area of %s. This is the "
                     "City's stated figure, not a survey." % resolved["stated_area"]),
            "statement_status": "ESTABLISHED",
            "confidence": "MEDIUM",
        })

    zoning = gathered.get("zoning") or {}
    refs = _ids(gathered, "authority", "publication")
    if zoning.get("split"):
        # SPLIT ZONING. Two zones touch this lot, so there is no single answer to
        # "what is it zoned". Naming one would be more confident than the
        # evidence - which is exactly what the first run of this module did.
        zones = ", ".join("%s (%s)" % ((z.get("attributes") or {}).get("ZONE_CODE"),
                                       (z.get("token") or {}).get("spatial_relation"))
                          for z in zoning.get("zones") or [])
        statements.append({
            "statement_id": "S-ZONE",
            "kind": "PROPERTY_FACT",
            "topic": "ZONING_DESIGNATION",
            "text": ("The subject parcel is touched by %d distinct zones: %s. A "
                     "zone boundary runs through the property, so no single zone "
                     "governs it and none is asserted. Which standards apply to "
                     "which part of the lot is not determinable from the mapping "
                     "alone." % (zoning.get("zone_count"), zones)),
            "statement_status": "UNRESOLVED",
            "confidence": "LOW",
        })
    elif zoning.get("present"):
        zone_finding = (zoning.get("zones") or [{}])[0]
        attributes = zone_finding.get("attributes") or {}
        decided = _decided(zone_finding)
        statements.append({
            "statement_id": "S-ZONE",
            "kind": "AUTHORITY_SAYS",
            "topic": "ZONING_DESIGNATION",
            "text": ("The subject parcel lies within zone %r (%s) under "
                     "Mississauga Zoning By-law %s. Base zone designation: %s."
                     % (attributes.get("ZONE_CODE"),
                        attributes.get("ZONE_DESCRIPTION"),
                        attributes.get("BYLAW"),
                        attributes.get("BASE_ZONE_DESIGNATION"))),
            "authority_refs": refs,
            "statement_status": "ESTABLISHED" if decided and refs else "PROVISIONAL",
            "confidence": "HIGH" if decided and refs else "MEDIUM",
            "spatial_layer": "zoning" if decided else None,
        })
        if attributes.get("GREENLANDS_OVERLAY") not in (None, "", " ", "N"):
            statements.append({
                "statement_id": "S-ZONE-GREENLANDS",
                "kind": "AUTHORITY_SAYS",
                "topic": "NATURAL_HERITAGE",
                "text": ("The City's zoning record carries GREENLANDS_OVERLAY = "
                         "%r for this zone." % attributes.get("GREENLANDS_OVERLAY")),
                "authority_refs": refs,
                "statement_status": "PROVISIONAL",
                "confidence": "MEDIUM",
                "spatial_layer": "zoning" if decided else None,
            })

    land_use = gathered.get("land_use") or {}
    plan_refs = _ids(gathered, "official_plan", "publication")
    if land_use.get("present"):
        attributes = land_use.get("attributes") or {}
        decided = _decided(land_use)
        statements.append({
            "statement_id": "S-OP-DESIGNATION",
            "kind": "AUTHORITY_SAYS",
            "topic": "OFFICIAL_PLAN_DESIGNATION",
            # The contrast with Toronto is the point: there this finding is
            # UNRESOLVED because no polygon exists to compute against.
            "text": ("The subject parcel is designated %r (%s) on Schedule 10 "
                     "Land Use Designations of the Mississauga Official Plan "
                     "(2010). The designation polygon is published as machine-"
                     "readable geometry, so containment was computed rather "
                     "than read from a map."
                     % (attributes.get("MOP_DESCRIPTION"),
                        attributes.get("MOP_CODE"))),
            "authority_refs": plan_refs,
            "statement_status": ("ESTABLISHED" if decided and plan_refs
                                 else "PROVISIONAL"),
            "confidence": "HIGH" if decided and plan_refs else "MEDIUM",
            "spatial_layer": "land_use" if decided else None,
        })
    else:
        statements.append({
            "statement_id": "S-OP-DESIGNATION",
            "kind": "PROPERTY_FACT",
            "topic": "OFFICIAL_PLAN_DESIGNATION",
            "text": ("No Schedule 10 land use designation polygon covers the "
                     "subject parcel in the City's published Official Plan data."),
            "statement_status": "UNRESOLVED",
            "confidence": "LOW",
        })

    for index, finding in enumerate(gathered.get("overlays") or []):
        name = finding.get("layer_name")
        sid = "S-OVL-%02d" % index
        if finding.get("present") is None:
            statements.append({
                "statement_id": sid, "kind": "PROPERTY_FACT",
                "topic": finding.get("topic") or "POLICY",
                "text": ("Whether the City's %s affects the subject parcel could "
                         "not be determined: %s" % (name, finding.get("note"))),
                "statement_status": "UNRESOLVED", "confidence": "LOW"})
            continue
        decided = _decided(finding)
        if finding.get("present"):
            attributes = {k: v for k, v in (finding.get("attributes") or {}).items()
                          if k not in ("OBJECTID", "FID", "Shape__Area",
                                       "Shape__Length", "GIS_AREA", "MSLINK",
                                       "COLOUR_CODE", "UTM_X", "UTM_Y")
                          and v not in (None, "", " ")}
            described = ", ".join("%s = %s" % (k, v)
                                  for k, v in list(attributes.items())[:4])
            statements.append({
                "statement_id": sid, "kind": "AUTHORITY_SAYS",
                "topic": finding.get("topic") or "POLICY",
                "text": ("The City's %s applies to the subject parcel%s."
                         % (name, ": " + described if described else "")),
                "authority_refs": plan_refs,
                "statement_status": ("ESTABLISHED" if decided and plan_refs
                                     else "PROVISIONAL"),
                "confidence": "HIGH" if decided and plan_refs else "MEDIUM",
                "spatial_layer": ("overlay:%s" % name) if decided else None})
        else:
            statements.append({
                "statement_id": sid, "kind": "PROPERTY_FACT",
                "topic": finding.get("topic") or "POLICY",
                "text": ("No polygon of the City's %s covers the subject parcel "
                         "in the City's published Official Plan data. This rests "
                         "on the publisher's own spatial query; no independent "
                         "envelope proof was computed." % name),
                "statement_status": "PROVISIONAL", "confidence": "MEDIUM"})

    heritage = gathered.get("heritage") or {}
    if heritage.get("checked"):
        covering = heritage.get("covering") or []
        if covering:
            described = "; ".join(
                str((c.get("attributes") or {}).get("HERC_DESCRIPTION"))[:64]
                for c in covering[:3])
            text = ("%d listed heritage propert%s COVER the subject parcel, "
                    "computed deterministically: %s"
                    % (len(covering), "y" if len(covering) == 1 else "ies",
                       described))
        else:
            text = ("No listed heritage property polygon covers the subject "
                    "parcel (%d touch its bounding area; containment was "
                    "computed, not assumed)." % heritage.get("touching", 0))
        statements.append({
            "statement_id": "S-HERITAGE",
            "kind": "AUTHORITY_SAYS" if covering else "PROPERTY_FACT",
            "topic": "HERITAGE_LISTING",
            "text": text,
            "authority_refs": plan_refs if covering else [],
            "statement_status": ("ESTABLISHED" if covering and plan_refs
                                 else "PROVISIONAL"),
            "confidence": "HIGH" if covering and plan_refs else "MEDIUM",
            "spatial_layer": "heritage" if covering else None,
        })
    return [{k: v for k, v in s.items() if v is not None} for s in statements]


def _layers(gathered):
    layers = {}

    def add(key, finding):
        if finding and finding.get("present") and finding.get("geometry"):
            layers[key] = {"crs": source.WORKING_CRS,
                           "geometry": finding["geometry"],
                           "source": "City of Mississauga %s"
                                     % finding.get("layer_name"),
                           "version": "published schedule"}

    zoning = gathered.get("zoning") or {}
    if not zoning.get("split"):
        add("zoning", (zoning.get("zones") or [{}])[0])
    for finding in (gathered.get("heritage") or {}).get("covering") or []:
        add("heritage", finding)
        break
    add("land_use", gathered.get("land_use"))
    for finding in gathered.get("overlays") or []:
        add("overlay:%s" % finding.get("layer_name"), finding)
    return layers


def _unresolved(gathered):
    issues = [{
        "issue_id": "U-BYLAW-PROVISION-TEXT",
        "question": ("What does Zoning By-law 0225-2007 require for this zone at "
                     "provision level?"),
        "materiality": "MINOR",
        "required_evidence": ("Provision-level text for the zone from the City's "
                              "office consolidation."),
    }]
    if (gathered.get("zoning") or {}).get("split"):
        issues.append({
            "issue_id": "U-SPLIT-ZONING",
            "question": ("Which zone standards apply to which part of the "
                         "split-zoned parcel?"),
            "materiality": "MATERIAL",
            "required_evidence": ("The zone boundary location relative to the "
                                  "parcel, and the standards of each zone."),
        })
    if not (gathered.get("attestation") or {}).get("attested"):
        issues.append({
            "issue_id": "U-PUBLICATION-ATTESTATION",
            "question": ("Are the hosted geospatial services the City's own "
                         "publications?"),
            # MATERIAL: without the City's catalogue naming them, these are
            # layers on a platform that also hosts private uploads, and nothing
            # resting on them can be more than provisional.
            "materiality": "MATERIAL",
            "required_evidence": ("The City's open data catalogue naming the "
                                  "hosted services it publishes."),
        })
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
    for key in ("authority", "official_plan", "publication"):
        outcome = gathered.get(key) or {}
        if outcome.get("record"):
            records.append(outcome["record"])

    outcome = lifecycle.run(
        address,
        resolver=lambda _address: resolved,
        authority_records=records,
        statements=_statements(gathered),
        layers=_layers(gathered),
        unresolved=_unresolved(gathered))
    outcome["retrieval"] = {
        "retrieved_at": gathered["retrieved_at"],
        "runner_version": RUNNER_VERSION,
        "source_version": gathered["source_version"],
        "attestation": gathered.get("attestation"),
        "resolution_method": resolved.get("resolution_method"),
        "upstream_transformation": resolved.get("upstream_transformation"),
        "zoning": {k: v for k, v in (gathered.get("zoning") or {}).items()
                   if k not in ("geometry", "token")},
        "land_use": {k: v for k, v in (gathered.get("land_use") or {}).items()
                     if k not in ("geometry", "token")},
        "overlays": [{k: v for k, v in f.items()
                      if k not in ("geometry", "token")}
                     for f in gathered.get("overlays") or []],
        "heritage": gathered.get("heritage"),
    }
    return outcome
