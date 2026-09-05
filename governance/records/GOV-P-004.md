# GOV-P-004 — Decoupled Two-Sided Procurement Foundation

- **GOVERNANCE ID:** GOV-P-004
- **TITLE:** Decoupled Two-Sided Procurement Foundation
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude Opus 5, under a direct Product Owner instruction of
  2026-09-05 to integrate this principle into the existing governance structure. No
  Prompt Register ID was issued for that instruction; the principle's wording as
  supplied is preserved verbatim under **As stated** below, so the approved text
  remains reconstructable independently of this record's own framing.
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-09-05
- **EFFECTIVE DATE:** 2026-09-05

## Scope

- **GOVERNS:** The relationship between the two procurement sides ARCHIOSK serves —
  issuance (Owner) and response (Proponent) — at every layer: product shape,
  deployment/runtime architecture, the form the boundary object takes, and how a
  later issued revision reaches a receiving side. It governs what may be assumed
  about the *other* party: their software, their infrastructure, their cooperation,
  and their continued existence.
- **OUT OF SCOPE:** Which side-specific capabilities exist and when they may be
  built — that is `STATUS.md`'s authorization table and
  `services/environment_capabilities.py`'s registry, not this record. It does not
  reach evaluation, award, scoring, or any adjudication workflow; it does not
  authorize the Neutral/Adjudication Workspace, the Experience Corpus, the Add
  Addendum facility, or a delta-ingestion mechanism, all of which remain governed by
  their own records. It does not govern multi-tenancy or organizational accounts.
  It says nothing about whether two ARCHIOSK deployments *may* be co-located — only
  that neither side's correctness may depend on it.

## Principle

> ARCHIOSK serves procurement issuance (Owner mode) and bid response (Proponent
> mode) as independent, fully isolated workflows over one shared
> evidence/supersession kernel. The boundary between the parties is the issued data
> room package — a physical artifact transferred out-of-band — never a shared
> runtime, network, application instance, or database.

Companion statement, part of this principle and quotable with it:

> Neither mode assumes or depends on the other party using ARCHIOSK.

### As stated

Preserved verbatim as approved, because the four clauses carry detail the two
sentences above compress:

> **Decoupled Two-Sided Procurement Foundation:** ARCHIOSK serves both procurement
> issuance (Owner mode) and bid response (Proponent mode) as independent, fully
> isolated workflows operating on a shared evidence/supersession kernel. The
> boundary between parties is the issued data room package, not a shared runtime or
> common database.
>
> - **Issuance (Owner):** Governs internal drafting, reconciliation, and completeness
>   testing, concluding in an export of an immutable issued baseline with
>   deterministic clause identities and provenance.
> - **Response (Proponent):** Ingests an issued data room package (standard documents
>   or structured export), establishes immutable snapshot baselines, and anchors
>   private compliance positions, evidence, assumptions, and cost impacts to stable
>   clause identities.
> - **Supersession via Delta Ingestion:** Addenda received through subsequent data
>   room updates are digested as new governed revisions that supersede prior items
>   without mutating historical records, automatically marking affected downstream
>   proponent work for review.
> - **Standalone Viability:** Neither mode assumes or depends on the other party
>   utilizing ARCHIOSK.

The approving clarification that accompanied it, equally binding:

> Owner and Proponent instances do NOT share an application, network, runtime, or
> database. They are completely decoupled entities. The boundary object between them
> is the physical data room artifact (issued documents, zip files, or structured
> exports) transferred out-of-band. Neither side assumes the other uses Archiosk.

## Rationale

`specified-unbuilt/cross-boundary-architecture.md` already settled the *project*
layer of this question, and settled it adversarially: a single shared workspace with
visibility flags was tested and rejected, because "every future feature is one bug
away from leaking confidential pre-publication owner deliberation to a bidder in an
active competition," where genuine physical separation fails safe — there is no code
path that can leak what was never in the same file.

What that document did not state is the layer *below* the project record. It
established two separate Projects; it did not say the two parties are separate
deployments with no shared infrastructure at all. That gap is not academic, and the
built work shows exactly where it bites: `CLAUDE-RFP-BOUNDARY-01`'s no-leak proof
(`tests/test_owner_proponent_isolation_01.py`) demonstrates isolation by scanning
"every file anywhere under the **shared registry storage root**." The proof is sound
and the isolation is real, but that sentence records a fact — both sides currently sit
in one deployment, over one storage root, in one process. Nothing today depends on
that co-location; without a stated rule, something eventually would, and it would be
discovered as a leak rather than as a design error.

