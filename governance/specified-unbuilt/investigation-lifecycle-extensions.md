# Specified But Unbuilt — Investigation Lifecycle Extensions and Deficiency

**Status:** Specified, not implemented. Extends the implemented `Case`/`CaseRecord` (see `current/kernel-object-model.md`).

## Lifecycle

Private → explicit Share/Publish → Shared → (first governed, non-owner-attributed contribution) → Collaborative → Archive.

**Collaboration threshold, precisely enumerated:** fires on the first governed write by an actor other than the owner, from any of: `ReviewMessage.actor`, `Relationship.created_by` (referencing this Case's Findings/Sources), `ReviewerValidation.reviewer`, `Disposition.reviewer`, `AnalysisTrigger.triggered_by_actor` (for analyses attached to this case), non-owner `Attention` creation on a thread anchored to this Case, non-owner `Activity.created_by` attached to this case. Explicitly excluded: mere viewing (never tracked at all, by anti-surveillance design); `Snapshot` creation by a non-owner (project-wide, not investigation-specific — including it would repeat the exact category error this list exists to avoid). One deliberately-flagged boundary case, not silently resolved: a non-owner adjudicating a Requirement whose evidence references this Case's Findings — recommended *not* to count, but named as needing an explicit decision, not a silent default.

Pre-threshold: owner may retract Shared→Private. Post-threshold: prohibited — this preserves shared provenance, not authorship (constitutional invariant 12).

**Archive is terminal (constitutional invariant 13).** Readable/searchable/citable/comparable/exportable/derivable; never receives new comments, findings, relationships, evidence, or adjudications. "Reopen an archived Case" does not survive as a concept — removed from the model entirely. New reasoning requires **Derive** (`derived_from_investigation_id` — chosen over "Copy"/"Adopt" specifically because it's ownership-neutral, correct whether the same owner extends their own scope or a different reviewer takes over frozen work): new permanent identity, explicit lineage, source unchanged forever.

**`CaseLock`, relocated off Archive entirely.** A temporary, reversible write-suspension on an *active* Case only (e.g., during managerial review) — always PM/authorized-role-gated. Archived material cannot be locked; there's nothing left to suspend that isn't already permanently frozen. "Unlock" is the only surviving relative of "reopen," and it never applies to archived material.

**Authority, not assumed unilateral:** before the collaboration threshold, the owner retains full control. After it, Archive requires PM/authorized-role authority — archiving collaborated-on work affects other contributors, not just the owner, and letting one person decide unilaterally would repeat the "no silent authority selection" failure this model rejects elsewhere. Lock/Unlock are always PM-gated, regardless of collaboration state, since Lock's entire purpose is inherently managerial. Copy/Derive authority is gated only by ordinary read/visibility access to the source — no additional tier, since the source is never mutated by being derived from.

## Publication anchoring

Two separate mechanisms at two separate grains, deliberately not one overloaded mechanism: **(A)** a cheap, Case-scoped content-plus-`project_state_version` anchor, captured at every Share/Publish act — proportional to the investigation's own size. **(B)** the full project `Snapshot`, decoupled from per-share frequency — optional, prompted, or maintained on an independent cadence, never triggered automatically by every individual share (a full-project Snapshot on every share would be proportional to total project size, not the shared item, and was tested and rejected for exactly that reason).

## Deficiency / completion-resolution

A distinct, thin kernel primitive (not a Finding-status extension, not a Disposition/RequirementAdjudication variant) — tested precisely: those three answer "what was observed," "what happens to this Finding," and "does evidence satisfy this Requirement" respectively; Deficiency additionally answers "who must correct it, by when, how was it corrected, who verified it, is it closed" — a multi-step, two-actor-role, due-date-bearing lifecycle none of the three existing objects are shaped for.

Composes from existing primitives rather than duplicating them: `Relationship` (link to originating Finding/Requirement/spec), `TemporalObligation` (correction due-dates), and an **append-only event sequence with a derived current status** — the same discipline behind `review_state_for_finding`/`requirement_adjudication_state` — rather than a mutable open/closed field. Minimum lifecycle: Identified → (Correction Required) → Correction Submitted → Verification Attempted → Verified/Accepted **or** Verification Failed (loops back, prior attempts preserved, never erased) → Closed (explicit, authorized act).

**Substantial Completion, Occupancy/Turnover, and Final Completion are distinct milestone events**, not derived from deficiency-count math and not hard-coded legal definitions — each grounded in an actual certificate/notice `Source` document, with Contract DNA offering only an expected template (never the actual date or criteria). A project may reach Substantial Completion, and later Occupancy, with an open Deficiency list; this is not a gap, it's the documented reality this design deliberately accommodates.

Unresolved deficiencies transition (non-destructively — marked transitioned, not falsely closed) into seasonal/warranty `TemporalObligation`s, or, where the delivery model requires it, link toward an eventual Maintenance Obligation — a **connection point only**, via `Relationship`'s already-open-world nature, not a design of the Machine Model layer (see `deferred-reserved/reservations.md`).

BEEHIVE should eventually answer deficiency-completion questions (how many remain, which are material, which block milestones, which are overdue) with **factors kept individually visible, never collapsed into a single project-health score** — the same discipline already required for `ViabilityAssessment`.

## `promote_requirement_item()` — finalized design contract, implementation not authorized

Bridges `RequirementItem` (legacy extraction pipeline) into the governed `Requirement` primitive, using the already-existing, previously-unused `REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED` registration method. The contract, finalized this engagement: promotion must not discard confidence, reasoning, triggering condition, or provenance. Concretely, promotion should **create or link an accompanying `Finding`** carrying the extraction confidence and an explicit `AnalysisTrigger` (`ANALYSIS_TRIGGER_USER_INITIATED`/`AGENT_INITIATED`), and the promoting actor must **actively assert** a real `source_id` — never inherit one implicitly — satisfying the no-silent-provenance-fabrication discipline established this session. This design is complete. Implementation remains not authorized (see `STATUS.md`).
