# GOV-CN-001 — Admit Multi-Observer Shear to Spin as a layer distinct from Helix

- **GOVERNANCE ID:** GOV-CN-001
- **TITLE:** Amend CIC-SPIN-INTELLIGENCE to v1.2 — admit an observer-shear layer, and fix the boundary that keeps it out of Helix
- **TYPE:** Governance Change Notice
- **VERSION:** v1.0
- **STATUS:** ABSORBED

## Authority

- **AUTHOR / PROPOSER:** Claude, under the Product Owner's GOV-CR-001 resolution directive (2026-08-30)
- **APPROVAL REQUIRED FROM:** Product Owner
- **DATE RAISED:** 2026-08-30
- **DECISION DATE:** 2026-08-30 — APPROVED by the Product Owner.

## Current governance

- **TARGET RECORD(S):** `governance/current/contracts/CIC-SPIN-INTELLIGENCE-v1.1.md` v1.1 (STATUS: CURRENT)
- **CURRENT WORDING:**

  SCOPE:

  > Spin evidence selection, assembly, model invocation, findings, provenance, and Helix / Progressive Project Convergence assessment.

  MANDATORY INVARIANTS (the Helix clause only; the remainder of the invariant
  list is unaffected and is not quoted here):

  > Helix is an investigative/convergence model, not a universal scoring system; Helix must not silently become a coordination percentage, health score, universal LOD/percentage mapping, universal tolerance table, hard-coded trade hierarchy, project-wide uniform-maturity assumption, or automatic engineering/design correction mechanism; expectation, observation, consequence, and evidence sufficiency remain distinct; non-convergence does not automatically equal noncompliance without evidence and authority context.

## Proposed change

- **PROPOSED WORDING:**

  SCOPE becomes:

  > Spin evidence selection, assembly, model invocation, findings, provenance, Helix / Progressive Project Convergence assessment, and Multi-Observer Shear analysis.

  The Helix clause of MANDATORY INVARIANTS is preserved **verbatim and
  unchanged**, and the following is added to the same invariant list
  immediately after it:

  > Multi-Observer Shear is a distinct analysis layer and is never Helix. Helix's subject is the convergence of interdependent physical/interface strands; Shear's subject is divergence between the frames of distinct parties observing the same project state. The two must not share a name, a vocabulary, a persisted field, or a parser; a Shear result must never be emitted as a Helix assessment and a Helix assessment must never be reinterpreted as Shear. Observer frames are derived from the project's own ingested contracts, roles and evidence — never from a hard-coded party set, delivery-model template, or assumed project structure; a project whose evidence does not establish distinct observer frames yields no Shear rather than a default one. Shear maps where distinct rational positions diverge and never adjudicates between them: divergence is not error, a party's position is not scored, and no observer frame is ranked above another. Shear never speculates about motive, intent, competence or state of mind, and is grounded only in what each party's own evidence states.

- **NATURE OF CHANGE:** addition
  <!-- Honest label. It widens SCOPE by admitting a new analysis layer, and it
       adds constraints; it narrows nothing and removes nothing. The Helix
       invariant clause itself is untouched, which is the point of the notice. -->

## Why

`GOV-CR-001` recorded a genuine conflict: the GO Decision Architecture directive
(2026-08-29) instructed that Multi-Observer Shear be implemented *as* Helix,
which would have replaced the governed subject of a CURRENT contract while
leaving its name, closed vocabulary and reference tests in place, and would have
hard-coded an `(Architect, GC, Owner)` party set in breach of constitutional
invariant #15.

The Product Owner resolved that conflict on 2026-08-30 by adopting the re-scope
recommendation. This notice is the governance action that resolution named.

Without it, the contract is silent on the distinction. A later reader of v1.1
would find a shear layer operating inside Spin with no governing text separating
it from Helix — which is the same ambiguity `GOV-CR-001` was filed about,
arriving a second time through the back door rather than the front.

The dynamic-observer-derivation requirement is written into the invariant rather
than left to implementation because that is the clause carrying constitutional
invariant #15 compliance. As an implementation intention it would survive
exactly as long as the first session that found hard-coding easier.

## Expected consequences

- **IF APPROVED:** Spin may carry an observer-shear layer in its own module with
  its own vocabulary and its own persisted field. Helix keeps its subject, its
  ten assessment values, its axes and its reference tests unchanged. Observer
  frames must be derived from ingested project evidence, and a project whose
  evidence does not establish them produces no Shear at all.
- **IF NOT APPROVED:** CIC-SPIN-INTELLIGENCE v1.1 continues to govern unchanged.
  `GOV-CR-001`'s blocked work stays blocked — no shear layer may be built inside
  Spin under any name, because the contract's SCOPE reaches Spin's model
  invocation and findings regardless of what a new module is called. The
  underlying need (making rational disagreement visible without adjudicating it)
  remains served only by existing authority-ambiguity findings and constitutional
  invariant #10.

## Affected invariants

Every invariant in CIC-SPIN-INTELLIGENCE v1.1 is listed, including those that
survive untouched, because a quietly disappearing invariant is the highest-risk
outcome of any notice.

| Invariant | Effect |
|---|---|
| Spin is genuinely model-backed | unchanged |
| Governed project evidence reaches the model | unchanged |
| Source scope and baseline/current provenance are truthful | unchanged |
| No Teacher/Oracle leakage | unchanged |
| No PSD/smoke-specific production steering | unchanged |
| No model-memory authority | unchanged |
| Truncation and selection are known/testable | unchanged |
| Findings are grounded in supplied evidence | unchanged — and extended in effect to Shear, which is bound by it |
| Strands may progress at different velocities | unchanged |
| Individual strand maturity alone does not prove coordination | unchanged |
| Claimed maturity comes from project evidence rather than universal stage assumptions | unchanged |
| A mature strand can still fail to mesh with dependent strands | unchanged |
| Helix is an investigative/convergence model, not a universal scoring system | unchanged — clause preserved verbatim |
| Helix must not silently become … hard-coded trade hierarchy … | unchanged — clause preserved verbatim, and reinforced by the new boundary invariant |
| Expectation, observation, consequence, and evidence sufficiency remain distinct | unchanged |
| Non-convergence does not automatically equal noncompliance without evidence and authority context | unchanged |
| *(new)* Multi-Observer Shear is a distinct layer and is never Helix | added |

