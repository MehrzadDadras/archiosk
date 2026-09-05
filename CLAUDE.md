# Claude Code — operating notes for Archiosk

This file is about **how Claude should operate on this repository** —
environment quirks, safety rules, and pointers to the right source of
truth. It deliberately does not contain:

- **Why Archiosk is architected the way it is** — that's `governance/`
  (start at `governance/STATUS.md` and
  `governance/current/kernel-object-model.md`; the domain model itself
  is ground-truthed in `services/case_workspace.py`). If a review or
  discussion reaches a ratified conclusion worth keeping, it belongs as
  a real file under `governance/`, following that corpus's existing
  structure — not duplicated or summarized here.
- **What happened during a particular session or experiment** — that's
  git history and commit messages. Don't build a parallel log of "what
  Claude did" in this file; if something is worth remembering, either
  commit it as governance (if it was ratified) or leave it as
  conversation history (if it was exploratory and wasn't).
- **File layout** — that's `MANIFEST.md` (hand-maintained; update it
  when you add, remove, or repurpose a tracked file).

## Scope boundary

Never edit, or edit-in-reference-to, anything under
`C:\Archiosk\App\archiosk-explorer` — a separate, sibling repository.
Read-only cross-references are fine when explicitly relevant; edits are
not.

## Before proposing a dependency or architectural pattern

Run `python tools/dependency_fit.py --name "..." [flags]` (see its own
`--help` / docstring). It encodes already-settled, deliberate
constraints — flat-JSON storage over a database, no client build step,
no async runtime, graceful degradation for the one optional cloud
dependency — with the reasoning attached. Don't re-derive that reasoning
from scratch in conversation, and don't silently propose something that
contradicts it.

Before proposing a new durable internal abstraction, first identify what already
serves the purpose, state why it is insufficient, and determine whether extending
it is cleaner than adding another abstraction. The `interpret_message()`
contextual-router work is an example: inspect the existing dispatch path before
introducing a parallel router.

That rule exists to prevent uncontrolled duplication — **not** to make the
existing shape automatically correct. Finding an existing equivalent does not
decide the architecture; it starts the question. See "History is evidence, not a
cage" below, which governs when the answer is to converge, supersede or delete
rather than extend.

## History is evidence, not a cage

**Product Owner correction, 2026-08-26.** This section governs where earlier
operating notes caused preservation of an implementation structure merely
because it already existed. It changes nothing about authority, evidence
integrity, security, project isolation, data preservation, consequential-action
gates, production safety, or any explicit Product Owner decision — those are
unaffected and still bind.

The repository, governance corpus, Prompt Depository, tests and prior
Claude/Codex/Gemini work are the accumulated history of the product. Read them
to learn why something exists, what it solved, what failed, and what was
decided. Then ask the question that actually matters:

> **If we were solving the Product Owner's real problem today, knowing what we
> now know, would we deliberately design it this way?**

If yes, keep it because it is good. If no, challenge it. Never reason "it exists,
therefore preserve it."

**Three categories, and only one of them is protected.** *Durable principle* —
provenance, project isolation, owner-controlled access, selection-is-not-
authorization, governed consequential actions, security boundaries, honest
uncertainty — defend these. *Current implementation* — routes, panels, menus,
service boundaries, class structure, CSS architecture, internal naming — open to
challenge. *Historical artifact* — structures that exist only because
development arrived there incrementally. Accumulated code, docs and tests do not
promote an accident into a principle.

**Product first, repository second.** Start from what the human experience
should be, then what architecture produces it safely, then how the repository
should evolve. Do not derive the experience from the classes that happen to
exist. A simple Product Owner expectation that the repository makes awkward is
evidence about the repository, not about the expectation.

**Internal complexity must earn user visibility.** ARCHIOSK may hold enormous
sophistication underneath. That is not a reason for another panel, mode,
Composer, indicator or vocabulary term. For each internal distinction ask
whether the user genuinely needs to understand it to do their work; if not, keep
it underneath. Sophistication below should usually produce *more* simplicity
above. Watch for the proliferation cycle — implementation distinction →
explanation → terminology → abstraction → UI concept → governance record → more
implementation — and stop it. **Deletion and convergence are advancement**;
progress is not measured in components created.

