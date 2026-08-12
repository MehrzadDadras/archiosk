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

CLAUDE-P12R: when a `represented_party` dict (name/role_type) is given,
the SAME one call is also asked for a risk/opportunity polarity FROM
that party's position - not a second model call, not a second
capability, just one more field in the same requested JSON. This is
deliberately optional and off by default: no represented party means no
polarity is asked for or returned, so a reviewer who hasn't declared who
they represent gets exactly the same behavior as before this existed.
The result is never itself governed truth - see PerspectiveAssessment's
own docstring in services/case_workspace.py for why this is recorded as
an attributed annotation, never a rewrite of the Requirement.

CLAUDE-P15: this Requirement's own governance status (active/superseded)
is now always stated in the prompt (a real, previously-missing gap - a
caller could ask about an already-superseded record with the model given
no signal at all). When `related_requirements` is given (each with its
own real id/text/status), the SAME call is also asked to distinguish
"different" from "wrong because it is no longer governing" - a
superseded requirement disagreeing with what superseded it is expected,
never itself a defect; only an ACTIVE requirement failing to match what
currently governs elsewhere is one. Reuses CaseWorkspaceStore.
current_requirement_for/requirement_predecessor to resolve which
requirements are actually relevant - never a new supersession-walking
mechanism.

CLAUDE-P16: `related_requirements` entries may now also carry a real
`relationship_type` (from CaseWorkspaceStore.relationships_for, an
existing, previously-unused-here method - not a new lookup mechanism)
- e.g. "qualifies" - so the model can reason about a genuine constraint
or exception relationship between two governed Requirements, not just
their independent texts. conversation_interpreter.py now gathers this
automatically for every real investigation (Supersession neighbors and
direct Relationships alike), not only when a test explicitly supplies
it - the production path, not a benchmark-only enrichment.

CLAUDE-P17: the represented-party prompt block gained three guardrails
against specific ways a perspective-sensitive polarity call could go
wrong even with correct underlying reasoning ability - assuming risk/
opportunity is zero-sum between two parties, recasting a statutory or
life-safety obligation as a commercial "opportunity" for whichever
party doesn't hold it, and manufacturing confident opposite answers
for two parties when the governed evidence genuinely does not settle
an allocation. No new evidence-gathering was needed here - the gap was
in what the model was told NOT to assume, not in what it could see.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from services.llm_gateway import call_llm_json

logger = logging.getLogger(__name__)

# CLAUDE-P19: a real, bump-on-meaningful-change marker for the Golden
# Laboratory regression suite's own "prompt/configuration version"
# tracking - NOT a claim that every wording tweak needs a bump, only
# changes that could plausibly shift real reasoning behavior (a new
# guardrail, a new requested field). Last touched by CLAUDE-P17's
# anti-zero-sum/perspective-neutral-obligation/ambiguity guardrails.
INVESTIGATION_PROMPT_VERSION = "p17"


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
    # CLAUDE-P36: the provider boundary's own record of what actually ran
    # - only ever set when ran=True. Callers (conversation_interpreter.py)
    # read these back to label the AnalysisRun/Artifact they persist,
    # rather than re-deriving a provider/model string of their own from
    # an env var - the one place that could silently drift from what this
    # function actually called. requested_at is when the provider request
    # was made, distinct from whatever timestamp the caller later stamps
    # on the governed record it creates from this result.
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None
    # CLAUDE-P12R - only ever set when a represented_party was given.
    risk_polarity: Optional[str] = None
    risk_confidence: Optional[float] = None
    risk_reasoning: Optional[str] = None
    # CLAUDE-P13R: opportunistic autonomous branching - a DIFFERENT,
    # sufficiently-grounded issue the model noticed while answering the
    # original question, distinct from open_questions (which are
    # uncertainties about THIS question, not new questions). The caller
    # (conversation_interpreter.py) decides whether to actually act on
    # this (bounded by AUTONOMOUS_BRANCH_CONFIDENCE_THRESHOLD and
    # CaseWorkspaceStore.can_open_autonomous_case_for's stop conditions) -
    # this module never creates a Case itself.
    suggested_branch: Optional[str] = None
    suggested_branch_confidence: Optional[float] = None
    # CLAUDE-P15 - only ever populated when related_requirements was
    # given: ids AMONG related_requirements the model believes are no
    # longer consistent with what currently governs. Never includes a
    # requirement whose own status is "superseded" - a superseded
    # requirement being historical is expected, not a finding.
    flagged_stale_ids: list[str] = field(default_factory=list)


