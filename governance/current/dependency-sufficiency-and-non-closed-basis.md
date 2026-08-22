# Dependency Sufficiency and the Non-Closed Basis

Status: current governance principle, v1.0, 2026-08-22
Repository grounding SHA: `6f05f61e60e76676d443f8039046853afa79b38b`

**NO IMPLEMENTATION AUTHORITY CREATED. NO NEW ARCHITECTURE AUTHORIZED.**

This record changes no runtime behavior, route, schema, template, test, vocabulary,
or contract. It creates no status field, no flag, no score, no traversal engine, no
watcher, and no object. It adds **one reasoning rule** that no existing record states,
and it deliberately states nothing else.

## The principle

> **Sufficiency does not transit a dependency edge.**
>
> A conclusion may be internally consistent, currently cited, and free of
> contradiction while the basis it depends on is itself unresolved. Agreement among
> dependents is not evidence that their common basis is settled. GO may confirm what
> it has actually checked; it must not let that confirmation imply that anything
> upstream of it was checked too.

Three consequences, each of which is the *reason* the rule is needed rather than a
separate rule:

1. **Local consistency is not systemic validity.** Confirming that a schedule, a
   calculation and a drawing agree is a statement about those three records. It is
   not a statement about the analysis, recommendation or investigation they rest on.
2. **Agreement is not closure.** Several records may agree because they inherited one
   unsupported assumption. Absence of a recorded contradiction is absence of a
   recorded contradiction — nothing more.
3. **An upstream source may declare its own basis unresolved.** A governing document
   that states further investigation, verification, specialist input, future
   determination or field confirmation is required has not settled the question it
   appears to answer. Carrying it forward as though it had is the failure this rule
   names.

## Scope

- **GOVERNS:** how an evidence-sufficiency, confidence, convergence or conformance
  result may be *worded, reported and relied upon* when the object assessed depends
  on another object that was not itself assessed. It governs the **inference**, not
  the storage.
- **OUT OF SCOPE:** everything already governed and deliberately not restated here —
  `constitutional-invariants.md` #1 (no silent truth-promotion), #6 (existence is not
  compliance), #10 (authority conflicts surface, never resolve silently);
  `GOV-P-001` v1.0 (selection is context, not authorization); `CIC-SPIN-INTELLIGENCE`
  v1.1's Helix invariants; `GO-PREAWARD-ADJUDICATION-01`'s *Evidence → Concern →
  Question* grammar and its "missing evidence, evidence not yet expected,
  insufficient maturity, contradiction, and authority uncertainty remain different
  conditions." **None of those is amended, widened or narrowed.**
- **NOT GOVERNED:** whether GO should *detect* any of this automatically. It should
  not do so merely because this record exists.

## Why the existing corpus does not already cover it

Every ingredient is present. The binding rule is not.

| Existing primitive | What it evaluates | Why it does not reach this case |
|---|---|---|
| `evaluate_information_sufficiency` → `SUFFICIENCY_*` (nine outcomes) | one `ExpectationItem` against an explicit `observed` list | Node-scoped and caller-supplied. Its own docstring records that matching evidence is "deliberately NOT auto-discovered"; nothing walks from the observed item to what *it* depends on. |
| `compare_maturity` | two maturity values in one ordered vocabulary | Compares an item to an expectation, never a dependent to its basis. |
| `RequirementPhaseAssessment` | one Requirement at the project's current design phase | Correctly refuses to judge a 30% submission against IFC. Silent on whether the basis of that submission is settled. |
| Helix `KNOWN_HELIX_ASSESSMENTS` (ten values) | one interface, on one axis | `stage_maturity_mismatch` exists and is the right word — but see F-1 below. |
| `KNOWN_CONFIDENCE_STATES` (seven, closed) | one Claim's evidentiary support | See F-2 below. |
| `Supersession`, `current_requirement_for`, `requirement_predecessor` | revision ancestry of one subject | A *temporal* chain (which version governs now), not a *dependency* chain (what this rests on). Both walk; neither crosses subjects. |
| `relationships_for` | one hop, one object | No recursive or transitive walker exists anywhere in `services/`. Confirmed by direct search. |

