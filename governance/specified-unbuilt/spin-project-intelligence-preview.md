# Specified But Unbuilt — Spin: Comprehensive Project Intelligence Preview

**Status:** Named, concept-preservation only, following the same pattern already established for
`adaptive-attention-and-context-circulation.md`/`trust-exchange-and-security-commissioning.md`/
`bug-eye-data-room-source-continuity.md`. **NOT AUTHORIZED** for implementation or further design.
Recorded under `CLAUDE-GO-DNA-01` (2026-08) as a required concept-preservation entry alongside that
stage's own implemented result (`current/go-dna-01-composer-result-contract-and-panel-zoning.md`)
— a small correction ("Overview is a likely primitive ancestor of the first Spin result, do not
delete it") with a large directional consequence for how a future comprehensive-review capability
should be scoped, named here so a future session does not rebuild machinery GO already has in
rough form, and does not invent a name/shape for this concept from scratch.

## What "Spin" names

A future capability distinct from, and preceding, ordinary focused conversational Composer
turns: a **comprehensive** machine review of a project's evidence, producing a structured,
persisted set of findings — the "first Spin result" — as opposed to the narrower, question-driven
`ComposerFinding` emission `current/go-dna-01-composer-result-contract-and-panel-zoning.md`
already implements (one or a few findings, produced only in response to a specific reviewer
question, never a sweep of the whole project).

**The governing distinction, recorded verbatim from the Product Owner's own framing:**

> Comprehensive Spin precedes focused conversation. Historical Spin finding sets are preserved
> rather than overwritten. Spin discovers → Pass adjudicates → Build incorporates.

None of this is built. `ComposerFinding` (implemented) does not overwrite anything — each turn's
findings are simply appended to `workspace.composer_findings` — but there is no concept of a
"Spin run" as a distinct, dated, comprehensive event; no run-level grouping; no comparison between
one Spin's finding set and a later one; no `Pass` (adjudication) or `Build` (incorporation) stage
of any kind.

## What already exists and should be reused, not duplicated (see the full audit in
`current/go-dna-01-composer-result-contract-and-panel-zoning.md`'s own §3/§6)

- `services/project_briefing.py`'s `generate_project_briefing` — the real, existing, one-shot,
  whole-document narrative synthesis (`matters_requiring_attention` etc.), already the closest
  primitive ancestor. **Do not delete or bypass it when Spin is eventually designed** — inspect
  whether it becomes Spin's own generation step, or whether Spin generalizes past it.
- `services.case_workspace.ComposerFinding`/`add_composer_finding` — the structured-finding shape
  and the Toolbox projection seam a comprehensive Spin result would also need; a Spin-produced
  finding should very likely be the SAME object, distinguished by provenance (which turn/run
  produced it), not a second finding type.
- `REQUIREMENT_ADJUDICATION_OUTCOMES`/`ReviewerValidation`/`Disposition` — the existing closed
  human-adjudication vocabularies "Pass" would almost certainly reuse rather than reinvent.
- `WorkProduct`'s draft→review→approve→issue lifecycle — the closest existing precedent for a
  "Build incorporates" step, if that step turns out to mean producing a governed deliverable from
  adjudicated Spin findings.

## Why this is GO LATER

- The narrower, question-driven Composer-finding capability (`CLAUDE-GO-RIGHT-PANEL-01`) was
  authorized and built FIRST, deliberately, as "the smallest repository-grounded implementation
  that proves GO intelligence can leave the chat stream and become persistent, visible project
  material" — Spin's own governing prompt explicitly excluded "historical Spin sets, full Pass/
  Build adjudication, Tool Making, custom-focus management, or a major right-panel redesign."
- No run-level grouping, comparison, or "Pass"/"Build" object exists yet to build on top of —
  designing Spin properly requires first deciding whether a "Spin run" is a new object or a
  read-time grouping over existing `ComposerFinding.created_at`/provenance, which has not been
  investigated.
- `Overview`'s own relationship to a future Spin result (full replacement? a rendering surface for
  Spin's output? left as-is with Spin appearing only in the Toolbox?) is explicitly unresolved —
  named as the open question a future authorization must answer, not answered here.

## Deliberately not investigated by this record

Whether a "Spin run" needs a new domain object at all, how historical Spin sets would be compared
(a diff view? a timeline?), what "Pass" adjudication states would be beyond reusing
`REQUIREMENT_ADJUDICATION_OUTCOMES`, what "Build" incorporation concretely produces, Tool Making
of any kind, and custom-focus/discipline selectors. Each requires its own repository-grounded
investigation before authorization, following the same discipline `CLAUDE-GO-RIGHT-PANEL-01`'s own
audit-first requirement already established for adjacent work.

---

## Addendum (`CLAUDE-GO-DNA-02`) — Task as directed probe vehicle, the investigative rhythm, and compound evidence

Recorded following `CLAUDE-GO-DNA-01`'s own governance capture, per the same "small correction,
large directional consequence" framework. **Metaphors are recorded for their product meaning, not
for literal implementation** — the Product Owner's own explicit instruction. No code changes
accompany this addendum. **NOT AUTHORIZED** for implementation.

### The investigative rhythm

> Load → Aim → Probe → Echo → Interpret → Re-aim

The product meaning: an investigation is not a fixed linear workflow. A PM (or GO, coordinating
with a PM) may redirect an in-progress investigation toward another drawing, document, discipline,
project stage, stakeholder, technical relationship, risk dimension, hypothesis, or an earlier
finding — at any point, not only at the start.

**What already exists toward this**, per `CLAUDE-GO-DNA-01`'s own reuse audit
(`current/go-dna-01-composer-result-contract-and-panel-zoning.md` §3/§6) — this addendum does not
re-derive that audit, only applies it to the rhythm above:

- `Case`/`InvestigationStep` (`services/case_workspace.py`) already records a real probe→response
  sequence: `record_investigation_step` captures the question asked, the evidence examined, and
  the conclusion reached, one `InvestigationStep` per probe. This is real *Load → Aim → Probe →
  Echo* infrastructure, already built, for Case-scoped investigation — **the strongest existing
  implementation thread**, not a gap to fill with a new Probe subsystem.
- **Partially schema-ready, confirmed by direct inspection, corrected from an earlier pass of this
  same audit (see the `CLAUDE-GO-DNA-05` addendum below):** *Re-aim* — redirecting an open
  Investigation's own focus mid-stream toward a different Requirement/Source/discipline while
  preserving the accumulated `InvestigationStep` history as context for the next probe.
  `InvestigationStep.branched_from_step_id` exists as a real schema field with a corresponding
  `record_investigation_step` parameter — a named persistence extension point for exactly this — but
  no route or caller anywhere in the repository ever sets it. The seam is schema-ready, not
  code-absent; what's missing is the orchestration that would ever populate it. This is a real,
  named seam — **specified-unbuilt, not built by this record.**
- *Interpret* is partially real: `_handle_investigate_requirement`'s own LLM call
  (`services/requirement_investigation.py`) produces `assessment`/`confidence`/
  `supporting_points`/`open_questions` per probe — genuine interpretation of one probe's evidence,
  not yet threaded across a re-aimed sequence of probes.

### Task as a directed probe vehicle

The Product Owner's own invariant, preserved verbatim:

> A Task may be an assembled package of evidence and intent aimed toward an investigative or
> project outcome.

**Not a redesign of the current `Task` model** — the governing instruction is explicit: first
determine what existing Task/Investigation primitives already support before adding anything.
Confirmed by direct inspection (`Task` dataclass, `services/case_workspace.py`): today a `Task` is
a title, a single `source_anchor` (one `ConversationSourceAnchor`), and open/completed status —
genuinely simpler than the payload the Product Owner describes (evidence, findings, source
references, tagged fragments, wondering notes, instructions, priority, ownership, timing,
dependencies, tools, stage, discipline/focus, approval/context). **None of this richer payload
shape is built.** `CLAUDE-GO-DNA-01` already named the one concrete, small, well-precedented seam
this direction points toward: a cross-reference field linking a `Task` back to the
`ComposerFinding`/`Finding` that spawned it, mirroring `WorkProduct.source_finding_id`'s already-
proven shape — that remains the smallest genuinely-useful step toward this richer model, not the
full assembled-package concept at once.

### Compound evidence and the evidence-fragment/address/tag/wondering-note shape

The Product Owner's real working method: **evidence fragment + source address + tag + wondering
note**. A wondering note is deliberately *not* a finding or conclusion — it may be an observation,
suspicion, emerging pattern, technical question, or possible consequence. The distinction between
**"evidence says"** and **"human/machine wonders whether"** is explicitly named as important for
forensic integrity and the coordinator/design-authority boundary (see the addendum below).

**Reuse thread, not a new model** — `CLAUDE-GO-DNA-01`'s own audit already found the relevant
pieces:

- `AddressableRegion`/`EvidenceItem` (Camel MM1) already provides real, addressable,
  document/page/paragraph-level evidence location — the "source address" half of the shape.
- `Tag`/`TagOccurrence` already provides human categorization/annotation — but anchors only into
  *conversation-message* text today (`ConversationSourceAnchor`), not into
  `AddressableRegion`/`EvidenceItem` directly. **This gap was already identified, not
  re-discovered here**: a future "tag the actual document passage" capability would extend
  `TagOccurrence`'s anchor scope to also accept an `AddressableRegion`/`EvidenceItem` id.
- **A "wondering note" has no existing object today.** It is not a `Finding`/`ComposerFinding`
  (both characterize something closer to a conclusion), not a `Tag` (a label, not free text), and
  not a plain `ConversationMessage` (conversational, not evidence-attached). This is a genuinely
  new concept with no coherent existing home — named here, **not built**, for a future session to
  design rather than conflate with an existing object merely because one is convenient.
- GO reasoning over the *relationship among several evidence fragments at once* (compound
  evidence, not one clause) has a partial existing precedent in MM6's relationship layer
  (`record_evidence_relationship`, `resolve_relationship_status`) but that layer connects two
  endpoints at a time, validated against `_MM6_ENDPOINT_LISTS` — whether it generalizes to an
  N-fragment compound-evidence bundle without a new object is unresolved, not investigated by this
  addendum.

### 360-degree re-aiming — the coordinator boundary

Preserved explicitly, because it governs what GO must never do regardless of how the probe/echo
mechanism above is eventually built:

> GO may explore an alternative as a question ("Could the responsible designer review whether
> relocating this scupper would improve envelope coordination?"). GO must not autonomously convert
> that into an instruction ("Move the scupper to this location.").

This is not a new invariant this codebase must build toward — it is a restatement, in probe/re-aim
language, of an invariant this codebase's own `services/project_qa.py` `BEHAVIORAL_CONTRACT`
already partially enforces today: *"You may suggest that something become a governed Requirement,
Finding, Task, or Decision, but you never create one yourself."* Any future Re-aim/probe
orchestration must preserve this exactly — GO characterizes and questions, a human or the
responsible design authority decides and directs.

### Canonical case: the Roof Scupper investigation (preserved, not simulated or built)

Preserved as a real, recorded example of the recursive investigative rhythm above, per the
Product Owner's own instruction — **a real site-construction coordination case, not a synthetic
one, and not something this repository has attempted to reproduce or automate.** The Product Owner,
coordinating imperfect/incomplete IFC drawings with a Construction Management team, investigated
roof scuppers: locating them, finding two roofs apparently lacking scuppers, relating scupper
elevations to roof-drain elevations, questioning whether some scuppers were shallow enough to
function in ordinary rainfall rather than as emergency overflow, finding scuppers hidden behind
roof walking panels (a maintenance-awareness concern), tracing where upper-roof discharge landed on
lower roofs, questioning whether the structural engineer had evaluated the receiving roofs'
flood/load susceptibility, and considering whether relocating a scupper might better align with
envelope panel seams — each question generated by the answer to the one before it, not from a
predetermined final RFI. **The mechanic to preserve**: one piece of evidence generates the next
question — this is the concrete, human-proven shape the Load → Aim → Probe → Echo → Interpret →
Re-aim rhythm above is meant to eventually support, not a workflow to hard-code literally.

**The authority layer, equally important and NOT to be dropped when this is eventually designed:**
before issuing the resulting RFI, the Product Owner separately obtained (a) technical concurrence
from the site architect (the designer's own office) that the concern was legitimate, and (b)
commercial/risk concurrence from the Construction Management team that pursuing the RFI was
appropriate and would not create avoidable commercial exposure (the RFI could trigger a Change
Notice). **These are explicitly different kinds of concurrence and must never be collapsed into one
generic "approved" state**: technical concurrence answers "is this a real, legitimate concern";
commercial concurrence answers "should we raise it, through what channel, with what risk
awareness." Today's `RFIDraft`/`ReviewerValidation`/`create_rfi_draft` gate
(`services/case_workspace.py`) already enforces *a* human-review requirement before an RFI can be
drafted at all — never a dry, unilateral machine decision — but records only one generic
`ReviewerValidation`, with no field distinguishing technical from commercial concurrence, and no
representation of a design-authority party (the site architect equivalent) separate from the
project's own reviewer. **This is a real, named gap, not built**: a future extension would need a
concurrence-type distinction on whatever gates RFI progression, not a second parallel approval
system. See `current/go-dna-01-composer-result-contract-and-panel-zoning.md` for how the existing
gate already implements the "never a dry machine decision" half of this invariant today.

---

## Addendum (`CLAUDE-GO-DNA-03`) — Claude's own investigative loop as GO's reference model

Recorded following a Product Owner clarification: **not a new feature idea** — a restatement,
sharpened by a new reference point, of the same investigative-GO intent already recorded in the
`CLAUDE-GO-DNA-02` addendum above. Per the Product Owner's own framing, this is a DNA-level
clarification, not a chatbot prompt-tuning exercise. **No code changes accompany this addendum.
NOT AUTHORIZED for implementation.**

### The reference-model claim

The Product Owner observed that Claude's own repository-investigation behavior — the pattern this
very session used repeatedly (audit the actual code before proposing anything, distinguish what a
search turned up from what actually matters, form a bounded hypothesis, test it, revise, act) — is
structurally the same reasoning discipline he has been trying to build into GO since before this
governance corpus existed. Agreed, and grounded concretely, not merely philosophically: the
`CLAUDE-GO-DNA-02` addendum's own **Load → Aim → Probe → Echo → Interpret → Re-aim** rhythm and
Claude's own working pattern in this session (observe a condition → search broadly → inspect
surrounding evidence → distinguish relevant from stray context → open the most relevant sources →
trace relationships → form a bounded hypothesis → test it → inspect the result → revise or redirect
→ validate → act) are the same shape applied to two different evidence domains — a Python
repository versus project drawings/documents/correspondence. Nothing about this claim requires new
code; it is a reason to trust the `CLAUDE-GO-DNA-02` rhythm as the right target shape, not a reason
to build a second one.

### A concrete, live instance of relevance discrimination (not hypothetical)

Earlier in this same session, a system-provided context block included selected text from an
unrelated file (an RFP Data Sheet timetable line) alongside an actual Product Owner instruction
about the Project Gateway, explicitly flagged as "may or may not be related." Claude correctly
disregarded it as stray context rather than treating it as an instruction to act on, because it had
no bearing on the actual request. This is the concrete behavior Part 7's "relevance discrimination"
names: not every retrieved/selected/adjacent passage is equally relevant merely because it arrived
in the same context window. GO's own future evidence-gathering (Load in the rhythm above) must
carry the same discipline — distinguishing relevant evidence from merely nearby, stale, superseded,
conflicting, or unsupported material — rather than treating everything a search or a Spin turns up
as equally load-bearing. No existing GO primitive performs this discrimination today; it is an
implicit property of how a future orchestrator (`services/conversational_turn.py`, specified but
not wired in — see `CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3, still not authorized) would need to
build its Context Envelope, not a new object.

### Reasoning discipline, not permission level

The one distinction this addendum states most sharply, because collapsing it would be a real
defect, not a style choice: **GO should inherit Claude's investigative reasoning pattern; it must
not inherit Claude's operating authority.** Claude, in this repository, may read code, search
broadly, form hypotheses, edit files, run tests, and (with the human's standing authorization for
this specific class of work) commit and push. GO must not acquire the professional-project
equivalent of that latitude merely because it reasons the same way — GO must not become, on its
own authority, the architect, engineer, designer, Construction-Management authority, Owner, or
issuer of consequential correspondence. This is not a new invariant to build toward; it is the same
coordinator boundary the `CLAUDE-GO-DNA-02` addendum already recorded (`BEHAVIORAL_CONTRACT`'s
"never create one yourself"; `create_rfi_draft`'s `ReviewerValidation` gate), now named explicitly
against the Claude-authority comparison the Product Owner raised, so a future session does not
mistake "GO reasons like Claude" for "GO may therefore act like Claude."

### Technical truth-seeking versus strategic communication

A new distinction, not previously named in this corpus: GO investigating project evidence answers
"what is actually happening" (technical truth-seeking); a human deciding whether/when/how to raise
it externally answers a separate question — who should hear it, through what channel, with what
consequence (strategic communication). The Roof Scupper canonical case above already demonstrates
both existing as separate steps (technical concurrence from the site architect; separate
commercial/risk concurrence from Construction Management) — this addendum names the general
principle the specific example illustrates: **a technically correct finding does not automatically
justify immediate external issuance, and a strategically sensitive condition must not be hidden
merely because it is inconvenient.** GO's role is to help the PM navigate that tension, not to
resolve it unilaterally in either direction. No new object is implicated — this sharpens how the
existing technical/commercial concurrence gap (named, not built, above) should eventually be
designed when it is authorized.

### What this addendum changes about the current implementation sequence

Nothing, by the Product Owner's own explicit instruction ("do not stop the current bounded product
work and begin a giant intelligence rewrite"). The existing priority order recorded under
`CLAUDE-GO-DNA-01`/`CLAUDE-GO-DNA-02` stands: finish the currently in-flight bounded work, then
reassess `CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3 from the accepted baseline, with this addendum's
reference-model framing and reasoning-discipline/authority distinction folded into that reassessment
rather than triggering a separate design pass now. The full Spin programme (this document's own
primary subject) remains specified-unbuilt, unchanged by this addendum.

---

## Addendum (`CLAUDE-GO-DNA-04`) — Belousov–Zhabotinsky analogue: emergent evidence-field patterns

Recorded following a Product Owner clarification naming the scientific reference behind the
"storm through dust / self-organizing color-pattern" metaphor used earlier in this corpus: the
**Belousov–Zhabotinsky (BZ) reaction**, a classic non-equilibrium chemical oscillator whose local
interactions produce self-organizing spatiotemporal patterns (waves, spirals). **Explicitly a
conceptual analogue, not a claim that GO reproduces chemistry.** Per the Product Owner's own
constraint, this addendum does **not** authorize a literal chemical simulation, a pattern engine,
or a visually decorative spiral system. **No code changes accompany this addendum. NOT AUTHORIZED**
for implementation or further design.

### Product meaning

The intended investigative field should not be forced prematurely into a rigid tree. A project's
evidence — fragments, weak relationships, contradictions, hypotheses, wondering notes,
requirements, findings, unresolved tensions, stakeholder responses — may coexist in large numbers
simultaneously, with local relationships among them producing larger patterns without a PM having
to predetermine what the significant pattern will be:

> evidence field → local interactions → temporary clusters/patterns → strengthening or weakening
> relationships → emerging project significance

### Mapping onto the already-recorded Spin/Probe/Echo/Pass/Build vocabulary (this same document, above)

This addendum does not introduce new top-level concepts — it describes the *behavior* the
already-named Spin/Probe/Echo/Pass/Build stages should eventually exhibit, once authorized:

- **Spin → emergence.** A comprehensive Spin broadly excites/interrogates the evidence field and
  lets patterns emerge, rather than requiring the PM to predetermine the important pattern in
  advance.
- **Probe → interrogation.** The bow/probe mechanism (`CLAUDE-GO-DNA-02` addendum, above) is
  deliberate attention aimed at one emerging pattern, not a fixed branch of a tree.
- **Echo → reorganization, not merely branching.** A probe's response may strengthen a pattern,
  weaken it, contradict it, dissolve it, merge it with another, reveal a new one, or redirect
  attention elsewhere — a genuinely different behavior than "Echo adds a child node," and the
  reason this is recorded as its own addendum rather than folded silently into DNA-02's rhythm.
- **Pass → human stabilization.** Adjudication (already a real, closed vocabulary via
  `REQUIREMENT_ADJUDICATION_OUTCOMES`/`ReviewerValidation`/`Disposition`, confirmed in this same
  document's own "what already exists" section above) is what turns an emergent pattern into
  accepted project understanding — not the pattern's own persistence or repetition.
- **Build → governed incorporation.** Unchanged from this document's own existing treatment
  (`WorkProduct`'s draft→review→approve→issue lifecycle, above).

### Relationship to existing evidence-relating machinery

`CLAUDE-GO-DNA-02`'s own addendum (above) already found the closest existing primitive: MM6's
relationship layer (`record_evidence_relationship`/`resolve_relationship_status`,
`services/case_workspace.py`), which connects two endpoints at a time, validated against
`_MM6_ENDPOINT_LISTS`. Whether pairwise relationships can generalize into an N-fragment,
strengthening/weakening/merging "pattern" without a new object remains **unresolved, not
investigated by this addendum either** — restated here because the BZ analogue makes explicit
*why* that generalization eventually matters (a pattern is not just a longer chain of pairwise
links; it can merge, dissolve, and re-emerge), not because the answer has changed.

### Relationship to Adaptive Attention / gear-attention (cross-reference, not duplication)

`adaptive-attention-and-context-circulation.md` (also NOT AUTHORIZED, concept-preservation only)
already names adjacent concerns from a different angle — compound-eye passive/active attention,
selective context circulation, "contextual defence against unrelated retrieval," and, most
relevant here, **"human authority over significance... the mechanism assists, it does not
override."** That same constraint applies directly to this addendum's emergence model: patterns
may self-organize, but a human's judgment of what matters remains authoritative — self-organization
proposes candidate significance, it does not adjudicate it. These two records describe the same
underlying tension (how much structure/salience the system may infer versus how much the PM must
still decide) from two different entry points — evidence-pattern emergence here, attention/
salience-across-Investigations there — and should be read together when either is eventually
designed, not merged into one document now.

### The hard constraint: provenance is not optional

Natural self-organizing systems do not need to explain their history; GO does. Even if GO's
investigative field behaves fluidly, it must preserve enough provenance to reconstruct which
evidence contributed to a pattern, what triggered its emergence, which probes tested it, what
echoes changed it, how the PM redirected it, and what was ultimately adjudicated. The desired
combination, stated verbatim: **self-organizing emergence + forensic reconstructability.** This is
consistent with, not additional to, this corpus's existing forensic-integrity requirements
(`CLAUDE-GO-DNA-02`'s own evidence-vs-wondering distinction; `RFIDraft.reference_snapshot`'s
already-real precedent for capturing a decision's own evidentiary basis at the moment it was made)
— any future emergence mechanism must be held to the same standard, not a looser one, precisely
because its behavior is less linear than the current tree-shaped UI.

### What this addendum changes about the current implementation sequence

Nothing. Concept-preservation only, per the Product Owner's own explicit instruction against
overbuilding. The full Spin programme, including this emergence behavior, remains specified-unbuilt.

---

## Addendum (`CLAUDE-GO-DNA-05`) — Evidence-driven question formation: a practical product directive

Recorded following a Product Owner clarification stated explicitly as a **practical product-
development directive**, not philosophy: GO must not depend on the user already knowing the right
question. It should detect conditions in project evidence that create a reason for a question to
exist, formulate that question, test it against the project, and present the resulting finding for
human judgment. **No code changes accompany this addendum. NOT AUTHORIZED for implementation.**

### A correction to `CLAUDE-GO-DNA-02`'s own audit, made while grounding this one

Repeated inspection while answering this addendum's required response found a primitive that
addendum under-credited: **`Claim`/`InvestigationClaim` (`CLAUDE-MM7`, `services/case_workspace.py`,
`record_investigation_claim`)**, attached to an `InvestigationStep`. It is real, wired end-to-end —
a live route (`POST /documents/<project_id>/investigations`, `routes/api.py`, calling
`services/cross_modal_investigation.py`'s `investigate_cross_modal_question`) and a live UI
(`static/js/drawing_image_viewer.js`'s drawing-viewer question box) — and structurally closer to
this addendum's own Evidence → Tension → Candidate Question → Investigation → Finding progression
(§4 of the governing prompt) than `ComposerFinding` is:

- `evidence_links` (list of typed references, validated against `_MM6_ENDPOINT_LISTS`) makes a
  hallucinated citation structurally impossible, not merely discouraged — `record_investigation_claim`
  requires at least one for every `claim_class` except the honest-abstention class
  (`CLAIM_CLASS_UNKNOWN`). This already IS the "why did you ask this" requirement (§5 of the
  governing prompt), enforced at the data layer, not merely at the prompt layer.
- `confidence_state` (`KNOWN_CONFIDENCE_STATES`, 7 closed values) already includes
  `conflicting_support`, `stale_evidence`, and `insufficient_evidence` — real, testable vocabulary
  for exactly the "reinforce/inhibit/stale-evidence" behavior §7 (A–F) describes, not a future
  design question.
- `claim_class` includes `CLAIM_CLASS_CONFLICTING` (a named inhibit signal) and
  `CLAIM_CLASS_DECISION_REQUIRING_AUTHORITY` (a named "this needs a human" signal) — closed
  vocabulary, not free text.
- `contradiction_relationship_ids` references real MM6 Relationships — the concrete mechanism by
  which one Claim can name what it conflicts with, without re-describing the conflict in its own
  words.
- `adoption_state` starts at `CLAIM_ADOPTION_PROPOSED` uniformly for every `author_type` (including
  `human`) until a human adopts it — already the general form of "weak wondering stays separate
  from promoted Finding" (§15 of the governing prompt), not a gap to fill.
- `evidence_excluded`/`assumptions`/`recommended_next_check` (verified present on `Claim`) are close
  to, respectively, a relevance-discrimination record, an explicit honesty-about-inference field, and
  a literal candidate-next-question field.
- `propose_ai_assisted_claim` (`services/cross_modal_investigation.py`) is a real, optional,
  externally-gated LLM call producing `author_type=OBSERVATION_AUTHOR_AI` claims — `record_investigation_claim`
  structurally refuses to pair AI authorship with a `DIRECTLY_VERIFIED`/`DETERMINISTIC_CALCULATION`
  class (Section 13's "do not claim deterministic computation when the result was AI-generated").

**The one precise, load-bearing gap, confirmed by inspecting the route directly**: `create_investigation`
requires `question` as a required JSON field (400 if absent) — it *investigates* a supplied question
deterministically by walking every real Relationship the anchor object participates in, recording
one Claim per contradiction/stale-endpoint/ordinary-support found. It does not, and structurally
cannot today, *form* the question itself from a noticed condition. Question-formation — the actual
subject of the governing prompt's §1 and §4 — has no existing primitive anywhere in this repository.
This is a materially different (and smaller) gap than treating the whole loop as unbuilt would
suggest.

### Correction to `CLAUDE-GO-DNA-02`'s Re-aim claim

That addendum stated "nothing links step N's conclusion to step N+1's own question." More precisely,
verified again here: `InvestigationStep.branched_from_step_id` (`services/case_workspace.py`) is a
real schema field with a corresponding `record_investigation_step` parameter — a named persistence
extension point for exactly this — but no route or caller anywhere in the repository ever sets it.
The seam is schema-ready, not code-absent; what's missing is the orchestration that would ever
populate it, not the field itself.

### Weak-signal vocabulary (§7 A–F of the governing prompt), mapped to what exists versus what doesn't

| Governing-prompt concept | Existing primitive | Gap |
|---|---|---|
| A. Multiple weak signals coexist | `Claim.confidence_state`/`claim_class`, unpromoted until `adoption_state` changes | Real at Case/Investigation level; no project-level equivalent for `ComposerFinding` |
| B. Signals reinforce | Multiple `Claim`s citing overlapping `evidence_links` | No aggregation/scoring across Claims exists |
| C. Signals inhibit | `contradiction_relationship_ids`, `CLAIM_CLASS_CONFLICTING`, `confidence_state=conflicting_support` | Real, named, closed vocabulary — not a gap |
| D/E. Patterns merge/split | — | No existing primitive; not investigated by this addendum |
| F. Patterns may die | `adoption_state` can presumably move to a rejected/dismissed state (vocabulary not fully audited here) | Not confirmed either way — a follow-up repository check, not answered by this addendum |
| G. Provenance survives | `evidence_links`/`RFIDraft.reference_snapshot`/`contradiction_relationship_ids` | Already the corpus's standing discipline (`CLAUDE-GO-DNA-02`'s evidence-vs-wondering distinction), not new |

### Seam classification (per the governing prompt's own §17 request)

- **Current commercial blocker:** none identified. The near-term proving loop (`CLAUDE-GO-COMPETE-01`)
  does not depend on spontaneous question-formation to demonstrate value today.
- **Near-term accelerator:** an orchestration layer that triggers `investigate_cross_modal_question`'s
  existing deterministic relationship-walk from a *detected structural condition* (an unresolved
  `CLAIM_CLASS_CONFLICTING`, a `stale_evidence` claim nobody adjudicated, an addendum superseding an
  earlier value) instead of only a human-supplied `question` string. This is the smallest concrete
  step toward §1's core ask, and composes with `CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3 rather than
  requiring a new stage.
- **Specified-unbuilt (this addendum's own primary content):** question-formation as a first-class
  object/capability; the Finding Quality Test (§14 of the governing prompt) as an enforceable
  contract rather than a checklist; user-writing-as-weak-signal (§9); pattern merge/split/death
  (D/E/F above); a project-level (`ComposerFinding`-scoped) equivalent of `Claim`'s adoption/
  confidence machinery.

### The Finding Quality Test (§14 of the governing prompt), preserved verbatim as a future contract

> 1. What caused GO to notice this? 2. What evidence supports it? 3. What evidence contradicts or
> weakens it? 4. Why might it matter? 5. What remains unresolved? 6. What question would test it?
> 7. What project stage/discipline does it affect? 8. How urgent is it and why? 9. Who should
> review/consult before action? 10. What human decision is actually required?

Recorded here as the eventual acceptance bar for any machine-originated Finding (project- or
Case-scoped) — not built, not enforced by any current test, but the concrete standard a future
`ComposerFinding` generalization or Stage 3 orchestrator should be measured against before shipping.

### What this addendum changes about the current implementation sequence

Nothing. Concept-preservation only, per the governing prompt's own explicit "acceleration, not
architectural expansion for its own sake." The existing priority order stands: finish current bounded
work, then reassess `CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3 from the accepted baseline, with the
near-term-accelerator seam named above available to fold into that reassessment if and when Stage 3
is separately authorized.
