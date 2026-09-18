# Claude Promotion Handoff: strict boundary semantics

Implementation SHA: `a5bee2c685b63f7ea9b06cb6c77d8ffac82818af`.
**NOT_PROMOTED** until Claude verifies ordinary runtime incorporation and proves
LIVE_REACHABLE. No push or deployment. This is one bounded Rule 7 capability,
not the complete Euclidean/projective kernel.

## Capability and implementation

Boundary contact is not strict containment. `engine/spatial_compiler.py` now
distinguishes INSIDE, ON_BOUNDARY, OUTSIDE and UNRESOLVED via
`classify_point_in_polygon`. The existing Boolean `point_in_polygon` API remains
compatible and returns true only for INSIDE. Its sole production caller was
`SpatialCompiler.compile`; other matches were tests or the separate planning
engine's private `_point_in_polygon`, which is unchanged.

`ToleranceContext.boundary_distance` centralizes the inclusive numerical boundary
band. Its default is 0.000001 in local chart units, matching the compiler's
six-decimal coordinate representation; this is neither physical scale nor an
evidentiary certainty. Other charts require calibrated tolerances. Exact contact
and near-boundary exclusion share ON_BOUNDARY, with numerical distance and
EXACT/APPROXIMATE accuracy retained separately. Invalid tolerance, nonfinite or
degenerate geometry, self-crossing, missing geometry level, and mismatched
spaces/planes refuse as UNRESOLVED with a machine-readable error.

Reuse: the existing deterministic spatial `_distance_point_to_segment`,
`_segments_cross`, `_point_in_ring` and compiler `signed_area`. No new geometry
library or dependency. No protected module changes. Rule 6 remains unchanged.
The explicit classifier requires a declared same-plane coordinate chart and
minimum PROJECTIVE level. Topological use does not earn Euclidean measurements.
The legacy Boolean wrapper retains its historical same-local-Cartesian input
contract; it must not become a shortcut for cross-view operations. Native PDF
user points are explicitly named PDF_USER_POINTS, never mislabeled pixels.

`SpatialCompiler.compile` consumes explicit classification, records
`label_containment` for each label occurrence/space pair, and warns on boundary
or unresolved states. The record preserves source, page, point/polygon, operator
version, plane/space, geometry level, tolerance, distance and result. Neither a
boundary label nor an unresolved result supplies the compiled room name.

## Qualification

`tests/test_spatial_compiler.py::TestRule7ContainmentProof` extends the existing
fixture from version 1.0.0 to 1.1.0 without changing its original expectation.
Positive: clear interior; label slightly inside beyond tolerance binds one room.
Negative: exterior excludes containment. Ambiguous: every edge/vertex, both
windings, either side within the tolerance band, exact shared wall and degenerate
polygon. Two adjacent synthetic rooms and their shared-wall OFFICE label run
through the actual compiler. JSON serialization/reload retains classifications,
provenance and warnings. Existing builder-corpus compiler tests also pass.
Additional refusals: space mismatch, plane mismatch, missing premise/level,
invalid tolerance; calibrated tolerance endpoints are inclusive.

Original red qualification: 7 failed, 16 passed, 43 deselected, 2 warnings,
1.15s. IMPLEMENTATION_DEFECT: half-open ray casting treated some exact boundary
points as inside despite the strict-containment docstring, and the compiler bound
the edge label. Expectations were retained, not rewritten to green.

After repair:

| Gate | Result |
| --- | --- |
| Focused `test_spatial_compiler.py -k 'TestRule7ContainmentProof or TestPointInPolygon'` | 49 passed, 43 deselected, 1 warning; 0.54s |
| Affected lane, sandbox attempt | 92 passed, 2 warnings, 1 setup error; 2.68s. WinError 5 accessing existing pytest temporary directory; environmental permission failure, not a geometry assertion |
| Same frozen affected lane, approved outside sandbox | 243 passed, 18 subtests; 7.22s; exit 0 |

Affected lane: `test_spatial_compiler.py`, `test_pdf_extractor.py`,
`test_mm4_drawing_intelligence.py`, `test_drawing_reference_binding_01.py`,
`test_document_muscles_01.py`, `test_go_pdz_authority_spatial_01.py`.
No code change between either affected-lane attempt. All commands used
`venv/Scripts/python.exe -m pytest -q`, PYTHONDONTWRITEBYTECODE=1.
Dependency/architecture fit check: PASS. No new full gate in this bounded repair;
the prior Rule 6 full-green result does not certify subsequent Rule 7 changes.

## Promotion obligations and exclusions

QUALIFIED / DISTILLED / IMPLEMENTED / GATED locally. Runtime wiring is established
to the existing compiler consumer; ordinary Ask GO consumption is NOT proven.
Claude must preserve `label_containment` through authoritative storage/routing
and surface ON_BOUNDARY/UNRESOLVED rather than flattening either into containment.
Prove shared-wall nonbinding and beyond-tolerance binding in the ordinary user
path, including reload and provenance. Compiled JSON round-trip qualification is
not proof of application persistence or a live Ask GO path.

Do not promote the Boolean wrapper as a typed cross-plane proof API. This change
does not establish physical scale, survey ownership, regulatory authority,
projective rectification, or evidentiary certainty. It assumes polygon input
already represents a closed enclosing boundary in a valid nonsingular chart;
it does not turn loose strokes or raw pixel proximity into that premise. Image
uncertainty calibration, general typed primitives and multi-stage proof records
remain Rule 7 work. A successful numeric classification cannot override a weak
read/bind premise or active confirmed counterevidence.
