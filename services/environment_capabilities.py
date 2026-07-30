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

CLAUDE-P30 extended this module with a capability grammar (below) and
two representative environment-differentiated workflows (RFI/
clarification directionality, Go/No-Go). Deliberately NOT extended this
stage: services/bhive_parser.py's AI prompts remain entirely unaware of
operating_environment. Consequence/risk/opportunity framing, question
generation, and Go/No-Go anomaly suggestion are all real candidates for
environment-aware AI analysis, but bhive_parser.py's prompts are
adversarially-tuned and have a standing multi-session caution around
touching them (see CLAUDE-P16/P22/P23/P25/P26 history); this stage's
own Part VII explicitly permits deferring this rather than forcing it
in, and the representative capabilities above (RFI direction, Go/No-Go
variants) already prove the architecture -- one shared record shape,
genuinely different environment-specific logic and vocabulary -- without
needing a prompt change to do it. A future stage adding environment-aware
AI analysis should follow this module's existing pattern (a capability
entry + a small, explicit mapping) and add deterministic prompt-contract
tests proving neutral extraction stays stable while environment-
dependent output differs, per Part VII's own instruction.
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


# ===========================================================================
# CLAUDE-P30 -- Capability grammar and centralized resolution
# ===========================================================================
#
# The two locked environments do not merely differ in which Participant
# roles are selectable (P29's one concrete capability). They differ in
# which tools exist at all, and in which direction a shared-looking tool
# actually operates. This section is the single place that answers "is
# capability X available in environment Y, and if not, why" -- routes,
# templates, and exports all call into it rather than each carrying its
# own `if operating_environment == "..."` branch.
#
# Deliberately NOT a plugin/registry framework: CAPABILITY_REGISTRY is a
# plain dict of small, readable dataclass instances, checked directly
# against a closed set of classification constants. Adding a new
# capability means adding one entry, the same shape as every other entry
# -- not writing a new resolution mechanism.

# -- Classification grammar (Part II) --------------------------------------

# Available identically, without gating, in every environment (including
# legacy/unclassified projects) -- the shared neutral foundation
# (immutable source preservation, neutral extraction, provenance,
# project isolation, audit history, ...). Registered here mainly so the
# inventory in Part I's deliverable is complete, not because this
# classification changes any actual availability check.
CAPABILITY_NEUTRAL = "neutral"

# Two related but distinct tools, one per environment, each the other's
# opposite number in a single real-world exchange (originate a question /
# receive and answer it). Never the same tool with a cosmetic label swap.
CAPABILITY_COUNTERPART = "counterpart"

# Both environments have a capability by a shared name, but the decision
# logic, evidence, authority, and vocabulary genuinely differ -- the
# underlying record shape can still be shared infrastructure (see
# GoNoGoAssessment).
CAPABILITY_PARALLEL = "parallel"

# Belongs only to the Client / Owner environment at the current product
# definition.
CAPABILITY_CLIENT_ONLY = "client_only"

# Belongs only to the Design-Builder / Proponent environment at the
# current product definition.
CAPABILITY_PROPONENT_ONLY = "proponent_only"

# Available in both environments, but bounded: it may help one side
# anticipate the other's likely position without switching environments
# or reaching into the other party's private project state. The existing
# represented_party_by/PerspectiveAssessment mechanism (CLAUDE-P12R/P17)
# is the concrete example -- see its own entry in CAPABILITY_REGISTRY.
CAPABILITY_COMPARATIVE_BOUNDED = "comparative_bounded"

# Recognized, named, and deliberately NOT implemented or exposed yet --
# unavailable in every environment regardless of variant fields, distinct
# from a capability that is simply absent from the registry entirely
# (which is just "not built" with no recorded intent either way).
CAPABILITY_FUTURE_NOT_AUTHORIZED = "future_not_authorized"

KNOWN_CAPABILITY_CLASSIFICATIONS = (
    CAPABILITY_NEUTRAL,
    CAPABILITY_COUNTERPART,
    CAPABILITY_PARALLEL,
    CAPABILITY_CLIENT_ONLY,
    CAPABILITY_PROPONENT_ONLY,
    CAPABILITY_COMPARATIVE_BOUNDED,
    CAPABILITY_FUTURE_NOT_AUTHORIZED,
)


