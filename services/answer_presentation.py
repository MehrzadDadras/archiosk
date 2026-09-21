"""CLAUDE-ANSWER-PRESENTATION-01 - the answer first, the machinery on request.

    EVIDENCE PRESERVATION IS NOT PRESENTATION REPETITION.

A person asked "Is there any stair in this drawing set?" and the reply led with
evidence admission, then the same SOURCE_REFERENCE qualification several times
over, then the same "not established as a project fact" sentence again for each
item, then raw OCR fragments. The answer was in there. It was underneath all of
that.

Every one of those sentences is TRUE, and none of them should be deleted. What
was wrong is that the machinery was rendered at the same weight as the answer,
and repeated once per evidence item rather than said once.

    RESULT FIRST -> GOVERNANCE SECOND -> TRACE ON DEMAND

So this module is a PROJECTION. It takes a GO answer that already exists and
re-orders it for reading:

    answer          the direct answer, first, in the person's words
    found_in        where it was found
    status          the qualifications, collapsed to one concise statement
    contradictions  NEVER collapsed - see below
    evidence        behind "Show evidence"
    technical       behind "Technical details" - and it holds EVERYTHING that
                    was moved out, so the canonical text is recoverable whole

WHAT THIS MODULE IS NOT.

It is not a second reporting engine, a second evidence store, or a parallel GO
path. It stores nothing, decides nothing, and calls no provider. It is a pure
function over a reply that some other owner already produced, and every caller
keeps its own result object. Removing this module would make the output uglier
and would not change a single stored fact.

    IT MUST NEVER CHANGE WHAT IS STORED. Presentation only.

CONTRADICTIONS ARE NEVER COLLAPSED, and this is the one rule worth stating
twice. Compression works by noticing that two sentences say the same thing.
Two pieces of evidence that DISAGREE also look repetitive - same subject, same
shape, similar words - and collapsing them would delete exactly the finding a
reviewer most needs. So anything carrying contradiction vocabulary is exempt
from every compression rule here and is surfaced in the primary view.

DELETION IS NOT COMPRESSION. Nothing this module moves out of the primary view
is discarded: `technical` carries the removed lines verbatim, and
`canonical_text` returns the original reply exactly as it was given. A reader
who expands everything sees what they would have seen before.
"""
from __future__ import annotations

import re
from typing import Optional

PRESENTATION_VERSION = "answer-presentation@1"

#: Sentences that qualify an answer rather than answering it. Matched
#: case-insensitively against whole sentences. Deliberately a CLOSED list of
#: phrasings this application actually emits - a loose "looks like a caveat"
#: heuristic would swallow real findings.
_QUALIFIER_PATTERNS = (
    r"not (?:yet )?(?:been )?establish(?:ed)? as (?:a )?project fact",
    r"not (?:yet )?promoted to (?:a )?project fact",
    r"source[_ ]reference evidence only",
    r"this is (?:a )?source[_ ]reference",
    r"not (?:yet )?authoritative",
    r"non-?binding",
    r"reference[- ]only",
    r"has not been adopted",
    r"remains? a proposal",
    r"is (?:a|an) (?:ai[- ])?generated proposal",
)
_QUALIFIER = re.compile("|".join(_QUALIFIER_PATTERNS), re.IGNORECASE)

#: A disagreement is never compressed. See the module docstring.
_CONTRADICTION = re.compile(
    r"\bcontradict\w*|\bconflict\w*|\bdisagree\w*|\binconsistent\b|"
    r"\bhowever\b|\bwhereas\b|\bbut the\b|\bdoes not match\b|\bmismatch\w*",
    re.IGNORECASE)

#: Lines that are machine residue rather than prose: OCR noise, identifiers,
#: hashes, state payloads. Each pattern is narrow on purpose.
_RESIDUE_PATTERNS = (
    r"^[^A-Za-z]*$",                                   # no letters at all
    r"^[A-Z0-9_]{6,}(?:\s+[A-Z0-9_]{2,}){2,}$",        # SHOUTED token runs
    r"\b[0-9a-f]{16,}\b",                              # hashes / ids
    r"^\s*\{.*\}\s*$",                                 # raw payloads
    r"^\s*[A-Za-z_]+=[^\s]+(?:\s+[A-Za-z_]+=[^\s]+)+", # key=value traces
)
_RESIDUE = re.compile("|".join(_RESIDUE_PATTERNS), re.IGNORECASE)