The second failure this prevents is commercial, not technical. A two-sided product
whose value depends on both sides adopting it has no viable first customer. If Owner
mode's export only works when the receiving party runs ARCHIOSK, or Proponent mode's
ingestion only works against an ARCHIOSK-produced structured export, then neither
mode can be sold, piloted, or used alone — and the real world overwhelmingly delivers
procurement documents as a folder of PDFs from a portal, not as a peer system's API
payload. The built path already respects this by good design and should respect it by
rule: `services/procurement_publication.py`'s `build_published_package_zip` is a plain
stdlib `zipfile` of exactly the selected files, deliberately carrying no manifest, and
the Proponent side registers it through the completely unmodified
`ingest_upload`/`ingest_folder_upload` — a human moves a zip between two systems that
have never spoken to each other. That is the boundary this principle names, made
permanent.

## Invariants

- No code path on either side may require, detect, or degrade in the absence of the
  other side running ARCHIOSK.
- The Owner→Proponent boundary object is a self-describing artifact — issued
  documents, a zip, or a structured export — transferred out-of-band by a human or
  an external system. There is no synchronous call, shared network, shared file
  system, shared database, or shared identity between the two sides.
- A structured export is an *optional enrichment* of the boundary object, never a
  precondition for it. Proponent mode must fully function on ordinary documents that
  carry no ARCHIOSK-generated structure at all.
- Owner-side issuance concludes in an immutable baseline: the issued set, its clause
  identities, and its provenance are fixed at the moment of issue and are never
  mutated afterwards.
- Proponent-side ingestion establishes its own immutable snapshot baseline as a
  fresh `Source` with truthful provenance of the received artifact — it never
  inherits the Owner project's operative truth.
- Proponent-side work products — compliance positions, evidence, assumptions, cost
  impacts — anchor to stable clause identities, so that a later revision can be
  related to them rather than guessed at.
- A received addendum enters as a new governed revision with its own identity,
  superseding prior items by explicit relation. No historical record is mutated,
  overwritten, or rewritten by its arrival.
- Downstream Proponent work affected by a superseding revision is **marked for
  human review**. Marking is an attention signal only; it never re-adjudicates,
  re-answers, invalidates, or silently amends the work it marks.
- Neither side's private, pre-issue or pre-submission deliberation is reachable by
  the other under any authority, including a legal one — a compelled disclosure is
  the owning party performing its own export, never a privileged read.

## Allowed variation

The artifact's file format and packaging (zip, folder, individual documents, a
future structured export format), the transport a human or external system uses to
move it, the storage layout each side uses internally, how clause identities are
derived and represented, whether the two sides run on one machine or twenty, which
side-specific capabilities each mode exposes, the UI through which either mode is
driven, and the mechanism by which affected work is marked for review. An
implementer may freely choose any of these without new governance approval. This
principle fixes the *shape* of the boundary and the *independence* of the two modes;
it prescribes no format, no transport, and no mechanism.

Co-locating both sides in one deployment for development, demonstration, or testing
is explicitly allowed and is what the existing no-leak proof does. What is forbidden
is depending on it.

## Prohibited drift

- **"Decoupled" read as "eventually integrated."** This is not a stepping stone to a
  synchronized Owner↔Proponent link, a shared procurement database, an
  interoperability API, or a portal both parties log into. Any such proposal is new
  governance, not an implementation detail of this one.
- **"Shared evidence/supersession kernel" read as "shared data."** The kernel shared
  between the two modes is *code and semantics* — the same object model, the same
  provenance and supersession rules. It is emphatically not a shared store, a shared
  index, a shared corpus, or a shared retrieval surface. Constitutional invariants #8
  and #9 are unaffected and still bind at full strength.
- **"Structured export" read as a required interchange format.** The moment
  Proponent mode works meaningfully better on an ARCHIOSK-produced export than on a
  portal's PDFs, Standalone Viability has been lost in practice while appearing
  intact on paper. The plain-documents path is the primary path.
- **"Automatically marking affected work for review" read as automatic
  application.** It is not. `specified-unbuilt/add-addendum-facility.md` §2 item 6
  already forbids exactly this — opening or adding an addendum "must not silently
  apply amendments, alter requirements, or overwrite the governing procurement
  document" — and the Analyze → Review → Apply authority sequence stands unchanged.
  Constitutional invariants #1 (no silent mutation) and #2 (machine inference never
  silently becomes authority) govern the marking act; what is automatic is the
  *flag*, never the *conclusion*.
- **"Marked for review" read as authorization to build the marking mechanism.** It
  is not. `specified-unbuilt/per-item-attention-review-state.md` remains
  **not implemented**, and this record commissions nothing.
