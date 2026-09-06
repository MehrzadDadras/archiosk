# ARCHIOSK Development Master Schedule — BASELINE SCHEDULE 01

**Status:** BASELINE, authorized by the Product Owner 2026-09-06.
**As-built basis:** the flight-test audit of the same date (product completeness
34%, pilot readiness 45%, sovereign intelligence maturity 58%, overall ~42%,
between 33% and 50% DD).
**Authority:** Product Owner. Recorded by Claude Opus 5.

This is the durable program record. It is **not** a task list and not a backlog.
It records what controls completion, what can run in parallel, what has float,
and what the two finish lines mean.

> **Do not silently overwrite this baseline.** Revisions follow the change
> control at the end of this document. A later schedule may supersede this one
> operationally; it must not erase how or why the forecast moved.

---

## 1. THE TWO SCHEDULE VIEWS — read both, never blend them

This baseline carries two forecasts on purpose. They answer different questions
and disagree by roughly a factor of two. Quoting either alone is a
misrepresentation.

| View | Question it answers | R1 forecast |
|---|---|---|
| **LOGIC CPM** | *What controls completion **if resources are available**?* | **14–19 calendar weeks** (68–95 working days) |
| **RESOURCE-LOADED** | *When can we actually finish **with the resources we have**?* | **~25 weeks / ~6 months** (~125 working days) |

**Neither number is wrong.** CPM assumes unlimited crews and reports the
dependency logic. Resource loading applies the capacity that actually exists.
The gap between them is not padding, error, or pessimism — it is the cost of
having one working resource against a network with genuine parallelism.

Blending them into a single figure would produce a number that answers neither
question, which is the scheduling equivalent of a green test over a wrong
contract.

### 1.1 Assumed effective capacity — the resource basis

The resource-loaded forecast assumes:

- **1.0 effective development resource** — one Claude Code session working
  single-track. Not 1.0 FTE of a human team; the unit is "one agent working one
  activity at a time."
- **The Product Owner is a DECISION resource, not a build resource.** PO time
  gates approvals, acceptances and the two human authority acts in the Script
  chain; it does not add build capacity.
- **Pilot participants (3–5 users) are a TEST resource during G2 only.** They
  consume support effort rather than producing schedule progress.
- **No concurrent agent tracks** (no Codex lane, no second Claude lane).

> **Adding capacity later is a RESOURCE CHANGE, not a float change.**
>
> If a Codex track or a second Claude lane is added, the LOGIC CPM network —
> its dependencies, its critical path, and every float value in it — is
> **unchanged**. Only the resource-loaded forecast moves. Any future revision
> claiming that added capacity "created float" is misreading this baseline:
> float is a property of the dependency logic, and capacity is a property of the
> crew. Re-run the resource loading; do not edit the network.

---

## 2. PRODUCT OWNER SCHEDULE DECISIONS (recorded, 2026-09-06)

1. **The controlled pilot runs BEFORE B1–B3 are complete.** Rationale as given:
   the pilot should expose real workflow conditions that *inform* the design of
   the change-arrival and carry-through engine rather than merely validate a
   design completed in isolation. Automated Addendum handling is an **accepted
   known limitation** during the pilot. B1–B3 proceed in parallel where
   practical.
2. **RFI is IN SCOPE for the pilot, bounded**: create, issue, answer, and
   preserve the governed record/provenance. An RFI answer is **not** required to
   trigger the systemic carry-through sweep during the pilot; that integration
   remains **B5**.
3. **ARCHIOSK 1.0 REQUIRES drawing dependents in carry-through**, staged
   **B3-A** (structured/textual) then **B3-B** (drawings). The dependency model
   must be designed from the start so drawing relationships can participate
   later **without re-architecting B3-A**.
   *Scheduling consequence, stated because it is easy to miss:* this makes
   **A2's design a 1.0-scope commitment, not a B3-A-scope one.**

---

## 3. THE TWO FINISH LINES

### FINISH LINE 1 — CONTROLLED PILOT PRODUCT (P1)

Safe and useful for a tightly controlled 3–5 user external pilot. It does **not**
require every 1.0 capability.

### FINISH LINE 2 — ARCHIOSK 1.0 (R1)

Operationally capable of the sovereign multi-party project-intelligence target:
real project lifecycle; source/authority/provenance integrity; temporal and
supersession history; RFI/Addendum/requirement-change handling; downstream
carry-through; multi-party isolation; trustworthy findings and work products;
auditable decision reconstruction; governed external-AI use; production
resilience.

