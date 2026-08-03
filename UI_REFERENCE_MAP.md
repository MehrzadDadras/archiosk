# UI Reference Map

**CLAUDE-P40-VW7A**, updated by **CLAUDE-P40-VW7B**. A stable-ID
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
| `menu.brand` | `<a>` | "Archiosk" | Navigates to `portal.index` (`/`) | Every authenticated page | active |
| `menu.context` | `<span>` | breadcrumb (Project / Investigation / Document / Overview) | Non-interactive, reflects current page state | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout` | `<details>` popup | "Display Layout" | Vertical/Horizontal steppers + Apply — sets `#display-divisions`' grid via `window.ArchioskDisplay`-adjacent client JS (`applyLayout` in `case_workspace.js`) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout.vertical-decrement`, `menu.display-layout.vertical-increment`, `menu.display-layout.horizontal-decrement`, `menu.display-layout.horizontal-increment` | `<button>` (4 distinct, named controls) | −/+ steppers | Adjust the PENDING Vertical/Horizontal count (not yet applied) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.display-layout.apply` | `<button>` | "Apply" | Commits the pending Vertical × Horizontal count to `#display-divisions` | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance` | `<details>` popup | "Appearance" | Per-surface (All/Menu/Lists/Display/Toolbox/Chat) Light/Dark/Tinted radio matrix, `localStorage`-persisted | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.all` | `<tr>` | "All" row | **CLAUDE-P40-VW8-QA (new):** applies one mode to all 5 surfaces at once; reflects "checked" only when all 5 already share one mode, otherwise unchecked with `#appearance-mixed-note` shown (Section 5 — never a 4th theme, a control over the existing 3) | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.all.light`, `menu.appearance.all.dark`, `menu.appearance.all.tinted` | `<input type="radio">` (3 distinct values, constructed from a fixed `{% for %}` loop — see `UI_REFERENCE_MAP.md`'s own test-side `_APPEARANCE_DYNAMIC_REFS` enumeration) | "All surfaces appearance: `Light`/`Dark`/`Tinted`" | Sets every surface (Menu/Lists/Display/Toolbox/Chat) to that mode in one action | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.menu`, `menu.appearance.lists`, `menu.appearance.display`, `menu.appearance.toolbox`, `menu.appearance.chat` | `<tr>` (5 distinct values, one per real surface) | per-surface row | Groups that surface's own 3 radios | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.appearance.menu.light`, `menu.appearance.menu.dark`, `menu.appearance.menu.tinted`, `menu.appearance.lists.light`, `menu.appearance.lists.dark`, `menu.appearance.lists.tinted`, `menu.appearance.display.light`, `menu.appearance.display.dark`, `menu.appearance.display.tinted`, `menu.appearance.toolbox.light`, `menu.appearance.toolbox.dark`, `menu.appearance.toolbox.tinted`, `menu.appearance.chat.light`, `menu.appearance.chat.dark`, `menu.appearance.chat.tinted` | `<input type="radio">` (15 distinct values: 5 surfaces × 3 modes) | "`<Surface>` appearance: `<Mode>`" | Sets that ONE surface's mode; `beehive:appearance:<surface>` in `localStorage` | Only rendered when `project_id`/`workspace` are defined | active |
| `menu.account` | `<details>` popup | "…" (username) | Contains UI Reference Mode toggle + Sign out | Every authenticated page | active |

## Shell (structural chrome — `templates/base.html`)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `shell.lists-divider` | `<button>` | (unlabeled divider) | Collapses/shows the Lists panel; `localStorage`-persisted, reviewer-wide | Every authenticated page | active |
| `shell.toolbox-divider` | `<button>` | (unlabeled divider) | Collapses/shows the Toolbox; `localStorage`-persisted, per-Project | Only rendered when `project_id`/`workspace` are defined | active |