**Tests protect intent, not accidental history.** When a deliberate improvement
breaks a test, decide which it is: a real regression, or a test defending
behaviour we intend to supersede. Never weaken a genuine safety test casually,
and never preserve obsolete behaviour just to keep an old assertion green.
Surface the distinction rather than resolving it silently.

**Governance makes change deliberate, not unthinkable.** If existing governance
appears to block a materially better product, neither violate it silently nor
abandon the better idea silently. State what the authority says, what the
evidence suggests, and what would be affected — then let the Product Owner
decide. Ambiguous conflicts get surfaced, not resolved by defaulting to either
preservation or revolution.

**Constraints bind implementation, never imagination.** When something better is
visible but currently blocked, do not quietly shrink the idea until it fits.
Report the better possibility, the exact constraint, the strongest safe step
available now, and what would unlock the rest.

**But do not manufacture blockers.** Ordinary engineering difficulty is not a
Product Owner decision. Do not ask again for authority already held, and do not
use governance as cover for conservatism. If the better solution is clear, the
authority exists, the risk is understood and the work is bounded — do it. This
cuts both ways and has already cost real time here: the Developer Composer
convergence was escalated as an A/B/C decision when the non-evidence-touching
option was plainly within authority all along.

**Four honest outcomes** for meaningful architectural work: do it; run the
smallest experiment that could disprove it; surface the constraint you can see
past; or reject it with reasons. Not every problem resolves into preserving what
is already there.

**Think AI-native.** Ask whether a workflow would still look like this if
capable AI had existed when it was invented. Where it is safe, GO should absorb
navigation, classification, form-filling and tool-selection rather than
reproducing conventional software mechanics — while explicit human authority is
preserved wherever consequences require it.

## Environment quirks that have cost real debugging time

- **`STATIC_VERSION` (and any env var with a `config.py` default) is
  actually controlled by `.env`, not the default in `config.py`.**
  `python-dotenv` never overrides an already-set environment variable,
  so once `.env` has a real value, `config.py`'s `os.getenv(..., default)`
  fallback is dead code for that variable. If a CSS/JS change isn't
  showing up live, check `.env` first, not `config.py`.
  **Bump it every time `static/css/main.css` or a `static/js/*.js` file
  changes, in the same work session as the change** — not just "know
  the mechanism exists." Three commits in a row once touched `main.css`
  significantly (shared macros, template families, the Case Workspace
  grid rework) without the bump, because `.env` isn't git-tracked and
  so never shows up in the diff being reviewed at commit time — nothing
  about looking at `git status` after a CSS commit surfaces this on its
  own. Check it explicitly, as its own step, not something the commit
  workflow will remind you of.
- **The Werkzeug dev-server reloader can accumulate orphaned
  parent/child process chains** across repeated `python app.py` starts,
  and a stale process in that chain keeps serving a stale `.env`
  snapshot even after a "fresh-looking" restart. Use the `restart-app`
  skill instead of a bare `python app.py` restart — it kills the whole
  chain, not just the PID on the port, and verifies the new value is
  actually being served.
- Use the venv interpreter directly — `./venv/Scripts/python.exe ...`
  (Windows) — rather than a bare `python`/`py`, which may resolve to a
  different interpreter entirely.

## Testing

Full suite: `./venv/Scripts/python.exe -m pytest -q`. **Measured baseline,
2026-08-31, on the tree committed as `72a4a7d`..`9c2408f`: 6,004 collected / 4 deselected / 6,000 selected →
5,998 passed, 2 skipped, 1,951 subtests, in 25:28.** Quote all four numbers
rather than one "test count": collected, selected and passed differ here, and a
figure that silently means one of the others is how the previously-recorded
"approximately 4,964" drifted roughly a thousand tests out of date without
anyone noticing. Recent observed wall-clock runs include approximately 25:28,
26:49, 27:57, 43:35, 59:47, 77:42, and 2:44:54 - note 27:57 and 59:47 are the
SAME suite on the same machine hours apart, and 25:28 and 2:52:35 are likewise
the same suite on materially the same tree. Duration varies substantially with
the environment and is not a fixed service-level expectation. Treat pass/fail as
the assurance signal, not wall-clock time. An unusually long run is not
automatically evidence of a code regression.

