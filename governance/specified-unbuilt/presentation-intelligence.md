# Specified But Unbuilt — Presentation Intelligence / Design-Intent Workflow

**Status:** Specified, not implemented. Zero code exists for anything in this document — no
PPTX/OOXML library, no conversion tooling, no dependency of any kind. Recorded under
`CLAUDE-FUTURE-PRES-A1` (2026-08-07), a repository-grounded architecture investigation performed
after the accepted Camel MM1–MM9 close-out (`d7df9a3`), the accepted CLAUDE-POSTCAMEL-P01
pilot-readiness seal (`9b4b845`), and the recorded (also unimplemented, also GO LATER)
`specified-unbuilt/voice-conversational-presence.md`. **GO LATER** — see Section 12 below for why,
and for the smallest safe future prototype.

**Relationship to the rest of this governance corpus.** This document is new; it does not
duplicate an existing one. It reuses, and does not restate, the ground-truth detail of
`StructuralUnit`/`AddressableRegion`/`EvidenceItem` (MM1), `Claim` (MM7), `Relationship`/
`Supersession` (MM1/MM6), and `WorkProduct`/`WorkProductSection` (MM8) — see
`current/kernel-object-model.md` for each. It assumes compatibility with, and does not modify,
`specified-unbuilt/voice-conversational-presence.md` (a stable per-slide `AddressableRegion` is
exactly what that document's own Anchor/Context-Envelope model already expects to resolve against)
and the still-unrecorded `CLAUDE-FUTURE-DT1-A1` Engineering Observatory conclusion (also GO LATER).

**No implementation implied.** Nothing here authorizes adding a PPTX/OOXML dependency, a document-
conversion subprocess, a new kernel domain object, or any UI surface. This document exists so a
future session does not have to re-derive this reasoning from scratch, and so no future session
treats "open a .pptx file" as the architecture, flattens every presentation statement into
"requirement," or builds a parallel governance/authority/revision system where an existing one
already applies.

---

## 1. Conceptual framing

The future capability is **Presentation Intelligence / Design-Intent Workflow**, not "PowerPoint
support." PPTX is the current industry vehicle, but the governed concept — a bidirectional,
provenance-distinct, contributor-assembled, evidence-checked communication artifact — is
format-independent, the same lesson MM1's "a source is not its filename" and MM3's "a worksheet/
row is representable via the general region mechanism" already taught this repository. Framing it
as file-format support risks building a feature around a format; framing it as Presentation
Intelligence keeps PPTX as one future `Source` kind, not the architecture.

## 2. The bidirectional procurement role

PowerPoint plays two opposite roles in Design-Build procurement, and both are real, useful
distinctions — not duplicative, not unnecessary complexity:

- **Client → Proponent** (briefing/explanatory): explains the RFP/RFQ, emphasizes priorities,
  illustrates aspirations, clarifies operational requirements — important context, but **not**
  automatically carrying the same contractual authority as RFP/RFQ text, addenda, or formal
  issued clarifications.
- **Proponent → Client** (design-intent assembly and final presentation): the pursuit team's
  collaborative response — organized by topic, assigned to disciplines/team members, progressively
  reviewed by the Design Manager, ultimately the client-facing artifact.

Direction/role should be **metadata on a generic presentation Source**, not separate object
classes — the same `Source.kind` + metadata pattern the kernel already uses elsewhere, not a new
type hierarchy.

## 3. Source authority / provenance

Preserve the principle:

> **A presentation is evidence of what someone communicated. It is not automatically evidence
> that the communication is true, current, contractually binding, or supported.**

This is already consistent with `EvidenceItem`'s own `evidence_class` vocabulary and needs **no
new authority tier**: a client-briefing statement is ordinary direct-source evidence from a
`Source` whose kind/metadata records it as a presentation, not a contract document — contractual
authority is already a property of *which* `Source`/`Requirement` a statement traces back to, not
of the presentation format. The existing Source-kind + evidence-class + `Claim`-classification
combination already distinguishes formal requirement from explanatory statement from unsupported
claim; no presentation-specific classification layer is evidenced as necessary.

## 4. Presentation Obligation — reuse `Relationship`, no new object

A Presentation Obligation ("a requirement/client-emphasis must be addressed in the presentation")
is structurally: a `Requirement` (or client-emphasis `EvidenceItem`) that a slide `EvidenceItem`
must `respond_to`/`implement` — the existing `RELATIONSHIP_TYPE_RESPONDS_TO`/
`RELATIONSHIP_TYPE_IMPLEMENTS` types, plus `resolve_relationship_status`'s existing proposed/
confirmed/disputed/stale derivation, already carry everything this concept needs, **except
assignment** (Section 6) and **except a coverage-gap query** ("which requirements have no
responding slide" — a read-time query over existing relationships, not a new object).
**Recommendation: no new kernel object; a thin query layer over existing `Relationship`s.**

## 5. Presentation Assertion — reuse `Claim`, no new object

"The design achieves X" is precisely what `Claim`'s `evidence_links` + `KNOWN_CLAIM_CLASSES` +
`resolve_claim_status` already model — an assertion is `ai_proposal`/`supported_interpretation`
until a human adopts it, `conflicting` if a contradicting relationship exists, `unknown` if
unsupported. MM7's `explain_investigation_answer` (the Trustworthy Answer Contract) already
answers "why should I trust this slide's claim" for any other evidence type; nothing about a
slide's extracted text is architecturally different from a PDF paragraph's once it is an
`EvidenceItem`. **Recommendation: no new object** — a Presentation Assertion is a `Claim` whose
anchor happens to be a slide region.

## 6. Contributor/section ownership — the one real gap

`Task` deliberately has no assignee field today (its own docstring: "Deliberately no assignee/
due-date/notification fields — those remain unauthorized by this same stage's own scope
boundary"). **This means the current architecture cannot represent "assigned to X, currently
Drafting" without new, currently-unauthorized capability.** The proposed status ladder
(Unassigned→Assigned→Drafting→Submitted→Returned→Accepted→Superseded) substantially duplicates
`WorkProduct`'s own six-state lifecycle plus `Supersession` for "Superseded" —
**recommendation: reuse the WorkProduct state machine per-section, adding only the one missing
primitive (an assignee/owner field), not a parallel state machine.** Per-section authorization
(a contributor working on their section without unrestricted authority over the whole
presentation) is genuinely new access-control scoping — existing authorization is at the
whole-Case/whole-WorkProduct level, not per-section — and should be recorded as new work, not
assumed to be free.

## 7. Template architecture

A presentation template is best modeled as **a `WorkProduct` created with a starting set of
empty/placeholder sections** (mirroring `create_work_product`'s existing `artifact_type`
parameter) — not a new "Presentation" object class, and not an imported PPTX (importing a real
client-branded template is a controlled-editing question, Section 10, not a template-architecture
question).

## 8. Navigation, Display, and cross-document intelligence

The **Document/Collection → ordered visual units → thumbnail rail → selected unit in Main
Display** pattern already exists in substance (PDF page thumbnails, drawing sheets) — a `"slide"`
`unit_type` would extend the existing thumbnail rail and multi-Display comparison mechanism
(`populateDivision`'s own `source`-kind division, already proven for drawings in MM4), not require
a new abstraction layer or a new workspace paradigm. Comparing "client slide vs. proponent slide
vs. requirement vs. risk-register row" is four existing division kinds shown together.

Cross-document intelligence (coverage gaps, unsupported claims, contradictions, stale evidence,
revision diffs) reduces entirely to **read-time queries over relationships/claims/revisions
already in the model**, mirroring MM6/MM7's own "derive at read time, never store a driftable
field" discipline — no new storage is implied.

## 9. Revision/version model

**`Supersession` is sufficient, unchanged.** A new deck upload is a new `Source` version;
`supersedes_source_id`/`register_source_revision` (already real, from MM2/MM4) already handles "a
document was revised, the old citation now resolves stale" — the identical mechanism handles a
revised deck. No PowerPoint-specific revision system should be built.

## 10. Extraction, rendering, and editing boundaries (not decided)

**Extraction priority, if ever built**: slide order, title/text-box content, and image references
first (directly feeds `EvidenceItem`/`Claim`); tables/charts next (map onto MM3's structured-cell
pattern); speaker notes/hyperlinks/master-layout/theme metadata last (visual fidelity, not
intelligence). Embedded media, OLE objects, and macros must never be extracted or executed.

**Rendering strategy is entirely unresolved and is the highest-uncertainty item in this whole
concept.** Every option (native browser OOXML rendering, server-side conversion to PDF/images, a
headless Office engine, hybrid extraction+rendered-image) is a new external dependency or a new
subprocess-execution surface — this application's running web process currently has **zero**
subprocess execution anywhere (confirmed during the companion `CLAUDE-FUTURE-DT1-A1` audit); a
conversion-tool-based path would be the first time that changes. **Must go through
`tools/dependency_fit.py` and a dedicated security review before any technology is chosen** — no
recommendation is made here beyond flagging the step.

**Editing boundary**: Levels A–C (Open/Understand/Review) are the correct target for a first
slice; controlled editing (replace text/image, add/reorder a slide) is plausible later; full
authoring competing with Microsoft PowerPoint is **not recommended at any stage**, consistent with
this repository's repeated, explicit "not a general office-document editor" boundary already
stated for Work Products (MM8) and reaffirmed at every subsequent stage's own deferral list.

## 11. Security

PPTX must be treated as fully untrusted input, exactly like every other ingested document: no
macro execution, no embedded-object activation, no following of remote-resource references,
decompression-bomb bounds on the zip container (mirroring MM3's own existing OOXML-zip
bounds-checking for `.xlsx`), and no execution of any external conversion tool without the same
sandboxing discipline any future subprocess-execution addition would need.

## 12. Compatibility with other recorded future architecture

- **Voice** (`specified-unbuilt/voice-conversational-presence.md`, GO LATER): a stable per-slide
  `AddressableRegion` id is exactly what that document's Anchor/Context-Envelope model already
  expects to resolve "this slide" against — no modification needed to either document.
- **Engineering Observatory** (`CLAUDE-FUTURE-DT1-A1`, GO LATER, not yet durably recorded as its
  own document): a future read-only Observatory would surface slide-extraction/rendering/
  coverage-query timing and errors the same way it would surface any other MM-stage diagnostic
  state — no Presentation-specific Observatory hook is needed beyond what that design already
  anticipates.

## 13. Provisional staged sequence

**PRES-1** (PPTX ingest as a new `Source.kind`, slide-as-`StructuralUnit`/`unit_type="slide"`
extraction — title/text only, no images/charts yet — thumbnail rail + Main Display reusing the
existing pattern) → **PRES-2** (structural extraction/search) → **PRES-3** (template/requirement
linkage) → **PRES-4** (contributor assignment — the one genuine new-capability gap, Section 6;
re-sequenced ahead of review/coverage stages since those are more valuable once real assignment
data exists to check against) → **PRES-5** (review/status/comments) → **PRES-6**
(requirement/evidence coverage checking) → **PRES-7** (controlled editing) → **PRES-8** (revision
comparison/provenance) → **PRES-9** (cross-document Presentation Intelligence) → **PRES-10**
(governed presentation generation/export). Numbering and staging remain provisional until real
implementation planning begins.

**Smallest useful future prototype: PRES-1 alone** — validates the rendering-strategy question
(Section 10), the single highest-uncertainty item, before any governance-adjacent work
(Obligation/Assertion/assignment) begins.

## 14. New objects genuinely required

**None as new kernel domain objects.** The only genuinely new requirement found is a **narrow
extension to `Task`** (an assignee/owner field, explicitly outside that object's current
authorized scope) to represent contributor ownership. Presentation Obligation, Presentation
Assertion, presentation status, presentation section, and slide identity are all representable by
`Relationship`, `Claim`, `WorkProduct`/`WorkProductSection` state, and `StructuralUnit.unit_type`
respectively, with no distortion of existing meaning.

## 15. Current programme decision

**GO LATER.** The conceptual architecture is unusually well-supported by primitives that already
exist and work (`Claim`, `Relationship`, `Supersession`, `WorkProduct`, multi-Display) — more so
than either the Engineering Observatory or Voice audits found for their own concepts. But the
rendering-strategy question (Section 10) is entirely unresolved and would be the first time this
codebase takes on real subprocess/external-conversion risk, and Presentation support is not
required for the accepted CLAUDE-POSTCAMEL-P01 pilot baseline. No evidence supports building
Presentation before independent pilot feedback exists on the capability already shipped.
