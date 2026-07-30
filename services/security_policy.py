"""
CLAUDE-P31 -- Organizational Security and Information Governance:
the centralized decision engine for what ARCHIOSK itself is permitted
to do with a project's data (external AI calls, telemetry, support
packages, exports, cross-project reference, and learning-zone
movement) -- distinct from `governance/specified-unbuilt/
security-policy.md`'s "Project Security Policy", which is a
*customer's own* security requirements captured as governed
`Requirement` content inside their project (Domain 1, application-
layer-neutral). This module is the opposite direction: it governs
ARCHIOSK's own application behavior, an infrastructure/application-
layer concern (see CLAUDE.md's "current tested code on pushed main is
authoritative" precedence rule for this category), not a kernel/
domain-model concept.

Deliberately NOT a general-purpose policy language. GOVERNED_ACTIONS is
a small closed set; evaluate_action is a compact, explicit, auditable
resolver over four ordered inputs (mandatory floor -> organization
baseline -> project profile -> exception), matching this module's own
Part VII instruction to prefer that over a speculative enterprise
policy engine.

Honesty boundary (Part I / XVI): this repository has no multi-
organization/tenancy model (see `governance/specified-unbuilt/
tenancy-and-project-authorization.md` -- Organization/
OrganizationMembership/ProjectOwnership are all still just SQLAlchemy
table designs on paper, not implemented). "Organization baseline" in
this module therefore means exactly one thing today: a single,
deployment-wide security configuration (services/
security_governance.py's SecurityGovernanceStore manages one global
record, not one per tenant). Never claim organization-level isolation
this repository does not yet enforce -- see SECURITY_CLAIMS_REGISTRY
below.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# -- Information classification (Part II.3) --------------------------------
# A closed set with explicit control meaning attached via
# CLASSIFICATION_DEFAULT_RESTRICTIONS below -- never a bare label.
CLASSIFICATION_STANDARD = "standard"
CLASSIFICATION_CONFIDENTIAL = "confidential"
CLASSIFICATION_RESTRICTED = "restricted"
CLASSIFICATION_HIGHLY_RESTRICTED = "highly_restricted"

INFORMATION_CLASSIFICATIONS = (
    CLASSIFICATION_STANDARD,
    CLASSIFICATION_CONFIDENTIAL,
    CLASSIFICATION_RESTRICTED,
    CLASSIFICATION_HIGHLY_RESTRICTED,
)


def is_valid_classification(value: Optional[str]) -> bool:
    return value in INFORMATION_CLASSIFICATIONS


# -- Governed actions (Part VII) --------------------------------------------
# A closed set, deliberately small and representative rather than
# exhaustive -- each entry is either genuinely enforced somewhere in this
# codebase (see each constant's own docstring-equivalent comment below)
# or is a real, name-stable placeholder for a mechanism that does not
# exist yet (never silently implied to be enforced when it isn't).
ACTION_EXTERNAL_AI_REQUEST = "external_ai_request"
ACTION_LOCAL_AI_REQUEST = "local_ai_request"
ACTION_TECHNICAL_TELEMETRY = "technical_telemetry"
ACTION_CONTENT_BEARING_SUPPORT_PACKAGE = "content_bearing_support_package"
ACTION_EXPORT = "export"
ACTION_CROSS_PROJECT_REFERENCE = "cross_project_reference"
ACTION_ORGANIZATION_PRIVATE_LEARNING = "organization_private_learning"
ACTION_SHARED_ARCHIOSK_CONTRIBUTION = "shared_archiosk_contribution"

GOVERNED_ACTIONS = (
    ACTION_EXTERNAL_AI_REQUEST,
    ACTION_LOCAL_AI_REQUEST,
    ACTION_TECHNICAL_TELEMETRY,
    ACTION_CONTENT_BEARING_SUPPORT_PACKAGE,
    ACTION_EXPORT,
    ACTION_CROSS_PROJECT_REFERENCE,
    ACTION_ORGANIZATION_PRIVATE_LEARNING,
    ACTION_SHARED_ARCHIOSK_CONTRIBUTION,
)

# -- Decision outcomes (Part VII) -------------------------------------------
DECISION_ALLOW = "allow"
DECISION_ALLOW_APPROVED_ROUTE = "allow_approved_route"
DECISION_REQUIRE_APPROVAL = "require_approval"
DECISION_ALLOW_WITH_REDACTION = "allow_with_redaction"
DECISION_ISOLATE = "isolate"
DECISION_DENY = "deny"
DECISION_UNSUPPORTED = "unsupported"

KNOWN_DECISIONS = (
    DECISION_ALLOW,
    DECISION_ALLOW_APPROVED_ROUTE,
    DECISION_REQUIRE_APPROVAL,
    DECISION_ALLOW_WITH_REDACTION,
    DECISION_ISOLATE,
    DECISION_DENY,
    DECISION_UNSUPPORTED,
)

# A strict ordering from least to most restrictive, used to resolve
# "most-restrictive-rule-wins" (Part VI) when floor/baseline/profile
# disagree. ALLOW_APPROVED_ROUTE and ALLOW_WITH_REDACTION sit strictly
# between ALLOW and REQUIRE_APPROVAL/ISOLATE/DENY -- both are "allowed,
# but not unconditionally", stricter than a bare ALLOW.
_RESTRICTIVENESS_ORDER = (
    DECISION_ALLOW,
    DECISION_ALLOW_APPROVED_ROUTE,
    DECISION_ALLOW_WITH_REDACTION,
    DECISION_REQUIRE_APPROVAL,
    DECISION_ISOLATE,
    DECISION_DENY,
)


def _more_restrictive(a: str, b: str) -> str:
    """Returns whichever of a/b is the more restrictive decision. Both
    must be in _RESTRICTIVENESS_ORDER (never DECISION_UNSUPPORTED, which
    is a separate "not evaluable at all" signal, not a point on this
    scale)."""
    return a if _RESTRICTIVENESS_ORDER.index(a) >= _RESTRICTIVENESS_ORDER.index(b) else b


# -- Classification -> control-bundle mapping (Part II.3) -------------------
# "Do not use labels without explicit control meaning... A project
# profile must resolve to actual action policies." Each classification
# below is defined ONLY by the decisions it maps to for GOVERNED_ACTIONS
# -- never referenced anywhere in this codebase as a bare adjective.
# Actions not listed for a given classification simply defer to
# whatever the floor/baseline already decided (this table only ever
# TIGHTENS, matching the same "profile can only tighten" rule
# evaluate_action itself enforces structurally).
CLASSIFICATION_PROFILE_DECISIONS: dict[str, dict[str, str]] = {
    CLASSIFICATION_STANDARD: {},
    CLASSIFICATION_CONFIDENTIAL: {
        ACTION_EXPORT: DECISION_REQUIRE_APPROVAL,
    },
    CLASSIFICATION_RESTRICTED: {
        ACTION_EXTERNAL_AI_REQUEST: DECISION_DENY,
        ACTION_EXPORT: DECISION_REQUIRE_APPROVAL,
    },
    CLASSIFICATION_HIGHLY_RESTRICTED: {
        ACTION_EXTERNAL_AI_REQUEST: DECISION_DENY,
        ACTION_EXPORT: DECISION_DENY,
        ACTION_CONTENT_BEARING_SUPPORT_PACKAGE: DECISION_ISOLATE,
    },
}


def profile_decision_for(classification: Optional[str], action_id: str) -> Optional[str]:
    """None if this classification has no explicit opinion on this
    action -- callers pass this straight through to evaluate_action's
    own profile_decision parameter, where None correctly means 'defer
    to floor/baseline', never 'no restriction regardless of what floor/
    baseline said.'"""
    if classification is None:
        return None
    return CLASSIFICATION_PROFILE_DECISIONS.get(classification, {}).get(action_id)


