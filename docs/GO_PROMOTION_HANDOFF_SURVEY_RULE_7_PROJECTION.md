# Claude Promotion Handoff: segment projection

Implementation SHA: `0475ad5e49a22a1b48137787e3a180d96a135f10`.
Status: QUALIFIED / DISTILLED / IMPLEMENTED / GATED locally. NOT_PROMOTED until
Claude verifies ordinary LIVE_REACHABLE behavior. No push or deployment.

## Capability and authority boundary

`engine/spatial_compiler.py::project_point_to_segment` extends the existing
geometry owner. It validates explicit chart/plane and Euclidean minimum level,
input finiteness, local differences, segment usability, squared denominator,
numerator, raw parameter, projected point, distance and distance-along. Only
after a finite parameter is proven is it constrained to the segment endpoints.
No physical scale, legal meaning, or evidentiary authority is inferred.

`ToleranceContext.segment_length` centralizes degeneracy tolerance in chart
units. Zero length is ZERO_LENGTH_SEGMENT; below tolerance or squared-norm
underflow is DEGENERATE_GEOMETRY. Non-finite intermediate arithmetic returns
NON_FINITE_DERIVED_VALUE (or NUMERIC_DERIVATION_FAILED for arithmetic exceptions).
Unsafe raw squared norms are refused, not replaced with plausible finite values.
Large origins with modest representable differences remain usable through local
translation. Extreme-length support is not claimed.

The existing `_distance_point_to_segment` wrapper declares the compiler's local
Euclidean frame and raises `SpatialCompilationError` with the structured refusal.
`SpatialCompiler._host_wall` stops placement on failure and validates dimensions,
offset and shift. `SpatialCompilationError.diagnostic` preserves the failed
operator, frame, tolerance and caller-supplied source. The compiler does not
catch that exception and manufacture a partial IFC element.

Unchanged: Rule 6, protected datum bytes, boundary/polygon predicates, and the
committed IFC numeric-admission/emission increment. No new geometry subsystem,
dependency, storage migration or automatic authority transition.

## Fixtures and gates

`tests/test_spatial_compiler.py::TestRule7ProjectionNumericQualification`:

- Interior/before-start/beyond-end projections; large translated origin.
- Exact zero, below-tolerance, squared-norm underflow, calibrated scale-equivalent
  just-above-tolerance segments.
- Non-finite point coordinates; finite inputs overflowing squared norm or raw
  parameter; wall-host placement must return finite values or refuse.
- Coordinate mismatch, plane mismatch, affine-only premise refusal.

Original next-operator gate: 3 failed, 1 passed, 97 deselected, 2 warnings; 0.61s.
Classification: IMPLEMENTATION_DEFECT. No expectation was weakened to pass.

Repair gates:

- Focused projection: 21 passed, 97 deselected, 1 warning; 0.33s.
- Spatial/compiler/IFC/PDF/document-binding lane: 233 passed, 6 subtests; 1.75s.
  This includes the prior numeric, boundary and polygon controls.
- No new full gate yet. Earlier 9,390-pass full gate belongs to numeric validity,
  not this subsequent projection change.

## Runtime, persistence and Ask GO obligations

Actual tested consumer: compiler wall-host placement -> compile_to_ifc -> IFC
validator/exporter. Invalid projection aborts placement/export. The operator's
structured result is not a new evidence store. Persistence/reload and ordinary
Ask GO consumption remain to be qualified by the end-to-end fixture map.
Claude must preserve source, operator, frame, tolerance, error and weaker premise
state through the authoritative evidence route. Ask GO must not treat a refused
placement as factual geometry, and must not print invalid numeric tokens as
measured properties. The projection-only commit claimed no persistence or live
proof; the adapter qualification below adds explicit API-path persistence proof.

## Authoritative evidence-routing and adapter tranche (2026-09-18)

Adapter implementation SHA: pending gated implementation commit. NOT_PROMOTED.
The projection implementation SHA above remains the unchanged mathematics owner.

