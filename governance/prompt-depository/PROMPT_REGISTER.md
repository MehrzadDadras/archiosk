# ARCHIOSK / GO Prompt Register

**Status:** Governed prospective register. This depository records future prompts and their lineage; it does not retroactively import historical prompts.

## Authority and scope

This directory is the authoritative repository location for preserved ARCHIOSK/GO prompt records. A record becomes durable project truth only when committed and pushed in accordance with `CLAUDE.md`.

Prompt records preserve Product Owner intent and execution provenance. They do not replace constitutional invariants, programme authorization in `governance/STATUS.md`, tested application behavior, or commit history.

Prompt history is not a set of equally current authorities. Resolve conflicts, corrections, supersession, absorption, and partial scope under the repository's [ratified governance-precedence rule](../governance-of-governance/amendment-and-ratification.md#precedence-among-ratified-records).

## Preservation rules

1. A Prompt ID is permanent. Never renumber, reuse, or silently change it.
2. Preserve exact prompt text verbatim. Corrections or later direction require a new prompt record with explicit lineage.
3. Obsolete prompts remain present. Mark them `SUPERSEDED` or `ABSORBED` and identify the successor; do not delete them.
4. Prompt text and execution results remain separate. A prompt record may cite runs, results, and commits, but must not embed result content as part of the exact prompt text.
5. Use only these statuses: `DRAFT`, `APPROVED`, `RUN`, `DEFERRED`, `SUPERSEDED`, `ABSORBED`.
6. Store each future prompt as one Markdown file directly in this directory, named from its stable Prompt ID. Do not derive identity from a mutable title.
7. Add every prompt record to the register table below. Stable fields and one-record-per-file storage are the interface for a future UI; the Markdown files remain the source of record.

## Register

No broad historical prompt migration has been performed.