## Compatibility and conflict analysis

- **CONSISTENT WITH:** `constitutional-invariants.md` #10 (authority conflicts
  surface, never resolve silently) — Shear is a mechanism for surfacing
  disagreement without picking a side, which is #10 expressed as analysis.
  `constitutional-invariants.md` #15 — the dynamic-derivation clause is what
  makes the layer compliant rather than merely not obviously offending.
  `constitutional-invariants.md` #14 (perspective must never alter epistemic
  truth) — Shear reports *that* frames diverge; it never lets a frame change what
  a Finding or Requirement means. `governance/current/situational-attributes-are-not-authority.md`.
- **CONFLICTS WITH:** None found in what was actually read. Stating the scope of
  the check rather than implying an exhaustive one, per this corpus's own
  standing rule that unmeasured is not unknown-shaped: read in full —
  `constitutional-invariants.md` (all seventeen) and
  `CIC-SPIN-INTELLIGENCE-v1.1.md`; read to their governing principle and
  invariant lines — `GOV-P-001` (selection is context, not authorization),
  `GOV-P-002` (work surfaces vs control surfaces), `GOV-P-003` (help without
  humiliation), `GOV-D-001`, `GOV-D-002`. **Not read for this notice:** the other
  eleven contract files in `governance/current/contracts/` (`CIC-CCN`,
  `CIC-COMPOSER`, `CIC-DEPLOYMENT`, `CIC-DEVELOPER-MODE` and v1.1,
  `CIC-GO-CONVERSATION` and v1.1, `CIC-PAGE-TEMPLATE`, `CIC-PANEL` and v1.1,
  `CIC-REPO-SAFETY`). Their subjects — CCN, Composer, deployment, Developer Mode,
  GO conversation, page templates, panels, repo safety — do not touch Spin's
  analysis layers, which is why they were not read; that is a judgment about
  relevance, not a completed check, and a reviewer who disagrees should treat
  this as the gap to close first. The check that mattered was #14: an observer-frame
  model is exactly the shape that could let perspective alter truth, which is
  why the proposed wording says Shear never adjudicates and never ranks a frame.
  `GOV-P-003` is a non-obvious consistency worth recording rather than a mere
  absence of conflict — *"the intended outcome is never that the user realises
  how intelligent GO is"* is the same discipline as refusing to adjudicate
  between parties: a system that told a project manager which stakeholder was
  right would be performing insight it has no authority for.
- **PRECEDENCE EFFECT:** None. Nothing currently settled changes hands. v1.1
  governs every situation it governs today; the notice only adds a layer the
  contract is presently silent about.

## Migration requirements

- **CODE / TESTS:** None required by this notice. Approving it authorizes future
  work; it builds nothing. `tests/test_go_decision_architecture_01.py` already
  pins the Helix vocabulary against silent change and needs no amendment — under
  the proposed wording those assertions become *more* correct, not less, since
  Shear must never touch that vocabulary.
- **EXISTING RECORDS:** On approval, CIC-SPIN-INTELLIGENCE v1.2 supersedes v1.1
  and a `GOV-S-` records the supersession with v1.1's wording preserved. This
  notice is then `ABSORBED` into v1.2. `GOV-CR-001` cites this notice as its
  resolution and needs no further amendment.
- **IN-FLIGHT WORK:** None authorized under the current wording is affected. The
  four implemented items of the GO Decision Architecture directive (survival
  triage ordering, cognitive stopping, temporal anti-smuggling, bounded execution
  authority) are prompt-level and touch neither Helix nor Shear.

## Approval required

Approving this authorizes **the boundary and the constraints**, not an
implementation. Specifically it authorizes a future, separately-ordered
observer-shear layer to exist inside Spin, on the stated terms: its own name, its
own vocabulary, its own field, dynamically derived observer frames, no
adjudication between frames.

It does **not** authorize: building `services/observer_shear.py` (that needs its
own implementation order), any UI surface for Shear, any persisted schema change,
or any change to Helix.

**One bundled question, stated so it is not settled by accident.** Approving this
also settles that observer shear belongs *inside* Spin's governed scope rather
than as a capability of its own with a separate contract. That is a real choice.
Inside Spin, it inherits Spin's evidence discipline, provenance and truncation
invariants for free, and is the smaller change; as its own capability it would
need a new CIC and could later be invoked outside a Spin pass. This notice
proposes inside Spin.

## Lineage

- **SUPERSEDES:** None.
- **ABSORBED INTO:** [CIC-SPIN-INTELLIGENCE v1.2](../current/contracts/CIC-SPIN-INTELLIGENCE-v1.2.md), via [GOV-S-001](GOV-S-001.md). This notice stays filed so its reasoning remains traceable; the governance now lives in v1.2.
- **RAISED FROM:** `GOV-CR-001`
- **RELATED DECISIONS:** None.

## Governance delta

`CHANGE PROPOSED — NOT APPLIED`

<!-- Superseded by the successor's own delta on approval (2026-08-30). The value above is preserved as the delta this notice carried while it stood, per the template's own rule; CIC-SPIN-INTELLIGENCE v1.2 and GOV-S-001 now carry the applied change. -->
