# Conversational Apprenticeship / Project-Aware Operational Agent (CLAUDE-POSTCAMEL-CA1)

**Status: CA1 FOUNDATION ESTABLISHED — FURTHER CONVERSATIONAL
APPRENTICESHIP REQUIRED.** Authorized in parallel with, not instead of,
the broader Workbench evolution, against the exact baseline
WB1-CLOSE established: stateless per-turn model calls, no system-role
behavioral contract, no bounded conversation continuity, narrow project
context, no ambient view awareness, very limited action invocation, and
a hardcoded "I didn't recognize an action" dead end with no concrete
next step. This tranche implements the smallest safe, bounded,
evidence-based slice of that gap, per the governing prompt's own
Concept-to-Implementation Rule (Section 0): items already authorized,
evidenced, safe, reversible, and deliverable without materially
expanding the tranche were implemented, not merely reported as
possible.

---

## A. Verified starting state

`HEAD == origin/main == 9b4457a5e0b9fff1d088e4f2047539942dafb0ab`
confirmed directly before this stage began; working tree clean except
the pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture.

## B. Conversational baseline confirmed

Read directly from `services/conversation_interpreter.py` and
`services/project_qa.py` before any change: deterministic keyword
trigger recognition throughout (the module's own stated design, not
loosened here); exactly two real model-call paths existed
(`_handle_investigate_requirement`, `_handle_project_question`), both
policy-gated through the same `_evaluate_external_ai_policy` resolver;
`answer_project_question`'s single `client.messages.create(...)` call
carried no `system=` parameter and no conversation history at all; the
final fallback for anything unmatched was a fixed prose string with no
structured next step.

## C. Concept-to-Implementation decisions made during CA1

Per Section 0's own instruction, each in-scope, evidenced, safe item
was implemented rather than only reported:

- **Behavioral contract (Section 6)** — implemented as a real
  `system=` parameter on the one real Project Q&A call.
- **Bounded multi-turn continuity (Section 5)** — implemented as a
  last-6-message window, project/case-isolated.
- **Project Orientation (Section 4)** — implemented as a fully
  deterministic (no model call) handler, sparse vs. established.
- **Contextual Next-Step Offering (Section 9), real chips** —
  implemented: `ConversationMessage.next_steps`, real navigation links
  only, never model-generated prose.
- **Better failure behavior (Section 23)** — implemented narrowly: the
  final "unrecognized" fallback now names orientation as an option and
  offers a real "Open Files" link.
- **A real routing bug found and fixed, not merely reported**:
  `quick_start`'s own Case-vs-project-level branch (`_looks_like_project_question`
  only) had no path for an orientation request — "orient me" would have
  silently created a brand-new Case titled "orient me," the exact
  failure mode CLAUDE-P40-B already fixed for plain questions. Fixed by
  adding the same `_looks_like_orientation_request` check to that one
  branch condition.

Explicitly **not** pursued as full implementations this stage, per
Section 0's own boundary list and the "no unrelated expansion" section:
full Glass Engine, full Delegation object/architecture, ambient
current-view/selection awareness beyond the pre-existing explicit
anchor mechanism, a general approved-action dispatcher beyond
navigation links, biometrics/voice, external communications. Each is
classified below (Sections K, R, S) rather than silently dropped.

## D. Behavioral-contract implementation

`services/project_qa.py`'s new `BEHAVIORAL_CONTRACT` constant — one
centralized system-role instruction, not duplicated per call site —
passed as `system=BEHAVIORAL_CONTRACT` in the one real
`client.messages.create(...)` call. Covers: answer only from given
evidence; say when evidence is insufficient; distinguish fact from
interpretation; recent history is continuity only, never Project truth
(Section 19); the agent may suggest but never itself create a governed
Requirement/Finding/Task/Decision (Section 3, human authority); never
claim an application capability that doesn't exist; never reveal
private step-by-step reasoning; respond only in the requested JSON
schema. `PROJECT_QA_PROMPT_VERSION` bumped `p38a` → `ca1a` (a real,
bump-on-meaningful-change marker, matching this module's own existing
discipline). **Classification: IMPLEMENTED.**

## E. Multi-turn continuity implementation

