# Situational Attributes Are Not Authority

Status: current governance principle, v1.0, 2026-08-22
Repository grounding SHA: `f7756aad65c95374d1a8b0a4cf18c38ca03e2107`

**NO IMPLEMENTATION AUTHORITY CREATED. NO LANGUAGE, JURISDICTION, PROCUREMENT,
ROLE OR TRANSLATION SUBSYSTEM AUTHORIZED.**

This record changes no runtime behavior, route, schema, template, test, vocabulary,
or contract. It creates no field, engine, table, or status. **It does not touch
CLAUDE-CA1D-COMPOSER-SPINE-01 Stage 3A**, whose language-neutral residual admission
is a verified live baseline and is preserved unchanged. It adds **one reasoning
rule** that no existing record states, and it deliberately states nothing else.

## The principle

> **Authority is read from project evidence. It is never inferred from the
> circumstances in which a question was asked or a document happened to arrive.**
>
> The language a person speaks, the language a document is written in, where a
> project sits, where an organization or its past work is located, and which
> interface someone is using are **attributes of a situation**. What governs is
> established by the project's own documents — and where they establish nothing,
> the honest output is that nothing was established.

Three consequences, each the reason the rule is needed rather than a separate rule:

1. **Language-neutral access; evidence-governed linguistic authority.** A person may
   ask in any language they can express themselves in, and may be answered in it.
   Which language version of a contract *governs* is a question answered only by a
   governing-language provision in the project evidence — never by the conversation's
   language, the interface's language, the country, or bilingual availability.
2. **Parallel language versions are evidence, and their divergence is information.**
   Each version is preserved with its own provenance. Where two versions differ
   materially, the divergence is surfaced, not reconciled away, and equal authority
   is never assumed. Where no governing-language provision is found, none is
   invented and no language is privileged by default.
3. **Jurisdiction of a project, jurisdiction of experience, and governing language
   are independent attributes.** Eligibility follows the procurement criteria the
   RFP actually states. Experience from elsewhere is not inadmissible because a
   project sits somewhere, and a project's location does not restrict experience
   unless the procurement documents say so.

## Scope

- **GOVERNS:** how an authority conclusion — which version governs, what is
  eligible, what is binding — may be reached. It governs the **inference**, not
  storage, not routing, and not what may be ingested.
- **OUT OF SCOPE — already governed, deliberately not restated:**
  `constitutional-invariants.md` #2 (machine inference never silently becomes
  authority), #3 (provenance mandatory), #7, #10 (authority conflicts surface, never
  resolve silently), **#14 (perspective never alters epistemic truth)**;
  `GOV-P-001` v1.0; [`evidence-richness-and-source-authority.md`](evidence-richness-and-source-authority.md)
  (**which already settles that no format or source type carries automatic
  authority — this record is the same rule applied to situational attributes rather
  than to evidence formats**);
  [`dependency-sufficiency-and-non-closed-basis.md`](dependency-sufficiency-and-non-closed-basis.md);
  [`irregularity-interpretation-and-legibility.md`](irregularity-interpretation-and-legibility.md)
  (interpret generously, conclude conservatively; never resolve by discarding).
  **None is amended.**
- **NOT GOVERNED:** whether any language, jurisdiction, eligibility or role
  capability is ever built. This record neither authorizes nor forbids one; it
  states what must remain true if one is.

## Why the existing corpus does not already cover it

**Most of what the originating discussion raised is already in force**, and is cited
rather than restated:

