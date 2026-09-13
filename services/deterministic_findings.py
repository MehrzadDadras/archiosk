"""CLAUDE-PRODUCTION-HORIZON-01 - ARCHIOSK originates what ARCHIOSK can prove.

    PRODUCTION HORIZON INVARIANT
    If a planning relationship can be established deterministically from admitted
    evidence - by arithmetic, geometry, explicit set membership, or exact
    source/status/date comparison - then ARCHIOSK originates that finding
    directly. The LLM is not required to discover deterministic truth first.

Probe 09 is the measurement that forces this. On 573 Shuter Street the FSI
relation was DETERMINISTICALLY VERIFIABLE in 5 runs out of 5, and the model
mentioned it in 2. The promotion path worked exactly as designed and still
delivered the finding 40% of the time, because promotion can only ever act on
something the model happened to say. A fact ARCHIOSK can prove should not depend
on whether a sampler surfaced it.

WHAT THIS MODULE DOES NOT DO, AND WHY THAT IS MOST OF THE DESIGN

It is not a rules engine. It originates ONE family - the FSI envelope relation -
because that is the only DERIVED family with live measurement behind it. The
other families named in the directive are already originated deterministically,
upstream, by the municipal Gate-01 runners:

    parcel / zoning containment   services/toronto_gate01.py `_property_statements`
                                  and `_zoning_statements`, with spatial tokens
                                  seated by `go_pdz_lifecycle.assemble`
    directly stated height        `_overlay_statements` over the Zoning Height
                                  Overlay (HT_HEIGHT / HT_STRING)
    directly stated setbacks      `_overlay_statements` over the Zoning Building
                                  Setback Overlay
    exception presence / absence  `_zoning_statements` (ZN_EXCPTN, both ways)

Re-originating those here would be a second definition of the same finding, which
is the proliferation this repository's operating notes exist to refuse. The gap
was never the factual layer. It was the DERIVED layer - the conclusion no single
retrieved attribute states, and which until now only the model could reach.

It also adds no new relation to `services/derivation_check.py`. The verifier is
frozen; this module is a CONSUMER of it. If the evidence supports a relation the
verifier cannot decide, the correct output is nothing.

FAIL CLOSED ON APPLICABILITY, NOT ONLY ON ARITHMETIC. Section 3's conditions are
all required together: admitted source, established applicability, inputs strong
enough, verifier VERIFIED, and no material unresolved condition bearing on THIS
claim. 2820 Danforth satisfies the arithmetic exactly and originates NOTHING,
because an unretrieved site-specific exception displaces the very figures being
summed. An exact sum over numbers that may not govern is not an established
conclusion, and an originator is the last place that distinction may be relaxed.
"""
from __future__ import annotations

import logging
from typing import Optional

from services import derivation_check
from services import go_pdz_contract as contract
from services import relation_binding

logger = logging.getLogger(__name__)

ORIGINATOR_VERSION = "deterministic-findings@1"

#: The one derived family originated here. Named so a report can say which
#: originator ran, rather than leaving a reader to infer it from a statement id.
FAMILY_FSI_ENVELOPE = "FSI_ENVELOPE"

#: Families that ARE deterministically originated, but upstream in the municipal
#: Gate-01 runner. Declared so that "what does ARCHIOSK originate?" has ONE
#: answer a reader can check, rather than two half-answers in two modules.
FAMILIES_ORIGINATED_UPSTREAM = (
    "PARCEL_IDENTITY", "ZONING_DESIGNATION", "SITE_SPECIFIC_EXCEPTION",
    "HEIGHT_OVERLAY", "BUILDING_SETBACK_OVERLAY", "OVERLAY_PRESENCE",
    "OVERLAY_ABSENCE", "OFFICIAL_PLAN_DESIGNATION",
)

#: Reserved id prefix. A deterministic finding can never collide with a model's
#: statement ids, and a reader can tell at a glance which layer wrote a line.
ID_PREFIX = "D-"

STATEMENT_FSI_ENVELOPE = ID_PREFIX + "FSI-ENVELOPE"

REASON_NO_CANDIDATE = "the evidence does not carry component and total figures"
REASON_NOT_VERIFIED = "the components do not sum past the total"
REASON_NOT_ESTABLISHED = (
    "a material unresolved condition bears on these figures, so the relation is "
    "verified but not established")


