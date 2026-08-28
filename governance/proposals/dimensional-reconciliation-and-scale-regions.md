# Proposal — Scale Regions and Dimensional Reconciliation

**Status:** PROPOSAL. Analytical and specification work only. No implementation
authorized by this document, and none performed while writing it. Nothing here
amends `constitutional-invariants.md` or `STATUS.md`.

**Baseline this describes:** `main` @ `fb06d17`. Every "current state" claim below
was read out of the code at the cited line, not recalled.

**Companion document:** `proposals/surface-vs-substrate-interaction-grammar.md`.
This proposal consumes that one's §4.2 basis rule, its §5.1 Tier 0–2 grammar, and
its §6.1/§6.2 contrastive-and-denominated disclosure requirement. It does not
restate them; where it extends one, it says so and says how.

**Read this first — two things this document must not be read as claiming.**

1. **ARCHIOSK cannot measure a drawing, and nothing here proposes that it should.**
   `services/drawing_intelligence.py:12–17` states the capability boundary in the
   module's own words: *"no PDF-to-image rendering, no local OCR, no automatic
   symbol/room/dimension recognition, no authoritative measurement from an
   uncalibrated page or image."* Every mechanism specified below operates on
   **stated** dimensions — text a document printed — and on nothing else. §7 makes
   this a hard boundary rather than a current limitation.
2. **"Glass Box" is new terminology, introduced by the directive that commissioned
   this document.** It appears nowhere in the repository or the governance corpus.
   This proposal treats it as a name for the already-specified Tier 0–2 disclosure
   model (grammar §5.1) and deliberately does **not** define it as a second,
   parallel construct. Per CLAUDE.md's proliferation-cycle warning, a new word for
   an existing mechanism is a cost, not a deliverable.

---

## 1. The gap, stated precisely

The interaction grammar settled how an assertion reaches its evidence. It assumed
throughout that "the evidence" is a *location on a page* — grammar §5.1 Tier 2 is
"the document itself, at its location where basis permits."

**A dimension is not located; it is located *and scaled*.** A number read off a
drawing means nothing until you know which scale region of which sheet it belongs
to and which unit system it was born in. Two readers can open the identical
citation, at the identical crop, and derive different real-world quantities — and
neither of them has made an error the grammar can detect, because the grammar's
notion of reachability terminates at the pixel.

This is the same failure the grammar found for citation and did not find for
measurement: **a route to evidence that leaves an inference to the reader is a
route that produces unrecorded, unverifiable conclusions** (grammar §4.1). The
inference here is not "which document did they mean" but *"what does this number
mean in the world."* It is performed constantly, silently, by every person who
reads a drawing, and the product currently offers no place to record it.

Two distinct inferences are involved, and conflating them is the specific error
this document exists to prevent:

| Inference the reader currently performs unaided | Governed by |
|---|---|
| *"Which scale governs the region I am looking at?"* | §4 — Scale Regions |
| *"Do these two dimensions, from different systems, agree?"* | §5 — Dimensional Genealogy |

---

## 2. What `main` actually has today

Measured, not recalled. This section is the "identify what already serves the
purpose" step CLAUDE.md requires before any new abstraction is proposed.

### 2.1 Scale exists as one string per sheet

`services/drawing_intake.py:131` registers exactly one extraction pattern:

```python
"scale": [ re.compile(r"^scale\s*:\s*(?P<value>.+)$", re.IGNORECASE) ],
```

`services/drawing_intelligence.py:208` (`_title_block_fields_for_page`) applies it
**per page**, which is correct — a multi-sheet set has one title block per sheet —
and yields `{field: {"value", "reliability", "evidence_snippet", "source_page"}}`.
That dict lands in `StructuralUnit.modality_metadata.fields` via
`register_drawing_sheet_structure` (`services/case_workspace.py:14439`).

So the shipped model is: **one sheet, one scale string, one reliability tag.** It
cannot represent a 1:100 plan carrying a 1:20 wall section and a 1:10 jamb detail,
which is the ordinary case, not an exotic one.

### 2.2 The reliability vocabulary is already right, and already covers scale

