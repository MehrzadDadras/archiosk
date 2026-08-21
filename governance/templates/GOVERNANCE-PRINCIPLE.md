# TEMPLATE — Governance Principle (`GOV-P-`)

**Purpose.** Preserve a durable product, architecture, evidence, authority, or
interaction principle — a rule that must remain true across many future changes.

**Before using this template, check the Routing rule in [`README.md`](README.md).**
If the rule belongs to a development work domain a `CIC-*` standing contract
already covers, it belongs in that contract. If it is a BEEHIVE domain-object
rule, it belongs in `constitutional-invariants.md` via that document's own
ratification process. A `GOV-P-` that restates either is duplication.

**Use it for** rules like *"Selection is context, not authorization"* — a single
canonical statement that more than one contract needs to cite identically.

---

```markdown
# GOV-P-nnn — <Title>

- **GOVERNANCE ID:** GOV-P-nnn
- **TITLE:** <short, quotable>
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** DRAFT | PROPOSED | CURRENT | SUPERSEDED | ABSORBED | WITHDRAWN

## Authority

- **AUTHOR / PROPOSER:** <who wrote it>
- **APPROVING AUTHORITY:** <who can approve it — normally the Product Owner>
- **APPROVAL DATE:** <YYYY-MM-DD, or "not approved">
- **EFFECTIVE DATE:** <YYYY-MM-DD, or "on approval">

## Scope

- **GOVERNS:** <what this applies to>
- **OUT OF SCOPE:** <what it deliberately does not reach — state this even when
  it seems obvious; an unstated boundary is where drift begins>

## Principle

> <One or two sentences. Authoritative, quotable, and readable on its own out of
> context. If it needs a paragraph to state, it is probably two principles.>

## Rationale

<Why this exists. Name the specific drift, failure, or ambiguity it prevents —
ideally one that actually happened. A rationale that could be written about any
principle is not a rationale.>

## Invariants

<What must remain true. One line each, each independently checkable. These are
what a `GOV-I-` oracle or a test would be written against.>

- <invariant>
- <invariant>

## Allowed variation

<What an implementer may change freely without new governance approval. Being
explicit here is what stops this principle from being read as broader than
intended, and is the difference between a usable rule and a blocker.>

## Prohibited drift

<What must not be silently reinterpreted. Name the specific plausible-sounding
misreadings — the ones a reasonable person would arrive at — not strawmen.>

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** <what evidence settles it>
- **TESTS / CHECKS / ORACLES:** <paths, lanes, or `GOV-I-` ids; "none yet" is an
  honest answer and is itself a finding>

## Dependencies

- **RELATED GOVERNANCE:** <GOV-* / constitutional invariant numbers / current records>
- **STANDING CONTRACTS:** <CIC-* ids and versions that cite or implement this>
- **REQUIRED IMPLEMENTATION ORDERS:** <if adopting this needs work; "none">

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** <what kinds of change cannot be made without
  a `GOV-CN-` and approval>
- **AMENDMENT / SUPERSESSION RULE:** <how this record may be replaced — normally:
  a new version via `GOV-CN-` and `GOV-S-`, never an in-place meaning edit>

## Lineage

- **SUPERSEDES:** <GOV-P-nnn vX.Y, and the scope superseded — or None>
- **SUPERSEDED BY:** <or None>
- **RELATED DECISIONS:** <GOV-D-* — or None>

## Governance delta

`ADDITIVE` | `UNCHANGED` | `CHANGE PROPOSED — NOT APPLIED` | `CONFLICT FOUND — STOPPED`
```

---

## Notes on filling this in

- **The Principle block is the only part that governs.** Everything else explains,
  bounds, or traces it. Write that block last, once you know what the invariants
  and allowed variation actually are.
- **Allowed variation is not optional politeness.** A principle with no stated
  allowed variation will be read as forbidding everything adjacent to it, and will
  be quietly ignored the first time that becomes inconvenient.
- **Do not force irrelevant fields.** A principle with no related decisions says
  `None`; it does not invent one.