**But it is not weather either — see the Watchdog Protocol below.** Those
figures predate both parallel execution and the discovery that much of that
spread had a diagnosable cause. A slow run is now a thing to investigate with
two commands, not to wait out.

**Never read the result through a pipe.** Redirect to a log file and capture
the exit code as its own line (`... > run.log 2>&1; echo "PYTEST_EXIT=$?" >>
run.log`). `pytest -q 2>&1 | tail -40` reports *tail's* exit status, not
pytest's, and a background-task notification saying "exit code 0" for the
wrapper is not evidence the suite passed - that combination once nearly landed a
commit on a fabricated pass (see `705aa2a`).

There is no CI here, so the full suite remains the gate for anything that
touches `routes/`, `services/`, `models.py`, `config.py`, `app.py`, or
migrations — unchanged — and for every deployment, accepted checkpoint, and
high-risk security/evidence/authorization change.

**Fast-path UI/markup changes no longer require it** (Product Owner,
2026-09-01). A change confined to `templates/`, `static/css/`, or `static/js/`
runs **Tier 0** (`./venv/Scripts/python.exe tools/tier0.py` — **52 files, 853
tests, 663 subtests, 23.6–30.2s over 5 runs**, measured 2026-09-05) plus the
targeted Lane A/B files for the surface being changed. See `TEST_LANES.md`.
The reason is arithmetic: a markup edit was costing between
27 minutes and 4 hours 35 minutes of gate for a result already understood, which
is a tax on iteration rather than a safety measure.

**Those counts are a dated observation, not a contract.** Tier 0's membership
is derived by rule on every run, so the lane grows on its own whenever a
source-scan test file is added — and a number written into prose then goes
stale in silence rather than failing. It already had: the 50 files / 803 tests
recorded on 2026-09-01 had drifted to 51 / 831 before this session added two
more. `tools/tier0.py --list` prints the current selection in a second;
re-measure rather than quoting this line if the number matters.

Two things this deliberately does not do. It does not touch the deploy gate —
nothing reaches the live host without a full run. And it does not pretend the
full suite was redundant on those changes: it twice caught defects no targeted
lane did, including a genuinely markup-shaped one (`test_mobile_submenu_repair_01`
failing `8 != 6`, where a new submenu used `workspace-menubar-panel` instead of
`workspace-menubar-subpanel` and would have been unreachable on a phone). The
trade being accepted is that such a defect is now caught at the deploy gate
rather than at the commit — later, but still before a user sees it. If that
proves wrong in practice, the honest fix is to widen Tier 0's membership or the
Lane B set, not to quietly restore the blanket gate.

If a CSS-only change breaks
`test_common_ui_elements_no_longer_reference_font_mono` or
`test_wordmark_is_the_only_space_grotesk_usage`, the fix is almost
always updating that test's own selector list, not reverting the CSS —
both tests assert against specific selector names, not against the
design intent.

**The test stores are cleared at session start, not torn down after.**
`tests/conftest.py`'s `pytest_sessionstart` empties
`instance/test_registry` and `instance/test_project_assets` before
collection. This is not tidiness: `TestingConfig` points those at fixed
paths (deliberately — `config.py` wants the artifacts inspectable after a
failure) and nothing ever emptied them, so every run's Projects
accumulated forever. `services/project_code.py` issues each Project a 3–4
character acronym and refuses to reuse one, and tests that ingest Projects
share a fixed name stem, so the space exhausts. It surfaced as 15 failures
across `test_write_collision_01.py` and `test_mobile_continuation_01.py`,
all `ProjectCodeError: Could not derive a unique project acronym` — in
features that had nothing to do with the accumulating state, only after
enough prior runs, reading exactly like a regression. One run leaves ~130
entries; it had reached 815. Clearing at the START rather than the end is
what keeps both properties: the last run's artifacts survive for as long
as you are looking at them, and no run inherits another's. Set
`ARCHIOSK_KEEP_TEST_REGISTRY=1` to preserve a previous run's store while
re-running a subset against it.

