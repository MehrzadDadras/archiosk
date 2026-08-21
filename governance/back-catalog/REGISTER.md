# Governance Back-Catalog Register

Audit artifact. Index: [`README.md`](README.md). **Governs nothing.**

`GBC-nnnn` ids are **audit-only**. They are not governance ids and do not replace
`GOV-*`, `CIC-*`, or prompt ids. Source files were not renamed.

Fields captured per record: file, title, date-if-established, status, authority,
classification, domain, related contracts/records/tests, current-vs-historical,
drift notes, lineage notes, authority gap, verification gap, recommended action,
priority. The tables below show the decision-relevant subset; `UNKNOWN` means the
corpus does not establish it, never a guess.

**Classification counts (121 records):**
`CANONICAL CURRENT` 20 · `GOVERNANCE CANDIDATE` 20 · `HISTORICAL` 36 ·
`SPECIFIED / UNBUILT` 22 · `DEFERRED / RESERVED` 19 · `SUPPORTING` 4

**Overlay counts (not exclusive):** GOV-P 6 · GOV-D 3 · GOV-CN 0 · GOV-CR 0 ·
GOV-S 3 · GOV-I 4 · GOV-X 3 · DRIFT 5 clusters · ORPHANED 14 · UNCLEAR 3

---

## D01 · Product constitution & governance process

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0001 | `constitutional-invariants.md` | CANONICAL CURRENT | Ratified | 17 invariants. Authority scoped to the BEEHIVE domain model only — **not** infrastructure. No verification oracle for any invariant → `GOV-I` opportunity | P2 |
| GBC-0002 | `governance-of-governance/amendment-and-ratification.md` | CANONICAL CURRENT | Ratified | Defines `SUPERSEDED`/`ABSORBED`/precedence. Now points to `templates/` | P3 |
| GBC-0003 | `STATUS.md` | CANONICAL CURRENT | UNKNOWN (no status line) | The real authorization authority: 66-row table. **Itself carries no status marker** | P2 |
| GBC-0004 | `history-mapping.md` | SUPPORTING | Inventory only | Maps the sibling Explorer corpus, read-only | P3 |
| GBC-0005 | `spare-parts-yard.md` | SUPPORTING | — | Built-but-unassigned components. Lifecycle grammar (Active/Reserve/Prototype/Future/Scrap) is a **GOV-P candidate** | P2 |
| GBC-0006 | `deferred-reserved/reservations.md` | DEFERRED / RESERVED | UNKNOWN (no status line) | Named-not-designed gaps | P3 |

## D02 · Kernel / domain-object model

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0007 | `current/kernel-object-model.md` | CANONICAL CURRENT | Implemented | Ground truth is `services/case_workspace.py`; doc is the narrative | P3 |
| GBC-0008 | `specified-unbuilt/investigation-lifecycle-extensions.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** — authority only in `STATUS.md` | P2 |
| GBC-0009 | `specified-unbuilt/scenario-and-viability.md` | SPECIFIED / UNBUILT | NOT AUTHORIZED | | P3 |
| GBC-0010 | `specified-unbuilt/metamorphosis-and-dormancy.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P3 |
| GBC-0011 | `specified-unbuilt/per-item-attention-review-state.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P3 |
| GBC-0012 | `specified-unbuilt/perspective-and-contract-dna.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED.** Holds `ReferenceStandard` (Domain 2a) — cited as live by the Airlock record | P1 |
| GBC-0013 | `specified-unbuilt/conversation-thread-lifecycle.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P3 |

## D03 · Evidence & authority

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0014 | `specified-unbuilt/camel-multimodal-programme.md` | SPECIFIED / UNBUILT | NOT AUTHORIZED | **Status conflict:** MM1–MM9 are IMPLEMENTED per `STATUS.md`, yet the record still reads NOT AUTHORIZED. See LC-01 | P0 |
| GBC-0015 | `specified-unbuilt/bug-eye-data-room-source-continuity.md` | SPECIFIED / UNBUILT | NOT AUTHORIZED | | P3 |
| GBC-0016 | `specified-unbuilt/add-addendum-facility.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P3 |
| GBC-0017 | `prompt-depository/GO-RIVER-01.md` | GOVERNANCE CANDIDATE | APPROVED | River = the one relationship architecture. **GOV-P candidate** | P1 |
| GBC-0018 | `prompt-depository/GO-INTAKE-FUTURE-01.md` | DEFERRED / RESERVED | DEFERRED | | P3 |
| GBC-0019 | `prompt-depository/GO-CAMEL-MM-01.md` | GOVERNANCE CANDIDATE | APPROVED | Programme anchor for GBC-0014 | P2 |

