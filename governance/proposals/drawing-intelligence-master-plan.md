# Proposal — Drawing Intelligence Master Plan

**Status:** PROPOSAL. Reconciliation, architecture and sequencing only. No
implementation authorized by this document, and none performed while writing it.
Nothing here amends `constitutional-invariants.md`, `STATUS.md`, any `CIC-*`
contract or any `POL-*` policy.

**Product Owner direction:** `ARCHIOSK DRAWING INTELLIGENCE — CONVERGED MASTER
PLAN & DURABLE GOVERNANCE 01`, 2026-09-11. That direction explicitly authorized
planning and governance registration and explicitly withheld feature
implementation. Its own standing clause governs this file: **preserve
principles, search for authority, surface conflicts, promote only after
acceptance.** This document therefore proposes; it does not ratify itself.

**Baseline this describes:** `main` @ `6b8f135`. Every "current state" claim was
read out of the code at the cited line, not recalled.

**Companion documents this consumes rather than restates:**
`proposals/dimensional-reconciliation-and-scale-regions.md` (§7's measurement
boundary, which this document treats as binding — see §4 below),
`current/legend-of-understanding-and-craft-workshop.md`,
`current/kernel-object-model.md` (implementation inventory),
`current/contracts/CIC-SPIN-INTELLIGENCE-v1.2.md`,
`current/policies/POL-MULTI-MODEL-COMMAND-SAFETY.md` §1 and §4.

---

## 1. The governing rule this plan is built on

> **MARKET KNOWLEDGE SHOULD CHALLENGE ARCHIOSK.**
> **REPOSITORY EVIDENCE SHOULD DECIDE HOW ARCHIOSK CHANGES.**

Two external architecture reviews proposed replacing ARCHIOSK's perception spine
— one with an industrial extraction stack, one with an external multimodal agent
inspecting client image crops. Both were tested against the repository. **Neither
survived contact with what is already built**, and the reason is the same in both
cases: the primitives they proposed to introduce mostly exist, and the parts that
do not exist are not the parts either plan identified.

This document records that reconciliation so it does not have to be repeated.

---

## 2. What is actually built (the correction to both external plans)

Read at `6b8f135`. This is the finding that should change how future proposals
are weighed: **the perception spine is substantially complete, and its most
capable components are written, tested and unreachable.**

| Component | State | Evidence |
|---|---|---|
| `Source` / `StructuralUnit` / `AddressableRegion` / `EvidenceItem` | BUILT | `case_workspace.py:1384`, `:5082`, `:5117`, `:5149` |
| `AddressableRegion.parent_region_id` | BUILT, now used | `case_workspace.py:5146`; first production writer is `perception_worker._slice_legend_candidates` (`6b8f135`) |
| Normalized 0–1 coordinate convention | BUILT, validated in three places identically | `case_workspace.py:17461`, `:17482`, `:17060` |
| Orientation normalization (EXIF → OSD → stored pixels) | BUILT | `image_intake.py:274` |
| Positioned OCR (line-level boxes) | BUILT | `positioned_text.py:151` |
| Perception worker (async, leased, retried, idempotent) | BUILT | `perception_worker.py:437`, `perception_jobs.py:83` |
| Legend candidate detection / entry slicing | BUILT | `legend_detection.py:299`, `legend_slicing.py:383` |
| `Relationship` — 45 types, provenance, status resolution, dispute | BUILT | `case_workspace.py:3758`, `:14584`, `:14637` |
| `Supersession`, `TemporalObligation`, `GovernanceLog`, `Snapshot`, `Claim` | BUILT | `case_workspace.py:3713`, `:3879`, `governance.py:64`, `:5248`, `:3390` |
| Bounded evidence sachets (4, read-time, never persisted) | BUILT | `case_workspace.py:17516`, `:14797`, `:15069` |
| Deterministic cross-modal investigation (not a model call) | BUILT | `cross_modal_investigation.py:78` |
| Spin | BUILT, text-only | `spin.py:370` |
| Provider seam, no cross-provider fallback by design | BUILT | `llm_gateway.py:496` |
| **`DerivedView` — scale state/value/method, North, rotation, `may_measure`, view↔source transforms, `may_compare_spatially`** | **BUILT, UNWIRED** | `case_workspace.py:2725`, `derived_view.py:91`, `:188`, `:222` |
| **`sheet_vision` — governed Gemini vision, local-first, conjunctive gate, allowlist egress digest, bounded rasterization, injection fencing, audit invariant** | **BUILT, UNWIRED** | `sheet_vision.py:589`; zero callers outside `tests/` |
| **`drawing_segmentation` — title-block segmentation, scale-notation parsing, `segment_sheet`** | **BUILT, UNWIRED** | `drawing_segmentation.py:195` |
| **`PDFVectorExtractor` — per-page vectors incl. closed rectangles, stroke widths, dashes, positioned native text** | **BUILT, UNWIRED to perception** | `engine/pdf_extractor.py:34` |

