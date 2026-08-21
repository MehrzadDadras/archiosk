# Test lanes — fast feedback without weakening the full suite

**CLAUDE-TEST-ACCEL-01.** The full suite (`./venv/Scripts/python.exe -m pytest -q`,
currently **3,594 tests**) stays the one authoritative gate before any commit that
touches `routes/`, `services/`, `templates/`, `static/`, `models.py`, `config.py`,
`app.py`, or migrations, and before every deployment — see `CLAUDE.md`'s own
Testing section, which this document does not change or override.

What this document adds: a **hand-maintained mapping** from "what changed" to
"which smaller test set gives fast, trustworthy feedback before the full run."
No pytest markers, no directory reorganization, no new dependency — every lane
below is just an explicit list of existing file paths, runnable today with the
ordinary `pytest -q <paths>` command. Nothing here deletes a test, weakens an
assertion, or makes any test's outcome conditional on which lane ran it.

## Why file-list lanes, not markers or directories (yet)

The suite has **no existing `pytest.ini`/`pyproject.toml`/`conftest.py`** and no
registered markers — confirmed by direct inspection, not assumed. Test files are
named by the *governance stage that introduced them* (`test_p40vw7b_*`,
`test_ca1d_*`, `test_mm4_*`, `test_spin_00a_*`), not by test *kind* — so a
filename alone doesn't reliably say "this is a unit test" vs. "this is a
cross-cutting regression test." 93 of the 204 test files (1,911 of 3,594 tests —
about 53% of the whole suite) carry a `p40`/`ca1d` stage prefix and are
structural HTML/route assertions against the Flask test client — there is no
real browser/E2E layer in this suite at all (every file that says so explicitly
confirms it; no Selenium/Playwright dependency exists in `requirements.txt`).

