# GOV-S-001 — CIC-SPIN-INTELLIGENCE v1.1 → v1.2, admitting Multi-Observer Shear as a layer distinct from Helix

- **GOVERNANCE ID:** GOV-S-001
- **TITLE:** Partial supersession of CIC-SPIN-INTELLIGENCE v1.1 — SCOPE and APPLIES WHEN replaced, MANDATORY INVARIANTS extended
- **TYPE:** Governance Supersession Record
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude, under `GOV-CN-001`
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-08-30
- **EFFECTIVE DATE:** 2026-08-30

## Superseded record

- **RECORD:** `CIC-SPIN-INTELLIGENCE` v1.1 (`governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md`)
- **SUPERSESSION EXTENT:** `PARTIAL`
- **SUPERSEDED SCOPE:** Exactly two clauses stop governing — **SCOPE** and
  **APPLIES WHEN** — each replaced by the wording below. **MANDATORY
  INVARIANTS** is *extended*, not superseded: every invariant in v1.1's list
  continues to govern, verbatim and unchanged, and clauses are added after them.
  No other clause of v1.1 is touched: GOVERNING PRINCIPLE, DOES NOT APPLY WHEN,
  OPTIONAL / CONTEXTUAL REQUIREMENTS, REFERENCE IMPLEMENTATIONS, REFERENCE TESTS
  and KNOWN LIMITATIONS all carry forward (the last three with additions that do
  not remove anything).
- **PRIOR WORDING:**

  SCOPE:

  > Spin evidence selection, assembly, model invocation, findings, provenance, and Helix / Progressive Project Convergence assessment.

  APPLIES WHEN:

  > Project/document Spin, evidence-to-model plumbing, prompts, findings, run history, or Helix assessment governance is touched.

## New governing record

- **RECORD:** `CIC-SPIN-INTELLIGENCE` v1.2 (`governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.2.md`)
- **NEW WORDING:**

  SCOPE:

  > Spin evidence selection, assembly, model invocation, findings, provenance, Helix / Progressive Project Convergence assessment, and Multi-Observer Shear analysis.

  APPLIES WHEN:

  > Project/document Spin, evidence-to-model plumbing, prompts, findings, run history, Helix assessment governance, or Multi-Observer Shear analysis is touched.

  Added to MANDATORY INVARIANTS, after the existing Helix clauses:

  > Multi-Observer Shear is a distinct analysis layer and is never Helix — Helix's subject is the convergence of interdependent physical/interface strands, Shear's subject is divergence between the frames of distinct parties observing the same project state, and the two must not share a name, a vocabulary, a persisted field, or a parser; a Shear result must never be emitted as a Helix assessment and a Helix assessment must never be reinterpreted as Shear; observer frames are derived from the project's own ingested contracts, roles and evidence — never from a hard-coded party set, delivery-model template, or assumed project structure — and a project whose evidence does not establish distinct observer frames yields no Shear rather than a default one; Shear maps where distinct rational positions diverge and never adjudicates between them, so divergence is not error, a party's position is not scored, and no observer frame is ranked above another; Shear never speculates about motive, intent, competence or state of mind, and is grounded only in what each party's own evidence states.

## Relationship type

`SUPERSEDED`

Scoped as stated above: v1.1's SCOPE and APPLIES WHEN clauses no longer govern.
Everything else in v1.1 continues to govern through v1.2, which is `ABSORBED`
in substance for the invariant list — but the record-level relationship is
`SUPERSEDED`, because v1.2 is a new version of the same contract rather than a
different record carrying the concept onward.

## Reason

`GOV-CR-001` (2026-08-30, RESOLVED) recorded that the GO Decision Architecture
directive's instruction to implement Multi-Observer Shear *as* Helix would have
replaced the governed subject of a CURRENT contract while leaving its name,
closed vocabulary and reference tests in place, and would have hard-coded an
`(Architect, GC, Owner)` party set in breach of constitutional invariant #15.

The Product Owner resolved that conflict by adopting the re-scope
recommendation, and approved `GOV-CN-001` on 2026-08-30. This record is the
supersession that notice required to take effect.

## What changed

