# Adopt Owner Baseline and Prepare Developmental Commissioning (CLAUDE-POSTCAMEL-COMM-I2)

**Status: OWNER BASELINE ESTABLISHED — DEVELOPMENTAL COMMISSIONING READY.**
Authorized following COMM-I1's RFP-independent preparation
(`governance/current/comm-i1-commissioning-specimen-setup.md`, commit
`86e63dc`) and the Product Owner's adoption of
**GEMINI-ARCHIOSK-RFP-02B — Retrospective Owner's Project Requirements —
Revision 0.2A — Product Owner Adoption Copy**. This stage ingests that
adopted document as the real project's Governing Source, registers its
34 Owner Requirements (OPR-1.1 through OPR-7.5) through the ordinary
product, reconciles the registered baseline against the adopted text,
and records the developmental commissioning doctrine as procedure. It
does **not** perform Compliance assessment, adjudicate any Requirement,
create a Punch List object, or implement FPR-12/FPR-13.

---

## Governing-input check

- `HEAD == origin/main == 86e63dc` confirmed before this stage began;
  working tree clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture.
- The real, persistent commissioning specimen (project id
  `0b743d80-13b0-4253-b411-9fa17ff11927`, owner `admin`, created by the
  persistent operator account `archiosk_commissioning`) was confirmed
  unchanged from COMM-I1's own closing state: 4→(now discussed below)
  Sources, 0 governed Requirements, 13 unpromoted founding-charter
  candidates, `operating_environment=client_owner`.
- This stage's Governing Owner Source is the exact document the Product
  Owner pasted and adopted in chat — verified against the session
  transcript rather than reconstructed from memory, since a prior turn
  in this same stage had already established (and the Product Owner had
  explicitly accepted) that no such document could be fabricated or
  substituted. No word of its Requirement text (Section B) was altered
  before registration.

## Part 1 — Owner OPR ingestion and Requirement registration

**Ingestion.** The adopted document was added to the real project as a
Governing Source through the ordinary, already-proven, extraction-free
pathway COMM-I1 identified — "+ Add Documents"
(`add_document_source` → `CaseWorkspaceStore.add_source`), **not** as a
second founding document. It now appears as the project's fourth
Source, `kind="project_document"` — visibly a different `kind` value
than the founding charter's own `rfq_rfp_document`, which is itself a
small, free, structural cue distinguishing "the Owner's governing
requirements document" from "the neutral charter used to open the
project," on top of the naming-convention distinction COMM-I1 already
relied on.

Confirmed live and by direct registry inspection: adding this Source did
**not** trigger requirement extraction — the legacy candidate-requirement
count stayed at 13, exactly as COMM-I1's own finding predicted.

**Registration.** All 34 Owner Requirements (OPR-1.1 through OPR-7.5)
were registered through the real, existing "+ Register a Requirement"
route (`POST /projects/<id>/workspace/requirements/register` →
`CaseWorkspaceStore.register_requirement`) — the same mechanism a human
reviewer would use one requirement at a time, driven here as a scripted
HTTP session against the live application (identical requests, same
authenticated operator account, same CSRF-protected form) rather than
34 manual clicks, purely to make exact verbatim preservation mechanical
instead of transcription-error-prone. No store method was called that
the real product route does not itself call; no field was populated
that the real registration form does not itself expose.

For each Requirement:

- `original_requirement_identifier` = the Owner ID exactly as given in
  the adopted document's own Section C schedule ("OPR-1.1", ..., "OPR-7.5").
- `text_reference` = the exact Section B "shall" statement for that ID,
  verbatim, with only the leading `**OPR-x.y (Name):**` markdown/ID
  prefix removed (the ID is already carried in
  `original_requirement_identifier`; the parenthetical short name is
  addressed under Residuals below).
- `source_id` = the newly-added Governing Source.
- `registration_method` = `human_registered` (honest — this was
  deliberate manual registration against a Source the extraction
  pipeline never touched, not machine extraction).
- `status` = `active` (existence only; no compliance claim).

## Part 2 — Reconciliation

A byte-for-byte comparison of all 34 persisted `text_reference` values
against the adopted document's own Section B text found **zero
mismatches**. Also confirmed by direct registry inspection:

