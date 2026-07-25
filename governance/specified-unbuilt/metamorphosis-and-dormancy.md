# Specified But Unbuilt — Authoritative Project Metamorphosis

**Status:** Specified, not implemented. **Confirmed conclusion, demonstrated not asserted: no dedicated Change/Metamorphosis object is needed.**

Pipeline: Prior Governed State → new authoritative input (RFI response, addendum, revised drawing, directive) → preserve prior state → identify the delta → determine impacted Requirements/Findings/Relationships → supersede/reopen/revalidate/preserve as appropriate → new governed state → impact report. Tested piece-by-piece against the existing kernel:

- **Preserve prior state:** `Snapshot` — sufficient, unchanged.
- **Record the new authoritative input:** `register_source_revision`/`Supersession` — already exactly this mechanism.
- **Identify the delta:** `AnalysisRun`/`AnalysisTrigger` — and the concrete finding worth restating precisely: `ANALYSIS_TRIGGER_SOURCE_CHANGE` **already exists in the trigger vocabulary**, unused for this exact purpose until now. No new object needed.
- **Determine impact:** `Relationship`'s existing `affects`/`depends_on`/`blocks` types — *if* those dependency links were actually recorded beforehand. Honest, named limitation: this is a discipline gap (was the dependency ever recorded), not a structural one — the mechanism doesn't guarantee completeness, only traceability where discipline was followed.
- **Flag for re-review:** the one genuinely small gap — a new `needs_revalidation` value on `Requirement.status`, the only net-new vocabulary this pipeline requires.
- **Impact report:** a query/view assembled from the above, not a stored object.

## Restart as a special case of metamorphosis

Restart (from Suspend/Defer) is architecturally just this same pipeline, triggered by elapsed dormant time rather than a specific new document — every Requirement/assumption active as of suspension gets flagged `needs_revalidation`, propagated through recorded dependencies, with unaffected items preserved only where continuing applicability can actually be demonstrated. See `scenario-and-viability.md` for the full dormancy/restart treatment and the decided targeted-revalidation-over-global-reverification recommendation.
