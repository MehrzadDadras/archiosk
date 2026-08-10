"""
CLAUDE-P38 (OBS-01) - real, grounded, read-only project-level Q&A.

Mirrors services/requirement_investigation.py's Anthropic integration
pattern exactly (lazy `anthropic` import, api_key/model/timeout read
from the same env vars, a prompt that demands strict JSON with no
prose/markdown fences, honest degrade-on-no-key/timeout/malformed-
output) - that module is this codebase's only precedent for calling a
real model outside ingestion, and inventing a second convention here
would be arbitrary.

Deliberately narrower than a general-purpose assistant: grounded ONLY
in this project's own already-extracted evidence (candidate
RequirementItems, governed Requirements, extracted schedule-related
items, the source filename) - never the model's own world knowledge,
never the Source's full original document text (not currently
queryable in one place for a document Source; see services/
requirement_investigation.py's own docstring on the same limitation).
A question this evidence can't answer gets an honest "not covered",
never a guess - this module never marks its own output as anything
more than a reply; unlike requirement_investigation.py, it creates no
Finding, no Artifact, no governed record of any kind. The human
question and this reply are both already persisted as ordinary
ConversationMessages by the caller (services/case_workspace.py's
add_message, via routes/workspace.py's _run_conversation_turn) -
nothing here duplicates that.
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0
PROVIDER_NAME = "anthropic"

# CLAUDE-P38: a real, bump-on-meaningful-change marker, same discipline
# as services/requirement_investigation.py's INVESTIGATION_PROMPT_VERSION.
# CLAUDE-POSTCAMEL-CA1: bumped (p38a -> ca1a) for the new system-role
# behavioral contract and the optional recent-history section below.
# CLAUDE-POSTCAMEL-CA1A: bumped again (ca1a -> ca1b) for the new
# current-UI-context section and the token-aware (not fixed-count)
# history bounding.
# CLAUDE-POSTCAMEL-CA1C: bumped again (ca1b -> ca1c) for the
# constructive-advice / capability-category-error / concision rules.
# CLAUDE-CA1D-RIVER-PO-01: bumped again (ca1c -> ca1d) for the optional
# river_actions structured field and its own gating rule.
PROJECT_QA_PROMPT_VERSION = "ca1d"

# CLAUDE-CA1D-RIVER-PO-01: a defensive ceiling on the model's own
# river_actions array, independent of the prompt's own "normally 1-5"
# guidance - this is what actually protects the UI from an unbounded
# list, not merely asking nicely. Malformed items (no non-empty "action")
# are dropped outright rather than rendered as a blank heading.
_MAX_RIVER_ACTIONS = 8

_MAX_CANDIDATE_ITEMS_IN_PROMPT = 40
_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT = 40
_MAX_MILESTONES_IN_PROMPT = 20
# CLAUDE-POSTCAMEL-CA1A (Section 5, token-aware continuity): CA1's own
# fixed 6-message cap is replaced by a character-budget walk - a long
# single message could previously still consume the whole window: this
# instead bounds total transmitted continuity by size, not by count,
# while still capping the message COUNT too (_MAX_RECENT_HISTORY_MESSAGES)
# so a long run of very short messages can't produce an unbounded list.
# No new tokenizer dependency - a deterministic character budget, per
# this stage's own "approximate character/token budget rather than a
# large dependency" instruction.
_RECENT_HISTORY_CHAR_BUDGET = 2000
_MAX_RECENT_HISTORY_MESSAGES = 20
_MAX_HISTORY_MESSAGE_CHARS = 300

# CLAUDE-POSTCAMEL-CA1 (Section 6, Behavioral instruction layer): one
# centralized system-role contract for this codebase's real, grounded
# Project Q&A path - deliberately not duplicated per call site. Also
# carries Section 3 (human authority: a suggestion is never an
# instruction, this agent never creates governed records itself) and
# Section 19 (recent conversation is continuity, never Project truth).
BEHAVIORAL_CONTRACT = (
    "You are ARCHIOSK Go, a project-aware assistant embedded in the ARCHIOSK "
    "application, helping a construction/design project professional. Follow "
    "these rules at all times:\n"
    "- Answer only from the project evidence given in this request. Never "
    "invent facts, files, views, or application capabilities that are not "
    "described here.\n"
    "- If the evidence is genuinely insufficient, say so plainly rather than "
    "guessing.\n"
    "- Distinguish stated fact from your own interpretation.\n"
    "- Recent conversation history, if given, is for conversational "
    "continuity only. It is not additional project evidence, and a prior "
    "reply - including your own - is never to be treated as newly-"
    "established project truth.\n"
    "- You may suggest that something become a governed Requirement, "
    "Finding, Task, or Decision, but you never create one yourself - only "
    "the human project manager does that, through ARCHIOSK's own governed "
    "controls.\n"
    "- Never claim to perform an application action you cannot actually "
    "perform.\n"
    "- Never reveal your own private step-by-step reasoning process - state "
    "only your conclusion and the evidence behind it.\n"
    # CLAUDE-POSTCAMEL-CA1A (Section 12, behavioral-contract update):
    # what a PM is currently looking at in the application is advisory
    # context only, never authority - it may resolve what "this"/"it"
    # refers to, but the governed evidence given in this request always
    # outranks it and outranks any conversational assumption. Every
    # object this context ever names has already been validated to
    # belong to the active Project before reaching this prompt (see
    # conversation_interpreter.py's own per-workspace lookups) - never
    # trust a different id if you are ever shown one.\n"
    "- If a \"currently looking at\" context is given below, treat it as "
    "advisory only: it may tell you what \"this\"/\"it\" refers to, but the "
    "governed project evidence always outranks it, and it never outranks "
    "governed evidence or authorizes an action on its own.\n"
    # CLAUDE-POSTCAMEL-CA1C (Sections 1/2/3/4/11/12): a live Product
    # Owner interaction found this agent answering an ordinary advice-
    # seeking question too defensively (opening with "only you can
    # decide" instead of a recommendation) and mixing Project evidence
    # with knowledge of ARCHIOSK's own capabilities. These two rules are
    # the general-path fix; the specific, highest-value case (organizing
    # a Source into folders) additionally has its own real, deterministic
    # handler (services/conversation_interpreter.py's own
    # _handle_organize_advice) that never reaches this model call at all.
    "- If the reviewer is clearly asking for your professional judgment "
    "or recommendation (not asking what the governing Source explicitly "
    "states), give a constructive recommendation first, then only the "
    "reasoning that materially matters. Do not open with \"only you can "
    "decide\" or similar disclaimers for an ordinary advice-seeking "
    "question - human authority still means the reviewer decides whether "
    "to act on it, but that does not require you to be timid in offering "
    "it. Reserve authority disclaimers for moments where a real governed "
    "decision or consequential state change is actually at stake.\n"
    "- This prompt is about the Project only. If the reviewer's question "
    "is actually about what ARCHIOSK itself can do (an application "
    "capability, not this Project's content), you have been routed here "
    "in error - say you're not sure and suggest they ask about the "
    "specific capability directly, rather than answering from this "
    "Project's evidence (doing so would be a category error).\n"
    "- Be concise: prefer a direct recommendation or answer, short "
    "material reasoning, and (if genuinely useful) a next step - not a "
    "restated question, a long introduction, or generic project-"
    "management prose.\n"
    # CLAUDE-CA1D-RIVER-PO-01 (River Action Stack): a live Product Owner
    # review found a genuinely useful answer to "what should I do next"
    # rendered as one dense explanatory paragraph - the wrong information
    # hierarchy for a question asking what deserves attention now. This
    # is a NARROW, semantically-gated structured-output addition, not a
    # general summarization instruction - see river_actions in the
    # requested schema below for exactly when it applies.
    "- If, and only if, the reviewer is asking what deserves attention or "
    "action next (not an ordinary factual or explanatory question), "
    "identify a SMALL set of the most consequential next moves (normally "
    "1-5 - never pad to a fixed count, and never promote something to "
    "this list merely because it exists in the source document) and "
    "return them as river_actions in the schema below, ranked by genuine "
    "consequence (blocking downstream work, gating human authority, an "
    "approaching externally meaningful deadline, resolving important "
    "uncertainty, affecting submission eligibility) - never by document "
    "order, recency, or verbosity. Leave river_actions empty for every "
    "other kind of question - do not force this structure onto ordinary "
    "answers.\n"
    "- Respond only in the exact JSON schema requested, with no prose "
    "outside it."
)


@dataclass
class ProjectQAResult:
    """`ran=False` means no real reasoning happened - a skipped_reason
    is always set in that case. `needs_clarification` is the model's
    OWN signal (part of the requested JSON schema), read back verbatim,
    the same "ask the human when genuinely needed" discipline
    RequirementInvestigationResult.needs_human_judgment already uses."""

    ran: bool
    answer: Optional[str] = None
    grounded_in: list[str] = field(default_factory=list)
    not_covered: Optional[str] = None
    needs_clarification: bool = False
    skipped_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None
    # CLAUDE-CA1D-RIVER-PO-01 (River Action Stack): the model's OWN
    # signal, same "read back verbatim" discipline needs_clarification
    # already uses - empty for every question except one genuinely
    # asking what deserves attention/action next (see BEHAVIORAL_CONTRACT's
    # own gating rule and _build_prompt's own schema instructions). Each
    # item: {"rank": int, "action": str, "rationale": str, "consequence":
    # str, "uncertainty": str, "evidence": list[str]} - defensively
    # parsed in answer_project_question (malformed items dropped, never
    # rendered as a blank heading; capped at _MAX_RIVER_ACTIONS regardless
    # of what the model returns).
    river_actions: list[dict] = field(default_factory=list)


def answer_project_question(
    question: str,
    document_filename: str,
    candidate_requirements: list[dict],
    governed_requirements: list[dict],
    milestones: list[dict],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
    display_title: Optional[str] = None,
    recent_history: Optional[list[dict]] = None,
    ui_context: Optional[dict] = None,
) -> ProjectQAResult:
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ProjectQAResult(
            ran=False,
            skipped_reason="No ANTHROPIC_API_KEY configured - real project Q&A cannot run in this deployment.",
        )

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = timeout if timeout is not None else float(
        os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    requested_at = datetime.now(timezone.utc).isoformat()

    import anthropic  # imported lazily so the dep is optional in dev

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    prompt = _build_prompt(
        question, document_filename, candidate_requirements, governed_requirements, milestones,
        display_title, recent_history, ui_context,
    )

    try:
        response = client.messages.create(
            model=model, max_tokens=1500, system=BEHAVIORAL_CONTRACT,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APITimeoutError:
        logger.warning("Project Q&A timed out after %.0fs.", timeout)
        return ProjectQAResult(ran=False, skipped_reason=f"Request timed out after {timeout:.0f}s.")
    except Exception:  # noqa: BLE001 - best-effort, mirrors requirement_investigation.py's own discipline
        logger.warning("Project Q&A failed.", exc_info=True)
        return ProjectQAResult(ran=False, skipped_reason="An error occurred calling the model.")

    text_out = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            logger.warning("Project Q&A was truncated at max_tokens: %r", text_out[-200:])
            return ProjectQAResult(ran=False, skipped_reason="Model's response was cut off before it finished (max_tokens).")
        logger.warning("Project Q&A returned non-JSON output: %r", text_out[:200])
        return ProjectQAResult(ran=False, skipped_reason="Model returned malformed output.")

    not_covered = parsed.get("not_covered")
    return ProjectQAResult(
        ran=True,
        answer=str(parsed.get("answer", "")).strip(),
        grounded_in=[str(g) for g in parsed.get("grounded_in", [])],
        not_covered=(str(not_covered).strip() or None) if not_covered else None,
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        river_actions=_parse_river_actions(parsed.get("river_actions")),
        provider=PROVIDER_NAME, model=model, requested_at=requested_at,
    )


def _parse_river_actions(raw) -> list[dict]:
    """Defensive parsing, not trust-on-faith: the model's own JSON is
    read back, never executed as a template or reinterpreted - a
    malformed item (no non-empty "action" heading) is dropped outright
    rather than rendered as a blank/broken row, and the list is
    hard-capped at _MAX_RIVER_ACTIONS regardless of what the model
    returned (the prompt's own "normally 1-5" is guidance to the model,
    this is the actual backstop)."""
    if not isinstance(raw, list):
        return []
    parsed_actions: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        action_text = str(item.get("action", "")).strip()
        if not action_text:
            continue
        try:
            rank = int(item.get("rank"))
        except (TypeError, ValueError):
            rank = len(parsed_actions) + 1
        parsed_actions.append({
            "rank": rank,
            "action": action_text,
            "rationale": str(item.get("rationale", "")).strip(),
            "consequence": str(item.get("consequence", "")).strip(),
            "uncertainty": str(item.get("uncertainty", "")).strip(),
            "evidence": [str(e) for e in item.get("evidence", []) if str(e).strip()],
        })
        if len(parsed_actions) >= _MAX_RIVER_ACTIONS:
            break
    parsed_actions.sort(key=lambda a: a["rank"])
    return parsed_actions


def _select_bounded_history(recent_history: list[dict]) -> list[dict]:
    """
    CLAUDE-POSTCAMEL-CA1A (Section 5): walk backwards from the most
    recent message, keeping whole messages (never truncating a message
    mid-sentence just to hit the budget exactly) until either the
    character budget or the message-count cap is reached, then restore
    chronological order. Recent turns are always favored - the OLDEST
    messages are the ones dropped first when the budget is exceeded.
    """
    selected: list[dict] = []
    total_chars = 0
    for message in reversed(recent_history):
        text = (message.get("text") or "").strip()[:_MAX_HISTORY_MESSAGE_CHARS]
        if not text:
            continue
        if selected and (
            total_chars + len(text) > _RECENT_HISTORY_CHAR_BUDGET
            or len(selected) >= _MAX_RECENT_HISTORY_MESSAGES
        ):
            break
        selected.append({"role": message.get("role"), "text": text})
        total_chars += len(text)
    selected.reverse()
    return selected


def _build_prompt(
    question: str, document_filename: str, candidate_requirements: list[dict],
    governed_requirements: list[dict], milestones: list[dict],
    display_title: Optional[str] = None, recent_history: Optional[list[dict]] = None,
    ui_context: Optional[dict] = None,
) -> str:
    lines = [
        "You are assisting a construction/design professional with a read-only "
        "question about a project. Answer ONLY from the governed evidence given "
        "below - never invent facts, dates, names, sections, or content not "
        "present in it. This is NOT the full source document text, only what "
        "has already been extracted from it - if the question needs more than "
        "this evidence provides, say so rather than guessing. Keep \"answer\" "
        "direct and concise (a sentence or two for a factual lookup) - put "
        "supporting detail, excerpts, and provenance in \"grounded_in\" instead "
        "of folding it into the answer itself.",
        "",
        # CLAUDE-P40-B (3.6): a real product-owner walkthrough asked "what "
        # is the name of this document?" and the answer treated the raw
        # uploaded filename as if it were the document's own formal
        # title, then buried the reply under revision/provenance text.
        # This module has no dedicated "detected title" extraction (see
        # this stage's own report on why that's deliberately deferred,
        # not built here) - the fix is prompt discipline: name every
        # identity concept this evidence CAN distinguish, and tell the
        # model which one actually answers an identity question.
        "Identity note: several different things could be called this "
        "project's \"name\", and they are NOT the same:",
        f"- Uploaded filename (mechanical, not authored content): {document_filename}",
    ]
    if display_title:
        lines.append(f"- This Project's own display name, set by a reviewer: {display_title}")
    lines.append(
        "- A formal document title, RFP/document number, issuer, and version MAY "
        "also appear as extracted text below (e.g. in a scope_of_work or "
        "\"other\" candidate item) - if so, that is almost always the better "
        "answer to \"what is the name of this document/RFP\" than the raw "
        "filename. If no such formal title is present in the evidence, say so "
        "and offer the filename as a fallback, clearly labeled as a filename, "
        "not asserted as the document's own title."
    )
    # CLAUDE-POSTCAMEL-CA1A (Section 6, context priority): explicit
    # current-UI context is placed BEFORE the evidence sections below -
    # it helps interpret the question, but the evidence, not this
    # context, is what answers it (governing principle: "Conversation
    # helps interpret the question. Project evidence answers it.").
    # Only ever real, already-validated labels (never raw ids) - see
    # conversation_interpreter.py's own resolution, which never trusts a
    # client-submitted id without checking it against this Project's own
    # workspace first.
    if ui_context and (ui_context.get("current_view") or ui_context.get("selected_source_name")):
        lines.append("\nWhat the reviewer is currently looking at in the application (advisory context, not evidence):")
        if ui_context.get("current_view"):
            lines.append(f"- Current Display view: {ui_context['current_view']}")
        if ui_context.get("selected_source_name"):
            lines.append(f"- Currently open Source: {ui_context['selected_source_name']}")

    lines.append(f"\nSource document: {document_filename}")

    if candidate_requirements:
        lines.append(
            f"\nCandidate items extracted from the document, not yet reviewed by a human "
            f"({len(candidate_requirements)} total, showing up to {_MAX_CANDIDATE_ITEMS_IN_PROMPT}):"
        )
        for item in candidate_requirements[:_MAX_CANDIDATE_ITEMS_IN_PROMPT]:
            lines.append(f"- [{item.get('category', '')}] {item.get('text', '')}")

    if governed_requirements:
        lines.append(
            f"\nGoverned (human-confirmed) Requirements ({len(governed_requirements)} total, "
            f"showing up to {_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT}):"
        )
        for r in governed_requirements[:_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT]:
            lines.append(
                f"- {r.get('original_requirement_identifier', '')}: {r.get('text_reference', '')} "
                f"(status: {r.get('status', '')})"
            )

    if milestones:
        lines.append(
            f"\nSchedule-related items extracted from the document, not yet confirmed "
            f"({len(milestones)} total, showing up to {_MAX_MILESTONES_IN_PROMPT}):"
        )
        for m in milestones[:_MAX_MILESTONES_IN_PROMPT]:
            lines.append(f"- {m.get('label', '')}")

    if not candidate_requirements and not governed_requirements and not milestones:
        lines.append("\nNo requirements or milestones have been extracted from this document yet.")

    # CLAUDE-POSTCAMEL-CA1 (Section 5, bounded multi-turn continuity): a
    # small, fixed-size recent window of THIS SAME project/case
    # conversation only - the caller (conversation_interpreter.py) is
    # responsible for never mixing messages across Projects or Cases.
    # Explicitly framed as continuity, not evidence, both here and in
    # BEHAVIORAL_CONTRACT's own system-role instruction - a prior turn
    # (including this model's own prior reply) must never be treated as
    # newly-established Project truth.
    bounded_history = _select_bounded_history(recent_history) if recent_history else []
    if bounded_history:
        lines.append(
            "\nRecent conversation in this project (most recent last) - for "
            "conversational continuity only, NOT additional project evidence. "
            "A prior reply, including your own, is not guaranteed correct and "
            "is never itself proof of anything:"
        )
        for m in bounded_history:
            speaker = "Reviewer" if m.get("role") == "human" else "ARCHIOSK Go"
            lines.append(f"- {speaker}: {m.get('text', '')}")

    lines.append(f"\nThe reviewer's question: \"{question}\"")
    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"answer": "<direct answer, grounded only in the evidence above; when '
        "quoting, quote exactly and mark it as a quote; otherwise make clear you "
        'are paraphrasing/summarizing>", "grounded_in": ["<short citation of which '
        'item(s) above support this>", ...], "not_covered": "<what the question '
        'asked about that this evidence does not cover, or empty string if fully '
        'covered>", "needs_clarification": <true if the evidence is genuinely '
        'insufficient to answer meaningfully, false otherwise>, "river_actions": '
        '[{"rank": <1-based integer, most consequential first>, "action": '
        '"<short, concrete action heading - what the reviewer should do, not a '
        'restated fact>", "rationale": "<why this was surfaced now - the '
        'consequence signal that earned its rank>", "consequence": "<what this '
        'is blocking, enabling, or affecting downstream if left unaddressed>", '
        '"uncertainty": "<anything you genuinely do not know or cannot safely '
        'infer about this action - empty string if none>", "evidence": ["<short '
        'citation supporting THIS action specifically>", ...]}, ...]}. '
        'river_actions MUST be an empty array [] unless the reviewer is genuinely '
        "asking what deserves attention or action next (see the rule above) - "
        'never populate it for an ordinary factual/explanatory question. When '
        'river_actions is populated, keep "answer" to one short framing sentence '
        "at most (the ranked list itself carries the substance) and put each "
        'action\'s own supporting evidence in that action\'s own "evidence" field '
        'rather than repeating it all in the top-level "grounded_in". If the '
        'evidence given is insufficient, say so plainly in "answer" and list what '
        'is missing in "not_covered" - do not guess.'
    )
    return "\n".join(lines)
