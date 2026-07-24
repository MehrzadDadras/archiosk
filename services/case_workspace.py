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

from services.governance import GovernanceLog

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
OBJECT_KIND_REQUIREMENT = "requirement"  # canonicalized in Prompt 10 - already used as a real extension kind in Batch C's Design-Build tests
OBJECT_KIND_REVIEW_THREAD = "review_thread"  # Prompt 10
OBJECT_KIND_RELATIONSHIP = "relationship"  # Prompt 10 #2 - a Relationship can itself be an Anchor
OBJECT_KIND_DISCIPLINE = "discipline"  # Prompt 12 - a maturity/expectation scope, not a stored object of its own
OBJECT_KIND_PACKAGE = "package"  # Prompt 12 - same: a labeled scope, not a stored object
OBJECT_KIND_PROJECT = "project"  # Prompt 12 - the whole-project scope; scope_id equals the Project's own project_id
OBJECT_KIND_EXPECTED_INFORMATION_PROFILE = "expected_information_profile"  # Prompt 12
OBJECT_KIND_MATURITY_RECORD = "maturity_record"  # Prompt 12

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
    OBJECT_KIND_REQUIREMENT,
    OBJECT_KIND_REVIEW_THREAD,
    OBJECT_KIND_RELATIONSHIP,
    OBJECT_KIND_DISCIPLINE,
    OBJECT_KIND_PACKAGE,
    OBJECT_KIND_PROJECT,
    OBJECT_KIND_EXPECTED_INFORMATION_PROFILE,
    OBJECT_KIND_MATURITY_RECORD,
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
RELATIONSHIP_TYPE_RESULTED_IN = "resulted_in"  # Prompt 10 #7: ReviewThread -> structured outcome linkage

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
    RELATIONSHIP_TYPE_RESULTED_IN,
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

# -- Review Thread vocabulary (Prompt 10) ------------------------------------
# All four vocabularies below use the Open-World pattern (known values
# normalized, unrecognized values preserved verbatim) - none of them are
# closed enums. intended_actor on Attention is deliberately NOT one of
# these: a person/role name space is fundamentally unbounded (anyone's
# username, any discipline), unlike these, which name a real finite set of
# professional review-comment shapes, thread lifecycle stages, attention
# states, and resolution outcome kinds.

MESSAGE_TYPE_OBSERVATION = "observation"
MESSAGE_TYPE_QUESTION = "question"
MESSAGE_TYPE_CRITIQUE = "critique"
MESSAGE_TYPE_CLARIFICATION_REQUEST = "clarification_request"
MESSAGE_TYPE_RESPONSE = "response"
MESSAGE_TYPE_SUGGESTION = "suggestion"
MESSAGE_TYPE_INTERPRETATION = "interpretation"
MESSAGE_TYPE_DECISION_NOTE = "decision_note"
MESSAGE_TYPE_EVIDENCE_NOTE = "evidence_note"
MESSAGE_TYPE_RESOLUTION_NOTE = "resolution_note"

KNOWN_MESSAGE_TYPES = (
    MESSAGE_TYPE_OBSERVATION,
    MESSAGE_TYPE_QUESTION,
    MESSAGE_TYPE_CRITIQUE,
    MESSAGE_TYPE_CLARIFICATION_REQUEST,
    MESSAGE_TYPE_RESPONSE,
    MESSAGE_TYPE_SUGGESTION,
    MESSAGE_TYPE_INTERPRETATION,
    MESSAGE_TYPE_DECISION_NOTE,
    MESSAGE_TYPE_EVIDENCE_NOTE,
    MESSAGE_TYPE_RESOLUTION_NOTE,
)

MESSAGE_ORIGIN_HUMAN = "human"
MESSAGE_ORIGIN_MACHINE = "machine"
MESSAGE_ORIGIN_SYSTEM = "system"
# Closed, not open-world: a message's origin is a structural fact about how
# BEEHIVE itself worked, not an evolving professional vocabulary - there is
# no legitimate fourth kind of origin to leave room for the way there is
# for message content or thread status.
KNOWN_MESSAGE_ORIGINS = (MESSAGE_ORIGIN_HUMAN, MESSAGE_ORIGIN_MACHINE, MESSAGE_ORIGIN_SYSTEM)

THREAD_STATUS_OPEN = "open"
THREAD_STATUS_UNDER_REVIEW = "under_review"
THREAD_STATUS_WAITING_FOR_RESPONSE = "waiting_for_response"
THREAD_STATUS_WAITING_FOR_EVIDENCE = "waiting_for_evidence"
THREAD_STATUS_RESOLVED = "resolved"
THREAD_STATUS_CLOSED = "closed"
THREAD_STATUS_REOPENED = "reopened"

KNOWN_THREAD_STATUSES = (
    THREAD_STATUS_OPEN,
    THREAD_STATUS_UNDER_REVIEW,
    THREAD_STATUS_WAITING_FOR_RESPONSE,
    THREAD_STATUS_WAITING_FOR_EVIDENCE,
    THREAD_STATUS_RESOLVED,
    THREAD_STATUS_CLOSED,
    THREAD_STATUS_REOPENED,
)

ATTENTION_STATUS_PENDING = "pending"
ATTENTION_STATUS_ACKNOWLEDGED = "acknowledged"
ATTENTION_STATUS_RESPONDED = "responded"

KNOWN_ATTENTION_STATUSES = (ATTENTION_STATUS_PENDING, ATTENTION_STATUS_ACKNOWLEDGED, ATTENTION_STATUS_RESPONDED)

RESOLUTION_OUTCOME_NO_ISSUE = "no_issue"
RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE = "acceptable_alternative"
RESOLUTION_OUTCOME_NEEDS_EVIDENCE = "needs_evidence"
RESOLUTION_OUTCOME_CONFIRMED_ISSUE = "confirmed_issue"
RESOLUTION_OUTCOME_WITHDRAWN = "withdrawn"

KNOWN_RESOLUTION_OUTCOMES = (
    RESOLUTION_OUTCOME_NO_ISSUE,
    RESOLUTION_OUTCOME_ACCEPTABLE_ALTERNATIVE,
    RESOLUTION_OUTCOME_NEEDS_EVIDENCE,
    RESOLUTION_OUTCOME_CONFIRMED_ISSUE,
    RESOLUTION_OUTCOME_WITHDRAWN,
)

# -- Source document identity / provenance vocabulary (Prompt 15) -----------
# Document-level authority (Prompt 15 #5) - distinct from per-clause
# Requirement.classification (Prompt 15 #11): a Source can be uniformly
# "contractual" as a whole document while individual Requirements it
# contains carry their own, different, per-clause classification.
DOCUMENT_AUTHORITY_CONTRACTUAL = "contractual"
DOCUMENT_AUTHORITY_REFERENCE = "reference"
DOCUMENT_AUTHORITY_INFORMATIONAL = "informational"
DOCUMENT_AUTHORITY_INDICATIVE = "indicative"
DOCUMENT_AUTHORITY_DRAFT = "draft"
DOCUMENT_AUTHORITY_ISSUED_FOR_PROCUREMENT = "issued_for_procurement"
DOCUMENT_AUTHORITY_PROJECT_AGREEMENT = "project_agreement"

KNOWN_DOCUMENT_AUTHORITY_LEVELS = (
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    DOCUMENT_AUTHORITY_REFERENCE,
    DOCUMENT_AUTHORITY_INFORMATIONAL,
    DOCUMENT_AUTHORITY_INDICATIVE,
    DOCUMENT_AUTHORITY_DRAFT,
    DOCUMENT_AUTHORITY_ISSUED_FOR_PROCUREMENT,
    DOCUMENT_AUTHORITY_PROJECT_AGREEMENT,
)

# Prompt 15 #4: generic enough for future uploads/connectors/imports, not
# just the controlled synthetic-corpus test scenario.
SOURCE_ORIGIN_TYPE_UPLOAD = "upload"
SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS = "controlled_corpus"
SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR = "external_connector"
SOURCE_ORIGIN_TYPE_IMPORT = "import"

KNOWN_SOURCE_ORIGIN_TYPES = (
    SOURCE_ORIGIN_TYPE_UPLOAD,
    SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
    SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR,
    SOURCE_ORIGIN_TYPE_IMPORT,
)

