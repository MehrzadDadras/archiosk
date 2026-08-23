# Specified But Unbuilt — Perspective, Contract/Delivery DNA, Template, ReferenceStandard

**Status:** Specified, not implemented.

## Perspective

First-class only at the application/authorization layer — **never** at the truth-model layer. A `Finding` does not become truer or less true depending on who is looking. Splits into two genuinely different things, tested and kept separate:

- **Authorization-gating** (which actions are actually permitted — publication capability, private/shared transitions, PM-gating for Archive/Lock): real, enforced, but just another application of the role/authority-check pattern already used throughout the kernel.
- **Default-emphasis/UI-lens** (which questions/views surface by default — Owner sees affordability/readiness prompts, Proponent sees pursuit/risk prompts): must stay lightweight, must never be stored as a field on governed data, and carries a real, tested anchoring risk (see below).

Named Perspectives (Owner, Proponent, Private Partner, Contractor, Consultant, Operator/Maintainer, Neutral/Arbiter, Legal/Commercial Advisor) are an open, extensible list — the admission test for a new one is simply whether it needs a new truth model (it never should).

**Anchoring risk, tested and confirmed real, not dismissed:** Perspective-driven default questions can narrow a user's attention before they've formed their own independent read, the same structural risk already identified for Experience Corpus heuristic retrieval. Mitigation reuses the same three-part fix: present defaults as structured starting points, never as an implicit claim of importance; never gate full kernel access behind the Perspective-filtered view; log which default-question-set was shown to whom, so a later-discovered blind spot is traceable.

**Sharpest guardrail — must never be relaxed:** Perspective's own code must never accept more than one project workspace. The Neutral/Adjudication Workspace (`cross-boundary-architecture.md`) is a structurally *separate* mechanism, permanently, precisely so Perspective never has to learn to read across a project boundary at all — even though the two will sound like natural siblings in casual conversation.

## Contract / Delivery DNA

A curated `Template` configuration — **not a new kernel primitive**, a specialized use of `Template` (below). Configures expected lifecycle stages, obligation types, commitment gates, default templates, recurring review prompts, risk categories — tested against DB, DBM, DBFM/P3, CM, DBB, Progressive DB, and custom hybrids without requiring per-delivery-model code branches, since lifecycle sequences are themselves template data.

**Must never supply operative truth.** Structural safeguard, not a restated principle: any record whose origin traces to a template, and which has not yet been explicitly re-sourced against a real project `Source`, is instantiated in a `template_default_unverified`-shaped status that is **type-incapable of satisfying any downstream governed conclusion** — cannot close a `RequirementAdjudication`, cannot feed a `ViabilityAssessment`, cannot be cited in an adopted Scenario — until a human explicitly re-sources it.

**Second, distinct risk found and named — template-driven omission, not just template-driven wrong-value.** A template that never prompts for a real obligation can function as a silent ceiling on what gets checked, purely by omission — a different failure mode than asserting a wrong default. No structural fix beyond the same "full kernel access must always remain available beyond whatever the template suggests" discipline already required for Perspective, plus periodic template-library review (`deferred-reserved/reservations.md`).

## Template

Reusable, non-project-scoped object (Domain 2b — Internal Reusable Practice). Instantiation into a project creates a fresh, project-specific record with `instantiated_from_template_id` provenance — the template itself is never operative, only what's instantiated from it, subject to the unverified-status safeguard above.

## ReferenceStandard

Domain 2a — External Authority Reference (codes, standards, LEED, jurisdictional material). Non-project-scoped. Currency is externally determined (by the issuing body), not internally by BEEHIVE or the firm — the sharpest distinction from Template/2b, where currency is internally, firm-governed. Adoption into a project reuses `Source`'s already-existing `origin_type`/`origin_reference` fields (`origin_type = "external_reference_import"`) — no new kernel mechanics needed, only the new background object itself.

## Create-Project / Pursuit UX flow

**Product design principle, not a constitutional rule (see the classification note at the end of this section):** an ordinary authorized user must be able to do this without ever reading, understanding, or manipulating a governance/constitutional artifact directly.

Named flow:

1. **Create New Project/Pursuit**
2. **Select or establish Perspective** (Owner, Proponent, Consultant, etc. — from the open, extensible list above)
3. **Identify project stage and delivery/contract model, where known** (may be left unknown/unset — nothing below requires it to be known at creation time)
4. **Enter basic project metadata**
5. **Ingest project sources**
6. **Save/close**
7. **Reopen the same governed project later and continue**

