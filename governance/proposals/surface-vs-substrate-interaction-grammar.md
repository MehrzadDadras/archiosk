# Proposal — Surface vs. Substrate: An Interaction Grammar for Record-Grounded Provenance

**Status:** PROPOSAL. Analytical synthesis only. No implementation authorized by
this document, and none performed while writing it. Nothing here amends
`constitutional-invariants.md` or `STATUS.md`.

**Baseline this describes:** `main` @ `6937b1a`. Measured directly, not recalled.

**Read this first.** The provenance repair discussed throughout
(`CaseWorkspaceStore.finding_provenance`) **is not on `main`.** It exists only on
`origin/spike/multi-surface-canvas` @ `f0a12ce` and is unmerged. On `main` today,
`templates/case_workspace.html:3210` still gates the entire Finding provenance
block on `{% if artifact %}`, and the hardcoded confidence float is still
rendered. Every "current state" claim below is `main`'s, and every empirical
result is from the spike branch's trial. Conflating the two would make this
document assert a repair the product does not have.

---

## 1. The paradigm, restated as three constraints

The Product Owner's framing, taken as binding for this proposal:

1. **Calm Surface ≠ Opaque Surface.** Reduction that removes the *route* to
   evidence is not calm; it is quiet.
2. **Grounded Provenance ≠ Permanent Technical Chrome.** The obligation is that
   evidence be *reachable*, not that its controls be *always visible*.
3. **The Anti-Fluency Constraint.** Simplification must never manufacture
   unearned epistemic confidence. Fluency, inferred references, and
   prose-derived citations must never substitute for record-grounded provenance.

Constraint 3 is the one this project learned empirically rather than assumed,
and it is the reason this document exists. It is developed in §4.

### 1.1 The decomposition the constraints imply

Provenance has **two independent properties**, and this codebase has never
separated them:

| Property | Question | Where it is decided |
|---|---|---|
| **Groundedness** | Does the citation trace to what was actually read? | the derivation |
| **Reachability** | How many actions from assertion to evidence? | the surface |

They are orthogonal, and all four combinations are constructible. Three of them
have now been observed in this product:

|  | Reachable | Not reachable |
|---|---|---|
| **Grounded** | *the target state — never yet built* | `main` today, and the spike's Arm A (line 337 of 388) |
| **Not grounded** | the spike's Arm B — **the dangerous cell** | pre-repair `main` for artifact-less Findings |

The engineering error to avoid is treating this as one axis. "Improve
provenance" has meant *groundedness* in every prior stage of this repository.
The blind trial showed that a surface can score perfectly on groundedness and
still deliver nothing, and — far more dangerous — can deliver fluently while
grounded in nothing.

---

## 2. Comparative landscape

Each entry: the transferable principle, then where it fails for a
high-liability technical domain. The failures matter more than the principles;
the principles are widely known and the failure boundaries are not.

### 2.1 Apple / consumer systems

**Principle.** Progressive disclosure bound to a single object: the thing you
touched offers the actions. Persistent chrome tells you *where you are* (tab
bar, nav bar), never *what you could do*. Reduction is enforced upstream by
hardware constraint, so the desktop inherits a vocabulary the phone already
pruned.

**Where it fails here.** Consumer calm assumes actions are reversible and
stakes are low, so hidden state is state you genuinely do not need. In a
liability domain, the state you "do not need" to complete a task may be exactly
the state that makes the resulting claim defensible. Apple's design language has
no concept of *evidence* — nothing in it distinguishes a value the system
measured from a value it inferred. Adopting its reduction without adding that
distinction is how a calm surface becomes an opaque one.

**Also note:** ARCHIOSK got Apple's reduction backwards. The phone breakpoint
already performs a real reduction, and `static/css/main.css` records the
reasoning for it verbatim — *"DISABLED ITEMS ARE NOISE HERE, NOT INFORMATION"*,
and the rejection of *"four competing permanent panes"*. That reasoning was
never propagated back to the desktop. The constraint produced the insight and
the insight stayed where the constraint was.

