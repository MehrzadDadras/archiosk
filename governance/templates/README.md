# Governance Template Family

Status: current governance-record format family, version 1.0
Authority: [`../governance-of-governance/amendment-and-ratification.md`](../governance-of-governance/amendment-and-ratification.md)
Companion: [`../current/canonical-implementation-order.md`](../current/canonical-implementation-order.md) and [`../current/contracts/README.md`](../current/contracts/README.md)

These are blank forms, not governance. A template governs nothing; a **record
created from one** governs what it says, once approved. Filing a template does
not create authority.

**Why a stable structure.** These work like military orders: the mission-specific
content changes every time, the structure does not. The structure is what forces
the important categories to be considered — authority, scope, invariants, allowed
variation, prohibited drift, verification, lineage — so an implementer does not
have to remember every prior conversation to avoid re-litigating a settled point.
The template carries the institutional memory.

**What this family closes.** `amendment-and-ratification.md` deferred the
operational detail of constitutional amendment authority, naming
*change-proposal review*, *conflict-escalation*, and *risk-acceptance* as
process items specified in the historic Explorer corpus but "mined for principle
rather than adopted as structure." Templates 3, 4 and 7 are those three,
adopted as structure here. Nothing in that document's principles is changed.

---

## The family

| Template | Record ID prefix | Use it to… | Do **not** use it to… |
|---|---|---|---|
| [Governance Principle](GOVERNANCE-PRINCIPLE.md) | `GOV-P-` | Preserve a durable product/architecture/evidence/authority/interaction rule that spans more than one work domain | Restate a rule a standing contract already carries — see **Routing** below |
| [Governance Decision Record](GOVERNANCE-DECISION-RECORD.md) | `GOV-D-` | Record a real choice between live alternatives, and why the others were rejected | Dress up a principle that had no alternatives. Not every rule is a decision |
| [Governance Change Notice](GOVERNANCE-CHANGE-NOTICE.md) | `GOV-CN-` | Propose an amendment to existing governance **without changing it** | Change governance. A CN in `PROPOSED` alters nothing by existing |
| [Governance Conflict Report](GOVERNANCE-CONFLICT-REPORT.md) | `GOV-CR-` | Stop work that cannot proceed without violating approved governance | Reinterpret the governance so the work can continue |
| [Governance Supersession Record](GOVERNANCE-SUPERSESSION-RECORD.md) | `GOV-S-` | Replace or narrow governance while preserving the prior wording and lineage | Delete, tidy, or retroactively "fix" a superseded record |
| [Governance Invariant / Test-Oracle](GOVERNANCE-INVARIANT-ORACLE.md) | `GOV-I-` | Turn an approved principle into something objectively pass/fail testable | Invent a new rule. An oracle tests a principle; it never creates one |
| [Governance Exception / Waiver](GOVERNANCE-EXCEPTION-WAIVER.md) | `GOV-X-` | Authorize one bounded, expiring deviation without weakening the rule globally | Create a precedent, or park a permanent deviation |

Record IDs are permanent and citable. Never renumber one to keep filing tidy —
gaps and out-of-order landmark numbers are normal and expected
(`amendment-and-ratification.md`, "ADR identity is durable, not filing-order").

---

## Routing — which home does this rule belong in?

This family sits beside two existing structures and must not compete with them.

```
Is it a reusable invariant about a DEVELOPMENT WORK DOMAIN
(Composer, GO conversation, Developer Mode, CCN, page templates,
 Spin, deployment, repo safety)?
        └── YES → a Standing Contract (CIC-*). Not a GOV-P.

Is it a rule about the BEEHIVE domain-object model
(provenance, authority, temporal validity, project isolation)?
        └── YES → constitutional-invariants.md, via its own
                  ratification process. Not a GOV-P.

Is it an operating/safety practice for working ON this repository?
        └── YES → CLAUDE.md. Not a GOV-P.

Is it an implementation inventory or current-state record?
        └── YES → governance/current/. Not a GOV-P.

Otherwise — a durable cross-cutting rule with no existing home,
or one canonical statement that several contracts each cite?
        └── GOV-P.
```

A `GOV-P` that merely restates a `CIC-*` invariant is duplication, and duplication
is how two authorities start disagreeing. When a principle already lives in a
contract, cite the contract.

---

## Status vocabulary

Deliberately small, and reused from what already exists rather than invented.

| Status | Meaning |
|---|---|
| `DRAFT` | Being written. No authority. |
| `PROPOSED` | Complete and submitted for approval. **Still no authority** — the normal state of a `GOV-CN-` and of a `GOV-CR-` awaiting a Product Owner decision. |
| `CURRENT` | Approved and governing. |
| `SUPERSEDED` | The identified earlier rule no longer governs *within the stated superseded scope*. A partial supersession leaves every unaffected part in force. |
| `ABSORBED` | The governing concept continues through an identified successor rather than ending. |
| `WITHDRAWN` | Proposed, then retracted before approval. Preserved, never deleted. |
| `EXPIRED` | `GOV-X-` only: a waiver that reached its expiry or review condition without renewal. The governing rule applies again in full. |

`SUPERSEDED` and `ABSORBED` carry exactly the meanings
`amendment-and-ratification.md` already ratified. Both must identify scope and
successor — similarity or overlap alone is neither.

