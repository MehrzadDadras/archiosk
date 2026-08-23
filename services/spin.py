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
SPIN_PROMPT_VERSION = "helix-qa-02"

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
_MAX_HELIX_ASSESSMENTS = 20

# PSD-SMOKE-01-D: the floor for a Spin model call, independent of prompt
# size. Spin always requests max_tokens=8000 of structured JSON, so its
# generation time barely varies with how small the evidence set is - see
# the fuller reasoning at the call site. Sits under this call's own 140s
# ceiling and well under deploy/gunicorn.conf.py's `timeout = 150` and
# deploy/nginx.conf's `proxy_read_timeout 150s`, both confirmed by direct
# inspection. Deliberately a floor, not a new default: a genuinely large
# prompt still scales above it, exactly as CLAUDE-DELTA-SPIN-02 intended.
SPIN_MIN_TIMEOUT_SECONDS = 120.0
_MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT = 40
_MAX_SUPERSESSION_EVIDENCE_IN_PROMPT = 40

# CODEX-HELIX-QA-ABSORPTION-01: deliberately small, Spin-local QA
# vocabulary. These values describe one interface assessment; they are
# not project-wide health, LOD, trade-priority, or engineering rules.
HELIX_AXIS_HORIZONTAL = "horizontal"
HELIX_AXIS_LONGITUDINAL = "longitudinal"
HELIX_AXIS_BOTH = "both"
KNOWN_HELIX_AXES = (HELIX_AXIS_HORIZONTAL, HELIX_AXIS_LONGITUDINAL, HELIX_AXIS_BOTH)

KNOWN_HELIX_EXPECTATION_STATES = (
    "mandatory_stage_fit", "partially_converged", "planned_deferred",
    "conditional_interface", "project_specific_rule", "not_applicable",
)
KNOWN_HELIX_ASSESSMENTS = (
    "converged", "dimension_conflict", "positional_conflict", "semantic_mismatch",
    "handshake_deficit", "propagation_lag", "stage_maturity_mismatch",
    "residual_ambiguity", "evidence_unavailable", "legitimate_deferred",
)
HELIX_ASSERTING_ASSESSMENTS = frozenset({
    "converged", "dimension_conflict", "positional_conflict", "semantic_mismatch",
    "handshake_deficit", "propagation_lag", "stage_maturity_mismatch",
})
HELIX_ABSTAINING_ASSESSMENTS = frozenset({
    "evidence_unavailable", "residual_ambiguity", "legitimate_deferred",
})
KNOWN_HELIX_EVIDENCE_SUFFICIENCY = (
    "directly_supportable", "visual_vector_supportable", "evidence_type_insufficient",
)
KNOWN_DIMENSION_RELATIONSHIP_CLASSES = (
    "exact_fit", "threshold_limit", "envelope_reservation", "informational",
    "uncertain_unclassified",
)

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
    # Per-interface Progressive Helix QA assessments. Kept distinct from
    # findings: expectation and observation are inspectable context for a
    # finding, not a second finding taxonomy.
    helix_assessments: list[dict] = field(default_factory=list)
    evidence_source_ids: list[str] = field(default_factory=list)