# -- Requirement vocabulary (Prompt 15) --------------------------------------
# Prompt 15 #10/#11: the SAME classification vocabulary NREOCRC itself uses
# ([MANDATORY]/[RATED]/[INDICATIVE]/[REFERENCE]/[INFORMATIONAL]) - per-
# clause, deliberately distinct from Source.document_authority above.
REQUIREMENT_CLASSIFICATION_MANDATORY = "mandatory"
REQUIREMENT_CLASSIFICATION_RATED = "rated"
REQUIREMENT_CLASSIFICATION_INDICATIVE = "indicative"
REQUIREMENT_CLASSIFICATION_REFERENCE = "reference"
REQUIREMENT_CLASSIFICATION_INFORMATIONAL = "informational"

KNOWN_REQUIREMENT_CLASSIFICATIONS = (
    REQUIREMENT_CLASSIFICATION_MANDATORY,
    REQUIREMENT_CLASSIFICATION_RATED,
    REQUIREMENT_CLASSIFICATION_INDICATIVE,
    REQUIREMENT_CLASSIFICATION_REFERENCE,
    REQUIREMENT_CLASSIFICATION_INFORMATIONAL,
)

# Prompt 15 #17: existence/lifecycle STATE, never a compliance outcome.
# COMPLIANT/NON_COMPLIANT deliberately do not belong to this vocabulary -
# those are evaluation results produced by Analysis/Finding, not facts
# about whether the Requirement record itself is currently in force.
REQUIREMENT_STATUS_ACTIVE = "active"
REQUIREMENT_STATUS_SUPERSEDED = "superseded"
REQUIREMENT_STATUS_WITHDRAWN = "withdrawn"
REQUIREMENT_STATUS_FUTURE_EFFECTIVE = "future_effective"
REQUIREMENT_STATUS_UNKNOWN = "unknown"

KNOWN_REQUIREMENT_STATUSES = (
    REQUIREMENT_STATUS_ACTIVE,
    REQUIREMENT_STATUS_SUPERSEDED,
    REQUIREMENT_STATUS_WITHDRAWN,
    REQUIREMENT_STATUS_FUTURE_EFFECTIVE,
    REQUIREMENT_STATUS_UNKNOWN,
)

# Hard denylist, not an open-world "known" vocabulary (see
# set_requirement_status): a compliance outcome must never become a
# Requirement status under any spelling, so this is deliberately checked
# and rejected rather than left to normalize_open_world_value's usual
# "preserve unfamiliar values verbatim" behavior.
_REQUIREMENT_STATUS_COMPLIANCE_DENYLIST = (
    "compliant", "non_compliant", "noncompliant", "not_compliant",
)

# Prompt 15 #8: where a Requirement's source_location points, reusing the
# same flexible-dict approach as Anchor.location (Batch D) rather than a
# new structural mechanism.
REQUIREMENT_LOCATION_TYPE_CLAUSE = "clause"
REQUIREMENT_LOCATION_TYPE_SECTION = "section"
REQUIREMENT_LOCATION_TYPE_PAGE = "page"
REQUIREMENT_LOCATION_TYPE_TABLE = "table"
REQUIREMENT_LOCATION_TYPE_TABLE_ROW = "table_row"
REQUIREMENT_LOCATION_TYPE_FIGURE = "figure"
REQUIREMENT_LOCATION_TYPE_PARAGRAPH = "paragraph"

KNOWN_REQUIREMENT_LOCATION_TYPES = (
    REQUIREMENT_LOCATION_TYPE_CLAUSE,
    REQUIREMENT_LOCATION_TYPE_SECTION,
    REQUIREMENT_LOCATION_TYPE_PAGE,
    REQUIREMENT_LOCATION_TYPE_TABLE,
    REQUIREMENT_LOCATION_TYPE_TABLE_ROW,
    REQUIREMENT_LOCATION_TYPE_FIGURE,
    REQUIREMENT_LOCATION_TYPE_PARAGRAPH,
)

# Prompt 15 #19/#20: registration provenance (who/what created this BEEHIVE
# record) is never conflated with requirement AUTHORITY (who/what the
# Owner is). Also the explicit honesty mechanism: a caller must say
# whether a Requirement was actually machine-extracted or hand-registered
# as a test fixture - see the NREOCRC lab script's own past overclaiming
# risk, now structurally prevented from being silent about it.
REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED = "machine_extracted"
REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE = "manually_registered_test_fixture"
REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE = "derived_from_structured_source"
REQUIREMENT_REGISTRATION_IMPORTED = "imported"
REQUIREMENT_REGISTRATION_OTHER = "other"

KNOWN_REQUIREMENT_REGISTRATION_METHODS = (
    REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE,
    REQUIREMENT_REGISTRATION_IMPORTED,
    REQUIREMENT_REGISTRATION_OTHER,
)

# -- Expected Information Profile / Maturity vocabulary (Prompt 11/12) -------
# Per Prompt 11 B: "expectation authority" is split into two independent axes
# rather than one flat label set. `bindingness` (below) is a small, genuinely
# closed spectrum of how strongly something is expected. WHO/WHAT says so
# (a contract clause, an owner PEP, industry practice, a machine inference)
# is unbounded free text - `ExpectationItem.authority_source` - mirroring the
# already-proven Supersession.authority_class free-text pattern, not a
# vocabulary requiring validation.

EXPECTATION_BINDINGNESS_MANDATORY = "mandatory"  # contractual/mandatory
EXPECTATION_BINDINGNESS_EXPECTED = "expected"  # project-required / normally expected
EXPECTATION_BINDINGNESS_RECOMMENDED = "recommended"  # recommended/typical/conditional collapse here - see report
EXPECTATION_BINDINGNESS_INFERRED = "inferred"  # machine-inferred - always the weakest tier

KNOWN_EXPECTATION_BINDINGNESS = (
    EXPECTATION_BINDINGNESS_MANDATORY,
    EXPECTATION_BINDINGNESS_EXPECTED,
    EXPECTATION_BINDINGNESS_RECOMMENDED,
    EXPECTATION_BINDINGNESS_INFERRED,
)

EXPECTED_KIND_DOCUMENT = "document"
EXPECTED_KIND_INFORMATION_WITHIN_DOCUMENT = "information_within_document"
EXPECTED_KIND_DECISION = "decision"
EXPECTED_KIND_ANALYSIS = "analysis"
EXPECTED_KIND_DATA = "data"
EXPECTED_KIND_EVIDENCE = "evidence"

KNOWN_EXPECTED_INFORMATION_KINDS = (
    EXPECTED_KIND_DOCUMENT,
    EXPECTED_KIND_INFORMATION_WITHIN_DOCUMENT,
    EXPECTED_KIND_DECISION,
    EXPECTED_KIND_ANALYSIS,
    EXPECTED_KIND_DATA,
    EXPECTED_KIND_EVIDENCE,
)

EXPECTATION_ITEM_STATUS_ACTIVE = "active"
EXPECTATION_ITEM_STATUS_WITHDRAWN = "withdrawn"
EXPECTATION_ITEM_STATUS_NOT_APPLICABLE = "not_applicable"

KNOWN_EXPECTATION_ITEM_STATUSES = (
    EXPECTATION_ITEM_STATUS_ACTIVE,
    EXPECTATION_ITEM_STATUS_WITHDRAWN,
    EXPECTATION_ITEM_STATUS_NOT_APPLICABLE,
)

PROFILE_STATUS_ACTIVE = "active"
PROFILE_STATUS_SUPERSEDED = "superseded"
PROFILE_STATUS_WITHDRAWN = "withdrawn"

KNOWN_PROFILE_STATUSES = (PROFILE_STATUS_ACTIVE, PROFILE_STATUS_SUPERSEDED, PROFILE_STATUS_WITHDRAWN)

# Example/canonical values only (Prompt 12 #5) - never the universal
# lifecycle. A project-specific stage (e.g. "Integrated Systems Gate B")
# normalizes to itself, verbatim, via normalize_open_world_value - it is
# never forced into this list or rejected for not being in it.
KNOWN_DESIGN_MATURITY_STAGES = (
    "concept",
    "schematic",
    "design_development",
    "bridging",
    "tender",
    "issued_for_construction",
)

# Same status: example/canonical only, roughly increasing precision - never
# inferred from design maturity (Prompt 11 D / Prompt 12 #6).
KNOWN_ESTIMATE_BASIS_VALUES = (
    "benchmark",
    "elemental",
    "assembly",
    "quantity_based",
    "trade_package",
    "subcontractor_quote",
    "detailed_takeoff",
    "procurement_pricing",
)

