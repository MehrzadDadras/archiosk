"""Project Perspective and retained-by relationship (CLAUDE-PERSPECTIVE-GATE-04).

The project's declared **working position** in the procurement chain, and the
**upstream edge** that distinguishes otherwise-identical positions.

Deliberately a separate module from `environment_capabilities.py`, not an
extension of it. `governance/specified-unbuilt/perspective-and-contract-dna.md`
is explicit that Perspective and operating environment / Contract-Delivery DNA
are distinct but interacting concepts, and that neither derives the other:
operating environment gates which *capabilities and tools* exist, Perspective
describes *where this project is working from*. Folding one into the other is
precisely the conflation the specification warns against, and would make the
five-position gate express positions as capability variants, which they are not.

**Perspective is context, not authority.** Selecting one changes which questions
are relevant and which evidence deserves attention. It never establishes
contractual authority, payment entitlement, liability, document precedence,
responsibility allocation, or which contract form governs -- those require
project evidence, always. Nothing here may be read as a conclusion about the
project.

**Profession does not determine perspective.** The same architect is a Lead
Design Consultant on one project and a Design-Builder's subconsultant on the
next; the same firm is a Prime on one and a Trade Bidder on another. Authoritative
evidence for this is recorded in `governance/reference-acquisition/REGISTER.md`:
a consultant is engaged under one standard form when an Owner retains them and a
different one when a Design-Builder does, and under one construction-management
arrangement the Owner holds the trade contracts while under another the
Construction Manager does. That is why the upstream edge is a first-class,
explicitly-declared attribute rather than an inference.

**Never inferred.** Position is declared by the person creating the project. It
is never derived from a document, a detected contract form, an email domain, a
user identity, or a profession.

This module is data and validation only -- no reasoning, no cognition, no
per-position code branches. Adding a position is a data change here, never a new
intelligence stack.
"""
from __future__ import annotations

from typing import Optional

# --- Perspective ---------------------------------------------------------
# A subset of the open, extensible list the governing specification already
# names (Owner, Proponent, Private Partner, Contractor, Consultant,
# Operator/Maintainer, Neutral/Arbiter, Legal/Commercial Advisor). Only the
# three the five entry choices actually need are carried here; the list is
# open by design, and extending it is a data addition.
PERSPECTIVE_OWNER = "owner"
PERSPECTIVE_CONSULTANT = "consultant"
PERSPECTIVE_CONTRACTOR = "contractor"

KNOWN_PERSPECTIVES = (
    PERSPECTIVE_OWNER,
    PERSPECTIVE_CONSULTANT,
    PERSPECTIVE_CONTRACTOR,
)

# --- Retained-by (the upstream edge) -------------------------------------
# Who retained this project's party. RETAINED_BY_NOT_ESTABLISHED is a real,
# honest state, never a placeholder to be quietly filled in later by
# inference: a bidder frequently does not yet know the full chain above them,
# and recording that truthfully is better than guessing it.
RETAINED_BY_OWNER = "owner"
RETAINED_BY_LEAD_CONSULTANT = "lead_consultant"
RETAINED_BY_DESIGN_BUILDER = "design_builder"
RETAINED_BY_PRIME_CONTRACTOR = "prime_contractor"
RETAINED_BY_NOT_ESTABLISHED = "not_established"

KNOWN_RETAINED_BY = (
    RETAINED_BY_OWNER,
    RETAINED_BY_LEAD_CONSULTANT,
    RETAINED_BY_DESIGN_BUILDER,
    RETAINED_BY_PRIME_CONTRACTOR,
    RETAINED_BY_NOT_ESTABLISHED,
)

RETAINED_BY_LABELS = {
    RETAINED_BY_OWNER: "The Owner",
    RETAINED_BY_LEAD_CONSULTANT: "The Owner's lead design consultant",
    RETAINED_BY_DESIGN_BUILDER: "The design-builder or general contractor",
    RETAINED_BY_PRIME_CONTRACTOR: "The prime contractor or construction manager",
    RETAINED_BY_NOT_ESTABLISHED: "Not established yet",
}