**Two specific findings make the gap consequential rather than theoretical.**

**F-1 — The Helix longitudinal axis compares content, not the sufficiency of the
basis.** `services/spin.py`'s own prompt text defines it exactly: *"longitudinal
means current evidence against governing origin/prior authoritative state."* A
downstream strand that faithfully reflects an upstream document therefore reads as
`converged` on that axis, whether or not the upstream document had settled the
question. The axis is correct for what it asks; it does not ask this.

**F-2 — `CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT`'s published meaning treats absence
of contradiction as strength.** Its defined, testable meaning — surfaced verbatim to
users by `explain_investigation_answer` — is *"At least one directly-verified,
current piece of evidence supports this claim, and no contradicting evidence was
found."* That is an honest report of what was checked. Combined with the absence of
any transitive walk, several dependents inheriting one unsupported assumption produce
no `CONTRADICTS` relationship and therefore no reduction in confidence. **This is not
a defect in the meaning string, which says only what it did.** It is the exact point
at which the rule above has to be applied by whoever reads or reports the result.

## What this record does NOT do

- **It creates no OPEN/CLOSED flag, closure score, numeric maturity score, graph
  traversal engine, or new status vocabulary.** "Closure" is used above as a
  reasoning word in prose. It is **not** promoted to a field name, an enum value, a
  storage concept, or a production term, and must not be.
- **It does not amend `CIC-SPIN-INTELLIGENCE` v1.1 or any Helix vocabulary.**
  `KNOWN_HELIX_ASSESSMENTS`, `KNOWN_HELIX_AXES`, `KNOWN_HELIX_EXPECTATION_STATES` and
  `KNOWN_HELIX_EVIDENCE_SUFFICIENCY` are unchanged. F-1 is recorded as an observation
  about the axis instruction, not as an instruction to change it.
- **It does not authorize automatic detection** of upstream non-closure, similar-
  condition divergence, propagation gaps, or maturity mismatch.
- **It does not authorize an RFI, a question, a Finding, a Task, a Claim, or any
  other record to be produced automatically** from anything it describes.
- **It does not make "shop drawings required" mean "design incomplete."** The
  existing distinction between `SUFFICIENCY_NOT_EXPECTED_YET` / Helix
  `planned_deferred` / `legitimate_deferred` and `SUFFICIENCY_EXPECTED_NOT_FOUND`
  already carries legitimate delegated design, and the Spin instruction's own
  *"planned deferral is not failure"* stands unchanged.
- **It does not create a Builder, pricing, tender or commercial vocabulary.**
  `MATURITY_TYPE_DESIGN` and `MATURITY_TYPE_ESTIMATE` remain the two structurally
  distinct maturity dimensions, and estimate maturity remains, correctly, *never
  inferred from* design maturity.
- **It creates no invariant.** `constitutional-invariants.md` is unamended; that list
  changes only through `governance-of-governance/amendment-and-ratification.md`.

## Verification

**Review-time, not automated. No test is proposed, and one should not be added.**
A test that tried to decide whether a report "implied more certainty than the chain
supports" would encode a judgement this principle deliberately leaves to a reviewer —
the same reasoning `GOV-P-002` records for its own verification section.

Where the rule bites in practice: an implementation order, report, Spin narration or
Composer reply that states a confirmation must not phrase it so that the confirmation
appears to extend past what was actually assessed.

## Conflicts surfaced, not resolved

- **F-1 and F-2 above** are recorded as observations against current, working,
  correctly-tested code. Neither is filed as a defect and neither is scheduled.
- **`ExpectedInformationProfile` / `ExpectationItem` / `MaturityRecord` have store
  methods and no route-level producer.** `routes/workspace.py` reads
  `expected_information_profiles` and `maturity_records` to build Spin context; no
  route creates either. `RequirementPhaseAssessment.phase_source` will therefore
  report `inferred` in practice. Recorded as repository state; **no repair is
  proposed or authorized here.**
