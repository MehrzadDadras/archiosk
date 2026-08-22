# Cross-layer verification — a development convention

Status: development convention, v1.0, 2026-08-22
Repository grounding SHA: `56b9c24b294d6b9e663e6b3dea917f859dd5ffd2`

**This is a development document. It carries no product authority.**
It changes no runtime behavior, route, schema, template, test, vocabulary, or
governance record. It creates no service, layer, module, boundary object, event
bus, orchestrator, defect database, test runner, or test lane. Nothing here is
citable as project truth, and nothing here authorizes an implementation.

`TEST_LANES.md` (which lanes to run) and `governance/current/canonical-implementation-order.md`
(how work is ordered, reported and stopped) are unchanged and remain authoritative
for what they cover. This document sits beside them and covers only what neither
does: **how an observation made while exercising one part of the system becomes a
diagnosis about another part, without becoming permission to change it.**

---

## 1. The distinction, and its limits

Two kinds of work have in practice been advanced separately:

- **Cognitive substrate** — how the system identifies evidence, preserves
  provenance, relates evidence, abstains, preserves disagreement, reasons across
  dependencies, handles maturity and non-closure, and separates evidence from
  authority.
- **Application operations** — how a person uploads and opens evidence, registers
  sheets, invokes an investigation, inspects findings, uses the Composer, and
  produces operational output.

**This distinction is development shorthand. It is not product architecture.**

### What it does not mean

**Mandatory, and never empty** — the same discipline `governance/vision/ANA-003.md`
applies to its own analogy, for the same reason.

- **It does not name a subsystem.** No module, service, package, layer, boundary,
  interface, or runtime component takes either name. There is no `CH` and no `AO`
  in this codebase and none is proposed.
- **It is not a new architectural boundary.** Where a real boundary exists, it is
  the one already in the code, and the code is the authority — not this document's
  description of it.
- **It does not map to agents.** "Codex advances the substrate, Claude exercises
  the application" is an observation about who has done which work, nothing more.
  **Agent identities must never enter product runtime, governance vocabulary, test
  taxonomy, or GO's own ontology.** They are development roles with no standing in
  the product, and a future reassignment must invalidate nothing.
- **It is not a licence to route work by label.** Whether a defect belongs to
  substrate or operations is decided by locating it in the code, never by which
  layer it was noticed from.
- **It creates no third thing.** There is no interface layer, firewall object, or
  boundary contract. "Interface" below is a diagnostic answer, not a component.

---

## 2. Where the boundary already exists

This convention describes something the repository already does. It is worth
recording precisely because it is real and unnamed — and worth keeping powerless
because the rules that matter are already governed elsewhere.

| Existing mechanism | What it already separates |
|---|---|
| `POST .../investigations` (`routes/api.py`) | The route supplies `question`, `case_id` and an anchor. It **cannot** set `claim_class`, `confidence_state` or `author_type` — those are decided inside `services/cross_modal_investigation.py`. An operational surface says *what to investigate*, never *what to conclude* |
| `record_investigation_claim` | Refuses `author_type=ai` paired with `directly_verified`/`deterministic_calculation`, and refuses an asserting claim with no real cited evidence. No caller can bypass either |
| `services/question_scope.py` module docstring | Declares its own limits in code: *"does not select an answer path, invoke a model, inspect project evidence, authorize a mutation, or change any existing Composer/workspace routing"* |
| `services/capability_registry.py` | Application-capability knowledge answered without reaching project evidence at all — `_handle_capability_question` receives only the matched `Capability` |
| `CaseOutcome` docstring | *"the machine… may say 'there is enough here to investigate'… it never gets to also say 'and this hypothesis survived.' `recorded_by` is never machine-populated"* |
| `can_open_autonomous_case_for` / `create_autonomous_case` | The machine may open an investigation on its own, capped at `MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT = 3` with a same-anchor duplicate check — and *"Case creation is never itself authority… regardless of which of these three produced it"* |
| `_require_approval` (`routes/workspace.py`) | The Approval Gate, kept deliberately separate from the Delegation Choice in the same module's own docstring |
| `create_rfi_draft` | Refuses without a prior `ReviewerValidation` — a machine observation cannot become an issued question |
| `project_clock.reconcile_project` | *"Never mutates a TemporalObligation's dates or status here — Project Open must not silently mutate governed project truth"* |
| `governance/current/contracts/README.md` | The standing-contract registry already sorts along this line: `CIC-SPIN-INTELLIGENCE` binds evidence/prompts/findings/provenance; `CIC-COMPOSER`/`CIC-PANEL`/`CIC-PAGE-TEMPLATE` bind surfaces; `CIC-REPO-SAFETY` binds everything |

**Confirmed by direct search: no record in `governance/` uses this vocabulary
today, and none is added.**

---

## 3. What is already governed, and the one thing that is not

Of the four candidate laws examined, **three are already in force** and are cited
here rather than restated:

- **Tools extend reach; they do not rewrite cognition.**
  `governance/current/evidence-richness-and-source-authority.md` v1.0 —
  *"Evidence richness increases investigative resolution. It never increases
  authority."* Restating it here would create a second wording of one rule, which
  is precisely the drift `GOV-P-001` was filed to correct.
- **A finding does not automatically become a workflow consequence.**
  `constitutional-invariants.md` #2 and #7; `GOV-P-001` v1.0;
  `GO-PREAWARD-ADJUDICATION-01` (*"do not force every finding into RFI form"*);
  and every mechanism in the table above.
