# Claude Promotion Handoff: survey Rule 1

Implementation commit: `39be5e63ad4bf39a66950fa344ac41246b4525f5`.

Status: QUALIFIED, DISTILLED, IMPLEMENTED, GATED (requested local lanes),
RUNTIME_WIRED. LIVE_REACHABLE is unproven; NOT_PROMOTED pending Claude's
production incorporation, gates, deployment and live consumer proof.
Rule 2 has not started. Nothing was pushed or deployed.

## Capability and prevented failure

Separate an observed building from a building proven inside the identified
subject parcel. Previously, the aggregate observation reached Ask GO as
`Existing building: Building A; Building B; Building C`, although B and C were
neighboring structures. Optical recovery must not establish parcel containment.

Only a footprint classified INSIDE_SUBJECT_PARCEL produces
`Existing building on subject property: Building A`.
OUTSIDE_SUBJECT_PARCEL remains explicitly labeled neighboring context.
TOUCHES_BOUNDARY, CROSSES_BOUNDARY and UNRESOLVED do not produce subject-property
building claims. Original observations and neighboring footprints remain stored.

## Exact implementation

- `services/survey_graph.py::footprint_containment`: validates explicit subject
  identity binding and the closed, ordered boundary; compares observed outlines
  with existing `deterministic_spatial` predicates. Checks component certainty
  again at consumption; does not trust cached containment.
- `services/survey_graph.py::normalise_graph`: persists `subject_parcel`
  (identity, boundary segment ids, read/bind certainty, binding basis, provenance)
  and per-footprint containment, provenance, occurrence id and separate certainty.
  Retains an occurrence with an invalid outline as unresolved.
- `services/visual_examination.py::SYSTEM_PROMPT`, `VISUAL_PROMPT_VERSION`:
  requires explicit source identity/boundary evidence and individual footprints;
  generation is `visual-examination-05`.
- `services/visual_classification.py::VISUAL_VERSION`, `VISUAL_VERSION_HISTORY`:
  current job generation `visual-examination@5`; generations 1–4 stay recognized
  as completed historical work. Deployment alone does not re-examine them.
- `services/document_examination.py::_visual_lines`: replaces unqualified survey
  building aggregation with occurrence-specific subject/context/unresolved lines.
  Both `build_result` and `document_conversation.build_context` use these lines.
- `tests/test_survey_reference_01.py::SubjectContainmentQualification` and
  `BRasterSurvey.test_the_result_page_shows_what_was_recovered_and_not_a_missing_text_layer`.

These are the five changed implementation/test files. No new service, dependency,
relationship primitive, or authority mechanism was introduced. The occurrence-local
`contained_by` result is inside the existing visual EvidenceItem payload, scoped
by its source and graph occurrence/segment ids; it is not a new authoritative
kernel Relationship or a legal determination of ownership.

## Fixtures and controls

Hermetic fixed provider readings use Lot 257 / No. 44, a rectangular closed
boundary S0–S3, Building A inside, and Buildings B/C outside on either side.
The upload is a synthetic raster; these tests qualify binding and consumption,
not optical recognition accuracy on a real survey.

- Positive: inside A is included as a subject-property building.
- Negative: B/C remain persisted and visible as neighboring context; neither
  enters a subject-property statement.
- Ambiguous: crossing and touching footprints remain unresolved for containment.
- Unbound: visible A and its original observation survive without subject identity;
  no subject-property claim reaches Document Shop or the actual Ask GO prompt.
- Stale aggregate: persist an inside result, weaken an edge, save and reload through
  a fresh CaseWorkspaceStore. Both consumers recompute unresolved containment.
- Additional refusals: uncertain edge, identity missing, proximity binding,
  open boundary, curved boundary, and invalid footprint coordinates.

The legacy raster assertion is classified STALE_PRE_CONTAINMENT_EXPECTATION.
It now proves completed visual examination, preserved building evidence, explicit
unresolved containment, and absence of false missing-text/no-reading messages.
No additional stale or genuine containment failures appeared in the broader lane.
An initial new-test duplicate-project-name error was corrected with distinct
control names; it never reached the containment implementation.

## Gate evidence

Focused Rule 1 plus affected BRasterSurvey: **15 passed, 1 warning,
10 subtests passed in 36.80s**.

Broader command:

```text
venv/Scripts/python.exe -m pytest -q tests/test_survey_reference_01.py tests/test_document_muscles_01.py tests/test_muscle_activation_01.py tests/test_drawing_reference_binding_01.py tests/test_document_shop_result_01.py tests/test_document_shop_conversation_01.py tests/test_document_shop_ocr_reader_01.py --disable-warnings --maxfail=1
```

Result: **296 passed, 1 warning, 24 subtests passed in 282.32s (0:04:42)**.
Scoped `git diff --check` passed. The full repository gate was not run for this
increment. Tests ran in the shared tree with unrelated pre-existing changes;
those files were neither staged nor committed with Rule 1.

## Runtime destination and Claude obligations

Normal visual worker examination → `visual_examination.normalise_payload` →
`survey_graph.normalise_graph` → existing visual EvidenceItem persistence →
workspace reload → `document_examination._visual_lines` → Document Shop result
and `document_conversation.build_context` → `ask` model boundary.

Claude must incorporate the exact implementation, run production incorporation
gates, and prove this behavior through ordinary Document Shop / Ask GO. The local
tests use a gateway spy and prove the actual outgoing prompt, not live model
obedience or live availability. Check any other ordinary Ask GO entry point
before declaring broader runtime reachability.

For property-specific questions, Ask GO must use only proven-inside occurrences
as subject-property structures. Neighboring structures may appear only as
explicit neighboring context; unresolved observations must not acquire ownership
or containment from the user's question. Verify persisted provenance, boundary
ids, occurrence ids and separate read/bind certainty remain accessible live.

## Authority constraints and unresolved exclusions

Coordinates are observed source-image fractions, not cadastral or legal geometry.
No page-up/North shortcut, proximity-only identity, inferred structure type,
invented closing edge, legal ownership, or regulatory authority is promoted.
Subject identity requires explicit source evidence with a declared/structural
binding; model assertion or proximity cannot reach recovered containment.

This increment qualifies simple straight closed boundaries only. Curved/open,
invalid or uncertain boundaries remain unresolved. A conservative .002
image-fraction exclusion band prevents near-edge inclusion; it is not a legal
survey tolerance. Unsupported complex parcel topology is not qualified here.
Historical readings without subject binding remain readable but unresolved for
containment; no history migration or automatic re-examination is authorized.

Do not promote cached inside classifications, aggregate building sentences,
neighboring structures as subject buildings, evaluator artifacts as live proof,
or any of survey Rules 2–6 under this handoff.
