# Specified But Unbuilt — Provenance at the Point of Interaction

**Status:** Investigated with an empirical trial (`CLAUDE-ARM-A-PROVENANCE-01`
delivered the mechanism; `CLAUDE-ARM-B-CANVAS-01` was the throwaway control arm,
built and deleted in the same session), **placement not implemented**. The
provenance *derivation* and *card-level rendering* are real, tested and on
`main`-track code. What is unbuilt is its **position in the page**.

Product Owner direction, 2026-08-28: *"Ensure finding provenance is delivered at
the top-level point of interaction (HUD / Finding Card) rather than buried 300
lines down in legacy accordion chrome."*

## A. What was measured, and how

A two-arm blind trial on one real question — **"Is door D-106 rated?"** — taken
from the metabolic bridge blind coordination audit, where ground truth was
already known (D-106 is tagged on A-101 and absent from the A-601 door schedule;
`none` is a real value elsewhere in that schedule, so absence ≠ non-rated).

Two fresh agents, each given only an entry URL, the question, and a page-viewing
command. Neither was told which surface it had, that a second surface existed,
what the answer was, and both were forbidden from reading the repository. Both
arms ran through the **same route-level authorization** (`_load_workspace_or_404`)
and the **same derivation** (`CaseWorkspaceStore.finding_provenance`), differing
only in presentation — so a difference in outcome could not be an artifact of one
arm computing less or being differently permissioned.

| | Arm A — full chrome, repaired provenance | Arm B — calm canvas, un-repaired provenance |
|---|---|---|
| Views to verified answer | **3** | **3** |
| Answer correct | yes | yes |
| Inspection order | entry → A-601 → A-101 | entry → A-601 → A-101 |
| Evidence links present | yes, from `AnalysisRun.source_ids` | yes, parsed from the statement text |
| Provenance position | line **337 of 388** (87% down) | first screen |

## B. The result, stated at the strength the evidence supports

**Equal step count, identical inspection order.** Both subjects attributed the
ease to the presence of evidence links, and both reached the answer at step 3.

- **Evidence links matter — supported, not confirmed.** The condition that would
  isolate this (no evidence links at all) was never run deliberately. It was
  approximated once by accident: an invalidated first trial in which a harness
  bug truncated Arm A's page and hid the provenance block. That subject took
  **6 views** rather than 3 and reported *"Links from the finding to its
  evidence. The finding names A-101 and 'the door schedule.' Neither is a
  link."* Different subject, and the truncation removed other content too, so
  this is a **single suggestive observation, not a measured result**.
- **Chrome costs attention, not steps.** It did not change the step count. It
  showed up as an unprompted *"Attention is full"* modal, a *"Not found"*
  image-search string with no image in play, and the four document names
  repeated **six times** on one page — *"roughly 20 lines of signal inside 150+
  lines of furniture."*
- **The two mechanisms are not equivalent, and this is the real finding.**
  Arm A's links are grounded in what the analysis actually **read**. Arm B's are
  parsed from what the statement **says**, so they would render a confident link
  to a document the analysis never opened. Arm B was more reachable and
  epistemically weaker; its subject trusted those links completely. **A citation
  that can lie is worse than a UUID, because it carries more authority.**

**Arm A got grounding right and placement wrong. Arm B got placement right and
grounding wrong.** Neither is the target state.

## C. What is therefore specified

Deliver the **record-grounded** provenance (`finding_provenance`, already built
and tested) at the **point of interaction**, rather than at the bottom of the
workspace page behind inactive chrome. The card-level rendering does not need
redesigning — a blind subject called it *"the best part of the surface … the
single thing that made this fast, and it deserves to be kept."* What needs
changing is that it currently sits after ~5,500 characters of menus, dialogs and
empty panels.

This is deliberately **not** specified as "strip the chrome." A separate measured
finding blocks that reading: `static/js/pdf_viewer.js` resolves every document
control — `doc-page-input`, `doc-zoom-*`, `doc-fit-*`, `doc-rotate`,
`doc-search-*`, `doc-download`, `doc-print`, `doc-snapshot` — by
`getElementById` against `templates/base.html`'s menu bar. In a chrome-less
render they are all `null`. **A meaningful share of the permanent chrome is the
implementation of Look**, not accretion, and naive removal deletes navigation
rather than noise. Any placement work must supply canvas-native Look first or
carry the menu bar with it.

## D. Named, not designed here

Both blind subjects independently asked for the same three things, and none of
them are about chrome or provenance:

1. **No route from a found gap to an action.** A door tagged on plan and missing
   from the schedule is a textbook RFI. `Export RFI` exists in the File menu and
   the investigation was literally titled "Door rating coordination" — the two
   halves never meet. *"The finding is a dead end: I can read it and confirm it,
   but I cannot do anything with it from where I am standing."*
2. **No completeness or scope signal.** Neither subject could tell whether D-106
   was the only gap, or whether four sheets were the whole set. *"On a real set
   with 400 doors I would need the surface to tell me '1 of N door tags
   unmatched'."*
3. **No reachable verification path.** *"I can see that no human has vouched for
   this, and I have no path to become that human."*

One mechanism worked exactly as intended and should be preserved: Arm A's
subject saw `Machine finding · Unverified` and **refused to accept the
conclusion without opening the sources**. The honesty badge drove verification.

## E. Defects observed during the trial, not fixed here

- *"Attention is full — Up to four Investigations can be held in Attention at
  once…"* renders when the project holds **one** Investigation, unprompted, and
  reads as a blocking obstacle. (Also carries a stray space: `to pin ,`.)
- *"Not found - ARCHIOSK doesn't yet compare this image against the document
  set."* renders with no image in play; read top-to-bottom, "Not found" is
  alarming before its owning widget is identified.
- `brief.md` is listed and linked as a document in both the File menu and the
  sidebar but renders no document — it is the project conversation view.
- Display divisions 2–6 each print the full document list, putting 20 duplicate
  document links between a reader and the finding.
