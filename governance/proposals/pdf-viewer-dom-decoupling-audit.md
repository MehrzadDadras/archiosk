# Proposal — PDF Viewer DOM Decoupling Audit

**Status:** Audit only. No runtime code or template was modified to produce it.
Every count below was measured against the working tree, not carried over from a
prior record.

**Question asked:** what is the smallest clean adapter/event contract that lets
the PDF drawing canvas operate headlessly, or under canvas-native controls
(`surface-vs-substrate-interaction-grammar.md` §5.3), while keeping current
behaviour intact?

**Answer in one line:** the engine is already decoupled — the coupling is
concentrated in two initialization gates and one toolbar-binding block, all
outside the render pipeline, and the repository already contains a working
example of the target architecture.

---

## 0. Correcting the premise this audit was commissioned under

The commissioning brief, and `surface-vs-substrate-interaction-grammar.md` §2.6,
describe **30 `getElementById` bindings that couple the drawing canvas to
`base.html` chrome**. The count is exact. The characterisation needs one
correction, because it changes what the work is.

**The bindings do not couple the canvas. They couple the toolbar.** Not one of
the 35 chrome elements is touched by the render pipeline, the viewport
lifecycle, or the geometry math. The canvas is passed **as a parameter** to
`mount(url, el, filename, sourceId)`, and the surface engine was already
extracted into a reusable factory by `CLAUDE-DUAL-DOCUMENT-FOCUS-01`.

The second correction is that the failure mode is not what §2.6 implies. §2.6
says that in a chrome-less render the controls "are all `null` … and the file's
own comment confirms this degrades silently." Per-control null-guarding does
exist for the *optional* controls, but it is never reached, because two hard
gates run first:

| Line | Gate | Effect if unmet |
|---|---|---|
| `pdf_viewer.js:67` | `container = getElementById('workspace-document-controls')`, then `if (!container) return;` | **Entire module returns.** No factory, no `window.ArchioskPdfViewer`, no auto-mount. |
| `pdf_viewer.js:100` | `if (!prevBtn ...  !nextBtn ... !pageInput ... !zoomOutBtn ... !zoomInBtn ... !searchInput) return;` | **Entire module returns.** Six specific chrome controls are mandatory. |

So a chrome-less render does not produce a degraded viewer with dead buttons. It
produces **no viewer at all**, and no public API for anything else to drive.
This is a better starting position than "30 scattered couplings," and a stricter
one: the work is not 30 edits, it is moving two gates.

---

## 1. Complete inventory

### 1.1 Totals, measured

| Measure | Value |
|---|---|
| `static/js/pdf_viewer.js` | 1,478 lines |
| `getElementById` calls | **48** |
| — resolving a literal `doc-*` id | **30** |
| — resolving a `doc-*` id dynamically (`:226–228`) | **5** |
| — resolving non-`doc-*` ids | **13** |
| `querySelector`-family calls | 3 |
| Distinct `doc-*` ids in `templates/base.html` | **35** |
| Set difference, either direction | **0** |

The 30/5 split is why the figure reads as 30: five annotation-tool buttons are
resolved in a loop over a literal id array rather than by individual calls. The
true chrome surface is **35 elements**, and it reconciles **exactly** with
`base.html` — every id the template defines is consumed, and every id the script
resolves exists. There are no orphans in either direction.

That zero/zero reconciliation is the single most important number in this audit,
and §3.5 returns to it.

### 1.2 Classification

**Essential viewer capability — viewport lifecycle, render pipeline, geometry
math: 0 of 35.**

There is no chrome element in the render path. The render pipeline receives its
DOM through arguments:

- the canvas container arrives as `mount()`'s `el` parameter
- thumbnail hosts arrive as `createPdfSurface(name, thumbnailsList,
  thumbnailsEmptyState)` parameters
- page geometry, zoom, rotation, mirror and scroll are closure state per surface

**Historical chrome coupling: 35 of 35.** Grouped by function:

| Group | Ids | Note |
|---|---|---|
| Page traversal | `doc-prev-page`, `doc-next-page`, `doc-page-input`, `doc-page-total` | 3 of 4 are hard-gated |
| Zoom / fit | `doc-zoom-in`, `doc-zoom-out`, `doc-zoom-level`, `doc-fit-width`, `doc-fit-page` | 2 of 5 hard-gated |
| Orientation | `doc-rotate`, `doc-mirror-h`, `doc-mirror-v`, `doc-reset-orientation`, `doc-orientation-status` | MM4; all null-guarded |
| Search | `doc-search-input`, `doc-search-prev`, `doc-search-next`, `doc-search-count` | input is hard-gated |
| Output | `doc-download`, `doc-print`, `doc-snapshot`, `doc-snapshot-status` | |
| Annotation | `doc-annotate-{text,highlight,ink,select}`, `doc-region-select`, `doc-annotate-{delete,undo,redo}`, `doc-annotation-status`, `doc-region-status` | Main-only by design |
| Layout containers | `doc-controls-overflow`, `doc-controls-overflow-panel`, `doc-controls-secondary` | responsive re-parenting, see §3.3 |

