"""
CLAUDE-DISCIPLINE-ALIGNMENT-01 - local consistency does not prove coordination.

THE FAILURE THIS EXISTS TO CATCH

A structural set can be internally flawless. An architectural set can be
internally flawless. They can still describe two different buildings, and every
check inside either discipline will pass while they do. The mismatch lives
between them, in assumptions neither set states because each considers them
obvious.

So assumptions are stored PER DISCIPLINE and never merged. Agreement is derived
here at read time. Merging them at write time would be the same mistake in
software that causes it on projects: the disagreement disappears into a
consensus nobody actually reached.

STALENESS IS NOT DISAGREEMENT

A structural assumption drawn on an architectural background two revisions old
is not wrong - it is out of date. Those need different coordination responses,
and reporting one as the other sends the question to the wrong person. So
`informed_by_revision` is compared against what the other discipline has since
issued, and STALE_CROSS_DISCIPLINE_INPUT is its own state.

NEITHER DISCIPLINE IS SUBORDINATE

This module never decides which discipline is right. It reports that they
differ, what each believes, what the physical consequence is, and what question
someone with professional authority now has to answer. GOV-P-006 again: a model
may constrain a governed transition, it may never authorize one - and deciding
between two professionals' judgements is authorizing one.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.case_workspace import (
    ALIGNMENT_STATE_ALIGNED,
    ALIGNMENT_STATE_ASSUMPTION_MISMATCH,
    ALIGNMENT_STATE_CONFLICT,
    ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL,
    ALIGNMENT_STATE_REVIEW_NEEDED,
    ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT,
    ALIGNMENT_STATE_UNRECONCILED,
)

logger = logging.getLogger(__name__)


class DisciplineAlignmentError(Exception):
    """An alignment question could not be answered."""


def _normalise(text: Optional[str]) -> str:
    return " ".join((text or "").split()).strip().lower()


def _stale_against(store, workspace, assumption: dict) -> Optional[dict]:
    """Was this assumption formed on information the other discipline replaced?

    Compares the recorded `informed_by_revision` against the current revision of
    the source it names. A missing revision is NOT reported as stale - unknown
    and out-of-date are different, and conflating them would manufacture
    coordination questions that have no evidence behind them.
    """
    source_id = assumption.get("informed_by_source_id")
    recorded = assumption.get("informed_by_revision")
    if not source_id or not recorded:
        return None
    source = store._find(workspace.sources, source_id)
    if source is None:
        return None
    current = source.get("revision")
    if not current or _normalise(current) == _normalise(recorded):
        return None
    return {"source_id": source_id, "informed_by_revision": recorded,
            "current_revision": current, "source_name": source.get("name")}


def reconcile(store, workspace, condition_id: str) -> dict:
    """Do the disciplines describe the same physical condition?

    Derived at read time from the stored per-discipline assumptions. Reports
    what each believes and what someone now has to decide - never which of them
    wins.
    """
    condition = store._find(workspace.drawing_conditions, condition_id)
    if condition is None:
        raise DisciplineAlignmentError(
            "Condition %s was not found." % condition_id)

    assumptions = store.discipline_assumptions_for(
        workspace, condition_id=condition_id)
    by_discipline = {}
    for assumption in assumptions:
        by_discipline.setdefault(assumption["discipline"], []).append(assumption)

    stale = [entry for entry in (
        {"assumption_id": assumption["id"],
         "discipline": assumption["discipline"],
         "detail": _stale_against(store, workspace, assumption)}
        for assumption in assumptions) if entry["detail"]]

    resolved = [assumption for assumption in assumptions
                if assumption.get("resolved_by")]

    if not assumptions:
        state, reason = (ALIGNMENT_STATE_REVIEW_NEEDED,
                         "No discipline has recorded an assumption about this "
                         "condition.")
    elif len(by_discipline) < 2:
        state, reason = (
            ALIGNMENT_STATE_UNRECONCILED,
            "Only %s has recorded an assumption. One discipline agreeing with "
            "itself is not coordination." % ", ".join(sorted(by_discipline)))
    elif resolved and len(resolved) == len(assumptions):
        state, reason = (ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL,
                         "Dispositioned by professional judgement.")
    elif stale:
        state, reason = (
            ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT,
            "%s worked from information that has since been reissued. That is "
            "an update question, not a disagreement."
            % ", ".join(sorted({entry["discipline"] for entry in stale})))
    else:
        statements = {
            discipline: {_normalise(a["assumption"]) for a in rows}
            for discipline, rows in by_discipline.items()
        }
        distinct = {frozenset(values) for values in statements.values()}
        if len(distinct) == 1:
            state, reason = (ALIGNMENT_STATE_ALIGNED,
                             "Every discipline states the same thing about "
                             "this condition.")
        else:
            unevidenced = [a for a in assumptions if not (a.get("evidence") or "").strip()]
            if unevidenced:
                state, reason = (
                    ALIGNMENT_STATE_ASSUMPTION_MISMATCH,
                    "The disciplines differ, and %d of the differing "
                    "statements rest on no cited evidence - an assumption "
                    "mismatch rather than a documented conflict."
                    % len(unevidenced))
            else:
                state, reason = (
                    ALIGNMENT_STATE_CONFLICT,
                    "Both disciplines cite evidence and they still disagree.")

    return {
        "condition_id": condition_id,
        "state": state,
        "reason": reason,
        "disciplines": sorted(by_discipline),
        "assumptions": [
            {"assumption_id": a["id"], "discipline": a["discipline"],
             "assumption": a["assumption"], "evidence": a.get("evidence"),
             "confidence": a.get("confidence"),
             "resolved_by": a.get("resolved_by"),
             "resolution_note": a.get("resolution_note")}
            for a in assumptions
        ],
        "stale_inputs": stale,
        # The output of this module is a QUESTION for a person, never a verdict.
        "coordination_question": _coordination_question(state, by_discipline,
                                                        condition),
        "professional_authority": (
            "Architectural and structural judgement remain with their "
            "respective professionals. This is a coordination question, not a "
            "determination."),
    }


def _coordination_question(state: str, by_discipline: dict,
                           condition: dict) -> Optional[str]:
    """The one sentence a human actually has to act on."""
    if state == ALIGNMENT_STATE_ALIGNED:
        return None
    subject = condition.get("proposed_meaning") or "this condition"
    if state == ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT:
        return ("Has %s been rechecked against the reissued information?"
                % subject)
    if state == ALIGNMENT_STATE_UNRECONCILED:
        return ("What does the other discipline assume about %s?" % subject)
    if state == ALIGNMENT_STATE_REVIEW_NEEDED:
        return ("What does each discipline assume about %s?" % subject)
    if state == ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL:
        return None
    return ("%s describe %s differently - which is correct, and what changes "
            "as a result?" % (" and ".join(sorted(by_discipline)), subject))


def unreconciled_interfaces(store, workspace, *,
                            source_id: Optional[str] = None) -> list:
    """Every condition whose disciplines have not actually met.

    The sweep a coordination review wants: not "are there errors" but "where
    has nobody checked". An interface with one discipline's view is listed,
    because a discipline agreeing with itself is the exact shape of the
    failure this module exists for.
    """
    conditions = store.drawing_conditions_for(workspace, source_id=source_id)
    rows = []
    for condition in conditions:
        outcome = reconcile(store, workspace, condition["id"])
        if outcome["state"] not in (ALIGNMENT_STATE_ALIGNED,
                                    ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL):
            rows.append(outcome)
    return rows
