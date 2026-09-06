"""
A2 - the governed dependency graph. "What depends on this?"

WHAT THIS IS, AND WHAT IT DELIBERATELY IS NOT

It is a QUERY layer. It is not a store, not a second graph, and not a new
relationship vocabulary. `services/case_workspace.py` already carries the whole
substrate: a typed `Relationship` with `from_type`/`from_id`/`to_type`/`to_id`,
a closed-but-open-world type vocabulary that already includes `depends_on`,
`blocks`, `affects`, `implements` and `derived_from`, per-edge provenance
(`created_by`, `created_at`, `provisional`, `confidence`, `confirmed_by`,
`related_analysis_id`, `related_finding_id`, `reason`, `validation_state`), and
`resolve_relationship_status`, which already derives
rejected/disputed/superseded/broken/stale/proposed/confirmed with a stated
precedence. That edge record's own docstring says it exists to serve "dependency
edges ... one mechanism serving both, rather than two separate graph systems."

Building a parallel dependency store would have contradicted that directly. What
was actually missing is the reading: nothing anywhere asked "what depends on X",
nothing classified the relationship vocabulary into dependency-bearing versus
supporting versus contradicting, and nothing traversed more than one hop safely.
That is the entire scope here.

THE THREE THINGS THAT MUST NOT COLLAPSE

1. **Dependency is not support and is not contradiction.** The vocabulary
   already distinguishes them and this module keeps them distinct rather than
   flattening everything into "related". A `contradicts` edge is not a weaker
   `depends_on`; it is a different claim about the world, and a carry-through
   sweep that treated it as a dependency would propagate an argument as if it
   were a requirement.

2. **Explicit is not inferred.** This is an ORTHOGONAL axis to type, carried by
   `provisional`. A machine-proposed edge is returned, labelled, and never
   silently promoted - `GOV-P-006`: a model may constrain a governed transition,
   it may never authorize one. `include_inferred=False` filters them out
   entirely for callers that need only adjudicated truth.

3. **Supersession is not a relationship type.** It never was here, deliberately:
   `Supersession` is its own primitive carrying governed lineage that an
   ordinary edge does not attempt to guarantee. This module never invents a
   supersession edge, and it never drops an edge for being stale or broken -
   erasing a superseded endpoint's edge would erase the lineage that makes the
   change reconstructable, which is the opposite of what carry-through needs.

DIRECTION IS PART OF THE SEMANTICS

"What depends on X" is not one query over one edge set, because the vocabulary
points two ways and reading it one way would silently invert half the graph:

  * `A depends_on B` - A is the dependent, B the dependency. Dependents of B are
    found on the FROM side of edges whose TO is B.
  * `A blocks B` / `A affects B` - B is the one whose state is contingent on A.
    Dependents of A are found on the TO side of edges whose FROM is A.

Both are dependency-bearing; they simply travel in opposite directions, and
`_DIRECTION` below records which is which per type rather than leaving it to
each caller to remember.

DRAWING COMPATIBILITY IS STRUCTURAL, NOT PROMISED

Nothing here is textual. Endpoints are `(object_type, object_id)` pairs over the
shared object-kind vocabulary, and `addressable_region` (a region on a drawing
sheet) and `structural_unit` already resolve as endpoints with supersession-
derived staleness through the same resolver every other kind uses. A drawing
dependent therefore participates in this graph today, with no re-architecture
owed to B3-B - which is the Product Owner's own condition on A2. B3-B still has
to decide WHICH drawing relationships to create and how to sweep them; it does
not have to change this model to do it.

BOUNDED BY CONSTRUCTION

Traversal is depth-limited, node-capped and cycle-safe. An unbounded recursive
expansion over a real project's relationship set is how a "show me everything
connected" feature becomes a request that never returns, and the cap is
therefore a default rather than an option a caller must remember.
"""
from __future__ import annotations

from typing import Optional

