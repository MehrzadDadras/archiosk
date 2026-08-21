# Drift Clusters, Supersession Chains, Waiver and Oracle Gaps

Audit artifact. Index: [`README.md`](README.md). **Governs nothing, resolves nothing.**

Nothing here is resolved. Clusters are reported with locations and wording so a
later Product Owner-approved mission can normalize one at a time.

---

# Part 1 — Drift clusters

Found by extracting all 9 `CIC-*` `MANDATORY INVARIANTS` fields mechanically and
comparing them, then tracing each idea outward through `governance/` and root
files. Not found by impression.

---

## DC-01 · Selection confers context, not authority — **confirmed drift**

**Core principle.** Selecting or focusing on something supplies context to the
system. It never grants permission to change anything.

| Location | Exact wording | Authority |
|---|---|---|
| `CIC-DEVELOPER-MODE` v1.0 | "selection is context, not authorization" | CURRENT contract invariant |
| `CIC-CCN` v1.0 | "selection never authorizes mutation" | CURRENT contract invariant |

**Wording difference.** The first is a statement about what selection *is*; the
second about what it *cannot do*. They are close but not identical: "context, not
authorization" also implies selection must *reach* the model as context — a
positive obligation the second wording does not carry.

**Authority difference.** None — both are v1.0 CURRENT mandatory invariants of
equal standing. That is the problem: two equal authorities, two texts, no parent.

**Risk.** Real, and near-term. An implementation order citing only `CIC-CCN` gets
the narrower rule and could legitimately conclude that selection need not be fed to
the model at all. Neither contract can be amended without the other silently
diverging further, because neither is derived from the other.

**Recommended canonical home.** A single `GOV-P` stating the rule once, cited by
both contracts, with each contract keeping its own domain-specific application.
Note it is also structurally adjacent to constitutional invariant #2 (*machine
inference never silently becomes authority*) — the `GOV-P` should say whether it is
a domain-layer application of #2 or an independent interaction rule. **It is not
obvious which, and this audit does not decide it.**

---

## DC-02 · "Primary Composer" — two different rules sharing a word

| Location | Wording | Means |
|---|---|---|
| `CIC-COMPOSER` v1.0 | "One primary Composer" | one canonical input widget per surface |
| `CIC-DEVELOPER-MODE` v1.0 | "Composer is the primary toolbox" | Composer is Developer Mode's main entry point |

**Not a duplicate — a collision.** These are different claims wearing the same
adjective. Risk is misreading rather than divergence: a reader citing "primary
Composer" may believe they have cited both.

**Recommended.** No `GOV-P`. Disambiguate wording at the next contract version
bump. Filing a governance record for a vocabulary collision would be overkill.

---

## DC-03 · Intelligence must reach the real model by the canonical path

| Location | Wording |
|---|---|
| `CIC-COMPOSER` v1.0 | "canonical submission path"; "model-backed behavior where intelligence is implied" |
| `CIC-GO-CONVERSATION` v1.0 | "ordinary intelligence reaches the canonical model path"; "canned fallbacks never swallow clear questions" |
| `CIC-SPIN-INTELLIGENCE` v1.0 | "Spin is genuinely model-backed"; "governed project evidence reaches the model" |

**Three contracts, three wordings, one idea:** no fake intelligence, no
short-circuit, no canned substitute — and the evidence must actually arrive.

**Risk.** Moderate. Each contract enforces it in its own domain, so nothing is
currently unguarded. But there is no single statement to cite, and a fourth
surface added tomorrow would need a fourth restatement — which is how the count
gets to five before anyone notices.

