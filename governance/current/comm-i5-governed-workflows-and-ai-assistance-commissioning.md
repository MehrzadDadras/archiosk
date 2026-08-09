# Governed Workflows and AI Assistance Commissioning (CLAUDE-POSTCAMEL-COMM-I5)

**Status: GOVERNED WORKFLOWS AND AI ASSISTANCE COMMISSIONING ASSESSED —
PRODUCT OWNER REVIEW REQUIRED.** Authorized following the Product
Owner's own confirmation of OPR-2.5 as Satisfied/Late Correction
(closing COMM-I4A, commit `6120042`). Assesses fourteen Current
Baseline Requirements spanning workspace navigation (3.x), governed
work products (4.x), and AI assistance (5.1-5.3). **No new
`RequirementAdjudication` was persisted for any of the fourteen** — every
outcome below is an agent assessment awaiting Product Owner review.
**No application code was modified this stage** — investigation and
live verification only.

---

## Governing-input check

`HEAD == origin/main == 6120042` confirmed before this stage began;
working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The
commissioning specimen was re-confirmed unchanged before and after this
stage's own live verification (which added two real Conversation
messages but registered no new Requirement, Source, or Adjudication).

## B–D. OPR-3.1/3.2/3.3 — Listings, Local Navigator, Main Display

**OPR-3.1 — AGENT ASSESSMENT: Satisfied.** The Lists sidebar
(Documents/Requirements/Investigations/RFI Correspondence/Work
Products/Tasks/Tags/Conversation) is the real, live, repeatedly-used
navigation surface throughout this entire commissioning sequence.
**Developmental: Timely Correction [DIRECT].** `governance/STATUS.md`'s
own ROOT-A1/ROOT-I1 record: ROOT-A1's audit found Requirements had no
dedicated Listings branch (living instead under an Overview accordion)
— "the real gap was navigation drift, not the data model" — and ROOT-I1,
the very next authorized stage in the same continuous programme,
promoted it to a real numbered branch. Found and fixed within one
continuous sequence, not left open across releases.

**OPR-3.2 — AGENT ASSESSMENT: Satisfied.** Per-modality internal
navigation (PDF page navigation, spreadsheet worksheet/row navigation,
drawing sheet navigation) built consistently across MM2–MM5.
**Developmental: Early-and-Sound Conception [DIRECT]** — each modality
added its own internal navigation without reworking a prior one's.

**OPR-3.3 — AGENT ASSESSMENT: Satisfied.** The central Display pane is
the primary, unchanged working surface used throughout every stage of
this commissioning sequence. **Developmental: Early-and-Sound
Conception [DIRECT].**

## E. OPR-3.6 — Persistence

**AGENT ASSESSMENT: Satisfied**, with one honestly-noted nuance.
Project-level state (Requirements, Sources, adjudications, Conversation)
is server-side and durable — confirmed repeatedly this session,
including a real cross-project switch in COMM-I4 with zero state loss.
**Nuance, checked directly this stage:** panel visibility and Appearance
preferences (`beehive:panel:*`, `beehive:appearance:*`) are stored in
browser `localStorage`, confirmed by direct inspection of
`templates/base.html` — device/browser-scoped, not account-scoped. A
user's chosen layout does not follow them to a different browser or
device, though their actual project data always does. **Developmental:
Early-and-Sound Conception for the governed project state itself
[DIRECT]; the localStorage-scoped UI-preference nuance is a design
characteristic, not a clear deviation from the Requirement's own text**
["across user sessions" is reasonably read as same-device session
continuity, which localStorage does provide] **[REASONABLE INFERENCE]**.

## F. OPR-3.7 — Progressive Disclosure

**AGENT ASSESSMENT: Satisfied.** Subdisclosure/accordion-based
complexity scaling is the consistent interaction grammar across every
Listings branch and Toolbox pane. **Developmental: Early-and-Sound
Conception [DIRECT]** — ROOT-A2's own two-pass stress test (real
Infrastructure Ontario procurement material, then a deliberately harder
"universal venue" generalization test) validated this grammar
unchanged against real, adversarially-chosen scenarios, not merely
against its own original test cases.

## G. OPR-4.1 — Requirement Recording

