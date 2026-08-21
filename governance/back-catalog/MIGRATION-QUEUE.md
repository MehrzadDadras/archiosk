# Migration Candidate Queue

Audit artifact. Index: [`README.md`](README.md). **Authorizes nothing.**

Every item is a recommendation awaiting a Product Owner-approved mission. Nothing
here may be actioned on the strength of this file.

**Priority meaning.** `P0` current ambiguity/drift/conflict that can affect
implementation now · `P1` canonicalization would materially reduce repeated drift ·
`P2` worth normalizing when adjacent work touches it · `P3` leave alone.

**Age is not priority.** The 18 `DEFERRED` prompt records and the 13 commissioning
stage records are the oldest material in the corpus and are all `P3`. They are
settled, correctly filed, and cost nothing where they sit.

---

## P0 — active risk (4)

| ID | Item | Why now | Proposed action |
|---|---|---|---|
| **MQ-P0-01** | **DC-01** — "selection is context, not authorization" vs "selection never authorizes mutation" | Two equal-authority v1.0 contract invariants, two texts, no parent. An order citing only `CIC-CCN` inherits the narrower rule | File **`GOV-P-001`**; both contracts cite it at their next version bump. **Do not edit either contract in place** |
| **MQ-P0-02** | **OG-01** — PSD Teacher/Oracle key has no pass/fail condition and separation is asserted, not enforced | A leaked oracle reports success. This is live PSD/Airlock work, not hypothetical | File **`GOV-I-001`** with pass/fail + leakage check. Raise placement separately |
| **MQ-P0-03** | **LC-01** — Camel record reads NOT AUTHORIZED while `STATUS.md` records MM1–MM9 IMPLEMENTED | A reader arriving at the file first gets the wrong answer about built capability | Dated status clarification on the record, matching the `spin-project-intelligence-preview.md` precedent. **Not a supersession** |
| **MQ-P0-04** | **GBC-0026** — `GO-EXTERNAL-VESTIBULE-01` is `DEFERRED` yet its Airlock/Vestibule distinction is load-bearing for three live mission authorizations | A `DEFERRED` record is doing current authoritative work. Status and use disagree | Either promote the distinction to a `GOV-P`, or correct the record's status. **Product Owner call** |

## P1 — high value (6)

| ID | Item | Why | Proposed action |
|---|---|---|---|
| MQ-P1-01 | **DC-03** — model-backed/canonical-path stated three ways in three contracts | Nothing unguarded today, but a fourth surface needs a fourth restatement | `GOV-P` cited by `CIC-COMPOSER`, `CIC-GO-CONVERSATION`, `CIC-SPIN-INTELLIGENCE` |
| MQ-P1-02 | **DC-04** — panel visibility ≠ data lifecycle, owned by one UI contract | Cross-cutting guarantee touching CCN, conversation and evidence lifecycles | **DONE 2026-08-21** — [`GOV-P-002`](../records/GOV-P-002.md) v1.0, filed for the *allocation* gap after investigation found the lifecycle half already well covered. See DC-04's outcome note |
| MQ-P1-03 | **WG-01** — Mission 02 doctrine departures have no expiry or review condition | Stands indefinitely if Mission 02 is never executed | `GOV-X-001` with a Product Owner-supplied review condition. **Invent no date** |
| MQ-P1-04 | **LC-03** — Airlock mission chain readable only by reading 617 lines in order | Six partial supersessions recorded in prose, never as lineage | One `GOV-S` recording the chain. Changes nothing |
| MQ-P1-05 | `canonical-implementation-order.md` has no `APPLICABLE GOVERNANCE` line | `GOV-*` records cannot be cited by orders until it does | One paragraph + one line in the short-form example |
| MQ-P1-06 | **14 `specified-unbuilt/` files carry no authorization marker** | Authority exists only in `STATUS.md`. A reader opening the file cannot tell whether it is authorized | Add the standard `**NOT AUTHORIZED**` marker where `STATUS.md` supports it. **Mechanical, evidence-backed, no meaning change** |

The 14: `add-addendum-facility`, `conversation-thread-lifecycle`,
`cross-boundary-architecture`, `go-learning-01-body-of-knowledge`,
`investigation-lifecycle-extensions`, `metamorphosis-and-dormancy`,
`organizational-security-department`, `per-item-attention-review-state`,
`peripheral-activity-dots`, `perspective-and-contract-dna`,
`presentation-intelligence`, `security-policy`,
`tenancy-and-project-authorization`, `voice-conversational-presence`.

⚠️ Three of these are **partially implemented** (`cross-boundary-architecture`,
`voice-conversational-presence`, `perspective-and-contract-dna`'s
`ReferenceStandard`). A blanket NOT AUTHORIZED stamp would be **wrong** for them.
They need per-record wording drawn from `STATUS.md`, not a bulk edit.

## P2 — useful when adjacent work touches it (7)

