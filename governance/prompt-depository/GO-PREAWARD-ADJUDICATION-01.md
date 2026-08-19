# GO-PREAWARD-ADJUDICATION-01 — Pre-Award Design-Build Pursuit and Design-Development Adjudication Engine

| Field | Value |
|---|---|
| Prompt ID | GO-PREAWARD-ADJUDICATION-01 |
| Title | Pre-Award Design-Build Pursuit and Design-Development Adjudication Engine |
| Agent | Unassigned (governed pre-award pursuit programme) |
| Status | APPROVED |
| Purpose | Preserve GO's adopted pre-award design-build pursuit direction: evidence-grounded requirement adjudication, ambiguity investigation, phase-aware design-development coordination, risk surfacing, and governed questions or actions under human design authority. |
| Product Owner acceptance | Product Owner-adopted programme direction supported by current product lineage. Core primitives and bounded workflows exist across Requirements, RequirementAdjudication, GO QA/QC phase assessment, Investigations, River, Camel/MM, Composer, and RFI governance; no single monolithic “adjudication engine” is claimed as implemented by this record. |
| Lineage | Dedicated programme anchor for the current pre-award pursuit and design-development composition. Current implementation truth remains [STATUS](../STATUS.md), [Kernel Object Model](../current/kernel-object-model.md), `CLAUDE-GO-QAC-01`, and [Composer Result Contract](../current/go-dna-01-composer-result-contract-and-panel-zoning.md). Related, not absorbed: [GO-COMPOSER-01](GO-COMPOSER-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), [GO-HELIX-01](GO-HELIX-01.md), [GO-RIVER-01](GO-RIVER-01.md), and [GO-CAMEL-MM-01](GO-CAMEL-MM-01.md). RFI implementation and authority remain canonical in the Kernel Object Model and current capability governance. |
| Superseded by | None |
| Absorbed into | None |

## Governing direction

GO should support the real work of pre-award design-build pursuits: ingesting RFP evidence, adjudicating requirements, investigating ambiguity, coordinating design-development evidence, surfacing risk, and producing governed questions or actions without taking design authority away from the team.

This is a composition of governed capabilities, not authorization to create a parallel project model, automated design authority, or one opaque “engine” that bypasses existing primitives.

## Evidence framework

Preserve the investigative and traceability framework:

> **SOR → Requirement Domain → Performance Requirement → System/Assembly → Design Criteria → IFC Evidence → Review Finding**

The chain is a review framework, not a claim that each named stage is already a dedicated canonical object or mandatory field. Existing `Source`, `Requirement`, `StructuralUnit`, `AddressableRegion`, `EvidenceItem`, `Relationship`, `RequirementPhaseAssessment`, `Finding`, and `RequirementAdjudication` primitives remain authoritative where they express the chain. Do not mint duplicate objects merely to reproduce its labels.

“IFC Evidence” means evidence appropriate to the applicable issued-for-construction or claimed delivery state where that state is actually established. GO must not demand IFC maturity during an earlier design phase or invent a project milestone.

## Finding characterizations

Known useful characterizations include:

- **Confirmed**
- **Partial**
- **Not demonstrated**
- **Contradiction**
- **RFI candidate / governed question**, where appropriate

These are programme-level review characterizations, not a new closed storage vocabulary. Use current canonical vocabularies where they already govern:

- `RequirementAdjudication` answers Satisfied, Partially Satisfied, Not Satisfied, Not Applicable, or Accepted Alternative.
- `RequirementPhaseAssessment` reuses the phase-aware information-sufficiency vocabulary, including expected later, below phase expectation, not demonstrated, conflicting, uncertain/investigate, and conforming for the current phase.
- Findings, Claims, and Relationships retain their own distinct status and provenance models.

Do not translate “Not demonstrated” automatically into noncompliance. Missing evidence, evidence not yet expected, insufficient maturity, contradiction, and authority uncertainty remain different conditions.