**The 13 non-`doc-*` bindings are a different category and must not be swept in
with the chrome.** Three sub-kinds:

- **Data carriers (7)** — `document-tab-strip` (×6) and
  `workspace-active-sources-data`. These are not controls; they are how the
  viewer learns `data-project-id`, `data-base-url` and the selected source id.
  `takeSnapshot()` and the API base URL both depend on them. **A headless
  surface still needs this data**, so these convert to injected configuration,
  not to events.
- **Focus targets (4)** — `workspace-display-panel` (×2), `eye-pane` (×2).
  Consumed by the focus state machine, all null-guarded.
- **Host / auto-mount (2 sites, plus 2 factory arguments)** —
  `toolbox-normal-content` and `toolbox-eye-thumbnails-panel`; plus
  `document-viewer-pdf-canvas` (`:1468`) and `thumbnails-list` /
  `thumbnails-empty-state` (`:1450`), which are call-site lookups feeding the
  factory's parameters — already the correct shape.

### 1.3 Related viewer scripts — the precedent already exists

| File | Lines | `getElementById` | Pattern |
|---|---|---|---|
| `pdf_viewer.js` | 1,478 | 48 | page-scoped singleton IIFE bound to one shared toolbar |
| `drawing_image_viewer.js` | 1,136 | **1** | **per-element `mount(imgEl)`, builds its own toolbar** |
| `eye_pane.js` | 736 | — | consumer of `ArchioskPdfViewer.createSurface` |
| `spatial_viewport.mjs` | 110 | — | — |

`drawing_image_viewer.js` is a comparably-sized, production, MM4-era viewer with
**one** `getElementById` — and that one is a data carrier
(`document-tab-strip`, `:96`), not a control. It constructs its own controls in
JS using the same `doc-control-btn` / `doc-zoom-level` /
`doc-orientation-status` **CSS classes** rather than the shared **ids**, and
exports `window.ArchioskDrawingImageViewer.mount` (`:1123`).

Its header comment states the contrast deliberately: *"Deliberately NOT a
page-scoped singleton IIFE the way pdf_viewer.js is (that file binds to ONE
top-menu `#workspace-document-controls` region shared by the whole page)."*

**The target architecture is not hypothetical, not unproven, and not foreign to
this codebase.** It is already running, in the same lineage, written under the
same discipline, for the sibling document type — and the class-not-id convention
it uses is the existing mechanism for a canvas-native control that inherits the
app's visual grammar without claiming the shared toolbar's identity.

---

## 2. The minimal interface / event boundary

### 2.1 What already exists

`createPdfSurface` (`:275`) returns an `api` object (`:1300–1327`) with roughly
30 members. The command half of the contract is **already complete**: `mount`,
`unmount`, `prevPage`, `nextPage`, `goToPage`, `zoomIn`, `zoomOut`, `fitWidth`,
`fitPage`, `rotate`, `mirrorHorizontal`, `mirrorVertical`, `resetOrientation`,
`searchStep`, `print`, `takeSnapshot`, `setActiveTool`, `undo`, `redo`, plus
accessors `hasDoc`, `getPage`, `getZoom`, `getSourceId`.

The toolbar block (`:1357–1440`) is already a thin dispatcher — every listener
is `var s = getFocused(); if (s) s.someMethod();`. **Nothing in that block needs
inventing; it needs relocating.**

### 2.2 What is missing — and it is small

Four members of the returned `api` reach *back* into chrome. These are the only
genuine leaks in the engine:

| Site | Leak | Consequence |
|---|---|---|
| `:453` | `searchQuery` read from `searchInput.value` when focused, else `''` | persistence reads chrome — see §3.1, a **confirmed** live defect |
| `:1297` | `setPageFromInput` falls back to writing `pageInput.value` | engine writes chrome |
| `onSearchEnter` (`:1316`) | falls back to reading `searchInput.value` | engine reads chrome |
| `refreshToolbar` (`:1245`) | writes `container.hidden`, `downloadLink.href`, `pageTotal`, plus four `update*Ui()` calls | the sync-down half, by design |