### Existing authoritative route

Source -> StructuralUnit -> AddressableRegion -> direct-source EvidenceItem ->
existing validator/operator -> calculated_value EvidenceItem -> existing
`derived_from` Relationship and explicit review -> CaseWorkspaceStore reload ->
`project_geometry_evidence` -> existing trust, relationship-status, binding and
anchor-currentness resolvers -> existing examination interpretation/not_established
rows -> unchanged document_conversation.build_context lists -> render_prompt.
The same read-time projection gates `IFCVolumeValidator.export_evidence`, which
applies the scoped result to a copy of the matching candidate and calls existing
wall placement / IFC export. It never exports the unrelated canned candidate as
proof of a geometric derivation.

No new EvidenceItem class, persistence collection, relationship type, parallel
geometry graph, Ask GO context field, dependency or migration. No fixture IDs in
production branches. `document_conversation.py`, `survey_graph.py`, projection
math, central tolerance, Rule 6 and protected datum code are unchanged by this
tranche. The tests assert absence of a geometry_premises context field and exercise
review changes after a finite result was persisted.

The existing calculated EvidenceItem's JSON carries original state, value or
refusal, validation errors, field and affected object ID, source evidence IDs,
premise IDs, operator/version, coordinate space, plane, tolerance context,
read/bind certainty, provenance and uncertainty. AddressableRegion binds the
object. Operator versions are part of the existing versioned operator identifier.
Numeric admission has a strict-finiteness policy rather than a geometric tolerance;
projection and polygon operators retain their existing central tolerance context.
Detailed derivation and trust records remain inspectable on examination rows;
only label/value prose enters the existing context lists.

Review is recomputed on every consumer read, not cached as acceptance. Disputed
links, weak binding, stale premises, counterevidence, malformed records and refused
upstream calculations block factual use/export. Even a confirmed link cannot
upgrade the stored operator result. Original evidence remains unchanged when a
later review produces a weaker consumer state.

An applicable invalid height surfaces UNRESOLVED: "Height could not be
established." Partially recovered evidence remains QUALIFIED in the existing
interpretation list. A missing examination row is a qualification failure, not
NOT_APPLICABLE. No fixture in this map is legitimately NOT_APPLICABLE. Unrelated
natural-language-question applicability and live provider answers remain Claude
incorporation obligations; prompt-boundary qualification is not live answer proof.

### Adapter locations and exact qualification inventory

- `tools/validate_rule7_fixture_map.py`: source/model adapters onto existing
  numeric_validity, polygon_region, semantic binding, project_point_to_segment,
  _host_wall, binding certainty and evidence-trust/currentness resolvers.
- `services/case_workspace.py::project_geometry_evidence`: shared read-time
  projection over existing evidence/review owners; no new storage or authority.
- `services/document_examination.py::_calculated_geometry_lines`: projects that
  same governed result into existing examination rows.
- `engine/ifc_volume_validator.py::IFCVolumeValidator.export_evidence`: scoped
  evidence-to-existing-IFC adapter, with object/frame checks and copied candidate.
- `tests/test_rule7_evidence_routing.py`: end-to-end adapter and adversarial
  governance regression controls.

Map/schema/ID registry: `tests/fixtures/rule7/rule7_fixture_map.v1.json`,
`rule7_fixture_map.schema.json`, `rule7_fixture_map.ids.v1.json`. Suite/schema
version 1.1.0; IDs are retained. Corrections are versioned: FIN-PROV-003 preserves
PARTIALLY_RECOVERED instead of scalar FINITE; FIN-PROV-004 preserves CONTESTED
instead of collapsing it to UNRESOLVED; FIN-DOM-001 cannot promote WEAK to FACTUAL
and now requires QUALIFIED (its operator is still missing).
FIN-ZERO-001 now requires DEGENERATE_GEOMETRY: 1e-200 is nonzero, so geometric
unusability must not be mislabeled exact ZERO_LENGTH_VECTOR. It remains blocked.

