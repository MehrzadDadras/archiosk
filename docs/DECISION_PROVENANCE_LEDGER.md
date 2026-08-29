# Decision & Provenance Ledger

A running record of what was directed, what evidence was actually opened, where
the epistemic boundaries were drawn, and why each implementation was chosen over
the shortcut that would have looked the same from outside.

**Rule of the ledger:** an entry is written *before* the code it describes, and
completed after. Anything the work did not establish is recorded as
`UNRESOLVED`, never smoothed into a finished-looking result. Where an entry and
the repository disagree, the repository wins and the correction is logged rather
than silently applied.

This ledger records reasoning. It is not an authority: `governance/` governs
domain-model decisions, and pushed `origin/main` remains the system of record.

---

## DPL-0005 - 2026-08-29 - Vector sheet standard, and one microphone

**Status:** complete, with two items recorded as `UNRESOLVED` rather than
closed - production transport compression, and device-verified speech.

### Directive received

> Consolidate the voice module: guard `voice_input.js` against insecure
> contexts, refactor `landing.js` onto the unified
> `window.ArchioskVoiceInput`, wire voice into the Nipigon and Calm Lake
> workspace headers. Provide an HTTPS local test server on port 8643 so real
> microphone speech recognition can be tested over a LAN IP. Complete landing
> box-sizing, discipline containers and the orientation grid, and record
> DPL-0005 covering the gzipped SVG + `viewBox` vector rendering standard and
> the voice secure-context requirement and module convergence.

---

## Part 1 - The vector sheet standard

### Evidence scanned

Every rendered sheet measured, raw and gzipped at level 6:

| Sheet | Raw | Gzipped | Ratio |
|---|---|---|---|
| A902 | 20.22 MB | 1.16 MB | 17.5x |
| A204 | 9.36 MB | 0.74 MB | 12.6x |
| A701 | 8.79 MB | 0.57 MB | 15.4x |
| A510 | 7.37 MB | 0.55 MB | 13.5x |
| A511 | 7.03 MB | 0.49 MB | 14.3x |
| A205 | 6.71 MB | 0.52 MB | 12.9x |
| A509 | 5.38 MB | 0.36 MB | 15.1x |
| A801 | 4.64 MB | 0.37 MB | 12.7x |
| A302 | 4.01 MB | 0.38 MB | 10.4x |
| RS501 | 2.77 MB | 0.18 MB | 15.4x |
| A100 | 1.51 MB | 0.18 MB | 8.4x |
| **All 11** | **77.79 MB** | **5.50 MB** | **14.2x** |

A second measurement decided the shape of the standard, and is the
counter-intuitive one: **a cropped SVG is not smaller.** Setting a cropbox
changes the viewport, not the content - the A204 washroom crop came out at
9609 KB, *larger* than the full page, because all 57,906 paths are still
emitted.

### The standard

1. **One vector asset per sheet.** A crop is a `viewBox` **view** onto it - a
   focus rectangle the viewport frames - never a second file. This is the same
   property the `live` Page-Field miniature has: one definition, shown two
   ways, so the crop and the full sheet *cannot* disagree about what the
   drawing says.
2. **Vector for anything a reader zooms; raster for anything they do not.**
   Panes get SVG, because linework stays mathematically sharp at any
   magnification rather than up to a chosen dpi. Page-Field thumbnails and
   discipline mosaics stay raster, because a 175px tile has no zoom and
   parsing 57,906 paths to fill one would be wasted work.
3. **Focus rectangles are recorded in the sheet's native view space**,
   transformed through the same rotation matrix the SVG was emitted under.
4. **Transport is compressed.** SVG is text; 14.2x is not an optimisation, it
   is the difference between a sheet arriving in seconds and in a minute.

### Architectural decisions & trade-offs

- **`tools/serve_https_harness.py` compresses in memory, not on disk.** The
  served tree is a build output regenerated constantly, and a stale `.gz`
  beside a fresh `.svg` would serve yesterday's drawing under today's
  timestamp. `Vary: Accept-Encoding` is set, because a LAN proxy replaying a
  gzipped body to an `identity` client would hand it bytes it cannot read.

### Verifications executed

- A204.svg over TLS: 9,818,961 bytes identity, 779,309 gzipped (12.6x),
  `Content-Encoding: gzip`, `Vary: Accept-Encoding`, and the decompressed body
  **byte-identical** to the identity response.
- nipigon.css: 40,280 -> 12,200 (3.3x), identical after decompression.
- An `Accept-Encoding: identity` client still receives the raw file.

### The mechanism, demonstrated in isolation

`docs/demos/demo_vector_desk.html` (new) is a single self-contained page showing
the two mechanics without the weight of a real 8 MB sheet: dynamic `viewBox`
framing with independent pan/zoom per pane and live coordinate telemetry, and
the split-pane coordination move where pressing `1/A801` frames the detail in
pane 2 **without moving pane 1**.

Three decisions inside it are worth recording:

- **The geometry is schematic and says so, unmissably.** A page that draws a
  plausible floor plan and labels it A204 becomes a picture of a building
  nobody surveyed. A dashed provenance banner states that the geometry was
  drawn for the demo, is not extracted from the source PDFs, and must not be
  cited as evidence — while naming what IS real (the room numbers, the
  callout, automobile elevator 110, read off the source annotations).
- **The briefed figure and the recorded figure are both drawn.** The demo was
  asked for a 1500 mm turning envelope; the verified A204 note records
  **1900** for room 104. Both appear, labelled. Quietly picking one would have
  been the opposite of what a coordination desk does.
- **Self-contained means it will not run from `/static/` — so it does not
  live there.** Measured, not assumed: `app.py`'s `set_csp_header` is an
  `@app.after_request`, so it applies to static responses too, and it sends
  `default-src 'self'` with `script-src 'self' 'nonce-<per-request>'`. A
  static file cannot carry a per-request nonce, and `style-src` is absent so
  inline styles fall back to `default-src` as well — both the inline `<style>`
  and the inline `<script>` are refused. It runs from `file://`, and from
  `tools/serve_https_harness.py`, which sends no CSP.

  It shipped at `static/demo_vector_desk.html` in `9307bd3` and was found
  answering **200** on the public web root during post-deploy verification.
  Moved to `docs/demos/` (CLAUDE-DEMO-RELOCATE-01). The inert-markup problem
  was the lesser half: a publicly-served page showing a plausible floor plan
  labelled A204 is a provenance hazard whether or not its script runs, and
  the banner saying the geometry is invented only helps a reader who reads
  it. **Not publishing it is stronger than explaining it.** It is
  documentation, and it now lives with the documentation.

