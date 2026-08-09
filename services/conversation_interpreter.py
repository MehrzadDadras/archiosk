"""
Conversation-as-control-surface prototype for the Case Workspace.

Honesty note: TRIGGER RECOGNITION here is deterministic keyword
pattern-matching, not natural language understanding, and stays that
way - it recognizes exactly the shapes of message the Case Workspace
prototype is built to demonstrate (see Prompt 4 #6): "Analyze ...",
"Show me the evidence supporting Finding N", "Compare ...", a free-text
correction addressed at whatever Finding is currently focused, and (CLAUDE-
P04) an investigation-shaped question anchored to a Requirement ("Why is
this like this?", "Check this.", "Something is wrong here."). Anything
else gets an honest "I didn't recognize an action" reply rather than a
guessed one.

What happens AFTER a Requirement-anchored investigation question is
recognized is genuinely different from every other action here: real
reasoning via services/requirement_investigation.py's Anthropic call,
not a canned reply or a mock finding. Every other recognized action
(Analyze a drawing, Compare) still calls services/drawing_analysis.py's
mock engine - CLAUDE-P04 deliberately proved real reasoning on
Requirements ONLY, not across every action this file recognizes.

Every recognized action still goes through the same governed operations
(record_analysis / record_review) explicit controls use — conversation is
an additional control surface, not a bypass of Analyze -> Review -> Apply.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AUTONOMOUS_BRANCH_CONFIDENCE_THRESHOLD,
    INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
    OBJECT_KIND_REQUIREMENT,
    PERSPECTIVE_ORIGIN_MACHINE,
    AnalysisTrigger,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    ProjectWorkspace,
)
from services.drawing_analysis import analyze_drawing, make_comparison_artifact
from services.project_qa import answer_project_question
from services.requirement_investigation import investigate_requirement
from services.security_policy import DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE
import services.quantitative_investigation as quant


@dataclass
class InterpretationResult:
    action_taken: str
    reply_text: str
    focused_finding_id: Optional[str] = None
    # CLAUDE-P40-B (3.6): grounded Project Q&A's supporting citations,
    # kept separate from reply_text - see ConversationMessage.grounded_in's
    # own comment for why. Only ever set by _handle_project_question.
    grounded_in: list[str] = field(default_factory=list)
    # CLAUDE-POSTCAMEL-CA1 (Section 9/10): a small, deterministic,
    # server-computed list of real next-step offers, each
    # {"label": str, "view": str} where `view` is always an existing
    # Display view name - never model-generated prose interpreted as a
    # command. Only ever set by _handle_project_orientation and
    # _handle_project_question (and the final unrecognized fallback).
    next_steps: list[dict] = field(default_factory=list)


_FINDING_NUMBER_PATTERN = re.compile(r"finding\s*#?\s*(\d+)", re.IGNORECASE)


def _evaluate_external_ai_policy(store: CaseWorkspaceStore, workspace: ProjectWorkspace):
    """
    CLAUDE-P36: the one call site in this file that can trigger a real
    external AI request (_handle_investigate_requirement, below) resolves
    ACTION_EXTERNAL_AI_REQUEST through this project's full effective
    security policy - mandatory floor, active organization baseline, this
    project's own security_profile classification, and any active
    exception - before that request is ever built. Mirrors routes/
    workspace.py's _evaluate_security_action and services/ingestion.py's
    ingestion-time gate exactly (same resolver, same four-input lookup);
    duplicated rather than shared, matching those two call sites' own
    existing precedent (each already duplicates this short lookup instead
    of sharing a helper, since each has a different way of reaching the
    registry store path - see _evaluate_security_action's own docstring).
    """
    from services.security_governance import SecurityGovernanceStore
    from services.security_policy import ACTION_EXTERNAL_AI_REQUEST, evaluate_action, profile_decision_for

    security_store = SecurityGovernanceStore(store.store_path)
    security_record = security_store.get()
    active_baseline = security_store.active_baseline(security_record)
    return evaluate_action(
        ACTION_EXTERNAL_AI_REQUEST,
        classification=workspace.security_profile,
        baseline_decision=(
            active_baseline["control_decisions"].get(ACTION_EXTERNAL_AI_REQUEST, {}).get("decision")
            if active_baseline else None
        ),
        baseline_version_id=active_baseline["id"] if active_baseline else None,
        profile_decision=profile_decision_for(workspace.security_profile, ACTION_EXTERNAL_AI_REQUEST),
        active_exception=security_store.active_exception_for(
            security_record, ACTION_EXTERNAL_AI_REQUEST, project_id=workspace.project_id,
        ),
    )


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
    governance_log=None,
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

    is_requirement_investigation_question = (
        anchor is not None
        and anchor.get("anchor_type") == "requirement"
        and _looks_like_investigation_request(lowered)
    )

    # CLAUDE-P40-VW8-QA-R6: a Case-scoped, evidence-guided quantitative
    # feasibility question (distance/elevation/slope/clearance - see
    # services/quantitative_investigation.py's own header for the full
    # reasoning) OR a follow-up message supplying a value for one
    # already in progress in THIS Case's conversation. Checked before
    # is_requirement_investigation_question's own handler below so a
    # quantitative question anchored to nothing in particular still
    # gets the specific, useful handler rather than falling through to
    # the generic project-question/discussion-acknowledgment path.
    # `looks_like_quantitative` itself is NOT case-gated (needed below,
    # for the needs_case escalation offer, which fires precisely when
    # no Case is open yet); `is_quantitative_question` is the case-
    # gated version this function actually dispatches on.
    looks_like_quantitative = quant.looks_like_quantitative_feasibility_question(lowered)
    is_quantitative_question = case is not None and (
        looks_like_quantitative
        or (
            quant.extract_values_from_text(text)
            and any(
                quant.looks_like_quantitative_feasibility_question((m.get("text") or "").lower())
                for m in case["conversation"]
            )
        )
    )
    needs_case = (
        lowered.startswith(("analyze", "analyse"))
        or ("evidence" in lowered and "finding" in lowered)
        or lowered.startswith("compare") or " compare " in f" {lowered} "
        or (focused_finding_id is not None and _looks_like_correction(lowered))
        or is_requirement_investigation_question
        or looks_like_quantitative
    )
    if needs_case and case is None:
        # The "conversation -> Investigation" escalation offer (routes/
        # workspace.py's start_investigation_from_aperture) reads this
        # exact message back out later by id - encoded here, not in a
        # new piece of session state, because the message itself is
        # already the durable record of what was asked and what it was
        # anchored to. Only offered when a Case-SHAPED action was
        # actually recognized (this branch) - never for an ordinary
        # unmatched question (anchor_acknowledged, below), so asking
        # "why is this like this?" never itself pushes toward creating
        # an Investigation just because it went unrecognized.
        action_taken = f"needs_case:{triggering_message_id}" if triggering_message_id else "needs_case"
        # CLAUDE-P40-VW8-QA-R6: a real suggested title for a
        # quantitative feasibility question - the question itself is
        # never replaced/truncated by it (it stays the full message,
        # unchanged, in this same reply and in the eventual Case's own
        # conversation).
        title_suggestion = (
            f" A suggested Investigation title: \"{quant.suggested_title(text)}\"."
            if looks_like_quantitative else ""
        )
        return InterpretationResult(
            action_taken=action_taken,
            reply_text=(
                "That needs an open Investigation (Findings live inside one) - "
                f"start one from this below, or open one and ask again.{title_suggestion}"
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

    if is_requirement_investigation_question:
        return _handle_investigate_requirement(
            text, workspace, case, store, reviewer, anchor, triggering_message_id, governance_log,
        )

    if is_quantitative_question:
        return _handle_quantitative_investigation(text, workspace, case, store, reviewer, triggering_message_id)

    if anchor is not None:
        return InterpretationResult(
            action_taken="anchor_acknowledged",
            reply_text=_describe_anchor_acknowledgment(anchor),
        )

    # CLAUDE-P38 (OBS-01): an ordinary, unanchored, read-only question
    # ("What are the objectives of this RFP?", "Summarize this project")
    # attempted here, before falling through to "I didn't recognize an
    # action" - the "Talk to this Project..." composer's own placeholder
    # promises ordinary project Q&A, but every branch above it only ever
    # recognized a narrow, Case-shaped command grammar. Bounded to
    # messages that actually look like a question (see
    # _looks_like_project_question) so an unrelated stray message still
    # gets the honest "unrecognized" reply rather than a real,
    # billed model call for something that was never a question at all.
    # CLAUDE-POSTCAMEL-CA1 (Section 4): checked before the generic
    # project-question branch below - see _ORIENTATION_PHRASES' own
    # comment for why. No Case requirement (orientation is always
    # Project-level) and no external-AI policy gate (no model call).
    if _looks_like_orientation_request(lowered):
        return _handle_project_orientation(workspace)

    if _looks_like_project_question(lowered):
        return _handle_project_question(text, workspace, case, store, reviewer, triggering_message_id)

    # CLAUDE-P40-B (3.7): "Analyze this drawing for..." was suggested
    # unconditionally, regardless of whether this Case has any drawing
    # Source - confirmed misleading for a text-document (DOCX/PDF RFP)
    # Case. Reuses the same drawing-Source check _handle_analyze already
    # makes, not a new medium-detection mechanism.
    has_drawing_source = bool(
        case is not None
        and any(
            s["id"] in case["source_ids"] and s["kind"] == "drawing"
            for s in CaseWorkspaceStore.active_sources(workspace)
        )
    )
    analyze_example = (
        "\"Analyze this drawing for ...\", " if has_drawing_source
        else "\"Investigate this Source for ...\", "
    )
    correction_example = (
        "\"This is not a datum, it is a civil reference\")." if has_drawing_source
        else "\"This is not a scope item, it is background context\")."
    )

    # CLAUDE-P40-VW8-QA-R6: "when an Investigation is active, ordinary
    # natural language must be treated as Investigation discussion
    # unless it clearly invokes another supported action." Every branch
    # above this one already tried every recognized action-shaped
    # pattern and this specific case-scoped quantitative pattern - a
    # plain contextual statement/clarification with an open Case
    # reaches here, and gets recorded as a real discussion contribution
    # instead of the same "unrecognized" reply a genuinely unrelated
    # stray message (no Case open at all) still gets below. Never
    # invents understanding of WHAT was said - the honest acknowledgment
    # is that it was received and will be considered, not a claim of
    # having reasoned about it.
    if case is not None:
        return InterpretationResult(
            action_taken="discussion_contribution",
            reply_text=(
                "Noted as context for this Investigation. I don't have a specific action to take on "
                "that alone - ask me to calculate/evaluate something (e.g. a feasibility question "
                "with the relevant dimensions), or use one of the recognized actions "
                f"({analyze_example}\"Show me the evidence supporting Finding N\", \"Compare ... with "
                "...\") when you're ready."
            ),
        )

    return InterpretationResult(
        action_taken="unrecognized",
        reply_text=(
            f"I didn't recognize an action in that message. Try {analyze_example}"
            "\"Show me the evidence supporting Finding N\", "
            "\"Compare ... with ...\", \"Draft an RFI from this accepted issue\", "
            "a direct question about this project (e.g. \"What are the "
            "objectives of this RFP?\"), \"orient me\" for a summary of what's "
            "registered here, or, with a Finding focused, a direct "
            f"correction (e.g. {correction_example}"
        ),
        # CLAUDE-POSTCAMEL-CA1 (Section 23): a dead end still leaves a
        # real, concrete, one-click way forward rather than only prose.
        next_steps=[{"label": "Open Files", "view": "files"}],
    )


def _describe_anchor_acknowledgment(anchor: dict) -> str:
    """
    Honest, narrow reply proving the aperture's context actually
    arrived, without claiming the message itself was understood -
    this interpreter is still deterministic keyword matching (see this
    module's own docstring), not reasoning about what was said.

    CLAUDE-P39: for a Requirement anchor specifically, this is also the
    one place a reviewer whose concern didn't happen to match
    _INVESTIGATION_PHRASES finds out - the fallback used to be a true
    dead end (no path forward, no hint at what phrasing would have
    worked); now it names a couple of phrasings that would. Still
    doesn't claim the message was understood, and still doesn't offer
    (or trigger) an Investigation on its own - the reviewer has to
    actually say so, same as before this stage.
    """
    kind = (anchor.get("anchor_type") or "item").replace("_", " ")
    label = anchor.get("description") or anchor.get("anchor_id", "")
    text = (
        f"Noted, in the context of this {kind}"
        f"{' (' + label + ')' if label else ''} - I didn't recognize a specific "
        "action in that message, but what you were looking at is on record "
        "against it."
    )
    if anchor.get("anchor_type") == "requirement":
        text += (
            " If this is a concern worth investigating, say so directly - e.g. "
            "\"Investigate this\" or \"Something is wrong here\" - and this can "
            "become the start of an Investigation."
        )
    return text


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
        s for s in CaseWorkspaceStore.active_sources(workspace)
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


# CLAUDE-P04: the deliberately narrow set of "unspecific" phrasings that
# route an anchored Requirement question to real investigation instead
# of the generic anchor_acknowledged fallback - matches the exact
# example phrasings this feature was scoped against ("Why is this like
# this?", "Check this.", "Something is wrong here.", "Where did this
# come from?"). Still keyword matching, per this module's own honesty
# note - only what happens AFTER a match is genuinely different here.
_INVESTIGATION_PHRASES = (
    "why is this", "why does this", "why was this", "why isn't this", "why is that",
    "check this", "something is wrong", "something's wrong", "something wrong here",
    "where did this come from", "where does this come from",
    "investigate this", "look into this",
    # CLAUDE-P39: additional natural ways a reviewer states a concern
    # about a Requirement without using any of the phrases above - found
    # live during this stage's own audit ("I'm not sure this covers
    # electrical systems as well, only mechanical" produced a silent
    # anchor_acknowledged dead end, with no path to an Investigation, for
    # exactly the kind of substantive concern this feature exists to
    # catch). Still a bounded phrase list, not a rewrite of this
    # module's deterministic-keyword-matching design.
    "not sure this covers", "not sure if this covers", "doesn't cover", "does not cover",
    "doesn't mention", "does not mention", "no mention of",
    "seems to conflict", "conflicts with", "not specified", "not stated",
    "unclear whether", "unclear if", "not clear whether", "not clear if",
    "concerned about", "concerned that", "this is missing", "appears to be missing",
)


def _looks_like_investigation_request(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _INVESTIGATION_PHRASES)


# CLAUDE-P38 (OBS-01): a deliberately simple, honest heuristic - a
# question mark, or one of these leading words/phrases - not an attempt
# at real language understanding (this module stays deterministic
# keyword matching throughout, per its own docstring). Bounding this
# rather than treating every unmatched message as a question keeps a
# genuinely unrelated stray message from triggering a real, billed
# model call for something that was never a question at all.
_PROJECT_QUESTION_STARTERS = (
    "what", "who", "when", "where", "why", "how", "which",
    "summarize", "summarise", "list", "walk me through", "walk through",
    "describe", "explain", "tell me", "give me", "overview", "outline",
)


def _looks_like_project_question(lowered: str) -> bool:
    stripped = lowered.strip()
    return stripped.endswith("?") or stripped.startswith(_PROJECT_QUESTION_STARTERS)


# CLAUDE-POSTCAMEL-CA1 (Section 4, Project orientation): a deliberately
# narrow, deterministic phrase set - same discipline as
# _looks_like_project_question above, not an attempt at real language
# understanding. Checked BEFORE _looks_like_project_question so "what's
# here"/"what do I have" (which would otherwise match that generic
# "what..." starter) gets the dedicated, no-model-call orientation
# handler instead of a real, billed Project Q&A request for a question
# that isn't actually about any specific evidence.
_ORIENTATION_PHRASES = (
    "orient me", "orient us", "what's here", "whats here", "what is here",
    "what do i have", "what do we have", "what's in this project",
    "what is in this project", "give me an overview", "give an overview",
    "where do i start", "where should i start", "where do we start",
    "what's the state of this project", "what is the state of this project",
)


def _looks_like_orientation_request(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _ORIENTATION_PHRASES)


def _handle_project_orientation(workspace: ProjectWorkspace) -> InterpretationResult:
    """
    CLAUDE-POSTCAMEL-CA1 (Section 4): real, deterministic Project
    orientation from actual workspace state - no model call, so this
    works even when ANTHROPIC_API_KEY is absent or the external-AI
    policy denies transmission (see _handle_project_question below for
    the contrast). Never fabricates structure and never treats a sparse
    Project as defective (this stage's own explicit instruction) -
    "sparse" here is an honest, evidenced, stated heuristic (few
    registered Sources AND no governed Requirements yet), not a claim
    of understanding the Project's actual maturity.

    next_steps are real navigable Display views only, per Section 9/10's
    own "do not offer actions that do not exist" - "map its contents" /
    "suggest a project structure" (the sparse example's own prose) are
    named as things a reviewer can ask for in conversation, not rendered
    as chips, because neither is a distinct existing view or action.
    """
    active_sources = CaseWorkspaceStore.active_sources(workspace)
    source_count = len(active_sources)
    requirement_count = len(workspace.requirements)
    is_sparse = source_count <= 2 and requirement_count == 0

    if is_sparse:
        source_word = "one registered project source" if source_count == 1 else (
            f"{source_count} registered project sources" if source_count else "no registered project sources yet"
        )
        reply = (
            f"I see {source_word}. I can inspect it, help you map its contents, "
            "suggest a Project structure around it (advisory only - nothing "
            "physical is created or moved), or leave it exactly as it is. "
            "Open Files below to look at what's registered, or ask something else."
        )
        next_steps = [{"label": "Open Files", "view": "files"}]
    else:
        reply = (
            f"This Project has {source_count} registered source(s) and "
            f"{requirement_count} governed Requirement(s) on record. I can help "
            "you survey the Project Territory, review what needs attention, "
            "review Requirements, or continue previous work - or ask something else."
        )
        next_steps = [
            {"label": "Open Files", "view": "files"},
            {"label": "Open Requirements", "view": "requirements"},
            {"label": "Open Overview", "view": "overview"},
        ]

    return InterpretationResult(
        action_taken="project_orientation", reply_text=reply, next_steps=next_steps,
    )


def _handle_investigate_requirement(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    reviewer: str,
    anchor: dict,
    triggering_message_id: Optional[str],
    governance_log=None,
) -> InterpretationResult:
    """
    The one real reasoning path in this file (CLAUDE-P04) - everything
    else above still calls services/drawing_analysis.py's mock engine.
    Requires an open Case (like _handle_analyze) because Finding/Artifact
    remain Case-scoped (record_analysis's own enforced constraint) - a
    Project-level Analysis literally cannot carry a real Finding, so
    there is no honest way to run this without one.
    """
    requirement = next((r for r in workspace.requirements if r["id"] == anchor["anchor_id"]), None)
    if requirement is None:
        return InterpretationResult(
            action_taken="investigate_failed",
            reply_text="That Requirement no longer exists in this Project.",
        )

    # CLAUDE-P36: this is the one real external-AI transmission this file
    # can trigger (see module docstring) - resolved through the SAME
    # security_policy.evaluate_action resolver services/ingestion.py and
    # routes/workspace.py's _evaluate_security_action already use for this
    # exact governed action, not a second permission system. Checked
    # BEFORE any evidence is gathered or a prompt is built, and before
    # investigate_requirement (the function that would actually transmit
    # anything) is ever called - a denial here means nothing about this
    # Requirement leaves the process. store.store_path is the same
    # REGISTRY_STORE_PATH every SecurityGovernanceStore in this app is
    # constructed from (CaseWorkspaceStore.__init__ keeps it verbatim).
    policy_decision = _evaluate_external_ai_policy(store, workspace)
    if policy_decision.decision not in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        denial_reason = (
            f"External AI analysis for this investigation is not permitted by this "
            f"project's security policy (controlling layer: {policy_decision.controlling_layer}). "
            f"{policy_decision.reason} Nothing was transmitted."
        )
        store.record_investigation_step(
            workspace,
            case_id=case["id"],
            step_kind=INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
            anchor=anchor,
            question=text,
            triggered_by_actor=reviewer,
            evidence_requested=[],
            evidence_examined_ids={},
            ran=False,
            skipped_reason=denial_reason,
        )
        return InterpretationResult(
            action_taken=f"investigation_policy_denied:{policy_decision.controlling_layer}",
            reply_text=(
                f"{denial_reason} Nothing was fabricated - the evidence already shown "
                "for this Requirement is what there is; the judgment call is yours to "
                "make from it, or ask again once policy permits this."
            ),
        )

    evidence = store.requirement_evidence(workspace, requirement["id"])
    adjudication_history = store.requirement_adjudications_for(workspace, requirement["id"])

    # CLAUDE-P08: fixed, honest description of what was gathered - not a
    # claim the model chose what to look at, since retrieval today is
    # deterministic (see requirement_evidence/requirement_adjudications_
    # for, both called unconditionally above, same for every question).
    evidence_requested = [
        "This Requirement's own recorded fields (text, classification, subject domain, status)",
        "Full adjudication history for this Requirement",
        "Findings/Relationships/AcceptedKnowledge cited by its latest adjudication",
        "Supersession neighbors (predecessor/current governing successor) and direct Relationships",
    ]
    evidence_examined_ids = {
        "adjudication_ids": [a["id"] for a in adjudication_history],
        "finding_ids": [f["id"] for f in evidence.get("findings", [])],
        "relationship_ids": [r["id"] for r in evidence.get("relationships", [])],
        "accepted_knowledge_ids": [k["id"] for k in evidence.get("accepted_knowledge", [])],
    }

    # CLAUDE-P12R: purely additive - None (no represented party set for
    # this reviewer) means investigate_requirement asks for and returns
    # nothing risk-related, identical to before this existed.
    represented_party = store.represented_party_for(workspace, reviewer)

    # CLAUDE-P15/P16: gathered for EVERY real investigation, not only
    # when a test supplies it - this is the production evidence path,
    # not a benchmark-only enrichment. Supersession neighbors (what this
    # superseded, what superseded this) and direct Relationships (e.g.
    # "qualifies") are both real, already-governed connections this
    # Requirement has - reusing store.current_requirement_for/
    # requirement_predecessor/relationships_for, never a new lookup.
    related_requirements = []
    if requirement["status"] == "superseded":
        current = store.current_requirement_for(workspace, requirement["id"])
        if current is not None and current["id"] != requirement["id"]:
            related_requirements.append({
                "id": current["id"],
                "original_requirement_identifier": current["original_requirement_identifier"],
                "text_reference": current["text_reference"], "status": current["status"],
                "relationship_type": "supersedes_this", "note": "the current governing successor",
            })
    predecessor = store.requirement_predecessor(workspace, requirement["id"])
    if predecessor is not None:
        related_requirements.append({
            "id": predecessor["id"],
            "original_requirement_identifier": predecessor["original_requirement_identifier"],
            "text_reference": predecessor["text_reference"], "status": predecessor["status"],
            "relationship_type": "superseded_by_this",
            "note": "the immediate predecessor this Requirement's own revision superseded",
        })
    for rel in store.relationships_for(workspace, OBJECT_KIND_REQUIREMENT, requirement["id"]):
        other_is_from = rel["to_id"] == requirement["id"]
        other_type = rel["from_type"] if other_is_from else rel["to_type"]
        other_id = rel["from_id"] if other_is_from else rel["to_id"]
        if other_type != OBJECT_KIND_REQUIREMENT:
            continue
        other = next((r for r in workspace.requirements if r["id"] == other_id), None)
        if other is None:
            continue
        related_requirements.append({
            "id": other["id"], "original_requirement_identifier": other["original_requirement_identifier"],
            "text_reference": other["text_reference"], "status": other["status"],
            "relationship_type": rel["relationship_type"],
            "note": f"connected via a real, registered '{rel['relationship_type']}' Relationship",
        })
        # CLAUDE-P18: a Relationship can point at a Requirement that has
        # ITSELF since been superseded (a lifecycle can span several
        # stages away from where a Relationship was originally drawn) -
        # without this, the model would only ever see the STALE related
        # text, never the current governing successor it's actually since
        # become. Reuses current_requirement_for again, never a new
        # supersession-walking mechanism.
        if other["status"] == "superseded":
            other_current = store.current_requirement_for(workspace, other["id"])
            if other_current is not None and other_current["id"] != other["id"]:
                related_requirements.append({
                    "id": other_current["id"],
                    "original_requirement_identifier": other_current["original_requirement_identifier"],
                    "text_reference": other_current["text_reference"], "status": other_current["status"],
                    "relationship_type": rel["relationship_type"],
                    "note": (
                        f"the CURRENT governing successor of the '{rel['relationship_type']}'-related "
                        f"Requirement above, which has itself since been superseded"
                    ),
                })
    evidence_examined_ids["related_requirement_ids"] = [r["id"] for r in related_requirements]

    result = investigate_requirement(
        question=text,
        requirement=requirement,
        adjudication_history=adjudication_history,
        evidence=evidence,
        represented_party=represented_party,
        related_requirements=related_requirements or None,
    )

    if not result.ran:
        store.record_investigation_step(
            workspace,
            case_id=case["id"],
            step_kind=INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
            anchor=anchor,
            question=text,
            triggered_by_actor=reviewer,
            evidence_requested=evidence_requested,
            evidence_examined_ids=evidence_examined_ids,
            ran=False,
            skipped_reason=result.skipped_reason,
        )
        return InterpretationResult(
            action_taken="investigation_unavailable",
            reply_text=(
                f"Real investigation can't run right now: {result.skipped_reason} "
                "Nothing was fabricated - the evidence already shown for this "
                "Requirement is what there is; the judgment call is yours to make "
                "from it, or ask again once this is configured."
            ),
        )

    trigger = AnalysisTrigger(
        trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
        trigger_reference_type="conversation_message" if triggering_message_id else None,
        trigger_reference_id=triggering_message_id,
        triggered_by_actor=reviewer,
    )
    # CLAUDE-P36: engine_name/engine_version come from the provider
    # boundary's OWN record of what it called (result.provider/
    # result.model), not a second, independently-read env var here - the
    # two could otherwise silently disagree if investigate_requirement
    # were ever called with an explicit model= override.
    analysis = store.record_analysis(
        workspace,
        case_id=case["id"],
        source_ids=[requirement["source_id"]],
        objective=text,
        engine_name=f"{result.provider}-requirement-investigation",
        engine_version=result.model,
        findings=[{"statement": result.assessment, "machine_confidence": result.confidence}],
        trigger=trigger,
    )

    step = store.record_investigation_step(
        workspace,
        case_id=case["id"],
        step_kind=INVESTIGATION_STEP_KIND_REQUIREMENT_INVESTIGATION,
        anchor=anchor,
        question=text,
        triggered_by_actor=reviewer,
        evidence_requested=evidence_requested,
        evidence_examined_ids=evidence_examined_ids,
        ran=True,
        assessment=result.assessment,
        confidence=result.confidence,
        supporting_points=result.supporting_points,
        open_questions=result.open_questions,
        needs_human_judgment=result.needs_human_judgment,
        analysis_id=analysis["id"],
    )

    # CLAUDE-P12R: an attributed annotation of what this looks like FROM
    # the represented party's position - never a rewrite of the
    # Requirement/Finding above, and never recorded when no represented
    # party was set (so risk_polarity is None and this is skipped).
    if represented_party is not None and result.risk_polarity:
        store.record_perspective_assessment(
            workspace,
            anchor=anchor,
            participant_id=represented_party["id"],
            polarity=result.risk_polarity,
            origin=PERSPECTIVE_ORIGIN_MACHINE,
            reasoning=result.risk_reasoning or result.assessment,
            confidence=result.risk_confidence,
            investigation_step_id=step["id"],
        )

    # CLAUDE-P13R: opportunistic autonomous branching - begun inside
    # reasoning already legitimately running here, never a scheduler.
    # Bounded by a real confidence threshold AND CaseWorkspaceStore's own
    # stop conditions (a project-wide cap, a same-anchor duplicate
    # check) - both checked before anything is created. Opening this
    # Case is not itself authority (see create_autonomous_case's own
    # docstring); it only ever asserts "there is enough here to
    # investigate."
    branch_case = None
    if (
        result.suggested_branch
        and (result.suggested_branch_confidence or 0) >= AUTONOMOUS_BRANCH_CONFIDENCE_THRESHOLD
        and store.can_open_autonomous_case_for(workspace, anchor)
    ):
        branch_title = (
            result.suggested_branch if len(result.suggested_branch) <= 80
            else result.suggested_branch[:77] + "..."
        )
        branch_case = store.create_autonomous_case(
            workspace, title=branch_title, objective=result.suggested_branch,
            anchor=anchor, spawned_from_step_id=step["id"], governance_log=governance_log,
        )

    reply_parts = [f"Assessment (confidence {result.confidence:.0%}): {result.assessment}"]
    if result.supporting_points:
        reply_parts.append("Based on: " + "; ".join(result.supporting_points))
    if result.open_questions:
        reply_parts.append("Open question(s) for you: " + "; ".join(result.open_questions))
    if result.risk_polarity:
        reply_parts.append(
            f"From {represented_party['name']}'s position, this reads as "
            f"{result.risk_polarity} (confidence {result.risk_confidence:.0%}): {result.risk_reasoning}"
        )
    if branch_case is not None:
        reply_parts.append(
            f"This also surfaced a separate, sufficiently-grounded concern, so a new "
            f"provisional Investigation was opened on its own: \"{branch_case['title']}\" - "
            "opening it isn't a claim that it's true, only that it's worth looking into; "
            "review it like any other Case."
        )
    if result.needs_human_judgment:
        reply_parts.append(
            "This needs your professional judgment before it's treated as anything "
            "more than a provisional Finding."
        )
    reply_parts.append(
        "Recorded as a provisional machine Finding in this Investigation's Artifact "
        "Workspace - review it there like any other."
    )

    return InterpretationResult(
        action_taken=f"analysis:{analysis['id']}",
        reply_text=" ".join(reply_parts),
    )


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


def _handle_project_question(
    text: str,
    workspace: ProjectWorkspace,
    case: Optional[dict],
    store: CaseWorkspaceStore,
    reviewer: str,
    triggering_message_id: Optional[str],
) -> InterpretationResult:
    """
    CLAUDE-P38 (OBS-01): a real, grounded read-only answer via
    services/project_qa.py's Anthropic call - never a Finding, never an
    Artifact, no governed record beyond the ConversationMessage the
    caller already persists either way. Requires no open Case (unlike
    _handle_investigate_requirement): there is nothing here that needs
    one to hold it.

    Policy-gated exactly like _handle_investigate_requirement
    (services.security_policy.evaluate_action, resolved via the same
    _evaluate_external_ai_policy this module already defines for that
    call site) - this is the second real external-AI transmission this
    file can trigger, and it must not bypass the same governed action.

    CLAUDE-POSTCAMEL-CA1 (Section 5): `case` (optional, matching
    interpret_message's own param) selects which real conversation
    thread the bounded recent-history window is drawn from - this
    Case's own `conversation` list, or `workspace.project_conversation`
    when case is None - so a Requirement/Investigation-scoped question
    never sees another Case's or another Project's history. The current
    human message (already persisted by the caller before this runs) is
    excluded from the window since it is passed separately as
    `question`.
    """
    policy_decision = _evaluate_external_ai_policy(store, workspace)
    if policy_decision.decision not in (DECISION_ALLOW, DECISION_ALLOW_APPROVED_ROUTE):
        denial_reason = (
            f"Answering questions about this project using external AI is not "
            f"permitted by this project's security policy (controlling layer: "
            f"{policy_decision.controlling_layer}). {policy_decision.reason} "
            f"Nothing was transmitted."
        )
        return InterpretationResult(
            action_taken=f"project_qa_policy_denied:{policy_decision.controlling_layer}",
            reply_text=denial_reason,
        )

    from services.requirements_registry import RequirementsRegistry

    document = RequirementsRegistry(store.store_path).get(workspace.project_id)
    candidate_requirements = (
        [{"text": r.text, "category": r.category} for r in document.requirements] if document else []
    )
    milestones = list(document.milestones) if document else []
    document_filename = document.filename if document else "(unknown source document)"

    # CLAUDE-POSTCAMEL-CA1 (Section 5): the same conversation thread this
    # reply will itself be appended to, minus the just-persisted current
    # human message (it is passed separately as `question` below) -
    # never another Case's or Project's messages.
    thread = case["conversation"] if case is not None else workspace.project_conversation
    recent_history = [
        {"role": m.get("role"), "text": m.get("text")} for m in thread[:-1]
    ] if thread else []

    result = answer_project_question(
        question=text,
        document_filename=document_filename,
        candidate_requirements=candidate_requirements,
        governed_requirements=list(workspace.requirements),
        milestones=milestones,
        # CLAUDE-P40-B (3.6): the Project's own human-assigned display
        # name (services.case_workspace.set_project_details) was never
        # passed here before - the model had no way to distinguish "the
        # Project's name" from "the raw uploaded filename" because
        # nothing else was ever offered to it.
        display_title=workspace.display_title,
        recent_history=recent_history,
    )

    if not result.ran:
        return InterpretationResult(
            action_taken="project_qa_unavailable",
            reply_text=(
                f"I can't answer that from this project's evidence right now: "
                f"{result.skipped_reason} Nothing was fabricated."
            ),
            # CLAUDE-POSTCAMEL-CA1 (Section 23): a dead end still offers a
            # real, concrete next step rather than only prose.
            next_steps=[{"label": "Open Requirements", "view": "requirements"}],
        )

    # CLAUDE-P40-B (3.6): reply_text is now the direct answer plus only
    # the short honesty notes (not_covered/needs_clarification) - never
    # the grounding citations, which used to be concatenated straight
    # into the same string and could visually swallow a short, direct
    # answer under a long provenance/citation tail (confirmed via a real
    # product-owner walkthrough: "began by treating the uploaded
    # filename as the document name... then repeated substantial
    # revision and provenance text"). grounded_in now travels on its own
    # field, rendered behind a collapsed disclosure by the template.
    reply_parts = [result.answer]
    if result.not_covered:
        reply_parts.append("Not covered by this project's extracted evidence: " + result.not_covered)
    if result.needs_clarification:
        reply_parts.append(
            "This evidence alone isn't enough to answer fully - treat this as a "
            "starting point, not a complete answer."
        )

    return InterpretationResult(
        action_taken="project_qa_answered",
        reply_text=" ".join(reply_parts),
        grounded_in=result.grounded_in,
    )


def _handle_quantitative_investigation(
    text: str,
    workspace: ProjectWorkspace,
    case: dict,
    store: CaseWorkspaceStore,
    reviewer: str,
    triggering_message_id: Optional[str],
) -> InterpretationResult:
    """
    CLAUDE-P40-VW8-QA-R6: a general, reusable evidence-guided
    quantitative pattern (distance/elevation-difference/slope/clearance
    feasibility) - see services/quantitative_investigation.py's own
    header for the full capability-boundary reasoning (no drawing OCR/
    measurement extraction, no hardcoded regulatory slope, no external-
    AI call - every value here is a number the reviewer has directly
    typed into this Case's own conversation, deterministic arithmetic
    only).

    Re-scans the WHOLE Case conversation (not just this one message) so
    a value confirmed several messages ago is still "remembered" -
    conversation history is the only persistence this uses; no new
    working-memory data model is introduced (see this file's own
    header on why: Finding remains a plain statement string, exactly
    as it already was).
    """
    all_text = [m.get("text", "") for m in case["conversation"]] + [text]
    value_lists = [quant.extract_values_from_text(t) for t in all_text]
    confirmed = quant.merge_values(*value_lists)

    has_drawing_source = bool(
        any(
            s["id"] in case["source_ids"] and s["kind"] == "drawing"
            for s in CaseWorkspaceStore.active_sources(workspace)
        )
    )

    # The question text itself: the EARLIEST prior message in this
    # conversation that looked like the question, so a later message
    # that only supplies a value (and may itself also happen to match
    # the same keyword trigger, e.g. "Available length is 22m") never
    # displaces the ORIGINAL question - never truncated either way
    # (Section: "the user's full question must not be replaced by a
    # truncated title"). Falls back to the current message only when
    # this is genuinely the first one to ever match.
    question_text = next(
        (m["text"] for m in case["conversation"]
         if quant.looks_like_quantitative_feasibility_question((m.get("text") or "").lower())),
        text,
    )

    missing = quant.missing_fields(confirmed)
    if missing:
        return InterpretationResult(
            action_taken="quantitative_investigation_in_progress",
            reply_text=quant.build_progress_reply(question_text, confirmed, has_drawing_source),
        )

    available = confirmed.get("available_travel_length")
    calc = quant.compute_feasibility(
        entrance_grade=confirmed["entrance_grade_elevation"].value,
        basement_grade=confirmed["basement_grade_elevation"].value,
        slope_percent=confirmed["longitudinal_slope_percent"].value,
        available_travel_length=available.value if available else None,
    )
    calculation_reply = quant.build_calculation_reply(calc, confirmed)

    if available is None:
        # Section "Finding behavior": "only create a candidate Finding
        # after the relevant evidence and assumptions are visible" - a
        # feasibility comparison isn't visible yet without an available
        # length, so no Finding is created for this reply; the
        # calculation so far is still shown transparently, plus a
        # specific ask for the one remaining input.
        return InterpretationResult(
            action_taken="quantitative_investigation_calculated",
            reply_text=(
                calculation_reply + " To compare against what's actually available, I still need the "
                f"{quant.FIELD_LABELS['available_travel_length']}." +
                quant.build_source_guidance(has_drawing_source)
            ),
        )

    unresolved = []
    if calc.additional_length == 0.0:
        unresolved.append("top/bottom transitions and required landing/curved geometry not yet stated")
    if not has_drawing_source:
        unresolved.append("no drawing Source attached - values are reviewer-stated, not drawing-measured")

    width = confirmed.get("driveway_width")
    statement = quant.build_finding_statement(question_text, confirmed, calc, width, unresolved)

    trigger = AnalysisTrigger(
        trigger_type=ANALYSIS_TRIGGER_USER_INITIATED,
        trigger_reference_type="conversation_message" if triggering_message_id else None,
        trigger_reference_id=triggering_message_id,
        triggered_by_actor=reviewer,
    )
    analysis = store.record_analysis(
        workspace,
        case_id=case["id"],
        source_ids=list(case["source_ids"]),
        objective=question_text,
        engine_name="quantitative_investigation",
        engine_version="p40-vw8qa-r6",
        findings=[{"statement": statement, "machine_confidence": 0.5}],
        trigger=trigger,
    )

    return InterpretationResult(
        action_taken=f"quantitative_investigation_finding:{analysis['id']}",
        reply_text=(
            calculation_reply +
            " Recorded as a candidate Finding for your review - provisional until you confirm it; "
            "this is geometric feasibility from stated values, not a regulatory or professional "
            "engineering sign-off."
        ),
    )
