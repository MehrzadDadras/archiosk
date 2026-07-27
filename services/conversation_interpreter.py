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

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ProjectWorkspace,
)
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
    case: Optional[dict],
    store: CaseWorkspaceStore,
    artifacts_dir: Path,
    reviewer: str,
    focused_finding_id: Optional[str],
    triggering_message_id: Optional[str] = None,
    anchor: Optional[dict] = None,
) -> InterpretationResult:
    """
    `case` is now optional (a project-level aperture - no Investigation
    open - see ConversationMessage's own docstring). The existing
    recognized actions (Analyze, evidence, Compare, correction) all
    genuinely need a Case (drawings and Findings are Case-scoped) and
    stay exactly as narrow as before - honestly declining, not
    guessing, when one isn't open - rather than being stretched to
    half-work without one.

    `anchor` (what the sender was actually looking at) does NOT expand
    what this interpreter understands - it is still deterministic
    keyword matching, not reasoning. What it changes is the fallback
    reply for anything unrecognized: acknowledging the anchor by name
    is an honest demonstration that the context was actually captured
    and carried through, not a claim that the message was understood.
    """
    lowered = text.strip().lower()

    if not lowered:
        return InterpretationResult(
            action_taken="none",
            reply_text="No instruction was recognized in an empty message.",
        )

    needs_case = (
        lowered.startswith(("analyze", "analyse"))
        or ("evidence" in lowered and "finding" in lowered)
        or lowered.startswith("compare") or " compare " in f" {lowered} "
        or (focused_finding_id is not None and _looks_like_correction(lowered))
    )
    if needs_case and case is None:
        return InterpretationResult(
            action_taken="needs_case",
            reply_text=(
                "That needs an open Investigation (drawings and Findings live "
                "inside one) - open or start one first, then ask again."
            ),
        )

    if lowered.startswith(("analyze", "analyse")):
        return _handle_analyze(text, workspace, case, store, artifacts_dir, reviewer, triggering_message_id)

    if "evidence" in lowered and "finding" in lowered:
        return _handle_show_evidence(lowered, case)

    if lowered.startswith("compare") or " compare " in f" {lowered} ":
        return _handle_compare(text, workspace, case, artifacts_dir, focused_finding_id)

    if "draft" in lowered and "rfi" in lowered:
        return _handle_draft_rfi_intent(focused_finding_id)

    if focused_finding_id is not None and _looks_like_correction(lowered):
        return _handle_correction(text, workspace, case, store, focused_finding_id, reviewer)

    if anchor is not None:
        return InterpretationResult(
            action_taken="anchor_acknowledged",
            reply_text=_describe_anchor_acknowledgment(anchor),
        )

    return InterpretationResult(
        action_taken="unrecognized",
        reply_text=(
            "I didn't recognize an action in that message. Try \"Analyze this "
            "drawing for ...\", \"Show me the evidence supporting Finding N\", "
            "\"Compare ... with ...\", \"Draft an RFI from this accepted issue\", "
            "or, with a Finding focused, a direct correction (e.g. \"This is not "
            "a datum, it is a civil reference\")."
        ),
    )


def _describe_anchor_acknowledgment(anchor: dict) -> str:
    """
    Honest, narrow reply proving the aperture's context actually
    arrived, without claiming the message itself was understood -
    this interpreter is still deterministic keyword matching (see this
    module's own docstring), not reasoning about what was said.
    """
    kind = (anchor.get("anchor_type") or "item").replace("_", " ")
    label = anchor.get("description") or anchor.get("anchor_id", "")
    return (
        f"Noted, in the context of this {kind}"
        f"{' (' + label + ')' if label else ''} - I didn't recognize a specific "
        "action in that message, but what you were looking at is on record "
        "against it."
    )


