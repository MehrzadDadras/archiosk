"""CLAUDE-GO-PDZ-LIFECYCLE-01 - address in, validated envelope out, then stop.

    ADDRESS
      -> PROPERTY IDENTITY
      -> AUTHORITY ACQUISITION      (official sources only)
      -> DETERMINISTIC SPATIAL      (geometry, never appearance)
      -> GO-PDZ STRUCTURED RESULT
      -> VR-01..VR-20
      -> GATE_01 STOP

The reachable path. Until now GO-PDZ was a contract with no producer and a
validator with no caller - implemented, deployed, and unreachable, the same
pattern this programme has now produced three times. This assembles the two new
seams into it.

NOTHING HERE INTERPRETS. `assemble()` is a builder: it turns already-acquired
authority records and already-computed spatial tokens into a contract-shaped
document and validates it. The planning judgement stays where it belongs - with
GO, whose statements arrive as inputs and are checked, not authored here.

TWO REFUSALS ARE STRUCTURAL RATHER THAN CHECKED AFTERWARDS:

  - **A non-official source cannot become an AUTHORITY_SAYS authority.**
    `planning_authority.may_satisfy_authority_says` gates the authorities list on
    the way in, so a secondary source is dropped from the authority set and the
    statement that leaned on it fails VR-04 rather than passing on a citation it
    should never have had.

  - **A spatial token is copied, never composed.** The relation and its basis
    come from `deterministic_spatial.relate()` verbatim. There is no code path
    here that can write `INSIDE` - which is what makes VR-09 enforceable instead
    of merely stated.

GATE 01 STOPS AT THE ENVELOPE. Owner program, statement of requirements, budget,
unit and room counts, massing and option selection all belong to
`GATE_02_OWNER_PROGRAM_ENTRY`. `assemble()` has no parameter that could carry
one, which is a stronger guarantee than a validator rule alone.
"""
from __future__ import annotations

import logging
from typing import Optional

from services import deterministic_spatial as spatial
from services import go_pdz_validator as validator
from services import planning_authority as authority
from services.go_pdz_contract import CONTRACT_ID, GATE_01, GATE_02, SCHEMA_VERSION

logger = logging.getLogger(__name__)

LIFECYCLE_VERSION = "go-pdz-lifecycle@1"


def resolve_identity(address, *, resolver) -> dict:
    """Establish WHICH parcel before anything is said about it.

    `resolver` is injected - there is no default and nothing here reaches a
    network. It returns `{parcel_identifier, normalized_address, municipality,
    parcel_count, geometry, crs, source}`; anything it cannot establish comes
    back as None and lowers identity confidence rather than being invented.

    Section 5's rule from the original contract: an ambiguous address match is
    not a starting point. More than one parcel, or none, yields UNRESOLVED, and
    VR-02 then forbids any ESTABLISHED authority statement about it.
    """
    try:
        resolved = resolver(address) or {}
    except Exception as exc:  # noqa: BLE001 - a failed lookup is a result
        logger.warning("identity resolution failed for %r (%s: %s)",
                       address, type(exc).__name__, exc)
        resolved = {}

    count = resolved.get("parcel_count")
    if count == 1 and resolved.get("parcel_identifier"):
        confidence = "HIGH"
    elif count == 1:
        confidence = "MEDIUM"
    elif count in (None, 0):
        confidence = "UNRESOLVED"
    else:
        confidence = "UNRESOLVED"      # several parcels is not one parcel

    return {
        "subject_id": resolved.get("subject_id") or ("SUBJ-" + str(abs(hash(
            (address or "").strip().upper())))[:10]),
        "address_as_given": address,
        "normalized_address": resolved.get("normalized_address"),
        "parcel_identifier": resolved.get("parcel_identifier"),
        "municipality": resolved.get("municipality"),
        "identity_confidence": confidence,
        # Not part of the contract document - carried alongside for the spatial
        # stage, which needs the geometry the contract does not record.
        "_geometry": resolved.get("geometry"),
        "_crs": resolved.get("crs"),
        "_geometry_source": resolved.get("source"),
        "_parcel_count": count,
    }


def spatial_context(identity, layers) -> dict:
    """One deterministic token per authority layer. `layers` is a dict of
    `{layer_name: {"crs", "geometry", "source", "version", "conflicting"}}`.

    Every value is produced by `deterministic_spatial.relate()`; this function
    performs no geometry of its own.
    """
    tokens = {}
    for name, layer in (layers or {}).items():
        layer = layer or {}
        tokens[name] = spatial.relate(
            {"crs": identity.get("_crs"), "geometry": identity.get("_geometry")},
            {"crs": layer.get("crs"), "geometry": layer.get("geometry")},
            subject_source=identity.get("_geometry_source"),
            layer_source=layer.get("source"),
            layer_version=layer.get("version"),
            subject_parcel_count=identity.get("_parcel_count") or 1,
            conflicting_layers=bool(layer.get("conflicting")))
    return tokens


