# GOV-P-007 — Invalid generated output is withdrawn and marked, never repaired

- **GOVERNANCE ID:** GOV-P-007
- **TITLE:** Invalid generated output is withdrawn and marked, never repaired
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** PROPOSED

## Authority

- **AUTHOR / PROPOSER:** Claude Opus 5, at Product Owner request, after five
  Help Scripts reached production carrying false provenance (`6253246`) and the
  question of what to do with them turned out to have no recorded answer.
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** Pending
- **EFFECTIVE DATE:** Pending

## Scope

- **GOVERNS:** Machine-generated content that has been found invalid — wrong
  provenance, ungrounded assertions, a superseded generation, or any other
  defect that makes it unfit to be relied on — after it has been persisted as a
  governed object. It governs three things about such output: whether it may
  remain reachable, whether it must be marked, and whether it may be corrected
  in place.
- **OUT OF SCOPE:** Whether generation should have happened, what a gate should
  check, and who may validate — `GOV-P-006` governs that. Content found merely
  incomplete or unfinished, which is ordinary draft work and not invalid.
  Retention periods, storage tiers, and any analytics built on retained
  material: this record permits retention and specifies none of that.

## Principle

> Generated output found invalid is **withdrawn** from active knowledge and
> **marked** with a stated cause. It is **never repaired in place**. It is
> **retained** rather than destroyed when it carries useful failure evidence.

Four clauses, and the third is the one that does the work:

> **Withdrawn.** It leaves REUSABLE content, active retrieval, and ordinary
> model-visible context. Being unreachable is not optional and not a
> side-effect.

> **Marked.** Silent inertness is insufficient. An invalid record that merely
> fails a gate looks identical to one that is unfinished, and the next reader
> cannot tell them apart. The mark carries a stated cause, an actor, and a time.

> **Never repaired.** Its stored provenance is not corrected, rewritten, or
> upgraded. A record of something that did not happen is worse than no record.

> **Retained where it teaches.** Deletion is a decision to be argued for, not a
> default, when the record carries evidence about what users asked, what failed,
> or which product area produced repeated friction.

## Rationale

The incident is small and the shape is not. `generate_help_clip` called the
authoring helpers without overriding their defaults, so model-written statements
were stored as human, `directly_verified` observations. Five Scripts reached
production that way. Every one of them was *already* unreachable — readiness
gates on REUSABLE and they were all DRAFT — and that turned out to be exactly
the problem worth recording: **they were harmless and indistinguishable from
ordinary work at the same time.**

The tempting repair is obvious and wrong. Editing `human_authored` to
`ai_proposed` on those five records produces a library that looks correct and
lies about its own history: it would assert that the system recorded the right
provenance at a time when it demonstrably did not. That is the same act
`GOV-P-006` forbids at the authority boundary, arriving from the other
direction — there a model must not acquire authority it never had; here a record
must not acquire correctness it never had. Regeneration produces a true Script.
Repair produces a plausible lie, and a cheaper one to produce.

The opposite error is equally available. Deleting the five is defensible and
loses the only sample of four independent generations against one scenario, four
differently-worded statements of the same evidence gap, and the exact record in
which the scene/direction design boundary first appears. That material is
product evidence about ARCHIOSK's own Help surface, and the impulse to tidy it
away is strongest at the moment it is most useful.

**Why a principle rather than a cleanup decision.** The disposition question
will recur on every generated-content surface this product grows, and answering
it case by case invites the cheap answer each time, because repair is always
faster than regeneration and deletion is always tidier than curation. Stating
the rule means both shortcuts have to be argued for.

## Invariants

- Content found invalid is excluded from reuse, retrieval, and ordinary
  model-visible context. Exclusion is not satisfied by the content merely
  failing a gate; it must not be reachable as an answer.
- An invalid record carries an explicit mark with a stated cause, a recorded
  actor, and a time. "It fails a check" is not a mark.
- The stored provenance of an invalid record is never edited, corrected or
  upgraded. Where the correct content is wanted, it is generated afresh as a
  new record.
- A correction never mutates the record it corrects. The invalid record and its
  replacement both exist, and the relationship between them is recorded rather
  than implied by absence.
- Retention of an invalid record does not make it citable. Retained material is
  evidence about the system, never evidence within it.
- Destroying an invalid record is a deliberate act with a stated reason, never a
  routine consequence of superseding it.

## Allowed variation

Which mechanism marks a record invalid — a rejection decision, a lifecycle
state, a governance-log event, or a purpose-built one — and where retained
material is stored. Whether retention is indefinite or bounded. What analysis,
if any, is ever performed on retained material. This principle fixes that
invalid output is withdrawn, marked, unrepaired and not reflexively destroyed;
it specifies no mechanism and commissions none.

## Prohibited drift

- **"Fixing the metadata is the same as regenerating."** It is not. One states
  what happened; the other states what we wish had happened.
- **"It already fails the gate, so it is handled."** Unreachable and marked are
  different properties, and only one of them survives a future change to the
  gate.
- **"It is invalid, so it is worthless."** Invalid for reuse and worthless as
  evidence are unrelated judgements.
- **"Keep everything, it might be useful."** Retention is for records carrying
  identifiable failure evidence, not a reason to never decide.
- **This record read as authorizing an analytics system.** It permits retention.
  It commissions no collection, no dashboard, and no processing of retained
  material.
- **This record read as covering unfinished work.** A draft nobody has finished
  is not invalid output.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** By the absence of any code path that edits
  the stored provenance of an existing record, and by the presence of an
  explicit invalidity mark — not merely a failing check — on records excluded
  for cause.
- **TESTS / CHECKS / ORACLES:** Partial. `tests/test_help_generated_provenance.py`
  asserts that neither validation nor claim adoption rewrites `content_class` or
  `author_type`, which pins the never-repaired clause on the one surface that
  has generated content today. `services/help_resolution.py` and its tests pin
  the withdrawal clause: only REUSABLE Scripts are retrievable, asserted
  directly against a bound-but-not-reusable Script. **No oracle covers the
  marking or retention clauses** — today they are procedure, not mechanism, and
  that gap is stated rather than papered over. It is shared with `GOV-P-004`,
  `GOV-P-005` and `GOV-P-006`, none of which has a `GOV-I-` either.

## Dependencies

- **RELATED GOVERNANCE:** [`GOV-P-006`](GOV-P-006.md) (a model may constrain a
  governed transition, never authorize one — the same refusal to let a record
  acquire standing it did not earn, at the authority boundary rather than the
  correction boundary); `constitutional-invariants.md` #3 (provenance is
  mandatory — a repaired record violates it by asserting a provenance that was
  never true) and #6 (existence is not compliance — a record existing in a
  library does not make it usable knowledge).
- **STANDING CONTRACTS:** None changed.
- **REQUIRED IMPLEMENTATION ORDERS:** None. Current behaviour already withdraws
  invalid Help Scripts from reuse and never repairs provenance. Marking is
  currently available through the existing rejection decision and is performed
  by a human, not by this record.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any mechanism that edits stored provenance
  on an existing record; any reading in which retained invalid material becomes
  citable as evidence within the product; any collection or analysis built on
  retained material.
- **AMENDMENT / SUPERSESSION RULE:** A new version via `GOV-CN-` and `GOV-S-`,
  never an in-place meaning edit.

## Lineage

- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** None yet. The disposition of the five Help Scripts
  described above is a separate Product Owner decision this record informs and
  does not make.

## Governance delta

`ADDITIVE`
