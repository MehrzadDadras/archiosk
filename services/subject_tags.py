"""CLAUDE-MUSCLE-F3-01 - the shared referent that lets text and drawings meet.

    A SPECIFICATION AND A DRAWING SCHEDULE CANNOT BE RELATED UNTIL THEY ARE
    TALKING ABOUT THE SAME NAMED THING.

An RFP package is not text documents plus drawings side by side. A clause says
"AHU-1 shall be provided with...", a mechanical schedule on M-501 has a row
labelled AHU-1, and a plan shows it in Room 203. Those are three pieces of
evidence about one subject, and nothing in this application could say so -
not because the relationships were missing, but because there was no shared
KEY to relate them by.

So this module does one small thing: it turns a piece of text from either
modality into a normalised subject key.

    "AHU-1"  "AHU 1"  "ahu-01"   ->  equipment:AHU-1
    "Room 203"  "RM. 203"        ->  room:203
    "3/A-401"                    ->  detail:A-201:3   (via detail_callout)

WHAT THIS MODULE DOES NOT DO, deliberately:

- It creates NO new relationship type. `same_subject_as`, `corresponds_to` and
  `depicts` already exist in `case_workspace` and already express everything
  needed once both ends carry the same key.
- It creates NO new storage. A subject key belongs on the EvidenceItem or
  AddressableRegion that already addresses the text.
- It does NOT own drawing/detail references. `services/detail_callout.py` and
  `services/sheet_identity.py` already parse sheet tokens and detail callouts,
  are already wired into `perception_worker`, and are the authority for that
  shape. This module DELEGATES to them rather than re-implementing the parse,
  because two regexes for one notation is how the two drift apart.

NORMALISATION IS LOSSY, SO THE VERBATIM SURVIVES. Every extraction keeps the
text exactly as it was read alongside the key it normalised to - the same rule
`sheet_identity.index_entries` already follows. A later reader must always be
able to see what the document actually said, not only what this module decided
it meant.

CONSERVATIVE BY DESIGN. A token that is merely tag-SHAPED is not a subject. A
bare "1", a date, a dimension and a page number all look like tags to a greedy
matcher, so the equipment pattern requires a recognised prefix and the room
pattern requires a room word. Missing a real tag costs a relationship that a
human can still make; inventing one puts a false subject into the evidence
graph.
"""
from __future__ import annotations

import re
from typing import Optional

SUBJECT_VERSION = "subject-tags@1"

KIND_EQUIPMENT = "equipment"
KIND_ROOM = "room"
KIND_DETAIL = "detail"
KIND_SHEET = "sheet"
SUBJECT_KINDS = (KIND_EQUIPMENT, KIND_ROOM, KIND_DETAIL, KIND_SHEET)

#: Equipment prefixes this module will recognise. A CLOSED list on purpose:
#: an open matcher on "<letters>-<digits>" swallows sheet numbers (A-201),
#: spec sections (2-14) and revision marks. Extending it is a deliberate act.
EQUIPMENT_PREFIXES = (
    "AHU", "RTU", "FCU", "VAV", "CU", "CUH", "EF", "SF", "RF", "MAU",
    "P", "CP", "HP", "B", "CH", "CT", "WH", "HX",
    "TX", "MCC", "ATS", "UPS", "PNL", "DP", "GEN",
    "FD", "SD", "FSD", "VFD", "DDC",
)

_EQUIPMENT = re.compile(
    r"\b(" + "|".join(sorted(EQUIPMENT_PREFIXES, key=len, reverse=True)) +
    r")[\s\-\.]?(\d{1,3})([A-Z]?)\b", re.IGNORECASE)

#: A room needs a room WORD. "203" on its own is a number, not a subject.
_ROOM = re.compile(r"\b(?:ROOM|RM)\.?\s*#?\s*([A-Z]?\d{1,4}[A-Z]?)\b",
                   re.IGNORECASE)