- 34 governed Requirements exist; 34 unique `original_requirement_identifier`
  values; no duplicate registration.
- All 34 cite the single new Governing Source — no accidental split
  across multiple Sources, no accidental reuse of the founding charter's
  Source id.
- The 13 founding-charter candidate requirements (legacy extraction
  artifacts from COMM-I1's neutral charter) are **untouched** —
  still 13, still unpromoted, still structurally separate from the 34
  governed Requirements. A live walkthrough (below) confirmed this
  separation is also visible, not just true in storage.
- No Requirement was accidentally merged (each of the 34 Owner IDs maps
  to exactly one governed record) or split (no Owner ID produced more
  than one record).

**Honestly reported product limitation, not silently compensated for:**
the real "+ Register a Requirement" form exposes exactly two content
fields — a clause identifier and its text — matching
`register_requirement_route`'s own three-field signature
(`source_id`/`original_requirement_identifier`/`text_reference`). The
adopted document's richer Section C schedule (Rationale, Priority,
Classification, Verification Method, Durable Record Source,
Supersedes/Refines) has no first-class per-Requirement field to land in
today; `Requirement` does carry optional `classification`/`title`/
`subject_domain`/`authority_source` fields the store method supports,
but the real registration route does not yet expose them, and populating
them by calling the store method directly (bypassing the route) would
have produced Requirement records no actual user of today's product
could produce — an honesty problem worse than the gap itself. This
stage registered through the real route exactly as it exists, and
relies on the whole adopted document remaining attached and readable at
the Source level for the schedule's richer columns; a future,
separately-authorized enhancement to the registration form (not
undertaken here) is the correct fix, not a workaround inside this stage.

## Part 3 — Developmental commissioning doctrine (procedure, not an OPR requirement)

Recorded per the Product Owner's explicit instruction to preserve, as
commissioning methodology, the distinction established after COMM-A1:

> **Commissioning begins when a requirement first has consequences, not
> when the project is ready to be inspected.**

This doctrine does not reopen or modify the adopted OPR. It governs how
future commissioning work against this baseline should be structured.

**Two questions, kept explicitly separate:**

1. **Present-state conformance** — does the system, as it exists today,
   satisfy this Requirement? (The ordinary Compliance/Adjudication
   question ROOT-I2's rollup and `RequirementAdjudication` already
   answer, deliberately not touched by this stage.)
2. **Developmental/formative conformance** — *when* should this
   Requirement first have governed design or implementation; was that
   conception window met, missed, or only partially met; and, where the
   evidence supports a conclusion, what did a missed window cost
   downstream (rework, compromise, accepted risk)?

Question 2 is retrospective-analysis methodology, not a new compliance
outcome and not a new adjudication vocabulary — `RequirementAdjudication`
is not extended by this doctrine, and no new outcome value is
introduced.

**The eleven-field commissioning structure** (prepared as a template
only — not populated for all 34 Requirements this stage; see Part 4 for
the bounded preliminary pass actually performed):

| # | Field | What it records |
|---|---|---|
| 1 | Requirement | The Owner ID and text under analysis |
| 2 | Conception window | When, ideally, this Requirement should first have governed a design or implementation decision |
| 3 | Historical evidence of first recognition | The earliest durable record (commit, governance document, STATUS.md row) showing this concern was actually recognized |
| 4 | Relevant decision | The specific design/implementation decision the conception window bears on |
| 5 | Earliest detectable deviation | The first point, if any, where practice diverged from what the Requirement would have required |
| 6 | Prevention opportunity | Whether, and how, earlier recognition could have avoided the deviation |
| 7 | Downstream dependents | What later work depended on (or was built assuming) the eventual resolution |
| 8 | Consequence of delayed recognition | Rework, compromise, accepted risk, or cost attributable to a missed window, where evidence supports a conclusion |
| 9 | Present condition | Current state relative to the Requirement (present-state conformance, cross-referenced, not re-derived here) |
| 10 | Verification evidence | What durable record substantiates fields 2–9 |
| 11 | Remaining disposition | What, if anything, still needs deciding |

Every claim entered against fields 2–8 must be tagged with one of three
evidence tiers, carried through explicitly rather than left implicit:

