"""
CLAUDE-P23 - the stable requirement bank for the compounding-suspicion
controlled experiment (tools/self_test_compounding_suspicion_experiment.py).

Deliberately reuses EXACT text already proven, across many real prior
runs, in the six Golden Laboratory Suite v1 tiers - never new, untested
prose. The whole point of this experiment is to isolate whether NEIGHBORING
evidence changes how a KNOWN-CLEAN or KNOWN-DEFECTIVE pair gets classified,
so every item's own, isolated classification must already be established
and stable before it can serve as a control.

Five categories, each with a stable, short id prefix:

CLEAN  - two independently unrelated, always-clean requirements
         (tier 1's R3/R4 - submission window vs evaluation weighting).
BAIT   - a genuine paraphrase pair (tier 4's record-drawings/as-built
         pair) - proven historically clean, and specifically the kind of
         thing an over-eager reasoner might false-positive on, since
         "different wording, same obligation" is easy to mistake for a
         real difference.
CONTRA - tier 1's classic, unambiguous numerical contradiction (72h
         autonomy vs 48h fuel storage) - the one case every prior run
         has caught 100% of the time.
DIFFICULT - tier 4 Case D's three-item exception scenario (gates
         unlocked / gates locked / an exception clause reconciling both) -
         apparently contradictory on the first two alone, but correctly
         non-contradictory once the exception is read.
AMBIGUOUS - tier 4 Case B's hidden qualification pair (unrestricted
         access vs locked doors) - documented in this codebase's own
         history as a genuinely qualitative, not clean-cut, case.
"""
from __future__ import annotations

from services.bhive_parser import RequirementItem
from tests.self_test.golden_corpus import golden_requirements
from tests.self_test.golden_corpus_semantic import AS_BUILT_DOCUMENTATION_TEXT, RECORD_DRAWINGS_TEXT
from tests.self_test.mutations import apply_numerical_contradiction
from tests.self_test.mutations_semantic import (
    GATES_EXCEPTION_TEXT,
    GATES_LOCKED_SECURITY_TEXT,
    GATES_UNLOCKED_TEXT,
    LOCKED_DOORS_SECURITY_TEXT,
    UNRESTRICTED_ACCESS_TEXT,
)

_tier1_clean = {r.id: r for r in golden_requirements()}
_tier1_mutated, _tier1_answer_key = apply_numerical_contradiction(golden_requirements())
_tier1_mutated_by_id = {r.id: r for r in _tier1_mutated}


def _item(item_id: str, text: str, category: str = "scope_of_work") -> RequirementItem:
    return RequirementItem(id=item_id, text=text, category=category, confidence=0.9, source_line=0)


CLEAN_A1 = _item("CLEAN-A1", _tier1_clean["R3"].text, category="submission_instruction")
CLEAN_A2 = _item("CLEAN-A2", _tier1_clean["R4"].text, category="evaluation_criteria")

BAIT_B1 = _item("BAIT-B1", RECORD_DRAWINGS_TEXT)
BAIT_B2 = _item("BAIT-B2", AS_BUILT_DOCUMENTATION_TEXT)

CONTRA_C1 = _item("CONTRA-C1", _tier1_mutated_by_id["R1"].text, category="technical_specification")
CONTRA_C2 = _item("CONTRA-C2", _tier1_mutated_by_id["R2"].text, category="technical_specification")

DIFFICULT_D1 = _item("DIFFICULT-D1", GATES_UNLOCKED_TEXT)
DIFFICULT_D2 = _item("DIFFICULT-D2", GATES_LOCKED_SECURITY_TEXT)
DIFFICULT_D3 = _item("DIFFICULT-D3", GATES_EXCEPTION_TEXT)

AMBIGUOUS_E1 = _item("AMBIGUOUS-E1", UNRESTRICTED_ACCESS_TEXT)
AMBIGUOUS_E2 = _item("AMBIGUOUS-E2", LOCKED_DOORS_SECURITY_TEXT)

CLEAN_ITEMS = [CLEAN_A1, CLEAN_A2]
BAIT_ITEMS = [BAIT_B1, BAIT_B2]
CONTRA_ITEMS = [CONTRA_C1, CONTRA_C2]
DIFFICULT_ITEMS = [DIFFICULT_D1, DIFFICULT_D2, DIFFICULT_D3]
AMBIGUOUS_ITEMS = [AMBIGUOUS_E1, AMBIGUOUS_E2]

ALL_ITEMS_BY_ID = {
    item.id: item
    for item in CLEAN_ITEMS + BAIT_ITEMS + CONTRA_ITEMS + DIFFICULT_ITEMS + AMBIGUOUS_ITEMS
}

# The one pair every permutation measures the false-positive rate against.
BAIT_PAIR_IDS = frozenset({"BAIT-B1", "BAIT-B2"})
