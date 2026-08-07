# First Independent Expert Pilot — Operating Plan (CLAUDE-POSTCAMEL-PILOT-01)

**Status:** Documentation-only operating plan. No application code, deployment, account, or
telemetry changes were made to produce this document. Recorded following the accepted
`CLAUDE-POSTCAMEL-P01` pilot-readiness seal (`9b4b845`) and the GO recommendation in
`current/pilot-readiness-postcamel-p01.md`, which this plan operationalizes and does not restate.
DT1, Voice, Presentation Intelligence, and POSTCAMEL-P02 remain GO LATER/unimplemented and are
not touched by this plan — see Section Q for how pilot evidence may *later* inform them without
starting any of them now.

**Governing principle, preserved throughout:** *the pilot tests the accepted product baseline;
the product is not redesigned around the pilot before the pilot begins.* Nothing in this plan
proposes a code change. Every "fast-follow" item named below is explicitly deferred, not fixed.

---

## A. Current accepted pilot baseline

- `CLAUDE-POSTCAMEL-P01` closed and accepted at `9b4b845`; `HEAD == origin/main == 88857c2` at
  the time of this plan (two further documentation-only commits recorded the DT1 and Voice/
  Presentation architecture audits after P01's own acceptance — no application code has changed
  since `9b4b845`).
- Recommendation on record: **GO — ready for independent expert pilot**, no blockers (category A
  empty); three fast-follow items tracked (category B), none blocking.
- **Known fast-follow items** (from `current/pilot-readiness-postcamel-p01.md`, not re-audited
  here): (1) the MM7 formal Claim/"Investigate" trust engine (confidence score, contradiction
  detection, human review gate) is wired only to drawing/image evidence — PDF/spreadsheet evidence
  gets a real, working, simpler grounded-Q&A path instead, with no formal `Claim`/Finding produced;
  (2) MM3's bounded spreadsheet cell-edit has no UI trigger anywhere — the governed
  Design-Manager path (the MM8 risk-register Work Product) does work and was live-verified; (3)
  Requirements have no sidebar branch of their own, unlike every other first-class object.
- **Known deployment condition**: admin accounts see every project on a deployment (the
  pre-existing, deliberate `CLAUDE-P32` single-deployment boundary, not something any recent
  stage changed) — the pilot must not run on a server that also holds real client projects.
- **Supported project-creation formats**: PDF/DOCX/TXT/CSV/MD only; drawings, images, and native
  spreadsheets can only be *added to* an already-created project, never used to start one — already
  honestly disclosed in the upload page's own copy.
- **Design Manager workflow, live-verified during P01**: drawing Investigation → machine Finding
  (confidence-scored, `UNVERIFIED`) → human Reviewer Validation (Correct/Incorrect/Partial/Needs
  Evidence/Not Applicable + "Add Correction") → a governed `risk_register`-shaped Work Product
  with real sections → DOCX/XLSX export.