### 2.2 Figma / infinite-canvas tools

**Principle.** *The panel is a function of selection.* Figma carries a feature
surface comparable to ARCHIOSK's and shows almost none of it, because the
inspector renders the selected object's properties and nothing else. Its guard
axis is **what is selected**. Multiplayer presence is ambient and non-intrusive;
follow-mode is opt-in and reversible, and observing never seizes the observed
person's camera.

**Where it fails here, and this is the sharpest limit in this section.** Figma's
inspector works because **a Figma object contains its own truth**. A rectangle
*is* its fill, stroke and position; inspecting the object and inspecting its
basis are the same act. An ARCHIOSK Finding is the opposite: it is a claim
*about* documents it is not. Selecting it and inspecting it yields the assertion,
not its basis.

**Therefore:** the inspector pattern transfers only if *basis* is modeled as
part of what is selectable. "Inspect the claim" must be a different, adjacent
act from "inspect what the claim rests on," and both must be one gesture from
the claim.

### 2.3 Google Maps / GIS

**Principle.** Density is a function of zoom, not a setting — labels appear and
recede with scale, and the user never opens a preferences pane to manage
clutter. No mode selection precedes the task: you type, and the system decides
whether that was a place, a route, or a business.

**Where it fails here.** Maps carries attribution globally (*"Map data ©…"*) and
essentially never per-feature. You cannot ask a road which survey established
it. Per-feature provenance under level-of-detail is an unsolved problem there,
because Maps has no liability surface — nobody is professionally accountable for
a mislabeled café.

**The rule this forces, and it is non-negotiable:** **provenance is
LOD-invariant.** Semantic zoom may thin *detail* — labels, secondary marks,
annotation density — but the *route from an assertion to its evidence must
survive every zoom level*. A design that drops the citation at low detail has
reintroduced the opacity the calm surface was supposed to avoid, and has done it
in the one state where the user is most likely to be forming an overview
judgment.

### 2.4 Bluebeam / Procore / traditional AEC

**Principle (Bluebeam).** A markup is a first-class object carrying author,
timestamp and status; the markup list is a *table view of the same objects* on
the page, and selection is bidirectional — click either, both highlight. This is
the correct precedent for Findings, and the closest thing in the market to what
ARCHIOSK needs.

**Cost (Bluebeam).** One of the most toolbar-dense professional applications in
existence, and in practice every user turns most of them off. The persistent
chrome is a tax paid continuously for capability used intermittently.

**Principle (Procore/ACC), mostly negative.** These are *module directories* —
RFIs, Submittals, Drawings, Meetings, Daily Logs. The user's actual task ("is
this door rated?") maps onto no single module. ARCHIOSK's app menu is one step
from being the same thing.

**The uncomfortable calibration.** Their surfaces are widely disliked and they
win the market anyway, because the RFI has a number and an audit trail. **In this
category the substrate sells and the surface retains.** A calm surface is a real
differentiator and a real driver of daily use; it is not the commercial moat,
and this proposal should not be argued as though it were.

### 2.5 Game HUDs and simulation engines

**Principles.** *Diegetic* display puts information in the world rather than in
a HUD. The HUD recedes when nothing is happening and returns on relevance.
Tutorialization by constrained affordance. And: **never render a disabled
control** — show nothing, or show a locked thing with a legible reason.

ARCHIOSK's own CSS reached the last of these independently and wrote it down;
thirteen of the drawer's sixty-one items are disabled in a given context, and
the file calls that noise rather than information.

**Where it fails here, and this shapes the whole grammar.** Games can afford
ambiguity: a misread HUD costs a life, not a professional liability. More
structurally — **not all provenance is diegetically representable.** A drawing
can carry a spatial mark (a region, a callout, a sheet reference) because those
things *are* spatial. It cannot naturally carry "who reviewed this, when, and
whether anyone confirmed it." Author, timestamp and adjudication state have no
position in the drawing's own coordinate system.