**100% means operational completion of this defined scope** — not that the
software can never improve again.

---

## 4. LOGIC CPM NETWORK

### 4.1 Controlled Pilot

```
E1 (2–3d) ──┐   TF 2
E2 (2–5d) ──┼──→ G1 (2d) → G2 (15–25d) → G3 (5–10d) → P1
D1 (3–5d) ──┘   both TF 0
A1 (0.5d) ····  TF 12 — parallel, controls nothing
```

**Controlling predecessors: E2 and D1 jointly** (5d each at pessimistic).
**E1 is the shortest of the three and carries 2 days float.** An earlier draft
serialized `E1 → E2`; that was wrong, and the correction is recorded here rather
than quietly applied.

### 4.2 ARCHIOSK 1.0

```
A2 → B1 → B2 → B3-A → B3-B → D3 → G4 → G5 (R1)
        └─→ C1 ───────────────────┘  (TF 4, thin — see 7.2)
G3 ──────────────────────────────→ G5
```

`C2` (drawing coordination in sweep) is **absorbed into B3-B** — it was the same
work under two names, and the Product Owner directed no double-counting.

---

## 5. CPM ACTIVITY TABLE

Working days. `∥` = no predecessor, may start at day 0. Contingency is held as a
named line item, applied **only** where confidence is LOW — never distributed
into base durations.

| ID | Activity | Pred | Base | Cont. | ES–EF | TF | Crit | Status | Conf |
|---|---|---|---|---|---|---|---|---|---|
| A1 | Correct stale supersession docstring | ∥ | 0.5 | — | 0–0.5 | 12 | | NOT STARTED | HIGH |
| E1 | Client construction in degrade path (8 sites) | ∥ | 2–3 | — | 0–3 | 2 | | COMPLETE | HIGH |
| **E2** | Resolve httpx/anthropic/google-genai conflict | ∥ | 2–5 | +1–2 | 0–5 | 0 | ★ | COMPLETE | MED |
| **D1** | Zone-scoped retrieval proof | ∥ | 3–5 | — | 0–5 | 0 | ★ | IMPLEMENTED / NEEDS PROOF | MED |
| **G1** | **P0** pilot gate assessment | E1,E2,D1 | 2 | — | 5–7 | 0 | ★ | NOT STARTED | HIGH |
| **G2** | Controlled 3–5 user pilot (RFI bounded) | G1 | 15–25 | — | 7–32 | 0 | ★ | NOT STARTED | LOW |
| **G3** | **P1** pilot findings closeout | G2 | 5–10 | +3–5 | 32–42 | 0 | ★ | NOT STARTED | LOW |
| E3 | External-model fault-injection tests | E1 | 3–4 | — | 3–7 | 5 | | NOT STARTED | MED |
| **A2** | Requirement/obligation dependency graph | ∥ | 8–13 | +2–3 | 0–13 | 0 | ★ | PRIMITIVE EXISTS / UNWIRED | MED |
| A3 | Authority-transition reconstruction | A2 | 5–8 | — | 13–21 | 8 | | PARTIAL | MED |
| **B1** | Change-arrival recognition (Addendum) | A2 | 8–13 | **+3–5** | 13–26 | 0 | ★ | **SPECIFIED ONLY** | LOW |
| **B2** | Requirement-level supersession linkage | B1 | 3–5 | — | 26–31 | 0 | ★ | PRIMITIVE EXISTS / UNWIRED | MED |
| **B3-A** | Structured carry-through sweep | A2,B2 | 8–12 | **+3–5** | 31–43 | 0 | ★ | NOT STARTED | LOW |
| **B3-B** | Drawing carry-through sweep (absorbs C2) | B3-A | 6–10 | **+2–4** | 43–53 | 0 | ★ | NOT STARTED | LOW |
| B4 | Requirement-level reconciliation | B3-A | 8–13 | — | 43–56 | 3 | | **misnamed today** | LOW |
| B5 | RFI answer → sweep integration | B3-A | 5–8 | — | 43–51 | 6 | | PARTIAL | MED |
| C1 | Change-triggered Spin mode | B1 | 5–8 | — | 26–34 | 4 | | PARTIAL | MED |
| **D3** | Two-sided procurement proof, real corpus | B3-B | 8–13 | **+3–5** | 53–66 | 0 | ★ | IMPLEMENTED / NEEDS PROOF | LOW |
| **RWK** | **Pilot finding / rework allowance** | G3 | 5–15 | — | 42–57 | 0* | ★ | ALLOWANCE | LOW |
| F1 | Training / Clip-Help routing split | ∥ | 3–5 | — | 0–5 | 12 | | PARTIAL | HIGH |
| **G4** | **V3** Addendum-3 scenario end-to-end | B3-B,D3,C1,RWK | 5–8 | — | 66–74 | 0 | ★ | NOT STARTED | MED |
| **G5** | **R1** 1.0 acceptance gate | G4,G3 | 2 | — | 74–76 | 0 | ★ | NOT STARTED | HIGH |
| H1–H5 | 2D/3D expansion, University, voice, polish, Airlock | — | — | — | — | ∞ | | DEFERRED | — |

