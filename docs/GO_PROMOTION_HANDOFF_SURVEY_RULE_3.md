# Claude Promotion Handoff: typed North and directional consumers

Implementation SHA: `3ecef538fe851024dc0ab0e517be2bf8d09d8ae6`.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
LIVE_REACHABLE remains unproven: NOT_PROMOTED pending Claude incorporation,
production gates, deployment and ordinary live Ask GO proof. Nothing deployed.

## Capability and failure prevented

A recovered grid-North note previously reached Ask GO alongside the unqualified
fact `Setbacks: North setback: 5 m`, even though geometric North was unresolved.
Now an unresolved governing North premise constrains semantic consumers as well
as rendering. Readable observations remain preserved with their reference system;
they are not rewritten as true North or discarded as unreadable.

TRUE_NORTH, GRID_NORTH, MAGNETIC_NORTH, ASSUMED_NORTH, OTHER and UNRESOLVED are
separate candidate types. Each carries source region/type, parsed and measured
direction, independent read/bind certainty, provenance and applicability.
Conflicting true-North directions remain unresolved; search priority does not
choose a winner and the resolver does not manufacture an average.

## Authoritative implementation locations

- `services/survey_north.py`: `REFERENCE_TYPES`, `SOURCE_TYPES`,
  `normalise_candidates`, `resolve_true_north`, `directional_observation`,
  `admits_true_direction`, `conversion_snapshot`, `propose_conversions`,
  `resolve_conversions`, `CONVERSION_CONTENT_TYPE`.
- `services/survey_graph.py`: `normalise_graph`, `solve_traverse`,
  `_solve_traverse_relative`, `build_primitives`.
- `services/visual_examination.py`: `SYSTEM_PROMPT`, `_clean_observation`,
  `_attach_measured_north`, `VISUAL_PROMPT_VERSION` = `visual-examination-07`.
- `services/visual_classification.py`: `VISUAL_VERSION` = `visual-examination@7`,
  `VISUAL_VERSION_HISTORY`, `_store_visual_record` proposes conversions only.
- `services/document_examination.py`: `visual_reading`, `survey_reference_of`,
  `_visual_lines`.
- `services/document_conversation.py`: `SYSTEM_PROMPT`, `build_context`,
  `render_prompt` carry the explicit governing true-North premise.
- `services/survey_reference.py`: `derive` retains directional reference,
  `_qualified_reference`, `headline`, `render_pdf` qualify directions at read time.
- `tests/test_survey_reference_01.py::TrueNorthQualification` and the explicitly
  reconciled legacy North/uncertainty assertions.

The commit also records the accepted, still-unimplemented Rule 7 extension in
`docs/SURVEY_GEOMETRY_PROOF_QUALIFICATION_SCOPE.md` and indexes it in MANIFEST.
That scope document is not evidence of a geometry-kernel capability.

## Premises, operators and review boundary

Typed arrow candidates use the existing `measure_north` pixel operator and
`survey_graph._reconcile_north` corroboration gate. Extraction cannot supply
successful measurement flags. Applicable candidates must retain recovered read
and binding certainty, source region, provenance and explicit reference text.
The existing 10-degree corroboration tolerance is retained and exposed; this is
not a newly calibrated universal precision claim.

Notes and baselines remain candidates but do not enter the arrow operator.
A note declaring a reference system does not establish an image direction;
a baseline requires a separately established directional derivation.

An explicit same-view conversion uses a proposed EvidenceItem plus the existing
supports Relationship and human `CaseWorkspaceStore.confirm_relationship`.
`resolve_relationship_status` governs confirmation, dispute, rejection,
supersession and stale/broken endpoints. A snapshot binds review to the complete
candidate and its conversion. Model-provided validation flags are discarded.
No new authority mechanism or relationship primitive is introduced.

The supported offset is explicitly clockwise in this image and bound to
THIS_VIEW. Do not substitute an unproven geographic declination or convergence.
Relative differences between independently established image directions are
marked approximate and scoped to observed image directions, not universal
geodetic transformations or Euclidean rectification.

## Fixtures and controls

