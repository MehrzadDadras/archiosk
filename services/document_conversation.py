"""CLAUDE-DOCUMENT-SHOP-CONVERSATION-01 - "Ask GO about this document".

The smallest customer-facing continuation of a Document Examination Result.
It explains and explores; it changes nothing.

WHAT THIS IS NOT, stated first because each was a real temptation:

- **Not a second conversation store.** `ConversationMessage` and
  `ProjectWorkspace.project_conversation` already exist and already mean "a
  message with no Investigation open". Each Document Shop job is its own
  workspace, so that list IS this document's conversation - the per-document
  scoping is structural, not enforced by a filter someone could forget.
- **Not a mutation path.** The stored examination result is an immutable
  snapshot. Nothing here writes evidence, requirements, sources, container
  state, or any Project record. The only write is the message itself.
- **Not an image path.** `llm_gateway.call_llm_json` accepts `image_base64`,
  and this module never passes it. Customer image bytes do not leave the host.
  That is a standing Product Owner constraint, and it is asserted by test at
  the call boundary rather than trusted to intent.

CAPABILITY HONESTY. The system can read text off an image (Tesseract, stored
as evidence) and it can show the image. It has NO coordinates: OCR runs as
plain text, and the stored region carries `page_index`/`paragraph_index` only.
So GO can answer "what does this note say" and must refuse "where is the
entrance". The system prompt says so in those words, because the failure mode
worth preventing is a confident answer inferred from OCR reading order - which
is reading order, never layout.
"""
from __future__ import annotations

import time
from typing import Any, Optional

# What the customer sees when the provider cannot be reached. One message, no
# partial answer, no cached guess - a degraded answer presented as a real one
# is worse than no answer.
UNAVAILABLE_MESSAGE = (
    "I could not answer just now - the assistant service did not respond. "
    "Your document and everything already found are unaffected. Please try again."
)

# CLAUDE-ASK-GO-HONEST-FAILURE-01: a reply that arrived and could not be read
# is NOT an unresponsive service, and saying so was a live defect.
#
# The Product Owner asked "What are the structures on this property?" and was
# told the assistant service did not respond. It had responded - HTTP 200, in
# well under a second - with a correct answer that began "GO read two
# structures on this property: 1. 1-storey brick dwelling...". The reply simply
# was not in the shape this caller requires, so the gateway returned ran=False
# and every ran=False mapped to the same sentence.
#
# The cost of that wording is not cosmetic: it sends a person to retry a
# service that was never down, and it points diagnosis at the provider when the
# fault is on this side. Four occurrences in thirty days, the earliest well
# before any of this tranche.
#
# NOTHING IS SALVAGED. The answer text sits in `outcome.raw_text`, and
# `LLMCallOutcome` states plainly that those fields are diagnostic evidence
# only and that `ran=False` still means unusable. Product Owner decision,
# 2026-09-17: keep that invariant and fix the sentence. The answer is still
# discarded; the person is simply told the truth about why.
MALFORMED_MESSAGE = (
    "GO answered, but not in a form I could read, so I have not shown it. "
    "Nothing about your document has changed. Asking again usually works."
)

TRUNCATED_MESSAGE = (
    "GO's answer was cut off before it finished, so I have not shown a part of "
    "it as though it were the whole. Nothing about your document has changed. "
    "A shorter or more specific question usually works."
)

NOT_CONFIGURED_MESSAGE = (
    "Asking questions about a document is not available in this environment yet. "
    "Everything on this page was worked out here and is unaffected."
)

ROLE_HUMAN = "human"
ROLE_SYSTEM = "system"