def _bylaw_reference(evidence_facts) -> list:
    """The in-force zoning by-law, if one was admitted.

    VR-07 reads this: HIGH confidence must rest on an authority that is in force.
    An empty list is returned rather than a guess when nothing qualifies - a
    citation that does not resolve is worse than no citation, and VR-19 says so.
    """
    for authority in (evidence_facts or {}).get("admitted_authorities") or []:
        if not isinstance(authority, dict):
            continue
        identifier = str(authority.get("authority_id") or "")
        if "BYLAW" in identifier.upper() and \
                authority.get("authority_status") == "IN_FORCE":
            return [identifier]
    return []


def _fsi_text(candidate, attestation) -> str:
    """Deliberately NOT in the authority's voice - VR-18 - and deliberately NOT
    an interpretation.

    "the zone permits" or "the by-law requires" would be this module legislating.
    What ARCHIOSK can stand behind is what the record CARRIES and what those
    figures do when added up, so that is all the sentence says.

    THE MISSING SENTENCE IS THE POINT. An earlier draft closed with "a mixed-use
    scheme has to allocate it between the uses" - true, useful, and NOT
    arithmetic. That is planning interpretation, it belongs to GO, and an
    originator that writes it has quietly become a second interpreter whose
    output carries an ESTABLISHED ceiling it did not earn. The text states the
    constraint and explicitly declines to say what follows from it.
    """
    computed = attestation["computed"]
    labels = {"FSI_COMMERCIAL_USE": "commercial use",
              "FSI_RESIDENTIAL_USE": "residential use",
              "FSI_OFFICE_USE": "office use",
              "FSI_EMPLOYMENT_USE": "employment use"}
    parts = ", ".join(
        "%s for %s" % (value, labels.get(label, label))
        for value, label in zip(candidate["components"], candidate["labels"]))
    return (
        "The City's zoning record carries a total floor space index of %s for "
        "this zone, alongside component figures of %s. Those components sum to "
        "%s, which exceeds the total by %s, so they cannot all be taken in full "
        "on the same site. Recomputed by ARCHIOSK from the retrieved figures "
        "(%s); the planning implication of this constraint is not stated here."
        % (computed["total"], parts, computed["sum"], computed["exceeds_by"],
           derivation_check.VERIFIER_VERSION))


def fsi_envelope(evidence_facts, *, verified_at=None) -> dict:
    """Originate the FSI envelope finding, or explain why not.

    Returns `{family, originated, statement, attestation, reason}`. Never raises
    and never mutates the evidence.
    """
    result = {"family": FAMILY_FSI_ENVELOPE, "originated": False,
              "statement": None, "attestation": None, "reason": None,
              "originator_version": ORIGINATOR_VERSION}

    candidate = relation_binding.fsi_candidate(
        (evidence_facts or {}).get("zoning"))
    if not candidate:
        result["reason"] = REASON_NO_CANDIDATE
        return result

    limits = relation_binding.material_limits(evidence_facts)
    attestation = derivation_check.check_components_exceed_total(
        components=candidate["components"], total=candidate["total"],
        labels=candidate["labels"], inputs_established=True,
        unresolved_affecting=limits)
    attestation["verified_at"] = verified_at
    attestation["binder_version"] = relation_binding.BINDER_VERSION
    attestation["originator_version"] = ORIGINATOR_VERSION
    # BOUND TO THIS STATEMENT AND THESE INPUTS, by the same identity function the
    # promotion path uses - so `relation_binding.verify_binding` and
    # `go_pdz_validator.governed_projection` re-check an originated finding on
    # exactly the same terms as a promoted one. An originator is not a privileged
    # author; it earns the class through the same attestation.
    attestation["binding"] = relation_binding.binding_identity(
        STATEMENT_FSI_ENVELOPE, candidate["relation"],
        {"components": candidate["components"], "total": candidate["total"]})
    attestation["evidence_refs"] = list(candidate["labels"]) + ["FSI_TOTAL"]
    result["attestation"] = attestation

    if attestation["result"] != derivation_check.VERIFIED:
        result["reason"] = REASON_NOT_VERIFIED
        return result
    if not attestation.get("supports_established"):
        # THE DANFORTH OUTCOME. Exact arithmetic, provisional applicability, and
        # therefore no originated finding at all - not a weaker one. A hedged
        # sentence about figures an unread exception may displace still puts
        # those figures in front of a reader as though they governed.
        result["reason"] = REASON_NOT_ESTABLISHED
        result["limits"] = limits
        return result

    result["statement"] = {
        "statement_id": STATEMENT_FSI_ENVELOPE,
        # WHO says it is still GO_INTERPRETS - no authority states this sum.
        # HOW it came to be believed is DETERMINISTIC_DERIVATION, which is the
        # axis that decides how strongly it may be stated.
        "kind": "GO_INTERPRETS",
        "topic": "DENSITY",
        "text": _fsi_text(candidate, attestation),
        "authority_refs": _bylaw_reference(evidence_facts),
        "statement_status": "ESTABLISHED",
        "confidence": "HIGH",
        "spatial_relation": "NOT_APPLICABLE",
        "spatial_basis": "NONE",
        "conflict_refs": [],
        "derived_from": [],
        "derivation": contract.DERIVATION_DETERMINISTIC,
        "derivation_check": attestation,
    }
    result["originated"] = True
    return result


