# Spare Parts Yard — Components Parked from an Active Surface

**Distinct from `deferred-reserved/reservations.md`** (gaps this project has
never designed) **and from `specified-unbuilt/`** (concepts fully designed but
never built). Everything named here was already built, working, tested code
that was deliberately unassigned from a user-facing surface — the code itself
still exists in git history at the commit named below; nothing here requires
re-implementation, only a decision about where it should be reachable again.

Lifecycle grammar (Product Owner, `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01`):

- **Active** — deployed and assigned to a current surface.
- **Reserve / Spare Parts Yard** — useful capability or component preserved
  but not currently assigned to an active user-facing surface. *(this file)*
- **Prototype** — tested/experimental assembly.
- **Future** — sufficiently shaped future concept preserved for later
  promotion (→ `specified-unbuilt/`).
- **Scrap** — obsolete/disproven/unsafe and genuinely safe to delete.

Nothing in this file is Scrap. Every item below still has its real,
unmodified route and store method in the current codebase — only its
*visible entry point* was removed.

---

## 1. "+ Add Text Record"

- **Status:** Reserve / Spare Parts Yard.
- **Was:** a left-rail "Project Tools" subdisclosure form (title + freeform
  content → a real, governed `Source` of `kind="text_record"`).
- **Route (unchanged, still real):** `workspace.add_text_record_source`,
  `POST /projects/<project_id>/workspace/sources/text-record`.
- **Removed from:** `templates/base.html`'s rail, commit
  `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01` (this stage).
- **Reason parked:** the left rail must remain a compact project/evidence
  navigation surface, not an action drawer — Product Owner: "the left rail
  is principally project switching + project/evidence navigation, not an
  action drawer or administration panel." Unlike "+ Add Documents," no
  decided new home (Admin/elsewhere) was named for this one specifically.
- **Promotion/reassignment trigger:** a later Product Owner decision
  establishing the correct surface for freeform-note evidence capture
  (candidates not yet evaluated: alongside Add Documents on Project Data
  Management; a GO-conversational intake path per
  `governance/specified-unbuilt/` future-intake work; its own dedicated
  surface).

## 2. "+ Register a Document Revision"

- **Status:** Reserve / Spare Parts Yard.
- **Was:** a left-rail "Project Tools" subdisclosure listing every
  revisable (non-drawing, non-superseded) active Source with a per-Source
  upload form to register a new revision.
- **Route (unchanged, still real):** `workspace.revise_document_source`,
  `POST /projects/<project_id>/workspace/sources/<source_id>/revise`.
- **Removed from:** `templates/base.html`'s rail, same commit as above.
- **Reason parked:** same rail-compactness rationale as Add Text Record
  above; no decided new home named this stage.
- **Promotion/reassignment trigger:** same as Add Text Record — a later
  Product Owner decision. Revision registration is closely related to
  Archive Documents (both are governed changes to the evidence set), so
  Project Data Management is a plausible future home, not yet decided.

## 3. "+ Add External Source"

- **Status:** Reserve / Spare Parts Yard — but already inert before this
  stage (worth naming honestly: there was no real capability behind this
  entry to protect). Its own content was always the static message "Not
  yet available — no external source connector is configured for this
  deployment" (`SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR` is a named enum
  value in `services/case_workspace.py`'s `KNOWN_SOURCE_ORIGIN_TYPES`, but
  nothing in this codebase has ever set it — confirmed during
  `CLAUDE-RFP27-TERRITORY-01`'s own Bug Eye governance research this same
  session).
- **Removed from:** `templates/base.html`'s rail, same commit as above.
- **Reason parked:** same rail-compactness rationale; recorded here for
  completeness of the historical "Project Tools" set, not because real
  functionality needs protecting.
- **Promotion/reassignment trigger:** whenever an actual external-source
  connector is built (a real future project, not scoped by this record).

## Not parked — promoted to a new Active home instead

For contrast, two former "Project Tools" items were **not** parked here —
the Product Owner named a real, decided new home for them:

- **"+ Add Documents"** → Active on Admin → Project Data Management
  (`templates/reset_project_data.html`'s own "Add documents to project"
  section), reusing the identical `workspace.add_document_source` route.
- **"Removed Items"** (view + restore already-archived Documents) →
  Active, merged into Project Data Management's own "Archive documents"
  section, reusing the identical `workspace.remove_document_route` /
  `workspace.restore_document_route` routes.

Both are now admin-gated (`portal.reset_project_data` is
`@admin_required`) where they were previously reachable by any authorized
project participant — a real, deliberate authorization narrowing that
follows directly from the Product Owner's own "belongs under Admin"
framing, not an oversight. See `CLAUDE-PROJECT-SURFACE-CONSOLIDATION-01`'s
own commit message for the full record.

## "Files" — not parked, not retired, de-duplicated only

The left rail's own "Files" leaf was removed, but this is **not** a Spare
Parts Yard entry: the underlying capability (`workspace.show_workspace`'s
`?view=files` — the real, governed Data Room/Design-Builder folder view
built in `CLAUDE-RFP27-TERRITORY-01`) stays fully **Active**, reachable via
Overview's own independent, pre-existing `display.overview.files-link`
("Open Files →"). Removing the rail's own copy is de-duplication, not a
lifecycle change.

## "Whole-Main scroll while a PDF is active" — narrowed, not retired

