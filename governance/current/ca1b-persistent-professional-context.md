# Persistent Professional Context / Requirement & Finding Selection (CLAUDE-POSTCAMEL-CA1B)

**Status: CA1B PERSISTENT PROFESSIONAL CONTEXT ESTABLISHED —
REQUIREMENT AND FINDING SELECTION RELIABLE.** Closes CA1A's own named
limitation: Requirement and Finding selection were anchor-only and did
not persist as reliably as Source selection (which already had a real,
bookmarkable `?source=` convention). Per the governing prompt's own
Concept-to-Implementation Rule, every in-scope, evidenced, safe item
was implemented, not merely reported as possible — including a real,
found gap in `log_out()` closed before this stage's own closure.

---

## A. Verified starting state

`HEAD == origin/main == 99f6e85` (CA1A's own closing commit) confirmed
directly before this stage began; working tree clean except the
pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture.

## B. Existing Requirement/Finding selection audit

Confirmed by direct reading: Source already had a real, per-project-
validated, bookmarkable `?source=<id>` convention in `show_workspace`
("None for a stale/foreign id, never an error"). Requirement and
Finding had **no equivalent** — the only way either was ever "selected"
was the explicit, per-message "Discuss this X" anchor (never
persisted beyond that one message), or, for Finding specifically, the
pre-existing, narrower, Case-scoped `focused_finding:{project_id}`
session key (set only as a side effect of "Show me the evidence
supporting Finding N," used only for corrections within an open Case —
a genuinely different concept from "what the PM is generally working
with," kept separate rather than overloaded, per Section 18's own
"Focused vs Governed" watch item).

## C. Persistence mechanism chosen

**One unified, project-scoped session slot**:
`selected_object:{project_id}` → `{"anchor_type": ..., "anchor_id": ...}`
(the same shape as the pre-existing `Anchor` dataclass, so it can be
passed anywhere an anchor already is without a second shape). Chosen
over per-type keys specifically so a new explicit selection of any kind
naturally replaces whatever was there before (Section 6's own "Finding
B wins" requirement) without separate reconciliation logic. Set by two
real triggers: (1) visiting a real `?requirement=`/`?finding=`/`?source=`
URL (new query-param support added mirroring `?source=`'s own exact
validation pattern); (2) an anchor attached to the current conversation
message. Session-based, not a `CaseWorkspaceStore` field — a selection
is deliberately not Project truth (Section 17).

## D. Unified context-envelope changes

`interpret_message` gains `selected_object: Optional[dict]`. A new
`effective_referent = anchor if anchor is not None else selected_object`
is computed once, per Section 5's own precedence (explicit
current-message anchor > persisted selection > current-view/`?source=`
fallback already established by CA1A), and used only by the CA1A
contextual-reference layer (`_handle_contextual_reference`,
`_handle_what_should_i_do_next`) — the pre-existing, older, anchor-only
grammar (`needs_case`, `is_requirement_investigation_question`,
`anchor_acknowledged`) is deliberately **untouched**, exactly as
Section 12 required ("extend the existing mechanism," not build a
second one).

## E. Requirement selection behavior

**IMPLEMENTED.** `?requirement=<id>` resolves against
`workspace.requirements` only (real per-project lookup, `None` for
stale/foreign). Persists across ordinary navigation and conversation
round-trips. Live-verified (Walkthrough A): visited `?requirement=`,
asked "Tell me about this" (real reply naming the Requirement),
navigated to Files then back to Overview, asked "Show me the evidence
for this" with **no re-selection** — same Requirement context held.

## F. Finding selection behavior

**IMPLEMENTED, same discipline as Requirement.** `?finding=<id>`
resolves against `workspace.findings` only. No pre-existing UI
aperture exists for "Discuss this Finding" (confirmed by direct grep —
none was fabricated); the real, tested mechanism is the URL convention
itself, exactly mirroring Source's own precedent. Live-verified
(Walkthrough B): a real Finding created via the existing governed
`record_analysis` path, selected via `?finding=`, "What should I do
with this?" correctly answered with the Finding's own statement and a
real "Start an Investigation from this" offer.

## G. Context precedence rule

**Final rule, tested directly:** (1) an anchor attached to *this*
message — always wins, freshest and most explicit; (2) the persisted
`selected_object` session slot — whichever type/id was selected most
recently by anchor or by a real query-param visit; (3) `?source=` on
the current request, if the persisted slot is empty; (4) nothing —
honest "I don't have anything specific selected." Live-verified
(Walkthrough C): selecting Requirement A then Finding B, "Tell me about
this" correctly resolved to Finding B — a later explicit selection
always overrides an earlier one, never coexists.

## H. Clear-selection behavior

**Exact rules, per Section 9:**
- Clears on **explicit user action**: a new route,
  `POST /projects/<id>/workspace/context/clear`, pops the session key;
  a small "Clear" control in the new context indicator posts to it.
- Clears (degrades to nothing, without an explicit purge) whenever the
  persisted id **no longer resolves** — every read goes through
  `_resolve_anchor_object`'s real per-workspace lookup, so a deleted/
  foreign object never renders or answers as if it still existed.
- **Does NOT clear merely because the user submits a chat message** —
  confirmed by design and by test; a plain conversational turn with no
  anchor of its own leaves the persisted slot untouched.
- **Clears on sign-out** — a real gap found during this stage's own
  audit: `services/auth.py`'s `log_out()` previously popped only the
  three auth keys (`user_id`/`username`/`role`), leaving
  `selected_object:{project_id}`/`focused_finding:{project_id}`
  reachable by a **fresh sign-in in the same browser**, since the
  session cookie itself was never cleared. Fixed by having `log_out()`
  also pop every session key with either prefix.
- Does **not** clear merely because the Project changes — see Section I
  (isolation is by separate key, not by active clearing).

## I. Project-switch behavior

**Per-project session keys are independent by construction** — no
special-case clearing logic needed or added. Switching to a different
Project simply looks up a different, empty key; switching back restores
the original Project's own selection completely unchanged (not cleared,
not overwritten by the other Project's activity in between).
Live-verified (Walkthrough D) and directly tested
(`test_switching_back_restores_original_project_selection`,
`test_requirement_selection_never_leaks_across_projects`).

## J. Refresh/re-entry persistence boundary

**Exact boundary, checked directly, not assumed:**
- **Ordinary page refresh:** survives (Flask session cookie persists
  across requests) — live-verified and tested.
- **Route round-trip / view navigation:** survives — the entire point
  of this stage, live-verified in Walkthrough A.
- **Application restart:** survives, as long as `FLASK_SECRET_KEY`
  (from `.env`, confirmed stable, not regenerated per restart) doesn't
  change — checked directly in `config.py`, not assumed.
- **Sign-out/sign-in:** does **not** survive, as of this stage's own
  fix (Section H) — confirmed to have been a real gap before the fix,
  closed, and directly tested.
- **Not promoted to long-term Project Memory** — this remains ephemeral
  session state, never written to `CaseWorkspaceStore`/governed JSON.

## K. Conversational integration

**No second resolver was created.** The exact same
`_handle_contextual_reference`/`_handle_what_should_i_do_next`
functions CA1A introduced now simply receive a richer
`effective_referent` — their own internal resolution-by-type logic
(`_resolve_anchor_object`, already generic across
requirement/finding/source) needed no change at all. Context remains
explainable (the "Currently working with" indicator names it plainly),
project-scoped, validated (never trusted without a real lookup), and
non-authoritative (Section 17 — selection means only "the object the PM
is currently working with," never accepted/approved/adjudicated).

## L. Contextual next-step behavior

Requirement referent offers "Open Requirements"; Finding referent
offers no extra navigation chip (no dedicated stand-alone Finding view
exists to link to — not fabricated); both offer the reused
`needs_case:` "Start an Investigation from this" escalation when no
Case is already open. Only real, already-existing actions are ever
offered.

## M. Action-dispatcher changes

**None beyond what CA1A already established.** The one dispatcher
action (`needs_case:` reuse) already generalizes across
Requirement/Finding/Source without modification — no new action type
was needed or added this stage.

## N. Investigation-safety verification

**Directly tested, both directions.** A persisted selection alone (no
anchor on the current message) still correctly offers "Start an
Investigation from this" when no Case is open
(`test_persisted_selection_alone_still_offers_investigation_when_no_case_open`)
— and correctly does **not** offer it when a Case is already open
(`test_persisted_selection_does_not_offer_investigation_inside_an_open_case`,
reusing the exact `offer_investigation = case is None` guard CA1A
already built). No ambiguous pronoun or quick-start phrase creates a
surprise Investigation — the CA1/CA1A fixes for this remain untouched
and unaffected by this stage's own changes.

## O. Semantic findings

Carried forward unchanged: File/Document/Source; Documents/Files;
Archive; Trust; Open/Establish; the "Eye"/"Terminal Eye" collision;
View vs. Selection; Context vs. Evidence; Conversation Memory vs.
Project Memory; Action vs. Suggestion. **New this stage, checked
directly, no collision found:** Selected vs. Active — "selected" now
consistently means the session-scoped professional-context slot this
stage introduces, "active" continues to mean the open Case/Investigation
(`active_case`), genuinely distinct concepts, not renamed or merged.
**Focused vs. Governed** — `focused_finding:{project_id}` (narrow,
Case-scoped, pre-existing) vs. the new `selected_object:{project_id}`
(general, project-scoped) are real, intentionally-kept-separate
concepts, named honestly here rather than collapsed into one to appear
tidier. **Current context vs. authoritative state** — directly enforced
by Section 17's own discipline; no code path this stage adds treats a
selection as governed truth.

## P. Latent-regression findings

Carried forward unchanged: `record_relationship`'s missing cross-project
guard; the two near-identical Source-revision routes; legacy hydration
shims; Documents/Files redundancy; the META-T01 click-reachability
regression; CA1's own quick_start surprise-Case bug; CA1A's
Investigation-replay context-loss bug; CA1A's second surprise-Case bug
(all four preserved as developmental evidence, all four still covered
by their own regression tests). **One new, real regression found during
this stage's own audit (Section H) and fixed before closure:**
`log_out()`'s incomplete session-clearing — a stale
`selected_object`/`focused_finding` slot could otherwise be silently
inherited by a fresh sign-in in the same browser. Now covered by
`test_logout_clears_persisted_selection`. No new *conversational*
regression was found live during this stage's own four walkthroughs
(unlike CA1A, which found two) — the extension point CA1A itself left
(`selected_object` threading) integrated cleanly into the existing,
already-hardened dispatch order.

## Q. Glass Engine readiness implications

**Real enabling evidence, not built.** A reliable "the PM is currently
working with Requirement X / Finding Y" signal is exactly the
attachment point a future Glass Engine step-tracer would need to
associate operational steps with the object they concern (per this
stage's own Section 20 example: "these operational steps belong to this
selected Requirement/Investigation"). Recorded as **Existing Future
Programme, now with a concrete, tested foundation** — the visible
Glass Engine trace itself remains unbuilt, per this stage's own explicit
instruction not to build it merely to demonstrate the relationship.

## R. VOICE-1 readiness assessment

**Not ready to authorize as the very next stage, honestly assessed.**
Persistent professional context removes one real prerequisite gap (a
spoken "tell me about this" now has something stable to resolve
against, the same as a typed one) — but VOICE-1 introduces its own,
separate, unaudited surface (microphone capture, speech-to-text
provider boundary, a new input modality's own security/consent
questions) that this stage did not examine at all. The honest
statement: this stage removes a *context* blocker for voice, not a
*voice-specific* one; VOICE-1's own remaining prerequisites (provider
choice, consent UX, audio-boundary security) are untouched and would
need their own audit before authorization, not assumed satisfied by
this stage's work.

## S. Five-Mode Stewardship Check (CLAUDE-POLICY-5MS)

**Prototyper** — proved, via four genuinely live browser walkthroughs,
that Requirement and Finding selection can survive real navigation
round-trips the same way Source's already did, including the "later
selection wins" transition behavior.

**Builder** — real, working, tested: the unified session slot, the two
new query-param handlers, the clear route, the visibility indicator,
the `log_out()` fix.

**Sweeper** — confirmed no second conversational resolver was created
(Section K); found and fixed one real, previously-undetected gap
(`log_out()`'s incomplete session-clearing, Section H/P) — a genuine
piece of "hidden route divergence" between auth and session state that
this stage's own audit uncovered, not merely a theoretical risk.

**Grower** — the unified `selected_object` slot and its `{"anchor_type",
"anchor_id"}` shape are now a real, reusable foundation: any future
handler needing "what is the PM working with" reads the same one slot,
already validated, already precedence-ordered.

**Maintainer** — the four new regression-relevant tests (cross-project
Requirement/Finding rejection, logout-clears-selection, no-surprise-
Investigation-with-open-Case) must remain durable, alongside CA1/CA1A's
own three prior regression tests.

## T. Future Prompt Earmarks

Carried forward unchanged: Glass Engine; Delegation First; broader
Workbench evolution; Presence & Re-entry/Daily Project Greeting;
VOICE-1; face/voice recognition; Project Memory/re-entry briefing;
Sovereign AI; Body of Knowledge; Bug Eye; Surface Trust; Work on
Demand/Destination-Led Orchestration; New Paradigm/Native AI Work
Environment; OPR-7.2. No genuinely new candidate was found this stage
beyond what Sections Q/R already named as enabling evidence for
existing programmes.

## U. Affected OPR map

Directly, materially engaged: **OPR-3.4** (Contextual Operations — the
context envelope and selection mechanism are exactly this), **OPR-5.1**
(source-aware reasoning — extended to Requirement/Finding), **OPR-5.2**
(evidence grounding — unchanged priority ordering, now serving a richer
referent), **OPR-5.3** (human authority — Section 17's "selection is
not truth" discipline), **OPR-5.4** (isolation — directly tested,
including a genuine new fix). **OPR-3.6** (Persistence) is narrowly
touched — session-based, not `CaseWorkspaceStore`-based, so this is a
UI/interaction persistence question, not the governed-data persistence
OPR-3.6 itself concerns; not reopened as a full reassessment. **OPR-3.3,
OPR-4.4, OPR-6.1, OPR-7.1** are not evidenced as materially touched by
this stage's actual diff and are **not** reopened. OPR-7.2 remains
explicitly deferred, unopened.

## V. Focused tests

`tests/test_ca1b_persistent_context.py` — 18 tests: query-param
Requirement/Finding/Source selection and persistence; context-indicator
presence/absence/stale-degrade; explicit reselection overriding stale
selection (Finding-over-Requirement, Source-to-Requirement, fresh-
anchor-over-persisted); cross-project Requirement/Finding rejection
(both HTTP-level and direct interpreter-level); switching away and back
restores the original Project's own selection; plain-refresh
persistence; logout clearing persisted selection; no-surprise-
Investigation in both directions (offered/not-offered). All 18 pass.

## W. Full regression result

Targeted regression first (CA1B + CA1A + CA1 test files, conversation/
QA/isolation/UI-reference-map/composer suites): 186 passed, 5 subtests.
Full suite, run genuinely fresh (started only after all code/test
changes were in place, including the live-found `log_out()` fix, and
after the server itself was restarted on the final code): **3050
passed, 0 failed, 65 subtests passed** (995.13s / 16m35s) — the
3032-test CA1A baseline plus this stage's own 18 new tests, zero
regressions anywhere else in the suite.

## X. Live-browser walkthroughs

Four full Builder-operated live-browser walkthroughs against the real
dev server, starting from sign-in immediately after a clean
`restart-app`:

- **Walkthrough A (Requirement persistence):** selected OPR-1.1 via
  `?requirement=`, "Tell me about this" answered correctly, navigated
  Files → Overview, "Show me the evidence for this" (no re-selection)
  answered correctly against the same Requirement.
- **Walkthrough B (Finding persistence):** a real Finding created via
  the governed `record_analysis` path, selected via `?finding=`, "What
  should I do with this?" answered correctly with the Finding's own
  statement.
- **Walkthrough C (context replacement):** selected Requirement A
  (OPR-1.3), then Finding B (the elevator-shaft Finding), "Tell me
  about this" correctly resolved to Finding B.
- **Walkthrough D (Project isolation):** switched to "Test 2," "Tell me
  about this" correctly returned the honest "nothing selected" reply,
  with zero trace of any commissioning-specimen content.

All four development evidence only — never counted as OPR-7.2
representative-user evidence.

## Y. Local :5000 status and exact review instructions

**Running now**, restarted cleanly via the established `restart-app`
procedure immediately before the four live walkthroughs above,
confirmed via `curl` (`HTTP 200` on `/login`) and via the walkthroughs
themselves. Represents this stage's own commit (Section Z).
**Product Owner review route:** sign in, open any project, append
`?requirement=<a real Requirement id>` or `?finding=<a real Finding
id>` to the Workspace URL (or use the existing "Discuss this
Requirement" link), observe the new "Currently working with: ..."
indicator above the Conversation composer, then ask "Tell me about
this" — navigate to another view and back, ask a follow-up, and confirm
the same object is still understood.

## Z. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document and the code/test changes are committed together.

## AA. Remaining context limitations

Stated plainly: Requirement/Finding still have no dedicated UI
click-affordance analogous to "Discuss this Source" for entering the
`?requirement=`/`?finding=` URL (the mechanism is real and tested, but
reached today only via a direct link, not a new button); the visibility
indicator is a single plain line, not a richer breadcrumb; the
persisted slot survives an application restart only as long as
`FLASK_SECRET_KEY` is unchanged (an existing, unmodified fact about this
app's session model, not something this stage altered); Glass Engine,
Delegation, and voice/biometric entry remain entirely unbuilt; VOICE-1's
own non-context prerequisites (provider choice, consent UX, audio
security boundary) were not examined.

## AB. Recommendation for next stage

The context foundation (current-view + Source/Requirement/Finding
selection + bounded history + context-aware next steps + a reliable,
tested clear/isolate/persist lifecycle) is now complete enough to
support a first bounded Glass Engine pass anchored to a selected
object, or a first bounded VOICE-1 pass if its own separate
prerequisites (provider, consent, audio boundary) are audited first.
Recommend auditing VOICE-1's own remaining prerequisites as the next
small step before attempting either Glass Engine or VOICE-1 as a full
tranche.

---

**Deliberately NOT done this stage:** full Glass Engine; Delegation
object/architecture; biometrics; voice recognition/synthesis (including
VOICE-1 itself); external communications integrations; broad Workbench
redesign; new document engines; Bug Eye; Sovereign AI; PMBOK/
Body-of-Knowledge architecture; independent final commissioning; a new
UI click-affordance for Requirement/Finding selection beyond the real,
tested URL convention; declaring OPR-7.2 satisfied or beginning
representative-user testing.
