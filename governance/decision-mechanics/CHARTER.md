# Decision Mechanics — Research Charter

**Status: CHARTER.** This document states what the Decision Mechanics research
programme is trying to find out, and the frame in which a finding would count.
It is not doctrine, it is not a specification, and it authorizes nothing.

Specifically, and in the same terms `TEMPLATE.md` already binds every specimen
in this directory:

- It **does not amend** `governance/constitutional-invariants.md`, which keeps
  its own ratification process
  (`governance/governance-of-governance/amendment-and-ratification.md`).
- It **does not authorize implementation.** `governance/STATUS.md` governs
  domain-model feature authorization and is unaffected by anything written here.
- It **establishes no invariant.** The programme's whole subject is which
  operations turn out to be invariant; a charter that already knew would have
  nothing to research. Every candidate below carries its evidential status, and
  the two that rest on a single trial say so.

A charter is falsifiable in one specific way: if the research question below can
be answered without the decomposition it proposes, or if the decomposition
turns out to have no invariant residue at all, the programme was mis-framed.
That outcome is a result, and §6 says what it would look like.

---

## 1. The core research question

> **Can the transformation from unresolved possibility to consequential
> determination be decomposed into invariant operations that survive changes in
> person, AI model, language, representation, interface, and domain?**

Each of the six variables is there because it is a way the question could be
answered *no*, and each is independently testable:

| Variable | The negative result it would produce |
|---|---|
| person | the operations are a description of one practitioner's habits |
| AI model | they are an artifact of one model family's behaviour |
| language | they are a property of English, or of one professional register |
| representation | they are a property of drawings, or of prose, but not of both |
| interface | they are a description of this product's current screens |
| domain | they are a property of building codes and not of determination |

The programme has evidence against none of these yet, which is worth stating
plainly at the outset. `DM-0001` varied representation only, at n=1 per arm,
in one domain, with one pair of subjects. **Five of the six variables are
entirely unvaried in the record to date.**

### 1.1 What "consequential determination" means here, and why the word is narrow

A determination is consequential when acting on it changes something that
cannot be changed back by the same means — a wall closes, a submittal issues,
an RFI goes out, a design is built. The programme is not about opinion
formation, preference, or classification. It is about the specific
transformation after which the world is different and the decision-maker is
answerable for it.

This narrowness is deliberate and it is what makes the question empirical
rather than philosophical: a consequential determination leaves artifacts —
records, timestamps, attributions, approvals — and artifacts can be examined
after the fact by someone who was not there.

---

## 2. The historical sequence this programme places itself in

The claim being made by this section is **structural, not comparative**: that
each step took a transformation everyone believed required a particular
physical or semantic substrate, and showed that the substrate was incidental to
the invariant relations underneath. The claim is emphatically *not* that the
third entry has the standing of the first two. It does not. The first two are
established results with proofs; the third is an open research programme with a
single retrospective specimen, and the asymmetry is the point of putting them in
one table rather than a reason to leave the table out.

| | Shed | Invariant isolated |
|---|---|---|
| **Turing, 1936** | the physical human calculator — the clerk, the paper, the hand | **Computation.** Discrete state transitions over a finite alphabet. What a calculator *is* turned out to be incidental to what calculating *does*. |
| **Shannon, 1948** | semantic meaning, and the physical wire | **Information.** Uncertainty reduction, measured as entropy. What a message *means* turned out to be incidental to how much it *resolves*. |
| **Decision Mechanics, 2026** | cognitive scaffolding, specific models, and interface chrome | **Governed determination.** *Candidate:* the operations by which collaborative judgment becomes an answerable commitment. **Not isolated. Not established. This row is the open question, not a result.** |

**The methodological inheritance, which is the actual reason for the table.**
Both prior steps proceeded by *shedding* — by identifying what could be removed
without the transformation ceasing to work, and then treating the residue as
the object of study. That is a method this programme can borrow directly, and
`TEMPLATE.md` §6 already institutionalizes it under the name **Exuvia
Variation**: apparatus built in order to be discarded, where the measurement is
the organism and the apparatus is the cast skin.

**The disanalogy, stated because it constrains what this programme can hope
for.** Turing and Shannon each shed something that was genuinely inessential.
It is not established that cognitive scaffolding, model identity, or interface
are inessential to determination — and one of this programme's live findings
points the other way. `DM-0001` §13 records that *representation changed
judgment independently of the underlying facts*, in both directions. If the
interface is load-bearing rather than incidental, "shed the interface" is not
available as a move, and the third row would need restating rather than
completing.

---

## 3. The three operations of representational movement

