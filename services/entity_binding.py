"""CLAUDE-ANTI-LAUNDERING-01, INVARIANT B - a value match is not corroboration.

    MODEL CONTRIBUTION
      -> ENTITY EXTRACTION        (deterministic; the model is never asked)
      -> ROLE ASSIGNMENT          (from host-owned facts, never from the prose)
      -> BINDING                  (value AND role must agree)
      -> ADMIT or QUARANTINE

THE GAP THIS CLOSES IS REAL AND IT IS IN OUR OWN CODE. `relation_binding`
already refuses to promote a claim whose values are not present in admitted
evidence - `REASON_VALUES_UNBOUND` - and already refuses a statement that recites
the numbers without asserting the relation. What it checks is SET MEMBERSHIP:
`needed.issubset(present)`, where `present` is every number appearing anywhere in
the text. So a contribution can pass by containing the right numbers in the wrong
places.

The case from the authorizing direction, over real Toronto zoning attributes:

    FSI_COMMERCIAL_USE   1.0    COMMERCIAL_COMPONENT
    FSI_RESIDENTIAL_USE  1.5    RESIDENTIAL_COMPONENT
    FSI_TOTAL            2.0    TOTAL_FSI_CAP
    (computed)           2.5    COMPUTED_COMPONENT_SUM
    (computed)           0.5    EXCEEDS_BY

"the permitted FSI is 2.5" must FAIL. Every value in it is host-owned, its
provenance is intact, and its arithmetic is ours - which is exactly why value
binding cannot be the test. 2.5 is the sum that BREACHES the cap, reported as the
cap. The claim is maximally wrong about the only thing that matters and minimally
distinguishable from a correct one.

    A VALUE MATCH WITHOUT ROLE FIDELITY IS NOT CORROBORATION.

WHAT THIS MODULE WILL NOT DO. It does not parse language generally, does not
build an ontology, and does not decide what a sentence means. It answers one
bounded question: for each number this text asserts, which ROLE does the text
attach it to, and is that the role the host's own facts give it? Where the text
attaches no role, there is nothing to contradict and nothing is claimed - silence
is not an assertion. Where it attaches a role we do not model, the claim is
unbound rather than wrong, and unbound fails closed.

NOTHING HERE MUTATES A HOST FACT, and nothing here is a confidence adjustment. A
failed binding QUARANTINES the contribution: the raw payload keeps it as
diagnostic evidence and the governed document does not carry it. Lowering a
claim's confidence so it can still be admitted would be the same laundering
performed in the open, so it is not available - see section 7 of the authorizing
direction and `governance/current/anti-laundering-invariants.md`.

AUTHORITY REFERENCES ARE NOT RE-IMPLEMENTED HERE. VR-19 already requires every
`authority_ref` to resolve to a declared authority, and a second checker would be
a second definition of one rule. This module reports that class only for
EXCEPTION references, which VR-19 does not cover.
"""
from __future__ import annotations

import re
from typing import Optional

BINDER_VERSION = "entity-binding@1"

# --- the failure classes, from section 7 of the authorizing direction ---------
FAILURE_UNBOUNDED_NUMERIC = "UNBOUNDED_NUMERIC_CLAIM"
FAILURE_ROLE_MISMATCH = "ROLE_MISMATCH"
FAILURE_UNBOUND_AUTHORITY = "UNBOUND_AUTHORITY_REFERENCE"
FAILURE_UNBOUND_EXCEPTION = "UNBOUND_EXCEPTION_REFERENCE"

FAILURE_CLASSES = (FAILURE_UNBOUNDED_NUMERIC, FAILURE_ROLE_MISMATCH,
                   FAILURE_UNBOUND_AUTHORITY, FAILURE_UNBOUND_EXCEPTION)