## D04 · Airlock / external intelligence

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0020 | `specified-unbuilt/external-intelligence-airlock.md` | CANONICAL CURRENT | Specified + 3 missions AUTHORIZED | **Filing anomaly:** live authorizations, an execution hold and accepted doctrine departures all live in a `specified-unbuilt/` file. 617 lines, the corpus's densest record | P0 |
| GBC-0021 | `prompt-depository/CLAUDE-AIRLOCK-AUTH-01.md` | CANONICAL CURRENT | RUN | Mission 01 authorization | P3 |
| GBC-0022 | `prompt-depository/CLAUDE-AIRLOCK-M01A-AUTH.md` | CANONICAL CURRENT | RUN | Mission 01A route | P3 |
| GBC-0023 | `prompt-depository/CLAUDE-AIRLOCK-M02-AUTH.md` | CANONICAL CURRENT | RUN | Mission 02 bootstrap | P3 |
| GBC-0024 | `prompt-depository/CLAUDE-AIRLOCK-M02-HOLD.md` | CANONICAL CURRENT | RUN | Execution hold. **GOV-X candidate** (WG-01) | P1 |
| GBC-0025 | `prompt-depository/CLAUDE-PSD-FOUNDATION-01.md` | CANONICAL CURRENT | RUN | Synthetic identity; principle filed in `CLAUDE.md` | P2 |
| GBC-0026 | `prompt-depository/GO-EXTERNAL-VESTIBULE-01.md` | GOVERNANCE CANDIDATE | DEFERRED | Airlock=movement / Vestibule=admission. **GOV-P candidate** — load-bearing and cited by live missions while itself DEFERRED | P0 |

## D05 · Spin / Helix

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0027 | `current/contracts/CIC-SPIN-INTELLIGENCE.md` | CANONICAL CURRENT | CURRENT v1.0 | 8 invariants incl. "no Teacher/Oracle leakage" — no pass/fail condition. **GOV-I candidate** | P0 |
| GBC-0028 | `specified-unbuilt/spin-project-intelligence-preview.md` | SPECIFIED / UNBUILT | NOT AUTHORIZED | 684 lines; partly implemented, carries its own current-status clarification | P2 |
| GBC-0029 | `prompt-depository/GO-HELIX-01.md` | GOVERNANCE CANDIDATE | APPROVED | Helix = convergence question. **GOV-P candidate** | P1 |
| GBC-0030 | `prompt-depository/GO-HELIX-QA-01.md` | GOVERNANCE CANDIDATE | APPROVED | Bounded implementation authorized; recorded Commit: Pending | P2 |
| GBC-0031 | `prompt-depository/GEMINI-HELIX-QA-CLARIFICATION-01.md` | HISTORICAL | RUN | Verbatim external source, deliberately kept separate from adoption | P3 |
| GBC-0032 | `prompt-depository/GO-SPIN-GAMES-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P2 |
| GBC-0033 | `prompt-depository/CLAUDE-HOLODECK-WORLDS-SPIN-01.md` | HISTORICAL | **SUPERSEDED** | The corpus's only explicit supersession. See LC-02 | P3 |
| GBC-0034 | `prompt-depository/CLAUDE-PROJECT-WORLD-NAMING-01.md` | CANONICAL CURRENT | RUN | Terminology successor to GBC-0033 | P3 |

## D06 · Composer / GO conversation

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0035 | `current/contracts/CIC-COMPOSER.md` | CANONICAL CURRENT | CURRENT v1.0 | "One primary Composer" vs GBC-0038's "Composer is the primary toolbox" — DC-02 | P1 |
| GBC-0036 | `current/contracts/CIC-GO-CONVERSATION.md` | CANONICAL CURRENT | CURRENT v1.0 | "canonical model path" — DC-03 | P1 |
| GBC-0037 | `current/go-dna-01-composer-result-contract-and-panel-zoning.md` | CANONICAL CURRENT | UNKNOWN | Result contract + panel zoning | P2 |
| GBC-0038 | `prompt-depository/GO-COMPOSER-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P2 |
| GBC-0039–42 | `current/ca1*.md` (4 records) | HISTORICAL | UNKNOWN (no status line) | Stage records: apprenticeship, context completion, persistent context, professional judgment | P3 |
| GBC-0043 | `prompt-depository/GO-VOICE-01.md` | GOVERNANCE CANDIDATE | APPROVED | Level 0–3 shipped; 4/5 unauthorized | P2 |
| GBC-0044 | `specified-unbuilt/voice-conversational-presence.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** despite partial implementation | P1 |

## D07 · Developer Mode / CCN

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0045 | `current/contracts/CIC-DEVELOPER-MODE.md` | CANONICAL CURRENT | CURRENT v1.0 | "selection is context, not authorization" — **DC-01** | P0 |
| GBC-0046 | `current/contracts/CIC-CCN.md` | CANONICAL CURRENT | CURRENT v1.0 | "selection never authorizes mutation" — **DC-01** | P0 |
| GBC-0047 | `current/developer-mode-ccn.md` | CANONICAL CURRENT | UNKNOWN | Named governance source for both contracts above | P1 |
| GBC-0048 | `prompt-depository/GO-NAVIGATION-CONTEXT-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P2 |