def _clean(text) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def normalise_equipment(prefix: str, number: str, suffix: str = "") -> str:
    """AHU / 01 / '' -> AHU-1. Leading zeros are not identity."""
    return "%s-%s%s" % (prefix.strip().upper(), str(int(number)),
                        (suffix or "").strip().upper())


def normalise_room(number: str) -> str:
    return str(number or "").strip().upper()


def subject_key(kind: str, identifier: str) -> str:
    """The key both modalities must agree on. One string, comparable by =="""
    return "%s:%s" % (kind, identifier)


def subjects_in(text: Optional[str], *, sheet_token: Optional[str] = None) -> list:
    """Every subject this text names, each with the verbatim that produced it.

    Order follows first appearance, and a subject named twice is returned once
    - a clause that mentions AHU-1 three times is still about one subject.
    """
    body = _clean(text)
    if not body:
        return []

    found, seen = [], set()

    for match in _EQUIPMENT.finditer(body):
        prefix, number, suffix = match.group(1), match.group(2), match.group(3)
        identifier = normalise_equipment(prefix, number, suffix)
        key = subject_key(KIND_EQUIPMENT, identifier)
        if key in seen:
            continue
        seen.add(key)
        found.append({"kind": KIND_EQUIPMENT, "identifier": identifier,
                      "key": key, "verbatim": match.group(0).strip(),
                      "version": SUBJECT_VERSION})

    for match in _ROOM.finditer(body):
        identifier = normalise_room(match.group(1))
        key = subject_key(KIND_ROOM, identifier)
        if key in seen:
            continue
        seen.add(key)
        found.append({"kind": KIND_ROOM, "identifier": identifier,
                      "key": key, "verbatim": match.group(0).strip(),
                      "version": SUBJECT_VERSION})

    # Sheet and detail NOTATION is parsed by `sheet_identity.sheet_token`,
    # which is the authority for it and is already wired. This module only
    # decides what counts as a subject.
    from services import sheet_identity

    # EQUIPMENT WINS OVER SHEET, and this is not a tie-break detail. "AHU-1"
    # is sheet-SHAPED - letters, separator, digits - so a sheet matcher claims
    # it happily and the evidence graph gains a sheet that does not exist. An
    # equipment prefix is a closed, deliberate list; a sheet prefix is any
    # letters at all. The narrower claim is the safer one.
    claimed = {s["verbatim"].upper().replace(" ", "").replace(".", "")
               for s in found}

    for word in re.split(r"[\s,;|]+", body):
        verbatim = word.strip().strip(".:()[]")
        if not verbatim:
            continue
        if verbatim.upper().replace(" ", "").replace(".", "") in claimed:
            continue

        # "3/A-401" - a detail on a sheet. Split once, delegate the sheet half.
        if "/" in verbatim:
            number, _, sheet_part = verbatim.partition("/")
            token = sheet_identity.sheet_token(sheet_part.strip())
            if token and number.strip().isdigit():
                identifier = "%s:%s" % (token, str(int(number.strip())))
                key = subject_key(KIND_DETAIL, identifier)
                if key not in seen:
                    seen.add(key)
                    found.append({"kind": KIND_DETAIL, "identifier": identifier,
                                  "key": key, "verbatim": verbatim,
                                  "version": SUBJECT_VERSION})
                continue

        token = sheet_identity.sheet_token(verbatim)
        if token is None:
            continue
        key = subject_key(KIND_SHEET, token)
        if key in seen:
            continue
        seen.add(key)
        found.append({"kind": KIND_SHEET, "identifier": token, "key": key,
                      "verbatim": verbatim, "version": SUBJECT_VERSION})

    return found


def shared_subjects(text_a: Optional[str], text_b: Optional[str]) -> list:
    """Subject keys named by BOTH texts - the join a bridge relationship needs.

    Returning keys rather than creating relationships is deliberate: deciding
    that two pieces of evidence are about the same subject is this module's
    job, and RECORDING that decision belongs to the governed relationship
    primitives that already exist.
    """
    keys_b = {s["key"] for s in subjects_in(text_b)}
    return [s for s in subjects_in(text_a) if s["key"] in keys_b]
