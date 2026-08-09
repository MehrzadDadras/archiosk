# OPR-5.3 Human Authority Provenance Corrective Tranche (CLAUDE-POSTCAMEL-COMM-I5A)

**Status: OPR-5.3 HUMAN AUTHORITY PROVENANCE CORRECTED — PRODUCT OWNER
REASSESSMENT REQUIRED.** Authorized by the Product Owner's explicit
Do-Not-Accept decision on COMM-I5's OPR-5.3 finding
(`governance/current/comm-i5-governed-workflows-and-ai-assistance-commissioning.md`,
commit `bb6fb5f`): `RequirementAdjudication` is documented as
representing a human answer, yet the product could not distinguish a
human-authored adjudication from an agent-authored assessment — the
four COMM-I3 adjudications demonstrated this in real operation. This is
the second COMM-stage to change application code, after COMM-I4A.

> **Product Owner confirmation (2026-08-09):** the Product Owner
> reviewed this stage's own Section N agent reassessment and confirmed
> it unchanged — **OPR-5.3: Satisfied, developmental classification
> Late Correction** — the same genuine confirmation pattern already
> used for OPR-2.5 after COMM-I4A. No new `RequirementAdjudication` was
> persisted on the Product Owner's behalf; this confirmation is
> recorded in governance only, for the same honestly-reported reason
> COMM-I3B/COMM-I4A/COMM-I5A already established: this session cannot
> authenticate as the real Product Owner, so no product-level record
> can truthfully carry their personal attribution. The commissioning
> sequence does not proceed to the final OPR-6.x/OPR-7.x tranche
> automatically from this confirmation alone — that requires its own
> separate authorization, per this stage's own explicit instruction.

---

## A. Starting state

`HEAD == origin/main == bb6fb5f` confirmed before this stage began;
working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture. The
commissioning specimen was unchanged: 34 governed Requirements, 4
`RequirementAdjudication` records (all `Satisfied`, all attributed to
`archiosk_commissioning`, none carrying an `attribution` field — it did
not exist yet), 13 unpromoted candidates.

## B. Exact OPR-5.3 failure mechanism before correction

Two distinct, compounding gaps, both confirmed by direct code
inspection before writing any fix:

1. `RequirementAdjudication`'s own field set
   (`id`/`project_id`/`requirement_id`/`outcome`/`adjudicator`/
   `adjudicated_at`/`reasoning`/evidence lists) carried no
   content-provenance field of any kind, despite its own class
   docstring calling it "the first-class record of **a human's**
   answer." `adjudicator` records WHO/WHAT ACCOUNT performed the
   write, never whether the judgment was personally formed by a human.
2. **Worse than silent absence — an affirmatively false stored claim:**
   `record_requirement_adjudication`'s own governance-log call
   hardcoded `role="human"` **unconditionally**, for every adjudication
   ever recorded, regardless of who or what actually performed it. Every
   one of the four real COMM-I3 agent-entered adjudications produced a
   governance-log event that **literally asserted** `role="human"` — a
   provably false record, not merely an ambiguous one. This was found
   during this stage's own audit of the method, not previously
   identified by COMM-I3A/I3B/I5's own procedural analysis.

## C. Existing provenance pattern reused

Per this stage's own instruction, the three existing patterns COMM-I5
identified were audited before designing anything new:

- **`Finding`/`AnalysisRun`**: machine origin lives on `AnalysisRun`
  (`engine_name`/`engine_version`); human judgment lives separately on
  `ReviewerValidation`/`Disposition` (`reviewer` field). Confirms the
  general shape (separate the machine-origin record from the
  human-judgment record) but doesn't map directly onto
  `RequirementAdjudication`, which is itself the single object playing
  both roles depending on who submits it.
- **`WorkProduct.content_class`** (MM8): the closer, directly-reusable
  precedent — a closed vocabulary distinguishing content origin, with
  asymmetric, behaviorally-triggered transitions (editing an
  `ai_proposed` section auto-transitions it to `edited_ai_proposal`,
  never silently to `human_authored`; `accepted_by`/`accepted_at`
  record human acceptance without touching `content_class`). **This is
  the pattern extended here.**

