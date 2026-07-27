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

Full suite: `./venv/Scripts/python.exe -m pytest -q` (currently 474
tests, ~45s). There is no CI here — this is the only gate, so run it
before committing anything that touches `routes/`, `services/`, or
`templates/`. If a CSS-only change breaks
`test_common_ui_elements_no_longer_reference_font_mono` or
`test_wordmark_is_the_only_space_grotesk_usage`, the fix is almost
always updating that test's own selector list, not reverting the CSS —
both tests assert against specific selector names, not against the
design intent.

When testing the live app through a browser, **always start from the
sign-in page**, never mid-session — a stale session cookie can carry
state across a restart in a way that's easy to misread as a real bug.

## Credentials given in chat

If given real credentials (FTP/SFTP/DB/etc.) for a one-off task: never
write them into any file inside this repository or any git-tracked
location. Use a transient file outside the repo (session scratchpad),
delete it immediately after use, and never echo the credential back in
a message.

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
