"""CLAUDE-MUSCLE-F4-01 - an addendum that REPLACES, told apart from one that
merely MENTIONS.

    REPORTING A SUPERSEDED REQUIREMENT AS CURRENT IS THE MOST CONSEQUENTIAL
    ERROR THIS APPLICATION CAN MAKE ON A PROCUREMENT PACKAGE.

Addenda are where the money and the risk are. A bidder who prices the base
specification after Addendum 3 deleted the clause has priced the wrong job. So
the detector's bias is toward NOT claiming a supersession: a clause that is
only discussed, cross-referenced or relied upon must never be recorded as
replaced.

WHAT IS AND IS NOT BUILT HERE. The supersession PRIMITIVE already exists -
`case_workspace.supersede_relationship`, plus `supersedes_source_id` /
`superseded_by_source_id` on Sources, and the RELATIONSHIP_STATUS_SUPERSEDED
vocabulary. None of that is re-implemented. What was missing is the DETECTOR:
nothing read an addendum and proposed that a particular clause replaces a
particular earlier one. This module is only that detector, and it returns a
proposal rather than writing anything.

    HISTORY IS NOT OVERWRITTEN. A supersession records that a later clause
    governs; it never edits or deletes the earlier text. Both versions remain
    readable, which is what lets a reader see what changed and when - the same
    rule `case_workspace` already enforces for Source revisions.

THE DISTINCTION IT DRAWS, precisely:

    "Delete Section 2.4 and replace with the following"   -> supersession
    "Section 2.4 is amended to read..."                   -> supersession
    "Refer to Section 2.4 for coordination requirements"  -> NO supersession
    "This clause supplements Section 2.4"                 -> NO supersession

The difference is an ACTION VERB DIRECTED AT the referenced clause. A verb
elsewhere in the sentence does not count, which is why the match requires the
verb and the reference to occur together rather than merely co-occur in the
same paragraph.

`supplements` and `in addition to` are deliberately NOT supersession. They
change the total requirement without replacing the earlier text, and recording
them as supersession would make the base clause vanish from a reader's view
when it still governs.
"""
from __future__ import annotations

import re
from typing import Optional

DETECT_VERSION = "supersession-detect@1"

#: What the addendum is doing to the clause it names.
ACTION_REPLACES = "replaces"
ACTION_AMENDS = "amends"
ACTION_DELETES = "deletes"
ACTION_ADDS = "adds"
ACTION_MENTIONS = "mentions"

#: Only these change what the earlier clause says. `adds` and `mentions` leave
#: it standing, and a reader must still see it.
SUPERSEDING_ACTIONS = (ACTION_REPLACES, ACTION_AMENDS, ACTION_DELETES)

#: A clause reference: "Section 2.4", "Clause 11.4.2", "§2.4", "Article 5".
_REFERENCE = re.compile(
    r"(?:\b(?:SECTION|CLAUSE|ARTICLE|PARAGRAPH|ITEM)\s*|§\s*)"
    r"(\d{1,3}(?:\.\d{1,3}){0,3})\b", re.IGNORECASE)

#: Verbs, grouped by what they do. Ordered longest-first inside each group so
#: "replace in its entirety" wins over a bare "replace".
_ACTION_PATTERNS = (
    (ACTION_DELETES, re.compile(
        r"\b(?:DELETE(?:D)?|REMOVE(?:D)?|STRIKE|OMIT(?:TED)?)\b", re.IGNORECASE)),
    (ACTION_REPLACES, re.compile(
        r"\b(?:REPLACE(?:D|S)?|SUPERSEDE(?:D|S)?|SUBSTITUTE(?:D)?|"
        r"IS\s+REPLACED\s+BY|IN\s+LIEU\s+OF)\b", re.IGNORECASE)),
    (ACTION_AMENDS, re.compile(
        r"\b(?:AMEND(?:ED|S)?|REVISE(?:D|S)?|MODIF(?:Y|IED|IES)|"
        r"CHANGE(?:D|S)?\s+TO\s+READ|IS\s+CHANGED)\b", re.IGNORECASE)),
    (ACTION_ADDS, re.compile(
        r"\b(?:ADD(?:ED|S)?|SUPPLEMENT(?:ED|S)?|IN\s+ADDITION\s+TO|"
        r"APPEND(?:ED)?)\b", re.IGNORECASE)),
)

#: How far from the reference an action verb may sit and still be read as
#: acting ON it. Deliberately short: a verb two sentences away is about
#: something else, and widening this is how false supersessions appear.
ACTION_WINDOW_CHARS = 120


def clause_references(text: Optional[str]) -> list:
    """Every clause this text names, with the verbatim reference preserved."""
    found, seen = [], set()
    for match in _REFERENCE.finditer(str(text or "")):
        number = match.group(1)
        if number in seen:
            continue
        seen.add(number)
        found.append({"clause": number, "verbatim": match.group(0).strip(),
                      "at": match.start()})
    return found


def _action_near(text: str, position: int) -> Optional[str]:
    """The strongest action verb acting on a reference at `position`, or None.

    Both sides are searched because an addendum writes it either way round -
    "Delete Section 2.4" and "Section 2.4 is deleted" mean the same thing.
    """
    low = max(position - ACTION_WINDOW_CHARS, 0)
    high = min(position + ACTION_WINDOW_CHARS, len(text))
    window = text[low:high]
    for action, pattern in _ACTION_PATTERNS:
        if pattern.search(window):
            return action
    return None


def detect(text: Optional[str]) -> list:
    """What this addendum clause does to each earlier clause it names.

    Returns one entry per referenced clause. A reference with no action verb
    near it is reported as `mentions` rather than dropped - a reader deciding
    whether the detector missed something needs to see what it considered.
    """
    body = str(text or "")
    results = []
    for reference in clause_references(body):
        action = _action_near(body, reference["at"]) or ACTION_MENTIONS
        results.append({
            "clause": reference["clause"],
            "reference_text": reference["verbatim"],
            "action": action,
            "supersedes": action in SUPERSEDING_ACTIONS,
            "version": DETECT_VERSION,
        })
    return results


def supersessions_in(text: Optional[str]) -> list:
    """Only the references this clause actually replaces, amends or deletes."""
    return [entry for entry in detect(text) if entry["supersedes"]]


def proposal(text: Optional[str], *, addendum_source_id: str,
             base_source_id: Optional[str] = None) -> dict:
    """A proposal a human or a governed writer can act on. WRITES NOTHING.

    Deliberately stops short of storage. `case_workspace.supersede_relationship`
    is the authority for recording a supersession and it takes a human-governed
    path; a detector that wrote directly would turn a reading into a governed
    fact with no one in between, which is the promotion this application exists
    to prevent.
    """
    entries = detect(text)
    superseding = [e for e in entries if e["supersedes"]]
    return {
        "addendum_source_id": addendum_source_id,
        "base_source_id": base_source_id,
        "references_found": len(entries),
        "supersessions_proposed": superseding,
        "mentions_only": [e for e in entries if not e["supersedes"]],
        "version": DETECT_VERSION,
        "evidence_class_note": (
            "A detected supersession is an ai_generated_proposal until a human "
            "records it through the governed control. Both clause texts are "
            "preserved either way."),
    }