`_handle_project_question` (now accepting `case`) selects the exact
conversation thread the new reply will itself join — `case["conversation"]`
when a Case is open, `workspace.project_conversation` otherwise — takes
every prior message except the just-persisted current one (passed
separately as `question`), and passes it to `answer_project_question`
as `recent_history`. `_build_prompt` renders up to the last **6**
messages (`_MAX_RECENT_HISTORY_MESSAGES`), each capped at 300
characters, explicitly framed in the prompt text as "for conversational
continuity only, NOT additional project evidence... not guaranteed
correct." No token-count limit is enforced (message-count bounding
only); system/tool messages don't exist in this schema (only
`human`/`system` roles), so none are excluded/summarized beyond the
6-message cap itself.

**Live-verified against the real commissioning specimen, genuinely
through the live Anthropic API (not mocked):** asked "orient me" then
"What did I just ask you?" in the same Project Conversation — the
second, real model response correctly answered *"Your most recent
question, just before this one, was 'orient me'."* — direct proof the
bounded window reaches the real model call. **Live-verified isolation**
at the unit level (`test_recent_history_never_crosses_projects`): a
second project's prompt never contains the first project's question or
answer text. **Classification: IMPLEMENTED**, bounded by message count
only (not by token/character budget beyond the per-message 300-char
cap) — a token-budget refinement is named as future work, not built
here.

## F. Project-orientation behavior

`services/conversation_interpreter.py`'s new `_handle_project_orientation`
— fully deterministic, no model call, so it works identically whether
or not `ANTHROPIC_API_KEY` is configured or the external-AI policy
permits transmission (neither applies, since nothing is transmitted).
Recognizes a bounded phrase set (`_ORIENTATION_PHRASES`: "orient me",
"what's here", "what do I have", "give me an overview", "where do I
start", etc.), checked before the generic project-question branch so
these phrasings don't route to a real, billed model call for something
that isn't evidence-specific. Sparse (`≤2` active Sources **and** zero
governed Requirements) vs. established is a stated, honest heuristic —
never a claim of understanding Project maturity. Sparse reply names the
real Source count and offers "Open Files" only (the one real,
distinctly-existing view); established reply names real Source/
Requirement counts and offers Open Files/Requirements/Overview.
**Live-verified against two genuinely different real projects**: the
commissioning specimen (4 Sources, 34 Requirements) returned *"This
Project has 4 registered source(s) and 34 governed Requirement(s) on
record..."*; "Test 2" (1 Source, 0 Requirements) returned *"I see one
registered project source. I can inspect it, help you map its
contents, suggest a Project structure around it (advisory only -
nothing physical is created or moved), or leave it exactly as it
is..."* — matching the governing prompt's own sparse-example wording.
**Classification: IMPLEMENTED.**

## G. Current-view/selection awareness

**NOT ACHIEVED this stage — boundary reason stated, not silently
dropped.** The pre-existing explicit "Discuss this X" anchor mechanism
(unchanged) already satisfies Section 8's own preference ("explicit,
traceable context over hidden inference") for the one case it covers.
Ambient current-Display-view awareness would require adding a hidden
field to three separate composer call sites (`quick_start`,
`post_message`, `discuss_object`) and threading it through
`_run_conversation_turn` into the prompt — judged, under Section 0's
own "without materially expanding the tranche" test, to be a
comparatively large cross-cutting change relative to this stage's
other bounded items. Named for a future tranche, not built here.

## H. Project-grounding improvements

**Not expanded this stage.** `_handle_project_question`'s existing
grounding (candidate/governed Requirements, milestones, filename,
display title) is unchanged; the only addition is the bounded recent-
history window (Section E), which is continuity, not additional
Project evidence, and is stated as such in both the prompt and the
system contract. No vector database, no new ingestion, no full-document
grounding claim — none was in scope and none was added.

## I. Contextual next-step mechanism