class CapabilityDefinition:
    """
    One entry in CAPABILITY_REGISTRY. `client_variant`/`proponent_variant`
    are the two things this module actually branches on: a human-readable
    description of what the capability means in that environment, or
    None if the capability has no meaning/availability there at all.
    Availability is always derived from these two fields (see
    capability_availability) -- there is no separate boolean to drift out
    of sync with them.

    `counterpart_capability_id`, when set, names the other half of a
    COUNTERPART pair -- used only to produce a more useful denial message
    ("X isn't available here; Y is, instead"), never to grant access.
    """

    __slots__ = (
        "capability_id", "classification", "description",
        "client_variant", "proponent_variant", "counterpart_capability_id",
    )

    def __init__(
        self,
        capability_id: str,
        classification: str,
        description: str,
        client_variant: str | None,
        proponent_variant: str | None,
        counterpart_capability_id: str | None = None,
    ) -> None:
        if classification not in KNOWN_CAPABILITY_CLASSIFICATIONS:
            raise ValueError(f"{classification!r} is not a recognized capability classification.")
        self.capability_id = capability_id
        self.classification = classification
        self.description = description
        self.client_variant = client_variant
        self.proponent_variant = proponent_variant
        self.counterpart_capability_id = counterpart_capability_id


# -- Registry (Part I inventory + Part II grammar applied) -----------------
#
# Deliberately representative, not exhaustive: every route/service/export
# actually gated by this module (Part III onward) has an entry here; the
# neutral-foundation and future/not-authorized entries exist to make the
# inventory honest about what was inspected and classified, not because
# every one of them is enforced through this specific mechanism (most of
# the neutral foundation is enforced structurally, by never branching on
# environment at all -- see each entry's own note).
CAPABILITY_REGISTRY: dict[str, "CapabilityDefinition"] = {
    "source_preservation": CapabilityDefinition(
        "source_preservation", CAPABILITY_NEUTRAL,
        "Immutable source/document preservation and revision tracking",
        client_variant="Available identically; never branches on environment.",
        proponent_variant="Available identically; never branches on environment.",
    ),
    "neutral_extraction": CapabilityDefinition(
        "neutral_extraction", CAPABILITY_NEUTRAL,
        "Extract/segment/classify requirements from a source document",
        client_variant="Available identically; the extraction pipeline (services/bhive_parser.py) never receives operating_environment.",
        proponent_variant="Available identically; the extraction pipeline (services/bhive_parser.py) never receives operating_environment.",
    ),
    "case_investigation": CapabilityDefinition(
        "case_investigation", CAPABILITY_NEUTRAL,
        "Case creation, Findings, Reviewer Validation, Disposition, Apply",
        client_variant="Available identically; environment plays no role in the investigation lifecycle itself.",
        proponent_variant="Available identically; environment plays no role in the investigation lifecycle itself.",
    ),
    "governance_audit_trail": CapabilityDefinition(
        "governance_audit_trail", CAPABILITY_NEUTRAL,
        "Append-only governance/audit log for the project",
        client_variant="Available identically; GovernanceLog has no environment concept.",
        proponent_variant="Available identically; GovernanceLog has no environment concept.",
    ),
    "participant_registration": CapabilityDefinition(
        "participant_registration", CAPABILITY_PARALLEL,
        "Register a project party and select who a reviewer represents",
        client_variant="Owner / Consultant / Other participant roles selectable (see allowed_participant_roles).",
        proponent_variant="Design-Builder / Contractor / Proponent / Other participant roles selectable (see allowed_participant_roles).",
    ),
    "comparative_perspective_assessment": CapabilityDefinition(
        "comparative_perspective_assessment", CAPABILITY_COMPARATIVE_BOUNDED,
        "Reviewer-personal, non-governed comparative reading of a governed object from one Participant's position",
        client_variant="Bounded to this project's own recorded Participants and evidence; never switches operating_environment or reaches another project's state.",
        proponent_variant="Bounded to this project's own recorded Participants and evidence; never switches operating_environment or reaches another project's state.",
    ),
    "rfi_originate": CapabilityDefinition(
        "rfi_originate", CAPABILITY_COUNTERPART,
        "Draft, revise, and issue a clarification request (RFI) against a Finding",
        client_variant=None,
        proponent_variant="Draft a question, link supporting evidence, review, and issue it to the Client/Owner.",
        counterpart_capability_id="rfi_respond",
    ),
    "rfi_respond": CapabilityDefinition(
        "rfi_respond", CAPABILITY_COUNTERPART,
        "Receive and issue an authoritative response to an already-issued RFI",
        client_variant="Review an issued RFI and record the authoritative response.",
        proponent_variant=None,
        counterpart_capability_id="rfi_originate",
    ),
    "go_no_go": CapabilityDefinition(
        "go_no_go", CAPABILITY_PARALLEL,
        "Record a Go/No-Go decision at a defined project stage",
        client_variant="Procurement Go/No-Go (initiate, release RFQ/RFP, shortlist, award, ...) -- see CLIENT_OWNER_DECISION_STAGES.",
        proponent_variant="Pursuit Go/No-Go (pursue, bid, accept terms, submit final proposal, ...) -- see DESIGN_BUILDER_PROPONENT_DECISION_STAGES.",
    ),
    "security_policy_architecture": CapabilityDefinition(
        "security_policy_architecture", CAPABILITY_FUTURE_NOT_AUTHORIZED,
        "Organizational security-team workspace, policy ingestion, and enforceable controls",
        client_variant=None,
        proponent_variant=None,
    ),
    "multi_tenant_project_authorization": CapabilityDefinition(
        "multi_tenant_project_authorization", CAPABILITY_FUTURE_NOT_AUTHORIZED,
        "Multi-organization tenancy (see governance/specified-unbuilt/tenancy-and-project-authorization.md)",
        client_variant=None,
        proponent_variant=None,
    ),
}


