# Irregularity, Interpretation, and Legibility

Status: current governance principle, v1.0, 2026-08-22
Repository grounding SHA: `b1589c5449c4204bd7a52eed3d83bf36d3921dad`

**NO IMPLEMENTATION AUTHORITY CREATED. NO NEW COGNITIVE RUNTIME SUBSYSTEM
AUTHORIZED. NO ROUTING REPAIR AUTHORITY CREATED.**

This record changes no runtime behavior, route, schema, template, test, vocabulary,
or contract. It creates no score, threshold, watcher, engine, queue, agent, status
value, or relationship type. It adds **one reasoning rule** that no existing record
states, and it deliberately states nothing else.

## The principle

> **Irregularity is information. Interpret it generously, conclude from it
> conservatively, and never resolve it by discarding it.**
>
> An unexpected value, an unfamiliar expression, a discontinuity, or a disagreement
> is a reason to widen what is considered — not a reason to reject the input, and not
> a defect until evidence makes it one. Interpretation may be *added* alongside what
> was actually observed. It may never *replace* it.

Two consequences, each the reason the rule is needed rather than a separate rule:

1. **Generous interpretation must extend to human expression, not only to project
   evidence.** This repository already interprets irregular *evidence* generously and
   concludes about it conservatively. It does not yet do the same for irregular
   *human input*. That asymmetry is the load-bearing content of this record — see the
   evidence below.
2. **Legibility, not cleanliness.** The purpose is to make the actual state of
   coordination legible, never to make a project appear coordinated. Apparent order
   must never be obtained by normalizing ambiguity, inventing a governing value,
   silently closing an unresolved condition, converting missing evidence into a
   default, or dropping a disagreement.

## Scope

- **GOVERNS:** how unexpected, unfamiliar, malformed, or conflicting input — from a
  person or from project evidence — may be interpreted, reported, and relied upon.
  It governs the **interpretation**, not the storage and not the routing.
- **OUT OF SCOPE — already governed, deliberately not restated:** `GOV-P-001` v1.0
  (selection is context, not authorization); `constitutional-invariants.md` #1, #5,
  #7, #10; [`evidence-richness-and-source-authority.md`](evidence-richness-and-source-authority.md)
  (richness increases resolution, never authority — **which already settles that
  widening interpretation cannot widen authority**);
  [`dependency-sufficiency-and-non-closed-basis.md`](dependency-sufficiency-and-non-closed-basis.md);
  `CIC-SPIN-INTELLIGENCE` v1.1's anti-scoring invariants. **None is amended.**
- **NOT GOVERNED:** how any specific surface should route, parse, or classify input.
  This record states what must remain true of the interpretation; it authorizes no
  change to any mechanism that produces one.

## Why the existing corpus does not already cover it

**Most of the rule is already in force, and is cited rather than restated.**

| Proposition | Where it already lives |
|---|---|
| Deviation is attention, not automatic defect | `dispute_relationship`/`reject_relationship` set state in place and never delete — *"never collapse into false consensus, preserve disagreement as a first-class fact"*; `CLAIM_CLASS_CONFLICTING`; `CONFIDENCE_STATE_CONFLICTING_SUPPORT` (*"do not treat this as resolved"*); invariant #10 |
| Preserve the original irregularity | `normalize_open_world_value` — an unrecognized value is *"never rejected, never silently coerced into a known category, and never loses its original text"*; `SourceReference.reference_text` is *"the ORIGINAL phrasing verbatim… never lost even when `resolution_status` is anything other than a clean single resolution"*; `Supersession`; invariant #5 |
| Interpret generously, conclude conservatively — **for evidence** | `resolve_source_reference_candidate` separates `candidate_targets` from `resolved_targets` across a closed eight-value `RESOLUTION_STATUS_*` vocabulary including `ambiguous`, `partially_resolved`, and `target_not_found`; *"a syntactically valid range/list is never expanded into ids that don't correspond to anything real"* |
| Anomaly may generate the next bounded question | Helix already carries `governed_question`, prompted verbatim as the *"Evidence → Concern → Question endpoint"*, plus `follow_on_game`; `unresolvable_aspects` becomes an honest `claim_class=unknown` claim, *"never silently omitted"*; `create_autonomous_case` is capped at `MAX_OPEN_AUTONOMOUS_CASES_PER_PROJECT = 3` with a same-anchor duplicate check |
| No anomaly score | `Claim` deliberately carries no confidence float; `KNOWN_DOCUMENT_QUALITY_GAUGES` is a three-state scale recorded against *"do not invent fake scientific precision"*; `CIC-SPIN-INTELLIGENCE` v1.1 forbids health scores and coordination percentages |