# -- Mandatory ARCHIOSK security floor (Part II.1) --------------------------
#
# These are the DEFAULT decision for each governed action when nothing
# else (baseline/profile/exception) says otherwise -- the floor a
# customer configuration can only ever tighten, never loosen, because
# the floor itself is simply what happens when no override exists, and
# an override can only move a decision toward MORE restrictive (see
# evaluate_action). There is deliberately no governed action anywhere in
# GOVERNED_ACTIONS for turning off authentication, CSRF, rate limiting,
# project isolation, or audit logging -- those protections are not
# expressed as a configurable dimension in this model at all, which is
# what actually keeps them unweakenable (not a runtime check that a
# sufficiently privileged caller could still flip).
MANDATORY_FLOOR_DEFAULTS: dict[str, str] = {
    ACTION_EXTERNAL_AI_REQUEST: DECISION_ALLOW,
    ACTION_LOCAL_AI_REQUEST: DECISION_ALLOW,
    ACTION_TECHNICAL_TELEMETRY: DECISION_ALLOW,
    # Content-bearing anything defaults to requiring explicit
    # authorization -- "a missing answer must not become permission"
    # (Part V), applied as the floor default, not merely a UI suggestion.
    ACTION_CONTENT_BEARING_SUPPORT_PACKAGE: DECISION_REQUIRE_APPROVAL,
    ACTION_EXPORT: DECISION_ALLOW,
    ACTION_CROSS_PROJECT_REFERENCE: DECISION_DENY,
    ACTION_ORGANIZATION_PRIVATE_LEARNING: DECISION_REQUIRE_APPROVAL,
    ACTION_SHARED_ARCHIOSK_CONTRIBUTION: DECISION_DENY,
}

