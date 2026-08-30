# GOV-CR-001 — Redefining Helix as stakeholder-frame shear collides with CIC-SPIN-INTELLIGENCE v1.1

- **GOVERNANCE ID:** GOV-CR-001
- **TITLE:** Multi-Observer Shear Mapping cannot be implemented as "Helix" without amending a CURRENT standing contract
- **TYPE:** Governance Conflict Report
- **VERSION:** v1.0
- **STATUS:** RESOLVED

## Authority

- **RAISED BY:** Claude, under the GO Decision Architecture directive (2026-08-29)
- **DATE RAISED:** 2026-08-30
- **DECISION REQUIRED FROM:** Product Owner

## Request / trigger

Product Owner directive, 2026-08-29, headed *"CODIFY THE GO CONSTITUTIONAL
DECISION ARCHITECTURE"*, opening instruction:

> Implement and enforce the core GO Decision Architecture across
> `services/spin.py`, prompt definitions, and audit reports

Item 3 of five, quoted in full because the conflict is in its detail:

> **3. Multi-Observer Shear Mapping (Helix):**
> - Model findings as divergence between stakeholder frames:
>   `Shear(i, j)_t = g(W_t, O_{i,t}) ⊖ g(W_t, O_{j,t})`
> - Map where distinct rational positions (Architect, GC, Owner) conflict
>   without collapsing disagreement into truth-vs-error.

The other four items are not in conflict and were implemented — see **Safe work
that may continue** below.

## Conflicting governance

| Record | Version | Operative text |
|---|---|---|
| `governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md` — SCOPE | v1.1 | > Spin evidence selection, assembly, model invocation, findings, provenance, and Helix / Progressive Project Convergence assessment. |
| `governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md` — GOVERNING PRINCIPLE | v1.1 | > A project consists of independently evolving but interdependent consequential strands moving toward delivery; coordination quality is demonstrated by how well those strands progressively mesh at the maturity actually being claimed; Spin is GO's governed process for testing that mesh. |
| `governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md` — MANDATORY INVARIANTS | v1.1 | > Helix is an investigative/convergence model, not a universal scoring system; Helix must not silently become a coordination percentage, health score, universal LOD/percentage mapping, universal tolerance table, hard-coded trade hierarchy, project-wide uniform-maturity assumption, or automatic engineering/design correction mechanism; expectation, observation, consequence, and evidence sufficiency remain distinct |
| `governance/constitutional-invariants.md` #15 | — | > **Contract DNA must never masquerade as project authority.** A delivery-model template may suggest expected obligations; only the actual, ingested project contract governs. |
| `governance/constitutional-invariants.md` #10 | — | > **Authority conflicts surface, never resolve silently.** Where two legitimate authorities disagree, the system flags the conflict rather than picking a side. |

## Exact conflict

Two separable breaches, either of which is sufficient on its own.

**1. Subject substitution under a governed name.** CIC-SPIN-INTELLIGENCE v1.1's
governing principle fixes Helix's subject as *interdependent consequential
strands* and how well they *mesh*. Its closed assessment vocabulary is built on
that subject: `dimension_conflict`, `positional_conflict`, `semantic_mismatch`,
`handshake_deficit`, `propagation_lag`, `stage_maturity_mismatch`. Every one
describes a relationship between design or delivery strands.

The directive's Helix has a different subject: divergence between *observers*.
`Shear(i, j)_t` ranges over stakeholder frames, not over strands. Implementing
it under the name Helix, inside a contract whose SCOPE explicitly covers "Helix
/ Progressive Project Convergence assessment", replaces the governed subject of
a CURRENT contract while leaving its name, its vocabulary and its reference
tests in place.

**2. A hard-coded observer set.** `(Architect, GC, Owner)` is a fixed three-party
frame applied to every project. The contract prohibits Helix silently becoming a
"hard-coded trade hierarchy", and the neighbouring prohibition on a
"project-wide uniform-maturity assumption" is the same family: a universal
structure imposed regardless of what the project's own evidence shows.

Constitutional invariant #15 is the sharper problem. Architect / GC / Owner is a
*delivery-model template* — it describes design-bid-build. On an IPD, design-
build, CM-at-risk or progressive-design-build project the parties, and which of
them hold which positions, are different. Hard-coding that triple makes a
delivery-model assumption govern in place of the actual ingested project
contract, which is precisely what #15 forbids.

