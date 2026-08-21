# Governance Back-Catalog — Audit Index

Status: audit artifact, version 1.0 · Recorded `CLAUDE-GOVERNANCE-BACKCATALOG-ORGANIZE-01`, 2026-08-20
Authority: **none.** This is a map, not a rule.

**This directory governs nothing.** It inventories, classifies, and recommends. No
existing record was moved, renamed, rewritten, re-dated, re-scoped, or marked
superseded by this audit. Where evidence was absent, the field says `UNKNOWN`
rather than a plausible guess.

## Artifacts

| File | Contains |
|---|---|
| [`REGISTER.md`](REGISTER.md) | Every mapped record, `GBC-0001`–`GBC-0121`, with classification, domain, status and gaps |
| [`DRIFT-AND-LINEAGE.md`](DRIFT-AND-LINEAGE.md) | Drift clusters, supersession chains, waiver gaps, oracle gaps |
| [`MIGRATION-QUEUE.md`](MIGRATION-QUEUE.md) | P0–P3 candidates and the recommended first filings |

Four artifacts, not five: drift and lineage are the same question asked across
space and across time, so they share a file.

---

## Corpus inspected

| Layer | Location | Files | Lines |
|---|---|---:|---:|
| Constitution | `governance/constitutional-invariants.md` | 1 | 29 |
| Governance-of-governance | `governance/governance-of-governance/` | 1 | 33 |
| Programme status | `governance/STATUS.md` | 1 | 153 |
| Current records | `governance/current/` | 27 | ~8,000 |
| Standing contracts | `governance/current/contracts/` | 10 | 208 |
| Templates *(the new family — not back-catalog)* | `governance/templates/` | 8 | 1,054 |
| Specified-unbuilt | `governance/specified-unbuilt/` | 23 | ~4,400 |
| Deferred/reserved | `governance/deferred-reserved/` | 1 | 17 |
| Prompt depository | `governance/prompt-depository/` | 51 | ~5,600 |
| Corpus index / parked | `history-mapping.md`, `spare-parts-yard.md` | 2 | 247 |
| Root governance-relevant | `CLAUDE.md`, `MANIFEST.md`, `UI_REFERENCE_MAP.md`, `TEST_LANES.md` | 4 | — |

**125 files / 21,128 lines under `governance/`**, plus 4 root files.
**121 records mapped** (the 8 template files are the new family itself, excluded).

No ADR directory exists in this repository. The ADR series referenced by
`history-mapping.md` belongs to the sibling `archiosk-explorer` repo and is
cross-referenced read-only, never duplicated here.

---

## Authority hierarchy — as it actually is

Derived from the corpus, not imposed on it.

```
  CONSTITUTIONAL INVARIANTS  (17, ratified)
  governance/constitutional-invariants.md
  amendable only via governance-of-governance/amendment-and-ratification.md
                         │
                         │  scoped to the BEEHIVE domain-object model only
                         ▼
  PROGRAMME AUTHORIZATION          ◄── governance/STATUS.md
  what is AUTHORIZED / NOT AUTHORIZED to build          (66-row table)
                         │
                         ▼
  CANONICAL GOV-* RECORDS  ····································· (0 filed)
  what must remain true, cross-cutting          ← the gap this audit maps
                         │
                         ▼
  CIC STANDING CONTRACTS  (9, v1.0)      ◄── current/contracts/README.md
  operational implementation/test contracts
                         │
                         ▼
  CANONICAL IMPLEMENTATION ORDER  ◄── current/canonical-implementation-order.md
  SITUATION · MISSION · EXECUTION · SUPPORT · COMMAND & CONTROL
                         │
                         ▼
  TASK ORDERS / PROMPTS  (50 records)    ◄── prompt-depository/PROMPT_REGISTER.md
  DRAFT · APPROVED · RUN · DEFERRED · SUPERSEDED · ABSORBED
                         │
                         ▼
  TESTS / VERIFICATION      ◄── TEST_LANES.md, tests/, protected oracle material

  ── off the authority spine, deliberately ──
  HISTORICAL        current/ stage records, RUN prompts, history-mapping.md
  SPECIFIED-UNBUILT specified-unbuilt/ (22) — designed, not authorized
  DEFERRED          deferred-reserved/, 18 DEFERRED prompt records
  PARKED            spare-parts-yard.md — built, unassigned from a surface
  ORACLES           protected test keys — must never enter the evidence path
```

**The layer that does not exist yet is the `GOV-*` band.** Cross-cutting
principles currently live one layer too low — inside individual `CIC` contracts —
which is precisely why the same rule now appears in two contracts with two
wordings. See `DRIFT-AND-LINEAGE.md`, cluster DC-01.