### UNRESOLVED

**Production does not compress these.** Neither `app.py` nor any config in
this repository enables transport compression, and Flask does not do it by
default. The 14.2x above is real and is now real *in the harness*; on
`archiosk.com` it is not, and a 20 MB A902 would be served whole. This is
recorded rather than fixed because it is a deployment-layer decision (the
front-end web server's `gzip`/`brotli` configuration) and no evidence was
gathered here about what that layer currently does.

---

## Part 2 - One microphone, and the origin it needs

### Evidence scanned

The audit read every voice path in `static/js/`: `voice_input.js`,
`landing.js`, `case_workspace.js`, `login.js`, and the six templates that load
a mic. The decisive measurement was taken on the exact origin the reviewer's
phone was using, not on a stand-in:

| | `http://10.0.0.177:8642` | `http://127.0.0.1:8642` |
|---|---|---|
| `isSecureContext` | **false** | true |
| `navigator.mediaDevices` | **undefined** | present |
| `getUserMedia` | **false** | true |
| `SpeechRecognition` | **`"function"`** | `"function"` |

`isSecureContext` appeared **zero times** in `voice_input.js`, `landing.js`
and `case_workspace.js`.

### Epistemic classification

- **DIRECT - the defect.** The constructor is defined on an insecure origin.
  The guard `if (!Ctor) return null` therefore **passes**, the mic button is
  revealed, and the start call fails on press. The symptom reported as "voice
  fails to respond" was never a broken recogniser: it was a microphone offered
  where the browser will not grant one. Feature detection tested the *symbol*,
  not the *capability*.
- **DIRECT - the duplication.** `landing.js` carried a second, independently
  maintained copy of the engine, its own header comment describing it as
  deliberately "mirroring" `voice_input.js`. One report of one defect therefore
  required the same fix in two files.
- **UNRESOLVED - whether speech now works on the device.** Everything below is
  verified by construction and by test; none of it is a spoken sentence
  transcribed on a phone. That verification needs the reviewer, an accepted
  certificate, and a voice.

### Architectural decisions & trade-offs

- **The guard tests the capability: `!Ctor || !window.isSecureContext`.**
  Hiding the button is the honest outcome - typing remains the fully
  equivalent path, and an absent affordance is better than a present one that
  cannot work.
- **`landing.js` keeps its ROUTER and loses its ENGINE.** The division is the
  honest one: every page's microphone *listens* identically, and only what it
  *does* with a sentence differs. `DIRECT_NAV`, `INFORMATIONAL`, `FALLBACK`
  and the transcription-variant patterns are preserved verbatim - that work
  came from a real Product Owner report ("sing in") and had no reason to be
  rewritten.
- **Voice dispatches real controls, and never performs an action itself.**
  On Nipigon a spoken "A801" calls `.click()` on the same sibling button a
  finger would; on Calm Lake a spoken surface name clicks that field's own
  button, so the prototype's existing honest refusals still fire ("Project
  intake is not built in this prototype") rather than a smoother-sounding lie.
  Voice cannot reach anything a tap cannot, so it inherits every guard the
  visible control already carries. The vocabulary is closed, and an
  unrecognised sentence is quoted back verbatim and does nothing.
- **`setStatus` is returned from the engine** so a caller says its own piece in
  the *same* live region, rather than growing a second one a screen reader
  would announce twice.
- **Listening is a change of FILL, not of shade** on every surface, so ready
  and listening stay distinguishable in greyscale. On Calm Lake it inverts to
  solid ink rather than amber: that surface is a deliberately grayscale
  wireframe, and `test_the_ramp_is_a_cool_near_neutral_and_never_warm` names
  `#7A4A08` by value as the thing it exists to exclude. The test was right and
  the wireframe's own grammar produced the better answer.
- **`app.py` was NOT given an `--ssl` mode.** Its `__main__` block binds
  `127.0.0.1` unconditionally and its own comment records that as deliberate -
  the same block that disabled Werkzeug's interactive debugger after a real
  incident. Adding "listen on every interface" to the application's dev
  entrypoint would loosen that constraint for a need that is not about the
  application: device testing here has always driven the static harness. The
  LAN exposure lives in `tools/serve_https_harness.py`, which serves
  pre-rendered files and can neither authenticate anybody nor reach the
  database. The directive offered either route; this is the narrower one.

### Verifications executed

- `tools/serve_https_harness.py` generates a certificate whose
  `subjectAltName` names the LAN IP, and a client validating against it
  fetches over TLS successfully - so the browser interstitial is the only
  barrier, not a rejected certificate. (An IP certificate without an `IP:` SAN
  is refused outright; CommonName has not been honoured for years.)
- Full suite green on every landing/voice file touched; the engine assertions
  in `test_ca1d_public_landing_03/05` were retargeted to `voice_input.js` with
  the reasoning recorded in each docstring, and two new tests were added: one
  asserting `landing.js` contains no engine tokens at all, one asserting the
  shell loads the engine before the router.
- `node --check` clean on all four changed scripts.

---

## Part 3 - Disciplines, and the counts behind them

Not in the directive's ledger list, but it is the change with the most
evidence behind it and the ledger is where evidence goes.

### Evidence scanned

Two independent readings, kept separate because they disagree:

**Delivered** - counted off `C:\Archiosk\Samples\5 Nipigon`: 51 PDFs, of
which 39 are A-series and 10 are RS501-RS510. The other two ("5 Nipigon.pdf",
"Nipigan Starter.pdf") are not numbered sheets and are counted as no
discipline's.

**Named** - read out of the DRAWING INDEX on `212109 A100 COVER PAGE.pdf`:

| Discipline | Index numbering | Delivered | Basis |
|---|---|---|---|
| Architectural | CV, A101-A902 | 39 | `direct` |
| Structural | S1-**S10** **and** RS501-RS510 | 10 | `inferred` |
| Mechanical | M1-M5 | 0 | `unresolved` |
| Electrical | E1-E5 | 0 | `unresolved` |
| Landscape | L1 | 0 | `unresolved` |
| Civil | SP1 | 0 | `unresolved` |

**Correction, logged rather than silently applied.** The structural set was
first recorded as S1-S9. It runs to **S10** (`UNDERGROUND FOUNDATION`). The
first reading used `\bS\d\b`, which matches a single digit and stopped at S9
without any sign that it had — a regex that cannot express the answer returns
a confident wrong one. Re-measured with `\bS\d{1,2}\b`.

**There is no P-series and no C-series on this project.** A later directive
asked for a "Plumbing / Civil (P / C-Series)" container. The index was searched
for both before building one:

- **No P-series exists at all.** Plumbing scope is carried by the MECHANICAL
  series — it is the *title* of M1 (`U/G GARAGE PLAN PLUMBING AND HVAC`) and
  M2 (`PLUMBING PLAN`), not a discipline of its own here.
- **The only `C1` on the cover is a zoning designation**, in the project-data
  block (`563.34 sq.m | C1 | 5 Nipigon Ave`), not a drawing number. Civil is
  numbered **SP1**.

So no P/C card was invented. Building one would put a container on screen
standing for a series this project does not have — the same defect as
accepting "A201 is the Level 2 floor plan" when its title block says FIRE
SCHEMATIC LAYOUT. The discrepancy is reported instead, and the Mechanical
tile's own note now says where plumbing actually lives.

### Epistemic classification

- **Reading the cover sheet added a discipline nobody had listed.** Civil
  (SP1, site servicing and grading) was not in the working set until A100 was
  actually opened. The index is the authority on what the project is supposed
  to contain; our memory of it is not.
- **Structural is `inferred`, not `direct`.** A100 carries *two* structural
  sets under two numbering systems, and only the RS framing series arrived.
  Calling it `direct` would assert a completeness the source does not support,
  and quietly reconciling the two is precisely what this project's evidence
  rule forbids. The disagreement is shown, not resolved.
- Four disciplines are named on the cover and delivered nothing. They still
  get a tile, rendered `unresolved` - because a project page that showed only
  the two disciplines with files would be hiding the most useful fact on the
  screen.

### Architectural decisions & trade-offs

- **A discipline tile is not a Page-Field.** It is a container, not a window
  onto a surface, so it does not take the pinned 175.00 x 152.17px geometry -
  that would claim a kinship it does not have. The sheets *inside* it are real
  Page-Fields and keep that geometry exactly.
- **Its face is a mosaic of its own real rendered faces**, at most four,
  because a fifth stops being a drawing at that size and becomes a texture.
  An empty discipline draws an empty dashed frame and never borrows another
  discipline's picture to look populated.
- **The strip always carries both numbers** ("39 sheets - 6 rendered"),
  because "39 sheets" and "39 sheets, all prepared" are different claims.
- **The grid axis keys on `orientation`, not on a width breakpoint.** The
  request was about the shape of the space; a landscape phone and a narrow
  desktop window can be the same width and want opposite layouts. Portrait is
  one column of wide short bands; landscape is one row of equal auto-columns,
  so seven tiles divide the width rather than wrapping below the fold.

---

## Part 4 - Request Trial Access, pruned

### Directive received

> Remove the eyebrow label so the h1 appears only once. Delete the descriptive
> paragraph. Strip the bottom secondary footer button container. Retain the
> top-left `← ARCHIOSK` link as the sole exit path. Align the form fields and
> centre the primary button.

### Evidence scanned

The page and everything asserting on it: `templates/start_trial.html`,
`tests/test_ca1d_trial_access_hotfix_01.py`,
`tests/test_ca1d_public_landing_01.py`,
`tests/test_p40vw7a_ui_reference_map.py`, and `UI_REFERENCE_MAP.md`.

The directive described the eyebrow as `<div class="eyebrow">`; the real
element is `<span class="landing-doc-kicker">`. Acted on what is there.

### Epistemic classification

Five tests failed on the removals, and each had to be classified rather than
edited into agreement:

- **Defending copy, not intent.** `test_get_renders_the_request_form_not_the_old_rejection`
  asserted the literal string "opening trial access gradually". What it is
  named for — the old dead end never returns, a real request action is here
  instead — is carried by its two `assertNotIn`s and the form/submit refs, all
  untouched. Removing the paragraph cannot restore a dead end.
- **Intent satisfied more strongly than before.**
  `test_request_access_is_the_primary_action_sign_in_and_explore_are_secondary`
  proved primacy by source order. With the secondary pair gone there is
  nothing left for the primary action to be primary *over*. Inverted rather
  than deleted, the way this suite already handles a retired capability
  (`NothingSpeaksWithoutBeingAskedTests`): the risk worth guarding is now that
  competing CTAs come back.
- **A real narrowing, recorded as one.** `test_success_state_still_offers_sign_in_and_explore`
  guarded the confirmation screen. The footer pair sat outside the
  submitted/not-submitted branch, so removing it removed it from **both**
  states: a visitor who has just submitted now has one way onward where they
  had three. That is the directive as written, and it is flagged rather than
  quietly softened. The replacement test asserts the confirmation is still not
  a dead end, via the top-left link.
- **A registry consequence, not a test to edit.**
  `test_every_active_registry_row_actually_exists_in_a_template` was correct to
  fail. `UI_REFERENCE_MAP.md`'s two rows are marked **retired** with the reason
  attached rather than deleted — a deleted row loses why it went.
- **A wrong assertion of my own.** A new "title appears once" test counted the
  whole response and found two, because `<title>` legitimately carries the same
  words. Scoped to the document body. Caught before it was committed, not
  after.

### Architectural decisions & trade-offs

- **The eyebrow is kept on the SUBMITTED branch.** There it reads "REQUEST
  TRIAL ACCESS / Request received" — a flow name and an outcome, not the same
  string twice. Removing it would leave a confirmation with no statement of
  what was confirmed. The duplication was only ever on the form view.
- **The form column is centred; the fields inside stay left-aligned.** A
  centred label over a full-width input has no common edge to read down. The
  480px measure is unchanged.
- **The button is sized to its text, not to the form.** A full-bleed primary
  action reads as a banner rather than a control.

---

---

## Part 5 - Single Active Project on Site: the constraint, not the code

### Directive received

> In field/standard mode, suppress the global sidebar list of unrelated test
> runs/projects to uphold the "Single Active Project on Site" boundary. Route
> project entry via direct code/search input ("5 Nipigon") directly into the
> active site desk.

### Evidence scanned

A read-only map of the whole authenticated navigation surface was taken before
touching anything: `config.py`, `app.py`, `routes/`, `services/`, `templates/`,
`static/js/`, `static/css/main.css`, `governance/`, `docs/`.

### Epistemic classification

**UNRESOLVED, and it is the premise rather than the work.** *There is no
field/standard mode in this application.* Searches for `field mode`, `site
mode`, `standard mode`, `on-site`, `kiosk`, `tablet mode` and `single active
project` return zero product hits — the only matches are unrelated prose and
~1095 uses of the Python `field` keyword. `config.py` has no mode variable at
all; its only environment axis is Flask's `development`/`production`/`testing`
config classes, which is deployment config.

Three things are easy to mistake for it, and none is one:

| Looks like a mode | What it actually is |
|---|---|
| `operating_environment` (`services/environment_capabilities.py:47`) | A per-project, locked, governed **stakeholder side** — Client/Owner vs Design-Builder/Proponent. A project fact, never a session or UI mode. |
| `developer_mode` (`routes/portal.py:185`) | A session boolean, admin-only, on/off against the default UI. It has **no counterpart**. |
| The PWA + narrow-viewport CSS | Responsive and installable behaviour. `static/js/pwa.js:14` even says "on a phone the reviewer may be standing on site" — but nothing branches on it server-side. |

**So the directive's first clause cannot be executed as written without first
inventing a new, user-visible operating mode.** That is a product decision, not
engineering difficulty, and it is the kind this repository's own operating
notes single out: *"Internal complexity must earn user visibility... For each
internal distinction ask whether the user genuinely needs to understand it to
do their work."* A second mode would also need gating decided at every one of
the six surfaces below.

### What the surfaces actually are

Six authenticated surfaces render a list of projects. All of them already
filter through one of two access functions, and both end at
`services/project_access.py:33` `can_access_project` (admin, owner, or
allow-list):

| # | Surface | Renders in | Data |
|---|---|---|---|
| 1 | Left rail "Projects" tree | `templates/base.html:870` | `app.py:1025` `_nav_recent_projects`, injected globally |
| 2 | File ▸ Open Project… | `templates/_app_menu.html:339` | same call, never a second query |
| 3 | Home `/` | `templates/index.html:94` | `_accessible_documents`, top 6 |
| 4 | Projects directory `/projects` | `templates/projects.html:46` | `_accessible_documents` |
| 5 | Project chooser `/projects/choose` | `templates/project_chooser.html:114` | `_accessible_documents` |
| 6 | Removed Projects | `templates/removed_projects.html:15` | `_accessible_documents(include_removed=True)` |

**The seam the directive is reaching for already exists.**
`app.py:720` `_NO_PROJECT_LISTING_ENDPOINTS` already suppresses surface 1 for a
named set of endpoints (auth pages, the gateway). Extending it is a one-line
change — *once someone decides which surfaces count as "on site."*

**Entry by typing already exists too**, three times over: the chooser search
(`project_chooser.html:90`, server-side substring on filename/project_id), the
directory search (`projects.html:26`), and a client-side filter in the Open
Project menu (`app_menu.js:214`). Two gaps are worth naming:

- **There is no lookup by project CODE.** `services/project_code.py` defines a
  governed 3-4 letter acronym, but its only UI is the New Project form
  (`upload.html:307`). Nothing resolves a typed code back to a project.
- **`GET /search` is orphaned.** `routes/portal.py:2855` `global_search()`
  returns exactly the JSON a quick-open overlay would need, and **nothing in
  `templates/` or `static/js/` references it**.

### Decision

**Nothing in the authenticated navigation was changed.** Of the four honest
outcomes available for architectural work — do it, run the smallest
disproving experiment, surface the constraint, or reject it with reasons —
this is the third. Removing the Projects tree unconditionally would be a
material change to the main product's navigation that the directive scoped to
a mode which does not exist; inventing the mode instead would add a
user-visible operating concept on a single line of instruction.

The prototype surfaces are unaffected either way: `nipigon_coordination.html`
and `calm_lake_prototype.html` are standalone templates that never extend
`base.html`, so they have never rendered the launcher panel. There is no
cross-project leakage on the site desk today.

**What would unblock it**, in the order it would be built: (1) decide whether
"on site" is a mode, a per-device setting, or simply "a project is open" —
the third needs no new concept at all and is the cheapest honest reading;
(2) extend `_NO_PROJECT_LISTING_ENDPOINTS`, or gate the injection at
`app.py:846`; (3) wire the orphaned `/search` to a quick-open overlay and add
code resolution beside the existing name/id substring match.

---

## Part 6 - The guards, because none existed

The 5 Nipigon surface had **no test file at all**. Everything it proves — that
a pane serves a vector, that a discipline count came off the source material,
that a microphone is hidden where it cannot work — was guarded only by whoever
last looked at it. `tests/test_nipigon_vector_and_disciplines_01.py` adds 21
tests, and each one guards something that has **already been violated once**
during this work:

- **Vector standard (9).** Both panes serve `.svg`; no `<sheet>_<label>.png`
  crop is referenced anywhere; the render tool no longer contains
  `pix.save(dest)`; focus rectangles reach the page as `data-focus`/`data-view`;
  thumbnails stay raster because a 175px tile has no zoom.
- **Discipline evidence (7).** All six named disciplines render; the counted
  39 and 10 appear; exactly four cards say "none delivered"; Structural is
  `inferred`; RS501 sits under Structural and A204 does not; the grid keys on
  `orientation`. One test exists purely to record a refusal —
  `test_no_plumbing_or_c_series_container_was_invented`.
- **Voice (5).** The engine tests capability rather than symbol; this surface
  carries no recogniser of its own; the mic is `hidden` by default; dispatch
  contains no `fetch`, no `XMLHttpRequest` and no `location.href` — only
  `.click()` on controls already on the page; and "go back" reaches the return
  control rather than Ask GO.

**A defect this work found by writing them.** Making the crops go was supposed
to be a deletion. The GO block's Jinja guard read `{% if go.chosen and
go.chosen.asset %}` — a *raster crop* — while the `src` it rendered was
`target_svg.file`, a vector. Retiring the crops would have made that guard
false and silently deleted the entire GO affordance, with the vector it needed
sitting right there on disk. A guard has to test the thing it guards; it now
reads `{% if go.chosen and target_svg %}`.

---

---

## Part 7 - Deployed to production

**`9307bd3e435e8a3359d518b1920db56b8ecb1967`, live on `archiosk.com`,
2026-08-29.**

### What the deploy actually spanned

Production was **13 commits behind**, not one. The live tree was pinned by
checksum before anything was packaged, because no marker on the server records
the deployed commit: `app.py`, `routes/portal.py`, `CONTINUATION_CHECKPOINT.md`
and `MANIFEST.md` were CRLF-normalised and matched against history, which put
live at **`dec5efb` or an ancestor** — confirmed independently by
`templates/calm_lake_prototype.html`, `governance/decision-mechanics/CHARTER.md`
and `tools/backup_holodeck_archive.ps1` all being absent from the live tree.

The server holds **CRLF** copies of the same content: `git archive` run on this
Windows host emits CRLF into the tarball. A naive `md5sum` comparison of a
deployed file against `git show` therefore never matches, and reads as drift
that is not there. Normalise before concluding anything.

`dec5efb..9307bd3` — 13 commits, carrying the Calm Lake prototype, the Nipigon
coordination surface, the Decision Mechanics programme, and this tranche.
`68ed4bb` (the Canvas UI step the Product Owner explicitly disowned as a
direction) was **not** previously deployed and rode along as an ancestor; it
cannot be excluded from a deploy of `9307bd3` without rewriting history.

### The gate that was nearly checked against the wrong range

Steps 7 and 8 of `deploy/DEPLOYMENT.md` (pinned dependencies, schema changes)
were first checked across `127b72f..9307bd3` — **one commit**, not thirteen.
That is precisely the failure the runbook warns about in its own step 7: *"This
was found before it caused an outage, but only because the deploy was being
checked against the diff rather than run by rote."* Re-checked across the true
`dec5efb..9307bd3` span:

| Path | Changed? |
|---|---|
| `requirements.txt` | no |
| `migrations/`, `models.py` | no |
| `config.py`, `.env.example` | no |

Both sections correctly skipped, and no database backup was required. Had any
been non-empty, the first check would have said "skip" and been wrong.

### Rollback point

- **Code:** `/var/www/archiosk-backup-pre-9307bd3` (764 files), taken before
  any write, excluding the persistent paths.
- **Secrets:** `/var/www/archiosk/.env.bak-pre-9307bd3`, taken before the
  `STATIC_VERSION` edit.
- **No database backup**, correctly: nothing in the range touches
  `migrations/` or `models.py`, so step 4's code-only rollback is a complete
  reversal.

### Verification performed

Dry-run first: **0 deletions**, 848 entries, and the single persistent-path
match was `.env.example` (tracked; documents variable *names*, never values).
Real `.env`, `instance/`, `.venv/`, `.claude/`: zero. After the sync: service
`active`, 14 workers, `/health` `ok`, `.env` and `instance/` intact, ownership
`archiosk:archiosk`.

Live content was then checked at the **new** asset URL, so a cache hit could
not be mistaken for a successful deploy: `landing.css` carries the
`box-sizing` fix, `voice_input.js` carries the secure-context guard,
`landing.js` contains **zero** `SpeechRecognitionCtor` and does reference
`ArchioskVoiceInput`. `/`, `/start-trial`, `/explore`, `/login` all 200;
`/admin/nipigon/` 403 and `/admin/calm-lake/` 302, so the prototypes are not
publicly reachable.

### `STATIC_VERSION` 133 → 135

`.env` is per-host and git-ignored, so nothing in the synced tree carries it
and nothing in a diff can catch it being wrong. Production was measured
serving **133** before the deploy and **135** after.

Direction matters more than the number. The checkpoint's own recorded
near-miss was a local bump to `124`, then `128`, both **below** what
production was already serving — a downgrade leaves every browser on its
cached stylesheet and looks exactly like a successful deploy. Measured live
both before and after, never assumed from a local file.

The edit itself was refused to this agent by the sandbox (a write to a
production secrets file) and was performed by the Product Owner from the
command line. Recorded because the refusal is correct behaviour worth
preserving, not an obstacle that was worked around.

### One defect found by verifying rather than by assuming

`static/demo_vector_desk.html` shipped in this commit and answered **200** on
the public web root. It was moved to `docs/demos/`
(CLAUDE-DEMO-RELOCATE-01) — see Part 1. The post-deploy check that caught it
was not looking for it; it was a routine sweep of what the deploy had made
reachable. That sweep is worth keeping.

---

### Also in this tranche

**The landing page centering defect**, reported from a phone as portrait-only.
`.landing-content` asks for `min-height: 100dvh` **and** `8vh/10vh` of vertical
padding; under the CSS default `content-box`, padding is added *outside* that
height, so a container meant to fill the screen is 118dvh tall and
`justify-content: center` faithfully centres inside a box 18% too tall.
Landscape hid it because 18% of a short viewport is ~90px rather than ~150px.
Same defect, quieter symptom. Fixed with `box-sizing: border-box` scoped to
`.landing-page`'s own subtree.

---

## DPL-0004 - 2026-08-28 - Archive custody moved to the WD My Cloud NAS

**Status:** complete. The archive now has a second copy on a different machine.

### Directive received

Retarget the Holodeck archive backup from a local disk to the WD My Cloud
EX4100 at `\WDMYCLOUDEX4100\Publicrchiosk-backups`: verify the share is
reachable, create the directory, change the script default, run the snapshot,
confirm all 232 files match over SMB, and log the migration.

### Evidence scanned

Reachability established before anything was changed:

| Check | Result |
|---|---|
| DNS | `WDMyCloudEX4100.local` -> `10.0.0.148` |
| SMB port 445 | `TcpTestSucceeded = True` (ICMP blocked, which is normal) |
| Shares visible | `Public`, `TimeMachineBackup`, `Recycle Bin - Volume_1` |
| Target directory | absent; created |
| Write/read probe | round-tripped over SMB before trusting the share |

A prior local Tier 1 snapshot exists on `D:rchiosk-backups`. `D:` was
confirmed to be **DiskNumber 1** against `C:`'s **DiskNumber 0** - genuinely a
separate physical device, not a second partition - so that copy survives a
drive failure and is retained rather than discarded.

### Epistemic classification

- `DIRECT` - the share is reachable, writable, and the snapshot verified: DNS,
  port, share enumeration, write probe, and a full hash comparison all
  measured, none assumed.
- `UNRESOLVED` - **whether the NAS itself is redundant.** Its own disk
  configuration was not inspected. A NAS is a different machine, which is
  strictly stronger than a different volume; it is *not* evidence of RAID, and
  this ledger does not claim it.
- `UNRESOLVED` - **offsite.** All copies are now in one building. A fire,
  theft or power event still takes every one of them. Tier 3 remains open.

### Architectural decisions & trade-offs

**A defect the run itself exposed, and the reason to read output rather than
exit codes.** The first NAS snapshot succeeded and reported
`VERIFIED SNAPSHOT: Microsoft.PowerShell.Core\FileSystem::\WDMYCLOUDEX4100\...`
- and the new "destination is a network share" line never printed.

`Resolve-Path` returns a PROVIDER-QUALIFIED string for a UNC target. The UNC
test therefore examined `M`, reported nothing, and fell through to a
drive-letter comparison of `M` against `C` - which "passed" for entirely the
wrong reason. A same-volume warning that cannot fire on the one destination
type it most needs to reason about is worse than no warning, because it reads
as a clean bill of health. Fixed by resolving `.ProviderPath`, and the fix was
confirmed by the message appearing on the next run.

The exit code was 0 both times. Nothing about the failure was visible in
pass/fail.

**The message says what the destination actually buys, and what it does not:**
"Different machine: survives failure of this computer. NOT offsite." A backup
tool that overstates its own protection is the specific way this kind of tool
fails people.

**The local `D:` snapshot is kept.** Retargeting the default is not a reason to
discard a verified copy on independent hardware.

### Verifications executed

Three independent confirmations, not one repeated:

1. **Round-trip during write** - 232 files re-expanded from the NAS zip and
   re-hashed against the source: match, hash-for-hash.
2. **`-VerifyOnly` over SMB** - live archive compared to the stored manifest:
   "Live archive is identical to the last verified snapshot."
3. **Zip integrity after the fact** - the manifest's recorded `ZipSha256`
   (`0C6D130D4A618ED3...`) re-computed against the file as it now sits on the
   NAS: MATCH. This is the one that proves the bytes survived the network, not
   merely that the write returned success.

Manifest: `FileCount = 232`, `Verified = True`.

On the share:
```
holodeck-archive-20260828-223408.zip            3,578,945 bytes
holodeck-archive-20260828-223408.manifest.json     47,146 bytes
holodeck-archive-20260828-223502.zip            3,578,945 bytes
holodeck-archive-20260828-223502.manifest.json     47,146 bytes
```

Two snapshots because the first ran before the ProviderPath fix; both are
independently verified and `-KeepLast 6` rotates them.

### Executive residue

- **Offsite is still open.** Every copy is in one building.
- **NAS redundancy is unverified.** Worth confirming its disk configuration
  before treating it as the durable copy.
- Re-run: `./tools/backup_holodeck_archive.ps1 -KeepLast 6` (now defaults to
  the NAS), and `-VerifyOnly` as a periodic integrity check.

---

## DPL-0003 · 2026-08-28 · Engine DNA preferences, and a test exemption made explicit

**Status:** complete.

### Directive received

Run the full regression suite to 100%, commit the sprint, then move every
ad-hoc overlay switch, theme flag and coordination behaviour off the drawing
canvas into a central Preferences surface reached from a gear in the Scene 1
header. Persist to `localStorage` under `ARCHIOSK_ENGINE_PREFS` with fallback
to `config/engine_preferences.json`. Scene 2 subscribes dynamically.

### Evidence scanned

`tests/test_p40vw8qa_site_wide_visual_consistency.py` was read before the run
rather than after, because the new `nipigon.css` would have made an existing
failure worse.

### Epistemic classification

**A pre-existing failure was resolved by reading the test's own intent, not by
weakening it.** `test_tokens_css_hardcoded_hex_only_appears_in_token_definitions`
globs every stylesheet in `static/css/` and forbids raw hex. Its docstring
scopes it: tokens are "the single mechanism that keeps Light/Dark/Tinted able
to repaint the WHOLE app from one place."

`calm_lake.css` has been failing it since `a4cfb19`, unnoticed, and `nipigon.css`
would have added a second violation. Both are standalone prototype stylesheets
loaded by exactly one template that does not extend `base.html`; their own
headers state that `main.css` is untouched by them and cannot be affected by
them. They define a self-contained ramp *on purpose* and are outside the
theming system by design.

The exemption is therefore **named, not pattern-matched** — a new shipped
stylesheet still fails, which is what the test is for. Recorded here rather
than resolved silently, because changing a test to make it pass is exactly the
move that needs a written reason.

`UNRESOLVED` and NOT addressed by this sprint: `test_mobile_continuation_01`
(`RuntimeError: Session backend did not open a session`) and
`test_write_collision_01` (`ProjectCodeError: could not derive a unique project
acronym`). Both reproduce on a clean `HEAD` worktree, both are unrelated to
this work, and both look like test-isolation rather than product defects.
Fixing them is its own task.

### Architectural decisions & trade-offs

**Defaults ship as data, not as literals.** `config/engine_preferences.json`
carries the schema *and* the defaults, and the panel is rendered from it. A
preference cannot exist in the panel but not in the defaults, or the reverse —
that disagreement is not representable.

**Precedence is explicit:** shipped defaults < `localStorage`. Every storage
read and write is wrapped, because storage can throw or return empty (private
window, cleared data, blocked site data) and a viewer who cannot persist must
still get a working page rather than an undefined engine.

**What a preference may not do.** None of these change a source document, a
derived native orientation, or a classification. Turning the semantic overlay
off does not un-classify anything; it stops drawing it. That boundary is what
makes the panel safe to expose.

**The overlay preference is a posture, not an override.** It is read when a
sheet is opened, so opening RS501 honours the setting without the reader
touching anything — but it still cannot switch on for a sheet with no
classification, because there would be nothing to draw.

**Strict provenance hides grounding, never the basis.** With it off, the
pointing card drops the evidence sentence and source file but keeps the
DIRECT/INFERRED badge. The badge *is* the claim; hiding it would leave a
coloured stroke asserting something with no visible standing.

**An unavailable preference is shown, disabled, with its reason.** Red
annotations/leaders needs a text layer and is derived for no sheet yet.
Omitting it would make the panel look complete when it is not.

**The drawing surface keeps its viewport controls and loses every engine
flag.** Zoom/pan/fit/rotate act on what you are looking at now; a switch that
configures the engine does not belong beside the sheet it configures.

### Verifications executed

- Panel renders all 7 controls from the JSON schema; defaults match the file.
- `localStorage` under `ARCHIOSK_ENGINE_PREFS` verified written and re-read.
- Theme switched gold-black → slate → gold-black via preferences only.
- Opening RS501 auto-applied the stored overlay preference.
- The in-canvas semantic toggle is hidden; Pane 2's bar carries only
  `out, in, fit, rccw, rcw, reset`.
- Targeted regression: **136 passed** (Calm Lake, site-wide visual
  consistency, security enforcement).
- **The full suite in flight at commit time predates these prefs patches**, so
  it does not describe the committed tree exactly. Stated plainly rather than
  implied; a fresh full run is the immediate next step.

---

## DPL-0002 · 2026-08-28 · RS501 semantic probe, viewport controls

**Status:** complete.

### Directive received

Three pieces, after the orientation defect was resolved and the A-series
semantic probe was reported blocked:

1. Establish this ledger and log the sprint before executing code changes.
2. Run the annotation-grounded semantic linework probe on **RS501**, using its
   genuine text layer (member tags, grid markers, level elevations) against its
   vector paths. Separate DIRECT from INFERRED. Render a non-destructive
   overlay with an ON/OFF toggle and explanatory pointing tooltips.
3. Implement viewport controls in Scene 2 — pan, zoom (pinch/scroll/buttons),
   fit, and manual 90° rotation override — for both panes.
4. Verify, serve on `0.0.0.0:8642`, capture 390×844 and 1600×844 with the
   overlay ON and a tooltip active.

### Evidence scanned

Measured directly from the source PDFs under `C:\Archiosk\Samples\5 Nipigon`,
read-only. Nothing under that root has been written, moved or renamed.

| Sheet | vector paths | images | PDF annots | text chars |
|---|---|---|---|---|
| A204 Ground Floor Plan | 57,906 | 0 | 0 | **0** |
| A801 Washroom Details | 28,258 | 0 | 0 | **0** |
| A201 Fire Schematic Layout | 14,342 | 0 | 0 | **0** |
| A401 Front/Rear Elevation | 38,333 | 0 | 0 | **0** |
| A100 Cover Page | 1,227 | 1 | 0 | 12,036 |
| **RS501 Structural Framing** | **13,426** | 0 | 0 | **2,401** |

RS501 text inventory: **432 positioned items** — 41 member-tag-shaped tokens,
76 grid letters, 65 bare numbers, plus level annotations carrying elevations
(`U/S PERIMETER BEAM 191500`, `GR. FL. SLAB 192610`, `TOP OF SKYLIGHT ELEV.
201520`).

Orientation evidence, all 49 sheets: 38 A-series at `/Rotate 0` with **no text
layer**; 10 RS-series at `/Rotate 90` **with** text; A100 at `/Rotate 0` with
text.

### Epistemic classification — the boundaries established

**Why the probe moved from the A-series to RS501.** The directive originally
named the washroom zone on A201/A401. Two findings moved it:

- A201 is *Fire Schematic Layout* and A401 is *Front/Rear Elevation* — verified
  from their title blocks. Neither carries washroom fixtures.
- More decisively, **the entire A-series has zero extractable text**. The room
  tags, the `H/C` annotation and the `1/A801` callout exist only as drawn glyph
  outlines among tens of thousands of paths. The only way to read them is OCR
  over a raster, which yields raster bounding boxes — the exact basis the
  directive forbade. The directive's own evidence standard ruled out the only
  available technique, so the probe was reported blocked rather than faked.

RS501 is the one family where annotation-grounded classification is honestly
possible, because it has both a real text layer and real vector geometry.

**The three tiers, as applied here:**

- `DIRECT` — geometry a text annotation can be tied to by construction: a tag
  whose leader terminates on the path, or a member tag sitting on the member.
  Established by geometry-to-text adjacency **plus** a leader trace, never by
  bounding-box proximity alone.
- `INFERRED` — geometry contiguous with DIRECT geometry (a continuing member
  run) but carrying no annotation of its own.
- `UNRESOLVED` — everything else. Expected to be the large majority, and
  reported as such rather than minimised.

### Architectural decisions & trade-offs

**The classification is geometric, not proximity.** The cheap version boxes a
piece of text and tints whatever falls inside. A DIRECT link here requires all
four of: the token matches a CISC-style designation (`W###X##`, `HS###X###X#.#`,
`L##X##X#.#`) rather than being any text; a path exists whose axis *agrees* with
the tag's writing axis; the tag sits within 9pt perpendicular of it; and the tag
lies inside the member's own span. **Two members matching equally means the tag
claims neither** — 19 tags were dropped that way, and refusing to choose is the
point.