These are the programme's **candidate** operations: the moves by which a
representation changes without the determination underneath it changing. They
are offered as a vocabulary for describing episodes, not as a closed set and
not as a claim that all three are real.

### 3.1 Abstraction (Exuvia)

> **Shed incidental embodiment once the invariant relations are isolated.**

Note the ordering, which is the whole content of the operation: *once
isolated*, not *in order to isolate*. Shedding before the invariant is known is
not abstraction, it is deletion — and this repository has a worked example.
`DM-0001` §11 and the interaction grammar's own §5.3 both record the same
sequencing constraint: `static/js/pdf_viewer.js` resolves 30 document controls
against `templates/base.html`'s menu bar, so a meaningful share of what looks
like removable chrome is the *implementation of a verb*. Reducing chrome before
a canvas-native `Look` vocabulary exists deletes navigation and leaves a drawing
nobody can move.

**Abstraction is therefore gated on a prior measurement,** and the failure mode
is that it feels like progress when performed early.

### 3.2 Preservation (Generative Symbols)

> **Retain irreducible tension where a symbol holds multi-dimensional meaning.**

Some symbols are load-bearing precisely because they have not been resolved into
one meaning, and flattening them destroys information that has no other home. A
drawing tag is simultaneously a location, an identity, a schedule row and a
contractual obligation; a code clause is simultaneously a requirement, a
jurisdiction and a date.

The operation says: **when a representation cannot be reduced without losing a
dimension, do not reduce it — carry the tension forward.** The corresponding
discipline already exists in this repository as the closed, derivation-owned
vocabularies (`RESOLUTION_STATUS_*`, `METADATA_RELIABILITY_*`,
`KNOWN_EVIDENCE_CLASSES`), each of which preserves a distinction that a simpler
boolean would have destroyed.

**This is the operation most in tension with product simplicity,** and the
tension is real rather than rhetorical: `CLAUDE.md` separately and correctly
holds that internal complexity must earn user visibility. Preservation is a
claim about what the *record* must retain. It is not a licence to surface every
retained dimension, and a specimen that uses it to justify another panel has
misapplied it.

### 3.3 Grounding (Manifestation)

> **Require abstract representations to yield to manifest evidence at the point
> of interaction.**

An abstraction earns its place only if, at the moment someone acts on it, it can
be made to produce the thing it abstracts. "At the point of interaction" is the
binding clause: evidence reachable in principle, or reachable by a specialist
later, does not satisfy it.

This is the operation with the most repository evidence behind it and it is
still not established. `DM-0001` §9 records that grounded links did **not**
reduce navigation cost on a clean fixture — all three control subjects reached
a verified answer in about three views with no citations at all. The value that
survived that result is different and narrower: a record-grounded link replaces
a silent, unverifiable human inference with an auditable one. Same destination,
different epistemics, and only one of the two leaves a trace.

---

## 4. Core epistemic axioms

"Axiom" here means **a premise the programme reasons from**, not a proven
result. Two of the three are candidates raised by a single specimen; one is
already constitutional. The difference is marked, because collapsing it would be
the exact failure mode the registry's standing rule exists to prevent.

### 4.1 Persuasiveness ≠ Groundedness

> **How convincing a representation is, and how well-founded it is, are
> independent properties. Representation confers authority that the underlying
> derivation may not have earned.**

**Status: candidate, n = 1 per arm.** Raised by `DM-0001`, whose own candidate
invariant is stated there as *"Reachability without grounding is a net epistemic
loss"* — and explicitly marked *not established*, one trial, one question, one
domain, one pair of subjects.

What the specimen actually observed, and it observed both directions:

- **Degrading.** Arm B's citations were parsed from the claim's own prose. They
  were *more* reachable than Arm A's and epistemically weaker, and its subject
  trusted them completely. A citation that can lie carries more authority than
  a raw identifier, because an identifier is inert and obviously unhelpful while
  a fluent, well-labelled citation *terminates inquiry*.
- **Improving.** Arm A's subject saw `Machine finding · Unverified` and refused
  to accept the conclusion without opening the sources — a representation that
  correctly *lowered* trust and drove verification.

The generalization the axiom licenses is narrow: **any mechanism that increases
reachability must be checked against what it is grounded in**, because
reachability is easy to improve by ungrounded means and those means feel like
progress. `DM-0001` §14 states the experiment that would disprove it — a
three-arm run measuring whether a subject detects a deliberately planted false
citation — and records that it has not been run.

### 4.2 Orthogonality of epistemic convergence and jurisdictional authority (E ⊥ A)

> **What is known and who may decide are independent axes. Movement along E
> never produces movement along A.**

