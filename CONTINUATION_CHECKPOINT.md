# Continuation checkpoint

## 2026-08-05 — CLAUDE-P40-VW9A (Files Cockpit Close-Out and Camel Programme Record)

**Scope:** a bounded close-out of the four cockpit residuals the VW9
final report identified, plus recording the previously-untracked Camel
MM1–MM9 multimodal programme. Product owner accepted the underlying VW9
Files/folder architecture conditionally; this stage resolves the
conditions, it does not issue the VW9 acceptance seal.

**A1 — folder-menu exclusivity and dismissal.** New `static/js/
files_folder_menus.js`: the Design-Builder Workspace's per-row "..."
`<details>` menus now behave as an exclusive group (opening one closes
any other), dismiss on outside click, and dismiss on Escape (returning
focus to the trigger) — adapts `document_tabs.js`'s own document-level
dismissal pattern to NATIVE `<details>`/`<summary>` elements rather than
rebuilding a synthetic menu (those hold real `<form>`s, not just
buttons), so native keyboard/screen-reader semantics are never touched.
**A real, broader defect found while testing this** (not merely the
narrow-viewport case A3 named): the panel used to be a floating
`position:absolute` overlay tall enough (three stacked forms) to
visually cover several rows below it — not just out of view, out of
*reach* (confirmed directly: a focused, in-viewport `<summary>` covered
by another row's open panel did not respond to a real click OR keyboard
Enter, polled for 3+ seconds). Fixed at the root rather than patched
around: the panel now renders in-flow unconditionally (`main.css`'s
`.files-folder-row:has(.files-folder-actions[open])`, using `:has()` -
already precedented in this file, `.conversation-thread:has(...)`),
pushing later rows down instead of floating over them. This single fix
also resolves A3.

**A2 — unambiguous move destinations.** `routes/workspace.py`'s
`design_builder_move_targets` now computes a `path_label` per candidate
(full ancestor breadcrumb via the same `store._folder_path()` the
in-page breadcrumb already uses), rendered in the Move `<select>`
instead of the bare folder name. Two same-named folders in different
branches ("Structural Drawings › Details" vs. "Architectural Drawings ›
Details") are now visibly distinguishable; the submitted `<option
value>` stays the folder id, unchanged and authoritative. Sibling-scoped
uniqueness itself was not touched.

**A3 — narrow display-division behavior.** Folded into A1's fix above:
the in-flow panel is unconditional, not gated behind a width
breakpoint, since real testing found the reachability problem was never
actually narrow-width-specific. Verified at a representative ~360px
`panel=1` (multi-Display division) width: `.files-roots` still
correctly stacks to one column (pre-existing 900px breakpoint,
unchanged), and the folder-actions panel is confirmed `position:
static`, never escaping the container, Rename field genuinely visible
and clickable. Only the panel's own internal form layout keeps a
dedicated `@media (max-width: 480px)` rule (stack fields vertically at
that width for readability).

**A4 — delete-cancellation return context.** `delete_folder_route`
(`routes/workspace.py`) now passes the folder's own server-derived
`parent_folder_id` (from the already-loaded, project-scoped folder
record — never raw request input) into `confirm_delete_folder.html`,
whose `confirm_back_url` now returns there (root-level folders still
land on the bare Files root) — the same "controlled application state,
not an arbitrary redirect" shape `confirm_action.html`'s own `case_id`
back-link already uses. Verified end-to-end (nested and root-level),
including actually following the rendered link to confirm it lands
inside the correct parent folder's own listing, not just that the href
string looks right.

**Part B — fluidity, recorded as deferred, not fixed.** The "+ New
Folder" disclosure closing after every POST/redirect (full-page-reload
architecture) is accepted fast-follow polish, not a VW9 blocker. No
client-side live-update conversion was made.

**Part C — viewport-support finding, recorded, not fixed.** Real-browser
evidence (fresh session, no `localStorage` state, 412px viewport, full
`base.html` shell): `.launcher-panel` (Lists) and `.workspace-right-
column` (Toolbox+Eye) BOTH default to their visible, `position:fixed`
overlay-drawer state simultaneously (neither auto-collapses on narrow
first load — only *manual* toggling has the existing mutual-exclusion
JS, `base.html`'s own `onNarrow()`/divider-click handlers), and their
bounding boxes measured `x:0..320` and `x:92..412` respectively — a
228px overlap covering the ENTIRE 412px viewport width, obscuring the
Display/main content area almost completely (screenshot evidence
captured). Escape does dismiss both (existing keydown handler), but
nothing surfaces that to a first-time narrow visitor. This is
DIFFERENT from, and narrower than, the earlier VW9 report's own claim
that "the whole shell does not collapse into a usable layout at ~412px”
— CLAUDE-P40-VW7B-QA3 (prior stage) already proved, with a real 1920px-
to-320px sweep, that the shell (including both drawers, and the topbar
z-index fix that keeps it clickable above either) works correctly once
a panel's hidden/shown state is established; the gap is specifically
the FRESH-SESSION default, not the mechanism itself. No existing
mobile/responsive marketing claim was found anywhere in the templates
(`grep`-verified), so per this stage's own governing instruction ("do
not undertake a broad shell redesign... unless a tiny correction is
clearly necessary to prevent false compatibility claims") no fix was
made — recorded for the product owner's own choice among: enforce/
document a minimum supported width (≥641px, where the drawer mechanism
never engages at all); build a controlled reduced-panel mode (the
cheapest concrete option: extend the existing `onNarrow()`/mutual-
exclusion JS to also auto-collapse BOTH drawers by default on first
narrow load, a few lines, reusing code that already exists); or
schedule full narrow-shell adaptation as a later cockpit stage.

**Part D/E — the Camel MM1–MM9 programme, recorded.** New
`governance/specified-unbuilt/camel-multimodal-programme.md`: the
product owner's own staged MM1 (multimodal foundation/evidence
contract) through MM9 (consolidated validation) intent, preserved in
substance, with a dependency graph and cross-cutting requirements
(fact/measurement/judgment/assumption/AI-suggestion vocabulary; no
silent AI-to-authoritative promotion; provenance; Excel interop) called
out explicitly rather than left implicit per-stage. Includes the
Design-Manager-as-expert-integrator requirement (Part E) with its
canonical Progressive Design-Build Excel risk-register/Monte Carlo
acceptance case, and an explicit table mapping that requirement's own
facets across MM1/MM3/MM6/MM7/MM8/MM9. `governance/STATUS.md` gained one
pointer row (not stage-by-stage rows) in "What's specified but unbuilt"
— every MM stage is explicitly **NOT AUTHORIZED** for implementation,
a staged intent record, not a build order. `MM1`–`MM9`/"cockpit" were
confirmed absent from the repository before this stage (`grep -rli`,
zero matches) — this closes that continuity gap, it does not silently
assert the programme was always tracked here.

**Tests:** new `tests/test_p40vw9a_files_cockpit_closeout.py` (10
focused tests - request-level A2/A4 coverage plus real-Chromium A1/A3
coverage, including the genuine reachability-race and hit-testing
findings surfaced while writing them, documented in the test file's own
comments rather than papered over). All pre-existing VW9/VW8/UI-
reference-map suites re-run clean after these changes. Full suite run
once, cleanly, for this stage's own close-out (see the final report for
the exact count/duration) - no competing browser/test/server process
left running afterward.

**Recommendation:** see the VW9A final report delivered in conversation
for the evidence-based accept/conditionally-accept/reject
recommendation. No acceptance seal is recorded in this entry, per this
stage's own explicit governing instruction.

## 2026-08-04 — CLAUDE-P40-VW9 (Governed Files Display and Project File Architecture)

**Scope, stated up front:** the first bounded implementation of a real
Files Display surface and its underlying Project file architecture -
explicitly NOT the final issued Data Room hierarchy, bulk/ZIP import,
external retrieval, existing-Document relocation, the full linked/
retrieved/ingested/used/preserved lifecycle, addenda/supersession
comparison, cross-Project access, global search, or P41. This is a
genuine new business-object family (`Folder`) - the same category of
authorization as CLAUDE-P40-VW7's Tag/Task addition, not a pure UI/
navigation stage - so, following that precedent, `governance/STATUS.md`
and `governance/current/kernel-object-model.md` both gained a matching
entry (see below), unlike VW7B/VW8/VW8-QA1 which stayed UI-only.

**A process incident, disclosed rather than silently absorbed:** three
forks were launched in parallel for pure read-only research (auditing
`services/case_workspace.py`, `routes/workspace.py`, and Lists/UI-
reference templates) before any implementation began. Because
`subagent_type: "fork"` inherits the FULL parent conversation - including
this stage's own large governing prompt - two of the three forks began
writing actual implementation code (a duplicate, conflicting `Folder`
dataclass/constants block) despite an explicit "before writing any code"
instruction. Caught immediately via `git status`/`git diff`; the rogue
uncommitted changes were `git stash`-ed (not discarded) and the domain
model was implemented directly, by hand, using only the forks' clean
research findings. Nothing from the rogue edits was used. Recorded as a
feedback memory for future sessions (avoid parallel research forks when
a large implementation mandate is already in the inherited context).

**1. Files as a real stable Display surface.** `routes/workspace.py`'s
`STABLE_DIRECTORY_KINDS["files"] = "Files"` and `case_workspace.js`'s
`PANEL_KINDS.files` - the second real entry in the extension point
CLAUDE-P40-VW8-QA1 built, proving it genuinely generalizes rather than
being a comment promising it would. Breadcrumb and division-0-header
labeling needed ZERO template changes (both already read the shared
`directory_view_label` VW8-QA1 introduced). One new Lists leaf
(`lists.project.files`, positioned between Documents and Investigations),
same stable-singleton shape as Overview - no tab-strip pill, no per-
instance id, no duplicate-open concept, works in multi-Display layouts
via the same `&panel=1` mechanism Overview/Investigations already use.

**A real bug found and fixed during real-browser verification, not
caught by any request-level test:** `base.html`'s multi-Display click-
interceptor used to have exactly ONE `data-view` Lists leaf (Overview),
so its dispatch fell through to a hardcoded `kind='overview'` for "any
`data-view` link, whatever its value" - accidentally correct at the
time. Adding Files as a SECOND `data-view` leaf exposed the real shape
of that bug: clicking Files while a non-zero Display was the active
target silently populated Overview instead. Fixed by reading the
attribute's own value (`data-view === 'files'` branch, checked before
the generic fallback); confirmed live in a real browser before and
after the fix, and now has its own source-text regression test
(`test_multi_display_click_interceptor_resolves_files_kind_not_overview`).

**2. Two governed sibling roots, Data Room and Design-Builder
Workspace - governed VIRTUAL roots, not persisted domain rows.**
`FOLDER_ROOT_DATA_ROOM`/`FOLDER_ROOT_DESIGN_BUILDER` are fixed code-level
constants; neither root is itself a `Folder` record. Real, persisted
`Folder` rows exist only inside Design-Builder Workspace -
`CaseWorkspaceStore.create_folder` has no `root` parameter at all and
always writes `FOLDER_ROOT_DESIGN_BUILDER`, so there is structurally no
route or method that can create a Data Room folder this stage - "ordinary
Design-Builder actions cannot touch Data Room" is true by construction,
not convention. Data Room's own real issued hierarchy import is
deliberately not started; its panel instead shows a truthful
compatibility view of every existing active `workspace.sources` (name +
link, honestly labeled "not yet organized into the issued hierarchy"),
or an honest empty state explaining the root's purpose when there are
none - never an invented hierarchy, never a reclassification.

**3. Stable folder identity.** `Folder.id` (uuid4, `_new_id()`) is
canonical, mirroring the exact principle already stated on `Source`'s
own docstring ("folder locations and filenames are external
representations only"). A folder's full path is always DERIVED at read
time by walking `parent_folder_id` (`CaseWorkspaceStore._folder_path`),
never stored as a string - the same "store flat, derive structure at
read time" shape this module already uses everywhere else. Rename only
touches `name`; move only touches `parent_folder_id`; neither ever
touches `id`. Deletion is a recoverable soft-delete (`removed_at`/
`removed_by`, same tombstone convention `Source`/`Project` already
establish) restricted to EMPTY folders only - a removed id is never
reused. No `folder_id` field was added to `Source` this stage - a
Document is structurally incapable of being assigned into a folder yet,
so no existing Investigation/RFI/Task/Tag/conversation/citation
relationship is touched by anything here, now or by construction for
whatever a future stage adds.

**4. Design-Builder Workspace folder operations - the full set asked
for, none deferred.** `create_folder`/`rename_folder`/`move_folder`/
`delete_folder` on `CaseWorkspaceStore`, routed through `routes/
workspace.py`'s new `/projects/<id>/workspace/folders...` routes. No
owner/admin gate (deliberately mirrors `create_task`/`create_custom_tag`'s
precedent, not `remove_source`'s - Design-Builder Workspace is
collaborative team structure, "created by the Project team," not owner-
locked evidence); `_load_workspace_or_404` is the one and only
authorization check, same as every other route. Sibling-name uniqueness
scoped to (project, root, parent) via `_reject_if_sibling_folder_name_taken`
(style mirrors `ingestion.py`'s own `_reject_if_name_taken`). Cycle
prevention via `_folder_descendant_ids` (rejects moving a folder into
itself or its own descendant); a corrupted/foreign `project_id` on a
folder record is independently rejected too (defense in depth, not just
structural workspace-file isolation - both were separately falsified and
confirmed during this stage's own review). Delete refuses a non-empty
folder outright. `templates/confirm_delete_folder.html` uses the
lightweight `confirm=yes/no` gate (same family as `confirm_remove_
document.html`), not the Approval Gate - deleting an empty organizational
folder is consequential-but-not-governed, the same category CLAUDE.md's
own "two different confirm vocabularies" note already places Remove
Document/Remove Project in.

**5. File lifecycle vocabulary - named and documented, NOT implemented,
per this stage's own explicit instruction not to fabricate states.**
`linked → retrieved → ingested → used → preserved`:
- **linked** - the Data Room references an external location/identifier
  for material not yet retrieved into Archiosk's own storage. No record
  type for this exists yet.
- **retrieved** - file bytes have been fetched into storage but not yet
  parsed/registered. No intermediate state exists yet - every current
  ingestion path goes straight from upload to a fully-registered `Source`.
- **ingested** - the ONLY state that is genuinely real today, and has
  been since before this stage: a Document is a first-class `Source`
  record in `workspace.sources` (`ingest_upload`/`add_document_source`).
  VW9 did not change this meaning at all.
- **used** - the Source has been actively drawn on by governed project
  work (cited by a Finding/Requirement/Relationship, referenced in an
  RFI). Not tracked as a stored field anywhere; only inferable today by
  querying existing references. The natural future shape is a DERIVED
  property (matching `review_state_for_finding`/`requirement_
  adjudication_state`'s own "derive at read time, never store" pattern),
  not a new stored flag.
- **preserved** - a Source (or a specific revision) locked as immutable
  relied-upon evidence, checksum-verified, replaceable only through
  `Supersession`'s existing append-only mechanism. Partially precedented
  (`Source.file_hash` already exists but is optional/unenforced) but not
  wired to any actual immutability gate.

Registering a Folder's identity, or a Source's existing ingestion, never
implies any of the other four states - no code path anywhere marks an
existing Document with a lifecycle state it hasn't actually earned.

**6. Existing Document compatibility - audited, all safeguards hold.**
No route in this stage creates, moves, duplicates, or mutates a `Source`
in any way. Existing Document URLs, tab restoration, Investigation/RFI
ownership, Task/Tag/conversation/citation links, and Remove/Restore
Document all verified unaffected (regression suite + direct browser
check: opened an existing Document normally while Files/folders existed
in the same Project, confirmed identical behavior). A legacy Project
predating this stage loads safely - `ProjectWorkspace.folders` is a
purely additive `list[dict]` field with an empty-list default (same
backward-compatible shape as `tags`/`tag_occurrences`/`tasks`), verified
directly by stripping the key from a real persisted workspace JSON and
confirming it still loads and can create folders going forward.

**7. Security.** Files/folders reuse `_load_workspace_or_404`/
`can_access_project` exactly like every other view - no new
authorization path. Verified: an unauthorized `read_only` stranger gets
404 on both the Files view and every folder mutation route;
unauthenticated requests redirect to `/login`; a crafted folder id from
a different Project is rejected (both via the structural "not in this
workspace's own list" path and, independently, via the explicit
`project_id` field check inside each mutation method - falsified and
confirmed both actually matter, not merely one masking the other being
untested); CSRF stays enforced (global `Flask-WTF` `CSRFProtect`, no
route in this stage is exempted). No case-level (`visible_cases_for`)
concept applies - folders follow the `Source` model (project-level
access only, no per-record visibility), matching fork audit findings
that Sources have no such layer either.

**Tests:** `tests/test_p40vw9_files_display_and_folder_architecture.py`
(40 tests - registry/architecture, persistence/identity, governance,
display behavior) plus the new click-interceptor regression test noted
above. Four of the most safety-critical tests (cross-project defense-in-
depth, cycle prevention, empty-folder-required delete, `STABLE_
DIRECTORY_KINDS` registration) were directly falsified during this
stage's own review - temporarily disabled the guard, confirmed the test
genuinely failed, restored the correct code - per this stage's own
"prove tests are sensitive" instruction; one of those falsification
passes (the naive cross-project test) revealed the test itself was
vacuous for an unrelated structural reason and was rewritten to
genuinely exercise the intended guard rather than accepted as passing.
One pre-existing VW8-QA1 test (`test_reserved_files_kind_is_
documentation_only_no_functional_branch`) asserted "files has NO entry
in PANEL_KINDS" - now literally false by this stage's own deliberate,
authorized design (that test's own prior-stage comment explicitly
anticipated this: "adds a real 'files' entry... not before" - that
"later stage" is this one) - updated, not reverted, to assert the new
invariant (`files:` IS a real registered entry, dispatched through the
shared table, still no bare string-comparison branch). Full suite:
2,588 passed, 0 failed (2,549 baseline + 39 new, +1 after the click-
interceptor regression test was added = 40 in the final VW9 file).

**Real-browser verified live** (restarted, `STATIC_VERSION` 55→56 for
the `main.css`/`case_workspace.js` changes; throwaway account/Project/
folders, all removed then permanently deleted after use): Files
projects into Display from Lists; the two roots render as visually/
semantically distinct siblings in both Black and Light appearance
modes; nested folder creation, rename, move (including the real move-
targets dropdown correctly excluding the folder itself and offering its
true valid destinations), and the delete confirm→cancel→confirm flow
all verified end-to-end; existing Document opening unaffected; multi-
Display embedding of Files alongside an open Document (the click-
interceptor bug above was found and fixed during exactly this check);
UI Reference Mode badges render identically to Overview's own sibling
leaves; unauthorized direct URL access denied.

**Narrow-viewport, verified in a follow-up session** after the browser-
automation window-resize tool was confirmed non-functional in this
environment (tested at two different target sizes, and via a DevTools
responsive-mode keyboard shortcut - neither changed the actual rendered
viewport, a tooling limitation, not a product gap). Worked around with a
same-origin `<iframe>` (420px wide, pointing at the live Files page,
inheriting the real session cookie) injected via `javascript_tool` -
CSS media queries evaluate against an iframe's own width independently
of the parent window, so this is genuine browser layout-engine output,
not a simulation. Confirmed `iframe.contentWindow.innerWidth === 412`
(well under the 900px breakpoint) and read `.files-roots`' own computed
style directly: `gridTemplateColumns` resolved to a SINGLE value
(`"300.271px"`, not two columns), and `.files-root-design-builder`'s
`top` (613px) sat below `.files-root-data-room`'s `bottom` (594px) -
i.e. genuinely stacked vertically, not two narrow side-by-side columns.
The breakpoint works correctly. Cleanup: iframe removed, throwaway
account/project created for this check were removed then permanently
deleted afterward.

**Governance:** `governance/STATUS.md` and `governance/current/kernel-
object-model.md` both gained a `Folder`/Files-architecture entry,
following the CLAUDE-P40-VW7 precedent (a real new business-object
family gets a governance row; pure UI/navigation stages don't).

**Deliberately not started, explicitly out of this stage's scope:** the
final issued Data Room hierarchy, inventing standard folder names, bulk/
ZIP import, external cloud-drive integration, remote retrieval, binary-
storage redesign, the full lifecycle automation named above, addenda
reconciliation, supersession/version comparison, checksum-based
evidence preservation beyond the honest naming above, moving existing
Documents into folders, replacing the ingestion workflow, a Files
restore-UI (soft-delete data is recoverable, no UI surface built),
cross-Project access, global search, organization sharing, multi-
tenancy, billing, and P41. No placeholder Files control was ever built
for any of these - every implemented piece is real.

No product-owner acceptance seal issued, per this stage's own governing
instruction.

## 2026-08-04 — CLAUDE-P40-VW8-QA-CLOSE (Product-Owner Acceptance Seal)

**Bounded documentation-only close-out** - no application code, template,
CSS, JavaScript, schema, or test file was touched in this stage.

**Product owner accepts:**

* `CLAUDE-P40-VW8 — Governed Display Tab System` (implementation commit
  `d623e1d`)
* `CLAUDE-P40-VW8-QA1 — Display Tab Architecture Sufficiency Review`
  (corrective commit `fa254fa`)

The acceptance explicitly includes the QA1 finding immediately below
this entry: VW8 initially lacked a reusable extension point for a future
stable Files Display surface (`directory_view == 'overview'` was an
independently-repeated literal, not a registry), and QA1 corrected this
with `routes/workspace.py`'s server-side `STABLE_DIRECTORY_KINDS`
registry and `static/js/case_workspace.js`'s client-side `PANEL_KINDS`
registry - the smallest generic foundation, not Files itself. The
synthetic-kind tests in
`tests/test_p40vw8qa1_stable_surface_extension_point.py` proved a future
stable Display surface can be registered and mounted through both
registries without adding any Files-specific placeholder behavior.

**This seal accepts the Display-tab foundation only** - it does not
authorize or accept a Files/Data Room implementation, Design-Builder
Workspace folders, file ingestion/retrieval changes, cross-Project
access, global search, additional business objects, or P41. None of
those were started.

**Evidence re-verified, not re-run:** `HEAD` and `origin/main` both
confirmed at `fa254fa` before this close-out; the QA1 entry's own
recorded full-suite result (2,549 passed, 0 failed) and real-browser
verification stand as recorded - the suite was not re-run since no
repository evidence changed and that recorded result was directly
verifiable from this same file. The pre-existing, unrelated
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture
remains untouched (not deleted, modified, regenerated, staged, or
committed) - preserved exactly as QA1 and every prior session already
left it.

**UI reference update not required.**

## 2026-08-04 — CLAUDE-P40-VW8-QA1 (Governed Display Tab System sufficiency review)

**Task:** independently determine whether VW8 (immediately below) genuinely
satisfied its product-owner purpose - not merely repairing the two
existing record-tab mechanisms (Documents, Investigations), but
establishing a real Display foundation for a *future* dedicated,
persistent Files Display tab. Explicitly not authorized to implement
Files itself, add a placeholder Files control, build a Data Room, or
touch real Project data.

**Finding: VW8 was incomplete.** VW8's own audit correctly identified
that Overview/Chats are this app's STABLE surfaces (a Project-level
singleton, no tab-strip pill) - but never generalized that pattern.
Grounded in the actual repository: `directory_view == 'overview'` was a
bare string literal independently repeated across `routes/workspace.py`'s
own `?view=` whitelist (`if directory_view not in ("overview",)`), the
breadcrumb in `templates/base.html`, and the Display division-0 header
name in `templates/case_workspace.html` - three copies kept in sync only
by hand, no registry naming "the set of stable kinds" anywhere.
`static/js/case_workspace.js`'s own client-side `kind` dispatch (for the
separate VW7B/VW4 multi-Display split-screen embedding path) had the
identical problem one layer down: `buildPanelUrl`, `populateDivision`,
and `syncListsActiveState` each ran their own independent
`kind === 'case' || kind === 'overview' || kind === 'new-case'`-shaped
chain - and `syncListsActiveState`'s own final fallback
(`: 'a[data-view="overview"]'`) was a genuine latent bug: it applied to
ANY unrecognized kind, not only 'overview', so a future unknown kind
would have silently marked Overview's own Lists leaf active instead of
nothing.

**Fix (smallest generic foundation, not Files):** `routes/workspace.py`'s
new `STABLE_DIRECTORY_KINDS` dict and `case_workspace.js`'s new
`PANEL_KINDS` table are now the two single sources of truth those sites
read from. `STABLE_DIRECTORY_KINDS` drives a new `directory_view_label`
computed once server-side and consumed by both the breadcrumb and the
division-0 header (replacing their independent `'Overview'` literals).
`PANEL_KINDS` replaces the three independent kind-dispatch chains with
one registry consulted by all three functions, fixing the latent
fallback bug in the process. Neither change adds a Lists leaf, a picker
entry, or any content branch for anything but Overview - registering a
kind's identity alone still renders nothing (proven by test, see below).

**Tests:** `tests/test_p40vw8qa1_stable_surface_extension_point.py` (9
tests) - registers a synthetic, non-user-facing test-only kind into
`STABLE_DIRECTORY_KINDS` for the duration of a test (`patch.dict`) and
confirms the breadcrumb, division-0 header, and `?view=` whitelist all
pick it up with ZERO template changes, that an unregistered value still
degrades to nothing, that a real `?case=`/`?source=` selection still
overrides a registered stable kind, and that registering a kind never
fabricates Overview-specific content. Plus source-text evidence that
`PANEL_KINDS` is the single table `buildPanelUrl`/`populateDivision`/
`syncListsActiveState` all read from, and that the old unconditional
Overview fallback in `syncListsActiveState` is gone. Fixed 3 pre-existing
tests (`test_p40vw8_governed_display_tab_system.py`'s
`test_reserved_files_kind_is_documentation_only_no_functional_branch`,
`test_p40vw8qa_new_investigation_action.py`'s
`test_populate_division_handles_new_case_kind` and
`test_build_panel_url_maps_new_case_to_the_view_query_param`) that pinned
the OLD three-independent-chains source-text shape - updated to verify
the same invariants against the new `PANEL_KINDS`-registry shape, not
reverted. Full suite: 2549 passed, 0 failed (`~53min` this run - no code
relationship to the change, matches this file's own already-documented
"duration has occasionally spiked" note elsewhere).

**Real-browser verified live** (restarted, throwaway account + Client/
Owner project + Investigation, both deleted after use): Overview
breadcrumb/division header render identically to before (now sourced
from `directory_view_label`, not a literal); multi-Display split-screen
Overview embedding via the refactored `buildPanelUrl`/`populateDivision`
still works end-to-end (iframe content + Lists active-state agreement);
closing that division correctly reverts. No visible regression.

**Not implemented (by design, per this stage's own constraints):** Files
itself, any Files control/leaf/picker entry, Data Room, folder hierarchy,
Add Document redesign, cross-Project access, global search, P41. No
product-owner acceptance seal issued.

## 2026-08-03 — CLAUDE-P40-VW8 (Governed Display Tab System)

**Tag collision, flagged explicitly:** this is a DIFFERENT stage from
the earlier, already-shipped "CLAUDE-P40-VW8"/"CLAUDE-P40-VW8-QA"
(Reference Mode completion, Appearance/theme correction, Lists/Display/
Menu fixes, Add Tag visible consequence, focused Project chooser,
Project-switching dialog — git log `4043784`/`639d84f`, and this file's
own entry further down). The tag is reused because that is what this
stage's own governing prompt specifies — the same "reused because the
prompt says so, disambiguated everywhere it matters" handling this
session already gave the earlier "CLAUDE-P40-VW7B" collision (see this
file's own VW7B entries).

**Started from a verified clean state:** local `HEAD` at `17eba2f`
(the VW7B-QA3 header-stacking fix, matching `origin/main` exactly,
already pushed) confirmed before any edit; working tree clean apart
from the pre-existing, unrelated `tests/fixtures/nreocrc/
_lab_instance_scratch_002/` scratch fixture.

**Authorization:** the product owner was unavailable for this session
and granted broad autonomous completion authority in advance (proceed
continuously through implementation/test/commit/push without pausing
for routine choices, progress reports, or push confirmation; hard-stop
only for the specific conditions that governing message listed - none
of which were reached). No product-owner acceptance seal is issued -
that remains pending the product owner's return, per that same
authorization's own explicit instruction.

**Audit (Section 2), grounded directly in the actual repository, not
assumed:** this application already has TWO real, working, tested
dynamic-record Display tab mechanisms before this stage touched
anything - CLAUDE-P40-DTAB1's Document tab strip (`kind='source'`:
pin/preview/hidden, rename/color, keyboard roving-tabindex, an "All
Tabs" overflow panel) and CLAUDE-P40-VW7B's Investigation Attention
Positions strip (`kind='case'`: a bounded 4-slot attention set, a real
"Focused" indicator, a non-destructive "release" that never navigates
or falsifies status). Neither RFI, Task, nor Tag is a separate Display
"kind" at all: an RFI leaf (`lists.project.rfis.leaf`) routes into its
OWNING Investigation (`?case=`); a Task/Tag leaf routes via
`routes/workspace.py`'s own `_conversation_source_url` into either the
bare workspace URL (Chats/no-selection state) or an Investigation's own
conversation (`?case=`) with a `#conv-source-<id>` scroll anchor - never
a `?source=` Document route, confirming Tasks/Tags are tied to
CONVERSATION passages, not Documents (a real, useful correction to my
own initial assumption while auditing - checked against the actual
route source, not left as a guess). "Project Tools" is a pure Lists-
region set of forms/actions that never touches Display at all. Overview
and Chats (the "nothing selected" state) are this app's two STABLE
surfaces - each a Project-level singleton with no possible duplicate,
represented through Lists' own server-rendered active-state plus the
Display division header text, deliberately with NO tab-strip pill of
their own - a considered "smallest coherent" choice (Section 3/4's own
"do not introduce browser-style tab complexity... unsupported by real
product needs"), not an oversight: a singleton that can never be
duplicated trivially satisfies "opening the same surface again focuses
the existing tab" without needing a switchable pill. "Files" is
reserved (Section 9) as a documented, no-op kind in
`case_workspace.js`'s own `populateDivision` comment - no branch, no
picker entry, no placeholder control anywhere, per that section's own
explicit "do not create placeholder controls that imply the Files
system already works."

Toolbox (Section 8) already implements the `active_case > selected_
source > neutral-empty-state` priority order server-side, request-
scoped exactly like Display itself - confirmed by direct template
inspection (`case_workspace.html`'s own `{% block toolbox %}`), no
client-side state to go stale, no code change needed. Eye (Section 8)
already clears on navigation by its own prior, accepted, explicitly-
documented design (EYE1's own "Not saved anywhere - cleared when you
navigate away or reload") - since every real tab activation in this
full-page-reload app IS a navigation, this is pre-existing, correct,
unchanged behavior. Both strips' CSS already truncates long labels
identically and both already scroll horizontally when more tabs exist
than fit - confirmed by direct CSS inspection (`.document-tab-label`/
`.attention-position-label`), no changes needed. Lists active-state
staleness (Section 5) was checked directly against
`case_workspace.js`'s own `syncListsActiveState` (idempotent - clears
its own client-managed `.active` classes before reapplying, every
render) and against `?case=`/`?source=`/`?view=` being fully server-
rendered per-request for division 0 (no client state to go stale there
at all) - no bug found.

**Two genuine, small, targeted coherence gaps were found and fixed** -
deliberately NOT a merge of the two existing strips into one, which
would have risked regressing VW7B's own recently-accepted 4-slot
capacity model and Document tabs' pin/preview mechanics for no product-
requested benefit (Section 4's own "do not introduce browser-style tab
complexity... unsupported by real product needs" cuts against a forced
merge just as much as it cuts against inventing new complexity):

1. `investigation_attention.js`'s own keyboard handler
   (`onPositionKeydown`) was missing the explicit Space-key activation
   `document_tabs.js`'s `onTabKeydown` already has (native `<a href>`
   elements activate on Enter but not Space - a button/checkbox
   convention, not a link one). A real accessibility-parity gap between
   this app's two dynamic-record tab strips - `UI_REFERENCE_MAP.md`'s
   own `.attention-position` row had actually already (incorrectly)
   documented "click/Enter/Space" as its behavior at VW7B time, ahead of
   the code actually implementing it; this stage closes that pre-
   existing doc/code gap rather than just noticing it. Fixed identically
   to `document_tabs.js`'s own approach.
2. `document_tabs.js`'s own `activateFallback` (closing the active
   Document tab with no other Document tab or preview left) fell
   straight to the empty Display state even when a perfectly good
   attended Investigation was sitting in the Attention strip right next
   to it - not incorrect per DTAB1's own original, Documents-only scope,
   but incoherent once this stage treats BOTH strips as one governed
   dynamic-record tab system per Section 4's "closing the active tab
   selects a deterministic neighboring... tab." Fixed by exposing a new,
   read-only `window.ArchioskInvestigationAttention.mostRecentAttended
   (excludingId)` lookup (insertion-order-based - attention has no
   per-entry recency timestamp the way Document tabs' own `lastActiveAt`
   does, so "last pushed into attention" is the defined, deterministic
   rule used instead of inventing new persisted state) that
   `activateFallback` now consults as a FINAL fallback, only after
   exhausting its own existing Document-tab/preview options and before
   the empty state - purely additive, degrades safely (a guarded
   `typeof` check) when `investigation_attention.js` never ran at all
   (a `panel_only` iframe division has no `#attention-strip`). Does NOT
   touch Attention's own "release never navigates" guarantee - a
   read-only lookup consulted by a DIFFERENT action (closing a Document
   tab), never a change to what release itself does.

No other code changes were required or made - every other item on
Section 2's own audit checklist was found already correct by direct
repository evidence, not merely assumed correct because nothing was
reported broken.

**Tests:** new `tests/test_p40vw8_governed_display_tab_system.py` (14
tests) - audit-confirmation tests (RFI/Task/Tag/Project-Tools routing,
empty-Display-state message, both strips present regardless of
selection, Overview/Chats deliberately pill-less), source-level tests
for both fixes, and two genuine real-Chromium tests (via the
`playwright` Python package - a dev/test-only optional dependency,
deliberately NOT added to `requirements.txt`, every test skips cleanly
if it's absent) for the cross-kind fallback and Space-key activation -
the two genuinely NEW pieces of runtime behavior a source-text assertion
cannot prove. A real, empirically-confirmed Chromium restriction was
hit and worked around here: `page.set_content()`-hosted documents (the
technique VW7B-QA3 established) have an opaque origin in this browser -
`window.localStorage` throws `SecurityError` there, which every call
site in both files under test silently swallows via `try/catch`,
meaning a `set_content()`-based test would have silently "passed" with
completely inert localStorage rather than erroring loudly. Fixed by
serving the real rendered HTML from a real (but non-routable, RFC 2606
`.invalid`) HTTP origin via `page.route()`'s own `fulfill()` instead -
still zero live server/real network dependency, but real, working
`localStorage`. Sanity-checked by reverting both JS fixes and
re-running: 7 of 14 tests genuinely failed (the ones actually exercising
either fix), 7 still passed (the unrelated audit-confirmation ones) -
proof this suite is a real regression guard, not tautological. Re-ran
DTAB1's own test file (`test_p40dtab1_document_tabs.py`) and both VW7B
test files unmodified as an explicit regression gate (158 tests total
across all four files) - all passed. `UI_REFERENCE_MAP.md`'s own
validation suite (`test_p40vw7a_ui_reference_map.py`, 22 tests) also
re-ran clean - no registry drift, since this stage added no new/moved/
retired `data-ui-ref` identifiers. Full suite: see this entry's own
final line below.

**Real-browser verification**, against the live running app (restarted,
`STATIC_VERSION` bumped 54→55), using a fresh throwaway account/Project
(2 Documents, 2 Investigations, all created via the real UI forms in a
real browser - deleted again after use, no real data touched):
no-selection empty state, Overview, opening a Document (tab strip
appears), opening a second Document (2 tabs, correct pin/preview
styling), re-opening an already-open Document (no duplicate tab),
opening an Investigation (attention position appears), attending a
second Investigation, closing an INACTIVE Document tab (no navigation),
closing the ONLY remaining active Document tab while 2 Investigations
are attended (**the new cross-kind fallback - landed on the attended
Investigation, screenshotted, Toolbox/Lists/breadcrumb all correctly
agreeing on the new active tab**), reload restoration, keyboard-only
Arrow+Space activation of an attention position (**the new Space-key
fix - genuinely worked live**), the header Switch-Project link, signed-
out access correctly redirecting to `/login` with no Project data
leaked, a 500px narrow viewport (Document tab strip still visible/
usable), and UI Reference Mode toggling on correctly. All confirmed
working via direct URL/DOM inspection and screenshots; no defect found.

**Preserved:** VW1-VW7B and all their accepted QA corrections
(explicitly re-confirmed by the DTAB1/VW7B regression test re-runs
above and the real-browser walkthrough) - Attention's own 4-slot
capacity model, "release never navigates," Document tabs' pin/preview/
hidden/rename/color mechanics, per-Project isolation, all untouched.
Files/Data Room hierarchy, Design-Builder folders, folder/ZIP import,
external storage sync, linked-document retrieval, a new ingestion
lifecycle, Add Document redesign, cross-Project document access, global
search, and P41 were NOT started - only the reservation comment
described above.

## 2026-08-03 — CLAUDE-P40-VW7B-QA3: Header Project Link Still Fails in Clean Browser Session

**Started from a verified clean state:** local `HEAD` at `c590d00`
(the combined VW7B-QA1+QA2 push, already on `origin/main`) confirmed
before any edit; working tree clean apart from the pre-existing,
unrelated `tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch
fixture.

**Report:** a clean-session real-browser reproduction (sign out, sign
in fresh, open a Project with a Document, single-click the Project
name once) showed the header link still did not navigate, contradicting
QA2's own report. The task explicitly instructed: do not assume QA2's
explanation was complete merely because static markup contains an
anchor, and required genuine browser-computed evidence, not another
source-text assertion.

**New capability exploited for this stage:** `npx playwright install
chromium --with-deps` successfully downloaded a real, working headless
Chromium into this environment (`C:\Users\<user>\AppData\Local\
ms-playwright\`) - every prior stage in this session had correctly and
honestly reported "no real browser tool exists here." The `playwright`
Python package (installed into `venv/`, NOT added to `requirements.txt`
- dev/test-only, never imported by the shipped app, every test using it
skips cleanly rather than failing if it's ever absent) reuses that same
browser install. This is the first stage in this session with genuine
`getBoundingClientRect`/`elementFromPoint`/`elementsFromPoint`/real-
`.click()` evidence instead of static-source reasoning about geometry.

**Diagnosis, with direct genuine-browser evidence:** launched the real
Chromium against the actual local dev server (a throwaway verifier
account + a real ingested PDF Project, deleted again after use - see
below), signed in fresh, opened the Project with its Document active,
and swept `document.elementFromPoint()` plus a real `.click()` across
viewport widths from 1920px down to 320px. Every width from 1920px down
to 700px clicked correctly - QA2's `flex-shrink: 0` fix was real and
never wrong as far as it went. At 600px and narrower, the click
consistently failed (`Timeout 3000ms exceeded`), and
`elementFromPoint()` at the link's own visible-text coordinates
returned `.tree-leaf.launcher-link.current-project` (Lists' own
current-Project row) instead of the topbar anchor - direct proof the
visible header text was being reached by clicks, just not by the
element a user would expect. Root cause: `main.css`'s own `@media
(max-width: 640px)` rules turn BOTH `.launcher-panel` (Lists) and
`.workspace-right-column` (Toolbox+Eye) into `position: fixed; top: 0;
... z-index: 30` overlay drawers below that breakpoint - a symmetric,
pre-existing, systemic gap on both sides, not a one-off. `.workspace-
topbar` itself was plain `position: static` with no z-index, so at
narrow widths either drawer painted over the entire topbar, including
the Project-name link, regardless of the link's own (correct) geometry.
The user's own browser window width at the time of the report was
never directly observed (no way to inspect that after the fact), but a
narrower-than-1024px effective viewport - an unmaximized window, a
snapped half-screen, devtools docked open, or OS display scaling - is
readily plausible and was the only variable, across the full sweep,
that reproduced the exact reported symptom.

**Fix, a structural correction (not a speculative one-property patch):**
`.workspace-topbar` gained `position: relative; z-index: 31` - one step
above the drawers' shared ceiling of 30, the same "stack higher than
anything it could ever appear over" idiom this file already uses
elsewhere (`.conv-selection-toolbar`/70 above the 60-ceiling Appearance
popup). Neither drawer's own `top: 0`/`z-index: 30` was touched - both
still correctly cover Display/Chat beneath the topbar, which is their
own intended behavior; only the always-persistent topbar strip (this
app's "one shell every authenticated page shares," per that rule's own
original comment) is now guaranteed to stay on top of them, at every
viewport width, regardless of which drawer (if either) is open. Because
the topbar has a real (opaque, per-appearance) background, this also
visually cleans up the narrow-width drawer's own top edge rather than
leaving two texts visually colliding.

**Verified with the real browser, re-run after the fix:** the same
1920px-to-320px sweep now succeeds at every width, including the
previously-failing 600px and down to 320px (a mobile width, not even
one QA3 asked about). Re-verified live against the actual running dev
server (not just the hermetic test) at 500px and 1440px with a fresh
throwaway account/Project: both widths navigate correctly to the
Vestibule, which correctly shows the Project as "CURRENTLY ENTERED";
screenshots taken before/after each click. The throwaway verifier
account and Project (used for both the diagnostic sweep and the live
double-check) were deleted from the real dev DB/registry afterward -
no lingering fixtures.

**Preserved and re-confirmed:** the VW7B-QA1 PDF fix (the live-browser
double-check's own screenshot shows the PDF rendering real page content
- confirms this independently, live, not just via the existing
regression tests), Project isolation, Lists scoping, per-Project
restoration, Investigation Attention Positions, the Archiosk mark's own
destination, and all real business data (only two throwaway
diagnostic-only accounts/Projects, created and destroyed within this
stage, ever touched the real dev DB).

**Tests:** new `tests/test_p40vw7b_qa3_header_topbar_stacking_fix.py`
(3 tests) - the first browser-capable/geometry-aware regression
coverage in this repository, per the task's own explicit demand that a
source-text assertion is insufficient for this class of bug (QA2's own
14 source-text tests had already passed while the real click failed).
Renders the genuine Flask-served HTML plus the genuine, unmodified
`tokens.css`/`main.css` file contents into a real headless Chromium via
`set_content()` - no live HTTP server involved, staying consistent with
this repo's hermetic-test discipline while still exercising real
browser layout/paint/hit-testing. Every test class skips cleanly (not
loudly) if Chromium isn't installed in a given environment. Sanity-
checked the test's own validity by temporarily reverting the CSS fix
and re-running: 2 of 3 tests genuinely failed against the unfixed CSS
(a different drawer intercepted the click in that run -
`.workspace-pane-toolbox` rather than the Lists tree - same root class
of bug, confirming this isn't narrowly overfit to one specific
intercepting element). Full suite: 2526 passed, 0 failed, in 794s -
only pre-existing, unrelated rate-limiter warnings. No UI-reference
changes were needed - no new `data-ui-ref`, no structural DOM change,
purely a CSS stacking-context property.

**Not started (per this stage's own explicit scope boundary):** SAFE1,
VW8, cross-Project access, global search, P41.

**Not pushed** - `HEAD` carries this stage's commit locally, one ahead
of `origin/main` at `c590d00`; pending product-owner review per this
session's established convention.

## 2026-08-03 — CLAUDE-P40-VW7B-QA2: Header Project Link Does Not Open Vestibule

**Started from a verified clean state:** local `HEAD` at `96bb08f`
(the VW7B-QA1 PDF fix, one commit ahead of `origin/main` at `0c6c520`,
not yet pushed - pending product-owner review) confirmed before any
edit; working tree clean apart from the pre-existing, unrelated
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture.

**Report:** real-browser acceptance of pushed VW7B found that clicking
the current Project name ("Nipigon Ramp") in the top header did not
open the Project Vestibule - the browser stayed on the current Project
workspace.

**Diagnosis, methodically ruling out every angle the task named, with
direct evidence for each:**
- **Rendered header composition / link target:** re-rendered the exact
  header markup via the Flask test client - the Project name genuinely
  IS a real `<a href="/projects/choose?current=<project_id>">` with a
  correct, authorized target and a real `aria-label`. Confirmed
  correct, not the defect.
- **JavaScript interference:** searched every `static/js/*.js` file for
  any reference to `.workspace-topbar` (none exist) and every
  `addEventListener('click', ...)` in the codebase - the one
  document-wide click listener (`case_workspace.js`, closing a context
  menu) does not call `preventDefault()`/`stopPropagation()` and is
  therefore harmless; the one interceptor scoped near the header
  (`base.html`'s Display-division routing script, from the OTHER,
  earlier "VW7B" stage) is explicitly scoped to `[data-tree-root]`
  (the Lists tree), which does not contain the header at all. Ruled
  out.
- **Overlay interference (CSS):** checked `pointer-events`
  declarations (only UI Reference Mode's own badge, itself
  `pointer-events: none` and irrelevant unless that dev-only mode is
  active) and z-index/absolute-positioning on every neighboring
  region - none present. Ruled out as a literal overlay.
- **Click area - the actual defect:** `.workspace-topbar` has three
  flex children - `.workspace-topbar-identity` (brand + the
  Project-switch link), `#workspace-document-controls` (the middle
  region, `flex: 1 1 auto`, actively grows to fill space whenever
  Document controls are visible - exactly the scenario CLAUDE-P40-
  VW7B-QA1 just fixed, making this region visible again for the first
  time in a real acceptance pass), and `.workspace-topbar-controls`
  (Display Layout/Appearance/Account). Only the LAST of these three
  had `flex-shrink: 0`. `.workspace-topbar-identity` did not, so the
  actively-growing middle region could squeeze it toward its own
  `min-width: 0` floor - shrinking the Project-name link's actual
  rendered/clickable area toward nothing, even though its DOM, href,
  and aria-label were correct the entire time. A geometry defect, not
  a routing, interception, or missing-anchor one.

**Fix, the smallest verified change:** `.workspace-topbar-identity`
gained the same `flex-shrink: 0` its sibling `.workspace-topbar-
controls` already had - symmetric treatment across both edge regions,
no new mechanism invented. `.workspace-topbar`'s own existing
`flex-wrap: wrap` remains the safe overflow fallback if all three
now-protected regions' combined natural width ever exceeds the
viewport (a two-line header, still fully clickable) rather than a
one-line header with an invisible-width link. `.workspace-topbar-
context`'s own nested `overflow: hidden`/`text-overflow: ellipsis`
still truncates an unusually long Project+Document name WITHIN this
now-guaranteed width, unaffected.

**Preserved and re-confirmed, per this stage's own explicit
checklist:**
- The Vestibule still distinguishes Current Project ("Currently
  entered") from Available Projects.
- Returning to the Project still restores its own independent
  workspace state (this is entirely client-side/localStorage,
  untouched by a CSS change - the header link itself carries no such
  state of its own).
- The Archiosk brand mark retains its own established destination
  (`/`, `aria-label="Archiosk Home"`) - unaffected.
- No click target overlaps another header control - if anything, this
  fix REDUCES overlap/ambiguity risk by guaranteeing each edge region
  its own space rather than letting the middle region encroach.
- Keyboard activation (a real, natively-focusable `<a>`, no
  `tabindex="-1"`) and accessible naming (`aria-label` carrying "Switch
  Project") both confirmed intact.
- Project isolation, Lists scoping, Investigation Attention Positions,
  and all business data - none of this logic lives in header CSS, so
  none of it was at risk from either the bug or the fix.

**Tests:** new `tests/test_p40vw7b_qa2_header_vestibule_link_fix.py`
(14 tests) - the flex-shrink fix itself, confirmation it matches the
sibling's own established pattern, confirmation the middle document-
controls region remains deliberately flexible, re-confirmation of
every other angle the task asked to rule out (link target with a
Document actually open - the exact real-browser scenario - JS
interference, single-tab-stop, brand-mark destination, keyboard/
accessible-name), and direct confirmation the Vestibule/restoration
guarantees are unaffected. Re-ran the BRAND1/header/VW7B test files
(122 tests) unmodified as an explicit regression gate - all passed. No
UI-reference changes were needed - no new reference, no structural DOM
change, purely a CSS layout property. Full suite: 2523 passed, 0 failed.

**Real-browser verification:** not available in this environment - a
real flex-shrink computed-geometry regression can only be directly
observed in an actual browser layout engine; stated honestly rather
than fabricated as a rendered-pixel proof. Product-owner verification
checklist: open a Project with a PDF Document active (Document
controls visible, reproducing the exact reported scenario) and confirm
the Project name in the header is reliably clickable across its full
visible width; confirm it still opens the Vestibule with "Current
Project"/"Currently entered" shown; confirm the Archiosk mark still
navigates home; confirm keyboard Tab reaches the link and Enter
activates it; confirm at a narrow viewport that the header wraps
sensibly rather than clipping the link again.

## 2026-08-03 — CLAUDE-P40-VW7B-QA1: Real-Browser PDF Source Failure

**Started from a verified clean state:** `HEAD == origin/main` at
`0c6c520` (the VW7B stage) confirmed before any edit; working tree
clean apart from the pre-existing, unrelated
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture.

**Report:** real-browser acceptance review of pushed commit `0c6c520`
found that selecting "Nipigan Starter.pdf" correctly moved the Lists
highlight from Chats to the Document and correctly updated the
breadcrumb/Toolbox, but Display showed "This PDF could not be opened
in the viewer: getDocument - expected either data, range, or url
parameter," with Thumbnails simultaneously stuck at its empty state.

**Diagnosis, grounded directly against the shipped vendor source, not
assumed:** `static/js/pdf_viewer.js`'s `mount()` and
`mountRememberedThumbnailsIfAny()` (CLAUDE-P40-LTH1) both called
`pdfjsLib.getDocument(url)` with `url` as a BARE STRING.
`static/js/vendor/pdfjs/pdf.min.mjs` (version 6.2.108, per that
directory's own README) does **not** normalize a bare string into
`{url: ...}` - confirmed by reading the actual shipped source: its real
`getDocument(t={})` immediately reads `t.url`, which is `undefined` for
a plain string, so neither `data`, `range`, nor a resolved `url` is
ever set. The literal throw text ("getDocument - expected either
`data`, `range`, or `url` parameter.") was found verbatim in the
shipped file, inside an ASYNCHRONOUS `Promise.all([...]).then(...)`
continuation that only runs once the PDF.js worker responds - not a
synchronous validation at call time, which is exactly why no prior
smoke check caught it, and why it would fail identically for **every**
PDF, not something specific to this one fixture. A Node.js empirical
probe against the same vendored file (stubbing just enough browser
globals to import it - `DOMMatrix`/`Path2D`/`ImageData`) additionally
confirmed neither call form throws synchronously, consistent with the
throw being deferred into the async continuation this diagnosis
identifies, rather than contradicting it.

**Ruled out, with direct evidence, not assumption:**
- **Not caused by VW7B** - VW7B never touched `pdf_viewer.js` at all;
  `git diff` across the VW7B commit confirms this file is absent from
  it.
- **Not a VW7B Lists/Vestibule/attention regression** - the report
  itself confirms Lists highlighting, breadcrumb, and Toolbox all
  behaved correctly; only Display/Thumbnails (pdf_viewer.js's own
  domain) failed.
- **Not caused by LTH1's remembered-thumbnail LOGIC** - LTH1 only
  inherited the identical, already-broken call convention via
  copy-paste from `mount()`'s own pre-existing (CLAUDE-P40-VW7A-QA2)
  code; the remembered-context reconciliation, revalidation, and
  isolation logic around it are all unaffected and unchanged.
- **Not a missing/invalid route or DOM source value** - confirmed via
  a real rendered-HTML check (`DomSourceValueGroundingTests`): the
  server-rendered `data-pdf-url` is a real, non-empty, correctly-
  authorized URL, and that URL genuinely resolves to the real file
  content through `workspace.source_file`. The bug was entirely in how
  the CLIENT consumed an already-correct value, never in what the
  server sent.
- **Not stale restoration state** - the failure occurs on a fresh,
  first-time `mount()` of an actively-selected Document, not a
  restored/remembered one; the remembered-thumbnails path shares the
  identical bug independently, not because of any restoration-state
  corruption.
- **Not a pre-existing invalid fixture** - the underlying file itself
  is never involved in producing this specific error text; a genuinely
  missing/corrupt file produces a different failure mode entirely (a
  404 from `source_file`, then a network-level PDF.js rejection),
  confirmed still distinct and still handled honestly (see below).

**Fix, the smallest verified change:** both call sites now pass
`{ url: url }` / `{ url: match.file_url }` instead of the bare string -
the real, verified contract this vendored build actually requires. No
Project or Document data was modified in any way to produce this fix
or make a test pass.

**Honest failure state, confirmed unaffected:** the genuinely-missing-
file case (a real, separate failure mode) still surfaces honestly - a
missing file on disk still 404s from `workspace.source_file`
(`services/case_workspace.py`'s own existing check, untouched), and
`mount()`'s own `.catch()` still calls `showLoadError()` +
`clearThumbnails()` for ANY `getDocument()` rejection reason, not just
the one this stage fixed - never a silently-undefined state passed to
PDF.js, and never a fabricated success state.

**Confirmed correct behavior, preserved and unaffected by this fix:**
only the current Project appears in opened Lists; clicking
Investigations/Documents/etc. only expands the family; clicking the
actual Document selects it; Chats loses its active highlight;
breadcrumb and Toolbox identify the selected Document; per-Project
restoration and authorization remain intact - none of this logic lives
in `pdf_viewer.js`, so none of it was at risk from either the bug or
the fix.

**Tests:** new `tests/test_p40vw7b_qa1_pdf_getdocument_fix.py` (9
tests) - the exact call-shape fix at both sites, a regression guard
against a bare-string call ever being reintroduced (scoped to the real
`pdfjsLib.` prefix specifically, after first catching and fixing a
self-collision where the guard's own broad regex matched this file's
own docstring quoting the vendored source's bare signature in prose -
the same "assertion trips on its own explanatory comment" bug class
this repo has hit before), confirmation the honest-failure path is
unaffected, and direct rendered-HTML evidence ruling out a DOM/route
cause. Re-ran the complete pre-existing LTH1/VW7A-QA2/DTAB1/document-
controls test files (197 tests) unmodified as an explicit regression
gate - all passed. No UI-reference changes were needed - no visible
structure, `data-ui-ref`, or route changed, only an internal JS
call-argument shape. Full suite: 2509 passed, 0 failed.

**Real-browser verification:** not available in this environment - the
fix itself was verified by direct inspection of the actual shipped
PDF.js source (not assumed), including locating the literal throw
statement and its surrounding async validation branch, exactly the
honest standard this repo has held to throughout. Product-owner
verification checklist: open "Nipigan Starter.pdf" (and, ideally, at
least one other previously-untested PDF, given this was a universal
defect, not fixture-specific) and confirm Display renders real pages
and Thumbnails populates; confirm a genuinely-removed/renamed file on
disk still shows the honest "could not be opened" error rather than a
silent blank state; confirm a remembered-thumbnails scenario (opening
a PDF, then navigating to an Investigation/Chat within the same
Project) also renders real thumbnails now, not just the empty state.


**Tag collision, flagged explicitly:** "CLAUDE-P40-VW7B" was already
used once before this stage, for an unrelated, already-shipped stage
(git `a61a7b8`/`9a5c11b`, "generalize active-Display projection;
relocate a misplaced admin control"). This stage reuses the same tag
because that is what its own governing prompt specified. Noted here,
in `templates/base.html`'s own comment, and in the new test file's own
module docstring so the collision is never silently ambiguous to a
future reader of git history or this file.

**Started from a verified clean state:** `HEAD == origin/main` at
`ee5a92c` (the LTH1 stage) confirmed before any edit; working tree
clean apart from the pre-existing, unrelated
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture.

**Critique of the proposed hierarchy, grounded before building anything
(Section 0's own explicit invitation to refine it):**
1. **"Foreground Project" needs no new persisted state.** This is a
   full-page-reload app (no client router) - it is already
   structurally equivalent to "the `project_id` the current URL
   names." The real defect was Lists RENDERING the portfolio even
   while a Project was open, not a missing state-tracking mechanism.
2. **The Vestibule already existed**, built in CLAUDE-P40-VW8-QA
   Section 12: `portal.choose_project` / `templates/project_chooser.html`
   (extends the Lists-free `gateway_base.html`, already reuses the
   correctly access-filtered, one-row-per-Project `_accessible_documents`).
   Extended in place rather than rebuilt (Section 4's own "least
   disruptive repository-compatible" instruction).
3. **Per-Project workspace restoration is already ~90% correct by
   construction.** DTAB1's Document tabs, LTH1's Lists/Thumbnails
   split, and EYE1's Toolbox/Eye split are all already persisted in
   `localStorage` keyed by username+`project_id` - returning to a
   different Project's URL already restores that Project's own state
   for free, with no cross-Project bleed risk (the keys are
   namespaced). Verified, not rebuilt (`PerProjectRestorationGroundingTests`).
4. **Investigation status already has a real two-state lifecycle**
   (`CASE_STATUS_OPEN`/`CASE_STATUS_ARCHIVED`, `services/case_workspace.py`)
   with a real, existing, previously-**unused-by-any-UI** governed
   completion route (`workspace.archive_case`, owner-or-admin gated -
   confirmed via `grep`, no prior caller anywhere). No "Waiting/Parked"
   governed state exists anywhere in the domain model, so Section 2's
   "use those terms only where those meanings already exist" rules out
   offering a third capacity-dialog option - only Release (pure
   attention-set change) and Conclude (the real `archive_case` action).
5. **"Four Investigation Attention Positions" is the one genuinely new
   concept**, with DTAB1's own Document-tab architecture as the direct
   template: client-side-only, `localStorage`-persisted, username+
   Project-scoped, revalidated on every load against a new LTH1-style
   JSON island (`#workspace-visible-cases-data`) - never a new backend
   endpoint or schema field.
6. **New Investigation creation already redirects straight into
   `?case=<new-id>`** (a prior, deliberate design decision - "opening a
   Project no longer auto-jumps into its first Case... a Case is only
   ever entered through an explicit `?case=`"). A newly created
   Investigation therefore correctly becomes the newly-focused
   attention position immediately - but if attention is already full,
   this exact page load is one of the "governing transitions" Section
   9 requires catching, alongside a bookmarked `?case=` URL, Back/
   Forward, and refresh - all handled uniformly by post-load
   reconciliation (see below), not a pre-click interceptor alone.

**Workspace-state vs. business-state:** enforced throughout by
construction, not by convention alone - `releaseFromAttention()`
(static/js/investigation_attention.js) only ever touches a local
`attention` array + `localStorage`, never a network request; the ONLY
code path that can change a Case's real status is the existing,
unmodified-in-behavior `archive_case` route, reached exclusively
through its own explicit "Conclude" button. Switching the Foreground
Project never writes anything server-side either - it is a plain GET
navigation.

**Opened-Project Lists correction (Section 3):** `templates/base.html`'s
Lists tree now branches on `project_id is defined and workspace is
defined` (the SAME gate Toolbox/Eye/Chat already use - needed because
a removed Project's tombstone render, `project_removed.html`, has
`project_id` in scope but never `workspace`/`document`, discovered via
a real crash while testing). When true: renders ONLY the Foreground
Project's own family branch (Overview/Documents/Investigations/RFIs/
Chats/Tasks/Tags/Project Tools), driven directly by `workspace`/
`document` rather than by finding this Project inside
`nav_recent_projects` (that list is capped at the 15 most-recently-
INGESTED projects - app.py's own documented, unfixed limitation - so
an older Project's own branch previously would not render AT ALL once
it aged out of that cap; a real latent defect this restructuring also
closes as a natural consequence). When false: the ORIGINAL portfolio
"Projects" root/`+ New Project`/`Removed Projects` render exactly as
before, unchanged - this stage's own scope is the OPENED workspace,
not portfolio browsing itself. Security/Project Data Management
(admin TOOLS, not portfolio Project-selection surfaces or "Project
records") deliberately stay reachable regardless of whether a Project
is open - Section 3's forbidden list names the PROJECTS root, other
Project names, `+ New Project`, and Removed Projects specifically, not
these. The old per-sibling-row "visual continuation" whitespace class
(`sibling-project-after-current`, CLAUDE-P40-VW7A-QA) is retired
outright - its trigger condition can no longer occur once the current
Project's own branch never renders inside the portfolio loop at all.

**Dead-code removal, a direct consequence of Section 3:** the
CLAUDE-P40-VW8 Project-switching interruption dialog
(`#project-switch-dialog`) and its click-interceptor are removed
entirely - its only trigger, `lists.projects.leaf` for a Project other
than the one open, never renders inside an open Project's Lists
anymore. Also no longer the RIGHT behavior even where reachable
(Section 6's own "do not show a confirmation merely because the user
changes Projects when state is safely persisted" - see point 3 above).
Its CSS classes (`.project-switch-dialog*`) were renamed and reused
(`.attention-capacity-dialog*`) for the new fifth-Investigation dialog
rather than duplicated - Section 13's own "do not introduce a separate
visual language."

**Project Vestibule (Section 4):** `routes/portal.py`'s `choose_project`
gained an optional `?current=<project_id>`, resolved through the SAME
already-access-filtered project list every other part of that route
already computes (never a second, separately-trusted lookup) - an
unauthorized, stale, or omitted value simply renders no "Current
Project" section, never a 404 (a soft display hint, not an
authorization boundary of its own; no new persisted "current project"
concept anywhere). `templates/project_chooser.html` gained a "Current
Project" section (excluded from "Available Projects" below it, never
duplicated) with a real, non-color "Currently entered" badge (text,
plus a border-width change, not color alone), and a link out to the
real, already-governed `portal.removed_projects` page (Section 4's own
"only if this is already a real governed repository concept" - it is,
linked rather than reinvented). Deliberately selection-only throughout
- no Documents/Findings/conversation content of any Project appears
here (verified: no `#launcher-panel`, no "Finding" text, no `conv-`
class prefix on this page).

**Header Switch-Project access (Section 5):** the Foreground Project's
own breadcrumb segment (`menu.context`'s first child) is now a real
`<a>` into the Vestibule (`portal.choose_project?current=<project_id>`),
carrying `aria-label="... — Switch Project"` since the bare visible
text (just the Project's own name) would not otherwise communicate
that activating it navigates away. Plain navigation, no interruption
dialog - per point 3 above, nothing is actually at risk.

**Project switching (Section 6) / per-Project restoration (Section
7):** no new mechanism built - verified the existing one instead (see
critique points 1/3/6 above). `PerProjectRestorationGroundingTests`
pins the exact `localStorage` key shapes for DTAB1/LTH1/EYE1/this
stage's own new attention-set, confirming all four are namespaced by
username+`project_id`.

**Four Investigation Attention Positions (Section 8):** new
`static/js/investigation_attention.js`, architecturally mirroring
`document_tabs.js` closely (a compact `role="tablist"` strip, real
`<a href="?case=<id>">` positions, roving-tabindex keyboard nav,
`[hidden]` entirely when attention is empty - "compact, visually
restrained," never a permanent empty bar). "Focused" is the URL-driven
`?case=` selection (no separate tracked concept, per critique point 1);
the ATTENTION SET (up to four Case ids, independent of which is
focused) is `localStorage`-persisted, keyed by username+`project_id`,
revalidated on every load against `#workspace-visible-cases-data` (new
JSON island, `routes/workspace.py`'s `show_workspace`, exposing only
`id`/`title`/`status`/`created_by` - real fields only, no fabricated
urgency/confidence signal, Section 8's own explicit prohibition). Each
position shows the Investigation's real title plus a real "Focused" or
"Archived" text tag (non-color cue, Section 6) alongside the existing
color treatment - never color alone. A `.attention-position-release`
button ("×") removes a position from attention WITHOUT navigating and
WITHOUT touching business status (Section 8's own explicit "must not
delete, close, resolve, archive, or otherwise falsify its real
status") - a pure `localStorage` membership change, even when
releasing the currently-focused position.

**Fifth-Investigation capacity (Section 9):** deliberately enforced via
POST-LOAD reconciliation on every workspace page render, not a
pre-click interceptor - `base.html` already runs a separate, unrelated
click-interceptor for Display-division routing (from the OTHER,
earlier "CLAUDE-P40-VW7B" stage - see the tag-collision note above);
entangling a second one with it risked both. Post-load reconciliation
uniformly covers every real entry path (an ordinary click, a
bookmark, Back/Forward, a refresh, or `create_case`'s own redirect)
rather than only the common one - genuinely the "governing transition"
Section 9 asks for, not a weaker substitute. When `?case=` names an
Investigation not already in the attention set while it's already at
4, `#attention-capacity-dialog` opens (real `role="dialog"`/
`aria-modal="true"`, reusing the renamed `.attention-capacity-dialog*`
CSS - see the dead-code note above) listing the four current positions,
each with real Release (immediate, client-side, closes the dialog and
completes the swap in place - no page reload needed, since the fifth
Investigation is already displayed) and Conclude (the real
`workspace.archive_case` route, extended with an optional `next_case`
form field - validated server-side against this reviewer's own
`visible_cases_for`, never a raw unchecked redirect target - so
concluding lands back on the Investigation the reviewer actually meant
to open, not the one just archived) actions, plus Cancel (navigates
back to the bare workspace URL/Overview - the page has already loaded
showing the fifth Investigation's own content, so "cancel" means
leaving it, not merely closing the dialog).

**Focused-Investigation behavior (Section 10):** unchanged from
existing behavior - `active_case` already drives Toolbox/Chat/Findings/
Eye exactly as before; this stage adds no new projection logic. DTAB1's
Document tabs remain completely independent of the four-position rule
(Section 10's own explicit "the four-position rule governs Investigation
subjects, not supporting Documents") - confirmed via the regression
suite (DTAB1's own 63 tests, re-run unmodified, all still passing).

**Isolation (Section 11):** `#workspace-visible-cases-data` is scoped
to the current Project only (same `visible_cases_for` privacy filter
the Lists Investigations branch already uses) - a foreign Project's
Case structurally cannot appear in the attention strip, since it never
appears in that JSON island at all. The Vestibule excludes unauthorized
Projects (reuses `_accessible_documents`, unchanged). Direct-URL access
to an unauthorized Project still 404s (unchanged - `_load_workspace_or_404`).
No UUID/project_id appears in any visible label (the header link's own
accessible name uses the display title, never the raw id).
`archive_case`'s `next_case` extension is authorization-checked the
same way every other Case reference on that route already is.

**Accessibility/responsive/Appearance (Section 13):** the new header
link and attention positions both gained real `:focus-visible` outlines
(a genuine, previously-nonexistent gap for the header link, since it
used to be a plain, non-interactive `<span>`). The capacity dialog has
real dialog semantics (`role`/`aria-modal`/`aria-labelledby`), matching
the retired Project-switch dialog's own established pattern exactly.
No new narrow-viewport mechanism was built - the attention strip
scrolls horizontally via the SAME `.document-tab-list`-established
`overflow-x: auto` idiom Document tabs already use. All new CSS is
token-driven (`var(--machine-blue)`, `var(--text-*)`, etc.), so every
established Appearance mode repaints it for free via the SAME combined
per-surface redefinition mechanism every other token-driven rule in
`main.css` already participates in - no new per-Appearance override
rule needed anywhere in this stage.

**UI-reference changes:** new — `menu.context.switch-project`,
`gateway.chooser.current`, `gateway.chooser.current.leaf`,
`gateway.chooser.available`, `gateway.chooser.removed-projects`,
`display.attention-positions`, `display.attention-positions.capacity-dialog`,
`display.attention-positions.capacity-dialog.cancel`. Retired —
`lists.project-switch-dialog`, `.stay`, `.switch`, `.open-new-tab`
(marked `retired` in `UI_REFERENCE_MAP.md`, never reused for a
different control). Retained unchanged — every `lists.project.*`/
`lists.projects*` id (only their recorded conditions/behavior
corrected to describe the new opened-vs-portfolio branching). Nothing
renumbered for tidiness. `tests/test_p40vw7a_ui_reference_map.py`'s own
registry-vs-template self-consistency check (the "registry" IS
`UI_REFERENCE_MAP.md` itself, parsed via regex - there is no separate
machine-readable registry file in this repository) passes.

**Tests:** new `tests/test_p40vw7b_vestibule_and_attention.py` (56
tests) covering every Section 15 item this stage's own scope reaches.
Updated 11 pre-existing test files in place for assertions that
targeted the now-corrected portfolio-in-open-Lists/interruption-dialog
behavior - 5 found and fixed BEFORE the first full-suite run (focused
runs against the specific files each change touched):
`test_p40dtab1_document_tabs.py`, `test_p40e2b1a_recursive_projection.py`,
`test_p40vw7a_qa_lists_hierarchy_selection_state.py`,
`test_p40vw7a_ui_reference_map.py`,
`test_p40vw8_project_switch_and_chooser.py` (retired its own five
dialog-specific test classes down to one explicit
`DialogRetirementTests` regression guard) - and 6 MORE surfaced only
by the first complete-suite run itself (files this stage's own changes
touch but that a targeted-file sweep didn't happen to include):
`test_global_search_and_header.py`, `test_home_navigation_shell.py`,
`test_p40e2b1_single_launcher_and_directories.py` (all three asserted
the "Projects" root stays rendered/highlighted inside an open
Project - now updated to assert the Foreground Project's own
`current-project` marker instead, since that root no longer renders
there at all), `test_p40e2b1a_recursive_projection.py` again (a
SECOND, different test in the same file - the header's own new
Switch-Project link legitimately adds a third occurrence of the
Project name to its own page, once as visible text and once in its
`aria-label`, not a visible duplication a sighted reviewer would ever
see), and `test_p40e3a_layout_reconciliation.py` (asserted another
Project rendered as a closed sibling leaf - now asserts it does not
render at all, the stronger, now-true guarantee). Each fix carries its
own comment explaining why. This is the concrete reason this
repository's own established convention is "run the complete suite
once, not just the files a change seems to touch" - a purely file-
scoped sweep would have shipped these six regressions.

One genuinely new, this-stage-introduced defect was also caught only
by the complete suite: two new CSS rules
(`.attention-position-focused-tag`/`-archived-tag`) were set at
`0.65rem` (10.4px), below this repository's own established, tested
11px minimum font-size floor (`test_global_search_and_header.py::
TypographyCorrectionTests::test_no_font_size_below_11px_floor`) -
raised to `0.7rem` (11.2px), the same size already used for
comparably-scaled labels elsewhere in this file (e.g.
`.document-tab-menu-btn`).

Along the way, also caught and fixed real "unanchored search matches
the wrong occurrence" / "assertion trips on its own explanatory
comment" bugs in this stage's OWN new test code (the same bug classes
this repo has hit before) - a `render();` search matching an earlier
occurrence than the one intended, and a forbidden-word check tripping
on the source's own prose explaining why that word doesn't apply -
fixed before being reported as passing, not left as latent gaps.

Also re-ran the complete pre-existing DTAB1/LTH1/EYE1/BRAND1/archive-
related test files (230+127 tests) unmodified as an explicit
regression gate before the first full-suite run - all passed, and the
full suite itself (run twice - once before, once after the six
additional fixes above) confirms no other regression exists anywhere
in the codebase. Full suite: 2500 passed, 0 failed.

**Real-browser verification:** not available in this environment -
every claim above is grounded in template/CSS/JS source inspection and
rendered-HTML structural tests, not a claimed rendered check.
Product-owner verification checklist: (1) sign in, confirm the
Gateway/Vestibule flow; (2) enter a Project, confirm Lists shows ONLY
that Project's own families, no other Project name, no `+ New
Project`, no `Removed Projects`; (3) click the Project name in the
header, confirm it opens the Vestibule with "Current Project" shown
and "Currently entered"; (4) create/open up to four Investigations,
confirm the attention strip fills with real, distinguishable positions;
(5) attempt a fifth, confirm the capacity dialog offers Release/
Conclude/Cancel truthfully, with no fabricated urgency; (6) Release one
and confirm the released Investigation is NOT deleted/archived
(reopen it from Lists to confirm); (7) Conclude one and confirm it
lands you back on the Investigation you actually meant to open, and
the concluded one shows "Archived" if it's still in attention
elsewhere; (8) switch Projects via the Vestibule, confirm the departed
Project's Lists/attention/Chat/Toolbox/Eye state is completely gone
from the rendered page and the entered Project's own state restores
independently; (9) refresh, Back/Forward, and a direct/bookmarked
`?case=` URL for a 5th Investigation, confirming the capacity dialog
still catches it; (10) log in as a second account and confirm zero
attention/Vestibule leakage; (11) Light/Black/Midnight Blue/Deep Forest
Appearance modes; (12) narrow viewport; (13) UI Reference Mode on/off,
confirming no badge overlaps the new header link or attention
positions.

## 2026-08-03 — CLAUDE-P40-LTH1: Persistent Left Lists and Page-Thumbnails Split

**Started from a verified clean state:** `HEAD == origin/main` at `6273f4f`
(the CLAUDE-P40-BRAND1 mark-geometry correction) confirmed before any
edit; working tree clean apart from the pre-existing, unrelated
`tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture.

**Cause of the missing split:** a real Lists/Thumbnails split already
existed (CLAUDE-P40-VW7A-QA2) - `.lists-pane`/`.thumbnails-pane`/
`#lists-thumbnails-divider` in `templates/base.html`. The Thumbnails
pane and its divider were both `[hidden]` by default, revealed only
once `static/js/pdf_viewer.js` decided the active Document was a PDF
(a `window.ArchioskListsThumbnailsSplit.show()`/`.hide()` API,
toggling a `.launcher-panel.has-thumbnails` class that `.lists-pane`'s
own CSS depended on to yield any height at all). That meant NO visible
split existed on Overview/Investigation/Chat/non-PDF-Document pages -
`.lists-pane`'s default `flex: 1 1 auto` filled the WHOLE column,
exactly matching the reported defect ("Project/List records continuing
uninterrupted to the bottom edge"). CLAUDE-P40-EYE1 had already solved
this identical problem for Eye relative to Toolbox by making Eye "a
permanent structural surface... never `[hidden]`" - Thumbnails was the
one remaining exception to that pattern; this stage brings it into
line, not a new mechanism.

**Structural implementation:** `.thumbnails-pane`/`#lists-thumbnails-
divider` are never `[hidden]` again; `.lists-pane` unconditionally
takes `flex: 0 0 var(--lists-height, 60%)` (the `.has-thumbnails`
class-gate removed entirely). Content, not visibility, now carries the
"nothing to show" case - a new `<p id="thumbnails-empty-state"
data-ui-ref="lists.thumbnails-pane.empty">Open a Document to view its
pages.</p>`, visible by default, toggled by `pdf_viewer.js`'s
`buildThumbnails()`/`clearThumbnails()` directly (the old cross-script
show/hide API is gone - nothing left to show/hide at the PANE level).

**Divider:** drag/keyboard mechanics (pointer drag, Arrow/Home/End,
double-click restore, Maximize toggle, `sessionStorage` persistence,
12–88% clamp) were already correct and are unchanged. Added: a real
`:focus-visible` outline (`outline: 2px solid var(--machine-blue)`) -
the pre-existing `::before` accent-line color/thickness change alone
was not a genuine focus indicator for a keyboard user, a real Section 6
gap closed here. `sessionStorage` already survives an ordinary page
refresh (its own scope is the browser tab, not a single load), so no
persistence-mechanism change was needed for "restore safely after
refresh."

**Document-context rules (the one genuinely new mechanism):** this is
a full-page-reload app, so "remembered Document context" means
client-side persistence + revalidation on the next load, not an
in-memory carry-over. `pdf_viewer.js` gained `mountRememberedThumbnailsIfAny()`,
run only when the current page has no Document of its own selected at
all (`#document-tab-strip`'s own `data-selected-source-id` is empty -
Overview, an Investigation, Chat, or no Project open). It reads a
`localStorage` key scoped by username+Project
(`beehive:panel:last-pdf-source:<username>:<projectId>`, matching
`document_tabs.js`'s own established key shape), revalidates the
remembered id against `#workspace-active-sources-data` (the SAME
authorized, Project-scoped JSON island every other client-side feature
in this shell already trusts - extended with one new boolean field,
`is_pdf`, computed server-side in `routes/workspace.py` via the exact
same `file_path.lower().endswith(".pdf")` test `case_workspace.html`'s
own Display branch already uses), and only then loads that PDF via
PDF.js purely to build its thumbnail list (no live canvas, no full
`mount()`). A stale/removed/unauthorized remembered id clears itself
(`localStorage.removeItem`) and falls through to the empty state -
never a broken reference. `mount()` itself now calls
`rememberLastPdfSource(currentSourceId)` on every REAL successful PDF
load, so the pointer always reflects the last Document actually
viewed - never an arbitrary "first Document in the Project" guess
(Section 3's explicit prohibition; grounded via source inspection, not
assumed). A thumbnail click in this remembered-only mode
(`thumbnailsOnlyMode`) is a real navigation to the Document route
(landing on the clicked page, via the SAME `localStorage` view-state
store `mount()` already reads on load) rather than `goToPage()`, since
there is no live canvas on the current page to render into. Switching
to a DIFFERENT, non-PDF Document deliberately does NOT surface the
remembered PDF's thumbnails - a newly-selected Document (of any kind)
is itself now "the" active Document context, and a non-PDF one
honestly has no pages, so the pane's default empty state is correct
there, not a stale unrelated PDF's thumbnails.

**Empty-state behavior:** quiet, compact, token-styled text - no
Project/List records rendered inside the pane at any point. Never
auto-selects a first Document (verified both by source inspection - no
`sources[0]`-style shortcut anywhere in the remembered-context code -
and a dedicated test class).

**Responsive:** no new narrow-viewport mechanism - `.launcher-panel`
already becomes a real overlay drawer at `max-width: 640px`
(CLAUDE-P40-E2B1); Thumbnails, now a permanent CHILD of that panel,
reflows inside the drawer automatically, the same way Toolbox+Eye
already reflow together as one column-becomes-drawer unit at that
width (CLAUDE-P40-EYE1). The vertical Lists/Thumbnails split is
height-based, orthogonal to the drawer's own width change, so nothing
further was needed - grounded in the existing rule, not invented.

**Accessibility:** divider keeps its existing `aria-label`/`role=
"separator"`/keyboard stepping, now with a real focus outline (above).
Closed a genuine pre-existing gap in Section 6's own "selected-page
indication that does not rely on color alone" requirement: the current
thumbnail used to be border-COLOR + background-color only; now also
`border-width: 3px` (a real 2px→3px geometry change) plus
`font-weight: 700`/`text-decoration: underline` on its page-number
label - both non-color cues, alongside the existing color ones, not
replacing them.

**Isolation:** `lastPdfSourceKey()` is scoped by BOTH username and
Project id (matches `document_tabs.js`'s own established cross-account
guard) - a foreign Project's remembered pointer can never even be
looked up from a different Project's page load, and two reviewers on
the same shared browser never see each other's remembered Document.
`activeSourcesFromJson()` reads the SAME server-computed, already-
authorization-filtered JSON island every other feature in this shell
trusts (confirmed via the pre-existing `DivisionAuthorizationTests` in
`tests/test_p40e2b_flexible_workspace_frame.py`, re-run unmodified) -
a removed/unauthorized Source never appears in it at all, so a
remembered id pointing at one always fails the revalidation and falls
to the empty state. No route touched by this stage accepts anything
but GET, and no test observed any Project/Document data change merely
from viewing a page.

**UI-reference changes:** `lists.thumbnails-pane.empty` (new). Every
other id in this region (`shell.lists-thumbnails-divider`,
`lists.thumbnails-pane`, `lists.thumbnails-pane.maximize`,
`lists.thumbnails-pane.list`) retained unchanged - only their recorded
*behavior* in `UI_REFERENCE_MAP.md` was corrected to describe the
permanent-pane treatment instead of the old show/hide gating. Nothing
renumbered or reparented elsewhere in the map.

**Tests:** new `tests/test_p40lth1_persistent_lists_thumbnails.py` (38
tests) covering structural panes, the empty state, the remembered-
context mechanism and its isolation properties, the `is_pdf` field,
divider accessibility, the non-color current-page cue, narrow-viewport
reasoning, Appearance coverage, and a regression spot-check against
EYE1/BRAND1/Chat/Document navigation. Updated
`tests/test_p40vw7a_qa2_thumbnails_annotations_layout.py` in place for
every assertion that targeted the now-corrected hidden-by-default
behavior (renamed/rewritten, not deleted) - along the way, caught and
fixed two real "unanchored search matches the wrong, earlier
occurrence" bugs in this stage's OWN new test/comment text (the same
bug class this repo has hit before): a `_rule_body` lookup for
`.lists-thumbnails-divider:focus-visible` initially matched the
earlier `:focus-visible::before` compound selector instead, and a
`assertNotIn("window.ArchioskListsThumbnailsSplit", ...)` guard
initially tripped on this stage's OWN explanatory comment mentioning
that literal string in prose - both fixed before being reported as
passing. Also re-ran the complete pre-existing DTAB1/EYE1/document-
controls/workspace-frame test files (175 tests) unmodified as an
explicit regression gate - all passed.

One genuinely pre-existing test broke for an honest reason, not a bug
in this stage's own code: `tests/test_p40e3a_layout_reconciliation.py`
`DisplayBlankByDefaultTests::test_blank_when_nothing_selected` searched
the WHOLE page body for the substring "empty-state" to guard against
Display's own blank state accidentally rendering something wrong - it
never anticipated a legitimate, unrelated `#thumbnails-empty-state`
element existing elsewhere on the SAME page (Lists' own permanent
Thumbnails pane, always rendered now). Fixed by scoping that test's
check to the Display region itself (`#workspace-display-panel`
through `</main>`) - its own actual subject - rather than the whole
body; not weakened, still forbids everything it originally forbade,
just where it always meant to look.

Full suite: 2455 passed, 0 failed.

**Real-browser verification:** not available in this environment -
every claim above is grounded in template/CSS/JS source inspection and
rendered-HTML structural tests, not a claimed rendered check.
Product-owner verification checklist: (1) open a Project workspace
with no Document selected - Thumbnails shows the empty state, visibly
divided from Lists; (2) open a PDF Document - thumbnails appear,
current page indicated with both color AND shape/weight cues; (3)
select several thumbnails, confirm Display/current-page sync both
ways; (4) drag AND keyboard-resize the divider, confirm a visible
focus outline while doing so; (5) refresh and confirm the split
proportion restores; (6) navigate from an open PDF Document into a
related Investigation or Chat within the same Project - thumbnails
should remain, not clear; (7) open a DIFFERENT, non-PDF Document -
thumbnails should show the empty state, not the previous PDF's pages;
(8) switch Projects and confirm zero thumbnail/remembered-context
leakage either direction; (9) log in as a second account in the same
browser and confirm zero leakage; (10) Light/Black/Midnight Blue/Deep
Forest Appearance modes; (11) a narrow viewport - confirm the Lists
drawer still reaches both regions without covering Display/Chat/
Toolbox/Eye; (12) UI Reference Mode on/off, confirm the new
`lists.thumbnails-pane.empty` badge doesn't overlap the message text.

## 2026-08-03 — CLAUDE-P40-BRAND1 (correction): Replace the parabola mark with a deterministic straight-line "bottleneck" mark

Product-owner correction to the mark's own geometry - everything else
from the original CLAUDE-P40-BRAND1 stage below (header wiring, type
hierarchy, `--brand-gold` token family + contrast verification, the
combined per-Appearance token-redefinition wiring, UI-reference-badge
reasoning, pre-auth-scope exclusion) is unchanged and still accurate;
only the SVG path data inside `archiosk_mark` (`templates/_macros.html`)
was replaced.

**New construction, exactly five visible elements, explicitly no
curves of any kind (the prior version's two quadratic-Bezier legs are
gone outright, not layered alongside):** two mirrored, asymmetrical
straight-line open angles - a short arm rising up-and-outward from a
vertex, and a longer leg descending down-and-outward, giving each
angle a "standing, leaning" character (`M17 9 L29 27 L12 57` left,
its exact horizontal mirror `M47 9 L35 27 L52 57` right, viewBox
`0 0 64 64`, `stroke-width="5"`). The two inner vertices (x=29, x=35)
deliberately do not touch - a real 6-unit "bottleneck" gap - with one
small filled dot (`fill="currentColor"`, not stroked) on the
centreline just below it, conceptually the one grain that passed
through. Reads as a minimal pair of opposing angles / an abstract "A"
without ever drawing a crossbar. Coordinates used exactly as supplied
(mirror-checked: `64 - x` for every point, confirmed exact) rather than
adjusted, since they already satisfy every stated constraint (shorter
arm/longer leg, non-touching gap, dot below the gap).

**Verification, honestly bounded:** no real browser/SVG-rendering tool
exists in this environment (unchanged from every prior stage's own
disclosure), and no SVG rasterizer library (`cairosvg`/`svglib`) is
installed in the venv either. Built a small one-off Pillow-based
rasterizer (session scratchpad, not committed - approximates
`stroke-linecap`/`-linejoin="round"` by stamping filled circles at
every vertex/endpoint) to actually render the exact path/circle
coordinates at 24px/32px/64px, supersampled 8x and downscaled for a
closer approximation of anti-aliased rendering, against both a dark
canvas swatch (`--dark-brand-gold` on `#1E1A12`) and the real Light
`--canvas`/`--brand-gold` pairing. At all three sizes the two unequal
mirrored angles, the central gap, and the dot below it remained
visually distinct and legible on both backgrounds - a real, if
approximate, rendered check, not a claimed one. This does not replace
an eventual real-browser walkthrough across all four Appearance modes
and both viewport extremes, which remains unverified the same way
every prior stage's equivalent claim has been stated honestly rather
than fabricated.

**Tests:** `tests/test_p40brand1_brand_mark.py`'s `MacroGeometryTests`
rewritten for the new construction (exactly 2 `<path>` + 1 `<circle>`,
no Q/C/A curve commands, no crossbar, each angle's arm shorter than its
leg, exact horizontal mirror between the two paths, non-touching inner
vertices, dot centred on the viewBox mid-line strictly below the gap,
dot filled not stroked, `viewBox="0 0 64 64"`/`stroke-width="5"`) -
`RepositoryGroundingTests`' path-data needle updated to match. All
other test classes in that file (header markup, rendered-HTML,
CSS/token/contrast) were unaffected by this correction and needed no
changes. Full suite: 2415 passed, 0 failed.

## 2026-08-03 — CLAUDE-P40-BRAND1: Top-Left ARCHIOSK Brand Treatment

**Grounding, before any code:** searched the whole repository for an
existing mark/medallion/icon to reuse (`svg`, `parabola`, `medallion`) -
none exists (no `.svg` file, no inline `<svg>` beyond the annotation-
toolbar glyphs, no favicon). "Reuse the same mark" wasn't literally
possible; reported this honestly and designed one new mark instead,
built as the single shared source the request actually asked for.

**The mark** (`archiosk_mark` macro, `templates/_macros.html`): two
real parabola legs, not a freehand approximation of one - SVG's
quadratic-Bezier `Q` command traces a literal parabola segment, so
`M 14 90 Q 22 42 50 12` (left leg) and its mirror `M 86 90 Q 78 42 50
12` (right leg, sharing the same apex) are mathematically true
parabolas by construction. Crossbar (`M 22 58 L 78 58`) placed by
solving where the left leg's own Bezier curve crosses y=58
(`9u²+30u-23=0` → `u≈0.643` → `x≈22.3`, mirrored to `≈77.7`), not
eyeballed. `stroke="currentColor"` means the ONE macro definition
already repaints correctly across every Appearance with zero color
logic inside the SVG - a future circular "medallion" badge treatment
(not built this stage, nothing to reuse yet) would call this same
macro rather than drawing a second copy. Always `aria-hidden="true"`/
`focusable="false"` - decorative in this stage's one use.

**Wired into the header** (`templates/base.html`'s `menu.brand` link):
icon and "Archiosk" now share the SAME `<a>` (one tab-stop, one
accessible name - `aria-label="Archiosk Home"`, since the SVG stays
hidden from the accessibility tree). `href`/`data-ui-ref="menu.brand"`/
navigation target completely unchanged - only the visible content and
accessible name are new.

**Type hierarchy correction** (`static/css/main.css`): "Archiosk" used
to be 0.85rem/`--text-metadata` (muted, secondary) - smaller and dimmer
than `menu.context`'s own breadcrumb (0.88rem/`--text-primary`),
backwards from identity branding. Now 1.2rem/600 via a real flex row
(`.workspace-topbar-brand-text`), genuinely larger/richer than the
breadcrumb. Checked `.workspace-topbar-context`'s ACTUAL current values
before touching anything - already 0.88rem/normal-weight, already
within the suggested 14-16px/normal-weight secondary range - left
deliberately unchanged rather than making an unneeded edit.
`.workspace-topbar`'s own `padding: 0.6rem 0` untouched, so header
height is not increased.

**Color:** new `--brand-gold` token family in `static/css/tokens.css`
(light value independently tuned + one shared dark value reused across
Black/Midnight Blue/Deep Forest, the same convention `--tabcolor-*`
already established) - kept separate from `--tabcolor-gold` despite
both being "gold," since this file's own discipline names tokens for
MEANING (brand identity vs. Document-tab accent), not raw appearance.
Considered and ruled out reusing `--bee-yellow` (documented as
icon-level-fill-only, and a bright saturated yellow unsuited as a thin
foreground/stroke color on light canvas - its current role is a
background fill with dark text on top, a different contrast case).
Verified via `tools/check_contrast.py`, extended with 4 new pairings at
the STRICTER 4.5:1 normal-text floor (not the 3.0 accent/badge floor
used for tab colors) - "Archiosk" is small, always-visible identity
text, not an occasional badge. All 4 pass with real margin (6.78:1 to
11.41:1 - see the tool's own output, not eyeballed).

**Per-Appearance wiring, and a real bug caught by an existing test:**
`.workspace-topbar` is already one of the combined "owned surface
roots" (`main.css`, alongside `.app-shell`/`.launcher-panel`/`.app-main`/
`.workspace-right-column`/`.chat-region`) that locally redefines the
standard token names per Appearance so every existing `var(...)` rule
repaints for free. First attempt instead added three standalone
`.workspace-topbar.appearance-dark .workspace-topbar-brand { color:
var(--dark-brand-gold); }`-style rules - which broke `tests/
test_p40vw8qa_theme_foreground_contrast.py`'s
`PerSurfaceScopingCompletenessTests`: that new selector is a literal
string-prefix of the real combined block's own selector, placed earlier
in the file, so the test's unanchored `.index()` search for
`.workspace-topbar.appearance-dark` started matching the new small rule
instead - the exact "unanchored search matches the wrong, newly-
inserted occurrence" bug class this repo has hit before (see the DTAB1
entry below). Root-cause fixed properly rather than patched around:
removed the three standalone rules and instead added `--brand-gold:
var(--dark-brand-gold)` (and `--tint-`/`--forest-`) directly inside the
three existing combined redefinition blocks, so `.workspace-topbar-
brand`'s own `color: var(--brand-gold)` now repaints per Appearance the
same way every other token-driven rule in the file already does - no
separate override rule needed at all. Also had to rephrase this fix's
own explanatory CSS comment once, since its first draft's prose
happened to contain the literal shadowing selector string and
re-triggered the same collision.

**UI-reference badge non-overlap:** `.ui-reference-mode-active
[data-ui-ref]::after` renders its label via `transform: translateY(
-100%)`, entirely ABOVE the referenced element's own box - independent
of that element's height, so the icon/text becoming taller doesn't
change this. `data-ui-ref="menu.brand"` stays on the SAME outer `<a>`
(not duplicated onto the inner `<svg>`/`<span>`) - the badge mechanism
is otherwise completely unmodified by this stage. `.workspace-topbar-
identity`'s own `overflow: hidden` is a pre-existing property, shared
identically by `menu.context` right next to it in the same container -
not something this stage introduces or worsens.

**Narrow-viewport reasoning:** `.workspace-topbar` already has
`flex-wrap: wrap`; `.workspace-topbar-identity` already has `min-width:
0`/`overflow: hidden`. This stage doesn't change either - only the
brand link's own intrinsic content width grew slightly (24px icon +
0.4rem gap + larger text). No real browser tool exists in this
environment to visually confirm the reflow; this is a structural read
of the existing, pre-established responsive mechanism, not a claimed
walkthrough.

**Pre-auth zero-state explicitly not touched:** `.gateway-logo`/
`.entry-shell-mark` (a separate, deliberately minimal `<div
class="gateway-logo">A</div>` brand block in `auth_shell.html`/
`gateway_base.html`) is out of scope - the request's own wording is
"the application's top-left menu/header," the AUTHENTICATED shell.

**Tests:** new `tests/test_p40brand1_brand_mark.py` (32 tests) -
macro geometry (two `Q` legs, shared apex, crossbar, `currentColor`,
decorative attributes, default size in the suggested 22-26px range),
header markup (single anchor/tab-stop, accessible name, `data-ui-ref`
preserved and not duplicated), rendered-HTML checks across `/`,
`/projects`, `/upload`, CSS (flex row, type-scale values, breadcrumb
left untouched, `--brand-gold` redefined in the shared owned-surface
scoping blocks, a guard against reintroducing the shadowing descendant
rule, header padding unchanged), token-family checks (all 4 Appearance
variants defined, dark/tint/forest share one value), and a real
contrast-ratio check against `tools/check_contrast.py`'s own live
numbers (not re-derived math). Also updated one pre-existing test
(`tests/test_global_search_and_header.py::HeaderAndBrandTests::
test_brand_lockup_reads_archiosk_only`) whose selector assumed the
brand link's visible text sat directly after `href="/">` with no
markup between - true before this stage's icon, now updated to a
plain-substring check (the SVG spans multiple lines, so a single-line
regex doesn't fit) that still pins down the actual, unchanged intent:
the visible wordmark text reads "Archiosk" only, nothing appended.
Full suite: 2407 passed, 0 failed.

## 2026-08-03 — CLAUDE-P40-DTAB1: Preview, Pinned, Colored, Renamed, and Hidden Document Display Tabs

**Started from a verified clean state:** `HEAD == origin/main` (`3098b6c`)
confirmed before any edit, working tree clean apart from the
pre-existing, unrelated `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
scratch fixture. No prior unpushed work existed to mix in - the
earlier-queued top-left brand-mark request had no code changes yet and
was set aside cleanly, to resume after this stage per the product
owner's own explicit priority signal.

**Repository-grounded design review (Section 1), findings:**

1. **Full-page-reload app, no client router** (`routes/workspace.py`'s
   `show_workspace`) - a tab is therefore a real `<a href="?source=
   <id>">`, never client-side routing invented for this stage. Stable
   URLs, direct links, and browser Back/Forward all keep working
   exactly as before, for free.
2. **Per-tab PDF viewer state can't live in a persistent in-memory
   instance** (there isn't one - every tab switch is a real page
   reload) - it has to be persisted (`localStorage`) and restored on
   the NEXT `mount()` for that same Document, keyed by source id.
3. **Tab metadata (pinned/hidden/alias/color) is a pure client-side
   workspace preference** - never a backend/schema change. Scoped by
   BOTH username (`session.get('username')`, already exposed via
   `current_username`) AND Project id - the first genuinely per-account
   preference this app has built, so this is a real, new requirement
   (existing per-project keys like `beehive:panel:toolbox:<id>` never
   needed a username segment, since they were reviewer-agnostic by
   original design).
4. **Server-side authorization revalidation reuses the EXISTING
   `#workspace-active-sources-data` JSON island** - the SAME authorized,
   Project-scoped data `populateDivision` already reads. Client JS
   cross-references every persisted tab entry against it on load and
   drops anything stale/unauthorized. Zero new backend endpoints.
5. **Toolbox/Thumbnails already follow whichever `?source=` the current
   page reflects** (server-rendered per-request) - no extra wiring
   needed there beyond tab links pointing at the correct URL.

No genuine architectural, authorization, destructive-migration, or
data-integrity conflict found - proceeded per Section 1's own "stop
only if a conflict is discovered" instruction.

**What was built:**

- **Tab strip** (`templates/case_workspace.html`, Division-0-only,
  suppressed inside a `panel_only` render): `#document-tab-strip`
  (`role="tablist"`), server-rendered `[hidden]` and entirely empty -
  `static/js/document_tabs.js` builds every tab client-side. An "All
  Tabs" `<details>` overflow control (Close All Tabs + a Hidden Tabs
  list) sits at the strip's own trailing edge.
- **Preview tab** (Section 4): single-clicking an unopened Document in
  Lists becomes the ONE replaceable preview tab (`sessionStorage`,
  cleared on session end unless converted). Selecting another unopened
  Document replaces it; selecting an already-pinned Document activates
  that tab instead, never touching the preview. Visually distinguished
  without color alone (italic label + dashed active-underline).
- **Pinned tabs** (Section 5): double-click, "Keep Open" menu action, or
  applying a rename/color all convert a preview to pinned
  (`localStorage`, keyed by username+Project). Never replaced by later
  preview navigation. Revalidated against `active_sources` on every
  load - a stale/removed/unauthorized entry is silently dropped, never
  exposed.
- **Per-tab PDF viewer state** (Section 6, `static/js/pdf_viewer.js`):
  page/zoom/rotation/scroll position/search query text persisted
  (`localStorage`, keyed by username+Project+source id) and restored on
  `mount()` instead of always resetting to page 1/100%/0°. Debounced
  writes (400ms) plus a synchronous `pagehide` flush so a fast tab
  click right after a change can't lose it. The restored search QUERY
  TEXT is repopulated but deliberately NOT auto-re-run - re-running it
  would jump to its first match and could silently override the
  just-restored page, the unsafe half of "where safe and appropriate."
- **Rename/alias** (Section 7): a real inline `<input>` (never `window.
  prompt()`, matching this app's own established convention), rejects
  empty/whitespace-only and case-insensitive duplicate aliases within
  the same user's Project tab workspace with an inline message. Restore
  Original Name clears the alias only - never touches the Document.
  Accessible name always includes the original Document name even when
  aliased ("*alias*, originally *name*"), plus a `title` tooltip and a
  "Show Original Document Name" menu action.
- **Curated color** (Section 8): 7 organizational accents (Gold/
  Turquoise/Lapis/Terracotta/Green/Purple/Default) as a thin top-border
  stripe only, never a fill - the active tab's own weight/background/
  underline are the real, non-color state cue. New `--tabcolor-*` token
  family in `static/css/tokens.css` (light values + one shared dark
  value reused across Black/Midnight Blue/Deep Forest, the same pattern
  every other accent color in that file already follows), verified via
  `tools/check_contrast.py` (extended with 38 new pairings, all real
  margin above the 3:1 accent-text floor - not eyeballed).
- **Hide/unhide** (Section 9): hiding a pinned tab preserves its alias/
  color/pin state, removes it from the visible strip only. If the
  hidden tab was active, falls back to the most-recently-used visible
  tab, then the preview, then a clear empty Display state (a real
  navigation to the bare workspace URL). Unhide (from the Hidden Tabs
  list) restores it to the strip and activates it.
- **Tab action menu** (Section 10): a real popover per tab, only the
  state-applicable actions shown (e.g. "Keep Open" only on a preview,
  "Restore Original Name"/"Default Color" only when set, "Hide Tab" not
  offered on a preview). Close removes only that tab's workspace state -
  never the Document, never a `fetch()`/`XMLHttpRequest` call, no
  invented dirty-state warning (there is no mutable state to lose).
  Close Others keeps exactly the one tab.
- **Identity/navigation** (Section 11): one stable tab entry per source
  id - activating an already-open Document updates that SAME entry
  (`lastActiveAt`) rather than creating a duplicate. Alias/color/
  visibility/pin/view-state never become identity. Individual `.
  document-tab` elements are a repeated pattern, left without their own
  `data-ui-ref` (the same convention `.thumbnail-row` and `lists.
  project.documents.leaf` already establish) - no UUID exposure risk.
- **Accessibility** (Section 12): real `tablist`/`tab` roles, roving
  `tabindex` (0 on the focused/active tab, -1 on the rest), Left/Right/
  Home/End move focus, Enter (native `<a>`) and an explicit Space
  handler both activate, Escape closes any open menu, every menu/color/
  rename/hidden-tab-restore control is keyboard-reachable.

**Not built this stage, per Section 10's own explicit deferral:** tab
reordering, tab groups, split Display panes, cross-Project tabs -
recorded here as future possibilities, not started.

**Tests:** new `tests/test_p40dtab1_document_tabs.py` (62 tests -
markup/CSS/JS-source coverage for every section above, contrast
verification via the real tool, existing-behavior preservation, no-
fetch/no-prompt/no-false-dirty-warning guards). Fixed a real anchor
bug discovered in the immediately-prior EYE1 scrollbar-theming test
file (`tests/test_p40eye1_scrollbar_theming.py`): its own unanchored
regex searches for the FIRST `::-webkit-scrollbar-thumb`-family rule in
the file started silently matching this stage's own NEW `.document-
tab-list` scrollbar rules instead of the original 8-container combined
block once this stage's CSS was inserted earlier in the file - one of
the three affected assertions actually failed (caught immediately);
the other two happened to still pass by coincidence (asserting a
substring, like `var(--machine-blue)`, that both the old and
wrongly-matched new rule equally contain) - a "passing for the wrong
reason" case, fixed alongside the one that visibly failed, not left as
a latent gap. Full suite: see this stage's own commit message for the
exact count.

**Real-browser verification:** not available in this environment -
every claim above is grounded in template/CSS/JS source inspection,
rendered-HTML structural tests, and `tools/check_contrast.py`'s own
real numeric output, not a claimed rendered check. Product-owner
verification checklist: (1) single-click preview, replace-only-the-
preview, double-click-to-pin, no duplicate tab for one Document; (2)
pinning multiple Documents and switching between them restores each
one's own page/zoom/rotation/scroll independently; (3) rename a tab,
confirm the Document's real name in Lists is unchanged, confirm the
tooltip/menu still surfaces the original name; (4) apply every curated
color across Black/Midnight Blue/Deep Forest/Light, confirm the active
tab is still identifiable with color removed (e.g. grayscale
screenshot); (5) hide/unhide both an active and an inactive tab,
confirm the active-hidden fallback lands somewhere sensible; (6)
reload and confirm restoration (pinned tabs return, preview does not
unless it was the active navigation target); (7) switch Projects and
confirm zero tab leakage either direction; (8) log in as a second
account in the same browser and confirm zero tab-name leakage; (9)
exercise the tab-strip overflow at a narrow viewport; (10) keyboard-
only tab navigation (Left/Right/Home/End/Enter/Space, menu, rename,
hidden-tab restore); (11) confirm PDF controls and Thumbnails still
follow the active tab; (12) confirm no white default gutters/
scrollbars/menus anywhere in the new tab strip.

**Note on theme names:** this stage's prompt referred to "Black, Deep
Blue, Deep Purple, and Soft Light" - this repo's actual approved theme
set (CLAUDE-P40-VW8-QA) is Black, Midnight Blue, Deep Forest, and
Light, consistent with the same note on the two entries below. All
reasoning above uses the real names.

## 2026-08-03 — CLAUDE-P40-EYE1 (browser correction): Remaining Unthemed Toolbox Scrollbar

A real-browser screenshot found one nested scroll container inside the
upper-right Toolbox/Findings region still rendering the browser's own
default white-track/gray-thumb scrollbar, despite `.workspace-pane-
toolbox` already carrying a `scrollbar-color` declaration from the
prior EYE1 build.

**Root cause, found by inspecting what property was actually set,
not by guessing at an unattached screenshot's contents:**
`scrollbar-color` is the newer, standards-track CSS property - Firefox
has always supported it, but Chromium/Edge only gained support in v121
(January 2024). On any Chromium build older than that, the property is
silently ignored entirely and the browser falls back to its own
default rendering - exactly matching "still white," even though the
CSS was technically correct per spec.

**Fix:** added the older, far more broadly-supported WebKit/Chromium
`::-webkit-scrollbar` pseudo-element API (`-track`/`-thumb`/
`-thumb:hover`/`-thumb:active`/`-corner`) ALONGSIDE the existing
`scrollbar-color` on every real scroll container in the app, not just
the one specifically reported (Section 8 of that message's own "check
all nested... scroll containers" instruction): `.lists-pane`,
`.thumbnails-list`, `.workspace-pane-toolbox`, `.eye-pane-body`,
`.eye-canvas-viewport`, `main` (Display's primary scroll region),
`.document-viewer-canvas-container` (the PDF viewer), and
`.conversation-thread` (Chat's message history) - the last four of
which turned out to have NEITHER property at all yet, a genuine
pre-existing gap the audit also caught. Track/corner use
`var(--surface-primary)`; thumb uses `var(--border-strong)` at rest and
`var(--machine-blue)` on hover/active (WebKit's own equivalent of
"visible hover/active scrolling states" - there is no dedicated
`:focus` pseudo-class for scrollbar parts, so the container's own
`:focus-visible` outline, already present on the keyboard-focusable
ones, covers focus instead). `background-clip: padding-box` + a
transparent border keeps the thumb visually inset from the track edges
while still using the browser's own real, proportional thumb-length
calculation - never a faked/hardcoded thumb size. Scroll mechanics
(`overflow`) on every container are completely unchanged - this
correction only ever adds scrollbar PAINTING.

Explicitly NOT touched, per this message's own boundary: no conversion
of this or any other scroll region into the "dual-axis medallion" -
that remains a separately-verified, not-yet-built pilot concept.

**Tests:** new `tests/test_p40eye1_scrollbar_theming.py` (9 tests -
`scrollbar-color` present on all 8 real scroll containers,
`::-webkit-scrollbar` pseudo-elements present and theme-token-based
(not hardcoded white/gray) on all 8, hover/active thumb states,
proportional-thumb construction, `overflow` mechanics unchanged, no
opacity used). Full suite: see this stage's own commit message for the
exact count.

**Real-browser verification:** still not available in this
environment - no screenshot was actually attached to this message
either, only a text description; the root-cause diagnosis above is
grounded in checking which CSS property was actually declared and
researching its real, versioned browser support, not in guessing at
image contents. Product-owner verification checklist: (1) every
scrollbar in the app (Lists, Thumbnails, Toolbox/Findings, Eye's body
and its image canvas, Display's main content area, the PDF viewer, and
Chat's message thread) shows a themed track/thumb/corner, not the
browser default, in Black, Midnight Blue, Deep Forest, and Light; (2)
the thumb visibly changes color on hover and while actively being
dragged; (3) scroll behavior (wheel, drag, keyboard, touch) is
unchanged from before this correction; (4) narrow viewports show the
same themed treatment.

## 2026-08-03 — CLAUDE-P40-EYE1 (browser corrections): Horizontal Expansion, Two-Dimensional Maximize, Scalable Canvas, and a Real Shell-Theming Bug Fix

Two real-browser checks of the EYE1 entry below reported further gaps,
plus a genuinely separate visual defect report ("thick white/cream
strips" on several workspace edges) that led to finding and fixing a
real bug in the EARLIER CLAUDE-P40-VW7A-QA2 shell-theming work. All
fixed within EYE1's own scope (no EYE2 features).

**Real bug found and fixed: `.app-shell` was never actually in the
appearance-mode selector lists.** The VW7A-QA2 browser-correction round
built a JS mechanism to piggyback an `.appearance-dark`/`-tinted`/
`-deep-forest` class onto `.app-shell` (so shell chrome like panel
dividers would have a themed fallback background) and gave `.app-shell`
a `background: var(--surface-primary)` declaration — but never actually
added `.app-shell` to the three combined CSS selector lists
(`.workspace-topbar.appearance-dark, .launcher-panel.appearance-dark,
...`) that redefine `--surface-primary`/`--canvas`/etc. per mode. The
JS class was applied correctly; there was simply no CSS rule that class
ever matched, so `.app-shell`'s own `--surface-primary` always resolved
to the unthemed `:root` Light default regardless of which class was
present — exactly reproducing "white/cream strips" anywhere shell
chrome relied on it in a dark mode. Found via direct code inspection
(`grep -n "app-shell\.appearance" static/css/main.css` returned nothing)
after a real-browser report, not by guessing at the screenshot's exact
pixel content (no image was actually attached to that message — only a
text description of marked edges). Fixed by adding `.app-shell` to all
three combined rules; a regression-guard test
(`test_app_shell_is_actually_in_the_combined_appearance_selector_lists`)
added so this specific class of bug (JS-only half of a fix shipped
without its CSS-only half) can't silently recur.

**1. Draggable right-column width.** `#toolbox-divider` (existing,
click-to-collapse/show) is now ALSO a real, mouse-draggable and
keyboard-operable (`ArrowLeft` widens/`ArrowRight` narrows, matching
drag direction) width resize handle for `.workspace-right-column` —
`width` is now `var(--right-column-width, min(340px, 30vw))` instead of
a fixed value. A genuine drag (movement past a small pixel threshold)
is distinguished from a plain click via a capture-phase click
interceptor (fires before the pre-existing bubble-phase toggle handler
regardless of script registration order), so an ordinary click still
collapses/shows exactly as before. Practical minimums: `RIGHT_MIN=260px`
in the drag-clamp logic, `CENTRE_MIN=320px` enforced both in that same
clamp logic AND as a real CSS floor on `.workspace-main-column` (defense
in depth). `ew-resize` cursor, the same `.dragging`-class accent
treatment as every other divider in this file. Persisted via
`localStorage`, per-Project (`beehive:panel:right-column-width:<id>`).
Hiding the column (`html.toolbox-hidden`) still `display:none`s it
entirely regardless of the stored width — no leftover reserved space.

**2. Two-dimensional Maximize Eye.** `#eye-maximize-btn` previously only
adjusted `--toolbox-height` (the Toolbox/Eye vertical split); it now
ALSO drives `.workspace-right-column`'s own width via a new
`window.ArchioskRightColumnWidth` API the width-drag script exposes
(`apply`/`current`/`maxForMaximize`/`DEFAULT_WIDTH`) — collapsing
Toolbox's height AND expanding the column to the largest practical
width (computed from the real current viewport width minus Lists' own
current width minus the centre column's practical minimum) in one
action. "Restore Eye" reverts both dimensions to their exact
pre-maximize values. The maximized width is deliberately never
persisted (only the last NORMAL width is) — a mid-maximize page reload
starts from the last real width, not the maximized one, so the reviewer
can never get trapped there. A conflicting Toolbox-own maximize (if
active) is reset first to avoid two controls fighting over
`--toolbox-height` at once.

**3. Responsive zoom/pan image canvas.** `static/js/eye_pane.js` was
substantially rewritten: the old small, fixed-size `<img>` preview
(`max-width/max-height: 100%` inside a much larger, centered drop
target) is replaced by a real canvas (`#eye-canvas`, `[hidden]` until an
image loads) with Fit/zoom-in/zoom-out/Actual-size(100%)/Reset controls
plus a Remove control. Fit computes `Math.min(viewport width / natural
width, viewport height / natural height)` — not capped at 1, so a small
image is scaled UP to genuinely use the available Eye area, matching
the report's own "must not remain a small thumbnail." The image's
`width`/`height` are set as real pixel values (`natural × scale`), never
CSS percentage-based sizing, so there is no stretching/distortion at any
zoom level (aspect ratio preserved by construction, both axes scaled by
the identical factor). Panning is native browser scroll
(`overflow: auto` on the viewport, the image sized to its own real
scaled pixels) rather than hand-rolled pointer-drag — real keyboard
(Page Up/Down, arrows) and touch/trackpad support for free. Mouse-wheel/
trackpad zoom is active only while the viewport itself has focus (the
report's own explicit "when focused" wording), so scrolling the page
near Eye is never accidentally hijacked. A `ResizeObserver` on the
viewport recalculates Fit automatically on any container resize — the
Toolbox/Eye divider drag, the new right-column width drag, or Eye
maximize/restore, all just resize the SAME observed element — but only
while still in "fit" mode; a deliberate manual zoom is tracked
separately and never silently overridden by a resize.

**Tests:** two new files — `tests/test_p40eye1_correction_resize_canvas.py`
(36 tests: width drag mouse/keyboard/persistence, two-dimensional
maximize/restore, canvas markup/CSS/JS for fit/zoom/pan/resize-
recalculation, no scope creep into EYE2 features) and a new regression
test in `tests/test_p40vw7a_qa2_thumbnails_annotations_layout.py`'s own
`AppearanceControlledSplitterTests` for the `.app-shell` selector-list
bug. Full suite: see this stage's own commit message for the exact
count.

**Real-browser verification:** still not available in this
environment — no screenshot was actually attached to either of this
round's product-owner messages, only text descriptions; every fix above
is grounded in template/CSS/JS source inspection (including, for the
`.app-shell` bug, a direct `grep` proving the missing selector, not a
guess at what the described screenshot showed) and rendered-HTML
structural tests, not a claimed rendered check. Product-owner
verification checklist for this round specifically: (1) no white/cream
strip anywhere in the shell in Black, Midnight Blue, Deep Forest, or
Light — the Lists/Display divider, Display/Toolbox divider, and the gap
below the header should all read as the same theme-correct color as the
edge already confirmed correct; (2) dragging `#toolbox-divider`'s own
left edge resizes the right column smoothly, with `ArrowLeft`/
`ArrowRight` doing the same via keyboard, and a plain click still
toggling collapse/show; (3) "Maximize Eye" visibly expands Eye both
taller AND wider, "Restore Eye" returns exactly to the prior split and
width; (4) a dropped/pasted image genuinely fills the available Eye
area at Fit, zoom in/out/Actual-size/Reset all behave correctly, the
mouse wheel zooms only when the image area itself is focused, and
panning works via normal scrolling once zoomed past the viewport size;
(5) resizing or maximizing Eye while a Fit-mode image is loaded
re-fits it automatically, but a manually-zoomed image does not snap back
on resize.

## 2026-08-03 — CLAUDE-P40-EYE1: Full-Height Right Column and Eye Structural Scaffold

**Started from a verified clean state:** `HEAD == origin/main` (`7e28371`)
confirmed before any edit, per this stage's own opening instruction.

**What was built** (mirrors CLAUDE-P40-VW7A-QA2's Lists/Thumbnails split
on the opposite side of the shell):

- **Right-column restructuring** (`templates/base.html`): Toolbox moved
  out of `.workspace-main-column` (where it briefly shared a row with
  Display, sibling of `.app-main` inside the now-retired
  `.workspace-content-row`) into a new, full-height `.workspace-right-
  column` - a THIRD sibling of Lists and `.workspace-main-column` inside
  `.app-shell-body`, spanning the same vertical extent as Display+Chat
  combined (Section 1's own explicit "must not stop at the Display/Chat
  divider"). `.workspace-content-row`, left with only `.app-main` as a
  child once Toolbox moved out, was removed rather than kept as dead
  CSS. The new column contains Toolbox (upper) and a new Eye pane
  (lower).
- **Toolbox/Eye divider**: a new draggable `#toolbox-eye-divider`,
  reusing the exact percentage-based pointer-drag/keyboard-step/
  double-click-restore pattern the Lists/Thumbnails divider already
  established. Persistence: `localStorage`, per-Project
  (`beehive:panel:toolbox-eye:{{ project_id }}`) - matching Toolbox's
  OWN existing show/hide preference scoping (per-Project), the
  "lightest existing preference mechanism" already established for
  this exact panel family, not a new scoping convention. Two explicit
  "Maximize Toolbox"/"Maximize Eye" buttons (each toggling to "Restore"
  and remembering the pre-maximize proportion) give both directions a
  real, discoverable, keyboard-reachable control, on top of the
  divider's own Home/End keyboard jump-to-extremes and manual drag.
- **Right-column hide/show**: the EXISTING `toolbox-divider`/
  `html.toolbox-hidden` mechanism (CLAUDE-P40-E3A, Section 7) now
  targets `.workspace-right-column` as a whole (Toolbox AND Eye
  together, plus the divider between them - a descendant, no separate
  rule needed), not `.workspace-pane-toolbox` alone - `aria-controls`
  on `shell.toolbox-divider` updated to match. `display: none` on the
  whole column is what releases all its width with no leftover empty
  panel/scrollbar channel/gutter, the same mechanism Lists' own hide/
  show already relies on (`.app-main`'s `flex: 1` expands automatically).
- **Eye pane scaffold** (Section 4's own explicit "structural surface,
  not a completed tool" boundary): a real `eye.heading` ("Eye"), a
  neutral empty state, and a genuinely functional (not decorative)
  paste/drop target (`static/js/eye_pane.js`, new) - real `dragover`/
  `drop`/`paste` event handling, an image read via `FileReader` and
  previewed in-tab-memory only (a plain `<img>` holding a `data:` URL;
  the file confirms via its own tests that no `fetch()`/`XMLHttpRequest`
  call exists anywhere), a Remove control returning to the empty state,
  and an inline (not silent) error for non-image input. Explicitly NOT
  built this stage, per the prompt's own deferral list: image editing,
  screenshot annotation, chat/Development-Terminal attachment, AI image
  interpretation, evidence persistence, document ingestion, DT1/
  Terminal behavior - all reserved for CLAUDE-P40-EYE2.
- **Appearance coverage**: the Toolbox surface's own painted root moved
  from `.workspace-pane-toolbox` to `.workspace-right-column` (all
  three combined `.appearance-dark`/`.appearance-tinted`/`.appearance-
  deep-forest` rules updated) - both Toolbox AND Eye now inherit the
  theme via ordinary CSS custom-property cascade from one shared
  ancestor, the same "outer column owns theme + background, inner panes
  stay transparent" split `.launcher-panel`/`.lists-pane` already
  established. `scrollbar-color` added to both scrollable panes. No
  opacity used anywhere in the new rules (verified by this stage's own
  tests) - existing dark-mode/Light-mode text-color rules inside
  Toolbox's own content were never touched, only the wrapper.
- **Narrow-viewport drawer**: `@media (max-width: 640px)` now applies
  `position: fixed`/width/z-index/padding/border to `.workspace-right-
  column` as a whole (the WHOLE column becomes the overlay drawer,
  Toolbox and Eye stacked exactly as at desktop widths via the base
  rule's own `display:flex`/`flex-direction:column`), not `.workspace-
  pane-toolbox` alone.

**Note on theme names:** this stage's prompt referred to "Black, Deep
Blue, Deep Purple, and Soft Light" - this repo's actual approved theme
set (CLAUDE-P40-VW8-QA) is Black, Midnight Blue, Deep Forest, and
Light. Flagged directly (consistent with the same note on the VW7A-QA2
browser-correction entry below) rather than silently substituted; all
reasoning above uses the real names.

**Tests:** new `tests/test_p40eye1_toolbox_eye_column.py` (32 tests -
structure, CSS, divider drag/keyboard/persistence, collapse/restore,
hide/show width release, Eye scaffold markup and JS, existing-behavior
preservation including the VW7A-QA2 Chat composer margin fix). Fixed
9 pre-existing test files whose own hardcoded selector lists/DOM-
ordering assumptions were made stale by the Toolbox surface's root
moving to `.workspace-right-column` and by Chat now rendering before
Toolbox in DOM order - the same "update the test's own selector list,
don't revert the change" precedent this repo's history already
establishes, not a silent regression. Two of those (`test_p40e3a_
layout_reconciliation.py`'s own toolbox-content slice tests) had
silently become no-op checks (Python's `body[start:end]` on a reversed
index range returns an empty string, so every `assertNotIn` on it was
vacuously true) - caught and fixed, not left passing for the wrong
reason. Full suite green (see the exact count in this stage's own
commit message).

**Real-browser verification:** still not available in this environment
- every claim above is grounded in template/CSS/JS source inspection
and rendered-HTML structural tests. Product-owner verification
checklist: (1) the right column visibly spans header-to-workspace-
bottom, matching Lists' own height, in every state; (2) dragging the
Toolbox/Eye divider resizes both panes smoothly, with keyboard Home/End
jumping to the practical extremes and arrow keys stepping; (3)
"Maximize Toolbox"/"Maximize Eye" each expand their own pane and
correctly restore the prior proportion on a second click; (4) hiding
Toolbox (the existing top-bar control) now visibly removes Eye too,
with Display/Chat reclaiming the full released width and no leftover
gutter; (5) restoring brings back the previous width AND the previous
Toolbox/Eye split; (6) the Eye pane accepts a real drag-and-drop image
and a real clipboard paste, previews it, and Remove returns to the
empty state; (7) all four Appearance themes (Black/Midnight Blue/Deep
Forest/Light) render both panes and the divider correctly, no white/
beige gutters, no opacity-faded text; (8) narrow viewport still shows
the whole right column as one overlay drawer; (9) the Chat composer's
own bottom margin (CLAUDE-P40-VW7A-QA2) is still visibly present; (10)
existing Toolbox content (Findings, Document tools, empty state) is
unchanged.

## 2026-08-03 — CLAUDE-P40-VW7A-QA2 (browser corrections): Left-Column Full-Height Background, Appearance-Controlled Splitters, Chat Composer Margin

Two real-browser checks of the VW7A-QA2 entry below reported three
further defects, all fixed within the same stage (no new scope).

**1. Light rectangle beneath Lists in dark Appearance modes.** Root
cause: the VW7A-QA2 entry's own `.chat-region` fix (`margin-left: 240px`
so Chat wouldn't render underneath Lists) offset Chat's box without
changing what painted the space *behind* it — leaving the strip
directly beneath Lists, for the height of Chat's own row, painted by
nothing at all (Chat no longer reached it; Lists never had reached it,
since `.chat-region` was always a full-width sibling of
`.app-shell-body`, a separate row below Lists' own row). **Fix, this
time structural rather than an offset:** `templates/base.html` now
nests `.chat-region` inside a new `.workspace-main-column` (containing
`.workspace-content-row` — Display+Toolbox — stacked above Chat),
itself a sibling of Lists inside `.app-shell-body`. Lists' own
`height: 100%` now genuinely spans the same vertical extent Chat's row
occupies, so its already-themed background (`Appearance All`'s
`--surface-primary`, unchanged) covers it with no gap. The margin-left
hack and its `html.launcher-hidden`/narrow-viewport overrides are
removed — no longer needed, since Chat's box now starts at the correct
horizontal position automatically as a real descendant. Also added:
`scrollbar-color` (Firefox-supported token pair) on `.lists-pane`/
`.thumbnails-list` — stated honestly as the ceiling of what plain CSS
can do here, since WebKit/Chromium has no equivalent property.

**2. "White splitter tracks... in the dark theme."** Root cause: panel
dividers/splitters (`.panel-divider` — Lists/Display and Display/
Toolbox — and `.lists-thumbnails-divider`) are shell CHROME, siblings
of the 5 Appearance-themed surfaces rather than descendants of any one
of them, so they never inherited a surface's own `--surface-primary`
redefinition and stayed on the unthemed `:root` light default
regardless of the active theme. **Fix:** `.app-shell` now gets a 6th,
piggybacked appearance class (both in `base.html`'s early pre-paint
script and its main Appearance-menu wiring script) sourced from the
Menu surface's own resolved mode — not a new, separately-configurable
preference, reusing existing state — giving every un-surfaced element
a theme-correct fallback via ordinary CSS custom-property inheritance.
A themed surface nested inside `.app-shell` still wins locally (closer
ancestor in the cascade), so per-surface Appearance independence
(mixed-mode) is unaffected. Every divider element then got a real,
non-transparent `background: var(--surface-primary)` — `.panel-divider`
now resolves through the new shell-level fallback; `.lists-thumbnails-
divider` and `.conversation-dock-resize-handle` are genuine descendants
of Lists/Chat respectively, so they already pick up THEIR OWN surface's
theme directly, no shell fallback needed. Hover/focus-visible/`.dragging`
accent states (`var(--machine-blue)`) are unchanged — only the resting
background moved off `transparent`. No opacity-based parent tricks used
anywhere in this fix.

**3. Chat composer touching the viewport edge.** `.conversation-input-
form` had `padding-left`/`padding-right` (via the shared
`--conversation-inset` token) but no bottom padding at all, since it is
the last child of `.conversation-dock-panel`/`.chat-region`
(`position: sticky; bottom: 0`). Added `padding-bottom: var(
--conversation-inset)` — the SAME token as left/right, for a balanced,
consistent inset — real flex-item padding, not page overflow or an
external strip, so it survives every `--chat-height` value and the
narrow-viewport layout unchanged.

**Tests:** `tests/test_p40vw7a_qa2_thumbnails_annotations_layout.py`
grew from 41 to 54 tests (new `ChatRegionNestingTests`,
`LeftColumnFullHeightBackgroundTests`, `AppearanceControlledSplitterTests`,
`ChatComposerBottomMarginTests`; the old margin-left-based
`ChatRegionLeftEdgeTests` checks were replaced, not left stale, once
the margin-left approach itself was superseded). Full suite green.

**Real-browser verification:** still not available in this
environment — every claim above is grounded in template/CSS/JS source
and rendered-HTML structural inspection. Product-owner checklist for
this correction specifically: (1) no light/unpainted rectangle beneath
Lists in Black, Midnight Blue, Deep Forest, or Light — full column
height, edge to edge, down to the workspace bottom; (2) every divider
(Lists/Display, Display/Toolbox, Lists/Thumbnails, Chat resize handle)
merges with its surrounding theme at rest, with a clearly visible
accent on hover/focus/drag, in all four themes; (3) the Chat composer
has a clearly visible, balanced bottom margin at every `--chat-height`
(compact/expanded/dragged) and at a narrow viewport.

**Note on theme names:** the browser-correction messages referred to
"Black, Deep Blue, Deep Purple, and Soft Light" — this repo's actual
approved theme set (CLAUDE-P40-VW8-QA) is Black, Midnight Blue, Deep
Forest, and Light. Flagged directly rather than silently substituted;
all reasoning above uses the real names.

## 2026-08-03 — CLAUDE-P40-VW7A-QA2: Complete the PDF Viewer Controls, Thumbnails and Collapsible Panel Geometry

**Reported defect (real-browser check of CLAUDE-P40-VW7A-QA, below):**
the old white browser-native toolbar was gone (correct), but the
replacement top-menu document controls did not visibly appear; page/
zoom/fit/rotate/search/print/download controls were absent from the
rendered interface; thumbnails and annotation capability were required
but missing; and hiding Toolbox left a large empty right-side column
instead of releasing its width.

**Diagnosis performed (static analysis only — no real browser tool
exists in this environment, stated honestly rather than fabricated):**
curl-based HTML/header inspection, CSS-cascade specificity scripts, and
a Node.js DOM-stub harness executing the actual `pdf_viewer.js` setup
code found no 100%-provable single root cause for the controls not
connecting. The single most plausible, well-reasoned, low-risk
candidate was applied: **vendored PDF.js was switched from the modern
`build/` distribution to `legacy/build/`** (broader browser/JS-engine
compatibility — PDF.js's own README: "for usage with older browsers/
environments... please see the `legacy/` folder"), re-extracted from
the same already-downloaded tarball, byte-verified via sha256sum. A
silent module-parse failure on an unsupported engine would exactly
match "renders but nothing connects," with no visible symptom to
confirm or rule it out — so `pdf_viewer.js`'s `mount()` also gained a
permanent diagnostic improvement regardless of whether this was the
real cause: any future load failure now shows a real, visible
`.document-viewer-load-error` message in the canvas container instead
of only a silent `console.error`.

The Toolbox-hidden-width report (`html.toolbox-hidden
.workspace-pane-toolbox { display: none; }` plus `base.html`'s own
`setUpDivider`) was re-investigated with the same rigor: CSS
specificity math, absence of conflicting/duplicate/stale selectors,
correct JS class-toggling both pre-paint and at runtime, absence of any
inline-style-setting resize code. No definitive code-level bug was
found — documented honestly rather than making unfounded speculative
changes. Re-confirmed unaffected by this stage's own new CSS (which is
entirely scoped to `.launcher-panel`'s own descendants).

**What was built:**
- **Lists/Thumbnails split** (`templates/base.html`'s own `<nav
  id="launcher-panel">`): the existing Lists content is now wrapped in
  a `.lists-pane` sibling of a new, `[hidden]`-by-default
  `#thumbnails-pane`, with a draggable `#lists-thumbnails-divider`
  between them — reusing `static/js/case_workspace.js`'s own
  `setUpChatResize` pointer-drag idiom (percentage-based, not pixel,
  since the available height varies by viewport) rather than inventing
  a new drag mechanism. Session-scoped persistence only
  (`sessionStorage`, not `localStorage` — a deliberately weaker
  guarantee than the Lists/Toolbox show/hide preferences). Double-click
  restores the default 60/40 split; a Maximize toggle on the
  Thumbnails header collapses Lists toward its own header and restores
  the prior proportion on a second click. `.launcher-panel.
  has-thumbnails .lists-pane` is what lets Lists silently regain the
  full column height the moment Thumbnails is hidden — no JS needs to
  touch `.lists-pane` directly for that to happen.
- **Real PDF thumbnails** (`static/js/pdf_viewer.js`): one real
  `<button role="listitem">` per page inside `#thumbnails-list`,
  rendered lazily via `IntersectionObserver` (not every page up front),
  clicking one calls the existing `goToPage(n)`. The current-page
  thumbnail is kept in sync (`aria-current="true"`, scrolled into view)
  from every `goToPage()` call regardless of trigger — toolbar,
  search-result jump, or a thumbnail click itself — via one shared
  `updateNavState() -> updateThumbnailCurrent()` path. Scope, stated
  honestly: this viewer shows one page at a time on a single
  `<canvas>` (unchanged from VW7A-QA), not a continuous multi-page
  scroll surface, so "follows page changes from scrolling" has nothing
  additional to listen for beyond what already drives the sync above.
- **`.chat-region` left-edge fix**: CLAUDE-P40-E3A, Section 9's own
  "Chat spans the entire application width" rule is narrowed
  (disclosed, not silently reversed) via `margin-left: 240px` — Chat
  now begins at the centre (Display) column's left edge, never
  underneath the full-height Lists/Thumbnails column, while still
  spanning Display+Toolbox. Collapses to `margin-left: 0` the instant
  `html.launcher-hidden` or a narrow (≤640px) viewport removes Lists
  from the row layout — reusing the SAME class the Lists divider
  already toggles, no new state to keep in sync.
- **Real client-side PDF annotation tools** (`static/js/pdf_viewer.js`
  + new `#doc-annotate-*` controls in `templates/base.html`'s
  `#workspace-document-controls`): text, highlight (rectangle drag),
  freehand ink, select+delete, undo/redo, one-active-tool-at-a-time
  (`aria-pressed`). Coordinates are stored in PDF page space
  (`PageViewport.convertToPdfPoint`/`convertToViewportPoint` —
  confirmed present in the vendored build via direct grep of
  `pdf.min.mjs`), not raw canvas pixels, so annotations stay correctly
  placed across zoom/rotation changes; drawn on a transparent overlay
  `<canvas>` stacked over the page canvas
  (`.document-viewer-page-wrap`), never touching the original file.
  **Disclosed scope boundary, per this stage's own explicit permission
  to stop rather than ship a fake control:** no PDF-writing library is
  vendored in this repo (only PDF.js's rendering half), and adding one
  is a real new-dependency decision (`tools/dependency_fit.py`) this
  stage does not make silently — so there is deliberately **no Save/
  Export control**. `#doc-annotation-status` ("Unsaved annotations
  (draft only — not saved to the Document)") plus a `beforeunload`
  warning are how "clearly indicate unsaved changes... warn before
  discarding" is satisfied instead of a nonfunctional save button.
  Annotations are real, interactive, and undoable for the current
  browser session; nothing in the code claims they persist beyond it.
- **Splitter appearance consistency** (Section 6): the new
  Lists/Thumbnails divider follows the same visual grammar as the
  existing `.panel-divider` (Lists/Toolbox — already one shared class,
  confirmed no per-modifier styling drift) and `.conversation-dock-
  resize-handle` (Chat) — quiet resting line, `--machine-blue` accent
  on hover/focus, transparent hit-target (no white/beige gutter in any
  theme, all colors are `var(--token)`). "Active accent only while
  dragging" is now a real `.dragging` class (not just `:hover`, which
  would drop the accent the moment the pointer strays off the thin
  line mid-drag, since the drag itself continues via document-level
  listeners) — added to both the Chat handle and the new divider.

**Not built this stage (explicit scope boundary from the prompt,
respected):** Internal Development Terminal, Terminal Eye, cross-
Project access, P41.

**UI references:** `UI_REFERENCE_MAP.md` updated — new `shell.
lists-thumbnails-divider` row, a new "Lists — PDF Thumbnails pane"
section (`lists.thumbnails-pane`, `.maximize`, `.list`), and a new
"Annotation tools" subsection under Document controls (`menu.
document-controls.annotate-text/-highlight/-ink/-select/-delete/-undo/
-redo`, `.annotation-status`). Individual `.thumbnail-row` buttons are
JS-generated per page (a repeated pattern, not a fixed control set) —
deliberately left unregistered, same convention as `lists.project.
documents.leaf` etc. `tests/test_p40vw7a_qa_document_controls.py`'s
own `test_no_decorative_controls_for_features_that_do_not_exist` had
"annotation" on its forbidden-word list from the prior stage (when
annotations genuinely didn't exist) — updated, not reverted, now that
this stage builds real ones.

**Tests:** new `tests/test_p40vw7a_qa2_thumbnails_annotations_layout.py`
(41 tests — structure, CSS, JS-source, and rendered-HTML checks for the
split/divider/thumbnails/annotations/Chat-offset/dragging-accent, plus
the legacy-PDF.js-build and visible-load-error changes). Full suite run
after these changes.

**Real-browser verification:** still NOT available in this environment
— every claim above is grounded in template/CSS/JS source inspection
and rendered-HTML structural tests, not an actual browser session.
Product-owner verification checklist (what a real browser check should
confirm): (1) header document controls now visibly render and connect
for an open PDF; (2) page/zoom/fit/rotate/search/print/download all
perform their real action; (3) Thumbnails pane appears only for a PDF,
thumbnails render progressively while scrolling the list, clicking one
navigates and highlights correctly; (4) the Lists/Thumbnails divider
drags, double-click restores default, Maximize toggles and restores;
(5) annotation tools draw/select/delete/undo/redo correctly and
`#doc-annotation-status` reads "Unsaved..." only when annotations
exist, clears when the last one is undone/deleted; (6) the original PDF
file is unchanged after annotating (re-open the Document fresh); (7)
hiding Toolbox now visibly releases its column width to Display/Chat;
(8) Chat's own left edge lines up with Display's, never extending under
Lists, at both a normal and a Lists-hidden/narrow-viewport state; (9)
all four Appearance themes on every new element (no white/beige
gutters); (10) UI Reference Mode badges show the new refs correctly.

## 2026-08-03 — CLAUDE-P40-VW7A-QA: Move Document Controls into the Top Application Menu

**Grounding finding, before any implementation:** the reported "white
strip toolbar... occupies a separate horizontal band inside the
Display" did not correspond to anything in this codebase. Direct
inspection of `templates/case_workspace.html` (pre-change) found the
entire document viewer was a bare `<iframe src="{{ raw file URL }}">`
(PDF/DOCX/TXT) or a plain `<img>` (drawings) - zero custom JS, zero
`data-ui-ref` of its own, and an explicit pane-note already stating
page/clause navigation "isn't available yet for this format." The
toolbar being described was the BROWSER'S OWN native PDF viewer chrome
rendering inside that iframe - not something this app built, styled,
or could script (a plain cross-origin iframe embed exposes no API for
a host page to read or drive a native PDF viewer's page/zoom/rotation/
search state). Reported this finding to the product owner directly
(via `AskUserQuestion`) before writing any code, rather than building
a fictional "relocation" of controls that never existed on this side.
Given three options (build a real PDF.js-based viewer / report only,
no build / minimal repositioning of what's genuinely Archiosk's own),
the product owner chose to build a real viewer.

**What was built:**
- **Vendored PDF.js** (`static/js/vendor/pdfjs/` - `pdf.min.mjs`,
  `pdf.worker.min.mjs`, Apache-2.0 `LICENSE`, a `README.md` documenting
  exact version/source/what was deliberately NOT taken). No client
  build step (`tools/dependency_fit.py` run against this exact vendoring
  approach: PASS on `no-client-build`, WARN-not-FAIL on
  `python-native-preferred` with the justification that client-side PDF
  rendering has no Python equivalent) - loaded via a plain dynamic
  `import()` from an ordinary script, same loading pattern as every
  other `static/js/*.js` file in this app. Deliberately did NOT vendor
  PDF.js's own bundled `pdf_viewer.mjs`/`pdf_viewer.css` UI - the whole
  point of this stage is Archiosk's own top-menu controls driving the
  low-level rendering API (`getDocument`/`getViewport`/`render` to a
  `<canvas>`) directly, not a second toolbar.
- **`static/js/pdf_viewer.js`** (new) - the adapter. Real page
  navigation, zoom (25%-400%, clamped), fit-width/fit-page (computed
  against the live container size), cumulative 90° rotation, and a
  genuine full-document text search (PDF.js's own `getTextContent()`,
  cached per page, cycles through matches jumping pages as needed) -
  not placeholders. Print opens the original PDF in a new tab (the
  browser's own native print/save chrome there already works reliably;
  re-implementing print pagination for a canvas-rendered page was
  judged unnecessary complexity). Auto-mounts by checking for
  `#document-viewer-pdf-canvas`'s presence/`data-pdf-url` - no inline
  per-page script needed, and no dependency on script-load ordering;
  works naturally with this app's full-page-reload architecture
  ("switching documents" is always a fresh page load, which always
  re-runs this check).
- **`templates/base.html`** - a new `#workspace-document-controls`
  region between the breadcrumb and Display Layout/Appearance/Account,
  `[hidden]` by default. Essential controls (page nav, zoom) always
  inline; secondary ones (fit/rotate/search/download/print) physically
  re-parented (real DOM node move, never a cloned duplicate) into a
  `<details>` overflow panel below a 900px viewport (matching this
  file's own existing breakpoint convention) via a `matchMedia`
  listener. Every button has a real `aria-label`+`title`, disabled
  state where applicable (page edges, no search matches).
- **`templates/case_workspace.html`** - a PDF Source (detected via
  `file_path` ending in `.pdf`, case-insensitive) now renders an empty
  canvas-container div instead of the old iframe; a drawing/DOCX/TXT
  Source keeps its existing `<img>`/`<iframe>` completely unchanged
  (out of scope - no renderer built for those formats). The stale
  "page navigation isn't available for this format" pane-note is now
  suppressed specifically for PDFs (still accurate, unchanged, for
  every other format).
- **CSS** - `.document-viewer-canvas-container` reuses the exact same
  box (`height: 70vh`, border, background) the old iframe had; removing
  the native browser chrome (a `<canvas>` has none) reclaims the extra
  vertical space automatically within that same box, not by growing
  it. The new top-menu controls use no per-button border/background
  except on hover/focus (the same restrained, "part of the application,
  not a bright toolbar pasted over it" language `.conv-selection-btn`
  already established for a comparable dense inline-action row) - every
  color is a `var(--token)` reference, so all four appearance themes
  (Black/Midnight Blue/Deep Forest/Light) work for free.

**Scope, stated honestly:** PDF only. Sidebar/thumbnail/outline/
annotation controls were NOT added - none existed before this stage
(nothing to preserve), and building them would be separate, much
larger subsystems (thumbnail generation, annotation persistence with
new backend storage) beyond "move/rebuild the controls that exist."

**UI references:** every `menu.document-controls*` identifier and
`display.document.pdf-canvas` is genuinely NEW - there was no prior
Archiosk-owned toolbar-container reference to retire or reparent
(confirmed directly from the pre-change template source, not assumed).
Also fixed, while auditing this same Menu region: `UI_REFERENCE_MAP.md`'s
own `menu.appearance*` rows had gone stale since the earlier Approved
Theme Set stage (still describing a 3-mode Light/Dark/Tinted matrix) -
corrected to the real 4-mode Light/Black/Midnight Blue/Deep Forest
matrix, and `tests/test_p40vw7a_ui_reference_map.py`'s own
`_APPEARANCE_MODES` constant (used to reconstruct the Jinja-loop-
constructed `menu.appearance.*` refs a plain regex can't recover) was
missing `deep-forest` entirely - a real pre-existing gap this stage's
own registry-consistency test caught and fixed.

**Real-browser verification:** NOT available in this environment -
every claim above is grounded in template/CSS/JS source inspection,
`tools/dependency_fit.py`'s own real output, and a rendered-HTML
structural test suite (see `tests/test_p40vw7a_qa_document_controls.py`),
not an actual browser session; stated honestly rather than fabricated.

## 2026-08-03 — CLAUDE-P40-VW7A-QA: Clarify Project Hierarchy and Selection State

**Reported defect:** the Lists panel's `PROJECTS` root (an expanded
heading), the current Project ("Nipigon Ramp"), and whichever child
was actually the selected destination (e.g. "Chats") all shared the
exact same literal CSS state — three different meanings collapsed into
one highlight, so a reviewer couldn't tell which of the three a filled
row actually meant.

**Root cause, confirmed directly from the markup/CSS (not assumed):**
`lists.project.self` (the Project's own name row) carried a
HARDCODED `active` class unconditionally — the exact same class every
genuinely-selected child leaf (`lists.project.chats`, `.overview`,
`.documents.leaf`, `.investigations.leaf`, `.rfis.leaf`) already
computed conditionally, and the exact same class/selector
(`.launcher-link.active { background: var(--surface-selected); }`)
painted BOTH with the identical `--surface-selected` fill.
`.launcher-heading.active` (PROJECTS) used a different color
(`--surface-hover`) but the same KIND of fill-based "this is
highlighted" treatment, still reading as selection-like.

**Fix — three now-genuinely-distinct treatments, no new backend/
domain concept, purely presentational:**
1. `.launcher-heading` (PROJECTS, and any future equivalent root) keeps
   its already-distinct structural-title typography (uppercase,
   letter-spaced, `--text-metadata`) — `.launcher-heading.active` no
   longer fills a background at all (only real `:hover`/
   `:focus-visible` do); expansion state is already fully conveyed by
   `aria-expanded` and the toggle-arrow rotation, needing no fill echo.
2. `lists.project.self` gets a NEW `.current-project` class instead of
   `.active` — a restrained left-edge marker (`border-left: 3px solid
   var(--border-strong)`, the same idiom `.finding-card` already uses
   elsewhere in this file for "flagged/notable") plus bold text, never
   `--surface-selected`. `aria-current="true"` identifies it as the
   current Project for assistive tech, distinct from `aria-current=
   "page"` on the actual selected child.
3. `.launcher-link.active` (selector/value unchanged) is now reserved
   exclusively for the ONE child leaf whose own href is what is
   actually displayed — `lists.project.self` no longer qualifies.
   Every already-existing conditional (Overview/Documents leaf/
   Investigations leaf/RFIs leaf/Chats/+New Investigation) now also
   sets `aria-current="page"` in lockstep with its own `active`
   condition — a real accessibility gap (none of these exposed ANY
   current/selected ARIA state before this stage), not just a visual
   fix.

**Tree-guide + sibling separation:** every `.tree-children` (uniform,
not Project-specific) gets a restrained 1px left border in the
existing quiet `--border` token — the classic file-tree vertical-
connector convention, satisfying "do not rely on background
highlighting to communicate nesting." A new `templates/base.html`
Jinja `namespace` (`sibling_separation`) tracks which ONE sibling
Project row renders immediately after the current Project's own child
group closes and adds `.sibling-project-after-current` (whitespace-
only `margin-top`, no border) there — verified empirically that
`nav_recent_projects` (`app.py`) sorts most-recently-**ingested**
first, so render order is the reverse of ingestion order (confirmed
directly against a real render before writing the corresponding tests,
not assumed).

**`isDescendantActive`/`data-tree-no-clear` (PROJECTS' own
collapse-clears-Display guard):** functionally unaffected — the
function still reads the unchanged `.tree-leaf.active` selector, which
still exists on whichever child leaf is genuinely selected (it just no
longer ALSO exists on `lists.project.self`, which was never scanned by
this specific check anyway since PROJECTS carries `data-tree-no-clear`
and short-circuits before reaching it). The comment explaining WHY
`data-tree-no-clear` is needed was corrected — it used to (accurately,
at the time) attribute this to the Project's own row always carrying
`.active`; that's no longer true, so the comment now correctly
attributes it to whichever child leaf is selected instead.

**UI references:** zero renumbered/retired — every existing
`lists.projects*`/`lists.project.*` identifier is unchanged;
`.current-project`/`.sibling-project-after-current` are pure CSS/layout
hooks, not governed references (documented in `UI_REFERENCE_MAP.md`'s
own new note rather than added as numbered rows).

**Real-browser verification:** NOT available in this environment — the
rendering claims above were verified via direct HTML inspection of the
Flask test client's own rendered output (grounded, not fabricated) and
the accompanying focused test suite, not an actual browser session;
stated honestly per this project's established convention.

**Commits:** implementation + tests in this stage's own bounded commit
(see `git log`).

## 2026-08-03 — CLAUDE-P40-VW8-QA: UI-Tagging completion, Selection-Toolbar Corrections, Panel-Border Hierarchy, Approved Theme Set, Chat Composer Corrections, Tag Reversibility

A single long stage covering a rapid sequence of product-owner
corrections, each addressed as its own bounded change with its own
tests. Summarized by area, not chronologically (several areas were
themselves revised more than once within this stage — the final state
is what's described; superseded intermediate states are noted only
where relevant to future readers).

**UI-tagging completion (root/subfolder reference tagging):** extended
`data-ui-ref` coverage to previously-untagged empty-state rows
(Documents/RFIs/Tasks/Tags), Security Department's 11 accordions + 5
subdisclosures (via a new optional `ui_ref=` parameter on
`templates/_macros.html`'s `accordion`/`subdisclosure` macros), and the
Projects Directory/Removed Projects pages. `tests/test_p40vw7a_ui_
reference_map.py`'s own `_all_template_refs()` scanner extended with a
second regex for macro-call-argument-style refs (`ui_ref='x.y'`, which
never appear as a literal `data-ui-ref="..."` in the calling template's
own source — only inside the macro body). Deliberately did NOT tag
Overview's ~30 internal accordions — CLAUDE-P40-E3A's own prior "one
consolidated `display.overview` leaf, no second navigation directory in
Display" decision governs there, not an oversight.

**Selection toolbar — three corrections, same root architecture:**
1. *Permanently visible / horizontal layout* (product-owner report):
   root-caused to `static/css/main.css`'s `.conv-selection-toolbar`
   rule having no `[hidden]` override — the class's own `display: flex`
   beat the `hidden` attribute at equal cascade specificity, the exact
   same bug CLASS as the R3 tokens.css comment-boundary regression
   (logic correct, a cascade detail made it invisible in effect). Fixed
   with `.conv-selection-toolbar[hidden] { display: none; }` +
   `flex-direction: column` (one action per row). Audited the full JS
   end to end first: all 6 actions (Tag/Task/Highlight/Important/
   Question/Copy) were already genuinely wired to real dialogs/routes/
   clipboard — nothing was decorative.
2. *Overlap with the browser/OS's own selection popup* (most
   identifiably Edge's "mini menu on text selection" —
   `edge://settings/appearance`, or the `QuickSearchShowMiniMenu`
   enterprise policy): confirmed no `contextmenu` suppression exists
   anywhere near this toolbar (already compliant). `positionToolbar`
   now prefers BELOW the selection first (was: above first, the direct
   spatial collision), and a new `repositionOrHideOnViewportChange`
   (bound to `window`'s `scroll`/capture-phase and `resize`) keeps the
   toolbar correctly placed — or hides it — if the containing panel
   scrolls or the viewport resizes while a selection is held, which
   nothing previously handled.
3. *No inverse actions* ("anything the user can tag/classify/highlight
   must have a clear way to remove that later"): NO new backend data
   model — Highlight/Important/Question are already just built-in Tags
   (`BUILT_IN_TAGS`), and `remove_tag_occurrence` already removes only
   the one occurrence record, never the Tag definition or any other
   occurrence of it. The one genuinely new backend surface is
   `routes/workspace.py`'s `tag_occurrences_for_selection_route` (GET,
   read-only) — needed because `app.py`'s own `hotlinks` filter only
   ever draws ONE inline `<mark>` per position when Tag occurrences
   overlap ("first-starting wins"), so a live selection can span an
   occurrence with no visible `<mark>` at all; this endpoint is the
   only reliable way the client can know "multiple Tags are attached
   here" in that case. Client: a new "Remove Tag (N)" button (hidden
   unless 1+ custom Tag occurrences overlap the selection) opens a
   dialog listing each by name (text, never color alone) with its own
   Remove; Highlight/Important/Question's own buttons swap between
   their add/remove identities (`data-conv-action`/`data-ui-ref`/label
   all change together — new refs `.remove-highlight`/`.unmark-
   important`/`.unmark-question`/`.remove-tag`/`.undo`, never inheriting
   the add/apply ones). A short-lived (8s) Undo re-POSTs the same
   add-Tag route with the removed occurrence's own tag id + anchor
   fields. `app.py`'s `hotlinks` filter gained `data-tag-id`/`data-
   tag-name` on the rendered `<mark>` for robust client-side reads.

**Panel-border hierarchy correction:** Chat's own existing treatment
(no `border-top` on `.chat-region` itself — one line via
`.conversation-dock-resize-handle::before`, using the fixed, mode-
invariant `--divider-strong` token) named as the approved reference.
Two concrete fixes: `.launcher-panel`'s desktop rule no longer draws
its own `border-right` (the adjacent `.panel-divider::before` already
drew a second, parallel line ~4-5px away — a real doubled boundary);
`.workspace-topbar`'s full-width bottom border switched from
`var(--border)` to `var(--divider-strong)` (same reasoning as Chat's
own divider — a token proven to read calmly at every theme's own
background, not one that gets locally redefined per mode). Audited and
left unchanged: the Display-to-Toolbox boundary (already a single quiet
line, no redundant second border), `.panel-divider` itself (already
quiet-at-rest/accent-on-hover-or-focus).

**Approved Theme Set — Black / Midnight Blue / Deep Forest / Light**
(replacing Light/Dark/Tinted): went through TWO real corrections within
this same stage, both preserved honestly in `tokens.css`'s own
comments rather than silently overwritten.
- *First pass:* renamed Dark→"Graphite" (#0E1116, neutral near-black)
  and Tinted→"Midnight Blue" (turning it from a light navy-grey
  daylight variant into a dark theme, #0B1B2B), added Deep Forest
  (#10231E, new). Shared warm off-white text (#E8E4DC) across all
  three. Surface/border ramps derived by reprojecting the existing
  `#000000`-based lightness progression onto each new hue.
- *Second, corrective pass* (explicit product-owner follow-up:
  "Restore the original true-black appearance... Do not use
  Graphite... must appear flat and matte"): Black restored to literal
  `#000000` (VW6's own original value) — the `--dark-*` token PREFIX
  and `.appearance-dark` CLASS NAME never changed through either
  revision, only the label and values (a `data-ui-ref` naming
  discipline extended to internal token names too: relabeling doesn't
  require renumbering). Midnight Blue deepened to `#001426`, Deep
  Forest to `#001A12` (both "visibly deep, saturated, and solid").
  Warm off-white text KEPT (the one part of the Graphite revision the
  follow-up explicitly preserved). Derivation method upgraded from raw-
  lightness reprojection to LUMINANCE-matching (`tools/derive_theme_
  palettes.py`, new) — required once saturation varies significantly:
  a fully saturated green reaches a given relative luminance at a much
  lower raw HSL lightness than blue does (WCAG's 0.7152 G-channel
  weight), so naive reprojection had genuinely failed contrast for Deep
  Forest (text-metadata dropped to 2.58:1) until this was fixed.
  Border/border-strong use reduced saturation (0.55/0.60) versus the
  surface steps so ordinary panel boundaries stay quiet even against a
  vividly saturated theme background — coordinated with the panel-
  border-hierarchy correction above. Migration: `dark`/`graphite` →
  `black`, `tinted` → `midnight-blue`, `midnight-blue`/`deep-forest`/
  `light` pass through unchanged, anything else (including no stored
  value at all — new default) → `black`. A new early script block
  (right after `.chat-region`'s own markup, before the ~300 lines of
  later panel-divider/menu/dialog wiring) applies the resolved
  per-surface classes as early as this plain-script architecture
  allows, specifically to remove the "new user sees a Light flash
  before Black initializes" window. UI refs: `light`/`dark`/`tinted`
  ref suffixes retained unchanged through both label revisions;
  `deep-forest` is the one genuinely new suffix.

**Chat composer — two corrections, same underlying area:**
1. *Heavy heading removed:* "PROJECT CONVERSATION" (and the
   explanatory guidance sentence beneath it) removed from the top of
   the Chat panel. The guidance paragraph's own DOM element
   (`#project-conversation-guidance`) is KEPT, emptied of its text —
   it is a real, already-wired anchor target for guidance-scope Tag/
   Task occurrences and navigate-to-source, not decorative; deleting it
   outright would have orphaned already-persisted data. A first attempt
   moved a compact "Chat (N)" label down to the composer row — the
   immediate follow-up rejected that too as a duplicate of the Lists
   panel's own "Chats" row, which now carries the count instead
   (`routes/workspace.py`'s new `project_conversation_count`). The
   composer input keeps a real accessible name via `aria-label=
   "Message"`, never placeholder-text-only.
2. *Inconsistent horizontal alignment:* the old per-role asymmetric
   message margins (`.conversation-message.human` indented left only,
   `.system` indented right only — two different left edges) replaced
   by ONE shared `--conversation-inset` custom property, declared once
   on `.conversation-dock-panel` and applied as left+right padding on
   both `.conversation-thread` and `.conversation-input-form` — every
   message, role label, and the composer now share the same left AND
   right edges. The composer input's own internal padding reverted to
   plain symmetric (the earlier VW8-QA fix that gave it an asymmetric
   1.5rem-left compensation is superseded, not layered on top of, this
   container-level inset). The resize-handle divider stays deliberately
   full-width, unaffected.

**Test regressions from the above, all fixed (not silently weakened —
each fix updates the assertion's own expected value/selector to match
the now-correct behavior, per this repo's own established discipline):**
`test_projects_directory_redesign.py` (a fragile regex assumed the
`<ul class="project-card-list">` tag had no other attributes — broken
by this stage's own earlier UI-tagging `data-ui-ref` addition to that
same element), `test_p40vw3_appearance_matrix.py`/`test_p40vw6_theme_
correction.py`/`test_p40vw8qa_r3_appearance_mode_integrity.py`/
`test_p40vw8qa_theme_foreground_contrast.py` (pinned the old 3-mode/
white-text/light-Tinted values — updated to 4-mode/warm-off-white/
dark-Tinted), `test_conversation_apertures.py` (pinned the removed
"Project Conversation (N)" heading text — updated to the new "Chats N"
Lists-row text), `test_p40e3a_layout_reconciliation.py` (a blanket "no
literal 'Undo' anywhere" check from a much earlier stage, before the
new genuinely-functional Undo control existed — narrowed to exclude
that one real control while still guarding against decorative ones).

**Commits:** see `git log` for the exact bounded sequence (implementation
+ tests were staged and committed in scoped groups matching the areas
above, not one mega-commit).

**Real-browser verification:** NOT available in this environment (no
browser-automation tool connected) — every visual/interaction claim
above is grounded in template/CSS/JS source inspection and the
project's own existing contrast-verification tooling, stated honestly
as a limitation per this repo's established convention, not fabricated.

**Reported defect:** inside an active Investigation, the reviewer
wrote "Those numbers are geodetic elevations from ground floor to the
basement." (a clarifying statement, not a command) and got the same "I
didn't recognize an action in that message" reply as a genuinely
unrelated stray message — the interpreter's final fallback never
distinguished "an open Investigation with nothing recognized" from
"no Investigation at all."

**Fix 1 — discussion contribution:** `services/conversation_
interpreter.py`'s final fallback now checks for an open Case first:
when one is open and nothing else matched, the message is recorded as
a real discussion contribution ("Noted as context for this
Investigation...") instead of the generic "unrecognized" reply. A
project-level message with no Case open still gets the original,
unchanged "unrecognized" reply — the change is scoped to exactly the
reported condition, not a blanket softening of every unmatched
message.

**Fix 2 — general evidence-guided quantitative pattern:** new
`services/quantitative_investigation.py` — a reusable (not "Nipigon
Ramp"-hardcoded) distance/elevation-difference/slope/clearance
feasibility pattern, wired into `conversation_interpreter.py` as a new
`_handle_quantitative_investigation` branch, checked before the
generic project-question/discussion-acknowledgment fallbacks. Every
value extracted is a number the reviewer directly TYPED into this
conversation (`extraction_method="conversation_stated"`, always
carrying its own exact matched quote and `status="user_provided"`) —
never a drawing citation, since no drawing was actually read: local
OCR and PDF-page rendering are NOT available in this environment
(confirmed directly during the R2A stage's own capability audit,
identical conclusion, not re-derived). Re-scans the WHOLE Case
conversation (not just the current message) each turn, so a value
confirmed several messages ago is still "remembered" — no new
persisted working-memory data model was introduced; conversation
history (already durable) is the only state this uses, and `Finding`
stays a plain statement string exactly as it already was (no new
business object).

**Calculation (the exact 5-step formula specified):** vertical drop =
entrance grade − basement grade; basic sloped run = vertical drop /
slope; total required travel = basic sloped run + additional length;
compared against available measured length once stated. The 6 m
driveway width is structurally never insertable into this formula —
`compute_feasibility` has no width parameter at all. No default/
hardcoded regulatory slope value anywhere — the reply explicitly
states the applicable slope must come from an already-adopted governed
source in the Project or the reviewer's own explicit assumption, and
is "never assumed automatically."

**Missing-source guidance:** when no drawing Source is attached, the
reply names specific evidence and explains why (site plan for entry
grade/available run, basement/parking plan for threshold elevation,
building section for clearances) — not a bare "add a Source." Points
to the real, pre-existing "+ Add drawing Source to this Investigation"
control (`templates/case_workspace.html`'s own Investigation-detail
view — corrected during this stage's own testing from an initially
wrong "in Lists" claim to where that control actually renders).

**Finding behavior:** only recorded once every value required for the
calculation (entrance grade, basement grade, slope) AND the available
length are all confirmed — reuses `CaseWorkspaceStore.record_analysis`/
`Finding` completely unchanged (provisional by default, requiring the
existing `ReviewerValidation`/`Disposition` review before Apply — the
"human must confirm before Apply" requirement was already true of
every Finding this mechanism has ever produced, not something newly
added). The statement packs every required field (question evaluated
in full — never truncated — confirmed inputs with their conversation
quotes, formula, computed values, margin, unresolved items, and an
explicit "not a final regulatory/professional engineering sign-off"
caveat).

**Escalation path:** a quantitative-shaped question asked with no
Investigation open yet now also triggers the existing "start an
Investigation" offer (`needs_case`), with a real suggested title
(`quant.suggested_title` — "Basement driveway ramp feasibility" for
the acceptance scenario, generalized from the question's own shape,
not a single hardcoded string) — the full question itself is never
replaced by this shorter title anywhere.

**No external-AI call of any kind** — every calculation is
deterministic arithmetic on reviewer-stated conversation text; verified
directly (a full acceptance-scenario run succeeds with no reachable
Anthropic client at all, not just by source inspection).

**Tests:** `tests/test_p40vw8qa_r6_quantitative_investigation.py` (37
tests) — the reported defect itself, natural-language question
recognition, missing-source/missing-measurement guidance, extraction
provenance/units/no-fabrication, the exact calculation formula
(including the width-never-in-slope-formula structural guarantee),
full conversational flow through candidate-Finding creation,
provisional (not auto-applied) status, conversation persistence, and
no-external-AI-call verification.

**No new UI elements this stage** — the entire capability runs through
the EXISTING Chat composer/conversation dock (`chat.composer.*`,
already registered), so there is nothing new for `UI_REFERENCE_MAP.md`
to record; stated honestly here rather than inventing a reference for
a control that doesn't exist.

**What remains unavailable (honest scope boundary):** real drawing
measurement (OCR/vision-based dimension extraction from a site
plan/basement plan/section) is NOT built — the same capability gap the
R2A stage's own audit already found and recorded, not re-litigated
here. Automated retrieval of governed regulatory/design criteria from
Documents already adopted into the Project is NOT built — the reply
asks the reviewer to state the applicable slope as an explicit
assumption instead of searching for one; a genuine "look up the
adopted standard" capability would be a real, separate future stage.
Only the elevation/slope/available-length pattern is implemented, not
distance/area/capacity/generic dimensional-fit — the module's own
structure (a field-pattern table + a single formula function) is built
to extend to those without a rewrite, but extending it is not part of
this bounded stage.

**Real-browser verification:** no interactive browser-automation tool
is connected in this environment. Every claim above is verified via
direct calls into `interpret_message`/`services.quantitative_
investigation` reproducing the exact acceptance-scenario conversation
turn-by-turn (not merely unit-testing the arithmetic in isolation) —
genuinely strong evidence for the conversational LOGIC, but the actual
rendered chat reply's appearance/readability in a real browser was not
observed; that remains the product owner's own retry to perform, on
this exact ramp-feasibility Investigation, left ready for it.

## 2026-08-02 — CLAUDE-P40-VW8-QA: New Investigation Action in Lists

**Commits:** `a78e8c8`. Product-owner walkthrough evidence: the
Investigations root in Lists had a disclosure chevron and count, but no
visible way to start one from inside that family — the only path was
the Overview page's own buried "+ Start Investigation" subdisclosure.

**Fix:** a real "+ New Investigation" action row, always first inside
the expanded family, present even at zero Investigations (never gated
on `visible_cases` being non-empty) — a plain `<a>` action row,
deliberately never an HTML radio (radios represent mutually-exclusive
choices; this is a command). Reuses `routes/workspace.py:create_case`
and `CaseWorkspaceStore.create_case` completely unchanged — no parallel
Investigation-creation implementation.

**Projection:** selecting it projects the exact same create-form
experience the pre-existing Overview subdisclosure already offered
into the active Display — a new `?view=new-case` route branch,
deliberately kept as its own `show_new_case_form` flag, separate from
the existing `?view=` "directory" vocabulary (`directory_view`) — a
CREATE FORM is not a browsable directory, and E3A's own prior comment
explicitly reasoned about never adding a second directory to that
vocabulary; this doesn't. Uses the same `panel_shell.html` iframe/
`populateDivision` mechanism Documents/Investigations/Overview already
use (`static/js/case_workspace.js`: `buildPanelUrl`/`populateDivision`/
`syncListsActiveState` extended for a new `'new-case'` kind). Division 0
gets real, bookmarkable navigation to the same URL, exactly like every
other leaf.

**Create/Cancel:** explicit actions on the form. A validation failure
(empty title) re-projects the SAME focused form with the flashed
error, rather than the pre-existing Overview-page redirect
`create_case` used before this stage (a small, backward-compatible
improvement for that older entry point too — landing back on the form
you were just filling in is strictly more direct than being bounced to
Overview). Success redirects to `?case=<id>` (preserving `&panel=1`
when the request was projected), matching "select the new Investigation
according to existing repository behavior" exactly — zero new
selection logic.

**Accident-proofing:** clicking the action row cannot accidentally
collapse the family — the toggle's own click listener is bound
directly to the `<button data-tree-parent>` element, never a delegated
listener that could also catch the sibling action row's click
(confirmed by reading the exact binding, not assumed).

**Audit of other expandable families (as required):** Documents/RFIs/
Tasks/Tags/Project Tools have no equivalent "+ New X" action of their
own inside their expanded family today — Documents/RFIs are populated
only via ingestion/RFI-draft workflows elsewhere, not a Lists-driven
create action; Tasks/Tags already have their own creation surfaces
inside Chat's selection toolbar, not Lists. The one pre-existing
precedent is `lists.new-project` ("+ New Project", admin-only, at the
top level) — same `.tree-leaf.launcher-new-project`
color-accent styling this stage's own `.tree-leaf-action` modifier now
mirrors for Investigations. No inconsistency requiring a fix was found
beyond the one this stage closes; not expanded into unrelated new
business capabilities per this stage's own explicit scope boundary.

**Tests:** `tests/test_p40vw8qa_new_investigation_action.py` (28
tests) — zero-count availability, projection (standalone and
panel-only), successful creation with count/leaf update, cancel and
validation-failure paths, no duplicate creation, authorization
(unauthenticated and a stranger without project access both rejected),
and the JS structural guarantees above.

**Real-browser verification:** no interactive browser-automation tool
is connected in this environment. Keyboard activation, focus movement
into the projected form, and focus-return after Cancel are reasoned
from the structural JS/template evidence above (the toggle's isolated
click listener, real `<a href>` elements throughout — all keyboard-
operable by construction, being real focusable, activatable anchor/
button elements, never a `<div onclick>` or similar), not observed
live; that remains the product owner's own walkthrough to perform.

## 2026-08-02 — CLAUDE-P40-VW8-QA-R2A: Smart Drawing-First Project Qualification

**Repository-grounded capability audit** (full writeup in
`services/drawing_intake.py`'s own module docstring): native PDF text/
metadata extraction (`pypdf`) and native DOCX text extraction
(`python-docx`) are real, already-installed dependencies. PDF-page
RENDERING (page -> raster image) is NOT available — no PDF-to-image
library (`pypdfium2`/`PyMuPDF`/`pdf2image`+poppler) is installed. Local
OCR is NOT available — no OCR Python package is installed, AND the
underlying `tesseract` OS binary is confirmed absent from this machine
(`where tesseract` finds nothing) — installing it would be a system-
level infrastructure change, not a bounded code addition, so it was
treated as out of this stage's safely-addable scope rather than
attempted. External-AI vision: `services/bhive_parser.py` already calls
the Anthropic API, but only ever with extracted TEXT, never an image,
and always behind the existing `ACTION_EXTERNAL_AI_REQUEST` security-
policy gate — this stage adds NO new external-AI call of any kind;
sending a drawing's image content to a vision model would be a new
confidentiality-relevant decision requiring its own explicit, opt-in,
separately-authorized stage, not something to wire into an automatic
pipeline step, so it's recorded as a future capability, never attempted
silently.

**Conclusion — the smallest safe, evidenced pipeline actually built:**
native-text-based candidate extraction (LABEL: VALUE pattern matching,
same technique as `bhive_parser.py`'s own pre-existing
`_DOCUMENT_METADATA_LABEL_PATTERN`, a genuinely different drawing-
title-block vocabulary) with full evidence/confidence per candidate,
honest degradation when no native text exists at all (an image-only/
scanned PDF), and a genuine two-request "machine proposes, human
confirms or corrects" flow — no chunked/background processing, matching
this repository's existing synchronous, flat-JSON architecture.

**A real, pre-existing defect found and fixed as a direct prerequisite:**
`BHiveParser.parse()` unconditionally raised `ParserError` (surfaced as
a fully rejected upload) whenever extracted text was empty — the exact
failure mode for a genuine image-only/scanned-PDF site plan, and
squarely the product owner's own original complaint ("Archiosk merely
stores an image-based site plan as an unintelligent attachment"). Now
scoped specifically to `.pdf` (other extensions keep the original
strict behavior — an empty `.txt`/`.docx` genuinely has nothing in it,
not an image-only-drawing equivalent): a structurally valid PDF with no
extractable text now returns a real, successfully-created
`ParsedDocument` with `text_extraction_status="no_native_text"` instead
of failing outright.

**Pipeline (Section 2's 9 steps, as actually implemented):** original
bytes preserved immediately (unchanged, pre-existing); native PDF/DOCX
text inspected at STAGING time only (`services/drawing_intake.py:
analyze_upload` — deliberately NOT the full parse/segment/classify/
consistency pipeline, so the Anthropic-calling stages never run before
a reviewer has even confirmed proceeding); candidate Project/drawing
metadata extracted with evidence (source page, exact matched line,
extraction method, confidence tier); presented on a new confirmation
page (`templates/upload_confirm.html`, `routes/portal.py:
upload_confirm`) for explicit confirm-or-correct; the Project is
created only from confirmed information, via the SAME, unchanged
`ingest_upload` every other path already uses; the original drawing is
attached with its provenance and extraction status exactly as before.
A plain RFP/RFQ with real native text and zero drawing-like candidates
is completely unaffected — routes straight to ingestion exactly as
before this stage, zero new friction for the common case.

**Evidence and confidence (Section 4):** every `CandidateField` retains
`source_page`, `evidence_snippet` (the exact matched line),
`extraction_method`, `confidence` (`high` for an explicit `LABEL:
VALUE` line, `medium` for a weaker/inferred match — e.g. discipline
inferred from a sheet-number prefix like `A-101` -> Architectural, only
when no explicit `discipline:` label was found), and a `status` the
route layer sets to `confirmed`/`corrected` once the reviewer actually
acts — never mutated by extraction itself. A conflicting user-entered
vs. drawing-derived Project name shows BOTH explicitly and requires an
explicit radio choice (entered / candidate / a third typed value) —
submitting without one is rejected (400), never silently resolved
either way. Every candidate offered, the reviewer's actual confirmed/
corrected values, and (when applicable) which name was chosen are
recorded as a new `drawing_metadata_candidates_confirmed` governance-
log event — append-only, alongside the existing `document_ingested`
event, never a mutation of it.

**Qualification rule (Section 5):** Project Operating Environment is
never a candidate field at all (structurally impossible to infer from
a drawing — `CANDIDATE_FIELDS` simply doesn't include it) and is
carried through unchanged from the initial upload form to Project
creation, never re-collected or re-derived on the confirm page. An
image-only PDF with zero candidates still allows Project creation from
confirmed user input alone — incomplete/absent OCR never blocks
creation. Project-name uniqueness is still enforced at confirm time
(reuses the existing `UploadError`/`_reject_if_name_taken` check
unchanged).

**Honest capability degradation (Section 6):** an image-only PDF
preserves the original file, still allows Project creation, and states
in plain language on the confirmation page that no text could be
automatically read and local OCR is not currently available — never a
fabricated candidate value, never the whole upload reported as failed.

**A real bug caught by this stage's own tests before shipping:** the
staging-time `analyze_upload` step initially crashed (`BadZipFile`/an
unhandled pypdf exception) on a malformed/garbage PDF or DOCX — caught
by `test_p40vw8qa_upload_capacity.py`'s own pre-existing fake-file
tests (which post non-PDF/DOCX byte content with a `.pdf`/`.docx`
filename, previously safe because the OLD code path only ever reached
the mocked `BHiveParser.parse`). Fixed by having `analyze_upload`
degrade to zero candidates on any parsing exception, deliberately never
a second place a bad-file error can originate from — the real,
authoritative parse (and its own established error handling) still
runs unchanged at confirm time.

**Tests:** `tests/test_p40vw8qa_r2a_drawing_intake.py` (new, 31 tests)
— native-text/partial-title-block/image-only drawings, Project-name
conflict (all three resolution choices), confidence tiers, confirmed-
vs-corrected tracking, provenance preservation in the governance log,
no invented metadata for a plain RFP, no external-AI call during
staging (verified by making `BHiveParser._classify`/
`_check_consistency` raise if called at all, then confirming staging
still succeeds — not just source inspection), Project-name uniqueness,
Operating-Environment immutability, discard, authorization, and a real
DOCX cover-sheet case. Every test that reaches the confirm-time
`ingest_upload` mocks `BHiveParser.parse` (this codebase's established
hermetic-test convention) — a manual smoke test during this stage's own
development that mocked only `extract_pdf_pages` and not `parse`
genuinely triggered two real Anthropic API calls, a direct, first-hand
confirmation that CLAUDE.md's own hermetic-test warning is not
theoretical.

**Report (per this addendum's own required 6-point structure):**
1. *Extract now:* project_name/number/address, owner/client, drawing
   title, sheet number, discipline (explicit or sheet-number-inferred),
   consultant, issue date, revision, scale — from native PDF/DOCX text
   only.
2. *What's local:* everything — `pypdf`/`python-docx` text extraction
   and the regex-based candidate matching, zero network calls.
3. *Requires governed external AI (not built this stage):* true visual/
   OCR understanding of an image-only drawing — recorded as a future,
   separately-authorized capability, never attempted silently.
4. *Still unavailable:* PDF-page rendering (no image preview of the
   drawing itself is shown) and local OCR (the `tesseract` binary is
   not installed in this environment) — both explicitly reported to the
   reviewer on the confirm page for an image-only PDF, never silently
   dropped.
5. *User must confirm:* every proposed field (all are editable, none
   pre-authoritative), and explicitly which Project name to use
   whenever the entered and drawing-derived names disagree.
6. *Verified vs. structurally inferred:* the full pipeline (staging,
   candidate extraction, confirm/correct, Project creation, governance-
   log provenance, discard, authorization) is verified end-to-end via
   the automated suite against real route/template/service code paths
   — no interactive browser-automation tool is connected in this
   environment, so the actual confirm-page LAYOUT/visual presentation
   is reasoned from template source, not seen rendered; that remains
   the product owner's own walkthrough to perform.

## 2026-08-02 — CLAUDE-P40-VW8-QA-R3: restore distinct Dark/Tinted/Light Appearance modes (real bug, root-caused and fixed)

**Symptom (product-owner walkthrough):** `All -> Dark` selected, every
individual Menu/Lists/Display/Toolbox/Chat row also showed Dark
selected, but the application remained visually Light/Tinted - Dark and
Tinted appeared the same.

**Root cause, found by direct investigation, not guessed:** a CSS
comment cannot contain the literal two-character sequence `*/`
ANYWHERE in its own text, including ordinary prose - every real CSS
parser (not just a naive one) treats the FIRST `*/` after a `/*` as
that comment's end, full stop, no nesting. The earlier Theme Foreground
Contrast Addendum added a comment to `static/css/tokens.css` reading
"...the `--text-*/--canvas/--surface-primary` names it reads are the
Light..." - the wildcard-notation `--text-*` immediately followed by
`/--canvas` accidentally forms a literal `*/`, silently truncating a
much longer intended comment mid-sentence. Everything after that point
- including the real `:root { --dark-canvas: #000000; ... }` block a
few lines later - became un-parseable "selector" text to a real
browser, which discards it as one invalid rule per CSS's own error-
recovery rules. Net effect: `--dark-canvas`/`--dark-surface-primary`/
`--dark-text-primary`/etc. were never actually defined in the browser's
custom-property registry at all; `var(--dark-canvas)` inside
`.app-main.appearance-dark` (and the other four owned surfaces)
resolved to nothing, and `background`/`color` fell back to their
initial values (transparent/inherited), letting the Light canvas
underneath show through - exactly the reported symptom. A second,
pre-existing instance of the identical defect (predating this session)
was found and fixed at the same time: `--review-state-*/--evidence-*`
in the file's own "visual pressure" comment, which was silently
truncating that comment and everything up to the next real `/*` too.

**Investigation method (recorded since it's reusable):** the JS toggle
logic was ruled out first by actually EXECUTING the real script
(extracted verbatim from `templates/base.html`) against a hand-built,
faithful DOM/localStorage simulation in Node.js - it correctly applied
`.appearance-dark` to all five target elements and synced every radio,
proving the bug was not there. CSS selector specificity and cascade
order were checked next (no `!important`, no higher-specificity
override found). The actual root cause was found by writing a small
Python CSS custom-property cascade resolver against the real shipped
files, which reported `--dark-surface-primary`/`--dark-text-primary`
as `UNRESOLVED` - impossible if the `:root` block defining them were
really being parsed, which led directly to checking comment boundaries
character-by-character and finding the accidental `*/`.

**Fix:** inserted a space between the wildcard `*` and the following
`/` in both comments (`--text-* / --canvas` / `--review-state-* /
--evidence-*`) - wording only, zero effect on any token VALUE.
Verified via the same cascade resolver: Dark now correctly computes to
`#000000` background / `#FFFFFF` foreground on all five owned surfaces,
genuinely distinct from Tinted's `#E9EEF6` / `#1B2A40` and Light's own
values.

**Regression guard added:**
`tests/test_p40vw8qa_r3_appearance_mode_integrity.py` (new) - a
structural comment-boundary integrity check (simulates the same real,
non-nested-comment CSS scanning algorithm a browser uses; fails if any
comment is terminated early by a stray `*/`) for both stylesheets, plus
a full computed-value cascade check proving Light/Dark/Tinted resolve
to three genuinely distinct background/foreground pairs on every one
of the five owned surfaces - not merely that the correct radio ends up
checked, which was never the actual bug and which the addendum's own
prompt explicitly said not to accept as sufficient proof. Also pins
down (via source inspection) that the JS toggle mechanism has exactly
one real `applyMode` call site, the "All" handler applies to all five
surfaces, and no `filter: invert`/recolor rule ever touches the
embedded-document viewer chrome (Display's own container follows the
theme; an uploaded PDF/drawing/image's authentic colors are never
altered).

**Real-browser verification:** no interactive browser-automation tool
is connected in this environment. The fix is proven via the CSS
cascade resolver's computed-value output (mechanically equivalent to
what a browser actually computes for `var()` substitution and rule
matching, verified against the real shipped files) and via the JS
executed live in Node against a faithful DOM simulation - genuinely
strong evidence, but final pixel verification (does it *look* right)
remains the product owner's own visual comparison to do, stated
honestly rather than fabricated.

## 2026-08-02 — CLAUDE-P40-VW8 / CLAUDE-P40-VW8-QA: Reference Mode completion, Appearance/theme correction, Lists/Display/Menu structural fixes, Add Tag visible consequence, focused Project chooser, Project-switching dialog, and three follow-up addenda (foreground contrast, site-wide visual consistency, upload capacity)

**Commits:** `4043784` (implementation), `639d84f` (tests). Full suite:
1864 passed, 0 failed, verified on the final combined state (all three
addenda included) immediately before these commits. **No product-owner
acceptance seal recorded** — not requested, and explicitly not
appropriate before the product owner's own real-browser walkthrough
(see this entry's own closing paragraph).

**Starting state:** VW7B (`9a5c11b`/`a61a7b8`) was the actual last
pushed baseline — the product owner's own VW8-QA prompt initially
assumed a "VW8" stage already existed; it did not (verified directly
via `git log`, same discrepancy-surfacing pattern as VW7A's own entry
below), corrected by a mid-session addendum before continuing. Full
suite: 1014 baseline → this stage adds four new test files plus
extensions to eleven existing ones; see the exact final count in the
push-time test run, not repeated here as a stale number.

**Section 3's 14 product-owner-observed defects — all addressed:**
UI Reference Mode is now genuinely discoverable (a real "UI Reference
Mode" checkbox in the account menu, off by default, persisted via
`localStorage`, honored pre-paint on Sign-in/Gateway/Workspace/popups);
every Appearance control (including the per-surface×mode radios) has
its own stable reference; a new Appearance "All" row applies Light/
Dark/Tinted to all five owned surfaces at once and shows an accessible
"Mixed" state rather than silently guessing; Tinted's palette was
relightened to a genuinely light, desaturated navy-blue-grey (was
reading as beige/too-strong); each of Light/Dark/Tinted now governs its
whole owned panel (body, header, empty state, scrollable region, nested
backgrounds, inputs, dividers, conversation history, composer,
divisions) via the existing per-surface CSS-custom-property scoping
mechanism, not a handful of spot-patched elements; the PROJECTS root
now genuinely toggles closed on a second activation (traced to a
generic "collapsing clears an active Display descendant" rule written
for Documents/Investigations incorrectly also firing for the Projects
root, whose own active-project row always carries `.active` — fixed
with a `data-tree-no-clear` guard, not a special case bolted onto the
shared handler); Display's right-click context menu now actually opens,
scoped specifically to `.display-division`'s own `contextmenu` handler
(never Lists/Toolbox/Chat/Menu); Display divisions now fill their real
available height instead of rendering as shallow white rectangles or
small patches — root-caused to `html`/`body` never having a height/
overflow constraint before this stage, so nothing in the Display grid's
own ancestor chain had a real height to distribute `1fr` tracks against
(the same missing constraint also explains defect 12); the Menu bar
now stays fixed while Lists/Display/Toolbox/Chat each scroll
independently — not via `position:sticky`, but because Menu is simply
never inside anything that scrolls once `html,body{height:100%;
overflow:hidden}` → `.app-shell{height:100vh;overflow:hidden}` →
`.app-shell-body{flex:1;overflow:hidden}` is in place; Add Tag now has
a real visible consequence on the tagged source text (see below); "Open
an existing project" now leads to a small focused chooser instead of
the full Projects-management page (see below).

**Add Tag visible consequence:** `app.py`'s `hotlinks` template filter
gained optional `message_id`/`anchor_scope`/`anchor_case_id` args
(backward-compatible — omitted, behavior is byte-identical to before)
that additionally wrap any tagged substring in
`<mark class="tag-highlight-inline conv-tag-color-{color}"
data-tag-occurrence-id="{id}" data-ui-ref="chat.tag-highlight"
title="Tagged: {name}">`, computed in ONE pass against the raw text
(hotlink-segment boundaries and tag-range boundaries merged into one
ordered cut-point list before rendering) so overlapping/partial
intersections with a hotlinked filename still produce valid, correctly-
nested HTML rather than two independent substring-wrapping passes
corrupting each other's output. `services/case_workspace.py` gained
`tag_occurrences_for_message` (the read-side counterpart) — reuses
`TagOccurrence`/its existing `source_anchor` exactly; no new business
object. `tests/test_p40vw8qa_tag_visible_consequence.py` (new) covers
the end-to-end route→rendered-HTML path, overlap/duplicate handling,
case- vs project-scoped anchoring, and the backward-compatible no-args
call shape.

**Focused existing-Project chooser:** new `routes/portal.py:
choose_project` (`/projects/choose`) + `templates/project_chooser.html`
(new, extends `gateway_base.html` — no Lists panel, no counts/sort/
Delete-forms), reusing `_accessible_documents`/`_safe_workspace`
unchanged (no new authorization surface). `projects_list`/`projects.html`
are untouched and remain the separate "administrative management"
destination, still reachable at `/projects`. Gateway's "Open an
existing project" now points here instead.

**CLAUDE-P40-VW8 — Project-switching interruption dialog:** activating
a different Project from Lists now shows an accessible dialog (Stay in
Current Project / Switch in This Tab / Open in New Tab) instead of
silently replacing the workspace. `data-project-id` on a Projects-root
leaf link marks it as a real switch target — present only when a
DIFFERENT Project is already open (`project_id is defined`); the active
Project's own row (`lists.project.self`) never carries it, so
"activating the already-current Project never opens the dialog" holds
by construction. Switch/Open-in-New-Tab reuse the link's own real,
already-authorized `workspace.show_workspace` href — no new route, no
client-side authorization decision. **A regression caught and fixed
during this stage's own self-review:** the first version also added a
`data-project-name` attribute duplicating the leaf's own already-
visible text, which broke CLAUDE-P40-E2B1's "a Project name must never
appear a second time" invariant (`test_p40e2b1_single_launcher_and_
directories.py`/`test_p40e2b1a_recursive_projection.py` both caught
this on the pre-commit full-suite run) — fixed by reading the target
name from the link's own `textContent` in JS instead of a redundant
attribute. `tests/test_p40vw8_project_switch_and_chooser.py` (new)
covers dialog gating, leaf-attribute correctness, the no-duplicate-name
regression specifically, and the chooser route.

**Theme Foreground Contrast Addendum (mid-session, product-owner
follow-up):** `tools/check_contrast.py`'s own `REQUIRED_PAIRINGS` only
ever checked LIGHT-mode pairings (the token names it reads are the
Light `:root` names; Dark/Tinted use separately-prefixed names it never
parsed) — auditing the full text-tier × surface-tier matrix directly
for all three modes found Light itself fully AA-compliant everywhere,
but two real sub-4.5:1 failures neither that script nor any prior
stage's spot checks had caught: `--dark-text-metadata` on
`--dark-surface-selected` (4.24:1) and `--tint-text-metadata` on
`--tint-surface-hover`/`-selected` (4.09:1 / 3.46:1) — both the
deepest/most-saturated layering step in each mode. Corrected in
`tokens.css` (`--dark-text-metadata: #BBB3A8`, `--tint-text-metadata:
#3D4D66`), each with enough margin to clear 4.5:1 while staying
visibly the dimmest of the three text tiers.
`tests/test_p40vw8qa_theme_foreground_contrast.py` (new) pins the full
corrected matrix down as a running regression, verifies the seven
semantic accents at 3:1 across all three modes, and verifies the
per-surface CSS-scoping mechanism (`.appearance-dark`/`.appearance-
tinted`) redefines the complete required token set on all five owned
surfaces, not just the two or three the original VW6 test file
checked.

**Site-Wide Visual-System Consistency Addendum (mid-session, product-
owner follow-up):** exhaustive template/stylesheet audit (no hardcoded
colors found anywhere in templates; two in `main.css` — see below) plus
two real, site-wide corrections: (1) `font-stretch: condensed` on
`html,body` removed — the font stack (`"Arial Nova Cond", "Arial
Narrow", Arial, sans-serif`) already names its condensed variants
explicitly, so `font-stretch` had no real effect THERE, but on the
fallback tier (plain "Arial"/`sans-serif`, i.e. any system without
Arial Nova installed) it caused the browser to synthesize a horizontal
squish — "unjustified synthetic font stretching," and specifically on
whichever system *didn't* have the intended font, the opposite of
graceful degradation; removing it changes zero px of which font family
loads. (2) `.blueprint-grid`'s backdrop line color (`#5995C0`, a fixed,
z-index:-1, 0.3-opacity brand watermark) was the one hardcoded hex
value left in `main.css` outside `tokens.css` itself — tokenized as
`--blueprint-grid-line` (same value, same deliberately mode-invariant
reasoning as `--divider-strong`) purely so `tokens.css` stays the one
place any shipped color is defined. Gateway/Auth pages confirmed
deliberately Light-only by design (no per-panel Appearance system
pre-workspace) but built from the SAME semantic token names as the
themed workspace shell, not a parallel palette.
`tests/test_p40vw8qa_site_wide_visual_consistency.py` (new) guards
both corrections as running regressions (no hardcoded color anywhere
outside `tokens.css`, no inline color styles in any template, no
`font-stretch` declaration anywhere) plus Gateway/Auth token-family
and heading-scale consistency checks.

**UI Reference Mode / registry:** `data-ref` renamed to `data-ui-ref`
throughout (templates, CSS, `app.py`, docs, tests) to match this
stage's own naming requirement; `UI_REFERENCE_MAP.md` gained new
`## Gateway`/`## Auth` sections and every new reference this stage
introduced (Appearance All row + its 3 mode radios, per-surface×mode
radios corrected from broken abbreviated shorthand to fully-qualified
values, Display context-menu + sub-actions, selection-toolbar actions,
`chat.composer.input`/`.send`, `chat.tag-highlight`,
`lists.project-switch-dialog` + its 3 actions, `gateway.chooser`/
`.search`/`.leaf`/`.back`, `auth.signin.*`). The Sign-in/Gateway
isolation invariant (VW5) evolved from "zero refs anywhere" to "no
workspace-shell-prefixed (`lists.`/`display.`/`toolbox.`/`chat.`/
`menu.`) refs leak" — Sign-in/Gateway now correctly carry their OWN
(`auth.*`/`gateway.*`) references, which is required, not a violation.

**Deferred, not implemented this stage (Section 13):** a microphone/
voice-input control for the Chat composer. Recorded here per explicit
instruction, reserved for a future bounded stage — no groundwork
(no UI stub, no route, no permission plumbing) was added, since the
prompt asked only that the requirement be recorded, not scaffolded.

**Project-Creation Upload-Capacity Correction (mid-session, product-
owner follow-up):** a real-document walkthrough hit Werkzeug's raw
default "Request Entity Too Large" page creating a Project. Diagnosis:
the ONLY enforcing layer reachable in dev is Flask's `MAX_CONTENT_LENGTH`
(`config.py`, sourced from `.env`'s `MAX_UPLOAD_MB`, was `25`);
`deploy/nginx.conf`'s `client_max_body_size` is a second, production-
only layer, already documented as "keep in sync," now updated to match.
Werkzeug's own form parser raises `RequestEntityTooLarge` **before**
`routes/portal.py:upload`'s view function ever runs, so a rejected
request never reaches `ingest_upload` at all — confirmed directly (not
just asserted) via `tests/test_p40vw8qa_upload_capacity.py`'s own
before/after registry-and-`workspace_sources`-directory checks: zero
partial Project/Document/temp-file state, and the requested project
name stays available for an immediate retry (`_reject_if_name_taken`
is never reached either). `routes/api.py`'s own existing blueprint-
scoped JSON 413 handler was the ONLY place this was ever handled — the
real web upload FORM (`routes/portal.py`) had no equivalent and fell
through to Flask's unstyled default.

Raised to **60MB** (`MAX_UPLOAD_MB` in `.env`/`.env.example`,
`client_max_body_size` in `deploy/nginx.conf`, kept consistent) —
evidence-based, not arbitrary: `services/ingestion.py`'s `ingest_upload`
reads the whole file into memory (`file_storage.read()`), a synchronous,
single-request, no-chunking/no-background-queue architecture bounded by
`ANTHROPIC_CLASSIFY_BUDGET_SECONDS=90`/`GUNICORN_TIMEOUT=150`. 60MB is
comfortable for real text-based RFP/RFQ/spec/report PDFs and DOCX files
with exhibits, and stays well inside a safe per-request memory/time
budget; a full scanned drawing package (100MB+) is explicitly recorded
as NOT safely supported by this architecture yet (needs streaming/
chunked upload or background processing) — a deliberate, documented
limitation, not silently papered over with an arbitrarily larger number.

Added `app.py`'s own app-level `@app.errorhandler(413)` (styled via the
existing `errors/error.html`/`_render_error` machinery 404/500/403
already use — never a new template), stating the actual configured
limit in plain language, a "Choose a different file" action back to
`/upload`, and no path/stack-trace/internals exposure (verified
directly). `routes/api.py`'s own JSON 413 handler is unaffected
(blueprint-scoped handlers win over the new app-level one for
`/api/v1/*`). `templates/upload.html` gained client-side pre-submit
file-size validation (the exact `"This file is X MB. The current
maximum is Y MB..."` message format specified), a stated processing
limitation note, and UI references on every control (`upload.*`) —
server-side `MAX_CONTENT_LENGTH` remains the real enforcement; the
client-side check is only a convenience. `tests/test_p40vw8qa_upload_
capacity.py` (new, 21 tests) covers boundary/over-limit behavior,
custom 413 presentation, transactional safety, authorization
preservation (a non-admin/unauthenticated request still never reaches
the 413 path — `@admin_required`/`@login_required` win first), and
supported/unsupported file types.

**Real-browser verification:** no interactive browser-automation tool
is connected in this environment (confirmed via `ToolSearch` — only
`WebFetch`, which summarizes content rather than driving interaction).
Every claim above is a structural/route/rendered-HTML/JS-source
assertion, verified by the automated suite; the actual pixel/
interaction-level walkthrough (Reference Mode toggle in a live account
menu, Appearance All/mixed-state visually, Display right-click/geometry
across viewport widths, the Project-switching dialog's focus/Escape/
popup-blocked behavior, tag highlight color contrast by eye) is left to
the product owner, stated honestly rather than fabricated, per that
addendum's own explicit instruction.

## 2026-08-02 — CLAUDE-P40-VW7B: left Lists root system and active-Display projection cleanup

**Commits:** `9a5c11b` (implementation), `a61a7b8` (tests). Starting
state was `16df46d` (the P40-VW7A checkpoint commit) - HEAD and
`origin/main` verified equal beforehand, tree clean except the
pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Full suite: 1792
passed, 0 failed (was 1768; 24 net new - 25 in the new
`tests/test_p40vw7b_root_system_and_projection.py`, minus one removed
as genuinely dead-code coverage, see below). **No product-owner
acceptance seal recorded** - not requested, and this stage's own
Section 19 explicitly said not to issue one.

**Premise correction before starting**: this stage's own prompt
assumed a "CLAUDE-P40-VW7A UI-reference registry" already existed as a
prior, separate stage. It did not - verified directly (`git log
--all`, a repo-wide search) before touching anything, surfaced the
discrepancy, and built VW7A for real as its own bounded, committed
stage first (see that entry, immediately below this one) before
starting VW7B against it, per product-owner instruction.

**What VW7B actually built** - the core, most literal reading of "a
leaf selection should ordinarily project into the currently active
Display": the active-Display-targeting mechanism, until now Documents
only (a real file, embedded via a plain `<iframe src=file_url>`/
`<img>`), now also covers Investigations and Overview. Mechanism: a
new `panel_only` flag (`?panel=1`) on the EXISTING `show_workspace`
route (no new route, no duplicated authorization - an unauthorized
`?panel=1` request fails at the identical `_load_workspace_or_404`
call every other view of the same data already goes through) and
`templates/panel_shell.html` (new): a minimal standalone document
`case_workspace.html` extends instead of `base.html` when that flag is
set, so Division 0's own content renders without Menu/Lists/Toolbox/
Chat chrome, safe to embed in an `<iframe>`. Division 0 itself keeps
real navigation unconditionally (VW4's own precedent, unchanged -
Stable URL Restoration untouched). `static/js/case_workspace.js`'s
`populateDivision`/`clearDivision`/`saveOpenDivisions` generalized from
a bare source id to `{kind, id, displayName}`, backward-compatible
with a session's sessionStorage saved before this stage. A new
`syncListsActiveState` keeps Lists' own highlighting understandable
across several simultaneously-open Displays (Section 7) without ever
touching a leaf's own server-rendered `.active` state.

**A real bug caught by the stage's own tests before shipping**: the
first working version of `panel_shell.html` rendered `case_workspace.html`'s
FULL `{% block content %}` unconditionally, including the 5 extra
Display divisions and the right-click context menu - meaning a panel
iframe recursively rendered its own empty 6-division grid inside
itself, and (had a saved `sessionStorage` state existed) could have
tried to populate ANOTHER panel iframe inside that one. Caught by
`test_panel_suppresses_division_zero_header_and_overview_back_link`'s
own assertion, not discovered live - fixed by wrapping that entire
block in the same `{% if not panel_only %}` pattern already used for
Division 0's own header.

**Root-system correction, evidence-based**: "Project Data Management"
(Reset Project Data) was nested inside the active Project's own
"Project Tools" branch. Reading `routes/portal.py`'s
`reset_project_data` directly (not assumed) showed it resets the WHOLE
`REGISTRY_STORE_PATH` - every Project in the deployment ("returns the
app to a clean, no-project state") - not the one Project whose tools
branch it sat in. Relocated to a new top-level `lists.system-data-management`
leaf, same route/gate/`html_id`, recorded as a retired reference in
`UI_REFERENCE_MAP.md` rather than a silent id reuse.

**Smaller, evidenced cleanups**: coherent empty states added to
Documents/Investigations/RFIs (they were missing the "No X yet."
pattern Tasks/Tags already established); RFI leaves gained
active-state and the same `data-case-id`/`data-case-title` attributes
as Investigation leaves, so an RFI participates in active-Display
projection identically (targeting its owning Investigation, exactly
matching what its real-navigation href already did); `promoteDivision`
removed as dead code (confirmed zero callers anywhere, via search,
before deleting - one pre-existing test that only checked its source
text was present, never that it ran, was removed rather than
weakened).

**Deliberately not done, with reasons recorded inline**: the
empty-division `<select>` picker (`display.division.picker`) stays
Documents-only - the Lists-leaf-click path is what this stage's own
prompt asked for, extending the picker too is a considered, deferred
enhancement, not scope creep into it. Tasks/Tags stay routed to the
persistent Chat surface, not Display - Section 10's own explicit
"document any justified exception" allowance, since fragmenting
conversation context into a Display division would be a worse design
than keeping it together. No VW8 Project-switching/safe-switching
behavior, no cross-Project discovery, no Welcome/Hafez, no P41 -
none started.

**Remaining/uncertain**: no real-browser walkthrough performed (no
browser-automation tool connected in this environment, consistent with
every VW stage before this one) - the 15-step journey this stage's own
Section 17 describes is verified here only via structural HTML/route/
JSON/regex assertions against the JS/template source, not pixel-level
Display-division layout, actual iframe rendering, or Light/Dark/Tinted
visual correctness inside a panel iframe specifically (the CSS/JS
mechanism for it is in place and structurally tested, but never
visually confirmed). `STATIC_VERSION` bumped to 37 in `.env`
(git-ignored) and the dev-server reloader chain (4 accumulated
processes) killed and restarted; verified serving `main.css?v=37`.

## 2026-08-02 — CLAUDE-P40-VW7A: left Lists/Menu/Display/Toolbox/Chat UI reference registry

**Commits:** `fd9044e` (implementation), `cbccadf` (tests). Starting
state was `62919ba` (the P40-VW7 checkpoint-correction commit) - HEAD
and `origin/main` verified equal beforehand, tree clean except the
pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Full suite: 1768
passed, 0 failed (was 1745; 27 net new). **No product-owner acceptance
seal recorded.**

**Why this stage exists**: CLAUDE-P40-VW7B's own prompt assumed a
"CLAUDE-P40-VW7A UI-reference registry/map" already existed from a
prior stage - it did not. Verified directly (`git log --all` for any
VW7A commit, a repo-wide search for a registry file or `data-ui-ref`-
style attribute) before touching anything, surfaced the discrepancy,
and asked how to proceed rather than silently fabricating a "VW7A
already happened" story or guessing at reference ids while
implementing VW7B's much larger scope. Product owner chose: build
VW7A for real, as its own bounded, committed stage, then run VW7B
against it - this entry is that stage.

**What VW7A is**: purely additive instrumentation, zero behavior
change. Every family/leaf-pattern/action across Menu, Lists, Display,
Toolbox, and Chat gained a stable `data-ui-ref="<surface>.<family>..."`
attribute directly on its existing element - never a new wrapper,
never a route/class/behavior change. `UI_REFERENCE_MAP.md` (new,
repo-root, alongside `MANIFEST.md`/`CONTINUATION_CHECKPOINT.md`) is
the central registry: 55 reference ids, one row each, documenting
current element/label/behavior/authorization notes/status
(active/retired). A new "UI Reference Mode" toggle (Account menu, off
by default, `localStorage`-persisted like the existing risk-layer/
history-full toggles) overlays each `data-ui-ref` value as a small CSS
badge (`content: attr(data-ui-ref)` - no new JS needed to read it) for
live cross-checking against the registry.

**Design choices worth remembering**:
- `data-ui-ref` identifies a KIND of control, not one instance - a
  repeating pattern (a Document leaf, a Task row) shares one value
  across every rendered instance; the existing per-instance attributes
  (`data-source-id`, `data-task-id`, an `href`) still disambiguate
  which one, unchanged.
- Deliberately NOT instrumented: per-instance content inside an
  already-referenced family (a single Finding card, a single
  Appearance-matrix radio) - proportional coverage for what VW7B and
  beyond actually need to cite, not maximal coverage for its own sake;
  documented explicitly in `UI_REFERENCE_MAP.md` itself so this reads
  as a stated boundary, not a gap.
- The badge's z-index (100) deliberately sits one tier above VW7's own
  Add Tag/Make Task dialogs (80, previously the file's own claimed
  ceiling) - a debug/QA aid must stay visible even while inspecting a
  control inside an open dialog. `tests/test_p40vw6_theme_correction.py`
  updated accordingly (see below) - this is the second time that
  file's "global max z-index" invariant has needed updating as new,
  legitimately-higher overlays were added; a future stage introducing
  a THIRD new overlay tier should expect the same.
- The badge's font-family reuses `--font-mono` (a technical dot-path
  id string is exactly IBM Plex Mono's reserved register per
  `tokens.css`'s own doctrine, the same class `.finding-provenance`/
  `.region-status` already occupy) and its font-size uses the existing
  `--text-2xs` token (11.2px) specifically to clear this app's own
  11px legibility floor - an initial `0.62rem` value failed that floor
  and was corrected before committing, not discovered after.

**Test-infrastructure note**: six pre-existing tests failed on the
first full-suite run after implementation - all six were either a
brittle exact-string/exact-attribute-order assertion broken by an
inserted (harmless) `data-ui-ref` attribute, or a z-index/font-mono-count
invariant that genuinely needed updating for the same legitimate
reasons above. None were regressions; each was fixed by updating the
test's own selector/expected-count to the new, still-correct reality
(same pattern this repo's CLAUDE.md already documents for the font-
mono/wordmark tests, and the same pattern VW7 itself used once for the
popup-stacking test). Full list: `test_global_search_and_header.py`
(brand-lockup selector, font-mono count 2→3),
`test_p40e1a_single_dock_and_terminology.py` and
`test_projects_directory_redesign.py` (two Lists-toggle/leaf exact-
string matches), `test_p40vw6_theme_correction.py` (retired the
"conv-dialog is the global max" claim, added the badge-is-now-the-max
assertion in its place).

**Remaining/uncertain**: no real-browser walkthrough performed (no
browser-automation tool connected in this environment). `STATIC_VERSION`
bumped to 36 in `.env` (git-ignored) and the dev-server reloader chain
(4 accumulated processes, same accumulation pattern the `restart-app`
skill exists for) killed and restarted; verified serving `main.css?v=36`.

**Next**: CLAUDE-P40-VW7B (Left Lists Root System and Active-Display
Projection Cleanup) proceeds from here, against this registry.

## 2026-08-02 — CLAUDE-P40-VW7: project-scoped conversation Tags and Tasks

**Commits:** `3457c9f` (implementation), `a2715fe` (tests), `0651c91`
(this entry). Starting state was `ad2cc23` (the P40-VW6 checkpoint
commit) - HEAD and `origin/main` verified equal beforehand, tree clean
except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Full suite: 1745
passed, 0 failed (was 1690 before this stage; 55 net new - 54 in the
new `tests/test_p40vw7_conversation_tags_and_tasks.py`, plus one
replacing an obsoleted VW6 assertion, see below). **No product-owner
acceptance seal recorded** - not requested this stage, and the
prompt's own Section 13 explicitly said not to issue one; subject to
the real-browser walkthrough this environment has no tool to perform
itself (stated as a limitation below, not fabricated).

**What this authorizes, narrowly**: a OneNote-style contextual toolbar
on selected Project Conversation text (`Add Tag`/`Make Task`/
`Highlight`/`Important`/`Question`/`Copy`), persistent source-anchored
Tags/Highlights and real persisted Tasks, and two new Lists branches
(`Tasks <count>`/`Tags <count>`) inside the active Project's own tree
that update live without a reload. Explicitly NOT authorized by this
same prompt: cross-project intelligence, machine-generated assumption
correction, organization-wide task management, external integrations,
or general autonomous chat governance - `governance/STATUS.md` gained
one new row recording exactly this boundary, not a reopening of the
"Application implementation, broadly: STILL FROZEN" default.

**Design choices worth remembering**:
- Anchoring is a text-quote-selector (scope + case/message/guidance
  identity + start/end offsets + exact quotation + limited prefix/
  suffix), computed client-side via `Range`-based offset math against
  a message's own `.conv-message-text` span - a new wrapper added
  specifically so the offset computation walks exactly the canonical
  `message.text` string, never the surrounding role-label/"Re:"/
  Source-grounding chrome that shares the same `.conversation-message`
  div. Confirmed `hotlinks()` never changes character count, so
  offsets computed against rendered `.textContent` stay valid against
  the server-stored string.
- `Highlight`/`Important`/`Question` are `BUILT_IN_TAGS` - fixed code
  constants, never stored per-project - so they mean the same thing in
  every Project regardless of who tags first; a custom tag whose
  normalized name collides with a built-in's name resolves to the
  built-in instead of creating a duplicate.
- `_validate_source_anchor` performs a REAL existence check (the case/
  message actually resolves against the current workspace) before
  anything is ever persisted - Tag/Task creation cannot itself produce
  an unresolvable anchor. `resolve_conversation_anchor` is the separate
  READ-time check `show_workspace` uses to decide "Source unavailable"
  - exercised in tests by directly editing a persisted record's
  `message_id` to simulate data drift, since the write path can't
  produce that state on its own.
- Deliberate scope simplification: Tags/Highlights are NOT rendered as
  permanent inline in-message highlights. The Lists panel is the sole
  discovery surface; navigating to a source scrolls the whole message
  into view and applies a temporary flash (`--highlight-orange-tint`,
  2.5s, removed by JS) rather than a permanent `<mark>` wrap reconciled
  against `hotlinks()`'s own substring-wrapping - reported here as an
  honest, bounded corner, not silently cut.
- First use of `fetch()` anywhere in this app - `tools/
  dependency_fit.py` was actually run beforehand per CLAUDE.md's own
  instruction (clean PASS on all 6 checks) rather than assumed
  compatible. Used only where Section 12's browser-verification steps
  require an update with no reload (Tag/Task creation, Tag removal);
  Task complete/reopen stayed classic form-POST + redirect on purpose.
- New `--tagcolor-*` tokens (`tokens.css`) are deliberately
  mode-invariant, unlike every other token in that file - they're
  never text, only a small bordered swatch dot, so a border ring
  (not six more dark/tinted variants) is what actually keeps them
  visible in Light/Dark/Tinted. The navigate-to-source flash instead
  reuses the existing, already mode-verified `--highlight-orange-tint`
  (a genuine semantic fit - "current position in a sequence") rather
  than a raw swatch color, after checking that a raw yellow flash
  would fail contrast against white Dark-mode text.
- `governance/STATUS.md`'s new row and this entry both explicitly do
  NOT interpret this authorization as covering cross-project
  intelligence, autonomous chat governance, or CLAUDE-P41 - none of
  that was started.

**Test-infrastructure note**: `tests/test_p40vw6_theme_correction.py`'s
`test_popup_z_index_is_the_highest_in_the_file` asserted the VW6
Appearance popup's z-index was the file's global maximum - the new
selection toolbar (70) and Add Tag/Make Task dialogs (80) legitimately
need to sit above it too (a dialog opened while the popup happens to
be open must still render on top), so that specific numeric ceiling is
now genuinely different, not regressed. Renamed/restructured rather
than weakened: the popup's own real invariant (strictly above the
Display context menu) is preserved and asserted directly, and a new
test confirms the toolbar/dialog are now the correctly-ordered top two
overlays with the dialog as the file's actual maximum.

**Remaining/uncertain**: no real-browser walkthrough was performed (no
browser-automation tool connected in this environment, consistent with
every VW stage before this one) - the 17-step journey the prompt's
Section 12 describes is verified here only via structural HTML/route/
JSON assertions, not pixel-level positioning, keyboard focus order, or
actual Light/Dark/Tinted visual rendering. `STATIC_VERSION` bumped to
35 in `.env` (git-ignored, not part of either commit) and the dev
server restarted via the `restart-app` skill for the CSS/JS changes to
take effect.

## 2026-08-02 — CLAUDE-P40-VW6: corrected Light, Dark, and Tinted panel rendering

**Commit:** `8abbd0d`. Full suite: 1690 passed, 0 failed (was 1650; 40
new). Starting state was `0021251` (the P40-VW5 checkpoint) - HEAD and
`origin/main` verified equal, tree clean except the pre-existing
untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. **No
product-owner acceptance seal recorded** - explicitly not requested
this stage; subject to another visual walkthrough.

**Product-owner browser observations**: Light panels showed untreated
portions; Dark panels weren't genuinely black, the Appearance popup
let underlying text show through, the workspace/Chat divider
disappeared; Tinted panels were inconsistently beige/gold rather than
a uniform light navy-blue.

**PRIMARY ROOT CAUSE**: `tokens.css`'s own VW3-authored Dark-mode
comment block ended with a stray Jinja-style `#}` instead of CSS's
own `*/` - a copy-paste artifact, present since the very first VW3
commit (`e4b241d`). CSS comments only end at the FIRST real `*/` -
`#}` is just more comment text - so the `:root {` meant to open the
`--dark-*` token block was itself swallowed inside the still-open
comment, and every `--dark-*` declaration that followed was a bare,
rule-less custom-property declaration: invalid CSS, silently dropped
by every browser. Every `var(--dark-canvas)`/etc. reference in
`.appearance-dark` therefore resolved against tokens that were NEVER
ACTUALLY DEFINED, collapsing `--canvas`/`--surface-primary`/
`--text-primary` to their inherited/initial value inside that scope -
explaining "not genuinely black" and "some text and internal panel
layers do not receive the Dark treatment" far more completely than
any single component gap could. Every VW3/VW4/VW5-era test that
appeared to verify Dark mode's tokens passed anyway, because they all
read `tokens.css` as plain text via regex, which cannot distinguish a
real declaration from dead text inside a broken comment - why this
went undetected across three prior stages. **Fixed with a one-
character change** (`#}` → `*/`); the new `BrokenCommentGuardTests`
strips real CSS comments before checking anything, closing that
specific blind spot for good.

**Separate, genuine defects found and fixed independently of the
comment bug**:
- VW3's Tinted mode never redefined the surface's token SCOPE the way
  Dark was meant to - it only swapped ONE element's own background per
  surface to `--surface-secondary` (Limestone/beige, a real, correct,
  UNRELATED token, never a dedicated Tinted palette). Fixed: Tinted
  now uses its own `--tint-*` family, redefining the full standard
  token set in the same combined selector `.appearance-dark` already
  used. `--tint-surface-primary` is `#D8E2F0` directly (the product
  owner's own specified navy, used as the actual painted panel fill).
- `--dark-canvas`/`--dark-surface-primary` were a dark warm brown
  (`#1A1814`/`#25221D`) in the source text - now literal `#000000`,
  `--dark-text-primary` literal `#FFFFFF`, every token recomputed and
  re-verified against pure black via `tools/check_contrast.py` (ALL
  PAIRINGS PASS, same for the new tint family).
- Browsers never theme a bare `<select>`/`<input>`/`<textarea>`/
  `<button>` from surrounding page CSS - the existing font-family
  backstop rule never had a color equivalent. Extended with
  `background-color`/`color`/`border-color` (tokens) - fixes the
  VW1/VW4 Document-picker dropdown and every other unstyled form
  control centrally.
- The workspace/Chat divider used `--border` (mode-scoped, always
  matching whichever mode Chat itself was in) - two adjacent Dark
  surfaces produced two very-low-contrast dark-on-dark lines,
  technically present, not perceptible. Fixed with a new
  `--divider-strong` token, deliberately never redefined by either
  scope, verified ≥3:1 against light/dark/tint backgrounds all at once
  (5.04:1 / 4.00:1 / 4.02:1).
- The Appearance popup's z-index (20) sat below the Display context
  menu's (40) with no real margin - raised to 60, now the highest
  z-index in `main.css`. Its background was always a solid token
  color, never rgba - confirmed, not changed for its own sake.

**Test-infrastructure note**: updated 1 pre-existing test
(`test_p40vw3_appearance_matrix.py`) whose assertion checked for the
OLD single-property Tinted rule this stage deliberately replaces - not
weakened, checking the new combined-selector mechanism instead.

**Tests**: added `tests/test_p40vw6_theme_correction.py` (40 tests) -
the comment-bug guard, full Dark/Tinted palette coverage (including
two real, non-simulated `tools/check_contrast.py` subprocess runs),
popup opacity/stacking, the divider token's measured contrast against
all three backgrounds, the global form-control backstop, independent
mixed-mode wiring and persistence/legacy-compat (VW3 preserved), VW4
Display Layout control readability, VW5 Sign-in/Gateway shell
boundaries (confirmed untouched), and confirmation no CSS filter/
blend-mode exists that could recolor actual document content.
Confirmed load-bearing by reverting both CSS files and observing
20/40 fail (including all 3 comment-guard tests correctly catching the
original bug), then restoring them. Directly affected suites re-run
explicitly (229 tests) - all passing. Full suite run to termination:
1690 passed, 0 failed.

**Browser evidence and its limitation, stated honestly**: no browser-
automation tool was actually connected in this session (checked
directly via tool search, twice, consistent with every prior VW
stage). Verification rests on structural CSS/JS/HTML source assertions
and real (non-simulated) contrast-tool runs, not visual inspection or
real computed-style reads. **The product owner should visually verify
all five rows Light, all five Dark, all five Tinted, at least three
mixed-mode combinations, the Appearance popup open in each Menu mode,
the Chat divider under contrasting adjacent modes, and both wide and
narrow viewports** during the continued walkthrough.

Preserves VW1-VW5 behaviour (re-confirmed by this stage's own tests),
routing/Sign-in/Gateway isolation, Display division behaviour, and all
real Project/Document/Investigation/RFI/conversation data - none were
touched. P40-E3B remains closed as DEFER; the conversation Tasks/Tags
work and P41 were not started.

## 2026-08-02 — CLAUDE-P40-VW5: standalone Sign-in and Project Gateway shell isolation

**Commit:** `a02425c`. Full suite: 1650 passed, 0 failed (was 1613; 36
new). Starting state was `2f89d70` (the P40-VW4 checkpoint) - HEAD and
`origin/main` verified equal, tree clean except the pre-existing
untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. **No
product-owner acceptance seal recorded** - explicitly not requested
this stage.

**Product-owner walkthrough correction**: the Project Gateway
(`/gateway`) displayed the left Lists panel. Required journey: fresh
unauthenticated entry -> standalone Sign-in -> successful sign-in ->
Project Gateway (no Lists/workspace shell) -> open/create a Project ->
full Project workspace (with its Lists panel).

**Root cause, diagnosed before changing anything**: `templates/
gateway_base.html` extended `base.html` and overrode only `{% block
content %}` - `base.html`'s own Lists panel is gated on bare
`authenticated`, unlike Toolbox/Chat/Display-Layout (already gated on
`project_id is defined and workspace is defined`), so it rendered
around Gateway's centered card on every visit.

**Fix**: `templates/gateway_shell.html` - a genuinely standalone shell
(the same principle `templates/auth_shell.html` already established
for `/login` et al., CLAUDE-P40-D1) that `gateway_base.html` now
extends instead of `base.html`. No Lists/Toolbox/Display/Chat markup
exists in this file to leak - structurally absent, not CSS-hidden. It
has its own minimal top bar (real `authenticated`/`is_admin`/
`current_username`, an account menu: Sign out, Removed Projects,
admin-only Security) so those functions stay reachable now that
they're not Lists leaves on this page - server-side authorization on
each route is unchanged and is the real enforcement, the menu is
discoverability only. `app.py`'s `inject_globals()` now skips the
`nav_recent_projects` store query for the Gateway endpoint
specifically, not just its rendering.

`routes/portal.py`'s `index()` now redirects an unauthenticated `/`
visit straight to `/login` instead of rendering an intermediate
marketing page. `login_required`/`admin_required` (`services/auth.py`)
were already correct and untouched: unauthenticated access to
`/gateway` or any Project workspace already redirected to
`/login?next=...`, and admin-only routes already returned 403 for an
authenticated non-admin - both re-confirmed by this stage's own tests,
not re-implemented.

Widened `.gateway-card` via a new `.gateway-card-wide` modifier
(Section 2: "must use the available width and remain visually
centred") without touching the base 480px width `login`/`forgot-
password`/`reset-password`'s own `.gateway-card-compact` still relies
on.

**Test-infrastructure note**: updated 2 pre-existing tests whose
premise VW5 deliberately supersedes (a Gateway sanity check that used
to assert `/gateway` showed `app-shell`/`launcher-panel`; an anonymous-
home test that used to assert HTTP 200 with a "Sign in to get started"
link) - not weakened, checking the new, deliberately different
behaviour instead, with a real workspace-page check added to cover
what the first test's own docstring actually meant to protect.

**Tests**: added `tests/test_p40vw5_signin_gateway_isolation.py` (36
tests) across all 16 required areas from the prompt. Confirmed load-
bearing by reverting every changed file (including deleting the new
shell) and observing 9/36 fail with the exact pre-fix leak visible in
the diff, then restoring everything. Directly affected suites re-run
explicitly (370 tests) - all passing. Full suite run to termination:
1650 passed, 0 failed.

**Browser evidence and its limitation, stated honestly**: no browser-
automation tool was actually connected in this session (checked
directly via tool search both before and during this stage,
consistent with every prior VW stage). Verification rests entirely on
structural HTML/route assertions. **The product owner should walk the
complete journey in a real browser** (logout/fresh session -> confirm
standalone Sign-in -> sign in -> confirm the centered Gateway with no
left panel -> open a Project -> confirm the full workspace and Lists
panel -> return to Gateway -> confirm the workspace shell and Project-
specific content disappear -> logout -> confirm return to Sign-in),
including wide and narrow viewports, during the continued walkthrough.

**MANIFEST.md**: updated entries for `routes/portal.py`,
`templates/index.html`, `templates/login.html` (also corrected a pre-
existing drift found while here: it extends `auth_shell.html`, not
`base.html` - stale since CLAUDE-P40-D1, not introduced by VW5), and
`templates/gateway.html`; added a row for the new `gateway_shell.html`.

**STATIC_VERSION correction**: `.env` (untracked) was bumped 32->33
for this stage's `main.css` changes (`.gateway-shell`, `.gateway-card-
wide`) - the VW5 implementation commit's own message incorrectly
claimed no bump was needed; caught and corrected in this same session,
recorded honestly here rather than silently amended.

Preserves the completed VW1-VW4 corrections (re-confirmed by this
stage's own tests inside a real Project workspace), authentication/
authorization/CSRF/safe-redirect behaviour, project ownership/allow-
list enforcement, existing Project-creation/operating-environment
locks, and all real Project/Document/Investigation/RFI/conversation
data - none were touched. P40-E3B remains closed as DEFER; the
conversation Tasks/Tags work and P41 were not started.

## 2026-08-02 — CLAUDE-P40-VW4: independent Vertical/Horizontal Display division controls

**Commit:** `0919b54`. Full suite: 1613 passed, 0 failed (was 1568; 45
new). Starting state was `34143c2` (the P40-VW3 checkpoint) - HEAD and
`origin/main` verified equal, tree clean except the pre-existing
untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. **No
product-owner acceptance seal recorded** - explicitly not requested
this stage; the result remains subject to the next walkthrough.

**Product-owner walkthrough correction**: the Display Layout panel
treated Vertical and Horizontal as an either/or choice sharing one
quantity. Replaced with two fully independent numbers - Vertical
divisions (side-by-side columns) and Horizontal divisions (stacked
rows), both permanently visible simultaneously - resulting Display
count is their PRODUCT, capped at the existing ceiling of 6 (14 valid
combinations).

**Existing model examined before changing it**: a single `quantity`
(1-6) + `orientation` pair, persisted as `{quantity, orientation}` in
localStorage, driving a static `[data-orientation][data-count]` CSS
attribute-selector table. Extended (not replaced) the same mechanism:
`vertical`/`horizontal` are the new source-of-truth numbers;
`quantity` is now a derived value (`vertical * horizontal`), so the
existing six-Display show/hide table and active-target bounds logic
are unchanged. Since 14 V×H≤6 combinations can't be enumerated as
static attribute selectors the way the single-axis version was,
`grid-template-columns`/`rows` now read `--display-v`/`--display-h`
custom properties set inline by `applyLayout` per Apply.

**Compatibility mapping** (this stage's own required rule, in
`normalizeStoredLayout`): a stored `{quantity, orientation}` shape
maps quantity 1 (either orientation) to Vertical 1/Horizontal 1; a
"vertical" quantity N to Vertical N/Horizontal 1; a "horizontal"
quantity N to Vertical 1/Horizontal N. The new `{vertical, horizontal}`
shape passes through unchanged (idempotent).

**Interaction**: both steppers fully independent; minimum 1 each; the
relevant increment button disabled (not silently refused) the moment
applying it would exceed 6, with a static "Maximum 6 Displays total"
note in both menus; Apply commits both values atomically; closing/
reopening either menu without Apply reseeds the pending display from
the actually-applied state. "Close this Display" shrinks whichever
axis is currently larger by one - the smallest reduction that still
yields a full, never-ragged rectangle (a true grid can't shrink by
exactly one cell).

**Divider mechanism replaced**: the old per-orientation border-swap
didn't generalize to two axes - a 1px `gap` the same color as
`--border`, with each division painting its own `--surface-primary`
over it, gives a real hairline on both axes at once, using only
existing tokens (VW3 appearance-mode compatible - verified no
hardcoded hex in any touched rule).

**Test-infrastructure note**: updated 4 pre-existing test files whose
assertions were tied to the retired single-axis model - not weakened,
same coverage against the new, deliberately different mechanism.

**Tests**: added `tests/test_p40vw4_independent_display_axes.py` (45
tests) covering default state, independent axis wiring, minimum/
ceiling enforcement, Apply-gating and dismiss-without-apply reseeding,
2x3/3x2 arrangement semantics, right-click vs top-bar mechanism
parity, legacy-state compatibility, Stable URL Restoration and
active-target/projection preservation, VW3 appearance-token
compliance, and keyboard/focus. Confirmed load-bearing by reverting
all four changed source files and observing 32/45 fail, then restoring
them. Directly affected suites re-run explicitly - all passing. Full
suite run to termination: 1613 passed, 0 failed.

**Browser evidence and its limitation, stated honestly**: no browser-
automation tool was actually connected in this session (checked
directly - `ToolSearch` for claude-in-chrome/MCP browser tools
returned nothing), consistent with every prior VW stage. A throwaway
local admin account was seeded directly into the dev SQLite DB in
anticipation of live verification, found unusable once the tool's
absence was confirmed, and removed again rather than left behind.
Verification rests entirely on structural HTML/CSS/JS source
assertions. **The product owner should confirm the controls visually
and functionally in a real browser, including the illustrated 2x3/3x2
arrangements**, during the continued walkthrough.

Preserves layout/panel ownership, VW1's context-menu correction, VW2's
relocated Project Tools, VW3's appearance matrix, active-target
routing, document projection, project isolation/authorization, and
project/document data - none were touched. P40-E3B remains closed as
DEFER; the conversation Tasks/Tags work and P41 were not started.

## 2026-08-02 — CLAUDE-P40-VW3: per-surface Light/Dark/Tinted appearance matrix

**Commit:** `e4b241d`. Full suite: 1568 passed, 0 failed (was 1544; 24
new). Starting state was `076683c` (the P40-VW2 checkpoint) - HEAD and
`origin/main` verified equal, tree clean except the pre-existing
untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Product-owner walkthrough correction**: the Appearance menu offered
one checkbox per surface (Lists/Display/Toolbox/Chat) - a binary
plain-vs-tinted choice - and the top Menu bar was not configurable at
all. Replaced with a real matrix: five surfaces (Menu, Lists, Display,
Toolbox, Chat) x three mutually exclusive modes (Light, Dark, Tinted),
real `<input type=radio>` groups (one per row, not checkboxes), rows
ordered Menu/Lists/Display/Toolbox/Chat to match the page's own visual
hierarchy.

**Previous appearance-state model**: one localStorage key per surface
(`beehive:appearance:{lists,display,toolbox,chat}`), value `'tinted'`
or `'plain'`/absent. **Compatibility mapping** (honest, lossless):
`'tinted'` carries over unchanged; `'plain'` or missing maps to
`'light'`, the new default, which renders identically to the old plain
state - no reviewer's prior choice is reinterpreted as something they
didn't pick. Menu has no prior key and defaults to `'light'`, matching
its previous unconfigurable appearance.

**Dark mode, new this stage**: `static/css/tokens.css` gained a
`--dark-*` token set (same hue family as the light palette, lightness
inverted - not an unrelated palette), contrast-verified against every
one of `tools/check_contrast.py`'s own required pairings (all pass).
`static/css/main.css` gained one shared `.appearance-dark` rule that
REDEFINES the standard token names locally on whichever surface's own
root carries that class - every existing component rule already
written as `var(--surface-primary)`/`var(--text-primary)`/etc.
throughout the file repaints correctly for free. Scoped CSS custom
properties (not a second linked stylesheet, which could only ever
apply page-wide) were required because the five surfaces must mix
independently (e.g. Dark Display with Light Lists and Tinted Toolbox) -
the five surfaces are DOM siblings, so this cannot cross-contaminate.

**Test-infrastructure note**: fixed two pre-existing tests in
`test_p40e2b_flexible_workspace_frame.py` whose own `_rule_body` helper
does a plain "first rule containing this selector as a token" search -
the new shared compound-selector rule legitimately matched that
definition earlier in the file than the real base rule it meant to
find. Fixed by relocating the shared rule to after all five surfaces'
own base rules (not by modifying the helper or weakening any
assertion) - restores its intended semantics for all five surfaces,
not just the two the existing suite happened to exercise.

**Tests**: added `tests/test_p40vw3_appearance_matrix.py` (24 tests) -
matrix structure (5x3, unique radio groups, no leftover checkboxes,
row order, accessible labels), preservation (menu still workspace-
gated, Menu's target element renders everywhere), dark-token CSS
(defined, scoped to `.appearance-dark` not `:root`, contrast-verified
by actually invoking `tools/check_contrast.py` as a subprocess against
a scratch tokens file), and JS wiring (all five targets, compatibility
mapping, independent per-surface persistence). Confirmed load-bearing
by reverting the three changed files and observing 22/24 new tests
fail, then restoring them. Directly affected suites re-run explicitly
(Display-layout, Stable URL Restoration, VW1 context-menu, VW2
relocation, flexible-frame, global search/header, visual-deboxing) -
all passing. Full suite run to termination: 1568 passed, 0 failed
(unusually long wall-clock time this run - ~33 minutes - noted per
CLAUDE.md's own "treat pass/fail as the signal, not wall-clock time"
guidance, not investigated further as unrelated to this change).

**Browser evidence and its limitation, stated honestly**: no browser/
pointer tool exists in this environment. Verification rests on
structural HTML/CSS/JS source assertions and a real, non-simulated
invocation of the repository's own contrast-checking tool - not a real
click or a visual comparison of any mixed-mode combination. **The
product owner should confirm representative mixed-mode combinations
(e.g. Dark Display with Light Lists and Tinted Toolbox) with a real
look during the continued walkthrough**, including that document
viewers embedded via `<iframe>` (PDF/Office rendering) cannot be
dark-mode-styled from this application's own CSS - an honest, inherent
limitation of embedding third-party document rendering, not a gap in
this stage's own work.

Preserves layout/panel ownership, VW1's context-menu correction, VW2's
relocated Project Tools, Display-splitting behaviour, persistence
schemas, authorization, and project/document data - none were touched.
P40-E3B remains closed as DEFER; P41 was not started.

## 2026-08-02 — CLAUDE-P40-VW2: relocated project-level controls from Toolbox to Lists

**Commit:** `17cbdaa`. Full suite: 1544 passed, 0 failed (was 1522; 22
net new). Starting state was `5468c0b` (the P40-VW1 checkpoint) - HEAD
and `origin/main` verified equal, tree clean except the pre-existing
untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Product-owner walkthrough correction**: the right Toolbox's no-
selection state showed a project-level panel - explanatory text,
Remove Project, the three Add-a-Source forms, Removed Items, admin-
only Project Data Management. This belonged in the left Lists panel's
active-Project hierarchy, not the contextual right Toolbox (which is
meant to hold only Document/Investigation-specific tools).

**Root ownership, diagnosed before moving any markup**: these controls
lived entirely inside `case_workspace.html`'s `{% block toolbox %}`
no-selection branch, filled into the `<aside id="workspace-toolbox-
panel">` `base.html`'s shell always owns.

**Relocation**: the exact same markup (forms, routes, CSRF via the
app-wide auto-injection, `confirm=yes` gates, owner/admin
authorization `{% if %}`s, `macros.subdisclosure` calls, unique ids)
moved wholesale into `base.html`'s own Lists panel, as a new "Project
Tools" branch sibling to Overview/Documents/Investigations/RFIs/Chats
inside the active Project's tree - collapsed by default, using the
same existing tree-toggle hover/pin/collapse mechanism as every
sibling branch, not a second navigation tree or column. `base.html`
gained its own `{% import "_macros.html" as macros %}` (a child
template's own import does not propagate to the parent's directly-
written markup). No route in `routes/workspace.py` was touched - a
pure template-layer relocation. Toolbox's no-selection branch is now a
concise neutral empty state only.

**Test-change note**: three pre-existing tests (in
`test_p40e2_toolbox_and_removal.py`, `test_p40e2b1_single_launcher_and_
directories.py`, `test_p40e3a_qa_reconciliation.py`) asserted these
controls were entirely absent from the whole page body outside the
no-selection state - a premise this relocation deliberately supersedes
(Lists' Project Tools branch, like its Documents/Investigations
siblings, is always part of the rendered hierarchy, just collapsed).
Rescoped to check the Toolbox region specifically
(`workspace-toolbox-panel`), which is what they actually meant to
verify; nothing was weakened.

**Tests**: added `tests/test_p40vw2_project_tools_relocation.py` (21
tests) - relocation ownership, absence from Toolbox in every state, no
duplication/unique ids, owner/admin-vs-granted-reviewer authorization,
intact Document/Investigation contextual Toolbox content, and
end-to-end functional proof (add document, add text record, remove +
restore document, remove project) through the relocated forms against
the unchanged routes. Confirmed load-bearing by reverting the template
changes locally and observing the new tests fail, then restoring them.
Directly affected suites re-run explicitly (Display-layout, Stable URL
Restoration, VW1 context-menu, Toolbox/removal, project home,
containment/restoration) - all passing. Full suite run to termination:
1544 passed, 0 failed.

**Browser evidence and its limitation, stated honestly**: no browser/
pointer tool exists in this environment. Verification rests on
structural HTML assertions (region scoping, id/action counts,
authorization-gated presence/absence) and end-to-end route-level
functional proof, not a real click. **The product owner should confirm
the visual placement and collapse/expand feel of the new Project Tools
branch with a real look during the continued walkthrough.**

Preserves the recursive Project hierarchy, collapse/pin behaviour,
active Project indication, Display geometry, Chat dock, stable URLs,
authorization filtering, project/document data, and the VW1 context-
menu correction - none were touched. P40-E3B remains closed as DEFER;
P41 was not started.

## 2026-08-02 — CLAUDE-P40-VW1: fixed the permanently-visible Display context menu

**Commit:** `7b83e82`. Full suite: 1522 passed, 0 failed (was 1507; 15
new tests added, none removed). Starting state was `510c4ef` (the
P40-E3B-DEFER-CLOSE seal) - HEAD and `origin/main` verified equal, tree
clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Product-owner walkthrough defect, first observation of the visual
walkthrough session**: the per-Display right-click menu
(`#display-context-menu` - Close/Divide/direction/quantity/Apply) was
permanently visible near the upper-left corner of a blank main Display
instead of hidden until a real right-click, and right-clicking a
Display did not visibly open it at the pointer.

**Root cause, confirmed by direct CSS/JS source inspection (not
assumed to be "just CSS" without checking)**: `static/css/main.css`'s
`.display-context-menu` rule sets `display: flex` via a plain class
selector - the same specificity (0,1,0) as the browser's own
user-agent-stylesheet rule `[hidden] { display: none }`. An
author-origin CSS rule always wins over a user-agent-origin rule at
equal specificity regardless of source order, so the JS-toggled
`hidden` attribute was being silently defeated on every render,
including the very first one. `static/js/case_workspace.js`'s
`setUpContextMenu` (open/close/target/Escape/outside-click/Apply-Close
dismissal, viewport clamping) was already correct and complete and
needed no change - this was not a JS bug. The top-bar Display
Layout/Appearance/User menus never hit this because they are native
`<details>`/`<summary>` disclosure widgets, an unrelated, unaffected
visibility mechanism.

**Fix** (one CSS rule, no JS/template/schema change): added
`.display-context-menu[hidden] { display: none; }` (specificity
0,2,0), which reliably overrides the base rule regardless of source
order. Verified load-bearing by reverting it locally (`git stash`),
observing the new test fail, then restoring it. `STATIC_VERSION`
bumped 29→30 (`.env`, untracked, per this repo's own CSS-change
discipline).

**Tests**: added `tests/test_p40vw1_display_context_menu.py` (15
tests) - the menu's `hidden` attribute survives initial and repeat
fresh renders on both a blank and a populated Display; the CSS
override rule exists without removing the open-state flex layout; the
existing JS wiring (per-division-scoped listener, native-menu
suppression scope, pointer targeting, `hidden` toggling, outside-click/
Escape/Apply/Close dismissal, untouched top-bar control) is asserted
intact. Directly affected suites re-run explicitly
(`test_p40e3a_layout_reconciliation.py`,
`test_p40e3a_qa_reconciliation.py`,
`test_p40e2b1a_recursive_projection.py` including the Stable URL
Restoration test) - all passing. Full suite run to termination: 1522
passed, 0 failed.

**Browser evidence and its limitation, stated honestly**: no browser/
pointer-interaction tool exists in this environment. Diagnosis and
verification rest on direct CSS-cascade-specificity reasoning (a well-
defined, deterministic browser behavior, not a guess) plus source-level
JS assertions; the actual visual result (menu now hidden, opens at the
pointer, targets the right division, stays clamped, dismisses
correctly) has NOT been confirmed by a real click in a real browser.
**The product owner should verify this correction with a real
right-click during the continued walkthrough.**

Preserves every existing Display-layout contract (orientation,
quantity, six-division ceiling, close/reflow, active-target routing,
document projection), the Stable URL Restoration guarantee, and all
navigation/Lists/Toolbox/Chat/persistence/authorization boundaries -
none were touched. P40-E3B remains closed as DEFER; P41 was not
started.

## 2026-08-02 — CLAUDE-P40-E3B-DEFER-CLOSE: evidence-backed Defer decision accepted

**Seal commit:** (this checkpoint commit itself). Starting state was
`a0c0552` (P40-E3A-F1-QA-CLOSE's own checkpoint commit) - HEAD and
`origin/main` verified equal before recording this seal; working tree
clean except the pre-existing, unrelated untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Last independently
verified full suite: **1507 passed, 0 failed** (unchanged - no code
changed since that run).

**The product owner accepts the P40-E3B conclusion: DEFER.** P40-E3B
performed repository-grounded scope derivation - reconciling this
checkpoint, the full P40-E3A/E3A-QA/F1 commit history, `governance/
STATUS.md`, and the current templates/CSS/JS/routes/tests - and found
no genuine, safe, marketable increment available within its own
boundaries. **No E3B implementation occurred.**

- Shell relocation and navigation, the left-panel recursive hierarchy,
  and dynamic Multi-Display state/projection were already delivered by
  P40-E3A and conditionally accepted (P40-E3A-QA-CLOSE, `1c56999`).
- Drawing/annotation, governed chat tagging and assumption correction,
  and cross-project intelligence/later integrations remain separately
  authorization-dependent (per `governance/STATUS.md`'s application-wide
  freeze default and `governance/specified-unbuilt/`) and were not
  started.
- The rendered-detail differences from the numbered prototype remain
  reserved for a future product-owner visual walkthrough - not
  attempted from prose in this stage, per P40-E3B's own scope boundary.

No application code, test, template, CSS, JavaScript, schema, or
project/document data was changed to reach or record this decision.
`MANIFEST.md` was not updated - nothing in it went stale, since no
tracked file it catalogues was touched. **The next productive activity
is the deferred visual walkthrough with the product owner.** P40-E3B is
now closed as DEFER; P41 was not started.

## 2026-08-02 — CLAUDE-P40-E3A-F1-QA-CLOSE: Stable URL Restoration flake closed

**Seal commit:** (this checkpoint commit itself). Starting state was
`e67e048` (P40-E3A-F1's own checkpoint commit) - HEAD and `origin/main`
verified equal before recording this seal; working tree clean except
the pre-existing, unrelated untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**The product owner accepts the P40-E3A-F1 correction**, on the basis
of an independent review (fresh reviewer context, no prior involvement
in the fix) that classified it ACCEPT: read the actual installed
`flask_wtf`/`itsdangerous` source and independently reproduced the
timestamped-re-signing mechanism live; proved the companion CSRF-
secret-stability assertion load-bearing by a reversible local break
(then fully reverted, confirmed via empty `git diff`); confirmed the
diff touches exactly `tests/test_p40e2b1a_recursive_projection.py` and
`CONTINUATION_CHECKPOINT.md`, nothing else; ran the targeted test (17
passed) and the full suite independently twice (1507 passed, 0 failed,
both times). No material concern remained.

**This seal closes one specific, narrow item - it does not re-open or
broaden anything else already recorded:**

- The Stable URL Restoration flake itself (`StableUrlRestorationTests::
  test_navigating_away_and_back_via_fresh_requests_restores_identical_state`)
  is now closed - root-caused, fixed, and independently verified.
- P40-E3A and P40-E3A-QA remain conditionally accepted exactly as
  previously recorded (P40-E3A-QA-CLOSE, `1c56999`) - this seal does
  not upgrade that to unconditional acceptance.
- The rendered-detail differences from the independently developed
  numbered prototype, recorded in that same P40-E3A-QA-CLOSE entry,
  remain deferred to a future visual-reconciliation round - untouched
  by this seal.
- The E3A test-change audit's category counts remain recorded as
  approximate (~89-135, methodology gap already documented) - this
  seal does not attempt to make them exact.

No application code, test, template, CSS, JavaScript, schema, or
project/document data was changed to record this seal.
`MANIFEST.md` was not updated - it does not catalogue individual
`tests/*.py` files (its own stated scope) or continuation-checkpoint
content, so nothing in it was stale as a result of this seal; no new
documentation convention was introduced. P40-E3B and P41 remain not
started.

## 2026-08-02 — CLAUDE-P40-E3A-F1: StableUrlRestoration flake root-caused and fixed

**Commit:** `97e51f9`. Full suite: 1507 passed (unchanged count - test-only
fix, no new tests added, one existing test corrected). Starting state
was `1c56999` (the P40-E3A-QA-CLOSE conditional acceptance seal).

Independently investigated the flake recorded as a residual in the
P40-E3A-QA-CLOSE seal:
`StableUrlRestorationTests::test_navigating_away_and_back_via_fresh_requests_restores_identical_state`
(2 of 5 full-suite runs, always passed isolated). Ruled out an
import-order/module-side-effect cause (running with every test module
imported but only this one executed passed 3/3). A fast, isolated
400-iteration reproduction script (session-scratchpad, not committed)
reproduced the failure 3 times in under 2 minutes and captured real
diffs each time.

**Root cause, confirmed by direct evidence**: all 3 captured mismatches
differed in exactly one place - the `<meta name="csrf-token">` tag,
and only in its timestamp/signature segment (the encoded secret before
the first "." was byte-identical every time). Flask-WTF's
`generate_csrf()` re-signs the session's stable CSRF secret with a
fresh `itsdangerous` timestamp on every call, by design - it does not
cache the fully-signed string across requests. Two requests landing in
different wall-clock seconds get a different signed token even though
nothing about session or page state changed; full-suite-scale GC/IO
pressure occasionally widens the gap between the test's two requests
enough to cross a second boundary. **This is expected, correct CSRF
behavior, not a product defect** - a pure test-correctness defect in
this one test's own prior (and, per that test's own comment, explicitly
asserted but wrong) assumption that the raw HTTP body would be
byte-stable across two different requests.

**Repair** (one test file, no application code): the CSRF meta tag is
normalized to a placeholder before the strict body comparison; a
companion assertion now checks the CSRF *secret* segment itself stays
identical across the two requests - real regression coverage in its
own right (unexpected per-request CSRF-identity rotation would be a
genuine security regression). No retries/sleeps/skips/weakened
assertions/forced ordering used. Verified: the same 400-iteration
reproduction with the fix applied - 0 mismatches (was 3). Confirmed via
grep this exposure was unique to this one test; nothing else in the
suite does a full-body equality comparison across two separate page
renders.

Preserves the P40-E3A-QA-CLOSE seal, the accepted layout, all
authorization/persistence boundaries, and every real record - no
template/CSS/JS/schema/governance file touched. P40-E3B and P41 not
started.

## 2026-08-02 — CLAUDE-P40-E3A-QA-CLOSE: conditional acceptance seal

**Seal commit:** (this checkpoint commit itself). Starting state was
`a31f863` (P40-E3A-QA's own checkpoint commit) - HEAD and `origin/main`
verified equal before recording this seal; working tree clean except
the pre-existing, unrelated untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Last verified full
suite: **1507 passed, 0 failed**.

**The product owner conditionally accepts P40-E3A and P40-E3A-QA as
the current working layout baseline.** This is explicitly not a
declaration that the interface is 100% complete - the following
residuals are recorded honestly, not fixed here, per this seal's own
instruction not to change application code or weaken tests:

- Some rendered details still differ from the independently developed
  numbered prototype - further visual reconciliation is deferred to a
  fresh future round, not considered closed by this seal.
- The intermittent `StableUrlRestorationTests::
  test_navigating_away_and_back_via_fresh_requests_restores_identical_state`
  flake (documented in the P40-E3A-QA entry above: failed 2 of 5
  full-suite runs that day, always passed isolated or in a partial
  replay of the same prior order, test body unchanged since before
  P40-E3A) remains unresolved.
- The E3A test-change audit (forked, independent read of the real
  diff) did not produce exact counts for every requested category -
  it reported a range (~89-135, methodology gap explained in its own
  findings) rather than one precise number per bucket.

No application code was changed to reach this seal; no test was
weakened. P40-E3B and P41 remain not started.

## 2026-08-02 — CLAUDE-P40-E3A-QA: browser-grounded layout reconciliation

**Commit:** `2eb23b4`. Full suite: 1507 passed (was 1491). Not yet
product-owner accepted. Starting state was `ee271e6` (P40-E3A's own
checkpoint commit).

Product owner opened the real application in a real browser for the
first time this stage and **approved the four-zone chassis direction**
(top bar / recursive Lists / Display+Toolbox / full-width Chat) - but
flagged concrete gaps between P40-E3A's implementation and the
reviewed prototype. Every flag traced to a real, confirmed repository
cause, not a cosmetic guess:

- RFIs branch disappearing at zero drafts - the only one of four
  sibling branches gated on non-empty content; made unconditional.
- Chat "visually heavy": two simultaneous Compact/Expanded buttons
  replaced by one state-naming toggle; retired "planned, not available
  yet" disclosure line removed (Section 13 already documents that
  scope, a runtime repeat was clutter); empty-history state now
  centers instead of leaving a bare gap; **three** stacked divider
  lines above the resize handle found and reduced to one (this
  stage's own new `.chat-region` border duplicated the handle's
  already-documented divider, and `.conversation-dock-panel` was never
  exempted from the generic `.accordion-section` border every other
  caller already is).
- Toolbox "visually heavy... project-level controls" bleeding into
  contextual views - Add a Document/Removed Items/Project Data
  Management used to render unconditionally below whatever was
  selected; scoped to the no-selection state only.
- "Beige/default tinted surfaces" - `.workspace-pane-toolbox` never
  got a default background in this stage's own earlier rewrite,
  letting the page's warm `--canvas` bleed straight through; now
  matches Lists/Display's own plain `--surface-primary` default.
- Context-menu position now clamps to the viewport; `.panel-divider`
  given an explicit low z-index so it can never paint above an
  overlay.

Independently audited (forked, read the real `git diff`, not the
implementer's own prior self-report) the ~135 pre-existing test
changes from the P40-E3A commit against a 5-bucket classification: no
weakened authorization/persistence/provenance/privacy/legacy-
compatibility invariant found. Top bar and the six-division ceiling
(explicitly verified, not reconsidered, per this stage's own
instruction) were already compliant.

3 pre-existing tests updated to reflect the corrections above; 16 new
focused tests added (`tests/test_p40e3a_qa_reconciliation.py`). One
pre-existing, low-frequency flake noted honestly, not hidden or
silently patched: `StableUrlRestorationTests::
test_navigating_away_and_back_via_fresh_requests_restores_identical_state`
failed in 2 of 5 full-suite runs today, always passed in isolation or
a partial run replaying the same prior order; its own test body is
unchanged since before P40-E3A - a pre-existing, environment-scale
flake, not a regression from this stage, left as-is rather than
weakened.

No real browser/screenshot tool exists in this environment - fixes
came from direct code inspection against the product owner's specific
observations, verified structurally (CSS/JS source assertions,
server-rendered HTML), not a rendered window. STATIC_VERSION 28 -> 29
(`main.css`, `case_workspace.js`, `_macros.html` all changed);
dev-server chain restarted and reverified serving it. P40-E3B and P41
not started.

## 2026-08-01 — CLAUDE-P40-E3A: numbered prototype layout transfer and interface reconciliation

**Commit:** `484a171`. Full suite: 1491 passed (was 1465). Not yet
product-owner accepted. Starting state was `b34d420` (P40-E2B1A's own
checkpoint commit).

Product owner explicitly resolved the P40-E2B1A conflict in favour of a
newer numbered layout prototype (a live reference this agent could not
actually access - no URL was ever supplied, stated honestly rather than
pretending to have inspected it; implementation worked from the
prompt's own detailed written layout contract instead): **P40-E2B1's
pure-root-launcher rule and P40-E2B1A's audit against it are both
superseded, deliberately, not by accident.** One physical Lists panel
now holds a real recursive hierarchy - hover reveals temporarily, click
pins/collapses, collapsing an active branch clears Display, a leaf
projects into Display and clicking it again clears Display. Display
never re-lists what Lists already lists: the P40-E2B1/E2B1A-era
`?view=documents/investigations/chats` directory bodies and
`.display-branch-nav` are removed outright, replaced by one
consolidated "Overview" leaf (what P40-E2B called Project Home). This
is a real, flagged behavior change from P40-E2B's own invariant that
that material stayed visible even while an Investigation was open -
Overview and an open Investigation are now mutually exclusive leaves,
per this stage's own leaf-exclusivity rule.

Shell rework: `base.html` now owns the full-width top bar (brand/
breadcrumb/Display-layout menu/Appearance menu/user three-dot menu),
the Lists hierarchy, and - gated on both `project_id` and `workspace`
being defined, not bare `authenticated` - the Toolbox/Chat block
containers, so neither leaks empty reserved width/a phantom sticky
chat bar onto the dashboard, Security, or other non-Workspace pages.
Lists | Display | Toolbox are flex siblings; Chat is a full-width
sticky row beneath. The old `.case-workspace` named-grid-area layout is
retired for flex specifically so "closing a Display expands the rest"
and "collapsing Toolbox releases space to Display" are free
consequences of `flex:1`/`display:none`, not something needing a
grid-template rewrite per state.

Display: 6 total divisions (0 always real-navigation-bound; 1-5
client-side slots - `MAX_DISPLAY_DIVISIONS`), a genuine dynamic
orientation+quantity+Apply control replacing the old fixed single/
side-by-side/stacked/grid presets, one active-target division routing
the next Lists Document click via a new `window.ArchioskDisplay`
bridge, and a per-division right-click context menu (Close/Divide/
direction/quantity/Apply only). Multi-Display geometry is reviewer/
device presentation state only (localStorage/sessionStorage) - never a
Project/Document/authorization/evidence/governance-log write.

Test reconciliation (delegated to a forked agent, reviewed before
commit) surfaced real bugs beyond stale assertions, all fixed: every
bare Project-level POST redirect in `routes/workspace.py` now passes
`view=overview` so a completed action is actually visible instead of
landing on the new blank default; `case_workspace.html`'s Toolbox/Chat
blocks recompute `drawing_sources` locally (Jinja blocks don't inherit
a sibling block's `{% set %}`); New Project gated on `is_admin`
(`portal.upload` is `@admin_required`); the Projects heading now
highlights on the directory page itself, not only inside an open
Workspace. ~135 pre-existing tests updated to assert the new,
authorized behavior; new `tests/test_p40e3a_layout_reconciliation.py`
covers this stage's own contract. No conflict found with the
preservation list (P32 authorization, auth-page isolation, legacy-
record compatibility, Reset/Restore safety, RFI authorization/
directionality, GET-never-mutates-beyond-`last_viewed_by`) or the
exclusion list (archive, lessons learned, cross-Project refs,
SharePoint, autosave, drawing/markup persistence, chat tags, ...).

No real browser/screenshot tool exists in this environment - geometry
was reasoned about (CSS Grid/flex spec behavior) and verified via
hermetic server-rendered-HTML tests, not a rendered window; stated
honestly rather than claimed. STATIC_VERSION 27 -> 28 (`main.css` and
`case_workspace.js` both changed); dev-server chain restarted and
reverified serving the new value. P40-E3B and P41 not started.

## 2026-08-01 — CLAUDE-P40-E2B1A: recursive projection conformance audit

**Commit:** `53bb458`. Full suite: 1465 passed (was 1448). Not yet
product-owner accepted. Starting state was `d64da5e` (P40-E2B1's own
commit).

Audited P40-E2B1 against an explicit interaction rule before touching
code: "the single left panel is a root launcher, not an expandable
navigation tree" - clicking a launcher with children projects them into
Display, recursively, never duplicated inline in the panel itself.
Found two real violations, despite the panel already being physically
one panel (physical single-panel compliance is not the same as semantic
root-launcher compliance):

- Project names were listed inline beneath "Projects" in the left panel
  (`base.html`'s `nav_recent_projects` loop).
- Documents/Investigations/Chats were listed inline beneath the active
  Project's own name in the left panel (`.launcher-project-context`).

Fix: the left panel now holds ONLY root launchers - Projects, New
Project, identity/Security/Sign out. Project names already had a
correct projection target (`portal.projects_list`, `/projects` -
unchanged). Documents/Investigations/Chats gained a new one: a
restrained inline link row at the top of Display's own division
(`.display-branch-nav` in `case_workspace.html`) - Overview/Documents/
Investigations/Chats, present in every per-project state, reusing the
exact same `?view=` URLs already built in P40-E2B1, no routing changes.
"Projects" in the panel now stays highlighted for the whole open
Project/Workspace subtree, not just the literal `/projects` path.

Recursive chain verified end-to-end via a fresh Flask test client:
Projects (root, `/projects`) -> a Project's own branch-nav (Display,
level 2) -> a directory's own children (level 3) -> a leaf's real
content in the active Display division (level 4, activating the shared
conversation dock where relevant).

Three pre-existing tests broke as a direct, correct consequence of the
fix - not because anything they actually test regressed. They were
incidentally relying on the OLD inline Project-name listing having been
present on every authenticated page (Home, `/security/`) as their only
source of that project name, not on their own stated subject
(corrupted-legacy-workspace resilience, P32 non-disclosure). Updated to
check each page's own real, correct content instead of that removed
side effect.

STATIC_VERSION 26 -> 27 (`main.css` changed). P40-E3 and P41 not
started.

## 2026-08-01 — CLAUDE-P40-E2B1: single launcher panel, Display-projected directories

**Commit:** `c0a125c`. Full suite: 1448 passed (was 1418). Not yet
product-owner accepted. Starting state was `4b57490` (the P40-E2B-QA-CLOSE
commit below - QA-close itself was never a separate checkpoint entry,
folded into this one since its own finding is what triggered this
stage).

Product correction, not a re-skin: the QA-close audit confirmed **two**
physical left panels rendered simultaneously on the Workspace page -
`base.html`'s app-wide side rail and `case_workspace.html`'s own
Workspace-local Lists panel (`.workspace-pane-lists`). This stage
eliminates the second column entirely, replacing both with **one**
restrained launcher panel.

- `base.html`: the side rail is gone. In its place, `.launcher-panel` -
  Projects (heading links to the authorized Project directory; names
  only beneath it, no per-project detail), New Project, and (only when
  a Project is open) that Project's own Documents/Investigations/Chats
  launchers, plus identity+Security+Sign out anchored at the bottom.
  "Pinned" is omitted outright - grepped the whole codebase, no backing
  implementation exists to fabricate a launcher for. The top bar
  (previously Workspace-page-local) moved here too, application-shell
  level, spanning Launcher/Display/Toolbox on every authenticated page,
  not just the Workspace - Display Layout/Toolbox toggle/document
  context stay gated to when a Workspace is actually open. Superseded
  Home/search/hamburger controls removed outright per spec, not hidden.
- `case_workspace.html`: `.workspace-pane-lists` is gone. Documents and
  Investigations become their own launcher-projected Display directories
  (`?view=documents`/`?view=investigations`/`?view=chats` on the SAME
  existing `show_workspace` GET route - no new routes, no client
  routing, exactly the `?source=`/`?case=` pattern already established).
  New Investigation creation moved into its own directory. Everything
  else previously in Lists (Operating Environment/Access/Settings/Needs
  Attention/Recent Focus/Investigation Quality/Participants/Go-No-Go/
  Accepted Knowledge/Instructions/Requirement Compliance/RFIs/
  Requirements/Key Dates/History) re-homed into Display's own Project
  Home view - a real regression was caught and fixed here during
  testing: this reference material was first gated on
  `not active_case and not directory_view`, which silently broke
  P40-E2B's own established, tested invariant ("Requirements/Sources/
  RFIs/Accepted Knowledge/History... a reviewer needs even while an
  Investigation is open" - `tests/test_workflow_integration.py`).
  Corrected to gate on `not directory_view` only, restoring that
  behavior exactly.
- `routes/workspace.py`: `?view=` resolution (a real `?case=`/`?source=`
  selection always wins over a bare directory view);
  `add_document_source`/`add_text_record_source` redirects now preserve
  `?view=documents` instead of dropping back to Project Home.
- `app.py`: `current_username` exposed via `inject_globals()` for the
  launcher's identity block.
- `main.css`/`case_workspace.js`: `.case-workspace` grid reduced from
  three columns (Lists/Display/Toolbox) to two (Display/Toolbox) - Chat
  still beneath Display only, Toolbox still spans both rows. The
  Launcher panel's own show/hide preference (`beehive:panel:launcher`)
  is reviewer-wide, not per-project like the old Lists toggle it
  replaces, since the panel itself is now global rather than
  Workspace-local.

Verified via rendered-DOM inspection (fresh Flask test client, real
GET requests, not just template compilation): exactly one top bar/
launcher panel/Toolbox/conversation dock/composer/Send/Display Layout
menu on every Workspace state (Project Home, all three directories, an
open Investigation), the top bar structurally precedes
`.app-shell-body` on every page (proving it genuinely spans above
Launcher+Main, not confined to one column), the launcher panel is
present with zero Toolbox/Chat/Display-Layout markup on non-Workspace
pages (Home, Projects list), and the old Lists panel is absent
everywhere. `auth_shell.html` (login/forgot-password/reset-password)
untouched - re-confirmed it still never extends `base.html`.

No browser/rendering tool exists in this environment - real `<details>`
keyboard operability, actual CSS Grid rendering, and pointer/keyboard
resize execution remain reasoned-not-proven, same honest limitation as
every prior stage.

STATIC_VERSION 25 -> 26 (`main.css`/`case_workspace.js` both changed).
P40-E3 and P41 not started.

## 2026-08-01 — CLAUDE-P40-E2B: flexible Workspace frame, resizable Chat, multi-display

**Commit:** `17ec86c`. Full suite: 1418 passed (was 1385). Not yet
product-owner accepted. Starting state was `82ec4d0` (P40-E2A2's own
acceptance seal).

Required wide geometry (top bar; Lists | Display | Toolbox; Lists |
Chat | Toolbox, Chat beneath Display only) built as a genuine
restructuring, not a re-skin:

**Section A** - a new Workspace-page-specific top bar
(`templates/case_workspace.html`) replaced the old conditional
`page_header` `<h1>` - identity/breadcrumb, Lists/Toolbox show-hide,
Display Layout menu, a contextual removed-Document badge, an overflow
menu. Deliberately excludes Home/search/Open Project/Project
Gateway/a second brand card - all already live in `base.html`'s
side-rail.

**Section B** - Lists (was folded into Display's own column under
P40-E specifically because it was *permanently* visible) is a real,
independently-collapsible column again - collapsibility resolves the
original complaint directly. Both Lists and Toolbox hide via a class
on `<html>` (never DOM removal - every form/draft/scroll position
inside survives), applied before first paint (same pattern as
`base.html`'s `nav-expanded`), reviewer-specific via localStorage,
never a `ProjectWorkspace` write.

**Section C** - the conversation dock is no longer a `<details>`/
accordion (which could collapse to nothing) - now an always-visible
panel beneath Display only (`grid-area: chat`, never spanning Lists/
Toolbox), resizable via a real ARIA separator (drag or
Arrow/Home/End when focused) or Compact/Expanded presets, clamped
120-640px, persisted per-reviewer via a `--chat-height` CSS custom
property.

**Section D** - Display Layout menu with four real layouts (Single/
Side by side/Stacked/Four-panel grid), each a genuinely different CSS
grid, never a decorative icon. Division 0 is always the server-
rendered active Investigation/Document/Project Home and the only
division Toolbox stays bound to (via the ordinary `?source=` query
string - the honest answer for a shared, server-rendered Toolbox).
Divisions 1-3 are client-side slots loading content through the SAME
authorized `workspace.source_file` route a normal `?source=` view
already uses - never a raw/guessed URL, never a removed or
cross-Project Source (`active_sources` only, resolved server-side into
a `file_url` a JS data island reads). Closing a division never touches
the underlying Source.

**Section E** - `.workspace-pane-display`/`.document-viewer-frame`/
`.document-viewer-image` no longer reference `--surface-secondary`
(Limestone/beige) or `border-radius` - a plain near-white surface,
matching a Document's own natural page background instead of clashing
with it.

**Section F** - re-verified by the full suite, not just asserted:
Project/Document removal, Toolbox controls, removed-state tombstones,
Reset/Restore/transaction recovery (`tests/test_p40e2a*.py` all green
unchanged), Findings-in-Toolbox, the one conversation dock,
Investigation navigation/terminology, `source_file`'s own 404 for a
foreign source_id, and P40-D2's no-structural-mutation-on-GET
invariant (re-tested against this stage's own new query-string/layout
surface area - only `last_viewed_by` changes, matching the
pre-existing, already-accepted invariant).

**Section G** - medium (`<=1080px`) stacks Lists/Toolbox to full-width
rows and collapses multi-division layouts to one column; narrow
(`<=640px`) turns Lists/Toolbox into real `position: fixed` overlay
drawers (same toggle buttons/classes, not a second mechanism),
closable via Escape.

38 new tests (`tests/test_p40e2b_flexible_workspace_frame.py`) covering
all 16 required points at the level actually provable without a real
browser (server-rendered HTML/attributes, real CSS/JS source text -
the same honest limitation this whole session has disclosed
throughout: no rendering/screenshot tool exists in this environment).
4 existing test files updated for two deliberate renames (the
`page_header` `<h1>` → top-bar breadcrumb, and `#conversation-dock` →
`.conversation-dock-panel` as the styled selector) - not regressions.

App restarted, `STATIC_VERSION` bumped to 24, verified serving.

---

## 2026-08-01 — CLAUDE-P40-E2A2: product-owner acceptance seal

**No code change - verification only.** The full P40-E2/P40-E2A/
P40-E2A1/P40-E2A2 line of work - contextual Toolbox, recoverable
Document/Project removal, removed-state route containment, Reset
Project Data, checksummed reset-snapshot restoration, the durable
transaction journal, and automatic crash recovery - is product-owner
accepted as of commit `83ece12` (checkpoint `5e99623`), 1,385 tests
passing. This closes the acceptance gap P40-E2A/E2A1 were explicitly
held back pending: Global Reset/Restore now has a proven, live-verified
automatic recovery path, not just an in-principle design.

---

## 2026-08-01 — CLAUDE-P40-E2A2: durable transaction journal, automatic crash recovery, final safety gate

**Commit:** `83ece12`. Full suite: 1385 passed (was 1365). Still not
product-owner accepted.

P40-E2A1 proved Reset/Restore work end-to-end but never built automatic
recovery from an interruption - a direct code search at the start of
this stage confirmed no journal, no PREPARED/LIVE_MOVED/etc. states,
and no automatic recovery existed anywhere in the repository. Built now:

**Journal (Section A).** `routes/portal.py`'s `_run_registry_transaction`
is the one journal-backed executor for both Reset and Restore -
PREPARED -> safety snapshot -> staged result built off to the side ->
LIVE_MOVED -> STAGED_INSTALLED -> re-verified against the checksums the
staged result was built to match -> VERIFIED -> old copy cleaned up.
Reset no longer wipes the live registry file-by-file in place (a real
gap - a crash mid-loop could have left a partially-wiped registry); it
now builds an empty result and swaps it in exactly like Restore always
did. The journal (`reset_transactions/`, a sibling of the registry,
untouched by either rename) carries no credentials or unvalidated
paths.

**Automatic recovery (Section B).** `_recover_interrupted_transactions`
runs at app boot (wired into `app.py`'s `create_app`, before any route
can read the registry) and at the top of every Reset/Restore admin
request. Ground truth is always what's actually on disk, not the
journal's last recorded state alone - completes forward if the staged
target verifies, rolls back to the pre-transaction copy (quarantining
a bad installed copy rather than deleting it) if it doesn't. A
transaction it can't resolve safely sets `REGISTRY_RECOVERY_FAILED`,
which a new app-wide `before_request` guard fails every request closed
against (except `/health` and static assets).

**Stale locks (Section C).** The lock file now records its owner's PID,
so recovery can tell a genuinely live process (never touched) from an
abandoned one (auto-recovered, lock cleared once terminal). Reset and
Restore share one lock, so they can never race each other.

**Two real bugs found and fixed by live verification, not just unit
tests (Sections D/F):**
1. `_checksums_for_dir`'s directory walk (`Path.rglob`) silently omits
   files past Windows' 260-char MAX_PATH from its results (unlike
   `shutil.copytree`/`os.rename`, which the E2A1 `_win_long_path` fix
   already covered) - a Restore's `expected_checksums` built from an
   already-nested snapshot path silently excluded a real file, and
   post-swap verification correctly (if confusingly) rejected the
   transaction. Fixed via a shared `_walk_root` helper.
2. An open file handle inside the registry blocks `os.rename()` of the
   containing directory on Windows (PermissionError) - POSIX has no
   such restriction. Fails safely (nothing touched yet) and recovers
   cleanly once released.

Both were caught by a real, separate isolated Flask process (its own
port, its own temporary registry/DB) driven over real HTTP: bug #1 hit
on the first live restore attempt; after each fix, the SAME process was
restarted (proving automatic recovery resolves the stuck transaction
with zero manual directory surgery) and re-driven through a clean
reset/restore cycle to `VERIFIED`/`cleanup_done=true`, with
byte-identical restored records confirmed via `diff`. The real
`instance/registry` (19 projects, a whole-tree fingerprint checked
before and after every stage of this session) was never touched -
confirmed by direct filesystem inspection, not assumed.

39 new/updated tests, including all 7 of Section E's required
interruption points for BOTH operations with the app literally
re-instantiated (`create_app()` called again) to simulate a process
restart, proving recovery runs automatically with no separate step.

---

## 2026-08-01 — CLAUDE-P40-E2A1: live isolated-process validation of Global Reset - found and fixed a real bug

**Commit:** `a3e6d3e`. Full suite: 1365 passed (was 1364). Still not
product-owner accepted - this stage exists specifically because P40-E2A
was held back pending exactly this kind of proof.

Per explicit instruction, Global Reset/Restore Snapshot was never
exercised against the real `instance/registry` - a completely separate
Flask process (own OS process, own port 5057, `REGISTRY_STORE_PATH`/
`DATABASE_URL` env vars pointed at a temporary isolated directory/SQLite
file, set before any project import) was launched instead, seeded with
one real Project/Investigation/Requirement via the real persistence
layer (`BHiveParser.parse` stubbed - the existing hermetic-test
convention, no live Anthropic API call), then driven entirely over real
HTTP with curl - real login, real CSRF tokens, real cookies.

**That live run immediately found a real bug the pytest suite's own
`tempfile.mkdtemp()` paths had never happened to trigger:**
`shutil.copytree` raised `[WinError 3] The system cannot find the path
specified` the instant a snapshot's own extra directory level
(`registry_snapshots/<stamp>/`) pushed an already-long
`workspace_sources/<project_id>/<hash>_<filename>` path past Windows'
classic 260-character MAX_PATH. Confirmed not an artifact of the
isolated environment's own path length - the same file's original,
un-nested path (one level shallower) had already copied and read back
fine at seed time; only the extra nesting a snapshot always adds
crossed the limit.

**Fixed** with a new `_win_long_path` helper in `routes/portal.py` -
the Windows-sanctioned `\\?\` extended-length prefix (no OS-level
`LongPathsEnabled` configuration required), applied at every
shutil/os call site in the snapshot-create/reset-wipe/restore-swap
path. A no-op on any other platform.

**Re-verified live, end-to-end, against the same isolated process
after the fix:** Reset succeeded (302), `/projects` showed a clean "No
projects yet." state, the snapshot listing showed correct kind/actor/
inventory, the restore preview showed "Verified" integrity with correct
current(0)/target(1) inventory, Restore succeeded (302), the restored
`.json`/`.workspace.json` files are **byte-identical** to the pre-reset
originals (`diff` produced no output), a `pre_restore_safety` snapshot
was taken automatically before the restore, the admin session/login
still worked post-restore, and `security_governance/reset_audit.jsonl`
shows one continuous audit trail across both events. The real
`instance/registry` (19 pre-existing projects, checked before and after
every step of this stage) and `instance/bhive.db` were never touched -
confirmed via direct filesystem inspection, not just inferred.

1 new deterministic regression test
(`test_reset_and_restore_succeed_past_windows_max_path` in
`tests/test_p40e2a_containment_and_restoration.py`) reproduces the same
>260-char condition inside the hermetic pytest suite itself, with
bounds computed from the test's own actual temp-directory length so it
stays meaningful regardless of where the OS places its temp folder -
this doesn't silently regress.

The isolated Flask process, its temporary registry/DB, and its scratch
directory were all torn down after verification - nothing from this
stage's live testing persists anywhere outside this checkpoint entry
and the commit itself.

---

## 2026-08-01 — CLAUDE-P40-E2A: removed-state route containment, reset-snapshot restoration

**Commit:** `c754bb5`. Full suite: 1364 passed (was 1339). Not yet
product-owner accepted - P40-E2 itself was explicitly held back from
acceptance pending this stage.

P40-E2's own review found two real acceptance gaps, both closed here:

**Gap 1 - removal only changed listing visibility.** An authorized
user (owner/admin, or anyone P32-accessible) could still reach a
removed Project's or Document's ordinary ACTIVE routes directly -
authorization and lifecycle are different checks, and P40-E2 only ever
checked the former. Fixed at `routes/workspace.py`'s
`_load_workspace_or_404`, the near-universal choke point every route
in that blueprint already passes through: a new `allow_removed=False`
default means an authorized caller reaching ANY route for a removed
Project is redirected to `show_workspace`, which now renders a
restrained "Project removed" tombstone (`templates/project_removed.html`
- display name, removed-at/-by, one Restore action) instead of the
active Workspace. Every child Document/Investigation route inherits
this automatically - chat, Investigation creation, document add,
findings review, all of it - with no per-route change; the only two
`allow_removed=True` exceptions are `show_workspace` itself and
`restore_project_route`. Unauthorized callers are unaffected (still the
pre-existing fail-closed 404, checked first). For a removed Document
specifically: the `?source=` viewer shows a "Document removed"
tombstone instead of embedding the file, `source_file` refuses to
serve it, `revise_source` refuses a new revision, and
`register_requirement`/`promote_requirement_item` refuse to target NEW
work at it - while an EXISTING Requirement/Finding that already cites
it keeps resolving the reference honestly (unchanged, by design).
`conversation_interpreter.py`'s drawing-Source detection now uses
`active_sources()`, so "Analyze this drawing" ignores a removed one.

**Gap 2 - Reset Project Data proved snapshot creation, never
restoration.** Every snapshot now carries a manifest
(`_snapshot_manifest.snapshot`, deliberately not `.json` - see that
constant's own comment on why) recording actor/time/kind/inventory and
a sha256 checksum of every file. New admin-only routes:
`/admin/reset-project-data/snapshots` (list, newest first) and
`.../snapshots/<id>/restore` (GET re-verifies integrity live and
previews current-vs-restored inventory; POST re-verifies again, takes
its own `pre_restore_safety` snapshot of whatever is CURRENTLY live
first, then swaps a staged rebuild into place via two `os.rename`
calls). `security_governance/` always comes from the CURRENT live
store during a restore, never the snapshot - accounts/security state
is never reverted to an old copy. Both this and Reset Project Data
share one `os.O_EXCL` lock file, so they can never race each other; a
stale lock shows its age rather than blocking silently forever.

**Atomicity, stated honestly, not oversold:** a flat-JSON-file
directory tree has no built-in multi-file transaction the way a
database does. The staged-build-then-two-atomic-renames pattern is
"safely recoverable" - each individual rename is atomic on the same
volume, and a failure while COPYING never touches the live store at
all - but a crash landing in the near-zero window between the two
renames would leave the live store path briefly missing. This residual
risk is not eliminated, only mitigated: the pre-restore safety snapshot
means the live state is never lost regardless; the lock file makes an
interrupted operation visibly "in progress" rather than silently
appearing to succeed; manual recovery from either snapshot is always a
plain filesystem copy. `_restore_snapshot`'s own docstring states this
exact limitation - this was judged sufficient to build rather than a
hard-stop, since it genuinely is "safely recoverable" in the sense
asked for, just not full ACID.

25 new tests (`tests/test_p40e2a_containment_and_restoration.py`)
against real tempfile-isolated filesystem stores - real
CaseWorkspaceStore/RequirementsRegistry reads/writes, real
`shutil.copytree`/`os.rename` during reset/restore, only
`BHiveParser.parse` stubbed (existing repo-wide convention) - covering
tombstone rendering/route-blocking for both removed Projects and
Documents, byte-identical restore, removed content absent from
search/AI-context, checksummed snapshot creation, corrupted-snapshot
restoration refusal, duplicate-submission lock sharing, no partial
registry left behind on a refused restore, and accounts/security-
governance survival through both reset and restore.

Explicitly NOT done, per this stage's own instruction: no removal or
reset/restore was ever run against the real `instance/registry/` data
in this session - every test above runs against a disposable
`tempfile.mkdtemp()` store. The product owner should not test Reset
Project Data against real records until this stage's restoration path
has been exercised and accepted first.

---

## 2026-07-31 — CLAUDE-P40-E2: contextual Toolbox, recoverable Document/Project removal, Reset Project Data

**Commit:** `7bcd250`. Full suite: 1339 passed (was 1311).

The permanent Findings-only right pane is now a persistent, contextual
Toolbox (`.workspace-pane-toolbox`, replacing `.workspace-pane-findings`
- the grid area/CSS class were renamed, not just restyled): Investigation
open shows Findings (moved in unchanged, still the same accordion);
Document selected shows Remove/Restore Document; nothing selected shows
restrained Project tools (Remove Project). Removed Items (this
Project's removed Documents, plus a link to Removed Projects) and an
admin-only Reset Project Data entry sit below, always visible. The
Toolbox always renders now (unlike the old Findings pane, which needed
`.case-workspace-single-column` to reclaim width when nothing was
open) - that class was removed as dead CSS.

Document/Project removal is recoverable, never a deletion:
`Source`/`ProjectWorkspace` gained `removed_at`/`removed_by`/
`removal_reason`; `CaseWorkspaceStore.remove_source`/`restore_source`/
`remove_project`/`restore_project` enforce owner-or-admin authority in
the store layer (same pattern as `grant_project_access`/`archive_case`).
`active_sources()` is the new filter for display/AI-context/search
reads of `workspace.sources`; a dependent reference (a Finding's own
citation) still resolves a removed Source directly via `_find`, so the
document viewer shows an honest "removed" state rather than breaking.
New routes (`remove_document_route`/`restore_document_route`/
`remove_project_route`/`restore_project_route`) reuse the
`confirm=yes/no` vocabulary `routes/portal.py`'s pre-existing, unrelated,
still-permanent `delete_project` already established (not the Approval
Gate's `confirm=once|session|no`) via new `confirm_remove_document.html`/
`confirm_remove_project.html`. `_accessible_documents` and `app.py`'s
`_nav_recent_projects` both now exclude removed projects from every
listing while leaving direct P32-authorized access untouched (the owner
can still reach a removed project's own workspace page to restore it,
via `/removed-projects`).

Reset Project Data (`/admin/reset-project-data`, admin-only) shows an
exact inventory (Projects/Documents/Investigations/Findings/
Requirements), requires typing an exact confirmation phrase, snapshots
the whole `REGISTRY_STORE_PATH` tree to a timestamped sibling
`registry_snapshots/<stamp>/` directory before wiping it (except
`security_governance/`, which holds auth-adjacent state - password
reset/rate-limit records - not project content), and is guarded against
duplicate submission by an `os.O_EXCL` lock file kept beside (not
inside) the store path. User accounts (`instance/bhive.db`), `.env`/
config, and schema version are never touched - the wipe only ever acts
inside `REGISTRY_STORE_PATH`. An audit line (actor/time/snapshot path/
removed entries) is appended to `security_governance/reset_audit.jsonl`,
the one subdirectory the wipe skips.

28 new tests (`tests/test_p40e2_toolbox_and_removal.py`) plus one
existing DOM-order test updated for the Findings->Toolbox rename.
STATIC_VERSION bumped to 23 (CSS grid-area rename, `main.css` changed).
App restarted via the `restart-app` skill and verified serving `v=23`.

Live-tested only against synthetic in-memory fixtures, never real
project records, per this stage's own explicit safety instruction -
Reset Project Data and Remove Project were deliberately not exercised
against the real `instance/registry/` store in this session.

---

## 2026-07-31 — CLAUDE-P40-E1A: product-owner acceptance seal

**No code change - verification only.** P40-E1A (one physical
conversation dock, Investigation listing, no Case terminology, and the
subsequent visual de-boxing pass) is product-owner accepted as of
commit `7d2a4f5`, 1,311 tests passing.

---

## 2026-07-31 — CLAUDE-P40-E1A-VISUAL-CLOSE: de-box decorative containers

**Commit:** `9e8fd66`. Full suite: 1311 passed (was 1291).

A "Visual De-boxing Addendum" was referenced as having been issued
separately - no record of it existed in this conversation or anywhere
in the repository, so it could not have been implemented yet.
Inspected the rendered Workspace's CSS, confirmed the decorative
containers it describes were still present, and implemented it now,
CSS-only (no template/class-name changes, no conversation/Investigation
persistence, authorization, or provenance touched):

`.workspace-pane` (wraps Project information, an open Investigation's
own content, Findings, an opened document, Project Briefing, Project
State) - was a filled/bordered/rounded card; now separated from
adjacent sections by a restrained bottom divider only. `.case-item`/
`.source-item` (Investigation/Source listing rows) - was a filled beige
(Limestone, `--surface-secondary`) card per row; now a plain divided
row, selected/active state kept as a real highlight.
`#conversation-dock` (the enclosing Conversation card) - the
box-shadow "lift" is gone, the `.accordion-section` top border it
already had is the only edge left; background kept (functional -
sticky-scroll legibility, not decoration). `.conversation-message` -
the filled beige bubble (human) and bordered card (system) are both
gone, distinguished now by indentation and the existing role-label
alone.

Deliberately untouched, per the addendum's own retention list: the
composer's own input border, real controls, focus states, selected
navigation rows, warnings, and consequential confirmations
(`.delegation-choice`/`.rfi-preview`/`.rfi-draft-card`, `.finding-card`
- discrete governed records/decision points, not ordinary messages).

20 new tests (`tests/test_p40e1a_visual_deboxing.py`) - text-level
checks against the real stylesheet (no browser/rendering tool exists
in this environment) confirming the named decorative properties are
gone and every explicitly-retained boundary is still there.

---

## 2026-07-31 — CLAUDE-P40-E1A: one physical conversation dock, Investigation listing, no Case terminology

**Commit:** `4c38cc6`. Full suite: 1291 passed (was 1275).

Real browser evidence (not caught by P40-E1's own tests) found the
dock was only partially unified: an open Investigation still rendered
its own accordion (`#conversation`), structurally separate from
Project Home's (`#project-conversation`) - different html_id,
different DOM position - so switching context still looked like a
different chatbox. Fixed by relocating both to one shared physical
position outside `.case-workspace`'s grid, through one macro
(`macros.conversation_dock`) with identical html_id/structure every
call. Draft and scroll-position keys are now scoped per conversation
context (`"project"` vs `"case-<id>"`, was a single shared project_id
key) - Section A's own explicit "preserve a separate draft... for each
conversation context."

Every authorized Investigation's own title (not just a count) now
lists under Work in the unified rail, sourced from the same P32/Case-
privacy-filtered `visible_cases` list the Workspace body already uses.
User-facing "Case" terminology (creation form, accordion title, and
roughly a dozen scattered strings) renamed to "Investigation" -
**the internal Case domain model, dataclass fields, route paths, and
`CaseWorkspaceStore` method names are all unchanged** - no
domain-model rename was performed, per this stage's own explicit
instruction not to risk one merely for display text.

**Correction to this checkpoint's own prior record:** the P40-E entry
below states conversation-thread lifecycle (Section F) and reviewer-
governed pattern suggestions (Section H) are "specified-but-unbuilt."
That remains accurate and unchanged by this stage - neither was
implemented here either. Restated explicitly because this stage's own
internal task tracking had marked the scoping *decision* as
"completed," which could be misread as the *feature* being complete;
it is not - see `governance/specified-unbuilt/conversation-thread-
lifecycle.md` and `reviewer-governed-pattern-suggestions.md`, both
still real, both still unbuilt.

30 new tests (`tests/test_p40e1a_single_dock_and_terminology.py`).

---

## 2026-07-31 — CLAUDE-P40-E1: exactly one conversation composer

**Commit:** `2fef98e`. Full suite: 1275 passed (was 1261).

P40-E's dock still left three composers competing on Project Home
("Ask about the project documents"/discuss_object, "Start or continue
project work"/quick_start, "Talk to this Project" inside the dock/also
discuss_object) - `_run_conversation_turn`'s own pre-existing docstring
already called all three "the same conversational entry point, reached
from three places," so collapsing them lost no capability. Removed the
first two composer forms entirely; the one remaining (in the dock)
posts to `quick_start`, which already classified a plain question from
a real "start work" request before this change. The Tools quick-links
(Add Document/Start Investigation/Open Source/Create Snapshot) stay as
the explicit-action alternative. Removed the "Separate from an
Investigation's own Conversation" explanatory line.

`macros.aperture` ("Discuss this Requirement") no longer renders its
own second, collapsed composer - now a button that attaches its anchor
to the one dock composer's hidden fields via a small JS handler and
focuses it; `quick_start` now accepts that optional anchor and always
routes to project-level conversation with it attached when present -
matching what `discuss_object` already did, so an anchored "Discuss
this" never accidentally spawns a new Investigation.

**Real gap found and fixed by this stage's own stricter tests:**
selecting a document (`?source=`) previously replaced the dock
entirely instead of coexisting with it - no composer at all in that
state. The document viewer now renders alongside Project Home (which
owns the dock), not instead of it.

14 new tests (`tests/test_p40e1_single_composer.py`). RFI delegation/
preview and Case-level conversation untouched - neither was ever a
duplicate composer.

---

## 2026-07-31 — CLAUDE-P40-E: unified document Workspace, conversation dock, hot-links

**Commits:** `328a778` (unified nav + Workspace layout), `e8ca197`
(conversation dock + hot-links), `58ef3d9` (specified-unbuilt docs +
tests). Full suite: 1261 passed (was 1242).

Transformed the Case Workspace's layout per product-design direction,
with an independent repository-grounded assessment first (per the
stage's own explicit instruction to challenge, not simulate).

**Eliminated the second, permanently-visible navigation column**
(`.workspace-pane-nav`, its own grid track running alongside the
active Case pane) - its useful entries now live as compact, counted
links in the unified left rail (`templates/base.html`), grouped
Project / Documents / Work / Decisions & Governance beneath the active
project's own row, only ever rendered for an authorized project. The
detailed content itself (Requirements/Sources/RFIs/Accepted Knowledge/
History) still renders unconditionally, confirmed necessary by an
already-existing test (`test_left_aside_always_visible_regardless_of_
case_selection`) - genuinely project-wide reference material a
reviewer needs while inside a Case, not dead weight. What changed is
placement: it now stacks in normal block flow (`.workspace-column`)
inside the same grid-area as the active Case pane or Project Home,
never a second column - which also retired the long-standing OPEN
ACCESSIBILITY CONCERN in `main.css` (no more out-of-order tab-order
region at narrow widths).

Side-rail restyled neutral (the Limestone/beige `--surface-secondary`
fill is gone, replaced with the same `--surface-primary` every
Workspace panel uses). Heading renamed "Case Workspace" -> "Workspace"
(display only - internal module names unchanged, matching the existing
Case->"Investigation" display-relabeling precedent). Added a real
`?source=<id>` document/drawing viewer inside the Workspace pane.

**Conversation dock:** the existing Case-level and Project-level
conversation accordions are now docked to the bottom of the viewport
via CSS sticky positioning - deliberately NOT physically relocated out
of their template position (the RFI delegation-choice/preview UI is
tightly coupled to the conversation, and Discussion/Review-threads
shares the same accordion group right after it; moving just the
message list risked breaking either). Compact by default with an
explicit expand toggle, and a real sessionStorage-backed draft/scroll-
position preservation script (this app is server-rendered, nothing
survives a navigation without deliberately saving it client-side).

**Hot-links:** `services.case_workspace.resolve_conversation_hotlinks`
turns an exact, currently-known Source filename mentioned in
conversation text into a safe `?source=` link - never a regex guess,
resolved fresh every render. Framework-agnostic (plain segments, no
Flask import); `app.py`'s new `hotlinks` Jinja filter builds the
actual escaped markup.

**Sections F (multi-thread conversation lifecycle) and H (reviewer-
governed pattern suggestions) are captured as specified-but-unbuilt**
(`governance/specified-unbuilt/conversation-thread-lifecycle.md`,
`reviewer-governed-pattern-suggestions.md`), not rushed: F needs a new
persisted object and a genuinely honest provenance guard before
permanent deletion could ever be allowed - no current field traces
"this message caused Finding X," and guessing at that check felt
irresponsible to squeeze in alongside everything else this stage
already covered. H's own instruction ("Archiosk may learn how the
reviewer investigates without learning what the reviewer must
conclude") is a near-verbatim restatement of this repository's own
ratified Experience Corpus principle, and `governance/STATUS.md` marks
"the Experience Corpus (all forms)" **NOT AUTHORIZED** - the new
document argues the personal/project-scoped version actually requested
is a genuinely different, narrower, never-promoted thing, but that
argument needs its own explicit review before being built, not a
unilateral decision made mid-stage. Both get an honest "planned, not
available yet" note in the dock instead of a dead/misleading control.

See this stage's own final report (delivered in-conversation) for the
full repository-grounded assessment, the responsive/accessibility
review, and the product-owner browser checklist.

---

## 2026-07-31 — CLAUDE-P40-D2-CLOSE: product-owner browser acceptance seal

**No code change - verification only.** The product owner completed
the browser validation P40-D2 handed off: `probe_rfq.txt` loaded
normally, the ownerless Reviews-era project loaded normally, neither
showed an error page, traceback, debugger control, console link, or
PIN prompt.

Post-browser fingerprints, recomputed read-only (route not reopened by
this agent):

| File | Pre-browser | Post-browser |
|---|---|---|
| `cdf185e5....json` | `90df028b18...` | `90df028b18...` (unchanged) |
| `cdf185e5....workspace.json` | `b6832930...` | `b6832930...` (unchanged) |
| `cdf185e5....governance.jsonl` | `e9ad35c780...` | `e9ad35c780...` (unchanged) |
| `eece5c88....json` | `6ac1f25aab...` | `6ac1f25aab...` (unchanged) |
| `eece5c88....workspace.json` | `a9e38d3b3a...` | `a9e38d3b3a...` (unchanged) |
| `eece5c88....governance.jsonl` | `7302cf0ab6...` | `7302cf0ab6...` (unchanged) |

**All six files byte-identical** - stronger than the permitted result
required (which only allowed `last_viewed_by` to differ). Most likely
explanation, grounded in the code: `show_workspace`'s `last_viewed_by`
write sits inside `if active_case is None:` (the Project-Home-only
branch) - a view that landed on a specific Case via `?case=` skips it
entirely, a real and unremarkable path, not a defect. Nothing
forbidden changed either way: no visibility field newly persisted, no
`reviews`/`legacy_reviews` rename, no dataclass default added, no
ownership/access/Case/Finding/Artifact/Analysis/Apply/conversation/
evidence/governance content changed.

**P40 acceptance seal:** P40-B, P40-C, P40-D, P40-D1, and P40-D2 are
all product-owner-accepted as of this verification. Full suite as of
commit `9b88e83`: 1242 passed.

---

## 2026-07-31 — CLAUDE-P40-D2: the view-persistence boundary

**Commit:** `4c7a452`. Full suite: 1242 passed (was 1231).

The unfinished part of P40-D: `show_workspace`'s `last_viewed_by`
tracking called `store.save(workspace)` on every ordinary Project Home
GET, and `save()`'s `json.dumps(asdict(workspace))` serializes the
COMPLETE in-memory dataclass - so viewing a legacy record silently
persisted P40-C's backfilled Case visibility, P40-D's `reviews` ->
`legacy_reviews` rename, AND every other dataclass field's default
value that was never in the original file, purely as a byproduct of a
read. An isolated route-level reproduction (real Flask test client
against isolated copies) proved it: a single GET on a legacy record
changed 21-60 fields, not the one `last_viewed_by` entry it was
supposed to record.

**Fix:** `CaseWorkspaceStore.record_last_viewed(workspace, reviewer)`
replaces that `save()` call - patches only `last_viewed_by` directly
into the raw on-disk JSON, never through
`ProjectWorkspace(**data)`/`asdict(workspace)`, and deliberately never
reads/bumps `version` (view metadata has no governance meaning and was
never a structural write). Re-verified on fresh isolated copies of
both previously-affected records plus all 19 real persisted projects
(copied into an isolated corpus): after the fix, exactly one field
changes per GET, stable across repeated views, across the whole corpus.

**Real-world finding, disclosed honestly:** fingerprinting the real
`eece5c88...` (the ownerless Reviews-era project) at the start of this
stage found it no longer matched its P40-D preservation copy - between
P40-D's own handoff and this stage starting, someone (almost certainly
the product owner, following P40-D's own instruction to open it as
administrator) opened it for real, hitting the still-unfixed bug this
stage closes. Its `reviews` key was renamed to `legacy_reviews` (both
review entries - decision/reviewer/note/timestamps - fully preserved,
byte-for-byte, just under the renamed key) and its owner was set to
`workspacetester` via the pre-existing, legitimate, already-governed
`ensure_owner_backfilled` mechanism (a real `project_owner_set`
governance event, deterministic exact-match against the original
ingestion actor - unrelated to and not weakened by this stage). Per
this stage's own explicit instruction for `probe_rfq.txt`'s prior
one-time normalization, this was NOT reverted - reverting would itself
be the "manually correct a real project record" action this whole
CLAUDE-P40 series has consistently refused to do. Recorded here as a
second, now-closed one-time normalization: no further view of this or
any other project will do this again.

See this stage's own final report (delivered in-conversation) for the
full before/after field classification, the isolated 19-project route
sweep result, and the live-server fingerprint sequence.

---

## 2026-07-31 — CLAUDE-P40-D1: authentication-surface isolation

**Commit:** `4190ee0`. Full suite: 1231 passed (was 1214).

A real product-owner screenshot showed `/login` rendered inside the
authenticated application shell - full left navigation, real project
names visible. A non-disclosure/authentication-boundary defect, not
styling. Root cause: `login()`'s GET handler rendered `login.html`
unconditionally regardless of session state, and `login.html`/
`forgot_password.html`/`reset_password.html` all extended
`gateway_base.html` -> `base.html`, whose side-rail nav (which queries
the live project-listing store) renders whenever `authenticated` is
true - true for an already-signed-in session hitting `/login` directly
(a stale bookmark, a second tab).

**Fix, four parts:** `templates/auth_shell.html` - a genuinely
standalone shell for `/login`/`/forgot-password`/`/reset-password`
that never extends `base.html` at all, so the nav markup structurally
does not exist to leak (CSS-hiding was never going to be sufficient,
per this stage's own explicit instruction). `app.py`'s
`inject_globals()` now guards `nav_recent_projects`/`authenticated`/
`is_admin` for exactly these three routes, so the project-listing
store query itself never runs for them - not just its rendering.
`routes/portal.py`'s `login()` now redirects an already-authenticated
request to the landing route instead of ever rendering the form
(honoring `?next=` when same-site, matching the existing post-login
redirect convention). `logout()` now returns to the isolated `/login`
page instead of the general `/` landing page.

`gateway.html` (the legitimate post-login project gateway) is
unaffected - still extends the original `gateway_base.html`/uses
`.gateway-page`/`.gateway-card` inside the real authenticated shell,
exactly as before. `STATIC_VERSION` bumped in `.env` for the
`main.css` change (new `.auth-shell-page`/`.auth-shell-footer` rules
only - no existing gateway rule was touched).

**Tests:** 17 new (`tests/test_p40d1_auth_shell_isolation.py`) proving
anonymous and already-authenticated requests to all three routes carry
no project name/ID/nav markup and never call the project-listing
store; sign-out returns the isolated shell and actually clears the
session; an unauthenticated/expired-equivalent request to a protected
route redirects to the isolated shell without leakage; the real
authenticated app shell (`/gateway`, `/`) is unaffected; P32 project
authorization (owner access, non-owner 404) is unaffected. Fixed
nothing pre-existing - `tests/test_csrf_protection.py`'s "every page
exposes the csrf-token meta tag" invariant was preserved by keeping
that inert meta tag in the new shell alongside each form's own
explicit hidden `csrf_token` input (this shell doesn't include
`base.html`'s JS auto-injection script at all).

Live-server HTTP check (not browser-rendered - labeled honestly, per
this stage's own explicit instruction): a fresh `python app.py`
restart confirmed serving `main.css?v=18`, and the anonymous `/login`
response contains zero `app-shell`/`side-rail`/`nav-toggle` markers.

---

## 2026-07-31 — CLAUDE-P40-D: persisted-project compatibility closure, mutation-free corpus validation, Add Addendum requirement capture

**Commits:** (see repository log for the staged P40-D commits). Full
suite: 1214 passed (was 1200).

Closes the second legacy-record defect P40-C's own bounded audit found
and deliberately deferred: `TypeError: ProjectWorkspace.__init__() got
an unexpected keyword argument 'reviews'`. Root cause traced to commit
`d1ac48e` ("Extend Case Workspace with three-part review model...")
which replaced the single original `Review` concept (commit `0e86380`,
`decision` one of `accept`/`reject`/`needs_evidence`/`correction`) with
two deliberately different concepts (`reviewer_validations` -
epistemic accuracy; `dispositions` - workflow decision, "what Apply
actually checks"). No honest one-to-one mapping exists (`"accept"`
plausibly meant both at once under the old single-concept model), so
nothing is converted or guessed: `CaseWorkspaceStore._hydrate_legacy_
reviews` preserves the raw legacy list verbatim under a new
`ProjectWorkspace.legacy_reviews` field, distinct in name from both
current concepts, applied at the same centralized `get()` boundary as
P40-C's `_hydrate_legacy_cases`.

**Important nuance, established by code inspection before writing any
fix:** unlike P40-C's `visibility` `KeyError` (which reached no
guard anywhere and was a real traceback-exposure incident), this
`reviews` `TypeError` was already caught at every real call site
(`routes/workspace.py`, `routes/portal.py`, `app.py`, `routes/
security.py`, `services/ingestion.py`, `services/project_access.py`,
`services/security_assurance.py` - all pre-existing CLAUDE-P37
hardening) and already failed closed to a 404/skip, never a raw 500.
So this was a product-availability defect (the affected project was
silently unopenable by its own owner, indistinguishable from
nonexistent), not a security defect - the fix restores real access, it
does not change the security posture. Confirmed via an isolated
worktree at the current baseline that the pre-fix `TypeError` is
byte-identical to what every one of those existing `except TypeError`
blocks already caught.

**Mutation-free corpus sweep:** all 19 currently persisted projects
load successfully through `CaseWorkspaceStore.get()`/`visible_cases_
for`/`RequirementsRegistry.get()`/`project_conversation_for` against an
isolated copy, with zero source-file mutation (fingerprint-verified
before/after). Four needed the P40-C visibility adapter, one (the
`reviews` project) needed both adapters together - no other
compatibility gap found across the whole corpus.

**Regression note:** fixed three pre-existing tests
(`test_project_access_control.py::CorruptedLegacyWorkspaceRouteTests`,
`test_security_assurance.py::SelfCheckTests::test_self_check_reports_
a_corrupted_legacy_workspace_as_an_anomaly_not_a_crash`, plus a stale
fixture in `test_market_critical_golden_path.py`) that had used a
literal `"reviews": []` key as their stand-in for "a generically
unrecognized/corrupted workspace field" - now that `reviews` is a
handled compatibility case rather than a crash, those fixtures were
updated to a still-genuinely-unrecognized field name so the underlying
fail-closed invariant they test remains exercised.

**Add Addendum requirement captured, not implemented:** recorded at
`governance/specified-unbuilt/add-addendum-facility.md`, following the
same "Specified But Unbuilt" convention as `tenancy-and-project-
authorization.md` - the product owner's exact requirement (child
record under an existing project, never a new project; source
choices; "reference first, archive once"; one immutable snapshot per
issued addendum; the full record-field list; amendment interpretation
deferred to a later governed workflow) preserved verbatim, with open
design decisions explicitly left open for whichever future stage is
separately authorized to design and build it.

See this stage's own final report (delivered in-conversation) for the
full per-project sweep table, the field-level P40-C-workspace-record
diff, and the live-server validation evidence.

---

## 2026-07-31 — CLAUDE-P40-C: legacy record compatibility, P40-B regression audit, safe failure containment, debugger elimination

**Commits:** `87869e8` (legacy Case-visibility compatibility fix),
`208601e` (safe failure containment + debugger elimination). Full
suite: 1200 passed (was 1177).

A real incident: opening a legacy project (Cases predating commit
`04fc14a`, "Implement Case visibility") crashed with `KeyError:
'visibility'`, and because `python app.py` unconditionally passed
`debug=True` to Flask, the resulting traceback page exposed Werkzeug's
interactive debugger and a PIN prompt - a real security defect, not
just a compatibility bug.

**Forensic causation, established from repository evidence, not
inference:** reproduced the identical crash via an isolated worktree
at the exact P40-B baseline (`4f97a6b`) and at final `448fe2d`,
replaying the same preserved copy of the affected record at both
points - byte-identical failure. `git diff` across the full P40-B
range confirms `visible_cases_for`, `show_workspace`'s early lines,
and every sidebar-listing file (`routes/portal.py`, `app.py`,
`templates/base.html`) were untouched by any P40-B commit.
**Classification: pre-existing and independently discovered, not
caused or exposed by P40-B.** `visible_cases_for`'s docstring itself
identifies it as a "ratified governance baseline," present since Case
visibility was first introduced - the crash has been latent for any
project with Cases older than that commit for as long as it has
existed.

**Compatibility fix:** `CaseWorkspaceStore.get()` (the single,
centralized `ProjectWorkspace(**data)` construction site in this
codebase) now hydrates a missing `visibility` key to
`CASE_VISIBILITY_SHARED` - deliberately not `PRIVATE` (would
retroactively impose a restriction the data was never subject to when
created - not "failing closed," inventing a new restriction) and not
`COLLABORATIVE` (falsely asserts genuine collaboration occurred,
Constitutional Invariant 12). One centralized fix, not fourteen
scattered patches - verified directly that it also resolves the
identical unguarded `case["visibility"]` access in `share_case`,
`retract`, `archive`, and `derive`. Project-level authorization
(`can_access_project`, P32's deny-by-default owner/allow-list/admin
gate) is completely unaffected - this only ever runs on
`workspace.cases`, reachable only after project access is already
granted.

**Security fix:** `app.py`'s `python app.py` entrypoint no longer
passes `debug=True` unconditionally - that literal overrode
`app.config['DEBUG']` entirely regardless of `.env`/`FLASK_ENV`, and
also explains why the incident bypassed the already-built, already-safe
`@app.errorhandler(500)` page (Flask only routes to registered error
handlers when `app.debug` is `False`). The reloader (a genuinely used
dev convenience) stays on; the interactive debugger is now off by
default, requiring both a narrow exact-match opt-in
(`ARCHIOSK_ENABLE_DEBUGGER == "1"`) and an explicit development
environment (`FLASK_ENV == "development"`) together - extracted into
`_interactive_debugger_enabled()` specifically so this is directly
testable, not just readable as source. `wsgi.py` (Gunicorn's real
production entrypoint) now hard-codes `create_app("production")`
rather than resolving via `FLASK_ENV` - found during this stage's own
audit that this repo's own `.env` sets `FLASK_ENV=development`, which
would otherwise leave the production entrypoint's config resolution
dependent on whatever a deployed `.env` happens to contain.

**Verified:** an unhandled exception induced via test instrumentation,
in a genuinely production-like configuration (`DEBUG=False`,
`TESTING=False` - not the hermetic unit-test config, which itself sets
`TESTING=True`), now returns the existing safe generic error page for
HTML routes and a clean JSON envelope for `/api/v1/` routes, with the
full traceback logged server-side only. Live-server validation (real
HTTP requests against the actual running `python app.py` process, the
same entrypoint the incident used): the authorized owner/admin opens
the exact affected route successfully; an authenticated-but-
unauthorized user is denied (404); the record's `.json`
(extraction) and `.governance.jsonl` (audit log) files remain
byte-identical before and after. The `.workspace.json` file's content
does change after live authorized access - honestly disclosed, not
hidden: `show_workspace` already calls `store.save(workspace)`
unconditionally on every Project Home view, to record
`last_viewed_by` - a real, pre-existing mechanism, unrelated to and
unchanged by this fix, that already wrote on every view before this
fix existed; the hydrated `visibility` field is naturally captured by
that already-happening write, adding exactly one key and changing no
id, text, or other field.

**Bounded audit, not broadened:** reviewed the complete P40-B-touched
surface for the same class of legacy-record assumption - found none
(every P40-B-introduced field is additive/Optional with safe
defaults). A read-only smoke pass across all 19 persisted projects
found exactly one other, structurally different legacy defect
(`TypeError: ProjectWorkspace.__init__() got an unexpected keyword
argument 'reviews'` on a different project, from an obsolete field
name rather than a missing one) - explicitly deferred as a different
root cause outside this incident's scope, not fixed here.

See this stage's own final report (delivered in-conversation) for the
full commit-level audit table, the before/after fingerprint proof, and
the ranked deferred items.

---

## 2026-07-31 — CLAUDE-P40-B: product-owner browser defect closure and first-use trust repair

**Commits:** `27a2a03` (Batch A: truthful controls/copy), `045fc27`
(Batch B: Q&A continuity/precision), `449c65a` (Batch C: rename
uniqueness), `4124221` (Batch D: Briefing timeout root cause +
truthful activity state). Full suite: 1177 passed (was 1151).

A real product owner's own browser session (Test 2 / Riverside
projects) surfaced eight defect areas; all eight were repository-
confirmed via direct code inspection/execution before any fix, per
this stage's own explicit "reproduce or mechanically trace each issue"
requirement (P40-B, superseding the earlier same-day P40-R corrective
review that flagged an authorization mismatch and an evidence-
overstatement problem in the prior P40 stage - this stage's own
verification evidence is explicitly labeled by class throughout, never
presented as browser-observed when it was HTTP-driven).

**3.3 (View-all controls dead)** and part of **3.5 (Q&A destination
unclear)** shared one root cause: `templates/_macros.html`'s
`accordion()` macro only ever writes `data-accordion-id`, never a real
HTML `id`, unless `html_id` is also passed - the "Requirements", "Key
Dates", and "Project Conversation" accordions never got one, so
same-page anchor links had nothing to scroll to and an *already-built*
auto-open-on-anchor script (`static/js/case_workspace.js`) had nothing
to find. Fixed by adding the three missing `html_id`s - no new JS.

**3.4 (silent mid-word truncation)**: `services/bhive_parser.py`'s
`_derive_milestones` did `req.text[:120]` with no ellipsis and no
justifying comment - a pre-P40 leftover that P40's own reflow fix made
bite far more often (real sentences are now whole, and therefore often
longer than 120 characters). Truncation removed; milestone labels now
match every other candidate list on the page, which never truncated.
The two "questionable classification" examples in the prompt (annual
financial statements / backup restoration / security events under
Technical; a lowest-price waiver under Financial) could not be
reproduced or investigated - they come from the product owner's own
real document, never provided to this repository - and were
explicitly deferred rather than guessed at.

**3.7 (drawing-only language leaking into text-RFP Cases)**: six leak
points (four in `templates/case_workspace.html`, two in `services/
conversation_interpreter.py`'s fallback replies) all fixed by reusing
the SAME `drawing_sources` check the existing "+ Add drawing Source"
control already computes - conditional, not a blanket swap: a Case
that genuinely has a drawing Source still sees the original,
drawing-specific copy verbatim.

**3.8 (dead-looking header controls)**: the minus (Collapse All) and
star controls were both already fully functional on inspection (real
routes, real persistence, real active-state CSS) - the star was just
missing a hover tooltip its sibling button already had. The three-dot
overflow menu was also functional but its bare glyph, containing
exactly one action, read as confusing ceremony - relabeled to a plain
"Edit" affordance, which also directly serves **3.1**'s "provide a
visible way to rename after ingestion."

**3.1 (Project identity)**: a real, repository-confirmed gap found
during investigation, not merely asserted - renaming a Project via
Edit Project Details never checked name uniqueness at all, even though
upload-time naming does (`services/ingestion.py`'s
`_reject_if_name_taken`). Extracted the same rule into a new public
`reject_if_display_name_taken`, excluding the Project being renamed
itself, wired into `edit_project_details`. No detected-source-title
comparison engine was built - no reliable "detected title" field
exists anywhere in the current schema, and this stage's own governing
prompt explicitly permitted deferring that in favor of edit
discoverability now.

**3.5 (quick_start silently creating a Case for a plain question)**:
already a named, open concern in `ConversationMessage`'s own docstring
before this stage ("forcing one into existence just to hold a message
is exactly the surprise quick_start currently causes"). Fixed by
reusing the existing `_looks_like_project_question` heuristic (already
trusted by `discuss_object`'s own reply routing) as a soft guard - a
plain question now routes through the same `case_id=None` project-level
conversation `discuss_object` uses; anything that doesn't read as a
plain question still creates a Case exactly as before. The governed
Investigation path itself was not touched.

**3.6 (document-identity answer imprecise)**: `services/project_qa.py`'s
prompt only ever said `"Source document: <filename>"`, with no access
to the Project's own `display_title` and no instruction distinguishing
filename from a formal title/RFP number/version if one exists in the
evidence; separately, `services/conversation_interpreter.py` flattened
the answer and its citations into one string. Fixed: the prompt now
names every identity concept explicitly and asks for a concise direct
answer; `grounded_in` now travels as its own additive field on
`ConversationMessage`/`InterpretationResult` (old saved messages
simply lack the key) and renders as a collapsed "Source grounding"
subdisclosure - reusing the exact pattern Project Briefing's own
source grounding already established.

**3.2 (Briefing timeout)**: traced to the exact boundary, not merely
widened. `.env`'s `ANTHROPIC_TIMEOUT_SECONDS=30` is an APPLICATION
timeout (the Anthropic SDK's own `timeout=`), confirmed comfortably
under `deploy/gunicorn.conf.py`'s worker timeout (150s) and `deploy/
nginx.conf`'s `proxy_read_timeout` (150s) - extending it carries no
risk of trading one failure for a worse one. Fixed with
`_scale_timeout_for_prompt_size`: the operator's configured value is
respected as a floor, only extended upward for a genuinely larger
rendered prompt, capped at 90s. Also fixed: "A generation request is
already in progress" (conflict-style wording for what is, in this
fully-synchronous, no-background-job architecture, an entirely
ordinary case - a second page load while the reviewer's own first
request is still in flight) reworded to name what's actually
happening; a genuine failure was being shown twice on the same page
(a flash banner duplicating the persistent inline "Generation failed -
Retry" state) - the flash was removed, the inline state alone remains.
No new queue/worker/background-job infrastructure was introduced or
found necessary.

**Verification, by evidence class** (see this stage's own final report
for the full breakdown): unit/integration (1177 passed, +26 new,
covering every fix above); automated HTTP route exercise against the
real running dev server, before/after, including one real (non-mocked)
Anthropic Q&A call - all 18 checks passed; no real browser or
unfamiliar-user verification was performed or claimed.

See this stage's own final report (delivered in-conversation) for the
full root-cause map, the P40-R corrective context this stage continues
from, and the remaining commercial blockers.

---

## 2026-07-31 — CLAUDE-P40: critical co-architect review — repaired visual line-wrap fragmentation

**Commit:** `5cd337c`. Full suite: 1151 passed (was 1130).

Explicit critical-review stage: required re-deriving the P40 bottleneck
from scratch (live re-audit + a 6-candidate comparison) rather than
reflexively continuing P39's own closing recommendation. Walked the
full golden path live against the real running dev server, screen by
screen, sign-in through History. Most of it held up well under direct
inspection (Briefing, grounded Q&A, the P39 Investigation-escalation
fix, the Apply/Issue Approval Gate confirm screens, RFI export,
History) - genuinely clear, professional copy, not the source of the
worst friction. The one sharp, immediately visible break: the
Requirements screen's "Extracted, not yet governed" list showed one
real sentence ("The Design-Builder shall provide all labor,
materials, and equipment required to complete the Riverside Community
Library renovation, including structural upgrades, mechanical
replacement, and accessibility improvements.") split into **three**
separate, independently confidence-scored "requirements," with a real
instance of the SAME sentence's fragments landing in two
**contradictory categories** (technical_specification vs.
compliance_legal). This is the first substantive data screen a
reviewer sees after the Project Briefing - confirmed as the strongest
candidate across customer harm, frequency (near-universal for real
PDF/wrapped-text RFPs), severity, and downstream contamination against
five other named candidates (Zero-Founder screen comprehension broadly,
rigid conversational routing, the three-vocabulary requirement-
adjudication flow, operational readiness, RFI mechanism ambiguity).

**Root cause:** `services/bhive_parser.py`'s `_segment` did a naive
per-physical-line split with no reflow - `pypdf.extract_text()` and a
plain-text upload both reproduce the source document's own visual line
wraps, which fall mid-sentence far more often than not.

**Fix**, scoped to exactly this: `_reflow_wrapped_lines` rejoins
consecutive lines into one logical clause when the accumulated text
doesn't already look sentence-complete and the next line reads as a
genuine continuation (starts lowercase) - never crossing a numbered/
lettered clause marker or a bullet marker, which always start a fresh
item. A line ending in a hyphen directly attached to a letter (no
preceding space - an unambiguous word-break signal, unlike guessing
from spelling) gets a dedicated no-space rejoin, which also correctly
reconstructs this corpus's own most common compound term when it wraps
the same way ("Design-" / "Builder" -> "Design-Builder", never
"DesignBuilder"). `RequirementItem` gained one additive `Optional`
`source_line_end` field for traceability - `_classify`/
`_classify_with_model`/`_classify_with_rules`/`_parse_model_output`
are completely untouched; the end-line map is applied to finished
`RequirementItem`s in `parse()`, after classification.

**Architecture freeze discipline, explicit:** rejected full fragment-
array/join-reason/uncertainty-score provenance tracking as more than
the "no traceability lost" hard-stop actually requires; rejected
touching `services/case_workspace.py`'s governed `Requirement` schema
(the defect lives entirely in the pre-promotion candidate list); no
new parser dependency added (the deterministic heuristic proved
sufficient against every required test shape). Only `services/
bhive_parser.py`'s own segmentation stage changed.

**Existing projects: never touched.** Reflow only runs during a NEW
document's segmentation inside `BHiveParser.parse()` - no migration,
no re-processing, no governed Requirement ID regenerated, no
Investigation/Finding/Disposition/RFI/History record altered.

**Verified live, before/after, against the real running dev server:**
the same real document that showed 36 fragmented "requirements" (with
the exact 3-way-split sentence above) now shows 18, with that sentence
appearing whole under a single confidence score.

See this stage's own final report (delivered in-conversation) for the
full 6-candidate comparison table, the transition map, and the ranked
remaining-blockers list.

---

## 2026-07-31 — CLAUDE-P39: commercial convergence — closed the Requirement-to-Investigation dead end

**Commit:** `14a107a`. Full suite: 1130 passed (was 1127).

First business-convergence stage (governing objective: one continuous,
trustworthy, Zero-Founder-usable golden path — Upload → Briefing →
Requirements → Question → Investigation → Decision → RFI → Export →
History — over further architecture/domain expansion). Audited the
full route/template surface for the mid-to-end half of that path
(Requirements onward — the Briefing half was already known from
P38-D2) via a forked mechanical route-mapping pass plus direct live
HTTP verification against the real running dev server.

**Two real candidates found; one selected.** (1) `services/
bhive_parser.py`'s `_segment` does a naive per-physical-line split with
no paragraph reflow — confirmed live on the real P38-D2 verification
project that every PDF/hard-wrapped-TXT sentence spanning more than one
visual line gets shredded into separate `RequirementItem`s, sometimes
with **different, contradictory categories for fragments of the same
sentence** (e.g. "...as indicated on the" / "structural drawings. Any
material deviation..." split across `technical_specification` and
`compliance_legal`). Real, high-value, but doesn't block the workflow
— extraction is degraded, not broken. (2) The "Discuss this
Requirement" aperture (`templates/_macros.html`'s `aperture` macro,
already correctly wired with anchor fields) and its backend
(`_handle_investigate_requirement` in `services/
conversation_interpreter.py`) both work correctly and — verified live
with a REAL Anthropic call — produce a genuinely well-reasoned,
evidence-grounded Finding. But the escalation offer that gets a
reviewer from "described a concern" to "start an Investigation" only
fired for six hardcoded phrases ("investigate this", "check this",
etc) — a live test confirmed a natural concern ("I'm not sure this
covers electrical systems as well") got a silent, unguided dead end
instead. Selected (2): it's a total, not merely degraded, block on the
Zero-Founder Test's explicit "convert a concern into an Investigation"
requirement, and improves four ranks (Trust Core's workflow-continuity
half, Functional Workflow Completeness, Market-Ready Product, UI
Information Architecture) against (1)'s two (Trust Core's accuracy
half, Extraction). (1) is deferred, not abandoned — see this stage's
own final report's ranked gap list.

**Fix, deliberately narrow** (matching this module's own
"deterministic keyword matching, not reasoning" discipline):
`_INVESTIGATION_PHRASES` gained natural concern-expressing phrasings
found live during this stage's testing ("not sure this covers",
"doesn't mention", "seems to conflict", "unclear whether", "concerned
about", ...) — additive only, every one of the three existing tests
covering the original narrow behavior still passes unchanged.
`_describe_anchor_acknowledgment` now names working phrasing
("Investigate this", "Something is wrong here") for the residual case
no phrase list will ever fully cover, so a miss is no longer silent.
No change to what's automatically analyzed or committed — opening an
Investigation still requires an explicit human click, and the real AI
call inside `_handle_investigate_requirement` still only fires after
that click on an explicit trigger-phrase match when a Case is already
open (that narrower, cost-conscious gate was deliberately left
untouched; only the costless "offer to escalate" branch was widened).

**Other findings, explicitly deferred** (ranked in this stage's own
final report): the extraction line-fragmentation defect above;
"BEEHIVE" (an internal/legacy name never introduced to users anywhere
else) leaking into the RFI-preview flash message; raw UUIDs
(`artifact.id`/`analysis_id`/`engine_name`) rendered inline, not
behind a disclosure, on Finding cards; the `findings-empty` state's
"analyze a drawing Source" copy being the wrong medium for a text-RFP
product; two unrelated mechanisms ("governed per-Finding RFI draft"
vs. the legacy project-wide consistency-flag export) both called "RFI
export" with no UI distinction.

See this stage's own final report (delivered in-conversation) for the
full transition map, Rank 1–5 evidence table, and three-stage
commercial convergence plan.

---

## 2026-07-31 — CLAUDE-P38-D2: restore AI-first automation and repair the opening briefing pipeline

**Commits:** `c8856c1` (provenance/lifecycle fields), `14e0d7e`
(analytical-vs-consequential policy distinction + automatic lifecycle
routing), `b160897` (template UX states), `73c0b03` (semantic repairs +
source grounding), `ebd451d` (realistic fixtures + tests). Full suite:
1127 passed (was 1104 before this stage's own new tests + P38-D2's
9-test lifecycle class + the em-dash/background-prose classifier
tests).

CLAUDE-P38-C/P38-D1 had left a manual-only Generate button and no way
to tell an approval-required policy state from an outright denial.
This stage restores the original governing intent ("automatic
analytical AI where policy permits; human authorization required only
for consequential actions") without adding a new governed action or
weakening the mandatory floor: `_project_briefing_ai_status()`
(`routes/workspace.py`) turns the existing `evaluate_action()` result
into three states the route now actually branches on
(allow/require_approval/denied) instead of collapsing everything
non-ALLOW into one generic path.

**Automatic lifecycle:** `/upload` now redirects through a real,
visible "Preparing your Project Briefing…" interstitial
(`preparing_project_briefing` route + template) that auto-submits the
real generation request — not a hidden background job.
`tools/dependency_fit.py --requires-background-worker` confirmed this
deployment has no queue/worker infra and no async runtime, which is
what ruled out every alternative except synchronous generation behind
a visible waiting page. A duplicate-call guard
(`generation_in_progress_for`, keyed off a timestamp that treats
anything older than 90s as abandoned) prevents a second real, billed
call while one is in flight.

**Bug found and fixed during this stage's own build:** the
interstitial's original "is there a Source to brief from" gate checked
`workspace.sources`, but the originally-ingested document never gets
its own `Source` record (only later manually-added material does) —
that gate would have skipped automatic generation on every real
upload. Now checks `document.requirements`/`milestones`/
`workspace.sources` together.

**Semantic repairs** (`services/project_briefing.py`):
`_looks_like_bare_heading` rewritten to a two-step prefix+verb check so
em-dash/en-dash/colon/semicolon/no-punctuation schedule headings are
excluded regardless of punctuation, not just a plain ASCII hyphen; a
new `_BACKGROUND_PROSE_PATTERNS` excludes descriptive present/perfect-
tense prose that shares topic vocabulary with a real requirement but
isn't one; `_TECHNICAL_INCLUSION_SIGNALS` tightened to require an
actual obligation-shaped phrase, not a bare topic noun.

**Trust record:** `ProjectBriefingResult.grounded_in` — a small set of
verbatim-quoted excerpts from the same extracted evidence, never
invented. `set_project_briefing` now preserves exactly one prior
version (`project_briefing_previous`) instead of overwriting it, shown
via a compact history disclosure. Provider/model/generated-by/source-
signature are now all displayed.

**UX states** (`templates/case_workspace.html`): distinct copy and a
`data-briefing-state` attribute for preparing / ready / stale-
regenerable / stale-approval-required / stale-denied / approval-
required / denied / failed-with-retry / no-source — never one generic
flash regardless of what's actually happening.

**Verification, reported by category (see this stage's own final
report for the full breakdown):** unit/integration (1127 passed, incl.
57 in `tests/test_project_briefing.py`); mocked-AI (the 9-test
`ProjectBriefingLifecycleTests` class, real Flask route/template stack
with only the Anthropic SDK call mocked); real-provider (multiple real,
non-mocked Anthropic calls against the actual running dev server —
automatic ALLOW-path generation, an explicit `confirm=once` approval-
gated generation, ~20s each — via a throwaway `*.invalid` admin account
created and suspended again in-process, never touching the real user's
credentials); live policy-state verification (DENY and
REQUIRE_APPROVAL both exercised against the real running server by
temporarily changing the deployment-wide `SecurityGovernanceStore`
baseline, then explicitly restored to `allow`/baseline afterward —
confirmed via the app's own resolver post-restore). No pixel-level
responsive/viewport verification was done (no screenshot tool in this
environment, same stated gap as CLAUDE-P38-C).

**Explicitly not built:** a debounce mechanism for "excessive repeated
calls during multi-file ingestion" — the app only ever ingests one file
per upload request (`request.files.get('file')`, singular) and a stale
briefing requires an explicit click to regenerate (never automatic), so
the scenario the debounce would guard against doesn't exist in this
codebase's current architecture. No P39 work began.

See this stage's own final report (delivered in-conversation) for the
full policy-state/failure-state matrices and exact browser-retest
steps.

---

## 2026-07-31 — CLAUDE-P38-C: Project Briefing semantic repair and controlled workspace simplification

**Commits:** `5817977` (semantic classification + compact previews),
`0786fb5` (page hierarchy, composer clarity, management-control
grouping). Full suite: 1104 passed (1086 + 18 new).

Browser retest of CLAUDE-P38-B found three real defects: (1) Technical/
Financial/Key Dates previews included unrelated clauses (privacy
prose, material-deviation language, proposal-preparation costs, bare
stage-title headings) because `RequirementItem.category` is a coarse
bucket never designed for this precision; (2) raw extraction lists
rendered directly on the landing page, burying the Generate button;
(3) two unlabeled composers and a fully-expanded Lifecycle/Layers block
competed with the opening briefing for viewport space.

**Fixed via a bounded exclusion/inclusion filter** layered on top of
the existing categories (`_qualifies_as_technical`/`_qualifies_as_
financial`/`_qualifies_as_key_date` in `services/project_briefing.py`)
— same discipline as CLAUDE-P38 OBS-09's cover-page-metadata filter,
not a classifier rewrite. Exclusion always wins; an uncertain item is
left out of the preview, never guessed in, but never deleted from the
full register. **Two additional false positives found live** (not in
the original prompt) during this stage's own verification against a
real running instance — a bare "Section 3 - Financial Submission"
heading satisfied its own inclusion signal, and a bare "following"
matched ordinary prose as if it were relative-milestone timing — both
fixed and regression-tested before sealing.

**Page hierarchy:** Generate/Regenerate now appears before any
deterministic list; each preview capped at 5 items with a real
qualifying count and an explicit "Open X" link; the two composers kept
as explicitly labeled, distinct controls (acceptable-fallback option —
unifying them would mean teaching `quick_start`'s unconditional
always-creates-a-Case behavior to route conditionally, a real
behavioral change to an existing tested route, not a labeling fix);
Lifecycle/Display Layers moved inside one collapsed "Project
Management & Settings" disclosure; two permanent prose paragraphs
moved behind a collapsed "What is Project State?" disclosure.

**Visual verification:** no browser/screenshot tool is available in
this environment. Verified instead via real HTTP requests against the
actual running dev server (same pattern as CLAUDE-P36) — uploaded a
purpose-built synthetic document exercising every prompt-given
inclusion/exclusion example, inspected the real rendered HTML structure
and content before/after each fix. This confirms content, order, and
absence/presence with certainty; it does **not** confirm pixel-level
responsive layout at wide/medium/narrow viewports — that gap is stated
plainly in this stage's own final report, not glossed over.

See this stage's own final report (delivered in-conversation) for the
full classification rule tables and browser retest checklist.

---

## 2026-07-31 — CLAUDE-P38-B: narrative-first project opening

**Commit:** `c5ecf52`. Full suite: 1086 passed (1070 + 16 new).

Adds a Project Briefing as the first substantial content on Project
Home, ahead of the quick-start composer and every downstream register,
per the explicit governing objective: verify sources → read Executive
Summary/Project Brief → understand objectives/scope/Technical &
Financial submission routes → follow reading guidance → ask grounded
questions → begin detailed review.

**Two deliberately separate layers.** (1) `services/project_briefing.
py`'s `deterministic_sections` — Technical Submission, Financial
Submission, Key Dates, Suggested Reading Path, all grouped from
already-extracted `RequirementItem.category` values and `document.
milestones` (CLAUDE-P38 OBS-11). No AI call, always available, never
says more than the extraction already says — an empty Financial
Submission section states plainly nothing was found, never fabricates
one. (2) `generate_project_briefing` — a real, grounded narrative
synthesis (Executive Summary, Objectives, Project Brief/"Basis of
Understanding" — explicitly labelled a machine-assisted draft, never
an approved Project Charter, Procurement Route, Matters Requiring
Early Attention), mirroring `project_qa.py`/`requirement_
investigation.py`'s established pattern exactly, gated through the
same `ACTION_EXTERNAL_AI_REQUEST` policy check (third real external-AI
site in this app). Never generated automatically on page load — only
on explicit action, cached on `ProjectWorkspace.project_briefing` with
a source-set signature (`source_signature_for`/`set_project_briefing`)
so a stale briefing is honestly flagged, not silently served.

**Explicitly not implemented, per this stage's own scope:** the
accordion-launched closable-working-tab architecture (remains a
separate future evaluation — no work began on it); a full three-tier
reorganization of every existing sidebar section into Primary/
Secondary/Management groups (the briefing is inserted first; P38's
already-tested section order elsewhere is unchanged, avoiding
unnecessary layout regression risk); estimating/ETCO/spreadsheet/
bidder-scoring functionality; date arithmetic (fixed/relative wording
shown verbatim, never calculated into an actual date).

See this stage's own final report (delivered in-conversation) for the
full capability assessment and browser retest steps.

---

## 2026-07-31 — CLAUDE-P38: browser-walkthrough defect closure and workspace usability repair

**Commits:** `413c545` (project Q&A), `f3f004d` (requirement over-
extraction + pipeline visibility), `585407d` (Key Dates + RFI
register), `d97b65a` (participant/instructions/Go-No-Go/lifecycle
authority), `02e5e8c` (Accepted Knowledge/Sources/History UX + two
regression-test fixes). Full suite: 1070 passed, 0 failed.

Fourteen browser-observed defects (OBS-01 through OBS-14) from the
product owner's own hands-on walkthrough of the Case Workspace, closed
in priority order. **No P37-A scope (pharmaceutical/ETCO/bidder-
scoring/spreadsheet-ingestion domain) was implemented** — that prompt
referenced files and terminology that don't exist in this repository
and was explicitly disregarded per the product owner's own
instruction; P38 stayed bounded to the real, existing construction
Design-Build RFQ/RFP workflow throughout.

**Priority 1 — core usability:**
- **OBS-01:** "Talk to this Project…" rejected ordinary questions
  ("What are the objectives of this RFP?") because `discuss_object`
  always posts with no anchor, so the message could never reach the
  Requirement-investigation path. New `services/project_qa.py` (mirrors
  `requirement_investigation.py`'s Anthropic pattern exactly) answers
  ordinary project questions grounded only in already-extracted
  evidence — never the model's world knowledge — with the same
  honest-degrade discipline, gated through the identical
  `ACTION_EXTERNAL_AI_REQUEST` policy check CLAUDE-P36 established.
  Bounded to messages that look like questions, so a stray message
  never triggers a real model call.
- **OBS-09:** cover-page/header metadata (RFP number, version, issue
  date, issuing organization, document status) was classified as a
  requirement candidate exactly like real text — neither classifier's
  schema has a "not a requirement" option. Fixed with a narrow
  pre-filter (`_is_document_metadata_line`) on the label:value shape
  cover pages use, applied before classification, not a change to
  either classifier's prompt.
- **OBS-07/OBS-10:** Requirement Compliance showed only "No
  Requirements... yet" with no indication candidates existed elsewhere
  (Sources reported 1,404, this section showed nothing). Now surfaces
  the already-computed candidate count with a direct link.
- **OBS-11:** Key Dates only showed manually-created dates, ignoring
  `document.milestones` (already extracted by `BHiveParser.
  _derive_milestones`, never surfaced anywhere). Now shown as a
  clearly separate, unconfirmed "From the source document" list.
- **OBS-08:** "RFI Export" implied RFIs only originate from flagged
  contradictions and that export was the whole feature. Renamed "RFIs"
  and rebuilt as a genuine project-wide register
  (`rfi_drafts_view`, filtered to `visible_cases` — same Case-privacy
  discipline the Findings section already applies).

**Priority 2 — governance and authority:**
- **OBS-04:** `record_go_no_go` was `@login_required` only — any
  authenticated participant, including `read_only`, could record the
  real decision. Now admin-only, enforced server-side in the route
  body. `GoNoGoAssessment` gained optional `decided_by_role`.
- **OBS-05:** same gap for Project Instructions — added
  `operating_instructions_updated_by_role`; the permanent governance
  explanation is now behind a collapsed disclosure.
- **OBS-03:** "Register a Participant" read like creating a login for
  someone else. Traced the actual mechanism and confirmed no
  impersonation exists — every governed write already records the real
  authenticated actor (added a test asserting this explicitly).
  Renamed to "Add a Project Party" with copy stating plainly it's a
  directory entry, not a login.
- **OBS-14:** the Lifecycle strip was fully static — "current" was
  hardcoded to RFP regardless of any real project state (no
  lifecycle-phase field exists anywhere in the domain model). Removed
  the false claim and "Historic Record" from the phase list rather
  than inventing a governed phase-transition mechanism with no
  evidence to design correctly; labeled "reference only — not tracked
  by this project."

**Priority 3 — workspace clarity:**
- **OBS-02:** Accepted Knowledge's permanent explanation paragraph is
  now behind a disclosure; the empty state shows real Finding counts
  (awaiting/applied) instead.
- **OBS-06:** source cards now show upload date. The exact quoted
  defect ("...already extracted by the Extract/Segment/Classify/
  Assemble pipeline") wasn't found verbatim anywhere in the current
  templates — likely already addressed by OBS-07/09/10's fixes, or was
  a summarized impression; not fixed as a literal string that doesn't
  exist.
- **OBS-12:** History defaulted to an always-expanded full list. Now a
  compact summary by default; "Show full history" persists via
  localStorage, same pattern as the existing Layers risk toggle. The
  complete audit record is unaffected either way.
- **OBS-13:** Layers renamed "Display Layers"; the checkbox label
  reframed as "viewing as X" rather than looking like the control
  belongs to that person.

**Deferred, explicitly not attempted this stage** (each judged to
require inventing real new architecture the walkthrough evidence
doesn't yet justify — recorded here so they aren't silently lost):
a full separate Go/No-Go "Recommendation" object distinct from the
decision itself (OBS-04's fuller vision); typed Project Instruction
categories/scope/expiry/history (OBS-05's fuller vision); RFI lifecycle
states beyond the existing draft/issued/answered (Candidate/Ready-for-
Review/Approved-for-Issue/Withdrawn, OBS-08's fuller vision); a real
governed project lifecycle-phase field and transition mechanism
(OBS-14's fuller vision); History's per-category filters (Human/
System/Access/Instructions/etc., OBS-12's fuller vision); fixed vs.
relative vs. conditional date-type classification for extracted
milestones (OBS-11's fuller vision, since no date-parsing exists at
all yet). None of these block the core workflow; all are legitimate
future work, not silently abandoned.

See this stage's own final report (delivered in-conversation) for the
full per-observation findings, browser re-test checklist, and seal
statement.

---

## 2026-07-30 — CLAUDE-P37: first marketable product slice and browser-walkthrough package

**Commit:** `c2f85dc` (hardened the two real market-critical choke
points). Full suite: 1030 passed (1028 + 2 new).

**Product slice defined** (full detail in this stage's own final
report, delivered in-conversation): first user = Design-Build proposal/
preconstruction reviewer; job = review an RFP/RFQ, adjudicate governed
Requirements, investigate ambiguity with governed AI assistance, and
issue traceable RFIs back to the client. Refines the originally-proposed
market proposition by making explicit that "AI-assisted investigation"
means the real, Anthropic-backed Requirement-investigation path only --
never the drawing-analysis path, which remains an explicit mock/
prototype and must not be presented as production capability in the
first release.

**Legacy-compatibility inspection (Part 6) found the real, previously-
unaddressed risk.** The unsafe `ProjectWorkspace(**data)` construction
is centralized in exactly one place (`CaseWorkspaceStore.get()`), but
defenses against it were duplicated ad hoc and incompletely applied.
CLAUDE-P36 had fixed two peripheral pages; this stage found the two
routines that actually matter most -- `routes/workspace.py`'s
`_load_workspace_or_404` (47+ routes: Case Workspace, Findings, RFI --
the entire market-critical surface) and `services/project_access.py`'s
`load_authorized_project_or_none` (every `routes/api.py` JSON route) --
were still unguarded, meaning the real, already-known corrupted legacy
project would 500 instead of 404 for anyone (authorized or not) who
reached its URL directly. Fixed both (same three-line pattern, sixth
occurrence of this defect class), with two new regression tests.

**Browser walkthrough package prepared, not yet performed.** A new
synthetic test document (`p37_walkthrough_document.txt`, session
scratchpad -- 5 clauses covering one clear investigable requirement,
one deliberately ambiguous one, a schedule pair a reviewer should
notice looks inconsistent, and a missing-referenced-document RFI-worthy
gap) and a single continuous numbered procedure were handed to the
product owner in this stage's final report. This is the first genuine
ask for the product owner's OWN hands-on browser session -- distinct
from, and not satisfied by, CLAUDE-P36's live-but-HTTP-driven
verification.

See this stage's own final report for the full product-slice boundary
(included/optional/excluded), claims register, and legacy-compatibility
Go-Now verdict.

---

## 2026-07-30 — CLAUDE-P36 Case 1/Case 2 walkthrough: performed live, by Claude, against the running app

**Commit:** `6dd1695`. Full suite: 1028 passed (1026 + 2 new).

**What actually happened.** The product owner asked Claude to perform
the Case 1 (denied) / Case 2 (permitted) walkthrough directly, rather
than waiting for a human browser session. No browser-automation tool is
available in this environment, so it was performed the closest honest
substitute: real HTTP requests (Python stdlib `urllib` + a real session
cookie, CSRF token extracted from each page like a browser's JS would)
against the actual running dev server (`restart-app`-cleaned, one
process), using a synthetic test document and a dedicated, suspended-
after-use test account (`p36_walkthrough`) — never the pytest test
client, never a mocked Anthropic call. **This is real live-app
verification, not a substitute for the product owner's own hands-on
browser session** — that distinction stays open regardless.

**Both cases passed.** Case 1 (project security profile set to
`restricted`): Discuss-this-Requirement → Start-an-Investigation
correctly refused with *"not permitted by this project's security
policy (controlling layer: profile)"*, zero Findings created, zero
provider calls. Case 2 (profile reset to `standard`): the same flow
made one real, ~14s Anthropic API call and produced a genuine,
appropriately-hedged provisional Finding (confidence 30%, correctly
flagged insufficient evidence rather than guessing) — carried through
ReviewerValidation → Confirmed Disposition → Apply → RFI draft → issue
→ `.docx` export, all verified with real content. Logged out and back
in: Applied badge, Finding, and issued RFI status all persisted.

**Two real defects found live, not by any prior test:** `GET /security/`
(the Security Department page, needed to set a project's profile for
Case 1) 500'd the instant a real project existed alongside the already-
known corrupted legacy workspace file — a third and fourth occurrence
of the CLAUDE-P32-documented `reviews`-key incompatibility, in
`routes/security.py::department_home` and `services/security_
assurance.py::run_security_self_check`, neither previously covered by
any test (this route had zero HTTP-level test coverage before this).
Both fixed (fail-closed to exclude for the former, matching existing
precedent; reported as an anomaly finding for the latter, since that
function's whole purpose is surfacing anomalies) — this is exactly the
kind of gap a real walkthrough is supposed to catch that a mocked test
suite cannot, even a thorough one.

**Cleanup performed:** the synthetic test project was deleted via the
real `/projects/<id>/delete` route; the `p36_walkthrough` test account
was suspended (not deleted) via `tools/create_credentials.py --suspend`.

**Standing caveats, unchanged:** this was a synthetic document, not a
real confidential one — success here does not prove confidential-client
deployment readiness (per the product owner's own explicit instruction).
The pre-ingestion external-AI selection/disclosure requirement remains
a deferred release-stage item, not implemented, per instruction.

---

## 2026-07-30 — CLAUDE-P36: external-AI governance, confidentiality, and provider-portability gate

**Commits:** `2fd949e` (enforcement + provider-portability fields),
`74a1735` (18-item focused test suite). Full suite: 1026 passed, 0
failed (1017 from CLAUDE-P35 + 9 new in
`tests/test_external_ai_governance.py`).

**What this closes.** P35 surfaced that `services/security_policy.py`'s
`ACTION_EXTERNAL_AI_REQUEST` governed action existed but was never
evaluated before the real requirement-investigation Anthropic call
(`_handle_investigate_requirement` -> `requirement_investigation.
investigate_requirement`) — a DENY baseline already blocked the export
route and the ingestion-time classify/consistency calls, but this one
real-time call site was unguarded. `_handle_investigate_requirement`
now resolves that action through the SAME resolver (`evaluate_action`)
already used by `routes/workspace.py`'s `_evaluate_security_action`
(export gate) and `services/ingestion.py`'s ingestion-time gate —
mandatory floor -> active organization baseline -> this project's own
`security_profile` classification -> any active exception — before any
evidence is gathered or a prompt is built. A denial stops the call
entirely, records an honest `InvestigationStep` (`ran=False`, a
policy-specific `skipped_reason`), and replies naming the controlling
policy layer, distinct from the pre-existing "no API key" / "provider
failed" messages.

**Provider portability (Limited Concession).** `RequirementInvestigationResult`
now carries `provider`/`model`/`requested_at` (set only when `ran=True`);
the caller persists `engine_name`/`engine_version` from what the
provider boundary actually used, instead of independently re-reading
`ANTHROPIC_MODEL` from the environment. No second provider was
implemented — this only removes one small, real Anthropic-specific
assumption from the caller, per P36's own explicit scope restraint.

**Call-site inventory (complete, 3 total):** `bhive_parser.py`'s
`_classify_with_model` and `_check_consistency` were already gated —
both keyed off `parser.ai_calls_disabled`, itself set by
`ingestion.py`'s own pre-existing `evaluate_action` call at ingestion
time (org-wide baseline/exception only; no project exists yet at that
point, an honest, already-documented limitation). `requirement_
investigation.py`'s `investigate_requirement` was the sole real
bypass, now closed. `services/drawing_analysis.py` makes no external
call at all (confirmed mock engine, CLAUDE-P35's own finding) — nothing
to gate there.

**Data minimization (reviewed, no code change).** The investigation
prompt sends: this Requirement's own text/classification/status, its
full adjudication history (including adjudicator usernames), linked
Findings/Relationships/AcceptedKnowledge, supersession/relationship
neighbors, and (opt-in only) the reviewer's represented-party name. It
does NOT send the source document's full text, unrelated Requirements,
project/client metadata, or pricing/contact information. One item
flagged for a future stage, not acted on here: adjudicator usernames
appear verbatim in the prompt — acceptable today (this deployment's
usernames aren't confirmed to be real-name-bearing), but worth revisiting
if a future deployment's usernames do carry real identity.

**Confidential real-document walkthrough gate:** now clear to proceed,
subject to the product owner performing the two-case (denied/permitted)
walkthrough in this stage's own final report before any actual
confidential document is used.

See this stage's own final report (delivered in-conversation) for the
full call-site inventory (Part A), root-cause explanation (Part B), and
the updated two-case walkthrough (Part I).

---

## 2026-07-30 — CLAUDE-P35: complete the first marketable investigation loop

**Commit:** `cf3865c` (golden-path test correction). Full suite: 1017
passed, 0 failed (unchanged count — this stage corrected an existing
test's mechanism, added no new test method).

**Governing context:** accepts CLAUDE-P34 as a successful automated
validation stage, with one central qualification the product owner
raised — the human walkthrough it prepared validated ingestion,
promotion, adjudication, Go/No-Go, access, and persistence, but never
the investigative path from a document to a Finding, Disposition, RFI,
and export. P35's mandate was to close that gap in the actual
application before asking the product owner to attempt the real-
document walkthrough.

**The central finding: P34's own "no UI path exists" claim was based
on incomplete investigation, not a real product gap.** P34 checked
only `_handle_analyze` (the "Analyze this..." trigger, genuinely
drawing-only) and concluded no text-to-Finding path existed at all.
Full investigation of `conversation_interpreter.py`'s dispatch tree
found a second, separate, real, Anthropic-API-backed path was already
fully wired: **"Discuss this Requirement"** (an aperture rendered next
to every governed Requirement, `templates/_macros.html`) posts a
project-level message; an investigation-shaped question is honestly
declined with a `needs_case` offer (no Case open yet, and a Finding
needs one to live in); accepting that offer via the **"Start an
Investigation from this"** button opens a real Case and re-runs the
same question, this time reaching `_handle_investigate_requirement` →
`services/requirement_investigation.py`'s real `investigate_requirement`
→ a genuine provisional Finding via the same `record_analysis` every
other Finding path uses. Verified end-to-end through real HTTP routes
(not just service-layer calls) before any file was changed.

Separately, `services/drawing_analysis.py`'s `analyze_drawing` (the
engine behind `_handle_analyze`) was confirmed to be an explicit
mock/prototype (`ENGINE_NAME = "beehive-mock-vision"`, a hardcoded
4-item finding library) — not real AI. So the ONE real reasoning path
in this product today is the text/Requirement one, not the drawing
one — the opposite of what P34's framing implied.

**Part 4 (bounded correction) resolved to no source change.** Since
the real mechanism already existed, worked, and was already reachable
through ordinary UI navigation, the smallest safe correction was to
`tests/test_market_critical_golden_path.py` itself: its docstring's
false claim was removed, and its Finding-creation step was rewritten
from a direct `store.record_analysis` stand-in to the real two-step
HTTP flow (`discuss_object` → `start_investigation_from_aperture`),
mocking only the one Anthropic API boundary
(`services.conversation_interpreter.investigate_requirement`), so the
composed test now proves the SAME route a real reviewer uses, not a
substitute for it.

**One real gap surfaced, not acted on (belongs to a later stage):**
`services/security_policy.py` already models `ACTION_EXTERNAL_AI_REQUEST`
as a governable action, but neither `discuss_object` nor
`start_investigation_from_aperture` calls `evaluate_action` before the
real Anthropic call runs — a DENY baseline on that action would not
currently block it. Flagged as evidence for CLAUDE-P40 (Security and
Confidentiality Release Gate); out of P35's bounded scope to fix.

**Scanned/image-only PDF:** confirmed no OCR anywhere in this codebase
— `pypdf`'s `extract_text()` returns `""` per image-only page, so
ingestion succeeds but yields zero/near-zero `RequirementItem`s,
silently starving the rest of the chain of anything to promote. Not a
crash; a real capability gap worth surfacing to the product owner
before they attempt a real-document walkthrough with a scanned file.

**Layer B still not performed.** The corrected, single-numbered-
sequence walkthrough (now describing the real Discuss→Start-
Investigation flow) was handed to the product owner in this stage's
final report. Completion requires the product owner's own attempt —
not claimed here.

See this stage's own final report (delivered in-conversation) for the
full source-type map, product decision, forensic/poetic integrity
checkpoint, and market-readiness assessment.

---

## 2026-07-30 — CLAUDE-P34: market-critical golden-path MVP validation

**Commit:** `d533fbc` (composed golden-path test, Layer A). Full suite:
1017 passed, 0 failed (1014 from CLAUDE-P32 + 3 new). Layer B (human
walkthrough) prepared and handed off, not yet performed by the product
owner — see the walkthrough package in this stage's own final report.

**Governing context:** CLAUDE-P33-GATE (architecture reassessment) and
CLAUDE-P33-CORRECTION (market-critical-path rule, medical/second-domain
direction ruled No-Go/Defer) both preceded this stage. P34 is validation
work under that correction — no new capability was authorized, so no
`governance/STATUS.md` row was added this stage.

**What was proven.** One continuous project, walked through real routes
end to end: ingest → operating-environment lock → project ownership/
access (grant, revoke, unauthorized denial) → Go/No-Go → Case creation
→ requirement promotion → adjudication → Finding/ReviewerValidation/
Disposition/Apply → RFI directionality (draft/issue) → per-Finding and
project-wide RFI export → close-and-reopen persistence (a fresh
`CaseWorkspaceStore` instance, not the same in-memory object) →
unauthorized-user isolation still holding afterward. A second test
proves the CLAUDE-P31 security-export gate and the CLAUDE-P32
project-access gate compose independently (a DENY baseline blocks even
the project's own owner). A third is regression coverage for the real
`instance/registry/` `'reviews'`-key incompatibility.

**The single most important product finding.** `services/
conversation_interpreter.py`'s `_handle_analyze` — the only user-facing
"Analyze this..." trigger — accepts only a drawing/image Source. There
is currently **no UI path from a text-ingested RFP/RFQ (this product's
primary document type, per every existing test fixture) to a Finding.**
`CaseWorkspaceStore.record_analysis` is itself source-kind-agnostic, so
the Finding/Disposition/Apply/RFI-directionality chain is proven to
compose correctly — but only reachable for a text document via a direct
service-layer call standing in for a UI trigger that does not exist.
Classified MVP-significant in this stage's own final report; not fixed
this stage (would expand scope beyond validation).

**Pre-existing `reviews`-key incompatibility (`instance/registry/
eece5c88-7288-4373-843a-0fde061c8fe0`):** identified, dated
(2026-07-24, `workspacetester`, `sample_rfp.txt`, no `version` field —
predates that field's introduction), confirmed disposable dev/test
scratch data referenced by no automated test. Chosen treatment:
**excluded from the golden-path specimen, left untouched on disk**
(already covered by CLAUDE-P32's fail-closed handling, now with its
own regression test). No migration, no deletion, no modification.

**Layer B not yet performed.** The walkthrough package (startup
commands, URL, test account, approved document, numbered steps,
expected results, failure/recovery guidance, evidence to return) was
produced and handed to the product owner in this stage's final report.
Completion requires the product owner's own usability judgment — not
claimed here.

See this stage's own final report (delivered in-conversation) for the
full market-critical product map, defect classification, three separate
compartmentalization verdicts (semantic/development/operational — all
No-Go/Defer or Limited-Concession, none Go-Now, for lack of a
demonstrated current bottleneck), and market-readiness assessment.

---

## 2026-07-30 — CLAUDE-P32: project-level access control and isolation gate

**Commits:** `61b0bf5` (domain/service-layer access-control model),
`7262c67` (route/UI wiring and bypass closures), `fdd708a` (existing
test-fixture updates), `831fe4b` (41 new tests), `e83ac25` (governance
amendment + CLAUDE.md hermetic-test note + MANIFEST). Full suite: 1014
passed, 0 failed (973 from CLAUDE-P31 + 41 new in
`tests/test_project_access_control.py`).

**Preceded by a repository reassessment (accepted as the working
scope), then a hard-stop.** Investigation confirmed CLAUDE-P27's own
flagged gap -- any authenticated user could open any project by
guessing its `project_id` -- was still open after P29/P30/P31 each
built locked-environment/capability/security-governance machinery on
top of it. Before writing code, `tests/test_case_privacy.py`'s
`CasePrivacyRouteTests` and `tests/test_route_authorization_hardening.py`
were found to be built on two genuinely different authenticated
sessions both reaching the *same* project (Case-level privacy, not
project-level access, is what each actually verifies) -- a deny-by-
default owner/allow-list model would flip dozens of their assertions.
Presented as a real product decision rather than resolved unilaterally;
the user chose deny-by-default with the two ratified suites' fixtures
(not assertions) updated to grant both sessions access first.

**What was built.** `services/project_access.py`'s `can_access_project`
is the single centralized decision (admin always passes; otherwise
`owner == username` or `username in access_allow_list`; `owner is None`
fails **closed**, admin-only -- the deliberate opposite of every other
None-means-ungated field in this codebase, since no project-level
check existed before this tranche to preserve compatibility with).
Enforced at `routes/workspace.py`'s `_load_workspace_or_404` (AST-
verified 47 of 50 routes already funneled through it; `export_rfi`,
the one exception, was refactored to use it too), `routes/api.py`'s
new `_load_authorized_project_or_404` (6 routes) plus a filtered
`GET /documents`, and `routes/portal.py`'s `_accessible_documents`/
`_require_project_access_or_404` (`/`, `/projects`, `/search`,
`/dashboard/<id>`, `/projects/<id>/delete`).

**A genuinely new bypass found mid-implementation, not on the original
list.** `app.py`'s `_nav_recent_projects` -- the side-rail's project
list, rendered on **every** authenticated page including error pages
via the global `inject_globals` context processor -- listed every
project's display name completely unfiltered. Confirmed live: a denied
project's own name was still visible in the nav rail on the very 404
page proving access to it was denied. Fixed, and filtered before its
display cap so the sidebar isn't under-filled by capping first.

**Owner/allow-list, explicitly not tenancy.** `ProjectWorkspace.owner`/
`access_allow_list` (new fields). `owner` is deliberately re-settable
(admin-only, unlike `operating_environment`'s hard lock -- a wrong
backfill must be recoverable). `grant_project_access`/
`revoke_project_access` reuse `archive_case`/`derive_case`'s own
owner-or-admin authority pattern exactly. `services/ingestion.py`'s
`ingest_upload` gained a required `owner` parameter, deliberately
separate from the pre-existing free-text `actor` field -- confirmed by
real repository evidence (`actor` values like `"Mehrzad Dadras, Design
Manager"`, never validated against any account) that reusing `actor`
would have been a real spoofing vector. `owner` is sourced from
`session['username']` at both real call sites, never user-suppliable
form data -- verified through the real `/upload` route with a
deliberately mismatched `actor` field to prove the two stay separate.

**Legacy-project backfill, deterministic only.** A pre-P32 project's
own first `document_ingested` event's `actor` is checked for an EXACT
match against a real `models.User.username`. Checked against this
repository's own real local `instance/registry/` data: 3 of 6 existing
projects were ingested by the real `workspacetester` account
(backfillable); the other 3 have free-text actors (`"agent1"`,
`"agent2"`, a human display name) with no matching account and stay
unowned/admin-only rather than guessed.

**A real, pre-existing, unrelated defect surfaced, not introduced, by
this stage's own verification.** At least one project in this
repository's actual local `instance/registry/` has an on-disk workspace
JSON with a `'reviews'` key `ProjectWorkspace(**data)` no longer
accepts -- invisible before this stage because nothing previously
iterated every project's workspace on every page load. `app.py` and
`routes/portal.py`'s new listing-filter code now fail closed (exclude,
don't crash) on this, restoring `_nav_recent_projects`'s own pre-
existing defensive-degradation guarantee, which a first pass at the
filtering fix had briefly dropped before the full suite caught it.

**Manual two-user, two-project isolation check: passed.** Reproduced
live (not only via the automated suite): two real sessions, two real
projects, direct HTTP requests -- owner opens their own project (200),
a second unauthorized user is denied (404) on the workspace page, the
API, and export; the same denial applies to a directly guessed real
`project_id`; grant/revoke toggles access live; admin opens both
regardless of ownership.

**Deliberately not built this stage:** separate read/write project-
level permissions (the existing `admin`/`read_only` role axis is
unchanged and still governs in-project actions -- exceeding this would
have gone beyond the bounded objective); any `services/case_workspace.py`
decomposition (P32's own additions were kept as small, clearly-tagged
insertions specifically so a future decomposition isn't made harder);
an ownership-transfer UI beyond the existing admin reassignment route;
anything resembling `Organization`/`OrganizationMembership` (still
unimplemented, still a distinct future stage).

**Security claims boundary.** Now supportable: "authenticated project
access is restricted to explicitly authorized users within this
deployment." Still not claimed: multi-organization tenant isolation,
complete organization isolation -- unchanged from CLAUDE-P31's
`SECURITY_CLAIMS_REGISTRY`, this stage added no new claim rows, only
made the existing "project authorization vs. tenancy" distinction
concretely true in code rather than aspirational.

---

## 2026-07-30 — CLAUDE-P31: organizational security and information governance (bounded foundation)

**Commits:** `7aa1bea` (domain/service-layer security governance foundation),
`16056dd` (external-AI + export enforcement wiring), `8114c2e` (Security
Department routes/UI), `edacee0` (80 new tests), `d577f29` (governance
amendment + MANIFEST). Full suite: 973 passed, 0 failed (893 from
CLAUDE-P30 + 80 new across five new test files).

**What was built.** A real, bounded, tested foundation for the eighteen
completion-condition questions this stage posed — not enterprise theatre.
`services/security_policy.py`'s `evaluate_action` is the single centralized
resolver: mandatory floor → organization baseline → project security
profile → exception, most-restrictive-wins, an exception's loosening
structurally capped at `DECISION_ALLOW`. The floor is unweakenable
because there is no governed action anywhere in `GOVERNED_ACTIONS` for
disabling authentication/CSRF/rate-limiting/audit — not a runtime check
that could be bypassed. `INFORMATION_CLASSIFICATIONS` (standard/
confidential/restricted/highly_restricted) each resolve to an explicit
control bundle (`CLASSIFICATION_PROFILE_DECISIONS`), never a bare label.

**Honesty boundary, load-bearing for the whole stage:** this repository
has no multi-organization/tenancy model (`specified-unbuilt/tenancy-
and-project-authorization.md` remains unimplemented). `services/
security_governance.py`'s `SecurityGovernanceStore` therefore manages
**one global, deployment-wide record** — every "organization baseline"
in this codebase today means one shared configuration, never an
isolated per-customer one. Stated directly in the module's own
docstring, and in `SECURITY_CLAIMS_REGISTRY` (`"multi-organization
tenant isolation"` = `specified_but_unbuilt`, `"complete organization
isolation"` = `prohibited_from_claiming`), not left implicit anywhere.

**Policy ingestion and provenance.** `SourcePolicy` → `PolicyStatement`
→ `ProposedControl` → governed `QAEntry` (6-state authority model) →
`BaselineVersion` (draft → under_review → approved → active →
superseded/withdrawn, `acknowledge_capability_impact` required before
`activate_baseline` will accept it) preserves "Original Written Policy
≠ Machine Interpretation ≠ Proposed Application Controls ≠ Ratified
Executable Security Baseline" end to end — every control decision
carries required source provenance, never disguising an ARCHIOSK
recommendation as a customer policy requirement. Deliberately **no
AI-assisted extraction** this stage — statements/proposals are
human-entered only, extending this codebase's standing caution about
`services/bhive_parser.py`'s fragile prompts to "write no new prompt at
all" for this pipeline rather than a narrower gate.

**Real enforcement, at two representative points.** `services/
ingestion.py` evaluates `external_ai_request` before every new
project's classification and wires the decision straight into
`BHiveParser`'s own pre-existing, already-tested `ai_calls_disabled`
kill switch (CLAUDE-P27-B) — zero lines changed inside
`bhive_parser.py` itself. `routes/workspace.py` gates `export` on both
RFI export routes, consulting the project's own `security_profile`
alongside the active baseline, naming the controlling policy layer in
its denial message. A `security_decision` audit event is recorded for
every ingestion-time evaluation regardless of outcome.

**Learning boundaries, honestly scoped.** `services/
learning_governance.py`'s `LearningContributionRequest` models the
three zones and a required five-stage review sequence before approval
(self-approval prohibited for shared-improvement targets) — but **moves
zero data**, because no shared-learning/training pipeline exists
anywhere in this repository to move data into. Confirmed both
structurally (no import edge to/from `case_workspace.py`'s quality
machinery) and behaviorally (a "Correct" `ReviewerValidation` creates no
contribution request).

**Assurance, activity-level only.** `services/security_assurance.py`'s
`aggregate_security_activity` is a pure read-side aggregation over every
project's existing `GovernanceLog` — no new audit substrate. Content-
level inspection remains impossible through this mechanism structurally
(no field on `SecurityActivityEntry` could hold project content), not
merely policy-forbidden. `run_security_self_check` independently
re-verifies five invariants rather than trusting their own writers.
Honesty maintained explicitly: `GovernanceLog`'s append-only guarantee
is by convention, not cryptographic — `"tamper-proof logs"` is
`prohibited_from_claiming`, stated plainly rather than omitted.

**Workspace.** `routes/security.py` + `templates/security_department.html`
— admin-only (no dedicated Security Officer role exists yet), reachable
via a new nav link in `templates/base.html`.

**Verification.** 80 new tests. One real incident during this stage: an
early draft of `tests/test_security_enforcement.py` called
`ingest_upload` directly (not through a parse-spy) in several tests, and
one full-suite run took **8.5 hours** because that path made a live,
apparently-hung Anthropic API call in this sandbox. Fixed by routing
every ingestion call in every new P31 test file through a `BHiveParser.
parse` spy that never invokes the real classify/consistency-check
pipeline — confirmed fully hermetic afterward (full suite back to ~193s).
This was a test-authoring mistake in this stage's own new files, not a
defect in `services/ingestion.py`'s actual (correct) security-gate logic,
which the spy-based tests verify directly.

**Independent critique (required section), key findings:** "Security
Department" was kept as the product term (matches the user's own
prompt framing; no better repository-grounded alternative surfaced).
Security and information governance were kept as one workspace, not
split — the volume of real content (policy/Q&A/baseline/assurance)
didn't yet justify two surfaces. The repository genuinely cannot support
*organization-level* policy before tenancy — hence the single-
deployment scoping stated everywhere above. Audit visibility was kept
strictly activity-level specifically to avoid the employee-surveillance
risk the prompt itself named — security administrators do **not** see
content by default, and no route exists to change that this stage.
Strongest-rule-wins was kept as the precedence model; a security
administrator CAN create exceptions (the only loosening path, capped at
`DECISION_ALLOW`); policy changes take effect only at explicit baseline
activation (an `effective_date`), never immediately on Q&A/statement
entry alone.

**Remaining hard-stop-adjacent items, none blocking, all explicitly
out of scope for this stage per its own instructions:** no tenancy
migration was performed or attempted; no legal/regulatory obligation
was invented (the model has a place — `SourcePolicy.jurisdiction`/
`approving_authority` — for an externally-established one to be
recorded, nothing more); no technical security property was promised
that the current system cannot enforce (`SECURITY_CLAIMS_REGISTRY` is
the explicit record of this); no irreversible security-policy
transformation occurred without rollback (baseline supersession
preserves every prior version, never deletes).

---

## 2026-07-30 — CLAUDE-P30: environment capability architecture + contractual tool directionality

**Commits:** `e5a494f` (domain/service layer -- capability grammar, RFI
directionality, Go/No-Go), `e9a1e12` (route/template/UI wiring), `d1490dd`
(39 new tests), `28b2f75` (governance + MANIFEST update). Full suite: 893
passed, 0 failed (854 from CLAUDE-P29 + 39 new in
`tests/test_capability_architecture.py`).

**What was built.** The locked Project Operating Environment (CLAUDE-P29)
went from "one gated field" (participant-role selection) to an actual
capability architecture with two representative, genuinely-enforced
environment-specific workflows.

**Centralized resolution, not scattered branches.** `services/
environment_capabilities.py` gained `CAPABILITY_REGISTRY` (a plain dict of
small `CapabilityDefinition` entries — deliberately not a plugin framework)
classified into a 7-value grammar (`CAPABILITY_NEUTRAL`/`_COUNTERPART`/
`_PARALLEL`/`_CLIENT_ONLY`/`_PROPONENT_ONLY`/`_COMPARATIVE_BOUNDED`/
`_FUTURE_NOT_AUTHORIZED`). `capability_availability`/`capability_denial_
reason` are the single functions every route/template/export calls into —
`routes/workspace.py`'s new `_require_capability` helper (mirrors the
existing `_require_visible_case` shape) is the one enforcement point for
routes. A legacy/unclassified project (`operating_environment is None`) is
ungated for every capability except `CAPABILITY_FUTURE_NOT_AUTHORIZED`,
matching P29's own `allowed_participant_roles` precedent — **except**
Go/No-Go, which has no sensible fallback vocabulary and is a hard refusal
for an unclassified project (a deliberate, tested exception, not an
inconsistency).

**RFI/clarification directionality.** `rfi_originate` (Design-Builder/
Proponent — draft, revise, issue) and `rfi_respond` (Client/Owner — record
the authoritative response to an issued RFI) are registered as
`CAPABILITY_COUNTERPART`, not a bare exclusive label, because each has a
real counterpart on the other side. `RFIDraft` gained `response_text`/
`responded_at`/`responded_by` and a new terminal status,
`RFI_STATUS_ANSWERED`; `CaseWorkspaceStore.respond_to_rfi_draft` requires
`RFI_STATUS_ISSUED` first (a response follows issuance) and refuses a
second response, the same one-way-transition shape `issue_rfi_draft`
already used. Both RFI exporters (`build_rfi_docx`/`build_rfi_draft_docx`)
now stamp workflow direction; `routes/api.py`'s own RFI export was
unstamped as a CLAUDE-P29-noted scope limitation and is now stamped too.

**Go/No-Go — one shared record, two genuinely different vocabularies.** New
primitive `GoNoGoAssessment` (`workspace.go_no_go_assessments`):
`CaseWorkspaceStore.record_go_no_go_decision` validates `decision_stage`
against whichever of `CLIENT_OWNER_DECISION_STAGES` (procurement-oriented:
release RFQ/RFP, shortlist, award, ...) or `DESIGN_BUILDER_PROPONENT_
DECISION_STAGES` (pursuit-oriented: bid, accept commercial terms, submit
final proposal, ...) applies to the project's own locked environment — a
Client project attempting a Proponent-only stage is rejected at both the
route and service layers (tested). `decision` itself (`go`/`no_go`/
`conditional_go`) is closed and shared; `anomalies` is open-world free
text, deliberately not a closed enum (the list of things that could
justify a No-Go is large, environment-specific, and expected to grow).

**Reviewer-perspective boundary confirmed, not newly built.**
`capability_availability` takes only `operating_environment` as an
argument — `represented_party_by`, session role, and Case visibility are
structurally incapable of reaching it. Tested directly: representing a
Design-Builder participant inside a Client/Owner project does not unlock
RFI origination.

**Deliberately not done this stage, and why.** No `services/bhive_parser.py`
prompt received `operating_environment` context — documented as a
deliberate deferral (not an oversight) in `environment_capabilities.py`'s
own module docstring, consistent with this codebase's standing multi-
session caution around that module's adversarially-tuned prompts. No
`CAPABILITY_CLIENT_ONLY`/`CAPABILITY_PROPONENT_ONLY` registry entries were
registered — every genuinely single-sided capability found on inspection
had a real counterpart, so `CAPABILITY_COUNTERPART` was the honest
classification instead of manufacturing a bare "exclusive" label. No third
Operating Environment value, no multi-tenancy, no organizational security
architecture (explicitly reserved for a separate future stage per the
user's own instruction).

**Independent critique (Part XI), recorded findings:** the current RFI
exchange happens within a single project's own `workspace.rfi_drafts` list
— origination and response are two capability-gated actions on the *same*
record inside the *same* project, not a real cross-organization document
exchange between two separate projects/tenants. This is an honest
simplification consistent with "tenancy remains designed but unimplemented"
(unchanged this stage) — a true two-party RFI exchange (Proponent's project
sends, Client's separate project receives) is blocked on tenancy, not on
anything this stage could resolve alone, and is flagged as a real
architectural gap for whichever future stage takes up cross-project/
cross-tenant document exchange.

---

## 2026-07-30 — CLAUDE-P29: locked Project Operating Environment types

**Commits:** `d339d1c` (domain/service layer), `02a3ed3` (route/template/UI
wiring), `486d61f` (29 new tests + P28 test-file fixup), `d684e80`
(governance amendment + MANIFEST.md). Full suite: 854 passed, 0 failed.

**What was built.** A locked, immutable, project-creation-time
classification — Client/Owner vs. Design-Builder/Proponent — answering
"which side of a procurement/delivery relationship is this project's
*workspace itself* structurally configured to serve." `services/
environment_capabilities.py` (new): a closed two-value enum, a strict
validator (`is_valid_operating_environment` — rejects rather than
open-world-preserves an unrecognized value, a deliberate deviation from
this codebase's dominant `normalize_open_world_value` pattern, since a
closed/gated field needs the opposite shape), and one concrete capability
mapping (`allowed_participant_roles`). `ProjectWorkspace.operating_
environment`/`_set_by`/`_set_at` (new fields, default `None`).
`CaseWorkspaceStore.set_operating_environment` is the single write gate
for the field — raises the new `OperatingEnvironmentAlreadySetError` on
any second call, so there is exactly one place immutability could fail,
and it's tested directly at both the service and route layers (direct
call, forged route submission, same-value resubmission).

**Explicitly distinct from the existing Perspective mechanisms, not a
reopening of CLAUDE-P28's finding.** `represented_party_by`/
`PerspectiveAssessment` (CLAUDE-P12R/P17) is mutable, per-reviewer, and
answers "whose eyes am I reading this Finding through today" — untouched
by this stage, confirmed by test (`RoleAndPerspectiveIndependenceTests`)
that neither it nor a reviewer's session role can reach `operating_
environment`. The governed, still-**NOT AUTHORIZED** "Perspective"
object in `governance/specified-unbuilt/perspective-and-contract-
dna.md` remains not authorized — this stage's user-provided reasoning
for why Operating Environment is a *different*, narrower, bounded
concept (immutable/project-wide/creation-time vs. mutable/per-reviewer/
default-emphasis-only) was independently evaluated and accepted as
substantively sound, not just a rationalization, and is recorded as such
in `governance/STATUS.md`'s new authorization row — which explicitly
does not touch the pre-existing Perspective/Contract-DNA NOT AUTHORIZED
row directly above it.

**Creation path.** `ingest_upload()` now requires `operating_environment`
(no default — same "no inference path" discipline as `promote_
requirement_item`'s `source_id`), validated before any parsing begins;
the `ProjectWorkspace` is now always created eagerly (previously only
when `project_name` was given) so the environment locks atomically at
project birth — no project can transiently exist unclassified.
`templates/gateway.html` offers two creation entrances instead of one
generic card; `templates/upload.html` requires an explicit environment
selection (server-side allowlist is the real enforcement; the UI
checkbox is cosmetic).

**Legacy projects.** A pre-P29 workspace loads with `operating_
environment=None` — never inferred or backfilled. `routes/workspace.py`'s
new `classify_operating_environment` (`@admin_required`, matching the
authority level of project creation itself) is the one-time path to
establish it, through the identical write gate — refused the same way
on any second attempt. `allowed_participant_roles(None)` returns `None`
(no gating), so every pre-existing legacy project's Participant
functionality is unchanged until explicitly classified.

**Environment-dependent behavior, kept narrow.** The one implemented
differentiation is which `Participant.role_type` values are selectable
per locked environment (`register_participant_route`). No new AI-prompt
content was written — `services/bhive_parser.py`'s adversarially-tuned
prompts were deliberately left untouched, consistent with this
project's standing caution around that module. RFI export
(`build_rfi_docx`/`build_rfi_draft_docx`) stamps the environment label
when available; `routes/api.py`'s own RFI export route was deliberately
left unstamped this stage (no `CaseWorkspaceStore` access there — an
explicit, noted scope limitation, not an oversight).

**Deferred, not done this stage:** general environment-gated analysis
content, `routes/api.py` RFI-export environment stamping, and any
environment value beyond the two authorized here — all remain **NOT
AUTHORIZED** pending their own fresh authorization, per the new
`governance/STATUS.md` row.

---

## 2026-07-29 — CLAUDE-P28: project operating perspective + historical/forward-ingestion review

**Commit:** `295d148`. Full suite: 825 passed, 0 failed.

**Part I — the premise was significantly wrong; investigated and corrected, not implemented as asked.**
Repository-grounded investigation (not assumption) found: project
creation and document ingestion are the same atomic operation
(`services/ingestion.py`'s `ingest_upload()` — there is no separate
"New Project" step anywhere in the app, so several of the placement
options this stage was asked to evaluate don't match real architecture).
More importantly: a real, tested, working comparative-perspective
mechanism **already exists** — `Participant`/`PerspectiveAssessment`/
`ProjectWorkspace.represented_party_by` (`services/case_workspace.py`,
CLAUDE-P12R/P17), explicitly documented in its own code as *"a personal
setting... not a governed fact"*, per-reviewer and per-project, feeding
real perspective-aware analysis in
`services/requirement_investigation.py`, tested in
`tests/test_perspective_tier.py`. This already correctly separates
"comparative analytical perspective" from anything project-governing,
exactly the distinction this stage asked for.

What's actually missing — a **project-level governing** perspective
("whose interests this whole project is configured to serve", set
near creation, distinct from any one reviewer's personal setting) —
has **no code anywhere**, but also has an existing, ratified
specification: `governance/specified-unbuilt/perspective-and-contract-
dna.md`'s "Create-Project/Pursuit UX flow" (Perspective as step 2),
with an explicit guardrail that Perspective *"must never be stored as
a field on governed data... first-class only at the
application/authorization layer."* `governance/STATUS.md`'s
authorization table marks this whole layer **NOT AUTHORIZED — specified
only**. Implementing the governed version this stage's prompt described
would mean building something this repository's own governance process
has explicitly withheld authorization for — the same situation as the
tenancy design work in CLAUDE-P27-B, handled the same way: documented,
not implemented, pending a deliberate ratification act this session
doesn't have standing to perform on the user's behalf. No new UI was
added either — the existing "not represented yet" messaging
(`templates/case_workspace.html`) was found adequate on inspection, not
worth adding a redundant banner alongside.

**Part II — several claimed historical-data gaps do not exist; the
premise (a body of legacy data needing an advancement pipeline) does
not match repository reality.** `tests/fixtures/nreocrc/` is a
synthetic QA/capability-probe lab (same category as `tests/self_test/`),
not historical customer data. Cedar Harbour is the one real local
project and it's already on the current schema (its `workspace.json`
already has `represented_party_by`/`perspective_assessments` as native
keys). Specific claimed gaps checked directly against code and lab
records: Markdown support — **resolved**
(`services/bhive_parser.py`, code comment cites and resolves the exact
concern); table-aware segmentation — **implemented and current**
("Batch H", contradicts the claim it's absent); OPR-1 Row 20 — **already
resolved**, independently re-confirmed in the lab's own adversarial
comparison; `expected_provider` null — **not a defect**, just an unset
optional field in a test script. One claimed gap **is** real and still
open, confirmed directly against the lab record: **Row 14 ↔ 5.3
cross-reference is missed** by the generic detector's design (only
inspects a row's Notes column when Security Level also contains "/").
Deliberately **not fixed this session** — this is the same fragile,
adversarially-tuned consistency-check code this whole extended session
has treated with extreme caution (CLAUDE-P16/P22/P23/P25/P26's own
history shows small changes here need dedicated golden-suite validation,
not a same-session fix folded into an unrelated stage). "Restricted
Communications Sub-Zone" — searched, present in source material, not
flagged as a gap anywhere in the lab's own exhaustive adversarial
review; no evidence of a missed relationship.

Given no concrete body of historical data actually needs migration
right now, a full speculative historical-advancement pipeline
(compatibility classes, quarantine states, lifecycle machinery) was
**not built** — this would be exactly the kind of premature complexity
`tools/dependency_fit.py`'s stance and this repository's demonstrated
practice (see the tenancy precedent again) argue against building
before a real admission queue exists.

**What was implemented** (`295d148`, 6 new tests, all bounded and
directly evidence-justified): `BHIVE_PARSER_VERSION` stamped on every
new `ParsedDocument` (a confirmed real gap — nothing was ever
versioned), following this file's own existing
`CONSISTENCY_PROMPT_VERSION`/`INVESTIGATION_PROMPT_VERSION` convention;
duplicate-content detection using `original_file_hash` (already
computed on every ingestion, never actually checked against anything
until now) — informational only, recorded in the governance log, not a
hard block; the first dedicated test for `_reject_if_name_taken`
(confirmed real and enforced, previously untested).

**Next stage entry point:** none of this blocks anything. The tenancy
design package remains the natural next stage pending its four open
product decisions (unchanged from CLAUDE-P27-D). If perspective work is
wanted next, the actual next step is a deliberate authorization
decision on `governance/specified-unbuilt/perspective-and-contract-
dna.md` (the same kind of decision the four tenancy questions need),
not further investigation — the investigation is complete.

---

## 2026-07-29 — CLAUDE-P27-D: system of record and AI collaboration route

Governance/collaboration stage, not further hardening — no runtime code
changed. Established, in `CLAUDE.md`'s new "System of record and AI
collaboration route" section (read it there for the full model, not
duplicated here): pushed `origin/main` is the authoritative durable
record for everything except `.env`/secrets (never in git, by design)
and the sibling `archiosk-explorer` repo's own governance corpus
(cross-referenced, never duplicated); conversational AI output
(including this session, and external tools like ChatGPT) is
provisional until it lands in a pushed commit; `governance/constitutional-
invariants.md`'s authority is scoped to the BEEHIVE domain-object model
only, not infrastructure/security, where current tested code on `main`
governs instead; direct-to-`main` commits (no feature branches/PRs/
issues) remain the right model at this project's current scale, revisit
if a second human contributor joins.

Also fixed, as directly in-scope for "system of record integrity":
`MANIFEST.md` had gone stale during the P27-B session (20 new files
never catalogued) and, separately, already contained a now-materially-
false claim predating this session (`routes/api.py` "unaffected"/"out
of scope" for auth — false since commit `c2db13f`) — both corrected.
`MANIFEST.md` also flags, but does not attempt to fix, a much larger
pre-existing staleness (it predates the multi-user auth system and the
entire Case Workspace subsystem) as separate future work.

**Next stage entry point (CLAUDE-P28):** per this checkpoint's own P27-B
section below, the tenancy design package
(`governance/specified-unbuilt/tenancy-and-project-authorization.md`)
is implementation-ready pending its four open product decisions — that
remains the most natural next stage if no other priority intervenes.

---

## 2026-07-29 — CLAUDE-P27/P27-A/P27-B: security review, Hardened Starter Baseline, SMTP finalization

Supersedes the CaseWorkspaceStore-era section below as the current state
summary; that section is retained unmodified as historical record, not
because it's still current.

**Current commit state:** local `HEAD` and `origin/main` both at `279dd8a`,
in sync, working tree clean except the pre-existing untracked
`tests/fixtures/nreocrc/_lab_instance_scratch_002/`. Full test suite: 819
passed, 0 failed as of the last full run this session.

**CLAUDE-P27** — full repository-grounded security/architecture review
(five parallel read-only inspection forks: identity/auth, tenant/
authorization/IDOR, storage/Snapshot, self-protection/AI, deployment/
audit/tests). Found the repository had no project-level tenancy/
authorization model (any authenticated user could open any project) and a
fully unauthenticated `/api/v1/*` JSON API. **CLAUDE-P27-A** restructured
the findings around natural continuation + a named Hardened Starter
Baseline rather than jumping straight to beta/subscription features.

**CLAUDE-P27-B** — the Hardened Starter Baseline, implemented as 10
reviewed, tested, individually-committed blocks (`c2db13f` through
`adccbd6`, see `git log --oneline bfa99d7..adccbd6` for the full list):
`/api/v1` authentication, a tenancy/project-authorization **design
package** (`governance/specified-unbuilt/tenancy-and-project-
authorization.md` — specified, deliberately **not implemented**, four
open product decisions block execution), `BaseConfig.validate()` boot
enforcement, `User.is_active` + suspension, security-event logging,
`ProxyFix`, rate limiting (Flask-Limiter), CSRF protection (Flask-WTF),
a prompt-injection boundary + AI kill switch in `services/bhive_parser.py`,
backup/restore tooling (a real backup + verified restore drill was run
against live data during the session), and Flask-Migrate/Alembic
adoption for the next schema change (the live database was `stamp`-ed to
the new baseline revision, not migrated through it).

**SMTP finalization (commit `279dd8a` for the credential-independent
code; real delivery verified live, not via a commit):**
- Implicit-TLS (`SMTP_USE_SSL`, `smtplib.SMTP_SSL`) support added
  alongside the pre-existing STARTTLS path in `services/email.py` —
  previously only STARTTLS existed at all.
- Boot-time SMTP configuration warnings added to `app.py`'s existing
  production validation (never hard-fails, matching the graceful-
  degradation philosophy already established for `ANTHROPIC_API_KEY`).
- Verified structurally that no reset token/URL is ever logged outside
  the dev-only fallback.
- **Real end-to-end delivery to `architect@rogers.com` via Netfirms is
  now fully verified**: SMTP connects, authenticates, and delivers;
  the reset link worked once and was correctly rejected on reuse; the
  dev-only fallback did not fire; no token or secret was exposed in
  the process (one earlier mistake mid-session — a dev-fallback-logged
  token was briefly echoed into the conversation transcript during
  diagnosis — was caught, the token was immediately invalidated via a
  direct DB write, and the log file was scrubbed; no repository
  content was affected).
- Working production config: `SMTP_HOST=smtp.netfirms.com`,
  `SMTP_PORT=465`, implicit SSL (`SMTP_USE_SSL=true`,
  `SMTP_USE_TLS=false`), full mailbox address as `SMTP_USERNAME`. The
  mailbox password required one reset on Netfirms' side before AUTH
  would succeed — the original password authenticated fine via
  webmail/IMAP but was rejected (clean SMTP `535`, not a connection
  drop) specifically for SMTP AUTH; resetting it resolved this.
- **Netfirms support case E-567913**: opened during diagnosis (the
  earlier STARTTLS/implicit-SSL AUTH-disconnect investigation surfaced
  a genuine, independently-confirmed TLS certificate hostname mismatch
  for `smtp.netfirms.com`, reported to Netfirms alongside the AUTH
  symptom). **Status: open, kept open only until Netfirms support
  confirms or closes it.** Whoever closes it should note: the
  practical blocking issue (SMTP AUTH rejection) was resolved by
  resetting the mailbox password, not by a Netfirms-side change — the
  certificate hostname-mismatch finding is a separate, still-
  unconfirmed report to Netfirms and may still be worth their fixing
  independent of this case's resolution.

**Not started this session, explicitly deferred, no new authorization
implied:** tenancy migration execution, `Invitation`/entitlement/
subscription models, further `CaseWorkspaceStore` route wiring (per
P27-A's own reasoning: wiring more routes before the tenancy work lands
would just add more surface inheriting the same still-open isolation
gap), dependency version-staleness remediation.

**Recommended next prompt**, if none of the above is what's wanted next:
resolve the four open product decisions in
`governance/specified-unbuilt/tenancy-and-project-authorization.md`
(personal-org default, project-to-org cardinality, project-name
uniqueness scope, admin-bypass semantics) — that design package is
otherwise implementation-ready.

---

## Historical: CaseWorkspaceStore backlog checkpoint (superseded above)

Written on explicit request, after a read-only investigation into the
`CaseWorkspaceStore` backlog item. **Not committed or pushed** — this file
is currently untracked, left for the user to review/commit/discard as they
choose. Session was stopped here deliberately so it can be cleared.

## Current commit state

- Local `HEAD`: `a79adf489c841c43b21f4e9e0dea53ad38b6c833`
- `origin/main`: `a79adf489c841c43b21f4e9e0dea53ad38b6c833`
- Both in sync. Working tree clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` directory, present
  since before this session started.

## P25 / P26 results (recap)

**CLAUDE-P25 — commit `686eaa2`.** Root cause: the consistency investigator
could focus on differing numeric thresholds while failing to credit
explicit temporal/operational/spatial/conditional scope stated *within* the
same two clauses — isolated to **clause density** (a long clause bundling a
numeric obligation with a protocol/condition description), not any one
scope dimension. Fix: `ConsistencyFlag` gained `requirement_a/b_obligation`,
`requirement_a/b_scope`, `scopes_overlap`, `scope_reconciliation_reasoning`;
prompt requires an explicit 4-step scope check; `_check_consistency`
deterministically drops any flag lacking scope reasoning or whose own
`scopes_overlap=False` contradicts inclusion. Results: 38/39 on the full
scope-reconciliation matrix post-fix; Golden Suite 30/31 clean (1 transient,
unrelated model-call error); full pytest 706 passed.

**CLAUDE-P26 — commit `833187c`.** Investigated P25's own recheck runs
showing ~50% malformed output specifically on the isolated two-clause
condition (valid JSON, then self-correction prose, sometimes a second,
differing JSON array). Did not reproduce in a fresh 57-call sample, but
real evidence from P25 confirms it happens intermittently. Tested and
**rejected** Anthropic tool-use (schema-enforced structured output) as a
fix: it fixed formatting 100% but got the one genuinely hard specimen wrong
3/6 times (each miss a bare ~33-token "no conflict" call vs. ~700–800
tokens of real reasoning in every correct run) — forcing structured output
let the model skip its own reasoning on the hard case. Adopted fix:
parsing-only, no new model-call shape. `services/consistency_response_
parser.py` classifies a response into 7 categories; the first four (single
valid JSON / valid JSON + harmless prose / multiple equivalent blocks /
malformed-but-repairable) are accepted immediately; only a genuinely
unresolvable response (conflicting blocks, or unusable) triggers exactly
one bounded retry before falling back to the prior graceful skip. Results:
real rerun of the exact previously-failing condition — 6/6 valid, all
correctly clean (2 recovered via the bounded retry). Full pytest 730
passed. Golden Suite fully clean (0 malformed, 0 false positives, 0
did-not-run).

**Candidate `276cac42` (aquatic-centre):** still quarantined, not promoted.
Clean baseline improved across both fixes (7/10 false positives in P24 →
0/8 after P25 → 6/6 correctly clean after P26), but per standing
instruction this is not grounds for promotion on its own.

Full detail: `tests/self_test/CHECKPOINT.md` (committed at `a79adf4`).

## Contents of commit a79adf4

One file changed vs. its parent `833187c`: `tests/self_test/CHECKPOINT.md`,
96 insertions, 0 deletions (pure addition). Commit message: "Add P25/P26
continuation checkpoint for the self-test regression lab" — concise
handoff covering `686eaa2` and `833187c`: what each found, what was fixed,
test results, the aquatic-centre candidate's still-quarantined status, and
the queued `CaseWorkspaceStore` backlog item (not started at that point).

## CaseWorkspaceStore backlog — read-only inventory (this session)

Produced by a forked, read-only investigation cross-referencing every
public method in `services/case_workspace.py` against `routes/workspace.py`,
the two intermediary services that also call into the store on already-
reachable production paths (`services/conversation_interpreter.py`,
`services/project_clock.py`), and `governance/STATUS.md`/`kernel-object-
model.md`'s authorization table. No code was written or changed.

The user's five requested categories don't cover every case found —
several subsystems are simply unwired, tested, and authorized with no
blocking concern. That's called out below as an extra, unrequested bucket
rather than force-fit into one of the five.

### 1. Genuinely required by current routes (not actually a gap)
Reachable today via `conversation_interpreter.interpret_message` (called
from `routes/workspace.py:1580`) or `project_clock.open_project` (called
from `routes/workspace.py:262`): `record_analysis`,
`can_open_autonomous_case_for`, `create_autonomous_case`,
`current_requirement_for`, `record_investigation_step`,
`requirement_predecessor`, `corrections_for_case`.

### 2. Intentionally dormant / future-facing
- `record_supersession`, `supersessions_for` — own docstring: "reserved for
  Experience/Knowledge revision," only used internally today.
- `record_activity` — zero callers anywhere (test or production), excluded
  from the collaboration-threshold set pending an authorship-convention
  decision that hasn't been made.

### 3. Duplicate or superseded
- `requirements_for_source` (→ `requirements_for_project`)
- `latest_requirement_adjudication_for` (→ `requirement_adjudication_state`)
- `case_outcomes_for`, `latest_case_outcome_for` (→ `case_outcome_state`)
- `dispositions_for_finding` (→ `latest_disposition`)
- `perspective_assessments_for_anchor` (→ `perspective_convergence_for`)
- `set_review_thread_status` (internal helper behind `resolve_review_thread`
  / `reopen_review_thread`)

### 4. Unsafe or unauthorized to expose
- `update_source_identity` — real write method, **zero test coverage found
  anywhere** in the suite. Wiring a route to it would be the first real
  exercise of this code path in production.

(Nothing found corresponds to a `governance/STATUS.md` **NOT AUTHORIZED**
item — those have no store methods written at all yet. No conflict between
this inventory and the authorization table.)

### 5. Uncertain and requiring architectural review
- `confirm_relationship` — `kernel-object-model.md` flags a known
  consistency gap (in-place mutation, not append-only). Wiring a route now
  would surface that gap to real users rather than resolve it first.
- `record_relationship` — standalone write entry point; unclear whether
  it's meant to be human-invoked or stay machine/internal-only.
- `link_thread_outcome` — combines thread-resolution + relationship-
  confirmation; needs a UX decision, and inherits `confirm_relationship`'s
  open question.
- `revise_temporal_obligation` — write path with no route; unlike
  `create_temporal_obligation` (wired), its revision/authority semantics at
  the route layer haven't been decided.

### 6. (Unrequested bucket) Ready to wire — tested, authorized, no blocker
- **Structured Tabular Evidence + Source-Reference resolution** (Foundation
  Batch J, newest subsystem): `register_table_evidence`,
  `tables_for_source`, `get_table`, `rows_for_table`, `get_table_row`,
  `resolve_table_cell`, `reconcile_table`,
  `extract_and_register_source_references`, `source_references_for_source`,
  `get_source_reference`, `source_references_to_target`. Well-tested
  (`tests/test_foundation_batch_j.py`); zero route or trigger point
  anywhere — even the write side isn't invoked during ingestion today.
- **Snapshot read-side** (write side `create_snapshot` already wired):
  `snapshots_for_project`, `get_snapshot`, `resolve_snapshot_objects`,
  `compare_snapshots`. A Snapshot can be created but never listed, opened,
  or diffed.
- **Expected Information Profile** (whole subsystem unwired):
  `create_expected_information_profile`, `add_expectation_item`,
  `set_expectation_item_status`, `profiles_for_scope`,
  `profiles_for_project`, `revise_expected_information_profile`. Tested in
  `test_foundation_batch_e.py`.
- **Design/Estimate Maturity** (whole subsystem unwired):
  `record_design_maturity`, `record_estimate_maturity`, `maturity_for_scope`,
  `revise_maturity`. Tested in `test_foundation_batch_e.py`.
- `set_requirement_status` — real write path, hard denylist against
  compliance-shaped values, IMPLEMENTED per `STATUS.md`. No route today.
- `derived_cases_of`, `carried_forward_adoptions_for_case` — read-only
  reverse-lookup queries behind already-wired, tested writes; lineage can't
  currently be displayed.
- `threads_for_project`, `threads_for_anchor` — low-priority read-side gaps.

### Smallest coherent wiring seams (identified, NOT implemented)
1. **Snapshot listing + compare** — smallest true seam; zero new write
   logic, purely additive read-side display, no architectural ambiguity.
2. **`set_requirement_status` route** — one small write route, directly
   analogous to already-wired patterns (`share_case`/`archive_case`).
3. **Foundation Batch J display** — larger seam; even the write side has no
   current trigger point, so wiring it coherently means first deciding
   where those writes should fire (ingestion pipeline vs. a manual action).

## Unresolved decisions
- Which wiring seam to start with first, if any (Snapshot read-side,
  `set_requirement_status`, Batch J, or Expected Info Profile/Maturity).
- Whether `confirm_relationship`'s known append-only gap should be fixed
  before any route wiring, or documented as an accepted limitation.
- Whether `update_source_identity` needs tests written first, independent
  of any route-wiring decision.
- Whether `record_activity`'s authorship convention should be decided now
  or left dormant.
- `governance/current/kernel-object-model.md` is stale (self-reports 393
  tests; suite is now 730) — separate documentation-debt observation, not
  acted on here.

## Recommended next prompt
"Wire the Snapshot read-side (list/open/compare) as the first
CaseWorkspaceStore seam: smallest, zero write-path risk, existing create
route already live." (Alternatives: `set_requirement_status`, or Expected
Information Profile if a larger single subsystem is preferred first.)