**Consequence for governance.** An external proposal that offers ARCHIOSK
"viewport detection", "scale handling" or "multimodal drawing reading" is not
offering a missing capability. It is offering a second implementation of an
existing one. Future proposals must be tested against this table first.

---

## 3. What is genuinely missing

Five gaps, in dependency order. None of them is a model, a database, or a
parsing library.

1. **Raster PDF pages yield no coordinates.** `raster_extraction.py:245-247`
   builds the *same* PyMuPDF OCR textpage that `positioned_text._default_ocr`
   uses, then calls only `page.get_text(textpage=…)` and discards the word
   boxes the engine already produced. `positioned_text.py:130` shows the single
   additional read that recovers them at no extra OCR cost. Compounding it,
   `perception_worker.run_one:458-463` refuses every non-PNG/JPEG file, while
   `ingestion.py:1007` **already enqueues perception jobs for PDFs** — so
   scanned drawings are queued today and dead-end at that gate. The store side
   (`register_positioned_text_regions`) is generic and already accepts any
   structural unit. **Only the producer is missing.**

2. **Nothing ever proposes a relationship between two Sources.** This is the
   empty centre. `Relationship` is a well-built substrate with 45 types and
   exactly **three** production writers, two of them manual.
   `cross_modal_investigation` reads that graph and cannot populate it, so a
   cross-drawing investigation today returns an honest abstention. This is the
   same point the Product Owner direction makes independently: *do not ask GO to
   find the discrepancy until ARCHIOSK can find the related things.*

3. **No evidence package spans two Sources.** All four sachets assemble one
   anchor plus its siblings and then explicitly exclude every other Source
   (`case_workspace.py:17583`). Spin, the only whole-project reasoner, is
   text-only under a 60,000-character cap and never sees a region or a box.

4. **No shared spatial frame between two sheets.** Every coordinate is a
   fraction of its own private frame; `x=0.5` means "half-way across whatever
   unit this region hangs from." `derived_view.may_compare_spatially` is a
   **veto**, not a transform, and with nothing writing scale or North in
   production it refuses every real pair.

5. **The capable components are unreachable.** See §2. `sheet_vision.read_sheet`
   additionally returns a JSON payload and writes no `EvidenceItem` and no
   `AddressableRegion`, so even once invoked it produces nothing the evidence
   graph can cite.

---

## 4. The conflict this plan surfaced, and the reconciliation proposed

**Surfaced rather than resolved, per constitutional invariant #10.**

The Product Owner direction proposes `PAGE SPACE → VIEW SPACE → PROJECT/WORLD
ANCHOR SPACE`, a `measure_clearance(…)` tool, and "clearance" among the things
code should deterministically know.

`proposals/dimensional-reconciliation-and-scale-regions.md` §7 states:

> **ARCHIOSK reconciles stated dimensions. It does not measure drawings, and no
> mechanism in this specification may be implemented in a way that produces a
> magnitude from page geometry.**

and `current/kernel-object-model.md` records the current implemented position:
**"Scale/measurement: recorded, never authoritative"** — no calibration, no
pixel-to-real-world conversion, no measurement tool, and a mandatory visible
warning in the viewer.

Both are grounded in constitutional invariant #2 (machine inference never
silently becomes authority). The dimensional proposal is `PROPOSAL` status and
therefore does not itself govern; the kernel-object-model statement is a current
implementation fact. **Either way, the direction's measured-clearance spine
conflicts with the corpus's stated position and must not be implemented on the
strength of a planning document.**

### Proposed reconciliation — identity anchoring, not coordinate registration