No second adjudication truth store was created. `RequirementAdjudication`
remains the single, sole governed record of a Requirement's compliance
determination.

## D. Data-model correction

`services/case_workspace.py`:

- Three new constants: `ADJUDICATION_ATTRIBUTION_HUMAN_REVIEWED`,
  `ADJUDICATION_ATTRIBUTION_AGENT_ASSESSMENT` (the only two real INPUT
  choices, `KNOWN_ADJUDICATION_ATTRIBUTIONS`), and
  `ADJUDICATION_ATTRIBUTION_UNKNOWN_LEGACY` (a DERIVED label only,
  never a storable input value — mirroring
  `REQUIREMENT_ADJUDICATION_STATE_NOT_YET_ASSESSED`'s own
  derived-never-stored pattern).
- `RequirementAdjudication` gains `attribution: Optional[str] = None` —
  honest absence for every record created before this field existed,
  the same backward-compatible shape every prior additive field on this
  object already uses.
- `record_requirement_adjudication` gains an `attribution: Optional[str] = None`
  parameter, validated against the closed vocabulary when supplied
  (`CaseWorkspaceError` if not). **Deliberately Optional at this layer**
  — six pre-existing test files call this method directly without the
  new parameter; making it mandatory here would have broken every one
  of them for no product-facing benefit. The mandatory-choice policy is
  enforced one layer up, at the real product route (Section F).
- The `role="human"` hardcode in the governance-log call is replaced
  with `role=(attribution or "unspecified")` — honestly derived from
  what was actually declared, never asserted independently of it.

## E. Human-versus-agent provenance semantics

Preserved exactly as instructed — three concepts, never conflated:

- **Authenticated actor identity** — `adjudicator`, unchanged, still a
  real session username.
- **Content provenance** — the new `attribution` field: did this
  judgment originate from a human's own review, or an agent/automated
  assessment.
- **Decision authority** — governed separately by the existing
  admin/read_only role axis and project access control, entirely
  untouched by this correction.

## F. Server-side authority/integrity protection

**Audited, not assumed:** every pre-existing use of `_require_approval`
in this codebase (`apply`, `rfi_issue`, `source_revision`, the two
COMM-I4A additions) gates a **final commit of already-persisted
content** — none of them carry substantial new form data (outcome text,
reasoning) through the gate's own confirm-page round-trip. Literally
reusing that mechanism here would have introduced a genuine new data-loss
bug: `confirm_action.html`'s own confirm form carries only
`confirm=once/session/no`, never the original `outcome`/`reasoning`/
`attribution` fields, so a first-time-per-session adjudication would
silently lose its content on the confirmation click — a regression this
codebase's own design has always avoided by scoping the gate narrowly.
This is reported honestly rather than glossed over: reusing the literal
mechanism would have made this correction worse, not better, for the
single most common case (an ordinary human reviewer adjudicating).

**What was built instead, applying the same underlying philosophy**
(explicit, mandatory, self-declared, attributed to a real identity,
durably logged) without the round-trip defect: `adjudicate_requirement`
now requires an explicit `attribution` form value in the **same**
request as the outcome and reasoning — no silent default, no inferred
value. Submitting without it, or with any value outside the two real
closed choices, is rejected outright (`flash` + redirect, no record
created) — confirmed by test.

**Honest limitation, stated plainly rather than pretended away:** this
does **not** cryptographically prove a human typed the request. Today's
account model has no mechanism to establish that (no biometric signal,
no CAPTCHA, no separate human/agent account flag), and building one is
explicitly out of this tranche's scope ("no broad new identity provider
or account taxonomy unless separately authorized"). What this
correction achieves is real and non-trivial without pretending to
achieve more: a mandatory, explicit, first-person self-attestation
("I am a human reviewer, personally recording my own judgment"),
attributed to a real authenticated identity, permanently and honestly
logged — ending the prior silent/false default, not manufacturing
unfakeable proof that cannot exist without new infrastructure this
stage was not authorized to build.

## G. Treatment of the four COMM-I3 historical adjudications

**Not mutated.** Per ADR-032-R06's own append-only,
human-adjudication-as-evidence principle (already governing
outcome/reasoning/timestamp), backfilling a new field onto a historical
record after the fact was judged unsafe for the same reason overwriting
any other field would be — it would assert, retroactively, a fact about
what was true "now," not what was recorded "then."

