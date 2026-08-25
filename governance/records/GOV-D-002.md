# GOV-D-002 — Task's notification scope boundary is lifted; assignment and due dates are not

- **GOVERNANCE ID:** GOV-D-002
- **TITLE:** Reconcile the earlier Task scope boundary for mobile continuation
- **TYPE:** Governance Decision Record
- **VERSION:** v1.0
- **STATUS:** CURRENT

## Authority

- **AUTHOR / PROPOSER:** Claude, under `CLAUDE-MOBILE-CONTINUATION-01`
- **APPROVING AUTHORITY:** Product Owner
- **APPROVAL DATE:** 2026-08-25
- **EFFECTIVE DATE:** on approval

Product Owner direction, 2026-08-25: *"The previous deliberate omission of
notification-related capability from Task is no longer an absolute prohibition.
However, do not implement notification delivery in this slice… Do not add
speculative notification fields merely because the prohibition has been lifted."*

## Decision question

> `Task`'s own docstring recorded that assignee, due-date **and notification**
> fields were "unauthorized by this same stage's own scope boundary". Mobile
> continuation needs `Task` to be the durable record of deferred work, and the
> Product Owner's eventual direction attaches a notification route to it.
>
> Does that earlier omission still govern, and if it is lifted, how much of it
> is lifted?

## Scope

- **GOVERNS:** The status of the earlier Task scope boundary, and what `Task`
  may accommodate in future bounded stages.
- **OUT OF SCOPE:** Notification delivery of any kind (email, push, in-app), the
  notification preference model, assignment, due dates, and any general workflow
  or task-management capability. None of those are authorized by this record.

## Options considered

| # | Option | Summary | Outcome |
|---|---|---|---|
| 1 | Lift notification only | The omission stops governing for notification; assignment and due dates stay out | **CHOSEN** |
| 2 | Lift the whole boundary | Treat the original omission as fully spent | rejected |
| 3 | Keep it, add a parallel record | Leave Task untouched and put deferral on a new object | rejected |

## Decision

> The earlier boundary no longer prohibits associating notification with `Task`.
> It continues to govern **assignment and due dates**, which remain out of scope.
>
> Lifting the prohibition is not a reason to add fields. No notification field
> is added by this record or by the stage that prompted it; the architecture is
> simply no longer forbidden from accommodating one later.

## Rationale

The original omission was a scope boundary of its own stage, not a durable
principle about what a Task may ever be — and the Product Owner, who set it, has
now narrowed it deliberately rather than by implication.

Splitting it matters. Assignment and notification are frequently conflated and
are genuinely different: assignment says who owns work, notification says who
gets told. Lifting one because the other was needed would be the kind of silent
widening this corpus's own amendment discipline exists to prevent.

Option 3 was rejected for the same reason `GOV-D-001` rejected building a
parallel path: a second object for "deferred work" would duplicate a governed
record that already carries status, provenance, anchoring, and a working route,
and would become the "unmanaged second task system" the authorizing prompt
explicitly names as a failure mode.

## Consequences

- **ACCEPTED COSTS:** A recorded scope boundary now has an exception, so a
  future reader of `Task`'s docstring must read this record too — which is why
  the docstring names it rather than being silently rewritten. And "notification
  is permitted but unbuilt" is a state that invites someone to build it without
  a further decision; the notification preference model still requires its own.
- **ENABLED:** `Task` can be the continuation record, and a later bounded stage
  can attach a notification route without first re-litigating the boundary.
- **FORECLOSED:** Nothing. Assignment and due dates were out of scope before
  this record and remain out of scope after it.

## Rejected alternatives

**Option 2 — lift the whole boundary.** Rejected as wider than the need and
wider than the direction given. *Would be worth reconsidering if* a real
requirement for assignment appears — at which point assignment deserves its own
decision, because "who owns this work" is a question about authority and
`Attention.intended_actor` already exists nearby and would need reconciling.

**Option 3 — a parallel record.** Rejected: see Rationale. *Would be worth
reconsidering if* deferred work ever needed a lifecycle `Task`'s open/completed
genuinely cannot express.

## Dependencies

- **RELATED GOVERNANCE:** `GOV-P-001` (selection is context, not authorization) —
  unchanged and load-bearing here: a deferred Task records intent and never
  licenses the deferred action. `GOV-D-001` (the bounded pre-project tier) is the
  nearest precedent for a narrow, one-purpose lifting.
- **STANDING CONTRACTS:** None changed.
- **REQUIRED IMPLEMENTATION ORDERS:** `CLAUDE-MOBILE-CONTINUATION-01`.

## Verification

- **HOW COMPLIANCE IS DEMONSTRATED:** `Task` carries no assignee, due-date or
  notification field; no delivery mechanism is reachable from the Task path; and
  a deferred Task cannot be shown to authorize its underlying action.
- **TESTS / CHECKS / ORACLES:** `tests/test_mobile_continuation_01.py`
  (`NoNotificationWasIntroduced`, `DeferringIsNotAuthorization`).

## Change control

- **REQUIRES NEW GOVERNANCE ACTION:** Adding assignment or due dates; building
  any notification delivery; adopting a notification preference model.
- **AMENDMENT / SUPERSESSION RULE:** A new `GOV-D-` superseding this one.

## Lineage

- **SUPERSEDES:** The notification clause only of the Task scope boundary
  recorded in `services/case_workspace.py`'s own `Task` docstring. The assignee
  and due-date clauses of that same boundary remain in force.
- **SUPERSEDED BY:** None.
- **RELATED DECISIONS:** `GOV-D-001`.

## Governance delta

`ADDITIVE`
