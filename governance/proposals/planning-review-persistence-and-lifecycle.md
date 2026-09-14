# Proposal — Planning Review Persistence and Lifecycle Contract

**Status:** PROPOSAL. Architecture and governance design only. No storage was
implemented, no migration written, no store created, no model called and nothing
deployed while writing this. Nothing here amends `constitutional-invariants.md`,
`STATUS.md`, any `CIC-*` contract or any `POL-*` policy.

**Product Owner direction:** `ARCHIOSK — PLANNING REVIEW PERSISTENCE & LIFECYCLE
CONTRACT 01`. That direction authorized design and explicitly withheld
implementation.

**Repository grounding SHA:** `f5bff45` (Planning Result Workspace 02A; full gate
8,695 passed / 0 failed). Anti-laundering dependency `64ddd93`.

**The blocker this answers:** `PERSISTENCE_GOVERNANCE_REQUIRED`, returned by
Workspace 02A because iterative follow-up on a previously-rendered result cannot
be done correctly without a lifecycle contract.

---

## 0. The one finding that shapes everything else

**A Planning Review cannot be a Case, and the reason is structural rather than
stylistic.** `ProjectWorkspace` is keyed by `project_id` (`case_workspace.py:5301`)
and **116 store methods take a workspace as their first argument**. Every durable
domain record in this repository — Case, Source, Requirement, Finding,
Supersession — lives inside one. So does the whole flat-JSON store: three files
per project under `REGISTRY_STORE_PATH`, all named `{project_id}.*`.

Section 8 of the direction says a review may begin `STANDALONE` from an address
and that ARCHIOSK must **not** silently create a project. Those two facts are
incompatible with modelling a review as a Case: doing so would require a
project_id at the moment a person types an address, which is precisely the silent
project creation section 8 forbids.

Therefore the proposal is **not** "a review is a Case". It is: *a review is its
own durable object that reuses the Case model's proven semantics and its store's
proven mechanics, at application scope, and becomes project-associated later by
an explicit act.*

That is the `integration gap before architecture gap` rule from `CLAUDE.md`
applied honestly in both directions — reuse the mechanisms, do not force the
container.

---

## 1. What already exists, and is reused rather than rebuilt

Nothing below is proposed as new. Each line is a mechanism this repository
already runs, with the file that owns it.

| Need | Existing owner | Reused for |
|---|---|---|
| Write-once immutable governed artifact | `procurement_governance.write_snapshot_once` (`:293`) — `open(..., "x")`, so "the pair *is* the path, a duplicate is not a constraint that has to be checked, it is a file that already exists" | The baseline revision |
| Frozen record + tamper detection | `@dataclass(frozen=True) IssuedProcurementSnapshot` (`:183`) with `payload_sha256` and `recomputed_digest()` (`:216`) | Revision integrity |
| Canonical result hash | `feasibility_compiler.payload_hash` / `canonical_evidence` (`:304-313`) — `sha256:` over sorted-key canonical JSON | `result_hash` |
| "Archive is terminal for the OBJECT, not for the WORK" | `case_workspace.derive_case_from_archive` (`:10169`) + `RELATIONSHIP_TYPE_DERIVED_FROM` (`:462`) | Follow-up revisions |
| Frozen-state write guard | `_require_case_not_archived` (`:10065`) — "the single centralized frozen-state guard" | Refusing writes to a sealed revision |
| Two orthogonal axes, not one enum | `CASE_STATUS_OPEN`/`ARCHIVED` beside `CASE_VISIBILITY_*` (`:4388` — "ARCHIVED is NOT a fourth visibility value") | Review status vs visibility |
| Non-destructive correction | `Supersession` (`:3713`), which deliberately does **not** pick a winner among branches | Correcting a revision |
| "Superseded" derived at read time, never stored | `:799-802`, `:14560-14583` | Currentness |
| Applicability retired by checksum, not by clock | `_work_product_content_checksum` (`:12836`) — "nothing expires it, nothing has to remember to invalidate it — the checksum simply no longer matches" | Revalidation |
| Authority currentness vocabulary | `planning_authority.APPLICABILITY_CURRENT / ADOPTED_NOT_IN_FORCE / HISTORICAL / SUPERSEDED / UNKNOWN` (`:76-80`) and `go_pdz_contract.AUTHORITY_STATUSES` (`:71`) | Currentness states |
| Atomic durable write | `_replace_with_retry` (`:6463`) | Every write |
| Optimistic concurrency | `save(expected_version=…)` → `ConcurrentModificationError` (`:1347`) | Revision ordering |
| Non-governed per-project sidecar | the `_view_state/` subdirectory pattern (`:6532`) | Where a review store may live without breaking `list_ids()` |
| Append-only audit | `GovernanceLog` JSONL (`services/governance.py:64`), including an **application-scope** log | Review audit trail |
| "May this account open this" | `project_access.can_access_project` (`:33`) — the single choke point, fails closed when owner is None | Project-associated access |
| Tombstone removal, children intact | `ProjectWorkspace.removed_at/removed_by/removal_reason` (`:5456`) | Review removal |
| Byte custody, and non-custody as a state | `workspace_sources/<project_id>/<uuid4hex>_<name>` + sha256 (`ingestion.py:519`); `external_source` non-custody = `origin_type=="external_connector"` **and** `file_path is None` | User-supplied objects |
| Authorized binary serving, never `static/` | `routes/project_assets.py` over `PROJECT_ASSET_PATH` (`config.py:97` — "/static/nipigon/A204.svg answered 200 unauthenticated") | Serving a supplied object |
| Export as a governed action | `security_policy.GOVERNED_ACTIONS` includes `export` and `cross_project_reference` | Packaging and filing |
| Machine id | `case_workspace._new_id()` = uuid4 (`:1364`) | `review_id`, `revision_id` |
| Human-facing reference | `project_code.format_reference()` → `SRPC-C-006`, and `issue_reference` **returns None when no code exists** (`:171`) | Review reference, honestly absent while standalone |
| Four layers of a follow-up | `planning_contribution.layered()` | Revision content |

