"""CLAUDE-VISUAL-COMPOSER-01: governed As-Read decision cards for Composer.

Composer is GO's communication hub. As-Read is the system of record. This
module is the seam between them, and its whole job is to keep that asymmetry
true: it READS governed As-Read records to build a card, and it never writes
one. Every mutation still goes through the existing As-Read decision routes and
primitives, so there is exactly one copy of any answer.

WHAT THE MODEL MAY SUPPLY, AND WHY THAT IS SAFE

A model may pass `question`, `interpretation` and `exception_summary` - three
strings that are displayed and trusted for nothing else. It cannot pass a
target, a scope or a verb, because this module does not accept them: the
target is an argument the CALLER already holds as a real governed id, and the
verbs come from the application's own closed vocabulary.

That is the difference between "the model writes the question" and "the model
decides what gets changed". The first is useful; the second is the failure
this contract exists to prevent, and prose has no path to it.

DISPOSITION IS NEVER STORED ON THE CARD

`current_disposition` is derived at read time from the governed record. A card
rendered a week after the decision shows the decision, and a card whose target
was later corrected on the As-Read page shows the correction. There is no
Composer-side copy of the answer to drift.
"""
from __future__ import annotations

from typing import Optional

from services.case_workspace import (
    DECISION_CARD_TARGET_FAMILY, DECISION_CARD_TARGET_ITEM, DECISION_CARD_VERBS,
    LEGEND_SCOPE_INSTANCE, LEGEND_SCOPE_SOURCE, LEGEND_STATUS_REVIEW_NEEDED,
    VISUAL_AUTHORITY_AS_READ_SNAPSHOT, CaseWorkspaceError,
)
from services.legend_of_understanding import family_meaning

# How many crops a card shows. The lower bound is the point of the exercise -
# a reviewer judging a repeated mark needs to see that it repeats - and the
# upper bound is the minute-scale rule: past six, the reader is auditing rather
# than recognising.
MIN_CROPS = 3
MAX_CROPS = 6


class DecisionCardError(Exception):
    """A card could not be built from governed records."""


def _reference(item: dict) -> dict:
    """One governed snapshot, named by its record. No path, no bytes, no URL."""
    return {
        "authority": VISUAL_AUTHORITY_AS_READ_SNAPSHOT,
        "legend_item_id": item["id"],
        "source_id": item.get("source_id"),
        "page_structural_unit_id": item.get("page_structural_unit_id"),
        "family_id": item.get("family_id"),
        "region": item.get("region"),
        "observed_text": item.get("observed_text"),
    }


def build_family_card(store, workspace, family_id: str, *,
                      question: Optional[str] = None,
                      interpretation: Optional[str] = None,
                      exception_summary: Optional[str] = None) -> dict:
    """A card for one symbol family, built from what As-Read already holds.

    Raises rather than inventing: a family with no representative has no crop
    a human could judge, and a card without evidence is the "agree with a
    plausible sentence" failure `propose_legend_item` already refuses.
    """
    items = store.legend_items_for(workspace, family_id=family_id)
    if not items:
        raise DecisionCardError("No governed records for family %s." % family_id)

    representatives = [i for i in items if i.get("family_role") == "representative"]
    with_crops = [i for i in representatives if i.get("snapshot_path")]
    if not with_crops:
        raise DecisionCardError(
            "Family %s has no representative snapshot. A decision card must "
            "show the mark, not a description of it." % family_id)

    summary = family_meaning(store, workspace, family_id)
    instances = [i for i in items if i.get("family_role") != "representative"]
    held = [i for i in instances if i.get("status") == LEGEND_STATUS_REVIEW_NEEDED]
    source_id = with_crops[0].get("source_id")

    card = {
        "target_kind": DECISION_CARD_TARGET_FAMILY,
        "target_id": family_id,
        "source_id": source_id,
        "scope_kind": summary.get("scope_kind") or LEGEND_SCOPE_SOURCE,
        "verbs": list(DECISION_CARD_VERBS),
        "question": question,
        "interpretation": interpretation,
        "exception_summary": exception_summary,
    }
    return {
        "decision_card": card,
        "visual_references": [_reference(i) for i in with_crops[:MAX_CROPS]],
        # Application-computed, for the caller's own default wording. Never a
        # substitute for the governed read below.
        "governed": {
            "member_count": len(items),
            "instance_count": len(instances),
            "held_count": len(held),
            "state": summary.get("state"),
            "meaning": summary.get("meaning"),
            "proposed_kind": (with_crops[0].get("proposed_kind")),
        },
    }