**Recommended canonical home.** One `GOV-P` ("intelligence is genuinely
model-backed and reaches the canonical path"), cited by all three. Strong
candidate, second only to DC-01.

---

## DC-04 · Panel visibility is not data lifecycle

Currently single-sourced in `CIC-PANEL` v1.0: *"Panel visibility is not data
lifecycle; closing never deletes data, ends conversation, cancels CCN, or clears
evidence. Menus are the canonical machinery/restoration path where available."*

**Not yet drifted** — but it is a cross-cutting interaction guarantee touching
CCN, conversation and evidence lifecycles, currently owned by a single UI contract.
The Product Owner's own formulation, *"Panels show the work. Menus hold the
machinery,"* appears **nowhere in the repository** in that form.

**Risk.** Low today, structural tomorrow: the natural place for a future
conversation-lifecycle contract to restate this is its own invariant list.

**Recommended.** `GOV-P` candidate, P1. Pre-empt the drift rather than record it
after the fact.

> **Outcome (2026-08-21, `CLAUDE-GOVERNANCE-CLOSEOUT-01`).** Resolved by
> [`GOV-P-002`](../records/GOV-P-002.md) v1.0 — but the investigation **narrowed this
> cluster's own finding**. The *lifecycle* half DC-04 flagged (closing ≠ deleting,
> menus as restoration path) turned out to be well covered and consistent across
> `CIC-PANEL` v1.0 **and** `current/panel-template-system.md`'s "Panel behavior
> principles" — single-sourced, but not drifted and not missing. The genuinely
> unstated half was **allocation**: nothing prevented a menu or configuration surface
> from accumulating substantive work, and `CIC-PANEL`'s own `APPLIES WHEN` clause
> would not have reached such a change. GOV-P-002 covers allocation only and amends
> neither existing record.

---

## DC-05 · Machine inference never silently becomes authority — **healthy layering, not drift**

Appears in seven records: `constitutional-invariants.md` #2 and #7,
`CIC-SPIN-INTELLIGENCE` ("no model-memory authority"),
`external-intelligence-airlock.md` ("no silent AI-to-authoritative promotion"),
`GO-EXTERNAL-VESTIBULE-01`, `kernel-object-model.md`,
`camel-multimodal-programme.md`, `STATUS.md`.

**This is what correct layering looks like.** A constitutional invariant with
domain-specific applications beneath it, each citing upward. Included here as the
**contrast case**: DC-01 and DC-03 look like this but lack the parent record. The
difference between drift and healthy specialization is whether a canonical parent
exists.

**Recommended.** No action. Use as the reference pattern.

---

# Part 2 — Supersession and lineage

## LC-01 · Camel MM1–MM9 — status conflict, not supersession · **P0**

- `specified-unbuilt/camel-multimodal-programme.md` — reads **NOT AUTHORIZED**
- `STATUS.md` — records MM1 through MM9 each **IMPLEMENTED, bounded**, with commits

**Classification: UNCLEAR.** This is not a supersession — it is a live record whose
own authorization marker contradicts the programme table. A reader arriving at the
file first gets the wrong answer.

`spin-project-intelligence-preview.md` faced the identical problem and solved it
with a dated "Current-status clarification" blockquote at its head. That precedent
exists and is cheap.

**Recommended.** Not a `GOV-S`. A dated status clarification on the Camel record,
matching the existing precedent. **Do not mark it superseded** — the specification
is still the design of record for what was built.

## LC-02 · Holodeck → Project World · **the only explicit chain**

```
CLAUDE-HOLODECK-WORLDS-SPIN-01   Status: SUPERSEDED
        │  scope: PM-facing terminology only
        ▼
CLAUDE-PROJECT-WORLD-NAMING-01   Status: RUN
```

**Classification: PARTIAL SUPERSESSION** — correctly recorded, with scope named
("only its PM-facing use of *Holodeck* was later corrected"). The predecessor is
preserved. **This is the corpus's model example**, and the only one of its kind:
1 explicit supersession across 121 records.

**Recommended.** None. Cite as the reference pattern.

## LC-03 · Airlock mission chain — implicit, needs recording · **P1**

