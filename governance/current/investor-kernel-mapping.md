# Investor intelligence: existing-owner mapping

This mapping precedes persistence changes. It records reuse decisions, not a
claim that the investment programme has been completed.

| Requirement | Classification | Existing owner and bounded extension |
| --- | --- | --- |
| Investor, vehicle, partner identity | EXISTING_EQUIVALENT | case_workspace.Participant; a project-scoped identity is not a verified profile |
| Original disclosure, page/region, extracted observation | EXISTING_EQUIVALENT | Source, StructuralUnit, AddressableRegion, EvidenceItem; retain bytes/hash and extraction origin |
| Individual mandate/capability assertion | EXTEND_EXISTING | Claim with an optional structured proposition; never a synthetic profile truth |
| Original extraction and categorization correction | EXISTING_EQUIVALENT | Claim and supersede_claim; successor preserves original, evidence links and review history |
| Parent/child, mandate, provenance and analytical links | EXTEND_EXISTING | Existing Relationship endpoints and analytical_scope; no second graph |
| Authority and currentness | EXTEND_EXISTING | Existing claim status, source currentness, proposition admission and review owners; unsuperseded does not mean a current mandate |
| Human disposition | EXISTING_EQUIVALENT | Existing claim adoption/rejection, ReviewerValidation/Disposition and promotion gates; attribution is distinct from actor identity |
| Matching | EXTEND_EXISTING | cross_modal_investigation normalized comparison and quantitative scalar predicates; mandatory failures cannot be averaged away |
| Multi-entity composition | EXTEND_EXISTING | Existing coverage/set-selection mechanism, with explicit role/applicability and compatibility premises |
| Operational results and trace | EXISTING_EQUIVALENT | AnalysisRun, runtime_observation and existing attention/GO Games surfaces |
| Commercial brief and presentations | EXTEND_EXISTING | WorkProduct/WorkProductSection and work_product_export render committed analysis |
| Discovery and candidate ingestion | EXTEND_EXISTING | external_research / External Intelligence Airlock and ingestion; current reference allowlist is not an investor catalogue |
| Investor-specific database, graph, authority or matching engine | DO_NOT_CREATE | Existing owners provide the persistence and execution boundaries |
| New durable primitive | NEW_PRIMITIVE_REQUIRED: none identified | Reassess only against a concrete unmet requirement |

Source classification, repeated reporting and network connections are not
verification. Historical activity, current disclosed mandate, recent commitment,
inferred pattern and unresolved currentness remain distinct proposition
classifications. A human categorization correction does not settle binding,
authority, applicability or temporal validity. Existing source currentness only
answers lineage/supersession; it cannot supply those missing temporal premises.

Automated investigation remains agent-attributed. Human review provenance follows
the existing explicit-attribution pattern documented in
comm-i5a-opr-5-3-human-authority-provenance-correction.md. No investor names,
mandates, commitments or AUM values from conversation examples are production
seeds. Evaluation fixtures remain EVALUATION_INPUT. Outreach is a separate
authorized action and is not executed by matching or brief generation.

Candidate discovery is now an EXTEND_EXISTING operation through the existing
external_research fixed-route catalogue, Airlock policy resolver and workspace
Source/EvidenceItem/AnalysisRun owners. The attention UI declares its work plan
and retrieves the selected public page. No project content is transmitted in
the fixed GET. The bounded catalogue includes CIB priority-sector and process
pages, not seeded investor facts. An arbitrary URL or redirected route is refused.

Original response bytes/hash, URL, publisher attribution, retrieval time,
extraction limits and screening notes are retained. Source, unvalidated evidence
and analysis commit together through the existing workspace save. Identical
URL/bytes reuse the retained source and evidence; an explicit later retrieval
records its own analysis without strengthening currentness. Reload reads only.
Post-commit failure cannot delete the retained original. Candidate text remains
outside the previous attention selection until explicitly selected for further
classification/matching. Human review and canonical promotion remain separate.

The existing session-only research answer path remains session-only; it does not
silently retain sources. Retention is the distinct typed attention action.
Tests: test_candidate_reference.py and test_airlock_web_research_01.py. Browser
proof uses verify_source_review_ui.py --public-reference against the actual
configured endpoint inside EVALUATION_INPUT scope. No production profile truth
is seeded from either a conversation or a test fixture.