# --- the entity roles Planning currently requires, and no more ---------------
#: Section 5 is explicit that no universal ontology is authorized. These are the
#: roles the Toronto zoning record actually publishes plus the two ARCHIOSK
#: computes from it, which is the whole set the FSI envelope family needs.
ROLE_TOTAL_FSI_CAP = "TOTAL_FSI_CAP"
ROLE_COMMERCIAL_COMPONENT = "COMMERCIAL_COMPONENT"
ROLE_RESIDENTIAL_COMPONENT = "RESIDENTIAL_COMPONENT"
ROLE_OFFICE_COMPONENT = "OFFICE_COMPONENT"
ROLE_EMPLOYMENT_COMPONENT = "EMPLOYMENT_COMPONENT"
ROLE_COMPUTED_COMPONENT_SUM = "COMPUTED_COMPONENT_SUM"
ROLE_EXCEEDS_BY = "EXCEEDS_BY"
ROLE_HEIGHT_LIMIT = "HEIGHT_LIMIT"
ROLE_STOREY_LIMIT = "STOREY_LIMIT"
ROLE_LOT_COVERAGE = "LOT_COVERAGE"
ROLE_SITE_AREA = "SITE_AREA"

#: Which published attribute carries which role. The host owns this mapping; a
#: contribution never supplies it.
ATTRIBUTE_ROLES = {
    "FSI_TOTAL": ROLE_TOTAL_FSI_CAP,
    "FSI_COMMERCIAL_USE": ROLE_COMMERCIAL_COMPONENT,
    "FSI_RESIDENTIAL_USE": ROLE_RESIDENTIAL_COMPONENT,
    "FSI_OFFICE_USE": ROLE_OFFICE_COMPONENT,
    "FSI_EMPLOYMENT_USE": ROLE_EMPLOYMENT_COMPONENT,
    "HT_HEIGHT": ROLE_HEIGHT_LIMIT,
    "HT_STORIES": ROLE_STOREY_LIMIT,
    "ZN_COVERAGE": ROLE_LOT_COVERAGE,
}

#: THE PHRASES THAT ATTACH A ROLE, ordered longest-intent first so that
#: "total FSI" is not read as a bare component mention. Each pattern is anchored
#: on wording the City and this application actually use; anything else attaches
#: no role at all, which is the safe outcome rather than a guess.
#:
#: `permitted|maximum|allowable FSI` maps to TOTAL_FSI_CAP deliberately. That is
#: what those words mean in a zoning context, and it is the exact phrasing the
#: worked failure case uses - so the mapping is what makes that case detectable
#: instead of invisible.
_ROLE_PHRASES = (
    (ROLE_COMPUTED_COMPONENT_SUM, re.compile(
        r"\b(?:component\s+sum|sum\s+of\s+the\s+components?|combined\s+total|"
        r"components?\s+sum\s+to|sum\s+to|their\s+sum|summed)\b", re.I)),
    (ROLE_EXCEEDS_BY, re.compile(
        r"\b(?:exceeds?\s+(?:it\s+|the\s+total\s+|the\s+cap\s+|the\s+limit\s+)?by|"
        r"over\s+by|excess\s+of|overage\s+of)\b", re.I)),
    (ROLE_COMMERCIAL_COMPONENT, re.compile(
        r"\b(?:commercial(?:\s+(?:use|component|allowance|fsi))?)\b", re.I)),
    (ROLE_RESIDENTIAL_COMPONENT, re.compile(
        r"\b(?:residential(?:\s+(?:use|component|allowance|fsi))?)\b", re.I)),
    (ROLE_OFFICE_COMPONENT, re.compile(
        r"\b(?:office(?:\s+(?:use|component|allowance|fsi))?)\b", re.I)),
    (ROLE_EMPLOYMENT_COMPONENT, re.compile(
        r"\b(?:employment(?:\s+(?:use|component|allowance|fsi))?)\b", re.I)),
    (ROLE_TOTAL_FSI_CAP, re.compile(
        r"\b(?:total\s+fsi|fsi_total|permitted\s+fsi|maximum\s+fsi|"
        r"allowable\s+fsi|fsi\s+cap|total\s+floor\s+space\s+index|"
        r"overall\s+fsi|fsi\s+limit)\b", re.I)),
    (ROLE_HEIGHT_LIMIT, re.compile(
        r"\b(?:height\s+limit|permitted\s+height|maximum\s+height|"
        r"height\s+of)\b", re.I)),
    (ROLE_STOREY_LIMIT, re.compile(
        r"\b(?:stor(?:e?y|ies)\s+limit|permitted\s+stor(?:e?y|ies)|"
        r"maximum\s+stor(?:e?y|ies)|number\s+of\s+stor(?:e?y|ies))\b", re.I)),
    (ROLE_LOT_COVERAGE, re.compile(
        r"\b(?:lot\s+coverage|site\s+coverage|coverage\s+of)\b", re.I)),
    (ROLE_SITE_AREA, re.compile(
        r"\b(?:site\s+area|parcel\s+area|lot\s+area)\b", re.I)),
)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")

