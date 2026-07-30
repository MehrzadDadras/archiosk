"""
Project Operating Environment (CLAUDE-P29) -- the locked, project-level,
immutable classification of which side of a procurement/delivery
relationship a project's workspace is configured to serve.

Deliberately NOT modeled with case_workspace.py's usual
normalize_open_world_value/KNOWN_* pattern (which validates but always
preserves an unrecognized value verbatim, never rejecting it) -- that
pattern is correct for presentation-shaped fields where "some unknown
future value" is harmless. It is wrong here on purpose: an unrecognized
environment value has no defined application behavior, and the whole
point of locking this field is that "Other" with undefined behavior
would undermine why it's locked at all. A new environment type is a
deliberate product decision (a new entry in OPERATING_ENVIRONMENTS and
everywhere that branches on it), never a free-text value that happens
to get accepted.

This module is intentionally small: a closed enum, a strict validator,
and the one concrete capability difference implemented this stage
(which Participant.role_type values, case_workspace.py's
KNOWN_PARTICIPANT_ROLES, make sense to represent inside a project
locked to a given environment). It is not a plugin framework -- adding
a genuinely new capability axis later means adding a new small mapping
here, the same shape as this one, not a redesign.
"""
from __future__ import annotations

CLIENT_OWNER = "client_owner"
DESIGN_BUILDER_PROPONENT = "design_builder_proponent"

# Closed set, deliberately -- see module docstring. Extending this list
# is itself the "deliberate new product definition" Part XI requires;
# it is never inferred from a value that merely wasn't rejected.
OPERATING_ENVIRONMENTS = (CLIENT_OWNER, DESIGN_BUILDER_PROPONENT)

OPERATING_ENVIRONMENT_LABELS = {
    CLIENT_OWNER: "Client / Owner",
    DESIGN_BUILDER_PROPONENT: "Design-Builder / Proponent",
}


def is_valid_operating_environment(value: str | None) -> bool:
    return value in OPERATING_ENVIRONMENTS


# Which existing Participant.role_type values (case_workspace.py's
# KNOWN_PARTICIPANT_ROLES) may be registered/represented inside a
# project locked to a given environment. Gates registration, not
# analysis: services/requirement_investigation.py's already-implemented
# represented_party-aware analysis (CLAUDE-P17) already produces
# different output depending on which Participant's role_type a
# reviewer represents -- this is what actually makes "environment-
# dependent analysis differs appropriately" true, without a new AI
# prompt being written for this stage. Gating which roles are even
# offerable is what keeps that existing differentiation aligned with
# the project's locked side, rather than letting a Client project
# register a "design_builder" participant and reason from their
# position, which would defeat the point of locking the project at all.
_ALLOWED_PARTICIPANT_ROLES_BY_ENVIRONMENT = {
    CLIENT_OWNER: ("owner", "consultant", "other"),
    DESIGN_BUILDER_PROPONENT: ("design_builder", "contractor", "proponent", "other"),
}


def allowed_participant_roles(operating_environment: str | None) -> tuple[str, ...] | None:
    """
    Returns the role_type tuple allowed for this environment, or None
    if the environment is unset/legacy -- callers must treat None as
    "no gating, every KNOWN_PARTICIPANT_ROLES value allowed" (the
    pre-P29 behavior), never as "nothing allowed". This is deliberate:
    a legacy project with operating_environment=None must not have its
    existing Participant/perspective functionality silently break --
    see Part X's "prevent access to environment-specific tools" read
    narrowly, not retroactively, for unclassified projects.
    """
    return _ALLOWED_PARTICIPANT_ROLES_BY_ENVIRONMENT.get(operating_environment)
