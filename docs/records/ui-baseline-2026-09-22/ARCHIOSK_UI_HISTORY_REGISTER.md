# ARCHIOSK UI Baseline + History Register

**Baseline date:** 2026-09-22
**Deployed code:** `55554b5` — *feat(explore): one public product page, and a clean checkout that can prove itself*
**Static asset version:** `STATIC_VERSION=181`
**Capture method:** live `https://archiosk.com`, real Chrome, authenticated `admin` session, 1538x784 viewport
**Companion document:** `ARCHIOSK_UI_BASELINE_2026-09-22.pdf` — the same record with the screenshots inline

---

## 0. How this record was made, and what it cannot claim

### 0.1 How the deployed SHA was established

**The application exposes no build identifier.** `/health` returns liveness only —
`{"checks":{"registry_recovery":"ok","registry_store":"ok"},"missing_config":[],"status":"ok"}`
— with no commit, no version and no build time.

The deployed commit is therefore **inferred from content markers, not asserted by the
application**:

| Marker | Observed live | Unique to |
| --- | --- | --- |
| Explore headline "Governed intelligence for projects, assets, and opportunities" | present | `55554b5` |
| `landing.css?v=181` | present, HTTP 200 | `STATIC_VERSION=181`, set at that deployment |
| Superseded copy "What Archiosk does" on `/explore` | absent | post-`55554b5` |

Two commits have been pushed to `origin/main` since (`1e4e4de` requirements,
`09ccb7f` README). Neither is deployed and neither changes rendered output.

> **This is itself the first recorded anomaly.** A UI baseline that cannot name the
> build it is a picture of is resting on inference. See A-01.

### 0.2 Prior UI history in the repository — what actually exists

Searched: tracked images, `docs/records/`, `governance/`, `tools/static_preview/`,
`C:\Archiosk\FlightTests`, and git history.

| Source | Finding |
| --- | --- |
| Tracked images in the repo | **4 files, all app icons.** No UI screenshots exist anywhere in version control. |
| `tools/static_preview/` | Produces HTML snapshots, not images; output is git-ignored (`.gitignore:33`) and transient. |
| `C:\Archiosk\FlightTests\evaluator` | Rendered *drawing sheet* PNGs — document evidence, not application UI. |
| `C:\Archiosk\FlightTests\visible` | JSON evidence stores, no images. |
| Git history of `templates/` | **The real prior record.** Specific, dated, and quoted throughout below. |

**This document is therefore the first screenshot baseline ARCHIOSK has ever had.**
Every change classification below is made against *markup history*, which is genuine
evidence, and never against a prior image, which does not exist. Where markup history
does not state why a change was made, the entry reads `UNKNOWN_INTENT` rather than
supplying a motive.

### 0.3 The two recorded pagescape notes, and their outcome

Two UI directions were recorded during the 2026-07-26 Cedar Harbour walkthrough as
*recorded, not authorized*. Both have since been implemented, by `96c2257` —
*First live pagescape correction pass*.

| Recorded note | Status today | Classification |
| --- | --- | --- |
| Remove the "STEP 1" label from `/upload` | Gone. The page reads "New Project" with no step label. | **REMOVED** — documented intent, implemented |
| True pre-auth zero-state, no shell chrome behind the sign-in form | Implemented. Signed-out `/login` is 4,520 bytes with no `workspace-topbar`, no menu bar, and a bare `<body>`. | **REMOVED** (the chrome) — documented intent, implemented |

`96c2257` also established a **disclosure grammar** — *"One disclosure-grammar
mechanism app-wide … collapsed accordions with a count summary, not always-expanded
content."* That principle is the nearest documented intent for the collapse
affordances examined in section 2, and it is a *general* principle, not a decision
about any specific control.

### 0.4 Limits of this baseline — stated rather than hidden

