# GO-CAMEL-MM-01 — Camel / MM1–MM9 — Multimodal Project Intelligence Programme

| Field | Value |
|---|---|
| Prompt ID | GO-CAMEL-MM-01 |
| Title | Camel / MM1–MM9 — Multimodal Project Intelligence Programme |
| Agent | Unassigned (implemented multimodal programme) |
| Status | APPROVED |
| Purpose | Preserve Camel/MM1–MM9 as GO's governed multimodal evidence, perception, relationship, investigation, work-product, and integration programme. |
| Product Owner acceptance | Approved and substantially implemented; MM1–MM9 are recorded as implemented in canonical governance. |
| Lineage | Dedicated depository anchor for Camel/MM1–MM9. Existing programme and implementation records remain authoritative and are not duplicated: [Camel Multimodal Programme](../specified-unbuilt/camel-multimodal-programme.md), [Kernel Object Model](../current/kernel-object-model.md), and [STATUS](../STATUS.md). Related, not absorbed: [GO-RIVER-01](GO-RIVER-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), [GO-HELIX-01](GO-HELIX-01.md), [GO-COMPOSER-01](GO-COMPOSER-01.md), and [Presentation Intelligence](../specified-unbuilt/presentation-intelligence.md). |
| Superseded by | None |
| Absorbed into | None |

## Two-layer distinction

### Human Work Surface

Users should be able to open, inspect, compare, mark up, and—where appropriately supported—edit common project evidence types.

### AI Intelligence Layer

GO should be able to ingest and interpret underlying evidence structure and relationships across modalities.

The layers are related but distinct. Do not confuse “the user can open the file” with “GO can reliably understand the evidence inside it.”

## Confirmed programme concepts

- staged multimodal development through MM1–MM9;
- PDF and document structure;
- spreadsheets and tables;
- drawings;
- images;
- cross-document and cross-modal relationships;
- revision and comparison intelligence;
- confidence and provenance;
- routine in-app editing where governed and appropriate.

## Canonical structural concepts

Repository evidence confirms `Source`, `StructuralUnit`, `AddressableRegion`, and `EvidenceItem`. Do not invent replacement primitives where these serve the purpose. Multimodal evidence remains addressable and traceable at useful granularity so findings can point to an actual source region rather than only a parent filename.

## Relationships to other programmes

### River

[GO-RIVER-01](GO-RIVER-01.md) records the relationship layer. MM6 established the bounded cross-document/cross-modal Relationship River. Multimodal machinery perceives and addresses evidence; River records and traverses meaningful relationships among evidence. They remain distinct.

### Spin, Spin-Games, and Helix

[GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) and [GO-HELIX-01](GO-HELIX-01.md) depend on honest multimodal capability boundaries. Smarter Spin may read text, inspect supported drawing/image evidence, understand supported tables, compare revisions, traverse evidence relationships, and report uncertainty where a modality cannot be interpreted reliably. Never imply visual or table understanding when only text extraction was available.

### Composer

[GO-COMPOSER-01](GO-COMPOSER-01.md) may explain multimodal findings and evidence traces without flattening modality-specific uncertainty.

### Presentation Intelligence

[Presentation Intelligence](../specified-unbuilt/presentation-intelligence.md) is a related, separately specified future programme created after the accepted Camel close-out. Do not silently absorb PowerPoint or Presentation Intelligence into MM1–MM9.

## MM6 relationship vocabulary

The canonical repository vocabulary includes `depends_on`, `blocks`, `affects`, `supports`, and `contradicts`, among additional governed types. `KNOWN_RELATIONSHIP_TYPES` remains authoritative.

## Confidence and provenance

Multimodal interpretation carries source provenance, an addressable location where possible, confidence or uncertainty, and a distinction between direct and derived evidence. Do not silently turn OCR, visual inference, or table interpretation into unquestioned fact.

## Editing boundary

Human-facing in-app editing may exist for routine supported evidence types, but editing authority remains governed separately from interpretation. AI is not authorized to rewrite authoritative project evidence merely because it can read it.

## Recovery status

The canonical Camel record preserves the MM1–MM9 stage sequence, scope, and milestones in substance. The following exact historical material remains **RECOVERY PENDING**:

- original MM1–MM9 prompt texts;
- original Camel Grand Plan wording;
- original per-stage acceptance reports;
- original diagrams or metaphors;
- complete history of deprecated or superseded multimodal approaches.

Do not reconstruct these from guesses. Future recovered material may enrich this record without replacing authoritative current implementation governance or destroying lineage.

## Exact prompt text

```text
ARCHIOSK/GO must be able to work across project evidence modalities — not only plain text — so that project review, comparison, Spin, River, Composer, and reporting can reason across documents, drawings, tables, spreadsheets, images, revisions, metadata, and other structured or visual evidence.
```

## Execution references

- Run: MM1–MM9 implemented and closed out; exact original run sequence is preserved in canonical governance, while original prompt/run artifacts remain recovery-pending
- Result: `governance/specified-unbuilt/camel-multimodal-programme.md`; `governance/current/kernel-object-model.md`; `governance/STATUS.md`
- Commit: Stage commits are recorded in canonical Camel/STATUS governance; no new implementation commit in this preservation operation