\* **RWK float is 0 by placement, not by certainty.** It is a declared unknown,
not padding hidden inside another activity's estimate. CPM cannot predict
redesign; inflating B3-A to conceal it would disguise uncertainty as an estimate.

**Total contingency: 17–29 days**, itemised above.

### 5.1 Status classification vocabulary

`COMPLETE` · `IMPLEMENTED / NEEDS PROOF` · `PARTIAL` ·
`PRIMITIVE EXISTS / UNWIRED` · `SPECIFIED ONLY` · `NOT STARTED` · `DEFERRED`

Governance specifications, code comments, test fixtures, prototypes and dormant
code are **not** counted as completed product capability unless a real workflow
consumes them.

---

## 6. MILESTONES

| ID | Milestone | Predecessor | Logic (wd) | Definition |
|---|---|---|---|---|
| **P0** | Pilot Ready | G1 | 5–7 | AI failure degrades honestly; dependency environment satisfiable; zone-scoped retrieval/RBAC proof passes; deploy/rollback healthy; no known critical public/private leakage |
| **P1** | Controlled Pilot Complete | G3 | 32–47 | 3–5 user pilot completed; real workflows exercised; RFI included in bounded form; findings classified; dispositions recorded; closeout complete |
| **V1** | Structured carry-through proven | B3-A | 31–48 | dependency graph + change recognition + supersession linkage + B3-A operational |
| **V2** | Full carry-through proven | B3-B | 43–63 | drawing dependents operational |
| **V3** | Multi-party Addendum scenario proven | G4 | 66–85 | two-sided procurement boundary proven; change-triggered findings work; Addendum scenario completes end-to-end |
| **R1** | **ARCHIOSK 1.0** | G5 | 68–95 | defined 1.0 operational acceptance complete; Product Owner acceptance |

### 6.1 R1 acceptance — the Addendum-3 scenario

1.0 is not complete unless this runs end-to-end:

| Scenario step | Activity | Baseline status |
|---|---|---|
| Ingest with authority/provenance | built | COMPLETE |
| Identify changed requirements | B1 | SPECIFIED ONLY |
| Link supersession | B2 | PRIMITIVE EXISTS / UNWIRED |
| Find dependents | A2 | PRIMITIVE EXISTS / UNWIRED |
| Detect carry-through failures | B3-A, B3-B | NOT STARTED |
| Protect party boundaries | D3 | IMPLEMENTED / NEEDS PROOF |
| Surface findings | C1 | PARTIAL |
| Preserve PM authority | GOV-P-006 | COMPLETE |
| Reconstruct *why* it changed | A3 | PARTIAL |

---

## 7. CRITICAL AND NEAR-CRITICAL PATHS

**Pilot critical:** `E2 ∥ D1 → G1 → G2 → G3`
**1.0 critical:** `A2 → B1 → B2 → B3-A → B3-B → D3 → G4 → G5`

### 7.1 Real float
`A1` (12) · `F1` (12) · `A3` (8) · `B5` (6) · `E3` (5) · `C1` (4) · `B4` (3) ·
`E1` (2)

### 7.2 Merge points where one late activity turns critical
- **G1** — three-way merge. Any of E1/E2/D1 slipping past 5d makes it controlling.
- **G4** — four-way merge of B3-B, D3, C1, RWK. **The highest-risk convergence
  in the schedule.**
- **C1's TF 4 is nominal, not comfortable.** V3 requires change-triggered
  findings, so a B1 delay makes C1 critical silently.

---

## 8. FORECAST

### 8.1 Logic CPM

