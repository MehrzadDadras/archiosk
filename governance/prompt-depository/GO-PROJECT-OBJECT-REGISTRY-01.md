# GO-PROJECT-OBJECT-REGISTRY-01 — Project Object Registry — Stable Human-Readable Project Object Identity

| Field | Value |
|---|---|
| Prompt ID | GO-PROJECT-OBJECT-REGISTRY-01 |
| Title | Project Object Registry — Stable Human-Readable Project Object Identity |
| Agent | Unassigned (future project-object identity programme) |
| Status | DEFERRED |
| Purpose | Preserve durable, readable identity for consequential project objects without replacing canonical machine identity or imposing one universal numbering scheme across object families. |
| Product Owner acceptance | Confirmed future programme direction. Current commissioning and canonical-root governance classify Project Object Registry/Numbering as a usability residual that remains unauthorized and is not required before commissioning. |
| Lineage | Dedicated Project Object Registry/Readable Numbering programme anchor. Canonical implemented object ownership remains governed by [Current Implemented Kernel Object Model](../current/kernel-object-model.md); deferral is established by [Self-Project Commissioning Readiness](../current/comm-a1-self-project-commissioning-readiness.md#k-registrynumbering-prerequisite-decision) and `governance/STATUS.md`. Related, not absorbed: [GO-COMPOSER-01](GO-COMPOSER-01.md), [GO-RIVER-01](GO-RIVER-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), and [GO-EXECUTION-01](GO-EXECUTION-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Confirmed direction

Consequential project objects should have durable, readable identity so humans and GO can refer to them reliably across conversations, reports, findings, relationships, and history.

Object families may include:

- requirements;
- findings;
- decisions;
- tasks;
- RFIs;
- evidence objects;
- Spins;
- other governed records.

This list identifies relevant families, not a closed ontology or authorization to create new canonical object types.

## Confirmed principles

- Machine identity and human-readable identity may coexist.
- IDs remain stable.
- Numbering aids reference; it must not imply a false hierarchy, authority, priority, or maturity.
- Renaming or changing a display label must not destroy canonical identity.
- Links, provenance, relationships, and history must survive display-name or numbering changes.
- Different canonical object families may retain different appropriate identity conventions.
- A display ordinal is not automatically a durable project-object identifier.

## Current repository boundary

The implemented kernel already gives governed objects durable machine identities and preserves family-specific identity where appropriate. For example, a Requirement retains its source's own numbering in `original_requirement_identifier`; Spin runs and findings retain their canonical object identity and history even where the UI projects readable labels such as `F-00N`.

Those existing conventions remain authoritative. This programme must audit whether a displayed label is stable or merely derived before treating it as a durable reference. It must not reinterpret creation order, table position, branch numbering, or another presentation ordinal as permanent identity.

Do not invent one universal numbering scheme where canonical object families already have suitable IDs. Any future registry must compose with the existing object model rather than create a parallel source of truth.

## Programme boundary

Current governance explicitly classifies Project Object Registry/Numbering as a deferred usability residual, not a prerequisite for commissioning and not an authorized implementation. This record does not authorize registry architecture, numbering syntax, schema changes, identifier migration, UI, or runtime behaviour.

## Recovery status

**RECOVERY PENDING:**

- original prompt;
- numbering syntax;
- registry architecture;
- UI;
- migration rules.

Do not invent these. Later recovered source material may enrich this record without replacing canonical object identities, family-specific conventions, or historical lineage.

## Exact prompt text

```text
Consequential project objects should have durable, readable identity so humans and GO can refer to them reliably across conversations, reports, findings, relationships, and history.
```

## Execution references

- Run: None
- Result: Programme preserved as a deferred usability residual; no implementation performed
- Commit: None
