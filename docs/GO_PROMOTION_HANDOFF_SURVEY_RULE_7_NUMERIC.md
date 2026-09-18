# Claude Promotion Handoff: finite geometric quantities

Implementation SHA: pending green milestone gate and implementation commit.
**NOT_PROMOTED** until Claude proves ordinary LIVE_REACHABLE behavior.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED locally; focused, affected and
milestone full gates green. Runtime consumer: existing IFC admission/export.
No push or deployment. This is not the complete Rule 7 proof kernel.

## Qualified capability and implementation

A geometric quantity must be finite before use. Invalid numeric input is never
clamped, coerced or substituted. `engine/ifc_volume_validator.py::numeric_validity`
classifies FINITE, NON_FINITE and UNRESOLVED without conversion. Booleans,
strings, missing values and integers outside the float engine's representable
range are unresolved. NaN, positive infinity and negative infinity are non-finite.
Being finite does not establish positivity, units, authority, or certainty.

Existing numeric seams were inspected before adding this narrow admission gate:
`survey_graph._num` coerces strings and returns None; `derivation_check._numbers`
converts numbers but does not exclude non-finite floats. Neither provides this
strict state/provenance contract; neither was changed. The gate stays in the
existing IFC validator rather than creating a parallel geometry service.

Authoritative changed symbols in `engine/ifc_volume_validator.py`:

- `numeric_validity`, `_require_finite`: one finite-number decision and refusal.
- `_numeric_inputs`: validates required numeric fields before geometric checks:
  space heights, polygon coordinates, wall endpoints/heights/thicknesses,
  opening offsets/widths/heights, level elevations, retained label coordinates
  and any present derived scale/measurement metadata.
- `_numeric_derivation`: arithmetic overflow/domain errors become governed
  numeric failures, not a fallback or an unhandled arithmetic exception.
- `IFCVolumeValidator.validate`: finite inputs precede region/semantic checks;
  computed wall length, opening extent and available area outputs are gated too.
- `_Step.add`: final nested numeric-emission check before an entity is appended.
- `IFCValidationError`: optional structured `diagnostic`, preserving existing
  exception compatibility. It identifies unresolved geometry, numeric state,
  source, field, stage and stable failure code; it does not describe an invalid
  token as a measured height or thickness.

No changes to the committed boundary classifier, polygon classifier, semantic
binding predicate, Rule 6, or protected datum bytes. Earlier region/binding
requirements still apply independently; a finite value cannot override them.
No storage migration, authority mechanism, or new numerical dependency.

## Fixtures and controls

Existing synthetic `room_model` supplies a valid region and a proven interior
label. `tests/test_ifc_volume_validator.py` now qualifies:

- Positive: finite height, thickness and endpoints reach real IFC export.
- Negative: NaN/+Infinity/-Infinity in 15 geometric fields/locations each refuse.
  This includes every wall endpoint coordinate, mixed polygon coordinates,
  openings, elevations, label points and retained derived scale metadata.
- Ambiguous: nonnumeric strings, booleans, missing values and unrepresentable
  integers remain UNRESOLVED rather than becoming numbers.
- Finite inputs causing wall-length overflow, opening-extent overflow or
  point-to-boundary distance arithmetic overflow refuse before export.
- A non-finite computed STEP argument is refused before entity storage.
- Source records are unchanged after refusal. Diagnostics serialize with
  `allow_nan=False`, retain source/field provenance and avoid invalid-value prose.

Exact tests: `test_rule7_nonfinite_dimensions_cannot_earn_a_volume`,
`test_numeric_validity_is_strict_and_does_not_coerce`,
`test_finite_inputs_with_nonfinite_derivation_are_refused`,
`test_step_emission_checks_derived_numeric_outputs_before_storage`, and the
existing positive `test_room_and_wall_export_to_ifc`.

Original red: **6 failed, 1 passed, 25 deselected, 2 warnings; 0.61s**.
IMPLEMENTATION_DEFECT: comparisons such as `height <= 0` did not prove
finiteness, so invalid quantities reached the actual exporter. Expectations
were preserved and extended to negative infinity and derived failures.

## Numerical-path inspection

The IFC writer has no homography/dehomogenization path. Existing drawing/view
transforms are rotation/mirror operations, not a qualified rectification engine;
none was extended here. Compiler projection has a zero-length branch before
division; its square root uses a sum of squares. The boundary classifier refuses
sub-tolerance edges before its distance arithmetic. Overflow in a finite-input
containment calculation was nevertheless reproduced and now yields a structured
numeric refusal at IFC admission. Scale/spacing division can produce unusable
metadata; present derived scale and measured-elevation fields are explicitly
gated before export. Near-zero remains a geometric/tolerance question even when
finite; this increment does not pretend finiteness proves conditioning.

## Gate record

| Gate | Result |
| --- | --- |
| Focused numeric/derived/emission controls | 61 passed, 25 deselected, 1 warning; 0.29s |
| Affected IFC/compiler/PDF/document-binding lane | 212 passed, 6 subtests; 1.96s |
| Rule 7 polygon/boundary/semantic regressions | 79 passed, 104 deselected, 1 warning; 0.64s |
| Periodic full gate for the combined IFC-admission milestone | 9,390 passed, 3 skipped, 14 warnings, 10,168 subtests passed; 732.38s; exit 0 |

Full command: `venv/Scripts/python.exe -m pytest -q -n 8 --dist loadfile`.
The 1,371-file before/after snapshot was identical; no overlapping writer was
observed. Protected datum SHA256 remained
`85d68507261b911c2d0c6f01ea5bd1e0e8af3aef98d29a25a02404e929639be7`.
The full gate covers the frozen working tree, including preserved pre-existing
uncommitted work; that unrelated work is excluded from this increment's commit.

Commands used `venv/Scripts/python.exe -m pytest -q`, with
PYTHONDONTWRITEBYTECODE=1. Affected lane: `test_spatial_compiler.py`,
`test_ifc_volume_validator.py`, `test_pdf_extractor.py`,
`test_drawing_reference_binding_01.py`. Runs are sequential.

## Persistence/runtime and Claude obligations

Existing compiler -> IFC validator -> STEP writer is the actual tested consumer.
Input source evidence remains untouched. A caller can retain the structured
refusal with provenance using existing evidence infrastructure; no separate
failure store was introduced. Application persistence/reload and ordinary Ask GO
routing of the diagnostic are not proven by these isolated tests.

Claude must verify the producer/consumer boundary, preserve diagnostics through
the authoritative evidence path, gate and prove live refusal. Ordinary Ask GO
must receive unresolved/invalid geometry with source and failed-field provenance,
never a measured-property sentence containing NaN or infinity. Do not promote
the report alone, raw malformed model JSON, silent numeric replacement, or
numeric validity as authority, geometry level, physical scale or semantic identity.