## Why both cannot currently be satisfied

Four readings were tried before filing.

**Reading A — "shear is a separate concept that merely borrows the name."**
Fails on the contract's own SCOPE clause, which reaches anything in Spin called
Helix. It also fails practically: two different models under one name inside one
module is the ambiguity a closed vocabulary exists to prevent, and
`services/spin.py` would then contain two things called Helix with
non-overlapping meanings.

**Reading B — "add shear values alongside the existing ten assessments."**
Fails on *"expectation, observation, consequence, and evidence sufficiency remain
distinct"*. A stakeholder-divergence value placed in the same `assessment` enum
as `dimension_conflict` makes one field carry two subjects, and a consumer
reading `SpinRun.helix_assessments` could no longer tell whether a record
describes strands failing to mesh or parties disagreeing. Those warrant
different responses.

**Reading C — "Architect/GC/Owner is not a trade hierarchy, so the prohibition
misses."** Narrowly true and it does not rescue the request. The clause's
subject is Helix acquiring a fixed universal frame, and the constitutional #15
breach stands independently of how the CIC clause is read.

**Reading D — "it is only prompt text, so no contract surface changes."** Fails
against the contract's own REFERENCE IMPLEMENTATIONS —
`services/spin.py::_parse_helix_assessments`, `SpinRun.helix_assessments`,
`SpinResult.helix_assessments`. Asking the model for shear requires either a new
persisted field or overloading a closed one; both change the tested surface the
contract names. This reading is also what the report exists to prevent: prompt
text that produces a governed record is not exempt because it is text.

No reading was found under which both the directive and the contract hold.

## Safe work that may continue

Four of the directive's five items do not touch this conflict. All four are
implemented, tested (26 new tests in
`tests/test_go_decision_architecture_01.py`), and independent of the decision
below.

