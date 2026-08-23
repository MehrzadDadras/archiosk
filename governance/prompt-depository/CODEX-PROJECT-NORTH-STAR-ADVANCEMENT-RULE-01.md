# CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01 — Project North Star — Spin-Led Advancement Rule

| Field | Value |
|---|---|
| Prompt ID | CODEX-PROJECT-NORTH-STAR-ADVANCEMENT-RULE-01 |
| Title | Project North Star — Spin-Led Advancement Rule |
| Agent | Codex |
| Status | APPROVED |
| Purpose | Govern each Project North Star advancement cycle through a Spin-led starting brief while retaining bounded, repository-grounded advancement authority. |
| Product Owner acceptance | Explicitly approved by the Product Owner in the preserved direction below. |
| Lineage | Project North Star advancement governance. No existing authoritative Project North Star programme record was found to link during this preservation operation. |
| Superseded by | None |
| Absorbed into | None |

## Governing interpretation

- Claude's latest Spin findings are the mandatory starting design brief for each Project North Star advancement cycle.
- Codex must begin by addressing the problems, gaps, contradictions, weaknesses, or proving-project deficiencies surfaced by that Spin.
- Those findings are not the outer limit of Codex's authority.
- After resolving the Spin-surfaced issues, Codex may make additional repository-grounded improvements that strengthen Project North Star as ARCHIOSK/GO's canonical proving project/template.
- The intended development loop is: `Claude Spin → mandatory issues surfaced → Codex resolves them first → Codex advances North Star further → Claude Spins again`.
- This authority does not permit tuning Project North Star to known oracle answers or compromising blind-testing protections.

## Exact prompt text

```text
Codex can do any advancement, but it must resolve the problems coming up in Spins by Claude as a starting point.
```

## Execution references

**Status stays `APPROVED`, deliberately.** This is a standing rule governing
*every* Project North Star advancement cycle, not a one-time instruction that is
now spent. What follows records that its first cycle has been demonstrated — the
same shape [`GO-RFP-PUBLICATION-BARRIER-01`](GO-RFP-PUBLICATION-BARRIER-01.md)
already uses for a standing direction with real execution behind it. Contrast
[`CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01`](CODEX-NORTH-BAYVIEW-TO-PROJECT-NORTH-STAR-01.md),
which moved to `RUN` because that transition happens once and has happened.

- Run: First governed cycle, 2026-08-22 → 2026-08-23. Claude produced and froze
  the relevant Spin (run `630beea5-911f-456e-b91a-fd3ea43ea1ef`, 9 sources, 9
  findings, 6 Helix assessments, oracle unopened). The Product Owner reviewed it
  and accepted it as **READY WITH EXCLUSIONS** — most of its content being project
  conditions in the corpus, which the review explicitly barred from becoming Codex
  requirements.
- Result: The review found exactly one genuine GO weakness the Spin itself
  evidenced — a Spin run persisted no timing, so Spin degradation was invisible
  from its own history. Codex addressed that Spin-derived item **first**, adding
  `started_at`, `completed_at` and `duration_ms` with legacy compatibility and no
  effect on evidence, Helix, findings, authority or cognition. Claude deployed the
  exact certified commit and live-verified persistence on a real run:
  `duration_ms = 101106` (101.1s). Only after that starting item was addressed did
  broader bounded advancement authority apply.

  The loop this record specifies therefore ran end to end as written:
  `Claude Spin → mandatory issues surfaced → Codex resolves them first → Codex
  advances North Star further → Claude Spins again`.

  One residual is recorded honestly rather than smoothed over: the timing fields
  persist, but the Spin history surface still renders the older "start time and
  duration are not separately recorded" text. Storage delivered; display not yet
  updated.
- Commit: `7e80c57992317f3167f5e9761da1d764e917bc1a` (Persist Spin execution
  timing), deployed to production 2026-08-23. Its prerequisite — the Spin timeout
  repair that made a completed Spin possible at all — is `cefcf61`.