def relation_identity(attestation) -> Optional[str]:
    """What makes two findings THE SAME finding.

    Section 8. Identity is the RELATION plus the canonical INPUTS - both already
    carried by every attestation this programme produces, so nothing new is
    invented to support it. Two statements asserting `components_exceed_total`
    over the same admitted figures are one finding with two authors, whatever
    words each of them chose.

    Deliberately NOT a general deduplication framework. It compares attested
    relations and nothing else; two statements without attestations are not
    comparable here and are left alone.
    """
    if not derivation_check.is_valid_attestation(attestation):
        return None
    inputs_hash = attestation.get("inputs_hash")
    relation = attestation.get("relation")
    if not inputs_hash or not relation:
        return None
    return "%s@%s" % (relation, inputs_hash)


def duplicates_of(originated, statements) -> list:
    """Statement ids among `statements` that restate an originated finding.

    Returns ids only - the caller decides what to do with them. This module does
    not reach into a document and delete another author's statement.

    THE DETERMINISTIC FINDING IS THE ONE THAT SURVIVES, because it is the one
    that appears on EVERY eligible run. A model-discovered duplicate appeared
    2 times in 5 on the same evidence; keeping it as the substantive finding
    would make the document's content depend on a sampler.
    """
    known = {relation_identity(s.get("derivation_check"))
             for s in originated or []}
    known.discard(None)
    if not known:
        return []
    duplicates = []
    for statement in statements or []:
        if not isinstance(statement, dict):
            continue
        identity = relation_identity(statement.get("derivation_check"))
        if identity and identity in known:
            duplicates.append(statement.get("statement_id"))
    return duplicates


#: Every originator, in the order their findings are emitted. One entry today;
#: the tuple exists so that adding a family is a registration rather than a
#: rewrite, and so a caller cannot originate a family this module has not
#: declared.
ORIGINATORS = (fsi_envelope,)


def originate(evidence_facts, *, verified_at=None) -> tuple:
    """Run every declared originator over the admitted facts.

    Returns `(statements, report)`. The report carries one entry per originator
    INCLUDING those that produced nothing, and why - a family that declined is a
    result, and a silent absence would be indistinguishable from a family that
    was never attempted.
    """
    statements, report = [], []
    for originator in ORIGINATORS:
        name = getattr(originator, "__name__", "unknown")
        try:
            outcome = originator(evidence_facts, verified_at=verified_at)
        except Exception as exc:  # noqa: BLE001 - never break a compile
            logger.warning("deterministic originator %s failed (%s: %s)",
                           name, type(exc).__name__, exc)
            report.append({"family": name, "originated": False,
                           "reason": "originator raised %s" % type(exc).__name__,
                           "originator_version": ORIGINATOR_VERSION})
            continue
        report.append({k: v for k, v in outcome.items() if k != "statement"})
        if outcome.get("originated") and outcome.get("statement"):
            statements.append(outcome["statement"])
    return statements, report
