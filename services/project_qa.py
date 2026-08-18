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
Case, no Analysis, no Artifact. The human question and this reply are
both already persisted as ordinary ConversationMessages by the caller
(services/case_workspace.py's add_message, via routes/workspace.py's
_run_conversation_turn) - nothing here duplicates that.

CLAUDE-GO-RIGHT-PANEL-01: this module's own JSON schema now ALSO
optionally carries a small `findings` array (parsed by
_parse_composer_findings below), promoted by the caller
(conversation_interpreter._handle_project_question) into real,
durable services.case_workspace.ComposerFinding records via
store.add_composer_finding - the seam that lets Composer intelligence
become persistent, tagged right-panel project material instead of only
existing as chat prose (see that class's own docstring for why this is
a distinct object from the Case/Analysis-bound Finding). Gated the
SAME defensive way river_actions already is: an ordinary factual
question returns an empty findings array and promotes nothing.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from services.conversational_turn import build_bounded_history, select_relevant_document_evidence
from services.llm_gateway import call_llm_json, resolve_timeout_from_env, scale_timeout_for_prompt_size

logger = logging.getLogger(__name__)

# CLAUDE-CA1D-COMPOSER-TIMEOUT-FIX-01: this module's own scaling base -
# matches services.llm_gateway.DEFAULT_TIMEOUT_SECONDS exactly, so a
# typical short question's timeout is completely unchanged from before
# this fix (prompt stays under scale_timeout_for_prompt_size's own
# 4000-char floor, base_timeout passes through untouched).
DEFAULT_TIMEOUT_SECONDS = 30.0

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
# CLAUDE-CA1D-RIVER-PO-02 (Section A, "compress missing-evidence
# notices"): bumped again (ca1d -> ca1d-po02) for the optional
# missing_evidence_summary field below.
# CLAUDE-GO-RIGHT-PANEL-01: bumped again (ca1d-po02 -> go-rp01) for the
# optional findings structured field and its own gating rule.
PROJECT_QA_PROMPT_VERSION = "go-rp01"

# CLAUDE-CA1D-RIVER-PO-01: a defensive ceiling on the model's own
# river_actions array, independent of the prompt's own "normally 1-5"
# guidance - this is what actually protects the UI from an unbounded
# list, not merely asking nicely. Malformed items (no non-empty "action")
# are dropped outright rather than rendered as a blank heading.
_MAX_RIVER_ACTIONS = 8

# CLAUDE-GO-RIGHT-PANEL-01: same defensive-ceiling discipline as
# _MAX_RIVER_ACTIONS above, applied to the new findings array - the
# actual backstop against an unbounded right-panel list, independent of
# the prompt's own guidance text.
_MAX_COMPOSER_FINDINGS = 10

