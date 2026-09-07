"""
CLAUDE-DERIVED-VIEW-01 - reasoning over scaled, oriented views of a drawing page.

WHAT THIS LAYER IS FOR

`services/case_workspace.py` stores the DerivedView. This module answers the
questions that decide whether it may be USED: is this view measurable, may these
two views be compared, what does its title block actually say once a human has
corrected it, and how do coordinates move between the source page and the
normalized view.

Those are guards, not conveniences. A scaled drawing region is exactly the kind
of object where a plausible-looking number is dangerous: 1:50 read off the wrong
detail, or two plans compared across different Norths, produce answers that are
confidently and quietly wrong. So the default for every question here is NO, and
the caller has to have the evidence.

THE FOUR REFUSALS

  * `may_measure` permits only QUANTITATIVE. INFORMATIVE is refused for
    MEASUREMENT and permitted for everything else through
    `may_use_semantically` - an NTS detail or a schematic is doing its job
    perfectly while carrying no scale, and refusing to read it would discard
    most of what a drawing set actually says.
  * `may_compare_spatially` refuses views whose scale, north or rotation frames
    are not both known AND compatible - including the case where both are known
    but disagree, which is the one a naive check passes.
  * `north_reference` refuses to return a direction when the view is CONFLICTED.
    A conflict already means two drawings disagree; picking one here would erase
    the disagreement precisely where a caller would stop looking.
  * `to_view_coordinates` / `to_source_coordinates` refuse when rotation is not
    recorded, rather than assuming zero. Assuming zero is how a rotated sheet
    silently produces mirrored geometry.

NOTHING HERE DERIVES GEOMETRY

No vectorisation, no scale detection, no North detection. This module reads what
was recorded and decides what may be done with it. Detection is future work and
must arrive as evidence with a method, not as an inference made here.
"""
from __future__ import annotations

import math
from typing import Optional

from services.case_workspace import (
    NORTH_CORROBORATION_CORROBORATED,
    NORTH_CORROBORATION_INCONSISTENT,
    NORTH_CORROBORATION_UNRESOLVED,
    NORTH_KIND_CONFLICTED,
    NORTH_KIND_PROJECT,
    NORTH_KIND_REVIEW_NEEDED,
    NORTH_KIND_TRUE,
    NORTH_KIND_UNKNOWN,
    NORTH_KIND_VIEW_ORIENTATION,
    ORIENTATION_STATE_NOT_APPLICABLE,
    SCALE_STATE_INFORMATIVE,
    SCALE_STATE_QUANTITATIVE,
)

#: Angular slack when comparing two recorded North directions. Deliberately
#: tight: this is a consistency check between two RECORDED values, not a
#: tolerance for estimating one.
NORTH_AGREEMENT_TOLERANCE_DEGREES = 1.0


def effective_title_block(view: dict) -> dict:
    """The inherited sheet identity with any human override applied, at READ time.

    Composed rather than stored, so the inherited record is never overwritten -
    what the sheet said and what a person corrected both stay recoverable.
    """
    effective = dict(view.get("inherited_title_block") or {})
    effective.update(view.get("title_block_overrides") or {})
    return effective


def title_block_provenance(view: dict) -> dict:
    """Which fields are the sheet's own and which a human changed."""
    inherited = view.get("inherited_title_block") or {}
    overrides = view.get("title_block_overrides") or {}
    return {
        "inherited": dict(inherited),
        "overridden": dict(overrides),
        "overridden_fields": sorted(overrides.keys()),
        "overridden_by": view.get("overridden_by"),
        "overridden_at": view.get("overridden_at"),
    }


def may_measure(view: dict) -> tuple:
    """(allowed, reason). MEASUREMENT and quantitative reasoning only.

    INFORMATIVE is refused here and that is not a defect in the view - an NTS
    detail or a schematic is doing its job perfectly while carrying no scale to
    measure against. The honest explanation differs from UNKNOWN, so the
    messages differ: INFORMATIVE says "this drawing is not for measuring",
    UNKNOWN says "we cannot tell yet".
    """
    state = view.get("scale_state")
    if state == SCALE_STATE_INFORMATIVE:
        return False, ("This view is INFORMATIVE. It is fully usable for notes, "
                       "labels, relationships and coordination, but it carries no "
                       "reliable scale and must be calibrated separately before "
                       "any measurement.")
    if state != SCALE_STATE_QUANTITATIVE:
        return False, ("This view's scale state is %s. Measuring would turn an "
                       "unverified reading into a number." % state)
    if not view.get("scale_value"):
        return False, "The view is QUANTITATIVE but no scale value was recorded."
    if not view.get("scale_method"):
        return False, ("The scale has no recorded method, so it cannot be shown to "
                       "rest on evidence.")
    return True, "Scale is quantitative, valued and evidenced."


