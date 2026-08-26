"""
CLAUDE-PROJECT-CODE-01 - the governed project acronym, and the human-readable
Task and Case references built from it.

People say "SRPC-T-014" in a meeting. They do not say a UUID.

THE PROPERTY THAT MATTERS MOST

An issued reference is STORED on the record, never re-derived at render time.
That is the whole reason a later acronym change is safe: the Task keeps the
string it was issued, so every report and email that already quoted it stays
true. A derived reference would silently rewrite history on rename, which the
Product Owner direction explicitly forbids. Several tests below exist only to
prove that stored-not-derived property holds.
"""
from __future__ import annotations

import unittest

from services.project_code import (
    CODE_MAX_LENGTH, CODE_MIN_LENGTH, ProjectCodeError, REFERENCE_TYPE_CASE,
    REFERENCE_TYPE_TASK, derive_code, format_reference, is_valid_code,
    issue_reference, next_sequence, normalize_code, validate_code,
)


class DerivingAnAcronymNobodyHadToInvent(unittest.TestCase):
    def test_it_takes_the_initials_a_person_would_have_written(self):
        self.assertEqual(derive_code("South Regional Police Centre"), "SRPC")
        self.assertEqual(derive_code("North Bayview Courthouse"), "NBC")

    def test_project_is_not_treated_as_a_noise_word(self):
        # This repository's own governed synthetic identity is Project Smoke
        # Detector = PSD (CLAUDE-PSD-FOUNDATION-01). Dropping "project" as noise
        # derives SMOK instead - inventing a second acronym for a project that
        # already has an authoritative one.
        self.assertEqual(derive_code("Project Smoke Detector"), "PSD")

    def test_a_leading_job_number_does_not_produce_an_invalid_code(self):
        # Real names here start with job numbers. Initialling "222109 1860
        # Alstep Dr" gives "21AD" - invalid, and unrecognizable even if it were
        # not.
        code = derive_code("222109 1860 Alstep Dr")
        self.assertTrue(is_valid_code(code))
        self.assertTrue(code[0].isalpha())

    def test_a_single_word_name_is_truncated_rather_than_initialled(self):
        self.assertEqual(derive_code("Riverside"), "RIVE")

    def test_a_two_word_short_name_still_yields_three_letters(self):
        self.assertEqual(derive_code("Elm Court"), "ELM")

    def test_a_name_with_no_letters_still_yields_a_valid_code(self):
        code = derive_code("12345")
        self.assertTrue(is_valid_code(code))

    def test_every_derived_code_is_valid(self):
        for name in ["A", "The Of And", "  ", "X Y", "Ω Ω Ω",
                     "Toronto Transit Commission Union Station Revitalisation"]:
            with self.subTest(name=name):
                self.assertTrue(is_valid_code(derive_code(name)), name)


class AcronymsDoNotCollide(unittest.TestCase):
    def test_a_taken_acronym_is_avoided(self):
        first = derive_code("South Regional Police Centre")
        second = derive_code("South Regional Police Centre", taken=[first])
        self.assertNotEqual(first, second)
        self.assertTrue(is_valid_code(second))

    def test_many_identical_names_all_get_distinct_codes(self):
        taken = []
        for _ in range(12):
            code = derive_code("Riverside Water Treatment", taken=taken)
            self.assertNotIn(code, taken)
            taken.append(code)

    def test_collision_checking_is_case_insensitive(self):
        code = derive_code("South Regional Police Centre", taken=["srpc"])
        self.assertNotEqual(normalize_code(code), "SRPC")


class ValidatingWhatAPersonTyped(unittest.TestCase):
    def test_a_good_code_is_normalized_not_rejected(self):
        self.assertEqual(validate_code(" s-r p c "), "SRPC")

    def test_too_short_and_too_long_are_refused_with_a_usable_message(self):
        for bad in ["AB", "ABCDE"]:
            with self.subTest(bad=bad), self.assertRaises(ProjectCodeError) as caught:
                validate_code(bad)
            self.assertIn(str(CODE_MIN_LENGTH), str(caught.exception))
            self.assertIn(str(CODE_MAX_LENGTH), str(caught.exception))

    def test_a_code_must_start_with_a_letter(self):
        with self.assertRaises(ProjectCodeError):
            validate_code("1ABC")

    def test_an_empty_code_is_refused(self):
        with self.assertRaises(ProjectCodeError):
            validate_code("")

    def test_a_taken_code_is_refused_by_name(self):
        with self.assertRaises(ProjectCodeError) as caught:
            validate_code("SRPC", taken=["SRPC"])
        self.assertIn("already in use", str(caught.exception))