`InterpretationResult.next_steps` (new) and `ConversationMessage.next_steps`
(new, `Optional`/defaulted so old saved JSON deserializes unchanged) —
a small, deterministic, server-computed `[{"label": ..., "view": ...}]`
list, `view` always an existing Display view name. Rendered via a new
`macros.next_step_offers` macro as real `<a href="?view=...">` links, on
the most recent message only, in both the case-scoped and project-level
conversation loops. **Never model-generated** — every next_steps value
in this codebase is assigned by Python code, never parsed from model
output, matching Section 10's own "structured action envelopes, not
arbitrary model prose." Attached to: orientation replies (Section F);
the "not covered" Project Q&A dead end (offers "Open Requirements");
the final "unrecognized" fallback (offers "Open Files"). Free-form
typing remains available regardless in every case.
**Classification: IMPLEMENTED**, scoped to navigation-only offers (no
"Delegate to…", no action beyond viewing, matching Section 9's own "do
not offer actions that do not exist").

## J. Approved action vocabulary/dispatcher

**PARTIALLY IMPLEMENTED.** The next-step links (Section I) are
themselves a real, bounded, auditable action vocabulary — but scoped to
exactly one action type: navigate to an existing, already-permission-
checked Display view (`workspace.show_workspace`, unchanged route,
unchanged authorization). The fuller vocabulary Section 10 named
(focus/open a specific Requirement or Finding by id, show a specific
Source, start an Investigation from a specific object) was **not**
built as a new dispatcher this stage — each of those already has its
own existing, working mechanism reachable through deterministic keyword
recognition (`_handle_show_evidence`, the "Start an Investigation from
this" button, "Discuss this X" apertures) or direct UI navigation;
building a second, structured envelope mechanism duplicating them was
judged out of this stage's smallest-slice scope. No unrestricted
tool-use loop was built or considered.

## K. Sparse-Project walkthrough

Builder-operated, live, against the real "Test 2" project (1 registered
Source, 0 governed Requirements, starting from a fresh sign-in):
"orient me" correctly returned the sparse-path reply and a working
"Open Files" link; the project was never treated as defective. This is
development evidence only, not OPR-7.2 representative-user evidence.

## L. Established-Project walkthrough

Builder-operated, live, against the real ARCHIOSK commissioning
specimen (4 registered Sources, 34 governed Requirements): "orient me"
correctly returned the established-path reply with real Open Files/
Requirements/Overview links; a follow-up "What did I just ask you?"
correctly answered from the real, bounded conversation history via a
genuine (non-mocked) Anthropic API call, proving continuity end-to-end,
not only at the unit level. This is development evidence only, not
OPR-7.2 representative-user evidence.

## M. Better failure behavior

The final "unrecognized" fallback (`case is None`, no anchor, no
recognized pattern) now names "orient me" as a real option and carries
a real "Open Files" next-step link, rather than prose alone. Every
other existing fallback/dead-end reply (`analyze_failed`,
`investigation_unavailable`, `investigation_policy_denied`,
`project_qa_policy_denied`, the `discussion_contribution` reply inside
an open Case) is unchanged — improving all of them was judged beyond
this stage's smallest-slice scope; the two touched
(`project_qa_unavailable`, `unrecognized`) were chosen because they are
the two genuine project-level dead ends a first-time user is most
likely to hit.

## N. Security/provider-boundary verification

`_evaluate_external_ai_policy`'s own gate is unchanged and still the
sole authority before either real model call — confirmed by reading
the call sites directly, not merely assumed. The new orientation
handler makes **no** external call at all, so it is unaffected by (and
does not need) that gate — stated explicitly as a real property, not
merely an oversight. No new field sent to the model carries anything
beyond what was already sent, plus the bounded recent-history window,
which is drawn from this codebase's own already-governed
`ConversationMessage` records (nothing newly exposed). Behavior remains
provider-neutral at the application layer — `BEHAVIORAL_CONTRACT` and
`recent_history` are plain data/strings passed to the existing
Anthropic transport call, not tied to any vendor-specific mechanism;
no Sovereign AI abstraction was built or needed for this.

## O. Conversation-memory vs. Project-truth safeguards

`BEHAVIORAL_CONTRACT` states directly that recent history (including
the model's own prior reply) is never to be treated as newly-
established Project truth, and that the agent may suggest but never
itself create a governed Requirement/Finding/Task/Decision. No code
path introduced by this stage writes a governed record from
conversation content beyond what already existed (the pre-existing
`_handle_correction`/`_handle_analyze`/investigation paths, all
unchanged). Orientation and next-step offers are read-only by
construction — they only ever navigate or describe existing state.

## P. Semantic findings

Carried forward unchanged: File/Document/Source; Documents/Files;
Archive; Trust; Open/Establish; the "Eye"/"Terminal Eye" collision.
**No new semantic collision found this stage** — "Project Orientation"
is a new but non-colliding term (it names a genuinely new, narrow
capability, not a rename of an existing one).

## Q. Latent-regression findings

Carried forward unchanged: `record_relationship`'s missing
cross-project guard; the two near-identical Source-revision routes;
Documents/Files redundancy; the META-T01 click-reachability regression
evidence. **Checked specifically per this stage's own Section 30
instruction** whether the new conversational context paths bypass
Project isolation, permission checks, human authority, or Source
provenance: confirmed they do not — `recent_history` is drawn from the
exact same `case`/`workspace` object already scoped and permission-
checked by `_load_workspace_or_404` before `interpret_message` is ever
reached; orientation reads only `CaseWorkspaceStore.active_sources`/
`workspace.requirements`, the same already-scoped workspace object; no
new route, no new permission surface. **No new latent regression
found.**

## R. Glass Engine implementation/foundation status

**NOT IMPLEMENTED — remains a future capability, per Section 17's own
explicit instruction not to build it merely to appear complete.**
`InvestigationStep` (`services/case_workspace.py`, pre-existing) is
real, evidenced architectural foundation — "one observable, auditable
unit of investigation work... deliberately never the model's raw
reasoning tokens" — but rendering it as a visible, collapsible
operational trace with truthful Pause/Stop/Skip/Redirect semantics (or
their honest absence) would require new template/route work this
stage's own bounded item list did not include without risking scope
expansion beyond the smallest safe slice already delivered. No fake
Pause/Stop/Skip/Redirect controls were built.

## S. Steps/Tasks/Investigations distinction

Confirmed by direct reading, not assumed: `Task` (durable, persisted,
open/completed, deliberately no assignee/delegation fields — its own
docstring states this remains out of scope), `Investigation`/`Case`
(the existing bounded-inquiry object), and `InvestigationStep` (the
existing auditable Step unit) are already three genuinely distinct,
correctly-named objects — Section 14's own "rectify the names before
trusting the relationships" instruction is substantially already
satisfied by the existing domain model. **Delegation remains the one
concept with no dedicated object at all** — confirmed again this stage,
unchanged from WB1-CLOSE's own finding. No new canonical object was
created.

## T. Future-Prompt Watch

Carried forward: broader Workbench evolution; full Glass Engine; full
Delegation architecture; Conversational Operational Terminal
(tabs/splits); Presence & Re-entry/Daily Project Greeting; voice/
biometrics; Sovereign AI; Body of Knowledge; Bug Eye; Surface Trust;
genuine OPR-7.2 representative-user validation. **New this stage:**
ambient current-view/selection awareness (Section G) — classified
**NEW FUTURE-PROMPT CANDIDATE**, scoped and reasoned about but not
built; a token-budget refinement to bounded history (Section E) —
classified **BACK-BURNER ITEM**; a general structured action dispatcher
beyond navigation (Section J) — classified **EXISTING FUTURE
PROGRAMME, now partially scoped**.

## U. Affected OPR map

Directly, materially engaged by this stage's real code changes:
**OPR-5.1** (Source-aware reasoning — the behavioral contract and
bounded history both act on the one real reasoning path), **OPR-5.2**
(Evidence grounding — recent-history framing explicitly reinforces
evidence/continuity separation), **OPR-5.3** (Human authority — the
behavioral contract's own explicit "suggests, never creates" clause),
**OPR-5.4** (isolation — recent-history project/case isolation
directly verified). **OPR-4.4/4.5, OPR-6.1, OPR-7.1** are not evidenced
as materially touched by this stage's actual diff (no Investigation/
Finding/Decision object or AI-vs-human capability distinction changed)
and are **not** reopened. OPR-7.2 remains explicitly deferred, unopened
by this stage.

## V. Focused tests

`tests/test_ca1_conversational_apprenticeship.py` — 12 tests: orientation
phrase detection; sparse-project orientation (real source count, real
Open Files link, no surprise Case created, works regardless of API-key
presence); established-project orientation (differs from sparse, real
Requirements/Overview links); behavioral contract sent as `system=`;
bounded recent history included in a second real (mocked) call;
recent-history project isolation; unrecognized-fallback next-step and
orientation mention. All 12 pass.

## W. Full regression result

Targeted regression first (`test_project_qa.py`,
`test_conversation_apertures.py`, `test_requirement_investigation.py`,
`test_p40vw8qa_r6_quantitative_investigation.py`,
`test_project_access_control.py`, `test_security_enforcement.py`,
`test_p40vw7a_ui_reference_map.py`): 159 passed, 5 subtests. Full suite,
run genuinely fresh (started after all code/test changes were in place,
never trusted from an ambiguous prior run): **3012 passed, 0 failed, 65
subtests passed** (956.23s / 15m56s) — the 3000-test META-T01-RC1/WB1
baseline plus this stage's own 12 new tests, zero regressions anywhere
else in the suite.

## X. Live-provider/live-browser verification

Two full Builder-operated live-browser walkthroughs performed against
the real dev server (restarted cleanly via the `restart-app` procedure
immediately before), starting from sign-in: the sparse "Test 2" project
and the established ARCHIOSK commissioning specimen (Sections K, L
above). The established-project walkthrough's second turn
("What did I just ask you?") was answered by a **genuine, live,
non-mocked Anthropic API call** — direct, real-provider proof that
bounded continuity works end-to-end, not merely under test mocks. Both
walkthroughs are development evidence only, never counted as OPR-7.2
representative-user evidence.

## Y. Local :5000 runtime status and Product Owner review route

**Running**, restarted cleanly via the established `restart-app`
procedure (all prior `app.py` process-chain members killed, exactly one
fresh instance started) immediately before both live walkthroughs above
— confirmed via `curl` (`HTTP 200` on `/login`) and via the two live
walkthroughs themselves, which exercised the exact new code paths
(orientation, behavioral contract, bounded history, next-step links)
directly through the browser against this same running instance. It
represents this stage's own commit (recorded in Section Z once
committed). **Product Owner review route:** sign in, open any project's
Workspace, go to `?view=conversation` (or Overview → the Conversation
composer), and type `orient me` — or ask a question, then a follow-up
that only makes sense with the first question in mind (e.g. "what did I
just ask?") to see bounded continuity directly.

## Z. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded once this document
and the code/test changes are committed together.

## AA. Remaining conversational limitations

Stated plainly, per the governing prompt's own "current limitations"
instruction: still no tool-use/agentic loop (every action remains
deterministic keyword recognition); still no full-document grounding
(extracted evidence only); still no ambient current-view/selection
awareness beyond the explicit anchor mechanism; recent-history bounding
is message-count only, not token-budget aware; the approved-action
vocabulary is navigation-only, not the fuller focus/open/show set named
in Section 10; Glass Engine, Delegation, and voice/biometric entry
remain entirely unbuilt; the orientation sparse/established heuristic
is a stated, simple count-based rule, not a claim of real project-
maturity understanding.

## AB. Recommendation for the next lateral/linear development balance

This stage delivered real, tested, live-verified lateral (conversational
intelligence) progress while making zero changes to the linear
(Workbench) track, matching the Product Owner's own "in parallel with,
not instead of" framing. The smallest coherent next lateral step is
extending the same bounded, deterministic pattern already proven here
(orientation, next-step offers, behavioral contract) to one or two more
genuinely useful, low-risk surfaces (e.g., a Requirements-focused
orientation branch, or token-budget-aware history) rather than
attempting Glass Engine, Delegation, or ambient view-awareness in one
further leap — each of those remains real future work, now more
precisely scoped than before this stage began.

---

**Deliberately NOT done this stage:** full Glass Engine; full Delegation
object/architecture; biometrics; voice recognition/synthesis; external
communications/team integrations; broad Workbench redesign; new PDF/
spreadsheet/PPT engines; Bug Eye; Sovereign AI; PMBOK/Body-of-Knowledge
architecture; independent final commissioning; ambient current-view/
selection awareness beyond the pre-existing explicit anchor mechanism; a
general approved-action dispatcher beyond real navigation links;
declaring OPR-7.2 satisfied or beginning representative-user testing.
