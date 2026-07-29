# Continuation checkpoint

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