class ReferencesAreStableAndIndependent(unittest.TestCase):
    def test_the_shape_is_what_people_will_say_out_loud(self):
        self.assertEqual(format_reference("SRPC", REFERENCE_TYPE_TASK, 14), "SRPC-T-014")
        self.assertEqual(format_reference("SRPC", REFERENCE_TYPE_CASE, 6), "SRPC-C-006")

    def test_task_and_case_sequences_are_independent(self):
        # SRPC-T-014 and SRPC-C-014 may both exist: the type letter distinguishes
        # them, so neither sequence has to leave gaps for the other.
        issued = ["SRPC-T-001", "SRPC-T-014", "SRPC-C-001"]
        self.assertEqual(next_sequence(issued, REFERENCE_TYPE_TASK), 15)
        self.assertEqual(next_sequence(issued, REFERENCE_TYPE_CASE), 2)

    def test_a_deleted_record_never_frees_its_number(self):
        # Derived from issued references rather than from a count, so removing
        # the middle one cannot make the next record reuse a retired reference.
        self.assertEqual(next_sequence(["SRPC-T-001", "SRPC-T-009"], REFERENCE_TYPE_TASK), 10)

    def test_the_first_reference_is_001(self):
        self.assertEqual(issue_reference("SRPC", REFERENCE_TYPE_TASK, []), "SRPC-T-001")

    def test_a_thousandth_task_widens_rather_than_wrapping(self):
        # Ugly but honest: wrapping to SRPC-T-000 would collide with real history.
        self.assertEqual(format_reference("SRPC", REFERENCE_TYPE_TASK, 1000), "SRPC-T-1000")

    def test_a_project_without_a_code_issues_no_reference(self):
        # Honest absence beats a fabricated string that looks authoritative and
        # identifies nothing.
        self.assertIsNone(issue_reference(None, REFERENCE_TYPE_TASK, []))
        self.assertIsNone(issue_reference("", REFERENCE_TYPE_TASK, []))
        self.assertIsNone(issue_reference("1BAD", REFERENCE_TYPE_TASK, []))

    def test_foreign_references_do_not_disturb_the_sequence(self):
        self.assertEqual(
            next_sequence(["OTHR-T-050", "SRPC-T-002", None, "", "garbage"],
                          REFERENCE_TYPE_TASK),
            51,
            "sequence is per-project by construction - the caller passes only its own")


class TheStoreIssuesAndKeepsReferences(unittest.TestCase):
    def setUp(self):
        import shutil
        import tempfile

        from services.case_workspace import CaseWorkspaceStore

        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-code-01")
        self.workspace.project_code = "SRPC"
        self.store.save(self.workspace)
        self.case = self.store.create_case(self.workspace, title="Matter", objective="o")
        self.message = self.store.add_message(
            self.workspace, self.case["id"], role="human", text="do the thing")
        self.store.save(self.workspace)

    def _anchor(self):
        return {"scope": "case", "case_id": self.case["id"],
                "message_id": self.message["id"], "start_offset": 0,
                "end_offset": len(self.message["text"]), "quote": self.message["text"]}

    def test_a_new_case_is_issued_the_first_case_reference(self):
        self.assertEqual(self.case["reference"], "SRPC-C-001")

    def test_a_new_task_is_issued_the_first_task_reference(self):
        task = self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        self.assertEqual(task["reference"], "SRPC-T-001")

    def test_successive_tasks_increment(self):
        first = self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        second = self.store.create_task(self.workspace, self._anchor(), title="t2", actor="u")
        self.assertEqual(first["reference"], "SRPC-T-001")
        self.assertEqual(second["reference"], "SRPC-T-002")

    def test_the_reference_survives_ordinary_task_mutation(self):
        task = self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        issued = task["reference"]
        self.store.complete_task(self.workspace, task["id"], actor="u")
        self.store.reopen_task(self.workspace, task["id"], actor="u")
        after = next(t for t in self.store.get("proj-code-01").tasks if t["id"] == task["id"])
        self.assertEqual(after["reference"], issued)

    def test_renaming_the_acronym_does_not_rewrite_issued_references(self):
        # The property this whole design exists for. A derived reference would
        # silently rewrite every report that already quoted SRPC-T-001.
        task = self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        workspace = self.store.get("proj-code-01")
        workspace.project_code = "NEWC"
        self.store.save(workspace)
        after = next(t for t in self.store.get("proj-code-01").tasks if t["id"] == task["id"])
        self.assertEqual(after["reference"], "SRPC-T-001")

    def test_a_task_created_after_the_change_uses_the_new_code(self):
        self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        workspace = self.store.get("proj-code-01")
        workspace.project_code = "NEWC"
        self.store.save(workspace)
        later = self.store.create_task(workspace, self._anchor(), title="t2", actor="u")
        self.assertTrue(later["reference"].startswith("NEWC-T-"))
        # And it does not restart at 001 - the sequence follows what was issued,
        # not what the code is.
        self.assertEqual(later["reference"], "NEWC-T-002")

    def test_a_project_without_a_code_still_creates_tasks(self):
        workspace = self.store.get_or_create("proj-code-02")
        case = self.store.create_case(workspace, title="c", objective="o")
        message = self.store.add_message(workspace, case["id"], role="human", text="hello")
        self.store.save(workspace)
        task = self.store.create_task(
            workspace,
            {"scope": "case", "case_id": case["id"], "message_id": message["id"],
             "start_offset": 0, "end_offset": 5, "quote": "hello"},
            title="no code here", actor="u")
        self.assertIsNone(task["reference"])
        self.assertIsNone(case["reference"])
        self.assertEqual(task["title"], "no code here")

    def test_the_machine_id_is_still_the_identity(self):
        # A human reference is for people; nothing looks records up by it.
        task = self.store.create_task(self.workspace, self._anchor(), title="t1", actor="u")
        self.assertTrue(task["id"])
        self.assertNotEqual(task["id"], task["reference"])


if __name__ == "__main__":
    unittest.main()
