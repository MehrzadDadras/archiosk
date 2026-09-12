"""CLAUDE-GO-PDZ-CONTRACT-01 - the address-only planning/zoning envelope.

    ADDRESS IN. LEGAL ENVELOPE OUT. STOP BEFORE OWNER PROGRAM.

GO-PDZ is the contract for what ARCHIOSK may return when it is given nothing but
a municipal address. It exists because the blind 35 Taber reconnaissance showed
that the hard part is not producing planning prose - it is refusing to produce
the parts that are not yet knowable, and being checkable about the difference.

THREE LAYERS, DELIBERATELY NOT COLLAPSED:

    STRUCTURE VALID   !=   SEMANTICALLY VALID   !=   GOVERNED AUTHORITY

`SCHEMA` below answers only the first: are the fields present and of the right
shape. `go_pdz_validator` answers the second: is the evidence discipline sound.
Neither answers the third, and nothing here ever will - the municipality and the
legislature remain the authority, and a passing result is a governed
INTERPRETATION of them.

THE GATE IS THE POINT. `GATE_01_ADDRESS_ONLY_ENVELOPE` ends where the owner's
program begins. A result that names unit counts, room counts, a budget, a
statement of requirements, massing, or a chosen option has not answered the
address question better - it has answered a different question nobody asked yet,
using facts nobody supplied. `GATE_02_OWNER_PROGRAM_ENTRY` is where those become
legitimate, and it is not this gate.

NO NEW DEPENDENCY. The schema is a real JSON Schema document so it travels, but
structural checking is done by `validate_structure` here rather than by adding
`jsonschema` to `requirements.txt`, which ships to the production host. The
package passes `tools/dependency_fit.py`; it is simply not needed for the subset
this contract uses, and the check it would perform is ~60 lines.

DERIVATION NOTE, RECORDED RATHER THAN IMPLIED. The authorizing prompt referred to
"the supplied schema" and to a `100 Example Avenue` fixture, neither of which was
attached. Both are DERIVED here from that prompt's own stated requirements - the
gate boundaries, the `spatial_relation` vocabulary, `conflict_refs`, the
ERROR/WARNING/INFO model, the required validator output fields, and the ten
negative cases. Rule identifiers live in one table in `go_pdz_validator` so that
re-keying them to a canonical specification, if one exists, is a single edit and
not a rewrite.
"""
from __future__ import annotations

CONTRACT_ID = "GO-PDZ-1.0-ONEPAGE"
SCHEMA_VERSION = "1.0"

GATE_01 = "GATE_01_ADDRESS_ONLY_ENVELOPE"
GATE_02 = "GATE_02_OWNER_PROGRAM_ENTRY"

#: What Gate 01 may not contain. Not a style preference: each of these requires a
#: fact the address alone cannot supply, so a Gate 01 result that states one is
#: asserting something it cannot have obtained.
GATE_01_FORBIDDEN_TOPICS = (
    "OWNER_PROGRAM", "STATEMENT_OF_REQUIREMENTS", "BUDGET", "UNIT_COUNT",
    "ROOM_COUNT", "MASSING", "OPTION_SELECTION", "DETAILED_DESIGN",
)

STATEMENT_KINDS = ("AUTHORITY_SAYS", "PROPERTY_FACT", "GO_INTERPRETS")

#: Evidential standing, distinct from confidence. A statement can be PROVISIONAL
#: and still be highly confident about being provisional.
STATEMENT_STATUSES = ("ESTABLISHED", "PROVISIONAL", "UNRESOLVED")
CONFIDENCES = ("HIGH", "MEDIUM", "LOW")

#: Where an authority stands in time. `ADOPTED_NOT_IN_FORCE` is the state that
#: caught out the blind reconnaissance: Toronto's OPA 804 is adopted and awaiting
#: ministerial approval, and treating it as binding would be wrong in the same
#: way as ignoring it.
AUTHORITY_STATUSES = (
    "IN_FORCE", "ADOPTED_NOT_IN_FORCE", "UNDER_APPEAL", "SUPERSEDED", "UNKNOWN",
)

#: Spatial predicates. These are TOKENS GO CONSUMES, never tokens GO MINTS.
SPATIAL_RELATIONS = (
    "INSIDE", "OUTSIDE", "INTERSECTS", "APPEARS_INSIDE", "AMBIGUOUS",
    "NOT_APPLICABLE",
)
#: How a spatial predicate was obtained. Only the first may carry an assertive
#: predicate; everything else degrades to APPEARS_INSIDE or AMBIGUOUS.
SPATIAL_BASES = ("DETERMINISTIC_GIS", "VISUAL_IMPRESSION", "NONE")
#: The predicates that assert a definite geometric fact.
ASSERTIVE_SPATIAL = ("INSIDE", "OUTSIDE", "INTERSECTS")

RESULT_STATUSES = ("GOVERNED_RESULT", "UNRESOLVED")

SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"