| Prompt ID | Title | Agent | Status | Product Owner acceptance | Record |
|---|---|---|---|---|---|
| CLAUDE-AIRLOCK-AUTH-01 | Record Product Owner Authorization for Mission 01 | Claude | RUN | Explicit Product Owner authorization, 2026-08-19; bounded External Intelligence Airlock Mission 01 only, recorded and pushed as `7318564` | [Record](CLAUDE-AIRLOCK-AUTH-01.md) |
| CLAUDE-AIRLOCK-M01A-AUTH | Authorize One Deterministic e-Laws Content Route | Claude | RUN | Explicit Product Owner authorization, 2026-08-19; bounded Mission 01A delivery-route continuation only, route fixed in trusted code and never model-selected | [Record](CLAUDE-AIRLOCK-M01A-AUTH.md) |
| CLAUDE-AIRLOCK-M02-AUTH | Authorize Definition Bootstrap Mission | Claude | RUN | Explicit Product Owner authorization, 2026-08-19; bounded Mission 02 vocabulary/definition bootstrap only, no substantive provision and no determination | [Record](CLAUDE-AIRLOCK-M02-AUTH.md) |
| CLAUDE-AIRLOCK-M02-HOLD | Record Preconditions Before Mission 02 Execution | Claude | RUN | Explicit Product Owner record, 2026-08-19; accepts Mission 02's two doctrine departures and holds its execution pending Mission 01A commit/sync and project-context resolution | [Record](CLAUDE-AIRLOCK-M02-HOLD.md) |
| CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01 | Record Product Owner Authorization for Composer Trusted Web Research (Airlock Mission 03, Slice 1) | Claude | RUN | Approved as written, 2026-08-24, framing accepted verbatim; Slice 1 implemented as CLAUDE-AIRLOCK-WEB-RESEARCH-01 | [Record](CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01.md) |
| CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01 | Scientific-Artistic Surface Recomposition for ARCHIOSK/GO | Claude | RUN | Accepted; bounded first visual slice subsequently implemented | [Record](CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01.md) |
| CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01A | Proceed — Bauhaus/Constructivist First Slice | Claude | RUN | Accepted; authorized bounded first implementation slice and retained Product Owner visual-acceptance gate | [Record](CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01A.md) |
| CLAUDE-HOLODECK-WORLDS-SPIN-01 | Reconstitute the Holodeck World Model and Advance Spin Through Worlds | Claude | SUPERSEDED | Accepted historically; only its PM-facing use of “Holodeck” was later corrected | [Record](CLAUDE-HOLODECK-WORLDS-SPIN-01.md) |
| CLAUDE-PROJECT-WORLD-NAMING-01 | Project World Naming Correction — Preserve Holodeck for GO-LEARNING-01 | Claude | RUN | Accepted and used as the governing terminology correction | [Record](CLAUDE-PROJECT-WORLD-NAMING-01.md) |
| CLAUDE-PSD-FOUNDATION-01 | Establish Synthetic Project Identity and Release Path | Claude | RUN | Explicit Product Owner security/liability decision, 2026-08-19; adopts Project Smoke Detector (PSD) as the synthetic test-project identity and restates Mission 02 Condition B against it | [Record](CLAUDE-PSD-FOUNDATION-01.md) |
| CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01 | North Bayview → Project North Star Transition | Codex | RUN | Explicit Product Owner direction; executed live 2026-08-23 after the required Spin review — project `547e8455-…` renamed to Project North Star with UUID, 55 Sources, Spin history and governance history preserved | [Record](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md) |
| CODEX-PROMPT-DEPOSITORY-01A-1 | Locate the Authoritative Prompt Depository Home | Codex | RUN | Accepted by subsequent Product Owner continuation | [Record](CODEX-PROMPT-DEPOSITORY-01A-1.md) |
| CODEX-PROMPT-DEPOSITORY-01B-1 | Verify the Prompt Depository Contract | Codex | RUN | Accepted by CODEX-PROMPT-DEPOSITORY-01B-2 | [Record](CODEX-PROMPT-DEPOSITORY-01B-1.md) |
| CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01 | Project North Star — Spin-Led Advancement Rule | Codex | APPROVED | Explicit Product Owner direction | [Record](CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01.md) |
| CODEX-PSD-SMA-PLOT-01 | Preserve the Blind Proponent Smoke-Investigation Test Plot | Codex | APPROVED | Explicit Product Owner test/oracle governance; preservation only, never Proponent-visible project evidence | [Record](CODEX-PSD-SMA-PLOT-01.md) |
| CODEX-PSD-TEACHER-ORACLE-02 | PSD Smoke / Horizontal Compartmentation Teacher Key | Codex | APPROVED | Protected Teacher/Oracle extension of the PSD blind proving plot; never project evidence | [Record](CODEX-PSD-TEACHER-ORACLE-02.md) |
| GO-ADAPTIVE-ATTENTION-01 | Adaptive Attention — Dynamic System Hierarchy / Gear-Attention Architecture | Unassigned | DEFERRED | Confirmed future programme direction; implementation remains unauthorized | [Record](GO-ADAPTIVE-ATTENTION-01.md) |
| GO-ADAPTIVE-WORKBENCH-01 | Adaptive Workbench — Context-Responsive Project Workspace | Unassigned | APPROVED | Product Owner-authorized distinct programme; one bounded Workbench increment is implemented while the larger grammar remains unbuilt | [Record](GO-ADAPTIVE-WORKBENCH-01.md) |
| GO-CAMEL-MM-01 | Camel / MM1–MM9 — Multimodal Project Intelligence Programme | Unassigned | APPROVED | Product Owner-adopted and substantially implemented programme | [Record](GO-CAMEL-MM-01.md) |
| GO-COMPOSER-01 | Composer — Governed Findings, Questions, and Next-Step Interaction | Unassigned | APPROVED | Product Owner-adopted and implemented interaction model | [Record](GO-COMPOSER-01.md) |
| GO-DT1-01 | DT1 — Terminal Eye / Engineering Observatory | Unassigned | DEFERRED | Confirmed Product Owner programme direction; implementation remains GO LATER and unauthorized | [Record](GO-DT1-01.md) |
| GO-EXECUTION-01 | Instrument Rail — Delegated Execution Continuity | Unassigned | DEFERRED | Confirmed future programme direction; durable delegated execution continuity remains unimplemented | [Record](GO-EXECUTION-01.md) |
| GO-EXTERNAL-VESTIBULE-01 | External Source Vestibule — Governed Entry of Outside Evidence | Unassigned | DEFERRED | Confirmed future programme direction; evidence admission remains distinct from the External Intelligence Airlock and unimplemented | [Record](GO-EXTERNAL-VESTIBULE-01.md) |
| GO-EXPERIENCE-CORPUS-01 | Experience Corpus — Learn How to Investigate Without Learning What to Believe | Unassigned | DEFERRED | Governing concept confirmed; Experience Corpus in all forms remains unauthorized | [Record](GO-EXPERIENCE-CORPUS-01.md) |
| GO-FIRST-RUN-01 | First-Run Experience — New-User Preview and Product Orientation | Unassigned | DEFERRED | Confirmed future programme direction; First-Run/New-User Preview remains a useful but non-required and unauthorized aid | [Record](GO-FIRST-RUN-01.md) |
| GO-HELIX-01 | Helix — Progressive Project Convergence | Unassigned | APPROVED | Product Owner-adopted governing concept corroborated by preserved programme evidence | [Record](GO-HELIX-01.md) |
| GEMINI-HELIX-QA-CLARIFICATION-01 | Progressive Helix QA Measurement Framework for ARCHIOSK/GO | Gemini | RUN | Complete source preserved verbatim; adoption governed separately by GO-HELIX-QA-01 | [Record](GEMINI-HELIX-QA-CLARIFICATION-01.md) |
| GO-HELIX-QA-01 | Progressive Helix QA — Evidence-Based Measurement of Project Convergence | Codex / GO | APPROVED | Explicit Product Owner refinement and bounded implementation authorization | [Record](GO-HELIX-QA-01.md) |
| GO-GEMINI-DOC-REVIEW-01 | Gemini C6/C8 — Document-Review Absorption into Spin-Games | Unassigned | APPROVED | Product Owner-adopted absorption direction corroborated by preserved programme evidence | [Record](GO-GEMINI-DOC-REVIEW-01.md) |
| GO-INTAKE-FUTURE-01 | GO-Native Document Intake — Governed Project Evidence Entry | Unassigned | DEFERRED | Confirmed future programme direction; governed ingestion/Reconcile exist but native intake remains unimplemented | [Record](GO-INTAKE-FUTURE-01.md) |
| GO-LAMS-01 | LAMS — Layered Architectural Memory System | Unassigned | DEFERRED | Confirmed Product Owner programme direction; implementation not authorized | [Record](GO-LAMS-01.md) |
| GO-LEADERSHIP-01 | Distributed Leadership — Recursive Delegation River | Unassigned | DEFERRED | Confirmed future programme direction; delegation architecture remains unimplemented | [Record](GO-LEADERSHIP-01.md) |
| GO-LIVING-KNOWLEDGE-01 | Living Body of Knowledge — Contextual Knowledge Navigation | Unassigned | DEFERRED | Confirmed future programme direction; project-knowledge navigation remains unimplemented | [Record](GO-LIVING-KNOWLEDGE-01.md) |
| GO-MERGED-HISTORY-01 | Merged History — Project Timeline Across Evidence, Decisions, and Change | Unassigned | DEFERRED | Confirmed future programme direction; decentralized history remains authoritative and a merged event/history view remains unauthorized | [Record](GO-MERGED-HISTORY-01.md) |
| GO-NAVIGATION-CONTEXT-01 | Navigation Context — Project-Aware Orientation and Return Paths | Unassigned | APPROVED | Product Owner-approved distinct programme; canonical operational map and bounded Composer return-pointer pilot exist while wider navigation work remains governed | [Record](GO-NAVIGATION-CONTEXT-01.md) |
| GO-NEUTRAL-ENTRY-01 | Neutral Entry — Unified Project Gateway and Operating-Environment Lock | Unassigned | APPROVED | Product Owner-adopted and implemented neutral-entry model; current gateway evolution preserves the governed project-context lock | [Record](GO-NEUTRAL-ENTRY-01.md) |
| GO-PM-SITUATIONAL-GAUGE-01 | PM Situational Gauge — Spin Room Attention and Project State Panel | Unassigned | DEFERRED | Confirmed future programme direction; gauge and custom-focus state remain unimplemented | [Record](GO-PM-SITUATIONAL-GAUGE-01.md) |
| GO-PREAWARD-ADJUDICATION-01 | Pre-Award Design-Build Pursuit and Design-Development Adjudication Engine | Unassigned | APPROVED | Product Owner-adopted programme supported by bounded Requirements, QAC, investigation, evidence, and RFI lineage | [Record](GO-PREAWARD-ADJUDICATION-01.md) |
| GO-PRESENTATION-01 | Presentation Intelligence — PowerPoint as Project Intent and Coordination Surface | Unassigned | DEFERRED | Confirmed future programme direction; Presentation Intelligence remains GO LATER and unauthorized | [Record](GO-PRESENTATION-01.md) |
| GO-PROJECT-MEMORY-01 | Project Memory as Narrative — Organizational Episode Memory | Unassigned | DEFERRED | Confirmed future programme direction; narrative project memory remains unimplemented | [Record](GO-PROJECT-MEMORY-01.md) |
| GO-PROJECT-OBJECT-REGISTRY-01 | Project Object Registry — Stable Human-Readable Project Object Identity | Unassigned | DEFERRED | Confirmed future programme direction; Registry/Numbering remains an unauthorized usability residual and is not required before commissioning | [Record](GO-PROJECT-OBJECT-REGISTRY-01.md) |
| GO-RIVER-01 | River — Evidence Relationship and Consequence Flow | Unassigned | APPROVED | Product Owner-adopted and implemented relationship model | [Record](GO-RIVER-01.md) |
| GO-RFP-PUBLICATION-BARRIER-01 | RFP Publication Barrier — Client Authoring to Blind Builder Intake | Unassigned | APPROVED | Product Owner-adopted and bounded implementation no-leak tested under `CLAUDE-RFP-BOUNDARY-01` | [Record](GO-RFP-PUBLICATION-BARRIER-01.md) |
| GO-RISK-MONTE-CARLO-01 | Risk Intelligence — Risk Registers and Monte Carlo Contingency | Unassigned | DEFERRED | Confirmed future programme direction; bounded risk-register support exists while the canonical Risk schema and Monte Carlo engine remain unauthorized | [Record](GO-RISK-MONTE-CARLO-01.md) |
| GO-SELF-COMMISSIONING-01 | Self-Project Commissioning — OPR, Verification, Deficiency, Recommissioning | Unassigned | APPROVED | Product Owner-adopted and substantially exercised; final independent commissioning remains outstanding | [Record](GO-SELF-COMMISSIONING-01.md) |
| GO-SPIN-GAMES-01 | Prompt-Spin-Games — Composable Investigative Strategies | Unassigned | APPROVED | Product Owner-adopted governing concept corroborated by preserved programme evidence | [Record](GO-SPIN-GAMES-01.md) |
| GO-SURFACE-TRUST-01 | Surface Trust — Apple Factor / Premium Professional Instrument | Unassigned | APPROVED | Broad Surface Trust principle and corrected Deep Ocean baseline accepted; wider implementation remains incomplete | [Record](GO-SURFACE-TRUST-01.md) |
| GO-TOOL-MAKING-01 | Tool Making — Governed Capability Composition and Internal Tool Generation | Unassigned | APPROVED | Governing Tool Making direction adopted; audited capability registry exists while generated-tool lifecycle remains unbuilt | [Record](GO-TOOL-MAKING-01.md) |
| GO-TRUST-SECURITY-01 | Trust Exchange — Security Policy, Client Requirements, and Recommissioning | Unassigned | DEFERRED | Confirmed future programme direction; Trust Exchange remains unauthorized | [Record](GO-TRUST-SECURITY-01.md) |
| GO-UNIVERSAL-VENUE-01 | Universal Venue — Director Workspace and Broader Governed World Platform | Unassigned | DEFERRED | Confirmed future architectural possibility; professional project use remains primary and the broader Venue/Director programme remains unauthorized | [Record](GO-UNIVERSAL-VENUE-01.md) |
| GO-VOICE-01 | Voice — Shoulder-Counsellor and Ushering Agent Programme | Unassigned | APPROVED | Product Owner-adopted Voice/Ushering direction with bounded implementation | [Record](GO-VOICE-01.md) |

## Prompt record format

Use this exact field set for future records. Use `None` where an optional relationship or reference does not exist; do not omit fields.

````markdown
# <Prompt ID> — <Title>

| Field | Value |
|---|---|
| Prompt ID | <stable identifier> |
| Title | <short descriptive title> |
| Agent | <intended or executing agent> |
| Status | DRAFT / APPROVED / RUN / DEFERRED / SUPERSEDED / ABSORBED |
| Purpose | <bounded intended outcome> |
| Product Owner acceptance | <acceptance state, date, and/or authoritative reference; or None> |
| Lineage | <predecessor, addendum, continuation, or related Prompt IDs; or None> |
| Superseded by | <Prompt ID; or None> |
| Absorbed into | <Prompt ID; or None> |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
<exact prompt text>
```

## Execution references

- Run: <reference or None>
- Result: <reference or None>
- Commit: <hash or None>
````

The outer example fence above is illustrative. In an actual record, use a fenced `text` block for the exact prompt and keep execution references outside that block.
