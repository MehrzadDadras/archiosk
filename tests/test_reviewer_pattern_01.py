"""CLAUDE-REVIEWER-PATTERN-01 - reviewer-private, project-local investigative patterns.

Product Owner authorized Case A only: a reviewer deliberately saves a private
investigative pattern for their own later use inside the same project. Cross-
project reuse is the Experience Corpus, which governance/STATUS.md marks NOT
AUTHORIZED in all forms, and there is no sharing transition in this slice.

The governing chain is:

    pattern -> investigative context -> review action -> independently
    obtained evidence -> finding

and never pattern -> finding. A saved pattern is a different object class from
a Finding, not a weaker one.

These are the nine guards the authorization required. Most of them assert an
absence, because that is what the boundary is made of.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    KNOWN_ADJUDICATION_ATTRIBUTIONS,
    KNOWN_CLAIM_ADOPTION_STATES,
    KNOWN_CLAIM_CLASSES,
    KNOWN_CONFIDENCE_STATES,
    KNOWN_SAVED_PATTERN_STATES,
    SAVED_PATTERN_SCOPE_PERSONAL,
    SAVED_PATTERN_STATE_ACTIVE,
    SAVED_PATTERN_STATE_RETIRED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)

ROOT = Path(__file__).resolve().parents[1]


class _PatternCase(unittest.TestCase):
    def setUp(self):
        self.tmp_root = Path(tempfile.mkdtemp(prefix="beehive_test_pattern_"))
        self.tmp_dir = self.tmp_root / "registry"
        self.tmp_dir.mkdir()
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_a = self.store.get_or_create("project-a")
        self.project_b = self.store.get_or_create("project-b")

    def tearDown(self):
        shutil.rmtree(self.tmp_root, ignore_errors=True)

    def _save(self, workspace, reviewer="reviewer_one", title="Check damper interlocks"):
        return self.store.save_reviewer_pattern(
            workspace, reviewer=reviewer, title=title,
            investigation_trigger="A smoke-control sequence is described across two disciplines",
            proposed_sequence=[
                "Inspect the mechanical schedule against the fire-alarm matrix",
                "Check whether the interlock is described in both",
            ],
            source_conversation_refs=["msg-123"],
        )


class ItBelongsToOneProjectAndOneReviewerTests(_PatternCase):
    def test_a_pattern_records_its_own_project(self):
        pattern = self._save(self.project_a)
        self.assertEqual(pattern["project_id"], "project-a")

    def test_a_pattern_records_its_own_author(self):
        pattern = self._save(self.project_a, reviewer="reviewer_one")
        self.assertEqual(pattern["created_by"], "reviewer_one")
        self.assertEqual(pattern["scope"], SAVED_PATTERN_SCOPE_PERSONAL)

    def test_an_unnamed_reviewer_cannot_save_one(self):
        with self.assertRaises(CaseWorkspaceError):
            self._save(self.project_a, reviewer="")

    def test_it_survives_a_reload_from_storage(self):
        self._save(self.project_a)
        reloaded = CaseWorkspaceStore(self.tmp_dir).get("project-a")
        self.assertEqual(len(reloaded.saved_patterns_by["reviewer_one"]), 1)


class AnotherReviewerCannotRetrieveItTests(_PatternCase):
    def test_a_different_reviewer_in_the_same_project_sees_nothing(self):
        self._save(self.project_a, reviewer="reviewer_one")
        self.assertEqual(self.store.reviewer_patterns_for(self.project_a, "reviewer_two"), [])

    def test_privacy_is_structural_not_a_filter(self):
        """Stored under the author's own key, so reading someone else's
        requires asking for their key - not merely forgetting a filter."""
        self._save(self.project_a, reviewer="reviewer_one")
        self.assertEqual(list(self.project_a.saved_patterns_by), ["reviewer_one"])

    def test_an_empty_reviewer_gets_nothing_rather_than_everything(self):
        self._save(self.project_a, reviewer="reviewer_one")
        self.assertEqual(self.store.reviewer_patterns_for(self.project_a, ""), [])
        self.assertEqual(self.store.reviewer_patterns_for(self.project_a, None), [])

    def test_a_reviewer_cannot_retire_another_reviewers_pattern(self):
        pattern = self._save(self.project_a, reviewer="reviewer_one")
        self.assertFalse(
            self.store.retire_reviewer_pattern(self.project_a, "reviewer_two", pattern["id"]),
        )
        self.assertEqual(len(self.store.reviewer_patterns_for(self.project_a, "reviewer_one")), 1)


class ItDoesNotTravelBetweenProjectsTests(_PatternCase):
    def test_the_same_reviewer_cannot_retrieve_it_through_another_project(self):
        """This is the Experience Corpus boundary. Crossing it is exactly what
        remains NOT AUTHORIZED."""
        self._save(self.project_a, reviewer="reviewer_one")
        self.assertEqual(self.store.reviewer_patterns_for(self.project_b, "reviewer_one"), [])

    def test_the_two_projects_store_separately(self):
        self._save(self.project_a, reviewer="reviewer_one")
        reloaded_b = CaseWorkspaceStore(self.tmp_dir).get("project-b")
        self.assertEqual(reloaded_b.saved_patterns_by, {})

    def test_no_cross_project_retrieval_path_was_introduced(self):
        """The store exposes retrieval per workspace; nothing added a lookup
        that spans project records."""
        source = (ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        start = source.index("def save_reviewer_pattern")
        end = source.index("def set_project_perspective")
        block = source[start:end]
        for forbidden in ("list_ids", "glob(", "rglob(", "for project_id in"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, block)


class APatternIsNotAFindingTests(_PatternCase):
    def test_its_state_vocabulary_cannot_collide_with_governed_vocabularies(self):
        governed = (
            set(KNOWN_CLAIM_ADOPTION_STATES) | set(KNOWN_CLAIM_CLASSES)
            | set(KNOWN_CONFIDENCE_STATES) | set(KNOWN_ADJUDICATION_ATTRIBUTIONS)
        )
        self.assertEqual(set(KNOWN_SAVED_PATTERN_STATES) & governed, set())

    def test_saving_one_creates_no_finding_requirement_or_evidence(self):
        before = (
            len(self.project_a.findings), len(self.project_a.requirements),
            len(self.project_a.sources), len(self.project_a.cases),
            len(self.project_a.relationships), len(self.project_a.source_references),
        )
        self._save(self.project_a)
        after = (
            len(self.project_a.findings), len(self.project_a.requirements),
            len(self.project_a.sources), len(self.project_a.cases),
            len(self.project_a.relationships), len(self.project_a.source_references),
        )
        self.assertEqual(after, before)

    def test_it_carries_no_claim_confidence_or_authority_field(self):
        """A pattern has nothing an evidence consumer could mistake for
        substantive support."""
        pattern = self._save(self.project_a)
        for field_name in (
            "claim_status", "claim_class", "confidence_state", "outcome",
            "disposition", "adjudicator", "grounded_in", "evidence",
        ):
            with self.subTest(field=field_name):
                self.assertNotIn(field_name, pattern)

    def test_provenance_is_references_never_copied_content(self):
        """The confidentiality boundary in this slice: a pattern cannot leak
        material it never contains, and a reference the reader cannot open
        stays closed to them."""
        pattern = self._save(self.project_a)
        self.assertEqual(pattern["source_conversation_refs"], ["msg-123"])
        blob = " ".join(str(v) for v in pattern.values())
        self.assertNotIn("RESTRICTED", blob.upper())


class NothingSavesAPatternAutomaticallyTests(_PatternCase):
    def test_no_application_code_calls_the_setter(self):
        """Saved patterns require deliberate reviewer action. A dismissed
        suggestion's content must never be persisted as hidden learning, and
        the enforcement is that no code path can create one at all."""
        callers = []
        for directory in ("services", "routes"):
            for path in (ROOT / directory).rglob("*.py"):
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "save_reviewer_pattern(" in text and path.name != "case_workspace.py":
                    callers.append(path.name)
        self.assertEqual(callers, [])

    def test_the_definition_is_the_only_occurrence_in_its_own_module(self):
        source = (ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("def save_reviewer_pattern"), 1)
        self.assertEqual(source.count("save_reviewer_pattern("), 1)


class LosingAccessDoesNotShareItTests(_PatternCase):
    def test_removing_the_author_from_the_allow_list_reveals_nothing(self):
        """Access loss must not turn private memory into shared project
        intelligence."""
        self.project_a.access_allow_list = ["reviewer_one", "reviewer_two"]
        self._save(self.project_a, reviewer="reviewer_one")

        self.project_a.access_allow_list = ["reviewer_two"]
        self.store.save(self.project_a)

        reloaded = CaseWorkspaceStore(self.tmp_dir).get("project-a")
        self.assertEqual(self.store.reviewer_patterns_for(reloaded, "reviewer_two"), [])
        self.assertIn("reviewer_one", reloaded.saved_patterns_by)

    def test_ownership_is_never_transferred(self):
        self._save(self.project_a, reviewer="reviewer_one")
        self.project_a.owner = "reviewer_two"
        self.store.save(self.project_a)
        reloaded = CaseWorkspaceStore(self.tmp_dir).get("project-a")
        self.assertEqual(
            reloaded.saved_patterns_by["reviewer_one"][0]["created_by"], "reviewer_one",
        )
        self.assertEqual(self.store.reviewer_patterns_for(reloaded, "reviewer_two"), [])


class RetirementPreservesTheRecordTests(_PatternCase):
    def test_retiring_hides_it_without_deleting_it(self):
        pattern = self._save(self.project_a)
        self.assertTrue(
            self.store.retire_reviewer_pattern(self.project_a, "reviewer_one", pattern["id"]),
        )
        self.assertEqual(self.store.reviewer_patterns_for(self.project_a, "reviewer_one"), [])
        stored = self.project_a.saved_patterns_by["reviewer_one"][0]
        self.assertEqual(stored["state"], SAVED_PATTERN_STATE_RETIRED)

    def test_a_new_pattern_starts_active(self):
        self.assertEqual(self._save(self.project_a)["state"], SAVED_PATTERN_STATE_ACTIVE)

    def test_returned_patterns_are_copies(self):
        """A caller cannot mutate stored state by editing what it was handed."""
        self._save(self.project_a)
        handed = self.store.reviewer_patterns_for(self.project_a, "reviewer_one")[0]
        handed["title"] = "tampered"
        self.assertNotEqual(
            self.project_a.saved_patterns_by["reviewer_one"][0]["title"], "tampered",
        )


class ExperienceCorpusStaysUnauthorizedTests(_PatternCase):
    def test_only_the_personal_scope_exists(self):
        source = (ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        self.assertIn("SAVED_PATTERN_SCOPE_PERSONAL", source)
        for wider in ("SAVED_PATTERN_SCOPE_PROJECT", "SAVED_PATTERN_SCOPE_ORGANIZATION",
                      "SAVED_PATTERN_SCOPE_GLOBAL"):
            with self.subTest(scope=wider):
                self.assertNotIn(wider, source)

    def test_no_promotion_or_sharing_entry_point_exists(self):
        source = (ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        for forbidden in ("def promote_reviewer_pattern", "def share_reviewer_pattern",
                          "def publish_reviewer_pattern"):
            with self.subTest(entry_point=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
