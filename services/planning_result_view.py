"""CLAUDE-PLANNING-RESULT-SURFACE-01 - a GO-PDZ document, arranged for a reader.

    GO-PDZ-1.0-ONEPAGE  ->  ten sections an architect can read in order

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT

It is a PROJECTION. It arranges statements the document already carries into the
sections the result surface presents, and it adds nothing: no figure is computed,
no conclusion is drawn, no absence is filled in. If the document does not say
something, the section says nothing.

It is NOT a second report structure. The section names and the vocabulary are the
contract's own, and the topics it routes on are the topics the municipal Gate-01
runners actually emit - `ZONING_DESIGNATION`, `DENSITY`, `HEIGHT_LIMIT`,
`TRANSIT_POLICY` and the rest - rather than a presentation vocabulary invented
here that would then need mapping to and from the real one.

NO STATEMENT IS EVER DROPPED. An unmapped topic is routed by `kind` to a
documented default rather than silently disappearing, and a test asserts that
every statement in a document reaches exactly one section. A projection that
loses a finding is worse than no projection: the reader cannot tell that
something is missing.

THE OPTIONS LIVE OUTSIDE THE DOCUMENT, ON PURPOSE

`GO-PDZ-1.0-ONEPAGE` has no options field and this tranche may not change the
schema. Development options are therefore carried on the ENVELOPE beside the
document, not inside it - which is also the honest shape: A/B/C/D are a
presentation of postures over one envelope, not additional governed statements.

HOST-ESTABLISHED FACT vs GO INTERPRETATION is read from `derivation`, the axis
built for exactly this question. DIRECT_AUTHORITY, PROPERTY_FACT and
DETERMINISTIC_DERIVATION are what ARCHIOSK establishes; MODEL_DERIVATION and
DEPENDENCY_FINDING are what GO read into the evidence. The surface shows the
difference because presenting the second as the first is the failure this whole
programme exists to prevent.
"""
from __future__ import annotations

from services import derivation_check
from services import go_pdz_contract as contract
from services import relation_binding

VIEW_VERSION = "planning-result-view@1"

#: How a fixture-rendered page announces itself. Read by the template; a page
#: without a real analysis behind it must never be mistakable for one.
DATA_CLASS_DEVELOPMENT = "DEVELOPMENT_FIXTURE"
DATA_CLASS_LIVE = "LIVE_ANALYSIS"

#: Section 5's ten sections, in order, with the key each one is addressed by.
SECTION_IDENTITY = "PROPERTY_IDENTITY"
SECTION_FRAMEWORK = "GOVERNING_PLANNING_FRAMEWORK"
SECTION_PERMITTED = "PERMITTED_DEVELOPMENT_CONTEXT"
SECTION_ENVELOPE = "DEVELOPMENT_ENVELOPE"
SECTION_MOBILITY = "MOBILITY_ACCESS_CONTEXT"
SECTION_CONSTRAINTS = "CONSTRAINTS_AND_OPPORTUNITIES"
SECTION_OPTIONS = "PLANNING_LEVEL_DEVELOPMENT_OPTIONS"
SECTION_UNRESOLVED = "UNRESOLVED_MUNICIPAL_CONFIRMATION"
SECTION_CONCLUSION = "PRE_DESIGN_CONCLUSION"
SECTION_EVIDENCE = "EVIDENCE_FOOTER"

SECTION_ORDER = (
    (SECTION_IDENTITY, "Property Identity"),
    (SECTION_FRAMEWORK, "Governing Planning Framework"),
    (SECTION_PERMITTED, "Permitted Development Context"),
    (SECTION_ENVELOPE, "Development Envelope"),
    (SECTION_MOBILITY, "Mobility / Access Context"),
    (SECTION_CONSTRAINTS, "Constraints & Opportunities"),
    (SECTION_OPTIONS, "Planning-Level Development Options"),
    (SECTION_UNRESOLVED, "Unresolved / Municipal Confirmation"),
    (SECTION_CONCLUSION, "Pre-Design Conclusion"),
    (SECTION_EVIDENCE, "Evidence Footer"),
)