## Lists — cross-Project (`templates/base.html`, reviewer-wide)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.projects` | tree-toggle `<button>` | "Projects" | Expands/collapses the Projects root; auto-open whenever a Project is open or `/projects` is the current page | Every authenticated page | active |
| `lists.projects.leaf` | tree-leaf `<a>` (pattern) | Project display name | Navigates to that Project's own workspace (`workspace.show_workspace`) — only for a Project that is **not** the currently active one (the active one instead expands into `lists.project.self` and its branch, below) | Filtered to `nav_recent_projects` (already access-scoped) | active |
| `lists.new-project` | tree-leaf `<a>` | "+ New Project" | Navigates to `portal.upload` | **Admin only** — `is_admin` | active |
| `lists.removed-projects` | tree-leaf `<a>` | "Removed Projects" | Navigates to `portal.removed_projects` | Every authenticated page | active |
| `lists.security` | tree-leaf `<a>` | "Security" | Navigates to `security.department_home` | **Admin only** — `is_admin` | active |
| `lists.system-data-management` | `<a>` inside a subdisclosure | "Reset Project Data…" | Navigates to `portal.reset_project_data`. **CLAUDE-P40-VW7B:** relocated here from the active Project's own "Project Tools" branch (`lists.project.tools.data-management`, retired — see below) — the route resets `REGISTRY_STORE_PATH` in full ("returns the app to a clean, no-project state"), every Project in the deployment, not the one whose tools branch it used to sit in | **Admin only** — `is_admin` | active |
| `lists.project-switch-dialog` | `<div role="dialog">` | (dialog, no visible label — `aria-labelledby` its own heading) | **CLAUDE-P40-VW8:** interruption dialog shown when activating `lists.projects.leaf` for a Project other than the one currently open. Rendered only when `project_id is defined` (a Project is already open) | Same access scope as the page it renders on | active |
| `lists.project-switch-dialog.stay` | `<button>` | "Stay in Current Project" | Closes the dialog; no navigation | Same as above | active |
| `lists.project-switch-dialog.switch` | `<button>` | "Switch in This Tab" | Navigates the current tab to the pending target Project's own already-authorized `workspace.show_workspace` URL | Same as above | active |
| `lists.project-switch-dialog.open-new-tab` | `<button>` | "Open in New Tab" | Opens the pending target Project's URL via `window.open`; shows `#project-switch-popup-note` if the browser blocks the popup, leaving the current tab untouched | Same as above | active |

