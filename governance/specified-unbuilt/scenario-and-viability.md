# Specified But Unbuilt — Scenario, Viability, and Commitment

**Status:** Specified, not implemented. **Authorization:** none of this may be built without a fresh, explicit go-ahead — see `STATUS.md`.

## Scenario and Scenario Delta

Distinct from `Case`/Investigation: a Case resolves through *evidence* (which hypothesis the facts support); a Scenario resolves through *authorized decision* (which possible future is chosen, for reasons outside physical fact — commercial, political, funding). Collapsing these was tested directly and rejected — they answer different kinds of questions.

Represented as **Baseline State Reference + Scenario Delta Set**: a `Scenario` record referencing the `project_state_version` it branches from, `status` (`proposed` / `adopted` / `not_adopted`), with its actual content expressed **entirely as `Relationship`-based deltas** against specific existing objects (proposed addition/replacement/omission/deferral/changed-value/changed-relationship) — never a duplicated copy of project content. This is the specific, tested safeguard against Scenario becoming a shadow second project state: nothing in a Scenario is ever operative until an authorized adoption act promotes it, and nothing in it duplicates content that already lives elsewhere in the project.

Non-adopted Scenarios are preserved historically, never deleted.

## Value Engineering (VE)

Confirmed, not a separate governance subsystem: VE is a Scenario `scenario_type` classification value, nothing more. Every VE-specific requirement (cost/schedule effect, affected Requirements, code implications, risk introduced/retired, revalidation-needed items) maps onto fields or `Relationship`s a generic Scenario already carries.

## Graduated Contract Commitment sequence

Not a binary PRE/POST gate — an open-world sequence of named commitment events (Pursuit → LOI → Conditional Award → Partial NTP → Full Execution → further events as needed), each carrying its own rule-binding for available scenario options, authority tiers, and recovery strategy. Modeled the same way `AnalysisTrigger`'s open-world vocabulary already works — new commitment-event types addable as data, not code.

**Pre-commitment governing question:** "Should we accept this risk at this price/terms?" Declining to proceed (no-bid, decline award, withdraw) is a normal, complete, unremarkable answer requiring no further obligation.

**Post-commitment governing question:** "How do we complete the obligation with the least damaging and most defensible commercial outcome?" — never "Should we remain in the project?"

## Continuous viability

`ViabilityAssessment`: append-only, attributed, created at each named lifecycle gate. Factors (probability of win, funding, cost certainty, contingency, schedule, margin, downside exposure) stay **individually visible, never collapsed into a single score** — direct reuse of ADR-032's confidence-separation principle. Progression through the lifecycle does not imply increasing viability; deterioration is simply visible when successive assessments are compared, not something requiring its own tracking mechanism. Identity stays attributed for accountability; the system must never compute or surface an automated PM/project-manager performance ranking from a sequence of assessments — the same identity-visible/no-automated-aggregate-judgment rule already established for reviewers, reapplied one tier up.

## The post-contract termination boundary — the sharpest rule in this document

Post-contract recovery scenarios (VE, re-scope, mitigation, negotiation, claims, absorbing reduced margin or loss) remain fully representable through the Scenario/`ViabilityAssessment` pipeline above, at any severity. **What is never representable through that pipeline, at any severity, under any authority level, is the project ending.** This is not a stricter Scenario requiring extraordinary authority to adopt — it is not a Scenario at all, and it is not a possible `ViabilityAssessment` conclusion. Economic deterioration alone, however severe and however honestly documented, never produces an exit option. A fully honest "no currently evaluated recovery scenario produces a viable outcome" conclusion remains reachable and must be representable — it stops there, escalated to executive/legal attention as appropriate, and does not itself trigger or authorize a project-ending record. See constitutional invariant 17 and `deferred-reserved/reservations.md`'s note on the future governed legal/dispute context for where a project-ending state, when genuinely warranted, actually enters the model.

## Dormancy / restart

Suspend/Defer reuses the `Lock` pattern (temporary, reversible — see `specified-unbuilt/investigation-lifecycle-extensions.md`). Cancel/Close reuses the `Archive` pattern (terminal). **Restart recommendation, decided:** targeted revalidation, not blind resurrection and not full global re-verification. On restart, flag every Requirement/assumption active as of suspension for `needs_revalidation`, propagate through recorded dependencies, and preserve unaffected items only where continuing applicability can actually be demonstrated. Restart is architecturally a special case of authoritative project metamorphosis (see `specified-unbuilt/metamorphosis-and-dormancy.md`), triggered by elapsed dormant time rather than a specific new document.
