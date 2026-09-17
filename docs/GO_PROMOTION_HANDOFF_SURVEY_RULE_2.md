# Claude Promotion Handoff: survey measurement genealogy

Implementation SHA: `73d896663fced6aa3878d64c939c3c47f344bb3a`.
Rule 1 baseline preserved: `39be5e63ad4bf39a66950fa344ac41246b4525f5`.

QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
LIVE_REACHABLE unproven: NOT_PROMOTED until Claude incorporates, gates, deploys
and proves the ordinary live consumer. No push or deployment performed.

## Capability and failure prevented

Preserve multiple measurement occurrences on a segment and select a current
working value only after independent establishment of segment binding,
chronology, measurement role, authority, applicability, and precedence.
Nonempty basis text, numeric closeness, dates alone, optical clarity, or a
model-supplied validation flag cannot establish those premises.

Each premise remains separate. Raw candidates produce proposed EvidenceItems
and provisional supports Relationships. The existing human
`CaseWorkspaceStore.confirm_relationship` path confirms each relationship;
`resolve_relationship_status` handles disputed, rejected, stale, broken and
superseded support. No automatic confirmation or supersession is written.

## Exact changed files and symbols

- `services/survey_graph.py`: `MEASUREMENT_PREMISES`,
  `MEASUREMENT_PREMISE_CONTENT_TYPE`, `measurement_snapshot`,
  `propose_measurement_premises`, `resolve_measurement_premises`,
  `measurement_genealogy`, `_measurement_occurrences`, `normalise_graph`,
  `_distance_of`, `build_primitives`.
- `services/visual_examination.py`: `SYSTEM_PROMPT`,
  `VISUAL_PROMPT_VERSION` (`visual-examination-06`).
- `services/visual_classification.py`: `VISUAL_VERSION` (`visual-examination@6`),
  `VISUAL_VERSION_HISTORY`, `_store_visual_record` proposes review evidence.
- `services/document_examination.py`: `visual_reading` resolves confirmed
  premises at read time; `_visual_lines` surfaces candidates, individual premise
  states/evidence ids, current value or explicit unresolved state.
- `tests/test_survey_reference_01.py::MeasurementGenealogyQualification`.

No new relationship primitive, authority mechanism, service or migration.
The premise payload is a new content type within the existing EvidenceItem;
human review uses existing supports Relationship confirmation, not a second
acceptance channel.

## Fixtures and controls

Synthetic fixed readings: segment S1, M1 = 144.00 m, record survey dated
1990-01-02; M2 = 144.12 m, measured survey dated 2025-03-04. Explicit candidate
link M2 -> M1 remains a proposal until each premise is confirmed.

- Positive: independent confirmations allow M2 as the working measurement;
  M1 remains historical evidence and the numeric difference is descriptive,
  never automatically a contradiction or materiality decision.
- Negative/ambiguous controls for all six axes: ESTABLISHED permits the
  otherwise valid selection; REJECTED or UNRESOLVED on any one axis refuses it.
- Missing date, wrong segment, less-legible current reading, ambiguous role,
  absent precedence and unresolved authority refuse selection.
- Explicitly unresolved prose remains unresolved despite nonempty basis text.
- Extraction-supplied validation flags are discarded during normalization.
- Real examination produces 12 provisional premise edges, not confirmed facts.
  Existing confirmation API makes them available to the selector after reload.
- Disputing a previously confirmed authority edge blocks selection after reload.
- Changing a measurement component invalidates its reviewed snapshot; no cached
  aggregate or clearer old value silently replaces the unresolved current value.

The optical/provider boundary is stubbed: these are controlled binding and
governance fixtures, not proof of OCR accuracy on a real survey.

## Persistence and runtime

Existing visual EvidenceItem retains every supplied occurrence: source plan,
printed value/role, unit, date, read/bind certainty, basis quotations, prior
occurrence link and provenance. Premise proposals are separate persisted
EvidenceItems linked to that visual EvidenceItem. A snapshot covers all
measurement candidates on the segment, so editing a candidate invalidates
earlier confirmations. Projection never edits the original measurement history.

Normal visual worker -> `_store_visual_record` -> proposed premise records ->
existing human Relationship confirmation -> `visual_reading` ->
`_visual_lines` -> Document Shop and `document_conversation.build_context` ->
ordinary document Ask GO prompt. The selector also gates `_distance_of` and
dimension labels in `build_primitives`.

Read-time premise resolution currently uses the Flask application's configured
registry store. Raw graph consumers without a validated read-time projection
remain unresolved. Existing exported/reference artifacts are historical; this
increment does not rewrite an earlier generated artifact after a review.

## Gates

Focused: **5 passed, 1 warning, 25 subtests passed in 10.74s**.

Affected lane: **301 passed, 49 subtests passed in 263.76s**:

```text
venv/Scripts/python.exe -m pytest -q tests/test_survey_reference_01.py tests/test_document_muscles_01.py tests/test_muscle_activation_01.py tests/test_drawing_reference_binding_01.py tests/test_document_shop_result_01.py tests/test_document_shop_conversation_01.py tests/test_document_shop_ocr_reader_01.py -n 8 --dist loadfile --disable-warnings --maxfail=1
```

Scoped diff check passed. No full repository gate for this increment; the
tranche schedules it after Rule 4. Unrelated dirty files were present in the
shared test tree and excluded from this commit.

## Claude incorporation obligations and exclusions

Verify an ordinary reviewer can locate, inspect and confirm the individual
premise proposals through the authoritative review UI. Local tests prove the
store acceptance path and actual outgoing Ask GO prompt, not live UI usability
or model obedience. Do not claim promotion based on these tests alone.

Ask GO must consume the resolved premise projection, preserve all historical
candidates, expose missing premises, and refuse a current value if any required
premise is unestablished. Carry source provenance and independent certainty.

Do not promote proposal text into authority, select by recency/clarity/proximity,
write legal lineage, substitute a clearer old value, or call a numeric difference
a contradiction. No unit conversion, materiality threshold, registered-plan
priority, ownership conclusion or legal precedence hierarchy is invented.
Unproven dates, roles, object identity, applicability and authority stay unresolved.
Human confirmations must establish each particular premise from source evidence;
the presence of a confirmation UI is not evidence that a source has authority.
