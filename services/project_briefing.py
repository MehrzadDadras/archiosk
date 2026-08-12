"""
CLAUDE-P38-B -- narrative-first project opening: a real, grounded
synthesis of the ingested source document into an Executive Summary,
Project Brief (Basis of Understanding), Procurement Route narrative,
and Matters Requiring Early Attention.

Mirrors services/project_qa.py's (and, before it, services/
requirement_investigation.py's) Anthropic integration pattern exactly -
same env vars, same honest-degrade-on-no-key/timeout/malformed-output
discipline. The difference from project_qa.py is SCOPE, not mechanism:
this generates an unprompted, multi-section synthesis rather than
answering one specific question, so it asks for more structured JSON
back - but the same rule governs both: never state something the
evidence doesn't support, and say so plainly when it doesn't.

Deliberately excludes anything requiring real derivation this module
cannot honestly do: no date arithmetic (fixed/relative wording from
the source is preserved verbatim by the caller, via the same
document.milestones already surfaced in CLAUDE-P38's Key Dates fix -
this module is never asked to calculate an actual date), no
estimating/financial calculation, no procurement-sequence assertion
beyond what the source's own extracted requirement candidates actually
establish. A Technical/Financial Submission split this module cannot
find real evidence for is reported as empty, never guessed at.

This is explicitly a MACHINE-ASSISTED DRAFT, not an approved Project
Charter - every caller of this module's output must say so, and this
module's own prompt says so to the model as well, so nothing in
`project_brief` reads with false authority.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from services.llm_gateway import call_llm_json, resolve_timeout_from_env

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 45.0

# CLAUDE-P38-B: bump on meaningful prompt/schema changes, same
# discipline as services/requirement_investigation.py's
# INVESTIGATION_PROMPT_VERSION and services/project_qa.py's
# PROJECT_QA_PROMPT_VERSION.
PROJECT_BRIEFING_PROMPT_VERSION = "p38b"

_MAX_ITEMS_PER_CATEGORY_IN_PROMPT = 30

# CLAUDE-P40-B (3.2): see generate_project_briefing's own comment at the
# call site for the full investigation. A compact document's prompt
# comfortably fits under _BASE_CHARS_BEFORE_SCALING - the timeout only
# ever grows past base_timeout once the prompt is genuinely larger than
# that, and never past _MAX_TIMEOUT_SECONDS regardless of size.
_BASE_CHARS_BEFORE_SCALING = 4000
_TIMEOUT_SECONDS_PER_EXTRA_1000_CHARS = 3.0
_MAX_TIMEOUT_SECONDS = 90.0


def _scale_timeout_for_prompt_size(base_timeout: float, prompt: str) -> float:
    extra_chars = max(0, len(prompt) - _BASE_CHARS_BEFORE_SCALING)
    scaled = base_timeout + (extra_chars / 1000.0) * _TIMEOUT_SECONDS_PER_EXTRA_1000_CHARS
    return min(scaled, _MAX_TIMEOUT_SECONDS)


@dataclass
class ProjectBriefingResult:
    """`ran=False` means no real synthesis happened - a skipped_reason
    is always set in that case, and the caller must never persist or
    display a briefing from it. Every string/list field is `None`/
    empty when the model found no real evidence to support it - never
    filled in with a plausible-sounding guess."""

    ran: bool
    executive_summary: Optional[str] = None
    objectives: list[str] = field(default_factory=list)
    project_brief: Optional[str] = None
    procurement_route: Optional[str] = None
    matters_requiring_attention: list[str] = field(default_factory=list)
    # CLAUDE-P38-D2 (Section 7): a small, honest set of short excerpts
    # pulled from the SAME extracted evidence given to the model, cited
    # back so a reader can see what grounded the synthesis - not a full
    # per-sentence citation system (out of scope per this stage's own
    # "compact, not a large subsystem" instruction), and never fabricated:
    # the model is asked to quote existing extracted text verbatim, not
    # generate new supporting text.
    grounded_in: list[str] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None


def generate_project_briefing(
    document_filename: str,
    candidate_requirements: list[dict],
    governed_requirements: list[dict],
    milestones: list[dict],
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> ProjectBriefingResult:
    prompt = _build_prompt(document_filename, candidate_requirements, governed_requirements, milestones)
    # CLAUDE-P40-B (3.2): confirmed live via a real product-owner
    # walkthrough - a larger Project's Briefing generation failed with
    # "Request timed out after 30s" while a smaller one succeeded. Root
    # cause traced precisely: the base timeout is an APPLICATION timeout
    # (the Anthropic SDK's own timeout=, sourced from .env's
    # ANTHROPIC_TIMEOUT_SECONDS), not an HTTP/provider/job-state one -
    # 30s is comfortably enough for a small prompt but not for a larger,
    # category-diverse document's proportionally larger one. The
    # operator's own configured value is respected as a FLOOR, never
    # reduced - this only extends it upward for a larger prompt, capped
    # well under this deployment's own Gunicorn worker timeout (150s,
    # deploy/gunicorn.conf.py) and nginx proxy_read_timeout (150s,
    # deploy/nginx.conf), so a genuinely slow generation still degrades
    # to this module's own honest timeout message, never a raw 502/504.
    # CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0): resolve_timeout_from_env is
    # the one piece of env resolution this module still needs directly -
    # it must scale FROM a base value before call_llm_json ever sees the
    # final timeout, so call_llm_json must not silently re-derive its own
    # default and discard this scaling.
    base_timeout = resolve_timeout_from_env(timeout, DEFAULT_TIMEOUT_SECONDS)
    timeout = _scale_timeout_for_prompt_size(base_timeout, prompt)

    outcome = call_llm_json(
        user_prompt=prompt, api_key=api_key, model=model, timeout=timeout,
        max_tokens=2500, log_label="Project briefing generation",
    )
    if not outcome.ran:
        return ProjectBriefingResult(ran=False, skipped_reason=outcome.skipped_reason)

    parsed = outcome.parsed
    return ProjectBriefingResult(
        ran=True,
        executive_summary=(str(parsed.get("executive_summary", "")).strip() or None),
        objectives=[str(o) for o in parsed.get("objectives", [])],
        project_brief=(str(parsed.get("project_brief", "")).strip() or None),
        procurement_route=(str(parsed.get("procurement_route", "")).strip() or None),
        matters_requiring_attention=[str(m) for m in parsed.get("matters_requiring_attention", [])],
        grounded_in=[str(g) for g in parsed.get("grounded_in", [])],
        provider=outcome.provider, model=outcome.model, requested_at=outcome.requested_at,
    )


def deterministic_sections(candidate_requirements: list[dict], milestones: list[dict]) -> dict:
    """
    CLAUDE-P38-B: everything here is a plain grouping of already-
    extracted data (RequirementItem.category, document.milestones,
    both from CLAUDE-P38/earlier) - no AI call, always available
    regardless of policy/API-key state, and always correct in the
    sense that it can never say more than the extraction itself
    already says. This is deliberately kept separate from
    generate_project_briefing's real synthesis above: a caller with no
    AI access at all still gets this much, honestly.

    `reading_path` is deliberately curated, not a dump of every raw
    category with its count (CLAUDE-P38-C: the browser retest found
    "Other extracted items (917)" and "Compliance and legal (210)"
    presented as the primary reading route - a category total is not a
    document section, and 'other'/'compliance_legal' specifically carry
    no real navigational meaning). Only categories with real, human-
    meaningful reading value are included, in a practical order,
    capped at 8-10 entries; 'other' and 'compliance_legal' are never
    part of this route (their items still exist and are still
    reachable through the full Requirements register - this only
    changes what's offered as a SUGGESTED route).

    Technical/Financial/Key Dates are each additionally filtered
    through a bounded exclusion/inclusion pass (_qualifies_as_technical/
    _qualifies_as_financial/_qualifies_as_key_date, below) - the same
    "narrow, high-precision pattern, not a classifier rewrite"
    discipline CLAUDE-P38 OBS-09's cover-page-metadata filter already
    established. An item the filter is unsure about is left OUT of the
    curated/preview lists (never included on a guess) but never
    deleted - `technical_submission_items`/`financial_submission_items`
    /`key_dates` are the FILTERED lists; the raw, unfiltered candidate
    set remains fully visible in the ordinary Requirements section this
    module doesn't touch.
    """
    by_category: dict[str, list[dict]] = {}
    for item in candidate_requirements:
        by_category.setdefault(item.get("category", "other"), []).append(item)

    technical_items = [
        item for item in (by_category.get("technical_specification", []) + by_category.get("submission_instruction", []))
        if _qualifies_as_technical(item.get("text", ""))
    ]
    financial_items = [
        item for item in by_category.get("budget_commercial", [])
        if _qualifies_as_financial(item.get("text", ""))
    ]
    key_dates = [
        item for item in milestones
        if _qualifies_as_key_date(item.get("label", ""))
    ]

    reading_order = [
        ("scope_of_work", "Project purpose, objectives, and scope", by_category.get("scope_of_work", [])),
        ("submission_instruction", "Submission Requirements", by_category.get("submission_instruction", [])),
        ("technical_specification", "Technical Submission", technical_items),
        ("budget_commercial", "Financial Submission", financial_items),
        ("schedule_milestone", "Key Dates and Milestones", key_dates),
        ("evaluation_criteria", "Evaluation Criteria", by_category.get("evaluation_criteria", [])),
    ]
    reading_path = []
    for category, label, items in reading_order:
        if not items:
            continue
        reading_path.append({
            "label": label,
            "category": category,
            "item_count": len(items),
            "first_item": items[0],
        })

    return {
        "scope_items": by_category.get("scope_of_work", []),
        "technical_submission_items": technical_items,
        "financial_submission_items": financial_items,
        "evaluation_items": by_category.get("evaluation_criteria", []),
        "key_dates": key_dates,
        "reading_path": reading_path[:10],
    }


# CLAUDE-P38-C: exclusion patterns first (checked before any inclusion
# signal) - a clause matching one of these is a real risk of misleading
# inclusion regardless of what else it says, so exclusion always wins.
# Every pattern here was chosen to match one of this stage's own
# concrete reported false positives.

# CLAUDE-P38-D2: found live during P38-C's own verification - a bare
# section heading like "Section 3 - Financial Submission" was swept
# into the Financial preview because it literally contains the phrase
# "financial submission". P38-C's first fix only recognized an ASCII
# hyphen; P38-D1's diagnosis confirmed real headings use en/em dashes,
# colons, semicolons, or no punctuation at all before a plain title
# ("Schedule 7 — Mandatory Demonstration Protocol" was NOT caught).
# Redesigned as two steps rather than one enumerated-punctuation regex:
# (1) recognize a heading-word + number PREFIX, tolerant of whatever
# punctuation (or none) follows it; (2) treat everything after that
# prefix as a bare title UNLESS it contains a real verb/modal - "Section
# 2.2 - Proponents shall submit..." still classifies normally (the
# remainder has "shall"), while "Schedule 15 - Output Specifications"
# does not (the remainder is a noun phrase with no verb at all).
_HEADING_PREFIX_PATTERN = re.compile(
    r"^\s*(section|schedule|appendix|part|article|clause)\s+\d+(\.\d+)*\s*[-–—:;.]*\s*",
    re.IGNORECASE,
)
_SENTENCE_VERB_PATTERN = re.compile(
    r"\b(shall|must|will|shall\s+not|is|are|does|do|has|have|includes?|requires?|means|"
    r"submit|provide|demonstrat|comply|conform)\b",
    re.IGNORECASE,
)


def _looks_like_bare_heading(text: str) -> bool:
    stripped = text.strip()
    match = _HEADING_PREFIX_PATTERN.match(stripped)
    if not match:
        return False
    remainder = stripped[match.end():].strip()
    if not remainder:
        return True
    return not _SENTENCE_VERB_PATTERN.search(remainder)


# CLAUDE-P38-D2: descriptive, present/perfect-tense background prose
# ("3.2 CMC information is presently distributed among multiple
# document classes...") describes the CURRENT information environment,
# not a proponent submission obligation - P38-D1 confirmed the
# then-current filter had no way to tell these apart from a real
# requirement that happens to share topic vocabulary. This is a bounded
# heuristic on common descriptive-tense phrasing, not real sentence-role
# classification (see this module's own module docstring on that
# honesty boundary) - an item using none of these phrasings but that is
# still just background prose can still slip through; this narrows the
# risk, it does not eliminate it.
_BACKGROUND_PROSE_PATTERNS = re.compile(
    r"is\s+presently|are\s+presently|is\s+currently|are\s+currently"
    r"|has\s+historically|have\s+historically"
    r"|information\s+is\s+distributed|is\s+distributed\s+among"
    r"|the\s+current\s+(environment|state|system)|existing\s+systems?"
    r"|(sponsors?|owners?|proponents?)\s+currently\s+use",
    re.IGNORECASE,
)

_TECHNICAL_EXCLUSION_PATTERNS = re.compile(
    r"material\s+deviat|materially\s+deviat"
    r"|privacy\s+legislation|held\s+in\s+confidence|in\s+confidence\s+and\s+subject"
    r"|the\s+sponsor\s+(reserves|may|shall)\b"
    r"|^\s*(definitions?|means\b|shall\s+mean)\b",
    re.IGNORECASE,
)
# CLAUDE-P38-D2: tightened from "any of these bare topic words" to
# requiring an actual obligation-shaped phrase - P38-D1 found that
# standalone nouns like "specification"/"validation"/"demonstrat" (no
# verb) were the exact words that let bare headings slip through
# classification even after the heading-prefix check; requiring them to
# appear WITH an obligation verb removes that path without excluding
# genuine short requirements like "All structural steel shall conform
# to CSA G40.21 350W" (still matches via "shall conform").
_TECHNICAL_INCLUSION_SIGNALS = re.compile(
    r"shall\s+(be|include|meet|comply|conform|submit|provide|demonstrat|complete|design)"
    r"|must\s+(be|include|submit|provide|demonstrat|comply|conform)"
    r"|(shall|will|must)\s+\w+\s+(submit|provide|design|demonstrat)"
    r"|submit(ted|ting)?\s+(a|the|an)\s+\w*\s*(design|technical|drawing|methodology|narrative|proposal)"
    r"|comply\s+with|conform\s+to",
    re.IGNORECASE,
)


def _qualifies_as_technical(text: str) -> bool:
    if _looks_like_bare_heading(text):
        return False
    if _TECHNICAL_EXCLUSION_PATTERNS.search(text):
        return False
    if _BACKGROUND_PROSE_PATTERNS.search(text):
        return False
    return bool(_TECHNICAL_INCLUSION_SIGNALS.search(text))


_FINANCIAL_EXCLUSION_PATTERNS = re.compile(
    r"cost(s)?\s+of\s+prepar|prepar(ing|ation)\s+(and\s+submitting\s+)?(its|their|the)\s+proposal"
    r"|bear\s+(all\s+)?costs?|at\s+its\s+own\s+(cost|expense)"
    r"|travel|attend(ing|ance)\s+at\s+(any\s+)?meetings?|due\s+diligence",
    re.IGNORECASE,
)
# CLAUDE-P38-D2: P38-D1's diagnosis found the browser-reported Financial
# false positives were all bare headings (fixed above via
# _looks_like_bare_heading), not content-level over-inclusion - these
# nouns are already reasonably precise financial-submission vocabulary
# (fee/bond/tax/escalation/pricing form), unlike Technical's broader
# terms, so left as a noun-based signal rather than forcing the same
# obligation-phrase restructuring onto evidence that didn't call for it.
_FINANCIAL_INCLUSION_SIGNALS = re.compile(
    r"price|pricing|\bfee\b|estimate|bond|financial\s+security|\btax(es)?\b|escalation"
    r"|allowance|contingency|\brate(s)?\b|\$|budget|financial\s+submission|commercial\s+(proposal|submission)",
    re.IGNORECASE,
)


def _qualifies_as_financial(text: str) -> bool:
    if _looks_like_bare_heading(text):
        return False
    if _FINANCIAL_EXCLUSION_PATTERNS.search(text):
        return False
    if _BACKGROUND_PROSE_PATTERNS.search(text):
        return False
    return bool(_FINANCIAL_INCLUSION_SIGNALS.search(text))


_KEY_DATE_EXCLUSION_PATTERNS = re.compile(
    r"reserves?\s+the\s+right\s+to\s+(amend|change|revise)\s+(this\s+|the\s+)?(timetable|schedule)"
    r"|^\s*schedule\s+of\s+events\s*$",
    re.IGNORECASE,
)
# A genuine temporal marker: a number+unit ("18 months", "80 Business
# Days"), a relative-anchor phrase ("after", "prior to", "no later
# than", "within"), or a month name / explicit date shape - required so
# a bare stage NAME with no timing content (e.g. a "Schedule of Events"
# heading standing alone) doesn't qualify merely because it was
# classified schedule_milestone. Deliberately does NOT include a bare
# "following" - found during this stage's own live verification to
# false-positive on ordinary prose ("the following stages shall
# apply..."), unlike "after", which reads as temporal far more
# reliably. The digit+unit pattern alone already covers the governing
# example ("80 Business Days after Commercial Close" matches via "80
# Business Days" regardless of "after").
_KEY_DATE_INCLUSION_SIGNALS = re.compile(
    r"\d+\s*(business\s+)?(day|week|month|year)s?\b"
    r"|no\s+later\s+than|within\s+\d+|\bafter\s+\w|prior\s+to"
    r"|deadline|due\s+(date|by)|\bby\s+\d|validity\s+period|submission\s+window"
    r"|january|february|march|april|may|june|july|august|september|october|november|december"
    r"|\d{4}-\d{2}-\d{2}",
    re.IGNORECASE,
)


def _qualifies_as_key_date(label: str) -> bool:
    if _KEY_DATE_EXCLUSION_PATTERNS.search(label):
        return False
    return bool(_KEY_DATE_INCLUSION_SIGNALS.search(label))


def _build_prompt(
    document_filename: str, candidate_requirements: list[dict],
    governed_requirements: list[dict], milestones: list[dict],
) -> str:
    lines = [
        "You are drafting a MACHINE-ASSISTED opening briefing for a construction/design "
        "professional about to review a procurement document - NOT an approved Project "
        "Charter, and you must never write as though it were one. Answer ONLY from the "
        "governed evidence given below - never invent a party, duty, date, dependency, "
        "or fact not present in it. This is NOT the full source document text, only what "
        "has already been extracted from it - where the evidence doesn't establish "
        "something (e.g. no Financial Submission requirement was found at all), say so "
        "by leaving the relevant field empty rather than guessing.",
        "",
        f"Source document: {document_filename}",
    ]

    by_category: dict[str, list[dict]] = {}
    for item in candidate_requirements:
        by_category.setdefault(item.get("category", "other"), []).append(item)

    category_labels = {
        "scope_of_work": "Scope of Work",
        "technical_specification": "Technical Specification",
        "compliance_legal": "Compliance / Legal",
        "budget_commercial": "Budget / Commercial",
        "schedule_milestone": "Schedule / Milestone",
        "submission_instruction": "Submission Instruction",
        "evaluation_criteria": "Evaluation Criteria",
        "other": "Other",
    }
    for category, label in category_labels.items():
        items = by_category.get(category, [])
        if not items:
            continue
        lines.append(f"\n{label} items extracted from the document ({len(items)} total, showing up to {_MAX_ITEMS_PER_CATEGORY_IN_PROMPT}):")
        for item in items[:_MAX_ITEMS_PER_CATEGORY_IN_PROMPT]:
            lines.append(f"- {item.get('text', '')}")

    if governed_requirements:
        lines.append(f"\nGoverned (human-confirmed) Requirements ({len(governed_requirements)}):")
        for r in governed_requirements[:_MAX_ITEMS_PER_CATEGORY_IN_PROMPT]:
            lines.append(f"- {r.get('original_requirement_identifier', '')}: {r.get('text_reference', '')}")

    if milestones:
        lines.append(f"\nSchedule-related items extracted from the document ({len(milestones)}):")
        for m in milestones[:_MAX_ITEMS_PER_CATEGORY_IN_PROMPT]:
            lines.append(f"- {m.get('label', '')}")

    if not candidate_requirements and not milestones:
        lines.append("\nNo requirements or milestones have been extracted from this document yet.")

    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"executive_summary": "<2-4 sentences: what the project is, why the '
        "procurement was issued, what the owner/client is seeking, the delivery/"
        'procurement model if evident, principal scope, anticipated outcome - '
        'grounded only in the evidence above; empty string if the evidence is too '
        'thin for an honest summary>", "objectives": ["<a stated project '
        'objective, as grounded in the evidence>", ...], "project_brief": '
        '"<a short synthesis covering project context, scope boundaries, major '
        "deliverables, principal parties and stated responsibilities, constraints "
        'and assumptions, and known gaps - empty string if not supportable>", '
        '"procurement_route": "<the documented procurement sequence (RFQ/RFP/'
        "clarification/submission/evaluation/award/commercial-close stages) "
        'ONLY where the evidence actually establishes a sequence - empty string '
        'if it does not>", "matters_requiring_attention": ["<a concrete, '
        "evidence-grounded observation - unclear scope, missing acceptance "
        "criteria, conflicting source language, unresolved responsibility, "
        'incomplete dates - never a fabricated concern>", ...], "grounded_in": '
        '["<a short excerpt (under ~25 words) COPIED VERBATIM from one of the '
        "extracted items above that materially supports the executive_summary "
        "or project_brief - never paraphrased, never invented; pick at most "
        '5-8, the ones that most directly ground your synthesis>", ...]}. '
        "Every field may be empty (string \"\" or empty array) - an honest gap "
        "is always better than a plausible-sounding invention."
    )
    return "\n".join(lines)