**Status: constitutional, not a candidate.** This axiom is not proposed here;
it is already `governance/constitutional-invariants.md` #2 — *"Increasing
machine knowledge never automatically increases machine authority. Consequential
governed-state change always requires legitimate human or contractual
authority."* It is restated in this charter because the research question ranges
over AI models and interfaces, which is exactly the territory where the two axes
get quietly conflated.

Two existing records are the same orthogonality seen from other angles, and a
specimen touching authority should be read against both:
`governance/current/situational-attributes-are-not-authority.md` (authority is
read from project evidence, never inferred from the circumstances of the
question), and the standing rule that **selection supplies context, never
authorization** — pointing at a thing is what gives an action its subject, and
emphatically not what permits it.

**The consequence for this programme:** a specimen may report that convergence
improved without reporting any authority change, and `TEMPLATE.md` §10 already
requires exactly that — *"If the episode produced knowledge but no authority
change, say that plainly."* An episode that reports the two moving together
should be suspected of having measured one and inferred the other.

### 4.3 The Actionability Horizon

> **The value of intelligence decays as the window of consequential
> intervention closes. A determination delivered after the window has shut has
> no value, however correct it is.**

**Status: candidate, unmeasured in this repository.** No specimen has yet
measured decision value against remaining window; the axiom is currently a
design premise, not a finding, and any specimen citing it must say which of the
two it is relying on.

Three consequences the programme takes from it:

1. **Ordering by consequence and remaining window is not the same as ordering
   by severity,** and the two routinely disagree. A severe finding with a wide
   window can be correctly ranked below a moderate one whose window shuts this
   week.
2. **A window is an assertion and carries its own basis.** A date read from a
   construction schedule and a date inferred from a sentence must not render
   identically — this is §4.1 applied one level up from citations, and it is the
   place the fluency hazard is easiest to miss.
3. **An unestablished window must not be able to claim urgency by being
   unknown.** "We do not know when" becoming "it is urgent" is the same
   truth-promotion `constitutional-invariants.md` #1 forbids, wearing scheduling
   clothes.

---

## 5. What this charter deliberately does not do

- **It does not rank the three operations, or claim they are complete.** Three
  is what the current record suggests, not a closed set. A specimen that needs a
  fourth should propose one rather than force an episode into an existing name.
- **It does not create a vocabulary for the product.** `Exuvia`, `Generative
  Symbols` and `Manifestation` are laboratory terms for describing episodes.
  None of them is a UI concept, a route, a panel, or a field, and none should
  become one on the strength of appearing here. `CLAUDE.md`'s proliferation
  cycle — implementation distinction → explanation → terminology → abstraction →
  UI concept → governance record → more implementation — names this exact risk,
  and a charter introducing three new terms is precisely where it starts.
- **It does not license retrospective reinterpretation.** Existing specimens are
  not to be rewritten to fit this frame. If an episode does not decompose into
  these operations, that is evidence about the operations.
- **It does not settle whether the third row of §2 belongs there.** It states
  the claim so it can be argued with.

---

## 6. What would refute the programme as framed

Recorded now, before results exist, because a charter written so that no
outcome could embarrass it is not a research charter.

1. **No invariant residue.** If specimens varying person, model, language and
   domain show the operations changing shape each time, then what is being
   described is a practice, not an invariant, and the programme should be
   renamed rather than continued.
2. **The interface turns out to be load-bearing.** If representation cannot be
   shed without the determination changing — and `DM-0001` §13 is already
   evidence in this direction — then §2's third row is mis-stated, because
   "shed interface chrome" would not be an available move.
3. **The decomposition never does work.** If the three operations only ever
   describe episodes after the fact and never predict, constrain, or change
   what gets built, they are a vocabulary rather than a mechanics. The test is
   whether a specimen's §14 falsification was ever *designed* using them.
4. **The axioms collapse into one.** If persuasiveness/groundedness and E ⊥ A
   turn out to be the same distinction seen twice, the charter is carrying a
   redundant premise and should say so.

---

## Provenance

Written 2026-08-28 from Product Owner direction, grounded against the
repository state at the time of writing: `governance/decision-mechanics/`
(`TEMPLATE.md` and `specimens/DM-0001-arm-a-arm-b-provenance.md`, established at
`1e1564e`), `governance/constitutional-invariants.md` #1 and #2,
`governance/current/situational-attributes-are-not-authority.md`, and
`governance/proposals/surface-vs-substrate-interaction-grammar.md`.

Every claim attributed to `DM-0001` above was read from that file rather than
recalled, including its candidate invariant's stated status and sample size.
The historical characterizations in §2 are the charter's own framing of Turing
(1936) and Shannon (1948) and are offered as such — no claim is made that either
author described their result in these terms.
