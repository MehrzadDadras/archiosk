# Planning & Zoning Composer integration

Deployment state: **LOCAL_ONLY**. No deployment or push authorized.

The Planning workspace uses the existing `conversation_dock`, shell chat region,
`ContextEnvelope`, `run_conversational_turn`, project security policy, and
`llm_gateway`. There is no second chat engine, provider adapter, or report store.

## Working flow

1. Choose the existing project and enter one or more property addresses. The
   address control adds/removes ordinary inputs; there is no batch-mode switch.
2. Each property passes independently through `planning_live.run_live`. The
   retained result keeps each complete property document and retrieval envelope.
3. The shared Composer discusses only that retained study. It receives property
   documents, authority references, exceptions, unresolved items, options,
   conclusion, supplied regulatory matrices, scenario and proposal state.
   Geometry coordinates stay in retained evidence; chat receives exact hashes
   and existing deterministic spatial relationships. Oversize context is refused,
   never silently truncated or restricted to the first property.
4. A successful turn creates a new shared transient run ID. Scenario is verbatim
   user context; model text remains `ai_proposed`. Neither writes into host facts.
5. Investigation requires an explicit confirmation and uses the existing
   municipal reader/compiler. It cannot accept a model-authored source URL or
   authority claim. It may remain unresolved. New retrieval creates a revision;
   prior proposal assessments are not carried over as if recomputed.
6. Save Study uses the existing immutable snapshot and artifact store. Reopen
   reads saved bytes. Continue creates a working revision without changing the
   saved result. Word/PDF export reads retained state without municipal retrieval.

## Boundaries

- Up to ten property inputs; identities, geometry, exceptions and provenance
  remain separate even for a combined-site scenario. Additional saved map assets
  have separate `evidence/property-N/` namespaces.
- The existing shared transient store remains authoritative for unsaved handoff:
  project + actor + random run ID, hash validation, one-hour TTL, existing save
  locking and idempotency. This is not automatic project-history persistence.
- Proposal comparisons accept only bound normalized matrix rows, source hashes,
  compatible units and an explicit minimum/maximum direction. The proposed value
  must occur in the user message. Existing deterministic comparison machinery
  computes the discrepancy. Its planning implication remains conditional on
  applicability; it does not predict approval or establish law from a working table.
- Presentation supports facts, compact headings, zoning focus and map visibility.
  Compact mode retains every factual row. Exception conditions, conclusion and
  material unresolved items remain visible. Arbitrary removal of material findings
  or promotion of conversational assertions into the report is not an allowed action.
- The report uses Fact / Value / Source / Status / Action. Detailed retrieval and
  provenance remain in the audit layer. A visual/text disagreement blocks export
  even if the user chooses to hide the map.
- Planning disables project-wide draft-assist and image/Q creation controls on
  the reused Composer. They would otherwise expand this bounded context to
  unrelated project work. Existing project Composer behavior is unchanged.
- Conversation is bounded to 100 messages, with the last twelve supplied as
  conversational history. The saved snapshot preserves the complete retained thread.
- No new project creation rule, infrastructure service, GO-PDZ schema, validator
  behavior, authority store or production deployment is introduced.

## Change-set isolation

`owned-files.json` names the candidate files. The isolated tree includes the
previously qualified Planning map/persistence/export prerequisites, which were
still uncommitted in the shared checkout. The unrelated table-unit repair in
`case_workspace.py`, validator repairs, governance edits and feasibility archives
are excluded. The shared checkout is preserved.

`isolated-setup.json` records the base HEAD, per-file hashes and verified existing
Nipigon test assets. No benchmark assets were acquired or copied.

## Qualification

The test lane uses synthetic municipal responses and mocked Composer replies.
It proves routing, context isolation, host state transitions, browser controls,
export integrity and snapshot behavior; it is not live-model competence evidence.

Exact commands, counts, timing and pre/post tree hashes are recorded in
`targeted-result.json`, `full-result.json` and their freeze records. The full gate
must be clean before this change set is recommended for deployment review.

No model calls, production deployment, rescoring, frontier advance or sealed
benchmark access occurred in this task.

## Completed gate

- Targeted Planning, existing Composer/export regressions and Tier 0: **1,457 passed / 5,063 subtests**, exit 0.
- Full parallel gate: **8,889 passed / 9,730 subtests / 3 skipped / zero failures or errors**, exit 0.
- Full pytest runtime: **665.59 seconds**; wrapper including verification: **667.15 seconds**. First test began at **33.41 seconds**.
- Eight workers, `--dist loadfile`, existing `not legacy_route_diagnostic` lane. Existing test-only secret and verified Nipigon assets supplied. External model calls disabled.
- Isolated files unchanged: **true**. Shared owned files unchanged: **true**. Base HEAD unchanged through gate: **true**.
- Recommendation: ready for Product Owner deployment review. Live provider behavior was not exercised; no deployment occurred.

Frozen gate tree fingerprint: `b1c1c3ab0612c29f29880892077cfc35a084fe10da91a3fdb57eea1fc7549561`.

The local commit contains the isolated Planning prerequisites and Composer changes, not unrelated concurrent repair work. Original detailed qualification logs remain in the shared workspace's record folder.
