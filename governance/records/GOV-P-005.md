# GOV-P-005 — Airlock is movement; Vestibule is admission

- **GOVERNANCE ID:** GOV-P-005
- **TITLE:** Airlock is movement; Vestibule is admission
- **TYPE:** Governance Principle
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude Opus 5, resolving `MIGRATION-QUEUE.md` **MQ-P0-04**
  / `REGISTER.md` **GBC-0026**, which the back-catalog audit raised as a P0 and
  explicitly referred to the Product Owner: *"Either promote the distinction to a
  `GOV-P`, or correct the record's status."*
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-09-05
- **EFFECTIVE DATE:** 2026-09-05

## Scope

- **GOVERNS:** The relationship between two distinct boundaries that material
  originating outside a project's governed corpus must cross, wherever such
  material arrives: an outbound/inbound research route, a received procurement
  package, an uploaded document of external origin, a connector-custody Source, or
  any future channel. It governs what crossing one boundary does and does not
  establish about the other.
- **OUT OF SCOPE:** Whether any particular admission workflow may be *built* — that
  remains `GO-EXTERNAL-VESTIBULE-01` (`DEFERRED`) and `STATUS.md`. Which external
  routes are permitted, and on what mission authority — that remains the Airlock
  mission authorizations. It authorizes no new capability, no new object, no new
  surface, and does not itself admit anything.

## Principle

> An **Airlock** is a *movement* boundary: what leaves, what returns, whether it is
> executable, and whether it carries instructions aimed at the internal agent. A
> **Vestibule** is an *admission* boundary: whether material that has arrived
> carries project authority.

The governing consequence, quotable with it and reproduced verbatim from
`specified-unbuilt/external-intelligence-airlock.md`, where it was first stated:

> "An Airlock response may become vestibule material, but crossing the Airlock does
> not confer project authority or complete admission."

Stated generally, beyond the Airlock case: **arrival is not admission.** Material
reaching a project's storage, index, or surfaces has not thereby become project
truth, and no mechanism may treat successful transit as if it were a governed
decision to admit.

## Rationale

This is filed to correct a status/use contradiction the back-catalog audit found and
scored P0, not to introduce a new rule. The distinction is already load-bearing and
already relied upon:

- Four Airlock mission-authorization records invoke it — `CLAUDE-AIRLOCK-AUTH-01`,
  `CLAUDE-AIRLOCK-M01A-AUTH`, `CLAUDE-AIRLOCK-M02-AUTH` and
  `CLAUDE-AIRLOCK-WEB-RESEARCH-AUTH-01`, all `RUN`. `CLAUDE-AIRLOCK-AUTH-01`'s own
  boundary is stated in these exact terms: *"Mission 01 authorizes one Airlock
  crossing. It authorizes no admission."*
- It is implemented. `services/external_intelligence_airlock.py`'s own docstring
  states that successful material *"is stored only as externally researched,
  unvalidated evidence; nothing here promotes it into project authority"* — and
  `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED` is a member of the deliberately **closed**
  `KNOWN_EVIDENCE_CLASSES` vocabulary in `services/case_workspace.py`, whose own
  comment names it as the vocabulary *"the whole Camel programme's own 'no silent
  AI-to-authoritative promotion' discipline leans on."*

Yet until this record, the distinction existed only in two places that cannot carry
authoritative weight: a `DEFERRED` prompt record (`GO-EXTERNAL-VESTIBULE-01`) and a
`specified-unbuilt/` specification. Both are, by their own status, statements about
something not authorized and not built. **A reader arriving at either one first is
told that the distinction is future work, while four live authorizations and the
running code depend on it now.** That is the contradiction GBC-0026 named.

A second reason makes filing it now rather than later the right call.
[`GOV-P-004`](GOV-P-004.md) (Decoupled Two-Sided Procurement Foundation, `CURRENT`,
2026-09-05) states as an invariant that *"Proponent-side ingestion establishes its
own immutable snapshot baseline as a fresh `Source` with truthful provenance of the
received artifact — it never inherits the Owner project's operative truth."* That is
this principle applied at the procurement boundary: the zip arrives, and arriving is
not admission. `GOV-P-004` needs a canonical statement of the general rule to cite;
without one, the same distinction would be restated a third time, in a third place,
with the original still marked deferred.

## Invariants

- Crossing a movement boundary never confers project authority. Transit success is
  not an admission decision and may never be recorded, displayed, or relied upon as
  one.
- Material of external origin carries an evidence class that states its origin, and
  that class is drawn from a closed vocabulary. A caller naming some other
  distinction is a defect to surface, not a value to preserve.
- Admission — the act of conferring project authority on arrived material — is a
  separate, governed, human-authorized act. No automated path performs it as a side
  effect of retrieval, ingestion, storage, indexing, or display.