**Discriminator letters currently issued: `T` (Task), `C` (Case)** (`project_code.py:46-47`). `P` is free.

---

## 2. Proposed object model (§A)

Two objects. The first is thin on purpose; all the weight is in the second.

### `PlanningReview` — a stable identity and a lineage root

It is deliberately **not** a container that holds results. It holds identity,
ownership, association and a pointer to its revisions, and it is the only mutable
part of the design.

    review_id            uuid4, minted by _new_id()
    created_at, created_by
    subject_address_as_given      the words the person typed
    municipality                  resolved, or None
    owner                         a models.User.username, as ProjectWorkspace.owner is
    access_allow_list             same semantics as ProjectWorkspace.access_allow_list
    status                        open | sealed          (lifecycle axis)
    visibility                    private | shared       (audience axis — orthogonal)
    association                   standalone | project_associated
    project_id                    None until explicitly bound
    reference                     None while standalone; SRPC-P-001 once bound
    revision_ids                  ordered, append-only
    removed_at / removed_by / removal_reason      tombstone, children intact

Why `status` and `visibility` are separate fields: `case_workspace.py:4388`
already made and recorded this correction once — "ARCHIVED is NOT a fourth
visibility value … A Case can therefore be PRIVATE+ARCHIVED or
COLLABORATIVE+ARCHIVED equally validly." Repeating that mistake here would be
repeating a mistake this repository has already paid for.

### `PlanningReviewRevision` — write-once, frozen, hash-verified

Modelled directly on `IssuedProcurementSnapshot`: a frozen dataclass, one file per
identity, created with `open(..., "x")` so the filesystem enforces uniqueness, and
carrying its own digest so an out-of-band edit is detectable rather than silent.

    revision_id          uuid4
    review_id            the parent identity
    ordinal              1, 2, 3 … monotonic, never renumbered
    kind                 BASELINE | FOLLOW_UP | REVALIDATION
    created_at, created_by
    derived_from_revision_id     None for BASELINE; the parent for the others

    -- the governed result, exactly as produced --
    document             the GO-PDZ-1.0-ONEPAGE document verbatim
    result_hash          payload_hash(document)
    result_status        the document's own
    contract / schema_version / validator_version / runner_version / view_version
    retrieval            retrieved_at, source_calls, timings
    evidence_refs        authority ids + their provenance hashes
    spatial_tokens       with their geometry hashes
    authority_fingerprint        see §5 — the thing revalidation compares

    -- present only on FOLLOW_UP, and only as separate layers --
    contributions        planning_contribution records, verbatim
    follow_up            the deterministic reviews
    admission            admitted / quarantined counts and decisions
    derived_posture      the inherited posture

    revision_digest      sha256 over the canonical form of everything above

**There is deliberately no update method for a revision, anywhere.** That is the
`Snapshot` discipline stated at `case_workspace.py:5248` — "There is deliberately
no update/mutation method anywhere in this module for Snapshot" — and it is
stronger than a guard, because there is nothing to guard.

### What is NOT proposed

- **No second GO-PDZ authority model.** GO-PDZ remains the result contract; a
  revision *carries* a document and never reinterprets one.
