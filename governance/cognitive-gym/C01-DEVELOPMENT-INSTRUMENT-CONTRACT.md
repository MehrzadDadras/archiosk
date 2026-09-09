# C01 development instrument contract and first qualification plan

**Status:** ACCEPTED CONTRACT / QUALIFICATION PLAN ONLY / NOT IMPLEMENTED.
Registered 2026-09-09 by Product Owner direction `GO COGNITIVE GYM - C01
DEVELOPMENT INSTRUMENT CONTRACT ACCEPTANCE / QUALIFICATION PLAN 01`.
The contract below is accepted; proposed qualification counts and delivery
choices remain a plan for later authorization, not measured results.
Authority: [observability specification](C01-DEVELOPMENT-OBSERVABILITY.md)
and [foundation](README.md). No controls, stimuli, code, provider execution,
or cognitive assessment are authorized by this registration.

> OBSERVED ACTION = EVIDENCE. COGNITIVE CAUSE = EXAMINER INFERENCE.

## 1. Accepted bounded contract

Each activity declares only its permitted response shapes, cardinalities,
limits, and addressing conventions. There is no universal required-field schema
and no chain-of-thought requirement.

| Shape | Minimum content |
|---|---|
| SELECT | Selected opaque IDs; declared single/multiple cardinality. |
| LOCATE | Location in a declared coordinate frame. |
| ORDER | Ordered IDs. |
| ANSWER | Short natural answer or declared scalar/unit. |
| CLARIFY | Focused question; paused decision reference; optional bounded alternatives. |
| CONDITIONAL CHOICE | Explicit condition and proposed action. |
| UNRESOLVED | Unresolved decision reference and brief missing-information statement. |

Short justification is permitted only when the activity requires it. Correctly
formed uncertainty responses are valid, not parser failures. Selection proposes
an action unless the activity explicitly authorizes execution; consequences are
separate events. Do not reward habitual clarification.

Selection links RUNNER-VISIBLE SCENE -> OPAQUE ELEMENT ID / COORDINATE LINK ->
EXAMINER ANNOTATION. IDs encode no correctness, relevance, family, expected action,
or examiner meaning. The runner must receive a usable mapping to visible content.
Keep IDs stable within a scene, without predictable answer assignments across
encounters. Do not silently snap ambiguous coordinates or correct invalid IDs.

Target delivery records target ID/version, exact wording, replace/add/suspend
operation, predecessor, unchanged constraints, permitted prior state, and delivery
sequence. GO need not restate the target: the instrument binds responses to the
request that delivered it. Target history is distinct from current authority.

Registered assistance descriptors remain INDEPENDENT, PROMPTED, CLARIFIED,
LOWER-BAR ASSISTED, RECOVERED AFTER FEEDBACK, and EXEMPLAR-EXPOSED. Preserve exact
support content/reference, event order, exposure lineage, and any hint or
answer-bearing content. No numeric assistance score; recovery is an examiner
interpretation, not something established by sending feedback alone.

Development-only reinforcement may acknowledge selection, inhibition, necessary
clarification, recovery, or reorientation. PRAISE CREATES NO NEW COMPETENCE
EVIDENCE. Exemplars have explicit EXEMPLAR mode, recorded exposure, no scored
question, and no assessment-evidence or pristine-holdout ancestry status.

Use the existing encounter record for external collection: encounter/scene/target
references, exact instructions and evidence identities, model/runtime, unchanged
raw response, separately parsed action, support, exposure, execution checks, and
ordering metadata. Examiner interpretation appends separately. The collector
never automatically reinjects interpretation; authorized developmental feedback
is a distinct logged outbound event and cannot draw on sealed assessment answers.

Keep BEHAVIORAL RESULT, CONTRACT DEFECT, DELIVERY DEFECT, TRANSPORT FAILURE,
VALID UNRESOLVED RESPONSE, and INVALID EXECUTION distinct. A valid but wrong ID
selection is behavior; a nonexistent ID is a contract defect. Invalidity retains
its specific cause. No silent JSON repair, ID correction, or answer-quality retry.