**INFERRED is reserved for structural continuation** — collinear, same axis,
sharing an endpoint within 4pt with a DIRECT member. Not "nearby geometry".

**Explicit refusals are honoured.** The sheet carries a revision cloud reading
`NON-SPECIFIED BEAM FOR CAR LIFT ENT. REF. TO STRUC.` Two `Non-Specified`
tokens were detected and are reported, never promoted to a classified member:
the drawing is stating that it does not know, and the overlay must not overrule
it.

**Coordinate spaces.** Verified that neither `get_text("words")` bboxes nor
`get_drawings()` coordinates respond to `set_rotation` — both report in
UNROTATED content space. Classification therefore runs in content space where
text and geometry genuinely share a frame, and only the *emitted* geometry is
transformed through `page.rotation_matrix` into the native view. An earlier pass
classified in one space and declared the view box of another; that is exactly
how an overlay ends up confidently drawn over the wrong lines. A second
instance of the same bug survived into the continuation pass and was caught by
INFERRED silently dropping to 0.

**The view transform is not a document change.** Pan/zoom/rotate live on
`.np-stage`, which holds the drawing *and* its overlay so the two cannot
separate. Each pane owns its own Viewport instance, so Pane 2 cannot move
Pane 1. `Reset` returns to the derived native orientation; `Fit` deliberately
does **not** clear a manual rotation, because fit is about size and reset is
about orientation. Nothing writes the source PDF or the derived orientation.