#: The machine-readable structural contract. Written as a JSON Schema document so
#: it can be published, diffed and consumed elsewhere; interpreted here by
#: `validate_structure`, which implements exactly the keywords used below.
SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://archiosk.com/schema/go-pdz-1.0-onepage.schema.json",
    "title": CONTRACT_ID,
    "type": "object",
    "required": ["contract", "schema_version", "gate", "next_authorized_gate",
                 "subject", "authorities", "statements", "result_status"],
    "additionalProperties": False,
    "properties": {
        "contract": {"const": CONTRACT_ID},
        "schema_version": {"const": SCHEMA_VERSION},
        "gate": {"const": GATE_01},
        "next_authorized_gate": {"const": GATE_02},
        "subject": {
            "type": "object",
            "required": ["subject_id", "address_as_given", "identity_confidence"],
            "additionalProperties": False,
            "properties": {
                "subject_id": {"type": "string", "minLength": 1},
                "address_as_given": {"type": "string", "minLength": 1},
                "normalized_address": {"type": ["string", "null"]},
                "parcel_identifier": {"type": ["string", "null"]},
                "municipality": {"type": ["string", "null"]},
                "identity_confidence": {"enum": list(CONFIDENCES) + ["UNRESOLVED"]},
            },
        },
        "authorities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["authority_id", "name", "authority_status"],
                "additionalProperties": False,
                "properties": {
                    "authority_id": {"type": "string", "minLength": 1},
                    "name": {"type": "string", "minLength": 1},
                    "instrument": {"type": ["string", "null"]},
                    "citation": {"type": ["string", "null"]},
                    "effective_date": {"type": ["string", "null"]},
                    "authority_status": {"enum": list(AUTHORITY_STATUSES)},
                    "retrieved_at": {"type": ["string", "null"]},
                    "url": {"type": ["string", "null"]},
                },
            },
        },
        "statements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["statement_id", "kind", "topic", "text",
                             "statement_status", "confidence"],
                "additionalProperties": False,
                "properties": {
                    "statement_id": {"type": "string", "minLength": 1},
                    "kind": {"enum": list(STATEMENT_KINDS)},
                    "topic": {"type": "string", "minLength": 1},
                    "text": {"type": "string", "minLength": 1},
                    "authority_refs": {"type": "array",
                                       "items": {"type": "string"}},
                    "statement_status": {"enum": list(STATEMENT_STATUSES)},
                    "confidence": {"enum": list(CONFIDENCES)},
                    "spatial_relation": {"enum": list(SPATIAL_RELATIONS)},
                    "spatial_basis": {"enum": list(SPATIAL_BASES)},
                    "conflict_refs": {"type": "array",
                                      "items": {"type": "string"}},
                    "derived_from": {"type": "array",
                                     "items": {"type": "string"}},
                },
            },
        },
        "site_specific_exceptions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["exception_id", "indicated_by", "text_retrieved"],
                "additionalProperties": False,
                "properties": {
                    "exception_id": {"type": "string", "minLength": 1},
                    "indicated_by": {"type": "string", "minLength": 1},
                    "text_retrieved": {"type": "boolean"},
                    "authority_ref": {"type": ["string", "null"]},
                    "missing_authority": {"type": ["string", "null"]},
                    "development_effect": {"type": ["string", "null"]},
                    "required_next_evidence": {"type": ["string", "null"]},
                },
            },
        },
        "unresolved": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["issue_id", "question", "materiality"],
                "additionalProperties": False,
                "properties": {
                    "issue_id": {"type": "string", "minLength": 1},
                    "question": {"type": "string", "minLength": 1},
                    "materiality": {"enum": ["MATERIAL", "MINOR"]},
                    "required_evidence": {"type": ["string", "null"]},
                },
            },
        },
        "result_status": {"enum": list(RESULT_STATUSES)},
    },
}


def _type_ok(value, expected) -> bool:
    names = expected if isinstance(expected, list) else [expected]
    for name in names:
        if name == "object" and isinstance(value, dict):
            return True
        if name == "array" and isinstance(value, list):
            return True
        # bool before int: in Python True is an int, and a boolean field that
        # accepts a number would silently accept True.
        if name == "boolean" and isinstance(value, bool):
            return True
        if name == "string" and isinstance(value, str):
            return True
        if name == "null" and value is None:
            return True
    return False


def validate_structure(document, schema=None, path="$") -> list:
    """Structure only. Returns [] when the shape is right, never raises.

    Implements exactly the JSON Schema keywords `SCHEMA` uses - const, enum,
    type, required, additionalProperties, minLength, items - and nothing else.
    A keyword that is not implemented is not silently ignored: it is not used.
    """
    schema = SCHEMA if schema is None else schema
    problems = []

    if "const" in schema and document != schema["const"]:
        problems.append((path, "expected %r, found %r" % (schema["const"], document)))
        return problems
    if "enum" in schema and document not in schema["enum"]:
        problems.append((path, "expected one of %s, found %r"
                         % (schema["enum"], document)))
        return problems
    if "type" in schema and not _type_ok(document, schema["type"]):
        problems.append((path, "expected type %s, found %s"
                         % (schema["type"], type(document).__name__)))
        return problems
    if "minLength" in schema and isinstance(document, str):
        if len(document) < schema["minLength"]:
            problems.append((path, "must be at least %d character(s)"
                             % schema["minLength"]))

    if isinstance(document, dict):
        for field in schema.get("required", []):
            if field not in document:
                problems.append(("%s.%s" % (path, field), "required field is missing"))
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for field in document:
                if field not in properties:
                    problems.append(("%s.%s" % (path, field),
                                     "field is not permitted by the contract"))
        for field, subschema in properties.items():
            if field in document:
                problems.extend(validate_structure(
                    document[field], subschema, "%s.%s" % (path, field)))

    if isinstance(document, list) and "items" in schema:
        for index, item in enumerate(document):
            problems.extend(validate_structure(
                item, schema["items"], "%s[%d]" % (path, index)))

    return problems
