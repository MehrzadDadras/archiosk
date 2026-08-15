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

import hashlib
import json
import re
import threading
import uuid
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dataclass_fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from services.governance import GovernanceLog

# Every ingested RFQ/RFP document is registered as this Project's first
# Source automatically (see get_or_create) — the RFQ/RFP pipeline is the
# beginning of the same persistent Project, not a separate product.
SOURCE_KIND_RFQ_RFP_DOCUMENT = "rfq_rfp_document"
SOURCE_KIND_DRAWING = "drawing"
# Prompt 3 (Project Home): a non-drawing document added directly as a
# Project Source (not tied to any one Case - see add_source) and a
# first-class textual evidence record (meeting note, site observation,
# telephone instruction, pasted requirement, etc.) - both open-world
# strings like every other Source.kind, not validated against a closed
# list, exactly like SOURCE_KIND_DRAWING already is.
SOURCE_KIND_PROJECT_DOCUMENT = "project_document"
SOURCE_KIND_TEXT_RECORD = "text_record"

# CLAUDE-P40-VW9 (Governed Files Display and Project File Architecture):
# a Folder's `root` names which of the two GOVERNED SIBLING ROOTS it
# belongs to - Data Room (controlled, externally-issued material) and
# Design-Builder Workspace (editable, team-organized material) are
# different governance spaces, not two flavors of the same thing a
# future stage might casually extend, so this is a closed tuple
# (validated below), not open-world like SOURCE_KIND_* above. Both
# roots are GOVERNED VIRTUAL roots this stage - neither is itself a
# persisted Folder record; a project's `workspace.folders` list holds
# only real, user-created folders, and every one of them this stage
# ever creates has root=FOLDER_ROOT_DESIGN_BUILDER (no route or method
# below accepts FOLDER_ROOT_DATA_ROOM as a creation target - see
# create_folder's own docstring). FOLDER_ROOT_DATA_ROOM exists as a
# named, honest placeholder for the future issued-hierarchy import,
# not a hidden half-built feature.
FOLDER_ROOT_DATA_ROOM = "data_room"
FOLDER_ROOT_DESIGN_BUILDER = "design_builder"
KNOWN_FOLDER_ROOTS = (FOLDER_ROOT_DATA_ROOM, FOLDER_ROOT_DESIGN_BUILDER)

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

# -- Requirement Adjudication vocabulary (Prompt 19 / Foundation Batch K) ---
# The human REQUIREMENT-level compliance record - a distinct question from
# Disposition above ("what happens to this Finding next") and from
# Requirement.status below (existence/lifecycle only, hard-walled off from
# compliance language by _REQUIREMENT_STATUS_COMPLIANCE_DENYLIST). A
# deliberately small, closed vocabulary - not every candidate outcome word
# gets its own state: "Needs Evidence" is omitted (it already exists as a
# ReviewerValidation state on the underlying Finding; an adjudicator who
# lacks evidence simply does not adjudicate yet) and "Superseded" is
# omitted (already carried by Requirement.status/Supersession lineage - a
# new adjudication is recorded against the successor Requirement instead
# of inventing a second way to say the same thing here).
REQUIREMENT_ADJUDICATION_SATISFIED = "Satisfied"
REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED = "Partially Satisfied"
REQUIREMENT_ADJUDICATION_NOT_SATISFIED = "Not Satisfied"
REQUIREMENT_ADJUDICATION_NOT_APPLICABLE = "Not Applicable"
REQUIREMENT_ADJUDICATION_ACCEPTED_ALTERNATIVE = "Accepted Alternative"

REQUIREMENT_ADJUDICATION_OUTCOMES = (
    REQUIREMENT_ADJUDICATION_SATISFIED,
    REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED,
    REQUIREMENT_ADJUDICATION_NOT_SATISFIED,
    REQUIREMENT_ADJUDICATION_NOT_APPLICABLE,
    REQUIREMENT_ADJUDICATION_ACCEPTED_ALTERNATIVE,
)

# Derived-only (never stored) - see requirement_adjudication_state below.
# Mirrors REVIEW_STATE_UNVERIFIED's own derived-absence pattern: a
# Requirement with no RequirementAdjudication record on file has no row
# saying so, just this computed answer.
REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED = "Not Yet Assessed"

# CLAUDE-POSTCAMEL-COMM-I5A: content-provenance for RequirementAdjudication
# (OPR-5.3's own corrective tranche). RequirementAdjudication's own
# docstring has always called this object "a human's answer", but until
# this addition nothing on the record itself distinguished a personally-
# formed human judgment from an agent/automation's assessment entered
# through the same real route - both were structurally identical, a
# username and free text. These two are the only real INPUT choices a
# caller may declare; UNKNOWN_LEGACY is a DERIVED label only (see
# resolve_requirement_adjudication_attribution below), mirroring
# REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED's own
# derived-never-stored pattern - a record predating this field is never
# silently relabeled as either real choice.
ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED = "human_reviewed"
ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT = "agent_assessment"
ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY = "unknown_legacy"

KNOWN_ADJUDICATION_ATTRIBUTIONS = (
    ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED,
    ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT,
)

# The four RequirementAdjudication records CLAUDE-POSTCAMEL-COMM-I3
# created against the real ARCHIOSK commissioning specimen, before this
# field existed. Never mutated to add attribution retroactively -
# ADR-032-R06's "human-adjudication-as-evidence", append-only,
# never-overwrite principle applies to this addition too, not only to
# outcome/reasoning/timestamp. Their agent origin is instead truthfully
# resolved BY REFERENCE, directly evidenced by
# governance/current/comm-i3-first-developmental-commissioning-tranche.md
# (commit 678c692) and this session's own contemporaneous script output
# recording exactly these ids at the moment they were created.
LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS = frozenset({
    "4e5d2482-3219-4df4-a3b2-e23666dd8f99",
    "6e7680a5-abf8-4a64-a410-436a0a6a0c60",
    "5d1a7860-cbf5-4d7d-b38f-cc78afbcc43e",
    "1c93d749-5c7c-44d5-921f-8df0c03a19d5",
})


def resolve_requirement_adjudication_attribution(record: dict) -> str:
    """
    Read-time resolution only - never stored, never backfilled onto the
    record itself. A record's own `attribution` field wins if present;
    otherwise a record is checked against the small, explicit, named
    LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS reference above (never a
    guess - only these four specific, governance-documented ids ever
    resolve to agent_assessment this way); anything else predating the
    field resolves honestly to UNKNOWN_LEGACY, never defaulted to
    "human" merely because it is old.
    """
    attribution = record.get("attribution")
    if attribution:
        return attribution
    if record.get("id") in LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS:
        return ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT
    return ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY

RFI_STATUS_DRAFT = "draft"
RFI_STATUS_ISSUED = "issued"
# CLAUDE-P30: the Client/Owner-side counterpart action to issuing -- an
# issued RFI that has received its authoritative response. Terminal:
# no method transitions a draft back out of "answered".
RFI_STATUS_ANSWERED = "answered"

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

# CLAUDE-P08: InvestigationStep.step_kind vocabulary - open-world, same
# pattern as KNOWN_RELATIONSHIP_TYPES (a single dataclass shape, a kind
# label, not a family of subclasses). Exactly ONE value is ever produced
# by real code today - see InvestigationStep's own docstring for why the
# others a fuller agentic loop would eventually need (a real evidence-
# retrieval step, a real branch, a human-gate action distinct from
# ReviewerValidation) are not listed here: naming a kind before anything
# produces it would be recording a capability that doesn't exist.
INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION = "requirement_investigation"
# CLAUDE-MM7: the second real kind this vocabulary has ever needed - a
# governed investigation across the MM1-MM6 evidence/relationship graph
# (EvidenceItem/AddressableRegion/DerivedObservation/Relationship),
# distinct from INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION's own
# Requirement-only scope. Reuses InvestigationStep unchanged (same
# question/evidence_requested/evidence_examined_ids/ran/skipped_reason/
# analysis_id shape already proven by MM7's own Requirement-investigation
# precedent) - only a new `step_kind` value, no new container.
INVESTIGATION_STEP_KIND_CROSS_MODAL_INVESTIGATION = "cross_modal_investigation"
KNOWN_INVESTIGATION_STEP_KINDS = (
    INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
    INVESTIGATION_STEP_KIND_CROSS_MODAL_INVESTIGATION,
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
OBJECT_KIND_SNAPSHOT = "snapshot"  # Batch G - a frozen reference to Project state itself
OBJECT_KIND_TABLE = "table"  # Batch J - structured tabular evidence
OBJECT_KIND_TABLE_ROW = "table_row"  # Batch J
OBJECT_KIND_TABLE_CELL = "table_cell"  # Batch J
OBJECT_KIND_SOURCE_REFERENCE = "source_reference"  # Batch J
OBJECT_KIND_REQUIREMENT_ADJUDICATION = "requirement_adjudication"  # Batch K
OBJECT_KIND_REVIEW_MESSAGE = "review_message"  # Selective Adopt/Carry-Forward tranche - distinct from OBJECT_KIND_REVIEW_THREAD, since a carried-forward comment points at the specific historical message, not its whole thread
OBJECT_KIND_PARTICIPANT = "participant"  # CLAUDE-P12R - a project party (Owner/Design-Builder/Proponent/etc.), so a Relationship/Anchor can point at one like anything else
# CLAUDE-MM1: the multimodal foundation/evidence contract - a Source's
# internal structure (page/sheet/section/frame), a precise locatable
# portion of one (span/bbox/cell/crop), a piece of evidence anchored to
# either, and an interpretation built from one or more Evidence Items.
# Generalizes what OBJECT_KIND_TABLE/TABLE_ROW/TABLE_CELL already do for
# tabular content specifically (Batch J) to every modality MM2-MM9 will
# eventually extract - see StructuralUnit/AddressableRegion/EvidenceItem/
# DerivedObservation below for the real objects these name.
OBJECT_KIND_STRUCTURAL_UNIT = "structural_unit"
OBJECT_KIND_ADDRESSABLE_REGION = "addressable_region"
OBJECT_KIND_EVIDENCE_ITEM = "evidence_item"
OBJECT_KIND_DERIVED_OBSERVATION = "derived_observation"
# CLAUDE-MM6: the one genuinely missing endpoint type the cross-modal
# relationship river needs - Task already exists (ProjectWorkspace.tasks,
# CLAUDE-P40's own "real persisted project Task" - see class Task above)
# but had no OBJECT_KIND_* of its own yet, since nothing needed to POINT
# AT one generically until now (Section 8's own "...-> task, risk, RFI,
# decision..." action-chain). Risk/RFI deliberately get NO new object
# kind here - MM3's own precedent already established that a risk-
# register row is representable via the general row-region mechanism
# (OBJECT_KIND_ADDRESSABLE_REGION/EVIDENCE_ITEM), not a dedicated
# RiskRecord; an RFI is generated FROM Requirements (services/
# rfi_export.py), not itself a first-class linkable object today.
OBJECT_KIND_TASK = "task"
# CLAUDE-MM7: an inspectable analytical Claim (see class Claim below) is
# itself a governed, citable, correctable object - Supersession's third
# real consumer (after Source and Relationship), so a corrected Claim's
# own predecessor/successor pair can be recorded the same way a
# corrected Relationship already is (see supersede_claim).
OBJECT_KIND_CLAIM = "claim"
# CLAUDE-MM8: an editable, governed professional artifact (see class
# WorkProduct below) - Supersession's fourth real consumer (after Source,
# Relationship, and Claim), so a revision's own predecessor/successor pair
# is recorded the same non-destructive way. Also citable the same way a
# Claim's own evidence_links cite real objects - a report section can
# reference another WorkProduct (e.g. "based_on" an earlier risk register).
OBJECT_KIND_WORK_PRODUCT = "work_product"

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
    OBJECT_KIND_SNAPSHOT,
    OBJECT_KIND_TABLE,
    OBJECT_KIND_TABLE_ROW,
    OBJECT_KIND_TABLE_CELL,
    OBJECT_KIND_SOURCE_REFERENCE,
    OBJECT_KIND_REQUIREMENT_ADJUDICATION,
    OBJECT_KIND_REVIEW_MESSAGE,
    OBJECT_KIND_PARTICIPANT,
    OBJECT_KIND_STRUCTURAL_UNIT,
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_EVIDENCE_ITEM,
    OBJECT_KIND_DERIVED_OBSERVATION,
    OBJECT_KIND_TASK,
    OBJECT_KIND_CLAIM,
    OBJECT_KIND_WORK_PRODUCT,
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
# Case-lineage tranche: a NEW Case derived from an ARCHIVED one - structurally
# distinct from "supersedes" (Supersession implies the predecessor is no
# longer the authoritative version of the SAME thing) and from ordinary
# evidentiary edges above (this connects two Cases, not a Finding/Source/
# Requirement pair). from_id is always the new derived Case, to_id is
# always the archived source Case - see derive_case_from_archive.
RELATIONSHIP_TYPE_DERIVED_FROM = "derived_from"
# CLAUDE-MM1: the remainder of the evidence-relationship vocabulary the
# multimodal foundation needs (camel-multimodal-programme.md's MM6) -
# added to the same open-world Relationship mechanism above, not a
# second edge type. same_subject_as/compares_with are symmetric in
# meaning but still stored with one direction, like every other
# Relationship here; the caller's from/to choice is the only record of
# which side initiated the comparison.
RELATIONSHIP_TYPE_SAME_SUBJECT_AS = "same_subject_as"
RELATIONSHIP_TYPE_COMPARES_WITH = "compares_with"
RELATIONSHIP_TYPE_CALCULATED_FROM = "calculated_from"
RELATIONSHIP_TYPE_MITIGATES = "mitigates"
RELATIONSHIP_TYPE_VALIDATES = "validates"
RELATIONSHIP_TYPE_INVALIDATES = "invalidates"
RELATIONSHIP_TYPE_ASSOCIATED_WITH = "associated_with"
# CLAUDE-MM6: exactly three new types, chosen for genuine distinctness
# from everything above rather than "add every synonym from the
# governing prompt's own list" (Section 7's own explicit caution).
# Reused instead of duplicated: extracted_from/located_in -> REFERENCES;
# conflicts_with -> CONTRADICTS; coordinates_with -> SAME_SUBJECT_AS or
# COMPARES_WITH depending on the reviewer's own intent; verifies/fails_
# to_verify -> VALIDATES/INVALIDATES (already MM1's own pair for exactly
# this); resolves/supports_finding -> SUPPORTS (to_type=finding);
# assigned_to/accepted_by/rejected_by/closed_by -> deferred, no governed
# Decision/RFI/closure object exists yet for them to name honestly.
RELATIONSHIP_TYPE_OBSERVES = "observes"  # field-reality evidence (image/photo) observing a design-intent or coordination condition - Section 4's own tributary distinction, not the same claim as CORRESPONDS_TO (which makes no field-vs-design claim)
RELATIONSHIP_TYPE_DEVIATES_FROM = "deviates_from"  # a built/observed condition diverges from what a requirement or specification calls for - distinct from CONTRADICTS (evidence vs. evidence), this is condition vs. requirement
RELATIONSHIP_TYPE_REQUIRES_FOLLOW_UP = "requires_follow_up"  # evidence/observation/Finding -> Task, the one governed action-chain edge this stage adds
# CLAUDE-MM8 Section 31: four genuinely new types for the relationships
# nothing existing already names honestly - every other Section-31
# candidate word is mapped onto an already-existing type instead (see the
# fuller comment on KNOWN_CONTENT_CLASSES/WORK_PRODUCT_STATE_* below).
RELATIONSHIP_TYPE_BASED_ON = "based_on"
RELATIONSHIP_TYPE_SUMMARIZES = "summarizes"
RELATIONSHIP_TYPE_RESPONDS_TO = "responds_to"
RELATIONSHIP_TYPE_RESOLVES = "resolves"

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
    RELATIONSHIP_TYPE_DERIVED_FROM,
    RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
    RELATIONSHIP_TYPE_COMPARES_WITH,
    RELATIONSHIP_TYPE_CALCULATED_FROM,
    RELATIONSHIP_TYPE_MITIGATES,
    RELATIONSHIP_TYPE_VALIDATES,
    RELATIONSHIP_TYPE_INVALIDATES,
    RELATIONSHIP_TYPE_ASSOCIATED_WITH,
    RELATIONSHIP_TYPE_OBSERVES,
    RELATIONSHIP_TYPE_DEVIATES_FROM,
    RELATIONSHIP_TYPE_REQUIRES_FOLLOW_UP,
    RELATIONSHIP_TYPE_BASED_ON,
    RELATIONSHIP_TYPE_SUMMARIZES,
    RELATIONSHIP_TYPE_RESPONDS_TO,
    RELATIONSHIP_TYPE_RESOLVES,
)

# CLAUDE-MM6 Section 6: a Relationship's own validation state, ADDITIVE to
# the pre-existing provisional/confirmed_by axis (proposed-vs-confirmed) -
# this is a SEPARATE question ("is this edge itself disputed or rejected
# by a human," not "has anyone confirmed it yet"). None (the default,
# every pre-MM6 Relationship record) means ordinary/undisputed - never
# conflated with an explicit, governed dispute or rejection.
RELATIONSHIP_VALIDATION_DISPUTED = "disputed"
RELATIONSHIP_VALIDATION_REJECTED = "rejected"
KNOWN_RELATIONSHIP_VALIDATION_STATES = (
    RELATIONSHIP_VALIDATION_DISPUTED,
    RELATIONSHIP_VALIDATION_REJECTED,
)

# CLAUDE-MM6 Section 6/14: the resolved, READ-TIME-DERIVED status
# resolve_relationship_status returns - never stored (same "store flat,
# derive structure at read time" convention resolve_region_citation
# already uses for citations). "superseded" comes from a Supersession
# record naming this relationship as predecessor (supersede_relationship,
# below) - never a stored field on Relationship itself, the same
# discipline that keeps Source's own staleness derived from Supersession/
# superseded_by_source_id rather than a mutated boolean.
RELATIONSHIP_STATUS_PROPOSED = "proposed"
RELATIONSHIP_STATUS_CONFIRMED = "confirmed"
RELATIONSHIP_STATUS_DISPUTED = "disputed"
RELATIONSHIP_STATUS_REJECTED = "rejected"
RELATIONSHIP_STATUS_STALE = "stale"
RELATIONSHIP_STATUS_BROKEN = "broken"
RELATIONSHIP_STATUS_SUPERSEDED = "superseded"

# -- CLAUDE-MM7: Governed Investigation, Analytical Reasoning, and ----------
# Trustworthy Answers. Every vocabulary below backs `Claim` (defined near
# Finding/InvestigationStep) - the new, genuinely small adapter Section 7
# asks for: "do not duplicate EvidenceItem/DerivedObservation/Finding
# truth unnecessarily... prefer adapters." A Claim never stores evidence
# CONTENT of its own - only validated references to real, already-
# governed EvidenceItem/AddressableRegion/DerivedObservation/Finding/
# Source/Task ids (the exact same `_MM6_ENDPOINT_LISTS` MM6 already
# validates against, reused unchanged - see record_investigation_claim).

# Section 4's seven required distinctions - a closed vocabulary (unlike
# KNOWN_RELATIONSHIP_TYPES's deliberately open one): these seven categories
# are the whole point of the Trustworthy Answer Contract, so silently
# accepting an eighth, uncontrolled spelling here would undermine the
# contract itself, not extend it.
CLAIM_CLASS_DIRECTLY_VERIFIED = "directly_verified"
CLAIM_CLASS_DETERMINISTIC_CALCULATION = "deterministic_calculation"
CLAIM_CLASS_SUPPORTED_INTERPRETATION = "supported_interpretation"
CLAIM_CLASS_AI_PROPOSAL = "ai_proposal"
CLAIM_CLASS_CONFLICTING = "conflicting"
CLAIM_CLASS_UNKNOWN = "unknown"
CLAIM_CLASS_DECISION_REQUIRING_AUTHORITY = "decision_requiring_authority"
KNOWN_CLAIM_CLASSES = (
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CLAIM_CLASS_DETERMINISTIC_CALCULATION,
    CLAIM_CLASS_SUPPORTED_INTERPRETATION,
    CLAIM_CLASS_AI_PROPOSAL,
    CLAIM_CLASS_CONFLICTING,
    CLAIM_CLASS_UNKNOWN,
    CLAIM_CLASS_DECISION_REQUIRING_AUTHORITY,
)

# Section 5's own explicit instruction: "Do not use vague confidence
# percentages without a defined and testable meaning" - a closed,
# categorical vocabulary instead of Finding.machine_confidence's own
# free float (that field is untouched; a Claim carries ITS OWN
# confidence_state, deliberately not reusing or repurposing the older
# float - the two answer different questions for different objects).
CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT = "strong_direct_support"
CONFIDENCE_STATE_PARTIAL_SUPPORT = "partial_support"
CONFIDENCE_STATE_CONFLICTING_SUPPORT = "conflicting_support"
CONFIDENCE_STATE_INDIRECT_SUPPORT = "indirect_support"
CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE = "insufficient_evidence"
CONFIDENCE_STATE_STALE_EVIDENCE = "stale_evidence"
CONFIDENCE_STATE_SPECIALIST_CONFIRMATION_REQUIRED = "specialist_confirmation_required"
KNOWN_CONFIDENCE_STATES = (
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONFIDENCE_STATE_PARTIAL_SUPPORT,
    CONFIDENCE_STATE_CONFLICTING_SUPPORT,
    CONFIDENCE_STATE_INDIRECT_SUPPORT,
    CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE,
    CONFIDENCE_STATE_STALE_EVIDENCE,
    CONFIDENCE_STATE_SPECIALIST_CONFIRMATION_REQUIRED,
)

# Section 5's own explicit requirement: each confidence_state must carry a
# DEFINED, TESTABLE meaning, not just a label - explain_investigation_answer
# includes this verbatim in every assembled answer so a first-time user
# never has to guess what "partial_support" is supposed to mean.
CONFIDENCE_STATE_MEANINGS = {
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT: (
        "At least one directly-verified, current piece of evidence supports this claim, "
        "and no contradicting evidence was found."
    ),
    CONFIDENCE_STATE_PARTIAL_SUPPORT: (
        "Some supporting evidence exists, but it is indirect, incomplete, or covers only "
        "part of the claim."
    ),
    CONFIDENCE_STATE_CONFLICTING_SUPPORT: (
        "Both supporting and contradicting evidence exist for this claim - see the "
        "contradiction list, do not treat this as resolved."
    ),
    CONFIDENCE_STATE_INDIRECT_SUPPORT: (
        "Evidence exists but does not directly address this claim - it supports a related "
        "fact this claim was inferred from."
    ),
    CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE: (
        "The evidence gathered for this investigation cannot establish this claim - "
        "see recommended_next_check for what would be needed."
    ),
    CONFIDENCE_STATE_STALE_EVIDENCE: (
        "The cited evidence's own Source has since been superseded by a later revision - "
        "the citation still resolves, but may no longer reflect current conditions."
    ),
    CONFIDENCE_STATE_SPECIALIST_CONFIRMATION_REQUIRED: (
        "This claim touches a judgment this system cannot make on its own - a qualified "
        "specialist must confirm it before it is relied on."
    ),
}

# Section 13's controlled analytical-method vocabulary - open-world (same
# pattern as KNOWN_RELATIONSHIP_TYPES/KNOWN_INVESTIGATION_STEP_KINDS),
# since "such as" in the governing prompt signals an extensible list, not
# a final closed set. ai_assisted_synthesis is the one method whose
# result is NEVER deterministic - Section 13's own "do not claim
# deterministic computation when the result was AI-generated" is enforced
# by record_investigation_claim (see its own docstring), not merely
# documented here.
ANALYTICAL_METHOD_DIRECT_RETRIEVAL = "direct_retrieval"
ANALYTICAL_METHOD_DETERMINISTIC_COMPARISON = "deterministic_comparison"
ANALYTICAL_METHOD_ARITHMETIC_CALCULATION = "arithmetic_calculation"
ANALYTICAL_METHOD_FORMULA_EVALUATION = "formula_evaluation"
ANALYTICAL_METHOD_CROSS_SOURCE_COMPARISON = "cross_source_comparison"
ANALYTICAL_METHOD_VERSION_COMPARISON = "version_comparison"
ANALYTICAL_METHOD_REQUIREMENT_TO_EVIDENCE_TRACE = "requirement_to_evidence_trace"
ANALYTICAL_METHOD_VISUAL_OBSERVATION = "visual_observation"
ANALYTICAL_METHOD_STRUCTURED_INTERPRETATION = "structured_interpretation"
ANALYTICAL_METHOD_AI_ASSISTED_SYNTHESIS = "ai_assisted_synthesis"
ANALYTICAL_METHOD_HUMAN_ADJUDICATION = "human_adjudication"
KNOWN_ANALYTICAL_METHODS = (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    ANALYTICAL_METHOD_DETERMINISTIC_COMPARISON,
    ANALYTICAL_METHOD_ARITHMETIC_CALCULATION,
    ANALYTICAL_METHOD_FORMULA_EVALUATION,
    ANALYTICAL_METHOD_CROSS_SOURCE_COMPARISON,
    ANALYTICAL_METHOD_VERSION_COMPARISON,
    ANALYTICAL_METHOD_REQUIREMENT_TO_EVIDENCE_TRACE,
    ANALYTICAL_METHOD_VISUAL_OBSERVATION,
    ANALYTICAL_METHOD_STRUCTURED_INTERPRETATION,
    ANALYTICAL_METHOD_AI_ASSISTED_SYNTHESIS,
    ANALYTICAL_METHOD_HUMAN_ADJUDICATION,
)

# Section 15's own required states (nine total): eight are STORED (set by
# an explicit human or system action - record_investigation_claim/
# accept_claim_as_observation/accept_claim_as_finding/dispute_claim/
# reject_claim/request_claim_specialist_review/request_claim_authority);
# "superseded" (the ninth) is deliberately NOT stored here - exactly like
# RELATIONSHIP_STATUS_SUPERSEDED, it is derived at read time in
# resolve_claim_status from a real Supersession record, never a value
# this field is ever directly set to.
CLAIM_ADOPTION_PROPOSED = "proposed"
CLAIM_ADOPTION_UNDER_REVIEW = "under_review"
CLAIM_ADOPTION_ACCEPTED_AS_OBSERVATION = "accepted_as_observation"
CLAIM_ADOPTION_ACCEPTED_AS_FINDING = "accepted_as_finding"
CLAIM_ADOPTION_REJECTED = "rejected"
CLAIM_ADOPTION_DISPUTED = "disputed"
CLAIM_ADOPTION_REQUIRES_SPECIALIST = "requires_specialist"
CLAIM_ADOPTION_REQUIRES_AUTHORITY = "requires_product_owner_or_contractual_authority"
# Derived-only, never stored - see resolve_claim_status.
CLAIM_ADOPTION_SUPERSEDED = "superseded"
KNOWN_CLAIM_ADOPTION_STATES = (
    CLAIM_ADOPTION_PROPOSED,
    CLAIM_ADOPTION_UNDER_REVIEW,
    CLAIM_ADOPTION_ACCEPTED_AS_OBSERVATION,
    CLAIM_ADOPTION_ACCEPTED_AS_FINDING,
    CLAIM_ADOPTION_REJECTED,
    CLAIM_ADOPTION_DISPUTED,
    CLAIM_ADOPTION_REQUIRES_SPECIALIST,
    CLAIM_ADOPTION_REQUIRES_AUTHORITY,
)

# -- CLAUDE-MM8: Governed Creation, Editing, Review, and Accountable --------
# Work Products. Backs `WorkProduct` (defined near Claim/Finding) - Section
# 5's own strict distinction ("work product is not evidence") means a
# WorkProduct never becomes an EvidenceItem merely by existing; it CITES
# evidence (and Claims/Findings/DerivedObservations) the same validated way
# a Claim does, via the same `_MM6_ENDPOINT_LISTS` (extended below to also
# accept `claim`/`work_product` themselves as citable/relatable objects).

# Section 17's lifecycle - six stored states (the "proposed"/"rejected"/
# "returned for revision" extras Section 17 mentions "where useful" are
# folded into this same set: revisions_required already IS "returned for
# revision"; a rejected/proposed WHOLE work product has no real use case
# yet distinct from simply not creating or not yet submitting one).
# "superseded" is deliberately NOT stored here - exactly like Claim/
# Relationship, it is derived at read time from a real Supersession record
# (see resolve_work_product_status), never a value this field is directly
# set to.
WORK_PRODUCT_STATE_DRAFT = "draft"
WORK_PRODUCT_STATE_NEEDS_REVIEW = "needs_review"
WORK_PRODUCT_STATE_REVIEWED = "reviewed"
WORK_PRODUCT_STATE_REVISIONS_REQUIRED = "revisions_required"
WORK_PRODUCT_STATE_APPROVED_FOR_ISSUE = "approved_for_issue"
WORK_PRODUCT_STATE_ISSUED = "issued"
# Derived-only, never stored - see resolve_work_product_status.
WORK_PRODUCT_STATE_SUPERSEDED = "superseded"
KNOWN_WORK_PRODUCT_STATES = (
    WORK_PRODUCT_STATE_DRAFT,
    WORK_PRODUCT_STATE_NEEDS_REVIEW,
    WORK_PRODUCT_STATE_REVIEWED,
    WORK_PRODUCT_STATE_REVISIONS_REQUIRED,
    WORK_PRODUCT_STATE_APPROVED_FOR_ISSUE,
    WORK_PRODUCT_STATE_ISSUED,
)

# Section 8's seven required content-provenance classes for one structured
# section of a work product - deliberately a DIFFERENT, work-product-scoped
# vocabulary from Claim's own KNOWN_CLAIM_CLASSES (a section answers "who/
# what put this text here", a Claim answers "what kind of assertion is
# this" - related questions, not the same one). `edited_ai_proposal` is
# the concrete answer to Section 8's "AI content must not become human-
# approved simply because a user opens the document": editing a section
# whose CURRENT class is ai_proposed transitions it here automatically
# (see edit_work_product_section), never silently to human_authored.
CONTENT_CLASS_HUMAN_AUTHORED = "human_authored"
CONTENT_CLASS_AI_PROPOSED = "ai_proposed"
CONTENT_CLASS_IMPORTED = "imported"
CONTENT_CLASS_DETERMINISTIC_CALCULATION = "deterministic_calculation"
CONTENT_CLASS_DIRECT_EVIDENCE_REFERENCE = "direct_evidence_reference"
CONTENT_CLASS_EDITED_AI_PROPOSAL = "edited_ai_proposal"
CONTENT_CLASS_TEMPLATE_CONTENT = "template_content"
KNOWN_CONTENT_CLASSES = (
    CONTENT_CLASS_HUMAN_AUTHORED,
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_IMPORTED,
    CONTENT_CLASS_DETERMINISTIC_CALCULATION,
    CONTENT_CLASS_DIRECT_EVIDENCE_REFERENCE,
    CONTENT_CLASS_EDITED_AI_PROPOSAL,
    CONTENT_CLASS_TEMPLATE_CONTENT,
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
MESSAGE_TYPE_CARRIED_FORWARD = "carried_forward"  # Selective Adopt/Carry-Forward tranche - a historical comment deliberately reconsidered in a derived active Case, authored by the adopting actor, not the original commenter

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
    MESSAGE_TYPE_CARRIED_FORWARD,
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
# CLAUDE-MM5: an Eye-pasted/dropped image saved to the project (Section 7 -
# "Save to project") is genuinely a distinct origin from an ordinary file
# upload (Section 8's own screenshot-workflow provenance requirement -
# "preserve... capture time" - reads more honestly as "captured via Eye"
# than "uploaded"); a derivative crop (Section 12/6) is neither an upload
# nor a capture - it is MECHANICALLY GENERATED from an existing region,
# which is exactly what origin_reference (below) is for.
SOURCE_ORIGIN_TYPE_EYE_CAPTURE = "eye_capture"
SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP = "derivative_crop"
# CLAUDE-SNAPSHOT-DUAL-SURFACE-01: a rendered-page capture of a document
# already open in Main or Eye (whichever surface currently has focus) -
# distinct from eye_capture (a pasted/dropped/camera image with no
# document of its own behind it) and derivative_crop (a bounded region
# crop of a Source's own stored file, not a rendered VIEW of it - a
# Snapshot can capture a page/zoom/rotation state a crop has no concept
# of). origin_reference carries "<parent_source_id>" or "<parent_source_
# id>#page=<n>" when a page number is known - meaning-depends-on-origin-
# type, same convention every other origin_type here already uses.
SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT = "document_snapshot"

KNOWN_SOURCE_ORIGIN_TYPES = (
    SOURCE_ORIGIN_TYPE_UPLOAD,
    SOURCE_ORIGIN_TYPE_CONTROLLED_CORPUS,
    SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR,
    SOURCE_ORIGIN_TYPE_IMPORT,
    SOURCE_ORIGIN_TYPE_EYE_CAPTURE,
    SOURCE_ORIGIN_TYPE_DERIVATIVE_CROP,
    SOURCE_ORIGIN_TYPE_DOCUMENT_SNAPSHOT,
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
# CLAUDE-P13: the one seam this pass adds - not yet issued/authoritative,
# distinct from FUTURE_EFFECTIVE (which IS already issued, just not yet
# the operative rule). Nothing in this codebase sets or reads this value
# yet; it exists only so an Owner/issuer drafting a Requirement before
# issuance has an honest status to record it under, without registering
# a not-yet-real clause as REQUIREMENT_STATUS_ACTIVE (which would
# misrepresent it as already authoritative). No route, form, or workflow
# uses this today - see the accompanying analysis for why issuer-side
# authoring is examined but deliberately not built in this pass.
REQUIREMENT_STATUS_DRAFT = "draft"

KNOWN_REQUIREMENT_STATUSES = (
    REQUIREMENT_STATUS_ACTIVE,
    REQUIREMENT_STATUS_SUPERSEDED,
    REQUIREMENT_STATUS_WITHDRAWN,
    REQUIREMENT_STATUS_FUTURE_EFFECTIVE,
    REQUIREMENT_STATUS_UNKNOWN,
    REQUIREMENT_STATUS_DRAFT,
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
# Distinct from the TEST_FIXTURE value above, which its own name commits to
# meaning exactly what it says - discovered live (Cedar Harbour discovery
# journey) that the vocabulary had no honest word for a real reviewer
# reading a real Source and directly asserting a Requirement's text, with
# no machine extraction and no test-fixture pretense involved.
REQUIREMENT_REGISTRATION_HUMAN_REGISTERED = "human_registered"
REQUIREMENT_REGISTRATION_DERIVED_FROM_STRUCTURED_SOURCE = "derived_from_structured_source"
REQUIREMENT_REGISTRATION_IMPORTED = "imported"
REQUIREMENT_REGISTRATION_OTHER = "other"

KNOWN_REQUIREMENT_REGISTRATION_METHODS = (
    REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
    REQUIREMENT_REGISTRATION_MANUAL_TEST_FIXTURE,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
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

# -- Structured Tabular Evidence / Source Reference vocabulary (Prompt 18 / Batch J) --
# Prompt 18 #14: the KIND of thing a source reference names (a Section, a
# Figure, a Row, ...) - open-world, since a different document could use
# "Schedule"/"Drawing"/"Annex"/etc, none of which this codebase should have
# to know about in advance to represent honestly.
REFERENCE_TYPE_SECTION = "section"
REFERENCE_TYPE_CLAUSE = "clause"
REFERENCE_TYPE_FIGURE = "figure"
REFERENCE_TYPE_TABLE = "table"
REFERENCE_TYPE_TABLE_ROW = "table_row"
REFERENCE_TYPE_APPENDIX = "appendix"

KNOWN_REFERENCE_TYPES = (
    REFERENCE_TYPE_SECTION,
    REFERENCE_TYPE_CLAUSE,
    REFERENCE_TYPE_FIGURE,
    REFERENCE_TYPE_TABLE,
    REFERENCE_TYPE_TABLE_ROW,
    REFERENCE_TYPE_APPENDIX,
)

# Prompt 18 #18: the RESOLVER's own closed output vocabulary - like
# SUFFICIENCY_*/TEMPORAL_CONDITION_* before it, never open-world, never
# supplied by a caller. See resolve_source_reference_candidate below.
RESOLUTION_STATUS_RESOLVED_EXACT = "resolved_exact"
RESOLUTION_STATUS_RESOLVED_RANGE = "resolved_range"
RESOLUTION_STATUS_RESOLVED_MULTIPLE = "resolved_multiple"
RESOLUTION_STATUS_AMBIGUOUS = "ambiguous"
RESOLUTION_STATUS_TARGET_NOT_FOUND = "target_not_found"
RESOLUTION_STATUS_UNSUPPORTED_REFERENCE_TYPE = "unsupported_reference_type"
RESOLUTION_STATUS_PARTIALLY_RESOLVED = "partially_resolved"
RESOLUTION_STATUS_UNKNOWN = "unknown"


class CaseWorkspaceError(Exception):
    """Raised for invalid workspace operations (unknown ids, bad states, etc)."""


class OperatingEnvironmentAlreadySetError(CaseWorkspaceError):
    """
    CLAUDE-P29: raised by CaseWorkspaceStore.set_operating_environment
    when a project's operating_environment is already non-None -- the
    structural enforcement of "a project's environment is locked at
    creation and can never be changed into the opposing one," not just
    a convention callers are expected to honor.
    """


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
    # CLAUDE-P40-E2: recoverable "Remove Document" - deliberately not a
    # deletion. `removed_at is None` is the only thing that means
    # "active" anywhere this field is read; the record itself, its id,
    # file_path, and every dependent reference (Findings/Artifacts/
    # Requirements citing this Source) are completely untouched by
    # removal - see CaseWorkspaceStore.remove_source/restore_source.
    removed_at: Optional[str] = None
    removed_by: Optional[str] = None
    removal_reason: Optional[str] = None
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
    # CLAUDE-MM1: additive Source-Artifact fields the multimodal foundation
    # needs (camel-multimodal-programme.md's MM1) - every existing Source
    # simply lacks these keys and loads with the honest None default, the
    # same backward-compatible shape every prior addition to this dataclass
    # already uses. mime_type/size_bytes are physical-file facts distinct
    # from `kind`'s coarse content category; security_classification is
    # per-Source (narrower than CLAUDE-P31's project-wide security_profile,
    # not a replacement for it); extractor_version mirrors ParsedDocument's
    # own parser_version (services/bhive_parser.py) but recorded on the
    # governed Source record itself, since only the auto-registered first
    # Source has an equivalent today.
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    security_classification: Optional[str] = None  # open-world
    extractor_version: Optional[str] = None
    # CLAUDE-RFP27-TERRITORY-01: which Folder (see below) this Source
    # belongs to - None means "unfiled," the honest state of every
    # pre-existing Source and of any Source whose real Data Room location
    # isn't known. Deliberately optional and additive (every existing
    # Source simply lacks this key and loads with the honest None
    # default, same backward-compatible shape as every prior addition to
    # this dataclass) - Lists' own flat Documents list is UNCHANGED for
    # any Source with folder_id=None; only Files' own per-folder view
    # (below) reads this field. Never inferred from filename/path
    # guessing - only ever set by real folder-reconciliation (see
    # CaseWorkspaceStore.ensure_folder_path/services/ingestion.py's own
    # reconcile_data_room_upload) or a future explicit move action.
    folder_id: Optional[str] = None


@dataclass
class Folder:
    """
    CLAUDE-P40-VW9: a Project-scoped organizational container inside one
    of the two governed Files roots (`root` - FOLDER_ROOT_DATA_ROOM or
    FOLDER_ROOT_DESIGN_BUILDER, above; every Folder this stage creates
    has root=FOLDER_ROOT_DESIGN_BUILDER). Canonical identity is `id`,
    exactly matching Source's own "folder locations and filenames are
    external representations only" principle above - a Folder retains
    its identity across rename (`name` changes) and move
    (`parent_folder_id` changes); nothing here is ever derived from
    name, parent, sibling order, or render order. A folder's full path
    is always DERIVED at read time by walking `parent_folder_id`
    pointers (see CaseWorkspaceStore._folder_path), never stored as a
    string - the same "store flat, derive structure at read time" shape
    this module already uses everywhere else (e.g. visible_cases_for).

    `parent_folder_id=None` means directly under this Folder's own
    `root` - `root` and `parent_folder_id` together, not
    `parent_folder_id` alone, place a Folder; a Design-Builder folder's
    `parent_folder_id`, even when None, never means "the Data Room" or
    vice versa. Every mutation method on CaseWorkspaceStore re-validates
    `project_id` against the calling workspace before acting (Section 10
    of this stage's own governing prompt: "folder operations cannot
    cross Project boundaries through crafted identifiers") - `project_id`
    is carried on the record itself, not inferred solely from already
    being inside `workspace.folders`, the same defensive shape
    `Source.project_id` already uses.

    No `folder_id` exists on `Source` (this stage does not add one - see
    this stage's own completion notes): a Document is never assigned
    into a Folder in this slice, so Document identity/relationships are
    completely unaffected by anything in this class.

    Deletion is a recoverable removal (`removed_at`/`removed_by`), the
    same "never a true deletion" convention `Source`/`ProjectWorkspace`
    already establish above (Constitutional Invariant 5: "correction is
    non-destructive... never erase") - `delete_folder` below only ever
    operates on an EMPTY folder (never one with real content to lose),
    but the id itself is still never reused for a different folder once
    removed, matching every other tombstone in this codebase.
    """

    id: str
    project_id: str
    root: str  # FOLDER_ROOT_* - only FOLDER_ROOT_DESIGN_BUILDER is ever created this stage
    name: str
    created_at: str
    created_by: Optional[str] = None
    parent_folder_id: Optional[str] = None
    removed_at: Optional[str] = None
    removed_by: Optional[str] = None


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


# CLAUDE-P40-VW7: bounded, project-scoped authorization for Project
# Conversation text Tags/Highlights/Tasks - an explicit, narrow lift of
# the "Application implementation, broadly: STILL FROZEN" default (see
# governance/STATUS.md's own authorization table, updated alongside
# this stage), NOT a general annotation/task-management architecture.
# Deliberately excluded, per the authorizing prompt itself: cross-
# project intelligence, machine-generated assumption correction,
# organization-wide task management, external integrations, general
# autonomous chat governance, user assignment, due dates, notifications.
#
# TAG_COLOR_PALETTE is a small, fixed set of NAMED colors (not raw hex)
# - CSS (static/css/tokens.css's --tagcolor-* family) maps each name to
# an actual swatch value per Light/Dark/Tinted mode, the same
# scoped-custom-property mechanism CLAUDE-P40-VW6 already established
# for the rest of the palette. Storing a name here, not a hex code,
# keeps the store layer honestly ignorant of the CSS token system and
# guarantees every tag - built-in or custom - renders correctly in
# every appearance mode without per-tag special-casing.
TAG_COLOR_PALETTE: tuple[str, ...] = ("yellow", "orange", "red", "green", "blue", "purple")

# Built-in tags: fixed, code-level identities (never stored in
# ProjectWorkspace.tags - creating one would misrepresent them as
# project-scoped custom tags, which they're explicitly not) so every
# project shares the exact same "Important"/"Question" meaning, and
# "Highlight" is honestly just another built-in tag under the hood
# (same TagOccurrence shape, same rendering path) rather than a
# second, parallel highlighting mechanism.
BUILT_IN_TAG_IMPORTANT = "built-in:important"
BUILT_IN_TAG_QUESTION = "built-in:question"
BUILT_IN_TAG_HIGHLIGHT = "built-in:highlight"
BUILT_IN_TAGS: dict[str, dict] = {
    BUILT_IN_TAG_IMPORTANT: {"id": BUILT_IN_TAG_IMPORTANT, "name": "Important", "color": "red"},
    BUILT_IN_TAG_QUESTION: {"id": BUILT_IN_TAG_QUESTION, "name": "Question", "color": "blue"},
    BUILT_IN_TAG_HIGHLIGHT: {"id": BUILT_IN_TAG_HIGHLIGHT, "name": "Highlight", "color": "yellow"},
}

# Conversation-source-anchor scopes - which of the two existing
# conversation lists (or the one static piece of guidance copy) a
# selection was made in. Deliberately mirrors ConversationMessage's own
# case_id=None-means-project-level convention rather than inventing a
# different one.
CONVERSATION_ANCHOR_SCOPE_CASE = "case"
CONVERSATION_ANCHOR_SCOPE_PROJECT = "project"
CONVERSATION_ANCHOR_SCOPE_GUIDANCE = "guidance"
KNOWN_CONVERSATION_ANCHOR_SCOPES = frozenset({
    CONVERSATION_ANCHOR_SCOPE_CASE, CONVERSATION_ANCHOR_SCOPE_PROJECT, CONVERSATION_ANCHOR_SCOPE_GUIDANCE,
})

# The one static guidance passage this stage anchors to a stable NAME
# rather than a fabricated conversation message (Section 4's own
# explicit instruction) - templates/case_workspace.html's own project-
# conversation "Talk to the Project itself..." paragraph. A second
# named guidance passage (none exists today) would get its own key
# here, not a new mechanism.
CONVERSATION_GUIDANCE_PROJECT_INTRO = "project-conversation-intro"


@dataclass
class ConversationSourceAnchor:
    """
    CLAUDE-P40-VW7: what a Tag/Highlight/Task occurrence actually points
    back to - a text-quote-style anchor (canonical offsets + the exact
    quotation + limited prefix/suffix context), not fragile DOM
    coordinates (Section 4's own explicit instruction). `case_id=None`
    with `scope="project"` mirrors ConversationMessage's own project-
    level convention; `scope="guidance"` never has a `message_id` at
    all (there is no message to point to - see
    CONVERSATION_GUIDANCE_PROJECT_INTRO above).
    """

    scope: str  # KNOWN_CONVERSATION_ANCHOR_SCOPES
    case_id: Optional[str] = None
    message_id: Optional[str] = None
    guidance_key: Optional[str] = None
    start_offset: int = 0
    end_offset: int = 0
    quote: str = ""
    prefix: str = ""
    suffix: str = ""


@dataclass
class Tag:
    """A project-scoped custom tag definition (built-in tags - Important/
    Question/Highlight - are NOT stored here, see BUILT_IN_TAGS above).
    Deliberately no organization-wide taxonomy: this list lives on ONE
    ProjectWorkspace, never shared or merged across projects."""

    id: str
    name: str
    color: str  # one of TAG_COLOR_PALETTE
    created_by: str
    created_at: str


@dataclass
class TagOccurrence:
    """One tagged/highlighted passage. `tag_id` is either a BUILT_IN_TAGS
    key or a real Tag.id from workspace.tags - resolve_tag() below is
    the one place that distinguishes them. Removing an occurrence never
    touches the source conversation text it points to (Section 5's own
    explicit requirement) - it only ever removes this record."""

    id: str
    tag_id: str
    source_anchor: dict  # asdict(ConversationSourceAnchor)
    quote: str
    created_by: str
    created_at: str


@dataclass
class Task:
    """A real persisted project Task created from a selected Project
    Conversation passage - Section 6's own explicit "not a decorative
    checkbox or temporary browser state" requirement. Deliberately no
    assignee/due-date/notification fields - those remain unauthorized
    by this same stage's own scope boundary."""

    id: str
    source_anchor: dict  # asdict(ConversationSourceAnchor)
    quote: str
    title: str
    status: str  # "open" | "completed"
    created_by: str
    created_at: str
    completed_by: Optional[str] = None
    completed_at: Optional[str] = None
    reopened_by: Optional[str] = None
    reopened_at: Optional[str] = None


TASK_STATUS_OPEN = "open"
TASK_STATUS_COMPLETED = "completed"


@dataclass
class ConversationMessage:
    """
    case_id is optional (matching the same extension AnalysisRun and
    ReviewThread already made): a message sent from a project-level
    context (a Requirement, a Source, no Case open at all) has nowhere
    case-shaped to live, and forcing one into existence just to hold a
    message is exactly the surprise quick_start currently causes (it
    silently creates a whole new Case for this reason). Case-scoped
    messages keep living inside their Case's own `conversation` list
    (unchanged, no migration); a case_id=None message lives in
    ProjectWorkspace.project_conversation instead - two lists, not one
    polymorphic one, matching how Requirement (project-level) and
    Finding (Case-level) already stay genuinely separate rather than
    being forced into a single "governed thing" abstraction.

    `anchor` (same Anchor shape ReviewThread already uses - anchor_type/
    anchor_id/source_id/location/description) records what the sender
    was actually looking at when they spoke, independent of which
    conversation the message landed in. This is the "aperture" - the
    system knows what was in view even though there is still only one
    conversation per Case (or one per project-level context), not a
    separate fragmented conversation per object a message happens to
    mention.

    `actor` names who sent a human message (role="system" replies leave
    it None - there is exactly one reply-generator, naming it would be
    noise). A shared/collaborative Case's conversation was previously
    unattributed beyond "human" vs "system" - this is what lets
    recent_anchors_for build a genuinely per-reviewer "where did I
    leave off" trail rather than a project-wide one.
    """

    id: str
    role: str  # "human" | "system"
    text: str
    created_at: str
    case_id: Optional[str] = None
    actor: Optional[str] = None  # who sent it, when role == "human" - see recent_anchors_for
    action_taken: Optional[str] = None
    anchor: Optional[dict] = None  # asdict(Anchor) - what was in view when this was sent
    # CLAUDE-POSTCAMEL-CA1A: the real, already-validated Source id (if
    # any) the sender was viewing via ?source= when THIS human message
    # was sent - only ever set on a human message, same as `anchor`.
    # Persisted for the same reason `anchor` is: without it,
    # start_investigation_from_aperture's own re-run of this exact
    # message text into a new Case would silently lose the original
    # Source-selection context and answer differently the second time -
    # found live, during this stage's own Walkthrough A, not assumed.
    # Optional/defaulted so old saved ConversationMessage JSON (pre-
    # CA1A) deserializes unchanged.
    selected_source_id: Optional[str] = None
    # CLAUDE-P40-B (3.6): grounded Project Q&A's supporting citations,
    # kept SEPARATE from `text` rather than concatenated into it - a
    # real product-owner walkthrough found a long "Grounded in: ..."
    # tail appended to `text` made a short, direct answer read as if it
    # "began by" repeating unrelated provenance text. Only ever set for
    # a project_qa_answered reply; every other reply leaves this empty.
    # Optional/defaulted so old saved ConversationMessage JSON (pre-
    # P40-B) deserializes unchanged.
    grounded_in: list[str] = field(default_factory=list)
    # CLAUDE-POSTCAMEL-CA1: a small, deterministic, server-computed list
    # of real next-step offers ({"label": ..., "view": ...}, `view`
    # always an existing Display view name) - never model-generated
    # prose parsed as a command (Section 10's own "structured action
    # envelopes, not arbitrary model prose"). Only ever set for
    # project_orientation/project_qa_answered/project_qa_unavailable/
    # unrecognized replies; every other reply leaves this empty.
    # Optional/defaulted so old saved ConversationMessage JSON (pre-CA1)
    # deserializes unchanged.
    next_steps: list[dict] = field(default_factory=list)
    # CLAUDE-POSTCAMEL-CA1C (Section 6/17): a real Source id, set only
    # when interpret_message's own _handle_organize_advice determined a
    # real, safe "Create this structure" action genuinely applies -
    # never model-generated, always a real, already-validated Source id.
    # Optional/defaulted so old saved ConversationMessage JSON (pre-
    # CA1C) deserializes unchanged.
    organize_source_id: Optional[str] = None
    # CLAUDE-CA1D-RIVER-01: the fourth beat - a small, deterministic list
    # of real, already-implemented next-action offers ({"kind": "task" |
    # "tag", "label": str, "tag_id": str (tag only)}), never model-
    # generated prose. Only ever set for a project_qa_answered reply
    # whose own answer was genuinely evidence-grounded; every other reply
    # leaves this empty. Optional/defaulted so old saved ConversationMessage
    # JSON (pre-CA1D) deserializes unchanged.
    operational_actions: list[dict] = field(default_factory=list)
    # CLAUDE-CA1D-RIVER-PO-01 (River Action Stack): a small, ranked set
    # of consequential next moves ({"rank": int, "action": str,
    # "rationale": str, "consequence": str, "uncertainty": str,
    # "evidence": list[str]}) - the model's OWN signal, read back
    # verbatim (same discipline grounded_in/next_steps already use),
    # never generated or reordered by this application's own code beyond
    # defensive validation (services/project_qa.py's own
    # _parse_river_actions). Only ever set for a project_qa_answered
    # reply the reviewer was genuinely asking "what should I do next" -
    # every other reply leaves this empty. Optional/defaulted so old
    # saved ConversationMessage JSON (pre-CA1D-RIVER-PO-01) deserializes
    # unchanged.
    river_actions: list[dict] = field(default_factory=list)
    # CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 1): provenance for a
    # conversational turn, reusing the SAME KNOWN_CONTENT_CLASSES closed
    # vocabulary WorkProductSection already uses (see add_message's own
    # validation, mirroring _add_work_product_section's) - never a new,
    # Conversation-specific vocabulary. None for every message persisted
    # before this stage existed (old saved ConversationMessage JSON
    # deserializes unchanged); every message persisted from this stage
    # forward gets a real value from add_message's own required-ish
    # stamping discipline (see routes/workspace.py's _run_conversation_
    # turn and each conversation_interpreter.py handler for which value
    # applies to which reply).
    content_class: Optional[str] = None
    # CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 1, greenfield): disambiguation
    # candidates a conversational turn's own reply offered
    # ({"anchor_type": str, "anchor_id": str, "description": str}, the
    # same shape Anchor's own fields already use - never a new object-
    # identity model), so a later turn's "no, I meant the other one" can
    # resolve against what was actually offered rather than re-deriving
    # candidates from raw history text. Only ever set on a system reply
    # that genuinely presented more than one plausible referent; every
    # other message leaves this empty. Optional/defaulted so old saved
    # ConversationMessage JSON (pre-Stage-1) deserializes unchanged.
    candidate_referents: list[dict] = field(default_factory=list)


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


# CLAUDE-GO-RIGHT-PANEL-01: a Composer-emitted, PROJECT-scoped
# characterization - deliberately NOT the same object as Finding above.
# Finding requires a case_id/analysis_id (a real, opened Investigation
# with a formal Analysis run behind it) - the Composer's own project-
# level Q&A path (services/project_qa.py) has neither of those and must
# not fabricate a fake Case/Analysis merely to satisfy Finding's shape
# (that would be "conflating the two" the governing product principle
# explicitly warns against). This is the smaller, lighter object: what
# the Composer noticed while answering an ordinary project question,
# promoted from transient reply prose into durable, project-scoped
# record - the same "governed-but-provisional, no Approval Gate"
# posture record_analysis's own Findings already have (see
# add_composer_finding below), reusing that established classification
# rather than inventing a new authority tier.
COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED = "machine_finding_unreviewed"
# CLAUDE-GO-RIGHT-PANEL-01: deliberately a ONE-member closed set for
# this first slice (Section 6's own "Machine Finding / Unreviewed"
# instruction) - stored and validated as a real closed vocabulary
# (mirroring KNOWN_CONTENT_CLASSES/REVIEWER_VALIDATION_STATES' own
# pattern immediately above), not a hardcoded string check, so a future
# PM-reviewed/accepted/modified/dismissed state is a vocabulary
# addition here, never a storage-shape migration.
KNOWN_COMPOSER_FINDING_STATES = (COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED,)


@dataclass
class ComposerFinding:
    """One Composer-emitted project characterization, promoted from a
    ProjectQAResult.findings entry (services/project_qa.py) into a
    durable, project-scoped record - see the module comment above this
    class for why it is not a Finding. `tag` is a short descriptive
    title (e.g. "Submission deadline"), deliberately a plain string, NOT
    a reference into the Tag/BUILT_IN_TAGS system above - that system is
    a small, reusable, colour-coded label taxonomy meant to be applied
    to many different passages; a per-finding one-off title is a
    genuinely different concept, and forcing it through create_custom_tag
    would flood that taxonomy with names never reused anywhere else (the
    repository already distinguishes the two, so this keeps them
    distinct rather than conflating them). `source_message_id` is the
    ConversationMessage this was promoted from (project_conversation,
    never a Case's own conversation - this object only exists on the
    project-level Q&A path) - the provenance link back to the turn that
    produced it. `urgency`/`project_stage` are optional and left None
    whenever the model did not honestly ground them (Section 2's own
    "do not invent unsupported metadata merely to fill fields")."""

    id: str
    project_id: str
    tag: str
    source_reference: str
    concern: str
    unresolved_question: str
    created_at: str
    created_by: Optional[str] = None
    urgency: Optional[str] = None
    project_stage: Optional[str] = None
    review_state: str = COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED
    content_class: str = CONTENT_CLASS_AI_PROPOSED
    source_message_id: Optional[str] = None


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
class RequirementAdjudication:
    """
    Foundation Batch K (Prompt 19): the human REQUIREMENT-level compliance
    record - a distinct question from Disposition's "what happens to this
    Finding next" above. Registering a Requirement (see Requirement) makes
    no claim about whether it is satisfied; this is the first-class record
    of a human's answer to that separate question, at the Requirement's
    own grain rather than any single Finding's.

    Deliberately many-to-many with evidence rather than 1:1 with a Finding
    the way Disposition/ReviewerValidation are: `evidence_finding_ids`/
    `evidence_relationship_ids` may be EMPTY (e.g. "Not Applicable" needs
    no supporting Finding at all) or may reference several Findings and
    Relationships spanning several Analyses. A Requirement never requires
    exactly one Finding to exist (see Requirement's own docstring) - this
    record preserves that same independence for its own outcome.

    Append-only like ReviewerValidation/Disposition (see
    record_requirement_adjudication) - a later adjudication supersedes an
    earlier one in EFFECT (see latest_requirement_adjudication_for /
    requirement_adjudication_state) but never overwrites or deletes it,
    per ADR-032-R06's human-adjudication-as-evidence principle.

    `outcome` is a CLOSED vocabulary (REQUIREMENT_ADJUDICATION_OUTCOMES),
    deliberately narrower than every candidate word considered (see the
    vocabulary comment above) - "Needs Evidence" and "Not Yet Assessed"
    are never stored values here, only ever the DERIVED absence of any
    record at all (requirement_adjudication_state): an un-adjudicated
    Requirement has no row, not a placeholder row saying so.

    Never touches `Requirement.status` (see set_requirement_status's own
    compliance denylist) - governed Requirement lifecycle state and
    adjudicated compliance outcome remain two separate, never-merged
    layers.

    CLAUDE-POSTCAMEL-COMM-I5A: `attribution` (Optional,
    KNOWN_ADJUDICATION_ATTRIBUTIONS) distinguishes a personally-formed
    human judgment from an agent/automation's assessment entered through
    this same object - the gap this docstring's own long-standing "a
    human's answer" claim never actually enforced. `adjudicator` alone
    (a username) was never sufficient: it says WHO/WHAT ACCOUNT performed
    the write, never whether the judgment itself was a human's own. A
    legacy record predating this field simply lacks the key (the same
    honest-absence pattern every prior additive field on this codebase
    uses) - see resolve_requirement_adjudication_attribution for how that
    absence is read, never silently defaulted to "human".
    """

    id: str
    project_id: str
    requirement_id: str
    outcome: str  # REQUIREMENT_ADJUDICATION_OUTCOMES
    adjudicator: str
    adjudicated_at: str
    reasoning: str
    evidence_finding_ids: list[str] = field(default_factory=list)
    evidence_relationship_ids: list[str] = field(default_factory=list)
    attribution: Optional[str] = None  # KNOWN_ADJUDICATION_ATTRIBUTIONS


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
class InvestigationStep:
    """
    CLAUDE-P08: one observable, auditable unit of investigation work -
    what was being investigated, what evidence was gathered, what
    conclusion/uncertainty resulted - deliberately never the model's raw
    reasoning tokens. The Anthropic messages API doesn't expose those
    for an ordinary text completion in the first place, so this schema
    isn't choosing to hide something it could otherwise show - there is
    nothing there to hide.

    One dataclass, an open-world `step_kind` (KNOWN_INVESTIGATION_STEP_
    KINDS - same pattern as Relationship.relationship_type/Supersession's
    object-kind normalization), not a family of subclasses for query/
    retrieval/comparison/branch/human-gate/conclusion - because exactly
    ONE kind of real investigative event exists today: a single grounded
    model call that bundles evidence-examination, conclusion,
    uncertainty, and a human-judgment signal into one round trip (see
    services/requirement_investigation.py's own docstring on why this is
    deliberately not yet a multi-step agentic loop). Distinct kinds
    become honest to add only once an actual multi-round loop produces
    them as separate observable events - inventing that taxonomy now,
    before anything real produces a second kind, would be modeling a
    capability that doesn't exist rather than describing one that does.

    `evidence_requested` is a plain description of what evidence
    CATEGORIES were gathered - honest because retrieval today is fixed/
    deterministic (see _handle_investigate_requirement), not a claim
    that the model itself chose what to look at.

    `evidence_examined_ids` references real governed records by id
    (adjudication/finding/relationship/accepted-knowledge ids already
    returned by requirement_adjudications_for/requirement_evidence) -
    never a text copy, so this can never drift from the record it
    describes, and every id here is independently look-up-able.

    `branched_from_step_id` is the schema's extension point for a future
    Investigation that exists because an earlier step's own
    open_questions prompted it - present now so no migration is needed
    later, but nothing in this pass ever sets it: whether an open
    question should ever automatically or manually spin off a new
    Investigation is a real product decision, not inferred here.

    The human-gate itself is NOT reinvented here - `needs_human_judgment`
    is a signal surfaced for display, but the actual gated act is the
    EXISTING ReviewerValidation on whatever Finding this step produced
    (`analysis_id` -> AnalysisRun.finding_ids). One Approval Gate
    mechanism, not two.
    """

    id: str
    project_id: str
    case_id: str
    step_kind: str
    anchor: dict  # asdict(Anchor) - what was being investigated
    question: str  # the reviewer's own question, verbatim
    triggered_by_actor: str
    created_at: str
    evidence_requested: list[str] = field(default_factory=list)
    evidence_examined_ids: dict = field(default_factory=dict)
    ran: bool = False
    skipped_reason: Optional[str] = None
    assessment: Optional[str] = None
    confidence: Optional[float] = None
    supporting_points: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    needs_human_judgment: bool = True
    analysis_id: Optional[str] = None
    branched_from_step_id: Optional[str] = None


@dataclass
class Claim:
    """
    CLAUDE-MM7: one inspectable, individually-classified, individually-
    cited unit of a governed investigation's answer - Section 7's own
    "represent an answer as inspectable claims rather than one
    undifferentiated paragraph." Attaches to an InvestigationStep
    (`investigation_step_id`) exactly the way an Artifact attaches to an
    AnalysisRun - the step is the container/audit-trail (question, what
    evidence categories were gathered, when), a Claim is one of
    potentially several individually-adoptable statements that step
    produced.

    `evidence_links` is a list of `{"object_type", "object_id"}` dicts -
    ALWAYS a reference to an already-governed, already-persisted record
    (validated by record_investigation_claim against the same
    `_MM6_ENDPOINT_LISTS` MM6 already uses), NEVER free text. This is
    the concrete, structural answer to Section 9's "no citation
    laundering": there is no code path by which a Claim can cite a
    source name, page, cell, or region that does not actually exist as
    a real object in THIS project - a hallucinated citation is not
    merely discouraged, it is impossible to persist.

    `contradiction_relationship_ids` references real, already-recorded
    MM6 Relationships (relationship_type CONTRADICTS by convention, but
    validated only for existence/project membership, not type, the same
    tolerant discipline the rest of this module already applies) - a
    Claim never re-describes a contradiction in its own words when a
    governed Relationship already says so.

    `confidence_state` (KNOWN_CONFIDENCE_STATES) is the ONLY confidence
    signal a Claim carries - deliberately no float alongside it (Section
    5: "do not use vague confidence percentages without a defined and
    testable meaning").

    `adoption_state` starts at CLAIM_ADOPTION_PROPOSED unconditionally,
    regardless of `claim_class` or `author_type` - even a
    directly_verified claim is a PROPOSAL until a human adopts it
    (Section 15: "AI-generated answers and relationships must remain
    proposals until appropriately reviewed" - this module reads that as
    "not yet human-adopted", not "not yet AI-generated", so the same
    discipline applies uniformly to every claim_class, not only ai_
    proposal). `derived_observation_id`/`finding_id` are set only once
    accept_claim_as_observation/accept_claim_as_finding actually creates
    the corresponding governed record - never guessed or pre-allocated.
    """

    id: str
    project_id: str
    investigation_step_id: str
    statement: str
    claim_class: str  # KNOWN_CLAIM_CLASSES (closed)
    method: str  # KNOWN_ANALYTICAL_METHODS (open-world)
    confidence_state: str  # KNOWN_CONFIDENCE_STATES (closed)
    author_type: str  # KNOWN_OBSERVATION_AUTHOR_TYPES (closed) - human/deterministic_process/ai
    created_by: str
    created_at: str
    evidence_links: list = field(default_factory=list)  # [{"object_type","object_id"}]
    evidence_excluded: list = field(default_factory=list)  # [{"object_type","object_id","reason"}]
    contradiction_relationship_ids: list = field(default_factory=list)
    assumptions: list = field(default_factory=list)
    recommended_next_check: Optional[str] = None
    adoption_state: str = CLAIM_ADOPTION_PROPOSED
    adopted_by: Optional[str] = None
    adopted_at: Optional[str] = None
    adoption_reason: Optional[str] = None
    derived_observation_id: Optional[str] = None
    finding_id: Optional[str] = None


@dataclass
class WorkProductSection:
    """
    CLAUDE-MM8 Section 10: "avoid reducing every professional artifact to
    one giant rich-text box" - one structured, individually addressable
    unit of a WorkProduct's own content. `section_type` is open-world
    (e.g. "narrative"/"risk"/"team_member"/"citation"/"finding_summary") -
    the SAME object shape serves a risk register's own rows, an RFI's own
    question/background blocks, and a report's own narrative paragraphs,
    distinguished only by `section_type` and whatever keys `content`
    happens to carry for that type - not a family of subclasses.

    `content_class` (KNOWN_CONTENT_CLASSES, closed) is Section 8's own
    provenance answer for THIS section specifically - never inferred from
    the parent WorkProduct's own author. `evidence_links` are validated
    exactly like Claim's own (real, already-governed objects only, via
    `_resolve_mm6_endpoint`) - a section can cite an EvidenceItem, a
    Claim, a Finding, another WorkProduct, etc.

    `accepted_by`/`accepted_at` are DELIBERATELY separate from
    `content_class`: accepting an AI-proposed section as good-enough-to-
    keep is a human sign-off, but it does NOT rewrite the section's own
    honest origin - `content_class` stays `ai_proposed` (or becomes
    `edited_ai_proposal` if it was also edited) forever, satisfying
    Section 8's "AI content must not become human-approved simply because
    a user opens the document" literally: acceptance and authorship are
    two different facts, never conflated into one field.

    `edit_history` records before/after (Section 16: "record before/after
    values for structured edits") - append-only, never trimmed.

    `removed` is a soft-delete flag (Section 16: "do not hard-delete
    consequential records without existing governance") - a removed
    section is excluded from rendering/export but never actually deleted
    from the list, so its own history remains inspectable.
    """

    id: str
    section_type: str
    content: dict
    content_class: str  # KNOWN_CONTENT_CLASSES (closed)
    author: str
    created_at: str
    order_index: int
    evidence_links: list = field(default_factory=list)  # [{"object_type","object_id"}]
    modified_at: Optional[str] = None
    accepted_by: Optional[str] = None
    accepted_at: Optional[str] = None
    edit_history: list = field(default_factory=list)  # [{"before","after","actor","at","reason"}]
    removed: bool = False
    removed_by: Optional[str] = None
    removed_at: Optional[str] = None


@dataclass
class WorkProductExportRecord:
    """One real export event (Section 19) - never inferred from the
    WorkProduct's own state, always an explicit record of an actual
    export call. `checksum` is of the EXPORTED FILE BYTES themselves,
    distinct from WorkProduct.issued_checksum (of the governed section
    content) - the two answer different integrity questions ("does this
    downloaded file match what I have on record" vs. "has the issued
    content itself been tampered with")."""

    format: str
    exported_at: str
    exported_by: str
    checksum: str


@dataclass
class WorkProductReview:
    """Section 17's own required review record - reviewer/date/role/
    comments/conditions/evidence version/unresolved contradiction, all
    preserved (never overwritten by a later review - see
    record_work_product_review, append-only like ReviewerValidation)."""

    reviewer: str
    role: str
    decision: str  # WORK_PRODUCT_STATE_REVIEWED | WORK_PRODUCT_STATE_REVISIONS_REQUIRED
    reviewed_at: str
    comments: Optional[str] = None
    conditions: Optional[str] = None
    unresolved_contradiction: bool = False


@dataclass
class WorkProduct:
    """
    CLAUDE-MM8: a mutable, editable, governed professional artifact -
    Section 5's own strict distinction ("work product is not evidence")
    means this object is NEVER itself an EvidenceItem, no matter how many
    other objects cite it; `_MM6_ENDPOINT_LISTS` makes it CITABLE (a
    Relationship/Claim/another WorkProduct may point at it), which is a
    different, one-way fact from being evidence.

    `sections` are embedded directly (asdict(WorkProductSection) dicts) -
    a WorkProduct is always read/written as one governed unit, the same
    single-owner-object pattern Case.conversation/Case.finding_ids
    already use, not a second top-level `ProjectWorkspace` list requiring
    its own cross-referencing.

    `case_id` is OPTIONAL (mirrors record_analysis's own Project-vs-Case
    duality) - a work product started from a Case-scoped Finding/
    Investigation naturally inherits that case_id, but a Project-level
    artifact (e.g. a project-wide team list) is equally legitimate with
    none.

    `issued_checksum` is set exactly once, at `issue_work_product` time,
    and never changes afterward - Section 18's own "frozen, identifiable
    output" guarantee. `version` starts at 1 and increments only when
    `revise_work_product` creates a NEW WorkProduct - the original's own
    `version` field never changes after it is set.
    """

    id: str
    project_id: str
    artifact_type: str  # open-world: "report"/"risk_register"/"team_list"/...
    title: str
    created_by: str
    created_at: str
    modified_at: str
    case_id: Optional[str] = None
    source_finding_id: Optional[str] = None
    source_investigation_step_id: Optional[str] = None
    sensitivity_classification: Optional[str] = None
    state: str = WORK_PRODUCT_STATE_DRAFT
    version: int = 1
    sections: list = field(default_factory=list)  # [asdict(WorkProductSection)]
    reviews: list = field(default_factory=list)  # [asdict(WorkProductReview)]
    exports: list = field(default_factory=list)  # [asdict(WorkProductExportRecord)]
    issued_at: Optional[str] = None
    issued_by: Optional[str] = None
    issued_checksum: Optional[str] = None


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
    # CLAUDE-P30: the Client/Owner-side counterpart to question_text/
    # issued_by above -- set only by CaseWorkspaceStore.respond_to_rfi_draft,
    # only once, only on an already-issued draft. Never written by the
    # same actor/method that drafted or issued the question: origination
    # and response are two separate, environment-gated capabilities
    # (services/environment_capabilities.py's "rfi_originate"/"rfi_respond").
    response_text: Optional[str] = None
    responded_at: Optional[str] = None
    responded_by: Optional[str] = None


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

    CLAUDE-MM6 additions, both backward-compatible (every pre-MM6 record
    simply lacks these keys and loads with the honest default, the same
    shape every prior addition to this codebase's own dataclasses
    already uses): `reason` (Section 6's own "reason or description" -
    a short human-entered explanation, distinct from `confidence`, which
    is a number, not prose); `validation_state` (None = ordinary,
    RELATIONSHIP_VALIDATION_DISPUTED/_REJECTED = an explicit human
    judgment AGAINST this edge - see dispute_relationship/
    reject_relationship below). Endpoint VERSION binding (Section 6/14 -
    "source and target versions") is deliberately NOT a stored field
    here: a from_id/to_id pointing at an EvidenceItem/AddressableRegion/
    Source already carries (or is reachable to) that object's own
    version/supersession state, so recording a SECOND, potentially-
    drifting copy of "the version this was created against" would
    violate the same "store flat, derive at read time" principle every
    citation in this codebase already follows - resolve_relationship_
    status (below) derives staleness from the ENDPOINT's own current
    state at read time instead.
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
    reason: Optional[str] = None
    validation_state: Optional[str] = None  # None | RELATIONSHIP_VALIDATION_DISPUTED | RELATIONSHIP_VALIDATION_REJECTED


CARRIED_FORWARD_OBJECT_TYPE_FINDING = "finding"
CARRIED_FORWARD_OBJECT_TYPE_REVIEW_MESSAGE = "review_message"

KNOWN_CARRIED_FORWARD_OBJECT_TYPES = (
    CARRIED_FORWARD_OBJECT_TYPE_FINDING,
    CARRIED_FORWARD_OBJECT_TYPE_REVIEW_MESSAGE,
)


@dataclass
class CarriedForwardAdoption:
    """
    Selective Adopt/Carry-Forward tranche: the one governed record that
    answers, uniformly across every supported object type, "which active
    items in a derived Case were deliberately carried forward from its
    archived predecessor, from which historical item, by whom, and
    when" - a single, cheaply filterable list rather than a different
    query shape per adopted object type.

    Deliberately its own minimal primitive, not a reuse of the
    Relationship substrate (contrast with CaseRecord.derived_from_case_id
    + the RELATIONSHIP_TYPE_DERIVED_FROM Relationship, which correctly
    reuses Relationship for a Case-to-Case edge): Relationship's
    from/to-object schema has no source-Case/target-Case concept of its
    own, and reconstructing "which Case did this get adopted INTO" from
    it would require re-deriving that through `_cases_referencing_object`
    on every query. This record exists specifically because that Case-
    to-Case-via-one-item bridge is this whole capability's job, and no
    existing primitive expresses it directly.

    object_type is open-world (KNOWN_CARRIED_FORWARD_OBJECT_TYPES) -
    deliberately narrow today (Finding, ReviewMessage only - see
    adopt_finding_into_case/adopt_review_message_into_case), extensible
    later without a schema change, same discipline as Supersession's
    predecessor_type/successor_type.

    This record never substitutes for the object-type-native pointer
    each successor object also carries - Finding's accompanying
    AnalysisRun/AnalysisTrigger.trigger_reference_id, ReviewMessage's
    own related_object_type/related_object_id - both exist together,
    the same denormalized-pointer-plus-governed-record pattern already
    used throughout this file (Source.supersedes_source_id +
    Supersession; CaseRecord.derived_from_case_id + the derived_from
    Relationship).
    """

    id: str
    project_id: str
    source_case_id: str
    target_case_id: str
    object_type: str
    source_object_id: str
    successor_object_id: str
    adopted_by: str
    adopted_at: str


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


# -- Case visibility (ratified governance baseline, Private -> Shared tranche) --
# Deliberately minimal for this tranche - only the two states the ratified
# Investigation Lifecycle spec authorizes now. COLLABORATIVE and ARCHIVED
# are named but NOT added here (see governance/specified-unbuilt/
# investigation-lifecycle-extensions.md) - adding their constants ahead of
# their own governed transitions would misrepresent them as available.
CASE_VISIBILITY_PRIVATE = "private"
CASE_VISIBILITY_SHARED = "shared"
# Collaboration threshold + irreversibility tranche: added now that Private
# <-> Shared exists to build on. COLLABORATIVE is a distinct THIRD state
# from SHARED - "visible to others" and "another party has genuinely
# contributed" are different facts (Constitutional Invariant 12), and
# collapsing them would silently permit exactly the privacy-reversal
# Invariant 12 exists to prevent. Archive is still deliberately NOT added
# here - it remains genuinely unbuilt, not implied by this tranche.
CASE_VISIBILITY_COLLABORATIVE = "collaborative"

KNOWN_CASE_VISIBILITY_STATES = (
    CASE_VISIBILITY_PRIVATE,
    CASE_VISIBILITY_SHARED,
    CASE_VISIBILITY_COLLABORATIVE,
)

# -- Case lifecycle status: Archive tranche -------------------------------------
# Architectural correction made explicit here, not silently: ARCHIVED is NOT
# a fourth visibility value. Visibility (PRIVATE/SHARED/COLLABORATIVE)
# answers "who can participate/see"; status (OPEN/ARCHIVED) answers
# "whether the Case is still alive and mutable" - two orthogonal axes, not
# one enum. A Case can therefore be PRIVATE+ARCHIVED or COLLABORATIVE+
# ARCHIVED equally validly. This reuses CaseRecord's own pre-existing
# `status` field (`status: str = "open"`, present since before this whole
# tranche sequence began) rather than inventing a new field - that field
# was always the right home for this, it simply had no enforced values or
# write-path guards until now (see _require_case_not_archived below).
CASE_STATUS_OPEN = "open"
CASE_STATUS_ARCHIVED = "archived"

KNOWN_CASE_STATUSES = (
    CASE_STATUS_OPEN,
    CASE_STATUS_ARCHIVED,
)

# CLAUDE-P11: the Case-level HYPOTHESIS verdict - a distinct question from
# CASE_STATUS above (existence/lifecycle: is this Case still open or
# archived) and from Disposition (what happens to one FINDING next). This
# is "did the premise that justified opening this Investigation hold up",
# at the Case's own grain - the same never-conflate-distinct-questions
# discipline Disposition/ReviewerValidation/RequirementAdjudication/
# Requirement.status all already keep separate from each other.
#
# A deliberately small, closed vocabulary - matching REQUIREMENT_
# ADJUDICATION_OUTCOMES' own restraint. "unresolved" is deliberately NOT
# a member: like REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED, it is
# never a stored value, only ever the DERIVED absence of any CaseOutcome
# record (see case_outcome_state) - an un-adjudicated Case has no row,
# not a placeholder row saying so.
CASE_OUTCOME_CONFIRMED = "confirmed"    # the hypothesis survived scrutiny to the point of mattering
CASE_OUTCOME_DEFEATED = "defeated"      # evidence contradicted the hypothesis that prompted this Investigation
CASE_OUTCOME_DUPLICATE = "duplicate"    # the same question as another Case, already covered there
CASE_OUTCOME_IRRELEVANT = "irrelevant"  # this Investigation should not have been opened - poorly grounded trigger

CASE_OUTCOME_STATES = (
    CASE_OUTCOME_CONFIRMED,
    CASE_OUTCOME_DEFEATED,
    CASE_OUTCOME_DUPLICATE,
    CASE_OUTCOME_IRRELEVANT,
)

# The derived state case_outcome_state() returns when no CaseOutcome has
# been recorded - never accepted by record_case_outcome, never stored.
CASE_OUTCOME_STATE_UNRESOLVED = "unresolved"

# CLAUDE-P13R: autonomous investigation, begun opportunistically inside
# reasoning already legitimately running (services/requirement_
# investigation.py's real call), never from a free-running scheduler. A
# named, attributable system actor - never a real username, never bare
# None (which already means something else on CaseRecord.created_by:
# "predates Case visibility") - so an autonomous Case is unambiguously
# distinguishable from every human-created one by this one field, not a
# second parallel flag.
AUTONOMOUS_INVESTIGATOR_ACTOR = "archiosk-autonomous-investigator"

# Stop conditions (Prompt: "bounded API/cost/branch controls... rather
# than interrupting the reviewer"). A global per-project cap plus a
# same-anchor duplicate check are deliberately the ONLY two guards - see
# can_open_autonomous_case_for's own docstring for why finer-grained
# topic-level dedup is a real, named gap rather than something faked
# with a naive heuristic.
MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT = 3
AUTONOMOUS_BRANCH_CONFIDENCE_THRESHOLD = 0.75

# CLAUDE-P13R: three distinct ways a Case comes to exist - a human
# creating one outright (create_case/quick_start), a human accepting the
# aperture's escalation offer (start_investigation_from_aperture - the
# Case is human-authorized but the QUESTION that prompted it was
# machine-recognized), and the machine opening one entirely on its own
# during otherwise-normal reasoning. Case creation is never itself
# authority (see CaseOutcome's own docstring) regardless of which of
# these three produced it - only investigation_quality_rollup_for_
# project's bucketing differs by origin, nothing about a Case's
# governance status does.
CASE_ORIGIN_DIRECT = "direct"
CASE_ORIGIN_ANCHOR_ESCALATED = "anchor_escalated"
CASE_ORIGIN_AUTONOMOUS = "autonomous"

# CLAUDE-P12R: a project party - Owner, Design-Builder, Proponent,
# Consultant, etc. Open-world (like REQUIREMENT_CLASSIFICATION or
# RELATIONSHIP_TYPE): a real project may have a party this list doesn't
# anticipate, and rejecting that would be worse than tolerating an
# unrecognized-but-preserved role_type.
PARTICIPANT_ROLE_OWNER = "owner"
PARTICIPANT_ROLE_DESIGN_BUILDER = "design_builder"
PARTICIPANT_ROLE_PROPONENT = "proponent"
PARTICIPANT_ROLE_CONSULTANT = "consultant"
PARTICIPANT_ROLE_CONTRACTOR = "contractor"
PARTICIPANT_ROLE_OTHER = "other"

KNOWN_PARTICIPANT_ROLES = (
    PARTICIPANT_ROLE_OWNER,
    PARTICIPANT_ROLE_DESIGN_BUILDER,
    PARTICIPANT_ROLE_PROPONENT,
    PARTICIPANT_ROLE_CONSULTANT,
    PARTICIPANT_ROLE_CONTRACTOR,
    PARTICIPANT_ROLE_OTHER,
)

# CLAUDE-P12R: risk/opportunity polarity - a canonical governed object's
# meaning FROM one participant's position, never a rewrite of the object
# itself. A deliberately small, closed vocabulary (like CASE_OUTCOME_
# STATES) - "shared"/"transferred"/etc. are real words the underlying
# idea uses, but the polarity a record actually stores stays this three-
# way axis; finer distinctions belong in `reasoning` (free text), not in
# a proliferating enum, until real usage shows three isn't enough.
PERSPECTIVE_POLARITY_RISK = "risk"
PERSPECTIVE_POLARITY_OPPORTUNITY = "opportunity"
PERSPECTIVE_POLARITY_NEUTRAL = "neutral"

KNOWN_PERSPECTIVE_POLARITIES = (
    PERSPECTIVE_POLARITY_RISK,
    PERSPECTIVE_POLARITY_OPPORTUNITY,
    PERSPECTIVE_POLARITY_NEUTRAL,
)

# Whose judgment a PerspectiveAssessment records - never inferred, always
# one of these two, explicitly.
PERSPECTIVE_ORIGIN_HUMAN = "human"
PERSPECTIVE_ORIGIN_MACHINE = "machine"

KNOWN_PERSPECTIVE_ORIGINS = (
    PERSPECTIVE_ORIGIN_HUMAN,
    PERSPECTIVE_ORIGIN_MACHINE,
)


@dataclass
class Participant:
    """
    CLAUDE-P12R (both sides of procurement / represented-party
    perspective): a party to the project - Owner, Design-Builder,
    Proponent, Consultant, etc. Exists so "who does the current reviewer
    represent" has something real to point at, and so a Relationship/
    Anchor can reference a Participant like any other object kind
    (OBJECT_KIND_PARTICIPANT). Deliberately minimal - a name and an
    open-world role, nothing about contact info/authority/contract
    terms, which belong to a real contract-management capability this
    is not attempting to become.
    """

    id: str
    project_id: str
    name: str
    role_type: str  # open-world, KNOWN_PARTICIPANT_ROLES
    created_at: str
    created_by: str
    note: Optional[str] = None


@dataclass
class PerspectiveAssessment:
    """
    CLAUDE-P12R: canonical governed object + represented party ->
    perspective-sensitive interpretation. This is the ENTIRE mechanism -
    never a rewrite of the Requirement/Finding/Source it's about, never a
    second copy of evidence, just an attributed, append-only annotation
    of what a governed object looks like FROM one Participant's position.

    Same anchor shape as Conversation/ReviewThread (asdict(Anchor)) - not
    a new attachment mechanism. `origin` distinguishes a human's own
    explicit mark - a governed reviewer act, NEVER inferred from cursor/
    mouse position or any other passive signal - from the machine's
    independently-reached assessment (see services/requirement_
    investigation.py's optional risk-polarity extension). Both are
    stored identically, so "do the human and machine agree" is a plain
    read of two records sharing the same anchor+participant (see
    perspective_convergence_for), not a second comparison mechanism.

    `confidence`/`investigation_step_id` are only ever set when
    origin == PERSPECTIVE_ORIGIN_MACHINE; `recorded_by` only when
    origin == PERSPECTIVE_ORIGIN_HUMAN - enforced in record_
    perspective_assessment, not just documented here.
    """

    id: str
    project_id: str
    anchor: dict  # asdict(Anchor)
    participant_id: str  # whose perspective this assessment is FROM
    polarity: str  # KNOWN_PERSPECTIVE_POLARITIES
    origin: str  # KNOWN_PERSPECTIVE_ORIGINS
    reasoning: str
    created_at: str
    recorded_by: Optional[str] = None
    confidence: Optional[float] = None
    investigation_step_id: Optional[str] = None


# -- Go/No-Go decision family (CLAUDE-P30) ---------------------------------
#
# Both Project Operating Environments need a Go/No-Go decision, but for
# different reasons at different stages -- see
# services/environment_capabilities.py's CLIENT_OWNER_DECISION_STAGES /
# DESIGN_BUILDER_PROPONENT_DECISION_STAGES. This is the "parallel
# capability family" shape: one shared, governed record type (this
# class), validated against whichever stage vocabulary the project's own
# locked environment actually uses (see
# CaseWorkspaceStore.record_go_no_go_decision) -- never one side's
# checklist quietly reused for the other.

GO_NO_GO_DECISION_GO = "go"
GO_NO_GO_DECISION_NO_GO = "no_go"
GO_NO_GO_DECISION_CONDITIONAL_GO = "conditional_go"

GO_NO_GO_DECISIONS = (
    GO_NO_GO_DECISION_GO,
    GO_NO_GO_DECISION_NO_GO,
    GO_NO_GO_DECISION_CONDITIONAL_GO,
)


@dataclass
class GoNoGoAssessment:
    """
    One governed decision record answering "should this project/pursuit
    continue past this stage." `operating_environment` is denormalized
    from the workspace's own locked field AT THE TIME OF THIS DECISION --
    read-only here, never independently settable, so a decision record
    always honestly reflects which vocabulary was actually in force when
    it was made (relevant only in the theoretical case the vocabulary
    itself changes in a future release; today it is simply a copy).

    `anomalies` is open-world free text (like Relationship.relationship_
    type) rather than a closed enum -- the conditions that could justify
    a No-Go are numerous, genuinely environment-specific, and expected to
    grow with real usage; a closed vocabulary here would be either
    incomplete on day one or an ever-growing enum masquerading as one.
    `decision` itself IS closed (GO_NO_GO_DECISIONS): the outcome
    vocabulary is small, stable, and identical in shape across both
    environments even though the stages and anomalies leading to it are
    not.
    """

    id: str
    project_id: str
    operating_environment: str
    decision_stage: str
    decision: str
    anomalies: list  # list[str], open-world
    rationale: str
    decided_by: str
    decided_at: str
    # CLAUDE-P38 (OBS-04): the decider's role at decision time - a bare
    # username alone left "who has the authority to make this call"
    # implicit. Optional/defaulted so existing serialized records
    # (pre-dating this field) round-trip unchanged.
    decided_by_role: Optional[str] = None


@dataclass
class CaseRecord:
    """
    `visibility` defaults to CASE_VISIBILITY_PRIVATE unconditionally -
    "newly created investigative Cases default to PRIVATE" per the
    ratified spec, not an open-world/caller-chosen value in this
    tranche. `created_by` is optional (None) only for backward
    compatibility with the many pre-existing callers of create_case()
    across Foundation Batches A-K that never passed an actor - a real,
    new Case created through the current route wiring always has one.
    A Case with created_by=None cannot be shared (see share_case) -
    there is no ambient/inferred owner to authorize the transition,
    an honest limitation rather than a silently-invented one.
    `shared_by`/`shared_at` record the transition directly on the
    record itself, alongside (not instead of) the GovernanceLog event
    share_case also writes - the same denormalized-pointer-plus-
    separate-governed-record pattern Source.supersedes_source_id and
    Supersession already use together.
    """

    id: str
    project_id: str
    title: str
    objective: str
    created_at: str
    status: str = CASE_STATUS_OPEN
    visibility: str = CASE_VISIBILITY_PRIVATE
    created_by: Optional[str] = None
    shared_by: Optional[str] = None
    shared_at: Optional[str] = None
    # Archive fields (lifecycle status, orthogonal to visibility - see the
    # CASE_STATUS_* comment above). archive_prior_visibility preserves what
    # visibility was AT archive time - archiving never changes visibility
    # itself, but this makes the pre-archive state independently legible
    # without needing to consult GovernanceLog.
    archived_by: Optional[str] = None
    archived_at: Optional[str] = None
    archive_authority: Optional[str] = None  # "owner" or "admin_override"
    archive_prior_visibility: Optional[str] = None
    # Collaboration threshold fields (Constitutional Invariant 12). Set
    # exactly once, atomically alongside the qualifying non-owner write
    # that triggers them - see _cross_collaboration_threshold_if_qualifying.
    # Never cleared, never mutated again once set (irreversibility is
    # enforced by rejecting the transition entirely, not by these fields
    # ever changing back).
    collaboration_established_by: Optional[str] = None
    collaboration_established_at: Optional[str] = None
    collaboration_contribution_type: Optional[str] = None
    collaboration_contribution_id: Optional[str] = None
    # Retraction fields (SHARED -> PRIVATE, pre-threshold only). Deliberately
    # does NOT clear shared_by/shared_at on retraction - "do not delete
    # historic evidence that the Case had previously been shared" (ratified
    # spec) - both the prior share and the later retraction remain visible
    # on the record itself, non-destructively.
    retracted_by: Optional[str] = None
    retracted_at: Optional[str] = None
    # Derivation lineage (Case-lineage tranche). Denormalized forward
    # pointer to the archived Case this one was derived from - cheap,
    # direct querying, same pattern as Source.supersedes_source_id
    # alongside Supersession. The authoritative, structural, queryable
    # record is the accompanying Relationship (RELATIONSHIP_TYPE_DERIVED_
    # FROM); both are written together in derive_case_from_archive so
    # they can never drift apart. None for every Case that is not itself
    # a derivation.
    derived_from_case_id: Optional[str] = None
    source_ids: list[str] = field(default_factory=list)
    conversation: list[dict] = field(default_factory=list)
    analysis_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    activity_ids: list[str] = field(default_factory=list)


@dataclass
class CaseOutcome:
    """
    CLAUDE-P11: a human's verdict on whether the hypothesis that justified
    opening this Case held up - CASE_OUTCOME_STATES above. Append-only,
    like ReviewerValidation/Disposition/RequirementAdjudication - a later
    record supersedes an earlier one IN EFFECT (see
    latest_case_outcome_for/case_outcome_state), never overwrites or
    deletes it, so a reviewer who first calls something "defeated" and
    later reopens it as "confirmed" leaves both judgments on the record.

    This is deliberately the ONLY place a machine-generated investigation
    hypothesis is ever declared right or wrong - the machine (see
    services/requirement_investigation.py, conversation_interpreter.py's
    needs_case/start_investigation_from_aperture) may say "there is enough
    here to investigate" by recognizing a pattern and a human accepting
    the escalation offer; it never gets to also say "and this hypothesis
    survived." `recorded_by` is never machine-populated.

    `duplicate_of_case_id` is only meaningful when outcome ==
    CASE_OUTCOME_DUPLICATE - a plain id reference (like Source.supersedes_
    source_id), not a copy of the other Case's content.
    """

    id: str
    project_id: str
    case_id: str
    outcome: str  # CASE_OUTCOME_STATES
    reasoning: str
    recorded_by: str
    recorded_at: str
    duplicate_of_case_id: Optional[str] = None


@dataclass
class ProjectContextEntry:
    """
    CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01: one recorded statement of the
    Project's current direction/orientation. Append-only, exactly like
    CaseOutcome above - a later entry is the CURRENT one in effect
    (ProjectWorkspace.project_context_entries[-1]), but every earlier
    entry remains on the record, with its own text/author/role/
    timestamp, never mutated or removed. See
    ProjectWorkspace.project_context_entries' own docstring for why this
    shape rather than a new versioning subsystem.
    """

    id: str
    project_id: str
    text: str
    created_at: str
    created_by: str
    created_by_role: Optional[str] = None


@dataclass
class Table:
    """
    Prompt 18 / Batch J: structured tabular evidence, first-class rather
    than something every consumer re-derives by reaching into
    ParsedDocument.tables independently. A Table is the governed record
    of "this table exists at this location in this Source" - its rows
    live in their own list (see TableRow) linked by `id`, the same
    FK-not-nesting pattern already used for ReviewThread/ReviewMessage
    rather than a new convention.

    `source_location` is a physical position within the Source (line
    range) - not a resolved SourceReference, since a Table describing
    where it physically sits is a different fact from something ELSE
    citing it (see SourceReference below). `section_context`, when
    determinable, is the nearest preceding heading - a convenience, not
    a guarantee (left None rather than guessed when no heading precedes
    it in the extracted text).

    Table ordinal (creation order) is NOT treated as permanent identity
    (Prompt 18 #4) - `id` is the only stable identity; `source_location`
    is the strongest available position reference, kept alongside it.
    """

    id: str
    project_id: str
    source_id: str
    headers: list[str]
    source_location: dict  # {"start_line": int, "end_line": int}
    created_at: str
    created_by: str
    title: Optional[str] = None
    section_context: Optional[str] = None
    extraction_engine: Optional[str] = None
    extraction_version: Optional[str] = None


@dataclass
class TableRow:
    """
    Prompt 18 #5: a Table's row, individually referencable by `id` -
    "Appendix OPR-1, Row 20" becomes a real record, not merely
    "somewhere in the Functional Program table."

    `cells` are embedded (not a separate top-level list, unlike Table/
    TableRow themselves) - a cell only ever makes sense in the context of
    its own row, the same reasoning already applied to Anchor (embedded
    in ReviewThread) and ExpectationItem (embedded in
    ExpectedInformationProfile). Each cell dict still carries its own
    stable `id` (Prompt 18 #3: "another object can reliably point to...
    this specific cell/value") - see resolve_table_cell below for how a
    Relationship can address one directly despite the embedding.

    Each cell dict holds: {"id", "header", "raw_value", "parsed_value",
    "qualifier", "unit"}. `raw_value` is NEVER discarded when a
    `parsed_value` is derived (Prompt 18 #6) - both are always present.
    `qualifier` preserves recognized non-numeric placeholders ("—", "TBD",
    "approx.", "included in subtotal", etc, Prompt 18 #7) rather than
    coercing them - a blank cell or em dash is never silently treated as
    zero.

    `source_row_identifier` is the row's OWN stated identity where the
    table provides one (e.g. a "#" column's value, "20") - kept distinct
    from `row_index` (structural position, 0-based), since a table could
    in principle omit or renumber its own identifier column.
    """

    id: str
    table_id: str
    project_id: str
    row_index: int
    cells: list[dict]
    created_at: str
    source_row_identifier: Optional[str] = None
    source_location: Optional[dict] = None  # {"line": int} where determinable


@dataclass
class SourceReference:
    """
    Prompt 18 #14/#23: a governed record of an EXPLICIT citation found in
    a Source's own text ("see Section 14", "Sections 10 through 14",
    "Figure OPR-2.1") - representation of the citation ITSELF, distinct
    from any richer semantic relationship (depends_on/contradicts/
    implements/etc) analysis might later assign (Prompt 18 #15). A
    Relationship may be created FROM a resolved SourceReference, but a
    SourceReference is not itself a Relationship - it is closer to
    Requirement (source-stated meaning) than to an analysis conclusion.

    `reference_text` is the ORIGINAL phrasing verbatim (Prompt 18 #17) -
    never lost even when `resolution_status` is anything other than a
    clean single resolution. `reference_type` is open-world
    (KNOWN_REFERENCE_TYPES). `resolved_target_ids` may hold zero, one, or
    many ids depending on `resolution_status` (a CLOSED, evaluator-owned
    vocabulary - see RESOLUTION_STATUS_*), always reflecting only targets
    actually confirmed to exist (Prompt 18 #16) - a syntactically-valid
    range is never expanded into ids that don't correspond to anything
    real in the current governed state.

    `origin_context` names where the reference was found - a clause
    (`{"location_type": "clause", "section": ...}`, reusing the existing
    Requirement.source_location shape rather than inventing a new one) or
    a table row (`{"location_type": "table_row", "table_row_id": ...}`).
    No new first-class Clause object was created for this (Prompt 18
    #20) - Markdown extraction's own section numbering is already a
    sufficient, resolvable target.
    """

    id: str
    project_id: str
    source_id: str
    reference_text: str
    reference_type: str  # open-world, KNOWN_REFERENCE_TYPES
    resolution_status: str  # RESOLUTION_STATUS_* (closed)
    origin_context: dict
    created_at: str
    created_by: str
    resolved_target_type: Optional[str] = None  # open-world object kind, when resolved
    resolved_target_ids: list[str] = field(default_factory=list)
    resolution_method: Optional[str] = None
    confidence: Optional[float] = None
    extractor_version: Optional[str] = None


# -- CLAUDE-MM1: Multimodal Foundation and Evidence Contract -----------------
# The shared governed representation every later Camel stage (MM2-MM9) builds
# on - camel-multimodal-programme.md's own MM1 framing. Extends today's
# kernel, which addresses whole Source records, to sub-document regions (a
# page, a sheet range, a drawing detail, an image region) as first-class,
# addressable, citable things, and establishes the fact/measurement/expert-
# judgment/user-assumption/AI-suggestion distinction as a shared vocabulary
# rather than something each future modality would otherwise re-invent.
#
# Deliberately generalizes, rather than duplicates, what already exists:
# Table/TableRow (Batch J, above) remain the real, tested, tabular-specific
# realization of "structural subdivision" and "addressable cell" - nothing
# here replaces them, and a future adapter could describe a Table as a
# StructuralUnit without migrating Table/TableRow's own storage. Relationship
# (below) is reused as-is for every evidence relationship this contract
# needs - see the new RELATIONSHIP_TYPE_*/OBJECT_KIND_* constants above,
# not a second edge mechanism.

EVIDENCE_CLASS_DIRECT_SOURCE = "direct_source_evidence"
EVIDENCE_CLASS_EXTRACTED = "extracted_evidence"
EVIDENCE_CLASS_NORMALIZED = "normalized_evidence"
EVIDENCE_CLASS_USER_ENTERED = "user_entered_evidence"
EVIDENCE_CLASS_IMPORTED_STRUCTURED_VALUE = "imported_structured_value"
EVIDENCE_CLASS_CALCULATED_VALUE = "calculated_value"
EVIDENCE_CLASS_AI_GENERATED_PROPOSAL = "ai_generated_proposal"
EVIDENCE_CLASS_EXTERNALLY_RESEARCHED = "externally_researched_evidence"

# Deliberately CLOSED, unlike Source.kind/Requirement.subject_domain above -
# this is the one vocabulary the whole Camel programme's own "no silent
# AI-to-authoritative promotion" discipline leans on (camel-multimodal-
# programme.md's cross-cutting requirements). A caller naming some other
# distinction is a defect to surface immediately (__post_init__ below),
# not a value to preserve verbatim - the same closed-vocabulary discipline
# already applied to REQUIREMENT_ADJUDICATION_OUTCOMES/REVIEWER_VALIDATION_
# STATES for the same reason.
KNOWN_EVIDENCE_CLASSES = (
    EVIDENCE_CLASS_DIRECT_SOURCE,
    EVIDENCE_CLASS_EXTRACTED,
    EVIDENCE_CLASS_NORMALIZED,
    EVIDENCE_CLASS_USER_ENTERED,
    EVIDENCE_CLASS_IMPORTED_STRUCTURED_VALUE,
    EVIDENCE_CLASS_CALCULATED_VALUE,
    EVIDENCE_CLASS_AI_GENERATED_PROPOSAL,
    EVIDENCE_CLASS_EXTERNALLY_RESEARCHED,
)

OBSERVATION_AUTHOR_HUMAN = "human"
OBSERVATION_AUTHOR_DETERMINISTIC_PROCESS = "deterministic_process"
OBSERVATION_AUTHOR_AI = "ai"
KNOWN_OBSERVATION_AUTHOR_TYPES = (
    OBSERVATION_AUTHOR_HUMAN,
    OBSERVATION_AUTHOR_DETERMINISTIC_PROCESS,
    OBSERVATION_AUTHOR_AI,
)

# CLAUDE-MM2: PDF/document classification (Section 11 of this stage's own
# governing prompt) - what register_pdf_page_structure below actually found,
# never conflated with "extraction succeeded" vs "extraction failed" alone.
# text_native/image_only/mixed are outcomes of a SUCCESSFUL pypdf read (the
# document opened fine, its pages simply do or don't carry a text layer);
# extraction_failed/encrypted_or_unsupported are the read itself failing -
# a materially different fact a caller must not conflate with "this PDF has
# no text" (Section 11's own explicit "do not claim 'no usable document'
# merely because text is absent" applies to image_only, not to a genuine
# read failure, which is its own honest, separate state).
PDF_CLASSIFICATION_TEXT_NATIVE = "text_native"
PDF_CLASSIFICATION_IMAGE_ONLY = "image_only"
PDF_CLASSIFICATION_MIXED = "mixed"
PDF_CLASSIFICATION_EXTRACTION_FAILED = "extraction_failed"
PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED = "encrypted_or_unsupported"
KNOWN_PDF_CLASSIFICATIONS = (
    PDF_CLASSIFICATION_TEXT_NATIVE,
    PDF_CLASSIFICATION_IMAGE_ONLY,
    PDF_CLASSIFICATION_MIXED,
    PDF_CLASSIFICATION_EXTRACTION_FAILED,
    PDF_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
)

# CLAUDE-MM3: spreadsheet/workbook classification (Section 5/16 of this
# stage's own governing prompt) - same "successful read with a real
# finding" vs "read itself failed" distinction PDF classification above
# already establishes. SUPPORTED covers both .xlsx (openpyxl) and .csv
# (stdlib csv) once actually read; the other three are the read failing
# or being refused outright, never silently treated as "empty."
SPREADSHEET_CLASSIFICATION_SUPPORTED = "supported"
SPREADSHEET_CLASSIFICATION_MALFORMED = "malformed"
SPREADSHEET_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED = "encrypted_or_unsupported"
SPREADSHEET_CLASSIFICATION_EXCESSIVE_SIZE = "excessive_size"
KNOWN_SPREADSHEET_CLASSIFICATIONS = (
    SPREADSHEET_CLASSIFICATION_SUPPORTED,
    SPREADSHEET_CLASSIFICATION_MALFORMED,
    SPREADSHEET_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    SPREADSHEET_CLASSIFICATION_EXCESSIVE_SIZE,
)

# CLAUDE-MM4: drawing-sheet classification (Section 5/16/20) - the same
# "successful read with real sheets" vs. "read itself refused/failed"
# distinction PDF/spreadsheet classification above already establish.
# Covers BOTH drawing-oriented PDFs (pypdf-read) and standalone raster
# images (PNG/JPEG, PIL-read) under one shared vocabulary - a drawing
# sheet is a drawing sheet regardless of container format.
DRAWING_CLASSIFICATION_SUPPORTED = "supported"
DRAWING_CLASSIFICATION_MALFORMED = "malformed"
DRAWING_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED = "encrypted_or_unsupported"
DRAWING_CLASSIFICATION_EXCESSIVE_SIZE = "excessive_size"
KNOWN_DRAWING_CLASSIFICATIONS = (
    DRAWING_CLASSIFICATION_SUPPORTED,
    DRAWING_CLASSIFICATION_MALFORMED,
    DRAWING_CLASSIFICATION_ENCRYPTED_OR_UNSUPPORTED,
    DRAWING_CLASSIFICATION_EXCESSIVE_SIZE,
)

# CLAUDE-MM4 Section 10: title-block field reliability - every metadata
# field this stage exposes (sheet number/title/discipline/revision/issue
# date/consultant/scale) is tagged with exactly one of these, never
# silently promoted to a higher tier than the extraction method actually
# supports. Mirrors drawing_intake.py's own CONFIDENCE_HIGH/MEDIUM +
# STATUS_UNCONFIRMED/CONFIRMED/CORRECTED vocabulary in spirit, but this is
# a distinct, coarser tier set for STRUCTURAL-UNIT metadata display
# (Section 10's own five named states) rather than that module's
# candidate-confirmation workflow (a different, Project-identity-scoped
# concern - see that module's own docstring).
METADATA_RELIABILITY_DIRECTLY_EXTRACTED = "directly_extracted"
METADATA_RELIABILITY_USER_ENTERED = "user_entered"
METADATA_RELIABILITY_INFERRED = "inferred"
METADATA_RELIABILITY_UNAVAILABLE = "unavailable"
METADATA_RELIABILITY_UNVERIFIED = "unverified"
KNOWN_METADATA_RELIABILITY_TIERS = (
    METADATA_RELIABILITY_DIRECTLY_EXTRACTED,
    METADATA_RELIABILITY_USER_ENTERED,
    METADATA_RELIABILITY_INFERRED,
    METADATA_RELIABILITY_UNAVAILABLE,
    METADATA_RELIABILITY_UNVERIFIED,
)

# CLAUDE-MM5: image/screenshot/camera classification (Section 5/17/21) -
# the same "successful read" vs. "read itself refused/failed" distinction
# every prior MM stage's own classification vocabulary already
# establishes, scoped to what MM4's own DRAWING_CLASSIFICATION_* doesn't
# need to distinguish: an ordinary photo has no "encrypted" state, but DOES
# need its own honest "this container claims to be an image but isn't one
# we support" state, kept distinct from "malformed" (a real image file
# that failed to decode) per Section 5's own explicit classification list.
IMAGE_CLASSIFICATION_SUPPORTED = "supported"
IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT = "unsupported_format"
IMAGE_CLASSIFICATION_MALFORMED = "malformed"
IMAGE_CLASSIFICATION_EXCESSIVE_SIZE = "excessive_size"
KNOWN_IMAGE_CLASSIFICATIONS = (
    IMAGE_CLASSIFICATION_SUPPORTED,
    IMAGE_CLASSIFICATION_UNSUPPORTED_FORMAT,
    IMAGE_CLASSIFICATION_MALFORMED,
    IMAGE_CLASSIFICATION_EXCESSIVE_SIZE,
)

# CLAUDE-MM5 Section 10: every metadata field this stage surfaces is
# tagged with exactly one of these - "preserved internally / shown to
# authorized users / stripped from exported derivative / unavailable /
# unverified", Section 10's own five named states verbatim. Deliberately
# a SEPARATE vocabulary from METADATA_RELIABILITY_* above (MM4's own
# "how was this value obtained" question) - this one answers a different
# question, "who is allowed to see this value and in what form," which
# matters specifically because a field like GPS can be perfectly reliably
# extracted (METADATA_RELIABILITY_DIRECTLY_EXTRACTED) while still being
# EXPOSURE_INTERNAL_ONLY (Section 9/10: "do not automatically expose
# precise location metadata in the UI or external packets") - conflating
# the two questions into one tier would make that distinction
# unrepresentable.
METADATA_EXPOSURE_PRESERVED_INTERNAL = "preserved_internal"
METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED = "shown_to_authorized"
METADATA_EXPOSURE_STRIPPED_FROM_EXPORT = "stripped_from_export"
METADATA_EXPOSURE_UNAVAILABLE = "unavailable"
METADATA_EXPOSURE_UNVERIFIED = "unverified"
KNOWN_METADATA_EXPOSURE_TIERS = (
    METADATA_EXPOSURE_PRESERVED_INTERNAL,
    METADATA_EXPOSURE_SHOWN_TO_AUTHORIZED,
    METADATA_EXPOSURE_STRIPPED_FROM_EXPORT,
    METADATA_EXPOSURE_UNAVAILABLE,
    METADATA_EXPOSURE_UNVERIFIED,
)


@dataclass
class StructuralUnit:
    """
    A logical subdivision of a Source - a PDF/document page, a worksheet,
    a drawing sheet, an image frame, a slide, a section - generalized
    across modalities rather than named per-modality (Prompt/Section 4's
    own examples). `unit_type` is deliberately open-world: MM1 does not
    extract every modality yet (no OCR, no PDF page renderer, no drawing
    parser - see this stage's own deferrals), it only needs to make each
    later modality representable without a schema change once MM2-MM5
    actually produce them.

    `order_index` is structural position (0-based), not permanent identity
    - the same "ordinal is not identity" principle Table's own docstring
    already states for itself; `id` is the only stable identity. A unit
    may nest under another (`parent_structural_unit_id` - e.g. a drawing
    detail viewport nested under its sheet) without a separate mechanism.
    `modality_metadata` is a free dict for modality-specific facts (page
    dimensions, sheet name, frame timestamp) that don't warrant their own
    typed field until a real second consumer needs one - honest, minimal,
    not a schema-avoidance escape hatch for facts that DO need real fields.
    """

    id: str
    project_id: str
    source_id: str
    unit_type: str  # open-world - "page" | "sheet" | "section" | "frame" | "table" | ...
    order_index: int
    created_at: str
    created_by: str
    label: Optional[str] = None
    parent_structural_unit_id: Optional[str] = None
    modality_metadata: dict = field(default_factory=dict)


@dataclass
class AddressableRegion:
    """
    A precise locatable portion of a StructuralUnit - a text span, a
    bounding box, a table cell, an image crop, a drawing callout region.
    `address` is a normalized location dict whose shape depends on
    `region_type` (e.g. `{"start_offset", "end_offset"}` for a text span,
    `{"x", "y", "width", "height"}` for a bounding box) - deliberately not
    a fixed set of named coordinate fields, so this is never overfit to
    PDF/image geometry alone (Section 5.3's own explicit caution). A
    region may nest under another (`parent_region_id`) for a sub-region
    of an already-addressed region.

    Citation rendering for a region is NEVER stored here - see
    CaseWorkspaceStore.resolve_region_citation, which derives a human-
    readable label at read time from this record plus its StructuralUnit
    and Source, the same "store flat, derive structure at read time"
    convention Folder's own path resolution already uses. This is also
    what gives citation stability across a renamed Source or relabeled
    unit: the id never changes even though the rendered text can.
    """

    id: str
    project_id: str
    structural_unit_id: str
    region_type: str  # open-world - "text_span" | "bbox" | "cell" | "row" | "crop" | ...
    address: dict
    created_at: str
    created_by: str
    parent_region_id: Optional[str] = None


@dataclass
class EvidenceItem:
    """
    Direct evidence preserved from, or anchored to, a Source or one of its
    AddressableRegions. `evidence_class` (KNOWN_EVIDENCE_CLASSES, closed)
    is the fact/measurement/expert-judgment/user-assumption/AI-suggestion
    distinction MM7 and the Design-Manager Monte Carlo case both depend on
    - established once here rather than re-invented per later modality.

    `region_id` is the finest-grained anchor available, not a required
    one: some evidence (e.g. a value a user typed with no specific source
    location) is honestly anchored only at the Source level - the same
    "honest absence over a fabricated anchor" principle Requirement.
    source_location already establishes. `source_id` is always required;
    "exact source anchor" is satisfied at minimum by that, refined by
    `region_id` whenever a real one exists.

    `validation_status` reuses REVIEWER_VALIDATION_STATES' vocabulary in
    meaning (never a second, drifting copy of it) - None means genuinely
    not yet reviewed, never silently treated as validated. `version`
    starts at 1 and is bumped by a future correction path (not built this
    stage - see MM1's own deferrals); `content_hash` is an optional
    integrity check, the same honestly-optional shape Source.file_hash
    already has.
    """

    id: str
    project_id: str
    source_id: str
    evidence_class: str  # KNOWN_EVIDENCE_CLASSES (closed, validated below)
    content: str
    content_type: str  # open-world - "text" | "number" | "boolean" | "image_reference" | ...
    created_at: str
    created_by: str  # human actor, or engine/model identity when machine-produced
    region_id: Optional[str] = None
    confidence: Optional[float] = None
    validation_status: Optional[str] = None  # None = not yet reviewed; else a REVIEWER_VALIDATION_STATES value
    security_classification: Optional[str] = None
    extractor_version: Optional[str] = None
    version: int = 1
    content_hash: Optional[str] = None

    def __post_init__(self):
        if self.evidence_class not in KNOWN_EVIDENCE_CLASSES:
            raise CaseWorkspaceError(
                f"'{self.evidence_class}' is not a recognized evidence class. "
                f"Use one of: {', '.join(KNOWN_EVIDENCE_CLASSES)}."
            )


@dataclass
class DerivedObservation:
    """
    An interpretation, finding, classification, comparison, inference, or
    summary based on one or more EvidenceItems - never itself direct
    evidence (Section 5.5's own explicit distinction). Deliberately NOT
    Finding: Finding requires a Case (`case_id: str`, no default) and is
    already the real, tested, Case-scoped assertion record; an evidence-
    contract observation must also work at the Source/project level
    before any Case exists, the same reason Requirement stays independent
    of Case. `case_id` here is optional, mirroring AnalysisRun/
    ConversationMessage's own case_id=None convention, not a new one.

    Left an open question, not silently resolved: whether Case-scoped
    Findings and cross-modal DerivedObservations should eventually
    converge is flagged in governance/current/kernel-object-model.md as a
    future design-review item - this stage does not merge them, and does
    not pretend the question is closed either.

    `author_type` (KNOWN_OBSERVATION_AUTHOR_TYPES, closed) is the human/
    deterministic-process/AI distinction; `author` is the free-text who-
    or-what. `related_analysis_id` optionally ties this to the AnalysisRun
    that produced it (engine/model version context), the same field
    Relationship already carries for the identical reason.
    """

    id: str
    project_id: str
    statement: str
    author_type: str  # KNOWN_OBSERVATION_AUTHOR_TYPES (closed, validated below)
    author: str
    method: str
    created_at: str
    supporting_evidence_ids: list[str] = field(default_factory=list)
    case_id: Optional[str] = None
    confidence: Optional[float] = None
    validation_status: Optional[str] = None
    contradiction_state: Optional[str] = None  # open-world, e.g. "disputed" | "resolved"
    superseded_by_observation_id: Optional[str] = None
    related_analysis_id: Optional[str] = None

    def __post_init__(self):
        if self.author_type not in KNOWN_OBSERVATION_AUTHOR_TYPES:
            raise CaseWorkspaceError(
                f"'{self.author_type}' is not a recognized observation author type. "
                f"Use one of: {', '.join(KNOWN_OBSERVATION_AUTHOR_TYPES)}."
            )


@dataclass
class Snapshot:
    """
    Prompt 6 L / Prompt 14 O-AC: a governed, IMMUTABLE reference to what
    existed in a Project at a particular state/time. There is deliberately
    no update/mutation method anywhere in this module for Snapshot - a
    later correction to a frozen understanding is always a NEW Snapshot,
    never an edit to an old one. Unlike Source/Requirement/Expected
    InformationProfile/MaturityRecord, a Snapshot is also never
    superseded by a later one: Snapshot 002 does not correct Snapshot
    001, it is an independent historical fact about a LATER moment - both
    remain equally true statements about their own respective times, so
    the shared Supersession lineage primitive does not apply here.

    Deliberately the "hybrid, leaning toward references over copies"
    design Prompt 14 O concluded, having reached it only by manually
    building exactly this kind of bundle by hand for the NREOCRC
    baseline: `reference_lists` holds only ids, keyed by the
    ProjectWorkspace list they came from, never duplicated record
    content. See _snapshot_reference_lists below - built generically via
    dataclass field introspection, so a future batch that adds a new
    governed list to ProjectWorkspace is automatically captured here with
    no change needed to this dataclass or to create_snapshot.

    Honest, load-bearing limitation - not hidden: several object kinds in
    this module are mutated IN PLACE after creation rather than
    following the append-only/successor pattern (Finding.claim_status,
    Relationship.provisional/confirmed_by, ReviewThread.status/
    resolution/outcome_refs, Attention.status/acknowledged_at/
    responded_message_id, and the predecessor side of any Supersession
    chain having its own status flipped to "superseded"). Resolving this
    Snapshot's references later (see resolve_snapshot_objects) returns
    those objects' CURRENT content, not necessarily what existed at
    freeze time - only the fact that the id existed yet is frozen, not
    the field values on it. True point-in-time content-fidelity for
    those specific fields would require either copying content (rejected
    here, per Prompt 14 O) or converting every in-place mutation to the
    successor pattern (a materially larger change than this batch
    undertakes) - see the Batch G report for the full accounting.
    """

    id: str
    project_id: str
    label: str
    project_state_version: int
    frozen_at: str
    created_by: str
    reference_lists: dict = field(default_factory=dict)
    note: Optional[str] = None


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
    # CLAUDE-P40-D: verbatim preservation for records serialized before
    # commit d1ac48e ("Extend Case Workspace with three-part review
    # model...") split the original single Review concept (decision one
    # of REVIEW_DECISIONS: accept/reject/needs_evidence/correction) into
    # reviewer_validations + dispositions above. Never written to by any
    # current code path - see CaseWorkspaceStore._hydrate_legacy_reviews
    # for why no honest 1:1 mapping onto either successor exists and
    # nothing is invented here.
    legacy_reviews: list[dict] = field(default_factory=list)
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
    snapshots: list[dict] = field(default_factory=list)
    tables: list[dict] = field(default_factory=list)
    table_rows: list[dict] = field(default_factory=list)
    source_references: list[dict] = field(default_factory=list)
    requirement_adjudications: list[dict] = field(default_factory=list)
    carried_forward_adoptions: list[dict] = field(default_factory=list)
    investigation_steps: list[dict] = field(default_factory=list)  # CLAUDE-P08 - see InvestigationStep
    case_outcomes: list[dict] = field(default_factory=list)  # CLAUDE-P11 - see CaseOutcome
    participants: list[dict] = field(default_factory=list)  # CLAUDE-P12R - see Participant
    go_no_go_assessments: list[dict] = field(default_factory=list)  # CLAUDE-P30 - see GoNoGoAssessment
    # CLAUDE-P40-VW7: project-scoped conversation Tags/Tasks. Purely
    # additive (a legacy record predating this stage simply lacks these
    # keys and loads with the empty-list default, same pattern as every
    # other list field on this dataclass - see save()'s own docstring
    # on why this is always backward-compatible). tags holds only
    # CUSTOM tag definitions (see Tag/BUILT_IN_TAGS above); built-in
    # tags are never written here.
    tags: list[dict] = field(default_factory=list)  # see Tag
    tag_occurrences: list[dict] = field(default_factory=list)  # see TagOccurrence
    tasks: list[dict] = field(default_factory=list)  # see Task
    # CLAUDE-GO-RIGHT-PANEL-01: see ComposerFinding's own docstring -
    # Composer-emitted, project-scoped characterizations, separate from
    # workspace.findings (Case/Analysis-bound Findings above).
    composer_findings: list[dict] = field(default_factory=list)  # see ComposerFinding
    # CLAUDE-P40-VW9: Design-Builder Workspace working folders (see Folder
    # above) - purely additive, same backward-compatible pattern as tags/
    # tag_occurrences/tasks above (a legacy record predating this stage
    # simply lacks the key and loads with the empty-list default).
    folders: list[dict] = field(default_factory=list)  # see Folder

    # CLAUDE-MM1: Multimodal Foundation and Evidence Contract - purely
    # additive, same backward-compatible pattern as every list field above
    # (a legacy record predating this stage simply lacks these keys and
    # loads with the empty-list default). See StructuralUnit/
    # AddressableRegion/EvidenceItem/DerivedObservation above.
    structural_units: list[dict] = field(default_factory=list)
    addressable_regions: list[dict] = field(default_factory=list)
    evidence_items: list[dict] = field(default_factory=list)
    derived_observations: list[dict] = field(default_factory=list)

    # CLAUDE-P31: this project's Security Profile (services.security_policy.
    # INFORMATION_CLASSIFICATIONS) -- unlike operating_environment, NOT
    # locked forever: policy legitimately changes over a project's life
    # (Part XIV), so this is re-settable, but every change is logged via
    # set_project_security_profile's own governance_log event (previous
    # value never silently lost). Defaults None -- a project with no
    # profile set is evaluated with profile_decision=None everywhere (see
    # services.security_policy.evaluate_action), i.e. governed purely by
    # the organization baseline/floor, never a fabricated default profile.
    security_profile: Optional[str] = None
    security_profile_set_by: Optional[str] = None
    security_profile_set_at: Optional[str] = None

    # CLAUDE-P32: project-level access control -- which authenticated
    # accounts may open this project at all. Orthogonal to, and checked
    # BEFORE, both role (admin/read_only) and Case-level visibility
    # (visible_cases_for) -- those answer "what can this user do inside
    # a project they're already allowed into"; this answers "may they be
    # in here at all." Unlike operating_environment, deliberately NOT a
    # one-time lock: a wrong owner (e.g. from backfill inference) must be
    # recoverable, not permanent -- but only ever re-settable by an admin
    # (enforced at the route layer, never by this store method itself,
    # matching set_project_security_profile's own precedent), and every
    # change is still fully accountable via its own governance_log event.
    # `owner is None` means "not yet established" (a legacy project
    # before this field existed, or a brand-new one mid-creation) --
    # never treated as "open to everyone," the opposite of every other
    # None-means-ungated field in this module (allowed_participant_roles,
    # capability_availability) precisely because this is the one field
    # whose absence must fail closed, not open.
    owner: Optional[str] = None
    owner_set_by: Optional[str] = None
    owner_set_at: Optional[str] = None
    # Additional accounts (real User.username values, validated by the
    # route layer before being passed in here -- this module still does
    # not import models/services.auth) explicitly granted access by the
    # owner or an admin. Never grants grant/revoke authority itself --
    # an allow-listed user can open the project, nothing more.
    access_allow_list: list[str] = field(default_factory=list)

    # CLAUDE-P40-E2: recoverable "Remove Project" - a completely
    # separate mechanism from routes/portal.py's pre-existing, real,
    # honestly-named delete_project (which stays exactly as
    # permanent/destructive as it always was, "Project Entry Rule" for
    # unwanted/duplicate/test entries - untouched by this stage).
    # `removed_at is None` is the only thing that means "active" -
    # every child record (Cases/Sources/Requirements/Findings/etc.)
    # stays completely intact and unmodified; only the project's own
    # listing visibility changes (see routes/portal.py's
    # _accessible_documents and app.py's _nav_recent_projects).
    removed_at: Optional[str] = None
    removed_by: Optional[str] = None
    removal_reason: Optional[str] = None

    perspective_assessments: list[dict] = field(default_factory=list)  # CLAUDE-P12R - see PerspectiveAssessment
    # Per-reviewer "who do I represent in this Project" (username ->
    # participant_id) - same personal/display-only shape as
    # last_viewed_by/starred: no governance meaning of its own, affects
    # no Case/Finding/Requirement directly. What it DOES do is select
    # whose perspective requirement_investigation.py's optional risk-
    # polarity extension reasons from, and whose PerspectiveAssessments
    # render for this reviewer - missing key = no represented party set,
    # not a default participant.
    represented_party_by: dict = field(default_factory=dict)

    # -- Project Home presentation state (Prompt 3) ---------------------------
    # UI/orientation state only - never forensic or compliance records, and
    # never consulted by any governance/authority decision in this module.
    # `starred` is a personal bookmark with no governance meaning: starring
    # or unstarring writes no GovernanceLog event and affects no Case,
    # Finding, or Requirement (Prompt 3 #3).
    starred: bool = False
    # Per-reviewer "last visited Project Home" marker (username -> ISO
    # timestamp), personal/display-only like `starred` - no governance
    # meaning, no event, affects nothing else. Exists so a returning
    # reviewer can be told what changed since they were last here,
    # rather than having to re-read the whole History log to reconstruct
    # it themselves. Missing key = never visited, not "visited at time
    # zero" - callers must check for absence, not default to an ancient
    # timestamp.
    last_viewed_by: dict = field(default_factory=dict)
    # CLAUDE-CA1D-ATTENTION-STATE-02: per-reviewer, per-item "meaningfully
    # reviewed at" marker (username -> object_id -> ISO timestamp),
    # personal/display-only like `last_viewed_by`/`starred` above - no
    # governance meaning, no event of its own. "Changed since reviewed"
    # is ALWAYS derived by comparing this against existing governed
    # evidence (see CaseWorkspaceStore.has_unreviewed_change) - this
    # field is never itself read as a change signal, only as a review-
    # boundary marker, exactly mirroring `last_viewed_by`'s own relation
    # to GovernanceLog for `since_last_visit`. Missing reviewer/object_id
    # key = never reviewed, not "reviewed at time zero" - callers must
    # check for absence (has_unreviewed_change already does), never
    # default to an ancient timestamp. First proof entity is Finding
    # (object_id = finding_id); nothing here assumes any other entity
    # type participates yet.
    item_reviewed_at: dict = field(default_factory=dict)
    # Conversation messages sent from a project-level context - no Case
    # open, nowhere case-shaped for the message to live (see
    # ConversationMessage's own docstring). A genuine second home for
    # Conversation, not a dumping ground: Case-scoped conversation stays
    # exactly where it already was (each Case's own `conversation` list),
    # unmigrated, unchanged.
    project_conversation: list[dict] = field(default_factory=list)
    # `display_title`/`display_description` override the Project's
    # otherwise-inherited identity (the ingested document's filename) for
    # presentation only - never a Source's own recorded `name`/
    # `document_id`, which remain that Source's actual forensic identity.
    display_title: Optional[str] = None
    display_description: Optional[str] = None
    # Project / Case Operating Instructions (Prompt 3 #7): human-authored
    # guidance (terminology, delivery-method context, reviewer conventions,
    # known assumptions) that is explicitly SUBORDINATE to governance -
    # nothing in this module ever reads operating_instructions to decide
    # Source authority, provenance, approval-gate behavior, or any Stone
    # Wall/constitutional rule. Presentation/context text only.
    operating_instructions: str = ""
    operating_instructions_updated_by: Optional[str] = None
    operating_instructions_updated_at: Optional[str] = None
    # CLAUDE-P38 (OBS-05): the issuer's role at the time they last set
    # this - "Last updated by admin" alone left the issuer's authority
    # implicit. Optional/defaulted so existing serialized records
    # (pre-dating this field) round-trip unchanged.
    operating_instructions_updated_by_role: Optional[str] = None
    # CLAUDE-P38-B: cached output of services.project_briefing.
    # generate_project_briefing - a plain dict (asdict of
    # ProjectBriefingResult), never regenerated silently on every page
    # view (a real Anthropic call every time would be slow and costly).
    # `project_briefing_source_signature` records which Sources it was
    # generated from (a sorted tuple of Source ids as a string) so the
    # workspace route can detect "the active source set changed" and
    # offer regeneration, per this stage's own honesty requirement,
    # without guessing at what changed. Deterministic-only sections
    # (deterministic_sections, same module) are NOT cached here - they
    # cost nothing to recompute on every render, unlike the real call.
    project_briefing: Optional[dict] = None
    project_briefing_generated_at: Optional[str] = None
    project_briefing_generated_by: Optional[str] = None
    # Project Context (CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01): the Project's
    # own current, human-declared orientation/direction - what the
    # Project is about right now, and why, as distinct from
    # operating_instructions above (terminology/convention/reviewer-
    # guidance text, explicitly NOT project direction). Direction
    # legitimately changes during design/pursuit (a client dropping a
    # ramp/parking concept for office space, say) - a later entry must
    # never silently erase an earlier one, so this is an APPEND-ONLY list
    # (ProjectContextEntry, below), the same "a later record supersedes
    # an earlier one IN EFFECT, never overwrites or deletes it" shape
    # already used throughout this module for ReviewerValidation/
    # Disposition/CaseOutcome - not a new versioning subsystem. The
    # CURRENT entry is always simply the last one; "history" is every
    # entry before it. Project Context is human-supplied orientation,
    # never itself treated as verified evidence - nothing in this module
    # reads it to decide Source authority, Stone Wall, or any
    # constitutional rule, the same subordination operating_instructions
    # already documents.
    project_context_entries: list[dict] = field(default_factory=list)
    project_briefing_source_signature: Optional[str] = None
    # CLAUDE-P38-D2: duplicate-call/idempotency guard for automatic
    # generation - set immediately before the real Anthropic call
    # begins, cleared immediately after (success or failure). A
    # concurrent request sees this set and does not start a second
    # call; treated as abandoned (safe to retry) once older than
    # GENERATION_IN_PROGRESS_TIMEOUT_SECONDS, so a killed worker process
    # can never leave this stuck forever - see
    # generation_in_progress_for/start_project_briefing_generation.
    project_briefing_generation_started_at: Optional[str] = None
    # CLAUDE-P38-D2: the auto-generation lifecycle's own "do not
    # regenerate when a previous generation failed repeatedly without
    # user intervention" rule needs a real record of the last failure -
    # without this, a failed attempt looks identical to "never tried",
    # and automatic (re)generation would otherwise retry forever against
    # e.g. a permanently misconfigured provider. Cleared on any
    # successful generation (set_project_briefing).
    project_briefing_last_failure_reason: Optional[str] = None
    project_briefing_last_failure_at: Optional[str] = None
    # CLAUDE-P38-D2: exactly one prior version, not a full history log
    # (this stage's own "do not build a large document-versioning
    # subsystem" instruction) - set by set_project_briefing whenever it
    # overwrites an EXISTING briefing, so a regeneration is never a
    # silent, unrecoverable overwrite.
    project_briefing_previous: Optional[dict] = None
    project_briefing_previous_generated_at: Optional[str] = None
    project_briefing_previous_source_signature: Optional[str] = None
    # CLAUDE-P29: Project Operating Environment -- the locked, project-
    # level classification of which side of the procurement/delivery
    # relationship this project's workspace serves (services/
    # environment_capabilities.py's CLIENT_OWNER /
    # DESIGN_BUILDER_PROPONENT). None means either a legacy project
    # (created before this field existed) or, structurally identically,
    # a new project not yet fully created -- both are "not established",
    # never fabricated. Once set to a real value it is permanently
    # locked: CaseWorkspaceStore.set_operating_environment (below) is
    # the ONLY code path that ever writes this field, and it refuses
    # outright if the field is already non-None -- there is no update/
    # convert path anywhere in this module, deliberately, matching
    # CLAUDE-P29's non-negotiable rule that a project's environment can
    # never be changed into the opposing one after creation.
    #
    # Explicitly NOT the same concept as represented_party_by above:
    # that is a personal, per-reviewer, freely-changeable setting with
    # no governance meaning: this is a locked, project-wide fact that
    # gates which capabilities (see environment_capabilities.py) the
    # project has at all. A reviewer changing who they represent can
    # never change this field -- the two are enforced through entirely
    # separate methods (set_represented_party vs.
    # set_operating_environment), and nothing here shares mutation
    # logic with that mechanism.
    operating_environment: Optional[str] = None
    operating_environment_set_by: Optional[str] = None
    operating_environment_set_at: Optional[str] = None

    # CLAUDE-MM7: Governed Investigation, Analytical Reasoning, and
    # Trustworthy Answers - purely additive, same backward-compatible
    # pattern as every list field above (a legacy record predating this
    # stage simply lacks this key and loads with the empty-list
    # default). See Claim above.
    claims: list[dict] = field(default_factory=list)

    # CLAUDE-MM8: Governed Creation, Editing, Review, and Accountable Work
    # Products - purely additive, same backward-compatible pattern as
    # every list field above. See WorkProduct above.
    work_products: list[dict] = field(default_factory=list)


def _snapshot_reference_lists(workspace: ProjectWorkspace) -> dict:
    """
    Generic reference-list capture for Snapshot (Prompt 14 O): walks
    every list field on ProjectWorkspace via dataclass introspection and
    records the ids currently present, rather than hardcoding one field
    per governed list type (which would need updating every time a
    future batch adds a new list). Skips `snapshots` itself (a Snapshot
    does not reference other Snapshots) and `project_id`/`version` (not
    lists of governed records).
    """
    result: dict[str, list[str]] = {}
    for f in dataclass_fields(ProjectWorkspace):
        if f.name in ("project_id", "version", "snapshots"):
            continue
        value = getattr(workspace, f.name)
        if isinstance(value, list):
            result[f.name] = [item["id"] for item in value if isinstance(item, dict) and "id" in item]
    return result


def compare_snapshot_reference_lists(snapshot_a: dict, snapshot_b: dict) -> dict:
    """
    Prompt 14 AC / Batch G: a generic, project-agnostic STRUCTURAL
    comparison between two Snapshots - which ids exist in one but not the
    other, per governed list, plus simple counts. Deliberately NOT a
    SEMANTIC comparison (Prompt 14's NREOCRC-specific criteria - source
    identity fidelity, requirement fidelity, authority fidelity, etc.):
    those require corpus-specific knowledge this generic function does
    not and should not encode. A semantic comparison for a specific
    corpus re-ingestion belongs in its own script built on top of this,
    the same way the NREOCRC ingestion lab script sits on top of
    CaseWorkspaceStore itself - resolve_snapshot_objects gives that
    script everything it needs to build one.

    Meaningful primarily for two Snapshots of the SAME evolving project
    over time (this architecture's lists are append-only - items are
    superseded/withdrawn, never deleted, so "removed_in_b" is expected to
    stay empty for that case in practice). Comparing Snapshots from two
    genuinely independent projects/ingestion runs is not rejected, but
    the id-sets will not overlap at all, so "added"/"removed" mean
    something different there - interpret with that in mind.
    """
    lists_a = snapshot_a.get("reference_lists") or {}
    lists_b = snapshot_b.get("reference_lists") or {}
    all_names = sorted(set(lists_a) | set(lists_b))
    comparison: dict = {}
    for name in all_names:
        ids_a = set(lists_a.get(name, []))
        ids_b = set(lists_b.get(name, []))
        comparison[name] = {
            "count_a": len(ids_a),
            "count_b": len(ids_b),
            "added_in_b": sorted(ids_b - ids_a),
            "removed_in_b": sorted(ids_a - ids_b),
        }
    return comparison


# -- Structured Tabular Evidence: pure helpers (Prompt 18 / Batch J) ---------
# Table/TableRow REGISTRATION reads a ParsedDocument.tables entry (raw
# headers/rows-of-strings, as BHiveParser already produces - Batch H) and
# turns it into governed evidence. These pure functions do the actual
# cell-level interpretation; register_table_evidence (on the store) does
# the persistence.

# Recognized non-numeric placeholders (Prompt 18 #7) - preserved as a
# QUALIFIER, never coerced into 0 or any other numeric default. Matched
# case-insensitively against the FULL stripped cell text.
_CELL_QUALIFIER_TOKENS = (
    "tbd", "n/a", "not applicable", "approx.", "approximate", "minimum",
    "maximum", "nominal", "if required", "included in subtotal",
)
_CELL_BLANK_MARKERS = ("", "—", "-", "–")


def parse_table_cell_value(raw: str) -> tuple[Optional[float], Optional[str]]:
    """
    Returns (parsed_value, qualifier) for one raw cell string - never
    discards `raw` itself (the caller keeps it separately). A blank cell
    or em dash becomes qualifier="blank"/"em_dash" with parsed_value=None,
    NEVER parsed_value=0 (Prompt 18 #7's central rule). A recognized
    qualifier PHRASE (whole-cell match) is preserved as the qualifier
    string itself. Free descriptive text that is neither a clean number
    nor a recognized qualifier is honestly left as (None, None) - the
    `raw` value is still there for a human to read; this function does
    not force everything into one of its two output buckets.
    """
    stripped = raw.strip()
    if stripped in _CELL_BLANK_MARKERS:
        return None, ("blank" if stripped == "" else "em_dash")

    lowered = stripped.lower().rstrip(".")
    for token in _CELL_QUALIFIER_TOKENS:
        if lowered == token.rstrip("."):
            return None, stripped

    numeric_candidate = stripped.replace(",", "")
    try:
        return float(numeric_candidate), None
    except ValueError:
        return None, None


def extract_unit_from_header(header: str) -> Optional[str]:
    """
    Prompt 18 #6: a unit is only ever inherited from the COLUMN HEADER's
    own explicit parenthetical (e.g. "Net Area (m²) each" -> "m²") - never
    guessed or assumed from cell content. Returns None when the header
    carries no such hint.
    """
    m = re.search(r"\(([^)]+)\)", header)
    if not m:
        return None
    candidate = m.group(1).strip()
    # A parenthetical like "this document" or "Draft" is not a unit -
    # only accept short, unit-shaped tokens (no spaces, or a single
    # qualifying word) to avoid misreading an unrelated parenthetical.
    if len(candidate) <= 6 and not candidate.lower() in ("each",):
        return candidate
    return None


_HEADING_LINE_RE = re.compile(r"^#{1,6}\s+(.+)$")
_BOLD_CAPTION_RE = re.compile(r"^\*\*([^*]+)\*\*$")


def find_preceding_heading(raw_lines: list[str], before_line_1indexed: int) -> Optional[str]:
    """
    Prompt 18 #4: a Table's `section_context` - the nearest markdown ATX
    heading (or bold standalone caption line) preceding the table, if
    any. Scans backward from the line just above the table's start.
    Returns None (never guessed) if nothing heading-shaped precedes it
    within the document.
    """
    for i in range(before_line_1indexed - 2, -1, -1):
        line = raw_lines[i].strip()
        if not line:
            continue
        m = _HEADING_LINE_RE.match(line)
        if m:
            return m.group(1).strip()
        m = _BOLD_CAPTION_RE.match(line)
        if m:
            return m.group(1).strip()
        # Stop at the first non-blank, non-heading, non-caption line -
        # "nearest preceding heading" means immediately above the table's
        # own lead-in, not the closest heading anywhere earlier in the
        # document.
        return None
    return None


def reconcile_table_evidence(table: dict, rows: list[dict]) -> Optional[dict]:
    """
    Prompt 18 #12/#28: the production version of generic grouped-quantity
    table reconciliation - consumes real Table/TableRow EVIDENCE (cells
    with an already-parsed `parsed_value` and their own `header`), not a
    raw ParsedDocument.tables dict. Column identification is still by
    HEADER KEYWORD (group/qty/each/subtotal), not fixed index - the same
    generic approach proven in the Prompt 17 experiment, now living in
    production so no future caller needs to reimplement it against
    Markdown directly.

    Returns None if `table` doesn't have the required column shape - an
    honest "not applicable", not a forced computation.

    This function does NOT decide what a mismatch MEANS (Prompt 18 #13):
    it reports numbers. Whether that constitutes a "source internal
    inconsistency" worth a Finding/ReviewThread is a decision for the
    caller (see the completion report for how this is used against
    Design-Builder-compliance concerns specifically NOT being implied
    here).
    """
    headers_lower = [h.lower() for h in table["headers"]]

    def find_col_index(*keywords):
        for i, h in enumerate(headers_lower):
            if all(kw in h for kw in keywords):
                return i
        return None

    group_col = find_col_index("group")
    qty_col = find_col_index("qty")
    unit_value_col = next((i for i, h in enumerate(headers_lower) if "area" in h and "each" in h), None)
    subtotal_col = find_col_index("subtotal")
    if None in (group_col, qty_col, unit_value_col, subtotal_col):
        return None

    group_header = table["headers"][group_col]
    qty_header = table["headers"][qty_col]
    unit_value_header = table["headers"][unit_value_col]
    subtotal_header = table["headers"][subtotal_col]

    def cell_value(row: dict, header: str) -> Optional[float]:
        for cell in row["cells"]:
            if cell["header"] == header:
                return cell["parsed_value"]
        return None

    def group_name(row: dict) -> Optional[str]:
        for cell in row["cells"]:
            if cell["header"] == group_header:
                return cell["raw_value"].strip()
        return None

    groups: list[dict] = []
    current_group_name = None
    current_rows: list[dict] = []

    def flush():
        if current_group_name is None:
            return
        computed = 0.0
        for row in current_rows:
            qty = cell_value(row, qty_header) or 0.0
            unit_value = cell_value(row, unit_value_header) or 0.0
            computed += qty * unit_value
        stated_values = [cell_value(row, subtotal_header) for row in current_rows]
        stated_values = [v for v in stated_values if v is not None]
        stated = stated_values[0] if stated_values else None
        groups.append({
            "group": current_group_name,
            "computed_from_line_items": computed,
            "stated_subtotal": stated,
            # None (not False) when there is no stated subtotal to compare
            # against at all - "nothing to compare" is a different fact
            # from "compared and it differs", and collapsing them would
            # misreport an ordinary missing-subtotal group as a mismatch.
            "matches": (abs(stated - computed) < 0.001) if stated is not None else None,
            "row_count": len(current_rows),
        })

    for row in rows:
        name = group_name(row)
        if name != current_group_name:
            flush()
            current_group_name = name
            current_rows = []
        current_rows.append(row)
    flush()

    total_line_items = sum(
        (cell_value(row, qty_header) or 0.0) * (cell_value(row, unit_value_header) or 0.0)
        for row in rows
    )
    total_stated_subtotals = sum(g["stated_subtotal"] for g in groups if g["stated_subtotal"] is not None)

    return {
        "groups": groups,
        "total_from_line_items": total_line_items,
        "total_from_stated_subtotals": total_stated_subtotals,
        "mismatched_group_count": sum(1 for g in groups if g["stated_subtotal"] is not None and not g["matches"]),
        "group_count": len(groups),
    }


# -- CLAUDE-MM1: citation address rendering ----------------------------------

def _render_region_address_label(region_type: str, address: dict) -> Optional[str]:
    """
    Human-readable rendering of an AddressableRegion's own `address` dict,
    used only by CaseWorkspaceStore.resolve_region_citation - deliberately
    a small, explicit set of KNOWN shapes (text span, bounding box, table
    cell/row, generic named point) with an honest fallback for anything
    else, rather than a single format string that would silently mis-
    render a shape it wasn't written for. Returns None (not a guess) when
    `address` doesn't match any recognized shape - the caller still gets
    a resolvable citation from the Source/unit label alone.
    """
    if region_type == "text_span" and "start_offset" in address and "end_offset" in address:
        return f"offset {address['start_offset']}-{address['end_offset']}"
    if region_type == "bbox" and {"x", "y", "width", "height"} <= address.keys():
        return f"region x={address['x']},y={address['y']}"
    if region_type in ("cell", "row") and "label" in address:
        return str(address["label"])
    # CLAUDE-MM2: register_pdf_page_structure's own paragraph regions - the
    # page number itself already appears via the StructuralUnit's own
    # label ("Page 14") in resolve_region_citation's label_parts, so this
    # only ever needs to add the paragraph position, matching the
    # "RFP.pdf · page 14 · paragraph 3" example this stage's own governing
    # prompt gives. 1-indexed for the human-facing rendering; the stored
    # `paragraph_index` itself stays 0-indexed, unchanged, matching
    # `order_index`'s own "position, not identity" convention.
    if region_type == "paragraph" and "paragraph_index" in address:
        return f"paragraph {address['paragraph_index'] + 1}"
    # CLAUDE-MM4: create_addressable_drawing_region's own rectangular
    # regions - "region_index" is a stable, 1-based, per-StructuralUnit
    # sequential position (assigned once at creation, never renumbered by
    # a later region's own creation or removal - see that method's own
    # docstring), giving the "A101 · Ground Floor Plan · region 3" shape
    # this stage's own governing prompt (Section 12) asks for.
    if region_type == "rectangular" and "region_index" in address:
        return f"region {address['region_index']}"
    # CLAUDE-MM5 Section 13: create_addressable_marker_region's own point
    # annotations - same region_index convention as rectangular regions,
    # rendered as "marker N" rather than "region N" so a citation never
    # implies a marker has spatial extent it doesn't have.
    if region_type == "marker" and "region_index" in address:
        return f"marker {address['region_index']}"
    if "label" in address:
        return str(address["label"])
    return None


# -- Generic Source-Reference parsing / resolution (Prompt 18 / Batch J) ----
# Two-phase, mirroring evaluate_information_sufficiency's shape: a pure
# SYNTACTIC parse (what does the text say, structurally) followed by a
# separate RESOLUTION step against caller-supplied known targets (does
# what it says actually exist) - never conflated, so a reference can be
# syntactically well-formed yet honestly unresolved.

_REF_NUMERIC_TOKEN = r"\d+(?:\.\d+)?"
_REF_WORD_TOKEN = r"(?=[\w\-.]*\d)[\w\-.]+"  # must contain a digit; dots allowed (e.g. "OPR-2.1")
_REF_CONNECTOR = r"(?:and|through|to)"
_REF_SEP = r"(?:[,\s]+|[-–—])"


def _reference_tail_group(token_pattern: str) -> str:
    unit = f"(?:{token_pattern}|{_REF_CONNECTOR})"
    return r"(" + unit + r"(?:" + _REF_SEP + unit + r")*)"


_REFERENCE_PATTERNS = (
    (REFERENCE_TYPE_SECTION, re.compile(r"\bSections?\s+" + _reference_tail_group(_REF_NUMERIC_TOKEN), re.IGNORECASE)),
    (REFERENCE_TYPE_FIGURE, re.compile(r"\bFigures?\s+" + _reference_tail_group(_REF_WORD_TOKEN), re.IGNORECASE)),
    (REFERENCE_TYPE_TABLE, re.compile(r"\bTables?\s+" + _reference_tail_group(_REF_WORD_TOKEN), re.IGNORECASE)),
    (REFERENCE_TYPE_APPENDIX, re.compile(r"\bAppendix\s+" + _reference_tail_group(_REF_WORD_TOKEN), re.IGNORECASE)),
)
_TABLE_ROW_COMPOUND_RE = re.compile(
    r"\b((?:Appendix|Table)\s+[\w\-]+),?\s+Rows?\s+" + _reference_tail_group(_REF_NUMERIC_TOKEN), re.IGNORECASE
)
_ROW_ONLY_RE = re.compile(r"\bRows?\s+" + _reference_tail_group(_REF_NUMERIC_TOKEN), re.IGNORECASE)

_NUMERIC_RANGE_RE = re.compile(r"^(\d+(?:\.\d+)?)\s*(?:through|to|[-–—])\s*(\d+(?:\.\d+)?)$", re.IGNORECASE)
# Deliberately excludes a bare hyphen (unlike the numeric range above) - a
# word-shaped identifier like "OPR-2.1" contains a hyphen that is part of
# the identifier itself, not a range connector, so only "through"/"to"/
# en-dash/em-dash (never bare "-") are treated as connectors between two
# WORD-shaped tokens.
_WORD_RANGE_CONNECTOR_RE = re.compile(r"\s+(?:through|to)\s+|\s*[–—]\s*", re.IGNORECASE)
_LIST_SPLIT_RE = re.compile(r",\s*(?:and\s+)?|\s+and\s+", re.IGNORECASE)


def _expand_numeric_range(start: str, end: str) -> Optional[list[str]]:
    """
    Arithmetic expansion ONLY where safe and unambiguous: both endpoints
    bare integers ("10".."14"), or both sharing the same major part
    before a single decimal point ("4.1".."4.6" -> 4.1..4.6). Returns
    None (never a guess) for anything else - e.g. differently-shaped
    endpoints, or a minor part that isn't a clean ascending integer run.
    """
    if start.isdigit() and end.isdigit():
        lo, hi = int(start), int(end)
        if lo <= hi <= lo + 100:
            return [str(n) for n in range(lo, hi + 1)]
        return None

    start_parts, end_parts = start.split("."), end.split(".")
    if len(start_parts) == 2 and len(end_parts) == 2 and start_parts[0] == end_parts[0]:
        major = start_parts[0]
        if start_parts[1].isdigit() and end_parts[1].isdigit():
            lo, hi = int(start_parts[1]), int(end_parts[1])
            if lo <= hi <= lo + 100:
                return [f"{major}.{n}" for n in range(lo, hi + 1)]
    return None


def _parse_reference_tail(tail: str) -> tuple[list[str], str]:
    """
    Parses the text AFTER a reference keyword ("Section(s)", "Figure(s)",
    ...) into a list of individual target strings plus a syntactic-form
    tag ("single"/"range"/"list"/"ambiguous"). Purely syntactic - does
    not check whether any target actually exists.
    """
    def _clean(token: str) -> str:
        return token.strip().rstrip(".,;")

    tail = _clean(tail)

    m = _NUMERIC_RANGE_RE.match(tail)
    if m:
        expanded = _expand_numeric_range(m.group(1), m.group(2))
        if expanded is not None:
            return expanded, "range"
        return [m.group(1), m.group(2)], "ambiguous"

    range_parts = _WORD_RANGE_CONNECTOR_RE.split(tail)
    if len(range_parts) == 2:
        start, end = _clean(range_parts[0]), _clean(range_parts[1])
        expanded = _expand_numeric_range(start, end)
        if expanded is not None:
            return expanded, "range"
        return [start, end], "ambiguous"

    if "," in tail or re.search(r"\band\b", tail, re.IGNORECASE):
        items = [_clean(p) for p in _LIST_SPLIT_RE.split(tail) if _clean(p)]
        if len(items) > 1:
            return items, "list"

    return [tail], "single"


def resolve_conversation_hotlinks(text: str, workspace: "ProjectWorkspace") -> list[dict]:
    """
    CLAUDE-P40-E, Section G: safe internal document hot-links inside
    conversation text. Turns an EXACT, case-sensitive, whole-string
    match against a real, currently-known Source filename in THIS
    project into a linkable segment - never a regex guess at "things
    that look like a filename" (Section G: "do not convert unverified
    text that merely resembles a filename into a trusted link. Resolve
    links through governed document identity"). Resolved fresh against
    `workspace.sources` every call, never a stale name/id baked into
    the message when it was originally posted - a Source later renamed
    or removed simply stops matching, it is never a dangling/broken
    link that still LOOKS clickable.

    Returns plain segments ({"text": str, "source_id": Optional[str]}),
    never HTML - this module stays framework/template-agnostic (it does
    not import Flask), matching its own existing precedent elsewhere
    (see the module docstring's "no import cycle" reasoning). The
    caller (app.py's `hotlinks` Jinja filter) is what actually builds
    the safe `<a href="...">` markup, with url_for and markupsafe
    escaping - both real Flask/template concerns this module
    deliberately stays out of.

    Deliberately narrow - Source filenames only, not Findings/clauses/
    Case titles: those would need either an id embedded in the message
    text (this module never fabricates one after the fact) or a
    separate governed-identity resolution path this stage doesn't
    build. A real, honest boundary, not a simulated one - see the
    document viewer's own pane-note on page/clause navigation for the
    same discipline applied to a different part of this stage.
    """
    if not text:
        return [{"text": text, "source_id": None}]

    name_to_id: dict[str, str] = {}
    for source in workspace.sources:
        name = source.get("name")
        if name and name not in name_to_id:
            name_to_id[name] = source["id"]

    if not name_to_id:
        return [{"text": text, "source_id": None}]

    # Longest name first, so "sample_drawing.png" doesn't get partially
    # shadowed by a shorter name that happens to be a substring of it.
    pattern = re.compile("|".join(re.escape(n) for n in sorted(name_to_id, key=len, reverse=True)))

    segments: list[dict] = []
    last_end = 0
    for match in pattern.finditer(text):
        if match.start() > last_end:
            segments.append({"text": text[last_end:match.start()], "source_id": None})
        matched_name = match.group(0)
        segments.append({"text": matched_name, "source_id": name_to_id[matched_name]})
        last_end = match.end()
    if last_end < len(text):
        segments.append({"text": text[last_end:], "source_id": None})
    return segments or [{"text": text, "source_id": None}]


def parse_source_reference_text(text: str) -> list[dict]:
    """
    Prompt 18 #14/#16/#17: finds every explicit reference mention in
    `text` (a clause's own sentence, a table-row Note, etc) and returns
    one candidate dict per mention: {"reference_text" (verbatim matched
    span), "reference_type" (open-world), "candidate_targets" (syntactic
    expansion - NOT yet existence-checked), "syntactic_form"}. A single
    piece of text may yield multiple candidates (e.g. one sentence citing
    both a Section and a Figure).

    Deliberately open-world at the PATTERN level too (Prompt 18 #14): new
    reference keywords are not exhaustively enumerable, so this is a
    reasonably-generic set of common document-part keywords
    (Section/Figure/Table/Appendix/Row), not a claim that every possible
    citation phrasing is covered.
    """
    candidates: list[dict] = []
    consumed_spans: list[tuple[int, int]] = []

    for m in _TABLE_ROW_COMPOUND_RE.finditer(text):
        container, row_tail = m.group(1), m.group(2)
        targets, form = _parse_reference_tail(row_tail)
        candidates.append({
            "reference_text": m.group(0), "reference_type": REFERENCE_TYPE_TABLE_ROW,
            "candidate_targets": [f"{container} Row {t}" for t in targets], "syntactic_form": form,
            "container": container,
        })
        consumed_spans.append(m.span())

    def _overlaps(span):
        return any(a <= span[0] < b or a < span[1] <= b for a, b in consumed_spans)

    for m in _ROW_ONLY_RE.finditer(text):
        if _overlaps(m.span()):
            continue
        targets, form = _parse_reference_tail(m.group(1))
        candidates.append({
            "reference_text": m.group(0), "reference_type": REFERENCE_TYPE_TABLE_ROW,
            "candidate_targets": targets, "syntactic_form": form,
        })
        consumed_spans.append(m.span())

    for ref_type, pattern in _REFERENCE_PATTERNS:
        for m in pattern.finditer(text):
            if _overlaps(m.span()):
                continue
            targets, form = _parse_reference_tail(m.group(1))
            candidates.append({
                "reference_text": m.group(0), "reference_type": ref_type,
                "candidate_targets": targets, "syntactic_form": form,
            })
            consumed_spans.append(m.span())

    return candidates


def resolve_source_reference_candidate(candidate: dict, known_targets: dict) -> dict:
    """
    Prompt 18 #16/#18: cross-checks a syntactic candidate's
    `candidate_targets` against ACTUALLY-KNOWN targets supplied by the
    caller - `known_targets` is a dict of {reference_type: set-of-known-
    identifier-strings} (e.g. {"section": {"4.1","4.2",...}, "figure":
    {"OPR-2.1","OPR-2.2"}}). A syntactically valid range/list is never
    expanded into ids that don't correspond to anything real in the
    current governed state - only confirmed targets ever appear in the
    returned `resolved_targets`.

    Returns {"resolution_status" (RESOLUTION_STATUS_*, closed), "resolved_targets"}.
    Pure - does no persistence; register_source_reference (on the store)
    does that using this function's output.
    """
    ref_type = candidate["reference_type"]
    known = known_targets.get(ref_type, set())
    targets = candidate["candidate_targets"]
    form = candidate["syntactic_form"]

    if not known and ref_type not in known_targets:
        return {"resolution_status": RESOLUTION_STATUS_UNSUPPORTED_REFERENCE_TYPE, "resolved_targets": []}

    confirmed = [t for t in targets if t in known]

    if form == "ambiguous":
        return {
            "resolution_status": (RESOLUTION_STATUS_PARTIALLY_RESOLVED if confirmed else RESOLUTION_STATUS_AMBIGUOUS),
            "resolved_targets": confirmed,
        }
    if not confirmed:
        return {"resolution_status": RESOLUTION_STATUS_TARGET_NOT_FOUND, "resolved_targets": []}
    if len(confirmed) < len(targets):
        return {"resolution_status": RESOLUTION_STATUS_PARTIALLY_RESOLVED, "resolved_targets": confirmed}
    if form == "range":
        return {"resolution_status": RESOLUTION_STATUS_RESOLVED_RANGE, "resolved_targets": confirmed}
    if form == "list":
        return {"resolution_status": RESOLUTION_STATUS_RESOLVED_MULTIPLE, "resolved_targets": confirmed}
    return {"resolution_status": RESOLUTION_STATUS_RESOLVED_EXACT, "resolved_targets": confirmed}


def check_citation_against_resolved_references(claimed_target: str, resolved_references: list[dict]) -> str:
    """
    Prompt 18 #19: generalizes the ad hoc check the Prompt 17 lab script
    did by hand (does the text ACTUALLY cite what a Relationship claims
    it cites) into a reusable function. Given a claimed target (e.g.
    "4.3") and a list of already-resolved SourceReference dicts (asdict
    form) derived from the SAME text, returns "VALID" if any resolved
    reference's `resolved_target_ids` contains the claim, "MISMATCH" if
    references were resolved but none match (the text cites something
    else instead), or "UNVERIFIABLE" if no references were resolved at
    all from that text (nothing to check against, one way or the other).
    """
    if not resolved_references:
        return "UNVERIFIABLE"
    for ref in resolved_references:
        if claimed_target in ref.get("resolved_target_ids", []):
            return "VALID"
    return "MISMATCH"


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
        self._hydrate_legacy_reviews(data)
        workspace = ProjectWorkspace(**data)
        self._hydrate_legacy_cases(workspace)
        return workspace

    @staticmethod
    def _hydrate_legacy_reviews(data: dict) -> None:
        """
        CLAUDE-P40-D: a workspace record serialized before commit
        d1ac48e ("Extend Case Workspace with three-part review model...")
        has a top-level "reviews" key - the original single Review
        concept (id, finding_id, decision, reviewer, reviewed_at, note;
        decision one of REVIEW_DECISIONS: accept/reject/needs_evidence/
        correction, introduced in commit 0e86380). "reviews" is not a
        ProjectWorkspace field at all anymore, so
        ProjectWorkspace(**data) raised TypeError: unexpected keyword
        argument 'reviews' for any such record.

        d1ac48e replaced the single Review with two deliberately
        DIFFERENT concepts: ReviewerValidation (epistemic accuracy:
        REVIEWER_VALIDATION_STATES = Correct/Incorrect/Partial/Needs
        Evidence/Not Applicable) and Disposition (workflow decision:
        DISPOSITIONS = Confirmed/Rejected/Deferred/... - "this, not
        ReviewerValidation, is what Apply actually checks", per
        Disposition's own docstring). Real persisted legacy `decision`
        values ("accept", "correction") are not members of either
        vocabulary - "accept" plausibly meant BOTH "epistemically
        Correct" and "workflow Confirmed" at once under the old
        single-concept model, and choosing one now would be inventing a
        decision this hydration step has no authority to make (Section
        C of the CLAUDE-P40-D prompt: no assumed one-to-one mapping).

        So nothing is converted. The raw legacy list is preserved
        verbatim under `legacy_reviews` - a real ProjectWorkspace field
        distinct in name from both current review concepts so nothing
        downstream mistakes it for a current-schema ReviewerValidation
        or Disposition record. Every id, finding_id, decision, reviewer,
        reviewed_at, and note survives unchanged; nothing is dropped or
        fabricated. Like _hydrate_legacy_cases below, this alone never
        calls save() and never mutates the source file - it only
        reshapes the in-memory dict handed to ProjectWorkspace(**data).
        """
        if "reviews" in data:
            data["legacy_reviews"] = data.pop("reviews")

    @staticmethod
    def _hydrate_legacy_cases(workspace: ProjectWorkspace) -> None:
        """
        CLAUDE-P40-C: a Case record serialized before Case-level
        visibility existed (commit 04fc14a, "Implement Case visibility:
        PRIVATE -> explicit Share -> SHARED") has no "visibility" key at
        all - CaseRecord's own dataclass default (CASE_VISIBILITY_
        PRIVATE) only ever applies to a NEW construction, never
        retroactively to already-persisted JSON. Every bracket-access
        read of case["visibility"] (visible_cases_for and every Case-
        collaboration-state-changing method) crashed with KeyError for
        any such legacy Case - confirmed via isolated replay to be
        reachable, unmodified, at both the CLAUDE-P40-B baseline and
        final commit; this predates and is unrelated to P40-B itself.

        Backfilled to CASE_VISIBILITY_SHARED, deliberately NOT
        CASE_VISIBILITY_PRIVATE: before the visibility concept existed,
        every Case was visible to anyone who already had project
        access - no per-case privacy concept existed yet to restrict
        it. Defaulting to PRIVATE would retroactively impose a
        restriction this data was never subject to when it was
        created - that is inventing a new restriction, not "failing
        closed" for this specific record. SHARED (never COLLABORATIVE)
        is deliberately the more conservative of the two non-private
        states: COLLABORATIVE additionally asserts "another party has
        genuinely contributed" (Constitutional Invariant 12 - see
        CASE_VISIBILITY_COLLABORATIVE's own comment), a claim this
        hydration step has no evidence for and must never fabricate.

        Project-level authorization (services.project_access.
        can_access_project, CLAUDE-P32's owner/allow-list gate) is
        completely unaffected and unreached by this method - this only
        ever runs on workspace.cases, which is only ever inspected
        after project-level access has already been granted elsewhere.
        This can therefore never grant, widen, or substitute for
        project access - it only restores the pre-visibility-concept
        Case-level behavior for users who already passed that gate.

        This method itself never calls save() and is never invoked
        outside get() - reading a legacy record, on its own, never
        writes anything (confirmed: an isolated read-only replay of the
        affected record never changed its file on disk).

        CLAUDE-P40-D2 CORRECTION to this docstring's own prior claim:
        P40-C's version of this comment asserted the hydrated value
        "safely" ending up persisted via show_workspace's pre-existing
        last_viewed_by write was fine because that write "adds exactly
        one key, changes no id, no text, no other field." That claim
        was never actually verified against real save() behavior and
        was wrong - save()'s json.dumps(asdict(workspace)) serializes
        every dataclass field, so that same "just recording a view"
        write was actually materializing ~50 previously-absent fields
        at their dataclass defaults (access_allow_list, owner, starred,
        every list field, `version`, etc.) onto disk, plus this
        method's own hydrated visibility and _hydrate_legacy_reviews'
        renamed legacy_reviews key - a real, undisclosed structural
        rewrite, confirmed via an isolated route-level reproduction
        that found 21-60 changed fields from a single GET. Fixed at the
        call site: routes/workspace.py's show_workspace no longer
        calls store.save(workspace) to record a view at all - it calls
        CaseWorkspaceStore.record_last_viewed(workspace, reviewer),
        which patches only last_viewed_by directly into the raw
        on-disk JSON (see that method's own docstring) and never
        touches this method's hydrated in-memory value or any other
        field on disk.
        """
        for case in workspace.cases:
            if "visibility" not in case:
                case["visibility"] = CASE_VISIBILITY_SHARED

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

    def record_last_viewed(self, workspace: ProjectWorkspace, reviewer: str) -> str:
        """
        CLAUDE-P40-D2: the ONLY implicit, GET-triggered write in this
        module - routes/workspace.py's show_workspace calls this on
        every ordinary Project Home view to record `last_viewed_by`
        (personal/display-only "what's new since I last looked" state,
        no governance meaning - see ProjectWorkspace's own "Project
        Home presentation state" section). Deliberately does NOT call
        save(): save()'s json.dumps(asdict(workspace)) serializes the
        COMPLETE in-memory dataclass, which for a legacy record means
        writing out every field CaseWorkspaceStore.get()'s own
        compatibility hydration added or renamed purely in memory
        (_hydrate_legacy_cases' backfilled Case visibility,
        _hydrate_legacy_reviews' reviews -> legacy_reviews rename) PLUS
        every other dataclass field's default value that was never in
        the original file at all - a real, undisclosed structural
        rewrite the first time any legacy record was merely viewed
        (confirmed via an isolated route-level reproduction: a single
        GET on a legacy record changed 21-60 fields, not the one
        last_viewed_by entry it was supposed to). Viewing a project
        must never itself perform a structural rewrite - "legacy
        compatibility values may be hydrated in memory, but viewing a
        project must not persist structural schema changes."

        Instead: patches ONLY `last_viewed_by[reviewer]` directly into
        the RAW on-disk JSON, read fresh from disk and written back
        with that one key changed - never through
        ProjectWorkspace(**data)/asdict(workspace) at all, so every
        other persisted key (a legacy record's still-original "reviews"
        key, a still-missing Case "visibility" key, or simply a field
        this dataclass has that the original file never mentioned)
        stays byte-for-byte as it was. Also updates
        workspace.last_viewed_by in memory so the rest of THIS
        request's own rendering sees the new value (matching what
        save() would have done for that one field) - the in-memory
        hydration this request is already using is completely
        unaffected either way.

        Deliberately does not read, check, or bump `version`: that
        counter exists for save()'s optimistic-concurrency check on
        GOVERNED structural writes (Cases, Findings, Requirements,
        etc.) - view metadata is explicitly "no governance meaning"
        (ProjectWorkspace's own docstring) and was never a structural
        write to begin with, so it does not participate in that
        counter at all, rather than inventing a reason it should.
        Shares save()'s own `_save_lock` so a concurrent governed
        save() and a concurrent view-metadata patch can't interleave
        into a corrupted file within one process - the same same-
        process-only guarantee `_save_lock`'s own docstring already
        states, no wider claim made here either.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        workspace.last_viewed_by[reviewer] = timestamp

        path = self._path_for(workspace.project_id)
        with self._save_lock:
            if not path.exists():
                return timestamp
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw.setdefault("last_viewed_by", {})[reviewer] = timestamp
            tmp_path = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
            tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            tmp_path.replace(path)

        return timestamp

    def record_item_reviewed(self, workspace: ProjectWorkspace, reviewer: str, object_id: str) -> str:
        """
        CLAUDE-CA1D-ATTENTION-STATE-02: records that `reviewer` has just
        meaningfully reviewed `object_id` (a Finding, in this first proof
        entity) - personal/display-only per-item state, the exact same
        category as `last_viewed_by`/`starred`, not a second history of
        what changed. The GOVERNED record of what happened is whichever
        real act this is called alongside (a Disposition, a Reviewer
        Validation, and the `finding_reviewed` GovernanceLog event that
        act already produces) - `has_unreviewed_change` reads THAT
        existing evidence to derive "changed", never this field, so
        there is no competing second history to keep in sync by hand.

        Deliberately mirrors `record_last_viewed` exactly: patches ONLY
        `item_reviewed_at[reviewer][object_id]` directly into the RAW
        on-disk JSON, never through `save()`'s versioned/`asdict
        (workspace)` path - this is not a structural write and does not
        participate in the version counter, for the same reason
        `record_last_viewed`'s own docstring already gives (a legacy
        record's absent/renamed keys must never be silently rewritten
        just because personal view-state was updated). Shares `save()`'s
        own `_save_lock` for the same same-process-only guarantee that
        method's docstring already states - no wider concurrency claim
        made here either.

        Caller-ordering correctness note (not enforced here, since this
        method has no way to see what a caller already logged): a real
        review action's own `finding_reviewed` GovernanceLog event and
        this call are two separate writes with two independently-
        generated timestamps. `has_unreviewed_change` treats a LATER
        GovernanceLog event as "changed since reviewed" using a strict
        `>` comparison - so this must be called AFTER the action's own
        GovernanceLog event is appended, never before, or the reviewer's
        own just-completed review would immediately look stale against
        their own action's own audit trail entry. See the call sites in
        `routes/workspace.py`'s `validate_finding`/`set_disposition`.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        workspace.item_reviewed_at.setdefault(reviewer, {})[object_id] = timestamp

        path = self._path_for(workspace.project_id)
        with self._save_lock:
            if not path.exists():
                return timestamp
            raw = json.loads(path.read_text(encoding="utf-8"))
            raw.setdefault("item_reviewed_at", {}).setdefault(reviewer, {})[object_id] = timestamp
            tmp_path = path.with_name(path.name + f".tmp-{uuid.uuid4().hex}")
            tmp_path.write_text(json.dumps(raw, indent=2), encoding="utf-8")
            tmp_path.replace(path)

        return timestamp

    def has_unreviewed_change(
        self, workspace: ProjectWorkspace, governance_log: GovernanceLog, reviewer: str, finding_id: str,
    ) -> bool:
        """
        CLAUDE-CA1D-ATTENTION-STATE-02: derived, never stored - the same
        "derived, never stored" discipline `review_state_for_finding`
        above already uses for a different question. Answers "has this
        Finding materially changed since `reviewer` last meaningfully
        reviewed it", by comparing `item_reviewed_at` against the
        existing, already-governed `finding_reviewed` GovernanceLog
        events for this finding - never a second, competing history of
        "what changed" invented for this feature's own convenience.

        Conservative by construction, never a guessed richer state:
        - No recorded review by this reviewer at all (missing key, or
          the persisted value isn't the plain non-empty string this
          field has only ever been written as) -> True (unreviewed).
          Malformed/wrong-typed persisted state fails this same way,
          never with an exception.
        - A recorded review exists, but a `finding_reviewed` event for
          this finding is timestamped AFTER it (by ANY reviewer, not
          just this one - another user's later disposition/validation
          is exactly the kind of material change that should make an
          earlier reviewer's own review stale again) -> True.
        - A recorded review exists and no later `finding_reviewed` event
          does -> False (still reviewed).

        First proof entity only: this only ever inspects `finding_reviewed`
        events. No other entity type's own change signal is implemented
        here - a Task/Source/Requirement caller would need its own
        derivation against whatever that entity's own trustworthy change
        signal turns out to be (see the design record's own Entity
        Coverage section), not a generalized abstraction invented ahead
        of a second real caller actually needing one.
        """
        per_reviewer = workspace.item_reviewed_at.get(reviewer) if isinstance(workspace.item_reviewed_at, dict) else None
        reviewed_at = per_reviewer.get(finding_id) if isinstance(per_reviewer, dict) else None
        if not isinstance(reviewed_at, str) or not reviewed_at:
            return True

        latest_change_at: Optional[str] = None
        for event in governance_log.read(workspace.project_id):
            if event.event_type != "finding_reviewed":
                continue
            if event.payload.get("finding_id") != finding_id:
                continue
            if latest_change_at is None or event.created_at > latest_change_at:
                latest_change_at = event.created_at

        if latest_change_at is None:
            return False
        return latest_change_at > reviewed_at

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
                # Only present for documents ingested after services/
                # ingestion.py started persisting the original upload -
                # None here is an honest gap for older projects, never
                # backfilled/fabricated.
                file_path=register_document_source.get("file_path"),
                file_hash=register_document_source.get("file_hash"),
            )
            workspace.sources.append(asdict(source))

        self.save(workspace)
        return workspace

    # -- Project Home presentation state (Prompt 3) ---------------------------

    def set_starred(self, workspace: ProjectWorkspace, starred: bool) -> ProjectWorkspace:
        """Toggle the Project's personal bookmark flag - see
        ProjectWorkspace.starred. No governance meaning and deliberately no
        GovernanceLog event (Prompt 3 #3)."""
        workspace.starred = starred
        return self.save(workspace)

    def set_project_details(
        self,
        workspace: ProjectWorkspace,
        actor: str,
        display_title: Optional[str] = None,
        display_description: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """Presentation-only override of the Project's displayed
        name/description - see ProjectWorkspace.display_title. Never
        touches any Source's own name/document_id."""
        workspace.display_title = display_title or None
        workspace.display_description = display_description or None
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_details_updated",
                actor=actor, role="system",
                payload={"display_title": workspace.display_title},
            )
        return workspace

    def set_operating_instructions(
        self,
        workspace: ProjectWorkspace,
        text: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
        actor_role: Optional[str] = None,
    ) -> ProjectWorkspace:
        """
        Records human-authored Project / Case Operating Instructions - see
        ProjectWorkspace.operating_instructions. These are always
        subordinate to governance: nothing in this store ever consults them
        to authorize a write, resolve Source authority, or bypass an
        approval gate (Prompt 3 #7).
        """
        workspace.operating_instructions = text
        workspace.operating_instructions_updated_by = actor
        workspace.operating_instructions_updated_at = _now()
        workspace.operating_instructions_updated_by_role = actor_role
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="operating_instructions_updated",
                actor=actor, role="system",
                payload={"length": len(text)},
            )
        return workspace

    def project_context_entries_for(self, workspace: ProjectWorkspace) -> list[dict]:
        """Every recorded Project Context entry, oldest first - the
        authoritative history. Callers wanting only the current one
        should use current_project_context below rather than indexing
        this list directly."""
        return list(workspace.project_context_entries)

    def current_project_context(self, workspace: ProjectWorkspace) -> Optional[dict]:
        """The Project's current direction/orientation - simply the last
        recorded entry, or None if nothing has ever been recorded. Never
        a separately-stored "current" field that could drift from the
        history - there is exactly one list, and current is always
        derived from it."""
        entries = workspace.project_context_entries
        return entries[-1] if entries else None

    def add_project_context_entry(
        self,
        workspace: ProjectWorkspace,
        text: str,
        actor: str,
        actor_role: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Records a NEW current Project Context - see
        ProjectWorkspace.project_context_entries' own docstring. Never
        edits or removes any prior entry; the previous current entry
        simply becomes history the moment a new one is appended. Empty
        text is rejected outright rather than silently accepted - an
        append-only history has no way to later distinguish "someone
        meant to clear it" from "someone submitted the form empty by
        mistake", so recording nothing is the only honest response
        here (see routes/workspace.py's own caller for how this is
        surfaced to the reviewer).
        """
        clean_text = text.strip()
        if not clean_text:
            raise CaseWorkspaceError("Project Context text cannot be empty.")

        entry = ProjectContextEntry(
            id=_new_id(), project_id=workspace.project_id, text=clean_text,
            created_at=_now(), created_by=actor, created_by_role=actor_role,
        )
        workspace.project_context_entries.append(asdict(entry))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_context_updated",
                actor=actor, role="system",
                payload={"entry_id": entry.id, "length": len(clean_text)},
            )
        return asdict(entry)

    def set_source_note(
        self,
        workspace: ProjectWorkspace,
        source_id: str,
        text: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Document Context (CLAUDE-POSTCAMEL-PROJECT-CONTEXT-01): human-
        supplied orientation attached to ONE Source - what it is, why
        it's present, its status, caveats, or intended use - reusing
        Source's own pre-existing `note` field (Prompt-era, never before
        wired to a route). Deliberately a plain overwrite (like
        operating_instructions), not an append-only history like Project
        Context - this stage's own governing prompt scopes history/non-
        overwrite specifically to Project Context, and a per-Document
        note carries no comparable "don't lose the earlier client
        direction" requirement. Explicitly independent of Project
        Context in both directions: setting this never touches
        project_context_entries, and vice versa.
        """
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        source["note"] = text.strip() or None
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="document_context_updated",
                actor=actor, role="system",
                payload={"source_id": source_id, "length": len(text.strip())},
                correlation_id=source_id,
            )
        return source

    @staticmethod
    def source_signature_for(workspace: "ProjectWorkspace") -> str:
        """A stable, order-independent fingerprint of the current
        Source set - used to decide whether a cached project_briefing
        is still current, or was generated from a set of Sources that
        has since changed. Deliberately just ids, not content hashes -
        a Source's own file content is immutable once ingested
        (revisions create a NEW Source, see supersedes_source_id), so
        the id set alone is a sufficient, honest signal."""
        return ",".join(sorted(s["id"] for s in workspace.sources))

    # CLAUDE-P38-D2: must be >= services.project_briefing's own
    # DEFAULT_TIMEOUT_SECONDS (45s) with margin, so a genuinely in-flight
    # call is never treated as abandoned before it could honestly have
    # finished or timed out on its own.
    PROJECT_BRIEFING_GENERATION_TIMEOUT_SECONDS = 90

    def start_project_briefing_generation(
        self, workspace: ProjectWorkspace, actor: str,
    ) -> ProjectWorkspace:
        """
        CLAUDE-P38-D2: set immediately before the real Anthropic call
        begins - the duplicate-call/idempotency guard automatic
        generation needs (a page refresh or a second reviewer opening
        the same project while generation is already in flight must not
        start a second real, billed call). Paired with
        clear_project_briefing_generation and generation_in_progress_for.
        """
        workspace.project_briefing_generation_started_at = _now()
        self.save(workspace)
        return workspace

    def clear_project_briefing_generation(self, workspace: ProjectWorkspace) -> ProjectWorkspace:
        workspace.project_briefing_generation_started_at = None
        self.save(workspace)
        return workspace

    def record_project_briefing_failure(self, workspace: ProjectWorkspace, reason: str) -> ProjectWorkspace:
        """CLAUDE-P38-D2: honestly distinguishes "generation failed" from
        "never attempted" - see the field's own comment on why this
        exists (the automatic-regeneration rule that must not retry
        forever against a repeatedly-failing provider)."""
        workspace.project_briefing_generation_started_at = None
        workspace.project_briefing_last_failure_reason = reason
        workspace.project_briefing_last_failure_at = _now()
        self.save(workspace)
        return workspace

    @classmethod
    def generation_in_progress_for(cls, workspace: ProjectWorkspace) -> bool:
        """True only while a generation start is both recorded AND
        still within the timeout window - a start timestamp older than
        that is treated as abandoned (e.g. the worker process that set
        it was killed/recycled mid-call), never a permanently stuck
        flag with no way to retry."""
        started_at = workspace.project_briefing_generation_started_at
        if not started_at:
            return False
        try:
            started = datetime.fromisoformat(started_at)
        except ValueError:
            return False
        elapsed = (datetime.now(timezone.utc) - started).total_seconds()
        return elapsed < cls.PROJECT_BRIEFING_GENERATION_TIMEOUT_SECONDS

    def set_project_briefing(
        self,
        workspace: ProjectWorkspace,
        briefing: dict,
        source_signature: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        Caches services.project_briefing.generate_project_briefing's
        output (a plain dict, asdict(ProjectBriefingResult)). Called
        automatically once, right after ingestion, when the project's
        security policy allows it without approval (CLAUDE-P38-D2) - or
        explicitly, on approval/regeneration, otherwise. `source_
        signature` (source_signature_for, above) lets the route honestly
        detect "the active source set changed since this was generated"
        without guessing at what changed.

        CLAUDE-P38-D2: if a briefing already exists, it is preserved as
        project_briefing_previous (exactly one prior version, not a
        history log) before being overwritten - a regeneration is never
        a silent, unrecoverable loss of the last one. Also clears the
        in-progress flag unconditionally, since a completed generation
        (successful or not) is, by definition, no longer in progress.
        """
        if workspace.project_briefing is not None:
            workspace.project_briefing_previous = workspace.project_briefing
            workspace.project_briefing_previous_generated_at = workspace.project_briefing_generated_at
            workspace.project_briefing_previous_source_signature = workspace.project_briefing_source_signature

        workspace.project_briefing = briefing
        workspace.project_briefing_generated_at = _now()
        workspace.project_briefing_generated_by = actor
        workspace.project_briefing_source_signature = source_signature
        workspace.project_briefing_generation_started_at = None
        workspace.project_briefing_last_failure_reason = None
        workspace.project_briefing_last_failure_at = None
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_briefing_generated",
                actor=actor, role="system",
                payload={"source_signature": source_signature},
            )
        return workspace

    def set_operating_environment(
        self,
        workspace: ProjectWorkspace,
        operating_environment: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        CLAUDE-P29: the single, centralized gate for
        ProjectWorkspace.operating_environment -- see that field's own
        comment. This is the ONLY method anywhere that ever writes it,
        and it enforces the lock structurally, not just by convention:
        raises OperatingEnvironmentAlreadySetError outright if the
        field is already non-None, with NO exception for re-setting it
        to the same value it already holds -- "locked" here means
        exactly one successful call to this method per project,
        ever, full stop.

        Serves two distinct real callers with the identical rule:
        1. New-project creation (services/ingestion.py's
           ingest_upload) -- called once, immediately after the
           workspace is first created, before any other write.
        2. One-time legacy classification (routes/workspace.py) -- an
           existing project whose operating_environment is still None
           (created before this field existed) may be classified
           exactly once. This is NOT a Client<->Proponent conversion --
           it is the first establishment of a previously absent value,
           the same "honest gap, never silently converted" treatment
           this codebase already gives every other field that predates
           its own introduction (see ProjectWorkspace.version's own
           comment for the established precedent).

        Deliberately validates against environment_capabilities.
        OPERATING_ENVIRONMENTS as a closed set (raises ValueError for
        anything else, including a well-intentioned "other") rather
        than this module's usual normalize_open_world_value pattern --
        see environment_capabilities.py's module docstring for why an
        unrecognized value must never be silently accepted here.
        """
        from services.environment_capabilities import is_valid_operating_environment

        if not is_valid_operating_environment(operating_environment):
            raise ValueError(
                f"{operating_environment!r} is not a recognized operating environment.",
            )
        if workspace.operating_environment is not None:
            raise OperatingEnvironmentAlreadySetError(
                f"Project {workspace.project_id!r} already has its operating environment "
                f"locked to {workspace.operating_environment!r} -- it cannot be changed.",
            )

        previous_state = workspace.operating_environment  # always None here, kept explicit for the log
        workspace.operating_environment = operating_environment
        workspace.operating_environment_set_by = actor
        workspace.operating_environment_set_at = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="operating_environment_established",
                actor=actor, role="system",
                payload={
                    "previous_state": previous_state,
                    "operating_environment": operating_environment,
                },
            )
        return workspace

    def correct_operating_environment(
        self,
        workspace: ProjectWorkspace,
        operating_environment: str,
        actor: str,
        reason: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        CLAUDE-VOICE27-MISCLASS-01: a deliberate, separate, admin-only
        governed exception to set_operating_environment's own one-time
        lock -- for the genuine case that field's own docstring didn't
        anticipate: the value was already established, but wrong from
        the start (e.g. picked based on which side ISSUED the source
        document rather than which side this team is actually working
        from -- an RFP is routinely received and worked from the
        Design-Builder/Proponent side, not evidence of Client/Owner
        role). set_project_owner (above) already has the identical
        precedent for a different project-level field: "a wrong
        backfill inference... must be recoverable," admin-only,
        reassignable, fully logged. Deliberately NOT a relaxation of
        set_operating_environment's own lock (that method's callers -
        new-project creation and one-time legacy classification - are
        completely unaffected and still enforce their single-call
        guarantee); this is a second, explicit, harder-to-reach path
        for the rarer "the one existing value itself is wrong" case,
        requiring a real `reason` (unlike set_operating_environment,
        which needs none - establishing a value for the first time
        isn't correcting anything) so the audit trail always records
        WHY a locked value moved, not just that it did. Authority
        (admin-only) is enforced by the CALLER, matching every other
        method in this class - see set_project_owner's own comment for
        why this module never checks a role itself.
        """
        from services.environment_capabilities import is_valid_operating_environment

        if not is_valid_operating_environment(operating_environment):
            raise ValueError(
                f"{operating_environment!r} is not a recognized operating environment.",
            )
        if not reason or not reason.strip():
            raise CaseWorkspaceError("A reason is required to correct the project operating environment.")
        if workspace.operating_environment == operating_environment:
            raise CaseWorkspaceError(
                f"Project {workspace.project_id!r} is already classified as {operating_environment!r}.",
            )

        previous_environment = workspace.operating_environment
        workspace.operating_environment = operating_environment
        workspace.operating_environment_set_by = actor
        workspace.operating_environment_set_at = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="operating_environment_corrected",
                actor=actor, role="system",
                payload={
                    "previous_environment": previous_environment,
                    "operating_environment": operating_environment,
                    "reason": reason.strip(),
                },
            )
        return workspace

    def record_go_no_go_decision(
        self,
        workspace: ProjectWorkspace,
        decision_stage: str,
        decision: str,
        rationale: str,
        decided_by: str,
        anomalies: Optional[list] = None,
        governance_log: Optional[GovernanceLog] = None,
        decided_by_role: Optional[str] = None,
    ) -> dict:
        """
        CLAUDE-P30: records one Go/No-Go decision -- "go_no_go" in
        environment_capabilities.py's registry. Requires the project's
        operating_environment to already be locked: a Go/No-Go decision
        only makes sense once it's known which side's decision-stage
        vocabulary applies (see decision_stages_for_environment), so a
        legacy/unclassified project cannot record one until classified --
        an honest limitation, not silently defaulted to either side's
        vocabulary.
        """
        from services.environment_capabilities import decision_stages_for_environment

        if workspace.operating_environment is None:
            raise CaseWorkspaceError(
                "This project's operating environment has not been established yet -- "
                "a Go/No-Go decision requires knowing which environment's decision "
                "stages apply."
            )
        if decision not in GO_NO_GO_DECISIONS:
            raise CaseWorkspaceError(
                f"{decision!r} is not a recognized Go/No-Go decision. Use one of: "
                f"{', '.join(GO_NO_GO_DECISIONS)}."
            )
        allowed_stages = decision_stages_for_environment(workspace.operating_environment)
        if decision_stage not in allowed_stages:
            raise CaseWorkspaceError(
                f"{decision_stage!r} is not a recognized decision stage for this "
                f"project's {workspace.operating_environment!r} environment."
            )
        if not rationale or not rationale.strip():
            raise CaseWorkspaceError("A Go/No-Go decision requires a recorded rationale.")

        assessment = GoNoGoAssessment(
            id=_new_id(),
            project_id=workspace.project_id,
            operating_environment=workspace.operating_environment,
            decision_stage=decision_stage,
            decision=decision,
            anomalies=list(anomalies or []),
            rationale=rationale.strip(),
            decided_by=decided_by,
            decided_at=_now(),
            decided_by_role=decided_by_role,
        )
        workspace.go_no_go_assessments.append(asdict(assessment))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="go_no_go_decided",
                actor=decided_by, role="human",
                payload={
                    "assessment_id": assessment.id,
                    "decision_stage": decision_stage,
                    "decision": decision,
                },
            )
        return asdict(assessment)

    def go_no_go_assessments_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.go_no_go_assessments)

    def set_project_security_profile(
        self, workspace: ProjectWorkspace, security_profile: str, actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        CLAUDE-P31: unlike set_operating_environment, this is NOT a
        one-time lock -- a project's security classification legitimately
        changes as policy or the project's own content changes (Part
        XIV). Every change is still fully accountable: the previous value
        is always captured in the logged event before being overwritten,
        never silently lost, and this remains the single method that
        ever writes this field (same "one gate" discipline as every
        other governed field in this store, just without the
        already-set-forever refusal).
        """
        from services.security_policy import is_valid_classification

        if not is_valid_classification(security_profile):
            raise ValueError(f"{security_profile!r} is not a recognized security profile.")

        previous_profile = workspace.security_profile
        workspace.security_profile = security_profile
        workspace.security_profile_set_by = actor
        workspace.security_profile_set_at = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="security_profile_set",
                actor=actor, role="system",
                payload={"previous_profile": previous_profile, "security_profile": security_profile},
            )
        return workspace

    def set_project_owner(
        self, workspace: ProjectWorkspace, owner: str, actor: str,
        source: str = "admin_assigned", governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        CLAUDE-P32: the single method that ever writes `owner` -- not a
        one-time lock like set_operating_environment (see the field's own
        comment for why: a wrong backfill inference must be recoverable).
        Authority (owner-or-admin, or admin-only for reassigning an
        already-owned project) is enforced by the CALLER -- this store
        module does not import services.auth/models, so it cannot check
        a role itself, the same reason archive_case takes actor_role as a
        plain string rather than looking it up.

        `source` is provenance, not a security check: "admin_assigned"
        (a real admin action, the normal route path) vs.
        "inferred_from_ingestion_actor" (services.project_access's
        deterministic, exact-match-only backfill) -- recorded on every
        event so the audit trail never conflates an automatic inference
        with a deliberate human decision.
        """
        if not owner or not owner.strip():
            raise CaseWorkspaceError("A project owner requires a username.")

        previous_owner = workspace.owner
        workspace.owner = owner.strip()
        workspace.owner_set_by = actor
        workspace.owner_set_at = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_owner_set",
                actor=actor, role="system",
                payload={"previous_owner": previous_owner, "owner": workspace.owner, "source": source},
            )
        return workspace

    def grant_project_access(
        self, workspace: ProjectWorkspace, username: str, actor: str, actor_role: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """
        CLAUDE-P32: owner-or-admin authority, the same pattern
        archive_case/derive_case already established in this module
        (actor_role passed through as a plain string by the caller, who
        already knows the real session role). An allow-listed user
        gains no further grant/revoke authority of their own -- only the
        owner or an admin can extend or shrink this list.
        """
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may grant project access.")
        if not username or not username.strip():
            raise CaseWorkspaceError("A username is required to grant project access.")

        username = username.strip()
        if username not in workspace.access_allow_list:
            workspace.access_allow_list.append(username)
            self.save(workspace)
            if governance_log is not None:
                governance_log.append(
                    project_id=workspace.project_id, event_type="project_access_granted",
                    actor=actor, role="system", payload={"username": username},
                )
        return workspace

    def revoke_project_access(
        self, workspace: ProjectWorkspace, username: str, actor: str, actor_role: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may revoke project access.")

        if username in workspace.access_allow_list:
            workspace.access_allow_list.remove(username)
            self.save(workspace)
            if governance_log is not None:
                governance_log.append(
                    project_id=workspace.project_id, event_type="project_access_revoked",
                    actor=actor, role="system", payload={"username": username},
                )
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
        folder_id: Optional[str] = None,
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

        CLAUDE-RFP27-TERRITORY-01: `folder_id`, when given, is NOT
        validated against workspace.folders here - callers that resolve
        a real Folder (CaseWorkspaceStore.ensure_folder_path) already
        guarantee it exists; this stays a plain optional passthrough, the
        same trust level file_path/origin_reference already have, so
        add_source's existing callers (none of which pass folder_id
        today) are completely unaffected.
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
            folder_id=folder_id,
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
        mime_type: Optional[str] = None,
        size_bytes: Optional[int] = None,
        security_classification: Optional[str] = None,
        extractor_version: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Backfills/corrects document-identity metadata on an already-
        registered Source (e.g. metadata that arrives after the file
        itself was uploaded). Only supplied fields are changed - honest
        absence is preserved for anything left None.

        `mime_type`/`size_bytes`/`security_classification`/
        `extractor_version` (CLAUDE-MM1) reuse this same partial-update
        method rather than a second one - they are document-identity
        metadata exactly like every field above, just added a stage
        later (services/pdf_intelligence.py is this method's first real
        caller for these four, populating them once the actual PDF bytes
        have been read).
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
        if mime_type is not None:
            source["mime_type"] = mime_type
        if size_bytes is not None:
            source["size_bytes"] = size_bytes
        if security_classification is not None:
            source["security_classification"] = security_classification
        if extractor_version is not None:
            source["extractor_version"] = extractor_version

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
        actor: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
        kind: Optional[str] = None,
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

        CLAUDE-POSTCAMEL-COMM-I4A: originally drawing-only
        (`kind` hardcoded to `SOURCE_KIND_DRAWING`, `width`/`height`
        required) - a real OPR-2.5 gap, since no other Source kind could
        be formally revised/superseded at all. `kind` now defaults to
        the OLD Source's own kind (a revision of a text_record stays a
        text_record, a revision of a project_document stays a
        project_document; drawing callers are unaffected since they
        pass `kind=SOURCE_KIND_DRAWING` explicitly or supersede a
        drawing, which resolves to the same value either way).
        `width`/`height` are drawing/image-specific and now Optional -
        every other Source kind simply has no pixel dimensions, the
        same honest-absence pattern every other optional Source field
        already uses. `region_statuses`/`compare_region` below remain
        unconditionally exercised for parity with the pre-existing
        drawing path, but are naturally inert for any Source with no
        crop-bearing Artifacts (true for every non-drawing kind today) -
        no kind-specific branching was needed there.
        """
        old_source = self._find(workspace.sources, old_source_id)
        if old_source is None:
            raise CaseWorkspaceError(f"Source {old_source_id} was not found.")
        if old_source.get("superseded_by_source_id"):
            raise CaseWorkspaceError(
                f"Source {old_source_id} has already been superseded by "
                f"{old_source['superseded_by_source_id']} - revise that Source instead."
            )

        new_source = Source(
            id=_new_id(),
            project_id=workspace.project_id,
            kind=kind or old_source["kind"],
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

    @staticmethod
    def active_sources(workspace: ProjectWorkspace) -> list[dict]:
        """CLAUDE-P40-E2: the filter every DISPLAY/AI-context/search
        read of workspace.sources should use going forward - a removed
        Source is excluded, never deleted. Provenance lookups that must
        keep resolving a Source regardless of removal (a Finding's own
        artifact/source citation, an existing Requirement's evidence
        reference) deliberately do NOT use this filter - they call
        _find directly against the full, unfiltered workspace.sources,
        exactly as they always have, so "Document removed" can be shown
        as an honest state on that reference rather than a broken one."""
        return [s for s in workspace.sources if not s.get("removed_at")]

    @staticmethod
    def removed_sources(workspace: ProjectWorkspace) -> list[dict]:
        return [s for s in workspace.sources if s.get("removed_at")]

    def remove_source(
        self, workspace: ProjectWorkspace, source_id: str, actor: str, actor_role: str = "",
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """CLAUDE-P40-E2, Section C: "Remove Document" - recoverable,
        never a deletion. Only ever sets removed_at/removed_by/
        removal_reason on the existing record; the id, file_path,
        checksum-bearing content on disk, and every dependent
        Finding/Artifact/Requirement reference are completely
        untouched. Restoring re-activates the SAME record - no
        re-ingestion, no new id (see restore_source). Owner-or-admin
        authority - the same pattern grant_project_access/archive_case
        already established in this module."""
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may remove a Document.")
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if source.get("removed_at"):
            raise CaseWorkspaceError(f"Source {source_id} is already removed.")

        removed_at = _now()
        source["removed_at"] = removed_at
        source["removed_by"] = actor
        source["removal_reason"] = reason
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="document_removed",
                actor=actor, role="human",
                payload={"source_id": source_id, "name": source.get("name"), "reason": reason, "removed_at": removed_at},
                correlation_id=source_id,
            )
        return source

    def restore_source(
        self, workspace: ProjectWorkspace, source_id: str, actor: str, actor_role: str = "",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """The exact same record, re-activated - never a new id, never
        re-ingested. See remove_source's own docstring. Same
        owner-or-admin authority as removal itself."""
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may restore a Document.")
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if not source.get("removed_at"):
            raise CaseWorkspaceError(f"Source {source_id} is not removed.")

        source["removed_at"] = None
        source["removed_by"] = None
        source["removal_reason"] = None
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="document_restored",
                actor=actor, role="human",
                payload={"source_id": source_id, "name": source.get("name")},
                correlation_id=source_id,
            )
        return source

    def remove_project(
        self, workspace: ProjectWorkspace, actor: str, actor_role: str = "",
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """CLAUDE-P40-E2, Section C: "Remove Project" - a completely
        separate, recoverable mechanism from routes/portal.py's
        pre-existing delete_project (permanent, unchanged by this
        stage - "Project Entry Rule" for unwanted/duplicate/test
        entries). Removes the Project AND everything under it as one
        bundle, from ACTIVE USE only - every Case/Source/Requirement/
        Finding/conversation record is completely untouched in
        storage; only this one workspace-level flag changes, and every
        listing route (routes/portal.py's _accessible_documents,
        app.py's _nav_recent_projects) is what actually excludes a
        removed project from view. Restoring (restore_project) returns
        the exact same project_id and every child identifier/
        relationship unchanged - never a re-creation. Owner-or-admin
        authority, same pattern as every other project-level write."""
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may remove a Project.")
        if workspace.removed_at:
            raise CaseWorkspaceError("Project is already removed.")

        removed_at = _now()
        workspace.removed_at = removed_at
        workspace.removed_by = actor
        workspace.removal_reason = reason
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_removed",
                actor=actor, role="human",
                payload={"reason": reason, "removed_at": removed_at},
            )
        return workspace

    def restore_project(
        self, workspace: ProjectWorkspace, actor: str, actor_role: str = "",
        governance_log: Optional[GovernanceLog] = None,
    ) -> ProjectWorkspace:
        """The exact same project, same project_id, every child record
        and relationship unchanged - see remove_project's own
        docstring. Same owner-or-admin authority as removal itself."""
        if actor != workspace.owner and actor_role != "admin":
            raise CaseWorkspaceError("Only the project owner or an admin may restore a Project.")
        if not workspace.removed_at:
            raise CaseWorkspaceError("Project is not removed.")

        workspace.removed_at = None
        workspace.removed_by = None
        workspace.removal_reason = None
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="project_restored",
                actor=actor, role="human",
                payload={},
            )
        return workspace

    # -- folders (CLAUDE-P40-VW9) ------------------------------------------

    def _folder_path(self, workspace: ProjectWorkspace, folder_id: Optional[str]) -> list[dict]:
        """Derives the ancestor chain (root-most first, ending with the
        folder itself) by walking parent_folder_id - a folder's path is
        NEVER stored as a string (Folder's own docstring), the same
        "store flat, derive structure at read time" shape this module
        already uses everywhere else."""
        chain: list[dict] = []
        seen: set[str] = set()
        current_id = folder_id
        while current_id is not None:
            if current_id in seen:
                break  # defensive only - move_folder's own cycle guard means a real cycle should never exist
            seen.add(current_id)
            folder = self._find(workspace.folders, current_id)
            if folder is None:
                break
            chain.append(folder)
            current_id = folder.get("parent_folder_id")
        chain.reverse()
        return chain

    def _folder_descendant_ids(self, workspace: ProjectWorkspace, folder_id: str) -> set[str]:
        """Every folder id transitively parented under folder_id (never
        including folder_id itself) - move_folder's own cycle guard
        (Section 5's own "prevent invalid cycles")."""
        children_by_parent: dict[Optional[str], list[dict]] = {}
        for f in workspace.folders:
            children_by_parent.setdefault(f.get("parent_folder_id"), []).append(f)
        descendants: set[str] = set()
        frontier = [folder_id]
        while frontier:
            current = frontier.pop()
            for child in children_by_parent.get(current, []):
                if child["id"] not in descendants:
                    descendants.add(child["id"])
                    frontier.append(child["id"])
        return descendants

    def _active_folder_siblings(
        self, workspace: ProjectWorkspace, project_id: str, root: str, parent_folder_id: Optional[str],
    ) -> list[dict]:
        return [
            f for f in workspace.folders
            if f["project_id"] == project_id and f["root"] == root
            and f.get("parent_folder_id") == parent_folder_id and not f.get("removed_at")
        ]

    def _reject_if_sibling_folder_name_taken(
        self, workspace: ProjectWorkspace, project_id: str, root: str, parent_folder_id: Optional[str],
        name: str, exclude_folder_id: Optional[str] = None,
    ) -> None:
        """Sibling-scoped uniqueness (only folders sharing the same
        project/root/parent) - deliberately narrower than
        ingestion.py's own _reject_if_name_taken, which is scoped to the
        WHOLE registry (Project entry names); exact-match string
        comparison and a short, plain, no-id message, matching that
        precedent's own style."""
        for sibling in self._active_folder_siblings(workspace, project_id, root, parent_folder_id):
            if sibling["id"] != exclude_folder_id and sibling["name"] == name:
                raise CaseWorkspaceError("A folder with that name already exists here.")

    def create_folder(
        self, workspace: ProjectWorkspace, name: str, parent_folder_id: Optional[str] = None,
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        CLAUDE-P40-VW9: creates a Design-Builder Workspace folder only -
        no caller may pass a root; this method always creates
        root=FOLDER_ROOT_DESIGN_BUILDER (Section 4's own "do not allow
        ordinary Design-Builder working-folder actions to silently
        modify [the Data Room]" - there is structurally no way to reach
        FOLDER_ROOT_DATA_ROOM through this method at all, not merely a
        convention some caller could bypass). No owner/admin gate,
        matching create_task/create_custom_tag's own precedent rather
        than remove_source/remove_project's - a Design-Builder folder is
        collaborative team working structure ("editable working
        organization created by the Project team"), not owner-locked
        evidence.
        """
        clean_name = (name or "").strip()
        if not clean_name:
            raise CaseWorkspaceError("A folder name cannot be empty.")
        if parent_folder_id is not None:
            parent = self._find(workspace.folders, parent_folder_id)
            if (
                parent is None or parent["project_id"] != workspace.project_id
                or parent["root"] != FOLDER_ROOT_DESIGN_BUILDER or parent.get("removed_at")
            ):
                raise CaseWorkspaceError("The parent folder was not found.")
        self._reject_if_sibling_folder_name_taken(
            workspace, workspace.project_id, FOLDER_ROOT_DESIGN_BUILDER, parent_folder_id, clean_name,
        )

        folder = Folder(
            id=_new_id(), project_id=workspace.project_id, root=FOLDER_ROOT_DESIGN_BUILDER,
            name=clean_name, created_at=_now(), created_by=actor, parent_folder_id=parent_folder_id,
        )
        workspace.folders.append(asdict(folder))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="folder_created",
                actor=actor or "system", role="human",
                payload={"folder_id": folder.id, "name": clean_name, "parent_folder_id": parent_folder_id},
                correlation_id=folder.id,
            )
        return asdict(folder)

    def ensure_folder_path(
        self, workspace: ProjectWorkspace, root: str, relative_path: str,
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> Optional[str]:
        """
        CLAUDE-RFP27-TERRITORY-01: the ONE place in this codebase allowed
        to construct a `root=FOLDER_ROOT_DATA_ROOM` Folder -
        `create_folder` above is deliberately hard-coded to
        FOLDER_ROOT_DESIGN_BUILDER only (its own docstring: "structurally
        no way to reach FOLDER_ROOT_DATA_ROOM through this method at all,
        not merely a convention some caller could bypass") - that guard
        stays completely untouched; this is a second, explicitly separate
        entry point for the "governed, deliberate act" that docstring
        itself named as the future exception. Called only from
        services/ingestion.py's own reconcile_data_room_upload (real,
        eligible files - directories are implied by a file's own path)
        and routes/workspace.py's own explicit "register empty folder
        paths" route (real directories with zero files - the one case a
        file-upload can never report, since browsers never emit a File
        for an empty directory).

        `relative_path` is a "/"-separated path (e.g. "01 RFP Documents/
        01.2 Addenda") - idempotent: walks each segment, reusing an
        existing same-named sibling under the same root/parent rather
        than creating a duplicate every time this is called again for
        the same real directory (a reconciliation run over an unchanged
        Data Room must be a safe no-op). Returns the deepest segment's
        folder_id, or None for an empty/root-only path.
        """
        segments = [s.strip() for s in relative_path.replace("\\", "/").split("/") if s.strip()]
        parent_folder_id: Optional[str] = None
        folder_id: Optional[str] = None
        for segment in segments:
            existing = next(
                (
                    f for f in self._active_folder_siblings(workspace, workspace.project_id, root, parent_folder_id)
                    if f["name"] == segment
                ),
                None,
            )
            if existing is not None:
                folder_id = existing["id"]
            else:
                folder = Folder(
                    id=_new_id(), project_id=workspace.project_id, root=root,
                    name=segment, created_at=_now(), created_by=actor, parent_folder_id=parent_folder_id,
                )
                workspace.folders.append(asdict(folder))
                folder_id = folder.id
                if governance_log is not None:
                    governance_log.append(
                        project_id=workspace.project_id, event_type="folder_created",
                        actor=actor or "system", role="system",
                        payload={"folder_id": folder.id, "name": segment, "root": root, "parent_folder_id": parent_folder_id},
                        correlation_id=folder.id,
                    )
            parent_folder_id = folder_id
        self.save(workspace)
        return folder_id

    def set_source_folder(
        self, workspace: ProjectWorkspace, source_id: str, folder_id: Optional[str],
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """CLAUDE-RFP27-TERRITORY-01: relinks an EXISTING Source into a
        Folder without touching anything else about it (id, file_hash,
        content, evidence already extracted) - the real mechanism behind
        "preserve existing Source identity... do not create duplicate
        Sources merely because earlier files were uploaded from a flat
        ad-hoc location," used by reconcile_data_room_upload when a
        newly-scanned file's content hash matches an already-registered
        Source exactly."""
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        source["folder_id"] = folder_id
        self.save(workspace)
        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="source_relinked_to_folder",
                actor=actor or "system", role="system",
                payload={"source_id": source_id, "folder_id": folder_id},
                correlation_id=source_id,
            )
        return source

    def rename_folder(
        self, workspace: ProjectWorkspace, folder_id: str, new_name: str,
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Renaming never changes `id` - the same "location is external
        representation only" convention Folder's own docstring
        establishes."""
        folder = self._find(workspace.folders, folder_id)
        if folder is None or folder["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Folder {folder_id} was not found.")
        if folder.get("removed_at"):
            raise CaseWorkspaceError(f"Folder {folder_id} has been deleted.")
        clean_name = (new_name or "").strip()
        if not clean_name:
            raise CaseWorkspaceError("A folder name cannot be empty.")
        self._reject_if_sibling_folder_name_taken(
            workspace, workspace.project_id, folder["root"], folder.get("parent_folder_id"),
            clean_name, exclude_folder_id=folder_id,
        )
        folder["name"] = clean_name
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="folder_renamed",
                actor=actor or "system", role="human",
                payload={"folder_id": folder_id, "name": clean_name},
                correlation_id=folder_id,
            )
        return folder

    def move_folder(
        self, workspace: ProjectWorkspace, folder_id: str, new_parent_folder_id: Optional[str],
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 5's own "prevent invalid cycles" / "prevent movement
        outside the current Project" / "prevent movement into the Data
        Room unless a later governed action explicitly authorizes it" -
        all three enforced here, structurally, not merely by what the UI
        happens to offer as choices."""
        folder = self._find(workspace.folders, folder_id)
        if folder is None or folder["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Folder {folder_id} was not found.")
        if folder.get("removed_at"):
            raise CaseWorkspaceError(f"Folder {folder_id} has been deleted.")

        if new_parent_folder_id == folder_id:
            raise CaseWorkspaceError("A folder cannot be moved into itself.")
        if new_parent_folder_id is not None:
            new_parent = self._find(workspace.folders, new_parent_folder_id)
            if (
                new_parent is None or new_parent["project_id"] != workspace.project_id
                or new_parent["root"] != FOLDER_ROOT_DESIGN_BUILDER or new_parent.get("removed_at")
            ):
                raise CaseWorkspaceError("The destination folder was not found.")
            if new_parent_folder_id in self._folder_descendant_ids(workspace, folder_id):
                raise CaseWorkspaceError("A folder cannot be moved into one of its own subfolders.")

        self._reject_if_sibling_folder_name_taken(
            workspace, workspace.project_id, folder["root"], new_parent_folder_id,
            folder["name"], exclude_folder_id=folder_id,
        )
        folder["parent_folder_id"] = new_parent_folder_id
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="folder_moved",
                actor=actor or "system", role="human",
                payload={"folder_id": folder_id, "new_parent_folder_id": new_parent_folder_id},
                correlation_id=folder_id,
            )
        return folder

    def delete_folder(
        self, workspace: ProjectWorkspace, folder_id: str,
        actor: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 4's own "delete an empty folder" - never a populated
        one; refuses outright if any active child folder exists.
        Recoverable (removed_at), matching Source/Project's own tombstone
        convention - see Folder's own docstring for why this is still the
        right shape even though nothing here holds real content to lose.
        No restore UI is built this stage (not part of the required
        Design-Builder operation list) - the data itself stays
        recoverable, a future stage can add a "Removed Folders" surface
        the same way Removed Items/Removed Projects already work."""
        folder = self._find(workspace.folders, folder_id)
        if folder is None or folder["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Folder {folder_id} was not found.")
        if folder.get("removed_at"):
            raise CaseWorkspaceError(f"Folder {folder_id} is already deleted.")
        has_active_children = any(
            f["project_id"] == workspace.project_id and f.get("parent_folder_id") == folder_id and not f.get("removed_at")
            for f in workspace.folders
        )
        if has_active_children:
            raise CaseWorkspaceError("Only an empty folder can be deleted - move or delete its contents first.")

        removed_at = _now()
        folder["removed_at"] = removed_at
        folder["removed_by"] = actor
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="folder_deleted",
                actor=actor or "system", role="human",
                payload={"folder_id": folder_id, "name": folder.get("name")},
                correlation_id=folder_id,
            )
        return folder

    # -- cases -----------------------------------------------------------------

    def create_case(self, workspace: ProjectWorkspace, title: str, objective: str, created_by: Optional[str] = None) -> dict:
        """
        `created_by` is optional only for backward compatibility with
        existing callers that predate Case visibility (see CaseRecord's
        own docstring) - every new Case is unconditionally CASE_
        VISIBILITY_PRIVATE regardless of whether an actor was given;
        visibility is never a caller-chosen value in this tranche.
        """
        case = CaseRecord(
            id=_new_id(),
            project_id=workspace.project_id,
            title=title,
            objective=objective,
            created_at=_now(),
            visibility=CASE_VISIBILITY_PRIVATE,
            created_by=created_by,
        )
        workspace.cases.append(asdict(case))
        self.save(workspace)
        return asdict(case)

    def visible_cases_for(self, workspace: ProjectWorkspace, actor: str) -> list[dict]:
        """
        The one real enforcement point for Case privacy (ratified
        governance baseline): a Case is visible to `actor` if it is not
        private, or if `actor` is its recorded creator/owner. Every
        route or query that lists, switches between, or resolves a
        default Case MUST go through this - filtering `workspace.cases`
        directly, or trusting an id supplied by the caller without
        checking it against this list first, silently re-opens exactly
        the "field called visibility='private' while unrestricted
        queries still return the Case" failure this method exists to
        prevent. Project membership/authentication alone is deliberately
        NOT sufficient here - see this method's own callers for where
        an authenticated-but-non-owner actor is still excluded.
        """
        # Open Cases before archived ones (stable within each group, so
        # relative creation order is otherwise unchanged) - archived Cases
        # accumulate over a project's life and would otherwise crowd out
        # active work in every caller that renders this list in order.
        # Safe to sort here, not just at render time: every other caller
        # (see this method's own callers) only uses this for set-membership
        # checks, never list order/indexing.
        return sorted(
            (
                c for c in workspace.cases
                if c["visibility"] != CASE_VISIBILITY_PRIVATE or c.get("created_by") == actor
            ),
            key=lambda c: c["status"] == CASE_STATUS_ARCHIVED,
        )

    def share_case(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        The one authorized transition this tranche implements: PRIVATE
        -> SHARED, by explicit human action only. Deliberately narrow
        authority model for this tranche: only the Case's own recorded
        creator/owner may share it - there is no collaboration threshold
        yet (specified but unbuilt, see governance/specified-unbuilt/
        investigation-lifecycle-extensions.md), so no PM/authorized-role
        override is implemented here; inventing one now would be ambient
        authority this tranche was explicitly told not to add. A Case
        with created_by=None (a pre-visibility legacy record) cannot be
        shared through this method - there is no recorded owner to
        authorize the transition, and no actor is silently treated as
        one.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        self._require_case_not_archived(workspace, case_id)

        if case["visibility"] != CASE_VISIBILITY_PRIVATE:
            raise CaseWorkspaceError(
                f"Case {case_id} is already '{case['visibility']}' - only a "
                "Private Case can be shared."
            )

        if case.get("created_by") is None or actor != case["created_by"]:
            raise CaseWorkspaceError(
                "Only this Case's own creator may share it. No delegated "
                "sharing authority exists yet."
            )

        prior_visibility = case["visibility"]
        shared_at = _now()
        case["visibility"] = CASE_VISIBILITY_SHARED
        case["shared_by"] = actor
        case["shared_at"] = shared_at
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_shared",
                actor=actor, role="human",
                payload={
                    "case_id": case_id, "case_creator": case["created_by"],
                    "prior_visibility": prior_visibility,
                    "resulting_visibility": CASE_VISIBILITY_SHARED,
                    "shared_at": shared_at,
                },
                correlation_id=case_id,
            )

        return case

    def retract_case_to_private(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        SHARED -> PRIVATE only, and only before the collaboration
        threshold has been crossed (Constitutional Invariant 12). A
        COLLABORATIVE Case rejects this outright - irreversibility is
        enforced here, at the validation gate, not merely documented.
        Owner-only, same authority model as share_case. Deliberately
        does not clear shared_by/shared_at - the fact this Case was
        once shared is not erased by retracting it, only its current
        visibility changes.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        self._require_case_not_archived(workspace, case_id)

        if case["visibility"] == CASE_VISIBILITY_COLLABORATIVE:
            raise CaseWorkspaceError(
                f"Case {case_id} is Collaborative - another party has already "
                "made a genuine, governed contribution. Reverting shared work "
                "to private is prohibited (Constitutional Invariant 12); this "
                "preserves shared provenance, not authorship."
            )
        if case["visibility"] != CASE_VISIBILITY_SHARED:
            raise CaseWorkspaceError(
                f"Case {case_id} is '{case['visibility']}' - only a Shared "
                "Case can be retracted to Private."
            )

        if case.get("created_by") is None or actor != case["created_by"]:
            raise CaseWorkspaceError("Only this Case's own creator may retract it.")

        retracted_at = _now()
        case["visibility"] = CASE_VISIBILITY_PRIVATE
        case["retracted_by"] = actor
        case["retracted_at"] = retracted_at
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_retracted_to_private",
                actor=actor, role="human",
                payload={
                    "case_id": case_id, "case_creator": case["created_by"],
                    "prior_visibility": CASE_VISIBILITY_SHARED,
                    "resulting_visibility": CASE_VISIBILITY_PRIVATE,
                    "retracted_at": retracted_at,
                },
                correlation_id=case_id,
            )

        return case

    def _cases_referencing_object(self, workspace: ProjectWorkspace, object_id: Optional[str]) -> list[dict]:
        """Every Case whose finding_ids/source_ids/artifact_ids contains
        object_id - used to resolve which Case(s) a Relationship's from_id/
        to_id belongs to, since Relationship carries no case_id of its own."""
        if not object_id:
            return []
        return [
            c for c in workspace.cases
            if object_id in c["finding_ids"] or object_id in c["source_ids"] or object_id in c["artifact_ids"]
        ]

    def _cross_collaboration_threshold_if_qualifying(
        self,
        workspace: ProjectWorkspace,
        case_id: Optional[str],
        actor: Optional[str],
        contribution_type: str,
        contribution_id: str,
    ) -> bool:
        """
        The one enforcement point for Constitutional Invariant 12
        becoming real, not just documented: SHARED -> COLLABORATIVE
        fires exactly once, the moment the first governed, attributed
        write by a non-owner actor actually commits. Callers are
        responsible for (a) already having filtered out machine/system-
        originated events before calling this at all - see each call
        site for how it distinguishes human origin - and (b) calling
        self.save(workspace) themselves, exactly once, immediately
        after, so this mutation and the qualifying write commit
        atomically together, never one without the other.

        Deliberately silent-and-safe on anything that doesn't qualify
        (no Case, not currently Shared, no actor, or actor is the
        owner) - this is a side effect of an otherwise-already-valid
        write, never a validation gate that could reject the write
        itself. Returns True only if this call actually crossed the
        threshold, so callers can correlate a governance_log event.
        """
        if not case_id:
            return False
        case = self._find(workspace.cases, case_id)
        if case is None:
            return False
        if case["visibility"] != CASE_VISIBILITY_SHARED:
            return False
        if not actor or actor == case.get("created_by"):
            return False

        case["visibility"] = CASE_VISIBILITY_COLLABORATIVE
        case["collaboration_established_by"] = actor
        case["collaboration_established_at"] = _now()
        case["collaboration_contribution_type"] = contribution_type
        case["collaboration_contribution_id"] = contribution_id
        return True

    def _require_case_not_archived(self, workspace: ProjectWorkspace, case_id: Optional[str]) -> None:
        """
        The single centralized frozen-state guard: every governed write
        that mutates a Case's contribution set, or the Case's own
        visibility, calls this first. `case_id=None` is a legitimate no-op
        (a Project-level write with no Case at all - archiving is a
        Case-scoped concept and has nothing to say about those). A
        missing Case is also a no-op here - the caller's own subsequent
        `_find`/existence check is responsible for that error, this guard
        only ever adds an ADDITIONAL rejection reason for an existing,
        archived Case, never replaces the normal not-found check.
        """
        if not case_id:
            return
        case = self._find(workspace.cases, case_id)
        if case is not None and case.get("status") == CASE_STATUS_ARCHIVED:
            raise CaseWorkspaceError(
                f"Case {case_id} is archived and frozen - no new governed "
                "contributions, and no visibility change, may be made to it. "
                "Historical content remains readable; new work requires a "
                "separately-authorized Derive to a new Case (not yet built)."
            )

    def archive_case(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        actor: str,
        actor_role: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Archive is terminal/frozen status, not a visibility state (see the
        CASE_STATUS_* comment above) - permitted from PRIVATE, SHARED, or
        COLLABORATIVE alike, since Archive is preservation, not
        publication, and never itself changes visibility. Never removes,
        rewrites, or resolves any existing contribution - unresolved
        comments/Findings/etc. remain exactly as they were, permanently,
        as part of the frozen historical record; they are not required to
        be withdrawn or resolved first, and a contributor who is no longer
        reachable is never a blocker.

        Authority: the narrowest existing legitimate pattern, not a new
        role architecture - the Case's own owner, OR an actor whose
        `actor_role` is the system's existing "admin" role
        (models.ROLE_ADMIN's value, passed through as a plain string
        rather than importing models/services.auth into this pure domain
        module - the same decoupling already used for `reviewer`/`actor`
        parameters everywhere else in this file). This is exactly the
        "Design Manager/project authority" path the ratified tranche
        describes: an admin can archive even if the original owner is
        unavailable, without inventing anything beyond the role
        distinction that already exists system-wide.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")

        if case.get("status") == CASE_STATUS_ARCHIVED:
            raise CaseWorkspaceError(f"Case {case_id} is already archived.")

        is_owner = case.get("created_by") is not None and actor == case["created_by"]
        is_admin_override = actor_role == "admin"
        if not (is_owner or is_admin_override):
            raise CaseWorkspaceError(
                "Only this Case's own creator, or an actor with the admin "
                "role, may archive it."
            )

        prior_visibility = case["visibility"]
        archived_at = _now()
        case["status"] = CASE_STATUS_ARCHIVED
        case["archived_by"] = actor
        case["archived_at"] = archived_at
        case["archive_authority"] = "owner" if is_owner else "admin_override"
        case["archive_prior_visibility"] = prior_visibility
        # Deliberately does NOT touch case["visibility"] - archiving never
        # changes who could see the Case, only whether it can still change.
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_archived",
                actor=actor, role="human",
                payload={
                    "case_id": case_id, "case_creator": case.get("created_by"),
                    "archive_authority": case["archive_authority"],
                    "prior_visibility": prior_visibility,
                    "archived_at": archived_at,
                },
                correlation_id=case_id,
            )

        return case

    def derived_cases_of(self, workspace: ProjectWorkspace, archived_case_id: str) -> list[dict]:
        """Reverse lineage lookup: every Case whose derived_from_case_id
        points at archived_case_id. Cheap field filter - the authoritative
        structural record is the accompanying RELATIONSHIP_TYPE_DERIVED_FROM
        Relationship (see derive_case_from_archive), but for the common
        "what was derived from this archive" query this denormalized
        pointer is sufficient and avoids an unnecessary relationship scan."""
        return [c for c in workspace.cases if c.get("derived_from_case_id") == archived_case_id]

    def derive_case_from_archive(
        self,
        workspace: ProjectWorkspace,
        archived_case_id: str,
        actor: str,
        actor_role: Optional[str] = None,
        title: Optional[str] = None,
        objective: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Archive is terminal for the OBJECT, not for the WORK: this is the
        one authorized way continued reasoning proceeds after archival - a
        brand new Case (new permanent id, new identity) that carries
        forward only the minimal working context, never the archived
        Case's own history.

        Explicitly NOT Supersession (the archived Case is not being
        replaced or corrected - it remains standing, permanent historical
        truth) and NOT a mutation of any kind to the archived Case - this
        method never writes to the archived Case's own record.

        Working context copied onto the new Case (per this tranche's
        "copy the working context; reference the history; do not clone
        the history"): `title`/`objective` (overridable by the caller,
        defaulting to the archived Case's own values - the minimal
        structural fields intrinsic to Case identity) and `source_ids`
        (references to Source *documents* - copying the reference list
        duplicates no content, since Source objects themselves are never
        cloned or mutated by this).

        Deliberately NOT copied - these remain attached to the archived
        Case exclusively, reachable only through the lineage pointer, never
        duplicated: conversation, analysis_ids, finding_ids, artifact_ids,
        activity_ids (and, transitively, every review thread/message/
        ReviewerValidation/Disposition/Attention/collaboration/archive
        event that referenced the archived Case - none of those carry a
        case_id pointing at the new Case, so they simply do not appear
        there).

        Visibility: the new Case always begins CASE_VISIBILITY_PRIVATE,
        regardless of what the archived Case's own visibility was -
        Constitutional Invariant 11 (private work stays private until
        deliberately shared) means creating a new working object must
        never itself constitute an act of sharing, even when its
        predecessor had already been shared/collaborative. The archived
        Case's own `visibility` field is never touched by this method.

        Authority: the same owner-or-admin pattern as archive_case - the
        archived Case's own creator, or an actor whose actor_role is the
        system's existing "admin" role. No new role architecture.
        """
        archived_case = self._find(workspace.cases, archived_case_id)
        if archived_case is None:
            raise CaseWorkspaceError(f"Case {archived_case_id} was not found.")

        if archived_case.get("status") != CASE_STATUS_ARCHIVED:
            raise CaseWorkspaceError(
                f"Case {archived_case_id} is not archived - derivation in this "
                "tranche is only defined as a path forward from an archived "
                "Case, not a general Copy/Adopt of an active one."
            )

        is_owner = archived_case.get("created_by") is not None and actor == archived_case["created_by"]
        is_admin_override = actor_role == "admin"
        if not (is_owner or is_admin_override):
            raise CaseWorkspaceError(
                "Only the archived Case's own creator, or an actor with the "
                "admin role, may derive a new active Case from it."
            )

        new_case = CaseRecord(
            id=_new_id(),
            project_id=archived_case["project_id"],
            title=title if title is not None else archived_case["title"],
            objective=objective if objective is not None else archived_case["objective"],
            created_at=_now(),
            created_by=actor,
            visibility=CASE_VISIBILITY_PRIVATE,
            derived_from_case_id=archived_case_id,
            source_ids=list(archived_case["source_ids"]),
        )
        relationship = Relationship(
            id=_new_id(),
            project_id=workspace.project_id,
            from_type=OBJECT_KIND_CASE,
            from_id=new_case.id,
            to_type=OBJECT_KIND_CASE,
            to_id=archived_case_id,
            relationship_type=RELATIONSHIP_TYPE_DERIVED_FROM,
            created_at=new_case.created_at,
            created_by=actor,
            provisional=False,  # a structural fact this method itself establishes, not a machine claim awaiting confirmation
        )

        workspace.cases.append(asdict(new_case))
        workspace.relationships.append(asdict(relationship))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_derived_from_archive",
                actor=actor, role="human",
                payload={
                    "derived_case_id": new_case.id,
                    "archived_case_id": archived_case_id,
                    "archived_case_creator": archived_case.get("created_by"),
                    "relationship_id": relationship.id,
                },
                correlation_id=new_case.id,
            )

        return asdict(new_case)

    def _validate_carry_forward_authority(
        self,
        workspace: ProjectWorkspace,
        source_case_id: str,
        target_case_id: str,
        actor: str,
        actor_role: Optional[str],
    ) -> tuple[dict, dict]:
        """
        Shared validation for every adopt_*_into_case method: the source
        Case must be archived (carry-forward, like Derive, is only
        defined from an archived predecessor - not a general Copy/Adopt
        of arbitrary active material), the target Case must actually be
        that source's own recorded derivation (`derived_from_case_id` -
        prevents carrying material into an unrelated Case merely because
        the actor happens to have write access to it), and authority is
        the same owner-or-admin pattern used throughout this tranche
        sequence, checked against the TARGET Case - "unauthorized
        participants must not carry historical material into another
        person's private derived Case" is a statement about who controls
        the destination, not the source.
        """
        source_case = self._find(workspace.cases, source_case_id)
        if source_case is None or source_case.get("status") != CASE_STATUS_ARCHIVED:
            raise CaseWorkspaceError(
                f"Case {source_case_id} is not archived - carry-forward in this "
                "tranche is only defined from an archived predecessor into its "
                "own derived active Case."
            )

        target_case = self._find(workspace.cases, target_case_id)
        if target_case is None:
            raise CaseWorkspaceError(f"Case {target_case_id} was not found.")
        if target_case.get("derived_from_case_id") != source_case_id:
            raise CaseWorkspaceError(
                f"Case {target_case_id} was not derived from Case {source_case_id} - "
                "carry-forward is only defined from an archived Case into its own "
                "derived active successor, not an arbitrary destination."
            )

        is_owner = target_case.get("created_by") is not None and actor == target_case["created_by"]
        is_admin_override = actor_role == "admin"
        if not (is_owner or is_admin_override):
            raise CaseWorkspaceError(
                "Only the target Case's own creator, or an actor with the "
                "admin role, may carry historical material into it."
            )

        self._require_case_not_archived(workspace, target_case_id)
        return source_case, target_case

    def carried_forward_adoptions_for_case(self, workspace: ProjectWorkspace, target_case_id: str) -> list[dict]:
        """Answers "which active items in this Case were carried forward,
        from which historical item, by whom, and when" in one filter -
        see CarriedForwardAdoption's own docstring for why this is a
        dedicated record rather than a Relationship query."""
        return [a for a in workspace.carried_forward_adoptions if a["target_case_id"] == target_case_id]

    def adopt_finding_into_case(
        self,
        workspace: ProjectWorkspace,
        source_finding_id: str,
        target_case_id: str,
        actor: str,
        actor_role: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Selective, human-authorized carry-forward of one historical
        Finding from its archived Case into that Case's own derived
        active successor. The original Finding is never touched, never
        moved, never re-cased - it remains exactly where it was
        recorded, in the archived Case, forever.

        A NEW Finding is created in the target Case, because continued
        review (ReviewerValidation/Disposition/Apply) requires a real,
        mutable Finding to attach to - not a read-only reference. Per
        this tranche's explicit architectural requirement: the adopted
        Finding re-enters as FINDING_STATUS_PROVISIONAL (Finding's own
        ordinary default - never anything stronger), honestly stating
        that a conclusion reached against the archived Case's old
        evidence context has NOT been re-validated against the target
        Case's current state merely by being carried forward. Renewed
        ReviewerValidation/Disposition against the new Finding is
        required exactly as it would be for any other Finding - nothing
        about carry-forward skips or shortcuts that.

        Finding has no generic related-object pointer of its own (unlike
        ReviewMessage), so provenance back to the original is carried on
        the accompanying AnalysisRun's AnalysisTrigger instead
        (trigger_reference_type/trigger_reference_id - already-existing
        fields, reused rather than adding a new one to Finding) - this
        mirrors promote_requirement_item's own precedent of creating an
        honest accompanying AnalysisRun rather than fabricating Finding
        provenance. The authoritative, uniformly-queryable lineage
        record is the new CarriedForwardAdoption row either way.
        """
        source_finding = self._find(workspace.findings, source_finding_id)
        if source_finding is None:
            raise CaseWorkspaceError(f"Finding {source_finding_id} was not found.")
        source_case_id = source_finding.get("case_id")
        if not source_case_id:
            raise CaseWorkspaceError(
                f"Finding {source_finding_id} has no recorded Case - carry-forward "
                "requires a known archived source Case to establish lineage from."
            )

        self._validate_carry_forward_authority(workspace, source_case_id, target_case_id, actor, actor_role)
        target_case = self._find(workspace.cases, target_case_id)

        adopted_at = _now()
        analysis_id = _new_id()
        finding_id = _new_id()

        trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
            triggered_by_actor=actor,
            trigger_reference_type=OBJECT_KIND_FINDING,
            trigger_reference_id=source_finding_id,
        )
        analysis = AnalysisRun(
            id=analysis_id,
            project_id=workspace.project_id,
            case_id=target_case_id,
            source_ids=[],
            objective=(
                f"Carry-forward review of Finding {source_finding_id} from "
                f"archived Case {source_case_id}."
            ),
            engine_name="carry_forward_adoption",
            engine_version="1.0",
            started_at=adopted_at,
            completed_at=adopted_at,
            trigger=asdict(trigger),
            finding_ids=[finding_id],
        )
        new_finding = Finding(
            id=finding_id,
            project_id=workspace.project_id,
            case_id=target_case_id,
            analysis_id=analysis_id,
            statement=source_finding["statement"],
            machine_confidence=source_finding["machine_confidence"],
            created_at=adopted_at,
            claim_status=FINDING_STATUS_PROVISIONAL,
        )
        adoption = CarriedForwardAdoption(
            id=_new_id(),
            project_id=workspace.project_id,
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            object_type=CARRIED_FORWARD_OBJECT_TYPE_FINDING,
            source_object_id=source_finding_id,
            successor_object_id=finding_id,
            adopted_by=actor,
            adopted_at=adopted_at,
        )

        workspace.analyses.append(asdict(analysis))
        workspace.findings.append(asdict(new_finding))
        target_case["analysis_ids"].append(analysis_id)
        target_case["finding_ids"].append(finding_id)
        workspace.carried_forward_adoptions.append(asdict(adoption))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="finding_carried_forward",
                actor=actor, role="human",
                payload={
                    "source_case_id": source_case_id, "target_case_id": target_case_id,
                    "source_finding_id": source_finding_id, "successor_finding_id": finding_id,
                    "adoption_id": adoption.id,
                },
                correlation_id=finding_id,
            )

        return asdict(new_finding)

    def adopt_review_message_into_case(
        self,
        workspace: ProjectWorkspace,
        source_message_id: str,
        target_case_id: str,
        actor: str,
        actor_role: Optional[str] = None,
        note: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Selective, human-authorized carry-forward of one historical
        review comment from its archived Case into that Case's own
        derived active successor. The original ReviewMessage (and its
        thread) is never touched - it remains exactly where it was
        authored, in the archived Case, unresolved or not, forever.

        A NEW ReviewThread + ReviewMessage is created, anchored to the
        target Case, so the reconsideration can actually be discussed/
        resolved in the target Case's own live context. Critically, the
        new message's `actor` is the ADOPTING actor, never the original
        commenter - "the original commenter must not falsely become the
        author of the new active item" (this tranche's own requirement,
        and the reason an unavailable/former contributor is never a
        blocker: they need not do or approve anything for their prior
        concern to be reconsidered). The original voice is preserved
        without being misattributed: `text` quotes the original message
        verbatim, clearly framed as a carried-forward quotation, and
        `related_object_type`/`related_object_id` (ReviewMessage's own
        existing generic pointer fields) point directly at the original
        message - no new field needed. The authoritative,
        uniformly-queryable lineage record is the new
        CarriedForwardAdoption row.
        """
        source_message = self._find(workspace.review_messages, source_message_id)
        if source_message is None:
            raise CaseWorkspaceError(f"Review message {source_message_id} was not found.")
        source_thread = self._find(workspace.review_threads, source_message["thread_id"])
        source_case_id = source_thread.get("case_id") if source_thread else None
        if not source_case_id:
            raise CaseWorkspaceError(
                f"Review message {source_message_id}'s thread has no recorded Case - "
                "carry-forward requires a known archived source Case to establish lineage from."
            )

        self._validate_carry_forward_authority(workspace, source_case_id, target_case_id, actor, actor_role)

        adopted_at = _now()
        anchor = Anchor(anchor_type=OBJECT_KIND_CASE, anchor_id=target_case_id)
        thread = ReviewThread(
            id=_new_id(),
            project_id=workspace.project_id,
            title=f"Carried forward: {source_thread['title']}",
            anchor=asdict(anchor),
            created_at=adopted_at,
            created_by=actor,
            case_id=target_case_id,
        )
        carried_text = (
            f"[Carried forward from archived Case {source_case_id}, "
            f"originally raised by {source_message['actor']}]\n\n{source_message['text']}"
        )
        if note:
            carried_text += f"\n\n[Adoption note from {actor}]: {note}"
        message = ReviewMessage(
            id=_new_id(),
            thread_id=thread.id,
            project_id=workspace.project_id,
            origin=MESSAGE_ORIGIN_HUMAN,
            actor=actor,
            message_type=MESSAGE_TYPE_CARRIED_FORWARD,
            text=carried_text,
            created_at=adopted_at,
            related_object_type=OBJECT_KIND_REVIEW_MESSAGE,
            related_object_id=source_message_id,
        )
        adoption = CarriedForwardAdoption(
            id=_new_id(),
            project_id=workspace.project_id,
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            object_type=CARRIED_FORWARD_OBJECT_TYPE_REVIEW_MESSAGE,
            source_object_id=source_message_id,
            successor_object_id=message.id,
            adopted_by=actor,
            adopted_at=adopted_at,
        )

        workspace.review_threads.append(asdict(thread))
        workspace.review_messages.append(asdict(message))
        workspace.carried_forward_adoptions.append(asdict(adoption))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="review_message_carried_forward",
                actor=actor, role="human",
                payload={
                    "source_case_id": source_case_id, "target_case_id": target_case_id,
                    "source_message_id": source_message_id, "successor_message_id": message.id,
                    "successor_thread_id": thread.id, "adoption_id": adoption.id,
                },
                correlation_id=message.id,
            )

        return asdict(message)

    def attach_source_to_case(self, workspace: ProjectWorkspace, case_id: str, source_id: str) -> None:
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        self._require_case_not_archived(workspace, case_id)
        if source_id not in case["source_ids"]:
            case["source_ids"].append(source_id)
        self.save(workspace)

    def add_message(
        self, workspace: ProjectWorkspace, case_id: Optional[str], role: str, text: str,
        action_taken: Optional[str] = None, anchor: Optional[dict] = None,
        actor: Optional[str] = None, grounded_in: Optional[list[str]] = None,
        next_steps: Optional[list[dict]] = None, selected_source_id: Optional[str] = None,
        organize_source_id: Optional[str] = None, operational_actions: Optional[list[dict]] = None,
        river_actions: Optional[list[dict]] = None, content_class: Optional[str] = None,
        candidate_referents: Optional[list[dict]] = None,
    ) -> dict:
        """
        case_id=None posts into ProjectWorkspace.project_conversation
        instead of a Case's own conversation list - the project-level
        home for a message sent with no Investigation open (see
        ConversationMessage's own docstring for why this is a second
        list, not a migration of the existing one).

        CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 1): content_class, when
        given, must be one of KNOWN_CONTENT_CLASSES - same closed-
        vocabulary validation _add_work_product_section already applies
        to its own content_class parameter, reused here rather than a
        second, Conversation-specific check.
        """
        if content_class is not None and content_class not in KNOWN_CONTENT_CLASSES:
            raise CaseWorkspaceError(
                f"'{content_class}' is not a recognized content class. Use one of: {', '.join(KNOWN_CONTENT_CLASSES)}."
            )
        if case_id is None:
            message = ConversationMessage(
                id=_new_id(), role=role, text=text, created_at=_now(),
                actor=actor, action_taken=action_taken, anchor=anchor,
                grounded_in=grounded_in or [], next_steps=next_steps or [],
                selected_source_id=selected_source_id, organize_source_id=organize_source_id,
                operational_actions=operational_actions or [], river_actions=river_actions or [],
                content_class=content_class, candidate_referents=candidate_referents or [],
            )
            workspace.project_conversation.append(asdict(message))
            self.save(workspace)
            return asdict(message)

        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")
        self._require_case_not_archived(workspace, case_id)
        message = ConversationMessage(
            id=_new_id(),
            case_id=case_id,
            role=role,
            text=text,
            created_at=_now(),
            actor=actor,
            action_taken=action_taken,
            anchor=anchor,
            grounded_in=grounded_in or [],
            next_steps=next_steps or [],
            selected_source_id=selected_source_id, organize_source_id=organize_source_id,
            operational_actions=operational_actions or [], river_actions=river_actions or [],
            content_class=content_class, candidate_referents=candidate_referents or [],
        )
        case["conversation"].append(asdict(message))
        self.save(workspace)
        return asdict(message)

    def project_conversation_for(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.project_conversation)

    # ---------------------------------------------------------------
    # CLAUDE-P40-VW7: project-scoped conversation Tags/Highlights/Tasks.
    # ---------------------------------------------------------------

    @staticmethod
    def _normalize_tag_name(name: str) -> str:
        """Collapses surrounding whitespace and internal run-whitespace,
        casefolds for COMPARISON only (the stored/displayed name keeps
        its original casing) - Section 5's own explicit "avoid
        accidental duplicates caused only by capitalization or
        surrounding whitespace" requirement."""
        return re.sub(r"\s+", " ", name).strip().casefold()

    def resolve_tag(self, workspace: ProjectWorkspace, tag_id: str) -> Optional[dict]:
        """Built-in tags (BUILT_IN_TAGS) and project-scoped custom tags
        (workspace.tags) share one id-space from every caller's point of
        view - this is the one place that actually distinguishes them,
        so nothing else needs to."""
        if tag_id in BUILT_IN_TAGS:
            return dict(BUILT_IN_TAGS[tag_id])
        return self._find(workspace.tags, tag_id)

    def list_custom_tags(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.tags)

    def create_custom_tag(self, workspace: ProjectWorkspace, name: str, color: str, actor: str) -> dict:
        """Idempotent by normalized name: re-submitting the same name
        (any casing/whitespace) returns the EXISTING tag rather than
        creating a duplicate - the actual mechanism behind Section 5's
        "avoid accidental duplicates" requirement, not just a display-
        time collapse. A collision with a BUILT-IN tag's name (e.g.
        typing "Important" into the custom-tag field) also returns the
        built-in tag's own id, so "Important" only ever means one thing
        in a given project regardless of which path created it."""
        stripped = re.sub(r"\s+", " ", (name or "")).strip()
        if not stripped:
            raise CaseWorkspaceError("Tag name cannot be empty.")
        if len(stripped) > 60:
            raise CaseWorkspaceError("Tag name is too long (60 characters max).")
        if color not in TAG_COLOR_PALETTE:
            raise CaseWorkspaceError(f"Unknown tag colour {color!r}.")

        normalized = self._normalize_tag_name(stripped)
        for builtin in BUILT_IN_TAGS.values():
            if self._normalize_tag_name(builtin["name"]) == normalized:
                return dict(builtin)
        for existing in workspace.tags:
            if self._normalize_tag_name(existing["name"]) == normalized:
                return existing

        tag = Tag(id=_new_id(), name=stripped, color=color, created_by=actor, created_at=_now())
        workspace.tags.append(asdict(tag))
        self.save(workspace)
        return asdict(tag)

    def add_composer_finding(
        self,
        workspace: ProjectWorkspace,
        tag: str,
        source_reference: str,
        concern: str,
        unresolved_question: str,
        created_by: Optional[str] = None,
        urgency: Optional[str] = None,
        project_stage: Optional[str] = None,
        source_message_id: Optional[str] = None,
    ) -> dict:
        """CLAUDE-GO-RIGHT-PANEL-01: the one write path that promotes a
        Composer-emitted characterization (services.project_qa's
        ProjectQAResult.findings, via
        conversation_interpreter._handle_project_question) from
        transient reply prose into a durable, project-scoped record -
        the "structured finding" half of the "conversational response +
        structured findings" result contract Section 8 of this stage's
        own governing prompt requires. Deliberately no case_id/
        analysis_id (see ComposerFinding's own docstring) and
        deliberately no Approval Gate (`_require_approval`) - this is
        the same "governed-but-provisional, no gate" posture
        record_analysis's own Findings already have; nothing here
        changes durable Requirement/RFI/Work Product state, so gating
        it would be inventing a new authority tier this stage's own
        prompt does not ask for."""
        stripped_tag = (tag or "").strip()
        if not stripped_tag:
            raise CaseWorkspaceError("A Composer Finding must have a non-empty tag/title.")
        finding = ComposerFinding(
            id=_new_id(),
            project_id=workspace.project_id,
            tag=stripped_tag,
            source_reference=(source_reference or "").strip(),
            concern=(concern or "").strip(),
            unresolved_question=(unresolved_question or "").strip(),
            created_at=_now(),
            created_by=created_by,
            urgency=(urgency or "").strip() or None,
            project_stage=(project_stage or "").strip() or None,
            source_message_id=source_message_id,
        )
        workspace.composer_findings.append(asdict(finding))
        self.save(workspace)
        return asdict(finding)

    def _validate_source_anchor(self, workspace: ProjectWorkspace, source_anchor: dict) -> dict:
        """Real validation, not just shape-checking - confirms the
        anchor's own case_id/message_id actually resolve against this
        SAME workspace before anything gets persisted, so a tampered or
        stale anchor can never be recorded as if it were real (Section
        8's own "prevent ID tampering" requirement, applied to the
        anchor payload itself, not just the surrounding project_id/
        occurrence_id path parameters route-layer checks already
        cover)."""
        scope = source_anchor.get("scope")
        if scope not in KNOWN_CONVERSATION_ANCHOR_SCOPES:
            raise CaseWorkspaceError(f"Unknown source anchor scope {scope!r}.")

        quote = (source_anchor.get("quote") or "").strip()
        if not quote:
            raise CaseWorkspaceError("Selected text cannot be empty.")
        if len(quote) > 2000:
            raise CaseWorkspaceError("Selected text is too long (2000 characters max).")

        start_offset = source_anchor.get("start_offset")
        end_offset = source_anchor.get("end_offset")
        if not isinstance(start_offset, int) or not isinstance(end_offset, int) or start_offset < 0 or end_offset <= start_offset:
            raise CaseWorkspaceError("Selection offsets are invalid.")

        if scope == CONVERSATION_ANCHOR_SCOPE_GUIDANCE:
            if source_anchor.get("guidance_key") != CONVERSATION_GUIDANCE_PROJECT_INTRO:
                raise CaseWorkspaceError("Unknown guidance source.")
            case_id = None
            message_id = None
        else:
            case_id = source_anchor.get("case_id")
            message_id = source_anchor.get("message_id")
            if not message_id:
                raise CaseWorkspaceError("A message source anchor requires a message id.")
            if scope == CONVERSATION_ANCHOR_SCOPE_CASE:
                case = self._find(workspace.cases, case_id) if case_id else None
                if case is None:
                    raise CaseWorkspaceError(f"Investigation {case_id} was not found.")
                message = self._find(case["conversation"], message_id)
            else:
                case_id = None
                message = self._find(workspace.project_conversation, message_id)
            if message is None:
                raise CaseWorkspaceError(f"Conversation message {message_id} was not found.")

        return {
            "scope": scope,
            "case_id": case_id,
            "message_id": message_id,
            "guidance_key": source_anchor.get("guidance_key") if scope == CONVERSATION_ANCHOR_SCOPE_GUIDANCE else None,
            "start_offset": start_offset,
            "end_offset": end_offset,
            "quote": quote,
            "prefix": (source_anchor.get("prefix") or "")[:80],
            "suffix": (source_anchor.get("suffix") or "")[:80],
        }

    def resolve_conversation_anchor(self, workspace: ProjectWorkspace, source_anchor: dict) -> bool:
        """Section 4's own "Source unavailable" requirement: True only
        if the anchor's target can genuinely still be resolved against
        the CURRENT state of this workspace (the Investigation and
        message still exist) - never assumed true merely because the
        record itself exists. Read-only, used by the Lists Tasks/Tags
        rendering to decide whether a "Source unavailable" state should
        show instead of a normal navigation link."""
        scope = source_anchor.get("scope")
        if scope == CONVERSATION_ANCHOR_SCOPE_GUIDANCE:
            return source_anchor.get("guidance_key") == CONVERSATION_GUIDANCE_PROJECT_INTRO
        message_id = source_anchor.get("message_id")
        if not message_id:
            return False
        if scope == CONVERSATION_ANCHOR_SCOPE_CASE:
            case = self._find(workspace.cases, source_anchor.get("case_id"))
            if case is None:
                return False
            return self._find(case["conversation"], message_id) is not None
        if scope == CONVERSATION_ANCHOR_SCOPE_PROJECT:
            return self._find(workspace.project_conversation, message_id) is not None
        return False

    def add_tag_occurrence(
        self, workspace: ProjectWorkspace, tag_id: str, source_anchor: dict, actor: str,
    ) -> dict:
        if self.resolve_tag(workspace, tag_id) is None:
            raise CaseWorkspaceError(f"Tag {tag_id} was not found.")
        validated_anchor = self._validate_source_anchor(workspace, source_anchor)

        occurrence = TagOccurrence(
            id=_new_id(), tag_id=tag_id, source_anchor=validated_anchor,
            quote=validated_anchor["quote"], created_by=actor, created_at=_now(),
        )
        workspace.tag_occurrences.append(asdict(occurrence))
        self.save(workspace)
        return asdict(occurrence)

    def remove_tag_occurrence(self, workspace: ProjectWorkspace, occurrence_id: str) -> None:
        """Removes only this occurrence record - never touches the
        source conversation message/text it pointed to (Section 5's own
        explicit requirement)."""
        occurrence = self._find(workspace.tag_occurrences, occurrence_id)
        if occurrence is None:
            raise CaseWorkspaceError(f"Tag occurrence {occurrence_id} was not found.")
        workspace.tag_occurrences.remove(occurrence)
        self.save(workspace)

    def tag_occurrences_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.tag_occurrences)

    def tag_occurrences_for_message(
        self, workspace: ProjectWorkspace, scope: str, message_id: str, case_id: Optional[str] = None,
    ) -> list[dict]:
        """CLAUDE-P40-VW8-QA, Section 11: occurrences anchored to this
        EXACT message - the read side of "the selected text must
        receive an identifiable, accessible tagged treatment", rendered
        inline by app.py's own `hotlinks` filter. Reuses the SAME
        TagOccurrence.source_anchor already stored for Lists/navigation
        - no second annotation mechanism, no new business object.
        Sorted by start_offset so the caller can render left-to-right
        and deterministically resolve overlaps (first-starting wins;
        see that filter's own comment)."""
        matches = [
            occ for occ in workspace.tag_occurrences
            if occ["source_anchor"].get("scope") == scope
            and occ["source_anchor"].get("message_id") == message_id
            and (scope != CONVERSATION_ANCHOR_SCOPE_CASE or occ["source_anchor"].get("case_id") == case_id)
        ]
        matches.sort(key=lambda occ: occ["source_anchor"]["start_offset"])
        return matches

    def create_task(self, workspace: ProjectWorkspace, source_anchor: dict, title: str, actor: str) -> dict:
        stripped_title = re.sub(r"\s+", " ", (title or "")).strip()
        if not stripped_title:
            raise CaseWorkspaceError("Task title cannot be empty.")
        if len(stripped_title) > 200:
            stripped_title = stripped_title[:197] + "..."

        validated_anchor = self._validate_source_anchor(workspace, source_anchor)

        task = Task(
            id=_new_id(), source_anchor=validated_anchor, quote=validated_anchor["quote"],
            title=stripped_title, status=TASK_STATUS_OPEN, created_by=actor, created_at=_now(),
        )
        workspace.tasks.append(asdict(task))
        self.save(workspace)
        return asdict(task)

    def complete_task(self, workspace: ProjectWorkspace, task_id: str, actor: str) -> dict:
        task = self._find(workspace.tasks, task_id)
        if task is None:
            raise CaseWorkspaceError(f"Task {task_id} was not found.")
        if task["status"] == TASK_STATUS_COMPLETED:
            raise CaseWorkspaceError("Task is already completed.")
        task["status"] = TASK_STATUS_COMPLETED
        task["completed_by"] = actor
        task["completed_at"] = _now()
        self.save(workspace)
        return task

    def reopen_task(self, workspace: ProjectWorkspace, task_id: str, actor: str) -> dict:
        task = self._find(workspace.tasks, task_id)
        if task is None:
            raise CaseWorkspaceError(f"Task {task_id} was not found.")
        if task["status"] == TASK_STATUS_OPEN:
            raise CaseWorkspaceError("Task is already open.")
        task["status"] = TASK_STATUS_OPEN
        task["reopened_by"] = actor
        task["reopened_at"] = _now()
        self.save(workspace)
        return task

    def tasks_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.tasks)

    def recent_anchors_for(
        self, workspace: ProjectWorkspace, reviewer: str, case_ids: set, limit: int = 5,
    ) -> list[dict]:
        """
        This reviewer's own anchored human messages - the durable,
        derived basis for a "where did I leave off" trail (the
        contextual-companion continuity discussed against the Windshield/
        Rear-view/Carousel model). Deliberately NOT a new persisted
        "memory" object: every entry here is read straight from
        ConversationMessage records that already exist for other
        reasons, so this can never drift from what actually happened or
        become an opaque second source of truth. Newest first, deduped
        by anchor_id (only the most recent mention of a given object
        survives - "here's where you last talked about X", not a full
        log), capped at `limit` so this stays a quick trail, not another
        unbounded history viewer.

        `case_ids` should be the caller's already-computed
        visible_case_ids - a Private Case's messages must be exactly as
        invisible here as its Findings already are everywhere else.
        """
        candidates = [
            m for m in workspace.project_conversation
            if m["role"] == "human" and m.get("actor") == reviewer and m.get("anchor")
        ]
        for case in workspace.cases:
            if case["id"] not in case_ids:
                continue
            candidates.extend(
                m for m in case["conversation"]
                if m["role"] == "human" and m.get("actor") == reviewer and m.get("anchor")
            )

        candidates.sort(key=lambda m: m["created_at"], reverse=True)

        seen_anchor_ids = set()
        result = []
        for message in candidates:
            anchor_id = message["anchor"]["anchor_id"]
            if anchor_id in seen_anchor_ids:
                continue
            seen_anchor_ids.add(anchor_id)
            result.append(message)
            if len(result) >= limit:
                break
        return result

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
        governance_log: Optional[GovernanceLog] = None,
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
            self._require_case_not_archived(workspace, case_id)
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

        # Collaboration threshold: only a genuinely human-initiated Analysis
        # can qualify - ANALYSIS_TRIGGER_USER_INITIATED specifically, never
        # AGENT_INITIATED/CLOCK_INITIATED/SYSTEM_RECHECK/etc, regardless of
        # what string triggered_by_actor happens to carry. This is the
        # machine-boundary distinction the ratified spec requires: a
        # machine-created record must never falsely cross the human
        # collaboration threshold merely because a non-owner name appears
        # somewhere on it.
        crossed = False
        if trigger.trigger_type == ANALYSIS_TRIGGER_USER_INITIATED:
            crossed = self._cross_collaboration_threshold_if_qualifying(
                workspace, case_id, trigger.triggered_by_actor, "analysis", analysis_id,
            )

        self.save(workspace)

        if crossed and governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_became_collaborative",
                actor=trigger.triggered_by_actor, role="human",
                payload={
                    "case_id": case_id, "contribution_type": "analysis",
                    "contribution_id": analysis_id,
                },
                correlation_id=case_id,
            )

        return asdict(analysis)

    # -- investigation worklist (CLAUDE-P08) ----------------------------------------

    def record_investigation_step(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        step_kind: str,
        anchor: dict,
        question: str,
        triggered_by_actor: str,
        evidence_requested: Optional[list[str]] = None,
        evidence_examined_ids: Optional[dict] = None,
        ran: bool = False,
        skipped_reason: Optional[str] = None,
        assessment: Optional[str] = None,
        confidence: Optional[float] = None,
        supporting_points: Optional[list[str]] = None,
        open_questions: Optional[list[str]] = None,
        needs_human_judgment: bool = True,
        analysis_id: Optional[str] = None,
        branched_from_step_id: Optional[str] = None,
    ) -> dict:
        """Persists one InvestigationStep - always, whether the underlying
        reasoning actually ran or was honestly skipped (ran=False,
        skipped_reason set). Recording the ATTEMPT, not only successful
        runs, is what makes "how the system fails honestly" itself
        auditable rather than leaving a silent gap in the worklist."""
        step = InvestigationStep(
            id=_new_id(),
            project_id=workspace.project_id,
            case_id=case_id,
            step_kind=normalize_open_world_value(step_kind, KNOWN_INVESTIGATION_STEP_KINDS),
            anchor=anchor,
            question=question,
            triggered_by_actor=triggered_by_actor,
            created_at=_now(),
            evidence_requested=evidence_requested or [],
            evidence_examined_ids=evidence_examined_ids or {},
            ran=ran,
            skipped_reason=skipped_reason,
            assessment=assessment,
            confidence=confidence,
            supporting_points=supporting_points or [],
            open_questions=open_questions or [],
            needs_human_judgment=needs_human_judgment,
            analysis_id=analysis_id,
            branched_from_step_id=branched_from_step_id,
        )
        workspace.investigation_steps.append(asdict(step))
        self.save(workspace)
        return asdict(step)

    def investigation_steps_for_case(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [s for s in workspace.investigation_steps if s["case_id"] == case_id]

    def investigation_step_for_analysis(self, workspace: ProjectWorkspace, analysis_id: str) -> Optional[dict]:
        return next((s for s in workspace.investigation_steps if s.get("analysis_id") == analysis_id), None)

    # -- CLAUDE-MM7: Governed Investigation, Analytical Reasoning, and ---------
    # Trustworthy Answers - Claim is the one genuinely new adapter object
    # (Section 7); everything else below reuses MM1-MM6 primitives (evidence
    # contract, Relationship, Supersession, Finding/DerivedObservation).

    def record_investigation_claim(
        self,
        workspace: ProjectWorkspace,
        investigation_step_id: str,
        statement: str,
        claim_class: str,
        method: str,
        confidence_state: str,
        author_type: str,
        created_by: str,
        evidence_links: Optional[list[dict]] = None,
        evidence_excluded: Optional[list[dict]] = None,
        contradiction_relationship_ids: Optional[list[str]] = None,
        assumptions: Optional[list[str]] = None,
        recommended_next_check: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 9 ("no citation laundering"), enforced structurally, not
        merely documented: every entry in `evidence_links` must name a
        REAL, already-governed object in THIS project (validated against
        the same `_MM6_ENDPOINT_LISTS` MM6 already uses) - there is no
        code path here that accepts a citation as free text. A claim
        asserting something (any claim_class other than CLAIM_CLASS_
        UNKNOWN, the honest-abstention class) must cite at least one
        piece of real evidence; abstention is the one class permitted to
        have none.

        Section 13's own "do not claim deterministic computation when
        the result was AI-generated" is enforced here, not left to
        caller discipline: `author_type=OBSERVATION_AUTHOR_AI` may never
        be paired with `claim_class` DIRECTLY_VERIFIED or DETERMINISTIC_
        CALCULATION.
        """
        step = self._find(workspace.investigation_steps, investigation_step_id)
        if step is None or step["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Investigation step {investigation_step_id} was not found.")

        if claim_class not in KNOWN_CLAIM_CLASSES:
            raise CaseWorkspaceError(
                f"'{claim_class}' is not a recognized claim class. Use one of: {', '.join(KNOWN_CLAIM_CLASSES)}."
            )
        if confidence_state not in KNOWN_CONFIDENCE_STATES:
            raise CaseWorkspaceError(
                f"'{confidence_state}' is not a recognized confidence state. "
                f"Use one of: {', '.join(KNOWN_CONFIDENCE_STATES)}."
            )
        if author_type not in KNOWN_OBSERVATION_AUTHOR_TYPES:
            raise CaseWorkspaceError(
                f"'{author_type}' is not a recognized author type. Use one of: {', '.join(KNOWN_OBSERVATION_AUTHOR_TYPES)}."
            )
        if author_type == OBSERVATION_AUTHOR_AI and claim_class in (
            CLAIM_CLASS_DIRECTLY_VERIFIED, CLAIM_CLASS_DETERMINISTIC_CALCULATION,
        ):
            raise CaseWorkspaceError(
                "An AI-authored claim cannot be classified as directly_verified or "
                "deterministic_calculation - that would claim deterministic computation "
                "for a result that was AI-generated. Use 'ai_proposal' or 'supported_interpretation'."
            )

        evidence_links = evidence_links or []
        for link in evidence_links:
            if self._resolve_mm6_endpoint(workspace, link.get("object_type"), link.get("object_id")) is None:
                raise CaseWorkspaceError(
                    f"Claim evidence link ({link.get('object_type')} {link.get('object_id')}) "
                    "was not found in this project - a claim can only cite real, already-governed evidence."
                )
        if not evidence_links and claim_class != CLAIM_CLASS_UNKNOWN:
            raise CaseWorkspaceError(
                "A claim must cite at least one piece of evidence unless its claim_class "
                "is 'unknown' (an honest abstention)."
            )

        contradiction_relationship_ids = contradiction_relationship_ids or []
        for rel_id in contradiction_relationship_ids:
            rel = self._find(workspace.relationships, rel_id)
            if rel is None or rel["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Contradiction relationship {rel_id} was not found in this project.")

        method = normalize_open_world_value(method, KNOWN_ANALYTICAL_METHODS)

        claim = Claim(
            id=_new_id(),
            project_id=workspace.project_id,
            investigation_step_id=investigation_step_id,
            statement=statement,
            claim_class=claim_class,
            method=method,
            confidence_state=confidence_state,
            author_type=author_type,
            created_by=created_by,
            created_at=_now(),
            evidence_links=evidence_links,
            evidence_excluded=evidence_excluded or [],
            contradiction_relationship_ids=contradiction_relationship_ids,
            assumptions=assumptions or [],
            recommended_next_check=recommended_next_check,
        )
        workspace.claims.append(asdict(claim))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="investigation_claim_recorded",
                actor=created_by, role="ai" if author_type == OBSERVATION_AUTHOR_AI else "human",
                payload={
                    "claim_id": claim.id, "investigation_step_id": investigation_step_id,
                    "claim_class": claim_class, "method": method, "confidence_state": confidence_state,
                },
                correlation_id=claim.id,
            )
        return asdict(claim)

    def claims_for_investigation_step(self, workspace: ProjectWorkspace, investigation_step_id: str) -> list[dict]:
        return [c for c in workspace.claims if c["investigation_step_id"] == investigation_step_id]

    def resolve_claim_status(self, workspace: ProjectWorkspace, claim_id: str) -> dict:
        """
        Section 6/14's own read-time-derivation discipline, applied to
        Claim exactly as resolve_relationship_status already applies it
        to Relationship: status is never a field this store writes
        directly (except the underlying `adoption_state`, which is a
        real stored human/system decision, not a derived fact) - broken/
        stale/superseded are all recomputed from CURRENT state on every
        call. Precedence (most authoritative first): REJECTED > DISPUTED
        > SUPERSEDED (a corrected replacement claim already exists) >
        BROKEN (a cited endpoint no longer resolves) > the stored
        adoption_state (proposed/under_review/accepted_as_observation/
        accepted_as_finding/requires_specialist/requires_product_owner_
        or_contractual_authority) - deliberately mirroring Relationship's
        own precedence so a human rejection can never be silently masked
        by a later machine-derived state.
        """
        claim = self._find(workspace.claims, claim_id)
        if claim is None:
            return {"status": "unresolved", "claim_id": claim_id}

        evidence_status = [
            self._resolve_mm6_endpoint_status(workspace, link["object_type"], link["object_id"])
            for link in claim["evidence_links"]
        ]
        contradiction_status = [
            {"relationship_id": rel_id, "resolved": self._find(workspace.relationships, rel_id) is not None}
            for rel_id in claim.get("contradiction_relationship_ids", [])
        ]
        successor_supersession = next(
            (s for s in workspace.supersessions
             if s["predecessor_type"] == OBJECT_KIND_CLAIM and s["predecessor_id"] == claim_id),
            None,
        )

        any_broken = any(not e["resolved"] for e in evidence_status) or any(
            not c["resolved"] for c in contradiction_status
        )
        any_stale = any(e.get("stale") for e in evidence_status)

        if claim["adoption_state"] == CLAIM_ADOPTION_REJECTED:
            status = CLAIM_ADOPTION_REJECTED
        elif claim["adoption_state"] == CLAIM_ADOPTION_DISPUTED:
            status = CLAIM_ADOPTION_DISPUTED
        elif successor_supersession is not None:
            status = CLAIM_ADOPTION_SUPERSEDED
        elif any_broken:
            status = "broken"
        else:
            status = claim["adoption_state"]

        result = {
            "status": status,
            "claim_id": claim_id,
            "claim_class": claim["claim_class"],
            "confidence_state": claim["confidence_state"],
            "stale": any_stale,
            "evidence": evidence_status,
            "contradictions": contradiction_status,
        }
        if successor_supersession is not None:
            result["superseded_by_claim_id"] = successor_supersession["successor_id"]
        return result

    def accept_claim_as_observation(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 14/15: the safe, explicit convergence bridge from a
        proposed Claim to a real, governed DerivedObservation - never a
        silent auto-promotion. `supporting_evidence_ids` is filtered to
        only this claim's EvidenceItem-typed citations (record_derived_
        observation's own closed requirement); a claim citing only
        regions/other object kinds still adopts, just with an honestly
        empty supporting_evidence_ids list, exactly like any other
        DerivedObservation with no EvidenceItem citations of its own."""
        claim = self._find(workspace.claims, claim_id)
        if claim is None or claim["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Claim {claim_id} was not found.")

        evidence_ids = [
            link["object_id"] for link in claim["evidence_links"]
            if link["object_type"] == OBJECT_KIND_EVIDENCE_ITEM
        ]
        observation = self.record_derived_observation(
            workspace, statement=claim["statement"], author_type=claim["author_type"], author=actor,
            method=claim["method"], supporting_evidence_ids=evidence_ids, actor=actor,
            governance_log=governance_log,
        )

        claim["adoption_state"] = CLAIM_ADOPTION_ACCEPTED_AS_OBSERVATION
        claim["adopted_by"] = actor
        claim["adopted_at"] = _now()
        claim["adoption_reason"] = reason
        claim["derived_observation_id"] = observation["id"]
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="investigation_claim_adopted_as_observation",
                actor=actor, role="human",
                payload={"claim_id": claim_id, "derived_observation_id": observation["id"], "reason": reason},
                correlation_id=claim_id,
            )
        return {"claim": claim, "derived_observation": observation}

    def accept_claim_as_finding(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, case_id: str,
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """The other half of Section 14's convergence bridge - a Claim
        promoted into a real, Case-scoped, governed Finding via the
        SAME record_analysis every other Finding in this codebase is
        created through (never a second Finding-creation path). The
        resulting Finding is FINDING_STATUS_PROVISIONAL exactly like
        every other freshly-recorded Finding - adoption here means "this
        claim is worth a Finding," never "this Finding is already
        validated" (ReviewerValidation/Disposition remain the real gate
        for that, unchanged)."""
        claim = self._find(workspace.claims, claim_id)
        if claim is None or claim["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Claim {claim_id} was not found.")

        source_ids: list[str] = []
        for link in claim["evidence_links"]:
            if link["object_type"] == OBJECT_KIND_EVIDENCE_ITEM:
                evidence = self._find(workspace.evidence_items, link["object_id"])
                if evidence and evidence.get("source_id") and evidence["source_id"] not in source_ids:
                    source_ids.append(evidence["source_id"])
            elif link["object_type"] == OBJECT_KIND_ADDRESSABLE_REGION:
                region = self._find(workspace.addressable_regions, link["object_id"])
                unit = self._find(workspace.structural_units, region["structural_unit_id"]) if region else None
                if unit and unit.get("source_id") and unit["source_id"] not in source_ids:
                    source_ids.append(unit["source_id"])

        trigger = AnalysisTrigger(
            trigger_type=ANALYSIS_TRIGGER_AGENT_INITIATED if claim["author_type"] == OBSERVATION_AUTHOR_AI
            else ANALYSIS_TRIGGER_USER_INITIATED,
            triggered_by_actor=actor,
        )
        # Claim.confidence_state (categorical) is the authoritative
        # signal end users see; machine_confidence here exists only
        # because Finding's own pre-existing schema requires a float -
        # a coarse, honestly-labeled midpoint, never presented on its
        # own as if it carried the categorical meaning.
        confidence_midpoint = {
            CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT: 0.9,
            CONFIDENCE_STATE_PARTIAL_SUPPORT: 0.6,
            CONFIDENCE_STATE_INDIRECT_SUPPORT: 0.4,
            CONFIDENCE_STATE_CONFLICTING_SUPPORT: 0.3,
            CONFIDENCE_STATE_STALE_EVIDENCE: 0.3,
            CONFIDENCE_STATE_SPECIALIST_CONFIRMATION_REQUIRED: 0.2,
            CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE: 0.1,
        }.get(claim["confidence_state"], 0.5)

        analysis = self.record_analysis(
            workspace, source_ids=source_ids, objective=claim["statement"],
            engine_name="cross_modal_investigation", engine_version=claim["method"],
            findings=[{"statement": claim["statement"], "machine_confidence": confidence_midpoint}],
            trigger=trigger, case_id=case_id, governance_log=governance_log,
        )
        finding_id = analysis["finding_ids"][0]

        claim["adoption_state"] = CLAIM_ADOPTION_ACCEPTED_AS_FINDING
        claim["adopted_by"] = actor
        claim["adopted_at"] = _now()
        claim["adoption_reason"] = reason
        claim["finding_id"] = finding_id
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="investigation_claim_adopted_as_finding",
                actor=actor, role="human",
                payload={"claim_id": claim_id, "finding_id": finding_id, "reason": reason},
                correlation_id=claim_id,
            )
        return {"claim": claim, "analysis": analysis, "finding_id": finding_id}

    def _set_claim_adoption_state(
        self, workspace: ProjectWorkspace, claim_id: str, new_state: str, event_type: str, actor: str,
        reason: Optional[str], governance_log: Optional[GovernanceLog],
    ) -> dict:
        claim = self._find(workspace.claims, claim_id)
        if claim is None or claim["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Claim {claim_id} was not found.")
        claim["adoption_state"] = new_state
        claim["adopted_by"] = actor
        claim["adopted_at"] = _now()
        claim["adoption_reason"] = reason
        self.save(workspace)
        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type=event_type, actor=actor, role="human",
                payload={"claim_id": claim_id, "reason": reason}, correlation_id=claim_id,
            )
        return claim

    def dispute_claim(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 12: first-class disagreement, never silently smoothed
        into consensus - the claim record itself is preserved, never
        deleted, exactly like dispute_relationship."""
        return self._set_claim_adoption_state(
            workspace, claim_id, CLAIM_ADOPTION_DISPUTED, "investigation_claim_disputed", actor, reason, governance_log,
        )

    def reject_claim(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        return self._set_claim_adoption_state(
            workspace, claim_id, CLAIM_ADOPTION_REJECTED, "investigation_claim_rejected", actor, reason, governance_log,
        )

    def request_claim_specialist_review(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 15: a claim this codebase must not resolve on its
        own - e.g. a structural/geotechnical judgment call - is marked
        as requiring a specialist rather than being silently adopted or
        silently left ambiguous."""
        return self._set_claim_adoption_state(
            workspace, claim_id, CLAIM_ADOPTION_REQUIRES_SPECIALIST,
            "investigation_claim_requires_specialist", actor, reason, governance_log,
        )

    def request_claim_authority(
        self, workspace: ProjectWorkspace, claim_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 15: a claim whose adoption would itself constitute
        issuing an RFI, accepting risk, approving design, certifying
        compliance, or closing a deficiency - none of which this claim
        object may ever do on its own (Section 15's own explicit
        prohibition) - is marked as requiring product-owner or
        contractual authority rather than silently treated as an
        ordinary adoptable observation."""
        return self._set_claim_adoption_state(
            workspace, claim_id, CLAIM_ADOPTION_REQUIRES_AUTHORITY,
            "investigation_claim_requires_authority", actor, reason, governance_log,
        )

    def supersede_claim(
        self, workspace: ProjectWorkspace, old_claim_id: str, statement: str, claim_class: str, method: str,
        confidence_state: str, author_type: str, reason: str, actor: str,
        evidence_links: Optional[list[dict]] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 16 (correction integrity): the original Claim is NEVER
        mutated or deleted - a correction creates a genuinely NEW Claim
        (via record_investigation_claim, so it is validated exactly like
        any other claim) and links it back to the original via
        record_supersession (Supersession's third real consumer, after
        Source and Relationship). `downstream_requires_review` names any
        DerivedObservation/Finding the OLD claim had already produced -
        Section 16's own "flag downstream work requiring review",
        computed here at the moment of correction rather than stored as
        a separate flag that could drift.
        """
        old = self._find(workspace.claims, old_claim_id)
        if old is None or old["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Claim {old_claim_id} was not found.")

        new_claim = self.record_investigation_claim(
            workspace, investigation_step_id=old["investigation_step_id"], statement=statement,
            claim_class=claim_class, method=method, confidence_state=confidence_state, author_type=author_type,
            created_by=actor, evidence_links=evidence_links if evidence_links is not None else old["evidence_links"],
            governance_log=governance_log,
        )
        supersession = self.record_supersession(
            workspace, predecessor_type=OBJECT_KIND_CLAIM, predecessor_id=old_claim_id,
            successor_type=OBJECT_KIND_CLAIM, successor_id=new_claim["id"], actor=actor, reason=reason,
            authority_class="approval_gate:claim_correction",
        )

        downstream_requires_review = {}
        if old.get("derived_observation_id"):
            downstream_requires_review["derived_observation_id"] = old["derived_observation_id"]
        if old.get("finding_id"):
            downstream_requires_review["finding_id"] = old["finding_id"]

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="investigation_claim_superseded", actor=actor, role="human",
                payload={
                    "old_claim_id": old_claim_id, "new_claim_id": new_claim["id"], "reason": reason,
                    "downstream_requires_review": downstream_requires_review or None,
                },
                correlation_id=new_claim["id"],
            )
        return {
            "old_claim_id": old_claim_id, "new_claim": new_claim, "supersession": supersession,
            "downstream_requires_review": downstream_requires_review or None,
        }

    # -- CLAUDE-MM8: Governed Creation, Editing, Review, and Accountable -------
    # Work Products. WorkProduct is the one genuinely new domain object
    # (Section 6/9); every lifecycle method below follows the same
    # "validate real references, mutate one governed record, save, log"
    # shape every prior MM stage's own write paths already use.

    def create_work_product(
        self,
        workspace: ProjectWorkspace,
        artifact_type: str,
        title: str,
        created_by: str,
        case_id: Optional[str] = None,
        source_finding_id: Optional[str] = None,
        source_investigation_step_id: Optional[str] = None,
        sensitivity_classification: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        `case_id` is optional (Section 6, mirroring record_analysis's own
        Project-vs-Case duality) - a Project-level work product (e.g. a
        project-wide team list) is legitimate with none. When given, must
        be a real, non-archived Case. `source_finding_id`/
        `source_investigation_step_id`, when given, must each be real -
        Section 4's own "start from evidence, a Finding, investigation,
        task, or existing work product" traceability requirement,
        enforced structurally rather than merely documented.
        """
        if not title or not title.strip():
            raise CaseWorkspaceError("A work product requires a title.")
        if case_id is not None:
            case = self._find(workspace.cases, case_id)
            if case is None:
                raise CaseWorkspaceError(f"Case {case_id} was not found.")
            self._require_case_not_archived(workspace, case_id)
        if source_finding_id is not None and self._find(workspace.findings, source_finding_id) is None:
            raise CaseWorkspaceError(f"Finding {source_finding_id} was not found.")
        if source_investigation_step_id is not None and self._find(
            workspace.investigation_steps, source_investigation_step_id,
        ) is None:
            raise CaseWorkspaceError(f"Investigation step {source_investigation_step_id} was not found.")

        now = _now()
        work_product = WorkProduct(
            id=_new_id(), project_id=workspace.project_id, artifact_type=artifact_type, title=title.strip(),
            created_by=created_by, created_at=now, modified_at=now, case_id=case_id,
            source_finding_id=source_finding_id, source_investigation_step_id=source_investigation_step_id,
            sensitivity_classification=sensitivity_classification,
        )
        workspace.work_products.append(asdict(work_product))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_created", actor=created_by, role="human",
                payload={"work_product_id": work_product.id, "artifact_type": artifact_type, "title": title},
                correlation_id=work_product.id,
            )
        return asdict(work_product)

    def work_products_for_project(self, workspace: ProjectWorkspace, case_id: Optional[str] = None) -> list[dict]:
        if case_id is not None:
            return [w for w in workspace.work_products if w.get("case_id") == case_id]
        return list(workspace.work_products)

    def get_work_product(self, workspace: ProjectWorkspace, work_product_id: str) -> Optional[dict]:
        return self._find(workspace.work_products, work_product_id)

    def _require_work_product_editable(self, work_product: dict) -> None:
        """Section 18/7's own immutability guarantee: an ISSUED work
        product can never be silently mutated - the only path forward for
        an issued artifact is revise_work_product, which creates a NEW
        draft rather than reopening the old one."""
        if work_product["state"] == WORK_PRODUCT_STATE_ISSUED:
            raise CaseWorkspaceError(
                "This work product has already been issued and cannot be edited - "
                "use revise_work_product to create an editable successor revision."
            )

    def add_work_product_section(
        self,
        workspace: ProjectWorkspace,
        work_product_id: str,
        section_type: str,
        content: dict,
        content_class: str,
        author: str,
        evidence_links: Optional[list[dict]] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 9/23: `evidence_links` validated exactly like Claim's
        own (real, already-governed objects only) - the same structural
        no-citation-laundering guarantee MM7 established, reused unchanged
        here rather than re-implemented."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)
        if content_class not in KNOWN_CONTENT_CLASSES:
            raise CaseWorkspaceError(
                f"'{content_class}' is not a recognized content class. Use one of: {', '.join(KNOWN_CONTENT_CLASSES)}."
            )
        evidence_links = evidence_links or []
        for link in evidence_links:
            if self._resolve_mm6_endpoint(workspace, link.get("object_type"), link.get("object_id")) is None:
                raise CaseWorkspaceError(
                    f"Section evidence link ({link.get('object_type')} {link.get('object_id')}) "
                    "was not found in this project."
                )

        now = _now()
        order_index = sum(1 for s in work_product["sections"] if not s["removed"])
        section = WorkProductSection(
            id=_new_id(), section_type=section_type, content=content, content_class=content_class,
            author=author, created_at=now, order_index=order_index, evidence_links=evidence_links,
        )
        work_product["sections"].append(asdict(section))
        work_product["modified_at"] = now
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_section_added", actor=author, role="human",
                payload={"work_product_id": work_product_id, "section_id": section.id, "section_type": section_type,
                         "content_class": content_class},
                correlation_id=work_product_id,
            )
        return work_product

    def edit_work_product_section(
        self,
        workspace: ProjectWorkspace,
        work_product_id: str,
        section_id: str,
        content: dict,
        actor: str,
        reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 16's own "record before/after values for structured
        edits" - `edit_history` gains one entry per call, never trimmed.
        Section 8's own "AI content must not become human-approved simply
        because a user opens the document": if this section's CURRENT
        content_class is `ai_proposed`, editing it transitions the class
        to `edited_ai_proposal` automatically - never silently to
        `human_authored`, and never left claiming to be an unedited AI
        proposal once it has genuinely been changed.
        """
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)

        section = next((s for s in work_product["sections"] if s["id"] == section_id and not s["removed"]), None)
        if section is None:
            raise CaseWorkspaceError(f"Section {section_id} was not found on this work product.")

        now = _now()
        section["edit_history"].append({
            "before": section["content"], "after": content, "actor": actor, "at": now, "reason": reason,
        })
        section["content"] = content
        section["modified_at"] = now
        if section["content_class"] == CONTENT_CLASS_AI_PROPOSED:
            section["content_class"] = CONTENT_CLASS_EDITED_AI_PROPOSAL
        work_product["modified_at"] = now
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_section_edited", actor=actor, role="human",
                payload={"work_product_id": work_product_id, "section_id": section_id, "reason": reason},
                correlation_id=work_product_id,
            )
        return work_product

    def accept_work_product_section(
        self, workspace: ProjectWorkspace, work_product_id: str, section_id: str, actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 8's "accepted text becomes part of the work product" -
        a human sign-off recorded WITHOUT rewriting the section's own
        `content_class` (see WorkProductSection's own docstring on why
        acceptance and authorship are deliberately two different facts)."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)

        section = next((s for s in work_product["sections"] if s["id"] == section_id and not s["removed"]), None)
        if section is None:
            raise CaseWorkspaceError(f"Section {section_id} was not found on this work product.")

        section["accepted_by"] = actor
        section["accepted_at"] = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_section_accepted", actor=actor, role="human",
                payload={"work_product_id": work_product_id, "section_id": section_id},
                correlation_id=work_product_id,
            )
        return work_product

    def remove_work_product_section(
        self, workspace: ProjectWorkspace, work_product_id: str, section_id: str, actor: str,
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Soft-delete only (Section 16: "do not hard-delete consequential
        records without existing governance") - a removed section is
        excluded from rendering/export/reorder but never actually deleted
        from `sections`, so its own edit_history stays inspectable."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)

        section = next((s for s in work_product["sections"] if s["id"] == section_id and not s["removed"]), None)
        if section is None:
            raise CaseWorkspaceError(f"Section {section_id} was not found on this work product.")

        section["removed"] = True
        section["removed_by"] = actor
        section["removed_at"] = _now()
        work_product["modified_at"] = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_section_removed", actor=actor, role="human",
                payload={"work_product_id": work_product_id, "section_id": section_id, "reason": reason},
                correlation_id=work_product_id,
            )
        return work_product

    def reorder_work_product_sections(
        self, workspace: ProjectWorkspace, work_product_id: str, section_id_order: list[str], actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)

        active_ids = {s["id"] for s in work_product["sections"] if not s["removed"]}
        if set(section_id_order) != active_ids:
            raise CaseWorkspaceError("The given section order must name exactly the work product's own active sections.")

        order_by_id = {sid: idx for idx, sid in enumerate(section_id_order)}
        for section in work_product["sections"]:
            if not section["removed"]:
                section["order_index"] = order_by_id[section["id"]]
        work_product["modified_at"] = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_sections_reordered", actor=actor, role="human",
                payload={"work_product_id": work_product_id}, correlation_id=work_product_id,
            )
        return work_product

    def record_work_product_review(
        self, workspace: ProjectWorkspace, work_product_id: str, reviewer: str, role: str, decision: str,
        comments: Optional[str] = None, conditions: Optional[str] = None, unresolved_contradiction: bool = False,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 17: reviewer/date/role/comments/conditions/unresolved-
        contradiction, append-only (a later review never overwrites an
        earlier one - see ReviewerValidation's own precedent). `decision`
        is a closed choice between the two review outcomes Section 17
        actually distinguishes: reviewed (ready to move toward issue) or
        revisions_required (sent back)."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)
        if decision not in (WORK_PRODUCT_STATE_REVIEWED, WORK_PRODUCT_STATE_REVISIONS_REQUIRED):
            raise CaseWorkspaceError(
                f"'{decision}' is not a valid review decision. Use '{WORK_PRODUCT_STATE_REVIEWED}' or "
                f"'{WORK_PRODUCT_STATE_REVISIONS_REQUIRED}'."
            )

        review = WorkProductReview(
            reviewer=reviewer, role=role, decision=decision, reviewed_at=_now(), comments=comments,
            conditions=conditions, unresolved_contradiction=unresolved_contradiction,
        )
        work_product["reviews"].append(asdict(review))
        work_product["state"] = decision
        work_product["modified_at"] = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_reviewed", actor=reviewer, role="human",
                payload={"work_product_id": work_product_id, "decision": decision,
                         "unresolved_contradiction": unresolved_contradiction},
                correlation_id=work_product_id,
            )
        return work_product

    def approve_work_product_for_issue(
        self, workspace: ProjectWorkspace, work_product_id: str, actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 17: reuses existing project role/action-evaluation
        mechanisms rather than inventing new approval authority - THIS
        method only enforces the state machine (must already be
        `reviewed`); who is allowed to call it at all is the route
        layer's own responsibility, matching every other consequential
        action in this codebase (Approval Gate / admin role), not a
        second authority system defined here."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        self._require_work_product_editable(work_product)
        if work_product["state"] != WORK_PRODUCT_STATE_REVIEWED:
            raise CaseWorkspaceError(
                "A work product must be reviewed (state='reviewed') before it can be approved for issue."
            )

        work_product["state"] = WORK_PRODUCT_STATE_APPROVED_FOR_ISSUE
        work_product["modified_at"] = _now()
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_approved_for_issue", actor=actor,
                role="human", payload={"work_product_id": work_product_id}, correlation_id=work_product_id,
            )
        return work_product

    @staticmethod
    def _work_product_content_checksum(work_product: dict) -> str:
        """Section 6/18: a checksum of the GOVERNED content (active
        sections only, in stable id order) - deliberately independent of
        any one export format's own byte-for-byte rendering (that is
        WorkProductExportRecord.checksum's own, separate job)."""
        active_sections = sorted(
            (s for s in work_product["sections"] if not s["removed"]), key=lambda s: s["id"],
        )
        canonical = json.dumps(
            [{"id": s["id"], "section_type": s["section_type"], "content": s["content"]} for s in active_sections],
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def issue_work_product(
        self, workspace: ProjectWorkspace, work_product_id: str, actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 7/18's own point of no return: requires `approved_for_
        issue` first (the full review -> approve -> issue chain Section
        17 lists), computes and permanently stores `issued_checksum`, and
        locks the work product - every subsequent add/edit/remove/reorder
        call on THIS record raises (see _require_work_product_editable).
        The only way forward from here is `revise_work_product`, which
        creates a NEW record; this one is never reopened.
        """
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        if work_product["state"] != WORK_PRODUCT_STATE_APPROVED_FOR_ISSUE:
            raise CaseWorkspaceError(
                "A work product must be approved for issue (state='approved_for_issue') before it can be issued."
            )

        now = _now()
        work_product["state"] = WORK_PRODUCT_STATE_ISSUED
        work_product["issued_at"] = now
        work_product["issued_by"] = actor
        work_product["issued_checksum"] = self._work_product_content_checksum(work_product)
        work_product["modified_at"] = now
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_issued", actor=actor, role="human",
                payload={"work_product_id": work_product_id, "version": work_product["version"],
                         "issued_checksum": work_product["issued_checksum"]},
                correlation_id=work_product_id,
            )
        return work_product

    def revise_work_product(
        self, workspace: ProjectWorkspace, work_product_id: str, actor: str, reason: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 18: "Creating Revision B must not rewrite Revision A" -
        the original ISSUED work product is never mutated or deleted; a
        genuinely NEW WorkProduct is created (a deep copy of the issued
        sections, `state=draft`, `version=original.version + 1`) and
        linked back via Supersession (WorkProduct's own fourth real
        consumer, after Source/Relationship/Claim). The new draft's own
        sections are copies with fresh ids (so editing the revision can
        never mutate the original's own section records by shared
        reference) but preserve their own original content_class/
        evidence_links/edit_history verbatim - a revision starts from
        exactly what was issued, not blank.
        """
        original = self._find(workspace.work_products, work_product_id)
        if original is None or original["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")
        if original["state"] != WORK_PRODUCT_STATE_ISSUED:
            raise CaseWorkspaceError("Only an issued work product can be revised.")

        now = _now()
        copied_sections = []
        for s in original["sections"]:
            copied = dict(s)
            copied["id"] = _new_id()
            copied_sections.append(copied)

        new_work_product = WorkProduct(
            id=_new_id(), project_id=workspace.project_id, artifact_type=original["artifact_type"],
            title=original["title"], created_by=actor, created_at=now, modified_at=now,
            case_id=original.get("case_id"), source_finding_id=original.get("source_finding_id"),
            source_investigation_step_id=original.get("source_investigation_step_id"),
            sensitivity_classification=original.get("sensitivity_classification"),
            state=WORK_PRODUCT_STATE_DRAFT, version=original["version"] + 1,
        )
        new_dict = asdict(new_work_product)
        new_dict["sections"] = copied_sections
        workspace.work_products.append(new_dict)

        supersession = self.record_supersession(
            workspace, predecessor_type=OBJECT_KIND_WORK_PRODUCT, predecessor_id=work_product_id,
            successor_type=OBJECT_KIND_WORK_PRODUCT, successor_id=new_work_product.id, actor=actor,
            reason=reason, authority_class="approval_gate:work_product_revision",
        )
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_revised", actor=actor, role="human",
                payload={"original_work_product_id": work_product_id, "new_work_product_id": new_work_product.id,
                         "reason": reason},
                correlation_id=new_work_product.id,
            )
        return {"original_work_product_id": work_product_id, "new_work_product": new_dict, "supersession": supersession}

    def resolve_work_product_status(self, workspace: ProjectWorkspace, work_product_id: str) -> dict:
        """Read-time-derived status, mirroring resolve_claim_status/
        resolve_relationship_status exactly - `superseded` is never a
        stored value, always recomputed from a real Supersession record
        naming this work product as predecessor."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None:
            return {"status": "unresolved", "work_product_id": work_product_id}

        successor_supersession = next(
            (s for s in workspace.supersessions
             if s["predecessor_type"] == OBJECT_KIND_WORK_PRODUCT and s["predecessor_id"] == work_product_id),
            None,
        )
        status = WORK_PRODUCT_STATE_SUPERSEDED if successor_supersession is not None else work_product["state"]
        result = {
            "status": status, "work_product_id": work_product_id, "artifact_type": work_product["artifact_type"],
            "version": work_product["version"], "issued_checksum": work_product.get("issued_checksum"),
        }
        if successor_supersession is not None:
            result["superseded_by_work_product_id"] = successor_supersession["successor_id"]
        return result

    def stale_evidence_for_work_product(self, workspace: ProjectWorkspace, work_product_id: str) -> dict:
        """
        Section 23: "If source evidence later becomes stale, the work
        product should be able to warn... without silently rewriting the
        issued artifact" - a pure, read-time check over every active
        section's own evidence_links, reusing the SAME staleness
        derivation `resolve_claim_status`/`resolve_relationship_status`
        already use. Never mutates the work product, issued or not.
        """
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            return {"status": "unavailable", "work_product_id": work_product_id}

        stale_links = []
        for section in work_product["sections"]:
            if section["removed"]:
                continue
            for link in section["evidence_links"]:
                info = self._resolve_mm6_endpoint_status(workspace, link["object_type"], link["object_id"])
                if not info["resolved"] or info.get("stale"):
                    stale_links.append({"section_id": section["id"], **info})
        return {
            "status": "assembled", "work_product_id": work_product_id,
            "has_stale_or_broken_evidence": len(stale_links) > 0, "stale_links": stale_links,
        }

    def record_work_product_export(
        self, workspace: ProjectWorkspace, work_product_id: str, export_format: str, exported_by: str,
        checksum: str, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 19: one real export EVENT per call - never inferred
        from state, always an explicit record that an export actually
        happened, with the real checksum of the bytes produced (computed
        by the caller, services.work_product_export.export_work_product,
        never re-derived here from something that could drift). Exporting
        is a READ of governed content, not itself gated by _require_
        work_product_editable - an issued OR a draft work product may
        both be exported (a draft export is for internal review, an
        issued export is the controlled output Section 19 describes)."""
        work_product = self._find(workspace.work_products, work_product_id)
        if work_product is None or work_product["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Work product {work_product_id} was not found.")

        record = WorkProductExportRecord(
            format=export_format, exported_at=_now(), exported_by=exported_by, checksum=checksum,
        )
        work_product["exports"].append(asdict(record))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="work_product_exported", actor=exported_by, role="human",
                payload={"work_product_id": work_product_id, "format": export_format, "checksum": checksum},
                correlation_id=work_product_id,
            )
        return work_product

    # -- investigation hypothesis survival / quality signal (CLAUDE-P11) -----------

    def record_case_outcome(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        outcome: str,
        reasoning: str,
        recorded_by: str,
        duplicate_of_case_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Records a human's verdict on this Case's own hypothesis. Same
        validation discipline as record_requirement_adjudication:
        existence-checked, closed vocabulary, reasoning required (a bare
        outcome word is never sufficient - see CaseOutcome's own
        docstring on why this is the one place a machine's investigative
        suggestion is ever declared right or wrong, and why that must
        always carry a human's stated basis)."""
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")

        if outcome not in CASE_OUTCOME_STATES:
            raise CaseWorkspaceError(
                f"'{outcome}' is not a recognized Case Outcome. "
                f"Use one of: {', '.join(CASE_OUTCOME_STATES)}."
            )

        if not reasoning or not reasoning.strip():
            raise CaseWorkspaceError(
                "A Case Outcome requires reasoning - the human basis for the "
                "verdict must be recorded, not just its outcome word."
            )

        if outcome == CASE_OUTCOME_DUPLICATE and not duplicate_of_case_id:
            raise CaseWorkspaceError(
                "A 'duplicate' outcome requires duplicate_of_case_id - which Case "
                "this one duplicates."
            )
        if duplicate_of_case_id and self._find(workspace.cases, duplicate_of_case_id) is None:
            raise CaseWorkspaceError(f"Case {duplicate_of_case_id} was not found.")

        record = CaseOutcome(
            id=_new_id(),
            project_id=workspace.project_id,
            case_id=case_id,
            outcome=outcome,
            reasoning=reasoning,
            recorded_by=recorded_by,
            recorded_at=_now(),
            duplicate_of_case_id=duplicate_of_case_id,
        )
        workspace.case_outcomes.append(asdict(record))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_outcome_recorded",
                actor=recorded_by, role="human",
                payload={"case_id": case_id, "outcome": outcome},
                correlation_id=case_id,
            )

        return asdict(record)

    def case_outcomes_for(self, workspace: ProjectWorkspace, case_id: str) -> list[dict]:
        return [o for o in workspace.case_outcomes if o["case_id"] == case_id]

    def latest_case_outcome_for(self, workspace: ProjectWorkspace, case_id: str) -> Optional[dict]:
        records = self.case_outcomes_for(workspace, case_id)
        return records[-1] if records else None

    def case_outcome_state(self, workspace: ProjectWorkspace, case_id: str) -> str:
        """Derived, never stored - mirrors requirement_adjudication_state's
        own derived-absence pattern: a Case with no recorded CaseOutcome
        is 'unresolved', not a placeholder row saying so."""
        latest = self.latest_case_outcome_for(workspace, case_id)
        return latest["outcome"] if latest is not None else CASE_OUTCOME_STATE_UNRESOLVED

    def case_origin_anchor(self, workspace: ProjectWorkspace, case: dict) -> Optional[dict]:
        """
        Whether this Case's own first Conversation message carried an
        Anchor - i.e. it was opened by escalating a machine-recognized,
        Case-shaped question (see start_investigation_from_aperture),
        rather than a human opening a Case outright with no machine
        involvement at all. Deliberately NOT a new stored field: a Case
        created via quick_start or the plain "+New Case" form has no
        anchor on its first message (or no conversation at all yet) and
        this simply returns None for those - reusing what
        _run_conversation_turn already records rather than adding a
        parallel "origin" field that could drift from what actually
        happened.
        """
        conversation = case.get("conversation") or []
        if not conversation:
            return None
        return conversation[0].get("anchor")

    def case_origin_kind(self, workspace: ProjectWorkspace, case: dict) -> str:
        """CASE_ORIGIN_DIRECT/ANCHOR_ESCALATED/AUTONOMOUS - checked in
        that priority order: AUTONOMOUS_INVESTIGATOR_ACTOR is checked
        first because an autonomous Case's own first message IS anchored
        (see create_autonomous_case) and would otherwise be indistinguishable
        from a human's anchor-escalated one by case_origin_anchor alone."""
        if case.get("created_by") == AUTONOMOUS_INVESTIGATOR_ACTOR:
            return CASE_ORIGIN_AUTONOMOUS
        return CASE_ORIGIN_ANCHOR_ESCALATED if self.case_origin_anchor(workspace, case) is not None else CASE_ORIGIN_DIRECT

    def can_open_autonomous_case_for(
        self, workspace: ProjectWorkspace, anchor: dict, max_open: int = MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT,
    ) -> bool:
        """
        The two bounded stop conditions (CLAUDE-P13R) checked BEFORE any
        autonomous Case is created - this is what keeps "opportunistic"
        from becoming "uncontrolled": a global per-project cap on
        currently-open autonomous Cases, and a same-anchor duplicate
        check (never open a second autonomous Case already investigating
        the exact same anchor). This is deliberately coarse, not a real
        topic-similarity dedup - two autonomous Cases about genuinely
        different aspects of the SAME Requirement would still both be
        blocked once one exists. A finer-grained check is a real,
        acknowledged gap, not something a naive heuristic should pretend
        to solve.
        """
        open_autonomous = [
            c for c in workspace.cases
            if c.get("created_by") == AUTONOMOUS_INVESTIGATOR_ACTOR and c["status"] != CASE_STATUS_ARCHIVED
        ]
        if len(open_autonomous) >= max_open:
            return False
        for case in open_autonomous:
            existing_anchor = self.case_origin_anchor(workspace, case)
            if (
                existing_anchor is not None
                and existing_anchor.get("anchor_type") == anchor.get("anchor_type")
                and existing_anchor.get("anchor_id") == anchor.get("anchor_id")
            ):
                return False
        return True

    def create_autonomous_case(
        self,
        workspace: ProjectWorkspace,
        title: str,
        objective: str,
        anchor: dict,
        spawned_from_step_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        The one real autonomous Case-creation path (CLAUDE-P13R) - always
        AUTONOMOUS_INVESTIGATOR_ACTOR, never a human. Callers MUST check
        can_open_autonomous_case_for first; this method itself does not
        re-check the stop conditions, so it stays a plain, honest
        "create this" primitive rather than silently swallowing a
        rejected request. The first Conversation message is system-
        authored (role="system") and anchored - never attributed to any
        human, never pretending a person asked this - recording WHY the
        machine opened it. Opening this Case is not itself authority: it
        says "there is enough here to investigate," nothing more (see
        CaseOutcome's own docstring) - the Approval Gate, ReviewerValidation,
        and CaseOutcome all remain exactly as they were for any other Case.
        """
        case = self.create_case(workspace, title=title, objective=objective, created_by=AUTONOMOUS_INVESTIGATOR_ACTOR)
        action_taken = f"autonomous_branch:{spawned_from_step_id}" if spawned_from_step_id else "autonomous_branch"
        # `objective` is `result.suggested_branch` from a real LLM
        # investigation call (services/requirement_investigation.py) -
        # this is model output, not a deterministic template string.
        self.add_message(
            workspace, case["id"], role="system", text=objective, anchor=anchor,
            action_taken=action_taken, content_class=CONTENT_CLASS_AI_PROPOSED,
        )

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_created",
                actor=AUTONOMOUS_INVESTIGATOR_ACTOR, role="machine",
                payload={
                    "case_id": case["id"], "title": title, "visibility": case["visibility"],
                    "origin": CASE_ORIGIN_AUTONOMOUS, "spawned_from_step_id": spawned_from_step_id,
                },
            )

        return self._find(workspace.cases, case["id"])

    def investigation_quality_rollup_for_project(self, workspace: ProjectWorkspace) -> dict:
        """
        The system-health signal (CLAUDE-P11, extended CLAUDE-P13R): a
        plain count of real, human-recorded CaseOutcomes (plus the
        derived 'unresolved' state), split three ways by case_origin_kind
        - anchor-escalated (a human accepted the aperture's offer),
        autonomous (the machine opened it entirely on its own), and
        direct (a human opened it outright, no machine involvement) -
        each of the first two further split by anchor type where that
        applies. This is the question "is Archiosk generating useful
        investigative hypotheses" made measurable, answered from the
        first two buckets - a directly-opened Case was never a machine
        suggestion, so its outcome says nothing about investigation
        quality. Keeping autonomous Cases in their OWN bucket (not merged
        into anchor_escalated, even though both are "anchored") is what
        lets deterioration specifically in UNSUPERVISED machine judgment
        be told apart from deterioration in human-accepted escalations.

        Deliberately read-only and consumed by nothing else in this
        codebase: not the interpreter's trigger matching, not
        requirement_investigation.py's prompt, not any model or engine
        choice, not can_open_autonomous_case_for's own stop conditions.
        "BEEHIVE may learn how to investigate without learning what to
        believe" is a property of what ISN'T wired to this method's
        return value, not just what is.
        """
        anchored_by_type: dict[str, dict[str, int]] = {}
        autonomous_by_type: dict[str, dict[str, int]] = {}
        unanchored: dict[str, int] = {}
        for case in workspace.cases:
            outcome_state = self.case_outcome_state(workspace, case["id"])
            origin_kind = self.case_origin_kind(workspace, case)
            if origin_kind == CASE_ORIGIN_AUTONOMOUS:
                anchor = self.case_origin_anchor(workspace, case)
                bucket = autonomous_by_type.setdefault(anchor.get("anchor_type", "unknown") if anchor else "unknown", {})
            elif origin_kind == CASE_ORIGIN_ANCHOR_ESCALATED:
                anchor = self.case_origin_anchor(workspace, case)
                bucket = anchored_by_type.setdefault(anchor.get("anchor_type", "unknown"), {})
            else:
                bucket = unanchored
            bucket[outcome_state] = bucket.get(outcome_state, 0) + 1
        return {
            "anchored_by_type": anchored_by_type,
            "autonomous_by_type": autonomous_by_type,
            "unanchored": unanchored,
        }

    # -- participants + represented-party perspective (CLAUDE-P12R) ----------------

    def record_participant(
        self, workspace: ProjectWorkspace, name: str, role_type: str, created_by: str,
        note: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Registers a project party. Deliberately no supersession/edit
        path in this pass - a Participant is a lightweight reference
        record (name + role), not a governed document; if a name needs
        correcting later that's a normal edit, not a lineage event, the
        same restraint ExpectedInformationProfile's own scope keeps."""
        if not name or not name.strip():
            raise CaseWorkspaceError("A Participant requires a name.")

        participant = Participant(
            id=_new_id(),
            project_id=workspace.project_id,
            name=name.strip(),
            role_type=normalize_open_world_value(role_type, KNOWN_PARTICIPANT_ROLES),
            created_at=_now(),
            created_by=created_by,
            note=note,
        )
        workspace.participants.append(asdict(participant))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="participant_registered",
                actor=created_by, role="human",
                payload={"participant_id": participant.id, "name": participant.name, "role_type": participant.role_type},
            )

        return asdict(participant)

    def participants_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.participants)

    def set_represented_party(self, workspace: ProjectWorkspace, reviewer: str, participant_id: str) -> None:
        """Which Participant `reviewer` currently represents in this
        Project - a personal setting, like last_viewed_by, not a
        governed fact about the Participant itself."""
        if self._find(workspace.participants, participant_id) is None:
            raise CaseWorkspaceError(f"Participant {participant_id} was not found.")
        workspace.represented_party_by[reviewer] = participant_id
        self.save(workspace)

    def represented_party_for(self, workspace: ProjectWorkspace, reviewer: str) -> Optional[dict]:
        participant_id = workspace.represented_party_by.get(reviewer)
        if participant_id is None:
            return None
        return self._find(workspace.participants, participant_id)

    def record_perspective_assessment(
        self,
        workspace: ProjectWorkspace,
        anchor: dict,
        participant_id: str,
        polarity: str,
        origin: str,
        reasoning: str,
        recorded_by: Optional[str] = None,
        confidence: Optional[float] = None,
        investigation_step_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Records what a governed object looks like FROM one Participant's
        position - never a rewrite of the object itself (see
        PerspectiveAssessment's own docstring). Append-only, same
        validation discipline as record_case_outcome/record_requirement_
        adjudication: existence-checked, closed vocabulary, reasoning
        required.
        """
        if self._find(workspace.participants, participant_id) is None:
            raise CaseWorkspaceError(f"Participant {participant_id} was not found.")

        if polarity not in KNOWN_PERSPECTIVE_POLARITIES:
            raise CaseWorkspaceError(
                f"'{polarity}' is not a recognized perspective polarity. "
                f"Use one of: {', '.join(KNOWN_PERSPECTIVE_POLARITIES)}."
            )

        if origin not in KNOWN_PERSPECTIVE_ORIGINS:
            raise CaseWorkspaceError(
                f"'{origin}' is not a recognized perspective origin. "
                f"Use one of: {', '.join(KNOWN_PERSPECTIVE_ORIGINS)}."
            )

        if not reasoning or not reasoning.strip():
            raise CaseWorkspaceError(
                "A Perspective Assessment requires reasoning - the basis for the "
                "risk/opportunity call must be recorded, not just its polarity word."
            )

        if origin == PERSPECTIVE_ORIGIN_HUMAN and not recorded_by:
            raise CaseWorkspaceError(
                "A human-origin Perspective Assessment requires recorded_by - this "
                "is never inferred, only ever an explicit reviewer act."
            )
        if origin == PERSPECTIVE_ORIGIN_MACHINE and recorded_by:
            raise CaseWorkspaceError(
                "A machine-origin Perspective Assessment must not carry recorded_by "
                "- that field exists only to attribute a genuinely human act."
            )

        record = PerspectiveAssessment(
            id=_new_id(),
            project_id=workspace.project_id,
            anchor=anchor,
            participant_id=participant_id,
            polarity=polarity,
            origin=origin,
            reasoning=reasoning,
            created_at=_now(),
            recorded_by=recorded_by,
            confidence=confidence,
            investigation_step_id=investigation_step_id,
        )
        workspace.perspective_assessments.append(asdict(record))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="perspective_assessment_recorded",
                actor=recorded_by or "system", role="human" if origin == PERSPECTIVE_ORIGIN_HUMAN else "machine",
                payload={
                    "anchor_type": anchor.get("anchor_type"), "anchor_id": anchor.get("anchor_id"),
                    "participant_id": participant_id, "polarity": polarity, "origin": origin,
                },
            )

        return asdict(record)

    def perspective_assessments_for_anchor(
        self, workspace: ProjectWorkspace, anchor_type: str, anchor_id: str, participant_id: Optional[str] = None,
    ) -> list[dict]:
        return [
            a for a in workspace.perspective_assessments
            if a["anchor"].get("anchor_type") == anchor_type
            and a["anchor"].get("anchor_id") == anchor_id
            and (participant_id is None or a["participant_id"] == participant_id)
        ]

    def perspective_convergence_for(
        self, workspace: ProjectWorkspace, anchor_type: str, anchor_id: str, participant_id: str,
    ) -> dict:
        """
        The convergence signal (CLAUDE-P12R #6): this Participant's
        latest human-recorded polarity and latest machine-recorded
        polarity for the same anchor, plus whether they agree - a plain
        read of two append-only records sharing an anchor+participant,
        not a new comparison mechanism. `agree` is None (not True/False)
        when either side hasn't recorded one yet - "no data" must never
        render as "disagreement."
        """
        records = self.perspective_assessments_for_anchor(workspace, anchor_type, anchor_id, participant_id)
        human = next((r for r in reversed(records) if r["origin"] == PERSPECTIVE_ORIGIN_HUMAN), None)
        machine = next((r for r in reversed(records) if r["origin"] == PERSPECTIVE_ORIGIN_MACHINE), None)
        agree = None
        if human is not None and machine is not None:
            agree = human["polarity"] == machine["polarity"]
        return {"human": human, "machine": machine, "agree": agree}

    # -- reviewer validation --------------------------------------------------------

    def record_reviewer_validation(
        self,
        workspace: ProjectWorkspace,
        finding_id: str,
        validation: str,
        reviewer: str,
        correction_note: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
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

        self._require_case_not_archived(workspace, finding["case_id"])

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
        # ReviewerValidation is, by construction, always a human act (this
        # is its entire reason for existing - a human's epistemic judgment
        # about a machine Finding) - no separate origin check is needed the
        # way machine-originated writes elsewhere require one.
        crossed = self._cross_collaboration_threshold_if_qualifying(
            workspace, finding["case_id"], reviewer, "reviewer_validation", record.id,
        )
        self.save(workspace)

        if crossed and governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_became_collaborative",
                actor=reviewer, role="human",
                payload={
                    "case_id": finding["case_id"], "contribution_type": "reviewer_validation",
                    "contribution_id": record.id,
                },
                correlation_id=finding["case_id"],
            )

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
        governance_log: Optional[GovernanceLog] = None,
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

        self._require_case_not_archived(workspace, finding["case_id"])

        record = Disposition(
            id=_new_id(),
            finding_id=finding_id,
            disposition=disposition,
            reviewer=reviewer,
            recorded_at=_now(),
        )
        workspace.dispositions.append(asdict(record))
        # Disposition, like ReviewerValidation, is by construction always a
        # human act - no separate machine-origin check needed.
        crossed = self._cross_collaboration_threshold_if_qualifying(
            workspace, finding["case_id"], reviewer, "disposition", record.id,
        )
        self.save(workspace)

        if crossed and governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_became_collaborative",
                actor=reviewer, role="human",
                payload={
                    "case_id": finding["case_id"], "contribution_type": "disposition",
                    "contribution_id": record.id,
                },
                correlation_id=finding["case_id"],
            )

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

            self._require_case_not_archived(workspace, finding["case_id"])

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
        # CLAUDE-P40-E2A, Section A: registering a NEW Requirement is
        # new analysis work, not an existing dependent reference (unlike
        # a prior Requirement/Finding that already cites this Source,
        # which must keep resolving it honestly - see active_sources'
        # own docstring) - removed content must not silently re-enter
        # active Workspace state this way.
        if source.get("removed_at"):
            raise CaseWorkspaceError(f"Source {source_id} has been removed. Restore it first.")
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

    # -- requirement adjudication (Prompt 19 / Foundation Batch K) ------------------

    def record_requirement_adjudication(
        self,
        workspace: ProjectWorkspace,
        requirement_id: str,
        outcome: str,
        adjudicator: str,
        reasoning: str,
        evidence_finding_ids: Optional[list[str]] = None,
        evidence_relationship_ids: Optional[list[str]] = None,
        attribution: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Records a Requirement-level compliance determination. Append-only
        - always creates a new record; see
        latest_requirement_adjudication_for/requirement_adjudication_state
        for the current effective outcome. `reasoning` is required, not
        optional (ADR-032-R05/R06: reviewer reasoning is preserved as
        first-class forensic evidence, never just a bare outcome word) -
        the same honesty-machinery shape as Requirement.registration_
        method's mandatory, never-defaulted field.

        Deliberately does NOT participate in any Case's collaboration
        threshold, even when `evidence_finding_ids` references a Finding
        that belongs to a Shared Case (the ratified spec's own
        deliberately-flagged boundary case, resolved here explicitly, not
        left as a silent default): adjudicating a Requirement is a
        contribution to the Requirement's own governed record, a
        genuinely different object from the Case whose evidence it cites.
        Counting it would blur two distinct objects' provenance together.

        CLAUDE-POSTCAMEL-COMM-I5A: `attribution` is Optional HERE
        (backward-compatible with every pre-existing direct caller of
        this method, matching this codebase's own established pattern
        for every prior additive field) - it is the real product route
        (`adjudicate_requirement`) that makes an explicit choice
        mandatory, not this store method. When supplied, it must be one
        of KNOWN_ADJUDICATION_ATTRIBUTIONS; nothing here infers or
        defaults it from `adjudicator`'s own identity, since a username
        alone was exactly the insufficiency this correction exists to
        fix.
        """
        requirement = self._find(workspace.requirements, requirement_id)
        if requirement is None:
            raise CaseWorkspaceError(f"Requirement {requirement_id} was not found.")

        if outcome not in REQUIREMENT_ADJUDICATION_OUTCOMES:
            raise CaseWorkspaceError(
                f"'{outcome}' is not a recognized Requirement Adjudication outcome. "
                f"Use one of: {', '.join(REQUIREMENT_ADJUDICATION_OUTCOMES)}."
            )

        if not reasoning or not reasoning.strip():
            raise CaseWorkspaceError(
                "A Requirement Adjudication requires reasoning - the human basis "
                "for the determination must be recorded, not just its outcome."
            )

        if attribution is not None and attribution not in KNOWN_ADJUDICATION_ATTRIBUTIONS:
            raise CaseWorkspaceError(
                f"'{attribution}' is not a recognized adjudication attribution. "
                f"Use one of: {', '.join(KNOWN_ADJUDICATION_ATTRIBUTIONS)}."
            )

        for finding_id in evidence_finding_ids or []:
            if self._find(workspace.findings, finding_id) is None:
                raise CaseWorkspaceError(f"Finding {finding_id} was not found.")

        for relationship_id in evidence_relationship_ids or []:
            if self._find(workspace.relationships, relationship_id) is None:
                raise CaseWorkspaceError(f"Relationship {relationship_id} was not found.")

        record = RequirementAdjudication(
            id=_new_id(),
            project_id=workspace.project_id,
            requirement_id=requirement_id,
            outcome=outcome,
            adjudicator=adjudicator,
            adjudicated_at=_now(),
            reasoning=reasoning,
            evidence_finding_ids=list(evidence_finding_ids or []),
            evidence_relationship_ids=list(evidence_relationship_ids or []),
            attribution=attribution,
        )
        workspace.requirement_adjudications.append(asdict(record))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="requirement_adjudicated",
                # CLAUDE-POSTCAMEL-COMM-I5A: this previously hardcoded
                # role="human" unconditionally, regardless of who/what
                # actually performed the write - a false claim for every
                # agent-entered adjudication (see the four legacy
                # COMM-I3 records this same correction addresses).
                # Derived honestly from the real attribution now, not
                # asserted independently of it.
                actor=adjudicator, role=(attribution or "unspecified"),
                payload={
                    "requirement_adjudication_id": record.id, "requirement_id": requirement_id,
                    "outcome": outcome, "attribution": attribution,
                },
                correlation_id=record.id,
            )
        return asdict(record)

    def requirement_adjudications_for(self, workspace: ProjectWorkspace, requirement_id: str) -> list[dict]:
        return [a for a in workspace.requirement_adjudications if a["requirement_id"] == requirement_id]

    def latest_requirement_adjudication_for(self, workspace: ProjectWorkspace, requirement_id: str) -> Optional[dict]:
        records = self.requirement_adjudications_for(workspace, requirement_id)
        return records[-1] if records else None

    def requirement_adjudication_state(self, workspace: ProjectWorkspace, requirement_id: str) -> str:
        """Derived, never stored - mirrors review_state_for_finding's own
        derived-absence pattern (Prompt 19 #5)."""
        latest = self.latest_requirement_adjudication_for(workspace, requirement_id)
        if latest is None:
            return REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED
        return latest["outcome"]

    def requirement_evidence(self, workspace: ProjectWorkspace, requirement_id: str) -> dict:
        """
        Makes the compliance rollup explainable, not just countable:
        resolves the requirement's own LATEST RequirementAdjudication's
        `evidence_finding_ids`/`evidence_relationship_ids` (already the
        real, existing governed link between a Requirement and the
        Findings/Relationships a human actually cited when adjudicating -
        no new linkage object invented) into the actual referenced
        records, plus every `AcceptedKnowledge` entry that traces back to
        one of those same Findings via its own `source_finding_id` (a
        second existing pointer, joined here rather than duplicated onto
        a new field).

        Deliberately does not scan every historical adjudication - only
        the current, latest one - matching `requirement_adjudication_state`'s
        own "derived from latest only" convention: this answers "why is
        the Requirement in its CURRENT state," not a full audit history
        (the full history remains reconstructable via
        `requirement_adjudications_for`, unchanged).

        Returns Finding/Relationship/AcceptedKnowledge as their raw
        stored dicts - no Case-visibility filtering happens here (this
        is a pure read of already-stored project-level state); the
        caller (route layer, which alone knows the current requester's
        identity) is responsible for deciding what to actually render
        for a Finding whose own Case isn't visible to them.
        """
        adjudication = self.latest_requirement_adjudication_for(workspace, requirement_id)
        if adjudication is None:
            return {"adjudication": None, "findings": [], "relationships": [], "accepted_knowledge": []}

        finding_ids = adjudication.get("evidence_finding_ids") or []
        relationship_ids = adjudication.get("evidence_relationship_ids") or []
        return {
            "adjudication": adjudication,
            "findings": [f for f in workspace.findings if f["id"] in finding_ids],
            "relationships": [r for r in workspace.relationships if r["id"] in relationship_ids],
            "accepted_knowledge": [k for k in workspace.knowledge if k.get("source_finding_id") in finding_ids],
        }

    def current_requirement_for(self, workspace: ProjectWorkspace, requirement_id: str) -> Optional[dict]:
        """
        CLAUDE-P15: walks the Supersession chain FORWARD from ANY
        Requirement id - current or historical - to whichever version is
        CURRENTLY governing (status == active). The complement of routes/
        workspace.py's existing `_requirement_revision_history` closure,
        which walks BACKWARD from a current Requirement to its
        predecessors for display; this is the direction real
        investigation needs - "given this (possibly stale) id, what
        actually governs right now" - and is promoted to a real,
        reusable store method rather than a second route-local closure,
        so services/requirement_investigation.py can use the exact same
        logic the template already relies on. Returns None only if the
        id doesn't exist at all; returns the SAME requirement unchanged
        if it is already current (zero-length walk).
        """
        requirement = self._find(workspace.requirements, requirement_id)
        if requirement is None:
            return None
        current_id = requirement_id
        while True:
            successor_supersession = next(
                (
                    s for s in workspace.supersessions
                    if s["predecessor_type"] == OBJECT_KIND_REQUIREMENT and s["predecessor_id"] == current_id
                ),
                None,
            )
            if successor_supersession is None:
                break
            current_id = successor_supersession["successor_id"]
        return self._find(workspace.requirements, current_id)

    def requirement_predecessor(self, workspace: ProjectWorkspace, requirement_id: str) -> Optional[dict]:
        """The immediate prior version this Requirement superseded, if
        any - one step of the same backward walk _requirement_revision_
        history performs, promoted here so the investigator can compare
        'what changed' without duplicating the traversal."""
        predecessor_supersession = next(
            (
                s for s in workspace.supersessions
                if s["successor_type"] == OBJECT_KIND_REQUIREMENT and s["successor_id"] == requirement_id
            ),
            None,
        )
        if predecessor_supersession is None:
            return None
        return self._find(workspace.requirements, predecessor_supersession["predecessor_id"])

    def requirements_evidenced_by_finding(self, workspace: ProjectWorkspace, finding_id: str) -> list[dict]:
        """Reverse of requirement_evidence's Finding side: every
        Requirement whose own latest RequirementAdjudication currently
        cites `finding_id` as evidence - used for AcceptedKnowledge's own
        drill-back ("which Requirement(s), if any, is this linked to"),
        via AcceptedKnowledge.source_finding_id. Honestly returns an
        empty list, never a fabricated link, when no adjudication cites
        this Finding."""
        linked = []
        for requirement in workspace.requirements:
            adjudication = self.latest_requirement_adjudication_for(workspace, requirement["id"])
            if adjudication and finding_id in (adjudication.get("evidence_finding_ids") or []):
                linked.append(requirement)
        return linked

    # -- requirement item promotion bridge (ratified governance baseline) ----------

    def promote_requirement_item(
        self,
        workspace: ProjectWorkspace,
        case_id: str,
        source_id: str,
        requirement_item: dict,
        actor: str,
        trigger: AnalysisTrigger,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Bridges a `RequirementItem` (the legacy, day-one extraction
        pipeline in services/bhive_parser.py - `{"id", "text",
        "category", "confidence", "source_line"}`) into the governed
        `Requirement` primitive. Deliberately takes a plain dict, not a
        typed import from bhive_parser - this module has never imported
        that one and keeps the two pipelines structurally decoupled, per
        the architecture review's own finding that they are different
        stages of one river, not a duplicate-truth risk requiring tighter
        coupling to resolve.

        `source_id` is never inferred - the caller must explicitly assert
        which real Source the extracted text actually came from (no-
        silent-provenance-fabrication discipline, governance/specified-
        unbuilt/investigation-lifecycle-extensions.md). `trigger` is
        required, not defaulted, mirroring record_analysis's own honesty
        discipline that every Analysis must say why it started.

        Preserves confidence, reasoning-bearing context, and provenance by
        creating an accompanying Finding + AnalysisRun (not just the bare
        Requirement) - this is the promotion's "explicit AnalysisTrigger"
        requirement satisfied concretely, not just documented. All three
        new records (Finding, AnalysisRun, Requirement) are constructed in
        memory and written in exactly one self.save(workspace) call, so a
        failure can never leave an orphan Finding without its Requirement
        or vice versa - the same single-save-per-governed-operation
        pattern already used by register_table_evidence, not a new
        transaction mechanism.

        Never touches Requirement.status beyond its ordinary default
        (REQUIREMENT_STATUS_ACTIVE) and never creates a Disposition or
        RequirementAdjudication - promotion only ever produces an
        un-adjudicated, ordinary Requirement. It still requires the normal
        RequirementAdjudication process before its compliance status means
        anything; this function performs no authority escalation of its
        own.
        """
        case = self._find(workspace.cases, case_id)
        if case is None:
            raise CaseWorkspaceError(f"Case {case_id} was not found.")

        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if source.get("removed_at"):
            raise CaseWorkspaceError(f"Source {source_id} has been removed. Restore it first.")

        missing = [f for f in ("id", "text", "confidence") if f not in requirement_item]
        if missing:
            raise CaseWorkspaceError(
                "requirement_item is missing required field(s): "
                f"{', '.join(missing)}."
            )

        source_location = None
        if requirement_item.get("source_line") is not None:
            source_location = {
                "location_type": REQUIREMENT_LOCATION_TYPE_PARAGRAPH,
                "line": requirement_item["source_line"],
            }

        started_at = _now()
        analysis_id = _new_id()
        finding_id = _new_id()

        finding = Finding(
            id=finding_id,
            project_id=workspace.project_id,
            case_id=case_id,
            analysis_id=analysis_id,
            statement=requirement_item["text"],
            machine_confidence=requirement_item["confidence"],
            created_at=_now(),
        )

        analysis = AnalysisRun(
            id=analysis_id,
            project_id=workspace.project_id,
            case_id=case_id,
            source_ids=[source_id],
            objective=(
                f"Promote extracted requirement item {requirement_item['id']} "
                "to a governed Requirement."
            ),
            engine_name="requirement_item_promotion",
            engine_version="1.0",
            started_at=started_at,
            completed_at=_now(),
            trigger=asdict(trigger),
            finding_ids=[finding_id],
        )

        requirement = Requirement(
            id=_new_id(),
            project_id=workspace.project_id,
            source_id=source_id,
            original_requirement_identifier=requirement_item["id"],
            text_reference=requirement_item["text"],
            created_at=_now(),
            created_by=actor,
            registration_method=REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED,
            subject_domain=requirement_item.get("category"),
            source_location=source_location,
        )

        workspace.findings.append(asdict(finding))
        case["finding_ids"].append(finding_id)
        workspace.analyses.append(asdict(analysis))
        case["analysis_ids"].append(analysis_id)
        workspace.requirements.append(asdict(requirement))

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="requirement_item_promoted",
                actor=actor, role="system",
                payload={
                    "requirement_item_id": requirement_item["id"],
                    "requirement_id": requirement.id,
                    "finding_id": finding_id,
                    "analysis_id": analysis_id,
                    "source_id": source_id,
                },
                correlation_id=requirement.id,
            )

        return {
            "requirement": asdict(requirement),
            "finding": asdict(finding),
            "analysis": asdict(analysis),
        }

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
        reason: Optional[str] = None,
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
            reason=reason,
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

    # -- CLAUDE-MM6: Cross-Document and Cross-Modal Relationship River --------
    # record_relationship (above) is deliberately left UNCHANGED - it has no
    # endpoint-existence check at all, and dozens of pre-existing tests
    # (Foundation Batches B/C/D/F/J, the NREOCRC lab fixtures, the self-test
    # corpus) already rely on that permissiveness, some for object kinds
    # this store has no dedicated existence-check for at all. Tightening it
    # in place would be a real regression risk for no proven benefit to
    # those already-governed call sites. Section 6/16's own "validate every
    # endpoint... deny cross-project relationships" requirement is met
    # instead by this NEW, additive, narrower entry point - the one this
    # stage's own routes/UI actually use - covering exactly the MM1-MM5
    # evidence-contract object kinds the cross-modal river vertical slice
    # needs, the same "add a safer wrapper, don't weaken the general
    # primitive" pattern MM3's create_addressable_cell_region already
    # established for create_addressable_region.

    # object_type -> the workspace list to search and the project_id key
    # each stored dict already carries (every one of these already stores
    # project_id directly on the record - Prompt 12/MM1's own standing
    # discipline - so this is a lookup table, not new validation logic).
    _MM6_ENDPOINT_LISTS = {
        OBJECT_KIND_EVIDENCE_ITEM: "evidence_items",
        OBJECT_KIND_ADDRESSABLE_REGION: "addressable_regions",
        OBJECT_KIND_STRUCTURAL_UNIT: "structural_units",
        OBJECT_KIND_DERIVED_OBSERVATION: "derived_observations",
        OBJECT_KIND_SOURCE: "sources",
        OBJECT_KIND_TASK: "tasks",
        OBJECT_KIND_FINDING: "findings",
        # CLAUDE-MM8: both added here for the first time - a work-product
        # section can now cite a Claim directly (Section 24: "claim
        # classifications must not disappear" when an MM7 answer is
        # promoted into a document) and a WorkProduct can cite/relate to
        # another WorkProduct (Section 31's based_on/cites/etc.).
        OBJECT_KIND_CLAIM: "claims",
        OBJECT_KIND_WORK_PRODUCT: "work_products",
    }

    def _resolve_mm6_endpoint(self, workspace: ProjectWorkspace, object_type: str, object_id: str) -> Optional[dict]:
        """Returns the real record for (object_type, object_id) IF it
        exists in THIS project, else None - a direct top-level
        `workspace.<list>` lookup for every MM6-supported object kind
        (Finding included - `workspace.findings` is itself already a
        flat, top-level, project-scoped list, not nested under Case)."""
        object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
        list_name = self._MM6_ENDPOINT_LISTS.get(object_type)
        if list_name is None:
            return None
        record = self._find(getattr(workspace, list_name), object_id)
        if record is None:
            return None
        # Task carries no project_id field of its own (see Task's own
        # docstring) - workspace.tasks is itself already a project-scoped
        # flat list (one JSON file per project), so finding it there
        # already proves project membership; every OTHER MM6-supported
        # kind does carry project_id and is defense-in-depth checked here.
        if "project_id" in record and record["project_id"] != workspace.project_id:
            return None
        return record

    def _resolve_mm6_endpoint_status(self, workspace: ProjectWorkspace, object_type: str, object_id: str) -> dict:
        """Shared by resolve_relationship_status and resolve_claim_status
        (CLAUDE-MM7) - the SAME "does this endpoint still resolve, and is
        it stale" question, asked identically whether the endpoint is one
        side of a Relationship or one citation of a Claim. Extracted
        rather than duplicated so the two resolvers can never quietly
        drift apart on what "stale" means for a given object_type."""
        record = self._resolve_mm6_endpoint(workspace, object_type, object_id)
        if record is None:
            return {"object_type": object_type, "object_id": object_id, "resolved": False}
        info = {"object_type": object_type, "object_id": object_id, "resolved": True}
        # Reuse the SAME citation resolver already built for MM2-MM5's
        # own regions where the endpoint IS a region - the cheapest,
        # most direct way to learn whether the underlying Source has
        # been superseded (Section 14's own staleness trigger).
        if object_type == OBJECT_KIND_ADDRESSABLE_REGION:
            citation = self.resolve_region_citation(workspace, object_id)
            info["citation"] = citation
            info["stale"] = citation.get("status") == "stale"
        elif object_type == OBJECT_KIND_EVIDENCE_ITEM and record.get("region_id"):
            citation = self.resolve_region_citation(workspace, record["region_id"])
            info["citation"] = citation
            info["stale"] = citation.get("status") == "stale"
        elif object_type == OBJECT_KIND_SOURCE:
            info["stale"] = bool(record.get("superseded_by_source_id"))
        else:
            info["stale"] = False
        return info

    def record_evidence_relationship(
        self,
        workspace: ProjectWorkspace,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        relationship_type: str,
        reason: Optional[str] = None,
        created_by: Optional[str] = None,
        provisional: bool = True,
        confidence: Optional[float] = None,
        related_finding_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 6: "do not permit arbitrary cross-project endpoints" - both
        `(from_type, from_id)` and `(to_type, to_id)` are resolved against
        THIS project's own real records before anything is written; a
        nonexistent id or one belonging to a different project raises
        CaseWorkspaceError rather than silently creating a broken-from-
        creation or cross-project-leaking edge. Restricted to the MM1-MM5
        evidence-contract object kinds (see _MM6_ENDPOINT_LISTS) plus
        Finding and Task - an endpoint type outside that set raises rather
        than falling through to the unchecked general primitive.
        """
        if from_type not in self._MM6_ENDPOINT_LISTS:
            raise CaseWorkspaceError(f"'{from_type}' is not a supported relationship endpoint type for this stage.")
        if to_type not in self._MM6_ENDPOINT_LISTS:
            raise CaseWorkspaceError(f"'{to_type}' is not a supported relationship endpoint type for this stage.")
        if self._resolve_mm6_endpoint(workspace, from_type, from_id) is None:
            raise CaseWorkspaceError(f"Relationship 'from' endpoint ({from_type} {from_id}) was not found in this project.")
        if self._resolve_mm6_endpoint(workspace, to_type, to_id) is None:
            raise CaseWorkspaceError(f"Relationship 'to' endpoint ({to_type} {to_id}) was not found in this project.")

        relationship = self.record_relationship(
            workspace, from_type=from_type, from_id=from_id, to_type=to_type, to_id=to_id,
            relationship_type=relationship_type, created_by=created_by, provisional=provisional,
            confidence=confidence, related_finding_id=related_finding_id, reason=reason,
        )

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="relationship_recorded",
                actor=created_by or "system", role="human" if not provisional else "system",
                payload={
                    "relationship_id": relationship["id"], "relationship_type": relationship["relationship_type"],
                    "from_type": from_type, "from_id": from_id, "to_type": to_type, "to_id": to_id,
                },
                correlation_id=relationship["id"],
            )
        return relationship

    def resolve_relationship_status(self, workspace: ProjectWorkspace, relationship_id: str) -> dict:
        """
        Section 6/14: the read-time-derived status a Relationship doesn't
        store on itself - mirrors resolve_region_citation's own shape
        (a stable id resolved into a human-legible state at read time,
        never persisted). Returns `{"status": "unresolved", ...}` for an
        unknown relationship id (the honest broken-anchor shape every
        other *_citation/*_status resolver in this codebase already uses),
        or the full resolved dict on success:
        `{"status", "relationship_id", "relationship_type", "reason",
        "from": {...endpoint status...}, "to": {...endpoint status...},
        "superseded_by_relationship_id"}`.

        Status precedence (most authoritative first): a human REJECTION or
        DISPUTE always wins over machine-derived staleness (Section 13: "a
        human disputes an AI-proposed relationship" is first-class
        information, never silently overridden by a later-computed
        status); then SUPERSEDED (a real replacement relationship already
        exists); then BROKEN (an endpoint no longer resolves at all); then
        STALE (an endpoint's own Source has been superseded, but the
        endpoint itself still resolves - Section 14's own worked example);
        then the ordinary CONFIRMED/PROPOSED pair from `provisional`.
        """
        relationship = self._find(workspace.relationships, relationship_id)
        if relationship is None:
            return {"status": "unresolved", "relationship_id": relationship_id}

        from_status = self._resolve_mm6_endpoint_status(workspace, relationship["from_type"], relationship["from_id"])
        to_status = self._resolve_mm6_endpoint_status(workspace, relationship["to_type"], relationship["to_id"])

        successor_supersession = next(
            (s for s in workspace.supersessions
             if s["predecessor_type"] == OBJECT_KIND_RELATIONSHIP and s["predecessor_id"] == relationship_id),
            None,
        )

        if relationship.get("validation_state") == RELATIONSHIP_VALIDATION_REJECTED:
            status = RELATIONSHIP_STATUS_REJECTED
        elif relationship.get("validation_state") == RELATIONSHIP_VALIDATION_DISPUTED:
            status = RELATIONSHIP_STATUS_DISPUTED
        elif successor_supersession is not None:
            status = RELATIONSHIP_STATUS_SUPERSEDED
        elif not from_status["resolved"] or not to_status["resolved"]:
            status = RELATIONSHIP_STATUS_BROKEN
        elif from_status.get("stale") or to_status.get("stale"):
            status = RELATIONSHIP_STATUS_STALE
        elif relationship.get("provisional", True):
            status = RELATIONSHIP_STATUS_PROPOSED
        else:
            status = RELATIONSHIP_STATUS_CONFIRMED

        result = {
            "status": status,
            "relationship_id": relationship_id,
            "relationship_type": relationship["relationship_type"],
            "reason": relationship.get("reason"),
            "from": from_status,
            "to": to_status,
        }
        if successor_supersession is not None:
            result["superseded_by_relationship_id"] = successor_supersession["successor_id"]
        return result

    def dispute_relationship(
        self, workspace: ProjectWorkspace, relationship_id: str, actor: str,
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 13: "a human disputes an AI-proposed relationship" -
        marks the edge disputed WITHOUT deleting or rewriting it (Section
        15's own "do not silently overwrite a mistaken relationship")."""
        relationship = self._find(workspace.relationships, relationship_id)
        if relationship is None or relationship["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Relationship {relationship_id} was not found.")
        relationship["validation_state"] = RELATIONSHIP_VALIDATION_DISPUTED
        self.save(workspace)
        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="relationship_disputed",
                actor=actor, role="human", payload={"relationship_id": relationship_id, "reason": reason},
                correlation_id=relationship_id,
            )
        return relationship

    def reject_relationship(
        self, workspace: ProjectWorkspace, relationship_id: str, actor: str,
        reason: Optional[str] = None, governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Section 15: a stronger, terminal form of dispute_relationship -
        "reason; author; date" are all preserved (reason on the record
        itself; author/date in the governance log entry, the same split
        every other correction in this codebase already uses)."""
        relationship = self._find(workspace.relationships, relationship_id)
        if relationship is None or relationship["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Relationship {relationship_id} was not found.")
        relationship["validation_state"] = RELATIONSHIP_VALIDATION_REJECTED
        self.save(workspace)
        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="relationship_rejected",
                actor=actor, role="human", payload={"relationship_id": relationship_id, "reason": reason},
                correlation_id=relationship_id,
            )
        return relationship

    def supersede_relationship(
        self,
        workspace: ProjectWorkspace,
        old_relationship_id: str,
        to_type: str,
        to_id: str,
        relationship_type: str,
        reason: str,
        actor: str,
        from_type: Optional[str] = None,
        from_id: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Section 15: "preserve original relationship; correction or
        rejection; reason; author; date; ... replacement relationship" -
        implemented by making this stage the SECOND real consumer of the
        pre-existing Supersession primitive (record_supersession's own
        docstring names future consumers beyond Source; MM6 is the first
        to actually arrive), rather than inventing a parallel correction
        mechanism. The OLD relationship is never deleted or mutated by
        this method itself (resolve_relationship_status derives its
        "superseded" state purely from the Supersession record) - only a
        NEW relationship is created and linked as successor.

        `from_type`/`from_id` default to the OLD relationship's own FROM
        endpoint when omitted (Section 15's own worked correction case:
        the FROM side is usually unchanged, only the TO side or the
        relationship_type itself was wrong) - pass them explicitly to
        correct the FROM side too.
        """
        old = self._find(workspace.relationships, old_relationship_id)
        if old is None or old["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Relationship {old_relationship_id} was not found.")

        new_relationship = self.record_evidence_relationship(
            workspace, from_type=from_type or old["from_type"], from_id=from_id or old["from_id"],
            to_type=to_type, to_id=to_id, relationship_type=relationship_type, reason=reason,
            created_by=actor, provisional=False, governance_log=governance_log,
        )

        supersession = self.record_supersession(
            workspace, predecessor_type=OBJECT_KIND_RELATIONSHIP, predecessor_id=old_relationship_id,
            successor_type=OBJECT_KIND_RELATIONSHIP, successor_id=new_relationship["id"],
            actor=actor, reason=reason, authority_class="approval_gate:relationship_correction",
        )

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="relationship_superseded",
                actor=actor, role="human",
                payload={"old_relationship_id": old_relationship_id, "new_relationship_id": new_relationship["id"], "reason": reason},
                correlation_id=new_relationship["id"],
            )
        return {"old_relationship_id": old_relationship_id, "new_relationship": new_relationship, "supersession": supersession}

    def build_relationship_sachet(
        self, workspace: ProjectWorkspace, relationship_id: str, task_description: Optional[str] = None,
    ) -> dict:
        """
        Section 12: the Governed Evidence Sachet, extended to a
        RELATIONSHIP PATH - "one relationship path... citations and
        versions... disclose what is included and excluded." Mirrors
        build_evidence_sachet's own read-time-assembly shape exactly (no
        new persisted object), but assembles around a Relationship's TWO
        endpoints rather than one region's sibling regions. Each endpoint
        gets its own citation where the object kind supports one
        (AddressableRegion/EvidenceItem-with-a-region); a Source, Task, or
        Finding endpoint gets its own minimal identity summary instead,
        never a fabricated citation for a kind that has none. Excludes
        every OTHER relationship and every unrelated object in the
        project - `excluded.summary` states this explicitly, the same
        honesty build_evidence_sachet's own manifest already establishes.
        """
        status = self.resolve_relationship_status(workspace, relationship_id)
        if status["status"] == "unresolved":
            return {"status": "unavailable", "relationship_id": relationship_id}
        relationship = self._find(workspace.relationships, relationship_id)

        total_relationships = len(workspace.relationships)
        return {
            "status": "assembled",
            "task": task_description,
            "relationship": {
                "relationship_id": relationship_id,
                "relationship_type": relationship["relationship_type"],
                "reason": relationship.get("reason"),
                "status": status["status"],
                "confidence": relationship.get("confidence"),
                "created_by": relationship.get("created_by"),
                "created_at": relationship.get("created_at"),
            },
            "from": self._resolve_mm6_endpoint_summary(workspace, relationship["from_type"], relationship["from_id"]),
            "to": self._resolve_mm6_endpoint_summary(workspace, relationship["to_type"], relationship["to_id"]),
            "excluded": {
                "summary": f"{max(total_relationships - 1, 0)} other relationship(s) in this project were excluded entirely.",
            },
        }

    def _resolve_mm6_endpoint_summary(self, workspace: ProjectWorkspace, object_type: str, object_id: str) -> dict:
        """Shared by build_relationship_sachet and CLAUDE-MM7's own
        build_investigation_evidence_sachet/explain_investigation_answer -
        the SAME "give me an intelligible summary of this endpoint,
        never just a bare id" question, asked identically whether the
        endpoint is one side of a Relationship or one citation of a
        Claim. Extracted rather than duplicated for the same reason as
        _resolve_mm6_endpoint_status above."""
        record = self._resolve_mm6_endpoint(workspace, object_type, object_id)
        summary = {"object_type": object_type, "object_id": object_id, "resolved": record is not None}
        if record is None:
            return summary
        if object_type == OBJECT_KIND_ADDRESSABLE_REGION:
            summary["citation"] = self.resolve_region_citation(workspace, object_id)
        elif object_type == OBJECT_KIND_EVIDENCE_ITEM:
            summary["content"] = record.get("content")
            summary["evidence_class"] = record.get("evidence_class")
            if record.get("region_id"):
                summary["citation"] = self.resolve_region_citation(workspace, record["region_id"])
        elif object_type == OBJECT_KIND_DERIVED_OBSERVATION:
            summary["statement"] = record.get("statement")
            summary["author_type"] = record.get("author_type")
        elif object_type == OBJECT_KIND_FINDING:
            summary["statement"] = record.get("statement")
            summary["claim_status"] = record.get("claim_status")
        elif object_type == OBJECT_KIND_SOURCE:
            summary["name"] = record.get("name")
            summary["security_classification"] = record.get("security_classification")
            summary["issue_date"] = record.get("issue_date")
            summary["revision"] = record.get("revision")
            summary["superseded"] = bool(record.get("superseded_by_source_id"))
        elif object_type == OBJECT_KIND_TASK:
            summary["title"] = record.get("title")
            summary["status"] = record.get("status")
        return summary

    def explain_evidence_trust(self, workspace: ProjectWorkspace, evidence_item_id: str) -> dict:
        """
        Section 10: the Trustworthy Answer Contract's own cross-modal
        foundation - "the equivalent of 'Why should I trust this?'"
        answered as a read-time AGGREGATION of already-governed records
        (no new storage, matching this whole module's own doctrine).

        `basis` classifies this ONE EvidenceItem via its own existing,
        already-closed `evidence_class` (KNOWN_EVIDENCE_CLASSES) - the
        same five-vs-more-way split Section 10 asks for was already built
        by MM1, not reinvented here:
          - EVIDENCE_CLASS_DIRECT_SOURCE -> "directly_verified_evidence"
          - EVIDENCE_CLASS_IMPORTED_STRUCTURED_VALUE/_CALCULATED_VALUE ->
            "imported_or_deterministic_calculation"
          - EVIDENCE_CLASS_AI_GENERATED_PROPOSAL -> "ai_generated_proposal"
          - EVIDENCE_CLASS_EXTERNALLY_RESEARCHED -> "externally_researched"
          - everything else -> "other_recorded_evidence"

        `supporting_relationships`/`contradicting_relationships` are this
        evidence's own edges filtered by relationship_type (Section 13:
        contradiction is first-class, never collapsed into a false
        consensus) - each carries its own resolve_relationship_status
        result, so a caller can see confirmed vs. disputed vs. stale
        support/contradiction, not just a bare count. `observations`/
        `findings` are whatever DerivedObservation/Finding this evidence
        is linked to via a relationship - Section 8's own evidence ->
        observation -> Finding chain, read back out.
        """
        evidence = self._find(workspace.evidence_items, evidence_item_id)
        if evidence is None or evidence["project_id"] != workspace.project_id:
            return {"status": "unavailable", "evidence_item_id": evidence_item_id}

        evidence_class = evidence.get("evidence_class")
        if evidence_class == EVIDENCE_CLASS_DIRECT_SOURCE:
            basis = "directly_verified_evidence"
        elif evidence_class in (EVIDENCE_CLASS_IMPORTED_STRUCTURED_VALUE, EVIDENCE_CLASS_CALCULATED_VALUE):
            basis = "imported_or_deterministic_calculation"
        elif evidence_class == EVIDENCE_CLASS_AI_GENERATED_PROPOSAL:
            basis = "ai_generated_proposal"
        elif evidence_class == EVIDENCE_CLASS_EXTERNALLY_RESEARCHED:
            basis = "externally_researched"
        else:
            basis = "other_recorded_evidence"

        citation = self.resolve_region_citation(workspace, evidence["region_id"]) if evidence.get("region_id") else None

        edges = self.relationships_for(workspace, OBJECT_KIND_EVIDENCE_ITEM, evidence_item_id, direction="both")
        supporting, contradicting, other = [], [], []
        for edge in edges:
            resolved = self.resolve_relationship_status(workspace, edge["id"])
            entry = {"relationship_id": edge["id"], "relationship_type": edge["relationship_type"], "status": resolved["status"]}
            if edge["relationship_type"] == RELATIONSHIP_TYPE_SUPPORTS:
                supporting.append(entry)
            elif edge["relationship_type"] == RELATIONSHIP_TYPE_CONTRADICTS:
                contradicting.append(entry)
            else:
                other.append(entry)

        observation_ids = {
            e["from_id"] if e["to_type"] == OBJECT_KIND_EVIDENCE_ITEM else e["to_id"]
            for e in edges
            if OBJECT_KIND_DERIVED_OBSERVATION in (e["from_type"], e["to_type"])
        }
        finding_ids = {
            e["from_id"] if e["to_type"] == OBJECT_KIND_EVIDENCE_ITEM else e["to_id"]
            for e in edges
            if OBJECT_KIND_FINDING in (e["from_type"], e["to_type"])
        }

        authority_boundary = (
            "requires_human_authority" if (finding_ids or basis == "ai_generated_proposal") else "informational"
        )

        return {
            "status": "assembled",
            "evidence_item_id": evidence_item_id,
            "basis": basis,
            "evidence_class": evidence_class,
            "content": evidence.get("content"),
            "citation": citation,
            "validation_status": evidence.get("validation_status"),
            "supporting_relationships": supporting,
            "contradicting_relationships": contradicting,
            "other_relationships": other,
            "has_contradictions": len(contradicting) > 0,
            "derived_observation_ids": sorted(observation_ids),
            "finding_ids": sorted(finding_ids),
            "authority_boundary": authority_boundary,
        }

    def explain_investigation_answer(self, workspace: ProjectWorkspace, investigation_step_id: str) -> dict:
        """
        CLAUDE-MM7 Section 5/6: the Trustworthy Answer Contract AND the
        "Why should I trust this?" control - deliberately ONE assembly
        function serving both, since Section 6's own field list
        (classification/anchors/relationship path/version/date/support/
        contradiction/method/uncertainty/review-status/authority
        boundary) is not a second, different contract, just Section 5's
        contract narrowed to what a user-facing drawer actually shows.
        The UI's own progressive disclosure (Section 20: answer+warning,
        then claims+citations, then full evidence+method) reveals more
        of this SAME payload in stages, rather than three separate
        endpoints that could drift apart from each other.

        A pure, read-time AGGREGATION over this investigation step's own
        Claims (no new storage) - matches explain_evidence_trust's own
        doctrine exactly, one level up (an investigation's worth of
        claims, not one evidence item's worth of relationships).
        """
        step = self._find(workspace.investigation_steps, investigation_step_id)
        if step is None or step["project_id"] != workspace.project_id:
            return {"status": "unavailable", "investigation_step_id": investigation_step_id}

        claims = self.claims_for_investigation_step(workspace, investigation_step_id)
        evidence_used, evidence_excluded_all = [], []
        claim_summaries = []
        contradiction_present = False
        stale_present = False
        missing_evidence, recommended_next_checks = [], []
        authority_boundary = "informational"

        for claim in claims:
            resolved = self.resolve_claim_status(workspace, claim["id"])
            citations = [
                self._resolve_mm6_endpoint_summary(workspace, link["object_type"], link["object_id"])
                for link in claim["evidence_links"]
            ]
            for link in claim["evidence_links"]:
                if link not in evidence_used:
                    evidence_used.append(link)
            for excluded in claim.get("evidence_excluded", []):
                if excluded not in evidence_excluded_all:
                    evidence_excluded_all.append(excluded)

            if claim["contradiction_relationship_ids"] or claim["claim_class"] == CLAIM_CLASS_CONFLICTING:
                contradiction_present = True
            if resolved.get("stale"):
                stale_present = True
            if claim["confidence_state"] in (
                CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE, CONFIDENCE_STATE_SPECIALIST_CONFIRMATION_REQUIRED,
            ) or claim["claim_class"] == CLAIM_CLASS_UNKNOWN:
                missing_evidence.append(claim["statement"])
            if claim.get("recommended_next_check"):
                recommended_next_checks.append(claim["recommended_next_check"])
            if (
                claim["claim_class"] == CLAIM_CLASS_DECISION_REQUIRING_AUTHORITY
                or claim["adoption_state"] in (CLAIM_ADOPTION_REQUIRES_SPECIALIST, CLAIM_ADOPTION_REQUIRES_AUTHORITY)
                or claim["author_type"] == OBSERVATION_AUTHOR_AI
            ):
                authority_boundary = "requires_human_authority"

            claim_summaries.append({
                "claim_id": claim["id"],
                "statement": claim["statement"],
                "claim_class": claim["claim_class"],
                "method": claim["method"],
                "confidence_state": claim["confidence_state"],
                "confidence_meaning": CONFIDENCE_STATE_MEANINGS.get(claim["confidence_state"]),
                "assumptions": claim["assumptions"],
                "citations": citations,
                "contradiction_relationship_ids": claim["contradiction_relationship_ids"],
                "author_type": claim["author_type"],
                "created_by": claim["created_by"],
                "created_at": claim["created_at"],
                "status": resolved["status"],
                "adoption_state": claim["adoption_state"],
                "adopted_by": claim.get("adopted_by"),
                "adopted_at": claim.get("adopted_at"),
                "recommended_next_check": claim.get("recommended_next_check"),
                "superseded_by_claim_id": resolved.get("superseded_by_claim_id"),
            })

        return {
            "status": "assembled",
            "investigation_step_id": investigation_step_id,
            "question": step["question"],
            "scope": "case" if step.get("case_id") else "project",
            "case_id": step.get("case_id"),
            "project": workspace.project_id,
            "ran": step["ran"],
            "skipped_reason": step.get("skipped_reason"),
            "evidence_used": evidence_used,
            "evidence_excluded": evidence_excluded_all,
            "claims": claim_summaries,
            "contradiction_state": contradiction_present,
            "freshness_state": "stale_evidence_present" if stale_present else "current",
            "confidence_state_meanings": CONFIDENCE_STATE_MEANINGS,
            "authority_boundary": authority_boundary,
            "missing_evidence": missing_evidence,
            "recommended_next_check": recommended_next_checks,
            "human_adoption_state": {c["claim_id"]: c["adoption_state"] for c in claim_summaries},
        }

    def build_investigation_evidence_sachet(
        self, workspace: ProjectWorkspace, investigation_step_id: str, task_description: Optional[str] = None,
    ) -> dict:
        """
        Section 11: the Governed Evidence Sachet, extended to a whole
        INVESTIGATION - "minimum necessary does not mean minimum
        intelligible." Assembles only the evidence actually cited by
        this investigation's own Claims (never the whole project),
        each with its own citation/version/exclusion accounting, mirroring
        build_relationship_sachet's shape exactly one level up. No
        external connectivity is implemented or referenced here (Section
        11's own explicit boundary). `expiry` is honestly `None` with an
        explanation, not a fabricated timestamp - this sachet is
        reassembled fresh from current state on every call, so it has no
        separate lifetime of its own to expire; a caller wanting a fixed
        snapshot should record one via Snapshot instead.
        """
        step = self._find(workspace.investigation_steps, investigation_step_id)
        if step is None or step["project_id"] != workspace.project_id:
            return {"status": "unavailable", "investigation_step_id": investigation_step_id}

        claims = self.claims_for_investigation_step(workspace, investigation_step_id)
        included, seen = [], set()
        for claim in claims:
            for link in claim["evidence_links"]:
                key = (link["object_type"], link["object_id"])
                if key in seen:
                    continue
                seen.add(key)
                included.append(self._resolve_mm6_endpoint_summary(workspace, link["object_type"], link["object_id"]))

        excluded_reasons = []
        for claim in claims:
            for excluded in claim.get("evidence_excluded", []):
                excluded_reasons.append(excluded)

        return {
            "status": "assembled",
            "task": task_description,
            "investigation_step_id": investigation_step_id,
            "question": step["question"],
            "included": included,
            "included_count": len(included),
            "excluded": {
                "items": excluded_reasons,
                "summary": (
                    f"{len(excluded_reasons)} item(s) explicitly excluded by the investigating claim(s); "
                    "every other object in this project not named above was never examined at all."
                ),
            },
            "expiry": None,
            "expiry_note": (
                "Not persisted - this sachet is assembled fresh from current state on every "
                "call, so it has no separate lifetime of its own to expire."
            ),
        }

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
        self._require_case_not_archived(workspace, thread.get("case_id"))

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

        # Collaboration threshold: only origin == human qualifies - a
        # machine- or system-authored message must never cross the
        # threshold merely because `actor` happens to hold a non-owner
        # name. Only counts if this thread is directly anchored to a Case
        # (thread["case_id"]) - a thread with no Case anchor has nothing
        # to cross the threshold on.
        crossed = False
        if origin == MESSAGE_ORIGIN_HUMAN:
            crossed = self._cross_collaboration_threshold_if_qualifying(
                workspace, thread.get("case_id"), actor, "review_message", message.id,
            )

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
            if crossed:
                governance_log.append(
                    project_id=workspace.project_id, event_type="case_became_collaborative",
                    actor=actor, role="human",
                    payload={
                        "case_id": thread.get("case_id"), "contribution_type": "review_message",
                        "contribution_id": message.id,
                    },
                    correlation_id=thread.get("case_id"),
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
        self._require_case_not_archived(workspace, thread.get("case_id"))

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

        # Attention has no separate machine/human origin field (unlike
        # ReviewMessage), but nothing in this codebase creates one with a
        # machine identity - "this person/role should attend to this
        # matter" has no autonomous-machine analogue here. Only counts if
        # the thread is directly anchored to a Case.
        crossed = self._cross_collaboration_threshold_if_qualifying(
            workspace, thread.get("case_id"), created_by, "attention", attention.id,
        )

        self.save(workspace)

        if crossed and governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="case_became_collaborative",
                actor=created_by, role="human",
                payload={
                    "case_id": thread.get("case_id"), "contribution_type": "attention",
                    "contribution_id": attention.id,
                },
                correlation_id=thread.get("case_id"),
            )

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

        thread = self._find(workspace.review_threads, attention["thread_id"])
        self._require_case_not_archived(workspace, thread.get("case_id") if thread else None)

        attention["status"] = ATTENTION_STATUS_RESPONDED
        attention["responded_message_id"] = response_message_id

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
        self._require_case_not_archived(workspace, thread.get("case_id"))
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
        self._require_case_not_archived(workspace, thread.get("case_id"))
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
        self._require_case_not_archived(workspace, thread.get("case_id"))
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

    def confirm_relationship(
        self, workspace: ProjectWorkspace, relationship_id: str, actor: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """Standalone confirmation for direct use outside a thread outcome
        context - see link_thread_outcome for the atomic, in-transaction
        version used when confirming as part of resolving a thread.

        Collaboration-threshold qualifying event uses confirmed_by, not
        created_by/relationship-creation - a Relationship's created_by can
        be machine-populated (provisional=True Spin output) with no
        structural guarantee it names a real human actor. Confirmation
        (provisional -> False, confirmed_by set) is the one point in this
        object's life that is unambiguously a human act, the same
        Finding-is-machine/ReviewerValidation-is-human split this codebase
        already draws everywhere else. A Relationship carries no case_id
        of its own, so this checks every Case whose Findings/Sources/
        Artifacts the relationship's from_id or to_id actually references.
        """
        relationship = self._find(workspace.relationships, relationship_id)
        if relationship is None:
            raise CaseWorkspaceError(f"Relationship {relationship_id} was not found.")

        referenced_cases = {
            c["id"]: c for c in (
                self._cases_referencing_object(workspace, relationship.get("from_id"))
                + self._cases_referencing_object(workspace, relationship.get("to_id"))
            )
        }
        # Reject if ANY referenced Case is archived - errs toward protecting
        # frozen state even when a Relationship also touches a non-archived
        # Case, rather than trying to partially confirm.
        for case_id in referenced_cases:
            self._require_case_not_archived(workspace, case_id)

        relationship["provisional"] = False
        relationship["confirmed_by"] = actor
        crossed_case_ids = [
            case_id for case_id in referenced_cases
            if self._cross_collaboration_threshold_if_qualifying(
                workspace, case_id, actor, "relationship_confirmation", relationship_id,
            )
        ]

        self.save(workspace)

        if governance_log is not None:
            for case_id in crossed_case_ids:
                governance_log.append(
                    project_id=workspace.project_id, event_type="case_became_collaborative",
                    actor=actor, role="human",
                    payload={
                        "case_id": case_id, "contribution_type": "relationship_confirmation",
                        "contribution_id": relationship_id,
                    },
                    correlation_id=case_id,
                )

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
        Deliberately does NOT participate in any Case's collaboration
        threshold (a documented exclusion, not an oversight): unlike
        ReviewMessage's structural `origin` field, Activity has no way to
        distinguish machine- from human-initiated work ("machine- or
        human-initiated" per this class's own docstring), and has zero
        real callers anywhere in this codebase today to establish a real-
        world convention either way. Counting it would risk exactly the
        false machine-boundary crossing the ratified spec prohibits.
        Revisit if/when Activity gains its own origin field.

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
        self._require_case_not_archived(workspace, case_id)

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
        self._require_case_not_archived(workspace, finding["case_id"])
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

    def update_rfi_draft_question(self, workspace: ProjectWorkspace, draft_id: str, question_text: str) -> dict:
        """
        Editing a draft's own question text - previously inlined directly
        in routes/workspace.py's update_rfi_question route (a mutation
        bypassing the store layer entirely), which meant it was the one
        RFIDraft write path that never called _require_case_not_archived.
        Moved here to close that gap using the same guard every other
        governed write already goes through, not a route-level
        workaround.
        """
        draft = self._find(workspace.rfi_drafts, draft_id)
        if draft is None:
            raise CaseWorkspaceError(f"RFI draft {draft_id} was not found.")
        self._require_case_not_archived(workspace, draft.get("case_id"))

        draft["question_text"] = question_text
        self.save(workspace)
        return draft

    def issue_rfi_draft(self, workspace: ProjectWorkspace, draft_id: str, issued_by: str) -> dict:
        draft = self._find(workspace.rfi_drafts, draft_id)
        if draft is None:
            raise CaseWorkspaceError(f"RFI draft {draft_id} was not found.")
        if draft["status"] == RFI_STATUS_ISSUED:
            raise CaseWorkspaceError("This RFI has already been issued.")
        self._require_case_not_archived(workspace, draft.get("case_id"))

        draft["status"] = RFI_STATUS_ISSUED
        draft["issued_at"] = _now()
        draft["issued_by"] = issued_by
        self.save(workspace)
        return draft

    def respond_to_rfi_draft(
        self, workspace: ProjectWorkspace, draft_id: str, response_text: str, responded_by: str,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        CLAUDE-P30: the Client/Owner-side counterpart to issue_rfi_draft --
        "rfi_respond" in environment_capabilities.py's registry. Requires
        the draft to already be RFI_STATUS_ISSUED (an unissued draft has
        nothing to respond to yet -- the same "response follows issuance"
        rule the real-world exchange this models actually has), and
        refuses outright if a response is already on record: exactly one
        authoritative response per RFI, matching issue_rfi_draft's own
        "already issued" refusal shape.
        """
        draft = self._find(workspace.rfi_drafts, draft_id)
        if draft is None:
            raise CaseWorkspaceError(f"RFI draft {draft_id} was not found.")
        if draft["status"] != RFI_STATUS_ISSUED:
            raise CaseWorkspaceError(
                "This RFI cannot be responded to yet -- it has not been issued."
            )
        self._require_case_not_archived(workspace, draft.get("case_id"))

        if not response_text or not response_text.strip():
            raise CaseWorkspaceError("A response requires response text.")

        draft["response_text"] = response_text.strip()
        draft["responded_at"] = _now()
        draft["responded_by"] = responded_by
        draft["status"] = RFI_STATUS_ANSWERED
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="rfi_answered",
                actor=responded_by, role="human",
                payload={"rfi_draft_id": draft_id},
            )
        return draft

    # -- Snapshot / Freeze / State Comparison (Prompt 14 O/AC, Batch G) ---------

    def create_snapshot(
        self,
        workspace: ProjectWorkspace,
        label: str,
        created_by: str,
        note: Optional[str] = None,
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        Freezes a governed reference to the CURRENT project state. There
        is deliberately no update_snapshot anywhere in this module - a
        Snapshot is immutable from the moment it is created; a later
        correction is always a NEW Snapshot (see the Snapshot dataclass
        docstring for why no Supersession lineage applies here either).
        """
        snapshot = Snapshot(
            id=_new_id(),
            project_id=workspace.project_id,
            label=label,
            project_state_version=workspace.version,
            frozen_at=project_clock_now().isoformat(),
            created_by=created_by,
            reference_lists=_snapshot_reference_lists(workspace),
            note=note,
        )
        workspace.snapshots.append(asdict(snapshot))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="snapshot_created",
                actor=created_by, role="system",
                payload={
                    "snapshot_id": snapshot.id, "label": label,
                    "project_state_version": snapshot.project_state_version,
                },
                correlation_id=snapshot.id,
            )
        return asdict(snapshot)

    def snapshots_for_project(self, workspace: ProjectWorkspace) -> list[dict]:
        return list(workspace.snapshots)

    def get_snapshot(self, workspace: ProjectWorkspace, snapshot_id: str) -> Optional[dict]:
        return self._find(workspace.snapshots, snapshot_id)

    def resolve_snapshot_objects(self, workspace: ProjectWorkspace, snapshot_id: str, list_name: str) -> list[dict]:
        """
        Resolves a frozen Snapshot's ids for `list_name` back to their
        CURRENT records in the live workspace (references, not copies -
        see the Snapshot dataclass docstring for the honest limitation
        this creates for in-place-mutated fields).
        """
        snapshot = self._find(workspace.snapshots, snapshot_id)
        if snapshot is None:
            raise CaseWorkspaceError(f"Snapshot {snapshot_id} was not found.")
        if list_name not in snapshot["reference_lists"]:
            raise CaseWorkspaceError(
                f"'{list_name}' is not a governed list this Snapshot captured. "
                f"Available: {', '.join(sorted(snapshot['reference_lists']))}."
            )
        ids = set(snapshot["reference_lists"][list_name])
        current_items = getattr(workspace, list_name, [])
        return [item for item in current_items if item.get("id") in ids]

    def compare_snapshots(self, workspace: ProjectWorkspace, snapshot_id_a: str, snapshot_id_b: str) -> dict:
        snap_a = self._find(workspace.snapshots, snapshot_id_a)
        snap_b = self._find(workspace.snapshots, snapshot_id_b)
        if snap_a is None:
            raise CaseWorkspaceError(f"Snapshot {snapshot_id_a} was not found.")
        if snap_b is None:
            raise CaseWorkspaceError(f"Snapshot {snapshot_id_b} was not found.")
        return compare_snapshot_reference_lists(snap_a, snap_b)

    # -- Structured Tabular Evidence (Prompt 18 / Batch J) ----------------------

    def register_table_evidence(
        self,
        workspace: ProjectWorkspace,
        source_id: str,
        parsed_table: dict,
        raw_lines: Optional[list[str]] = None,
        extraction_engine: Optional[str] = None,
        extraction_version: Optional[str] = None,
        actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> tuple[dict, list[dict]]:
        """
        Bridges a ParsedDocument.tables entry (BHiveParser's raw headers/
        rows-of-strings, Batch H) into governed Table/TableRow evidence -
        the "STRUCTURED TABULAR EVIDENCE" step in Prompt 18's own diagram.
        Call this once per table worth registering as evidence, rather
        than every consumer reaching into ParsedDocument.tables on its
        own (the exact duplication this batch exists to remove).

        `raw_lines`, if given, lets `section_context` be derived from the
        nearest preceding heading (find_preceding_heading) - optional,
        since not every caller has the full document text on hand.
        """
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        section_context = (
            find_preceding_heading(raw_lines, parsed_table["start_line"]) if raw_lines else None
        )
        table = Table(
            id=_new_id(), project_id=workspace.project_id, source_id=source_id,
            headers=list(parsed_table["headers"]),
            source_location={"start_line": parsed_table["start_line"], "end_line": parsed_table["end_line"]},
            created_at=_now(), created_by=actor,
            section_context=section_context,
            extraction_engine=extraction_engine, extraction_version=extraction_version,
        )
        workspace.tables.append(asdict(table))

        units_by_header = {h: extract_unit_from_header(h) for h in parsed_table["headers"]}
        row_dicts: list[dict] = []
        data_row_start_line = parsed_table["start_line"] + 2  # + header line, + separator line

        # Generic row-identifier column: only the table's OWN first column,
        # and only if its header looks like a conventional row-number/id
        # column - never assumed for a table that doesn't actually have one.
        id_col_index = None
        if parsed_table["headers"] and parsed_table["headers"][0].strip().lower() in ("#", "no", "no.", "item", "row"):
            id_col_index = 0

        for row_index, raw_row in enumerate(parsed_table["rows"]):
            cells = []
            for col_index, header in enumerate(parsed_table["headers"]):
                raw_value = raw_row[col_index] if col_index < len(raw_row) else ""
                parsed_value, qualifier = parse_table_cell_value(raw_value)
                cells.append({
                    "id": _new_id(), "header": header, "raw_value": raw_value,
                    "parsed_value": parsed_value, "qualifier": qualifier,
                    "unit": units_by_header.get(header),
                })
            row = TableRow(
                id=_new_id(), table_id=table.id, project_id=workspace.project_id,
                row_index=row_index, cells=cells, created_at=_now(),
                source_row_identifier=(
                    raw_row[id_col_index].strip()
                    if id_col_index is not None and id_col_index < len(raw_row) else None
                ),
                source_location={"line": data_row_start_line + row_index},
            )
            workspace.table_rows.append(asdict(row))
            row_dicts.append(asdict(row))

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="table_evidence_registered",
                actor=actor, role="system",
                payload={"table_id": table.id, "source_id": source_id, "row_count": len(row_dicts)},
                correlation_id=table.id,
            )
        return asdict(table), row_dicts

    def tables_for_source(self, workspace: ProjectWorkspace, source_id: str) -> list[dict]:
        return [t for t in workspace.tables if t["source_id"] == source_id]

    def get_table(self, workspace: ProjectWorkspace, table_id: str) -> Optional[dict]:
        return self._find(workspace.tables, table_id)

    def rows_for_table(self, workspace: ProjectWorkspace, table_id: str) -> list[dict]:
        return [r for r in workspace.table_rows if r["table_id"] == table_id]

    def get_table_row(self, workspace: ProjectWorkspace, row_id: str) -> Optional[dict]:
        return self._find(workspace.table_rows, row_id)

    def resolve_table_cell(self, workspace: ProjectWorkspace, cell_id: str) -> Optional[dict]:
        """
        Prompt 18 #3: resolves a single cell by its OWN id even though
        cells are embedded within their row (not a separate top-level
        list) - a Relationship can address `to_type="table_cell",
        to_id=<cell id>` and this is how it gets resolved back.
        """
        for row in workspace.table_rows:
            for cell in row["cells"]:
                if cell["id"] == cell_id:
                    return cell
        return None

    def reconcile_table(self, workspace: ProjectWorkspace, table_id: str) -> Optional[dict]:
        """
        Production entry point for Prompt 18 #12/#28: reconciles a
        REGISTERED Table (by id) using its real TableRow evidence, not a
        raw ParsedDocument.tables dict - the caller never needs direct
        access to BHiveParser output for this.
        """
        table = self.get_table(workspace, table_id)
        if table is None:
            raise CaseWorkspaceError(f"Table {table_id} was not found.")
        rows = self.rows_for_table(workspace, table_id)
        return reconcile_table_evidence(table, rows)

    # -- Generic Source-Reference resolution (Prompt 18 / Batch J) -------------

    def extract_and_register_source_references(
        self,
        workspace: ProjectWorkspace,
        source_id: str,
        text: str,
        origin_context: dict,
        known_targets: Optional[dict] = None,
        resolution_method: Optional[str] = None,
        actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> list[dict]:
        """
        Finds every explicit reference in `text` (parse_source_reference_
        text) and persists one governed SourceReference per candidate.
        Resolved against `known_targets` if given (resolve_source_
        reference_candidate); if `known_targets` is omitted entirely, each
        reference is still persisted with resolution_status=UNKNOWN rather
        than silently discarded (Prompt 18 #18) - the original citation
        text and syntactic type are never lost even when nothing is known
        yet about what it might resolve to.
        """
        source = self._find(workspace.sources, source_id)
        if source is None:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        created: list[dict] = []
        for candidate in parse_source_reference_text(text):
            if known_targets is not None:
                resolution = resolve_source_reference_candidate(candidate, known_targets)
            else:
                resolution = {"resolution_status": RESOLUTION_STATUS_UNKNOWN, "resolved_targets": []}

            reference = SourceReference(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                reference_text=candidate["reference_text"],
                reference_type=normalize_open_world_value(candidate["reference_type"], KNOWN_REFERENCE_TYPES),
                resolution_status=resolution["resolution_status"],
                origin_context=origin_context, created_at=_now(), created_by=actor,
                resolved_target_ids=resolution["resolved_targets"],
                resolution_method=resolution_method,
            )
            workspace.source_references.append(asdict(reference))
            created.append(asdict(reference))

            if governance_log is not None:
                event_type = (
                    "source_reference_resolved"
                    if resolution["resolution_status"] in (
                        RESOLUTION_STATUS_RESOLVED_EXACT, RESOLUTION_STATUS_RESOLVED_RANGE,
                        RESOLUTION_STATUS_RESOLVED_MULTIPLE,
                    ) else "source_reference_resolution_failed"
                )
                governance_log.append(
                    project_id=workspace.project_id, event_type=event_type, actor=actor, role="system",
                    payload={
                        "reference_id": reference.id, "reference_text": reference.reference_text,
                        "status": reference.resolution_status,
                    },
                    correlation_id=reference.id,
                )

        if created:
            self.save(workspace)
        return created

    def source_references_for_source(self, workspace: ProjectWorkspace, source_id: str) -> list[dict]:
        return [r for r in workspace.source_references if r["source_id"] == source_id]

    def get_source_reference(self, workspace: ProjectWorkspace, reference_id: str) -> Optional[dict]:
        return self._find(workspace.source_references, reference_id)

    def source_references_to_target(self, workspace: ProjectWorkspace, target_id: str) -> list[dict]:
        """
        Prompt 18 #24: low-level explicit-reference graph traversal -
        every SourceReference whose resolved targets include `target_id`.
        Deliberately separate from the higher-level project semantic
        graph (Relationship) - this is citation-level, not analysis-level.
        """
        return [r for r in workspace.source_references if target_id in r["resolved_target_ids"]]

    # -- CLAUDE-MM1: Multimodal Foundation and Evidence Contract ---------------
    # Every mutation below re-validates each referenced id's own project_id
    # against the calling workspace before acting - the same "cannot cross
    # Project boundaries through crafted identifiers" defense-in-depth
    # CLAUDE-P40-VW9's Folder methods already establish, not a new pattern.

    def create_structural_unit(
        self, workspace: ProjectWorkspace, source_id: str, unit_type: str, order_index: int,
        label: Optional[str] = None, parent_structural_unit_id: Optional[str] = None,
        modality_metadata: Optional[dict] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if parent_structural_unit_id is not None:
            parent = self._find(workspace.structural_units, parent_structural_unit_id)
            if parent is None or parent["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Structural unit {parent_structural_unit_id} was not found.")

        unit = StructuralUnit(
            id=_new_id(), project_id=workspace.project_id, source_id=source_id,
            unit_type=unit_type, order_index=order_index, created_at=_now(), created_by=actor,
            label=label, parent_structural_unit_id=parent_structural_unit_id,
            modality_metadata=dict(modality_metadata) if modality_metadata else {},
        )
        workspace.structural_units.append(asdict(unit))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="structural_unit_created",
                actor=actor, role="system",
                payload={"structural_unit_id": unit.id, "source_id": source_id, "unit_type": unit_type},
                correlation_id=unit.id,
            )
        return asdict(unit)

    def structural_units_for_source(self, workspace: ProjectWorkspace, source_id: str) -> list[dict]:
        return [u for u in workspace.structural_units if u["source_id"] == source_id]

    def get_structural_unit(self, workspace: ProjectWorkspace, unit_id: str) -> Optional[dict]:
        return self._find(workspace.structural_units, unit_id)

    def create_addressable_region(
        self, workspace: ProjectWorkspace, structural_unit_id: str, region_type: str, address: dict,
        parent_region_id: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        unit = self._find(workspace.structural_units, structural_unit_id)
        if unit is None or unit["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Structural unit {structural_unit_id} was not found.")
        if parent_region_id is not None:
            parent = self._find(workspace.addressable_regions, parent_region_id)
            if parent is None or parent["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Addressable region {parent_region_id} was not found.")

        region = AddressableRegion(
            id=_new_id(), project_id=workspace.project_id, structural_unit_id=structural_unit_id,
            region_type=region_type, address=dict(address), created_at=_now(), created_by=actor,
            parent_region_id=parent_region_id,
        )
        workspace.addressable_regions.append(asdict(region))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="addressable_region_created",
                actor=actor, role="system",
                payload={"region_id": region.id, "structural_unit_id": structural_unit_id, "region_type": region_type},
                correlation_id=region.id,
            )
        return asdict(region)

    def regions_for_structural_unit(self, workspace: ProjectWorkspace, structural_unit_id: str) -> list[dict]:
        return [r for r in workspace.addressable_regions if r["structural_unit_id"] == structural_unit_id]

    def get_addressable_region(self, workspace: ProjectWorkspace, region_id: str) -> Optional[dict]:
        return self._find(workspace.addressable_regions, region_id)

    def register_evidence_item(
        self, workspace: ProjectWorkspace, source_id: str, evidence_class: str, content: str, content_type: str,
        region_id: Optional[str] = None, confidence: Optional[float] = None,
        security_classification: Optional[str] = None, extractor_version: Optional[str] = None,
        content_hash: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        `evidence_class` is validated by EvidenceItem.__post_init__ against
        the closed KNOWN_EVIDENCE_CLASSES vocabulary - an unrecognized
        value raises rather than being silently accepted, the one place
        in this whole method this codebase's usual open-world tolerance
        does not apply (see EvidenceItem's own docstring for why).
        """
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")
        if region_id is not None:
            region = self._find(workspace.addressable_regions, region_id)
            if region is None or region["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Addressable region {region_id} was not found.")

        item = EvidenceItem(
            id=_new_id(), project_id=workspace.project_id, source_id=source_id,
            evidence_class=evidence_class, content=content, content_type=content_type,
            created_at=_now(), created_by=actor, region_id=region_id, confidence=confidence,
            security_classification=security_classification, extractor_version=extractor_version,
            content_hash=content_hash,
        )
        workspace.evidence_items.append(asdict(item))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="evidence_item_registered",
                actor=actor, role="system",
                payload={"evidence_item_id": item.id, "source_id": source_id, "evidence_class": evidence_class},
                correlation_id=item.id,
            )
        return asdict(item)

    def evidence_items_for_source(self, workspace: ProjectWorkspace, source_id: str) -> list[dict]:
        return [e for e in workspace.evidence_items if e["source_id"] == source_id]

    def get_evidence_item(self, workspace: ProjectWorkspace, evidence_item_id: str) -> Optional[dict]:
        return self._find(workspace.evidence_items, evidence_item_id)

    def record_derived_observation(
        self, workspace: ProjectWorkspace, statement: str, author_type: str, author: str, method: str,
        supporting_evidence_ids: Optional[list[str]] = None, case_id: Optional[str] = None,
        confidence: Optional[float] = None, related_analysis_id: Optional[str] = None,
        actor: str = "system", governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        `author_type` is validated by DerivedObservation.__post_init__
        against the closed KNOWN_OBSERVATION_AUTHOR_TYPES vocabulary, the
        same discipline register_evidence_item applies to evidence_class.
        Every id in `supporting_evidence_ids` must already exist as a real
        EvidenceItem in THIS project - an observation can never cite
        evidence that doesn't exist or belongs to another project, the
        same defense-in-depth every other cross-reference in this module
        applies.
        """
        evidence_ids = list(supporting_evidence_ids or [])
        for evidence_id in evidence_ids:
            evidence = self._find(workspace.evidence_items, evidence_id)
            if evidence is None or evidence["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Evidence item {evidence_id} was not found.")
        if case_id is not None:
            case = self._find(workspace.cases, case_id)
            if case is None or case["project_id"] != workspace.project_id:
                raise CaseWorkspaceError(f"Case {case_id} was not found.")

        observation = DerivedObservation(
            id=_new_id(), project_id=workspace.project_id, statement=statement,
            author_type=author_type, author=author, method=method, created_at=_now(),
            supporting_evidence_ids=evidence_ids, case_id=case_id, confidence=confidence,
            related_analysis_id=related_analysis_id,
        )
        workspace.derived_observations.append(asdict(observation))
        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="derived_observation_recorded",
                actor=actor, role="system",
                payload={
                    "derived_observation_id": observation.id, "author_type": author_type,
                    "supporting_evidence_ids": evidence_ids,
                },
                correlation_id=observation.id,
            )
        return asdict(observation)

    def get_derived_observation(self, workspace: ProjectWorkspace, observation_id: str) -> Optional[dict]:
        return self._find(workspace.derived_observations, observation_id)

    def resolve_region_citation(self, workspace: ProjectWorkspace, region_id: str) -> dict:
        """
        The citation contract (Section 7): a stable internal anchor
        (`region_id` itself, unaffected by rename/relabel) resolved into a
        human-readable rendering at READ time, never stored - the same
        "store flat, derive structure at read time" convention Folder's
        own path resolution and resolve_conversation_anchor already use.
        Returns `{"status": "resolved", "label", "region_id",
        "structural_unit_id", "source_id", "region_type", "address"}` on
        success, or `{"status": "unavailable", "region_id"}` when the
        region, its unit, or its Source can no longer be found or has
        been removed - an honest broken-anchor state, never a fabricated
        label. Full source-version-aware staleness detection (Section 8)
        is a deferred future extension, not attempted here - see this
        stage's own documentation.
        """
        region = self._find(workspace.addressable_regions, region_id)
        if region is None or region["project_id"] != workspace.project_id:
            return {"status": "unavailable", "region_id": region_id}

        unit = self._find(workspace.structural_units, region["structural_unit_id"])
        if unit is None or unit["project_id"] != workspace.project_id:
            return {"status": "unavailable", "region_id": region_id}

        source = self._find(workspace.sources, unit["source_id"])
        if source is None or source["project_id"] != workspace.project_id or source.get("removed_at"):
            return {"status": "unavailable", "region_id": region_id}

        unit_label = unit.get("label") or f"{unit['unit_type']} {unit['order_index']}"
        address_label = _render_region_address_label(region["region_type"], region["address"])
        label_parts = [source["name"], unit_label]
        if address_label:
            label_parts.append(address_label)

        result = {
            # CLAUDE-MM2 (Section 13): "preserved old citation" - a region
            # anchored to a Source that has since been superseded is still
            # resolved (the old evidence and its citation remain readable,
            # never silently invalidated), just explicitly flagged stale
            # via the EXISTING Source.superseded_by_source_id pointer
            # (register_source_revision, drawings-only today) - no new
            # version mechanism, no full redline comparison.
            "status": "stale" if source.get("superseded_by_source_id") else "resolved",
            "label": " · ".join(label_parts),
            "region_id": region["id"],
            "structural_unit_id": unit["id"],
            "source_id": source["id"],
            "region_type": region["region_type"],
            "address": region["address"],
        }
        if source.get("superseded_by_source_id"):
            result["superseded_by_source_id"] = source["superseded_by_source_id"]
        return result

    # -- CLAUDE-MM2: PDF and Document Intelligence ------------------------------
    # Mirrors register_table_evidence's own shape (Batch J, above): takes
    # ALREADY-EXTRACTED per-page text, never raw bytes or a pypdf call -
    # this module still does not import services/bhive_parser.py (see
    # promote_requirement_item's own docstring on why). The actual pypdf
    # read, and the encrypted/malformed classification only a failed READ
    # can produce, live in services/pdf_intelligence.py, a thin caller that
    # does the extraction and then calls this method with its result.

    def register_pdf_page_structure(
        self, workspace: ProjectWorkspace, source_id: str, pages: list[str],
        extractor_version: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        One StructuralUnit per PDF page (`unit_type="page"`, stable page
        index/label) unconditionally - a page's identity and existence are
        real regardless of whether it carries a text layer (Section 11:
        "do not claim 'no usable document' merely because text is
        absent" - an image-only page is still a real, addressable page).
        For any page with real (non-whitespace) text, additionally splits
        it into paragraphs (blank-line-delimited - deterministic, no NLP)
        and registers one AddressableRegion + one EvidenceItem per non-
        empty paragraph, each carrying its own page/paragraph address for
        `_render_region_address_label`'s "page N · paragraph M" rendering.

        Returns `{"classification", "page_count", "structural_unit_ids",
        "addressable_region_ids", "evidence_item_ids"}` - `classification`
        is one of PDF_CLASSIFICATION_TEXT_NATIVE/IMAGE_ONLY/MIXED (never
        the two failure states - those only ever come from a failed READ,
        handled entirely in services/pdf_intelligence.py before this
        method is ever called with a real `pages` list).
        """
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        structural_unit_ids: list[str] = []
        addressable_region_ids: list[str] = []
        evidence_item_ids: list[str] = []
        pages_with_text = 0

        for page_index, page_text in enumerate(pages):
            unit = StructuralUnit(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                unit_type="page", order_index=page_index, created_at=_now(), created_by=actor,
                label=f"Page {page_index + 1}",
            )
            workspace.structural_units.append(asdict(unit))
            structural_unit_ids.append(unit.id)

            paragraphs = [p.strip() for p in re.split(r"\n\s*\n", page_text) if p.strip()]
            if paragraphs:
                pages_with_text += 1
            for paragraph_index, paragraph_text in enumerate(paragraphs):
                region = AddressableRegion(
                    id=_new_id(), project_id=workspace.project_id, structural_unit_id=unit.id,
                    region_type="paragraph",
                    address={"page_index": page_index, "paragraph_index": paragraph_index},
                    created_at=_now(), created_by=actor,
                )
                workspace.addressable_regions.append(asdict(region))
                addressable_region_ids.append(region.id)

                evidence = EvidenceItem(
                    id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                    evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content=paragraph_text,
                    content_type="text", created_at=_now(), created_by=actor,
                    region_id=region.id, extractor_version=extractor_version,
                )
                workspace.evidence_items.append(asdict(evidence))
                evidence_item_ids.append(evidence.id)

        if pages_with_text == 0:
            classification = PDF_CLASSIFICATION_IMAGE_ONLY
        elif pages_with_text == len(pages):
            classification = PDF_CLASSIFICATION_TEXT_NATIVE
        else:
            classification = PDF_CLASSIFICATION_MIXED

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="pdf_page_structure_registered",
                actor=actor, role="system",
                payload={
                    "source_id": source_id, "classification": classification,
                    "page_count": len(pages), "evidence_item_count": len(evidence_item_ids),
                },
                correlation_id=source_id,
            )

        return {
            "classification": classification,
            "page_count": len(pages),
            "structural_unit_ids": structural_unit_ids,
            "addressable_region_ids": addressable_region_ids,
            "evidence_item_ids": evidence_item_ids,
        }

    def register_plain_text_structure(
        self, workspace: ProjectWorkspace, source_id: str, text: str,
        extractor_version: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        CLAUDE-CA1D-RECEPTION-FIX-01 (folder establishment): the non-PDF
        counterpart to register_pdf_page_structure above, for a Source
        whose real, addressable subdivision is "the document" itself
        rather than pages (.txt/.csv/.md/.docx - anything BHiveParser's
        own _extract already reduces to one plain-text string). One
        StructuralUnit (unit_type="document", order_index=0) covering
        the whole Source, then one AddressableRegion + EvidenceItem per
        non-empty paragraph - the identical blank-line-delimited split
        register_pdf_page_structure uses per page, applied once to the
        whole document instead of once per page. Exists so a Source
        added outside the founding-document path (e.g. every other file
        in a folder establishment) has real, per-paragraph evidence GO's
        chat can actually draw on - not merely a registered filename.
        """
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        unit = StructuralUnit(
            id=_new_id(), project_id=workspace.project_id, source_id=source_id,
            unit_type="document", order_index=0, created_at=_now(), created_by=actor,
        )
        workspace.structural_units.append(asdict(unit))

        addressable_region_ids: list[str] = []
        evidence_item_ids: list[str] = []
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        for paragraph_index, paragraph_text in enumerate(paragraphs):
            region = AddressableRegion(
                id=_new_id(), project_id=workspace.project_id, structural_unit_id=unit.id,
                region_type="paragraph", address={"paragraph_index": paragraph_index},
                created_at=_now(), created_by=actor,
            )
            workspace.addressable_regions.append(asdict(region))
            addressable_region_ids.append(region.id)

            evidence = EvidenceItem(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content=paragraph_text,
                content_type="text", created_at=_now(), created_by=actor,
                region_id=region.id, extractor_version=extractor_version,
            )
            workspace.evidence_items.append(asdict(evidence))
            evidence_item_ids.append(evidence.id)

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="plain_text_structure_registered",
                actor=actor, role="system",
                payload={"source_id": source_id, "paragraph_count": len(paragraphs)},
                correlation_id=source_id,
            )

        return {
            "paragraph_count": len(paragraphs),
            "structural_unit_id": unit.id,
            "addressable_region_ids": addressable_region_ids,
            "evidence_item_ids": evidence_item_ids,
        }

    # -- CLAUDE-MM3: Spreadsheet and Structured-Data Intelligence --------------
    # Mirrors register_pdf_page_structure's own shape exactly: takes ALREADY-
    # EXTRACTED sheet data (never raw bytes, never an openpyxl/csv call) -
    # this module still does not import services/spreadsheet_intelligence.py
    # or openpyxl, the same decoupling promote_requirement_item() and MM2's
    # register_pdf_page_structure both already establish. Reuses the exact
    # same StructuralUnit/AddressableRegion/EvidenceItem primitives MM1
    # defined and MM2 already realized for PDF pages/paragraphs - a
    # worksheet IS a StructuralUnit (unit_type="worksheet"), a row IS an
    # AddressableRegion (region_type="row") - no new domain objects needed.

    def register_spreadsheet_structure(
        self, workspace: ProjectWorkspace, source_id: str, sheets: list[dict],
        extractor_version: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        `sheets` shape (produced by services/spreadsheet_intelligence.py,
        already bounded/truncated there - this method trusts its input
        exactly like register_pdf_page_structure trusts its `pages` list):
        `[{"name", "index", "visible", "row_count", "column_count",
        "truncated", "rows": [{"row_index", "cells": {col_letter: {"value",
        "formula", "cached_value", "data_type"}}}]}]`.

        One StructuralUnit per sheet unconditionally (a hidden or empty
        sheet is still real and addressable - the same "do not claim no
        usable document merely because content is sparse" principle MM2's
        image-only PDF pages already established). One AddressableRegion +
        EvidenceItem per row actually present in the (already-bounded)
        `rows` list - `region.address` carries the row's own cell values
        as real structured data (a dict, not just a citation label), since
        AddressableRegion.address has always been a free-form dict; the
        EvidenceItem's own `content` is a human-readable rendering of the
        same row, never a second, potentially-drifting copy of the values.
        """
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        structural_unit_ids: list[str] = []
        addressable_region_ids: list[str] = []
        evidence_item_ids: list[str] = []

        for sheet in sheets:
            unit = StructuralUnit(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                unit_type="worksheet", order_index=sheet["index"], created_at=_now(), created_by=actor,
                label=sheet["name"],
                modality_metadata={
                    "visible": sheet.get("visible", True),
                    "row_count": sheet.get("row_count", 0),
                    "column_count": sheet.get("column_count", 0),
                    "truncated": sheet.get("truncated", False),
                },
            )
            workspace.structural_units.append(asdict(unit))
            structural_unit_ids.append(unit.id)

            for row in sheet.get("rows", []):
                row_index = row["row_index"]
                cells = row.get("cells", {})
                region = AddressableRegion(
                    id=_new_id(), project_id=workspace.project_id, structural_unit_id=unit.id,
                    region_type="row",
                    address={
                        "row_index": row_index, "sheet_name": sheet["name"],
                        "label": f"row {row_index}", "cells": cells,
                    },
                    created_at=_now(), created_by=actor,
                )
                workspace.addressable_regions.append(asdict(region))
                addressable_region_ids.append(region.id)

                rendered = "; ".join(
                    f"{col}={info.get('value')!r}" for col, info in cells.items()
                )
                evidence = EvidenceItem(
                    id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                    evidence_class=EVIDENCE_CLASS_DIRECT_SOURCE, content=rendered,
                    content_type="spreadsheet_row", created_at=_now(), created_by=actor,
                    region_id=region.id, extractor_version=extractor_version,
                )
                workspace.evidence_items.append(asdict(evidence))
                evidence_item_ids.append(evidence.id)

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="spreadsheet_structure_registered",
                actor=actor, role="system",
                payload={
                    "source_id": source_id, "sheet_count": len(sheets),
                    "evidence_item_count": len(evidence_item_ids),
                },
                correlation_id=source_id,
            )

        return {
            "sheet_count": len(sheets),
            "structural_unit_ids": structural_unit_ids,
            "addressable_region_ids": addressable_region_ids,
            "evidence_item_ids": evidence_item_ids,
        }

    def create_addressable_cell_region(
        self, workspace: ProjectWorkspace, structural_unit_id: str, sheet_name: str, cell_ref: str,
        value, actor: str = "system", governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        A single-cell AddressableRegion, distinct from the per-row regions
        register_spreadsheet_structure creates in bulk - the direct answer
        to Section 6's own "support at least: cell" requirement and
        Section 18's "create direct evidence from at least one cell." Not
        created automatically for every cell in every row (that would
        multiply region/evidence records by the sheet's own column count
        for no proven benefit yet - the existing per-row region already
        carries every cell's value in its own `address["cells"]`); this
        method exists for the caller (a route, a future UI action) that
        needs one SPECIFIC cell to be its own first-class, individually-
        citable anchor.
        """
        unit = self._find(workspace.structural_units, structural_unit_id)
        if unit is None or unit["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Structural unit {structural_unit_id} was not found.")

        region = self.create_addressable_region(
            workspace, structural_unit_id=structural_unit_id, region_type="cell",
            address={"sheet_name": sheet_name, "cell_ref": cell_ref, "label": f"cell {cell_ref}", "value": value},
            actor=actor, governance_log=governance_log,
        )
        return region

    # -- CLAUDE-MM4: Drawing Intelligence and Orientation-Normalized ------------
    # Comparison. Mirrors register_pdf_page_structure's/register_spreadsheet_
    # structure's own shape exactly: takes ALREADY-EXTRACTED per-sheet data
    # (never raw bytes, never a pypdf/PIL call) - this module still does not
    # import services/drawing_intelligence.py, the same decoupling every
    # prior MM stage's own registration method already establishes. A
    # drawing sheet IS a StructuralUnit (unit_type="sheet") - no new domain
    # object needed. Deliberately does NOT auto-create AddressableRegions
    # the way MM2's paragraphs/MM3's rows do: a drawing sheet has no natural
    # sub-structure to enumerate automatically (Section 6: "do not invent
    # sheet numbers or titles when they cannot be extracted reliably" -
    # the same honesty applies to regions, which only a human reviewer can
    # meaningfully place). See create_addressable_drawing_region below for
    # the on-demand, reviewer-driven region path.

    def register_drawing_sheet_structure(
        self, workspace: ProjectWorkspace, source_id: str, sheets: list[dict],
        extractor_version: Optional[str] = None, actor: str = "system",
        governance_log: Optional[GovernanceLog] = None, unit_type: str = "sheet",
    ) -> dict:
        """
        `sheets` shape (produced by services/drawing_intelligence.py):
        `[{"index", "label", "width", "height", "source_rotation",
        "metadata": {field_name: {"value", "reliability", "evidence_snippet",
        "source_page"}}}]` - `metadata`'s own per-field shape is Section
        10's own required classification (directly_extracted/user_entered/
        inferred/unavailable/unverified - KNOWN_METADATA_RELIABILITY_TIERS),
        never a bare value with no reliability tag. `width`/`height` are the
        sheet's own pixel/point dimensions in its ORIGINAL, unrotated,
        unmirrored orientation - the same frame every AddressableRegion this
        sheet ever gets is anchored in (see create_addressable_drawing_region
        and services/drawing_intelligence.py's coordinate-transform module).
        `source_rotation` is the PDF page's own baked-in `/Rotate` value (0
        for a raster image, always) - a fact ABOUT the source file itself,
        distinct from the reviewer's own view-only rotation/mirror state,
        which this method never stores (Section 7: "transformation state...
        must not silently alter the source" - there is nothing here for a
        view transform to even write to).

        One StructuralUnit per sheet unconditionally - the same "a sheet is
        real and addressable even with no extractable title-block metadata"
        principle MM2's image-only PDF pages already established (Section 6:
        "do not invent sheet numbers or titles... when they cannot be
        extracted reliably" - an honestly-empty metadata dict is preferred
        over a guessed one).

        `unit_type` defaults to "sheet" (MM4's own drawing-set vocabulary)
        but CLAUDE-MM5's own `services/image_intelligence.py` passes
        `unit_type="image"` for an ordinary photo/screenshot/Eye capture -
        Section 6's own distinct vocabulary ("image; frame; page rendering;
        screenshot; camera capture") for a genuinely different kind of
        Source, reusing this SAME method (and therefore the SAME
        AddressableRegion/EvidenceItem/citation machinery below) rather
        than a parallel, duplicated registration path. Every other field
        in `sheets` keeps its MM4 meaning unchanged regardless of
        `unit_type` - a photo simply always has exactly one entry in that
        list (Section 6: "one stable image-frame structural unit is
        sufficient"), never a per-page loop.
        """
        source = self._find(workspace.sources, source_id)
        if source is None or source["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Source {source_id} was not found.")

        structural_unit_ids: list[str] = []
        for sheet in sheets:
            unit = StructuralUnit(
                id=_new_id(), project_id=workspace.project_id, source_id=source_id,
                unit_type=unit_type, order_index=sheet["index"], created_at=_now(), created_by=actor,
                label=sheet.get("label") or f"{unit_type.capitalize()} {sheet['index'] + 1}",
                modality_metadata={
                    "width": sheet.get("width"),
                    "height": sheet.get("height"),
                    "source_rotation": sheet.get("source_rotation", 0),
                    "fields": sheet.get("metadata", {}),
                },
            )
            workspace.structural_units.append(asdict(unit))
            structural_unit_ids.append(unit.id)

        self.save(workspace)

        if governance_log is not None:
            governance_log.append(
                project_id=workspace.project_id, event_type="drawing_sheet_structure_registered",
                actor=actor, role="system",
                payload={"source_id": source_id, "sheet_count": len(sheets)},
                correlation_id=source_id,
            )

        return {
            "sheet_count": len(sheets),
            "structural_unit_ids": structural_unit_ids,
        }

    def create_addressable_drawing_region(
        self, workspace: ProjectWorkspace, structural_unit_id: str,
        x: float, y: float, width: float, height: float,
        actor: str = "system", governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        A rectangular AddressableRegion (Section 6: "support at least...
        rectangular region") anchored to a drawing sheet's ORIGINAL,
        unrotated, unmirrored coordinate frame - `x`/`y`/`width`/`height`
        are all normalized 0-1 fractions of the sheet's own stored
        width/height (register_drawing_sheet_structure's own `modality_
        metadata`), the same convention MM3's spreadsheet cells and this
        module's own pre-MM1 Artifact.crop already use for image regions.
        Callers (services/drawing_intelligence.py's own coordinate-
        transform functions) are responsible for converting a reviewer's
        on-screen, possibly-rotated-or-mirrored selection BACK into this
        original frame before calling this method - this method itself
        performs no transform math, only bounds validation, matching the
        "store flat" principle every other MM1-MM4 write path already
        follows.

        `region_index` is a stable, 1-based, per-StructuralUnit sequential
        position - assigned once here from a simple count of this unit's
        existing regions, NEVER renumbered later (a subsequently-deleted
        region would leave a gap, not a collision - this codebase has no
        region-deletion path yet, so the gap case does not currently
        arise, but the assignment rule itself is written to be safe if one
        is ever added).
        """
        unit = self._find(workspace.structural_units, structural_unit_id)
        if unit is None or unit["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Structural unit {structural_unit_id} was not found.")

        for name, value in (("x", x), ("y", y), ("width", width), ("height", height)):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise CaseWorkspaceError(f"Region '{name}' must be a number.")
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise CaseWorkspaceError("Region x/y must be normalized fractions between 0 and 1.")
        if width <= 0 or height <= 0:
            raise CaseWorkspaceError("Region width/height must be positive.")
        if x + width > 1 + 1e-9 or y + height > 1 + 1e-9:
            raise CaseWorkspaceError("Region extends past the sheet's own bounds.")

        existing_count = len(self.regions_for_structural_unit(workspace, structural_unit_id))
        region = self.create_addressable_region(
            workspace, structural_unit_id=structural_unit_id, region_type="rectangular",
            address={
                "x": x, "y": y, "width": width, "height": height,
                "region_index": existing_count + 1,
            },
            actor=actor, governance_log=governance_log,
        )
        return region

    def create_addressable_marker_region(
        self, workspace: ProjectWorkspace, structural_unit_id: str,
        x: float, y: float, actor: str = "system", governance_log: Optional[GovernanceLog] = None,
    ) -> dict:
        """
        CLAUDE-MM5 Section 13: a POINT AddressableRegion (`region_type=
        "marker"`) - the one bounded annotation shape this stage
        implements ("marker/pin... Defer a full markup editor"). Same
        ORIGINAL-frame, bounds-validated, sequential-region_index
        discipline as create_addressable_drawing_region above, just with
        no width/height (a marker has no spatial extent, only a point).
        The marker's own text note is NOT stored here - it lives in the
        accompanying EvidenceItem (evidence_class=USER_ENTERED), the same
        "region records geometry, evidence records content" split every
        other MM1-MM4 region type already follows.
        """
        unit = self._find(workspace.structural_units, structural_unit_id)
        if unit is None or unit["project_id"] != workspace.project_id:
            raise CaseWorkspaceError(f"Structural unit {structural_unit_id} was not found.")

        for name, value in (("x", x), ("y", y)):
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise CaseWorkspaceError(f"Marker '{name}' must be a number.")
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise CaseWorkspaceError("Marker x/y must be normalized fractions between 0 and 1.")

        existing_count = len(self.regions_for_structural_unit(workspace, structural_unit_id))
        region = self.create_addressable_region(
            workspace, structural_unit_id=structural_unit_id, region_type="marker",
            address={"x": x, "y": y, "region_index": existing_count + 1},
            actor=actor, governance_log=governance_log,
        )
        return region

    def build_evidence_sachet(
        self, workspace: ProjectWorkspace, region_id: str, task_description: Optional[str] = None,
    ) -> dict:
        """
        CLAUDE-MM4 Section 14: the Governed Evidence Sachet - "Archiosk
        does not pour the whole project into every question. It steeps
        only the minimum necessary evidence through a governed,
        selectively permeable boundary." A pure, read-time ASSEMBLY of
        already-governed MM1 records (this StructuralUnit, this Region,
        its sibling regions on the SAME sheet only, its citation, and the
        owning Source's own sensitivity classification) into one allow-
        listed packet - no new persisted object, no external call, the
        same "derive at read time" convention resolve_region_citation
        already uses. Deliberately excludes every OTHER sheet and every
        OTHER source in the project (`excluded_summary` records the counts
        so the packet is honest about what it left out - "minimum
        necessary does not mean minimum intelligible": the sibling
        regions and the sheet's own title-block metadata are INCLUDED
        specifically so a detail is never detached from its sheet).

        Returns `{"status": "unavailable", "region_id"}` for a broken
        anchor (same honest shape resolve_region_citation already uses),
        or the assembled packet dict on success. Raises nothing - a
        missing task_description is simply carried through as None.
        """
        citation = self.resolve_region_citation(workspace, region_id)
        if citation["status"] == "unavailable":
            return {"status": "unavailable", "region_id": region_id}

        region = self._find(workspace.addressable_regions, region_id)
        unit = self._find(workspace.structural_units, citation["structural_unit_id"])
        source = self._find(workspace.sources, citation["source_id"])

        sibling_regions = [
            {"region_id": r["id"], "region_type": r["region_type"],
             "label": _render_region_address_label(r["region_type"], r["address"])}
            for r in self.regions_for_structural_unit(workspace, unit["id"])
            if r["id"] != region_id
        ]
        total_sheets = len([u for u in workspace.structural_units if u["source_id"] == source["id"]])

        return {
            "status": "assembled",
            "task": task_description,
            "citation": citation["label"],
            "sheet": {
                "structural_unit_id": unit["id"],
                "label": unit.get("label"),
                "unit_type": unit["unit_type"],
                "fields": unit.get("modality_metadata", {}).get("fields", {}),
            },
            "region": {
                "region_id": region["id"],
                "region_type": region["region_type"],
                "address": region["address"],
            },
            "nearby_regions": sibling_regions,
            "source": {
                "source_id": source["id"],
                "name": source["name"],
                "security_classification": source.get("security_classification"),
                "version_status": citation["status"],
            },
            "excluded": {
                "summary": (
                    f"{max(total_sheets - 1, 0)} other sheet(s) and "
                    f"{len(sibling_regions)} sibling region(s) on this sheet were named but not "
                    f"expanded; every other source in this project was excluded entirely."
                ),
            },
        }
