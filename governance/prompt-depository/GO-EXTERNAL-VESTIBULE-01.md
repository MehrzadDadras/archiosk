# GO-EXTERNAL-VESTIBULE-01 — External Source Vestibule — Governed Entry of Outside Evidence

| Field | Value |
|---|---|
| Prompt ID | GO-EXTERNAL-VESTIBULE-01 |
| Title | External Source Vestibule — Governed Entry of Outside Evidence |
| Agent | Unassigned (future external-evidence admission programme) |
| Status | DEFERRED |
| Purpose | Preserve a controlled evidence-admission boundary where outside information retains provenance, uncertainty, and non-authoritative status until governed review or promotion. |
| Product Owner acceptance | Confirmed future programme direction. The adopted OPR's FPR-7 and existing External Intelligence Airlock governance provide related foundations, but no complete External Source Vestibule admission workflow is implemented or authorized. |
| Lineage | Dedicated External Source Vestibule programme anchor. Related authoritative foundations remain distinct: the adopted OPR's FPR-7 external-source vestibule referenced by [Bug Eye — Data Room Source Continuity](../specified-unbuilt/bug-eye-data-room-source-continuity.md); [GO-INTAKE-FUTURE-01](GO-INTAKE-FUTURE-01.md); [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md); implemented evidence-class/provenance machinery in [Kernel Object Model](../current/kernel-object-model.md); [GO-RIVER-01](GO-RIVER-01.md); [GO-COMPOSER-01](GO-COMPOSER-01.md); and [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Controlled admission principle

Evidence coming from outside the governed project corpus should enter through a controlled vestibule rather than silently becoming project truth.

The vestibule preserves distinctions among:

- external information;
- project-authoritative evidence;
- contextual or reference material;
- unverified material;
- imported evidence awaiting adjudication.

These are governing distinctions, not a recovered closed status vocabulary. Exact admission and promotion states remain recovery-pending.

## Confirmed principles

- Provenance survives entry.
- Outside information does not automatically gain project authority.
- External evidence may support investigation without silently modifying the canonical project record.
- Conflicts between external and project evidence remain visible.
- Human review may be required before promotion into governed project evidence.

An external source's confident wording, apparent recency, or technical sophistication does not supply project authority. Current project evidence, authority, security, and human-adjudication rules continue to govern conclusions and consequential adoption.

## Relationship to GO-Native Intake

[GO-INTAKE-FUTURE-01](GO-INTAKE-FUTURE-01.md) remains distinct:

- GO-Native Intake governs project evidence entry generally.
- External Source Vestibule governs the status and controlled admission of evidence originating outside the governed project corpus.

The future programmes may compose, but neither absorbs the other.

## Relationship to External Intelligence Airlock

[External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md) remains a separate governed boundary:

- **Vestibule:** evidence and intake status, provenance, review, and controlled admission.
- **Airlock:** external intelligence, tool, request, response, and data-movement boundary.

An Airlock response may become vestibule material, but crossing the Airlock does not confer project authority or complete admission. Conversely, outside evidence may require vestibule handling even when no external AI or tool interaction occurred.

## Relationship to River

[GO-RIVER-01](GO-RIVER-01.md) may relate admitted external material to project evidence while preserving provisional status, provenance, confidence, and conflict. A relationship does not promote external information into project truth or erase disagreement.

## Relationship to Composer

[GO-COMPOSER-01](GO-COMPOSER-01.md) may explain source status, surface conflict, ask for review, or propose a governed next step. Composer must not silently admit, promote, or characterize outside material as authoritative merely because it is useful to an answer.

## Relationship to security and trust governance

[GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md), project isolation, security classification, and existing human-authority controls remain authoritative. External admission must preserve confidentiality, authorization, tenant and project boundaries, and any applicable Airlock constraints.

## Existing foundations and limits

The repository already contains useful but incomplete foundations:

- `Source.origin_type` includes an unwired `external_connector` value.
- `EvidenceItem.evidence_class` includes `externally_researched_evidence`.
- evidence records preserve validation status, security classification, provenance, and confidence.
- River relationships can keep supporting and contradicting evidence distinct.
- existing human-adjudication machinery prevents silent AI-to-authoritative promotion.

These foundations do not constitute an implemented External Source Vestibule. Do not infer an admission UI, promotion workflow, connector, or complete classification model from them.

## Programme boundary

This preservation record does not authorize external connectors, intake UI, admission or promotion workflow, classification changes, River changes, Composer changes, or security-policy changes.

## Recovery status

**RECOVERY PENDING:**

- original prompt;
- exact promotion and admission states;
- UI;
- external-source classification;
- historical prototypes;
- historical acceptance reports and implementation sequence.

Do not invent these. Later recovered source material may enrich this record without replacing its stable identity, current evidence-provenance machinery, Airlock distinction, or human-authority boundary.

## Exact prompt text

```text
Evidence coming from outside the governed project corpus should enter through a controlled vestibule rather than silently becoming project truth.
```

## Execution references

- Run: None
- Result: External Source Vestibule preserved as a distinct deferred programme; related evidence and Airlock foundations confirmed
- Commit: None
