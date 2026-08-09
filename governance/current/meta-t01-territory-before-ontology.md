# Territory Before Ontology / Project-Workspace Metamorphosis (CLAUDE-POSTCAMEL-META-T01)

**Status: TERRITORY BEFORE ONTOLOGY ESTABLISHED — TARGETED
RECOMMISSIONING REQUIRED.** Authorized by the Product Owner's own
disposition of COMM-CONTINUE-01 (OPR-7.2 confirmed Partially
Satisfied, not accepted as a residual, Substantial Completion held
pending genuine representative-user validation — deliberately deferred
until **after** this metamorphosis, so that validation reflects the
product intended for actual pilot use) and a new Product Owner design
direction: **Territory Before Ontology** — *"First show me what I
already have. Then show me what ARCHIOSK knows about it,"* and
*"ARCHIOSK does not ask the project to move into ARCHIOSK. ARCHIOSK
enters the project."*

This stage makes bounded, repository-grounded copy and template
changes establishing this principle where the current product actually
violated it — it does not rewrite the workbench, does not fabricate
folder hierarchy that doesn't exist, and does not declare the outstanding
OPR-7.2 test satisfied.

---

## A. Verified starting state

`HEAD == origin/main == 2ea9b494bd78c1ee3d81a784e7937b07c28a073c`
confirmed directly before this stage began; working tree clean except
the pre-existing untracked `tests/fixtures/nreocrc/_lab_instance_scratch_002/`
fixture.

## B. Current workspace mental model discovered

Read directly, not assumed: a brand-new project's actual first screen
(`/upload` → `/workspace/briefing/preparing` → `?view=overview`, the
real, confirmed redirect chain) opened with **zero mention of the
reviewer's own registered material anywhere on the page.** Overview's
own accordion order, read top to bottom exactly as rendered: Project
Operating Environment/Access → Project Management & Settings → Needs
Attention → Recent Focus → Investigation Quality → Participants →
Go/No-Go → Accepted Knowledge → Project Instructions → Requirements →
RFI Correspondence → Key Dates → History. Every one of these is either
administrative metadata or governed ARCHIOSK intelligence — none of
them answer "what files do I actually have here." A user would have to
separately think to click "Documents" or "Files" in the Lists sidebar
to see their own material at all. This is a direct, repository-grounded
confirmation of the gap the Product Owner's own design direction names.

## C. Current Project/Source/File architecture

Confirmed directly:

- **Project creation/opening**: `/upload` ingests exactly one founding
  document and creates a project; `ingest_upload` always generates a
  fresh UUID `project_id` (re-confirmed, already established in
  COMM-I4).
- **Source/file storage**: `Source.file_path` is an internally-
  controlled, UUID-prefixed path inside `instance/registry/workspace_sources/<project_id>/`
  — never the user's own original filesystem path. **No original
  external folder/path information has ever been captured anywhere in
  this codebase** — a browser file-picker upload gives ARCHIOSK a
  filename and bytes, never a directory structure. This was true before
  this stage and remains true after it; nothing was invented to imply
  otherwise.
- **Lists/Local Navigator**: the Lists sidebar (`base.html`) already
  lists "Documents" (a flat registered-Source list) and "Files"
  (`data-root-branch="2.2"`, the VW9 Data Room/Design-Builder Workspace
  split) as two separate branches — a real, pre-existing structural
  redundancy this stage did not introduce (see Section L).
- **Existing UI hierarchy honesty, better than assumed**: VW9's own
  `display.files` surface (Data Room / Design-Builder Workspace) was
  already carefully, honestly written **before** this stage — Data
  Room's own copy already said *"its real issued hierarchy is imported
  through a separate, deliberate, governed action, not yet part of this
  stage"* and *"No Documents yet. Documents added to this Project will
  appear here, honestly labeled, until the Data Room's own issued
  hierarchy is imported in a future stage."* This stage did not have to
  correct a fabrication — VW9 never claimed a folder hierarchy that
  doesn't exist. The gap was entry-point/orientation framing and one
  under-stated reassurance in Design-Builder Workspace's own copy, not
  dishonesty in the existing Files surface.
