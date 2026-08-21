# Product Vision & Analogies

Status: current explanatory doctrine family, version 1.0 · Recorded
`CLAUDE-GOV-P-001-AND-VISION-ANALOGY-FAMILY-01`, 2026-08-20

# This directory carries no implementation authority.

Records here explain **why** ARCHIOSK is built the way it is and **how to reason**
about it. They are important, durable, and deliberately powerless.

They live outside `governance/templates/` on purpose. A `VIS-*` or `ANA-*` record
must never be mistaken for a `GOV-*` record, and co-location would have implied
exactly that.

## What these records may do

- explain product intent and destination;
- preserve conceptual lineage and terminology origin;
- help an agent or a new contributor understand the architecture;
- explain *why* a governance record or contract exists;
- link to the `GOV-*`, `CIC-*` and current records that actually govern.

## What these records may never do

- authorize a code change;
- override, narrow, widen or reinterpret governance;
- supersede a `CIC-*` contract;
- override a Product Owner instruction;
- **create an invariant by metaphor.** An analogy that seems to imply a rule
  implies nothing. If the rule is real, it belongs in a `GOV-*` record or a
  contract, stated plainly and without the metaphor.

An implementation order may cite a `VIS-*` or `ANA-*` record **for orientation
only**. Citing one never satisfies, replaces, or excuses an applicable `GOV-*`
record or `CIC-*` contract.

---

## The two record types

| Type | Prefix | Purpose | Mandatory field |
|---|---|---|---|
| [Product Vision Record](TEMPLATE-VIS.md) | `VIS-` | Where the product is going and what that intent enables | `WHAT IT DOES NOT AUTHORIZE` |
| [Analogy / Mental Model Record](TEMPLATE-ANA.md) | `ANA-` | How to reason about a part of the product, by comparison | `DOES NOT MEAN` |

**`DOES NOT MEAN` is mandatory on every `ANA-` record and may never be empty.**
Analogies are powerful because they transfer structure, and dangerous for the same
reason: they transfer structure that does not apply along with structure that does.
An analogy without stated limits is a rule nobody voted for.

### Filed records

| ID | Title | Type | Status | Record |
|---|---|---|---|---|
| VIS-001 | ARCHIOSK is the kiosk | Product Vision | CURRENT | [Record](VIS-001.md) |
| VIS-002 | Tools that make tools | Product Vision | CURRENT | [Record](VIS-002.md) |
| ANA-001 | Composer as service counter, GO as the machinery behind it | Analogy | CURRENT | [Record](ANA-001.md) |

VIS-001 and ANA-001 were filed as **template validation examples**, drawn entirely
from an existing current governance record (`current/developer-mode-ccn.md`).
VIS-002 was filed on explicit Product Owner decision. No provenance was invented for
any of them. Everything else remains a candidate, or a recorded decision **not** to
file — see [`CANDIDATE-REGISTER.md`](CANDIDATE-REGISTER.md).

---

## Where these sit in the authority chain

```
  PRODUCT VISION        VIS-*     explains the destination and the intent
        │                         ── no authority ──
  ANALOGIES /           ANA-*     explains how to reason about the product
  MENTAL MODELS                   ── no authority ──
        │
        │   may influence how governance is FORMULATED
        │   may never bypass, satisfy or override it
        ▼
  CONSTITUTIONAL INVARIANTS       what must remain true, domain-model layer
        │
        ▼
  CANONICAL GOV-* RECORDS         what must remain true, cross-cutting
        │
        ▼
  CIC STANDING CONTRACTS          operational implementation/test obligations
        │
        ▼
  IMPLEMENTATION ORDERS           what an agent is authorized to do now
        │
        ▼
  TESTS / VERIFICATION            demonstrate compliance
```

**The one-way arrow is the whole point.** Vision and analogy flow *into* how
governance gets worded. Nothing flows back out: a well-argued analogy does not
become a rule by being persuasive, and a vision record does not authorize the work
that would realise it.

---

## When a metaphor stops being a metaphor

Some ARCHIOSK vocabulary began as analogy and matured into defined architectural
mechanism. **Airlock** and **Vestibule** are the clear case: they now name a real
movement boundary and a real admission boundary, with governed missions, mandatory
conditions and STOP boundaries attached
(`specified-unbuilt/external-intelligence-airlock.md`,
`prompt-depository/GO-EXTERNAL-VESTIBULE-01.md`).

**Do not demote a formal architectural term into an analogy record.** Where a term
has a governing definition elsewhere, an `ANA-*` record may explain the origin of
the mental model and must link to the formal definition — it never restates it, and
never becomes the place people look it up.

The `CANDIDATE-REGISTER.md` classifies each concept as `VIS`, `ANA`, `FORMAL TERM`
or `UNCLEAR` for exactly this reason.

---

## Preservation

Nothing here replaces anything. Where a concept evolved —

```
early metaphor → recurring product doctrine → formal architectural term → governance
```

— the chain is recorded, and every link stays where it is. A later formal term does
not obsolete the metaphor that preceded it; the metaphor is how the term is still
best explained to someone encountering it for the first time.

No historical wording was rewritten, no prompt relocated, and no analogy removed
because a formal term later existed.
