"""
CLAUDE-DELTA-SPIN-01 -- governed, comprehensive project-intelligence Spin.

Mirrors services/project_qa.py's Anthropic integration pattern exactly
(lazy client via services.llm_gateway.call_llm_json, same env vars, same
honest-degrade-on-no-key/timeout/malformed-output discipline, same
BEHAVIORAL_CONTRACT authority rules - imported and extended, not
duplicated). The difference from project_qa.py is SCOPE and PURPOSE, not
mechanism: project_qa answers one reviewer question against a relevance-
scored slice of project evidence; this module produces an unprompted,
COMPREHENSIVE characterization of the whole project (First Spin), or a
characterization of what has changed in project understanding since an
earlier Spin run (Delta Spin) - never a filename diff, never a re-run of
First Spin, never a generic "13 new documents" summary.

Governing distinction, preserved from governance/specified-unbuilt/
spin-project-intelligence-preview.md: "Comprehensive Spin precedes
focused conversation... Spin discovers -> Pass adjudicates -> Build
incorporates." This module implements only the DISCOVER half - it never
adjudicates (no ReviewerValidation/Disposition/RequirementAdjudication is
touched) and never incorporates (no Task/RFI/Requirement/WorkProduct is
created). Every emitted finding is persisted via
CaseWorkspaceStore.record_spin_run/add_composer_finding in the SAME
governed-but-provisional, no-Approval-Gate posture ordinary Composer
findings already have - a human decides what happens next.

Findings are represented as services.case_workspace.ComposerFinding
records (see that class's own docstring on why a Spin-produced finding
reuses that object rather than inventing a second finding type), grouped
by a services.case_workspace.SpinRun. This module itself creates neither
directly - it returns a plain SpinResult; the caller (routes/workspace.py)
is responsible for persisting it via store.record_spin_run, the same
"generation module never touches the store directly" separation
project_qa.py/project_briefing.py already establish.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from services.case_workspace import (
    KNOWN_SPIN_DELTA_CLASSIFICATIONS,
    KNOWN_SPIN_WORLDS,
    SPIN_KIND_DELTA,
    SPIN_KIND_FIRST,
    SPIN_WORLD_SURVIVAL,
)
from services.llm_gateway import call_llm_json, resolve_timeout_from_env, scale_timeout_for_prompt_size
from services.project_qa import BEHAVIORAL_CONTRACT as _PROJECT_QA_BEHAVIORAL_CONTRACT

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 45.0

# CLAUDE-DELTA-SPIN-01: bump on meaningful prompt/schema changes, same
# discipline as services/project_qa.py's PROJECT_QA_PROMPT_VERSION.
SPIN_PROMPT_VERSION = "delta-spin-01"

_MAX_CANDIDATE_ITEMS_IN_PROMPT = 40
_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT = 40
_MAX_MILESTONES_IN_PROMPT = 20

# CLAUDE-DELTA-SPIN-01: a comprehensive pass looks across more of the
# project's documents than a single-question Composer turn does (that
# path's own _MAX_ADDITIONAL_DOCUMENTS_IN_PROMPT is 15) - still a bounded
# constant, not "no cap" (Section 6's own "widen only where evidence
# warrants it" is about ADAPTIVE ATTENTION within this cap, not license
# to remove it).
_MAX_DOCUMENTS_IN_PROMPT = 30
_MAX_EXCERPTS_PER_DOCUMENT = 8
# CLAUDE-DELTA-SPIN-01: same "priority document gets the large excerpt
# allowance" reasoning services.conversational_turn.select_relevant_
# document_evidence already established for an explicitly-named/currently-
# open document - here the priority signal is "this Source is new or
# changed since the baseline Spin run", not question relevance.
_MAX_EXCERPTS_FOR_CHANGED_DOCUMENT = 80

_MAX_PRIOR_FINDINGS_IN_PROMPT = 40

# CLAUDE-DELTA-SPIN-01: same defensive-ceiling discipline as services.
# project_qa._MAX_COMPOSER_FINDINGS - the actual backstop against an
# unbounded finding list, independent of the prompt's own "normally
# 8-15" guidance. A comprehensive pass is allowed a somewhat larger
# ceiling than a single-question Composer turn (10) since it is
# characterizing the whole project, not one answer.
_MAX_SPIN_FINDINGS = 20

# CLAUDE-HOLODECK-WORLDS-SPIN-01: same defensive-ceiling discipline,
# applied to the new games_played self-report - the actual backstop
# against an unbounded trace list, independent of the prompt's own
# suggested example sequence.
_MAX_GAMES_PLAYED = 10

# CLAUDE-HOLODECK-WORLDS-SPIN-01: a World's own objective is PRODUCT-
# DEFINED, stable text - never model-generated, never derived from
# evidence. Displayed verbatim in the Spin State Report (routes/
# workspace.py) and given to the model verbatim as its own framing - the
# same object serves both purposes so the two can never drift apart.
SPIN_WORLD_OBJECTIVES = {
    SPIN_WORLD_SURVIVAL: (
        "Find consequential conditions that could materially harm project "
        "success if overlooked."
    ),
}

# CLAUDE-HOLODECK-WORLDS-SPIN-01: Survival Mode's own attention framing -
# appended to the ordinary Spin prompt (never replacing it, never
# touching BEHAVIORAL_CONTRACT's own authority-preservation rules above)
# only when world=SPIN_WORLD_SURVIVAL. This is the entire mechanism by
# which a "World" changes what Spin pays attention to: a different
# framing layer over the SAME single call, never a second engine.
_SURVIVAL_MODE_INSTRUCTIONS = (
    "\n\nYou are performing this Spin in SURVIVAL MODE. Your objective in "
    "this pass is specifically: " + SPIN_WORLD_OBJECTIVES[SPIN_WORLD_SURVIVAL] + " "
    "Prioritize your attention toward evidence and relationships bearing on: "
    "disqualification or eligibility risk, mandatory requirements, "
    "conflicting instructions, unresolved addenda, hidden or ambiguous "
    "scope, authority ambiguity (which document actually governs), design "
    "or coordination gaps, a change that does not appear to have propagated "
    "to everywhere it should have, procurement traps, schedule dependencies "
    "that could block delivery, cost exposure, safety consequences, "
    "commissioning gaps, operational incompatibility, and evidence the "
    "project team appears to be relying on incorrectly. This is NOT license "
    "to pad the findings list or manufacture drama - an ordinary, "
    "well-coordinated condition is not a survival finding merely because "
    "you looked at it. Prioritize by genuine consequence, not by count.\n"
    "For EACH finding you emit in this Survival pass, also self-report, "
    "honestly, which investigative move(s) you effectively used to reach "
    "it - a 'games_played' array alongside your findings. This is a report "
    "of your OWN reasoning path, not a fixed checklist to run mechanically: "
    "only report a move that genuinely happened for a genuine reason. "
    "Games may include (not a closed list - use the name that most "
    "accurately describes what you actually did): 'Change Game' (a change "
    "in evidence or requirement prompted the investigation), 'Propagation "
    "Game' (you traced a change or requirement to its downstream "
    "consequences across disciplines/documents), 'Conflict Game' (you "
    "found two pieces of evidence that disagree), 'Authority Game' (you "
    "determined which document actually governs), 'Convergence Game' (you "
    "tested whether several related strands of evidence agree with each "
    "other), 'Missing Evidence Game' (expected evidence was absent). Each "
    "games_played entry: {\"game\": \"<name>\", \"triggered_by\": \"<what "
    "evidence or earlier discovery caused you to make this move>\", "
    "\"finding\": \"<which finding tag, if any, this move led to - empty "
    "string if it did not lead to a reportable finding>\"}. Never fabricate "
    "a move that did not genuinely occur, and never pad this list to match "
    "the example names above."
)

# CLAUDE-DELTA-SPIN-01: extends services.project_qa.BEHAVIORAL_CONTRACT
# (imported, not copied) with Spin-specific rules - the authority-
# preservation rules (non-binding status survives, human creates governed
# records, never fabricate) apply identically here, so they are reused
# verbatim rather than risking the two drifting apart.
BEHAVIORAL_CONTRACT = (
    _PROJECT_QA_BEHAVIORAL_CONTRACT
    + "\n\n"
    + "You are now performing a Spin: a comprehensive review of this "
    "project's evidence, not an answer to one reviewer question. Examine "
    "the evidence given below as a whole and identify the discrete, "
    "material conditions a project manager should know about - never pad "
    "to a fixed count, and never invent a finding merely to fill the "
    "list.\n"
    "- A NEW capability of this specific pass: if, and only if, prior "
    "Spin findings are given below (a delta_spin run, comparing against "
    "an earlier baseline), classify EVERY finding you emit with a "
    "'delta_classification' field, one of exactly these closed values: "
    "'new' (a genuinely new condition, no prior counterpart), "
    "'strengthened' (a prior concern is now more clearly evidenced or "
    "more consequential), 'weakened' (a prior concern is now less "
    "clearly evidenced or less consequential, but not fully resolved), "
    "'resolved' (the evidence now directly demonstrates a prior concern "
    "no longer holds), 'unchanged' (a prior concern with no material "
    "change either way - only include this when carrying it forward is "
    "itself materially useful, not as padding), 'superseded' (a prior "
    "understanding has been replaced by newer evidence, not merely "
    "restated), 'indeterminate' (the evidence genuinely does not permit "
    "closing this one way or the other - preserve the uncertainty rather "
    "than forcing a classification), 'new_verification_gap' (a new "
    "condition requiring verification or commissioning evidence that "
    "does not yet exist). Never guess a classification the evidence does "
    "not support - 'indeterminate' is always available and is the honest "
    "choice when it applies.\n"
    "- When you classify a finding as anything other than 'new' or "
    "'indeterminate', name what earlier understanding it reassesses in "
    "'related_prior_understanding' (plain text, e.g. referencing a prior "
    "finding's own tag) - never fabricate a reference to something not "
    "actually in the prior findings given below.\n"
    "- Preserve every authority distinction already stated above exactly: "
    "a document being newly added or recently changed never means its "
    "own content became more authoritative - a reference design remains "
    "non-binding regardless of revision number, a draft workbook remains "
    "non-binding regardless of how recently it was added, and a "
    "restricted/tenant-specific document's conclusions must never be "
    "generalized project-wide.\n"
    "- If a cross-disciplinary consequence is genuinely evidenced (a "
    "requirement affecting more than one discipline/interface, a "
    "downstream verification or commissioning obligation), say so "
    "explicitly in the finding's own 'concern' - do not stop at "
    "identifying the originating requirement alone when the evidence "
    "shows it propagates further.\n"
    "- You are never authorized to decide anything here - do not phrase "
    "a finding as an instruction, a decision, or something already "
    "resolved by you. State the condition and what remains for a human "
    "to judge."
)


@dataclass
class SpinResult:
    """`ran=False` means no real Spin pass happened - a skipped_reason is
    always set in that case, and the caller must never persist findings
    from it. `findings` is empty whenever `ran` is False. Mirrors
    ProjectQAResult's own honest-degrade contract."""

    ran: bool
    findings: list[dict] = field(default_factory=list)
    skipped_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None
    # CLAUDE-HOLODECK-WORLDS-SPIN-01: empty for every ordinary (world=None)
    # Spin - only populated when a World's own prompt addition asked for
    # it. See _parse_games_played for the defensive-parsing contract.
    games_played: list[dict] = field(default_factory=list)


