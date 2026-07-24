"""
Case Workspace — the shared Project / Case / Source / Artifact / Analysis /
Finding / Review / Apply model, prototyped on top of the existing flat-JSON
storage (see RequirementsRegistry, GovernanceLog). One JSON file per
project, alongside that project's existing `{project_id}.json` (the
RFQ/RFP ParsedDocument) and `{project_id}.governance.jsonl`.

Authority sequence, preserved throughout this module:

    Analyze -> Review -> Apply

An Analysis run produces Findings. Findings are provisional
(claim_status="provisional") until reviewed. Review is intentionally split
into three separate, non-collapsed concepts:

- ReviewerValidation: the human's epistemic classification of a Finding's
  accuracy (Correct / Incorrect / Partial / Needs Evidence / Not
  Applicable), optionally carrying a correction_note.
- Disposition: a separate workflow decision about what happens to the
  Finding next (Confirmed / Rejected / Deferred / Known Pending
  Acceptance / Known Accepted). This, not ReviewerValidation, is what
  gates Apply eligibility.
- review_state: a derived (never stored) coarse summary (Unverified /
  Verified / Not Verified) computed from the latest ReviewerValidation.

Apply is a separate, explicit action (see apply_findings below) that is
the only thing in this module allowed to write into RequirementsRegistry
or mark a Finding as governed truth. Nothing upstream - not Analysis, not
ReviewerValidation, not Disposition being recorded - auto-applies a
Finding. Apply requires a Disposition of "Confirmed" already on record.
"""
from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Every ingested RFQ/RFP document is registered as this Project's first
# Source automatically (see get_or_create) — the RFQ/RFP pipeline is the
# beginning of the same persistent Project, not a separate product.
SOURCE_KIND_RFQ_RFP_DOCUMENT = "rfq_rfp_document"
SOURCE_KIND_DRAWING = "drawing"

FINDING_STATUS_PROVISIONAL = "provisional"
FINDING_STATUS_APPLIED = "applied"

# The five-label vocabulary required for Reviewer Validation (matches the
# same vocabulary already established in 5173's Investigation Workflow
# and Information Model docs). Kept separate from Disposition below -
# these answer two different questions ("is this finding accurate?" vs.
# "what should happen to it?") and are never collapsed into one field.
REVIEWER_VALIDATION_STATES = (
    "Correct",
    "Incorrect",
    "Partial",
    "Needs Evidence",
    "Not Applicable",
)

DISPOSITIONS = (
    "Confirmed",
    "Rejected",
    "Deferred",
    "Known Pending Acceptance",
    "Known Accepted",
)

REVIEW_STATE_UNVERIFIED = "Unverified"
REVIEW_STATE_VERIFIED = "Verified"
REVIEW_STATE_NOT_VERIFIED = "Not Verified"

RFI_STATUS_DRAFT = "draft"
RFI_STATUS_ISSUED = "issued"

REGION_STATUS_UNCHANGED = "unchanged"
REGION_STATUS_CHANGED = "changed"
REGION_STATUS_UNABLE_TO_DETERMINE = "unable_to_determine"

# -- Analysis trigger vocabulary (Prompt 7 / Foundation Batch A) -----------
# Open-world compatible (Prompt 5B/6): this is a KNOWN vocabulary with an
# explicit escape hatch (ANALYSIS_TRIGGER_OTHER + trigger_type_label), not a
# closed enum that makes an unanticipated future trigger unrepresentable.
# ANALYSIS_TRIGGER_LEGACY_UNSPECIFIED is reserved for the honest fact that
# older, already-persisted AnalysisRun records never captured a trigger at
# all - it is never applied to a newly created Analysis (see record_analysis).
ANALYSIS_TRIGGER_USER_INITIATED = "user_initiated"
ANALYSIS_TRIGGER_CLOCK_INITIATED = "clock_initiated"
ANALYSIS_TRIGGER_SOURCE_CHANGE = "source_change"
ANALYSIS_TRIGGER_STATE_CHANGE = "state_change"
ANALYSIS_TRIGGER_DEPENDENCY_CHANGE = "dependency_change"
ANALYSIS_TRIGGER_GOVERNANCE_TRIGGER = "governance_trigger"
ANALYSIS_TRIGGER_SYSTEM_RECHECK = "system_recheck"
ANALYSIS_TRIGGER_AGENT_INITIATED = "agent_initiated"
ANALYSIS_TRIGGER_EXTERNAL_UPDATE = "external_update"
ANALYSIS_TRIGGER_OTHER = "other"
ANALYSIS_TRIGGER_LEGACY_UNSPECIFIED = "legacy_unspecified"

ANALYSIS_TRIGGER_TYPES = (
    ANALYSIS_TRIGGER_USER_INITIATED,
    ANALYSIS_TRIGGER_CLOCK_INITIATED,
    ANALYSIS_TRIGGER_SOURCE_CHANGE,
    ANALYSIS_TRIGGER_STATE_CHANGE,
    ANALYSIS_TRIGGER_DEPENDENCY_CHANGE,
    ANALYSIS_TRIGGER_GOVERNANCE_TRIGGER,
    ANALYSIS_TRIGGER_SYSTEM_RECHECK,
    ANALYSIS_TRIGGER_AGENT_INITIATED,
    ANALYSIS_TRIGGER_EXTERNAL_UPDATE,
    ANALYSIS_TRIGGER_OTHER,
    ANALYSIS_TRIGGER_LEGACY_UNSPECIFIED,
)


# -- Open-World classification pattern (Prompt 8 #3) ------------------------
# Generalizes the trigger_type/"other" shape Batch A already established for
# AnalysisTrigger into a single reusable rule, applied wherever this batch
# genuinely needs it (object kinds, relationship types) rather than
# refactoring every existing classification in the app.


def normalize_open_world_value(raw: str, known_values: tuple[str, ...]) -> str:
    """
    Matches `raw` against `known_values` case-insensitively/trimmed and
    returns the CANONICAL spelling if it matches - closing uncontrolled
    spelling drift on values BEEHIVE already recognizes. If `raw` does not
    match anything known, it is returned UNCHANGED, verbatim: an
    unrecognized value is never rejected, never silently coerced into a
    known category, and never loses its original text. This is the
    concrete difference from a closed enum (which would reject it) and
    from a fully arbitrary string field (which would let "Source"/
    "source "/"SOURCE" drift apart as three different stored values).
    """
    normalized = raw.strip().lower()
    for known in known_values:
        if normalized == known.lower():
            return known
    return raw


def is_known_open_world_value(value: str, known_values: tuple[str, ...]) -> bool:
    """Whether `value` is one of the known canonical values, vs an
    extension/unclassified value BEEHIVE doesn't yet have a category for."""
    return value in known_values


# -- Object-kind vocabulary (Prompt 8 #4) ------------------------------------
# Used wherever a field names WHAT KIND of domain object something refers to
# (Supersession.predecessor_type/successor_type, Relationship.from_type/
# to_type, TemporalObligation.origin_type). Deliberately not exhaustive -
# "experience_knowledge" and "decision" are reserved for domain objects that
# don't exist yet (Prompt 5B's Experience Reservoir; Disposition is today's
# closest analogue of "decision", not an exact match) - normalize_open_world_
# value above means a caller naming some other kind is never rejected for it.
OBJECT_KIND_SOURCE = "source"
OBJECT_KIND_EVIDENCE = "evidence"
OBJECT_KIND_ARTIFACT = "artifact"
OBJECT_KIND_FINDING = "finding"
OBJECT_KIND_CASE = "case"
OBJECT_KIND_ANALYSIS = "analysis"
OBJECT_KIND_ACTIVITY = "activity"
OBJECT_KIND_TEMPORAL_OBLIGATION = "temporal_obligation"
OBJECT_KIND_EXPERIENCE_KNOWLEDGE = "experience_knowledge"
OBJECT_KIND_DECISION = "decision"