**Precedence** is already settled and unchanged by this audit
(`canonical-implementation-order.md`): explicit current Product Owner instruction →
current approved governance → applicable standing contract/version → order-specific
detail → implementation convenience. For domain-model rules,
`constitutional-invariants.md` is highest; for infrastructure behaviour, tested
code on pushed `main` governs.

---

## Domain map

Fifteen domains, built from corpus content. Counts are records whose primary
subject is that domain.

| # | Domain | Records | Canonical home today | Notes |
|---|---|---:|---|---|
| D01 | Product constitution & governance process | 6 | `constitutional-invariants.md`, `amendment-and-ratification.md`, `STATUS.md` | Densest authority, thinnest volume |
| D02 | Kernel / domain-object model | 7 | `current/kernel-object-model.md` | Ground truth is `services/case_workspace.py` |
| D03 | Evidence & authority (multimodal, intake) | 6 | `specified-unbuilt/camel-multimodal-programme.md` | MM1–MM9 implemented; record still filed as specified-unbuilt |
| D04 | Airlock / external intelligence | 7 | `specified-unbuilt/external-intelligence-airlock.md` | **Filing anomaly** — live authorizations in a specified-unbuilt file |
| D05 | Spin / Helix | 8 | `GO-HELIX-01`, `GO-HELIX-QA-01`, `CIC-SPIN-INTELLIGENCE` | Concept anchors in prompts, contract in `current/` |
| D06 | Composer / GO conversation | 9 | `CIC-COMPOSER`, `CIC-GO-CONVERSATION`, `go-dna-01` | Four CA1 stage records sit under this |
| D07 | Developer Mode / CCN | 4 | `CIC-DEVELOPER-MODE`, `CIC-CCN`, `current/developer-mode-ccn.md` | Source of drift cluster DC-01 |
| D08 | Page / panel / template | 5 | `page-surface-template-inventory.md`, `panel-template-system.md`, `CIC-PAGE-TEMPLATE`, `CIC-PANEL` | Two contracts + two inventories + `UI_REFERENCE_MAP.md` |
| D09 | Project lifecycle & publication | 6 | `cross-boundary-architecture.md`, `GO-RFP-PUBLICATION-BARRIER-01` | |
| D10 | Security / tenancy / trust | 5 | `organizational-security-department.md`, `GO-TRUST-SECURITY-01` | All specified-unbuilt or deferred |
| D11 | Self-project commissioning | 13 | `comm-a1` … `comm-i6`, `continue-01` | Largest single cluster; entirely historical |
| D12 | Test / oracle | 4 | `CODEX-PSD-TEACHER-ORACLE-02`, `TEST_LANES.md` | **Protected oracle filed in the prompt depository** |
| D13 | Prompt & process governance | 5 | `PROMPT_REGISTER.md`, `canonical-implementation-order.md`, `contracts/README.md` | The meta layer |
| D14 | Deployment / repo safety | 3 | `CIC-DEPLOYMENT`, `CIC-REPO-SAFETY`, `CLAUDE.md` | |
| D15 | Future programmes (deferred concepts) | 33 | `prompt-depository/GO-*` | 18 `DEFERRED`, 15 `APPROVED` concept anchors |

**Cluster observation.** D11 (13 records) and D15 (33 records) together are 38% of
the corpus and carry no current authority. The live authority surface is far
smaller than the corpus size suggests: **20 canonical-current records out of 121.**

---

## Classification vocabulary used

As directed, plus one addition. `GOVERNANCE CANDIDATE` was needed for the 20
`APPROVED` prompt records that carry real governing concepts but are not
themselves canonical governance — the distinction §12 of the mission requires.

`CANONICAL CURRENT` · `GOVERNANCE CANDIDATE` · `HISTORICAL` · `SUPPORTING` ·
`SPECIFIED / UNBUILT` · `DEFERRED / RESERVED` · `DUPLICATE / DRIFT` · `ORPHANED` ·
`UNCLEAR` · and the `CANDIDATE GOV-P/D/CN/CR/S/I/X` overlay.

The `GOV-*` candidate tags are an **overlay**, not an exclusive class: a record can
be `CANONICAL CURRENT` and still contain a principle that belongs canonically in a
`GOV-P`.

---

## Method and its limits

Every governance directory was enumerated and every file opened at least to its
header. Contract invariants were extracted mechanically and compared field-by-field
— that is how the drift clusters were found, not by impression. The prompt
depository was sampled comprehensively by register status, with full reads of the
Airlock, Helix, Spin, Composer, Oracle and PSD records.

**What this audit did not do:** read all 21,128 lines end-to-end. Long historical
stage records (`comm-*`, `ca1*`, `pilot-*`, ~8,000 lines) were classified from
headers, status markers and `STATUS.md`'s own table rather than full reads. They
are uniformly historical stage records and none is proposed for migration, so the
cost of a deeper read was not justified — but a principle buried in one of them
would not have been found. `MIGRATION-QUEUE.md` records this as a known limit, not
a completed sweep.
