"""
B2 - requirement-level supersession linkage. The governed old -> new transition.

WHAT B2 IS

B1 decided a change arrived and a human accepted it. B2 is the act that makes
the successor govern: it creates the new Requirement, marks the predecessor
superseded, and records the Supersession that ties them together with the
authority the change rested on. It answers "what did this replace, and what is
current now?"

It is deliberately thin. `CaseWorkspaceStore.revise_requirement` already does
the whole non-destructive revision - successor created, predecessor preserved
and flipped to superseded, Supersession written in the same save() - and its own
docstring says "An Addendum amending/qualifying/superseding an earlier
requirement is exactly this call - no special Addendum workflow is built." B2
does not re-implement any of that. What B2 adds is the part that primitive
deliberately does not have an opinion about: WHO may call it, WHEN, and what
must never happen twice.

THE AUTHORITY TRANSITION IS THE POINT

A revision may begin only from a B1 assessment that is ACCEPTED by a human and
authority-moving (AMENDS or SUPERSEDES). Everything else is refused here, at the
one entry point, so there is no second path into a governed transition:
PROPOSED is refused because accepting is the human act GOV-P-006 reserves;
REVIEW is refused because ambiguity is not a quiet amendment; CLARIFIES and
NO_CHANGE are refused because noticing a document is not revising a requirement.

AMENDS AND SUPERSEDES USE THE SAME PRIMITIVE, AND THAT IS HONEST

Both produce a successor and preserve the predecessor, because in this model
there is no third thing an amendment could be: editing the requirement in place
would destroy the genealogy, which `CURRENT STATE MUST NOT LAUNDER HISTORY`
forbids outright. The difference between them is not mechanical, it is
provenance - WHY the successor exists - so the transition type is recorded in
the Supersession's own reason rather than expressed as a different code path. A
distinction invented at the mechanism level here would be a distinction without
a difference, and would read as meaning more than it does.

WHAT B2 REFUSES TO DECIDE

If the predecessor already has a successor, a second accepted change is NOT
applied. `current_requirement_for` walks the chain with `next(...)`, so a second
supersession on one predecessor would give the project two heads and the
resolver would silently pick one - which is exactly the "do not choose by
recency" failure. B2 raises `ChangeApplicationConflict` and leaves it to a
person. `pending_conflicts` lists these so they are visible rather than merely
refused.

Note the asymmetry this exposes rather than hides: `register_source_revision`
guards against revising an already-superseded Source, and `revise_requirement`
does not. The guard is enforced HERE rather than added to that primitive,
because it has other callers - the golden-corpus builders among them - and
widening a general-purpose primitive's contract is not B2's to do.

WHAT B2 DOES NOT TOUCH

Dependencies. A2 edges attached to the predecessor stay on the predecessor, and
B2 manufactures no successor edges - a requirement being revised is not evidence
that anything still depends on the new version, and asserting it would be
inventing a relationship nobody recorded. Deciding what the dependents mean is
B3-A's sweep. B2 will happily SHOW them (`transition_brief`), because a reviewer
should see what a change touches; showing is not propagating.

Drawings are likewise untouched, but the lineage B2 writes uses the shared
Supersession primitive, so B3-B can trace a drawing relationship through the
requirement genealogy later without anything here changing.
"""
from __future__ import annotations

import logging
from typing import Optional

from services import change_arrival
from services.case_workspace import (
    AUTHORITY_MOVING_CHANGE_TYPES,
    CHANGE_ARRIVAL_STATE_ACCEPTED,
    CHANGE_TYPE_AMENDS,
    CHANGE_TYPE_SUPERSEDES,
    OBJECT_KIND_REQUIREMENT,
    REQUIREMENT_STATUS_SUPERSEDED,
)

logger = logging.getLogger(__name__)


class ChangeApplicationError(Exception):
    """An accepted change could not be applied as a governed transition."""


class ChangeApplicationConflict(ChangeApplicationError):
    """The predecessor already has a successor. A human must resolve it."""


def _assessment(workspace, assessment_id: str) -> dict:
    row = next((a for a in workspace.change_arrival_assessments
                if a["id"] == assessment_id), None)
    if row is None:
        raise ChangeApplicationError("Assessment %s was not found." % assessment_id)
    return row


def is_applicable(assessment: dict) -> tuple:
    """(applicable, reason). The one gate into a governed transition."""
    if assessment.get("state") != CHANGE_ARRIVAL_STATE_ACCEPTED:
        return False, ("This change is %s. Only a human-accepted change may revise a "
                       "governed requirement." % assessment.get("state"))
    if assessment["change_type"] not in AUTHORITY_MOVING_CHANGE_TYPES:
        return False, ("A '%s' does not move authority, so it does not revise anything."
                       % assessment["change_type"])
    return True, "Accepted and authority-moving."


def existing_successor(workspace, requirement_id: str) -> Optional[dict]:
    """The Supersession already leaving this requirement, if any."""
    return next(
        (s for s in workspace.supersessions
         if s["predecessor_type"] == OBJECT_KIND_REQUIREMENT
         and s["predecessor_id"] == requirement_id),
        None,
    )


