"""CLAUDE-MUSCLE-F1-01 - reading a value and attaching it are two claims.

    A NUMBER YOU CAN READ PERFECTLY MAY BELONG TO SOMETHING ELSE.

This module exists because of a defect found on a live record, and the defect
is worth stating exactly because every extractor in this application can
reproduce it.

The Castille survey prints `144.12` immediately above the run labelled LOT
LINE 3. The extractor read that text cleanly and stored it against that
segment with `certainty: RECOVERED`. RECOVERED was true of READING the text -
it is large, clear and unambiguous - and unproven of the ATTACHMENT, which
rested on the annotation being printed near the line. A scale cross-check
later agreed only to about six percent, and the sheet is photographed at an
angle so no tighter proof was available.

One field was carrying two different claims, and the stronger one won
silently. On a survey with five runs that is one wrong number. On a
procurement package with thousands of schedule rows and notes it is a
systematic, confident error.

So the two claims are separated:

    read_certainty  - how sure are we what this says?
    bind_certainty  - how sure are we what it belongs to?

THE WEAKER ONE GOVERNS ANY USE OF THE VALUE. `bound_certainty` is what a
consumer must ask for, and it never returns better than either input. A value
read perfectly and attached by proximity is a PARTIALLY_RECOVERED fact about
its object, however crisp the digits.

WHY A BASIS, NOT JUST A NUMBER. `bind_basis` records HOW the attachment was
made, because the honest ceiling differs by method. Text printed inside a
schedule cell belongs to that row by construction. Text printed near a line
belongs to it by inference, and no amount of confidence in the reading can
raise that. `ceiling_for` encodes those ceilings in one place so that a future
extractor cannot quietly claim a stronger basis than it has earned.

This module is deliberately tiny and has no dependencies beyond the certainty
vocabulary it shares with `visual_examination`. It is meant to be imported by
every extractor that attaches a value to an object.
"""
from __future__ import annotations

from typing import Optional

from services.visual_examination import (
    PARTIALLY_RECOVERED,
    RECOVERED,
    UNRESOLVED,
    WITHHELD_AS_UNSAFE,
)

BINDING_VERSION = "binding@1"

#: Weakest first. `weaker` compares positions in this order, so adding a state
#: means placing it here once rather than editing every comparison.
CERTAINTY_ORDER = (
    WITHHELD_AS_UNSAFE,
    UNRESOLVED,
    PARTIALLY_RECOVERED,
    RECOVERED,
)

# -- How an attachment was made ---------------------------------------------

#: The value is printed ON the object, or inside a container that IS the object
#: (a schedule cell, a title-block field). Attachment is structural.
BIND_BASIS_STRUCTURAL = "structural"

#: The object names itself and the value names the same object - a tag match, a
#: sheet token, an explicit reference. Attachment is by shared identity.
BIND_BASIS_DECLARED = "declared"

#: The value sits near the object and nothing else claims it. This is an
#: INFERENCE, and it is where the Castille defect lives.
BIND_BASIS_PROXIMITY = "proximity"

#: Attachment was asserted by a model with no structural or declared support.
BIND_BASIS_ASSERTED = "asserted"

#: No attachment was established at all.
BIND_BASIS_NONE = "none"

BIND_BASES = (BIND_BASIS_STRUCTURAL, BIND_BASIS_DECLARED, BIND_BASIS_PROXIMITY,
              BIND_BASIS_ASSERTED, BIND_BASIS_NONE)

#: The best `bind_certainty` each basis may ever claim. THE CEILING IS THE
#: POINT OF THIS MODULE: proximity and assertion can never reach RECOVERED,
#: however legible the text or however confident the reader sounded.
_CEILING = {
    BIND_BASIS_STRUCTURAL: RECOVERED,
    BIND_BASIS_DECLARED: RECOVERED,
    BIND_BASIS_PROXIMITY: PARTIALLY_RECOVERED,
    BIND_BASIS_ASSERTED: PARTIALLY_RECOVERED,
    BIND_BASIS_NONE: UNRESOLVED,
}


def rank(certainty) -> int:
    """Position in CERTAINTY_ORDER; unknown values rank as the weakest."""
    try:
        return CERTAINTY_ORDER.index(str(certainty or "").strip().upper())
    except ValueError:
        return 0


def weaker(a, b) -> str:
    """The less certain of two states. Never returns better than either."""
    return a if rank(a) <= rank(b) else b


def ceiling_for(bind_basis) -> str:
    """The strongest `bind_certainty` this attachment method may claim."""
    return _CEILING.get(str(bind_basis or "").strip().lower(), UNRESOLVED)


def bind_certainty(bind_basis, claimed: Optional[str] = None) -> str:
    """The honest binding certainty for an attachment.

    A claim stronger than the basis allows is LOWERED to the ceiling rather
    than refused: the attachment is still real, it is just not as sure as the
    caller thought. A claim weaker than the ceiling is kept - a reader who says
    it is unsure about an attachment it made structurally is believed.
    """
    limit = ceiling_for(bind_basis)
    if claimed is None:
        return limit
    return weaker(claimed, limit)


def bind(value, *, read_certainty: str, bind_basis: str,
         claimed_bind_certainty: Optional[str] = None,
         bound_to: Optional[str] = None, note: str = "") -> dict:
    """One value, attached to one object, carrying both claims separately.

    The returned record is what every extractor should store instead of a bare
    `certainty`. `bound_certainty` is precomputed so that a consumer reading
    the record casually still gets the honest answer - the failure this module
    prevents must not depend on a caller remembering to call a function.
    """
    resolved_bind = bind_certainty(bind_basis, claimed_bind_certainty)
    return {
        "value": value,
        "read_certainty": read_certainty,
        "bind_certainty": resolved_bind,
        "bind_basis": bind_basis,
        "bound_to": bound_to,
        "bound_certainty": weaker(read_certainty, resolved_bind),
        "binding_version": BINDING_VERSION,
        "note": note,
    }


def bound_certainty(record) -> str:
    """What a consumer may claim when USING this value against its object.

    Always the weaker of the two. A perfectly legible number attached by
    proximity is a PARTIALLY_RECOVERED fact about the thing it is attached to,
    and this is the function that refuses to forget that.
    """
    if not isinstance(record, dict):
        return UNRESOLVED
    def state(value):
        value = str(value or "").strip().upper()
        return value if value in CERTAINTY_ORDER else UNRESOLVED

    result = weaker(state(record.get("read_certainty")),
                    state(record.get("bind_certainty")))
    if "bind_basis" in record:
        result = weaker(result, ceiling_for(record["bind_basis"]))
    # A stored aggregate is a cache, never authority to strengthen either
    # component. Preserve a more conservative stored decision as well.
    if "bound_certainty" in record:
        result = weaker(result, state(record["bound_certainty"]))
    return result


def is_value_bearing(record) -> bool:
    """May this value be used to state something about its object at all?"""
    from services.visual_examination import VALUE_BEARING

    return bound_certainty(record) in VALUE_BEARING
