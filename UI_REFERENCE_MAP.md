# UI Reference Map

**CLAUDE-P40-VW7A**, updated by **CLAUDE-P40-VW7B** and **CLAUDE-P40-VW9**. A stable-ID
registry over the application's Menu, Lists, Display, Toolbox, and
Chat surfaces — the traceability layer this and future stages use to
know what a control currently is, means, and does before renaming,
reparenting, or retiring it. This document is a durable record,
updated alongside the code, the same way `MANIFEST.md` and
`CONTINUATION_CHECKPOINT.md` are.

**VW7B in one line:** the active-Display-targeting mechanism (until
now, Documents only — a real file, embedded via a plain `<iframe src=
file_url>`/`<img>`) was generalized to also cover Investigations and
Overview, via a new `?panel=1` query flag on the existing
`workspace.show_workspace` route (no new route) and
`templates/panel_shell.html` (a minimal standalone document
`case_workspace.html` extends instead of `base.html` when that flag is
set) — see the Display section below and routes/workspace.py's own
`panel_only` comment. `lists.project.tools.data-management` was
retired and relocated (see "Retired references") after VW7B's own
inspection found it resets **every** Project in the deployment, not
the active one — nesting it under one Project's own tools misrepresented
its real scope.

**VW9 in one line:** Files became the second real entry in the
`STABLE_DIRECTORY_KINDS`/`PANEL_KINDS` stable-surface extension point
VW8-QA1 built — one new Lists leaf (`lists.project.files`) and one new
Display surface (`display.files`, the two governed sibling roots below
it) rendered through the exact same registry-driven mechanism Overview
already used, proving that extension point genuinely generalizes rather
than being a comment promising it would. No existing reference was
retired or reparented by this stage; every new reference is additive.
A real, latent bug in the multi-Display click-interceptor (`templates/
base.html`) was found and fixed during this stage's own real-browser
verification: it used to hardcode `kind='overview'` for ANY `data-view`
link, correct only by coincidence when Overview was the only one that
existed — fixed to read the attribute's own value.

## What this is, and isn't

VW7A was purely additive and instrumentation-only: every control
already existed before it; nothing was renamed, moved, or behaviorally
changed to build this registry — `git diff` against the VW7A commit
shows only `data-ui-ref="..."` insertions (plus the new UI Reference Mode
toggle itself and its CSS/JS).

VW7B is a real (if bounded) behavior/structure stage, exactly what
this registry exists to make traceable: it generalized the active-
Display-targeting mechanism to Investigations/Overview, relocated one
misplaced admin control, and added coherent empty states to three
families that were missing them. Every row below states current
behavior as of VW7B, not VW7A — where VW7B changed something, the row
says so; where it didn't, the row is unchanged from VW7A.

