# Canonical Implementation Order

Status: current implementation/governance format, version 1.0  
Registry: [`contracts/README.md`](contracts/README.md)

This is ARCHIOSK's stable order format for bounded Codex implementation work.
The task changes; the inherited structure and applicable standing contracts do
not. This document is a human-readable discipline, not a runtime DSL or prompt
compiler.

## 1. SITUATION

Record the current state before editing:

- affected routes, services, pages/surfaces, and triggering observation;
- project/application context and current repository/live build, when relevant;
- constraints and known unrelated working-tree changes;
- applicable Template-Worthy IDs from the [Page/Surface Template Inventory](page-surface-template-inventory.md);
- existing governance and standing contracts.

## 2. MISSION

State one clear bounded outcome, its success evidence, and explicit non-goals.

## 3. EXECUTION

Record:

- implementation intent and required sequencing;
- `APPLICABLE GOVERNANCE` with exact ID and version — canonical `GOV-*` records the
  work must hold true (see [`../records/`](../records/) and
  [`../templates/README.md`](../templates/README.md)). Omit the heading when none applies;
- `APPLICABLE STANDING CONTRACTS` with exact ID and version;
- reference templates/patterns reviewed and selected;
- authority/context boundaries and preservation requirements;
- behavior-defining tests and stop conditions for conflicts.

UI orders must include: affected Template-Worthy IDs, reference candidates,
selected reference, intentional differences, and known parity gaps.

## 4. SUPPORT

Record applicable persistence/data, model/API and evidence/context paths,
deployment/rollback, observability, security, accessibility, migration or
backfill, test infrastructure, and operational dependencies.

## 5. COMMAND & CONTROL

Record Product Owner authority, governance delta, mutation authority,
commit/push/deploy authorization, escalation/stop conditions, repository-root
verification, reporting format, and required final acceptance evidence.

## Contract applicability and precedence

Every order must explicitly list applicable contracts, and any canonical `GOV-*`
record the work must hold true. A relevant omitted contract or governance record is
a completion finding, not an implementation convenience. A cited `GOV-*` record is
reported against on completion using the same compliance vocabulary as a contract.

Precedence is:

1. explicit current Product Owner instruction;
2. current approved governance;
3. applicable standing contract/version;
4. order-specific details;
5. implementation convenience.

If a current order conflicts with approved governance or a mandatory contract,
stop and report `GOVERNANCE DELTA: CONFLICT FOUND — STOPPED`. A Product Owner
change to a standing rule requires a new contract version and an explicit delta;
it never silently rewrites historical meaning.

## Contract compliance check

Before completion, report one result for every applicable contract:

`PASS` · `PARTIAL` · `NOT APPLICABLE` · `CONFLICT`

Include concise evidence. A mandatory invariant knowingly marked `PARTIAL` or
`CONFLICT` requires explicit Product Owner acceptance before the task is called
complete.

## Short-form order example

```text
CANONICAL IMPLEMENTATION ORDER

SITUATION
Developer Home greeting currently over-injects active CCN context.

MISSION
Make conversational salience natural without changing UI or CCN semantics.

APPLICABLE GOVERNANCE
GOV-P-001 v1.0

APPLICABLE STANDING CONTRACTS
CIC-GO-CONVERSATION v1.0
CIC-DEVELOPER-MODE v1.0
CIC-COMPOSER v1.0
CIC-REPO-SAFETY v1.0
CIC-DEPLOYMENT v1.0

EXECUTION
Correct the smallest canonical prompt/context path. Preserve model routing.

SUPPORT
Focused model-seam tests, diff check, and bounded live verification.

COMMAND & CONTROL
Bounded commit/deploy authorized. Report contract compliance and
GOVERNANCE DELTA: UNCHANGED.
```