#: A line that forms a sentence is prose, whatever its digit count.
#:
#: THIS GUARD EXISTS BECAUSE THE RATIO TEST HID A CONTRADICTION. Sheet
#: references are digit-heavy - "A-201 contradicts A-301." is 46% non-alphabetic
#: and was classified as OCR residue, which moved a genuine disagreement out of
#: the primary answer. Drawing-set answers are FULL of sheet numbers, so the
#: ratio alone is the wrong discriminator: machine residue rarely forms a
#: sentence, and prose almost always does.
_SENTENCE_SHAPED = re.compile(r"[A-Za-z]{4,}.*[.!?]\s*$")

#: A line with this proportion of non-alphabetic characters is read as OCR
#: residue. Photographed drawings return linework as stray characters, which is
#: worth keeping and not worth leading with.
_RESIDUE_NONALPHA_RATIO = 0.45
_RESIDUE_MIN_LENGTH = 12


def _sentences(text: str) -> list:
    """Split into sentences, keeping their terminators.

    Deliberately simple. A cleverer splitter would handle abbreviations better
    and would also be a thing that can be wrong in ways nobody notices; the
    cost of a bad split here is one oddly-placed sentence, not a wrong fact.
    """
    parts = re.split(r"(?<=[.!?])\s+", str(text or "").strip())
    return [p.strip() for p in parts if p.strip()]


def _normalise(sentence: str) -> str:
    """For equality testing only - never for display."""
    return re.sub(r"[^a-z0-9]+", " ", sentence.lower()).strip()


def is_qualifier(sentence: str) -> bool:
    return bool(_QUALIFIER.search(sentence or ""))


def is_contradiction(sentence: str) -> bool:
    return bool(_CONTRADICTION.search(sentence or ""))


def is_residue(line: str) -> bool:
    """Machine residue, as opposed to something written for a person."""
    body = (line or "").strip()
    if len(body) < _RESIDUE_MIN_LENGTH:
        return False
    # An explicit machine signature wins outright - a hash or a key=value trace
    # is residue even if someone wrapped a full stop around it.
    if _RESIDUE.search(body):
        return True
    # Otherwise a sentence is prose, however many sheet numbers it carries.
    if _SENTENCE_SHAPED.search(body):
        return False
    letters = sum(1 for ch in body if ch.isalpha())
    return (1.0 - letters / len(body)) >= _RESIDUE_NONALPHA_RATIO


def collapse_repeats(sentences: list) -> tuple:
    """Say each qualification once. Returns (kept, collapsed_count).

    Only QUALIFIERS collapse. Two identical findings are not the same event and
    two contradictory ones are the whole point, so neither is touched.
    """
    kept, seen, collapsed = [], set(), 0
    for sentence in sentences:
        if is_contradiction(sentence) or not is_qualifier(sentence):
            kept.append(sentence)
            continue
        key = _normalise(sentence)
        if key in seen:
            collapsed += 1
            continue
        seen.add(key)
        kept.append(sentence)
    return kept, collapsed


def project(reply_text: Optional[str], *, grounded_in=None, evidence=None,
            status_note: Optional[str] = None) -> dict:
    """Re-order one existing GO answer for reading. Stores nothing.

    `reply_text` is the answer some other owner already produced and is never
    modified - `canonical_text` returns it verbatim. Everything else here is a
    view over it.
    """
    original = str(reply_text or "")
    lines = original.splitlines()

    prose, technical = [], []
    for line in lines:
        (technical if is_residue(line) else prose).append(line)

    sentences = _sentences("\n".join(prose))
    kept, collapsed = collapse_repeats(sentences)

    answer, qualifiers, contradictions = [], [], []
    for sentence in kept:
        if is_contradiction(sentence):
            contradictions.append(sentence)
        elif is_qualifier(sentence):
            qualifiers.append(sentence)
        else:
            answer.append(sentence)

    # THE ANSWER LEADS. If every sentence was a qualification the answer is
    # genuinely only a qualification, and saying so plainly beats an empty
    # heading above a status line.
    if not answer and qualifiers:
        answer, qualifiers = qualifiers[:1], qualifiers[1:]

    status = " ".join(qualifiers).strip()
    if status_note:
        status = (status + " " + status_note).strip() if status else status_note

    return {
        "answer": " ".join(answer).strip(),
        "found_in": list(grounded_in or []),
        "status": status,
        "contradictions": contradictions,
        "evidence": list(evidence or []),
        "technical": [line for line in technical if line.strip()],
        "collapsed_qualifications": collapsed,
        "residue_lines_moved": len([l for l in technical if l.strip()]),
        "canonical_text": original,
        "version": PRESENTATION_VERSION,
    }


def canonical_is_recoverable(view: dict, reply_text: Optional[str]) -> bool:
    """Everything moved out is still reachable, byte for byte.

    A projection that quietly dropped a line would be indistinguishable from
    one that tidied it, so this is asserted rather than assumed.
    """
    return (view or {}).get("canonical_text") == str(reply_text or "")