1. **No signed-out screenshots.** `/`, `/gateway` and `/login` redirect an
   authenticated session to `/projects`. Capturing them as a visitor sees them would
   mean ending the Product Owner's live session, which was not done. `/login` is
   recorded from its served markup instead; `/` and `/gateway` are recorded as
   redirects. **This is a real gap**, and closing it needs one deliberate signed-out
   pass.
2. **No true mobile rendering.** The window was resized to 420x900 and the tool
   reported success, but `innerWidth` stayed at 1771 — the viewport did not follow the
   window, and the resulting capture is **byte-identical** to the desktop one
   (sha256 prefix `46850fed85a2`). Responsive behaviour below is read from the
   stylesheet and the DOM and is labelled as such. **No responsive claim here rests on
   a screenshot.**
3. **Capture-tool quirk, not an application defect.** Screenshots requested with a
   `scale` parameter returned magnified or four-way-tiled images. Every image kept
   here was captured at default scale and visually verified. Recorded so a future
   operator does not mistake the artifact for a rendering bug.
4. **Density is per-page and not persisted.** `INSPECT` survives only in the URL
   (`?density=inspect`, written by `history.replaceState`) and is lost on the next
   navigation. Screenshots labelled WORK are the default state.

---

## 1. Vocabulary, grounded in the code

### 1.1 Density modes — PUBLIC / WORK / INSPECT

Defined in `static/css/product_ui.css:1-5`, applied as `body[data-ui-density]`.

| Mode | Set by | Content width | Section gap | Base text |
| --- | --- | --- | --- | --- |
| `public` | `templates/landing_shell.html:41` | 48rem | 4rem | default |
| `work` | `templates/base.html:86` — default for every authenticated page | 76rem | 2.5rem | .95rem |
| `inspect` | `?density=inspect`, or Tools & settings -> View: Inspect | 90rem | 1.25rem | .85rem |

The control is a two-button group (Work / Inspect) at the foot of the app-menu panel —
`templates/_app_menu.html:789`. **PUBLIC is not offered as a user choice**;
`static/js/product_ui.js` accepts only `work` and `inspect`.

Observed effect (screenshots 01 vs 03): in INSPECT the project rows tighten and the
content column widens, so five project rows sit above the fold where WORK shows three.
Nothing is added or removed — it is density, not disclosure.

### 1.2 Developer / UI Reference Mode — what it is, and what it is not

**UI Reference Mode does not reveal hidden controls. It labels controls that are
already on screen.**

- Control: Account menu (`admin …`) -> **UI Reference Mode**, a checkbox —
  `templates/base.html:384`.
- Mechanism: stores `beehive:ui-reference-mode` in `localStorage` and adds
  `ui-reference-mode-active` to `<html>` — `templates/base.html:60, 1511-1516`.
- Effect: `static/css/main.css:7983-7988` gives every `[data-ui-ref]` element a dashed
  `--machine-blue` outline and a `::after` badge printing its own `data-ui-ref` value.
- Scope: presentation only. **No element's visibility changes, no control appears, no
  route unlocks.** Its own source comment calls it "a developer/QA-facing toggle, not a
  product-owner-facing feature".

Verified live: screenshot 05 has Reference Mode on and shows an identical control set
to screenshot 01, with identifier badges added over the top.

**"Developer Mode" is a separate and unrelated thing** — a server-side session state
rendered as a `DEVELOPER MODE` badge with an exit `x` in the menu bar
(`templates/_app_menu.html:853-856`). It was **active throughout this capture**. Its
only observed rendering effect is the badge itself.

### 1.3 Shells — five, not four

`templates/` holds four files named `*_shell.html` (`auth`, `gateway`, `landing`,
`panel`). The **Help Center is a fifth shell that is not named as one**:
`templates/help/index.html` is a standalone `<!doctype html>` document that does not
extend `base.html`. It renders with no menu bar and in a light theme, while every other
authenticated page is dark with the menu bar. See A-02.

---

## 2. The Projects collapse affordance — the case asked for specifically

### 2.1 What the affordances are

`/projects` carries **three** collapse affordances, all native `<details>`, all
introduced by the same commit `d8b836b` (2026-09-21):

