"""
Project Clock / temporal reconciliation (Prompt 8 #7/#8).

Orchestrates CaseWorkspaceStore (TemporalObligation storage) and
GovernanceLog (temporal event history) the same way
conversation_interpreter.py orchestrates CaseWorkspaceStore and
drawing_analysis.py - a thin coordinating layer, not a new subsystem.

Honesty note on "Project Open": this app is a stateless Flask request
cycle with no single literal session-open moment (already established in
Prompt 5A). Reconciliation runs once per call to reconcile_project(), and
the caller decides when that is - today, once per GET
.../workspace request, the same way review_state_for_finding is
recomputed fresh on every render rather than cached.

Scope, stated plainly: this stops at recording a `temporal_condition_changed`
governance event, plus - whenever the new condition is
DUE_SOON/DUE/OVERDUE, whether or not the obligation belongs to any
Investigation Case (Prompt 9 #3) - one CLOCK_INITIATED AnalysisRun with an
empty findings list. It never creates a Finding, never touches a schedule
field, and never runs Pass/Human Adjudication/Build. See the Foundation
Batch C report for what that leaves for later.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.case_workspace import (
    ANALYSIS_TRIGGER_CLOCK_INITIATED,
    DEFAULT_DUE_SOON_WINDOW_DAYS,
    TEMPORAL_CONDITION_DUE,
    TEMPORAL_CONDITION_DUE_SOON,
    TEMPORAL_CONDITION_OVERDUE,
    TEMPORAL_OBLIGATION_STATUS_ACTIVE,
    AnalysisTrigger,
    CaseWorkspaceStore,
    ProjectWorkspace,
    evaluate_temporal_condition,
    project_clock_now,
)
from services.governance import GovernanceLog

_ACTIONABLE_CONDITIONS = {TEMPORAL_CONDITION_DUE_SOON, TEMPORAL_CONDITION_DUE, TEMPORAL_CONDITION_OVERDUE}


@dataclass
class TemporalObservation:
    obligation_id: str
    previous_condition: Optional[str]
    current_condition: str
    changed: bool
    analysis_id: Optional[str] = None


def reconcile_project(
    workspace: ProjectWorkspace,
    store: CaseWorkspaceStore,
    governance_log: GovernanceLog,
    actor: str = "project_clock",
    due_soon_window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS,
) -> list[TemporalObservation]:
    """
    Evaluates every ACTIVE Temporal Obligation's condition against the
    Project Clock. Records a `temporal_condition_changed` governance event
    only for a MEANINGFUL transition (Prompt 8 #12) - repeated calls while
    a condition stays the same (e.g. still OVERDUE) never create duplicate
    events, because "previous condition" is read back from the last such
    event already on record, not from any new stored field on the
    obligation itself (Prompt 8 #9 - the obligation does not change
    merely because time passed).

    Never mutates a TemporalObligation's dates or status here - Project
    Open must not silently mutate governed project truth (Prompt 8 #16).
    """
    now = project_clock_now()
    observations: list[TemporalObservation] = []
    existing_events = governance_log.read(workspace.project_id)

    for obligation in workspace.temporal_obligations:
        if obligation.get("status") != TEMPORAL_OBLIGATION_STATUS_ACTIVE:
            continue  # no live temporal condition to reconcile for a terminal obligation

        current_condition = evaluate_temporal_condition(obligation, now, due_soon_window_days)

        last_event = next(
            (
                e for e in reversed(existing_events)
                if e.event_type == "temporal_condition_changed" and e.correlation_id == obligation["id"]
            ),
            None,
        )
        previous_condition = last_event.payload.get("current_condition") if last_event else None
        changed = previous_condition != current_condition

        observation = TemporalObservation(
            obligation_id=obligation["id"],
            previous_condition=previous_condition,
            current_condition=current_condition,
            changed=changed,
        )
        observations.append(observation)

        if not changed:
            continue

        governance_log.append(
            project_id=workspace.project_id,
            event_type="temporal_condition_changed",
            actor=actor,
            role="system",
            payload={
                "obligation_id": obligation["id"],
                "previous_condition": previous_condition,
                "current_condition": current_condition,
            },
            trigger={
                "trigger_type": ANALYSIS_TRIGGER_CLOCK_INITIATED,
                "trigger_reference_type": "temporal_obligation",
                "trigger_reference_id": obligation["id"],
            },
            correlation_id=obligation["id"],
        )

        # Prompt 9 #3: a Project-scoped obligation (no case_id) now gets a
        # legitimate Project-level Analysis (case_id=None) instead of being
        # skipped - Batch B's limitation here is resolved by Prompt 9's
        # AnalysisRun.case_id becoming optional. No Case is fabricated
        # merely to satisfy this; findings stays empty either way, since
        # this remains an honest "something changed, worth noting" signal,
        # never a fabricated authoritative claim.
        if current_condition in _ACTIONABLE_CONDITIONS:
            trigger = AnalysisTrigger(
                trigger_type=ANALYSIS_TRIGGER_CLOCK_INITIATED,
                trigger_reference_type="temporal_obligation",
                trigger_reference_id=obligation["id"],
                triggered_by_actor=actor,
            )
            case_id = obligation.get("case_id")  # None => Project-level Analysis
            analysis = store.record_analysis(
                workspace,
                case_id=case_id,
                source_ids=[],
                objective=(
                    f"Temporal reconciliation: \"{obligation['title']}\" is now "
                    f"{current_condition.replace('_', ' ')}."
                ),
                engine_name="beehive-temporal-clock",
                engine_version="0.1.0-prototype",
                findings=[],
                trigger=trigger,
            )
            observation.analysis_id = analysis["id"]

            governance_log.append(
                project_id=workspace.project_id,
                event_type="analysis_started",
                actor=actor,
                role="system",
                payload={"case_id": case_id, "analysis_id": analysis["id"]},
                trigger={
                    "trigger_type": ANALYSIS_TRIGGER_CLOCK_INITIATED,
                    "trigger_reference_type": "temporal_obligation",
                    "trigger_reference_id": obligation["id"],
                },
                correlation_id=analysis["id"],
            )

    return observations


def open_project(
    workspace: ProjectWorkspace,
    store: CaseWorkspaceStore,
    governance_log: GovernanceLog,
    actor: str = "project_clock",
    due_soon_window_days: int = DEFAULT_DUE_SOON_WINDOW_DAYS,
) -> list[TemporalObservation]:
    """
    Prompt 9 #4: PROJECT OPEN as its own explicitly named lifecycle
    operation - the conceptual "wake up" step - kept distinct from the
    HTTP GET that happens to invoke it today. This currently delegates
    entirely to reconcile_project() (temporal reconciliation is the only
    Project-Open behavior that exists yet), but callers should call THIS
    function rather than reconcile_project() directly: the workspace
    route is only one possible caller; a future scheduled sweep or CLI
    command could call the same operation without touching the route, and
    any future Project-Open behavior beyond temporal reconciliation (a
    Source-change check, say) has one place to attach without any caller
    needing to change.

    This is a deliberately small seam, not a new web-stack architecture
    (Prompt 9 #4 explicitly asks not to over-build this): the route may
    still be the only caller for now, and that remains a safe, honest
    incremental choice - see the Batch C report's discussion of GET
    safety/idempotency/multi-user tradeoffs this does and does not solve.
    """
    return reconcile_project(workspace, store, governance_log, actor=actor, due_soon_window_days=due_soon_window_days)
