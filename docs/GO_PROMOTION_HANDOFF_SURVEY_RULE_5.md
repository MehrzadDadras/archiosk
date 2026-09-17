# Claude Promotion Handoff: scoped public access

**CURRENT STATUS: CONTRADICTION REPAIR FULL-GATE GREEN / READY FOR CLAUDE / NOT_PROMOTED.**
Repair implementation: `43a3b5c46528a75e94c1089260cb27073c7ae7f3`.
QUALIFIED / DISTILLED / IMPLEMENTED / GATED / RUNTIME_WIRED locally.
LIVE_REACHABLE is not proven; Claude must verify, incorporate, gate, deploy and
prove the ordinary Ask GO path. No push or deployment occurred.
The original implementation SHA and historical gates below describe the earlier increment.

The Rule 5 counterevidence fixture exposed an IMPLEMENTATION_DEFECT: confirmed
support ignored confirmed contradiction. The Rule 2 measurement-precedence and
Rule 3 reviewed grid-to-true conversion controls independently reproduced the
same defect. Their narrowly scoped repairs consume the existing trust projection.
The independent, conflicting measured-North control passes without changing the
existing angle-conflict resolver. Rule 1 and Rule 4 behavior remain unchanged.

Contradiction-repair implementation symbols:
- `services/case_workspace.py::CaseWorkspaceStore.explain_evidence_trust` exposes
  confirmed and unresolved counterevidence separately; all historical edges remain.
- `services/survey_graph.py::resolve_access_interpretations`,
  `resolve_measurement_premises`, `access_interpretations` gate conclusions on
  current counterevidence and retain trust records and explicit premise states.
- `services/survey_north.py::resolve_conversions` refuses contested conversion.
- `services/document_examination.py::_visual_lines` carries qualified access and
  measurement states and counterevidence relationship IDs to Document Shop and
  ordinary Ask GO. North context retains candidates and conversion review records.
- `tests/test_survey_reference_01.py`: `SurveyAccessQualification`,
  `MeasurementGenealogyQualification`, `TrueNorthQualification`.

Controls use the existing synthetic parcel/access detail, M1/M2 measurement
genealogy, a same-segment M3 counterevidence record, reviewed grid-to-true
conversion, and independently measured 30/100-degree North candidates. Positive:
confirmed support alone. Negative: confirmed counterevidence prevents an
established conclusion. Ambiguous: proposed counterevidence remains UNRESOLVED.
Access confirmation, reload, counterevidence rejection, and another reload prove
that current projection can change without deleting either evidence record.
The runtime path remains worker -> persisted EvidenceItems/relationships ->
reload -> trust projection -> examination -> Document Shop / Ask GO context.

Governance: supported does not mean uncontested. No new contradiction engine,
authority transition, storage schema or migration. Existing relationship review
remains authoritative. Exact subject/snapshot, applicability and independent
read/bind certainty remain required. Unresolved counterevidence is conservatively
blocking; rejected/superseded counterevidence stays visible but is not active.
Do not promote raw proposal classifications or conversions around this gate.

Gates for the contradiction repair:
- Rule 5 focused: 6 passed, 6 subtests, 11.08 seconds.
- Combined Rule 2/3/5 focused: 19 passed, 51 subtests, 34.77 seconds; additional
  persisted independent North-conflict control: 1 passed, 6.63 seconds.
- Affected survey/document/evidence-trust lane: 383 passed, 83 subtests,
  306.16 seconds, exit 0.
- Full repository gate: **1 failed, 9252 passed, 3 skipped, 14 warnings,
  10133 subtests passed, 741.63 seconds, exit 1**.

Full-gate blocker classified UNRELATED_REGRESSION:
`tests/test_storage_bridge_durable_05.py::ClaimingIsAtomicAcrossRealProcesses::test_exactly_one_of_four_processes_wins_a_single_request`.
The claiming subprocess raises Windows WinError 32 at
`services/bridge_queue.py:195`, `path.unlink(missing_ok=True)`, leaving the
observed winner list empty. Those files were not changed by the repair.
Implementation initially stopped per the mandatory full-gate rule at
`72717e63408fdc1da31aca7d94f3ea933ddf7058`. The Product Owner then authorized a
bounded classification sequence and one fresh full gate. All runs follow;
the original red result above remains evidence.

### Queue classification, 2026-09-17

**UNRELATED_ENVIRONMENTAL_CONTENTION**, under the authorized classification
criteria. This is not proof that Windows queue contention can never recur.
The exact failing test invokes `BridgeQueueStore` directly; `bridge_queue.py`
imports only standard-library modules. Its claim path, test setup and conftest
do not call the changed survey/trust functions. `services/__init__.py` is empty.
The containing test file also tests CaseWorkspaceStore in separate test classes;
those are not on the failing subprocess call path. Queue code/test and conftest
have no tranche diff. No production or test code was modified in this investigation.

| Run | Command scope | Result |
| --- | --- | --- |
| Original full gate | `pytest -q -n 8 --dist loadfile` | 1 failed, 9252 passed, 3 skipped, 10133 subtests, 14 warnings; 741.63s; exit 1 |
| Isolation 1 | Exact failing node above, serial pytest | 1 passed; 0.45s; exit 0 |
| Isolation 2 | Same exact node | 1 passed; 0.61s; exit 0 |
| Isolation 3 | Same exact node | 1 passed; 0.40s; exit 0 |
| Smallest relevant lane | `pytest -q tests/test_storage_bridge_durable_05.py` | 25 passed, 7 subtests; 4.67s; exit 0 |
| One authorized fresh full gate | `pytest -q -n 8 --dist loadfile` | **9253 passed, 3 skipped, 10133 subtests, 14 warnings; 713.37s; exit 0** |

All commands used `venv/Scripts/python.exe -m pytest` with
`PYTHONDONTWRITEBYTECODE=1`. Runs were sequential. Scoped repair and queue file
hashes matched before and after the fresh full gate. No overlapping writer was
observed. The exact tested repair was committed without further code changes.
The invariant remains: confirmed support cannot authorize a downstream conclusion
while its governing premise remains actively contested. This applies to future
datum/authority and geometry/projective premises as well as Rules 2/3/5.

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
The contradiction-repair full gate above supersedes this historical checkpoint.
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
