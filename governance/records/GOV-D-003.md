# GOV-D-003 — The deferred programme set was reviewed against current substrate and remains correctly deferred

- **GOVERNANCE ID:** GOV-D-003
- **TITLE:** The deferred programme set was reviewed against current substrate and remains correctly deferred
- **TYPE:** Governance Decision Record
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude Opus 5, under a direct Product Owner instruction of
  2026-09-05: *"Get the old assignments done with so we can move on, and the
  sequence does not matter unless Claude finds it matters."*
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-09-05
- **EFFECTIVE DATE:** 2026-09-05

## Decision question

Should the long-standing deferred programme records — named in the instruction as
External Source Vestibule, Project Object Registry, First-Run UX, Merged History,
Risk/Monte Carlo and Universal Venue, alongside the two approved commissioning and
pre-award programmes — be retired, closed, absorbed into current kernel primitives,
or implemented as one bundled slice, so that attention moves to forward
architecture under [`GOV-P-004`](GOV-P-004.md)?

## Scope

- **GOVERNS:** The disposition of those records, and the standing of the deferred
  set as a whole relative to the question "is there an open backlog here?"
- **OUT OF SCOPE:** The content of any deferred programme; whether any of them may
  later be built (that remains `STATUS.md` and each record); the genuinely open
  normalization items in `back-catalog/MIGRATION-QUEUE.md`, which are unaffected and
  listed below as still open; and `MQ-P0-04`, resolved separately and concurrently
  by [`GOV-P-005`](GOV-P-005.md).

## Options considered

1. **Retire / close the records.** Move them to a terminal state so the backlog
   reads as cleared.
2. **Close as `ABSORBED` into current kernel primitives.** Treat the implemented
   substrate as having satisfied the intent.
3. **Schedule one bundled implementation slice.** Build enough of each to close them.
4. **Record the review; change no status.** Confirm on evidence that the set is
   correctly deferred, and date that confirmation.

## Decision

**Option 4.** The deferred set is confirmed correctly deferred as of 2026-09-05.
**No status changes, no absorptions, no deletions, and no implementation is
authorized by this record.** What closes is the *question*, not the programmes: the
review happened, it is dated, and it does not need repeating without new evidence.

The instruction's premise — that these are open assignments awaiting disposition —
does not hold, and the decision records that finding rather than acting on the
premise.

## Rationale

**These records were never an open queue.** `prompt-depository/PROMPT_REGISTER.md`
describes itself as a *"governed prospective register"* that *"records future
prompts and their lineage."* It is a preservation instrument for Product Owner
intent. `DEFERRED` is not an item awaiting closure; it is the disposition, carrying
Product Owner acceptance language in each record.

**The substrate reconciliation option 2 proposes has already been performed, and
reached the opposite conclusion.** `current/comm-a1-self-project-commissioning-readiness.md`
sections J, K, L and M are exactly that exercise. Each names the implemented
primitive that covers the near-term need, and each concludes *not required* while
preserving the future question — which is *why* these are deferred. Every one of
the four was re-verified in code on 2026-09-05 rather than taken on the record's
word:

| Section | Programme | Primitive named | Verified |
|---|---|---|---|
| J | Merged History | `GovernanceLog` + per-object append-only sub-history | `services/case_workspace.py` |
| K | Project Object Registry | `original_requirement_identifier` preserves `OPR-X.X` | `services/case_workspace.py:1440` |
| L | Risk / Monte Carlo | risk register as an ordinary `WorkProduct` | `artifact_type="risk_register"`, `templates/case_workspace.html:3626` |
| M | First-Run UX | throwaway-admin + disposable-project + real-delete-gate pattern | `comm-a1` §M, exercised across six gates |

Reaching "retire" instead would require **new** evidence, not a fresh reading of the
same evidence.

**The two closest "already satisfied" candidates fail on inspection.**
`services/project_code.py` gives a *project* a governed readable acronym, and its own
header records that *"Repository inspection found NO existing acronym or project-code
concept"* — a project code is not project-**object** identity, which is what
`GO-PROJECT-OBJECT-REGISTRY-01` concerns (findings, requirements, relationships).
And `services/external_intelligence_airlock.py`, while genuinely implementing the
non-promotion rule, states in its own docstring that it is *"deliberately a small
process seam over existing ARCHIOSK primitives, not a durable Airlock subsystem,"*
scoped to one mission and one fixed route — which is precisely what
`GO-EXTERNAL-VESTIBULE-01` already says about itself. The records are accurate as
filed, not stale.

**The corpus's own audit already answered the retirement question.**
`back-catalog/MIGRATION-QUEUE.md`, verbatim: *"Age is not priority. The 18 `DEFERRED`
prompt records and the 13 commissioning stage records are the oldest material in the
corpus and are all `P3`. They are settled, correctly filed, and cost nothing where
they sit."* And: *"Approximately 60 of 121 records are correctly filed and need
nothing… The corpus is not disorganized."*

**Retiring would destroy information rather than reduce it.** A `DEFERRED` record
with Product-Owner-confirmed direction and a named reason carries strictly more than
a closed one. Nothing is currently paid for keeping them.

## Consequences

- **ACCEPTED COSTS:** The register keeps a visible deferred set, so a future reader
  may again mistake preserved intent for an open queue. This record is the answer to
  that, and is why it was worth filing rather than simply doing nothing.
