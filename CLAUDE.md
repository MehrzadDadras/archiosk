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

Full suite: `./venv/Scripts/python.exe -m pytest -q` (currently 1014
tests, ~3-4min, though duration has occasionally spiked much higher for
reasons unrelated to any specific code change — treat pass/fail as the
signal, not wall-clock time). There is no CI here — this is the only gate, so run it
before committing anything that touches `routes/`, `services/`, or
`templates/`. If a CSS-only change breaks
`test_common_ui_elements_no_longer_reference_font_mono` or
`test_wordmark_is_the_only_space_grotesk_usage`, the fix is almost
always updating that test's own selector list, not reverting the CSS —
both tests assert against specific selector names, not against the
design intent.

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