#: Topic -> section. Every key is a topic a municipal Gate-01 runner really
#: emits (`toronto_gate01.REPORTED_OVERLAYS` and its statement builders), so this
#: map is checkable against the producer rather than aspirational.
TOPIC_SECTIONS = {
    "PARCEL_IDENTITY": SECTION_IDENTITY,
    "SITE_AREA": SECTION_IDENTITY,

    "ZONING_DESIGNATION": SECTION_FRAMEWORK,
    "SITE_SPECIFIC_EXCEPTION": SECTION_FRAMEWORK,
    "OFFICIAL_PLAN_DESIGNATION": SECTION_FRAMEWORK,
    "SECONDARY_PLAN": SECTION_FRAMEWORK,
    "SITE_SPECIFIC_POLICY": SECTION_FRAMEWORK,
    "BYLAW_APPLICABILITY": SECTION_FRAMEWORK,

    "PERMITTED_USE": SECTION_PERMITTED,
    "LAND_USE_CATEGORY": SECTION_PERMITTED,

    "DENSITY": SECTION_ENVELOPE,
    "HEIGHT_LIMIT": SECTION_ENVELOPE,
    "BUILDING_SETBACK": SECTION_ENVELOPE,
    "LOT_COVERAGE": SECTION_ENVELOPE,

    # POLICY_AREA sits here rather than under the framework because what it
    # decides, in Toronto, is the PARKING RATE - the City's own attribute links
    # straight to Chapter 970. Filing it as "policy" would bury a mobility
    # control under a heading nobody looks at for parking.
    "POLICY_AREA": SECTION_MOBILITY,
    "TRANSIT_POLICY": SECTION_MOBILITY,
    "PARKING": SECTION_MOBILITY,
    "LOADING": SECTION_MOBILITY,

    "HERITAGE": SECTION_CONSTRAINTS,
    "HERITAGE_LISTING": SECTION_CONSTRAINTS,
    "NATURAL_HERITAGE": SECTION_CONSTRAINTS,
}

#: Where a topic this map does not know goes. By KIND, so the destination is
#: still meaningful: something an authority says is framework context, and
#: something GO read into the evidence is an interpretation.
DEFAULT_SECTION_BY_KIND = {
    "AUTHORITY_SAYS": SECTION_FRAMEWORK,
    "PROPERTY_FACT": SECTION_IDENTITY,
    "GO_INTERPRETS": SECTION_CONSTRAINTS,
}

#: `derivation` classes ARCHIOSK establishes itself. Everything else on that axis
#: is a reading, and the surface labels it as one.
ESTABLISHED_DERIVATIONS = (
    contract.DERIVATION_DIRECT_AUTHORITY,
    contract.DERIVATION_PROPERTY_FACT,
    contract.DERIVATION_DETERMINISTIC,
)

#: Section 10's four postures. Order is presentation order; a result renders only
#: the ones it actually carries.
OPTION_POSTURES = (
    ("A", "AS-OF-RIGHT"),
    ("B", "MAXIMUM COMPLIANT"),
    ("C", "RELIEF-DEPENDENT"),
    ("D", "SPECULATIVE TEST"),
)

#: THE RENDERER DOES NOT DECIDE WHAT IS AN OPPORTUNITY.
#:
#: A first version sorted interpretations into the two columns by looking for
#: words like "permits" and "allows". It then filed "whether the Official Plan
#: permits this intensity CANNOT BE DETERMINED" as an opportunity, because the
#: sentence contains "permits" - a dependency presented to an architect as a
#: possibility. Reading intent out of prose is the exact fabrication this
#: programme refuses everywhere else, and a presentation layer is not where it
#: becomes acceptable.
#:
#: So the split is DECLARED by the producer, on the envelope beside the options,
#: and anything not declared an opportunity is shown as a constraint. The
#: contract has no such field and this tranche may not add one; over-reporting a
#: limit is also the safer error on a pre-design surface.
OPPORTUNITY_IDS_KEY = "opportunity_statement_ids"


def _is_established(statement) -> bool:
    return contract.derivation_of(statement) in ESTABLISHED_DERIVATIONS


def _section_for(statement) -> str:
    """Which section a statement belongs in.

    KIND DECIDES FIRST, and only for GO_INTERPRETS. A reading of the evidence
    belongs under Constraints & Opportunities whatever it is ABOUT - routing it
    by topic instead put the FSI trade-off under Development Envelope beside the
    figures it was interpreting, which left section 6 empty and, worse, placed an
    interpretation among the established controls. Sections 1-5 are what the
    municipality's records establish; section 6 is what was read into them.
    """
    if statement.get("kind") == "GO_INTERPRETS":
        return SECTION_CONSTRAINTS
    topic = (statement.get("topic") or "").upper()
    if topic in TOPIC_SECTIONS:
        return TOPIC_SECTIONS[topic]
    return DEFAULT_SECTION_BY_KIND.get(statement.get("kind"), SECTION_CONSTRAINTS)


