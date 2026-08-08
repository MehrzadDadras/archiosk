# Curated Self-Project Commissioning Setup (CLAUDE-POSTCAMEL-COMM-I1)

**Status:** RFP-independent preparation complete; **HOLD on Owner OPR
ingestion** — the approved Gemini Revision 0.2A has not been supplied.
Authorized following COMM-A1's READY WITH PREPARATION verdict
(`governance/current/comm-a1-self-project-commissioning-readiness.md`,
commit `2c78aa8`). This stage executes the RFP-independent bounded
preparation COMM-A1 named and establishes the real ARCHIOSK commissioning
specimen — it does **not** make ARCHIOSK the live management system
controlling its own continued development. The existing Claude/Git/
repository/prompt process remains authoritative for building ARCHIOSK.

---

## Governing-input check (Section 1)

- `HEAD == origin/main == 2c78aa8` confirmed before this stage began.
- Working tree clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture.
- The approved Gemini Owner Project Requirements, Revision 0.2A, was
  searched for directly (repository-wide file search for `*OPR*`/
  `*gemini*`) and was **not found** — the only matches are the
  pre-existing, unrelated `NREOCRC-OPR-001` test fixture corpus, a
  different specimen used for other testing purposes. No OPR content was
  pasted or attached to this conversation either.
- Per this stage's own explicit instruction, work stopped before Parts
  F/G (Owner OPR ingestion, reference-schedule reconciliation) and before
  the "real" forms of Parts H/I (a genuine Compliance baseline and first
  commissioning pass both require real Owner Requirements). Parts A-E, K,
  L (the RFP-independent scope), M, and N proceeded.

## Part A/K — Boundary preserved, new future programmes recorded

No implementation occurred for any item in COMM-I1's own Part A exclusion
list. Two new future-programme concepts named in Part K were recorded,
without implementation, per the same `specified-unbuilt/` convention
already used for Voice/Presentation:

- `specified-unbuilt/adaptive-attention-and-context-circulation.md`
- `specified-unbuilt/trust-exchange-and-security-commissioning.md`

Both are explicitly concept-preservation records, not repository-grounded
architecture investigations (unlike the Voice/Presentation records) —
`governance/STATUS.md` gained matching paragraph entries under "What's
specified but unbuilt," worded to avoid overclaiming rigor that was not
applied.

## Part B — Real commissioning specimen created

A real, persistent project was created through the ordinary product
pathway — no special/privileged treatment:

