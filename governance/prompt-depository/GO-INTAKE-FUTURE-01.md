# GO-INTAKE-FUTURE-01 — GO-Native Document Intake — Governed Project Evidence Entry

| Field | Value |
|---|---|
| Prompt ID | GO-INTAKE-FUTURE-01 |
| Title | GO-Native Document Intake — Governed Project Evidence Entry |
| Agent | Unassigned (future governed evidence-intake programme) |
| Status | DEFERRED |
| Purpose | Preserve a future native intake experience that establishes durable source identity, provenance, authority, project isolation, revision context, and downstream intelligence readiness at evidence entry. |
| Product Owner acceptance | Confirmed future programme direction. Current governed ingestion and analyze-first Data Room Reconcile are implemented foundations; the broader native-intake experience remains unimplemented. |
| Lineage | Dedicated future native-intake programme anchor. Existing implementation truth remains authoritative in [Kernel Object Model](../current/kernel-object-model.md) and the live Reconcile contract in [UI Reference Map](../../UI_REFERENCE_MAP.md). Related, not absorbed: deferred [Bug Eye — Data Room Source Continuity](../specified-unbuilt/bug-eye-data-room-source-continuity.md), [GO-CAMEL-MM-01](GO-CAMEL-MM-01.md), [GO-RIVER-01](GO-RIVER-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), and the project-establishment/territory boundary in [Territory Before Ontology](../current/meta-t01-territory-before-ontology.md). |
| Superseded by | None |
| Absorbed into | None |

## Confirmed principles

- Intake establishes where a source came from and which project owns it.
- Project isolation applies from the moment evidence enters.
- Original source identity remains durable.
- Intake supports later reconciliation, revision comparison, supersession, and missing-link detection.
- Users should not have to reconstruct provenance manually after upload.
- Intake prepares evidence for downstream Requirements, River, Spin, comparison, multimodal review, and reporting.

This is not merely a file-upload widget. Current ingestion already creates governed, project-scoped `Source` identity and provenance; this programme concerns the broader native experience and lifecycle intelligence around that foundation.

## Native intake versus generic upload

A generic upload asks: “What file did you upload?”

A future GO-native intake should also address governed questions such as:

- Which project?
- What source or type?
- Is this new, revised, superseding, or supplemental evidence?
- What authority or provenance is known?
- Does it correspond to an existing source?
- Has the authoritative file moved or disappeared?
- What downstream project intelligence should be refreshed?

Do not force the user to supply facts GO can establish reliably from governed evidence. Where identity, authority, or change meaning is uncertain, preserve uncertainty and ask rather than guess.

## Reconcile and revision awareness

The implemented Data Room Reconcile flow already analyzes and classifies files as unchanged, new, modified, missing, renamed or moved, ineligible, or ambiguous. It is analyze-first: preview does not mutate project evidence, and only explicitly confirmed new files are registered.

Preserve idempotency. Repeating reconciliation against an unchanged Data Room must not create duplicate project evidence. File-level modification, disappearance, or relocation does not by itself establish a substantive project change, supersession, or new governing requirement; those conclusions require governed review and appropriate evidence.

## Data Room and authoritative-file boundary

Preserve the near-term hybrid direction: ARCHIOSK application and intelligence may be online while authoritative full project files remain on user- or company-controlled storage. Native intake must not require ARCHIOSK to become the permanent warehouse for the entire corpus; optional future cloud hosting remains separate.

No external Data Room connector exists today. If such a source later moves or becomes unavailable, GO should preserve identity and relationships, expose the break truthfully, and support governed rerouting or recovery rather than pretending availability.

## Relationship to Bug Eye

[Bug Eye](../specified-unbuilt/bug-eye-data-room-source-continuity.md) is a related but distinct deferred watcher over external source location and governed relationships. Bug Eye may watch evidence state; native intake governs how evidence enters or is reconciled. Do not merge the subsystems by assumption.

Preserve Bug Eye's governing distinction: a changed location is not a changed identity, and a changed document is not merely a changed location.

## Relationship to Camel and multimodal intelligence

[GO-CAMEL-MM-01](GO-CAMEL-MM-01.md) supplies the governed multimodal evidence primitives, including `Source`, `StructuralUnit`, `AddressableRegion`, and `EvidenceItem`. Intake should prepare evidence for those mechanisms without duplicating them or claiming successful interpretation before registration and inspection occur.

## Relationship to River and Spin

[GO-RIVER-01](GO-RIVER-01.md) and [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) depend on trustworthy source identity and provenance. Good intake improves later relationship and investigation quality; Spin should not have to guess identity or provenance that intake could preserve. Intake itself does not determine what Spin must conclude.

## Neutral Entry and project-creation boundary

Project establishment selects or creates the project context and its operating environment. Native document intake governs evidence entry after or within that context. The current “Establish a Project” and Project Gateway/territory patterns remain related but distinct; do not collapse project identity creation and evidence lifecycle into one ambiguous operation.

## Governance boundary

Native intake preserves project isolation, source provenance, durable identity, authority distinctions, non-destructive revision and supersession, human review of consequential interpretations, and truthful unavailable or ambiguous states. It must not duplicate Sources, silently promote file changes into project truth, repair missing links without authority, or weaken storage and access boundaries.

This record does not authorize intake UI, external connectors, file watchers, storage synchronization, ingestion changes, Reconcile changes, rerouting, or runtime behaviour.

## Recovery status

**RECOVERY PENDING:**

- exact `CLAUDE-GO-INTAKE-FUTURE-01` prompt wording;
- original programme ID if different;
- native intake UI;
- detailed Reconcile workflow lineage;
- Bug Eye interaction;
- archive, move, and reroute UX;
- local or company storage integration design;
- historical prototypes or acceptance reports;
- exact metadata and intake-state model.

Do not invent these. Later recovered material may enrich this record while preserving current ingestion, Reconcile, project-isolation, storage, and evidence-model truth.

## Exact prompt text

```text
ARCHIOSK/GO should eventually have a native, governed document-intake experience that brings project evidence into the system in a way that preserves project identity, provenance, authority, revision state, and later multimodal/relationship intelligence from the beginning.
```

## Execution references

- Run: None for the broader future programme; current ingestion and Data Room Reconcile are implemented separately
- Result: Existing implementation remains documented by `governance/current/kernel-object-model.md` and `UI_REFERENCE_MAP.md`
- Commit: Future programme none; exact Reconcile and ingestion commit lineage not reconstructed here
