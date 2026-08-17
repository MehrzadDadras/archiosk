# Specified But Unbuilt — Navigation & Context Operational Map

**Status:** Living reference document (not a feature spec). Created under
`CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01` (two rounds of repository-grounded
investigation, both read-only, both run as forked sub-agents) and its Product
Owner disposition approving this file. Populated only with findings the two
investigation rounds and the earlier `CLAUDE-WORKSPACE-SHELVING-ARCHITECTURE-01`
review actually established against real code — nothing here is invented or
extrapolated beyond that evidence. Every row below carries its own confidence
and provenance so a future reader (human or Claude) can tell a settled fact
from a live recommendation without re-deriving it.

**Purpose:** stop this codebase's navigation/context defects from being
independently rediscovered in future sessions (this document exists because
one already was — see the Document List/Thumbnails row below, found twice in
one session before this file existed). Read this before re-investigating
navigation/context/return-path behavior; update it when a game or a real
architectural change contradicts a row.

**Explicitly not this document's job:** duplicating `MANIFEST.md`, `UI_REFERENCE_MAP.md`,
or any other existing repository documentation; describing UI element
inventories (see `UI_REFERENCE_MAP.md` for that); prescribing an
implementation before one is proven. Keep this file's own size proportional
to what's operationally load-bearing — do not expand it "just in case."

**Freshness anchor:** rows 1-14 are accurate as of commit `48b4468`; rows
15-21 (Multimodal Perception Games round) are accurate as of commit
`6180ec0`; row 22 (`CLAUDE-FILE-PUBLISH-RFP-01`) and the "Active pilot —
Image Search... Composer" / voice-fix sections are accurate as of commit
`32fe808` (code), live-deployed at commit `72d5829`, and fully
success-path live-verified (both text Composer and the vision path, after
a Product Owner production credential fix) as of 2026-08-16 under
`CLAUDE-PRODUCTION-AUTH-CLEANUP-RELOCATION-01`; rows 23-27
(`CLAUDE-CLIENT-RFP-PROJECT-CREATION-01`) are accurate as of commit
`f779d32`, live-deployed and live-verified (a real 35-document North
Bayview corpus established on production) as of 2026-08-16; row 28
(`CLAUDE-DEVELOPER-MODE-COCKPIT-01` Addendum E) is accurate as of commit
`c1aa71f`, live-deployed and live-verified as of 2026-08-16; row 29
(`CLAUDE-DATA-ROOM-RECONCILE-01`) is accurate as of commit `9683f29`,
live-deployed and live-verified against North Bayview's real 43-file
corpus as of 2026-08-16; row 30 (the Owner/Proponent working-material
label fix) is accurate as of commit `acf4257` (code, deployed to
production the same day) and `99f9fd8` (the hermetic cross-environment
test), hermetically verified on both operating environments as of
2026-08-17 - not yet live-browser-verified (see row 30's own note on
why). If the referenced file/line has since changed, the row's own
confidence should be treated as stale until re-verified, not trusted at
face value.

---

## How to read this table

- **Confidence** — High (directly confirmed by reading the real code/tests),
  Medium (a reasoned recommendation, not yet implemented or PO-approved),
  Low (a hypothesis worth checking, not yet confirmed).
