# Snapshot 002 Reconstruction (Prompt 17 §20)

Reconstructed from Snapshot 002's governed/derived state only (`reconstruction_002.json`, `snapshot_002.json`) — not by re-reading the source files, except where a field is itself a provenance citation.

## A. Project identity
North River Emergency Operations and Community Resilience Centre ("the Project" / "the Facility"), project_id `nreocrc`. Governed by one registered Source, `NREOCRC-OPR-001.md` (Owner's Project Requirements), `document_id=NREOCRC-OPR-001`, `revision=0`, `document_status="ISSUED WITH RFP — CONTRACTUAL DOCUMENT"`, `document_authority=contractual`.

## B. Owner / issuer
`issuer = "North River Infrastructure Corporation"` (derived generically from the Source's own front-matter table, not typed from memory).

## C. Delivery / procurement model
One `MaturityRecord` (`maturity_type=design`, `value="rfp_pre_proposal"`) — an open-world extension value, since no canonical design-maturity stage fits an RFP/pre-Proposal state. **Known limitation, unchanged from Snapshot 001**: this value describes a procurement/commercial milestone, not a design maturity stage, and BEEHIVE still has no separate axis to hold it correctly.

## D. Current issued documents
Per the Expected-Information re-run over the Section 3 cross-reference table (found generically): `NREOCRC-OPR-001` (this document, "Issued") and the Functional Program (Appendix OPR-1 of this document, "Issued") are both already-present, observed documents.

## E. Future expected documents
Four documents are stated "To be issued" with no date: `NREOCRC-IDP-001` (Indicative Design Package), `NREOCRC-SCH-001` (Procurement and Milestone Schedule), `NREOCRC-DR-001` (Data Room Document Register), `NREOCRC-PA-001 (Draft)` (Draft Project Agreement). One further reference item ("City of North River Accessibility Design Standard, 2023 ed.") is bucketed `UNKNOWN` — its own status text ("Incorporated by reference; to be listed") didn't match any of the three generic status buckets cleanly.

One document is stated **"Issued concurrently"** — `NREOCRC-RFP-001` (the RFP main document) — and is bucketed distinctly from the four above, since it is *not* a future item; it is a presently-relied-upon document that is simply absent from this corpus state.

## F. Authority hierarchy
Reconstructed as an ordered 8-item list directly from Section 2.2's own numbered text (generic numbered-list parse, qualifiers preserved verbatim): (1) Project Agreement once executed, (2) Addenda (latest governing), (3) this OPR, (4) the Functional Program, (5) RFP main document (technical gaps only), (6) Accepted Proposal Commitments (bounded by the full "exceed AND do not derogate" conjunctive test, preserved verbatim this time), (7) Indicative Design Package (Indicative only), (8) Data Room material (Reference/Informational only) — with the qualifier "current statement of intent... will be restated and finalized in the Project Agreement" preserved as a trailing caveat, not silently dropped. **No Relationship edges exist for this hierarchy** — none of items 1/2/5/6/7/8 have a registered Source/Requirement of their own in this corpus state to point at.

## G. Major Requirements
59 Requirements registered: 56 via generic bracket-tag derivation, 2 via manual transcription of unlabeled clauses (2.2, 8.1), 1 via generic table-row boundary detection (Appendix OPR-1, Row 20).

## H. Mandatory items
42 of the 56 bracket-derived requirements are `mandatory` — the plurality classification, as expected for a Contractual Document.

## I. Rated items
8 requirements are `rated` (evaluation-criteria items — e.g. minimizing surface parking, architectural expression, exceeding minimum accessibility/structural/security/standby-power provisions).

## J. Indicative items
2 requirements are `indicative`: 4.6 (preliminary site/building placement concepts) and 18.3 (Future Expansion Area is not part of current contracted scope). Both remain `indicative` regardless of the containing document's own `contractual` authority — confirmed independently (see Authority Test).

## K. Informational / Reference items
4 requirements are `informational` (5.3, 8.4, 17.1, 20.1). Zero are `reference` — confirmed absent from the source's own bracket-tag usage, not a miss.

## L. Functional / security organization
Facility organized into Public / Controlled / Secure zones (Figure OPR-2.1), with a further "Restricted Communications Sub-Zone" nested inside the Secure Zone (confirmed via generic SVG text-label extraction — the label appears literally as embedded `<text>` in Figure OPR-2.1; this is textual confirmation only, not visual/spatial interpretation). Appendix OPR-1 (Functional Program) organizes 42 rooms/spaces into 7 departments. One room, Row 20 (Situational Awareness / Media Briefing Room), is generically flagged as a boundary space (Security Level value contains "/": "Secure/Controlled interface"), corroborated by an independently-found narrative cross-reference to the same row number.

## M. Major cross-references
11 Relationships, all generically derived from Section/Figure mentions within each requirement's own registered text: figure correspondences (multiple clauses → Figure OPR-2.1/2.2) and clause cross-references (including 12.3 → 4.5, corrected from the prior run's 12.3 → 4.3). 18 further "Section N" mentions were found but left unresolved because no exact clause-level Requirement exists for that bare section number (container-level references, e.g. "Section 14", "Section 18") — not fabricated as edges.

## N. Unresolved / future-confirmed information
11 requirement sections carry a generically-detected hedge phrase ("to be confirmed", "to be issued", "assumed", "approximate", etc.), preserved verbatim in their own text: 2.2, 4.2, 5.3, 6.1, 14.3, 15.1, 16.1, 18.1, 19.3, 20.1, 20.2. **Known scanning gap**: the keyword list used for this automated scan did not flag 9.4, Row 8, or 13.3 — their hedge language is still present verbatim in their registered text, just not surfaced by this particular scan.

## O. Apparent source inconsistencies
One real, generically-derived arithmetic inconsistency: Appendix OPR-1's departmental subtotal cells do not reconcile with the sum of their own line items in 5 of 7 departments, and none of {line-item sum, subtotal-cell sum, stated grand total} agree with each other (3,205 / 3,980 / 4,105 m²). Recorded as a provisional Finding (via a real Analysis run) plus a ReviewThread requesting the **Owner's** attention — explicitly not classified as Design-Builder non-compliance.

## P. Current expected-information state
See D/E above; re-run against the same historical corpus state using a fully generic per-row mechanism rather than a hand-picked document list.

## Q. Unknowns
- Whether 2.2 and 8.1 (unlabeled clauses) should default to Mandatory per Section 2.3's own stated rule — not automatically applied; left `classification=None`.
- 12.2's actual epistemic content (Standby Power Sizing Reference table) — not represented by any Requirement in this snapshot at all (see Under-Interpretation Audit).
- Whether any other document in the corpus uses a different clause-labeling convention than "**N.N** [LABEL]" — untested, since only one document exists in this corpus state.
- Exact resolution mechanism (if any) for the 18 unresolved bare-section references and the "Sections 12.1 through 12.3" range-reference case.
