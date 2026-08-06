# Specified But Unbuilt — the Camel Multimodal Programme (MM1–MM9)

**Status:** Specified, not implemented. Zero code exists for anything in
this document. Recorded here under `CLAUDE-P40-VW9A` to close a real
continuity gap: this programme (codename "Camel") was maintained
outside this repository and could not be found during the CLAUDE-P40-VW9
final report (`grep -rli "MM1\|MM2\|...\|MM9"` and `"cockpit"` both
returned zero matches across the whole repository at that time). This
document is the durable record going forward — the product owner's
original stage intent, preserved verbatim in substance, with stage
boundaries lightly refined where existing repository evidence (`Source`,
`Finding`, `Requirement`, `Relationship`, `AnalysisRun`/`AnalysisTrigger`,
`GovernanceLog` — see `current/kernel-object-model.md`) makes a boundary
concrete rather than speculative. These are **programme stages, not nine
isolated technical modules** — dependencies and cross-cutting
requirements are called out explicitly below rather than forcing
capabilities into artificial per-stage silos.

**Relationship to the rest of this governance corpus:** BEEHIVE's
existing kernel (`Source`, `Requirement`, `Finding`, `Relationship`,
`Case`, evidence/provenance/confidence machinery — see
`current/kernel-object-model.md`) already carries the general shape
every MM stage below needs (governed representation, provenance,
confidence, human validation, no silent AI-to-authoritative promotion).
No MM stage below proposes a second, parallel truth model — each is
additional **content types and interaction surfaces** that must compose
with the existing kernel, not replace or duplicate it. Where a stage
below implies something that sounds like a new kernel primitive, treat
that as a flag for future design review against `constitutional-
invariants.md`, not as pre-authorized.

**Authorization status:** every stage below is **NOT AUTHORIZED** for
implementation — this document records intent and sequencing, it is not
a build order — **except MM1, MM2, MM3, MM4, MM5, MM6, and MM7, now IMPLEMENTED**
(`CLAUDE-MM1`, 2026-08-05, authorized following the accepted cockpit gate
`CLAUDE-CGP-02`; `CLAUDE-MM2`, 2026-08-05, authorized following the
accepted MM1 seal; `CLAUDE-MM3`, 2026-08-05, authorized following the
accepted MM2 seal; `CLAUDE-MM4`, 2026-08-06, authorized following the
accepted MM3 seal; `CLAUDE-MM5`, 2026-08-06, authorized following the
accepted MM4 seal; `CLAUDE-MM6`, 2026-08-06, authorized following the
accepted MM5 seal; `CLAUDE-MM7`, 2026-08-06, authorized following the
accepted MM6 seal; see `STATUS.md`'s own authorization table and
`current/kernel-object-model.md` for the real, tested, ground-truth
detail — this document's own MM1/MM2/MM3/MM4/MM5/MM6/MM7 sections below
are retained as the original stage descriptions, not updated to
duplicate that record).
MM8–MM9 remain exactly as originally recorded: this programme's "specified
but unbuilt" pointer in `STATUS.md` continues to cover them as a single
pointer, not stage-by-stage rows, until each is individually taken up.

---

## MM1 — Multimodal foundation and evidence contract

**IMPLEMENTED** — see `current/kernel-object-model.md`'s
`StructuralUnit`/`AddressableRegion`/`EvidenceItem`/`DerivedObservation`
entry for what actually exists in code today. The description below is
preserved as the original stage intent this implementation was built
from, not rewritten to narrate what was built.