Plus `updateNavState` (`:513`), `showControls` / `hideControls` (`:510–511`) and
`updateOrientationStatus` (`:660`), each guarded by `isFocused()` — 13 gating
sites in total.

**The root cause of all four leaks is one thing: `searchQuery` and the displayed
page number are owned by the DOM instead of by the surface.** Fix that and the
leaks close as a consequence rather than as four separate patches.

### 2.3 The proposed contract

Smallest sufficient boundary — one new subscription method, one state shape, one
ownership move. No CustomEvent bus is required: a subscribe callback is smaller,
is synchronous, needs no event-name registry, and matches how
`ArchioskEyeLayout.refresh()` already works in this codebase.

```
createPdfSurface(name, opts) -> api

api.subscribe(listener) -> unsubscribe      // NEW: the only added member
api.setSearchQuery(str)                     // NEW: ownership moves into surface

// listener(state) receives one immutable snapshot:
state = {
  hasDoc, page, pageCount, canPrev, canNext,
  zoom, rotation, mirrorH, mirrorV,
  searchQuery, matchIndex, matchCount,
  downloadUrl, downloadFilename,
  activeTool, canUndo, canRedo,
  orientationText, regionText, annotationText, snapshotText
}
```

Every existing command method stays exactly as it is.

The surface emits `state` whenever it changes and **never touches a `doc-*`
element**. Consumers then become interchangeable:

- **`toolbar_binder`** — the existing 35 lookups, the two hard gates, the
  responsive re-parenting, and `getFocused()` dispatch. Subscribes, renders into
  `base.html`. Current behaviour preserved exactly.
- **canvas-native Look (§5.3)** — subscribes to the same snapshot and renders a
  transient page indicator that recedes when idle. Needs `page`, `pageCount`,
  `zoom` — all already computed.
- **headless** — subscribes to nothing. Drives via commands, reads via
  accessors.

`opts` carries the data currently scraped from `document-tab-strip`:
`{ projectId, baseUrl, thumbnailsList, thumbnailsEmptyState }`. See §4.1 for why
`opts` cannot simply replace the current positional parameters without a
deliberate test decision.

---

## 3. Hidden dependencies and hazards

**The brief asked for a strong case to falsify the assumption that this coupling
is accidental. The assumption does not survive.** Five independent lines of
evidence.

### 3.1 The persisted-state hazard — a CONFIRMED live defect, not just a decoupling trap

**Status: reproduced under control on 2026-08-28.** The reproduction record is
§3.1.1 below. This section originally recorded the finding as static-analysis
only; it is no longer provisional.

`saveViewStateNow` (`:443`) persists `searchQuery` as `searchInput.value` only
when the surface is focused, and as `''` otherwise. The `pagehide` handler
(`:1464`) flushes **every** surface, not just the focused one:

```
Object.keys(surfaces).forEach(function (n) { surfaces[n].saveViewStateNow(); });
```

An unfocused surface therefore evaluates `isFocused()` as false and persists
`searchQuery: ''` to `localStorage` for its own source. On the next load, `:1187`
restores that empty string.

**Consequence: closing the page while Eye holds focus appears to silently blank
Main's remembered search query for that document** — and vice versa.

It is a pre-existing defect independent of any decoupling work, and it is
*caused by* the DOM owning state the surface should own — the same root cause as
§2.2. A naive `el ? el.value : ''` decoupling would make it unconditional rather
than intermittent, which is precisely the trap the brief asked about.

### 3.1.1 Reproduction record

**Method.** The real `static/js/pdf_viewer.js` was loaded **unmodified** into a
Node process under a minimal DOM stub and driven through its own public API.
No logic was re-implemented: `saveViewStateNow`, the `pagehide` flush and
`loadViewState` are the shipped functions, executed as written. Because
`saveViewStateNow` is not on the public API, the only shipped path that reaches
it — the `pagehide` flush — is what the harness fires; no private state was
poked.

**Sequence.** Main mounts `source-A`; `doc-search-input` is set to `"door"`;
unload fires while Main is focused (baseline). Eye is then created, mounts
`source-B`, and takes focus via the shipped `setFocus('eye')`. **The search box
is never touched again.** Unload fires a second time.

| Step | Focus at unload | Persisted `source-A` `searchQuery` |
|---|---|---|
| Baseline | `main` | `"door"` |
| After focus switch | `eye` | `""` |

**Control.** The identical run with the single line `V.setFocus('eye')` removed
— Eye still created, still mounted, second unload still fired — preserves
`"door"`. The sole differentiator is the focus switch, which isolates the cause
to `isFocused()` inside `saveViewStateNow` (`:453`) rather than to the second
unload, to Eye's existence, or to Eye's own save.