# Non-configurable narrative description of what the floor actually
# consists of in THIS repository today, cross-referenced against real
# code -- used by services/security_assurance.py's self-check and by
# the Security Department workspace, never re-derived by hand elsewhere.
# Each entry names the actual enforcing mechanism, not an aspiration.
MANDATORY_FLOOR_PROTECTIONS: dict[str, str] = {
    "authentication": "services/auth.py's login_required/admin_required session gate",
    "csrf": "Flask-WTF CSRFProtect, registered in app.py",
    "rate_limiting": "services/rate_limit.py's Flask-Limiter, decorating /login, /upload, /documents/ingest, password-reset routes",
    "project_isolation": "one flat-JSON file per project_id -- an id from Project A is structurally absent from Project B's own file (no cross-tenant isolation yet -- see honesty boundary in this module's docstring)",
    "audit_append_only": "services/governance.py's GovernanceLog -- append-only .jsonl, corrections are new events with predecessor_id, never in-place edits",
    "operating_environment_immutability": "services/case_workspace.py's set_operating_environment -- OperatingEnvironmentAlreadySetError on any second call (CLAUDE-P29)",
    "password_hashing": "werkzeug.security.generate_password_hash/check_password_hash, models.py's User",
}


# -- Resolution result -------------------------------------------------------

@dataclass
class SecurityDecision:
    action_id: str
    decision: str
    reason: str
    # Which layer actually produced the winning decision -- "floor",
    # "baseline", "profile", or "exception" -- so a denial can always be
    # explained (Part VIII's user-facing notice / Part IX's Q&A
    # provenance requirement), not just asserted.
    controlling_layer: str
    baseline_version_id: Optional[str] = None
    exception_id: Optional[str] = None


def evaluate_action(
    action_id: str,
    classification: Optional[str] = None,
    baseline_decision: Optional[str] = None,
    baseline_version_id: Optional[str] = None,
    profile_decision: Optional[str] = None,
    active_exception: Optional[dict] = None,
) -> SecurityDecision:
    """
    The single centralized resolver (Part VII) -- callers (routes,
    services/ingestion.py, services/rfi_export.py callers, etc.) pass in
    already-looked-up inputs rather than this function reaching into
    stores itself, so it stays a pure, directly-testable function with
    no I/O of its own (the same "keep the decision logic separate from
    persistence" shape services/environment_capabilities.py's
    capability_availability already established in CLAUDE-P30).

    Precedence (Part VI), most-restrictive-wins unless a valid exception
    exists:
        floor default -> baseline decision (if any, must not loosen
        floor) -> project profile decision (if any, must not loosen
        floor or baseline) -> exception (may loosen, but never past the
        floor's own DECISION_ALLOW ceiling -- an exception cannot invent
        a decision more permissive than ALLOW, since ALLOW is already
        the least restrictive point on the scale).
    """
    if action_id not in GOVERNED_ACTIONS:
        return SecurityDecision(
            action_id=action_id, decision=DECISION_UNSUPPORTED,
            reason=f"{action_id!r} is not a recognized governed action.",
            controlling_layer="none",
        )

    floor_default = MANDATORY_FLOOR_DEFAULTS[action_id]
    effective = floor_default
    controlling_layer = "floor"
    reason = f"ARCHIOSK mandatory floor default for {action_id!r}."

    if baseline_decision is not None:
        if baseline_decision not in KNOWN_DECISIONS:
            raise ValueError(f"{baseline_decision!r} is not a recognized decision.")
        tightened = _more_restrictive(effective, baseline_decision)
        # A baseline can only ever equal or tighten the floor -- if the
        # supplied baseline_decision were somehow LESS restrictive than
        # the floor, _more_restrictive already keeps the floor's own
        # value, so "loosening" is structurally impossible here, not
        # merely disallowed by convention.
        effective = tightened
        controlling_layer = "baseline"
        reason = f"Organization security baseline decision for {action_id!r}."

    if profile_decision is not None:
        if profile_decision not in KNOWN_DECISIONS:
            raise ValueError(f"{profile_decision!r} is not a recognized decision.")
        tightened = _more_restrictive(effective, profile_decision)
        effective = tightened
        controlling_layer = "profile"
        reason = f"Project security profile decision for {action_id!r}."

    if active_exception is not None:
        exception_decision = active_exception.get("decision")
        if exception_decision in KNOWN_DECISIONS:
            # An exception may loosen the effective decision (that is
            # its entire purpose) but never past DECISION_ALLOW -- there
            # is no decision less restrictive than ALLOW to loosen into,
            # so this is a structural ceiling, not a policy choice that
            # could be bypassed by a sufficiently generous exception.
            if _RESTRICTIVENESS_ORDER.index(exception_decision) < _RESTRICTIVENESS_ORDER.index(effective):
                effective = exception_decision
                controlling_layer = "exception"
                reason = active_exception.get("rationale") or f"Active exception for {action_id!r}."

    return SecurityDecision(
        action_id=action_id, decision=effective, reason=reason,
        controlling_layer=controlling_layer, baseline_version_id=baseline_version_id,
        exception_id=(active_exception or {}).get("id") if controlling_layer == "exception" else None,
    )