Collect only discrete consequential task events, not private reasoning, attention
weights, inferred gaze, continuous telemetry, or unnecessary precise timing.
Unknown selection remains NOT OBSERVED.

## 2. Proposed first slice and exclusions

Qualify only neutral single selection, explicit target replacement, focused
clarification, strict external collection, and mode rejection. Active response
shapes: SELECT and CLARIFY. Other accepted shapes, multiple selection, coordinates,
route execution, target add/suspend execution, adaptive difficulty, and rich
role worlds remain outside this first slice. Reject unsupported modes/operations
at admission rather than approximating them. This does not narrow the accepted
contract; it bounds the first proof.

Proposed future live controls: two independent repetitions of each sequence:

- Neutral selection: one response per encounter (2 calls).
- Target replacement: two responses per encounter (4 calls).
- Clarification then selection: two responses per encounter (4 calls).

Total proposed ceiling: 10 real-provider calls, zero automatic retries. Use only
future disposable instrument controls, never C01 game or sealed C02 material.
Do not repeat poor responses to obtain a favorable result. Provider/model,
transport, output budget, price-based financial ceiling, timeout, and residual
acceptance must be frozen before any future call. Existing provider or launcher
qualification does not automatically qualify this new multi-turn contract.

First run deterministic parser, ordering, isolation, and mode-denial tests without
a provider. Real calls then prove actual pixel/locator, target, and response
delivery. Offline negative tests are required but not substitutes for live-path
proof. Control correctness demonstrates delivery only, not C01 competence.

## 3. Locator recommendation

| Option | Burden and required proof | Ambiguity |
|---|---|---|
| Neutral visible locators (recommended first) | Adds glyph reading and label-to-object binding; low coordinate burden. Prove legibility, unique association, stable mapping, and exact outbound delivery. Counterbalance IDs/positions across disposable controls. | Do not guess between ambiguous associations; stop or retain a clarification. |
| Coordinates with external hit testing (later) | Avoids visible ID reading but adds coordinate-frame, scale, precision, and hit-testing demands. Requires separate delivery and boundary qualification. | Explicit ambiguous hit/no-hit; no silent snapping. |

First use one scene image with neutral locators. Labels carry no examiner meaning
and must not obscure objects. This is an instrument addressing control, not pure
unlabelled perception. If locator burden prevents reliable addressing, stop;
do not silently switch to coordinates or attribute the difficulty to C01.

## 4. Authorized encounter state

Use fresh provider requests with explicitly assembled state, not an unrestricted
conversation transcript or provider thread. State is limited to the same
encounter and references an allowlisted event sequence:

- Current scene/evidence and addressing map, unchanged unless explicitly versioned.
- Current target/version and exact predecessor target in explicitly historical,
  superseded form for the replacement control.
- Explicitly unchanged constraints.
- Prior parsed observable selection or clarification, only when declared needed;
  never automatically the entire raw prior output or free-form prose.
- Exact logged support needed for the current step.

For the neutral control, no prior state. For replacement, include scene, historical
A, current B, unchanged constraints, and the declared prior selection. For
clarification continuation, include scene/current target, the preceding focused
question, and the delivered clarification support. The target version need not
change when support resolves a referent without changing the objective; record
the support condition separately. If wording is revised, create a new version.

Never include sibling encounters, general chat history, examiner annotations,
reviews, answer keys, persistent retrieval, or unapproved prior outputs. No model
tools/connectors. This is a new bounded state contract, not reuse or widening of
existing carry authority. Mode cannot change within an encounter.

Proof requires exact outbound captures matched to the allowlist at every turn,
fresh client/request evidence, no thread/history/cache insertion under application
control, and synthetic denied-channel canaries. Minimize broker access to sealed
request content; external collection cannot grant it examiner filesystem access.
Provider-internal behavior remains an explicitly stated external residual.

## 5. Required proof plan