def may_use_semantically(view: dict) -> tuple:
    """(allowed, reason). Non-quantitative use - the common case.

    Separate from `may_measure` on purpose. An INFORMATIVE view supports OCR,
    tags, labels, relationship analysis, coordination context and even vector
    linework for visual/semantic purposes; refusing all of that because it
    cannot be measured would discard most of what a drawing set actually says.

    The rule is a boundary, not a gate: read it, reason about it, relate it -
    just never measure it.
    """
    state = view.get("scale_state")
    if state in (SCALE_STATE_QUANTITATIVE, SCALE_STATE_INFORMATIVE):
        return True, "Semantic and coordination use is permitted."
    return False, ("This view's scale state is %s, so even its intent is not "
                   "established." % state)


def north_reference(view: dict) -> dict:
    """The usable North for this view, or an honest refusal.

    Returns which KIND of north it is. True and project north are never merged:
    a comparison that mixes them is wrong by exactly the angle between them, and
    that angle is often small enough to look like a rounding error.
    """
    state = view.get("north_state")
    if state == NORTH_KIND_CONFLICTED:
        return {"usable": False, "kind": NORTH_KIND_CONFLICTED, "degrees": None,
                "reason": ("Another project document disagrees about North. Both "
                           "readings are preserved; a human decides which governs.")}
    if state in (NORTH_KIND_UNKNOWN, NORTH_KIND_REVIEW_NEEDED):
        return {"usable": False, "kind": state, "degrees": None,
                "reason": "North is %s for this view." % state}
    if state == NORTH_KIND_TRUE and view.get("true_north_degrees") is not None:
        return {"usable": True, "kind": NORTH_KIND_TRUE,
                "degrees": view["true_north_degrees"],
                "method": view.get("true_north_method"), "reason": None}
    if state == NORTH_KIND_PROJECT and view.get("project_north_degrees") is not None:
        return {"usable": True, "kind": NORTH_KIND_PROJECT,
                "degrees": view["project_north_degrees"],
                "method": view.get("project_north_method"), "reason": None}
    if state == NORTH_KIND_VIEW_ORIENTATION:
        return {"usable": False, "kind": NORTH_KIND_VIEW_ORIENTATION, "degrees": None,
                "reason": ("Only the view's own orientation is known. That is not a "
                           "North reference and must not be used as one.")}
    return {"usable": False, "kind": state, "degrees": None,
            "reason": "North state %s carries no usable direction." % state}


def north_corroboration_state(view: dict) -> str:
    """CORROBORATED / INCONSISTENT / UNRESOLVED, from the recorded checks.

    Any single disagreement makes the whole thing INCONSISTENT. Agreement
    elsewhere does not outvote it - a conflict is not resolved by counting.
    """
    checks = view.get("north_corroboration") or []
    if not checks:
        return NORTH_CORROBORATION_UNRESOLVED
    if any(not c.get("agrees") for c in checks):
        return NORTH_CORROBORATION_INCONSISTENT
    return NORTH_CORROBORATION_CORROBORATED


def _rotation(view: dict) -> Optional[float]:
    source = view.get("source_rotation_degrees")
    normalized = view.get("normalized_rotation_degrees")
    if source is None and normalized is None:
        return None
    return (normalized or 0.0) - (source or 0.0)


def to_view_coordinates(view: dict, x: float, y: float) -> tuple:
    """Source-page point -> normalized-view point.

    Refuses when no rotation was recorded rather than assuming zero: a rotated
    sheet treated as unrotated produces geometry that is wrong in a way nothing
    downstream can detect.
    """
    angle = _rotation(view)
    if angle is None:
        raise ValueError(
            "This view records no rotation, so page and view coordinates cannot "
            "be related. Assuming zero would silently mis-place geometry.")
    radians = math.radians(angle)
    origin = (view.get("region") or {})
    ox, oy = float(origin.get("x", 0.0)), float(origin.get("y", 0.0))
    dx, dy = x - ox, y - oy
    return (dx * math.cos(radians) - dy * math.sin(radians),
            dx * math.sin(radians) + dy * math.cos(radians))


