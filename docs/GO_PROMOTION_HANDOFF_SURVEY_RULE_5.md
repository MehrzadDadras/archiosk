# Claude Promotion Handoff: scoped public access

Implementation: `a423d7901adb75be2f84e6f9273fee275ff7e54c`.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
**NOT_PROMOTED**: Claude must verify, incorporate, gate, deploy and prove
LIVE_REACHABLE through ordinary Ask GO. Nothing pushed or deployed.

## Capability and failure prevented

Preserve separate access-edge occurrences and their street, sidewalk, landscape
strip, curb, curb cut, driveway, pedestrian approach and building-entry evidence.
Street adjacency does not establish primary access or building front. Missing
entry evidence does not prove no access. Multiple primary claims, including an
unresolved competing claim, prevent automatic selection.

Access interpretation reuses the existing EvidenceItem proposal and `supports`
relationship confirmation path. No automatic authority transition or second
approval mechanism was introduced. An exact-source review is necessary but not
sufficient: required feature bindings, traceable regions, subject edge and
Rule 1 building containment must also hold. Physical access classification never
establishes ownership, legal frontage, zoning applicability or a height datum.

## Exact changed implementation

- `services/survey_graph.py`: `ACCESS_CONTENT_TYPE`, `ACCESS_CLASSES`,
  `ACCESS_FEATURES`, `_access_occurrences`, `access_snapshot`,
  `propose_access_interpretations`, `resolve_access_interpretations`,
  `access_interpretations`, `normalise_graph`.
- `services/visual_classification.py::_store_visual_record`: registers proposal
  evidence and provisional existing relationships; processing generation 9.
- `services/visual_examination.py`: generation 09 extraction instructions;
  historical processing generations remain recognized without re-examination.
- `services/document_examination.py::visual_reading`, `_visual_lines`:
  resolve current review state and surface scoped results, independent feature
  certainty, provenance and review evidence IDs in Document Shop and Ask GO.
- `services/document_conversation.py::SYSTEM_PROMPT`: access-use obligations.
- `tests/test_survey_reference_01.py::SurveyAccessQualification` and MANIFEST.

Runtime: normal intake → visual worker → existing visual EvidenceItem plus
proposal EvidenceItems → existing relationship review → fresh store reload →
examination → Document Shop / `document_conversation.build_context/render_prompt`.
The consumer recomputes validation; extraction cannot supply validation flags.
Snapshots bind reviews to exact occurrences and visual evidence IDs. Changed,
pending, disputed or rejected evidence cannot inherit an accepted interpretation.
All source candidates remain preserved; projections do not overwrite history.

## Fixtures and controls

Synthetic closed subject parcel and contained building reuse the Rule 1 fixture.
A separately documented entry/access detail supplies explicit source regions,
feature-to-edge bindings, public-street status and a printed main-entry role.

- Positive: confirmed primary access; separate sidewalk/landscape/curb/cut/walk/
  driveway observations; secondary access and rear service access; explicit
  no-access edge alongside another established primary edge.
- Negative: adjacency alone, missing subject parcel, wrong-edge binding, missing
  entry region, unbound entry relationship, absent approaches; free-form main-entry
  text does not become a recovered access-selection claim.
- Ambiguous: corner site with competing primary candidates; one reviewed primary
  and another unresolved primary; contradictory access/no-access evidence.
- Persistence/runtime: real worker/store reload, existing human confirmation,
  Document Shop result route, ordinary Ask GO context, stale snapshot refusal,
  subsequent rejection and fresh reload.
- A genuine implementation regression over-guarded the observed dimension
  `15.24 m frontage`. The code was narrowed; its original partial-certainty
  assertion was retained. An observed frontage dimension is not primary access.

## Gates

Focused repair/control gate: **6 passed, 6 subtests**, 7.91 seconds.
Final survey/document lane: **314 passed, 75 subtests**, 320.50 seconds, exit 0.
Implementation/fixture hashes were unchanged across the final lane.
Latest full repository gate was the Rule 4 milestone, before Rule 5:
9245 passed, 3 skipped, 14 warnings, 10127 subtests, 705.75 seconds, exit 0.
The next required full gate is after Rule 8. Existing unrelated dirty planning/
feasibility work was preserved and excluded from this commit.

## Claude incorporation obligations and limitations

Ordinary Ask GO must receive scoped access classifications together with review
state, provenance, read/bind certainty and unresolved candidates. It must not
infer primary access from a street name, turn a frontage dimension into an entry
designation, use page orientation, or convert physical access into legal rights.
Directional frontage claims remain subject to Rule 3's true-North gate.

The producer proposes; existing governed confirmation is required. Verify that
the ordinary review surface makes each exact proposal and its obligations
reviewable, then prove the accepted/rejected states in live Ask GO. No live proof
is claimed here. Source facts may be incomplete; missing public status, entry
binding, subject geometry or review remains UNRESOLVED.

Current qualification requires a proven contained building, including for the
no-access classification. Vacant sites and subject boundaries that Rule 1 cannot
establish remain unresolved. General geometry reconstruction and photographed-plan
rectification remain Rule 7 work. Historical generated PDF bytes are not rewritten.