_MAX_CANDIDATE_ITEMS_IN_PROMPT = 40
_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT = 40
_MAX_MILESTONES_IN_PROMPT = 20
# CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: the additional-document cap/
# excerpt-per-document cap used to be duplicated here AND in services.
# conversational_turn.py (same two numbers, two places that could drift).
# Now defined exactly once, in conversational_turn.py, as select_
# relevant_document_evidence's own default parameters - this module just
# calls that function (below) rather than slicing the list itself.
# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0): the token-aware history-
# bounding walk (was _select_bounded_history/_RECENT_HISTORY_CHAR_BUDGET
# etc., originally added here by CLAUDE-POSTCAMEL-CA1A) now lives in
# services/conversational_turn.py's build_bounded_history, shared by
# every conversational turn, not just a project question.

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
    # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01 (Section 4): evidence
    # SELECTION and evidence AUTHORITY are different questions - a
    # document being relevant enough to include here never means its
    # own content is binding. Some source documents explicitly mark
    # their own status (e.g. "non-binding owner reference," "PROPOSED,"
    # "draft") - carry that status forward exactly as stated, never
    # upgrade it because the document was recently added, closely
    # matches the question, or is the only thing that answers it.\n"
    "- If a document's own content states or implies it is non-binding, "
    "reference-only, proposed, draft, or otherwise not yet authoritative, "
    "say so explicitly in your answer - never present it as a confirmed "
    "requirement or binding fact merely because it was the evidence that "
    "answered the question.\n"
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
    # CLAUDE-GO-RIGHT-PANEL-01: a second, SEPARATE structured-output
    # gate from river_actions above - river_actions answers "what should
    # I do next," findings answers "what discrete issue did you notice
    # and why does it matter." The two are never the same list: a
    # "what's next" question can populate river_actions with nothing
    # characterization-shaped in it, and a "what's wrong" question can
    # populate findings with nothing action-ranked in it. Both stay
    # empty for an ordinary factual question.
    "- If, and only if, the reviewer is genuinely asking you to identify, "
    "characterize, or list discrete issues, discrepancies, gaps, or "
    "unresolved conditions across the project (not an ordinary factual "
    "lookup, and not a \"what should I do next\" question), identify a "
    "SMALL set of the most meaningful ones (normally 1-8 - never pad to a "
    "fixed count, and never invent one merely to fill the list) and return "
    "them as findings in the schema below. For each: a short (a few words) "
    "\"tag\" title; \"source_reference\" citing where in the evidence this "
    "comes from; \"concern\" stating why it matters; \"unresolved_question\" "
    "stating what would need to be resolved. Only include \"urgency\" or "
    "\"project_stage\" when the evidence genuinely supports a specific "
    "value - leave either as an empty string rather than guessing one. "
    "Leave findings empty for every other kind of question.\n"
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
    # CLAUDE-CA1D-RIVER-PO-02 (Section A): a SHORT, compact companion to
    # not_covered - a noun-phrase-style summary ("current extended
    # submission deadline and full RFP Data Sheet"), never a full
    # sentence - populated by the model itself only when river_actions
    # is also populated. not_covered itself is unchanged and still
    # carries the full explanation; this field exists purely so the
    # primary scan path can show a compact line instead of that full
    # sentence when a River Action Stack is present (see
    # conversation_interpreter.py's own use of this field - "keep [full
    # detail] out of the primary scan path unless it changes the
    # immediate decision," never silently dropped).
    missing_evidence_summary: Optional[str] = None
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
    # CLAUDE-GO-RIGHT-PANEL-01: the model's OWN signal, same "read back
    # verbatim, only when genuinely warranted" discipline river_actions
    # already uses - empty for every ordinary factual question, non-empty
    # only when the reviewer is genuinely asking to characterize/identify
    # issues, discrepancies, or unresolved conditions across the project
    # (see BEHAVIORAL_CONTRACT's own gating rule and _build_prompt's own
    # schema instructions). Each item: {"tag": str, "source_reference":
    # str, "concern": str, "unresolved_question": str, "urgency":
    # Optional[str], "project_stage": Optional[str]} - defensively parsed
    # in answer_project_question (malformed items dropped, never rendered
    # as a blank row; capped at _MAX_COMPOSER_FINDINGS regardless of what
    # the model returns). The caller (conversation_interpreter.py's
    # _handle_project_question) is responsible for promoting these into
    # real services.case_workspace.ComposerFinding records - this
    # dataclass itself creates no durable record of any kind, matching
    # this module's own existing "creates no Case, no Analysis, no
    # Artifact" discipline.
    findings: list[dict] = field(default_factory=list)


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
    additional_document_evidence: Optional[list[dict]] = None,
) -> ProjectQAResult:
    prompt = _build_prompt(
        question, document_filename, candidate_requirements, governed_requirements, milestones,
        display_title, recent_history, ui_context, additional_document_evidence,
    )
    # CLAUDE-CA1D-COMPOSER-TIMEOUT-FIX-01: live Product Owner report - a
    # broad, multi-item "characterize every discrepancy in this project,
    # with 5 fields each" question failed with "Request timed out after
    # 30s." Root-caused to TWO compounding gaps, both now fixed:
    #   1. max_tokens=1500 was genuinely too small for this class of
    #      question - reproduced locally, the model was cut off mid-JSON
    #      (stop_reason=max_tokens) before it could finish. Raised to
    #      3000, empirically confirmed sufficient (a real run against the
    #      reported project completed cleanly, stop_reason=end_turn, in
    #      ~28s). Not raised further "to be safe" - 3000 is the smallest
    #      value that was actually observed to complete this class of
    #      query without truncation.
    #   2. This module had NO prompt-size timeout scaling at all (unlike
    #      services/project_briefing.py, which already fixed the exact
    #      same failure mode under CLAUDE-P40-B 3.2) - every question got
    #      the same flat ANTHROPIC_TIMEOUT_SECONDS regardless of prompt
    #      size, leaving no margin for a large evidence blob plus a
    #      genuinely long generation. Reuses
    #      services.llm_gateway.scale_timeout_for_prompt_size (promoted
    #      from project_briefing.py's own private copy for this) with the
    #      SAME already-accepted rate/ceiling (3s per extra 1000 prompt
    #      chars, 90s max). This module's own fixed schema-instruction
    #      boilerplate (BEHAVIORAL_CONTRACT + _build_prompt's own
    #      "respond ONLY with a JSON object..." schema text) is itself
    #      already ~4.4k chars with zero evidence, just over the 4000-char
    #      scaling floor - so even a trivial question's timeout drifts a
    #      little past the base (~31s, not exactly 30s) - harmless, and a
    #      genuinely large evidence blob (like this project's 1310
    #      extracted candidate items) scales up far more, never past this
    #      deployment's own Gunicorn worker timeout (150s) or nginx
    #      proxy_read_timeout (150s on location /, deploy/gunicorn.conf.py
    #      / deploy/nginx.conf) - confirmed via direct inspection before
    #      choosing 90s as the ceiling here.
    base_timeout = resolve_timeout_from_env(timeout, DEFAULT_TIMEOUT_SECONDS)
    timeout = scale_timeout_for_prompt_size(
        base_timeout, prompt,
        base_chars_before_scaling=4000, seconds_per_extra_1000_chars=3.0, max_timeout=90.0,
    )
    # CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0): the client-setup/error-
    # handling/JSON-parsing boundary this module used to own directly is
    # now services/llm_gateway.py's call_llm_json - same behavior, one
    # shared implementation instead of a third independent copy of it.
    outcome = call_llm_json(
        user_prompt=prompt, system_prompt=BEHAVIORAL_CONTRACT,
        api_key=api_key, model=model, timeout=timeout, max_tokens=3000,
        log_label="Project Q&A",
    )
    if not outcome.ran:
        return ProjectQAResult(ran=False, skipped_reason=outcome.skipped_reason)

    parsed = outcome.parsed
    not_covered = parsed.get("not_covered")
    missing_evidence_summary = parsed.get("missing_evidence_summary")
    return ProjectQAResult(
        ran=True,
        answer=str(parsed.get("answer", "")).strip(),
        grounded_in=[str(g) for g in parsed.get("grounded_in", [])],
        not_covered=(str(not_covered).strip() or None) if not_covered else None,
        missing_evidence_summary=(
            (str(missing_evidence_summary).strip() or None) if missing_evidence_summary else None
        ),
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        river_actions=_parse_river_actions(parsed.get("river_actions")),
        findings=_parse_composer_findings(parsed.get("findings")),
        provider=outcome.provider, model=outcome.model, requested_at=outcome.requested_at,
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


def _parse_composer_findings(raw) -> list[dict]:
    """Same defensive-parsing discipline as _parse_river_actions above -
    the model's own JSON is read back, never trusted on faith. A
    malformed item (no non-empty "tag" title) is dropped outright rather
    than rendered as a blank right-panel row; the list is hard-capped at
    _MAX_COMPOSER_FINDINGS regardless of what the model returned.
    `urgency`/`project_stage` are left None (never an empty string
    rendered as if it were a real answer) when the model didn't supply
    them - Section 2's own "do not invent unsupported metadata merely
    to fill fields" applies to a blank-but-present value just as much as
    a fabricated one."""
    if not isinstance(raw, list):
        return []
    parsed_findings: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "")).strip()
        if not tag:
            continue
        urgency = str(item.get("urgency", "")).strip()
        project_stage = str(item.get("project_stage", "")).strip()
        parsed_findings.append({
            "tag": tag,
            "source_reference": str(item.get("source_reference", "")).strip(),
            "concern": str(item.get("concern", "")).strip(),
            "unresolved_question": str(item.get("unresolved_question", "")).strip(),
            "urgency": urgency or None,
            "project_stage": project_stage or None,
        })
        if len(parsed_findings) >= _MAX_COMPOSER_FINDINGS:
            break
    return parsed_findings