| # | Affordance | Source | Contents |
| --- | --- | --- | --- |
| 1 | "Other ways to start or recover work" | `templates/projects.html:17` | Document Upload, Planning & Zoning, Removed Projects |
| 2 | "Ask GO to help you find your next step" | `templates/projects.html` (class `ui-help-composer`) | the GO orientation Composer, moved here from `index.html` |
| 3 | "Project reference" — **one per project row** | `templates/projects.html:125` | that project's `project_id` |

### 2.2 The three questions asked, answered from observation

**Is it visible normally?**
**Yes.** All three summaries render on a plain, signed-in visit to `/projects` with no
flags, no query string and no mode set. Screenshot 01 shows the two page-level
triangles under the page heading and a "Project reference" triangle on every row. All
three are **closed by default** — the summary is visible, the content is not.

**Does it appear only in UI Reference Mode?**
**No.** Reference Mode cannot make a control appear; it only overlays identifier badges
on elements that are already rendered (section 1.2). Screenshot 05 is `/projects` with
Reference Mode on: the same three affordances, in the same places, still closed, now
wearing badges.

A detail worth recording: **the disclosure summaries carry no `data-ui-ref` of their
own.** Their children do — `projects-directory.document-shop`,
`projects-directory.planning-zoning`, `projects-directory.removed-link`. So in
Reference Mode the *contents* can be named but the *affordance that hides them* cannot.

**Is historical intent documented?**
**Partially, and not at the level that matters.**

- `d8b836b`'s message is a single line — *"Simplify governed review UI with shared
  density shells and result-first presentation"* — with no body. It states no reason
  for collapsing these particular controls.
- `templates/projects.html` carries a detailed `CLAUDE-HOME-UNIFY-01` comment
  explaining the page's *heading* and the Composer's *move*, and says nothing about the
  disclosures.
- The general disclosure grammar from `96c2257` (section 0.3) is consistent with
  collapsing them, but is a principle, not a decision about these controls.

**Classification: `CONDITIONAL` + `UNKNOWN_INTENT`.** Per instruction, no judgement is
offered on whether this is good or bad. What can be said factually is what changed:
before `d8b836b`, Document Upload / Planning & Zoning / Removed Projects were
**always-visible buttons**, and the project id was **always-visible text**; after it,
both sit one click away.

### 2.3 A related inconsistency, recorded without judgement

The project id is treated **two different ways in two places**:

- `/projects` — behind a per-row "Project reference" disclosure.
- `/removed-projects` — printed in full, unhidden, directly under each project name
  (screenshot 12).

Same datum, same user, two grammars. No commit states an intent for the difference.
**Classification: `UNKNOWN_INTENT`.**

---

## 3. Page-by-page baseline

Field order per page: route -> purpose -> primary action -> visible controls ->
conditional/hidden -> Reference-Mode-only -> responsive -> density -> interactions ->
anomalies -> change classification.

Reference-id counts come from a live DOM sweep classifying every `[data-ui-ref]`
element as VISIBLE, BEHIND_DISCLOSURE (inside a closed `<details>`), ZERO_BOX
(rendered but zero-sized) or HIDDEN_CSS (`display:none`/`visibility:hidden`/`hidden`).

---

### 3.1 All Projects — `/projects`

*Screenshots 01 (WORK), 02 (app menu open), 03 (INSPECT), 04 (account menu open), 05 (Reference Mode on)*

- **Deployed SHA / date:** `55554b5` / 2026-09-22
- **Purpose:** the single home destination for a signed-in session. `/` and `/gateway`
  both land here — proven by byte-identical captures, not assumed.
- **Primary action:** open a project (each row is the link).
- **Visible controls (14 refs):** `projects-directory.new-project` (admin only),
  `.search`, `.environment-filter`, `.filter-apply`, `.list`, `.leaf` x8,
  `.leaf.delete` x8, `tank.container`, `menu.developer-mode-badge` + `.exit`,
  `footer.public`, `footer.explore`, `footer.support`.