| ID | Item | Action |
|---|---|---|
| MQ-P2-01 | **DC-02** — "primary Composer" means two things | Disambiguate at next contract version bump. No governance record |
| MQ-P2-02 | **OG-02** — 17 constitutional invariants, zero oracles | Two or three `GOV-I`, not seventeen |
| MQ-P2-03 | **OG-03** — Spin blind-test and Helix QA prohibitions untested | Fold into MQ-P0-02 where methods overlap |
| MQ-P2-04 | **GBC-0079** — protected oracle filed in the general prompt depository | Placement review. Product Owner call |
| MQ-P2-05 | **GBC-0005** — spare-parts lifecycle grammar (Active/Reserve/Prototype/Future/Scrap) | Useful vocabulary living in one parked-components file. `GOV-P` candidate |
| MQ-P2-06 | **GBC-0003** — `STATUS.md` carries no status marker of its own | One line |
| MQ-P2-07 | **WG-03** — synthetic-identity "unless a test requires it" is self-judged | File a `GOV-X` at first invocation, not before |

## P3 — leave alone (majority of the corpus)

18 `DEFERRED` prompt records · 13 commissioning stage records · 4 CA1 stage
records · `pilot-*`, `meta-t01*`, `wb1` · `history-mapping.md` ·
`GEMINI-HELIX-QA-CLARIFICATION-01` (verbatim external source, correctly isolated) ·
LC-05's five implicit historical chains · the `SUPERSEDED` Holodeck record.

**Approximately 60 of 121 records are correctly filed and need nothing.** That is
the healthiest finding in this audit and is worth stating plainly: the corpus is
not disorganized. It has a **missing layer** (canonical `GOV-*`) and a **status-marker
gap**, not a filing problem.

---

## Re-evaluating the three previously proposed first filings

The mission asks whether `GOV-P-001` / `GOV-I-001` / `GOV-X-001` remain the best
first candidates now that the full corpus is mapped.

| Proposed | Verdict | Reasoning |
|---|---|---|
| **`GOV-P-001` — selection is context, not authorization** | ✅ **FILED 2026-08-20** | The only *confirmed* drift between two equal-authority current contracts. See the record's own dated verification correction — the positive half proved better covered than first reported, on the Developer Mode path only |
| **`GOV-I-001` — Teacher/Oracle blindness** | ✅ **Confirmed, and stronger than assumed** | The audit found the actual oracle record (`CODEX-PSD-TEACHER-ORACLE-02`), which is more substantial than the contract invariant that named it — frozen basis, hash, explicit never-ingest rule — and confirms the missing pass/fail and enforcement |
| **`GOV-X-001` — Mission 02 departure/waiver** | ⚠️ **Confirmed with a caveat** | Right target, but it **cannot be filed without a Product Owner decision**: the missing element is an expiry/review condition, and this audit may not invent one. File it as a Product-Owner-input item, not an agent-authored record |

**One candidate the earlier recommendation missed:** MQ-P0-04
(`GO-EXTERNAL-VESTIBULE-01` `DEFERRED` while load-bearing). It is arguably a
sharper P0 than `GOV-X-001`, because a status/use contradiction misleads a reader
today, whereas the missing waiver expiry only bites if Mission 02 stalls.

---

## Recommended next single normalization mission

> **File `GOV-P-001` — "Selection is context, not authorization" — and add the
> `APPLICABLE GOVERNANCE` line to the Canonical Implementation Order.**

One principle record plus one paragraph. Deliberately the smallest possible
increment, chosen because:

- it resolves the corpus's only **confirmed** drift between two live authorities;
- it is the first end-to-end exercise of the whole chain — `GOV-P` filed, register
  row added, two `CIC` contracts citing it, an order able to cite it;
- **it proves the template family in use.** A template family with no records filed
  against it is untested in the only way that matters;
- it touches no historical record, moves no file, and changes no meaning.

**Explicitly not in that mission:** the 14 status markers (MQ-P1-06 — mechanical
but needs per-record judgment for the three partially-implemented ones), the Camel
clarification (MQ-P0-03 — needs Product Owner confirmation of which record
governs), and `GOV-I-001`/`GOV-X-001` (each deserves its own bounded mission).

**Sequence after that:** MQ-P0-02 (`GOV-I-001`) → MQ-P0-03 + MQ-P0-04 (both Product
Owner decisions) → MQ-P1-06 (status markers) → MQ-P1-01/02 (remaining `GOV-P`s).

---

## Known limits of this audit

- **~8,000 lines of historical stage records** (`comm-*`, `ca1*`, `pilot-*`,
  `meta-t01*`, `wb1`) were classified from headers, status markers and `STATUS.md`
  rather than read end-to-end. All are historical and none is proposed for
  migration — but a principle buried inside one would not have been found.
- **Drift detection covered governance and root files, not the test suite.** A
  principle stated only in a test docstring is out of scope here.
- **Domain assignment is single-primary.** Records spanning domains (the Airlock
  record touches D04, D10 and D12) are counted once.
- **No record's meaning was interpreted where its wording was ambiguous.** Those
  are `UNCLEAR` in the register, not resolved.
