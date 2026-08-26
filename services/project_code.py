"""
CLAUDE-PROJECT-CODE-01 - the governed 3-or-4-letter project acronym, and the
human-readable references built from it.

WHY THIS EXISTS

People say "SRPC-T-014" in a meeting. They do not say a UUID. The Product Owner
wants short, durable references usable in conversation, reports, email and
notifications - and every project therefore needs a governed acronym to build
them from.

Repository inspection found NO existing acronym or project-code concept: only
`ProjectWorkspace.display_title` (the visible name, globally unique, enforced by
services/ingestion.py's own _reject_if_name_taken) and the opaque `project_id`.
So this is a new field, not a competing second system - there was no first one.

THE ONE DESIGN DECISION THAT MATTERS

An issued reference is STORED on the record, never re-derived at render time.

That is what makes an acronym change safe. If references were computed from the
project's current code, renaming a project would silently rewrite every
historical reference in every report and email that already quoted it - exactly
what the direction forbids. Because each Task and Case keeps the string it was
issued, history says what it always said, and a later acronym change affects only
what is issued afterwards.

The sequence follows the convention already established for `region_index`:
1-based, per-project, per-type, assigned once at creation, never renumbered by a
later deletion. Task and Case sequences are independent - SRPC-T-014 and
SRPC-C-014 can both exist, because the type discriminator distinguishes them.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

CODE_MIN_LENGTH = 3
CODE_MAX_LENGTH = 4
_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]{2,3}$")

# Type discriminators. Deliberately single letters: the reference has to survive
# being read aloud and typed from memory.
REFERENCE_TYPE_TASK = "T"
REFERENCE_TYPE_CASE = "C"

# Words that carry no identifying signal in a project name. Kept short and
# obvious on purpose - this is an abbreviation helper, not a linguistics
# project, and the user can always edit the result.
# "project" is deliberately NOT here. This repository's own governed synthetic
# identity is Project Smoke Detector = PSD (CLAUDE-PSD-FOUNDATION-01), and
# dropping the word as noise derives SMOK instead - inventing a second acronym
# for a project that already has an authoritative one, which the direction
# explicitly forbids. Real project names use the word meaningfully.
_NOISE_WORDS = frozenset({
    "the", "a", "an", "of", "for", "and", "at", "in", "on", "to",
})


class ProjectCodeError(ValueError):
    """A proposed acronym cannot be used, with a reason a person can act on."""


def normalize_code(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", (raw or "")).upper()


def is_valid_code(raw: str) -> bool:
    return bool(_CODE_PATTERN.match(normalize_code(raw)))


def validate_code(raw: str, taken: Iterable[str] = ()) -> str:
    """Return the normalized code, or raise with a message worth showing."""
    code = normalize_code(raw)
    if not code:
        raise ProjectCodeError("A project acronym is required.")
    if len(code) < CODE_MIN_LENGTH or len(code) > CODE_MAX_LENGTH:
        raise ProjectCodeError(
            "A project acronym must be %d or %d letters." % (CODE_MIN_LENGTH, CODE_MAX_LENGTH))
    if not _CODE_PATTERN.match(code):
        raise ProjectCodeError(
            "A project acronym must start with a letter and use only letters and digits.")
    if code in {normalize_code(t) for t in taken}:
        raise ProjectCodeError("That project acronym is already in use.")
    return code


def derive_code(project_name: str, taken: Iterable[str] = ()) -> str:
    """Propose an acronym from a project name.

    Initials of the significant words first, because that is what a person would
    have written themselves - "South Regional Police Centre" gives SRPC. Falls
    back through progressively less elegant strategies rather than failing, and
    only ever resorts to a numeric suffix when the obvious forms are taken.
    """
    taken_norm = {normalize_code(t) for t in taken if t}
    words = [w for w in re.split(r"[^A-Za-z0-9]+", project_name or "") if w]
    significant = [w for w in words if w.lower() not in _NOISE_WORDS] or words

    # A code must start with a letter, so lead with the words that can provide
    # one. Real project names here often begin with a job number - "222109 1860
    # Alstep Dr" - and initialling those gives "21AD", which is invalid and,
    # worse, unrecognizable. Prefer the words a person would actually say.
    lettered = [w for w in significant if w[:1].isalpha()]
    if lettered:
        significant = lettered

    candidates: list[str] = []

    initials = "".join(w[0] for w in significant).upper()
    if len(initials) >= CODE_MAX_LENGTH:
        candidates.append(initials[:CODE_MAX_LENGTH])
    if CODE_MIN_LENGTH <= len(initials) <= CODE_MAX_LENGTH:
        candidates.append(initials)

    # One significant word ("Riverside") reads better truncated than initialled.
    if significant:
        first = re.sub(r"[^A-Za-z0-9]", "", significant[0]).upper()
        if len(first) >= CODE_MAX_LENGTH:
            candidates.append(first[:CODE_MAX_LENGTH])
        if len(first) >= CODE_MIN_LENGTH:
            candidates.append(first[:CODE_MIN_LENGTH])

    # Two short words ("Elm Court") - take letters from each.
    if len(significant) >= 2:
        candidates.append((significant[0][:2] + significant[1][:2]).upper())

    for candidate in candidates:
        if is_valid_code(candidate) and normalize_code(candidate) not in taken_norm:
            return normalize_code(candidate)

    # Everything obvious is taken or unusable. Vary the last character rather
    # than lengthening: the reference has to stay short to be worth having.
    base = next((normalize_code(c) for c in candidates
                 if normalize_code(c)[:1].isalpha()), "PRJ")
    stem = base[:CODE_MIN_LENGTH] or "PRJ"
    if not stem[:1].isalpha():
        stem = "PRJ"
    for suffix in "23456789":
        candidate = (stem + suffix)[:CODE_MAX_LENGTH]
        if is_valid_code(candidate) and normalize_code(candidate) not in taken_norm:
            return normalize_code(candidate)
    for suffix in range(10, 100):
        candidate = (stem[:2] + str(suffix))
        if is_valid_code(candidate) and normalize_code(candidate) not in taken_norm:
            return candidate
    raise ProjectCodeError("Could not derive a unique project acronym.")


def format_reference(code: str, reference_type: str, sequence: int) -> str:
    """SRPC-T-014. Zero-padded to three digits, and never truncated beyond it -
    a project's 1000th Task is SRPC-T-1000, which is ugly but honest, where
    wrapping to SRPC-T-000 would collide with real history."""
    return "%s-%s-%03d" % (normalize_code(code), reference_type, int(sequence))


def next_sequence(existing_references: Iterable[str], reference_type: str) -> int:
    """One past the highest sequence ever ISSUED for this type.

    Derived from the issued references themselves rather than from a counter or
    from len(records), so deleting a record can never cause the next one to
    reuse its reference - the same "assigned once, never renumbered" property
    region_index already relies on.
    """
    highest = 0
    pattern = re.compile(r"^[A-Z0-9]{3,4}-%s-(\d+)$" % re.escape(reference_type))
    for reference in existing_references:
        match = pattern.match((reference or "").strip().upper())
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def issue_reference(
    code: Optional[str], reference_type: str, existing_references: Iterable[str],
) -> Optional[str]:
    """The reference to store on a new record, or None if the project has no
    code yet.

    Returning None is deliberate and is not a failure: a record created before
    its project was backfilled simply carries no human reference, which is
    honest. Inventing a reference against a missing code would produce a string
    that looks authoritative and identifies nothing.
    """
    if not code or not is_valid_code(code):
        return None
    return format_reference(code, reference_type, next_sequence(existing_references, reference_type))
