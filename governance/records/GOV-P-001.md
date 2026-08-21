# GOV-P-001 — Selection is context, not authorization

- **GOVERNANCE ID:** GOV-P-001
- **TITLE:** Selection is context, not authorization
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude, under `CLAUDE-GOV-P-001-AND-VISION-ANALOGY-FAMILY-01`
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-08-20
- **EFFECTIVE DATE:** 2026-08-20

## Scope

- **GOVERNS:** Every ARCHIOSK surface where a user selects, focuses, opens, attaches
  or otherwise points at a governed object — project sources, requirements,
  findings, application objects in Developer Mode, CCN context elements, panel and
  page selections. It governs both what selection *must* do and what it *must not*
  do.
- **OUT OF SCOPE:** How a mutation *is* authorized. This principle says selection is
  not the authorizing act; it does not define what is. Authorization mechanisms
  remain governed where they already live — the Approval Gate, adjudication paths,
  `RequirementAdjudication`/`Disposition`/`ReviewerValidation`, and explicit Product
  Owner instruction. Also out of scope: which objects are selectable on a given
  surface, and the UI affordances of selection.

## Principle

> **Selecting an object supplies it to the system as context, and never as
> permission.** Where a surface supports selection, the selected object must be
> genuinely available as context to the reasoning that follows. Selection alone
> never authorizes creating, changing, promoting, or deleting anything.

Both halves are load-bearing. The positive obligation is not decoration on a
prohibition: a system that accepts a selection and then fails to use it as context
violates this principle just as surely as one that treats selection as consent.

## Rationale

This rule already governed ARCHIOSK in three places, in three different wordings,
none derived from the others:

| Source | Wording |
|---|---|
| `current/developer-mode-ccn.md` | "selected application objects are conversational context for inspection, explanation, tracing, comparison, critique and suggestion. **Selection is never authorization to mutate.**" |
| `CIC-DEVELOPER-MODE` v1.0 | "selection is context, not authorization" |
| `CIC-CCN` v1.0 | "selection never authorizes mutation" |

Two of those — the contract invariants — are equal-authority `CURRENT` records with
no parent between them. The drift is real and directional: `CIC-CCN`'s wording
carries **only** the prohibition, so an implementation order citing `CIC-CCN` alone
inherits a strictly narrower rule and could legitimately conclude that a selection
need never reach the model at all. That is not what the governance source says, and
it is not what the product does.

Recorded as drift cluster **DC-01** in
[`../back-catalog/DRIFT-AND-LINEAGE.md`](../back-catalog/DRIFT-AND-LINEAGE.md),
found by mechanical comparison of all nine `CIC-*` invariant fields.

## Invariants

- A selected object is available as context to the reasoning, explanation or
  analysis that follows on that surface.
- Selection never creates, modifies, promotes, adjudicates, publishes or deletes a
  governed object.
- Selection never substitutes for an authorization step that is otherwise required.
- Selected objects retain their existing identity, provenance and project scope;
  selection does not re-scope or re-attribute them.
- Selection context is filtered by project scope where the selected objects carry
  it, so selecting never leaks across a project boundary.

## Allowed variation

- **How** selection is expressed per surface — click, command, attachment, focus,
  `/CCN` element capture, or a future direct visual selection.
- **What** is selectable on a given surface, and how many objects at once.
- How selected context is rendered, summarized, truncated or prioritized before
  reaching the model, provided it genuinely reaches it.
- Whether a surface supports selection at all. A surface with no selection does not
  violate this principle.
- Per-surface analysis vocabulary applied to selected elements — for example CCN's
  `KEEP`/`MOVE`/`MODIFY`/`RETIRE`/`INVESTIGATE`.

## Prohibited drift

- **Reducing this to the prohibition alone.** "Selection never authorizes mutation"
  is half the rule. Citing only that half is how the positive obligation was lost in
  `CIC-CCN` in the first place.
- Treating selection as implied consent because the user "clearly meant it" — a
  selection plus an inferred intent is still not an authorization.
- Treating a *count* of selections, or a repeated selection, as escalating intent.
- Treating selection inside Developer Mode as different in kind. Developer Mode
  makes ARCHIOSK the subject; it does not relax this rule.
