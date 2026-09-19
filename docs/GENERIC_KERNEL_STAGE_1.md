# Generic information kernel mapping — Stage 1

Scope: the Product Owner's ARCHIOSK / GO Intelligence Programme, Stage 1 only.
Stage 2 must wait for Product Owner use and review of this implementation.

## Baseline and architecture

Started from clean repository `3e11de50f6dcb0b0fedf61b50e9e77695822dd68`.
Direct SSH inspection on 2026-09-19 confirmed the active deployed service
identifies `c1ffa6c82de2cce205379741c1c149e6f5235924`; `/health` returned 200.
The difference is the existing documentation-only convergence closeout.
The previous Survey/runtime convergence proof remains in
[SURVEY_RUNTIME_CONVERGENCE.md](SURVEY_RUNTIME_CONVERGENCE.md).

`CaseWorkspaceStore.inspect_kernel_mapping` is a read-only vocabulary projection
over its existing workspace collections. Both real and evaluation Flask routes
call this same method. Its EvidenceItem view calls `admit_proposition`, which
continues to own trust, geometry qualification and evaluation lineage. Endpoint
currentness and relationships use their existing resolvers. No schema, identity,
graph, geometry, admission, conversation or persistence owner is replaced.
Neither protected worker file changes. Inspection creates no authoritative state.

The existing runtime observer records actual method invocation and returns. The
route records consumption of the returned mapping; the existing after-request
hook records the HTTP surface. Trace persistence is operational only. Record
references are visibly distinguished from proof of another consumer's invocation.

All 17 candidate concepts are mapped in the UI. Existing `Attention` is a reviewer
notification, not the proposed analytical scope. A provisional `Relationship` is
not an expiring, objective-bound constellation. Universal subject identity also
remains unproven: addressed regions and scoped subject references are the current
concrete substrate. These findings do not authorize Stage 2/3 implementation.

Existing attention precursors must be extended before proposing new storage:
`InvestigationStep.question`, `evidence_requested`, `evidence_examined_ids`,
`Claim.evidence_links` and `evidence_excluded` (with reasons),
`explain_investigation_answer`, and `build_relationship_sachet` (task-bound read
projection of one recorded relationship with an excluded-relationship count).
These are not yet the complete analytical scope/lifetime/promotion contract.

## Product Owner workflow

1. Sign in as administrator, enable Developer Mode, open
   `/admin/survey-evaluation`, and choose **Observe my real requests**.
2. Under live project execution, open **Inspect generic kernel mapping** for
   **226104 1 Castille**. Direct entry:
   `/projects/9c00eeec-4e65-4bde-bcea-de8b09c8beb1/kernel`.
   The baseline contains two sources, 42 evidence items and no private cases.
3. Select a Source, then an EvidenceItem, and press **Inspect item**. See its
   concrete type, generic roles, unchanged stored record, authority fields,
   governed admission, currentness, source jump, relationships and references.
4. Follow a downstream reference and a source jump. Select a different item;
   each form submission is a real Flask request to the same owned mapping.
5. Follow **Observation** to inspect actual invocation, return, consumption and
   surfacing. Mapping is an inspection consumer; an Ask GO/export invocation is
   only proven by operating that consumer's own existing UI.
6. Open an existing Survey Evaluation run and choose **Inspect generic kernel
   mapping**. These use `/admin/survey-evaluation/<run_id>/kernel`, with an explicit
   EVALUATION_INPUT ceiling, the same mapping and the same admission owner.
7. Review the concept/gap table and direct the next stage only after use.

**Reload amendment:** **Reload view** appears on kernel mapping, the Survey
catalog/runtime observation page and each Survey evaluation run. It issues a GET
to the same route and preserves item/observation/query selection; it does not
resubmit a review, calculation or confirmation POST. The existing Operational
Convergence surface already has **Refresh evidence**. Future programme review
surfaces should reuse the shared `components/review_reload.html` control.

Existing evaluation examples are listed in the convergence closeout: earned H
`287369d4b4af47dc8ddaf2e49aa9cb0e`, missing monument
`60678a60a1ce49d787265790c088b09e`, qualified traverse
`270812e8302f484890356792b6036b99`. Their stored state is resolved afresh by the
existing owner; repeated inspection cannot strengthen it.