- **No `revisions` list embedded in a mutable review record.** Embedding immutable
  content inside a mutable container would create a second immutability mechanism
  competing with write-once files, and the weaker one would win by accident.
- **No new status ladder for results.** `result_status` stays the contract's own.

---

## 3. Identity (§B)

- `review_id` and `revision_id` are uuid4 via the existing `_new_id()`. No prefix
  scheme is invented; this repository already settled that machine ids are plain
  uuid4 and that human-facing identity is a separate concern.
- **`result_hash` is `payload_hash(document)`** — the existing canonical
  `sha256:` function, not a new one.
- `ordinal` is the human-legible sequence within a review, following the
  `region_index` convention `project_code.py:30` already names: "1-based,
  per-project, per-type, assigned once at creation, never renumbered by a later
  deletion."
- **A human-facing reference exists only once a review is project-associated**,
  because `format_reference` needs a project code. Proposed:
  `REFERENCE_TYPE_PLANNING_REVIEW = "P"` → `SRPC-P-001`. While standalone, the
  reference is `None`, and that is the correct answer rather than a gap:
  `issue_reference` already "returns None when no code exists … Inventing a
  reference against a missing code would produce a string that looks
  authoritative and identifies nothing" (`project_code.py:171`).

---

## 4. Baseline immutability (§C)

**Rule.** The first live analysis of a review is written once as `ordinal 1`,
`kind = BASELINE`, and is never rewritten, amended, re-run into place, or
re-pointed. Later human interaction can only produce a *new* revision.

**Enforced by three things, in order of strength:**

1. **The filesystem.** `open(path, "x")` where the path *is* the identity. Two
   concurrent writers cannot both succeed, and there is no check-then-write race
   to lose.
2. **Absence of a write path.** No update method is written for a revision.
3. **The digest.** `revision_digest` is recomputed on read and compared, exactly
   as `recomputed_digest()` does for an issued procurement snapshot, so an edit
   made outside the application is a detected inconsistency rather than a silent
   substitution.

**What the baseline stores or references, per §3 of the direction:** the exact
document, `result_hash`, the property identity, every authority's
`authority_status` / `applicability` / `effective_date` / `version_identifier` /
`provenance_hash`, evidence refs, spatial tokens with geometry hashes, retrieval
timestamps, validator and runner versions, `result_status`, and release
eligibility as the validator reported it (`promotable`).

**One honest limitation, stated rather than discovered later.** `Snapshot`'s own
docstring already records the equivalent problem at `case_workspace.py:5272-5286`:
resolving a reference returns *current* content, so point-in-time fidelity is not
guaranteed for anything stored by reference. This design therefore stores the
GO-PDZ document **by value**, not by reference. A review that referenced live
records would silently change meaning as those records changed — which is the
laundering this whole programme exists to prevent, arriving through a storage
decision.

---

## 5. Currentness and revalidation (§D)

**Nothing expires on a clock, and no currentness value is stored.** Both of those
follow existing rules rather than preference: `superseded` is derived at read time
everywhere in this codebase (`:799-802`), and applicability is retired by checksum
mismatch rather than by expiry — "nothing expires it, nothing has to remember to
invalidate it" (`:11861`).

**The mechanism: an authority fingerprint.** Each revision stores, for every
authority it relied on, the tuple

    (authority_id, applicability, effective_date, version_identifier, provenance_hash)

canonicalised and hashed into `authority_fingerprint`. On reopen ARCHIOSK
re-reads only that **metadata** — not the geometry, not the overlays, not a full
Gate-01 run — and recomputes the fingerprint. This is a cheap read, and it is the
difference between "is what I concluded still standing on the same law" and
"analyse this address again".

**Derived states, computed on read, reusing existing vocabulary:**

| Derived state | Condition |
|---|---|
| `CURRENT` | fingerprint matches; every authority still `CURRENT` / `IN_FORCE` |
| `REVALIDATION_AVAILABLE` | fingerprint differs in a way that does not invalidate — a new `version_identifier`, a newly published amendment |
| `REVALIDATION_REQUIRED` | an authority the result relied on is now `SUPERSEDED` or `HISTORICAL`, or a site-specific exception state changed, or the parcel identity no longer resolves |
| `SUPERSEDED` | a `Supersession` record names this revision as predecessor |
| `INDETERMINATE` | the fingerprint could not be re-read (source unreachable) — **not** `CURRENT` |

The direction's `STALE_SOURCE` and `HISTORICAL` are deliberately **not** added as
new names: `stale` already exists as a derived boolean with a single resolver
(`:14560-14583`), and `HISTORICAL` already exists in `APPLICABILITY_*` as a
property of an *authority*, not of a review. Promoting an authority-level word to
a review-level status would create two meanings for one term.

