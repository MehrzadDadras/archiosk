# Experiment Reporting Corrections — Errata for `reconstruction_002.json`

**This is an errata note, not a rewrite.** Per the standing instruction not to rewrite any frozen experiment artifact, `reconstruction_002.json`, `snapshot_002.json`, and every other file already committed under `snapshot_002/` remain exactly as originally produced. Nothing there has been edited. This file documents two confirmed **report-layer** defects found by Adversarial Review 002 (and, for the second, independently by this session's own pre-review self-audit), corrected here in an additive, non-destructive way — the same philosophy this codebase already uses everywhere else for corrections (Supersession, ThreadResolution) rather than silent overwrites.

Both defects are bugs in `ingest_nreocrc_lab_002.py`'s own **summary/diagnostic computation** — not in the actual governed data it produced (the real `ProjectWorkspace`/`Snapshot 002` content), and not in any Batch F/G/H production code.

## Defect 1 — Requirement count off-by-one (58 reported vs. 59 actually frozen)

`reconstruction_002.json`'s `requirement_extraction_test.total_requirements_registered` reads **58**, computed as `len(bracket_clauses) + len(manual_unlabeled)` (56 + 2) at the point in the script where that summary field was written — before the Appendix OPR-1 Row 20 boundary-detection requirement (registered later, in Step 6) was added.

**Corrected value: 59** — independently confirmed by counting `snapshot_002.json`'s `reference_lists.requirements` array (59 entries) and the underlying workspace's `requirements` list (59 entries) directly. The real, governed Requirement count has always been 59; only the diagnostic summary field undercounted it by one.

## Defect 2 — Expected-Information row-3 internal contradiction

`reconstruction_002.json`'s `expected_information_shadow_rerun.rows` entry for the Functional Program (`document_id: "Appendix OPR-1 (this document)"`) is labeled `generic_bucket: "ALREADY OBSERVED (present in this corpus)"`, while the same row's `raw_evaluator_outcome` reads `"expected_not_found"` — a direct contradiction for the same row.

**Root cause, confirmed:** the script's observed-evidence matcher (`ingest_nreocrc_lab_002.py`, Step 9) only treated a row as "observed" when its `document_id` cell matched the literal string `"NREOCRC-OPR-001"` exactly:

```python
observed = [{"object_type": "source", ...}] if row[docid_col].strip() == "NREOCRC-OPR-001" else []
```

The Functional Program's own row reads `document_id = "Appendix OPR-1 (this document)"` — a different string naming the same underlying Source — so it fell through to `observed = []`, and `evaluate_information_sufficiency` correctly (and honestly) returned `expected_not_found` for the evidence it was actually given, even though the document is, in fact, present.

**Correction:** this is a matching-heuristic bug in the lab script, not a defect in `evaluate_information_sufficiency` itself (Batch E production code) — the evaluator did exactly what its inputs told it to do. The corrected reading for that row is: `raw_evaluator_outcome` **should have been** `expected_and_found` (or, given the Functional Program's specific embedded-TBC caveats already known from Adversarial Review 001 §7, arguably `found_but_insufficient_for_stage` — a judgment call outside this errata's scope). The `generic_bucket` label ("ALREADY OBSERVED") was and remains the correct reading of the row.

## Scope note

Both corrections concern **this experiment's own reporting/diagnostic layer only**. Neither implies any change to:
- Batch F (`Source`/`Requirement`), Batch G (`Snapshot`), or Batch H (`.md`/table extraction) production code — all unaffected, unchanged.
- The frozen `snapshot_002.json` record — its `reference_lists.requirements` count was always 59; there was nothing to fix there.
- `devils_advocate_review_002.md`, `snapshot_comparison_001_vs_002.md`, or `adversarial_comparison_001_vs_002.md` — all remain exactly as originally produced.

No production code was touched to produce this errata. Foundation Batch J's architecture (Structured Tabular Evidence, generic Source-Reference resolution) is a separate, forward-looking change and is not a fix for either defect above — see `Batch J`'s own completion report for that work.
