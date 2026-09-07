"""
CLAUDE-LEGEND-OF-UNDERSTANDING-01 - GO proposes, a human confirms, meaning becomes reusable.

WHY THIS COMES BEFORE DEEPER DRAWING WORK

The real E1 sheet proved the shape of the problem: OCR recovers the title block
at 0.75 legible tokens and the drawing body at far less, so no amount of further
machine effort reliably tells us what the marks on that sheet MEAN. A person
looking at a cropped image answers in seconds what a recogniser cannot answer at
all.

So the sequence is deliberately cheap-first:

    cheap perception  ->  compact human confirmation  ->  reusable understanding
                      ->  expensive interpretation, only where it now pays

`deferred_work` names what is being held back and why, so the saving is visible
rather than merely claimed.

THE SNAPSHOT IS NOT DECORATION

Every review row carries a real crop of the actual mark, and
`propose_legend_item` REFUSES an item without one. Asking someone to confirm
"section reference" as a detached label invites them to agree with a plausible
sentence; showing them the mark asks a question they can actually answer. It is
also the only way an UNKNOWN row is useful - an unreadable squiggle with its
picture attached is a real question, while the word "unknown" alone is not.

OBSERVATION IS NEVER OVERWRITTEN

Decisions append. `effective_meaning` derives the current reading from the newest
decision at read time, so GO's original proposal and every correction since stay
readable. A reviewer who changes their mind twice leaves three legible states.

PRECEDENCE: EXPLICIT PROJECT EVIDENCE BEATS A GENERIC GUESS, ALWAYS

`resolve_meaning` walks the tiers in order - an explicit sheet legend, then
human-confirmed project / discipline / source-set conventions, then generic
inference, then unresolved. A generic symbol recogniser can never override what
this project's own legend says, which is the failure mode that makes
symbol libraries dangerous on real drawing sets.

STYLE CONTEXT INFORMS CONFIDENCE, NEVER MEANING

Era, office and discipline are recorded and may raise or lower confidence. They
must never by themselves decide what a mark is: "1970s hand-drafted structural"
is evidence about how to read a sheet, not a licence to assert its contents.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from services.case_workspace import (
    FAMILY_REPRESENTATIVE_LIMIT,
    FAMILY_ROLE_INSTANCE,
    FAMILY_ROLE_REPRESENTATIVE,
    LEGEND_KIND_DETAIL_REFERENCE,
    LEGEND_KIND_ELEVATION_MARKER,
    LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_SCOPE_DISCIPLINE,
    LEGEND_SCOPE_INSTANCE,
    LEGEND_SCOPE_PAGE,
    LEGEND_SCOPE_PROJECT,
    LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED,
    LEGEND_STATUS_DEFERRED,
    LEGEND_STATUS_INFORMATIVE,
    LEGEND_STATUS_OVERRIDDEN,
    LEGEND_STATUS_PROPOSED,
    LEGEND_STATUS_REVIEW_NEEDED,
    LEGEND_STATUS_UNKNOWN,
)

logger = logging.getLogger(__name__)

SNAPSHOT_DIR_NAME = "legend_snapshots"
#: Crops are small and shown at review size; 200dpi keeps a symbol legible
#: without storing a megabyte per row.
SNAPSHOT_DPI = 200

#: A decision that settles the row for review purposes. DEFERRED deliberately
#: does not - deferring is choosing to answer later, not answering.
SETTLED_STATUSES = (
    LEGEND_STATUS_CONFIRMED, LEGEND_STATUS_OVERRIDDEN,
    LEGEND_STATUS_UNKNOWN, LEGEND_STATUS_INFORMATIVE,
)


class LegendError(Exception):
    """A legend operation could not be performed."""


def snapshot_region(raw_bytes: bytes, page_index: int, rect, destination_dir: str,
                    item_key: str, *, dpi: int = SNAPSHOT_DPI, rotate: int = 0) -> Optional[str]:
    """Crop the actual mark to a PNG and return its path. Never raises.

    Stored as a plain asset rather than registered as a derivative Source: a
    sheet can carry dozens of marks, and turning each into a Source would bury
    the real documents under review artefacts.
    """
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - pymupdf is pinned
        return None
    try:
        os.makedirs(destination_dir, exist_ok=True)
        document = pymupdf.open(stream=raw_bytes, filetype="pdf")
        try:
            page = document.load_page(page_index)
            matrix = pymupdf.Matrix(dpi / 72.0, dpi / 72.0)
            if rotate:
                matrix = matrix * pymupdf.Matrix(rotate)
            pixmap = page.get_pixmap(matrix=matrix, clip=pymupdf.Rect(*rect))
            path = os.path.join(destination_dir, "%s.png" % item_key)
            pixmap.save(path)
            return path
        finally:
            document.close()
    except Exception as exc:  # noqa: BLE001 - a missing crop is a result
        logger.warning("Legend snapshot failed for %s: %s", item_key, exc)
        return None


def effective_meaning(item: dict) -> dict:
    """The current reading, derived from the newest decision at read time.

    Never stored, so GO's proposal and every human correction remain readable
    forever. An overridden item reports the human's meaning while still carrying
    what GO originally said.
    """
    decisions = item.get("decisions") or []
    latest = decisions[-1] if decisions else None
    if latest and latest.get("action") == LEGEND_STATUS_OVERRIDDEN:
        meaning, authority = latest.get("meaning"), "human_override"
    elif latest and latest.get("action") == LEGEND_STATUS_CONFIRMED:
        meaning, authority = item.get("proposed_meaning"), "human_confirmed"
    elif latest and latest.get("action") in (LEGEND_STATUS_UNKNOWN,
                                             LEGEND_STATUS_INFORMATIVE):
        meaning, authority = None, "human_" + latest["action"]
    else:
        meaning, authority = item.get("proposed_meaning"), "machine_proposal"
    return {
        "meaning": meaning,
        "authority": authority,
        "status": item.get("status", LEGEND_STATUS_PROPOSED),
        "proposed_meaning": item.get("proposed_meaning"),
        "proposed_kind": item.get("proposed_kind"),
        "scope_kind": item.get("scope_kind", LEGEND_SCOPE_INSTANCE),
        "scope_id": item.get("scope_id"),
        "decided_by": (latest or {}).get("actor"),
        "decided_at": (latest or {}).get("at"),
        "history_length": len(decisions),
    }


def _scope_matches(item: dict, *, page_id: Optional[str], source_id: Optional[str],
                   discipline: Optional[str]) -> bool:
    """Does this item's confirmed scope reach the place being asked about?"""
    scope = item.get("scope_kind", LEGEND_SCOPE_INSTANCE)
    if scope == LEGEND_SCOPE_INSTANCE:
        return False           # applies only to its own mark, never reused
    if scope == LEGEND_SCOPE_PAGE:
        return bool(page_id) and item.get("page_structural_unit_id") == page_id
    if scope == LEGEND_SCOPE_SOURCE:
        return bool(source_id) and item.get("source_id") == source_id
    if scope == LEGEND_SCOPE_DISCIPLINE:
        return bool(discipline) and (
            (item.get("style_context") or {}).get("discipline") == discipline)
    if scope == LEGEND_SCOPE_PROJECT:
        return True
    return False