**Reachability in the product.** `saveViewStateSoon` is triggered by page
change, zoom, rotate, mirror and page render (`:616, :622, :649, :674, :681,
:691, :749`) — **not** by typing in the search box. So a query is persisted
opportunistically by whatever the reviewer does next on Main, and is then
blanked at unload if Eye holds focus at that moment. Both halves are ordinary
use; neither requires an unusual sequence.

**Severity, stated honestly.** The lost value is a remembered convenience
restored at `:1187`, not evidence, provenance or governance state. No Source,
Finding, region or citation is affected. It is a real state-corruption defect of
low user-facing severity — recorded here because it *confirms the §2.2 root
cause* rather than because it is urgent on its own.

**Falsification note.** The harness's first run was **invalid and was
discarded**: it reported the same `""` outcome, but its baseline had never
stored `"door"` (`saveViewStateNow` is absent from the public API, so the setup
call silently did nothing). A first-ever write of `""` is not a blanking. The
result above is from the corrected harness, where the baseline is asserted
before the test proceeds and the run aborts if it is missing.

### 3.2 The single-toolbar constraint is an explicit Product Owner decision

`pdf_viewer.js`'s header states it directly: *"There is still exactly ONE
physical top toolbar (`#workspace-document-controls` — 'do not duplicate two
permanent full toolbars' is the Product Owner's own explicit constraint)."*

Any adapter permitting two consumers to render controls simultaneously must
reconcile with that constraint. This audit's boundary does not violate it — a
canvas-native indicator that *recedes when idle* is not a second permanent
toolbar, and §5.3 requires exactly that — but the constraint is real and binds
the design.

### 3.3 The responsive re-parenting moves real DOM nodes

`applyResponsiveState` (`:112–127`) physically re-parents
`#doc-controls-secondary` between the toolbar and the overflow panel below
900px, via `appendChild` / `insertBefore`. The comment is emphatic that this
moves *"the SAME DOM node … never a cloned duplicate, so every control keeps
exactly one physical identity regardless of viewport width."*

A second consumer cannot co-own those nodes. This behaviour belongs to
`toolbar_binder` and must not migrate into the engine.

### 3.4 The tool vocabulary lives in the template

`setActiveTool(btn.dataset.tool)` reads `data-tool` from `base.html:166–181`.
The identity of the tools — `text`, `highlight`, `ink`, `select`, `region` — is
**declared in markup, not in JavaScript**. A headless or canvas-native surface
has no `data-tool` attributes to read and must be given that vocabulary
explicitly. This is a real interface gap the current `api` does not express.

### 3.5 The reconciliation itself

35 ids in the template, 35 resolved by the script, **zero orphans in either
direction**. Accretion does not produce that. Accretion leaves dead ids in
templates and stale lookups in scripts. The header comment claims the property
outright — *"Every function below is called by a real button/input in that
region; nothing here is scaffolding for a control that doesn't exist yet"* — and
the measurement confirms it still holds.

**Conclusion.** The coupling is deliberate, documented, load-bearing for an
explicit Product Owner constraint, and internally consistent. It is *historical*
only in the narrow sense that `CLAUDE-P40-VW7A-QA` predates the canvas-native
ambition. It is **not accidental**, and any proposal treating it as debris to be
swept away is wrong on the evidence. §2.6's warning — *a meaningful share of the
permanent chrome is the implementation of Look, not accretion* — is confirmed by
this audit, not merely repeated by it.

---

## 4. The invisible refactor surface

"Invisible" must mean two things here: invisible to the user, **and** invisible
to the test suite. The second is far more constraining, and is the finding most
likely to be missed.

### 4.1 Six test files pin exact JavaScript source strings

`test_dual_document_focus_01.py`, `test_p40vw7a_qa_document_controls.py`,
`test_p40dtab1_document_tabs.py`, `test_p40lth1_persistent_lists_thumbnails.py`,
`test_p40vw7a_qa2_thumbnails_annotations_layout.py` and
`test_p40vw7b_qa1_pdf_getdocument_fix.py` read `pdf_viewer.js` as text and
assert on literal substrings. Pinned strings include:

```
"function createPdfSurface(name, thumbnailsList, thumbnailsEmptyState)"
"function getFocused() { return surfaces[window.__activeDocumentSurface]; }"
"var m = surfaces.main; if (m) m.setActiveTool(btn.dataset.tool);"
"annotationToolButtons.forEach(function (btn) { btn.disabled = !isMain; });"
"createSurface: createPdfSurface"
```

