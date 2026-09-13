"""CLAUDE-PROMOTION-08 - discovery is not proof; proof is not discovery.

    MODEL STATEMENT
      -> CANDIDATE RELATION EXTRACTION   (deterministic, never asks the model)
      -> DETERMINISTIC VERIFIER          (services/derivation_check.py)
      -> ATTESTATION                     (bound to THIS statement and THESE inputs)
      -> DETERMINISTIC_DERIVATION        (assigned by ARCHIOSK, never claimed)
      -> GOVERNED PROJECTION

Probe 07 measured the gap this closes. On 2820 Danforth the model discovered the
FSI relation in 2 runs of 5, while ARCHIOSK verified it deterministically in 5 of
5 - and the two facts never met. The claim stayed MODEL_DERIVATION, capped at
PROVISIONAL / MEDIUM, with a proof of it sitting unused beside it. The
architecture could only ever LOWER a claim; nothing could raise one on evidence.

THE BINDING IS THE WHOLE DIFFICULTY. An attestation must promote the exact
relation it verified, not any statement that happens to contain the same numbers.
A sentence reciting "FSI 3.0, commercial 2.0, residential 2.5" while saying
something else entirely mentions every value and asserts nothing about their sum.
So a candidate must carry BOTH the values - matched against admitted evidence,
not against the prose - AND the relational assertion, and the attestation is
keyed to a binding identity computed from the statement id, the relation and the
canonical inputs.

FAIL CLOSED EVERYWHERE. Ambiguous parsing, more than one candidate, values that
do not bind exactly to admitted facts, a hash that no longer matches, an
unsupported relation, or nothing verifier-eligible at all: the statement stays
MODEL_DERIVATION and keeps its VR-21 ceiling. Promotion is the exception that
must be earned, never the default that must be prevented.

NOTHING HERE GENERATES A FINDING. If the verifier can prove a relation the model
never mentioned, that proof is NOT turned into a new statement - that is
deterministic finding generation, a different capability, and mixing it in here
would blur the line this module exists to draw. This promotes model-discovered
AND deterministically-verified claims, and nothing else.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from typing import Optional

from services import derivation_check
from services import go_pdz_contract as contract

logger = logging.getLogger(__name__)

BINDER_VERSION = "relation-binding@1"

#: Why a statement was not promoted. Returned verbatim so a reader can tell
#: "nothing to verify here" from "verified but the inputs are provisional".
REASON_NO_CANDIDATE = "no verifier-eligible relation found in the statement"
REASON_AMBIGUOUS = "more than one candidate relation matched; binding refused"
REASON_VALUES_UNBOUND = "asserted values do not bind exactly to admitted facts"
REASON_NO_RELATION_LANGUAGE = "values present but no relational assertion made"
REASON_REFUTED = "the verifier refuted the asserted relation"
REASON_INPUTS_NOT_ESTABLISHED = (
    "the relation is verified but a material unresolved dependency limits its "
    "applicability")
REASON_HASH_MISMATCH = "attestation inputs no longer match the admitted evidence"
REASON_BINDING_MISMATCH = "attestation is bound to a different statement"

#: The relational assertion a `components_exceed_total` claim must actually make.
#: Merely naming the figures is not the claim - this is what separates "2.0 and
#: 2.5 exceed 3.0" from "the standards are 2.0, 2.5 and 3.0".
_EXCEEDS_LANGUAGE = re.compile(
    r"(exceed|sum\b|combined|together|both (?:be )?maxim|cannot both|"
    r"not .{0,20}both|concurrent|simultaneous|in full)", re.IGNORECASE)

_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text) -> set:
    return {float(match) for match in _NUMBER.findall(text or "")}


def binding_identity(statement_id, relation, inputs) -> str:
    """Ties an attestation to ONE statement and ONE set of inputs."""
    canonical = json.dumps({"statement_id": statement_id, "relation": relation,
                            "inputs": inputs}, sort_keys=True,
                           separators=(",", ":"), default=str)
    return "bind:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def fsi_candidate(zoning_facts) -> Optional[dict]:
    """The one supported relation family, read from admitted zoning attributes.

    Deliberately narrow (section 5). A universal symbolic reasoner is not the
    goal and would be unverifiable itself; this decides one relation over figures
    the City publishes, and returns None for a zone that does not publish
    component allowances.
    """
    attributes = (zoning_facts or {}).get("attributes") or {}
    total = attributes.get("FSI_TOTAL")
    components, labels = [], []
    for field in ("FSI_COMMERCIAL_USE", "FSI_RESIDENTIAL_USE",
                  "FSI_OFFICE_USE", "FSI_EMPLOYMENT_USE"):
        value = attributes.get(field)
        if isinstance(value, (int, float)) and not isinstance(value, bool) \
                and value > 0:
            components.append(float(value))
            labels.append(field)
    if not isinstance(total, (int, float)) or isinstance(total, bool) \
            or len(components) < 2:
        return None
    return {"relation": derivation_check.RELATION_COMPONENTS_EXCEED_TOTAL,
            "components": components, "labels": labels, "total": float(total)}


def material_limits(evidence_facts) -> list:
    """Unresolved conditions that bear on ZONE-STANDARD arithmetic.

    Section 6, and the part that decides the real Danforth outcome. An unretrieved
    site-specific exception DISPLACES the parent standards, so a sum over those
    published figures is exact arithmetic about numbers that may not govern. The
    Official Plan designation being undetermined is also MATERIAL, but it bears on
    a different question and is deliberately NOT treated as limiting here -
    "material" must mean material TO THIS RELATION, or every finding inherits
    every doubt in the document.
    """
    limits = []
    exception = ((evidence_facts or {}).get("zoning") or {}).get(
        "site_specific_exception") or {}
    if exception and exception.get("acquired") is False:
        limits.append("site-specific exception applies and its text was not "
                      "retrieved; it displaces the parent zone standards these "
                      "figures come from")
    return limits


def candidates_for(statement, evidence_facts) -> list:
    """Every verifier-eligible relation this statement actually asserts.

    THE MODEL IS NEVER ASKED. Extraction is deterministic: the values must match
    admitted facts, and the statement must make the relational assertion.
    """
    text = statement.get("text") or ""
    found = []
    candidate = fsi_candidate((evidence_facts or {}).get("zoning"))
    if candidate:
        present = _numbers_in(text)
        needed = set(candidate["components"]) | {candidate["total"]}
        if needed.issubset(present):
            if _EXCEEDS_LANGUAGE.search(text):
                found.append(candidate)
            else:
                found.append({**candidate, "_rejected": REASON_NO_RELATION_LANGUAGE})
    return found


def bind(statement, evidence_facts, *, verified_at=None) -> dict:
    """Attempt to promote ONE statement. Never mutates it; never raises.

    Returns `{promoted, reason, attestation, derivation}`. `promoted` is True only
    when every condition in section 7 holds.
    """
    statement_id = statement.get("statement_id")
    outcome = {"statement_id": statement_id, "promoted": False,
               "attestation": None, "binder_version": BINDER_VERSION,
               "derivation": contract.DERIVATION_MODEL}

    if statement.get("kind") != "GO_INTERPRETS":
        outcome["reason"] = REASON_NO_CANDIDATE
        return outcome

    found = candidates_for(statement, evidence_facts)
    usable = [c for c in found if "_rejected" not in c]
    if not found:
        outcome["reason"] = REASON_NO_CANDIDATE
        return outcome
    if not usable:
        outcome["reason"] = found[0]["_rejected"]
        return outcome
    if len(usable) > 1:
        outcome["reason"] = REASON_AMBIGUOUS
        return outcome

    candidate = usable[0]
    limits = material_limits(evidence_facts)
    attestation = derivation_check.check_components_exceed_total(
        components=candidate["components"], total=candidate["total"],
        labels=candidate["labels"], inputs_established=True,
        unresolved_affecting=limits)

    attestation["verified_at"] = verified_at
    attestation["binder_version"] = BINDER_VERSION
    attestation["binding"] = binding_identity(
        statement_id, candidate["relation"],
        {"components": candidate["components"], "total": candidate["total"]})
    attestation["evidence_refs"] = list(candidate["labels"]) + ["FSI_TOTAL"]
    outcome["attestation"] = attestation

    if attestation["result"] != derivation_check.VERIFIED:
        outcome["reason"] = REASON_REFUTED
        return outcome
    if not attestation.get("supports_established"):
        # VERIFIED ARITHMETIC, PROVISIONAL APPLICABILITY. The sum is exact and
        # the conclusion still cannot be established - which is the correct and
        # slightly disappointing outcome for the only live case that qualifies.
        outcome["reason"] = REASON_INPUTS_NOT_ESTABLISHED
        outcome["limits"] = limits
        return outcome

    outcome["promoted"] = True
    outcome["derivation"] = contract.DERIVATION_DETERMINISTIC
    outcome["reason"] = None
    return outcome


def annotate(document, evidence_facts, *, verified_at=None) -> tuple:
    """A COPY of the document with ARCHIOSK's own classification attached.

    The original payload is never touched - section 2. What comes back is the
    document ARCHIOSK is prepared to stand behind, plus a per-statement report of
    what was attempted and why it did or did not promote.
    """
    annotated = json.loads(json.dumps(document, default=str))
    report = []
    for statement in annotated.get("statements") or []:
        if not isinstance(statement, dict):
            continue
        # Whatever the model may have emitted for these is discarded before
        # ARCHIOSK decides - the classification is not negotiable with the model.
        statement.pop("derivation", None)
        statement.pop("derivation_check", None)

        outcome = bind(statement, evidence_facts, verified_at=verified_at)
        report.append(outcome)
        if outcome["promoted"]:
            statement["derivation"] = contract.DERIVATION_DETERMINISTIC
            statement["derivation_check"] = outcome["attestation"]
    return annotated, report


def verify_binding(statement, evidence_facts) -> bool:
    """Does the attestation on this statement still hold?

    Re-derives the binding identity and the input hash from the CURRENT admitted
    facts. An attestation copied onto another statement, or kept after its inputs
    changed, fails here - which is what stops a valid attestation from becoming a
    transferable token.
    """
    check = statement.get("derivation_check")
    if not derivation_check.is_valid_attestation(check):
        return False
    candidate = fsi_candidate((evidence_facts or {}).get("zoning"))
    if not candidate:
        return False
    expected = binding_identity(
        statement.get("statement_id"), candidate["relation"],
        {"components": candidate["components"], "total": candidate["total"]})
    if check.get("binding") != expected:
        return False
    inputs = check.get("inputs") or {}
    return (sorted(inputs.get("components") or []) == sorted(candidate["components"])
            and inputs.get("total") == candidate["total"])
