# Source-anchored normalized comparison

The existing attention UI invokes CaseWorkspaceStore.run_information_comparison,
cross_modal_investigation.compare_normalized_information and the quantitative
owner's shared scalar predicate. Results remain ordinary AnalysisRun records.
The existing Participant identity can now be referenced by the existing evidence
graph, consistent with its Entity role in the kernel mapping. Identity does not
establish a company capability or any other proposition.

The bounded comparison accepts declared scalar or vocabulary-set hypotheses.
Both premises retain subject, scope, property, evidence references, qualifiers,
viewpoint basis and reason. Matching units/vocabularies are mandatory; no unit
conversion, synonym mapping, prose interpretation or identity equivalence is
inferred. Different qualifiers return PARTIAL. Missing viewpoint or qualifiers
remain UNRESOLVED. Incompatible scopes remain INCOMPARABLE.

Retained view references must belong to the referenced source. Original bytes
must still match the recorded source hash, and the derived artifact must pass
the existing view reader. Results expose the transform metadata and evidence
fingerprints. A transformed view never grants factual consistency or authority.

All entered normalizations are EVALUATION_INPUT, including those referencing a
real project. Conditional MATCH/NON_MATCH is a model predicate; factual consistency
remains UNRESOLVED. No new reading, source, canonical relationship or evidence is
created. Existing admission/currentness results accompany the persisted analysis.
Archived cases, foreign subjects and missing evidence cannot run this action.

This is a reusable comparison foundation, not completed semantic interpretation
drift, automated RFP fit, canonical proposition admission or engineering validation.
Those capabilities still require their actual governed premises and consumers.

Tests: tests/test_normalized_comparison.py, tests/test_constraint_probing.py and
tests/test_kernel_mapping.py. tools/verify_source_review_ui.py exercises the real
form using a retained mirrored view, asserts owner invocation and checks that
Reload leaves persisted bytes unchanged. Live authentication continues to require
an existing human-issued verification URL; no agent-created credentials are used.
