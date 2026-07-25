# BEEHIVE Governance Baseline — STATUS

**This is the mandatory first read for any future session, human or AI, working on ARCHIOSK/BEEHIVE.**

**Placement notice:** this baseline was authored in a staging area and, on explicit authorization, committed here at `governance/` in this repository (`C:\Archiosk\Research\archiosk`, the backend repo) as a documentation-only commit. This is its interim live home, not necessarily its final one — the ratified target architecture envisions a single consolidated repository (`backend/` + `explorer/` + `governance/`), and repository consolidation itself remains separately unauthorized and frozen (see the authorization table below). Nothing in `C:\Archiosk\App\archiosk-explorer` was touched, moved, or merged to produce this placement — its historic governance corpus remains exactly where it is; see `history-mapping.md` for the full inventory and mapping.

---

## What BEEHIVE is

BEEHIVE is a governed project-development intelligence environment that accompanies a construction/infrastructure project through its lifecycle — from earliest conception through procurement, contractual commitment, design, construction, and, where the delivery model requires it, operations and handback — while preserving provenance, authority, temporal state, project isolation, and human decision rights at every stage. It is not inherently an Owner application or a Proponent application.

A particular project's governed environment emerges from: **BEEHIVE Constitutional Kernel + Perspective + Contract/Delivery DNA + Project-Specific Governed Sources.**

**BEEHIVE is a user-facing project application, not a governance-document interface.** An ordinary authorized user creates a project, works in it, saves, and reopens it later — conceptually comparable to how modern AI applications let a user create and reopen a persistent Project — with all of the governance/provenance/authority/lifecycle machinery described in this baseline operating underneath that experience, never as something a user must read, understand, or manually manipulate to do ordinary project work. See `specified-unbuilt/perspective-and-contract-dna.md` for the Create-Project/Pursuit UX flow this baseline already supports.

Everything actually implemented today is a strict, uncontradicted subset of this thesis. Nothing built needs to be reworked as the remaining pieces are designed and built. See `constitutional-invariants.md` for the rules that never change, and `current/kernel-object-model.md` for what exists in code today.

---

## What's actually implemented (real, tested, running code)

`services/case_workspace.py` (backend repo), 10 Foundation Batches plus the `promote_requirement_item()` bridge, Case-visibility (Private/Shared), and the collaboration-threshold/retraction tranches, 235 passing `unittest` tests. Full detail and code anchors: `current/kernel-object-model.md`. In one sentence: `Source`, `Requirement`, `Finding`, `Relationship`, `Case`, `ReviewerValidation`, `Disposition`, `RequirementAdjudication`, `Snapshot`, `Supersession`, `TemporalObligation`, `AnalysisRun`/`AnalysisTrigger`, `GovernanceLog`, the `promote_requirement_item()` bridge, Case visibility (`CASE_VISIBILITY_PRIVATE`/`CASE_VISIBILITY_SHARED`, `visible_cases_for`, `share_case`), and the Collaborative state/threshold (`CASE_VISIBILITY_COLLABORATIVE`, `retract_case_to_private`) all exist, are tested, and are the ground truth for everything else in this baseline. `RequirementAdjudication`, the promotion bridge, and the explicit Private→Shared→Collaborative Case lifecycle are also now reachable through minimal route wiring in `routes/workspace.py` (`promote_requirement_item_route`, `adjudicate_requirement`, `share_case`, `retract_case`).

## What's specified but unbuilt (fully designed, zero code)

Scenario/Scenario-Delta, `ViabilityAssessment`, `Template`, `ReferenceStandard`, Contract/Delivery DNA, Perspective (application layer), the graduated Contract Commitment event sequence, authoritative project metamorphosis (composes from existing primitives, no new object), Owner/Proponent publication (Published Procurement Instrument), the Neutral/Adjudication Workspace, the Experience Corpus (all forms), Project Security Policy (as governed `Requirement` content), the remainder of the investigation lifecycle extensions **beyond Case visibility/collaboration itself** — Archive, `CaseLock`, Derive/Copy/Adopt, publication anchoring — Deficiency/completion-resolution, dormancy/restart. Full detail in `specified-unbuilt/`. (Case visibility — Private/Shared/Collaborative, the explicit Share transition, the collaboration threshold, and pre-collaboration Shared→Private retraction — is now implemented; see the authorization table below and `current/kernel-object-model.md`.)

## What's deliberately deferred (acknowledged, not designed)