def apply_accepted_change(store, workspace, assessment_id: str, actor: str,
                          governance_log=None, **overrides) -> dict:
    """Turn ONE accepted, authority-moving B1 assessment into lineage.

    Idempotent by record, not by guesswork: an assessment already carrying an
    `applied_supersession_id` returns that governed result unchanged rather than
    minting a second successor. `overrides` are passed to `revise_requirement`
    so a caller can supply the amended text; anything not overridden carries
    forward from the predecessor, which is what keeps an amendment a revision
    rather than a retyped requirement.
    """
    assessment = _assessment(workspace, assessment_id)

    # Idempotency FIRST, before any gate - re-applying an already-applied
    # change must be a no-op that returns the truth, not a second refusal.
    if assessment.get("applied_supersession_id"):
        return {
            "applied": False,
            "already_applied": True,
            "assessment_id": assessment_id,
            "supersession_id": assessment["applied_supersession_id"],
            "successor_id": assessment["applied_successor_id"],
            "reason": "This change was already applied; its existing transition is returned.",
        }

    applicable, reason = is_applicable(assessment)
    if not applicable:
        raise ChangeApplicationError(reason)

    predecessor_id = assessment["target_requirement_id"]
    conflict = existing_successor(workspace, predecessor_id)
    if conflict is not None:
        raise ChangeApplicationConflict(
            "Requirement %s has already been superseded by %s. Two accepted changes "
            "claiming the same predecessor would split the current-state head, and "
            "which one governs is a human decision, not a timestamp comparison."
            % (predecessor_id, conflict["successor_id"]))

    successor, supersession = store.revise_requirement(
        workspace, predecessor_id, actor=actor,
        # The transition type lives here rather than in a separate code path -
        # AMENDS and SUPERSEDES differ in provenance, not in mechanism.
        reason="%s per B1 assessment %s (source %s)" % (
            assessment["change_type"], assessment_id, assessment["incoming_source_id"]),
        authority_class=assessment.get("authority_basis"),
        governance_log=governance_log,
        **overrides,
    )
    store.mark_change_arrival_applied(
        workspace, assessment_id, supersession_id=supersession["id"],
        successor_id=successor["id"], actor=actor)

    return {
        "applied": True,
        "already_applied": False,
        "assessment_id": assessment_id,
        "change_type": assessment["change_type"],
        "authority_basis": assessment.get("authority_basis"),
        "predecessor_id": predecessor_id,
        "successor_id": successor["id"],
        "supersession_id": supersession["id"],
    }


def lineage_of(store, workspace, requirement_id: str) -> dict:
    """What is current, what this replaced, what replaced this, and the chain.

    Every answer is derived at read time from the Supersession records, never
    from a stored "current" flag and never from recency - which is the whole
    reason the chain exists rather than a timestamp sort.
    """
    requirement = next((r for r in workspace.requirements if r["id"] == requirement_id), None)
    if requirement is None:
        raise ChangeApplicationError("Requirement %s was not found." % requirement_id)

    current = store.current_requirement_for(workspace, requirement_id)
    predecessor = store.requirement_predecessor(workspace, requirement_id)
    successor_link = existing_successor(workspace, requirement_id)

    chain, seen, cursor = [], {requirement_id}, requirement_id
    while True:
        link = existing_successor(workspace, cursor)
        if link is None or link["successor_id"] in seen:
            break
        cursor = link["successor_id"]
        seen.add(cursor)
        chain.append({
            "supersession_id": link["id"],
            "predecessor_id": link["predecessor_id"],
            "successor_id": link["successor_id"],
            "actor": link.get("actor"),
            "authorized_at": link.get("authorized_at"),
            "reason": link.get("reason"),
            "authority_class": link.get("authority_class"),
        })

    return {
        "requirement_id": requirement_id,
        "this": requirement,
        "is_current": requirement.get("status") != REQUIREMENT_STATUS_SUPERSEDED,
        "current": current,
        "replaced": predecessor,
        "replaced_by": successor_link["successor_id"] if successor_link else None,
        "chain": chain,
    }


def pending_conflicts(store, workspace) -> list[dict]:
    """Accepted, authority-moving changes that CANNOT be applied automatically.

    Surfaced rather than silently skipped: an accepted change that quietly does
    nothing is indistinguishable from one nobody made, and that is how a
    superseded requirement keeps governing without anyone noticing.
    """
    blocked = []
    for assessment in workspace.change_arrival_assessments:
        if assessment.get("applied_supersession_id"):
            continue
        applicable, _reason = is_applicable(assessment)
        if not applicable:
            continue
        conflict = existing_successor(workspace, assessment["target_requirement_id"])
        if conflict is not None:
            blocked.append({
                "assessment_id": assessment["id"],
                "predecessor_id": assessment["target_requirement_id"],
                "existing_successor_id": conflict["successor_id"],
                "existing_supersession_id": conflict["id"],
                "change_type": assessment["change_type"],
                "needs": "human resolution - two accepted changes claim one predecessor",
            })
    return blocked


def transition_brief(store, workspace, assessment_id: str) -> dict:
    """What this transition would do, and what it touches - for a reviewer.

    `affected` comes from B1's own A2 consumption, so there is still exactly one
    dependency lookup in this codebase. It is shown, never acted on: propagating
    to those dependents is B3-A.
    """
    assessment = _assessment(workspace, assessment_id)
    applicable, reason = is_applicable(assessment)
    conflict = existing_successor(workspace, assessment["target_requirement_id"])
    return {
        "assessment": assessment,
        "applicable": applicable and conflict is None,
        "reason": ("Requirement already superseded by %s" % conflict["successor_id"])
                  if conflict is not None else reason,
        "already_applied": bool(assessment.get("applied_supersession_id")),
        "affected": change_arrival.affected_dependents(
            store, workspace, assessment["target_requirement_id"]),
    }