- **Item 4, six-invariant Survival Mode.** `_SURVIVAL_MODE_INSTRUCTIONS`
  restructured into the six ordered triage questions, with the prior attention
  topics preserved verbatim inside question 2. Framing text over the same single
  call; no vocabulary, field or schema change. Question 5 ("which work can safely
  halt") carries an added guard so it is surfaced as an option for a human and
  can never read as a stop-work direction or a project-ending conclusion —
  constitutional invariant #17.
- **Item 1, cognitive stopping**, as *behaviour*, recorded through the closed
  vocabulary that already exists (`indeterminate`, and the abstaining Helix
  assessments `residual_ambiguity` / `evidence_unavailable` /
  `legitimate_deferred`).
- **Item 2, temporal anti-smuggling and observable constraints.** The decision-
  horizon rule (evidence then available, time then remaining, authority then
  held), an explicit hindsight prohibition, and a prohibition on speculating
  about motive, intent or state of mind.
- **Item 5, bounded execution authority.** Already enforced before this
  directive by `BEHAVIORAL_CONTRACT` and constitutional invariant #2. Nothing was
  added; a test now pins it.

**Not part of this conflict, recorded so it is not mistaken for one.** The
directive's item 1 also proposed a four-bin vocabulary,
`[KNOWN] | [UNKNOWN] | [CONTRADICTED] | [TIME-CRITICAL]`. That was not
implemented either, but **no ratified governance forbids it** — it was an
engineering judgment that a second set of bins would give the same unresolved
state two names alongside `KNOWN_SPIN_DELTA_CLASSIFICATIONS` and the abstaining
Helix assessments. It is a design objection, not a governance conflict, and the
Product Owner can overrule it without any governance action at all.

## Blocked work

- **Item 3, Multi-Observer Shear Mapping**, in its entirety — blocked by
  CIC-SPIN-INTELLIGENCE v1.1's SCOPE and MANDATORY INVARIANTS clauses, and
  independently by constitutional invariant #15 as to the hard-coded
  `(Architect, GC, Owner)` frame.

Note what is *not* blocked: the principle behind item 3. *"Map where distinct
rational positions conflict without collapsing disagreement into truth-vs-error"*
is already constitutional invariant #10, and Spin already surfaces authority
ambiguity rather than resolving it. The mechanism is blocked; the intent is
already governed.

## Decision required from Product Owner

| Option | Effect | Governance action needed |
|---|---|---|
| Drop item 3 | Helix stays a strand-convergence model. Stakeholder divergence continues to surface through existing authority-ambiguity findings and constitutional #10, without a dedicated model. | none |
| Re-scope: build shear under its own name, not Helix | Two clearly distinct models. Shear gets its own vocabulary and its own persisted field; Helix is untouched, so its contract, tests and stored records keep their meaning. Observer frames derived from ingested project evidence rather than hard-coded. | `GOV-CN-` amending CIC-SPIN-INTELLIGENCE to v1.2 to add the new concept and state the boundary between the two |
| Amend Helix itself to cover observer divergence | One model with a widened subject. Requires re-deciding what the ten existing assessment values mean, and what `SpinRun.helix_assessments` means in already-stored runs. | `GOV-CN-` amending CIC-SPIN-INTELLIGENCE to v1.2; likely `GOV-S-` for the superseded invariant wording |
| Authorize a bounded exception | Shear built as instructed, time-boxed, on the record as a deviation rather than a rule. Does not resolve the constitutional #15 problem, which a waiver cannot reach. | `GOV-X-` — and a separate constitutional decision for the hard-coded frame |
| Proceed as instructed | Item 3 built as written. Precedent set: a standing contract's governed subject may be replaced by an implementation order without amendment, and a delivery-model template may be hard-coded in place of the ingested contract. That precedent would apply to every other CIC-* and to invariant #15 generally. | explicit Product Owner override, recorded |

**RECOMMENDATION:** **Re-scope — build shear under its own name.** It delivers
what item 3 is actually for (making rational disagreement visible without
adjudicating it) while leaving a CURRENT contract, its closed vocabulary and its
stored records intact; and deriving the observer frames from each project's own
ingested evidence rather than a fixed triple both satisfies constitutional #15
and produces a better answer on any project that is not design-bid-build.

## Resolution

**Product Owner decision, 2026-08-30.** The re-scope recommendation is adopted.

> Helix remains strictly dedicated to physical/interface strand convergence
> (CIC-SPIN-INTELLIGENCE v1.1). Multi-Observer Shear is defined as a distinct
> epistemic analysis layer, fully decoupled from Helix naming. Observer frames
> are derived dynamically from project ingested contracts and roles (IPD parties,
> CM-at-risk, trade contractors) rather than hardcoded to a fixed
> (Architect, GC, Owner) triple.

Both breaches identified above are addressed by this decision, and it is worth
recording which mechanism addresses which: the **subject-substitution** breach by
keeping the two layers separately named and separately vocabularied, and the
**constitutional invariant #15** breach by deriving observer frames from the
project's own ingested evidence.

`GOV-CN-001` carried the amendment this resolution required. It was **approved
by the Product Owner on 2026-08-30**, producing
[CIC-SPIN-INTELLIGENCE v1.2](../current/contracts/CIC-SPIN-INTELLIGENCE-v1.2.md)
and [GOV-S-001](GOV-S-001.md); the notice is now `ABSORBED`.

**The stop on item 3 is lifted and in effect.** v1.2 governs, and it admits a
Multi-Observer Shear layer on the stated terms — its own name, vocabulary, field
and parser; observer frames derived from the project's own ingested contracts and
roles; no adjudication between frames.

One thing this does *not* do: building `services/observer_shear.py` still needs
its own implementation order. v1.2 governs a layer that does not yet exist, which
is the correct order of operations and not an oversight.

## Lineage

- **RESOLVED BY:** `GOV-CN-001` (raised from this report), on the recorded
  Product Owner decision of 2026-08-30 adopting the re-scope recommendation.
- **RESOLUTION DATE:** 2026-08-30
- **RELATED CONFLICTS:** None. First `GOV-CR-` filed.
- **RELATED DECISIONS:** None directly. `governance/decision-mechanics/CHARTER.md`
  §5 is relevant context but not a conflicting authority: it states that the
  programme's laboratory terms are "not a vocabulary for the product" and that
  none should become "a UI concept, a route, a panel, or a field", which is the
  same caution from the research side rather than a second governance clause.

## Governance delta

`CONFLICT FOUND — STOPPED`