```
external-intelligence-airlock.md  (NOT AUTHORIZED, CLAUDE-CGP-02)
        │
        ├─ CLAUDE-AIRLOCK-AUTH-01    Mission 01   partial authorization
        │       └─ supersedes the blanket NOT AUTHORIZED "only to the extent Mission 01 requires"
        ├─ CLAUDE-AIRLOCK-AUTH-02    stale-floor correction (non-destructive)
        ├─ CLAUDE-AIRLOCK-M01A-AUTH  Mission 01A  delivery route
        ├─ CLAUDE-AIRLOCK-M02-AUTH   Mission 02   + 2 accepted doctrine departures
        ├─ CLAUDE-AIRLOCK-M02-HOLD   execution hold; Condition A satisfied by 22ec1ff
        └─ CLAUDE-PSD-FOUNDATION-01  Condition B restated (real → synthetic identity)
```

**Classification: PARTIAL SUPERSESSION, repeated, recorded in prose but never as
lineage.** Each step correctly says what it supersedes and preserves prior wording,
but reconstructing the chain requires reading 617 lines in order. The original
"Authorization status: both concepts are NOT AUTHORIZED" paragraph still stands
verbatim, correctly, and is now contradicted by three later sections that each
narrow it.

**Recommended.** One `GOV-S` recording the chain as lineage. Nothing changes; the
chain becomes readable without a full-document read.

## LC-04 · Governance-process deferral → template family · **ABSORBED, recorded**

`amendment-and-ratification.md` deferred change-proposal review,
conflict-escalation and risk-acceptance → `governance/templates/` `GOV-CN`/`GOV-CR`/
`GOV-X`. Pointer added 2026-08-20, original deferral preserved verbatim.
**Correctly recorded. No action.**

## LC-05 · Implicit chains with no explicit record

| Predecessor | Successor | Type | Recorded? |
|---|---|---|---|
| `meta-t01-territory-before-ontology` | `meta-t01-rc1-targeted-recommissioning` | HISTORICAL PREDECESSOR | prose only |
| `comm-i4` | `comm-i4a` (OPR-2.5 correction) | PARTIAL SUPERSESSION | prose only |
| `comm-i5` | `comm-i5a` (OPR-5.3 correction) | PARTIAL SUPERSESSION | prose only |
| `comm-i6` | `continue-01` (OPR-7.2 re-audit) | HISTORICAL PREDECESSOR | prose only |
| `pilot-readiness-postcamel-p01` | `pilot-operating-plan-postcamel-p01` | ABSORBED | prose only |

All five are closed historical sequences with no current authority. **Recommended:
leave alone.** Recording lineage for settled history is cost without benefit — the
`-a`/`-rc1` naming already encodes the relationship.

---

# Part 3 — Waiver / exception gaps

Search terms: exception, temporary, authorized departure, held, waiver, special
case, one-time, pilot, test-only, synthetic, approved deviation, until, pending.

**Important negative result.** "Deviation" occurs ~25 times across `comm-*`, but
in every case as a *domain* term — a design deviation from Owner requirements
under commissioning assessment. **None is a governance waiver.** Classifying them
as such would have manufactured twenty-five phantom exceptions.

Three genuine waiver-shaped items exist. None is filed as a waiver.

## WG-01 · Mission 02 accepted doctrine departures · **P1**

> "This acceptance extends to Mission 02 only and creates no precedent for a later
> mission." — `external-intelligence-airlock.md`

Two Mission 01A boundaries were relaxed for Mission 02 by explicit Product Owner
acceptance: evidence-item count (1 → up to 5) and the single-provision assumption.

| Check | Result |
|---|---|
| Scope bounded | ✅ Mission 02 only |
| Precedent excluded | ✅ explicitly |
| Authority named | ✅ Product Owner |
| **Expiry / review condition** | ❌ **absent** |
| Compensating controls | ⚠️ implicit (closed concept list) — not labelled as such |
| Closure / outcome | ❌ absent |