def _applicability_to_authority_status(applicability):
    return {
        authority.APPLICABILITY_CURRENT: "IN_FORCE",
        authority.APPLICABILITY_ADOPTED_NOT_IN_FORCE: "ADOPTED_NOT_IN_FORCE",
        authority.APPLICABILITY_HISTORICAL: "SUPERSEDED",
        authority.APPLICABILITY_SUPERSEDED: "SUPERSEDED",
        authority.APPLICABILITY_UNKNOWN: "UNKNOWN",
    }.get(applicability, "UNKNOWN")


def assemble(*, identity, authority_records, statements,
             spatial_tokens=None, site_specific_exceptions=None,
             unresolved=None) -> dict:
    """Build the contract document. Validates nothing and interprets nothing.

    Authority records that cannot ground an AUTHORITY_SAYS statement are
    EXCLUDED from `authorities` rather than downgraded, and the exclusions are
    returned separately so the omission is visible. A statement that cited one
    then fails VR-04 or VR-19, which is the correct outcome: the citation was
    never admissible.
    """
    admitted, excluded = [], []
    for record in authority_records or []:
        if authority.may_satisfy_authority_says(record):
            admitted.append({
                "authority_id": record.get("authority_id"),
                "name": record.get("official_title") or record.get(
                    "issuing_authority"),
                "instrument": record.get("issuing_authority"),
                "citation": record.get("provision_locator"),
                "effective_date": record.get("effective_date"),
                "authority_status": _applicability_to_authority_status(
                    record.get("applicability")),
                "retrieved_at": record.get("retrieved_at"),
                "url": record.get("url"),
            })
        else:
            excluded.append({
                "authority_id": record.get("authority_id"),
                "url": record.get("url"),
                "source_class": record.get("source_class"),
                "reason": record.get("source_class_reason"),
            })

    prepared = []
    tokens = spatial_tokens or {}
    for statement in statements or []:
        statement = dict(statement)
        layer = statement.pop("spatial_layer", None)
        if layer is not None:
            token = tokens.get(layer)
            if token is None:
                statement["spatial_relation"] = spatial.RELATION_AMBIGUOUS
                statement["spatial_basis"] = spatial.BASIS_NONE
            else:
                # COPIED, never composed. Nothing here can write INSIDE.
                statement["spatial_relation"] = token["spatial_relation"]
                statement["spatial_basis"] = token["spatial_basis"]
        statement.setdefault("spatial_relation", spatial.RELATION_NOT_APPLICABLE)
        statement.setdefault("spatial_basis", spatial.BASIS_NONE)
        statement.setdefault("authority_refs", [])
        statement.setdefault("conflict_refs", [])
        statement.setdefault("derived_from", [])
        prepared.append(statement)

    exceptions = list(site_specific_exceptions or [])
    issues = list(unresolved or [])

    # FAIL CLOSED. An unreadable exception, or a material unresolved issue, and
    # the result is not a governed result - decided here rather than left for a
    # caller to remember.
    unreadable = any(not e.get("text_retrieved") for e in exceptions)
    material = any(i.get("materiality") == "MATERIAL" for i in issues)
    result_status = "UNRESOLVED" if (unreadable or material) else "GOVERNED_RESULT"

    document = {
        "contract": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "gate": GATE_01,
        "next_authorized_gate": GATE_02,
        "subject": {k: v for k, v in identity.items() if not k.startswith("_")},
        "authorities": admitted,
        "statements": prepared,
        "site_specific_exceptions": exceptions,
        "unresolved": issues,
        "result_status": result_status,
    }
    return {"document": document, "excluded_authorities": excluded,
            "spatial_tokens": tokens, "lifecycle_version": LIFECYCLE_VERSION}


def run(address, *, resolver, authority_records, statements, layers=None,
        site_specific_exceptions=None, unresolved=None) -> dict:
    """The whole Gate 01 path, assembled and validated. Never raises.

    Returns the document, the validation envelope, and the evidence that was
    refused along the way. Stops at Gate 01 - there is no parameter here through
    which an owner program could arrive.
    """
    identity = resolve_identity(address, resolver=resolver)
    tokens = spatial_context(identity, layers or {})
    built = assemble(
        identity=identity, authority_records=authority_records,
        statements=statements, spatial_tokens=tokens,
        site_specific_exceptions=site_specific_exceptions, unresolved=unresolved)
    outcome = validator.validate(built["document"])
    return {
        "lifecycle_version": LIFECYCLE_VERSION,
        "gate": GATE_01,
        "gate_stop": ("Gate 01 ends at the legal envelope. Owner program, "
                      "requirements, budget, counts, massing and option "
                      "selection are %s and are not produced here." % GATE_02),
        "identity": identity,
        "document": built["document"],
        "excluded_authorities": built["excluded_authorities"],
        "spatial_tokens": tokens,
        "validation": outcome,
        "promotable": outcome["promotable"],
    }