def _build_prompt(
    question: str, document_filename: str, candidate_requirements: list[dict],
    governed_requirements: list[dict], milestones: list[dict],
    display_title: Optional[str] = None, recent_history: Optional[list[dict]] = None,
    ui_context: Optional[dict] = None, additional_document_evidence: Optional[list[dict]] = None,
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

    # CLAUDE-CA1D-RECEPTION-FIX-01 (folder establishment): a Project
    # established from a folder can have OTHER real documents beyond the
    # founding one above (e.g. exhibits, addenda) - each item here is
    # {"filename", "relative_path", "excerpts": [...]}, real extracted
    # paragraph text (services.case_workspace.register_plain_text_structure),
    # never the model's own inference about what such a file might
    # contain. Kept in its own section, clearly distinguished from the
    # founding document's own requirements/milestones above (those went
    # through full classification; these did not - "extracted text",
    # never "requirements", for anything here).
    if additional_document_evidence:
        # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: relevance-scored,
        # never merely "the first N by registration order" - see that
        # function's own docstring for the full scoring model. ui_context
        # (validated server-side, never a raw client id - see
        # conversation_interpreter.py's own resolution) supplies which
        # Source, if any, the reviewer currently has open.
        ui_context = ui_context or {}
        shown = select_relevant_document_evidence(
            additional_document_evidence, question,
            selected_source_id=ui_context.get("selected_source_id"),
            selected_source_name=ui_context.get("selected_source_name"),
        )
        # Section 3/7 (explicit-document guarantee, failure honesty): every
        # document's NAME is listed here regardless of whether its excerpts
        # made the selection below, so the model can truthfully distinguish
        # "this document exists in the project but I wasn't given enough of
        # its content" from "no such document exists in this project at
        # all" - the two used to be indistinguishable to it.
        all_names = [d.get("relative_path") or d.get("filename", "") for d in additional_document_evidence]
        lines.append(
            f"\nAll other project documents by name ({len(all_names)} total - not their "
            f"content, just confirming what exists in this project):"
        )
        for name in all_names:
            lines.append(f"- {name}")
        lines.append(
            f"\nExtracted text for the {len(shown)} of those documents most relevant to this "
            f"question (not yet run through requirement classification). If a document you "
            f"need is named above but has no extracted text below, or too little to answer "
            f"confidently, say so plainly rather than answering from a different, less "
            f"relevant document:"
        )
        for doc in shown:
            label = doc.get("relative_path") or doc.get("filename", "")
            lines.append(f"- {label}:")
            for excerpt in doc.get("excerpts", []):
                lines.append(f"  - {excerpt}")

    # CLAUDE-POSTCAMEL-CA1 (Section 5, bounded multi-turn continuity): a
    # small, fixed-size recent window of THIS SAME project/case
    # conversation only - the caller (conversation_interpreter.py) is
    # responsible for never mixing messages across Projects or Cases.
    # Explicitly framed as continuity, not evidence, both here and in
    # BEHAVIORAL_CONTRACT's own system-role instruction - a prior turn
    # (including this model's own prior reply) must never be treated as
    # newly-established Project truth.
    bounded_history = build_bounded_history(recent_history) if recent_history else []
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
        'rather than repeating it all in the top-level "grounded_in"; likewise, '
        'put action-specific evidence GAPS in that action\'s own "uncertainty" '
        'field rather than repeating them in "not_covered". If the evidence '
        'given is insufficient, say so plainly in "answer" and list what is '
        'missing in "not_covered" - do not guess. When river_actions is '
        'populated AND something is genuinely missing, ALSO provide '
        '"missing_evidence_summary": a SHORT, compact, noun-phrase-style '
        'summary of what is missing (e.g. "current extended submission '
        'deadline and full RFP Data Sheet") - never a full sentence, never a '
        "restatement of not_covered's own wording, suitable for a single "
        'scan-path line. Leave "missing_evidence_summary" as an empty string '
        'when nothing is missing, or when river_actions is empty. "findings": '
        '[{"tag": "<a few words - a short descriptive title>", '
        '"source_reference": "<where in the evidence above this comes from>", '
        '"concern": "<why this matters>", "unresolved_question": "<what would '
        'need to be resolved>", "urgency": "<only if the evidence genuinely '
        'supports one - empty string otherwise>", "project_stage": "<only if '
        'the evidence genuinely supports one - empty string otherwise>"}, '
        '...]}. findings MUST be an empty array [] unless the reviewer is '
        "genuinely asking you to identify/characterize/list discrete issues, "
        "discrepancies, gaps, or unresolved conditions across the project (see "
        "the rule above) - never populate it for an ordinary factual/"
        "explanatory question, and never populate it merely because "
        'river_actions was also populated (they answer different questions).'
    )
    return "\n".join(lines)
