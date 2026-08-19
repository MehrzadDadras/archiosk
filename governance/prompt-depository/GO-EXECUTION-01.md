# GO-EXECUTION-01 — Instrument Rail — Delegated Execution Continuity

| Field | Value |
|---|---|
| Prompt ID | GO-EXECUTION-01 |
| Title | Instrument Rail — Delegated Execution Continuity |
| Agent | Unassigned (future delegated-execution continuity programme) |
| Status | DEFERRED |
| Purpose | Preserve a governed, durable, observable, and recoverable execution-continuity model for delegated work without implying unsupported background autonomy or persistence. |
| Product Owner acceptance | Confirmed future programme direction. Existing Instrument Rail work proves only bounded admin telemetry, transient Composer execution status, and a narrow live-session state bridge; durable delegated-work continuity is not implemented. |
| Lineage | Dedicated execution-continuity programme anchor. Related, not absorbed: [GO-LEADERSHIP-01](GO-LEADERSHIP-01.md), [GO-ADAPTIVE-ATTENTION-01](GO-ADAPTIVE-ATTENTION-01.md), and [GO-COMPOSER-01](GO-COMPOSER-01.md). Existing authoritative precedents remain the implemented Instrument Rail tranche documented in [Programme Status](../STATUS.md), the task and investigation model in [Kernel Object Model](../current/kernel-object-model.md), and the separately specified [Per-Item Attention/Review State Model](../specified-unbuilt/per-item-attention-review-state.md). |
| Superseded by | None |
| Absorbed into | None |

## Execution-state vocabulary

- `Active`
- `Waiting`
- `Attention Needed`
- `Stalled`
- `Detached`
- `Completed`

This is the preserved future programme vocabulary, not a claim about current runtime support. The implemented live-session bridge deliberately recognizes only a narrower evidence-confirmed vocabulary (`active`, `waiting_for_input`, and `unknown`) and explicitly does not claim stalled, detached, or completed states.

## Recovery sequence

**Observe → Diagnose → Nudge → Verify → Recover → Rehydrate**

The sequence describes governed recovery intent. Exact state transitions, retry semantics, and operational controls remain recovery-pending and unauthorized.

## Confirmed principles

- Delegated work has durable identity and state.
- The user can see what remains active, waiting, blocked, detached, or completed.
- GO distinguishes legitimate waiting from silent failure.
- Continuity survives session boundaries where the architecture genuinely permits it.
- Detached or interrupted work remains recoverable without pretending it completed.
- Results return to the originating task and context with provenance.
- Recovery avoids duplicating execution of an existing task.
- Human attention is requested when a consequential blocker cannot be resolved safely.

Where continuous or background execution is unsupported, interruption must be represented truthfully rather than simulated as persistence.

## Instrument Rail

The Instrument Rail is a compact, project-facing surface through which delegated execution state may eventually be inspected and resumed. Its exact UI remains recovery-pending; this record does not authorize a dashboard or generic task manager.

Current Instrument Rail implementation is narrower and remains authoritative for what exists today: an admin-only Operations/telemetry page, a transient Composer-adjacent “Working on your request…” status, and a narrow read-only session-state bridge. Those proofs do not provide durable delegated task identity, background recovery, or the six-state vocabulary above. The future project-facing continuity surface must not be conflated with the admin/developer machinery zone.

## Relationship to Distributed Leadership

[GO-LEADERSHIP-01](GO-LEADERSHIP-01.md) governs how work may be delegated and coordinated across actors and workstreams. Execution Continuity governs how delegated work remains alive, visible, recoverable, and returns results. Do not collapse the programmes.

## Relationship to Adaptive Attention

[GO-ADAPTIVE-ATTENTION-01](GO-ADAPTIVE-ATTENTION-01.md) may eventually help surface stalled work, consequential waiting, detached execution, or completed work requiring review. Adaptive Attention is not a prerequisite for execution continuity.

## Relationship to Composer and Tasks

[GO-COMPOSER-01](GO-COMPOSER-01.md) may surface or interact with execution state, but continuity must not exist only in transient chat history. Existing `Task`, `Investigation`, and `InvestigationStep` governance remains authoritative; current `Task` records do not carry assignee or delegation fields, and this preservation record does not alter them.

## Governance boundary

This programme does not imply unrestricted background autonomy. Every execution remains bounded by delegated scope, authority, project isolation, security, available tools, and approval gates. Recovery does not expand authority, conceal interruption, fabricate completion, or silently create duplicate work.

## Programme boundary

Do not implement background workers, execution persistence, delegated-work objects, state transitions, notifications, retry logic, or Instrument Rail UI merely because this preservation record exists.

## Recovery status

**RECOVERY PENDING:**

- original `GO-EXECUTION-01` prompt text;
- exact Instrument Rail visual design;
- full state-transition model;
- retry and recovery semantics;
- relationship to tasks and notifications;
- historical prototypes or acceptance reports;
- diagrams and implementation sequence.

Do not invent these. Later recovered material may enrich this record without replacing current task, execution, security, or Instrument Rail truth.

## Exact prompt text

```text
Delegated work must remain durable, observable, and recoverable after it has been handed off. GO should not lose track of work simply because attention moves elsewhere or a session ends.

Observe → Diagnose → Nudge → Verify → Recover → Rehydrate
```

## Execution references

- Run: None for durable delegated execution continuity
- Result: Existing Instrument Rail proof is bounded and does not implement this programme
- Commit: None