`services/case_workspace.py:3967–3979` defines
`METADATA_RELIABILITY_DIRECTLY_EXTRACTED / USER_ENTERED / INFERRED / UNAVAILABLE /
UNVERIFIED`, closed, and its own comment names the fields it governs — *"sheet
number/title/discipline/revision/issue date/consultant/**scale**"* — with the rule
attached: *"never silently promoted to a higher tier than the extraction method
actually supports."*

**This is the correct discipline and this proposal does not replace it.** But
reliability answers *"how did we come to hold this string?"* It does not answer
*"what does this string govern?"* — and that second question is the whole content
of a multi-scale sheet. §4 adds the second axis; it does not touch the first.

### 2.3 The nesting this needs already exists and is already named

`StructuralUnit` (`services/case_workspace.py:4027`) carries
`parent_structural_unit_id` (line 4057), and its docstring anticipates this exact
case in its own words: *"A unit may nest under another (`parent_structural_unit_id`
— e.g. **a drawing detail viewport nested under its sheet**) without a separate
mechanism."*

`AddressableRegion` (line 4062) is open-world on `region_type` (line 4086) and its
docstring names *"a drawing callout region"* among its intended shapes.

**The object model already reaches this problem. Nothing in §4 requires a new
durable abstraction** — which is why §4 does not propose one.

### 2.4 Units are already stated-only, and the discipline is exemplary

`extract_unit_from_header` (`services/case_workspace.py:4770`):

> *"a unit is only ever inherited from the COLUMN HEADER's own explicit
> parenthetical (e.g. `"Net Area (m²) each"` -> `"m²"`) — **never guessed or
> assumed from cell content**. Returns None when the header carries no such hint."*

And the cell contract at line 3767: cells hold
`{"id","header","raw_value","parsed_value","qualifier","unit"}`, where **`raw_value`
is NEVER discarded** when a `parsed_value` is derived, and `qualifier` preserves
`"—"`, `"TBD"`, `"approx."` rather than coercing them — *"a blank cell or em dash is
never silently treated as zero."*

**§5 is a generalization of this rule from table cells to drawing dimensions, not a
new rule.** The genealogy specified there is what "never discard `raw_value`" looks
like when the derivation is a unit conversion rather than a numeric parse.

### 2.5 A blanket measurement disclaimer already ships

`static/js/drawing_image_viewer.js:355–358` appends to every sheet's metadata panel:

> *"Measurements are not reliable: scale is recorded as extracted text only, not
> calibrated against this image. Do not take dimensions from this view."*

**This sentence is substantively correct and must not be weakened.** Two properties
of it are defects under the grammar, both addressed in §6.4:

- It is **unconditional** — rendered identically whether the sheet stated `1:100`,
  stated `NTS`, or stated nothing at all. A warning that cannot vary carries no
  information about the sheet in front of you.
- It is **non-diegetic and sheet-global** — one sentence in a metadata panel, for a
  page that may contain three scale regions of differing trustworthiness.

### 2.6 The canvas has no concept of real-world length

`services/drawing_intelligence.py:96–181` (`transform_point_to_display` and its
rectangle counterparts) and `create_addressable_drawing_region`
(`services/case_workspace.py:14518`) operate entirely on **normalized 0–1 fractions
of the sheet's own stored width/height**. Rotation and mirroring are modelled;
magnification is not, and real-world length is not present anywhere in the
geometry.

This is a sound decision and §7 keeps it. It does mean that a "scale region" can
only ever be a **declared, addressed area carrying a stated scale** — never a
calibrated one.

---

## 3. The distinction this proposal turns on

Two dimensions from different unit systems can disagree in two ways that look
identical in a diff and are not remotely the same finding.

**Arithmetic disagreement.** `2400 mm` on one sheet, `7'-10"` (2387.6 mm) on
another, for the same wall. One of them is wrong. The disagreement is a *quantity
error*, it has a magnitude, and stating that magnitude is useful: someone will
change a number.

**Modular disagreement — a phase clash.** A `600 mm` structural grid on A-101 and
`16" o.c.` studs (406.4 mm) on A-501. **Neither is wrong.** Each is internally
correct, conventional, and probably specified by a different consultant. They
disagree because their modules are incommensurable: the two rhythms coincide only
at large common multiples, and across any ordinary run they drift continuously in
and out of phase.

> **Reporting a phase clash as a delta is a lie of exactly the family the grammar's
> Anti-Fluency Constraint names.** "Δ 193.6 mm" is arithmetically true, fluent,
> precise, and it tells the reader to correct a number. There is no number to
> correct. The finding is that two module systems meet on this project and someone
> must decide which governs — a coordination decision, not a dimensional one.

Precision cannot resolve it. Converting to more decimal places makes the report
more confident and no more true. This is the concrete case that makes the general
rule bite: **a more precise answer to the wrong question is the most attractive
failure mode available to this product**, because it looks like rigour.

Both parties being correct while the system must not pick a side is
`constitutional-invariants.md` #10 verbatim — *"Authority conflicts surface, never
resolve silently."* A phase clash is an authority conflict expressed in
millimetres.

---

## 4. Deliverable 1 — Scale Regions

### 4.1 Definition

> A **Scale Region** is a bounded area of a drawing sheet, addressed in that
> sheet's original coordinate frame, over which exactly one stated scale governs —
> together with the record of **what that scale statement's scope actually is**.

A Scale Region is **not a new object.** It is:

- a nested `StructuralUnit` (`unit_type: "detail"` or `"viewport"`) under its
  sheet, using `parent_structural_unit_id` exactly as that class's docstring
  already anticipates (§2.3), for a callout that carries its own identity and
  label; **or**
- an `AddressableRegion` with `region_type: "scale_region"` on the sheet unit,
  for a bounded area that has a distinct scale but no independent identity.

Both already exist, are already open-world on their type field, and already nest.
The proposal adds **one closed vocabulary and one rule**, not a mechanism.

### 4.2 The scope vocabulary — what a scale statement actually governs

The reliability tiers (§2.2) stay untouched and answer *how the string was
obtained*. This second, orthogonal, closed vocabulary answers *what it governs*,
and is derivation-owned in the same way `RESOLUTION_STATUS_*` is — the evaluator
names its own outcome and a caller never supplies one:

| Scope | Means | Governs |
|---|---|---|
| `sheet_absolute` | title block states a scale with no exception clause | the whole sheet |
| `sheet_default` | *"1:100 unless noted otherwise"* — a default **with a stated exception clause** | only regions that state nothing |
| `region_stated` | a viewport/callout states its own scale | that region only |
| `not_to_scale` | `NTS` — an explicit, positive refusal by the author | that region; **measurement prohibited by the source itself** |
| `none_stated` | no scale statement anywhere on record for this area | nothing — extent unknown |

**`sheet_default` is the finding that justifies this vocabulary.** *"1:100 U.N.O."*
is not a sheet scale. It is a default plus an admission that exceptions exist
somewhere on the sheet, unlocated. Today it is extracted by
`drawing_intake.py:131`'s pattern and rendered by `drawing_image_viewer.js:347` as
`Scale: 1:100 unless noted otherwise (directly extracted)` — a `directly_extracted`
reliability tag, which is *true about the string* and actively misleading *about
the sheet*. The document has told the reader "there are other scales here and I
have not told you where," and the interface renders that as an extracted fact.

**`not_to_scale` must never collapse into `none_stated`.** This is
`case_workspace.py:3770`'s `qualifier` rule applied to drawings: an em dash is not
zero, and `NTS` is not "no scale found." One is the author stating a boundary; the
other is the system finding nothing. Rendering them identically discards a
statement the source actually made.

### 4.3 The rule

> **A dimension may only be reconciled against another dimension when both sides'
> governing Scale Region is on record. Where it is not, the finding's scope is
> `none_stated` and the finding must say so rather than proceed.**

This is `constitutional-invariants.md` #3 (provenance is mandatory) applied to
magnitude rather than to citation. It is also the point where this proposal
deliberately accepts producing *fewer* findings: a reconciliation the system cannot
scope is one it must decline to assert, not one it may assert with a caveat.

### 4.4 What this displaces, honestly

Per grammar §4.1, the case for this is **not** that it saves the reader steps. On a
four-document fixture with one scale per sheet it saves none.

> The value of a Scale Region is that it replaces the reader's silent, unrecorded
> *"which scale governs this callout?"* with a recorded answer that a reviewer can
> later check — including checking that the answer was **unknown**.

Same destination, different epistemics, and only one of the two leaves a trace.
That is the argument this must be defended on, and §9 is the experiment that could
refute it.

---

## 5. Deliverable 2 — Native Dimensional Genealogy

### 5.1 Native means the record keeps the system it was born in

A dimension printed `16" o.c.` is an **imperial** fact about this project.
`406.4 mm` is a *derived view* of that fact. The record must hold the first and
derive the second, never the reverse, and never lose the first — which is
`case_workspace.py:3770`'s *"`raw_value` is NEVER discarded"* extended from cells to
dimensions.

The consequence is a display rule, not just a storage one:

> **A converted magnitude may never be rendered in the same visual form as a stated
> one, and must always be able to name the magnitude and unit it was derived from.**

`406.4 mm` presented as though A-501 said it is the identical defect to the
grammar's Arm B rendering a prose-derived deep link as though the analysis had read
the document. No drawing in the set says `406.4`. Something has to carry that.

### 5.2 The genealogy — four retained steps

Each step is retained; none replaces its predecessor.

| Step | Holds | Rule |
|---|---|---|
| `stated` | the literal string the source printed — `2400`, `8'-0"`, `16" o.c.` | never discarded, never normalized in place |
| `parsed` | magnitude + unit token, **where the unit was stated** | never guessed from magnitude — extends `extract_unit_from_header`'s rule verbatim |
| `normalized` | a canonical magnitude for comparison only | maps to the existing `EVIDENCE_CLASS_NORMALIZED` (`case_workspace.py:3865`); never displayed as the fact |
| `compared` | the relationship between two normalized magnitudes | a distinct record from either side — invariant #6, *existence ≠ compliance* |

**A bare number with no stated unit stops at `stated`.** It never advances to
`parsed`. There is no drawing convention reliable enough to infer that `2400` is
millimetres, and inferring it is the same class of act `extract_unit_from_header`
already refuses to perform for table cells.

### 5.3 The origin vocabulary

Closed, derivation-owned, mirroring the grammar §4.2 basis vocabulary so the two
compose rather than compete:

| Origin | Means | Strength |
|---|---|---|
| `stated` | the source printed this magnitude and this unit | strongest |
| `converted` | arithmetically derived from a `stated` magnitude; carries its parent | strong, but **must be visually distinct** |
| `modular` | implied by a stated module and a stated count (`16" o.c. × 6`) | strong, and **must show the module, not just the product** |
| `asserted` | named in prose; not verified against a dimension string or schedule | weak — grammar §4.2's `asserted`, same rendering prohibition |
| `measured` | **reserved and prohibited** | — |

**`measured` is defined precisely so that it can be forbidden.** Per §2.6 and
`drawing_intelligence.py:12–17`, ARCHIOSK holds no calibrated relationship between
page coordinates and real-world length, and a value of this origin is therefore
unproducible today. Naming the slot and closing it is cheaper than discovering, two
stages from now, that something began emitting pixel-derived lengths under a
plausible field name. If calibration is ever built, opening this slot is a
deliberate, reviewable act.

### 5.4 Reconciliation outcomes

The result of comparing two dimensions. Closed; the evaluator names its own
outcome.

| Outcome | Means | Is it a defect? |
|---|---|---|
| `reconciled_exact` | agree within the precision both sides state | no |
| `reconciled_within_stated_tolerance` | a tolerance the **source** stated covers the difference | no |
| `precision_artifact` | differ only below the precision either side states (`2438` vs `2438.4`) | **no — must not be rendered as a finding** |
| `conversion_discrepancy` | do not agree arithmetically; one side is wrong | yes — a quantity error |
| `modular_phase_clash` | each internally correct; modules incommensurable | yes — a **coordination decision**, not a quantity error |
| `system_undeclared` | one or both sides never reached `parsed` — no stated unit | not a defect; a **gap in the record** |
| `incomparable` | different Scale Regions with no established relationship, or different subjects | no assertion made |

Three separations in that table are load-bearing:

1. **`precision_artifact` is not a finding.** Producing one is how a system trains
   its reader to ignore it. `8'-0"` is 2438.4 mm; a drawing that says `2438` has not
   disagreed with anything.
2. **`conversion_discrepancy` and `modular_phase_clash` must never render
   identically** — §3. One asks for a corrected number; the other asks for a
   decision about which module governs. A single "mismatch" badge over both is the
   fluency defect this whole document is organized against.
3. **`system_undeclared` is an honest gap, not a failure.** It reports that the
   source did not state a unit — which is itself a real, actionable observation
   about the drawing set, and frequently the more useful finding.

---

## 6. Deliverable 3 — Dimensional Reconciliation Findings in Tiers 0–2

Grammar §5.1's tiers, unchanged in structure. What follows specifies what each tier
must carry when the assertion is dimensional, and the one place where scale forces
an addition to the grammar itself (§6.3).

### 6.1 Tier 0 — the assertion and its badge

Tier 0 is the anti-fluency tier and is never optional. For a dimensional finding it
must carry the **reconciliation outcome** as a first-class badge, because the
outcome determines what kind of act the finding calls for:

```
Stud module does not align with the structural grid
[Modular clash — not a conversion error]   Machine finding · Unverified
```

**Not** this:

```
Grid spacing mismatch: 600 mm vs 406.4 mm  (Δ 193.6 mm)
```

The rejected form is the §3 lie in its natural habitat. It is shorter, more
precise, more confident, and it directs the reader to change a number that must not
be changed. It also renders `406.4` — a `converted` magnitude — in the same visual
form as `600`, a `stated` one, violating §5.1.

**`machine_confidence` stays out of Tier 0 here.** `Finding.machine_confidence`
(`case_workspace.py:1759`) is a float, and the grammar's own §9 Q3 already flags
rendering it as a percentage as a fluency risk of this family. A dimensional finding
must not compound a precision claim about the world with a precision claim about the
model's certainty. This proposal does not resolve Q3; it declines to inherit the
problem.

### 6.2 Tier 1 — contrastive, native, denominated

Grammar §6.1 requires two-sided and role-labelled; §6.2 requires a denominator.
Both apply, plus the native-system rule from §5.1:

```
Grid alignment — Level 2 partition layout

  structural grid   A-101 Level 2 Floor Plan           stated   600 mm o.c.
                    scale region: sheet @ 1:100 (sheet_absolute)    basis: read   [open]

  stud module       A-501 Details, Detail 3            stated   16" o.c.
                    scale region: detail 3 @ 1:10 (region_stated)   basis: read   [open]
                    — 16" = 406.4 mm  (converted; A-501 does not state a metric value)

  — modules coincide only at 4877 mm (8 × 600 ≈ 12 × 406.4)
  — no coincidence within the 3600 mm run dimensioned on A-101

  scope: 2 dimension strings compared, across 2 scale regions, 3 sheets examined;
         1 further dimension string on A-501 not comparable (no stated unit)
```

Four properties are required, not stylistic:

- **Each side in its native system**, with the conversion shown as a derived line
  that names what it was derived from (§5.1).
- **The governing Scale Region named on both sides, with its scope** (§4.2). Sheet
  identity is insufficient: the two sides here differ by a factor of ten in
  magnification, and a reader who does not know that cannot check the finding.
- **The coincidence interval, not the delta.** This is what makes a phase clash
  legible as a phase clash: the answer to *"where do these ever line up?"* is the
  finding's actual content.
- **The denominator, including the incomparable remainder** (grammar §6.2). A reader
  must be able to distinguish "checked and clear" from "not checked", and
  `system_undeclared` items must appear in the count rather than vanishing.

### 6.3 Tier 2 — and the constraint scale adds to the grammar

Grammar §5.1 Tier 2 is *"the document itself, at its location"*, and §6.3 requires
provenance to be LOD-invariant. Scale forces one addition the grammar does not
cover, because it never had two evidence locations at different magnifications:

> **A cross-scale Tier 2 must render each side inside its own Scale Region at that
> region's own scale, and must state the magnification difference explicitly. It
> must never silently rescale one side to match the other.**

A 1:100 plan and a 1:10 detail cannot share a magnification. Normalizing them to a
common real-world size makes one illegible and the other enormous; normalizing them
to a common on-screen size makes a 600 mm bay and a 406.4 mm stud spacing *look the
same length*. **A silently rescaled drawing is a falsified drawing** — it is the
Anti-Fluency Constraint expressed in geometry, and it is the most likely way a calm
canvas would break this.

Two further requirements follow:

- **Scale Region boundaries are LOD-invariant.** Grammar §6.3 protects the basis
  badge as a drawing zooms out; this protects the region boundary as it zooms *in*.
  A reader who magnifies into a detail callout and loses the fact that they crossed
  a scale boundary will misread every dimension inside it, and will do so
  confidently.
- **A `not_to_scale` region must remain marked at every zoom.** It is the one place
  where the source itself has prohibited the reader's next instinct.

### 6.4 What this does to the existing blanket warning

`drawing_image_viewer.js:355–358`'s sentence (§2.5) is correct and stays correct.
Under this specification it stops being one unconditional sentence per sheet and
becomes a **property of each Scale Region**, varying with scope:

| Region scope | What the reader is owed |
|---|---|
| `sheet_absolute` / `region_stated` | scale is on record, uncalibrated — stated dimensions are usable, scaled-off ones are not |
| `sheet_default` | this region may be an exception the sheet declined to locate |
| `not_to_scale` | **the source itself prohibits measurement here** — the strongest state, and currently indistinguishable from the others |
| `none_stated` | no scale on record for this area at all — stronger than today's blanket warning, not weaker |

**Note the direction of travel.** For a `none_stated` or `not_to_scale` region this
is a *stronger* warning than ships today. This specification must not be implemented
as a way to switch the disclaimer off where a scale happens to have been extracted;
a stated scale is still uncalibrated, and §7 does not move.

### 6.5 The action boundary

Grammar §6.4 applies unchanged and with an addition specific to this class. A
`modular_phase_clash` has no dimensional correction available, so the governed
action offered at Tier 1 must not be one — it is an RFI or a coordination question
addressed to whoever owns the module decision. Offering "correct the dimension" on a
finding where no dimension is wrong would use the action affordance to assert the
very thing §3 forbids.

Commit stays deliberately effortful, attributed, and companion-identified. Calm
applies to understanding; the approval gate keeps its friction.

---

## 7. The measurement boundary, as a rule rather than a limitation

> **ARCHIOSK reconciles stated dimensions. It does not measure drawings, and no
> mechanism in this specification may be implemented in a way that produces a
> magnitude from page geometry.**

Grounded in `drawing_intelligence.py:12–17` and §2.6: the geometry layer holds
normalized 0–1 fractions and no calibration. Three consequences bind any future
implementation of this document:

1. **A Scale Region is a declared area carrying a stated scale.** It is never
   derived by detecting that part of a sheet "looks like" a different scale.
2. **`measured` origin (§5.3) stays closed.** Opening it requires real calibration
   and a separate, deliberate authorization.
3. **A stated scale is not a calibration.** `1:100` in a title block tells you what
   the author intended at plot size. It tells you nothing about the PDF in front of
   you, which may have been scaled on export, cropped, or reissued at a different
   sheet size. This is why §6.4 keeps the warning even where scope is
   `sheet_absolute`.

The honest position — that the system knows what the drawing *says* and not what the
drawing *is* — is more useful than a calibrated guess would be, and is the only
position consistent with invariant #2.

---

## 8. What this proposal does not authorize

- **No implementation.** No routes, services, templates, CSS or JS are modified by
  this document, and none were touched while writing it.
- **No new durable abstraction.** Scale Regions compose from `StructuralUnit`
  nesting and `AddressableRegion` (§2.3, §4.1); genealogy extends the existing
  cell-level `raw_value`/`unit` discipline (§2.4) and reuses
  `EVIDENCE_CLASS_NORMALIZED`. What is new is **three closed vocabularies and the
  rendering rules that keep them distinct** — nothing else.
- **No measurement capability**, no calibration, no OCR, no dimension recognition.
  §7 forbids all four.
- **No weakening of the existing scale warning.** §6.4 varies it and strengthens it
  in two of four states; it never removes it.
- **No resolution of `machine_confidence` rendering** (grammar §9 Q3). §6.1 keeps it
  out of Tier 0 for this finding class and leaves the general question open.
- **No claim that any of this has been tested.** Nothing here rests on a trial. §9 is
  what a trial would have to look like.

---

## 9. The experiment that could refute this

Per grammar §7, the prediction is written down before running, so it can be wrong in
the record rather than in memory. **This is a pre-registration, not a result.**

**Claim under test:** rendering a modular phase clash *as a delta* causes readers to
propose a dimensional correction; rendering it *as a clash with a coincidence
interval* causes them to propose a module or grid decision.

**Design, following §7's own rules:**

- **Build the competing arm to win.** The delta arm gets the best version of itself
  — accurate arithmetic, clean typography, correct citations, both sides linked. If
  it loses, it must lose on substance.
- **Vary one thing.** Same fixture, same authorization path, same derivation, same
  scale-region data on both arms. **Only the Tier 0/Tier 1 rendering differs.**
- **Blind the subject.** No knowledge of which arm, that arms exist, the hypothesis,
  or the answer; no repository access.
- **Never let the stimulus contain the answer** — §7 rule 6, and the specific defect
  that permanently weakened the Arm A/B retrieval measure. The finding sentence must
  **not** contain the words "clash", "module", or "correction". The task must require
  the reader to characterize the disagreement, not repeat a characterization.
- **Check for asymmetric handicap first** — §7 rule 5. Both renderings must fit the
  same output window; the phase-clash form is longer, and a truncation limit that
  binds it and not the delta form would reproduce the exact defect that invalidated
  the first Arm A/B run.

**Measured outcome:** the *class of action* the subject proposes, not step count. Q1
(grammar §3.1) established that navigation cost is the wrong dependent variable on a
clean fixture. The question here is whether the surface changed what the reader
concluded, which is the only thing this proposal claims.

**What would refute it:** subjects reading the delta form who spontaneously identify
the incommensurability anyway. That result would mean the rendering distinction in
§6.1 is decoration, and §3 would need restating — the finding would be that
competent readers supply the modular reasoning themselves, which would be the exact
mirror of Q1's own negative result and should be reported as such.

---

## 10. Open questions this cannot settle

1. **Can a Scale Region be established at all without OCR?** §4 assumes a callout's
   scale statement is reachable as text. `drawing_intelligence.py:12–17` defers OCR,
   and detail-callout scale annotations are frequently vector or raster graphics
   rather than a `Scale:` line in a text layer. **This is the load-bearing
   feasibility risk in the entire proposal.** If detail scales are not
   text-extractable, the honest outcome is that most regions are `none_stated` —
   which is still a truthful and useful record, but a far smaller capability than §6
   depicts, and §6.4's `none_stated` row becomes the common case rather than the edge
   one.
2. **Does the coincidence interval scale?** §6.2 shows two modules on one run. Three
   or more systems across a full drawing set produce a combinatorially larger set of
   intervals, and it is not established that any of them remain legible — grammar §9
   Q2's concern, in a different dimension.
3. **Is `sheet_default` decidable from the string alone?** *"1:100 U.N.O."*,
   *"AS NOTED"*, *"VARIES"*, *"1:100 @ A1"* and *"NTS"* are five different
   statements, and only the last is unambiguous. Parsing them reliably is unproven,
   and misparsing one into `sheet_absolute` would manufacture exactly the false
   confidence §4.2 exists to prevent. A wrong scope is worse than `none_stated`.
4. **Does the `converted`/`stated` visual distinction survive a calm surface?** §5.1
   requires converted magnitudes to render differently. On a dense schedule
   comparison that may mean the majority of values carry a modifier, at which point
   the distinction stops signalling. Grammar §9 Q4's question — whether visual
   distinctness is *sufficient* for weak-basis citations — recurs here unresolved,
   and this document inherits the answer rather than providing one.

---

## Appendix — drift found while measuring, recorded not fixed

Per CLAUDE.md (*"flag and fix drift when you find it"*), stated here rather than
silently corrected in another document.

1. **`PROVENANCE_BASIS_*` does not exist in the codebase.** The interaction-grammar
   proposal cites it twice as an existing precedent — §4.2 (*"the same discipline
   `RESOLUTION_STATUS_*` and `PROVENANCE_BASIS_*` already use"*) and §8 (*"extends
   the existing `PROVENANCE_BASIS_*` shape rather than adding a parallel one"*). A
   repository-wide search finds the identifier **only in that document**. The real
   precedents for the discipline it describes are `RESOLUTION_STATUS_*`
   (`services/case_workspace.py:1177`), `METADATA_RELIABILITY_*` (line 3967) and
   `KNOWN_EVIDENCE_CLASSES` (line 3880) — all closed, all derivation-owned, all
   tested. The argument in that document is unaffected; only the citation is wrong.
   **This proposal cites the real constants throughout and does not inherit the
   error.** Correcting the grammar document is that document's own revision, not a
   silent edit from here.
2. **The scale warning is unconditional** (§2.5). It renders identically when scale
   is `unavailable` (where it is true but uninformative) and when a scale was
   extracted (where it silently undercuts the value shown two lines above it). §6.4
   specifies what it should become; nothing is changed by this document.
3. **`finding_provenance` remains absent from `main`.** Confirmed at this baseline:
   no occurrence in `services/case_workspace.py` or `templates/case_workspace.html`.
   The interaction grammar's "Read this first" is still accurate, and every §6
   rendering above is therefore specified against a surface that does not yet render
   Tier 1 for any finding class at all.