- Accepting a selection and silently discarding it before the model call, then
  describing the result as context-aware.
- Reading "context" as permission to widen scope — selection supplies *that* object,
  not its neighbours, its project, or its history.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** For the positive half — evidence that the
  selected object actually reached the reasoning path (a prompt-boundary or
  model-seam test, not a UI assertion). For the negative half — evidence that a
  mutation attempted from selection alone is refused by the surface's normal
  authorization path.
- **TESTS / CHECKS / ORACLES:** `tests/test_developer_mode_ccn_01.py`,
  `tests/test_developer_ui_reveal_workbench_history_01.py`, and the Developer
  Composer tests named by the citing contracts. **No test currently asserts the
  positive half as such** — that is a real verification gap, recorded here rather
  than papered over, and a `GOV-I` candidate.

  > **Correction (2026-08-21, `CLAUDE-GOVERNANCE-CLOSEOUT-01`).** The sentence above
  > is **too broad and is corrected here** rather than edited away. A test-architecture
  > investigation found the positive half **is** already proven on the Developer Mode /
  > application path:
  > `tests/test_developer_home_composer_01.py::test_application_adapter_supplies_context_and_history_to_shared_model_gateway`
  > patches the gateway and asserts the selected element's label appears in the actual
  > `user_prompt` — selection genuinely reaching the model, not merely being stored.
  > That test is **not named in either citing contract's `REFERENCE TESTS`**, so the
  > coverage existed but was not discoverable from the contracts; that is a citation
  > gap, now recorded.
  >
  > **The narrowed, still-open gap:** no equivalent assertion exists on the
  > **project-workspace** selection path. `tests/test_ca1b_persistent_context.py`'s
  > nineteen tests cover persistence, project scoping, indicator display and
  > cross-project rejection — none asserts that a selected Requirement or Finding
  > reaches the model prompt as reasoning context.
  >
  > **Deliberately unresolved:** whether workspace selection reaches the prompt at all
  > today was **not** established by that pass. This matters, and is why no test was
  > added: if the behaviour exists, a test would prove it (permitted); if it does not,
  > the same test would prescribe new behaviour (not permitted in a governance pass).
  > Establishing which is the first step of any future verification work.
  >
  > Recommended verification point, when authorized: a single assertion at the
  > workspace model seam, mirroring the Developer Mode test above, in
  > `tests/test_ca1b_persistent_context.py`. No new harness required.

## Dependencies

- **RELATED GOVERNANCE:** `constitutional-invariants.md` #2 (machine inference never
  silently becomes authority) — **adjacent, not parent.** #2 governs machine
  *inference* becoming authority; this governs a *human* act of selection being read
  as authority. They rhyme and neither derives from the other. This record does not
  claim descent from #2, and a future decision that it should be one would be a
  `GOV-CN`, not an edit here.
- **GOVERNANCE SOURCE:** `current/developer-mode-ccn.md` (2026-08-20) — the record
  both citing contracts already name as their source.
- **STANDING CONTRACTS:** `CIC-DEVELOPER-MODE` v1.0, `CIC-CCN` v1.0 — both cite this
  record as of 2026-08-20 and retain their own implementation and test obligations.
- **REQUIRED IMPLEMENTATION ORDERS:** None. This record changes no behaviour; it
  gives an existing rule one canonical statement.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any narrowing of either half, any change to the
  invariant list, and any claim of descent from a constitutional invariant.
- **AMENDMENT / SUPERSESSION RULE:** A new version via `GOV-CN` and `GOV-S`. Never an
  in-place meaning edit. Citing contracts pin the version they cite, so a v2.0 does
  not silently re-interpret orders written against v1.0.

## Lineage

- **SUPERSEDES:** None. The three prior wordings are **not** superseded — they remain
  in force in their own records as domain-specific statements, and this record is
  their canonical parent, not their replacement.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** None. Recommended by the back-catalog audit
  (`CLAUDE-GOVERNANCE-BACKCATALOG-ORGANIZE-01`, MQ-P0-01).

## Governance delta

`ADDITIVE`