KNOWN_OBJECT_KINDS = (
    OBJECT_KIND_SOURCE,
    OBJECT_KIND_EVIDENCE,
    OBJECT_KIND_ARTIFACT,
    OBJECT_KIND_FINDING,
    OBJECT_KIND_CASE,
    OBJECT_KIND_ANALYSIS,
    OBJECT_KIND_ACTIVITY,
    OBJECT_KIND_TEMPORAL_OBLIGATION,
    OBJECT_KIND_EXPERIENCE_KNOWLEDGE,
    OBJECT_KIND_DECISION,
)

# -- Typed relationship vocabulary (Prompt 8 #1) -----------------------------
# "supersedes" is deliberately NOT here (Prompt 8 #2) - that stays governed
# exclusively through the Supersession primitive below, never an ordinary
# relationship edge.
RELATIONSHIP_TYPE_SUPPORTS = "supports"
RELATIONSHIP_TYPE_CONTRADICTS = "contradicts"
RELATIONSHIP_TYPE_QUALIFIES = "qualifies"
RELATIONSHIP_TYPE_REFERENCES = "references"
RELATIONSHIP_TYPE_DEPICTS = "depicts"
RELATIONSHIP_TYPE_CORRESPONDS_TO = "corresponds_to"
RELATIONSHIP_TYPE_IMPLEMENTS = "implements"
RELATIONSHIP_TYPE_DEPENDS_ON = "depends_on"
RELATIONSHIP_TYPE_BLOCKS = "blocks"
RELATIONSHIP_TYPE_AFFECTS = "affects"

KNOWN_RELATIONSHIP_TYPES = (
    RELATIONSHIP_TYPE_SUPPORTS,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_QUALIFIES,
    RELATIONSHIP_TYPE_REFERENCES,
    RELATIONSHIP_TYPE_DEPICTS,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    RELATIONSHIP_TYPE_IMPLEMENTS,
    RELATIONSHIP_TYPE_DEPENDS_ON,
    RELATIONSHIP_TYPE_BLOCKS,
    RELATIONSHIP_TYPE_AFFECTS,
)

# -- Temporal Obligation vocabulary (Prompt 8 #5/#9/#10) ---------------------
# Lifecycle STATE (stored, changed only by governed action) - kept separate
# from temporal CONDITION (derived, see evaluate_temporal_condition), per
# Prompt 8 #10: an ACTIVE obligation may currently be OVERDUE - those are
# two different questions.
TEMPORAL_OBLIGATION_STATUS_ACTIVE = "active"
TEMPORAL_OBLIGATION_STATUS_COMPLETED = "completed"
TEMPORAL_OBLIGATION_STATUS_CANCELLED = "cancelled"
TEMPORAL_OBLIGATION_STATUS_SUPERSEDED = "superseded"

TEMPORAL_OBLIGATION_STATUSES = (
    TEMPORAL_OBLIGATION_STATUS_ACTIVE,
    TEMPORAL_OBLIGATION_STATUS_COMPLETED,
    TEMPORAL_OBLIGATION_STATUS_CANCELLED,
    TEMPORAL_OBLIGATION_STATUS_SUPERSEDED,
)

# Derived-only condition vocabulary - never stored on the obligation itself.
TEMPORAL_CONDITION_NOT_YET_DUE = "not_yet_due"
TEMPORAL_CONDITION_DUE_SOON = "due_soon"
TEMPORAL_CONDITION_DUE = "due"
TEMPORAL_CONDITION_OVERDUE = "overdue"

# Policy, not project truth (Prompt 8 #11): a default look-ahead window for
# DUE_SOON, overridable per call - never hard-coded as the only possible
# value. A future per-project/per-contract override belongs to whichever
# batch adds real per-project configuration; this is the honest fallback.
DEFAULT_DUE_SOON_WINDOW_DAYS = 7


class CaseWorkspaceError(Exception):
    """Raised for invalid workspace operations (unknown ids, bad states, etc)."""


class ConcurrentModificationError(CaseWorkspaceError):
    """
    Raised when a governed write's expected predecessor version no longer
    matches what is actually persisted - something else (another request,
    another actor, a future clock-triggered process) already committed a
    newer version between this caller's read and its write. The caller
    must reload current state and retry; this store never silently
    overwrites a newer state with a stale one. Deliberately actor-neutral
    (Prompt 7 #3): this has no idea whether the other writer was a human
    request or a machine process, and does not need to.
    """


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return str(uuid.uuid4())


def project_clock_now() -> datetime:
    """
    Prompt 8 #7: the Project Clock as a first-class SYSTEM REFERENCE -
    current project time, evaluated against Temporal Obligations to
    derive a Temporal Condition (see evaluate_temporal_condition below).
    Deliberately NOT a Source Artifact and NOT itself an assertion that
    anything is overdue - it only ever supplies "now". Kept as its own
    named function, distinct from the string-timestamp helper `_now()`
    used for record timestamps elsewhere, as an explicit seam: a future
    real Project Clock (contract-specific calendars, time zones, a
    frozen/injected clock for testing) replaces what this one function
    returns; nothing that calls it needs to change.
    """
    return datetime.now(timezone.utc)


@dataclass
class Source:
    """
    Folder locations and filenames are external representations only -
    canonical identity is this record's `id`, not its file_path or name.
    A Source retains this identity even if later renamed or reorganized.
    Revision relationships (supersedes/superseded_by) are tracked
    explicitly by id, not inferred from filenames - see
    register_source_revision below.
    """

    id: str
    project_id: str
    kind: str  # SOURCE_KIND_*
    name: str
    added_at: str
    file_path: Optional[str] = None  # relative to the workspace's binary store, drawings only
    width: Optional[int] = None
    height: Optional[int] = None
    note: Optional[str] = None
    supersedes_source_id: Optional[str] = None
    superseded_by_source_id: Optional[str] = None


@dataclass
class ConversationMessage:
    id: str
    case_id: str
    role: str  # "human" | "system"
    text: str
    created_at: str
    action_taken: Optional[str] = None


@dataclass
class Artifact:
    """
    A derived working object. Never a substitute for its Source — every
    Artifact keeps source_id, page, and crop distinct from the Source it
    was derived from, per the Specimen != Focus Page / Source != Artifact
    principle carried over from the 5173 Information Model.
    """

    id: str
    project_id: str
    case_id: str
    kind: str  # "focus_snip" | "comparison" | "requirement_excerpt"
    source_id: str
    analysis_id: str
    created_at: str
    engine_name: str
    engine_version: str
    page: Optional[int] = None
    crop: Optional[dict] = None  # {"x","y","width","height"} normalized 0-1
    image_path: Optional[str] = None  # relative path to the generated crop, drawing artifacts only
    finding_id: Optional[str] = None


@dataclass
class Finding:
    id: str
    project_id: str
    case_id: str
    analysis_id: str
    statement: str
    machine_confidence: float
    created_at: str
    claim_status: str = FINDING_STATUS_PROVISIONAL
    artifact_id: Optional[str] = None