**This forces a hybrid, and the split is principled rather than aesthetic:**

- **Diegetic** — evidence with a *spatial* referent: sheet, page, region,
  callout, schedule row. Belongs on the canvas, at its location.
- **Non-diegetic** — evidence with a *governance* referent: author, method,
  time, verification state, adjudication history. Belongs in a contextual
  inspector, summoned, never permanent.

Attempting to make governance evidence diegetic produces decoration. Attempting
to make spatial evidence non-diegetic produces the current Findings list, where
"source: `<uuid>`" describes a location the reader cannot go to.

### 2.6 ARCHIOSK — honest self-critique, measured on `main` @ `6937b1a`

| Measurement | Value |
|---|---|
| Distinct `data-ui-ref` values in `templates/` | **585** |
| `static/css/main.css` | **9,642** lines |
| `templates/case_workspace.html` | **4,154** lines |
| `templates/base.html` | **2,436** lines |
| Registered routes | **202** |
| `getElementById('doc-…')` calls in `pdf_viewer.js` | **30** |
| Finding provenance gate | `{% if artifact %}` — `case_workspace.html:3210` |
| Hardcoded confidence float rendered | yes, 1 site |

Prior audit, same corpus: **193 of 380** live controls with a project open are
permanent chrome (51%), gated by essentially two conditions — `authenticated`
and `project open`. There is no third axis: nothing narrows by task, by role, or
by what the person is doing. Figma's third axis is *selection*, and its absence
here is the single largest structural cause of the 51%.

**The false choice, stated precisely.** On `main`, a professional asking "is this
door rated?" gets one of exactly two things:

- For a **drawing-analysis** Finding: provenance rendered as `source: <uuid>` —
  plain text, no link, while the document list shows names and not ids, so the
  id cannot even be matched by eye. The human name *is* resolved by
  `build_reference_snapshot` and printed roughly a hundred lines lower in the
  RFI card, for the same document.
- For a **requirement-investigation or quantitative-investigation** Finding: no
  provenance block at all, because no Artifact was minted — while
  `AnalysisRun.source_ids` sits in storage recording exactly which documents
  were read.

Both branches are grounded and unreachable. The chrome tax is real and separate:
in the trial, the repaired provenance sat at **line 337 of 388** rendered lines —
87% down the page, behind an unprompted *"Attention is full"* modal in a project
holding one Investigation, a *"Not found"* image-search string with no image in
play, and the four document names repeated **six times**.

**The trap to name explicitly.** `pdf_viewer.js` resolves **30** document
controls — page, zoom, fit, rotate, search, download, print, snapshot — by
`getElementById` against `base.html`'s menu bar. In a chrome-less render they are
all `null`, and the file's own comment confirms this degrades silently. **A
meaningful share of the permanent chrome is the implementation of the *Look*
verb, not accretion.** Any proposal that reads "51% is furniture, delete it"
deletes navigation and calls it simplification.

---

## 3. Empirical basis

`CLAUDE-ARM-A-PROVENANCE-01` (`4ae07b9`) and `CLAUDE-ARM-B-CANVAS-01` (`f0a12ce`),
both on the unmerged spike branch. Full record:
`governance/specified-unbuilt/provenance-at-the-point-of-interaction.md`.

One real question — *"Is door D-106 rated?"* — from the metabolic bridge blind
coordination audit, where ground truth was known. Two fresh agents, each given
only an entry URL and the question; neither told which surface it had, that a
second existed, or the answer; both forbidden from reading the repository. Both
arms shared the same authorization choke point and the same derivation.

| | Arm A (full chrome, repaired) | Arm B (calm canvas, un-repaired) |
|---|---|---|
| Views to verified answer | **3** | **3** |
| Inspection order | entry → A-601 → A-101 | entry → A-601 → A-101 |
| Provenance position | line 337 / 388 | first screen |

**Equal step count, identical unprompted inspection order.** Both subjects
attributed the ease to evidence links being present.