def resolve_meaning(store, workspace, observed_text: Optional[str] = None, *,
                    proposed_kind: Optional[str] = None,
                    page_id: Optional[str] = None,
                    source_id: Optional[str] = None,
                    discipline: Optional[str] = None) -> dict:
    """What does this mark mean HERE, applying evidence in precedence order.

    An explicit legend on the sheet outranks everything; a generic inference
    outranks nothing. That ordering is the guard against a symbol library
    quietly overruling what a project's own legend says.
    """
    key = (observed_text or "").strip().upper()
    candidates = [
        item for item in workspace.legend_items
        if item.get("status") in (LEGEND_STATUS_CONFIRMED, LEGEND_STATUS_OVERRIDDEN)
        and _scope_matches(item, page_id=page_id, source_id=source_id,
                           discipline=discipline)
        and ((key and (item.get("observed_text") or "").strip().upper() == key)
             or (proposed_kind and item.get("proposed_kind") == proposed_kind))
    ]

    def tier_rank(item):
        order = {"explicit_legend": 0, "confirmed_project": 1,
                 "confirmed_discipline": 2, "confirmed_source_set": 3,
                 "generic_inference": 4}
        scope_rank = {LEGEND_SCOPE_PAGE: 0, LEGEND_SCOPE_SOURCE: 1,
                      LEGEND_SCOPE_DISCIPLINE: 2, LEGEND_SCOPE_PROJECT: 3}
        return (order.get(item.get("evidence_tier"), 4),
                scope_rank.get(item.get("scope_kind"), 4))

    if not candidates:
        return {"resolved": False, "tier": "unresolved", "meaning": None,
                "reason": ("Nothing confirmed at any scope reaching here explains "
                           "this mark.")}
    best = sorted(candidates, key=tier_rank)[0]
    resolved = effective_meaning(best)
    return {
        "resolved": True,
        "tier": best.get("evidence_tier"),
        "meaning": resolved["meaning"],
        "authority": resolved["authority"],
        "scope_kind": best.get("scope_kind"),
        "legend_item_id": best["id"],
        "reason": None,
    }