- **`RELATIONSHIP_TYPE_SAME_SUBJECT_AS` and `RELATIONSHIP_TYPE_COMPARES_WITH` have no
  producer or consumer** anywhere in `services/`, `routes/`, `templates/` or
  `static/`. The vocabulary for representing similar-condition divergence exists and
  is unused. Recorded; **no detector is designed or authorized.**

## Relationship to existing records

- **[`GO-HELIX-01`](../prompt-depository/GO-HELIX-01.md)** (APPROVED) and
  **[`CIC-SPIN-INTELLIGENCE` v1.1](contracts/CIC-SPIN-INTELLIGENCE-v1.1.md)** — Helix
  already holds *"a strand may be individually mature while still failing to mesh with
  dependent strands."* This record is the narrower companion in the other direction:
  a strand may mesh with its basis while the basis is unsettled. **Helix is refined by
  this rule, not replaced, and no parallel convergence doctrine is created.**
- **[`GO-PREAWARD-ADJUDICATION-01`](../prompt-depository/GO-PREAWARD-ADJUDICATION-01.md)**
  (APPROVED) — already governs observation-before-solution via *Evidence → Concern →
  Question*, "do not force every finding into RFI form," and the explicit prohibition
  on GO deciding design compliance autonomously. **Not restated, not extended.**
- **[`GO-RIVER-01`](../prompt-depository/GO-RIVER-01.md)** (APPROVED) — River makes
  dependency and consequence relationships traversable and forbids manufacturing
  causal certainty. This record adds no traversal and no River obligation.
- **[`specified-unbuilt/scenario-and-viability.md`](../specified-unbuilt/scenario-and-viability.md)**
  (NOT AUTHORIZED) — already the designed, unbuilt home for a candidate solution that
  is not project truth (`proposed`/`adopted`/`not_adopted`, expressed as Relationship
  deltas; VE is a `scenario_type`, not a subsystem), and already carries the
  pre-commitment question *"Should we accept this risk at this price/terms?"*. **Its
  status is unchanged and this record does not activate any part of it.**
- **[`specified-unbuilt/investigation-lifecycle-extensions.md`](../specified-unbuilt/investigation-lifecycle-extensions.md)**
  (partly unbuilt) — its unbuilt `Deficiency` primitive is the one existing design
  that answers *"is it closed"* for a correction lifecycle. Different question,
  deliberately not merged with this one. **Status unchanged.**
- **[`dormant-concern-recoverability-inventory-2026-08-22.md`](dormant-concern-recoverability-inventory-2026-08-22.md)** —
  found that recorded resolution conditions (`recommended_next_check`,
  `unresolved_question`) are inert. That is the same shape of gap one layer down and
  is **not re-derived here.**
- **[`VIS-004`](../vision/VIS-004.md) / [`ANA-003`](../vision/ANA-003.md)** —
  explanatory only, no authority, and not the basis of this record.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** any widening into a status vocabulary, a
  detector, a traversal mechanism, a scoring model, or an automatic action.
- **AMENDMENT RULE:** new version, never an in-place meaning edit.
- **SUPERSEDES:** None. **SUPERSEDED BY:** None.
- **GOVERNANCE DELTA:** `ADDITIVE`.

## Lineage

Stated by the Product Owner in conversation on **2026-08-22**, from a design
discussion about how experienced project managers and builders discover consequential
problems in contract information. The framing appears nowhere else in this
repository; **no earlier provenance is claimed and none was found by search.** The
worked examples that accompanied it (a fire-rated door traced to its occupancy basis;
a pile schedule traced to a geotechnical report that itself required further
investigation; eleven penetrations referencing a firestopping detail and one that does
not) are **illustrations, not governed cases**, and no project, party or document is
named or implied by them.

The wider discussion also proposed governed-ancestry traversal, investigative
curiosity, similar-condition comparison, pricing/commercial closure and role-dependent
solution generation. Each was tested against this repository and found either already
covered or explicitly unbuilt-by-design; **none of them is adopted by this record.**