- **Six-panel extension points**: the current shell already separates
  Lists (project navigation), Toolbox (contextual operations), Display
  (primary/comparison surfaces), Eye (image/drawing evidence pane),
  Thumbnails, and the topbar (global command surface: Display Layout/
  Appearance/Project Context/Account) — six real, already-modular
  regions, each its own template/CSS region, not six hardwired
  rectangles (see Section H).
- **What can be truthfully implemented without an external connector**:
  honest counts and pointers over already-registered Sources/Folders —
  confirmed, and exactly what this stage implemented. A real external
  Data Room/folder mirror cannot be truthfully implemented without the
  still-unbuilt external connector (`SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR`,
  already named but unwired — Bug Eye's own eventual foundation, COMM-I3B).

## D. Territory Before Ontology assessment

**A real, material violation existed, not a stylistic nitpick.**
Section B's own finding — zero territory information anywhere on a
brand-new project's first screen — directly produces exactly the
failure criterion this stage was asked to test against: a first-time
user has no honest orientation to "what do I already have" before being
shown eight distinct categories of ARCHIOSK's own intelligence. No
material architectural conflict was found with the Product Owner's own
direction — the existing domain model (`Source`, `Folder`,
`FOLDER_ROOT_DATA_ROOM`/`FOLDER_ROOT_DESIGN_BUILDER`) already supports
an honest territory/intelligence split; the gap was presentation and
sequencing, not data model.

## E. Implementation changes

Three bounded, copy/template-level changes, no new domain object, no
new route, no new store method:

1. **`templates/upload.html`** — heading reframed from "Ingest a
   project document" to **"Open a Project"**; intro copy states plainly
   that Archiosk works alongside existing material, does not take its
   place, and that files stay wherever they already are. The upload
   mechanism itself (one founding document, `ingest_upload`) is
   completely unchanged — only the framing language around it.
2. **`templates/case_workspace.html`, Overview** — a new **"Project
   Territory"** accordion, open by default, inserted immediately after
   Environment/Access/Project-Management-&-Settings and **before**
   Needs Attention — the first governed-intelligence content a reviewer
   would otherwise see. States an honest, real `active_sources` count
   and explicitly disclaims any requirement to move/duplicate/reorganize
   files, with a real cross-page pointer to `?view=files` — the exact
   same relocation-not-reimplementation shape ROOT-I1 already
   established for the Requirements pointer immediately below it.
3. **`templates/case_workspace.html`, Files/Design-Builder Workspace**
   — one sentence directly addressing the stated failure criterion:
   *"This is optional — nothing about working in Archiosk requires
   recreating your project's real Data Room or file server here."*
   Placed inside the pre-existing, collapsed-by-default "+ New Folder"
   disclosure rather than as always-visible intro copy — **a real,
   found-and-fixed regression, not a hypothetical**: a genuine
   real-browser Playwright test already in this codebase
   (`test_p40vw9a_files_cockpit_closeout.py`,
   `RealBrowserFolderMenuTests`) proves the two Design-Builder folder
   rows' own click-reachability against this exact page's real rendered
   height; an always-visible sentence added above the folder list —
   even a single one, even merged into the pre-existing paragraph —
   pushed the second row's trigger just far enough to break that proof,
   confirmed by isolating the change via `git stash` and re-running the
   test against unmodified `origin/main` (passed), then bisecting by
   re-adding and removing the sentence alone (failed with it, passed
   without it). Moved into the collapsed disclosure — which contributes
   zero rendered height until a reviewer opens it — fixed the
   regression while keeping the reassurance exactly where it is most
   contextually relevant: the moment a reviewer is about to create
   ARCHIOSK-side folder structure.

`UI_REFERENCE_MAP.md` updated for two new refs
(`display.overview.files-link`, `upload.limits.formats`) and one
re-scoped ref (`upload.limits`), per this repository's own established
consistency-test requirement.

## F. Files / Project Territory surface

Not rebuilt — VW9's own Data Room/Design-Builder Workspace split
already correctly distinguishes real external/issued material (Data
Room) from ARCHIOSK-internal working organization (Design-Builder
Workspace), and already honestly declines to fabricate a hierarchy that
doesn't exist. This stage's own contribution is (a) making this surface
reachable from a prominent Overview pointer instead of only the Lists
sidebar, and (b) strengthening Design-Builder Workspace's own copy so
its optional, internal nature is stated directly rather than left
implicit. **Never fabricated:** no nested directory tree was invented
to imitate an external filesystem; Data Room continues to show a flat,
honestly-labeled list of registered Sources exactly as before.

## G. ARCHIOSK Intelligence surface

Unchanged and not required to change — Requirements, Investigations,
Findings, Decisions/Dispositions, Tasks, Work Products, and Compliance
all already exist as real, separately-navigable Lists branches and
Overview accordions. This stage's only intervention regarding
intelligence content was **sequencing** (Project Territory now appears
before it in Overview), never removing, hiding, or relabeling any of
it. No empty ontology category was created to satisfy this prompt.

## H. Six-panel/workbench implications

**Audit only, per explicit instruction — nothing implemented.** The
current shell's six conceptual roles (global command surface = topbar;
project navigation = Lists; primary display = Display; comparison/
secondary display = Display's own multi-division mechanism, already
real since MM4; contextual operations/toolbox = Toolbox; conversation/
operational surface = Project/Case Conversation) are already reasonably
separated at the template/CSS level, not fused into one monolith — a
real, favorable precondition for a future evolution toward stable
"workspace territories/view containers" projecting different contextual
views, VS Code-Workbench-style. This stage did not attempt that
evolution; it is named here, per Section 7's own instruction, as the
**broader VS Code Workbench precedent for later development**, not
undertaken now. No uncontrolled workbench rewrite occurred.