- Nothing may self-promote: material cannot change its own validation state, and no
  component may raise the authority of material by asserting that it is reliable.
- Provenance of arrived material is truthful about what actually arrived — the real
  artifact, its real origin, its real uncertainty — regardless of what the material
  claims about itself.
- The two boundaries stay separately identifiable. A single mechanism may implement
  both, but a record, message, or interface that collapses them into one
  "it got in, so it counts" step violates this principle.

## Allowed variation

Whether Airlock and Vestibule are one module or two; the number and naming of
transit routes; how an admission decision is presented to the person making it;
which evidence class a given origin maps to; whether admission is per-item or
batched; and every implementation detail of storage, indexing, and display. This
principle fixes the *relationship* between the two boundaries, not the mechanism
that realises either.

## Prohibited drift

- **"The Airlock is secure, therefore admitted."** Hardening the movement boundary
  never substitutes for an admission decision. The stronger the transit controls,
  the more tempting this inversion becomes.
- **"It is in the project, therefore it is project truth."** Storage location,
  visibility in a panel, or inclusion in an index confers nothing.
- **This record read as authorizing the External Source Vestibule.** It does not.
  `GO-EXTERNAL-VESTIBULE-01` remains `DEFERRED`, no admission workflow is
  authorized by this filing, and the absence of one is not a defect this record
  creates a duty to fix.
- **This record read as narrowing the Airlock mission authorizations.** Those stand
  exactly as written; this states the distinction they already relied on.
- **"External" read as "untrusted", or "internal" read as "authoritative".** The
  principle is about the *act of admission*, not about a trust score attached to an
  origin. Internally originated material is equally incapable of self-promotion.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** By the closed `KNOWN_EVIDENCE_CLASSES`
  vocabulary and its `__post_init__` validation in `services/case_workspace.py`; by
  `services/external_intelligence_airlock.py` storing only
  `EVIDENCE_CLASS_EXTERNALLY_RESEARCHED` and containing no promotion path; and by
  the continued absence of any code path that raises validation state as a
  consequence of successful retrieval or ingestion.
- **TESTS / CHECKS / ORACLES:** Partial, and better than assumed —
  `tests/test_external_intelligence_airlock_m01a.py::test_self_promotion_cannot_change_validation_state`
  is a genuine oracle for the non-promotion half, and
  `test_fabricated_citation_and_wrong_quote_store_no_evidence` guards the
  truthful-provenance half at the Airlock. **No oracle covers the general
  principle** across the other arrival channels (procurement receipt, connector
  custody, ordinary upload of externally originated material). That is a real gap;
  closing it is a `GOV-I-` record this principle does not yet have, and is related
  to the `GOV-I-` oracle `GOV-P-004` also lacks.

## Dependencies

- **RELATED GOVERNANCE:** [`GOV-P-004`](GOV-P-004.md) v1.0 (its Proponent-side
  ingestion invariant is this principle applied at the procurement boundary);
  `specified-unbuilt/external-intelligence-airlock.md` (where the distinction was
  first stated, and whose wording this record reproduces rather than rewrites);
  `prompt-depository/GO-EXTERNAL-VESTIBULE-01.md` (`DEFERRED` — the unbuilt
  admission *workflow*, unaffected by this filing);
  `prompt-depository/GO-INTAKE-FUTURE-01.md` (`DEFERRED`);
  `specified-unbuilt/camel-multimodal-programme.md` (the "no silent
  AI-to-authoritative promotion" cross-cutting requirement);
  `current/kernel-object-model.md` (implemented evidence-class and provenance
  machinery); `constitutional-invariants.md` #3 (provenance is mandatory).
- **STANDING CONTRACTS:** None changed. Any contract governing a surface on which
  external material appears may cite this record.
- **REQUIRED IMPLEMENTATION ORDERS:** None. This record changes no runtime behaviour
  and requires none to be changed.

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Any mechanism that would make admission a
  consequence of transit; any opening of the `KNOWN_EVIDENCE_CLASSES` vocabulary;
  any automated promotion of arrived material to project authority; and any reading
  that treats this record as authorization to build the External Source Vestibule.
- **AMENDMENT / SUPERSESSION RULE:** A new version via `GOV-CN-` and `GOV-S-`, never
  an in-place meaning edit.

## Lineage

- **SUPERSEDES:** None. The distinction's original statements in
  `specified-unbuilt/external-intelligence-airlock.md` and
  `GO-EXTERNAL-VESTIBULE-01` remain exactly as written; this record makes the rule
  citable at the correct authority layer rather than replacing either.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** [`GOV-D-003`](GOV-D-003.md).

## Governance delta

`ADDITIVE`
