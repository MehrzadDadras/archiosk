# External Reference Acquisition Register

**Layer 1 of the three-layer contract-knowledge architecture. Governs nothing.**

This file records **how ARCHIOSK learned** what it believes about external standard
forms — provenance, research date, source class, corrections, and what remains
unverified. It is not user-facing, it is not project evidence, and it confers no
authority. The durable *rules* live in
[`../specified-unbuilt/perspective-and-contract-dna.md`](../specified-unbuilt/perspective-and-contract-dna.md);
this is the audit trail beneath them.

Established under `CLAUDE-CONTRACT-KNOWLEDGE-03`, 2026-08-23, after a location check
found no existing register could cleanly own external publisher material:
`spare-parts-yard.md` holds parked built code, `back-catalog/REGISTER.md` indexes this
repository's own governance history, `deferred-reserved/reservations.md` holds gaps never
designed, `vision/CANDIDATE-REGISTER.md` holds vision candidates, and
`prompt-depository/PROMPT_REGISTER.md` is bound to prompts by its own contract. **Do not
create a second register overlapping this one.**

---

## The licensing rule this register exists to honour

> **ARCHIOSK MAY EXPLAIN THE MAP; THE AUTHORITATIVE PUBLISHER REMAINS THE SOURCE OF THE
> STANDARD FORM.**

Standard forms are copyrighted and licence-restricted. Several require a publisher's
authorization seal for lawful use. ARCHIOSK therefore stores a **structured reference
record and a verified official access path** — never the protected text — and the form is
**never omitted for being protected**. A summary is not a substitute for the document.

**Possession for project analysis does not create publication or redistribution rights.**
An authorized user may place an executed, issued, RFP or otherwise legitimately obtained
contract inside their own private project, and GO may analyse it within that governed
project boundary. It does **not** thereby become Library material, cross-project
reference content, training material, or public ARCHIOSK content.

## Record shape (Layer 2 `ReferenceStandard`)

`identifier` · `full_title` · `edition_year` · `issuing_organization` ·
`official_source_url` · `status` · `parties` · `relationship_edge` · `delivery_context` ·
`payment_basis` · `concepts_supported` · `related_forms` · `jurisdiction_notes` ·
`research_date` · `provenance` · **`licence_limitation` (mandatory, never empty)**

## Source classes used in `provenance`

`ISSUER` (the publishing body itself) · `PROFESSIONAL_BODY` (RAIC/OAA/AIBC/ACEC practice
material) · `PUBLIC_GUIDANCE` (government procurement guides) · `COMMENTARY` (law-firm and
trade-press analysis). **Prefer the issuer.** Commentary may inform structure; it is never
recorded as the authority. Every claim below is classed, and the three epistemic
categories are never merged:

- **FACT** — stated by an authoritative public source.
- **INTERPRETATION** — professional reading of that source.
- **ARCHIOSK EXPECTATION** — our own investigative inference. Never evidence.

---

## Records — CCDC (Canadian Construction Documents Committee)

Official catalogue: <https://www.ccdc.org/documents/> · researched 2026-08-23 · `ISSUER`
· `licence_limitation`: copyrighted; several require a CCDC copyright seal for use;
reference-only, text not stored.

| Identifier | Edition(s) | Relationship edge | Payment basis |
|---|---|---|---|
| CCDC 2 | 2020 | Owner → Contractor | stipulated price |
| CCDC 2CcQ | 2024 | Owner → Contractor (Civil Code of Québec) | stipulated price |
| CCDC 2MA | 2023 | Owner → Contractor (master agreement) | — |
| CCDC 3 | 2016 | Owner → Contractor | cost plus fee |
| CCDC 4 | 2023 | Owner → Contractor | unit price |
| CCDC 5A | 2010, **2025** | Owner → Construction Manager (**agent**) | fee for services |
| CCDC 5B | 2010, **2025** | Owner → Construction Manager (**at risk**) | services + Work |
| CCDC 9A | 2018 | Contractor (declarant) | payment-distribution evidence |
| CCDC 9B | 2018 | Subcontractor (declarant) | payment-distribution evidence |
| CCDC 11 | 2019 | Contractor qualification statement | — |
| CCDC 14 | 2013, **2026** | Owner → Design-Builder | stipulated price |
| CCDC 15 | 2013, **2026** | **Design-Builder → Consultant** | schedule-defined |
| CCDC 17 | 2010, **2025** | Owner → Trade Contractor (on CM projects) | stipulated price |
| CCDC 18 | 2023 | Owner → Contractor (civil works) | unit/stipulated hybrid |
| CCDC 30 | 2018, **2025** | multi-party IPD | risk/reward pool |
| CCDC 31 | 2020 | **Owner → Consultant** | fixed / %-of-Work / time-based / hybrid |
| CCDC 32 | 2026 | Owner → Design-Builder (**progressive**) | two-phase |
| CCDC 33 | 2026 | **Design-Builder → Consultant** (progressive) | schedule-defined |
| CCDC 41 | — | insurance requirements | — |
| CCDC 220/221/222 | 2024 | surety bond forms | — |