Machine Model / Installed Asset Identity; infrastructure/tenant hosting isolation; recurring `TemporalObligation` implementation; Experience Corpus partition mechanics; multi-decade storage strategy; template-library staleness governance; detailed workspace-module/application-surface structure; a future governed legal/dispute context (formal termination, default, insolvency, negotiated termination, court/arbitral intervention). Full list: `deferred-reserved/reservations.md`.

---

## Implementation authorization status — verbatim, do not silently change

| Item | Status |
|---|---|
| Architecture (the nine-round review this baseline documents) | **RATIFIED** |
| Application implementation, broadly | **STILL FROZEN** |
| Foundation Batch K (`RequirementAdjudication`) | Already implemented in code; **further feature expansion NOT AUTHORIZED** |
| `promote_requirement_item()` design | READY (superseded by implementation below) |
| `promote_requirement_item()` implementation | **IMPLEMENTED** — `services/case_workspace.py` (`CaseWorkspaceStore.promote_requirement_item`), 14 tests in `tests/test_requirement_promotion.py::PromoteRequirementItemTests`. Further feature expansion beyond this narrow tranche remains **NOT AUTHORIZED**. |
| `RequirementAdjudication` route wiring (`routes/workspace.py`) | **IMPLEMENTED** — `promote_requirement_item_route` and `adjudicate_requirement`, 5 tests in `tests/test_requirement_promotion.py::RequirementRouteWiringTests`. No broader UI/route architecture authorized beyond these two routes. |
| Case visibility — PRIVATE / SHARED / COLLABORATIVE states | **IMPLEMENTED** — `CaseRecord.visibility`/`created_by`/`shared_by`/`shared_at`/`collaboration_established_by`/`collaboration_established_at`/`collaboration_contribution_type`/`collaboration_contribution_id`/`retracted_by`/`retracted_at`, `CaseWorkspaceStore.visible_cases_for` (the real enforcement point — every case listing/switching/default-selection query in `routes/workspace.py` goes through it), plus indirect-identifier guards on `artifact_image` and `preview_finding_id`. 50 tests total across `tests/test_case_privacy.py` (24) and `tests/test_case_collaboration.py` (26). |
| Explicit Case PRIVATE → SHARED transition | **IMPLEMENTED** — `CaseWorkspaceStore.share_case` (owner-only authority), route wiring at `POST /projects/<project_id>/workspace/cases/<case_id>/share`. |
| Collaboration threshold (SHARED → COLLABORATIVE) | **IMPLEMENTED** — `CaseWorkspaceStore._cross_collaboration_threshold_if_qualifying`, invoked from the six qualifying write paths (`record_reviewer_validation`, `record_disposition`, `add_review_message` [human origin only], `request_attention`, `confirm_relationship`, `record_analysis` [`ANALYSIS_TRIGGER_USER_INITIATED` only]) atomically alongside each write's own `save()`. `Activity` and `RequirementAdjudication` are deliberately excluded, reasoned and documented in code, not silently omitted — see `current/kernel-object-model.md`. |
| Pre-collaboration Case SHARED → PRIVATE retraction | **IMPLEMENTED** — `CaseWorkspaceStore.retract_case_to_private` (owner-only, rejects outright once Collaborative), route wiring at `POST /projects/<project_id>/workspace/cases/<case_id>/retract`. |
| Post-collaboration privacy-reversion prohibition (Constitutional Invariant 12) | **IMPLEMENTED** — enforced at the single validation gate in `retract_case_to_private`; no other method mutates `visibility`, so there is exactly one place irreversibility could fail, and it is tested directly. |
| Archive, `CaseLock`, Derive/Copy/Adopt, publication anchoring | **NOT AUTHORIZED** — specified only; explicitly *not* implied by the rows above. See `specified-unbuilt/investigation-lifecycle-extensions.md`. |
| Scenario, ViabilityAssessment, Perspective, Contract DNA, Published Procurement Instrument, Neutral Workspace, Experience Corpus | **NOT AUTHORIZED** — specified only |
| Repository migration/consolidation | **FROZEN** — both repos remain physically separate |

If any future session is tempted to build something from `specified-unbuilt/` or `deferred-reserved/` without a fresh, explicit authorization, that is a mistake this document exists to prevent.

---

## Where to go next

- The rule that never changes: `constitutional-invariants.md`
- What's real in code today: `current/kernel-object-model.md`
- What's designed but not built: `specified-unbuilt/*.md`
- What's acknowledged but not designed: `deferred-reserved/reservations.md`
- How this baseline itself may change: `governance-of-governance/amendment-and-ratification.md`
- What exists in the historic Explorer corpus and where it maps: `history-mapping.md`