def investigate_requirement(
    question: str,
    requirement: dict,
    adjudication_history: list[dict],
    evidence: dict,
    represented_party: Optional[dict] = None,
    related_requirements: Optional[list[dict]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> RequirementInvestigationResult:
    prompt = _build_prompt(
        question, requirement, adjudication_history, evidence, represented_party, related_requirements,
    )
    # CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 0): the client-setup/error-
    # handling/JSON-parsing boundary this module used to own directly is
    # now services/llm_gateway.py's call_llm_json - same behavior, one
    # shared implementation instead of a second independent copy of it.
    outcome = call_llm_json(
        user_prompt=prompt, api_key=api_key, model=model, timeout=timeout,
        # CLAUDE-P17: 1000 was tight enough to sometimes truncate valid
        # JSON mid-string once represented_party (risk_polarity block)
        # and a populated suggested_branch are BOTH present in one
        # response - a real, discovered token-budget bug, not just a
        # theoretical risk (an early perspective-tier lab run hit
        # exactly this). 2048 gives room for every optional field this
        # module can request simultaneously.
        max_tokens=2048, log_label="Requirement investigation",
    )
    if not outcome.ran:
        return RequirementInvestigationResult(ran=False, skipped_reason=outcome.skipped_reason)

    parsed = outcome.parsed
    result = RequirementInvestigationResult(
        ran=True,
        assessment=str(parsed.get("assessment", "")).strip(),
        confidence=float(parsed.get("confidence", 0.5)),
        supporting_points=[str(p) for p in parsed.get("supporting_points", [])],
        open_questions=[str(q) for q in parsed.get("open_questions", [])],
        needs_human_judgment=bool(parsed.get("needs_human_judgment", True)),
        provider=outcome.provider,
        model=outcome.model,
        requested_at=outcome.requested_at,
    )
    if represented_party is not None and parsed.get("risk_polarity"):
        result.risk_polarity = str(parsed["risk_polarity"]).strip()
        result.risk_confidence = float(parsed.get("risk_confidence", 0.5))
        result.risk_reasoning = str(parsed.get("risk_reasoning", "")).strip()
    if parsed.get("suggested_branch"):
        result.suggested_branch = str(parsed["suggested_branch"]).strip()
        result.suggested_branch_confidence = float(parsed.get("suggested_branch_confidence", 0.5))
    if related_requirements is not None:
        result.flagged_stale_ids = [str(i) for i in parsed.get("flagged_stale_ids", [])]
    return result


def _build_prompt(
    question: str, requirement: dict, adjudication_history: list[dict], evidence: dict,
    represented_party: Optional[dict] = None, related_requirements: Optional[list[dict]] = None,
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
    # CLAUDE-P15: the requirement's own governance status was never
    # surfaced before this - a real gap, since a caller could otherwise
    # ask about an already-superseded record with the model given no way
    # to know that. "active" is stated too, not left implicit, so silence
    # on this point is never mistaken for uncertainty.
    lines.append(f"This Requirement's own status: {requirement.get('status', 'active')}.")

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

    if related_requirements:
        lines.append(
            "\nOther governed Requirements relevant to this question (each with its "
            "own real status - a status of 'superseded' means this is PRESERVED "
            "HISTORICAL RECORD, not currently governing; it existing alongside a "
            "newer statement is expected and correct, not itself a problem. Only "
            "flag a genuine issue where an ACTIVE requirement fails to match what "
            "is CURRENTLY governing elsewhere - never flag a superseded one for "
            "disagreeing with what superseded it):"
        )
        for related in related_requirements:
            note = f" ({related['note']})" if related.get("note") else ""
            rel_type = f" [{related['relationship_type']}]" if related.get("relationship_type") else ""
            lines.append(
                f"- [{related['id']}] {related.get('original_requirement_identifier', '')}{rel_type} "
                f"(status: {related.get('status', 'active')}){note}: {related.get('text_reference', '')}"
            )

    lines.append(f"\nThe reviewer's question: \"{question}\"")

    schema_fields = (
        '{"assessment": "<direct answer to the question, grounded only in the '
        'evidence above>", "confidence": <0-1 float, your own genuine confidence>, '
        '"supporting_points": ["<short evidence citations>", ...], '
        '"open_questions": ["<anything genuinely uncertain or missing from the '
        'evidence given>", ...], "needs_human_judgment": <true if this genuinely '
        "requires the reviewer's professional judgment rather than being fully "
        'settled by the evidence, false only if the evidence above is fully '
        "conclusive>"
    )
    if represented_party is not None:
        lines.append(
            f"\nThe reviewer represents {represented_party.get('name', '')} "
            f"({represented_party.get('role_type', '')}) on this project. Also assess, "
            "STRICTLY from that party's own position (not a neutral or overall view): "
            "does this Requirement, as currently understood, read as risk exposure, an "
            "opportunity, or neutral for that specific party. This is a perspective-"
            "sensitive judgment, not a claim about the Requirement's own meaning - the "
            "same Requirement can honestly be risk for one party and opportunity for "
            "another."
        )
        # CLAUDE-P17: three guardrails found necessary while building the
        # perspective-sensitive risk/opportunity tier - each addresses a
        # specific way an honest-sounding polarity call could still be
        # wrong, none of them a claim about any particular Requirement's
        # content.
        lines.append(
            "Do not assume this is zero-sum. Risk for one party does NOT imply "
            "opportunity for another, and opportunity for one party does NOT imply "
            "risk for another - each party's polarity must be judged independently "
            "from what the evidence actually says about THAT party's own exposure, "
            "never inferred as the mirror image of a different party's position. It "
            "is entirely possible, and often correct, for a condition to be risk for "
            "both parties (for different reasons), opportunity for one party with no "
            "corresponding harm to the other, or neutral for a party the evidence "
            "does not actually implicate."
        )
        lines.append(
            "If this Requirement states a statutory, life-safety, regulatory-"
            "compliance, or public-interest obligation, its underlying character does "
            "not change merely because a different party bears responsibility for it. "
            "Perspective may change WHO must manage the obligation and how exposed "
            "they are to the consequences of getting it wrong, but never turns the "
            "obligation itself into a commercial 'opportunity' for whichever party "
            "does not hold it - the party not holding it, if anything, is relieved of "
            "a burden, which is neutral or a reduced-risk position, not a gain."
        )
        lines.append(
            "If the evidence given genuinely does not establish which party bears an "
            "allocation (no clause, Relationship, or other governed fact actually "
            "settles it), say so plainly in risk_reasoning and give a low "
            "risk_confidence rather than manufacturing a confident answer - and "
            "recognize that genuine allocation ambiguity reads as uncertainty for "
            "EVERY party asked about it, not as a confident but opposite answer for "
            "each one."
        )
        schema_fields += (
            ', "risk_polarity": "<one of: risk, opportunity, neutral - from that '
            'party\'s position specifically>", "risk_confidence": <0-1 float>, '
            '"risk_reasoning": "<why, from that party\'s position>"'
        )

    lines.append(
        "\nSeparately: while answering, you may have noticed something ELSE - a "
        "different, genuinely concerning issue this Requirement's own evidence "
        "raises, distinct from the question you were actually asked (not just "
        "restating an open_question above - something substantial enough that it "
        "would deserve its own separate Investigation). Only report one if you are "
        "genuinely confident it is real and grounded in the evidence already given "
        "- leave it out entirely rather than manufacturing one to seem thorough."
    )
    schema_fields += (
        ', "suggested_branch": "<a different, separately-investigable issue, or '
        'omit/empty if none>", "suggested_branch_confidence": <0-1 float, only if '
        "suggested_branch is given>"
    )

    if related_requirements:
        schema_fields += (
            ', "flagged_stale_ids": ["<id from the Other governed Requirements list '
            "above whose CURRENT (active) text does not match what currently "
            "governs elsewhere - empty array if none genuinely conflict>\"]"
        )

    schema_fields += "}"

    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        + schema_fields
        + ". If the evidence given is insufficient to answer confidently, say so "
        'plainly in "assessment" and list what is missing in "open_questions" - do '
        "not guess."
    )
    return "\n".join(lines)