**The overlay is scoped to the sheet it was derived from.** `npSyncOverlay()`
hides the toggle unless Pane 2 is showing RS501 — offering it over A801 would
invite a reader to believe RS501's classification describes a washroom detail.

**`vector-effect: non-scaling-stroke`.** The overlay lives in a 2592-unit
viewBox displayed ~800px wide, so plain stroke widths rendered sub-pixel at fit
zoom and the classification was invisible until the reader zoomed in.

**DIRECT and INFERRED differ in weight and dash as well as hue** (5px solid cyan
vs 3.5px dashed amber), so the distinction survives greyscale rather than
depending on telling cyan from amber.

### Verifications executed

**Classification counts on RS501** — 432 text items, 846 segments considered:

| Tier | Count |
|---|---|
| DIRECT | **17** |
| INFERRED | **11** |
| UNRESOLVED segments | **822** |
| member designations found | 69 |
| tags matching no member | 33 |
| tags ambiguous (claimed nothing) | 19 |
| explicit `Non-Specified` refusals | 2 |

**Registration:** 0 of 28 classified segments fall outside the declared view
box; overlay box measured 800×533 against an image box of 800×533, aligned
within 2px on all four edges.

**Pane independence:** Pane 2 zoomed to 220% and rotated 90°; Pane 1 transform
verified byte-identical before and after. Mobile: Pane 2 at 240% with Pane 1
holding 100%.