## I. Entry-flow implications

The `/upload` → `/briefing/preparing` → `?view=overview` chain itself
is unchanged (same routes, same mechanism) — only the copy at the first
and third steps changed. This was judged sufficient: the entry
*behavior* (what happens, what gets created) did not structurally
contradict Territory Before Ontology; the entry *framing* (what the
user is told is happening) did, and is what this stage corrected. No
bounded follow-up implementation stage is required for the entry flow
itself beyond what this stage already did.

## J. Source identity preservation

**Not redesigned, re-confirmed unchanged.** `Source.id` remains the
sole canonical identity; `file_path` remains an internal, ARCHIOSK-
controlled storage detail, never conflated with a real external
location. "A changed location is not a changed identity; a changed
document is not merely a changed location" is unaffected by this
stage's own changes — nothing here touches `register_source_revision`,
`supersedes_source_id`, or any other COMM-I4A mechanism.

## K. Bug Eye compatibility

Preserved, not implemented. This stage's own "Project Territory"
framing and the honest Data-Room/Design-Builder distinction are exactly
the conceptual foundation `specified-unbuilt/bug-eye-data-room-source-continuity.md`
already names as its own prerequisite — Bug Eye's future job (detecting
moved/renamed/superseded Sources in a real external Data Room) only
makes sense once the product has first established, as this stage does,
that the external Data Room is the real territory and ARCHIOSK's own
registration is a layer around it, not a replacement for it. No
watcher, connector, relinking, hashing, or automatic rerouting was
implemented.

## L. Terminology / Semantic Integrity findings

Per "rectify the names before trusting the relationships" — audited,
not renamed:

