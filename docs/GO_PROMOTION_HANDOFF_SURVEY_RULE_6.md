# Claude Promotion Handoff: current governing height datum

**NOT_PROMOTED.** Local qualification is not live promotion. No push or deployment.
Implementation SHA: recorded in the follow-up handoff commit after this increment.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
LIVE_REACHABLE remains unproven.

## Qualified capability and failure prevented

Keep a street centerline observation separate from a current governing height
datum. Recovered regulatory text is not established site applicability; geometry
is not regulatory authority. A governing projection requires six independently
reviewed premises: centerline geometry, regulatory requirement, authority,
applicability to the exact subject, selected governing street, and documented
building reference alignment/midpoint. Active confirmed contradiction defeats
establishment; unresolved counterevidence also blocks it.

Currentness follows EvidenceItem -> AddressableRegion/ancestors -> Source, or
EvidenceItem -> Source when regionless. Whole-Source replacement invalidates
dependent present-tense use; scoped replacement affects only its exact evidence
or region ancestry. Historical content remains queryable and is never rewritten.

## Protected-module reconciliation

An earlier affected lane failed with AUTHORITY_CONFLICT: Rule 6 had added
governance policy to the implementation pinned by
`docs/records/datum-lifecycle-transition-01.json`. Original result:
**1 failed, 327 passed, 117 subtests; 286.58s**. The failing node was
`tests/test_survey_reference_01.py::NWorkerIsolation::test_the_flight_deck_projection_carries_no_conflict`.
The record and guard were neither edited nor repinned.

`services/datum_corroboration.py` was restored to the exact protected bytes.
Raw SHA-256: `85d68507261b911c2d0c6f01ea5bd1e0e8af3aef98d29a25a02404e929639be7`.
No deterministic datum mathematics moved. The existing pinned engine still
produces provisional cross-document `corresponds_to` corroboration; that output
does not confer regulatory authority. Its named-level corroboration is distinct
from the survey's centerline candidate evidence and cannot supply missing
applicability, governing-street or building-reference premises.

New unpinned owner: `services/height_datum_governance.py`. Existing homes were
inspected first: `planning_authority` owns injectable acquisition,
`go_pdz_lifecycle` builds validated planning envelopes, `planning_contribution`
handles user contributions, and `document_examination` presents stored state.
Putting candidate proposal writes and this complete review chain in any of those
would cross its existing responsibility. The narrow adapter reuses their
authoritative primitives and introduces no second datum engine, trust engine,
relationship type, authority transition, database or migration.
`tools/dependency_fit.py --name height-datum-governance-adapter`: PASS.

## Exact implementation files and symbols

- `services/height_datum_governance.py`: `HEIGHT_AXES`, `HEIGHT_PREMISE_TYPE`,
  `normalise_height_datums`, `height_snapshot`, `propose_height_datums`,
  `resolve_height_datums`, `height_datum_projection`, `is_height_datum_claim`.
- `services/case_workspace.py`: `CaseWorkspaceStore.resolve_anchor_currentness`,
  `_resolve_mm6_endpoint_status`, `explain_evidence_trust`. Read-only currentness
  projection; existing supersession writers and acceptance rules are unchanged.
- `services/survey_graph.py::normalise_graph`: structured candidate admission.
- `services/visual_examination.py`: `SYSTEM_PROMPT`, `VISUAL_PROMPT_VERSION`
  (`visual-examination-10`) requests candidate evidence, never established status.
- `services/visual_classification.py`: `VISUAL_VERSION`, `VISUAL_VERSION_HISTORY`,
  `_store_visual_record` persists six proposal EvidenceItems and provisional links.
- `services/document_examination.py`: `visual_reading`, `_visual_lines` resolve
  fresh review state and surface status, evidence IDs, certainty and provenance.
- `services/survey_reference.py::_qualified_reference`: legacy free-text datum
  claims remain qualified observations, not governing facts.
- `services/document_conversation.py`: `SYSTEM_PROMPT`, `build_context`,
  `render_prompt` supply HEIGHT DATUM PREMISES to ordinary document Ask GO.
- `tests/test_survey_reference_01.py::SurveyHeightDatumQualification`:
  `datum_reading`, `review_datums`, four qualification tests below.
- `MANIFEST.md` and this handoff document the ownership split and promotion work.

## Fixtures and controls

Hermetic synthetic survey: subject Lot 257 / No. 44, proven-inside building B1,
First Street ST1, observed centerline, explicitly documented reference axis,
synthetic clause 4 and independent authority acquisition with an injected fetcher.
The official-domain URL is a fixture; no live authority fetch or legal conclusion
is used. Existing governed relationship confirmation establishes each premise.

`test_independent_premise_chain_controls_through_persistence_and_consumers`:

- Positive: all six reviewed premises and independent current official authority
  -> GOVERNING_DATUM_ESTABLISHED.
- Negative: no rule -> GEOMETRY_ONLY; explicitly inapplicable ->
  RULE_RECOVERED_NOT_APPLICABLE; curb/road edge -> no centerline substitution.
- Ambiguous: unreviewed applicability, wrong subject, unlinked/obsolete authority,
  weak binding, two street candidates without established selection, missing
  reviewed alignment -> no governing datum (UNRESOLVED,
  APPLICABILITY_UNRESOLVED or DATUM_CANDIDATE as appropriate).