**Instead:** a small, explicit, named constant —
`LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS`, the exact four real ids,
directly evidenced by `governance/current/comm-i3-first-developmental-commissioning-tranche.md`
(commit `678c692`) and this session's own contemporaneous script output
— plus a read-time-only resolver,
`resolve_requirement_adjudication_attribution(record)`: a record's own
`attribution` field wins if present; otherwise, only these four named
ids resolve to `agent_assessment`; anything else predating the field
resolves honestly to `unknown_legacy`, never defaulted to "human."
This is a truthful **projection**, not a second truth store — it adds
no new persisted data and duplicates no existing field; it only
changes what is *displayed* for four specific, already-known,
already-documented records.

## H. Ordinary human adjudication workflow

The real Adjudicate form (`templates/case_workspace.html`) gained two
required radio inputs, neither pre-checked, directly beneath the
existing outcome/reasoning fields: *"My own personal review"* and
*"An agent/automated assessment (not a personal human judgment)."* No
other field, button, or layout in the form changed. A human reviewer
using the ordinary product now cannot submit an adjudication without
making this choice explicit.

## I. UI/history representation

Both the single-adjudication line and the multi-entry "Adjudication
history" disclosure now show a small badge — "Human-reviewed" / "Agent
assessment" / "Unknown/legacy provenance" — resolved via the same
`resolve_requirement_adjudication_attribution` function, reusing the
existing `.review-state-badge` visual style already used for outcome
badges elsewhere on the same page. No new visual component, no general
UI modernization.

## J. Append-only/history preservation

Confirmed by test and by the underlying mechanism being entirely
unchanged: `latest_requirement_adjudication_for`'s own `records[-1]`
resolution means a human's own subsequent adjudication supersedes an
agent's **in effect** — becomes the current governing outcome — while
the agent's record remains permanently in the append-only history,
correctly labeled, never deleted or overwritten.

## K. Tests and full regression results

Eleven new focused tests
(`tests/test_comm_i5a_adjudication_attribution.py`) covering exactly
the required list: human-origin provenance, agent-origin provenance,
rejection of an invalid/self-declared-fiction attribution value at both
the store's closed-vocabulary check and the route's mandatory-choice
check, backward-compatible omission resolving to `unknown_legacy`,
correct resolution of the four named legacy ids without mutating them,
append-only history with human-supersedes-agent-in-effect resolution,
and UI representation (`Human-reviewed`/`Agent assessment` both found
in the real rendered page). All eleven pass.

**Real regressions found and fixed across two full-suite passes, not
silently reverted:** the first full run surfaced eight pre-existing
test failures; after fixing those, a second full run surfaced **seven
more** in different files this session's own narrower grep for direct
`record_requirement_adjudication(` callers had missed (these instead
called the real `/adjudicate` HTTP route by URL, not the store method
by name). All fifteen are legitimate and expected consequences of this
stage's own intentional behavior change, not bugs in the correction:

- `tests/test_foundation_batch_k.py`'s own
  `test_f_adjudication_with_finding_evidence` asserted the governance
  log's `role` equalled `"human"` — exactly the false hardcode this
  stage removed. Updated to assert the honest `"unspecified"` value for
  a call that supplies no `attribution`.
- Every other affected file (`test_requirement_promotion.py`,
  `test_root_i2_compliance_rollup.py`, `test_conversation_apertures.py`,
  `test_visual_pressure.py`, `test_requirement_evidence_workflow.py`,
  `test_workflow_integration.py`, `test_rfi_compliance_workflow.py`,
  `test_market_critical_golden_path.py` — eleven call sites across
  eight files in total) POSTs to the real `adjudicate_requirement`
  route without an `attribution` field — exactly what the new
  mandatory-choice enforcement now correctly rejects. Each updated to
  supply `attribution="human_reviewed"`, matching what an ordinary
  human reviewer's own browser session would actually submit.

Full suite after all fixes, run genuinely fresh (not the same process
re-read): **2989 passed, 0 failed, 65 subtests passed** (19m37s).

## L. Live verification

