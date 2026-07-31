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

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 45.0
PROVIDER_NAME = "anthropic"

# CLAUDE-P38-B: bump on meaningful prompt/schema changes, same
# discipline as services/requirement_investigation.py's
# INVESTIGATION_PROMPT_VERSION and services/project_qa.py's
# PROJECT_QA_PROMPT_VERSION.
PROJECT_BRIEFING_PROMPT_VERSION = "p38b"

_MAX_ITEMS_PER_CATEGORY_IN_PROMPT = 30


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
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return ProjectBriefingResult(
            ran=False,
            skipped_reason="No ANTHROPIC_API_KEY configured - a real project briefing cannot be generated in this deployment.",
        )

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = timeout if timeout is not None else float(
        os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )
    requested_at = datetime.now(timezone.utc).isoformat()

    import anthropic  # imported lazily so the dep is optional in dev

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    prompt = _build_prompt(document_filename, candidate_requirements, governed_requirements, milestones)

    try:
        response = client.messages.create(
            model=model, max_tokens=2500, messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APITimeoutError:
        logger.warning("Project briefing generation timed out after %.0fs.", timeout)
        return ProjectBriefingResult(ran=False, skipped_reason=f"Request timed out after {timeout:.0f}s.")
    except Exception:  # noqa: BLE001 - best-effort, mirrors project_qa.py's own discipline
        logger.warning("Project briefing generation failed.", exc_info=True)
        return ProjectBriefingResult(ran=False, skipped_reason="An error occurred calling the model.")

    text_out = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        if response.stop_reason == "max_tokens":
            logger.warning("Project briefing was truncated at max_tokens: %r", text_out[-200:])
            return ProjectBriefingResult(ran=False, skipped_reason="Model's response was cut off before it finished (max_tokens).")
        logger.warning("Project briefing returned non-JSON output: %r", text_out[:200])
        return ProjectBriefingResult(ran=False, skipped_reason="Model returned malformed output.")

    return ProjectBriefingResult(
        ran=True,
        executive_summary=(str(parsed.get("executive_summary", "")).strip() or None),
        objectives=[str(o) for o in parsed.get("objectives", [])],
        project_brief=(str(parsed.get("project_brief", "")).strip() or None),
        procurement_route=(str(parsed.get("procurement_route", "")).strip() or None),
        matters_requiring_attention=[str(m) for m in parsed.get("matters_requiring_attention", [])],
        provider=PROVIDER_NAME, model=model, requested_at=requested_at,
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

    `reading_path` orders categories into the practical sequence a
    reviewer would want (objectives/scope -> technical -> financial ->
    dates -> evaluation -> other), each entry carrying enough of the
    real item to be useful and, where the item has a source_line, a
    citation - never a synthetic "location" this module can't back up
    (no in-browser line-anchored source viewer exists yet; callers link
    to the Source's own file instead).
    """
    by_category: dict[str, list[dict]] = {}
    for item in candidate_requirements:
        by_category.setdefault(item.get("category", "other"), []).append(item)

    reading_order = [
        ("scope_of_work", "Project purpose, objectives, and scope"),
        ("technical_specification", "Technical Submission"),
        ("submission_instruction", "Submission instructions"),
        ("budget_commercial", "Financial Submission"),
        ("schedule_milestone", "Dates and milestones"),
        ("evaluation_criteria", "Evaluation and demonstrations"),
        ("compliance_legal", "Compliance and legal"),
        ("other", "Other extracted items"),
    ]
    reading_path = []
    for category, label in reading_order:
        items = by_category.get(category, [])
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
        "technical_submission_items": (
            by_category.get("technical_specification", []) + by_category.get("submission_instruction", [])
        ),
        "financial_submission_items": by_category.get("budget_commercial", []),
        "evaluation_items": by_category.get("evaluation_criteria", []),
        "key_dates": list(milestones),
        "reading_path": reading_path,
    }


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
        'incomplete dates - never a fabricated concern>", ...]}. Every field may '
        "be empty (string \"\" or empty array) - an honest gap is always better "
        "than a plausible-sounding invention."
    )
    return "\n".join(lines)
