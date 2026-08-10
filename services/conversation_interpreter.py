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
from services.capability_registry import (
    CAPABILITY_STATUS_FUTURE,
    CAPABILITY_STATUS_IMPLEMENTED,
    CAPABILITY_STATUS_PARTIAL,
    CAPABILITIES,
    find_capability_by_phrase,
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
    # CLAUDE-POSTCAMEL-CA1C (Section 6/17): set only by
    # _handle_organize_advice, when a real, safe "Create this structure"
    # action genuinely exists for a real, currently-referenced Source -
    # a structured action envelope (a Source id, never free model
    # prose), rendered by the template as one real POST button that
    # creates real, governed Design-Builder Workspace folders. None
    # whenever no such offer applies.
    organize_source_id: Optional[str] = None
    # CLAUDE-CA1D-RIVER-01 (Project Gravity / River Continuity): the
    # "fourth beat" - a meaningful, evidence-grounded answer should not
    # end as inert prose when a safe, ALREADY-IMPLEMENTED next
    # professional action is available (Section 2's own "River
    # Continuity Rule"). Each entry is a structured envelope, never
    # model-generated prose interpreted as a command (same discipline
    # organize_source_id above already established): {"kind": "task" |
    # "tag", "label": str, "tag_id": str (kind="tag" only)}. Rendered by
    # the template as a real POST button reusing the EXISTING create_task_
    # route/add_tag_occurrence_route unchanged - no new backend mechanism,
    # per Section 7's own "reuse existing mechanisms, do not create a
    # parallel subsystem." Only ever set by _handle_project_question, and
    # only when result.grounded_in is genuinely non-empty (a real,
    # evidence-backed answer - "a response earns an operational
    # continuation only when there is genuine work to continue," Section
    # 10) - never for a "not covered"/policy-denied/unavailable reply,
    # and never reachable at all for a conversational utterance (CA1C-
    # CONV-FIX-02's own gate intercepts those before this handler ever
    # runs - Conversation != Investigation holds by construction, not by
    # a second check here).
    operational_actions: list[dict] = field(default_factory=list)


_FINDING_NUMBER_PATTERN = re.compile(r"finding\s*#?\s*(\d+)", re.IGNORECASE)

# CLAUDE-CA1D-RIVER-01: a deliberately narrow, deterministic phrase set -
# same discipline as every other trigger in this module - used only to
# CONTEXTUALIZE the fourth beat's own label (Section 3's own "the fourth
# beat should be contextual and operational"), never to decide WHETHER
# one is offered at all (that's result.grounded_in alone, checked by the
# caller). A question naming none of these still gets the generic label.
_DEADLINE_TOPIC_PHRASES = (
    "deadline", "due date", "due by", "milestone", "schedule", "timeline", "submission date",
)
_RISK_TOPIC_PHRASES = (
    "risk", "concern", "conflict", "issue", "problem",
)


def _operational_action_label(question_lowered: str) -> str:
    if any(phrase in question_lowered for phrase in _DEADLINE_TOPIC_PHRASES):
        return "Make a Task to track these deadlines"
    if any(phrase in question_lowered for phrase in _RISK_TOPIC_PHRASES):
        return "Make a Task to address this"
    return "Make a Task from this"


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
    current_view: Optional[str] = None,
    selected_source_id: Optional[str] = None,
    selected_object: Optional[dict] = None,
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

    CLAUDE-POSTCAMEL-CA1B (Sections 4/5): `selected_object` (same shape
    as `anchor` - anchor_type/anchor_id) is the caller's persisted
    "professional context" slot (Requirement/Finding/Source), read from
    session, ALREADY superseded by `anchor` whenever this specific
    message carries one (the caller sets/reads persisted state in that
    order - see routes/workspace.py's own _run_conversation_turn).
    Deliberately NOT consulted by the pre-existing needs_case/
    is_requirement_investigation_question/anchor_acknowledged grammar
    below, which remains exactly as anchor-only as it always was - only
    the CA1A contextual-reference layer (Section 12: "extend the
    existing mechanism," not build a second one) honors it, via
    `effective_referent` below.
    """
    lowered = text.strip().lower()

    if not lowered:
        return InterpretationResult(
            action_taken="none",
            reply_text="No instruction was recognized in an empty message.",
        )

    # CLAUDE-CA1C-CONV-FIX-02: checked FIRST, before ANY Investigation-
    # shaped routing below (needs_case, is_requirement_investigation_
    # question, is_quantitative_question) - a greeting must never be
    # evaluated against "does this need a Case" logic at all, not merely
    # win a tiebreak against it once evaluated. Anchor is deliberately
    # ignored here - an anchored "hello" is still just a greeting.
    if _looks_like_conversational_utterance(lowered):
        return _handle_conversational_utterance(reviewer)

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

    # CLAUDE-POSTCAMEL-CA1A (Sections 2/3): never trust a client-
    # submitted current_view/selected_source_id blindly - re-validate
    # both against THIS workspace before they influence anything.
    # current_view against a fixed allowlist; selected_source_id by a
    # real per-workspace lookup, exactly the same "None for a stale/
    # foreign id, never an error" convention routes/workspace.py's own
    # show_workspace already uses for ?source=.
    validated_current_view = current_view if current_view in _KNOWN_CURRENT_VIEWS else None
    validated_selected_source = next(
        (s for s in workspace.sources if s["id"] == selected_source_id), None,
    ) if selected_source_id else None

    # CLAUDE-POSTCAMEL-CA1B (Section 5, context precedence): the
    # CA1A contextual-reference layer's own referent, extended -
    # THIS message's own explicit anchor always wins (freshest, most
    # explicit signal); otherwise the persisted "professional context"
    # slot (Requirement/Finding/Source, whichever was selected most
    # recently by anchor or by a real ?requirement=/?finding=/?source=
    # visit); a stale/foreign persisted id degrades to None exactly like
    # anchor already does (_resolve_anchor_object's own real per-
    # workspace lookup, not trusted merely because it's in session). A
    # persisted Source falls through to validated_selected_source below
    # only when even the persisted slot is empty, per this stage's own
    # explicit "current selected object" > "current view context"
    # ordering.
    effective_referent = anchor if anchor is not None else selected_object

    # CLAUDE-POSTCAMEL-CA1A (Section 10): "what should I do next" gets
    # its own dedicated handler, checked ahead of the generic anchor
    # fallback, so it can use whatever real context IS available
    # (anchor, selected Source) and honestly fall back to Project
    # Orientation (itself real, deterministic, evidence-based) when
    # nothing more specific is selected - never generic PM advice
    # invented without grounding.
    if _looks_like_what_next(lowered):
        return _handle_what_should_i_do_next(workspace, effective_referent, validated_selected_source)

    # CLAUDE-POSTCAMEL-CA1C (Sections 3/4/13): a question about
    # ARCHIOSK's OWN capability ("Can you create folders?") must be
    # answered from Application Capability Knowledge, never from
    # Project evidence - answering "not covered by the Project
    # evidence" here would be a category error (Section 4's own named
    # example). Only intercepts when a self-referential phrase AND a
    # positively-identified capability keyword both match - if the
    # phrase merely LOOKS self-referential ("Can you tell me...") but no
    # specific capability is identified, this falls through to ordinary
    # handling below rather than forcing a wrong answer.
    if _looks_like_capability_question(lowered):
        matched_capability = find_capability_by_phrase(lowered)
        if matched_capability is not None:
            return _handle_capability_question(matched_capability)

    # CLAUDE-POSTCAMEL-CA1C (Sections 1/2/6/9/19): "should I organize
    # this into folders" is a professional-advice question, not an
    # evidence lookup - answered with a constructive recommendation
    # first, a real vertical structure grounded in this Project's own
    # already-extracted candidate items (never a hardcoded universal
    # taxonomy), and a real, truthful next action. Resolves the Source
    # to organize from whatever real referent is available (an anchor,
    # or CA1B's own persisted/URL selection) - asks which Source if none
    # exists, never guesses (Section 19).
    if _looks_like_organize_question(lowered):
        referent_type, referent_object = _resolve_anchor_object(workspace, effective_referent)
        source_for_organize = referent_object if referent_type == "source" else validated_selected_source
        return _handle_organize_advice(store, workspace, source_for_organize)

    # CLAUDE-POSTCAMEL-CA1A (Sections 2/4/12/18): a bounded set of
    # pronoun-dependent phrasings ("tell me about this", "show me the
    # evidence for this", ...) - checked unconditionally (whether or not
    # a real referent exists), because _handle_contextual_reference
    # itself already gives the correct answer either way: a real,
    # factual description when an anchor or genuinely selected Source is
    # available, or Section 18's own required honest "I don't have
    # anything specific selected" reply when neither is - never a
    # guessed answer, and never an unnecessary, ungroundable model call
    # for a question this module already knows it cannot ground.
    # Several of these phrases would otherwise also match
    # _looks_like_project_question's own starters ("what", "tell me") -
    # this check runs first deliberately, so an ambiguous "this" is
    # never silently handed to the model to guess at.
    if _looks_like_contextual_reference(lowered):
        return _handle_contextual_reference(
            workspace, effective_referent, validated_selected_source, triggering_message_id, case,
        )

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
        return _handle_project_question(
            text, workspace, case, store, reviewer, triggering_message_id,
            ui_context={
                "current_view": validated_current_view,
                "selected_source_name": validated_selected_source["name"] if validated_selected_source else None,
            },
        )

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


# CLAUDE-CA1C-CONV-FIX-02 (Greetings Must Not Enter Investigation
# Attention): a real Product Owner typed "hello"/"hello hello" into
# Project Home's composer and watched GO create a brand-new Investigation
# for it, which then immediately tripped the four-Investigation attention
# limit's own "Attention is full" dialog - a greeting matched NONE of
# quick_start's existing "stay conversational" exemptions (project
# question, orientation, contextual-reference, what-next), so it fell
# through to the same case-creation path as a real work request.
# "Conversation != Investigation" is the durable principle this stage
# names explicitly - an Investigation requires actual investigative
# intent, not merely any typed message. Deliberately exact-phrase, same
# discipline as every other trigger in this module (still not an attempt
# at general language understanding) - but normalized first (trailing
# punctuation stripped, immediately-repeated words collapsed) so "hello
# hello" and "how are you?" match the same short canonical phrase list
# a raw substring check would otherwise need dozens of literal variants
# to cover.
_CONVERSATIONAL_UTTERANCE_PHRASES = (
    "hello", "hi", "hey", "hiya", "yo",
    "hello there", "hi there", "hey there",
    "good morning", "good afternoon", "good evening", "good night",
    "how are you", "how are things", "how is everything", "how's everything",
    "hows everything", "how's it going", "hows it going",
    "what's up", "whats up", "how do you do",
    "do you hear me", "can you hear me", "are you there", "you there",
    "thanks", "thank you", "thx", "cheers", "much appreciated",
    "ok", "okay", "got it", "sounds good", "cool", "great", "nice",
    "alright", "all right",
    "bye", "goodbye", "see you", "see ya", "take care",
)


def _normalize_for_conversational_check(lowered: str) -> str:
    stripped = lowered.strip().strip("!?.,;:~ ")
    tokens = stripped.split()
    deduped: list[str] = []
    for token in tokens:
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return " ".join(deduped)


def _looks_like_conversational_utterance(lowered: str) -> bool:
    return _normalize_for_conversational_check(lowered) in _CONVERSATIONAL_UTTERANCE_PHRASES


def _handle_conversational_utterance(reviewer: str) -> InterpretationResult:
    """
    The dedicated destination for a greeting/acknowledgment/social check-
    in - never Project evidence, never an Investigation, never an
    attention slot. Personalizes with the reviewer's own name when it's
    a real one (never "Anonymous" or a raw session placeholder), per the
    governing report's own preferred wording ("Hello Mehrzad. What are
    you working on?").
    """
    reviewer_stripped = (reviewer or "").strip()
    display_name = (
        reviewer_stripped.split()[0].capitalize()
        if reviewer_stripped and reviewer_stripped.lower() != "anonymous"
        else None
    )
    greeting = f"Hello {display_name}." if display_name else "Hello."
    return InterpretationResult(
        action_taken="conversational_utterance",
        reply_text=f"{greeting} What are you working on?",
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


# CLAUDE-POSTCAMEL-CA1A (Section 2): the same allowlist as routes/
# workspace.py's own STABLE_DIRECTORY_KINDS keys - duplicated rather
# than imported to avoid a circular import (routes/workspace.py already
# imports FROM this module). Any value outside this set is treated as
# no selection at all, never trusted or passed through, matching this
# module's own "None for a stale/foreign value, never an error"
# convention used throughout.
_KNOWN_CURRENT_VIEWS = frozenset({"overview", "files", "requirements"})

# CLAUDE-POSTCAMEL-CA1A (Section 10): a deliberately narrow, exact-ish
# phrase set for "what should I do next" - same deterministic-keyword
# discipline as every other trigger in this module.
_WHAT_NEXT_PHRASES = (
    "what should i do next", "what should i do", "what do i do next", "what next",
)


def _looks_like_what_next(lowered: str) -> bool:
    stripped = lowered.strip().rstrip("?")
    return stripped in _WHAT_NEXT_PHRASES


# CLAUDE-POSTCAMEL-CA1A (Sections 2/4/12): a bounded set of pronoun-
# dependent phrasings this module can now resolve against a real
# referent (an anchor, or a genuinely viewed Source) - still keyword
# matching, still honest about not understanding anything beyond this
# fixed list, per this file's own long-standing design note.
_CONTEXTUAL_REFERENCE_PHRASES = (
    "what am i looking at", "tell me about this", "what does this mean",
    "show me the evidence for this", "what should i do with this",
    "what can i do with this", "where did this come from",
)


def _looks_like_contextual_reference(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _CONTEXTUAL_REFERENCE_PHRASES)


def _resolve_anchor_object(workspace: ProjectWorkspace, anchor: Optional[dict]):
    """
    CLAUDE-POSTCAMEL-CA1A (Section 3): cross-project-safe by
    construction - every lookup is a real, direct search against THIS
    workspace's own already-project-scoped lists, never a raw id
    trusted on its own. A stale, deleted, or cross-project id simply
    resolves to (anchor_type, None), the same honest "no longer exists"
    convention _handle_investigate_requirement's own Requirement lookup
    already uses - never an error, never a guess.
    """
    if anchor is None:
        return None, None
    anchor_type = anchor.get("anchor_type")
    anchor_id = anchor.get("anchor_id")
    if anchor_type == "requirement":
        return anchor_type, next((r for r in workspace.requirements if r["id"] == anchor_id), None)
    if anchor_type == "finding":
        return anchor_type, next((f for f in workspace.findings if f["id"] == anchor_id), None)
    if anchor_type == "source":
        return anchor_type, next((s for s in workspace.sources if s["id"] == anchor_id), None)
    return anchor_type, None


def _handle_what_should_i_do_next(
    workspace: ProjectWorkspace, anchor: Optional[dict], selected_source: Optional[dict],
) -> InterpretationResult:
    """
    CLAUDE-POSTCAMEL-CA1A (Section 10): considers whatever real referent
    is actually available (an anchor first, then a genuinely selected
    Source) before ever falling back to Project Orientation - never
    generic, ungrounded PM advice. No model call anywhere in this path -
    fully deterministic, same discipline as _handle_project_orientation.
    """
    anchor_type, anchor_object = _resolve_anchor_object(workspace, anchor)
    if anchor_type is not None and anchor_object is None:
        return InterpretationResult(
            action_taken="what_next_stale_reference",
            reply_text=(
                f"That {anchor_type.replace('_', ' ')} no longer exists in this Project, so I can't "
                "offer anything specific about it. Ask a general project question, or open Files/"
                "Requirements to pick something current."
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )
    if anchor_type == "requirement" and anchor_object is not None:
        return InterpretationResult(
            action_taken="what_next_requirement",
            reply_text=(
                f"You're looking at {anchor_object['original_requirement_identifier']}. I can show its "
                "source evidence, its adjudication history, or you can ask a direct question about it."
            ),
            next_steps=[{"label": "Open Requirements", "view": "requirements"}],
        )
    if anchor_type == "finding" and anchor_object is not None:
        return InterpretationResult(
            action_taken="what_next_finding",
            reply_text=(
                "You're looking at a Finding. I can start an Investigation from it if one isn't open "
                "yet, or you can ask what it's grounded in."
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )
    if selected_source is not None:
        return InterpretationResult(
            action_taken="what_next_source",
            reply_text=(
                f"You're currently viewing \"{selected_source['name']}\". I can help you map its "
                "contents, suggest a Project structure around it (advisory only), or start an "
                "Investigation on it."
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )
    return _handle_project_orientation(workspace)


def _handle_contextual_reference(
    workspace: ProjectWorkspace, anchor: Optional[dict], selected_source: Optional[dict],
    triggering_message_id: Optional[str], case: Optional[dict] = None,
) -> InterpretationResult:
    """
    CLAUDE-POSTCAMEL-CA1A (Sections 2/4/12/18): a real, factual,
    deterministic description of whatever the reviewer's "this"/"it"
    actually refers to - an anchor first (a click is a stronger signal
    than a merely-open Source), else a genuinely selected Source. Never
    hallucinates a referent: with neither, says so plainly and offers a
    real way to establish one, instead of guessing (Section 18).

    Where a real Investigation-starting affordance is genuinely useful
    (a Requirement/Finding/Source, and NO Case is already open - `case`
    is passed through only to gate this), this reuses the EXISTING
    `needs_case:` escalation mechanism - the same "Start an
    Investigation from this" button already rendered and tested
    elsewhere on this page - rather than building a second, parallel
    action-execution path (Section 8's own "preserve that lesson" about
    never creating a surprise Investigation from ambiguous language;
    this offer is a button the PM must still click, never automatic).
    Offering to "start" one while a Case is ALREADY open would be
    semantically wrong (and template dead weight - the escalation
    button only renders in the project-level conversation loop), so
    that offer is only ever made when `case is None`.
    """
    anchor_type, anchor_object = _resolve_anchor_object(workspace, anchor)
    offer_investigation = case is None and triggering_message_id is not None

    if anchor_type is not None and anchor_object is None:
        return InterpretationResult(
            action_taken="contextual_reference_stale",
            reply_text=(
                f"That {anchor_type.replace('_', ' ')} no longer exists in this Project - I can't "
                "describe it. Open Files or Requirements to find something current."
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )

    def _closing(subject: str) -> str:
        if offer_investigation:
            return f" Start an Investigation below if you want to look into {subject} further, or ask a direct question about it."
        return f" Ask a direct question about {subject} if you'd like."

    if anchor_type == "requirement" and anchor_object is not None:
        return InterpretationResult(
            action_taken=f"needs_case:{triggering_message_id}" if offer_investigation else "contextual_reference",
            reply_text=(
                f"You're looking at {anchor_object['original_requirement_identifier']} "
                f"(status: {anchor_object['status']}): \"{anchor_object['text_reference'][:200]}\"."
                f"{_closing('it')}"
            ),
            next_steps=[{"label": "Open Requirements", "view": "requirements"}],
        )

    if anchor_type == "finding" and anchor_object is not None:
        return InterpretationResult(
            action_taken=f"needs_case:{triggering_message_id}" if offer_investigation else "contextual_reference",
            reply_text=(
                f"You're looking at a Finding: \"{anchor_object['statement'][:200]}\"."
                f"{_closing('what it is grounded in')}"
            ),
        )

    if anchor_type == "source" and anchor_object is not None:
        return InterpretationResult(
            action_taken=f"needs_case:{triggering_message_id}" if offer_investigation else "contextual_reference",
            reply_text=(
                f"You're looking at the Source \"{anchor_object['name']}\" ({anchor_object['kind']})."
                f"{_closing('its contents')}"
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )

    if selected_source is not None:
        return InterpretationResult(
            action_taken=f"needs_case:{triggering_message_id}" if offer_investigation else "contextual_reference",
            reply_text=(
                f"You're currently viewing the Source \"{selected_source['name']}\" "
                f"({selected_source['kind']})."
                f"{_closing('it')}"
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )

    return InterpretationResult(
        action_taken="contextual_reference_unavailable",
        reply_text=(
            "I don't have anything specific selected right now, so I can't tell what \"this\" "
            "refers to. Open a Source or Requirement, or use \"Discuss this...\" where you see it, "
            "then ask again - or ask a general project question instead."
        ),
        next_steps=[{"label": "Open Files", "view": "files"}],
    )


# CLAUDE-POSTCAMEL-CA1C (Section 3/13): self-referential phrasing - the
# question is about ARCHIOSK itself, not this Project's own material.
# Deliberately checked ALONGSIDE (not instead of) a real capability-
# keyword match (see interpret_message's own call site) so a genuine
# project question that merely happens to start "Can you tell me..."
# is never hijacked into a capability answer it doesn't deserve.
_CAPABILITY_SELF_REFERENCE_PHRASES = (
    "can you", "can archiosk", "does archiosk", "are you able to",
    "is archiosk able to", "do you support", "does this application support",
    # CLAUDE-VOICE1-DIAG-01: a real Product Owner asked "Are you capable
    # of ..." - a natural synonym for "are you able to" the original list
    # missed, sending the question to the generic project-QA path instead
    # of this deterministic capability-question handler.
    "are you capable of", "is archiosk capable of",
)


def _looks_like_capability_question(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _CAPABILITY_SELF_REFERENCE_PHRASES)


def _handle_capability_question(capability) -> InterpretationResult:
    """
    CLAUDE-POSTCAMEL-CA1C (Sections 4/5/13): answered ENTIRELY from
    Application Capability Knowledge (services/capability_registry.py) -
    no workspace, no Source, no Project evidence of any kind is ever
    consulted here, by construction (this function receives only the
    already-matched Capability, nothing else). Truthful per status:
    never claims an unavailable/future capability is available, never
    hedges an implemented one with unnecessary disclaimers.
    """
    if capability.status == CAPABILITY_STATUS_IMPLEMENTED:
        reply = capability.description
    elif capability.status == CAPABILITY_STATUS_PARTIAL:
        reply = capability.description
    elif capability.status == CAPABILITY_STATUS_FUTURE:
        reply = f"Not yet. {capability.description}"
    else:
        reply = f"No. {capability.description}"
        if capability.alternative:
            alternative = CAPABILITIES[capability.alternative]
            reply += f" What I can do instead: {alternative.description}"
    return InterpretationResult(action_taken=f"capability_question:{capability.key}", reply_text=reply)


# CLAUDE-POSTCAMEL-CA1C (Sections 1/2/6/9): a deliberately narrow
# phrase set for "should I organize this" - the exact live scenario
# that triggered this tranche, per this file's own long-standing
# deterministic-keyword discipline.
_ORGANIZE_QUESTION_PHRASES = (
    "should i organize", "how should i organize", "organize this into folders",
    "organize this rfp", "organize it into folders", "organize this document",
    "should this be organized", "how do i organize",
    # CLAUDE-VOICE1-DIAG-01: real Product Owner usage asked this with
    # "divide"/"split", never the literal word "organize" - without
    # these, the question silently fell through to the older, generic
    # project-QA path instead of this handler.
    "divide this into", "divide the main file", "divide it into different folder",
    "into different folder", "into a different folder", "how to divide the main file",
    "suggest how to divide", "should i divide", "how should i divide",
    "split this into", "split it into folders", "how do i split",
)


def _looks_like_organize_question(lowered: str) -> bool:
    return any(phrase in lowered for phrase in _ORGANIZE_QUESTION_PHRASES)


# CLAUDE-POSTCAMEL-CA1C (Section 20): maps the REAL, already-extracted
# candidate-Requirement category vocabulary (services/bhive_parser.py's
# own REQUIREMENT_CATEGORIES - never a new document-analysis engine) to
# a small set of readable organizational group names. Only groups with
# at least one real extracted item are ever proposed - never a
# hardcoded universal construction taxonomy (Section 6's own explicit
# instruction).
_CATEGORY_GROUP_LABELS = {
    "submission_instruction": "Procurement",
    "evaluation_criteria": "Procurement",
    "scope_of_work": "Technical / Scope",
    "technical_specification": "Technical / Scope",
    "compliance_legal": "Commercial / Legal",
    "budget_commercial": "Commercial / Legal",
    "schedule_milestone": "Schedule / Milestones",
    "other": "Appendices",
}
_ORGANIZE_GROUP_ORDER = [
    "Procurement", "Technical / Scope", "Commercial / Legal", "Schedule / Milestones", "Appendices",
]


def compute_organize_groups(store: CaseWorkspaceStore, workspace: ProjectWorkspace) -> list[str]:
    """
    CLAUDE-POSTCAMEL-CA1C (Section 20): the one, shared, real
    computation behind both the conversational proposal
    (_handle_organize_advice) and the real "Create this structure"
    action (routes/workspace.py's own apply_organize_structure) - a
    single source of truth, so what the PM is shown is always exactly
    what would be created, never a mismatch between promise and result.
    """
    from services.requirements_registry import RequirementsRegistry

    document = RequirementsRegistry(store.store_path).get(workspace.project_id)
    candidate_items = document.requirements if document else []

    return [
        group for group in _ORGANIZE_GROUP_ORDER
        if any(_CATEGORY_GROUP_LABELS.get(item.category, "Appendices") == group for item in candidate_items)
    ]


def _handle_organize_advice(
    store: CaseWorkspaceStore, workspace: ProjectWorkspace, source: Optional[dict],
) -> InterpretationResult:
    """
    CLAUDE-POSTCAMEL-CA1C (Sections 1/6/8/9/19): "Answer first, explain
    only what matters, offer the next action" - a constructive
    recommendation, a real project-grounded vertical structure, and a
    truthful next action, never a defensive "only you can decide"
    opener for what is plainly an advice-seeking question. Territory
    Before Ontology is preserved throughout: the original Source is
    never touched, moved, or duplicated by this function - only a real,
    recoverable, governed Design-Builder Workspace Folder structure is
    ever proposed or (on a later, explicit "Create this structure"
    click) created.
    """
    if source is None:
        return InterpretationResult(
            action_taken="organize_advice_no_referent",
            reply_text=(
                "Which Source should I organize? Open it, or use \"Discuss this Source\" where you "
                "see it, then ask again."
            ),
            next_steps=[{"label": "Open Files", "view": "files"}],
        )

    present_groups = compute_organize_groups(store, workspace)

    if not present_groups:
        return InterpretationResult(
            action_taken="organize_advice_insufficient_structure",
            reply_text=(
                f"Keep \"{source['name']}\" intact - there isn't enough extracted structure from it yet "
                "for a grounded recommendation. Ask me a specific question about it, or register "
                "governed Requirements from it first, then ask again."
            ),
        )

    structure_lines = "\n".join(f"- {group}" for group in present_groups)
    reply = (
        f"Yes. Keep \"{source['name']}\" intact and organize it virtually first - nothing physical is "
        "created or moved unless you ask.\n\n"
        "Recommended structure (based on what's actually extracted from this project so far):\n"
        f"{structure_lines}\n\n"
        "This creates a real, governed Design-Builder Workspace structure, not a change to the "
        "original document."
    )
    return InterpretationResult(
        action_taken=f"organize_advice:{source['id']}",
        reply_text=reply,
        organize_source_id=source["id"],
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
    ui_context: Optional[dict] = None,
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
        ui_context=ui_context,
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

    # CLAUDE-CA1D-RIVER-01: the fourth beat, offered only for a genuinely
    # evidence-grounded answer (grounded_in non-empty) - a "not covered"/
    # unclear reply has no real work to continue and gets none. "Make a
    # Task" and "Highlight this answer" are the two candidate actions
    # Section 5's own list names that are ALREADY genuinely implemented
    # end-to-end today (create_task_route, add_tag_occurrence_route) -
    # every other candidate in that list (Create Finding, Add to Risk
    # Register, Delegate) is deliberately omitted, not merely disabled,
    # per Section 9's own "never show an action GO cannot actually
    # perform" capability-truth requirement.
    operational_actions: list[dict] = []
    if result.grounded_in:
        # Same truncation convention routes/workspace.py's own quick_start
        # already uses for a Case title - "Follow up: " names what the
        # Task is actually about (the question), never the full answer
        # text, which the Task's own anchor/provenance already preserves
        # in full via anchor_quote.
        follow_up_title = f"Follow up: {text}"
        if len(follow_up_title) > 80:
            follow_up_title = follow_up_title[:77] + "..."
        operational_actions = [
            {"kind": "task", "label": _operational_action_label(text.lower()), "default_title": follow_up_title},
            {"kind": "tag", "label": "Highlight this answer", "tag_id": "built-in:highlight"},
        ]

    return InterpretationResult(
        action_taken="project_qa_answered",
        reply_text=" ".join(reply_parts),
        grounded_in=result.grounded_in,
        operational_actions=operational_actions,
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
