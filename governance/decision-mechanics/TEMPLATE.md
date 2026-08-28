# Decision Mechanics — Specimen Log Template

`governance/decision-mechanics/` is an **empirical laboratory registry** for
testing candidate invariants of collaborative judgment. A specimen is one
recorded episode of a decision actually being made: what was proposed, what
opposed it, what was tried, how judgment moved, and what survived contact with
evidence.

This is a **laboratory**, not a doctrine. A specimen records what an episode
measured. A candidate invariant is a *hypothesis raised by* a specimen, never a
rule established by one. Nothing here amends
`governance/constitutional-invariants.md`, and nothing here authorizes
implementation — those have their own processes
(`governance/governance-of-governance/amendment-and-ratification.md`,
`governance/STATUS.md`).

---

## Standing rule — unmeasured is not unknown-shaped

**Anything the episode did not actually measure must be marked `unknown` or
`unmeasured`. It must never be reconstructed, inferred, or smoothed to make the
log look complete.** A specimen with eight honest `unmeasured` fields is worth
more than one that reads as a finished study, because the next experiment is
designed from the gaps.

**Primary evidence in the repository always overrides recollection.** Commit
SHAs, file paths, mechanism names and quoted text are verified against the
actual tree or git object before being written down. Where a recollection and
the repository disagree, the repository wins and the correction is recorded in
§1 rather than silently applied.

Retrospective specimens — written after the fact, from artifacts rather than
from live instrumentation — must say so in §1 and are held to this rule most
strictly, because recollection is exactly what is most available and least
reliable.

---

## The fifteen sections

Every specimen carries all fifteen. A section with nothing in it says
`unmeasured` and, where useful, why.

### 1. Specimen Identity
Identifier (`DM-NNNN`), title, date of the episode, and date of the log if
different. Primary artifacts with **full commit SHAs** and their reachability
(which ref contains them; whether the ref is merged). Whether the log is
contemporaneous or retrospective. Any correction made against primary evidence
while writing, stated explicitly.

### 2. Initial Proposition
The claim as it actually entered the episode, in the words used at the time
where those are recoverable. Not the cleaned-up version, and not the conclusion.

### 3. Epistemic State
What was known, unknown, and assumed before the episode. Includes whether ground
truth existed and how it was established. Distinguish "known" from "believed."

### 4. Authority State
Who held decision authority, what was already authorized, what was not, and
which constraints bound the episode. Quote standing direction where it exists.

### 5. Strongest Opposition
The strongest available case *against* the initial proposition — stated at full
strength, not as a straw man. If no genuine opposition was raised at the time,
say so; that itself is a finding about the episode.

### 6. Exuvia Variation
The variant built in order to be **shed** — apparatus constructed to produce a
measurement and then deliberately discarded. Record what was built, what was
deleted, whether it is recoverable, and what that costs the repeatability of the
trial. Named for the shed exoskeleton: the measurement is the organism, the
apparatus is the cast skin.

### 7. Trial / Experiment
Design, arms, subjects, controls, and what was held constant so a difference in
outcome could not be an artifact of something else. State the measurement
instrument and what it could not see.

### 8. Movement of Judgment
How belief actually moved during the episode, in order. This is the section the
registry exists for. Record reversals, invalidated runs, and moments where the
evidence went against the proposer. An episode where judgment did not move is a
valid specimen and should say so.

### 9. Determination
What was concluded, **stated at the strength the evidence supports** and no
further. Separate "measured", "supported but not isolated", and "suggestive
single observation".

### 10. Authority Transition
What changed in authority as a result: what became authorized, specified,
deferred, or blocked. If the episode produced knowledge but no authority change,
say that plainly.

### 11. Consequence / Feedback
What actually happened downstream — including consequences the episode did not
intend, such as records stranded on unmerged branches, citations left dangling,
or work later built on the result.

### 12. Candidate Invariant
The generalizable rule this specimen *proposes*, phrased so it could be wrong,
with its current evidential status and sample size. Never asserted as
established.

### 13. Representation Effects
How presentation — placement, wording, badges, chrome, ordering — changed
judgment independently of the underlying facts. Both directions: representation
that improved calibration and representation that degraded it.

### 14. Next Falsification
The specific experiment that would most efficiently disprove the candidate
invariant, and the control the episode failed to run. Concrete enough to
execute.

### 15. Executive Residue
What is left on a decision-maker's desk: open asks, observed defects, sequencing
constraints, and anything the episode surfaced but deliberately did not resolve.

---

## Conventions

- Files: `specimens/DM-NNNN-short-slug.md`, numbered in order of logging.
- Cite commits by full SHA on first mention, short form after.
- Quote subjects and standing direction verbatim; never paraphrase into a
  stronger claim than was made.
- Mark every unmeasured field. Do not delete the section.