from services.case_workspace import (
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_STRUCTURAL_UNIT,
    RELATIONSHIP_TYPE_AFFECTS,
    RELATIONSHIP_TYPE_ASSOCIATED_WITH,
    RELATIONSHIP_TYPE_BASED_ON,
    RELATIONSHIP_TYPE_BLOCKS,
    RELATIONSHIP_TYPE_CALCULATED_FROM,
    RELATIONSHIP_TYPE_COMPARES_WITH,
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_CORRESPONDS_TO,
    RELATIONSHIP_TYPE_DEPENDS_ON,
    RELATIONSHIP_TYPE_DEPICTS,
    RELATIONSHIP_TYPE_DERIVED_FROM,
    RELATIONSHIP_TYPE_DEVIATES_FROM,
    RELATIONSHIP_TYPE_IMPLEMENTS,
    RELATIONSHIP_TYPE_INVALIDATES,
    RELATIONSHIP_TYPE_OBSERVES,
    RELATIONSHIP_TYPE_QUALIFIES,
    RELATIONSHIP_TYPE_REFERENCES,
    RELATIONSHIP_TYPE_REQUIRES_FOLLOW_UP,
    RELATIONSHIP_TYPE_RESULTED_IN,
    RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
    RELATIONSHIP_TYPE_SUMMARIZES,
    RELATIONSHIP_TYPE_SUPPORTS,
    RELATIONSHIP_TYPE_VALIDATES,
    RELATIONSHIP_STATUS_REJECTED,
    normalize_open_world_value,
    KNOWN_OBJECT_KINDS,
)

# -- Relationship classes ---------------------------------------------------
# What KIND of claim an edge makes. Orthogonal to explicit/inferred below.
CLASS_DEPENDENCY = "dependency"
CLASS_SUPPORTING = "supporting"
CLASS_CONTRADICTION = "contradiction"
CLASS_OTHER = "other"

# -- Direction, for dependency-bearing types only ---------------------------
#: `A <type> B` means A is the dependent and B the dependency.
DIRECTION_FORWARD = "forward"
#: `A <type> B` means B is the dependent and A the dependency.
DIRECTION_REVERSE = "reverse"

_DIRECTION = {
    RELATIONSHIP_TYPE_DEPENDS_ON: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_IMPLEMENTS: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_DERIVED_FROM: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_BASED_ON: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_CALCULATED_FROM: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_REFERENCES: DIRECTION_FORWARD,
    # Cross-modal carry-through hooks. A region that DEPICTS a requirement is
    # carrying that requirement onto a sheet, so the depiction is the dependent
    # - which is exactly the edge B3-B will sweep.
    RELATIONSHIP_TYPE_DEPICTS: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_CORRESPONDS_TO: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_REQUIRES_FOLLOW_UP: DIRECTION_FORWARD,
    RELATIONSHIP_TYPE_RESULTED_IN: DIRECTION_FORWARD,
    # The two that travel the other way.
    RELATIONSHIP_TYPE_BLOCKS: DIRECTION_REVERSE,
    RELATIONSHIP_TYPE_AFFECTS: DIRECTION_REVERSE,
}

DEPENDENCY_TYPES = tuple(_DIRECTION.keys())

SUPPORTING_TYPES = (
    RELATIONSHIP_TYPE_SUPPORTS,
    RELATIONSHIP_TYPE_VALIDATES,
    RELATIONSHIP_TYPE_OBSERVES,
    RELATIONSHIP_TYPE_SUMMARIZES,
    RELATIONSHIP_TYPE_QUALIFIES,
    RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
    RELATIONSHIP_TYPE_COMPARES_WITH,
    RELATIONSHIP_TYPE_ASSOCIATED_WITH,
)

CONTRADICTION_TYPES = (
    RELATIONSHIP_TYPE_CONTRADICTS,
    RELATIONSHIP_TYPE_INVALIDATES,
    RELATIONSHIP_TYPE_DEVIATES_FROM,
)

#: Endpoint kinds that are spatial. Named so B3-B has a hook and so the
#: drawing-compatibility claim is testable rather than asserted in prose.
SPATIAL_ENDPOINT_KINDS = (
    OBJECT_KIND_ADDRESSABLE_REGION,
    OBJECT_KIND_STRUCTURAL_UNIT,
)

DEFAULT_MAX_DEPTH = 1
DEFAULT_MAX_NODES = 200


