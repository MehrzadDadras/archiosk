# Claude Promotion Handoff: segment projection

Implementation SHA: pending implementation commit.
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
measured properties. No persistence or live proof is claimed by this handoff.
