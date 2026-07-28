"""
CLAUDE-P13R self-test laboratory - controlled mutation.

Each function here takes the Golden Corpus and returns (mutated_copy,
answer_key) - the mutated copy is what the investigator actually sees;
the answer_key is what the evaluator grades against. The investigator
(tools/self_test_lab.py) only ever imports the mutated copy's requirement
list, never the PlantedMutation - keeping the two genuinely separated,
not just conventionally separated.

The clean (unmutated) Golden Corpus is itself part of the test: running
the investigator against golden_requirements() with NO mutation applied
should find nothing, proving Archiosk can leave a good document alone
rather than manufacturing discrepancies (see tools/self_test_lab.py).

Currently implements the "obvious" tier only - one concrete, working
example end to end, not a full six-tier library built ahead of having
proven the harness itself works. Add the next tier once this one has
actually been run for real (see the accompanying report).
"""
from __future__ import annotations

import copy

from services.bhive_parser import RequirementItem

from tests.self_test.mutation_schema import DIFFICULTY_TIER_OBVIOUS, PlantedMutation


def apply_numerical_contradiction(
    requirements: list[RequirementItem],
) -> tuple[list[RequirementItem], PlantedMutation]:
    """
    Obvious tier: R2's fuel-storage sizing is silently changed from 72 to
    48 hours, directly contradicting R1's 72-hour requirement that R2's
    own text explicitly cites ("per the autonomy requirement in R1").
    Every other requirement is untouched.
    """
    mutated = copy.deepcopy(requirements)
    for item in mutated:
        if item.id == "R2":
            item.text = item.text.replace("72 hours", "48 hours")

    answer_key = PlantedMutation(
        mutation_id="MUT-001-numerical-contradiction",
        mutation_kind="numerical_contradiction",
        difficulty_tier=DIFFICULTY_TIER_OBVIOUS,
        description=(
            "R2's fuel storage sizing was changed from 72 to 48 hours, directly "
            "contradicting R1's 72-hour autonomy requirement, which R2's own text "
            "explicitly cites."
        ),
        location="R1",
        expected_detection=(
            "A cross-requirement contradiction between R1 (72h autonomy) and R2 "
            "(48h fuel storage, while citing R1's 72h requirement)."
        ),
        non_defects=[
            "R3's 45-day submission window and R4's 60/40 evaluation weighting are "
            "unrelated and internally consistent - must not be flagged.",
            "R5's 30-day as-built delivery window is unrelated to fuel autonomy - "
            "must not be flagged.",
        ],
    )
    return mutated, answer_key