def inherit_group_understanding(store, workspace, group_id: str, target_source_id: str,
                                target_page_id: str, actor: str,
                                snapshot_path_for=None) -> list:
    """Carry a confirmed group understanding onto another sheet in the family.

    So a reviewer is not asked the same question on every sheet of a set. The
    inherited item records `inherited_from_item_id`, so a reader can always tell
    one sheet's own evidence from a family assumption - which matters when a
    page later contradicts the group.
    """
    settled = [
        item for item in workspace.legend_items
        if item.get("group_id") == group_id
        and item.get("status") in (LEGEND_STATUS_CONFIRMED, LEGEND_STATUS_OVERRIDDEN)
        and item.get("source_id") != target_source_id
    ]
    created = []
    for parent in settled:
        meaning = effective_meaning(parent)
        snapshot = (snapshot_path_for(parent) if snapshot_path_for
                    else parent.get("snapshot_path"))
        item = store.propose_legend_item(
            workspace,
            source_id=target_source_id,
            page_structural_unit_id=target_page_id,
            region=dict(parent.get("region") or {}),
            proposed_kind=parent.get("proposed_kind"),
            proposed_meaning=meaning["meaning"] or parent.get("proposed_meaning"),
            interpretation_method="inherited_group_understanding",
            actor=actor,
            snapshot_path=snapshot,
            observed_text=parent.get("observed_text"),
            confidence=parent.get("confidence"),
            legend_evidence="group %s" % group_id,
            evidence_tier=parent.get("evidence_tier", "confirmed_source_set"),
            style_context=dict(parent.get("style_context") or {}),
            group_id=group_id,
            inherited_from_item_id=parent["id"],
        )
        created.append(item)
    return created


def contradicts_group(item: dict, observed_text: Optional[str],
                      proposed_kind: Optional[str]) -> bool:
    """Does this page disagree with what the group assumed?"""
    if not item.get("inherited_from_item_id"):
        return False
    if observed_text and (item.get("observed_text") or "") and \
            observed_text.strip().upper() != item["observed_text"].strip().upper():
        return True
    return bool(proposed_kind) and proposed_kind != item.get("proposed_kind")


def review_rows(store, workspace, *, source_id: Optional[str] = None,
                page_structural_unit_id: Optional[str] = None) -> list:
    """The compact review table: snapshot, proposal, confidence, decision.

    Deliberately flat and small. This is a confirmation surface, not a
    configuration screen - a reviewer should be able to clear a sheet quickly.
    """
    items = store.legend_items_for(
        workspace, source_id=source_id, page_structural_unit_id=page_structural_unit_id)
    rows = []
    for item in items:
        # A mark belonging to a family is represented by its family row, not
        # its own - representatives included, since the family row is where its
        # crop is shown. The exception is a row that came back for review: that
        # is a real question for a human, and collapsing it would lose it.
        if item.get("family_id") and                 item.get("status") != LEGEND_STATUS_REVIEW_NEEDED:
            continue
        resolved = effective_meaning(item)
        rows.append({
            "legend_item_id": item["id"],
            "snapshot_path": item.get("snapshot_path"),
            "has_snapshot": bool(item.get("snapshot_path")),
            "observed_text": item.get("observed_text"),
            "proposed_kind": item.get("proposed_kind"),
            "proposed_meaning": item.get("proposed_meaning"),
            "effective_meaning": resolved["meaning"],
            "authority": resolved["authority"],
            "confidence": item.get("confidence"),
            "status": item.get("status"),
            "scope_kind": item.get("scope_kind"),
            "evidence_tier": item.get("evidence_tier"),
            "inherited": bool(item.get("inherited_from_item_id")),
            "family_id": item.get("family_id"),
            "family_role": item.get("family_role"),
            "history_length": resolved["history_length"],
            "region": item.get("region"),
            "source_id": item.get("source_id"),
            "page_structural_unit_id": item.get("page_structural_unit_id"),
        })
    return rows


