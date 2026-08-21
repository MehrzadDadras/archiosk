# Standing Contract Registry

Status: current registry, version 1.0  
Authority: [`../canonical-implementation-order.md`](../canonical-implementation-order.md)

These contracts carry ARCHIOSK's reusable development DNA. Orders reference an
ID and exact version; they do not need to repeat the contract. Each contract is
versioned independently. A material meaning change creates a new version and
records the delta; prior orders remain interpretable against the version cited.

## Registry

| Contract ID | Current version | Status | Applies when | Record |
|---|---:|---|---|---|
| CIC-COMPOSER | v1.0 | CURRENT | Any Composer/input or conversational-surface work | [Record](CIC-COMPOSER.md) |
| CIC-GO-CONVERSATION | v1.0 | CURRENT | Any GO/model-backed conversational behavior | [Record](CIC-GO-CONVERSATION.md) |
| CIC-DEVELOPER-MODE | v1.0 | CURRENT | Developer Mode, application inspection, or Developer context | [Record](CIC-DEVELOPER-MODE.md) |
| CIC-CCN | v1.0 | CURRENT | CCN parsing, context, lifecycle, or contemplated-change work | [Record](CIC-CCN.md) |
| CIC-PAGE-TEMPLATE | v1.0 | CURRENT | Material page/surface/template or shared UI work | [Record](CIC-PAGE-TEMPLATE.md) |
| CIC-PANEL | v1.0 | CURRENT | Page composition, panel state, or nested-template work | [Record](CIC-PANEL.md) |
| CIC-SPIN-INTELLIGENCE | v1.0 | CURRENT | Spin evidence, prompts, model calls, findings, or provenance | [Record](CIC-SPIN-INTELLIGENCE.md) |
| CIC-DEPLOYMENT | v1.0 | CURRENT | Any pushed build or live deployment/verification | [Record](CIC-DEPLOYMENT.md) |
| CIC-REPO-SAFETY | v1.0 | CURRENT | Every repository change | [Record](CIC-REPO-SAFETY.md) |

## Selection rule

`CIC-REPO-SAFETY` applies to every implementation order. Add the other
contracts when the `Applies when` condition is present. Orders may add a more
specific current governance record, but may not omit a clearly applicable
contract silently. If applicability is uncertain, list the contract and mark
the compliance result `PARTIAL` pending resolution.

## Version and supersession rule

The registry is an index, not a replacement for the contract records. Do not
edit an approved invariant in place. Create the next version, state `SUPERSEDES`
and the semantic delta, then update this table. `SUPERSEDED BY` links on the
older record preserve the historical chain.

## Existing governance linkage

The contracts derive from the current Developer Mode/CCN record, the Composer
and GO prompt records, the Page/Surface Template Inventory, Spin/evidence
governance, the deployment procedure, and repository safety instructions. They
do not replace those authorities; precedence is defined by the Canonical
Implementation Order.