`INDETERMINATE` is the one addition, and it earns its place: the failure mode it
prevents is a source timeout being rendered as "still current", which would turn
an unreachable municipal service into a silent currency claim.

---

## 6. Follow-up revisions (§E)

A contribution never edits anything. It produces a new revision with
`kind = FOLLOW_UP`, `derived_from_revision_id` pointing at the revision the person
was actually looking at, and the four layers persisted **separately** exactly as
`planning_contribution.layered()` already returns them:

    USER_INPUT              the contribution records, verbatim, classified
    GO_CONTRIBUTION         the deterministic follow-up review
    ADMISSION_DECISION      admitted / quarantined, with the binding failures
    GOVERNED_FOLLOW_UP      the governed result this revision stands behind

The baseline is referenced **by `revision_id` + `result_hash`**, never copied and
edited. So a follow-up revision can be verified against the exact baseline it was
built on, and cannot claim a baseline it did not read.

This is `derive_case_from_archive`'s rule at a different grain: copy the working
context, reference the history, do not clone the history.

**Lineage vocabulary:** `derived_from` for a follow-up (the predecessor still
stands); `Supersession` only for a *correction* — where the predecessor is no
longer the authoritative version of the same thing. `case_workspace.py:457-462`
already draws that distinction in exactly these words, and it must not be blurred
here.

---

## 7. Reopening a review (§6 of the direction)

1. **Show the stored revision first.** No municipal call, no re-analysis. What
   ARCHIOSK concluded then, with its own retrieval timestamp.
2. **Then compute currentness** from the fingerprint metadata read.
3. **Present the two as two things.** "What ARCHIOSK concluded on 13 September
   2026, from records retrieved at 12:04" beside "one authority has since been
   superseded — revalidation required". Never merged into a single present-tense
   claim.
4. **Revalidation is an explicit act that produces a new revision**
   (`kind = REVALIDATION`), never an in-place refresh.

---

## 8. Export identity (§L, and the §18 migration)

**Target behaviour.** An export names a revision and renders it:

    review_id, revision_id, ordinal, result_hash, revision_digest,
    generated_at, currentness_state (computed at export time),
    retrieval.retrieved_at, contract, validator_version

and the bytes it renders come from that stored revision. No municipal retrieval
occurs. `planning_export.build_export_document` already takes a view and a scope
and touches no reader — it is already shaped for this.

**Why it currently re-runs, and what changes.** `routes/planning_zoning.py::export_result`
re-runs the analysis today for one reason: there is nothing stored to read. That
was the honest choice among three bad ones (round-tripping the result through the
browser would have meant the host treating client bytes as host-owned facts;
inventing a store was forbidden). It is not a design; it is the shape of the
blocker.

**Migration, in order:**

1. Persist revisions (§O tranche 1). Nothing about export changes yet.
2. `export_result` gains a `revision_id` parameter and renders from the store
   when given one. The re-run path remains only for the case with no stored
   revision.
3. Once the live path always has a revision, **delete the re-run branch from the
   live path**. The fixture/preview export keeps its own no-retrieval path, which
   never re-ran anything.
4. The re-run behaviour is then gone rather than deprecated, and a test asserts
   the export route reaches no reader.

**One thing to fix at the same time, since it is the same defect:** the export
currently carries its own fresh `retrieved_at`, which differs from the page the
person was looking at. Once exports render a stored revision, the timestamp in
the file *is* the timestamp of the reviewed result, and the discrepancy the
current UI has to apologise for disappears.

---

## 9. Project association (§I)

- A review begins `STANDALONE`. **No project is created**, and nothing in the
  standalone path may call project creation.
- `SAVE TO PROJECT` is an explicit act that: sets `association =
  project_associated`, sets `project_id` to a **governed project identity the
  actor already has access to** (checked through `can_access_project` — the
  existing single choke point, not a new check), issues `SRPC-P-nnn` via
  `issue_reference`, and writes a `GovernanceLog` event.
- **Binding is one-way and non-destructive.** Unbinding is not proposed: a review
  filed into a project has been seen in that project's context, and silently
  unfiling it would be the kind of reversal invariant 12 refuses elsewhere. If a
  review was bound in error, the correction is a `Supersession`-style record, not
  an erasure.
- The application-scope record remains canonical after association. The project
  gets a **copy**, which is exactly what §9 of the direction says it is.

---

## 10. Project filing and the NAS (§J) — and a dependency that must be surfaced

**Two facts make §9's folder convention undeliverable today, and neither is a
difficulty to engineer around — both are things ARCHIOSK genuinely does not have.**