**Status:** the general mechanism stays fully **Active**; only its
application to one specific content shape was scoped out. Not a
component with its own route/store method, so it doesn't fit this file's
usual entry shape exactly, but recorded here per Product Owner instruction
(`CLAUDE-MAIN-DISPLAY-SCROLL-SIMPLIFICATION-01`) since it is genuine
retired *behavior*.

- **Was:** `main`'s own `overflow-y: auto` (`CLAUDE-P40-VW8-QA` — "the ONE
  scroll region for every page's actual content") made the ENTIRE Display
  area, including an already-independently-scrollable PDF canvas
  (`.document-viewer-canvas-container`, fixed `height: 70vh`, its own
  `overflow: auto`), a second nested vertical scroll surface. Reported live
  as two visible scrollbars stacked side by side while viewing a multipage
  PDF — the outer one redundant and, per the Product Owner, unwanted
  ("the document moves, the workspace does not").
- **Retired:** `main`'s whole-content scroll, but **only** in the specific
  state where `.document-viewer-canvas-container` is present as a
  descendant (`main:has(.document-viewer-canvas-container) { overflow-y:
  hidden; }`, `static/css/main.css`). A real mechanism removal (the scroll
  container itself stops existing in that state), not a cosmetic
  scrollbar hide.
- **Preserved / reusable concept:** `main`'s own base rule (`CLAUDE-P40-
  VW8-QA`'s "Menu must stay visible while content scrolls, one shared
  central rule rather than scattered per-page overrides") is untouched and
  still governs every other page — Investigation, Overview, forms, Project
  Data Management, Chat, etc. all still rely on it exactly as before. The
  reusable DNA here is the `:has()`-scoped-override pattern itself (already
  used elsewhere in this file — `.conversation-thread:has(...)`,
  `.files-folder-row:has(...)`) as the general technique for "one shared
  ancestor rule, narrowed for one specific descendant content shape"
  without forking the ancestor rule into two competing near-duplicates.
- **Promotion/reassignment trigger:** none anticipated — this is the
  intended permanent state for the PDF-viewing case. Would only need
  revisiting if a future stage gives `.document-viewer-canvas-container`
  itself a non-fixed height (currently `70vh`, independent of `main`'s own
  height), which could reopen the same double-scroll question from a
  different root cause.

## Real image/shape/visual document search — Future Reserve

- **Status:** Future (not yet built at all, not a parked/removed component
  — recorded here per Product Owner instruction,
  `CLAUDE-DOCUMENT-RAIL-SEARCH-01` Part 10).
- **Intended PM workflow:** in the left rail's Image search mode (`static/
  js/document_marks.js`'s own image tray — paste/drop/preview/collapse
  states are real and already built), the PM supplies a shape, symbol,
  graphic detail fragment, or visual pattern (pasted, dropped, or —
  eventually — captured directly from an open Document/drawing via an
  existing ARCHIOSK capture path such as Eye's own paste/drop or a
  Snapshot) and ARCHIOSK returns other Documents/drawings in the SAME
  project containing a visually similar condition — the same purpose
  Bluebeam VisualSearch serves, not its literal appearance.
- **Why it is deferred — a real, checked absence, not an assumption:**
  `services/image_intelligence.py`'s own header comment states the
  existing capability boundary explicitly: "no facial recognition, no
  object/defect detection, no OCR over arbitrary image content, no
  panorama stitching, no filters/artistic effects — this module reads
  EXIF metadata and pixel dimensions only, never interprets what an
  image DEPICTS." No visual-feature extraction, embedding, or similarity-
  matching capability exists anywhere in this codebase today (checked
  services/image_intelligence.py, services/drawing_intelligence.py,
  services/case_workspace.py) — there is nothing to safely expose now.
  Faking this with OCR-text matching (Part 10's own explicit prohibition)
  or filename/dimension heuristics would misrepresent a real evidence-
  discovery claim as genuine visual matching, which this project's own
  "never fabricate/hide evidence silently" principle forbids.
- **Required capability, if built:** a real visual-feature index — at
  minimum, per-page/per-sheet image embeddings (or an equivalent
  hand-built shape/symbol-matching pipeline) computed at ingestion time
  and persisted (mirroring the "genuinely new extraction+storage work,
  not a per-search re-parse" conclusion this same stage's own text-
  search audit reached for document content) — plus a similarity query
  path from a pasted/dropped query image against that index, scoped to
  the active project only.
- **Evidence types involved:** drawing/image Sources primarily (`kind=
  "drawing"`), and potentially PDF page rasters for drawing sets embedded
  in PDF form — the same universe `services/drawing_intelligence.py` and
  `services/image_intelligence.py` already govern.
- **Future mixed text+image direction (Part 11):** once both a real text
  index (see the companion note this same audit would add if content
  search is ever built) and a real visual index exist, a combined query
  such as "image sample + text condition" (e.g. a pasted door-hardware
  symbol + `secure courtroom`) becomes a straightforward intersection of
  the two result sets — the Image tray's own architecture (a persisted
  query image, independent of the Text field) already leaves room for
  this without a redesign; nothing about today's UI needs to change to
  add it later, only a real backend to call.
- **Promotion trigger:** a future Product Owner decision to invest in a
  real visual-indexing pipeline (a genuinely new capability, not a small
  extension) — until then, Image mode's own "Search" action stays an
  honest deferred state (`#documents-image-search-status`), never a
  fabricated result list.
