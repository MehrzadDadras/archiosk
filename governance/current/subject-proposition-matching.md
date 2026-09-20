# Source-anchored propositions and shared requirement matching

This increment extends CaseWorkspaceStore's Participant, Claim, Supersession,
DerivedObservation and AnalysisRun owners. It creates no investor database,
parallel graph, correction store or comparison engine. The persistence mapping
was recorded in investor-kernel-mapping.md before extending Claim.

The existing project/evaluation attention UI can register a subject reference and
record an individual typed interpretation linked to selected source evidence.
Each interpretation retains an exact source quote, source/page/region lineage,
source/evidence fingerprints, source class, declared temporal meaning and dates,
author, time, reason and runtime reference. A source quote anchors an
interpretation; it does not prove that the interpretation is correct. Source
classification is not authentication. Registering a subject does not verify it.

Corrections create successor Claims through existing supersession. The UI shows
before/after values without changing the original observation. Explicit human
review may adopt an interpretation or reject it through existing review owners.
Agent-originated classification remains agent-attributed. Neither classification
nor adoption establishes authority, binding, current mandate or canonical fit.
Re-evaluation remains a separate action. Evaluation provenance cannot be dropped.

The same normalized predicates compare requirements with candidate propositions
for construction, RFP, capital and asset contexts. Domain labels change only the
presentation vocabulary. Up to sixteen distinct criteria retain their individual
predicates, mandatory/optional designation, candidate identity and source
premises. Missing candidates remain unresolved. Mandatory non-matches dominate
all successes; numeric score overrides are not accepted. Scope, units,
vocabulary, viewpoint basis and qualifiers are never silently reconciled.

Temporal inspection requires an explicit query date, declared interval and the
required candidate temporal meaning. Historical activity, recent commitment and
current disclosed mandate are distinct. An absent end date grants no inferred
continuing validity. Even interval containment is only a declared premise.

The persisted result distinguishes conditional model FIT/MATCH from governed
factual UNRESOLVED. No approved investor profile, actual current mandate or
complete requirement inventory is inferred. Each run retains all used claims,
admissions and temporal checks, and lists scoped claims left outside selection.
The UI renders this committed result and flags subsequently changed, rejected
or superseded premises. Reload does not recompute the result or change evidence.

Entry: an existing project's kernel mapping -> Governed attention, or the
existing Survey Evaluation case -> attention. Set attention, add a subject and
source-backed propositions, then use Requirement matching. Results link to the
existing muscle inspector. No live investor information is seeded by tests.

Focused qualification: test_subject_propositions.py,
test_requirement_matching.py, test_normalized_comparison.py, existing MM7/MM8 and
muscle-inspector suites. Browser qualification:
tools/verify_source_review_ui.py --propositions exercises actual Flask forms,
source jumps, immutable correction, explicit local human-review fixtures,
conditional matching, runtime invocation and read-only Reload. Automated live
verification never attests human review.

This increment does not complete investor discovery, verified proposition
promotion, capital composition, investor acceptance games or the Capital
Alignment Brief. Those remain programme work. It must not be advertised as a
completed investment service.
