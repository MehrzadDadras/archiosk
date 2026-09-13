"""CLAUDE-ANTI-LAUNDERING-01, INVARIANT C - authority improves posture, derivation does not.

    AS_OF_RIGHT -> APPROVED_RELIEF -> RELIEF_DEPENDENT -> SPECULATIVE_TEST -> UNSUPPORTED
    (most authoritative)                                          (most conservative)

A derived object may sit where its parent sits, or further down. It may never sit
further UP than the thing it was derived from.

WHY A SECOND LADDER, WHEN `CLAIM_CEILINGS` ALREADY EXISTS. `CLAIM_CEILINGS`
governs how strongly ONE STATEMENT may be stated given how it came to be
believed. This governs what a DERIVED WORK PRODUCT may claim about its regulatory
standing given what it was derived from. They are the same principle - a ceiling
that a derivation cannot exceed - applied to different objects, and this module
deliberately borrows `CLAIM_CEILINGS`' idiom (ordered tuple, index comparison,
maximum-never-floor) rather than inventing a new one.

THE FAILURE THIS PREVENTS IS THE MOST EXPENSIVE ONE IN THE PROGRAMME, because it
is invisible at every individual step. A zoning envelope establishes that a
massing needs a minor variance: RELIEF_DEPENDENT. A design option is generated
against that envelope. A cost estimate is produced for the option. A procurement
package is assembled from the estimate. Each step is competent and none of them
lies. But the package quotes a price for a building nobody is entitled to build,
and the qualification that would have said so was dropped at the first step that
found it inconvenient to carry. Nobody laundered anything deliberately; the
posture simply was not a field, so it could not be inherited.

    AUTHORITY MAY IMPROVE POSTURE. DERIVATION ALONE MAY NOT.

`APPROVED_RELIEF` HAS NO DERIVATIONAL PATH. It is reachable only by admitting a
governed authority or decision event - a committee decision, a municipal
approval, an authority record standing behind the relief. A cost estimate, a
structural model, a design option and a procurement artifact are all equally
incapable of producing it, however confident they are.

WHAT THIS MODULE DOES NOT DO. It implements no Structural, Cost, RFP or
Procurement consumer - section 10 of the authorizing direction is explicit that
those are not built in this tranche. It provides the inheritance rule and the
authorized-transition gate, proven on Planning fixtures, so that a consumer built
later inherits a rule that already exists instead of inventing its own.
"""
from __future__ import annotations

from typing import Optional

POSTURE_VERSION = "planning-posture@1"

POSTURE_AS_OF_RIGHT = "AS_OF_RIGHT"
POSTURE_APPROVED_RELIEF = "APPROVED_RELIEF"
POSTURE_RELIEF_DEPENDENT = "RELIEF_DEPENDENT"
POSTURE_SPECULATIVE_TEST = "SPECULATIVE_TEST"
POSTURE_UNSUPPORTED = "UNSUPPORTED"

#: Ordered MOST AUTHORITATIVE FIRST, so a larger index is more conservative.
#: Same idiom as `contract.STATUS_STRENGTH`, inverted direction because the
#: conservative end is the safe end here.
POSTURE_LADDER = (
    POSTURE_AS_OF_RIGHT,
    POSTURE_APPROVED_RELIEF,
    POSTURE_RELIEF_DEPENDENT,
    POSTURE_SPECULATIVE_TEST,
    POSTURE_UNSUPPORTED,
)

#: Reachable ONLY through an admitted governed authority event.
AUTHORITY_ONLY_POSTURES = (POSTURE_APPROVED_RELIEF,)

#: How a posture came to be held, so a reader can tell inheritance from decision.
BASIS_INHERITED = "INHERITED_FROM_PARENT"
BASIS_MORE_CONSERVATIVE = "DERIVED_MORE_CONSERVATIVE"
BASIS_AUTHORITY_EVENT = "GOVERNED_AUTHORITY_EVENT"
BASIS_NO_PARENT = "ORIGINATED_WITHOUT_PARENT"
POSTURE_BASES = (BASIS_INHERITED, BASIS_MORE_CONSERVATIVE,
                 BASIS_AUTHORITY_EVENT, BASIS_NO_PARENT)

REFUSED_NO_AUTHORITY = ("posture improvement requires a governed authority "
                        "event; derivation alone cannot authorize it")
REFUSED_UNKNOWN_POSTURE = "posture is not in the ladder"
REFUSED_NOT_AN_IMPROVEMENT = "target posture is not an improvement on the parent"
REFUSED_AUTHORITY_ONLY = ("this posture is reachable only through a governed "
                          "authority event")


def is_posture(value) -> bool:
    return value in POSTURE_LADDER


def strength_index(posture) -> Optional[int]:
    """Position on the ladder. 0 is the most authoritative."""
    if posture not in POSTURE_LADDER:
        return None
    return POSTURE_LADDER.index(posture)


