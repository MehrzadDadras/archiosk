# ARCHIOSK Development Master Schedule — BASELINE SCHEDULE 01

**Status:** BASELINE, authorized by the Product Owner 2026-09-06.
**Revision:** 02E (2026-09-06) — duration unit defined as **Virtual Engineering
Days (VED)**, third clock added, measured velocity recorded. **The logic network
is unchanged from Rev 01.** Rev 02A added the CH0–CH3 milestone ids (§6.2) and
the two-VED-remainder reporting rule (§8.4.4). Rev 02B records **P0 / CH1 as
ACHIEVED** (§6.3) after the rollback path was exercised end-to-end. See the
revision history at the end.
**As-built basis:** the flight-test audit of 2026-09-06 (product completeness
34%, pilot readiness 45%, sovereign intelligence maturity 58%, overall ~42%,
between 33% and 50% DD). Rev 02 does not restate the audit; E1, E2 and D1
completing after it are recorded as activity status, not as a new maturity
figure — a percentage nobody measured is not evidence.
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
| **LOGIC CPM** | *What controls completion **if resources are available**?* | **68–95 VED** of effort (Rev 01 read this as 14–19 calendar weeks; see §8.4) |
| **RESOURCE-LOADED** | *When can we actually finish **with the resources we have**?* | **~125 VED** of effort (Rev 01 read this as ~25 weeks; see §8.4) |

**Neither number is wrong.** CPM assumes unlimited crews and reports the
dependency logic. Resource loading applies the capacity that actually exists.
The gap between them is not padding, error, or pessimism — it is the cost of
having one working resource against a network with genuine parallelism.

Blending them into a single figure would produce a number that answers neither
question, which is the scheduling equivalent of a green test over a wrong
contract.

### 1.0 The duration unit — VIRTUAL ENGINEERING DAYS (VED)

**Product Owner direction, 2026-09-06 (Rev 02).** Every duration in this
baseline is denominated in **Virtual Engineering Days (VED)**.

> **1 VED = approximately one conventional full engineering workday of effort
> under this baseline's original estimating assumption.**

VED measures **effort, not elapsed calendar time.** The distinction was
implicit when this baseline said "working days" and that phrasing was
misleading: it invited the reading that one duration unit equals one day on the
wall, which is not how ARCHIOSK is being built. The Product Owner works
essentially every day and drives multiple AI agents, so effort and elapsed time
decouple — and a single number that silently means both is exactly the kind of
blended figure §1 already refuses.

**No estimate was rewritten.** Every base duration, contingency, float value
and milestone range in this document is the number Rev 01 recorded. Only the
unit's *name* and its *interpretation* changed, so estimates stay comparable
across revisions and the conversion from Rev 01 is the identity.

**This changes no dependency.** Delivery speed is not a reason to relax logic:
predecessors, the critical path and every float value are untouched. See §8.4,
which adds the elapsed clock without disturbing the other two.

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