#: An exception id as this application writes it, so a contribution inventing one
#: is detectable. `toronto_gate01` emits TOR-EXCEPTION-<n>.
_EXCEPTION_REF = re.compile(r"\b[A-Z]{2,10}-EXCEPTION-[A-Za-z0-9._-]+\b")


def _number_text(value) -> set:
    """Every way one number can legitimately appear in prose.

    2.0 must match "2.0" and "2"; 0.5 must match "0.5" and ".5" is deliberately
    NOT generated - no producer in this repository writes it and inventing forms
    widens what counts as a match, which is the wrong direction for this module.
    """
    forms = set()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return forms
    forms.add(("%f" % number).rstrip("0").rstrip("."))
    forms.add("%g" % number)
    if number == int(number):
        forms.add(str(int(number)))
    forms.add(str(number))
    return {form for form in forms if form}


def host_roles(evidence_facts) -> dict:
    """ROLE -> the set of textual forms the host's own facts give that role.

    Built from admitted evidence only. The computed roles - the component sum and
    the overage - are recomputed here from the published components rather than
    read from any contribution, which is what makes them host-owned.
    """
    facts = evidence_facts or {}
    zoning = facts.get("zoning") or {}
    attributes = zoning.get("attributes") or {}

    roles = {}

    def record(role, value):
        forms = _number_text(value)
        if forms:
            roles.setdefault(role, set()).update(forms)

    components = []
    for field, role in ATTRIBUTE_ROLES.items():
        value = attributes.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        if value < 0:                      # the City's own "not stated" marker
            continue
        record(role, value)
        if role in (ROLE_COMMERCIAL_COMPONENT, ROLE_RESIDENTIAL_COMPONENT,
                    ROLE_OFFICE_COMPONENT, ROLE_EMPLOYMENT_COMPONENT) \
                and value > 0:
            components.append(float(value))

    total = attributes.get("FSI_TOTAL")
    if len(components) >= 2:
        component_sum = round(sum(components), 10)
        record(ROLE_COMPUTED_COMPONENT_SUM, component_sum)
        if isinstance(total, (int, float)) and not isinstance(total, bool) \
                and component_sum > total:
            record(ROLE_EXCEEDS_BY, round(component_sum - float(total), 10))

    area = (facts.get("parcel") or {}).get("stated_area_sq_m")
    if isinstance(area, (int, float)) and not isinstance(area, bool):
        record(ROLE_SITE_AREA, area)
    return roles


#: A number followed immediately by a connector and then a role phrase:
#: "1.5 for residential use". Anchored with no punctuation permitted between, so
#: it cannot reach past a comma into the next list item.
_TRAILING_CONNECTOR = re.compile(r"^\s+(?:for|of|in|as|to|toward|towards)\s+",
                                 re.IGNORECASE)

#: Where one clause stops describing and the next begins.
_CLAUSE_BREAK = re.compile(r"[.;:]\s|\bwhile\b|\bwhereas\b|\bbut\b", re.IGNORECASE)


