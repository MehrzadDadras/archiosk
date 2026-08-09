# OPR-7.2 Evidence Boundary Audit (CLAUDE-POSTCAMEL-CONTINUE-01)

**Status: OPR-7.2 EVIDENCE BOUNDARY VERIFIED — PRODUCT OWNER REVIEW
REQUIRED.** A fresh-session, narrow commissioning-governance check,
explicitly instructed not to preserve COMM-I6's own "Satisfied"
conclusion for OPR-7.2 merely because it was already recorded.
Independently re-audits the underlying evidence and corrects the
conclusion to **Partially Satisfied**. No code was changed. No
`RequirementAdjudication` was created.

---

## A. Verified starting repository state

Confirmed directly, not assumed from the prior session's own report:

- `git status`: clean except the pre-existing untracked
  `tests/fixtures/nreocrc/_lab_instance_scratch_002/` fixture.
- `git rev-parse HEAD` and `git rev-parse origin/main`: both
  `08b6c3ae9c6eb261b0b316a036e6151a87c19db8` — `HEAD == origin/main`,
  matching the prior session's report exactly.
- `git log --oneline -5` confirms the reported commit sequence
  (COMM-I6, the OPR-5.3 confirmation addendum, COMM-I5A, COMM-I5,
  COMM-I4A) really exists in history, not merely claimed.

## B. Exact adopted OPR-7.2 text

Read directly from the real adopted document on disk
(`instance/registry/workspace_sources/0b743d80-13b0-4253-b411-9fa17ff11927/…GEMINI-ARCHIOSK-RFP-02B_Rev0.2A_Product-Owner-Adoption-Copy.txt`),
not recalled from memory:

- **Section B (Core Document):** *"OPR-7.2 (Zero-Founder Testing):
  Representative users shall be able to execute core workflows without
  creator intervention."*
- **Section C (Full Requirement Schedule):** requirement statement
  "Representative users shall execute core workflows without creator
  intervention," Priority Critical, Classification Current Baseline,
  **Verification Method: "User Testing."**
- **Section H (Verification Matrix):** OPR-7.2 is listed under the
  **"Test (T)"** category — the matrix has exactly four categories
  (Inspection/Demonstration/Test/Commissioning-PO-Sign-off); "User
  Testing" is not one of them.

**A genuine internal inconsistency in the adopted document itself,
found during this audit, not previously flagged:** Section C names
OPR-7.2's own specific verification method as "User Testing," a term
distinct from ordinary "Test" everywhere else in the same schedule
(e.g. OPR-2.1, OPR-4.1 also say "Test"). Section H's own master matrix
then folds OPR-7.2 into the generic "Test (T)" bucket alongside
Sources/Requirements/AI-reasoning Requirements that are legitimately
satisfied by ordinary automated/functional testing — silently
collapsing "User Testing" into "Test" rather than giving it its own
category. This is the Owner's own document disagreeing with itself
about what OPR-7.2 actually requires, not something this session can
resolve unilaterally. Recorded under Future-Prompt Watch below.

## C. All evidence previously used to claim OPR-7.2 Satisfied

Re-read directly from the real, committed governance files, not from
memory of the prior session's own summary:

1. **`governance/current/pilot-readiness-postcamel-p01.md`** (Section
   1, "Method"): *"A repository-grounded audit... was performed first,
   from the stated posture of 'I have been given this application.
   What do I do?' — followed by three live-browser Zero-Founder
   walkthroughs against a freshly restarted dev server, using a
   throwaway `pilot_audit` admin account and two throwaway projects."*
2. **`governance/current/comm-i1-commissioning-specimen-setup.md`**
   (Part L, "Zero-Founder walkthrough"): *"Performed live, via the
   ordinary product, logged in as the real `archiosk_commissioning`
   operator account."*
3. **`governance/current/comm-a1-self-project-commissioning-readiness.md`**
   (Section N, "Zero-Founder Commissioning Plan") — a plan/test-design
   document, not itself a record of an outside party executing it.
4. Automated regression tests (2989 passing) — none of these are
   browser-driven or user-facing in the sense OPR-7.2 means; they
   verify code behavior, not human usability.