# --- The five visible entry choices --------------------------------------
# Ordinary procurement language only. No contract-form names, no CCDC/RAIC/CCA
# terminology, and none of this module's own vocabulary ("perspective",
# "retained-by", "Contract DNA", "ReferenceStandard") reaches the user: the
# system carries the sophistication so the user does not have to.
ENTRY_CLIENT_OWNER = "client_owner"
ENTRY_LEAD_DESIGN_CONSULTANT = "lead_design_consultant"
ENTRY_SUBCONSULTANT = "subconsultant"
ENTRY_PRIME_CONTRACTOR = "prime_contractor"
ENTRY_TRADE_BIDDER = "trade_bidder"

ENTRY_CHOICES = (
    ENTRY_CLIENT_OWNER,
    ENTRY_LEAD_DESIGN_CONSULTANT,
    ENTRY_SUBCONSULTANT,
    ENTRY_PRIME_CONTRACTOR,
    ENTRY_TRADE_BIDDER,
)

ENTRY_CHOICE_LABELS = {
    ENTRY_CLIENT_OWNER: "Client / Owner",
    ENTRY_LEAD_DESIGN_CONSULTANT: "Lead Design Consultant",
    ENTRY_SUBCONSULTANT: "Subconsultant / Specialist Consultant",
    ENTRY_PRIME_CONTRACTOR: "Prime / Design-Builder / GC",
    ENTRY_TRADE_BIDDER: "Subcontractor / Trade Bidder",
}

ENTRY_CHOICE_SUBTITLES = {
    ENTRY_CLIENT_OWNER:
        "Procure design and/or construction services.",
    ENTRY_LEAD_DESIGN_CONSULTANT:
        "Respond to an Owner's design-services procurement and coordinate specialist consultants.",
    ENTRY_SUBCONSULTANT:
        "Respond to a consultant-issued specialist scope.",
    ENTRY_PRIME_CONTRACTOR:
        "Respond to an Owner's construction or design-build procurement, and procure downstream scopes where applicable.",
    ENTRY_TRADE_BIDDER:
        "Respond to a contractor-issued trade package and prepare bid or delivery work.",
}

# Which Perspective each visible choice establishes. Several choices share a
# Perspective on purpose -- Lead Consultant and Subconsultant are both the
# consultant position, and Prime and Trade Bidder are both the contractor
# position. What separates them is the upstream edge below, not a new
# vocabulary value, and not a separate reasoning stack.
ENTRY_CHOICE_PERSPECTIVE = {
    ENTRY_CLIENT_OWNER: PERSPECTIVE_OWNER,
    ENTRY_LEAD_DESIGN_CONSULTANT: PERSPECTIVE_CONSULTANT,
    ENTRY_SUBCONSULTANT: PERSPECTIVE_CONSULTANT,
    ENTRY_PRIME_CONTRACTOR: PERSPECTIVE_CONTRACTOR,
    ENTRY_TRADE_BIDDER: PERSPECTIVE_CONTRACTOR,
}

# Which upstream relationships are offerable for each choice. The Owner is the
# apex of the chain and is retained by no one, so it offers none. Every other
# choice may always answer "not established yet" -- the tuples below are what
# the user may pick from, never what the system assumes.
ENTRY_CHOICE_RETAINED_BY_OPTIONS = {
    ENTRY_CLIENT_OWNER: (),
    # CLAUDE-ENTRY-REDUNDANCY-01: the two consultant positions deliberately
    # do NOT offer "not established". They are the only positions whose
    # capability side cannot be read from the position alone - the same
    # profession sits on the Owner's side when the Owner retains them and on
    # the delivery side when a design-builder does - so this question is what
    # resolves it. Every option here resolves to a side; asking it is how the
    # redundant second question was removed without guessing.
    ENTRY_LEAD_DESIGN_CONSULTANT: (
        RETAINED_BY_OWNER, RETAINED_BY_DESIGN_BUILDER,
    ),
    ENTRY_SUBCONSULTANT: (
        RETAINED_BY_LEAD_CONSULTANT, RETAINED_BY_DESIGN_BUILDER,
    ),
    ENTRY_PRIME_CONTRACTOR: (
        RETAINED_BY_OWNER, RETAINED_BY_NOT_ESTABLISHED,
    ),
    ENTRY_TRADE_BIDDER: (
        RETAINED_BY_PRIME_CONTRACTOR, RETAINED_BY_OWNER, RETAINED_BY_NOT_ESTABLISHED,
    ),
}


def is_valid_perspective(value: Optional[str]) -> bool:
    return value in KNOWN_PERSPECTIVES


