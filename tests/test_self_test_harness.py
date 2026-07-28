"""
CLAUDE-P13R - proves the self-test laboratory's own plumbing (mutation ->
answer key -> evaluator) is correct, using a MOCKED consistency-check
result. This does NOT exercise a real model - that is deliberately a
separate, hand-run exercise (tools/self_test_lab.py), matching the same
test-hermeticity discipline already established for requirement_
investigation.py (see app.py's create_app("testing") forcing
ANTHROPIC_API_KEY empty) - the automated suite must never silently make
a real, billed call.

What this DOES prove, hermetically and on every run:
  - the mutation function changes exactly what its own answer key claims
    and nothing else;
  - the evaluator correctly sorts a caught defect, a missed defect, a
    confirmed false positive (matching a declared non_defect), and an
    unplanted/unexplained flag into their four separate buckets;
  - a genuinely clean run (no flags at all) is not itself a failure -
    "caught nothing because there was nothing to catch" must never be
    conflated with "missed a planted defect."

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from services.bhive_parser import ConsistencyFlag
from tests.self_test.evaluator import evaluate
from tests.self_test.golden_corpus import golden_requirements
from tests.self_test.mutation_schema import PlantedMutation
from tests.self_test.mutations import apply_numerical_contradiction


class MutationTests(unittest.TestCase):
    def test_mutation_changes_only_the_targeted_requirement(self):
        original = golden_requirements()
        mutated, answer_key = apply_numerical_contradiction(original)

        changed = [
            (o.id, o.text) for o, m in zip(original, mutated) if o.text != m.text
        ]
        self.assertEqual([c[0] for c in changed], ["R2"])
        self.assertIn("48 hours", mutated[1].text)

        # The original list itself must be untouched (mutation returns a copy).
        self.assertIn("72 hours", original[1].text)

    def test_answer_key_names_the_real_change(self):
        _, answer_key = apply_numerical_contradiction(golden_requirements())
        self.assertEqual(answer_key.location, "R1")
        self.assertIn("72", answer_key.description)
        self.assertIn("48", answer_key.description)


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        _, self.answer_key = apply_numerical_contradiction(golden_requirements())

    def test_clean_run_with_no_flags_is_not_a_missed_defect_by_itself(self):
        """A clean run against the UNMUTATED corpus should produce no
        flags - this is success (leaving a good document alone), not
        evaluated against an answer key that doesn't apply to it."""
        result = evaluate(flags=[], answer_key=[])
        self.assertEqual(result.caught, [])
        self.assertEqual(result.missed, [])
        self.assertEqual(result.confirmed_false_positives, [])
        self.assertEqual(result.unplanted_and_unexplained, [])

    def test_a_correctly_targeted_flag_is_caught(self):
        flag = ConsistencyFlag(
            id="flag-1", requirement_a_id="R1", requirement_a_text="72 hours...",
            requirement_b_id="R2", requirement_b_text="48 hours...",
            explanation="R1 requires 72h autonomy but R2 sizes fuel for only 48h.",
        )
        result = evaluate(flags=[flag], answer_key=[self.answer_key])
        self.assertEqual(result.caught, [self.answer_key.mutation_id])
        self.assertEqual(result.missed, [])

    def test_no_flags_at_all_against_a_real_answer_key_is_a_missed_defect(self):
        result = evaluate(flags=[], answer_key=[self.answer_key])
        self.assertEqual(result.caught, [])
        self.assertEqual(result.missed, [self.answer_key.mutation_id])

    def test_a_flag_matching_a_declared_non_defect_is_a_confirmed_false_positive(self):
        flag = ConsistencyFlag(
            id="flag-2", requirement_a_id="R3", requirement_a_text="45 days...",
            requirement_b_id="R4", requirement_b_text="60/40...",
            explanation="R3's submission window conflicts with R4's evaluation weighting.",
        )
        result = evaluate(flags=[flag], answer_key=[self.answer_key])
        self.assertEqual(result.confirmed_false_positives, [flag.explanation])
        self.assertEqual(result.unplanted_and_unexplained, [])
        # A confirmed false positive must never also count as caught.
        self.assertEqual(result.caught, [])

    def test_an_unexplained_flag_goes_to_its_own_bucket_not_silently_dropped(self):
        flag = ConsistencyFlag(
            id="flag-3", requirement_a_id="R5", requirement_a_text="as-built...",
            requirement_b_id="R3", requirement_b_text="45 days...",
            explanation="A genuinely novel pairing the answer key says nothing about.",
        )
        result = evaluate(flags=[flag], answer_key=[self.answer_key])
        self.assertEqual(result.unplanted_and_unexplained, [flag.explanation])
        self.assertEqual(result.confirmed_false_positives, [])

    def test_summary_reports_all_four_categories(self):
        result = evaluate(flags=[], answer_key=[self.answer_key])
        self.assertIn("missed=1", result.summary())
        self.assertIn("caught=0", result.summary())


class BothAnchorsCorrectTests(unittest.TestCase):
    """CLAUDE-P14: a two-sided mutation (secondary_location set) is
    evaluated on two separate questions - was it found at all, and were
    BOTH real anchors correctly named - not collapsed into one."""

    def setUp(self):
        self.mutation = PlantedMutation(
            mutation_id="MUT-TEST-cross", mutation_kind="cross_document_inconsistency",
            difficulty_tier="cross_document", description="x", location="RFP-1",
            secondary_location="APX-1", expected_detection="x",
        )

    def test_both_anchors_correctly_named_is_caught_and_marked_correct(self):
        flag = ConsistencyFlag(
            id="f1", requirement_a_id="RFP-1", requirement_a_text="96h",
            requirement_b_id="APX-1", requirement_b_text="72h", explanation="mismatch",
        )
        result = evaluate(flags=[flag], answer_key=[self.mutation])
        self.assertEqual(result.caught, [self.mutation.mutation_id])
        self.assertEqual(result.both_anchors_correct, [self.mutation.mutation_id])

    def test_only_one_anchor_named_is_caught_but_not_marked_both_correct(self):
        """Real Requirement ids only ever come from THIS mutation's own
        pair in this test, so any match here is inherently 'found it' -
        but citing the wrong second id must not count as both-correct."""
        flag = ConsistencyFlag(
            id="f2", requirement_a_id="RFP-1", requirement_a_text="96h",
            requirement_b_id="SOME-OTHER-ID", requirement_b_text="?", explanation="mismatch",
        )
        result = evaluate(flags=[flag], answer_key=[self.mutation])
        self.assertEqual(result.caught, [self.mutation.mutation_id])
        self.assertEqual(result.both_anchors_correct, [])

    def test_single_sided_mutation_never_populates_both_anchors_correct(self):
        _, single_sided = apply_numerical_contradiction(golden_requirements())
        flag = ConsistencyFlag(
            id="f3", requirement_a_id="R1", requirement_a_text="72h",
            requirement_b_id="R2", requirement_b_text="48h", explanation="mismatch",
        )
        result = evaluate(flags=[flag], answer_key=[single_sided])
        self.assertEqual(result.caught, [single_sided.mutation_id])
        self.assertEqual(result.both_anchors_correct, [])


if __name__ == "__main__":
    unittest.main()