# -- Security claims registry (Part XVI) -------------------------------------

CLAIM_IMPLEMENTED_AND_TESTED = "implemented_and_tested"
CLAIM_IMPLEMENTED_WITH_LIMITATIONS = "implemented_with_limitations"
CLAIM_CONFIGURED_DEPENDENT_ON_PROVIDER = "configured_but_dependent_on_external_provider"
CLAIM_SPECIFIED_BUT_UNBUILT = "specified_but_unbuilt"
CLAIM_UNSUPPORTED = "unsupported"
CLAIM_PROHIBITED_FROM_CLAIMING = "prohibited_from_claiming"

# What this deployment can and cannot truthfully promise today, checked
# directly against real code, not aspiration. Add to this registry
# before adding a new claim anywhere in the product -- a claim not
# listed here should not be made in UI copy, docs, or sales material.
SECURITY_CLAIMS_REGISTRY: dict[str, str] = {
    "session-based authentication": CLAIM_IMPLEMENTED_AND_TESTED,
    "CSRF protection": CLAIM_IMPLEMENTED_AND_TESTED,
    "rate limiting on sensitive routes": CLAIM_IMPLEMENTED_AND_TESTED,
    "append-only project audit trail": CLAIM_IMPLEMENTED_AND_TESTED,
    "immutable original source preservation": CLAIM_IMPLEMENTED_AND_TESTED,
    "locked project operating environment": CLAIM_IMPLEMENTED_AND_TESTED,
    "external AI request gating (kill switch)": CLAIM_IMPLEMENTED_AND_TESTED,
    "organization-wide security baseline (single deployment)": CLAIM_IMPLEMENTED_WITH_LIMITATIONS,
    "external AI processing (Anthropic API)": CLAIM_CONFIGURED_DEPENDENT_ON_PROVIDER,
    "multi-organization tenant isolation": CLAIM_SPECIFIED_BUT_UNBUILT,
    "AI-assisted policy clause extraction": CLAIM_SPECIFIED_BUT_UNBUILT,
    "shared cross-customer learning pipeline": CLAIM_SPECIFIED_BUT_UNBUILT,
    "content-level assurance viewer": CLAIM_SPECIFIED_BUT_UNBUILT,
    "regional/data-residency processing control": CLAIM_UNSUPPORTED,
    # The eight claims Part XVI explicitly names as never to be offered
    # unless independently verified -- listed here, in this state, so no
    # future session can accidentally start advertising one of them.
    "data never leaves a specific country": CLAIM_PROHIBITED_FROM_CLAIMING,
    "customer-managed encryption keys": CLAIM_PROHIBITED_FROM_CLAIMING,
    "air-gapped operation": CLAIM_PROHIBITED_FROM_CLAIMING,
    "no AI provider retention": CLAIM_PROHIBITED_FROM_CLAIMING,
    "local AI only": CLAIM_PROHIBITED_FROM_CLAIMING,
    "tamper-proof logs": CLAIM_PROHIBITED_FROM_CLAIMING,
    "complete organization isolation": CLAIM_PROHIBITED_FROM_CLAIMING,
    "zero-knowledge support access": CLAIM_PROHIBITED_FROM_CLAIMING,
}


def claim_status(claim: str) -> Optional[str]:
    return SECURITY_CLAIMS_REGISTRY.get(claim)
