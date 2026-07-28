"""
CLAUDE-P21 - hermetic tests for tests/self_test/candidate_admission.py's
ONE genuinely model-independent check: deterministic_ceiling_check.

Pure function, no mocks needed, no model calls anywhere in this module -
that is exactly the point being tested.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from tests.self_test.candidate_admission import (
    deterministic_ceiling_check,
    extract_ceiling_ppm,
    extract_ph_range,
)


class ExtractionTests(unittest.TestCase):
    def test_extract_ceiling_ppm(self):
        self.assertEqual(extract_ceiling_ppm("rated for continuous service up to 3.0 ppm"), 3.0)

    def test_extract_ceiling_ppm_absent(self):
        self.assertIsNone(extract_ceiling_ppm("no ppm figure here"))

    def test_extract_ceiling_ppm_exceeding_phrasing(self):
        # CLAUDE-P22: unambiguous exposure-prohibition wording, not "rated for up to X".
        self.assertEqual(extract_ceiling_ppm("shall not be exposed to concentrations exceeding 3.0 ppm"), 3.0)

    def test_extract_ceiling_ppm_exceed_phrasing(self):
        self.assertEqual(extract_ceiling_ppm("shall not be used where concentration may exceed 3.0 ppm"), 3.0)

    def test_extract_ph_range_within_the_range_of_phrasing(self):
        self.assertEqual(extract_ph_range("pH values within the range of 7.2 to 7.6"), (7.2, 7.6))

    def test_extract_ph_range_between_phrasing(self):
        self.assertEqual(extract_ph_range("pH between 7.0 and 8.0"), (7.0, 8.0))


class DeterministicCeilingCheckTests(unittest.TestCase):
    def test_confirms_ceiling_conflict_when_mutated_is_lower(self):
        result = deterministic_ceiling_check(
            mutated_text="rated for continuous service at free chlorine concentrations up to 3.0 ppm and pH values within the range of 7.2 to 7.6",
            reference_text="rated for continuous service in chlorinated water at free chlorine concentrations up to 5.0 ppm and pH values within the range of 7.0 to 8.0",
        )
        self.assertEqual(result.mutated_ceiling_ppm, 3.0)
        self.assertEqual(result.reference_ceiling_ppm, 5.0)
        self.assertTrue(result.ceiling_conflict)
        self.assertTrue(result.numeric_conflict_confirmed)

    def test_no_conflict_when_ranges_are_equal(self):
        result = deterministic_ceiling_check(
            mutated_text="rated up to 5.0 ppm and pH between 7.0 and 8.0",
            reference_text="rated up to 5.0 ppm and pH between 7.0 and 8.0",
        )
        self.assertFalse(result.ceiling_conflict)
        self.assertFalse(result.ph_range_conflict)
        self.assertFalse(result.numeric_conflict_confirmed)

    def test_missing_figures_never_fabricate_a_conflict(self):
        result = deterministic_ceiling_check(mutated_text="no numbers here", reference_text="also none")
        self.assertIsNone(result.mutated_ceiling_ppm)
        self.assertFalse(result.numeric_conflict_confirmed)


if __name__ == "__main__":
    unittest.main()
