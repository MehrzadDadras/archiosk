# First Developmental Commissioning Tranche (CLAUDE-POSTCAMEL-COMM-I3)

**Status: FIRST DEVELOPMENTAL COMMISSIONING TRANCHE COMPLETE — METHOD
CALIBRATED.** Authorized following COMM-I2's acceptance
(`governance/current/comm-i2-owner-baseline-and-developmental-commissioning.md`,
commit `1b9cbe8`). Commissions four calibration Requirements
(OPR-3.4, OPR-1.4, OPR-7.4, OPR-3.5) on both axes the doctrine
distinguishes — present-state conformance (real
`RequirementAdjudication` against the existing outcome vocabulary) and
developmental/formative conformance (the eleven-field, evidence-graded
method COMM-I2 recorded) — to prove the method before any decision to
scale it to the remaining 30.

---

## Governing-input check

`HEAD == origin/main == 1b9cbe8` confirmed before this stage began;
working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The real
commissioning specimen was unchanged from COMM-I2's closing state (34
governed Requirements, 0 adjudications, 13 unpromoted candidates) before
this stage's own adjudications were recorded.

## 1. Present-state adjudication (real product action, existing vocabulary only)

All four were adjudicated through the real `adjudicate_requirement`
route (`POST /projects/<id>/workspace/requirements/<id>/adjudicate`) —
the same control the live Requirements view exposes and that COMM-I2
confirmed renders but deliberately did not exercise. No new outcome
value was introduced; all four used `Satisfied`, the existing
`REQUIREMENT_ADJUDICATION_SATISFIED` constant. Live-verified afterward:
the Compliance rollup correctly re-computed to "4 SATISFIED, 30 NOT YET
ASSESSED" — the "unknown is not non-compliant" rule holding for the
remaining 30 exactly as designed.

### OPR-3.4 — Contextual Operations

**Outcome: Satisfied.** The running workspace renders the Lists
sidebar (Documents/Requirements/Investigations/RFI Correspondence/Work
Products/Tasks/Tags as independently-filed branches), the Toolbox pane,
and the primary Display simultaneously and adjacently, each maintaining
its own filing ontology — directly observed live during this and the
prior COMM-I2 walkthrough, not inferred.

### OPR-1.4 — Lifecycle Management

**Outcome: Satisfied.** `CaseWorkspaceStore.remove_source`/
`restore_source` provide recoverable retention/removal/restoration
(only `removed_at`/`removed_by`/`removal_reason` are set; id/file_path/
every dependent reference are left untouched, per the `Source`
dataclass's own docstring and the CLAUDE-P40-E2 comment on
`remove_source`). `routes/portal.py`'s admin-gated, confirm-gated
`delete_project` provides real permanent deletion, reusing "the
confirm-gate idiom already used for consequential actions" (its own
comment) rather than being a one-off mechanism. This is the Rev 0.2A-
bounded text — unsupported whole-project archive/restore was
deliberately removed from scope by the OPR's own Section A amendment,
and this adjudication is against that adopted text, not the superseded
Rev 0.2 wording.

### OPR-7.4 — Deficiency Close-Out

**Outcome: Satisfied**, with one honestly-recorded residual (see Part
7). The mandatory clause — "identifiable and traceable through
governed project records, shall receive a disposition, and shall be
closed or explicitly accepted" — is met by existing primitives:
`Requirement` + `RequirementAdjudication` (this very record) already
functions as the disposition/closure record at the Requirement's own
grain, with `Accepted Alternative`/`Not Applicable` serving as
explicit-acceptance outcomes; `Finding`/`Disposition` provide a second,
deeper route when a deficiency is investigated through an Investigation.
No `PunchListItem` or dedicated Punch List UI exists or was created —
matching the Rev 0.2A implementation-neutral text exactly.

### OPR-3.5 — Canonical Ownership

**Outcome: Satisfied.** Directly evidenced twice: by
`governance/STATUS.md`'s own ROOT-A1 record ("found the domain layer
already disciplined about canonical ownership" before that audit ever
examined it), and freshly, in this very tranche — the OPR Source added
in COMM-I2 is referenced by id from all 34 Requirement records and
rendered identically in the Documents Listing and every Requirement's
provenance, never duplicated.

