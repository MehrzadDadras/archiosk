# Continuation checkpoint

## 2026-09-01 (application) — `3ab9477`: Developer Composer moved to Developer Tools

**`3ab9477` is the latest application commit and is pushed to `origin/main`.** This
entry records application completion; it does not claim a production deployment newer
than the `d760e6b` / `v=147` deployment recorded below.

The Developer Composer moved from authenticated `/` to the protected
`/admin/developer-tools` surface. Its workbench, conversation history, screenshot
attachment, voice input, CCN context, and application-scoped session state now render
through `templates/developer_tools.html`. The route supplies the complete Developer
Composer context directly.

`portal.index()` now has only two outcomes: unauthenticated requests render
`landing.html`; authenticated requests receive a **302** to
`portal.projects_list`. The Developer Mode exception and the old template-rendering
fallback were removed.

Verification: **56 passed, 37 subtests passed** across Composer convergence,
Developer Composer, Developer menu, and Developer UI reveal/workbench/history tests.

## 2026-09-01 (deploy) — `d760e6b` live at `v=147`: one home destination, and a staging mistake caught before it shipped

**`d760e6b` is live on `https://archiosk.com`**, replacing `7445ba1`. Confirmed
from systemd: `Gunicorn - ArchiOSK GO (accepted build d760e6b)`.

Rollback marker **`/var/www/archiosk-backup-7445ba1`** (21M, `.env` at `600`,
pre-edit unit at `/root/archiosk-go.service.bak-7445ba1`). Proven to be a real
pre-deploy point before anything else was touched: it still carries
`page_header('Projects')`, against the live tree's `page_header('All Projects')`.

**`STATIC_VERSION` 146 → 147**, stepped as `CURRENT + 1` off the live file.
Rollback trees pruned back to **2** (`7445ba1` + `408997b`); `921d851` removed by
explicit name behind a guard refusing the keepers and the live directory.

### What shipped

Authenticated `/` now redirects to `/projects`, which is the single home
destination: heading and title "All Projects", the orientation Composer and its
voice input, Search, Environment filter, project cards, and one "+ New Project".
The Lists/Display tray switcher no longer renders on project-less pages.
Anonymous `/` is unchanged and still the public landing page.

### Three things the change would have destroyed in silence

Each was found by inspection, not by a test failing first, and each is the part
of this stage worth remembering:

1. **The Developer Composer** — `templates/index.html` is its only home. It
   survives behind an explicit developer-mode branch in `index()`. **Still owed:
   relocate it to `/admin/developer-tools` and delete that branch.**
2. **The orientation Composer** — was guarded by `{% if not developer_mode %}` in
   a template that now renders only *under* developer mode, so it was
   unreachable markup rather than a relocated feature. Moved to `projects.html`.
3. **The operating-environment preset** on New Project. Restored, and only when
   exactly one environment is accessible.

### The gate was red first, and that mattered

The first full run on this tree: **11 failed, 6,130 passed**. It caught four
files no targeted lane touched — including `test_composer_convergence_01`, which
holds a registry of every Composer surface keyed by template path and failed the
moment the Composer moved. That is the mechanism working.

It also exposed a weaker problem: `test_p40e3a_layout_reconciliation` had two
loops over the same project-less URLs, and only one failed. The other asserts
ABSENCE of the Toolbox and Chat regions and would have kept passing against a
`Redirecting...` stub — green for the worst possible reason. Both now follow the
redirect.

Second run, after fixes: **6,140 passed, 2 skipped, 4 deselected, 2,513
subtests, `PYTEST_EXIT=0`, in 1:03:42.** Production code was byte-identical
between the two runs, so re-running could have been argued away. It was not —
this repository has already had to justify one deploy on a red suite, and a gate
reasoned around once stops being a gate.

### A staging mistake, recorded because it nearly shipped

`cbc4593` committed and pushed `tests/fixtures/wd_nas_bridge/builder_corpus/`
and `manifest.json` — six files `CONTINUATION_CHECKPOINT.md` records as
deliberately untracked in three separate entries. Cause: staging with
`git add -A -- tests/` instead of naming the files the change touched.

Not a secrets or provenance exposure. The genuinely held-out material is
`wd_nas_bridge/oracle/`, which `.gitignore` already protected and which was
never committed. The recorded reason for untracking is narrower: no test reads
this corpus, so committing it asserts a dependency that does not exist, and it
would ship to the server because `git archive` exports the commit.

Caught before the deploy, so **nothing untracked ever reached the live tree** —
verified twice, in the tarball (0 matches) and on the server after rsync.
`ff47e6e` untracked it; `d760e6b` added the `.gitignore` rules that `ff47e6e`'s
message had *claimed* were added but were not, because that edit anchored on a
path string appearing twice in the file and silently wrote nothing. Both facts
are in the history rather than amended away.

`.gitignore`'s existing `wd_nas_bridge/oracle/` block already warned, in its own
words, that "nothing enforced it, so a `git add -A` would have committed the
held-out answers." That argument always applied one directory up and had never
been extended there. Now it is.

### Verified live over HTTPS

| Check | Result |
|---|---|
| `/`, `/login` | 200, assets at `?v=147` |
| `/health` | 200 |
| `/projects` anonymous | 302 → `/login?next=/projects` — gated |
| `main.css?v=147` | 200, 419,863 bytes, carries the flyout rule |
| Deployed templates | `page_header('All Projects')` and the orientation Composer both present on the server |
| Untracked fixture on server | absent |

nginx `[crit]` monitor timer still `active`; disk 8.4G used / 89G free.

### Not verified, and why

**No authenticated live check was performed.** It needs the ephemeral
verification identity, and `tools/manage_verification_access.py`'s own docstring
states it is maintainer-run and "never something an automated agent runs
itself". Running it would have created an auth token in production against an
explicit instruction. The authenticated path is proven in-process against a real
test client — `/` 302s to `/projects`, which renders the heading, the Composer,
one "+ New Project" and no tray switcher — but that is not the same as a browser
on the live host, and this entry should not imply it is.

### Carried forward

- **Relocate the Developer Composer** to `/admin/developer-tools` and delete the
  developer-mode branch in `index()`.
- **`bridge_queue.claim_pending`'s unguarded `_write`** — real, reproduced,
  unfixed.
- **The distributed full-suite slowdown** — 1:03:42 and 2:42:32 on the same tree
  hours apart. The 300s per-test timeout has never tripped across two full runs,
  so no single test hangs; the cost is spread across the run.

## 2026-09-01 (deploy) — `7445ba1` live at `v=146`: the menu fixes, on a green suite, and the stall got a bound

**`7445ba1` is live on `https://archiosk.com`**, replacing `408997b`. Confirmed
from systemd: `Gunicorn - ArchiOSK GO (accepted build 7445ba1)`.

Rollback marker **`/var/www/archiosk-backup-408997b`** (20M of code, `.env`
copied in at `600`, pre-edit unit at `/root/archiosk-go.service.bak-408997b`).

**`STATIC_VERSION` 145 → 146**, stepped as `CURRENT + 1` read off the live file,
never from a local record. Required: `main.css` changed.

### The gate was green this time

**6,139 passed, 2 skipped, 4 deselected, 2,509 subtests, `PYTEST_EXIT=0`** in
**1:42:43**. Read from a redirected log with the exit code captured as its own
line — a background-task notification again reported "exit code 0" for the
wrapper during this session while pytest had actually exited 1, on a different
run, which is exactly the trap `CLAUDE.md` documents.

`test_storage_bridge_durable_05` passed. The unguarded `_write` in
`bridge_queue.claim_pending` is **still a real, unfixed defect** — it simply did
not lose the race this time. Nothing about this deploy addresses it.

### A third slow run, and the first one with a diagnostic attached

1:42:43 against a 26–35 minute norm. Not the 4h27m/4h35m magnitude, but well
outside normal — the third slow run in the series.

**What is new is that it now carries evidence.** `pytest.ini`'s new
`timeout = 300` did not trip once across 6,139 tests. So no individual test
hangs past five minutes: the slowness is **distributed across the whole run**,
not concentrated in one stuck test. That narrows the hypothesis away from "a
test blocks on something" and toward something environmental (I/O contention,
AV scanning, thermal throttling). It also retires the idea that a tighter global
bound would have been better — a 60s or 120s cap would have aborted a run that
was genuinely just slow, which is how a timeout stops being trusted.

### What shipped

`329f5cd` — Home targets `/projects`, and nested submenus fly out sideways.

- **Home.** The href was never broken and nothing intercepted it; `/` simply
  renders the project entry shell for an authenticated session, and everyone who
  can see the menu is authenticated. Product Owner decision: Home opens the full
  Projects Directory. `/` itself is unchanged.
- **Appearance / Display Layout.** Both kept the geometry they had as top-level
  topbar dropdowns when `CLAUDE-APP-MENU-01` relocated them inside the Archiosk
  menu, so they grew the parent panel downward instead of flying out. Re-anchored
  to `.workspace-menubar-subpanel`'s own values in a separate rule, leaving
  Account (still genuinely top-level) alone.

`7445ba1` — Tier 0 and the timeout bound. Test infrastructure only; inert on the
server, and it ships because `git archive` exports tracked files.

### Verified live, over HTTPS, from outside the host

| Check | Result |
|---|---|
| `/`, `/login` | 200, assets requested at `?v=146` |
| `/health` | 200, `registry_store` and `registry_recovery` both `ok` |
| `/projects` anonymous | 302 → `/login?next=/projects` — Home's new target is gated, not exposed |
| `main.css?v=146` | 200, **419,863 bytes**, carries `CLAUDE-MENU-SUBMENU-FLYOUT-01` and the re-anchor rule |

Fetched back over the wire, not read off disk — disk only proves rsync ran.
nginx `[crit]` monitor timer still `active` after the deploy.

### Still unexercised by a human

Every menu change here remains unverified by a person on a real device. The
Appearance flyout was proven by measured browser geometry (offset `+3.2px`,
top-delta `0.0px`, pixel-identical to Admin and Developer; parent panel height
234px unchanged when opening) — real evidence, but not the same as somebody
using it. The `(not yet available)` stubs from `9158b95`/`0f0593e` are likewise
still unseen.

### Carried forward

- **`bridge_queue.claim_pending`'s unguarded `_write`** — real, reproduced,
  unfixed, and green-by-luck on this run.
- **The distributed slowdown** — three occurrences now, cause still
  unidentified, but no longer capable of hiding: a hang would now name itself.