Performed against the real, persistent ARCHIOSK commissioning
specimen, starting from sign-in, after a full app-server restart to
load the corrected code: all 34 Requirements render correctly; the
four historical COMM-I3 records (OPR-1.4, OPR-3.4, OPR-3.5, OPR-7.4)
each now display **"Satisfied by archiosk_commissioning AGENT
ASSESSMENT — [original reasoning text, unchanged]"** — directly
confirming Section 12's own requirement: these four can no longer be
mistaken, within the corrected product representation, for personal
Product Owner or human judgments. Every un-adjudicated Requirement's
Adjudicate form shows the two required, unchecked attribution radios.
**No new adjudication was created during this verification** — read-only
inspection only, per this stage's own explicit instruction.

## M. Developmental commissioning classification after correction

**Late Correction [DIRECT].** The historical record, preserved rather
than erased:
- The original design correctly emphasized human authority
  conceptually — `RequirementAdjudication`'s own docstring has called
  it "a human's answer" since Foundation Batch K.
- Several other governed objects (`WorkProduct`, `Claim`, candidate-
  Requirement promotion) implemented that principle correctly from
  their own original design.
- `RequirementAdjudication` never carried equivalent content
  provenance — not a regression, a gap present since its own original
  implementation.
- COMM-I3 exposed the gap through real operation (four genuine,
  contemporaneously-authorized agent-entered adjudications).
- COMM-I5 formally identified it against OPR-5.3's own text, naming a
  candidate correction without implementing it.
- COMM-I5A (this stage) performed the corrective work, on explicit
  Product Owner authorization.

This is "Late," not "Timely," because — exactly like OPR-2.5's own
history — the gap existed from original implementation and was only
closed after being exposed in real operation and separately assessed,
not caught and fixed within one continuous audit-then-build sequence
the way OPR-3.1/OPR-4.3 were.

## N. Agent reassessment of OPR-5.3

**AGENT REASSESSMENT — PRODUCT OWNER REVIEW REQUIRED: Satisfied.**
`RequirementAdjudication` now carries real, closed-vocabulary
attribution, mandatory and explicit at the real product route, honestly
resolved (never defaulted to "human") for both new and legacy records,
visibly rendered in the ordinary UI, and verified live against the real
commissioning specimen. Combined with `WorkProduct`/`Claim`/candidate-
promotion's own pre-existing correct enforcement, OPR-5.3's text — "AI
features shall assist and structure but require explicit human review
and approval for all governed work products" — now has a real,
consistent, structural answer across every governed object it touches.
**No new `RequirementAdjudication` was persisted on the Product Owner's
behalf.**

## O. Residuals/limitations

- **Not solved, and not claimed to be solved:** the product still
  cannot cryptographically verify that a session claiming
  `human_reviewed` is genuinely a human rather than a sufficiently
  motivated script — stated honestly in Section F, not papered over.
  This would require new identity/authentication infrastructure,
  explicitly out of this tranche's scope.
- The four legacy COMM-I3 records depend on a small, hand-maintained
  reference constant (`LEGACY_AGENT_ATTRIBUTED_ADJUDICATION_IDS`)
  rather than a stored field — correct and honest for exactly these
  four, but not a pattern intended to scale to a large volume of
  pre-field legacy records; any future large-scale legacy backfill need
  would warrant its own separate design.
- No change was made to `Disposition`/`ReviewerValidation` or any other
  governed object — this correction is scoped exactly to
  `RequirementAdjudication`, per this stage's own explicit instruction
  not to modify unrelated objects merely for symmetry.

## P. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document, the code changes, and the test files are committed together.

## Q. Recommendation on Product Owner confirmation

Ready for reassessment from Partially Satisfied to Satisfied: the
provenance distinction is now real, mandatory, honestly resolved, and
live-verified against the real commissioning specimen, with the four
historical agent-entered records now unambiguously labeled rather than
indistinguishable from personal human judgments.

## R. Recommendation on proceeding to the final tranche

Not begun automatically. Once the Product Owner confirms or overrides
this reassessment, OPR-6.x (Multimodal/CAMEL Capabilities) and OPR-7.x
(Testing, Commissioning, and Close-Out) remain the final tranche
completing all 34 Requirements.
