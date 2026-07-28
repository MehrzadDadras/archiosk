"""
CLAUDE-P13R self-test laboratory - hidden answer-key evaluation.

Grades the investigator's real, blind output (a list of ConsistencyFlag)
against the answer key (a list of PlantedMutation) it never saw. Matches
by requirement id (PlantedMutation.location against ConsistencyFlag.
requirement_a_id/requirement_b_id) - exact, not fuzzy text search, since
services/bhive_parser.py's own consistency prompt already gives the
model each requirement's real id to cite back.
"""
from __future__ import annotations

from services.bhive_parser import ConsistencyFlag

from tests.self_test.mutation_schema import PlantedMutation, SelfTestResult


def evaluate(flags: list[ConsistencyFlag], answer_key: list[PlantedMutation]) -> SelfTestResult:
    result = SelfTestResult()
    caught_mutation_ids: set[str] = set()
    both_anchors_correct_ids: set[str] = set()

    for flag in flags:
        flagged_ids = {flag.requirement_a_id, flag.requirement_b_id}
        matched_mutation = next(
            (m for m in answer_key if m.location in flagged_ids or m.secondary_location in flagged_ids),
            None,
        )

        if matched_mutation is not None:
            caught_mutation_ids.add(matched_mutation.mutation_id)
            # "identified the correct anchors on BOTH sides" - only a
            # meaningful question for a mutation that HAS two sides.
            if (
                matched_mutation.secondary_location is not None
                and matched_mutation.location in flagged_ids
                and matched_mutation.secondary_location in flagged_ids
            ):
                both_anchors_correct_ids.add(matched_mutation.mutation_id)
            continue

        # Not a match for any planted mutation - check whether the golden
        # corpus's own answer key already named this exact PAIR as a known
        # non-defect (a confirmed false positive), or whether it's
        # genuinely unexplained (a human must judge: hallucination, or a
        # real discovery the corpus author didn't anticipate). Requires
        # BOTH flagged ids in the SAME non_defect text, not just either
        # one anywhere - an id mentioned in an unrelated non_defect note
        # must not launder a genuinely different, unexplained pairing.
        is_declared_non_defect = any(
            all(req_id in non_defect_text for req_id in flagged_ids)
            for mutation in answer_key
            for non_defect_text in mutation.non_defects
        )
        if is_declared_non_defect:
            result.confirmed_false_positives.append(flag.explanation)
        else:
            result.unplanted_and_unexplained.append(flag.explanation)

    for mutation in answer_key:
        if mutation.mutation_id in caught_mutation_ids:
            result.caught.append(mutation.mutation_id)
            if mutation.mutation_id in both_anchors_correct_ids:
                result.both_anchors_correct.append(mutation.mutation_id)
        else:
            result.missed.append(mutation.mutation_id)

    return result