## D08 · Page / panel / template

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0049 | `current/contracts/CIC-PAGE-TEMPLATE.md` | CANONICAL CURRENT | CURRENT v1.0 | | P2 |
| GBC-0050 | `current/contracts/CIC-PANEL.md` | CANONICAL CURRENT | CURRENT v1.0 | "Menus are the canonical machinery/restoration path"; "closing never deletes data". **GOV-P candidate** — DC-04 | P1 |
| GBC-0051 | `current/page-surface-template-inventory.md` | CANONICAL CURRENT | current inventory | Progressive template principle embedded in an inventory | P2 |
| GBC-0052 | `current/panel-template-system.md` | CANONICAL CURRENT | UNKNOWN | | P2 |
| GBC-0053 | `specified-unbuilt/peripheral-activity-dots.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P3 |

## D09 · Project lifecycle & publication

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0054 | `specified-unbuilt/cross-boundary-architecture.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED**; partially implemented via `CLAUDE-RFP-BOUNDARY-01` | P1 |
| GBC-0055 | `prompt-depository/GO-RFP-PUBLICATION-BARRIER-01.md` | GOVERNANCE CANDIDATE | APPROVED | No-leak tested | P2 |
| GBC-0056 | `prompt-depository/GO-NEUTRAL-ENTRY-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P2 |
| GBC-0057 | `prompt-depository/GO-PREAWARD-ADJUDICATION-01.md` | DEFERRED / RESERVED | DEFERRED | | P3 |
| GBC-0058 | `specified-unbuilt/tenancy-and-project-authorization.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED** | P2 |
| GBC-0059 | `prompt-depository/GO-PROJECT-OBJECT-REGISTRY-01.md` | DEFERRED / RESERVED | DEFERRED | | P3 |

## D10 · Security / tenancy / trust

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0060 | `specified-unbuilt/organizational-security-department.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED.** Holds `ACTION_EXTERNAL_AI_REQUEST`, the Airlock's real anchor | P1 |
| GBC-0061 | `specified-unbuilt/security-policy.md` | SPECIFIED / UNBUILT | no auth marker | **ORPHANED**, 11 lines | P3 |
| GBC-0062 | `specified-unbuilt/trust-exchange-and-security-commissioning.md` | SPECIFIED / UNBUILT | NOT AUTHORIZED | | P3 |
| GBC-0063 | `prompt-depository/GO-TRUST-SECURITY-01.md` | DEFERRED / RESERVED | DEFERRED | | P3 |
| GBC-0064 | `CLAUDE.md` *(root)* | CANONICAL CURRENT | — | Operating/safety rules incl. synthetic identity, credentials, scope boundary | P2 |

## D11 · Self-project commissioning *(entirely historical)*

| GBC | Files | Class | Status | Notes | Pri |
|---|---|---|---|---|---|
| GBC-0065–77 | `current/comm-a1`, `comm-i1`…`comm-i6`, `comm-i3a/b`, `comm-i4a`, `comm-i5a`, `continue-01` (13) | HISTORICAL | mostly no status line | Stage records of a completed commissioning programme. 11 of 13 carry no status marker; authority lives in `STATUS.md` | P3 |
| GBC-0078 | `prompt-depository/GO-SELF-COMMISSIONING-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P3 |

