"""
Real Requirement investigation - Requirements as the single proving
ground for genuine reasoning behind the Conversation aperture (see
conversation_interpreter.py's own docstring for why THAT file stays
deterministic keyword matching while THIS one is not: the keyword
matcher's job is only to recognize that an investigation-shaped
question was asked, never to answer it).

Mirrors services/bhive_parser.py's existing Anthropic integration
pattern exactly - lazy `anthropic` import (optional dependency), api_key/
model/timeout read from the same env vars, a prompt that demands strict
JSON with no prose/markdown fences, and honest degrade-on-no-key/
timeout/malformed-output (never a fabricated result) - because that
pattern is this codebase's only precedent for calling a real model, and
inventing a second convention here would be arbitrary.

Deliberately ONE request/response round trip, exactly like every
existing Anthropic call in this app - no tool use, no re-prompting, no
multi-step worklist decomposition or branching. Building that honestly
(the model requesting specific evidence lookups as auditable steps,
rather than everything being stuffed into one prompt up front) is a
genuinely separate, larger piece of orchestration infrastructure this
module does not attempt - see the accompanying analysis delivered
alongside this file for what that would need.

Context given to the model is deliberately narrow: THIS Requirement's
own recorded fields, its full adjudication history, and its existing
linked Findings/Relationships/AcceptedKnowledge (via
CaseWorkspaceStore.requirement_evidence) - not the Source's full
original document text (not currently queryable in one place for a
document Source; see the analysis) and not every other Requirement in
the Project (which would balloon prompt size for a scope this pass
deliberately keeps narrow: one Requirement, one question).
"""
from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 30.0


@dataclass
class RequirementInvestigationResult:
    """
    `ran=False` means no real reasoning happened - a skipped_reason is
    always set in that case, and no Finding must ever be recorded from
    it. `needs_human_judgment` is the model's OWN signal (part of the
    requested JSON schema), read back verbatim rather than silently
    resolved - this is how "ask the human when professional judgment is
    needed" stays honest instead of becoming a hidden default.
    """

    ran: bool
    assessment: Optional[str] = None
    confidence: Optional[float] = None
    supporting_points: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    needs_human_judgment: bool = True
    skipped_reason: Optional[str] = None


def investigate_requirement(
    question: str,
    requirement: dict,
    adjudication_history: list[dict],
    evidence: dict,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> RequirementInvestigationResult:
    api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return RequirementInvestigationResult(
            ran=False,
            skipped_reason="No ANTHROPIC_API_KEY configured - real investigation cannot run in this deployment.",
        )

    model = model or os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    timeout = timeout if timeout is not None else float(
        os.getenv("ANTHROPIC_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
    )

    import anthropic  # imported lazily so the dep is optional in dev

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)
    prompt = _build_prompt(question, requirement, adjudication_history, evidence)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APITimeoutError:
        logger.warning("Requirement investigation timed out after %.0fs.", timeout)
        return RequirementInvestigationResult(
            ran=False, skipped_reason=f"Request timed out after {timeout:.0f}s.",
        )
    except Exception:  # noqa: BLE001 - best-effort, mirrors bhive_parser's own consistency-check discipline
        logger.warning("Requirement investigation failed.", exc_info=True)
        return RequirementInvestigationResult(
            ran=False, skipped_reason="An error occurred calling the model.",
        )

    text_out = "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )
    cleaned = re.sub(r"^```(json)?|```$", "", text_out.strip(), flags=re.MULTILINE).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("Requirement investigation returned non-JSON output: %r", text_out[:200])
        return RequirementInvestigationResult(
            ran=False, skipped_reason="Model returned malformed output.",
        )

    return RequirementInvestigationResult(
        ran=True,
        assessment=str(parsed.get("assessment", "")).strip(),
        confidence=float(parsed.get("confidence", 0.5)),
        supporting_points=[str(p) for p in parsed.get("supporting_points", [])],
        open_questions=[str(q) for q in parsed.get("open_questions", [])],
        needs_human_judgment=bool(parsed.get("needs_human_judgment", True)),
    )


def _build_prompt(
    question: str, requirement: dict, adjudication_history: list[dict], evidence: dict,
) -> str:
    lines = [
        "You are assisting a construction/design professional reviewing a governed "
        "contract Requirement. Answer ONLY from the governed evidence given below - "
        "never invent facts, dates, names, or outcomes not present in it.",
        "",
        f"Requirement ({requirement.get('original_requirement_identifier', '')}): "
        f"{requirement.get('text_reference', '')}",
    ]
    if requirement.get("classification"):
        lines.append(f"Classification: {requirement['classification']}")
    if requirement.get("subject_domain"):
        lines.append(f"Subject domain: {requirement['subject_domain']}")

    if adjudication_history:
        lines.append("\nAdjudication history (oldest first):")
        for a in adjudication_history:
            lines.append(f"- {a['outcome']} by {a['adjudicator']} on {a['adjudicated_at']}: {a['reasoning']}")
    else:
        lines.append("\nNo Adjudication has been recorded against this Requirement yet.")

    findings = evidence.get("findings", [])
    if findings:
        lines.append("\nLinked Findings:")
        for f in findings:
            lines.append(f"- ({f.get('claim_status', '')}) {f.get('statement', '')}")

    relationships = evidence.get("relationships", [])
    if relationships:
        lines.append("\nLinked Relationships:")
        for r in relationships:
            lines.append(f"- {r['from_type']} {r['relationship_type']} {r['to_type']}")

    knowledge = evidence.get("accepted_knowledge", [])
    if knowledge:
        lines.append("\nAccepted project knowledge citing this Requirement:")
        for k in knowledge:
            lines.append(f"- {k.get('statement', '')}")

    lines.append(f"\nThe reviewer's question: \"{question}\"")
    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"assessment": "<direct answer to the question, grounded only in the '
        'evidence above>", "confidence": <0-1 float, your own genuine confidence>, '
        '"supporting_points": ["<short evidence citations>", ...], '
        '"open_questions": ["<anything genuinely uncertain or missing from the '
        'evidence given>", ...], "needs_human_judgment": <true if this genuinely '
        "requires the reviewer's professional judgment rather than being fully "
        'settled by the evidence, false only if the evidence above is fully '
        'conclusive>}. If the evidence given is insufficient to answer '
        'confidently, say so plainly in "assessment" and list what is missing in '
        '"open_questions" - do not guess.'
    )
    return "\n".join(lines)