**The gap is the asymmetry.** Generous interpretation is implemented, tested, and
carefully vocabularised for *project evidence*. For *human expression*, the whole
gate is:

```python
def _looks_like_project_question(lowered: str) -> bool:
    stripped = lowered.strip()
    return stripped.endswith("?") or stripped.startswith(_PROJECT_QUESTION_STARTERS)
```

Two syntactic tests on the surface form of a sentence. A message that fails both is
routed by `quick_start` into creating a governed Case, and the reply asks the person
to restate their request using the product's own action grammar.

`quick_start`'s own docstring already records this class of surprise as a known,
only-partly-closed concern — *"forcing one into existence just to hold a message is
exactly the surprise quick_start currently causes"* — and narrowed it for plain
questions without resolving it generally.

**Measured, live, on the deployed build** during the PSD Builder smoke test
(2026-08-22):

| Input | Ends with `?` | Outcome |
|---|---|---|
| A six-sentence professional review instruction | no | Case created; no model call; no findings |
| *"Is this going to cost us more?"* | yes | Six cross-document findings, with honest abstention on cost |
| *"Are there similar conditions…? Tell me which differences look like they need explaining…"* | no (question is not last) | Case created; no model call; no findings |
| *"Which similar conditions in this package are handled differently from each other?"* | yes | Four peer-divergence findings, including one correctly characterized as legitimate variation |

The third row is the decisive one: the message **contains** a question mark but does
not **end** with one. The same subject matter reached or failed to reach cognition on
a one-character difference. **The quality of the underlying reasoning was never the
variable.**

## Invariants

- An unrecognized or unusual input is a reason to widen what is considered, never a
  reason to discard it or to require the person to restate it in the system's own
  vocabulary before it can be understood.
- Interpretation is recorded alongside the observed value, never in place of it. The
  literal as-found form remains retrievable after any mapping, match, or
  normalization.
- Lower certainty accompanies wider interpretation. Widening what is considered never
  raises the confidence, status, or authority of what is concluded.
- A conflict is reported as a conflict. Apparent coordination is never produced by
  normalizing ambiguity, inventing a governing value, defaulting a missing value, or
  closing an unresolved condition.
- Where interpretation cannot be settled from evidence, abstention is the correct
  output, not a plausible reconstruction.

## Allowed variation

Deliberately broad — this constrains interpretation, not mechanism.

- How any surface parses, routes, classifies, or ranks input, and whether it uses a
  model, a heuristic, or neither.
- Whether normalization, candidate matching, or fuzzy association exists at all, and
  by what method — provided the as-found form survives it.
- How uncertainty is expressed to a person, so long as it is not expressed as a
  number that implies precision the evidence does not carry.
- Any arrangement the existing evidence, Claim, Relationship, Spin and Supersession
  contracts already permit.

## Prohibited drift

- **Reading this as authority to change routing.** It is not. The measured evidence
  above is diagnosis, and `CROSS_LAYER_VERIFICATION.md`'s own rule applies: a report
  crosses, authority does not.
- Deriving a rupture score, anomaly temperature, aperture percentage, curiosity
  metric, confidence scalar, or candidate-match percentage. **All are excluded**, and
  the last is excluded for the same reason `Claim` refuses a confidence float.
- Building a watcher, daemon, scheduler, event bus, recursive investigation engine,
  or specialist swarm. Bounded question generation already exists and is already
  capped; unbounded exploration is not authorized by anything here.
