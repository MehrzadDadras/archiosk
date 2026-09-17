# Claude Promotion Handoff — Cycles 1–4

Status: **CYCLES_1_4_READY_FOR_CLAUDE_PROMOTION**.

Exact implementation commit for every cycle in this handoff:
`332074b25ac85bf410d628c754e11f848587d741`.
The handoff is finalized in a subsequent documentation-only commit so it can
name the immutable implementation SHA without a self-referential commit hash.

Reconciled baseline: `089f4a309a160cbf9075b376a68b9f968a3a2872`.
Claude's incorporated survey-graph and North reconciliation remain unchanged.
Cycle 5 has not started. No push, deployment, production-data migration, or
remote live proof is part of this handoff.

## Promotion contract

These are production-module changes with local consumer tests, not model
training or a bulk Cognitive Gym import. Every cycle remains **NOT_PROMOTED**
until Claude verifies incorporation into the authoritative production path,
gates the resulting tree, deploys, and proves **LIVE_REACHABLE** for ordinary
users. A passing test, this document, or a registered proposal is insufficient.

The handoff's implementation SHA identifies only programme-owned changes.
Other uncommitted planning/feasibility/Gym work in the shared tree must not be
included or overwritten. Do not cherry-pick old survey changes over the baseline.
The full gate ran on the frozen shared working tree, including that unrelated
work; it was not a separate clean checkout of the implementation commit.
Claude must gate the actual incorporated production candidate before deploying.

## Runtime entry points

- Normal examination: `services/visual_classification.py:examine_source`
  invokes `drawing_segmentation.examine_title_blocks` and
  `package_muscles.activate`. The latter invokes proposal-only
  `register_supersessions`; it cannot apply authoritative lineage.
- Native perception: `services/perception_worker.py:_register_sheet_index`
  calls `sheet_identity.register_sheet_index`, which persists manifest gaps
  even without a vision/model call.
- Ordinary document result and Ask GO: `routes/portal.py` GET/POST
  `/document-shop/jobs/<project_id>` calls
  `document_examination.build_result`; Ask GO calls
  `services/document_conversation.py:ask`, `build_context`, and `render_prompt`.
  Cycles 1–3 are qualified at these local consumer boundaries. Claude must prove
  the corresponding deployed, ordinary-user behavior.
- Cycle 4 uses the existing human review/apply routes specified below. Its
  scoped proposals and applied lineage still require ordinary Ask GO
  incorporation and live proof; generic lineage availability is not that proof.

## Cycle 1 — weaker relevant certainty survives consumption

- **Capability / prevented failure:** preserve separate read and binding
  certainty; prevent a cached/persisted RECOVERED aggregate from upgrading a
  PARTIALLY_RECOVERED attachment.
- **Authoritative implementation and changed symbols:**
  `services/binding.py:bound_certainty` recomputes and caps the aggregate;
  `services/document_examination.py:_visual_lines` surfaces graph dimensions
  with separate attachment and read certainty.
- **Changed tests / fixtures:** `tests/test_document_muscles_01.py:
  F1BindConfidenceSplit.test_persisted_aggregate_cannot_strengthen_components`;
  `tests/test_survey_reference_01.py:BindingPromotionJourney`.
  Castille `144.12`, read RECOVERED, binding to LOT LINE 3 PARTIALLY_RECOVERED.
- **Controls:** persist/reload that split; inject an incorrectly high aggregate
  into persisted evidence; renderer must not render a certain bound value;
  absent/UNRESOLVED reading cannot strengthen binding. Document Shop and actual
  Ask GO gateway-boundary spy must receive qualified wording.
- **Persistence/runtime assumptions:** existing flat workspace evidence and
  graph renderer; the gateway is stubbed for repeatability. This proves consumer
  handling, not live OCR accuracy. Already-committed graph normalization is a
  baseline dependency, not a second implementation.
- **Authority constraints:** certainty is not approval or permission to use an
  uncertain attachment as a measured property.
- **Must reach ordinary Ask GO:** “144.12 read; attachment to LOT LINE 3 only
  partially recovered,” including after reload and legacy aggregate corruption.
- **Must not promote:** OCR confidence as object-binding proof, cached aggregate
  authority, or the test fixture as live recognition evidence.