## 2. Developmental / formative commissioning findings

Every field below is tagged **[DIRECT]** (directly evidenced),
**[INFER]** (reasonable inference), or **[NONE]** (insufficient
evidence) individually — not once per Requirement — so a reader can see
exactly which parts of each finding are load-bearing fact versus
judgment.

### OPR-3.4 — Contextual Operations

1. **Conception window [DIRECT]:** at the point ARCHIOSK's basic
   workspace shell (Listings/Local Navigator/Main Display/Contextual
   Operations) was first architected — every later feature depends on
   having somewhere to render.
2. **First actually recognized [DIRECT]:** the adopted OPR's own
   Section F Historical Evolution register states an early direction
   ("rigid four-chamber fixed layout") already existed — the general
   need was recognized very early, in some concrete (if imperfect) form.
3. **Relevant decision [DIRECT]:** the choice of a rigid four-chamber
   split as the first concrete realization of that recognized need.
4. **Earliest reasonably detectable deviation [INFER]:** the rigidity
   itself, once real feature growth (Cases, Requirements, RFI,
   Investigations, Work Products) needed more flexible/adjacent
   contextual panes than a fixed four-way split could economically
   support. No durable record pins the exact moment this became
   apparent.
5. **Prevention opportunity [INFER]:** designing the eventual
   decoupled "workspace grammar" from the outset might have avoided the
   intermediate rigid form, but no record establishes whether that was
   realistically foreseeable at the time.
6. **Downstream dependents [DIRECT]:** ROOT-A1's nine-branch canonical
   root, ROOT-I1's Requirements Listings promotion, every MM1–MM9
   Toolbox-mounted viewer, and this Requirements pane itself all sit on
   the corrected (post-four-chamber) form.
7. **Consequence of delayed recognition [NONE]:** a change occurred
   (Section F says so plainly); its cost, schedule impact, or rework
   magnitude is not recorded anywhere available to this session. Say
   so exactly rather than estimate.
8. **Classification: TIMELY CORRECTION [DIRECT for the fact of
   correction; INFER for its timeliness].** Section F records the
   four-chamber concept as "formally recorded as superseded," with the
   current baseline (OPR-3.1–3.4) governing — and every major dependent
   built on the corrected form, not the rigid one, which is consistent
   with (though does not conclusively prove) the correction preceding
   most real downstream investment.

**Ordinary-project/RFP translation:** *When does the client's own
navigation/workflow-adjacency expectation first need to be pinned down?*
Before any workspace layout is committed to, ask the Owner directly
whether investigations/comparisons/tracking must be visible **alongside**
primary content or may be sequential/modal — a cheap question early,
an expensive rebuild once dependent screens assume one answer.

### OPR-1.4 — Lifecycle Management

1. **Conception window [DIRECT]:** from the first persistent
   multi-project deployment — any such system needs an answer to
   create/retain/remove/restore/delete from day one.
2. **First actually recognized [DIRECT]:** the `removed_at`/
   `removed_by`/`removal_reason` recoverable-removal pattern recurs
   across multiple object types in `services/case_workspace.py`
   (Source, Folder, and others), and `delete_project`'s own comment
   states it reuses "the confirm-gate idiom **already used** for
   consequential actions" — both signal an established, pre-existing
   lifecycle-control discipline, not something built freshly for this
   Requirement.
3. **Relevant decision [DIRECT]:** the Rev 0.2A Section A amendment
   itself — bounding OPR-1.4 to the controls actually implemented
   (retention/removal/restoration-where-supported/permanent-deletion)
   rather than the Rev 0.2 draft's implied whole-project-container
   archive/restoration.
4. **Earliest reasonably detectable deviation [DIRECT]:** the
   deviation is in the **Rev 0.2 requirements draft**, not the product
   — it assumed a capability the product never built. Caught during
   COMM-A1's repository-grounded audit, before Rev 0.2A's adoption.