@dataclass
class ReviewerValidation:
    """The human's epistemic classification of a Finding's accuracy."""

    id: str
    finding_id: str
    validation: str  # REVIEWER_VALIDATION_STATES
    reviewer: str
    validated_at: str
    correction_note: Optional[str] = None


@dataclass
class Disposition:
    """A separate workflow decision about what happens to a Finding next.
    Distinct from ReviewerValidation - this, not validation accuracy, is
    what Apply actually checks."""

    id: str
    finding_id: str
    disposition: str  # DISPOSITIONS
    reviewer: str
    recorded_at: str


@dataclass
class AnalysisTrigger:
    """
    Prompt 6/7: every Analysis must be able to explain why it started -
    "reviewer asked a question" is a different fact than "the Project Clock
    detected an overdue obligation" or "a superseding drawing invalidated
    prior evidence," and that difference is itself provenance. Open-world
    compatible: trigger_type is a known vocabulary (ANALYSIS_TRIGGER_TYPES)
    with an explicit "other" escape hatch, never a closed enum that makes
    an unanticipated trigger unrepresentable.
    """

    trigger_type: str  # ANALYSIS_TRIGGER_TYPES
    trigger_type_label: Optional[str] = None  # free text; expected when trigger_type == "other"
    trigger_reference_type: Optional[str] = None  # e.g. "conversation_message"
    trigger_reference_id: Optional[str] = None
    triggered_by_actor: Optional[str] = None

    def __post_init__(self):
        if self.trigger_type not in ANALYSIS_TRIGGER_TYPES:
            raise CaseWorkspaceError(
                f"'{self.trigger_type}' is not a recognized Analysis Trigger type. "
                f"Use one of: {', '.join(ANALYSIS_TRIGGER_TYPES)} (use "
                f"'{ANALYSIS_TRIGGER_OTHER}' with trigger_type_label set for anything else)."
            )


@dataclass
class AnalysisRun:
    """
    case_id is optional (Prompt 9 #1): an Analysis no longer requires an
    Investigation Case to exist. project_id remains required and explicit
    either way - a Project-level Analysis (case_id=None) is still
    unambiguously attached to its Project, just not to any particular
    Case within it. See record_analysis for the one real constraint this
    creates: Finding/Artifact remain Case-scoped in this batch (Prompt 9
    #2's deliberately narrow extension point), so a Project-level
    Analysis must pass an empty findings list.
    """

    id: str
    project_id: str
    source_ids: list[str]
    objective: str
    engine_name: str
    engine_version: str
    started_at: str
    completed_at: str
    case_id: Optional[str] = None
    trigger: Optional[dict] = None  # asdict(AnalysisTrigger) - see record_analysis
    finding_ids: list[str] = field(default_factory=list)
    prior_corrections_considered: int = 0


@dataclass
class ApplyRecord:
    id: str
    project_id: str
    finding_ids: list[str]
    applied_by: str
    applied_at: str
    target: str  # human-readable description of what governed state changed


@dataclass
class AcceptedKnowledge:
    """
    Prompt 5 #8 (knowledge continuity) scaffold correction: Prompt 4 had
    no first-class Knowledge region - an Applied Finding just sat inside
    the Case that produced it, with nothing making it discoverable from
    a later, unrelated Case. This is the minimal structural fix: Apply
    now always creates one of these alongside marking the Finding
    applied (see apply_findings below), so accumulated intelligence
    survives independent of which Case happens to still reference it.
    Deliberately minimal - no search/indexing/graph traversal here, just
    the durable record a later feature can build on.
    """

    id: str
    project_id: str
    statement: str
    source_case_id: str
    source_finding_id: str
    established_at: str
    established_by: str


@dataclass
class Activity:
    """
    Prompt 5 #11 scaffold correction: a general work item that is
    neither a machine Analysis nor a Finding - the structural home for
    lifecycle stages whose work doesn't center on evidence review (e.g.
    "schedule a site visit", "follow up with the structural engineer",
    an opportunity go/no-go note). Kept deliberately minimal and
    separate from AnalysisRun - an Activity is not a kind of Analysis,
    it's a kind of work, machine- or human-initiated, that a Case can
    hold alongside its Findings.
    """

    id: str
    project_id: str
    case_id: str
    kind: str  # short label, e.g. "note", "task", "decision-log"
    description: str
    created_at: str
    created_by: str
    status: str = "open"  # "open" | "done"


@dataclass
class RFIDraft:
    """
    Automatically inherits its reference bundle from the Case/Finding/
    Artifact/Source chain that produced the issue at creation time, so
    the reviewer never has to manually re-type information BEEHIVE
    already knows. reference_snapshot is a point-in-time copy (not a
    live pointer) so the draft remains meaningful even if the underlying
    Source is later renamed, moved, or superseded by a revision.
    """

    id: str
    project_id: str
    case_id: str
    finding_id: str
    question_text: str
    created_at: str
    created_by: str
    reference_snapshot: dict
    status: str = RFI_STATUS_DRAFT
    issued_at: Optional[str] = None
    issued_by: Optional[str] = None


@dataclass
class RevisionNotice:
    """
    Surfaces "Reference update detected" without ever silently replacing
    the Source a Finding/Artifact was originally created from. The old
    Source and its Artifacts are untouched; this is purely an additional,
    visible notice attached to the Case.
    """

    id: str
    project_id: str
    case_id: str
    old_source_id: str
    new_source_id: str
    created_at: str
    artifact_region_status: list  # [{"artifact_id","status"}]


@dataclass
class Supersession:
    """
    Prompt 6/7 shared lineage primitive: the one governed record of "object
    A was superseded by object B, by whom, when, why, under what
    authority," shared by every domain object that needs non-destructive
    correction rather than each one reimplementing its own
    supersedes/superseded_by bookkeeping. Today only Source uses this (see
    register_source_revision); TemporalObligation and Experience/Knowledge
    revision are named future users (Prompt 5A/5B/6) that should write into
    this same table rather than growing their own copies.

    Domain objects may still keep a denormalized pointer of their own (e.g.
    Source.supersedes_source_id) for cheap, direct querying - but this
    record is the authoritative one, and both should always be written
    together in the same governed transition (see register_source_revision)
    so they can never drift apart.

    Deliberately does NOT enforce a single "current successor" per
    predecessor at this layer (Prompt 6 #9 - branching): a predecessor
    could in principle acquire more than one proposed successor before
    adjudication decides which is authoritative. Picking a winner is a
    separate, later governance question; this primitive's only job is
    making the full history reconstructable, never picking a winner itself.

    This is also the boundary Prompt 7 #1 asks to leave prepared, not
    built: a future typed relationship substrate (supports/contradicts/
    depicts/depends_on/etc, Prompt 6 D) is a SEPARATE, more loosely
    governed edge type from this one. `supersedes` is never an ordinary
    edge in that future substrate - it stays governed exclusively through
    this dedicated mechanism.
    """

    id: str
    project_id: str
    predecessor_type: str  # open-world: free text (e.g. "source"), not a closed enum
    predecessor_id: str
    successor_type: str
    successor_id: str
    actor: str
    authorized_at: str
    reason: Optional[str] = None
    authority_class: Optional[str] = None  # e.g. "approval_gate:source_revision"