Compatible neighbours, unchanged: the Prompt Register's
`DRAFT`/`APPROVED`/`RUN`/`DEFERRED`/`SUPERSEDED`/`ABSORBED`, the contract
registry's `CURRENT`, and the Canonical Implementation Order's compliance results
`PASS`/`PARTIAL`/`NOT APPLICABLE`/`CONFLICT`.

---

## Governance delta

Every record and every implementation order ends with exactly one:

| Value | Meaning |
|---|---|
| `UNCHANGED` | Governance was applied, not modified. |
| `ADDITIVE` | New governance added; nothing existing altered. |
| `CHANGE PROPOSED — NOT APPLIED` | An amendment is on the table and has **not** taken effect. |
| `CONFLICT FOUND — STOPPED` | Work stopped rather than reinterpret approved governance. |

---

## Lineage rules

1. **Never edit an approved record in place** to change its meaning. Create the
   successor, state what it supersedes and the semantic delta, and leave the prior
   wording readable.
2. **Never delete a superseded record.** It stays, marked, so citations to it stay
   resolvable.
3. **Corrections to a factual error** in a record are non-destructive: leave the
   original sentence, add an adjacent dated correction. Do not silently repair.
4. **Precedence** is unchanged and set elsewhere: explicit current Product Owner
   instruction → current approved governance → applicable standing contract/version
   → order-specific detail → implementation convenience.
5. **A conflict surfaces; it never self-resolves.** File a `GOV-CR-`.

---

## Using these with implementation orders

Governance says **what must remain true**. An implementation order says **what an
agent is authorized to do now**. They are different documents and must stay so.

An order cites governance by ID and version instead of restating it:

```text
APPLICABLE GOVERNANCE
GOV-P-004 v1.0
GOV-X-002 v1.0   (expires 2026-09-15)

APPLICABLE STANDING CONTRACTS
CIC-REPO-SAFETY v1.0
CIC-COMPOSER v1.0
```

Cited records are reported against on completion using the Canonical
Implementation Order's existing compliance vocabulary — `PASS` · `PARTIAL` ·
`NOT APPLICABLE` · `CONFLICT` — with concise evidence. A knowingly `PARTIAL` or
`CONFLICT` result on a mandatory invariant requires explicit Product Owner
acceptance before the work is called complete.

---

## Keeping this cheap

Not every decision needs a record. File one when the reasoning would otherwise
have to be reconstructed from conversation, when an implementer could reasonably
drift without it, or when something is being deviated from. A repository of
records nobody reads is worse than no repository at all.

## Expressiveness validation

These templates were tested against real existing ARCHIOSK governance before being
filed. Recorded so the exercise is not repeated from scratch. **No existing record
was rewritten**; the point was to find out what the forms can and cannot express.

| Existing governance | Correct home | Result |
|---|---|---|
| "Composer is the primary toolbox" (`CIC-DEVELOPER-MODE` v1.0) | Stays in the contract | Routing correctly **declines** it — single-domain invariant |
| "CCN is contemplated intent, not implementation authorization" (`CIC-CCN` v1.0) | Stays in the contract | Routing correctly declines it |
| Developer Mode applies GO reflexively to ARCHIOSK (`CIC-DEVELOPER-MODE` scope) | Stays in the contract | Routing correctly declines it |
| Progressive template discipline (`page-surface-template-inventory.md`, `CIC-PAGE-TEMPLATE`) | Stays where it is | Implementation inventory, not a principle record |
| Deep Ocean accepted visual baseline (`CLAUDE.md`) | Stays in `CLAUDE.md` | Confirms not every principle must migrate here |
| **"Selection is context, not authorization"** | **`GOV-P-` candidate** | `CIC-DEVELOPER-MODE` says *"selection is context, not authorization"*; `CIC-CCN` says *"selection never authorizes mutation"*. Same rule, two wordings, two contracts — exactly the case a single canonical `GOV-P-` exists to prevent drifting apart |
| No Teacher/Oracle leakage (`CIC-SPIN-INTELLIGENCE` v1.0) | **`GOV-I-` candidate** | The contract states the invariant; it has no pass/fail condition and no leakage check. The blind-oracle separation section supplies both |
| Mission 02 accepted doctrine departures (Airlock record) | **`GOV-X-` shape** | Maps cleanly — bounded scope, and the record already states *"creates no precedent for a later mission"*. **Gap surfaced:** it carries no expiry or review condition, which this template makes mandatory |
| Airlock stale-floor correction (`CLAUDE-AIRLOCK-AUTH-02`) | Not a supersession | Correctly excluded — a non-destructive factual correction, which `GOV-S-` explicitly carves out |
| Mission 02 execution hold (`CLAUDE-AIRLOCK-M02-HOLD`) | `GOV-D-` near-fit | **Gap surfaced:** "authorized but conditioned pending preconditions" has no dedicated form. A decision record carries it adequately; a distinct template was **not** created for a single instance |

**Two gaps found, neither closed here:** waivers already in force without an expiry,
and the "authorized but held" shape. Both are reported rather than silently
designed around — creating an eighth template for one observed instance would be
exactly the bureaucracy this family is meant to avoid.

---

## Register

| ID | Title | Type | Version | Status | Record |
|---|---|---|---|---|---|
| [GOV-P-001](../records/GOV-P-001.md) | Selection is context, not authorization | Governance Principle | v1.0 | CURRENT | [Record](../records/GOV-P-001.md) |

Add one row per record created from a template. The register is an index, never a
replacement for the record.
