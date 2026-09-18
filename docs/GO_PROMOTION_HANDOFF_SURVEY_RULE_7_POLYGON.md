# Claude Promotion Handoff: polygon validity before IFC space export

Implementation SHA: `ef8a621cfdf278c228898f6a278937f9bc36c877`.
**NOT_PROMOTED**. QUALIFIED / DISTILLED / IMPLEMENTED / GATED locally;
RUNTIME_WIRED to the existing compiler/IFC consumer. Ordinary Ask GO and
LIVE_REACHABLE remain unproven. No push or deployment.

## Capability and authoritative implementation

Closure is necessary but insufficient for a planar region. A valid region is
also insufficient to establish a semantic room identity. IFC export now requires
both geometric validity and independently rechecked strict label binding.

`engine/ifc_volume_validator.py::polygon_region` returns VALID_REGION, COLLINEAR,
ZERO_AREA, SELF_INTERSECTING, INSUFFICIENT_VERTICES, DEGENERATE or UNRESOLVED,
with error code, context, operator version, signed/absolute area and tolerances.
It verifies finite coordinates, distinct vertices, explicit closure, nonzero
extent, non-collinear support, sufficient area and a simple region. One repeated
first/last vertex is closure, not a duplicate defect. Other repeated vertices
refuse. Missing/weak/contested geometry, per-vertex uncertainty, and plane/space
mismatch cannot become valid by numerical area alone.

Reuse: existing `engine/spatial_compiler.py::ToleranceContext`,
`classify_point_in_polygon`, `signed_area`, and deterministic spatial
`_segments_cross`. No new geometry library or tolerance epsilon. The area
exclusion band is the centralized boundary distance multiplied by perimeter,
in chart units squared. Signed area is computed after translating to the first
vertex to reduce large-origin cancellation. Boundary classification behavior
from `a5bee2c685b63f7ea9b06cb6c77d8ffac82818af` remains unchanged.

`IFCVolumeValidator.validate` calls the region classifier before export and
`_semantic_binding_established` before admitting a space. The latter consumes
existing `label_containment` occurrences, checks source/scope and read/bind
certainty, and recomputes strict containment against the current polygon. A
cached INSIDE state, a name alone, an edge label, contested evidence, or multiple
interior labels cannot supply semantic identity. Invalid geometry or unresolved
binding raises IFCValidationError before any STEP text is produced.

`engine/spatial_compiler.py::SpatialCompiler.compile` now carries
`geometry_context` per candidate space and read/bind certainty on retained label
occurrences. Native PDF extraction's schema and coordinate convention establish
the producer frame; unknown input remains unresolved. Explicitly weaker or
contested page premises are retained. `services/binding.bound_certainty` applies
the existing structural-binding ceiling. This is a deterministic compiler input
contract, not a new authority mechanism or a claim that arbitrary model-supplied
metadata proves itself. Inputs must reach this boundary through their governed
producer; remote/model payload admission is not qualified by these tests.
The producer also carries weaker vector and label read/bind components and
counterevidence flags. Because the legacy loop assembler lacks per-edge evidence
IDs, an uncertain vector conservatively constrains the page's exported spaces;
identical label text shares the weakest retained text premise. This may abstain
more broadly than a future occurrence-scoped producer, never more confidently.

Changed files: `engine/ifc_volume_validator.py`, `engine/spatial_compiler.py`,
`tests/test_ifc_volume_validator.py`, `tests/test_spatial_compiler.py`, `MANIFEST.md`,
`docs/SURVEY_GEOMETRY_PROOF_QUALIFICATION_SCOPE.md`, this handoff.
Rule 6 files and protected datum bytes are unchanged.

## Fixtures and controls

`tests/test_ifc_volume_validator.py::room_model` is synthetic same-plane drawing
geometry. Fixture version 2.0.0 adds explicit geometry context and independently
located label evidence. This is EXPECTED_SUPERSESSION of the old test's implicit
assumption that a supplied room name alone proved binding; geometric expectations
remain unchanged. No test expectation was weakened.

- Positive: rectangle; explicitly closed triangle; a single interior label.
- Negative: three/four collinear points; insufficient distinct vertices;
  duplicate collapse; self-intersecting bow-tie; open boundary.
- Ambiguous: area below the centralized exclusion band, weak geometry/vertex,
  contested geometry, missing context, mixed coordinate spaces or planes.
- Semantic controls: name-only input, boundary label with stale cached INSIDE,
  weak/contested label and wrong-plane label all refuse export.
- Existing native-PDF builder corpus proves compilation and IFC export still
  work; the original Rule 7 boundary controls remain green.

Tests: `test_rule7_closed_chain_must_establish_a_region_before_volume_export`,
`test_polygon_states_keep_topology_separate_from_area`,
`test_polygon_premises_cannot_be_promoted_by_area`,
`test_valid_geometry_does_not_establish_semantic_identity`.

Original red: 1 failed, 6 passed, 2 warnings, 0.21s. IMPLEMENTATION_DEFECT:
the validator checked closure/intersections but admitted a collinear zero-area
loop and emitted an IFC space. The failure is preserved here, not retried away.

| Gate | Result |
| --- | --- |
| Focused `tests/test_ifc_volume_validator.py` | 26 passed, 1 warning; 0.20s |
| Compiler / IFC / PDF / drawing-reference-binding lane | 147 passed, 6 subtests; 1.16s |
| Rule 7 boundary regressions | 49 passed, 43 deselected, 1 warning; 0.77s |
| Added native vector/text uncertainty controls, initial targeted run | 76 passed, 45 deselected, 1 warning; 1.37s |
| Final focused polygon/semantic/native-premise controls | 78 passed, 45 deselected, 1 warning; 0.69s |
| Final affected compiler/IFC/PDF/binding lane | 152 passed, 6 subtests; 2.91s |
| Final boundary regressions | 49 passed, 48 deselected, 1 warning; 0.60s |

Additional native-corpus test:
`TestEndToEndToIFC.test_rule7_weak_native_input_cannot_become_an_exportable_space`
checks page uncertainty, vector binding uncertainty, label read/bind uncertainty,
and contested labels through compile -> actual export refusal.

Commands used `venv/Scripts/python.exe -m pytest -q`,
PYTHONDONTWRITEBYTECODE=1. Affected lane files:
`test_spatial_compiler.py`, `test_ifc_volume_validator.py`,
`test_pdf_extractor.py`, `test_drawing_reference_binding_01.py`.
No full-repository result is claimed for this bounded increment.

## Runtime, persistence and Claude obligations

Existing path: PDFVectorExtractor -> SpatialCompiler.compile ->
IFCVolumeValidator.validate/export. Model JSON carries source/plane/context and
retained occurrence evidence; validation recomputes rather than trusts cached
classification. No schema migration or historical rewrite. Legacy models lacking
context or label evidence now refuse IFC export instead of guessing. Application
persistence/live routing of these additional fields still requires Claude proof.

Ordinary Ask GO must distinguish geometric region validity from semantic room
binding, consume unresolved/refusal states and provenance, and never describe a
zero-area loop as a valid space. Claude must verify authoritative producer
admission, retain the context/label evidence through persistence and reload, gate,
deploy and demonstrate positive and refused IFC/user-facing cases live.

Do not promote arbitrary JSON certainty flags as verified evidence, recorded
authority as established authority, chart area as physical area, geometry as
ownership, or a polygon as a named room without semantic binding. No homography,
rectification, physical scale, general 3D validity, or live Ask GO capability is
claimed. The complete Rule 7 kernel remains unfinished.
