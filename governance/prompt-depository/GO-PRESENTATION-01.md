# GO-PRESENTATION-01 — Presentation Intelligence — PowerPoint as Project Intent and Coordination Surface

| Field | Value |
|---|---|
| Prompt ID | GO-PRESENTATION-01 |
| Title | Presentation Intelligence — PowerPoint as Project Intent and Coordination Surface |
| Agent | Unassigned (future presentation-intelligence programme) |
| Status | DEFERRED |
| Purpose | Preserve presentation decks as governed, bidirectional project-intent, evidence, and coordination surfaces rather than reducing the programme to file viewing or slide rendering. |
| Product Owner acceptance | Confirmed future programme direction. Existing governance records `CLAUDE-FUTURE-PRES-A1` as GO LATER, specified but unimplemented and not authorized. |
| Lineage | Prompt Depository anchor for the canonical [Presentation Intelligence / Design-Intent Workflow](../specified-unbuilt/presentation-intelligence.md). Related, not absorbed: [GO-CAMEL-MM-01](GO-CAMEL-MM-01.md), [GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md), [GO-HELIX-01](GO-HELIX-01.md), and the authenticated Project World lineage preserved by [CLAUDE-PROJECT-WORLD-NAMING-01](CLAUDE-PROJECT-WORLD-NAMING-01.md). Client/Proponent information boundaries remain governed separately by [Cross-Boundary Architecture](../specified-unbuilt/cross-boundary-architecture.md). |
| Superseded by | None |
| Absorbed into | None |

## Confirmed use cases

- Proponents use PowerPoint to present design intent to clients.
- Clients use PowerPoint to explain RFP intent and expectations to proponents.
- Presentation templates may contain required topics or requirements.
- Team members contribute discipline slides or content.
- Presentations evolve through repeated coordination and review until ready.
- A deck can become meaningful project evidence rather than a disposable visual artefact.

## ARCHIOSK direction

ARCHIOSK/GO should eventually work intelligently with presentation decks. Potential capabilities include opening and viewing decks in the application; understanding supported slide text, images, diagrams, tables, notes, and structure; comparing revisions; tracing content to requirements and project evidence; identifying missing presentation topics; detecting inconsistency with underlying evidence; supporting contribution and review; and helping assemble governed project or client presentation material.

These are programme directions, not authorization to implement them. The canonical specification keeps the capability format-independent: PPTX is an industry vehicle and future `Source` kind, not the architecture itself.

## Presentation as coordination instrument

A presentation deck can operate as a coordination template. A client or pursuit team may establish required sections, assign contributors to supply discipline content, and repeatedly review and refine the deck until complete. Presentation Intelligence therefore extends beyond rendering.

Repository governance identifies a real current capability gap: `Task` has no assignee field, so contributor or section ownership is not free reuse and remains unauthorized. A future presentation template may reuse governed `WorkProduct` sections, but this record creates no assignment or coauthoring machinery.

## Client and Proponent dual use

### Client-side

PowerPoint may communicate RFP intent, expectations, project requirements, and evaluation or briefing material.

### Proponent-side

PowerPoint may communicate interpretation, design intent, proposed solutions, coordination, progress, and compliance narrative.

Do not collapse these roles or leak evidence across governed Client/Proponent boundaries. A presentation is evidence of what someone communicated; it is not automatically proof that the communication is true, current, binding, or supported.

## Relationship to Camel and multimodal intelligence

[GO-CAMEL-MM-01](GO-CAMEL-MM-01.md) provides relevant multimodal primitives, including `Source`, `StructuralUnit`, `AddressableRegion`, `EvidenceItem`, relationships, claims, work products, and supersession. Presentation Intelligence remains a distinct programme intentionally created after Camel/MM1–MM9; do not absorb it silently into Camel.

## Relationship to Requirements, Spin, and Helix

[GO-SPIN-GAMES-01](GO-SPIN-GAMES-01.md) and [GO-HELIX-01](GO-HELIX-01.md) may eventually support questions such as whether a slide overclaims its evidence, omits a requirement, misses a propagated change, retains superseded intent, or fails to converge across discipline contributions. This record does not implement those reviews or games.

The canonical specification finds that presentation obligations and assertions can likely reuse existing `Relationship` and `Claim` machinery, while `Supersession` already models deck revision. These remain architecture findings, not implementation authority.

## Relationship to Project World and workspace

Future slide thumbnails, evidence navigation, comparison, and presentation projection may interact within the authenticated Project World/workspace. The existing document and multi-Display patterns are relevant precedents, but exact UI remains recovery-pending and is not invented here.

## Governance boundary

Presentation Intelligence preserves source provenance, project and tenant isolation, version and revision identity, authority distinctions, Client/Proponent information barriers, and human approval for issued or published presentations. GO must not silently rewrite, approve, issue, or publish presentation content as authoritative project communication.

PPTX remains untrusted input. Rendering and conversion architecture is unresolved, would introduce new dependency or subprocess risk, and requires a separately authorized dependency-fit and security review.

## Programme boundary

This record does not authorize PPTX dependencies, slide parsing, rendering, editing, coauthoring, comparison, workflow, UI, generation, export, or publication.

## Recovery status

**RECOVERY PENDING:**

- original PowerPoint or Presentation prompt text;
- exact historical programme ID;
- original template and coauthoring workflow wording;
- UI integration concept;
- comparison and review architecture;
- Client and Proponent presentation examples;
- PowerPoint opening and editing technical approach;
- historical prototypes or acceptance reports.

Do not invent these. Later recovered material may enrich this record while preserving the canonical specification, source wording, authority, and programme lineage.

## Exact prompt text

```text
PowerPoint is not merely a presentation file type in design-build work. It is a major project vehicle for assembling, coordinating, reviewing, and communicating design intent between proponents, clients, consultants, and project teams.

A presentation deck can operate as a coordination template.
```

## Execution references

- Run: `CLAUDE-FUTURE-PRES-A1` architecture investigation
- Result: `governance/specified-unbuilt/presentation-intelligence.md`; GO LATER / not authorized
- Commit: Exact historical commit lineage recovery-pending