def to_source_coordinates(view: dict, x: float, y: float) -> tuple:
    """Normalized-view point -> source-page point. The exact inverse."""
    angle = _rotation(view)
    if angle is None:
        raise ValueError(
            "This view records no rotation, so view and page coordinates cannot "
            "be related.")
    radians = math.radians(-angle)
    origin = (view.get("region") or {})
    ox, oy = float(origin.get("x", 0.0)), float(origin.get("y", 0.0))
    return (x * math.cos(radians) - y * math.sin(radians) + ox,
            x * math.sin(radians) + y * math.cos(radians) + oy)


def may_compare_spatially(view_a: dict, view_b: dict) -> tuple:
    """(allowed, reason). The rule that must hold before any cross-view overlay.

    Four things must be compatible - coordinate frame, North definition,
    rotation and scale - and the interesting failure is not "one is missing" but
    "both are known and they differ". A check that only tested for presence
    would pass two plans at 1:100 and 1:50 and produce an overlay wrong by a
    factor of two.
    """
    if view_a.get("project_id") != view_b.get("project_id"):
        return False, "These views belong to different projects."

    for label, view in (("first", view_a), ("second", view_b)):
        allowed, reason = may_measure(view)
        if not allowed:
            return False, "The %s view is not measurable: %s" % (label, reason)

    if view_a.get("unit_system") != view_b.get("unit_system"):
        return False, ("These views use different unit systems (%s vs %s)."
                       % (view_a.get("unit_system"), view_b.get("unit_system")))

    if float(view_a["scale_value"]) != float(view_b["scale_value"]):
        return False, ("These views are at different scales (1:%s vs 1:%s). They can "
                       "only be compared through an explicit transform."
                       % (view_a["scale_value"], view_b["scale_value"]))

    north_a, north_b = north_reference(view_a), north_reference(view_b)
    if not north_a["usable"] or not north_b["usable"]:
        return False, ("North is not established for both views (%s / %s)."
                       % (north_a["kind"], north_b["kind"]))
    if north_a["kind"] != north_b["kind"]:
        return False, ("One view is referenced to %s and the other to %s. Mixing "
                       "them without an explicit transform is wrong by the angle "
                       "between them." % (north_a["kind"], north_b["kind"]))
    if abs(float(north_a["degrees"]) - float(north_b["degrees"])) > NORTH_AGREEMENT_TOLERANCE_DEGREES:
        return False, ("The two views record different North directions "
                       "(%.2f vs %.2f degrees)."
                       % (north_a["degrees"], north_b["degrees"]))

    rot_a, rot_b = _rotation(view_a), _rotation(view_b)
    if rot_a is None or rot_b is None:
        return False, "Rotation is not recorded for both views."

    return True, "Scale, units, North reference and rotation are all compatible."


def traceability(view: dict) -> dict:
    """The chain a future vector primitive must be able to walk back.

    Source -> Page -> Derived View -> Scale -> Orientation/North -> Region.
    Assembled from the record rather than stored, so it can never disagree with
    the view it describes.
    """
    measurable, measure_reason = may_measure(view)
    north = north_reference(view)
    return {
        "source_id": view.get("source_id"),
        "page_structural_unit_id": view.get("page_structural_unit_id"),
        "derived_view_id": view.get("id"),
        "region": view.get("region"),
        "scale": {
            "state": view.get("scale_state"),
            "value": view.get("scale_value"),
            "notation": view.get("scale_notation"),
            "method": view.get("scale_method"),
            "confidence": view.get("scale_confidence"),
            "unit_system": view.get("unit_system"),
            "measurable": measurable,
            "reason": measure_reason,
        },
        "orientation": {
            "state": view.get("orientation_state"),
            "source_rotation_degrees": view.get("source_rotation_degrees"),
            "normalized_rotation_degrees": view.get("normalized_rotation_degrees"),
            "applied_rotation_degrees": _rotation(view),
        },
        "north": north,
        "north_corroboration_state": north_corroboration_state(view),
        "title_block": title_block_provenance(view),
        "derivation_reason": view.get("derivation_reason"),
        "derived_at": view.get("created_at"),
        "derived_by": view.get("created_by"),
    }
