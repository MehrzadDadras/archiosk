"""CLAUDE-DERIVED-STRENGTH-06 - the model may discover a claim; this verifies it.

    MODEL DISCOVERY          is not          DETERMINISTIC VERIFICATION

Probe 05 measured a real arithmetic constraint on 2820 Danforth: the zone's
commercial FSI allowance of 2.0 and residential allowance of 2.5 sum to 4.5,
which exceeds the total cap of 3.0, so both cannot be taken in full. The model
found it in one run out of five, and when it found it, it emitted ESTABLISHED /
HIGH - while the finding it produced in five runs out of five stayed PROVISIONAL.
The model was most assertive exactly where it was least reproducible.

THE WRONG FIX IS TO TRUST OR DISTRUST THE MODEL'S CONFIDENCE. Downgrading the FSI
constraint because Gemini noticed it inconsistently would discard a correct and
useful finding for a reason that has nothing to do with whether it is true.
Trusting it would let a rare assertive claim and a rare assertive WRONG claim
look identical to a reader.

So this module recomputes the relation from the admitted facts, outside the
model, and issues an attestation. The claim is then governed by arithmetic rather
than by how sure the model sounded.

WHAT MAKES THE ATTESTATION UNFORGEABLE BY A MODEL. It is not a flag the model can
set. It carries the verifier's own version, the operation performed, the exact
input values READ FROM THE EVIDENCE, and a hash of those inputs. A payload that
merely says `"derivation": "DETERMINISTIC_DERIVATION"` without a check that this
module produced is rejected by VR-21 - which is what stops the ceiling from being
a suggestion.

NOTHING HERE INTERPRETS. It answers one question: does the relation the statement
asserts actually hold over the supplied numbers? A relation it does not implement
is UNVERIFIED, never assumed true - the same declared-competence discipline as
`deterministic_spatial`, applied to arithmetic instead of geometry.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

VERIFIER_VERSION = "derivation-check@1"

#: Outcomes. UNVERIFIED is not a failure of the claim - it means this verifier
#: has no competence over that relation and the claim therefore stays a model
#: derivation, which is the safe class.
VERIFIED = "VERIFIED"
REFUTED = "REFUTED"
UNVERIFIED = "UNVERIFIED"

#: Relations this module can actually decide. Declared, not assumed.
RELATION_COMPONENTS_EXCEED_TOTAL = "components_exceed_total"
RELATION_VALUE_EXCEEDS_LIMIT = "value_exceeds_limit"
SUPPORTED_RELATIONS = (RELATION_COMPONENTS_EXCEED_TOTAL,
                       RELATION_VALUE_EXCEEDS_LIMIT)


def _hash(payload) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                           default=str)
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def _numbers(values):
    """Only real numbers. A string that looks numeric is NOT silently coerced -
    the evidence either carries a number or it does not."""
    out = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        out.append(float(value))
    return out


def check_components_exceed_total(*, components, total, labels=None,
                                  inputs_established=True,
                                  unresolved_affecting=()) -> dict:
    """Do the component allowances sum past the total cap?

    The Danforth relation, stated generally. `inputs_established` and
    `unresolved_affecting` are section 4-C's other two conditions: arithmetic on
    a figure that is itself provisional does not yield an established conclusion,
    however exact the sum is.
    """
    parsed = _numbers(components)
    total_value = _numbers([total])
    if parsed is None or total_value is None or not parsed:
        return {"result": UNVERIFIED, "verifier_version": VERIFIER_VERSION,
                "relation": RELATION_COMPONENTS_EXCEED_TOTAL,
                "reason": "inputs are not all numeric in the supplied evidence"}

    total_value = total_value[0]
    combined = sum(parsed)
    holds = combined > total_value
    attestation = {
        "verifier_version": VERIFIER_VERSION,
        "relation": RELATION_COMPONENTS_EXCEED_TOTAL,
        "operation": "sum(components) > total",
        "inputs": {"components": parsed, "total": total_value,
                   "labels": list(labels or [])},
        "computed": {"sum": combined, "total": total_value,
                     "exceeds_by": round(combined - total_value, 10)},
        "inputs_hash": _hash({"components": parsed, "total": total_value}),
        "result": VERIFIED if holds else REFUTED,
        "inputs_established": bool(inputs_established),
        "unresolved_affecting": list(unresolved_affecting or []),
    }
    # SECTION 4-C, AND THE HONEST PART. The arithmetic can be exact and the
    # conclusion still not established: a cap computed from a figure that an
    # unretrieved exception may displace is a correct sum about a provisional
    # number. `supports_established` is what VR-21 reads, not `result`.
    attestation["supports_established"] = bool(
        holds and inputs_established and not attestation["unresolved_affecting"])
    return attestation


def check_value_exceeds_limit(*, value, limit, label=None,
                              inputs_established=True,
                              unresolved_affecting=()) -> dict:
    parsed = _numbers([value, limit])
    if parsed is None:
        return {"result": UNVERIFIED, "verifier_version": VERIFIER_VERSION,
                "relation": RELATION_VALUE_EXCEEDS_LIMIT,
                "reason": "inputs are not all numeric in the supplied evidence"}
    observed, permitted = parsed
    holds = observed > permitted
    attestation = {
        "verifier_version": VERIFIER_VERSION,
        "relation": RELATION_VALUE_EXCEEDS_LIMIT,
        "operation": "value > limit",
        "inputs": {"value": observed, "limit": permitted, "label": label},
        "computed": {"exceeds_by": round(observed - permitted, 10)},
        "inputs_hash": _hash({"value": observed, "limit": permitted}),
        "result": VERIFIED if holds else REFUTED,
        "inputs_established": bool(inputs_established),
        "unresolved_affecting": list(unresolved_affecting or []),
    }
    attestation["supports_established"] = bool(
        holds and inputs_established and not attestation["unresolved_affecting"])
    return attestation


def is_valid_attestation(check) -> bool:
    """Does this look like something THIS module produced?

    Deliberately checks structure rather than a signature: the guarantee that
    matters is enforced upstream, where only this module is called. What this
    prevents is a payload carrying `derivation_check: {"result": "VERIFIED"}` and
    nothing else - a model asserting its own verification.
    """
    if not isinstance(check, dict):
        return False
    if check.get("verifier_version") != VERIFIER_VERSION:
        return False
    if check.get("relation") not in SUPPORTED_RELATIONS:
        return False
    for field in ("operation", "inputs", "computed", "inputs_hash", "result"):
        if field not in check:
            return False
    return check.get("result") in (VERIFIED, REFUTED, UNVERIFIED)


def verify_fsi_envelope(zoning_attributes, *, unresolved_affecting=()) -> Optional[dict]:
    """The Danforth case, read straight from the City's own zoning attributes.

    Returns None when the evidence does not carry the three figures - this
    verifier has nothing to say about a zone that does not publish component
    allowances, and saying nothing is the correct output.
    """
    attributes = zoning_attributes or {}
    total = attributes.get("FSI_TOTAL")
    components, labels = [], []
    for field in ("FSI_COMMERCIAL_USE", "FSI_RESIDENTIAL_USE",
                  "FSI_OFFICE_USE", "FSI_EMPLOYMENT_USE"):
        value = attributes.get(field)
        # The City writes -1 for "not applicable", which is not a zero allowance.
        if isinstance(value, (int, float)) and not isinstance(value, bool) \
                and value > 0:
            components.append(value)
            labels.append(field)
    if total is None or len(components) < 2:
        return None
    return check_components_exceed_total(
        components=components, total=total, labels=labels,
        inputs_established=True, unresolved_affecting=unresolved_affecting)
