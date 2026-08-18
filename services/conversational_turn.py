"""
CLAUDE-CA1D-COMPOSER-SPINE-01 - the Composer's real conversational
orchestration: bounded multi-turn history (Stage 0), and now (Stage 2)
the Context Envelope and the real, model-backed conversational turn
that let the Composer genuinely understand a turn rather than only
pattern-match it (see services/conversation_interpreter.py's own
module docstring on why THAT file stays deterministic keyword matching
for the fast path).

CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): built here, NOT wired into
interpret_message's dispatch chain yet - that is Stage 3, gated on a
governance record being written first (per this repo's own
ratification discipline; see the plan's "Resolved design decisions").
Every function here is independently unit-testable against a mocked
services.llm_gateway.call_llm_json without touching
conversation_interpreter.py at all, and this module deliberately never
imports from conversation_interpreter.py (Stage 3 will need the
reverse import - conversation_interpreter.py calling into this module
- so this module must not import back from it, or that becomes
circular).

Reuses governance/specified-unbuilt/voice-conversational-presence.md's
Section 8 (narrowest-first Context Envelope: active selection/Anchor ->
current view -> current project evidence -> nothing broader) and
Section 9 (referent resolution/abstention: one clear referent resolves
normally; more than one plausible referent must be presented, never
guessed; no reasonable referent abstains honestly) as the design
language for new orchestration on the EXISTING chat surface - not a
new UI/voice architecture, and not an implementation of Voice itself.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from services.case_workspace import ProjectWorkspace
from services.llm_gateway import call_llm_json

logger = logging.getLogger(__name__)

# CLAUDE-POSTCAMEL-CA1A (Section 5, token-aware continuity, originally
# services/project_qa.py): a fixed message-count cap alone lets one long
# single message consume the whole window - this instead bounds total
# transmitted continuity by size, not by count, while still capping the
# message COUNT too so a long run of very short messages can't produce
# an unbounded list. No tokenizer dependency - a deterministic character
# budget, per that stage's own "approximate character/token budget
# rather than a large dependency" instruction.
_RECENT_HISTORY_CHAR_BUDGET = 2000
_MAX_RECENT_HISTORY_MESSAGES = 20
_MAX_HISTORY_MESSAGE_CHARS = 300


def build_bounded_history(
    recent_history: list[dict],
    char_budget: int = _RECENT_HISTORY_CHAR_BUDGET,
    max_messages: int = _MAX_RECENT_HISTORY_MESSAGES,
    max_message_chars: int = _MAX_HISTORY_MESSAGE_CHARS,
) -> list[dict]:
    """
    Walk backwards from the most recent message, keeping whole messages
    (never truncating a message mid-sentence just to hit the budget
    exactly) until either the character budget or the message-count cap
    is reached, then restore chronological order. Recent turns are
    always favored - the OLDEST messages are the ones dropped first when
    the budget is exceeded. Callers pass raw {"role", "text"} dicts (the
    same shape services/case_workspace.py's ConversationMessage already
    exposes) - this function has no model/persistence knowledge of its
    own.
    """
    selected: list[dict] = []
    total_chars = 0
    for message in reversed(recent_history):
        text = (message.get("text") or "").strip()[:max_message_chars]
        if not text:
            continue
        if selected and (
            total_chars + len(text) > char_budget
            or len(selected) >= max_messages
        ):
            break
        selected.append({"role": message.get("role"), "text": text})
        total_chars += len(text)
    selected.reverse()
    return selected


# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): project evidence assembly -
# moved here verbatim from services/conversation_interpreter.py's own
# _handle_project_question (the ONLY place this logic existed before
# this stage), which now calls this same function instead of carrying
# its own inline copy. Behavior-preserving extraction, same discipline
# Stage 0 already used for services/llm_gateway.py - one implementation
# instead of a second copy for the new orchestrator to grow.
_MAX_CANDIDATE_ITEMS_IN_PROMPT = 40
_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT = 40
_MAX_MILESTONES_IN_PROMPT = 20
_MAX_ADDITIONAL_DOCUMENTS_IN_PROMPT = 15
_MAX_EXCERPTS_PER_ADDITIONAL_DOCUMENT = 8


@dataclass
class ProjectEvidence:
    document_filename: str
    display_title: Optional[str] = None
    candidate_requirements: list[dict] = field(default_factory=list)
    governed_requirements: list[dict] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)
    additional_document_evidence: list[dict] = field(default_factory=list)


def gather_project_evidence(workspace: ProjectWorkspace, store) -> ProjectEvidence:
    """`store` is a CaseWorkspaceStore (not type-hinted to avoid a
    services.case_workspace -> services.conversational_turn ->
    services.case_workspace import cycle; CaseWorkspaceStore itself
    never imports this module)."""
    from services.requirements_registry import RequirementsRegistry

    document = RequirementsRegistry(store.store_path).get(workspace.project_id)
    candidate_requirements = (
        [{"text": r.text, "category": r.category} for r in document.requirements] if document else []
    )
    milestones = list(document.milestones) if document else []
    document_filename = document.filename if document else "(unknown source document)"

    additional_document_evidence: list[dict] = []
    if workspace.evidence_items:
        sources_by_id = {s["id"]: s for s in workspace.sources}
        excerpts_by_source: dict[str, list[str]] = {}
        for item in workspace.evidence_items:
            source_id = item.get("source_id")
            content = item.get("content")
            if not source_id or not content:
                continue
            excerpts_by_source.setdefault(source_id, []).append(content)
        for source_id, excerpts in excerpts_by_source.items():
            source = sources_by_id.get(source_id)
            if source is None:
                continue
            additional_document_evidence.append({
                "filename": source.get("name"),
                "relative_path": source.get("origin_reference"),
                "excerpts": excerpts,
                # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: additive keys,
                # backward-compatible with any caller reading only the
                # three keys above - used by select_relevant_document_
                # evidence (below) to score relevance instead of relying
                # on this list's own incidental order (Source-registration
                # order, which used to be the ONLY signal downstream
                # prompt-builders had, silently excluding anything
                # registered after the first _MAX_ADDITIONAL_DOCUMENTS_IN_
                # PROMPT documents regardless of relevance).
                "source_id": source_id,
                "added_at": source.get("added_at"),
                "document_authority": source.get("document_authority"),
            })

    return ProjectEvidence(
        document_filename=document_filename,
        display_title=workspace.display_title,
        candidate_requirements=candidate_requirements,
        governed_requirements=list(workspace.requirements),
        milestones=milestones,
        additional_document_evidence=additional_document_evidence,
    )


# -- CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01 ------------------------------
# Root cause of the defect this replaces: `additional_document_evidence`
# above is built by iterating `workspace.evidence_items` in plain
# insertion order (a Python dict preserves the order its keys were first
# added - see excerpts_by_source above), which is Source-REGISTRATION
# order, nothing else. Every prompt-builder that later did
# `additional_document_evidence[:_MAX_ADDITIONAL_DOCUMENTS_IN_PROMPT]`
# was therefore always keeping the OLDEST-registered documents and
# discarding everything registered after the cap - regardless of
# whether the discarded document was the one the reviewer explicitly
# named, was more relevant to the actual question, was more
# authoritative, or was the very evidence a Data Room Reconcile pass
# had just added. Confirmed live on North Bayview (CLAUDE-SPREADSHEET-
# SOURCE-ELIGIBILITY-01 + CLAUDE-LIVE-VERIFICATION-ACCOUNT-MECHANISM-01):
# asking about a workbook registered 36th of 42 Sources produced "not
# present in any of the extracted documents," a technically-honest but
# practically-wrong answer, since the workbook's own evidence was real
# and present in the store, just never reaching the prompt at all.
#
# The cap itself (_MAX_ADDITIONAL_DOCUMENTS_IN_PROMPT/_MAX_EXCERPTS_PER_
# ADDITIONAL_DOCUMENT) is a legitimate, still-needed prompt-size/token
# protection (its own original comment: "bounded the same way every
# other prompt section already is, so this can't grow the prompt
# unboundedly") - kept unchanged as the ceiling. What changes is WHICH
# evidence fills that ceiling: relevance-scored, not merely oldest-
# first. "Preserve evidence. Organize understanding. Compress
# attention." - this is the compression step, applied to WHAT is worth
# keeping, not merely HOW MUCH.

_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "is", "are",
    "was", "were", "what", "which", "who", "whom", "this", "that", "these",
    "those", "with", "from", "by", "at", "as", "it", "its", "be", "been",
    "being", "do", "does", "did", "has", "have", "had", "can", "could",
    "will", "would", "should", "about", "into", "i", "you", "your", "my",
    "me", "we", "our", "if", "not", "no", "yes",
})

# A document the reviewer names outright is the strongest possible signal
# (Section 3's "explicit-document guarantee") - deliberately a RATIO plus
# a minimum count, not either alone: a ratio alone would let a two-word
# filename ("RFI Log") match almost any question containing "log"; a
# count alone would unfairly disadvantage a short filename that's fully
# quoted. Both together mean "most of this document's own distinguishing
# words appear in the question," which is what "explicitly named" means
# in practice.
_EXPLICIT_MATCH_MIN_OVERLAP_WORDS = 2
_EXPLICIT_MATCH_MIN_OVERLAP_RATIO = 0.5

# A document that IS the explicit match (or the one currently open) gets
# a much larger excerpt allowance than an incidentally-relevant one -
# tabular/spreadsheet evidence in particular has no reliable per-row
# keyword signal (a data row like "UD-001, Facility-wide distribution of
# the 58 courtrooms..." doesn't repeat the sheet's own name or column
# headers), so keyword-filtering individual rows out of a document the
# reviewer specifically asked about would silently drop the very rows
# that answer the question. 80 is generous enough to cover a real,
# moderately-sized single workbook's full row count end to end (the
# North Bayview specimen's own proof case is 80 rows across 5 sheets)
# while staying a bounded constant, not "no cap."
_MAX_EXCERPTS_FOR_PRIORITY_DOCUMENT = 80

# Authority is a real, already-modeled field (services.case_workspace.
# KNOWN_DOCUMENT_AUTHORITY_LEVELS) but is honestly absent (None) on most
# Sources today - the folder-upload/Reconcile ingestion paths that
# register the vast majority of real project documents never set it
# (Section 1's own "determine exactly why" - not yet wired in, not a
# decision this task's own scope authorizes revisiting). Used only as a
# SMALL tiebreaker when present, never as a requirement for inclusion -
# an unpopulated field must never silently exclude an otherwise-relevant
# document.
_AUTHORITY_SCORE_BY_LEVEL = {
    "contractual": 3, "project_agreement": 3,
    "issued_for_procurement": 2,
    "reference": 1, "informational": 1,
    "indicative": 0, "draft": 0,
}


def _significant_words(text: str) -> set[str]:
    """Lowercase, alphanumeric tokens of length >= 3, common English
    function words dropped - not a linguistic feature system, just enough
    to stop near-universal words ("the", "what") from spuriously
    "matching" almost any document or question."""
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {t for t in tokens if len(t) >= 3 and t not in _STOPWORDS}


def _document_name_words(doc: dict) -> set[str]:
    label = doc.get("relative_path") or doc.get("filename") or ""
    stem = re.sub(r"\.[a-zA-Z0-9]{1,5}$", "", label)  # strip a file extension only
    return _significant_words(stem)


def _is_explicit_name_match(doc_words: set[str], question_words: set[str]) -> bool:
    if not doc_words:
        return False
    overlap = doc_words & question_words
    return (
        len(overlap) >= _EXPLICIT_MATCH_MIN_OVERLAP_WORDS
        and len(overlap) / len(doc_words) >= _EXPLICIT_MATCH_MIN_OVERLAP_RATIO
    )


def _is_current_document(doc: dict, selected_source_id: Optional[str], selected_source_name: Optional[str]) -> bool:
    if selected_source_id and doc.get("source_id") == selected_source_id:
        return True
    if selected_source_name and doc.get("filename") == selected_source_name:
        return True
    return False


def select_relevant_document_evidence(
    additional_document_evidence: list[dict],
    question: str,
    selected_source_id: Optional[str] = None,
    selected_source_name: Optional[str] = None,
    max_documents: int = _MAX_ADDITIONAL_DOCUMENTS_IN_PROMPT,
    max_excerpts_per_document: int = _MAX_EXCERPTS_PER_ADDITIONAL_DOCUMENT,
) -> list[dict]:
    """
    Replaces plain `additional_document_evidence[:max_documents]` with a
    relevance-scored selection. Returns AT MOST `max_documents` entries,
    each `{"filename", "relative_path", "excerpts"}` (excerpts already
    trimmed to that document's own allowance) - same shape callers
    already expect, so this is a drop-in replacement for the old slice,
    not a new contract.

    Scoring, highest tier first (a document can qualify for more than
    one tier; tiers are additive, not exclusive, so a document that is
    BOTH explicitly named AND currently open scores higher than either
    alone):
      - Explicitly named in the question (_is_explicit_name_match) -
        the dominant signal; effectively guarantees inclusion.
      - Currently open/selected Source - a reviewer looking at
        something is very likely asking about it even without naming it.
      - Keyword overlap between the question and this document's own
        filename + excerpt text - the general relevance signal for
        everything else.
      - document_authority, when populated - a small tiebreaker only
        (Section 4: authority and relevance are different questions;
        this never promotes an otherwise-irrelevant document).
      - Recency (Source.added_at) - the smallest tiebreaker of all,
        used only to break remaining ties sensibly (newer favored over
        older when nothing else distinguishes two documents) rather
        than the OLD behavior of registration order being the only
        signal that mattered.

    A document scoring exactly zero on every tier is still eligible if
    there's room left under max_documents once every genuinely relevant
    document has been placed (bounded retrieval never means empty
    retrieval for a broad/ambiguous question - Section 8, Game D) -
    ties among zero-scoring documents fall back to recency.
    """
    if not additional_document_evidence:
        return []

    question_words = _significant_words(question)

    # Recency rank: index 0 = most recent. Missing/unparseable added_at
    # sorts last (oldest-equivalent) rather than raising - honest
    # degradation, not a crash, for the (currently common) case of a
    # Source predating this field's own introduction.
    def _added_at_key(doc: dict) -> str:
        return doc.get("added_at") or ""

    by_recency = sorted(additional_document_evidence, key=_added_at_key, reverse=True)
    recency_rank = {id(doc): i for i, doc in enumerate(by_recency)}
    total_docs = len(additional_document_evidence)

    scored: list[tuple[int, bool, dict]] = []
    for doc in additional_document_evidence:
        doc_words = _document_name_words(doc)
        explicit_match = _is_explicit_name_match(doc_words, question_words)
        is_current = _is_current_document(doc, selected_source_id, selected_source_name)

        content_words = set(doc_words)
        for excerpt in doc.get("excerpts", [])[:20]:  # bounded scan - scoring, not the final selection
            content_words |= _significant_words(excerpt)
        keyword_overlap = len(question_words & content_words)

        authority_score = _AUTHORITY_SCORE_BY_LEVEL.get((doc.get("document_authority") or "").lower(), 0)
        recency_score = total_docs - recency_rank[id(doc)]  # higher for more recent

        score = 0
        if explicit_match:
            score += 1_000_000
        if is_current:
            score += 500_000
        score += keyword_overlap * 100
        score += authority_score * 10
        score += recency_score  # smallest weight - pure tiebreaker

        is_priority_document = explicit_match or is_current
        scored.append((score, is_priority_document, doc))

    # Stable sort (Python's sort is stable) - among exactly-equal scores,
    # original (registration) order survives as the final, harmless
    # tiebreaker, same as it always implicitly was, just no longer the
    # PRIMARY signal.
    scored.sort(key=lambda entry: entry[0], reverse=True)

    selected: list[dict] = []
    for _score, is_priority_document, doc in scored[:max_documents]:
        excerpt_cap = _MAX_EXCERPTS_FOR_PRIORITY_DOCUMENT if is_priority_document else max_excerpts_per_document
        selected.append({
            "filename": doc.get("filename"),
            "relative_path": doc.get("relative_path"),
            "excerpts": doc.get("excerpts", [])[:excerpt_cap],
        })
    return selected


# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): Context Envelope, narrowest-
# first (governance/specified-unbuilt/voice-conversational-presence.md
# Section 8): an already-resolved Anchor outranks an already-resolved
# `selected_object`, which outranks current-view/selected-Source
# context, which outranks nothing but this project's own evidence -
# never a broader, cross-project scope (structurally impossible here:
# this function only ever receives the one already-resolved
# `workspace`/`store`, no cross-project parameter exists to pass).
#
# Anchor/selected_object resolution itself (turning an {"anchor_type",
# "anchor_id"} shape into a real object) stays the caller's job -
# services/conversation_interpreter.py's own _resolve_anchor_object,
# reused unchanged - so this module never needs to import back from
# conversation_interpreter.py.
@dataclass
class ContextEnvelope:
    effective_referent_type: Optional[str]
    effective_referent: Optional[dict]
    current_view: Optional[str]
    selected_source: Optional[dict]
    project_evidence: ProjectEvidence


def build_context_envelope(
    workspace: ProjectWorkspace,
    store,
    anchor_type: Optional[str] = None,
    anchor_object: Optional[dict] = None,
    selected_type: Optional[str] = None,
    selected_object: Optional[dict] = None,
    current_view: Optional[str] = None,
    selected_source: Optional[dict] = None,
) -> ContextEnvelope:
    """A resolved (non-None) Anchor always wins over `selected_object` -
    the same "a new explicit selection replaces the old one" precedence
    services/conversation_interpreter.py's own `effective_referent`
    already establishes (CLAUDE-POSTCAMEL-CA1B, Section 5) - reused
    here as the same rule, not a second, competing one."""
    if anchor_object is not None:
        effective_type, effective_referent = anchor_type, anchor_object
    else:
        effective_type, effective_referent = selected_type, selected_object
    return ContextEnvelope(
        effective_referent_type=effective_type,
        effective_referent=effective_referent,
        current_view=current_view,
        selected_source=selected_source,
        project_evidence=gather_project_evidence(workspace, store),
    )


# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): the closed intent_class
# vocabulary and its own safety classification - the single enforcement
# point for safe-vs-consequential (the plan's own "hard routing
# requirement"). Stage 3 wires this into interpret_message's dispatch
# chain and adds the actual handler/proposal-envelope wiring; until
# then this table is pure data, exercised only by this module's own
# tests, never reachable from a live request. An intent_class outside
# this table is never used for dynamic dispatch - run_conversational_turn
# always normalizes an unrecognized value to INTENT_CLASS_GENERAL_ANSWER.
INTENT_CLASS_GENERAL_ANSWER = "general_answer"
INTENT_CLASS_CONTEXTUAL_REFERENCE = "contextual_reference"
INTENT_CLASS_INVESTIGATE_REQUIREMENT = "investigate_requirement"
INTENT_CLASS_ORGANIZE_ADVICE = "organize_advice"
INTENT_CLASS_PROPOSE_DRAFT_RFI = "propose_draft_rfi"
INTENT_CLASS_PROPOSE_APPLY_FINDINGS = "propose_apply_findings"
INTENT_CLASS_PROPOSE_SOURCE_REVISION = "propose_source_revision"
INTENT_CLASS_PROPOSE_WORK_PRODUCT_ISSUE = "propose_work_product_issue"

SAFETY_SAFE = "safe"
# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): "consequential" here means
# exactly what services/case_workspace.py's own record_analysis/
# record_reviewer_validation do NOT require (no Approval Gate) and what
# routes/workspace.py's _require_approval DOES gate today (Apply, RFI
# Issue, Source revision, Work Product issue) - not a new classification,
# the existing one, read back.
SAFETY_CONSEQUENTIAL = "consequential"

# Each entry documents which EXISTING handler/route a future Stage 3/4
# would reuse - never a new mutating code path of this module's own.
INTENT_DISPATCH_TABLE: dict[str, dict] = {
    INTENT_CLASS_GENERAL_ANSWER: {
        "safety": SAFETY_SAFE,
        "reuses": "run_conversational_turn's own reply_text (this module) - no other handler",
    },
    INTENT_CLASS_CONTEXTUAL_REFERENCE: {
        "safety": SAFETY_SAFE,
        "reuses": "conversation_interpreter._handle_contextual_reference (unchanged)",
    },
    INTENT_CLASS_INVESTIGATE_REQUIREMENT: {
        "safety": SAFETY_SAFE,
        "reuses": "conversation_interpreter._handle_investigate_requirement (unchanged) - "
                   "record_analysis is governed-but-provisional, no Approval Gate today",
    },
    INTENT_CLASS_ORGANIZE_ADVICE: {
        "safety": SAFETY_SAFE,
        "reuses": "conversation_interpreter._handle_organize_advice (unchanged)",
    },
    INTENT_CLASS_PROPOSE_DRAFT_RFI: {
        "safety": SAFETY_CONSEQUENTIAL,
        "reuses": "routes.workspace.create_rfi_draft's own _require_approval gate - "
                   "proposal envelope only, never called directly from here",
    },
    INTENT_CLASS_PROPOSE_APPLY_FINDINGS: {
        "safety": SAFETY_CONSEQUENTIAL,
        "reuses": "routes.workspace's Apply route's own _require_approval gate - "
                   "proposal envelope only, never called directly from here",
    },
    INTENT_CLASS_PROPOSE_SOURCE_REVISION: {
        "safety": SAFETY_CONSEQUENTIAL,
        "reuses": "routes.workspace's Source-revision route's own _require_approval gate - "
                   "proposal envelope only, never called directly from here",
    },
    INTENT_CLASS_PROPOSE_WORK_PRODUCT_ISSUE: {
        "safety": SAFETY_CONSEQUENTIAL,
        "reuses": "routes.workspace's Work Product issue route's own _require_approval gate - "
                   "proposal envelope only, never called directly from here",
    },
}
KNOWN_INTENT_CLASSES = tuple(INTENT_DISPATCH_TABLE.keys())
CONSEQUENTIAL_INTENT_CLASSES = tuple(
    intent for intent, meta in INTENT_DISPATCH_TABLE.items() if meta["safety"] == SAFETY_CONSEQUENTIAL
)
_MAX_CANDIDATE_REFERENTS = 5

CONVERSATIONAL_TURN_PROMPT_VERSION = "spine-01"

# CLAUDE-CA1D-COMPOSER-SPINE-01 (Stage 2): the new orchestrator's own
# system-role contract - deliberately separate from project_qa.py's
# BEHAVIORAL_CONTRACT (that one answers a narrower, already-classified
# "project question"; this one also classifies WHAT KIND of turn this
# is). Carries the same non-negotiable rules that contract already
# established (never invent facts, distinguish stated fact from
# interpretation, a suggestion is never an instruction, never claim an
# application action it cannot perform, never reveal private reasoning)
# plus the new classification/reflection/candidate-referent contract.
CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT = (
    "You are ARCHIOSK Go, a project-aware assistant embedded in the ARCHIOSK "
    "application, helping a construction/design project professional. Follow "
    "these rules at all times:\n"
    "- Answer only from the project evidence given in this request. Never "
    "invent facts, files, views, or application capabilities that are not "
    "described here.\n"
    "- If the evidence is genuinely insufficient, say so plainly rather than "
    "guessing.\n"
    "- Distinguish stated fact from your own interpretation.\n"
    # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01 (Section 4): same rule as
    # project_qa.py's own BEHAVIORAL_CONTRACT - evidence selection and
    # evidence authority are different questions.
    "- If a document's own content states or implies it is non-binding, "
    "reference-only, proposed, draft, or otherwise not yet authoritative, "
    "say so explicitly - never present it as a confirmed requirement or "
    "binding fact merely because it was the evidence that answered the "
    "question.\n"
    "- Recent conversation history, if given, is for conversational "
    "continuity only, never additional project evidence - a prior reply, "
    "including your own, is never newly-established project truth.\n"
    "- You may suggest that something become a governed Requirement, "
    "Finding, Task, Decision, RFI, or Work Product entry, but you never "
    "create or issue one yourself - only the human, through ARCHIOSK's own "
    "governed controls (which may ask them to confirm), does that.\n"
    "- Never claim to perform an application action you cannot actually "
    "perform. Never reveal your own private step-by-step reasoning - state "
    "only your conclusion and the evidence behind it.\n"
    "- Classify this turn's intent_class from the CLOSED list given below. "
    "If none genuinely fits, use \"general_answer\" - never invent a new "
    "intent_class value.\n"
    "- A \"currently looking at\" or \"currently selected\" context, if "
    "given, is advisory only: it may resolve what \"this\"/\"it\"/\"that\" "
    "refers to, but governed project evidence always outranks it.\n"
    "- If more than one plausible referent exists for \"this\"/\"it\"/\"that\", "
    "do not guess - list them in candidate_referents instead and ask a "
    "short clarification in reply_text. If no reasonable referent exists, "
    "say so plainly rather than inventing one.\n"
    "- Provide \"reflection\" (a short, one-sentence restatement of what you "
    "understood the reviewer to be asking or asking for) only when it "
    "materially confirms intent, resolves ambiguity, or the turn proposes a "
    "consequential action - never as routine paraphrasing on an ordinary "
    "turn. Leave it null otherwise.\n"
    "- Respond only in the exact JSON schema requested, with no prose "
    "outside it."
)


@dataclass
class ConversationalTurnResult:
    """`ran=False` means no real reasoning happened - a skipped_reason
    is always set in that case, the same degrade-safe contract every
    other LLM-backed result in this codebase already follows."""

    ran: bool
    intent_class: str = INTENT_CLASS_GENERAL_ANSWER
    reply_text: Optional[str] = None
    reflection: Optional[str] = None
    grounded_in: list[str] = field(default_factory=list)
    needs_clarification: bool = False
    # Each item: {"anchor_type", "anchor_id", "description"} - the same
    # shape Anchor's own fields already use. Only ever populated when
    # more than one plausible referent genuinely exists (Section 9's
    # "present the candidates, never guess"); every entry is re-resolved
    # against the real workspace before being trusted (see
    # _validate_candidate_referents below) - an invalid/adversarial
    # anchor_id in the model's own JSON is dropped, never trusted merely
    # because the model returned it.
    candidate_referents: list[dict] = field(default_factory=list)
    # Only ever populated when intent_class is in
    # CONSEQUENTIAL_INTENT_CLASSES - a structured proposal envelope
    # pointing at a real existing gated route, never itself an
    # executable action. None for every safe intent_class.
    proposed_action: Optional[dict] = None
    skipped_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    requested_at: Optional[str] = None


def _validate_candidate_referents(raw, workspace: ProjectWorkspace) -> list[dict]:
    """Defensive parsing - the model's own JSON is read back, never
    trusted on faith. Each candidate's anchor_id is re-resolved against
    THIS workspace's own real lists before being kept; an id that does
    not exist (stale, foreign, or simply invented) is dropped outright,
    never surfaced as a selectable option. Mirrors
    conversation_interpreter._resolve_anchor_object's own per-type
    lookup, duplicated here (not imported) to avoid a
    conversation_interpreter.py <-> conversational_turn.py import
    cycle - the same "short lookup duplicated per call site" precedent
    conversation_interpreter._evaluate_external_ai_policy already sets."""
    if not isinstance(raw, list):
        return []
    valid: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        anchor_type = item.get("anchor_type")
        anchor_id = item.get("anchor_id")
        if not anchor_type or not anchor_id:
            continue
        exists = False
        if anchor_type == "requirement":
            exists = any(r["id"] == anchor_id for r in workspace.requirements)
        elif anchor_type == "finding":
            exists = any(f["id"] == anchor_id for f in workspace.findings)
        elif anchor_type == "source":
            exists = any(s["id"] == anchor_id for s in workspace.sources)
        if not exists:
            continue
        valid.append({
            "anchor_type": anchor_type,
            "anchor_id": anchor_id,
            "description": str(item.get("description", "")).strip(),
        })
        if len(valid) >= _MAX_CANDIDATE_REFERENTS:
            break
    return valid


def _default_forced_reflection(intent_class: str, is_consequential: bool, is_ambiguous: bool) -> str:
    """CLAUDE-CA1D-COMPOSER-SPINE-01 (Resolved design decision #1):
    reflection is code-forced, not left to model discretion, whenever
    the resolved intent_class is consequential OR more than one
    plausible referent exists - both cases where staying silent risks a
    misunderstood consequential action or a silently-guessed referent.
    This is the deterministic fallback used only when the model's own
    "reflection" field was left null in exactly those two cases -
    never overrides a reflection the model DID provide."""
    if is_ambiguous:
        return "More than one thing could match what you're referring to - see the options below before I proceed."
    return f"Before I proceed: this looks like a request to {intent_class.replace('_', ' ')} - confirm that's right."


def run_conversational_turn(
    text: str,
    workspace: ProjectWorkspace,
    envelope: ContextEnvelope,
    recent_history: Optional[list[dict]] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> ConversationalTurnResult:
    """The one new LLM call site this stage adds. Never executes
    anything itself - only classifies intent_class (from the closed
    INTENT_DISPATCH_TABLE vocabulary) and returns a structured result
    for a FUTURE caller (Stage 3) to route. No mutating store/route
    method is imported or reachable from this function - the
    correctness invariant the plan requires for every consequential
    intent_class ("only envelope construction, never execution") holds
    here by construction, not by a runtime check."""
    prompt = _build_conversational_turn_prompt(text, envelope, recent_history)
    outcome = call_llm_json(
        user_prompt=prompt, system_prompt=CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT,
        api_key=api_key, model=model, timeout=timeout, max_tokens=1500,
        log_label="Conversational turn",
    )
    if not outcome.ran:
        return ConversationalTurnResult(ran=False, skipped_reason=outcome.skipped_reason)

    parsed = outcome.parsed
    intent_class = str(parsed.get("intent_class", "")).strip()
    if intent_class not in KNOWN_INTENT_CLASSES:
        intent_class = INTENT_CLASS_GENERAL_ANSWER

    candidate_referents = _validate_candidate_referents(parsed.get("candidate_referents"), workspace)
    is_consequential = intent_class in CONSEQUENTIAL_INTENT_CLASSES
    is_ambiguous = len(candidate_referents) > 1

    reflection_raw = parsed.get("reflection")
    reflection = (str(reflection_raw).strip() or None) if reflection_raw else None
    if reflection is None and (is_consequential or is_ambiguous):
        reflection = _default_forced_reflection(intent_class, is_consequential, is_ambiguous)

    proposed_action = None
    if is_consequential and not is_ambiguous:
        raw_action = parsed.get("proposed_action")
        if isinstance(raw_action, dict):
            proposed_action = {
                "intent_class": intent_class,
                "description": str(raw_action.get("description", "")).strip(),
            }

    return ConversationalTurnResult(
        ran=True,
        intent_class=intent_class,
        reply_text=str(parsed.get("reply_text", "")).strip(),
        reflection=reflection,
        grounded_in=[str(g) for g in parsed.get("grounded_in", [])],
        needs_clarification=bool(parsed.get("needs_clarification", False)),
        candidate_referents=candidate_referents,
        proposed_action=proposed_action,
        provider=outcome.provider, model=outcome.model, requested_at=outcome.requested_at,
    )


def _build_conversational_turn_prompt(
    text: str, envelope: ContextEnvelope, recent_history: Optional[list[dict]],
) -> str:
    evidence = envelope.project_evidence
    lines = [
        "You are assisting a construction/design professional in an ongoing "
        "conversation about a project. Answer ONLY from the governed evidence "
        "given below - never invent facts, dates, names, sections, or content "
        "not present in it.",
        "",
        f"Source document: {evidence.document_filename}",
    ]
    if evidence.display_title:
        lines.append(f"This Project's own display name: {evidence.display_title}")

    if envelope.effective_referent is not None:
        lines.append(
            f"\nCurrently selected/anchored ({envelope.effective_referent_type}): "
            f"{envelope.effective_referent}"
        )
    if envelope.current_view:
        lines.append(f"Current Display view: {envelope.current_view}")
    if envelope.selected_source is not None:
        lines.append(f"Currently open Source: {envelope.selected_source.get('name', '')}")

    if evidence.candidate_requirements:
        lines.append(
            f"\nCandidate items extracted from the document, not yet reviewed by a human "
            f"({len(evidence.candidate_requirements)} total, showing up to "
            f"{_MAX_CANDIDATE_ITEMS_IN_PROMPT}):"
        )
        for item in evidence.candidate_requirements[:_MAX_CANDIDATE_ITEMS_IN_PROMPT]:
            lines.append(f"- [{item.get('category', '')}] {item.get('text', '')}")

    if evidence.governed_requirements:
        lines.append(
            f"\nGoverned (human-confirmed) Requirements ({len(evidence.governed_requirements)} "
            f"total, showing up to {_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT}):"
        )
        for r in evidence.governed_requirements[:_MAX_GOVERNED_REQUIREMENTS_IN_PROMPT]:
            lines.append(
                f"- {r.get('original_requirement_identifier', '')}: {r.get('text_reference', '')} "
                f"(status: {r.get('status', '')})"
            )

    if evidence.milestones:
        lines.append(
            f"\nSchedule-related items extracted from the document, not yet confirmed "
            f"({len(evidence.milestones)} total, showing up to {_MAX_MILESTONES_IN_PROMPT}):"
        )
        for m in evidence.milestones[:_MAX_MILESTONES_IN_PROMPT]:
            lines.append(f"- {m.get('label', '')}")

    if evidence.additional_document_evidence:
        # CLAUDE-GO-GROUNDING-EVIDENCE-SELECTION-01: same relevance-scored
        # selection project_qa.py's own _build_prompt now uses, not a
        # plain registration-order slice - see select_relevant_document_
        # evidence's own docstring above for the full model. This
        # prompt builder isn't wired into interpret_message's dispatch
        # chain yet (Stage 3, still gated), but fixing it now means Stage
        # 3 doesn't ship with the same defect reintroduced.
        selected_source_id = envelope.selected_source.get("id") if envelope.selected_source else None
        selected_source_name = envelope.selected_source.get("name") if envelope.selected_source else None
        shown = select_relevant_document_evidence(
            evidence.additional_document_evidence, text,
            selected_source_id=selected_source_id, selected_source_name=selected_source_name,
        )
        all_names = [d.get("relative_path") or d.get("filename", "") for d in evidence.additional_document_evidence]
        lines.append(
            f"\nAll other project documents by name ({len(all_names)} total - not their "
            f"content, just confirming what exists in this project):"
        )
        for name in all_names:
            lines.append(f"- {name}")
        lines.append(
            f"\nExtracted text for the {len(shown)} of those documents most relevant to this "
            f"message (not yet run through requirement classification). If a document you "
            f"need is named above but has no extracted text below, say so plainly:"
        )
        for doc in shown:
            label = doc.get("relative_path") or doc.get("filename", "")
            lines.append(f"- {label}:")
            for excerpt in doc.get("excerpts", []):
                lines.append(f"  - {excerpt}")

    bounded_history = build_bounded_history(recent_history) if recent_history else []
    if bounded_history:
        lines.append(
            "\nRecent conversation in this project (most recent last) - for "
            "conversational continuity only, NOT additional project evidence:"
        )
        for m in bounded_history:
            speaker = "Reviewer" if m.get("role") == "human" else "ARCHIOSK Go"
            lines.append(f"- {speaker}: {m.get('text', '')}")

    lines.append(f"\nThe reviewer's message: \"{text}\"")
    lines.append(
        "\nRespond ONLY with a JSON object, no prose, no markdown fences: "
        '{"intent_class": "<one of: ' + ", ".join(KNOWN_INTENT_CLASSES) + '>", '
        '"reply_text": "<your direct reply to the reviewer>", '
        '"reflection": "<short restatement of what you understood, or null - see '
        'the system rule on when this applies>", '
        '"grounded_in": ["<short citation of which evidence above supports this>", ...], '
        '"needs_clarification": <true if the evidence is genuinely insufficient to '
        'answer meaningfully, false otherwise>, '
        '"candidate_referents": [{"anchor_type": "requirement|finding|source", '
        '"anchor_id": "<a real id from the evidence above>", "description": "<short '
        'label>"}, ...] (empty array unless more than one plausible referent genuinely '
        'exists for this turn), '
        '"proposed_action": {"description": "<what you are proposing, in plain '
        'language>"} or null (only meaningful when intent_class is one of: ' +
        ", ".join(CONSEQUENTIAL_INTENT_CLASSES) + ")}"
    )
    return "\n".join(lines)