MATURITY_TYPE_DESIGN = "design"
MATURITY_TYPE_ESTIMATE = "estimate"
# Closed, not open-world: exactly two structurally distinct dimensions
# (Prompt 11 D / Prompt 12 #6) - there is no legitimate third "kind" of
# maturity this batch's model is meant to hold.
KNOWN_MATURITY_TYPES = (MATURITY_TYPE_DESIGN, MATURITY_TYPE_ESTIMATE)

MATURITY_STATUS_ACTIVE = "active"
MATURITY_STATUS_SUPERSEDED = "superseded"
KNOWN_MATURITY_STATUSES = (MATURITY_STATUS_ACTIVE, MATURITY_STATUS_SUPERSEDED)

# -- Information Sufficiency outcome vocabulary (Prompt 12 #8) ---------------
# This is the EVALUATOR's own closed output vocabulary (like
# TEMPORAL_CONDITION_* before it) - never open-world, never supplied by a
# caller, never persisted as its own record. See evaluate_information_
# sufficiency below.
SUFFICIENCY_EXPECTED_AND_FOUND = "expected_and_found"
SUFFICIENCY_EXPECTED_NOT_FOUND = "expected_not_found"
SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE = "found_but_insufficient_for_stage"
SUFFICIENCY_NOT_EXPECTED_YET = "not_expected_yet"
SUFFICIENCY_EXPECTATION_MAY_NOT_APPLY = "expectation_may_not_apply"
SUFFICIENCY_INACCESSIBLE = "inaccessible"
SUFFICIENCY_AUTHORITY_OR_VERSION_UNCERTAIN = "authority_or_version_uncertain"
SUFFICIENCY_SUPERSEDED = "superseded"
SUFFICIENCY_CONFLICTING = "conflicting_current_information"


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
    # -- document identity / provenance (Prompt 15) --------------------------
    # Deliberately distinct from `name`/`file_path` (Prompt 15 #3): `name` is
    # the physical file's name, `document_id` is the issuer's own document
    # identity - a later revision may keep the same document_id with a
    # different file_path/file_hash/revision entirely. None of these fields
    # are validated as required - honest absence throughout (Prompt 15 #2).
    document_id: Optional[str] = None
    revision: Optional[str] = None  # free text - "0", "1", "A" - not assumed numeric
    issue_date: Optional[str] = None
    issuer: Optional[str] = None
    document_status: Optional[str] = None  # verbatim, as literally stated by the source (e.g. "ISSUED WITH RFP — CONTRACTUAL DOCUMENT")
    document_authority: Optional[str] = None  # open-world normalized, KNOWN_DOCUMENT_AUTHORITY_LEVELS
    file_hash: Optional[str] = None
    # Generic provenance reference (Prompt 15 #4) - NOT specific to the
    # NREOCRC test corpus. origin_type names what kind of place this Source
    # came from; origin_reference's meaning depends on origin_type (an
    # immutable corpus file path, an external connector's artifact id, an
    # import archive reference, or None for an ordinary upload).
    origin_type: Optional[str] = None  # open-world, KNOWN_SOURCE_ORIGIN_TYPES
    origin_reference: Optional[str] = None


@dataclass
class Requirement:
    """
    Prompt 14/15: a source-stated Requirement is project meaning that
    exists the moment the Owner (or any issuer) states it - independently
    of any machine analysis. It is NOT a Finding: a Finding is a
    machine/reviewer ASSERTION produced by examining evidence; a
    Requirement never requires a Finding to exist, and a Finding must
    never be used merely as storage for an Owner requirement (Prompt 15
    #1). Registering a Requirement makes no claim about whether it is
    satisfied - that question belongs entirely to Analysis/Finding/Pass/
    Human Adjudication, layers this object never touches.

    `original_requirement_identifier` preserves the source's own numbering
    ("12.1", "Appendix OPR-1 Row 20") - BEEHIVE's own `id` is a separate,
    stable internal identity; neither replaces the other (Prompt 15 #7).

    `classification` (open-world, e.g. mandatory/indicative) is the
    per-clause authority - deliberately independent of Source.
    document_authority, the whole-document classification (Prompt 15
    #11): a Contractual document can contain both Mandatory and
    Indicative clauses simultaneously.

    `status` is existence/lifecycle state only - never a compliance
    result (Prompt 15 #17). COMPLIANT/NON_COMPLIANT are not, and must
    never become, values of this field.

    `registration_method` is honesty machinery (Prompt 15 #19/#20): it
    must always say whether this record was actually machine-extracted or
    hand-registered as a test fixture - the exact distinction the NREOCRC
    corpus test needed and previously had to track only informally in a
    lab-script comment.

    Lineage/revision reuses the shared Supersession primitive (see
    revise_requirement) - the same non-destructive pattern as Source and
    TemporalObligation revision, not a new mechanism.
    """

    id: str
    project_id: str
    source_id: str
    original_requirement_identifier: str
    text_reference: str
    created_at: str
    created_by: str
    registration_method: str  # KNOWN_REQUIREMENT_REGISTRATION_METHODS
    status: str = REQUIREMENT_STATUS_ACTIVE
    classification: Optional[str] = None  # open-world, KNOWN_REQUIREMENT_CLASSIFICATIONS
    authority_source: Optional[str] = None  # free text, mirrors Supersession.authority_class
    applicability: Optional[str] = None
    subject_domain: Optional[str] = None  # open-world
    title: Optional[str] = None
    source_location: Optional[dict] = None  # {"location_type": open-world KNOWN_REQUIREMENT_LOCATION_TYPES, ...}
    effective_context: Optional[str] = None


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


def validate_requirement_location_citation(source_text: str, location_value: str) -> bool:
    """
    Lightweight citation-validation hook (Prompt 15 #23). Prompt 13's
    NREOCRC test produced a real defect: a Relationship cited "Section
    4.3" when the source text it was meant to describe actually named
    "Section 4.5". This function would have caught that: it checks
    whether `location_value` (e.g. "4.3", "Section 4.5") appears
    literally in `source_text` - a substring presence check, not real
    document-structure parsing.

    Deliberately minimal: no file I/O (the caller supplies the text it
    already has), no table/section-aware verification. A True result is
    not proof of correctness (the string could appear coincidentally
    elsewhere in a large document) - only a False result is a strong,
    actionable signal that a citation is wrong and should be reviewed
    before being trusted.
    """
    return location_value in source_text


def compare_maturity(a: str, b: str, known_order: tuple[str, ...] = KNOWN_DESIGN_MATURITY_STAGES) -> Optional[int]:
    """
    Compares two maturity values by position in `known_order`. Returns -1
    (a earlier than b), 0 (equal), 1 (a later than b), or None if EITHER
    value is not part of the known ordered vocabulary - an honest "cannot
    determine" rather than a guess (Prompt 12 #14: an unfamiliar project-
    specific maturity stage must never be silently forced into a known
    ordering just so a comparison can produce an answer).
    """
    if a not in known_order or b not in known_order:
        return None
    ia, ib = known_order.index(a), known_order.index(b)
    return (ia > ib) - (ia < ib)


