# GO-RFP-PUBLICATION-BARRIER-01 — RFP Publication Barrier — Client Authoring to Blind Builder Intake

| Field | Value |
|---|---|
| Prompt ID | GO-RFP-PUBLICATION-BARRIER-01 |
| Title | RFP Publication Barrier — Client Authoring to Blind Builder Intake |
| Agent | Unassigned (governed procurement-publication programme) |
| Status | APPROVED |
| Purpose | Preserve the adopted Client-private → formal publication → physically separate blind Builder-intake boundary for RFP development and independent investigation. |
| Product Owner acceptance | Product Owner-adopted and implemented in bounded form under `CLAUDE-RFP-BOUNDARY-01`; Owner/Proponent project separation, a governed publication act, separate Proponent intake, and a no-leak proof exist. Broader publication lifecycle and Progressive Design-Build exchange remain outside this programme scope. |
| Lineage | Dedicated programme anchor for `CLAUDE-RFP-BOUNDARY-01` and the Owner/Proponent publication architecture in [Cross-Boundary Architecture](../specified-unbuilt/cross-boundary-architecture.md). Current implementation and authorization truth remains [STATUS](../STATUS.md), [Kernel Object Model](../current/kernel-object-model.md), and `tests/test_owner_proponent_isolation_01.py`. Related, not absorbed: [GO-NEUTRAL-ENTRY-01](GO-NEUTRAL-ENTRY-01.md), project capability governance in `services/environment_capabilities.py`, [Project North Star advancement](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md), and [North Bayview → Project North Star transition](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Governing project-world sequence

GO may be used first on the Client or Owner side to develop, review, reconcile, and correct an RFP. That private working corpus remains invisible to Builder or Proponent GO until the RFP is formally published.

The governed sequence is:

> **Client-private authoring and review → formal publication → separate blind Builder intake and investigation**

Publication is the only governed crossing point. The Builder project does not receive access to the Owner project; it imports the published procurement package as its own fresh evidence in an independent project context.

## After publication

- The published RFP becomes Builder-side evidence.
- Unpublished Client working material remains inaccessible.
- Builder-side GO investigates the published corpus independently.
- No hidden leakage from Client-side GO reasoning, corrections, drafts, or oracle knowledge is permitted.

Published material does not carry private authoring history, hidden working drafts, unreleased corrections, unpublished findings, internal reasoning, or evaluation truth merely because those records exist in the Owner project.

## Purpose of the proving model

This programme tests:

- role separation;
- publication state;
- blind discovery;
- information-barrier integrity;
- Client-side GO and Builder-side GO as distinct governed uses of the same platform.

The current proving exercise is intentionally **not Progressive Design-Build**. Do not infer bidirectional collaboration, ongoing shared authoring, post-publication co-development, or continuous cross-party exchange from this record. Repository governance explicitly leaves broader Progressive Design-Build collaboration outside the bounded publication implementation.

## Relationship to Neutral Entry

[GO-NEUTRAL-ENTRY-01](GO-NEUTRAL-ENTRY-01.md) remains distinct. A unified application gateway does not merge Owner and Proponent projects, evidence, authority, or confidentiality. Neutral Entry establishes the governed project context; this programme governs the publication boundary between separate project contexts.

## Relationship to project capability governance

The locked Project Operating Environment and current capability governance remain authoritative. Client/Owner and Design-Builder/Proponent are project-level contexts, not login-page choices. Publication eligibility, participant roles, available actions, and downstream workflows remain governed by project context and explicit authorization.

The implemented bounded publication transition is a separate lifecycle axis from operating environment. Neither axis is a cosmetic toggle.

## Relationship to Project North Star and blind testing

[CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md) and [CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md) preserve the proving-project lineage and blind-testing protections. Project North Star advancement must not use Owner-private material or oracle knowledge to tune Builder-side evidence or expected discovery.

The Builder-side investigator must be able to reach every expected conclusion from published evidence alone. Private truth may evaluate the result but may not become an undisclosed input to it.

## Relationship to RFP publication and issue governance

[Cross-Boundary Architecture](../specified-unbuilt/cross-boundary-architecture.md) remains the canonical programme architecture. Current bounded implementation uses an explicit Owner publication act to export selected Sources into an immutable publication artifact and an independent Proponent project to ingest the published bytes as fresh Sources.

Current implementation does not authorize broader publication anchoring, general cross-project reads, Addendum-specific lifecycle machinery, bidirectional exchange, or evaluation-stage workflow. Those remain separately governed.

## Information-barrier invariants

- The Owner and Proponent projects remain physically and logically separate.
- Publication transfers only explicitly selected published evidence.
- Unpublished evidence stays in the Owner project.
- The Proponent project has no privileged read path into the Owner project.
- Client reasoning, drafts, corrections, and oracle material never silently cross the boundary.
- Formal publication does not make unrelated Owner-private content discoverable.
- Builder conclusions remain grounded in Builder-visible evidence.

## Programme boundary

This preservation record does not authorize access-control, publication, ingestion, project-registration, capability, lifecycle, or UI changes. It records the adopted boundary and links current implementation truth.

## Recovery status

**RECOVERY PENDING:**

- original prompt;
- exact publication workflow history beyond current governed records;
- publication and intake UI history;
- RFP project-registration sequence;
- historical blind-test and acceptance reports.

Do not invent these. Later recovered source material may enrich this record without replacing its stable identity, current bounded implementation, or blindness and information-barrier invariants.

## Exact prompt text

```text
GO may be used first on the Client/Owner side to develop, review, reconcile, and correct an RFP. That private working corpus must remain invisible to Builder/Proponent GO until the RFP is formally published.
```

## Execution references

- Run: `CLAUDE-RFP-BOUNDARY-01`
- Result: Bounded Owner-private → publication → separate Proponent-intake boundary implemented and no-leak tested
- Commit: See repository history and current `governance/STATUS.md`; exact historical acceptance commit recovery pending