| Aspect | Before | After |
|---|---|---|
| SCOPE | Spin evidence, assembly, model invocation, findings, provenance, Helix assessment | …the same, plus Multi-Observer Shear analysis |
| APPLIES WHEN | …or Helix assessment governance is touched | …or Multi-Observer Shear analysis is touched |
| Helix's subject | strand convergence | **unchanged** — strand convergence, clause preserved verbatim |
| Helix vocabulary, axes, parser | ten assessments, three axes, `_parse_helix_assessments` | **unchanged** |
| Shear's status | not mentioned; a shear layer inside Spin would have been ungoverned | governed: distinct layer, own name/vocabulary/field/parser, dynamically derived observer frames, never adjudicates |
| Observer frames | not addressed | must be derived from ingested contracts, roles and evidence; no default frame when evidence establishes none |
| REFERENCE IMPLEMENTATIONS | Helix paths only | …plus an explicit statement that Shear has none yet |
| KNOWN LIMITATIONS | three | …plus Shear authorized-in-principle-and-unbuilt, and the frame-derivation mechanism undesigned |

## What remains in force

Mandatory on a `PARTIAL` supersession, and checked clause by clause. All of the
following continue to govern, unchanged, through v1.2:

- **GOVERNING PRINCIPLE** — strands, meshing, and Spin as the process that tests
  the mesh. Untouched. This is what keeps Helix's subject fixed.
- **DOES NOT APPLY WHEN** — presentational timestamp/history changes.
- **Every one of v1.1's MANDATORY INVARIANTS**, verbatim: model-backed Spin;
  governed evidence reaches the model; truthful source scope and provenance; no
  Teacher/Oracle leakage; no PSD/smoke-specific steering; no model-memory
  authority; known/testable truncation and selection; findings grounded in
  supplied evidence; strands progress at different velocities; individual strand
  maturity does not prove coordination; claimed maturity comes from project
  evidence; a mature strand can still fail to mesh; **Helix is an
  investigative/convergence model, not a universal scoring system**; **Helix must
  not silently become a coordination percentage, health score, universal
  LOD/percentage mapping, universal tolerance table, hard-coded trade hierarchy,
  project-wide uniform-maturity assumption, or automatic engineering/design
  correction mechanism**; expectation, observation, consequence and evidence
  sufficiency remain distinct; non-convergence is not automatically
  noncompliance.
- **OPTIONAL / CONTEXTUAL REQUIREMENTS** — dry-run/model-boundary diagnostics.
- **REFERENCE IMPLEMENTATIONS, REFERENCE TESTS, KNOWN LIMITATIONS** — every
  v1.1 entry retained; v1.2 adds to each without removing anything.

The two Helix clauses are bolded above because they are the ones `GOV-CR-001`
was filed to protect. They survive this supersession untouched, which was the
point of the re-scope.

## Migration / transition

- **CODE / TESTS:** None required. This supersession authorizes a layer; it
  builds nothing. `tests/test_go_decision_architecture_01.py`'s Helix-vocabulary
  assertions need no amendment and become *more* load-bearing under v1.2, since
  Shear must never touch that vocabulary.
- **IN-FLIGHT WORK:** None authorized under v1.1 is affected. The four
  implemented items of the GO Decision Architecture directive (survival triage
  ordering, cognitive stopping, temporal anti-smuggling, bounded execution
  authority) are prompt-level and touch neither Helix nor Shear. Building
  `services/observer_shear.py` requires its own implementation order and is not
  authorized by this record.
- **CITATIONS:** `governance/current/contracts/README.md`'s registry row updated
  to v1.2. No other record cites CIC-SPIN-INTELLIGENCE by version.

## Historical status

`CIC-SPIN-INTELLIGENCE-v1.1.md` is preserved in place, readable, and citable for
lineage. It has been marked `STATUS: SUPERSEDED` and `SUPERSEDED BY:
CIC-SPIN-INTELLIGENCE v1.2, via GOV-S-001` — status markers only. No wording in
that file was altered; the reasoning that produced it stays exactly as written.

**Pre-existing drift, flagged and then corrected on instruction.**
`governance/current/contracts/CIC-SPIN-INTELLIGENCE.md` (v1.0) carried
`STATUS: CURRENT` despite already recording `SUPERSEDED BY:
CIC-SPIN-INTELLIGENCE v1.1`. That contradiction predates this record. It was
raised rather than fixed silently, and the Product Owner directed the correction
on 2026-08-30; v1.0's status marker now reads `SUPERSEDED`.

Scope of that correction, stated because a retroactive edit to governance needs
its bounds on the record: **the status marker only.** No wording in v1.0 was
altered, and no `GOV-S-` was filed for the v1.0 → v1.1 supersession. Filing one
now would mean reconstructing a 2026-08-21 decision nobody present recorded,
which is the reconstruction this corpus's own standing rule forbids — the
missing supersession record stays missing and visible, rather than being
invented to make the file set look complete. v1.0's own `SUPERSEDED BY` line has
always named its successor, so the lineage was never actually lost; only the
status marker disagreed with it.

Three files in that directory name this contract. Exactly one, v1.2, governs.