**Hermetic tests — spy on external calls, don't let them run for real.**
Any test path that can reach `ingest_upload`/`BHiveParser.parse` (or any
other call to the Anthropic API, SMTP, or external networking) must
replace that boundary with a deterministic spy/stub/fake, unless the
test is deliberately, explicitly written and named as a live external-
integration test. A CLAUDE-P31 test that skipped this once caused a
single background test run to take **8.5 hours** (a real, un-mocked
`ingest_upload` call hung against a live API in the sandbox). The
established pattern (see `tests/test_security_enforcement.py` or
`tests/test_project_access_control.py`'s own `_ingest` helpers):
`unittest.mock.patch.object(BHiveParser, "parse", fake_parse)` where
`fake_parse` returns a plain `ParsedDocument` directly, never calling
the real extract/classify/consistency-check pipeline. `config.py`'s
`ANTHROPIC_API_KEY` class attribute is fixed at first import, before
`app.py`'s own testing-mode env-clearing runs — do not assume
`create_app("testing")` alone makes a test hermetic against a real key
present in `.env`.

When testing the live app through a browser, **always start from the
sign-in page**, never mid-session — a stale session cookie can carry
state across a restart in a way that's easy to misread as a real bug.

## Test Suite & Execution Watchdog Protocol

Established 2026-09-05 by measurement, after a gate took 7 hours that should
have taken minutes. Every number below was observed on this machine, not
estimated.

### Baseline and execution modes

| Mode | Command | Baseline |
|---|---|---|
| **Parallel** | `pytest -q -n 8 --dist loadfile` | **~8 minutes** |
| Serial | `pytest -q` | **~2h 45m** |

Same result either way: 12 failed, 6,177 passed, 2 skipped, 2,573 subtests,
6,191 executed in both. A 20x difference in time and none in outcome.

**A gate run MUST state which mode it executed.** "The full suite passed" now
means two different things, and a reader cannot tell 8 minutes from 2h 45m from
the sentence alone.

`--dist loadfile` rather than bare `-n 8`: it keeps a file's tests on one
worker, which preserves the within-file state locality many `setUp` methods
assume. Parallel mode needs `pytest-xdist`, which is installed in the venv and
deliberately NOT in `requirements.txt` - that file ships to production and
pytest itself is not in it either. A fresh clone gets the serial path and is
correct, only slower.

### Pre-flight sweep - AUTOMATIC since `98b7e1a`

`tests/conftest.py`'s `pytest_configure` now detects and tree-kills orphaned
`app.py` chains before every run, on the controller only. **You no longer need
to remember the manual check** - it is the run's own first act, and it names
what it killed in the output. `ARCHIOSK_ALLOW_ORPHAN_APP=1` suppresses it.

It costs ~11ms on a clean machine. Two stages, because command lines are
expensive here: a ctypes `CreateToolhelp32Snapshot` (20.7ms, and the only
option that yields PARENT pids) finds any `python.exe` outside pytest's own
tree, and PowerShell CIM (943.5ms - `psutil` is absent and `wmic` no longer
exists on Windows 11 26200) confirms the command line ONLY when stage 1 found
something. Nothing is killed on stage 1 alone: "not ours" is equally true of a
Jupyter kernel. The allowlist is positive and total - `python.exe`, `app.py` in
the command line, rooted under `BASE_DIR`, no `pytest`, outside our tree - and
it targets the CHAIN ROOT, since killing a leaf leaves the reloader free to
spawn a replacement.

The manual check remains useful for diagnosing a run already in flight, which
the guard cannot help with because it only fires at startup:

```bash
tasklist //FI "IMAGENAME eq python.exe"
```

Orphaned `python app.py` / Werkzeug reloader chains starve the suite of I/O.
This is not hypothetical: a five-deep chain (`42236 -> 32964 -> 34144 -> 36296
-> 34412`), the oldest 47 hours old, was found mid-gate. Each restart had
nested a new child under the previous one - the accumulation this file's
Environment-quirks section already warns about, now with a measured cost.

Kill the whole chain from the TOP, which takes the descendants with it and
stops the reloader respawning a child:

```bash
taskkill //PID <oldest-pid> //T //F
```

Killing it mid-run recovered the suite immediately: **CPU 5.6% -> ~79%**, and
progress from roughly 10 percentage points per hour to 7 points in 4 minutes.
Roughly a 10x recovery, with the pytest process untouched because it sits under
a different parent. Under the standing live-only, no-localhost policy these
processes should not be running at all.

### Anomaly and degradation thresholds

- **Parallel (`-n 8`) anomaly threshold: 15 minutes.** Against an ~8 minute
  baseline, that is roughly 2x - past it, something is wrong.
- **Instantaneous CPU below 20% means I/O starvation or process contention,
  NOT slow code.** Cumulative average is misleading on a long run; compute the
  instantaneous rate as `delta-CPU-seconds / delta-wall-seconds`. The
  diagnostic run showed 5.6% cumulative while genuinely starved, and ~79%
  instantaneous the moment contention was cleared.

**Claude MUST NOT silently poll past these thresholds.** On crossing one,
immediately and without being asked:

1. dump the last 15 lines of the redirected log;
2. sample process telemetry - PID, elapsed, CPU seconds, computed CPU %, read
   and write bytes;
3. state plainly whether the run is advancing, starved, or hung, and alert.

Waiting quietly while a gate burns hours is the failure mode this exists to
prevent. A log that is still growing means slow, not hung - and those are
different problems with different answers.

### Benchmarking rule

**Any performance benchmark on this machine requires at least 5 runs per
side.** Windows filesystem variance is large enough that fewer is
indistinguishable from noise, and this was learned the expensive way: a
Defender-exclusion benchmark returned a 16.9% mean improvement that could not
be called, because the after-set's standard deviation was 11.88 against the
before-set's 2.23 and the distributions overlapped - the slowest after-run was
slower than the fastest before-run.

Report mean, median, min, max and standard deviation, and check distribution
SEPARATION rather than only comparing means. A percentage threshold set in
advance is only valid if the variance is comparable on both sides; when it is
not, separation is the test.

## Credentials given in chat

If given real credentials (FTP/SFTP/DB/etc.) for a one-off task: never
write them into any file inside this repository or any git-tracked
location. Use a transient file outside the repo (session scratchpad),
delete it immediately after use, and never echo the credential back in
a message.

## Synthetic test-project identity

An ARCHIOSK/GO test project built from real-world research material may
carry a deliberately **synthetic project identity** — a name that is not
the real-world project's. This is a Product Owner security/liability
decision, not a cosmetic one.

**A synthetic identity must never falsify provenance.** The separation is:

- **Real source material** — preserved as source evidence, with its real
  provenance intact.
- **ARCHIOSK test-project identity** — synthetic.

Concretely:

- The project's display/name identity may be synthetic.
- Original source names, document identifiers, and provenance stay
  truthful. Never rename, sanitize, or rewrite a source document to match
  a synthetic identity — that would make the evidence lie, and
  `governance/constitutional-invariants.md` #3 (provenance is mandatory)
  is what forbids it.
- Source evidence is never silently reclassified as synthetic evidence.
- Real owner/client/site/project identifiers do not become canonical
  test-project identity unless a test specifically requires one of them
  **as source evidence**.
- Do not persist a synthetic↔real mapping unless something actually needs
  it. An unnecessary mapping file recreates the exposure the synthetic
  identity was adopted to avoid.
- Durable ARCHIOSK test artifacts — reports, prompts, governance records —
  use the synthetic identity wherever the real identity is not needed for
  evidence provenance.

The current synthetic identity in use is **Project Smoke Detector (PSD)**
(`CLAUDE-PSD-FOUNDATION-01`, 2026-08-19).

The formal capability name is **Smoke Management Analysis (SMA)**. SMA is
the broader governed investigation of how smoke-related requirements,
conditions, systems, exceptions, thresholds, and project facts interact. It
may examine smoke control, HVAC operation or shutdown, smoke/fire dampers,
detection, fire alarm, compartmentation, egress and locking, detention or
staff-controlled operation, suppression, emergency power, Alternative
Solutions, and Code applicability. **Smoke Management Analysis is not a
Smoke Control System**: a Smoke Control System is only one possible engineered
subsystem or outcome considered by SMA. Preserve generic industry terms and
source/OBC wording verbatim; do not rename source evidence to match this
product capability name. **PSD is the synthetic test project/context; SMA is
the governed analysis capability being developed and tested using PSD.**

## Two different "confirm" vocabularies — don't mix them

`routes/workspace.py`'s Approval Gate (Apply, Issue RFI, adjudication,
etc. — see `_require_approval`) uses `confirm=once|session|no`. The
Delete-project flow uses a separate, unrelated `confirm=yes|no`. Passing
`confirm=yes` to an Approval-Gated route is not an error — it silently
no-ops and re-renders the confirm page. If a POST to a workspace action
returns 200 instead of the expected redirect, check which vocabulary the
route actually expects before assuming something else is broken.