| Proposition | Where it already lives |
|---|---|
| One project reality; perspective changes consequence, not truth | **Constitutional invariant #14** — *"Who is looking may change what's shown or permitted; it never changes what a Finding, Requirement, or Relationship means."* Implemented by `PerspectiveAssessment`: *"never a rewrite of the Requirement/Finding/Source it's about, never a second copy of evidence"* |
| Perspective never confers permission | `GOV-P-001` v1.0; invariant #2; `_require_approval` |
| Maturity calibrates expectation without a fixed severity table | `CIC-SPIN-INTELLIGENCE` v1.1 forbids universal LOD/percentage mapping and health scores; `KNOWN_DESIGN_MATURITY_STAGES` is *"example/canonical only… never the universal lifecycle"*; `GO-PREAWARD-ADJUDICATION-01` forbids judging a 30% submission by IFC expectations |
| Trade focus must not become an evidence silo | `Requirement.subject_domain` is open-world; `OBJECT_KIND_DISCIPLINE` is *"a maturity/expectation scope, not a stored object of its own"*; `gather_project_evidence` takes no Case and is project-wide; `select_relevant_document_evidence` biases without filtering — *"bounded retrieval never means empty retrieval"* |
| A local question does not imply a local evidence boundary; known vs unknown relationship scope | `dependency-sufficiency-and-non-closed-basis.md` |
| No fixed source-authority hierarchy | `evidence-richness-and-source-authority.md` |
| Project isolation and pre-publication blindness | Invariants #8, #9; `GO-RFP-PUBLICATION-BARRIER-01` |
| Owner / Design-Builder / trade participation | `operating_environment` (locked per project); `KNOWN_PARTICIPANT_ROLES`, open-world via `normalize_open_world_value`, so a subcontractor or trade participant is representable without a new vocabulary |

**The gap is situational attributes.** Confirmed by direct search: **no language field
exists anywhere in `services/case_workspace.py`** — nothing distinguishes the language
a person is speaking, the language a Source is written in, and the language a contract
establishes as governing. The only `jurisdiction` field in the repository belongs to
`services/security_governance.py`'s `SourcePolicy` — a security-policy attribute,
unrelated to project or contractual jurisdiction. A repository-wide search of
`governance/` for governing-language or eligibility-jurisdiction wording returns
nothing.

**The gap became live today.** Stage 3A's language-neutral residual admission is
deployed and verified: a Spanish imperative now reaches full project cognition and is
answered in Spanish, citing English-language project evidence. That is correct and is
preserved. It also means the untaken inference — *answered in French, therefore the
French version governs* — is now reachable in production for the first time. The rule
is recorded before the mistake, not after.

## Invariants

- A conclusion about which language version governs cites a governing-language
  provision in the project's own evidence, or reports that none was established.
- Every language version of a document is preserved as evidence with its own
  provenance. Material divergence between versions is surfaced; it is never resolved
  by normalization, selection, or translation.
- A translation, however produced, never becomes the authoritative source. An answer
  may be given in the reviewer's language while the authority cited remains the
  governing evidence.
- Project location, organization location, and jurisdiction of prior experience are
  recorded as the distinct facts they are, and none of them determines eligibility.
  Eligibility cites the procurement criteria actually stated.
- Where a situational attribute is unknown, it stays unknown. Absence is reported,
  never defaulted.

## Allowed variation

Deliberately broad — this constrains inference, not capability.

- Which languages the interface, the model, or the evidence pipeline support, and
  whether any language capability exists at all.
- Whether language, jurisdiction, or eligibility are ever modelled as fields, and by
  what mechanism — provided a conclusion still cites evidence.
- How an answer is presented, framed, or worded for a given reader, including in
  their own language — `PerspectiveAssessment` and invariant #14 already permit
  consequence framing to vary.
- Any project deciding, through its own governed records, that a particular version
  governs. **This rule forbids the automatic inference, not the project's own
  explicit determination.**

## Prohibited drift

- Reading this as a reason to restrict conversational language, or as authority to
  change Stage 3A. **Language-neutral admission is the verified live baseline and is
  preserved unchanged.**
- Deriving a language-authority engine, jurisdiction engine, procurement-eligibility
  engine, translation layer, language-detection subsystem, or default-language rule.
  **All are excluded.**
- Deriving a country-specific or region-specific rule of any kind. A bilingual
  jurisdiction implies nothing about which version governs.
