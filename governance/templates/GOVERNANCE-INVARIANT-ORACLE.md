# TEMPLATE — Governance Invariant / Test-Oracle (`GOV-I-`)

**Purpose.** Translate an approved principle into something objectively testable —
a stated pass condition, a stated fail condition, and a method that distinguishes
them without judgement.

**An oracle tests a principle; it never creates one.** If filling this in requires
inventing a rule that is not already approved somewhere, stop and file a `GOV-P-`
or a `GOV-CN-` first.

**When to escalate to a `GOV-I-`.** A `CIC-*` contract already lists mandatory
invariants and reference tests, and for most invariants that pairing is enough.
Write a `GOV-I-` when the invariant is hard to test honestly: when the pass
condition is contested, when the test could pass for the wrong reason, or when the
oracle must stay **hidden from the system under test** — a Teacher/Oracle blind
evaluation being the sharp case.

---

```markdown
# GOV-I-nnn — <Title>

- **GOVERNANCE ID:** GOV-I-nnn
- **TITLE:** <the invariant, in one line>
- **TYPE:** Governance Invariant / Test-Oracle
- **VERSION:** v1.0
- **STATUS:** DRAFT | PROPOSED | CURRENT | SUPERSEDED | ABSORBED | WITHDRAWN

## Authority

- **AUTHOR / PROPOSER:** <who>
- **APPROVING AUTHORITY:** <who>
- **APPROVAL DATE:** <YYYY-MM-DD>
- **EFFECTIVE DATE:** <YYYY-MM-DD, or "on approval">

## Governing principle

- **SOURCE RECORD:** <GOV-P-nnn vX.Y, CIC-* vX.Y, or constitutional invariant #>
- **PRINCIPLE TEXT:**

  > <Verbatim quote of the approved rule this oracle tests. If no approved source
  > exists, this record cannot proceed.>

## Invariant

> <The single thing that must remain true, stated so that "did it hold?" has a
> yes/no answer. One invariant per record — an oracle covering three invariants
> will report a failure without saying which one broke.>

## Pass condition

<Exactly what must be observed for this to pass. Stated positively and
specifically enough that two people running it independently reach the same
verdict.>

## Fail condition

<Exactly what constitutes a failure — including the near-misses that should count
as failures. Write this separately rather than as "not the pass condition": the
gap between the two is where an invariant silently stops being enforced.>

## Test / oracle method

- **METHOD:** automated test | deterministic check | structured review | blind evaluation
- **PROCEDURE:** <how it is run, concretely>
- **LOCATION:** <test path / lane / script — or "manual, no automation yet">
- **FREQUENCY:** <every change to X | per release | on demand>

### Blind-oracle separation

<Complete this section only for a blind or Teacher/Oracle evaluation. Delete it
otherwise.>

- **HIDDEN ORACLE MATERIAL:** <what the system under test must never see —
  expected answers, planted conditions, scoring keys>
- **WHERE IT LIVES:** <a location outside the evaluated corpus>
- **LEAKAGE PROHIBITION:** Hidden oracle material must never be registered as a
  `Source`, an `EvidenceItem`, or any other project evidence, and must never enter
  a model prompt for the system under test. A leaked oracle does not produce a
  wrong answer — it produces a **right answer for the wrong reason**, which is
  worse, because the test then reports success.
- **LEAKAGE CHECK:** <how absence of leakage is actually verified, not assumed>

## Evidence required

<What must be captured for a result to count: outputs, logs, run ids, diffs,
screenshots. A verdict with no retained evidence is an opinion.>

## Known limitations

<What this oracle does **not** prove. State it plainly — an oracle whose limits
are unstated will be cited as proving more than it does, which is the most common
way a passing test becomes a false assurance.>

## Dependencies

- **RELATED GOVERNANCE:** <GOV-* / CIC-* / invariants>
- **REQUIRED IMPLEMENTATION ORDERS:** <work needed to automate this — or "none">

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** <what changes to pass/fail conditions need
  approval — narrowing a fail condition always does>
- **AMENDMENT / SUPERSESSION RULE:** <normally a new version via `GOV-CN-`/`GOV-S-`>

## Lineage

- **SUPERSEDES:** <or None>
- **SUPERSEDED BY:** <or None>
- **RELATED DECISIONS:** <or None>

## Governance delta

`ADDITIVE` | `UNCHANGED`
```

---

## Notes on filling this in

- **One invariant per record.** Bundling is the fastest way to an oracle that
  reports a failure nobody can locate.
- **Write the fail condition independently.** Deriving it as the negation of the
  pass condition hides the near-misses, and the near-misses are what actually
  happen.
- **"Known limitations" is not a weakness section.** It is what keeps a green
  result from being over-cited later.
- **Automating this later does not need new governance.** Moving a `MANUAL`
  procedure into a test file is allowed variation; changing what counts as passing
  is not.
