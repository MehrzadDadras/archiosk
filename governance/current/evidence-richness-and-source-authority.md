# Evidence Richness and Source Authority

Status: current governance principle, v1.0, 2026-08-22
Repository grounding SHA: `06cb88fbd4b28f171eb8e23b7f3615bf7f763bf7`

**NO IMPLEMENTATION AUTHORITY CREATED. NO REVIT/IFC IMPLEMENTATION AUTHORITY
CREATED. NO NEW ARCHITECTURE AUTHORIZED.**

This record changes no runtime behavior, route, schema, template, test, vocabulary,
or contract. It creates no connector, parser, viewer, entity graph, score, or
status. It adds **one reasoning rule** that no existing record states, and it
deliberately states nothing else.

## The principle

> **Evidence richness increases investigative resolution. It never increases
> authority.**
>
> A source that can answer more questions, in more detail, is not thereby a more
> governing source. What governs is decided by the project's own evidence and
> authority records — never by the fidelity, structure, or sophistication of the
> format a fact arrived in.

Three consequences, each the *reason* the rule is needed rather than a separate rule:

1. **The documentary baseline is a floor of capability, not a ceiling of
   authority.** Issued PDFs, specifications, addenda, schedules, reports and
   written clarifications are the evidence an ordinary Builder or subcontractor
   actually receives, and GO must be fully useful with nothing else. That makes
   them the **universal documentary baseline**. It does not make them universally
   supreme: which record governs a given condition is project-specific, and this
   record creates no precedence order in either direction.
2. **The authoring platform is provenance, not proof.** That a sheet was produced
   by a modelling tool says who made it, not that any particular condition on it is
   evidenced by the underlying model. Authored-in and derived-from are different
   claims, and only the first is established by knowing the tool.
3. **Absence of a richer source is not a finding about the poorer one.** "No model
   evidence was located" and "the issued detail is wrong" are different statements.
   The first is an abstention; the second is an assertion requiring its own
   evidence.

## Scope

- **GOVERNS:** how the format, structure or fidelity of a source may influence
  selection, confidence, precedence and reported conclusions. It governs the
  **inference from richness**, not what may be stored or ingested.
- **OUT OF SCOPE — already governed, deliberately not restated:**
  `constitutional-invariants.md` #2 (machine inference never silently becomes
  authority), #7 (hypothetical never silently becomes baseline), #14 (perspective
  never alters epistemic truth), #15 (template never masquerades as project
  authority); `GOV-P-001` v1.0;
  [`dependency-sufficiency-and-non-closed-basis.md`](dependency-sufficiency-and-non-closed-basis.md)
  (sufficiency does not transit a dependency edge — which already covers a
  geometrically resolved model sitting on an unresolved basis, and is **not**
  re-derived here); `CIC-SPIN-INTELLIGENCE` v1.1's anti-scoring invariants;
  `GO-PREAWARD-ADJUDICATION-01`'s *Evidence → Concern → Question* grammar and its
  prohibition on demanding IFC maturity at an earlier phase. **None is amended,
  widened or narrowed.**
- **NOT GOVERNED:** whether any model, CAD or connector capability is ever built.
  This record neither authorizes nor forbids one; it states what would have to
  remain true if one were.

## Why the existing corpus does not already cover it

The **deferral** is recorded in many places — `STATUS.md`, `CONTINUATION_CHECKPOINT.md`
and `camel-multimodal-programme.md` all record native DWG/DXF/RVT/IFC parsing as
**NOT AUTHORIZED**, and `kernel-object-model.md` carries an explicit
placeholder pointer to a future external-model-coordination relationship model,
named and not designed.

The **positive rule** is recorded nowhere. A repository-wide search for a PDF-first
principle, an "issued PDF is foundational" statement, or any wording separating
documentary baseline from documentary supremacy returns nothing in `governance/`.
The direction exists in conversation and as a negative (what is not built); it has
never been stated as what must remain true.

