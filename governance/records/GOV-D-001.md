# GOV-D-001 — A bounded pre-project conversational tier for project establishment

- **GOVERNANCE ID:** GOV-D-001
- **TITLE:** Authorize model-based advisory conversation on the Establish a Project surface, without granting project-less Composer authority generally
- **TYPE:** Governance Decision Record
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude, under `CLAUDE-ESTABLISH-HELPDESK-01`
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-08-25
- **EFFECTIVE DATE:** on approval

Product Owner direction, 2026-08-25: *"Proceed toward the bounded pre-project
'registry help desk' tier for Establish a Project. The helper must become a real
Composer, not remain a keyword responder. Scope the minimum governance change
required to authorize that one project-less conversational use case, while
preserving the explicit project-registration commit boundary… Do not generalize
project-less Composer authority beyond what that job requires."*

## Decision question

> ARCHIOSK's supported project-creation path is document-led: founding document →
> project creation → project identity, role, operating environment, governance.
> The person establishing a project therefore has to make consequential setup
> decisions *before* any project exists to reason inside.
>
> `governance/STATUS.md` records the project-less orientation endpoint as
> deliberately **rule-based, non-`interpret_message`**, never opening a
> `CaseWorkspaceStore`, with the Context Envelope and Levels 4/5 of the authority
> ladder NOT AUTHORIZED. That decision is intact and was not made carelessly.
>
> Should a person establishing a project be able to hold a real, evidence-aware
> conversation before the project exists — and if so, what is the smallest
> authority that permits it without reopening project-less Composer authority in
> general?

## Scope

- **GOVERNS:** One surface only — the Establish a Project page's conversational
  helper, and the single backend path serving it. It authorizes (a) model-based
  reasoning in place of the keyword responder on that path, and (b) transient
  inspection of at most one user-supplied candidate founding document during that
  conversation.
- **OUT OF SCOPE:** The Home/orientation composer, which the Product Owner
  explicitly held separate and which remains rule-based and navigational.
  Also out of scope, and unchanged: Levels 4/5 of the authority ladder, the
  Shoulder Counsellor profile, the Context Envelope, ephemeral→governed-record
  promotion, the Engineering Observatory, general project-less Composer
  authority, and any widening of the External Intelligence Airlock.

## Options considered

| # | Option | Summary | Outcome |
|---|---|---|---|
| 1 | Bounded pre-project tier | One surface, real reasoning, transient document, no persistence, registration stays the commit | **CHOSEN** |
| 2 | Widen the orientation endpoint | Let every project-less surface reason with the model | rejected |
| 3 | Keep the keyword FAQ, rename it | Stop calling it a Composer; set expectations honestly | rejected |
| 4 | Defer until the project exists | Create the project first, then advise inside it with full authority | rejected |

## Decision

> The Establish a Project helper may reason with the real conversational spine
> rather than a keyword table, and may read one candidate founding document the
> user has already selected, **for the duration of a single turn and no longer**.
>
> It may advise on project naming, the user's declared position, the resulting
> operating environment, and how registration should proceed. It commits nothing.
> Creating the project, registering a Source, and every governed write remain
> exactly where they are today: behind the explicit project-creation controls.
>
> This authorizes one surface. It is not a general project-less Composer
> authority, and any second surface requires its own record.

## Rationale

Three constraints decided it, and they are narrower than they first appear.

**The ladder was never the obstacle.** Reading a document and advising is Level 3
(Suggest). It creates no record, mutates nothing, and needs no confirmation
mechanism, so Levels 4/5 stay untouched and unauthorized. What actually blocked
this were two specific prohibitions — "rule-based, non-`interpret_message`" and
the unauthorized Context Envelope — not the ladder.

**Neither blocked mechanism is needed.** `CaseWorkspaceStore` is not opened,
because there is no project to open; that clause of the original constraint is
preserved intact rather than waived. The Context Envelope resolves
narrowest-first through active selection → document → project → corpus, and none
of those exist pre-registration; what this surface needs is strictly smaller — a
question, and optionally one document's extracted text. So the Context Envelope
also stays unauthorized rather than being quietly adopted. The authorization is
therefore genuinely two clauses wide, not a general lifting.