def more_authoritative_than(candidate, parent) -> bool:
    """True when `candidate` claims MORE standing than `parent` - the refusal."""
    left, right = strength_index(candidate), strength_index(parent)
    if left is None or right is None:
        return False
    return left < right


def inherit(parent_posture, proposed_posture=None) -> dict:
    """The posture a derived object actually gets. Never raises.

    Returns `{posture, inherited_posture, posture_basis, refused, reason}`.

    FAIL CLOSED IN BOTH DIRECTIONS. An unrecognised parent yields UNSUPPORTED
    rather than the benefit of the doubt, and an unrecognised proposal is ignored
    rather than honoured. A derivation that proposes nothing inherits exactly
    what its parent had - the point is that the qualification travels by default,
    with no step required to remember to carry it.
    """
    if not is_posture(parent_posture):
        return {"posture": POSTURE_UNSUPPORTED,
                "inherited_posture": None,
                "posture_basis": BASIS_NO_PARENT,
                "refused": True,
                "reason": REFUSED_UNKNOWN_POSTURE}

    if proposed_posture is None or proposed_posture == parent_posture:
        return {"posture": parent_posture,
                "inherited_posture": parent_posture,
                "posture_basis": BASIS_INHERITED,
                "refused": False,
                "reason": None}

    if not is_posture(proposed_posture):
        return {"posture": parent_posture,
                "inherited_posture": parent_posture,
                "posture_basis": BASIS_INHERITED,
                "refused": True,
                "reason": REFUSED_UNKNOWN_POSTURE}

    if more_authoritative_than(proposed_posture, parent_posture):
        # THE WHOLE INVARIANT, in one branch. The proposal is discarded and the
        # parent's posture stands; the refusal is recorded rather than silent,
        # because a downstream consumer that tried to improve posture is
        # information about that consumer.
        return {"posture": parent_posture,
                "inherited_posture": parent_posture,
                "posture_basis": BASIS_INHERITED,
                "refused": True,
                "reason": REFUSED_NO_AUTHORITY}

    # More conservative than the parent: always permitted, never questioned.
    return {"posture": proposed_posture,
            "inherited_posture": parent_posture,
            "posture_basis": BASIS_MORE_CONSERVATIVE,
            "refused": False,
            "reason": None}


def is_governed_authority_event(event) -> bool:
    """Does this qualify as an authority event that may improve posture?

    DELIBERATELY STRICT, and it reuses the existing authority vocabulary rather
    than inventing a parallel one: the event must name the deciding authority,
    carry a decision, and reference an admitted authority record. A dict a
    downstream consumer assembled about its own confidence satisfies none of
    those and is not an authority event.
    """
    if not isinstance(event, dict):
        return False
    if not event.get("authority_ref"):
        return False
    if not event.get("decided_by"):
        return False
    if not event.get("decision"):
        return False
    # A decision that is still pending has decided nothing.
    return bool(event.get("decided_at"))


def authorize_transition(parent_posture, target_posture, *, authority_event) -> dict:
    """Improve posture on an admitted governed decision. Never raises.

    This is the ONLY path by which posture may become more authoritative, and it
    requires the event to be produced outside the derivation asking for it.
    """
    if not is_posture(parent_posture) or not is_posture(target_posture):
        return {"posture": parent_posture if is_posture(parent_posture)
                           else POSTURE_UNSUPPORTED,
                "inherited_posture": parent_posture if is_posture(parent_posture)
                                     else None,
                "posture_basis": BASIS_INHERITED if is_posture(parent_posture)
                                 else BASIS_NO_PARENT,
                "refused": True,
                "reason": REFUSED_UNKNOWN_POSTURE}

    if not more_authoritative_than(target_posture, parent_posture):
        # Not an improvement: this is ordinary inheritance and needs no authority.
        outcome = inherit(parent_posture, target_posture)
        outcome["reason"] = outcome["reason"] or REFUSED_NOT_AN_IMPROVEMENT
        outcome["refused"] = target_posture != outcome["posture"]
        return outcome

    if not is_governed_authority_event(authority_event):
        return {"posture": parent_posture,
                "inherited_posture": parent_posture,
                "posture_basis": BASIS_INHERITED,
                "refused": True,
                "reason": REFUSED_NO_AUTHORITY}

    return {"posture": target_posture,
            "inherited_posture": parent_posture,
            "posture_basis": BASIS_AUTHORITY_EVENT,
            "refused": False,
            "reason": None,
            "authorized_by": {
                "authority_ref": authority_event.get("authority_ref"),
                "decided_by": authority_event.get("decided_by"),
                "decision": authority_event.get("decision"),
                "decided_at": authority_event.get("decided_at"),
            }}