**The gap has one live edge.** `services/conversational_turn.py`'s
`_AUTHORITY_SCORE_BY_LEVEL` is the only fixed ranking of source authority anywhere
in this repository (`contractual`/`project_agreement` 3 → `indicative`/`draft` 0).
Its own comment already scopes it correctly — *"authority and relevance are
different questions; this never promotes an otherwise-irrelevant document"* — and it
is weighted ×10 against an explicit name match's ×1,000,000, so its behavioural
effect today is small and correct. **What is missing is the rule that keeps it that
way.** Nothing states that this table is retrieval ordering and must never become
governing precedence.

Confirmed by direct search: `Source.document_authority` is open-world-normalized and
has **no ordering function** in `services/` or `routes/`; there is no
`resolve_governing_source` counterpart to `current_requirement_for`; requirement
authority is per-clause (`KNOWN_REQUIREMENT_CLASSIFICATIONS`) and temporal ancestry
is supersession, not precedence. **That absence is correct and this record preserves
it.**

## Invariants

- Evidence format never determines governing authority. A structured model, a
  spreadsheet, a scanned addendum and a text-native PDF are ordered by the project's
  own authority records or not at all.
- `_AUTHORITY_SCORE_BY_LEVEL`, and any successor to it, is **retrieval relevance
  ordering only**. It must never be read, reused, or extended as a statement about
  which source governs.
- No modality is a prerequisite for value. A project with no model evidence is
  fully legitimate, and a capability that only functions when a richer source exists
  is an enrichment, never a baseline.
- Requesting richer evidence is an abstention, not a finding. The existing
  `evidence_type_insufficient` path — which already names an IFC/model source as the
  richer evidence to ask for — asserts nothing about the condition it declined to
  assess.
- Authored-in and derived-from remain distinguishable claims, and the second is
  never inferred from the first.

## Allowed variation

Deliberately broad — this constrains inference, not capability.

- Which modalities are ever supported, in what order, by what mechanism.
- Whether a future read-oriented model capability exists at all.
- How richer evidence improves resolution: finer regions, more parameters, better
  peer comparison, more precise citation — all unconstrained by this record.
- Any project deciding, through its own governed records, that a model **is** the
  governing record for some condition. This rule forbids the *automatic* inference,
  not the project's own explicit determination.

## Prohibited drift

- Reading this as "model evidence is less trustworthy." It is not. The rule is
  symmetric: richness neither raises nor lowers authority.
- Reading this as forbidding a future connector, or as authorizing one.
- Deriving a fixed source-authority matrix, a contradiction score, a provenance
  percentage, or a universal geometry-governs / specification-governs rule from any
  sentence above. **All four are explicitly excluded**, and the third is already
  forbidden in spirit by `Claim`'s deliberate refusal to carry a confidence float.
- Treating "issued from a modelling tool" as establishing that a condition is
  model-evidenced.
- Using this record to justify a `CanonicalEntity` graph. The existing
  `_MM6_ENDPOINT_LISTS` endpoint validation, `Supersession`, `Anchor` and
  `parent_structural_unit_id` already carry identity, identity-over-time,
  open-world reference and containment respectively; **no repository evidence was
  found that they are insufficient**, and none is claimed here.

## Verification

**Review-time, not automated. No test is proposed and none should be added.** A test
asserting "this conclusion did not over-credit a richer format" would encode a
judgement this principle deliberately leaves to a reviewer — the same reasoning
`GOV-P-002` records for its own verification section.

Where it bites: any change that reads a source's format, structure or authoring
environment and lets that influence precedence, confidence, or the wording of a
conclusion.

## Conflicts surfaced, not resolved

- **`_AUTHORITY_SCORE_BY_LEVEL` is a fixed universal ranking** living in the
  retrieval path. Correct today, correctly commented, and **not filed as a defect.**
  This record binds its interpretation; it does not schedule a change to it.
