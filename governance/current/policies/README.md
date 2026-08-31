# Standing Policy Registry

Status: current registry, version 1.0
Authority: [`../../constitutional-invariants.md`](../../constitutional-invariants.md)
(highest, for anything it speaks to), then
[`../canonical-implementation-order.md`](../canonical-implementation-order.md).

Policies carry standing, cross-cutting rules that are not tied to one
implementation surface. They differ from the
[standing contracts](../contracts/README.md) in subject, not in weight: a
contract governs *how a kind of work is done* and is cited by an implementation
order; a policy governs *what the system may claim, permit, or become*,
independent of which work is in progress.

A policy never outranks a constitutional invariant. Where the two overlap, the
invariant governs and the policy is the restatement.

## Registry

| Policy ID | Current version | Status | Applies when | Record |
|---|---:|---|---|---|
| POL-MULTI-MODEL-COMMAND-SAFETY | v1.0 | CURRENT | A model provider is added, swapped, or removed; a model output is proposed as a basis for action; a delivery-model risk framing is applied; or anything is transmitted outside this machine | [Record](POL-MULTI-MODEL-COMMAND-SAFETY.md) |

## Claim-status discipline

Policies in this registry mark each substantive claim **[IMPLEMENTED]**,
**[SPECIFIED-UNBUILT]**, or **[NOT CLAIMABLE]**, mirroring
`services/security_policy.py`'s `SECURITY_CLAIMS_REGISTRY`. This is a hard
requirement, not a stylistic one: a policy that reads as uniformly true while
describing partly-unbuilt behaviour becomes a source of false assurance, and is
worse than no policy at all.

Where a policy and the code's own claims registry disagree about what this
system delivers, **the registry governs and the policy is the defect.** The
registry is under test; a document is not.

## Version and supersession rule

Same as the contract registry: the index is not a replacement for the record.
Do not edit an approved rule in place — create the next version, state
`SUPERSEDES` and the semantic delta, then update this table. `SUPERSEDED BY`
links on the older record preserve the historical chain, per
[`../../governance-of-governance/amendment-and-ratification.md`](../../governance-of-governance/amendment-and-ratification.md).