**Stated at the strength the evidence carries:**

- **Evidence links matter — suggestive, not confirmed.** The isolating condition
  (no links at all) was never run deliberately; it occurred once by accident when
  a harness defect truncated Arm A's page, and that subject took **6** views
  rather than 3. Different subject, contaminated run. One observation.
- **Chrome costs attention, not steps.** It did not move the step count.
- **The fixture leaked the answer** — the finding sentence stated the
  conclusion — so the retrieval measure is permanently weakened for both arms.
  What it does not contaminate is verification behaviour: both subjects went to
  the documents rather than trusting the sentence.

---

## 4. The Anti-Fluency Constraint, developed

This is the finding the trial produced that was not anticipated, and it is the
load-bearing idea of this proposal.

**Arm B's citations were parsed from the claim's own prose.** They resolved sheet
tokens and schedule marks out of the finding's sentence and rendered them as
confident deep links. They were *more reachable* than Arm A's and *epistemically
weaker*: had the sentence named a document the analysis never opened, Arm B would
have rendered an equally confident link to it. Its subject trusted those links
completely and said so.

**A citation that can lie is worse than a UUID, because it carries more
authority.** A raw id is inert and obviously unhelpful; the reader knows they
have been given nothing. A fluent, well-labelled, clickable citation *terminates
inquiry*. It is the more attractive failure, which is precisely why
simplification pressure selects for it.

Generalized: **reachability is easy to improve by ungrounded means, and those
means feel like progress.** Any future work that makes provenance more reachable
must be checked against what the new mechanism is grounded in, or it will drift
toward fluency by the path of least resistance.

### 4.1 The rule this yields

> **Every citation surface must be able to state its own basis, and bases that
> differ in strength must not be rendered identically.**

Concretely, a closed, derivation-owned vocabulary — the same discipline
`RESOLUTION_STATUS_*` and `PROVENANCE_BASIS_*` already use, where the evaluator
names its own outcome and a caller never supplies one:

| Basis | Means | Strength |
|---|---|---|
| `located` | a specific region of a specific page (Artifact) | strongest |
| `read` | a document the analysis actually opened (`AnalysisRun.source_ids`) | strong |
| `asserted` | named in the claim's text; **not verified as read** | weak — must be visually distinct |
| `none` | no basis on record | rendered as a real answer, not a blank |

**`asserted` may never be rendered in the same visual form as `read` or
`located`.** If a prose-derived jump is offered at all, it must read as *"the
statement names A-601"* and not as *"this came from A-601"*. The spike's Arm B
violated this and is the reason the rule is written down.

A corollary the trial also produced: a citation must not assert a location for a
thing that has no location. Arm B rendered `→ D-106 in A-601` for a finding whose
entire content is that D-106 is **absent** from A-601. Its subject flagged it
unprompted. Negative findings need negative-form citations —
`→ D-106 absent from A-601`.

---

## 5. Deliverable 1 — The interaction grammar

The four verbs are already settled: **Look, Point, Ask, Commit**, with Commit
bound to an identified companion. Provenance attaches to **Point**.

### 5.1 Three tiers, each one gesture from the last

| Tier | Content | Surface | Persistence |
|---|---|---|---|
| **0 — Assertion** | the claim + its **basis badge** + verification state | in place, with the claim | always with the claim |
| **1 — Basis** | which documents, by name, and each one's **role** in the claim | contextual inspector, summoned by Point | dismissible |
| **2 — Evidence** | the document itself, at its location where basis permits | the canvas | replaces the view |

**Tier 0 is the anti-fluency tier and is never optional.** An assertion that
renders without a basis badge is a fluency defect regardless of how calm the
surface is. `Machine finding · Unverified` already does half this job on `main`
and demonstrably works: Arm A's subject saw it and **refused to accept the
conclusion without opening the sources**. That badge earns its place and should
be extended, not replaced.

**Tier 1 carries role, not just identity.** "Read from A-101, A-601" is weaker
than it looks for a coordination defect, because it does not say what each
document contributed. See §6.