- Explicit true-North arrow; true-North symbol in title block; both agree;
  both disagree; grid only; magnetic only; assumed/other; no candidate.
- Rotated image and independent raster-axis measurement.
- Basis note and baseline cannot masquerade as arrow measurements.
- A model-supplied conversion approval is ignored. A real provisional
  conversion remains unresolved, human confirmation enables it after reload,
  and rejection blocks it again.
- Setbacks, frontage/lot-line language, structure descriptions and bearings
  cannot enter recovered true-directional context with an unresolved premise.
- A directional footprint label retains its proven parcel containment but its
  directional meaning is separately qualified as unresolved.
- Historical reference summaries are requalified without mutating their source
  record. Explicit true-bearing requests refuse an unresolved true-North premise.
- Weakening a persisted candidate's binding removes the arrow and directional
  claims after reload; a stale cached aggregate cannot govern consumption.

Pixel fixtures are synthetic. Provider and reply boundaries are deterministic
stubs/spies; expected mathematical angles come from the constructed fixture,
not model behavior. Live provider classification and reply obedience are not
proven by these tests.

## Persistence and runtime consumer map

Normal examination -> normalized graph candidates -> deterministic per-region
arrow measurement -> existing visual EvidenceItem -> reload -> typed resolution.
Optional conversion proposals persist separately and are revalidated from
existing governed Relationships at consumption.

| Consumer | Guard |
|---|---|
| Document Shop evidence lists | `_visual_lines` preserves observation and qualifies directional use |
| Document Ask GO | `build_context`/`render_prompt` carry true-North state and source candidates; system instruction governs directional semantics even in recovered text |
| Current SVG/plan primitives | `build_primitives` requires established true North before emitting its North arrow |
| Explicit true-bearing reconstruction | `solve_traverse(..., reference_type="TRUE_NORTH")` refuses an unestablished premise |
| Relative traverse mathematics | Retains an explicit reference type; unknown reference does not become true North |
| Survey Reference summaries and regenerated PDFs | `_qualified_reference` rechecks directional use of stored observations |
| Current reference graph after conversion review | `survey_reference_of` projects matching confirmed conversion evidence without changing stored history |

Existing downloaded/generated PDF bytes remain historical artifacts; this
increment does not overwrite them. Claude must verify artifact presentation and
regeneration policy during live incorporation, rather than presenting an old
artifact as newly validated output. Non-document Ask GO entry points also need
their own live reachability verification.

## Gate results and classifications

- Broad affected lane: **307 passed, 69 subtests passed in 237.35s**.
- Final Rule 3 + frozen Rules 1/2 controls after the footprint-label guard and
  prompt-shape clarification: **17 passed, 1 warning, 55 subtests passed in 32.70s**.
- Earlier final conversion-focused set: **6 passed, 1 warning, 16 subtests passed
  in 11.90s**; subsequent controls added note/baseline/assumed/other refusals and
  the directional footprint-label regression.

Broad command: the seven-file survey/document lane used in the Rule 2 handoff,
with `-n 8 --dist loadfile --disable-warnings --maxfail=1`.
No full repository gate yet; the tranche requires it after Rule 4.
The shared tree contained unrelated pre-existing changes, excluded from this
commit. Scoped diff checks passed.

Four legacy North assumptions and one literal prompt-wording expectation were
classified EXPECTED_SUPERSESSION before reconciliation. The footprint-label
case was an explained IMPLEMENTATION_DEFECT: containment remained correct while
directional meaning needed qualification. The repair preserves Rule 1's decision
and historical observation. Rule 2's premise-selection behavior is unchanged.

## Claude obligations / do not promote

Verify ordinary live examination collects typed candidates and correctly locates
their source regions. Verify conversion proposals are inspectable/reviewable and
the actual model refuses unproved directional conclusions. Preserve source
provenance, separate certainty, candidate conflicts and rejected history.

Do not promote generic N/angle readings to true North, convert grid/magnetic
directions merely because angles are close, let priority suppress conflict, or
turn image angles into legal bearings, world geometry, ownership or regulatory
authority. Do not promote note/baseline directions without their additional
premises, old artifact bytes as current proof, or the Rule 7 scope as an
implemented projective kernel.