**Tooltip:** activated on `W250X45` → renders `DIRECT / LOCATED`, `Structural
beam`, the evidence sentence, and the source file. Confirmed positioned inside
Pane 2 after an initial defect placed it over Pane 1.

**Strokes in view:** 12 DIRECT at `rgb(53,224,208)` 5px and 6 INFERRED in view
at 240% zoom.

**Regression:** 128 targeted tests pass (Calm Lake + security enforcement). The
full suite has NOT been re-run since the new blueprint and these changes.

### Epistemic edge cases encountered

- **Ambiguous shared geometry (19 tags).** A W-section drawn as two parallel
  flange lines gives a tag two equally good candidates. Reported as ambiguous
  rather than resolved by picking the nearer by a hair.
- **33 tags matched no member**, mostly column designations whose members are
  drawn as rectangles (`re`) rather than line segments; only `l` items are
  considered. A known, bounded limitation, not a silent one.
- **Explicit non-specification.** Two `Non-Specified` tokens; the sheet refuses
  to specify a beam and the overlay respects that.

### Generalizability

**38 of 49 sheets have no text layer at all.** This technique generalizes to the
11 that do — the 10 RS structural sheets and the cover — and to none of the
architectural set. Any claim that ARCHIOSK can derive semantic linework across
5 Nipigon would be false: it can do so for roughly 22% of the sheets, and the
boundary is a property of how the PDFs were produced, not of the algorithm.