**Gap: no expiry.** If Mission 02 is never executed, this acceptance stands
indefinitely. **No expiry date is invented here.** What is needed: a Product Owner
review condition — most naturally "on Mission 02 completion or abandonment".

## WG-02 · Mission 02 execution hold · **P2**

Authorized-but-conditioned. Condition A satisfied (`22ec1ff`); Condition B open.

**Not a waiver** — it restricts rather than permits. Flagged because it has **no
form in the template family**; `GOV-D` is the workable near-fit. Already recorded
as a known gap in `templates/README.md`. One instance does not justify an eighth
template.

## WG-03 · Synthetic test-project identity · **P2**

`CLAUDE.md`: real identifiers "do not become canonical test-project identity
**unless a test specifically requires one of them as source evidence**."

That clause is a standing, open-ended, self-judged exception inside an otherwise
firm rule. Not wrong — but it is the shape that erodes quietly, because whoever
invokes it also decides whether it applies.

**Gap:** no review condition, no record of invocation. **Recommended:** if invoked,
file a `GOV-X` at that moment. Nothing to do until then.

---

# Part 4 — Oracle / test-governance gaps

## OG-01 · PSD Teacher/Oracle key · **P0 — the strongest GOV-I candidate**

`prompt-depository/CODEX-PSD-TEACHER-ORACLE-02.md`

Self-classified *"protected TEST/ORACLE governance. This record is not project
evidence and must never be ingested into either the Owner or Proponent"* workspace.
Carries a frozen Code basis (O. Reg. 163/24 as amended by 447/24), an effective
date, a retrieved-package SHA-256, and an explicit later-version cross-check that
is deliberately **not** the frozen basis.

| `GOV-I` requirement | Present? |
|---|---|
| Explicit governing principle | ⚠️ implied — `CIC-SPIN-INTELLIGENCE`'s "no Teacher/Oracle leakage" |
| Invariant | ✅ never ingested as project evidence |
| **Pass condition** | ❌ **absent** |
| **Fail condition** | ❌ **absent** |
| Evidence required | ⚠️ hash present; no retention rule for a run |
| Leakage prohibited | ✅ stated plainly |
| Oracle separated from system under test | ⚠️ **stated, not enforced** |

**The gap that matters.** Separation is asserted in prose, in a file living inside
the general prompt depository — the same directory the corpus treats as ordinary
development history. Nothing mechanically prevents ingestion. A leaked oracle does
not produce a wrong answer; it produces a **right answer for the wrong reason**,
and the test then reports success.

**Recommended.** `GOV-I-001`. Supply pass/fail conditions and a leakage check.
Separately consider whether protected oracle material should live outside
`prompt-depository/` — **a Product Owner call, not an audit call.**

## OG-02 · Constitutional invariants have no oracles · **P2**

17 ratified invariants; **zero** have a stated pass/fail condition or named test.
Several are mechanically checkable (#8 project isolation is already enforced by
`services/project_access.py`; #5 non-destructive correction by `Supersession`).

**Recommended.** Do not write 17 oracles. Pick the two or three where a silent
regression would be most damaging and least visible.

## OG-03 · Spin blind-test rules · **P2**

`CIC-SPIN-INTELLIGENCE` carries "no PSD/smoke-specific production steering" and
"truncation and selection are known/testable" — both testable, neither with a
stated condition. `GO-HELIX-QA-01` adds prohibitions (no health score, no universal
LOD mapping) that are also assertions without checks.

**Recommended.** Fold into the OG-01 filing where they share a method; otherwise P2.

## OG-04 · Interaction invariants · **P3**

`CIC-PANEL`'s "closing never deletes data, ends conversation, cancels CCN, or
clears evidence" is four independently testable claims in one sentence. Good `GOV-I`
material once DC-04's `GOV-P` exists — **principle first, oracle second.**