- **Status** — `settled fact` (safe to assume without re-verifying),
  `open defect` (real, confirmed, not yet fixed), `dispositioned` (Product
  Owner has already ruled on it — don't re-litigate), `recommendation`
  (proposed, awaiting or partially through approval), `piloting` (an
  approved, bounded experiment is in progress — see its own section below).

| # | Finding | Confidence | Status | Provenance |
|---|---|---|---|---|
| 1 | Every route resolves objects by UUID first (`project_id`, `source_id`, `case_id`, `finding_id`); display name/filename is presentation-only, never a lookup key. Similarly-named objects never collide. | High | settled fact | Navigation Games Round 1, Game F1 — confirmed at `routes/portal.py` `_project_summary`/`app.py` `menu_open_project_choices` |
| 2 | `operating_environment` is a project-owned, locked-once-at-creation field (`services/case_workspace.py`). It is never a per-account/per-User field, and `is_admin()` has zero coupling to it. | High | settled fact | This session's Option C implementation + earlier plan-mode audit, cross-checked in both Games rounds |
| 3 | **Split-state defect**: the "current document" a user is viewing has two independent authorities — server truth (`?source=` on `workspace.show_workspace`) and a client-only `localStorage` "remembered last PDF" (`static/js/pdf_viewer.js`) — that can disagree with **no visual signal** distinguishing them on the Document List. | High | open defect (fix approved, not yet implemented) | Found independently twice in one session: Workspace Shelving review (Addendum B) and Navigation Games Round 1 (Game H2) — same root cause, two different investigative framings. Product Owner approved a fix (independent row-level indicator on the Document List; do not repurpose Mark/X, Keep-on-Main, Eye, or Gear) |
| 4 | **Exactly one** "return to where I came from" mechanism exists anywhere in this codebase: a `document.referrer`/`history.back()` heuristic on `templates/project_chooser.html`'s own back link. It is not reused by any other page. | High | settled fact | Navigation Games Round 1, direct code read |
| 5 | **No internal link carries origin/purpose state.** Every navigation link (Composer hotlinks, breadcrumbs, cross-object references) is built as a plain `url_for(...)` with forward-only state (destination), never backward state (why the user is going, what to return to) — with one deliberate exception (#6). This is the single largest, most generalizable navigation defect found. | High | open defect | Navigation Games Round 1, Cluster 1 (Games A1, D1, G2) — e.g. `app.py`'s `render_conversation_hotlinks` builds hotlink URLs with only `source_id`, no return context |
| 6 | **Working exception to #5**: the `?case=&preview_finding_id=` redirect (`routes/workspace.py`, RFI-preview flow) is a real, deliberate, working example of purpose surviving a redirect. Proves the pattern is cheap to build when done on purpose. | High | settled fact (reference pattern) | Navigation Games Round 1, Game C1 |
| 7 | `InvestigationStep.question` (the reviewer's own real purpose, verbatim) + `evidence_examined_ids` (real record ids, never text copies) are already linked in one record at the data layer — but this linkage is never surfaced anywhere as a UI return path. | High | settled fact (data layer) / open gap (UI layer) | Navigation Games Round 1, Game B1 — `services/case_workspace.py` `InvestigationStep` |
| 8 | `RFIDraft.reference_snapshot` is a deliberate point-in-time copy of the Case/Finding/Artifact/Source reference chain, specifically so a draft survives the source later being renamed, moved, or superseded. This is the correct, proven pattern for "acquired evidence must survive the source object changing later." | High | settled fact (reference pattern) | Navigation Games Round 1, Game G1 — `services/case_workspace.py` `RFIDraft` |
| 9 | Nothing in this codebase corrupts an object's canonical shelf/home based on where it was opened from — Investigations, Documents, etc. always re-derive their shelf membership fresh from stable project-scoped state, never from navigation history. | High | settled fact | Navigation Games Round 1, Game I1; Workspace Shelving review |
| 10 | Compare's on/off state and second-document selection are held in a plain in-memory JS variable (`static/js/eye_pane.js`) with **no persistence** — any navigation or refresh silently resets it. | High | dispositioned | Navigation Games Round 1, Game H1. Product Owner has already ruled this is intentional: "current-state evidence, not a future product decision." A timestamped Comparison Report remains a separate, outstanding, unrelated question — do not conflate the two. |
| 11 | `Anchor` (`services/case_workspace.py`) is a generic, already-reused, open-world "what this is about" pointer (`anchor_type`, `anchor_id`, `source_id`, `location`, `description`) — the closest existing primitive to an origin/target pointer for a future excursion mechanism. | High | settled fact | Navigation Games Round 1, Section A |
| 12 | The following governance-sounding names, referenced across both rounds of the Navigation Games prompts, are confirmed **absent** from both `governance/` and code — purely aspirational vocabulary in the prompts themselves, not descriptions of an existing mechanism: `CLAUDE-GO-TRAJECTORY-RECALL-01`, `CLAUDE-GO-CONTEXT-AWARENESS-01`, `CLAUDE-GO-USHERING-AGENT-01`, `CLAUDE-GO-WORK-PATH-NAVIGATION-01`, `CLAUDE-SURFACE-QUIET-CAPABILITY-01`, `CLAUDE-GATEKEEPER-01`, `CLAUDE-AGENT-ORCHESTRATION-GOVERNOR-01`, `CLAUDE-VALIDATION-ISOLATION-01`, `CLAUDE-CAPABILITY-RELOCATION-INTEGRITY-01`. The closest real, formal record of an attention/context model is `governance/specified-unbuilt/adaptive-attention-and-context-circulation.md` (status: **NOT AUTHORIZED**), which independently names the same primitives (`InvestigationStep`, `Relationship`, `GovernanceLog`, `Anchor`) as this document's own findings. | High | settled fact | Navigation Games Rounds 1 and 2, exhaustive repo-wide grep both times |
| 13 | Smallest generalized fix for #5: an `Anchor`-shaped `origin_kind`/`origin_id`/`purpose` parameter set any "go look at something" link could carry, resolved server-side into a small, quiet, optional "Return to [origin]" affordance — composition of #6 and #11's existing shapes, not a new subsystem. | Medium | dispositioned | Navigation Games Round 1, Section G. Product Owner accepted the Composer-hotlink pilot (row 14) as successful, 2026-08-16, but explicitly **do not widen to other surfaces** (breadcrumbs, other cross-object links) until further discovery games independently demonstrate a reusable pattern — see "Active pilot" below. |
| 14 | **Product Owner-recorded pilot finding (verbatim, 2026-08-16):** "A reliable return pointer may require contextual state, not merely one originating object ID. In this pilot, `origin_message_id` alone was insufficient; `case` was also required to reconstruct the originating conversation correctly. Discover the minimum sufficient return envelope experimentally rather than assuming it from schema." | High | dispositioned | Composer hotlink origin-pointer pilot (commit `bdf10c8`) — see "Active pilot" below for the full technical account of how this was discovered |
| 15 | **No vision-capable Anthropic API call exists anywhere in this codebase.** `services/llm_gateway.py` (the shared call site every LLM-backed feature funnels through) and every caller (`bhive_parser.py`, `cross_modal_investigation.py`, `investigation_snapshot.py`) build `content` as a plain string; none construct an image content block. This falsifies the "disconnected nerves, not missing organs" hypothesis for vision specifically — the organ itself is absent, not merely unwired. | High | settled fact | Perception Games Round 1, forks investigating Composer intake and ingest/OCR machinery, cross-confirmed independently by both |
| 16 | Document-set **Image Search** (`templates/base.html:502-523`, `static/js/document_marks.js:244-380`) is a UI-complete, backend-empty placeholder: clicking "Search" makes zero network calls and always returns the same static message regardless of image content — there is no match/no-match distinction because no search ever runs. The limitation is already honestly disclosed in the UI copy itself and in `governance/spare-parts-yard.md:151-204`. No escape hatch to Composer exists in code, markup, or JS. A pasted image is held only in browser memory (`FileReader`→dataURL), never uploaded. | High | open defect (dead end, no escape) | Perception Games Round 1, Image Search fork — direct code read of both files plus the referenced spare-parts-yard record |
| 17 | **Composer is text-only end-to-end, client and server.** `static/js/case_workspace.js` has no paste/drop/file-input handler on the Composer form; `routes/workspace.py`'s `post_message`/`quick_start` accept only a text form field server-side; `ConversationMessage` (`services/case_workspace.py:1535-1604`) has no attachment field, live or dead. Even if vision capability existed, no path carries an image into a Composer turn today. | High | settled fact | Perception Games Round 1, Composer-intake fork |
| 18 | `services/image_intelligence.py`'s `register_eye_capture` persists immediately and unconditionally into a governed Source/StructuralUnit on any valid image (calls `store.add_source(...)` directly) — there is no ephemeral/temporary staging tier anywhere in the image pipeline. ARCHIOSK currently has only two states for image content, "untouched" and "governed" — no middle "temporary conversational evidence" tier the kind row 5 in this document's own "Optional companion" framing (and the Product Owner's stated lifecycle goal) would need. | High | open gap | Perception Games Round 1, ingest/OCR-machinery fork |
| 19 | **Voice is real but narrow.** `static/js/voice_input.js` uses the browser's native `SpeechRecognition` Web Speech API (not `MediaRecorder`/audio blobs — a deliberate design choice per the file's own comments) to transcribe speech directly into the Composer text field (`case_workspace.js:1171-1180`). Once inserted, a voice-originated message is indistinguishable from typed text to the backend — no voice-origin flag, no referent/context metadata reaches `conversation_interpreter.py`. `governance/specified-unbuilt/voice-conversational-presence.md`'s own claim that "no speech library... of any kind" exists is stale: this VOICE-1-shaped prototype has since shipped. | High | settled fact (partially supersedes a stale governance claim) | Perception Games Round 1, voice fork |
| 20 | **Reproduced defect:** "Can you hear me?" is pattern-matched by `conversation_interpreter.py:739` into the generic social-utterance bucket (`_handle_conversational_utterance`) and answered "Hello [Name]. What are you working on?" — not a truthful statement about the transcription channel actually working. Confirmed by direct code trace, not yet live-browser-verified. | High | open defect (isolated, cheap to fix, independent of any vision work) | Perception Games Round 1, voice fork |
| 21 | `Selection Family`/`Depository` (referenced in prompt vocabulary) are confirmed absent from implementation — a single passing mention in `governance/STATUS.md`, zero code anywhere in `services/`, `static/js/`, `templates/`. Same category as row 12's aspirational-only prompt vocabulary; extends row 12's list rather than replacing it. | High | settled fact | Perception Games Round 1, Composer-intake fork; corroborated by this session's own governance-wide grep for the round's other named concepts (`VOICE-INTENT-CONTEXT`, `COMPANION-NARRATION`, `PRESENT-TIME-AURA`, `INFORMATION-GEOMETRY`, `MINIMUM-SUFFICIENT-CONTEXT`, etc. — all zero hits outside this map's own rows) |
| 22 | **Operational lesson (`CLAUDE-FILE-PUBLISH-RFP-01`, 2026-08-16): a relocated/added invocation surface for an existing canonical capability must reuse the exact same availability condition as every other surface — not a second, independently-maintained copy of it.** The File-menu "Publish RFP…" command (`templates/_app_menu.html`, added `bf3ae20`) correctly reused the canonical route (no duplicate publish implementation — `open-publish-panel` scrolls to and opens the same Toolbox form that already POSTs to `publish_procurement_package_route`), but its own *visibility* condition (`can_publish_procurement_package` alone) silently drifted from the sibling Toolbox panel's condition (`is_admin and can_publish_procurement_package`, matching the route's own `@admin_required`) — a real non-admin/`read_only` actor on an otherwise-eligible Owner project would see an enabled-looking command that dead-ended on click. Caught by direct verification of a delegated fork's finding, not by the fork itself (row 12/21's "unverified fork finding" discipline held here too) — no existing test exercised a non-admin actor against this specific command. Fixed by making the new surface read the identical condition, not a menu-specific rule of its own. | High | dispositioned (fixed, commit `10cea77`) | `CLAUDE-FILE-PUBLISH-RFP-01` — reuse this lesson before adding any future invocation surface (menu item, shortcut, secondary button) for a capability that already has an authorization/readiness gate elsewhere |
| 23 | **Project creation is not actually coupled to "one file."** `templates/upload.html` has always had two real, separately-routed establishment paths sharing one form: `portal.upload` (single file, `formaction` defaults to it) and `portal.upload_folder` → `services/ingestion.py`'s `ingest_folder_upload` (a whole folder/corpus, `CLAUDE-CA1D-RECEPTION-FIX-01`). The founding/principal file goes through the unchanged, existing `ingest_upload`; every other eligible file becomes a real governed `Source` with real `BHiveParser`-extracted text persisted as `EvidenceItem`s (`register_plain_text_structure`) — never filename-only. Per-file failure (bad extension, oversize, unreadable) is skipped and reported, never fails the whole establishment. `relative_path` is stored only as `Source.origin_reference` display/provenance metadata, never used to construct an on-disk path. | High | settled fact, live-verified | `CLAUDE-CLIENT-RFP-PROJECT-CREATION-01` — direct code read (`routes/portal.py:1991-2150`, `services/ingestion.py:352-493`) plus live establishment of a real 35-file corpus on production, commit `f15e741`/`f779d32` |
| 24 | **The Product Owner's "No file was provided" failure was a wrong-button/discoverability trap, not a missing capability.** `upload()`'s own single-file-only check (`routes/portal.py:2009-2015`) is what generates that exact message, and it runs regardless of what's staged in the folder picker — pressing "Create project and parse document" always POSTs to `portal.upload`. The folder path's own submit button (`#folder-submit-button`) already started `disabled` until a valid folder + founding-document choice was made; the single-file button had no equivalent gating at all, so it could be pressed with nothing chosen and produce a full server round trip before the user learned anything. Fixed: the same "disabled until valid" discipline now applies to both buttons. | High | dispositioned (fixed, commit `f15e741`) | `CLAUDE-CLIENT-RFP-PROJECT-CREATION-01` |
| 25 | **Real bug found and fixed: a genuine double-submit race in project establishment.** Reproduced live, by accident, during this round's own North Bayview verification — a slow request (35 files, plus a real external-AI classification call for the founding document) left a window where a second click on the same submit button fired a second identical request before the first had finished committing. `services/ingestion.py`'s `_reject_if_name_taken` uniqueness check only looks at *already-persisted* projects, so it did not yet see the first one — both requests succeeded, producing two real, fully-registered, identically-named projects. Neither submit button was ever disabled once a genuine submission actually started (only "not yet valid," row 24's fix). Fixed: both buttons disable immediately on the form's own `submit` event. A residual, explicitly out-of-scope case remains: two genuinely separate browser tabs/processes racing the server directly would still need a server-side lock/idempotency token to close — real additional scope this round did not cover. | High | open residual (server-side race unfixed, client-side window closed) | `CLAUDE-CLIENT-RFP-PROJECT-CREATION-01`, commit `f779d32` — the duplicate project this bug produced live was removed via the existing recoverable Remove Project flow, never permanent delete |
| 26 | **"Link to Storage" is confirmed a genuine, deliberate, honest unbuilt placeholder — not a gap to fix.** Its own template copy already states this ("not yet configured... shown here rather than hidden, and left disabled rather than misrepresented as available"). `SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR` is a named-but-never-set value in `KNOWN_SOURCE_ORIGIN_TYPES`, and the future watcher concept it would eventually need (`governance/specified-unbuilt/bug-eye-data-room-source-continuity.md`, "Bug Eye") is explicitly **NOT AUTHORIZED** — "Filesystem watchers or background daemons of any kind... not authorized... without a fresh authorization naming this file." Confirms the existing folder-upload path (row 23), not a new storage-link mechanism, is correctly the smallest real answer for a multi-document specimen like North Bayview. | High | settled fact | `CLAUDE-CLIENT-RFP-PROJECT-CREATION-01` — direct read of `governance/specified-unbuilt/bug-eye-data-room-source-continuity.md`, cross-checked against `templates/upload.html`'s own copy |
| 27 | **A zero-Source project shell is possible at the data-model layer but exercised by no current route.** `CaseWorkspaceStore.get_or_create(project_id, register_document_source=None)` (`services/case_workspace.py:5302-5318`) constructs a bare `ProjectWorkspace` with no Sources when no document is given — the "project needs a first document" coupling is a *caller* choice (every real route always passes one), not a data-model invariant. Not pursued as a UI path this round: North Bayview always has a real founding document, so an empty-shell establishment flow would be new, unrequested product surface with no present need. | Medium | settled fact (architecture), recommendation (do not build) | `CLAUDE-CLIENT-RFP-PROJECT-CREATION-01` — direct code read, not implemented |
| 28 | **Two different, deliberately-separate patterns already exist for a reviewer-wide UI "mode," and a new one must pick the right one on purpose.** "UI Reference Mode" (`templates/base.html`) is genuinely client-only — `localStorage` + an `<html>` class, applied pre-paint, never server-verified — correct for its own purpose (a presentation-only QA aid with no capability behind it) but would be a real authorization gap if reused for anything capability-bearing, since any user can set that `localStorage` key directly. Developer Mode (`CLAUDE-DEVELOPER-MODE-COCKPIT-01` Addendum E) deliberately used the *other* existing pattern instead: a plain `session['developer_mode']` boolean, set only by an `admin_required`-gated route (`routes/portal.py`'s `toggle_developer_mode`), read into template context by the ONE existing global context processor (`app.py`'s `inject_globals`, the same mechanism `is_admin`/`ai_calls_disabled` already use) rather than a per-route pass-through. `developer_mode` re-checks `is_admin()` again at read time as defense-in-depth, not just at the toggle route. This is the reusable lesson: a future reviewer-wide toggle should consciously choose between these two patterns based on whether it is presentation-only (client-side, like UI Reference Mode) or authorization-sensitive (server-session + context processor, like Developer Mode), never default to the client-only shape merely because it already exists and is simpler to copy. | High | settled fact | `CLAUDE-DEVELOPER-MODE-COCKPIT-01` Addendum E, commit `c1aa71f`, live-verified |
| 29 | **Analyze-first Data Room Reconciliation shipped, reusing 100% of the pre-existing registration mechanism.** `services/ingestion.py`'s `preview_data_room_reconcile` is a genuinely read-only comparison pass (hash + `origin_reference` matching against `active_sources`, never touching the store) staged via a new `PendingReconcileStore` (flat-JSON manifest + sibling raw bytes, TTL sweep — the same shape as `PendingUploadStore`); the pre-existing `reconcile_data_room_upload` (`CLAUDE-RFP27-TERRITORY-01`) was left completely unchanged and is still the only function that ever mutates the registry, invoked only after an explicit confirm. **Real Jinja footgun found and fixed**: a report dict keyed `"items"` silently resolved to the bound `dict.items` method under Jinja's dot-access (`report.items.new` returned the method object, not the list), rendering every itemized section as empty while the summary counts were correct — caught only by isolating backend output from rendered HTML, not by the summary line looking right. Renamed the key to `"by_status"`; there is no general Jinja guard against this class of bug, so any future report-shaped dict should avoid `items`/`keys`/`values`/`get` as a top-level key. Live-verified against North Bayview's real 43-file corpus: 27 unchanged, 0 new (the Product Owner's expected "one new eligible workbook" is actually `.xlsx` — genuinely **ineligible** per `ALLOWED_UPLOAD_EXTENSIONS`, a correction to the round's own framing, not a bug), 7 modified (confirmed via real filesystem mtimes to be genuine content drift in the underlying Codex-generated corpus, not a Reconcile defect), 1 renamed (a legitimate edge case: the project's founding document was registered via the original single-file establishment route, which never set `origin_reference`, so a hash match against a `None` origin_reference is classified "renamed from None" — cosmetically confusing but not a data-integrity issue). | High | settled fact, live-verified | `CLAUDE-DATA-ROOM-RECONCILE-01`, commit `9683f29`, live-verified on North Bayview production project `547e8455-d388-467d-9e60-1bc497681c86` |
| 30 | **A generic Files-shell label leaking across `operating_environment` — real pattern, worth checking for elsewhere.** The Files view's second root (`services/case_workspace.py`'s `FOLDER_ROOT_DESIGN_BUILDER`, "editable working material organized by the Project team") was named and labeled "Design-Builder Workspace" in `CLAUDE-P40-VW9`, before `operating_environment` (`CLIENT_OWNER`/`DESIGN_BUILDER_PROPONENT`) existed as a concept, and every call site rendered that literal text unconditionally — on a `CLIENT_OWNER` project this wrongly implied access to or coexistence with a Design-Builder/Proponent workspace, which never exists inside the same project record (a real Owner/Proponent publication-boundary leak, not cosmetic). Fixed with one shared helper, `services/environment_capabilities.py`'s `working_material_root_label(operating_environment)` (`CLIENT_OWNER` → "Owner Workspace", `DESIGN_BUILDER_PROPONENT` → "Design-Builder Workspace", legacy/unclassified → "Project Workspace"), reused by both the Files template (`case_workspace.html`) and Composer's own folder-reference/organize-advice conversational replies (`conversation_interpreter.py`) so the panel and the chat never disagree. **Deliberately left alone**: `capability_registry.py`'s static "what can you do" capability description still says "Design-Builder Workspace" unconditionally — `_handle_capability_question` is documented "by construction" (CA1C) to never consult workspace/project state for self-referential app-capability answers, and it names the mechanism by its canonical internal name rather than claiming per-project Proponent-workspace access, so this is a different, narrower category than the panel/reply leak and changing it would reopen a separately-ratified design decision. Underlying mechanism (folder root, route names, the `design_builder` form value, every `data-ui-ref`) is unchanged throughout — only user-facing label text is environment-aware now. **Verification is hermetic, not live-browser**: creating a throwaway admin account on production (both via `tools/create_credentials.py` over SSH and via a direct ORM-upsert script) was denied by the sandbox's own auto-mode classifier, and no admin session was already held in this round; Product Owner disposition (2026-08-17) was to verify via the pytest test client instead of pursuing further account-creation workarounds. `tests/test_p40vw9_files_display_and_folder_architecture.py`'s `test_working_material_root_label_is_environment_aware` proves both directions directly against real `CLIENT_OWNER`/`DESIGN_BUILDER_PROPONENT` fixtures. A future round wanting genuine live-browser proof on this surface will need the Product Owner to either supply credentials or approve the account-creation action first. | High | dispositioned (fixed, hermetically verified) | `CLAUDE-GO-NAVIGATION-CONTEXT-GAMES-01` follow-up (Owner/Proponent boundary audit), commits `acf4257`/`99f9fd8`, 2026-08-17 |

---

## Reusable organized understanding (do not re-derive)

Rows 1, 2, 9, and 11 above are settled facts a future task can cite directly
rather than re-verifying. Row 3 and row 10 are each already the subject of a
specific Product Owner disposition — future work should implement/respect
those dispositions, not re-open the question of whether they're real or
correct.

## Known contamination boundary

An unverified fork/agent finding must not be treated as canonical until
checked against real evidence (a test run, a direct file read, an explicit
Product Owner ruling) — this file's own rows are labeled with confidence
specifically so a `Medium`/`recommendation` row is never read as already
decided.

---

## Active pilot — Composer hotlink origin pointer

**Approved scope (Product Owner, 2026-08-16):** test row 13's approach on
Composer hotlinks only (`app.py`'s `render_conversation_hotlinks` /
`services/case_workspace.py`'s `resolve_conversation_hotlinks`) — the
highest-frequency real "go look at something" action in the app (Navigation
Games Round 1, Games A1/G2). Explicit purpose: **prove or disprove** whether
purpose-aware return can be achieved by composing existing primitives
(`Anchor`'s shape, the `?case=&preview_finding_id=` redirect precedent)
rather than building a new navigation framework — not to ship a finished
feature. Report the pilot's result here (and to the Product Owner) before
widening it to any other surface (breadcrumbs, other cross-object links).

**Result (2026-08-16, commit pending):** **Proves the composition approach
works, with one real, discovered refinement.**

Implementation: `app.py`'s `render_conversation_hotlinks` now appends
`origin_message_id` (the citing message's own id, already an existing
function parameter — no new data) to every Source hotlink URL it builds.
`routes/workspace.py`'s `show_workspace` reads it back as a soft display
hint (never validated server-side — same treatment `?current=`/
`?preview_finding_id=` already get; a stale/foreign id just produces a dead
`#fragment` link, which a browser already no-ops on safely, not an error).
`templates/_app_menu.html` renders a small, quiet "← Return to conversation"
link — reusing the already-existing `id="message-<id>"` DOM anchor on every
conversation message (`templates/case_workspace.html`, unchanged) — only
when the parameter is present. Zero new routes, zero new persistence,
zero new schema.

**The refinement, found by actually building this, not anticipated in
advance:** the message id alone was not sufficient. A case-scoped
conversation thread (as opposed to the project-scoped one) only renders on
the destination page at all when `?case=<id>` also selects it — so the
first implementation produced a "Return to conversation" link that pointed
at a fragment nothing on the page actually had. Fixed by also carrying
`anchor_case_id` (already an existing parameter passed into the same
function) as `case=` when the citing message was case-scoped. This is
itself useful new evidence for row 5/13 above: an origin pointer is not
always a single id — it can require its own small, already-available
supporting context to actually resolve, and that context should be
identified by building and testing, not assumed complete from the schema
alone.

**Verified:** full suite clean (9 known pre-existing, unrelated failures
only); 5 new dedicated tests (`tests/test_p40e_unified_workspace.py`,
`OriginMessageIdPilotTests`) cover the real end-to-end round trip (following
the actual rendered href, not a hand-built URL), the no-parameter common
case (no link renders — quiet by default), and the stale-id degradation
path. Live-deployed and live-browser-verified on production (posted a real
Composer message, clicked the resulting hotlink, confirmed `source=`/
`origin_message_id=`/`case=` all carried correctly, confirmed the return
link renders and navigates to the right `#message-<id>` fragment).

**Product Owner disposition (2026-08-16): accepted as successful.** Do
**not** widen the origin-pointer mechanism to any other surface yet. Row 14
above records the Product Owner's own verbatim finding from this pilot.
Keep the current implementation limited to Composer Source hotlinks until
additional discovery games independently demonstrate a reusable pattern —
this is now a closed, bounded piece of the codebase, not a base to build on
without a fresh authorization.

---

## Perception Games round (`CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01`, 2026-08-16)

**Scope:** architectural investigation only (four parallel read-only forks
— document-set Image Search, Composer attachment intake, voice/audio,
ingest/OCR/vision machinery). No implementation performed. See rows 15-21
above for the individual findings; this section is the round's headline
conclusion, kept short on purpose.

**Headline finding:** ARCHIOSK has **no vision capability anywhere** — not
in ingest, not in Composer, not in Image Search — because no file in the
repository ever constructs an Anthropic vision content block (row 15). This
is a stronger result than the prompt's own working hypothesis ("disconnected
nerves, not missing organs"): for vision, the organ is missing outright. The
nerves-vs-organs framing does hold for voice — real, working browser-native
dictation exists (row 19), but it carries no context/referent metadata and
mishandles a direct channel-status question (row 20).

**Two independent, low-cost quick wins identified** (neither requires
building vision capability first): (1) the "can you hear me" mismatch (row
20) is a narrow, isolated `conversation_interpreter.py` intent-bucket fix;
(2) Image Search's placeholder message (row 16) already discloses its own
limitation honestly but offers no next move — failing the impatient-child
test on dead-end grounds alone, independent of whether real search is ever
built.

**No pilot authorized this round.** The smallest reversible next
experiment identified — a single new vision-capable Composer turn wired
only to Image Search's existing "Send to Composer" gap, with the pasted
image never persisted — is a recommendation awaiting Product Owner
disposition, not yet built. Do not begin it without a fresh authorization.

---

## Active pilot — Image Search "Not found" → Composer vision interpretation

**Approved scope (Product Owner, 2026-08-16):** exactly the escape hatch
recommended above — Image Search's own no-match state → "Not found" →
"Open in Composer" → one real vision-capable Composer turn → zero
automatic persistence. Not general Composer-wide image attachments, not
visual search, no new database/media subsystem, no automatic Source
registration. Also approved: an isolated fix for the "can you hear me"
voice-channel-status defect (row 20), unrelated to vision.

**Result (2026-08-16, commit `32fe808`): proves the composition approach
works, with the same kind of refinement the earlier hotlink pilot found —
minimum sufficient context had to be discovered by building, not assumed.**

Implementation: `services/llm_gateway.py`'s `call_llm_json` gained optional
`image_base64`/`image_media_type` params — the first and only place in this
codebase that ever constructs an Anthropic vision content block, additive
and backward-compatible (every existing caller is unaffected; `content`
stays a plain string when the new params are omitted). `routes/workspace.py`'s
new `open_image_in_composer` reuses the existing `ACTION_EXTERNAL_AI_REQUEST`
security gate (same `_evaluate_security_action` resolver every other real
external-AI call site in this file already uses — no new governance
mechanism), posts a human-role placeholder message (`"Sent an image from
Document Search (no match found) for GO to look at."` — never the image
bytes themselves) and GO's real interpretation as two ordinary
`ConversationMessage`s via the existing `store.add_message`, and never
persists the image anywhere else — no Source, no StructuralUnit, no disk
write. `static/js/document_marks.js` builds a hidden form (base.html) with
the client-side-only `imageDataUrl` and reads the current Case, if any,
from the URL — the exact same "soft display hint, re-validated server-side,
never an authorization boundary" discipline the Composer hotlink pilot (row
13/14) established for `?case=`.

**Minimum-sufficient-context finding (this pilot's own version of row 14):**
one vision-capable call was sufficient — no second call, no multi-turn
tool loop, no retrieval step was needed to produce a usable interpretation.
The context that *did* turn out to matter: the workspace's own
`display_title`, given to the model as the only project-relevance signal
(deliberately not the full evidence corpus — this is temporary
conversational evidence, not a governed Q&A grounded in extracted
requirements). The `Anchor`/soft-hint primitives were sufficient as-is;
nothing new was needed beyond composing what rows 11/13 already
established.

**Temporary-evidence lifecycle finding:** confirmed by direct code
construction, not just observation — this pilot proves a genuinely
temporary tier is possible without building the "full ephemeral-evidence
architecture" row 18 flagged as missing. The image never becomes a
persistent object of any kind; the *fact* that an image was sent is what
persists (as an ordinary conversational message), not the image itself.
This is a real, minimal existence proof that ARCHIOSK's binary
"untouched/governed" lifecycle gap (row 18) can be closed for a
single-shot interaction without a new schema — but this pilot deliberately
does **not** solve multi-turn referent continuity ("what about the image
from two messages ago") — that remains open, matching the Product Owner's
own explicit "do not build the full architecture yet" instruction.

**Live-verified twice (2026-08-16, commit `72d5829` deployed to
archiosk.com) — both the failure path and, after a production credential
fix, the real success path.**

First pass: pasted a synthetic unrelated image into a real
Design-Builder/Proponent project's Image Search, clicked Search (`"Not
found - ARCHIOSK doesn't yet compare this image against the document set.
Open in Composer and GO can look at it directly."`, the inline button
correctly styled as a small in-sentence link, not an oversized standalone
`.btn`), clicked "Open in Composer" — confirmed the redirect and the two
new `CONVERSATION` messages. The production `ANTHROPIC_API_KEY` was
invalid at that point (a pre-existing, unrelated infrastructure defect,
confirmed via server logs and independently reproduced against the
ORDINARY text Composer path too — see `CLAUDE-PRODUCTION-AUTH-CLEANUP-
RELOCATION-01`'s own diagnosis below), so the honest degradation path is
what actually fired: `"GO couldn't look at the image just now: An error
occurred calling the model."` — never a fabricated result. This proved
the failure path live, under a real failure condition, not a mocked one.

Second pass, after the Product Owner replaced the credential: pasted a
freshly-generated, distinctive synthetic image (a red square and a blue
circle on white, drawn via canvas so its content was verifiably known in
advance) into a different real project's Image Search, same route through
"Not found" → "Open in Composer". GO's real reply: `"This appears to be a
simple graphic with a red square and a blue circle on a white background —
likely a placeholder, test image, or basic design element. It doesn't
appear to relate to '[project]' in any recognizable way. If you meant to
upload a different file, you may want to try again."` — an accurate
description of the actual pixel content (proving the vision call is real,
not canned), honestly assessed non-relevance rather than fabricating a
connection, and offered a next move. Minor nuance worth a future
revalidation, not a defect: the reply named "ARCHIOSK" rather than the
project's own `display_title` when assessing relevance — the system
prompt's own "You are GO, ARCHIOSK's project assistant" framing likely
bled into that clause; harmless (no false relevance claimed) but a
candidate wording tweak if this surface is ever revisited. Also confirmed
live: the project's Document count stayed unchanged (27 before and after)
— no Source was registered for the test image, matching the "zero
automatic persistence" requirement exactly.

**Production credential note:** the underlying blocker was diagnosed as
the credential itself being invalid/revoked at Anthropic's end, not an
ARCHIOSK wiring defect — confirmed by testing the exact key in the
running process's own environment directly against
`https://api.anthropic.com/v1/models`, isolated from the application,
before any Product Owner action. `archiosk-go.service` has exactly one
env source (`EnvironmentFile=/var/www/archiosk/.env`, no competing
`Environment=` override, no wrapper script) — a clean, single-source
configuration with nothing left to reconcile. An unused, `inactive`/
`disabled` legacy `archiosk.service` unit (pointing at a dead
`/home/ubuntu/app.py`, referencing a separate, stale `/etc/archiosk.env`
that doesn't even contain the key) was found but confirmed harmless — not
part of the live path, not a competing source.

**Product Owner disposition: accepted (implicit — implementation and
verification proceeded exactly as this round's own approval specified).**
Do not widen beyond Image Search's own no-match escape hatch without a
fresh authorization — general Composer-wide image paste, multi-turn
referent continuity, and a formal ephemeral-evidence schema all remain
explicitly unbuilt.

---

## Voice channel-status fix (`CLAUDE-GO-MULTIMODAL-PERCEPTION-GAMES-01`, 2026-08-16, commit `32fe808`)

Row 20's reproduced defect is fixed: `services/conversation_interpreter.py`
gained a dedicated `_looks_like_channel_status_check`/
`_handle_channel_status_check`, checked before the generic greeting bucket
in both `interpret_message` and `quick_start`'s own separate Case-creation
routing gate (`routes/workspace.py`) — the latter needed its own fix too, a
real gap a focused test caught (removing "can you hear me" from the
greeting-phrase list without also updating `quick_start`'s own OR-chain
would have silently created a new Investigation for a literal
channel-status question). **Live-verified** on archiosk.com: "Can you hear
me?" now returns `"Yes - I don't hear audio directly, but your words came
through as text and I have them."` — a truthful, one-sentence answer, never
the generic `"Hello. What are you working on?"` greeting.
