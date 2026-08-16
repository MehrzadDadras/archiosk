"""
Bounded GO QA/QC pass (Section 5): "GO drafts -> PM reviews/edits -> PM
accepts" - GO's own first-pass Document Context claims, drafted from a
Source's ALREADY-EXTRACTED evidence text (EvidenceItem content, the same
grounding project_qa.py/requirement_investigation.py already restrict
themselves to - never the model's own world knowledge, never content
this project hasn't actually extracted).

Mirrors requirement_investigation.py/project_qa.py's own Anthropic
integration pattern exactly, via the shared services.llm_gateway.
call_llm_json (lazy anthropic import, api_key/model/timeout from the
same env vars, strict-JSON prompt, honest degrade-on-no-key/timeout/
malformed-output - never a fabricated claim when the model can't be
reached).
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from services.case_workspace import KNOWN_DOCUMENT_CONTEXT_FIELDS
from services.llm_gateway import call_llm_json

logger = logging.getLogger(__name__)

DOCUMENT_CONTEXT_DRAFT_PROMPT_VERSION = "go-qac-01"

_SYSTEM_PROMPT = (
    "You are drafting a first-pass Document Context for a construction/design "
    "project source document, for a Project Manager to review, edit, or reject. "
    "Ground every statement ONLY in the evidence text given - never invent facts "
    "the text does not support. Return strict JSON only, no prose, no markdown "
    "fences: a JSON array of objects, each {\"field_kind\": one of "
    + json.dumps(list(KNOWN_DOCUMENT_CONTEXT_FIELDS))
    + ", \"statement\": a short, factual statement, \"directly_evidenced\": true "
    "if the statement is explicitly stated in the text, false if it is a "
    "reasonable inference}. Only include fields you can actually say something "
    "about from the given text - never guess a field merely to fill it in. "
    "Return at most 6 items."
)


def draft_document_context_claims(
    source_name: str,
    evidence_text: str,
    api_key: Optional[str] = None,
    timeout: Optional[float] = None,
) -> dict:
    """
    Returns {"ran": bool, "claims": [{"field_kind","statement",
    "directly_evidenced"}], "skipped_reason": str|None} - never raises.
    A caller that gets ran=False simply has nothing to draft this time
    (Section 5: "Do not present inference as established fact" applies
    equally to failure - an honest "could not draft" beats a fabricated
    claim).
    """
    if not evidence_text or not evidence_text.strip():
        return {
            "ran": False, "claims": [],
            "skipped_reason": "No extracted evidence text available for this source yet.",
        }

    user_prompt = (
        f"Source document name: {source_name}\n\n"
        f"Evidence text extracted from this source (may be partial):\n{evidence_text[:6000]}"
    )
    outcome = call_llm_json(
        user_prompt=user_prompt,
        system_prompt=_SYSTEM_PROMPT,
        api_key=api_key,
        timeout=timeout,
        max_tokens=1200,
        log_label="Document Context draft (GO QA/QC)",
    )
    if not outcome.ran:
        return {"ran": False, "claims": [], "skipped_reason": outcome.skipped_reason}

    parsed = outcome.parsed
    if not isinstance(parsed, list):
        return {"ran": False, "claims": [], "skipped_reason": "Model returned an unexpected shape."}

    claims = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        field_kind = item.get("field_kind")
        statement = item.get("statement")
        if not field_kind or not statement or not str(statement).strip():
            continue
        claims.append({
            "field_kind": str(field_kind),
            "statement": str(statement).strip(),
            "directly_evidenced": bool(item.get("directly_evidenced", False)),
        })
    return {"ran": True, "claims": claims, "skipped_reason": None}
