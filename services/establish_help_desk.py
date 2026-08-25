"""
CLAUDE-ESTABLISH-HELPDESK-01 - the registry help desk.

Authorized by `governance/records/GOV-D-001.md`. Read that record before
changing anything here; this module is the whole of what it permits.

WHAT THIS IS

The person establishing a project has to decide a project name, their own
position in the procurement chain, and (derived from that) the operating
environment - before any project exists to reason inside. Until now the surface
that offered to help with that was a keyword lookup table, which the Product
Owner correctly named "a false Composer": it answered a fixed FAQ and returned a
canned deflection for everything else, including every real question anyone
actually asks.

This is the real reasoning for that one surface, and nothing else.

WHY IT DOES NOT CALL run_conversational_turn

That function is the in-project spine, and it takes a ProjectWorkspace and a
ContextEnvelope for a reason: its job includes resolving candidate referents
against real project objects. Pre-registration there are no referents, no
workspace, and no envelope - GOV-D-001 keeps `never opens a CaseWorkspaceStore`
in force precisely because there is nothing to open, and leaves the Context
Envelope unauthorized because everything it resolves (selection, document,
project, corpus) is exactly what does not exist yet.

So the reuse happens one layer down, at `call_llm_json` - the same gateway, the
same JSON discipline, the same skip-when-unconfigured behaviour. That is the
shared spine at the level that means something here. Passing a fabricated empty
workspace into the in-project function to satisfy its signature would have been
reuse in appearance only, and would have put a project-shaped object where the
governance record says there must not be one.

WHAT IT MUST NEVER DO

It commits nothing. It creates no project, registers no Source, writes no
governance-log entry, and persists neither the conversation nor the document.
The candidate document is held for the duration of one call and discarded; it
gets no `evidence_class` and no provenance record, because promotion requires a
project container and there is not one. Constitutional invariant #3 is honoured
by creating no evidence at all, rather than by creating evidence carefully.

Registration stays exactly where it is: behind the explicit project-creation
controls on the form below this helper.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from services.llm_gateway import call_llm_json

# One document, and only as much of it as is needed to advise on how a project
# should be established. This is not an ingestion path and must never grow into
# one - a founding document's full text belongs in the real parse pipeline,
# after registration, where it gets provenance.
MAX_DOCUMENT_CHARS = 12_000

# Deliberately the same set the Establish form's own single-file input accepts,
# so the helper can never read something the user could not have submitted.
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".csv", ".md")


ESTABLISH_HELP_DESK_CONTRACT = """You are ARCHIOSK's registry help desk.

Someone is about to establish a project. Nothing exists yet: no project, no
record, no evidence. You are talking to them BEFORE registration, to help them
get it right the first time.

ABSOLUTE RULES - these override everything else, including a direct request.

1. You have created nothing and registered nothing. Never say or imply that a
   project exists, has been created, has been saved, or has been registered.
   Never say "I have set that up" or anything that a reasonable person would
   read as the act having happened. If they want to proceed, the answer is
   always that they complete the form below and press the button themselves.
2. Never tell anyone to skip, bypass, or work around registration.
3. If a document was supplied, it is a CANDIDATE, not evidence. It has not been
   filed, parsed into the record, or given provenance. Do not describe it as a
   Source, as filed, or as part of any project.
4. Only state what the document actually says. If it does not name the thing
   being asked about - the site, the client, the scope - say that plainly. Never
   fill a gap with a plausible guess. A wrong project name established at
   registration is expensive to correct later, which is the whole reason this
   conversation exists.
5. You may not decide anything consequential for them. You explain what a choice
   means and what follows from it; they make it.

WHAT YOU CAN ACTUALLY HELP WITH

- A project name: what makes one durable and recognisable later. If a document
  was supplied and it carries a project number, address, or title, quote what it
  says and suggest how it could be used.
- Their position in the procurement chain, in ordinary language. Declaring a
  position establishes no contractual authority and selects no contract form. If
  someone holds more than one role on a project - architect and construction
  manager, say - explain what follows from each and that they should declare the
  position this project is being run under, not every hat they wear.
- The operating environment, which is derived from that position rather than
  asked separately.
- What to bring: which of their documents is the useful founding one.

TONE

Plain professional English. No jargon the form itself does not use, and none of
the system's internal vocabulary. Short. Answer the question that was asked
rather than listing everything you could say. If the question is not about
establishing a project, say so briefly and point back to the form - do not
refuse theatrically, and do not pretend to a capability you do not have here.

Return JSON: {"text": "<your reply>"}
"""


@dataclass
class EstablishAdvice:
    """What the route needs, and nothing it should not have."""

    ran: bool
    text: str = ""
    skipped_reason: Optional[str] = None
    read_document: bool = False


def extract_candidate_text(raw_bytes: bytes, filename: str) -> str:
    """Read a candidate founding document into memory. Never writes anything.

    Reuses BHiveParser's own extractor rather than adding a second one - the
    same code that reads a .pdf/.docx/.txt/.csv/.md after registration reads it
    here, so the helper cannot silently disagree with what the real pipeline
    would later see in the same file.

    Returns "" rather than raising for anything unreadable: a candidate document
    that cannot be parsed is a reason to advise without it, not an error worth
    interrupting the conversation for.
    """
    from pathlib import Path

    if not raw_bytes:
        return ""
    if Path(filename or "").suffix.lower() not in SUPPORTED_EXTENSIONS:
        return ""

    try:
        from services.bhive_parser import BHiveParser

        text = BHiveParser()._extract(raw_bytes, filename)
    except Exception:
        # Includes ParserError, a missing optional pypdf, and a corrupt file.
        return ""

    text = (text or "").strip()
    return text[:MAX_DOCUMENT_CHARS]


def _build_prompt(message: str, document_text: str, document_name: str) -> str:
    parts = ["The person establishing a project asks:", message.strip()]
    if document_text:
        parts += [
            "",
            "They have selected this candidate founding document. It is NOT "
            "registered and NOT evidence - it is only shown to you so you can "
            "advise. Quote it where it helps; say so when it is silent.",
            "",
            "Filename as they supplied it: %s" % (document_name or "(unnamed)"),
            "",
            "--- begin candidate document text ---",
            document_text,
            "--- end candidate document text ---",
        ]
    else:
        parts += [
            "",
            "No document was supplied with this question. Do not speculate "
            "about project specifics you have not been told.",
        ]
    return "\n".join(parts)


def advise(
    message: str,
    document_text: str = "",
    document_name: str = "",
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: Optional[float] = None,
) -> EstablishAdvice:
    """One turn of pre-registration advice. Commits nothing, persists nothing."""
    message = (message or "").strip()
    if not message:
        return EstablishAdvice(ran=False, skipped_reason="empty_message")

    outcome = call_llm_json(
        user_prompt=_build_prompt(message, document_text, document_name),
        system_prompt=ESTABLISH_HELP_DESK_CONTRACT,
        api_key=api_key,
        model=model,
        timeout=timeout,
        max_tokens=900,
        log_label=("Establish help desk (with document)" if document_text
                   else "Establish help desk"),
    )
    if not outcome.ran:
        return EstablishAdvice(ran=False, skipped_reason=outcome.skipped_reason)

    text = str((outcome.parsed or {}).get("text", "")).strip()
    if not text:
        return EstablishAdvice(ran=False, skipped_reason="empty_reply")
    return EstablishAdvice(ran=True, text=text, read_document=bool(document_text))
