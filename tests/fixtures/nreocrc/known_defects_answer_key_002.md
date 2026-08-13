# Known Defects Answer Key — NREOCRC Corpus State 002 (Addenda Extension)

**DO NOT INGEST THIS FILE.** This is the tester's own answer key for grading
`CLAUDE-GO-COMPETE-01`'s competitive kill-test (Section 17) against the
`addenda_corpus_state_002/` extension. It exists so the proving loop can be
judged against a known-correct answer rather than graded by eye, and so a
"the model happened to say something plausible" pass is distinguishable from
"the model actually found the real issue." Never register this file as a
Source in a test project. Mirrors the discipline `ingest_nreocrc_lab_002.py`'s
own docstring already established for Snapshot 001's hidden answers (the
arithmetic discrepancy, Row 20, the 4.5 citation) — this file is the
Corpus-State-002 continuation of that same practice, not a new one.

---

## Carried forward from Corpus State 001 (unchanged, documented elsewhere)

- **Program Net Area Subtotal arithmetic discrepancy** — `NREOCRC-OPR-001`
  states "4,105 m²" (Section, Appendix OPR-1 footer) but the seven
  Department Area Subtotal cells actually sum to **3,980 m²**
  (570+850+1,120+175+545+460+260). Already documented in
  `devils_advocate_review_001.md` §7/§8 and `ingest_nreocrc_lab_002.py`'s
  own docstring. A correct GO answer to "is the evidence sufficient/is
  there a discrepancy in the Functional Program area totals" should surface
  this, or at minimum not affirm the stated 4,105 m² as internally
  consistent without qualification.
- **Row 20 (Situational Awareness / Media Briefing Room)** — the one row in
  Appendix OPR-1 with a split security classification ("Secure/Controlled
  interface"), flagged by the document's own Note (b). A correct GO answer
  about zoning/security-classification questions touching this room should
  reflect the dual-boundary condition, not collapse it into a single zone.

## New in Corpus State 002 (this extension)

### Defect 1 — Section 12.1 / 12.2 reconciliation gap (the central planted issue)

- `NREOCRC-ADD-02` amends OPR-001 Section 12.1: standby power duration
  **96 hours → 120 hours**.
- `NREOCRC-ADD-02` explicitly does **not** amend Section 12.2 (the Sizing
  Reference table, still showing the 72-hour Bylaw-minimum fuel storage
  basis and 24-hour refuelling assumption).
- `NREOCRC-ADD-03` (Owner's response to a Proponent question asking exactly
  this) confirms Section 12.1 governs, characterizes 12.2 as a
  non-mandatory planning reference, and explicitly declines to issue a
  revised numeric fuel-storage basis.
- **Correct answer**: there is no single stated fuel-storage-hours number
  that satisfies the current Mandatory requirement — the Design-Builder
  must independently size fuel storage to meet the 120-hour generation
  duration; the 72-hour figure in 12.2 is stale/informational only, not a
  safe design target. A correct GO answer to "does the fuel storage sizing
  basis reconcile with the 120-hour requirement?" should say **no
  reconciliation is stated / the 72-hour reference is now insufficient on
  its face**, not treat 12.2's 72 hours as still authoritative.
- **This IS the strategic-RFI-worthy condition** (Section 5/17 of
  CLAUDE-GO-COMPETE-01's own prompt): a well-formed RFI here should ask the
  Owner to confirm whether the Design-Builder may rely on its own
  independently-derived fuel storage sizing to meet the 120-hour
  requirement without risk of a Proposal-stage compliance finding against
  the (now stale) 72-hour reference figure — protecting the Proponent's
  position without rewriting the RFP.

### Defect 2 — NREOCRC-DBR-001's own staleness

- `NREOCRC-DBR-001` (the pursuit team's own draft Basis of Design) is
  **dated January 28, 2027** — before `NREOCRC-ADD-02` (February 3, 2027).
- It sizes fuel storage to **72 hours at 1,050 kW**, i.e. the PRE-Addendum
  basis, and is silent on the 120-hour requirement.
- It is not a "planted trap" — its own Section 5 already flags "Reconcile
  this Basis of Design against any RFP Addenda issued after the date of
  this draft" as an open item. It is a realistic stale internal draft, the
  kind that genuinely exists mid-pursuit.
- **Correct adjudication outcome**: `NOT_SATISFIED` or `PARTIALLY_SATISFIED`
  (`REQUIREMENT_ADJUDICATION_NOT_SATISFIED` /
  `REQUIREMENT_ADJUDICATION_PARTIALLY_SATISFIED` in
  `services/case_workspace.py`'s own closed vocabulary) against Section
  12.1 as amended — 72 hours does not satisfy a 120-hour Mandatory
  requirement. A GO answer that reports this evidence as satisfying the
  current requirement without qualification is a real failure, not a
  matter of interpretation.

### Defect 3 (minor, low-stakes control) — NREOCRC-ADD-01 is a decoy

- `NREOCRC-ADD-01` is intentionally uneventful (closes out two TBD
  citations, touches nothing in Section 12). It exists so "what changed
  between Addendum 1 and Addendum 2" and "what changed between Addendum 2
  and Addendum 3" produce genuinely different, distinguishable answers —
  a system that gives the same generic answer regardless of which pair of
  addenda is asked about has failed the addendum-intelligence test
  (CLAUDE-GO-COMPETE-01 Section 12), independent of Defect 1 above.