- **Conditional / hidden:** 97 refs behind disclosures (91 of them the app menu,
  3 `projects-directory`, 3 `index.orientation`); 31 zero-box; 7 CSS-hidden, including
  `menu.mobile-nav-toggle` (correctly hidden above 640px) and
  `menu.help.shortcuts-panel`.
- **Reference-Mode-only controls:** **none.** Reference Mode adds badges, not controls.
- **Responsive (from CSS, not observed):** at <=640px `.workspace-menubar` is replaced
  by `.mobile-nav-toggle` opening a drawer — `static/css/main.css:8410`. Above 641px
  the toggle is hidden — `:8830`. The rule's own comment cites "the Product Owner's own
  iPhone screenshot" as the reason, so intent here **is** documented.
- **Density:** WORK default; INSPECT via the menu (screenshot 03).
- **Known interactions:** menu-bar `<summary>` elements opened on the **second** click
  after a fresh page load in both menus tested; the first click focused without
  opening. Observed twice, cause not established.
- **Anomalies:** see A-05 (Search nav), A-06 (id disclosure inconsistency).
- **Change classification vs markup history:**
  - "Other ways to start or recover work" disclosure — **HIDDEN** (was three visible
    buttons) / `UNKNOWN_INTENT`
  - Per-row "Project reference" disclosure — **HIDDEN** (was visible id) / `UNKNOWN_INTENT`
  - Orientation Composer — **MOVED** here from `templates/index.html`, documented in
    `CLAUDE-HOME-UNIFY-01`
  - Heading "All Projects" — **BEHAVIOR_CHANGED** from "Projects" to match the File
    menu item verbatim, documented
  - `+ New Project` — **UNCHANGED**, admin-gated, documented in
    `CLAUDE-PROJECTS-NEW-ACTION-01`

---

### 3.2 New Project — `/upload`

*Screenshot 06*

- **Purpose:** create a project and bring in its founding material.
- **Primary action:** `upload.submit`.
- **Visible controls (26 refs):** identity (`upload.actor`, `upload.role`); five
  company-identity radios (`client_owner`, `lead_design_consultant`, `subconsultant`,
  `prime_contractor`, `trade_bidder`); project identity (`upload.project-name`,
  `upload.project-code` as four single-character acronym boxes); three source-domain
  choices (`client-issued`, `team-workspace`, `external-reference`); folder and file
  pickers; `upload.help` Composer with voice.
- **Conditional / hidden (15):** `upload.client-size-error`,
  `upload.folder.picker-input`, `.domain-summary`, `.summary`, `.founding-picker`,
  `.error`, `upload.file.rows`, `.founding-note`, `upload.help.voice.status`,
  `.reply` — all error/progress states that appear on interaction.
- **Reference-Mode-only:** none.
- **Density:** WORK. **Disclosures:** none — this page is fully expanded.
- **Anomalies:** none observed.
- **Change classification:** "STEP 1" eyebrow — **REMOVED**, documented intent
  (section 0.3). Page title "New Project" — **BEHAVIOR_CHANGED** from "Ingest an RFP or
  RFQ", documented in `4ddd215` *"the page says what the person is doing"*.

---

### 3.3 Document Upload — `/document-shop`

*Screenshot 07*