| Milestone | Working days | Calendar weeks |
|---|---|---|
| P0 | 5–7 | 1–1.5 |
| P1 | 32–47 | 6.5–9.5 |
| V1 | 31–48 | 6–10 |
| V2 | 43–63 | 9–13 |
| V3 | 66–85 | 13–17 |
| **R1** | **68–95** | **14–19** |

### 8.2 Resource-loaded (1.0 effective resource)

At single-track capacity the parallel paths serialize. Total work across both
paths is ~106 base days + 17–29 contingency ≈ **~125 working days ≈ ~25 weeks ≈
~6 months** to R1. P0 is substantially unaffected (~1.5–2 weeks) because its
three predecessors are short; **P1 and R1 are the milestones that move.**

### 8.3 Calendar conversion

**No start date is assumed.** If the Product Owner establishes a formal schedule
start date, these durations convert directly into milestone dates. Ranges are
reported rather than single dates because the underlying estimates do not
support false precision.

---

## 9. RISK REGISTER

| Risk | P | I | Mitigation | Affects |
|---|---|---|---|---|
| Carry-through sweep harder than estimated — no prior art here | HIGH | HIGH | Spike on one requirement type before committing B3-A | B3-A, B3-B |
| google-genai/anthropic conflict re-breaks AI silently | MED-HIGH | HIGH | E2 + a test asserting the pin set is satisfiable | E2 |
| Real project data invalidates assumptions tests never covered | HIGH | MED | This is what G2 is FOR — do not over-harden beforehand | G2, RWK |
| Stale comments misdirect planning (**has occurred twice**) | MED | MED | A1; treat comments as evidence of past state only | A1, A2 |
| Multi-party procurement proof fails on a real corpus | MED | HIGH | D3 early spike against synthetic two-sided data | D3 |
| PO decisions mis-recorded as implementation authority | MED | HIGH | `CLAUDE.md` doctrine; ~1 day of practice so far | all |
| UI diversion | MED | MED | Hard stop after F1 | F1 |
| Overbuilding 2D/3D before workflow demand | LOW-MED | MED | Keep in H until B3-B demands it | H1 |

---

## 10. DELIBERATELY DEFERRED

2D/3D expansion beyond B3-B's needs; ARCHIOSK University; voice; further visual
polish; Airlock beyond authorized missions; Training *implementation* beyond
F1's routing split; B4 unless the pilot demands it.

---

## 11. NEXT WORK PACKAGE (recorded, not started)

1. **A2 — Requirement/obligation dependency graph.** First 1.0 critical-path
   activity, no predecessor, and PO decision 3 makes its design a 1.0-scope
   commitment.

**Parallel pilot track:**
2. **E2 — resolve the AI dependency conflict.**
3. **D1 — zone-scoped retrieval proof.**

`A1` may be bundled with A2 — the author of A2 is the person the stale docstring
misled — but **A1 does not control the schedule** (TF 12, 0.5d) and must not be
reported as if it does.

---

## 12. ASSUMPTIONS, CONFIDENCE, EVIDENCE LIMITATIONS

**Assumptions:** single-track capacity per §1.1; no calendar start date; pilot
participants available when P0 is reached; no change to the 1.0 scope in §3.

**Confidence:** activity identification and sequencing **HIGH** (grounded in
code). Status classifications **HIGH**. Durations **LOW–MEDIUM** — *no velocity
baseline exists for this repository*, so ranges are engineering judgment, not
measurement. B1, B3-A and B3-B carry the weakest estimates **and control the
finish date**.

**Evidence limitations:** these workflows have not been exercised as a user;
float derives from a dependency network constructed for this baseline, not an
empirically validated one; B1/B3 have no comparable prior work in this
repository.

---

## 13. CHANGE CONTROL

Baseline 01 is preserved. Any revision creates **BASELINE SCHEDULE 02** (or a
recorded revision block below) and must state:

- **what changed** — activities, durations, logic, or scope;
- **why** — evidence available at the time;
- **authority** — who directed it;
- **effect on the LOGIC critical path**;
- **effect on the RESOURCE-LOADED forecast** (and whether capacity changed);
- **effect on P0 / P1 / R1**.

A capacity change (adding a Codex or second Claude track) re-runs §8.2 **only**.
It does not alter §4, §5 float, or the critical path — see §1.1.

### Revision history

| Rev | Date | Authority | Change | Effect on R1 |
|---|---|---|---|---|
| 01 | 2026-09-06 | Product Owner | Baseline established | — |