**Tier 2 is diegetic; Tiers 0–1 are non-diegetic.** Per §2.5: spatial evidence
goes on the canvas at its location; governance evidence goes in the inspector.

### 5.2 What this replaces, and what it must not resurrect

- **Replaces:** the permanent Findings accordion at the bottom of a 388-line
  page, and the `source: <uuid>` line inside it.
- **Must not resurrect:** a persistent menu bar. But see §5.3 — this cannot be
  done by deletion alone.

### 5.3 The Look prerequisite, which is a hard sequencing constraint

Because 30 document controls resolve against `base.html`'s menu bar, **a
canvas-native Look vocabulary must exist before any chrome reduction, not
after.** Minimum, all diegetic and all non-persistent:

- pan (drag), zoom (wheel/pinch), fit (double-tap)
- a **sheet/page indicator that appears on change and recedes when idle** —
  the games HUD pattern, not a permanent readout
- page/sheet traversal without a persistent prev/next control
- **document switching without a Lists rail** — an auto-hiding index, closed by
  default

The spike demonstrated all of these are constructible and that a chrome-less
render of the same route is ~9 KB against ~167 KB, with 10 instrumented controls
against 251. It also demonstrated that omitting document switching makes the
surface unable to express the task at all.

**Ordering is not a preference here.** Reducing chrome before Look is
canvas-native removes navigation and leaves a drawing nobody can move.

---

## 6. Deliverable 2 — Progressive disclosure for multi-sheet coordination defects

A coordination defect is **not a property of a document; it is a relationship
between documents.** D-106 is a defect because it is *present on A-101* and
*absent from A-601*. Prose flattens this into one sentence and a flat citation
list flattens it further — "read from A-101, A-601" discards which side
contributed what, which is the entire content of the finding.

### 6.1 Contrastive disclosure

Tier 1 for a coordination defect should be **two-sided and role-labelled**,
not a list:

```
D-106
  present    A-101 Level 1 Floor Plan      basis: read     [open]
  absent     A-601 Door Schedule           basis: read     [open]
             — schedule runs D-101…D-105, D-107; no D-106 row
```

Both blind subjects reconstructed exactly this by hand, and both independently
observed that the *gap between D-105 and D-107* is what converts "an omission"
into "a single targeted RFI." The surface made them derive it; it should carry
it.

### 6.2 Scope, because absence is only meaningful against a checked set

Both subjects, independently, asked whether D-106 was the only gap and whether
four sheets were the whole set. One put it precisely: *"On a real set with 400
doors I would need the surface to tell me '1 of N door tags unmatched'."*

**A negative finding must disclose the extent of the check that produced it.**
"No row for D-106" is not actionable without "7 tags on A-101, 6 matched, 1
unmatched, 4 documents examined." Without it a reader cannot distinguish a
thorough check from a shallow one, and — worse — cannot tell whether silence
means "checked and absent" or "not checked."

This is where `asserted`-basis citations become actively dangerous rather than
merely weak: a prose-derived citation list has **no denominator at all**.

### 6.3 Zoom behaviour

Per §2.3, provenance is **LOD-invariant**. As a drawing zooms out, annotation
density may thin; the basis badge and the route to Tier 1 must not. A finding
that becomes uncitable at overview zoom is uncitable exactly when a reader is
forming a summary judgment.

### 6.4 The action boundary

Both subjects, independently and as their top-ranked gap, reported that a
confirmed defect had **nowhere to go**. `Export RFI` exists in the File menu; the
investigation was literally titled "Door rating coordination"; the two never
meet. One wrote: *"I can read it and confirm it, but I cannot do anything with it
from where I am standing."*

Disclosure that terminates at understanding is incomplete. **Tier 1 must offer
the governed action** — and per the four-verb grammar, Commit stays deliberately
effortful, attributed, and companion-identified. Calm applies to *understanding*;
friction at the approval gate is a feature, not a defect to smooth away.

---

