# Rule 7B projective / homography qualification

Status: **NOT_PROMOTED**. Kernel and API-path qualification are green;
Claude live-incorporation proof remains outstanding.
Baseline: `017f7b29b26b62dba79b64036742f8f5a069891a`, following authoritative
evidence-routing implementation `24058463f7e634cd4b769b9ca94b76bb60616a75`.

## Ownership and mathematical contract

The six blockers were mapped read-only against
`RULE_7B_MISSING_OPERATOR_INVENTORY.md` before implementation. The existing
`engine/spatial_compiler.py` geometry owner now supplies vector usability,
bounded acos intervals, homography validation, dehomogenization, homogeneous
point and line transforms, inversion, composition, vanishing-direction
classification, and horizon-residual classification. Existing numeric admission
and `ToleranceContext` are reused. Restricted display rotations and survey arc
constraints were inspected but are not equivalent projective operators.
No dependency, geometry library, evidence primitive, storage graph or Ask GO
context channel was added. Existing projection/polygon mathematics is retained.

Every result explicitly carries source/target coordinate space and plane,
geometry level, conditioning, uncertainty, operator/version, source provenance,
premises and tolerance context. Accepted spaces are SOURCE_PIXELS,
NORMALIZED_IMAGE, AFFINE_RECTIFIED, EUCLIDEAN_RECTIFIED, WORLD_SCALED and
RECTIFIED_DISPLAY_PIXELS. Labels do not perform conversions. Endpoint mismatch
refuses; same-chart scalar/vector/dehomogenization operations require the same
plane and space. Inversion constructs a new reversed transform.

Column-vector convention: points use Hx; lines use inverse-transpose H. AB
followed by BC composes H2 H1. Singular and unusably conditioned transforms
refuse. Homogeneous canonicalization preserves equivalence and is not evidence
coercion. Dehomogenization uses a scale-normalized W guard; exact infinity,
near infinity and the zero homogeneous vector remain distinct, with no finite
point emitted. Inverse residuals and point round trips use central tolerance.

Geometry levels remain PROJECTIVE -> AFFINE -> EUCLIDEAN -> METRIC_SCALED.
An operator may retain or lower its declared premise level, never earn a higher
level merely from an invertible matrix. A general projective point cannot
authorize Euclidean IFC placement. This tranche supplies no rectification
estimator, camera calibration, image-normalization conversion, horizon fitter
or physical-scale admission. Direction classification does not invent a station,
picture-plane origin or finite vanishing-point position; horizon classification
requires an already observed residual with explicit IMAGE_DIAGONAL units.

## Central qualification defaults and degeneracy

`ToleranceContext` adds vector length 1e-6, normalized homogeneous W 1e-12,
matrix pivot 1e-14, weak/max homography infinity-norm condition 1e8/1e10,
and round-trip residual 1e-9. These are qualification defaults requiring chart
calibration, not universal physical tolerances. Existing boundary/segment
defaults remain 1e-6.

Angular classification is <=0.25 degrees in the parallel/infinity band,
>0.25 and <1 near infinity (including 0.251), and >=1 finite. Exact parallelism
is recorded separately from the tolerance band. Kappa is 1/abs(n dot unit(v)):
<20 good, [20,100) weak, >=100 degenerate. Exact parallelism retains a projective
direction at infinity without serializing infinite conditioning or a finite VP.
Horizon residual <=0.001 is consistent, (0.001,0.003] weak, >0.003 inconsistent.

Tiny mathematically nonzero vectors refuse as geometrically degenerate, distinct
from exact zero. Bounded acos records the original input, original error
interval, explicit domain intersection and conditional angular interval.
Recoverable domain drift remains WEAK; no scalar is silently clamped. Invalid
domain and non-finite derived arithmetic refuse factual use.

## Six fixtures and authoritative end-to-end route

| Previously blocked fixture | Qualified capability | Governing outcome |
|---|---|---|
| R7-FIN-ZERO-001 | Vector usability | DEGENERATE_GEOMETRY; no normalized direction |
| R7-FIN-DOM-001 | Bounded acos | WEAK conditional interval; no factual scalar |
| R7-FIN-DOM-002 | Bounded acos refusal | INVALID_NUMERIC_DOMAIN |
| R7-FIN-TR-001 | Validated H and point transform | Finite [2,3] |
| R7-FIN-TR-002 | Dehomogenization | DEHOMOGENIZATION_UNSTABLE; no finite point |
| R7-FIN-TR-003 | Homography validation | HOMOGRAPHY_SINGULAR |