- **Rollback trees were 7; pruned to 2 the same day**, on explicit Product Owner
  authorization — `archiosk-backup-408997b` (this deploy's own rollback) and
  `archiosk-backup-921d851` (one older fallback), exactly what `DEPLOYMENT.md`
  step 13 asks for. `2d80d1f`, `9d16b8c`, `bb2b276`, `e7e8962` and `f332681` were
  removed by explicit name, never a glob with exclusions. Both keepers were proven
  to be genuine pre-deploy rollback points BEFORE anything was deleted: each still
  carries `url_for('portal.index')` for Home and zero occurrences of the flyout
  rule, against the live tree's `portal.projects_list` and one. ~100 MB freed,
  which is nothing on 89 GB — the point was that seven near-identical trees make
  the real rollback point harder to identify under pressure, not disk.


## 2026-09-01 (deploy) — `408997b` live at `v=145`: the menubar work, shipped on a red suite for a stated reason

**`408997b` is live on `https://archiosk.com`**, replacing `921d851`. Confirmed
from systemd: `Gunicorn - ArchiOSK GO (accepted build 408997b)`.

Rollback marker **`/var/www/archiosk-backup-921d851`** (845 files, `.env` at
`600`, pre-edit unit). Rollback trees now **6**; 8.5G used / 89G free.

**`STATIC_VERSION` 144 → 145**, stepped as `CURRENT + 1` from the live file.
Required: `main.css` and `app_menu.js` both changed.

### Deployed while the last full suite was red — and why that was safe

The suite that gated this tree failed one test:
`test_storage_bridge_durable_05.py::ClaimingIsAtomicAcrossRealProcesses`. The
entry below records it in full. Three facts made deploying anyway a judgement
with evidence rather than a gamble:

1. **This deploy carries no Python application code at all.** The entire delta is
   `static/css/main.css`, `static/js/app_menu.js`, `templates/_app_menu.html`,
   `templates/projects.html` — plus documentation and tests. `bridge_queue.py`,
   the red test's subject, is not in it.
2. **The failure mode cannot occur in production.** It is `WinError 32` from
   `os.replace` — a Windows-specific error. The live host is Linux, where
   `os.replace` is atomic and does not raise it.
3. The test passed in the four preceding full runs and 3/3 in isolation, in 4-8
   seconds each, against a run that took 4:35:47.

The underlying defect — `self._write` outside the guard in `claim_pending` — is
still real and still unfixed. What the above establishes is that it is not
*this deploy's* risk, not that it has gone away.

### Verified live

- Dry run: **8 modified, 0 new, zero deletions**, matching
  `git diff --name-status` exactly; 837 metadata-only re-copies.
- `/health` 200 (public and internal), `/login` 200, `/gateway` 302,
  `/projects` 302. No journal errors across the restart.
- Assets serve **`?v=145`** in served content.
- **Both changed static files were fetched back over HTTPS and inspected**, not
  read off disk — disk only proves rsync ran. `main.css` (418,401 bytes) carries
  `.menu-shortcut`, `.menu-item-icon` and the `:has()` rule; `app_menu.js`
  (12,584 bytes) carries the `focus-document-search` handler.
- nginx `[crit]` monitor still active after the deploy.

### What is now live that nobody has looked at

Every menu change in this deploy is unexercised by a human: the View and Window
groups, the Panels submenu, eleven disabled stubs, the Tools measurement group,
the renamed Home item, and the `+ New Project` action on the projects directory.
The shortcut slots are live and deliberately empty.

Also still unexercised from earlier deploys: the chunked upload, the re-auth
path, and the three Help guides — which have never been read by anyone.

### Still carried forward

- **`bridge_queue.claim_pending`'s unguarded `_write`** — real, reproduced,
  unfixed, and not addressed by this deploy.
- **The stall** — twice observed, cause unidentified, now known to be capable of
  failing tests rather than only delaying them.
- **Rollback trees are 6**, having been pruned to 2 on 31 August. Five deploys
  since then rebuilt them.

## 2026-09-01 — The stall recurred, and it took a latent Windows race with it

Two findings from a single full-suite run, plus the menubar work that run was
gating. Recorded together because the second was only visible because of the
first.

### The stall is no longer "non-recurring"

The entry below records an unexplained full-suite stall as **"unidentified and
non-recurring."** That is now false. A run on 2026-09-01 took **4:35:47** against
a 27-minute norm established over four consecutive runs on the same machine:

| Run | Duration | Storage-bridge concurrency test |
|---|---|---|
| full5 | 33:44 | pass |
| full6 | 26:50 | pass |
| full7 | 26:27 | pass |
| full8 | 26:49 | pass |
| **full9** | **4:35:47** | **FAIL** |

The earlier occurrence was 78% in 4h27m, then 100% in 2h52m on the same tree. So
this is the second stall of roughly the same magnitude, and the pattern is
"occasionally 6-10x, cause unknown", not a one-off.

**What is new is the correlation.** The previous stall was slow but green. This
one failed a timing-dependent test, which means the stall is not merely a
cosmetic wall-clock problem — it widens race windows far enough to change
outcomes. `CLAUDE.md`'s guidance that an unusually long run "is not automatically
evidence of a code regression" still holds; what this adds is that a long run may
manufacture failures of its own.

### A latent Windows defect it exposed

`tests/test_storage_bridge_durable_05.py::ClaimingIsAtomicAcrossRealProcesses`
failed with two of four processes claiming the same request. The subprocess
traceback names the cause:

```
services/bridge_queue.py:147  self._write(target, record)
services/bridge_queue.py:255  os.replace(temporary, path)
PermissionError: [WinError 32] The process cannot access the file
  because it is being used by another process
```

Reading `claim_pending` shows why that is possible:

```python
try:
    os.rename(path, target)      # THE concurrency primitive. Atomic.
except (FileNotFoundError, OSError):
    continue
record["claimed_at"] = ...
self._write(target, record)      # <-- OUTSIDE the guard
```

The rename — the actual atomicity primitive, and the thing the module's own
comment calls out — **is** correctly guarded. The write that follows is not. On
Windows `os.replace` raises `WinError 32` whenever another process holds the
destination open, so a worker can die *after* having already won the claim,
leaving the queue in a state the design does not describe.

**Not fixed here.** It is unrelated to the menubar work that run was gating, it
lives in real concurrency code whose semantics deserve a deliberate change rather
than a drive-by one, and the correct repair is not obvious: moving `_write`
inside the `try` would swallow a genuine failure, while retrying on `WinError 32`
needs a bounded policy. Recorded as a real defect with a reproduction, not as a
flaky test to re-run until green.

### Why the menubar work was committed anyway

**Product Owner decision**, on this evidence: 6,126 passed; the single failure is
in code the change does not touch; it passed in the four preceding full runs and
3/3 in isolation immediately afterwards (4-8 seconds each). The alternative was
re-gating at a cost of anywhere between 27 minutes and 4.5 hours for a result
already understood.

Recorded rather than absorbed, because "the suite was red when this landed" is
exactly the kind of fact that becomes unknowable six commits later.

### The menubar work itself

`8844705`, `9158b95`, `0f0593e` — File/View/Window/Document/Tools menus, the
projects-directory action, and the shortcut-slot layout.

**Most of what was requested already existed.** Across the batch, seven items
were verified as built rather than added: Split View, in-document Search, the
thumbnails pane, File-menu New Project, the menu dividers, and the View menu's
zoom/fit controls. Shipping "(not yet available)" on any of them would have told
a reviewer that a working capability was missing — worse than an inert control,
because it is a false statement rather than an absent one.

**Eleven keyboard accelerators were requested; none is bound.** There is no Ctrl
or Alt keybinding anywhere in `static/js` — the only modifier usage is `shiftKey`
for shift-Enter. Two of the proposed bindings collided with each other (`Ctrl+2`
assigned to both Fit Width and Split Vertical), four sat on items that are
themselves disabled stubs, and `F11` belongs to the browser. The **layout**
shipped; the hints did not, and a test now fails if a `<kbd>` appears without a
binding behind it.

**A real defect the full suite caught.** `test_mobile_submenu_repair_01` failed
`8 != 6`: the new Window > Panels submenu used `workspace-menubar-panel` where a
nested submenu needs `workspace-menubar-subpanel`, and the mobile flatten is
written against the subpanel class — that submenu would have been **unreachable
on a phone**. 229 targeted tests, including the menu and registry suites, passed
it clean. Only the full suite carries that file. That is twice in two batches
that the full suite caught something no targeted lane could.

### Still carried forward

- **`bridge_queue.claim_pending`'s unguarded `_write`** — real, reproduced,
  unfixed.
- **The stall** — now twice observed, cause still unidentified, and now known to
  be capable of failing tests rather than merely delaying them.
- **`e7e8962`... none of this is deployed.** Live remains `921d851` at `v=144`;
  every commit after it is unreleased.
- **No human has exercised** the chunked upload, the re-auth path, the Help
  guides, or any of the new menu items.

## 2026-08-31 (fourth deploy) — `921d851` live at `v=144`: upload progress, Help guides, and a red suite that earned its keep

**`921d851` is live on `https://archiosk.com`**, replacing `bb2b276`. Confirmed
from systemd: `Gunicorn - ArchiOSK GO (accepted build 921d851)`.

Rollback marker **`/var/www/archiosk-backup-bb2b276`** (841 files, `.env` at
`600`, pre-edit unit). Rollback trees now **5**; 8.6G used / 89G free.

**`STATIC_VERSION` 143 → 144**, stepped as `CURRENT + 1` from the live file.
Genuinely required: `static/js/chunked_upload.js` changed by +77/−21.

### What shipped

**Upload progress** — an explicit `<progress>` bar with
`Uploading chunk 10 of 22 — 45% (32.0 MB / 71.0 MB)`, then
`Assembling & verifying file...`, then `✓ Upload complete`.

**Three Help guides** — `drawing-ingestion`, `what-is-reconciliation`,
`file-types-and-limits` — with the paragraphs taken off the upload card and the
Reconcile control and replaced by a label and a link.

### The suite went red, and that is the entry

The full run failed at 67% on
`test_every_template_data_ref_has_a_registry_row` **after a targeted lane of 218
tests had passed clean**. Two new `data-ui-ref` values had no
`UI_REFERENCE_MAP.md` row. Nothing smaller than the full suite could have caught
it, and it was caught before anything was committed or deployed.

Adding the rows then failed the **reverse** assertion: the three progress refs are
created by `chunked_upload.js` at submit time, so no template contains them.
There were two ways out and one was wrong — marking them non-`active` would have
satisfied the scanner by **putting a false status in the registry to make a test
pass**, which is backwards from what the registry is for.

This repository already had the right mechanism: four dynamic-ref allowlists in
that test exist for exactly this case. `_CHUNKED_UPLOAD_DYNAMIC_REFS` is a fifth,
and is **read from the JS by regex rather than hard-coded**, so renaming a ref in
the script fails there with a clear diff instead of drifting silently out of the
registry. Verified it discovers all three rather than passing vacuously on an
empty set.

### Written against the code, not the brief

The brief for the reconciliation guide asked it to explain *"cross-discipline
clash/version alignment"*. **There is no clash detection in this codebase** —
grepped across `services/`, `routes/`, `engine/` and `templates/`; the only
"Clash" string is a label inside the fixture-fed `calm_lake` prototype.
`help_center.py`'s own docstring forbids describing an unbuilt capability
("indistinguishable from a lie to the person reading it on a site"), so the guide
documents the seven real `RECONCILE_STATUS_*` verdicts and **states the absence
plainly** rather than dropping it silently. A test pins that sentence.

**One sentence deliberately did not move.** *"Nothing is added, relinked, or
removed until you review the report and approve it"* stays on the Reconcile
control. It is the assurance that makes that button safe to press, and an
assurance about a governed action belongs at the point of action — behind a link,
the only people who read it are the ones who already went looking.

### Verified live

- Dry run: **8 modified + 4 new = 12, zero deletions**, matching
  `git diff --name-status` exactly; 833 metadata-only re-copies.
- `/health` 200 (public and internal), `/login` 200, `/gateway` 302, no journal
  errors.
- Assets serve **`?v=144`** in served content.
- **The deployed JS was fetched back over HTTPS** (15,864 bytes) and carries
  `createElement('progress')`, `Assembling & verifying file`, `Upload complete`
  and `needsReauth`.
- **All seven guides are gated, not broken** — each 302s to
  `/login?next=/help/<guide>` for a browser and returns
  `401 session_expired` to a script, which is what distinguishes a working
  auth gate from a 500. The `next=` preserves the guide, so signing in lands on
  the page that was asked for.

### Still carried forward

- **No human has exercised a chunked upload, the re-auth path, or the new
  guides.** Everything above is automated HTTP, a node truth table, and the
  suite. The guides in particular have never been *read* by anyone.
- `admin_required`'s **403** for an authenticated-but-`read_only` script caller
  still renders HTML — same `.json()` problem, different case, still unaddressed.
- **Rollback trees are back to 5** after being pruned to 2 earlier today; four
  deploys in one session rebuilt them. Worth knowing before the next prune.

## 2026-08-31 (third deploy) — `bb2b276` live at `v=143`: the re-auth case that actually happens

**`bb2b276` is live on `https://archiosk.com`**, replacing `2d80d1f`. Confirmed
from systemd: `Gunicorn - ArchiOSK GO (accepted build bb2b276)`.

Rollback marker **`/var/www/archiosk-backup-2d80d1f`** (841 files, `.env` at
`600`, pre-edit unit). Rollback trees now **4**; 8.6G used / 89G free.

**`STATIC_VERSION` 142 → 143**, stepped as `CURRENT + 1` from the live file.

### What this fixes, and why the previous deploy only half-fixed it

The entry below recorded the discovery that `CLAUDE-SESSION-EXPIRY-JSON-01`'s new
`401 session_expired` path is unreachable for a POST: Flask-WTF's CSRF check is a
`before_request` hook, so it runs **before** the view's `@login_required`, and
the CSRF token is bound to the session — an expired session takes the token with
it. Every request `chunked_upload.js` makes is a POST, so handling only the 401
handled only the case that cannot occur here.

`needsReauth()` now recognises 401, `session_expired`, `csrf_expired`, the literal
`"CSRF token expired"` reason, and a 400 carrying an explicit `redirect`.

### The guard that mattered most

`needsReauth()` returns **false for any ok response, on its first line**.
`upload-complete` returns a `redirect` field on **success** — the workspace URL to
return to — and the completion path consults this helper *before* testing
`response.ok`. Treating a bare `redirect` as a re-auth signal without checking
status first would have sent every completed upload to the login page. The
directive did list `data.redirect` as a trigger; it is honoured, scoped to 4xx.

### Evidence

`needsReauth()` was **extracted from the shipped file** and run under node
against a 12-case truth table — not a retyped copy, so it tests what ships. All
pass, including the success-carrying-`redirect` trap and correct discrimination
between `csrf_expired` and ordinary 400 refusals (`unsupported_format`,
`invalid_chunk`, `integrity_failed` all correctly false, as do 404 and 500).

Lane: **153 passed** (session expiry, chunked upload, api auth, csrf expiry, csrf
protection, auth shell isolation, route authorization).

**The full suite was deliberately not re-run**, and the reasoning is recorded
rather than assumed: nothing under `routes/`, `services/`, `templates/`,
`models.py`, `config.py`, `app.py` or `migrations/` changed — only `static/js`
and one test — which is the condition `CLAUDE.md` actually states. The two
suite-wide scanners that glob **every** `static/js/*.js`
(`test_landing_simplify_01`, `test_p40vw7b_qa2_header_vestibule_link_fix`) were
identified by search and run explicitly rather than assumed irrelevant: 35
passed.

### Verified live

- Dry run: **3 modified, 0 new, 0 deletions**, exactly matching
  `git diff --name-status`; 838 metadata-only re-copies.
- `/health` 200 (public and internal), `/login` 200, `/gateway` 302, no journal
  errors across the restart.
- Assets serve **`?v=143`** in served content.
- **The served JavaScript was fetched back over HTTPS and inspected** — it
  carries `needsReauth`, both `csrf_expired` occurrences, the `CSRF token
  expired` reason and the `response.ok` guard. Verifying the file on disk would
  only have proved rsync worked; this proves what a browser will actually
  receive.
- `Cache-Control: public, immutable, max-age=2592000` on that asset — a 30-day
  cache, which is precisely why the version bump is not optional.
- nginx `[crit]` monitor still active after the deploy.

### Still carried forward

- **No human has yet exercised a chunked upload**, and now no human has exercised
  the re-auth path either. Everything above is automated HTTP and a node truth
  table. The feature's whole point — a large drawing set uploading in pieces
  through a real browser, and an expired sign-in mid-upload returning the person
  cleanly to the login card — remains unverified by a person.
- `admin_required`'s **403** for an authenticated-but-`read_only` script caller
  still renders HTML: same `.json()` problem, different case (a standing
  authorization decision, not an expiring session), still deliberately
  unaddressed.
- Rollback trees are **4**. Pruning remains a deliberate per-occasion decision.

## 2026-08-31 (second deploy) — `2d80d1f` live at `v=142`: chunked upload, JSON session expiry, and the ordering discovery that qualifies it

**`2d80d1f` is live on `https://archiosk.com`**, replacing `e7e8962`. Confirmed
from systemd rather than from commands exiting zero: `systemctl show
archiosk-go.service -p Description --value` returns `Gunicorn - ArchiOSK GO
(accepted build 2d80d1f)`.

**Rollback marker: `/var/www/archiosk-backup-e7e8962`** — 832 code files plus the
pre-edit `.env` at mode `600` and the pre-edit unit, inside that sibling tree.
Rollback trees are now **3** (`e7e8962`, `f332681`, `9d16b8c`), 8.6G used / 89G
free.

**`STATIC_VERSION` 141 → 142**, and this time it was genuinely required —
`static/js/chunked_upload.js` is new. Stepped as `CURRENT + 1` read from the live
`.env`, never as an absolute number, per the runbook's own record of a bump that
once landed *below* what production was serving. Verified in **served content**:
`main.css?v=142`, `login.js?v=142`, `ocean_field.js?v=142`, `pwa.js?v=142`,
`voice_input.js?v=142`.

Steps 7 and 8 skipped, verified rather than presumed: `git diff` over
`requirements.txt` and over `models.py`/`migrations/` are both empty for this
range.

### Ten commits, and the dry run proved the change set exactly

The delta was `e7e8962..HEAD` — **not** the two most recent commits. The
originally-stated range began at `1401304`, which had never been deployed; naming
the rollback tree from it would have produced a marker for a commit that was
never live.

Step 5's itemized dry run resolved the change set to **8 modified + 9 new = 17
files, zero deletions**, matching `git diff --name-status`'s own 8 `M` and 9 `A`
exactly. 824 further entries were metadata-only re-copies — the `git archive`
timestamp artifact — which is why a `-v` listing's raw line count is not evidence
of anything. The only protected-path name in the output was `.env.example`, the
tracked template that is *supposed* to deploy.

### The discovery: CSRF runs before the auth gate

`CLAUDE-SESSION-EXPIRY-JSON-01` makes `login_required` return
`401 {"error": "session_expired", "redirect": ...}` to a script instead of a 302
an XHR would follow into unparseable HTML. Verified live, both halves:

- browser-shaped `GET /projects/some-project/workspace` → **302** to
  `/login?next=/projects/some-project/workspace`
- script-shaped (`X-Requested-With`) → **401** with exactly that JSON body

**But a POST does not reach it.** Flask-WTF's CSRF check is a `before_request`
hook and therefore runs *before* the view's own `@login_required`. A script POST
without a valid token is refused as `400 {"error": "csrf_expired"}` first — and
because the CSRF token is bound to the session, a session that has expired takes
the token with it. So in practice:

| | what a script actually receives |
|---|---|
| GET, expired session | `401 session_expired` ← the new path |
| POST, expired session | `400 csrf_expired` ← the pre-existing CSRF handler |

This was found by testing the deployed endpoints rather than by reading the code,
and it is recorded because it **narrows what the new work actually changed**. The
401 path is real, correct and live, and it is not the path most chunked-upload
failures will take.

It is not a regression — `CLAUDE-CSRF-EXPIRY-01` already made that 400 a clean
JSON refusal rather than a raw Flask-WTF error page, so a script gets a parseable
body either way. What is **not** yet handled is the client: `chunked_upload.js`
auto-redirects on 401 but merely *reports* a 400 `csrf_expired` as
`Refused (CSRF token missing or expired)`. The reviewer sees an honest message
and no automatic return to sign-in.

**Deliberately not fixed in this deploy.** Stacking a further change onto a
just-completed production deploy, to fix something discovered during its own
verification, is how a good deploy becomes a bad afternoon. Carried forward
below.

### Verified live

- `/health` **200** (public and internal), `/login` **200**, `/gateway` **302**.
- Both new endpoints registered and gated: `upload-chunk` and `upload-complete`
  return **302** to a browser and a JSON refusal to a script.
- No `error|traceback|exception|critical` in the journal across either restart
  (the deploy restart and the `daemon-reload` restart for step 12).
- The nginx `[crit]` monitor survived the deploy: timer active, last run
  `Finished ARCHIOSK nginx critical-error check`.
- Deploy scratch removed from `/tmp` on both ends.

### Still carried forward

- **`chunked_upload.js` should treat `csrf_expired` the way it treats
  `session_expired`** — both mean "sign in again" to the person looking at the
  screen. This is the next change, not part of this deploy.
- **No human has exercised a chunked upload.** Everything above is HTTP-level and
  automated. The feature's whole point — a large drawing set uploading in pieces
  through a real browser — has not been done by a person, and the last time a
  human first exercised an upload path it found a 40-hour-old defect.
- `admin_required`'s **403** for an authenticated-but-`read_only` script caller
  still renders HTML. Same `.json()` problem, different case (a standing
  authorization decision, not an expiring session), deliberately unaddressed.
- **Rollback trees are 3.** Pruning remains the deliberate per-occasion decision.

## 2026-08-31 (feature) — Chunked document upload, lifting a deferral this repository had already written down

`CLAUDE-CHUNKED-UPLOAD-01`, committed as `aa8f550`. **1,180 insertions, zero
deletions** — the existing single-request upload path is untouched.

### This was a recorded deferral, not a new idea

`.env.example` has carried the reason verbatim: *"A full scanned drawing package
(100MB+) is NOT safely supported by this synchronous architecture yet … requiring
streaming/chunked upload or background processing, not something to raise this
number further to paper over."* This is that work. The note now says which half
is lifted, because "chunked upload exists" read as covering everything would be
worse than the original limitation:

- **Lifted** — the Workspace "Add Documents" surface (Admin → Project Data
  Management).
- **Still deferred** — every other surface, notably the new-project folder upload
  in `routes/portal.py`, which remains single-request and still bound by
  `MAX_UPLOAD_MB`.

### The limit was not where it looked

Three ceilings apply, and the binding one is not the obvious one:

| | |
|---|---|
| Flask `MAX_CONTENT_LENGTH` | **25 MB** (`MAX_UPLOAD_MB`) — the real limit |
| nginx `client_max_body_size` | 60 MB |
| gunicorn `timeout` | 150 s |

Raising all three is two lines of config and is a legitimate alternative. It was
not chosen because it does not survive a dropped connection at 90% of a 400 MB
transfer, and it holds the whole body in one `gthread` worker for the duration.

### A transport, not a second ingestion path

`upload-complete` performs the **identical** `add_source` +
`_register_source_content` sequence as `add_document_source`. A chunked document
and a single-request document are indistinguishable once registered — same kind,
same `origin_type`, same `source_registered` governance event, same
Spin-readability. A second ingestion path producing subtly different Sources
would be a provenance defect rather than a feature, so the test suite asserts
that equivalence **directly against a Source created the ordinary way in the same
test**, not by inspection.

### Three decisions that departed from the obvious

**Staging under `REGISTRY_STORE_PATH`, not `/tmp`.** `deploy/gunicorn.service`
sets `PrivateTmp=true`, so `/tmp` is a per-service namespace discarded on
restart — a deploy mid-upload would silently take every in-flight chunk with it.
And `services/bridge_queue.py` already records Phase 2 discovering that state
landing in one of fifteen workers is invisible to the other fourteen,
*"intermittent rather than broken - the worst way for something to be wrong."*
This is that conclusion applied rather than re-derived.

**`PendingReconcileStore` examined first and deliberately not extended.**
CLAUDE.md requires identifying what already serves the purpose before adding an
abstraction. Its `create()` takes the complete bytes of every file up front and
writes its manifest once — the opposite lifecycle to fragments arriving across
many requests. Its *pattern* is reused (directory under the store, JSON manifest,
the same 24-hour TTL); its contract is not.

**No client-side SHA-256, and the code says why.** `crypto.subtle.digest` has no
streaming API, so hashing a 400 MB file in the browser means holding 400 MB in
memory — the exact problem this feature exists to avoid. The server hashes
*while* streaming to disk, so the digest covers precisely the bytes that landed
rather than a re-read afterwards. The endpoint still accepts an optional client
digest; both the matching and mismatching cases are tested.

### Security properties

**Cross-project reach is inexpressible, not refused.** The manifest records the
owning project and every entry point re-derives the directory from an id
validated against `^[0-9a-f]{32}$` — so `..`, `/` and a drive letter all fail by
the same rule instead of by a list of things to strip.

**Authorization is re-checked on every chunk**, not once at chunk 0. An upload
spans minutes and many requests, and access can be revoked inside that window, so
the `upload_id` is a correlation handle and never a capability.

**`MAX_CHUNKED_UPLOAD_MB` (500 MB) is a deliberately separate ceiling.**
`MAX_CONTENT_LENGTH` bounds one request, and under chunking one request is one
~5 MB chunk — without its own ceiling, chunking would convert a bounded upload
path into an unbounded one, which is the obvious way this feature could make
things worse rather than better.

Chunks are written temp-then-renamed, so a retried chunk is never observable
half-written by an `assemble()` that only checks existence. Assembly streams into
a `.assembling` file that gets its real name only once fully written and
size-checked. Staged chunks are discarded only **after** the Source is durably
registered — cleaning earlier would make a failure between assembly and
registration unrecoverable.

### Evidence

**Full suite green: 6,055 passed, 2 skipped, 4 deselected, 1,973 subtests,
53:04, `PYTEST_EXIT=0`** — captured to a log file, never read through a pipe. All
32 `tests/test_chunked_upload.py` tests present in that run.

Three of those 32 failed on first write and were **my test bug, not the
implementation**: the fixture project legitimately already holds the baseline
document `ingest_upload` creates it with, so a `sources == 0` baseline was wrong.
Corrected to assert on the specific Source by name, which does not depend on the
fixture's shape.

Collection is now **6,061 / 6,057 selected**.

### Carried forward

- **`STATIC_VERSION` must be bumped on the SERVER at deploy.**
  `static/js/chunked_upload.js` is new and nginx caches `/static/` as immutable
  for 30 days. Bumped locally 141 → 142, but `.env` is git-ignored by design, so
  that bump **cannot** ship in a commit — `DEPLOYMENT.md` step 10 is the only
  place it happens.
- **Not deployed.** `e7e8962` remains live; this and every commit after it are
  unreleased.
- **Expiry sweeps on new-upload creation**, matching `PendingReconcileStore`. If
  no new upload ever starts, an abandoned set persists past 24 hours. That is the
  existing store's behaviour too, and is recorded rather than quietly accepted.

## 2026-08-31 (monitoring) — nginx `[crit]` alerting installed, and the bug its own fail-closed design caught on the first run

`CLAUDE-NGINX-CRIT-MONITOR-01`, committed as `db612af`/`80a466c`. Closes the gap
the entry below named: nginx wrote `[crit]` for ~40 hours and nothing read it.

### Why the application could never have caught this itself

nginx returned 500 **before proxying**, so gunicorn never saw the request. No
amount of application-side logging would have helped — the blind spot was
structurally outside the app. That is why the monitor watches nginx and nothing
else.

### What is installed, and deliberately where

`deploy/nginx_crit_monitor.py` → `/usr/local/bin/archiosk-nginx-monitor`, driven
by a systemd oneshot and a 5-minute timer, both tracked in `deploy/` and
installed to `/etc/systemd/system/` separately from the application sync —
exactly as `gunicorn.service` already is.

**Nothing is installed into `/var/www/archiosk`.** The application tree is an
exact export of one commit; adding a file to it would make the live tree stop
matching the deployed hash, which `DEPLOYMENT.md` step 12 exists to keep
checkable. Monitoring is infrastructure, so it sits beside `nginx.conf`.

### Two load-bearing properties

**It must not lose an alert.** The cursor advances only *after* delivery
succeeds. A failed send re-reports next run rather than swallowing the line.

**It must not invent one.** Rotation is detected by **inode**, not size.
logrotate runs daily here with `create 0640 www-data adm`, so a fresh file
legitimately starts at 0 bytes — a size-only check would replay the entire
previous day, every night, forever.

### The first live run failed, and that is the design working

`systemctl start` returned `Result=exit-code`:

```
nginx-crit-monitor: cannot read /var/log/nginx/error.log: [Errno 13] Permission denied
```

An empty `CapabilityBoundingSet=` drops `CAP_DAC_OVERRIDE`, and `error.log` is
`www-data:adm 0640` — so even **root** could not read it. The hardening was too
aggressive and broke the one thing the unit exists to do.

`SupplementaryGroups=adm` is the fix, and is genuinely least-privilege in a way
granting a capability would not have been.

The failure is worth recording because a monitor that *swallowed* that error
would have reported "no critical lines" every five minutes forever — strictly
worse than having no monitor, since it manufactures confidence. It is now
recorded in the unit file, the ops doc, and a test, because the next person
hardening this unit will be tempted to re-empty that capability set.

### Noise suppression, because a muted monitor is the failure mode

The dry run over the real log found **71 `[crit]` lines, 19 of them scanner TLS
handshake failures** — permanent internet background, not this server's fault.
Paging on those every five minutes gets the alert muted within a day, which
recreates the blindness. They are **suppressed, not hidden**: never alerting
alone, always counted in any alert that does fire, extensible via
`ARCHIOSK_ALERT_IGNORE` rather than by editing the script. A test asserts that a
real fault buried in 18 noise lines still alerts.

### Install order matters

Dry run → `--reset` → enable. At install the log held **52 actionable `[crit]`
lines, all of them the already-fixed incident**. Skipping `--reset` would have
made the monitor's very first message a false alarm about a solved problem,
spending its credibility before reporting anything real.

The dry run grouped the incident as `51 x [crit] ... open()
"/var/lib/nginx/<tempfile>" failed (13: Permission denied)` — confirming it would
have caught the original defect.

### Evidence

- `tests/test_nginx_crit_monitor_01.py` — **22 tests**, in the normal suite,
  loading the script by path the same way `test_storage_bridge_agent_04.py` loads
  `tools/storage_bridge_agent.py`.
- Host: `Result=success`, `ExecMainStatus=0`, timer enabled with next run
  scheduled, state cursor advancing.
- End-to-end detection proven against a scratch file, so the production log was
  never written to.
- Collection is now **6,029 / 6,025 selected** (6,004 + 3 route-guard tests from
  `2d91615` + 22 here). The `CLAUDE.md` baseline remains accurate because it is
  attributed to the tree `72a4a7d`..`9c2408f` rather than to "current"; **no
  full-suite pass count exists for the current tree** and none is claimed.

### An unrelated defect found while committing

`MANIFEST.md` was about to be committed with **284 lines of pure line-ending
churn** around a 3-line insert: `pathlib.Path.write_text` translates `\n` to
`\r\n` on Windows, and this repository stores every file as LF. Caught by reading
the diffstat rather than trusting it, fixed with a byte-level rewrite, and the
commit amended. Worth knowing because every checkpoint and MANIFEST edit in this
repository is made from Windows and the same trap applies to all of them.

### Still carried forward

- **The alert sink is currently the journal** — functional, but nobody watches a
  journal. Webhook and email sinks are implemented, tested and documented but
  **not configured**; email additionally needs the unit's `CAP_DAC_READ_SEARCH`
  lines uncommented, because `.env` is `0600`. Choosing a real destination is
  outstanding and is a Product Owner decision.
- `e7e8962` remains the live application commit. The monitor is infrastructure
  and shipped independently of it.

## 2026-08-31 (verification) — Document upload verified end to end by the Product Owner, and independently corroborated server-side: the upload-500 incident is CLOSED

**Reported by the Product Owner, 2026-08-31**, during authenticated browser use of
`https://archiosk.com`: the document upload processed cleanly with zero 500s, and
the document rendered and was indexed in the active project workspace.

> **Correction, added after this entry was first written.** The Product Owner
> subsequently clarified that the confirmation above was sent **before** the
> upload was actually performed, not after it. This entry originally implied the
> report described a completed action. It did not - the report preceded the event
> it described by roughly ninety seconds, and the upload then genuinely succeeded
> at 17:24:04.
>
> The corroboration below is unaffected and is what establishes the true order.
> That is the point worth keeping: a first check at 17:23 found `total sources:
> 0` and was **correct at the time**; treating it as final would have produced a
> confident, wrong report that the upload had failed. Neither the human report
> nor the machine check was sufficient alone. Only the two together, ordered by
> timestamp, say what actually happened.

Unlike the previous human-verification entry, this one is **not solely a report**.
The human judgement — that the document rendered and reads correctly in the
workspace — is the Product Owner's and is recorded as theirs. The mechanical facts
below were independently confirmed by this agent from the server's own state, and
the two agree.

### Server-side corroboration

- `instance/registry/222109-1860-alstep-dr.workspace.json` modified **17:24:04
  UTC**, growing 6,211 → **7,264 bytes** — it had previously been untouched since
  30 August 23:25.
- That workspace's Source count went **0 → 1**: `A-01.pdf`, `kind:
  project_document`, `origin_type: upload`, `removed_at: None`.
- The project's append-only governance log gained a **`source_registered`** event
  (actor `admin`), growing 481 → 1,011 bytes.
- **Zero** HTTP 5xx in `archiosk-go.service` since the fix, and **zero**
  `body/... Permission denied` entries in nginx since 16:04:41. The last 500 of
  any kind on this path remains 16:03:17, before the fix.

This is the first entry in this file where a human's verification and the
application's own persisted state have been checked against each other rather
than one standing alone.

### The two attempts are worth recording, because 302 does not mean what it looks like

There were exactly two `POST .../workspace/sources/document` requests after the
nginx fix, and **both returned 302**:

- **17:22:53 → 302 (261 bytes).** Not a success. The session had lapsed, so the
  POST was bounced; the very next request is
  `GET /login?next=/admin/reset-project-data`. Nothing was written.
- **17:23:24** — `POST /login` → 302: the Product Owner signs back in.
- **17:24:04 → 302 (297 bytes).** The real one. This is the request that wrote the
  workspace file and the governance event.

A 302 is the normal post-upload redirect **and** the normal auth bounce, so the
status code alone distinguishes nothing. Only the persisted state does. An
intermediate check run at 17:23 — between the two attempts — showed `total
sources: 0` and would have supported exactly the wrong conclusion if it had been
treated as final. The store, not the access log, is what settles whether an
upload happened.

It also incidentally demonstrates the authorization gate holding correctly under
real use: an unauthenticated upload POST was refused rather than processed.

### What this closes

- **The upload-500 incident (entry below) is CLOSED.** The
  `nginx -t -c`-induced ownership defect is fixed, and the path it broke is now
  proven working by a real human upload that persisted real state — not only by
  the synthetic 1MB/2MB buffered POSTs used to verify the fix at the time.
- **Authenticated browser verification of `e7e8962` is substantially exercised.**
  Sign-in, an authenticated session, the project workspace, document upload,
  rendering and indexing have all now been driven by a human against the deployed
  build. Recorded as what was actually reported and corroborated — Gateway and
  project-open were not separately named in this round, so this is not claimed as
  a complete sweep of every surface.

### Still carried forward

- **`e7e8962` remains the live commit**; the checkpoint commits after it are not
  deployed, and nothing in this entry changes that.
- **Nothing alerts on nginx `[crit]` lines.** The ownership defect ran for ~40
  hours unnoticed and was found only because a human hit it. That gap is
  unchanged by this verification.

## 2026-08-31 (incident) — Document upload returning 500: an `nginx -t` config test had silently re-owned nginx's temp directories

**Reported by the Product Owner during authenticated browser verification of
`e7e8962`.** Uploading a document to a project workspace returned **500 Internal
Server Error**. Root cause found, fixed and verified. **It was not a Python
fault, and it was not caused by the deploy.**

### There was no traceback, and that was the diagnosis

`archiosk-go.service`'s journal was clean — **zero** HTTP 5xx since the deploy
restart, and no `Traceback`/`Exception` anywhere today. That is not a gap in the
logging. The request never reached Python at all; it failed one layer up, in
nginx, which returned 500 before proxying to gunicorn.

The actual error, from `/var/log/nginx/error.log`:

```
2026/08/31 15:55:02 [crit] 413469#413469: *80650
  open() "/var/lib/nginx/body/0000000082" failed (13: Permission denied),
  client: 99.241.129.246, server: archiosk.com,
  request: "POST /projects/222109-1860-alstep-dr/workspace/sources/document HTTP/1.1"
```

with matching `POST .../workspace/sources/document → 500` access-log entries at
15:55:10, 15:55:31 and 15:55:53.

**A diagnostic note worth keeping:** the instinctive command
`journalctl -u archiosk -n 100` returns records for a **retired**
`archiosk.service` whose last entry is 11 August. It looks clean and sends the
reader onward to nginx for the wrong reason. The live unit is
**`archiosk-go.service`**.

### Mechanism

nginx workers run as `www-data` (`user www-data;` in `/etc/nginx/nginx.conf`),
but `/var/lib/nginx/body` was owned `nobody:root`, mode `0700`. Proven directly
rather than inferred:

```
$ sudo -u www-data touch /var/lib/nginx/body/_probe
touch: cannot touch '/var/lib/nginx/body/_probe': Permission denied
```

nginx spills any request body larger than `client_body_buffer_size` (~8–16k) to
disk. That is why the failure looked selective and intermittent: small POSTs such
as sign-in fit in memory and worked normally, while **a file upload never fits**,
so it failed every single time. `client_max_body_size 60M` is configured, so
nginx was accepting the upload and then failing to write it.

### Root cause: a configuration *test* mutated production state

All five temp directories — `body`, `fastcgi`, `proxy`, `scgi`, `uwsgi` — changed
ownership at the **identical nanosecond**, `ctime 2026-08-29 23:22:39.863329657`.
`auth.log.2.gz` names the command at exactly that second:

```
Aug 29 23:22:39 sudo: ubuntu : COMMAND=/usr/sbin/nginx -t -c /tmp/nginxtest/test.conf
```

`nginx -t -c <file>` run as root creates and **chowns the compiled-in temp paths
to whatever `user` that config declares**. The throwaway test config carried no
`user www-data;` line, so nginx fell back to its built-in default — `nobody`.
`nginx -V` confirms the binary was compiled without `--user`, so that default
applies. Validating a candidate config re-owned live nginx state as a side
effect, which is not a behaviour anyone would expect from a syntax check.

### It was not the deploy, and the coincidence is why that needed proving

The break predates `e7e8962` (deployed 15:34 on 31 August) by roughly **40
hours**. It surfaced only now because large POSTs are rare here: the first
occurrence in any log is a bot scan at 07:03 on 31 August, and the first real
user impact is the upload at 15:55 — **21 minutes after the deploy**. Every
rotated `error.log.*.gz` contains zero occurrences.

Without the `ctime` and the `auth.log` entry, the obvious and wrong conclusion
was that the deploy caused it. It did not; the deploy shipped one application
file and never touched nginx.

### The fix

```bash
sudo chown -R www-data:www-data /var/lib/nginx
```

Applied to **all five** directories rather than `body` alone. `proxy` was equally
unwritable, and `proxy_buffering` spills large *upstream responses* to disk — RFI
`.docx` exports and PDF/crop downloads were latent failures of exactly the same
kind that simply had not been hit yet. No nginx restart was required; `open()`
happens per request.

### Verified

- `sudo -u www-data touch` now succeeds in **all five** directories.
- **End-to-end, not just filesystem:** a 1MB POST — large enough to force nginx to
  buffer to disk — returned **404 from the application** rather than 500 from
  nginx, and the request is visible in gunicorn's own log, proving it traversed
  the layer that was broken. Repeated at 2MB, and against **`www.archiosk.com`**
  specifically, since the last failure at 16:03:16 came through that hostname.
- **Zero** `body/... Permission denied` entries after the fix. The last one ever
  recorded is 16:03:16; the successful buffered POST is 16:04:42.
- `/health` 200, `/login` 200, `/gateway` 302, service still on `e7e8962`.

One honesty note on the evidence: the verification probes wrote into those same
directories and therefore overwrote their `ctime`s, so post-fix `ctime` values are
not usable as a record of when the chown landed. The ordering above rests on the
nginx log timestamps and the successful buffered POST, which the probes did not
affect.

### Prevention

Never run `nginx -t -c <partial-config>` as root. Either use plain `nginx -t`,
which reads the real `/etc/nginx/nginx.conf` and so inherits `user www-data;`, or
include `user www-data;` in any standalone test config. The failure is silent at
test time and only appears later, on the next request large enough to need a disk
buffer — which may be days afterwards, as it was here.

### Still carried forward

- **Authenticated browser verification of `e7e8962` is now partially exercised** —
  the Product Owner reached the workspace and attempted a document upload, which
  is more than any previous entry could claim. It is **not** recorded as complete:
  the upload itself failed on this defect and has not yet been re-attempted
  successfully by a human since the fix.
- The `nobody`-owned state existed for ~40 hours before anyone noticed, because
  nothing alerts on nginx `[crit]` lines.

## 2026-08-31 (host cleanup) — Rollback trees pruned from 108 to 2, on explicit Product Owner instruction

**Product Owner directive, 2026-08-31.** `deploy/DEPLOYMENT.md` step 13 states
that removing older `archiosk-backup-<hash>` trees is "a separate, deliberate
decision each time, not part of routine per-deploy cleanup — don't automate away
your only rollback point." This entry records that decision being taken
deliberately, by instruction, for the first time. **106 generations removed; the
two most recent retained.**

- **Retained:** `/var/www/archiosk-backup-f332681` (829 files, `.env` at `600`)
  and `/var/www/archiosk-backup-9d16b8c` (826 files, `.env` at `600`) — verified
  as the two newest by mtime (15:32 and 10:19 on 2026-08-31) rather than assumed
  from their names.
- **Disk:** 11G used / 87G free → **8.6G used / 89G free**. Roughly 2.4G
  reclaimed, against a measured 1.8G of `du` in the trees themselves.
- `/var/www` now holds **6 entries**, down from 112.

### The dangerous neighbours, and why the glob was safe

`/var/www` contains two directories that are **real data backups, not code
rollback trees**: `archiosk-db-backups` (392K) and `archiosk-registry-backups`
(4.9M). Neither is recoverable from git, and losing either would be a materially
worse outcome than losing every rollback tree combined.

Both were explicitly proven to fall **outside** `archiosk-backup-*` before
anything was deleted — the glob requires the literal `archiosk-backup-` prefix,
and `archiosk-db-backups` / `archiosk-registry-backups` do not carry it. The live
`/var/www/archiosk` and `/var/www/html` were checked the same way. That check was
run as a positive test (does the glob's own output contain this path?) rather than
by reading the pattern and reasoning about it.

### How the deletion was constrained

The removal did **not** run `rm -rf /var/www/archiosk-backup-*`. An explicit
delete-list was materialised to a file and asserted against before use:

1. exactly 106 entries;
2. every entry carrying the `/var/www/archiosk-backup-` prefix;
3. neither retained tree present;
4. none of the four protected paths present;
5. no `..` or glob metacharacter in any entry;
6. every entry a real directory and not a symlink.

The list was then **re-validated inside the same command that performed the
deletion**, so no unverified gap could exist between checking and deleting, with
an abort path that removes nothing if the re-check disagrees.

One assertion failed spuriously on the first attempt and correctly stopped the
run: `grep -c` exits 1 when its count is zero, and under `pipefail` that read as
a failure even though the true count of offending entries was zero. Nothing was
deleted. Recorded because the failure mode is worth knowing — a safety check that
fails closed on its own bug is behaving correctly, and the fix was to the
assertion, not to the safety margin.

### Verified after

- Live tree intact: **837 files** (836 tracked from the deployed commit, plus
  `.env`), `.env` still `archiosk:archiosk` `600` at 813 bytes, `instance/` intact.
- `archiosk-go.service` **active**, Description still
  `Gunicorn - ArchiOSK GO (accepted build e7e8962)`, no `error|traceback|
  exception|critical` in the journal.
- `https://archiosk.com/health` **200**, `/login` **200**, `/gateway` **302**, and
  the Spin diagnostic still **401** — nothing about the prune touched the running
  application, which is the point.

### What this changes about rollback posture

Rollback depth is now **two generations, not 108**. `f332681` is the immediate
rollback target for the current `e7e8962` deploy, and `9d16b8c` is one further
back. Anything older is gone and is **not** recoverable — those trees were the
only copies of their build state, since the application directory is not a git
repository. This is an accepted, instructed trade, not an accident; every one of
those commits remains reconstructible from `origin/main` via `git archive`, which
is what makes the trade reasonable.

### Still carried forward

- **Authenticated browser verification of `e7e8962` remains outstanding** — see
  the deploy entry below. Unchanged by this cleanup.
- **The unexplained full-suite stall** remains unidentified and non-recurring.

## 2026-08-31 (deploy) — `e7e8962` deployed to `archiosk.com`, carrying 11 commits and exactly one application file

**`e7e8962` is live on `https://archiosk.com`**, replacing `f332681`. Confirmed
from systemd rather than assumed: `systemctl show archiosk-go.service -p
Description --value` returns `Gunicorn - ArchiOSK GO (accepted build e7e8962)`.

**Rollback marker: `/var/www/archiosk-backup-f332681`** — 827 code files, plus
the pre-edit `.env` at mode `600` (`archiosk:archiosk`) and the pre-edit systemd
unit, all inside that sibling tree rather than beside the live `.env`, which is
the mistake `CLAUDE-DEPLOY-ENV-BACKUP-01` records. Rollback trees are now **108**.

**`STATIC_VERSION` stays at 141** — correctly, and confirmed twice rather than
once: `git diff f332681..e7e8962 -- static/` is empty, and the served sign-in page
still returns `main.css?v=141`, `login.js?v=141`, `ocean_field.js?v=141`,
`pwa.js?v=141`, `voice_input.js?v=141`. Nothing for a cache bust to flush.

Steps 7 and 8 both skipped, **verified rather than presumed**: `git diff` over
`requirements.txt` and over `models.py`/`migrations/` are both empty for this
range.

### The range is large but the risk surface is not

Eleven commits, 13 changed files — and only **one** of them is application code
the running service actually imports: `routes/api.py`, gaining the admin-gated
Spin source-signature diagnostic (`7d7e078`). The other twelve are documentation
(`CLAUDE.md`, `MANIFEST.md`, `CONTINUATION_CHECKPOINT.md`, `.gitignore`), tests
and fixtures, and two `tools/` scripts that the service never imports.

That distinction was established from the diff before deploying, not inferred
afterwards, and it is why a deploy spanning eleven commits was a low-risk one.

### The dry-run earned its place in the procedure

Step 5's itemized dry-run (`rsync -ain`) resolved the change set exactly:

- **8 files with real content changes** (`>f.s…`, size differs) — precisely the 8
  `M` entries in `git diff --name-status`.
- **5 newly created files** (`>f+++++++++`) — precisely the 5 `A` entries.
- **819 metadata-only re-copies** (`>f..t…`, time/owner/group but identical
  content) — the `git archive` artifact this runbook already warns about, and the
  reason a plain `-v` dry-run listing 893 lines is not evidence of an 893-file
  change.
- **Zero deletions.**

The only protected-path name appearing anywhere in the output was `.env.example`,
which is a **tracked** file that is *supposed* to deploy — exactly the case the
runbook cites for why the exclude is `.env` plus `.env.bak-*` and not the broader
`.env*`. Live `.env` (813 bytes, mode `600`) and `instance/` were both confirmed
intact after the sync.

### What was verified live

- `https://archiosk.com/health` → **200**; internal `127.0.0.1:8000/health` → **200**.
- `/login` renders **4,525 bytes** with its real title, all three form fields
  (`username`, `password`, `csrf_token`), and a CSP `nonce` on its inline script —
  so `app.py`'s per-request nonce machinery is working, not merely present.
- `/gateway` unauthenticated → **302** to `/login?next=/gateway`, not a 500.
- No `error|traceback|exception|critical` in the service journal across either
  restart (the deploy restart, and the `daemon-reload` restart for step 12).
- **The new endpoint is genuinely live and genuinely gated.**
  `GET /api/v1/documents/some-project/spin-runs/some-run/source-signature`
  returns `401 {"error":"unauthorized"}` — not a `404` (so the route registered)
  and not a `200` (so the blueprint gate holds), byte-identical in shape to the
  pre-existing `/governance` control route tested alongside it.

### Not verified, and not claimed

**Authenticated browser verification was not performed for this deploy.** The
Claude browser extension was not connected, and this agent has no credentials —
authenticated verification is a Product Owner action, as `CIC-DEPLOYMENT` already
records. Everything above is unauthenticated HTTP and served-content evidence.

This deploy changed **no user-visible surface at all** — the one application
change is an admin-only JSON endpoint with no UI — so the visual scope that would
normally need a human eye is genuinely empty here. That is a reason the gap
matters less this time, not a reason to record it as closed. The verification
logged two entries below covers `f332681`.

**The full suite was not re-run at deploy time.** It last ran green on the tree
committed as `72a4a7d`..`9c2408f` (5,998 passed, exit 0); the three commits after
it changed only tests, `tools/` and documentation, each covered by a targeted lane
(239 passed, exit 0). No application code entered the range after that full run.

### Still carried forward

- **Rollback trees are 108** (~1.7G against 87G free). Pruning remains the
  deliberate per-occasion decision the runbook describes and still has not been
  taken. The two most recent generations (`f332681`, `9d16b8c`) are both intact.
- **The unexplained full-suite stall** remains unidentified and non-recurring.
- **`tests/fixtures/wd_nas_bridge/` remains deliberately untracked**, so it is
  structurally absent from the deployed tree — `git archive` exports the commit.

## 2026-08-31 (reconciliation) — The three open items from the entry below, closed; and a route no authentication test had ever touched

Three commits, pushed to `origin/main` at `414834f`:

- **`2d91615`** `fix(tests)` — closes an API route coverage gap and guards it with
  `RouteListsCoverTheRealBlueprintTests`.
- **`6a30dbb`** `chore` — the deprecated `fitz` alias retired in favour of direct
  `pymupdf` imports.
- **`414834f`** `docs` — `MANIFEST.md`'s API surface and `CLAUDE.md`'s test
  metrics reconciled against measured reality.

This entry closes **all three** items the entry below recorded as "Open items
recorded, not fixed."

### The finding: a documented surface audit turned up an untested route

The reconciliation began as documentation work — `MANIFEST.md` claimed nine
routes where the blueprint has 43. Enumerating the real surface from the live
`url_map` (rather than by reading decorators, which is what let the row drift in
the first place) produced the actual shape: **43 `api.*` rules, 24 admin-gated
via `_ADMIN_ONLY_ENDPOINTS`, 19 login-only.**

Diffing that ground truth against `tests/test_api_authentication.py`'s two
hand-maintained lists found
`POST /api/v1/documents/<project_id>/sources/<source_id>/snapshot`
(`api.create_document_snapshot`, CLAUDE-SNAPSHOT-DUAL-SURFACE-01) in **neither**.

It was correctly gated in production the whole time — it is listed in
`_ADMIN_ONLY_ENDPOINTS` and the blueprint-wide `before_request` hook enforced it.
What was missing was any test: absent from `API_ROUTES`, the "every route rejects
an unauthenticated request" sweep never touched it; absent from
`ADMIN_ONLY_ROUTE_PATHS`, which was consistent only because the route was missing
upstream of it. **Nothing failed.** A route nobody lists is a route nobody tests,
and the hook's own merit — that a new route cannot omit the gate by accident — is
exactly what kept the omission invisible.

That list's own comment claims it is kept explicit "so a route added later and
left out of this list is an obvious gap." It was not obvious. It was silent, and
the route had been in the blueprint long enough to carry its own CLAUDE- tag. A
comment asserting a property the file cannot enforce is the thing that actually
failed.

`RouteListsCoverTheRealBlueprintTests` now asks the app instead of trusting the
lists: it walks `url_map` for `api.*` rules, substitutes the same placeholder ids
the lists use, and asserts every registered route is listed, that nothing listed
has stopped existing (a stale entry asserts against a 404 and passes for the
wrong reason), and that `ADMIN_ONLY_ROUTE_PATHS` equals the actually-gated set in
both directions. It fails loudly on a route parameter it cannot substitute rather
than silently checking a path containing a literal `<param>`.

**Verified by mutation, not by passing.** Removing the snapshot entry from
`API_ROUTES` makes the guard fail naming that exact route; restored, all three
pass. A guard that has never been seen to fail is not yet evidence of anything.

### What the documents now say

`MANIFEST.md`'s `routes/api.py` row enumerates all 43 endpoints grouped by the
CLAUDE- tag each section already carries, with the gate stated per group, and
records two things a reader would otherwise have to rediscover: that `POST` and
`GET /relationships` share one path — which is *why* the test lists are keyed by
`(method, path)` — and that the Spin diagnostic is the one deliberate admin-only
READ, because it discloses a whole run's input set rather than a single object.
Its "Connects to" column now names the six services imported inside their
handlers, which the previous text omitted entirely.

`CLAUDE.md` carries the measured baseline in full rather than as one number:
**6,004 collected / 4 deselected / 6,000 selected → 5,998 passed, 2 skipped,
1,951 subtests, 25:28**, measured on the tree committed as `72a4a7d`..`9c2408f`.
Quoting all of them is the point — collected, selected and passed are three
different numbers here, and a lone "test count" silently meaning one of the
others is precisely how "approximately 4,964" drifted roughly a thousand tests
out of date without anyone noticing.

The pipe rule was also promoted into `CLAUDE.md`. It existed only in `705aa2a`'s
commit message, which is not where anyone looks before running a suite.

### The `fitz` retirement

`requirements.txt` has always said PyMuPDF is "Imported as `pymupdf`, not the
deprecated `fitz` alias", and `engine/pdf_extractor.py` — the application code
that actually depends on it — already complied. Three scripts outside the
application did not. `import pymupdf as fitz` would have satisfied the note's
letter while leaving every call site reading `fitz.`, so the rename went all the
way through; no `fitz` token remains anywhere outside the venv.

`generate_drawings.py` was deliberately **not executed**. It rewrites the tracked,
digest-pinned `builder_corpus/Drawings_Set.pdf`. Confirmed byte-identical after
the change — `sha256 41c6524e3343b760…`, still matching that corpus's
`manifest.json` exactly.

### Evidence

Targeted lane across the authentication, PDF-extractor, Nipigon, spatial-compiler,
metabolic-bridge and PSD corpus tests: **239 passed, 74 subtests, `PYTEST_EXIT=0`**,
redirected to a log with the exit code captured as its own line.

The full suite was **not** re-run for these commits, and deliberately so: nothing
under `routes/`, `services/`, `templates/`, `models.py`, `config.py`, `app.py` or
`migrations/` changed, which is the condition `CLAUDE.md` actually states. It was
also verified that no test reads `MANIFEST.md` or `CLAUDE.md` as data — every
reference to either in `tests/` is prose inside a docstring — so the documentation
half of this work carries no test risk at all.

### Why three commits and not one

The requested commit was a single `docs:` reconciliation. The route-coverage gap
is a security-test repair that the audit happened to surface, and burying it in a
documentation commit would hide it from exactly the person later asking when that
route started being tested. It also lands *first* on purpose: the new
`MANIFEST.md` row asserts that both test lists cover every route, and that
sentence only became true with `2d91615`.

### Still carried forward

- **Live production remains `f332681`.** None of `72a4a7d`, `7d7e078`, `9c2408f`,
  `edfd672`, `3ab4e6e`, `2d91615`, `6a30dbb` or `414834f` is deployed. The
  authenticated browser verification recorded two entries below covers `f332681`,
  not any of this work.
- **`tests/fixtures/wd_nas_bridge/` remains deliberately untracked** — no test
  reads it, and committing unused scaffolding would assert a dependency that does
  not exist.
- **Rollback trees are 107** (~1.7G against 87G free). Pruning remains the
  deliberate per-occasion decision the runbook describes.
- **The unexplained full-suite stall** remains unidentified and non-recurring.

## 2026-08-31 (later still) — The parked working tree audited and shipped: test-store isolation, a Spin input diagnostic, and a custody boundary that nothing enforced

Three commits, all on a full suite green **before** any of them landed:

- **`72a4a7d`** `test(infra)` — `tests/conftest.py` clears the test stores at
  session start, plus its guard test and the `CLAUDE.md` section describing it.
- **`7d7e078`** `feat(api)` — `GET /api/v1/documents/<id>/spin-runs/<run>/source-signature`,
  admin-gated, plus its own test and both `tests/test_api_authentication.py` lists.
- **`9c2408f`** `chore(fixtures)` — the held-out oracle boundary made enforceable,
  and the metabolic-bridge corpus's manifest and generator tracked.

### What was parked, and what it turned out to be

The tree had been carried, uncommitted, across the two entries below — both of
which flagged it as work whose green "covers more than what was deployed." It
was not abandoned scratch. It was three unrelated pieces of finished work with no
commit boundary drawn through them, which is why it needed an audit before a
commit rather than a `git add -A`.

The test-store piece is the one with teeth. `TestingConfig` points the registry
at a FIXED path, deliberately, so artifacts stay inspectable after a failure —
and nothing ever emptied it. `services/project_code.py` refuses to reuse a
Project acronym and the space is ~100 variants per name stem, so accumulation
eventually exhausts it. It had reached 815 entries and surfaced as 15 failures in
`test_write_collision_01.py` / `test_mobile_continuation_01.py`, features with no
relationship to the state actually accumulating. That is the worst shape a test
failure can take, and one measured run leaves ~130 entries — six or seven runs of
headroom remained.

### The finding: a documented custody property that nothing enforced

Five **tracked** test files — `test_storage_bridge_01.py`, `_trust_02`,
`_endpoints_03`, `_agent_04`, and `test_external_custody_disconnect_02.py` — each
assert in their own docstring that `tests/fixtures/wd_nas_bridge/oracle/`
"remains unread and untracked", and each corpus `manifest.json` names its oracle
as "private evaluation material" under an ingest rule of "Register only files
beneath `builder_corpus`".

Nothing enforced any of it. There was no `.gitignore` rule, and both oracle
directories sat untracked in the working tree. A single `git add -A` — the
obvious way to clear a parked tree — would have committed the held-out answers
and made all five of those claims false in the same stroke that recorded them.
Those two oracle directories are now ignored **by name**, following the
precedent that file already set for `tests/fixtures/nreocrc/_lab_instance_scratch*/`.

The first attempt used a `tests/fixtures/*/oracle/` wildcard and was wrong —
caught and corrected in the commit after `9c2408f`. "Oracle" is not one thing in
this repository: `tests/fixtures/psd/oracle/` is **deliberately tracked** and is
read by `tests/test_psd_smoke_corpus_01.py`, which asserts the file exists and
covers the required evaluation classes. The already-tracked file was never at
risk (git ignores only untracked files, which is why the suite stayed green), but
any file later added or renamed there would have been silently dropped and that
test would fail on a fresh clone with nothing explaining why. Held-out-ness is a
per-corpus decision, so each corpus is now listed individually. Verified with
`git check-ignore` in three directions: both held-out oracles caught, the PSD
oracle not caught either as it exists today or as a hypothetical new file.

**Neither oracle file was read at any point during this audit.**

`tests/fixtures/wd_nas_bridge/` (its `builder_corpus` and `manifest.json`)
remains deliberately untracked. No test reads it — the storage-bridge tests build
their own temp corpora inline — and committing unused scaffolding would assert a
dependency that does not exist.

The metabolic-bridge `manifest.json` records a digest for the already-tracked
`Drawings_Set.pdf`. It was verified against the bytes rather than trusted:
`41c6524e3343b760…`, 15515 bytes, both exact. A manifest that asserts a digest
has to be true or it is worse than absent.

### The suite

**5998 passed, 2 skipped, 4 deselected, 1951 subtests, 25:28, pytest exit 0** —
6004 collected, 4 deselected, 6000 selected. Targeted API/auth lane beforehand:
232 passed, 154 subtests, exit 0.

Both runs were redirected to a log file with the exit code captured as its own
line, never through a pipe. `705aa2a` records why: a piped run's `tail` reported
ITS OWN status as 0 and nearly landed a commit on a fabricated pass. The
background-task notification for this run likewise reported "exit code 0" for the
wrapper script, and that was **not** what was trusted — `PYTEST_EXIT=0` was read
out of the log.

One absence worth recording as understood rather than unexplained: the full run
printed no `[conftest] reset test stores` line, while the lane run did. That is
the hook behaving correctly. The lane ended with
`test_it_is_a_no_op_when_the_store_is_already_absent`, which removes the store
itself, so the full session started with nothing to remove and the message is
conditional on having removed something — the fresh-clone path, exercised at
full-suite scale.

At **25:28** this is the fastest full run recorded here, against 2:52:35 and a
stalled 4h27m on materially the same tree. That is further evidence the stall
logged below was non-recurring; it is **not** an explanation of it, which remains
unidentified.

### What this narrows in the two entries below

Both carry an item stating the 5998-pass result covered a COMBINED tree including
uncommitted work, of which "None of it shipped." Most of it has now shipped, so
that item is **narrowed, not closed**: `routes/api.py`,
`tests/test_api_authentication.py`, `CLAUDE.md`, `tests/conftest.py`, the PSD
spin-source diagnostic, the registry isolation test and the metabolic_bridge
fixtures are all now committed. The `wd_nas_bridge` fixtures remain untracked by
decision, so a run from a clean checkout still is not byte-for-byte the same test
population as the runs those entries describe. Those entries are left as written.

### Open items recorded, not fixed

- **`MANIFEST.md`'s `routes/api.py` row is stale**, and was already stale before
  this work. It documents only the original ~9 routes ("these six now all go
  through…") and was never updated for the MM1/MM2/MM3/MM6 additions, so the new
  diagnostic is not the cause and fixing it properly is a larger, separate pass.
- **`CLAUDE.md`'s stated collection size is stale** — it says "approximately
  4,964 tests in the current collection" against a measured 6004 collected /
  6000 selected. Its wall-clock list also predates the 25:28 run above.
- **`tests/fixtures/metabolic_bridge/generate_drawings.py` imports the deprecated
  `fitz` alias**, while `requirements.txt` explicitly notes PyMuPDF is "Imported
  as `pymupdf`, not the deprecated `fitz` alias." Two existing `tools/` scripts
  do the same, so it is consistent with practice but contradicts the stated
  convention. Not run by any test.

### Still carried forward

- **Rollback trees are 107** (~1.7G against 87G free). Pruning remains the
  deliberate per-occasion decision the runbook describes.
- **The unexplained full-suite stall** remains unidentified and non-recurring.
- **Nothing here is deployed.** These three commits are pushed to `origin/main`
  and have not been released to `archiosk.com`; the live commit remains
  `f332681`. The authenticated browser verification recorded in the entry below
  covers that deploy, not this work.

## 2026-08-31 (later) — Product Owner authenticated browser verification of `f332681`: the standing gap is closed

**Reported by the Product Owner, 2026-08-31.** This entry records a HUMAN
verification, not a machine one. Nothing below was observed by this agent; it is
logged as the Product Owner's own report, with that provenance explicit, because
the whole value of this record is that a person actually looked. Attributing it
otherwise would make the strongest evidence in this file indistinguishable from
the weakest.

**Verified live on `https://archiosk.com`, authenticated:**

- Gateway.
- Project-open, on Project North Star.
- Workspace top-nav.
- Clean wordmark rendering and the lettermark favicon, with **zero residual mark
  artifacts**.
- CSRF and session handling.

### What this closes

The **"NOT VERIFIED IN AN AUTHENTICATED BROWSER"** item carried forward by the
two entries below is **CLOSED**. It had been open across two deploys, and
`CIC-DEPLOYMENT` names authenticated browser verification as a known limitation
precisely because it needs a Product Owner session. Those entries are left
exactly as written — the item was genuinely open when each was recorded, and
editing them to say otherwise would falsify the record of what was known at the
time. This entry supersedes the item; it does not rewrite its history.

Two things in particular now have human confirmation that no test in this
repository could supply:

- **The lettermark purge (`9d16b8c`) is visually confirmed.** Its own commit
  message records that the retired mark's real defect was only visible at
  shipped sizes — a bowtie at 16px beside the wordmark, an hourglass in a
  browser tab — and that the Product Owner reported it three times before it was
  believed. Byte-identical assets and a green suite were never going to settle
  that; "zero residual mark artifacts", seen, is what settles it.
- **CSRF and session handling behave correctly for a real signed-in user.** The
  deploy verified both handler branches by request, but `WTF_CSRF_ENABLED` is
  `False` under `TestingConfig`, and no test in this repository exercises a real
  browser session at all.

### One question raised, deliberately not resolved here

The verification names the opened project as **Project North Star**.
`CLAUDE.md` records `CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01` as **APPROVED
and UNEXECUTED**, conditioned on its own text — *"After this Spin, ask Codex to
rename the project"* — with no such Spin review on record.

This agent did not authenticate and so cannot say what the project's live
display name currently is. Either the rename has since been executed (a real
state change that deserves its own record, since the condition it was gated on
does not appear to have been met), or the approved future name was used
informally for a project still live under its earlier identity. **Recorded as an
open question rather than resolved by assumption**, and no "North Bayview"
reference anywhere in this repository has been touched: `CLAUDE.md` is explicit
that those are historical evidence of work genuinely done under that name, not
drift to tidy, and rewriting them would falsify provenance against
constitutional invariant 3.

### Still carried forward

- **The 5998-pass suite result covers a COMBINED tree** including uncommitted
  in-progress work (`routes/api.py`, `tests/test_api_authentication.py`,
  `CLAUDE.md`, plus untracked `tests/conftest.py`, the PSD spin-source
  diagnostic, the registry isolation test, and the metabolic_bridge /
  wd_nas_bridge fixtures). None of it shipped; the green nonetheless covers more
  than what was deployed.
- **The unexplained full-suite stall** (78% in 4h27m, then 100% in 2h52m on the
  same tree) remains unidentified and non-recurring.
- **Rollback trees are 107** (~1.7G against 87G free); pruning remains the
  deliberate per-occasion decision the runbook describes.

## 2026-08-31 — `f332681` deployed: graceful CSRF expiry, and a green suite that was not green

`f332681` is **live on `archiosk.com`**, carrying four commits: this checkpoint's
previous entry, the two `POL-MULTI-MODEL-COMMAND-SAFETY` policy commits, and the
CSRF expiry handler itself. **`STATIC_VERSION` stays at 141** — correctly, and
confirmed from the diff rather than assumed: `git diff 9d16b8c..f332681 --
static/` is empty, so there is nothing for a cache bust to flush. Rollback
marker: **`/var/www/archiosk-backup-9d16b8c`** — 824 code files plus the
pre-edit `.env` at mode `600` and the pre-edit unit file, inside that sibling
tree.

Steps 7 and 8 both skipped, verified rather than presumed: no `requirements.txt`
change and no `migrations/`/`models.py` change in the range. `app.py` was the
only application code in it.

### The feature — an expired CSRF token is a timeout, not a fault

An idle mobile session or an overnight form previously hit Flask-WTF's own raw
"Bad Request - The CSRF token has expired" 400 page. `app.py` now registers a
handler on `CSRFError` specifically — never a blanket 400, which would relabel
every ordinary validation fault as an expired session.

**The part that was not obvious, and would have shipped as dead code.** The
natural implementation is to branch on the existing `_wants_json()`. That helper
tests `request.path.startswith("/api/")`, and every blueprint mounted under
`/api/` is `csrf.exempt` — so a CSRF failure can never arrive on an `/api/` path
at all, and the JSON branch would have been unreachable while looking correct in
review.

The real JSON casualties are the page-level `fetch()` calls in `static/js`
(`case_workspace.js`, `draft_assist.js`, `investigation_snapshot.js`,
`drawing_image_viewer.js`). They POST to NON-exempt blueprints with an
`X-CSRFToken` header and then call `resp.json()`. An HTML redirect makes that
throw, so an expired token surfaced as the generic "a network error occurred"
catch — a wrong diagnosis of a routine timeout. `_csrf_wants_json()` therefore
keys off HOW the client asked (the `X-CSRFToken` header, `X-Requested-With`,
`is_json`, or an Accept that STRICTLY prefers JSON) rather than where. The
strictness is load-bearing: `Accept: */*` scores JSON and HTML equally, and a
non-strict comparison would turn ordinary form posts into JSON replies.

Verified LIVE on both branches, not merely that the service came up — two
harmless rejected POSTs against a nonexistent user:

- form POST, no token → `302` to `/login`
- fetch-style POST, stale `X-CSRFToken` → `400`
  `{"error":"csrf_expired","message":"CSRF token missing or expired"}`

That live check also proves CSRF is genuinely enforced in production, which the
suite structurally cannot: `WTF_CSRF_ENABLED = False` under `TestingConfig`.

### Two existing assertions superseded — strengthened, not relaxed

`tests/test_csrf_protection.py` asserted `400` for a rejected POST. The HTML
branch now returns `302`, so those assertions had to change — and the hazard is
that a SUCCESSFUL login is also `302`, so simply swapping the number would have
left tests unable to tell rejection from success at all.

They now assert the security property directly: a rejected POST redirects to
`/login` and leaves **no `user_id` in the session**; a successful one redirects
to `/` and sets one. Strictly stronger than the status code it replaces. The
rejection MECHANISM was superseded; CSRF enforcement is unchanged.

### The suite episode — a green that was not green

Worth recording because it nearly caused a false-green commit, and because the
mechanism is already documented in this repository and still caught us.

The first full-suite run was launched as `pytest -q 2>&1 | tail -40` in the
background. Three separate failures compounded:

1. **`| tail` buffered everything.** The output file sat at **0 bytes for 4h27m**
   — no progress visible at all.
2. **`| tail` reported ITS OWN exit status.** The task notification said
   `completed (exit code 0)`. That was `tail`'s zero, not pytest's. This exact
   trap is already recorded in this file's own 2026-08-29 entry, and it still
   very nearly landed a commit on a fabricated pass.
3. **`-q` gave only dots**, so nothing could name a hung test.

The run also genuinely stalled: **4h27m to reach 78%, with only 861s of CPU**
(~5% utilization) and no open network connections. It was killed, which is what
made the pipeline exit 0.

The re-run redirected straight to a file with `-u -v` — incremental writes, one
named line per test — and a separate watchdog armed to fire on 15 minutes of
zero log growth, because **a hang produces no completion notification at all**
and passive waiting is therefore not a strategy. It completed cleanly:
**5998 passed, 2 skipped, 4 deselected, 1951 subtests, 2:52:35, pytest exit 0**
— captured explicitly, not read off a pipe.

**The stall's cause is unidentified and did not recur.** Same tree, same
machine: 78% in 4h27m the first time, 100% in 2h52m the second. Recorded as an
open unknown rather than explained away. Note also that 2:52:35 exceeds the
2:44:54 maximum `CLAUDE.md` records; that range is left alone on a single
sample, consistent with its own instruction that duration is not an assurance
signal.

**Operational rule this produced:** never pipe a background test run through
`tail`. Redirect to a file. The exit status you read must be pytest's own.

### Carried forward

- **STILL NOT VERIFIED IN AN AUTHENTICATED BROWSER.** Unchanged from the
  previous entry and now two deploys old. Sign-in renders and the CSRF handler
  is confirmed live by request, but Gateway, opening a project, and the
  workspace surfaces have not been exercised by a human since the lettermark
  purge. `CIC-DEPLOYMENT` names this as a known limitation; it is not resolved
  by anything above.
- **The full suite ran against a COMBINED tree.** The 5998-pass result includes
  uncommitted in-progress work present in the working directory at the time
  (`routes/api.py`, `tests/test_api_authentication.py`, `CLAUDE.md`, plus
  untracked `tests/conftest.py`, the PSD spin-source diagnostic, the registry
  isolation test, and the metabolic_bridge/wd_nas_bridge fixtures). None of it
  shipped — `git archive` exports the commit, not the tree — but the green
  covers more than what was deployed, and a later run without those files is
  not strictly the same test.
- **Rollback trees are now 107** (~1.7G against 87G free), across two naming
  conventions. Not urgent; pruning remains the deliberate per-occasion decision
  the runbook describes and still has not been taken. The two most recent
  generations (`9d16b8c`, `1db81eb`) are both intact.

## 2026-08-30 — `9d16b8c` deployed at `v=141`, and a prior deploy that had synced but never restarted

`9d16b8c` (the lettermark purge — the constructed mark retired, the app icon
becomes a letter A) is **live on `archiosk.com` at `STATIC_VERSION=141`**,
verified in served content rather than by command exit status. The rollback
marker for this deploy is **`/var/www/archiosk-backup-1db81eb`** — 825 code
files, plus the pre-edit `.env` at mode `600` and the pre-edit
`archiosk-go.service` unit file, both held INSIDE that sibling tree and never
beside the live `.env`, per `CLAUDE-DEPLOY-ENV-BACKUP-01`.

Relative to the previously-running build this carried five commits, not one:
`5c5b4ef`, `932c905` (Gemini vision), `0eb6b16` (GO Decision Architecture),
`1f2b150` and `9d16b8c`. No `migrations/` or `models.py` change, so
`deploy/DEPLOYMENT.md` step 8 did not apply.

### The finding — the deploy was already half-done, and inert

The routine was run from step 1, and steps 2–7 turned out to be **no-ops that
had already happened**. A prior run had synced the tree at `15:10:36 UTC` and
stopped there. A checksum-based `rsync -avnc` — ignoring mtime, comparing
content — reported **zero file differences** against a fresh `git archive` of
`9d16b8c`, and `google-genai==2.20.0` and `segno==1.6.6` were already installed
and importing in the venv.

**The service had never been restarted.** Gunicorn's `ExecMainStartTimestamp`
was `01:34:42 UTC`, roughly fourteen hours BEFORE the code it was supposedly
running reached the disk. The workers were serving `1db81eb` from memory, which
is also why the systemd `Description` marker still naming `1db81eb` was
accurate about the running build while the disk sat a release ahead.

That produced the exact mixed state step 10 exists to prevent, already in
progress. nginx serves `/static/` directly from disk, so the NEW CSS and icons
were being served under the OLD `?v=140` URL: every browser holding a cached
`v=140` stylesheet kept the old CSS, every new visitor got the new CSS rendered
by old Python, and `/health` returned 200 throughout. **A successful sync and a
green `/health` prove nothing about which code is executing.** The 2026-08-18
entry below already recorded that principle in the abstract — this is its
concrete instance, and the gap it hid was fourteen hours wide.

### What completing it actually required

`.env` bumped 140 → 141 using the runbook's `CURRENT + 1` form read from the
live file, not an absolute number, because the recorded near-miss is a bump that
landed BELOW production and looked like success. The requested value, the live
`+1`, and `9d16b8c`'s own commit message (`STATIC_VERSION 140 -> 141`) all
independently agreed at 141. The unit `Description` was updated `1db81eb` →
`9d16b8c` and `daemon-reload`ed BEFORE the restart, so a single restart
activated code, environment and marker together rather than the runbook's
literal restart → bump → restart; step 7's own "restarted twice" reasoning is
the warrant for that deviation.

### Verification — served content, not exit codes

Service active since `20:06:42 UTC`. Journal error/traceback/exception grep
empty. `/health` 200 on both `127.0.0.1:8000` and public HTTPS. Served assets
now carry `?v=141`. `archiosk-mark` appears **0** times in the served
`main.css` and **0** times in the rendered sign-in HTML, and the retired
`.gateway-logo` / `.workspace-app-mark` classes are absent from the served
stylesheet. `app-icon-192.png` fetched over HTTPS is **byte-identical** to the
blob in `9d16b8c`.

`static/app-icon.svg` matches only after newline normalization. This machine's
`core.autocrlf=true` converts LF → CRLF during `git archive`, so deployed TEXT
files are not byte-identical to their committed blobs while the rasters are.
Harmless to rendering, but it means byte-comparing any deployed text file
against its commit will always show a false difference — worth knowing before
someone reads one as corruption. `.gitattributes` currently disables conversion
only for the NREOCRC corpus and the vendored PDF.js files. Recorded, not
changed: it is a repository-wide decision, not a deploy-time one.

### Carried forward

- **NOT VERIFIED IN AN AUTHENTICATED BROWSER.** The sign-in page renders and the
  retired mark is absent from it, but Gateway, opening a project and the
  workspace surfaces were not exercised — that needs a Product Owner session,
  which `CIC-DEPLOYMENT` already names as a known limitation. The lettermark is
  proven present in the served bytes; it has not been LOOKED at, and the
  2026-08-25 entry's warning applies unchanged — a green suite and matching
  checksums do not prove the human interaction is good.
- **`GEMINI_API_KEY` is unset on the host**, which is the supported steady state,
  not a degraded one: `services/sheet_vision.py` completes its local PyMuPDF
  extraction and returns an honest `skipped_reason`. Setting it is a separate,
  credential-touching decision, and `ACTION_GEMINI_VISION_REQUEST` still gates
  transmission independently of the key.
- **Host scratch and rollback trees are accumulating.** `/tmp` holds five
  superseded staging directories (`archiosk-deploy-staging-62fcfb1`,
  `archiosk-stage-{61c088b,9d9bd0b,b99597a,f4e422c}`) and two `bhive-pre-*.db`
  files from prior sessions; `/var/www` holds **106** `archiosk-backup-*` trees
  totalling **1.7G** under two different naming conventions
  (`archiosk-backup-<hash>` and `archiosk-backup-pre-<hash>`). At 87G free this
  is not a threat, and step 13 was followed for this deploy's own scratch. But
  `CLAUDE-DEV-CLEANUP-01` found the same accumulation before and the backlog
  predating it is untouched — pruning older generations is the deliberate,
  per-occasion decision the runbook says it is, and it has not been taken.

## 2026-08-28 (later) — Phase 1: the Page-Field entry environment, and the archive it came out of

A read-only design archaeology of an artifact outside this repository produced a
design rule, a custody alarm, and then an implementation. Recorded together
because the implementation is only justified by the archaeology.

### The archaeology — `governance/proposals/fish-tank-design-archaeology.md`

The "fish tank" is `C:\Archiosk\holodeck\archive\` — **232 files, 19,337,785
bytes, 2026-05-03 to 2026-05-10**, cited once by `291d2cf` and never part of
this repository. Two things about it matter here.

**Custody is the finding with a deadline.** That directory is `.gitignore`'d out
of its own repository (holodeck `4360f99`, "metabolize archive copies out of
active Git tracking"), which tracks 5 files. The archive therefore exists as a
single uncommitted copy on one disk, versioned only by filename. It is the sole
record of the mechanisms below, which appear in no commit message or note
anywhere. See `governance/proposals/holodeck-archive-custody.md` and
`tools/backup_holodeck_archive.ps1` — the script is written and verified (232
files → 3,578,945 bytes, 5.4×, every file re-hashed after round-trip; and
`-VerifyOnly` re-checks the live tree against the manifest, distinguishing
additions from ALTERED files so corruption is not laundered into the backup).
**Tier 1 has NOT been run against a permanent destination** — that needs a
volume from the Product Owner and is the outstanding ask.

**The invariant the lineage produced:** *moving things are atmosphere and are
unreachable; reachable things do not move.* The archive's v1.9 word-fish were
`pointer-events: none` and faked being caught with cursor-distance arithmetic —
they looked interactive and were inert to keyboard and touch. Five versions of
rework followed (v2.16 → v2.17 → v2.17.1 `FIXED` → v2.17.2 `REPAIRED` → v2.18
bespoke swimmer geometry) before v2.20 abandoned the approach entirely: *"Fix
clickability using real HTML anchor links only. No JavaScript is required."*
Independently, `291d2cf` refused the fish for this repository and `c6bd26b`'s
landing layer states the same boundary in shipped code.

Three mechanisms were recovered that existed only in the artifacts:

- **Channel separation.** Both surviving engines drove motion through LAYOUT
  POSITION (`left`/`top` in `archiosk_holodeck_v_3.html`, `margin-*` keyframes
  in v2.20) and neither ever wrote `transform` — because a running animation on
  `transform` wins the cascade over the `:hover`/`:focus-visible` transform and
  silently deletes the focus affordance. The physics owns position; the
  interaction state owns `transform`.
- **Proximity may change appearance, never position.** v1.9 drifted its objects
  toward the cursor and so made them unacquirable; `v_3.html` kept the proximity
  band and deleted the drift.
- **Hover-freeze.** Hovering halts the object's orbit, so a moving target can be
  acquired. Single observation; whether it suffices for motor-impaired users is
  recorded as **unmeasured**.

**The warrant for stillness is the archive's own.** `v_3.html` carries two fish
taxa: `procurement-fish`, driven by `requestAnimationFrame`, and `signal-fish`
— Risk, Assumption, Decision, RFI, Cost — positioned by static CSS and never
touched by the animation loop. At v3.0 the objects stopped meaning "where you
go" and started meaning "what you must not miss", and in the same step they
stopped moving. §5 of the record also corrects a provenance claim that was in
uncommitted work at the time: it asserted the archive physics "only ever wrote
`transform`", which is false in every stratum and inverts the actual reason
focus worked.

### The implementation — Phase 1 baseline

A **Page-Field** is a stable, touchable miniature window into a real surface.
The interior face carries identity; the footer strip only confirms it. Five
tiles, deterministic territories, `175.00 × 152.17px` each — measured identical
across every face, because the aspect is declared once on `.cl-field-face` and a
test asserts it is never overridden per face.

**Two scenes, and only one on the page at a time.** This was built wrong first
and the correction is the point: the field was a band bolted on TOP of the
workspace, making the entry environment a header row inside the very surface it
is an entry to. The workspace is now wrapped in `.cl-surface`, the body carries
`data-scene`, and the CSS uses `display: none` — not offscreen, not
`visibility: hidden`. Measured: **0 focusable elements inside the hidden
workspace**. A hidden workspace still in the tab order is worse than an absent
one. Tapping M-201 enters Scene 2; the return contracts to the field and
restores focus to the tile that was opened.

**Every number on a tile is derived, and absent rather than zero when the record
supports nothing.** Counts carry a stated meaning, and `field_count` returns
`None` where nothing is countable — a zero would itself be a measurement.

- **Specimen 01 — M-201, `live`.** The only surface whose miniature can honestly
  claim `live`: `templates/_calm_lake_plan.html` defines the plan geometry once
  and both the full canvas and the miniature call it, so the miniature is not a
  picture of the drawing and cannot drift from it. `MINIATURE_VIEW` crops the
  viewport to the building extent, and pin coordinates are PROJECTED into that
  crop — a raw sheet percentage puts the pin in the wrong room, arithmetic no
  screenshot review catches, so it has its own test.
- **Specimen 02 — Spin, `kind`.** No Spin fixture was invented. The derivation
  trace already existed in the findings: run → finding → side. Rendered as 3
  findings, 6 sides, and the one `asserted` side draws hollow with a broken
  link, because it names a document without establishing one.
- **Intake is not a Page-Field and the model says so** — it opens nothing, so it
  declares no miniature basis, emits no `data-miniature`, and counts nothing.
- **Card 5 is SP-001, not "Specifications / Addenda"** — the directive asked for
  addenda; the fixture holds none, and a category label implying documents that
  do not exist is the failure this grammar refuses.

**A CSP defect the static harness cannot see.** Scene 1 first used inline
`style="--x:…"`. It rendered perfectly in the preview because `http.server`
sends no CSP header, while `app.py` sets `default-src 'self'` with no
`style-src`, which refuses parsed inline style attributes.
`test_no_inline_style_attributes_anywhere` caught it. Fixed with the page's own
idiom — `data-*` plus `style.setProperty`, a CSSOM write the CSP permits, as
`.cl-mark` already does. Territory became enumerated CSS classes instead: the
set is small and closed, and a field that will not lay out without JavaScript is
worse than a pin that will not position without it.

### Verification

- **110 Calm Lake tests**, up from 63.
- **Pre-existing failures, confirmed not caused here** by running them against a
  clean `HEAD` worktree: `tests/test_write_collision_01.py` (5) and
  `test_p40vw8qa_site_wide_visual_consistency.py::…::test_tokens_css_hardcoded_hex_only_appears_in_token_definitions`.
  The latter is real drift that arrived with the Calm Lake commits —
  `calm_lake.css` defines 18 raw hex values and that test globs every stylesheet
  except `tokens.css`. **Open decision:** exempt the prototype explicitly, or
  adopt `tokens.css` variables. Not resolved silently either way.
- **`MANIFEST.md` drift fixed.** The Calm Lake prototype landed six tracked
  files in `a4cfb19` and none were ever registered. Added, along with the new
  files.
- **`STATIC_VERSION` is now 126.** It had been bumped to 124, which is BELOW the
  deployed baseline of 125 recorded above — a downgrade that would have left the
  new CSS stale live. `.env` is per-host and git-ignored, so the deploying host
  must set its own value above 125.

### Not done, deliberately

The live archive still has no backup. Scene 1 leaves ~350px of empty field below
five cards at 844px; the approved 175px footprint was kept rather than scaling
cards up unilaterally. Only M-201 opens — the other tiles say so rather than
transitioning to a blank workspace. `spike/multi-surface-canvas` remains
unmerged and unreviewed.

## 2026-08-28 — A canvas preview that could not exist, and the governance record it recovered

A directive asked for a local interactive preview of the multi-surface canvas on
`spike/multi-surface-canvas @ f0a12ce`. It was not executable, for two reasons
that were verified against the repository rather than assumed, and the stage
ended as a governance repair instead. Recorded because the negative result is
the durable part.

### Why the preview could not be built

- **There is no canvas at `f0a12ce`.** That commit is the one that DELETED the
  control-arm scaffold. `routes/spike_arm_b.py` and
  `templates/spike/arm_b_canvas.html` were built and removed before commit, per
  this repository's own discipline that exploratory apparatus stays out of
  version control. Confirmed against the tree — no `templates/spike/` entry, no
  `spike_arm_b` module, no canvas blueprint among `app.py`'s registrations —
  not inferred from that commit's message. The branch name records the
  EXPERIMENT, not a surviving surface.
- **The standing no-localhost rule forbids the server.** The Product Owner rule
  ("No localhost. Work on the application that the Product Owner actually sees
  online") covers `python app.py` and `127.0.0.1:5000` for development,
  testing, inspection and browser proof, explicitly including throwaway
  pre-deploy checks. The `pytest` suite remains the one carve-out; it binds no
  port.

A local branch `preview/ui-surface` and an isolated worktree were created, then
removed on Product Owner instruction. `git worktree remove`, `git branch -D`,
nothing left behind. `f0a12ce` was confirmed reachable from
`origin/spike/multi-surface-canvas` before the branch was deleted, so nothing
was lost.

### What actually landed — `dec5efb`

`governance/proposals/surface-vs-substrate-interaction-grammar.md:283` cited
`governance/specified-unbuilt/provenance-at-the-point-of-interaction.md` as
"Full record:". That file existed only at `f0a12ce` on the unmerged spike and
**did not exist on `main`** — a dangling citation of exactly the class `d849501`
("PROVENANCE_BASIS_* was never written") was written to correct.

The 116-line record was landed verbatim from `f0a12ce`, byte-identical. One
subsection was added, **C.1**, recording the single rebuild constraint the
record did not state: the canvas is not recoverable from git, so a rebuild
starts from specification, not code. No new governance document was created —
the chrome trap is already measured in the grammar at 2.6 and restated in
section C, and a third copy would be the proliferation cycle `CLAUDE.md` names.

### Constraints that now bind the formal Canvas UI phase

- `static/js/pdf_viewer.js` resolves **30** document controls by
  `getElementById` against `templates/base.html`'s menu bar; in a chrome-less
  render they are all `null` and degrade silently. A meaningful share of the
  permanent chrome is the implementation of **Look**, not accretion. Any
  placement work must supply canvas-native Look first or carry the menu bar
  with it. **This is 30 bindings, not the ~10 control families it looks like at
  a glance** — an earlier count in-session said ~10 and was wrong.
- The acceptance bar is **record-grounded** provenance
  (`AnalysisRun.source_ids`), never links parsed from statement text. Arm B was
  more reachable and epistemically weaker, and its subject trusted its links
  completely: a citation that can lie is worse than a UUID.
- Chrome costs attention, not steps. Both arms reached the correct answer in
  three views.

### State at close

`main` @ `dec5efb`, pushed and verified via `git ls-remote` (`0/0` divergence).
Governance markdown only — no `routes/`, `services/`, `models.py`, `config.py`,
`app.py` or migrations touched, so the full suite was not the gate. `MANIFEST.md`
unchanged by design; it states that `governance/*.md` is deliberately not
catalogued there.

**`spike/multi-surface-canvas` remains unmerged and is not superseded by this.**
Only its governance file was landed. The station/presence spike code on that
branch — `routes/station.py`, `services/presence_bus.py`, `services/station.py`,
the `c72da4e1b806_station_enrolments` migration and their tests — is still
branch-only and unreviewed.

Also unrecorded here and still only in git: the four `2026-08-28` governance
proposal commits this stage builds on (`48e9cdd`, `fb06d17`, `f70ba81`,
`d849501`) — the Surface vs. Substrate grammar and the Scale Regions /
Dimensional Reconciliation proposal.


## 2026-08-25 (later) — Entry simplified, Q made a real container, a development bridge, a Composer pen, and a capture preflight

Continues the entry above, which stopped at `dae1045`. Six further stages
landed the same day; this records them so the durable record is not six commits
behind the code. Deployed baseline is now `1cfb711` at `STATIC_VERSION=125`.

> **Correction, 2026-08-29.** That last sentence has since gone stale and was
> believed on two later occasions before being checked. **Production is serving
> `STATIC_VERSION=133`, measured** — an anonymous `curl` of `archiosk.com/`
> returns `app-icon.svg?v=133`. The `125` above is left standing because it was
> true when written and this file is a record, not a dashboard; it is corrected
> here rather than overwritten.
>
> The failure mode this caused is worth naming, because it nearly shipped
> twice: a local `.env` was bumped to `124`, then `128`, both **below** what
> production was already serving. Deploying either would have *lowered* the
> version, left every browser on its cached stylesheet, and made the new CSS
> invisible live — a silent no-op that looks exactly like a successful deploy.
> `.env` is per-host and git-ignored, so nothing in a diff can catch this.
>
> **Do not trust a recorded version number before a deploy. Measure the live
> one.** `curl -s https://archiosk.com/ | grep -oE '\?v=[0-9]+'` costs nothing
> and is the only authority — per this repository's own precedence rule, the
> deployed state is evidence and a checkpoint that disagrees with it is the
> thing that drifted. Local is now `135` — bumped again for the voice/vector
> tranche below, which changed three stylesheets and four scripts.

### What landed

- **`CLAUDE-ENTRY-SIMPLIFY-01`** (`ae4ff02`) — the two-card "Choose where you'd
  like to work" gate is RETIRED. It presented as a governed choice while
  persisting nothing, granting no authority and setting no account role, and it
  only ever appeared for people whose projects span both environments — in
  practice admins. Environment filtering moved to `/projects`, beside search,
  where it reads as a filter. This RESTORES `GO-NEUTRAL-ENTRY-01`'s principle
  literally rather than reinterpreting it.

- **`CLAUDE-MULTI-IMAGE-Q-01`** (`8af7bf7`) and **`CLAUDE-Q-MATERIALS-01`**
  (`4ffa119`) — a Q accumulates photos, then any material type. **Neither
  needed a new container**: `case["source_ids"]` has always been a list and
  `attach_source_to_case` has always appended to it. Both stages added a missing
  VERB. Every material type already had a governed ingestion path; the document
  and text-record paths simply never attached to anything, deliberately, because
  "a Case draws on Sources, it does not own them" — a model this work preserved.
  Authorization rows are in `governance/STATUS.md`.

- **`CLAUDE-DIAGNOSTIC-BRIDGE-01`** (`79d335d`) — capture a live product problem
  where it happened. **The bridge is a PULL, and that is the architecture, not a
  limitation**: ARCHIOSK cannot call a development agent, which runs on an
  operator's machine when a human starts it. Capture writes an inert row a
  session reads later, and the receipt says "Recorded as", never "sent to
  Claude". Admin-only, and code modification/deployment are deliberately
  UNREPRESENTABLE as states. First new database table since verification tokens;
  the reasoning (Reset/Restore renames the flat-JSON store away, so an
  application diagnostic must not die with a project reset) is recorded in the
  migration itself.

- **`CLAUDE-COMPOSER-DRAFT-ASSIST-01`** (`fb5ee25`) — a pen beside the Composer.
  The risk it is shaped around is not clumsy rewriting but a model quietly
  ADDING a dimension, a drawing number or a commitment into text then issued as
  an RFI, so the no-invention rule is absolute and stated FIRST in the prompt.
  The draft is never overwritten: exactly two lines write to the textarea, both
  inside click handlers.

- **`CLAUDE-CAPTURE-REVIEW-01`/`-02`** (`8eb3fd9`, `5e4df8d`, `1cfb711`) — look
  at the photo before attaching it. **The ordering was the real defect**:
  normalization ran the instant a file was picked, so any crop would have cut
  into an already-downscaled re-encode and lost exactly the detail construction
  review needs. Crop now works on the original, stored as fractions and
  converted to source pixels once. Orientation was INVESTIGATED and found
  `NOT NEEDED` — no `createImageBitmap` anywhere, no `image-orientation`
  override, every decode through an `HTMLImageElement`, and the server reads
  EXIF orientation as metadata only — so no rotation machinery was built.

### Two findings about our own process, worth more than the features

**Lane E earned its place twice in one day.** It caught four stale tests I had
already shipped past, and a contract I had broken (a fourth "Undo" in the
workspace body). Bounded lanes missed both.

**Reverse-reference discovery cannot find body-scanning contract tests.** At
`5e4df8d` a deliberately wide 20-file discovery set still missed
`test_p40e3a_layout_reconciliation.py`, because that file references none of the
changed files or symbols — it renders the page and scans tokens. Widening the
grep can never fix this; only rendering the page or running Lane E can. Recorded
here rather than in `TEST_LANES.md`, which is another agent's recent work.

### Certification and deployment

`cffe532` certified 4917/0 and deployed at v=124. `5e4df8d` certified 4963/1 —
the one failure was the Undo contract, repaired in `1cfb711`, which certified
**4964 passed / 0 failed** and is deployed at **v=125**, verified by checksumming
deployed files against the certified commit.

Full-suite duration is now observed between 27:57 and 59:47 for the SAME suite
on the same machine hours apart. Treat pass/fail as the signal; the clock is not
a regression indicator.

### Carried forward — nothing here has an unknown status

- **NOT VALIDATED BY THE PRODUCT OWNER**: the Pen, capture preflight and crop,
  multi-image Q, Q materials, the diagnostic bridge, entry simplification, the
  `/projects` environment filter. All live; none confirmed in a browser. **A
  green suite does not prove the human interaction is good.**
- **EXPERIMENTAL pending acceptance**: app icon, landing brand, startup sonic
  cue — by explicit Product Owner instruction, not promoted to brand governance.
- **OPEN GATE**: the Pen's RFI factual-restraint trials were requested and never
  returned; that acceptance remains `VALIDATION INCOMPLETE`.
- **NO BROWSER TEST HARNESS.** Every test on the Pen and the capture preflight
  is a source-structure or service-level assertion. This is the single largest
  assurance gap in the repository.
- **Investigated, deliberately not built**: construction-native reasoning
  vocabulary (`INTERESTING BUT NOT YET WARRANTED` — `games_played` has no oracle
  yet); the self-test laboratory (`VALUABLE PRINCIPLE — IMPLEMENTATION NEEDS
  REASSESSMENT` — it targets `BHiveParser._check_consistency`, and the
  intelligence surface has since moved to Spin and the Composer, which it knows
  nothing about); cross-device conversation recovery (designed, unbuilt).
- **The largest unexploited lever found by investigation**: extracted document
  text is discarded after ingest and there is no retrieval layer of any kind, so
  GO reasons over a corpus it has largely never read back. That, not any new
  runtime technology, is the constraint worth attacking next.

## 2026-08-25 — Mobile distribution, a redesigned icon, a startup cue, and a cross-user privacy defect found and repaired

**The important item is the defect, not the features.** A cross-user privacy
disclosure was introduced earlier in this same working session, reached
production, and was live for roughly a day before the full suite caught it.

### CLAUDE-CASE-PRIVACY-REPAIR-01 (`5627a79`) — fixed, deployed, verified

`64eb700` moved the conversation list into the shared shell and iterated
`workspace.cases` — every Case in the Project. Any reviewer who could open a
Project saw every OTHER reviewer's PRIVATE Case titles, by name, on every
authenticated page. The audit that followed found the same mistake a second
time in `45fddf5`'s document export, which wrote those titles into a
downloadable `.docx`/`.xlsx`/`.pdf` — worse, because the file then travels.

`CaseWorkspaceStore.visible_cases_for` is the one governed enforcement point
and its own docstring already named this exact mistake. Both loops were written
anyway. **The lesson worth carrying forward is not "filter case lists" — it is
that this codebase's own docstrings encode hard-won boundaries, and a new UI
surface that touches project data must be checked against them before it
ships.** No test existed for the switcher because the switcher was new; the
suite caught it only because seven older tests asserted whole-page absence.

Repaired with the EXISTING mechanism only (`open_visible_cases`, already
computed and already passed to the template), fail-closed on both sides: the
template defaults to `[]` when the filtered list is absent, and
`_export_document_for` takes it as a REQUIRED POSITIONAL parameter so omitting
it raises `TypeError` rather than leaking. `tests/test_case_privacy_switcher_
disclosure_01.py` (23 tests) asserts against the switcher markup and the
export's own rows, not the whole page, so a future failure names the surface.

Audit result, for the record: no other template iterates `workspace.cases`; all
route-level id lookups are guarded by `_require_visible_case` or
`visible_case_ids`; `routes/workspace.py`'s Accepted Knowledge read is
deliberately unfiltered by a documented pre-existing decision (reported, not
changed); `routes/portal.py`'s Reset inventory counts correctly and exposes no
title.

**Live verification honesty:** the authenticated two-user behaviour was NOT
exercised against production — no credentials, and pytest is deliberately absent
from the production venv. What was proven instead: the deployed files are
byte-identical to the tested commit once CRLF is normalised (`git archive`
applies CRLF here; `core.autocrlf=true`). That is inference from the artifact,
not observation of the live system. **A two-account live check remains
genuinely outstanding.**

### Correction to the entry above — the GO-NEUTRAL-ENTRY-01 "contradiction" was mine, not the record's

I reported that `GO-NEUTRAL-ENTRY-01` ("Superseded by: None") and
`routes/portal.py` ("explicitly and NARROWLY supersedes that one decision")
could not both be true. They can, and both are. **The two statements have
different subjects, and the identifiers differ by one prefix:**

- **`GO-NEUTRAL-ENTRY-01`** is the governance PROGRAMME record holding the
  accepted principle. Not superseded. Its own Lineage field already names
  `CLAUDE-POST-SIGNIN-GATEWAY-SIMPLIFICATION-01` as later "surface evolution",
  and its acceptance line already says that work "changed the physical surface
  without reversing the neutral-entry principle."
- **`CLAUDE-GO-NEUTRAL-ENTRY-01`** is the IMPLEMENTATION stage. A narrow
  sub-decision of it — that entry-time environment derivation was ruled out —
  is what was superseded.

The superseding decision is real and evidenced, not inferred: commit `cea176b`
records it verbatim as a Product Owner disposition — *"recorded explicitly per
Disposition B: this narrowly supersedes the entry-specific portion of
CLAUDE-GO-NEUTRAL-ENTRY-01 only. That decision's broader principle is
preserved; only entry sequencing changes."*

So the governance record is accurate, the code is inside the principle, and
**neither needed to change.** The only defect was that the docstring's "that one
decision" left its subject implicit while a near-identically-named record said
the opposite about itself — which is exactly the misreading it produced in me.
The docstring now names both identifiers and states which one was superseded.
No governance text, no behaviour, and no test was changed.

Worth keeping as a method note: when two records appear to contradict, check
that they are talking about the same subject before concluding either is stale.
Programme records and implementation-stage records in this repository are
routinely named `X` and `CLAUDE-X`.

### Shipped alongside, all EXPERIMENTAL pending Product Owner acceptance

- **`CLAUDE-MOBILE-PWA-01`** — ARCHIOSK is installable to a phone home screen.
  `templates/sw.js` + `manifest.webmanifest` served from the SITE ROOT (a
  worker's scope is its own URL path, so `/static/sw.js` could only control
  `/static/*`). The worker is written to be as close to inert as possible: HTML
  is never cache-first, the cache name carries `STATIC_VERSION`, old caches are
  deleted on activate, and only versioned `/static/` URLs are ever cached.
  `static/js/pwa.js` OFFERS a reload, never performs one.
- **`CLAUDE-MOBILE-ICON-01`** — a real app icon. Closed-base X, shorter
  upper-left arm, ends cut horizontally (left) and vertically (right), mitred
  feet. It is a FILLED OUTLINE generated by `tools/render_app_icon.py` because
  SVG's three line caps are all perpendicular to the stroke and both free ends
  are diagonal — the cuts are not expressible as a stroke setting. **Defect
  found on the way: `apple-touch-icon` pointed at an SVG in all four shells;
  iOS ignores SVG there and falls back to a screenshot of the page.**
- **`CLAUDE-LANDING-SONIC-01`** — a ~1.4s synthesised startup cue on the landing
  shell only. **iOS cannot sound on cold launch** — an AudioContext is created
  suspended and resumes only inside a real user gesture, and installing to the
  home screen does not lift this. It tries, then arms and plays at the first
  real tap. No silent-buffer unlock trick. Must never become the automatic
  spoken welcome retired in `aec1b04`.
- **Landing CSS defect:** `.landing-*` rules were first written into `main.css`,
  which `landing_shell.html` does not load — dead on the only page that uses
  them, and the test asserted against the wrong file and passed. Moved to
  `landing.css`, which also got the `100dvh` fix `main.css` already had; on iOS
  `100vh` is taller than the visible viewport, which is what put content "beyond
  the screen frame."

### Standing items

- **Two long-open questions now answered by evidence.** The 7-hour Lane E run
  flagged earlier did not reproduce: today's full runs were **1:04:28** and
  **27:05**. And the web-research slice (`5bd6e27`), whose Lane E gate was never
  completed, is included in the clean **4824-passed** run at `5627a79` — that
  gate is now satisfied.
- **Admin / all-projects entry flow was traced (read-only, no change made).**
  `/gateway` is a bare redirect; the real surface is `portal.index`. The
  Client/Owner vs Design-Builder/Proponent choice is `?environment=` only —
  nothing persisted, no authority granted, a filter over six list items. Admins
  see it solely because `can_access_project` returns True for them, so both
  sides appear. **A contradiction was reported here and there was none** - see
  the correction below. Also: account
  creation is CLI-only, access-request review does not exist, and project access
  assignment lives inside an open project rather than the Admin menu.
- The prior session's uncommitted `2026-08-18` entry below is left as it was
  found. One line in it — "Production deployment of application HEAD `4274808`
  remains outstanding" — is stale; many deployments have landed since, most
  recently `5627a79`. Recorded here rather than edited into someone else's
  provisional text.

## 2026-08-29 — Voice convergence, HTTPS harness, discipline containers

Landed in one tranche; full reasoning in `docs/DECISION_PROVENANCE_LEDGER.md`
DPL-0005.

**Voice.** `static/js/voice_input.js` is now the ONLY recognition engine in the
product. Its capability check was wrong in a way that produced the reported
"voice fails to respond": the `SpeechRecognition` constructor is *defined* on an
insecure origin, so `if (!Ctor) return null` passed, the mic was revealed, and
the start call failed on press. Measured on the phone's own origin
(`http://10.0.0.177:8642`): `isSecureContext false`, `navigator.mediaDevices`
undefined, constructor `"function"`. The guard is now
`!Ctor || !window.isSecureContext`. `static/js/landing.js` carried a second,
independently maintained copy of the whole engine — one report needed the same
fix in two files — and now keeps only its own router (`DIRECT_NAV`,
`INFORMATIONAL`, `FALLBACK`, and the transcription-variant patterns, all
preserved verbatim). Nipigon and Calm Lake gained mics that DISPATCH REAL
CONTROLS (`.click()` on a button a finger could reach), so voice can never
reach anything a tap cannot.

**Consequence worth knowing before testing.** Voice now works on `localhost`
and is correctly ABSENT on any plain-http LAN address. That is the browser's
rule, not ours. `tools/serve_https_harness.py` (new) serves a static harness
over TLS on `0.0.0.0:8643` with a self-signed certificate naming the LAN IP in
`subjectAltName`, and gzips SVG/CSS/JS in memory (A204.svg 9.82 MB → 779 KB on
the wire, verified byte-identical). `app.py` was deliberately NOT given an
`--ssl` mode; its `__main__` binds `127.0.0.1` by explicit decision and the LAN
exposure belongs in a tool that can reach neither the database nor a session.

**Still UNRESOLVED:** no sentence has been spoken into a phone yet. Everything
above is verified by construction and by test, not by a device. Also
unresolved: production serves these SVGs **uncompressed** — nothing in this
repository enables transport compression, so the 14.2x is real in the harness
and not on `archiosk.com`. That is a deployment-layer decision and no evidence
was gathered about what that layer currently does.

**Disciplines.** 5 Nipigon scene 1 is now one tile per trade rather than one
per sheet. Counted, not assumed: 39 A-series and 10 RS-series PDFs on disk;
the A100 DRAWING INDEX names Architectural, Structural (as **both** S1-S9 and
RS501-RS510), Mechanical M1-M5, Electrical E1-E5, Landscape L1, and Civil SP1.
Reading the cover sheet added Civil, which was in nobody's working list. Four
disciplines are named and delivered nothing; they render `unresolved` rather
than being omitted. Structural is `inferred`, not `direct`, because only one of
its two named numbering systems arrived and that disagreement is shown rather
than reconciled.

**DEPLOYED.** `9307bd3` is live on archiosk.com at `STATIC_VERSION=135`
(measured live before at 133 and after at 135 — never assumed from the local
file, which is per-host and git-ignored). Production was **13 commits behind**,
not one: the live tree was pinned by CRLF-normalised checksum to `dec5efb` or
an ancestor, so the deploy spanned `dec5efb..9307bd3` and carried Calm Lake,
Nipigon, Decision Mechanics and this tranche. `68ed4bb` rode along as an
ancestor. Rollback: `/var/www/archiosk-backup-pre-9307bd3` (764 files) and
`.env.bak-pre-9307bd3`; no database backup needed because nothing in the range
touches `migrations/` or `models.py` — re-verified across the TRUE range after
first checking only `127b72f..9307bd3`, which is the one-commit mistake
`deploy/DEPLOYMENT.md` step 7 warns about by name. Post-deploy sweep found
`static/demo_vector_desk.html` answering 200 on the public web root; moved to
`docs/demos/`. Full record: DPL-0005 Part 7.

**Also:** the landing page's portrait centering defect was `content-box` +
`min-height: 100dvh` + `8vh/10vh` padding = 118dvh; fixed with `border-box`
scoped to `.landing-page`. The scene-1 grid axis now keys on `orientation`
(portrait: one column of wide short bands; landscape: one row of equal
auto-columns) rather than on a width breakpoint.

**Request Trial Access pruned.** Eyebrow (a verbatim repeat of the h1),
explanatory paragraph, and the bottom Sign In / Explore pair all removed; the
top-left `← Archiosk` link is the sole exit. Note the consequence, which is
deliberate: the **confirmation state** now also exits only through that link,
where it used to offer three ways onward. Five tests failed on the removals and
each was classified rather than edited into agreement — two were defending copy
rather than intent, one is a real narrowing now asserted as such, one was a
correct `UI_REFERENCE_MAP.md` staleness failure (both rows marked **retired**
with reasons, not deleted), and one was a wrong assertion of mine caught before
commit.

**Crop rasters are gone from the pipeline.** `tools/render_nipigon_assets.py`
no longer emits `<sheet>_<label>.png` at a fixed dpi. A crop is a `viewBox`
view onto the one vector asset, so a second lower-fidelity picture of the same
region could only ever disagree with it — which is not hypothetical here.
**This surfaced a live defect:** the GO block's Jinja guard tested
`go.chosen.asset` (a raster crop) while rendering `target_svg.file` (a vector),
so retiring the crops would have silently deleted the whole GO affordance with
its vector present and usable. Now guards on `target_svg`.

**`tests/test_nipigon_vector_and_disciplines_01.py` (new, 21 tests).** This
surface had no test file at all. Nine guard the vector standard, seven the
counted discipline evidence, five the voice contract. One exists purely to
record a refusal: `test_no_plumbing_or_c_series_container_was_invented`.

**Two source-reading corrections, logged not silently applied.** The structural
S-series runs to **S10**, not S9 — the first regex was `\bS\d\b`, which
cannot match two digits and stopped without any sign it had. And a directive
asked for a "Plumbing / Civil (P / C-Series)" card: the A100 index has **no
P-series at all** (plumbing is the *title* of M1 and M2, inside Mechanical) and
the only `C1` on the sheet is a zoning designation in the project-data block,
not a drawing number. Civil is numbered SP1. No card was invented.

**"Field mode" does not exist — surfaced, not built.** A directive asked to
suppress the global project sidebar "in field/standard mode". A full read-only
map of the navigation surface found **no such mode anywhere** in the product;
`operating_environment` is a per-project stakeholder side, `developer_mode` is
an admin session boolean with no counterpart, and the PWA is responsive
behaviour nothing branches on server-side. Executing the clause would mean
inventing a new user-visible operating mode on one line of instruction, so
nothing in the authenticated navigation was changed. The seam it wants already
exists (`app.py:720` `_NO_PROJECT_LISTING_ENDPOINTS`), as does typed entry
(three search inputs) — the gaps are lookup-by-project-code and the orphaned
`GET /search` at `routes/portal.py:2855`, which returns exactly the JSON a
quick-open overlay needs and is referenced by nothing. See DPL-0005 Part 5 for
what would unblock it. The prototype surfaces never rendered the launcher panel
at all, so there is no cross-project leakage on the site desk today.

## 2026-08-18 — ARCHIOSK/GO Prompt, Visual, and Deployment Continuation

- `governance/prompt-depository/` exists and is the authoritative Prompt Depository. Preserved prompt records include:
  - `CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01`
  - `CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01A`
  - `CLAUDE-HOLODECK-WORLDS-SPIN-01`
  - `CLAUDE-PROJECT-WORLD-NAMING-01`
  - `CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01`
  - `CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01`
- The corrected blue Deep Ocean baseline is Product Owner accepted and governed; preserve it.
- The Bauhaus/Constructivist visual direction remains pending actual live review.
- Survival Mode / Project World live verification remains pending deployment.
- Production deployment of application HEAD `4274808` remains outstanding.
- `/health` alone is not proof that `4274808` is deployed; direct live-content verification is required.

## 2026-08-10 — CLAUDE-CA1D-INSTRUMENT-RAIL-01 (Plan Mode + Smallest Implementation Tranche)

**The Instrument Rail / Admin Machinery Zone architecture item queued by the prior checkpoint entry** (below) is no longer just planned — a Plan Mode pass ran first, then live Product Owner observation added two further requirements mid-plan, then an explicitly-authorized smallest implementation tranche landed as commit `c6cd56b`.

**Plan Mode pass:** repository-grounded (confirmed `HEAD == origin/main == 4c2fdb9` before starting, no prior implementation existed). Found the existing shell is 5 themed surfaces + 1 structural pane (Menu/Lists/Display/Toolbox/Chat + Eye), with exactly one existing "admin machinery lives at the periphery" precedent (Security Department: admin-gated page, reached from the Lists admin branch). Found `governance/current/wb1-adaptive-workbench.md` had already concluded the existing 5-surface grammar substantially satisfies "center = work, edges = state" in spirit, with full rail/navigation consolidation named as unbegun, unjustified future work — directly load-bearing prior art, not discovered independently by this round. Found two already-flagged, unresolved naming collisions ("Eye"/"Terminal Eye", "Terminal"/"Operational Terminal") to avoid compounding. **Recommendation:** no new persistent perimeter rail column — reuse the admin-page pattern for persistent machinery, plus one minimal top-bar line for ambient global facts.

**Two live-observed additions, mid-plan:** the Product Owner added, from watching real usage rather than reading the repository, a further split the first pass hadn't made: transient, command-specific execution state (active agents, spawned tests, waiting/completed subagents) should stay composer-adjacent, not be forced into the persistent perimeter — "persistent machinery lives at the perimeter; transient execution may remain close to the instruction that caused it." Plus a sparse, situational contextual-suggestion line, architecturally reserved but explicitly not required to be behaviorally built this round. This refined the plan from a two-way split (admin page + top-bar line) into a four-part one (admin page / top-bar line / composer-adjacent execution strip / contextual-suggestion line, the last reserved-not-built) — independently confirming, not contradicting, the first pass's core conclusion that a single rail column was never the right shape.

**Smallest implementation tranche (Section K), explicitly bounded:** proves three things, nothing wider.

1. **Persistent admin machinery has a legitimate peripheral home:** `routes/operations.py` + `templates/operations.html`, `@admin_required`, reached from the same Lists admin branch as Security Department. Wires `services.diagnostics.build_technical_telemetry` (built CLAUDE-P31, never previously rendered anywhere) into real page content, plus the live `AI_CALLS_DISABLED` kill-switch state. Repository/git diagnostics and subagent orchestration detail were explicitly excluded, not deferred silently.
2. **One quiet global machine fact lives in the top bar without clutter:** the same `AI_CALLS_DISABLED` state, admin-gated, rendered only when set — nothing added to the top bar in the ordinary case.
3. **One real transient execution state appears composer-adjacent and disappears when resolved:** `static/js/case_workspace.js` sets a new `#dock-composer-execution-status` span right before the chat composer's own classic (un-intercepted) form-POST fires — no fetch/AJAX, no new backend infrastructure, respecting `tools/dependency_fit.py`'s no-async-runtime/no-background-worker constraints. The browser's own default behavior (current DOM stays rendered until the response replaces it) makes "disappears when resolved" real, not simulated.

**Also landed, a live Product Owner visual refinement found mid-implementation:** the composer's top/bottom lane rules now permanently reuse `--machine-blue` (ARCHIOSK's existing chat/machine identity color, already used for `.conversation-message.system`'s role-label) instead of the neutral `--border`, gaining a matching top rule it previously lacked — no new token, composer surface/placeholder/mic/Send untouched, kept thin.

**Verification:** full suite run three times across this tranche. First run caught one real regression (`UI_REFERENCE_MAP.md` consistency test — the three new `data-ui-ref` values had no registry rows, and `templates/operations.html` wasn't yet in the test's own scanned-file list) and one CSS-selector test that still asserted the OLD composer border color/token the live refinement deliberately changed — both fixed as the existing test suite's own explicit convention already established (extend the scan, update the selector's expected value; never revert deliberate product-owner-directed CSS). Final run: **3,195 passed, 0 failed, 88 subtests.** Live browser validation (fresh sign-in, per this repo's own testing rule) confirmed: the Operations page reachable and rendering real telemetry/kill-switch content for admin, its Lists leaf absent for a non-admin render; the top-bar status line absent in the ordinary case; the composer execution-status text and Send-disable verified to be set by the actual registered submit handler (not a re-simulated one) via a capture-order-correct in-page event dispatch; the composer border color verified via `getComputedStyle()` to be `#235066` (`var(--machine-blue)`) on both edges, background still transparent. A throwaway `rail_browser_verify` admin account was created for this and deleted at close-out.

**Repository close-out:** implementation+tests commit (`c6cd56b`) → this documentation/checkpoint commit, on `main`, pushed to `origin/main` immediately after. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. `STATIC_VERSION` bumped twice in `.env` (once per `main.css`/`case_workspace.js`-touching pass) and verified served live.

**Explicitly deferred, not silently dropped — this tranche's own stated boundary:** the top-bar status line's underlying mechanism is proven but nothing else is wired to it yet; subagent/fork-level execution detail inside the composer strip; the contextual-suggestion line's behavior and trigger rules (when is a cue "materially helpful" vs. noise — needs a closed rule set before any code, to avoid becoming exactly the generic coaching layer the Product Owner ruled out); an internal terminal; live test-run progress; repository/git state display; execution watchdog/restart-safety signaling (no data source for any of this exists yet — the running web app has no mechanism to observe a Claude Code session's live state in real time; closing that gap needs its own bridging-mechanism design, not assumed solvable by UI work alone). Each is its own scoped follow-up, not bundled into this proof-of-pattern tranche.

## 2026-08-10 — CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION, Sections A/B (Compact Missing-Evidence Lines, Internal-First Document Opening)

**Two of the three items queued (not started) by the prior PO-01/PO-02 checkpoint entry**, now landed as commit `74bf51b`, following full-suite verification (`3,186 passed, 0 failed, 88 subtests`) and live browser confirmation against the real "Test 2" RFP project.

**Section A — compress missing-evidence notices:** a River Action Stack answer's opening caveat ("Not covered by this project's extracted evidence: `<full sentence>`") dominated the primary scan path even though the same detail already belonged inside whichever ranked action's own `uncertainty` field. Added an optional `missing_evidence_summary` field to the existing `answer_project_question` JSON schema (`services/project_qa.py`, `PROJECT_QA_PROMPT_VERSION` bumped `ca1d` → `ca1d-po02`) — a short, compact companion to the unchanged, full `not_covered` field — and steered the prompt to put action-specific evidence gaps into each action's own `uncertainty` field rather than the top-level `not_covered` when `river_actions` is populated. `services/conversation_interpreter.py` uses the compact "Missing evidence: X." line only when both `river_actions` and a summary are present; otherwise it falls back to the full sentence unchanged — material uncertainty is never silently dropped. **Live-verified:** the real model now naturally leaves the top-level caveat empty most of the time, since the gap already lives in the right place — confirmed by expanding a ranked action and finding the deadline-gap detail in its own `uncertainty` field, with a clean top-level scan path above it.

**Section B — internal-first document opening:** a Source with no dedicated in-app viewer (`.docx`/`.txt`/anything besides drawing/PDF/XLSX) fell back to the same `<iframe src=workspace.source_file>` PDF/XLSX use — but most browsers cannot render those formats inline, so selecting the document silently triggered an OS-level download the instant it opened. **Live-reproduced against the real `.docx` RFP Source** in "Test 2" before fixing. Replaced with a calm, honest in-app card (`display.document.no-preview`) plus two explicit secondary actions: "Open externally" (`as_attachment=False`, browser decides) and "Download" (`?download=1` on the same route, forces `as_attachment=True`). Drawing/PDF/XLSX Sources are completely untouched. Two pre-existing tests that asserted the old iframe fallback for a `.txt` Source were updated to assert the new card instead — their real invariant (PDF detection doesn't misfire for a non-PDF Source) was unchanged. Live-verified: the real `.docx` RFP Source now renders the card with correctly-linked actions, no iframe, no silent download.

**Repository state at this checkpoint:** implementation+tests commit (`74bf51b`) → this documentation/checkpoint commit, on `main`, pushed to `origin/main` immediately after. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**One item remains queued, not started:** the ARCHIOSK Instrument Rail / Admin Machinery Zone architecture plan (recorded, not built, in the prior checkpoint entry) still needs its own Plan Mode pass before any implementation. No River/Risk/Drawing-comment tranche expansion was begun.

## 2026-08-10 — CLAUDE-CA1D-RIVER-PO-01/PO-02 (River Action Stack, Provenance Precision, Highlight/Focus Grammar, Task Checkboxes, Reduced Chrome, LEFTPANEL-DENSITY-04)

**Product Owner live-use commissioning round**, authorized following the CA1D-RIVER-01/02/03 "fourth beat" work (`b8de35d`). A consolidated validation-and-correction cycle driven by live browser use of the real "Test 2" RFP project, landed as commit `94b9837`.

**River Action Stack** (`services/project_qa.py`, `PROJECT_QA_PROMPT_VERSION` bumped to `ca1d`): an optional `river_actions` field on the SAME existing single-call `answer_project_question` JSON schema — no second AI call, no new route. The model itself decides, per its own behavioral-contract instruction, whether a question is genuinely "what should I do next" (never forced onto ordinary factual answers). When present, `templates/_macros.html`'s new `river_action_stack` macro renders a small ranked set of actions (rank + heading only, collapsed by default), each independently expandable via the app's existing `subdisclosure`/`<details>` primitive — deliberately not a new "+/−" affordance — revealing rationale/consequence/uncertainty/evidence per action.

**Task/tag provenance precision, and a real defect found and fixed live:** the fourth-beat "Make a Task"/"Highlight this answer" controls anchor to the top-ranked River Action's own text (not the whole reply) when one exists — "prefer the smallest reliable source anchor available." Live verification against the real project found this broke the TAG path specifically: `app.py`'s `hotlinks()` renders a highlight by slicing `message.text[start:end]` using the *stored offsets directly* — it never searches for the quote's own content — so a river action's derived text (never a literal substring of the reply prose) produced a persisted, Tags-counted `tag_occurrence` whose `end_offset` exceeded `len(message.text)` and was silently dropped by `hotlinks()`'s own bounds guard on every render. Fixed in `services/conversation_interpreter.py`: Task keeps the precise anchor (its title/provenance metadata has no rendering dependency); Highlight always anchors to the whole answer, since the whole message genuinely is the smallest *reliable* anchor for that specific mechanism. New regression tests (`tests/test_ca1d_river_po02_provenance_precision.py`) lock in both the original defect and the fix.

**Eye-panel status fix:** task-creation feedback was visually landing near the Eye panel because the fourth beat reused `#conv-selection-status` (a `position: fixed` toast built for the unrelated selection toolbar) whose fixed viewport corner happens to coincide with Eye's own screen region in this app's shell layout — confirmed live via `getBoundingClientRect()`, not guessed. Removed the toast from this interaction entirely (`static/js/case_workspace.js`); feedback is now the clicked button's own label text, live-verified to leave the toast element hidden throughout.

**Shared highlight/focus grammar**, corrected through three live Product-Owner passes: (1) `.tag-highlight-inline` never set `color`, so the browser's UA default (`mark { color: black }`) silently beat intended `--text-primary` inheritance — invisible in Light, a real contrast failure in Dark; (2) the opaque fill was replaced with a translucent `color-mix()` wash ("content remains primary; highlight is an atmospheric layer behind it"), and the temporary source-return flash (`.conv-source-flash`) became a distinct animated glow rather than sharing the persistent mark's own look; (3) both were judged still too strong on a live multi-line passage and reduced again (persistent highlight 22%→12%; temporary flash's peak fill 22%→10%, with most of its visible effect moved onto a soft blurred box-shadow edge instead of a fill). Persistent and temporary states are now deliberately distinguishable in kind, not just intensity — contrast-verified by hand against this app's Light/Dark extremes at every step, and live-confirmed via `getComputedStyle()` in both appearance modes.

**Task checkbox:** "Mark complete"/"Reopen" text links replaced with a real, native `<input type="checkbox">`, immediately before the task title (`templates/base.html`), keyboard-accessible with a visually-hidden per-task label, submitting the same pre-existing `complete_task_route`/`reopen_task_route` on `change` — no second completion mechanism. Checked state uses `--accepted-green` (declared meaning: "accepted/confirmed" — a genuine semantic match). Live-verified full Open→Completed→Open round-trip, including exact computed colors.

**Reduced visual chrome:** the fourth-beat buttons dropped the shared `.review-btn` pill (a scoped override — Finding review's own pill is untouched) for a line-based, underline-on-hover treatment with a hairline divider between adjacent actions. The chat composer's text input dropped its all-around border/fill for a single bottom rule ("a disciplined lane, not a boxed widget"); Send remains a real, filled commit control.

**CLAUDE-LEFTPANEL-DENSITY-04:** a further Product Owner density pass on top of the earlier DENSITY-03 indentation fix. Row padding tightened on every tree row (heading/link/subheading/empty-state — the only source of inter-row spacing, since `.tree-node`/`.tree-children` carry no margin or gap of their own). `.launcher-link.active` moved from a full opaque `--surface-selected` fill to the same translucent `color-mix()` idiom (35%) plus a slim 2px `--machine-blue` edge accent, kept visually distinct from both `:hover` (plain wash, no border) and `.current-project` (border only, no fill, `--border-strong`).

**Tests:** 3,172 passed, 0 failed, 88 subtests (full suite, run twice across this stage — once before, once after the LEFTPANEL-DENSITY-04 pass — both clean). Three genuinely broken pre-existing test assertions were updated, not reverted-around: two composer-alignment tests and one left-panel test asserted the OLD specific values this stage deliberately changed; one site-wide visual-consistency test caught literal hex values this stage's own explanatory CSS comments had introduced (fixed by describing colors in prose instead).

**Live-browser verification:** a throwaway `po_verify_ca1d` admin account (suspended, not deleted — `tools/create_credentials.py` has no delete option) against the real "Test 2" RFP project. Confirmed live: River Action Stack rendering with independent per-item disclosure and correct ranking; a Task created from a River Action carrying that action's own text as its title, not a generic "Follow up: <question>"; the Eye-panel toast staying hidden through task creation; the highlight-rendering defect and its fix (both reproduced against the real project); translucent highlight contrast in both Light and Dark appearance via `getComputedStyle()`; the temporary-focus glow's correct structural behavior (its own 2.5s CSS animation is too short to catch mid-flight through CDP round-trip latency — a disclosed tooling limitation, not a defect, confirmed instead via a manually-applied class showing the correct post-animation transparent end state); the full task-checkbox complete/reopen round-trip; and the left-panel density/active-state computed values matching source exactly. The verification account was suspended and its scratchpad password files deleted at close-out.

**Independent critique (Product Owner direction, not blindly implemented):** the anchor-precision request ("prefer the smallest reliable source anchor") was sound in principle but under-specified in one real way — "reliable" has a different meaning for provenance metadata (any string is fine) than for inline text highlighting (must be a literal substring the renderer can locate). Implementing the request literally for both paths is what produced the live-caught defect; the fix narrows "smallest reliable anchor" to mean whatever is actually reliable for each specific consuming mechanism, not one size fits both. Not implemented as requested; corrected before landing, and this doc records why.

**Explicitly deferred, not silently dropped:** full sub-message-range precise "temporary focus" (highlighting only the originating passage within a message, not the whole message) remains out of scope — `navigateToConversationSource()` still operates at whole-message granularity. Safely wrapping/unwrapping a DOM Range around `hotlinks()`-rendered content (risk: corrupting existing `<mark>` nesting, whitespace/entity mismatches between a stored quote and rendered `textContent`) is real, non-trivial work that deserves its own dedicated, tested tranche rather than being folded into this correction round.

**New work queued by this round, not started:** (1) compress River Action Stack "not covered"/missing-evidence notices into a compact evidence-status line inside the primary scan path, keeping full detail in the existing expansion/source-grounding surfaces; (2) internal-first document opening — selecting a project document should activate/display it inside ARCHIOSK (thumbnails, in-context tools) rather than triggering a browser/OS download-open prompt, which should only ever follow an explicit secondary action (Open externally/Download/Save a copy).

**ARCHIOSK Instrument Rail / Admin Machinery Zone — architecture note, not built:** the Product Owner identified a future need for a defined peripheral zone for Claude/agent state, an internal terminal, execution checklists, tests, diagnostics, repository state, restart safety, and other admin/developer machinery — kept out of Conversation/Eye/Toolbox/project content, so the central workspace stays project-only. The recommended shape (assessed, not implemented): a genuinely new, separate perimeter zone — analogous to VS Code's Activity Bar + side panel in spatial discipline only, not visual identity — distinct from the existing Toolbox ("Project Tools"), which is and should remain *project-scoped* user action tooling; the Instrument Rail would be cross-project/system-level machinery with no single-project home. Must be role-gated with progressive visibility (ordinary user: project instrument only; admin: + approved machinery access; developer: + deeper diagnostics) — never shown to ordinary users by default. This is a real, separate information-architecture and access-control decision that deserves its own scoped plan (Plan Mode) rather than inline implementation; explicitly not begun by this round.

**Repository state at this checkpoint:** implementation+tests commit (`94b9837`) → this documentation/checkpoint commit, on `main`, pushed to `origin/main` immediately after. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**No River/Risk/Drawing-comment tranche expansion is authorized or begun by this round.** The three newly-identified items above (missing-evidence compression, internal-first document opening, Instrument Rail planning) are queued, not started.

## 2026-08-07 — CLAUDE-POSTCAMEL-P01 (Product-Owner Acceptance Seal)

**Product owner accepts CLAUDE-POSTCAMEL-P01 at commit `a67d046` as the completed POSTCAMEL pilot-readiness programme.**

**Accepted evidence:** the repository-grounded audit and live-browser Zero-Founder walkthroughs (procurement, Design Manager, and non-RFP project-start scenarios); correction of the four bounded usability/trust defects identified during the audit (the "for this prototype" founder-language leak, the MM9 registration-panel discoverability fix, and the Work Product "Add a section"/"Edit this section" silent field-scoping data-loss fix); the full-suite result of **2,889 passed, 0 failed, 65 subtests**; the canonical pilot-readiness and Elephant-Test documentation (`governance/current/pilot-readiness-postcamel-p01.md`); and the recommendation **GO — ready for independent expert pilot**.

**Accepted as non-blocking fast-follow items, not conditions of this acceptance:**
1. MM7 formal Claim/Investigate coverage is stronger for drawing/image evidence than for PDF/spreadsheet evidence (PDF/spreadsheet evidence is served by a real but simpler grounded-Q&A path instead).
2. Spreadsheet cell editing has no direct UI trigger; governed Work Product workflows currently cover the principal pilot need.
3. Requirements do not yet have a dedicated sidebar branch.

**Deployment condition for the first pilot:** do not co-host real independent-pilot client data with unrelated projects/users on the present server configuration, because admin accounts currently have server-wide project visibility (the pre-existing, deliberate `CLAUDE-P32` single-deployment boundary — not something this programme changed). Use an isolated pilot deployment or equivalent isolation.

**No work on POSTCAMEL-P02, Surface Trust, Voice Architecture, or another future programme is authorized by this acceptance seal. CLAUDE-POSTCAMEL-P01 is closed.**

## 2026-08-07 — CLAUDE-POSTCAMEL-P01 (Independent Expert Pilot Readiness and Zero-Founder Hardening)

**First post-Camel programme**, authorized following the accepted Camel MM1–MM9 close-out (`d7df9a3`). Explicitly not a new broad capability programme — a Zero-Founder audit (repository-grounded, then three live-browser walkthroughs: procurement, Design Manager, non-RFP start) to determine pilot readiness, followed by a bounded hardening pass fixing only what the audit found to be genuinely real.

**Fixes made** (all bounded, reversible, no new dependency, no domain-model/schema change): (1) a "for this prototype" founder-language leak in `routes/workspace.py`'s `add_drawing_source` error message; (2) the MM9 registration-panel link (`templates/case_workspace.html`) repositioned from after the fully-rendered document (below the fold on anything longer than one page) to directly under the document title; (3) the Work Product "Add a section" form's silent field-group mismatch — every field for every section type rendered at once with no indication only the selected type's own fields persist, reproduced live (a reviewer's risk data was silently discarded while "Narrative" was still selected) — fixed with a progressive-enhancement JS toggle (`static/js/case_workspace.js`) that preserves the form's existing "works with JavaScript disabled" guarantee; (4) the mirror bug in "Edit this section," fixed more simply with a pure Jinja per-type conditional since an existing section's type is already fixed server-side. `STATIC_VERSION` bumped to 62.

**Tests:** one new regression test, `tests/test_mm8_work_products.py::WorkProductRouteTests::test_edit_section_form_only_renders_its_own_section_type_fields`, proving a risk section's edit form shows risk fields (with real saved values) and never team_member-only fields, and vice versa.

**Full-suite result:** one controlled run after all fixes and the new regression test landed, dev-server and prior background test processes stopped first: **2,889 passed, 0 failed, 65 subtests** in 2204.60s (36m44s) — exactly one more than MM9's own last confirmed count (2,888), matching the one new test added this stage. Zero regressions.

**Live-browser verification:** a throwaway `pilot_audit` admin account and two throwaway projects ("Riverside Pump Station Upgrade" seeded from a real hand-built minimal RFP PDF; "Mechanical Coordination Review" seeded from a real Coordination Report PDF, deliberately non-procurement, satisfying the non-RFP guard, with a real openpyxl risk-register workbook and a real PNG drawing added). Confirmed live: MM9 registration for both PDF and XLSX (now discoverable without scrolling); grounded Q&A with inline "Source grounding" citations; honest abstention ("not covered by this project's extracted evidence... treat this as a starting point, not a complete answer"); the Project Briefing's evidence-grounded, provenance-stamped "Matters Requiring Early Attention" list; a full drawing Investigation → machine Finding (confidence-scored, UNVERIFIED) → human Reviewer Validation chain; and, after the fix, a Work Product risk section saving its real field values correctly. Both throwaway projects were permanently deleted (not merely soft-removed) and the throwaway account deleted at close-out; the verification dev-server process chain was stopped.

**Real, documented gaps — found, not fixed, none blocking:** the MM7 formal Claim/"Investigate" trust engine (confidence score, contradiction detection, human review gate) remains wired only to drawing/image evidence — PDF/spreadsheet evidence gets a real, working, but simpler grounded-Q&A path instead, with no formal Finding produced; MM3's bounded spreadsheet cell-edit has no UI trigger anywhere (the actual governed Design-Manager path, the MM8 risk-register Work Product, does work and was live-verified); Requirements have no sidebar branch of their own, unlike every other first-class object. Full detail, including the Elephant-Test clear-eyes hierarchy audit and the future workspace-template extension-point note, is recorded in the new `governance/current/pilot-readiness-postcamel-p01.md` — the canonical record for this stage, not restated here.

**Recommendation: GO — ready for an independent expert pilot.** No blockers found; several fast-follow items tracked (see that document's own Section 11). No product-owner acceptance seal is recorded in this entry. No pilot was begun by this stage, and no post-P01 capability programme (Monte Carlo, Airlock, Navisworks, drone, federation, education, or a saved-workspace-template system) was started.

**Repository state at this checkpoint:** implementation/fixes commit → focused-test commit → documentation/checkpoint commit, in that order, on `main`; pushed to `origin/main` immediately after. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-07 — CLAUDE-MM9 (Product-Owner Acceptance Seal) — Camel MM1–MM9 Programme Close-Out

**Product owner accepts MM9 and the recommendation: ACCEPT — MM9 successfully completed the whole-system integration and validation stage, identified and closed a real user-facing MM2/MM3 evidence-registration gap, verified PDF and XLSX evidence registration live in the browser, completed the full suite with 2,888 passed and 0 failed, preserved repository integrity, and introduced no material scope creep.**

**Commits sealed:** `37b612d` (implementation: `static/js/document_structure_registration.js`, `templates/case_workspace.html`'s new mount point and `.xlsx`-iframe branch) → `bc094d4` (documentation: `kernel-object-model.md`'s real ground-truth entry, `STATUS.md`'s MM9-scoped `IMPLEMENTED, bounded` row and updated authorization-status paragraph, `camel-multimodal-programme.md`'s MM9 section and authorization paragraph, `MANIFEST.md`'s new-file row) → `04ae0db` (continuation checkpoint).

**Repository state:** `HEAD` and `origin/main` both confirmed at `04ae0db` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Test evidence:** one controlled full-suite run against the changed template/JS: **2,888 passed, 0 failed, 65 subtests** — identical to MM8's last confirmed count, confirming zero regression from the MM9 UI-wiring change. Deliberately no new Python test file this stage, matching MM4/MM5's own established precedent that a JS-only widget mounted onto already-tested backend routes is proven by live-browser verification, not a second layer of route tests.

**Live-browser verification:** a real throwaway account and project on a freshly `restart-app`'d dev server, starting from a clean sign-in (a stale prior-session cookie was found and explicitly logged out first). Real PDF evidence registration verified live: a hand-built minimal PDF added as a Source, "Register this document" correctly produced "Registered for citation: 1 page, 1 citable paragraph," confirmed to persist correctly across a fresh page reload. Real XLSX evidence registration verified live: a real openpyxl-written workbook added as a Source, "Register this workbook" correctly produced "Registered for citation: 1 worksheet, 3 citable rows." Both registrations reused MM2's/MM3's own existing, unmodified backend methods with no new failure surface.

**Cleanup confirmed:** the throwaway account and project were fully, permanently removed (project permanently deleted via the app's own delete flow, not merely soft-removed; account row deleted, not merely suspended); the verification dev-server process chain was stopped; all scratchpad verification scripts and fixture files were removed. No disposable MM9 artifact was left behind.

**Preserved, explicit, non-blocking residual — not resolved or narrowed at this seal:** the canonical Design-Manager/quantitative-risk/Monte-Carlo case is **not yet proven** because a governed Monte Carlo engine does not yet exist. P50/P80/P90 and the complete Progressive Design-Build risk workflow must not be represented as delivered capability — the risk-register data model (MM3/MM8) is structurally ready to feed such an engine without rework, but the engine itself remains deliberately unbuilt.

**Carried forward, cross-cutting doctrine and deferrals this stage's implementation is consistent with, not restated verbatim here, and not resolved or narrowed by this seal:** the Probing Vessel doctrine; the Trustworthy Answer Contract; the Governed Evidence Sachet; Proof Before Federation; Finding and DerivedObservation remain distinct unless later evidence justifies convergence (unchanged through MM1–MM9, no merge made); future Navisworks/model-coordination integration; a future drone/micro-drone field-reality stream; a future External Intelligence Airlock/external information-retrieval connector; a future Learning Vessel/public-learning branch; remaining cockpit and product-polish work. None of these are narrowed, expanded, or resolved by this seal.

**MM9 is the final stage of the Camel MM1–MM9 programme. No post-MM9 programme is started by this seal.**

## 2026-08-07 — CLAUDE-MM9 (Whole-System Integration and Consolidated Validation)

**Ninth real MM1 consumer**, authorized following the accepted MM8 seal (`b7768a3`). This session recovered and continued a CLAUDE-MM9 work session interrupted mid-flight by a VS Code reload (the interrupting IDE event terminated the prior Claude/PowerShell terminal, not any part of the repository). Recovery was strictly non-destructive: `git status`/`diff`/`log` confirmed `HEAD == origin/main == b7768a3` with no lost commits; the only surviving uncommitted work was a modified `templates/case_workspace.html`, a new, complete `static/js/document_structure_registration.js`, and an already-bumped `STATIC_VERSION=61` in `.env` — internally consistent and ready to continue from, not restarted from scratch. The pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/` was left exactly as found throughout.

**MM9's own governing description** (`specified-unbuilt/camel-multimodal-programme.md`) frames it as a validation/acceptance stage, not a build stage in the same sense as MM1–MM8. Consistent with that framing and with MM8's own precedent of fixing a real defect found during live-browser verification rather than merely reporting it, this stage's own repository-grounded investigation found one concrete, real integration gap and closed it: MM2's `/pdf-structure` and MM3's `/spreadsheet-structure` registration routes were real, fully tested, and reachable by direct API call, but had zero UI trigger anywhere in the running application, so a first-time user could never turn an uploaded PDF or `.xlsx` Source into citable evidence.

**Implementation:** `static/js/document_structure_registration.js` (new) — a lazy, per-Source "Register this document"/"Register this workbook" widget mirroring MM4's own `drawing_image_viewer.js` "Register this drawing" precedent exactly (same `mount(el)` shape, not a page singleton). Checks existing registration via `GET .../structural-units`/`.../evidence`; otherwise POSTs to the existing, completely unmodified `/pdf-structure`/`/spreadsheet-structure` routes and re-renders a citable-count summary. `templates/case_workspace.html` gained one mount point after the existing PDF-canvas branch, plus a genuinely new `.xlsx`-iframe branch (previously `.xlsx` fell through to the generic catch-all iframe with no distinguishing mount point at all). No new backend route, no new domain object, no new dependency. `STATIC_VERSION` bumped to 61 in the same work session per this repository's own CLAUDE.md discipline (confirmed already done correctly before the interruption).

**Deliberately no dedicated Python test file** — matching MM4/MM5's own precedent that a JS-only widget mounted onto already-tested backend routes is proven by live-browser verification, not a second layer of route tests duplicating MM2's/MM3's own suites. One controlled full-suite run against the changed template/JS: **2,888 passed, 0 failed, 65 subtests** — identical to MM8's last confirmed count, confirming zero regression.

**Live-browser verification:** a real throwaway account (`mm9_verify`) and project on a freshly `restart-app`'d dev server (confirmed serving `STATIC_VERSION=61` via `curl` before testing began), starting from a clean sign-in (a stale `mm8verify` session cookie was found carrying over from a prior session's testing and was explicitly logged out first, per this repository's own "always test from sign-in" discipline). A real, hand-built minimal PDF (same construction MM2's own test suite uses for its one real-file proof) and a real openpyxl-written `.xlsx` workbook were added as genuine Sources. The PDF's "Register this document" button produced "Registered for citation: 1 page, 1 citable paragraph," confirmed to persist correctly across a fresh page reload. The workbook's "Register this workbook" button produced "Registered for citation: 1 worksheet, 3 citable rows." The throwaway account and project were fully, permanently removed afterward (project permanently deleted via the app's own delete flow, not merely soft-removed; account suspended) — not merely soft-removed, matching MM7/MM8's own cleanup precedent.

**Deliberately NOT attempted this stage, remaining NOT AUTHORIZED:** the full canonical Design-Manager/Monte-Carlo end-to-end acceptance case the Camel programme's own cross-cutting requirement describes — structurally impossible to complete honestly while the Monte Carlo engine itself remains unbuilt (MM7's own STATUS row, unchanged by this stage); a broad, automated `RealBrowserBehaviorTests`-style harness exercising the whole MM1–MM8 surface in one pass; an in-app citable-paragraph/row browser (individual citations remain reachable only through the diagnostic evidence API, exactly as MM2/MM3 already documented); and any other later-programme engine.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM9-scoped `IMPLEMENTED, bounded` row and its own top authorization-status paragraph was updated; `camel-multimodal-programme.md`'s authorization-status paragraph and MM9 section both gained this stage's commit-and-date parenthetical; `MANIFEST.md` gained the new file's own row. No new `data-ui-ref` values were introduced (the new mount point is a JS-populated container, not a template-level interactive control), so `UI_REFERENCE_MAP.md` needed no change — confirmed by inspection of the existing registry-consistency guard's own scan pattern before assuming so.

**Recommendation:** ACCEPT — MM9 closes a real, user-facing gap in already-shipped, already-governed MM2/MM3 capability, live-verified end to end, with zero regression and zero new scope beyond what its own investigation found. The Camel programme's full canonical Design-Manager/Monte-Carlo acceptance case remains genuinely, honestly unproven — not something this stage could responsibly claim without a Monte Carlo engine that does not exist. No product-owner acceptance seal is recorded in this entry, per this stage's own governing instruction. No post-MM9 programme is begun by this entry.

**Recovery note:** this checkpoint's "one controlled full-suite run" and "live-browser verification" sections above describe work actually performed in THIS recovery/continuation session, not re-derived from the interrupted session's own (unrecorded) intentions.

**Repository state at this checkpoint:** implementation commit → documentation commit → this checkpoint commit, in that order, on `main`; pushed to `origin/main` immediately after. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-07 — CLAUDE-MM8 (Product-Owner Acceptance Seal)

**Product owner accepts MM8 and the recommendation: ACCEPT — MM8 delivers the governed work-product layer, allowing ARCHIOSK to move from evidence and investigation into editable, reviewable, versioned, issued professional work products while preserving provenance, human authority, revision history, and source traceability.**

**Commits sealed:** `70d5979` (implementation: `WorkProduct`/`WorkProductSection`/`WorkProductExportRecord`/`WorkProductReview` and their full lifecycle, provenance, immutability, and revision methods in `services/case_workspace.py`; new `services/work_product_export.py`; 12 new form-POST/redirect routes in `routes/workspace.py`; the "Work Products" sidebar branch and `?work_product=<id>` detail/edit pane in `templates/base.html`/`templates/case_workspace.html`; `tests/test_mm8_work_products.py`) → `b1e6b28` (documentation: `kernel-object-model.md`'s real ground-truth entry, `STATUS.md`'s MM8-scoped `IMPLEMENTED, bounded` row, `camel-multimodal-programme.md`'s MM8 section marked implemented, `UI_REFERENCE_MAP.md`'s four new rows) → `3228773` (continuation checkpoint).

**Test evidence:** 38 focused tests in `tests/test_mm8_work_products.py` (34 store-level + 4 functional route tests). One controlled full-suite run after all fixes were in place: **2,888 passed, 0 failed, 65 subtests passed** — a real regression against a pre-existing UI-reference-map registry-consistency guard (four new `data-ui-ref` values left undocumented) was caught and fixed by documenting them in `UI_REFERENCE_MAP.md`, not by weakening the guard, in the same work session, not a separate defect.

**Live-browser verification:** a real throwaway account and two projects, seeded with genuine three-modality evidence (drawing region, spreadsheet row, PDF paragraph), run against the live dev server with a clean `restart-app` cycle before and after, then fully removed afterward.

**Work-product creation/edit/save/review/issue behavior:** a "report" WorkProduct was created live from an accepted Finding, populated with a human-authored section citing three evidence objects and an AI-proposed section, edited (confirmed AI provenance transitioned to `edited_ai_proposal`, never silently to `human_authored`), reviewed, approved, and issued through the real UI and the existing Approval Gate's two-step `confirm=once` flow — confirmed live, not by test alone.

**Unsaved-state and save-confirmation behavior:** satisfied by architecture, not new client-side state — MM8's UI is classic form-POST/redirect throughout (matching RFI's own established precedent, not MM6/MM7's fetch()-based JSON convention), so no local draft state exists to desync and no false "saved" indication is possible.

**Issued-version immutability and later revision behavior:** `issue_work_product` computes a permanent SHA-256 `issued_checksum`; every subsequent mutation attempt on an issued work product is structurally refused (falsification-tested, including a checksum-unchanged proof after a refused edit). `revise_work_product` — Supersession's fourth real consumer — was exercised live: the issued report was revised after issue, and the original issued revision was confirmed byte-for-byte unchanged afterward, with the new revision starting as an independent draft.

**Evidence backlinks and citation preservation:** every section's `evidence_links` were validated live against real, already-governed objects in the same project; citations remained intact and navigable from the work-product content back to the underlying evidence across edit, review, issue, and revision.

**Human-authored versus AI-assisted provenance:** all seven closed content classes (`human_authored`/`ai_proposed`/`imported`/`deterministic_calculation`/`direct_evidence_reference`/`edited_ai_proposal`/`template_content`) were exercised; accepting an AI-proposed section was confirmed to record `accepted_by`/`accepted_at` without rewriting `content_class` — acceptance and authorship remain separately visible facts, live-verified in the running UI.

**Structured spreadsheet work-product behavior:** a "risk_register" WorkProduct (the Design-Manager scenario) was created live with a risk section (description/probability/impact/mitigation/owner) citing spreadsheet evidence, reviewed, approved, issued, and exported — structurally ready to feed a later Monte Carlo engine without rework, though that engine itself remains deliberately not built this stage.

**Export/reopen verification:** real DOCX and XLSX downloads were generated and inspected for both the report and risk-register work products; formula-injection sanitization was confirmed live and by falsification test; each export's own checksum (of the actual bytes produced) was confirmed distinct from the permanent `issued_checksum`.

**Project isolation and authority enforcement:** a live, authenticated cross-project evidence-citation attempt (verified with a real CSRF token, not merely an unauthenticated 400) was confirmed refused and caught by the route's own `except CaseWorkspaceError` handler, matching the paired falsification test proving the same denial at the store layer.

**Repository state:** `HEAD` and `origin/main` both confirmed at `3228773` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Preserved, explicit, non-blocking residuals and deferrals — none resolved or narrowed at this seal:**
- Finding and DerivedObservation remain distinct; preserve both, no merge.
- RFI (`RFIDraft`) remains on its existing, backward-compatible path and has not been migrated into the generalized `WorkProduct` architecture.
- Full Microsoft Word/Excel/CAD/Bluebeam parity remains deferred.
- Live collaborative co-authoring, electronic/legally-binding digital signatures, a generalized workflow designer, a full Monte Carlo engine, a schedule engine, Navisworks integration, drone mission operations, external AI/internet connectors, trusted-agency federation, the Learning Vessel/education product, and a broad cockpit redesign all remain deferred.

**Carried forward, cross-cutting doctrine this stage's implementation is consistent with, not restated verbatim here:** the Probing Vessel doctrine (the exported artifact as cargo manifest, not the ocean itself); the Trustworthy Answer Contract (claim classifications and provenance survive promotion into a work product, never silently becoming ordinary prose); the Governed Evidence Sachet (citation, context, and disclosure discipline preserved into exports); Proof Before Federation; and human authority over every consequential promotion from draft to reviewed, approved, issued, or revised — no work product this stage produces, deterministic-cited or AI-authored, can become an issued, authoritative artifact without an explicit human review/approve/issue chain.

**MM9 is not started by this seal.** This entry records acceptance only.

## 2026-08-07 — CLAUDE-MM8 (Governed Creation, Editing, Review, and Accountable Work Products)

**Eighth real MM1 consumer**, authorized following the accepted MM7 seal (`0147cac`). Repository-grounded investigation found RFI (`RFIDraft`, `services/rfi_export.py`) as the one existing precedent for bounded creation/editing/export of a real professional artifact — implemented entirely via classic form-POST/redirect in `routes/workspace.py`, never `routes/api.py`'s fetch()-based JSON convention MM6/MM7 both used. No prior generalized "work product" abstraction existed; every existing artifact type (RFI, requirement, finding) was purpose-built and non-editable-in-place beyond RFI's own narrow fields.

**No new dependency.** `services/work_product_export.py`'s DOCX/XLSX renderers reuse the already-accepted `python-docx`/`openpyxl` packages exactly as-is, the same packages `rfi_export.py` already used.

**Implementation:** new `WorkProduct`/`WorkProductSection` (`services/case_workspace.py`) — Section 5's "a work product is not evidence" enforced by construction: neither is ever an `EvidenceItem`; both are made citable via `_MM6_ENDPOINT_LISTS` (which also gains `Claim` as a citable kind for the first time here). Six stored lifecycle states (`draft`/`needs_review`/`reviewed`/`revisions_required`/`approved_for_issue`/`issued`) plus a read-time-derived `superseded`; seven closed content-provenance classes (`human_authored`/`ai_proposed`/`imported`/`deterministic_calculation`/`direct_evidence_reference`/`edited_ai_proposal`/`template_content`). `edit_work_product_section` auto-transitions `ai_proposed` to `edited_ai_proposal` on genuine edit, never silently to `human_authored` (falsification-tested); `accept_work_product_section` records `accepted_by`/`accepted_at` without touching `content_class` at all — acceptance and authorship stay deliberately separate facts. `_require_work_product_editable` is the single centralized immutability guard, called at the top of every mutating method — an issued work product refuses every mutation (falsification-tested, including a checksum-unchanged proof after a refused edit). `issue_work_product` requires the full `reviewed` → `approved_for_issue` → `issued` chain (falsification-tested for both skipped steps) and computes a permanent SHA-256 `issued_checksum` over the active sections' canonical JSON. `revise_work_product` makes `Supersession`'s fourth real consumer (after Source/Relationship/Claim): a genuinely new `WorkProduct` with deep-copied, fresh-id sections and `version = original.version + 1`, the original never mutated — live-verified byte-for-byte unchanged after editing the revision. `stale_evidence_for_work_product` warns without rewriting issued content, reusing MM7's own endpoint-status helper unchanged. Four new relationship types (`based_on`/`summarizes`/`responds_to`/`resolves`); every other Section 31 candidate mapped onto an existing type, and `supersedes`/`revises` routed through the existing Supersession primitive, never as an ordinary relationship edge.

`services/work_product_export.py` (new file): real DOCX (narrative rendering) and XLSX (tabular, union-of-keys columns plus a `content_class` "Source" column and a Metadata sheet) renderers. Every exported cell passes through `_sanitize_cell_value` — any string starting with `=`/`+`/`-`/`@` gets a leading `'` prefix before being written (falsification-tested). Export checksum is computed from the actual bytes produced by `export_work_product`, distinct from `issued_checksum` (which answers a different, permanent-content-integrity question).

`routes/workspace.py`: 12 new routes, deliberately matching RFI's own established form-POST/redirect architecture, not MM6/MM7's JSON convention — this satisfies Section 15's unsaved-state contract by architecture, since no client-side draft state exists to desync. `issue_work_product` reuses the existing Approval Gate (`_require_approval`, `confirm=once` vocabulary) unchanged, mirroring `issue_rfi_draft`'s own precedent exactly. `export_work_product_route` reuses the existing `_require_export_allowed` security-policy gate unchanged. `_work_product_case_id` mirrors `_rfi_draft_case_id` for `_require_visible_case` enforcement. UI: a new "Work Products" Lists sidebar branch (`templates/base.html`) and a `?work_product=<id>` detail/edit pane (`templates/case_workspace.html`) reusing existing CSS classes only — no `static/css/main.css`/`static/js/*.js` changes this stage, so no `STATIC_VERSION` bump was required.

**Real defect found and fixed during live-browser verification, not by any test:** work-product redirects originally also carried `case=<id>` alongside `work_product=<id>`, and since `case_workspace.html`'s top-level chain checks `{% if active_case %}` before `{% elif selected_work_product %}`, any Case-scoped work product could never reach its own detail view — the Case's own Investigation view silently rendered instead. Diagnosed by reasoning through the template's own if/elif precedence order (confirmed via `grep -n "^{% if \|^{% elif "`); fixed by a targeted script that stripped `, case=case_id` only from the twelve lines containing both `work_product=` and `, case=case_id` substrings, leaving the ~76 other legitimate `case=case_id` occurrences elsewhere in the 4000+-line file untouched. Re-verified live immediately afterward: the same work product id, now without `case=`, correctly rendered its own "REPORT · V2 · DRAFT" detail view with editable sections.

**Tests:** 38 in `tests/test_mm8_work_products.py` (34 store-level — identity/persistence, blank-title falsification, draft/issued state resolution, evidence insertion/citation preservation with unsupported/cross-project falsification, the `ai_proposed`→`edited_ai_proposal` provenance-transition proof, accept-does-not-rewrite-content-class proof, invalid-content-class falsification, soft-delete, reorder, issued-immutability falsification on both add and edit, failed-edit-leaves-checksum-unchanged proof, issue-without-approval/approve-without-review falsification, the `revisions_required` review path, invalid-review-decision falsification, revise-preserves-original with independently-copied sections, revise-non-issued/unknown falsification, stale-evidence-detected-without-rewriting-checksum, concurrent-mutation protection, export-checksum-matches-actual-bytes, real DOCX/XLSX content verification, empty-export falsification, formula-injection sanitization, `record_work_product_export` event proof, sensitivity-classification preservation, and a real backward-compatibility test exercising the full, unmodified `create_rfi_draft`/`issue_rfi_draft` chain — plus 4 functional route tests against the real Flask app, including the full create → section → review → approve → issue Approval-Gate two-step `confirm=once` flow, real export downloads, and unauthenticated-request rejection). One controlled full-suite run after all fixes: **2,888 passed, 0 failed** (an intermediate run, started before the redirect fix, caught one real regression against `tests/test_p40vw7a_ui_reference_map.py`'s own registry-consistency guard — the four new `data-ui-ref` values this stage's sidebar branch introduced were undocumented in `UI_REFERENCE_MAP.md`; fixed by adding the missing rows, matching the RFIs/Investigations branches' own existing documentation pattern, not by weakening the guard).

**Live-verified against the running app, not tests alone:** a real throwaway account and two projects, seeded with genuine three-modality evidence (drawing region, spreadsheet row, PDF paragraph), a real MM7 investigation accepted as a Finding, a "report" WorkProduct created from that Finding with a human-authored section citing three evidence objects, an AI-proposed section edited to `edited_ai_proposal`, and a template-content section removed; a drawing Source revised after citation to produce a genuine stale-evidence warning; reviewed, approved, and issued through the real UI/Approval Gate; revised after issue with the original issued revision confirmed unchanged; a spreadsheet-based "risk_register" WorkProduct (Design-Manager scenario) created, populated, reviewed, approved, issued, and exported; real DOCX/XLSX downloads opened and inspected; a cross-project evidence-citation attempt confirmed refused (via an authenticated fetch with a real CSRF token, correctly caught by `except CaseWorkspaceError`, section not added). Clean `restart-app` cycle before and after. Throwaway account, two projects, and all seeded files removed afterward (`mm8_cleanup_verification.py`, scratchpad-only, never committed).

**Monte Carlo:** re-evaluated per Section 13's own explicit instruction and deliberately NOT built — the risk register created this stage (fields for description/probability/impact/mitigation/owner, evidence-linked, revision-tracked) is structurally ready to feed a later quantitative engine without rework, but implementing that engine itself would materially broaden this stage's scope; deferred to MM9 or a dedicated future prompt, exactly as the governing prompt anticipated.

**Finding/DerivedObservation recommendation:** unchanged from MM7 — "preserve both with explicit relationships," reaffirmed after evaluating MM8's own new `WorkProduct`/`WorkProductSection` addition against the full evidence → observation → Finding → Work Product/Action → Decision/Issue chain; no merge is warranted, and none was made.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM8-scoped `IMPLEMENTED, bounded` row (MM9 remains its own separate, still-`NOT AUTHORIZED` authorization); `camel-multimodal-programme.md`'s own authorization-status paragraph gained MM8's commit-and-date parenthetical; `UI_REFERENCE_MAP.md` gained the four missing rows the full-suite run's own registry-consistency guard caught.

**Deliberately NOT built this stage, remaining out of scope:** full Microsoft Word/Excel parity, desktop publishing, arbitrary PDF editing, CAD authoring, a full Bluebeam replacement, live collaborative co-authoring, electronic/legally-binding digital signatures, a generalized workflow designer, a full Monte Carlo engine, a schedule engine, Navisworks integration, drone mission operations, external AI/internet connectors, trusted-agency federation, the Learning Vessel/education product, and a broad cockpit redesign. RFI (`RFIDraft`) was deliberately left unmigrated onto the new `WorkProduct` model this stage — proven unmodified by a real backward-compatibility test, remaining its own, separately proven capability, exactly per Section 21's own "use the existing RFI capability as one proof, not the entire product direction" instruction.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM9 is not started by this stage.

**Evidence:** working tree change set: `CONTINUATION_CHECKPOINT.md` (this entry), `UI_REFERENCE_MAP.md`, `governance/STATUS.md`, `governance/current/kernel-object-model.md`, `governance/specified-unbuilt/camel-multimodal-programme.md`, `routes/workspace.py`, `services/case_workspace.py`, new `services/work_product_export.py`, `templates/base.html`, `templates/case_workspace.html`, new `tests/test_mm8_work_products.py` — staged and committed in this same work session (implementation `70d5979` → documentation `b1e6b28` → this checkpoint). The pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/` was left exactly as found.


## 2026-08-06 — CLAUDE-MM7 (Product-Owner Acceptance Seal)

**Product owner accepts MM7 and the recommendation: ACCEPT — MM7 delivers a real, tested, live-verified governed-investigation capability with structural anti-hallucination citation guarantees, honest abstention, first-class contradiction handling, and human authority preserved at every promotion point.**

**Commits sealed:** `351bc1c` (implementation: `Claim`/`record_investigation_claim`/`resolve_claim_status`/`accept_claim_as_observation`/`accept_claim_as_finding`/`dispute_claim`/`reject_claim`/`request_claim_specialist_review`/`request_claim_authority`/`supersede_claim`/`explain_investigation_answer`/`build_investigation_evidence_sachet` in `services/case_workspace.py`; new `services/cross_modal_investigation.py`; eleven new `/api/v1` routes in `routes/api.py`; the "Investigate" sub-form and inline claim list in `static/js/drawing_image_viewer.js`/`static/css/main.css`; `tests/test_mm7_governed_investigation.py` and the `tests/test_api_authentication.py` route-auth extension) → `6cfd172` (documentation: `kernel-object-model.md`'s real ground-truth entry, `STATUS.md`'s MM7-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM7 section marked implemented) → `5b7e493` (continuation checkpoint).

**Test evidence:** 31 focused tests in `tests/test_mm7_governed_investigation.py` plus 16 new tests and 8 new admin-gated routes in `tests/test_api_authentication.py`'s route-auth matrix. One controlled full-suite run: **2,850 passed, 0 failed** — a real regression against a pre-existing governance-scope guard test (`test_case_adoption.py`'s own closed `adopt_*` method list for the unrelated Selective Adopt/Carry-Forward feature) was caught and fixed by renaming the colliding methods (`adopt_claim_as_*` → `accept_claim_as_*`) rather than weakening that guard, in the same work session, not a separate defect.

**Live-browser verification:** a real throwaway project and account, seeded with genuine three-modality evidence (drawing region, spreadsheet row, PDF paragraph) linked by a contradiction relationship and a since-superseded source, run against the live dev server with a clean `restart-app` cycle before and after, then fully removed afterward.

**Claim-level citation validation:** every `evidence_link` is validated against a real, already-governed object in THIS project before a claim can be written — falsification-tested that a nonexistent id and a real id belonging to another project are both refused, so a fabricated citation is structurally impossible to persist, not merely discouraged.

**Abstention when evidence is insufficient:** proven both by test and live — an investigation run live against a brand-new marker's evidence (no relationships yet) correctly produced an honest `claim_class=unknown` claim ("I cannot establish a defensible answer from the available evidence"), carrying its own defined confidence meaning and a recommended next check, never a fabricated answer.

**Contradiction and stale-evidence behavior:** a real `contradicts` relationship in the live-seeded investigation produced its own `conflicting` claim (`contradiction_state: true`), never hidden behind co-existing support; a relationship whose endpoint Source had been superseded produced a `stale_evidence`-confidence claim (`freshness_state: stale_evidence_present`) — both confirmed via authenticated fetches against the running app, not tests alone.

**"Why should I trust this?" evidence-path behavior:** `explain_investigation_answer` (one assembly serving both the Trustworthy Answer Contract and the "Why should I trust this?" control) was confirmed live to return the full claim list with classification, confidence state and its defined meaning, citations, contradiction links, and adoption state for every claim in the seeded investigation.

**AI proposal versus human adoption states:** every claim starts `proposed` regardless of `claim_class` or author; `record_investigation_claim` structurally refuses pairing an AI author with a `directly_verified`/`deterministic_calculation` classification (falsification-tested). Live-verified: clicking "Accept as observation" in the running UI updated the claim's status badge from `proposed` to `accepted_as_observation` in place, proving the human-adoption gate is real, not decorative.

**Correction-history and downstream-review behavior:** `supersede_claim` was exercised live on a claim already accepted as an observation — the original claim was preserved unmutated, a new corrected claim was created and linked via `Supersession` (its third real consumer), and the original's resolved status correctly showed `superseded`; `downstream_requires_review` correctly named the finding/observation the original claim had already produced, confirmed via authenticated fetch against the running app.

**Project-isolation and cross-project denial evidence:** a live, authenticated POST attempting to start an investigation anchored on another project's own evidence was confirmed refused (400 `invalid_investigation`) against the running app, matching the paired falsification test proving the same denial at the store layer.

**Repository state:** `HEAD` and `origin/main` both confirmed at `5b7e493` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Preserved, explicit, non-blocking scope boundaries — none resolved or narrowed at this seal:**
- No unrestricted external search.
- No generalized autonomous agents.
- No automatic legal, contractual, code-compliance, design-approval, risk-acceptance, grading, or disciplinary conclusions — every consequential promotion from evidence to observation, Finding, decision, or action remains an explicit human act.
- No Navisworks or drone-mission analytics integration.
- No Monte Carlo engine.
- No Layer-3 trusted-agency federation.
- `propose_ai_assisted_claim` exists and is tested for its own honest no-key degrade, but remains not wired into any live route or UI this stage.

**Carried forward, cross-cutting doctrine this stage's implementation is consistent with, not restated verbatim here:** the Probing Vessel doctrine (AI as navigator/scout, human as captain); the Trustworthy Answer Contract (implemented this stage as `explain_investigation_answer`, distinguishing directly-verified/deterministic/interpretive/AI-proposal/conflicting/unknown/decision-requiring-authority claims and surfacing contradiction and staleness honestly); the Governed Evidence Sachet (extended this stage to a whole investigation via `build_investigation_evidence_sachet`, same allow-listed/excluded-summary discipline MM4/MM6 already established); Proof Before Federation; and human authority over every consequential promotion from evidence to observation, Finding, decision, or action — no claim this stage produces, deterministic or AI-authored, can become governed truth without an explicit human `accept_claim_as_observation`/`accept_claim_as_finding` action.

**MM8 is not started by this seal.** This entry records acceptance only.

## 2026-08-06 — CLAUDE-MM7 (Governed Investigation, Analytical Reasoning, and Trustworthy Answers)

**Seventh real MM1 consumer**, authorized following the accepted MM6 seal (`503f9e9`). Repository-grounded investigation found most of the substrate already in place, scoped narrowly to Requirements: `InvestigationStep` (Prompt 8/CLAUDE-P04) already carried question/evidence_requested/evidence_examined_ids/ran/skipped_reason/analysis_id, fed by `services/requirement_investigation.py`'s own real, policy-gated Anthropic call; `services/project_qa.py` (CLAUDE-P38) already answered project questions via a real model call grounded in Requirement/milestone text, with `grounded_in` as unvalidated free-text strings. Neither reached into the MM1-MM6 evidence/relationship graph or decomposed an answer into individually-classified, individually-citable claims.

**No new dependency.** The one optional real-AI extension point (`propose_ai_assisted_claim`) reuses the already-accepted `anthropic` package via the same lazy-import/graceful-degrade pattern `project_qa.py`/`requirement_investigation.py` already established.

**Implementation:** new `Claim` (`services/case_workspace.py`) — never stores evidence content, only validated `evidence_links` resolved through the SAME `_MM6_ENDPOINT_LISTS` MM6 already validates relationship endpoints against, so a hallucinated citation is structurally impossible to persist. Four vocabularies (`KNOWN_CLAIM_CLASSES` closed/seven distinctions, `KNOWN_CONFIDENCE_STATES` closed/seven categorical states each with a defined testable meaning in `CONFIDENCE_STATE_MEANINGS`, `KNOWN_ANALYTICAL_METHODS` open-world, `KNOWN_CLAIM_ADOPTION_STATES` nine states with `superseded` derived at read time). `record_investigation_claim` structurally refuses an AI-authored claim classified `directly_verified`/`deterministic_calculation`. `resolve_claim_status`/`explain_investigation_answer` (one assembly serving both the Trustworthy Answer Contract and "Why should I trust this?")/`build_investigation_evidence_sachet` all derive at read time. `accept_claim_as_observation`/`accept_claim_as_finding` reuse `record_derived_observation`/`record_analysis` unchanged. `supersede_claim` makes `Supersession`'s third real consumer, flagging downstream review. New `services/cross_modal_investigation.py`: a deterministic engine (`investigate_cross_modal_question`) classifying every real Relationship touching an anchor object into a claim (contradiction/stale/support/abstention), reproducible by construction; an optional, NOT route-wired `propose_ai_assisted_claim`; a real, tested prompt-injection heuristic (`contains_likely_prompt_injection`). Eleven new `/api/v1` routes. UI: a small "Investigate" sub-form and inline claim list extending MM6's own river panel (`static/js/drawing_image_viewer.js`) — no `window.prompt()` anywhere.

**Self-caught defect, fixed before commit:** MM6's own `OBJECT_KIND_TASK` had been defined but never added to `KNOWN_OBJECT_KINDS` (harmless — the open-world normalizer's fallback happened to produce the same value — but `is_known_open_world_value` would have incorrectly reported it unrecognized). Fixed alongside adding `OBJECT_KIND_CLAIM` to the same tuple.

**Real naming collision, fixed before commit:** `adopt_claim_as_observation`/`adopt_claim_as_finding` collided with `test_case_adoption.py`'s own closed-set governance guard test for the UNRELATED Selective Adopt/Carry-Forward feature (archived-Case → derived-Case object carry-forward). Rather than weakening that governance-sensitive test, both methods were renamed to `accept_claim_as_observation`/`accept_claim_as_finding` (which also matches the route function names already chosen independently).

**Tests:** 31 in `tests/test_mm7_governed_investigation.py` (claim identity/classification/citation-validity falsification including cross-project denial and the AI-authored-deterministic-claim guardrail, broken/stale/superseded/disputed/rejected status derivation, human adoption creating real DerivedObservation/Finding records, correction integrity with downstream-review flagging, the Trustworthy Answer Contract field-shape proof, evidence-sachet allow-listing, concurrent-mutation protection, backward compatibility with the pre-MM7 `requirement_investigation` step kind, the deterministic engine's own contradiction/stale/abstention/disputed-produces-no-claim/reproducibility behavior, prompt-injection heuristic and AI-boundary honest-degrade proof) plus 16 new tests + 8 new admin-gated routes in `tests/test_api_authentication.py`. Full suite: **2,850 passed, 0 failed** (one real regression against a pre-existing governance guard, caught and fixed via the rename above in the same work session, not a separate defect).

**Live-verified against the running app, not tests alone:** a real throwaway project seeded with genuine three-modality evidence (drawing region, spreadsheet row, PDF paragraph) linked by a contradiction relationship and a since-superseded source, investigated via the real deterministic engine producing conflicting/stale/abstention claims, one accepted as a Finding, one accepted then corrected via `supersede_claim` with history preserved, one disputed. Confirmed live: a brand-new marker created through dispatched `PointerEvent`s reaching the new "Investigate" form; running a real investigation through the actual UI form handler on evidence with no relationships yet, correctly producing an honest abstention claim with its defined confidence meaning and recommended next check; "Accept as observation" updating the live status badge; the pre-seeded investigation's `contradiction_state`/`freshness_state`/all four claim adoption states correct via authenticated fetches; a live cross-project investigation POST correctly refused (400 `invalid_investigation`); the evidence sachet correctly allow-listing only cited evidence. Clean `restart-app` cycle before and after. Throwaway account, two projects, and all seeded files removed afterward.

**Finding/DerivedObservation recommendation:** "preserve both with explicit relationships, formalized via a new adapter" — `Claim` is that adapter, not a merge or migration. The two concepts remain exactly as distinct as every prior MM stage left them.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM7-scoped `IMPLEMENTED` row (MM8-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM7 section marked implemented with a pointer, original stage-intent prose preserved.

**Deliberately NOT built this stage, remaining out of scope:** unrestricted external search, generalized autonomous agents, automatic legal/contractual/code-compliance/design-approval/risk-acceptance conclusions, a general semantic knowledge graph, Navisworks/drone-mission integration, a Monte Carlo engine, broad report authoring, full office-document editing, Layer-3 trusted-agency federation, a broad cockpit redesign, and every other MM8-MM9 engine. `propose_ai_assisted_claim` exists and is tested but is not wired into any live route or UI this stage.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM8 is not started by this stage.

**Evidence:** working tree change set: `governance/STATUS.md`, `governance/current/kernel-object-model.md`, `governance/specified-unbuilt/camel-multimodal-programme.md`, `routes/api.py`, `services/case_workspace.py`, new `services/cross_modal_investigation.py`, `static/css/main.css`, `static/js/drawing_image_viewer.js`, `tests/test_api_authentication.py`, new `tests/test_mm7_governed_investigation.py` — staged and committed in this same work session (implementation → documentation → this checkpoint). The pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/` was left exactly as found.


## 2026-08-06 — CLAUDE-MM6 (Product-Owner Acceptance Seal)

**Product owner accepts MM6 and the recommendation: ACCEPT — MM6 delivers a real, tested, live-verified cross-modal relationship layer built on existing ARCHIOSK primitives, with read-time status derivation, first-class disagreement handling, and a bounded user-facing relationship surface.**

**Commits sealed:** `874bd4b` (implementation: `record_evidence_relationship`/`resolve_relationship_status`/`dispute_relationship`/`reject_relationship`/`supersede_relationship`/`explain_evidence_trust`/`build_relationship_sachet` in `services/case_workspace.py`; nine new `/api/v1` routes in `routes/api.py`; the bounded "Relationships" panel in `static/js/drawing_image_viewer.js` and `static/css/main.css`; `tests/test_mm6_relationship_river.py` and the `tests/test_api_authentication.py` route-auth extension) → `6cdf734` (documentation: `kernel-object-model.md`'s real ground-truth entry, `STATUS.md`'s MM6-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM6 section marked implemented) → `5c375fc` (continuation checkpoint).

**Test evidence:** 29 focused tests in `tests/test_mm6_relationship_river.py` plus 10 new tests and 5 new admin-gated routes in `tests/test_api_authentication.py`'s route-auth matrix (`ADMIN_ONLY_ROUTE_PATHS` refactored from path-only to `(method, path)` keys — the first route where an admin-gated POST and a non-admin-gated GET share a path). One controlled full-suite run: **2,803 passed, 0 failed** — a real defect (a new CSS class shipped below the app's 11px accessibility floor) was caught by the suite itself and fixed before commit, not a separate regression.

**Live-browser verification:** a real throwaway project and account, seeded with genuine three-modality evidence (a drawing region on a real PNG, a spreadsheet row, a PDF paragraph) linked to a real Case/Finding, run against the live dev server with a clean `restart-app` cycle before and after, then fully removed afterward.

**Relationship creation and navigation across modalities:** a relationship was created live through the actual UI form handler (drawing-region evidence → Finding) and independently via the authenticated API (PDF-paragraph evidence ↔ spreadsheet-row evidence); both endpoints of each relationship resolve to their own real citation/content through the relationship sachet, letting either side be opened from the relationship itself.

**Directional and typed relationships:** every relationship carries an explicit `from`/`to` direction (rendered as `→`/`←` relative to the object being viewed) and a typed `relationship_type` drawn from the closed-plus-open MM1 vocabulary, extended this stage by three new types (`observes`/`deviates_from`/`requires_follow_up`) after deliberately mapping every other candidate name onto an existing type.

**States as actually implemented, all derived at read time, never stored as a mutable field:** `proposed` (default, provisional) and `confirmed` (explicit human confirmation) both verified live via the UI Confirm action; `disputed` and `rejected` (human disagreement recorded in place, the relationship never deleted) verified live, with `rejected` proven live to outrank even a `stale` endpoint; `stale` (an endpoint's own citation or Source has been superseded) verified live both before and after a Confirm action, proving staleness outranks provisional/confirmed; `broken` (an endpoint no longer resolves) covered by falsification test; `superseded` and its corrected replacement (a correction creates a new relationship via `record_evidence_relationship` and links it back via `record_supersession` — the original is preserved, never mutated or deleted, full history reconstructable) verified both by test and by a live authenticated status check confirming the correct `superseded_by_relationship_id`.

**Project-isolation and cross-project denial:** every relationship endpoint is re-validated against `project_id` before anything is written; a falsification test proves a real endpoint belonging to another project is refused (paired with proof the older, unguarded `record_relationship` primitive would have silently allowed the same cross-project link), and a live authenticated POST attempting a cross-project relationship was confirmed refused (400 `invalid_relationship`) against the running app.

**Source-version and citation preservation:** the relationship sachet was confirmed live to preserve the ORIGINAL region citation's content and coordinates unchanged after its owning Source was superseded by a later revision — the old evidence is never silently rewritten, only flagged stale via the existing `superseded_by_source_id` pointer.

**Contradiction and correction-history behavior:** the Trustworthy Answer Contract (`explain_evidence_trust`) keeps supporting and contradicting relationships as separate lists, falsification-tested and live-confirmed that a contradiction is never hidden behind a co-existing support edge — first-class disagreement, never collapsed into false consensus. Correction history for a superseded relationship is fully reconstructable via `supersessions_for`, matching the same non-destructive-correction discipline the rest of this codebase already uses for Source revisions.

**Final recommendation and repository state:** ACCEPT, as stated above. `HEAD` and `origin/main` both confirmed at `5c375fc` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**Preserved, explicit, non-blocking scope boundaries — none resolved or narrowed at this seal:**
- No free-form graph visualization — the river viewer remains a small, bounded panel scoped to one object's own relationships, never a general graph canvas.
- No broad semantic search.
- No automatic knowledge-graph construction or automatic relationship acceptance — every relationship starts `provisional` unless a human explicitly confirms it.
- No Navisworks/external-model-coordination integration.
- No drone or micro-drone (Bee-Scout Colony) integration.
- `Finding` and `DerivedObservation` remain distinct — this stage's own report neither recommends nor evidences a safer formal relationship or convergence path between them, so no merge or migration is authorized by this seal.

**Carried forward, cross-cutting doctrine this stage's implementation is consistent with, not restated verbatim here:** the Probing Vessel doctrine (AI as navigator/scout, human as captain); the Trustworthy Answer Contract (implemented this stage as `explain_evidence_trust`, distinguishing directly-verified/AI-proposed/other evidence bases and surfacing contradiction honestly); the Governed Evidence Sachet (extended this stage to a relationship path via `build_relationship_sachet`, same allow-listed/excluded-summary discipline MM4 established); Proof Before Federation; and human authority over AI-proposed relationships and conclusions — every relationship this stage can create defaults to `provisional`, and confirmation, dispute, rejection, and correction are all actions this stage models as human acts, never machine-automated ones.

**MM7 is not started by this seal.** This entry records acceptance only.

## 2026-08-06 — CLAUDE-MM6 (Cross-Document and Cross-Modal Relationship River)

**Sixth real MM1 consumer**, authorized following the accepted MM5 seal (`3f69d50`). Repository-grounded investigation found the substrate this stage needed already largely in place: the general `Relationship` dataclass/`record_relationship`/`relationships_for`/`confirm_relationship` (Foundation Batch H) and the general `Supersession`/`record_supersession`/`supersessions_for` (Prompt 8, previously Source-only) — the second explicitly documented in its own docstring as intended for exactly this kind of future reuse. What did NOT exist: any endpoint-existence/cross-project validation on `record_relationship` (deliberately permissive, used by ~15 existing callers), any derived relationship-status concept, any correction mechanism for a Relationship specifically, and any "why should I trust this" aggregation.

**No new dependency.**

**Implementation:** new `CaseWorkspaceStore.record_evidence_relationship` — an ADDITIVE, validating wrapper around the unchanged `record_relationship`, restricted to seven MM1-MM5 evidence-contract object kinds (`evidence_item`/`addressable_region`/`structural_unit`/`derived_observation`/`source`/`task`/`finding`), rejecting a nonexistent or cross-project endpoint before anything is written. `Task` needed one real fix during its own falsification testing: `Task` has no `project_id` field (unlike every other MM1-era record), so the endpoint-resolution helper's project-match check now skips that specific check for `Task` — `workspace.tasks` is itself already a project-scoped flat list, so membership alone already proves project ownership. Three new relationship types (`observes`/`deviates_from`/`requires_follow_up`); every other candidate name was deliberately mapped onto an already-existing MM1 type instead. New `resolve_relationship_status` derives proposed/confirmed/disputed/rejected/stale/broken/superseded at READ TIME (never stored), with human dispute/reject outranking an earlier confirm and rejection outranking even a stale endpoint (both falsification-tested live, not just in unit tests — see below). `dispute_relationship`/`reject_relationship` set a new `validation_state` field in place, never deleting the record. `supersede_relationship` creates a new relationship via `record_evidence_relationship` and links it back via `record_supersession` — `Supersession`'s second real consumer. New `explain_evidence_trust` (the Trustworthy Answer Contract) and `build_relationship_sachet` (the Governed Evidence Sachet extended to a relationship path). Nine new `/api/v1` routes (five admin-gated: create/confirm/dispute/reject/supersede; four not: list/status/sachet/trust).

**UI: a small, bounded "Relationships" panel added to `static/js/drawing_image_viewer.js`** (shared MM4/MM5 viewer) — deliberately NOT a free-form graph canvas. Appears next to a just-created region's/marker's own citation; shows the Trustworthy Answer Contract summary, the evidence item's own relationships (direction/type/reason/live status badge/Confirm/Dispute/Reject), and a bounded create-relationship form. Status-badge colors reuse `tokens.css`'s own existing semantic tokens. One CSS defect caught by the full suite and fixed before commit: `.relationship-status-badge`'s initial `font-size: 0.68rem` (10.88px) tripped `test_no_font_size_below_11px_floor`; corrected to `0.7rem`.

**Tests:** 29 in `tests/test_mm6_relationship_river.py` (endpoint-existence/cross-project-denial falsification with a paired proof that the older unguarded primitive would have allowed the same cross-project link; status derivation for all seven states; dispute/reject precedence over confirm; supersession with preserved history; contradiction-never-hidden-behind-support; the evidence→observation→Finding chain; the relationship-path Governed Evidence Sachet; a real `ConcurrentModificationError` proof; backward compatibility with every pre-MM6 `record_relationship` caller) plus 10 new tests + 5 new admin-gated routes in `tests/test_api_authentication.py` (which also had `ADMIN_ONLY_ROUTE_PATHS` refactored from path-only to `(method, path)` keys — the first route where an admin-gated POST and a non-admin-gated GET share one path, `/relationships`). Full suite: **2,803 passed, 0 failed** (one pre-existing-pattern CSS-floor failure introduced by this stage's own new class, caught and fixed in the same work session, not a separate regression).

**Live-verified against the running app, not tests alone:** a real throwaway project seeded with genuine three-modality evidence (a drawing region on a real PNG, a spreadsheet row, a PDF paragraph — all via the same store methods MM2-MM4's own registration routes call) plus a real Case/Finding via `record_analysis`, a disputed relationship, a superseded relationship (history preserved), and a source revision predating the fixture (proving stale-detection against genuinely already-stale evidence). Confirmed live: the drawing viewer's pre-existing MM2 stale-source label ("SUPERSEDED BY A LATER REVISION") rendering correctly; a brand-new marker created through real dispatched `PointerEvent`s (the automation tool's own `left_click_drag` does not reliably fire intermediate `pointermove` events against this viewport, a testing-tool limitation, not an app defect — worked around by dispatching the pointer sequence directly, matching MM4's own documented precedent for a different tooling gap) producing a real persisted `EvidenceItem` and the new "Relationships" button; the river panel opening with the correct trust-summary/empty-list/create-form; a relationship created live through the actual form handler, appearing with the correct direction/type/reason; the resulting status badge correctly showing **stale** both before and after clicking Confirm (endpoint staleness outranks provisional/confirmed, proven live); Reject subsequently flipping status to **rejected** (outranking stale, proven live); the pre-seeded disputed and superseded relationships' status endpoints returning `disputed`/`superseded` (with the correct `superseded_by_relationship_id`) via real authenticated fetches; the Trustworthy Answer Contract endpoint correctly surfacing a real contradiction; a live cross-project relationship POST correctly refused (400 `invalid_relationship`); the relationship sachet correctly preserving the ORIGINAL region citation content/coordinates after the owning Source was superseded (source-version-distinctness); a missing-file spreadsheet Source 404ing honestly rather than crashing. Clean `restart-app` cycle both before and after. Throwaway account, two projects, and all seeded files removed afterward.

**Finding/DerivedObservation usage evidence:** this is the first stage to exercise the full evidence→`DerivedObservation`/`Finding` relationship chain across genuinely distinct `Source`s in one linked scenario, via `explain_evidence_trust`'s own `derived_observation_ids`/`finding_ids` — the two concepts remain distinct, not merged, the same open question every prior MM stage has left explicitly unresolved.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM6-scoped `IMPLEMENTED` row (MM7-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM6 section marked implemented with a pointer, original stage-intent prose preserved. Two future relationship models named in this stage's own governing prompt (Navisworks/model-coordination; Drone Mission/Micro-Drone Bee-Scout Colony, with two principles the prompt asked to be preserved verbatim) are recorded as a pointer only, not reproduced — the verbatim doctrinal text was not present in this session's own compacted context at documentation time, and reproducing a paraphrase as if it were the original would have recorded a false verbatim text into governance. A future session actually authorized to design either model should pull the original wording from this stage's own conversation transcript.

**Deliberately NOT built this stage, remaining out of scope:** broad semantic search, automatic knowledge-graph construction, automatic relationship acceptance (every relationship starts `provisional` unless explicitly confirmed), a full free-form graph visualization, "reopen an existing region" (the Relationships panel is reachable only from a region/marker just created in the current session — an MM4/MM5 limitation this stage does not lift), Navisworks integration, drone-mission/Bee-Scout-Colony integration, and every other MM7-MM9 modality/analytics engine.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM7 is not started by this stage.

**Evidence:** working tree change set: `governance/STATUS.md`, `governance/current/kernel-object-model.md`, `governance/specified-unbuilt/camel-multimodal-programme.md`, `routes/api.py`, `services/case_workspace.py`, `static/css/main.css`, `static/js/drawing_image_viewer.js`, `tests/test_api_authentication.py`, new `tests/test_mm6_relationship_river.py` — staged and committed in this same work session (implementation → documentation → this checkpoint). The pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/` was left exactly as found.


## 2026-08-06 — CLAUDE-MM5 (Product-Owner Acceptance Seal)

**Product owner accepts MM5 and the recommendation: ACCEPT — MM5 delivers a real, tested, end-to-end image, screenshot, and camera-evidence vertical slice, with Eye operating as a governed visual-evidence surface, an explicit temporary-versus-saved lifecycle, reversible orientation, region and marker evidence, stable citations, EXIF-free derivative export, and a rigorous GPS-privacy boundary.**

**Commits sealed:** `8951d48` (implementation: `services/image_intelligence.py` — `register_eye_capture`/`extract_bounded_crop`/`create_marker_and_evidence`; `create_addressable_marker_region` and a backward-compatible `unit_type` parameter on `register_drawing_sheet_structure` in `services/case_workspace.py`; three new admin-gated `/api/v1` routes; `eye_pane.js`'s real Save-to-project/rotate/mirror/reset; `drawing_image_viewer.js`'s marker tool, "Export crop" action, and the live-verified `unit_type="image"` recognition fix; `tests/test_mm5_image_intelligence.py` and two corrected pre-existing EYE1-era test files) → `8c10b45` (documentation: `kernel-object-model.md`, `STATUS.md`'s MM5-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM5 section marked implemented, `UI_REFERENCE_MAP.md`) → `db27f87` (continuation checkpoint).

**Test evidence:** focused — 32 new tests (26 in `tests/test_mm5_image_intelligence.py`, 6 new tests + 3 new routes in `tests/test_api_authentication.py`'s route-auth matrix), all passing. Full suite: **2764 passed, 0 failed** (2732 baseline + 26 MM5 + 6 auth). Falsification evidence: a real GPS-bearing JPEG fixture proved its own coordinate values never appear anywhere in the returned metadata dict's own string form (the privacy boundary is enforced by never reading the values, not by redacting them after the fact); original-bytes-unchanged proven by direct checksum comparison after live rotate/mirror/region/marker/crop-export activity; `unit_type` backward compatibility with MM4 proven for every existing call site; cross-project denial proven for markers and derivative crops; stale-anchor-after-revision proven via the pre-existing `register_source_revision` mechanism.

**Reuse of MM4's infrastructure rather than duplication:** Eye's own "Save to project" action hands off to the SAME real, already-tested `drawing_image_viewer.js` MM4 built — full rotate/mirror/region-select/citation/metadata-panel functionality reused as-is, not reimplemented. `register_drawing_sheet_structure`'s new `unit_type` parameter and `create_addressable_marker_region`'s reuse of the generic `create_addressable_region` underneath mean MM5 added no parallel domain objects at all. Comparison with an MM4 drawing needed zero new code — an Eye-saved photo is a `Source(kind="drawing")` like any MM4 drawing image.

**Live-browser/application evidence:** a real screenshot-shaped PNG constructed in-browser via `<canvas>`/`toBlob()` and dropped onto Eye — confirmed "Temporary preview — not saved to the project," rotate producing the required visible status text, then "Save to project" with a description, landing on the real persisted-Source viewer. Region creation, citation rendering, and "Export crop" (a real derivative Source, checksum shown) confirmed live via the running server. A marker note and a region both confirmed persisted via direct evidence-listing API calls (`user_entered_evidence`/`direct_source_evidence`/`marker_note`, correct content). Two-Display comparison: an MM4 drawing and a second Eye-saved photo opened simultaneously — mirroring only the photo's own division left the drawing's division completely unaffected. On-disk byte-for-byte integrity confirmed for every MM5-created file (original photo, second photo, derivative crop) against their own recorded SHA-256 checksums after all of this live activity. A real defect (the sheet-lookup not recognizing `unit_type="image"`, forcing a redundant manual registration click) was found and fixed during this same pass, then re-verified live. Throwaway account and project cleaned up afterward.

**Metadata and GPS privacy handling, recorded as verified, not merely designed:** EXIF fields (camera make/model, software, capture timestamp, orientation) are extracted with reliability and exposure tags; GPS coordinates are DETECTED (`gps_present: true/false`) but their values are never read into memory at all; a derivative crop is EXIF-free by construction, with a `removed_metadata_fields` manifest naming exactly what the original had that the derivative lacks.

**Preserved, explicit, non-blocking scope boundaries — none resolved or narrowed at this seal:**
- `Finding` and `DerivedObservation` remain distinct pending further evidence — not merged or migrated this stage.
- No automatic object recognition, defect diagnosis, facial recognition, OCR over arbitrary images, panorama stitching, continuous camera streaming, or external image service.
- No full photo editor or advanced annotation suite — one bounded point-marker type only.
- MM6 is not started by this seal.

**Preserved future cross-cutting requirements — identified but not built or scheduled by this seal, and not expanding MM5's own scope:**
- The Probing Vessel and Trustworthy Answer Contract.
- The Governed Evidence Sachet (already implemented at the MM4 layer and reused unchanged by MM5's own regions/markers; its own further evolution beyond the current allow-listed-packet shape remains future work).
- A future Drone Mission / Micro-Drone Bee-Scout Colony / site-reality-to-IFC evidence stream.
- A future Learning Vessel branch, to remain strictly separated from the current construction product.

**Also carried forward unchanged:** OCR, PDF-to-image rendering, automatic overlay registration, synchronized comparison controls, native CAD/BIM parsing, and every other later-modality engine already deferred by MM1-MM4.

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `db27f87` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**MM6 is not started by this seal.** This entry records acceptance only.

## 2026-08-06 — CLAUDE-MM5 (Image, Screenshot, and Camera Evidence)

**Fifth real MM1 consumer**, authorized following the accepted MM4 seal (`09472ed`). Repository-grounded investigation first found Eye (`templates/base.html`, `static/js/eye_pane.js`) already had a genuinely real paste/drop/preview/zoom/fit surface from CLAUDE-P40-EYE1, explicitly documented as "not saved anywhere... editing, annotation, and evidence capture are not part of this stage" - this stage's own governing prompt is exactly the authorized "next stage" that note anticipated. `static/js/drawing_image_viewer.js` (MM4) already had full rotate/mirror/region-select/citation logic for a PERSISTED Source - the smallest real MM5 slice was making Eye's own SAVE action a bridge into that already-built machinery, not reimplementing it.

**No new dependency** - `Pillow` (pre-MM1) already covers PNG/JPEG/WebP decode and EXIF extraction (`Image.getexif()`/`get_ifd()`).

**Implementation:** `register_drawing_sheet_structure` (MM4) gained one backward-compatible `unit_type` parameter (default `"sheet"`); MM5 is the first caller passing `unit_type="image"`, reusing MM4's own `AddressableRegion`/`EvidenceItem`/citation/evidence-sachet machinery rather than a parallel path - falsification-tested that every existing MM4 call site is unaffected. New `create_addressable_marker_region` (`region_type="marker"`, Section 13's one bounded annotation type - a point, not a rectangle) shares MM4's own `region_index` sequence with rectangular regions (a marker and a region on the same sheet get "marker 1"/"region 2", never both "1"). New `services/image_intelligence.py` - deliberately separate from `services/drawing_intelligence.py` (a different metadata vocabulary, EXIF camera facts vs. drawing title-blocks, a small accepted amount of duplicated Pillow-open/decompression-bomb-guard boilerplate rather than touching MM4's already-shipped code): `register_eye_capture` (content-sniffed format detection when the extension is missing/unrecognized, Section 17's own "not extension alone"), `extract_bounded_crop` (a real derivative PNG, EXIF-free by construction, registered as its own Source with `origin_type=derivative_crop`/`origin_reference=<region_id>`), `create_marker_and_evidence`.

**Privacy boundary, the one genuinely new policy decision this stage makes:** GPS coordinates are DETECTED (`gps_present: true/false`) but their actual values are never read into memory at all - not redacted after extraction, never extracted in the first place. Falsification-tested: a real GPS-bearing JPEG fixture's own coordinate values never appear anywhere in the returned metadata dict's own string form.

**Eye is now the real governed visual-evidence surface Section 7 describes.** `eye_pane.js` gained view-only rotate/mirror/reset on the unsaved preview (CSS transform, nothing persisted), an explicit always-visible temporary-vs-saved status, and a real "Save to project" action (multipart upload to the new `eye-capture` route, the real original `File` object, never the transformed view). On save, Eye hands off to `drawing_image_viewer.js` (MM4) - now also loaded from `base.html` directly (previously only `case_workspace.html`) - rather than reimplementing rotate/mirror/region-select/citation a second time. Two new tools added to that shared viewer: a marker tool (click-to-place) and an "Export crop" action.

**Real defect found and fixed during live-browser verification:** `drawing_image_viewer.js`'s own sheet-lookup (`ensureSheetUnit`) filtered for `unit_type === 'sheet'` only - an Eye-saved photo's own `unit_type="image"` StructuralUnit (already created automatically at save time) went unrecognized, forcing a redundant manual "Register this drawing" click (which then created a genuinely duplicate `sheet`-type unit for the same Source) before region/marker tools would work. Fixed to accept either `unit_type`; re-verified live with a second Eye capture reaching "Drag a rectangle..." immediately after save, no redundant click, no duplicate unit.

**Tests:** 32 total (26 in `tests/test_mm5_image_intelligence.py` - real-Pillow/EXIF orchestration, content-based extension sniffing, GPS-presence-without-value falsification, original-bytes-unchanged proof, marker/region citation distinctness, stale-anchor-after-revision, derivative-crop EXIF-free-by-construction plus removed-fields manifest, `unit_type` backward compatibility with MM4, functional API-route tests for the full eye-capture → marker → region → derivative-crop chain; 6 new tests + 3 new routes in `tests/test_api_authentication.py`). Full suite: **2764 passed, 0 failed** (2732 baseline + 26 MM5 + 6 auth). Three pre-existing EYE1-era tests required real fixes, each a stale assertion against a deliberate, in-scope MM5 change rather than a regression to revert: the "no persist/annotate/ingest" scope-boundary guard (`tests/test_p40eye1_correction_resize_canvas.py`) narrowed to what MM5 itself still defers (chat/terminal attachment, external AI); the "never sent anywhere" guard (both `test_p40eye1_correction_resize_canvas.py` and `test_p40eye1_toolbox_eye_column.py`) narrowed to "not sent until the reviewer explicitly saves" (`fetch()` now legitimately exists, scoped to `saveToProject` only); the Reset button's own exact-string match updated for its new combined fit+orientation-reset handler.

**Live-verified against the running app, not tests alone:** a real throwaway project seeded with one MM4 drawing image; a real screenshot-shaped PNG constructed in-browser via `<canvas>`/`toBlob()` and dropped onto Eye - confirmed "Temporary preview — not saved to the project," rotate producing the required visible status text, then "Save to project" with a description, landing on the SAME real `drawing_image_viewer.js` MM4 built. Region creation, citation rendering ("site-photo.png · Sheet 1 · region 1"), and "Export crop" (derivative Source created, checksum shown) all confirmed live via the running server, not mocked. A second region created WHILE the sheet was in its default orientation and a marker note both confirmed persisted via a direct evidence-listing API call (`user_entered_evidence`/`direct_source_evidence`/`marker_note` all present with correct content). Two-Display comparison: the MM4 drawing and a second Eye-saved photo opened simultaneously, mirroring only the photo's own division and leaving the drawing's division completely unaffected. On-disk byte-for-byte integrity confirmed for every MM5-created file (original photo, second photo, derivative crop) against their own recorded SHA-256 checksums after all of this live activity. Throwaway account and project cleaned up afterward.

**Finding/DerivedObservation usage evidence:** a marker's own `EvidenceItem` (the reviewer's own observation text) and a `DerivedObservation` built from it continue to show the same MM1-MM4 pattern - not merged, not migrated; the convergence question remains open.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM5-scoped `IMPLEMENTED` row (MM6-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM5 section marked implemented with a pointer; `UI_REFERENCE_MAP.md` gained rows for four new Eye controls and updated three existing ones.

**Deferred, per this stage's own explicit scope:** a full photo editor, filters/artistic effects, automatic object/defect/facial recognition, OCR over arbitrary images, panorama stitching, a direct mobile application, continuous camera streaming, a full annotation suite beyond the one point-marker type, full overlay registration, external AI/image services. EXIF `orientation` is captured/reported as metadata but not auto-applied to rotate the displayed image - a documented, deliberate limitation (browsers disagree on native EXIF-orientation handling).

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM6 is not started by this stage.

**Evidence:** `HEAD`/`origin/main` both confirmed in sync after push (see final report for the exact hash). Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-06 — CLAUDE-MM4 (Product-Owner Acceptance Seal)

**Product owner accepts MM4 and the recommendation: ACCEPT — MM4 delivers a real, tested, end-to-end drawing-intelligence vertical slice through the MM1 evidence contract, including reversible orientation transforms, stable drawing citations, independent-Display comparison, and the first implemented Governed Evidence Sachet workflow.**

**Commits sealed:** `8e5df26` (implementation: `register_drawing_sheet_structure`/`create_addressable_drawing_region`/`build_evidence_sachet` in `services/case_workspace.py`; new `services/drawing_intelligence.py` — `transform_point_to_display`/`transform_point_to_original`, `register_drawing_evidence_for_source`, `create_drawing_region_and_evidence`; three new `/api/v1` routes in `routes/api.py`; mirror-H/mirror-V/reset and a persisted "region" tool added to `static/js/pdf_viewer.js`; new `static/js/drawing_image_viewer.js`; `static/js/case_workspace.js`'s `populateDivision` extended; `templates/base.html`/`templates/case_workspace.html`/`static/css/main.css` updated; `UI_REFERENCE_MAP.md` extended; `tests/test_mm4_drawing_intelligence.py` and three pre-existing tests corrected to their real invariants) → `74347e0` (documentation: `kernel-object-model.md`, `STATUS.md`'s MM4-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM4 section marked implemented) → `8bb805a` (continuation checkpoint).

**Test evidence:** full suite — **2,732 passed, 0 failed**, 6 pre-existing unrelated rate-limiter warnings, 35 subtests passed. 42 new tests in `tests/test_mm4_drawing_intelligence.py` (coordinate-transform math with a full round-trip proof for every rotation × mirror combination and a composition-order falsification, sheet/region CRUD, cross-project denial, stale-anchor-after-revision, evidence-sachet assembly/exclusion, real-pypdf/real-Pillow orchestration, functional API tests) plus 6 new tests + 3 new routes in `tests/test_api_authentication.py`. Three pre-existing tests were corrected to their real, still-true invariants rather than reverted: a `UI_REFERENCE_MAP.md` registry gap for six new controls, two `populateDivision` char-window assertions widened for a legitimate longer explanatory comment, and one assertion narrowed to its real invariant (the Document's own file route is never a `fetch()` target) now that `pdf_viewer.js` legitimately calls `fetch()` for the new region/structure routes.

**Live-browser/application evidence:** a real throwaway project with two deliberately mirrored hand-built PNG drawings (architectural vs. structural plan — reversed grid letters, stair on opposite sides, the cross-discipline scenario Section 9 describes) seeded directly into the live store. Confirmed live: sheet registration; rotate, horizontal mirror, and vertical mirror each producing the required visible status text ("...— source unchanged"); reset; two regions created on the same sheet — one untransformed, one while horizontally mirrored — both independently verified via the citations API to resolve to mathematically correct ORIGINAL-frame coordinates (the mirrored region's stored `x` exactly matched the expected `1 − displayed_x` inversion); the on-disk original PNG confirmed byte-for-byte identical to a freshly-regenerated copy after all of this activity; genuine two-Display independent comparison (mirroring one division's drawing changed only that division, the other remained completely unaffected) via the app's own exposed `window.ArchioskDisplay.populateDivision` API. Throwaway account and project cleaned up afterward.

**Preserved, explicit, non-blocking scope boundaries — none resolved or narrowed at this seal:**
- No CAD/BIM parsing (DWG/DXF/RVT/IFC) — a drawing-oriented PDF or raster image only.
- No automated symbol recognition — every region is reviewer-drawn, on demand; nothing is auto-detected.
- No automatic overlay, registration, clash detection, or authoritative measurement — a visible "measurements are not reliable" warning ships in the drawing-image viewer itself.
- No source modification by rotate or mirror operations — proven, not merely claimed (byte-for-byte hash match against a freshly-regenerated original after live rotate/mirror/region-creation activity).
- Orientation transforms remain reversible view state with original-coordinate mapping — every `AddressableRegion` is always stored in the sheet's original, untransformed frame; `transform_point_to_display`/`transform_point_to_original` round-trip exactly for every rotation × mirror combination.
- Broader image, screenshot, camera, and annotation workflows remain for MM5 — this stage's own image-viewer work covers only what a drawing-intelligence proof needs (zoom/pan/rotate/mirror/region-select), not general image editing or camera intake.
- `Finding` and `DerivedObservation` remain distinct pending further evidence — not merged or migrated this stage.

**Also carried forward unchanged:** a drawing-oriented PDF's own comparison-Display behavior (still the pre-existing plain `<iframe>`, no Archiosk controls — the independent-orientation proof itself uses two image drawings, which is real and fully independent); visually redisplaying a previously-created region as a highlighted overlay on reopen (citation/coordinates are proven correct via the API; no "show existing regions" UI affordance yet); OCR remains unavailable (a standalone image's title-block metadata is always honestly "unavailable"); the one honest browser-automation-tooling observation (a native `<select>`'s `change` event was not reliably triggerable via this session's tooling, worked around via the app's own exposed API — a testing-tool limitation, not a disproven claim about real-user behavior).

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `8bb805a` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**MM5 is not started by this seal.** This entry records acceptance only.

## 2026-08-06 — CLAUDE-MM4 (Drawing Intelligence and Orientation-Normalized Comparison)

**Fourth real MM1 consumer**, authorized following the accepted MM3 seal (`792c417`). Repository-grounded investigation first found substantial reusable infrastructure that shrank the real build needed: a pre-MM1 "Case Workspace prototype" already had `Source(kind='drawing')`, `Artifact.crop`, `register_source_revision`, and `services/drawing_analysis.py`'s real (if simple) per-region pixel comparison; `static/js/pdf_viewer.js` already had a full PDF.js-backed viewer with 90°-rotate and a real, coordinate-correct annotation-overlay pointer system (`convertToPdfPoint`/`convertToViewportPoint`); `services/drawing_intake.py` already had title-block LABEL: VALUE field-pattern extraction. What did NOT exist: any viewer at all for a standalone raster drawing image (a bare, uncontrolled `<img>`), any mirror/reset orientation control anywhere, and any REAL persisted region/citation mechanism for a drawing (only ephemeral, never-saved PDF annotations existed).

**No new dependency** - `pypdf` (MM2) and `Pillow` (pre-MM1) already cover every format this stage needed; Pillow's own built-in `DecompressionBombError` guard was reused for free.

**Implementation:** a drawing sheet is a `StructuralUnit` (`unit_type="sheet"`, one per PDF page or one for a standalone image) via new `register_drawing_sheet_structure` - deliberately does NOT auto-create regions (unlike MM2/MM3's own bulk paragraph/row registration) since a drawing sheet has no natural sub-structure to enumerate; regions are reviewer-driven, on demand, via new `create_addressable_drawing_region` (`region_type="rectangular"`, bounds-validated, sequential `region_index`). New `services/drawing_intelligence.py` owns the one genuinely new piece of math this stage needed: `transform_point_to_display`/`transform_point_to_original` (mirror-then-rotate composition, exact round-trip, deterministically tested for every rotation × mirror combination) - every region is always stored in the sheet's ORIGINAL frame; rotation/mirror are view-only state. `static/js/pdf_viewer.js` gained mirror-H/mirror-V/reset (composing as rotate-then-mirror - PDF.js bakes rotation into the raster first - a documented, deliberately different but equally valid composition order from the image viewer's own) plus a new persisted "region" tool reusing its existing VW7A-QA2 annotation-overlay coordinate machinery. New `static/js/drawing_image_viewer.js` gives a standalone raster drawing real zoom/pan/rotate/mirror/region-select for the first time - mounted PER-ELEMENT (not a page singleton), so it works identically in the primary document pane and inside a comparison Display division; `case_workspace.js`'s `populateDivision` now mounts it there too. Governed Evidence Sachet (`CaseWorkspaceStore.build_evidence_sachet`) implemented for the first time - a read-time-assembled, allow-listed packet for one region plus its sheet/siblings/citation, excluding every other sheet/Source; exposed read-only, not admin-gated. Three new routes: `POST .../drawing-structure`, `POST .../drawing-regions` (both admin-gated), `GET .../regions/<id>/evidence-sachet` (not admin-gated, matching the citation route's own authority level).

**Tests:** 48 total (42 in `tests/test_mm4_drawing_intelligence.py` - coordinate-transform math including a composition-order falsification and full round-trip proof for every rotation×mirror combination, sheet/region CRUD, cross-project denial, stale-anchor-after-revision, evidence-sachet assembly/exclusion, real-pypdf/real-Pillow orchestration, functional API tests; 6 new tests + 3 new routes in `tests/test_api_authentication.py`). Full suite: **2732 passed, 0 failed** (2687 baseline + 42 MM4 + 6 auth - 3 pre-existing tests whose own char-window/fetch-absence assertions needed updating for legitimate, deliberate MM4 changes, not reverted). Three PRE-EXISTING tests required real fixes, each confirmed as a stale assertion against a deliberate, in-scope change rather than a regression to revert: `test_p40vw7a_ui_reference_map.py` needed new `UI_REFERENCE_MAP.md` rows for the six new `data-ui-ref` values added to `templates/base.html`; two `populateDivision`-parsing tests (`test_p40vw8qa1_stable_surface_extension_point.py`, `test_p40vw8qa_new_investigation_action.py`) had their own arbitrary 1200-char search window widened to 2200, since MM4's own explanatory comment legitimately pushed `PANEL_KINDS[kind]` further into the function body without changing the actual code path being asserted; `test_p40vw7a_qa2_thumbnails_annotations_layout.py`'s own `test_original_document_is_never_written_to` was narrowed to its real invariant (the Document's own file route is never a `fetch()` target) now that `pdf_viewer.js` legitimately calls `fetch()` for the new region/structure API routes.

**Live-verified against the running app, not tests alone:** a real throwaway project with two hand-built PNG drawings (an "architectural" and a "structural" plan, deliberately mirrored relative to each other - grid letters A-D vs D-A, stair rectangle on opposite sides - the exact cross-discipline scenario Section 9 describes) seeded directly into the live store. Live-confirmed: sheet registration, rotate (visual + status text), horizontal AND vertical mirror (visual + status text), reset, and - the rigorous part - TWO regions created on the SAME sheet, one with no transform active and one WHILE mirrored horizontally, both independently verified via the citations API to resolve back to mathematically correct ORIGINAL-frame coordinates (the mirrored region's stored `x` exactly matched the expected `1 - displayed_x` inversion). The on-disk original PNG was confirmed byte-for-byte IDENTICAL to a freshly-regenerated copy after all of this activity (rotate/mirror/region-creation never touches the source file). Two-Display comparison: both drawings opened simultaneously via Display Layout (2 vertical divisions), each mounting its own fully independent `drawing_image_viewer.js` instance - mirroring the RIGHT division's structural plan visibly changed only that division (status banner, stair position, mirrored grid labels) while the LEFT division's architectural plan remained completely unchanged, proving genuine per-Display independence. One honest finding, not a regression: the Display-division document-picker `<select>`'s own `change` event could not be reliably triggered via this session's browser-automation tooling (a documented native-`<select>`-in-automation limitation, not something disproven for a real user); the underlying mechanism was instead verified directly and completely via the app's own exposed `window.ArchioskDisplay.populateDivision` API, which is what a real Lists-panel click ultimately calls.

**Finding/DerivedObservation usage evidence:** a drawing region's `EvidenceItem` (anchored, verbatim) and a `DerivedObservation` built from it continue to show the same MM1-MM3 pattern - not merged, not migrated; the convergence question remains open.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM4-scoped `IMPLEMENTED` row (MM5-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM4 section marked implemented with a pointer, original stage-intent prose preserved; `UI_REFERENCE_MAP.md` gained six new rows for the new PDF-viewer orientation/region controls.

**Deferred, per this stage's own explicit scope:** native DWG/DXF/RVT/IFC parsing, full BIM navigation, automatic symbol/room/dimension recognition, authoritative takeoff, full drawing-overlay registration/clash detection, sophisticated redline comparison, handwritten-markup recognition, a full annotation editor, synchronized pan/zoom/opacity comparison controls, a single unified top-menu drawing toolbar (the image viewer's own in-pane toolbar and the PDF viewer's top-bar toolbar remain two separate surfaces, explicitly not unified this stage), and OCR (so a standalone image's title-block metadata is always honestly "unavailable"). A drawing-oriented PDF's own comparison-Display behavior is unchanged (still the pre-existing plain `<iframe>`, no Archiosk controls) - the independent-orientation comparison proof itself uses two image drawings, which is real and fully independent. Visually redisplaying a PREVIOUSLY-created region as a highlighted overlay box on reopen is not built (the citation/coordinates are proven correct via the API; there is no "show existing regions" UI affordance yet).

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM5 is not started by this stage.

**Evidence:** `HEAD`/`origin/main` both confirmed in sync after push (see final report for the exact hash). Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-05 — CLAUDE-MM3 (Product-Owner Acceptance Seal)

**Product owner accepts MM3 and the recommendation: ACCEPT — ARCHIOSK can open, inspect, bounded-edit, and re-export real XLSX/CSV files through the MM1 evidence contract, with live round-trip verification and all 2,687 tests passing.**

**Commits sealed:** `35fd70a` (implementation: `SPREADSHEET_CLASSIFICATION_*` constants, `register_spreadsheet_structure`, `create_addressable_cell_region` in `services/case_workspace.py`; new `services/spreadsheet_intelligence.py` — `inspect_workbook`, `_inspect_csv`, `register_spreadsheet_evidence_for_source`, `apply_bounded_cell_edit`, `safe_csv_cell`; two new admin-gated `/api/v1` routes in `routes/api.py`; `.xlsx` added to `routes/workspace.py`'s `ALLOWED_DOCUMENT_EXTENSIONS` as add-only; `templates/base.html`'s Add-Documents `accept` attribute fixed; `tests/test_mm3_spreadsheet_intelligence.py`, `tests/test_api_authentication.py` extended) → `a9dc614` (documentation: `kernel-object-model.md`, `STATUS.md`'s MM3-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM3 section marked implemented) → `cf969b8` (continuation checkpoint).

**Test evidence:** focused — 37 new tests (33 in `tests/test_mm3_spreadsheet_intelligence.py` using real openpyxl-built workbook fixtures throughout, no mocking of the parser itself; 4 new tests + 2 new routes in `tests/test_api_authentication.py`), all passing. Full suite: **2,687 passed, 0 failed** (2,650 baseline + 33 + 4 new), 6 pre-existing unrelated rate-limiter warnings, 31 subtests passed, 1552.29s. Falsification evidence: a `.xlsx`-renamed encrypted/OLE2 file was proven refused despite its extension (content-based detection, not extension trust); a formula-cell edit attempt was proven refused with a clear error rather than silently succeeding or corrupting the cell; a stale `expected_file_hash` was proven to reject the edit rather than silently overwrite; the `cell.coordinate`-vs-`cell.column_letter` key-contract bug was caught by a genuine test failure (`KeyError: 'E'`), not by inspection alone.

**Live upload-edit-export-reopen evidence:** a real risk-register `.xlsx` workbook (formulas, a hidden sheet) uploaded through the actual "+ Add Documents" browser flow, registered via the new API into real `StructuralUnit`/`AddressableRegion`/`EvidenceItem` records, one non-formula cell edited via the new API (pre-edit backup file written, file-level hash updated), then re-downloaded through the pre-existing generic `source_file` route and reopened with openpyxl — the edit persisted, every formula and untouched cell was byte-for-byte unaffected, the hidden sheet remained hidden. A real product defect was found and fixed during this same live-browser pass: `templates/base.html`'s Add-Documents file input had a stale `accept` attribute missing `.xlsx`, silently filtering the file out of the browser's own FileList before submission even though the server-side check was already correct; root-caused via workspace-store inspection → template grep → curl route verification (CSRF token correctly extracted from the page's `<meta name="csrf-token">` tag) → fix → re-verified live. Throwaway account and project cleaned up afterward.

**Preserved scope boundaries — explicit, non-blocking, none resolved or narrowed at this seal:**
- No Excel formula-recalculation engine — formula cells remain read-only; openpyxl's cached last-known value is reported honestly (including as `None` when the workbook was never opened by real Excel), never computed.
- No Monte Carlo engine — not attempted, per this stage's own explicit scope exclusion.
- No forced, permanent risk-register schema — a risk-register row remains representable through the general worksheet/row/cell model; no risk-specific dataclass or field set was created.
- No full Excel parity — no grid/editor UI, no multi-cell/range edits, no Power Query, no pivot tables/charts, no legacy `.xls` support, no cross-workbook comparison.
- MM4 is not started by this seal.

**Preserved future cross-cutting requirements — identified but not built or scheduled by this seal:**
- A document-contextual top toolbar spanning PDF, spreadsheet, image, and drawing surfaces — currently each surface's controls remain separate; unifying them is future UI work, not started.
- The Governed Evidence Sachet / "tea-bag" principle — evidence packaging/provenance concept noted for a future stage, not implemented.
- Reversible horizontal/vertical mirroring and rotation for drawings, images, screenshots, and page renderings, with transformed-coordinate mapping back to an unchanged source — noted as future geometry-transform work; no mirroring/rotation code exists yet in any MM1–MM3 surface.

**Also carried forward unchanged from MM1/MM2:** the `Finding`-versus-`DerivedObservation` convergence question remains open; `pdf_intelligence.py`'s broad `except Exception` fallback remains a future exception-narrowing item; OCR, PDF-to-image rendering, handwriting recognition, advanced table extraction, annotation, redaction, digital-signature validation, form filling, embedded-file extraction, a new region-selection UI, and full redline/version comparison all remain deferred.

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `cf969b8` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. App server verified to start cleanly (`/login` → HTTP 200) and shut down cleanly (no residual `python.exe` processes) on this exact commit prior to sealing.

**MM4 is not started by this seal.** This entry records acceptance only.

## 2026-08-05 — CLAUDE-MM3 (Spreadsheet and Structured-Data Intelligence)

**Third real MM1 consumer**, authorized following the accepted MM2 seal (`8d577b1`). Repository-grounded investigation first found NO spreadsheet library installed at all (no openpyxl/xlrd/pandas) - the first genuine new-dependency decision in the whole Camel programme. Checked `openpyxl` against `tools/dependency_fit.py` (clean PASS on every constraint) before adding; judged directly analogous to the already-accepted `pypdf`/`python-docx` and required for MM3 to exist at all, not a "major dependency" hard-stop. Legacy `.xls` deliberately not added (would need a second, separate dependency).

**Implementation:** `.xlsx` is an add-to-existing-project Source format only (`routes/workspace.py`'s `ALLOWED_DOCUMENT_EXTENSIONS`), deliberately not a project-creation format - avoids forcing a spreadsheet through `BHiveParser`'s fragile requirement-classification pipeline. `services/case_workspace.py`'s `register_spreadsheet_structure` reuses MM1/MM2's own primitives with zero new domain objects (worksheet = `StructuralUnit`, row = `AddressableRegion` carrying real structured cell data); citation rendering needed zero new code. New `services/spreadsheet_intelligence.py`: two-pass openpyxl read distinguishing formula/cached-value/entered-value, content-based macro detection, OLE2 encrypted-file detection, decompression-bomb/row-count bounds, and `apply_bounded_cell_edit` (refuses formula cells, checks a file-level concurrency hash, backs up the pre-edit original, preserves data type on write). "Export a revised workbook" needed zero new code - the pre-existing generic Source-download route already serves the post-edit bytes.

**Real defect found and fixed during live-browser verification:** `templates/base.html`'s Add-Documents file input had a stale hardcoded `accept` attribute silently filtering `.xlsx` out of the browser's own FileList before submission, even though the server-side check was already correct - fixed to match.

**Tests:** 81 total (33 in `tests/test_mm3_spreadsheet_intelligence.py`, using real openpyxl-built workbooks throughout rather than mocking - openpyxl is now a first-class dependency; plus 4 new tests + 2 new routes in `tests/test_api_authentication.py`). Full suite: **2,687 passed, 0 failed** (2,650 baseline + 33 + 4 new).

**Live-verified against the running app:** a real risk-register workbook (formulas, hidden sheet) uploaded via the actual Add Documents flow, registered via the new API with real data, one cell edited via the API, then re-downloaded through the existing generic download route and reopened - the edit persisted, every formula and untouched cell was byte-for-byte unaffected, hidden sheet still hidden. Throwaway account and project cleaned up afterward.

**Finding/DerivedObservation usage evidence:** real spreadsheet-sourced evidence continues to show the same MM1/MM2 pattern - not merged, convergence question remains open.

**Documentation** (commit `a9dc614`): `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM3-scoped `IMPLEMENTED` row (MM4-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM3 section marked implemented with a pointer.

**Deferred, per this stage's own explicit scope:** Monte Carlo simulation, a spreadsheet grid/editor UI, full Excel recalculation, VBA/macro execution, Power Query, pivot-table/chart editing, arbitrary formula authoring, legacy `.xls` support, full workbook-wide semantic comparison. No permanent risk-record schema was created - a risk-register row is already representable via the general row-region mechanism.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM4 is not started by this stage.

**Evidence:** `HEAD`/`origin/main` both confirmed in sync after push (see final report for the exact hash). Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-05 — CLAUDE-MM2 (Product-Owner Acceptance Seal)

**Product owner accepts MM2 and the recommendation: ACCEPT — the PDF/document-intelligence slice is real, tested, additive, live-verified against uploaded content, and reuses the MM1 evidence infrastructure without duplicating it.**

**Commits sealed:** `0d95216` (implementation: `register_pdf_page_structure`, `services/pdf_intelligence.py`, the paragraph citation branch, source-version staleness in `resolve_region_citation`, the new admin-gated `/api/v1` route, `tests/test_mm2_pdf_document_intelligence.py`) → `ce325ac` (documentation: `kernel-object-model.md`, `STATUS.md`'s MM2-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM2 section marked implemented) → `6abb447` (continuation checkpoint).

**Source classifications tested:** all five - `text_native`, `image_only`, `mixed` (successful reads, distinguished by whether pages carry a text layer) and `extraction_failed`, `encrypted_or_unsupported` (failed reads, never conflated with "no text present") - each with dedicated test coverage in `tests/test_mm2_pdf_document_intelligence.py`.

**Test evidence:** focused - 23 tests in `tests/test_mm2_pdf_document_intelligence.py` plus 2 new tests and 1 new route added to `tests/test_api_authentication.py`'s route-auth matrix, all passing. Full suite: **2,650 passed, 0 failed** (2,625 baseline + 25 new). Falsification evidence: the cross-project reference guard was proven load-bearing (a deliberately unguarded bypass shown to succeed against a foreign source where the real, guarded method correctly raises).

**Live-browser/application evidence:** a real, hand-built 3-page PDF uploaded through the actual `/upload` flow (no regression to existing ingestion), opened and paginated page 1 → page 2 in the existing, unmodified PDF.js-backed browser viewer (real rendered text, real thumbnails), then the new API route triggered via a real authenticated session against that real Source - producing real `StructuralUnit`/`EvidenceItem` records and a citation rendering exactly `"mm2_verify_3page.pdf · Page 2 · paragraph 1"`, matching this stage's own governing prompt's citation example precisely. Throwaway account and project cleaned up afterward, no residue left in the live store.

**Preserved, explicit, non-blocking residuals and deferrals — not resolved or narrowed at this seal:**
- `Finding` and `DerivedObservation` remain distinct; their possible convergence is still an open architectural question, left open by this seal, not resolved.
- The broad `except Exception` fallback in `services/pdf_intelligence.py` conservatively classifies any novel failure as `extraction_failed`; retained as a future exception-narrowing item, not addressed now.
- OCR, PDF-to-image rendering, handwriting recognition, advanced table extraction, annotation, redaction, digital-signature validation, form filling, embedded-file extraction, a new region-selection UI, and complete redline/version comparison all remain deferred, unchanged.

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `6abb447` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**MM3 is not started by this seal.** This entry records acceptance only.

## 2026-08-05 — CLAUDE-MM2 (PDF and Document Intelligence)

**First real MM1 consumer**, authorized following the accepted MM1 seal (`8a6cf3f`). Repository-grounded investigation first found substantial existing infrastructure that shrank the real implementation needed: `BHiveParser.extract_pdf_pages` already gives real per-page text (used by `services/drawing_intake.py`); a full PDF.js-backed viewer with page navigation/zoom/search already exists (`static/js/pdf_viewer.js`); PDF bytes are reliably persisted at `Source.file_path`; `services/drawing_intake.py`'s own prior audit already established OCR/PDF-rendering are unavailable in this environment (no pypdfium2/PyMuPDF/pdf2image, no pytesseract/tesseract).

**Implementation:** `services/case_workspace.py`'s `register_pdf_page_structure` mirrors `register_table_evidence`'s own already-parsed-input shape (`pages: list[str]` in, never raw bytes — preserving the standing "does not import `bhive_parser`" rule) - one `StructuralUnit` per PDF page unconditionally, paragraph-level `AddressableRegion`/`EvidenceItem`s for pages with real text. New `services/pdf_intelligence.py` is the thin orchestration layer that does the real pypdf read and classifies `text_native`/`image_only`/`mixed`/`extraction_failed`/`encrypted_or_unsupported` - the last two only ever from a failed read, never conflated with "no text." `resolve_region_citation` gained source-version staleness awareness (`"status": "stale"` when the underlying Source has been superseded, label still preserved - "preserved old citation," reusing the existing `Source.superseded_by_source_id` pointer, no new mechanism). `update_source_identity` gained the four MM1 `Source` fields as parameters rather than a second method. One new admin-gated write route (`POST /api/v1/documents/<project_id>/sources/<source_id>/pdf-structure`); no new UI - the existing viewer was reused as-is.

**Tests:** 48 total (23 in `tests/test_mm2_pdf_document_intelligence.py`, 2 new + 1 new route in `tests/test_api_authentication.py`), including a deliberate falsification of the cross-project guard and a real, hand-built minimal PDF (no reportlab/fpdf dependency added) used for one genuine end-to-end unit test. Full suite: **2,650 passed, 0 failed** (2,625 baseline + 25 new).

**Live-verified against the running app, not tests alone:** a real 3-page hand-built PDF uploaded through the actual `/upload` flow (no regression), opened and paginated in the existing browser viewer (page 1 → page 2, thumbnails, real rendered text), then the new API route triggered via a real authenticated session against that real Source, producing real `StructuralUnit`/`EvidenceItem` records and a citation rendering exactly `"mm2_verify_3page.pdf · Page 2 · paragraph 1"` - matching this stage's own governing prompt's citation example precisely. Throwaway account and project cleaned up afterward.

**Finding/DerivedObservation usage evidence:** real PDF-sourced evidence continues to show the two concepts serving different grains (anchored verbatim content vs. an interpretation built from it) - consistent with MM1's own finding, not merged or migrated, the convergence question remains open.

**Documentation:** `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM2-scoped `IMPLEMENTED` row (MM3-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM2 section marked implemented with a pointer, original stage-intent prose preserved.

**Deferred, per this stage's own explicit scope:** OCR, PDF-to-image rendering, handwritten recognition, advanced table extraction (Batch J's `Table`/`TableRow` remains the tabular path), PDF annotation editing, redaction, digital-signature validation, form filling, embedded-file extraction, a new region-selection UI, and full semantic redline/version comparison.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM3 is not started by this stage.

**Evidence:** `HEAD`/`origin/main` both confirmed in sync after push (see final report for the exact hash). Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-05 — CLAUDE-MM1 (Product-Owner Acceptance Seal)

**Product owner accepts MM1 and its recommendation: ACCEPT — the multimodal evidence contract is real, tested, additive, live-verified, and sufficient for MM2-MM9 to build upon without premature extraction-engine implementation.**

**Commits sealed:** `452a814` (implementation: `StructuralUnit`/`AddressableRegion`/`EvidenceItem`/`DerivedObservation`, evidence relationships reusing `Relationship`, the read-time citation resolver, three read-only `/api/v1` routes, `tests/test_mm1_evidence_contract.py`) → `cc275c9` (documentation: `kernel-object-model.md`, `STATUS.md`'s MM1-scoped `IMPLEMENTED` row, `camel-multimodal-programme.md`'s MM1 section marked implemented) → `f76207f` (continuation checkpoint).

**Test evidence:** focused - 25 new tests in `tests/test_mm1_evidence_contract.py` plus 3 new routes added to `tests/test_api_authentication.py`'s route-auth matrix, all passing. Full suite: **2,625 passed, 0 failed** (2,600 baseline + 25 new). Falsification evidence: the cross-project reference guard was proven load-bearing (a deliberately unguarded bypass shown to succeed where the real, guarded method correctly raises); the citation resolver's broken-anchor state was proven load-bearing (removing the underlying Source's availability flips a previously-resolved citation to `unavailable`).

**Live application evidence:** verified against the actually-running app, not request-level tests alone - a real throwaway account and project seeded directly into the live `instance/registry` store, then a real session-cookie login followed by real HTTP requests through all three new endpoints (evidence list, structural-unit list, citation resolution for both a real region and an unknown one, correctly returning `{"status":"unavailable"}` rather than a 404/500) - all cleaned up afterward (account and project files deleted, no residue left in the live store).

**Preserved, explicit, non-blocking architectural residual — not collapsed or migrated at this seal:** whether Case-scoped `Finding` and the new, Case-optional `DerivedObservation` should eventually converge remains an open question. Both concepts stay exactly as implemented in `452a814` — no merge, no migration, no deprecation of either. **Assigned to the earliest later stage where real usage evidence (an actual MM2-MM7 consumer needing both concepts at once) makes the distinction-or-convergence decision necessary** - not resolved speculatively ahead of that evidence existing.

**Security/Intelligence Airlock and Design-Manager/risk-intelligence compatibility remain planning-level only** — the MM1 data model was shown capable of representing sensitivity classification, externally-researched evidence with human-adoption gating, and spreadsheet/risk-register/Monte-Carlo-shaped evidence and observations, but **no external connector, sanitization pipeline, new governed action, or Monte Carlo/spreadsheet engine was implemented in MM1**, and none is authorized by this seal.

**All explicit MM2-MM9 deferrals preserved unchanged:** no OCR, PDF rendering/annotation engine, spreadsheet editing engine, Excel formula execution, drawing geometry recognition, image editor, phone-camera integration, cross-document semantic search, Monte Carlo calculation, external internet/AI connector, addenda reconciliation, broad UI redesign, or production security hardening beyond MM1's own model requirements was built or authorized this stage.

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `f76207f` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**MM2 is not started by this seal.** This entry records acceptance only.

## 2026-08-05 — CLAUDE-MM1 (Multimodal Foundation and Evidence Contract)

**First implementation stage of the Camel MM1-MM9 programme**, authorized following the accepted cockpit gate (`CLAUDE-CGP-02`, GO recommendation, sealed at `febd434`). Repository-grounded investigation first (Foundation Batch J's `Table`/`TableRow`/`SourceReference`, `Relationship`, `Finding`, `Source`, `ConversationSourceAnchor` all read in full before designing anything) found strong existing building blocks that made a much smaller, purely additive implementation possible than a from-scratch design would have needed.

**New primitives** (`services/case_workspace.py`, commit `452a814`): `StructuralUnit` (a Source's logical subdivision - page/sheet/section/frame, open-world `unit_type`), `AddressableRegion` (a precise locatable portion - span/bbox/cell/crop, open-world `region_type`, never overfit to one modality's geometry), `EvidenceItem` (`evidence_class` is the one closed, validated vocabulary in the whole addition - direct/extracted/normalized/user-entered/imported/calculated/AI-generated-proposal/externally-researched), `DerivedObservation` (deliberately NOT `Finding` - `case_id` optional, mirroring `AnalysisRun`/`ConversationMessage`'s own convention, since an evidence-contract observation must also work before any Case exists; whether Case-scoped Findings and cross-modal Observations should eventually converge is left an explicit open question, not silently resolved).

**Reused rather than duplicated:** `Relationship` (already open-world `from_type`/`to_type`/`relationship_type`, already `provisional=True` by default) is reused as-is for every evidence relationship - only new `OBJECT_KIND_*`/`RELATIONSHIP_TYPE_*` constants were added (`same_subject_as`/`compares_with`/`calculated_from`/`mitigates`/`validates`/`invalidates`/`associated_with`). `Table`/`TableRow` (Batch J) remain the real tabular-specific realization, untouched.

**Citation contract:** `resolve_region_citation` derives a human-readable label at read time (never stored), returning an honest `"unavailable"` state - falsification-tested directly (removing the underlying Source flips a previously-resolved citation to unavailable).

**100% additive, zero destructive migration:** four new `ProjectWorkspace` list fields, four new `Optional` `Source` fields (`mime_type`/`size_bytes`/`security_classification`/`extractor_version`) - every legacy record simply lacks the new keys and loads with the existing empty-list/`None`-default convention, verified directly (a pre-MM1 workspace JSON with the keys stripped still loads and can create new MM1 records). Every mutation re-validates each referenced id's own `project_id` against the calling workspace, the same defense-in-depth `Folder`'s own methods already established - falsification-tested (a deliberately unguarded bypass proves the real, guarded method's rejection is load-bearing).

**Retrieval, no new UI:** three read-only routes on the existing `/api/v1` surface (`structural-units`, `evidence`, `citations/<region_id>`), added to `tests/test_api_authentication.py`'s existing route-auth matrix so they can't silently go unchecked.

**Tests:** 25 in `tests/test_mm1_evidence_contract.py` plus the 3 new API routes. Full suite: **2,625 passed, 0 failed** (2,600 baseline + 25 new), ~92min (duration, not pass/fail, is the noisy signal here per this file's own standing note). **Live-verified against the running app**, not request-level tests alone: a real throwaway account, a real project seeded directly against the live `instance/registry` store, then curl with a real session cookie through login → evidence list → structural units → citation resolution for both a real region and an unknown one (`{"status":"unavailable"}`, not a 404/500) - all cleaned up afterward (account and project files deleted).

**Documentation** (commit `cc275c9`): `governance/current/kernel-object-model.md` gained the real ground-truth entry; `governance/STATUS.md`'s authorization table gained an MM1-scoped `IMPLEMENTED` row (MM2-MM9 remain their own separate, still-`NOT AUTHORIZED` authorizations); `camel-multimodal-programme.md`'s own MM1 section marked implemented with a pointer, original stage-intent prose preserved rather than rewritten. Also fixed, as directly in-scope: an accidental duplicate paragraph in `STATUS.md`'s External Intelligence Airlock pointer row (same content committed twice across two prior CGP-02 commits).

**Deferred, per this stage's own explicit scope (MM2-MM9's own future work, not oversight):** any real extraction engine (OCR, PDF rendering, spreadsheet parsing, drawing/image intelligence); cross-document/cross-modal analysis; the Monte Carlo/Design-Manager engine itself (the model was shown compatible, not built); any External Intelligence Airlock connector; full source-version-aware citation staleness detection (`Source` has no version counter yet, only `supersedes_source_id` lineage); wiring structural-unit/region/evidence extraction into the live ingestion pipeline.

**Recommendation:** see the final report delivered in conversation for full detail. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction. MM2 is not started by this stage.

**Evidence:** `HEAD`/`origin/main` both confirmed in sync after push (see final report for the exact hash). Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-05 — CLAUDE-CGP-02 (Final Cockpit Gate — Product-Owner Acceptance Seal)

**Product owner accepts the final cockpit gate recommendation: GO — cockpit accepted; MM1 may begin.**

**Verified finding preserved:** the procurement-narrow project-creation framing found live during this gate's own browser review — `templates/upload.html`'s H1 ("Ingest an RFP or RFQ") and body copy, and every ingested Source's internal `kind` rendered verbatim to users as "RFQ RFP DOCUMENT" in the Display header and Toolbox — was corrected (honest, generic "Ingest a project document" copy; a new presentation-only `source_kind_label` filter, `Source.kind` itself untouched) and validated both in the real browser and by the full test suite.

**Accepted residuals, recorded exactly as non-blocking — none blocks or is a dependency of MM1:**
- 412px drawer overlap below the currently supported width; no mobile-support claim is being made; future resolution requires a separate product-owner choice.
- Footer implementation-detail text.
- New Folder disclosure closing after POST/redirect.

**Relevant CGP-02 commits:**
- `e929304` — Part D corrections (procurement-narrow copy, `Source.kind` display label)
- `c484d1c` — Part E governance record (External Intelligence Airlock / Constructive Boundary Response)
- `adb819c` — gate continuation checkpoint (final report reference)
- `502bd42` — post-gate cleanup review checkpoint

**Test result:** full suite 2,600 passed, 0 failed (2,597 baseline + 3 new in `tests/test_formatting.py`).

**Browser evidence:** live-verified directly — sign-in/error state, project creation/ingestion, Lists/Documents/Files, Display Layout (division numbering, split create/remove), Appearance matrix ("All" row, Black/Midnight Blue/Deep Forest), dark-theme contrast, conversation dock (send → AI response → source-grounding disclosure), and the two corrected defects above, each confirmed live before and after the fix.

**Evidence at seal:** `HEAD` and `origin/main` both confirmed at `502bd42` immediately before this seal. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

**MM1 is not started by this seal.** This entry records acceptance only.

## 2026-08-05 — CLAUDE-CGP-02 post-gate cleanup review (throwaway account/project audit)

**Verified state at close:** `HEAD` and `origin/main` both at `adb819c`, in sync. Working tree unchanged apart from the preserved, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`. No `python.exe`, `app.py`, or `pytest` processes remained running.

**Removed:** the `cgp02-audit` throwaway account and its one project (created during the CGP-02 live-browser cockpit review) were deleted.

**Confirmed absent:** the `qa1_vw8_throwaway` account did not exist — nothing to remove.

**Investigated and left active, no changes made:**
- `workspacetester` — a standing QA/reference account with historical project ownership; left active.
- `prodtest` and `produser` — no discovered dependencies, but their origin remains ambiguous; both left active pending stronger evidence.

No other users, projects, or files were altered during this review.

## 2026-08-05 — CLAUDE-CGP-02 (Final Cockpit Gate and MM1 Readiness Decision)

**Evidence-based cockpit gate review, not implementation work.** Reconstructed the accepted baseline from `governance/STATUS.md`/`CONTINUATION_CHECKPOINT.md`, then verified the live application directly in a real browser (sign-in through error state, project creation/ingestion, Lists/Documents/Files, Display Layout/multi-Display/Appearance, Toolbox/Eye, conversation dock, dark theme) rather than relying on prior-stage prose alone. A first background-fork attempt at the browser survey drifted into spawning its own nested agents/background jobs instead of doing the work directly (an instance of the fork-scope-bleed pattern already recorded in memory); stood it down and completed the walkthrough directly instead.

**Two live-confirmed, bounded corrections** (commit `e929304`): `templates/upload.html`'s H1 ("Ingest an RFP or RFQ") and body copy overclaimed procurement-only framing beyond even its own accepted-format list — reworded to "Ingest a project document," honestly scoped to the still-real PDF/DOCX/TXT/CSV/MD-only support. Separately, every ingested Source's internal `kind` (`rfq_rfp_document` — still the one real ingestion pipeline) was rendered verbatim to users as "RFQ RFP DOCUMENT" in both the Display header and Toolbox, reinforcing the same narrow framing structurally; added `services/formatting.py`'s presentation-only `source_kind_label` (`Source.kind` itself untouched) wired via a new Jinja filter at all four raw-render call sites in `templates/case_workspace.html`. `tests/test_formatting.py` added (3 tests). Full suite: 2,600 passed, 0 failed.

**Everything else evaluated and left alone, per this stage's own "gate-critical only" scope**: the Appearance "All" matrix, Display division numbering/split add-remove, dark-theme contrast, and the Files surface's Data Room/Design-Builder Workspace distinction (adequately explained in-context, mitigating the Documents-vs-Files naming overlap on first glance) all verified working as designed. The already-known, already-documented 412px fresh-session drawer-overlap residual (VW9A) was reconfirmed present, not re-litigated or fixed here — still pending its own product-owner choice among the three options VW9A already recorded. The gateway footer's "Flat-JSON registry" text (a mild internal-implementation-detail leak) was noted but left as non-blocking polish, below this stage's correction threshold.

**Governance record added** (commit `c484d1c`), planning-level only: `governance/specified-unbuilt/external-intelligence-airlock.md` — the product owner's Intelligence Airlock/External Intelligence Vestibule and Constructive Boundary Response concepts, composing with (not duplicating) `services/security_policy.py`'s existing `ACTION_EXTERNAL_AI_REQUEST` gate and `services/governance.py`'s `GovernanceLog`, mapped across MM1-MM9. `governance/STATUS.md` gained one pointer row, same filing pattern as the Camel programme's own entry. **NOT AUTHORIZED** for implementation — no connector, sanitization pipeline, new governed action, or boundary-response runtime behavior exists.

**Gate recommendation:** see the final report delivered in conversation for the full acceptance matrix and accept/conditional-accept/reject decision. No product-owner acceptance seal is recorded in this entry, per this stage's own explicit governing instruction.

**Evidence:** `HEAD`/`origin/main` both confirmed at `c484d1c` after push. Working tree clean except the pre-existing, untouched `tests/fixtures/nreocrc/_lab_instance_scratch_002/`.

## 2026-08-05 — CLAUDE-P40-VW9/VW9A-QA-CLOSE (Product-Owner Acceptance Seal)

**Bounded documentation-only close-out** - no application code, template, CSS, JavaScript, schema, or test file was touched in this stage.

**Product owner accepts:**

* `CLAUDE-P40-VW9 — Governed Files Display and Project File Architecture` (implementation commit `82d573b`, narrow-viewport verification commit `507e77e`)
* `CLAUDE-P40-VW9A — Files Cockpit Close-Out and Camel Programme Record` (cockpit-residual implementation + tests commit `13c0347`, Camel MM1-MM9 programme record commit `c7ef12b`)

The acceptance covers: the Files Display surface and Data Room/Design-Builder Workspace two-root architecture (VW9); the bounded Design-Builder folder domain model (create/nested-create/rename/move/delete-empty, soft-delete, sibling-scoped uniqueness, cycle prevention); and VW9A's resolution of all four cockpit residuals identified in the VW9 final report - A1 (folder-menu exclusivity/dismissal, and the broader in-flow-panel reachability fix it surfaced), A2 (move-destination path disambiguation), A3 (narrow multi-Display-division layout, resolved by the same fix as A1), and A4 (delete-cancellation return context).

**Evidence, re-verified as part of this close-out:** `HEAD` and `origin/main` both confirmed at `c7ef12b` immediately before this seal. Full test suite: **2,597 passed, 0 failed**, 12m32s, run once cleanly with no competing browser/test/server process left running afterward (VW9A's own close-out run). The pre-existing, unrelated `tests/fixtures/nreocrc/_lab_instance_scratch_002/` scratch fixture remains untouched (not deleted, modified, regenerated, staged, or committed) - preserved exactly as every prior session already left it.

**Retained, non-blocking cockpit residual, explicitly not resolved by this seal:** the whole-application shell (Menu/Lists/Toolbox/Eye) does not auto-collapse on a fresh session (no `localStorage` state yet) at narrow (~412px) viewport widths - both side drawers default to their visible overlay state simultaneously and measurably overlap (228px of mutual overlap at 412px, screenshot-verified during VW9A), obscuring the Display/main content area. No existing product claim asserts mobile/narrow-viewport support, so this was deliberately left unfixed pending a genuine product-owner choice among: enforcing/documenting a minimum supported width (≥641px, where the drawer mechanism never engages); a controlled reduced-panel mode (cheapest option: extend the existing `onNarrow()` mutual-exclusion JS in `templates/base.html` to also auto-collapse both drawers by default on first narrow load); or scheduling full narrow-shell adaptation as its own later cockpit stage. Tracked here for later resolution, not silently dropped.

**Also explicitly not part of this seal** (VW9's own stated exclusions, unchanged): the final issued Data Room hierarchy, bulk/ZIP import, external retrieval, existing-Document-to-folder assignment, full lifecycle automation, addenda/supersession comparison, a Files restore UI, cross-Project access, global search, and P41. VW9A's own Part B deferral (the "+ New Folder" disclosure closing after each POST/redirect) also remains accepted fast-follow polish, not part of this seal's own scope. The Camel MM1-MM9 programme record (`governance/specified-unbuilt/camel-multimodal-programme.md`) is a specified-but-unbuilt intent record - this seal does not authorize implementation of any MM stage.

**UI reference update not required** (no new `data-ui-ref` entries were added by VW9A's own residual fixes).

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

## Delta Spin engine + first Spin Surface slice — accepted (CLAUDE-DELTA-SPIN-01/02, CLAUDE-SPIN-SURFACE-01/02)

Starting state: `dd825a4` (clean, North Bayview reconciled to 55 Documents,
no prior Spin capability - repository-wide grep for "Delta Spin"/"First
Spin" returned zero code matches; `governance/specified-unbuilt/
spin-project-intelligence-preview.md` explicitly marked the whole concept
NOT AUTHORIZED). Ending state: `5b5af4c`, live and deployed, both the Delta
Spin engine and its first human-facing surface formally Product-Owner-
accepted.

### What shipped (four commits, `dd825a4..5b5af4c`)

1. **`62fcfb1` (CLAUDE-DELTA-SPIN-01)** - the first governed Delta Spin
   implementation: `services/spin.py` (new, mirrors `services/project_qa.py`'s
   Anthropic-call pattern, reuses its `BEHAVIORAL_CONTRACT`), `SpinRun` +
   `KNOWN_SPIN_DELTA_CLASSIFICATIONS` (new/strengthened/weakened/resolved/
   unchanged/superseded/indeterminate/new_verification_gap) in
   `services/case_workspace.py`, `ComposerFinding` extended with three
   additive fields (`spin_run_id`/`delta_classification`/
   `related_prior_understanding` - a Spin-produced finding reuses
   `ComposerFinding` rather than a second finding type, per that governing
   record's own recommendation), a Toolbox `Spin` section with First/Delta
   Spin triggers. 38 focused tests, full suite green.
2. **`02a4c49` + `f0ef9cb` (CLAUDE-DELTA-SPIN-02)** - live changed-evidence
   acceptance testing (a temporary project ingesting the real North Bayview
   G1 sample corpus, First Spin, a real governed Reconcile to the G2 corpus,
   Delta Spin against that baseline) found and fixed two real, live-only
   defects the earlier zero-delta live test never exercised: `max_tokens`
   truncation (4000 -> 8000) and, as a direct second-order consequence, an
   insufficient timeout ceiling (90s -> Spin-specific 140s, confirmed
   against this deployment's real 150s gunicorn/nginx limits). Live-
   reproved after each fix; the second, populated Delta Spin run
   independently re-derived findings matching this session's own earlier
   manual North Bayview investigation (the OS-08 v1.0a->v1.1 supersession,
   the "not adopted as a requirement" third-bay framing, the PA Schedule 14
   commissioning-gap) without ever being told them, plus a genuinely new
   cross-disciplinary finding (OS-08 security -> commissioning -> PA
   Schedule 20 payment-mechanism deduction risk) this session's own manual
   work never found.
3. **CLAUDE-SPIN-SURFACE-01 (design only, no code)** - the accepted product
   architecture for a longitudinal Spin history/State-Report/evolution-
   matrix surface, grounded in direct inspection of `STABLE_DIRECTORY_KINDS`
   (the real extension point) and the already-built-but-unwired
   `MaturityRecord`/`ExpectedInformationProfile`/`evaluate_information_
   sufficiency` phase-conformance engine (`CLAUDE-GO-QAC-01`) as the target
   reuse point for a future document-maturity column. Named, not built:
   Local Spin, the full evolution matrix, persisted authority/`Supersession`
   relationships (MM6's `Relationship`/`record_evidence_relationship`
   named as the closest existing primitive for that future step).
4. **`5b5af4c` (CLAUDE-SPIN-SURFACE-02)** - the smallest coherent slice of
   that design: `"spin"` registered as a fourth `STABLE_DIRECTORY_KINDS`
   stable-singleton view (`display.spin`), a pure derived `_build_spin_
   state_report` view-model function (classification counts, evidence
   delta from `source_signature` diffing, reassessed-finding count - no new
   persistence), full unhidden Spin history with per-run drill-down via
   `?spin_run=<id>`. The Toolbox's own `toolbox.spin` section shrank to
   triggers + a one-line latest-run summary + a link into the new tab
   (relocation, not duplication - same precedent `CLAUDE-GO-DNA-01`'s Panel
   Zoning already established). Minimum-viable naming-conflict fix: the
   older, unrelated, client-side-only "Spin — Evidence Isolation
   (prototype)" launcher and its own page renamed to "Evidence Isolation
   (Legacy Prototype)" / button text "SPIN" -> "APPLY" (visible text only,
   every `spin.*` ui_ref left unchanged). 15 new focused tests plus 3
   updated pre-existing tests (two in `test_delta_spin_01.py` whose
   assertions had to follow the relocated content, one in
   `test_spin_00a_container_prototype.py` for the rename). Live-validated
   against the same temporary acceptance project, including a failed run's
   own State Report and the renamed prototype page.

### Full suite state at each accepted checkpoint
- `62fcfb1`: 4049 passed / 10 known / 0 new.
- `f0ef9cb`: 4049 passed / 10 known / 0 new (unchanged - both fixes were
  narrow constant changes, no new tests required at the engine layer).
- `5b5af4c`: 4064 passed (4049 + 15 new) / 10 known (unchanged) / 0 new.
The "10 known" failures are the same pre-existing, unrelated CSS/JS/
Playwright UI tests throughout this whole arc - never touched, never
counted as new.

### Temporary acceptance project - preserved, not cleaned up
`CLAUDE-DELTA-SPIN-02-Acceptance-NorthBayview-G1`, project id
`2e918a07-b7cc-483b-a888-d0224d9d4a61` (Client/Owner environment), live on
`archiosk.com`. Contains a real G1 First Spin (18 findings, after 3 earlier
honest `max_tokens`/timeout failures also still preserved), a real governed
G1->G2 Reconcile (13 new / 2 missing / 1 renamed, confirmed and imported),
and two independent Delta Spin runs (18 and 17 findings) against that same
baseline - the concrete acceptance evidence behind both engine and surface
sign-off. Deliberately left in place per the governing prompts' own
explicit "do not delete automatically" instruction - a future session
should get Product Owner confirmation before removing it.

### Known residual, explicitly deferred, not a blocker
The Spin State Report's classification-summary line renders the raw
internal vocabulary token verbatim (`NEW_VERIFICATION_GAP`, underscore,
all-caps) rather than a humanized "NEW VERIFICATION GAP" - found during the
final live validation pass, Product-Owner-acknowledged as cosmetic and
explicitly deferred to a later surface-polish pass, not fixed in this arc.

### Explicitly NOT authorized/built by any of this work (per each governing
prompt's own repeated scope boundary - do not assume future authorization)
Local/Document Spin (and its own promotion-to-project-thread mechanism);
the Project Spin -> Local Spin recommendation column; Document Phase
Completeness/Maturity (even though its own target reuse point is now
identified); the full evolution matrix (thread-identity strategy (a) -
text-anchored via `related_prior_understanding` - is the recommended
starting mechanism when that work is authorized, not thread-id schema
strategy (b)); persisted authority/Supersession relationships; the larger
ARCHIOSK visual-language programme; Publish; Builder; RFI automation.

## Recommended next prompt
Either (a) a small, isolated text-formatting fix for the deferred
`NEW_VERIFICATION_GAP` display issue, if the Product Owner wants it picked
up opportunistically before the next real slice, or (b) the next Spin
Surface slice explicitly named as future work in CLAUDE-SPIN-SURFACE-01/02
(Local Spin generation, extending `CLAUDE-GO-QAC-01`'s phase-conformance
engine to the Source grain for document maturity, or the full evolution
matrix using thread-identity strategy (a)) - whichever the Product Owner
prioritizes; none of the three has been started.

---

## Session checkpoint: CLAUDE-HOLODECK-WORLDS-SPIN-01, Deep Ocean hue fix,
## CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01 - pushed, deployment outstanding

Four changesets committed and pushed to `origin/main` this session, in
dependency order:

1. `172b2b1` - Governance: establish the Prompt Depository
   (`governance/prompt-depository/PROMPT_REGISTER.md`), per explicit
   Product Owner authorization lifting the prior "no provenance tagging"
   stance. Bounded exception, not a general provenance system - see
   `CLAUDE.md`'s own "No general provenance-tagging system" section.
2. `f829f27` - CLAUDE-HOLODECK-WORLDS-SPIN-01: Survival Mode, the first
   Spin World. `SPIN_WORLD_SURVIVAL`/`KNOWN_SPIN_WORLDS`
   (`services/case_workspace.py`), `SPIN_WORLD_OBJECTIVES` +
   `_SURVIVAL_MODE_INSTRUCTIONS` + `games_played` self-reported trace
   (`services/spin.py`), an optional `world` form field on
   `run_spin_route` (ordinary triggers with no world posted are
   unaffected - `test_ordinary_spin_run_unaffected_by_world_feature`), a
   "Survival Mode" checkbox on both Spin trigger forms, and a World/
   Objective + Games Played section on the Spin State Report. 22 new
   tests (`tests/test_holodeck_worlds_spin_01.py`).
3. `1d83d42` - Fix Deep Ocean theme: corrected a systemic cyan-green hue
   bug (~172 degrees) to the intended blue-cyan (~207 degrees) across
   `tokens.css`'s `--ocean-*` tokens and its two byte-identical-parity
   duplicates in `main.css` (`.gateway-shell`, `.gateway-card-compact`)
   and `landing.css`. **Product Owner accepted; this correction must be
   preserved** - do not revert to the older `rgba(176, 255, 244, ...)`
   green/aqua direction. See the new "Deep Ocean accepted visual
   baseline" note added to this file's own `CLAUDE.md` (Color / visual
   changes section) recording the same constraint durably.
4. `4274808` (HEAD) - CLAUDE-BAUHAUS-CONSTRUCTIVIST-UI-01: bounded first
   visual slice - Spin State Report composition. Per-classification
   presentation treatment (`_SPIN_CLASSIFICATION_TREATMENT` in
   `routes/workspace.py`: rank/weight_class/accent/bar_px/border_style
   for all 8 `delta_classification` values, only 2 non-default accent
   colors), rendered via `.spin-finding`/`.spin-weight-max/-high/-base/
   -quiet`/`.spin-report-headline` (`main.css`) and a rewritten Findings
   loop (`templates/case_workspace.html`) consuming the new
   `spin_state_report.presented_findings`. 22 new tests
   (`tests/test_bauhaus_spin_findings_01.py`); full Spin-related suite
   (97 tests) green.

Full regression suite run before this arc's commits were split out:
4109 passed / 9 failed (the same pre-existing, unrelated flaky set as
every prior checkpoint in this file) / 0 new failures.

### Deployment status: OUTSTANDING as of this checkpoint - do not assume live
`git rev-parse HEAD` and `git rev-parse origin/main` both resolve to
`4274808` - the repository itself is fully in sync. **Production
(archiosk.com) is not.** Verified directly against the live server:

- `GET /health` returns `{"status":"ok"}` - **this does NOT prove the new
  code is deployed.** It reflects process liveness/registry health only,
  not which commit's static assets or Python/template code is running.
- Cache-busted `fetch()` of `https://archiosk.com/static/css/main.css`
  (fresh request, `cache: 'no-store'`, confirmed via `?cb=<timestamp>`
  querystring so no CDN/browser cache could be in play) shows:
  - the OLD Deep Ocean value `rgba(176, 255, 244, ...)` still live;
  - the accepted correction `rgba(176, 219, 255, ...)` **not** live;
  - `.spin-report-headline` and `.spin-weight-max` (Bauhaus CSS) **not**
    present in the served stylesheet at all.
- DOM checks on the live acceptance project's own Spin tab
  (`archiosk.com/projects/2e918a07-b7cc-483b-a888-d0224d9d4a61/
  workspace?view=spin`) show the OLD `<h2>Spin State Report</h2>` /
  `.workspace-pane-label` / `macros.subdisclosure` markup, and zero
  elements matching `[data-ui-ref="toolbox.spin.world-survival"]` - the
  Survival Mode control and Bauhaus Spin State Report markup are both
  absent from the live surface.

An earlier live visual judgement was given by the Product Owner (Deep
Ocean accepted, Bauhaus rejected as "not visibly strong enough") based
on looking at archiosk.com **before this discrepancy was caught**. Once
shown the direct evidence above, the Product Owner withdrew both
verdicts, then clarified the final disposition:

- **Deep Ocean: ACCEPTED, independent of live-deployment status.** The
  blue-leaning hue correction itself is approved and must be preserved
  when deployment occurs - the earlier live sighting being invalid does
  not put the design decision back in question, only the "I confirmed
  it live" claim.
- **Bauhaus/Constructivist Spin State Report: PENDING live visual
  judgement.** The earlier rejection is void (it wasn't looking at this
  code). Do not revert or widen the Bauhaus work based on that voided
  verdict. Do not record Bauhaus/Constructivist principles into
  governance until an actual live review happens post-deployment.
- **Survival Mode / Project World: PENDING live verification.** The
  required live deliverable (run Survival Mode against real project
  evidence on the preserved acceptance project, show the actual
  `games_played` trace) has still never been completed - blocked purely
  on deployment, not on any remaining code work.

### Next session: do not repeat the mistake above
Before reporting any live visual/functional review as complete, verify
the specific commit is actually served (a cache-busted content check or
DOM marker unique to the change, not just `/health` or "the page looks
different") FIRST. A stale/partial deploy is easy to mistake visually
for the real thing. Once `4274808` (or later) is confirmed live by that
method, the outstanding work is exactly the three items above - no new
code, no additional commits needed unless the live review surfaces a
real defect.

### Note on working-tree state at session close
At session close, `CLAUDE.md` and `governance/prompt-depository/` showed
uncommitted changes this session did not make (a new "Deep Ocean
accepted visual baseline" note in `CLAUDE.md`, and four new prompt
records - two attributed to Agent "Claude" covering a Holodeck-Worlds
terminology correction, two attributed to Agent "Codex" covering a
"Project North Star" transition/advancement-rule direction neither
this session's own conversation nor this checkpoint has any other
record of). This looks like concurrent activity from another
agent/process against the same working directory, not leftover work
from this session. Left entirely untouched (neither committed nor
discarded) rather than guessed at - a future session should investigate
provenance before acting on it either way.
