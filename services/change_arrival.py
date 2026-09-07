"""
B1 - change-arrival recognition. "What does this arriving document change?"

THE QUESTION, AND THE LINE THIS STOPS AT

When an Addendum arrives, B1 answers: which existing Requirements does it
amend, qualify, supersede, clarify, or leave alone? It records that answer as a
PROPOSAL and stops. It does not revise a Requirement, does not write
supersession, and does not touch project history - that is B2, taken by a
person on an accepted assessment. It does not sweep dependents either; naming
who would be affected is not the same as resolving them, and the sweep is B3.

AUTHORITY GOVERNS, NOT RECENCY

The single most dangerous mistake available here is treating "newer" as
"authoritative". A later filename, a fresher filesystem timestamp, an RFI
answer, or a background note can all arrive after a Requirement and change
nothing about what governs. So recognition begins with the incoming Source's
DECLARED `document_authority`, and a document that carries none recognizes
nothing at all - it does not fall back to a guess, and it does not quietly
downgrade to "probably a clarification".

`AUTHORITY_BEARING_LEVELS` is deliberately narrow. `reference`,
`informational`, `indicative` and `draft` are all real, useful authority levels
that cannot move a contractual requirement, and an RFI answer recorded against
one of them is exactly the case the tests pin.

THE MODEL PROPOSES; A PERSON DECIDES

GOV-P-006, applied literally. Every assessment is written PROPOSED. Nothing in
this module can accept one, and `record_change_arrival_assessment` has no
parameter that would let a caller pre-accept. The human act is
`review_change_arrival_assessment`, and only an ACCEPTED, authority-moving
assessment is something B2 may act on.

AMBIGUITY IS AN ANSWER

When scope cannot be established, the change type is `review` - an explicit
refusal to guess, not a weak `amends`. Nothing downstream may read REVIEW as a
low-confidence amendment, which is why it is its own value in the vocabulary
rather than a confidence score attached to `amends`.

A2 IS CONSUMED HERE, IN PRODUCTION

`affected_dependents` calls services/dependency_graph.py rather than walking
relationships itself. That is the point of A2 having been built as a query
layer: B1 is its first production consumer, and there is exactly one dependency
lookup in this codebase. The governed distinctions A2 makes are preserved and
passed through untouched - inferred edges stay labelled, contradictions stay
out of the dependency answer, and a human-rejected edge is never traversed as
an accepted dependency.
"""
from __future__ import annotations

import logging
from typing import Optional

from services import dependency_graph
from services.case_workspace import (
    AUTHORITY_MOVING_CHANGE_TYPES,
    CHANGE_ARRIVAL_STATE_ACCEPTED,
    CHANGE_ARRIVAL_STATE_PROPOSED,
    CHANGE_TYPE_AMENDS,
    CHANGE_TYPE_CLARIFIES,
    CHANGE_TYPE_NO_CHANGE,
    CHANGE_TYPE_QUALIFIES,
    CHANGE_TYPE_REVIEW,
    CHANGE_TYPE_SUPERSEDES,
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    DOCUMENT_AUTHORITY_ISSUED_FOR_PROCUREMENT,
    DOCUMENT_AUTHORITY_PROJECT_AGREEMENT,
    KNOWN_CHANGE_TYPES,
    OBJECT_KIND_REQUIREMENT,
    normalize_open_world_value,
)

logger = logging.getLogger(__name__)

#: The only declared authority levels that can move a governed requirement.
#: Everything else - reference, informational, indicative, draft - may inform a
#: reader without changing what governs.
AUTHORITY_BEARING_LEVELS = (
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    DOCUMENT_AUTHORITY_ISSUED_FOR_PROCUREMENT,
    DOCUMENT_AUTHORITY_PROJECT_AGREEMENT,
)


class ChangeArrivalError(Exception):
    """A change-arrival assessment could not be performed."""


def authority_of(source: dict) -> Optional[str]:
    """The Source's own DECLARED authority, or None. Never inferred."""
    value = (source or {}).get("document_authority")
    return value or None


def carries_change_authority(source: dict) -> bool:
    """Can this document move a governed requirement at all?

    Declared authority only. A document with no declared authority returns
    False - honest absence, not a permissive default, because defaulting open
    here would let any uploaded file amend a contract.
    """
    return authority_of(source) in AUTHORITY_BEARING_LEVELS


def recognize_arrival(store, workspace, incoming_source_id: str) -> dict:
    """Is this document capable of changing anything, and why or why not?

    Returns a decision with its reason attached rather than a bare boolean, so
    a refusal can be shown to a user as something other than silence.
    """
    source = next((s for s in workspace.sources if s["id"] == incoming_source_id), None)
    if source is None:
        raise ChangeArrivalError("Source %s was not found." % incoming_source_id)

    authority = authority_of(source)
    if authority is None:
        return {
            "recognized": False,
            "source_id": incoming_source_id,
            "authority_basis": None,
            "reason": ("This document declares no authority, so it cannot change a "
                       "governed requirement. Declare its authority first."),
        }
    if not carries_change_authority(source):
        return {
            "recognized": False,
            "source_id": incoming_source_id,
            "authority_basis": authority,
            "reason": ("Authority '%s' does not move a governed requirement. It may "
                       "inform a reader without changing what governs." % authority),
        }
    return {
        "recognized": True,
        "source_id": incoming_source_id,
        "authority_basis": authority,
        "reason": "Declared authority '%s' can carry a change." % authority,
    }