- Treating "widen interpretation" as licence to widen scope, project boundary, or
  authority. `GOV-P-001` and `evidence-richness-and-source-authority.md` govern that
  and are unchanged.
- Treating an anomaly as a defect because it is anomalous. `SUFFICIENCY_NOT_EXPECTED_YET`,
  Helix `planned_deferred` / `legitimate_deferred`, and the existing legitimate-variation
  posture already distinguish these.
- **Promoting any of the metaphors this rule was discussed under into architecture.**
  Geology, strata, fault lines, tectonic rupture, deconstructivist fracture, beauty
  marks, children's incomplete language, and reductive painting are **explanatory
  analogies only**. None names a class, service, schema, threshold, queue, layer,
  hierarchy, or authority ranking, and none may be cited as a reason a mechanism must
  take a particular shape. The rule above is stated in domain-neutral terms precisely
  so the analogies are not load-bearing.

## Verification

**Review-time, not automated. No test is proposed and none should be added.** A test
asserting "this interpretation was generous enough" would encode a judgement this
principle deliberately leaves to a reviewer — the same reasoning `GOV-P-002` records
for its own verification section.

Where it bites: any change that decides what a person or a document *meant*, and any
report that presents a project as more settled than its evidence supports.

## Conflicts surfaced, not resolved

- **`_looks_like_project_question` is a two-test syntactic gate** on the human-input
  path, against a rich, closed, tested resolution vocabulary on the evidence path.
  Recorded as an observed asymmetry against working code. **Not filed as a defect
  here, not scheduled, and not repaired** — the PSD smoke-test findings
  (`PSD-SMOKE-01-A/B/C/D`) remain frozen and separately owned.
- **`candidate_referents` exists but is narrowly populated** — only *"on a system
  reply that genuinely presented more than one plausible referent."* The primitive
  for holding an unresolved human referent exists; nothing populates it from an
  input the system did not already recognize. Recorded; no change proposed.

## Relationship to existing records

- **[`evidence-richness-and-source-authority.md`](evidence-richness-and-source-authority.md)**
  v1.0 — already settles that widening never raises authority. This record depends on
  that and does not restate it.
- **[`dependency-sufficiency-and-non-closed-basis.md`](dependency-sufficiency-and-non-closed-basis.md)**
  v1.0 — agreement is not closure. The companion in the other direction: disagreement
  is not defect.
- **`GO-PREAWARD-ADJUDICATION-01`** — *Evidence → Concern → Question* and *"do not
  force every finding into RFI form"* already govern what happens after an anomaly is
  noticed. **Not extended.**
- **`GO-HELIX-01` / `CIC-SPIN-INTELLIGENCE` v1.1** — `governed_question`,
  `follow_on_game` and the abstaining assessments already implement bounded
  question-generation. **No Helix vocabulary is touched.**
- **`GO-PM-SITUATIONAL-GAUGE-01`** (DEFERRED) — *"the gauge summarizes; the
  drill-down explains"* and *"a gauge without grounded state is decoration"* are the
  nearest existing statement of the legibility half, scoped to a future surface. This
  record states the rule generally; that programme's status is unchanged.
- **`CROSS_LAYER_VERIFICATION.md`** — the measured routing evidence above was
  produced under that convention and is cited as evidence, not as ownership.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** any score, threshold, detector, routing rule,
  status vocabulary, or automatic action derived from this principle.
- **AMENDMENT RULE:** new version, never an in-place meaning edit.
- **SUPERSEDES:** None. **SUPERSEDED BY:** None.
- **GOVERNANCE DELTA:** `ADDITIVE`.

## Lineage

Stated by the Product Owner in conversation on **2026-08-22**, from a design
discussion about the epistemic value of anomaly and unclear expression. The framing
appears nowhere else in this repository; **no earlier provenance is claimed and none
was found by search.** The discussion reached the rule through several analogies;
none is adopted, named, or made vocabulary by this record, and the **Prohibited
drift** section exists specifically to keep them explanatory.

The routing measurements cited above come from the completed PSD Builder blind smoke
test on the deployed `b1589c5` build. They are **evidence for this principle, not
authorization to change what they measured.**