| Term(s) | Finding |
|---|---|
| **File** / **Document** / **Source** | A genuine three-way collision: "Source" is the canonical domain term; "Document" is the UI-facing synonym ("+ Add Documents"); "File" is used for the Files Display surface name, `Source.file_path` (an internal storage detail), *and* colloquially for the user's own real external material — three different referents sharing one word. Not resolved here; named for future terminology reconciliation. |
| **Documents** (Lists branch) vs. **Files** (Lists branch) | Two separate sidebar entries that both plausibly answer "where are my files" — a real, pre-existing structural redundancy this stage did not introduce and did not resolve (restructuring the sidebar itself was judged a bigger change than this stage's own bounded scope warranted). Named for Owner review. |
| **Archive** | Already-known collision, reconfirmed: `CASE_STATUS_ARCHIVED` (real, implemented Case lifecycle state) vs. whole-project archive/restoration (explicitly *not* implemented, explicitly removed from OPR-1.4's own adopted scope). Directly relevant to Territory Before Ontology's own promise not to silently reorganize anything. |
| **Trust** | A fresh finding this stage: "Surface Trust / Apple Factor" (a named, NOT-implemented future visual-polish programme) vs. `explain_evidence_trust`/"Trustworthy Answer Contract" (a real, implemented MM6/MM7 evidence-grounding mechanism) — two materially different meanings of "trust" (visual polish vs. epistemic grounding) sharing one word. |
| **Workspace** | `ProjectWorkspace`/`CaseWorkspaceStore` (the literal domain class names) and "the workspace" (the general UI shell term, `/projects/<id>/workspace` URL) reinforce each other consistently — no collision found. |
| **Territory** | Not a pre-existing code/UI term at all — introduced fresh by this prompt as a design principle. No collision; not made into rigid UI chrome (see below). |
| **Navigator** | OPR-3.2's own name ("Local Navigator") does not appear as literal UI chrome anywhere — it maps onto several different concrete per-modality features (PDF page nav, spreadsheet row nav, drawing sheet nav) without one single visible "Navigator" panel. An OPR-name-to-UI-reality mapping gap, not a collision, consistent with the same shape of finding already made for OPR-3.4/Contextual Operations. |
| **Open** | Heavily reused as a plain navigation verb ("Open Requirements →," "Open Files →," `open_folder`) — consistent, not colliding; this stage's own new "Open a Project" heading and "Open Files →" pointer fit the same established pattern rather than introducing a new one. |

**Deliberate choice, stated explicitly:** "Territory" itself was **not**
made into a literal, capitalized UI category label (no "TERRITORY" nav
item was added) — the word already does real work in explanatory
sentences ("your project's own territory... remains wherever it
already is") without needing to become a rigid taxonomy term risking
its own future collision, consistent with "do not rename terminology
merely for elegance."

**COMM-CONTINUE-01 finding preserved exactly, not touched:** the
adopted OPR's own Section C ("User Testing") vs. Section H (folded into
generic "Test") inconsistency for OPR-7.2 remains recorded in
`continue-01-opr-7-2-evidence-boundary-audit.md`, not reopened or
resolved here, per explicit instruction.

## M. Compatibility and latent-regression findings

No new dormant path was introduced by this stage's own changes (all
three changes are additive copy/one new accordion, nothing removed or
forked). Carried forward, not re-investigated: the two Latent-Regression
items COMM-I6 already named (`record_relationship`'s missing
cross-project guard; the two near-identical Source-revision routes) —
both unaffected by this stage. New this stage: the Documents/Files
sidebar redundancy (Section L) is itself a real, if minor, "multiple
authorities over project navigation" candidate per Section 16's own
checklist — two branches, no single canonical answer to "where do I see
my files," though neither one is wrong, just overlapping.

## N. Builder usability walkthrough results

Performed and **truthfully labeled**: this session's own Builder
(Claude Code) navigated the real, live, freshly-restarted application
as `archiosk_commissioning`, confirming — not merely asserting — that
`/upload` renders the new heading/copy, that the real commissioning
specimen's Overview now opens with "Project Territory" showing an
honest, live count (4 registered) before Needs Attention, and that
Design-Builder Workspace's new reassurance sentence renders correctly
alongside the pre-existing Data Room/Design-Builder Workspace split.
**This is explicitly not, and is not offered as, the outstanding OPR-7.2
representative-user validation** — it is the same Builder-operated
tier of evidence COMM-I6/CONTINUE-01 already classified as tiers 2/3,
not tiers 4/5.

## O. OPR-7.2 outstanding-test preparation

Not conducted this stage, per explicit instruction — the genuine
representative-user validation is deliberately deferred until after
this metamorphosis and its targeted recommissioning, so the evidence
reflects the product intended for actual pilot use. This stage's own
changes are designed with that future test in mind: a first-time
reviewer landing on Overview now sees an honest territory summary before
any ARCHIOSK-intelligence content, which is the condition the future
representative-user test should be evaluated against, not a substitute
for running it.

## P. Targeted recommissioning impact map

Requirements potentially materially touched by this metamorphosis,
named per this stage's own required minimum consideration list — **no
outcome prejudged**:

| Requirement | Touched? | Why |
|---|---|---|
| OPR-3.1 (Listings) | **Yes** | Overview's own accordion order changed (new "Project Territory" inserted before Needs Attention) |
| OPR-3.2 (Local Navigator) | No | Unaffected — no per-modality navigation code touched |
| OPR-3.3 (Main Display) | No | Unaffected — Display mechanism untouched |
| OPR-3.5 (Canonical Ownership) | No | `Source`/`Folder` identity mechanisms untouched |
| OPR-3.6 (Persistence) | No | No session/state persistence mechanism touched |
| OPR-3.7 (Progressive Disclosure) | **Yes** | The explicit purpose of this stage's own reordering — should be re-examined against the new "Where am I / What is here / What does Archiosk know" sequence |
| OPR-1.1/1.3 (Project Creation/Switching) | **Yes, narrowly** | Entry-point copy (`/upload`) changed; the underlying creation/switching mechanism did not |
| Human-operation surfaces (OPR-6.1) | **Yes, narrowly** | The human-vs-AI distinction itself is unchanged, but the surface where a human first orients to the project changed |
| OPR-7.2 (Zero-Founder validation) | **Directly, by design** | This entire stage exists because of COMM-CONTINUE-01's own OPR-7.2 finding; the outstanding test should be run against this corrected surface, not the pre-metamorphosis one |

**Recommended targeted subset for reassessment**: OPR-3.1, OPR-3.7, and
(narrowly) OPR-1.1/1.3 — a bounded re-check of the Overview/entry
surface only, not a full 34-Requirement re-commissioning.

## Q. Future-Prompt Watch

| Item | Classification | Trigger | Why it matters | Pull-forward condition |
|---|---|---|---|---|
| File/Document/Source three-way naming collision | **BACK-BURNER ITEM — RESURFACE FOR OWNER REVIEW** | This stage's own Semantic Integrity audit | Three real, distinct concepts share one everyday word across code, UI, and plain English | Before any future terminology-reconciliation pass, or before external-facing documentation that could be read literally |
| Documents/Files sidebar redundancy | **LATENT REGRESSION / DORMANT-RISK CANDIDATE (low severity)** | This stage's own architecture audit | Two Lists branches both plausibly answer "where are my files," with no single canonical pointer between them | If a future stage ever needs "the one place files live," reconcile before adding a third |
| "Trust" naming collision (Surface Trust vs. Trustworthy Answer Contract) | **BACK-BURNER ITEM — RESURFACE FOR OWNER REVIEW** | This stage's own Semantic Integrity audit | Visual-polish programme and epistemic evidence-grounding mechanism share one word | Before Surface Trust's own future stage is named/scoped in detail |
| VS Code Workbench precedent (view containers, stable command surface) | **EXISTING FUTURE PROGRAMME — RELEVANT EVIDENCE FOUND** | This stage's own Section 7/H audit | The current shell's six regions are already modular enough to support this evolution without a rewrite | Explicit, separate Product Owner authorization for a workbench-evolution stage |
| Bug Eye's own territorial foundation | **EXISTING FUTURE PROGRAMME — RELEVANT EVIDENCE FOUND** | This stage's own Section K | Territory Before Ontology is confirmed, by this stage's own work, to be the correct conceptual prerequisite Bug Eye already named itself as depending on | Any future authorization to begin Bug Eye design work |
| OPR-7.2 genuine representative-user test | **EXISTING FUTURE PROGRAMME — RELEVANT EVIDENCE FOUND** (carried forward from COMM-CONTINUE-01) | Explicitly deferred by the Product Owner's own instruction this stage | The test should now be run against the corrected, territory-first surface | Product Owner authorization once targeted recommissioning (Section P) is complete |

No item above was implemented. No Future Programme or OPR text was
created or modified.

## R. Tests/full regression result

Ten new focused tests
(`tests/test_meta_t01_territory_before_ontology.py`) covering: the
Project Territory accordion's presence and honest count, its position
before Needs Attention (progressive-disclosure order, verified by
string-index comparison), the never-move/duplicate framing, the
Design-Builder Workspace reassurance copy, continued Data Room/
Design-Builder distinctness, the upload page's new heading/copy, and a
regression guard confirming every pre-existing `data-ui-ref` the
established test suite depends on is still present. All pass.
Three initial test-writing errors (whitespace assumptions crossing a
template line-wrap, and one wrong expected Source count) were found and
fixed in the test file itself, not the template — confirmed by direct
debugging that the template output was correct in every case.

**One real regression was found and fixed, not just a test-writing
error — a genuine example of this codebase's own existing test coverage
doing its job.** The full suite's first run failed
`test_p40vw9a_files_cockpit_closeout.py::RealBrowserFolderMenuTests::test_opening_one_folder_menu_closes_another_and_outside_click_dismisses`,
a real-browser Playwright test proving the two Design-Builder folder
rows' click-reachability. Confirmed via `git stash` (passed against
unmodified `origin/main`) and bisection (failed with the new
Design-Builder sentence present as always-visible copy, in either a
separate or merged paragraph; passed with it removed) that this
stage's own added copy — not a pre-existing flake — pushed the second
folder row's trigger out of reach within the test's own fixed 800px
viewport. Fixed by relocating the sentence into the pre-existing,
collapsed-by-default "+ New Folder" disclosure (Section E), which
resolved the regression while placing the reassurance at an arguably
more relevant moment. Re-confirmed passing (8/8) after the fix.

