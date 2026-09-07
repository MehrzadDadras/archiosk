"""
CLAUDE-VIEW-REFERENCE-01 - a callout is a POINTER, never the thing it points at.

THE DISTINCTION THIS EXISTS TO ENFORCE

A section line drawn on a plan is not a section. It is a mark saying "the section
is drawn elsewhere". If ARCHIOSK turns that mark into a Section view, the project
acquires a section that does not exist, with no geometry behind it, and every
later reader inherits the fiction.

So there are two kinds of thing on a sheet and they are never interchangeable:

  PHYSICAL VIEW   geometry that actually exists on THIS page - a plan, a
                  section, a detail that is genuinely drawn here.
  VIEW REFERENCE  a symbol pointing at a view located somewhere else - a section
                  head, a detail bubble, an elevation reference, a match line, a
                  continuation note.

`classify_marker` is a total function over the reference kinds and returns
VIEW_REFERENCE for every one of them. There is deliberately no code path that
turns a reference into a DerivedView.

BUILT ENTIRELY ON PRIMITIVES THAT ALREADY EXIST

Nothing here is a second cross-reference system, because a first one already
exists. `CLAUDE-DRAWING-REFS-01` added REFERENCE_TYPE_SHEET /
_DETAIL_CALLOUT / _SCHEDULE_MARK / _GRID_INTERSECTION to `SourceReference`,
whose own note says they are "new PATTERNS and new TARGETS for the existing
SourceReference machinery, not a second resolver", and that RESOLUTION_STATUS_*
"already carries every outcome a drawing linker needs". It does:

    RESOLVED    -> RESOLUTION_STATUS_RESOLVED_EXACT
    UNRESOLVED  -> RESOLUTION_STATUS_TARGET_NOT_FOUND
    AMBIGUOUS   -> RESOLUTION_STATUS_AMBIGUOUS
    CONFLICTED  -> RESOLUTION_STATUS_RESOLVED_MULTIPLE

RESOLUTION IS DERIVED AT READ TIME, WHICH IS WHY A LATE TARGET JUST WORKS

`resolve_source_reference_status` already establishes the pattern: the stored
record is the EXTRACTION-TIME FACT, and resolution is re-derived against whatever
the project currently contains. This module follows it exactly. A reference to a
sheet nobody has uploaded is UNRESOLVED today and RESOLVED the moment the sheet
arrives - with no mutation, no reprocessing, and its original creation history
untouched, because nothing was ever written down as "resolved" in the first
place.

HUMAN CONFIRMATION REUSES THE RELATIONSHIP SUBSTRATE

A person confirming a target records a `Relationship` with `provisional=False`
and `confirmed_by` set - the same governed edge A2 already reads. The extracted
evidence is never erased or overwritten: the confirmation sits beside it and the
resolver simply prefers it.

WHAT THIS DOES NOT DO

It does not detect callouts in an image. It reads TEXT that some other layer
recovered, using the parser that already exists. No symbol recognition, no
vectorisation. When the section line is eventually vectorised it will be a line
primitive whose SEMANTIC meaning is still "reference to another view" - the
geometry and the meaning are different facts about the same mark.
"""
from __future__ import annotations

import logging
from typing import Optional

from services.case_workspace import (
    OBJECT_KIND_DERIVED_VIEW,
    OBJECT_KIND_SOURCE,
    REFERENCE_TYPE_DETAIL_CALLOUT,
    REFERENCE_TYPE_SHEET,
    RELATIONSHIP_TYPE_REFERENCES,
    RESOLUTION_STATUS_AMBIGUOUS,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_RESOLVED_MULTIPLE,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
)

logger = logging.getLogger(__name__)

#: The two kinds of mark. Never interchangeable.
MARKER_PHYSICAL_VIEW = "physical_view"
MARKER_VIEW_REFERENCE = "view_reference"

VIEW_REFERENCE_SECTION = "section_callout"
VIEW_REFERENCE_DETAIL = "detail_callout"
VIEW_REFERENCE_ELEVATION = "elevation_reference"
VIEW_REFERENCE_MATCH_LINE = "match_line"
VIEW_REFERENCE_CONTINUATION = "continuation_reference"

KNOWN_VIEW_REFERENCE_KINDS = (
    VIEW_REFERENCE_SECTION, VIEW_REFERENCE_DETAIL, VIEW_REFERENCE_ELEVATION,
    VIEW_REFERENCE_MATCH_LINE, VIEW_REFERENCE_CONTINUATION,
)

#: Recorded when the target SHEET is known but which view on it is not. Not a
#: failure - a real, useful, partial answer, and better than inventing a view
#: boundary nobody has established.
TARGET_VIEW_UNRESOLVED = "target_view_unresolved"