def understanding_report(store, workspace, source_id: str,
                         page_structural_unit_id: Optional[str] = None) -> dict:
    """The compact intro report - a table, not an essay.

    Says what GO believes, what it cannot yet do, and WHY the expensive work is
    being held back. `deferred_work` is the honest half: the saving from
    confirming first is only real if the deferral is visible.
    """
    source = next((s for s in workspace.sources if s["id"] == source_id), None)
    if source is None:
        raise LegendError("Source %s was not found." % source_id)

    items = store.legend_items_for(
        workspace, source_id=source_id, page_structural_unit_id=page_structural_unit_id)
    views = store.derived_views_for(workspace, source_id=source_id)
    pages = [u for u in workspace.structural_units if u["source_id"] == source_id]

    awaiting = [i for i in items if i.get("status") not in SETTLED_STATUSES]
    inherited = [i for i in items if i.get("inherited_from_item_id")]
    unknown = [i for i in items if i.get("status") == LEGEND_STATUS_UNKNOWN]
    contested = [i for i in items if i.get("status") == LEGEND_STATUS_REVIEW_NEEDED]
    style = {}
    for item in items:
        style.update(item.get("style_context") or {})

    deferred = []
    if awaiting:
        deferred.append(
            "Targeted OCR and symbol parsing are held until %d proposal(s) are "
            "confirmed - reading marks whose meaning is unsettled would have to "
            "be redone." % len(awaiting))
    if not views:
        deferred.append(
            "View segmentation is held: no derived view has been established on "
            "this sheet yet.")
    deferred.append(
        "Vectorisation is not attempted at all until the drawing grammar is "
        "confirmed.")

    return {
        "source_id": source_id,
        "source_name": source.get("name"),
        "title_block": {
            "document_id": source.get("document_id"),
            "revision": source.get("revision"),
            "issuer": source.get("issuer"),
        },
        "pages": len(pages),
        "view_count": len(views),
        "scale_states": sorted({v.get("scale_state") for v in views}) if views else [],
        "orientation_states": sorted({v.get("north_state") for v in views}) if views else [],
        "style_context": style,
        "proposed_items": len(items),
        "awaiting_confirmation": len(awaiting),
        "inherited_from_group": len(inherited),
        "unknown_items": len(unknown),
        "review_needed": len(contested),
        "rows_without_snapshot": len([i for i in items if not i.get("snapshot_path")]),
        "safe_next_steps": (
            ["Confirm or correct the proposed readings."] if awaiting
            else ["Targeted segmentation and OCR of confirmed regions."]),
        "deferred_work": deferred,
    }


# ---------------------------------------------------------------------------
# CLAUDE-SECTION-CUT-FAMILY-01 - few human confirmations, many governed instances
#
# E1 carries the same section-cut symbol many times. One review row per
# occurrence is the wrong shape twice over: it asks a person the same question
# repeatedly, and it stores a half-megabyte crop for each repetition of an
# answer already given.
#
# So visually equivalent marks are clustered into a FAMILY, a person confirms
# the family once from a small representative set, and the meaning applies to
# the members within the scope they chose.
#
# WHAT IS SHARED AND WHAT IS NOT
#
# The family shares MEANING - "this shape is a section reference". It shares
# nothing else. Direction, mirror state, rotation, nearby label and candidate
# target stay on each instance, because on a section cut the direction decides
# WHICH view is referenced: normalising it away would leave every instance
# agreeing about the symbol while silently pointing at the wrong drawing.
#
# WHAT COUNTS AS A MATERIAL DIFFERENCE - a correction worth stating
#
# The obvious rule is wrong. A differing candidate target is NOT material: two
# section cuts pointing at different views are exactly what a family of section
# cuts looks like, and treating that as a difference would flag every member
# and defeat the whole mechanism. What is material is a difference that makes
# the FAMILY'S MEANING wrong for that instance - a different symbol kind, a
# different label grammar, a size well outside the family, or a
# direction-dependent family meeting an instance whose direction was never
# recorded. That last one is an honest "cannot apply", not a forced membership.
#
# NO PARALLEL DECISION MODEL
#
# Applying a family meaning goes through `decide_legend_item`, and a
# non-conforming instance goes through `flag_legend_item_review` - the same
# append-only transitions a single row uses. The family layer proposes and
# derives; it never invents an authority of its own, which is GOV-P-006 read at
# this scale.
# ---------------------------------------------------------------------------

