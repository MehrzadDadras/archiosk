# Golden Laboratory Suite — continuation checkpoint (CLAUDE-P25 / P26)

Concise handoff for a future session picking up the self-test regression
lab (`tests/self_test/`, `tools/self_test_*.py`) after CLAUDE-P25 and
CLAUDE-P26. Not governance — this covers the regression/reliability
testing infrastructure and its two most recent production fixes to
`services/bhive_parser.py`'s consistency check. Full narrative detail is
in the commit messages themselves; this is the fast-resume version.

Both commits below are on `main` and pushed to `origin/main`
(`https://github.com/MehrzadDadras/archiosk.git`) — confirmed both
resolve to `833187c` as of this checkpoint.

## CLAUDE-P25 — commit `686eaa2`

**Problem:** the consistency investigator could focus on differing
numeric thresholds while failing to credit explicit temporal/
operational/spatial/conditional scope stated *within* the same two
clauses. Root cause isolated to **clause density** (a long clause
bundling a numeric obligation with a protocol/condition description),
not any one scope dimension — confirmed by a 13th "dense" specimen built
in a different domain than the failing real candidate.

**Fix:** `ConsistencyFlag` gained `requirement_a/b_obligation`,
`requirement_a/b_scope`, `scopes_overlap`, `scope_reconciliation_
reasoning`. Prompt requires an explicit 4-step scope check before
including any pair. `_check_consistency` deterministically drops any
flag lacking scope reasoning or whose own `scopes_overlap=False`
contradicts inclusion.

**Results:** 38/39 on the full scope-reconciliation matrix post-fix
(1 skip, not a wrong answer); Golden Suite 30/31 clean (1 transient
model-call error, unrelated); full pytest 706 passed.

## CLAUDE-P26 — commit `833187c`

**Problem:** P25's real recheck runs showed ~50% malformed output on the
*isolated two-clause* condition specifically — a valid JSON array,
self-correction prose ("wait, let me reconsider"), sometimes a second,
differing JSON array. Strict `json.loads` discarded these outright even
when a good answer was present.

**Investigated and rejected:** Anthropic tool-use (schema-enforced
structured output). Fixed formatting 100%, but on the one genuinely hard
specimen tested (a real dense conflict) it got the answer wrong 3/6
times — each miss a bare ~33-token `{"flags": []}` vs. ~700–800 tokens of
real reasoning in every correct run. Forced structured output let the
model skip its own reasoning in half the hard-case runs. Temperature=0
showed no measurable difference from default.

**Fix (parsing only, no new model-call shape, no second semantic
pass):** `services/consistency_response_parser.py` classifies a raw
response into 7 categories (single valid JSON / valid JSON + harmless
prose / multiple equivalent blocks / multiple **conflicting** blocks /
malformed-but-repairable / unusable / transport failure). The first four
are accepted immediately. Only a genuinely unresolvable response
triggers exactly **one** bounded retry of the identical request before
falling back to the prior graceful skip. Provenance (both raw
responses, retry flag, category) preserved via the existing
`usage_sink` channel.

**Results:** real rerun of the exact previously-failing condition
(aquatic-centre isolated clean pair) — **6/6 valid, all correctly
clean** (2 of those recovered via the bounded retry). Full pytest 730
passed. Golden Suite fully clean: 0 malformed, 0 false positives, 0
did-not-run.

## Quarantined candidate: `276cac42` (aquatic-centre)

Status **unchanged: still quarantined, not promoted.** Its clean
baseline has improved across both P25 and P26 (isolated-pair false
positives went from 7/10 in P24 → 0/8 after P25 → 6/6 correctly clean
after P26's retry fix), but per explicit standing instruction this is
**not** grounds for promotion on its own — it may only be reconsidered
if production capability improves for reasons *broader* than admitting
this one specimen. No admission review has been reopened.

## Remaining backlog

**Task #8 — "Backlog: wire remaining unwired CaseWorkspaceStore
subsystems"** — pending, **not started**, explicitly not started as
part of this checkpoint.

## Recommended next work (not started)

1. If a future session wants to keep improving the consistency
   investigator's reliability rather than pivot to task #8: no known
   open defect remains in this area — P25 and P26 both closed with
   clean regression runs. The next natural investigation, if any signal
   emerges, would be watching real production `usage_sink` telemetry
   (`response_category`, `retried`) over time to see whether the P26
   retry path fires more than the near-zero rate seen so far.
2. Otherwise, task #8 (`CaseWorkspaceStore` backlog) is the queued next
   substantive piece of work — see `governance/current/kernel-object-
   model.md` and `governance/STATUS.md` for what's implemented vs.
   authorized before starting it.