Perspective and Contract/Delivery DNA may **configure** the newly-created workspace — which default questions surface, which template set is offered, which lifecycle stages are expected — but creating a project must never become **technically dependent** on a developer or on a hard-coded project type.

**This is already structurally supported by decisions made earlier in this document, not a new architectural burden:** Perspective is specified as "first-class only at the application/authorization layer" — configuration, never a code branch — and Contract/Delivery DNA is specified as "a specialized use of `Template`... lifecycle sequences are themselves template data... addable as data, not code" (above). Adding a new Perspective or a new delivery-model template set is therefore always a *data* addition, never a kernel-code change. Save/close/reopen requires no new mechanism either: `Case`/`ProjectWorkspace` (see `current/kernel-object-model.md`) are already implemented, already persisted per `project_id`, and already perspective-neutral — reopening a project is unaffected by which Perspective the reopening user happens to have.

**Classification note, tested rather than assumed:** the request behind this flow was checked against the constitutional-invariant discipline in `constitutional-invariants.md` and found *not* to warrant a new invariant. The genuinely epistemic/authority-shaped core one might expect here — "a UI must never require bypassing governed functions to get ordinary work done" — is already fully covered by existing invariants 1 (no silent mutation), 2 (authority-gated state change), and 10 (no silent authority-selection): an interface that forced a user around the governed API to get unstuck would already violate those, without needing a new rule. What remains is a genuine but different-in-kind statement — a product/UX design commitment about ergonomics and adoptability, not about truth, authority, provenance, or isolation — and it belongs here, and in `STATUS.md`'s front-door summary, rather than padding the seventeen-item invariant list with something that isn't itself an epistemic rule.

---

## Extension: Retained-By, the Reference Library, and modified standard forms (CLAUDE-CONTRACT-KNOWLEDGE-03)

**Status:** Architecture accepted in principle by the Product Owner, 2026-08-23. **Still SPECIFIED-UNBUILT — zero code exists.** This extension amends nothing above; it adds the one missing relationship primitive and the three-layer knowledge separation that authoritative external research showed to be necessary. Research provenance lives in [`../reference-acquisition/REGISTER.md`](../reference-acquisition/REGISTER.md), which governs nothing.

### Retained-by, not a second position concept

A `procurement_position` field was proposed and **withdrawn**. It was a rediscovery of Perspective under a new name, and it could not represent the cases below. **Do not create it.**

The missing primitive is the **upstream edge — who retained this project's party** — as an explicit, project-local attribute alongside Perspective. The five intended entry contexts then need no new kernel values:

| Entry context | Representation |
|---|---|
| Client / Owner | Perspective `Owner` |
| Prime / Design-Builder / GC | Perspective `Contractor` + Contract/Delivery DNA |
| Lead Design Consultant | Perspective `Consultant` + retained-by `Owner` |
| Subconsultant / Specialist | Perspective `Consultant` + retained-by `Lead Consultant` or `Design-Builder` |
| Subcontractor / Trade Bidder | Perspective `Contractor` + retained-by `Prime` or `Owner` (via CM) |

Three authoritative findings force this shape, none of which a flat position enum can express:

- The **same consultant** is engaged under CCDC 31 when the Owner retains them and under CCDC 15/33 when a Design-Builder does. Same profession, same Perspective, different upstream edge, materially different obligations.
- Under **CCDC 5A** the Owner holds the trade contracts (CCDC 17); under **CCDC 5B** the Construction Manager does. Identical job title, opposite contractual position — an *edge-direction* change, not a perspective change.
- **RAIC Document Nine** is not stand-alone and must not be used without its Prime Contract attached, and **CCA 1** lets the parties elect whether the Prime Contract or the Subcontract governs a conflict. A downstream party's obligations are therefore not readable from its own agreement alone.

**PERSPECTIVE IS PROJECT WORKING CONTEXT, NOT PROJECT TRUTH. PROFESSION DOES NOT DETERMINE PERSPECTIVE. THE SAME ORGANIZATION MAY OCCUPY DIFFERENT PERSPECTIVES ON DIFFERENT PROJECTS.** Perspective and Contract/Delivery DNA remain distinct but interacting: neither derives the other.

