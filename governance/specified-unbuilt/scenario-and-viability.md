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

---

## Addendum (`CLAUDE-GO-DNA-06`) — "Win it well": commercial pursuit viability, and the flexible-net principle

Recorded following a Product Owner clarification, explicitly a **DNA delta**, not new authorization: *"We want to win the RFP, but we want to win it well."* **No code changes accompany this addendum. NOT AUTHORIZED for implementation** beyond what is already built and described below.

### This document's own `ViabilityAssessment`/`Scenario` design already answers most of the governing prompt's Sections 1–4

Re-read against the new prompt, this document's existing, pre-dating design already states the core commercial invariant more rigorously than the new prompt does: "Continuous viability... Factors... stay individually visible, never collapsed into a single score" (above) is the direct, already-recorded answer to the new prompt's "do not reduce complex pursuit viability to a single-machine score." The Graduated Contract Commitment sequence (Pursuit → LOI → Conditional Award → Partial NTP → Full Execution) is the already-recorded answer to "phase-aware... early pursuit / intermediate estimate / late final estimate." Nothing in Sections 1–4 of the new prompt requires new design here — it requires cross-reference, not restatement.

### A materially important correction: `GoNoGoAssessment` (`CLAUDE-P30`) is real and already does much of this — this document's own header ("Specified, not implemented") describes `Scenario`/`ViabilityAssessment` specifically, not Go/No-Go as a whole

Verified directly in `services/case_workspace.py` and `routes/workspace.py`, not assumed: a **simpler, already-built precursor** to this document's own `ViabilityAssessment` exists and is live:

- `GoNoGoAssessment` — `decision` (closed: `go`/`no_go`/`conditional_go`, exactly the three states the new prompt asks for), `decision_stage` (validated against `CLIENT_OWNER_DECISION_STAGES`/`DESIGN_BUILDER_PROPONENT_DECISION_STAGES`, `services/environment_capabilities.py`), `anomalies` (open-world free text), `rationale`, `decided_by`/`decided_by_role`.
- `workspace.go_no_go_assessments` is a **list**, appended to via `record_go_no_go_decision`, never overwritten — repeated, phase-aware assessment is already the storage shape, not a future redesign. `DESIGN_BUILDER_PROPONENT_DECISION_STAGES` alone (`pursue` → `submit_rfq_response` → `continue_after_shortlisting` → `bid_rfp` → `accept_commercial_terms` → `continue_after_addenda` → `submit_final_proposal` → `proceed_with_delivery_strategy`) already maps closely onto the new prompt's own "early pursuit / intermediate estimate / late final estimate" progression.
- The route (`POST /projects/<project_id>/workspace/go-no-go`, `routes/workspace.py`) is real, admin-only (server-side enforced, not merely hidden — `CLAUDE-P38` OBS-04 closed exactly this gap previously), and rendered live in `templates/case_workspace.html` as a reverse-chronological history plus a real recording form.