@dataclass
class Relationship:
    """
    Prompt 8 #1 typed relationship substrate: the general graph-edge
    mechanism for cross-modal evidence relationships (Prompt 6 D) and
    dependency edges (Prompt 6 I / Prompt 8 #14/#15) - one mechanism
    serving both, rather than two separate graph systems, since both are
    structurally identical (an id, a typed FROM, a typed TO, provenance).

    from_type/to_type use the same object-kind vocabulary and
    normalize_open_world_value as Supersession, so a Relationship can
    point at anything Supersession can. relationship_type is validated
    against KNOWN_RELATIONSHIP_TYPES the same way, with unrecognized
    values preserved verbatim rather than rejected or coerced.

    NEVER used for supersession (Prompt 8 #2) - "supersedes" stays
    governed exclusively through the Supersession primitive, which
    carries governed lineage semantics (predecessor preserved, authority,
    reconstructable history) an ordinary relationship edge does not
    attempt to guarantee.

    provisional=True by default: a machine-asserted relationship (e.g.
    "this graphic corresponds_to this requirement") is Spin output like
    any Finding - not authoritative until something adjudicates it. This
    batch implements the field, not an adjudication workflow for it.
    """

    id: str
    project_id: str
    from_type: str
    from_id: str
    to_type: str
    to_id: str
    relationship_type: str
    created_at: str
    created_by: Optional[str] = None
    provisional: bool = True
    confidence: Optional[float] = None
    confirmed_by: Optional[str] = None
    related_analysis_id: Optional[str] = None
    related_finding_id: Optional[str] = None


@dataclass
class TemporalObligation:
    """
    Prompt 8 #5: the first genuine horizontal temporal domain object -
    generic enough for RFI response dates, submittal review periods,
    design deliverables, procurement releases, permit milestones,
    inspections, commissioning, governance expiries, risk reassessment
    dates, notices, warranties, and project milestones alike (Prompt
    5A/8), none of which get a bespoke due-date field of their own
    anywhere in BEEHIVE.

    baseline_date is the original committed date and is never changed in
    place after creation. current_accepted_date is the presently-governing
    date; a revision (see revise_temporal_obligation) creates a NEW
    TemporalObligation as successor via the Supersession primitive rather
    than mutating this one - the same non-destructive pattern already
    used for Source (Prompt 8 #6). forecast_date/actual_date are None
    until there is a real fact to put there - absence is represented
    honestly, never guessed or defaulted (Prompt 8 #5).

    case_id is optional and deliberately so: many obligations belong to a
    specific Case (an RFI response date), but some are Project-level with
    no natural Case (a project-wide risk-reassessment date, per Prompt 8
    Test A's own example). Only obligations WITH a case_id can currently
    produce a CLOCK_INITIATED Analysis on reconciliation, since
    AnalysisRun itself remains Case-scoped in this batch - see
    services/project_clock.py and the Batch B report's "Q" section for
    the Project-level-Analysis gap this leaves open.
    """

    id: str
    project_id: str
    title: str
    origin_type: str  # object kind this obligation is ABOUT (e.g. "activity", "case")
    origin_id: str
    required_action: str
    baseline_date: str  # ISO date/datetime - set once, never changed after creation
    current_accepted_date: str  # the presently-governing date
    created_at: str
    created_by: str
    case_id: Optional[str] = None
    status: str = TEMPORAL_OBLIGATION_STATUS_ACTIVE
    responsible_actor: Optional[str] = None
    forecast_date: Optional[str] = None
    actual_date: Optional[str] = None
    dependency_ids: list[str] = field(default_factory=list)
    authority_context: Optional[str] = None


def evaluate_temporal_condition(
    obligation: dict,
    now: datetime,
    due_soon_window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS,
) -> str:
    """
    Derived, never stored (Prompt 8 #9) - the obligation itself does not
    change merely because time passed; only the relationship between its
    current_accepted_date and NOW changes. Mirrors the existing
    review_state_for_finding pattern: computed fresh from stored facts
    plus "now" every time, never cached on the object.

    A terminal lifecycle status (completed/cancelled/superseded) is
    returned as-is rather than compared against the clock at all - a
    completed obligation has no live temporal condition to evaluate.
    """
    if obligation.get("status") in (
        TEMPORAL_OBLIGATION_STATUS_COMPLETED,
        TEMPORAL_OBLIGATION_STATUS_CANCELLED,
        TEMPORAL_OBLIGATION_STATUS_SUPERSEDED,
    ):
        return obligation["status"]

    accepted = datetime.fromisoformat(obligation["current_accepted_date"])
    today = now.date()
    accepted_date = accepted.date()

    if today > accepted_date:
        return TEMPORAL_CONDITION_OVERDUE
    if today == accepted_date:
        return TEMPORAL_CONDITION_DUE
    if (accepted_date - today).days <= due_soon_window_days:
        return TEMPORAL_CONDITION_DUE_SOON
    return TEMPORAL_CONDITION_NOT_YET_DUE


@dataclass
class CaseRecord:
    id: str
    project_id: str
    title: str
    objective: str
    created_at: str
    status: str = "open"
    source_ids: list[str] = field(default_factory=list)
    conversation: list[dict] = field(default_factory=list)
    analysis_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    activity_ids: list[str] = field(default_factory=list)


@dataclass
class ProjectWorkspace:
    project_id: str
    # Prompt 7 / Foundation Batch A: monotonically increasing state
    # version, checked and advanced by CaseWorkspaceStore.save() below.
    # Existing projects saved before this field existed simply lack the
    # key in their JSON and load with version=0 - an honest fresh starting
    # point for the concurrency counter, not a claim about their real
    # history (see the Foundation Batch A report for the full rationale).
    version: int = 0
    sources: list[dict] = field(default_factory=list)
    cases: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    findings: list[dict] = field(default_factory=list)
    reviewer_validations: list[dict] = field(default_factory=list)
    dispositions: list[dict] = field(default_factory=list)
    analyses: list[dict] = field(default_factory=list)
    applies: list[dict] = field(default_factory=list)
    rfi_drafts: list[dict] = field(default_factory=list)
    revision_notices: list[dict] = field(default_factory=list)
    knowledge: list[dict] = field(default_factory=list)
    activities: list[dict] = field(default_factory=list)
    supersessions: list[dict] = field(default_factory=list)
    relationships: list[dict] = field(default_factory=list)
    temporal_obligations: list[dict] = field(default_factory=list)


