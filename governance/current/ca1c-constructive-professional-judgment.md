# Constructive Professional Judgment / Self-Capability Awareness (CLAUDE-POSTCAMEL-CA1C)

**Status: CA1C CONSTRUCTIVE PROFESSIONAL RESPONSE ESTABLISHED —
ARCHIOSK GO CAN ADVISE, STRUCTURE, AND STATE ITS OWN CAPABILITIES
TRUTHFULLY.** A live Product Owner interaction found ARCHIOSK Go
answering an ordinary advice-seeking question too defensively, burying
a recommendation in prose, mixing Project evidence with knowledge of
ARCHIOSK's own capabilities, and never presenting a proposed structure
in reusable form. This tranche reproduces that exact scenario, fixes it
with real, tested, live-verified behavior, and separately performs a
bounded VOICE-1 prerequisite audit (no voice implementation).

---

## A. Verified starting state

`HEAD == origin/main == 2ac387e` (CA1B's own closing commit) confirmed
directly before this stage began; working tree clean except the
pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture.

## B. Live conversational weakness reproduced

Confirmed by direct reading before any fix: `_handle_project_question`
(the one general LLM-based path) had no behavioral distinction between
an evidence lookup and an advice-seeking question, and no mechanism at
all to answer a question about ARCHIOSK's own capabilities — such a
question would silently fall into the same Project-evidence-only prompt
and could only ever answer (truthfully, but uselessly) "not covered by
the evidence." Live-reproduced against the real commissioning specimen
after the fix (Section N) — see the exact before/after contrast there.

## C. Advice/evidence/capability classification architecture

Three real, distinct paths, not a single blended one:

- **Evidence question** — unchanged: `_handle_project_question`,
  grounded in Project evidence, honest "not covered" when unsupported.
- **Professional advice question** — the specific, highest-value case
  (organizing a Source) now has its own real, deterministic handler
  (`_handle_organize_advice`) that never reaches the model at all; the
  general case is handled by a `BEHAVIORAL_CONTRACT` update teaching
  the model itself the "recommend first" discipline.
- **Application-capability question** — a new deterministic handler
  (`_handle_capability_question`) answered entirely from
  `services/capability_registry.py`, never from Project evidence, by
  construction (the function receives only the matched `Capability`,
  nothing else).

All three are dispatched deterministically in `interpret_message`,
before the generic project-question fallback, so a capability or
organize question is never silently handed to the evidence-only model
call.

## D. Constructive-response implementation

**IMPLEMENTED.** `_handle_organize_advice`'s reply opens with a direct
recommendation ("Yes. Keep ... intact and organize it virtually
first...") before any explanation, matching Section 1's own governing
rhythm exactly. Live-verified against the real commissioning specimen's
own adopted RFP-style document (Section N).

## E. Concision behavior

**IMPLEMENTED for the deterministic path** (the organize/capability
replies are short, structured, and end with a real next step, never
restate the question or open with a disclaimer). **Taught, not
enforced, for the general LLM path** — `BEHAVIORAL_CONTRACT` now
explicitly asks for a direct answer, short material reasoning, and a
next step where useful; this is instruction, not a hard constraint, so
it is honestly classified **PARTIALLY IMPLEMENTED** for questions that
still reach the model.

## F. Vertical hierarchy formatting

**IMPLEMENTED.** `_handle_organize_advice` renders one group per line
(`"- {group}"`, joined by real `\n` characters). A new CSS rule
(`.conv-message-text { white-space: pre-wrap; }`) was required and
added — without it, the browser's default whitespace handling would
have silently collapsed every embedded newline into a single run-on
line, defeating the entire point of Section 6. `STATIC_VERSION` bumped
(69 → 70) in the same session, per this repository's own standing
`.env` rule.

## G. Subfolder proposal behavior

**NOT ACHIEVED as true nesting — honestly bounded to one level.** The
real, already-extracted candidate-Requirement category vocabulary
(`REQUIREMENT_CATEGORIES`) only supports grouping into a flat set of
named categories, not a genuine two-level hierarchy — inventing a
deeper structure (e.g. "Technical / Scope" containing fabricated
"Architectural/Structural/Mechanical/Electrical" children, the
governing prompt's own example) would have been exactly the "hardcoded
universal construction taxonomy" Section 6 explicitly forbids. The
proposal and the real "Create this structure" action both create only
the one level that is honestly grounded — Section 5's own "Capability
truthfulness" was judged to outrank Section 6's own nesting example.

## H. Original Source preservation behavior

**IMPLEMENTED and stated explicitly in every reply.** "Keep \"{source
name}\" intact" and "nothing physical is created or moved unless you
ask" appear in the recommendation itself, not as a separate disclaimer
paragraph. The real "Create this structure" action only ever calls
`store.create_folder` (Design-Builder Workspace) — confirmed by direct
reading that this mechanism cannot touch the Data Room or any Source
record at all (Section 8/21, Territory Before Ontology preserved).

## I. Application capability-awareness implementation

**IMPLEMENTED.** `services/capability_registry.py` — a small, flat,
non-sprawling dict of `Capability(key, status, description,
alternative)`, every entry checked directly against this repository's
own code before being written (e.g. `create_virtual_folder_structure`
confirmed real via `services/case_workspace.py`'s own `Folder` class
and `create_folder` method; `edit_spreadsheets`/`open_powerpoint`
confirmed unavailable via `upload.html`'s own accepted-formats list).
Deterministic keyword routing (`find_capability_by_phrase`) - checked
only when a self-referential phrase ("can you", "can archiosk", ...)
is ALSO present, so an ordinary project question that happens to start
"Can you tell me..." is never hijacked into a capability answer it
doesn't deserve (verified by test).

## J. Capability registry / source of truth

One file, one dict, twelve entries — deliberately not a sprawling
ontology (Section 4's own explicit instruction). Extending it is one
`Capability` entry plus one phrase mapping, never a schema change.
Every status (`implemented`/`partial`/`unavailable`/`future`) is a
real, checked classification, not the product's stated future vision.

## K. Physical folder-creation audit

**Classified precisely, per Section 17:**
- **Physical (operating-system) folder creation: NOT AVAILABLE.** No
  filesystem access to a Project's external Territory exists anywhere
  in this codebase — confirmed by direct search, not assumed.
- **Virtual (governed Design-Builder Workspace) folder creation:
  IMPLEMENTED, and was already implemented before this stage** —
  `services/case_workspace.py`'s own `Folder` class and
  `create_folder` method (real, hierarchical via `parent_folder_id`,
  recoverable delete, project-scoped, already had a working route). This
  stage's own real contribution was **the conversational bridge**
  (Section 17's own "if it is already safely supported and merely lacks
  the conversational bridge, implement that bridge") — a new route
  (`apply_organize_structure`) and a new template action, not a new
  capability.

## L. Virtual structure behavior

**IMPLEMENTED, using the existing mechanism, not a new ontology.** The
conversational proposal and the real creation action share one
function (`compute_organize_groups`) as their single source of truth,
so what is shown to the PM is always exactly what would be created —
no risk of the promise and the result silently diverging.

## M. Contextual next-action behavior

**IMPLEMENTED, capability-aware by construction.** "Create this
structure" is only ever rendered when `_handle_organize_advice` itself
determined a real Source and real grounded groups exist
(`organize_source_id` is `None` otherwise, per the existing `needs_case`
precedent's own "structured envelope, never model prose" discipline).
No unavailable action is ever offered as executable — the "Prepare
structure" vs. "Create this structure" distinction Section 14 names is
resolved by there being only one real, always-available action level
(virtual creation), so a lesser "Prepare" label was not needed to stay
truthful.

## N. Live RFP walkthrough

Builder-operated, live, against the real ARCHIOSK commissioning
specimen's own adopted OPR document
(`GEMINI-ARCHIOSK-RFP-02B_Rev0.2A_Product-Owner-Adoption-Copy.txt`),
starting from sign-in, immediately after a clean `restart-app`:

- Selected the Source via `?source=`.
- Asked, verbatim, **"Should I organize this into folders?"**
- Got: *"Yes. Keep \"GEMINI-ARCHIOSK-RFP-02B_Rev0.2A_Product-Owner-Adoption-Copy.txt\"
  intact and organize it virtually first - nothing physical is created
  or moved unless you ask.\n\nRecommended structure (based on what's
  actually extracted from this project so far):\n- Technical / Scope\n-
  Commercial / Legal\n- Appendices\n\nThis creates a real, governed
  Design-Builder Workspace structure, not a change to the original
  document."* — rendered with real vertical line breaks (confirmed
  visually, not just in raw text), no "only you can decide" opener, no
  category-error language.
- Clicked **"Create this structure"** — got a real, honest confirmation
  ("Created 3 folder(s): Technical / Scope, Commercial / Legal,
  Appendices.") and confirmed the real, governed Folder records now
  exist in Design-Builder Workspace.
- Asked, verbatim, **"Can you create physical folders on my
  computer?"** — got: *"No. ARCHIOSK has no mechanism to create real
  operating-system folders anywhere - it has no filesystem access to a
  Project's own external Territory at all. What I can do instead:
  ARCHIOSK can create real, governed Design-Builder Workspace folders
  (including nested ones) to organize a Project - a virtual
  organizational structure, never a physical filesystem folder, and
  never a change to the original Source or Data Room."* — no RFP
  content searched, no category error.

Development evidence only, not OPR-7.2 representative-user evidence.

## O. Project Evidence vs Application Capability tests

Directly tested and live-verified in both directions: a real capability
question never triggers a Project-evidence search (`test_folder_capability_answered_truthfully_no_rfp_search`,
`test_email_capability_says_no_without_searching_project`), and an
ordinary evidence question is confirmed NOT to be mis-classified as a
capability question (`test_ordinary_evidence_question_is_not_a_capability_question`).

## P. Semantic findings

Carried forward unchanged: File/Document/Source; Documents/Files;
Archive; Trust; Open/Establish; the "Eye"/"Terminal Eye" collision;
View vs. Selection; Context vs. Evidence; Conversation Memory vs.
Project Memory; Action vs. Suggestion; Selected vs. Active; Focused vs.
Governed; Current context vs. authoritative state. **New this stage,
each checked directly, no unresolved collision found:** **Advice vs.
Decision** — a recommendation is now clearly distinguished from a
governed decision by construction (the organize handler never writes
governed state; only the human's later, explicit click does).
**Recommendation vs. Requirement** — the organize reply never claims
the proposed grouping is a contractual requirement, only a
recommendation grounded in extracted categories. **Project Evidence vs.
Application Capability** — this stage's own central architectural
contribution (Section C). **Virtual Structure vs. Physical Folder** —
named explicitly in every organize reply, never left for the PM to
infer (Section 21's own explicit instruction). **Can vs. Should** — a
capability question ("can you") and an advice question ("should I")
are now routed to genuinely different handlers, never conflated.
**Suggest vs. Execute** — the "Create this structure" button remains a
button the PM must click; nothing is ever created merely by asking.

## Q. Latent-regression findings

Carried forward unchanged: `record_relationship`'s missing
cross-project guard; the two near-identical Source-revision routes;
legacy hydration shims; Documents/Files redundancy; the META-T01
click-reachability regression; CA1's own quick_start surprise-Case bug;
CA1A's two live-found regressions; CA1B's `log_out()` gap (all six
still covered by their own regression tests). **Watched specifically
per this stage's own Section 31, nothing new found:** the capability
registry could genuinely go stale as features change (e.g. if voice
input were later implemented, `voice_input`'s status would need
updating) — recorded as a real, standing maintenance obligation
(Section R), not a defect today; contextual next-step chips were
confirmed to still only ever offer real, existing views/actions;
`compute_organize_groups` being the single shared source of truth
(Section L) was specifically designed to prevent "proposal and result
diverge" from ever becoming a real latent regression.

## R. Five-Mode Stewardship Check (CLAUDE-POLICY-5MS)

**Prototyper** — proved, live, against the real commissioning
specimen's own adopted RFP-style document, that a genuinely
constructive, structured, capability-aware reply is possible from this
codebase's existing deterministic-handler discipline, without any new
document-analysis engine.

**Builder** — real, working, tested: the capability registry, the two
new deterministic handlers, the real `apply_organize_structure` route
(genuinely creates governed Folder records), the CSS fix that makes
vertical structure actually visible, the behavioral-contract update.

**Sweeper** — found and fixed the exact defensive-wording weakness the
Product Owner reported; found that physical vs. virtual folder
creation had never been named as two different capabilities anywhere
in this codebase (a real Project Evidence/Application Capability
confusion risk, not merely a hypothetical one); confirmed no duplicate
conversational resolver was created (Section C's three paths share the
same `interpret_message` dispatch, not a parallel system).

**Grower** — the capability registry itself is now a small, reusable
foundation: any future capability (Delegation, voice, a real physical-
storage connector) gets one registry entry, not a new mechanism; the
"shared computation, both consumed by the proposal and the real action"
pattern (`compute_organize_groups`) is reusable for any future
propose-then-execute conversational feature.

**Maintainer** — the capability registry must be updated whenever a
real capability's status changes (Section Q's own named risk); the
`compute_organize_groups` single-source-of-truth pattern and the
category-error test coverage (Section O) must remain durable.

## S. VOICE-1 prerequisite audit

**Confirmed by direct search: no browser microphone/speech API
(`getUserMedia`, `SpeechRecognition`, `MediaRecorder`) is referenced
anywhere in this codebase today** — this is a genuinely greenfield
audit, not an extension of existing code. Findings, per Section 25's
own checklist:

- **Browser microphone APIs**: `navigator.mediaDevices.getUserMedia`
  (audio capture) is the standard, broadly-supported mechanism; no
  browser-compatibility blocker for a modern Chromium/Firefox/Safari
  target.
- **Current environment support**: `getUserMedia` requires a "secure
  context" — HTTPS, or `localhost`/`127.0.0.1` as an explicit exception.
  This repository's local dev server (`http://127.0.0.1:5000`) already
  qualifies for local testing; a real production deployment would need
  HTTPS, which is outside this audit's own scope to confirm one way or
  the other for this specific deployment.
- **Permission UX**: the browser's own native microphone-permission
  prompt is unavoidable and appropriate (Push-to-Talk should trigger it
  on first use, not proactively).
- **Speech-to-text options**: two real architectural choices exist —
  (a) an external provider (e.g. a hosted speech API), or (b) an
  in-browser API (`window.SpeechRecognition`/`webkitSpeechRecognition`,
  Chromium-only, sends audio to a Google-operated backend under the
  hood despite being a "browser API"). Neither is assumed or selected
  by this audit (Section 25's own explicit "do not assume a provider").
- **Local vs. external processing**: a genuinely local (on-device,
  no-network) speech-to-text option was not identified as already
  available anywhere in this stack; any real implementation will
  involve *some* external processing boundary unless a local model is
  deliberately added later — a real, named tradeoff, not resolved here.
- **Security/privacy boundary**: audio capture must go through the SAME
  external-AI policy gate (`_evaluate_external_ai_policy`) any other
  external transmission in this codebase already goes through — no new,
  separate permission system should be built.
- **Consent**: distinct from the OS/browser microphone permission
  prompt - a PM-facing, in-app explanation of what happens to captured
  audio (Section 27's own privacy rule) would be a new, real UX
  requirement, not yet designed.
- **Temporary audio handling / persistence**: **not audited in code**
  because no code exists yet; the honest architectural default implied
  by Section 27 ("Push-to-Talk," "no ambient recording") is that raw
  audio should never be persisted beyond the single transcription
  round-trip - a requirement to design in, not something already true
  of any existing mechanism.
- **Provider dependency**: real, unavoidable for any non-trivial speech
  accuracy - not resolved by this audit.
- **Failure behavior**: no existing precedent to reuse directly, but
  this codebase's own established discipline (`ProjectQAResult.ran=False`
  with an honest `skipped_reason`, never a fabricated result) is a
  directly applicable pattern for "transcription failed / no permission
  / no network."
- **Accessibility implications**: Push-to-Talk is itself an
  accessibility-positive addition for some users (an alternative input
  channel) but must not become the ONLY way to invoke a capability -
  text must remain fully equivalent, per Section 26's own "two doors
  into the same Operational Agent."
- **Local `:5000` environment**: can safely support a *prototype*
  (secure-context exception for `127.0.0.1` already applies) - this is
  a real, positive finding, not a blocker.

## T. VOICE-1 security/privacy findings

No always-listening, wake-word, or ambient-recording mechanism exists
or was designed - the smallest true target (press-to-talk, release-to-
stop, transcript reviewable before sending) is directly compatible with
this codebase's own existing conversational architecture (text and
voice would both ultimately call the same `_run_conversation_turn`).
No biometric voice identification was considered or designed, per
Section 27's own explicit prohibition. The one real, unresolved
security question is provider choice — any external speech-to-text
provider is a new class of data leaving this application (raw audio,
not just extracted text), which must go through the existing external-
AI policy gate and be named explicitly to the PM, not silently added as
if equivalent to the existing text-only Anthropic call.

## U. VOICE-1 recommended smallest implementation boundary

Not decided by this audit (implementation is out of scope), but
named as the shape a future authorization should specify: press
microphone → capture audio locally in the browser → transcribe via a
named, explicitly-authorized provider (a real Product Owner decision,
not assumed) → populate the existing text composer (never auto-submit)
→ PM reviews/edits → submits through the exact same
`_run_conversation_turn` every text message already uses. No raw audio
persisted beyond the transcription round-trip unless a future stage
explicitly authorizes it.

**VOICE-1 REQUIRES PREREQUISITE CORRECTION BEFORE IMPLEMENTATION** —
specifically, a real Product Owner decision on speech-to-text provider
(none was assumed or selected by this audit, per its own explicit
instruction) and a designed (not yet designed) in-app consent/audio-
handling UX are both still outstanding. Neither is a large blocker, but
both are real, unresolved prerequisites, not merely formalities.

## V. Glass Engine readiness implications

Unaffected by this stage in either direction - CA1C's own real
contribution (capability truthfulness, constructive advice) is
orthogonal to Glass Engine's own step-visibility concern. CA1B's own
persistent-selection foundation remains the more directly relevant
enabling evidence, carried forward unchanged.

## W. Future Prompt Earmarks

Carried forward unchanged: VOICE-1 (now with a real, bounded
prerequisite audit on record); Presence & Re-entry/Daily Project
Greeting; Glass Engine; Delegation First; broader Workbench; Work on
Demand/Destination-Led Orchestration; New Paradigm/Native AI Work
Environment; Adaptive Attention/Gear Hierarchy; Project Memory; Bug
Eye; Body of Knowledge; Sovereign AI; Surface Trust; OPR-7.2.
**Newly preserved, per Section 32's own conditional instruction:**
Self-Capability Awareness / Capability Registry is judged to deserve
continued attention as the product grows (Section Q's own "could go
stale" risk), but NOT a larger dedicated future programme beyond
"keep the registry honest as capabilities change" - the minimal,
flat, non-sprawling shape already built is judged sufficient for the
foreseeable term, not merely a first phase of something bigger.

## X. Affected OPR map

Directly, materially engaged: **OPR-5.1** (source-aware reasoning - the
organize-advice handler is itself a new form of source-grounded
reasoning), **OPR-5.2** (evidence grounding - the explicit Project-
Evidence-vs-Capability distinction directly strengthens this),
**OPR-5.3** (human authority - "suggest, never execute without a real
click" is now doubly reinforced), **OPR-3.4** (Contextual Operations -
the new organize/capability handlers are new contextual behaviors).
**OPR-3.7** (Progressive Disclosure) is narrowly touched - the vertical
structure IS a disclosure-density improvement, but not reopened as a
full reassessment. **OPR-6.1, OPR-7.1** are not evidenced as materially
touched by this stage's actual diff and are **not** reopened. OPR-7.2
remains explicitly deferred, unopened.

## Y. Focused tests

`tests/test_ca1c_constructive_response.py` — 17 tests: capability-
registry status classification (implemented/unavailable/with-alternative/
unmatched); phrase detection (capability vs. organize vs. ordinary
evidence question); live capability-question conversation tests
(folder/physical-folder/email, confirming no Project-evidence search);
organize-advice (no-referent, recommendation-first + Source-preservation,
vertical-structure grounding, real Create-this-structure action and its
idempotency, insufficient-structure honesty); the shared
`compute_organize_groups` source-of-truth. All 17 pass.

## Z. Full regression result

Targeted regression first (CA1C + CA1B + CA1A + CA1 test files,
conversation/QA/security/isolation/UI-reference-map/composer suites):
203 passed, 5 subtests. Full suite, run genuinely fresh (started only
after all code/test changes were in place, including the CSS/
STATIC_VERSION fix, and after the server itself was restarted on the
final code): **3067 passed, 0 failed, 65 subtests passed** (1002.85s /
16m42s) — the 3050-test CA1B baseline plus this stage's own 17 new
tests, zero regressions anywhere else in the suite.

## AA. Live-browser/provider verification

One full Builder-operated live-browser walkthrough against the real
dev server (restarted cleanly via `restart-app` immediately before,
confirmed serving `main.css?v=70`), starting from sign-in: the exact
Section N scenario above, run against the real ARCHIOSK commissioning
specimen's own adopted RFP-style document - constructive recommendation
first, real vertical structure with genuine line breaks, a real
governed folder-creation action confirmed to actually create the
proposed folders, and a real, truthful capability-question answer with
no RFP search. Development evidence only, not OPR-7.2 representative-
user evidence.

## AB. Local :5000 status and exact Product Owner review instructions

**Running now**, restarted cleanly via the established `restart-app`
procedure immediately before the live walkthrough above, confirmed via
`curl` (`HTTP 200` on `/login`, `main.css?v=70` confirmed served).
Represents this stage's own commit (Section AC). **Product Owner review
route:** sign in, open the ARCHIOSK commissioning specimen, select the
adopted RFP Source (Files → the GEMINI-ARCHIOSK-RFP document, or a real
`?source=` link), and ask **"Should I organize this into folders?"** in
the Conversation composer. Expect: a direct "Yes" recommendation, a
real vertical list of groups, Source-preservation stated plainly, and a
real "Create this structure" button. Then ask **"Can you create
physical folders on my computer?"** and expect a truthful "No" with a
real alternative, never a reference to the RFP's own content.

## AC. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document and the code/test changes are committed together.

## AD. Remaining conversational limitations

Stated plainly: the organize-advice structure remains one level deep
(no genuine subfolder nesting - Section G's own honest boundary);
`RequirementsRegistry` is project-level, not per-Source, so the
organize proposal is grounded in "this Project's own extracted
material" rather than strictly "this specific Source's own content"
when a Project has more than one Source with extracted candidate
items; the general LLM-based advice path is taught concision and
directness but not mechanically enforced (Section E); the capability
registry covers twelve named capabilities, not an exhaustive list -
extending it remains cheap but is not automatic; VOICE-1 remains
entirely unimplemented, with real, named prerequisites still open.

## AE. Recommendation for next stage

The constructive-response and capability-truthfulness foundation is
now real, tested, and live-proven against the exact scenario that
motivated this tranche. VOICE-1 is not ready for implementation as the
immediate next stage - its own real prerequisites (a Product Owner
decision on speech-to-text provider, a designed consent/audio-handling
UX) should be resolved first, as their own small, bounded next step,
before either VOICE-1 or Glass Engine is attempted as a full tranche.

---

**Deliberately NOT done this stage:** voice/audio implementation;
biometrics; wake word; always-listening; a full folder-management
subsystem beyond the one real bridge to the existing `create_folder`;
full Glass Engine; Delegation; WB2; Bug Eye; Body of Knowledge;
Sovereign AI; Surface Trust redesign; independent/representative-user
testing; genuine multi-level subfolder nesting beyond what the real
extracted category data honestly supports; declaring OPR-7.2 satisfied.