#: Two marks are the same size for clustering purposes within this relative
#: tolerance. Hand-placed symbols and rasterisation both wobble; a section
#: bubble drawn twice is rarely the same number of pixels.
FAMILY_SIZE_TOLERANCE = 0.25

#: Kinds whose meaning depends on which way the mark points. For these, an
#: instance with no recorded direction cannot inherit the family's meaning.
DIRECTION_DEPENDENT_KINDS = (
    LEGEND_KIND_SECTION_REFERENCE, LEGEND_KIND_DETAIL_REFERENCE,
    LEGEND_KIND_ELEVATION_MARKER,
)


def _label_shape(text: Optional[str]) -> str:
    """The GRAMMAR of a label, not its value.

    "A/E2" and "B/E2" are the same kind of mark and must cluster together, so
    letters collapse to L and digits to D while separators survive verbatim.
    This is how two callouts to different views stay one family.
    """
    shape = []
    for character in (text or "").strip().upper():
        if character.isalpha():
            shape.append("L")
        elif character.isdigit():
            shape.append("D")
        elif character.isspace():
            continue
        else:
            shape.append(character)
    # Collapse runs so "E12" and "E2" agree: the count of digits is not grammar.
    collapsed = []
    for token in shape:
        if not collapsed or collapsed[-1] != token:
            collapsed.append(token)
    return "".join(collapsed)


def _size_bucket(region: Optional[dict]) -> tuple:
    """A coarse size key. Rounded so near-identical marks land together."""
    region = region or {}
    width = float(region.get("width") or 0)
    height = float(region.get("height") or 0)
    if width <= 0 or height <= 0:
        return (0, 0)
    step = 1.0 + FAMILY_SIZE_TOLERANCE
    def bucket(value):
        power = 0
        while value >= step:
            value /= step
            power += 1
        return power
    return (bucket(width), bucket(height))


def family_signature(candidate: dict) -> tuple:
    """What makes two marks visually equivalent FOR CLUSTERING.

    Deliberately excludes rotation, mirror state, direction and target. Those
    are the per-instance facts the family is not claiming to determine, and
    including them would produce one family per occurrence - the outcome this
    whole mechanism exists to avoid.
    """
    return (
        candidate.get("proposed_kind"),
        _label_shape(candidate.get("observed_text") or candidate.get("nearby_label")),
        _size_bucket(candidate.get("region")),
    )


def cluster_candidates(candidates: list) -> list:
    """Group observed marks into families. Deterministic, order-preserving.

    Returns one dict per family with its signature, its members in the order
    observed, and the representatives a human will actually be shown.
    """
    families = {}
    order = []
    for candidate in candidates:
        signature = family_signature(candidate)
        if signature not in families:
            families[signature] = []
            order.append(signature)
        families[signature].append(candidate)
    clustered = []
    for index, signature in enumerate(order):
        members = families[signature]
        representatives = select_representatives(members)
        chosen = {id(member) for member in representatives}
        clustered.append({
            "family_key": "family-%d" % (index + 1),
            "signature": signature,
            "proposed_kind": signature[0],
            "label_shape": signature[1],
            "members": members,
            "member_count": len(members),
            "representatives": representatives,
            # Positional so the choice survives serialisation - object identity
            # would not, and a family that forgets which crops a human saw is
            # a family nobody can audit.
            "representative_indexes": [
                position for position, member in enumerate(members)
                if id(member) in chosen
            ],
        })
    return clustered


def select_representatives(members: list, limit: int = FAMILY_REPRESENTATIVE_LIMIT) -> list:
    """The few marks a human is actually shown.

    Spread rather than the first N: the widest variance in direction is the most
    informative set to look at, because a reviewer seeing only identical crops
    cannot tell whether the family really is uniform.
    """
    if len(members) <= limit:
        return list(members)

    # A mark whose direction was never read is a poor exemplar of a
    # direction-dependent family: its crop would define the family while itself
    # being the case the family cannot answer. So fully-observed members are
    # preferred, and an under-observed one is only shown if there is nothing
    # else - which then surfaces as a REVIEW_NEEDED member rather than as the
    # thing the human was asked to generalise from.
    observed = [m for m in members
                if m.get("section_line_direction_degrees") is not None]
    pool = observed if len(observed) >= limit else members
    ordered = sorted(
        pool,
        key=lambda m: (
            m.get("section_line_direction_degrees") is None,
            m.get("section_line_direction_degrees") or 0.0,
        ),
    )
    if limit == 1:
        return [ordered[0]]
    step = (len(ordered) - 1) / float(limit - 1)
    picked, seen = [], set()
    for slot in range(limit):
        index = int(round(slot * step))
        if index not in seen:
            seen.add(index)
            picked.append(ordered[index])
    return picked


