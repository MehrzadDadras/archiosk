# UI Reference Map

**CLAUDE-P40-VW7A.** A stable-ID registry over the application's Menu,
Lists, Display, Toolbox, and Chat surfaces — the traceability layer
future stages (starting with CLAUDE-P40-VW7B) use to know what a
control currently is, means, and does before renaming, reparenting, or
retiring it. This document is a durable record, updated alongside the
code, the same way `MANIFEST.md` and `CONTINUATION_CHECKPOINT.md` are.

## What this is, and isn't

This stage is purely additive and instrumentation-only: every control
below already existed before VW7A: nothing was renamed, moved, or
behaviorally changed to build this registry. A `data-ref="<id>"`
attribute was added directly on the existing element — never a new
wrapper element, never a change to an existing `id`/class/route/href.
`git diff` against the VW7A commit shows only `data-ref="..."`
insertions (plus the new UI Reference Mode toggle itself and its CSS/
JS) — confirm this before trusting any claim below that a control's
behavior is unchanged.

**Turn on UI Reference Mode** (Account menu, top-right, "UI Reference
Mode" checkbox) to see every instrumented control's own `data-ref`
value rendered as a small badge directly on the page — the fastest way
to cross-check this document against the live app. Off by default; a
reviewer/device preference (`localStorage`), never a Project record.

## ID scheme

Dot-separated, lowercase, kebab-case-within-segment, hierarchical:
`<surface>.<family>[.<subfamily>][.<kind>]`.

Surfaces: `menu` (top bar), `lists` (left panel), `display` (main
projection area), `toolbox` (right contextual panel), `chat` (bottom
conversation dock), `shell` (structural chrome — panel dividers).

**A `data-ref` value identifies a KIND of control, not one instance.**
For a repeating pattern (a Document leaf, a Task row, a Project row),
every rendered instance shares the same `data-ref` — the existing
per-instance attributes (`data-source-id`, `data-task-id`,
`data-tag-occurrence-id`, the leaf's own `href`) still disambiguate
which one, exactly as they did before this stage. This is a query
selector convention, not an HTML `id` — uniqueness is not implied or
required, and none of the code that reads `data-ref` (only the CSS
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
| `menu.appearance` | `<details>` popup | "Appearance" | Per-surface (Menu/Lists/Display/Toolbox/Chat) Light/Dark/Tinted radio matrix, `localStorage`-persisted | Only rendered when `project_id`/`workspace` are defined | active |
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

## Lists — active Project branch (`templates/base.html`, only inside the currently open Project's own row)

| Reference | Element | Label | Current behavior | Auth notes | Status |
|---|---|---|---|---|---|
| `lists.project.self` | tree-leaf `<a>`, `active` | active Project's own display name | Navigates to its own workspace (a no-op — already there); this row is what expands into every entry below | Same as `_load_workspace_or_404` (project owner/allow-list/admin) | active |
| `lists.project.overview` | tree-leaf `<a>` | "Overview" | Navigates to `?view=overview` — fills Display division 0 with the Project Briefing/Project State content (`display.overview`, below) | Same as workspace access | active |
| `lists.project.documents` | tree-toggle `<button>` | "Documents (`<count>`)" | Expands/collapses; count = `active_sources\|length` | Same as workspace access | active |
| `lists.project.documents.leaf` | tree-leaf `<a>` (pattern) | Document name | Navigates to `?source=<id>` — fills Display division 0 with Document content, syncs Toolbox to `toolbox.document` | Same as workspace access | active |
| `lists.project.investigations` | tree-toggle `<button>` | "Investigations (`<count>`)" | Expands/collapses; count = `visible_cases\|length` | Same as workspace access, further filtered to `visible_cases` (Case-privacy-aware) | active |
| `lists.project.investigations.leaf` | tree-leaf `<a>` (pattern) | Investigation title | Navigates to `?case=<id>` — fills Display division 0 with Investigation content, syncs Toolbox to `toolbox.investigation-findings` | Same as `visible_cases` | active |
| `lists.project.rfis` | tree-toggle `<button>` | "RFIs (`<count>`)" | Expands/collapses; count = `rfi_drafts_view\|length` | Same as workspace access | active |
| `lists.project.rfis.leaf` | tree-leaf `<a>` (pattern) | RFI question text (truncated) | Navigates to the **owning Investigation's** `?case=<id>` (an RFI draft has no standalone page — deliberate, documented since CLAUDE-P40-E3A) | Same as workspace access | active |
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
| `lists.project.tools` | tree-toggle `<button>` | "Project Tools" | Expands/collapses; contains every control below | Same as workspace access (individual controls below carry their own, narrower gates) | active |
| `lists.project.tools.remove-project` | `<button>` in a `<form>` | "Remove Project" | POST to `remove_project_route` (Approval-Gate `confirm=yes\|no` vocabulary) | **Owner or admin** — `is_project_owner or is_admin` | active |
| `lists.project.tools.add-document` | `<form>` inside a subdisclosure | "+ Add Documents" | POST (multipart) to `add_document_source` | Same as workspace access | active |
| `lists.project.tools.add-text-record` | `<form>` inside a subdisclosure | "+ Add Text Record" | POST to `add_text_record_source` | Same as workspace access | active |
| `lists.project.tools.add-external-source` | `<p>` inside a subdisclosure | "+ Add External Source" | **Not implemented** — static "not yet available" text, no form | Same as workspace access | active |
| `lists.project.tools.removed-items` | `<ul>`/`<p>` inside a subdisclosure | "Removed Items (`<count>`)" | Lists removed Documents in this Project (or "No removed Documents…") | Same as workspace access | active |
| `lists.project.tools.removed-items.restore` | `<button>` in a `<form>` (pattern) | "Restore Document" | POST to `restore_document_route` | Same as workspace access | active |
| `lists.project.tools.data-management` | `<a>` inside a subdisclosure | "Reset Project Data…" | Navigates to `portal.reset_project_data` | **Admin only** — `is_admin` | active |

## Display (`templates/case_workspace.html`)

| Reference | Element | Current behavior | Auth notes | Status |
|---|---|---|---|---|
| `display.divisions` | `#workspace-display-panel` | The whole Display surface — 1-6 divisions (VW4's independent Vertical/Horizontal axes), managed by `window.ArchioskDisplay` (`case_workspace.js`) | Same as workspace access | active |
| `display.division` | `.display-division` (pattern — division 0 is always server-rendered/real navigation; divisions 1-5 are client-side-only slots) | Shows whichever record is currently projected into it (Investigation/Document/Overview for division 0; a Document only, via `display.division.picker`, for 1-5) | Division 0: same as workspace access. Divisions 1-5: can only ever load a Document already in `active_sources` (same authorization, enforced by `workspace.source_file`) | active |
| `display.division.picker` | `<select>` (pattern, divisions 1-5 only) | "Open a Document here…" — populates that division client-side via `window.ArchioskDisplay.populateDivision` | Options limited to `active_sources` | active |
| `display.division.close` | `<button>` (pattern, divisions 1-5 only) | Clears that division, shrinks the Vertical/Horizontal layout by one (VW4's deterministic shrink rule) | — | active |
| `display.overview` | `#project-overview` | The Overview leaf's actual content: Operating Environment, Access/Settings, Needs Attention, Recent Focus, Investigation Quality, Participants, Go/No-Go, Accepted Knowledge, Instructions, Requirement Compliance, RFIs, Requirements, Key Dates, History — all consolidated under this one leaf (CLAUDE-P40-E3A, Section 5) | Same as workspace access | active |

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
| `chat.tag-dialog` | `#conv-tag-dialog` (CLAUDE-P40-VW7) | "Add Tag" dialog — existing/custom tag + color picker | Same as workspace access | active |
| `chat.task-dialog` | `#conv-task-dialog` (CLAUDE-P40-VW7) | "Make Task" dialog — editable title | Same as workspace access | active |

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

None yet — this is VW7A's first version of the registry. Future
stages: when a control this map names is genuinely removed (not just
renamed/reparented — see the ID scheme note above), move its row here
with the stage that retired it and why, and never reuse the same
`data-ref` value for a different control afterward.

## Known gap, not yet fixed

This map is hand-maintained, like `MANIFEST.md` — nothing here is
auto-synced from the templates. `tests/test_p40vw7a_ui_reference_map.py`
enforces that every `data-ref` value actually present in
`templates/base.html`/`case_workspace.html`/`_macros.html` has a
matching row here (and vice versa, for `active`-status rows), but that
test cannot catch a row whose *description* has drifted from actual
behavior — treat any specific behavioral claim above with the same
"verify against the actual file before relying on it" caution
`MANIFEST.md`'s own header asks for.