def _handle_analyze(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    artifacts_dir: Path,
    reviewer: str,
    triggering_message_id: Optional[str],
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
    prior_corrections = store.corrections_for_case(workspace, case["id"])

    try:
        raw_findings = analyze_drawing(
            image_path=Path(source["file_path"]),
            objective=text,
            artifacts_dir=artifacts_dir,
            prior_corrections=prior_corrections,
        )
    except Exception as exc:  # noqa: BLE001 - surfaced to the reviewer, not swallowed
        return InterpretationResult(
            action_taken="analyze_failed",
            reply_text=f"Analysis could not run: {exc}",
        )

    for item in raw_findings:
        item["source_id"] = source["id"]

    from services.drawing_analysis import ENGINE_NAME, ENGINE_VERSION

    # Prompt 7: this is the one, real trigger this Analysis has today - a
    # human typed a conversational instruction. Honest and specific rather
    # than a generic default: names the exact ConversationMessage that
    # caused it, when the caller has that id (post_message always does;
    # triggering_message_id is only ever None for call paths - none exist
    # yet - that don't originate from a stored message).
    trigger = AnalysisTrigger(
        trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
        trigger_reference_type="conversation_message" if triggering_message_id else None,
        trigger_reference_id=triggering_message_id,
        triggered_by_actor=reviewer,
    )

    analysis = store.record_analysis(
        workspace,
        case_id=case["id"],
        source_ids=[source["id"]],
        objective=text,
        engine_name=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        findings=raw_findings,
        trigger=trigger,
        prior_corrections_considered=len(prior_corrections),
    )

    count = len(analysis["finding_ids"])
    context_note = (
        f" Incorporated {len(prior_corrections)} prior reviewer correction(s) "
        "from this Case - matching topics were excluded from this run."
        if prior_corrections
        else ""
    )
    return InterpretationResult(
        action_taken=f"analysis:{analysis['id']}",
        reply_text=(
            f"Analysis complete on \"{source['name']}\". {count} candidate "
            f"finding(s) generated, each with its own Focus Snip Artifact. "
            f"All are provisional until reviewed — see the Artifact Workspace.{context_note}"
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
    # A conversational correction is recorded as a Reviewer Validation of
    # "Incorrect" carrying the correction text as its note - not a fourth,
    # separate concept. This keeps reviewerValidation/disposition/
    # review_state exactly three things, per Prompt 4 #1.
    try:
        store.record_reviewer_validation(
            workspace,
            finding_id=focused_finding_id,
            validation="Incorrect",
            reviewer=reviewer,
            correction_note=text,
        )
    except CaseWorkspaceError as exc:
        return InterpretationResult(action_taken="correction_failed", reply_text=str(exc))

    return InterpretationResult(
        action_taken=f"correction:{focused_finding_id}",
        reply_text=(
            "Recorded as a Reviewer Validation (Incorrect) with your correction "
            "attached to the focused Finding. The original machine finding is "
            "preserved; your correction is a separate, attributed record "
            "alongside it — it does not overwrite it, and nothing was applied "
            "to governed project state. Future analysis in this Case will "
            "account for it."
        ),
        focused_finding_id=focused_finding_id,
    )


def _handle_draft_rfi_intent(focused_finding_id: Optional[str]) -> InterpretationResult:
    """
    Recognizes "Draft an RFI ..." intent but does not create the draft
    itself - this is a Delegation Choice point (Prompt 4 #10): the route
    layer presents "Do it for me / Show me the proposed action first /
    Cancel" before anything is created, using the reference_snapshot
    BEEHIVE already has rather than asking the reviewer to reconstruct it.
    """
    if focused_finding_id is None:
        return InterpretationResult(
            action_taken="rfi_intent_failed",
            reply_text=(
                "Focus a Finding first (e.g. \"Show me the evidence supporting "
                "Finding 2\"), then ask me to draft an RFI from it."
            ),
        )

    return InterpretationResult(
        action_taken=f"rfi_intent:{focused_finding_id}",
        reply_text=(
            "I can draft an RFI from the focused Finding, inheriting its "
            "Source/page/region/Case references automatically. Choose below "
            "how you'd like to proceed."
        ),
        focused_finding_id=focused_finding_id,
    )