def asserted_role(text, position, end=None) -> Optional[str]:
    """Which role the text attaches to the number at `position`, if any.

    TWO CONSTRUCTIONS, because real wording uses both and a rule that knows only
    one produces confident nonsense on the other:

        <role> ... <number>      "a total floor space index of 2.0"
        <number> <conn> <role>   "1.0 for commercial use, 1.5 for residential use"

    THE TRAILING CONSTRUCTION IS TRIED FIRST, and that order is the fix rather
    than a preference. A pure nearest-phrase-wins rule reads the second example
    as commercial=1.5, because "commercial use" sits two characters before 1.5
    while "residential use" sits five after it - so the closer phrase is the one
    that belongs to the PREVIOUS number. That is not a hypothetical: it is the
    exact sentence `deterministic_findings._fsi_text` emits, as a GO_INTERPRETS
    statement, and it would have quarantined ARCHIOSK's own proven finding.

    BOUNDED BY NEIGHBOURING NUMBERS AND CLAUSE BREAKS in both directions. A role
    phrase already taken by a nearer number cannot also claim this one, and one
    on the far side of a sentence boundary is describing something else.

    A number with no role phrase in its own span attaches to nothing, and that is
    NOT a failure - a figure mentioned without a meaning assigned to it makes no
    claim this module can contradict.
    """
    end = position if end is None else end

    # The trailing construction, checked before anything else.
    trailing = _TRAILING_CONNECTOR.match(text[end:])
    if trailing:
        at = end + trailing.end()
        for role, pattern in _ROLE_PHRASES:
            match = pattern.match(text, at)
            if match:
                return role
    # Clause-bounded: a role phrase on the far side of a sentence boundary or a
    # semicolon is describing something else, and reaching across one is how a
    # proximity heuristic starts inventing assertions.
    clause_start = 0
    for boundary in _CLAUSE_BREAK.finditer(text[:position]):
        clause_start = max(clause_start, boundary.end())

    # AND NUMBER-BOUNDED, which is the subtler half. A role phrase already taken
    # by a nearer number must not also claim a later one, or "the components sum
    # to 2.5, exceeding the cap of 2.0" lets `sum to` reach past 2.5 and assert
    # that 2.0 is the component sum - a ROLE_MISMATCH against a sentence that is
    # entirely correct.
    for earlier in _NUMBER.finditer(text[:position]):
        clause_start = max(clause_start, earlier.end())

    window = text[clause_start:position]

    #: The nearest PRECEDING phrase, which is what the leading construction uses.
    best_role, best_at = None, -1
    for role, pattern in _ROLE_PHRASES:
        for match in pattern.finditer(window):
            if match.start() > best_at:
                best_role, best_at = role, match.start()
    return best_role


def bind_statement(statement, evidence_facts, *, declared_exceptions=None) -> dict:
    """Every binding this statement's numbers and references produce.

    Returns `{statement_id, bindings, failures}`. Never raises and never mutates
    the statement. `failures` empty means nothing detectable is wrong; it does
    NOT mean the statement is corroborated, which is a different question that
    `relation_binding` answers.
    """
    text = (statement or {}).get("text") or ""
    statement_id = (statement or {}).get("statement_id")
    roles = host_roles(evidence_facts)
    bindings, failures = [], []

    #: Every textual form the host owns, in any role at all.
    owned = set()
    for forms in roles.values():
        owned |= forms

    for match in _NUMBER.finditer(text):
        token = match.group(0)
        role = asserted_role(text, match.start(), match.end())
        if role is None:
            # No role asserted: no claim to check. Recorded so the audit trail
            # shows the number was SEEN and deliberately not treated as a claim.
            bindings.append({"value": token, "asserted_role": None,
                             "host_role": None, "bound": None,
                             "note": "no role asserted; not a checkable claim"})
            continue
        if role not in roles:
            # THE HOST DOES NOT SOURCE THIS ROLE, so the host cannot adjudicate
            # it. "Unbound" must mean "the host does not have this value", never
            # "the host does not model this role" - the second is a fact about
            # our own coverage, and quarantining a contribution for it would
            # punish the contribution for our gap. The Toronto zoning record
            # publishes no site area, so a true statement about site area must
            # not be destroyed by a checker that cannot see one.
            bindings.append({"value": token, "asserted_role": role,
                             "host_role": None, "bound": None,
                             "note": "host holds no fact in this role; unchecked"})
            continue
        host_forms = roles.get(role) or set()
        if token in host_forms:
            bindings.append({"value": token, "asserted_role": role,
                             "host_role": role, "bound": True})
            continue
        if token in owned:
            # THE WORKED CASE. The value is genuinely ours; the role is not.
            actual = sorted(r for r, forms in roles.items() if token in forms)
            bindings.append({"value": token, "asserted_role": role,
                             "host_role": actual[0] if actual else None,
                             "bound": False})
            failures.append({
                "failure": FAILURE_ROLE_MISMATCH,
                "statement_id": statement_id,
                "value": token,
                "asserted_role": role,
                "host_role": actual[0] if actual else None,
                "detail": ("the value %s is host-owned but its role is %s, not "
                           "%s; a value match without role fidelity is not "
                           "corroboration"
                           % (token, actual[0] if actual else "unassigned", role)),
            })
            continue
        bindings.append({"value": token, "asserted_role": role,
                         "host_role": None, "bound": False})
        failures.append({
            "failure": FAILURE_UNBOUNDED_NUMERIC,
            "statement_id": statement_id,
            "value": token,
            "asserted_role": role,
            "host_role": None,
            "detail": ("the value %s is asserted as %s and does not appear in "
                       "any admitted host fact" % (token, role)),
        })

    # DECLARED BY THE DOCUMENT, not by the evidence facts. `_zoning_facts`
    # carries only whether an exception was acquired, never its id, so sourcing
    # the declared set from there would report EVERY exception reference as
    # unbound - a checker whose only behaviour is a false positive. The
    # authoritative list is the document's own `site_specific_exceptions`, which
    # `toronto_gate01._exceptions()` writes from the City's zoning record.
    declared = set(declared_exceptions or ())
    for reference in sorted(set(_EXCEPTION_REF.findall(text))):
        if not declared:
            # Nothing declared to check against: unchecked, not failed.
            bindings.append({"value": reference, "asserted_role": "EXCEPTION_ID",
                             "host_role": None, "bound": None,
                             "note": "document declares no exceptions; unchecked"})
            continue
        if reference in declared:
            bindings.append({"value": reference, "asserted_role": "EXCEPTION_ID",
                             "host_role": "EXCEPTION_ID", "bound": True})
            continue
        bindings.append({"value": reference, "asserted_role": "EXCEPTION_ID",
                         "host_role": None, "bound": False})
        failures.append({
            "failure": FAILURE_UNBOUND_EXCEPTION,
            "statement_id": statement_id,
            "value": reference,
            "asserted_role": "EXCEPTION_ID",
            "host_role": None,
            "detail": ("exception reference %s does not resolve to any "
                       "exception declared in the admitted evidence" % reference),
        })

    return {"statement_id": statement_id, "bindings": bindings,
            "failures": failures}