Targeted re-runs of `test_p40vw7a_ui_reference_map.py`,
`test_p40vw9_files_display_and_folder_architecture.py`,
`test_p40vw9a_files_cockpit_closeout.py`,
`test_p40vw8qa_upload_capacity.py`, `test_project_home.py`,
`test_root_i1_canonical_navigation.py`, and four other Overview-
adjacent suites all pass. Full suite, run genuinely fresh after the
fix: **2997 passed, 0 failed, 65 subtests passed** (15m00s).

## S. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document and the code/test changes are committed together.

## T. Remaining UI work

- Files' own Data Room hierarchy remains a flat list, honestly labeled
  as such — importing a real issued hierarchy remains future,
  deliberately deferred work (VW9's own original scope, unchanged).
- The Documents/Files sidebar redundancy (Section L/Q) is named, not
  resolved.
- The broader VS Code Workbench "view containers" evolution (Section H)
  is named, not begun.
- Surface Trust / Apple Factor visual polish remains entirely
  untouched and out of scope, as instructed.

## U. Recommendation for the next targeted recommissioning stage

A bounded re-assessment of OPR-3.1 (Listings), OPR-3.7 (Progressive
Disclosure), and OPR-1.1/1.3 (Project Creation/Switching, narrowly, for
their entry-point copy only) against the corrected Overview/entry
surface — not a full 34-Requirement re-commissioning, per this stage's
own explicit instruction not to recommission everything automatically.

## V. Recommendation for genuine representative-user Zero-Founder testing

Now that the Territory-first surface exists, the Product Owner's own
deferred OPR-7.2 validation should be scheduled against **this**
corrected product, once the targeted recommissioning above (Section U)
is complete — not before, and not automatically from this stage.