- **Neither side manufactures certainty.** `Claim` deliberately carries no
  confidence float; `CLAIM_CLASS_UNKNOWN` and `evidence_type_insufficient` are
  first-class abstentions; `compare_maturity` returns `None` rather than guessing;
  `governance/current/dependency-sufficiency-and-non-closed-basis.md` v1.0 governs
  the inference from agreement.
  **One thin spot, recorded and not repaired:** `evaluate_information_sufficiency`'s
  `observed` argument is caller-supplied by design (*"deliberately NOT
  auto-discovered"*), and the phase-assessment route's own input is documented as
  *"a deliberately minimal stand-in."* Nothing forbids an operational surface from
  synthesizing a plausible-looking `observed` list. **Recorded as an observation
  against working code; no repair is proposed or authorized.**

**The one rule not found anywhere in the repository is the reporting rule**, and it
is the only rule this document states:

> **A report crosses; authority does not.**
>
> Exercising one part of the system may reveal a defect that belongs to another
> part. That observation is **evidence for diagnosis, never permission to repair**.
> The side that noticed describes the failure and the evidence for it. The side
> that owns the code decides what, if anything, changes.

This is a development-process rule about who may change what. **It is deliberately
not filed as governance**, because it governs contributors rather than the product,
and `governance/vision/README.md`'s own precedent is that a rule belongs where its
authority actually lies.

The nearest existing precedent is real and should be followed: the Canonical
Implementation Order already requires an agent that finds a conflict to report
`GOVERNANCE DELTA: CONFLICT FOUND — STOPPED` rather than resolve it. **This is the
same shape, one layer down.**

---

## 4. Defect report shape

A plain-text section in whatever already carries the work — a report to the Product
Owner, an implementation order's findings section, or a commit message. **No file
format, no database, no tooling, no identifier registry.**

| Field | What it holds |
|---|---|
| `defectId` | A short local label for referring to it in this exchange. Not a durable identifier and not registered anywhere |
| `boundaryHypothesis` | `POSSIBLE_SUBSTRATE` · `POSSIBLE_OPERATIONS` · `POSSIBLE_INTERFACE` · `INCONCLUSIVE`. **A hypothesis, stated as one** |
| `observedBehavior` | What actually happened, reproducibly |
| `expectedProfessionalBehavior` | What an experienced PM or Builder would have expected — stated as a professional expectation, not as a proposed implementation |
| `evidenceOfGap` | Real files, lines, records, or reproduction steps. Not an argument |
| `excludedInterpretations` | Readings that were checked and ruled out, with what ruled them out. This is the field that stops a plausible-but-wrong diagnosis from travelling |
| `requestedOwnerReview` | What the reporter is asking the Product Owner to decide |

**The reporting side describes the failure and the evidence. It does not prescribe
the receiving side's repair.** A report containing a patch is not a report.

Order, and it is not negotiable per-defect:

**classify → reproduce → locate the boundary → authorize the owner → repair →
cross-layer retest.**

`INCONCLUSIVE` is a complete and respectable answer. Locating the boundary means
finding the code, not deciding which label sounds right.

---

## 5. Test purposes

These are **purposes, not lanes**. `TEST_LANES.md`'s Lane A/B/C/D/E execution model
is unchanged, and its assurance tiers are already declared *"orthogonal to lanes."*
Three of the four purposes are already those tiers under different words:

| Purpose | Where it already lives |
|---|---|
| Substrate invariance — evidence, disagreement, abstention, authority boundaries, non-closure | **Tier 2** — already defined as *"provenance isolation, authority separation, context-is-not-evidence, and project/application separation"* |
| Operational execution — does the real user workflow work | **Tier 3** — *"real template identity, selected object, referent, active source, and task intent"* |
| Boundary integrity — does a new instrument increase reach without changing epistemic rules | **Tier 2**, specifically its project/application-separation and context-is-not-evidence halves |
| **Professional outcome** — does the integrated product notice and characterize what an experienced PM or Builder would care about | **Not covered by any existing tier.** Tiers 1–4 all test mechanism |

**The fourth is genuinely new**, and the Builder smoke corpus at
`tests/fixtures/psd/builder_corpus/` (private oracle at `tests/fixtures/psd/oracle/`)
is the first instrument for it. **No tier is renumbered, renamed, or added.**

---

## 6. Cross-strand object test pattern — future shape only

**One project condition → several source representations → controlled mismatch →
deterministic expected observations.**

The pattern is compatible with existing primitives, and no new mechanism is
implied: several `Source` records, one `EvidenceItem` per representation,
`CORRESPONDS_TO`/`CONTRADICTS`/`DEVIATES_FROM` between them, one `Claim` citing
several evidence items with `evidence_excluded` carrying what could not be
established, and `CONFIDENCE_STATE_CONFLICTING_SUPPORT` for the mismatch. Peer
comparison would use `SAME_SUBJECT_AS`/`COMPARES_WITH`, which exist and still have
no producer.

It fits the professional-outcome purpose, and it is the right shape for a future
integration test because the expected observations are deterministic rather than
judged.

**Not built. No fixture, no object, no identifier, and no model or IFC evidence is
implied by recording this shape.** The documentary corpus remains the baseline.

---

## 7. Standing statements

- **NO CH/AO RUNTIME IMPLEMENTATION AUTHORITY CREATED.**
- **NO REVIT/IFC IMPLEMENTATION AUTHORITY CREATED.**
- **THE PDF/DOCUMENTARY BUILDER SMOKE TEST REMAINS THE NEXT PRODUCT VALIDATION
  BASELINE.**
- Agent identities remain development roles and never enter product runtime,
  governance vocabulary, test taxonomy, or GO's ontology.