**Lineage, recorded so a future session does not mistake this for two competing systems**: `GoNoGoAssessment` (built) is the primitive ancestor `ViabilityAssessment` (this document's own specified-unbuilt design) generalizes — the same relationship DNA-01's own §6 lineage table already established for `Overview`/Spin. A future `ViabilityAssessment` should extend `GoNoGoAssessment`'s proven shape (closed decision outcome, phase-scoped, human-authorized, append-only history), not replace or duplicate it.

### The one precise, load-bearing gap — confirmed by inspection, matching the new prompt's Section 3 exactly

`GoNoGoAssessment.anomalies` is **free text only** — unlike `Claim.evidence_links` (`CLAUDE-MM7`, see `specified-unbuilt/spin-project-intelligence-preview.md`'s `CLAUDE-GO-DNA-05` addendum), there is no typed, validated reference from a Go/No-Go decision back to the real `Finding`/`ComposerFinding`/`Claim`/`RFIDraft` records that motivated it. This is the exact, smallest missing seam behind the new prompt's own worked example ("this RFI does not itself make the project NO-GO, but its unresolved consequence increases exposure by affecting X, Y, Z") — the mechanism to make that sentence machine-traceable rather than only human-composed prose already has a proven pattern to copy (`Claim.evidence_links`' validate-against-real-governed-objects discipline), it is simply not applied to `GoNoGoAssessment` yet. **Not built by this addendum.**

### No cost/schedule/commercial-consequence fields exist anywhere today

Confirmed by direct inspection of `Finding`, `ComposerFinding`, `Claim`, `InvestigationStep`, `WorkProduct`: none carry a monetary, schedule, or contingency-effect field. `WorkProduct.artifact_type` accepts the open-world example string `"risk_register"` as a label only — a `WorkProduct` can be *classified* as a risk register, nothing more; there is no structured risk-register content model. This document's own "Value Engineering (VE) confirmed, not a separate governance subsystem" section already establishes the right shape for when this is eventually built (cost/schedule effect, affected Requirements, risk introduced/retired — fields or Relationships a generic `Scenario` already carries) — reused here as the target shape for a future `GoNoGoAssessment`↔evidence link too, not a reason to invent a second one.

### The flexible-net principle (new content — Sections 5–10 of the governing prompt)

Not previously recorded in this corpus by name, though consistent with it: **govern the method strongly; keep the taxonomy extensible.** Verified where this repository already honors and violates this principle:

- **Honors it:** `Claim.claim_class`/`confidence_state` are closed-but-deliberately-complete vocabularies (`CLAUDE-GO-DNA-05`); `GoNoGoAssessment.anomalies` and `AnalysisTrigger`'s own vocabulary (`services/case_workspace.py`) are open-world by design, specifically to avoid "an ever-growing enum masquerading as one" (the class's own docstring language, reused verbatim here because it already states this principle precisely).
- **Violates it, named honestly:** `CLIENT_OWNER_DECISION_STAGES`/`DESIGN_BUILDER_PROPONENT_DECISION_STAGES` are **closed, hardcoded tuples** — a third procurement model, or a stage neither existing vocabulary anticipates, requires a code change, not a data change. This is a real, if minor, overfit point relative to the new prompt's "flexible net... not overfit to one procurement model" requirement. **Not a defect to fix now** — named as a seam for whenever Go/No-Go's own vocabulary needs to grow past two environments.

### Search/investigation muscle (Sections 8–9 of the governing prompt) — cross-reference, not new content

This is the same ground `CLAUDE-GO-DNA-05` (`specified-unbuilt/spin-project-intelligence-preview.md`) already covers in more repository-grounded detail: `investigate_cross_modal_question`/`Claim` is the real "search using governed tools, return typed evidence" muscle; question-*formation* (detecting a condition worth investigating before a question is supplied) remains the named, unbuilt gap. Not restated here — see that addendum.

### Seam classification (per the governing prompt's own request)

- **CURRENT** (already enforced, verified): human-only Go/No-Go authority (admin-gated, server-side); closed three-state decision vocabulary; phase-scoped, append-only assessment history; the post-contract termination boundary (this document's own existing, unrelated-but-adjacent invariant, above) already forbids treating commercial deterioration as an automatic exit trigger — the same "human decides, GO informs" boundary this addendum's own findings-to-viability link would need to respect if ever built.
- **NEAR-TERM COMMERCIAL ACCELERATOR** (not implemented by this addendum; smallest bounded next step if separately authorized): a typed, validated reference field on `GoNoGoAssessment` (or a new linking record) pointing to the `Finding`/`ComposerFinding`/`Claim`/`RFIDraft` ids that informed a given decision — mirroring `Claim.evidence_links`'s proven validation discipline. This alone would make "why did this decision change" explainable from real project evidence rather than only from human-composed rationale text.
- **SPECIFIED-UNBUILT** (this document's own pre-existing scope, unchanged): `Scenario`/`ScenarioDelta`, full `ViabilityAssessment` (individually-visible probability/funding/cost-certainty/contingency/schedule/margin/downside-exposure factors), cost/schedule/consequence fields on findings generally, any quantitative/Monte Carlo aggregation, and the flexible-net vocabulary-extensibility work named above.

### What this addendum changes about the current implementation sequence

Nothing, per the governing prompt's own explicit instruction against broad new authorization. `GoNoGoAssessment` remains as-is, fully functional; the evidence-link seam named above is recorded for a future, separately-authorized stage, not begun here.