**In every one of the three live-walkthrough records above, the actor
performing the walkthrough is explicitly named as this session's own
Builder** — Claude Code, operating a throwaway or operator account it
itself created, adopting a deliberately naive posture ("I have been
given this application") as a role-play framing, not as evidence of an
actually-independent party. No file in this repository's governance
corpus records a walkthrough performed by anyone other than the
Builder. No evidence was found of the real Product Owner personally
operating the application UI at any point in this repository's history
— every Product Owner interaction on record is textual (chat prompts,
review, and decision), never a recorded browser session.

## D. Classification of that evidence by test type

| Tier | Evidence found | Verdict |
|---|---|---|
| 1. Automated test | 2989 passing tests | Real, extensive |
| 2. Builder-operated browser walkthrough | POSTCAMEL-P01 (3 scenarios), COMM-A1, COMM-I1 | Real, extensive |
| 3. Builder simulating an unfamiliar user | POSTCAMEL-P01's own explicit "I have been given this application. What do I do?" posture | Real, but self-adopted by the same party who built the system |
| 4. Product Owner walkthrough | **None found** | No record of the Product Owner personally operating the UI exists anywhere in this repository |
| 5. Genuine representative-user Zero-Founder test | **None found** | No record of any party independent of the Builder ever operating the application exists |
| 6. Independent commissioning | Not yet performed | Explicitly reserved for a future, separately-authorized stage (COMM-I6's own Section 13 boundary), correctly not attempted |

## E. Whether a genuine representative user has been demonstrated

**No.** Tiers 4 and 5 have zero evidence. Every recorded "Zero-Founder"
walkthrough was performed by the same party that built the system,
using an account that party itself created, in the same session/
authority context as its own development work. This does not meet the
adopted Requirement's own literal bar — "**without creator
intervention**" — because the creator (the Builder) is the one who
performed every recorded walkthrough. A careful, well-designed
simulation of naivety by the creator is not the absence of the
creator.

## F. Corrected/reconfirmed OPR-7.2 assessment

**B. Partially Satisfied.** COMM-I6's own "Satisfied, with an honest
methodological caveat" is corrected. The caveat itself — precisely
because it says the required party (a representative user independent
of the creator) has never actually operated the system — describes an
unmet element of the Requirement's own text, not a minor footnote to
an otherwise-earned Satisfied outcome. Useful, real Zero-Founder/
browser evidence exists (tiers 1–3) and should not be discarded — it
demonstrates the *workflow itself* is completable without hidden,
undocumented founder-only knowledge, a real and valuable finding — but
it does not demonstrate what OPR-7.2 actually requires: a
representative user, independent of the creator, completing a core
workflow unaided.

## G. Developmental classification

**Timely Correction, preserved from COMM-I6, with one adjustment:**
the correction sequence itself continues past COMM-I6 — POSTCAMEL-P01
found and fixed three real defects via its own walkthroughs (the
original Timely Correction basis), but COMM-I6's own subsequent
assessment of what that evidence actually proves against OPR-7.2's
literal text was, on this audit, itself found to need correction. This
audit is the second, narrower correction layered on the same
Requirement — not a new deficiency in the product, but a deficiency in
how far the evidence had previously been read to reach.

## H. Smallest remaining action if incomplete

A single, genuinely independent party — someone who did not build
ARCHIOSK and is not the Builder operating a role-play posture —
completes at least one representative core workflow (e.g., create a
project, ingest a document, register and adjudicate a Requirement,
produce and export a Work Product) unaided, with the session observed
or recorded. This does **not** require the full Independent
Commissioning Authority arrangement (Section 13's own future,
heavier-weight stage) — a single genuine human walkthrough, even
informal, would close this specific gap. The Product Owner personally
operating the application once would itself satisfy tier 4 evidence,
though tier 5 (a party independent of both Builder and Owner) would be
the fullest reading of "representative user."

## I. Consequence for OPR-7.3 / Substantial Completion consideration

**OPR-7.3 consideration should be held pending OPR-7.2 validation, or
the Product Owner may choose to treat this gap as an Accepted Residual
— that choice belongs to the Product Owner alone, not this audit.**
OPR-7.3's own adopted text requires "all current baseline requirements"
satisfied "notwithstanding minor accepted residuals" (Rev 0.2A's own
wording) — with OPR-7.2 now Partially Satisfied rather than Satisfied,
the baseline is not, at this moment, fully Satisfied across all 34
Requirements without either (a) closing the OPR-7.2 gap per Section H
above, or (b) the Product Owner explicitly accepting it as a residual,
the same real mechanism already exercised for OPR-7.4. This audit does
not make that choice; it only reports that the choice now exists where
COMM-I6 had reported none.

## J. Whether the other seven COMM-I6 assessments remain unaffected

**Unaffected.** OPR-6.1, 6.2, 6.3, 7.1, 7.4, and 7.5 concern distinct
capabilities (AI/human distinction, cross-document intelligence,
export, integration testing, deficiency close-out, residual
acceptance) with their own independent evidence, none of which this
audit's findings touch. OPR-7.1 in particular already correctly
distinguished regression testing from developmental commissioning from
independent final commissioning in COMM-I6's own text — that
distinction stands and is reinforced, not undermined, by this audit.

## Future-Prompt Watch (continued from COMM-I6)

| Item | Classification | Trigger | Why it matters | Pull-forward condition |
|---|---|---|---|---|
| Adopted OPR's own Section C/Section H inconsistency for OPR-7.2's verification method ("User Testing" vs. folded into generic "Test") | **BACK-BURNER ITEM — RESURFACE FOR OWNER REVIEW** | Direct reading of the adopted document during this audit | The Owner's own document disagrees with itself about what OPR-7.2 requires; resolving it is the Owner's prerogative over their own document, not this session's to silently normalize | Before any future revision or reconciliation pass over the adopted OPR itself |
| Zero genuine representative-user (tier 4/5) evidence anywhere in this repository's history | **EXISTING FUTURE PROGRAMME — RELEVANT EVIDENCE FOUND** (directly feeds the already-named Independent Commissioning Authority arrangement) | This audit's own evidence review | Confirms, with a fresh and rigorous pass, exactly the gap that future stage exists to close — strengthens rather than changes COMM-I6's own Section V | Explicit, separate Product Owner authorization to arrange either a genuine human walkthrough or the full independent-commissioning stage |

No item above was implemented. No Future Programme or OPR text was
created or modified.

## Tests and live verification

None performed this stage — this was a documentation/evidence audit
only, re-reading already-committed governance files and the adopted
OPR document directly. No application code was touched, so no
regression run was warranted or performed.

## K. Commits / HEAD / origin/main / working tree

See the final chat report for exact values, recorded after this
document and the COMM-I6 correction notice are committed together.

## L. Recommendation to the Product Owner

Two independent choices, not one: (1) whether to close the OPR-7.2 gap
via a genuine representative-user walkthrough (Section H's own smallest
action) before considering Substantial Completion, or accept it as a
residual the same way OPR-7.4's own gap was accepted; and (2), separate
from either choice, whether and when to authorize the future Independent
Commissioning Authority stage this repository's own governance corpus
has been explicitly preserving space for since COMM-I6. Neither
decision was made by this audit.
