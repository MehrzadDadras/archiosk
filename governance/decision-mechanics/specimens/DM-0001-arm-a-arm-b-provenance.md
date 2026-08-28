# DM-0001 — The Arm A / Arm B Provenance Trial

**Retrospective specimen.** Written 2026-08-28 from repository artifacts, not
from live instrumentation of the episode. Per `../TEMPLATE.md`'s standing rule,
every field the trial did not actually measure is marked `unmeasured` rather
than reconstructed.

---

## 1. Specimen Identity

| | |
|---|---|
| Identifier | DM-0001 |
| Episode date | 2026-08-28 |
| Log date | 2026-08-28 (retrospective, same day) |
| Log basis | Repository artifacts only |

**Primary artifacts, verified against the tree:**

| Artifact | Full SHA | Reachability |
|---|---|---|
| `CLAUDE-ARM-A-PROVENANCE-01` | `4ae07b98a5561d605eba77e35a5e9ccbbcfa314a` | `origin/spike/multi-surface-canvas` only — **unmerged** |
| `CLAUDE-ARM-B-CANVAS-01` | `f0a12ce69b784921bdc712b237a63175d0ea3934` | `origin/spike/multi-surface-canvas` only — **unmerged** |
| Record landed on `main` | `dec5efbeac96dcf27be663c769bc927664641577` | `origin/main` |

**Governance record:**
`governance/specified-unbuilt/provenance-at-the-point-of-interaction.md`

### Corrections made against primary evidence while writing this log

1. **Record path.** The commissioning directive cited
   `governance/proposals/provenance-at-the-point-of-interaction.md`. **That path
   does not exist.** The record is in `governance/specified-unbuilt/`. The
   `proposals/` directory holds `surface-vs-substrate-interaction-grammar.md`,
   `dimensional-reconciliation-and-scale-regions.md` and
   `pdf-viewer-dom-decoupling-audit.md` — and the *grammar* proposal is
   correctly cited at `proposals/`, which is the likely source of the
   conflation.
2. **`dec5efb` is not a pure verbatim recovery.** The directive describes it as
   "recovering Arm B record". It recovered the 116-line record verbatim **and
   added one new subsection, C.1** (rebuild start state), producing 134 lines.
   Verified by object comparison: `f0a12ce`'s copy is 116 lines, `dec5efb`'s is
   134.
3. **Section count.** The directive names the template's sections as "all 14"
   but enumerates **fifteen**. The enumeration was treated as authoritative;
   `TEMPLATE.md` carries fifteen.
4. **No discussion draft exists in the working record.** The directive refers to
   "our discussion draft" of this specimen. No such draft appears in this
   session's history, so this log is built **entirely from primary artifacts**.
   Any prior draft held elsewhere should be diffed against this file rather than
   assumed consistent with it.

---

## 2. Initial Proposition

From `f0a12ce`'s own commit message, in the words used at the time:

> My synthesis claimed buried provenance — not chrome volume — was what stopped
> someone answering a real question.

The episode was explicitly framed as a test capable of proving that claim
**wrong**: *"This ran the experiment capable of proving that wrong, recorded the
result at the strength the evidence supports, and threw the apparatus away."*

---

## 3. Epistemic State

**Known before the trial.** Ground truth for the question was already
established from the metabolic bridge blind coordination audit: D-106 is tagged
on A-101 and absent from the A-601 door schedule, and `none` is a real value
elsewhere in that schedule — so absence ≠ non-rated. The provenance
*derivation* (`CaseWorkspaceStore.finding_provenance`) and card-level rendering
already existed and were tested.

**Unknown before the trial.** Whether *placement* of provenance changed what a
professional could actually do. This is precisely what the proposition asserted
and the trial measured.

**Assumed.** That step count to a verified answer is a meaningful proxy for
practical capability. This assumption was never itself tested — `unmeasured`.

---

## 4. Authority State

Standing Product Owner direction, 2026-08-28, quoted in the record:

> Ensure finding provenance is delivered at the top-level point of interaction
> (HUD / Finding Card) rather than buried 300 lines down in legacy accordion
> chrome.

Authority existed to run the experiment and to build throwaway apparatus.
Authority did **not** extend to implementing placement — the record's own status
line is *"placement not implemented."* The repository's standing discipline that
exploratory apparatus stays out of version control governed the deletion in §6.

---

## 5. Strongest Opposition

The strongest case against the initial proposition, at full strength:

**If buried provenance were the binding constraint, moving it to the first
screen should reduce the work required to answer the question. It did not.**
Both arms reached a correct verified answer in **3 views**, in the **identical
inspection order** (entry → A-601 → A-101). The proposition's own predicted
effect failed to appear.