def evaluate_information_sufficiency(
    item: dict,
    observed: list[dict],
    milestone_condition: Optional[str] = None,
) -> dict:
    """
    Prompt 11/12: the Expected Information Shadow's actual comparison -
    derived, never persisted, mirroring evaluate_temporal_condition's
    shape exactly. Given a stored ExpectationItem dict and an explicit
    list of observed-evidence descriptors, returns one SUFFICIENCY_*
    outcome plus supporting detail. Never called automatically by
    anything in this batch, and never itself decides whether to create a
    Finding/ReviewThread/WorkItem - that decision belongs to a later,
    separately-governed workflow (Prompt 11 AA's escalation threshold).

    `observed` entries are plain dicts describing what BEEHIVE already
    knows about matching evidence - deliberately NOT auto-discovered from
    the whole workspace (Prompt 12 #7): matching an expectation to actual
    Sources/Evidence is a search/reconciliation step left to a later
    workflow; this function only proves the comparison logic given an
    explicit observed set. Each entry may carry: "resolution_level"
    (compared against item["expected_maturity"]), "accessible" (bool),
    "authority_confidence" ("confirmed"|"uncertain"), "superseded" (bool),
    "conflicts" (bool).

    Checks run in a deliberate priority order (documented inline) -
    applicability is checked before existence, because "this doesn't even
    apply here" is a more fundamental fact than whether something was
    found.
    """
    if item.get("status") in (EXPECTATION_ITEM_STATUS_WITHDRAWN, EXPECTATION_ITEM_STATUS_NOT_APPLICABLE):
        return {"outcome": SUFFICIENCY_EXPECTATION_MAY_NOT_APPLY, "detail": {"item_status": item["status"]}}

    if milestone_condition == TEMPORAL_CONDITION_NOT_YET_DUE:
        return {"outcome": SUFFICIENCY_NOT_EXPECTED_YET, "detail": {"milestone_condition": milestone_condition}}

    if not observed:
        return {"outcome": SUFFICIENCY_EXPECTED_NOT_FOUND, "detail": {}}

    if all(o.get("superseded") for o in observed):
        return {"outcome": SUFFICIENCY_SUPERSEDED, "detail": {"observed_count": len(observed)}}

    if any(not o.get("accessible", True) for o in observed):
        return {"outcome": SUFFICIENCY_INACCESSIBLE, "detail": {}}

    if any(o.get("authority_confidence") == "uncertain" for o in observed):
        return {"outcome": SUFFICIENCY_AUTHORITY_OR_VERSION_UNCERTAIN, "detail": {}}

    if any(o.get("conflicts") for o in observed):
        return {"outcome": SUFFICIENCY_CONFLICTING, "detail": {}}

    detail: dict = {}
    expected_maturity = item.get("expected_maturity")
    if expected_maturity:
        resolution_levels = [o["resolution_level"] for o in observed if o.get("resolution_level")]
        if resolution_levels:
            comparisons = [compare_maturity(level, expected_maturity) for level in resolution_levels]
            if any(c is not None and c < 0 for c in comparisons):
                return {
                    "outcome": SUFFICIENCY_FOUND_BUT_INSUFFICIENT_FOR_STAGE,
                    "detail": {"observed_resolution_levels": resolution_levels, "expected_maturity": expected_maturity},
                }
            if all(c is None for c in comparisons):
                detail["maturity_comparison"] = "indeterminate - value(s) not in a known ordered vocabulary"

    return {"outcome": SUFFICIENCY_EXPECTED_AND_FOUND, "detail": detail}


@dataclass
class Anchor:
    """
    Prompt 10 #2: what a ReviewThread is about. Uses the same open-world
    object-kind vocabulary as Supersession/Relationship rather than a new
    polymorphic framework. One primary Anchor per ReviewThread
    (ReviewThread.anchor); ReviewThread.related_anchors holds any
    additional lightweight references, kept intentionally unstructured
    (plain dicts) rather than a second first-class object - overbuilding
    this was explicitly warned against.
    """

    anchor_type: str  # object kind, open-world (source/finding/relationship/temporal_obligation/requirement/...)
    anchor_id: str
    source_id: Optional[str] = None
    location: Optional[dict] = None  # flexible - {"page":..., "region":...}, {"paragraph":...}, etc.
    description: Optional[str] = None


@dataclass
class ReviewThread:
    """
    Prompt 10 #1: a governed discussion concerning a particular matter -
    explicitly NOT a Finding, Work Item, Risk, Analysis, or chat session
    (though it may reference all of those). case_id is optional from the
    start (Prompt 10 #20, extending Batch C's principle): a thread does
    not require an Investigation Case any more than a Project-level
    Analysis does.

    `resolution` holds the CURRENT resolution (None if never resolved);
    `resolution_history` holds every PRIOR resolution, pushed there only
    on reopen (see reopen_review_thread) - never overwritten, never
    deleted (Prompt 10 #5/#13). `outcome_refs` records every structured
    consequence the thread has been linked to (Prompt 10 #7) - the
    discussion itself never IS project truth; these are pointers to
    wherever that truth actually lives (a Relationship, a Finding, etc).
    """

    id: str
    project_id: str
    title: str
    anchor: dict  # asdict(Anchor)
    created_at: str
    created_by: str
    case_id: Optional[str] = None
    status: str = THREAD_STATUS_OPEN
    related_anchors: list[dict] = field(default_factory=list)
    resolution: Optional[dict] = None
    resolution_history: list[dict] = field(default_factory=list)
    outcome_refs: list[dict] = field(default_factory=list)


@dataclass
class ReviewMessage:
    """
    Prompt 10 #3/#8/#14: one entry in a ReviewThread's discussion.
    `origin` distinguishes human/machine/system authorship structurally -
    `text` must contain only what a human reviewer should actually see
    (Prompt 10 #3/#9 - no hidden chain-of-thought, ever). A machine-
    authored message should carry related_analysis_id whenever it
    honestly can, so "why did BEEHIVE say that" is always traceable back
    to a real AnalysisRun rather than asserted as free-floating text.
    `project_state_version` is captured at creation for provenance -
    which governed state this message was written against.
    """

    id: str
    thread_id: str
    project_id: str
    origin: str  # KNOWN_MESSAGE_ORIGINS
    actor: str
    message_type: str  # open-world, KNOWN_MESSAGE_TYPES
    text: str
    created_at: str
    reply_to_message_id: Optional[str] = None
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None
    related_analysis_id: Optional[str] = None
    related_finding_id: Optional[str] = None
    project_state_version: Optional[int] = None


@dataclass
class Attention:
    """
    Prompt 10 #4: "this person/role should attend to this matter" - never
    contractual responsibility, requirement ownership, approval authority,
    or a Work Item (which does not exist in this batch, or at all yet).
    `intended_actor` is deliberately free text, not validated against any
    vocabulary (see the module-level note above KNOWN_MESSAGE_TYPES) -
    people and roles are not a closed or even meaningfully "known" set the
    way message types or thread statuses are.
    """

    id: str
    thread_id: str
    project_id: str
    message_id: str  # the message that generated this attention request
    intended_actor: str
    created_by: str
    created_at: str
    status: str = ATTENTION_STATUS_PENDING
    acknowledged_at: Optional[str] = None
    responded_message_id: Optional[str] = None


@dataclass
class ThreadResolution:
    """Prompt 10 #6. Additive, never a mutation of the conversation that
    preceded it - the messages remain exactly as written; this is a
    separate record layered on top."""

    resolution_outcome: str  # open-world, KNOWN_RESOLUTION_OUTCOMES
    summary: str
    resolved_by: str
    resolved_at: str
    related_evidence_refs: list[dict] = field(default_factory=list)
    authority_context: Optional[str] = None


@dataclass
class ExpectationItem:
    """
    Prompt 12 #3: one expected information item within a profile - a
    document, information within a document, a decision, an analysis,
    data, or evidence (open-world `expected_kind`). Embedded inside its
    owning ExpectedInformationProfile's `items` list, not a separate
    top-level store, mirroring how Anchor is embedded inside ReviewThread.

    `bindingness` + `authority_source` implement Prompt 11 B's split:
    bindingness is the small closed "how strongly expected" spectrum;
    authority_source is free text naming WHO/WHAT says so (a contract
    clause, an owner PEP, industry practice, "machine_inferred") - never
    validated, exactly like Supersession.authority_class.

    `expected_provider` names who would normally supply this information -
    explicitly NOT contractual responsibility, Work Item ownership, or
    approval authority (Prompt 12 #15). `milestone_trigger_id` optionally
    names a TemporalObligation gating whether this expectation is active
    yet at all (Prompt 12 #11).
    """

    id: str
    expected_kind: str  # open-world, KNOWN_EXPECTED_INFORMATION_KINDS
    description: str
    created_at: str
    created_by: str
    status: str = EXPECTATION_ITEM_STATUS_ACTIVE
    applicability: Optional[str] = None
    expected_maturity: Optional[str] = None
    bindingness: str = EXPECTATION_BINDINGNESS_EXPECTED
    authority_source: Optional[str] = None
    expected_provider: Optional[str] = None
    milestone_trigger_id: Optional[str] = None
    related_object_type: Optional[str] = None
    related_object_id: Optional[str] = None


@dataclass
class ExpectedInformationProfile:
    """
    Prompt 12 #1/#2: what information would reasonably be expected, at
    what maturity, for a particular governed project context. An
    expectation/reference structure - NOT project truth. Deliberately
    scoped (scope_type/scope_id, open-world object kind - typically
    "project"/"discipline"/"package") rather than one global project-wide
    template: a project may hold many of these simultaneously, one per
    discipline/package, each independently revisable.

    Revision is non-destructive (see revise_expected_information_profile):
    a governed correction supersedes the whole profile via the shared
    Supersession primitive, exactly like Source revision - the original
    remains historically reconstructable.
    """

    id: str
    project_id: str
    title: str
    scope_type: str  # open-world object kind
    scope_id: str
    created_at: str
    created_by: str
    status: str = PROFILE_STATUS_ACTIVE
    items: list[dict] = field(default_factory=list)  # list of asdict(ExpectationItem)
    authority_context: Optional[str] = None