def instance_differs_materially(instance: dict, reference: dict) -> list:
    """Reasons this instance cannot carry the family's confirmed meaning.

    An empty list means the family meaning applies. Every reason returned is a
    reason to send the row back to a human, never a reason to guess.
    """
    reasons = []
    if instance.get("proposed_kind") != reference.get("proposed_kind"):
        reasons.append(
            "kind differs: %s vs the family's %s"
            % (instance.get("proposed_kind"), reference.get("proposed_kind")))

    instance_shape = _label_shape(
        instance.get("observed_text") or instance.get("nearby_label"))
    reference_shape = _label_shape(
        reference.get("observed_text") or reference.get("nearby_label"))
    if instance_shape != reference_shape:
        reasons.append(
            "label grammar differs: %r vs the family's %r"
            % (instance_shape, reference_shape))

    if _size_bucket(instance.get("region")) != _size_bucket(reference.get("region")):
        reasons.append("size falls outside the family's range")

    kind = reference.get("proposed_kind")
    if kind in DIRECTION_DEPENDENT_KINDS:
        # The family says what the symbol MEANS; the instance must still say
        # which way it points, or the meaning cannot be applied honestly.
        if instance.get("section_line_direction_degrees") is None and \
                instance.get("view_direction_degrees") is None:
            reasons.append(
                "direction was never recorded, and %s meaning depends on it" % kind)
    return reasons


def family_meaning(store, workspace, family_id: str) -> dict:
    """What the family means, derived at read time from its representatives.

    Never stored. If the representatives were decided differently, the family is
    CONTESTED and applies to nothing - two people disagreeing about the same
    symbol is exactly the state that must not be silently averaged.
    """
    representatives = store.legend_items_for(
        workspace, family_id=family_id, family_role=FAMILY_ROLE_REPRESENTATIVE)
    instances = store.legend_items_for(
        workspace, family_id=family_id, family_role=FAMILY_ROLE_INSTANCE)
    if not representatives:
        return {"family_id": family_id, "state": "unknown_family",
                "meaning": None, "representative_count": 0,
                "instance_count": len(instances)}

    resolved = [effective_meaning(item) for item in representatives]
    settled = [r for r in resolved if r["status"] in SETTLED_STATUSES]
    if not settled:
        state, meaning = "awaiting_confirmation", None
    elif len(settled) != len(resolved):
        state, meaning = "partially_confirmed", None
    else:
        meanings = {(r["meaning"] or "").strip().upper() for r in settled}
        if len(meanings) > 1:
            state, meaning = "contested", None
        else:
            state = "confirmed"
            meaning = settled[0]["meaning"]
    scopes = {r["scope_kind"] for r in resolved}
    return {
        "family_id": family_id,
        "state": state,
        "meaning": meaning,
        "proposed_kind": representatives[0].get("proposed_kind"),
        "scope_kind": scopes.pop() if len(scopes) == 1 else None,
        "scope_id": representatives[0].get("scope_id"),
        "representative_count": len(representatives),
        "instance_count": len(instances),
        "confirmations_asked_of_human": len(representatives),
        "governed_instances": len(instances),
    }