The conflict dissolves without weakening §7, because **the first commercially
meaningful discrepancy needs no coordinate transform at all.**

- **Topology is not magnitude.** "Region A overlaps region B", "this callout
  targets that sheet", "this tag appears in this block" are relationships in
  normalized page space. A polygon test returns a boolean, not a millimetre.
  Nothing in §7 forbids a boolean.
- **Identity anchors beat geometric anchors.** *"Grid C/4"* on A-201 and *"Grid
  C/4"* on S-201 are the same place **by declaration**, not by measurement. A
  shared grid label, level name, room number, door tag or schedule key is a
  registration anchor that costs no calibration and carries the author's own
  authority. This is a stronger basis than a derived transform, not a weaker one.
- **Stated-vs-stated reconciliation is the product.** "Structural states 2400
  AFF; Architectural states 2700 AFF for the same element at the same grid
  intersection" is auditable and signable. It is also exactly what the
  dimensional proposal's Native Dimensional Genealogy already designs.
- **Measured clearance stays closed**, per §7 consequence 2, until real
  calibration and a separate deliberate authorization.

This is not a workaround. The dimensional proposal already warned that **"a more
precise answer to the wrong question is the most attractive failure mode
available to this product, because it looks like rigour."** A measured Δ invites
a reader to correct a number; a stated-value conflict tells them which drawing to
fix.

**Product Owner decision required.** This section proposes a reconciliation; it
does not enact one. If measured geometry is genuinely wanted in the MVP, §7 must
be amended through its own process rather than bypassed by a plan.

---

## 5. Principles proposed for durable registration

Proposed, not ratified. Each is proposed because it is currently unwritten
anywhere, and each cites rather than restates existing authority.