def run_spin(
    spin_kind: str,
    document_filename: str,
    candidate_requirements: list[dict],
    governed_requirements: list[dict],
    milestones: list[dict],
    additional_document_evidence: Optional[list[dict]] = None,
    maturity_context: Optional[list[dict]] = None,
    expectation_context: Optional[list[dict]] = None,
    relationship_evidence: Optional[list[dict]] = None,
    supersession_evidence: Optional[list[dict]] = None,
    changed_source_keys: Optional[set] = None,
    prior_findings: Optional[list[dict]] = None,
    display_title: Optional[str] = None,
    world: Optional[str] = None,
    primary_source_id: Optional[str] = None,
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
    selected_document_evidence = _select_comprehensive_document_evidence(
        additional_document_evidence or [], changed_source_keys,
    )
    evidence_source_ids = []
    if primary_source_id:
        evidence_source_ids.append(primary_source_id)
    evidence_source_ids.extend(
        item["source_id"] for item in selected_document_evidence
        if item.get("source_id") and item["source_id"] not in evidence_source_ids
    )

    prompt = _build_prompt(
        spin_kind, document_filename, candidate_requirements, governed_requirements, milestones,
        display_title, additional_document_evidence, changed_source_keys, prior_findings, world,
        maturity_context, expectation_context, relationship_evidence, supersession_evidence,
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
    # PSD-SMOKE-01-D: the ceiling above was raised for LARGE corpora, but
    # the scaling it caps is driven by PROMPT size while Spin's actual
    # latency is driven by RESPONSE size - max_tokens=8000 of structured
    # JSON (helix_assessments, findings, games_played), requested
    # identically no matter how small the evidence set is. A small corpus
    # therefore gets the SHORTEST timeout while needing nearly the same
    # generation time, which is backwards for this one call site.
    #
    # Measured on the 9-file PSD Builder corpus: the scaled value landed
    # at 61s, deterministically, three runs out of three - well under this
    # call's own sanctioned 140s ceiling and under deploy/gunicorn.conf.py's
    # `timeout = 150` and deploy/nginx.conf's `proxy_read_timeout 150s`.
    # Roughly 89 seconds of already-authorized budget went unused while
    # the model was still generating; nginx never terminated anything
    # (zero 504s in nginx and journald, every /spin/run returned 302).
    #
    # The floor is therefore not new tolerance - it is this call site
    # already-approved 140s ceiling applied consistently to the small-input
    # case the prompt-size formula under-serves. Ordinary project QA and
    # the project briefing succeed on the identical corpus precisely
    # because they request far smaller responses.
    base_timeout = resolve_timeout_from_env(timeout, DEFAULT_TIMEOUT_SECONDS)
    timeout = max(
        SPIN_MIN_TIMEOUT_SECONDS,
        scale_timeout_for_prompt_size(
            base_timeout, prompt,
            base_chars_before_scaling=4000, seconds_per_extra_1000_chars=3.0, max_timeout=140.0,
        ),
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
    helix_assessments = _parse_helix_assessments(parsed.get("helix_assessments"))
    return SpinResult(
        ran=True, findings=findings, games_played=games_played,
        helix_assessments=helix_assessments,
        evidence_source_ids=evidence_source_ids,
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


def _parse_helix_assessments(raw) -> list[dict]:
    """Defensively preserve a bounded, inspectable interface assessment.

    Closed values prevent model-invented QA states from becoming stored
    doctrine. Free text is evidence description only. An item without an
    interface, valid axis, expectation, assessment, or evidence-sufficiency
    state is dropped rather than guessed.
    """
    if not isinstance(raw, list):
        return []
    parsed: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        interface = str(item.get("interface", "")).strip()
        axis = str(item.get("spin_axis", "")).strip().lower()
        expectation = str(item.get("expectation_state", "")).strip().lower()
        assessment = str(item.get("assessment", "")).strip().lower()
        sufficiency = str(item.get("evidence_sufficiency", "")).strip().lower()
        if (
            not interface or axis not in KNOWN_HELIX_AXES
            or expectation not in KNOWN_HELIX_EXPECTATION_STATES
            or assessment not in KNOWN_HELIX_ASSESSMENTS
            or sufficiency not in KNOWN_HELIX_EVIDENCE_SUFFICIENCY
        ):
            continue
        dimension_class = str(item.get("dimension_relationship_class", "")).strip().lower() or None
        if dimension_class not in KNOWN_DIMENSION_RELATIONSHIP_CLASSES:
            dimension_class = None
        evidence = item.get("observed_evidence")
        if not isinstance(evidence, list):
            evidence = []
        observed = []
        for source in evidence[:12]:
            if not isinstance(source, dict):
                continue
            source_reference = str(source.get("source_reference", "")).strip()
            if not source_reference:
                continue
            observed.append({
                "source_reference": source_reference,
                "revision": str(source.get("revision", "")).strip() or None,
                "region": str(source.get("region", "")).strip() or None,
                "observed_value": str(source.get("observed_value", "")).strip() or None,
                "confidence": str(source.get("confidence", "")).strip() or None,
            })
        if assessment in HELIX_ASSERTING_ASSESSMENTS and (
            not observed or sufficiency == "evidence_type_insufficient"
        ):
            continue
        parsed.append({
            "interface": interface,
            "spin_axis": axis,
            "strands": [str(v).strip() for v in item.get("strands", [])[:12] if str(v).strip()]
                if isinstance(item.get("strands"), list) else [],
            "claimed_maturity": str(item.get("claimed_maturity", "")).strip() or None,
            "maturity_source": str(item.get("maturity_source", "")).strip() or None,
            "expectation_state": expectation,
            "expectation_rationale": str(item.get("expectation_rationale", "")).strip(),
            "dimension_relationship_class": dimension_class,
            "observed_evidence": observed,
            "assessment": assessment,
            "consequence": str(item.get("consequence", "")).strip() or None,
            "uncertainty": str(item.get("uncertainty", "")).strip() or None,
            "evidence_sufficiency": sufficiency,
            "follow_on_game": str(item.get("follow_on_game", "")).strip() or None,
            "governed_question": str(item.get("governed_question", "")).strip() or None,
        })
        if len(parsed) >= _MAX_HELIX_ASSESSMENTS:
            break
    return parsed


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
            "source_id": doc.get("source_id"),
            "excerpts": doc.get("excerpts", [])[:cap],
            "is_changed_since_baseline": is_changed[id(doc)],
        })
    return selected


def _shape_relationship_evidence(items: Optional[list[dict]]) -> list[dict]:
    """Project existing relationship records into a bounded prompt shape.

    Relationship records remain evidence inputs, not conclusions. In
    particular, open-world relationship types are preserved verbatim rather
    than normalized or promoted to the closed Helix vocabularies.
    """
    if not isinstance(items, list):
        return []
    fields = (
        "id", "project_id", "from_type", "from_id", "to_type", "to_id",
        "relationship_type", "created_at", "created_by", "provisional",
        "confidence", "confirmed_by", "related_analysis_id",
        "related_finding_id", "reason", "validation_state", "status",
    )
    shaped = []
    for item in items[:_MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT]:
        if not isinstance(item, dict):
            continue
        shaped.append({key: item[key] for key in fields if key in item})
    return shaped


def _shape_supersession_evidence(items: Optional[list[dict]]) -> list[dict]:
    """Project existing supersession records into a bounded prompt shape."""
    if not isinstance(items, list):
        return []
    fields = (
        "id", "project_id", "predecessor_type", "predecessor_id",
        "successor_type", "successor_id", "actor", "authorized_at",
        "reason", "authority_class",
    )
    shaped = []
    for item in items[:_MAX_SUPERSESSION_EVIDENCE_IN_PROMPT]:
        if not isinstance(item, dict):
            continue
        shaped.append({key: item[key] for key in fields if key in item})
    return shaped


def _build_prompt(
    spin_kind: str, document_filename: str, candidate_requirements: list[dict],
    governed_requirements: list[dict], milestones: list[dict],
    display_title: Optional[str] = None,
    additional_document_evidence: Optional[list[dict]] = None,
    changed_source_keys: Optional[set] = None,
    prior_findings: Optional[list[dict]] = None,
    world: Optional[str] = None,
    maturity_context: Optional[list[dict]] = None,
    expectation_context: Optional[list[dict]] = None,
    relationship_evidence: Optional[list[dict]] = None,
    supersession_evidence: Optional[list[dict]] = None,
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

    lines.append(
        "\nPROGRESSIVE HELIX QA: For each consequential interface you can fairly assess, "
        "compare the expected degree of relationship resolution at the project-specific "
        "maturity/purpose evidenced here with the observed fit. Percentage or issue labels "
        "are clues only, never universal LOD/tolerance rules. Different interfaces may be "
        "at different legitimate maturities. Keep expectation separate from observation; "
        "planned deferral is not failure. Horizontal means current cross-strand fit; "
        "longitudinal means current evidence against governing origin/prior authoritative "
        "state; both may apply. Consequence changes attention, never technical truth. "
        "Never impose a universal trade hierarchy, health score, tolerance, or engineering "
        "solution. If the supplied modality cannot support the audit, record "
        "evidence_type_insufficient and ask for the richer evidence needed."
    )
    if maturity_context:
        lines.append("\nProject-recorded maturity context (project evidence, not universal rules):")
        for m in maturity_context[:30]:
            lines.append(
                f"- {m.get('scope_type', '')}:{m.get('scope_id', '')} = {m.get('value', '')} "
                f"(effective {m.get('effective_at', '')}; status {m.get('status', '')})"
            )
    if expectation_context:
        lines.append("\nProject-defined expected-information context:")
        for e in expectation_context[:40]:
            lines.append(
                f"- {e.get('scope_type', '')}:{e.get('scope_id', '')} expects "
                f"{e.get('description', '')} at {e.get('expected_maturity', '')} "
                f"(status {e.get('status', '')})"
            )

    if relationship_evidence is not None:
        shaped_relationships = _shape_relationship_evidence(relationship_evidence)
        omitted = max(len(relationship_evidence) - len(shaped_relationships), 0)
        lines.append(
            f"\nRelationship evidence (existing project records, not automatic conclusions; "
            f"{len(relationship_evidence)} supplied, showing up to "
            f"{_MAX_RELATIONSHIP_EVIDENCE_IN_PROMPT}; {omitted} omitted by the bounded cap):"
        )
        for relationship in shaped_relationships:
            lines.append(
                "- "
                f"{relationship.get('id', '')}: "
                f"{relationship.get('from_type', '')}/{relationship.get('from_id', '')} "
                f"--{relationship.get('relationship_type', '')}--> "
                f"{relationship.get('to_type', '')}/{relationship.get('to_id', '')}; "
                f"status={relationship.get('status', '')}; "
                f"provisional={relationship.get('provisional', '')}; "
                f"validation={relationship.get('validation_state', '')}; "
                f"confidence={relationship.get('confidence', '')}; "
                f"reason={relationship.get('reason', '')}"
            )
        lines.append(
            "Treat these relationship records as bounded evidence only: "
            "CONTRADICTS may indicate tension, not automatic noncompliance; "
            "an edge does not prove convergence; missing edges must not be fabricated."
        )

    if supersession_evidence is not None:
        shaped_supersessions = _shape_supersession_evidence(supersession_evidence)
        omitted = max(len(supersession_evidence) - len(shaped_supersessions), 0)
        lines.append(
            f"\nSupersession evidence (existing project lineage records, not automatic conclusions; "
            f"{len(supersession_evidence)} supplied, showing up to "
            f"{_MAX_SUPERSESSION_EVIDENCE_IN_PROMPT}; {omitted} omitted by the bounded cap):"
        )
        for supersession in shaped_supersessions:
            lines.append(
                "- "
                f"{supersession.get('id', '')}: "
                f"{supersession.get('predecessor_type', '')}/{supersession.get('predecessor_id', '')} "
                f"superseded by {supersession.get('successor_type', '')}/"
                f"{supersession.get('successor_id', '')}; "
                f"authorized_at={supersession.get('authorized_at', '')}; "
                f"authority={supersession.get('authority_class', '')}; "
                f"reason={supersession.get('reason', '')}"
            )
        lines.append(
            "Treat supersession as lineage/change evidence only: a successor does "
            "not prove downstream propagation or coordination without supporting evidence."
        )

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
        + ', "helix_assessments": [{"interface": "<named consequential interface>", '
        '"spin_axis": "<horizontal|longitudinal|both>", "strands": ["<strand>"], '
        '"claimed_maturity": "<only when evidenced; empty otherwise>", '
        '"maturity_source": "<project evidence establishing the expectation; empty if absent>", '
        '"expectation_state": "<mandatory_stage_fit|partially_converged|planned_deferred|conditional_interface|project_specific_rule|not_applicable>", '
        '"expectation_rationale": "<why this fit is expected now, grounded in project evidence>", '
        '"dimension_relationship_class": "<exact_fit|threshold_limit|envelope_reservation|informational|uncertain_unclassified; empty if not dimensional>", '
        '"observed_evidence": [{"source_reference": "<source/sheet/page>", "revision": "<or empty>", "region": "<or empty>", "observed_value": "<or empty>", "confidence": "<or empty>"}], '
        '"assessment": "<converged|dimension_conflict|positional_conflict|semantic_mismatch|handshake_deficit|propagation_lag|stage_maturity_mismatch|residual_ambiguity|evidence_unavailable|legitimate_deferred>", '
        '"consequence": "<evidence-grounded consequence; empty if none>", '
        '"uncertainty": "<what remains uncertain; empty if none>", '
        '"evidence_sufficiency": "<directly_supportable|visual_vector_supportable|evidence_type_insufficient>", '
        '"follow_on_game": "<game genuinely warranted; empty if none>", '
        '"governed_question": "<Evidence → Concern → Question endpoint; empty if none>"}, ...]'
        + "}. Never pad the findings list to a fixed count, and never invent "
        "one merely to fill it - an honest, shorter list is always better than a "
        "padded one."
        + (' Never pad "games_played" either - report only moves that genuinely occurred.' if world else "")
    )
    return "\n".join(lines)
