"""
CLAUDE-P31, Part XII/XIII -- Owner assurance/activity visibility and a
reflexive self-check, both built as READ-SIDE aggregations over
mechanisms that already exist and are already tested (services.
governance.GovernanceLog, one append-only .jsonl file per project) --
no new storage, no new audit substrate. "Security-relevant audit
records should be append-only" (Part XII) is therefore inherited
directly from GovernanceLog's own existing, already-tested append-only
guarantee, not reimplemented here.

Honesty boundary (Part XII's own instruction: "Be honest about current
technical limits. Do not present ordinary mutable logging as tamper-
proof."): GovernanceLog's .jsonl files are ordinary files on the
deployment's own filesystem -- append-only by *convention* (every write
path in this codebase only ever appends), not by any cryptographic or
filesystem-level integrity guarantee. See services.security_policy.
SECURITY_CLAIMS_REGISTRY's "tamper-proof logs": prohibited_from_claiming.

Activity-level only: every function here returns actor/action-category/
timestamp/decision metadata, never the underlying project content
(Findings, requirement text, documents) -- "content-level inspection
remains separately controlled" (Part XII) is enforced by this module
having no code path back to any project's actual Requirement/Finding
text at all, not by a permission check that could be bypassed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Event types this module treats as "security-relevant" for assurance
# purposes -- a closed, named list rather than "everything in every
# GovernanceLog", so assurance activity stays a genuinely filtered,
# security-focused view rather than a duplicate of the full project
# audit trail.
SECURITY_RELEVANT_EVENT_TYPES = (
    "security_decision",
    "security_profile_set",
    "operating_environment_established",
)


@dataclass
class SecurityActivityEntry:
    project_id: str
    event_type: str
    actor: str
    role: str
    created_at: str
    decision: Optional[str] = None
    controlling_layer: Optional[str] = None


def aggregate_security_activity(registry, governance_log_factory, since: Optional[str] = None) -> list[SecurityActivityEntry]:
    """
    `registry` -- a services.requirements_registry.RequirementsRegistry
    (its list_ids() is the only cross-project enumeration mechanism this
    codebase has -- see honesty boundary in services.security_policy's
    module docstring: no Organization table exists to scope this by
    tenant, so this genuinely reads every project in the deployment).
    `governance_log_factory` -- a zero-arg callable returning a fresh
    services.governance.GovernanceLog (callers already have one
    constructed per-app; kept as a factory rather than a single shared
    instance so this function has no hidden dependency on a particular
    Flask app context).
    """
    log = governance_log_factory()
    entries: list[SecurityActivityEntry] = []
    for project_id in registry.list_ids():
        for event in log.read(project_id):
            if event.event_type not in SECURITY_RELEVANT_EVENT_TYPES:
                continue
            if since is not None and event.created_at <= since:
                continue
            payload = event.payload or {}
            entries.append(SecurityActivityEntry(
                project_id=project_id, event_type=event.event_type, actor=event.actor, role=event.role,
                created_at=event.created_at, decision=payload.get("decision") or payload.get("security_profile"),
                controlling_layer=payload.get("controlling_layer"),
            ))
    entries.sort(key=lambda e: e.created_at, reverse=True)
    return entries


# -- Self-check (Part XIII) --------------------------------------------------

@dataclass
class SelfCheckFinding:
    check_name: str
    severity: str  # "info" | "anomaly"
    description: str
    project_id: Optional[str] = None


def run_security_self_check(registry, case_workspace_store_factory, security_store, security_record) -> list[SelfCheckFinding]:
    """
    A representative, not exhaustive, set of checks (Part XIII: "Implement
    representative self-checks where safely supported") -- each one is a
    concrete, deterministic, pure-Python assertion over already-persisted
    state, no new instrumentation required. Returns only ANOMALY findings
    plus one INFO summary finding when everything is conforming ("Policy
    -> action -> enforcement decision -> audit event -> independent
    control check -> conforming or anomaly").

    `case_workspace_store_factory` -- zero-arg callable returning a fresh
    services.case_workspace.CaseWorkspaceStore, same factory shape as
    aggregate_security_activity's governance_log_factory and for the
    same reason.
    """
    from services.environment_capabilities import is_valid_operating_environment
    from services.security_policy import is_valid_classification

    findings: list[SelfCheckFinding] = []
    store = case_workspace_store_factory()

    # Check 1: every project's operating_environment, if set, is a
    # currently-valid value (catches a hand-edited/corrupted JSON file,
    # not a runtime bypass -- set_operating_environment itself already
    # structurally prevents an invalid write).
    # Check 2: every project's security_profile, if set, is currently valid.
    for project_id in registry.list_ids():
        # CLAUDE-P36: a corrupted legacy workspace file (missing a field
        # ProjectWorkspace's current dataclass shape requires -- the
        # pre-existing real instance/registry/ 'reviews'-key
        # incompatibility documented since CLAUDE-P32/P34) must not crash
        # the ENTIRE self-check merely because one such project exists on
        # disk. Unlike app.py's _nav_recent_projects/routes/portal.py's
        # _accessible_documents (which silently exclude), this function's
        # whole purpose is surfacing anomalies -- so an unreadable
        # workspace is itself reported as one, not swallowed.
        try:
            workspace = store.get(project_id)
        except TypeError:
            findings.append(SelfCheckFinding(
                "workspace_readable", "anomaly",
                "This project's workspace file could not be loaded (incompatible with the "
                "current governed schema) -- excluded from every other check below.",
                project_id=project_id,
            ))
            continue
        if workspace is None:
            continue
        if workspace.operating_environment is not None and not is_valid_operating_environment(workspace.operating_environment):
            findings.append(SelfCheckFinding(
                "operating_environment_valid", "anomaly",
                f"Project has an unrecognized operating_environment value: {workspace.operating_environment!r}.",
                project_id=project_id,
            ))
        if workspace.security_profile is not None and not is_valid_classification(workspace.security_profile):
            findings.append(SelfCheckFinding(
                "security_profile_valid", "anomaly",
                f"Project has an unrecognized security_profile value: {workspace.security_profile!r}.",
                project_id=project_id,
            ))

    # Check 3: every control decision recorded on every baseline carries
    # real provenance (Part III: "Never disguise an application
    # recommendation as a customer policy requirement") -- a
    # policy_statement/qa_entry-sourced decision must actually reference
    # a source_id that still exists in this same record.
    known_statement_ids = {s["id"] for s in security_record.policy_statements}
    known_qa_ids = {q["id"] for q in security_record.qa_entries}
    for baseline in security_record.baselines:
        for action_id, entry in baseline.get("control_decisions", {}).items():
            source_type = entry.get("source_type")
            source_id = entry.get("source_id")
            if source_type == "policy_statement" and source_id not in known_statement_ids:
                findings.append(SelfCheckFinding(
                    "control_decision_provenance", "anomaly",
                    f"Baseline {baseline['id']} action {action_id!r} cites a missing policy_statement {source_id!r}.",
                ))
            if source_type == "qa_entry" and source_id not in known_qa_ids:
                findings.append(SelfCheckFinding(
                    "control_decision_provenance", "anomaly",
                    f"Baseline {baseline['id']} action {action_id!r} cites a missing qa_entry {source_id!r}.",
                ))

    # Check 4: no more than one ACTIVE baseline exists at once (the
    # activate_baseline/supersede pair is the only writer of `status`,
    # but this independently re-verifies the invariant it's supposed to
    # maintain, rather than trusting that writer never has a bug).
    active_baselines = [b for b in security_record.baselines if b["status"] == "active"]
    if len(active_baselines) > 1:
        findings.append(SelfCheckFinding(
            "single_active_baseline", "anomaly",
            f"{len(active_baselines)} baselines are simultaneously ACTIVE (expected at most one).",
        ))

    # Check 5: no expired exception is still marked "active" (expiry is
    # checked at evaluation time by active_exception_for's own filter --
    # this independently re-scans for one whose expires_at has already
    # passed but whose stored status was never flipped, which would be
    # silently correct today but worth surfacing).
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for exception in security_record.exceptions:
        if exception["status"] == "active" and exception["expires_at"] is not None and exception["expires_at"] <= now:
            findings.append(SelfCheckFinding(
                "exception_not_stale", "anomaly",
                f"Exception {exception['id']} has expired ({exception['expires_at']}) but is still marked active.",
            ))

    if not findings:
        findings.append(SelfCheckFinding(
            "self_check_summary", "info", "No anomalies detected across all representative checks.",
        ))
    return findings
