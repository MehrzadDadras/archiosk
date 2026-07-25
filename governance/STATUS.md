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

`services/case_workspace.py` (backend repo), 4,594 lines, 10 Foundation Batches, 166 passing `unittest` tests. Full detail and code anchors: `current/kernel-object-model.md`. In one sentence: `Source`, `Requirement`, `Finding`, `Relationship`, `Case`, `ReviewerValidation`, `Disposition`, `RequirementAdjudication`, `Snapshot`, `Supersession`, `TemporalObligation`, `AnalysisRun`/`AnalysisTrigger`, and `GovernanceLog` all exist, are tested, and are the ground truth for everything else in this baseline.

## What's specified but unbuilt (fully designed, zero code)

Scenario/Scenario-Delta, `ViabilityAssessment`, `Template`, `ReferenceStandard`, Contract/Delivery DNA, Perspective (application layer), the graduated Contract Commitment event sequence, authoritative project metamorphosis (composes from existing primitives, no new object), Owner/Proponent publication (Published Procurement Instrument), the Neutral/Adjudication Workspace, the Experience Corpus (all forms), Project Security Policy (as governed `Requirement` content), investigation lifecycle extensions (visibility, collaboration threshold, Archive/Lock/Derive), Deficiency/completion-resolution, dormancy/restart. Full detail in `specified-unbuilt/`.

## What's deliberately deferred (acknowledged, not designed)

Machine Model / Installed Asset Identity; infrastructure/tenant hosting isolation; recurring `TemporalObligation` implementation; Experience Corpus partition mechanics; multi-decade storage strategy; template-library staleness governance; detailed workspace-module/application-surface structure; a future governed legal/dispute context (formal termination, default, insolvency, negotiated termination, court/arbitral intervention). Full list: `deferred-reserved/reservations.md`.

---

## Implementation authorization status — verbatim, do not silently change

| Item | Status |
|---|---|
| Architecture (the nine-round review this baseline documents) | **RATIFIED** |
| Application implementation, broadly | **STILL FROZEN** |
| Foundation Batch K (`RequirementAdjudication`) | Already implemented in code; **further feature expansion NOT AUTHORIZED** |
| `promote_requirement_item()` design | **READY** (see `specified-unbuilt/` for the finalized contract) |
| `promote_requirement_item()` implementation | **NOT YET AUTHORIZED** |
| `RequirementAdjudication` route wiring (`routes/workspace.py`) | **NOT YET AUTHORIZED** |
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