# Kept deliberately small. Every clause is here because its absence produced a
# wrong answer shape in reasoning about this feature, not for decoration.
SYSTEM_PROMPT = """You are GO, helping someone understand ONE document they uploaded.

WHAT YOU HAVE
You are given that document's identity, the text recovered from it, and the
examination result already shown to the person. You have nothing else, and you
must not imply otherwise.

WHAT YOU CAN AND CANNOT DO
- You may explain, summarise, quote, compare passages WITHIN this document, and
  say what is uncertain.
- If the document is an image or a scan, the text you have was READ OFF the
  image by a text-recognition engine. You can therefore answer questions about
  what the text SAYS.
- You CANNOT see the image. You have no coordinates, no layout, no positions,
  no shapes, no colours. The order of the recovered text is reading order, NOT
  page layout - never infer position, adjacency, direction or spatial
  relationship from it.
- So questions like "where is the entrance", "what is in the lower-right",
  "what streets surround the site", "what is next to this" CANNOT be answered.
  Say plainly that you can read the text on this document but cannot yet see
  where things are on it. Do not guess. Do not hedge into a half-answer.

WHEN A VISUAL EXAMINATION IS INCLUDED BELOW
For survey directions, the TRUE NORTH PREMISE below governs every claim,
including recovered text, setbacks, frontage, structure descriptions and bearing
reconstruction. GRID, MAGNETIC and ASSUMED North are distinct reference systems.
When true North is unresolved, preserve observed values with their reference
system but do not answer a true-north directional question from them. A number
or visible arrow does not establish its North system or a conversion.
Everything above describes what the RECOVERED TEXT can support. Where the
material below carries a VISUAL EXAMINATION, GO has already looked at this
document once and recorded what it saw, and that record is yours to use.
- Answer from it directly. "North" and "Lot dimensions" and "Existing building"
  are things that were seen, not inferred from reading order.
- It is a READING, not the document speaking. Say "GO read the north arrow as
  pointing to the upper right", not "the survey states".
- The examination's own certainty travels with each item and you must keep it.
  Something listed as partially recovered is partially recovered when you
  report it; something listed as unresolved has no value and you must not
  supply one, however reasonable a guess would be.
- The examination is a fixed record made earlier. You are not looking at the
  picture now, so a question it does not cover is still unanswered - say so
  rather than reasoning your way to an answer from the items it does cover.
- Where a SURVEY REFERENCE exists, it is a derived working reference built from
  that reading - never a certified or legal survey, and never authority. Say
  what is on it and where it came from; do not upgrade what it is.

HOW TO ANSWER
- Ground every claim in what you were given. Quote the document's own words
  when they settle the question.
- Separate what the document says from what you infer. "The text says X" and
  "that suggests Y" are different claims and must read differently.
- If the document does not establish something, say so in one plain sentence.
- No jargon from the system's internals. Write to a person who uploaded a
  document, not to an engineer.
- Be brief. A few sentences usually. No headings, no bullet lists unless the
  answer is genuinely a list.

Answer as JSON: {"answer": "your reply"}"""

# How many prior turns travel with a question. Enough to hold a thread, bounded
# so a long conversation cannot grow the request without limit.
MAX_HISTORY_TURNS = 12
MAX_EVIDENCE_CHARS = 12000
MAX_QUESTION_CHARS = 2000


def conversation_for(workspace) -> list[dict]:
    """This document's turns, oldest first.

    Reads `project_conversation` directly: one workspace per Document Shop job
    means this list cannot contain another document's turns. There is no filter
    to get wrong.
    """
    return [
        {
            "role": m.get("role"),
            "text": m.get("text") or "",
            "created_at": m.get("created_at") or "",
            "is_customer": m.get("role") == ROLE_HUMAN,
        }
        for m in (getattr(workspace, "project_conversation", None) or [])
        if (m.get("text") or "").strip()
    ]


def _evidence_text(workspace, source_id: str) -> str:
    """The recovered text for THIS source, in page/paragraph order.

    Reuses document_examination's own scoping - source_id match plus the
    region-to-page-unit join - so the conversation cannot see evidence the
    result page itself would not show.
    """
    from services import document_examination as dx

    recovered = dx._recovered(workspace, source_id)
    return (recovered.get("preview") or "")[:MAX_EVIDENCE_CHARS], recovered


def build_context(document, workspace, result: dict, question: str) -> dict[str, Any]:
    """EXACTLY what leaves this host, assembled in one place so it can be read.

    Returning it rather than formatting it inline is deliberate: a test asserts
    on this dict, so "what we send" is inspectable instead of buried in string
    concatenation.
    """
    from services import document_examination as dx

    source_id = result.get("source_id")
    evidence, recovered = _evidence_text(workspace, source_id) if source_id else ("", {})

    def _lines(group):
        return [f"{i['label']}: {i['value']}" for i in (result.get(group) or [])]

    history = [
        {"role": t["role"], "text": t["text"]}
        for t in conversation_for(workspace)[-MAX_HISTORY_TURNS:]
    ]

    # CLAUDE-SURVEY-REFERENCE-01: what GO SAW travels with what GO READ.
    #
    # This function previously sent the failed text extraction and nothing else,
    # so on a survey image the whole of GO's context was "No text was recovered
    # from this document" - and GO answered accordingly, about a document whose
    # address, north arrow and footprint were sitting in evidence.
    #
    # STILL NO IMAGE BYTES. The picture was looked at once, in the examination,
    # under its own gate and with its own audit record. This box sends the
    # RECORD of that looking, which is a short list of qualified statements -
    # not a second transmission of the customer's survey.
    visual = dx.visual_reading(workspace, source_id) if source_id else None
    reference = dx.survey_reference_of(workspace, source_id) if source_id else None
    visual_recovered, visual_partial, visual_unresolved = dx._visual_lines(visual)
    from services import survey_north
    north = survey_north.resolve_true_north((visual or {}).get("graph") or {})

    return {
        # identity of THIS document only - never the container id, never a path
        "document_name": result.get("name") or "",
        "file_name": result.get("filename") or "",
        "is_image": bool(result.get("is_image")),
        "state": result.get("state_label") or "",
        # the visual examination, as a record of qualified statements
        "visual_ran": bool(visual),
        "visual_document": (visual or {}).get("label") or "",
        "visual_classification": (visual or {}).get("classification") or "",
        "visual_recovered": visual_recovered,
        "visual_partially_recovered": visual_partial,
        "visual_unresolved": visual_unresolved,
        "true_north_premise": north if (visual or {}).get("document_category") == "survey" else None,
        "survey_reference": bool(reference),
        "survey_reference_note": (reference or {}).get("source_note") or "",
        # the examination result as the customer sees it
        "established": _lines("established"),
        "interpretation": _lines("interpretation"),
        "not_established": _lines("not_established"),
        # the recovered text, and HOW it was recovered
        "recovered_text": evidence,
        "text_was_read_from_the_image": bool(recovered.get("was_recovered")),
        "read_by": recovered.get("read_by") or [],
        "history": history,
        "question": (question or "").strip()[:MAX_QUESTION_CHARS],
    }