## D12 · Test / oracle

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0079 | `prompt-depository/CODEX-PSD-TEACHER-ORACLE-02.md` | CANONICAL CURRENT | UNKNOWN | **Protected TEST/ORACLE governance filed in the prompt depository.** Frozen Code basis, retrieved-package hash, explicit never-ingest rule. Strongest **GOV-I candidate**; see OG-01 | P0 |
| GBC-0080 | `prompt-depository/CODEX-PSD-SMA-PLOT-01.md` | HISTORICAL | UNKNOWN | PSD smoke plot | P2 |
| GBC-0081 | `TEST_LANES.md` *(root)* | SUPPORTING | — | Lane selection, not governance | P3 |
| GBC-0082 | `prompt-depository/GO-GEMINI-DOC-REVIEW-01.md` | GOVERNANCE CANDIDATE | APPROVED | | P3 |

## D13 · Prompt & process governance

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0083 | `prompt-depository/PROMPT_REGISTER.md` | CANONICAL CURRENT | governed register | 48 records; 7 preservation rules; closed status vocabulary | P3 |
| GBC-0084 | `current/canonical-implementation-order.md` | CANONICAL CURRENT | current format v1.0 | No `APPLICABLE GOVERNANCE` line yet — see MQ-P1-05 | P1 |
| GBC-0085 | `current/contracts/README.md` | CANONICAL CURRENT | registry v1.0 | 9 contracts, all v1.0, all CURRENT, none superseded | P3 |
| GBC-0086 | `prompt-depository/CODEX-PROMPT-DEPOSITORY-01A-1.md` | HISTORICAL | RUN | | P3 |
| GBC-0087 | `prompt-depository/CODEX-PROMPT-DEPOSITORY-01B-1.md` | HISTORICAL | RUN | | P3 |

## D14 · Deployment / repo safety

| GBC | File | Class | Status | Notes / gaps | Pri |
|---|---|---|---|---|---|
| GBC-0088 | `current/contracts/CIC-DEPLOYMENT.md` | CANONICAL CURRENT | CURRENT v1.0 | | P3 |
| GBC-0089 | `current/contracts/CIC-REPO-SAFETY.md` | CANONICAL CURRENT | CURRENT v1.0 | Applies to every order | P3 |
| GBC-0090 | `MANIFEST.md` *(root)* | SUPPORTING | — | File layout; explicitly excludes `governance/*.md` | P3 |
| GBC-0091 | `UI_REFERENCE_MAP.md` *(root)* | SUPPORTING | — | `data-ui-ref` index | P3 |

## D15 · Future programmes *(deferred concept anchors)*

| GBC | Files | Class | Status | Notes | Pri |
|---|---|---|---|---|---|
| GBC-0092–0109 | `GO-ADAPTIVE-ATTENTION-01`, `GO-DT1-01`, `GO-EXECUTION-01`, `GO-EXPERIENCE-CORPUS-01`, `GO-FIRST-RUN-01`, `GO-LAMS-01`, `GO-LEADERSHIP-01`, `GO-LIVING-KNOWLEDGE-01`, `GO-MERGED-HISTORY-01`, `GO-PM-SITUATIONAL-GAUGE-01`, `GO-PRESENTATION-01`, `GO-PROJECT-MEMORY-01`, `GO-RISK-MONTE-CARLO-01`, `GO-UNIVERSAL-VENUE-01`, +4 | DEFERRED / RESERVED | DEFERRED | 18 records. Concept preservation; none authorized. **Leave alone** | P3 |
| GBC-0110–0115 | `GO-ADAPTIVE-WORKBENCH-01`, `GO-SURFACE-TRUST-01`, `GO-TOOL-MAKING-01`, `GO-EXPERIENCE-CORPUS-01`, `CODEX-NORTH-BAYVIEW…`, `CODEX-PROJECT-NORTH-STAR…` | GOVERNANCE CANDIDATE | APPROVED | Partly implemented programmes | P2 |
| GBC-0116–0121 | `specified-unbuilt/` remainder: `adaptive-attention…`, `navigation-context-operational-map`, `presentation-intelligence`, `reviewer-governed-pattern-suggestions`, `go-learning-01…`, `current/meta-t01*`, `current/wb1`, `current/pilot-*` | HISTORICAL / SPECIFIED | mixed | Stage and concept records | P3 |

---

## UNCLEAR — needs Product Owner review

| GBC | Record | Why unclear |
|---|---|---|
| GBC-0014 | `camel-multimodal-programme.md` | Marked NOT AUTHORIZED while `STATUS.md` records MM1–MM9 IMPLEMENTED. Which governs? |
| GBC-0020 | `external-intelligence-airlock.md` | A `specified-unbuilt/` file holding three live authorizations. Correct filing is a Product Owner call, not an audit call |
| GBC-0079 | `CODEX-PSD-TEACHER-ORACLE-02.md` | Protected oracle material inside the general prompt depository. Whether that placement is intentional is unknown |
