# TEMPLATE — Governance Exception / Waiver (`GOV-X-`)

**Purpose.** Authorize one bounded, time-limited deviation from a governing rule
without weakening that rule globally.

**Exceptions must not silently become precedents.** A waiver applies to the scope
it names and nothing else. A second, similar situation needs its own `GOV-X-` — or,
if the pattern keeps recurring, a `GOV-CN-` to change the rule honestly. Reusing a
waiver by analogy is how a rule stops being a rule without anyone deciding to
repeal it.

**Every waiver expires.** A deviation with no expiry and no review condition is not
an exception; it is an unrecorded amendment. If the deviation should be permanent,
that is a `GOV-CN-`, not this template.

This is `amendment-and-ratification.md`'s deferred *risk-acceptance*, adopted as
structure.

---

```markdown
# GOV-X-nnn — <Title>

- **GOVERNANCE ID:** GOV-X-nnn
- **TITLE:** <the deviation, in one line>
- **TYPE:** Governance Exception / Waiver
- **VERSION:** v1.0
- **STATUS:** DRAFT | PROPOSED | CURRENT | EXPIRED | WITHDRAWN | SUPERSEDED

## Authority

- **REQUESTED BY:** <who>
- **APPROVING AUTHORITY:** <who can waive this rule — normally the Product Owner;
  a constitutional invariant is **not waivable** by this template>
- **APPROVAL DATE:** <YYYY-MM-DD>

## Governing rule

- **RECORD:** <exact id and version — GOV-* / CIC-* vX.Y / current record>
- **RULE TEXT:**

  > <Verbatim quote of the rule being deviated from. The rule stays in force
  > everywhere this waiver's scope does not reach.>

## Exception

> <Exactly what is permitted that the rule would otherwise forbid. Narrow and
> concrete. "Flexibility around X" is not an exception; it is an erosion.>

## Scope

- **APPLIES TO:** <the specific work, mission, surface, record, or run>
- **DOES NOT APPLY TO:** <everything adjacent that a reader might assume is
  covered. This field is what stops the waiver spreading.>
- **PRECEDENT:** **None.** This waiver authorizes its stated scope only. A similar
  future situation requires its own record.

## Justification

<Why the deviation is warranted here, and why the alternative — complying, or
changing the rule — is worse in this specific case. If the honest answer is "the
rule is wrong", file a `GOV-CN-` instead.>

## Duration

- **START:** <YYYY-MM-DD>
- **EXPIRY:** <YYYY-MM-DD> **or** **REVIEW CONDITION:** <a specific, observable
  event — "when Mission 03 is authorized", "when the parser is replaced". Not
  "when convenient".>
- **ON EXPIRY:** the governing rule applies again in full, with no further action
  required. Renewal is a new `GOV-X-`, not an extension of this one.

## Risks

<What could go wrong because of this deviation, stated concretely. A waiver whose
risk section says "minimal" has not been assessed.>

- <risk>

## Compensating controls

<What is put in place so the deviation is survivable — extra verification, a
narrower blast radius, a manual check, additional logging. Name who performs each.
If nothing compensates, say so explicitly; an uncompensated waiver may still be
correct, but the Product Owner should approve it knowing that.>

- <control>

## Verification

- **HOW THE BOUND IS ENFORCED:** <what stops this waiver being applied outside its
  scope — ideally a check, not an intention>
- **TESTS / CHECKS / ORACLES:** <or "none">

## Closure / revocation

- **CLOSURE CONDITION:** <what makes this waiver no longer needed>
- **REVOCATION:** <who may revoke early, and on what trigger>
- **CLOSED ON:** <blank until closed>
- **OUTCOME:** <blank until closed — what actually happened, including whether the
  risks materialised. This is the field that makes the next waiver decision better
  informed than this one.>

## Dependencies

- **RELATED GOVERNANCE:** <GOV-* / CIC-* / invariants>
- **RAISED FROM:** <GOV-CR-nnn, if a conflict report produced this — or None>

## Lineage

- **SUPERSEDES:** <a prior waiver this renews — or None>
- **SUPERSEDED BY:** <or None>
- **RELATED DECISIONS:** <or None>

## Governance delta

`ADDITIVE`
<!-- A waiver adds a bounded, expiring permission. It never modifies the governing
     rule — if the rule itself should change, that is a GOV-CN-. -->
```

---

## Notes on filling this in

- **Scope and expiry are the whole template.** Everything else supports them. A
  waiver with a vague scope or an open-ended expiry has repealed a rule by
  accident.
- **"Does not apply to" earns its place.** Waivers spread by analogy, and the
  analogy is always drawn by someone who was not in this conversation.
- **Constitutional invariants are not waivable here.** They change only through
  their own recorded, attributed, reasoned amendment process.
- **Fill in the outcome on closure.** A waiver register where every entry stops at
  approval teaches nothing; one that records what actually happened makes the next
  risk decision cheaper and better.