The unchanged architecture is source StructuralUnit/AddressableRegion and
direct-source EvidenceItem -> authoritative deterministic operator -> calculated
EvidenceItem -> reviewed derived_from Relationship -> CaseWorkspaceStore persist
and reload -> project_geometry_evidence trust/currentness/binding projection ->
existing examination rows -> document_conversation.build_context/render_prompt.
The IFC export_evidence adapter consumes that same reloaded governed result.

The harness adapter in `tools/validate_rule7_fixture_map.py` dispatches by
operator, not fixture ID. The existing calculated-result operator allowlists in
case_workspace and document_examination admit the three newly routed operator
versions. IFC refuses weak intervals, unstable W, singular H and insufficient
geometry level. For admitted points it installs the actual transformed point
before ordinary IFC validation/emission. Evidence trust does not upgrade stored
invalid or weak results. Numeric uncertainty is not mislabeled partial recovery.

Applicable refused conclusions remain UNRESOLVED with ordinary not-established
prose; unrelated evidence may be NOT_APPLICABLE. No invalid machine value or
raw diagnostic replaces that prose. Existing invalid-height control remains
"Height could not be established." Detailed provenance stays in evidence and
examination records, not a second conversation dictionary.

Map/schema/ID registry remain `tests/fixtures/rule7/rule7_fixture_map.v1.json`,
`rule7_fixture_map.schema.json`, `rule7_fixture_map.ids.v1.json` (version 1.1.0).
New run artifact: `tests/fixtures/rule7/rule7b_results.v1.json`.
Result: **34 PASS / 0 BLOCKED_MISSING_OPERATOR / 0 FAIL / 0 NOT_APPLICABLE**.
The historical 28/6 adapter report and inventory remain available. All six
newly unblocked fixtures passed individually before the full map was run.

## Gates and promotion boundary

- Independent operator controls: 52 passed in `tests/test_rule7b_projective.py`.
- Fixture-map structural validator: 34 STRUCTURE_VALID.
- Full fixture map: 34 PASS through the evidence/reload/trust/IFC/context route.
- Projection focused gate: 21 passed, 97 deselected.
- Evidence/trust/conversation lane: 367 passed, 87 subtests (383.64s).
  Files: test_rule7_evidence_routing, test_mm1_evidence_contract,
  test_mm6_relationship_river, test_mm7_governed_investigation,
  test_document_shop_result_01, test_document_shop_conversation_01,
  test_survey_reference_01. Approved execution outside the sandbox supplies
  pytest temporary-directory access.
- IFC lane: test_ifc_volume_validator.py, 86 passed (0.52s).
- Numeric/polygon/boundary regressions: 159 passed, 45 deselected (0.73s),
  across test_ifc_volume_validator.py and test_spatial_compiler.py.
- Frozen-tree full repository gate: **9,523 passed, 3 skipped, 14 warnings,
  10,177 subtests passed in 786.45s (13m06s)**, exit 0. Eight-worker
  `--dist loadfile` mode, repository default selection. All 2,168 captured
  file hashes matched after completion; HEAD remained the baseline above.
- Implementation SHA: `c0e7f72320024e4d422c03083e79ce75bb5c9a1c`.
  This final SHA entry is a subsequent documentation-only commit.

API-path qualification does not establish ordinary live ingestion, automatic
compiler-output evidence registration, UI reachability or provider answers.
Claude must prove live incorporation and retained uncertainty/refusal before
promotion. No push or deployment.

Full-gate command: `pytest -q -n 8 --dist loadfile -p no:cacheprovider`, one run
after all targeted gates; expected 8-12 minutes, anomaly threshold 20 minutes
or stalled progress. Worktree file hashes are captured before/after; log retained
locally under `instance/rule7b_full_gate.log`. Pre-existing unrelated worktree
changes are included in the gate but excluded from the Rule 7B commit.
The hash comparison initially used an unsupported PowerShell AsHashtable
parameter; the compatible read-only rerun compared all files successfully.
Only this handoff's result/SHA finalization follows the frozen-tree gate.
