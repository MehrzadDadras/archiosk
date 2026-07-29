"""
CLAUDE-P26 - specimens for the isolated structured-output reliability
investigation (tools/self_test_structured_output_reliability_
experiment.py).

Reuses, unchanged:
  - the aquatic-centre candidate's own clean SPEC-22-41-04/-06 pair,
    materialized from tests/self_test/candidates/276cac42-07c8-4866-
    be91-b78c9798cb6e.json (read-only - CLAUDE-P26 does not reconsider
    or promote that candidate).
  - the dense HVAC/purge-cooling RECONCILED pair from CLAUDE-P25's
    tests/self_test/scope_reconciliation_bank.py
    (temporal_occupied_unoccupied_dense), unchanged.

Adds ONE new specimen CLAUDE-P26 needs that P25 didn't build: a dense
pair in the SAME domain and clause shape as the reconciled one above,
but where the scopes genuinely DO overlap - so the reliability
investigation covers a genuine-conflict case, not only clean ones. The
"including during occupied hours" overlap phrase mirrors the same
escape-route pattern already used by scope_reconciliation_bank.py's
other CONFLICT specimens.
"""
from __future__ import annotations

from services.bhive_parser import RequirementItem
from tests.self_test.scope_reconciliation_bank import PAIRS as SCOPE_RECONCILIATION_PAIRS


def _item(item_id: str, text: str) -> RequirementItem:
    return RequirementItem(id=item_id, text=text, category="scope_of_work", confidence=0.9, source_line=0)


DENSE_RECONCILED_PAIR = next(
    p for p in SCOPE_RECONCILIATION_PAIRS
    if p.dimension == "temporal_occupied_unoccupied_dense" and p.kind == "reconciled"
)

DENSE_CONFLICT_ITEM_A = _item(
    "DENSE-CONFLICT-A",
    "Space A shall be maintained at a temperature of 68 to 72 degrees Fahrenheit during occupied hours, "
    "and all HVAC equipment serving Space A shall be sized to reject heat loads from IT equipment, "
    "lighting, and occupancy during that period.",
)
DENSE_CONFLICT_ITEM_B = _item(
    "DENSE-CONFLICT-B",
    "All ductwork, dampers, and terminal units serving Space A, including equipment used during "
    "occupied-hour operation, shall be rated for continuous service at supply air temperatures as low "
    "as 40 degrees Fahrenheit. This rating is required because the facility's emergency purge-cooling "
    "protocol, mandated by the fire marshal, may be performed at any time of day, including during "
    "occupied hours, and requires the entire HVAC system serving Space A - with no damper or terminal "
    "unit isolated or closed for any reason - to remain in continuous full-flow operation while supply "
    "air temperature is reduced to 40 degrees Fahrenheit during each purge-cooling event.",
)
DENSE_CONFLICT_NOTE = (
    "Same domain, density, and bundled-clause shape as the reconciled dense pair above, but "
    "'including during occupied hours' explicitly places the 40F purge-cooling event inside Space A's "
    "68-72F occupied-hours requirement - a genuine, overlapping-scope conflict, not resolved by any "
    "scope dimension."
)

# Filler clean items used only to give the dense pairs a realistic
# multi-item BATCH context without re-deriving a whole new corpus -
# reused verbatim from the (unrelated, already-clean) scope-
# reconciliation bank so they carry no risk of their own false positive.
BATCH_FILLER_ITEMS = [
    p.item_a for p in SCOPE_RECONCILIATION_PAIRS
    if p.dimension in ("operational_mode", "spatial_zone", "temporary_permanent")
][:3]