**Turn on UI Reference Mode** (Account menu, top-right, "UI Reference
Mode" checkbox) to see every instrumented control's own `data-ui-ref`
value rendered as a small badge directly on the page — the fastest way
to cross-check this document against the live app. Off by default; a
reviewer/device preference (`localStorage`), never a Project record.

## ID scheme

Dot-separated, lowercase, kebab-case-within-segment, hierarchical:
`<surface>.<family>[.<subfamily>][.<kind>]`.

Surfaces: `menu` (top bar), `lists` (left panel), `display` (main
projection area), `toolbox` (right contextual panel), `chat` (bottom
conversation dock), `shell` (structural chrome — panel dividers).

**A `data-ui-ref` value identifies a KIND of control, not one instance.**
For a repeating pattern (a Document leaf, a Task row, a Project row),
every rendered instance shares the same `data-ui-ref` — the existing
per-instance attributes (`data-source-id`, `data-task-id`,
`data-tag-occurrence-id`, the leaf's own `href`) still disambiguate
which one, exactly as they did before this stage. This is a query
selector convention, not an HTML `id` — uniqueness is not implied or
required, and none of the code that reads `data-ui-ref` (only the CSS
reference-mode badge and this stage's own consistency tests) assumes
otherwise.

## Status column

- **active** — currently rendered, in real use.
- **retired** — a control this ID used to name was removed; the ID is
  never reused for something else (see "Retired references" below).

---

## Menu (top bar — `templates/base.html`, present on every authenticated page)

| Reference | Element | Label/summary | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `menu.brand` | `<a>` | bottleneck mark (`archiosk_mark` macro, decorative/`aria-hidden`) + "Archiosk" | Navigates to `portal.index` (`/`); single accessible name `aria-label="Archiosk Home"` covers mark+text as one link/tab-stop (CLAUDE-P40-BRAND1 — was bare "Archiosk" text at `--text-metadata`/0.85rem; now icon+wordmark at `--brand-gold`(+per-appearance)/1.2rem·600, sized above `menu.context`'s breadcrumb to read as the application identity; the mark itself is two mirrored straight-line open angles with a non-touching central gap and one dot below it — a product-owner correction replaced an earlier two-parabola-leg version outright) | Every authenticated page | active |
| `menu.context` | `<span>` | breadcrumb (Project / Investigation / Document / Overview) | Non-interactive container; its own first segment (`menu.context.switch-project`, below) is now interactive | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.context.switch-project` | `<a>` (new, CLAUDE-P40-VW7B) | the Foreground Project's own display name | Section 5's own required "deliberate access to Switch Project" — navigates to `portal.choose_project?current=<project_id>` (the Project Vestibule, extended for this stage). `aria-label`/`title` carry the real purpose ("Switch Project") since the visible text alone (just the Project's name) would not otherwise communicate that activating it navigates away. A real, already-authorized navigation — no interruption dialog (per-Project workspace state is already safely persisted; see the template's own note on the now-retired `lists.project-switch-dialog`, below) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout` | `<details>` popup | "Display Layout" | Vertical/Horizontal steppers + Apply — sets `#display-divisions`' grid via `window.ArchioskDisplay`-adjacent client JS (`applyLayout` in `case_workspace.js`) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout.vertical-decrement`, `menu.display-layout.vertical-increment`, `menu.display-layout.horizontal-decrement`, `menu.display-layout.horizontal-increment` | `<button>` (4 distinct, named controls) | −/+ steppers | Adjust the PENDING Vertical/Horizontal count (not yet applied) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout.apply` | `<button>` | "Apply" | Commits the pending Vertical × Horizontal count to `#display-divisions` | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance` | `<details>` popup | "Appearance" | Per-surface (All/Menu/Lists/Display/Toolbox/Chat) **Light/Black/Midnight Blue/Deep Forest** radio matrix (CLAUDE-P40-VW8-QA Approved Theme Set — was Light/Dark/Tinted; this row was stale until this stage, corrected while auditing the same Menu region for the document-controls addition below), `localStorage`-persisted | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.all` | `<tr>` | "All" row | Applies one mode to all 5 surfaces at once; reflects "checked" only when all 5 already share one mode, otherwise unchecked with `#appearance-mixed-note` shown (Section 5 — never a 5th theme, a control over the existing 4) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.all.light`, `menu.appearance.all.dark`, `menu.appearance.all.tinted`, `menu.appearance.all.deep-forest` | `<input type="radio">` (4 distinct values, constructed from a fixed `{% for %}` loop) | "All surfaces appearance: `Light`/`Black`/`Midnight Blue`/`Deep Forest`" | Sets every surface (Menu/Lists/Display/Toolbox/Chat) to that mode in one action. `dark`/`tinted` ref suffixes retained unchanged through two label revisions (Dark→Graphite→Black, Tinted→Midnight Blue — see `tokens.css`'s own comment); `deep-forest` is the one genuinely new suffix | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.menu`, `menu.appearance.lists`, `menu.appearance.display`, `menu.appearance.toolbox`, `menu.appearance.chat` | `<tr>` (5 distinct values, one per real surface) | per-surface row | Groups that surface's own 4 radios | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.menu.light`, `menu.appearance.menu.dark`, `menu.appearance.menu.tinted`, `menu.appearance.menu.deep-forest`, `menu.appearance.lists.light`, `menu.appearance.lists.dark`, `menu.appearance.lists.tinted`, `menu.appearance.lists.deep-forest`, `menu.appearance.display.light`, `menu.appearance.display.dark`, `menu.appearance.display.tinted`, `menu.appearance.display.deep-forest`, `menu.appearance.toolbox.light`, `menu.appearance.toolbox.dark`, `menu.appearance.toolbox.tinted`, `menu.appearance.toolbox.deep-forest`, `menu.appearance.chat.light`, `menu.appearance.chat.dark`, `menu.appearance.chat.tinted`, `menu.appearance.chat.deep-forest` | `<input type="radio">` (20 distinct values: 5 surfaces × 4 modes) | "`<Surface>` appearance: `<Mode>`" | Sets that ONE surface's mode; `beehive:appearance:<surface>` in `localStorage`, stored value from the new mode vocabulary (`black`/`midnight-blue`/`deep-forest`/`light`) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.account` | `<details>` popup | "…" (username) | Contains UI Reference Mode toggle + Sign out | Every authenticated page | active |

**Document controls (CLAUDE-P40-VW7A-QA, Move Document Controls into the Top Application Menu — new surface, no prior identifiers to retire):**
the central region between `menu.context` and `menu.display-layout`/
`menu.appearance`/`menu.account`. The document viewer's own OLD
`<iframe>` embed never had any Archiosk-built toolbar or `data-ui-ref`
of its own — the "toolbar" reported as a defect was the browser's own
native PDF chrome rendering inside that iframe, entirely outside this
app's control (confirmed by direct inspection of the prior template
source before this stage's own change). Every reference below is
therefore genuinely NEW, not reparented from an old one — stated
honestly rather than fabricating a "moved from" history that doesn't
exist. Hidden (`[hidden]`) whenever no PDF Source is the active
Display target; `static/js/pdf_viewer.js` (vendored PDF.js — see
`static/js/vendor/pdfjs/README.md`) owns every control's real
behavior. PDF only — a drawing/DOCX/TXT Source has no page/zoom/
rotation concept this stage builds a renderer for (the pre-existing
`display.document`/`toolbox.document` pane-note about page navigation
still renders, unchanged, for those formats).

| Reference | Element | Label/summary | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `menu.document-controls` | `<div role="toolbar">` | (no visible label — `aria-label="Document controls"`) | The whole contextual region; `[hidden]` unless a PDF Source is active | Same as workspace access | active |
| `menu.document-controls.prev-page`, `menu.document-controls.next-page` | `<button>` | ‹ / › | Real page navigation — re-renders the PDF.js canvas at the new page; disabled at the first/last page respectively | Same as workspace access | active |
| `menu.document-controls.page-input` | `<input>` | current page number | Typing a number + blur/Enter jumps to that page (clamped to 1..page count) | Same as workspace access | active |
| `menu.document-controls.zoom-out`, `menu.document-controls.zoom-in` | `<button>` | − / + | Adjusts the render scale by 10%, clamped 25%–400% | Same as workspace access | active |
| `menu.document-controls.fit-width`, `menu.document-controls.fit-page` | `<button>` | "Fit width" / "Fit page" | Computes the scale that fits the current page's width, or both dimensions, to the canvas container | Same as workspace access | active |
| `menu.document-controls.rotate` | `<button>` | ↻ | Rotates the rendered page 90° per click (cumulative, wraps at 360°) | Same as workspace access | active |
| `menu.document-controls.mirror-h`, `menu.document-controls.mirror-v` | `<button>` | ↔ / ↕ | CLAUDE-MM4: toggles a horizontal/vertical view-only CSS mirror on the rendered page (never touches the stored PDF bytes) | Same as workspace access | active |
| `menu.document-controls.reset-orientation` | `<button>` | ↴ | CLAUDE-MM4: clears rotation and both mirror flags back to the identity view | Same as workspace access | active |
| `menu.document-controls.orientation-status` | `<span aria-live="polite">` | (no visible label at rest) | CLAUDE-MM4: reads e.g. "Rotated 90° clockwise and mirrored horizontally — source unchanged" whenever any orientation transform is active, empty at the identity view | Same as workspace access | active |
| `menu.document-controls.region-select` | `<button>` (joins the annotate-tool one-of-group) | ▢ | CLAUDE-MM4: drag-to-select-rectangle tool that creates a REAL, persisted `AddressableRegion` + `EvidenceItem` via `POST .../drawing-regions` — distinct from the ephemeral, never-saved annotation tools above | Same as workspace access | active |
| `menu.document-controls.region-status` | `<span aria-live="polite">` | (no visible label at rest) | CLAUDE-MM4: sheet lookup/registration prompts, in-progress "Saving region…", and the resulting citation + "Copy citation" action after a region is created | Same as workspace access | active |
| `menu.document-controls.search-input` | `<input type="search">` | "Search in document" | Real full-document text search via PDF.js's own `getTextContent()` (extracted and cached per page) across every page — not a placeholder | Same as workspace access | active |
| `menu.document-controls.search-prev`, `menu.document-controls.search-next` | `<button>` | ∧ / ∨ | Cycles to the previous/next match, jumping pages as needed; disabled with no matches | Same as workspace access | active |
| `menu.document-controls.download` | `<a download>` | ↓ | Direct link to the same `workspace.source_file` URL the canvas itself renders from | Same as workspace access | active |
| `menu.document-controls.print` | `<button>` | 🖶 | Opens the original PDF in a new tab (the browser's own native print/save chrome there is fully functional) — a real, working action, not a stub; re-implementing print pagination for a canvas-rendered page was judged unnecessary complexity given this already works reliably | Same as workspace access | active |
| `menu.document-controls.overflow` | `<details>` | "…" | Only shown (CSS `.doc-controls-overflow-active`, JS-toggled) below a 900px viewport; `static/js/pdf_viewer.js` re-parents the SAME secondary-control DOM nodes into it, never a cloned duplicate | Same as workspace access | active |
| `display.document.pdf-canvas` | `<div>` (Display) | (no visible label) | Empty container `static/js/pdf_viewer.js` fills with a `<canvas>` on mount — replaces the old plain `<iframe src=raw-file-url>` for a PDF Source specifically (drawings/DOCX/TXT keep their existing `<img>`/`<iframe>`, unchanged) | Same as workspace access | active |

**Annotation tools (CLAUDE-P40-VW7A-QA2 — new, added to the same `menu.document-controls` region, inside `doc-controls-secondary` so they share its existing responsive overflow behavior; no prior identifiers to retire):** real, client-side-only PDF annotation tools — text/highlight/freehand ink, select+delete, undo/redo. One active tool at a time (`aria-pressed`, toggled by `static/js/pdf_viewer.js`'s `setActiveTool`). Coordinates are stored in PDF page space (`PageViewport.convertToPdfPoint`/`convertToViewportPoint`), not raw canvas pixels, so annotations stay correctly placed across zoom/rotation changes. Deliberately **no** Save/Export ref exists — the disclosed scope boundary: no PDF-writing library is vendored in this repo (only PDF.js's rendering half — `static/js/vendor/pdfjs/README.md`), so there is no reliable way to bake these into a real derived PDF file this stage. `menu.document-controls.annotation-status` is how "unsaved changes" is surfaced instead.

| Reference | Element | Label/summary | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `menu.document-controls.annotate-text`, `menu.document-controls.annotate-highlight`, `menu.document-controls.annotate-ink`, `menu.document-controls.annotate-select` | `<button>` (one-of-four, `aria-pressed`) | T / ▭ / ✎ / ↖ | Selects the active annotation tool; clicking the already-active one deselects it (no tool = clicks on the canvas do nothing) | Same as workspace access | active |
| `menu.document-controls.annotate-delete` | `<button>` | ✕ | Removes the currently-selected annotation (Select tool); disabled with no selection | Same as workspace access | active |
| `menu.document-controls.annotate-undo`, `menu.document-controls.annotate-redo` | `<button>` | ↶ / ↷ | Real undo/redo stacks over annotation add/delete operations for the current browser session only; disabled when the respective stack is empty | Same as workspace access | active |
| `menu.document-controls.annotation-status` | `<span aria-live="polite">` | (no visible label at rest) | Reads "Unsaved annotations (draft only — not saved to the Document)" whenever any page has at least one annotation, empty otherwise; a `beforeunload` prompt backs this up on tab close/navigation | Same as workspace access | active |

## Shell (structural chrome — `templates/base.html`)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `shell.lists-divider` | `<button>` | (unlabeled divider) | Collapses/shows the Lists panel; `localStorage`-persisted, reviewer-wide | Every authenticated page | active |
| `shell.toolbox-divider` | `<button>` | (unlabeled divider) | Collapses/shows the WHOLE right column (Toolbox and Eye together, CLAUDE-P40-EYE1 — was Toolbox alone); `localStorage`-persisted, per-Project. **Product-owner browser correction:** now ALSO a real, mouse-draggable/keyboard-operable (`ArrowLeft` widens/`ArrowRight` narrows) WIDTH resize handle for the right column — a genuine drag (movement past a small threshold) is distinguished from a plain click, so the pre-existing collapse/show behavior is unchanged for an ordinary click. Width persisted separately (`beehive:panel:right-column-width:<project_id>`), clamped against a practical minimum for both the right column and the centre (Display/Chat) column | Only rendered when `project_id`/`workspace` are defined | active |
| `shell.lists-thumbnails-divider` | `<div role="separator">` (CLAUDE-P40-VW7A-QA2) | (unlabeled divider) | Draggable (pointer + arrow-key) horizontal split between `lists.thumbnails-pane` and Lists above it; percentage-based, `sessionStorage`-persisted (deliberately weaker than the `localStorage` panel-show/hide prefs above — Section 3's own "may persist per session"; still survives an ordinary refresh, which is all CLAUDE-P40-LTH1's own persistence requirement needs); double-click restores the default 60/40 split. **CLAUDE-P40-LTH1 (correction):** no longer ever `[hidden]` — a permanent fixture, the same treatment `shell.toolbox-eye-divider` already has (below); real `:focus-visible` outline added | Every authenticated page | active |

## Lists — cross-Project (`templates/base.html`, reviewer-wide)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.projects` | tree-toggle `<button>` | "Projects" | Expands/collapses the Projects root; auto-open whenever a Project is open or `/projects` is the current page | Every authenticated page | active |
| `lists.projects.leaf` | tree-leaf `<a>` (pattern) | Project display name | Navigates to that Project's own workspace (`workspace.show_workspace`) — only for a Project that is **not** the currently active one (the active one instead expands into `lists.project.self` and its branch, below) | Filtered to `nav_recent_projects` (already access-scoped) | active |
| `lists.new-project` | tree-leaf `<a>` | "+ New Project" | Navigates to `portal.upload` | **Admin only** — `is_admin` | active |
| `lists.removed-projects` | tree-leaf `<a>` | "Removed Projects" | Navigates to `portal.removed_projects` | Every authenticated page | active |
| `lists.security` | tree-leaf `<a>` | "Security" | Navigates to `security.department_home` | **Admin only** — `is_admin` | active |
| `lists.system-data-management` | `<a>` inside a subdisclosure | "Reset Project Data…" | Navigates to `portal.reset_project_data`. **CLAUDE-P40-VW7B:** relocated here from the active Project's own "Project Tools" branch (`lists.project.tools.data-management`, retired — see below) — the route resets `REGISTRY_STORE_PATH` in full ("returns the app to a clean, no-project state"), every Project in the deployment, not the one whose tools branch it used to sit in | **Admin only** — `is_admin` | active |
| `lists.project-switch-dialog` | *(retired — CLAUDE-P40-VW7B)* | (dialog, no visible label — `aria-labelledby` its own heading) | **CLAUDE-P40-VW8:** interruption dialog shown when activating `lists.projects.leaf` for a Project other than the one currently open. **CLAUDE-P40-VW7B:** its only trigger, `lists.projects.leaf`, no longer renders while a Project is open at all (Section 3's own removal of the portfolio from the opened Lists panel) — dead code, removed outright rather than left unreachable. Nothing renders this reference any more; retired rather than reused for a different control | — | retired |
| `lists.project-switch-dialog.stay` | *(retired — CLAUDE-P40-VW7B)* | "Stay in Current Project" | Retired alongside its parent dialog, above | — | retired |
| `lists.project-switch-dialog.switch` | *(retired — CLAUDE-P40-VW7B)* | "Switch in This Tab" | Retired alongside its parent dialog, above | — | retired |
| `lists.project-switch-dialog.open-new-tab` | *(retired — CLAUDE-P40-VW7B)* | "Open in New Tab" | Retired alongside its parent dialog, above | — | retired |

**Selection-state hierarchy correction (CLAUDE-P40-VW7A-QA, all identifiers above retained unchanged):**
`lists.projects` (an expanded root), `lists.project.self` (the current
Project), and whichever child leaf is actually selected (e.g.
`lists.project.chats`) used to share the literal same `active` CSS
class/fill, reading as three indistinguishable "selected" rows. Now
three genuinely distinct treatments, none of them renumbered or
reparented: `lists.projects`'s own structural-title typography no
longer paints a selection-style fill merely for being expanded
(`aria-expanded` alone conveys that); `lists.project.self` gets a new
`.current-project` CSS class (a restrained left-edge marker,
`aria-current="true"`) instead of `.active`; the `.active` class and
its `--surface-selected` fill are now reserved exclusively for the one
child leaf whose own href is what is actually displayed
(`aria-current="page"`). A new `.sibling-project-after-current` class
(not a UI reference — a pure layout hook, whitespace-only) marks
whichever sibling Project row renders immediately after the current
Project's own child group closes, so it doesn't visually read as a
continuation of that group.

## Lists — active Project branch (`templates/base.html`, only inside the currently open Project's own row)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.project.self` | tree-leaf `<a>`, `current-project` (CLAUDE-P40-VW7A-QA — was `active`, see note below) | active Project's own display name | Navigates to its own workspace (a no-op — already there); this row is what expands into every entry below. `aria-current="true"` identifies it as the current Project, distinct from `aria-current="page"` on whichever child leaf is actually selected | Same as `_load_workspace_or_404` (project owner/allow-list/admin) | active |
| `lists.project.overview` | tree-leaf `<a>`, `data-view="overview"` | "Overview" | **Division 0 is the active target (default):** real navigation to `?view=overview`. **A non-zero Display is the active target (CLAUDE-P40-VW7B):** client-side-intercepted, no navigation — projects into that division via `window.ArchioskDisplay.populateDivision(target, 'overview', '', 'Overview')`, an `<iframe src="...?view=overview&panel=1">`. Either way the content is `display.overview`, below | Same as workspace access | active |
| `lists.project.documents` | tree-toggle `<button>` | "Documents (`<count>`)" | Expands/collapses; count = `active_sources\|length`; "No Documents yet." empty state (CLAUDE-P40-VW7B) | Same as workspace access | active |
| `lists.project.documents.leaf` | tree-leaf `<a>`, `data-source-id` (pattern) | Document name | **Division 0 active target:** real navigation to `?source=<id>`. **Non-zero Display active target:** client-side `populateDivision(target, 'source', sourceId, name)` — unchanged since VW7A, a real file embedded via `<iframe src=file_url>`/`<img>`, never the `&panel=1` mechanism. Syncs Toolbox to `toolbox.document` | Same as workspace access | active |
| `lists.project.documents.empty` | `<span>` | "No Documents yet." | Empty-state message (CLAUDE-P40-VW7B — untagged until CLAUDE-P40-VW8-QA's Complete Root and Subfolder UI Reference Tagging stage) | Same as workspace access | active |
| `lists.project.files` | tree-leaf `<a>`, `data-view="files"` (CLAUDE-P40-VW9, new) | "Files" | **Division 0 is the active target (default):** real navigation to `?view=files`. **A non-zero Display is the active target:** client-side-intercepted via `PANEL_KINDS.files` — projects into that division via `populateDivision(target, 'files', '', 'Files')`, an `<iframe src="...?view=files&panel=1">`. Either way the content is `display.files`, below. Same stable-singleton shape as `lists.project.overview` — no tab-strip pill, no per-instance id, no duplicate-open concept | Same as workspace access | active |
| `lists.project.investigations` | tree-toggle `<button>` | "Investigations (`<count>`)" | Expands/collapses; count = `visible_cases\|length`; "No Investigations yet." empty state (CLAUDE-P40-VW7B) | Same as workspace access, further filtered to `visible_cases` (Case-privacy-aware) | active |
| `lists.project.investigations.leaf` | tree-leaf `<a>`, `data-case-id`/`data-case-title` (pattern) | Investigation title | **Division 0 active target:** real navigation to `?case=<id>`. **Non-zero Display active target (CLAUDE-P40-VW7B, new):** client-side, no navigation — `populateDivision(target, 'case', caseId, title)`, an `<iframe src="...?case=<id>&panel=1">` rendering the exact same content Division 0 would have shown, wrapped in `panel_shell.html` instead of the full shell. Syncs Toolbox to `toolbox.investigation-findings` only when it's Division 0 (a non-zero division's iframe has no Toolbox of its own — see `templates/panel_shell.html`) | Same as `visible_cases` | active |
| `lists.project.investigations.new` | tree-leaf `<a>` (action row, `data-new-case`), always first inside the expanded family, present even at zero Investigations | "+ New Investigation" | **Division 0 active target:** real navigation to the focused `?view=new-case` create-form page. **Non-zero Display active target (CLAUDE-P40-VW8-QA, new):** projects the same focused form via `populateDivision(target, 'new-case', '', 'New Investigation')` — `?view=new-case&panel=1`, same iframe/`panel_shell.html` mechanism as an Investigation/Overview leaf. Not a radio — a command, always available, never creates a record merely by expanding the family | Same as workspace access | active |
| `lists.project.investigations.empty` | `<span>` | "No Investigations yet." | Empty-state message, rendered alongside (not instead of) `lists.project.investigations.new` — the action row is never gated on this state | Same as `visible_cases` | active |
| `lists.project.investigations.new.form` | `<form>` | (create form) | Posts to `workspace.create_case` (unchanged, pre-existing route/service — no parallel Investigation-creation implementation) | Same as workspace access — the route itself is `@login_required` | active |
| `lists.project.investigations.new.title`, `lists.project.investigations.new.objective` | `<input>` | "Investigation title" / "Objective (optional)" | Title required; objective optional — identical fields to the pre-existing Overview "+ Start Investigation" subdisclosure | Same as above | active |
| `lists.project.investigations.new.create` | `<button>` | "Create Investigation" | Submits the form | Same as above | active |
| `lists.project.investigations.new.cancel` | `<a>` | "Cancel" | Navigates to `?view=overview` — creates nothing | Same as above | active |
| `lists.project.investigations.new.validation-error` | `<div>` (flash message) | (validation error text) | Rendered only when `workspace.create_case` rejects an empty title — the SAME focused form re-appears (not the Overview page) so the reviewer's next attempt starts from where they were | Same as above | active |
| `lists.project.rfis` | tree-toggle `<button>` | "RFIs (`<count>`)" | Expands/collapses; count = `rfi_drafts_view\|length`; "No RFIs yet." empty state (CLAUDE-P40-VW7B) | Same as workspace access | active |
| `lists.project.rfis.leaf` | tree-leaf `<a>`, `data-case-id`/`data-case-title` (pattern) | RFI question text (truncated) | Targets the **owning Investigation**, exactly like `lists.project.investigations.leaf` above — an RFI draft has no standalone page (deliberate, documented since CLAUDE-P40-E3A). CLAUDE-P40-VW7B: now also carries `active`-state (when its owning Investigation is `active_case`) and the same `data-case-id`/`data-case-title` attributes, so it participates in active-Display projection identically to an Investigations leaf | Same as workspace access | active |
| `lists.project.rfis.empty` | `<span>` | "No RFIs yet." | Empty-state message (CLAUDE-P40-VW7B — untagged until CLAUDE-P40-VW8-QA's Complete Root and Subfolder UI Reference Tagging stage) | Same as workspace access | active |
| `lists.project.chats` | tree-leaf `<a>` | "Chats N" (CLAUDE-P40-VW7A-QA added the `<span class="launcher-count">` — the Project's own conversation message count, `project_conversation_count` in `routes/workspace.py`) | Navigates to the bare workspace URL (no `?source=`/`?case=`) — renders Project Conversation (`chat.thread`, project scope) | Same as workspace access | active |
| `lists.project.tasks` | tree-toggle `<button>` | "Tasks (`<total>`)" | Expands/collapses; contains `lists.project.tasks.open`/`.completed` sub-groups | Same as workspace access | active |
| `lists.project.tasks.open` | sub-heading `<p>` | "Open (`<count>`)" | Not a toggle — plain grouping label | — | active |
| `lists.project.tasks.completed` | sub-heading `<p>` | "Completed (`<count>`)" | Not a toggle — plain grouping label | — | active |
| `lists.project.tasks.leaf` | tree-leaf `<a>`/`<span>` (pattern) | Task title | Navigates to `#conv-source-<message_id or guidance>` on the correct workspace URL (`_conversation_source_url`) — scrolls/flashes the source passage. Renders as an unavailable `<span>` (no link) when the source anchor no longer resolves | Same as workspace access | active |
| `lists.project.tasks.complete` | `<button>` in a `<form>` (pattern) | "Mark complete" | POST to `complete_task_route`, classic redirect | Same as workspace access | active |
| `lists.project.tasks.reopen` | `<button>` in a `<form>` (pattern) | "Reopen" | POST to `reopen_task_route`, classic redirect | Same as workspace access | active |
| `lists.project.tasks.open.empty` | `<span>` | "No open Tasks." | Empty-state message beneath `lists.project.tasks.open`'s own sub-heading (untagged until CLAUDE-P40-VW8-QA's Complete Root and Subfolder UI Reference Tagging stage) | Same as workspace access | active |
| `lists.project.tasks.completed.empty` | `<span>` | "No completed Tasks." | Empty-state message beneath `lists.project.tasks.completed`'s own sub-heading | Same as workspace access | active |
| `lists.project.tags` | tree-toggle `<button>` | "Tags (`<total occurrences>`)" | Expands/collapses; contains one `lists.project.tags.group` per tag in use | Same as workspace access | active |
| `lists.project.tags.group` | sub-heading `<p>` (pattern) | tag name + color swatch + occurrence count | Not a toggle — plain grouping label; always expanded (`data-tree-open`) | — | active |
| `lists.project.tags.leaf` | tree-leaf `<a>`/`<span>` (pattern) | quoted passage (truncated) | Navigates to `#conv-source-<...>` — same scroll/flash mechanism as Tasks. Renders unavailable when the anchor no longer resolves | Same as workspace access | active |
| `lists.project.tags.remove` | `<button>` in a `<form>` (pattern) | "Remove" | `fetch()` POST to `remove_tag_occurrence_route`, live-patches counts/DOM without reload | Same as workspace access | active |
| `lists.project.tags.empty` | `<span>` | "No Tags yet." | Empty-state message (untagged until CLAUDE-P40-VW8-QA's Complete Root and Subfolder UI Reference Tagging stage) | Same as workspace access | active |
| `lists.project.tools` | tree-toggle `<button>` | "Project Tools" | Expands/collapses; contains every control below. **CLAUDE-P40-VW7B:** no longer contains Reset Project Data — see `lists.system-data-management` above and "Retired references" below | Same as workspace access (individual controls below carry their own, narrower gates) | active |
| `lists.project.tools.remove-project` | `<button>` in a `<form>` | "Remove Project" | POST to `remove_project_route` (Approval-Gate `confirm=yes\|no` vocabulary) | **Owner or admin** — `is_project_owner or is_admin` | active |
| `lists.project.tools.add-document` | `<form>` inside a subdisclosure | "+ Add Documents" | POST (multipart) to `add_document_source` | Same as workspace access | active |
| `lists.project.tools.add-text-record` | `<form>` inside a subdisclosure | "+ Add Text Record" | POST to `add_text_record_source` | Same as workspace access | active |
| `lists.project.tools.add-external-source` | `<p>` inside a subdisclosure | "+ Add External Source" | **Not implemented** — static "not yet available" text, no form | Same as workspace access | active |
| `lists.project.tools.removed-items` | `<ul>`/`<p>` inside a subdisclosure | "Removed Items (`<count>`)" | Lists removed Documents in this Project (or "No removed Documents…") | Same as workspace access | active |
| `lists.project.tools.removed-items.restore` | `<button>` in a `<form>` (pattern) | "Restore Document" | POST to `restore_document_route` | Same as workspace access | active |

## Lists — Page Thumbnails pane (`templates/base.html`, CLAUDE-P40-VW7A-QA2, corrected CLAUDE-P40-LTH1)

Nested inside the same `<nav id="launcher-panel">` as the Lists tree above (`lists.thumbnails-pane` is `lists.project.self`'s own sibling region, not a second panel). **CLAUDE-P40-LTH1 (correction):** used to be `[hidden]` unless the active Display target was a PDF (shown/hidden via a `window.ArchioskListsThumbnailsSplit.show()`/`.hide()` API) — a product-owner browser review found this meant NO visible Lists/Thumbnails split existed at all on Overview/Investigation/Chat/non-PDF-Document pages (Lists silently filled the whole column, a real reported screenshot defect). The pane is now a PERMANENT structural surface, the exact same correction CLAUDE-P40-EYE1 already made for `eye.panel` relative to Toolbox — content, not visibility, now carries the "nothing to show" case (`lists.thumbnails-pane.empty`, below). When no Document is actively selected on the current page (Overview/an Investigation/Chat/no Project), `static/js/pdf_viewer.js` additionally attempts to populate the pane from a client-side-remembered "last-viewed PDF Document" for this Project+reviewer (`localStorage`, revalidated on every load against the SAME authorized `#workspace-active-sources-data` JSON island every other client-side feature in this shell already trusts — never an arbitrary "first Document in the Project," and a stale/removed/unauthorized remembered id clears itself back to the empty state). Thumbnails are rendered lazily (`IntersectionObserver`) as real per-page `<canvas>` images, not placeholders.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.thumbnails-pane` | `<div>` | "Thumbnails" (header text) | The whole pane; contains the maximize toggle, the empty-state message, and the thumbnail list. Never `[hidden]` (CLAUDE-P40-LTH1) | Every authenticated page | active |
| `lists.thumbnails-pane.maximize` | `<button aria-pressed>` | "Maximize" / "Restore" | Collapses Lists toward its header (keeping whatever proportion was active immediately before, on the toggle-back click) so Thumbnails takes most of the column; a manual toggle, not tied to drag state | Every authenticated page | active |
| `lists.thumbnails-pane.empty` | `<p>` (new, CLAUDE-P40-LTH1) | "Open a Document to view its pages." | Visible by default (server-rendered); hidden by `static/js/pdf_viewer.js`'s `buildThumbnails()` the moment real thumbnails exist, shown again by `clearThumbnails()`. Covers both "no Document selected or remembered" and "the active Document is not a PDF" (a drawing/DOCX/TXT genuinely has no pages) | Every authenticated page | active |
| `lists.thumbnails-pane.list` | `<div role="list">` | (no visible label — `aria-label="Page thumbnails"`) | Contains one real, clickable `<button role="listitem">` per PDF page (`.thumbnail-row`, unregistered as an individual ref — a repeated pattern, not a fixed set of controls, same convention as `lists.project.documents.leaf` etc.); clicking one calls `goToPage(n)` when a Document is actually mounted on this page, or navigates to the Document route (landing on the clicked page) when the thumbnails came from a remembered Document instead (CLAUDE-P40-LTH1); `aria-current="true"` follows the current page from ANY navigation source, with a non-color border-width/label-weight cue alongside the color one | Every authenticated page | active |

## Document Tabs (`templates/case_workspace.html`, CLAUDE-P40-DTAB1)

Documents only (never Investigations/RFIs/Chats/Tasks/Tags/Toolbox/Eye)
— a compact tab strip immediately above the active Document content,
Division-0-only. All server-rendered markup below is deliberately
empty/`[hidden]`; `static/js/document_tabs.js` builds every tab from
`#workspace-active-sources-data` (the same authorized, Project-scoped
JSON island `menu.document-controls`'s own populateDivision already
reads) cross-referenced against this browser's own `localStorage`
(pinned/hidden tabs, per-user per-Project) and `sessionStorage` (the
one replaceable preview tab). A tab is a real `<a href="?source=<id>">`
— activating one is a genuine page navigation, never client-side
routing, so stable URLs and Back/Forward are unaffected. Individual
`.document-tab` elements are a repeated pattern (one per open Document),
not a fixed set of controls — left without their own `data-ui-ref`,
the same convention already established for `.thumbnail-row` (CLAUDE-
P40-VW7A-QA2) and `lists.project.documents.leaf`.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `display.document-tabs` | `<div>` | — | The whole tab strip; `[hidden]` server-side, revealed by JS once at least one real tab (pinned or preview) exists | Only rendered when `project_id`/`workspace` are defined and not `panel_only` | active |
| `display.document-tabs.all-tabs` | `<details>` | "▾" (aria-label "All Tabs") | Contains "Close All Tabs" and the Hidden Tabs list (below) | Same as `display.document-tabs` | active |
| `display.document-tabs.all-tabs.summary` | `<summary>` | "▾" | The `<details>` disclosure trigger | Same as `display.document-tabs` | active |

**Per-tab pattern (JS-generated, one instance per open Document, no individual `data-ui-ref`):**

| Pattern | Element | Current behavior |
|---|---|---|
| `.document-tab` | `<a role="tab" href="?source=<id>">` | The tab itself — real navigation on click/Enter/Space; `aria-selected` reflects the current Document; roving `tabindex` (0 on the focused/active tab, -1 on the rest, Left/Right/Home/End move focus); `aria-label` communicates an alias plus the original Document name (never just the alias — Section 12's own "do not replace the actual Document accessible name"); `data-tab-color` drives the curated accent stripe; `.document-tab-preview` marks the one replaceable preview tab (italic label + dashed active-underline, never color alone) |
| `.document-tab-menu-btn` | `<button>` (per tab) | "⋯" — opens the per-tab context menu (Keep Open/Rename/Restore Original Name/Tab Color/Default Color/Hide/Close/Close Others/Show Original Document Name), only the state-applicable subset shown |
| `.document-tab-close` | `<button>` (per tab) | "×" — closes that one tab's workspace state only, never the Document |
| `.document-tab-rename-input` | `<input>` (transient) | Real inline rename field (never `window.prompt()`), commits on Enter/blur, cancels on Escape; empty/whitespace and duplicate-alias input is rejected with an inline message |
| `.document-hidden-tab-item` | `<button>` (inside `display.document-tabs.all-tabs`) | One row per hidden tab — shows alias + original name, selecting restores it to the visible strip and activates it (real navigation) |

## Investigation Attention Positions (`templates/case_workspace.html`, CLAUDE-P40-VW7B, new)

Up to four Investigations held in attention, the same compact tab-strip
idiom `display.document-tabs` above already established (deliberately
reused — Section 13's own "do not introduce a separate visual
language" — a genuinely distinct control family, never a shared
selector with Document tabs). Division-0-only, present regardless of
the current selection. Server-rendered markup is empty/`[hidden]`;
`static/js/investigation_attention.js` builds every position from
`#workspace-visible-cases-data` (the same authorized, privacy-filtered
`visible_cases_for` list the Lists Investigations branch already
reads) cross-referenced against this browser's own `localStorage`
attention-set (per-user per-Project). "Focused" = whichever Investigation
the current `?case=` already names (no separate persisted concept — the
same reasoning `menu.context.switch-project`'s own note gives for
"Foreground Project" needing no new state, one level down); the
attention SET (which up to four are held, independent of which is
focused) is the one genuinely new piece of client-side state. A
position is a real `<a href="?case=<id>">` — activating one is a
genuine page navigation, never client-side routing. Individual
`.attention-position` elements are a repeated pattern (one per
attended Investigation), left without their own `data-ui-ref`, the
same convention `.document-tab`/`.thumbnail-row`/
`lists.project.documents.leaf` already establish.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `display.attention-positions` | `<div>` | — | The whole strip; `[hidden]` whenever the attention set is empty (Section 8's own "compact, visually restrained" — never a permanent empty bar) | Only rendered when `project_id`/`workspace` are defined and not `panel_only` | active |
| `display.attention-positions.capacity-dialog` | `<div role="dialog">` (new) | "Attention is full" | Fifth-Investigation capacity interruption (Section 9) — shown by post-load reconciliation whenever `?case=` names an Investigation not already in the attention set while it's already at 4. Reuses the same dialog CSS family the retired `lists.project-switch-dialog` (below) used to, renamed rather than duplicated | Only rendered when `project_id`/`workspace` are defined and not `panel_only` | active |
| `display.attention-positions.capacity-dialog.cancel` | `<button>` | "Cancel" | Navigates back to the bare workspace URL (Overview) — Section 9's own "cancel opening the new Investigation"; the page has already loaded showing the fifth Investigation's own content (post-load reconciliation, not a pre-click intercept — see that script's own header comment), so cancelling means leaving it, not merely closing the dialog | Same as above | active |

**Per-position pattern (JS-generated, one instance per attended Investigation, no individual `data-ui-ref`):**

| Pattern | Element | Current behavior |
|---|---|---|
| `.attention-position` | `<a role="tab" href="?case=<id>">` | The position itself — real navigation on click/Enter/Space; `aria-selected` reflects whether this is the focused Investigation; roving `tabindex`, Left/Right/Home/End move focus; a real "Focused" text tag (non-color cue, Section 6) on the focused position, an "Archived" text tag on a frozen one (`CASE_STATUS_ARCHIVED`) |
| `.attention-position-release` | `<button>` (per position) | "×" — releases that Investigation from attention only (Section 8's own explicit "must not delete, close, resolve, archive, or otherwise falsify its real status"); never navigates, even when releasing the currently-focused position |
| `.attention-capacity-dialog-item` | `<li>` (inside the capacity dialog, one per currently-attended position) | Shows the Investigation's title with two real actions: "Release" (pure attention-set change, immediate, no page reload) and "Conclude" (the real, already-existing, owner-or-admin-gated `workspace.archive_case` route — the genuine governed completion action Section 9 requires, not a fabricated "soft close"; no "move to Waiting/Parked" option is offered, since no such governed Case state exists in this repository's actual model — grounded, not omitted by oversight) |

### CLAUDE-P40-VW8 (Governed Display Tab System) audit note

Distinct from the earlier, already-shipped "CLAUDE-P40-VW8"/"CLAUDE-
P40-VW8-QA" stage (Reference Mode completion, Appearance/theme
correction, etc. — see this file's own entries elsewhere and
`CONTINUATION_CHECKPOINT.md`); flagged per this repository's established
tag-collision discipline. This stage added no new, moved, or retired
`data-ui-ref` identifiers — every control above already existed and is
unchanged structurally. What it formalizes, grounded directly in the
repository rather than assumed:

- **The real governed tab-kind vocabulary** is `case_workspace.js`'s own
  `populateDivision(divisionIndex, kind, id, displayName)` dispatch —
  `'source'` (Document), `'case'` (Investigation), `'overview'`, and
  `'new-case'` are the only real kinds. `'files'` is now a documented,
  reserved, no-op kind (a comment only — no branch, no picker entry, no
  placeholder control anywhere) for the future dedicated Files Display
  tab.
- **`display.document-tabs`** (Documents) and **`display.attention-
  positions`** (Investigations) are this app's two real dynamic-record
  tab strips. Neither RFI, Task, nor Tag is a separate Display kind —
  an RFI leaf (`lists.project.rfis.leaf`) routes into its owning
  Investigation (`?case=`); a Task/Task leaf (`lists.project.tasks.leaf`
  / `lists.project.tags.leaf`) routes via `routes/workspace.py`'s own
  `_conversation_source_url` into either the bare workspace URL (Chats)
  or an Investigation's own conversation (`?case=`) with a `#conv-
  source-<id>` scroll anchor — never a `?source=` Document route.
  `lists.project.tools` is Lists-only and never touches Display at all.
- **`display.overview`** and the bare/"Chats" no-selection state are
  this app's two stable surfaces — Project-level singletons with no
  possible duplicate, represented through Lists' own server-rendered
  active-state plus the division header text, deliberately with no
  tab-strip pill of their own (a considered choice, not an omission —
  see this stage's own checkpoint entry for the full reasoning).
- Two small, targeted coherence fixes were made (both purely behavioral
  — no markup/ref changes): `.attention-position` now also activates on
  Space (this table's own row above already documented "click/Enter/
  Space" as its behavior — the code had not actually implemented Space
  until this stage closed that pre-existing doc/code gap); and
  `document_tabs.js`'s close-fallback now also considers an attended
  Investigation before falling back to the empty Display state, so
  "closing the active tab" is coherent across BOTH real dynamic-record
  tab strips, not just within whichever one was closed.

## Display (`templates/case_workspace.html`)

**CLAUDE-P40-VW7B, the `panel_only`/`panel_shell.html` mechanism:**
Division 0 is always the real, server-navigated page (`base.html`'s
full shell) — unchanged. A non-zero division (1-5) that shows a
Document embeds the real file directly (`<iframe src=file_url>`/
`<img>`, unchanged since VW7A). A non-zero division that shows an
Investigation or Overview instead embeds an `<iframe>` pointing back
at the SAME `workspace.show_workspace` route with `&panel=1` appended
(`routes/workspace.py`'s own `panel_only` flag) — `case_workspace.html`
extends `templates/panel_shell.html` (a minimal standalone document:
CSS links, CSRF meta + auto-inject, a `.app-main`-scoped Appearance-
mode script, `{% block content %}`/`{% block extra_scripts %}`) instead
of `base.html` when that flag is set, so the identical Division-0
content renders without Menu/Lists/Toolbox/Chat chrome. No new route,
no duplicated authorization — an unauthorized `?panel=1` request fails
at the exact same `_load_workspace_or_404` call every other view of
this data already goes through. Division 0's own header, Overview's
"← Projects" link, AND the entire divisions-1-5-plus-context-menu
block are all suppressed inside a panel (`{% if not panel_only %}`) —
the first two because the OUTER division already provides equivalent
chrome, the last because it is not merely redundant but actively
recursive if left unguarded: a panel's own `case_workspace.js` instance
would otherwise try to restore/populate its own divisions 1-5 from
`sessionStorage`, which could itself embed another panel iframe. Caught
by `tests/test_p40vw7b_root_system_and_projection.py`'s own structural
assertion before ever shipping, not discovered live.

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `display.divisions` | `#workspace-display-panel` | The whole Display surface — 1-6 divisions (VW4's independent Vertical/Horizontal axes), managed by `window.ArchioskDisplay` (`case_workspace.js`) | Same as workspace access | active |
| `display.division` | `.display-division` (pattern — division 0 is always server-rendered/real navigation; divisions 1-5 are client-side-only slots) | Shows whichever record is currently projected into it. **CLAUDE-P40-VW7B:** divisions 1-5 can now show a Document (real file, unchanged), an Investigation, or Overview (both via the `panel_only` iframe mechanism above) — previously Documents only | Division 0: same as workspace access. Divisions 1-5: a Document can only ever be one already in `active_sources` (enforced by `workspace.source_file`); an Investigation/Overview goes through the identical `_load_workspace_or_404`/`visible_cases` checks `?panel=1` shares with every other view | active |
| `display.division.picker` | `<select>` (pattern, divisions 1-5 only) | "Open a Document here…" — populates that division client-side via `window.ArchioskDisplay.populateDivision`. **Still Documents-only** — not extended to list Investigations this stage (a considered, deferred enhancement; the Lists-leaf-click path above is what VW7B's own prompt asked for, not this picker) | Options limited to `active_sources` | active |
| `display.division.close` | `<button>` (pattern, divisions 1-5 only) | Clears that division (any kind — Document, Investigation, or Overview), shrinks the Vertical/Horizontal layout by one (VW4's deterministic shrink rule) | — | active |
| `display.overview` | `#project-overview` | The Overview leaf's actual content: Operating Environment, Access/Settings, Needs Attention, Recent Focus, Investigation Quality, Participants, Go/No-Go, Accepted Knowledge, Instructions, Requirement Compliance, RFIs, Requirements, Key Dates, History — all consolidated under this one leaf (CLAUDE-P40-E3A, Section 5). Its own "← Projects" back-link is suppressed when rendered inside a panel (CLAUDE-P40-VW7B) | Same as workspace access | active |
| `display.files` | `.files-surface` (CLAUDE-P40-VW9, new) | The Files leaf's actual content — the two governed sibling roots below | Same as workspace access | active |
| `display.files.data-room` | `.files-root-data-room` | "Data Room" | Controlled, project-level root. No mutation control of any kind is rendered inside this section — Design-Builder Workspace's own folder routes cannot reach `FOLDER_ROOT_DATA_ROOM` at all (structural, not merely a missing button) | Same as workspace access | active |
| `display.files.data-room.compatibility-list` | `<ul>` | Existing Document names (pattern, same `source-item`/`<a href=?source=<id>>` shape `lists.project.documents.leaf` already uses) | Rendered only when `data_room_sources` is non-empty — every active (non-removed) `workspace.sources`, honestly labeled as pre-Files/not-yet-organized, never reclassified or duplicated | Same as workspace access | active |
| `display.files.data-room.empty` | `<p>` | "No Documents yet…" | Rendered only when `data_room_sources` is empty — explains the root's purpose, not an error state | Same as workspace access | active |
| `display.files.design-builder` | `.files-root-design-builder` | "Design-Builder Workspace" | Editable, team-organized root — the one root every folder route below can mutate | Same as workspace access | active |
| `display.files.design-builder.breadcrumb` | `<p>` | Design-Builder Workspace › ⟨open folder ancestors⟩ | Derived at read time from `CaseWorkspaceStore._folder_path` (never a stored path string); each ancestor is a real link to `?view=files&folder=<id>`. Distinct from the top application breadcrumb (`menu.context`), which stays "Files" regardless of which folder is open, the same way `display.overview`'s own internal accordions never change it either | Same as workspace access | active |
| `display.files.design-builder.new-folder` | `<details>` (via `macros.subdisclosure`) | "+ New Folder" | Contains the create-folder form below | Same as workspace access | active |
| `display.files.design-builder.new-folder.name` | `<input type="text">` | Folder name | POSTs to `create_folder_route` (`parent_folder_id` = the currently open folder, or empty for root) | Same as workspace access | active |
| `display.files.design-builder.new-folder.create` | `<button>` | "Create Folder" | Submits the form above | Same as workspace access | active |
| `display.files.design-builder.folder-list` | `<ul>` | — | Contains one `display.files.design-builder.folder-row` per child folder of the currently open folder (or the root) | Same as workspace access | active |
| `display.files.design-builder.folder-row` | `<li>` (pattern) | Folder name | Real navigation to `?view=files&folder=<id>` — drills into that folder. Contains the contextual action menu below | Same as workspace access | active |
| `display.files.design-builder.folder-row.options` | `<summary>` (pattern, `<details>`) | "⋮" (aria-label "Folder options for `<name>`") | Opens the contextual Rename/Move/Delete panel for that row | Same as workspace access | active |
| `display.files.design-builder.folder-row.rename.name`, `display.files.design-builder.folder-row.rename.submit` | `<input>`/`<button>` (pattern) | Rename form | POSTs to `rename_folder_route` — sibling-name uniqueness enforced server-side | Same as workspace access | active |
| `display.files.design-builder.folder-row.move.destination`, `display.files.design-builder.folder-row.move.submit` | `<select>`/`<button>` (pattern) | Move form | POSTs to `move_folder_route` — the `<select>`'s own options are server-computed per row (`design_builder_move_targets`) to exclude the folder itself and its own descendants, on top of `move_folder`'s independent, authoritative re-validation | Same as workspace access | active |
| `display.files.design-builder.folder-row.delete` | `<button>` (pattern) | "Delete" | POSTs to `delete_folder_route` — the confirm=yes/no gate below, never an immediate delete | Same as workspace access | active |
| `display.files.design-builder.empty` | `<p>` | "This folder is empty."/"No folders yet…" | Empty-state message, phrased differently for an open subfolder vs. the Design-Builder Workspace root itself | Same as workspace access | active |
| `display.files.design-builder.folder.delete.confirm-yes`, `display.files.design-builder.folder.delete.confirm-no` | `<button>` (`templates/confirm_delete_folder.html`) | "Yes — delete this folder" / "No — keep this folder" | The confirm=yes/no interruption page (same family as `confirm_remove_document.html`) — only reachable after `delete_folder_route`'s own empty-folder check would otherwise pass | Same as workspace access | active |
| `display.context-menu` | `#display-context-menu` (CLAUDE-P40-VW8-QA — formally registered; existed since CLAUDE-P40-E3A) | Right-click menu for the targeted division — Close/Divide | Hidden by default; opens via `contextmenu` on a `.display-division`, targets whichever one was clicked | Same as workspace access | active |
| `display.context-menu.close` | `<button>` | "Close this Display" | Clears the targeted division, reflows remaining divisions (VW4's deterministic shrink rule) | Same as workspace access | active |
| `display.context-menu.vertical-decrement`, `display.context-menu.vertical-increment`, `display.context-menu.horizontal-decrement`, `display.context-menu.horizontal-increment` | `<button>` (4 distinct, named controls) | −/+ steppers | Adjust the PENDING Vertical/Horizontal count for "Divide this Display" | Same as workspace access | active |
| `display.context-menu.apply` | `<button>` | "Apply" | Commits the pending Vertical × Horizontal count | Same as workspace access | active |

## Toolbox (`templates/case_workspace.html`)

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `toolbox.panel` | `#workspace-toolbox-panel` (`<aside>`, `templates/base.html`) | The panel container itself — always present within an open Workspace, empty elsewhere. CLAUDE-P40-EYE1: no longer owns its own width/background/scroll (moved to `#workspace-right-column`, below) — the upper pane inside that column, sized by the Toolbox/Eye divider | Only rendered when `project_id`/`workspace` are defined | active |
| `toolbox.maximize` | `<button aria-pressed>` (new, CLAUDE-P40-EYE1) | "Maximize Toolbox" / "Restore" | Expands Toolbox toward the right column's practical maximum (keeping whatever proportion was active immediately before, on the toggle-back click); floats over the pane's own top-right corner rather than a new header row, since `toolbox.heading` already occupies that position | Only rendered when `project_id`/`workspace` are defined | active |
| `toolbox.heading` | `<h2>` | "Toolbox" — static | — | active |
| `toolbox.investigation-findings` | `<section>` | Rendered when an Investigation is the active selection (`active_case`) — Findings list, artifacts, RFI actions | Findings filtered to `findings_view` (already access/visibility-scoped) | active |
| `toolbox.document` | `<section>` | Rendered when a Document is the active selection (`selected_source`) — Document-level tools | Same as workspace access | active |
| `toolbox.empty` | `<section>` | Rendered when neither an Investigation nor a Document is selected — concise neutral empty state, points to Documents/Investigations/Project Tools in Lists | — | active |

## Right column: Toolbox above Eye (`templates/base.html`, CLAUDE-P40-EYE1)

Mirrors the Lists/Thumbnails split (CLAUDE-P40-VW7A-QA2) on the opposite
side — `#workspace-right-column` is now the full-height column (a
sibling of Lists AND `.workspace-main-column` inside `.app-shell-body`,
spanning the same vertical extent as Display+Chat, never stopping at
the Display/Chat divider), containing Toolbox (upper, see above) and
the new Eye pane (lower) split by a draggable divider. The existing
`shell.toolbox-divider` show/hide control (see the Shell section above)
now collapses/restores this WHOLE column, not Toolbox alone, **and**
(product-owner browser correction) is also a real mouse-draggable/
keyboard-operable WIDTH resize handle for the column — a genuine drag
is distinguished from a plain click via a movement threshold, so the
existing collapse/show behavior is unchanged for an ordinary click.
Eye itself is a structural scaffold only this stage (Section 4's own
explicit boundary) — a heading, a neutral empty state, and a real (not
decorative) paste/drop target with a responsive zoom/pan viewing canvas
(browser correction, Section 3) that previews an image in-session with
no persistence, no editing, no annotation, and no AI interpretation.

`shell.toolbox-divider`'s own row (Shell section above) already documents this extended behavior in full — not repeated as a second row here to avoid a duplicate ref in the registry.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `shell.toolbox-eye-divider` | `<div role="separator">` (new) | (unlabeled divider) | Draggable (pointer + arrow-key) horizontal split between Toolbox and Eye; percentage-based, `localStorage`-persisted per-Project (matching Toolbox's own existing show/hide preference scoping); double-click restores the default 60/40 split; never `[hidden]` — Eye is a permanent pane, only the split proportion is adjustable | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.panel` | `<div>` (new) | "Eye" (header text) | The whole pane; contains the heading, the maximize toggle, and the drop target | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.heading` | `<h2>` (new) | "Eye" — static | — | active |
| `eye.maximize` | `<button aria-pressed>` (new) | "Maximize Eye" / "Restore Eye" | **Two-dimensional** (product-owner browser correction): collapses Toolbox toward its practical minimum (height) AND expands the right column to its largest practical width (via `shell.toolbox-divider`'s own resize logic) in one action; restores BOTH dimensions exactly on the toggle-back click. The maximized width is deliberately never persisted, so a mid-maximize page reload can't leave the reviewer stuck there | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.drop-target` | `<div role="group">` (new) | "Paste or drop an image here to preview it." (empty state) | A real drop target: `static/js/eye_pane.js` handles `dragover`/`drop`/`paste`, reads an image file via `FileReader`, and hands it to `eye.canvas` (below) for display — held only in this tab's own memory until the reviewer explicitly saves it (`eye.canvas.save`, below). Non-image drops/pastes show an inline error, not a silent failure. Dropping/pasting a new image while one is shown replaces it. **CLAUDE-MM5** turned this from a structural-scaffold-only preview into the real governed visual-evidence surface Section 7 describes — see `eye.canvas.save`/`.rotate`/`.mirror-h`/`.mirror-v` below | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas` | `<div>` (new, product-owner browser correction) | — | The responsive image-viewing canvas — `[hidden]` until an image is loaded, then fills `eye.drop-target`'s own available area (not a small fixed thumbnail). Contains the view-control toolbar and `eye.canvas.viewport` | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.zoom-out`, `eye.canvas.zoom-in` | `<button>` (new) | − / + | Multiplies/divides the current scale by 1.25, clamped 5%–800%; switches to manual (non-auto-refitting) mode | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.fit` | `<button>` (new) | "Fit" | Scales the image to fill the viewport on whichever axis is tighter, preserving aspect ratio (not capped at 100% — a small image is scaled UP to use the available area too); the initial view for every newly-loaded image | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.actual-size` | `<button>` (new) | "1:1" | Sets scale to exactly 100% (the image's real pixel size); switches to manual mode | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.reset` | `<button>` (new) | "Reset" | Returns to Fit (same target as `eye.canvas.fit`) and re-centers, AND (CLAUDE-MM5) clears any rotate/mirror view state back to identity | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.rotate` | `<button>` (new, CLAUDE-MM5) | ↻ | Rotates the UNSAVED preview 90° clockwise per click, cumulative — a view-only CSS transform, nothing persisted (Section 4/11) | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.mirror-h`, `eye.canvas.mirror-v` | `<button>` (new, CLAUDE-MM5) | ↔ / ↕ | Toggles a horizontal/vertical view-only mirror on the UNSAVED preview | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.remove` | `<button>` (new) | "Discard preview" (CLAUDE-MM5 relabel — was "Remove") | Clears the loaded, UNSAVED preview, returning `eye.drop-target` to its neutral empty state. Has no effect once the image is saved (`eye.canvas.save`, below) — the saved Source is real project data, not a discardable preview | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.save` | `<button>` (new, CLAUDE-MM5) | "Save to project" | Uploads the real, original file bytes (never the transformed/rotated view) to `POST /api/v1/documents/<project_id>/eye-capture`; on success, replaces this pane's content with the SAME real drawing/image viewer MM4 built (`static/js/drawing_image_viewer.js`), now backed by a persisted Source with full rotate/mirror/region-select/citation | Only rendered when `project_id`/`workspace` are defined | active |
| `eye.canvas.viewport` | `<div>` (new) | — | The actual scroll/pan surface — the image is sized to its real scaled pixel dimensions (never CSS percentage-based sizing, so no stretching/distortion at any zoom); native browser scroll is the pan mechanism (keyboard/touch/trackpad all work for free); mouse-wheel/trackpad zoom is active only while this element itself has focus; a `ResizeObserver` recalculates Fit automatically whenever its own container is resized or Eye is maximized/restored, but only while still in Fit mode — a deliberate manual zoom is never silently overridden | Only rendered when `project_id`/`workspace` are defined | active |

## Chat (`templates/_macros.html`'s `conversation_dock` macro + `templates/case_workspace.html`)

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `chat.dock` | `#chat-region` (`templates/base.html`) | The whole Chat surface (dock header, resize handle, thread, composer) — full application width, bottom row of the shell | Only rendered when `project_id`/`workspace` are defined | active |
| `chat.thread` | `.conversation-thread` (pattern — case-scoped and project-scoped share this same reference) | The scrollable message list; case-scoped when an Investigation is open, project-scoped otherwise (mutually exclusive) | Same as workspace access | active |
| `chat.composer` | `<form>` | Posts a new message — to `post_message` (case-scoped) or `quick_start` (project-scoped) | Same as workspace access | active |
| `chat.selection-toolbar` | `#conv-selection-toolbar` (CLAUDE-P40-VW7; moved/reparented CLAUDE-P40-VW8-QA — see note below) | The contextual toolbar on a meaningful text selection — Add Tag/Make Task/Highlight/Important/Question/Copy. Positioned beside the live selection, vertical (one action per row), hidden whenever nothing meaningful is selected | Same as workspace access (server-side re-checked on every mutation) | active |
| `chat.selection-toolbar.tag`, `chat.selection-toolbar.task`, `chat.selection-toolbar.highlight`, `chat.selection-toolbar.important`, `chat.selection-toolbar.question`, `chat.selection-toolbar.copy` | `<button>` (6 distinct, named actions) | toolbar action buttons | See `chat.selection-toolbar`'s own row — one reference per action | Same as workspace access | active |
| `chat.selection-toolbar.remove-tag` | `<button>` (CLAUDE-P40-VW8-QA, reversibility correction) | "Remove Tag (N)" — hidden unless 1+ non-built-in Tag occurrences overlap the selection; opens `chat.remove-tag-dialog` | Same as workspace access | active |
| `chat.selection-toolbar.remove-highlight`, `chat.selection-toolbar.unmark-important`, `chat.selection-toolbar.unmark-question` | `<button>` (JS-toggled state — CLAUDE-P40-VW8-QA) | The SAME physical `.highlight`/`.important`/`.question` buttons, with `data-conv-action`/`data-ui-ref`/label swapped to this "remove" identity only while that built-in Tag is currently applied to the selection (`applyAppliedTagState` in `static/js/case_workspace.js`) — never both identities on the same element at once, and never inherited from the add/apply reference (a distinct id per state, per the correction's own explicit requirement) | Same as workspace access | active (rendered conditionally, by JS, not statically in template source — not picked up by the static template scan, hence not in this file's own automated consistency test) |
| `chat.selection-toolbar.undo` | `#conv-selection-undo` (CLAUDE-P40-VW8-QA) | Short-lived (8s) Undo for the most recent Tag/Highlight/Important/Question removal — re-POSTs the same add-Tag route with the removed occurrence's own tag id + anchor fields | Same as workspace access | active |
| `chat.remove-tag-dialog` | `#conv-remove-tag-dialog` (CLAUDE-P40-VW8-QA) | "Remove Tag" dialog — lists every currently-applied custom Tag on the selection (name + swatch, never color alone), each with its own Remove | Same as workspace access | active |
| `chat.selection-toolbar.applied-tags-list` | `#conv-remove-tag-list` (CLAUDE-P40-VW8-QA) | The list itself, inside `chat.remove-tag-dialog` | Same as workspace access | active |
| `chat.tag-dialog` | `#conv-tag-dialog` (CLAUDE-P40-VW7) | "Add Tag" dialog — existing/custom tag + color picker | Same as workspace access | active |
| `chat.task-dialog` | `#conv-task-dialog` (CLAUDE-P40-VW7) | "Make Task" dialog — editable title | Same as workspace access | active |
| `chat.composer.input` | `<input>` | the ONE conversation composer's text field | Posts to `post_message`/`quick_start` on submit | Same as workspace access | active |
| `chat.composer.send` | `<button>` | "Send" | Submits `chat.composer.input`'s form | Same as workspace access | active |
| `chat.tag-highlight` | `<mark class="tag-highlight-inline">` (pattern, CLAUDE-P40-VW8-QA, Section 11) | inline tagged-text treatment | Rendered by `app.py`'s own `hotlinks` filter around the exact tagged substring of a persisted message — the corrected "Add Tag has no visible consequence" defect. `data-tag-occurrence-id` disambiguates which occurrence; `data-tag-id`/`data-tag-name` added (CLAUDE-P40-VW8-QA, reversibility correction) for client-side applied-state detection | Same as workspace access (never rendered for a message the reviewer can't already see) | active |
| `chat.dock.label` | *(retired — CLAUDE-P40-VW7A-QA)* | A compact "Chat (N)" `<label>` briefly lived beside the composer input (moved down from the old top-of-panel heading) — the immediate product-owner follow-up rejected it as a duplicate of the Lists panel's own "Chats" row (which now carries the count instead, via `lists.project.chats` — see Lists section below). Nothing renders this reference any more; retired rather than reused for a different control | — | retired |

**`chat.selection-toolbar*` — moved/reparented, not replaced (CLAUDE-P40-VW8-QA):**
the HTML (`#conv-selection-toolbar`, its `hidden` attribute) and the
JS (`static/js/case_workspace.js` selection-tracking, anchor
computation, viewport-clamped positioning, per-action availability,
Escape/outside-click/selection-clear close handling, real Tag/Task
dialog + built-in-tag POST wiring for Highlight/Important/Question,
clipboard Copy) were already correct — audited end to end, none of
the 6 actions were decorative or inert. The one real defect was
`static/css/main.css`'s `.conv-selection-toolbar` rule having no
`[hidden]` override, so the class's `display: flex` beat the `hidden`
attribute at equal cascade specificity and the toolbar rendered
permanently regardless of what the JS correctly set — the same bug
CLASS as the R3 tokens.css comment-boundary regression. Fixed by
adding `.conv-selection-toolbar[hidden] { display: none; }` and
changing the layout to `flex-direction: column` (one action per row,
per product-owner request) with `text-align: left` on
`.conv-selection-btn`. All six `chat.selection-toolbar*` identifiers
above are retained unchanged — their meaning did not change, only
their visibility bug and row/column arrangement did.

**Native-popup-overlap correction (same identifiers, no new ones):**
a browser/OS-owned text-selection popup (most identifiably Microsoft
Edge's own "mini menu on text selection," `edge://settings/appearance`
→ "Show mini menu when I select text," or the enterprise
`QuickSearchShowMiniMenu` policy) is not created by, mergeable into, or
controllable from this page — no `contextmenu` listener exists in this
toolbar's own setup (confirmed by reading `static/js/case_workspace.js`
in full; the file's one `contextmenu` listener is the unrelated
Display-division picker). `positionToolbar` now prefers BELOW the
selection first (was: above first) specifically to sit on the opposite
side from where that native popup conventionally appears, and a new
`repositionOrHideOnViewportChange` (bound to `window`'s `scroll`,
capture phase, and `resize`) keeps the toolbar correctly placed — or
hides it — if the containing panel scrolls or the viewport resizes
while a selection is held, which nothing previously handled. Copy was
already, and remains, fully self-sufficient (copies the complete
captured selection text), so a reviewer never needs the native popup
for ordinary copying.

## Gateway (`templates/gateway_shell.html`, `gateway.html`, `project_chooser.html` — CLAUDE-P40-VW8-QA, new surface)

Gateway/the chooser render inside `gateway_shell.html`, never `base.html`
— no Lists/Display/Toolbox/Chat exists here, and none of these
references may ever start with `lists.`/`display.`/`toolbox.`/`chat.`/
`menu.` (see `tests/test_p40vw7a_ui_reference_map.py`'s own
`SignInGatewayIsolationTests`, which asserts exactly this).

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `gateway.account` | `<details>` popup | "…" (username) | Contains UI Reference Mode toggle, Removed Projects, admin-only Security, Sign out | Every authenticated page (this shell only renders post-login) | active |
| `gateway.create-client-owner` | `<a>` | "Create Client / Owner Project" | Navigates to `portal.upload?environment=client_owner` | **Admin only** — `is_admin` | active |
| `gateway.create-design-builder` | `<a>` | "Create Design-Builder / Proponent Project" | Navigates to `portal.upload?environment=design_builder_proponent` | **Admin only** — `is_admin` | active |
| `gateway.open-existing` | `<a>` | "Open an existing project" | Navigates to `portal.choose_project` (the focused chooser, below) — **CLAUDE-P40-VW8-QA:** previously `portal.projects_list`, the full management directory; that page is unchanged and still reachable directly, just no longer Gateway's own first destination (Section 12) | Every authenticated page | active |
| `gateway.chooser` | `<h2>` | "Open an existing project" | Section heading, non-interactive | Every authenticated page | active |
| `gateway.chooser.search` | `<form>` | project search | `?q=` filter, server-side, same `_accessible_documents` matching `projects_list` uses; preserves `?current=` (below) via a hidden field so searching never drops the Current Project context | Every authenticated page (results scoped to `_accessible_documents`) | active |
| `gateway.chooser.leaf` | `<a>` (pattern) | a Project card | Navigates to `workspace.show_workspace` for that Project — the exact same authorized route every other Project-opening path uses | Filtered to `_accessible_documents` (already access-scoped) | active |
| `gateway.chooser.current` | `<section>` (new, CLAUDE-P40-VW7B) | "Current Project" | This route/template is now also the Project Vestibule (Section 4) — only rendered when arriving with a valid, authorized `?current=<project_id>` (set by `menu.context.switch-project`, below); a soft display hint, never a new persisted "current project" concept or an authorization boundary of its own | Every authenticated page; `current` silently ignored if unauthorized/stale/omitted | active |
| `gateway.chooser.current.leaf` | `<a>` | Current Project's own card, "Currently entered" badge | Re-enters the same already-open Project via `workspace.show_workspace` — a plain link, no confirmation (workspace state is safely persisted per-Project already; see `menu.context.switch-project`'s own note on why no interruption dialog guards this) | Same as `gateway.chooser.leaf` | active |
| `gateway.chooser.available` | `<p>` (new, CLAUDE-P40-VW7B) | "Available Projects" | Section label shown only alongside `gateway.chooser.current` — the current Project is excluded from this list below it, never duplicated | Every authenticated page | active |
| `gateway.chooser.removed-projects` | `<a>` (new, CLAUDE-P40-VW7B) | "Removed Projects" | Navigates to `portal.removed_projects` — Section 4's own "Archived or removed Projects... only if this is already a real governed concept," linked out to the real page rather than duplicated inline | Every authenticated page | active |
| `gateway.chooser.back` | `<a>` | "← Back to Gateway" | Navigates to `portal.gateway` | Every authenticated page | active |

## Auth (`templates/auth_shell.html`, `login.html` — CLAUDE-P40-VW8-QA, new surface)

Pre-authentication. `auth_shell.html` has no toggle of its own (the
Account menu the toggle lives in only exists once authenticated) — it
only ever HONORS an already-enabled `beehive:ui-reference-mode`
preference set during a previous authenticated session (a device/
browser preference, unaffected by sign-out), never sets one.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `auth.signin.username` | `<input>` | "Username" | Sign-in form field | Pre-authentication | active |
| `auth.signin.password` | `<input type="password">` | "Password" | Sign-in form field | Pre-authentication | active |
| `auth.signin.submit` | `<button>` | "Sign in" | Submits the sign-in form | Pre-authentication | active |

## Upload / Project creation (`templates/upload.html`, `templates/errors/error.html` — CLAUDE-P40-VW8-QA, Project-Creation Upload-Capacity Correction)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `upload.limits` | `<p>` | (accepted formats/size copy) | States accepted formats, `MAX_CONTENT_LENGTH`-derived max size, and the scanned-drawing-package processing limitation, before any file is chosen | `portal.upload` — **admin only** | active |
| `upload.error` | `<p>` | (server-side error text) | Renders `UploadError`/`GovernanceError` messages from a rejected POST | Same as above | active |
| `upload.client-size-error` | `<p>` | (client-side size-check text) | Hidden until the chosen file exceeds the max; JS-populated, never server-rendered | Same as above | active |
| `upload.operating-environment.client_owner` | `<input type="radio">` | "Client / Owner" | Selects the Client/Owner Project Operating Environment | Same as above | active |
| `upload.operating-environment.design_builder_proponent` | `<input type="radio">` | "Design-Builder / Proponent" | Selects the Design-Builder/Proponent Project Operating Environment | Same as above | active |
| `upload.project-name` | `<input>` | "Project name" | Optional display name; defaults to the filename | Same as above | active |
| `upload.file` | `<input type="file">` | (file picker) | Carries `data-max-upload-bytes`/`data-max-upload-mb`, read by the client-side size-check script | Same as above | active |
| `upload.actor` | `<input>` | "Your name" | Optional free-text audit-trail field | Same as above | active |
| `upload.role` | `<input>` | "Your role" | Optional free-text audit-trail field | Same as above | active |
| `upload.submit` | `<button>` | "Create project and parse document" | Submits the upload form | Same as above | active |
| `errors.upload-too-large` | `<a>` | "Choose a different file" | The 413 error page's own return action, back to `portal.upload` — no Project/Document/workspace is ever created for a request that hits this handler (Werkzeug rejects it before the view function runs) | Every request path (413 can occur pre-authentication-check on a route, though `/upload` itself is admin-only) | active |
| `upload.confirm.no-native-text-notice` | `<p>` | (image-only-PDF notice) | States that no text could be automatically read (Section 6's honest-degradation report) — never rendered for a document with real extractable text | `portal.upload_confirm` — **admin only** | active |
| `upload.confirm.no-candidates-notice` | `<p>` | (no-candidates notice) | States that no title-block-style fields were detected, when the file had real text but nothing matched a known field pattern | Same as above | active |
| `upload.confirm.error` | `<p>` | (server-side error text) | Renders `UploadError`/`GovernanceError` from a rejected confirm POST | Same as above | active |
| `upload.confirm.name-conflict` | `<fieldset>` | "Project name — conflicting values found" | Only rendered when the user-entered name and the drawing-derived candidate name differ — requires an explicit choice (Section 4: "present both... require an explicit choice") | Same as above | active |
| `upload.confirm.name-conflict.entered`, `upload.confirm.name-conflict.candidate`, `upload.confirm.name-conflict.custom` | `<input type="radio">` | (the three name choices) | Selects which Project name to use — never a silent default | Same as above | active |
| `upload.confirm.name-conflict.custom-input` | `<input>` | (custom name) | Free-text Project name, used only when the "different name" radio is selected | Same as above | active |
| `upload.confirm.fields` | `<fieldset>` | "Drawing-derived details" | Wraps every candidate field input | Same as above | active |
| `upload.confirm.field.project_name`, `upload.confirm.field.project_number`, `upload.confirm.field.project_address`, `upload.confirm.field.owner_client`, `upload.confirm.field.drawing_title`, `upload.confirm.field.sheet_number`, `upload.confirm.field.discipline`, `upload.confirm.field.consultant`, `upload.confirm.field.issue_date`, `upload.confirm.field.revision`, `upload.confirm.field.scale` | `<div>` (one per `services/drawing_intake.py`'s `CANDIDATE_FIELDS`) | (field label) | One row per candidate field (`project_name` only rendered here when not in conflict — see `upload.confirm.name-conflict` above) | `portal.upload_confirm` — **admin only** | active |
| `upload.confirm.field.project_name.input`, `upload.confirm.field.project_number.input`, `upload.confirm.field.project_address.input`, `upload.confirm.field.owner_client.input`, `upload.confirm.field.drawing_title.input`, `upload.confirm.field.sheet_number.input`, `upload.confirm.field.discipline.input`, `upload.confirm.field.consultant.input`, `upload.confirm.field.issue_date.input`, `upload.confirm.field.revision.input`, `upload.confirm.field.scale.input` | `<input>` | (field value) | Editable — a machine candidate is always a proposal, never authoritative on its own (Section 5) | Same as above | active |
| `upload.confirm.field.project_name.evidence`, `upload.confirm.field.project_number.evidence`, `upload.confirm.field.project_address.evidence`, `upload.confirm.field.owner_client.evidence`, `upload.confirm.field.drawing_title.evidence`, `upload.confirm.field.sheet_number.evidence`, `upload.confirm.field.discipline.evidence`, `upload.confirm.field.consultant.evidence`, `upload.confirm.field.issue_date.evidence`, `upload.confirm.field.revision.evidence`, `upload.confirm.field.scale.evidence` | `<small>` | (evidence text) | Shows confidence, source page, extraction method, and the exact matched line — only rendered when a candidate was actually found for that field | Same as above | active |
| `upload.confirm.submit` | `<button>` | "Confirm and create Project" | Submits the confirm form — creates the Project from confirmed/corrected values via the same `ingest_upload` every other upload path uses | Same as above | active |
| `upload.confirm.discard` | `<button>` | "Discard and start over" | Discards the staged upload (raw bytes + candidates) and returns to `/upload` | Same as above | active |

---

## Security Department (`templates/security_department.html` — CLAUDE-P40-VW8-QA, Complete Root and Subfolder UI Reference Tagging)

An "equivalent root/subfolder on an administrative page" per this stage's own explicit scope — reached via `lists.security` (admin only). Each top-level accordion is a real, distinct governed record family (mirrors the Lists tree's own "one toggle per family" shape, via `templates/_macros.html`'s `accordion`/`subdisclosure` macros, both extended this stage with an optional `ui_ref` parameter — backward-compatible; every pre-existing caller that omits it, including every Overview-page accordion in `case_workspace.html`, is unaffected and deliberately left untagged, consolidated under `display.overview` per CLAUDE-P40-E3A). Refs are macro CALL ARGUMENTS (`ui_ref='security.floor'`) — the literal `data-ui-ref="..."` attribute text only exists inside the macro body itself, not in this template's own source.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `security.floor` | `<details class="accordion-section">` | "Mandatory ARCHIOSK Security Floor" | Always expanded by default; read-only — no configurable action can weaken it | **Admin only** — `security.department_home` route | active |
| `security.claims` | `<details class="accordion-section">` | "Security Claims Registry" | What this deployment can/cannot truthfully promise | Same as above | active |
| `security.baselines` | `<details class="accordion-section">` | "Organization Security Baseline" | Draft/activate/withdraw baselines; add per-action control decisions | Same as above | active |
| `security.policies` | `<details class="accordion-section">` | "Source Policies" | Lists ingested policies; each may record a policy statement | Same as above | active |
| `security.policies.add` | `<details class="add-source-details">` (nested inside `security.policies`) | "+ Ingest a source policy" | POST (multipart) to `security.record_source_policy` | Same as above | active |
| `security.controls` | `<details class="accordion-section">` | "Proposed Controls" | Lists proposed control decisions | Same as above | active |
| `security.controls.add` | `<details class="add-source-details">` (nested inside `security.controls`) | "+ Propose a control" | POST to `security.propose_control` | Same as above | active |
| `security.qa` | `<details class="accordion-section">` | "Governed Q&A" | Lists recorded Q&A entries; provisional ones may be approved | Same as above | active |
| `security.qa.add` | `<details class="add-source-details">` (nested inside `security.qa`) | "+ Record a Q&A entry" | POST to `security.record_qa_entry` | Same as above | active |
| `security.exceptions` | `<details class="accordion-section">` | "Exceptions" | Lists active/expired exceptions; active ones may be revoked | Same as above | active |
| `security.exceptions.add` | `<details class="add-source-details">` (nested inside `security.exceptions`) | "+ Grant an exception" | POST to `security.grant_exception` | Same as above | active |
| `security.projects` | `<details class="accordion-section">` | "Projects" | Per-Project security-profile classification | Same as above | active |
| `security.learning` | `<details class="accordion-section">` | "Learning Contribution Requests" | Records governed intent only — no shared-learning pipeline exists in this deployment | Same as above | active |
| `security.learning.add` | `<details class="add-source-details">` (nested inside `security.learning`) | "+ Request a learning contribution review" | POST to `security.create_learning_request` | Same as above | active |
| `security.assurance-activity` | `<details class="accordion-section">` | "Assurance — Activity" | Read-only governance-event activity log (actor/project/action/decision only — no project content) | Same as above | active |
| `security.self-check` | `<details class="accordion-section">` | "Assurance — Self-Check" | Read-only automated consistency findings | Same as above | active |

## Projects Directory (`templates/projects.html` — CLAUDE-P40-VW8-QA, Complete Root and Subfolder UI Reference Tagging)

The full administrative Project-management page (`portal.projects_list`) — distinct from `gateway.chooser` (the focused picker) and from `lists.projects`/`lists.projects.leaf` (the Lists-tree root); reachable directly by URL and via `removed-projects.back-link`. A different top-level prefix (`projects-directory`, not `projects`) deliberately avoids reading as a sub-family of `lists.projects`, which it isn't.

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `projects-directory.removed-link` | `<a>` | "Removed Projects" | Navigates to `portal.removed_projects` | Every authenticated page | active |
| `projects-directory.search` | `<form>` | project search | `?q=` filter | Every authenticated page | active |
| `projects-directory.list` | `<ul>` | the Project card list | Wraps every `projects-directory.leaf` row | Filtered to `_accessible_documents` (already access-scoped) | active |
| `projects-directory.leaf` | `<a>` (pattern) | a Project card | Navigates to `workspace.show_workspace` for that Project | Same as above | active |
| `projects-directory.leaf.delete` | `<button>` in a `<form>` (pattern) | "Delete" | POST to `portal.delete_project` | **Admin only** — `is_admin` | active |
| `projects-directory.empty` | `<div>` | "No projects yet." / "No projects match…" | Empty/no-results state; admin-only "Create New Project" link when genuinely empty | Every authenticated page | active |

## Removed Projects (`templates/removed_projects.html` — CLAUDE-P40-VW8-QA, Complete Root and Subfolder UI Reference Tagging)

Reached via `lists.removed-projects`. A different top-level prefix from `lists.removed-projects` itself (that ref is the Lists-tree LINK to this page, not the page's own content).

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `removed-projects.back-link` | `<a>` | "← Back to Projects" | Navigates to `portal.projects_list` | Every authenticated page | active |
| `removed-projects.list` | `<ul>` | the removed-Project card list | Wraps every `removed-projects.leaf` row | Every authenticated page | active |
| `removed-projects.leaf` | `<li>` (pattern — not a link; a removed Project has no workspace to navigate to) | a removed Project card | Non-interactive except its own Restore button | Every authenticated page | active |
| `removed-projects.leaf.restore` | `<button>` in a `<form>` (pattern) | "Restore" | POST to `workspace.restore_project_route` | Every authenticated page | active |
| `removed-projects.empty` | `<div>` | "No removed Projects." | Empty state | Every authenticated page | active |

---

## Deliberately NOT instrumented this stage

Per-instance content inside a family (a single Finding card, a single
`ReviewThread` comment inside `toolbox.investigation-findings`, a
single Appearance-matrix radio, a single Display-Layout stepper
button) — these are either per-record data (not stable UI controls in
the sense this registry tracks) or fine-grained widgets inside an
already-referenced family/dialog. Add a reference for any of these
only when a future stage needs to individually track, preserve, or
retire one — this registry stays proportional to what VW7B and beyond
actually need to cite, not maximal coverage for its own sake.

## Retired references

| Reference | Retired by | Reason | Replacement |
|---|---|---|---|
| `lists.project.tools.data-management` | CLAUDE-P40-VW7B | Nested inside the active Project's own "Project Tools" branch, but `portal.reset_project_data` operates on the whole `REGISTRY_STORE_PATH` — every Project in the deployment, not this one. Misrepresented scope, evidenced by reading that route directly before moving anything (Section 3's own "Administrative/account functions do not automatically belong inside the active Project root") | `lists.system-data-management` (same route, same admin-only gate, same `html_id="project-data-management"` — only position and reference id changed) |

Future stages: when a control this map names is genuinely removed (not
just renamed/reparented — see the ID scheme note above), move its row
here with the stage that retired it and why, and never reuse the same
`data-ui-ref` value for a different control afterward.

## Known gap, not yet fixed

This map is hand-maintained, like `MANIFEST.md` — nothing here is
auto-synced from the templates. `tests/test_p40vw7a_ui_reference_map.py`
enforces that every `data-ui-ref` value actually present in
`templates/base.html`/`case_workspace.html`/`_macros.html` has a
matching row here (and vice versa, for `active`-status rows), but that
test cannot catch a row whose *description* has drifted from actual
behavior — treat any specific behavioral claim above with the same
"verify against the actual file before relying on it" caution
`MANIFEST.md`'s own header asks for.