**The evidence is provisional by construction.** The document is one the user has
*already chosen in the creation form* and has not yet submitted. It is read for
the turn and discarded. It is not a `Source`, carries no `evidence_class`, gets
no provenance record, and is never promoted — because promotion requires a
project container, which is precisely what does not exist yet. This is not a new
persistence model; it is the deliberate absence of one.

The alternative the Product Owner named directly — a reliably-submitted question
answered by a canned lookup — was rejected in their own words as *"a false
Composer"*, and that is the correct reading. `CLAUDE-ESTABLISH-COMPOSER-ENTER-01`
made the field submit reliably; it did not make it answer.

## Consequences

- **ACCEPTED COSTS:**
  - A project-less surface now reaches the model. That is a real widening of the
    attack and cost surface, and it means an unauthenticated-adjacent page
    (authenticated, but pre-project) can trigger model spend. Rate limiting and
    the existing external-AI policy gate must cover it explicitly, not by
    inheritance.
  - Advice given before a project exists cannot be grounded in project evidence,
    so it will sometimes be more generic than in-project advice. The surface must
    not present it as project truth.
  - A second conversational spine call site exists, which is one more place that
    must stay behind the external-AI gate.
  - The "no project-less model reasoning" line was previously simple to state and
    enforce. It is now conditional, and conditional rules erode faster.
- **ENABLED:** The document-led establishment path can actually be discussed
  before it is committed to — which is what the path was always for. The
  Establish helper stops being a Composer in appearance only.
- **FORECLOSED:** The clean claim that no project-less surface reasons with the
  model. Any future audit must now check *which* project-less surface.

## Rejected alternatives

**Option 2 — widen the orientation endpoint generally.** Rejected as
disproportionate: it would authorize model reasoning on every project-less
surface to solve a problem on one, and the Product Owner explicitly held Home
orientation separate. *Would be worth reconsidering if* a second project-less
surface develops a genuine evidence-aware need — at which point the right move
is still a per-surface record, not a blanket lift.

**Option 3 — keep the FAQ, rename it.** Honest, cheap, and genuinely defensible:
a labelled FAQ misleads nobody. Rejected because it solves the naming problem and
not the user's problem — the person establishing a project still cannot ask the
question they actually have. *Would be worth reconsidering if* the bounded tier
proves too costly or too hard to keep inside its boundary.

**Option 4 — create the project first, then advise.** Rejected because it inverts
the documented path and makes registration the *cheap* act rather than the
deliberate one, producing throwaway projects created solely to ask a question —
and project records are exactly what should not be created speculatively.
*Would be worth reconsidering if* a genuine draft/provisional project object is
ever introduced, which today it is not.

## Dependencies

- **RELATED GOVERNANCE:** `governance/STATUS.md` (Governed Voice / Conversational
  Presence); `specified-unbuilt/voice-conversational-presence.md`;
  `current/ca1-conversational-apprenticeship.md` Section AC;
  `specified-unbuilt/external-intelligence-airlock.md` (unchanged and not
  widened); `constitutional-invariants.md` #3 (provenance) — respected by not
  creating evidence at all.
- **STANDING CONTRACTS:** `CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT`.
- **REQUIRED IMPLEMENTATION ORDERS:** `CLAUDE-ESTABLISH-HELPDESK-01`.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** The Establish path creates no `Source`, no
  project, and no governance-log entry; the candidate document is never written to
  disk or into any workspace file; the external-AI policy gate is resolved before
  any model call on this path; and no second project-less surface acquires the
  same capability without its own `GOV-D-`.
- **TESTS / CHECKS / ORACLES:** `tests/test_establish_helpdesk_01.py`;
  `tests/test_composer_convergence_01.py` (surface registry and its recorded
  exceptions).

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Extending this tier to any other surface;
  persisting the candidate document or the conversation; allowing it to create or
  pre-create any project record; adopting the Context Envelope here; or any
  movement to Level 4/5.
- **AMENDMENT / SUPERSESSION RULE:** A new `GOV-D-` superseding this one, never an
  in-place edit.

## Lineage

- **SUPERSEDES:** None. This **narrows by exception** the scope of `STATUS.md`'s
  Governed Voice / Conversational Presence entry as it applies to one surface;
  every other clause of that entry — including "never opens a
  `CaseWorkspaceStore`" and the unauthorized Context Envelope — remains in force,
  here and everywhere.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** `GOV-P-003` (help without humiliation) governs how this
  surface speaks.

## Governance delta

`ADDITIVE`
