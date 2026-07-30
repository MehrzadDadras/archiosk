"""
CLAUDE-P31, Part XI -- Learning zone boundaries.

Honesty boundary, stated up front and load-bearing for everything
below: **this repository has no shared-learning, model-training, or
cross-customer corpus mechanism of any kind.** No fine-tuning pipeline,
no embedding index shared across projects, no fixture-collection
service -- confirmed by repository inspection (services/bhive_parser.py
calls the Anthropic API per-request, statelessly; nothing here persists
prompts/outputs anywhere but the single project's own governed record).

This module therefore does NOT move any data between zones, because
there is nowhere for Zone 3 ("Shared ARCHIOSK Improvement") to actually
receive it yet. What it DOES do, honestly: model the three zones as
named constants, and provide a governed APPROVAL-TRACKING record
(LearningContributionRequest) that captures the lifecycle Part XI
describes -- candidate signal, authority check, eligibility check,
confidentiality review, personal-information review, minimization,
approval -- as a real, tested, auditable decision trail, while making
zero claim that reaching "approved" status actually causes any
training, corpus admission, or data transfer to occur. See
services.security_policy.SECURITY_CLAIMS_REGISTRY's "shared cross-
customer learning pipeline": specified_but_unbuilt, not implemented.

A "Good" ReviewerValidation/quality rating never reaches this module at
all -- confirmed structurally: services/case_workspace.py's
record_reviewer_validation and record_disposition import nothing from
this module, and this module imports nothing from case_workspace.py's
Finding/quality machinery. That absence of a code path IS the
enforcement of "a Good rating must never automatically authorize shared
training" (Part XI), not a runtime check layered on top of one.
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


class LearningGovernanceError(Exception):
    """Raised for invalid learning-contribution operations."""


# -- Learning zones (Part XI) -------------------------------------------
ZONE_PROJECT_PRIVATE = "project_private"
ZONE_ORGANIZATION_PRIVATE = "organization_private"
ZONE_SHARED_ARCHIOSK_IMPROVEMENT = "shared_archiosk_improvement"

LEARNING_ZONES = (
    ZONE_PROJECT_PRIVATE,
    ZONE_ORGANIZATION_PRIVATE,
    ZONE_SHARED_ARCHIOSK_IMPROVEMENT,
)

# -- Contribution lifecycle stages (Part XI's own listed sequence) ------
STAGE_CANDIDATE_SIGNAL = "candidate_signal"
STAGE_AUTHORITY_CHECK = "authority_check"
STAGE_ELIGIBILITY_CHECK = "eligibility_check"
STAGE_CONFIDENTIALITY_REVIEW = "confidentiality_review"
STAGE_PERSONAL_INFORMATION_REVIEW = "personal_information_review"
STAGE_MINIMIZATION = "minimization_or_synthesis"
STAGE_APPROVED = "contribution_approved"
STAGE_REJECTED = "rejected"
STAGE_WITHDRAWN = "withdrawn"

KNOWN_STAGES = (
    STAGE_CANDIDATE_SIGNAL,
    STAGE_AUTHORITY_CHECK,
    STAGE_ELIGIBILITY_CHECK,
    STAGE_CONFIDENTIALITY_REVIEW,
    STAGE_PERSONAL_INFORMATION_REVIEW,
    STAGE_MINIMIZATION,
    STAGE_APPROVED,
    STAGE_REJECTED,
    STAGE_WITHDRAWN,
)

# The stages that must be completed, in order, before STAGE_APPROVED can
# be reached -- a request cannot jump straight from candidate_signal to
# approved.
_REQUIRED_STAGES_BEFORE_APPROVAL = (
    STAGE_AUTHORITY_CHECK,
    STAGE_ELIGIBILITY_CHECK,
    STAGE_CONFIDENTIALITY_REVIEW,
    STAGE_PERSONAL_INFORMATION_REVIEW,
    STAGE_MINIMIZATION,
)


@dataclass
class LearningContributionRequest:
    """
    A governed record of INTENT and APPROVAL STATE ONLY -- see module
    docstring. `target_zone` names where a contribution is being
    proposed to move TOWARD; approval of a request never itself performs
    that movement (no code path in this repository could -- the
    mechanism to receive Zone 3 contributions does not exist).
    """

    id: str
    project_id: str
    source_zone: str
    target_zone: str
    candidate_description: str
    requested_by: str
    created_at: str
    completed_stages: list = field(default_factory=list)
    current_stage: str = STAGE_CANDIDATE_SIGNAL
    decided_by: Optional[str] = None
    decided_at: Optional[str] = None
    rationale: Optional[str] = None


def create_contribution_request(
    project_id: str, source_zone: str, target_zone: str, candidate_description: str, requested_by: str,
) -> LearningContributionRequest:
    if source_zone not in LEARNING_ZONES or target_zone not in LEARNING_ZONES:
        raise LearningGovernanceError("source_zone/target_zone must be a recognized learning zone.")
    if not candidate_description or not candidate_description.strip():
        raise LearningGovernanceError("A contribution request requires a candidate_description.")
    return LearningContributionRequest(
        id=_new_id(), project_id=project_id, source_zone=source_zone, target_zone=target_zone,
        candidate_description=candidate_description.strip(), requested_by=requested_by, created_at=_now(),
    )


def advance_stage(request: LearningContributionRequest, stage: str, actor: str) -> LearningContributionRequest:
    """Records one completed review stage -- append-only (completed_stages
    is never rewritten, only appended to), matching this codebase's
    standing preference for append-only governed history over in-place
    mutation."""
    if stage not in KNOWN_STAGES:
        raise LearningGovernanceError(f"{stage!r} is not a recognized contribution stage.")
    if stage in (STAGE_APPROVED, STAGE_REJECTED, STAGE_WITHDRAWN):
        raise LearningGovernanceError(f"{stage!r} is a terminal decision -- use decide_contribution instead.")
    request.completed_stages.append({"stage": stage, "actor": actor, "at": _now()})
    request.current_stage = stage
    return request


def decide_contribution(
    request: LearningContributionRequest, decision: str, decided_by: str, rationale: str,
) -> LearningContributionRequest:
    """
    STAGE_APPROVED can only be reached once every stage in
    _REQUIRED_STAGES_BEFORE_APPROVAL has actually been recorded --
    "a Good rating must never automatically authorize shared training"
    generalizes here to "no shortcut of ANY kind reaches approval
    without every governed review stage on record."

    Approval of a shared_archiosk_improvement target additionally
    requires a SEPARATE authority from mere quality/troubleshooting
    sign-off -- enforced by this being the only function that can set
    STAGE_APPROVED at all, and by the caller being required to supply a
    real `decided_by` actor distinct from `requested_by` for that target
    zone (an author cannot self-approve their own outward contribution).
    """
    if decision not in (STAGE_APPROVED, STAGE_REJECTED):
        raise LearningGovernanceError(f"{decision!r} is not a valid terminal decision.")
    if decision == STAGE_APPROVED:
        completed = {entry["stage"] for entry in request.completed_stages}
        missing = [s for s in _REQUIRED_STAGES_BEFORE_APPROVAL if s not in completed]
        if missing:
            raise LearningGovernanceError(
                f"Cannot approve -- required review stages not yet recorded: {', '.join(missing)}."
            )
        if request.target_zone == ZONE_SHARED_ARCHIOSK_IMPROVEMENT and decided_by == request.requested_by:
            raise LearningGovernanceError(
                "A shared-improvement contribution cannot be approved by the same actor who requested it."
            )
    request.current_stage = decision
    request.decided_by = decided_by
    request.decided_at = _now()
    request.rationale = rationale
    return request


def withdraw_contribution(request: LearningContributionRequest, actor: str, rationale: str) -> LearningContributionRequest:
    request.current_stage = STAGE_WITHDRAWN
    request.decided_by = actor
    request.decided_at = _now()
    request.rationale = rationale
    return request