def build_item_card(store, workspace, legend_item_id: str, *,
                    question: Optional[str] = None,
                    interpretation: Optional[str] = None,
                    exception_summary: Optional[str] = None) -> dict:
    """A card for one individually-held mark."""
    item = next((i for i in store.legend_items_for(workspace)
                 if i["id"] == legend_item_id), None)
    if item is None:
        raise DecisionCardError("No governed record %s." % legend_item_id)
    if not item.get("snapshot_path"):
        raise DecisionCardError(
            "Legend item %s has no snapshot. A decision card must show the "
            "mark." % legend_item_id)

    card = {
        "target_kind": DECISION_CARD_TARGET_ITEM,
        "target_id": legend_item_id,
        "source_id": item.get("source_id"),
        "scope_kind": item.get("scope_kind") or LEGEND_SCOPE_INSTANCE,
        "verbs": list(DECISION_CARD_VERBS),
        "question": question,
        "interpretation": interpretation,
        "exception_summary": exception_summary,
    }
    return {
        "decision_card": card,
        "visual_references": [_reference(item)],
        "governed": {
            "member_count": 1, "instance_count": 0,
            "held_count": 1 if item.get("status") == LEGEND_STATUS_REVIEW_NEEDED else 0,
            "state": item.get("status"),
            "meaning": item.get("proposed_meaning"),
            "proposed_kind": item.get("proposed_kind"),
        },
    }


def current_disposition(store, workspace, card: dict) -> dict:
    """Read the answer back OFF THE GOVERNED RECORD, every render.

    This is what makes Composer and the As-Read page incapable of disagreeing:
    neither holds a disposition, both ask the same record. A card whose target
    was decided on the workbench shows that decision without Composer being
    told, and a stale card cannot exist because there is nothing to go stale.
    """
    if not card:
        return {"settled": False, "state": None, "meaning": None}
    kind = card.get("target_kind")
    target = card.get("target_id")
    try:
        if kind == DECISION_CARD_TARGET_FAMILY:
            summary = family_meaning(store, workspace, target)
            state = summary.get("state")
            return {
                "settled": state == "confirmed",
                "state": state,
                "meaning": summary.get("meaning"),
                "missing": False,
            }
        item = next((i for i in store.legend_items_for(workspace)
                     if i["id"] == target), None)
        if item is None:
            # Honest degradation: the message and its provenance survive; the
            # card says the record is gone rather than pretending it answered.
            return {"settled": False, "state": None, "meaning": None, "missing": True}
        status = item.get("status")
        return {
            "settled": status in ("confirmed", "overridden", "unknown", "informative"),
            "state": status,
            "meaning": item.get("proposed_meaning"),
            "missing": False,
        }
    except (CaseWorkspaceError, Exception):  # noqa: B014 - deliberate
        return {"settled": False, "state": None, "meaning": None, "missing": True}


def snapshot_is_available(store, workspace, reference: dict) -> bool:
    """Does the governed record this reference names still carry a crop?

    Checked at render time so a removed snapshot degrades to "evidence no
    longer available" beside a message that still records what was asked and
    why - rather than a broken image, which tells the reader nothing.
    """
    item = next((i for i in store.legend_items_for(workspace)
                 if i["id"] == reference.get("legend_item_id")), None)
    return bool(item and item.get("snapshot_path"))