All 25 original failures are individually classified, with existing symbol,
required adapter, missing operator and eligibility, in
`tests/fixtures/rule7/rule7_adapter_inventory.v1.json`.
Exact machine-readable run: `tests/fixtures/rule7/rule7_adapter_results.v1.json`.
Command: `venv/Scripts/python.exe tools/validate_rule7_fixture_map.py --all`.
Result: **28 PASS, 0 FAIL, 6 BLOCKED_MISSING_OPERATOR, 0 NOT_APPLICABLE**.
The CLI reports ADAPTERS_PASS_WITH_BLOCKED_OPERATORS and end_to_end_proven=false;
its zero exit status denotes adapter-tranche success, not a complete Rule 7 kernel.
A single blocked fixture returns exit status 2.

Blocked IDs:

- R7-FIN-ZERO-001: vector usability.
- R7-FIN-DOM-001 and R7-FIN-DOM-002: bounded inverse-trigonometric domain handling.
- R7-FIN-TR-001, R7-FIN-TR-002 and R7-FIN-TR-003: homography validation, point
  transform, stable dehomogenization and singularity refusal.

The absent mathematical contracts and existing overlaps are isolated in
`docs/RULE_7B_MISSING_OPERATOR_INVENTORY.md`. No absent operation is implemented
as a convenient harness adapter. Blocked fixtures do not claim completed hops.

### Downstream projection consumers

| Consumer | Classification | Evidence / remaining obligation |
|---|---|---|
| SpatialCompiler projection wrapper | ALREADY_CONSUMES_GOVERNED_RESULT | Explicit-frame projection refuses unsafe arithmetic before returning placement quantities. |
| Wall-host placement | ALREADY_CONSUMES_GOVERNED_RESULT | _host_wall uses that wrapper; finite input overflow still refuses. |
| IFC geometry through export_evidence | ALREADY_CONSUMES_GOVERNED_RESULT | Reloaded evidence/trust governs admission; real wall placement and existing exporter consume eligible results. |
| Document examination | ALREADY_CONSUMES_GOVERNED_RESULT | Calculated rows use the shared read-time projection. |
| Ask GO prompt boundary | ALREADY_CONSUMES_GOVERNED_RESULT | Existing examination lists carry qualified prose; context architecture unchanged. |
| Automatic compiler-output evidence registration | MISSING_WIRING | The harness explicitly registers evidence with production APIs; automatic ingestion and ordinary live reachability are not proven. |
| Generic projective transform consumers | NOT_APPLICABLE | No such operator is implemented in this tranche; six fixtures are explicitly blocked. |

The existing direct IFC API still performs numeric/polygon/semantic admission on
in-memory models. The new evidence-backed API additionally requires the evidence
review chain. This tranche does not claim every pre-existing caller automatically
uses that evidence-backed entry point.

### Gates and promotion boundary

- First invalid-height evidence-route control: PASS.
- All 34 fixtures: 28 adapter passes, six separately reported missing operators.
- Structural validation: 34 fixtures, STRUCTURE_VALID.
- Projection focused gate: 21 passed, 97 deselected.
- Evidence/trust/conversation lane: 366 passed, 87 subtests (466.29s). Includes
  the new routing controls, MM1 evidence contract, MM6 relationships, MM7 governed
  investigation, Document Shop result/conversation and survey-reference controls.
- IFC lane: 86 passed (0.80s).
- Numeric/polygon/boundary regressions: 159 passed, 45 deselected (0.80s),
  across test_ifc_volume_validator.py and test_spatial_compiler.py.

The first evidence-lane attempt failed in pytest temporary-directory setup with
WinError 5, before the affected test bodies. Classified ENVIRONMENT_PERMISSION, then rerun with
approved execution outside the sandbox. No expectation was weakened for it.
No new full-repository gate is claimed for this bounded adapter tranche.

Claude must establish ordinary live incorporation, source/region and review
reachability, actual Ask GO behavior, and retained refusal through that route
before promotion. No push or deployment.
