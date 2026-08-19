# GO-TOOL-MAKING-01 — Tool Making — Governed Capability Composition and Internal Tool Generation

| Field | Value |
|---|---|
| Prompt ID | GO-TOOL-MAKING-01 |
| Title | Tool Making — Governed Capability Composition and Internal Tool Generation |
| Agent | Unassigned (governed capability-composition programme) |
| Status | APPROVED |
| Purpose | Preserve the adopted direction that GO should search and compose existing capabilities before proposing the smallest reusable, governed internal tool for a genuine capability gap. |
| Product Owner acceptance | Governing Tool Making direction approved. A small audited Application Capability Knowledge registry is implemented; Composer Tool Making and generated-tool lifecycle remain explicitly unbuilt and require separately governed implementation. |
| Lineage | Dedicated Tool Making programme anchor. Current implementation truth for the audited application-capability registry remains `services/capability_registry.py` and [Kernel Object Model](../current/kernel-object-model.md); [Composer Result Contract and Panel Zoning](../current/go-dna-01-composer-result-contract-and-panel-zoning.md) explicitly preserves Tool Making as specified-unbuilt and warns that the fixed Project Tools UI is not a tool registry. Related, not absorbed: [GO-COMPOSER-01](GO-COMPOSER-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), [GO-CAMEL-MM-01](GO-CAMEL-MM-01.md), [Project North Star advancement rule](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md), [North Bayview → Project North Star transition](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md), and the deferred [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md). |
| Superseded by | None |
| Absorbed into | None |

## Governing primitive rule

> **Before creating a new primitive, search for a useful composition of existing primitives. When a genuinely missing primitive is discovered, build it as a small lubricated package with stable interfaces so that it multiplies what the other primitives can do.**

The same discipline applies to internal tool creation.

## Tool Making is not feature sprawl

- Do not create a new tool merely because a task can be named.
- Search the live capability registry and existing primitives first.
- Prefer composition over duplication.
- Where a true gap exists, create the smallest reusable capability that solves the class of problem rather than one hard-coded example.
- New tools expose stable, inspectable interfaces.
- Generated tools remain bounded by project, authority, security, and provenance rules.
- A new internal tool becomes discoverable to future GO reasoning rather than remaining hidden one-off code.

## Capability registry

GO should maintain or consult a live capability registry representing what the application can currently do. It should help answer:

- Can this already be done?
- Which primitives can be composed?
- Which tools already exist?
- What scopes and modalities do they support?
- What authority or safety constraints apply?
- What is genuinely missing?

The current repository already contains two distinct authoritative capability mechanisms which must not be duplicated or conflated:

- `services/capability_registry.py` is the small, audited Application Capability Knowledge source used to answer ordinary questions about what ARCHIOSK can actually do.
- `services/environment_capabilities.py` governs capability availability by locked Project Operating Environment.

Neither is a general plugin framework or generated-tool registry. A future Tool Making implementation must first determine whether to extend or compose these existing mechanisms rather than creating a parallel registry.

The fixed “Project Tools” UI is a hard-coded set of existing administrative forms, not a data-driven tool registry or Tool Making foundation.

## Governed tool-making workflow

> **User/GO need → capability search → composition attempt → gap identification → bounded tool proposal → governed creation → testing → registry update → reuse**

Identifying a gap does not itself authorize tool creation. Consequential, novel, security-sensitive, or authority-expanding changes retain the appropriate Product Owner or human approval gate.

## Relationship to Composer

[GO-COMPOSER-01](GO-COMPOSER-01.md) remains distinct. Tool Making may be invoked through a governed Composer task: use an existing capability, compose existing capabilities, or propose a bounded new tool. Conversational convenience must not bypass implementation governance, approval, testing, or provenance.

## Relationship to Spin-Games

[GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) remains distinct. Spin-Games preferentially compose existing primitives. A Spin investigation may expose a genuine reusable capability gap and therefore create a Tool Making candidate, but every unusual finding must not create a new primitive.

## Relationship to Camel and multimodal machinery

[GO-CAMEL-MM-01](GO-CAMEL-MM-01.md) remains authoritative for canonical multimodal primitives and evidence contracts. Tool Making reuses those capabilities rather than creating duplicate document-, image-, table-, drawing-, revision-, or relationship-specific machinery.

## Relationship to Project North Star

[CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md) and [CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md) remain distinct. Project North Star may prove a newly composed internal tool, but the tool must generalize beyond the proving case and must never be tuned to known oracle answers or weaken blindness protections.

## Governance and safety boundary

A generated or newly composed tool preserves:

- project isolation;
- source provenance;
- authority boundaries;
- security controls;
- reversible and testable implementation where possible;
- human approval for consequential actions;
- existing application contracts.

Tool Making does not authorize arbitrary external-code installation, unauthorized-data access, hidden side effects, Airlock or security bypass, automatic constitutional-governance alteration, or self-expansion of authority.

## Small lubricated package principle

A **small lubricated package with stable interfaces** has narrow responsibility, is easy to invoke, interoperates with other primitives, avoids unnecessary coupling, exposes sufficient metadata and provenance for governance, and increases the usefulness of the wider capability set.

## Programme boundary

This preservation record does not authorize tool generation, capability-registry expansion, plugin machinery, Composer UI, runtime self-modification, or changes to any existing application capability. Current implemented registries and governance remain authoritative until separately changed.

## Recovery status

**RECOVERY PENDING:**

- original Tool Making prompt text;
- exact capability-registry schema for generated tools;
- Composer UI and interaction;
- approval workflow;
- internal-tool lifecycle;
- tool versioning and deprecation;
- examples and prototypes;
- historical acceptance reports;
- original historical programme ID if different.

Do not invent these. Later recovered source material may enrich this record without replacing current capability-registry truth, stable programme identity, or safety boundaries.

## Exact prompt text

```text
GO should be able to recognize when an existing set of capabilities can be composed into a useful internal tool, and where genuinely necessary, propose or generate a small bounded tool package that becomes part of the application's reusable capability set.

Before creating a new primitive, search for a useful composition of existing primitives. When a genuinely missing primitive is discovered, build it as a small lubricated package with stable interfaces so that it multiplies what the other primitives can do.
```

## Execution references

- Run: None for Tool Making; the existing capability registries were implemented under separate governed work
- Result: Tool Making preserved as approved programme direction; application capability registry confirmed implemented; generation workflow remains unbuilt
- Commit: None