def classify_marker(kind: str) -> str:
    """Is this mark a view, or a pointer to one?

    Total over KNOWN_VIEW_REFERENCE_KINDS and there is no path by which a
    reference kind returns PHYSICAL_VIEW. That asymmetry is the point: the
    expensive mistake is promoting a callout into a view, never the reverse.
    """
    return (MARKER_VIEW_REFERENCE if kind in KNOWN_VIEW_REFERENCE_KINDS
            else MARKER_PHYSICAL_VIEW)


def is_view_reference(kind: str) -> bool:
    return classify_marker(kind) == MARKER_VIEW_REFERENCE


def register_view_reference(store, workspace, source_id: str, text: str, *,
                            reference_kind: str, parent_derived_view_id: Optional[str] = None,
                            region: Optional[dict] = None,
                            direction_degrees: Optional[float] = None,
                            page_structural_unit_id: Optional[str] = None,
                            actor: str = "system", extractor_version: Optional[str] = None,
                            governance_log=None) -> list:
    """Persist the callout TEXT as governed SourceReference(s).

    `known_targets` is deliberately NOT passed: resolution belongs at read time
    (see `resolve_view_reference`), so what is stored is only what was actually
    found on the sheet. That is what lets a target uploaded next week resolve a
    reference recorded today without rewriting it.

    The view-reference specifics ride in `origin_context`, which the primitive
    documents as "where the reference was found" - the parent view, the region,
    and the viewing direction are exactly that.
    """
    if not is_view_reference(reference_kind):
        raise ValueError(
            "%r is not a view-reference kind. A physical view is registered as a "
            "DerivedView, never as a reference." % reference_kind)

    origin_context = {
        "marker_class": MARKER_VIEW_REFERENCE,
        "view_reference_kind": reference_kind,
        "parent_derived_view_id": parent_derived_view_id,
        "page_structural_unit_id": page_structural_unit_id,
        "region": dict(region or {}),
        # The direction a section is VIEWED. Deliberately its own field and
        # never merged with north or with view rotation - a section arrow says
        # which way you are looking, not where north is.
        "direction_degrees": direction_degrees,
    }
    return store.extract_and_register_source_references(
        workspace, source_id=source_id, text=text, origin_context=origin_context,
        include_drawing_tokens=True, actor=actor,
        extractor_version=extractor_version, governance_log=governance_log,
    )


def _sheet_identity(source: dict, views: list) -> set:
    """Every identifier by which this sheet might legitimately be cited."""
    identity = set()
    for value in (source.get("document_id"), source.get("name")):
        if value:
            identity.add(str(value).strip().upper().replace(".PDF", ""))
    for view in views:
        label = (view.get("inherited_title_block") or {}).get("sheet_label")
        if label:
            identity.add(str(label).strip().upper())
            identity.add(str(label).split()[0].strip().upper())
    return {value for value in identity if value}


def eligible_targets(store, workspace, exclude_source_id: Optional[str] = None) -> list:
    """Sources this project may legitimately resolve a reference against.

    Same project only, removed sources excluded, and the citing sheet itself
    excluded - a sheet does not cross-reference itself.
    """
    return [
        source for source in workspace.sources
        if not source.get("removed_at") and source["id"] != exclude_source_id
    ]


def _normalise(token: Optional[str]) -> str:
    return "".join((token or "").upper().split()).replace("-", "").replace(".PDF", "")