Guides (same licence limitation): CCDC 00, 01, 10 (delivery methods), 16 (changes),
20 (contract administration), 21 (insurance), 22 (surety bonds), 23 (calling bids),
24, 29 (pre-qualification), 30-G, 32-G, 40 (mediation/arbitration), 44, 45, 46, 47.

**FACT** — CCDC 31 Schedule A enumerates service categories: Advisory, Project
Initiation, Conceptual Design, Preliminary Design, Detailed Design, Construction
Administration, On-Site, and Post-Construction, and supports fixed, percentage-of-Work,
time-based or combined remuneration. *(`PROFESSIONAL_BODY`/`PUBLIC_GUIDANCE`; BC publishes
its own user guide and supplementary conditions for it.)*

**FACT** — CCDC 9A/9B are sworn declarations that prior progress payments were
distributed to subcontractors and suppliers, subject to three exceptions: properly
retained holdback, payments deferred by agreement, and amounts withheld in legitimate
dispute.

**FACT** — under CCDC 5A the Owner contracts the trades directly (CCDC 17 being the
Owner↔Trade Contractor form); under CCDC 5B the Construction Manager carries the Work and
its risk.

**ARCHIOSK EXPECTATION** — 5A vs 5B is the clearest evidence that an identical job title
can sit on opposite sides of a contractual edge. Any model that stores a flat "position"
without the edge cannot represent it.

## Records — CCA (Canadian Construction Association)

| Identifier | Edition | Edge | Official source |
|---|---|---|---|
| **CCA 1** | **2021** | **Prime Contractor → Subcontractor** | <https://www.cca-acc.com/cca_documents/cca-1-2021-stipulated-price-subcontract/> |

`ISSUER` + `COMMENTARY` · researched 2026-08-23 · `licence_limitation`: copyrighted;
reference-only.

**FACT** — CCA 1 – 2021 is the standard stipulated-price subcontract between contractor
and subcontractor, revised to align with CCDC 2 – 2020. Users elect either a
refer-by-reference or a standalone approach by completing one of two alternative pages
and discarding the other.

**FACT (precedence — the most important acquisition in this register)** — the parties
**elect** whether the Prime Contract or the Subcontract governs a conflict, and may
designate specific subcontract provisions that remain **not subordinate** to the Prime
Contract. Incorporation of the CCDC Division 01 specification is **not assumed** and must
be expressly made a contract document.