def run_spin(
    spin_kind: str,
    document_filename: str,
    candidate_requirements: list[dict],
    governed_requirements: list[dict],
    milestones: list[dict],
    additional_document_evidence: Optional[list[dict]] = None,
    changed_source_keys: Optional[set] = None,
    prior_findings: Optional[list[dict]] = None,
    display_title: Optional[str] = None,
    world: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> SpinResult:
    """`spin_kind` is SPIN_KIND_FIRST or SPIN_KIND_DELTA (services.
    case_workspace). `changed_source_keys`/`prior_findings` are only
    meaningful (and only given by the caller) for SPIN_KIND_DELTA - a
    First Spin has no baseline to diff against or classify relative to.

    `changed_source_keys` is a set of {filename or relative_path} values
    the caller has already determined are new or changed since the
    baseline run's own recorded source_signature (see routes/workspace.py
    - a real, explicit diff of Source ids, never inferred here from
    filenames or dates).

    CLAUDE-HOLODECK-WORLDS-SPIN-01: `world`, when given, must be one of
    KNOWN_SPIN_WORLDS (validated by the caller/store, not re-validated
    here defensively - matches this module's own existing trust boundary
    with routes/workspace.py). `None` (the default) is ordinary Spin,
    completely unaffected by anything this addition introduced."""
    if world is not None and world not in KNOWN_SPIN_WORLDS:
        raise ValueError(f"Unknown Spin world {world!r}.")
    prompt = _build_prompt(
        spin_kind, document_filename, candidate_requirements, governed_requirements, milestones,
        display_title, additional_document_evidence, changed_source_keys, prior_findings, world,
    )
    # CLAUDE-DELTA-SPIN-02: live acceptance testing found a second-order
    # consequence of raising max_tokens 4000 -> 8000 below - a larger
    # permitted output takes proportionally longer to generate, and the
    # previous 90s ceiling (project_qa.py/project_briefing.py's own
    # shared default, correct for THEIR smaller max_tokens) started
    # producing honest "Request timed out after 90s" failures instead of
    # truncation ones - same underlying problem, different failure mode,
    # still blocking the acceptance behavior. 140s leaves a 10s margin
    # under this deployment's own real ceiling (deploy/gunicorn.conf.py's
    # `timeout = 150`, deploy/nginx.conf's `proxy_read_timeout 150s` on
    # location / - confirmed by direct inspection, not assumed).
    base_timeout = resolve_timeout_from_env(timeout, DEFAULT_TIMEOUT_SECONDS)
    timeout = scale_timeout_for_prompt_size(
        base_timeout, prompt,
        base_chars_before_scaling=4000, seconds_per_extra_1000_chars=3.0, max_timeout=140.0,
    )

    # CLAUDE-DELTA-SPIN-02: live acceptance testing against the North
    # Bayview G1 evidence state found a real, reproducible truncation
    # defect - stop_reason=max_tokens at 4000, discarding the entire run
    # (services.llm_gateway.call_llm_json's own honest-degrade: a
    # truncated response is never partially parsed, the whole attempt is
    # reported as ran=False). A comprehensive Spin can return up to
    # _MAX_SPIN_FINDINGS (20) findings, each with several free-text
    # fields (plus delta_classification/related_prior_understanding for a
    # delta_spin) - roughly double project_qa.py's own _MAX_COMPOSER_
    # FINDINGS (10) ceiling, which itself already needed 3000 tokens
    # (CLAUDE-CA1D-COMPOSER-TIMEOUT-FIX-01, same truncation failure mode).
    # 8000 is the smallest round increase confirmed to clear this
    # specific reproduction; well under claude-sonnet-4-6's own output
    # ceiling.
    outcome = call_llm_json(
        user_prompt=prompt, system_prompt=BEHAVIORAL_CONTRACT,
        api_key=api_key, model=model, timeout=timeout, max_tokens=8000,
        log_label=f"Spin ({spin_kind})",
    )
    if not outcome.ran:
        return SpinResult(ran=False, skipped_reason=outcome.skipped_reason)

    parsed = outcome.parsed
    findings = _parse_spin_findings(parsed.get("findings"), spin_kind=spin_kind)
    games_played = _parse_games_played(parsed.get("games_played")) if world else []
    return SpinResult(
        ran=True, findings=findings, games_played=games_played,
        provider=outcome.provider, model=outcome.model, requested_at=outcome.requested_at,
    )


def _parse_spin_findings(raw, spin_kind: str) -> list[dict]:
    """Same defensive-parsing discipline as services.project_qa.
    _parse_composer_findings - the model's own JSON is read back, never
    trusted on faith. A malformed item (no non-empty "tag") is dropped
    outright; the list is hard-capped at _MAX_SPIN_FINDINGS regardless of
    what the model returned. `delta_classification` is dropped back to
    None (never persisted as a guessed/invalid value) unless it is both
    given AND a member of the closed KNOWN_SPIN_DELTA_CLASSIFICATIONS
    vocabulary, AND spin_kind is SPIN_KIND_DELTA - a first_spin run's
    findings never carry a classification even if the model mistakenly
    supplied one, since a First Spin has no baseline to classify against."""
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
        related_prior_understanding = str(item.get("related_prior_understanding", "")).strip()

        delta_classification = None
        if spin_kind == SPIN_KIND_DELTA:
            candidate = str(item.get("delta_classification", "")).strip().lower()
            if candidate in KNOWN_SPIN_DELTA_CLASSIFICATIONS:
                delta_classification = candidate

        parsed_findings.append({
            "tag": tag,
            "source_reference": str(item.get("source_reference", "")).strip(),
            "concern": str(item.get("concern", "")).strip(),
            "unresolved_question": str(item.get("unresolved_question", "")).strip(),
            "urgency": urgency or None,
            "project_stage": project_stage or None,
            "delta_classification": delta_classification,
            "related_prior_understanding": related_prior_understanding or None,
        })
        if len(parsed_findings) >= _MAX_SPIN_FINDINGS:
            break
    return parsed_findings


def _parse_games_played(raw) -> list[dict]:
    """Same defensive-parsing discipline as _parse_spin_findings - the
    model's own JSON self-report is read back, never trusted on faith. A
    malformed item (no non-empty "game") is dropped outright; the list is
    hard-capped at _MAX_GAMES_PLAYED regardless of what the model
    returned. This is an inspectable trace of the model's OWN reasoning
    path (Section 12's own "concise inspectable trace... not hidden
    chain-of-thought"), never executed as instructions and never used to
    trigger a second real call - a single-call self-report, not a
    multi-step agentic loop."""
    if not isinstance(raw, list):
        return []
    parsed_games: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        game = str(item.get("game", "")).strip()
        if not game:
            continue
        parsed_games.append({
            "game": game,
            "triggered_by": str(item.get("triggered_by", "")).strip(),
            "finding": str(item.get("finding", "")).strip(),
        })
        if len(parsed_games) >= _MAX_GAMES_PLAYED:
            break
    return parsed_games


def _select_comprehensive_document_evidence(
    additional_document_evidence: list[dict],
    changed_source_keys: Optional[set],
    max_documents: int = _MAX_DOCUMENTS_IN_PROMPT,
    max_excerpts_per_document: int = _MAX_EXCERPTS_PER_DOCUMENT,
) -> list[dict]:
    """A comprehensive pass has no single "question" to score relevance
    against (services.conversational_turn.select_relevant_document_
    evidence's own scoring model is deliberately not reused here for that
    reason - it is built around a question string). Instead: every
    document is eligible for inclusion (comprehensive, not a question-
    driven slice); a Source named in `changed_source_keys` (new or
    changed since the baseline run - only ever non-empty for a
    delta_spin, see run_spin's own docstring) gets the larger excerpt
    allowance and sorts first, since PM attention should widen there
    first (Section 6, "adaptive attention" - a small changed document may
    deserve more excerpt budget than several large unchanged ones);
    remaining documents sort by recency, the same smallest-tiebreaker
    services.conversational_turn already uses. Bounded at max_documents
    regardless - never "no cap"."""
    if not additional_document_evidence:
        return []
    changed_source_keys = changed_source_keys or set()

    def _key(doc: dict) -> str:
        return doc.get("relative_path") or doc.get("filename") or ""

    def _added_at(doc: dict) -> str:
        return doc.get("added_at") or ""

    is_changed = {id(doc): (_key(doc) in changed_source_keys) for doc in additional_document_evidence}
    # Changed-since-baseline documents first; within each group, most
    # recent first (stable sort - registration order survives remaining
    # ties, the same harmless fallback services.conversational_turn's
    # own scoring already relies on).
    by_recency = sorted(additional_document_evidence, key=_added_at, reverse=True)
    ordered = sorted(by_recency, key=lambda doc: 0 if is_changed[id(doc)] else 1)

    selected: list[dict] = []
    for doc in ordered[:max_documents]:
        cap = _MAX_EXCERPTS_FOR_CHANGED_DOCUMENT if is_changed[id(doc)] else max_excerpts_per_document
        selected.append({
            "filename": doc.get("filename"),
            "relative_path": doc.get("relative_path"),
            "excerpts": doc.get("excerpts", [])[:cap],
            "is_changed_since_baseline": is_changed[id(doc)],
        })
    return selected


def _build_prompt(
    spin_kind: str, document_filename: str, candidate_requirements: list[dict],
    governed_requirements: list[dict], milestones: list[dict],
    display_title: Optional[str] = None,
    additional_document_evidence: Optional[list[dict]] = None,
    changed_source_keys: Optional[set] = None,
    prior_findings: Optional[list[dict]] = None,
    world: Optional[str] = None,
) -> str:
    is_delta = spin_kind == SPIN_KIND_DELTA
    lines = [
        (
            "You are performing a DELTA SPIN: a change-aware review of this project's "
            "evidence since an earlier comprehensive Spin. Your job is NOT to list which "
            "files were added, and NOT to redo a full project review from scratch - it is "
            "to determine what has MATERIALLY changed in project UNDERSTANDING, what that "
            "change affects, and where a project manager's attention should move now. Carry "
            "forward what is still valid from the prior findings below; do not simply repeat "
            "them; do not manufacture a classification for something with no real change."
            if is_delta else
            "You are performing a FIRST SPIN: a comprehensive, broad review of this "
            "project's evidence - not an answer to one narrow question. Identify what is "
            "going on in this project as a whole: the material conditions, requirements, "
            "risks, and open questions a project manager should know about."
        ),
        "Answer ONLY from the governed evidence given below - never invent a party, duty, "
        "date, dependency, requirement, or fact not present in it. This is NOT the full "
        "source document text, only what has already been extracted from it.",
    ]
    if world:
        lines.append(_SURVIVAL_MODE_INSTRUCTIONS)
    lines += [
        "",
        f"Source document: {document_filename}",
    ]
    if display_title:
        lines.append(f"Project: {display_title}")

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
        lines.append(f"\n{label} items extracted from the founding document ({len(items)} total, showing up to {_MAX_CANDIDATE_ITEMS_IN_PROMPT}):")
        for item in items[:_MAX_CANDIDATE_ITEMS_IN_PROMPT]:
            lines.append(f"- {item.get('text', '')}")

    if governed_requirements:
        lines.append(f"\nGoverned (human-confirmed) Requirements ({len(governed_requirements)}, showing up to {_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT}):")
        for r in governed_requirements[:_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT]:
            lines.append(f"- {r.get('original_requirement_identifier', '')}: {r.get('text_reference', '')} (status: {r.get('status', '')})")

    if milestones:
        lines.append(f"\nSchedule-related items extracted from the founding document ({len(milestones)}, showing up to {_MAX_MILESTONES_IN_PROMPT}):")
        for m in milestones[:_MAX_MILESTONES_IN_PROMPT]:
            lines.append(f"- {m.get('label', '')}")

    if additional_document_evidence:
        all_names = [d.get("relative_path") or d.get("filename", "") for d in additional_document_evidence]
        lines.append(
            f"\nAll other project documents by name ({len(all_names)} total - not their "
            f"content, just confirming what exists in this project):"
        )
        for name in all_names:
            marker = " [NEW OR CHANGED SINCE BASELINE]" if (changed_source_keys and name in changed_source_keys) else ""
            lines.append(f"- {name}{marker}")

        shown = _select_comprehensive_document_evidence(additional_document_evidence, changed_source_keys)
        lines.append(
            f"\nExtracted text for {len(shown)} of those documents (not yet run through "
            f"requirement classification). Documents marked [NEW OR CHANGED SINCE BASELINE] "
            f"above are the ones most likely to drive this Spin's own findings, but are not "
            f"the only ones worth considering:"
        )
        for doc in shown:
            label = doc.get("relative_path") or doc.get("filename", "")
            marker = " [NEW OR CHANGED SINCE BASELINE]" if doc.get("is_changed_since_baseline") else ""
            lines.append(f"- {label}{marker}:")
            for excerpt in doc.get("excerpts", []):
                lines.append(f"  - {excerpt}")

    if is_delta and prior_findings:
        lines.append(
            f"\nPrior Spin findings from the baseline run being compared against "
            f"({len(prior_findings)} total, showing up to {_MAX_PRIOR_FINDINGS_IN_PROMPT}) - "
            f"this is the PRIOR PROJECT UNDERSTANDING you are updating, not new evidence:"
        )
        for pf in prior_findings[:_MAX_PRIOR_FINDINGS_IN_PROMPT]:
            lines.append(
                f"- [{pf.get('tag', '')}] {pf.get('concern', '')} "
                f"(source: {pf.get('source_reference', '')}; open question: {pf.get('unresolved_question', '')})"
            )
    elif is_delta:
        lines.append(
            "\nNo prior Spin findings were recorded for the baseline run - treat every "
            "finding here as newly surfaced ('new'), since there is nothing to compare "
            "against."
        )

    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"findings": [{"tag": "<a few words - a short descriptive title>", '
        '"source_reference": "<where in the evidence above this comes from>", '
        '"concern": "<why this matters, including any cross-disciplinary or '
        'verification/commissioning consequence the evidence genuinely supports>", '
        '"unresolved_question": "<what would need to be resolved>", "urgency": '
        '"<only if the evidence genuinely supports one - empty string otherwise>", '
        '"project_stage": "<only if the evidence genuinely supports one - empty '
        'string otherwise>"'
        + (
            ', "delta_classification": "<one of: new, strengthened, weakened, '
            'resolved, unchanged, superseded, indeterminate, new_verification_gap>", '
            '"related_prior_understanding": "<which prior finding this reassesses, by '
            'its tag - empty string only for a genuinely new or indeterminate finding '
            'with no prior counterpart>"'
            if is_delta else ""
        )
        + "}, ...]"
        + (
            ', "games_played": [{"game": "<name>", "triggered_by": "<what caused this '
            'move>", "finding": "<which finding tag this led to, if any - empty string '
            'if none>"}, ...]'
            if world else ""
        )
        + "}. Never pad the findings list to a fixed count, and never invent "
        "one merely to fill it - an honest, shorter list is always better than a "
        "padded one."
        + (' Never pad "games_played" either - report only moves that genuinely occurred.' if world else "")
    )
    return "\n".join(lines)
