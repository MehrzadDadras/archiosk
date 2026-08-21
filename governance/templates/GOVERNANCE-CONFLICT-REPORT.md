# TEMPLATE — Governance Conflict Report (`GOV-CR-`)

**Purpose.** Stop implementation when requested work cannot proceed without
violating approved governance — and hand the Product Owner a decision, not a
reinterpretation.

**The rule this template exists to enforce: no silent reinterpretation.** When an
instruction and approved governance cannot both be satisfied, the honest move is
to stop and say so. Finding a reading of the governance under which the work is
technically fine is the failure mode this record prevents.

This is `amendment-and-ratification.md`'s deferred *conflict-escalation*, adopted
as structure. The mandatory delta `CONFLICT FOUND — STOPPED` already exists in the
Canonical Implementation Order; this is the record that accompanies it.

---

```markdown
# GOV-CR-nnn — <Title>

- **GOVERNANCE ID:** GOV-CR-nnn
- **TITLE:** <the conflict, in one line>
- **TYPE:** Governance Conflict Report
- **VERSION:** v1.0
- **STATUS:** PROPOSED
  <!-- A conflict report is raised, not approved. It resolves when the Product
       Owner decides: the work is dropped, the work is re-scoped, a GOV-CN-
       amends the governance, or a GOV-X- authorizes a bounded exception. -->

## Authority

- **RAISED BY:** <agent or person>
- **DATE RAISED:** <YYYY-MM-DD>
- **DECISION REQUIRED FROM:** <normally the Product Owner>

## Request / trigger

<What was asked for, and where it came from — the order, prompt, or instruction,
cited by id where one exists. Quote the operative sentence rather than summarising
it; the exact ask is half of the conflict.>

## Conflicting governance

| Record | Version | Operative text |
|---|---|---|
| <GOV-* / CIC-* / invariant #> | vX.Y | > <verbatim quote of the clause in conflict> |

## Exact conflict

<State the collision precisely: doing X, as instructed, would violate Y, which
requires Z. Not "this seems to be in tension with" — name the specific clause and
the specific act that would breach it.>

## Why both cannot currently be satisfied

<Show that this is a genuine conflict, not a gap in your own reading. Include the
readings you tried and why each fails. If a reading exists under which both hold,
this is not a conflict report — take that reading and proceed.>

## Safe work that may continue

<Everything in the original request that does **not** touch the conflict, listed
explicitly so the whole task is not blocked by one clause. Being precise here is
what makes stopping cheap enough to do honestly.>

- <item that can proceed>
- <item that can proceed>

## Blocked work

- <item that cannot proceed, and which clause blocks it>

## Decision required from Product Owner

<The available paths, stated neutrally, with the consequence of each. Recommend
one — a report that refuses to recommend pushes the analysis back onto the person
with the least context.>

| Option | Effect | Governance action needed |
|---|---|---|
| Drop or re-scope the work | <effect> | none |
| Amend the governance | <effect> | `GOV-CN-` |
| Authorize a bounded exception | <effect> | `GOV-X-` |
| Proceed as instructed | <effect — including what precedent it sets> | explicit Product Owner override, recorded |

**RECOMMENDATION:** <one option, with one sentence of why>

## Lineage

- **RESOLVED BY:** <blank until decided; then the record that settled it —
  `GOV-CN-nnn`, `GOV-X-nnn`, a recorded Product Owner override, or "work dropped".
  A conflict report with no resolution recorded is an open stop, and reads as one.>
- **RESOLUTION DATE:** <blank until decided>
- **RELATED CONFLICTS:** <earlier GOV-CR-* against the same clause — a repeat is a
  signal the governance itself needs a `GOV-CN-`, not another stop — or None>
- **RELATED DECISIONS:** <GOV-D-* / GOV-P-* — or None>

## Governance delta

`CONFLICT FOUND — STOPPED`
<!-- Mandatory. This is the only valid value for this record type. -->
```

---

## Notes on filling this in

- **Quote the governance verbatim.** A summarised clause invites the reader to
  assume you have already interpreted it — which is the thing you stopped in order
  not to do.
- **"Safe work that may continue" is not padding.** A conflict report that blocks
  an entire task when only one part collides makes stopping expensive, and expensive
  stopping is how conflicts start getting reinterpreted instead of reported.
- **Include "proceed as instructed" as a real option.** The Product Owner may
  legitimately override; the record's job is to make sure the override is a decision
  someone made, with its precedent stated, rather than something that just happened.
- **Do not resolve your own conflict report.** Raising it and then acting on your
  preferred option is the same silent reinterpretation in two steps.
