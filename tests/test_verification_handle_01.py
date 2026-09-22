"""CLAUDE-VERIFICATION-HANDLE-01 - CITATION != VERIFICATION PATH, proven.

Every test here builds its records through the REAL CaseWorkspaceStore methods
and then asks the handle what it says. Hand-built dicts were deliberately not
used: this session has already been burned twice by fixtures that agreed with
the assumption instead of the system, so the store writes the records and the
projection reads them back.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    CURRENTNESS_CURRENT,
    CURRENTNESS_UNRESOLVED,
    DOCUMENT_AUTHORITY_CONTRACTUAL,
    EVIDENCE_CLASS_EXTRACTED,
    KNOWN_CURRENTNESS_STATES,
    OBJECT_KIND_EVIDENCE_ITEM,
    OBJECT_KIND_FINDING,
    AnalysisTrigger,
    CaseWorkspaceStore,
    normalise_currentness,
)
from services.verification_handle import (
    GRANULARITY_NONE,
    GRANULARITY_REGION,
    GRANULARITY_SOURCE,
    STATUS_PARTIAL,
    STATUS_RESOLVED,
    STATUS_UNRESOLVED,
    verification_handle_for,
)


class TheCurrentnessVocabularyIsClosed(unittest.TestCase):
    """The vocabulary exists to stop a fifth spelling, so test the edges."""

    def test_the_resolver_can_only_speak_the_closed_vocabulary(self):
        for state in KNOWN_CURRENTNESS_STATES:
            self.assertEqual(normalise_currentness(state), state)

    def test_case_and_whitespace_do_not_create_new_states(self):
        self.assertEqual(normalise_currentness("  CURRENT "), CURRENTNESS_CURRENT)
        self.assertEqual(normalise_currentness("Stale"), "stale")

    def test_an_unknown_string_never_becomes_current(self):
        """The one direction that would launder a typo into a verified fact."""
        for junk in ("UNCHANGED", "probably fine", "", None, 7, "curren"):
            self.assertEqual(normalise_currentness(junk), CURRENTNESS_UNRESOLVED)


class _Workspace(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.store = CaseWorkspaceStore(self.root)
        self.workspace = self.store.get_or_create("proj-verify")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)

    def _source(self, name="Specification.pdf", authority=None):
        source = self.store.add_source(
            self.workspace, name=name, file_path="/tmp/" + name, kind="project_document")
        if authority:
            record = next(s for s in self.workspace.sources if s["id"] == source["id"])
            record["document_authority"] = authority
            self.store.save(self.workspace)
        return source

    def _analysis(self, case, source_ids, statement):
        """One AnalysisRun carrying one Finding, through the real recorder."""
        return self.store.record_analysis(
            self.workspace, source_ids=source_ids, objective="Verify",
            engine_name="test", engine_version="1.0",
            findings=[{"statement": statement, "machine_confidence": 0.9}],
            trigger=AnalysisTrigger(trigger_type="user_initiated",
                                    triggered_by_actor="tester"),
            case_id=case["id"])

    def _finding_of(self, analysis):
        """record_analysis returns the AnalysisRun; the Finding it created is
        reached through finding_ids, the same way every other consumer does."""
        return next(f for f in self.workspace.findings
                    if f["id"] == analysis["finding_ids"][0])


class AFindingAnchorsAtSourceLevelAndSaysSo(_Workspace):
    """A Finding carries no evidence links. The handle must not imply it does."""

    def test_a_finding_reports_source_granularity_not_a_fabricated_region(self):
        source = self._source()
        case = self.store.create_case(self.workspace, "Setbacks", "Check the north setback")
        analysis = self._analysis(case, [source["id"]],
                                  "The north setback is 3.6m per A-201.")
        finding = self._finding_of(analysis)

        handle = verification_handle_for(
            self.store, self.workspace, OBJECT_KIND_FINDING, finding["id"])

        self.assertEqual(handle["granularity"], GRANULARITY_SOURCE)
        self.assertEqual(handle["status"], STATUS_PARTIAL)
        self.assertIn("region", handle["anchors"][0]["missing"])
        self.assertIn("record an addressable region",
                      handle["next_verification_step"])
        # The identifiers a human would actually search for.
        self.assertIn("A-201", handle["search_terms"])
        self.assertIn("3.6m", handle["search_terms"])

    def test_a_finding_whose_run_recorded_no_source_is_unresolved_not_empty(self):
        case = self.store.create_case(self.workspace, "Hunch", "No evidence yet")
        analysis = self._analysis(case, [], "Something seems wrong.")
        finding = self._finding_of(analysis)

        handle = verification_handle_for(
            self.store, self.workspace, OBJECT_KIND_FINDING, finding["id"])

        self.assertEqual(handle["status"], STATUS_UNRESOLVED)
        self.assertEqual(handle["granularity"], GRANULARITY_NONE)
        self.assertIn("carries no evidence links of its own",
                      handle["unresolved_reason"])
        # Still useful: it says what to do, and it did not invent an anchor.
        self.assertIn("Identify the source", handle["next_verification_step"])
        self.assertEqual(handle["anchors"], [])


class EvidenceAtRegionLevelResolves(_Workspace):
    def _anchored_evidence(self, authority=DOCUMENT_AUTHORITY_CONTRACTUAL):
        source = self._source(authority=authority)
        unit = self.store.create_structural_unit(
            self.workspace, source_id=source["id"], unit_type="page",
            order_index=1, label="Page 12", actor="tester")
        region = self.store.create_addressable_region(
            self.workspace, structural_unit_id=unit["id"], region_type="text_span",
            address={"start_offset": 10, "end_offset": 64}, actor="tester")
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=source["id"],
            evidence_class=EVIDENCE_CLASS_EXTRACTED,
            content="The north setback shall be 3.6m measured to the lot line.",
            content_type="text", actor="tester", region_id=region["id"])
        return source, unit, region, evidence

    def test_a_region_anchored_fact_is_fully_checkable(self):
        _, unit, region, evidence = self._anchored_evidence()

        handle = verification_handle_for(
            self.store, self.workspace, OBJECT_KIND_EVIDENCE_ITEM, evidence["id"])
        anchor = handle["anchors"][0]

        self.assertEqual(handle["granularity"], GRANULARITY_REGION)
        self.assertEqual(handle["status"], STATUS_RESOLVED)
        self.assertEqual(anchor["region"]["id"], region["id"])
        self.assertEqual(anchor["structural_unit"]["label"], "Page 12")
        self.assertTrue(anchor["locator_text"])
        self.assertIn("3.6m", anchor["excerpt"])
        self.assertEqual(anchor["authority"]["level"], DOCUMENT_AUTHORITY_CONTRACTUAL)
        self.assertEqual(anchor["currentness"], CURRENTNESS_CURRENT)
        self.assertEqual(anchor["missing"], [])

    def test_an_unrecorded_authority_is_stated_not_guessed(self):
        _, _, _, evidence = self._anchored_evidence(authority=None)

        handle = verification_handle_for(
            self.store, self.workspace, OBJECT_KIND_EVIDENCE_ITEM, evidence["id"])
        anchor = handle["anchors"][0]

        self.assertFalse(anchor["authority"]["recorded"])
        self.assertIsNone(anchor["authority"]["level"])
        self.assertEqual(handle["status"], STATUS_PARTIAL)
        self.assertIn("document authority", handle["next_verification_step"])

    def test_resolved_means_checkable_never_checked(self):
        """The distinction the whole handle exists to preserve."""
        _, _, _, evidence = self._anchored_evidence()
        handle = verification_handle_for(
            self.store, self.workspace, OBJECT_KIND_EVIDENCE_ITEM, evidence["id"])

        self.assertEqual(handle["status"], STATUS_RESOLVED)
        # A validation is a separate record, and the handle has not written one.
        record = next(e for e in self.workspace.evidence_items
                      if e["id"] == evidence["id"])
        self.assertIsNone(record.get("validation_status"))
        # And the next step asks for exactly that.
        self.assertIn("reviewer validation", handle["next_verification_step"].lower())


class TheHandleWritesNothing(_Workspace):
    """A projection that mutated the workspace would be a second store."""

    def test_reading_a_handle_leaves_the_workspace_byte_identical(self):
        source = self._source(authority=DOCUMENT_AUTHORITY_CONTRACTUAL)
        case = self.store.create_case(self.workspace, "C", "O")
        analysis = self._analysis(case, [source["id"]], "A statement.")
        finding = self._finding_of(analysis)

        path = self.store._path_for(self.workspace.project_id)
        before = path.read_bytes()
        for _ in range(3):
            verification_handle_for(
                self.store, self.workspace, OBJECT_KIND_FINDING, finding["id"])
        self.assertEqual(path.read_bytes(), before)

    def test_an_unsupported_object_type_declines_rather_than_guesses(self):
        handle = verification_handle_for(
            self.store, self.workspace, "requirement", "whatever")
        self.assertEqual(handle["status"], STATUS_UNRESOLVED)
        self.assertIn("no verification path", handle["unresolved_reason"])


if __name__ == "__main__":
    unittest.main()