## Color / visual changes

`static/css/main.css`'s own header comment is the source of truth for
the semantic color grammar — what each accent color is allowed to mean,
and why color is used rarely. Read it before changing any `--token`.
Verify contrast changes with real numbers (WCAG relative-luminance
contrast ratio), not by eye, and check the result against every
existing text/background pairing that uses the token you're changing,
not just the one you're focused on.

**Deep Ocean accepted visual baseline:** preserve the corrected,
blue-leaning Deep Ocean treatment. The
`CLAUDE-DEEP-OCEAN-HUE-CORRECTION-01` change from the older
`rgba(176, 255, 244, ...)` green/aqua direction to the newer
`rgba(176, 219, 255, ...)` direction is intentional and Product Owner
accepted; do not revert it unless the Product Owner explicitly changes
this constraint. `static/css/tokens.css` holds the canonical
`--ocean-*` values and correction rationale, and
`tests/test_appearance_simplify_01_global_theme.py` enforces parity at
required duplicate-use sites. This acceptance does not extend to the
Bauhaus/Constructivist experiment, which remains pending live visual
judgement after deployment.

## Recurring procedures — use the skill, don't re-derive it

- **`restart-app`** — clean-kill the whole dev-server reloader chain and
  start one fresh instance.
- **`rebuild-static-preview`** — rebuild and locally serve the static
  HTML preview (source lives in `tools/static_preview/`, output is
  git-ignored).
