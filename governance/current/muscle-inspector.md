# Recorded muscle execution inspector

The existing capability registry describes nineteen instrumented owners with
inputs, outputs, allowed transitions, refusal/qualification states, provenance
requirements, authority rules and runtime hooks. Registration does not establish
invocation or assert completion of every master-programme muscle.

The existing runtime observation owner projects actual recorded events against
these contracts. It never calls a domain resolver, scores success or changes a
governed state. INVOKED requires a recorded invocation; an isolated return or a
catalogue entry is NOT_OBSERVED. Truncated traces stay explicitly incomplete.
Consumer/surfaced events are shown at request level, without inventing causal
success for every muscle. Repeated calls remain in their recorded sequence.

AnalysisRun retains an optional operational trace ID when record_analysis runs
inside observation. This is a link, not evidence. The authoritative analysis is
still committed before the request trace is emitted/retained. A missing trace
does not invalidate or recreate the analysis; the direct trace URL returns 404.
Old/unobserved executions truthfully have no invocation link. No migration or
separate execution store is introduced.

The attention UI links its persisted executions to the existing Survey
Evaluation request inspector. Admin and Developer Mode restrictions remain.
The inspector shows contracts, actual input/result events, returned state,
refusal/error and request consumer output. Reload reads stored records only.
Retired disposable-case traces remain suppressed by the existing lifecycle owner.

Focused tests: tests/test_muscle_inspector.py checks real instrumented owners,
actual Flask invocation, persistence/trace links, absent observations, invalid
and retired trace URLs and read-only inspection. Existing review/game and Survey
tests cover the affected shared AnalysisRun path. Browser qualification uses
tools/verify_source_review_ui.py and follows the real execution link.

The broader programme remains incomplete: this inspector does not manufacture
semantic drift, binding, engineering validation or cross-domain business results
for muscles that have not produced them.

Cross-domain operational exposure is EXTEND_EXISTING. The same Survey Evaluation
page selects up to eight retained evaluation runs and reads their AnalysisRuns
and runtime_observation muscle projections. It performs no comparison or matching
again. Every displayed invocation comes from an actual recorded owner event.
Unavailable/truncated traces stay explicit; a catalogue entry never supplies proof.
Counts are request-level when several analyses share a trace, not invented
per-analysis call counts. The real result/evidence and exact trace remain linked.

Construction assembly layers, RFP discipline capability, capital requirements and
asset control-function cases supply distinct typed EVALUATION_INPUT premises to
the same existing matching path. Their computed predicates do not establish
physical adequacy, verified capability, mandate or factual fit. They do not
promote fixtures into project authority. Tests: test_cross_domain_runtime.py;
actual browser: tools/verify_source_review_ui.py --cross-domain. Reload retains
selections and does not mutate either evaluation or normal workspace records.