A second opposition constrains the obvious remedy: the reading "51% of controls
are furniture, delete it" is blocked by a separate measured finding —
`static/js/pdf_viewer.js` resolves its document controls by `getElementById`
against `templates/base.html`'s menu bar, so a meaningful share of permanent
chrome is *the implementation of Look*, not accretion. Naive removal deletes
navigation rather than noise.

---

## 6. Exuvia Variation

**Built to be shed:** `routes/spike_arm_b.py` and
`templates/spike/arm_b_canvas.html` — the Arm B "calm canvas" control surface.
Both were **deleted before commit** under the repository's apparatus-stays-out
discipline. The blind-trial harness lived in the session scratchpad and was
never in the repository at all.

**Recoverability: none.** Verified against the tree at `f0a12ce` rather than
inferred from its message — no `templates/spike/` entry, no `spike_arm_b`
module, no canvas blueprint among `app.py`'s registrations.

**Cost to the registry, stated plainly:** the trial **cannot be re-run as
conducted**. Arm B no longer exists in any recoverable form, so every future
comparison against it depends on this record rather than on re-execution. That
is the price the deletion discipline charges, and it is the reason DM-0001
exists at all.

---

## 7. Trial / Experiment

| Design element | Value |
|---|---|
| Question | *"Is door D-106 rated?"* — one real question, known ground truth |
| Arms | A: full chrome, **repaired** provenance. B: calm canvas, **un-repaired** provenance |
| Subjects | Two fresh agents, one per arm |
| Given to each | An entry URL, the question, and a page-viewing command |
| Blinding | Not told which surface they had, that a second existed, or the answer |
| Constraint | Forbidden from reading the repository |
| Held constant | Same route-level authorization (`_load_workspace_or_404`) and same derivation (`CaseWorkspaceStore.finding_provenance`) |

Holding authorization and derivation constant is what makes the comparison
meaningful: a difference in outcome could not be an artifact of one arm
computing less or being differently permissioned. The arms differed **only in
presentation**.

**Measured results:**

| | Arm A | Arm B |
|---|---|---|
| Views to verified answer | **3** | **3** |
| Answer correct | yes | yes |
| Inspection order | entry → A-601 → A-101 | entry → A-601 → A-101 |
| Evidence links | from `AnalysisRun.source_ids` | parsed from statement text |
| Provenance position | line **337 of 388** (87% down) | first screen |

**What the instrument could not see — `unmeasured`:**

- Time on task. Only *views* were counted, never seconds.
- Subject identity, model, or version. Recorded only as "two fresh agents".
- Confidence, numerically. Arm B's subject "trusted those links completely" is a
  qualitative observation.
- Error rate. n = 1 per arm; both correct, which cannot distinguish a robust
  surface from a lucky one.
- Whether chrome reduction *alone* helps. Never isolated.
- Any second question, second domain, or repeat run.

---

## 8. Movement of Judgment

1. **Entering:** buried provenance is what stops a professional answering.
2. **First run invalidated.** A harness bug truncated Arm A's page and hid the
   provenance block. That subject took **6 views** rather than 3 and reported:
   *"Links from the finding to its evidence. The finding names A-101 and 'the
   door schedule.' Neither is a link."* Different subject, and the truncation
   removed other content too. Discarded as a result; retained as an observation.
3. **Valid run contradicted the proposition on its own predicted metric.** Equal
   step count, identical inspection order.
4. **Attention re-anchored** from *placement* to *grounding* — the arms differed
   in something the proposition had not been about, and that difference was
   epistemic rather than spatial.
5. **Leaving:** neither arm is the target state. Arm A got grounding right and
   placement wrong; Arm B got placement right and grounding wrong.

The proposer's own claim was the thing the evidence went against. That is the
most valuable property of this specimen.

---

## 9. Determination

**Measured.** Equal step count (3 v 3), identical inspection order, both correct.
Placement did not change what the subject could do on this question.

**Measured.** Chrome costs *attention*, not steps — an unprompted *"Attention is
full"* modal, a *"Not found"* image-search string with no image in play, and
four document names repeated **six times** on one page; *"roughly 20 lines of
signal inside 150+ lines of furniture."*

**Supported, not isolated.** Evidence links matter. Both subjects attributed the
ease to their presence. The condition that would isolate this — no links at all
— was never deliberately run.

**Single suggestive observation, not a result.** The invalidated 6-view run.

**The real finding.** The two link mechanisms are not equivalent. Arm A's links
are grounded in what the analysis actually **read**; Arm B's are parsed from
what the statement **says**, so Arm B would render a confident link to a
document the analysis never opened. Arm B was more reachable and epistemically
weaker.