## Cycle 2 — view existence is independent of field recovery

- **Capability / prevented failure:** retain situated drawing evidence when a
  title block cannot be read; prevent filename/package metadata from filling
  unrecovered fields as if they were read from the sheet.
- **Authoritative implementation and changed symbols:**
  `services/drawing_segmentation.py:read_region`, `segment_sheet`,
  `examine_title_blocks`; `services/visual_classification.py:examine_source`;
  `services/case_workspace.py:CaseWorkspaceStore.create_derived_view`;
  `services/derived_view.py:effective_title_block`;
  `services/drawing_intake.py:_FIELD_PATTERNS`;
  `services/sheet_identity.py:sheet_identity_of`, `title_block_readings`;
  `services/document_examination.py:build_result`.
- **Qualification fixture / changed tests:**
  `tests/test_survey_reference_01.py:SheetIdentityPromotionJourney` creates
  native PDFs for architectural A-203, mechanical M-501, old/current revision
  labels, and a blurred raster title block, using the misleading upload name
  `A-999-rev99-current.pdf`.
- **Controls:** printed fields retain individual values, certainty and region
  provenance; blurred fields remain UNRESOLVED; no discipline from sheet-prefix
  inference; old/current issue labels are independently retained; repeated
  examination does not duplicate structure/views. Document Shop and Ask GO
  context expose the same unresolved state.
- **Root-cause repair:** native-text perception could return before registering
  pages on an unreadable PDF. `examine_title_blocks` now registers physical PDF
  page structure when absent, explicitly making no text assertion, then invokes
  the existing title-block candidate producer.
- **Persistence/runtime assumptions:** PyMuPDF, existing DerivedView storage,
  native region reading and existing raster OCR fallback. Unreadable OCR is
  stubbed in qualification; remote OCR and deployment still require verification.
- **Authority constraints:** administrative inherited metadata remains separate
  from `inherited_title_block.field_readings`; a view is not a recovered identity.
- **Registry closeout:** `UI_REFERENCE_MAP.md` now registers the intended
  `upload.confirm.field.issue_state`, `.input`, and `.evidence` surfaces emitted
  by `templates/upload_confirm.html`. This repair adds three registry rows only;
  it changes no Cycle 1–4 runtime behavior.
- **Must reach ordinary Ask GO:** sheet number/title, discipline, revision,
  issue date/state with independent certainty and inspectable provenance;
  unreadable fields explicitly UNRESOLVED, without losing the drawing.
- **Must not promote:** filename guesses, neighboring-sheet values, inferred
  discipline, or revision recency as authority.

## Cycle 3 — expected-but-absent with reconstructable history

- **Capability / prevented failure:** preserve a declared absence while allowing
  its current projection to clear after arrival; prevent normalized identifiers
  from replacing issued evidence and prevent invented missing-sheet content.
- **Authoritative implementation and changed symbols:**
  `services/sheet_identity.py:register_sheet_index`,
  `register_manifest_gap_evidence`, `missing_sheet_findings`,
  `declared_but_absent`, `MANIFEST_GAP_CONTENT_TYPE`;
  `services/package_muscles.py:register_manifest_gaps` delegates to that writer;
  `services/document_examination.py:build_result` surfaces package-wide gaps.
- **Qualification / changed tests:**
  `tests/test_survey_reference_01.py:MissingSheetPromotionJourney`;
  `tests/test_document_muscles_01.py:F5ExpectedButAbsent`.
  Native index says `A-203`; package initially lacks it; later `A203` arrives.
- **Controls:** `reference_text == A-203`, `sheet_token == A203`; deterministic
  key equivalence; issued spelling in visible text; `contents_claim is None`;
  absence persists without a vision/model call; arrival clears Document Shop
  and Ask GO context while the original EvidenceItem remains identical.
- **Persistence/runtime assumptions:** append-only manifest-gap observations
  record observation time and then-present source IDs. Current absence is
  recomputed against eligible sources; historical SourceReference resolution
  and earlier evidence are not rewritten. Unchanged observations are idempotent.
- **Authority constraints:** an index declaration proves expectation, not the
  missing sheet's existence, contents, intentional withholding, or package
  completeness beyond the observed gap.