| Dimension | Evidence required |
|---|---|
| SELECTION DELIVERY | Exact scene/image identity and configuration; legible uniquely associated locators; actual model returns one valid opaque selection on disposable controls. |
| SELECTION PARSING | Strict declared SELECT/CLARIFY contracts; raw bytes/text preserved separately from parsed fields. Deterministic rejection of malformed JSON, nonexistent IDs, wrong cardinality, and unsupported shape. |
| TARGET VERSIONING | Exact wording/version/predecessor and request binding; reject missing, stale, duplicate, or out-of-order events. No dependence on GO echoing metadata. |
| TARGET REPLACEMENT | A-response/change/B-response order; B present before its response; scene/constraints preserved; A marked historical. Disposable A/B actions distinguishable and actual returned actions demonstrate the transition. |
| AUTHORIZED ENCOUNTER STATE | Every outbound field maps to allowed same-encounter state; fresh requests; denied history absent. Negative attempts to include extra context are rejected before provider dispatch. |
| CLARIFICATION FLOW | Actual CLARIFY with focused question and paused decision; exact clarification logged as support; next response bound to that support condition. Do not judge the wisdom of asking. |
| EXTERNAL COLLECTION | Exact outbound identities/target, raw/parsed output, support/order, configuration and validity preserved. Examiner annotations append separately; canary annotation never appears in later outbound context. |
| MODE ENFORCEMENT | Mode fixed; ASSESSMENT rejects undeclared reinforcement, adaptation, exemplars, feedback and extra support before dispatch. EXEMPLAR rejects scored action requests. DEVELOPMENT rejects unlogged support. |
| EXAMINER ISOLATION | Selected-control-only access, denied examiner/review/sibling/prior-output channels, canaries absent from outbound/returned content, and technical access-denial evidence. |
| EXECUTION VALIDITY | Delivery/receipt/parse/ID/order checks plus controlled truncation, malformed response and transport-failure handling; each retained with its specific defect and no repair/retry. |

If old and new targets permit the same action, record SWITCHING NOT OBSERVABLE
FROM THIS EVENT. Test this annotation offline; it cannot substitute for the
distinguishable live replacement control. Lack of discriminating behavior is an
observability limitation, not automatically an execution defect or cognitive cause.

Clarification qualification may explicitly request a clarification response as
an instrument control. That proves the channel, not spontaneous judgment about
when to ask. Do not improvise follow-up hints to force a control to succeed.

Mode-denial tests require dispatch evidence (zero provider requests for rejected
events), including attempted mid-encounter mode changes and unlogged support.
Exemplar demonstration/scoring rejection can be verified without model execution.
The live clarification flow proves an allowed, logged DEVELOPMENT support path.
No positive qualification of an ASSESSMENT runner is claimed by these denial tests.

## 6. Stops, verdicts, and preservation

Hard stop the qualification campaign and preserve evidence if any of these occurs:

- Selectable content cannot be addressed reliably under the declared locator contract.
- Target version, delivery, response binding, or event order cannot be proven.
- Prior context exceeds the declared state, or examiner annotations/canaries leak.
- Mode controls are bypassable, including unlogged support or scored exemplars.
- Parser repairs JSON/IDs, or ambiguous selections are silently snapped.
- Collector interpretation returns through an undeclared input path.
- Perceptual burden or execution behavior lies outside the frozen qualification scope.
- Truncation, response-contract defect, or transport failure occurs during a live control.

Expected rejection during a planned offline negative test is successful denial
evidence, not itself a stop. Unexpected acceptance or failed containment is a stop.
No automatic widening, new modality, budget change, remedial control generation,
or retry campaign follows a stop without separate authorization.

Future verdicts for each of the ten dimensions above are QUALIFIED or NOT
QUALIFIED, with exact evidence and scope. Untested requirements are NOT QUALIFIED
with reason UNTESTED. No verdict is issued by this plan. Qualification supports
instrument claims only, not developmental status, reliability, or progress points.

Preserve C01 definition, C02 opening sequence/instructions, difficulty anchors,
C09 semantics, historical evidence, existing launchers/carry, and product code.
No cognitive assessment or real game material belongs in qualification. This
specification creates no implementation or competing governance hierarchy.

Next proposed authorization: C01 DEVELOPMENT INSTRUMENT QUALIFICATION 01,
limited to this slice, additive evaluator-only implementation and disposable
controls, frozen execution/financial contract before calls, separate dimension
verdicts, no C01 assessment and no C02 changes. It is not issued by this document.