**P1 — Perception produces evidence, never authority.** Every perception output
is `EVIDENCE_CLASS_EXTRACTED` and carries its own uncertainty. A reading is a
reading of an image, never the document speaking. *(Existing basis:
`legend-of-understanding-and-craft-workshop.md` §3; constitutional invariant #2.)*

**P2 — Wrong region, correct downstream processing, is the characteristic
failure of this pipeline.** A compiler-shaped system produces plausible output
from a mis-located input, and plausibility is what makes it dangerous. Every
stage must carry its parent's weakness forward rather than presenting its own
internal success as the result. *(Observed: `CLAUDE-GO-PERCEPTION-LEGEND-SLICE-01`
faithfully sliced a title block that `rows_beside` mis-identified as a legend.)*

**P3 — Where code can know, code decides; where interpretation is required, GO
interprets.** GO is not the ruler; GO interprets what the ruler measured. GO must
not perform deterministic geometry that code can establish, and code must not
assign meaning that requires judgement. *(Cited, not restated:
`POL-MULTI-MODEL-COMMAND-SAFETY` §1, `CIC-SPIN-INTELLIGENCE-v1.2`,
`legend-of-understanding-and-craft-workshop.md` §3,
`dimensional-reconciliation` §7. A GOV-P is the corpus's own home for a rule
four records each partially restate — see §9.)*

**P4 — Relationship before discrepancy.** ARCHIOSK does not compare two
conditions because their text resembles each other. A comparison requires a
stated basis — callout, shared grid, shared level, shared tag, shared schedule
key, shared specification reference, revision lineage, or an existing governed
relationship — and that basis is recorded with the finding.

**P5 — Zero image egress is a property of the perception path, not of ARCHIOSK.**
The perception worker is local-only. A separate, Product-Owner-authorized,
classification-gated vision seam exists (`sheet_vision.py`, denying at
RESTRICTED and above). Stating "ARCHIOSK never sends drawings out" is false and
would mislead a future reader; stating "customer perception is local" is true.
*(Existing basis: `POL-MULTI-MODEL-COMMAND-SAFETY` §4, which owns this subject.)*

**P6 — Claim strength follows evidence quality and task tolerance.** There is no
universal precision doctrine. A question answerable from a stated value does not
inherit the uncertainty of a question that would need calibration, and neither
inherits a fixed threshold. *(Existing basis:
`irregularity-interpretation-and-legibility.md`.)*

---

## 6. Phased plan

Effort is given as VED (vertical effort day) ranges with explicit confidence.
Ranges are estimates, not commitments, and no elapsed-time promise is made.

### Phase 0 — Foundation map *(this document; complete)*

### Phase 1 — Perception gap closeout *(critical path)*

| | |
|---|---|
| **Objective** | Positioned evidence from the sources clients actually send. |
| **1A — PDF positioned OCR** | Return word boxes from the textpage `raster_extraction` already builds; feed `register_positioned_text_regions` per page unit; remove the worker's image-only gate. Fix the known one-unit binding at `perception_worker.py:131-134` so page *n* binds to page *n*. |
| **1B — PNG working frame** | Decouple frame format from the orientation decision. Today `_encode_frame` runs only when `orientation["changed"]` is true, so an unrotated JPEG is read as JPEG — measured at 4,953 chars / 0.426 legible against 9,548 / 0.631 for the lossless frame. The working frame should be a deliberate perception decision, not a side-effect. Source bytes, EXIF and checksum remain untouched either way. |
| **1C — `rows_beside`** | Bound or retire the only detection fallback with no measured real example. P2 is the reason this is on the critical path. |
| **Reused** | `positioned_text`, `register_positioned_text_regions`, `perception_jobs`, `image_intake` |
| **Exit evidence** | A real scanned sheet from the corpus produces line-level regions with correct per-page binding; the PNG change is measured on ≥3 real sources before adoption; `rows_beside` either bounds correctly or is disabled with its removal recorded. |
| **Do NOT build** | Layout models, new OCR engines, viewport detection, any new store method. |
| **Failure modes** | Silent per-page mis-binding; a PNG change that improves one corpus and degrades another; region volume (see §7). |
| **VED** | 3–6 · **confidence MEDIUM-HIGH** (1A is precisely located; 1B is a decision plus measurement) |

### Phase 2 — Viewport / view / scale *(mostly wiring)*

Objective: a sheet resolves into views with declared scale, each carrying its own
provenance. **`DerivedView`, `drawing_segmentation.segment_sheet`,
`derived_view.may_measure` / `to_view_coordinates` / `may_compare_spatially` and
`PDFVectorExtractor`'s closed rectangles already exist.** The work is wiring and
a viewport-boundary proposer over vector rectangles, not new architecture.
Prerequisite: Phase 1. **Do NOT** open `measured` scale origin (§4).
**VED 5–10 · confidence MEDIUM** (unwired code has unknown integration cost).

### Phase 3 — Sheet index and callout relationships *(the empty centre)*

Objective: the first automatic `Relationship` writer in the system — callouts,
sheet references, detail chains, drawing index — proposed with provenance, never
confirmed automatically. This is gap #2 and the largest single unlock: it makes
`cross_modal_investigation` capable of returning something other than abstention.
Prerequisite: Phase 1. **VED 8–15 · confidence MEDIUM.**

### Phase 4 — Grid / level / tag identity anchors

Objective: extract *declared* anchors — grid labels, level names, room numbers,
tags, schedule keys — as first-class identity, and relate regions that share one.
**Identity, not coordinate registration** (§4). Prerequisite: Phases 1, 3.
**VED 8–15 · confidence LOW-MEDIUM** (real grid-bubble recognition on raster
sheets is unmeasured here).

### Phase 5 — Two-sided governed micro-context

Objective: the first evidence package that spans two Sources — "region R on the
architectural sheet, the corresponding region on the structural sheet, the
relationship basis, both citations, both authorities, both uncertainties." Extend
the existing sachet pattern; do not invent a second one. Prerequisite: Phases 3, 4.
**VED 5–10 · confidence MEDIUM.**

### Phase 6 — First deterministic + semantic discrepancy

Objective: one auditable cross-discipline finding. Deterministic half is
**stated-value reconciliation anchored by shared identity** (§4), not measured
geometry. GO reconciles wording, intent and consequence over the Phase 5 package.
Prerequisite: Phase 5. **VED 8–15 · confidence LOW-MEDIUM.**

### Phase 7 — Controlled pilot proof

One real drawing set, end to end, with human disposition. Exit: a finding a
professional will sign. **VED 5–12 · confidence LOW.**

### Phase 8 — Component benchmarking and selective replacement

Only after a working baseline exists to benchmark against. **VED open.**

---

## 7. Storage — the one measured limit

Recorded: one real photographed source produced **502 KB** of line-level
positioned-region JSON; the largest workspace record in the system is **1,005
KB**, rewritten whole on every save. Measured this session: per-write cost tracks
workspace size (**32 ms** at 151 KB, **71 ms** at 615 KB, 5 runs each).

Arithmetic consequence, stated as extrapolation rather than benchmark:

| Sheets in one project | Approx. one workspace JSON |
|---|---|
| 10 | ~5 MB |
| 50 | ~25 MB |
| 500 | **~245 MB** |
| 2,000 | ~980 MB |

**Confidence: HIGH on direction, MEDIUM on magnitude.** Flat JSON is correct for
Document Shop scale and is not correct for a 500-sheet set. This is the measured
limit the Product Owner direction asked to be identified before any storage
change is considered — **it is not an argument for a graph database.** ARCHIOSK
needs a relationship graph; it does not follow that it needs a graph engine. The
deficiency to solve when the time comes is *whole-record rewrite cost on a
per-project file*, and that is the sentence a future proposal must answer.

---

## 8. External components — benchmark candidates only

Nothing is installed, selected or endorsed. A candidate enters implementation
only after beating the current internal primitive **on real ARCHIOSK material**,
and technology names belong in this register, never in doctrine.

| Candidate | Problem it might solve | Internal baseline | Benchmark trigger | Reject if |
|---|---|---|---|---|
| Docling (MIT) | Table/spec structure | `pdf_intelligence` text-only | Phase 8 | No gain on real specs |
| Shapely / GEOS (BSD-3) | Overlap, containment, distance | Hand-rolled float math, no library | Phase 2 needs polygon ops | Hand-rolled suffices at this scale |
| Alternative OCR | Raster legibility | Tesseract via PyMuPDF | After 1A/1B are measured | No gain over the lossless-frame change |
| Commercial PDF SDK | AGPL exposure on PyMuPDF | PyMuPDF (AGPL/commercial), already load-bearing | Commercial licensing decision | Artifex licence is cheaper |
| Layout detection | Viewport boundaries | `PDFVectorExtractor` rectangles | Only if Phase 2 rectangles prove insufficient | AGPL (DocLayout-YOLO) or revenue-threshold weights (Surya) — both disqualifying for a commercial AEC product |
| IFC tooling | BIM verification | None | Post-MVP | — |

Licensing note for the record: **PyMuPDF is AGPL-3.0/commercial and is already
deployed.** Any claim that a PyMuPDF-centred stack carries "zero licensing risk"
is false.

---

## 9. What this proposal does not do

- **No implementation.** No service, route, template, schema or test changed.
- **No self-ratification.** §5's principles are proposed. The corpus's routing
  rules indicate their eventual homes — a `CIC-DRAWING-INTELLIGENCE` contract for
  the domain architecture (no existing contract covers perception), a `GOV-P` for
  P3, and `POL-MULTI-MODEL-COMMAND-SAFETY`'s own next version for P5 — but each
  requires Product Owner ratification and, for the policy, a supersession record.
  **None was created here.**
- **No amendment of the measurement boundary.** §4 surfaces the conflict and
  proposes a reconciliation. It does not enact one.
- **No new storage architecture**, no graph database, no spatial index.
- **No change to zero-egress behaviour.**
- **No deletion.** Legend work is frozen at its current foundation, not removed;
  the Craft Workshop / Legend of Understanding governance distinction is
  untouched.

---

## 10. Recovery anchor

A future session with none of this conversation should be able to recover:
this document, `CONTINUATION_CHECKPOINT.md`'s entry for `6b8f135`, and
`STATUS.md`'s pointer. The three facts most easily lost are: **the capable
drawing components are built and unwired** (§2), **the empty centre is
relationship proposal, not perception** (§3.2), and **the measurement boundary
conflict is unresolved and must not be bypassed by a plan** (§4).

---

# Addendum 1 — Product Owner decision brief: the measurement boundary

**Added 2026-09-11** under `MASTER PLAN ACCEPTANCE PREP + CODEX TRAINING HANDOFF
CADENCE 01`. Appended to this proposal rather than filed separately: the conflict
is this document's §4, and a second file would create a second authority on one
subject. **The decision is the Product Owner's. Nothing below is enacted.**

## The question, stated once

May ARCHIOSK derive a physical magnitude from drawing page geometry, and if so
under what contract? Existing doctrine says no
(`dimensional-reconciliation-and-scale-regions.md` §7; `kernel-object-model.md`
"recorded, never authoritative"), both grounded in constitutional invariant #2.

## Option A — Identity-first / stated-value reconciliation

Relationships and comparisons rest on **declared** identity: grids, levels, tags,
callouts, view identities, stated dimensions, explicit datum values. No physical
magnitude is ever derived from page geometry.

- **Benefit.** No governance change required — it is already compliant. Fastest
  to a first finding. Every claim carries the author's own authority, so a
  finding is signable without ARCHIOSK vouching for a measurement. Immune to the
  export/crop/reissue problem §7 names.
- **Risk.** Cannot detect a discrepancy that exists only geometrically — two
  elements that physically clash while every stated value agrees. Depends on
  drawings being adequately annotated, which poor sets are not.
- **Constitutional impact.** None. Invariant #2 is satisfied by construction.
- **Effect on MVP.** Enables it. This is the shortest path to Phase 6.
- **Implementation burden.** Lowest. No calibration, no transform provenance, no
  tolerance model.
- **Professional / liability.** Strongest position: ARCHIOSK reports what the
  documents state and who stated it. It never asserts a dimension of its own.
- **New governance required.** None beyond ratifying this plan.

## Option B — Governed calibrated measurement

Magnitude from geometry is permitted only when an explicit calibration contract
is satisfied. If adopted, §7 must be **amended through its own process**, not
bypassed, and at minimum the contract must fix all eight of:

1. **Authoritative scale source** — and its rank against a conflicting one
   (`DerivedView.scale_method` already enumerates: printed notation, title label,
   graphic scale bar, known dimension, vector metadata, manual confirmation).
2. **Calibration evidence** — what was measured against what known quantity, by
   whom, and when. §7's "a stated scale is not a calibration" must survive.
3. **Viewport boundary** — which view the transform belongs to. Page is not view.
4. **Transform provenance** — the full chain, reconstructable, per invariant #3.
5. **Tolerance** — per operation, not universal.
6. **Uncertainty** — carried into every claim, never dropped downstream.
7. **Claim restrictions** — what may and may not be asserted from a measured
   value, and the language it must be reported in.
8. **Professional authority** — whether a measured magnitude is ever ARCHIOSK's
   assertion or always a human professional's, and what the human is signing.

- **Benefit.** Detects geometric-only discrepancies. Matches what competitors
  claim, and is the capability a clearance check genuinely needs.
- **Risk.** The one §7 names precisely: *"a more precise answer to the wrong
  question is the most attractive failure mode available to this product, because
  it looks like rigour."* A calibrated number invites correction of a value that
  may not be wrong. Export scaling, cropping and reissue silently invalidate a
  calibration that still looks valid.
- **Constitutional impact.** **Direct tension with invariant #2** unless the
  contract keeps the magnitude as inference and never promotes it to authority.
  This is the crux and it is not a drafting detail.
- **Effect on MVP.** Delays it materially — calibration is a research problem on
  raster sheets, not an implementation task.
- **Implementation burden.** Highest by a wide margin.
- **Professional / liability.** Weakest. ARCHIOSK becomes the author of a
  dimension a professional may rely on.
- **New governance required.** A §7 amendment with supersession record, a
  calibration contract, probably a `CIC-*`, and revised claim language.

## Option C — Hybrid

Option A is the default and the MVP path. Calibrated measurement becomes a
later, **separately governed** capability for narrowly defined operations where
calibration evidence genuinely exists (e.g. a sheet carrying a graphic scale bar
plus a verifiable known dimension).

- **Benefit.** Ships A's speed and safety without foreclosing B. Matches §7's own
  consequence 2, which says the `measured` origin *stays closed* — closed is not
  abolished. Real evidence from Phases 1–6 then informs whether B is worth its
  cost, instead of deciding now.
- **Risk.** "Later" can become permanent drift, or the narrow exception can widen
  quietly. Needs the trigger condition written down now.
- **Constitutional impact.** None today; defers B's invariant-#2 question to the
  point where it must actually be answered.
- **Effect on MVP.** Identical to A.
- **Implementation burden.** Identical to A today.
- **Professional / liability.** Identical to A today.
- **New governance required.** None now. A future B-style authorization later,
  through §7's own process.

## Recommendation

**Option C**, and the reasoning is that it is Option A plus honesty about the
future rather than a different plan. A and C are indistinguishable in code for
the whole of Phases 1–6; they differ only in whether the corpus records that
measurement is *deferred pending evidence* or *excluded in principle*. Recording
it as deferred is truer to what is actually known: nobody here has yet measured
whether calibration is achievable on real raster sheets, and excluding it
permanently would be a decision made without that evidence — the same error in
the opposite direction.

Option B should not be taken now. Not because measurement is wrong in principle,
but because its hardest part is unmeasured, its governance cost is real, and the
first commercially meaningful discrepancy demonstrably does not need it.

**This is a recommendation. The decision is the Product Owner's, and the plan
does not proceed past Phase 1A's authorization without it.**

---

# Addendum 2 — Storage: measured scale limit, registered as a future trigger

Registered, not acted on. **No replacement storage is proposed or chosen.**

- ~**502 KB** positioned-region payload for one measured real source
- largest current workspace record ~**1,005 KB**, **rewritten whole on every save**
- measured write cost rising with workspace size: **32 ms** at 151 KB,
  **71 ms** at 615 KB (5 runs each)
- **~245 MB** extrapolated for a 500-sheet project in one workspace JSON —
  **direction HIGH confidence, magnitude MEDIUM**

**Trigger, stated so a future session inherits a condition rather than a
judgement call:** flat workspace JSON remains valid for present small-scale
workflows and is not credible as the permanent persistence mechanism for
500–2,000 sheet positioned-evidence projects. The eventual decision must follow
**actual access and query requirements**, and the deficiency it must answer is
*whole-record rewrite cost on a per-project file* — not the absence of a graph
engine. ARCHIOSK needs a relationship graph; that does not imply a graph
database, and relationship proposal (§3.2) must not be solved by introducing one.

---

# Addendum 3 — Corrected statements, preserved rather than overwritten

Per `CLAUDE.md`'s **CURRENT STATE MUST NOT LAUNDER HISTORY**. Four claims made
earlier in this plan's own development were wrong or too broad. They are recorded
here with their corrections so the evolution stays reconstructable.

| Earlier claim | Correction | Why it was wrong |
|---|---|---|
| "ARCHIOSK has zero image egress" | True of the **production perception worker**. False of ARCHIOSK as a whole: `services/sheet_vision.py` is a separately governed, classification-gated external vision seam that denies at RESTRICTED+. Making ordinary customer perception depend on it is **not currently authorized**. | Generalized one path's property to the whole system. |
| "An external-vision architecture would be a governance reversal" | The governed seam **already exists** and was Product-Owner-authorized 2026-08-29. What would be a reversal is routing *customer perception* through it, or sending RESTRICTED+ material. It is a policy question about existing machinery, not an architecture question. | Asserted from the perception path without searching for an existing seam. |
| "No storage change is needed at 500–2,000 sheets" | No longer supportable. See Addendum 2. | Stated before the positioned-evidence payload was measured. |
| Viewport / scale placed early on the critical path | Moved later. Most of it is **built and unwired**, and the first discrepancy needs identity anchoring, not coordinate registration. It enters only where a selected discrepancy actually requires it. | Component names sounded foundational; dependency analysis said otherwise. |

---

# Addendum 4 — Revised development order

Subject to the Addendum 1 decision:

**Phase 1A — PDF positioned OCR.** Then evidence decides:

- **usable geometry** → 1B PNG working frame → cross-Source relationship proposal
- **poor geometry** → 1B PNG working frame **first** → remeasure → then
  relationship proposal

Then: relationship proposal → two-sided micro-context → stated-value
reconciliation → first auditable discrepancy.

**Viewport / scale wiring enters only where the selected discrepancy requires
it** — not earlier because the component names sound foundational.

**Phase 1A is technically independent of the measurement decision.** It produces
positioned text regions in the existing normalized 0–1 fraction space and derives
no magnitude of any kind, so it is compatible with Options A, B and C alike. It
is **TECHNICALLY UNBLOCKED, AWAITING PRODUCT OWNER AUTHORIZATION.**