- **Purpose:** examine a document without creating a project first.
- **Primary action:** `document-shop.submit` — "Examine this document".
- **Visible controls (11):** `document-shop.intake`, `.file`, `.file.choose`,
  `.accepted-formats` (".csv, .docx, .jpeg, .jpg, .md, .pdf, .png, .txt, .xlsx. Up to
  60 MB per file."), `.name` (required), `.submit`, `.jobs-link`.
- **Conditional / hidden:** `document-shop.file.status`, `.file.names`.
- **Reference-Mode-only:** none. **Density:** WORK. **Disclosures:** none.
- **Anomalies:** none observed.
- **Change classification:** **ADDED** as a whole page by `f114d9a` — *"a door for the
  person who has a document but not a project"*. Documented intent.

---

### 3.4 My documents — `/document-shop/jobs`

*Screenshot 08*

- **Purpose:** the private desk of documents brought in for examination.
- **Primary action:** open a document's result.
- **Visible controls:** view nav (My documents / Archive / Recently Deleted), Reload,
  Select all, Clear selection, an "N selected" counter, per-row checkbox + title +
  "Analysis history" + Delete, and "Examine a document".
- **Reference-Mode-only:** none. **Density:** WORK.
- **Anomalies:** **A-03** (literal `?` separators) and **A-04** (title/heading
  disagreement). Both below.
- **Change classification:** **UNCHANGED** in structure since `f114d9a`/`b8ce135`.

---

### 3.5 Planning & Zoning — `/planning-zoning`

*Screenshot 09*

- **Purpose:** read a municipality's own zoning and planning records for an address.
- **Primary action:** `planning-zoning.submit`.
- **Visible controls (25):** mode tabs (Single property / Batch);
  `planning-zoning.backend-state`; address field; four analysis-mode radios (Zoning
  check / Zoning + planning constraints / Development envelope / Zoning +
  planning-level design options); optional context (direction, strategy, condition,
  question); submit; `planning-zoning.gate-note`.
- **Conditional / hidden:** `planning-zoning.working` — the working indicator.
- **Reference-Mode-only:** none. **Density:** WORK. **Disclosures:** none.
- **Anomalies:** **A-07** — the page prints the literal token `BACKEND_READY_TO_WIRE`
  to the user.
- **Change classification:** **ADDED** by `4b9afb8` — *"the front door, and the honest
  boundary behind it"*. Documented intent.

---

### 3.6 Case Workspace — `/projects/<id>/workspace`

*Screenshot 10*

- **Purpose:** the working surface for one project — conversation, evidence, tools.
- **Primary action:** `chat.composer.send`.
- **Visible controls (41 of 317 refs):** breadcrumb with conversation switcher
  (`shell.context.identity.toggle`); tray switcher — Lists, Display, Eye, Toolbox
  (`shell.tray-switcher.*`); `chat.dock`, `chat.thread`, `chat.operational-actions`;
  composer with attach, voice and send; Toolbox panel — `toolbox.maximize`,
  `toolbox.compare`, Spin block (`toolbox.spin.run-first`,
  `toolbox.spin.world-survival` = Survival Mode, two `?` help affordances,
  `toolbox.spin.empty` = "No Spin runs yet."), and Project Intelligence
  (REQUIREMENTS 0, CONVERSATION 5, Investigations (3), RFI Correspondence (0), Work
  Products (0), Tasks (0), Tags (0), Evidence Isolation, Project Administration).
- **Conditional / hidden:** **132 refs behind disclosures** (108 menu, 21 toolbox,
  3 shell) and **107 zero-box** — by far the densest page in the application.
  **Roughly seven of every eight reference-identified controls here are not on screen
  at rest.**
- **Reference-Mode-only:** none.
- **Density:** WORK, shell `work-start`.
- **Anomalies:** **A-08** — the conversation prints `SOURCE_REFERENCE` seven times in
  consecutive lines.
- **Change classification:** structure **UNCHANGED** this baseline period; the
  answer-first presentation shipped in `91c0fa6` is **not** wired into this dock (see
  A-08), so the workspace still shows the pre-fix shape.

---

### 3.7 GO Review Workspace — `/admin/survey-evaluation`

*Screenshot 11*

- **Purpose:** investigate a question, understand the result, inspect the evidence.
- **Primary action:** submit the evaluation objective.
- **Visible controls:** "Choose a review task" link; "Reload view"; the objective
  textarea; a task card grid — Review a project (selected), Compare sources, Review
  coordination, Evaluate capital alignment, and three more below the fold.
- **Reached from:** menu bar **Review** (`/admin/survey-evaluation`) and **Compare**
  (same path with `?task=compare`). These are two entries to one page distinguished by
  a query parameter — **not** duplicate links.
- **Reference-Mode-only:** none. **Density:** WORK.
- **Anomalies:** an admin-only route (`/admin/...`) occupies two of the six primary
  navigation slots. Recorded as an observation, not a judgement.
- **Change classification:** **BEHAVIOR_CHANGED** by `d8b836b` — shared density shells
  and result-first presentation. Commit message states the what, not the why.

---

### 3.8 Removed Projects — `/removed-projects`

*Screenshot 12*

- **Purpose:** recover a project moved out of active use.
- **Primary action:** Restore.
- **Visible controls:** "Back to Active Projects"; per row — name, full project id,
  "Removed <date> by <user>", Restore.
- **Reference-Mode-only:** none. **Density:** WORK.
- **Authorization note:** `@login_required`, **not** admin-gated — deliberate, per
  `CLAUDE-LEFT-RAIL-01`, which documents the separate `menu.account.*` ref namespace as
  reflecting that real difference.
- **Anomalies:** **A-06** — ids shown raw here, disclosed behind a triangle on
  `/projects`.
- **Change classification:** **MOVED** — reached from the Account menu and from inside
  the "Other ways to start or recover work" disclosure on `/projects`; previously a
  top-level button. Documented for the menu move, `UNKNOWN_INTENT` for the disclosure.

---

### 3.9 Help Center — `/help`

*Screenshot 13*

- **Purpose:** "The desks carry controls. The reasoning lives here."
- **Primary action:** open a guide.
- **Visible controls:** eight guide cards (New Project; Field access passes; Spatial
  coordination; Spin & Survival Mode; Building Box in meetings; Drawing ingestion &
  baselines; What is Reconciliation?; File types & limits), a "Help Clip Studio" link,
  and a footer.
- **Reference-Mode-only:** none — **and none of the badges appear here at all**, since
  the page does not load the authenticated shell.
- **Density:** none. `body` carries no `data-ui-density`.
- **Anomalies:** **A-02** — light theme, no menu bar, no navigation back into the app
  except the footer.
- **Change classification:** **UNCHANGED** as a standalone document since
  `CLAUDE-HELP-CENTER-01`. The comment documents the card-container choice; the
  standalone-shell choice is `UNKNOWN_INTENT`.

---

### 3.10 Diagnostics — `/developer/diagnostics`

*Screenshot 14*

- **Purpose:** problems captured from the live product, with the context the
  application already knew.
- **Primary action:** read a captured report. Empty at capture: "No diagnostics
  captured yet."
- **Visible controls:** none beyond the shell — the page is a read surface.
- **Density:** WORK, full menu bar. **Reference-Mode-only:** none.
- **Notable:** the page states plainly that "Nothing here has been transmitted anywhere
  — a report waits until a development session is asked to read it."
- **Change classification:** **UNCHANGED** this period.

---

### 3.11 Explore — `/explore` (public)

*Screenshot 15*

- **Purpose:** the one public product page.
- **Primary actions:** Request Trial Access (`/start-trial`), Sign In (`/login`).
- **Visible controls:** back link; hero with the five-item "what it shows" list; four
  working-environment cards; five numbered workflow steps; governance section; a
  second CTA pair.
- **Density:** PUBLIC, shell `public-explain`, 48rem column, serif display face on the
  Deep Ocean dotted field.
- **Renders while signed in** without adopting the app chrome — unlike `/about`.
- **Change classification:** **BEHAVIOR_CHANGED** wholesale by `55554b5` — seven
  internal capability headings replaced by four sections. Intent documented in the
  template comment and the commit.

---

### 3.12 Request Trial Access — `/start-trial` (public)

*Screenshot 16*

- **Purpose:** request access.
- **Primary action:** Request Access.
- **Visible controls:** Name, Email (required), "What are you hoping to use Archiosk
  for? (optional)", submit.
- **Density:** PUBLIC. Renders without app chrome even when signed in.
- **Change classification:** **UNCHANGED** this period.

---

### 3.13 About — `/about`

*Screenshot 17*

- **Purpose:** short statement of what Archiosk is.
- **Primary action:** "What Archiosk does" -> `/explore`.
- **Visible controls:** heading, two paragraphs, the CTA, and a closed "Technical
  details" disclosure.
- **Density:** **PUBLIC**, shell `public-explain` — **but it renders the authenticated
  menu bar** when signed in. Mixed condition; see A-09.
- **Anomalies:** **A-09** (mixed shell) and **A-10** — the button still reads "What
  Archiosk does", the exact phrase `55554b5` retired from `/explore`. The label now
  names its destination by a title that destination no longer uses.
- **Change classification:** **BEHAVIOR_CHANGED** at the destination, label
  **UNCHANGED** — a carry-through gap from the Explore rewrite.

---

### 3.14 Sign in — `/login` (markup only, no screenshot)

- **Purpose:** authenticate.
- **Primary action:** `auth.signin.submit`.
- **Controls (6 refs, from served markup):** `auth.signin.username`, `.password`,
  `.password-toggle`, `.submit`, `.voice`, `.voice.status`.
- **Pre-auth footprint:** 4,520 bytes. No `workspace-topbar`, no menu bar, `<body>`
  with no attributes, `<h1>Archiosk</h1>`.
- **Density:** none.
- **Change classification:** **REMOVED** (all shell chrome) by `96c2257`, documented
  intent, and the state the 2026-07-26 note asked for.
- **Gap:** no rendered screenshot — see section 0.4.

---

### 3.15 Redirects and non-pages

| Route | Behaviour | Evidence |
| --- | --- | --- |
| `/` | -> `/projects` when authenticated | capture byte-identical to `/projects` |
| `/gateway` | -> `/projects` when authenticated | capture byte-identical to `/projects` |
| `/login` | -> `/projects` when authenticated | observed at session start |
| `/search` | **renders raw JSON** | screenshot 18, A-05 |
| `/project/<id>` | **plain-text "Not authorised."** for both projects tried | screenshot 19, A-11 |
| `/documents/<project_id>` | styled 404 with chrome and "Back to home" | screenshot 20 |

---

## 4. Anomalies and uncertainties

Recorded, classified, **not fixed** — this task is documentation only. Severity is this
record's own reading, offered to help triage, and is not a Product Owner decision.

| # | Anomaly | Evidence | Severity |
| --- | --- | --- | --- |
| **A-01** | **No deployed build identifier anywhere in the UI or `/health`.** The running build cannot state which commit it is; this baseline had to infer it from copy and asset version. | `/health` body; section 0.1 | Medium — every future live verdict depends on inference |
| **A-02** | **Help Center renders in a light theme with no app chrome**, unlike every other authenticated page. It is a standalone `<!doctype html>` that does not extend `base.html`. | screenshot 13; `templates/help/index.html` | Medium |
| **A-03** | **Literal `?` characters used as separators** between the three Document Shop views — "My documents ? Archive ? Recently Deleted". Confirmed as U+003F in the source, not an encoding artifact of capture. | `templates/document_shop_jobs.html:21,22` | Low, visible on every visit |
| **A-04** | **Title and heading disagree**: `<title>` is "Document Shop Jobs", `<h1>` is "My documents". Internal name in the tab, product name on the page. | screenshot 08 | Low |
| **A-05** | **Primary-nav "Search" navigates to a JSON endpoint.** The route's own docstring calls it "the Global search overlay's backend … exposed as JSON for the overlay instead of a full-page GET" — and the menu links straight at it. A user clicking Search sees `{"results":[]}`. | `routes/portal.py:3228`; `templates/_app_menu.html:138`; screenshot 18 | **High** — a top-level nav item lands on raw JSON |
| **A-06** | **Project id disclosed two different ways**: behind a per-row triangle on `/projects`, printed raw on `/removed-projects`. | screenshots 01, 12 | Low |
| **A-07** | **`BACKEND_READY_TO_WIRE` printed to the user** on Planning & Zoning — an internal classification constant surfaced as page copy. | `routes/planning_zoning.py:52,169`; screenshot 09 | Medium |
| **A-08** | **`SOURCE_REFERENCE` printed seven times** in a Case Workspace conversation. This is the exact symptom `services/answer_presentation.py` was built to collapse ("the same SOURCE_REFERENCE qualification several times", its own docstring line 6) — the projection is wired into the document page but **not** into the workspace dock. | screenshot 10; `services/answer_presentation.py:6` | Medium |
| **A-09** | **`/about` is a PUBLIC-density page that renders the authenticated menu bar.** Mixed shell condition. | screenshot 17 | Low |
| **A-10** | **Superseded label survives**: `/about` still offers "What Archiosk does", the phrase `55554b5` retired from `/explore`. Carry-through gap from that change. | screenshot 17 | Low |
| **A-11** | **`/project/<id>` returns a bare unstyled "Not authorised."** for an admin who can open the same project's workspace — no shell, no explanation, no way back. Reproduced on two different projects with byte-identical output, so it is route-wide, not project-specific. | screenshot 19 | Medium |
| **A-12** | **Dead CSS rule**: `product_ui.css` hides `.workspace-menubar-mobile-toggle` under `body[data-ui-density]`, but that class exists in no template or script. The live mobile control is `.mobile-nav-toggle`, governed correctly by the 640px breakpoint. The rule matches nothing. | `static/css/product_ui.css`; grep of `templates/`, `static/js/` | Low |
| **U-01** | **Uncertainty — second-click menu opening.** Menu-bar `<summary>` elements opened on the second click after a fresh page load, in both menus tested; the first click focused without opening. Observed twice. Cause not established, and not investigated further under a documentation-only scope. | screenshots 19->20 and 22->23 sequences | Unresolved |
| **U-02** | **Uncertainty — density does not persist.** INSPECT lives only in the URL and is lost on navigation. Whether that is intended is not stated anywhere. | `static/js/product_ui.js` | Unresolved |

---

## 5. Change classification summary

| Classification | Count | Items |
| --- | --- | --- |
| **ADDED** | 2 | Document Upload page; Planning & Zoning page |
| **REMOVED** | 2 | "STEP 1" label on `/upload`; all pre-auth shell chrome on `/login` |
| **MOVED** | 2 | Orientation Composer (index -> projects); Removed Projects (top level -> Account menu + disclosure) |
| **HIDDEN** | 2 | "Other ways to start or recover work"; per-row "Project reference" |
| **CONDITIONAL** | 1 | `+ New Project` (admin only) |
| **BEHAVIOR_CHANGED** | 4 | Explore page rewritten; `/upload` title; Projects heading; GO Review density shells |
| **UNCHANGED** | 6 | My documents; Removed Projects structure; Help Center; Diagnostics; Request Trial Access; `/about` label |
| **UNKNOWN_INTENT** | 4 | Both Projects disclosures; the id-disclosure inconsistency; the Help Center standalone shell |

**Every `UNKNOWN_INTENT` above shares one cause:** the change is real and traceable in
markup, and the commit that made it did not say why. `d8b836b` alone accounts for three
of the four, and it is the only UI commit in this period whose message is a single line
with no body.

---

## 6. What a future baseline should do differently

1. **Capture signed out.** One pass as a visitor closes the `/`, `/login` and public
   landing gap, which is the only category of page this baseline could not photograph.
2. **Capture at a real phone width.** Resizing the window did not resize the viewport
   here; a device-emulation capture or a genuinely narrow window is needed before any
   responsive claim can rest on an image rather than a stylesheet.
3. **Record the build the page came from.** Until the application can state its own
   commit (A-01), every baseline inherits the same inference.

---

*Prepared 2026-09-22 against live `https://archiosk.com`. Documentation only — no
application code, template, stylesheet or test was changed in producing this record.*
