# TEMPLATE — Governance Decision Record (`GOV-D-`)

**Purpose.** Record an explicit choice made among alternatives that were genuinely
live at the time, and preserve why the others were rejected.

**Do not turn every principle into a decision record.** A rule that had no real
alternative is a `GOV-P-`, not a `GOV-D-`. The test: could you name at least one
other option a competent person would have argued for? If not, this is the wrong
template.

**Rejected alternatives are the point.** A decision record whose value survives is
one that stops the same rejected option being re-proposed in six months by someone
who was not in the conversation.

---

```markdown
# GOV-D-nnn — <Title>

- **GOVERNANCE ID:** GOV-D-nnn
- **TITLE:** <the decision, stated as a decision>
- **TYPE:** Governance Decision Record
- **VERSION:** v1.0
- **STATUS:** DRAFT | PROPOSED | CURRENT | SUPERSEDED | ABSORBED | WITHDRAWN

## Authority

- **AUTHOR / PROPOSER:** <who framed the question>
- **APPROVING AUTHORITY:** <who decided>
- **APPROVAL DATE:** <YYYY-MM-DD>
- **EFFECTIVE DATE:** <YYYY-MM-DD, or "on approval">

## Decision question

> <The question as it actually stood, before the answer was known. Written so a
> reader who disagrees with the outcome would still accept this as a fair framing.>

## Scope

- **GOVERNS:** <what this decision binds>
- **OUT OF SCOPE:** <what it does not settle — especially adjacent questions a
  reader might assume were also decided here>

## Options considered

| # | Option | Summary | Outcome |
|---|---|---|---|
| 1 | <name> | <one line> | **CHOSEN** / rejected |
| 2 | <name> | <one line> | rejected |
| 3 | <name> | <one line> | rejected |

<Include only options that were genuinely considered. Padding the table with
strawmen makes the record less trustworthy, not more thorough.>

## Decision

> <What was decided. Concise and unambiguous.>

## Rationale

<Why this option. What evidence, constraint, or grounding decided it — repository
state, a measured result, a Product Owner requirement. Name it.>

## Consequences

- **ACCEPTED COSTS:** <what is worse because of this choice — every real decision
  has some; a record listing none is not finished>
- **ENABLED:** <what becomes possible or simpler>
- **FORECLOSED:** <what becomes harder or is now off the table>

## Rejected alternatives

<Per rejected option: why it was rejected, and — importantly — **what would have to
change for it to be worth reconsidering**. That second half is what makes this
record useful later instead of merely historical.>

## Dependencies

- **RELATED GOVERNANCE:** <GOV-* / constitutional invariants / current records>
- **STANDING CONTRACTS:** <CIC-* ids and versions>
- **REQUIRED IMPLEMENTATION ORDERS:** <work this decision authorizes or requires;
  "none" if it changes nothing yet>

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** <how you can tell the decision is actually
  being followed in the codebase>
- **TESTS / CHECKS / ORACLES:** <paths, lanes, `GOV-I-` ids, or "none yet">

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** <what would require revisiting this>
- **AMENDMENT / SUPERSESSION RULE:** <normally: a new `GOV-D-` superseding this one,
  never an in-place edit of the decision>

## Lineage

- **SUPERSEDES:** <GOV-D-nnn vX.Y and superseded scope — or None>
- **SUPERSEDED BY:** <or None>
- **RELATED DECISIONS:** <or None>

## Governance delta

`ADDITIVE` | `UNCHANGED` | `CHANGE PROPOSED — NOT APPLIED` | `CONFLICT FOUND — STOPPED`
```

---

## Notes on filling this in

- **Write the question before the answer.** If the decision question can only be
  understood by someone who already knows the outcome, it has been written
  backwards and will not survive as a record.
- **"Accepted costs" is mandatory in substance, not just in form.** A decision with
  no downside was not a decision.
- **Reversal is a new record.** Superseding a `GOV-D-` means a new `GOV-D-` plus a
  `GOV-S-`; the original stays readable, including its rejected options.
