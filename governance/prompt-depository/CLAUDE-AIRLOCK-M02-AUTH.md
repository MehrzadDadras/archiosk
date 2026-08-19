# CLAUDE-AIRLOCK-M02-AUTH — Authorize Definition Bootstrap Mission

| Field | Value |
|---|---|
| Prompt ID | CLAUDE-AIRLOCK-M02-AUTH |
| Title | Authorize Definition Bootstrap Mission |
| Agent | Claude |
| Status | RUN |
| Purpose | Authorize External Intelligence Airlock Mission 02 — a vocabulary/bootstrap retrieval of at most five pre-authorized O. Reg. 163/24 classification definitions over the proven Mission 01A route, with deterministic location and per-item verification, one tool-less interpretation, and no canonical project effect. |
| Product Owner acceptance | Explicitly authorized by the Product Owner, 2026-08-19, for Mission 02 only; expressly not authorization for substantive Code provisions, tables, referenced provisions, Alternative Solution material, or any determination. |
| Lineage | Third bounded mission under [CLAUDE-AIRLOCK-AUTH-01](CLAUDE-AIRLOCK-AUTH-01.md), following [CLAUDE-AIRLOCK-M01A-AUTH](CLAUDE-AIRLOCK-M01A-AUTH.md) whose delivery route it reuses unchanged. Issued after the repository-grounded investigation brief the Product Owner commissioned as `CLAUDE-SRPC-OBC-BRIDGE-01`, which recommended this mission as the single first bounded Code mission; that brief is not itself registered under this contract at preservation time. Related, not absorbed: [External Intelligence Airlock](../specified-unbuilt/external-intelligence-airlock.md), [GO-EXTERNAL-VESTIBULE-01](GO-EXTERNAL-VESTIBULE-01.md), [GO-TRUST-SECURITY-01](GO-TRUST-SECURITY-01.md). |
| Superseded by | None |
| Absorbed into | None |

## Exact prompt text

<!-- Preserve verbatim. Do not summarize, normalize, or insert run results here. -->

```text
CLAUDE-AIRLOCK-M02-AUTH — Authorize Definition Bootstrap Mission

Record Product Owner authorization for exactly one new External Intelligence Airlock mission:

MISSION 02 — O. Reg. 163/24 Classification-Framework Definition Bootstrap

This authorization extends the Airlock only for this mission.

PURPOSE

Retrieve and verify the Ontario Building Code definitions needed to interpret the already-established SRPC project-side classification claims before any substantive Code provision investigation begins.

This is a vocabulary/bootstrap mission only.

AUTHORIZED REGULATION

O. Reg. 163/24 only.

Use the same deterministic official Ontario e-Laws delivery route already proven under Mission 01A.

Do not authorize another source, regulation, jurisdiction, or delivery mechanism.

AUTHORIZED TERMS

The mission may retrieve only the definition entries corresponding to these pre-authorized concepts, if they exist in the regulation’s definition structure:

1. contained use / contained-use vocabulary;
2. impeded egress / impeded-egress vocabulary;
3. high building;
4. post-disaster building;
5. major occupancy.

If the regulation uses an exact official spelling or term variant for one of these concepts, trusted deterministic parsing may bind the project phrase to that official term only where the relationship is structurally evident.

The LLM may not choose additional terms.

LOCATION DISCIPLINE

Trusted code may locate the regulation’s definition structure using deterministic:

- structural traversal;
- fixed heading/anchor text;
- verified provision labels.

The model may not choose where to look.

Do not assume all authorized terms necessarily occur in one provision.

However:

- no general search;
- no recursive discovery;
- no follow-on provision retrieval;
- no model-selected navigation.

If one authorized concept is not present in the bounded definition structure:

STOP and report it as not located.

Do not widen the mission to find it elsewhere.

INTERPRETATION

Use exactly one existing tool-less call_llm_json() interpretation.

External Code text remains untrusted input.

Deterministically verify for every returned definition:

- regulation identity;
- version/consolidation identity;
- official term identity;
- provision/location identity;
- exact quoted wording under bounded normalization;
- correspondence between requested authorized concept and returned official definition.

If any requested item fails deterministic verification:

do not admit that item.

Do not make a second LLM call.

PERSISTENCE

Successful verified items may be represented only through existing mechanisms as:

evidence_class = externally_researched_evidence
validation_status = None

Record GovernanceLog / mission trace.

Crossing the Airlock does NOT make the material project authority.

No promotion.

No ReferenceStandard admission yet.

No Project Code Profile.

No River relationship.

No Code-aware Spin.

No project compliance finding.

NO CANONICAL PROJECT MUTATION

Mission 02 must have no canonical project effect.

EXPLICITLY OUT OF SCOPE

Do not retrieve:

- substantive occupancy provisions;
- controlled-egress provisions;
- locking provisions;
- smoke-control provisions;
- HVAC provisions;
- fire-alarm provisions;
- tables;
- referenced provisions;
- Alternative Solution material;
- another regulation.

Do not determine:

- whether SRPC is a high building;
- whether B1 rules apply;
- whether detention doors must release;
- whether smoke control is required;
- whether the project complies.

Those are later governed comparisons.

STOP CONDITIONS

STOP if:

- definition structure cannot be deterministically located;
- any authorized concept requires following another provision;
- version identity becomes ambiguous;
- the route changes;
- a term is absent from the bounded definition structure;
- deterministic quote/location verification fails;
- the model proposes an unrequested term;
- more than one LLM call would be required.

A STOP may recommend the next bounded mission but may not execute it.

GOVERNANCE PRESERVATION

Before creating any new governance file, search for the existing authoritative Airlock authorization / mission-governance location.

Preserve this authorization there.

Do not create parallel governance machinery.

Preserve principles rather than implementation details.

Surface conflicts rather than overwriting existing doctrine.

FINAL REPORT

Return:

A. governance location used
B. exact authorized scope
C. prohibited scope
D. STOP conditions
E. repository changes
F. commit SHA if authorization is committed
G. HEAD / origin/main state

Then STOP.

Do not execute Mission 02.
```

## Execution references

- Run: Claude governance-only Mission 02 authorization pass, 2026-08-19; issued from synchronized `c3f6a2cf7d270f43ac7a4c42bdb9ed0f05c666d5`
- Result: `governance/specified-unbuilt/external-intelligence-airlock.md` (header status amended; `### Mission 02 — classification-framework definition bootstrap` subsection appended within the existing Mission 01 authorization section, non-destructively, including an explicit "two deliberate, bounded extensions of Mission 01A" subsection surfacing the evidence-item-count and single-provision departures rather than silently absorbing them) and `governance/STATUS.md` (Airlock prose pointer and authorization-table row extended to name Mission 02 and its scope, and the prose pointer's own former "or Mission 02" exclusion corrected so it no longer contradicts the authorization)
- Commit: recorded in the same governance-only commit that introduced this file — the commit whose parent is `c3f6a2cf7d270f43ac7a4c42bdb9ed0f05c666d5`
