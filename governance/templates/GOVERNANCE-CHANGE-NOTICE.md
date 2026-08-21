# TEMPLATE — Governance Change Notice (`GOV-CN-`)

**Purpose.** Propose an amendment to existing governance **without changing it**.

**The load-bearing rule: a `GOV-CN-` in `PROPOSED` alters nothing by existing.**
Approved governance keeps governing, unmodified, until the notice is approved and
a `GOV-S-` records the supersession. Filing a notice is not a soft edit, is not
notice-and-proceed, and never shifts the burden onto whoever would object.

This is `amendment-and-ratification.md`'s deferred *change-proposal review*,
adopted as structure. Its principle — no silent governance mutation — is
unchanged and is exactly what this template enforces.

---

```markdown
# GOV-CN-nnn — <Title>

- **GOVERNANCE ID:** GOV-CN-nnn
- **TITLE:** <what is proposed, in one line>
- **TYPE:** Governance Change Notice
- **VERSION:** v1.0
- **STATUS:** DRAFT | PROPOSED | WITHDRAWN | ABSORBED
  <!-- A change notice never reaches CURRENT. On approval it produces a new
       version of the target record plus a GOV-S-, and this notice becomes
       ABSORBED into that successor. -->

## Authority

- **AUTHOR / PROPOSER:** <who proposes>
- **APPROVAL REQUIRED FROM:** <who must approve — normally the Product Owner;
  for a constitutional invariant, its own ratification process>
- **DATE RAISED:** <YYYY-MM-DD>
- **DECISION DATE:** <blank until decided>

## Current governance

- **TARGET RECORD(S):** <exact ids and versions — GOV-*, CIC-* vX.Y,
  constitutional invariant number, or current-record path>
- **CURRENT WORDING:** 

  > <Quote the governing text verbatim. Do not paraphrase it — a paraphrase in a
  > change notice is already a small unauthorized edit.>

## Proposed change

- **PROPOSED WORDING:**

  > <The exact replacement text, written as it would stand if approved.>

- **NATURE OF CHANGE:** clarification | narrowing | widening | reversal | addition
  <!-- Be honest here. A widening described as a clarification is the most common
       way governance drifts without anyone deciding to change it. -->

## Why

<The problem, drift, ambiguity, or new evidence prompting this. If the trigger was
a real incident or a conflict report, cite it by id.>

## Expected consequences

- **IF APPROVED:** <what changes in practice>
- **IF NOT APPROVED:** <what stays true, and what problem remains unsolved>

## Affected invariants

<Per invariant in the target record: does it survive unchanged, narrow, widen, or
disappear? An invariant that quietly disappears is the single highest-risk outcome
of any change notice — list every one, including the ones that survive.>

| Invariant | Effect |
|---|---|
| <invariant> | unchanged / narrowed / widened / removed |

## Compatibility and conflict analysis

- **CONSISTENT WITH:** <records this still sits comfortably beside>
- **CONFLICTS WITH:** <records this would contradict if approved — or "none found",
  stated as a result of an actual check, not an assumption>
- **PRECEDENCE EFFECT:** <does approving this change which record governs a
  situation that is currently settled?>

## Migration requirements

- **CODE / TESTS:** <what would have to change; "none" if purely documentary>
- **EXISTING RECORDS:** <records needing restatement, and whether that is in scope
  here or separate>
- **IN-FLIGHT WORK:** <orders or missions already authorized under the current
  wording, and what happens to them>

## Approval required

<State plainly what approving this authorizes and what it does not. If approval
would also implicitly settle a second question, say so — bundled approval is how
unexamined decisions get made.>

## Lineage

- **SUPERSEDES:** <a prior notice this replaces, e.g. one WITHDRAWN after review — or None>
- **ABSORBED INTO:** <blank until approved; then the successor record this notice
  produced, which is where its reasoning now lives>
- **RAISED FROM:** <GOV-CR-nnn, if a conflict report prompted this — or None>
- **RELATED DECISIONS:** <GOV-D-* — or None>

## Governance delta

`CHANGE PROPOSED — NOT APPLIED`
<!-- This is the only valid value while the notice stands. It becomes UNCHANGED
     if withdrawn, or is replaced by the successor record's own delta on approval. -->
```

---

## Notes on filling this in

- **Quote, never paraphrase, the current wording.** The diff between current and
  proposed is the entire content of this record.
- **"Nature of change" is where honesty is cheapest and most valuable.** Widening
  a rule and calling it a clarification passes review and then surprises everyone
  later.
- **On approval, this notice does not become the governance.** It produces a new
  version of the target record and a `GOV-S-`. The notice is then `ABSORBED`, and
  stays filed so the reasoning remains traceable.
