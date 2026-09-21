# Work plans, capital coverage and transaction history: owner mapping

The consolidated Product Owner directive continues the existing programme.
Intermediate UI is execution proof, not a Product Owner approval stop.
This mapping precedes durable additions; it does not assert their implementation.

| Proposed capability | Classification | Existing owner / extension boundary |
| --- | --- | --- |
| Intended investigation procedure | EXTEND_EXISTING | InvestigationStep already represents planned/skipped/executed work, anchors, evidence categories, branches and an AnalysisRun reference. Add a typed optional plan payload here. |
| Plan revision and execution history | EXTEND_EXISTING | Append InvestigationSteps linked to the originating step; preserve prior intent. Plan records never enter proposition admission. |
| Actual result and completion proof | EXISTING_EQUIVALENT | AnalysisRun persists results; runtime_observation retains invocation/consumer/surfacing records. Qualification must reference actual tests, not a configured boolean or a plan's assertion. |
| Report compression | EXISTING_EQUIVALENT | CaseWorkspaceStore.project_attention_report and work_product_export.compress_presentation_records; a read-only projection over original records. |
| Hard, soft, unknown and compositional requirements | EXTEND_EXISTING | Existing Requirement/Claim and typed matching predicates. Explicit requirement policy supplements the existing mandatory flag without treating missing evidence as partial coverage. |
| Coverage assignments and compatibility | EXTEND_EXISTING | Existing AnalysisRun.governed_result, cross_modal_investigation and quantitative predicates. Positive coverage, additive basis and partnership compatibility require separate evidenced premises. |
| Minimum sufficient configurations | EXTEND_EXISTING | Existing cover_requirements and role composition; preserve all equally minimal solutions, exclusions and failed smaller configurations. |
| Participant / project identity | EXISTING_EQUIVALENT | Participant, project/source identity, source-anchored Claims and reviewed Relationships. Parent-child links do not substitute legal entities. |
| Transaction identity and event propositions | EXTEND_EXISTING | Source-anchored Claims represent independently reviewable identity/event assertions; existing relationship endpoints connect them. Do not force transactions into Participant records or mistake an investigative Case for transaction identity. |
| Event occurrence, discovery and review | EXTEND_EXISTING | Extend the existing Claim proposition envelope with typed event metadata. Server-recorded creation time remains distinct from event occurrence and discovery. |
| Maturity and current lifecycle | EXTEND_EXISTING | Governed projection over independently admitted event Claims and existing temporal/currentness/supersession services; retained AnalysisRuns expose actual executions. Historical maturity is never overwritten by lifecycle changes. |
| Scoped replacement / refinancing | EXTEND_EXISTING | Existing Relationships and Supersessions over explicitly identified component propositions. Do not supersede an entire transaction identity for a component-only change. |
| Human verification / promotion | EXTEND_EXISTING | Existing explicit-attribution review/adoption/validation owners. Text correction, categorization, source class and matching success cannot silently become transaction authority. |
| Operational transition records | EXTEND_EXISTING | Persist the underlying governed proposition/transition first in the workspace, then append existing governance/runtime records. Audit traces do not become transaction truth. |
| Capital / transaction database or graph | DO_NOT_CREATE | Existing workspace persistence and relationship owners remain the sole path. |
| New independent durable primitive | NEW_PRIMITIVE_REQUIRED: none established | Reassess only if a concrete requirement cannot be represented honestly by the mapped owners. |

Unknown mandatory premises block complete coverage. A hard conflict requires
positive incompatible evidence. Optional/soft matches cannot repair a mandatory
failure. Partial contributions are additive only under an established combination
basis; arithmetic does not establish partnership structure or commitments.

Transaction identity, participant roles, project phase, event dimension, authority
and overlapping temporal applicability precede current confirmation. A debt
facility, MOU, related project or historical collaboration cannot establish an
equity JV. Occurrence time orders events; discovery time does not reverse history.
Supersession, termination, failed conditions, suspension and reinstatement retain
their different meanings and the unaffected component scopes.

Raw-source admission currently returns reference-level qualification. The new
transaction work must earn any stronger scoped state through explicit admissible
evidence and the existing review owners. This mapping does not grant that state.

## Transaction extension under qualification

`Claim.event_proposition` retains a typed source interpretation, exact quote,
source/evidence fingerprints, project/party/transaction scope, occurrence and
discovery dates, and explicit dependency references. Its existence confers no
event authority. `ReviewerValidation.proposition_review` records separate human
checks for reading, binding, applicability, authenticity and event authority.
The existing Finding Disposition and Apply remain separate. Evaluation Claims
cannot enter canonical Apply. Raw-source, geometry and IFC admission are unchanged.

`resolve_transaction_identity` and `investigate_transaction_history` extend
`cross_modal_investigation`. The workspace persists their output as an ordinary
AnalysisRun; GET inspection only reads that result and detects changed premises.
Missing current applicability does not erase historical maturity. Explicit
corrections, waivers and successor links retain predecessor Claims. Financing
relationships remain distinct from equity and partnership confirmation.

The real attention dispatcher exposes transaction source entry and review,
declares its existing Governed Work Plan, and renders the retained result using
the existing report projection. Scoped human verification is exposed through the
existing Finding validation form; it does not implicitly Apply anything.
Controlled transaction games use the existing Survey Evaluation registry and
EVALUATION_INPUT source boundary. They never fabricate human reviews.