Virtual Engineering Days (VED — see §1.0; the figures are Rev 01's, unchanged).
`∥` = no predecessor, may start at day 0. Contingency is held as a named line
item, applied **only** where confidence is LOW — never distributed into base
durations.

| ID | Activity | Pred | Base | Cont. | ES–EF | TF | Crit | Status | Conf |
|---|---|---|---|---|---|---|---|---|---|
| A1 | Correct stale supersession docstring | ∥ | 0.5 | — | 0–0.5 | 12 | | NOT STARTED | HIGH |
| E1 | Client construction in degrade path (8 sites) | ∥ | 2–3 | — | 0–3 | 2 | | COMPLETE | HIGH |
| **E2** | Resolve httpx/anthropic/google-genai conflict | ∥ | 2–5 | +1–2 | 0–5 | 0 | ★ | COMPLETE | MED |
| **D1** | Zone-scoped retrieval proof | ∥ | 3–5 | — | 0–5 | 0 | ★ | COMPLETE | MED |
| **G1** | **P0** pilot gate assessment | E1,E2,D1 | 2 | — | 5–7 | 0 | ★ | COMPLETE | HIGH |
| **G2** | Controlled 3–5 user pilot (RFI bounded) | G1 | 15–25 | — | 7–32 | 0 | ★ | NOT STARTED | LOW |
| **G3** | **P1** pilot findings closeout | G2 | 5–10 | +3–5 | 32–42 | 0 | ★ | NOT STARTED | LOW |
| E3 | External-model fault-injection tests | E1 | 3–4 | — | 3–7 | 5 | | NOT STARTED | MED |
| **A2** | Requirement/obligation dependency graph | ∥ | 8–13 | +2–3 | 0–13 | 0 | ★ | COMPLETE¹ | MED |
| A3 | Authority-transition reconstruction | A2 | 5–8 | — | 13–21 | 8 | | PARTIAL | MED |
| **B1** | Change-arrival recognition (Addendum) | A2 | 8–13 | **+3–5** | 13–26 | 0 | ★ | **COMPLETE** | LOW |
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

¹ **A2 is now COMPLETE: B1 is its real production consumer.** §5.1's condition
— "not counted as completed product capability unless a real workflow consumes
them" — is met. `services/change_arrival.py:affected_dependents` calls the A2
query on a production path reached by `routes/workspace.py`'s
`declare_change_arrival_route`, and it preserves rather than flattens the
governed distinctions A2 makes: inferred stays labelled, contradictions are
reported beside dependents rather than inside them, and a human-rejected edge is
never traversed as an accepted dependency.

There is exactly one dependency lookup in this codebase, which was the point of
building A2 as a query layer rather than letting B1 grow its own.

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

| ID | Milestone | Predecessor | Logic (VED) | Definition |
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

### 6.2 Release overlay — CHASSIS milestones CH0–CH3 (Rev 02A)

**Product Owner direction, 2026-09-06.** These are the product-release overlay
from the Chassis Boundary Audit. That audit said explicitly *"Do NOT replace
Baseline Schedule 01. This is a product-release overlay on top of it"* — which
is why no chassis milestone was ever written into this document. Rev 02A records
them here **for identification only**, so the labels stop being ambiguous.

| ID | Milestone | Meaning |
|---|---|---|
| **CH0** | Chassis Boundary Agreed | The Pilot Chassis / Core / future-module split is settled |
| **CH1** | Pilot Chassis Ready | The stable chassis is releasable to a controlled pilot |
| **CH2** | Pilot Chassis Validated | The chassis has survived real pilot use |
| **CH3** | ARCHIOSK Core Release | Core capability envelope released |

**Identifier mapping — the collision this fixes.**

| Old label | New ID | Why it had to change |
|---|---|---|
| C0 | **CH0** | — |
| C1 | **CH1** | Collided with **activity C1**, Change-triggered Spin mode |
| C2 | **CH2** | Collided with **historical activity C2**, drawing coordination, absorbed into B3-B (§4.2) |
| C3 | **CH3** | — |

> **The collision was not theoretical.** Rev 02 answered a question about
> "P0 / C1" using **activity** C1 (Change-triggered Spin mode, TF 4) when the
> **chassis** milestone C1 (Pilot Chassis Ready) was meant. The sentence was
> internally consistent and answered the wrong object, which is exactly why one
> label meaning two things is a defect rather than a cosmetic issue.

**Activity IDs are unchanged.** Activity `C1` keeps its ID; historical activity
`C2` keeps its name in §4.2's absorption note. Renaming activities would break
every reference in this document to preserve a newer overlay, which is backwards.

**These carry no duration, float or predecessor in this network.** They are
release states, not CPM activities, and the audit's own key result was that the
Pilot Chassis and ARCHIOSK Core sit **off the 1.0 critical path**. Do not
schedule against them here.

**Alignment to this network:** CH1 ↔ **P0**; CH2 ↔ **P1**; CH3 has no single
equivalent — the Core envelope is a product scope decision, not a CPM milestone.

### 6.3 P0 / CH1 — ACHIEVED 2026-09-06 (Rev 02B)

**Verdict: PASS.** All five P0 clauses are met against committed, gate-backed,
live-verified evidence.

| P0 clause | Evidence | SHA |
|---|---|---|
| AI failure degrades honestly | Gateway boundary; construction inside the failure boundary; AST carry-through guard. Demonstrated in production, not only in tests — a live Gemini call returned 404 and produced `ran=False` with no 500 | `5637ede` |
| Dependency environment satisfiable | `requirements.txt` installs; `pip check` clean in repository, dev venv and **production**; both providers construct on the live host | `06e9d35` |
| Zone-scoped retrieval / RBAC proof passes | 32 adversarial tests, two actors, marker-based leak detection; whole route table driven unauthenticated | `081cf59` |
| Deploy / rollback healthy | Deploy exercised repeatedly; **rollback exercised end-to-end 2026-09-06** — see below | `06e9d35`, `7d58a97` |
| No known critical public/private leakage | Exactly 10 routes answer an anonymous GET, all intended, now held by an allowlist test; the Help session-id collision was found and closed | `081cf59` |

**The rollback exercise, because a backup nobody restored is a belief.** Product
Owner decision, 2026-09-06: a structurally valid backup was not sufficient for a
real external-user pilot. Exercised end-to-end against the live host —
`/var/www/archiosk-backup-4b5da42` restored over production using
`deploy/DEPLOYMENT.md`'s own documented Rollback procedure verbatim; service
restarted; `/health` 200 locally and publicly; `/` and `/login` served; no
journal errors. The code genuinely reverted (the gateway helper was absent and
the old pins were back), so the exercise tested a real restore rather than a
no-op. Production then returned to `7d58a97` and was re-verified, including a
real Anthropic call through the application's own gateway.

Two properties worth recording, because both are non-obvious and both held:

- **No data was touched.** `instance/` and `.env` are excluded from the rollback
  exactly as they are from a deploy. 28 registry files and 37 MB of project data
  were identical before, during and after; `.env` survived; the SQLite database
  was untouched. There are no migrations between the two builds, so the restore
  was schema-safe.
- **Version skew is survivable.** The rollback deliberately does not revert
  `.venv/`, so pre-gateway code — which constructs provider clients directly in
  four places — ran against the *forward* dependency set. It worked. A rollback
  therefore does not reintroduce the dependency outage that E2 closed, which is
  the failure this exercise most needed to rule out.

**Accepted pilot limitations**, recorded as known and accepted rather than
discovered later:

1. **Gemini is reachable but its configured model id returns 404.**
   `GEMINI_MODEL` is pinned to `gemini-2.5-flash`, which Google no longer serves
   to new users. The dependency path is proven healthy — the client constructs,
   authenticates and reaches the API — and the gateway degrades honestly rather
   than failing. **Not a pilot blocker unless Gemini is presented as supported
   pilot capability.** Model selection is a Product Owner decision and was
   deliberately not changed.
2. **D1 proves project and discipline isolation, not multi-organization
   tenancy.** There is no `Organization` model in this codebase and
   `governance/specified-unbuilt/tenancy-and-project-authorization.md` remains
   unimplemented. The controlled pilot must not be positioned as tenant-isolated.

**CH1 (Pilot Chassis Ready) is achieved with P0.** Next controlling pilot
activity is **G2**. The R1 critical path is unchanged.

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

| Milestone | VED | Rev 01 calendar weeks |
|---|---|---|
| P0 | 5–7 | 1–1.5 |
| P1 | 32–47 | 6.5–9.5 |
| V1 | 31–48 | 6–10 |
| V2 | 43–63 | 9–13 |
| V3 | 66–85 | 13–17 |
| **R1** | **68–95** | **14–19** |

### 8.2 Resource-loaded (1.0 effective resource)

At single-track capacity the parallel paths serialize. Total work across both
paths is ~106 base VED + 17–29 contingency ≈ **~125 VED ≈ ~25 weeks ≈
~6 months** to R1. P0 is substantially unaffected (~1.5–2 weeks) because its
three predecessors are short; **P1 and R1 are the milestones that move.**

### 8.3 Calendar conversion

**No start date is assumed.** If the Product Owner establishes a formal schedule
start date, these durations convert directly into milestone dates. Ranges are
reported rather than single dates because the underlying estimates do not
support false precision.

### 8.4 The third clock — ACTUAL ELAPSED FORECAST (Rev 02)

§1 carried two clocks. Rev 02 adds a third and keeps all three separate:

| Clock | Question | Unit |
|---|---|---|
| **A. LOGIC CPM** | What must precede what? | VED, dependency-ordered |
| **B. VIRTUAL EFFORT** | How much conventional engineering work remains? | VED |
| **C. ACTUAL ELAPSED** | How fast is that effort actually being consumed? | calendar days |

**Never merge them.** A single blended figure is what §1 already refuses;
adding a third clock makes that easier to get wrong, not harder.

#### 8.4.1 Measured delivery velocity — evidence, not impression

Two windows, because they answer different questions and the shorter one is not
a replacement for the longer.

**Evidence window: 2026-07-20 → 2026-09-06 — 48 calendar days, 47 of them with
at least one commit.** That is the whole of this repository's version-controlled
history. The Product Owner reports program activity from early May 2026, and
that is accepted as the program start, but **it is not corroborable from either
repository**: the backend's first commit is 2026-07-20 and the Explorer repo's
is 2026-07-23, itself a single "Initial baseline" commit bundling design
documents authored earlier and never separately dated. May–July effort is real
and is recorded in `governance/history-mapping.md`'s inventory; it is simply not
measurable here, so it is excluded rather than estimated.

**Effort delivered over the evidence window** is derived from this baseline's
own two figures — the 2026-09-06 flight-test audit's maturity percentages and
the ~125 VED remaining to R1 — by proportion:

| Audit measure | Delivered | Implied VED delivered |
|---|---|---|
| Product completeness | 34% | ~64 |
| Overall | ~42% | ~90 |
| Pilot readiness | 45% | ~102 |

→ **~64–102 VED delivered in 48 calendar days.**

> This assumes VED scales roughly linearly with the audit's maturity
> percentages. It does not, exactly. The range is reported instead of a point
> for that reason, and the whole derivation is a **cross-check on order of
> magnitude, not a measurement**.

**A. LONG-RUN OBSERVED VELOCITY — ~1.3–2.1 VED / calendar day.**

**B. RECENT OPERATING VELOCITY — 8–15 VED / calendar day, n = 1 day.**
E1 (2–3) + E2 (3–7 incl. contingency) + D1 (3–5) all closed on 2026-09-06.

#### 8.4.2 Acceleration is NOT demonstrated at program level

The recent figure is roughly 4–11× the long-run one, and applying it as a
multiplier would be wrong. Two independent size-aware measures show the current
period is **not** faster than the historical baseline:

| Month | Active days | Commits / active day | Lines added / active day |
|---|---|---|---|
| 2026-07 (from the 20th) | 10 | 23.4 | ~7,600 |
| 2026-08 | 31 | 17.6 | ~8,290 |
| 2026-09 (to the 6th) | 6 | 16.0 | ~3,440 |

Commit cadence is flat-to-declining and line volume is well down. Recent work
is lower-volume and higher-judgment (governance, UI, dependency repair), so
neither proxy is a good VED meter — but neither supports an acceleration claim
either, and two proxies pointing the same way is enough to refuse one.

**Conclusion: forecast with the LONG-RUN number.** E1/E2/D1 closing inside
budget is evidence about three short, well-specified, HIGH/MED-confidence
infrastructure activities. It is not evidence about B1 (SPECIFIED ONLY),
B3-A/B3-B (NOT STARTED) or D3 — the LOW-confidence carry-through work that
actually controls R1, and which has no prior art here by this baseline's own
risk register.

#### 8.4.3 Revised elapsed forecast

Remaining effort ≈ **~110–117 VED** (~125 baseline less the 8–15 VED of E1, E2
and D1). At the long-run 1.3–2.1 VED/calendar day: **~52–88 calendar days ≈
~7.5–13 weeks.**

That is faster than §8.2's ~25 weeks, and the reason is legitimate rather than
optimistic: §8.2 priced 125 VED at 1.0 VED per **working** day, five days a
week. The measured program runs ~1.3–2.1 VED per **calendar** day across 47 of
48 days. **§8.2 is not withdrawn** — it remains the correct answer to its own
question, which is what a conventional single-track crew would take.

**The binding constraint moves.** Once engineering effort compresses, R1 stops
being effort-controlled:

- **G2 is a 15–25 VED controlled pilot with 3–5 real users.** That is elapsed
  human time and no amount of agent capacity compresses it. Its real duration
  is a Product Owner scheduling input, not derivable here.
- **RWK (5–15 VED)** cannot be predicted before the pilot produces findings.
- **Product Owner decision gates** sit on the path and are not build effort.

So the honest elapsed forecast to R1 is **~8–14 weeks, LOW confidence**, and it
is now dominated by the pilot and the decision gates rather than by engineering
throughput. Refine it after each completed activity rather than trusting the
range.

### 8.4.4 Two VED remainders — never quote one as the other (Rev 02A)

Every report must carry **both**. They answer different questions and differ by
roughly a factor of two, for the same reason §1's two forecasts do.

| | Value | What it means |
|---|---|---|
| **A. Critical-path VED remaining** | **61–98 VED** | Effort along the controlling chain A2 → B1 → B2 → B3-A → B3-B → D3 → G4 → G5. What R1 waits on **if capacity is available**. |
| **B. Total resource-loaded VED remaining** | **~120–200 VED** | Every incomplete activity (19 of them). What matters at 1.0 lane, where off-path work still consumes the only resource. |

**A is the floor, B is the bill.** Quoting A alone understates the work at the
capacity that actually exists; quoting B alone implies dependencies that do not
exist. At 1.0 effective lane the program pays B, not A — that gap is the same
parallelism cost §1 already names.

**A discrepancy this surfaces rather than fixes.** §8.2's headline "~106 base +
17–29 contingency ≈ ~125 VED" sits slightly *below* its own table: summing every
activity's base gives ~111.5 at the optimistic end, so the full table totals
~128.5–216.5 VED. On the §8.2 basis, remaining reads ~110–117 VED; on the
table's own sum it reads ~120–200. Both are quoted above rather than reconciled,
because reconciling them means re-estimating, which Rev 02A is not authorized to
do. Note also that summing pessimistic endpoints across 19 activities is
over-pessimistic in the ordinary way — they will not all land at maximum — so
the top of range B is an envelope, not a forecast.

### 8.5 Parallel-agent capacity (Rev 02)

§1.1 assumed no concurrent agent tracks. Actual observed lanes:

| Lane | Work | Evidence in this repository |
|---|---|---|
| **Claude** | Baseline 01 critical-path application work | All 60 most recent commits carry `Co-Authored-By: Claude Opus 5` |
| **Codex** | Wind Tunnel / AFT test-corpus work | **None.** No Codex-attributed commit exists in this history |
| **Product Owner** | Decisions, briefs, acceptance | The task briefs themselves |

Codex is genuinely working per the Product Owner, but it produces no artifact in
this repository's system of record, and **it closes no Baseline 01 activity
here**. Under §8's own rule, Wind Tunnel work is therefore not counted as
critical-path completion.

**Effective capacity on Baseline 01 activities remains 1.0 lane.** Per §1.1 that
means §8.2/§8.4 re-run and nothing else — no dependency, float or critical-path
value moves. Do not double-count a lane that is not closing activities in this
network.

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
| 02 | 2026-09-06 | Product Owner | Duration unit renamed to **Virtual Engineering Days (VED)** (§1.0); third clock — actual elapsed forecast — added (§8.4); measured delivery velocity recorded (§8.4.1); parallel-agent capacity recorded (§8.5); E1, E2, D1 marked COMPLETE | **LOGIC: NO MOVEMENT.** Elapsed forecast revised from ~25 weeks to ~8–14 weeks on measured long-run velocity |
| 02A | 2026-09-06 | Product Owner | Chassis release milestones recorded as **CH0–CH3** with the C0–C3 mapping (§6.2); reporting must carry **two** VED remainders, critical-path and total resource-loaded (§8.4.4) | **LOGIC: NO MOVEMENT.** No duration, float, status or dependency altered |
| 02B | 2026-09-06 | Product Owner | Rollback path exercised end-to-end on the live host at Product Owner direction; **G1 → COMPLETE**; **P0 / CH1 recorded as ACHIEVED** (§6.3) with the two accepted pilot limitations | **LOGIC: NO MOVEMENT.** G1 sits off the R1 critical path, so R1 does not move |
| 02C | 2026-09-06 | Product Owner | **A2 → COMPLETE** (`83e9e65`) — the governed dependency graph, built as a query layer over the existing Relationship substrate. Status change only | **LOGIC: NO MOVEMENT**, but A2 is the first completed activity **ON** the R1 critical path, so remaining critical-path effort falls 61–98 → 51–82 VED |
| 02D | 2026-09-06 | Product Owner | **A2 → IMPLEMENTED / NEEDS CONSUMER** (§5.1's stricter reading adopted; B1 becomes its first consumer). Baseline gate recovery: a real multi-process durability defect in `services/bridge_queue.py` fixed, and a flaky test contract in `test_perspective_entry_gate_04` corrected | **LOGIC: NO MOVEMENT.** Reliability work discovered BY A2, not part of the R1 network; A2's VED estimate and critical-path position are unchanged |
| 02E | 2026-09-06 | Product Owner | **B1 → COMPLETE** and **A2 → COMPLETE** (B1 is A2's first production consumer, satisfying §5.1). Status only | **LOGIC: NO MOVEMENT.** B1 is ON the R1 critical path, so remaining critical-path effort falls 51–82 → 40–64 VED |

**Rev 02A — what changed, why, and what it deliberately did not touch.**

*What changed.* Two reporting corrections and nothing else. §6.2 records the
chassis release milestones as CH0–CH3 with their mapping from C0–C3. §8.4.4
requires every report to carry the critical-path remainder and the total
resource-loaded remainder as separate figures.

*Why.* Two ambiguities were producing wrong sentences rather than merely untidy
ones. **First**, `C1` named both an activity (Change-triggered Spin mode) and a
chassis milestone (Pilot Chassis Ready), and Rev 02 answered a question about
"P0 / C1" using the activity when the milestone was meant — a fluent, internally
consistent, wrong answer. **Second**, a single "VED remaining" figure was being
quoted where the critical-path number (61–98) and the resource-loaded number
(~120–200) differ by roughly a factor of two and mean different things.

*A correction to how Rev 02 described the chassis milestones.* They were never
"in" this baseline to rename. The Chassis Boundary Audit that defined them said
explicitly *"Do NOT replace Baseline Schedule 01. This is a product-release
overlay on top of it"*, and "chassis" appeared nowhere in this document before
Rev 02A. §6.2 therefore **records them for the first time** under unambiguous
ids; it does not rename an existing entry, and it does not make them CPM
activities — they carry no duration, float or predecessor here.

*Authority.* Product Owner, 2026-09-06.

*Effect on the LOGIC schedule.* **None.** No activity id, duration, contingency,
float, predecessor, status or critical-path entry changed. Activity `C1` keeps
its id deliberately: renaming activities to accommodate a newer overlay would
break every existing reference in this document to protect the newer label.

*Effect on the elapsed forecast.* None. §8.4.3 stands as written.

**Rev 02 — what changed, why, and what it must not be read as.**

*What changed.* A reporting and resource-interpretation refinement only:
terminology (§1.0), a third clock (§8.4), measured velocity from repository
evidence (§8.4.1–8.4.2), a revised elapsed forecast (§8.4.3), observed agent
lanes (§8.5), and three activity statuses.

*Why.* Rev 01's "working days" invited the reading that one duration unit equals
one day of elapsed time. It does not: the Product Owner works essentially every
day (47 of 48 days carry commits) and drives multiple AI agents, so effort and
elapsed time had to be separated before either could be reported honestly.

*Authority.* Product Owner, 2026-09-06.

*Effect on the LOGIC schedule.* **None.** No dependency, duration, contingency,
float value, milestone or critical-path entry was altered. Every number in §5
and §6 is Rev 01's. The conversion from "working days" to VED is the identity —
the unit was renamed and defined, not re-estimated.

*Effect on the RESOURCE-LOADED forecast.* §8.2 stands unchanged as the answer to
its own question. §8.4.3 adds the measured-elapsed answer alongside it.
Effective capacity on Baseline 01 activities is still **1.0 lane** — Codex's
Wind Tunnel work is real but closes no activity in this network and is not
counted (§8.5).

*Effect on P0 / P1 / R1.* P0's three predecessors are complete, leaving G1 (2
VED). P1 remains gated by the controlled pilot. R1's logic critical path is
untouched; only its **elapsed** forecast moved, and it moved because measured
velocity replaced an assumption — not because scope was reduced.

> **What Rev 02 must not be read as.** Recent per-activity speed is NOT program
> acceleration. §8.4.2 records two independent measures showing the current
> period is not faster than July–August. Forecast with the long-run number.