- **Name:** ARCHIOSK Application Development Project
- **Operating environment:** Client / Owner (per COMM-A1's own finding
  and the Product Owner's real acceptance authority)
- **Project ID:** `0b743d80-13b0-4253-b411-9fa17ff11927`
- **Owner:** set to the real, pre-existing `admin` account
  (`architect@rogers.com`) via the ordinary "Manage access → Set owner"
  control — never the operator account used to create it.
- **Created via:** a new, persistent, clearly-named operator account,
  `archiosk_commissioning` (admin role) — created because the real
  `admin` account's password is not known to this session and must never
  be entered or reset by it. This account is **not** a throwaway fixture
  and was **not** deleted at the end of this stage, unlike every prior
  disposable walkthrough account this session used — it, and the project
  it created, are the real, ongoing commissioning specimen.

This project is **real and persists** after this stage ends. It is not
disposable test data.

## Part C — Founding charter

A neutral founding charter (not the Gemini OPR) was written and used as
the project's founding upload document. It states: project identity;
purpose (commissioning ARCHIOSK against its approved Owner requirements,
once ingested); the Product Owner's acceptance authority; that
development history is used as a curated commissioning specimen; and
that ARCHIOSK does not control its own live development process. It
explicitly disclaims being a competing Owner-requirements document.

**Residual, honestly reported:** the founding-document ingestion pathway
(`CaseWorkspaceStore.get_or_create` → `ingest_upload`) runs machine
requirement-extraction unconditionally on whatever document is uploaded
at project creation, regardless of content. The neutral charter produced
13 noisy "candidate requirements" (ordinary narrative sentences tagged
`other`/`scope of work` at 75-90% confidence) — confirmed live. None were
promoted; none are governed Requirements. This is the same finding
COMM-A1 made against its own disposable test charter, now reconfirmed
against the real, permanent one. No code change is recommended to fix
this — it is architecturally unavoidable for *any* founding document
under the current ingestion design, and the candidates are inert unless a
human deliberately promotes one.

## Part D — Source category mapping (repository-grounded, not assumed)

Determined by direct code inspection, then confirmed live:

| Category | Existing primitive/path | Extraction risk |
|---|---|---|
| Governing Source | `Source`, added via `add_document_source` ("+ Add Documents") *after* project creation — never as the founding document (Part C's own instruction) | None — `add_document_source` calls `CaseWorkspaceStore.add_source` directly and never touches `BHiveParser`/`RequirementsRegistry` |
| Supporting Evidence | `Source` (kind `text_record`), added via `add_text_record_source` ("+ Add Text Record") | None — confirmed live: adding two text records left the "Extracted, not yet governed" count unchanged at 13 |
| Historical Record | Same as Supporting Evidence for pre-project material; the project's own future `GovernanceLog` for everything that happens inside it going forward | None |
| Working Product | `WorkProduct`, created via the existing "+ New Work Product" form | N/A — not a Source, never enters extraction |

**Key finding, newly established this stage (not known at COMM-A1):**
requirement-extraction is a **founding-document-only** behavior.
`add_document_source` and `add_text_record_source` — the only two paths
for adding a Source to an *existing* project — both call
`CaseWorkspaceStore.add_source` directly and never invoke `BHiveParser`.
This means that when the real Gemini OPR is added later via "+ Add
Documents" (per Part C's own instruction not to re-use it as a second
founding document), **no automatic candidate extraction will run against
it at all.** Every OPR-derived Requirement will need to be registered
through the existing, already-tested "+ Register a Requirement" manual
path — a real, fully legitimate, already-designed-for workflow (its own
UI copy: "For a Requirement's text that lives in a Source the legacy
extraction pipeline never saw... No Investigation needed"), not a gap.
This materially changes Part E/F's own future execution plan and is
recorded here so a future session does not assume automatic extraction
will do this work.

## Part E — Curated corpus actually used

Deliberately small and representative, not the complete development
archive, per this stage's own explicit instruction:

1. The founding charter itself (Governing charter, not an Owner Source).
2. "COMM-A1 Self-Project Commissioning Readiness — Summary" (Text
   Record, Supporting Evidence) — condensed findings, pointing to
   `governance/current/comm-a1-self-project-commissioning-readiness.md`
   as the authoritative full record.
3. "CAMEL MM1–MM9 and POST-CAMEL/ROOT Stabilization — Summary" (Text
   Record, Supporting Evidence) — condensed history, pointing to
   `governance/STATUS.md` as the authoritative full record.

**Not yet populated, honestly listed rather than silently skipped:**

- The approved Gemini OPR and its structured Requirement Schedule —
  blocked entirely on availability (Part F/G).
- A dedicated canonical-ownership/project-isolation governance-evidence
  item (e.g. citing `governance/constitutional-invariants.md`) — omitted
  to keep the corpus genuinely small per this stage's own "avoid
  indiscriminate ingestion" instruction; trivial to add later via the
  same "+ Add Text Record" path.

## Parts F/G/H/I — Explicitly not executed

Owner OPR ingestion, reference-schedule reconciliation, a real Compliance
baseline, and a first commissioning pass all require the approved Gemini
OPR, which has not been supplied. None were executed. No fabricated or
placeholder Owner Requirements were created to simulate them.

## Part J — Punch List boundary preserved

No canonical `PunchListItem` type was created. No implementation of the
Requirement → adverse adjudication → Finding → Disposition → optional
Task → Punch List projection was attempted — this remains exactly the
future architecture-gate item COMM-A1 already named.

## Part L — Zero-Founder walkthrough (RFP-independent scope only)

Performed live, via the ordinary product, logged in as the real
`archiosk_commissioning` operator account:

- **Open/create the project:** done — real project created via the
  ordinary `/upload` flow, Client/Owner environment.
- **Distinguish Governing Source from historical/supporting evidence:**
  currently a **documentation convention** (each Text Record's own title/
  content states its category), not an enforced UI field — honestly
  reported as a small residual; nothing in the UI visually flags a Source
  as "Governing" vs "Supporting" vs "Historical" today.
- **Navigate Requirements:** confirmed quiet and correct — 0 governed,
  13 un-promoted candidates, exactly matching ROOT-I1/ROOT-I2's own
  established progressive-disclosure behaviour.
- **Open Compliance:** correctly absent — ROOT-I2's Compliance section
  only renders once at least one governed Requirement exists, confirmed
  unchanged.
- **Leave and return without losing state:** confirmed — navigated
  between Overview/Documents/Requirements repeatedly; ownership, Source
  list, and environment all persisted correctly across every navigation.
- **Open Owner OPR / review extracted Requirement / representative
  Investigation-Finding tied to a real Owner Requirement:** not
  performed — requires the OPR (Parts F/H/I).

## Part M — Testing

**No application code was modified this stage.** Every change was either
real project data created through the ordinary, already-tested product
(no new code path exercised that ROOT-I1/ROOT-I2/ROOT-I3's own test
suites don't already cover) or a governance-documentation commit. Per
this stage's own explicit instruction ("If no application code needs
modification, say so explicitly... do not make code changes merely to
make this prompt appear productive"), no regression tests were run and
the full suite was not re-executed — the last confirmed baseline (2969
passed, 0 failures, at `a89d612`/`2c78aa8`) remains the current, accurate
baseline, since nothing that baseline covers has changed.

## Part N — Durable record

This document, plus the two new `specified-unbuilt/` records and the
`governance/STATUS.md` updates, are committed to the repository following
the same durable-record convention COMM-A1 itself was preserved under.

## Residuals carried forward

- The founding-document extraction-noise behaviour (Part C) — architectural,
  not a defect, not fixed here.
- Source-category distinction is documentation-convention-only, not a UI
  field (Part L) — a real, small, future usability item.
- The curated corpus's canonical-ownership/governance-evidence item is
  not yet added (Part E) — trivial future addition.
- Everything COMM-A1 itself already listed as a residual (Registry/
  Numbering, canonical Risk, Punch List projection, First-Run Preview)
  remains exactly as COMM-A1 left it — untouched by this stage.

## Recommendation

Per this stage's own required deliverable, see the final terminal/chat
report for the full lettered report (A-Q) and the chosen recommendation.
