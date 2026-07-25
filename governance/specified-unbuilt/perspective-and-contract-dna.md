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