def capability_availability(capability_id: str, operating_environment: str | None) -> bool:
    """
    True if `capability_id` is usable in `operating_environment`.

    A legacy/unclassified project (`operating_environment is None`) is
    ungated for every capability except CAPABILITY_FUTURE_NOT_AUTHORIZED
    -- the same "None means no gating" precedent already established by
    allowed_participant_roles, applied consistently here rather than
    invented separately per capability.
    """
    definition = CAPABILITY_REGISTRY[capability_id]
    if definition.classification == CAPABILITY_FUTURE_NOT_AUTHORIZED:
        return False
    if operating_environment is None:
        return True
    if operating_environment == CLIENT_OWNER:
        return definition.client_variant is not None
    if operating_environment == DESIGN_BUILDER_PROPONENT:
        return definition.proponent_variant is not None
    return False


def capability_variant_label(capability_id: str, operating_environment: str | None) -> str | None:
    """The environment-specific description of this capability, or None
    if unavailable (matches capability_availability exactly)."""
    definition = CAPABILITY_REGISTRY[capability_id]
    if operating_environment == CLIENT_OWNER:
        return definition.client_variant
    if operating_environment == DESIGN_BUILDER_PROPONENT:
        return definition.proponent_variant
    return definition.description if operating_environment is None else None


def capability_denial_reason(capability_id: str, operating_environment: str | None) -> str | None:
    """
    None if the capability is available; otherwise a single stable,
    non-implementation-leaking sentence explaining why, reused by every
    route/template that needs to explain a denial rather than each
    writing its own ad hoc message (Part IX).
    """
    if capability_availability(capability_id, operating_environment):
        return None

    definition = CAPABILITY_REGISTRY[capability_id]
    if definition.classification == CAPABILITY_FUTURE_NOT_AUTHORIZED:
        return f"{definition.description} is not yet authorized for use."

    env_label = OPERATING_ENVIRONMENT_LABELS.get(operating_environment, "this project's")
    counterpart = (
        CAPABILITY_REGISTRY.get(definition.counterpart_capability_id)
        if definition.counterpart_capability_id else None
    )
    if counterpart is not None:
        return (
            f"{definition.description} is not available in a {env_label} project. "
            f"The counterpart capability here is: {counterpart.description}."
        )
    return f"{definition.description} is not available in a {env_label} project."


# -- Go/No-Go decision-stage vocabularies (Part V) --------------------------
#
# Representative, not exhaustive -- each list proves the point (one
# shared decision-record shape, two genuinely different stage
# vocabularies) without attempting to be a complete enterprise decision
# framework. Extending either list is a deliberate product decision, not
# free text (same closed-set reasoning as OPERATING_ENVIRONMENTS itself).

CLIENT_OWNER_DECISION_STAGES = (
    "initiate_project",
    "proceed_with_procurement",
    "release_rfq",
    "release_rfp",
    "shortlist",
    "negotiate",
    "award",
    "proceed_to_next_stage",
    "pause_restructure_or_cancel",
)

DESIGN_BUILDER_PROPONENT_DECISION_STAGES = (
    "pursue",
    "submit_rfq_response",
    "continue_after_shortlisting",
    "bid_rfp",
    "accept_commercial_terms",
    "continue_after_addenda",
    "submit_final_proposal",
    "proceed_with_delivery_strategy",
)

_GO_NO_GO_DECISION_STAGES_BY_ENVIRONMENT = {
    CLIENT_OWNER: CLIENT_OWNER_DECISION_STAGES,
    DESIGN_BUILDER_PROPONENT: DESIGN_BUILDER_PROPONENT_DECISION_STAGES,
}


def decision_stages_for_environment(operating_environment: str) -> tuple[str, ...]:
    """
    Raises ValueError for None/unrecognized -- unlike
    allowed_participant_roles, there is no "ungated" fallback here: a
    Go/No-Go decision is only meaningful once it's known which side's
    vocabulary applies (see CaseWorkspaceStore.record_go_no_go_decision,
    which requires operating_environment to already be locked).
    """
    stages = _GO_NO_GO_DECISION_STAGES_BY_ENVIRONMENT.get(operating_environment)
    if stages is None:
        raise ValueError(f"{operating_environment!r} has no Go/No-Go decision-stage vocabulary.")
    return stages