## 7. Deliverable 3 — Maintaining the adversarial methodology

`CLAUDE-ARM-B-CANVAS-01` produced its most valuable finding *because the control
arm was built to win*. Had Arm B been a strawman, its citations would never have
worked well enough to reveal that a fluent citation can be wrong. Preserving that
discipline is the point of this section.

**1. Build the competing arm to win.** If the alternative cannot beat your
hypothesis, the test cannot refute it. An arm that fails by construction proves
your position by circularity, not by evidence.

**2. Vary one thing; share everything else.** Both arms went through the same
authorization choke point (`_load_workspace_or_404`) and the same derivation
(`finding_provenance`). Identical authorization is an *experimental control*, not
hygiene: an experiment whose arms are differently permissioned cannot attribute
outcomes to the thing it claims to test.

**3. Blind the subject.** No knowledge of which arm, that arms exist, the
hypothesis, or the answer. Forbid reading the repository. This project has used
blind agents productively before (the metabolic bridge coordination audits) and
should keep using them.

**4. Pre-register the prediction.** Write down the expected outcome before
running, so it can be wrong in the record rather than in memory.

**5. Instrument the harness for fidelity, and treat harness defects as
disqualifying.** The first run was invalidated by three defects, all mine — a
4,000-character print limit that cut one arm at 67% of its page and removed the
feature under test while leaving the shorter arm intact; a literal `\n` in a
fixture; and no HTML-entity decoding, which surfaced as a fake rendering bug.
**Check for asymmetric handicap explicitly:** a limit that binds one arm and not
the other is the failure mode to look for first, because it is invisible when
both arms "run fine."

**6. Never let the stimulus contain the answer.** The fixture's finding sentence
stated the conclusion, permanently weakening the retrieval measure. Design the
stimulus so the task *requires* the mechanism under test.

**7. Report at the strength the evidence carries.** Distinguish *measured*,
*suggestive*, and *single accidental observation* — in the durable record, not
just in conversation. A checkpoint entry outlives the discussion that produced
it, and an over-stated result becomes a premise for later work.

**8. Delete the apparatus; keep the finding.** `routes/spike_arm_b.py` and
`templates/spike/arm_b_canvas.html` were never committed and leave no trace in
git. The harness lived in the session scratchpad. The durable output is the
finding, not the ruler.

**9. Let a losing result stand.** The trial did not confirm the hypothesis it was
built to test — 3 views in both arms. Recording the tie, and the unexpected
finding it exposed, is worth more than a confirmed prediction would have been.

---

## 8. What this proposal does not authorize

- **No implementation.** No UI templates, CSS, routes or services are modified by
  this document, and none were touched while writing it.
- **No chrome deletion.** Blocked on canvas-native Look (§5.3), which is a
  sequencing constraint, not a preference.
- **No merge of the spike branch.** `origin/spike/multi-surface-canvas` @
  `f0a12ce` carries Arm A and remains unmerged; whether it lands on `main` is a
  separate Product Owner decision.
- **No claim that the trial confirmed the calm-surface thesis.** It did not.
- **No new abstraction beyond the basis vocabulary in §4.1**, which extends the
  existing `PROVENANCE_BASIS_*` shape rather than adding a parallel one.

## 9. Open questions this cannot settle

1. **Is the 6-vs-3 gap real?** The only cell separating "links" from "no links"
   came from an invalidated run. The cheap decisive test is a deliberate control
   arm: full chrome, no evidence links. Run before building on §4.
2. **Does contrastive disclosure (§6.1) survive real scale?** Demonstrated on a
   6-row schedule. A 400-door set is a different problem.
3. **Confidence calibration** — `reservations.md` item 14. Two model
   self-reported floats still render as precise percentages. Unresolved, and
   related: a percentage is a fluency risk of the same family as an ungrounded
   citation.
4. **Can `asserted`-basis citations be made safe at all**, or should they simply
   not be offered? This proposal requires them to be visually distinct; it does
   not establish that distinctness is sufficient.
