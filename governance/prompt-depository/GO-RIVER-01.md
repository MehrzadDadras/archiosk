# GO-RIVER-01 — River — Evidence Relationship and Consequence Flow

| Field | Value |
|---|---|
| Prompt ID | GO-RIVER-01 |
| Title | River — Evidence Relationship and Consequence Flow |
| Agent | Unassigned (implemented governing relationship programme) |
| Status | APPROVED |
| Purpose | Preserve River as GO's governed, inspectable relationship and consequence-flow layer across project evidence, modalities, findings, requirements, decisions, and other supported project objects. |
| Product Owner acceptance | Approved and implemented; corroborated by the implemented MM6 Relationship River and later Product Owner-commissioned CA1D River surfaces. |
| Lineage | Dedicated River programme anchor. Existing implementation documentation remains authoritative and is not duplicated: [Kernel Object Model — MM6](../current/kernel-object-model.md) and [STATUS — Camel MM6](../STATUS.md). Related, not absorbed: [GO-HELIX-01](GO-HELIX-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), and [CLAUDE-HOLODECK-WORLDS-SPIN-01](CLAUDE-HOLODECK-WORLDS-SPIN-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Confirmed principles

- Project evidence must not be treated as isolated document snippets.
- Relationships carry provenance and remain inspectable.
- Consequential relationships may cross documents, disciplines, revisions, and modalities.
- A relationship discovered during one investigation may become the path for another Spin-Game.
- Relationships help GO follow propagation and convergence without inventing causal certainty.
- Explicit and inferred relationships remain distinguishable.
- Uncertainty or confidence remains visible where a relationship is inferred rather than directly evidenced.
- River supports human inspection of why two project objects were connected.

## Governed relationship vocabulary

Repository evidence confirms these `KNOWN_RELATIONSHIP_TYPES` values among a larger governed vocabulary:

- `depends_on`
- `blocks`
- `affects`
- `supports`
- `contradicts`

This list is not exhaustive. The repository's existing `KNOWN_RELATIONSHIP_TYPES` is canonical; do not invent a parallel ontology.

## Existing machinery

The implemented machinery includes `record_evidence_relationship`, `KNOWN_RELATIONSHIP_TYPES`, the cross-document/cross-modal relationship facilities in [services/case_workspace.py](../../services/case_workspace.py), the bounded River viewer, and later CA1D River Action Stack surfaces recorded in `UI_REFERENCE_MAP.md` and `CONTINUATION_CHECKPOINT.md`. This record does not modify or duplicate those components.

## Relationships to other programmes

### Helix

[GO-HELIX-01](GO-HELIX-01.md) defines the convergence model. River makes connective evidence between consequential strands traversable so Spin can test whether those strands appropriately mesh. River and Helix remain distinct.

### Prompt-Spin-Games

[GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) may traverse River to follow consequences, launch propagation review, test contradiction, inspect dependencies, test convergence, find supporting or weakening evidence, and discover where a changed condition warrants further investigation. River is not itself a Spin-Game.

### Multimodal intelligence

Implemented MM1–MM6 evidence machinery supports relationships across registered text, tables, drawings/images, structural units, addressable regions, and other validated endpoints. Supported examples include requirement text and drawing evidence, addenda and affected schedules, narrative and table evidence, drawing regions and commissioning evidence, and revision deltas with downstream evidence. These relationships remain governed evidence connections, not automatic causal conclusions.

### Composer and findings

River relationships may support a finding's explanation and evidence trace. The normal experience remains concise while allowing inspection of triggering evidence, followed sources, relationship types, and consequential paths. Do not expose private chain-of-thought.

## Governance boundary

River must not silently turn inferred relationships into project truth. Preserve distinctions among direct evidence, derived or inferred relationships, confidence, authority, and human adjudication where consequential. Do not automatically correct the project because a relationship suggests a conflict or gap.

## Recovery status

**RECOVERY PENDING:**

- original River Prompt IDs and programme sequence;
- exact `CA1D-RIVER-01/02/03` prompt wording;
- full relationship-type history;
- exact “Make the River Visible” Product Owner prompt;
- UI treatment and visualization decisions;
- historical River acceptance reports;
- original metaphors or diagrams.

Do not invent these. Future recovered material may enrich this record while preserving original source wording, implementation lineage, Product Owner acceptance, and later evolution.

## Exact prompt text

```text
River is GO's relationship layer for recording, traversing, and making consequential connections between project evidence, findings, requirements, documents, modalities, decisions, and other project objects.

The purpose is not simply to create links.

The purpose is to let GO follow how one piece of evidence affects, depends on, supports, contradicts, blocks, or otherwise changes the significance of another.
```

## Execution references

- Run: Implemented through Camel MM6 and later CA1D River evolution; exact historical run references recovery-pending
- Result: `governance/current/kernel-object-model.md`; `governance/STATUS.md`; `UI_REFERENCE_MAP.md`; `CONTINUATION_CHECKPOINT.md`
- Commit: Exact full lineage recovery-pending