Expected states include SOURCE_REFERENCE, PROPOSAL, UNRESOLVED and scoped
calculation states exactly as returned by admission. Generic role labels do not
imply established propositions. Unknown/foreign item selections return 404;
anonymous requests require login; non-admin or disabled Developer Mode is refused.
Whole-project inspection refuses if any Case is invisible to the actor, so
indirect references cannot reveal private Case content. Removed projects use the
existing tombstone flow. All responses are private/no-store.

## Limits and validation contract

This bounded mapping covers 23 existing collections. Other populated collections
are named as unmapped; absence from the view does not imply absence from the
model. Downstream references are exact stored ID fields, not semantic matches or
an exhaustive dataflow graph. Serialized content retains its original text;
inspection does not infer edges from prose. Source jumps preserve existing
addresses; no automatic page or region binding is invented. The controlled PDF
link identifies the evaluation run, not an inferred per-item source file.

No new attention, temporary edge, pattern inference, muscle framework, game,
matching or composition engine is claimed. No authoritative state is created by
inspection; governed state consumption, read-only integrity, uncertainty and
absence of false strengthening are the applicable proof obligations.

Focused tests: `tests/test_kernel_mapping.py`, Survey runtime convergence and
Survey Evaluation suites. They compare persisted bytes before/after inspection,
verify actual route-level resolver invocation and consumer traces, exact
provenance/qualification, privacy refusals, escaping and evaluation isolation.
Run the authoritative full suite with a frozen implementation tree before
deployment; record result and immutable SHA in the delivery closeout. Live browser
proof must operate the real forms; a fixture invocation alone is insufficient.
Product Owner approval and progression remain pending until that use/review.

## Delivery checkpoint — 2026-09-19

Implementation and deployed SHA:
`900a48c1490f67b93a7a543ebc6d9fa850b9c2d6`.
This closeout text is documentation after that implementation commit.

The authoritative full gate ran in parallel (`-n 8 --dist loadfile`) on the
frozen implementation, with **9,530 passed, 5 skipped, 14 warnings, 10,035 subtests
passed, PYTEST_EXIT=0**, in 744.04 seconds. All eleven frozen file hashes matched
after the gate. Two additional skips versus the baseline were confirmed as
sandbox-denied symlink creation; both containment tests passed when rerun with
the required filesystem access (2 passed in 4.62 seconds). No test or production
implementation was changed to make them pass. The remaining three skips match
the baseline count. Focused qualification includes 132 passing tests before the
reload amendment, 131 passing plus an over-strict reflected-query assertion in
the amended run, then all 12 kernel tests passing after correcting that assertion.
The final full gate includes that correction and the complete reload amendment.
The first full run was stopped at 61% for the Product Owner's reload amendment;
it is not counted as qualification, and edits began only after its workers exited.

Retained local records: `instance/kernel-focused-03.log`,
`instance/kernel-focused-04.log`, `instance/kernel-focused-05.log`,
`instance/kernel-full-02.log`, `instance/kernel-frozen-02-hashes.csv`,
`instance/kernel-deploy-dry-run.log`, `instance/kernel-deploy.log`, and
`instance/kernel-deploy-verification.log`.

Exact archive SHA256:
`e2e6fb8dcdc29118df088f9faa23c81164b083967886d6fe9fc8bcb37de1c2cd`.
The deployment dry-run showed only expected application changes and the prior
convergence documentation closeout; no deletions or protected-path changes.
All **1,127 checked archive files** matched deployed bytes. Protected `.claude/`
configuration was excluded. Environment bytes were compared to the rollback copy
and remain unchanged. Instance data, virtualenv and retained drawing assets were
excluded from sync. GO, perception and visual services are active; local/public
health checks passed. The new live kernel route returns 302 to anonymous access.
Rollback code and the restricted environment copy remain at
`/var/www/archiosk-backup-c1ffa6c82de2cce205379741c1c149e6f5235924-before-kernel-900a48c1490f67b93a7a543ebc6d9fa850b9c2d6`.