- **Directly evidenced** — a specific durable record (a commit, a
  governance document, a STATUS.md row, the adopted OPR's own text)
  states the fact.
- **Reasonable inference** — the available durable record is consistent
  with a conclusion but does not state it outright.
- **Insufficient evidence** — no durable record exists to support a
  conclusion either way; say so rather than guess.

**Two-tier applicability.** This doctrine has two intended depths of
use, recorded here so a future session does not assume one implies the
other:

- **Deep self-commissioning** — the ARCHIOSK retrospective exercise
  itself, where the system's own development history is the evidence
  base and a thorough, multi-requirement conception-window analysis is
  both possible and the point of the exercise.
- **Light ordinary-project commissioning** — a normal client/RFP-driven
  project, where this same present-state/developmental distinction still
  applies in principle, but would ordinarily be applied only to a small
  number of Requirements a reviewer has independent reason to flag as
  structurally formative, not exhaustively to every Requirement — an
  ordinary project does not have, and does not need, ARCHIOSK's own
  depth of internally-authored development history to draw on.

This is procedural knowledge only. It authorizes no new RFP-facing
capability, no new domain object, and no UI.

## Part 4 — Bounded conception-window classification (preliminary, not exhaustive)

Commissioning-analysis only — no compliance judgment is made or implied
by anything in this Part. Six Requirements were examined against
durable records already in this repository's own governance corpus;
the remaining 28 were not analyzed this stage (see Residuals).

**Directly evidenced, timing-critical (early conception, later
correction needed):**

- **OPR-3.4 (Contextual Operations)** — the adopted OPR's own Section F
  Historical Evolution register states outright: *"Earlier Direction:
  Rigid 'four-chamber' fixed layout. Later Refinement: Flexible
  workspace grammar separating listings, local navigator, main display,
  and contextual operations..."* This is directly evidenced from the
  Governing Source itself — a foundational navigation requirement whose
  first realized form had to be superseded. Downstream cost is not
  quantified in any available durable record; only the fact of the
  supersession is directly evidenced, not its cost.
- **OPR-1.4 (Lifecycle Management)** — directly evidenced by this very
  adoption cycle: the OPR's Section A amendment note records that the
  Rev 0.2 formulation assumed unsupported whole-project-container
  archive/restoration, corrected only at Product Owner reconciliation
  following COMM-A1's findings. The conception window for "what
  lifecycle capability is actually implemented" was effectively missed
  until this commissioning-preparation sequence itself surfaced it.
- **OPR-7.4 (Deficiency Close-Out)** — the same pattern: Section A
  records the Rev 0.2 formulation was revised to be implementation-
  neutral (no dedicated `PunchListItem`/Punch List UI/second canonical
  truth system required) specifically because COMM-A1's own repository-
  grounded audit found no such object exists or is needed. Directly
  evidenced, same conception-window class as OPR-1.4.

**Directly evidenced, early-and-sound (offered as a contrast case, not
every requirement is late-recognized):**

- **OPR-3.5 (Canonical Ownership)** — `governance/STATUS.md`'s own
  ROOT-A1 record states the nine-branch canonical root audit "found the
  domain layer already disciplined about canonical ownership" *before*
  that audit ever ran — i.e., the discipline predates its own
  formalization as an Owner Requirement, evidence of an early, sustained
  conception window with no detected deviation.

**Reasonable inference only, insufficient evidence for a substantive
conclusion:**

- **OPR-2.4 (Provenance Maintenance)** — the Requirement Schedule's own
  "Supersedes/Refines" column notes "Refines OPR-4.2 (Rev 0)," meaning
  this clause's identity or scope changed at least once before Rev 0.2A.
  Rev 0's actual text was never supplied to this session; the *nature*
  of that change cannot be characterized beyond the fact that one
  occurred.
- **OPR-2.3 (Drawing & Visual Ingestion)** — the Schedule similarly
  notes "Refined from Rev 0.1." Same limitation: a change is inferable,
  its substance is not.

No other Requirements were examined for conception-window timing this
stage. This is a bounded, preliminary pass, not a completed analysis
across the 34-Requirement baseline.

## Part 5 — Zero-Founder / technical verification (bounded)

Live-browser walkthrough, starting from the sign-in page, as the real
`archiosk_commissioning` operator:

- Requirements Listings branch shows **34** (sidebar count and Requirements
  view heading both agree).
- "Extracted, not yet governed (13)" remains a separate, distinct
  disclosure from "Governed Requirements (34)" — the founding-charter
  noise and the Owner baseline are visually distinguishable, not merely
  distinguishable in storage.
- ROOT-I2's Compliance rollup, exercised for the first time against a
  real Owner baseline rather than a disposable test fixture, rendered
  correctly: *"34 awaiting review — not yet adjudicated; this is not a
  finding of non-compliance — from
  GEMINI-ARCHIOSK-RFP-02B_Rev0.2A_Product-Owner-Adoption-Copy.txt (34)."*
  and a "34 NOT YET ASSESSED" governed-requirement pill — the "unknown
  is not non-compliant" rule holding exactly as designed, now proven
  against real Owner content instead of a synthetic fixture.
- Expanding a Requirement (OPR-1.1) rendered its exact registered text,
  its Owner ID, and a live Adjudicate control — present and functional,
  **not exercised**, per this stage's explicit boundary against
  performing Compliance assessment.
- Documents Listings shows all four Sources by name, the new
  `GEMINI-ARCHIOSK-RFP-02...` entry visibly distinct from the founding
  charter and the two prior text records.

No adjudication was submitted. No Compliance assessment was performed.
No `PunchListItem` or Punch List UI was created.

## Part 6 — Boundaries observed

Confirmed not touched this stage: FPR-12 (Adaptive Attention & Context
Circulation) and FPR-13 (Trust Exchange & Security Commissioning) —
recorded as Future Programmes only, per the adopted OPR's own Section E,
untouched; Registry/Numbering; canonical Risk object; First-Run Preview;
PowerPoint/presentation architecture; Terminal Eye; Surface Trust. No
`PunchListItem` domain object or dedicated Punch List UI was created.
No unrestricted commissioning or Compliance assessment was performed.

## Testing

No application code was modified this stage — every change was real
project data created through the ordinary, already-tested product
(`add_document_source`, `register_requirement_route`, both already
covered by ROOT-I1–ROOT-I3's own test suites) or a governance-
documentation commit. Per this stage's own scope, the full regression
suite was not re-run; the last confirmed baseline (2969 passed, 0
failures, at `a89d612`/`98e52dc`/`2c78aa8`/`86e63dc`) remains accurate,
since nothing that baseline covers has changed.

## Residuals carried forward

- Section C's richer per-Requirement schedule metadata (Rationale,
  Priority, Verification Method, Durable Record Source, Supersedes) is
  preserved only at the whole-Source level, not field-by-field on each
  Requirement (Part 2's own honestly-reported limitation) — a future,
  separately-authorized enhancement to the registration form, not fixed
  here.
- The Section B parenthetical short name (e.g. "Project Creation") was
  not persisted as `Requirement.title` — the real registration route
  does not expose that field; each name remains readable in the
  attached Governing Source itself.
- 28 of the 34 Requirements received no conception-window analysis this
  stage (Part 4) — a bounded, explicitly incomplete first pass, not a
  finding that the other 28 have no timing story.
- Everything COMM-A1/COMM-I1 already listed as a residual (Registry/
  Numbering, canonical Risk, Punch List projection, First-Run Preview,
  Source-category-as-a-UI-field) remains exactly as COMM-I1 left it.

## Recommendation

**OWNER BASELINE ESTABLISHED — DEVELOPMENTAL COMMISSIONING READY.** The
adopted Owner baseline is registered, verbatim-reconciled, and
technically verified live; the developmental commissioning doctrine and
its evidence-graded conception-window method are recorded as procedure;
a bounded preliminary classification identified three directly-evidenced
timing-critical Requirements and one directly-evidenced early-and-sound
contrast case. **This is not a claim that ARCHIOSK is fully commissioned
against this baseline** — no Compliance assessment or adjudication has
been performed against any of the 34 Requirements, and 28 of them have
no conception-window analysis yet. The recommended next tranche is a
real, bounded first commissioning pass: adjudicate a small, deliberately
chosen subset of the 34 (a natural starting set is the four Requirements
Part 4 already examined, since their developmental history is already
documented) rather than attempting all 34 at once.