class CaseWorkspaceStore:
    """
    Flat-JSON persistence: one `{project_id}.workspace.json` file per
    project, stored alongside RequirementsRegistry's own
    `{project_id}.json`. Mirrors RequirementsRegistry's own
    storage-agnostic style (save()/get()) deliberately, so a future
    backend swap (if ever justified) touches one class, not call sites.
    """

    # Class-level, not per-instance: every request constructs a fresh
    # CaseWorkspaceStore (see routes/workspace.py's _store()), so an
    # instance-level lock would protect nothing across requests. This
    # serializes save() across all projects within one Python process/
    # thread pool - it closes the same-process race between concurrent
    # gthread worker threads entirely. It does NOT close a race between
    # separate gunicorn WORKER PROCESSES (deploy/gunicorn.conf.py runs
    # several) hitting the same project's file within the same instant -
    # that narrower cross-process race is a documented, intentionally
    # deferred gap (see the Foundation Batch A report), not something
    # silently claimed as solved here. The version check below still
    # deterministically catches the far more common case this batch's
    # tests actually describe: a writer that read state N, did some work,
    # and only later - after someone else has already fully committed
    # N+1 - attempts its own write.
    _save_lock = threading.Lock()

    def __init__(self, store_path: str | Path):
        self.store_path = Path(store_path)
        self.store_path.mkdir(parents=True, exist_ok=True)
        self.binaries_path = self.store_path / "workspace_artifacts"
        self.binaries_path.mkdir(parents=True, exist_ok=True)

    # -- persistence -------------------------------------------------------

    def _path_for(self, project_id: str) -> Path:
        return self.store_path / f"{project_id}.workspace.json"

    def get(self, project_id: str) -> Optional[ProjectWorkspace]:
        path = self._path_for(project_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ProjectWorkspace(**data)

    def save(self, workspace: ProjectWorkspace, expected_version: Optional[int] = None) -> ProjectWorkspace:
        """
        Every governed write goes through here. Two things changed for
        Foundation Batch A versus the original naive read-then-write:

        1. Version-checked (optimistic concurrency, not a lock): `expected
           _version` defaults to `workspace.version` - the version this
           in-memory object was loaded at, or last successfully saved to,
           if this is the Nth save within one call chain (each store
           method already ends with self.save(workspace), and workspace
           is mutated in place, so a chain of calls within one request
           naturally advances N -> N+1 -> N+2 with no extra bookkeeping
           needed from callers). If the version actually on disk has
           moved past `expected_version`, this raises
           ConcurrentModificationError instead of silently overwriting
           whatever the other writer already committed.
        2. Atomic write (temp file + Path.replace, which is an atomic
           rename on both POSIX and Windows) instead of a direct
           write_text - a crash mid-write can no longer leave a
           half-written JSON file at the real path.

        This is deliberately NOT a lock, a distributed transaction, or a
        network-coordinated mechanism (tools/dependency_fit.py already
        establishes this project stays off that kind of infrastructure).
        See the class docstring note on `_save_lock` for exactly what
        concurrency gap this does and does not close.
        """
        path = self._path_for(workspace.project_id)
        expected = workspace.version if expected_version is None else expected_version

        with self._save_lock:
            if path.exists():
                on_disk_version = json.loads(path.read_text(encoding="utf-8")).get("version", 0)
                if on_disk_version != expected:
                    raise ConcurrentModificationError(
                        f"Project {workspace.project_id} was modified by another writer "
                        f"(expected version {expected}, found {on_disk_version} on disk). "
                        "Reload the Project's current state and retry."
                    )

            workspace.version = expected + 1
            tmp_path = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
            tmp_path.write_text(json.dumps(asdict(workspace), indent=2), encoding="utf-8")
            tmp_path.replace(path)

        return workspace

    def get_or_create(
        self,
        project_id: str,
        register_document_source: Optional[dict] = None,
    ) -> ProjectWorkspace:
        """
        `register_document_source`, if given (filename + counts), is used
        once to auto-register the Project's already-ingested RFQ/RFP
        document as Source #1 — so a Project's lifecycle always starts
        from the same evidence that already exists, rather than asking
        the reviewer to re-upload something already in the registry.
        """
        workspace = self.get(project_id)
        if workspace is not None:
            return workspace

        workspace = ProjectWorkspace(project_id=project_id)

        if register_document_source is not None:
            source = Source(
                id=_new_id(),
                project_id=project_id,
                kind=SOURCE_KIND_RFQ_RFP_DOCUMENT,
                name=register_document_source["filename"],
                added_at=register_document_source.get("ingested_at") or _now(),
                note=(
                    f"{register_document_source.get('requirement_count', 0)} requirements, "
                    f"{register_document_source.get('milestone_count', 0)} milestones "
                    "already extracted by the Extract/Segment/Classify/Assemble pipeline."
                ),
            )
            workspace.sources.append(asdict(source))

        self.save(workspace)
        return workspace

    # -- lookups -------------------------------------------------------------

    @staticmethod
    def _find(items: list[dict], item_id: str, id_field: str = "id") -> Optional[dict]:
        return next((item for item in items if item[id_field] == item_id), None)

    # -- sources ---------------------------------------------------------------

    def add_drawing_source(
        self,
        workspace: ProjectWorkspace,
        name: str,
        file_path: str,
        width: int,
        height: int,
    ) -> dict:
        source = Source(
            id=_new_id(),
            project_id=workspace.project_id,
            kind=SOURCE_KIND_DRAWING,
            name=name,
            added_at=_now(),
            file_path=file_path,
            width=width,
            height=height,
        )
        workspace.sources.append(asdict(source))
        self.save(workspace)
        return asdict(source)

    def register_source_revision(
        self,
        workspace: ProjectWorkspace,
        old_source_id: str,
        name: str,
        file_path: str,
        width: int,
        height: int,
        actor: str,
        reason: Optional[str] = None,
    ) -> tuple[dict, list[dict], dict]:
        """
        Registers a NEW Source as a revision of an existing one. Never
        replaces or mutates the old Source or any Artifact/Finding
        derived from it - those keep pointing at the original evidence
        exactly as it was when the Finding was created. Returns the new
        Source, one RevisionNotice per Case that used the old Source
        (each carrying a real per-Artifact region comparison - see
        services/drawing_analysis.compare_region - rather than a guess),
        and the Supersession record (Prompt 6/7's shared lineage
        primitive) governing this revision. Source keeps its own
        supersedes_source_id/superseded_by_source_id pointers below for
        cheap direct querying, but the Supersession record - written in
        the same in-memory mutation, persisted by the same save() call -
        is the authoritative one; the two can never drift apart because
        nothing here can commit one without the other.
        """
        old_source = self._find(workspace.sources, old_source_id)
        if old_source is None:
            raise CaseWorkspaceError(f"Source {old_source_id} was not found.")

        new_source = Source(
            id=_new_id(),
            project_id=workspace.project_id,
            kind=SOURCE_KIND_DRAWING,
            name=name,
            added_at=_now(),
            file_path=file_path,
            width=width,
            height=height,
            supersedes_source_id=old_source_id,
        )
        workspace.sources.append(asdict(new_source))
        old_source["superseded_by_source_id"] = new_source.id

        from services.drawing_analysis import compare_region

        affected_artifacts = [
            a for a in workspace.artifacts if a["source_id"] == old_source_id and a.get("crop")
        ]

        notices: list[dict] = []
        affected_case_ids = {
            c["id"] for c in workspace.cases if old_source_id in c["source_ids"]
        }

        for case_id in affected_case_ids:
            region_statuses = []
            for artifact in affected_artifacts:
                if artifact["case_id"] != case_id:
                    continue
                try:
                    status = compare_region(
                        Path(old_source["file_path"]),
                        Path(file_path),
                        artifact["crop"],
                    )
                except Exception:  # noqa: BLE001 - a comparison failure is "unable to determine", not a crash
                    status = REGION_STATUS_UNABLE_TO_DETERMINE

                region_statuses.append({"artifact_id": artifact["id"], "status": status})

            notice = RevisionNotice(
                id=_new_id(),
                project_id=workspace.project_id,
                case_id=case_id,
                old_source_id=old_source_id,
                new_source_id=new_source.id,
                created_at=_now(),
                artifact_region_status=region_statuses,
            )
            workspace.revision_notices.append(asdict(notice))
            notices.append(asdict(notice))

        supersession = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=OBJECT_KIND_SOURCE,
            predecessor_id=old_source_id,
            successor_type=OBJECT_KIND_SOURCE,
            successor_id=new_source.id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
            authority_class="approval_gate:source_revision",
        )
        workspace.supersessions.append(asdict(supersession))

        self.save(workspace)
        return asdict(new_source), notices, asdict(supersession)

    def revision_notices_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [n for n in workspace.revision_notices if n["case_id"] == case_id]

    # -- cases -----------------------------------------------------------------

    def create_case(self, workspace: ProjectWorkspace, title: str, objective: str) -> dict:
        case = CaseRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            objective=objective,
            created_at=_now(),
        )
        workspace.cases.append(asdict(case))
        self.save(workspace)
        return asdict(case)

    def attach_source_to_case(self, workspace: ProjectWorkspace, case_id: str, source_id: str) -> None:
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        if source_id not in case["source_ids"]:
            case["source_ids"].append(source_id)
        self.save(workspace)

    def add_message(self, workspace: ProjectWorkspace, case_id: str, role: str, text: str, action_taken: Optional[str] = None) -> dict:
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        message = ConversationMessage(
            id=_new_id(),
            case_id=case_id,
            role=role,
            text=text,
            created_at=_now(),
            action_taken=action_taken,
        )
        case["conversation"].append(asdict(message))
        self.save(workspace)
        return asdict(message)

    # -- analysis / findings / artifacts ----------------------------------------

    def corrections_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[str]:
        """Prior correction notes from this Case's Findings, so a new
        Analysis run can visibly account for them rather than repeating
        a mistake a reviewer already corrected."""
        case = self._find(workspace.cases, case_id)
        if case is None:
            return []
        notes = []
        for finding_id in case["finding_ids"]:
            for validation in self.reviewer_validations_for_finding(workspace, finding_id):
                if validation.get("correction_note"):
                    notes.append(validation["correction_note"])
        return notes

    def record_analysis(
        self,
        workspace: ProjectWorkspace,
        source_ids: list[str],
        objective: str,
        engine_name: str,
        engine_version: str,
        findings: list[dict],
        trigger: AnalysisTrigger,
        case_id: Optional[str] = None,
        prior_corrections_considered: int = 0,
    ) -> dict:
        """
        `findings` is a list of {"statement", "machine_confidence", "crop"?,
        "image_path"?, "page"?} dicts already produced by an analysis
        engine (e.g. services/drawing_analysis.py). This method is what
        actually persists them as governed-but-provisional Finding/Artifact
        records — the engine itself never touches the workspace store.

        `trigger` is required, not defaulted (Prompt 7 #6): every NEW
        Analysis must honestly state why it started.

        `case_id` is optional (Prompt 9 #1) - a Project-level Analysis
        (case_id=None) is legitimate and no longer treated as incomplete.
        It is deliberately NOT permitted to carry real `findings`, though:
        Finding and Artifact remain Case-scoped in this batch (both still
        require a case_id of their own) - widening that too is the named,
        left-open extension point for whenever a Project-level Analysis
        actually needs to assert something, not something this batch
        forces through by fabricating a Case (Prompt 9 #1) or by silently
        dropping Finding/Artifact's own case_id requirement without
        deciding what that means.
        """
        case = None
        if case_id is not None:
            case = self._find(workspace.cases, case_id)
            if case is None:
                raise CaseWorkspaceError(f"Case {case_id} was not found.")
        elif findings:
            raise CaseWorkspaceError(
                "A Project-level Analysis (no case_id) cannot currently record "
                "Findings - Finding/Artifact remain Case-scoped in this batch. "
                "Pass an empty findings list, or attach a case_id if Findings "
                "are needed."
            )

        started_at = _now()
        analysis_id = _new_id()
        finding_ids: list[str] = []

        for item in findings:
            finding_id = _new_id()
            artifact_id = None

            if item.get("crop") or item.get("image_path"):
                artifact = Artifact(
                    id=_new_id(),
                    project_id=workspace.project_id,
                    case_id=case_id,
                    kind=item.get("artifact_kind", "focus_snip"),
                    source_id=item["source_id"],
                    analysis_id=analysis_id,
                    created_at=_now(),
                    engine_name=engine_name,
                    engine_version=engine_version,
                    page=item.get("page"),
                    crop=item.get("crop"),
                    image_path=item.get("image_path"),
                )
                artifact_id = artifact.id
                workspace.artifacts.append(asdict(artifact))
                case["artifact_ids"].append(artifact_id)

            finding = Finding(
                id=finding_id,
                project_id=workspace.project_id,
                case_id=case_id,
                analysis_id=analysis_id,
                statement=item["statement"],
                machine_confidence=item["machine_confidence"],
                created_at=_now(),
                artifact_id=artifact_id,
            )
            workspace.findings.append(asdict(finding))
            case["finding_ids"].append(finding_id)
            finding_ids.append(finding_id)

            if artifact_id is not None:
                artifact_record = self._find(workspace.artifacts, artifact_id)
                artifact_record["finding_id"] = finding_id

        analysis = AnalysisRun(
            id=analysis_id,
            project_id=workspace.project_id,
            case_id=case_id,
            source_ids=source_ids,
            objective=objective,
            engine_name=engine_name,
            engine_version=engine_version,
            started_at=started_at,
            completed_at=_now(),
            trigger=asdict(trigger),
            finding_ids=finding_ids,
            prior_corrections_considered=prior_corrections_considered,
        )
        workspace.analyses.append(asdict(analysis))
        if case is not None:
            case["analysis_ids"].append(analysis_id)

        self.save(workspace)
        return asdict(analysis)

    # -- reviewer validation --------------------------------------------------------

    def record_reviewer_validation(
        self,
        workspace: ProjectWorkspace,
        finding_id: str,
        validation: str,
        reviewer: str,
        correction_note: Optional[str] = None,
    ) -> dict:
        if validation not in REVIEWER_VALIDATION_STATES:
            raise CaseWorkspaceError(
                f"'{validation}' is not a recognized Reviewer Validation state. "
                f"Use one of: {', '.join(REVIEWER_VALIDATION_STATES)}."
            )

        finding = self._find(workspace.findings, finding_id)
        if finding is None:
            raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

        if finding["claim_status"] == FINDING_STATUS_APPLIED:
            raise CaseWorkspaceError(
                "This Finding has already been applied to governed project "
                "state and can no longer be reviewed. Its history remains "
                "in place; it cannot be re-adjudicated retroactively."
            )

        record = ReviewerValidation(
            id=_new_id(),
            finding_id=finding_id,
            validation=validation,
            reviewer=reviewer,
            validated_at=_now(),
            correction_note=correction_note,
        )
        workspace.reviewer_validations.append(asdict(record))
        # Recording a Reviewer Validation is not a Disposition and never
        # changes claim_status - see record_disposition/apply_findings.
        self.save(workspace)
        return asdict(record)

    def reviewer_validations_for_finding(self, workspace: ProjectWorkspace, finding_id: str) -> list[dict]:
        return [r for r in workspace.reviewer_validations if r["finding_id"] == finding_id]

    def latest_reviewer_validation(self, workspace: ProjectWorkspace, finding_id: str) -> Optional[dict]:
        records = self.reviewer_validations_for_finding(workspace, finding_id)
        return records[-1] if records else None

    def review_state_for_finding(self, workspace: ProjectWorkspace, finding_id: str) -> str:
        """Derived, never stored - a coarse summary of the latest Reviewer
        Validation. Verified only when the latest validation is Correct."""
        latest = self.latest_reviewer_validation(workspace, finding_id)
        if latest is None:
            return REVIEW_STATE_UNVERIFIED
        if latest["validation"] == "Correct":
            return REVIEW_STATE_VERIFIED
        return REVIEW_STATE_NOT_VERIFIED

    # -- disposition -----------------------------------------------------------------

    def record_disposition(
        self,
        workspace: ProjectWorkspace,
        finding_id: str,
        disposition: str,
        reviewer: str,
    ) -> dict:
        if disposition not in DISPOSITIONS:
            raise CaseWorkspaceError(
                f"'{disposition}' is not a recognized Disposition. "
                f"Use one of: {', '.join(DISPOSITIONS)}."
            )

        finding = self._find(workspace.findings, finding_id)
        if finding is None:
            raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

        if finding["claim_status"] == FINDING_STATUS_APPLIED:
            raise CaseWorkspaceError(
                "This Finding has already been applied to governed project state."
            )

        if self.latest_reviewer_validation(workspace, finding_id) is None:
            raise CaseWorkspaceError(
                "A Disposition requires a Reviewer Validation on record first - "
                "classify the Finding's accuracy before deciding what happens to it."
            )

        record = Disposition(
            id=_new_id(),
            finding_id=finding_id,
            disposition=disposition,
            reviewer=reviewer,
            recorded_at=_now(),
        )
        workspace.dispositions.append(asdict(record))
        self.save(workspace)
        return asdict(record)

    def dispositions_for_finding(self, workspace: ProjectWorkspace, finding_id: str) -> list[dict]:
        return [d for d in workspace.dispositions if d["finding_id"] == finding_id]

    def latest_disposition(self, workspace: ProjectWorkspace, finding_id: str) -> Optional[dict]:
        records = self.dispositions_for_finding(workspace, finding_id)
        return records[-1] if records else None

    # -- apply ---------------------------------------------------------------------

    def apply_findings(
        self,
        workspace: ProjectWorkspace,
        finding_ids: list[str],
        applied_by: str,
        target: str = "Recorded in the Project's governed finding ledger.",
    ) -> dict:
        """
        The only method in this module that may set claim_status to
        "applied". Requires every listed Finding to have a Disposition of
        "Confirmed" already on record - Apply never runs off an
        unreviewed Finding, nor off ReviewerValidation alone. This is the
        explicit, separately-authorized step; nothing upstream of this
        call (Analysis, ReviewerValidation, Disposition being recorded)
        can trigger it on its own.
        """
        for finding_id in finding_ids:
            finding = self._find(workspace.findings, finding_id)
            if finding is None:
                raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

            latest = self.latest_disposition(workspace, finding_id)
            if latest is None or latest["disposition"] != "Confirmed":
                raise CaseWorkspaceError(
                    f"Finding {finding_id} does not have a Confirmed Disposition on "
                    "record. Apply requires an explicit 'Confirmed' disposition first."
                )

        apply_record = ApplyRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            finding_ids=list(finding_ids),
            applied_by=applied_by,
            applied_at=_now(),
            target=target,
        )
        workspace.applies.append(asdict(apply_record))

        for finding_id in finding_ids:
            finding = self._find(workspace.findings, finding_id)
            finding["claim_status"] = FINDING_STATUS_APPLIED

            # Knowledge continuity (Prompt 5 #8): Apply is also the one
            # moment a Finding's substance becomes reusable outside the
            # Case that produced it. Without this, an applied Finding was
            # only ever discoverable by re-opening its original Case.
            knowledge = AcceptedKnowledge(
                id=_new_id(),
                project_id=workspace.project_id,
                statement=finding["statement"],
                source_case_id=finding["case_id"],
                source_finding_id=finding_id,
                established_at=_now(),
                established_by=applied_by,
            )
            workspace.knowledge.append(asdict(knowledge))

        self.save(workspace)
        return asdict(apply_record)

    def knowledge_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.knowledge)

    # -- shared successor / lineage primitive (Prompt 6/7) ----------------------------

    def record_supersession(
        self,
        workspace: ProjectWorkspace,
        predecessor_type: str,
        predecessor_id: str,
        successor_type: str,
        successor_id: str,
        actor: str,
        reason: Optional[str] = None,
        authority_class: Optional[str] = None,
    ) -> dict:
        """
        Standalone entry point for domain objects other than Source (see
        register_source_revision for Source's own call, made inline as
        part of its own governed transition). Used directly by
        revise_temporal_obligation below (Prompt 8), and reserved for
        Experience/Knowledge revision (Prompt 5B) once that region exists.

        predecessor_type/successor_type are normalized through the
        Open-World pattern (Prompt 8 #3/#4) - a known object kind is
        canonicalized, an unrecognized one is preserved verbatim rather
        than rejected.
        """
        record = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=normalize_open_world_value(predecessor_type, KNOWN_OBJECT_KINDS),
            predecessor_id=predecessor_id,
            successor_type=normalize_open_world_value(successor_type, KNOWN_OBJECT_KINDS),
            successor_id=successor_id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
            authority_class=authority_class,
        )
        workspace.supersessions.append(asdict(record))
        self.save(workspace)
        return asdict(record)

    def supersessions_for(self, workspace: ProjectWorkspace, object_type: str, object_id: str) -> list[dict]:
        """Every Supersession record naming this object as EITHER predecessor
        or successor - the full reconstructable history in either direction."""
        object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
        return [
            s for s in workspace.supersessions
            if (s["predecessor_type"] == object_type and s["predecessor_id"] == object_id)
            or (s["successor_type"] == object_type and s["successor_id"] == object_id)
        ]

    # -- typed relationship substrate (Prompt 8 #1) -----------------------------------

    def record_relationship(
        self,
        workspace: ProjectWorkspace,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        relationship_type: str,
        created_by: Optional[str] = None,
        provisional: bool = True,
        confidence: Optional[float] = None,
        related_analysis_id: Optional[str] = None,
        related_finding_id: Optional[str] = None,
    ) -> dict:
        relationship = Relationship(
            id=_new_id(),
            project_id=workspace.project_id,
            from_type=normalize_open_world_value(from_type, KNOWN_OBJECT_KINDS),
            from_id=from_id,
            to_type=normalize_open_world_value(to_type, KNOWN_OBJECT_KINDS),
            to_id=to_id,
            relationship_type=normalize_open_world_value(relationship_type, KNOWN_RELATIONSHIP_TYPES),
            created_at=_now(),
            created_by=created_by,
            provisional=provisional,
            confidence=confidence,
            related_analysis_id=related_analysis_id,
            related_finding_id=related_finding_id,
        )
        workspace.relationships.append(asdict(relationship))
        self.save(workspace)
        return asdict(relationship)

    def relationships_for(
        self,
        workspace: ProjectWorkspace,
        object_type: str,
        object_id: str,
        direction: str = "both",
    ) -> list[dict]:
        """direction: "from" (this object is the FROM side), "to" (this
        object is the TO side), or "both"."""
        object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
        results = []
        for r in workspace.relationships:
            matches_from = r["from_type"] == object_type and r["from_id"] == object_id
            matches_to = r["to_type"] == object_type and r["to_id"] == object_id
            if direction == "from" and matches_from:
                results.append(r)
            elif direction == "to" and matches_to:
                results.append(r)
            elif direction == "both" and (matches_from or matches_to):
                results.append(r)
        return results

    # -- Temporal Obligation (Prompt 8 #5/#6) -----------------------------------------

    def create_temporal_obligation(
        self,
        workspace: ProjectWorkspace,
        title: str,
        origin_type: str,
        origin_id: str,
        required_action: str,
        accepted_date: str,
        created_by: str,
        case_id: Optional[str] = None,
        responsible_actor: Optional[str] = None,
        authority_context: Optional[str] = None,
    ) -> dict:
        """baseline_date and current_accepted_date both start equal to
        `accepted_date` - there is no revision yet, so there is only one
        date on record so far."""
        obligation = TemporalObligation(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            origin_type=normalize_open_world_value(origin_type, KNOWN_OBJECT_KINDS),
            origin_id=origin_id,
            required_action=required_action,
            baseline_date=accepted_date,
            current_accepted_date=accepted_date,
            created_at=_now(),
            created_by=created_by,
            case_id=case_id,
            responsible_actor=responsible_actor,
            authority_context=authority_context,
        )
        workspace.temporal_obligations.append(asdict(obligation))
        self.save(workspace)
        return asdict(obligation)

    def revise_temporal_obligation(
        self,
        workspace: ProjectWorkspace,
        obligation_id: str,
        new_accepted_date: str,
        actor: str,
        reason: Optional[str] = None,
        authority_class: Optional[str] = None,
    ) -> tuple[dict, dict]:
        """
        Creates a NEW TemporalObligation as the successor - never mutates
        the old one in place (Prompt 8 #6), same non-destructive pattern
        as register_source_revision. baseline_date carries forward
        UNCHANGED from the predecessor; only current_accepted_date
        differs - so what was originally committed remains reconstructable
        no matter how many revisions occur. Linked via the same
        Supersession primitive Source revision uses, written in the same
        governed transition (one save() call) so the old obligation's
        status flip to "superseded" and the new record's creation can
        never land independently of each other.
        """
        old = self._find(workspace.temporal_obligations, obligation_id)
        if old is None:
            raise CaseWorkspaceError(f"Temporal Obligation {obligation_id} was not found.")

        new_obligation = TemporalObligation(
            id=_new_id(),
            project_id=workspace.project_id,
            title=old["title"],
            origin_type=old["origin_type"],
            origin_id=old["origin_id"],
            required_action=old["required_action"],
            baseline_date=old["baseline_date"],
            current_accepted_date=new_accepted_date,
            created_at=_now(),
            created_by=actor,
            case_id=old.get("case_id"),
            status=TEMPORAL_OBLIGATION_STATUS_ACTIVE,
            responsible_actor=old.get("responsible_actor"),
            authority_context=old.get("authority_context"),
        )
        workspace.temporal_obligations.append(asdict(new_obligation))
        old["status"] = TEMPORAL_OBLIGATION_STATUS_SUPERSEDED

        supersession = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=OBJECT_KIND_TEMPORAL_OBLIGATION,
            predecessor_id=obligation_id,
            successor_type=OBJECT_KIND_TEMPORAL_OBLIGATION,
            successor_id=new_obligation.id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
            authority_class=authority_class,
        )
        workspace.supersessions.append(asdict(supersession))

        self.save(workspace)
        return asdict(new_obligation), asdict(supersession)

    def temporal_obligations_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.temporal_obligations)

    def temporal_condition_for(
        self,
        workspace: ProjectWorkspace,
        obligation_id: str,
        now: Optional[datetime] = None,
        due_soon_window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS,
    ) -> str:
        obligation = self._find(workspace.temporal_obligations, obligation_id)
        if obligation is None:
            raise CaseWorkspaceError(f"Temporal Obligation {obligation_id} was not found.")
        return evaluate_temporal_condition(obligation, now or project_clock_now(), due_soon_window_days)

    # -- activities ------------------------------------------------------------------

    def record_activity(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        kind: str,
        description: str,
        created_by: str,
    ) -> dict:
        """
        A general work item - not an Analysis, not a Finding. The
        structural home for lifecycle work that isn't evidence-review
        shaped (Prompt 5 #11): an opportunity go/no-go note, a follow-up
        task, a coordination log entry. Deliberately has no status
        workflow of its own beyond open/done - building that out is
        explicitly deferred, not attempted here.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")

        activity = Activity(
            id=_new_id(),
            project_id=workspace.project_id,
            case_id=case_id,
            kind=kind,
            description=description,
            created_at=_now(),
            created_by=created_by,
        )
        workspace.activities.append(asdict(activity))
        case.setdefault("activity_ids", []).append(activity.id)
        self.save(workspace)
        return asdict(activity)

    def activities_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [a for a in workspace.activities if a["case_id"] == case_id]

    # -- RFI drafts --------------------------------------------------------------

    def build_reference_snapshot(self, workspace: ProjectWorkspace, finding_id: str) -> dict:
        """
        Assembles everything BEEHIVE already knows about a Finding's
        lineage, so a reviewer never has to re-type it. Never asks for
        information already present in the Case/Source/Artifact chain.
        """
        finding = self._find(workspace.findings, finding_id)
        if finding is None:
            raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

        case = self._find(workspace.cases, finding["case_id"])
        artifact = self._find(workspace.artifacts, finding.get("artifact_id")) if finding.get("artifact_id") else None
        source = self._find(workspace.sources, artifact["source_id"]) if artifact else None
        latest_validation = self.latest_reviewer_validation(workspace, finding_id)

        return {
            "case_id": case["id"] if case else None,
            "case_title": case["title"] if case else None,
            "finding_id": finding_id,
            "finding_statement": finding["statement"],
            "source_id": source["id"] if source else None,
            "source_name": source["name"] if source else None,
            "artifact_id": artifact["id"] if artifact else None,
            "page": artifact.get("page") if artifact else None,
            "region": artifact.get("crop") if artifact else None,
            "engine_name": artifact.get("engine_name") if artifact else None,
            "engine_version": artifact.get("engine_version") if artifact else None,
            "reviewer_validation": latest_validation["validation"] if latest_validation else None,
            "reviewer": latest_validation["reviewer"] if latest_validation else None,
            "snapshot_taken_at": _now(),
        }

    def create_rfi_draft(
        self,
        workspace: ProjectWorkspace,
        finding_id: str,
        question_text: str,
        created_by: str,
    ) -> dict:
        if self.latest_reviewer_validation(workspace, finding_id) is None:
            raise CaseWorkspaceError(
                "An RFI can only be drafted from a reviewed Finding - "
                "record a Reviewer Validation first."
            )

        finding = self._find(workspace.findings, finding_id)
        reference_snapshot = self.build_reference_snapshot(workspace, finding_id)

        draft = RFIDraft(
            id=_new_id(),
            project_id=workspace.project_id,
            case_id=finding["case_id"],
            finding_id=finding_id,
            question_text=question_text,
            created_at=_now(),
            created_by=created_by,
            reference_snapshot=reference_snapshot,
        )
        workspace.rfi_drafts.append(asdict(draft))
        self.save(workspace)
        return asdict(draft)

    def rfi_drafts_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [d for d in workspace.rfi_drafts if d["case_id"] == case_id]

    def issue_rfi_draft(self, workspace: ProjectWorkspace, draft_id: str, issued_by: str) -> dict:
        draft = self._find(workspace.rfi_drafts, draft_id)
        if draft is None:
            raise CaseWorkspaceError(f"RFI draft {draft_id} was not found.")
        if draft["status"] == RFI_STATUS_ISSUED:
            raise CaseWorkspaceError("This RFI has already been issued.")

        draft["status"] = RFI_STATUS_ISSUED
        draft["issued_at"] = _now()
        draft["issued_by"] = issued_by
        self.save(workspace)
        return draft