Every downstream bidder may hold an **independent ARCHIOSK project**. A Trade project is not a Participant row inside its GC's project, and a Subconsultant project is not a Participant row inside its Lead Consultant's. `Participant.role_type` describes parties represented *inside* a project; it is not a project's own working position, and must not be used as one. Procurement is a **branching relationship graph**, never automatically a single Owner to GC to Trade ladder — and the retained-by edge never creates cross-project authorization or shared state.

### Three orthogonal axes, never collapsed

**Delivery method** (DBB, DB, PDB, CM-agency, CM-at-risk, IPD) x **payment basis** (stipulated, cost-plus, unit, fee-for-service, schedule-defined, hybrid) x **relationship** (who retains whom). The recovered historical prototype fused all three into a single contract label and consequently assigned a fixed adjudicative persona per form — "Absolute Arbiter", "Auditor-Facilitator", "Surveyor-Validator". That is contract form manufacturing authority. **It must not be revived.**

### Three knowledge layers

1. **Research / acquisition record** — `reference-acquisition/REGISTER.md`. Provenance, source class, research date, corrections, unverified items. Governs nothing, not user-facing.
2. **Curated reference knowledge** — the `ReferenceStandard` object already specified above (Domain 2a, currency externally determined by the issuing body). Record shape: identifier, full title, edition/year, issuing organization, official source URL, status, parties, relationship edge, delivery context, payment basis, supported concepts, related forms, jurisdiction notes, research date, provenance, and a **mandatory, never-empty `licence_limitation`**.
3. **Project Contract/Delivery DNA** — derived only from the project corpus, evidence-linked, belonging to the project.

The firewall between 2 and 3 is **already structural, not merely a rule**: any record traceable to a template that has not been explicitly re-sourced against a real project `Source` is instantiated `template_default_unverified`-shaped and is *type-incapable* of satisfying a downstream governed conclusion. Reference knowledge may suggest questions, name expected evidence, explain terminology and highlight deviations. It may not satisfy a requirement, prove an obligation, override project evidence, or supply a clause the project copy does not contain.

**EXPECTED EVIDENCE GUIDES SEARCH; IT DOES NOT MANUFACTURE EVIDENCE.** The template-driven-omission risk named earlier in this document applies here in full: a reference expectation that never prompts for a real obligation acts as a silent ceiling on what gets checked, so full kernel access must always remain available beyond whatever the Perspective suggests.

### Standard form is a reference baseline, not project truth

    REFERENCE STANDARD -> PROJECT-SPECIFIC MODIFICATIONS -> PRECEDENCE / SUPERSESSION -> EFFECTIVE PROJECT CONDITION

GO must eventually recognize supplementary conditions, amendments, addenda, project schedules, RFP terms, negotiated deviations, responsibility matrices and project-specific commercial modifications — and record each delta with its source, effect, provenance to exact project evidence, and a status of explicit / apparent / conflicting / unresolved / superseded / requires-clarification, reusing the existing resolution and supersession vocabulary rather than inventing one.

Modification is the norm, not the exception: British Columbia publishes its own supplementary conditions for both CCDC 31 and RAIC Document Six, and CCA 1 makes precedence itself a per-project election. **A CONTRACT NAME DOES NOT SETTLE THE CONTRACT.** A form identification is a question to verify, never a conclusion, and a contract name alone never supplies missing clauses.

**Contract form and jurisdiction are separate attributes that interact.** Prompt-payment regimes, lien/holdback legislation, the Quebec CCQ context, public procurement rules and professional regulation are recorded separately and never inferred from a form name or from document language.

### Protected material

**ARCHIOSK MAY EXPLAIN THE MAP; THE AUTHORITATIVE PUBLISHER REMAINS THE SOURCE OF THE STANDARD FORM.** For copyrighted or licence-restricted forms the Library stores a reference record and a verified official access path, never the protected text — and copyright is never a reason to omit a form. A Library summary is not a substitute for the actual contract document.

**POSSESSION FOR PROJECT ANALYSIS DOES NOT CREATE PUBLICATION OR REDISTRIBUTION RIGHTS.** An authorized user may place a legitimately obtained contract inside their private project and GO may analyse it within that governed boundary; it does not thereby become Library material, cross-project reference content, training material, or public content. **The project copy — including its supplementary conditions, amendments, addenda and deviations — is the project evidence GO must analyse.**

This modernizes, rather than carries forward, the historical framing: ARCHIOSK is analytical decision support, professional and legal review remains applicable, outputs require verification, and CCDC text is not reproduced. The obsolete "non-confidential demo only" wording does not survive into the private-project architecture, because private project analysis is exactly what that architecture now governs.