**AGENT ASSESSMENT: Satisfied.** Creation via `register_requirement`
(exercised 34+ times this session); "editing" via `revise_requirement`
— deliberately a non-destructive Supersession-based revision (an
Addendum), never in-place text mutation, consistent with this
codebase's append-only philosophy for every other governed object.
**Developmental: Early-and-Sound Conception [DIRECT]** — the
revision-not-mutation design choice is present from `revise_requirement`'s
own original implementation, not a later correction.

## H. OPR-4.2 — Requirement Adjudication (special scrutiny)

**AGENT ASSESSMENT: Satisfied**, for the Requirement's own text.
`RequirementAdjudication` (Foundation Batch K), the closed five-value
outcome vocabulary, and the real Adjudicate control are all present,
tested, and repeatedly exercised this commissioning sequence.
**Developmental: Early-and-Sound Conception [DIRECT].** **Important
scope note:** OPR-4.2's own text ("status tracking, approval gating,
and adjudication") does not itself promise a human-vs-agent authority
distinction — that promise belongs to OPR-5.3 and to
`RequirementAdjudication`'s own docstring. The authority-distinction
finding is recorded fully under OPR-5.3 below, not duplicated here,
per this stage's own instruction not to assume governance notes solve
a product limitation.

## I. OPR-4.3 — Compliance Rollup

**AGENT ASSESSMENT: Satisfied.** ROOT-I2's Compliance rollup, exercised
live throughout this entire commissioning sequence (correctly
distinguishing "awaiting review" from "needing attention," never
treating "unknown" as "non-compliant"). **Developmental: Timely
Correction [DIRECT].** ROOT-A2's own audit found this as the one real
gap in an otherwise-validated root architecture; ROOT-I2, the next
authorized stage, built it as a pure projection over existing
adjudication state. Same healthy audit-then-immediate-fix pattern as
OPR-3.1.

## J. OPR-4.4 — Investigations

**AGENT ASSESSMENT: Satisfied.** `InvestigationStep` (Foundation
Batch/Prompt 8 era) extended cleanly through MM6 (cross-modal
relationships) and MM7 (the `Claim` adapter, the deterministic
cross-modal investigation engine) without rework to the original
container. **Developmental: Early-and-Sound Conception [DIRECT]** —
`governance/STATUS.md`'s own MM7 row: "Reuses `InvestigationStep`...
unchanged as the investigation container... rather than a second
parallel record system."

## K. OPR-4.5 — Findings & Decisions (special scrutiny)

**AGENT ASSESSMENT: Satisfied.** Checked directly this stage:
`Finding` itself carries no human/AI attribution field, by design — it
is documented as "a machine/reviewer ASSERTION," always traceable to
its own `analysis_id`, and `AnalysisRun` carries real machine
provenance (`engine_name`/`engine_version`). Human attribution lives on
the two separate objects that make human judgment about a Finding:
`ReviewerValidation` (`reviewer` field, epistemic accuracy) and
`Disposition` (`reviewer` field, workflow decision). "Full attribution"
is genuinely present, correctly distributed across three objects that
each answer a different question, not collapsed onto one. **This is
the same pattern OPR-5.3's own gap (below) is missing for
`RequirementAdjudication`** — worth naming as a lesson (Section P).
**Developmental: Early-and-Sound Conception [DIRECT]** — this
three-object separation is present from Foundation Batch design, not a
later correction.

## L. OPR-4.6 — RFI Generation (special scrutiny)

**AGENT ASSESSMENT: Satisfied.** Checked directly this stage, not
merely assumed: `create_rfi_draft` **structurally requires** a
`finding_id` and a prior `ReviewerValidation` on that Finding
("An RFI can only be drafted from a reviewed Finding") before an RFI can
even be created, and captures a `reference_snapshot` at creation time —
grounding is enforced by construction, not by policy alone. Every
RFI-drafting/editing/issuing route (`routes/workspace.py`) calls
`_require_capability(workspace, "rfi_originate", ...)` server-side —
confirmed by direct code inspection across all four RFI-mutation
routes — so operating-environment directionality (Proponent-only
origination, per CLAUDE-P30) is enforced at the route layer, not merely
hinted at in the template. **Developmental: Early-and-Sound Conception
[DIRECT]** for the grounding requirement (present in RFI's own original
implementation); directionality was added cleanly at CLAUDE-P30 as a
natural extension, not a correction to a prior gap.

## M. OPR-5.1 — Source-Aware Reasoning

