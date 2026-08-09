# Conversational Context Completion / See Where I Am (CLAUDE-POSTCAMEL-CA1A)

**Status: CA1A CONTEXT COMPLETION ESTABLISHED — ARCHIOSK GO CAN SEE THE
PM'S IMMEDIATE WORKING CONTEXT.** Completes the three items CA1
deferred: ambient/current-view awareness, token-aware conversation
budgeting, and a fuller (still bounded) action dispatcher. Per the
governing prompt's own standing Concept-to-Implementation Rule, every
in-scope, evidenced, safe item was implemented rather than reported as
"architecturally supported." Two real regressions were found live
during this stage's own required walkthroughs and fixed before
closure, not merely noted.

---

## A. Starting commit/state

`HEAD == origin/main == edcd9dd1ab162fa15a103da6ae4703b7d7f9f51b`
(CA1's own commit) confirmed directly before this stage began; working
tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture.

## B. Composer/context-route audit

Confirmed by direct reading, not assumed: there is exactly **one**
composer `<form>` in the entire Workspace DOM (`macros.conversation_dock`,
per its own docstring — "exactly one composer in the Workspace DOM,"
CLAUDE-P40-E1). "Three composer routes" (CA1's own language) means
three different POST *targets* the same one form can submit to
(`quick_start`, `post_message`, `discuss_object`), not three separate
UI paths. `show_workspace` already computes real, per-project-validated
current-state variables on every render — `directory_view` (validated
against `STABLE_DIRECTORY_KINDS`) and `selected_source` (validated
against `workspace.sources`, `None` for any stale/foreign id) — the
exact real "current UI context" Section 2 asked for already existed
server-side; it simply never reached the composer or the interpreter.
A fourth `_run_conversation_turn` call site was also found
(`start_investigation_from_aperture`, the "Start an Investigation from
this" escalation) — relevant to Section F below.

## C. Context-envelope architecture

One small, reusable envelope on the ONE shared composer — not three
separate ad hoc mechanisms, per Section 2's own instruction. Two hidden
fields (`current_view`, `selected_source_id`) added to
`conversation_dock`'s markup, populated from the same already-validated
`directory_view`/`selected_source` template variables `show_workspace`
already computes. Threaded through all three composer routes into
`_run_conversation_turn`, into `interpret_message`, and re-validated a
**second** time server-side there (`_KNOWN_CURRENT_VIEWS` allowlist;
a real per-workspace Source lookup) before ever being trusted — a
client could tamper with the hidden field value between render and
submit, so the render-time validation alone is not sufficient.
Deliberately kept as two plain fields, not a new class hierarchy or
plugin framework (Section 15's own "do not overengineer" instruction).

## D. Current-view awareness implementation

**IMPLEMENTED.** `current_view` is threaded end-to-end and consumed in
`_handle_project_question`'s `ui_context`, rendered as "Current Display
view: {view}" in the real model prompt, placed (Section 6's own
priority order) after Project identity and before the evidence
sections. Live-verified via a mocked-model test that an unknown/
fabricated view name never reaches the prompt at all.

## E. Selected-object awareness implementation

**IMPLEMENTED, bounded to Source.** A genuinely viewed Source
(`?source=`) is now real, validated context usable exactly like an
explicit anchor. Requirement/Finding "selection" continues to be
carried only by the pre-existing explicit anchor mechanism ("Discuss
this X") — there is no persistent `?requirement=`/`?finding=` URL-level
selection concept anywhere in this codebase to surface (confirmed by
direct grep), so nothing was fabricated to fill that gap. A new
deterministic (no model call) `_handle_contextual_reference` resolves
"tell me about this" / "what am I looking at" / "what does this mean" /
"show me the evidence for this" / "what should I do with this" / "what
can I do with this" / "where did this come from" against, in priority
order: an explicit anchor (any type: requirement/finding/source), else
a genuinely selected Source, else an honest "I don't have anything
specific selected right now" reply (Section 18) — never a guessed
referent, and never an unnecessary external-AI call for a question this
module already knows it cannot ground.

## F. Cross-project validation

**IMPLEMENTED and directly tested.** Every object lookup this stage
adds (`_resolve_anchor_object`, the `selected_source_id` lookup) is a
real, direct search against the *active* `workspace`'s own already-
project-scoped lists — a foreign/stale/deleted id simply resolves to
`None`, the same honest convention `_handle_investigate_requirement`'s
own pre-existing Requirement lookup already used. Tests confirm: a
Requirement id from a genuinely different Project is rejected with an
honest "no longer exists" reply and never leaks its own identifier; a
Source id from a different Project degrades to "nothing selected."

**One real regression found live and fixed, not merely a design
concern:** `start_investigation_from_aperture` (the "Start an
Investigation from this" escalation) already replayed a message's
`anchor` when re-running it inside a new Case, but never replayed
`selected_source_id` — because that field didn't exist on
`ConversationMessage` at all until this stage. Found during this
stage's own live Walkthrough A: escalating a Source-grounded reply
produced the honest-but-**wrong** "nothing selected" reply on replay,
purely because the field was never persisted. Fixed by adding
`ConversationMessage.selected_source_id` (optional/defaulted, so old
saved JSON deserializes unchanged) and threading it through
`add_message` and the escalation's own re-run call — verified both by
a new regression test and by re-running the exact live walkthrough
step that first exposed it.

## G. Token-aware history implementation

**IMPLEMENTED — replaces CA1's fixed 6-message cap.**
`_select_bounded_history` (`services/project_qa.py`) walks backwards
from the most recent message, keeping whole messages (each capped at
300 characters, never truncated mid-sentence to hit budget exactly)
until either a **2000-character total budget** or a **20-message count
cap** is reached, then restores chronological order — recent turns are
always favored; the *oldest* messages are dropped first. At least one
message is always kept even if it alone exceeds the budget, so a single
long turn never starves continuity entirely. No new tokenizer
dependency — a deterministic character-budget approximation, per the
governing prompt's own explicit preference. Fallback: identical to
CA1's own (empty history is simply omitted from the prompt). Tests
cover: budget respected, chronological order preserved, single
long-message edge case.

## H. Behavioral-contract updates

Updated only as needed (Section 12): the centralized
`BEHAVIORAL_CONTRACT` (`services/project_qa.py`) now states explicitly
that a "currently looking at" context, when given, is advisory only —
it may resolve what "this"/"it" refers to, but governed project
evidence always outranks it and it never authorizes an action on its
own. No duplication across call sites; still the one centralized
contract CA1 itself established.

## I. Action-dispatcher extensions

**PARTIALLY IMPLEMENTED, by deliberate reuse rather than new
machinery.** Rather than building a second, parallel action-execution
path, `_handle_contextual_reference` reuses the exact, already-tested,
already-rendered `needs_case:<message_id>` escalation ("Start an
Investigation from this") CA1's own `_handle_project_question` sibling
mechanisms already established — offered only when a real anchored/
selected object exists **and** no Case is already open
(`offer_investigation = case is None`). This directly preserves
Section 8's own named lesson (CA1's `quick_start`/"orient me" fix):
never a surprise Investigation from ambiguous language, always a real
button the PM must click. The fuller candidate vocabulary (a general
focus/open/show dispatcher independent of the existing keyword paths)
was not built as new machinery — audited and judged unnecessary, since
every candidate action already has a working, tested path
(`_handle_show_evidence`, the anchor mechanism itself, plain
navigation links).

## J. Contextual next-step refinement

**IMPLEMENTED.** Next-step offers are now context-shaped: a Requirement
referent offers "Open Requirements"; a Source referent offers "Open
Files"; a Finding referent offers no extra chip (Findings have no
dedicated stand-alone view to link to); the honest "nothing selected"
reply still offers "Open Files" as a concrete way to establish a real
referent. Free-form input remains available in every case.

## K. Sparse-Project walkthrough (Walkthrough A)

Builder-operated, live, against the real "Test 2" project (1 registered
Source, 0 Requirements), starting from sign-in, immediately after a
clean `restart-app`: navigated to the Source's own `?source=` URL,
asked "What can I do with this?" — got the correct, real,
Source-grounded reply with a working "Open Files" link and a working
"Start an Investigation from this" button. Followed that action:
**this is exactly where the selected_source_id-replay regression
(Section F) was first found live** — the escalated Investigation
initially lost the context and answered "nothing selected." Fixed, then
the identical walkthrough step re-run and confirmed correct on the
freshly restarted server. Development evidence only, not OPR-7.2
representative-user evidence.

## L. Established-Project walkthrough (Walkthrough B)

Builder-operated, live, against the real ARCHIOSK commissioning
specimen (34 Requirements, 4 Sources): clicked "Discuss this
Requirement" (anchoring to OPR-1.4), asked "Tell me about this" — got
*"You're looking at OPR-1.4 (status: active): ...Start an Investigation
below..."* Then asked "Show me the evidence for this" **without**
re-anchoring (anchor is correctly per-message, not sticky, by this
codebase's own existing design) — **this is exactly where the second
live regression (Section M) was first found**: the message silently
created a brand-new surprise Case instead of staying project-level.
Fixed, then the identical step re-run and confirmed correct: it now
stays in Project Conversation and gives the honest "nothing specific
selected" reply (correct, since no referent really was available for
that specific message). Asked "What should I do next?" with no active
referent — correctly fell back to real Project Orientation ("4
registered source(s), 34 governed Requirement(s)..."), also staying
project-level. Development evidence only, not OPR-7.2 evidence.

## M. Project-switch/isolation walkthrough (Walkthrough C)

Builder-operated, live: switched from the commissioning specimen
directly to "Test 2," asked "Tell me about this" again — got the
honest "nothing specific selected" reply, with **zero** trace of OPR-1.4
or any commissioning-specimen content. Confirms the anchor/selection
context genuinely does not survive a Project switch.

**Second real regression found live during this same walkthrough
sequence (Walkthrough B), fixed before closure:** `quick_start`'s own
Case-vs-project-level routing check (already once corrected by CA1 for
"orient me") had no awareness of this stage's own new
contextual-reference/what-next phrases. Typing "Show me the evidence
for this" into the *main* composer (no anchor attached) silently
created a brand-new Case titled "Show me the evidence for this" —
precisely the failure mode CA1's own Section 8 explicitly named as a
lesson to preserve. Fixed by extending `quick_start`'s routing
condition to also check `_looks_like_contextual_reference` and
`_looks_like_what_next`, mirroring the exact fix pattern CA1 already
used for orientation. Verified by two new regression tests and by
re-running the exact live step that exposed it on a freshly restarted
server.

## N. Error/ambiguity behavior

Tested directly: ambiguous "this" with no selection at all → honest,
non-guessed reply (Section 18). Stale/garbage `selected_source_id` →
degrades silently to no selection, never an error. Cross-project
Requirement/Source ids → rejected honestly, never accepted merely
because submitted while a different Project is active. No case where a
referent was hallucinated.

## O. Security/provider-boundary result

The pre-existing `_evaluate_external_ai_policy` gate is untouched and
still the sole authority before the one real model call this stage's
new code can reach (`_handle_project_question`, via `ui_context`). The
new deterministic contextual-reference/what-next/orientation handlers
make **no** external call at all, so the policy gate is structurally
irrelevant to them (not bypassed — never reached). Only a resolved
Source **name** (never a raw id, never full document content) is added
to the model prompt — no new class of data disclosed beyond what CA1
already sent.

## P. Conversation-memory vs Project-truth safeguard

Unchanged from CA1, reinforced by Section H's behavioral-contract
update: current-view/selection context is explicitly advisory, recent
history is explicitly continuity-only, and no code path this stage adds
writes a governed record from conversational content — the new
handlers are read-only by construction (they only describe existing
state or offer a real, explicit, PM-clicked escalation button).

## Q. Semantic findings

Carried forward unchanged: File/Document/Source; Documents/Files;
Archive; Trust; Open/Establish; the "Eye"/"Terminal Eye" collision. New
watch items this stage's own governing prompt asked for, checked
directly: **View vs. Selection** — confirmed genuinely distinct in this
codebase (`directory_view` vs. `selected_source`/anchor), no collision
found. **Context vs. Evidence** — this stage's own `BEHAVIORAL_CONTRACT`
update exists specifically to keep this distinction explicit to the
model; no code-level collision found. **Conversation memory vs. Project
memory** — already distinguished by CA1, reinforced, not re-litigated.
**Action vs. Suggestion** — the `needs_case:` reuse (Section I) is
itself evidence this distinction already holds structurally (an offer
is always a button, never automatic).

## R. Latent-regression findings

Carried forward unchanged: `record_relationship`'s missing cross-
project guard; the two near-identical Source-revision routes; legacy
hydration shims; Documents/Files redundancy; the META-T01
click-reachability regression. **Two new latent regressions were found
live this stage and both were fixed, not merely logged** — see Sections
F and M. Both are now covered by dedicated regression tests
(`test_investigation_escalation_replays_the_original_selected_source`,
`test_contextual_reference_phrase_in_main_composer_does_not_create_a_surprise_case`,
`test_what_next_phrase_in_main_composer_does_not_create_a_surprise_case`)
so a future change reintroducing either is caught automatically.

## S. Five-Mode Stewardship Check (CLAUDE-POLICY-5MS)

**Prototyper** — proved, via three genuinely live browser walkthroughs
(not merely unit tests), that a real PM-shaped interaction ("what can I
do with this," "tell me about this," "show me the evidence for this,"
"what should I do next") can be answered from real application state
without the PM repeating what they're looking at.

**Builder** — real, working, tested behavior: the context envelope
end-to-end; the deterministic contextual-reference handler; token-aware
history; two regression fixes discovered by the Builder's own live
testing, not left as findings.

**Sweeper** — confirmed there is exactly one composer in the DOM, not
three duplicate paths (Section B) — nothing to consolidate there, the
"three routes" framing was about POST targets, not UI duplication. Two
genuine pieces of route divergence *were* found and closed: the
escalation-replay gap (Section F) and the `quick_start` routing gap
(Section M) — both were real "hidden route divergence" / "inconsistent
action availability" per this stage's own Section 23 warning, not
hypothetical.

**Grower** — the context envelope and the `needs_case:` reuse pattern
are now real, generalizable mechanisms: any future handler needing
"what is the PM looking at" can reuse the same two fields rather than
inventing new plumbing; any future handler needing a safe
"offer-not-auto-start" Investigation escalation can reuse the same
`offer_investigation` guard pattern.

**Maintainer** — the two regression tests from Sections F/M must remain
durable (Section R). The cross-project rejection tests (Requirement and
Source) must remain durable as the one concrete proof this stage's new
context paths don't create isolation leakage.

## T. Future-Prompt Earmarks

Carried forward unchanged: full Glass Engine; Delegation First; broader
Workbench evolution; Presence & Re-entry/Daily Project Greeting; voice/
biometrics; Sovereign AI; Body of Knowledge; Bug Eye; Surface Trust;
OPR-7.2. **New candidate, per Section 16's own instruction:** the
`offer_investigation`/`needs_case:` reuse pattern this stage leaned on
is real, auditable action state directly relevant to a future Glass
Engine's own step-tracer — recorded as **Existing Future
Programme, relevant evidence found**, not built.

## U. Affected OPR map

Directly, materially engaged: **OPR-5.1** (source-aware reasoning — the
context envelope and contextual-reference handler both act on real
Source/Requirement state), **OPR-5.2** (evidence grounding — the
context-priority ordering in the prompt), **OPR-5.3** (human
authority — the "advisory, never authority" contract update, the
never-automatic Investigation offer), **OPR-5.4** (isolation — directly
tested this stage, twice, including the two regressions found and
fixed). **OPR-3.4** (Contextual Operations) is narrowly touched by the
context-envelope's UI-side wiring but not re-opened as a full
reassessment — no new operational pane was created. **OPR-4.4, OPR-6.1,
OPR-7.1, OPR-3.6** are not evidenced as materially touched by this
stage's actual diff and are **not** reopened. OPR-7.2 remains
explicitly deferred, unopened.

## V. Focused tests

`tests/test_ca1a_context_completion.py` — 20 tests: phrase detection;
token-aware-history budget/order/edge-case; anchored
Requirement/Finding "tell me about this"; cross-project anchor
rejection; no-surprise-Investigation-when-Case-open (direct
`interpret_message` test — `post_message` has no anchor form fields
today, so this exact combination has no live HTTP path, though the
guard is real production code); selected-Source context; stale/
cross-project `selected_source_id` rejection; ambiguous-no-selection
honesty; "what should I do next" (context-aware and orientation
fallback); current-view appearing in (and unknown values never
appearing in) the real prompt; the escalation-replay regression fix;
the two `quick_start` surprise-Case regression fixes. All 20 pass.

## W. Full regression result

Targeted regression first (CA1+CA1A test files, conversation/QA/
security/composer suites): 226 passed, 5 subtests, before the first
live walkthrough. Full suite, run genuinely fresh **after** both live-
found regressions were fixed and the server restarted on the final
code (never trusted from an earlier, now-stale run — two earlier
background runs were deliberately killed mid-flight for this exact
reason): **3032 passed, 0 failed, 65 subtests passed** (991.29s /
16m31s).

## X. Live-provider/browser verification

Three full Builder-operated live-browser walkthroughs against the real
dev server, each starting from sign-in, immediately after a clean
`restart-app`: Walkthrough A (sparse "Test 2," selected Source),
Walkthrough B (established commissioning specimen, anchored
Requirement, three-turn conversation), Walkthrough C (cross-project
isolation). Two genuine regressions were found live during these exact
walkthroughs (Sections F, M), fixed, and the identical walkthrough
steps re-run and reconfirmed correct on a freshly restarted server
before this stage was considered complete. All three walkthroughs are
development evidence only — never counted as OPR-7.2 representative-
user evidence.

## Y. Local :5000 status and exact review instructions

**Running now**, restarted cleanly via the established `restart-app`
procedure (all prior `app.py` process-chain members killed, exactly one
fresh instance started) after the final code fix, confirmed via `curl`
(`HTTP 200` on `/login`) and via the three live walkthroughs themselves,
which exercised every new code path directly through the browser
against this same running instance. It represents this stage's own
commit (recorded in Section Z). **Product Owner review route:** sign
in, open the ARCHIOSK commissioning specimen or "Test 2," go to
`?view=requirements` (or any Source), click "Discuss this Requirement"
(or open a Source directly), then ask "Tell me about this," "Show me
the evidence for this," or "What should I do next?" in the Conversation
composer to see real context resolution directly.

## Z. Commits / HEAD / origin/main / working tree

Committed as `da544881952008688ca27ad0f13dc415a737c081`
("CLAUDE-POSTCAMEL-CA1A: Conversational Context Completion"), covering
`services/case_workspace.py`, `services/project_qa.py`,
`services/conversation_interpreter.py`, `routes/workspace.py`,
`templates/_macros.html`, `templates/case_workspace.html`, this
document, `governance/STATUS.md`, and
`tests/test_ca1a_context_completion.py`. Pushed to `origin/main`
(`edcd9dd..da54488`). `HEAD == origin/main == da54488`. Working tree
clean afterward except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture.

## AA. Remaining conversational limitations

Stated plainly: Requirement/Finding "selection" still only exists via
the explicit anchor click, not a persistent URL-level selection the way
Source now has; the action dispatcher remains navigation-and-escalation
only (no direct focus/open-by-id dispatcher independent of existing
keyword paths); history bounding is a character-budget approximation,
not a real tokenizer; Glass Engine, Delegation, and voice/biometric
entry remain entirely unbuilt; the sparse/established orientation
heuristic (CA1's own) is unchanged, still a simple stated count rule.

## AB. Recommendation for next stage

The context-completion foundation (current-view + selection + bounded
history + context-aware next steps) is now real, tested, and
live-proven, including two regressions this stage's own testing
discipline caught before they could reach the Product Owner. The
smallest coherent next step is a further bounded pass extending real
Requirement/Finding selection (not just Source) to a persistent,
validated URL-level mechanism analogous to `?source=`, before
attempting Glass Engine or Delegation, which both depend on exactly
this kind of reliable "what is the PM looking at" foundation.

---

**Deliberately NOT done this stage:** full Glass Engine; Delegation
object/architecture; biometrics; voice recognition/synthesis; external
communications integrations; broad Workbench redesign; new document
engines; Bug Eye; Sovereign AI; PMBOK/Body-of-Knowledge architecture;
independent final commissioning; a general focus/open/show dispatcher
beyond real navigation and the reused `needs_case:` escalation;
declaring OPR-7.2 satisfied or beginning representative-user testing.
