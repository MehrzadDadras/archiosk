# GOV-P-006 — A model may constrain a governed transition; it may never authorize one

- **GOVERNANCE ID:** GOV-P-006
- **TITLE:** A model may constrain a governed transition; it may never authorize one
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude Opus 5, on finding the rule load-bearing in code
  across two commits (`1f8ad42`, `26cd795`) with no authoritative home — the same
  status/use gap `MQ-P0-04` raised about the Airlock/Vestibule distinction, and
  the same remedy.
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-09-05
- **EFFECTIVE DATE:** 2026-09-05

## Scope

- **GOVERNS:** Any place where a model-generated assessment participates in a
  governed transition — a readiness gate, a validation step, an adoption, a
  publication, a promotion, a state change. It governs what such an assessment
  may cause, in both directions: what it may prevent, and what it may not bring
  about.
- **OUT OF SCOPE:** Whether a model may be called at all, and on what route —
  that is `ACTION_EXTERNAL_AI_REQUEST` and the Airlock mission authorizations.
  What a model is asked, how well it answers, and whether its output is any
  good. It authorizes no capability and commissions no mechanism.

## Principle

> A model-generated assessment may **constrain** a governed transition — block
> it, or require review before it proceeds. It may never **authorize** one:
> not validate, not adopt, not publish, not promote, and not by itself move any
> object to a state carrying more authority than it had.

The asymmetry is the whole rule, and it is what makes a model safe to place
inside a gate at all. A component that can only ever stop something cannot
become the authority for starting it.

Two corollaries, part of the principle and quotable with it:

> **Absence of an assessment is not a pass.** A gate that treats "nothing has
> been assessed" as satisfied is decorative.

> **An assessment that could not run is not a verdict.** Infrastructure failure
> degrades to "review needed", never to either answer.

## Rationale

Three records already say a version of *this input informs, it does not
authorize*, each for a different input, and none of them reaches a model
assessment:

- [`GOV-P-001`](GOV-P-001.md) — *selection is context, not permission*. About a
  human's selection on a surface.
- [`GOV-P-005`](GOV-P-005.md) — *arrival is not admission*. Its GOVERNS clause is
  explicitly scoped to "material originating outside a project's governed
  corpus", wherever such material **arrives**.
- `constitutional-invariants.md` #15 — *Contract DNA must never masquerade as
  project authority*. About a delivery-model template.

**Why GOV-P-005 is the near miss rather than the home.** It was the obvious
candidate and it does not fit, on two independent grounds. Its scope is arriving
external *material*; a question-fit verdict is neither arriving nor material —
it is an assessment produced about content already inside the corpus. And its
own change control states "a new version via `GOV-CN-` and `GOV-S-`, never an
in-place meaning edit", so widening its GOVERNS clause is not a small amendment:
it is a Change Notice plus a Supersession, to make a precise record less precise.
A sibling is both smaller and more honest. The two remain closely related and
cite each other.

**Why this is filed at all, rather than left in the code.** It is already
load-bearing. `resolve_script_readiness` refuses to report VALIDATED without a
PASS verdict, and refuses to reach REUSABLE on a PASS alone; `assess_question_fit`
is given no workspace or store precisely so it cannot reach a state to change.
Both behaviours were implemented, tested and mutation-tested before this record
existed, which means the rule was governing the product from a code comment.
That is the exact condition `MQ-P0-04` was scored P0 for, and filing it here is
the same remedy applied one layer earlier — before, rather than after, someone
notices.

The failure this prevents is specific and quiet. A model in a gate starts as a
helper and becomes the decision, because each step is locally reasonable: first
its verdict is advisory, then a passing verdict is treated as sufficient because
it usually is, then the human review that was meant to follow becomes a
formality nobody performs. Nothing announces the moment authority moved. Stating
the asymmetry as a rule means the drift has to be argued for rather than
arrived at.

## Invariants

- A model-generated assessment may block a governed transition or require review
  of it, and may cause no transition on its own.
- No model output may validate, adopt, publish, promote, or advance the state of
  any governed object without a separate human act that is itself recorded.
- The absence of an assessment never satisfies a gate that expects one.
- An assessment that did not run — no key, timeout, transport error, malformed
  or unrecognised output — resolves to "review needed", never to pass and never
  to fail.
- A stored assessment describes the object as it stood when the assessment was
  made. It does not carry forward to changed content on its own.
- Where a model assessment is persisted beside a governed record, its own
  provenance travels with it: what was assessed, when, by what, and whether it
  actually ran.

## Allowed variation

Which model, which prompt, what an assessment is called, how many outcome values
it has beyond the pass/block/review distinction, whether it is invoked
automatically or on request, whether verdicts are stored or recomputed, and how
a reviewer is shown one. This principle fixes what an assessment may *cause*,
never how it is produced or presented.

## Prohibited drift

- **"The verdict is reliable enough to act on."** Reliability is not the
  question; authority is. A more accurate model does not acquire the right to
  promote, and a claim that it has become accurate enough is the drift, not an
  argument against it.
- **"No verdict recorded, so nothing is blocking."** Absence is not a pass.
- **"The model was unavailable, so treat it as passed"** — or as failed. Neither.
- **"A human already reviewed something similar."** Validation attaches to the
  object as it stands, not to a family of objects.
- **This record read as restricting when a model may be CALLED.** It does not
  reach that; `ACTION_EXTERNAL_AI_REQUEST` governs it.
- **This record read as authorizing a model-in-the-loop gate anywhere.** It
  constrains such gates where they exist; it commissions none.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** By the absence of any code path in which a
  model result raises the authority of a governed object, and by the presence of
  a separate recorded human act on every promotion path that involves one.
- **TESTS / CHECKS / ORACLES:** Partial and real, unusually so for a principle
  here. `tests/test_script_measurement_gate.py` asserts that a PASS alone does
  not validate, that FAIL and REVIEW_NEEDED block despite human validation, that
  an absent verdict still requires review, and that a stored verdict stops
  applying once content changes. `tests/test_question_fit_semantic_check.py`
  asserts every degrade path resolves to review-needed and that the assessment
  function is handed no workspace, store, or identifier. Both were
  mutation-tested. **No oracle covers the general case** across future
  model-in-the-loop gates — that is a `GOV-I-` this record does not have, and it
  shares that gap with `GOV-P-004` and `GOV-P-005`.

## Dependencies

- **RELATED GOVERNANCE:** [`GOV-P-001`](GOV-P-001.md) (selection is context, not
  permission — the same shape for a human input); [`GOV-P-005`](GOV-P-005.md)
  (arrival is not admission — the same shape for external material, and the
  near-miss home discussed above); `constitutional-invariants.md` #15 (Contract
  DNA must never masquerade as project authority) and #6 (existence is not
  compliance); `specified-unbuilt/camel-multimodal-programme.md`'s own
  "AI-generated answers and relationships must remain proposals until
  appropriately reviewed", which this generalises from claims to transitions.
- **STANDING CONTRACTS:** None changed. Any contract governing a surface where a
  model participates in a decision may cite this record.
- **REQUIRED IMPLEMENTATION ORDERS:** None. The behaviour already conforms.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any mechanism in which a model result
  advances a governed object's state without a separate recorded human act; any
  reading in which an absent or failed assessment satisfies a gate.
- **AMENDMENT / SUPERSESSION RULE:** A new version via `GOV-CN-` and `GOV-S-`,
  never an in-place meaning edit.

## Lineage

- **SUPERSEDES:** None.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** None.

## Governance delta

`ADDITIVE`