- **`verify-template-refactor`** — prove a `templates/`/CSS-class
  restructuring didn't change rendered output, via
  `tools/static_preview/diff_snapshot.py`. A passing test suite is not
  proof of this on its own — this codebase's tests check status codes
  and data, not markup geometry.

## Large, irreversible reasoning before acting

For architecture-level questions where no code change is wanted yet (a
route/root map, a build-vs-don't-build question, a purpose-alignment
review) — prefer Plan Mode over a long inline message: it produces an
explicit, approvable plan instead of relying on a "proceed" being read
correctly out of several paragraphs of prose. This does not apply once
the user has already authorized direct action for a described class of
work ("materialize what you think is appropriate," "keep moving") — at
that point the investigation and the action are the same authorized
step, and inserting a plan-approval pause fights the explicit
instruction rather than serving it.

## Investigating noisy problems

Prefer forking (the `Agent` tool with `subagent_type: "fork"`) for
open-ended diagnostic side-quests that generate a lot of throwaway tool
output — process-tree dumps, wide greps, log diffing, before/after
snapshot verification. It keeps that noise out of the main conversation
instead of filling context that then has to be compacted, which can
lose fidelity on whatever the user said right before the noisy
investigation started. The test is whether the work is self-contained
and independently verifiable (a fork can report "done, tests pass,
diffs clean" and that's genuinely sufficient) — if later steps in the
same turn need the specific file content just read to make further
judgment calls against it, keep it in the main thread instead of
forking and then immediately needing to re-read the same files.

## Multi-part requests

When a single message contains more than one distinct, sizeable piece
of work (e.g. "do X, then after that do Y"), use `TaskCreate`/`TaskUpdate`
to track each part rather than just working through them silently. It
costs nothing, gives the user visibility into which part is in
progress, and matches how this repository's own work has actually
arrived in practice — as large, multi-phase single messages, not one
request at a time.

## System of record and AI collaboration route

**Pushed `origin/main` is the authoritative durable system of record**
for source code, tests, schemas/migrations, this repository's own
governance corpus, continuation checkpoints, and accepted AI-assisted
work — for everything except the two carve-outs below. Operationally
this means: a local uncommitted change, an unpushed local commit, a
`TaskList` entry, or anything said in a conversation (this one,
another Claude Code session, or an external tool like ChatGPT) is
**provisional** — real only once it lands as a pushed commit. None of
those things are themselves citable as project truth; only what they
caused to be committed is. Don't treat "the AI said X" or "a prior
session concluded X" as fact — check the actual current repository
state.

Two things are legitimately authoritative but deliberately don't live
in git: **`.env`/secrets** (git-ignored by design — git records only
the variable *names* `.env.example` documents, never real values,
which live solely on the deploying host and the operator's own
credential storage), and **the sibling `archiosk-explorer` repo's own
governance corpus** (e.g. its ADR series — a different repository's
system of record, cross-referenced read-only via
`governance/history-mapping.md`, never duplicated here — see "Scope
boundary" above).

**Route for substantial work** (small fixes don't need all of this —
use judgment): intent → ground it in the actual repository (read the
real code/tests/git state before proposing anything, not memory or
assumption) → a plan, for anything large/irreversible enough to
warrant one (Plan Mode for pure-investigation stages; inline for
everything else) → self-critique the plan before implementing, not
after → implement as staged, individually-tested, individually-
committed increments (not one mega-commit) → run the relevant tests,
and the full suite whenever `routes/`, `services/`, `models.py`,
`config.py`, `app.py`, or migrations changed → inspect the actual diff
before committing → a commit message that states the objective, the
evidence, and what was preserved/hardened/replaced (this repository's
existing commit history is already the right model to follow — keep
writing them this way, don't invent a lighter or heavier convention)
→ push → update `CONTINUATION_CHECKPOINT.md` (or a `governance/`
document, if the conclusion is a ratified domain-model decision) at
real stage boundaries, not after every single commit — it becomes
noise otherwise.

**Where external AI collaborators (ChatGPT or otherwise) fit:**
freely, as a thinking surface, at the intent/investigation/plan/
critique stages — a second independent perspective is genuinely
useful there. Their output carries no authority on its own; it only
becomes real once someone (human or this agent) grounds it against
the actual repository and it lands in a commit. Don't paste
speculative external-AI output directly into governance docs or
commit messages as if it were already verified — verify it here
first, the same as any other proposal.

**Project North Star advancement cycles start from Spin findings.**
Approved as `CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01` — *"Codex
can do any advancement, but it must resolve the problems coming up in
Spins by Claude as a starting point."* The loop the record states is
`Claude Spin → mandatory issues surfaced → Codex resolves them first →
Codex advances North Star further → Claude Spins again`. Recorded here
because the rule was approved in the Prompt Depository and then never
became visible in day-to-day operating notes, so it stopped being
followed — a trajectory-continuity repair, not new doctrine; the
record remains the authority and is not restated beyond the line above.

Two limits are part of the rule, not caveats on it. **Spin findings
are the starting brief, not the ceiling** — once those are addressed,
broad repository-grounded advancement continues within whatever the
mission authorizes. And it **scopes to Project North Star advancement
cycles only** — a security fix, an authorization repair, a deployment,
a UI pass or any other bounded mission is governed by its own mission
and never blocks on a Spin.

`CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01` (the rename itself)
remains APPROVED and unexecuted, and that is currently correct: its own
text conditions it — *"After this Spin, ask Codex to rename the
project"* — and no such Spin review is on record. Do not treat the
lingering "North Bayview" references as drift to tidy up. Every one of
them in this repository is historical evidence of work that genuinely
happened under that name ("Confirmed live on North Bayview", "the North
Bayview specimen's own proof case is 80 rows across 5 sheets"), and
rewriting them would falsify provenance against constitutional
invariant #3. When the rename does happen it applies to the proving
project's *current* identity, not to the record of what was already
proven under the old one.

**No general provenance-tagging system beyond what already exists.** Commit
messages already carry authorship/reasoning/evidence for every
substantial change in this repo's history — that's sufficient
traceability at this project's current scale. The former deferral of prompt
IDs, agent-name headers, and acceptance records was lifted by explicit
Product Owner authorization for prospective prompt preservation. The bounded
exception is `governance/prompt-depository/PROMPT_REGISTER.md`; follow its
stable-ID, verbatim-text, lineage, and prompt/result-separation contract. Do
not create a parallel prompt register, migrate historical prompts without
separate authorization, or extend this exception into a general provenance
tagging system.

**Branches, PRs, issues, ADRs:** this repository's entire history is
direct commits to `main` — no feature branches, no PRs, no tags, no
`.github/` issue/PR conventions, no dedicated ADR directory of its
own. That's the right model at the current scale (effectively one
human plus AI agents, no second reviewer to route a PR to) — don't
introduce protected branches, mandatory PR review, or an issues
tracker merely because GitHub offers them; that's process weight with
no one on the other end of it yet. Revisit if a second human
contributor joins. Domain-model architecture decisions already have a
real, working ratification process — see
`governance/governance-of-governance/amendment-and-ratification.md` —
extend that discipline informally to infrastructure decisions too
(state what changed and why in the commit, don't silently overwrite
prior reasoning) rather than building a second, heavier mechanism for
the same purpose.

**Precedence when records disagree** (narrower than "governance always
wins" — `governance/constitutional-invariants.md`'s own declared
authority is scoped to the BEEHIVE domain-object model, not
infrastructure): for domain-model rules, `constitutional-invariants.md`
is highest, amendable only through its own ratification process — if
code contradicts it, the code is the defect. For domain-model feature
authorization, `governance/STATUS.md`'s table governs — code
implementing something marked NOT AUTHORIZED is a defect, not evidence
the table is outdated. For infrastructure/application/security
behavior (auth, SMTP, CSRF, rate limiting, deployment — everything
`constitutional-invariants.md` is silent on), current tested code on
pushed `main` is authoritative; `CONTINUATION_CHECKPOINT.md` summarizes
it but doesn't govern it, and if the two disagree the checkpoint is
stale, not the code. `MANIFEST.md` governs file layout only when
accurate — flag and fix drift when you find it (see `MANIFEST.md`'s
own note above), don't let it silently go stale.

**Deployed/external-provider state is evidence, never truth on its
own.** A third-party integration actually working (e.g. a real SMTP
provider accepting and delivering mail) is exactly the kind of thing
worth verifying live and recording the result of — but the verified
*result* belongs in a commit/checkpoint, and the live system itself
never becomes an alternate source of record. If a deployed
environment's behavior drifts from what's in the repository, that's
drift to reconcile back toward the repository (or a deliberate,
recorded exception), never something to silently treat as the new
truth.

**Exploratory/diagnostic scripts stay in the session scratchpad, not
the repo**, until something durable is actually proven — this
repository has never needed a "throwaway experiments" folder because
one-off diagnostics (a connectivity probe, a schema-diff check) belong
outside version control entirely unless they're becoming a permanent
tool.
