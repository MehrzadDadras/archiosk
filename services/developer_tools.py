"""Bounded, admin/developer-only project reset operations.

These operations deliberately reuse the flat-file ProjectWorkspace and
GovernanceLog primitives. They do not introduce a second project lifecycle or
analysis store. Source bytes and source-derived evidence remain outside both
reset contracts.
"""
from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from services.case_workspace import CaseWorkspaceStore, ProjectWorkspace
from services.governance import GovernanceLog


# A test reset is intentionally limited to the established synthetic PSD
# identity convention; arbitrary production projects cannot qualify merely by
# being selected from an admin list.
_SYNTHETIC_MARKERS = ("synthetic", "test project", "fixture", "project smoke detector", "(psd)")

# Source identity, source-derived structure/evidence, current authority and
# project presentation/access state are preserved by the deep reset.
_TEST_RESET_PRESERVE = {
    "project_id", "version", "sources", "folders", "structural_units",
    "addressable_regions", "evidence_items", "derived_observations",
    "supersessions", "security_profile", "security_profile_set_by",
    "security_profile_set_at", "owner", "owner_set_by", "owner_set_at",
    "access_allow_list", "operating_environment", "operating_environment_set_by",
    "operating_environment_set_at", "lifecycle_stage", "lifecycle_stage_set_by",
    "lifecycle_stage_set_at", "removed_at", "removed_by", "removal_reason",
    "starred", "last_viewed_by", "item_reviewed_at", "display_title",
    "display_description", "operating_instructions", "operating_instructions_updated_by",
    "operating_instructions_updated_at", "operating_instructions_updated_by_role",
}


def _state_lists(workspace: ProjectWorkspace) -> list[str]:
    """Return list-valued workspace fields eligible for analytical reset."""
    return [
        name for name, value in asdict(workspace).items()
        if isinstance(value, list) and name not in {"sources", "folders", "structural_units", "addressable_regions", "evidence_items", "derived_observations"}
    ]


def qualifies_as_synthetic_test_project(workspace: ProjectWorkspace) -> bool:
    """Require an explicit synthetic/test identity before deep reset."""
    text = " ".join(
        str(value or "")
        for value in (workspace.display_title, workspace.display_description, workspace.operating_instructions)
    ).lower()
    return any(marker in text for marker in _SYNTHETIC_MARKERS)


def _reset_lists(workspace: ProjectWorkspace, names: list[str]) -> dict[str, int]:
    removed: dict[str, int] = {}
    for name in names:
        values = getattr(workspace, name)
        if values:
            removed[name] = len(values)
            setattr(workspace, name, [])
    return removed


def _apply_with_audit(
    store: CaseWorkspaceStore,
    workspace: ProjectWorkspace,
    governance_log: GovernanceLog,
    *,
    actor: str,
    reset_type: str,
    removed: dict[str, int],
) -> dict[str, Any]:
    """Persist atomically through the existing store and append one audit event.

    If the audit append fails, restore the exact pre-operation JSON bytes. This
    keeps a failed reset from leaving a partially completed project state.
    """
    path = store._path_for(workspace.project_id)
    before = path.read_bytes() if path.exists() else None
    original = copy.deepcopy(workspace)
    try:
        store.save(workspace)
        governance_log.append(
            project_id=workspace.project_id,
            event_type="developer_project_reset",
            actor=actor,
            role="admin",
            authority_class="developer_tools",
            reason=reset_type,
            payload={"reset_type": reset_type, "removed_counts": removed, "outcome": "completed"},
        )
    except Exception:
        if before is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(before)
        # Keep the caller's object honest if it retries in-process.
        workspace.__dict__.clear()
        workspace.__dict__.update(original.__dict__)
        raise
    return {"reset_type": reset_type, "removed_counts": removed}


def reset_analysis_state(
    store: CaseWorkspaceStore, workspace: ProjectWorkspace, governance_log: GovernanceLog, *, actor: str,
) -> dict[str, Any]:
    """Clear only Spin-derived analytical history; preserve project evidence."""
    spin_finding_ids = {run_id for run in workspace.spin_runs for run_id in run.get("finding_ids", [])}
    before = len(workspace.spin_runs)
    workspace.spin_runs = []
    workspace.spin_generation_started_at = None
    # Composer findings emitted by Spin are derived; ordinary project findings
    # remain untouched.
    workspace.composer_findings = [
        finding for finding in workspace.composer_findings
        if finding.get("id") not in spin_finding_ids and not finding.get("spin_run_id")
    ]
    if workspace.project_briefing is not None:
        workspace.project_briefing = None
        workspace.project_briefing_generated_at = None
        workspace.project_briefing_generated_by = None
        workspace.project_briefing_source_signature = None
    return _apply_with_audit(
        store, workspace, governance_log, actor=actor, reset_type="analysis_state",
        removed={"spin_runs": before, "spin_findings": len(spin_finding_ids)},
    )


def reset_test_project(
    store: CaseWorkspaceStore, workspace: ProjectWorkspace, governance_log: GovernanceLog, *, actor: str,
) -> dict[str, Any]:
    """Deep-reset mutable project/test state while retaining evidence identity."""
    if not qualifies_as_synthetic_test_project(workspace):
        raise ValueError("Project is not explicitly identified as synthetic/test material.")
    removed = _reset_lists(workspace, [
        name for name in _state_lists(workspace) if name not in _TEST_RESET_PRESERVE
    ])
    workspace.spin_generation_started_at = None
    for field in ("project_briefing", "project_briefing_generated_at", "project_briefing_generated_by", "project_briefing_source_signature"):
        if hasattr(workspace, field):
            setattr(workspace, field, None)
    return _apply_with_audit(
        store, workspace, governance_log, actor=actor, reset_type="test_project",
        removed=removed,
    )