- **ENABLED:** Forward work under `GOV-P-004` proceeds without an implied backlog
  obligation. A dated review exists to cite.
- **FORECLOSED:** Nothing. Every deferred programme remains available for
  authorization on its own merits, unchanged.

## Rejected alternatives

- **Option 1 (retire/close).** The register's Status vocabulary is closed —
  `DRAFT`/`APPROVED`/`RUN`/`DEFERRED`/`SUPERSEDED`/`ABSORBED` — and contains no
  "closed" state. Retiring would require amending the register's own contract to
  record something less informative than what it already holds.
- **Option 2 (`ABSORBED`).** `ABSORBED` is a factual claim requiring a named
  successor, and preservation rule 3 requires identifying it. No successor exists
  for any of these; every record's own Lineage field says *"Related, not absorbed"*
  about the adjacent programmes, deliberately. Asserting absorption would falsify
  lineage — the same class of harm `constitutional-invariants.md` #3 forbids for
  evidence provenance.
- **Option 3 (bundled slice).** Would build six programmes that `STATUS.md` does not
  authorize. Under the repository's precedence rule, code implementing something
  marked NOT AUTHORIZED is a defect, not evidence the table is outdated.

## Sequencing finding

The instruction asked whether sequence matters. For the deferred set: **no.** There
are no schema, domain-model or route dependencies among them; each record's Lineage
names the adjacent programmes as *related, not absorbed*, and none blocks another.

Two exceptions were found and do matter, both tied to the forward `GOV-P-004` work:

- **External Source Vestibule had to be settled with `GOV-P-004`, not after it.**
  Its Airlock/Vestibule distinction is load-bearing for four `RUN` mission
  authorizations while the record carrying it is `DEFERRED` — `MQ-P0-04`/`GBC-0026`,
  scored P0 — and `GOV-P-004`'s own Proponent-side ingestion invariant is that
  distinction applied at the procurement boundary. Resolved concurrently by
  [`GOV-P-005`](GOV-P-005.md), by promotion rather than retirement.
- **`GO-PREAWARD-ADJUDICATION-01` is the anchor for what `GOV-P-004` deliberately
  excludes.** `GOV-P-004`'s OUT OF SCOPE states it *"does not reach evaluation,
  award, scoring, or any adjudication workflow."* Retiring the pre-award record
  would remove the counterpart that exclusion points at.

## Dependencies

- **RELATED GOVERNANCE:** [`GOV-P-005`](GOV-P-005.md) (resolves `MQ-P0-04`, filed
  concurrently); [`GOV-P-004`](GOV-P-004.md) (the forward architecture this clears
  the way for); `current/comm-a1-self-project-commissioning-readiness.md` §§J/K/L/M
  (the substrate reconciliation relied on here);
  `back-catalog/MIGRATION-QUEUE.md` and `back-catalog/REGISTER.md` (the actual
  normalization backlog); `prompt-depository/PROMPT_REGISTER.md` preservation rules
  2 and 3; `STATUS.md`.
- **STANDING CONTRACTS:** None changed.
- **REQUIRED IMPLEMENTATION ORDERS:** None.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** By the eight named prompt records retaining
  their existing statuses and verbatim prompt text, and by the absence of any
  implementation of the six deferred programmes.
- **TESTS / CHECKS / ORACLES:** None, and none is appropriate — this record decides
  that a set of documents stays as it is.

## What remains genuinely open

Recorded so that "the backlog is cleared" is not read more broadly than this
decision supports. Verified 2026-09-05 against `back-catalog/MIGRATION-QUEUE.md`:

- **`MQ-P0-02`** — `GOV-I-001`, Teacher/Oracle pass-fail and leakage enforcement.
  **P0, open.** No `GOV-I-` record of any number exists yet.
- **`MQ-P1-03`** — `GOV-X-001`, the Mission 02 doctrine-departure waiver. **Open,
  and blocked on Product Owner input:** the missing element is an expiry/review
  condition, which an agent may not invent.
- **`MQ-P1-06`** — authorization markers on `specified-unbuilt/` files. **Open:** 12
  of the 14 still carry none. Three of the fourteen are partially implemented and
  need per-record wording, not a bulk stamp.
- **`MQ-P1-01`, `MQ-P1-04`, and the seven `P2` items** — open, lower priority.
- **A `GOV-I-` oracle for `GOV-P-004`'s Standalone Viability**, already recorded as
  owed in `CONTINUATION_CHECKPOINT.md`. `GOV-P-005` has the same gap for its own
  general case.

Already resolved and needing nothing: `MQ-P0-01` (`GOV-P-001`), `MQ-P0-03` (Camel
status clarification), `MQ-P1-02` (`GOV-P-002`), `MQ-P1-05` (Canonical
Implementation Order's `APPLICABLE GOVERNANCE` line), and now `MQ-P0-04`.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any status change to a record covered by this
  review; any assertion that a deferred programme has been absorbed; and any
  reading of this record as authorization to build one.
- **AMENDMENT / SUPERSESSION RULE:** A new `GOV-D-` superseding this one. New
  evidence that a deferred programme's intent is genuinely satisfied by implemented
  substrate is exactly what would justify that.

## Lineage

- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** `GOV-D-001`, `GOV-D-002`.

## Governance delta

`ADDITIVE`