> **A citation that can lie is worse than a UUID, because it carries more
> authority.**

---

## 10. Authority Transition

The trial produced **knowledge, not authorization**. The record was filed as
*Specified But Unbuilt*; placement remains unimplemented. No implementation
authority was created by the experiment.

What did transition: the apparatus was authorized to be destroyed and was
destroyed, and the finding was specified as the acceptance bar for any future
canvas — record-grounded links (`AnalysisRun.source_ids`), never links parsed
from statement text.

---

## 11. Consequence / Feedback

**Unintended, and the most instructive consequence.** The record lived only on
the unmerged `spike/multi-surface-canvas` branch, while
`governance/proposals/surface-vs-substrate-interaction-grammar.md:283` cited it
on `main` as *"Full record:"* — a **dangling citation to a file that did not
exist on `main`**, of exactly the class `d849501` ("PROVENANCE_BASIS_* was never
written: correct a false citation in the grammar") had been written to correct.
Closed by `dec5efb`, which landed the record and added §C.1.

**Downstream.** The `pdf_viewer.js` chrome finding became §5.3 of the grammar —
*the Look prerequisite, a hard sequencing constraint*: canvas-native Look must
exist **before** any chrome reduction, because reducing chrome first removes
navigation and leaves a drawing nobody can move.

---

## 12. Candidate Invariant

> **Reachability without grounding is a net epistemic loss.** A representation
> that makes a claim easier to act on, while weakening the basis on which the
> claim rests, leaves the reader worse off than an inconvenient but honest one —
> because reachability is itself read as authority.

**Status: candidate.** Raised by one trial, n = 1 per arm, one question, one
domain, one pair of subjects. Not established. Deliberately phrased so it could
be wrong: it predicts that a *more* reachable but statement-parsed citation
produces *more* misplaced confidence than a UUID, which is directly testable and
was not tested here.

---

## 13. Representation Effects

**Degrading.** Arm B's subject trusted parsed links completely. The links looked
identical in kind to Arm A's grounded ones while resting on a weaker mechanism —
presentation conferred authority the underlying derivation had not earned.

**Improving.** Arm A's subject saw `Machine finding · Unverified` and **refused
to accept the conclusion without opening the sources.** A representation that
correctly *lowered* trust and drove verification. This is the one mechanism the
record explicitly says should be preserved.

**Neutral on the measured metric.** Chrome volume changed reported experience
substantially and step count not at all.

---

## 14. Next Falsification

**The control this episode failed to run:** an arm with **no evidence links at
all**, otherwise identical. It was approximated once only by accident, through a
harness bug, with a different subject and other content also removed.

**Most efficient disproof of the candidate invariant:** a three-arm run —
grounded links, parsed links, no links — measuring not only step count but
**whether the subject detects a deliberately planted false citation** (a link to
a document the analysis never read). The invariant predicts the parsed-link arm
misses it most often. Step count alone cannot falsify it, which is the design
error worth not repeating.

**Secondary:** repeat with more than one question and more than one subject per
arm, and record time on task, since n = 1 and step-count-only are this
specimen's two structural weaknesses.

---

## 15. Executive Residue

**Both subjects independently asked for the same three things, none about chrome
or provenance:**

1. **No route from a found gap to an action.** `Export RFI` exists in the File
   menu; the investigation was titled "Door rating coordination"; the two halves
   never meet. *"The finding is a dead end: I can read it and confirm it, but I
   cannot do anything with it from where I am standing."*
2. **No completeness or scope signal.** *"On a real set with 400 doors I would
   need the surface to tell me '1 of N door tags unmatched'."*
3. **No reachable verification path.** *"I can see that no human has vouched for
   this, and I have no path to become that human."*

**Defects observed during the trial, recorded and not fixed:** the *"Attention
is full"* modal rendering with one Investigation (plus a stray space, `to pin
,`); the *"Not found"* image-search string with no image in play; `brief.md`
listed and linked as a document but rendering none; Display divisions 2–6 each
printing the full document list, putting 20 duplicate links between reader and
finding.

**Sequencing constraint carried forward:** grammar §5.3 — canvas-native Look
before any chrome reduction.

---

## Provenance

Verified 2026-08-28 against `origin/main` and the unmerged
`origin/spike/multi-surface-canvas`. Quoted subject statements and Product Owner
direction are taken verbatim from
`governance/specified-unbuilt/provenance-at-the-point-of-interaction.md` as
landed by `dec5efb`. Commit SHAs were read from git objects, not from
recollection. Line numbers cited from other documents are as at
`68ed4bba3ca11c82d10dd39f89944a8082e7b827` and will drift.
