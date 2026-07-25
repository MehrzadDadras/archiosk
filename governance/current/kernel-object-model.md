# Current Implemented Kernel Object Model

**Status:** Implemented. **Ground truth:** `services/case_workspace.py` in `C:\Archiosk\Research\archiosk` (backend repo). Test suite: `tests/test_foundation_batch_a.py` through `test_foundation_batch_k.py` plus `tests/test_requirement_promotion.py`, stdlib `unittest`, 185 passing tests as of the `promote_requirement_item()` implementation tranche (commit follows this document). Every anchor below was checked directly against current code, not recalled from an earlier round — line numbers shift as the file grows; re-verify before citing in future work if material time has passed.

Each entry: implementation status, code anchor, what question it answers, known gaps.

---

### `Source` — implemented
`case_workspace.py:688`. Answers: what document/drawing/model is this, and where did it come from. Fields include `document_id`, `revision`, `issue_date`, `issuer`, `document_status`, `document_authority`, `file_hash`, `origin_type`/`origin_reference` (open-world, already the correct mechanism for importing external/cross-project material — see `specified-unbuilt/cross-boundary-architecture.md`).

### `Requirement` — implemented
`case_workspace.py:732`. Answers: what did the Owner/source document state, independent of any Finding. Never a compliance claim — `set_requirement_status` (`~3054`) enforces a hard denylist against compliance-shaped status values. `registration_method` distinguishes machine-extracted from manually-registered content, feeding directly into `promote_requirement_item()`'s finalized design contract (see `specified-unbuilt/investigation-lifecycle-extensions.md`).

### `Finding` — implemented
`case_workspace.py:822`. Answers: what discrepancy/observation has a machine or human asserted. `claim_status` defaults to `provisional` — the object is weak-by-default, unlike `Requirement`, by design (this asymmetry is why Requirement branching needed a `"proposed"` status extension and Finding did not — see `specified-unbuilt/investigation-lifecycle-extensions.md`).

### `Relationship` — implemented, one known consistency gap
`case_workspace.py:1105`. Answers: how are two objects connected (open-world `relationship_type`: supports/contradicts/qualifies/references/depicts/corresponds_to/implements/depends_on/blocks/affects/resulted_in). `provisional`/`confirmed_by` correctly separate machine-asserted from human-confirmed status at the field level — but `confirm_relationship` (`~3776`) mutates these fields **in place** rather than following the append-only/successor pattern used everywhere else in this model. This is a real, honestly-preserved inconsistency: at any single point in time the object's status is still correctly readable, but the pre-confirmation state is not separately reconstructable the way `Finding`→`ReviewerValidation` preserves its full history. Flagged, not yet fixed.

### `Case` / `CaseRecord` — implemented, several designed extensions unbuilt
`case_workspace.py:1550`. Answers: what investigation is this. `status: str = "open"` exists but is **decorative today** — confirmed by direct check: no method in the file ever mutates it. The full designed extension set (visibility field, collaboration-threshold check, `CaseLock`, `derived_from_investigation_id`, publication anchors) is specified but unbuilt — see `specified-unbuilt/investigation-lifecycle-extensions.md`.

### `ReviewerValidation` — implemented
`case_workspace.py:835`. Answers: is this Finding accurate (Correct/Incorrect/Partial/Needs Evidence/Not Applicable) — deliberately separate from `Disposition`.

### `Disposition` — implemented
`case_workspace.py:847`. Answers: what happens to this Finding next (Confirmed/Rejected/Deferred/Known Pending Acceptance/Known Accepted). Gates `apply_findings` (`~2908`) — Apply requires a Confirmed Disposition on record.

### `RequirementAdjudication` — implemented (Foundation Batch K)
`case_workspace.py:860`, methods at `~3091`–`3176`. Answers: does current evidence satisfy this Requirement (Satisfied/Partially Satisfied/Not Satisfied/Not Applicable/Accepted Alternative). Mandatory, non-defaulted `reasoning` field. Validated evidence references (`evidence_finding_ids`/`evidence_relationship_ids`) resolve only against the current project's own `workspace.findings`/`workspace.relationships` — structurally incapable of accepting a cross-project or legacy-`RequirementItem` reference. `requirement_adjudication_state` is derived, never stored, matching `review_state_for_finding`'s pattern. **Route wiring implemented** — `routes/workspace.py`'s `adjudicate_requirement` (`POST /projects/<project_id>/workspace/requirements/<requirement_id>/adjudicate`) calls this directly, passing its own `governance_log` through rather than double-logging.