def render_prompt(context: dict[str, Any]) -> str:
    """The context as the single user message. No image, ever."""
    parts = ["DOCUMENT: %s (file: %s)" % (context["document_name"], context["file_name"])]
    if context["is_image"]:
        how = ("read off the image by %s" % ", ".join(context["read_by"])
               if context["read_by"] else "read off the image")
        parts.append("This document is an IMAGE. Any text below was %s. "
                     "You cannot see the image itself." % how)

    # CLAUDE-SURVEY-REFERENCE-01. Placed BEFORE the recovered text, because on
    # a survey image it is the substantive answer and the text is fragments.
    if context.get("visual_ran"):
        if context.get("true_north_premise"):
            import json
            parts.append("TRUE NORTH PREMISE (governs all directional semantics): " + json.dumps(context["true_north_premise"], sort_keys=True))
        visual = ["VISUAL EXAMINATION - what GO saw when it looked at this "
                  "document. This is GO's reading, not the document speaking."]
        if context.get("visual_document"):
            visual.append("Document: %s (classification: %s)"
                          % (context["visual_document"],
                             context.get("visual_classification") or "unstated"))
        if context.get("visual_recovered"):
            visual.append("Recovered:\n%s" % "\n".join(
                "- " + item for item in context["visual_recovered"]))
        if context.get("visual_partially_recovered"):
            visual.append("Partially recovered - legible in part only:\n%s" % "\n".join(
                "- " + item for item in context["visual_partially_recovered"]))
        if context.get("visual_unresolved"):
            visual.append("Unresolved claims - a quoted observation may be readable while its binding, reference system or permitted use is unproven. "
                          "Preserve the qualified observation; do not supply or promote an unestablished conclusion:\n%s" % "\n".join(
                              "- " + item for item in context["visual_unresolved"]))
        if context.get("survey_reference"):
            visual.append("A SURVEY REFERENCE has been produced from this "
                          "reading and is available to the person as a PDF. %s "
                          "It is a derived working reference, never a certified "
                          "or legal survey."
                          % (context.get("survey_reference_note") or ""))
        parts.append("\n".join(visual))
    parts.append("EXAMINATION RESULT (%s)" % context["state"])
    for label, key in (("Established from the file", "established"),
                       ("GO's reading", "interpretation"),
                       ("Not established", "not_established")):
        if context[key]:
            parts.append("%s:\n%s" % (label, "\n".join("- " + x for x in context[key])))
    if context["recovered_text"]:
        parts.append("TEXT RECOVERED FROM THIS DOCUMENT:\n%s" % context["recovered_text"])
    else:
        parts.append("No text was recovered from this document.")
    if context["history"]:
        parts.append("EARLIER IN THIS CONVERSATION:\n%s" % "\n".join(
            "%s: %s" % ("Person" if h["role"] == ROLE_HUMAN else "GO", h["text"])
            for h in context["history"]))
    parts.append("THE PERSON ASKS:\n%s" % context["question"])
    return "\n\n".join(parts)