@dataclass
class MaturityRecord:
    """
    Prompt 12 #5/#6: DesignMaturity and EstimateMaturity share this one
    shape (scope + open-world value + provenance), distinguished only by
    `maturity_type` - a closed, structural distinction (design vs
    estimate), never conflated or inferred from one another. Scoped the
    same way ExpectedInformationProfile is, so a project can hold many
    (architecture=60%, structure=90%, mechanical=30%, simultaneously) -
    there is no single global project percentage anywhere in this model.

    Revision is non-destructive (see revise_maturity) via Supersession,
    same as everything else that changes over a project's life.
    """

    id: str
    project_id: str
    maturity_type: str  # KNOWN_MATURITY_TYPES
    scope_type: str  # open-world object kind
    scope_id: str
    value: str  # open-world, normalized against KNOWN_DESIGN_MATURITY_STAGES or KNOWN_ESTIMATE_BASIS_VALUES
    created_at: str
    created_by: str
    status: str = MATURITY_STATUS_ACTIVE
    effective_at: Optional[str] = None


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
    review_threads: list[dict] = field(default_factory=list)
    review_messages: list[dict] = field(default_factory=list)
    attentions: list[dict] = field(default_factory=list)
    expected_information_profiles: list[dict] = field(default_factory=list)
    maturity_records: list[dict] = field(default_factory=list)
    requirements: list[dict] = field(default_factory=list)


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

    def add_source(
        self,
        workspace: ProjectWorkspace,
        name: str,
        file_path: str,
        kind: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        document_id: Optional[str] = None,
        revision: Optional[str] = None,
        issue_date: Optional[str] = None,
        issuer: Optional[str] = None,
        document_status: Optional[str] = None,
        document_authority: Optional[str] = None,
        file_hash: Optional[str] = None,
        origin_type: Optional[str] = None,
        origin_reference: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
        actor: str = "system",
    ) -> dict:
        """
        Prompt 15: the general Source-registration mechanism, not limited
        to drawings (width/height are optional here). `add_drawing_source`
        below is now a thin wrapper kept for its existing callers/route.
        This is the method a non-drawing document (an OPR text document,
        a schedule, any non-image Source) should call directly, instead
        of constructing a Source dataclass by hand the way the NREOCRC
        ingestion lab script previously had to (a gap this batch closes).
        """
        source = Source(
            id=_new_id(),
            project_id=workspace.project_id,
            kind=kind,
            name=name,
            added_at=_now(),
            file_path=file_path,
            width=width,
            height=height,
            document_id=document_id,
            revision=revision,
            issue_date=issue_date,
            issuer=issuer,
            document_status=document_status,
            document_authority=(
                normalize_open_world_value(document_authority, KNOWN_DOCUMENT_AUTHORITY_LEVELS)
                if document_authority is not None else None
            ),
            file_hash=file_hash,
            origin_type=(
                normalize_open_world_value(origin_type, KNOWN_SOURCE_ORIGIN_TYPES)
                if origin_type is not None else None
            ),
            origin_reference=origin_reference,
        )
        workspace.sources.append(asdict(source))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="source_registered",
                actor=actor, role="system",
                payload={"source_id": source.id, "kind": kind, "document_id": document_id},
                correlation_id=source.id,
            )
        return asdict(source)

    def add_drawing_source(
        self,
        workspace: ProjectWorkspace,
        name: str,
        file_path: str,
        width: int,
        height: int,
        document_id: Optional[str] = None,
        revision: Optional[str] = None,
        issue_date: Optional[str] = None,
        issuer: Optional[str] = None,
        document_status: Optional[str] = None,
        document_authority: Optional[str] = None,
        file_hash: Optional[str] = None,
        origin_type: Optional[str] = None,
        origin_reference: Optional[str] = None,
    ) -> dict:
        return self.add_source(
            workspace, name=name, file_path=file_path, kind=SOURCE_KIND_DRAWING,
            width=width, height=height, document_id=document_id, revision=revision,
            issue_date=issue_date, issuer=issuer, document_status=document_status,
            document_authority=document_authority, file_hash=file_hash,
            origin_type=origin_type, origin_reference=origin_reference,
        )

    def update_source_identity(
        self,
        workspace: ProjectWorkspace,
        source_id: str,
        actor: str,
        document_id: Optional[str] = None,
        revision: Optional[str] = None,
        issue_date: Optional[str] = None,
        issuer: Optional[str] = None,
        document_status: Optional[str] = None,
        document_authority: Optional[str] = None,
        file_hash: Optional[str] = None,
        origin_type: Optional[str] = None,
        origin_reference: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Backfills/corrects document-identity metadata on an already-
        registered Source (e.g. metadata that arrives after the file
        itself was uploaded). Only supplied fields are changed - honest
        absence is preserved for anything left None.
        """
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        if document_id is not None:
            source["document_id"] = document_id
        if revision is not None:
            source["revision"] = revision
        if issue_date is not None:
            source["issue_date"] = issue_date
        if issuer is not None:
            source["issuer"] = issuer
        if document_status is not None:
            source["document_status"] = document_status
        if document_authority is not None:
            source["document_authority"] = normalize_open_world_value(document_authority, KNOWN_DOCUMENT_AUTHORITY_LEVELS)
        if file_hash is not None:
            source["file_hash"] = file_hash
        if origin_type is not None:
            source["origin_type"] = normalize_open_world_value(origin_type, KNOWN_SOURCE_ORIGIN_TYPES)
        if origin_reference is not None:
            source["origin_reference"] = origin_reference

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="source_identity_updated",
                actor=actor, role="system", payload={"source_id": source_id},
                correlation_id=source_id,
            )
        return source

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

    # -- Requirement (Prompt 15) --------------------------------------------------------

    def register_requirement(
        self,
        workspace: ProjectWorkspace,
        source_id: str,
        original_requirement_identifier: str,
        text_reference: str,
        created_by: str,
        registration_method: str,
        classification: Optional[str] = None,
        authority_source: Optional[str] = None,
        applicability: Optional[str] = None,
        subject_domain: Optional[str] = None,
        title: Optional[str] = None,
        source_location: Optional[dict] = None,
        effective_context: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Registers a source-stated Requirement - project meaning that
        exists independently of any Finding (Prompt 14/15 #1). Requires an
        honest `registration_method` (KNOWN_REQUIREMENT_REGISTRATION_
        METHODS) rather than defaulting one, so a caller can never be
        silent about whether this was actually machine-extracted or
        hand-registered as a test fixture.
        """
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if registration_method not in KNOWN_REQUIREMENT_REGISTRATION_METHODS:
            raise CaseWorkspaceError(
                f"'{registration_method}' is not a recognized Requirement registration "
                f"method. Use one of: {', '.join(KNOWN_REQUIREMENT_REGISTRATION_METHODS)}."
            )
        if source_location is not None and "location_type" in source_location:
            source_location = dict(source_location)
            source_location["location_type"] = normalize_open_world_value(
                source_location["location_type"], KNOWN_REQUIREMENT_LOCATION_TYPES
            )

        requirement = Requirement(
            id=_new_id(),
            project_id=workspace.project_id,
            source_id=source_id,
            original_requirement_identifier=original_requirement_identifier,
            text_reference=text_reference,
            created_at=_now(),
            created_by=created_by,
            registration_method=registration_method,
            classification=(
                normalize_open_world_value(classification, KNOWN_REQUIREMENT_CLASSIFICATIONS)
                if classification is not None else None
            ),
            authority_source=authority_source,
            applicability=applicability,
            subject_domain=subject_domain,
            title=title,
            source_location=source_location,
            effective_context=effective_context,
        )
        workspace.requirements.append(asdict(requirement))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="requirement_registered",
                actor=created_by, role="system",
                payload={
                    "requirement_id": requirement.id, "source_id": source_id,
                    "original_requirement_identifier": original_requirement_identifier,
                    "registration_method": registration_method,
                },
                correlation_id=requirement.id,
            )
        return asdict(requirement)

    def requirements_for_source(self, workspace: ProjectWorkspace, source_id: str) -> list[dict]:
        return [r for r in workspace.requirements if r["source_id"] == source_id]

    def requirements_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.requirements)

    def set_requirement_status(
        self, workspace: ProjectWorkspace, requirement_id: str, status: str, actor: str,
    ) -> dict:
        """
        For lifecycle transitions other than supersession (which only
        revise_requirement sets, since it is tied to lineage) - e.g.
        withdrawn, future_effective, unknown.

        Deliberately narrow exception to the general Open-World rule of
        never rejecting an unfamiliar value (Prompt 15 #17): a compliance
        outcome is not a Requirement lifecycle state under any
        circumstance, so a status that is obviously compliance-shaped is
        rejected outright here rather than silently preserved as an
        "extension value" the way a genuinely novel lifecycle state would
        be. This mirrors the existing precedent that `supersedes` is
        reserved exclusively for lineage and is never an ordinary
        Relationship type - a hard constitutional line, not everything
        being open-world all the time.
        """
        requirement = self._find(workspace.requirements, requirement_id)
        if requirement is None:
            raise CaseWorkspaceError(f"Requirement {requirement_id} was not found.")

        normalized_check = status.strip().lower().replace("-", "_").replace(" ", "_")
        if normalized_check in _REQUIREMENT_STATUS_COMPLIANCE_DENYLIST:
            raise CaseWorkspaceError(
                f"'{status}' is a compliance outcome, not a Requirement lifecycle state "
                "(Prompt 15 #17). Compliance is an Analysis/Finding/Pass/Human Adjudication "
                "result - record it there, never as this Requirement's own status."
            )

        requirement["status"] = normalize_open_world_value(status, KNOWN_REQUIREMENT_STATUSES)
        self.save(workspace)
        return requirement

    def revise_requirement(
        self,
        workspace: ProjectWorkspace,
        requirement_id: str,
        actor: str,
        reason: Optional[str] = None,
        authority_class: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
        **overrides,
    ) -> tuple[dict, dict]:
        """
        Non-destructive revision (Prompt 15 #16): creates a new
        Requirement as successor via the shared Supersession primitive -
        the same pattern as Source/TemporalObligation/ExpectedInformation
        Profile revision, not a new mechanism. `overrides` may supply any
        of the optional Requirement fields to change on the successor
        (e.g. `classification=...`, `text_reference=...`); anything not
        overridden carries forward unchanged from the predecessor. An
        Addendum amending/qualifying/superseding an earlier requirement is
        exactly this call - no special Addendum workflow is built.
        """
        old = self._find(workspace.requirements, requirement_id)
        if old is None:
            raise CaseWorkspaceError(f"Requirement {requirement_id} was not found.")

        new_requirement = Requirement(
            id=_new_id(),
            project_id=workspace.project_id,
            source_id=overrides.get("source_id", old["source_id"]),
            original_requirement_identifier=overrides.get(
                "original_requirement_identifier", old["original_requirement_identifier"]
            ),
            text_reference=overrides.get("text_reference", old["text_reference"]),
            created_at=_now(),
            created_by=actor,
            registration_method=overrides.get("registration_method", old["registration_method"]),
            classification=overrides.get("classification", old["classification"]),
            authority_source=overrides.get("authority_source", old["authority_source"]),
            applicability=overrides.get("applicability", old["applicability"]),
            subject_domain=overrides.get("subject_domain", old["subject_domain"]),
            title=overrides.get("title", old["title"]),
            source_location=overrides.get("source_location", old["source_location"]),
            effective_context=overrides.get("effective_context", old["effective_context"]),
        )
        workspace.requirements.append(asdict(new_requirement))
        old["status"] = REQUIREMENT_STATUS_SUPERSEDED

        supersession = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=OBJECT_KIND_REQUIREMENT,
            predecessor_id=requirement_id,
            successor_type=OBJECT_KIND_REQUIREMENT,
            successor_id=new_requirement.id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
            authority_class=authority_class,
        )
        workspace.supersessions.append(asdict(supersession))

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="requirement_superseded",
                actor=actor, role="system",
                payload={"predecessor_id": requirement_id, "successor_id": new_requirement.id, "reason": reason},
                correlation_id=supersession.id,
            )
        return asdict(new_requirement), asdict(supersession)

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

    # -- Review Threads (Prompt 10) ----------------------------------------------------
    #
    # No route/UI calls any of this yet (Prompt 10 is backend/domain
    # foundation only) - mutating methods below accept an optional
    # `governance_log` parameter and log directly when given, the same
    # way services/project_clock.py logs its own events, rather than
    # requiring a route layer that does not exist yet.

    def create_review_thread(
        self,
        workspace: ProjectWorkspace,
        title: str,
        anchor_type: str,
        anchor_id: str,
        created_by: str,
        case_id: Optional[str] = None,
        anchor_source_id: Optional[str] = None,
        anchor_location: Optional[dict] = None,
        anchor_description: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        anchor = Anchor(
            anchor_type=normalize_open_world_value(anchor_type, KNOWN_OBJECT_KINDS),
            anchor_id=anchor_id,
            source_id=anchor_source_id,
            location=anchor_location,
            description=anchor_description,
        )
        thread = ReviewThread(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            anchor=asdict(anchor),
            created_at=_now(),
            created_by=created_by,
            case_id=case_id,
        )
        workspace.review_threads.append(asdict(thread))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_thread_created",
                actor=created_by,
                role="system",
                payload={
                    "thread_id": thread.id,
                    "anchor_type": anchor.anchor_type,
                    "anchor_id": anchor_id,
                    "case_id": case_id,
                },
                correlation_id=thread.id,
            )
        return asdict(thread)

    def threads_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.review_threads)

    def threads_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [t for t in workspace.review_threads if t.get("case_id") == case_id]

    def threads_for_anchor(self, workspace: ProjectWorkspace, anchor_type: str, anchor_id: str) -> list[dict]:
        anchor_type = normalize_open_world_value(anchor_type, KNOWN_OBJECT_KINDS)
        return [
            t for t in workspace.review_threads
            if t["anchor"]["anchor_type"] == anchor_type and t["anchor"]["anchor_id"] == anchor_id
        ]

    def add_review_message(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        origin: str,
        actor: str,
        message_type: str,
        text: str,
        reply_to_message_id: Optional[str] = None,
        related_object_type: Optional[str] = None,
        related_object_id: Optional[str] = None,
        related_analysis_id: Optional[str] = None,
        related_finding_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")
        if origin not in KNOWN_MESSAGE_ORIGINS:
            raise CaseWorkspaceError(
                f"'{origin}' is not a recognized message origin. Use one of: {', '.join(KNOWN_MESSAGE_ORIGINS)}."
            )

        message = ReviewMessage(
            id=_new_id(),
            thread_id=thread_id,
            project_id=workspace.project_id,
            origin=origin,
            actor=actor,
            message_type=normalize_open_world_value(message_type, KNOWN_MESSAGE_TYPES),
            text=text,
            created_at=_now(),
            reply_to_message_id=reply_to_message_id,
            related_object_type=(
                normalize_open_world_value(related_object_type, KNOWN_OBJECT_KINDS)
                if related_object_type is not None else None
            ),
            related_object_id=related_object_id,
            related_analysis_id=related_analysis_id,
            related_finding_id=related_finding_id,
            project_state_version=workspace.version,
        )
        workspace.review_messages.append(asdict(message))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_message_added",
                actor=actor,
                role="system",
                payload={"thread_id": thread_id, "message_id": message.id, "origin": origin},
                correlation_id=message.id,
            )
        return asdict(message)

    def messages_for_thread(self, workspace: ProjectWorkspace, thread_id: str) -> list[dict]:
        return [m for m in workspace.review_messages if m["thread_id"] == thread_id]

    def request_attention(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        message_id: str,
        intended_actor: str,
        created_by: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Attention means "this person/role should attend to this matter" -
        nothing more (Prompt 10 #4). It never creates contractual
        responsibility, requirement ownership, approval authority, or a
        Work Item - none of those exist as a side effect here, or at all
        in this batch. The only structural side effect is the thread
        moving to WAITING_FOR_RESPONSE if it was OPEN/UNDER_REVIEW - a
        deterministic, explicit rule, not an inferred one.
        """
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")

        attention = Attention(
            id=_new_id(),
            thread_id=thread_id,
            project_id=workspace.project_id,
            message_id=message_id,
            intended_actor=intended_actor,
            created_by=created_by,
            created_at=_now(),
        )
        workspace.attentions.append(asdict(attention))

        if thread["status"] in (THREAD_STATUS_OPEN, THREAD_STATUS_UNDER_REVIEW):
            thread["status"] = THREAD_STATUS_WAITING_FOR_RESPONSE

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_attention_requested",
                actor=created_by,
                role="system",
                payload={"thread_id": thread_id, "attention_id": attention.id, "intended_actor": intended_actor},
                correlation_id=attention.id,
            )
        return asdict(attention)

    def attentions_for_thread(self, workspace: ProjectWorkspace, thread_id: str) -> list[dict]:
        return [a for a in workspace.attentions if a["thread_id"] == thread_id]

    def respond_to_attention(
        self,
        workspace: ProjectWorkspace,
        attention_id: str,
        response_message_id: str,
    ) -> dict:
        attention = self._find(workspace.attentions, attention_id)
        if attention is None:
            raise CaseWorkspaceError(f"Attention {attention_id} was not found.")

        attention["status"] = ATTENTION_STATUS_RESPONDED
        attention["responded_message_id"] = response_message_id

        thread = self._find(workspace.review_threads, attention["thread_id"])
        if thread is not None and thread["status"] == THREAD_STATUS_WAITING_FOR_RESPONSE:
            thread["status"] = THREAD_STATUS_UNDER_REVIEW

        self.save(workspace)
        return attention

    def set_review_thread_status(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        status: str,
        actor: str,
    ) -> dict:
        """Explicit, deterministic status transitions for states that
        aren't a side effect of a more specific action (e.g.
        WAITING_FOR_EVIDENCE) - never inferred from message content."""
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")
        thread["status"] = normalize_open_world_value(status, KNOWN_THREAD_STATUSES)
        self.save(workspace)
        return thread

    def resolve_review_thread(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        resolution_outcome: str,
        summary: str,
        resolved_by: str,
        related_evidence_refs: Optional[list[dict]] = None,
        authority_context: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Additive (Prompt 10 #6): sets thread.resolution and status -
        never touches a single existing ReviewMessage. The conversation
        remains available exactly as written."""
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")
        if thread["status"] in (THREAD_STATUS_RESOLVED, THREAD_STATUS_CLOSED):
            raise CaseWorkspaceError(
                f"Review Thread {thread_id} is already {thread['status']} - reopen it before resolving again."
            )

        resolution = ThreadResolution(
            resolution_outcome=normalize_open_world_value(resolution_outcome, KNOWN_RESOLUTION_OUTCOMES),
            summary=summary,
            resolved_by=resolved_by,
            resolved_at=_now(),
            related_evidence_refs=related_evidence_refs or [],
            authority_context=authority_context,
        )
        thread["resolution"] = asdict(resolution)
        thread["status"] = THREAD_STATUS_RESOLVED

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_thread_resolved",
                actor=resolved_by,
                role="system",
                payload={"thread_id": thread_id, "resolution_outcome": resolution.resolution_outcome},
                correlation_id=thread_id,
            )
        return thread

    def reopen_review_thread(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        reason: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Never erases the prior resolution (Prompt 10 #5/#13): it is
        pushed onto resolution_history, timestamped and attributed, and
        only THEN is thread.resolution cleared to make room for a new
        one. The original discussion, the original resolution, and the
        reopening itself all remain independently reconstructable.
        """
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")
        if thread["status"] not in (THREAD_STATUS_RESOLVED, THREAD_STATUS_CLOSED):
            raise CaseWorkspaceError(f"Review Thread {thread_id} is not resolved/closed - nothing to reopen.")

        thread["resolution_history"].append({
            "resolution": thread["resolution"],
            "reopened_at": _now(),
            "reopened_by": actor,
            "reopen_reason": reason,
        })
        thread["resolution"] = None
        thread["status"] = THREAD_STATUS_REOPENED

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_thread_reopened",
                actor=actor,
                role="system",
                payload={"thread_id": thread_id, "reason": reason},
                correlation_id=thread_id,
            )
        return thread

    def confirm_relationship(self, workspace: ProjectWorkspace, relationship_id: str, actor: str) -> dict:
        """Standalone confirmation for direct use outside a thread outcome
        context - see link_thread_outcome for the atomic, in-transaction
        version used when confirming as part of resolving a thread."""
        relationship = self._find(workspace.relationships, relationship_id)
        if relationship is None:
            raise CaseWorkspaceError(f"Relationship {relationship_id} was not found.")
        relationship["provisional"] = False
        relationship["confirmed_by"] = actor
        self.save(workspace)
        return relationship

    def link_thread_outcome(
        self,
        workspace: ProjectWorkspace,
        thread_id: str,
        outcome_type: str,
        actor: str,
        object_type: Optional[str] = None,
        object_id: Optional[str] = None,
        confirm_relationship_id: Optional[str] = None,
        reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Structured outcome linkage (Prompt 10 #7) - never automatic;
        always an explicit call alongside/after resolve_review_thread.
        Reuses the existing typed Relationship substrate rather than a
        new outcome-link mechanism: when object_type/object_id are given,
        records a Relationship(relationship_type="resulted_in") from the
        thread to that governed object. confirm_relationship_id lets a
        resolution mark an existing provisional Relationship (e.g. the
        original departs_from) as no longer merely provisional - this is
        how "Relationship confirmed" as an outcome is represented, with
        no new field beyond what Relationship already had since Batch B.

        Everything here - the new Relationship (if any), the confirmation
        (if any), and the outcome_ref record - happens on the same
        in-memory workspace mutation before the single save() call at the
        end, so they commit atomically together (never a Relationship
        created without its outcome_ref, or vice versa).
        """
        thread = self._find(workspace.review_threads, thread_id)
        if thread is None:
            raise CaseWorkspaceError(f"Review Thread {thread_id} was not found.")

        relationship_id = None
        if object_type is not None and object_id is not None:
            relationship = Relationship(
                id=_new_id(),
                project_id=workspace.project_id,
                from_type=OBJECT_KIND_REVIEW_THREAD,
                from_id=thread_id,
                to_type=normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS),
                to_id=object_id,
                relationship_type=RELATIONSHIP_TYPE_RESULTED_IN,
                created_at=_now(),
                created_by=actor,
                provisional=False,
            )
            workspace.relationships.append(asdict(relationship))
            relationship_id = relationship.id

        if confirm_relationship_id is not None:
            confirmed = self._find(workspace.relationships, confirm_relationship_id)
            if confirmed is None:
                raise CaseWorkspaceError(f"Relationship {confirm_relationship_id} was not found.")
            confirmed["provisional"] = False
            confirmed["confirmed_by"] = actor

        outcome_ref = {
            "outcome_type": outcome_type,
            "object_type": object_type,
            "object_id": object_id,
            "relationship_id": relationship_id,
            "confirmed_relationship_id": confirm_relationship_id,
            "reason": reason,
            "linked_by": actor,
            "linked_at": _now(),
        }
        thread["outcome_refs"].append(outcome_ref)

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="review_thread_outcome_linked",
                actor=actor,
                role="system",
                payload={
                    "thread_id": thread_id,
                    "outcome_type": outcome_type,
                    "object_type": object_type,
                    "object_id": object_id,
                },
                correlation_id=thread_id,
            )
        return thread

    # -- Expected Information Profile / Maturity (Prompt 11/12) -----------------------
    #
    # Same convention as Review Threads: no route/UI calls any of this yet
    # (backend/domain foundation only) - mutating methods accept an
    # optional `governance_log` and log directly when given.

    def create_expected_information_profile(
        self,
        workspace: ProjectWorkspace,
        title: str,
        scope_type: str,
        scope_id: str,
        created_by: str,
        authority_context: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        profile = ExpectedInformationProfile(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            scope_type=normalize_open_world_value(scope_type, KNOWN_OBJECT_KINDS),
            scope_id=scope_id,
            created_at=_now(),
            created_by=created_by,
            authority_context=authority_context,
        )
        workspace.expected_information_profiles.append(asdict(profile))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="expected_information_profile_created",
                actor=created_by,
                role="system",
                payload={"profile_id": profile.id, "scope_type": profile.scope_type, "scope_id": scope_id},
                correlation_id=profile.id,
            )
        return asdict(profile)

    def add_expectation_item(
        self,
        workspace: ProjectWorkspace,
        profile_id: str,
        expected_kind: str,
        description: str,
        created_by: str,
        bindingness: str = EXPECTATION_BINDINGNESS_EXPECTED,
        authority_source: Optional[str] = None,
        applicability: Optional[str] = None,
        expected_maturity: Optional[str] = None,
        expected_provider: Optional[str] = None,
        milestone_trigger_id: Optional[str] = None,
        related_object_type: Optional[str] = None,
        related_object_id: Optional[str] = None,
    ) -> dict:
        profile = self._find(workspace.expected_information_profiles, profile_id)
        if profile is None:
            raise CaseWorkspaceError(f"Expected Information Profile {profile_id} was not found.")
        if bindingness not in KNOWN_EXPECTATION_BINDINGNESS:
            raise CaseWorkspaceError(
                f"'{bindingness}' is not a recognized expectation bindingness. "
                f"Use one of: {', '.join(KNOWN_EXPECTATION_BINDINGNESS)}."
            )

        item = ExpectationItem(
            id=_new_id(),
            expected_kind=normalize_open_world_value(expected_kind, KNOWN_EXPECTED_INFORMATION_KINDS),
            description=description,
            created_at=_now(),
            created_by=created_by,
            applicability=applicability,
            expected_maturity=expected_maturity,
            bindingness=bindingness,
            authority_source=authority_source,
            expected_provider=expected_provider,
            milestone_trigger_id=milestone_trigger_id,
            related_object_type=(
                normalize_open_world_value(related_object_type, KNOWN_OBJECT_KINDS)
                if related_object_type is not None else None
            ),
            related_object_id=related_object_id,
        )
        profile["items"].append(asdict(item))
        self.save(workspace)
        return asdict(item)

    def set_expectation_item_status(
        self,
        workspace: ProjectWorkspace,
        profile_id: str,
        item_id: str,
        status: str,
        actor: str,
    ) -> dict:
        profile = self._find(workspace.expected_information_profiles, profile_id)
        if profile is None:
            raise CaseWorkspaceError(f"Expected Information Profile {profile_id} was not found.")
        item = self._find(profile["items"], item_id)
        if item is None:
            raise CaseWorkspaceError(f"Expectation Item {item_id} was not found.")
        item["status"] = normalize_open_world_value(status, KNOWN_EXPECTATION_ITEM_STATUSES)
        self.save(workspace)
        return item

    def profiles_for_scope(self, workspace: ProjectWorkspace, scope_type: str, scope_id: str) -> list[dict]:
        """Active profiles only - superseded/withdrawn profiles remain in
        workspace.expected_information_profiles for historical reconstruction
        (see supersessions_for) but are not "currently governing"."""
        scope_type = normalize_open_world_value(scope_type, KNOWN_OBJECT_KINDS)
        return [
            p for p in workspace.expected_information_profiles
            if p["scope_type"] == scope_type and p["scope_id"] == scope_id and p["status"] == PROFILE_STATUS_ACTIVE
        ]

    def profiles_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.expected_information_profiles)

    def revise_expected_information_profile(
        self,
        workspace: ProjectWorkspace,
        profile_id: str,
        actor: str,
        reason: Optional[str] = None,
        authority_class: Optional[str] = None,
        new_title: Optional[str] = None,
        new_items: Optional[list[dict]] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> tuple[dict, dict]:
        """
        Prompt 12 #12/#13: non-destructive governed correction - creates a
        successor profile via the shared Supersession primitive rather
        than mutating the original. This is exactly the mechanism for a
        project-specific override (Prompt 12 #13/Test P): the generic/
        default profile is superseded by a new one carrying the corrected
        items, with `reason`/`authority_class` recording who authorized
        the change and why - the original remains fully reconstructable.
        """
        old = self._find(workspace.expected_information_profiles, profile_id)
        if old is None:
            raise CaseWorkspaceError(f"Expected Information Profile {profile_id} was not found.")

        new_profile = ExpectedInformationProfile(
            id=_new_id(),
            project_id=workspace.project_id,
            title=new_title if new_title is not None else old["title"],
            scope_type=old["scope_type"],
            scope_id=old["scope_id"],
            created_at=_now(),
            created_by=actor,
            items=new_items if new_items is not None else [dict(i) for i in old["items"]],
            authority_context=old.get("authority_context"),
        )
        workspace.expected_information_profiles.append(asdict(new_profile))
        old["status"] = PROFILE_STATUS_SUPERSEDED

        supersession = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=OBJECT_KIND_EXPECTED_INFORMATION_PROFILE,
            predecessor_id=profile_id,
            successor_type=OBJECT_KIND_EXPECTED_INFORMATION_PROFILE,
            successor_id=new_profile.id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
            authority_class=authority_class,
        )
        workspace.supersessions.append(asdict(supersession))

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="expected_information_profile_revised",
                actor=actor,
                role="system",
                payload={"predecessor_id": profile_id, "successor_id": new_profile.id, "reason": reason},
                correlation_id=supersession.id,
            )
        return asdict(new_profile), asdict(supersession)

    # -- Design / Estimate Maturity (Prompt 11/12) --------------------------------------

    def record_design_maturity(
        self,
        workspace: ProjectWorkspace,
        scope_type: str,
        scope_id: str,
        value: str,
        created_by: str,
        effective_at: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        return self._record_maturity(workspace, MATURITY_TYPE_DESIGN, scope_type, scope_id, value, created_by, effective_at, governance_log)

    def record_estimate_maturity(
        self,
        workspace: ProjectWorkspace,
        scope_type: str,
        scope_id: str,
        value: str,
        created_by: str,
        effective_at: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        return self._record_maturity(workspace, MATURITY_TYPE_ESTIMATE, scope_type, scope_id, value, created_by, effective_at, governance_log)

    def _record_maturity(
        self,
        workspace: ProjectWorkspace,
        maturity_type: str,
        scope_type: str,
        scope_id: str,
        value: str,
        created_by: str,
        effective_at: Optional[str],
        governance_log: Optional[GovernanceLog],
    ) -> dict:
        known_values = KNOWN_DESIGN_MATURITY_STAGES if maturity_type == MATURITY_TYPE_DESIGN else KNOWN_ESTIMATE_BASIS_VALUES
        record = MaturityRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            maturity_type=maturity_type,
            scope_type=normalize_open_world_value(scope_type, KNOWN_OBJECT_KINDS),
            scope_id=scope_id,
            value=normalize_open_world_value(value, known_values),
            created_at=_now(),
            created_by=created_by,
            effective_at=effective_at,
        )
        workspace.maturity_records.append(asdict(record))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="maturity_recorded",
                actor=created_by,
                role="system",
                payload={
                    "maturity_id": record.id, "maturity_type": maturity_type,
                    "scope_type": record.scope_type, "scope_id": scope_id, "value": record.value,
                },
                correlation_id=record.id,
            )
        return asdict(record)

    def maturity_for_scope(
        self, workspace: ProjectWorkspace, maturity_type: str, scope_type: str, scope_id: str,
    ) -> Optional[dict]:
        """Latest ACTIVE record for this exact type+scope - superseded
        records remain in workspace.maturity_records for history but are
        not "current" (Prompt 12 #5: no single global project percentage;
        every scope is looked up independently)."""
        scope_type = normalize_open_world_value(scope_type, KNOWN_OBJECT_KINDS)
        matches = [
            m for m in workspace.maturity_records
            if m["maturity_type"] == maturity_type
            and m["scope_type"] == scope_type
            and m["scope_id"] == scope_id
            and m["status"] == MATURITY_STATUS_ACTIVE
        ]
        return matches[-1] if matches else None

    def revise_maturity(
        self,
        workspace: ProjectWorkspace,
        maturity_record_id: str,
        new_value: str,
        actor: str,
        reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> tuple[dict, dict]:
        old = self._find(workspace.maturity_records, maturity_record_id)
        if old is None:
            raise CaseWorkspaceError(f"Maturity record {maturity_record_id} was not found.")

        known_values = KNOWN_DESIGN_MATURITY_STAGES if old["maturity_type"] == MATURITY_TYPE_DESIGN else KNOWN_ESTIMATE_BASIS_VALUES
        new_record = MaturityRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            maturity_type=old["maturity_type"],
            scope_type=old["scope_type"],
            scope_id=old["scope_id"],
            value=normalize_open_world_value(new_value, known_values),
            created_at=_now(),
            created_by=actor,
        )
        workspace.maturity_records.append(asdict(new_record))
        old["status"] = MATURITY_STATUS_SUPERSEDED

        supersession = Supersession(
            id=_new_id(),
            project_id=workspace.project_id,
            predecessor_type=OBJECT_KIND_MATURITY_RECORD,
            predecessor_id=maturity_record_id,
            successor_type=OBJECT_KIND_MATURITY_RECORD,
            successor_id=new_record.id,
            actor=actor,
            authorized_at=_now(),
            reason=reason,
        )
        workspace.supersessions.append(asdict(supersession))

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id,
                event_type="maturity_revised",
                actor=actor,
                role="system",
                payload={"predecessor_id": maturity_record_id, "successor_id": new_record.id, "reason": reason},
                correlation_id=supersession.id,
            )
        return asdict(new_record), asdict(supersession)

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
