"""
CLAUDE-DRAWING-CONDITIONS-01 - what a condition is, where it stops, and what
happens there.

WHY THIS EXISTS ALONGSIDE SYMBOL FAMILIES

Family recognition asks *what other things are like this?*. Boundary
recognition asks *where does this condition stop, meet or change?*. They are
different questions and they need each other: the family tells you a detail is
one of twelve like it, the boundary tells you that this one meets a different
material at its head. Answering only the first produces confident
generalisation about conditions nobody checked the edges of.

THE START OF A CONDITION IS OFTEN INVISIBLE. ITS BOUNDARIES ARE NOT.

That is the practical reason boundaries are the primary observation here. A
drawing rarely announces where an assembly begins, but it shows a hatch change,
a thickness change, a joint, a level change. Those are visible, and each is
evidence of TRANSITION - never, by itself, proof of meaning.

EVERY VERDICT IN THIS MODULE IS DERIVED AT READ TIME

Nothing here writes. Continuity, load path and threshold priority are computed
from the stored observations and human decisions each time they are asked for.
A boundary that could not be judged yesterday becomes judgeable the moment its
missing evidence arrives, with no reprocessing and nothing to unwrite - the
same read-time-derivation contract `resolve_relationship_status` and
`resolve_source_reference_status` already follow.

TWO INFERENCES THIS MODULE REFUSES TO MAKE

*Touching is not continuity.* Two lines meeting on a drawing say the draftsman
put them there; they say nothing about whether an air barrier carries through
the junction. `functional_layer_continuity` will report REVIEW_NEEDED for a
layer whose transfer is unstated no matter how cleanly the geometry meets.

*Touching is not support.* A load path requires a recorded, evidenced edge.
`structural_admission_state` will not promote spatial adjacency into
SUPPORTED_BY, because a lintel that is merely drawn near an opening is exactly
the condition an engineer needs to be asked about.

AND ONE IT REFUSES TO CLAIM

Adequacy. This module can say a load path is incomplete or unstated. It can
never say a member is sufficient - that is engineering judgement, it requires
analysis this system does not do, and GOV-P-006 already draws the line: a model
may constrain a governed transition, it may never authorize one.

FORM MAY BE CHOSEN. PHYSICS CANNOT BE NEGOTIATED.

`expression_class` keeps those apart so they are never argued in the same
voice. An unconventional geometry is not a defect and this module never reports
it as one; what it reports is the physical consequence the geometry creates,
which is a different sentence with a different addressee.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.case_workspace import (
    CONTINUITY_STATE_CONTINUOUS,
    CONTINUITY_STATE_INTERRUPTED,
    CONTINUITY_STATE_REVIEW_NEEDED,
    CONTINUITY_STATE_TRANSFERRED,
    CONTINUITY_STATE_UNKNOWN,
    DISCRETE_EDGE_BEHAVIORS,
    EDGE_BEHAVIOR_INTERRUPTED,
    EDGE_BEHAVIOR_UNKNOWN,
    EDGE_CLASS_CONTINUITY,
    EDGE_CLASS_DISCRETE,
    EDGE_CLASS_UNKNOWN,
    EXPRESSION_DESIGN_CHOICE,
    EXPRESSION_PERFORMANCE_CONSTRAINED,
    HOST_RELATIONSHIP_TYPES,
    STRUCTURAL_RELATIONSHIP_TYPES,
    STRUCTURAL_STATE_CONFLICT,
    STRUCTURAL_STATE_PATH_INCOMPLETE,
    STRUCTURAL_STATE_REVIEW_NEEDED,
    STRUCTURAL_STATE_SUPPORTED,
    SUPPORT_DEPENDENCY_DEPENDENT,
    THRESHOLD_KIND_CHANGE,
    THRESHOLD_KIND_INTERSECT,
    THRESHOLD_KIND_OVERLAP,
    THRESHOLD_KIND_PENETRATE,
    THRESHOLD_KIND_RESPONSIBILITY_CHANGE,
    THRESHOLD_KIND_TERMINATE,
    THRESHOLD_KIND_TRANSFER,
    THRESHOLD_KIND_TRANSITION,
)

logger = logging.getLogger(__name__)

#: How deep the island -> branch -> mainland walk may go before we conclude the
#: parent chain is circular. Real assemblies nest a handful of levels; a longer
#: chain is a data defect, and looping forever on it would hang a page render.
MAX_MEMBERSHIP_DEPTH = 32

#: Thresholds where a condition changes hands or changes physics. These are
#: where deeper reasoning is worth spending, because they are where
#: coordination questions and RFIs actually come from. Ordered most-costly
#: first, which is also most-valuable first.
THRESHOLD_PRIORITY_ORDER = (
    THRESHOLD_KIND_RESPONSIBILITY_CHANGE,
    THRESHOLD_KIND_TRANSFER,
    THRESHOLD_KIND_PENETRATE,
    THRESHOLD_KIND_TRANSITION,
    THRESHOLD_KIND_INTERSECT,
    THRESHOLD_KIND_TERMINATE,
    THRESHOLD_KIND_OVERLAP,
    THRESHOLD_KIND_CHANGE,
)

#: A decision that settles a row. DEFERRED is deliberately absent, for the same
#: reason it is absent from the legend's own settled set: deferring is choosing
#: to answer later, not answering.
SETTLED_STATUSES = ("confirmed", "overridden", "unknown", "informative")


class DrawingConditionError(Exception):
    """A condition query could not be answered."""


# ---------------------------------------------------------------------------
# Hierarchical membership: island -> branch -> mainland
# ---------------------------------------------------------------------------

def membership_chain(store, workspace, condition_id: str) -> list:
    """From this condition up to the largest assembly that claims it.

    Returned local-first, so `chain[0]` is the detail in front of you and
    `chain[-1]` is the system it belongs to. A cycle is reported rather than
    followed - a parent chain that loops is a data defect, and silently
    truncating it would hide the defect while still returning a plausible list.
    """
    chain, seen = [], set()
    current = store._find(workspace.drawing_conditions, condition_id)
    if current is None:
        raise DrawingConditionError("Condition %s was not found." % condition_id)
    while current is not None:
        if current["id"] in seen:
            raise DrawingConditionError(
                "Condition %s has a circular parent chain." % condition_id)
        seen.add(current["id"])
        chain.append(current)
        if len(chain) > MAX_MEMBERSHIP_DEPTH:
            raise DrawingConditionError(
                "Condition %s nests deeper than %d levels."
                % (condition_id, MAX_MEMBERSHIP_DEPTH))
        parent_id = current.get("parent_condition_id")
        current = (store._find(workspace.drawing_conditions, parent_id)
                   if parent_id else None)
    return chain


def system_of(store, workspace, condition_id: str) -> Optional[dict]:
    """The largest assembly this condition belongs to, or itself if it is one."""
    chain = membership_chain(store, workspace, condition_id)
    return chain[-1] if chain else None


def siblings_of(store, workspace, condition_id: str) -> list:
    """Other conditions under the same parent.

    This is the membership answer to "what else is like this?", and it is NOT
    the same as a symbol family: siblings share a PARENT, family members share a
    MEANING. A window head and a window sill are siblings and are not alike.
    """
    condition = store._find(workspace.drawing_conditions, condition_id)
    if condition is None:
        raise DrawingConditionError("Condition %s was not found." % condition_id)
    parent_id = condition.get("parent_condition_id")
    if not parent_id:
        return []
    return [row for row in workspace.drawing_conditions
            if row.get("parent_condition_id") == parent_id
            and row["id"] != condition_id]


def descendants_of(store, workspace, condition_id: str) -> list:
    """Everything beneath this condition, breadth-first, cycle-safe."""
    found, frontier, seen = [], [condition_id], {condition_id}
    depth = 0
    while frontier:
        depth += 1
        if depth > MAX_MEMBERSHIP_DEPTH:
            raise DrawingConditionError(
                "Condition %s nests deeper than %d levels."
                % (condition_id, MAX_MEMBERSHIP_DEPTH))
        children = [row for row in workspace.drawing_conditions
                    if row.get("parent_condition_id") in frontier
                    and row["id"] not in seen]
        for child in children:
            seen.add(child["id"])
        found.extend(children)
        frontier = [child["id"] for child in children]
    return found


# ---------------------------------------------------------------------------
# Thresholds and edges
# ---------------------------------------------------------------------------

def threshold_priority(boundary: dict) -> dict:
    """How much deeper reasoning this boundary is worth.

    The body establishes the family; the threshold tests the construction. Rank
    is by the most consequential threshold present, not by how many are - a
    single responsibility change matters more than three material changes.
    """
    kinds = boundary.get("threshold_kinds") or []
    ranked = [kind for kind in THRESHOLD_PRIORITY_ORDER if kind in kinds]
    unranked = [kind for kind in kinds if kind not in THRESHOLD_PRIORITY_ORDER]
    if not ranked and not unranked:
        return {"priority": "routine", "leading_threshold": None,
                "reason": "No threshold recorded on this boundary.",
                "thresholds": []}
    if ranked:
        leading = ranked[0]
        position = THRESHOLD_PRIORITY_ORDER.index(leading)
        priority = "high" if position <= 2 else (
            "elevated" if position <= 5 else "routine")
        reason = "%s is the most consequential threshold recorded here." % leading
    else:
        # An unrecognised threshold is preserved rather than discarded, and it
        # gets attention rather than being ranked below everything known.
        leading, priority = unranked[0], "elevated"
        reason = ("%s is not a recognised threshold kind and was preserved "
                  "verbatim." % leading)
    return {"priority": priority, "leading_threshold": leading,
            "reason": reason, "thresholds": ranked + unranked}


def edge_behavior_state(boundary: dict) -> dict:
    """Is the recorded behaviour coherent with the KIND of edge this is?

    A vapour barrier given "cut" is the failure this catches. Cut is a
    perfectly good answer for a hard material edge and a meaningless one for a
    continuity layer, where the real question is what happens to the FUNCTION.
    Reporting it as REVIEW_NEEDED rather than accepting it is the difference
    between a record that looks complete and one that is.
    """
    edge_class = boundary.get("edge_class") or EDGE_CLASS_UNKNOWN
    behavior = boundary.get("edge_behavior")
    if not behavior:
        return {"state": CONTINUITY_STATE_REVIEW_NEEDED,
                "edge_class": edge_class, "behavior": None,
                "reason": "No edge behaviour recorded."}
    if edge_class == EDGE_CLASS_UNKNOWN:
        return {"state": CONTINUITY_STATE_REVIEW_NEEDED,
                "edge_class": edge_class, "behavior": behavior,
                "reason": ("The kind of edge was never established, so the "
                           "behaviour cannot be read as either a material "
                           "termination or a continuity question.")}
    if edge_class == EDGE_CLASS_CONTINUITY and behavior in DISCRETE_EDGE_BEHAVIORS:
        return {"state": CONTINUITY_STATE_REVIEW_NEEDED,
                "edge_class": edge_class, "behavior": behavior,
                "reason": ("'%s' describes a hard material edge, but this is a "
                           "continuity layer - what happens to the FUNCTION is "
                           "unanswered." % behavior)}
    if edge_class == EDGE_CLASS_DISCRETE and behavior not in DISCRETE_EDGE_BEHAVIORS:
        return {"state": CONTINUITY_STATE_REVIEW_NEEDED,
                "edge_class": edge_class, "behavior": behavior,
                "reason": ("'%s' is a continuity behaviour recorded against a "
                           "discrete material edge." % behavior)}
    if behavior in (EDGE_BEHAVIOR_UNKNOWN, EDGE_BEHAVIOR_INTERRUPTED):
        return {"state": (CONTINUITY_STATE_UNKNOWN
                          if behavior == EDGE_BEHAVIOR_UNKNOWN
                          else CONTINUITY_STATE_INTERRUPTED),
                "edge_class": edge_class, "behavior": behavior,
                "reason": "Recorded as %s." % behavior}
    return {"state": CONTINUITY_STATE_CONTINUOUS if
            edge_class == EDGE_CLASS_CONTINUITY else "resolved",
            "edge_class": edge_class, "behavior": behavior,
            "reason": "%s is coherent with a %s." % (behavior, edge_class)}


# ---------------------------------------------------------------------------
# Functional layers - building science, honestly bounded
# ---------------------------------------------------------------------------

def functional_layer_continuity(boundary: dict) -> list:
    """For each functional layer at this boundary: does the function survive?

    The question is never "is a line drawn through" but "what happens to the
    function". A layer that stops with a stated transfer is TRANSFERRED and
    fine; a layer that stops with nothing said is REVIEW_NEEDED, however tidy
    the drawing looks. A drawn termination is not valid merely because it is
    drawn.

    This never proposes a repair. Naming the gap is within what evidence
    supports; designing the flashing is not.
    """
    results = []
    for layer in boundary.get("functional_layers") or []:
        function = layer.get("function")
        intended = layer.get("intended")
        continues = layer.get("continues")
        transfer = (layer.get("transfer_mechanism") or "").strip()
        evidence = (layer.get("evidence") or "").strip()

        if intended is False:
            state, reason = (CONTINUITY_STATE_UNKNOWN,
                             "This layer is not intended to perform here.")
        elif continues is True:
            if evidence:
                state, reason = (CONTINUITY_STATE_CONTINUOUS,
                                 "Continuity is stated and evidenced.")
            else:
                state, reason = (
                    CONTINUITY_STATE_REVIEW_NEEDED,
                    "Continuity is asserted with no evidence behind it.")
        elif continues is False and transfer:
            if evidence:
                state, reason = (
                    CONTINUITY_STATE_TRANSFERRED,
                    "The layer stops, and the function transfers by %s." % transfer)
            else:
                state, reason = (
                    CONTINUITY_STATE_REVIEW_NEEDED,
                    "A transfer by %s is claimed with no evidence behind it."
                    % transfer)
        elif continues is False:
            state, reason = (
                CONTINUITY_STATE_REVIEW_NEEDED,
                "The layer stops here and nothing says how the function "
                "continues.")
        else:
            state, reason = (
                CONTINUITY_STATE_REVIEW_NEEDED,
                "Whether this layer continues was never established.")
        results.append({
            "function": function,
            "state": state,
            "reason": reason,
            "transfer_mechanism": transfer or None,
            "evidence": evidence or None,
            # Naming the gap is in scope. Designing the fix is not.
            "repair_proposed": False,
        })
    return results


def performance_consequence(condition: dict, boundary: dict) -> dict:
    """What the chosen form COSTS physically - never whether it is good.

    An unconventional geometry is a design choice and this returns nothing
    critical about it. What it returns is whether that choice leaves a
    performance-constrained layer unanswered, which is a question for the
    designer rather than a judgement about their design.
    """
    unresolved = [row for row in functional_layer_continuity(boundary)
                  if row["state"] == CONTINUITY_STATE_REVIEW_NEEDED]
    expression = condition.get("expression_class")
    return {
        "expression_class": expression,
        "aesthetic_critique": None,   # never produced, by design
        "physical_consequences": [
            "%s is unresolved at this boundary: %s" % (row["function"], row["reason"])
            for row in unresolved
        ],
        "note": (
            "Form is the designer's to choose; these are the physical "
            "questions the chosen form raises, not objections to it."
            if expression == EXPRESSION_DESIGN_CHOICE else
            "This condition is performance-constrained: the questions below "
            "are not preferences."
            if expression == EXPRESSION_PERFORMANCE_CONSTRAINED else
            "Whether this is a design choice or performance-constrained was "
            "never established."),
    }


# ---------------------------------------------------------------------------
# Host / dependent, and structural admission
# ---------------------------------------------------------------------------

def _edges_of(store, workspace, condition_id: str, types) -> list:
    """Recorded edges of the given types where this condition is the FROM side."""
    edges = store.relationships_for(
        workspace, "drawing_condition", condition_id, direction="from")
    return [edge for edge in edges if edge.get("relationship_type") in types]


def host_support_state(store, workspace, condition_id: str) -> dict:
    """Does a dependent material actually have the host it needs?

    A dependent condition with no recorded host is REVIEW_NEEDED, not an
    assumption that one exists off-drawing. This is the cheapest genuinely
    useful building-science check there is: an adhered finish with no stated
    substrate is a real coordination question on real projects.
    """
    condition = store._find(workspace.drawing_conditions, condition_id)
    if condition is None:
        raise DrawingConditionError("Condition %s was not found." % condition_id)

    dependency = condition.get("support_dependency")
    edges = _edges_of(store, workspace, condition_id, HOST_RELATIONSHIP_TYPES)
    hosts = []
    for edge in edges:
        host = store._find(workspace.drawing_conditions, edge["to_id"])
        hosts.append({"relationship_type": edge["relationship_type"],
                      "host_condition_id": edge["to_id"],
                      "host_present": host is not None,
                      "host_meaning": (host or {}).get("proposed_meaning"),
                      "provisional": edge.get("provisional", True),
                      "confidence": edge.get("confidence")})

    if dependency is None:
        state, reason = (CONTINUITY_STATE_REVIEW_NEEDED,
                         "Whether this can stand on its own was never "
                         "established.")
    elif dependency != SUPPORT_DEPENDENCY_DEPENDENT:
        state, reason = ("self_supporting",
                         "Recorded as self-supporting; no host is required.")
    elif not hosts:
        state, reason = (CONTINUITY_STATE_REVIEW_NEEDED,
                         "A dependent material with no recorded host. What it "
                         "is fixed to is a real question, not an omission to "
                         "fill in.")
    elif not any(host["host_present"] for host in hosts):
        state, reason = (CONTINUITY_STATE_REVIEW_NEEDED,
                         "Every recorded host points at a condition that does "
                         "not exist here.")
    else:
        state, reason = ("hosted",
                         "Hosted by %d recorded condition(s)." % len(
                             [h for h in hosts if h["host_present"]]))
    return {"condition_id": condition_id, "support_dependency": dependency,
            "state": state, "reason": reason, "hosts": hosts}


def structural_admission_state(store, workspace, condition_id: str) -> dict:
    """Is there a credible, recorded path for the forces to reach the ground?

    Walks the load-bearing edges upward. Reports INCOMPLETE where the chain
    stops at something that is not itself supported, and CONFLICT where two
    recorded edges disagree about what carries the same element.

    It never reports adequacy. "There is a path" and "the path is sufficient"
    are different claims, and only the first is answerable from a drawing.
    """
    condition = store._find(workspace.drawing_conditions, condition_id)
    if condition is None:
        raise DrawingConditionError("Condition %s was not found." % condition_id)

    path, visited, current_id = [], set(), condition_id
    state, reason = STRUCTURAL_STATE_SUPPORTED, "A recorded load path exists."
    while True:
        if current_id in visited:
            state = STRUCTURAL_STATE_CONFLICT
            reason = "The recorded load path is circular."
            break
        visited.add(current_id)
        edges = _edges_of(store, workspace, current_id,
                          STRUCTURAL_RELATIONSHIP_TYPES)
        if not edges:
            current = store._find(workspace.drawing_conditions, current_id)
            if (current or {}).get("support_dependency") == \
                    SUPPORT_DEPENDENCY_DEPENDENT:
                state = STRUCTURAL_STATE_PATH_INCOMPLETE
                reason = ("The path stops at a dependent element with nothing "
                          "recorded carrying it.")
            elif current_id == condition_id:
                state = STRUCTURAL_STATE_REVIEW_NEEDED
                reason = ("No load-bearing edge is recorded at all. Spatial "
                          "adjacency is not a load path.")
            break

        targets = {edge["to_id"] for edge in edges}
        if len(targets) > 1:
            state = STRUCTURAL_STATE_CONFLICT
            reason = ("Two different elements are recorded as carrying the "
                      "same condition.")
            path.append({"from": current_id,
                         "candidates": sorted(targets)})
            break

        edge = edges[0]
        support = store._find(workspace.drawing_conditions, edge["to_id"])
        path.append({"from": current_id, "to": edge["to_id"],
                     "relationship_type": edge["relationship_type"],
                     "support_present": support is not None,
                     "provisional": edge.get("provisional", True)})
        if support is None:
            state = STRUCTURAL_STATE_PATH_INCOMPLETE
            reason = ("The path reaches %s, which is not a recorded condition."
                      % edge["to_id"])
            break
        current_id = edge["to_id"]

    return {
        "condition_id": condition_id,
        "state": state,
        "reason": reason,
        "path": path,
        # Said explicitly because the absence of this sentence is how a
        # "structurally supported" reading turns into a sufficiency claim.
        "adequacy_claimed": False,
        "adequacy_note": ("Path completeness only. Capacity, sizing and "
                          "adequacy require engineering analysis and remain "
                          "the engineer's."),
    }


def spatially_adjacent(region_a: dict, region_b: dict, tolerance: float = 1.0) -> bool:
    """Do these two regions touch?

    Provided so that the REFUSAL above can be stated as a fact rather than an
    absence: adjacency is computable, and it still does not produce a load path
    or a continuity verdict. Callers get the geometry; they do not get to call
    it support.
    """
    def box(region):
        x = float((region or {}).get("x") or 0)
        y = float((region or {}).get("y") or 0)
        return (x, y,
                x + float((region or {}).get("width") or 0),
                y + float((region or {}).get("height") or 0))

    ax0, ay0, ax1, ay1 = box(region_a)
    bx0, by0, bx1, by1 = box(region_b)
    return (ax0 - tolerance <= bx1 and bx0 - tolerance <= ax1
            and ay0 - tolerance <= by1 and by0 - tolerance <= ay1)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def boundary_report(store, workspace, condition_id: str) -> dict:
    """Everything derivable about one condition and its edges, in one read."""
    condition = store._find(workspace.drawing_conditions, condition_id)
    if condition is None:
        raise DrawingConditionError("Condition %s was not found." % condition_id)

    boundaries = store.condition_boundaries_for(workspace, condition_id=condition_id)
    rows = []
    for boundary in boundaries:
        layers = functional_layer_continuity(boundary)
        rows.append({
            "boundary_id": boundary["id"],
            "evidence": boundary.get("boundary_evidence"),
            "edge": edge_behavior_state(boundary),
            "threshold": threshold_priority(boundary),
            "functional_layers": layers,
            "unresolved_layers": len(
                [row for row in layers
                 if row["state"] == CONTINUITY_STATE_REVIEW_NEEDED]),
            "both_sides_recorded": bool(boundary.get("side_a")) and
                                   bool(boundary.get("side_b")),
            "consequences": performance_consequence(condition, boundary),
        })

    chain = membership_chain(store, workspace, condition_id)
    return {
        "condition_id": condition_id,
        "meaning": condition.get("proposed_meaning"),
        "status": condition.get("status"),
        "membership_chain": [row["proposed_meaning"] for row in chain],
        "system": chain[-1]["proposed_meaning"] if chain else None,
        "sibling_count": len(siblings_of(store, workspace, condition_id)),
        "boundaries": rows,
        "host": host_support_state(store, workspace, condition_id),
        "structure": structural_admission_state(store, workspace, condition_id),
        "boundaries_needing_review": len(
            [row for row in rows if row["unresolved_layers"]]),
        "deferred_work": [
            "Vector extraction is not attempted: the drawing grammar for this "
            "sheet is not confirmed.",
            "Quantitative geometry is not derived from any view that is not "
            "QUANTITATIVE.",
        ],
    }
