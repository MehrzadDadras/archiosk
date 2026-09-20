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