Qualification includes `test_transaction_propositions`,
`test_scoped_proposition_review`, `test_transaction_identity`,
`test_transaction_history`, `test_transaction_scoped_lifecycle`, and
`test_transaction_review_surface`. The existing browser verifier's
`--transaction-games` mode exercises actual forms, invocation and read-only Reload.
Local browser proof is not authenticated production proof. Component configuration
amendments and the remaining programme work must be qualified before claiming
complete master-directive coverage.

Presentation formats are EXTEND_EXISTING: WorkProduct sections and their cited
evidence remain the content owner. PDF reuses document_export; PowerPoint and
standalone web output extend work_product_export. No new durable abstraction or
generated narrative is introduced. Export preserves draft state, qualifications,
complete retained content and citation identifiers. Format conversion cannot
assert currentness or replace explicit re-evaluation of changed premises.

Verified requirement scope is EXTEND_EXISTING: a source-anchored, reviewed
structured Claim may declare a `complete_requirement_inventory` (TOKEN_SET,
vocabulary `requirement_claims`, values are the explicitly bound requirement
Claim identities). Separate `requirement_policy` Claims use vocabulary
`requirement:<claim-id>` and identify obligation and comparison operator.
These remain ordinary Claims with original source quotes and the existing
scoped ReviewerValidation / Disposition / Apply chain. A form checkbox is not
the governing policy. Missing inventory, ambiguous policy, unknown mandatory
premises or unreviewed candidate facts cannot earn factual fit. Inventory
requirements outside attention remain visible dependencies. The same normalized
comparison owner handles conditional and admitted inputs; no second matcher.

Reviewed composition is EXTEND_EXISTING: the same retained matching runs feed
`evaluate_requirement_coverage` and `cover_requirements`. Source policies may
declare `DIVISIBLE` only for numeric quantities. Combining partial quantities
requires an admitted, current `additive_capacity_basis` Claim naming the
participating subjects and exact property/unit/scope. Absence of that premise
leaves collective coverage unresolved. No source record is rewritten.

Partnership requirements are EXISTING_EQUIVALENT structured Claims. A
`complete_partnership_inventory` uses the same requirement-Claim vocabulary and
source-policy admission, with qualifiers naming the exact participant subjects.
One retained, current reviewed matching run per party must positively satisfy
every blocking dimension for that configuration. Complete capability coverage
does not substitute for this evidence. Neither result establishes commitment,
transaction identity, an actual JV, or financial close.

The existing composition UI selects the reviewed procedure and retained
partnership executions. Its result-first matrix renders persisted assignments,
all minimum capability sets, and failed smaller configurations. Selecting all
candidates is a separate configuration from a sufficient subset; the retained
selected-configuration result remains inspectable. Source changes flag historical
results for explicit re-evaluation. Reload and report filters are observational.
Tests: `test_reviewed_composition.py`; actual browser negative admission:
`tools/verify_source_review_ui.py --propositions`. Automated production verification
does not manufacture the human attestations needed for positive factual coverage.

Interpretation review and proposition root tracing are EXTEND_EXISTING: structured
Claims, confirmed dependencies, scoped admission, normalized comparison and the
existing professional AnalysisRun remain the owners. No durable primitive is added.
The same bounded root tracer accepts a Claim target and stops on missing authority,
scope change, ambiguity or a broken chain before returning to the target.
Wording is compared independently from the declared typed meaning. A separately
reviewed `interpretation_change_authorization` Claim uses vocabulary
`claim_transition:<upstream-claim-id>`, a single target Claim ID as its token value,
and one qualifier, `AUTHORIZED` or
`PROHIBITED`. Source scope, authority and temporal applicability must be admitted.
Direction is part of the reviewed premise: permission cannot be reused in reverse.
Absent authorization remains unresolved; it is never fabricated from silence.
The professional UI and retained presentation consume these committed results.
The existing tracer can stop at an explicitly requested controlling proposition
across multiple confirmed dependencies. Every intermediate scope and admission
is checked; unrelated branches are not traversed after sufficient premises are
obtained. Historical presentation sections remain immutable when new governing
evidence arrives. The existing export-status projection then exposes
REVIEW_REQUIRED from the original analysis's retained premise fingerprints.

Representation redundancy is EXTEND_EXISTING: professional coverage calls the
existing necessity and normalized-comparison owners. A normal reviewed Claim
may attest `complete_representation_inventory`, with TOKEN_SET values naming
the scoped proposition Claims and vocabulary `representation:<evidence-id>`.
Both inventories must close the same subject, scope, coverage and qualification;
each member must be anchored solely to its addressed representation, current,
and admitted through ReviewerValidation / Disposition / Apply. Ambiguous,
unreviewed, stale or incomplete inventories remain unresolved. An inventory is
not an authority shortcut: every member must independently pass admission.
Typed agreement earns only scoped REDUNDANT_CONSISTENT, and an admitted positive
value conflict earns REDUNDANT_CONFLICTING. Neither authorizes deletion. Shared
coverage alone still proves neither equivalence nor physical performance.
All inventory/member evidence remains recoverable in the retained professional
result, including dependencies outside attention. At most 32 representations
are compared per review; larger scopes explicitly request narrowing.