def _presented(statement, authorities) -> dict:
    """One statement, with just enough decoration for a reader.

    Adds NOTHING the document does not carry. `established` and `authority_names`
    are both read from what is already there.
    """
    refs = [ref for ref in statement.get("authority_refs") or [] if ref]
    return {
        "statement_id": statement.get("statement_id"),
        "kind": statement.get("kind"),
        "topic": statement.get("topic"),
        "text": statement.get("text"),
        "status": statement.get("statement_status"),
        "confidence": statement.get("confidence"),
        "derivation": contract.derivation_of(statement),
        "established": _is_established(statement),
        "spatial_relation": statement.get("spatial_relation"),
        "spatial_basis": statement.get("spatial_basis"),
        "authority_refs": refs,
        "authority_names": [authorities[ref]["name"] for ref in refs
                            if ref in authorities],
        "derived_from": [ref for ref in statement.get("derived_from") or [] if ref],
        "attested": bool(statement.get("derivation_check")),
    }


def _sort_constraints(presented, opportunity_ids) -> dict:
    """Split section 6 using the producer's OWN declaration. See above."""
    declared = {ref for ref in opportunity_ids or [] if ref}
    constraints, opportunities = [], []
    for item in presented:
        target = (opportunities if item.get("statement_id") in declared
                  else constraints)
        target.append(item)
    return {"constraints": constraints, "opportunities": opportunities}


def build_view(result) -> dict:
    """Arrange one result envelope for the surface. Never raises on thin input.

    `result` is `{document, options, data_class, ...}` - the GO-PDZ document plus
    the presentation-only parts that the contract deliberately does not carry.
    """
    result = result or {}
    document = result.get("document") or {}
    authorities = {a.get("authority_id"): a
                   for a in document.get("authorities") or []
                   if isinstance(a, dict) and a.get("authority_id")}

    buckets = {key: [] for key, _label in SECTION_ORDER}
    for statement in document.get("statements") or []:
        if not isinstance(statement, dict):
            continue
        buckets[_section_for(statement)].append(_presented(statement, authorities))

    subject = document.get("subject") or {}
    exceptions = [e for e in document.get("site_specific_exceptions") or []
                  if isinstance(e, dict)]
    unresolved = [u for u in document.get("unresolved") or []
                  if isinstance(u, dict)]

    # An exception whose text was never retrieved is an unresolved item with a
    # different shape, and it belongs in the same place a reader looks for what
    # still needs confirming - not in a separate list they have to notice.
    unretrieved = [e for e in exceptions if not e.get("text_retrieved")]

    return {
        "view_version": VIEW_VERSION,
        "data_class": result.get("data_class") or DATA_CLASS_DEVELOPMENT,
        "preview": (result.get("data_class") or DATA_CLASS_DEVELOPMENT)
        != DATA_CLASS_LIVE,
        "fixture_note": result.get("fixture_note"),
        "contract": document.get("contract"),
        "gate": document.get("gate"),
        "next_authorized_gate": document.get("next_authorized_gate"),
        "result_status": document.get("result_status"),
        "section_order": SECTION_ORDER,
        "identity": {
            "address": subject.get("normalized_address")
            or subject.get("address_as_given"),
            "address_as_given": subject.get("address_as_given"),
            "municipality": subject.get("municipality"),
            "parcel_identifier": subject.get("parcel_identifier"),
            "identity_confidence": subject.get("identity_confidence"),
            "statements": buckets[SECTION_IDENTITY],
        },
        "framework": {
            "statements": buckets[SECTION_FRAMEWORK],
            "authorities": list(authorities.values()),
            "exceptions": exceptions,
        },
        "permitted": {"statements": buckets[SECTION_PERMITTED]},
        "envelope": {"statements": buckets[SECTION_ENVELOPE]},
        "mobility": {"statements": buckets[SECTION_MOBILITY]},
        "interpretation": _sort_constraints(
            buckets[SECTION_CONSTRAINTS], result.get(OPPORTUNITY_IDS_KEY)),
        "options": [option for option in result.get("options") or []
                    if isinstance(option, dict)],
        "unresolved": unresolved,
        "unretrieved_exceptions": unretrieved,
        "conclusion": result.get("conclusion"),
        "evidence": list(authorities.values()),
        "retrieval": result.get("retrieval") or {},
    }