def apply_family_decision(store, workspace, family_id: str, actor: str, *,
                          governance_log=None) -> dict:
    """Carry one confirmed family meaning to its instances.

    Refuses unless the family is genuinely confirmed. Instances that differ
    materially are flagged for review rather than forced into membership - the
    brief is explicit that a non-conforming mark goes back to a human, and an
    almost-right meaning applied silently is worse than no meaning at all.
    """
    summary = family_meaning(store, workspace, family_id)
    if summary["state"] != "confirmed":
        raise LegendError(
            "Family %s is %s - only a confirmed family may be applied."
            % (family_id, summary["state"]))

    representatives = store.legend_items_for(
        workspace, family_id=family_id, family_role=FAMILY_ROLE_REPRESENTATIVE)
    reference = representatives[0]
    applied, flagged = [], []
    for instance in store.legend_items_for(
            workspace, family_id=family_id, family_role=FAMILY_ROLE_INSTANCE):
        if instance.get("status") in SETTLED_STATUSES:
            continue          # a human already answered this one; never overwrite
        if instance.get("status") == LEGEND_STATUS_REVIEW_NEEDED:
            continue          # already sent back to a human; re-flagging adds noise
        reasons = instance_differs_materially(instance, reference)
        if reasons:
            store.flag_legend_item_review(
                workspace, instance["id"],
                reason="Does not match family %s: %s" % (family_id, "; ".join(reasons)),
                actor=actor)
            flagged.append({"legend_item_id": instance["id"], "reasons": reasons})
            continue
        settled = effective_meaning(reference)
        store.decide_legend_item(
            workspace, instance["id"],
            action=(LEGEND_STATUS_OVERRIDDEN
                    if settled["authority"] == "human_override"
                    else LEGEND_STATUS_CONFIRMED),
            actor=actor,
            meaning=(summary["meaning"]
                     if settled["authority"] == "human_override" else None),
            scope_kind=summary["scope_kind"] or LEGEND_SCOPE_INSTANCE,
            scope_id=summary["scope_id"],
            note="Applied from confirmed symbol family %s." % family_id,
            governance_log=governance_log)
        applied.append(instance["id"])
    return {
        "family_id": family_id,
        "meaning": summary["meaning"],
        "applied": applied,
        "flagged_for_review": flagged,
        "human_confirmations": summary["representative_count"],
        "governed_instances": len(applied),
    }


def family_review_rows(store, workspace, *, source_id: Optional[str] = None) -> list:
    """The collapsed review surface: one row per family, not per occurrence.

    A row carries the representative crops a human judges and states how many
    instances ride on the answer, so the reviewer can see what their one
    decision is actually deciding.
    """
    items = store.legend_items_for(workspace, source_id=source_id)
    families, order = {}, []
    for item in items:
        family_id = item.get("family_id")
        if not family_id:
            continue
        if family_id not in families:
            families[family_id] = {"representatives": [], "instances": []}
            order.append(family_id)
        bucket = ("representatives"
                  if item.get("family_role") == FAMILY_ROLE_REPRESENTATIVE
                  else "instances")
        families[family_id][bucket].append(item)

    rows = []
    for family_id in order:
        bucket = families[family_id]
        summary = family_meaning(store, workspace, family_id)
        representatives = bucket["representatives"]
        rows.append({
            "family_id": family_id,
            "state": summary["state"],
            "proposed_kind": summary.get("proposed_kind"),
            "proposed_meaning": (representatives[0].get("proposed_meaning")
                                 if representatives else None),
            "effective_meaning": summary["meaning"],
            "confidence": (representatives[0].get("confidence")
                           if representatives else None),
            "evidence_tier": (representatives[0].get("evidence_tier")
                              if representatives else None),
            "source_id": (representatives[0].get("source_id")
                          if representatives else source_id),
            "representatives": [
                {"legend_item_id": r["id"],
                 "has_snapshot": bool(r.get("snapshot_path")),
                 "observed_text": r.get("observed_text"),
                 "status": r.get("status")}
                for r in representatives
            ],
            "instance_count": len(bucket["instances"]),
            "instances_needing_review": len(
                [i for i in bucket["instances"]
                 if i.get("status") == LEGEND_STATUS_REVIEW_NEEDED]),
            "decisions_saved": max(len(bucket["instances"]), 0),
        })
    return rows