def declared_exceptions(document) -> set:
    """Exception ids the DOCUMENT itself declares - the authoritative list."""
    entries = (document or {}).get("site_specific_exceptions") or []
    return {str(entry.get("exception_id")) for entry in entries
            if isinstance(entry, dict) and entry.get("exception_id")}


def admit(document, evidence_facts) -> tuple:
    """Quarantine every statement whose entities do not bind. Returns a tuple.

        (admitted_document, entity_bindings, binding_failures)

    THE INPUT DOCUMENT IS NEVER MUTATED and no host fact is touched. The returned
    document is a shallow copy whose `statements` list omits the quarantined
    ones; the caller keeps the raw payload, so a quarantined contribution remains
    readable as diagnostic evidence rather than being destroyed.

    ONLY MODEL CONTRIBUTIONS ARE SUBJECT TO THIS. A statement ARCHIOSK itself
    originated - `AUTHORITY_SAYS` transcribed from a retrieved attribute, a
    `PROPERTY_FACT`, a deterministic finding - is host-owned already, and running
    a binding check against the facts it IS would be circular. The admission
    boundary is for contributions crossing INTO the canonical result.
    """
    statements = (document or {}).get("statements") or []
    declared = declared_exceptions(document)
    admitted, bindings, failures = [], [], []
    for statement in statements:
        if (statement or {}).get("kind") != "GO_INTERPRETS":
            admitted.append(statement)
            continue
        outcome = bind_statement(statement, evidence_facts,
                                 declared_exceptions=declared)
        bindings.append(outcome)
        if outcome["failures"]:
            failures.extend(outcome["failures"])
            continue                       # QUARANTINED, not weakened
        admitted.append(statement)

    result = dict(document or {})
    result["statements"] = admitted
    return result, bindings, failures


def quarantined_ids(binding_failures) -> list:
    """The statement ids that did not survive admission, in first-seen order."""
    seen, order = set(), []
    for failure in binding_failures or []:
        statement_id = failure.get("statement_id")
        if statement_id is not None and statement_id not in seen:
            seen.add(statement_id)
            order.append(statement_id)
    return order