### `promote_requirement_item()` — implemented (ratified governance baseline tranche)
`case_workspace.py`, method on `CaseWorkspaceStore`, immediately after `requirement_adjudication_state`. Bridges a `RequirementItem` (`services/bhive_parser.py`'s legacy extraction pipeline, still-decoupled by design — this module does not import `bhive_parser`) into a governed `Requirement`. `source_id` has no default and cannot be omitted (`TypeError` if the caller tries) — no inference path exists. Creates the Requirement's accompanying `Finding` + `AnalysisRun`/`AnalysisTrigger` (preserving extraction confidence and an explicit, caller-supplied trigger) and the `Requirement` itself (`registration_method=REQUIREMENT_REGISTRATION_MACHINE_EXTRACTED`) in memory, then writes all three in exactly one `self.save(workspace)` call — the same single-save-per-governed-operation pattern `register_table_evidence` already uses, so a failure between records is structurally impossible, not just tested for. Never sets `Requirement.status` to anything but its ordinary default and never creates a `Disposition`/`RequirementAdjudication` — the promoted Requirement is exactly as un-adjudicated as a manually-registered one. Route wiring: `routes/workspace.py`'s `promote_requirement_item_route` (`POST /projects/<project_id>/workspace/cases/<case_id>/requirement-items/<requirement_item_id>/promote`), form-required `source_id`, `AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor=<reviewer>)` constructed from the real requesting session. Tests: `tests/test_requirement_promotion.py` (19 tests: 14 store-layer, 5 route-layer).

### `Snapshot` — implemented
`case_workspace.py:1690`, `create_snapshot` at `~4316`. Answers: what did the whole project look like at a point in time. `project_state_version` (an integer, incremented on every governed write via `ProjectWorkspace.version`) is the correct, collision-proof identity for point-in-time state — proven not vulnerable to the same-calendar-day-different-state problem a bare timestamp would have. Can only capture the *current* version at creation time; cannot retroactively reconstruct a past version if none was taken at the time.

### `Supersession` — implemented
`case_workspace.py:1060`. Answers: what replaced what, by whom, under what authority, non-destructively. Deliberately reserves (but has never been exercised for) multiple simultaneous proposed successors per predecessor — the basis for the `"proposed"`/`"not_adopted"` status-extension pattern reused across Requirement branching, Scenario, and `needs_revalidation` in `specified-unbuilt/`.

### `TemporalObligation` — implemented, one extension reserved
`case_workspace.py:1148`. Answers: what's due, by when. Current shape models a single due-date, not a recurring series — recurring-obligation support (30-year P3 maintenance schedules) is a real, named, deferred extension — see `deferred-reserved/reservations.md`.

### `AnalysisRun` / `AnalysisTrigger` — implemented
`case_workspace.py:935` / `908`. Open-world trigger vocabulary already includes `ANALYSIS_TRIGGER_SOURCE_CHANGE` — confirmed still present, and confirmed to be the correct, already-existing mechanism for authoritative-metamorphosis delta-detection (see `specified-unbuilt/metamorphosis-and-dormancy.md`) rather than requiring a new object.

### `GovernanceLog` — implemented
`services/governance.py`. Append-only JSONL audit trail, one file per project (`{project_id}.governance.jsonl`), confirmed to have no cross-project read path — this is the mechanism confirmed safe against cross-party leakage in the Owner/Proponent boundary review.

### Legacy, distinct object — `RequirementItem` / `RequirementsRegistry`
`services/bhive_parser.py`, `services/requirements_registry.py`. The original, day-one (`4ce97fd`) requirement-extraction pipeline, still live in production via `services/ingestion.py` → `routes/api.py`/`routes/portal.py`. Structurally separate storage from `ProjectWorkspace` — no code path exists that could resolve a `RequirementItem` id through any `Requirement`-scoped lookup. Confirmed a different stage of the same conceptual river (extracted candidate vs. governed Requirement), not a duplicate-truth risk, not a legacy-vs-current split requiring cleanup before Batch K can be trusted.
