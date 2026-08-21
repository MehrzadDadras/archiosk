# Governance-of-Governance — How This Baseline Itself May Change

**Status:** Governing process, ratified this session by the process it now describes.

## The pipeline this baseline was produced by, now the standing process

Proposed → adversarially reviewed and challenged → ratified → filed as specified-unbuilt or deferred-reserved → implemented → current. This document exists because the nine-round review that produced this baseline was itself an instance of this pipeline — a change to constitutional invariants or kernel structure should go through comparably real scrutiny, not be adopted by assertion. This is a demonstrated process, not a hypothetical one.

## No silent governance mutation

The same discipline `constitutional-invariants.md` #1 requires of project data applies to the governance documents themselves: a rule does not change by quietly editing this baseline. A change to `constitutional-invariants.md` requires its own recorded rationale, its own supersession record, and preservation of the prior wording — not an in-place edit with no trace.

## Historic preservation

Nothing in `history-mapping.md`'s corpus is ever edited to "fix" it retroactively. If a historic document's content is wrong, superseded, or embarrassing, the correction is a *new* document that supersedes it, with the historic document preserved verbatim and the supersession relationship recorded — the same non-destructive-correction discipline (constitutional invariant 5) applied to governance material itself, not just project data.

## Precedence among ratified records

When two authoritative programme or governance records materially conflict, the later explicit Product Owner-ratified decision governs unless that later decision explicitly preserves the earlier rule. Historical records remain preserved for lineage, but do not regain authority merely because they are older or more broadly worded. Product Owner corrections may explicitly narrow or override earlier governance.

`SUPERSEDED` means the identified earlier rule no longer governs within the stated superseded scope. A partial supersession leaves every unaffected part of the earlier record in force. `ABSORBED` means the governing concept continues through the identified successor rather than ending. These relationships must identify their scope and successor; similarity or overlap alone is not supersession or absorption.

Current canonical or implemented governance remains authoritative unless a later ratified Product Owner decision changes it. A preserved history or prompt corpus is therefore not a flat set of equally current authorities: status, lineage, scope, ratification, and chronology must be resolved before applying a record.

## ADR identity is durable, not filing-order

**General principle, not a one-off fact about ADR-032:** an ADR's number is a permanent, citable identity, not a position in a sequence. Renumbering an ADR to preserve tidy sequential filing is not free — it invalidates every existing citation to that number, in code comments, in other documents, anywhere. ADR-032 remains a permanent landmark identity specifically because it is already cited by number in live code (`src/ai/AICapability.ts`'s docstring cites "ADR-032-R08" directly) — a concrete, evidenced cost of renumbering, not a hypothetical one. Any future ADR numbering scheme should assume gaps and out-of-sequence landmark numbers are normal and acceptable, and should never assume sequential numbers can be safely renumbered later without cost.

## Constitutional amendment authority

Not designed in operational detail here (that belongs with `deferred-reserved/reservations.md`'s governance-process items, several of which — change-proposal review, conflict-escalation, risk-acceptance — are already specified in the historic Explorer corpus's `GOVERNANCE-*` schema family, mined for principle rather than adopted as structure). The minimum standing rule: a constitutional invariant may only be added, merged, or reworded through a recorded, attributed, reasoned act — never a silent edit — and the prior wording must remain reconstructable.

**Update (`CLAUDE-GOVERNANCE-TEMPLATE-FAMILY-01`, 2026-08-20):** the three governance-process items named in the paragraph above — change-proposal review, conflict-escalation, and risk-acceptance — now have adopted structure in `governance/templates/` (`GOV-CN-`, `GOV-CR-`, `GOV-X-` respectively), alongside templates for principles, decisions, supersession, and test-oracles. Those are **blank forms, not governance**: filing one creates no authority, and none of this document's principles are changed by them. Constitutional amendment authority itself remains undesigned in operational detail, and a constitutional invariant remains outside what a `GOV-X-` waiver may reach.