def _failure_message(parse_status) -> str:
    """The sentence that matches what actually happened.

    Deliberately three outcomes and no more. A person needs to know whether to
    retry, rephrase, or wait - and those are the only three actions available
    to them. Nothing here names a format, a provider, a model or a status code:
    the distinction that matters to the reader is "it never answered" versus
    "it answered and I could not use it", not how the answer was malformed.
    """
    from services import llm_gateway

    if parse_status == llm_gateway.PARSE_TRUNCATED:
        return TRUNCATED_MESSAGE
    if parse_status == llm_gateway.PARSE_MALFORMED:
        return MALFORMED_MESSAGE
    return UNAVAILABLE_MESSAGE


def ask(document, workspace, result: dict, question: str, *, app) -> dict[str, Any]:
    """One question, one answer. Returns {"ok", "answer", "reason"}.

    NEVER raises for a provider problem - an outage is an outcome the customer
    is told about, not a 500. And never a silent fallback: if the provider did
    not answer, the reply says so instead of offering something weaker while
    looking the same.
    """
    from services import llm_gateway

    api_key = app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"ok": False, "answer": NOT_CONFIGURED_MESSAGE,
                "reason": "no_api_key"}

    context = build_context(document, workspace, result, question)
    outcome = llm_gateway.call_llm_json(
        user_prompt=render_prompt(context),
        system_prompt=SYSTEM_PROMPT,
        api_key=api_key,
        model=app.config.get("ANTHROPIC_MODEL"),
        max_tokens=1200,
        log_label="Document Shop conversation",
        # image_base64 / image_media_type are deliberately NOT passed. The
        # customer's image never leaves this host.
    )

    if not getattr(outcome, "ran", False):
        # WHICH FAILURE IT WAS, in the person's words and without internals.
        # "did not respond" is reserved for the case where that is true.
        return {"ok": False,
                "answer": _failure_message(getattr(outcome, "parse_status", None)),
                "reason": getattr(outcome, "skipped_reason", None) or "not_run"}

    parsed = getattr(outcome, "parsed", None) or {}
    answer = (parsed.get("answer") or "").strip()
    if not answer:
        # A well-formed reply carrying no answer is also something that came
        # back and could not be used - not an absent service.
        return {"ok": False, "answer": MALFORMED_MESSAGE, "reason": "empty_answer"}
    return {"ok": True, "answer": answer, "reason": None}


# How many times a conversation turn will re-read and re-apply before it gives
# up. Matches services.perception_worker.CONCURRENT_WRITE_RETRIES deliberately:
# the two are the same contention, seen from opposite ends.
CONCURRENT_WRITE_RETRIES = 5


def _post_with_retry(store, workspace, role: str, text: str,
                     actor: Optional[str] = None):
    """Append one message, tolerating a write that landed underneath us.

    CLAUDE-CUSTOMER-CONTAINMENT-01. `CaseWorkspaceStore.save` is optimistic-
    concurrency: it refuses to overwrite a record that moved since it was read.
    That is correct, and it was being paid for by the wrong person.

    The route reads the workspace, asks the provider - seconds, not
    milliseconds - and only then writes. The perception worker is writing
    recovered evidence to that SAME workspace throughout, and legitimately so.
    So the losing write is not a rare double-tap; it is the ordinary case of
    asking a question while the document is still being read, and the customer
    was shown "Someone else saved first" for a conflict with a background job
    that is nobody else and is not an error.

    The worker already re-reads and re-applies from its side
    (perception_worker._write_evidence_with_retry). This is the same tolerance
    from the customer's side, and it is per-message rather than around the pair
    on purpose: retrying both would re-post a question that was already stored.

    Returns the workspace actually written to, so the caller's second message
    continues from the record this one produced rather than the stale one.
    """
    last_error = None
    for attempt in range(CONCURRENT_WRITE_RETRIES):
        try:
            store.add_message(workspace, None, role, text, actor=actor)
            return workspace
        except Exception as exc:
            if type(exc).__name__ not in ("ConcurrentModificationError",
                                          "WriteCollisionError"):
                raise
            last_error = exc
            fresh = store.get(workspace.project_id)
            if fresh is None:
                raise
            workspace = fresh
            time.sleep(0.05 * (attempt + 1))
    raise last_error


def record_turn(store, workspace, *, actor: str, question: str,
                answer: str, governance_log=None) -> None:
    """Persist the exchange onto THIS document's conversation.

    Two messages through the existing `add_message`, case_id=None, which is the
    established route into project_conversation. Nothing else about the
    workspace is touched - the examination result, its evidence and its sources
    are exactly as they were.

    Each message is written through `_post_with_retry`, because the document is
    frequently still being examined while its owner is asking about it.
    """
    workspace = _post_with_retry(store, workspace, ROLE_HUMAN, question.strip(),
                                 actor=actor)
    _post_with_retry(store, workspace, ROLE_SYSTEM, answer.strip())
