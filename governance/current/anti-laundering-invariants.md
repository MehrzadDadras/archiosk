# Core Anti-Laundering Invariants

Status: current governance principle, v1.0, 2026-09-13
Repository grounding SHA: `e937bcd65d4475716b25b1afe03639df165f0e22`
Authorizing direction: Product Owner, `ARCHIOSK — CORE ANTI-LAUNDERING INVARIANTS 01`

**BOUNDED IMPLEMENTATION AUTHORITY CREATED, FOR PLANNING & ZONING ONLY.** Unlike
the three sibling records of 2026-08-22 (`situational-attributes-are-not-authority`,
`evidence-richness-and-source-authority`,
`dependency-sufficiency-and-non-closed-basis`), this one is not reasoning-only: it
authorizes additive vocabulary on the GO-PDZ statement contract and three bounded
service modules on the Planning admission path. It authorizes **no** implementation
in RFP/Procurement, Drawing Intelligence, Document Review or Design Review, and no
placeholder code in any of them. It does not redesign GO-PDZ, does not create a
parallel canonical schema, and does not permit any plugin or model contribution to
write canonical state.

## Why these three, and why they are not constitutional amendments

`constitutional-invariants.md` states its own scope precisely: "These are rules —
timeless, context-independent statements of how BEEHIVE must behave. They are not
mechanisms, dataclasses, or field names; those live in
`current/kernel-object-model.md`." All three invariants below are **mechanisms
implementing rules that are already constitutional**, so they belong here rather
than as a proposed eighteenth entry on a list that is "deliberately not padded" and
amendable only through `governance-of-governance/amendment-and-ratification.md`.

What they implement:

| Invariant | Constitutional rule it mechanises |
|---|---|
| A — Effect Typing | #1 no silent inference or truth-promotion; #6 existence ≠ compliance |
| B — Entity-Role Binding | #3 provenance is mandatory; #1 no silent inference |
| C — Monotonic Posture Inheritance | #2 machine inference never silently becomes authority; #7 hypothetical ≠ authoritative |

The shared failure they exist to prevent has one shape. **A weaker epistemic state
is laundered into a stronger one by passing through a step that looks like
processing.** Silence becomes permission by being tabulated. A number becomes
corroborated by appearing near the right words. A speculative option becomes an
entitlement by being costed. In each case nothing lied; a boundary simply was not
typed, so it could not be checked.

## Invariant A — EFFECT TYPING

> **SILENCE IS EVIDENCE ABOUT WHAT WAS FOUND. PERMISSION IS A STATUTORY
> CONCLUSION THAT REQUIRES A GOVERNING BASIS. ARCHIOSK MUST NEVER ENCODE THE
> FIRST AS THE SECOND.**

Six statutory effects are distinguished, and the distinction is preserved end to
end — never collapsed for presentation:

    NO EVIDENCE FOUND  ≠  NO REQUIREMENT EXISTS  ≠  REQUIREMENT REMOVED  ≠  PROHIBITED

`statutory_effect` ∈ `EXPLICIT_PERMISSION`, `EXPLICIT_PROHIBITION`,
`REQUIREMENT_REMOVED`, `NOT_APPLICABLE`, `NO_EXPRESS_PROVISION`,
`UNRESOLVED_EFFECT`.

`effect_basis` ∈ `EXPRESS_TEXT`, `PARENT_REGIME_RULE`, `SITE_SPECIFIC_EXCEPTION`,
`SUPERSESSION`, `DETERMINISTIC_APPLICATION`, `UNRESOLVED`.

**There is no `SILENT_PERMITTED` primitive, and there must never be one.** A
source that says nothing licenses exactly one effect: `NO_EXPRESS_PROVISION`.
Movement from `NO_EXPRESS_PROVISION` to any stronger effect requires the governing
regime to establish that effect, recorded as the basis that establishes it.

`NO_EXPRESS_PROVISION` may itself be stated strongly — "the by-law contains no
express provision" is a finding about the record, and ARCHIOSK already proves
absences deterministically. What it may never do is speak permissively. The
distinction is between *what was found* and *what follows*.

`UNRESOLVED_EFFECT` fails closed. An effect nobody has established cannot support
an established statement.

## Invariant B — ENTITY-ROLE BINDING

> **A VALUE MATCH WITHOUT ROLE FIDELITY IS NOT CORROBORATION.**

Before a model contribution is admitted into a canonical governed result, every
consequential factual entity it asserts must bind to an authorized host-owned
source **in the correct semantic role**. Token equality is insufficient.

The worked case, from real Toronto zoning attributes:

    commercial_fsi   1.0   → COMMERCIAL_COMPONENT
    residential_fsi  1.5   → RESIDENTIAL_COMPONENT
    total_fsi_cap    2.0   → TOTAL_FSI_CAP
    component_sum    2.5   → COMPUTED_COMPONENT_SUM
    exceeds_by       0.5   → EXCEEDS_BY

A contribution asserting "the permitted FSI is 2.5" must **fail**. The value 2.5 is
genuinely present in the host findings, and that is precisely why value-set
membership cannot be the test: 2.5 is the computed sum that *breaches* the cap, and
the contribution has reported it as the cap itself. The arithmetic is right, the
provenance is right, and the meaning is inverted.

Four failure classes are detected where structured findings support them:
`UNBOUNDED_NUMERIC_CLAIM`, `ROLE_MISMATCH`, `UNBOUND_AUTHORITY_REFERENCE`,
`UNBOUND_EXCEPTION_REFERENCE`.