The shared governed representation every later stage builds on:
documents, pages, sheets, drawings, images, tables, regions, cells,
extracted content, direct evidence, derived observations, provenance,
confidence, and human validation, all as one coherent vocabulary rather
than per-modality one-offs invented independently in MM2–MM5. This is
the stage where the **fact vs. measurement vs. expert judgment vs. user
assumption vs. AI suggestion** distinction (load-bearing throughout MM7
and MM3's own Design-Manager case, Part E below) must be established as
a shared, governed vocabulary once — not re-invented per modality.

Grounds in what already exists rather than starting blank: `Source`
already carries `origin_type`/`origin_reference`/provenance fields;
`Finding` already distinguishes claim status and carries
`AnalysisTrigger` (machine vs. human-initiated); `Relationship` already
carries a `confirmed_by`/provisional distinction. MM1's real work is
extending this vocabulary to **sub-document regions** (a page, a sheet
range, a drawing detail, an image region) as first-class, addressable,
citable things — today's kernel addresses whole `Source` records, not
regions within them.

**Depends on nothing below.** Every other MM stage depends on MM1.

## MM2 — PDF and document intelligence

**IMPLEMENTED, bounded** — see `current/kernel-object-model.md`'s "PDF
page structure and citation" entry for what actually exists in code
today: text-native/image-only/mixed classification, page-level
`StructuralUnit`s, paragraph-level `AddressableRegion`/`EvidenceItem`s,
a strengthened citation resolver, and `services/pdf_intelligence.py`.
Scanned/image-only PDFs are classified honestly (OCR and PDF-to-image
rendering remain unavailable in this environment, per `services/
drawing_intake.py`'s own prior audit, re-confirmed not re-investigated)
- never rendered or OCR'd. Annotations, table extraction beyond the
existing Batch J `Table`/`TableRow` path, and full redline/version
comparison were not built this stage. The description below is
preserved as the original stage intent this implementation was built
from, not rewritten to narrate what was built.

Text-native and scanned PDFs; page navigation; extraction; selectable
regions; tables; document structure; citations; annotations; links from
findings back to exact source locations (page, region, coordinates) —
the first real consumer of MM1's region-addressing vocabulary. The
existing PDF viewer (`static/js/pdf_viewer.js`) and `BHiveParser`
(`services/bhive_parser.py`) are the concrete, already-real anchors this
stage would extend, not replace.

**Depends on MM1.**

## MM3 — Spreadsheet and structured-data intelligence

**IMPLEMENTED, bounded** — see `current/kernel-object-model.md`'s
"Worksheet/row structure and bounded editing" entry for what actually
exists in code today: worksheet/row `StructuralUnit`/`AddressableRegion`/
`EvidenceItem`s, workbook classification (including content-based macro
detection and decompression-bomb bounds), formula preservation with an
honest cached-value distinction, and one bounded single-cell edit with a
real, live-verified export/reopen round trip. Monte Carlo, a spreadsheet
grid UI, full Excel recalculation, and a permanent risk-record schema
were deliberately not built - see that entry's own deferral list. The
description below is preserved as the original stage intent this
implementation was built from, not rewritten to narrate what was built.

Open, inspect, create, and edit spreadsheets and structured tables;
sheets, tables, cells, formulas, named ranges, charts, types,
dependencies, and unsupported features; preserve ordinary Excel
interoperability (round-trip fidelity, not a lossy one-way import).

**Includes the Design Manager's role as an expert integrator and the
Progressive Design-Build risk-register/Monte Carlo case — see Part E
below**, recorded as its own cross-cutting section rather than folded
silently into this stage's own prose, since it is explicitly a
requirement that **spans** MM3 (native structured data + Excel
linkage), MM6 (cross-document linkage to requirements/drawings/
schedule/estimates), and MM7 (governed analysis, fact-vs-judgment-vs-
AI-suggestion discipline) simultaneously — mapped precisely at the end
of this document.

**Depends on MM1.**

## MM4 — Drawing intelligence

**IMPLEMENTED, bounded** — see `current/kernel-object-model.md`'s
"Drawing sheets, reversible orientation, and evidence sachets" entry and
`STATUS.md`'s own authorization-table row for the real, tested,
ground-truth detail (`CLAUDE-MM4`, 2026-08-06). The prose immediately
below is retained as the ORIGINAL stage intent this implementation was
authorized against, not rewritten to match what was actually built —
drawing-sheet structure, reversible mirror/rotate view transforms,
on-demand rectangular regions, real independent-Display comparison, and
the Governed Evidence Sachet are real; native CAD/BIM parsing, automatic
symbol/dimension recognition, authoritative takeoff, and full overlay/
clash-detection registration remain unbuilt, exactly as this section's
own prose already anticipated below.

Plans, elevations, sections, details, scales, dimensions, symbols,
callouts, drawing relationships, revisions, visual regions, and
governed human-supervised drawing investigation. The most demanding
consumer of MM1's region-addressing model (a callout referencing a
detail on a different sheet is a `Relationship` between two MM1
regions, not a new mechanism).

**Depends on MM1; benefits from MM2's document-structure work
(sheet sets are frequently PDF-packaged) but does not strictly require
it.**

## MM5 — Image, screenshot, and camera evidence

**IMPLEMENTED, bounded** — see `current/kernel-object-model.md`'s
"Eye becomes a real governed visual-evidence surface" entry and
`STATUS.md`'s own authorization-table row for the real, tested,
ground-truth detail (`CLAUDE-MM5`, 2026-08-06). The prose immediately
below is retained as the ORIGINAL stage intent this implementation was
authorized against, not rewritten to match what was actually built — a
real paste/drop/upload-to-project Eye pane, reversible orientation,
region/marker evidence, a stable citation contract, and EXIF-free
derivative crop export are real; a full photo editor, automatic object/
defect/facial recognition, and OCR over arbitrary images remain unbuilt,
exactly as this section's own prose already anticipated below.

Uploaded images, screenshots, pasted images, and phone-camera evidence
with preview, orientation, metadata, annotation, region selection,
evidence capture, and project linkage. The existing Eye pane (`static/
js/case_workspace.js`'s paste/drop-to-preview surface, currently
explicitly "not saved anywhere — cleared when you navigate away or
reload; editing, annotation, and evidence capture are not part of this
stage" per its own rendered copy) is the direct, already-real precursor
this stage would graduate into governed, persisted evidence.

**Depends on MM1.**

## MM6 — Cross-document and cross-modal relationships — IMPLEMENTED, bounded (`CLAUDE-MM6`, 2026-08-06; see `STATUS.md`'s authorization table and `current/kernel-object-model.md`'s matching entry for the real, tested, ground-truth detail — the stage-intent prose immediately below is retained unchanged as the original description, not rewritten to duplicate that record)

Connects requirements, specifications, drawings, spreadsheets,
schedules, estimates, images, investigations, RFIs, decisions, changes,
tasks, and evidence — reusing the existing `Relationship` primitive
(already open-world, already used for `derived_from`/adoption lineage
per `investigation-lifecycle-extensions.md`) rather than inventing a
second linkage mechanism. The explicit discipline carried over from
existing `Relationship` usage: linking never erases or merges source
boundaries — a linked spreadsheet cell and a linked drawing detail
remain themselves, cross-referenced, never flattened into one record.

**Depends on MM2, MM3, MM4, MM5** (there is nothing to cross-link until
the individual modalities exist) **and MM1** (transitively).

## MM7 — Governed multimodal investigation and analytics — IMPLEMENTED, bounded (`CLAUDE-MM7`, 2026-08-06; see `STATUS.md`'s authorization table and `current/kernel-object-model.md`'s matching entry for the real, tested, ground-truth detail — the stage-intent prose immediately below is retained unchanged as the original description, not rewritten to duplicate that record)

AI-assisted and deterministic analysis across modalities, distinguishing
facts, calculations, expert judgment, assumptions, AI suggestions,
confidence, contradictions, and required approvals — the MM1 vocabulary
applied at analysis time, across every modality MM2–MM6 made addressable
and linkable. Reuses `AnalysisRun`/`AnalysisTrigger`'s existing
machine-vs-human-initiated distinction and `Finding`'s existing
provisional-until-validated status; **no MM7 analysis output may be
silently promoted to an authoritative conclusion** — the same rule Part
E states explicitly for the Monte Carlo case applies programme-wide,
not just to that one scenario.

**Depends on MM6** (cross-modal analysis needs cross-modal linkage to
analyze across) **and, for any single-modality analysis, the relevant
MM2–MM5 stage directly.**

## MM8 — Routine in-app creation and editing

Create, add, delete, rename, reorder, revise, and export ordinary
project artifacts — team lists, registers, schedules, tables, reports,
and linked structured records — without requiring code. This is
deliberately the most "ordinary CRUD" stage of the programme; its
governance obligation is narrower than MM1–MM7's (provenance/confidence/
AI-boundary discipline matters far less for "add a row to a team
contact list" than for "an AI-suggested Monte Carlo correlation"), but
exports must still honestly label origin the same way `promote_
requirement_item()`'s own precedent already establishes for its own
Finding-creation path.

**Depends on MM1** for anything touching a structured record type MM1
already governs (e.g. editing an already-imported spreadsheet table);
otherwise largely independent of MM2–MM7, and could plausibly be
resequenced earlier if the product owner prioritizes ordinary in-app
authoring ahead of deeper multimodal intelligence.

## MM9 — Consolidated product workflows and validation

Proves end-to-end multimodal project workflows through real-browser use
(this repository's own established convention — see CLAUDE.md's "always
test from sign-in", and every `RealBrowserBehaviorTests` class already
in `tests/`), project isolation, provenance, reversible editing,
ordinary exports, Zero-Founder usability, performance, and commercial
acceptance scenarios. Not a build stage in the same sense as MM1–MM8 —
a validation/acceptance stage that presumes the others exist, structured
the same way this repository already treats "real browser verification"
as a required, separate proof step from unit/request-level tests (see
CLAUDE.md's own Testing section and every prior CLAUDE-P40 stage's
completion notes).

**Depends on every prior MM stage** actually being implemented; by
definition cannot start meaningfully early.

---

## Dependency summary

```
MM1 (foundation)
 ├─ MM2 (PDF)
 ├─ MM3 (spreadsheet)         ─┐
 ├─ MM4 (drawing)              ├─ MM6 (cross-modal linkage) ─ MM7 (governed analytics)
 ├─ MM5 (image/camera)        ─┘
 └─ MM8 (routine CRUD, mostly independent, resequenceable)

MM9 (consolidated validation) — depends on all of the above
```

## Cross-cutting requirements (apply across multiple stages, not owned by one)

- **Fact vs. measurement vs. expert judgment vs. user assumption vs. AI
  suggestion** — established once in MM1, enforced in every stage that
  produces or consumes governed content (sharpest in MM7, and in the
  Design-Manager/Monte-Carlo case below).
- **No silent AI-to-authoritative promotion** — the same discipline
  `services/case_workspace.py`'s existing `Finding.claim_status`
  (provisional until explicitly validated) already enforces for
  ordinary Findings must extend to every MM stage's own AI-touched
  output, not be re-invented per stage.
- **Provenance and source-evidence traceability** — every MM stage's
  own content must be traceable to who supplied it and on what
  authority, the same obligation `Source`/`origin_type`/
  `origin_reference` already carry for today's kernel.
- **Excel/professional-tool interoperability** (MM3, sharpest) — native
  governed structured data must never come at the cost of losing the
  ability to link to, import from, edit, and export back to real
  external workbooks other professional tools also touch.

---

## Design-Manager integration requirement (cross-cutting Camel requirement)

**Recorded per `CLAUDE-P40-VW9A` Part E — a durable, cross-cutting
requirement, not scoped to one MM stage.**

ARCHIOSK supports the Design Manager as an **expert integrator**, not
merely a coordinator who chases specialists. It must help
multidisciplinary teams structure, connect, challenge, calculate,
govern, and preserve expert work products **while retaining the
accountable authority of estimators, schedulers, designers, consultants,
and other specialists** — ARCHIOSK integrates and governs their work, it
does not silently substitute for their professional judgment or
authority.

### Canonical acceptance case

A Progressive Design-Build project uses an Excel risk register and Monte
Carlo analysis. The client requires an 80% confidence/acceptance
threshold. The team records risks, probability and cost/schedule impact
ranges, assumptions, distributions, correlations, mitigations, and
accountable owners; calculates P50/P80/P90 and the contingency
corresponding to P80; identifies dominant drivers; changes a mitigation
assumption; reruns and compares the model; and preserves the complete
evidence and decision trail.

**Treated as a canonical validation case (an MM9-shaped proof), not a
disconnected feature request and explicitly not a justification for
building a generic spreadsheet clone.** The future capability must
support both:

- **native governed structured data and analysis inside ARCHIOSK**, and
- **governed linkage to, import from, editing of, and export back to
  professional Excel workbooks** — round-trip, not one-way.

### Must preserve

- Formulas and calculated values where technically possible.
- Original source workbooks.
- Named sheets, tables, ranges, cells, charts, and external-link
  warnings.
- Who supplied each input.
- Source evidence and authority.
- Fact vs. measurement vs. expert judgment vs. user assumption vs. AI
  suggestion (MM1's shared vocabulary, applied here concretely).
- Distributions, parameters, dependencies, and correlations.
- Model version and run context.
- Pre/post-mitigation scenarios.
- Approvals, residual uncertainty, and decision authority.
- Links back to requirements, drawings, estimates, schedule activities,
  investigations, RFIs, decisions, tasks, and outcomes.

**AI must not silently promote suggested probabilities, ranges,
correlations, mitigations, or conclusions into governed expert inputs.**
This is a specific, concrete instance of the programme-wide "no silent
AI-to-authoritative promotion" cross-cutting requirement above — an
AI-suggested correlation between two risks stays AI-suggested,
distinguishable in the record from an estimator's own asserted
correlation, until a human with the accountable authority to do so
explicitly adopts it.

### Mapping across MM stages

| Requirement facet | MM stage(s) |
|---|---|
| Native structured data (risk register itself: rows, distributions, formulas) | MM3 |
| Excel round-trip (import/edit/export, formula/named-range/chart preservation, external-link warnings) | MM3 |
| Fact/judgment/assumption/AI-suggestion distinction for every register input | MM1 (vocabulary), MM7 (enforcement at analysis time) |
| Links to requirements, drawings, estimates, schedule, investigations, RFIs, decisions, tasks | MM6 |
| Monte Carlo run itself (P50/P80/P90, contingency, dominant-driver identification, rerun/compare) | MM7 |
| Pre/post-mitigation scenario comparison, model version and run context | MM7 |
| Approvals, residual uncertainty, decision authority, accountable owner per risk | MM7 (analysis governance) composing with the existing `RequirementAdjudication`/`Disposition` authority pattern (`current/kernel-object-model.md`) — not a new authority mechanism |
| Ordinary register editing outside a live Monte Carlo run (add/remove a risk row, reorder, rename) | MM8 |
| End-to-end proof of the whole canonical case, real-browser | MM9 |

No single MM stage owns this requirement in full — it is the programme's
own worked example of why MM1–MM9 are staged dependencies feeding one
coherent capability, not nine independent features.