def propose_change(store, workspace, incoming_source_id: str,
                   target_requirement_id: str, change_type: str, evidence: str,
                   actor: str, confidence: Optional[float] = None,
                   uncertainty: Optional[str] = None,
                   subject_scope: Optional[str] = None,
                   governance_log=None) -> dict:
    """Record ONE proposed change, after checking the authority actually allows it.

    An authority-moving type (amends/supersedes) is REFUSED outright when the
    incoming document cannot carry change authority. That refusal is the whole
    of B1's value: it is what stops an RFI answer or a reference document from
    being recorded as an amendment merely because someone believed it was one.
    A non-moving observation (clarifies/qualifies/no_change/review) is still
    recordable, because noticing that a document discusses a requirement
    without changing it is a real and useful finding.
    """
    decision = recognize_arrival(store, workspace, incoming_source_id)
    change_type = normalize_open_world_value(change_type, KNOWN_CHANGE_TYPES)

    if change_type in AUTHORITY_MOVING_CHANGE_TYPES and not decision["recognized"]:
        raise ChangeArrivalError(
            "'%s' would move authority, and this document cannot: %s"
            % (change_type, decision["reason"]))

    return store.record_change_arrival_assessment(
        workspace,
        incoming_source_id=incoming_source_id,
        target_requirement_id=target_requirement_id,
        change_type=change_type,
        evidence=evidence,
        created_by=actor,
        authority_basis=decision["authority_basis"],
        confidence=confidence,
        uncertainty=uncertainty,
        subject_scope=subject_scope,
        governance_log=governance_log,
    )


def affected_dependents(store, workspace, target_requirement_id: str, *,
                        max_depth: int = 1, include_inferred: bool = True) -> dict:
    """B1's consumption of A2, in production.

    Names what ELSE points at the changed Requirement. Naming is all this does:
    nothing here resolves, rewrites or propagates anything, which is the B1/B3
    line. The governed distinctions A2 makes are passed through rather than
    flattened, so a caller can still tell an adjudicated dependency from a
    machine-proposed one.
    """
    result = dependency_graph.dependents_of(
        store, workspace, OBJECT_KIND_REQUIREMENT, target_requirement_id,
        max_depth=max_depth, include_inferred=include_inferred)
    related = dependency_graph.related_non_dependencies(
        store, workspace, OBJECT_KIND_REQUIREMENT, target_requirement_id)
    return {
        "requirement_id": target_requirement_id,
        "dependents": result["edges"],
        "counts": result["counts"],
        "truncated": result["truncated"],
        # Contradictions are reported ALONGSIDE, never inside, the dependency
        # answer - a reviewer deciding on an amendment needs to see them, and
        # A2's whole point is that they are not dependencies.
        "contradicting": related["contradicting"],
        "supporting": related["supporting"],
        "supersession_lineage": dependency_graph.supersession_lineage(
            store, workspace, OBJECT_KIND_REQUIREMENT, target_requirement_id),
    }


def assessment_brief(store, workspace, assessment_id: str) -> dict:
    """One assessment plus what it would touch - the reviewer's whole picture.

    Assembled at read time and stored nowhere, the same discipline every other
    derived status in this codebase follows: a snapshot of dependents taken at
    proposal time would be stale by the time a human looked at it.
    """
    assessment = next(
        (a for a in workspace.change_arrival_assessments if a["id"] == assessment_id), None)
    if assessment is None:
        raise ChangeArrivalError("Assessment %s was not found." % assessment_id)
    return {
        "assessment": assessment,
        "moves_authority": assessment["change_type"] in AUTHORITY_MOVING_CHANGE_TYPES,
        "awaiting_human": assessment.get("state") == CHANGE_ARRIVAL_STATE_PROPOSED,
        "affected": affected_dependents(store, workspace, assessment["target_requirement_id"]),
    }


def ready_for_b2(store, workspace) -> list[dict]:
    """Assessments a person has ACCEPTED that actually move authority.

    The handoff B2 will read. Deliberately excludes everything still PROPOSED -
    B2 acting on an unreviewed proposal is precisely the silent adoption
    GOV-P-006 forbids - and everything that does not move authority, because a
    clarification is not a revision waiting to happen.
    """
    return [
        a for a in workspace.change_arrival_assessments
        if a.get("state") == CHANGE_ARRIVAL_STATE_ACCEPTED
        and a["change_type"] in AUTHORITY_MOVING_CHANGE_TYPES
    ]