A failed binding **quarantines the contribution**. It preserves the raw
contribution as diagnostic evidence, does not mutate host facts, does not weaken
the canonical document, and does not by itself invalidate the document when
existing materiality policy holds the quarantined content nonmaterial.
**Confidence reduction may never be used to rescue a failed binding** — degrading
a claim's confidence so it can still be admitted is the laundering this invariant
exists to stop, performed in the open.

No universal NLP ontology is authorized. Only the entity classes Planning
currently requires are implemented.

## Invariant C — MONOTONIC POSTURE INHERITANCE

> **AUTHORITY MAY IMPROVE POSTURE. DERIVATION ALONE MAY NOT.**

Downstream derived work may preserve its parent's posture or become **more
conservative** than it. It may never silently become more authoritative.

    AS_OF_RIGHT → APPROVED_RELIEF → RELIEF_DEPENDENT → SPECULATIVE_TEST → UNSUPPORTED
    (most authoritative)                                        (most conservative)

A cost estimate, structural model, design option, procurement artifact or any
other derivation cannot upgrade posture by itself, however competent it is and
however confident it sounds. Posture improves only when an explicit governed
authority or decision event is admitted — `RELIEF_DEPENDENT → APPROVED_RELIEF`
only after a governed municipal decision enters the record, never because
something downstream assumed the relief.

`APPROVED_RELIEF` is reachable **only** through such an event. It has no
derivational path.

## What already existed, and was reused rather than duplicated

This record deliberately adds no second definition of anything the repository
already has. Established before this direction and load-bearing for it:

- **`go_pdz_contract.CLAIM_CEILINGS`** — derivation class → maximum (status,
  confidence). The precedent for a ceiling that a derivation cannot exceed, and
  the model for Invariant C. `STATUS_STRENGTH`/`CONFIDENCE_STRENGTH` already give
  the ordered-comparison idiom the posture ladder follows.
- **`go_pdz_validator` VR-21** — "a model derivation cannot promote its own claim
  strength." Invariant C for claim strength; the posture ladder is the same rule
  for derived work.
- **`go_pdz_validator` VR-19** — "every authority_ref resolves to a declared
  authority." This **is** `UNBOUND_AUTHORITY_REFERENCE`, already enforced, and is
  not reimplemented.
- **`go_pdz_validator` VR-08 / VR-20** — an unretrieved site-specific exception
  forces `UNRESOLVED` and forbids applying parent-zone standards over it. Effect
  typing's fail-closed behaviour already exists for this one case.
- **`go_pdz_validator` VR-13 / VR-14** — no prediction of a municipal approval
  decision; discretionary relief not asserted as definite pre-proposal. Posture
  doctrine in prose form, enforced on statement text.
- **`go_pdz_validator._AUTHORITY_VOICE`** — already blocks a GO interpretation
  from saying "is permitted" or "is prohibited". Invariant A's permissive-voice
  prohibition extends this to typed effects rather than replacing it.
- **`services/relation_binding.py`** — binding with fail-closed reasons, an
  attestation keyed to statement id + relation + canonical inputs, and
  `REASON_VALUES_UNBOUND` ("asserted values do not bind exactly to admitted
  facts"). Invariant B's value binding is already here; what was missing is role
  fidelity, and that is the gap this record closes.
- **`services/derivation_check.py`** — `VERIFIED`/`REFUTED`/`UNVERIFIED` with a
  hash of the inputs actually read, and declared competence that returns
  `UNVERIFIED` rather than assuming truth outside it.
- **`feasibility_compiler.MODEL_WITHHELD_FIELDS`** — the model may not set
  `derivation` or `derivation_check`. Typed effect and posture follow the same
  rule: ARCHIOSK assigns them, a contribution never asserts them.
- **The raw/governed payload split** — `go_pdz_payload` is kept exactly as it
  arrived and `governed_payload` carries ARCHIOSK's own classification. Quarantine
  needs no new preservation mechanism; this is already it.

## Conflicts found

**None requiring resolution.** No existing authoritative principle contradicts
these three; every one of them sharpens a rule already in the corpus. Two things
are recorded because they are tensions rather than conflicts:

1. **The GO-PDZ programme has no governance record at all.** A search of
   `governance/` for "GO-PDZ" returns nothing: the contract, its VR-01..VR-21
   validator, the derivation taxonomy and the claim ceilings live entirely in code
   and commit messages. That is a real gap in the corpus, and this record is
   **not** a substitute for it — it references those mechanisms without ratifying
   or restating them. Recording GO-PDZ properly remains unauthorized and open.

2. **`constitutional-invariants.md` is scoped to the BEEHIVE domain-object
   model**, and Planning & Zoning is not obviously inside that model. The mapping
   table above is therefore offered as implementation lineage, not as a claim that
   the constitution governs Planning. If the Product Owner wants Planning brought
   explicitly inside constitutional scope, that is a ratification act, not an
   inference available to this record.

## Cross-domain registration

The doctrine is registered as applicable to every domain below. **Only Planning &
Zoning is implemented.** No placeholder production code exists in the others, and
none is authorized by this record.

| Domain | Effect Typing | Entity-Role Binding | Posture Inheritance |
|---|---|---|---|
| Planning & Zoning | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED |
| RFP / Procurement | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED |
| Drawing Intelligence | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED |
| Document Review | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED |
| Design Review | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED | NOT YET IMPLEMENTED |

Planning is the proving ground because it is the only line that currently runs an
end-to-end governed path with a real authority, a deterministic verifier, an
admitted model contribution and a published result — so an invariant can be proven
here against real municipal evidence rather than asserted against a fixture.