- **Derivation has no representational home.** Current primitives express who
  authored a *container* (`Source.issuer`/`origin_type`/`extractor_version`) and how
  reliably a *metadata value* was obtained (`METADATA_RELIABILITY_*`, five tiers
  including `unverified`). Neither answers whether a *particular region's content*
  is evidenced by an underlying model — that is a property of the representation,
  not of the file or of a metadata field. `StructuralUnit.modality_metadata` is
  already a free dict for exactly this class of modality-specific fact, and
  `parent_structural_unit_id` already nests a detail viewport under its sheet.
  **Recorded as the one conceptual gap found. No field, tier, vocabulary or schema
  is proposed, and none is authorized.**
- **`RELATIONSHIP_TYPE_SAME_SUBJECT_AS` / `COMPARES_WITH` still have no producer.**
  Already recorded in
  [`dependency-sufficiency-and-non-closed-basis.md`](dependency-sufficiency-and-non-closed-basis.md);
  **not re-derived here**, and no detector is designed or authorized.

## Relationship to existing records

- **`camel-multimodal-programme.md`** — MM1's evidence contract was built so later
  modalities are *"representable without a schema change."* `StructuralUnit.unit_type`,
  `AddressableRegion.region_type`, `EvidenceItem.content_type` and `Source.kind` are
  all open-world by design, and `SOURCE_ORIGIN_TYPE_EXTERNAL_CONNECTOR` already
  exists. **This record adds the authority rule that contract does not carry. The
  programme's own NOT AUTHORIZED deferrals are unchanged.**
- **`GO-HELIX-01`** / **`CIC-SPIN-INTELLIGENCE` v1.1** — `evidence_type_insufficient`
  and the `HELIX_ABSTAINING_ASSESSMENTS` set already implement abstention, and
  `_parse_helix_assessments` structurally refuses an asserting assessment with no
  observed evidence. **Unchanged; no Helix vocabulary is touched.**
- **`GO-RIVER-01`** — `CORRESPONDS_TO`, `DEPICTS`, `DEVIATES_FROM`, `OBSERVES` and
  `CONTRADICTS` already exist for representation-versus-condition divergence, and
  disagreement is preserved rather than collapsed. **No new relationship type and no
  generic producer.**
- **`kernel-object-model.md`** — its recorded, not-implemented external-model
  relationship placeholder remains exactly that. **Not activated, not elaborated.**
- **`GO-PREAWARD-ADJUDICATION-01`** — already prohibits demanding IFC maturity at an
  earlier phase and already governs observation before solution. **Not restated.**

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** any precedence mechanism, authority ordering,
  derivation vocabulary, connector, scoring model, or automatic action.
- **AMENDMENT RULE:** new version, never an in-place meaning edit.
- **SUPERSEDES:** None. **SUPERSEDED BY:** None.
- **GOVERNANCE DELTA:** `ADDITIVE`.

## Lineage

Stated by the Product Owner in conversation on **2026-08-22**, from a design
discussion about surviving real-world evidence disorder and about whether a future
read-oriented Revit/IFC capability could remain optional. The framing appears
nowhere else in this repository; **no earlier provenance is claimed and none was
found by search.**

The same discussion proposed a three-layer evidence model, a four-case
representation/model comparison matrix, dirty-BIM detection conditions, and a
"queryable epistemic probe." **None of them is adopted, named, or made vocabulary
by this record** — each was tested against the repository and found either already
representable with existing primitives or deliberately unbuilt. The four comparison
cases in particular are **not** canonized: they remain reasoning cases, and no
quadrant, status, or classification follows from them.

**The PDF/documentary smoke test remains the next product validation baseline.** The
Builder corpus at `tests/fixtures/psd/builder_corpus/` and the private oracle at
`tests/fixtures/psd/oracle/` are untouched by this record and no model evidence is
added to either.