- Confirmed selected-street or authority counterevidence -> CONTESTED.
- Every case reloads from persistence and checks Document Shop and Ask GO context;
  the positive case spies on the actual `dc.ask` gateway prompt.

`test_currentness_scope_history_and_contested_successor`:

- Current Source with region -> eligible when other premises pass.
- Real `register_source_revision` whole-Source lifecycle, with and without region
  -> stale; historical EvidenceItem content remains identical and accessible.
- Accepted datum-region or exact EvidenceItem replacement -> stale.
- Accepted unrelated-clause replacement -> datum evidence remains eligible.
- Current successor initially eligible; confirmed counterevidence then blocks
  the governing projection after another reload.

`test_geometry_observation_survives_without_a_governing_rule` retains geometry.
`test_regulatory_height_datum_claim_requires_separate_authority` prevents a
legible free-text regulatory claim from entering recovered governing facts.

## Persistence, authority and runtime obligations

Runtime: normal visual worker -> graph normalization -> persisted visual and
proposal EvidenceItems -> existing governed review -> workspace reload ->
`document_examination.visual_reading` -> currentness/trust resolution ->
Document Shop and `document_conversation.build_context/render_prompt/ask`.
Snapshots bind reviews to the exact candidate/visual record. Model-supplied review
states are not admitted. No persisted aggregate may override weaker read/bind
certainty. Existing visual versions remain readable; re-examination is deliberate.

Authority requires an independently acquired official planning record, retained
representation with matching provenance hash, exact provision locator/text,
reviewed supporting relationship, current anchors, and separately established
site applicability. Acquisition currentness is not site applicability. Source
revision does not automatically select or approve a successor. Candidate
corroboration, source text and proximity cannot replace any premise.

Ask GO must consume the projected status and all six premise states, evidence
identities, read/bind certainty and provenance. Only GOVERNING_DATUM_ESTABLISHED
permits a current governing statement. Historical evidence may be described as
historical. Missing alignment remains a candidate; curb/road edge, ambiguous
corner selection, stale or contested authority remain non-governing.

Do not promote raw extraction, free-form height-datum sentences, provisional
corroborations, review-looking model fields, or an evaluator-only result. No
physical height calculation, midpoint inference from image appearance, automatic
regulatory interpretation, new supersession write or legal ownership inference
is included.

## Gate record

All runs are sequential, using `venv/Scripts/python.exe -m pytest` and
`PYTHONDONTWRITEBYTECODE=1`; no code edits during each gate.

| Gate | Result after protected reconciliation |
| --- | --- |
| Protected bytes | Raw SHA-256 matches historical protected record exactly |
| `test_survey_reference_01.py -k NWorkerIsolation` | 9 passed, 170 deselected, 1 warning; 9.04s |
| `test_survey_reference_01.py -k SurveyHeightDatumQualification` | 4 passed, 175 deselected, 22 subtests, 1 warning; 85.41s |
| Source revision/supersession/trust lane | 164 passed, 4 subtests, 1 warning; 27.25s |
| Survey/planning/document lane, 8 workers/loadfile | 422 passed, 117 subtests; 346.44s |
| Full repository gate, 8 workers/loadfile | **9257 passed, 3 skipped, 14 warnings, 10168 subtests; 731.79s; exit 0** |

Exactly one full gate ran after reconciliation. SHA-256 snapshots of 1,368 code,
test, configuration and documentation files were identical before/after the gate;
HEAD remained `159a8a5a7a9932e1d42b589a67c927acc5e13a53` until committing this
increment. No overlapping writer was observed. Pre-existing unrelated dirty
planning/feasibility work was included in the tested tree but excluded from the
Rule 6 commit. Only this gate record and implementation-SHA documentation were
finalized afterward. A staging whitespace check also removed one trailing blank
line from the new adapter; no executable code changed.

Source lane files: `test_comm_i4a_source_revision_generalization.py`,
`test_supersession_authority.py`, `test_b2_supersession_linkage.py`,
`test_mm2_pdf_document_intelligence.py`, `test_mm6_relationship_river.py`,
`test_mm7_governed_investigation.py`, `test_storage_bridge_trust_02.py`.

Survey lane files: `test_survey_reference_01.py`,
`test_survey_notation_qualification.py`, `test_datum_corroboration_01.py`,
`test_datum_corroboration_wiring_01.py`, `test_go_pdz_authority_spatial_01.py`,
`test_document_muscles_01.py`, `test_muscle_activation_01.py`,
`test_drawing_reference_binding_01.py`, `test_document_shop_result_01.py`,
`test_document_shop_conversation_01.py`, `test_document_shop_ocr_reader_01.py`.

## Claude live proof still required

Verify the committed adapter and currentness helper, incorporate through the
authoritative production review path, gate, deploy, and prove ordinary Ask GO
receives the qualified status. Demonstrate a fully reviewed current positive,
geometry-only negative, obsolete whole-Source and scoped-clause cases, unaffected
clause, regionless evidence, contested successor and unresolved corner/alignment
cases. Show historical evidence still accessible and governing language withheld
in every non-established case. Verify the protected datum engine/worker hashes
remain intact. Until this is shown, Rule 6 is **NOT_PROMOTED**.