def classify(relationship_type: str) -> str:
    """Which kind of claim this edge makes. Unknown types are OTHER, never
    silently treated as a dependency - an unrecognised edge must not become a
    carry-through obligation by default."""
    relationship_type = normalize_open_world_value(relationship_type, ())
    if relationship_type in DEPENDENCY_TYPES:
        return CLASS_DEPENDENCY
    if relationship_type in SUPPORTING_TYPES:
        return CLASS_SUPPORTING
    if relationship_type in CONTRADICTION_TYPES:
        return CLASS_CONTRADICTION
    return CLASS_OTHER


def is_inferred(relationship: dict) -> bool:
    """Machine-asserted until something adjudicates it. Mirrors the field's own
    default rather than assuming a value is present."""
    return bool(relationship.get("provisional", True))


def _endpoint(relationship: dict, side: str) -> tuple:
    return (relationship["%s_type" % side], relationship["%s_id" % side])


def _edge_view(store, workspace, relationship: dict, role: str) -> dict:
    """One edge, with its governed status and full provenance attached.

    Provenance is copied out explicitly rather than by returning the raw record,
    so that a caller reading this cannot mistake a proposed edge for an
    adjudicated one merely because both are dicts.
    """
    status = store.resolve_relationship_status(workspace, relationship["id"])
    return {
        "relationship_id": relationship["id"],
        "relationship_type": relationship["relationship_type"],
        "relationship_class": classify(relationship["relationship_type"]),
        "direction": _DIRECTION.get(relationship["relationship_type"]),
        "role": role,                      # "dependent" or "dependency"
        "from": {"type": relationship["from_type"], "id": relationship["from_id"]},
        "to": {"type": relationship["to_type"], "id": relationship["to_id"]},
        # -- provenance / authority, never stripped ------------------------
        "inferred": is_inferred(relationship),
        "confidence": relationship.get("confidence"),
        "created_by": relationship.get("created_by"),
        "created_at": relationship.get("created_at"),
        "confirmed_by": relationship.get("confirmed_by"),
        "reason": relationship.get("reason"),
        "validation_state": relationship.get("validation_state"),
        "related_analysis_id": relationship.get("related_analysis_id"),
        "related_finding_id": relationship.get("related_finding_id"),
        # -- derived at read time, never stored ----------------------------
        "status": status.get("status"),
        "endpoint_status": {"from": status.get("from"), "to": status.get("to")},
    }


def _neighbours(store, workspace, object_type: str, object_id: str,
                want_dependents: bool, include_inferred: bool) -> list[dict]:
    """One hop. `want_dependents=True` answers "what depends on this"."""
    object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
    out = []
    for relationship in store.relationships_for(workspace, object_type, object_id, direction="both"):
        rel_type = relationship["relationship_type"]
        if classify(rel_type) != CLASS_DEPENDENCY:
            continue
        if not include_inferred and is_inferred(relationship):
            continue

        direction = _DIRECTION.get(rel_type)
        this_is_from = _endpoint(relationship, "from") == (object_type, object_id)

        # Which side of this edge is the DEPENDENT one?
        if direction == DIRECTION_FORWARD:
            dependent_side, dependency_side = "from", "to"
        else:
            dependent_side, dependency_side = "to", "from"

        this_side = "from" if this_is_from else "to"
        if want_dependents:
            # We want the things that depend on the queried object, so the
            # queried object must be the DEPENDENCY side of this edge.
            if this_side != dependency_side:
                continue
            other = _endpoint(relationship, dependent_side)
            role = "dependent"
        else:
            if this_side != dependent_side:
                continue
            other = _endpoint(relationship, dependency_side)
            role = "dependency"

        view = _edge_view(store, workspace, relationship, role)
        view["other"] = {"type": other[0], "id": other[1]}
        out.append(view)
    return out


