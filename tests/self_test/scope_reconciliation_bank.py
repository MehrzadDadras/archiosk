"""
CLAUDE-P25 - the scope-reconciliation controlled specimen bank.

Investigates a limitation found while admission-reviewing the aquatic-
centre candidate (CLAUDE-P24): the production consistency investigator
may focus on differing numeric thresholds while failing to credit
explicit temporal, operational, spatial, or conditional scope stated
WITHIN the same two clauses being compared - structurally different from
CLAUDE-P23's order/adjacency defect (which concerned a hard pair
contaminating a SEPARATE, unrelated pair elsewhere in a batch).

Six scope dimensions, each with TWO specimens:

  RECONCILED - apparently different obligations that are NOT actually in
  conflict once the stated scope is correctly read (the investigator
  should NOT flag these).

  CONFLICT - a genuine conflict using similar scope-sounding language and
  the same kind of numbers/terminology as its RECONCILED counterpart, so
  a fix cannot simply teach the model "scope language present -> never a
  conflict" (the investigator SHOULD flag these).

Dimensions: occupied/unoccupied hours (temporal), normal/emergency
operating mode, zone/system (spatial), temporary/permanent condition,
design-basis/verified-operating-limit, and general-rule/named-exception
(this last one is the ONE dimension CLAUDE-P16/P23's existing machinery
was already built around - a useful control to confirm that mechanism
still works, since it addresses a reconciling clause SEPARATE from the
two being compared, not scope stated within them).

Every specimen is brand new, hand-authored prose - deliberately NOT the
aquatic-centre candidate's own text, since this investigates the
limitation independently of that candidate's admission.
"""
from __future__ import annotations

from dataclasses import dataclass

from services.bhive_parser import RequirementItem


@dataclass
class ScopePair:
    dimension: str
    kind: str  # "reconciled" | "conflict"
    item_a: RequirementItem
    item_b: RequirementItem
    note: str


def _item(item_id: str, text: str) -> RequirementItem:
    return RequirementItem(id=item_id, text=text, category="scope_of_work", confidence=0.9, source_line=0)