def resolve_view_reference(store, workspace, reference_id: str) -> dict:
    """Resolve ONE view reference against the project as it stands NOW.

    Derived, never stored. A confirmed human Relationship wins over any
    extracted match; otherwise the sheet identifier is matched against eligible
    sources, and - only when the target sheet is unambiguous - against that
    sheet's DerivedViews for the specific target view.

    Refuses to guess in both directions: no candidate is TARGET_NOT_FOUND,
    several candidates is AMBIGUOUS, and neither is quietly resolved by
    recency, filename or being the only other file in the project.
    """
    reference = next((r for r in workspace.source_references if r["id"] == reference_id), None)
    if reference is None:
        return {"status": RESOLUTION_STATUS_TARGET_NOT_FOUND,
                "reason": "No such reference.", "reference_id": reference_id}

    context = reference.get("origin_context") or {}
    base = {
        "reference_id": reference_id,
        "reference_text": reference.get("reference_text"),
        "reference_type": reference.get("reference_type"),
        "view_reference_kind": context.get("view_reference_kind"),
        "marker_class": context.get("marker_class", MARKER_VIEW_REFERENCE),
        "direction_degrees": context.get("direction_degrees"),
        "parent_derived_view_id": context.get("parent_derived_view_id"),
    }

    # 1. A human confirmation outranks anything derived from text.
    confirmed = [
        rel for rel in workspace.relationships
        if rel.get("from_id") == reference_id
        and rel.get("relationship_type") == RELATIONSHIP_TYPE_REFERENCES
        and not rel.get("provisional", True)
        and not rel.get("validation_state")
    ]
    if confirmed:
        edge = confirmed[0]
        base.update({
            "status": RESOLUTION_STATUS_RESOLVED_EXACT,
            "resolution_method": "human_confirmation",
            "target_type": edge.get("to_type"),
            "target_ids": [edge.get("to_id")],
            "confirmed_by": edge.get("confirmed_by") or edge.get("created_by"),
            "reason": None,
        })
        return base

    # 2. Otherwise match the cited sheet identifier against eligible sources.
    cited = _normalise(reference.get("reference_text"))
    candidates = []
    for source in eligible_targets(store, workspace, reference.get("source_id")):
        views = store.derived_views_for(workspace, source_id=source["id"])
        identities = {_normalise(value) for value in _sheet_identity(source, views)}
        if any(identity and identity in cited for identity in identities):
            candidates.append((source, views))

    if not candidates:
        base.update({
            "status": RESOLUTION_STATUS_TARGET_NOT_FOUND,
            "resolution_method": "sheet_identifier_match",
            "target_type": None, "target_ids": [],
            "reason": ("No registered sheet in this project matches the cited "
                       "identifier. The reference stands as recorded; if the sheet "
                       "is uploaded later this resolves with no reprocessing."),
        })
        return base

    if len(candidates) > 1:
        base.update({
            "status": RESOLUTION_STATUS_AMBIGUOUS,
            "resolution_method": "sheet_identifier_match",
            "target_type": OBJECT_KIND_SOURCE,
            "target_ids": [source["id"] for source, _views in candidates],
            "reason": ("More than one registered sheet matches this citation. "
                       "Choosing by filename or recency would be a guess; a human "
                       "confirms the governing target."),
        })
        return base

    source, views = candidates[0]
    detail = _detail_token(reference)
    matching_views = [
        view for view in views
        if detail and detail in _normalise(view.get("derivation_reason"))
    ] if detail else []

    if len(matching_views) == 1:
        base.update({
            "status": RESOLUTION_STATUS_RESOLVED_EXACT,
            "resolution_method": "sheet_and_view_match",
            "target_type": OBJECT_KIND_DERIVED_VIEW,
            "target_ids": [matching_views[0]["id"]],
            "target_source_id": source["id"], "reason": None,
        })
        return base
    if len(matching_views) > 1:
        base.update({
            "status": RESOLUTION_STATUS_RESOLVED_MULTIPLE,
            "resolution_method": "sheet_and_view_match",
            "target_type": OBJECT_KIND_DERIVED_VIEW,
            "target_ids": [view["id"] for view in matching_views],
            "target_source_id": source["id"],
            "reason": "Several views on the target sheet match this callout.",
        })
        return base

    base.update({
        "status": RESOLUTION_STATUS_RESOLVED_EXACT,
        "resolution_method": "sheet_identifier_match",
        "target_type": OBJECT_KIND_SOURCE,
        "target_ids": [source["id"]],
        "target_source_id": source["id"],
        "target_view_state": TARGET_VIEW_UNRESOLVED,
        "reason": ("The target sheet is identified. Which view on it is not - that "
                   "sheet has no segmented view matching this callout, and "
                   "inventing a view boundary would be worse than saying so."),
    })
    return base


def _detail_token(reference: dict) -> Optional[str]:
    """The detail/section number from a callout like 3/A-501, if present."""
    text = (reference.get("reference_text") or "").strip()
    if "/" in text:
        head = text.split("/")[0].strip().upper()
        head = head.replace("DETAIL", "").replace("DET.", "").replace("DET", "").strip()
        return head or None
    return None


def confirm_target(store, workspace, reference_id: str, target_type: str,
                   target_id: str, actor: str, reason: Optional[str] = None) -> dict:
    """A human names the governing target. Extracted evidence is untouched.

    Recorded as a CONFIRMED Relationship rather than by editing the reference,
    so the original citation and its extraction-time status remain exactly as
    found, and the confirmation is itself a governed, attributable edge.
    """
    reference = next((r for r in workspace.source_references if r["id"] == reference_id), None)
    if reference is None:
        raise ValueError("No such reference: %s" % reference_id)
    edge = store.record_relationship(
        workspace,
        from_type="source_reference", from_id=reference_id,
        to_type=target_type, to_id=target_id,
        relationship_type=RELATIONSHIP_TYPE_REFERENCES,
        created_by=actor, provisional=False,
        reason=reason or "Human-confirmed view-reference target.",
    )
    return edge


def references_from_view(store, workspace, derived_view_id: str) -> list:
    """Every view reference recorded as sitting on this view."""
    return [
        r for r in workspace.source_references
        if (r.get("origin_context") or {}).get("parent_derived_view_id") == derived_view_id
    ]