- **This record read as authorizing delta ingestion, the Add Addendum facility, or
  the Neutral/Adjudication Workspace.** It governs how those must behave *if and
  when* separately authorized. It authorizes none of them.
- **"Immutable issued baseline" read as a new object.** Nothing here asks for a new
  kernel primitive. `Source` revision plus `Supersession` is the mechanism
  `cross-boundary-architecture.md` already resolved for addendum lineage, and it is
  the mechanism this principle assumes.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** Structurally, and in two directions. By the
  continued *absence* from the codebase of any cross-deployment call, shared
  credential, peer-discovery, or Owner↔Proponent synchronization path — a grep-level
  fact, not a judgment. And by Proponent-side ingestion continuing to run through the
  unmodified `services/ingestion.py` entry points on ordinary uploaded documents,
  with no branch that detects or requires ARCHIOSK-produced structure.
- **TESTS / CHECKS / ORACLES:** Partial, and the gap is named rather than glossed.
  `tests/test_owner_proponent_isolation_01.py` (12 tests) proves the project-level
  no-leak property for the built slice — a planted secret in an unpublished Owner
  `Source` is asserted scoped exclusively to the Owner `project_id` across every file
  under the registry storage root. `services/procurement_publication.py`'s
  `build_published_package_zip` and `CaseWorkspaceStore.publish_procurement_package`
  (`services/case_workspace.py:6761`) are the boundary-object producers and are
  covered there. **What is not tested:** Standalone Viability itself. No check
  asserts that no code path depends on the counterparty running ARCHIOSK, and no
  check asserts that the two sides do not depend on shared infrastructure — today
  they demonstrably share a storage root in every environment that exists. That is an
  honest gap and would need a `GOV-I-` oracle it does not have. The
  Supersession-via-Delta-Ingestion invariants are unverifiable at present because the
  mechanism is unbuilt.

## Dependencies

- **RELATED GOVERNANCE:** `constitutional-invariants.md` #1 (no silent mutation), #2
  (inference is not authority), #3 (provenance mandatory), #4 (temporal validity
  explicit), #5 (correction non-destructive), #8 (project boundaries strict), #9
  (cross-boundary movement explicit and authorized), #11 (private work stays
  private) — this principle specializes #8 and #9 to the procurement boundary at the
  deployment layer and contradicts none of them;
  `specified-unbuilt/cross-boundary-architecture.md` (the resolved project-layer
  design this extends downward — its Owner/Proponent publication section, its
  addendum-lineage-is-ordinary-`Supersession` finding, and its
  legally-compelled-disclosure resolution all stand unchanged);
  `specified-unbuilt/add-addendum-facility.md` (§2 item 6 is the binding constraint
  on the Delta Ingestion clause);
  `specified-unbuilt/per-item-attention-review-state.md` (the unbuilt mechanism the
  "marked for review" clause would eventually use); `STATUS.md`'s `CLAUDE-P29`,
  `CLAUDE-P30` and `CLAUDE-RFP-BOUNDARY-01` rows (the built substrate:
  `operating_environment`, the capability registry, `lifecycle_stage`, and the
  publication act); `STATUS.md`'s own "BEEHIVE... is not inherently an Owner
  application or a Proponent application" — the sentence this record makes into a
  rule; [`GOV-P-001`](GOV-P-001.md) v1.0 (selection is context, not authorization —
  the same no-implicit-authority discipline applied to the publish act).
- **STANDING CONTRACTS:** None currently states this. `CIC-DEPLOYMENT` is the nearest
  neighbour and is unaffected — it governs how *this* repository deploys, not how two
  independent parties relate.
- **REQUIRED IMPLEMENTATION ORDERS:** None. This record changes no runtime behaviour
  and requires none to be changed. The built `CLAUDE-RFP-BOUNDARY-01` slice already
  conforms.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any synchronous, networked, or shared-storage
  link between an Owner deployment and a Proponent deployment; any dependency of
  either mode on the counterparty running ARCHIOSK; any structured export that
  becomes a precondition rather than an enrichment; any automatic application,
  re-adjudication, or invalidation of Proponent work on receipt of an addendum; and
  any reading that would collapse the two modes into one shared workspace under
  differentiated access.
- **AMENDMENT / SUPERSESSION RULE:** A new version via `GOV-CN-` and `GOV-S-`, never
  an in-place meaning edit.

## Lineage

- **SUPERSEDES:** None. `specified-unbuilt/cross-boundary-architecture.md` is
  extended, not superseded — every statement in it remains in force, and this record
  adds the deployment-layer and standalone-viability rules it left unstated.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** None.

## Governance delta

`ADDITIVE`