---

## DPL-0001 · 2026-08-28 · Native drawing orientation derivation

**Status:** complete.

### Directive received

Pane 2 was presenting A510 in the wrong orientation. Treat it as a
drawing-intelligence defect, not a one-sheet CSS correction: inspect rotation
metadata, derive a bounded orientation signal from sheet evidence where
metadata is insufficient, store the derived orientation as part of the surface
derivation, use it for both miniature and expanded surface, preserve the source
PDF, and allow manual rotation that does not mutate the derived value.

### Evidence scanned

All 49 sheets probed for `/Rotate`, page box, text layer and dominant writing
direction. A510 rendered at all four rotations and inspected visually.

### Epistemic classification

- **Metadata is insufficient, measured:** 38 of 49 sheets are stored portrait at
  `/Rotate 0` with no text layer; read as stored, every one is on its end.
- **Metadata is also not ignorable:** the 10 RS sheets carry `/Rotate 90` and it
  is *correct*.
- `DIRECT` signal — dominant writing direction, where a text layer exists.
- `INFERRED` signal — title block as the densest edge band, placed on the right.
- `UNRESOLVED` — a low density margin flags `needs_confirmation`; the sheet is
  still rendered, because refusing to show a drawing helps nobody.

### Architectural decisions & trade-offs