**AGENT ASSESSMENT: Satisfied.** Live-verified fresh this stage, not
only cited from prior code reading: a real question against the
commissioning project ("What does OPR-3.5 require?") returned a
correct, grounded answer, and a control question naming a real,
different, pre-existing project in this same deployment ("What is
Nipigon Ramp?") produced **zero evidence of cross-project awareness** —
the system treated it as an unknown topic requiring a new Investigation,
not as a reference to the other project's real data. **Developmental:
Early-and-Sound Conception [DIRECT]** — `services/project_qa.py`'s own
docstring states this narrow, non-general-assistant scoping was the
deliberate design at that module's own original stage (CLAUDE-P38),
not a later hardening.

## N. OPR-5.2 — Evidence Grounding

**AGENT ASSESSMENT: Satisfied.** Same live test as OPR-5.1: the
"Source grounding" disclosure, expanded live this stage, showed the
exact governed record the answer was based on — *"OPR-3.5: A single
governed record shall maintain one canonical source of truth and be
projectable across multiple views without duplication. (status:
active)"* — a verbatim citation of the real governed Requirement, not
a paraphrase or plausible-sounding invention. **Developmental:
Early-and-Sound Conception [DIRECT]** — `ProjectQAResult.grounded_in`
exists in the module's own original design.

## O. OPR-5.3 — Human Authority (special scrutiny — the central finding of this tranche)

**AGENT ASSESSMENT: Partially Satisfied.** This Requirement's own text
— *"AI features shall assist and structure but require explicit human
review and approval for all governed work products"* — is genuinely
satisfied for some governed objects and genuinely not for one.

**Satisfied, checked directly:**
- `WorkProduct` (MM8): editing an `ai_proposed` section auto-transitions
  it to `edited_ai_proposal` — never silently to `human_authored` —
  and `accepted_by`/`accepted_at` require an explicit human action
  without touching `content_class`. Real, tested, structural.
- `Claim` (MM7): `propose_ai_assisted_claim` exists but is **not
  route-wired** — no live path lets an agent create a Claim without a
  human-initiated call. A human must always act first.
- Machine-extracted candidate Requirements: never auto-promoted;
  `promote_requirement_item` requires an explicit human action.

**Not satisfied, identified honestly rather than assumed away by
governance notes:** `RequirementAdjudication` has **no
content-provenance field of any kind** — confirmed by direct
inspection of its dataclass (`id`/`project_id`/`requirement_id`/
`outcome`/`adjudicator`/`adjudicated_at`/`reasoning`/evidence lists,
nothing else). Its own docstring calls it "the first-class record of
**a human's** answer," but nothing in the product enforces that,
detects a violation of it, or even records whether a given adjudication
was personally formed by a human or produced by an agent operating a
legitimately-authenticated account. **This is not hypothetical**: the
four `RequirementAdjudication` records this very commissioning
sequence created (COMM-I3) are real, honestly-attributed to
`archiosk_commissioning`, and legitimate under their own contemporaneous
Product Owner authorization (COMM-I3B's own finding) — but nothing
about their storage shape would have looked any different had they been
misrepresented as personal human judgments. The only thing that
prevented misrepresentation was this session's own external, procedural
honesty (governance documentation), never a product-level control.
More generally: no account in this system (not just
`archiosk_commissioning`) carries any human-vs-agent operator flag at
all — the product has no way, in principle, to know whether any given
authenticated action was a human's own click or a script's.

**Candidate smallest bounded correction, named but explicitly NOT
implemented this stage, requiring its own Product Owner authorization**
(per this stage's own instruction): a `content_class`-style field on
`RequirementAdjudication`, mirroring `WorkProduct`'s own already-proven
vocabulary and enforcement pattern (e.g., distinguishing an
agent-entered assessment awaiting confirmation from a personally-formed
human adjudication) — the same shape of fix COMM-I4→COMM-I4A already
proved out once for `register_source_revision`, not a novel mechanism
requiring invention.

**Developmental — two sub-findings, not one verdict:**
- `WorkProduct`/`Claim`/candidate-promotion: **Early-and-Sound
  Conception [DIRECT]** — each enforces human gating from its own
  original design.
- `RequirementAdjudication`: **Unresolved Developmental Deficiency
  [DIRECT]** — the gap has existed since Foundation Batch K's own
  original implementation; it was never regressed into, it was simply
  never built, and this is the first stage to assess it against
  OPR-5.3's own text rather than only as a procedural governance note
  (COMM-I3A/I3B).

## P. Cross-case formative lessons

- **Two genuinely different correction speeds appeared side by side in
  this tranche, worth contrasting directly.** OPR-3.1 and OPR-4.3 are
  both "Timely Correction" — a dedicated audit found a real gap and the
  very next authorized stage closed it, within one continuous
  programme. This is a materially healthier pattern than OPR-2.5's own
  "Late Correction" (COMM-I4/I4A) — a gap self-disclosed at ship time
  but left open across several subsequent stages before a dedicated
  commissioning pass finally forced the correction. Seeing both
  patterns in adjacent Requirements makes the distinction concrete
  rather than abstract.
- **OPR-4.5's attribution triad (`AnalysisRun`/`ReviewerValidation`/
  `Disposition`) is the pattern OPR-5.3's own gap is missing.** The
  codebase already solved "distinguish machine origin from human
  judgment" once, cleanly, for Findings — it was simply never extended
  to `RequirementAdjudication`. This is the second time in this
  commissioning sequence (after OPR-2.5's drawing-only
  `register_source_revision`) that the smallest correction candidate is
  "generalize an existing, already-proven internal pattern" rather than
  invent a new one.
- **AI-assistance isolation was proven behaviorally this stage, not
  only structurally.** COMM-I4 established structurally that no AI-facing
  function has a cross-project fetch primitive to misuse. This stage
  adds a live, real behavioral proof against a genuine, different,
  pre-existing project in the same deployment — the two forms of
  evidence (code shape, live behavior) now both exist and agree.

## Q. Ordinary-project/RFP translation

- **OPR-3.1:** What object categories does the Owner expect to browse as
  first-class lists from day one, so none end up buried under a generic
  "Overview" the way Requirements once were?
- **OPR-3.2:** For each accepted document type, what internal structure
  (pages, sheets, rows) will reviewers actually need to jump to directly?
- **OPR-3.3:** What single surface is the Owner's reviewer expected to
  treat as "the document," so secondary panes never compete with it?
- **OPR-3.6:** Which specific preferences (not just data) does the Owner
  expect to follow a person across devices, versus stay local to one
  browser?
- **OPR-3.7:** At what point does the Owner's own reviewer need to see
  everything at once versus progressively, and does that threshold match
  this system's own disclosure defaults?
- **OPR-4.1:** Does the Owner expect a Requirement's text to ever be
  corrected in place, or always via a traceable Addendum/revision?
- **OPR-4.2:** What outcome vocabulary does the Owner's own contract
  already use for compliance determinations, and does it map cleanly
  onto the five stored here?
- **OPR-4.3:** At what reporting cadence does the Owner need a rollup,
  and does "awaiting review" need to be distinguishable from "flagged"
  in their own reporting, the way it is here?
- **OPR-4.4:** What triggers the Owner's own definition of "an
  investigation" worth tracking as a discrete unit, rather than ordinary
  conversation?
- **OPR-4.5:** Does the Owner's own audit standard require knowing
  *which analysis engine/version* produced a Finding, not just who
  reviewed it?
- **OPR-4.6:** Which party in this specific contract structure is
  authorized to originate an RFI, and does that match the Client/Owner
  vs. Design-Builder/Proponent split this system enforces?
- **OPR-5.1:** What is explicitly out of bounds for AI-assisted answers
  on this project, and is that boundary enforceable structurally or only
  by instruction?
- **OPR-5.2:** What citation granularity will the Owner actually accept
  as "evidence" in a real dispute?
- **OPR-5.3:** Which specific governed decisions does this Owner require
  a human to have personally, individually reviewed — not merely
  authorized in advance as a class of action?

## R. Deficiencies/residuals discovered

- **OPR-5.3 / `RequirementAdjudication`: no content-provenance field —
  real, unresolved, honestly surfaced.** Candidate correction named in
  Section O, not implemented, pending Product Owner authorization.
- **OPR-3.6: UI-preference persistence is device/browser-scoped, not
  account-scoped** — a design characteristic, not a clear violation of
  the Requirement's own text; recorded for completeness.
- No other deficiency found among the fourteen Requirements.

## S. Product limitations

The account model (`models.User`) carries no human-vs-agent operator
distinction for any account, not only `archiosk_commissioning` — named
in Section O as the structural root of the OPR-5.3 finding, not
proposed for correction this stage.

## T. Product Owner decision package

| Owner ID | Agent assessment | Developmental classification | Strongest evidence | Tier | Deficiency/residual | Recommendation | PO decision required |
|---|---|---|---|---|---|---|---|
| OPR-3.1 | Satisfied | Timely Correction | ROOT-A1→ROOT-I1 STATUS.md record | DIRECT | None | No action needed | Confirm or override |
| OPR-3.2 | Satisfied | Early-and-Sound | MM2–MM5 per-modality navigation | DIRECT | None | No action needed | Confirm or override |
| OPR-3.3 | Satisfied | Early-and-Sound | Central Display pane, used throughout | DIRECT | None | No action needed | Confirm or override |
| OPR-3.6 | Satisfied | Early-and-Sound (data); design nuance (UI prefs) | Cross-project switch test (COMM-I4); `localStorage` inspection | DIRECT / INFER | UI prefs are device-scoped | No action needed; note nuance | Confirm or override |
| OPR-3.7 | Satisfied | Early-and-Sound | ROOT-A2's two-pass stress test | DIRECT | None | No action needed | Confirm or override |
| OPR-4.1 | Satisfied | Early-and-Sound | `revise_requirement`'s own non-destructive design | DIRECT | None | No action needed | Confirm or override |
| OPR-4.2 | Satisfied | Early-and-Sound | Foundation Batch K, exercised repeatedly | DIRECT | Authority question belongs to OPR-5.3, not here | No action needed | Confirm or override |
| OPR-4.3 | Satisfied | Timely Correction | ROOT-A2→ROOT-I2 STATUS.md record | DIRECT | None | No action needed | Confirm or override |
| OPR-4.4 | Satisfied | Early-and-Sound | `InvestigationStep` reused unchanged through MM6/MM7 | DIRECT | None | No action needed | Confirm or override |
| OPR-4.5 | Satisfied | Early-and-Sound | `AnalysisRun`/`ReviewerValidation`/`Disposition` attribution triad | DIRECT | None | No action needed | Confirm or override |
| OPR-4.6 | Satisfied | Early-and-Sound | `create_rfi_draft`'s structural grounding requirement; `_require_capability` gate on every route | DIRECT | None | No action needed | Confirm or override |
| OPR-5.1 | Satisfied | Early-and-Sound | Live test: correct grounded answer + zero cross-project leakage | DIRECT | None | No action needed | Confirm or override |
| OPR-5.2 | Satisfied | Early-and-Sound | Live "Source grounding" citation, verbatim match | DIRECT | None | No action needed | Confirm or override |
| **OPR-5.3** | **Partially Satisfied** | **Mixed: Early-and-Sound (WorkProduct/Claim/candidates) / Unresolved Developmental Deficiency (RequirementAdjudication)** | `RequirementAdjudication`'s own docstring ("a human's answer") vs. its own field set (no provenance field) | DIRECT | **Real: no product-level distinction between human and agent adjudication authority** | Candidate correction named (content-provenance field, mirroring `WorkProduct`), not implemented | **Decision needed: authorize a future corrective tranche / accept as residual / insufficient evidence** |

## U. Tests/live verification

No application code was modified this stage, so the full regression
suite was not re-run (nothing it covers changed). Live-browser
verification performed fresh this stage, starting from sign-in: a real
AI-assisted question against the commissioning project returned a
correct, grounded answer with an expandable "Source grounding" citation
matching the real governed Requirement verbatim; a control question
naming a genuine, different, pre-existing project in the same
deployment produced no evidence of cross-project awareness. All other
evidence was gathered by direct repository inspection (`Finding`,
`AnalysisRun`, `RequirementAdjudication`, `WorkProduct`,
`create_rfi_draft`, RFI route capability gates, `base.html`'s
localStorage usage) or by citing this repository's own already-
committed `governance/STATUS.md` record where a claim was already
proven in a prior stage.

## V. Commits / HEAD / origin/main / working tree

No code changes this stage — see the final chat report for the exact
commit recording this governance document alone.

## W. Recommendation for the final remaining commissioning tranche

Thirteen of fourteen Requirements need only ordinary Product Owner
confirmation. **OPR-5.3 requires an actual Product Owner decision** —
structurally identical in shape to OPR-2.5's own path through COMM-I4 →
COMM-I4A: assess, name the smallest bounded correction, then let the
Product Owner decide whether to authorize it before any code changes.
Once resolved, the remaining OPR-6.x/OPR-7.x Requirements (Multimodal/
CAMEL capabilities and Testing/Commissioning/Close-Out) are the final
tranche completing all 34.
