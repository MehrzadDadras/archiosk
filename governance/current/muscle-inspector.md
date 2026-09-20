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