def _traverse(store, workspace, object_type: str, object_id: str, *,
              want_dependents: bool, max_depth: int, max_nodes: int,
              include_inferred: bool) -> dict:
    origin = (normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS), object_id)
    visited = {origin}
    frontier = [origin]
    edges: list[dict] = []
    truncated = False

    for depth in range(1, max(0, max_depth) + 1):
        next_frontier = []
        for node_type, node_id in frontier:
            for view in _neighbours(store, workspace, node_type, node_id,
                                    want_dependents, include_inferred):
                view["depth"] = depth
                edges.append(view)
                other = (view["other"]["type"], view["other"]["id"])
                if other in visited:
                    continue          # cycle-safe: never revisit a node
                if len(visited) >= max_nodes:
                    truncated = True
                    continue
                # A human REJECTION stops traversal THROUGH the edge. The edge
                # is still reported - suppressing it would hide the judgment -
                # but a rejected relationship must not carry a dependency
                # onward as though it had been accepted.
                if view["status"] == RELATIONSHIP_STATUS_REJECTED:
                    continue
                visited.add(other)
                next_frontier.append(other)
        frontier = next_frontier
        if not frontier:
            break

    nodes = [{"type": t, "id": i} for (t, i) in visited if (t, i) != origin]
    return {
        "origin": {"type": origin[0], "id": origin[1]},
        "question": "what depends on this" if want_dependents else "what does this depend on",
        "edges": edges,
        "nodes": nodes,
        "max_depth": max_depth,
        "truncated": truncated,
        "include_inferred": include_inferred,
        "counts": {
            "total": len(edges),
            "explicit": sum(1 for e in edges if not e["inferred"]),
            "inferred": sum(1 for e in edges if e["inferred"]),
        },
    }


def dependents_of(store, workspace, object_type: str, object_id: str, *,
                  max_depth: int = DEFAULT_MAX_DEPTH,
                  max_nodes: int = DEFAULT_MAX_NODES,
                  include_inferred: bool = True) -> dict:
    """WHAT DEPENDS ON THIS? - the question A2 exists to answer.

    Returns every dependency-bearing edge for which the queried object is the
    DEPENDENCY, with each edge's provenance and read-time governed status
    attached. Inferred edges are included and labelled by default; pass
    `include_inferred=False` for adjudicated edges only.
    """
    return _traverse(store, workspace, object_type, object_id,
                     want_dependents=True, max_depth=max_depth,
                     max_nodes=max_nodes, include_inferred=include_inferred)


def dependencies_of(store, workspace, object_type: str, object_id: str, *,
                    max_depth: int = DEFAULT_MAX_DEPTH,
                    max_nodes: int = DEFAULT_MAX_NODES,
                    include_inferred: bool = True) -> dict:
    """WHAT DOES THIS DEPEND ON? - the mirror, same rules."""
    return _traverse(store, workspace, object_type, object_id,
                     want_dependents=False, max_depth=max_depth,
                     max_nodes=max_nodes, include_inferred=include_inferred)


def related_non_dependencies(store, workspace, object_type: str, object_id: str) -> dict:
    """Supporting and contradicting edges, kept OUT of the dependency answer
    and reported separately.

    They are returned rather than discarded because a contradiction touching an
    object is exactly what a reviewer needs to see next to its dependents - and
    because silently dropping them is how a "no contradictions" impression gets
    manufactured from a query that never looked.
    """
    object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
    supporting, contradicting = [], []
    for relationship in store.relationships_for(workspace, object_type, object_id, direction="both"):
        kind = classify(relationship["relationship_type"])
        if kind == CLASS_SUPPORTING:
            supporting.append(_edge_view(store, workspace, relationship, "supporting"))
        elif kind == CLASS_CONTRADICTION:
            contradicting.append(_edge_view(store, workspace, relationship, "contradiction"))
    return {"supporting": supporting, "contradicting": contradicting}


def supersession_lineage(store, workspace, object_type: str, object_id: str) -> list[dict]:
    """The governed lineage for this object, from the Supersession primitive.

    Deliberately a SEPARATE call rather than a relationship class. Supersession
    was never modelled as an edge here, and folding it into the dependency
    answer would blur a governed lineage record into an ordinary assertion.
    """
    object_type = normalize_open_world_value(object_type, KNOWN_OBJECT_KINDS)
    return list(store.supersessions_for(workspace, object_type, object_id))