**FACT** — payment obligations reference *Payment Legislation* (Ontario's Construction Act
prompt-payment regime and provincial equivalents). *Ready-for-Takeover* replaces
Substantial Performance as the primary milestone, with the one-year warranty running from
it, and references revert to Substantial Performance where the prime contract omits it.
Indemnification is limited to direct loss and damage, excluding indirect, consequential,
punitive and exemplary damages. Adjudication under applicable provincial legislation is
preserved. *(`COMMENTARY` — WeirFoulds; not verified against the issuer's own text.)*

**ARCHIOSK EXPECTATION** — because precedence is *elected per project*, a Trade Bidder
project's governing hierarchy cannot be derived from the form name. This is the
canonical case for the delta model: identify the baseline, then find what the project
actually elected.

## Records — RAIC (Royal Architectural Institute of Canada)

| Identifier | Edition | Edge | Official source |
|---|---|---|---|
| **Document Six** | 2017, **2018** | Client → Architect | <https://raic.org/raic/canadian-standard-form-contract-architectural-services-document-six-2018-edition> |
| **Document Nine** | **2018** | **Architect → Consultant** | <https://raic.org/raic-digital-contracts/> |

`ISSUER` + `PROFESSIONAL_BODY` · researched 2026-08-23 · `licence_limitation`:
copyrighted; **requires an RAIC Authorization Seal for lawful use**; reference-only.

**FACT** — Document Six is the Canadian Standard Form of Contract for Architectural
Services; the 2017 rewrite replaced the 2006 edition and was harmonized with CCDC 2 and
ACEC 31. BC publishes its own user guide and supplementary conditions for it.

**FACT — Document Nine is the Subconsultant edge, and it is not stand-alone.** It is the
Canadian Standard Form of Contract between Architect and Consultant, recommended for
engineering consultants and other design professionals (landscape architects, interior
designers, food-service consultants and other architects). It **must not be used without
a Prime Contract attached as Appendix 1**.

**ARCHIOSK EXPECTATION** — that dependency is authoritative confirmation that a
downstream agreement incorporates its upstream contract by reference. A Subconsultant
project's obligations are therefore not readable from its own agreement alone, which is
precisely why the upstream edge must be an explicit, first-class attribute.

## Records — ACEC (Association of Consulting Engineering Companies – Canada)

| Identifier | Edition | Edge | Official source |
|---|---|---|---|
| **Document 31** | 2010 | Client → Engineer (prime) | <https://acec.ca/Publications/acec_contracts.html> |
| **Document 32** | 2011 | **Engineer → Sub-Consultant** | <https://acec.ca/Publications/acec_contracts.html> |
| Document 36 | 2012 | Client → Engineer (studies and reports) | <https://acec.ca/Publications/acec_contracts.html> |

`ISSUER` + `COMMENTARY` · researched 2026-08-23 · `licence_limitation`: copyrighted;
reference-only.

**FACT** — ACEC 31 – 2010 is the Engineering Agreement Between Client and Engineer, a
major rewrite of 31-1996, prepared primarily for small-to-medium projects, and explicitly
contemplates the Engineer acting **either as lead (prime) consultant or as one of several
consultants**. A companion Guide exists.

**FACT** — ACEC 36 – 2012 is an Agreement of Studies and Reports between engineer and
client for advisory/analysis work. **It is not a subconsultant form.** ACEC **32 – 2011**
is the Agreement between Engineer and Sub-Consultant.

**Numbering collision — recorded as a trap.** **ACEC Document 31 ≠ CCDC 31.** Different
issuers, same number, adjacent purpose. Matching on the bare numeral would conflate an
engineering agreement with a CCDC consultant contract.

---

## Correction history

Corrections are preserved, never silently overwritten.

| Date | Correction |
|---|---|
| 2026-08-23 | **CCDC 6A / 6B do not exist** in any edition. Searched exhaustively across the current catalogue and all recovered historical material. The intended A/B pair is **CCDC 9A / 9B** (Statutory Declaration of Progress Payment Distribution, by Contractor / by Subcontractor). The 6A/6B assumption is discarded and must not be reintroduced. |
| 2026-08-23 | **ACEC 36 is not the subconsultant form**, contrary to an earlier ARCHIOSK working assumption. It is Studies and Reports. **ACEC 32 – 2011** is the Engineer → Sub-Consultant agreement. |
| 2026-08-23 | The Prime → Subcontractor edge is **not a CCDC form**. It is **CCA 1**, published by the Canadian Construction Association. A model assuming the CCDC family spans the whole chain has a hole exactly where the Trade Bidder perspective lives. |
| 2026-08-23 | An earlier recovery sweep of the historical Holodeck material reported far fewer CCDC references than exist, because `holodeck/.gitignore` contains `archive/` and ripgrep honours it by default. Re-running with `--no-ignore --hidden` moved the count from 4 files to 155. **Any earlier "searched and found nothing" conclusion about that material is unreliable.** |

## Unverified and unresolved

- **RAIC Document Nine edition currency** — 2018 edition confirmed; whether a later edition exists is unverified.
- **ACEC Document 32 – 2011** — identified authoritatively as the engineer→sub-consultant form; its mechanics have **not** been researched.
- **CCA 1 mechanics** rest on `COMMENTARY`, not the issuer's own text. Flagged for re-verification against CCA material.
- **Consultant → sub-consultant under CCDC 31** — CCDC publishes no equivalent to RAIC 9 / ACEC 32; whether CCDC 31 contemplates sub-consultants is unresolved.
- **Supplier / manufacturer** — no standard form identified; purchase-order practice not researched.
- Change/claims/notice depth (CCDC 16, 20), insurance/bonding (41, 21, 22, 220–222), pre-qualification (11, 29), and jurisdictional overlays (prompt payment, lien/holdback, Québec CCQ, professional regulation) remain **unacquired**.

## Acquisition backlog, in dependency order

1. ACEC 32 – 2011 mechanics *(completes the Subconsultant edge)*
2. CCA 1 re-verification against issuer material *(currently commentary-backed)*
3. CCDC 16 and 20 — changes, notices, contract administration
4. CCDC 5A/5B/17 mechanics beyond the position difference
5. CCDC 14/15/32/33 design-build family detail
6. Insurance, surety, pre-qualification
7. Jurisdictional overlays

> **KNOWLEDGE ACQUISITION IS CONTINUOUS AND VERSIONED, NOT A ONE-TIME COMPLETION EVENT.**
> Standard forms are reissued — CCDC 5A/5B/17/30 and the whole design-build suite are
> mid-refresh across 2025–2026. A record without an edition year is not knowledge.