- **Must reach ordinary Ask GO:** “Missing evidence: A-203” now, and a distinct
  historical account after arrival. Do not present an old gap as currently open.
- **Must not promote:** normalized spelling as the source quote or a fabricated
  reconstruction of A-203.

## Cycle 4 — scoped proposal, human acceptance, authoritative application

- **Capability / prevented failure:** an automatic detector may identify a
  change but cannot retire any governing evidence. Prevent clause amendments
  from acquiring Source endpoints, near-word action inference, first-match
  predecessor selection, and proposal-to-authority laundering.
- **Proposal representation:** an `EvidenceItem` with class
  `ai_generated_proposal` and content type
  `application/vnd.archiosk.supersession-proposal+json`. JSON carries predecessor
  and successor typed IDs, candidate predecessor IDs, clause/whole-document
  scope, directive EvidenceItem/text, region/source provenance, content hashes,
  declared authority basis, categorical certainty, and uncertainty. A linked
  `ChangeArrivalAssessment.supersession_proposal_id` identifies that evidence;
  its requirement target is null. No second approval mechanism or graph type.
- **Authoritative implementation / exact changed symbols:**
  `services/supersession_detect.py:scoped_directive`, `clause_paragraph`,
  `has_directed_change`;
  `services/package_muscles.py:register_supersessions`,
  `supersession_candidates`, `supersession_proposal`,
  `SUPERSESSION_PROPOSAL_CONTENT_TYPE` (removes `_earlier_source_naming`);
  `services/case_workspace.py:ChangeArrivalAssessment`,
  `CaseWorkspaceStore.record_change_arrival_assessment`,
  `review_change_arrival_assessment`;
  `services/change_application.py:apply_accepted_change`, `_scoped_proposal`,
  `_scoped_successor`, `_apply_scoped_change`, `pending_conflicts`,
  `transition_brief`;
  `services/change_arrival.py:assessment_brief`;
  `routes/workspace.py:apply_change_arrival_route` updates its success wording
  to support scoped predecessors rather than falsely calling all of them Requirements.
- **Acceptance hook:** existing POST
  `/projects/<project_id>/workspace/change-arrival/<assessment_id>/review` calls
  `review_change_arrival_assessment`. Acceptance still writes NO lineage.
  Deferral is leaving the existing assessment proposed; rejection uses the
  existing rejected state. Unresolved scope/authority cannot be accepted.
- **Exact authoritative write point:** existing POST
  `/projects/<project_id>/workspace/change-arrival/<assessment_id>/apply` calls
  `change_application.apply_accepted_change`; only its accepted,
  authority-moving scoped branch `_apply_scoped_change` calls the existing
  `CaseWorkspaceStore.record_supersession`. No automatic call remains in
  `package_muscles`. Evidence is revalidated at application, not trusted merely
  because the assessment was previously accepted.
- **Endpoint model:** a clause occupying one identifiable paragraph uses the
  existing paragraph EvidenceItem on each side, each anchored to its own
  AddressableRegion and page StructuralUnit. The edge is
  `evidence_item -> evidence_item`; unaffected paragraph EvidenceItems and the
  base Source have no supersession edge. Explicit whole-document replacement
  uses `source -> source` and updates existing source revision pointers.
- **Qualification fixtures / changed tests:**
  `tests/test_muscle_activation_01.py:F4SupersessionActivated` uses real temporary
  CaseWorkspaceStore persistence and `register_pdf_page_structure`, base clauses
  2.4 and 2.5, and separate addendum paragraphs. Existing B1/B2 suites defend
  the original Requirement acceptance/application path.
- **Positive controls:** complete explicit replacement; acceptance then apply;
  exact endpoint content and contractual authority after reload; unchanged
  historical evidence and unaffected clause 2.5; exact quoted document name plus
  “in its entirety” for Source scope; existing HTTP review/apply routes with
  real login and a test store; idempotent replay and interrupted stamp recovery.
- **Negative / ambiguous controls:** mention-only and nearby unrelated replace
  verb; supplement; missing predecessor; two predecessor clauses in different
  Sources; multiple headings in one paragraph; replacement without its body;
  missing declared authority; OCR/proposal predecessor evidence; rejection and
  deferral; changed text under the same ID; competing accepted successors.