PAIRS: list[ScopePair] = [
    ScopePair(
        dimension="temporal_occupied_unoccupied", kind="reconciled",
        item_a=_item("TEMP-R-A", "Space A shall be maintained at a temperature of 68 to 72 degrees Fahrenheit during occupied hours, defined as 7:00 AM to 6:00 PM."),
        item_b=_item("TEMP-R-B", "Space A temperature may be allowed to set back to 55 degrees Fahrenheit during unoccupied hours for energy conservation."),
        note="Disjoint time windows (occupied vs unoccupied) - not a conflict.",
    ),
    ScopePair(
        dimension="temporal_occupied_unoccupied", kind="conflict",
        item_a=_item("TEMP-C-A", "Space A shall be maintained at a temperature of 68 to 72 degrees Fahrenheit during occupied hours, defined as 7:00 AM to 6:00 PM."),
        item_b=_item("TEMP-C-B", "Space A shall be maintained at 55 degrees Fahrenheit at all times, including during occupied hours, to satisfy adjacent equipment cooling requirements."),
        note="'including during occupied hours' explicitly overlaps the first clause's scope - a genuine conflict.",
    ),
    ScopePair(
        dimension="operational_mode", kind="reconciled",
        item_a=_item("MODE-R-A", "Generator G-1 shall remain on standby, non-running, at all times during normal utility power availability."),
        item_b=_item("MODE-R-B", "Generator G-1 shall start and run automatically during any utility power outage, in emergency operation mode, until normal utility power is restored."),
        note="Different operating modes (normal vs emergency), mutually exclusive by definition - not a conflict.",
    ),
    ScopePair(
        dimension="operational_mode", kind="conflict",
        item_a=_item("MODE-C-A", "Generator G-1 shall remain on standby, non-running, at all times during normal utility power availability."),
        item_b=_item("MODE-C-B", "Generator G-1 shall run continuously, including during normal utility power availability, to support the facility's continuous load-bank testing program."),
        note="'including during normal utility power availability' explicitly overlaps the first clause's scope - a genuine conflict.",
    ),
    ScopePair(
        dimension="spatial_zone", kind="reconciled",
        item_a=_item("ZONE-R-A", "Zone 1 (Server Room), served by AHU-1, shall be maintained at 65 to 68 degrees Fahrenheit year-round."),
        item_b=_item("ZONE-R-B", "Zone 2 (Office Area), served by AHU-2, shall be maintained at 70 to 74 degrees Fahrenheit during occupied hours."),
        note="Different zones served by different air handlers - not a conflict.",
    ),
    ScopePair(
        dimension="spatial_zone", kind="conflict",
        item_a=_item("ZONE-C-A", "Zone 1 (Server Room), served by AHU-1, shall be maintained at 65 to 68 degrees Fahrenheit year-round."),
        item_b=_item("ZONE-C-B", "All zones served by AHU-3, including Zone 1, shall be maintained at 72 to 76 degrees Fahrenheit to satisfy the building's central humidity control strategy."),
        note="'including Zone 1' explicitly places the same zone under a second, conflicting temperature mandate - a genuine conflict.",
    ),
    ScopePair(
        dimension="temporary_permanent", kind="reconciled",
        item_a=_item("TEMP2-R-A", "The permanent parking structure shall provide a minimum of 200 accessible parking spaces upon Substantial Completion."),
        item_b=_item("TEMP2-R-B", "A temporary parking area, in use only during the construction period prior to Substantial Completion, shall provide a minimum of 10 accessible parking spaces."),
        note="Different time periods (construction-only temporary area vs the post-completion permanent structure) - not a conflict.",
    ),
    ScopePair(
        dimension="temporary_permanent", kind="conflict",
        item_a=_item("TEMP2-C-A", "The permanent parking structure shall provide a minimum of 200 accessible parking spaces upon Substantial Completion."),
        item_b=_item("TEMP2-C-B", "All parking areas, whether temporary or permanent, and applicable both before and after Substantial Completion, shall provide not fewer than 240 accessible parking spaces."),
        note="'both before and after Substantial Completion' explicitly overlaps the permanent structure's own scope with a higher, conflicting figure - a genuine conflict.",
    ),
    ScopePair(
        dimension="design_basis_verified", kind="reconciled",
        item_a=_item("DESIGN-R-A", "The transformer shall have a design-basis capacity rating of 2500 kVA."),
        item_b=_item("DESIGN-R-B", "Field-verified load testing confirms the transformer's actual operating load does not exceed 2000 kVA under normal conditions."),
        note="A rated maximum CAPABILITY vs. a verified actual load comfortably within it - not a conflict.",
    ),
    ScopePair(
        dimension="design_basis_verified", kind="conflict",
        item_a=_item("DESIGN-C-A", "The transformer shall have a design-basis capacity rating of 2500 kVA."),
        item_b=_item("DESIGN-C-B", "Field-verified load testing confirms the transformer's actual continuous operating requirement, including all currently planned future expansions, is 2800 kVA."),
        note="The verified REQUIREMENT (2800 kVA, including planned expansions) exceeds the design-basis rating (2500 kVA) - a genuine capacity shortfall.",
    ),
    ScopePair(
        dimension="general_rule_named_exception", kind="reconciled",
        item_a=_item("RULE-R-A", "All exterior doors shall remain locked at all times for building security."),
        item_b=_item("RULE-R-B", "The designated fire exit doors on the east facade, identified in Life Safety Drawing LS-101, are exempt from the locking requirement and shall remain operable for egress at all times."),
        note="A named, specific egress-only exception to the general rule - not a conflict.",
    ),
    ScopePair(
        dimension="general_rule_named_exception", kind="conflict",
        item_a=_item("RULE-C-A", "All exterior doors shall remain locked at all times for building security."),
        item_b=_item("RULE-C-B", "The main lobby entrance doors, identified in Life Safety Drawing LS-101, shall remain unlocked and freely operable during all facility operating hours for public access."),
        note="A named door identified for PUBLIC ACCESS (not egress-only) directly contradicts the general locked-at-all-times rule - a genuine conflict, not resolved merely by being 'named'.",
    ),
    # CLAUDE-P25: added after the baseline run came back a clean 24/24 -
    # every specimen above is a short, single-topic pair. The REAL
    # aquatic-centre candidate's own failing pair (SPEC-22-41-04/-06) was
    # structurally different: a short clause A, and a long clause B
    # bundling several distinct facts (material rating + protocol timing
    # + a continuous-operation mandate) with the scope-qualifying phrase
    # ("performed during non-occupied hours") buried in the middle. This
    # pair deliberately mirrors that DENSITY pattern, in a completely
    # different domain (HVAC/purge-cooling, not pool chemistry), to test
    # whether clause density - not the scope dimension itself - is the
    # real risk factor.
    ScopePair(
        dimension="temporal_occupied_unoccupied_dense", kind="reconciled",
        item_a=_item(
            "DENSE-TEMP-A",
            "Space A shall be maintained at a temperature of 68 to 72 degrees Fahrenheit during occupied hours, "
            "and all HVAC equipment serving Space A shall be sized to reject heat loads from IT equipment, "
            "lighting, and occupancy during that period.",
        ),
        item_b=_item(
            "DENSE-TEMP-B",
            "All ductwork, dampers, and terminal units serving Space A, including equipment used during "
            "occupied-hour operation, shall be rated for continuous service at supply air temperatures as low "
            "as 40 degrees Fahrenheit. This rating is required because the facility's emergency purge-cooling "
            "protocol, mandated by the fire marshal, is performed during unoccupied hours and requires the "
            "entire HVAC system serving Space A - with no damper or terminal unit isolated or closed for any "
            "reason - to remain in continuous full-flow operation while supply air temperature is reduced to "
            "40 degrees Fahrenheit during each purge-cooling event.",
        ),
        note=(
            "Deliberately mirrors the aquatic-centre candidate's own clause density and shape (a short clause A; "
            "a long clause B bundling equipment rating + protocol timing + continuous-operation mandate, with "
            "the 'during unoccupied hours' phrase buried mid-sentence) - same temporal scope dimension as the "
            "first pair above, but structurally dense rather than simple. Not a conflict: the purge-cooling "
            "event and its 40F supply air only occur during unoccupied hours, disjoint from Space A's "
            "occupied-hours 68-72F requirement."
        ),
    ),
]