def is_valid_entry_choice(value: Optional[str]) -> bool:
    return value in ENTRY_CHOICES


def perspective_for_entry_choice(entry_choice: Optional[str]) -> Optional[str]:
    """The Perspective a visible entry choice establishes, or None if unrecognized."""
    return ENTRY_CHOICE_PERSPECTIVE.get(entry_choice)


def retained_by_options(entry_choice: Optional[str]) -> tuple[str, ...]:
    """Offerable upstream relationships for a choice; empty for the Owner."""
    return ENTRY_CHOICE_RETAINED_BY_OPTIONS.get(entry_choice, ())


def is_valid_retained_by(entry_choice: Optional[str], value: Optional[str]) -> bool:
    """Validate an upstream relationship AGAINST ITS OWN CHOICE.

    Gating per choice rather than against the flat vocabulary is what stops a
    Trade Bidder project declaring it was retained by a lead design consultant,
    or an Owner project declaring it was retained at all. None is always valid:
    an unanswered relationship is a legitimate state, distinct from
    RETAINED_BY_NOT_ESTABLISHED, which is a deliberate declaration that it is
    not yet known.
    """
    if value is None:
        return True
    return value in retained_by_options(entry_choice)


def entry_choice_view() -> list[dict]:
    """The five choices, ordered, shaped for a template.

    Ordered upstream-to-downstream so the procurement chain reads in its
    natural direction rather than alphabetically.
    """
    return [
        {
            "value": choice,
            "label": ENTRY_CHOICE_LABELS[choice],
            "subtitle": ENTRY_CHOICE_SUBTITLES[choice],
            "retained_by_options": [
                {"value": option, "label": RETAINED_BY_LABELS[option]}
                for option in retained_by_options(choice)
            ],
        }
        for choice in ENTRY_CHOICES
    ]


# --- Deriving the operating environment ------------------------------------
# CLAUDE-ENTRY-REDUNDANCY-01. Live review found the creation form asking two
# adjacent questions - "Project Operating Environment" and "Your position" -
# which put the same words ("Client / Owner") in two boxes meaning different
# things, and exposed an internal abstraction as a user decision.
#
# The redundant USER DECISION is removed; the internal semantic distinction is
# NOT. operating_environment remains a separate, locked, required field with
# its own governance and its own meaning ("whose side", which gates
# capabilities). It is now derived from the position the user actually
# declared instead of being asked for twice.
#
# This supplies application context only. It establishes no contractual
# authority and selects no Contract/Delivery DNA: perspective is context, not
# authority, and entry context does not select contract form.
_ENVIRONMENT_BY_ENTRY_CHOICE = {
    ENTRY_CLIENT_OWNER: "client_owner",
    ENTRY_PRIME_CONTRACTOR: "design_builder_proponent",
    ENTRY_TRADE_BIDDER: "design_builder_proponent",
}

# The consultant positions resolve through their upstream edge instead. Who
# retains a consultant is exactly what decides which side of the publication
# boundary their work sits on.
_ENVIRONMENT_BY_RETAINED_BY = {
    RETAINED_BY_OWNER: "client_owner",
    RETAINED_BY_LEAD_CONSULTANT: "client_owner",
    RETAINED_BY_DESIGN_BUILDER: "design_builder_proponent",
}


def requires_retained_by(entry_choice: Optional[str]) -> bool:
    """True where the upstream edge is what resolves the capability side.

    Only the consultant positions. Everywhere else the position alone
    determines it, so the question stays optional and "not established yet"
    remains an honest answer.
    """
    return entry_choice in (ENTRY_LEAD_DESIGN_CONSULTANT, ENTRY_SUBCONSULTANT)


def operating_environment_for(
    entry_choice: Optional[str], retained_by: Optional[str] = None,
) -> Optional[str]:
    """The operating environment a declared position implies, or None.

    None means genuinely unresolved - a consultant position with no upstream
    edge supplied. Callers must treat that as "ask", never as a default: the
    field is locked at creation and irreversible, so guessing it wrong costs
    the user their whole project.
    """
    direct = _ENVIRONMENT_BY_ENTRY_CHOICE.get(entry_choice)
    if direct is not None:
        return direct
    if requires_retained_by(entry_choice):
        return _ENVIRONMENT_BY_RETAINED_BY.get(retained_by)
    return None