- **Grounded PDF/spreadsheet Q&A**: real (calls the configured Anthropic API), working, shows
  inline "Source grounding" citations, and abstains honestly when evidence doesn't cover a
  question ("not covered by this project's extracted evidence... treat this as a starting point,
  not a complete answer").
- **Auth/roles/isolation**: session-based login, `admin`/`read_only` roles, `can_access_project`
  deny-by-default for everyone except `admin` (which bypasses project-level isolation entirely —
  see the deployment condition above).

## B. Recommended first-user profile

The stated hypothesis — an experienced Design Manager or Design-Build pursuit/preconstruction
professional, RFP/RFQ-literate, comfortable with drawings/coordination/risk registers, with no
prior ARCHIOSK exposure — is the right profile and should not be adjusted. Two refinements:

- **Explicitly avoid a "friendly expert"** already sympathetic to the product or personally
  connected to its development — sympathy masks exactly the usability failures this pilot exists
  to surface (per Section G's own framing: don't optimize for a user who will forgive confusion).
- **Prefer someone who currently uses competing/adjacent tools daily** (Bluebeam, Excel risk
  registers, SharePoint, PowerPoint for pursuit response) — their instinctive reach for a familiar
  control (e.g., "where's the spreadsheet grid?") is itself valuable evidence, not noise to filter
  out.

No further candidate identification is possible from repository evidence alone — **selecting the
actual individual is a genuine product-owner decision**, not inferred here (see Section V).

## C. Recommended isolated environment

The safest practical environment, given the admin-visibility condition (A): a **separate
deployment or a separate, freshly-reset local instance** with:

- its own `REGISTRY_STORE_PATH` (this repository's flat-JSON registry root) containing only
  pilot-corpus projects — never pointed at the same registry directory used for development/
  testing/other real work;
- a single pilot account, created fresh, `admin` role (required to upload/create a project — see
  A's format note), with no other accounts sharing that deployment;
- a known, reproducible reset procedure (delete the pilot `REGISTRY_STORE_PATH` and re-seed from
  the corpus manifest, Section D) so the environment can be restored to a known-clean state before
  and, if needed, between sessions;
- clear separation from any development/admin work happening in parallel — the pilot session
  should not run on the same dev-server process a developer is also using to diagnose something
  else that day.

This is a recommendation, not an action — no deployment or environment change is made by this
plan (deployment changes are an explicit hard-stop for this prompt).

## D. Recommended pilot corpus

P01's own recommendation (a Coordination Report/specification-type PDF, one drawing, one small
risk-register spreadsheet) is confirmed correct and should not be expanded. This exact
combination:

- starts the project from **non-procurement text** (guards against RFP-overfitting, per P01's own
  Scenario C finding);
- is completable in one controlled session;
- naturally exercises document ingestion → Project Briefing → drawing Investigation → machine
  Finding → human review → risk-register Work Product → export, without requiring every Camel
  capability;
- is small enough to be entirely synthetic or explicitly authorized, non-confidential material —
  no real client data is needed or recommended for this first pilot (Section V).

**Do not add** a second document type, a second drawing, or a multi-project scenario for this
first pilot — P01's own scope discipline (`Section 3.6` of that document) argued against
over-scoping, and that reasoning still holds.

## E. Realistic pilot task/scenario

A single, professionally-framed objective, given verbally or in one short written paragraph, not
a click-by-click script:

> "You've been asked to review this early Design-Build project package — a coordination report, a
> drawing, and a preliminary risk register — and identify the most important coordination or
> requirement issues that should be raised before the next design review. Use ARCHIOSK to do
> that, and produce whatever record of your findings you think is useful to bring to that review."

This deliberately does not name any ARCHIOSK feature (Investigation, Finding, Work Product) —
whether the user discovers and correctly uses those mechanisms unprompted **is** the evidence.

## F. Zero-Founder intervention rules

**Allowed, by default:**
- initial login instructions (URL, username, password);
- the one-paragraph task objective (Section E) and confirmation the material is synthetic/
  authorized;
- resolving a genuine technical failure (page won't load, server error) — distinct from product
  confusion;
- answering, once asked, "is the system broken?" with a factual yes/no.

**Not allowed by default:** explaining where a feature lives; explaining ARCHIOSK terminology
(Investigation, Finding, Work Product, Source, registered/registration); coaching which document
to open first; suggesting what to investigate; rescuing the user from confusing navigation;
interpreting a system result for them.

**If intervention becomes necessary anyway** (the user is fully stuck, not merely slow): the
observer states plainly that this is an intervention, notes the exact trigger and exact wording
used, and logs it as a finding in its own right (Section H's "Friction" category, or Section I's
category A if the session cannot proceed at all without it) — an intervention is evidence of a
product gap, not a neutral act of customer support.

## G. Minimal onboarding

Limit onboarding strictly to: (1) a one-sentence description of what ARCHIOSK broadly does ("a
governed evidence and investigation workspace for construction project documents"); (2) login
credentials; (3) confirmation the project materials are synthetic/authorized, not a real client's
confidential data; (4) who to tell if completely, technically blocked (not product-confused,
technically blocked). **No feature walkthrough, no terminology glossary, no guided tour.** If the
pilot cannot proceed without more than this, that fact is itself the most important finding of the
session (log it under Section I, category A or B, not as a process failure).

## H. Observation framework

Observe and log against these categories (Orientation, Trust, Workflow, Design-Manager value,
Friction, Missing capability) exactly as outlined in the governing prompt — reproduced here as the
canonical observation checklist for the Observer Sheet (Section R):

- **Orientation**: does the user know where they are, what project/document is open, and how to
  move between documents/tools?
- **Trust**: does the user distinguish AI-generated from human-reviewed content? Do "Source
  grounding" and confidence/`UNVERIFIED` labels land as intended? Does an honest abstention read
  as protective or as "broken"?
- **Workflow**: can the user start, ingest, investigate, produce useful output, and recover from
  a mistake, all without founder help?
- **Design-Manager value**: does ARCHIOSK visibly reduce searching/re-reading, or surface a
  coordination issue the user would have found anyway at the same speed?
- **Friction**: hesitation, backtracking, misread controls, unclear terminology, moments requiring
  rescue.
- **Missing capability**: what does the user naturally attempt that ARCHIOSK cannot yet do?

## I. Finding classification

Adopt the four-tier scheme from the governing prompt directly — it is compatible with, and more
operationally granular than, P01's own A/B/C/D blocker classification (which classified *known,
already-identified* issues; this scheme classifies *newly observed* pilot findings in real time):

- **A — Pilot blocker**: the user cannot complete a core task or trust the result.
- **B — Serious friction/fast-follow**: the user proceeds, but with real confusion, a workaround,
  or lost confidence.
- **C — Improvement opportunity**: a useful refinement that doesn't materially obstruct the
  workflow.
- **D — Future capability request**: a valuable idea outside this pilot's accepted scope.

## J. Session structure

1. **Minimal introduction** (5–10 minutes, hard ceiling): Section G's onboarding plus Section E's
   task objective, nothing more.
2. **Independent work** (the primary session — no fixed time limit is recommended; let the user
   reach a natural stopping point, whether success, a real blocker, or their own sense of
   completion).
3. **Think-back interview** (immediately after, while memory is fresh): ask the user to narrate,
   unprompted, what they thought ARCHIOSK was doing, where they felt confident, where they didn't
   trust it, what was confusing, what felt useful, what they expected but couldn't do.
4. **Targeted follow-up** (only after free narration is exhausted): ask specifically about any
   accepted-baseline workflow the user did *not* naturally encounter (e.g., if they never opened
   the spreadsheet, ask what they'd expect there) — this is the only point at which the observer
   may name a feature the user didn't discover themselves, and only to ask about it, never to
   explain it.

## K. Feedback questions

Use the governing prompt's own list verbatim — it is well-constructed and avoids leading framing:
what did you think ARCHIOSK was for after the first few minutes; what felt immediately useful;
where did you hesitate; was there output you didn't trust, and what made you trust or distrust it;
what did you expect to do but couldn't; would this replace/complement/complicate your current
tools; at what point in a real pursuit would you actually use it; what would have to improve
before you'd use it on a real project; what should ARCHIOSK never do automatically. **Do not ask
about Voice, Presentation, DT1, or P02 by name** — if the user raises something adjacent to one of
those unprompted, record it under Section Q without steering the conversation toward it.

## L. Evidence/recording recommendations

Minimum sufficient record: timestamped observer notes against the Section H categories, screenshots
at key moments (not continuous), the user's own final work product/export if one is created, a
list of routes/screens visited (recoverable from server logs if needed, not a new instrumentation
requirement), and an explicit log of every founder intervention (Section F) with exact trigger and
wording. **Screen or audio recording is not assumed** — if used, it requires the user's explicit,
informed consent, obtained before the session starts, and that consent decision is not made by
this plan (Section V). No telemetry code is proposed or should be added for this pilot.

## M. Success criteria

**Mandatory** (the pilot cannot be called a PASS, per Section T, without all of these): the user
begins meaningful work without founder coaching beyond Section G; the user correctly identifies
which project/document is currently open at multiple points without asking; the user completes at
least one grounded investigation (a real question answered with visible evidence, whether via the
formal Investigation flow or the grounded Q&A path); no trust-breaking false-success event occurs
(Section N).

**Desirable, not mandatory**: the user creates or reviews at least one durable Work Product/
Finding; the user can articulate, unprompted, where a given answer's evidence came from; the user
independently identifies a credible professional use for the product without being asked to
imagine one.

## N. Failure/stop criteria

Stop the session (not merely log a finding) if: a security or privacy boundary is actually
breached (cross-project data exposure, an unauthorized user reaching pilot data); a project is
unrecoverably corrupted; the system repeatedly claims success for an action that did not actually
persist (a real false-success event, exactly the class of defect P01's own audit found and fixed
once already); evidence is presented as grounded/cited when it demonstrably is not; the core
ingestion/viewing path fails outright on the agreed corpus. **Ordinary confusion, hesitation, or
the user disliking a workflow is not a stop condition — it is the evidence the pilot exists to
produce.**

## O. Defect protocol

If something goes wrong mid-session: **observe → record → classify (Section I) → decide whether
the session can continue → do not fix live.** A live fix is authorized only if (a) the issue meets
the Section N stop criteria, (b) the product owner explicitly authorizes a repair in that moment,
and (c) the fix is treated exactly like any other change in this repository's own discipline —
exact reproduction preserved, affected commit identified, a minimal fix, a regression test, and
the pilot is understood to have been interrupted and require a fresh, re-baselined session
afterward, not a silent resume. Absent explicit real-time authorization, a defect is recorded and
addressed after the session, never during it — the pilot must not become an ad hoc development
session.

## P. Treatment of known fast-follow items

None of the three known fast-follow items (A) are fixed for this pilot. The chosen corpus (D)
naturally exercises two of them: the drawing will likely go through the full formal Investigation/
Finding path, while the PDF and spreadsheet will surface the simpler grounded-Q&A path instead —
**if the user notices and comments on that asymmetry unprompted, that reaction is itself
prioritization evidence** (does it register as confusing, or does the grounded-Q&A path already
feel sufficient for text/structured evidence?). The spreadsheet cell-edit gap is unlikely to
surface at all unless the user specifically tries to edit a cell in place rather than using the
risk-register Work Product — if they do try, record it as new, corpus-specific evidence rather
than assuming it confirms the existing finding.

## Q. How future programmes should receive pilot evidence

Pilot evidence may **inform prioritization of** DT1, Voice, Presentation Intelligence, and
POSTCAMEL-P02 later — it must never be used to **start** any of them now. Concretely: repeated
difficulty understanding hierarchy/layout is evidence for P02's eventual scope, not a reason to
open P02; strong, unprompted demand for a PowerPoint-shaped workflow is evidence for
Presentation's eventual priority, not a reason to begin it; repeated hands-busy/navigation
friction is evidence for Voice's eventual priority, not a reason to prototype it; a developer's
own inability to quickly diagnose a pilot-session failure is evidence for DT1's eventual case, not
a reason to build it. Record such observations under Section I's category D and cross-reference
the relevant `specified-unbuilt/` document by name — do not open a new work item against any of
them from this pilot alone.

## R. Required pilot artifacts

Five, not six — Pilot Corpus Manifest (D) and Pilot Brief (E+G) are naturally one short document,
since the corpus and the task framing are decided together and read together before the session:

1. **Pilot Brief & Corpus Manifest** — the one-paragraph task (E), the exact corpus file list and
   what each file synthetically represents (D), and the onboarding limit (G), combined into one
   page.
2. **Observer Sheet** — the Section H checklist plus a blank timestamped log and the Section F
   intervention log, used live during the session.
3. **Participant Feedback Sheet** — the Section K question list, used in Part 3/4 of the session.
4. **Finding Classification Log** — every observation from the Observer/Feedback sheets, sorted
   into Section I's A/B/C/D categories after the session.
5. **Post-Pilot Decision Record** — the Section T outcome, dated, with the evidence (from the
   Finding Classification Log) that supports it.

## S. Launch gate

The pilot should not begin until all of the following are true: the accepted commit is identified
and recorded (currently `9b4b845` for P01's own acceptance; `88857c2` for repository state at
plan time); the isolated environment (C) is confirmed, not merely planned; the corpus (D) is
loaded and has been opened once by a developer to confirm it ingests cleanly on that environment;
the pilot account has been tested end-to-end (login → create project → add documents) on that
same isolated environment; no unrelated/confidential project is visible from that account; the
reset procedure (C) has been exercised at least once; the Observer Sheet and Participant Feedback
Sheet (R) exist in final form; and the consent/recording decision (L) has been resolved one way or
the other, not left ambiguous.

## T. Post-pilot decision framework

- **PASS** — all Section M mandatory criteria met, no Section N stop event occurred: proceed to a
  second independent pilot or a limited real-project trial.
- **PASS WITH FAST FOLLOWS** — mandatory criteria met, but the Finding Classification Log contains
  category-B items with clear, bounded fixes: fix that bounded set, retest, continue.
- **HOLD** — core workflow/value was visible, but friction was severe enough that a further pilot
  without changes would likely repeat the same failure rather than produce new evidence: resolve
  the specific friction, then re-run this same plan, not a redesigned one.
- **NO-GO/REFRAME** — a Section N stop event occurred, or the Finding Classification Log shows the
  core proposition or workflow itself (not a fixable detail) does not hold up: return to
  architecture-level reassessment, not a patch.

No outcome is predetermined by this plan.

## U. Whether the pilot package was created now

**Yes.** The repository contains sufficient accepted evidence (`current/pilot-readiness-
postcamel-p01.md`, the P01 seal, and this session's own direct familiarity with the live product)
to produce this documentation-only operating plan now, without fabricating any genuine
product-owner choice. The five artifacts in Section R are described in full above; none required
information this repository doesn't already have.

## V. Product-owner decisions still required before launch

Not fabricated here, genuinely outstanding:

1. **Who** the actual first pilot participant is (Section B narrows the profile; it cannot name a
   person).
2. **Where** the isolated pilot environment actually runs (a separate physical/cloud deployment
   vs. a separate local instance) — an actual deployment decision, out of this prompt's scope.
3. **Whether** screen/audio recording will be used, and obtaining the resulting consent — a real
   consent decision (Section L).
4. **When** the pilot is scheduled, and who observes it.
5. Confirmation that the pilot corpus (D) will remain fully synthetic/authorized for this first
   pilot, per Section 22 of the governing prompt — no real client material is recommended, but the
   final confirmation is the product owner's.

## W. Confirmation

No application code was changed. No POSTCAMEL-P02, Voice, DT1, or Presentation Intelligence work
was started or touched. No deployment was created or modified. No pilot account was created. No
one was contacted. No confidential or real client project data was introduced. This document is
the entire output of this planning stage.