## Lists — active Project branch (`templates/base.html`, only inside the currently open Project's own row)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.project.self` | tree-leaf `<a>`, `active` | active Project's own display name | Navigates to its own workspace (a no-op — already there); this row is what expands into every entry below | Same as `_load_workspace_or_404` (project owner/allow-list/admin) | active |
| `lists.project.overview` | tree-leaf `<a>`, `data-view="overview"` | "Overview" | **Division 0 is the active target (default):** real navigation to `?view=overview`. **A non-zero Display is the active target (CLAUDE-P40-VW7B):** client-side-intercepted, no navigation — projects into that division via `window.ArchioskDisplay.populateDivision(target, 'overview', '', 'Overview')`, an `<iframe src="...?view=overview&panel=1">`. Either way the content is `display.overview`, below | Same as workspace access | active |
| `lists.project.documents` | tree-toggle `<button>` | "Documents (`<count>`)" | Expands/collapses; count = `active_sources\|length`; "No Documents yet." empty state (CLAUDE-P40-VW7B) | Same as workspace access | active |
| `lists.project.documents.leaf` | tree-leaf `<a>`, `data-source-id` (pattern) | Document name | **Division 0 active target:** real navigation to `?source=<id>`. **Non-zero Display active target:** client-side `populateDivision(target, 'source', sourceId, name)` — unchanged since VW7A, a real file embedded via `<iframe src=file_url>`/`<img>`, never the `&panel=1` mechanism. Syncs Toolbox to `toolbox.document` | Same as workspace access | active |
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
| `lists.project.chats` | tree-leaf `<a>` | "Chats" | Navigates to the bare workspace URL (no `?source=`/`?case=`) — renders Project Conversation (`chat.thread`, project scope) | Same as workspace access | active |
| `lists.project.tasks` | tree-toggle `<button>` | "Tasks (`<total>`)" | Expands/collapses; contains `lists.project.tasks.open`/`.completed` sub-groups | Same as workspace access | active |
| `lists.project.tasks.open` | sub-heading `<p>` | "Open (`<count>`)" | Not a toggle — plain grouping label | — | active |
| `lists.project.tasks.completed` | sub-heading `<p>` | "Completed (`<count>`)" | Not a toggle — plain grouping label | — | active |
| `lists.project.tasks.leaf` | tree-leaf `<a>`/`<span>` (pattern) | Task title | Navigates to `#conv-source-<message_id or guidance>` on the correct workspace URL (`_conversation_source_url`) — scrolls/flashes the source passage. Renders as an unavailable `<span>` (no link) when the source anchor no longer resolves | Same as workspace access | active |
| `lists.project.tasks.complete` | `<button>` in a `<form>` (pattern) | "Mark complete" | POST to `complete_task_route`, classic redirect | Same as workspace access | active |
| `lists.project.tasks.reopen` | `<button>` in a `<form>` (pattern) | "Reopen" | POST to `reopen_task_route`, classic redirect | Same as workspace access | active |
| `lists.project.tags` | tree-toggle `<button>` | "Tags (`<total occurrences>`)" | Expands/collapses; contains one `lists.project.tags.group` per tag in use | Same as workspace access | active |
| `lists.project.tags.group` | sub-heading `<p>` (pattern) | tag name + color swatch + occurrence count | Not a toggle — plain grouping label; always expanded (`data-tree-open`) | — | active |
| `lists.project.tags.leaf` | tree-leaf `<a>`/`<span>` (pattern) | quoted passage (truncated) | Navigates to `#conv-source-<...>` — same scroll/flash mechanism as Tasks. Renders unavailable when the anchor no longer resolves | Same as workspace access | active |
| `lists.project.tags.remove` | `<button>` in a `<form>` (pattern) | "Remove" | `fetch()` POST to `remove_tag_occurrence_route`, live-patches counts/DOM without reload | Same as workspace access | active |
| `lists.project.tools` | tree-toggle `<button>` | "Project Tools" | Expands/collapses; contains every control below. **CLAUDE-P40-VW7B:** no longer contains Reset Project Data — see `lists.system-data-management` above and "Retired references" below | Same as workspace access (individual controls below carry their own, narrower gates) | active |
| `lists.project.tools.remove-project` | `<button>` in a `<form>` | "Remove Project" | POST to `remove_project_route` (Approval-Gate `confirm=yes\|no` vocabulary) | **Owner or admin** — `is_project_owner or is_admin` | active |
| `lists.project.tools.add-document` | `<form>` inside a subdisclosure | "+ Add Documents" | POST (multipart) to `add_document_source` | Same as workspace access | active |
| `lists.project.tools.add-text-record` | `<form>` inside a subdisclosure | "+ Add Text Record" | POST to `add_text_record_source` | Same as workspace access | active |
| `lists.project.tools.add-external-source` | `<p>` inside a subdisclosure | "+ Add External Source" | **Not implemented** — static "not yet available" text, no form | Same as workspace access | active |
| `lists.project.tools.removed-items` | `<ul>`/`<p>` inside a subdisclosure | "Removed Items (`<count>`)" | Lists removed Documents in this Project (or "No removed Documents…") | Same as workspace access | active |
| `lists.project.tools.removed-items.restore` | `<button>` in a `<form>` (pattern) | "Restore Document" | POST to `restore_document_route` | Same as workspace access | active |

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
| `display.context-menu` | `#display-context-menu` (CLAUDE-P40-VW8-QA — formally registered; existed since CLAUDE-P40-E3A) | Right-click menu for the targeted division — Close/Divide | Hidden by default; opens via `contextmenu` on a `.display-division`, targets whichever one was clicked | Same as workspace access | active |
| `display.context-menu.close` | `<button>` | "Close this Display" | Clears the targeted division, reflows remaining divisions (VW4's deterministic shrink rule) | Same as workspace access | active |
| `display.context-menu.vertical-decrement`, `display.context-menu.vertical-increment`, `display.context-menu.horizontal-decrement`, `display.context-menu.horizontal-increment` | `<button>` (4 distinct, named controls) | −/+ steppers | Adjust the PENDING Vertical/Horizontal count for "Divide this Display" | Same as workspace access | active |
| `display.context-menu.apply` | `<button>` | "Apply" | Commits the pending Vertical × Horizontal count | Same as workspace access | active |

## Toolbox (`templates/case_workspace.html`)

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `toolbox.panel` | `#workspace-toolbox-panel` (`<aside>`, `templates/base.html`) | The panel container itself — always present within an open Workspace, empty elsewhere | Only rendered when `project_id`/`workspace` are defined | active |
| `toolbox.heading` | `<h2>` | "Toolbox" — static | — | active |
| `toolbox.investigation-findings` | `<section>` | Rendered when an Investigation is the active selection (`active_case`) — Findings list, artifacts, RFI actions | Findings filtered to `findings_view` (already access/visibility-scoped) | active |
| `toolbox.document` | `<section>` | Rendered when a Document is the active selection (`selected_source`) — Document-level tools | Same as workspace access | active |
| `toolbox.empty` | `<section>` | Rendered when neither an Investigation nor a Document is selected — concise neutral empty state, points to Documents/Investigations/Project Tools in Lists | — | active |

## Chat (`templates/_macros.html`'s `conversation_dock` macro + `templates/case_workspace.html`)

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `chat.dock` | `#chat-region` (`templates/base.html`) | The whole Chat surface (dock header, resize handle, thread, composer) — full application width, bottom row of the shell | Only rendered when `project_id`/`workspace` are defined | active |
| `chat.thread` | `.conversation-thread` (pattern — case-scoped and project-scoped share this same reference) | The scrollable message list; case-scoped when an Investigation is open, project-scoped otherwise (mutually exclusive) | Same as workspace access | active |
| `chat.composer` | `<form>` | Posts a new message — to `post_message` (case-scoped) or `quick_start` (project-scoped) | Same as workspace access | active |
| `chat.selection-toolbar` | `#conv-selection-toolbar` (CLAUDE-P40-VW7) | The OneNote-style contextual toolbar on a meaningful text selection — Add Tag/Make Task/Highlight/Important/Question/Copy | Same as workspace access (server-side re-checked on every mutation) | active |
| `chat.selection-toolbar.tag`, `chat.selection-toolbar.task`, `chat.selection-toolbar.highlight`, `chat.selection-toolbar.important`, `chat.selection-toolbar.question`, `chat.selection-toolbar.copy` | `<button>` (6 distinct, named actions) | toolbar action buttons | See `chat.selection-toolbar`'s own row — one reference per action | Same as workspace access | active |
| `chat.tag-dialog` | `#conv-tag-dialog` (CLAUDE-P40-VW7) | "Add Tag" dialog — existing/custom tag + color picker | Same as workspace access | active |
| `chat.task-dialog` | `#conv-task-dialog` (CLAUDE-P40-VW7) | "Make Task" dialog — editable title | Same as workspace access | active |
| `chat.composer.input` | `<input>` | the ONE conversation composer's text field | Posts to `post_message`/`quick_start` on submit | Same as workspace access | active |
| `chat.composer.send` | `<button>` | "Send" | Submits `chat.composer.input`'s form | Same as workspace access | active |
| `chat.tag-highlight` | `<mark class="tag-highlight-inline">` (pattern, CLAUDE-P40-VW8-QA, Section 11) | inline tagged-text treatment | Rendered by `app.py`'s own `hotlinks` filter around the exact tagged substring of a persisted message — the corrected "Add Tag has no visible consequence" defect. `data-tag-occurrence-id` disambiguates which occurrence | Same as workspace access (never rendered for a message the reviewer can't already see) | active |

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
| `gateway.chooser.search` | `<form>` | project search | `?q=` filter, server-side, same `_accessible_documents` matching `projects_list` uses | Every authenticated page (results scoped to `_accessible_documents`) | active |
| `gateway.chooser.leaf` | `<a>` (pattern) | a Project card | Navigates to `workspace.show_workspace` for that Project — the exact same authorized route every other Project-opening path uses | Filtered to `_accessible_documents` (already access-scoped) | active |
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