## Phase-aware design-development review

The current `CLAUDE-GO-QAC-01` lineage establishes the governing principle that conformance must be judged against both the SOR requirement and the maturity expected at the current project phase. A 30% submission must not be judged against 90% or IFC expectations unless the project itself establishes that requirement.

Project-defined expected-information profiles govern when available. Inferred or secondary expectations remain labeled as such. Phase assessment is provisional GO-authored analysis and never silently becomes human Requirement adjudication.

## RFI and governed-question grammar

Preserve:

> **Evidence → Concern → Question**

This grammar is appropriate where GO has evidence of a consequential ambiguity, conflict, omission, or unresolved condition but lacks authority to decide it. Do not force every finding into RFI form.

Current RFI governance remains authoritative:

- an RFI draft is grounded in an existing governed Case and validated Finding;
- origination and response are directionally controlled by the locked Project Operating Environment;
- drafting, review, issue, response, and export remain separate governed stages;
- an RFI candidate or Composer suggestion is not an issued RFI;
- GO does not issue a consequential question autonomously.

## Human adjudication and design authority

Consequential requirement interpretation remains subject to human adjudication. GO may extract, compare, investigate, characterize, trace, and recommend, but must not:

- decide design compliance autonomously;
- silently choose among ambiguous contractual interpretations;
- modify authoritative design evidence;
- treat a phase assessment as a human adjudication;
- issue an RFI or direct the design team without the applicable governance gate;
- infer authority from confidence or model fluency.

`RequirementAdjudication` attribution and Product Owner/human-authority governance remain authoritative. Agent assessments stay visibly distinct from human-reviewed decisions.

## Relationship to Composer

[GO-COMPOSER-01](GO-COMPOSER-01.md) presents evidence-grounded findings, questions, uncertainty, and optional next steps. Composer may help continue an investigation or prepare an RFI candidate, but conversational convenience does not bypass adjudication or RFI governance.

## Relationship to Spin-Games and Helix

[GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) provides bounded investigative compositions for change, conflict, missing evidence, authority, propagation, and convergence. [GO-HELIX-01](GO-HELIX-01.md) supplies the question of whether consequential project strands appropriately mesh at the maturity being claimed.

Neither Spin-Games nor Helix replaces requirement adjudication or professional design judgment.

## Relationship to River

[GO-RIVER-01](GO-RIVER-01.md) makes requirement, system, evidence, contradiction, dependency, and consequence relationships traversable. River connections retain provenance and uncertainty and must not manufacture causal or contractual certainty.

## Relationship to Camel/MM

[GO-CAMEL-MM-01](GO-CAMEL-MM-01.md) provides addressable multimodal evidence across documents, tables, spreadsheets, drawings, images, and revisions. The pre-award programme must not imply visual, table, drawing, or IFC understanding when only text extraction was available.

## Programme boundary

This preservation record does not authorize implementation, a new adjudication engine, requirement-schema changes, automated design review, risk scoring, RFI changes, new finding statuses, or modification of current authority controls.

## Recovery status

**RECOVERY PENDING:**

- original programme prompt;
- exact engine architecture;
- complete requirement workflow;
- original evidence-framework wording and mappings;
- historical test projects;
- historical acceptance reports.

Do not invent these. Later recovered material may enrich this record without replacing its stable identity, current canonical primitives, or human-authority boundary.

## Exact prompt text

```text
GO should support the real work of pre-award design-build pursuits: ingesting RFP evidence, adjudicating requirements, investigating ambiguity, coordinating design-development evidence, surfacing risk, and producing governed questions/actions without taking design authority away from the team.
```

## Execution references

- Run: None for a monolithic engine; current capability lineage includes Foundation RequirementAdjudication, `CLAUDE-GO-QAC-01`, Camel/MM, Composer, River, Spin, and governed RFI tranches
- Result: Programme direction preserved against substantial bounded product lineage; no implementation performed
- Commit: None