- Treating role or perspective as a reason to reach a different factual conclusion —
  invariant #14 governs and is unchanged. Reader-adapted framing is permitted;
  reader-adapted truth is not.
- Treating a trade, discipline or CSI focus as an evidence boundary.
- Reading the downstream-vulnerability observation — that a specialty trade inherits
  accumulated ambiguity and is therefore a demanding test of whether a condition was
  understood — as licence to bias findings toward any party. **It is a test of
  completeness, never a thumb on the scale**, and it confers no authority on anyone.

## Verification

**Review-time, not automated. No test is proposed and none should be added.** A test
asserting "this authority conclusion was properly evidenced" would encode a judgement
this principle deliberately leaves to a reviewer — the same reasoning `GOV-P-002`
records for its own verification section.

Where it bites: any change that concludes what governs, what is binding, or what is
eligible, and any answer that presents a translated or reader-adapted form as the
authority.

## Conflicts surfaced, not resolved

- **No language attribute exists on `Source` or anywhere else.** A project holding
  two language versions of one document today records them as two Sources with no
  representable relationship of "same document, other language," and no place to
  record a governing-language provision. Recorded as an observed gap against working
  code. **No field is proposed and none is authorized.**
- **No project-jurisdiction or experience-jurisdiction attribute exists.** The
  independence this record requires is therefore currently preserved by absence
  rather than by structure. That is adequate today precisely because nothing infers
  from them; it would stop being adequate the moment something did.

## Relationship to existing records

- **[`evidence-richness-and-source-authority.md`](evidence-richness-and-source-authority.md)**
  v1.0 — richness increases resolution, never authority. This record is the same rule
  turned outward: *situation* never confers authority either. Its companion, not its
  restatement.
- **`constitutional-invariants.md` #14** — already governs perspective versus truth
  completely. This record adds nothing there and must not be read as strengthening or
  reinterpreting it.
- **`GO-HELIX-01` / `CIC-SPIN-INTELLIGENCE` v1.1** — maturity doctrine unchanged; no
  fixed 30/60/90/IFC severity mapping is introduced or implied.
- **`GO-RFP-PUBLICATION-BARRIER-01`** — blindness and Owner/Proponent isolation
  unchanged and unweakened.
- **`CLAUDE-CA1D-COMPOSER-SPINE-01` Stage 3A** — untouched. Access stays language-
  neutral; only the authority *inference* is constrained.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** any language, jurisdiction, eligibility or
  translation mechanism; any default-language rule; any automatic authority
  conclusion.
- **AMENDMENT RULE:** new version, never an in-place meaning edit.
- **SUPERSEDES:** None. **SUPERSEDED BY:** None.
- **GOVERNANCE DELTA:** `ADDITIVE`.

## Lineage

Stated by the Product Owner in conversation on **2026-08-22**, reconciling a recovered
earlier ARCHIOSK design conversation about subcontractor use, Owner/GC/trade
perspectives, procurement, and lifecycle. **That earlier conversation is treated as a
conceptual stress test and option inventory, not a specification**, and nothing in it
is adopted here beyond the rule stated above.

The Ottawa–Gatineau example that prompted it — subcontractor experience from other
provinces permitted at pre-contract qualification while the draft Progressive
Design-Build contract was in English — is an **illustration, not a governed case**. No
project, party, or procurement is named or implied by it, and no country-specific or
region-specific rule follows from it.

The term **"AI loyalty"**, used in that earlier conversation, is **deliberately not
adopted**. It implies interpretation bending toward whoever is logged in, which
invariant #14 already forbids. The governed formulation is *perspective-sensitive
consequence framing with evidence invariance* — and that is already in force, so this
record does not restate it.

The technical cascade proposed in that conversation — PDF/OCR/CV libraries, vector and
full-text retrieval infrastructure, model-serving stacks, background workers,
watchers, dashboards — is **option space, not authority**, and none of it is adopted,
authorized, or made more likely by this record.