Retrofitting `@pytest.mark.*` decorators onto dozens of existing files is a real
reorganization with its own review cost — CLAUDE-TEST-ACCEL-01 deliberately
stops short of that (see its own "do not undertake a large reorganization
without first reporting" instruction) and instead proves the *cheaper* thing
first: does explicit-file-list selection already give the fast-feedback/full-
assurance split the Product Owner wants, with zero new test-suite risk? Measured
answer below: yes, by roughly 25-50x for the two worked examples tried.

## The lanes

**Lane A — Immediate Local.** The test file(s) written for the exact surface
being changed. Always the fastest, always run first.

**Lane B — Feature/Domain.** Other test files that exercise the same shared
mechanism the change actually touches (a shared template block, a shared route
function, a shared service) — found by grepping for the specific `data-ui-ref`
prefix, shared macro, or shared function the change modified, not just by
"feels related."

**Lane C — Critical Core.** A fixed, small set that protects cross-cutting
invariants regardless of which feature changed: project isolation/
authorization (`test_project_access_control.py`, `test_route_authorization_
hardening.py`, `test_security_enforcement.py`, `test_csrf_protection.py`),
canonical-data integrity (`test_operating_environment.py`,
`test_backup_restore.py`, `test_flask_migrate_baseline.py`), the golden-path
smoke test (`test_market_critical_golden_path.py`), and the one file that
enforces this repo's own global design-system conventions
(`test_global_search_and_header.py` — see "What Lane C actually caught" below).

**Lane D — Broader Regression.** `tests/test_foundation_batch_*.py` (10 files,
166 tests) — this repository's own existing broad, deliberately cross-cutting
golden-path/regression sweep, already present, not something this document
invents — plus any other file a real dependency chain points to (e.g. changing
`CaseWorkspaceStore` itself should pull in every file that instantiates it,
which in practice is most of the suite — see "Escalation past Lane C" below).

**Lane E — Full Acceptance.** `./venv/Scripts/python.exe -m pytest -q` — all
3,594 tests, unchanged, still the only gate for commit/deploy/checkpoint.

## Assurance tiers — orthogonal to lanes

Assurance tiers describe what a test proves; they do not replace or change the
execution lanes above.

- **Tier 1 — deterministic wiring:** IDs, capability routing, template
  propagation, and precedence order.
- **Tier 2 — structural invariants:** provenance isolation, authority
  separation, context-is-not-evidence, and project/application separation.
- **Tier 3 — context-grounded behavior:** real template identity, selected
  object, referent, active source, and task intent.
- **Tier 4 — adversarial ambiguity:** ambiguous language plus stale, conflicting,
  missing, or cross-surface context.

**Tier 4 must vary context, not only language.** Existing adversarial lexical
corpora are Tier-4 regression material, but are not by themselves sufficient
architectural acceptance tests.

## Decision rule

1. Start at Lane A. Always.
2. Add Lane B when the change touches anything beyond the feature's own new
   file(s) — a shared template block's control flow, a shared macro, a route
   function also used by other features, shared CSS/JS loaded on other pages.
3. Add Lane C whenever the change touches `routes/`, `services/case_workspace.py`,
   authentication/authorization code, any persisted field, or shared CSS/JS —
   i.e. almost always, for anything past a single isolated new file. Lane C is
   cheap (roughly 80-140s measured below) relative to its coverage, so the
   conservative default is to include it rather than reason about whether it's
   "really" necessary.
4. **Uncertainty widens the set, never narrows it** — if it's unclear whether a
   shared primitive is actually touched, treat it as touched and run Lane B/C
   anyway. This mirrors CLAUDE-TEST-ACCEL-01's own explicit guardrail.
5. Lane D/E only at a real checkpoint: before commit for anything touching
   `routes/`, `services/`, `models.py`, `config.py`, `app.py`, or migrations
   (full suite, per `CLAUDE.md`'s existing rule — unchanged), and always before
   deployment.

## Measured proof — Worked Example 1: SPIN-00A (commit `f465fcd`)

SPIN-00A touched: `routes/workspace.py` (`show_workspace`'s own toolbox
selection `{% if %}` chain gained a new branch), `templates/case_workspace.html`
(same chain, plus a new launcher inside the existing Project-Intelligence
section), `templates/_spin_prototype.html` (new), `templates/_macros.html` (new
`tool_pane` macro), `templates/base.html` (one new script tag, same gate as two
existing ones), `static/css/main.css` (new rules only), `static/js/
spin_prototype.js` (new).

| Lane | Files | Tests | Measured time | Catches |
|---|---|---|---|---|
| A | `test_spin_00a_container_prototype.py` | 20 | 17-18s | Spin's own logic: launcher, all 3 variants render, nonmutation, authorization |
| A+B | + `test_go_right_panel_01.py`, `test_p40e2_toolbox_and_removal.py`, `test_p40eye1_correction_resize_canvas.py`, `test_p40eye1_scrollbar_theming.py`, `test_p40eye1_toolbox_eye_column.py`, `test_p40vw7a_ui_reference_map.py` | 174 | 60s | Proves the shared toolbox `{% if/elif %}` chain SPIN's new branch was inserted into still renders Investigation/Document/default views identically, and the UI-reference registry stayed consistent |
| A+B+C | + `test_project_access_control.py`, `test_route_authorization_hardening.py`, `test_security_enforcement.py`, `test_csrf_protection.py`, `test_operating_environment.py`, `test_backup_restore.py`, `test_flask_migrate_baseline.py`, `test_market_critical_golden_path.py`, `test_global_search_and_header.py` | **317** | **140s (2m20s)** | See below — this is what actually caught the real regression |
| E (full) | everything | 3,594 | 2,615-4,662s (43-78 min, two measured runs) | Authoritative gate |

**What Lane C actually caught, for real, during this same session:** implementing
SPIN-00A's new CSS, I used `--font-mono` (reserved for exactly 3 technical-
register exceptions — paths/ids/logs — by this repo's own explicit design-system
rule) in three new compact-control classes. Lanes A and B — every test file
topically related to Spin or to the Toolbox shell — passed cleanly. The
violation was caught only by `test_global_search_and_header.py`'s
`test_font_mono_reduced_to_exactly_the_three_technical_exceptions`, a file with
**no topical relationship to Spin or the Toolbox at all** — it asserts a
repo-wide typography convention by counting a CSS pattern across the whole
stylesheet. This is the concrete, measured reason Lane C exists as a *fixed*
set run "even when the immediate feature appears unrelated," per CLAUDE-TEST-
ACCEL-01's own Lane C definition — a naive "only run tests topically near my
change" heuristic would have missed this and only caught it at the full-suite
gate, 2,600+ seconds later instead of 140.

**Escalation past Lane C:** the remaining ~3,277 tests (MM1-8 multimodal
intelligence, RFI compliance/export, voice, security-department depth, self-test
harness, foundation batches, every other stage-tagged UI file, etc.) have no
plausible dependency on anything SPIN-00A's commit touched — none of them
render the Toolbox's no-selection branch, call `show_workspace`, or assert
`--font-mono` counts. Lane D/E were correctly deferred to the pre-commit/
pre-deploy gate, which is exactly what happened (this session ran the full
3,594-test suite once before committing `f465fcd`, and it passed).

## Measured proof — Worked Example 2: Requirements (a substantially different feature)

Requirements is a deeper application/data feature than Spin: `routes/
workspace.py`'s `promote_requirement_item_route`/`register_requirement_route`/
`revise_requirement_route`, `services/requirement_investigation.py` (a real
Anthropic-integration investigation flow), and `services/requirements_
registry.py`, all writing real, persisted, canonical `ProjectWorkspace` fields
(`workspace.requirements`) — unlike Spin, which never mutates project data at
all.

| Lane | Files | Tests | Measured time |
|---|---|---|---|
| A | `test_requirement_promotion.py`, `test_requirement_investigation.py`, `test_requirement_evidence_workflow.py`, `test_requirement_extraction_metadata_filter.py`, `test_requirement_revision_wiring.py` | 54 | 17-18s |
| A+B | + `test_workflow_integration.py` (real end-to-end promotion flow), `test_ca1d_composer_spine_stage1_schema.py` (Composer surfaces Requirement-shaped findings), `test_root_i1_canonical_navigation.py` (root nav routes into Requirements), `test_supersession_authority.py` (a Requirement revision is a supersession event) | 105 | 31-32s |
| A+B+C | + the same 9-file Critical Core set as above | **248** | **110s (1m50s)** |
| E (full) | everything | 3,594 | 2,615-4,662s |

Same shape as Spin, at roughly proportionally larger Lane A/B (Requirements has
more real, persisted behavior to protect) — confirming the lane *architecture*
generalizes; only the specific file lists inside Lane A/B change per feature.

## Estimated routine-feedback reduction

Both worked examples: **Lane A+B+C finished in under 2.5 minutes** against a
full-suite baseline of **43-78 minutes** measured this same session — roughly a
**20-30x** reduction in wall-clock feedback time for the escalation path that
actually would have caught every regression introduced during real work this
session (both the UI-reference-registry drift from the Gateway task and the
font-mono violation from this task were each inside a Lane A+B+C set for their
own change). These are measured repository numbers, not estimates.

## Parallelization

`pytest-xdist` is **not currently installed** (`pip show pytest-xdist` returns
not-found) — nothing here assumes it. Investigated feasibility, not enabled:

- Every test class creates its **own** `tempfile.mkdtemp()`-rooted registry
  directory and its **own** `create_app("testing")` Flask app per `setUp` — no
  shared file path or shared mutable module-level state was found across test
  files (checked directly: no `lru_cache`/module-level cache in `services/` or
  `tests/`, no test binds a real port or starts `app.run()`).
- `TestingConfig.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"` — each Flask
  app instance gets its own isolated in-memory DB; nothing shared across
  processes, and xdist workers are separate OS processes, not threads.
- One file (`test_p40c_legacy_compat_and_safety.py`) mutates real `os.environ`
  directly for a handful of tests, with an explicit snapshot/restore in
  teardown — safe across xdist worker processes (separate `os.environ` per
  process) but worth a second look before ever running that file interleaved
  with unrelated tests *within the same worker* if xdist is adopted later.
- **Conclusion:** the isolation pattern already used throughout this suite
  looks safe for process-level parallelization (`pytest-xdist -n auto`), but
  this was not proven by an actual parallel run in this pass — CLAUDE-TEST-
  ACCEL-01's own guardrail ("do not introduce parallel execution until its
  determinism is proven") means that requires a dedicated follow-up: install
  `pytest-xdist` in a throwaway environment, run the full suite under `-n auto`
  twice, and diff pass/fail sets before ever relying on it for a real gate.

## Migration plan (proposed, not started)

If markers are wanted later (mainly useful for `pytest -m critical_core`
ergonomics over typing 9 file paths): register `critical_core`, `spin`,
`requirements`, etc. in a new `pytest.ini`, add one `pytestmark =
[pytest.mark.critical_core]` line per file in the Lane C set (9 files) first —
smallest, highest-value set, touches nothing about test behavior — then expand
per-feature markers opportunistically as new features land (e.g. SPIN-00A's own
test file could carry `pytestmark = pytest.mark.spin` today), rather than
retrofitting all 204 files in one pass. Each marker addition is a one-line,
zero-behavior-change diff to an existing file, individually reviewable.

## Do not

- Do not treat a Lane A-only or Lane A+B-only pass as sufficient to commit.
  Lane C is cheap; skip it only when a change is provably confined to one new,
  never-shared file (rare — even SPIN-00A's own "just a prototype" change
  needed Lane C to catch its real regression).
- Do not run Lane D/E lists by intuition when a real dependency chain is
  unclear — expand toward the full suite instead.
- Do not skip the full suite before any commit touching `routes/`, `services/`,
  `templates/`, `static/`, `models.py`, `config.py`, `app.py`, or migrations —
  unchanged from `CLAUDE.md`.