- **Derived value is an ADDITIONAL rotation, not an absolute one.** The first
  implementation produced an absolute rotation and *undid* the publisher's own
  `/Rotate 90` on the RS sheets, standing upright sheets on end. Absolute is now
  `(stored + additional) % 360`.
- **Landscape is a hard constraint, not a preference.** A508/A603/A606 derived a
  confident-looking `180` — still portrait, still unreadable. These are 24×36
  sheets drawn landscape, so only rotations leaving the sheet landscape are
  candidates. That is evidence about the drawing.
- **Text direction is read in unrotated content space.** Verified that
  PyMuPDF's line `dir` does not respond to `set_rotation`, so the rotation is
  computed against stored `/Rotate` rather than found by re-reading at each
  candidate — an approach that silently returned the same answer four times.
- **Crops are taken in the space they were measured in, then rotated.** A clip
  rect is not rotation-invariant: cropping after rotation silently moved the
  washroom crop onto *AUTOMOBILE ELEV. 110*.
- **Stored in the derivation.** The manifest records `stored_rotate`,
  `additional`, `absolute`, `signal`, `evidence`, `margin`,
  `needs_confirmation`. Miniature and expanded sheet share one rotated render,
  so they agree by construction rather than by two matching guesses.
- **Source PDFs never written.** `set_rotation` acts on the in-memory document.

### Verifications executed

- A510 rendered at 0/90/180/270 and inspected: only 270 puts the title block on
  the right reading horizontally.
- Derivation run across all 49 sheets: 38 → 270, 10 → 90, cover → 0.
- A204/A801/RS501/A508/A902 rendered at their derived orientations and
  inspected; RS501-at-absolute-0 is what exposed the discarded-`/Rotate` defect.
- Washroom crop re-inspected after the crop-space fix: Room 104, `H/C`,
  corridor 103 and the `1/A801` callout all present and upright.
- `needs_confirmation` after the landscape constraint: **none** in the rendered
  set.