1. **ARCHIOSK does not know any project's storage root.**
   `governance/current/meta-t01-territory-before-ontology.md:58` states it plainly,
   and `STATUS.md:173` carries the same finding: "**no original external
   folder/path information has ever been captured anywhere in this codebase** (a
   browser upload gives only a filename and bytes)." The same record also warns
   against "fabricating any folder hierarchy that doesn't exist", which is exactly
   what writing to an assumed project root would be.

   **And the filing convention's own shape is not yet part of the system of
   record.** The device is committed evidence: `docs/DECISION_PROVENANCE_LEDGER.md`
   DPL-0004 records the WD My Cloud EX4100 at `\\WDMYCLOUDEX4100\Public\` — but as
   a **backup** target (`archiosk-backups`), not as a project filing tree. The
   `DAI-Cloud/<year>/<projectcode> <name>/<phase>/` layout appears only in a
   `Feasibility Studies/` corpus that is **untracked** in this working tree — a
   concurrent worker's provisional material, which `CLAUDE.md`'s system-of-record
   rule makes "real only once it lands as a pushed commit" and therefore not
   citable as project truth.

   So §9's `<Project Root>\Planning & Zoning Reviews\` cannot be specified from
   committed evidence today, and this proposal does not specify it. It proposes
   that ARCHIOSK **publish a recommended relative path inside a package manifest**
   and let a human or the private-side agent decide where the project root is —
   which is the only honest option while the root is something ARCHIOSK has never
   been told.

2. **The storage bridge cannot write.** `services/storage_bridge.py:6-9` is
   explicit that the design exists to read private storage "without SMB or port
   445 being exposed to the internet, and **without keeping the bytes**", and its
   three routes are manifest → pending → deliver: the private side speaks first
   and hands bytes *in*. There is no outbound write channel, and `:18-23` records
   that the module "holds no address, no socket, no client and no credential …
   **A test asserts the absence by AST**, because a promise that ARCHIOSK never
   dials out is worth less than a module that cannot."

**So filing a review package to `<Project Root>\Planning & Zoning Reviews\` is not
a storage feature — it is a new capability in the bridge protocol**, and it
inverts the direction the bridge was deliberately built to allow. Proposed instead,
in increasing order of what it would cost:

- **Now, with no new capability:** ARCHIOSK produces the **Review Package** as a
  downloadable artifact (§13's package), with the *recommended* relative path
  `Planning & Zoning Reviews/<review reference or ordinal>/` stated inside its
  manifest. A person or the existing private-side agent files it. ARCHIOSK
  publishes the convention; it does not perform the write.
- **Later, if authorized:** extend the bridge with a **pull** purpose — the
  private-side agent asks "is there a package for this project?" and writes it
  locally. That preserves private-side-speaks-first exactly, adds no outbound
  socket, and reuses `BridgeQueueStore`'s existing purpose vocabulary
  (`PURPOSE_REGISTER_SOURCE` / `PURPOSE_EXTRACT_TEXT` / `PURPOSE_PDF_GEOMETRY`
  → a fourth).
- **Not proposed:** ARCHIOSK mounting or writing SMB. It would contradict the
  bridge's stated design and the AST test that enforces it.

**Whichever is chosen: the project-facing copy is a copy.** The application-scope
governed review and its audit trail remain, and deleting the filed copy deletes a
copy.

---

## 11. User-supplied object custody (§F)

Three states already exist in this codebase and all three are needed:

| State | How it is expressed | When |
|---|---|---|
| **Described, not held** | a record with name, kind, byte_count, sha256 and no bytes — what Workspace 02A already produces | the default, and what is built today |
| **Held** | bytes under `REGISTRY_STORE_PATH/planning_reviews/<review_id>/objects/<uuid4hex>_<name>` + sha256, following `workspace_sources/`'s exact shape | only if byte upload is authorized |
| **Non-custody** | the `external_source` pattern: `origin_type` names the connector **and** `file_path is None` | a document that stays on the client's own storage |

Per object: `object_id` (uuid4), `supplied_by`, `submitted_at`, original filename
and declared type, `sha256`, `classification` (the existing
`planning_contribution.CLASSIFICATIONS`), `review_id` / `revision_id`,
`project_id` once associated, `authority_status` (`UNVERIFIED_BY_ARCHIOSK`, which
already exists), and `retention_state`.

**Two rules carried forward without change.** `USER_SUPPLIED_EVIDENCE` means a
person supplied an object that can be evaluated, never that its contents are
authoritative. And if bytes are ever held, they are served the way drawing sheets
are served — through an authorizing route over a non-`static/` path, because
`config.py:97` records that `/static/nipigon/A204.svg` answered 200
unauthenticated and that is the whole reason `PROJECT_ASSET_PATH` exists.

---

## 12. Ownership and access (§G)

**No new permission vocabulary.** This repository already keeps three unrelated
ones deliberately separate (`models.py:45-49`), and adding a fourth is how they
start collapsing.

| Who | Decided by |
|---|---|
| Owner of a standalone review | the review's own `owner` field, mirroring `ProjectWorkspace.owner`; **fails closed when None** — admin only, as `can_access_project:36-45` already does |
| Shared with an account | the review's `access_allow_list`, same semantics: "an allow-listed user can open the project, nothing more" (`:5444`) |
| A project-associated review | `project_access.can_access_project(project_id, …)` — the existing single choke point, called, not reimplemented |
| Project member / external stakeholder | `ProjectAccessToken` + `project_rbac`, if a review is ever exposed to a token holder. **Not proposed in this design** — a planning review is not a drawing sheet, and no token scope for it is defined |
| Admin / support | the existing `is_admin()`, and it is a **route to the record, never a bypass of currentness or of quarantine** |

**Whether an account may create a durable review at all** is an entitlement
question, and this codebase has exactly one honest answer for it today:
`auth.user_can_upload_to_storage()` currently `return True`, labelled
"Deliberately, honestly a no-op today … When a real trial/managed-plan
entitlement distinction is built, THIS function (and only this function) needs to
change" (`auth.py:103-114`). A review-creation entitlement belongs in a helper of
that same shape — one question, one owner — and not scattered across a route.

---

## 13. Retention and deletion (§H)

Five lifecycles, deliberately not identical, as the direction requires.

| Thing | Mechanism | What survives |
|---|---|---|
| **Review** | tombstone: `removed_at` / `removed_by` / `removal_reason`, children intact — `ProjectWorkspace:5450-5455`'s exact pattern | every revision, the audit log |
| **Revision** | **never deleted individually.** A revision is write-once; removing one would break the lineage another revision cites by hash | — |
| **Project-local filed copy** | freely deletable; it is a copy | the canonical review |
| **User-supplied object** | record tombstoned like `remove_source` ("never a deletion"); **bytes** may be destroyed separately, leaving the record and its sha256 | that the object existed, who supplied it, when, and its digest |
| **Audit / governance** | `GovernanceLog` is append-only JSONL and is not pruned by any of the above | everything |
| **Hard erasure** | only the existing `_delete_project_files` shape, which `routes/portal.py:1930` already labels honestly: "Deliberately NOT a governed operation … this is the opposite of a governed state change — it's erasure" | nothing, and it says so |

**There is no retention policy in this repository today** — the inventory found
none in `governance/current/`, and the only retention rule anywhere is operational
(`DEPLOYMENT.md:698`, keep 3 rollback directories). This design therefore proposes
*mechanisms with distinct lifecycles* and explicitly does **not** invent
durations. A retention period is a Product Owner and probably a legal decision,
not an architectural one.

---

## 14. Subscription offboarding (§K) — and the second surfaced dependency

**There is no subscription in ARCHIOSK.** Not deferred, not partial — absent.
`TrialAllowance` (`models.py:437`) is a per-project counter of outbound LLM calls
with "deliberately no decrement and no expiry sweep". `auth.py:103-108` states
there is "no real public-trial account/entitlement concept yet … **there is no
self-serve signup flow**". `models.User` has `is_active` but no `expires_at`,
plan, tier or subscription field.

So §13's "before account closure/expiration" has **no event to trigger on**, and
designing an offboarding hook against a lifecycle that does not exist would be
building a mechanism for a state nothing can enter.

**What can be designed now, and is worth designing now:** the **Review Package**
as a self-contained artifact that requires no ARCHIOSK subscription, no ARCHIOSK
account and no ARCHIOSK server to read — which is the actual requirement behind
the section. A directory or zip containing:

    manifest.json         review_id, revisions with ordinal/result_hash/digest,
                          currentness at packaging time, the recommended filing path
    revisions/<ordinal>-<kind>.json        each governed result, verbatim
    exports/<ordinal>.docx, .pdf           the rendered deliverables
    visuals/<ordinal>-<panel>.svg          panels, with provenance in the manifest
    contributions/                          records, classified, with digests
    objects/                                supplied bytes where held, by sha256
    evidence-index.json                     every authority, applicability, retrieval
    provenance.json                         the audit extract for this review

Word, PDF, JSON and SVG are all readable without ARCHIOSK, which satisfies "do
not require continued subscription to read exported deliverables" by construction
rather than by promise.

Packaging is already a governed action: `export` is in
`security_policy.GOVERNED_ACTIONS`, so the policy evaluation point exists.

---

## 15. Status and revision model (§14 of the direction)

The direction offers a seven-state ladder and asks to derive from existing
vocabulary and avoid proliferation. Derived, it collapses to **two stored values
and the rest computed**:

**Stored on the review:** `status ∈ {open, sealed}`. Two values, following
`CASE_STATUS_OPEN`/`ARCHIVED` rather than inventing a parallel ladder. `sealed`
is this design's word for archived-as-terminal, chosen only because `archived` is
already a Case status and reusing the string across two object kinds invites
exactly the confusion `models.py:45-49` warns about.

**Stored on each revision:** `kind ∈ {BASELINE, FOLLOW_UP, REVALIDATION}`.

**Computed, never stored:** the review's presented state.

| Direction's proposal | Resolution |
|---|---|
| `DRAFT` | not needed. A review exists once a baseline exists; before that there is nothing to store |
| `GOVERNED_RESULT` | the revision's own `result_status`, already in the contract |
| `FOLLOW_UP_IN_PROGRESS` | not a stored state. A follow-up revision is written completely or not at all — there is no half-written revision to be "in progress" |
| `UPDATED_GOVERNED_RESULT` | a later revision with a higher ordinal |
| `STALE` | derived currentness (§5) |
| `SUPERSEDED` | derived from a `Supersession` record, as everywhere else |
| `ARCHIVED` | `status = sealed` |

Seven states become two stored fields. That is the point of deriving from what
exists rather than adding to it.

---

## 16. Anti-laundering across persistence (§15)

Persistence is a new opportunity for every invariant in `64ddd93` to fail
quietly, so each is named with the thing that prevents it:

| Must never | Prevented by |
|---|---|
| Upgrade `USER_INPUT` to authority | classification is stored on the record and never recomputed; `HOST_ONLY_CLASSES` is a closed list; no store method accepts a classification change |
| Improve posture through storage | posture is stored **with its basis** (`POSTURE_BASES`), and `APPROVED_RELIEF` remains reachable only through `authorize_transition` with a governed event. Round-tripping through a file is not an authority event |
| Erase quarantine | `binding_failures` and `admission` are part of the revision's hashed content. Removing one changes `revision_digest`, which is checked on read |
| Drop provenance | evidence refs, geometry hashes and authority provenance hashes are inside the hashed content, not alongside it |
| Turn stale evidence into current authority | currentness is **derived on every read** from the stored fingerprint; there is no stored `CURRENT` value to go stale, and `INDETERMINATE` prevents an unreachable source reading as current |
| Merge baseline and follow-up invisibly | separate files, separate ordinals, separate `kind`, and the four layers separately keyed. The export carries them as four titled blocks, which Workspace 02A already does |

**One new risk this design creates, stated plainly:** a stored result is a result
that can be *shown later without being re-read*, and the further it travels from
its retrieval the more it looks like a present-tense claim. That is why
currentness is derived on every read rather than stored, why `INDETERMINATE`
exists, and why reopening shows the stored revision and its currentness as two
things. It is the single most likely way this feature launders something, and it
is a display discipline as much as a storage one.

---

## 17. Storage placement (§17)

**Canonical review records: flat JSON, at application scope.** A standalone review
has no `project_id`, so it cannot live in the project-keyed store. Proposed:

    REGISTRY_STORE_PATH/planning_reviews/<review_id>/review.json
    REGISTRY_STORE_PATH/planning_reviews/<review_id>/revisions/<ordinal>-<kind>.json
    REGISTRY_STORE_PATH/planning_reviews/<review_id>/objects/<uuid4hex>_<name>
    REGISTRY_STORE_PATH/planning_reviews/_index.json         (owner → review_ids)

**EVERY ONE OF THOSE PATHS IS INSIDE `planning_reviews/`, AND THAT IS LOAD-BEARING
RATHER THAN TIDY.** `RequirementsRegistry.list_ids()` globs `*.json` at the
registry root, relies on `Path.stem` stripping exactly one suffix level, and
excludes `CaseWorkspaceStore`'s files **by name** — `if not
p.stem.endswith(".workspace")` (`requirements_registry.py:54-62`). It is an
allow-by-exclusion list, so any *new* `*.json` at the registry root is enumerated
as a project id.

A first draft of this section put the index at
`REGISTRY_STORE_PATH/planning_reviews.index.json`, which would have appeared in
every project listing in the application as a project called
`planning_reviews.index`. Caught by reading `list_ids()` rather than trusting the
summary of it. The index therefore lives at `planning_reviews/_index.json`, and a
Tranche 1 test asserts `list_ids()` is unchanged by the presence of any review.

**Audit: `GovernanceLog`**, which already supports an application-scope log
(`application.governance.jsonl`) — so a standalone review's audit trail has a
home that exists.

**What would belong in SQLite instead, by this repository's own stated rule.**
`models.py:447-451` gives the test: something belongs in SQL when the flat-JSON
store being renamed away by Reset/Restore would silently reset it — "handing out
unlimited trial usage to anyone who noticed". Applied honestly: review *content*
must not be in SQL (it is domain data, and the flat-JSON stance is settled
policy). But if review creation is ever **metered or entitled**, that counter
belongs in SQL for exactly the `TrialAllowance` reason. Nothing else here does.

**Local-first is preserved.** The application holds the governed review and its
audit trail; the project-facing copy goes to storage the company controls; bytes
are held only if authorized, and non-custody stays available as a first-class
state. ARCHIOSK does not become the warehouse for customer project files.

**One known gap inherited, not solved:** `case_workspace.py:6509-6518` records
that the `_save_lock` is a thread lock and does **not** close the cross-process
race between gunicorn workers. Per-review files make this narrower than it is for
the shared workspace file — two people editing one review is rare where two
people touching one project is not — but it is inherited, not fixed, and the
write-once revisions are immune to it by construction while `review.json` is not.

---

## 18. Governance gaps and conflicts (§N, §16)

**Preserved, not closed:**

1. **GO-PDZ has no separately ratified governance record.** Recorded as open in
   `governance/STATUS.md` by the anti-laundering tranche. This design references
   the contract and validator as *implemented mechanisms* and ratifies nothing.
   **Does this design depend on GO-PDZ's formal authority status?** For storage,
   no — a revision stores a document and a hash, and neither needs the contract
   to be ratified. But for **release and filing**, yes: filing a Review Package
   into a client's project folder is closer to issuing a deliverable than to
   saving a draft, and `WorkProduct`'s `approved_for_issue` → `issued` ladder
   exists precisely because issuance is a governed threshold. Whether a planning
   review may be *issued* on the authority of an unratified internal contract is
   a Product Owner question, and this proposal does not answer it.

2. **`constitutional-invariants.md` is scoped to the BEEHIVE domain-object
   model.** This design reuses Case-derived semantics by *lineage*, which is not
   a claim that the constitution governs Planning.

**Newly surfaced by this design:**

3. **ARCHIOSK holds no project storage root** (`STATUS.md:173`), so §9's filing
   convention cannot be performed by ARCHIOSK today.
4. **The storage bridge is read-only by design** and a write would invert it.
5. **There is no subscription lifecycle**, so §13 has no event to hook.
6. **No retention policy exists**, so durations are deliberately unproposed.
7. **No `Organization`/tenancy concept** (`project_access.py:10-18`) — a review
   shared beyond one deployment's accounts has no model, and none is invented here.

---

## 19. Smallest implementation tranche after approval (§O)

**Tranche 1 — persist the baseline, and nothing else.** Deliberately excludes
follow-up revisions, revalidation, project association, filing, packaging and
byte custody.

- `services/planning_review.py`: the two dataclasses, `write_revision_once` on
  `procurement_governance`'s exact pattern, `read_review`, `read_revision`,
  `verify_digest`. No update method anywhere in the module.
- `PlanningReview` at application scope under `planning_reviews/`, with the
  owner-based access check failing closed on a missing owner.
- The live route writes a `BASELINE` revision after a successful analysis and
  renders from what it wrote.
- `export_result` accepts `revision_id` and renders from the store; the re-run
  branch stays only for the no-revision case.
- `GovernanceLog` events: `planning_review_created`, `planning_revision_written`.
- Tests: write-once refuses a second write at the same identity; a tampered file
  is detected by digest; the export of a stored revision is byte-identical to the
  export taken at analysis time; no update method exists (AST); a review with no
  owner is admin-only; nothing is written to the registry root.

**Why the baseline alone is the right first cut.** It is the whole of §3, it
unblocks §7 and §18 — the export stops re-running, which is the most visible
current defect — and it needs no decision about filing, packaging, custody,
entitlement or retention, every one of which has an open governance question
above it. Tranche 2 (follow-up revisions and revalidation) becomes a pure
addition once revisions exist, because the follow-up shape is already built and
tested in `planning_contribution.layered()`.

**Not in any tranche until separately authorized:** writing to the NAS, byte
upload custody, token exposure of a review, retention durations, and issuance of
a review as a deliverable.
