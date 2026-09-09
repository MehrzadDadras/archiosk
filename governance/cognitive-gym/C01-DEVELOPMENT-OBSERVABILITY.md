# C01 developmental observability

**Status:** ACCEPTED SPECIFICATION / NOT IMPLEMENTED. Registered 2026-09-09.
Product Owner authority: `GO COGNITIVE GYM - C01 DEVELOPMENT OBSERVABILITY
SPECIFICATION ACCEPTANCE / REGISTRATION 01`.
Governed by [foundation section 5.1](README.md#51-playful-development-and-orientation)
and the [existing capability catalog](CAPABILITY-CATALOG.md).

> OBSERVED BEHAVIOR = EVIDENCE.
> PROPOSED COGNITIVE CAUSE = EXAMINER INFERENCE.

This is a bounded developmental encounter specification, not a generic telemetry
framework, capability scale, or permission to implement or execute. C01 is not
a hidden score multiplier. Observe actions and responses, not private reasoning.

## 1. Minimum encounter record

| Part | Retained information |
|---|---|
| Encounter header | Campaign/world ID; item/scene ID; mode; primary capability; configuration/protocol reference; scene reference; prior exposure; assistance references. |
| Ordered events | Sequence; event type; target ID/version where applicable; exact instruction/response or artifact reference; observable selection/action where available; timestamp only where useful. |
| Examiner interpretation | Execution validity; observable outcome; earliest observable divergence; possible contribution; alternatives; confidence; limitations; next developmental recommendation. |

Only five bounded event types are specified:

- **Context supplied:** scene, available evidence/cues, constraints, and permitted prior state.
- **Target supplied / changed:** exact wording and whether it replaces, supplements, or suspends the previous objective.
- **GO response / action:** unchanged response, selection, action, or clarification request.
- **Support supplied:** clarification, prompt, feedback, reinforcement, or exemplar reference.
- **Execution event:** delivery confirmation, completion, or defect.

Reference scene/evidence records rather than exhaustively duplicating cues.
Examiner relevance annotations remain external to runner inputs. Unknown
observations remain unknown: NOT OBSERVED is not an empty selection or proof of
non-use. Factual events remain separate from examiner interpretation.

## 2. Encounter outcome annotations

| Annotation | Observable basis or limit |
|---|---|
| TARGET-ALIGNED BEHAVIOR | Selection/action serves the supplied objective. |
| TARGET MISSELECTION OBSERVED | Selection/action follows a conflicting criterion; its cause is separately assessed. |
| TARGET-CHANGE RESPONSE ABSENT | A verified change was delivered, but subsequent behavior does not demonstrate adaptation. |
| OBSOLETE-TARGET BEHAVIOR REPEATED | Subsequent action specifically matches the superseded objective. |
| RELEVANT-CUE USE NOT DEMONSTRATED | Necessary cue use is not demonstrated; this does not prove the cue was unnoticed. |
| IRRELEVANT-CUE USE OBSERVED | Selection, action, or explicit reference demonstrably relies on an irrelevant cue. |
| MATERIAL AMBIGUITY RECOGNIZED | Clarification or conditional behavior identifies a consequential unresolved interpretation. |
| UNNECESSARY CLARIFICATION | Available information was sufficient, with no material alternative established. |
| TARGET-ALIGNED SELECTION / DOWNSTREAM ERROR | Correct selection precedes an incorrect subsequent result. |
| ATTRIBUTION UNRESOLVED | Available behavior cannot distinguish competing explanations. |
| INVALID EXECUTION | A material execution defect prevents the intended cognitive attribution. |

These are encounter annotations, not scores, developmental levels, or permanent
traits. Multiple annotations may occur in sequence, including assisted recovery.

## 3. Earliest divergence and confidence

> ATTRIBUTION BEGINS AT THE EARLIEST EXTERNALLY EVIDENCED MISMATCH,
> NOT THE EARLIEST IMAGINED MENTAL ERROR.

1. Verify execution and delivered material.
2. Establish the governing target at that event.
3. Compare observable action/selection to the target.
4. Locate the first supported mismatch.
5. Preserve alternative explanations.

The first divergence identifies where investigation starts, not automatically
the root cause. Correct selection followed by a downstream error is not evidence
of target-selection failure. Missing selection evidence cannot be invented.

Each attribution links primary capability, observable event, earliest divergence,
possible C01 contribution, alternatives, confidence, and evidence limitations.
Reuse the foundation's confidence vocabulary:

| Confidence | Bounded attribution meaning |
|---|---|
| INSUFFICIENT | Observability or delivery evidence is inadequate, or competing explanations cannot be separated. |
| LIMITED | Behavior supports a possible contribution; material alternatives remain. |
| SUPPORTED | Observable evidence and relevant checks support the stated contribution within its declared scope. |

Confidence belongs to the examiner's attribution, not GO's self-confidence.
SUPPORTED C01 CONTRIBUTION does not mean C01 was the sole cause. Use ATTRIBUTION
UNRESOLVED when available behavior cannot distinguish causes.

## 4. Assistance and reinforcement

| Event-linked descriptor | Meaning |
|---|---|
| INDEPENDENT | No task-specific assistance preceded this response; prior exposure remains disclosed. |
| PROMPTED | An attentional or procedural cue was supplied. |
| CLARIFIED | Objective or permitted information was clarified. |
| LOWER-BAR ASSISTED | Challenge was simplified; record the changed factor. |
| RECOVERED AFTER FEEDBACK | Correct behavior followed feedback on an earlier response. |
| EXEMPLAR-EXPOSED | A relevant demonstration was available; link the exposure record. |

These are not one ordered competence scale. Assisted success is not independent
reliability. A necessary clarification may be independently initiated; the answer
after clarification uses clarified conditions and is recorded accordingly.

Reinforcement retains exact feedback or reference, the justifying behavior/event,
whether it followed independent success, recovery, or necessary clarification,
any hint or answer-bearing information supplied, and the subsequent material's
freshness/exposure status once known.

> PRAISE CREATES NO NEW EVIDENCE.

Freshness comes from material lineage, not examiner intention. Reinforcement is
development-only; do not reward response style instead of target behavior.

## 5. Target changes, distraction, and ambiguity

Observable target transition:

OLD TARGET ACTIVE -> CHANGE COMMUNICATED -> REPLACEMENT UNDERSTOOD -> NEW ACTION
SERVES REPLACEMENT -> OBSOLETE TARGET RETIRED -> UNCHANGED CONSTRAINTS PRESERVED.

Retain the previous target/version, exact change and delivery order, and
subsequent behavior. Acknowledgement alone is weak evidence of understanding.
The old objective may remain as history but must stop governing current action
when superseded. If the same action satisfies both objectives, successful
switching is NOT ESTABLISHED from that action alone. Constraint retention also
requires observable support; otherwise it remains unobserved.

> DO NOT EQUATE MENTION WITH USE.
> DO NOT EQUATE SILENCE WITH SUCCESSFUL INHIBITION.

Distinguish where observable: cue noticed; cue selected as relevant; appropriate
non-use; distractor followed; weak relevant cue used; conflict appropriately
unresolved. A reference or interaction may evidence noticing without evidencing
use. Appropriate non-use needs discriminating behavior, not silence alone.
Image availability does not establish cue perceptibility. No exhaustive scene
description is required: selective attention is the target.

Ambiguity behavior distinguishes:

- **NECESSARY CLARIFICATION:** resolves a material uncertainty about the objective.
- **UNNECESSARY CLARIFICATION:** resolves no defensible material uncertainty.
- **SAFE CONDITIONAL ACTION:** explicit assumption, bounded consequence, permitted reversible action.
- **UNSUPPORTED CONSEQUENTIAL ASSUMPTION:** material interpretation chosen without sufficient basis or authority.
- **PRESERVED PARTIAL PROGRESS:** supported independent work proceeds while the dependent choice remains open.
- **BLANKET HESITATION:** answerable work withheld without a material blocker.

Keep missing evidence, ambiguous wording, several permissible goals, and examiner
uncertainty separate. A difficult but clear target is not automatically ambiguous.

## 6. Diagnosis and development frontier

Preserve the original outcome unchanged. Possible contributors include C01 target
selection, C02 perception, C22 wording/language, C12 state carry, downstream
reasoning, genuine ambiguity, and execution defect. Do not automatically
attribute a downstream error to C01. Required state must first be shown to have
been delivered and available before proposing a cognitive carry failure.

Later fresh simplified developmental probes may distinguish hypotheses. Record
assistance and changed conditions. They do not rescore the original item, rewrite
history, establish a permanent diagnosis, or automatically establish C01
competence. Later interpretations link forward to preserved evidence.

Observability may identify bounded contrasts: stable-target success versus
post-switch difficulty; harmless distraction versus salient competition;
necessary clarification versus over-questioning. Report scope, support
conditions, observation count/diversity, and alternatives. One observation
identifies a candidate development focus, not a trait, reliable level, or
progress-history point.

## 7. Product Owner review and data minimization

The minimum human-readable card contains world/scene, primary bar, exposure,
permitted evidence, current target, short target-change timeline, GO observable
action/raw answer, assistance, feedback/reinforcement, observed outcome, possible
attribution, alternatives, confidence, execution limitations, and next
developmental step. Keep factual events visually separate from examiner
interpretation. Preserve raw responses unchanged; no private chain of thought.

Retain supplied-context references, consequential events, observable
responses/actions, support, execution validity, and bounded interpretation only
as needed to understand the encounter. Do not collect hidden reasoning,
attention-weight telemetry, inferred gaze, continuous behavioral capture, or
unnecessary precise timing. Sequence establishes order; unknown remains unknown.

## 8. Preservation and authority boundary

The C01 definition, C02 opening sequence, frozen C02 instructions, D0-D4 anchors,
C09 TARGET semantics, append-only profile/history principles, existing evidence,
launcher qualifications, and product code remain unchanged. Here target means
task objective, not a revision to proposition semantics.

Development allows recorded feedback and reinforcement. Exemplars demonstrate
but are not scored or competence evidence. Assessment remains blind with frozen
instructions: no orientation coaching, cookies, or feedback reinjection.
Development/exemplar exposure cannot become pristine holdout evidence.
Developmental success is not automatic competence proof.

This registration contains no stimuli, answer keys, provider outputs, runtime,
instrumentation, or assessment records. Future examiner records remain under the
existing FlightTests/evaluator authority; this file defines their bounded
meaning, not an implementation or a competing governance hierarchy.
