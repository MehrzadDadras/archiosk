# Claude Promotion Handoff: survey notation and conditional curve geometry

Implementation SHA: `a19403b7c028cd6471cea4319128c1f8d3db2c8c`.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
LIVE_REACHABLE is unproven: **NOT_PROMOTED** until Claude verifies,
incorporates, gates, deploys and proves ordinary live Ask GO consumption.
No push or deployment was performed.

## Capability and prevented failure

Parse explicit printed quadrant bearings instead of trusting a supplied numeric
azimuth. Preserve the printed text and claimed number independently; disagreement,
invalid notation or absent bearing refuses a computed azimuth. Read and binding
certainty remain separate and persisted aggregates cannot strengthen them.

Radius/chord constrain a conditional circular-arc family. They do not select a
minor rather than major arc, prove placement, establish a Euclidean image frame,
or remove perspective distortion. The old renderer silently made those choices.
It now retains curve parameters and draws only a qualified endpoint connection,
with curvature/branch/frame unresolved. No default left bulge or frontage-based
minor-arc assumption remains. Missing curve data stays partial; inconsistent
radius/chord values remain a conflict. Era never supplies missing evidence.

## Exact implementation and runtime destination

- `services/survey_graph.py`: `_printed_azimuth`, `_bearing`, `_azimuth_of`,
  `segment_inputs`, `normalise_graph`, `curve_constraints`,
  `_arc_from_chord_and_radius`, `build_primitives`.
- `services/visual_examination.py`: examination prompt generation 08 preserves
  explicit bearings, contextual curve notation, radius/chord/arc_length/delta.
- `services/visual_classification.py`: `VISUAL_VERSION` generation 8;
  generations 1–7 remain recognized without automatic re-examination.
- `services/document_examination.py::_visual_lines`: printed notation,
  reference system, read/bind certainty, curve parameters and unresolved uses
  reach Document Shop and `document_conversation.build_context/render_prompt`.
- `tests/test_survey_notation_qualification.py::SurveyNotationQualification`;
  `tests/test_survey_reference_01.py::SurveyNotationRuntimeQualification` and
  `ZDimensionOnlySheets`; `MANIFEST.md` records the qualification files.

Normal path: intake → visual worker → normalized graph in the existing visual
EvidenceItem → reload → examination → Document Shop / ordinary Ask GO context.
The existing SVG and PDF primitive consumers share the refusal. No alternate
survey subsystem or geometry library was introduced.

## Fixtures and controls

- Positive: NE/SE/SW/NW quadrant strings and degree/minute/second notation;
  conditional radius 10 / chord 10 yields minor 60° and major 300° alternatives.
- Negative: numeric azimuth with unprinted `b`; printed/numeric disagreement;
  angle outside quadrant range; impossible chord greater than diameter;
  incompatible radius/chord units; persisted strong aggregate over weak binding.
- Ambiguous: missing bearing; missing/unbound curve parameters; a lone C label
  does not change a straight segment into a curve; raw image endpoints cannot
  prove a circular arc even with readable radius/chord and asserted bulge side.
- Runtime fixture: one mixed-completeness synthetic survey passes through the
  worker, persistence, fresh store reload, real Document Shop result route and
  ordinary Ask GO context. Old dimension-only, explicit-bearing, contextual
  curve and ambiguous-C occurrences remain distinct.
- The closure regression's placeholder `b` was classified EXPECTED_SUPERSESSION
  and replaced with explicit printed cardinal quadrant bearings. Its closure
  and non-closure assertions were retained.

## Gate evidence

- Final focused gate: 24 passed, 53 subtests, 1 warning (26.81 seconds).
- Survey/document lane before final bearing-component tightening: 309 passed,
  69 subtests (288.35 seconds).
- Final frozen-tree full gate: `pytest -q -n 8 --dist loadfile`;
  **9245 passed, 3 skipped, 14 warnings, 10127 subtests passed in 705.75 seconds**;
  exit 0. Hashes of all survey implementation/fixture files and MANIFEST were
  unchanged across the run. The workspace also held pre-existing unrelated
  planning/feasibility edits; those were not included in this commit.

## Persistence, governance and Ask GO obligation

Source observations remain historical evidence. Read-time bearing checks cover
older persisted graphs too. New curve parameters use the existing value/binding
schema; enclosing visual EvidenceItem/source and segment identifiers retain
traceability. No existing persisted records are migrated or rewritten.

Ask GO must consume the uncertainty alongside the readable values. It must not
turn parsed bearing into true North, partial binding into recovered binding,
an arc family into a chosen arc, or image coordinates into legal survey geometry.
Rules 1–3 remain governing, including measurement precedence and typed North.

Do not promote an era heuristic, page-orientation bearing, C-only classification,
implicit scale, invented curve branch, ownership conclusion, or regulatory datum.
This is not the Rule 7 projective proof kernel. Full metric rectification,
calibrated tolerances and generalized geometric derivation records remain pending.
Already-generated historical PDF bytes are not rewritten; Claude must verify
current ordinary consumers and distinguish historical artifacts during live proof.