**This directly constrains §2.3.** Changing the factory signature to
`createPdfSurface(name, opts)` breaks
`test_defines_create_pdf_surface_factory` even though no user-visible behaviour
changes. Moving the toolbar dispatch to a separate file breaks the `getFocused`
assertion.

Per `CLAUDE.md`'s *"Tests protect intent, not accidental history,"* these are
the category to surface rather than resolve silently. The intent they protect —
Eye uses the shared factory rather than a re-introduced mini-renderer;
annotation tools stay Main-only — is genuine and worth keeping. The
*exact-string coupling* is the accidental part. A decoupling stage must either
preserve the strings verbatim or replace those assertions with behavioural
equivalents as an explicit, argued change.

The remaining eight of the fourteen referencing test files assert on rendered
markup (for example `self.html.index('id="workspace-document-controls"')`) and
are **unaffected** by any pure-JS refactor.

### 4.2 What can move with no user-visible change and no test change

1. Adding `subscribe(listener)` and `setSearchQuery(str)` to the `api` object —
   purely additive.
2. Introducing an internal `emit()` alongside the existing `isFocused()`-gated
   writes, both running, snapshot unused. Additive.
3. Moving `projectId` / `baseUrl` resolution behind one internal accessor that
   still reads `document-tab-strip` by default.
4. Giving the surface real ownership of `searchQuery`, with the toolbar input
   mirroring it. Closes §3.1 as a side effect.

### 4.3 What cannot move invisibly

- Changing the factory signature (§4.1).
- Relocating the toolbar block to a separate file (§4.1).
- Lifting the two hard gates — behaviour-changing by definition; that is the
  point of the work.
- Anything touching the responsive re-parenting (§3.3).

---

## 5. Smallest reversible proof

**Proposed experiment — one file, additive only, no gate touched, no markup
touched, no test touched.**

Add `subscribe(listener)` and an internal `emit()` to `createPdfSurface`, called
at the same points that currently call `refreshToolbar()` / `updateNavState()`.
Leave every existing chrome write in place and running. Then, in a scratchpad
harness only, register a listener that records snapshots.

**The falsifiable claim:** *for a representative session — mount, page, zoom,
fit, rotate, mirror, search, focus-switch, unmount — the recorded snapshot
stream contains every value the toolbar displays, with no snapshot missing and
none stale relative to the DOM.*

**If true:** the state shape in §2.3 is sufficient, and a canvas-native consumer
can be built against it without touching the toolbar at all. The hard gates then
become a separate, later, one-line-each change with a known-good consumer
already proven.

**If false:** the diff between snapshot and DOM names precisely which state the
engine does not yet own — the highest-value output of the experiment, and far
cheaper to learn this way than from a partial rewrite.

**Why this is the smallest.** It changes no observable behaviour, breaks no
pinned string, needs no template edit, requires no decision about the
single-toolbar constraint, and is revertible by deleting one function. §3.1 no longer depends on it, having been reproduced
separately (§3.1.1); the snapshot stream should nonetheless show `searchQuery`
correct for an unfocused surface, which is the regression check for that fix.

Estimated surface: roughly 40 lines added to one file, zero removed.

---

## 6. What this audit deliberately does not conclude

- **Not "the coupling is technical debt."** §3 argues the opposite, on evidence.
- **Not a design for canvas-native Look.** §5.3 owns that; this audit only
  establishes that the state it needs (`page`, `pageCount`, `zoom`) is already
  computed and merely unexposed.
- **Not that decoupling should proceed now.** §5.3's sequencing constraint
  stands: Look must exist before chrome is reduced. This audit changes the cost
  estimate of that ordering, not the ordering itself.
- **Not a verdict on the two hard gates.** Whether a chrome-less route *should*
  mount a viewer is a product question, not an architectural one.
- **§3.1 is now confirmed** (reproduced under control, §3.1.1) and is therefore no
  longer an open question. What it does *not* settle is whether it should be
  fixed standalone or absorbed into the ownership move in §2.2 — that is a
  scheduling decision, not a finding.

---

## 7. Provenance

Measured against the working tree at `main` @ `11e29af`. Sources:
`static/js/pdf_viewer.js`, `static/js/drawing_image_viewer.js`,
`static/js/eye_pane.js`, `templates/base.html`, and the fourteen test files that
reference the viewer contract. Line numbers are as at that commit and will
drift.

Related: `governance/proposals/surface-vs-substrate-interaction-grammar.md` §2.6
(the 30-binding measurement this audit refines) and §5.3 (the Look sequencing
constraint this audit is subordinate to);
`governance/specified-unbuilt/provenance-at-the-point-of-interaction.md` §C.1
(canvas rebuild start state).