- **Persistence/runtime assumptions:** paragraph EvidenceItems must already be
  registered by normal perception. No new extraction service. Only native/direct
  source evidence with an existing authority-bearing `document_authority` can
  qualify for acceptance. Stored hashes prevent changed content at the same
  endpoint from retaining an old approval. Saves use existing optimistic
  workspace versioning; retry recovers a successful lineage write if assessment
  stamping was interrupted. Neither endpoint's evidence text is overwritten.
- **Authority/governance:** use existing human review and separate application;
  scope proof is not acceptance. Authority is copied from declared Source
  authority, never inferred from a filename or arrival time. Existing legacy
  Source-level supersessions are NOT migrated/deleted; a clause application
  encountering whole-source lineage blocks for review. Claude must audit such
  persisted records before enabling authoritative consumption of older data.
- **Must reach ordinary Ask GO:** distinguish proposed/rejected/unresolved
  amendments from accepted-and-applied lineage; show exact clause scope and both
  evidence citations; unaffected clauses remain current. The local detector and
  human routes are wired, but scoped proposal review discovery and ordinary
  Ask GO's end-to-end accepted-lineage interpretation still need incorporation
  and live proof. Do not infer those from the existing generic lineage reader.
- **Must not promote:** automatic authoritative lineage, broad Source endpoints
  for clause changes, ambiguous targets, unreviewed proposals, missing declared
  authority, old erroneous broad edges, or a successful service test as live proof.
- **Bounded limitations:** no multi-paragraph/cross-page clause segmentation,
  no OCR-based scope establishment, no general legal amendment parser, no
  automatic selection among sequential/competing amendments. Unsupported
  directed changes remain unresolved; grammar coverage must not be silently
  broadened during incorporation.

## Gate record and required next phase

Cycle 4 independent gate: **89 passed, 6 subtests passed** (one warning).
Cycles 1–3 regression and broader document-muscle lane: **306 passed,
134 subtests passed** (one warning; 342.82 seconds).
Focused UI-reference guard: **25 passed, 1 warning in 26.14 seconds**.

Exact full repository gate command:
`venv/Scripts/python.exe -m pytest -q -n 8 --dist loadfile --disable-warnings --maxfail=1`
with `PYTHONDONTWRITEBYTECODE=1`.

Exact final result: **9211 passed, 3 skipped, 14 warnings, 10064 subtests passed
in 701.54s (0:11:41)**. Exit code 0. Implementation-tree hashes matched before
and after the gate. No edits or other pytest sessions ran during it.
The earlier missing UI-reference registry failure is resolved.

| Cycle | QUALIFIED | DISTILLED | IMPLEMENTED | GATED | RUNTIME_WIRED | LIVE_REACHABLE |
|---|---|---|---|---|---|---|
| 1 — Certainty | Yes | Yes | Yes | Green | Local ordinary-consumer boundary | Unproven |
| 2 — Situated sheet fields | Yes | Yes | Yes | Green | Local ordinary-consumer boundary | Unproven |
| 3 — Missing-sheet history | Yes | Yes | Yes | Green | Local ordinary-consumer boundary | Unproven |
| 4 — Scoped accepted supersession | Yes | Yes | Yes | Green | Examination + human review/apply | Unproven |

No authority conflict remains in the Cycles 1–4 implementation: automatic
detection creates proposals, unresolved targets cannot establish lineage, and
only the existing accepted authority-moving application path writes the
scoped Supersession. The legacy-data audit noted above remains a production
incorporation obligation, not an automatic data rewrite.

The increment is ready for Claude promotion work. All four cycles remain
**NOT_PROMOTED to live GO** until LIVE_REACHABLE is proven.

Claude must verify this exact implementation, incorporate it into the
authoritative deployed paths without overwriting newer valid work, gate the
resulting tree, deploy, and demonstrate real ordinary-user consumers. Capture
the deployed SHA, fixture/source IDs, persisted records, visible Document Shop
result, Ask GO question/answer and scope/certainty/provenance checks. Cycle 4
also requires a real human review/apply journey and proof that an unaccepted
proposal changes no governing answer. Stop before Cycle 5 unless separately
authorized. No bulk Gym loading or generic tool calling.