5. **Prevention opportunity [DIRECT]:** grounding the OPR draft
   against the real codebase before Rev 0.2 was first written (the
   same "read the real code before proposing" discipline this
   repository's own CLAUDE.md already requires of every session) would
   have caught this at first-draft time rather than at adoption-review
   time.
6. **Downstream dependents [DIRECT]:** none — no code, route, or
   governance record anywhere references whole-project archive/restore
   as implemented or planned, confirmed by direct repository search.
7. **Consequence of delayed recognition [DIRECT for "no implementation
   rework occurred"; NONE for drafting/review cost]:** because nothing
   was ever built to the incorrect assumption, the correction cost was
   contained to a documentation amendment (Section A). How much
   drafting/review time that amendment itself consumed is not recorded.
8. **Classification: TIMELY CORRECTION [DIRECT].** Caught and fixed
   before adoption, before any implementation existed that assumed the
   wrong capability.

**Ordinary-project/RFP translation:** *What lifecycle guarantee is the
Owner actually assuming when they write "archive" or "retain" into an
RFP?* Ask explicitly, before design: does "archive" mean recoverable
removal of individual records (real today), or a frozen whole-project
snapshot with later restoration (not built) — the two are easy to
conflate in prose and expensive to discover apart after commitments are
made downstream.

### OPR-7.4 — Deficiency Close-Out

1. **Conception window [DIRECT]:** once the system first had multiple
   governed objects (Requirement, Finding, Disposition) whose lifecycle
   could produce an unresolved state needing closure tracking — i.e.,
   from Foundation Batch K (`RequirementAdjudication`) onward.
2. **First actually recognized [DIRECT]:** `RequirementAdjudication`
   ("the human REQUIREMENT-level compliance record") and `Disposition`/
   `Finding` all existed well before this OPR was ever drafted — the
   underlying capability was recognized and built long before the Owner
   articulated OPR-7.4 in words.
3. **Relevant decision [DIRECT]:** the Section A amendment keeping
   OPR-7.4 implementation-neutral rather than mandating a new
   `PunchListItem`, directly informed by COMM-A1's own audit finding
   that no such object exists or is needed.
4. **Earliest reasonably detectable deviation [DIRECT]:** same shape
   as OPR-1.4 — the deviation was in the **Rev 0.2 draft** (implying a
   dedicated Punch List architecture), not the product. Caught by
   COMM-A1's audit before adoption.
5. **Prevention opportunity [DIRECT for the mechanism that worked;
   INFER for "could have applied even earlier"]:** the same
   repository-grounding discipline that caught this at COMM-A1 could,
   in principle, have applied at first-draft time.
6. **Downstream dependents [DIRECT]:** none built assuming a dedicated
   `PunchListItem` — confirmed absent by repeated direct code reading
   across ROOT-A1 through this stage.
7. **Consequence of delayed recognition [DIRECT]:** contained to a
   documentation amendment, no implementation rework, **plus one real,
   currently-live residual** (see Part 7 below) found independently
   during this tranche, not by the original OPR-drafting deviation.
8. **Classification: TIMELY CORRECTION for the OPR-drafting deviation
   [DIRECT]**; the separately-found assembled-view gap is not itself a
   deviation from the adopted text (Section E below explains why) and
   is tracked as a forward-looking observation, not a fifth
   classification value.

**Ordinary-project/RFP translation:** *What evidence should exist by
the time a deficiency is claimed closed?* Before design, confirm with
the Owner which existing record type (Adjudication vs. Finding+
Disposition vs. Task) is intended to carry closure evidence for their
specific deficiency-tracking expectation — assuming ARCHIOSK's flexible,
multi-primitive answer matches a client's mental model of "a punch
list" without checking is the actual risk, not any gap in the product.

### OPR-3.5 — Canonical Ownership

1. **Conception window [DIRECT]:** at the very first governed
   dataclass design (Foundation Batches) — canonical-ownership
   discipline is foundational and expensive to retrofit later.
2. **First actually recognized [DIRECT]:** `governance/STATUS.md`'s
   own ROOT-A1 record states the domain layer was **already**
   disciplined about canonical ownership before that audit examined it
   — recognized and built in from early design, not discovered as a
   gap and retrofitted.
3. **Relevant decision [DIRECT]:** the foundational choice to key
   every governed object by a stable `id` and reference it by id
   everywhere, never duplicating content across views.
4. **Earliest reasonably detectable deviation [DIRECT — absence]:** no
   deviation is recorded in any available record, from Foundation
   Batches through MM1–MM9 through ROOT/COMM — every extension is
   additive and id-referencing. Recorded as "none found," not as proof
   no deviation could ever exist.
5. **Prevention opportunity:** not applicable — no deviation to
   prevent.
6. **Downstream dependents [DIRECT]:** effectively the entire system —
   every Listings branch, cross-reference, and citation/evidence-sachet
   mechanism across MM1–MM9 depends on this discipline holding.
7. **Consequence of delayed recognition:** none — this is the
   positive contrast case.
8. **Classification: EARLY-AND-SOUND CONCEPTION [DIRECT].**

**Ordinary-project/RFP translation:** *Where will this client's own
canonical source of truth live, and does every downstream view merely
reference it?* A useful early-pursuit question precisely because
ARCHIOSK's own answer (id-based reference, never copy) generalizes
cleanly — worth stating to an Owner as a design commitment up front,
not discovered as a gap later the way OPR-3.4/1.4/7.4's Rev-0.2-era
issues were.

## 3. Cross-case lessons about conception windows and prevention

- **Two different deviation shapes appeared, and conflating them would
  be a mistake.** OPR-3.4's deviation was a genuine **implementation**
  correction (a shipped architectural direction was later superseded).
  OPR-1.4's and OPR-7.4's deviations were **requirements-drafting**
  corrections (the Rev 0.2 OPR text itself assumed capabilities the
  product never had) — the product was never wrong; an earlier draft of
  the Owner's own requirements was. Both are legitimately "conception
  window" findings, but only the first says anything about ARCHIOSK's
  own build history; the other two say something about how OPRs should
  be authored (grounded against real code before being drafted, which
  is exactly this repository's own standing CLAUDE.md discipline,
  independently re-derived here through commissioning).
- **The single positive case (OPR-3.5) is not evidence the method is
  biased toward finding problems.** It stands because a real, credible
  contrast is directly evidenced, not inserted for balance — worth
  noting since a four-item sample could otherwise look cherry-picked
  toward deficiency-finding.
- **Every "prevention opportunity" finding in this tranche points to
  the same mechanism**: ground a requirement or an architecture
  decision against the real, current repository state before finalizing
  it. This is not a new discovery — it is this repository's own
  existing operating discipline (CLAUDE.md's "ground it in the actual
  repository" rule) — but this tranche is the first time that discipline
  has been shown, with real evidence, to be the actual causal fix for
  every drafting-side deviation found so far.
- **Cost/schedule impact could not be quantified for any of the four
  Requirements.** This is itself a finding: this repository's durable
  records (commits, STATUS.md rows, governance documents) are excellent
  at recording *what* changed and *why*, but do not currently record
  effort/cost/schedule data at all — so no developmental finding in this
  method can ever produce a quantified cost figure from this repository
  alone, only a qualitative timely/late classification. Recorded
  honestly rather than estimated.

## 4. Ordinary-project/RFP prospective commissioning translation

See the per-Requirement "Ordinary-project/RFP translation" notes above.
Taken together, they show the developmental doctrine translates to a
consistent, lighter question for ordinary projects: **at each governed
Requirement, ask what decision it will constrain, by when, and what
would make a late discovery expensive** — asked once, briefly, at
pursuit/early-design time for a small, reviewer-flagged subset of
Requirements, not applied exhaustively. No new RFP-facing capability,
domain object, or UI was built or proposed to support this; it is a
question discipline for the reviewer, not a product feature.

## 5. Deficiencies / accepted alternatives / insufficient-evidence items

- **No unresolved developmental deficiency was found in this tranche.**
  Every deviation identified (OPR-3.4's implementation correction,
  OPR-1.4's and OPR-7.4's drafting corrections) was already resolved
  before or during this stage's own governing input (the adopted
  Rev 0.2A text).
- **One real, live, present-state residual was found** against
  OPR-7.4: no single assembled cross-Requirement "deficiency close-out"
  view exists yet, unlike the two proven precedents for exactly this
  shape of projection (`routes/workspace.py`'s `needs_attention_view`
  and ROOT-I2's `compliance_view`). This does **not** change the
  Satisfied adjudication (OPR-7.4's own text makes such a projection
  permissive — "may be projected" — not mandatory), and is not a
  deficiency against the Requirement itself.
- **Cost/schedule consequence fields are INSUFFICIENT EVIDENCE across
  all four Requirements** — recorded plainly in Part 2 and Part 3
  rather than estimated.

## 6. Product limitations encountered

- The real "+ Register a Requirement"/adjudication surface has no
  first-class field for a "developmental commissioning" record distinct
  from the ordinary adjudication `reasoning` free-text field used here
  — the eleven-field structure and evidence tags in this document exist
  only as a governance-document convention, not as product state. This
  was recorded here rather than worked around with a hidden data
  structure, per this stage's own explicit instruction.
- Confirmed again (as COMM-I2 already found): no per-Requirement field
  exists for the adopted OPR's richer schedule metadata (Priority,
  Verification Method, etc.) — unchanged residual, not reopened here.

## 7. OPR-7.4 self-referential deficiency-projection explanation

Per this stage's own Section 7 instruction, since a real (minor,
accepted) gap was found against exactly the Requirement under
examination, here is how it would be projected into close-out under the
adopted implementation-neutral OPR-7.4 model, using only existing
governed primitives — no `PunchListItem`, no dedicated UI:

1. **Identify:** the gap is already identifiable and traceable — it is
   recorded, by name, in this governance document and in the OPR-7.4
   `RequirementAdjudication`'s own `reasoning` text (Part 1 above),
   both durable, both citable.
2. **Disposition:** if a reviewer chose to track it as active work
   rather than merely as a documented observation, the ordinary route
   is a `Task` (`create_task`) anchored to a real Project Conversation
   passage referencing this residual, or an `Investigation`/`Finding`
   citing OPR-7.4 directly if deeper analysis were warranted. Neither
   was created this stage — Section 6's "do not fabricate product state
   merely to complete the report" was read as governing exactly this
   choice: an illustrative Task or Finding manufactured only to
   demonstrate the mechanism would itself be exactly that kind of
   fabricated state, so the mechanism is explained rather than staged.
3. **Close or explicitly accept:** because OPR-7.4's own text makes the
   assembled projection view permissive ("may"), the correct closure
   here is **explicit acceptance as a residual**, recorded in this
   document and in `governance/STATUS.md` — which is itself the
   `Requirement`+`RequirementAdjudication`+governance-record pattern
   OPR-7.4 describes, demonstrated on itself.

## 8. Tests and live-product verification

No application code was modified. All four adjudications were performed
through the real, unmodified `adjudicate_requirement` route via an
authenticated scripted HTTP session (same route, same CSRF-protected
form, same operator account a human reviewer's browser would use).
Live-browser-verified afterward, starting from sign-in: the Compliance
rollup correctly re-computed from "34 NOT YET ASSESSED" to "30 NOT YET
ASSESSED, 4 SATISFIED." Per this stage's own scope, the full regression
suite was not re-run; the last confirmed baseline (2969 passed, 0
failures) remains accurate, since nothing it covers has changed.

## Residuals carried forward

- OPR-7.4's assembled cross-Requirement deficiency view (Part 5/7) —
  explicitly accepted, not built.
- All COMM-A1/COMM-I1/COMM-I2 residuals not touched by this stage
  remain exactly as COMM-I2 left them.
- 30 of 34 Requirements remain unadjudicated and without conception-
  window analysis — this tranche was deliberately bounded to four.

## Recommendation

**FIRST DEVELOPMENTAL COMMISSIONING TRANCHE COMPLETE — METHOD
CALIBRATED.** The method produced real, differentiated findings across
four contrasting Requirements (one clean pass, two drafting-side
corrections, one implementation-side correction), each with individually
evidence-tagged claims, without inventing a new adjudication vocabulary,
a new domain object, or fabricated product state. It is calibrated
enough to scale to the remaining 30 Requirements in a future,
separately-authorized tranche — not automatically, per this stage's own
explicit stop-after-calibration instruction.