# ---------------------------------------------------------------------------
# DEVELOPMENT FIXTURE. NOT AN ANALYSIS OF ANY REAL PROPERTY.
# ---------------------------------------------------------------------------
# Section 4: a controlled development result object, used to prove RENDERING and
# nothing else. The address is deliberately a synthetic one ("Example Avenue"),
# so no reader can mistake this page for a finding about a property that exists,
# and so nothing here can be confused with the reserved benchmark subject.
#
# It is a REAL GO-PDZ-1.0-ONEPAGE DOCUMENT: a test validates it against
# `go_pdz_contract.SCHEMA` and runs `go_pdz_validator.validate` over it with zero
# errors. A fixture that could not exist would prove nothing about rendering the
# real thing.
#
# `result_status` is UNRESOLVED, and that is correct rather than pessimistic: one
# MATERIAL unresolved issue is present, and VR-15 says a material unresolved
# condition must reach the result status. The surface therefore exercises its
# most important state rather than its happiest one.
DEVELOPMENT_FIXTURE = {
    "data_class": DATA_CLASS_DEVELOPMENT,
    "fixture_note": (
        "Development fixture. This is a rendering specimen built on a synthetic "
        "address, not an analysis of a real property, and no municipal source or "
        "model was consulted to produce it."
    ),
    "document": {
        "contract": contract.CONTRACT_ID,
        "schema_version": contract.SCHEMA_VERSION,
        "gate": contract.GATE_01,
        "next_authorized_gate": contract.GATE_02,
        "subject": {
            "subject_id": "FIXTURE-SUBJECT-1",
            "address_as_given": "100 Example Avenue, Toronto, ON",
            "normalized_address": "100 Example Ave, Toronto, ON",
            "parcel_identifier": "FIXTURE-PARCEL-0000000",
            "municipality": "City of Toronto",
            "identity_confidence": "HIGH",
        },
        "authorities": [
            {"authority_id": "FIXTURE-BYLAW", "name": "Zoning By-law (example)",
             "instrument": "Zoning By-law", "citation": "Chapter 40, Section 40.10",
             "version_identifier": "example consolidation",
             "source_type": "MACHINE_READABLE_LAYER",
             "authority_status": "IN_FORCE", "effective_date": "2013-05-09",
             "retrieved_at": "2026-09-13T00:00:00Z"},
            {"authority_id": "FIXTURE-OP", "name": "Official Plan (example)",
             "instrument": "Official Plan",
             "version_identifier": "example consolidation",
             "source_type": "MAP_SCHEDULE",
             "authority_status": "IN_FORCE",
             "retrieved_at": "2026-09-13T00:00:00Z"},
        ],
        "statements": [
            {"statement_id": "F-PARCEL", "kind": "PROPERTY_FACT",
             "topic": "PARCEL_IDENTITY",
             "text": "The address resolves to exactly one property boundary in "
                     "the municipal parcel record.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": [], "conflict_refs": [], "derived_from": []},
            {"statement_id": "F-AREA", "kind": "PROPERTY_FACT",
             "topic": "SITE_AREA",
             "text": "The parcel record states a lot area of 612 m2. This is the "
                     "municipality's stated figure, not a survey.",
             "statement_status": "ESTABLISHED", "confidence": "MEDIUM",
             "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
             "authority_refs": [], "conflict_refs": [], "derived_from": []},
            {"statement_id": "F-ZONE", "kind": "AUTHORITY_SAYS",
             "topic": "ZONING_DESIGNATION",
             "text": "The parcel lies within a zone labelled 'CR 2.0 (c1.0; "
                     "r1.5)' on the municipal zoning mapping.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-NO-EXCEPTION", "kind": "AUTHORITY_SAYS",
             "topic": "SITE_SPECIFIC_EXCEPTION",
             "text": "No site-specific exception is flagged against this zone. "
                     "An exception displaces the parent standard, so its absence "
                     "is recorded rather than assumed.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-OP", "kind": "PROPERTY_FACT",
             "topic": "OFFICIAL_PLAN_DESIGNATION",
             "text": "The Official Plan governs this parcel and was retrieved as "
                     "a map schedule. The property-to-schedule relationship is "
                     "not machine-readable and has not been established here.",
             "statement_status": "UNRESOLVED", "confidence": "LOW",
             "spatial_relation": "AMBIGUOUS", "spatial_basis": "NONE",
             "authority_refs": ["FIXTURE-OP"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-USE", "kind": "AUTHORITY_SAYS",
             "topic": "PERMITTED_USE",
             "text": "The zone is a Commercial Residential zone: it contemplates "
                     "residential and non-residential uses on the same lot.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-FSI", "kind": "AUTHORITY_SAYS",
             "topic": "DENSITY",
             "text": "The zoning record carries a total floor space index of 2.0, "
                     "with component figures of 1.0 for commercial use and 1.5 "
                     "for residential use.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-HEIGHT", "kind": "AUTHORITY_SAYS",
             "topic": "HEIGHT_LIMIT",
             "text": "A height overlay applies, stating a maximum building "
                     "height of 12.0 m.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-SETBACK", "kind": "AUTHORITY_SAYS",
             "topic": "BUILDING_SETBACK",
             "text": "A building setback overlay applies to this parcel.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-PARKING", "kind": "AUTHORITY_SAYS",
             "topic": "POLICY_AREA",
             "text": "The parcel falls within Policy Area 1, which is the "
                     "attribute that governs parking rates for this zone.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "INSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": []},
            {"statement_id": "F-MTSA", "kind": "PROPERTY_FACT",
             "topic": "TRANSIT_POLICY",
             "text": "No Major Transit Station Area applies to this parcel, and "
                     "every polygon of that layer within 2 km was computed "
                     "outside it.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "OUTSIDE", "spatial_basis": "DETERMINISTIC_GIS",
             "authority_refs": [], "conflict_refs": [], "derived_from": []},
            {"statement_id": "F-FSI-ENVELOPE", "kind": "GO_INTERPRETS",
             "topic": "DENSITY",
             "text": "The component figures of 1.0 and 1.5 sum to 2.5, which "
                     "exceeds the total of 2.0 by 0.5, so they cannot both be "
                     "taken in full on the same site.",
             "statement_status": "ESTABLISHED", "confidence": "HIGH",
             "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
             "authority_refs": ["FIXTURE-BYLAW"], "conflict_refs": [],
             "derived_from": ["F-FSI"],
             "derivation": contract.DERIVATION_DETERMINISTIC,
             "derivation_check": None},   # filled in below by the real verifier
            {"statement_id": "F-MIX", "kind": "GO_INTERPRETS",
             "topic": "DENSITY",
             "text": "Because the total is the binding figure, a mixed-use "
                     "scheme permits roughly 1.0 of commercial floor space only "
                     "if residential is held to 1.0 - the trade-off, rather than "
                     "either maximum, is what shapes a scheme here.",
             "statement_status": "PROVISIONAL", "confidence": "MEDIUM",
             "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
             "authority_refs": [], "conflict_refs": [],
             "derived_from": ["F-FSI-ENVELOPE"],
             "derivation": contract.DERIVATION_MODEL},
            {"statement_id": "F-OP-DEPENDENCY", "kind": "GO_INTERPRETS",
             "topic": "OFFICIAL_PLAN_DESIGNATION",
             "text": "Whether the Official Plan designation permits this "
                     "intensity cannot be determined until the schedule is read "
                     "for this parcel; the zoning figures above do not answer it.",
             "statement_status": "PROVISIONAL", "confidence": "HIGH",
             "spatial_relation": "NOT_APPLICABLE", "spatial_basis": "NONE",
             "authority_refs": [], "conflict_refs": [],
             "derived_from": ["F-OP"],
             "derivation": contract.DERIVATION_DEPENDENCY},
        ],
        "site_specific_exceptions": [],
        "unresolved": [
            {"issue_id": "U-OFFICIAL-PLAN-DESIGNATION",
             "question": "Which Official Plan land-use designation applies to "
                         "this parcel?",
             "materiality": "MATERIAL",
             "required_evidence": "The Official Plan land-use schedule read for "
                                  "this parcel, or a municipal confirmation of "
                                  "the designation."},
            {"issue_id": "U-BYLAW-PROVISION-TEXT",
             "question": "What do the by-law provisions say at the level of the "
                         "individual standard?",
             "materiality": "MINOR",
             "required_evidence": "The by-law chapter text for the zone's own "
                                  "provisions."},
        ],
        "result_status": "UNRESOLVED",
    },
    # Declared by the producer, never inferred from wording. The mixed-use
    # trade-off is genuinely an opportunity - it says what the envelope makes
    # available. The Official Plan dependency is not, however its sentence reads.
    "opportunity_statement_ids": ["F-MIX"],
    # Section 10. Presentation postures over ONE envelope, carried beside the
    # document because the contract has no options field and this tranche may not
    # add one.
    "options": [
        {"key": "A", "posture": "AS-OF-RIGHT",
         "title": "Build within the stated figures",
         "rationale": "Uses only the zoning figures that are established, with "
                      "no relief sought and no unresolved question relied on.",
         "enabling_conditions": [
             "Total floor space index held at or below 2.0",
             "Building height at or below the 12.0 m overlay",
             "Parking provided at the Policy Area 1 rate"],
         "key_constraint": "The commercial and residential component figures "
                           "cannot both be taken in full.",
         "unresolved_dependency": None},
        {"key": "B", "posture": "MAXIMUM COMPLIANT",
         "title": "Take the full permitted total",
         "rationale": "Allocates the whole 2.0 total between uses rather than "
                      "leaving capacity unused.",
         "enabling_conditions": [
             "A mix that sums to the 2.0 total",
             "Massing that fits the height overlay and the setback overlay"],
         "key_constraint": "Height, not density, is usually what binds first on "
                           "a lot of this size.",
         "unresolved_dependency": "The Official Plan designation is not "
                                  "established, and it bears on intensity."},
        {"key": "C", "posture": "RELIEF-DEPENDENT",
         "title": "Exceed a stated standard through a planning process",
         "rationale": "Describes the pathway and its tests, not an outcome: "
                      "relief is applied for, considered and decided by others.",
         "enabling_conditions": [
             "A specific standard identified as the one to be varied",
             "A planning rationale addressing the applicable tests"],
         "key_constraint": "Nothing here indicates whether relief would be "
                           "granted, and this surface does not predict it.",
         "unresolved_dependency": "The by-law provision text has not been read "
                                  "at the level of the individual standard."},
    ],
    "conclusion": (
        "The zoning figures for this parcel are established and internally "
        "constrained: the total is the binding control and the component figures "
        "cannot both be realised. A pre-design envelope can be stated on that "
        "basis. What cannot yet be concluded is whether the Official Plan "
        "designation supports this intensity, and that question is material - so "
        "this result is UNRESOLVED rather than governed, and the Official Plan "
        "schedule is the next evidence to obtain."
    ),
    "retrieval": {
        "retrieved_at": "2026-09-13T00:00:00Z",
        "runner_version": "development-fixture",
        "source_version": "development-fixture",
    },
}


def _attest_fixture() -> None:
    """Give the fixture's deterministic statement a REAL attestation.

    Built by the same verifier and the same binding identity the live path uses,
    over the fixture's own figures. Hand-writing an attestation would have been
    fabricating a proof object - and VR-21 caught the first version of this
    fixture doing exactly that: a statement declaring DETERMINISTIC_DERIVATION
    with nothing behind it is governed as a model derivation and may not be
    stated as ESTABLISHED / HIGH. The validator was right.

    Pure arithmetic, offline: `derivation_check` and `relation_binding` touch no
    network and no model, which is what keeps this surface honest about making
    no live call.
    """
    statement = next(s for s in DEVELOPMENT_FIXTURE["document"]["statements"]
                     if s["statement_id"] == "F-FSI-ENVELOPE")
    components, total = [1.0, 1.5], 2.0
    labels = ["FSI_COMMERCIAL_USE", "FSI_RESIDENTIAL_USE"]
    attestation = derivation_check.check_components_exceed_total(
        components=components, total=total, labels=labels,
        inputs_established=True, unresolved_affecting=[])
    attestation["verified_at"] = "2026-09-13T00:00:00Z"
    attestation["binder_version"] = relation_binding.BINDER_VERSION
    attestation["binding"] = relation_binding.binding_identity(
        statement["statement_id"],
        derivation_check.RELATION_COMPONENTS_EXCEED_TOTAL,
        {"components": components, "total": total})
    attestation["evidence_refs"] = labels + ["FSI_TOTAL"]
    statement["derivation_check"] = attestation


_attest_fixture()


def development_view() -> dict:
    """The fixture, projected. The only result this surface can serve today."""
    return build_view(DEVELOPMENT_FIXTURE)