**Authenticated live UI proof is pending.** No maintainer-issued verification
link has been supplied in this session. The existing mechanism reserves issuance
to a human maintainer (`services/verification_access.py` and
`tools/manage_verification_access.py`); no credentials or alternate login path
were created. `tools/verify_kernel_mapping_live.py` is ready to operate the actual
Inspect/Reload forms and retain live observation IDs and screenshots. No live
runtime trace reference is claimed for Stage 1 until that execution occurs.
Health, deployed bytes, and an anonymous redirect do not satisfy live invocation.

| Activation step | Proven status at this checkpoint |
| --- | --- |
| IMPLEMENTED | Existing owner extension and shared real/evaluation UI deployed |
| REACHABLE | Flask routes and links tested; live anonymous authentication boundary verified |
| INVOKED | Actual resolver invocation proven by real Flask route tests; authenticated live UI pending |
| CONSUMED | Returned mapping consumed by template and recorded in route tests; live proof pending |
| SURFACED | Governed states, provenance, refusals and reload controls rendered in tests; live visual proof pending |
| END-TO-END OBSERVABLE | Local route chain proved; live browser chain and Product Owner use/review pending |

The Product Owner entry is
[Castille kernel mapping](https://archiosk.com/projects/9c00eeec-4e65-4bde-bcea-de8b09c8beb1/kernel).
Enable Developer Mode and request observation first through
[Survey Evaluation](https://archiosk.com/admin/survey-evaluation).
Select Source/EvidenceItem, inspect, follow provenance/references, then reload.
The UI links the current request's trace when observation recording is enabled.
Review of Stage 1 remains open; Stage 2 has not begun.

## Programme register — retain through later stages

- Attention changes focus, not truth; excluded evidence still exists.
- Temporary edges are not canonical truth and require governed promotion.
- Readable does not mean bound; newer does not mean authoritative.
- Computable does not mean established; projective does not mean Euclidean;
  Euclidean does not mean metric; metric does not mean legal/survey authority.
- Raw prose is not a governed proposition; LLM output is not canonical truth.
- Trace is not evidence; evaluation input is not project authority.
- Rendering preserves qualification; IFC preserves admission; Ask GO preserves
  deterministic state. Consumers carry the weakest applicable qualification.
- Matching is not semantic similarity; composition is not ranking; investment fit
  does not authorize automatic execution. Asset compatibility does not act.
- Missing, ambiguous, conflicting, insufficient and untrusted evidence remain
  explicit; no stronger state without new evidence or an explicit premise.
- Preserve lineage from source through observation, binding, transformation,
  governed result, consumer and UI/export. Commit state before emitting telemetry.
- Failures identify reusable muscles, not necessarily game-specific defects:
  ATTENTION_FAILURE, IDENTITY_FAILURE, BINDING_FAILURE, TRAVERSAL_FAILURE,
  RELATIONSHIP_FAILURE, COMPARISON_FAILURE, CONTRADICTION_FAILURE,
  GAP_DETECTION_FAILURE, AUTHORITY_FAILURE, UNCERTAINTY_FAILURE,
  COMPOSITION_FAILURE, CONSUMER_FAILURE, MISSING_PRIMITIVE, FALSE_STRENGTHENING,
  PREMATURE_DECISION_COLLAPSE. Rerun affected games after muscle fixes.
- Domain success must not hard-code domain logic into the kernel. Construction,
  RFP, team composition, investment and assets reuse governed owners.
- CREATE → PROVE → CUT OVER → RESERVE/DELETE. Preserve the working path until a
  replacement is proven; do not leave competing active paths after cutover.
- Each stage: BUILD → real UI → real INVOCATION → live proof → Product Owner use
  and direction. IMPLEMENTED/REACHABLE do not prove INVOKED, CONSUMED, SURFACED
  or END-TO-END OBSERVABLE. Scorecards are diagnostic, not runtime proof.
- Follow Stage 1 mapping, 2 attention, 3 constellations, 4 muscles, 5 construction
  games, 6 RFP matching, 7 team composition, 8 investment, 9 assets, 10 cross-domain
  testing. Do not cross a Product Owner stage-review gate implicitly.