def register_family(store, workspace, family: dict, *, source_id: str,
                    page_structural_unit_id: str, actor: str,
                    proposed_meaning: str, interpretation_method: str,
                    snapshot_for=None, confidence: Optional[float] = None,
                    evidence_tier: str = "generic_inference",
                    legend_evidence: Optional[str] = None,
                    style_context: Optional[dict] = None,
                    governance_log=None) -> dict:
    """Turn one cluster into governed rows: a few representatives, many instances.

    Only the representatives are cropped. That is the whole economy of this
    mechanism - `snapshot_for` is called for them and not for the rest, so a
    sheet with twenty identical section cuts stores three images instead of
    twenty and asks one question instead of twenty.

    Per-instance variance travels with each member untouched. The family decides
    what the symbol MEANS; it never decides where a particular one points.
    """
    members = family.get("members") or []
    # Positions are the source of truth, not the `representatives` list: object
    # identity does not survive storage, and a family that cannot say which
    # crops a human saw is a family nobody can audit.
    indexes = family.get("representative_indexes")
    if indexes is None:
        chosen = {id(member) for member in (family.get("representatives") or [])}
        indexes = [position for position, member in enumerate(members)
                   if id(member) in chosen]
    representative_positions = {position for position in indexes
                                if 0 <= position < len(members)}
    if not representative_positions:
        raise LegendError("A family needs at least one representative to review.")

    family_id = family.get("family_id") or _new_family_id()
    created = {"family_id": family_id, "representatives": [], "instances": []}

    for position, member in enumerate(members):
        is_representative = position in representative_positions
        snapshot_path = None
        if is_representative and snapshot_for is not None:
            snapshot_path = snapshot_for(member)
        if is_representative and not snapshot_path:
            raise LegendError(
                "A family representative without a crop cannot be reviewed - it "
                "is the image the human is being asked to judge.")
        item = store.propose_legend_item(
            workspace,
            source_id=source_id,
            page_structural_unit_id=page_structural_unit_id,
            region=member.get("region") or {},
            proposed_kind=family.get("proposed_kind") or member.get("proposed_kind"),
            proposed_meaning=proposed_meaning,
            interpretation_method=interpretation_method,
            actor=actor,
            snapshot_path=snapshot_path,
            observed_text=member.get("observed_text"),
            derived_view_id=member.get("derived_view_id"),
            confidence=confidence,
            legend_evidence=legend_evidence,
            evidence_tier=evidence_tier,
            style_context=style_context,
            family_id=family_id,
            family_role=(FAMILY_ROLE_REPRESENTATIVE if is_representative
                         else FAMILY_ROLE_INSTANCE),
            instance_rotation_degrees=member.get("instance_rotation_degrees"),
            instance_mirrored=member.get("instance_mirrored"),
            section_line_direction_degrees=member.get("section_line_direction_degrees"),
            view_direction_degrees=member.get("view_direction_degrees"),
            nearby_label=member.get("nearby_label"),
            candidate_target_reference=member.get("candidate_target_reference"),
            governance_log=governance_log,
        )
        created["representatives" if is_representative else "instances"].append(item)

    created["snapshots_taken"] = len(created["representatives"])
    created["snapshots_avoided"] = len(created["instances"])
    return created


def _new_family_id() -> str:
    from services.case_workspace import _new_id
    return _new_id()


def confirm_family(store, workspace, family_id: str, action: str, actor: str, *,
                   meaning: Optional[str] = None,
                   scope_kind: str = LEGEND_SCOPE_SOURCE,
                   scope_id: Optional[str] = None,
                   note: Optional[str] = None,
                   governance_log=None) -> dict:
    """One human answer for the whole family, then carry it to the instances.

    This is the entire point of the mechanism expressed as a single call: the
    reviewer answers once, every representative records that same answer through
    the ordinary append-only transition, and the members inherit it - except any
    that differ materially, which go back to a human instead.

    The default scope is SOURCE rather than PROJECT. A convention confirmed on
    one sheet is evidence about that sheet; promoting it across a project is a
    decision a person makes deliberately, not a default they get silently.
    """
    representatives = store.legend_items_for(
        workspace, family_id=family_id, family_role=FAMILY_ROLE_REPRESENTATIVE)
    if not representatives:
        raise LegendError("Family %s has no representative to decide." % family_id)

    decided = []
    for representative in representatives:
        store.decide_legend_item(
            workspace, representative["id"], action=action, actor=actor,
            meaning=meaning, scope_kind=scope_kind, scope_id=scope_id,
            note=note or "Decided as symbol family %s." % family_id,
            governance_log=governance_log)
        decided.append(representative["id"])

    result = {
        "family_id": family_id,
        "action": action,
        "representatives_decided": decided,
        "applied": [],
        "flagged_for_review": [],
    }
    # UNKNOWN, INFORMATIVE and DEFERRED settle the representatives without
    # establishing a meaning, so there is nothing to carry to the members.
    if action in (LEGEND_STATUS_CONFIRMED, LEGEND_STATUS_OVERRIDDEN):
        carried = apply_family_decision(
            store, workspace, family_id, actor, governance_log=governance_log)
        result.update({
            "meaning": carried["meaning"],
            "applied": carried["applied"],
            "flagged_for_review": carried["flagged_for_review"],
            "human_confirmations": carried["human_confirmations"],
            "governed_instances": carried["governed_instances"],
        })
    return result
