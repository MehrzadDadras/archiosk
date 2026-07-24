"""
Conversation-as-control-surface prototype for the Case Workspace.

Honesty note: this is deterministic keyword pattern-matching, not natural
language understanding. It recognizes exactly the shapes of message the
Case Workspace prototype is built to demonstrate (see Prompt 4 #6):
"Analyze ...", "Show me the evidence supporting Finding N", "Compare ...",
and a free-text correction addressed at whatever Finding is currently
focused. Anything else gets an honest "I didn't recognize an action"
reply rather than a guessed one. This keeps the conversation surface real
and traceable rather than an unlabeled black box, in the same spirit as
services/drawing_analysis.py's mock findings.

Every recognized action still goes through the same governed operations
(record_analysis / record_review) explicit controls use — conversation is
an additional control surface, not a bypass of Analyze -> Review -> Apply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from services.case_workspace import CaseWorkspaceError, CaseWorkspaceStore, ProjectWorkspace
from services.drawing_analysis import analyze_drawing, make_comparison_artifact


@dataclass
class InterpretationResult:
    action_taken: str
    reply_text: str
    focused_finding_id: Optional[str] = None


_FINDING_NUMBER_PATTERN = re.compile(r"finding\s*#?\s*(\d+)", re.IGNORECASE)


def interpret_message(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    artifacts_dir: Path,
    reviewer: str,
    focused_finding_id: Optional[str],
) -> InterpretationResult:
    lowered = text.strip().lower()

    if not lowered:
        return InterpretationResult(
            action_taken="none",
            reply_text="No instruction was recognized in an empty message.",
        )

    if lowered.startswith(("analyze", "analyse")):
        return _handle_analyze(text, workspace, case, store, artifacts_dir)

    if "evidence" in lowered and "finding" in lowered:
        return _handle_show_evidence(lowered, case)

    if lowered.startswith("compare") or " compare " in f" {lowered} ":
        return _handle_compare(text, workspace, case, artifacts_dir, focused_finding_id)

    if focused_finding_id is not None and _looks_like_correction(lowered):
        return _handle_correction(text, workspace, case, store, focused_finding_id, reviewer)

    return InterpretationResult(
        action_taken="unrecognized",
        reply_text=(
            "I didn't recognize an action in that message. Try \"Analyze this "
            "drawing for ...\", \"Show me the evidence supporting Finding N\", "
            "\"Compare ... with ...\", or, with a Finding focused, a direct "
            "correction (e.g. \"This is not a datum, it is a civil reference\")."
        ),
    )


def _handle_analyze(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    artifacts_dir: Path,
) -> InterpretationResult:
    drawing_sources = [
        s for s in workspace.sources
        if s["id"] in case["source_ids"] and s["kind"] == "drawing"
    ]
    if not drawing_sources:
        return InterpretationResult(
            action_taken="analyze_failed",
            reply_text=(
                "There's no drawing Source attached to this Case yet. Add one "
                "before asking me to analyze it."
            ),
        )

    source = drawing_sources[-1]

    try:
        raw_findings = analyze_drawing(
            image_path=Path(source["file_path"]),
            objective=text,
            artifacts_dir=artifacts_dir,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer, not swallowed
        return InterpretationResult(
            action_taken="analyze_failed",
            reply_text=f"Analysis could not run: {exc}",
        )

    for item in raw_findings:
        item["source_id"] = source["id"]

    from services.drawing_analysis import ENGINE_NAME, ENGINE_VERSION

    analysis = store.record_analysis(
        workspace,
        case_id=case["id"],
        source_ids=[source["id"]],
        objective=text,
        engine_name=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        findings=raw_findings,
    )

    count = len(analysis["finding_ids"])
    return InterpretationResult(
        action_taken=f"analysis:{analysis['id']}",
        reply_text=(
            f"Analysis complete on \"{source['name']}\". {count} candidate "
            f"finding(s) generated, each with its own Focus Snip Artifact. "
            "All are provisional until reviewed — see the Artifact Workspace."
        ),
    )


def _handle_show_evidence(lowered: str, case: dict) -> InterpretationResult:
    match = _FINDING_NUMBER_PATTERN.search(lowered)
    if not match:
        return InterpretationResult(
            action_taken="focus_failed",
            reply_text="Which finding? Try \"Show me the evidence supporting Finding 2\".",
        )

    index = int(match.group(1)) - 1
    finding_ids = case["finding_ids"]
    if index < 0 or index >= len(finding_ids):
        return InterpretationResult(
            action_taken="focus_failed",
            reply_text=f"This Case only has {len(finding_ids)} finding(s) so far.",
        )

    finding_id = finding_ids[index]
    return InterpretationResult(
        action_taken=f"focus:{finding_id}",
        reply_text=f"Focused Finding {index + 1} in the Artifact Workspace.",
        focused_finding_id=finding_id,
    )


def _handle_compare(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    artifacts_dir: Path,
    focused_finding_id: Optional[str],
) -> InterpretationResult:
    focused_label = "the focused fragment"
    if focused_finding_id is not None:
        finding = next((f for f in workspace.findings if f["id"] == focused_finding_id), None)
        if finding is not None:
            focused_label = finding["statement"][:40]

    make_comparison_artifact(
        label_a=focused_label,
        label_b="structural drawing (referenced)",
        note=text,
        artifacts_dir=artifacts_dir,
    )

    return InterpretationResult(
        action_taken="compare",
        reply_text=(
            "A mock comparison Artifact was generated — illustrative only, "
            "not a claim of real pixel-level comparison in this prototype."
        ),
    )


def _looks_like_correction(lowered: str) -> bool:
    return lowered.startswith((
        "this is not", "that is not", "actually,", "no, it", "it is not",
        "this isn't", "that isn't",
    ))


def _handle_correction(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    focused_finding_id: str,
    reviewer: str,
) -> InterpretationResult:
    try:
        store.record_review(
            workspace,
            finding_id=focused_finding_id,
            decision="correction",
            reviewer=reviewer,
            note=text,
        )
    except CaseWorkspaceError as exc:
        return InterpretationResult(action_taken="correction_failed", reply_text=str(exc))

    return InterpretationResult(
        action_taken=f"correction:{focused_finding_id}",
        reply_text=(
            "Recorded as a correction on the focused Finding. The original "
            "machine finding is preserved; your correction is a separate, "
            "attributed record alongside it — it does not overwrite it, and "
            "nothing was applied to governed project state."
        ),
        focused_finding_id=focused_finding_id,
    )
