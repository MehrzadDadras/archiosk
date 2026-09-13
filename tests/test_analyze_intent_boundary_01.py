"""CLAUDE-ANALYZE-BOUNDARY-01 - the Analyze intent may not lie about what saw.

Consolidation Blueprint 01 established, and these tests defend:

    SILENT_FALLBACK_DOES_NOT_EXIST     nothing in the real perception stack can
                                       degrade into the prototype
    compare_region IS REAL             pixel comparison, on a live path
    analyze_drawing IS NOT             canned text from a fixed library

The defect being closed is narrow and was never a crash. A reviewer typed
"Analyze this drawing", received "Analysis complete … 3 candidate finding(s)",
and nothing in that sentence said the finding text had been chosen from a list
of six illustrative statements without the drawing being read. The engine name
was stored, and rendered on the Artifact - so the information existed, one click
away, for a reader who knew that "beehive-mock-vision" meant "canned".

That is disclosure by archaeology. These tests require it in the sentence the
reviewer actually reads.

WHAT IS DELIBERATELY NOT TESTED HERE: that a real engine serves this intent. It
does not. The deployed perception stack reads positioned TEXT; it produces no
candidate findings against an objective. Inventing that integration was out of
scope, so the gap is recorded in `test_the_architectural_gap_is_recorded` rather
than hidden behind a passing assertion.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import drawing_analysis, region_comparison
from services.case_workspace import SOURCE_KIND_DRAWING, CaseWorkspaceStore
from services.conversation_interpreter import interpret_message


def _write_image(path: Path, colour, size=(400, 300)):
    Image.new("RGB", size, colour).save(path, format="PNG")
    return path


class CompareRegionIsRealAndStillWorks(unittest.TestCase):
    """A - the real logic survived the move, unchanged in behaviour."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.region = {"x": 0.1, "y": 0.1, "width": 0.5, "height": 0.5}

    def test_identical_images_compare_unchanged(self):
        a = _write_image(self.tmp / "a.png", (120, 120, 120))
        b = _write_image(self.tmp / "b.png", (120, 120, 120))
        self.assertEqual(region_comparison.compare_region(a, b, self.region),
                         "unchanged")

    def test_a_materially_different_region_compares_changed(self):
        a = _write_image(self.tmp / "a.png", (0, 0, 0))
        b = _write_image(self.tmp / "b.png", (255, 255, 255))
        self.assertEqual(region_comparison.compare_region(a, b, self.region),
                         "changed")

    def test_an_unreadable_image_is_undetermined_not_an_exception(self):
        a = _write_image(self.tmp / "a.png", (10, 10, 10))
        missing = self.tmp / "nope.png"
        self.assertEqual(region_comparison.compare_region(a, missing, self.region),
                         "unable_to_determine")

    def test_the_threshold_and_return_vocabulary_are_carried_across(self):
        """No semantic change: same threshold, same three return values."""
        self.assertEqual(region_comparison.CHANGED_THRESHOLD, 8)
        self.assertEqual(
            {region_comparison.STATUS_UNCHANGED, region_comparison.STATUS_CHANGED,
             region_comparison.STATUS_UNABLE_TO_DETERMINE},
            {"unchanged", "changed", "unable_to_determine"})

    def test_case_workspace_takes_it_from_the_real_module(self):
        source = Path("services/case_workspace.py").read_text(encoding="utf-8")
        self.assertIn("from services.region_comparison import compare_region", source)
        self.assertNotIn("from services.drawing_analysis import compare_region", source)


class TheRealCodeDoesNotDependOnThePrototype(unittest.TestCase):
    """D - and the dependency may only ever run one way."""

    def test_the_prototype_no_longer_owns_the_real_comparison(self):
        self.assertFalse(hasattr(drawing_analysis, "compare_region"))

    def test_the_real_module_never_imports_the_prototype(self):
        source = Path("services/region_comparison.py").read_text(encoding="utf-8")
        self.assertNotIn("import drawing_analysis", source)
        self.assertNotIn("from services.drawing_analysis", source)

    def test_no_real_perception_module_can_reach_the_prototype(self):
        """The measured claim from Blueprint 01, kept true by assertion."""
        for name in ("perception_worker", "perception_jobs", "drawing_intelligence",
                     "sheet_vision", "legend_detection", "legend_slicing",
                     "raster_extraction", "positioned_text"):
            path = Path("services/%s.py" % name)
            if not path.exists():
                continue
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("drawing_analysis", source,
                             "%s must not be able to reach the prototype" % name)

    def test_the_handler_has_no_except_clause_that_falls_back_to_canned_output(self):
        source = Path("services/conversation_interpreter.py").read_text(encoding="utf-8")
        start = source.index("def _handle_analyze")
        end = source.index("def _handle_show_evidence")
        body = source[start:end]
        after_except = body.split("except Exception")[1:]
        for fragment in after_except:
            self.assertNotIn("analyze_drawing(", fragment.split("def ")[0],
                             "a failure must not be answered with canned output")


class ThePrototypeDeclaresItself(unittest.TestCase):
    """C - explicit, machine-readable, and in the module's own first line."""

    def test_the_engine_class_is_recorded_not_merely_implied_by_a_name(self):
        self.assertEqual(drawing_analysis.ENGINE_CLASS, "PROTOTYPE")

    def test_the_capability_vocabulary_admits_no_real_engine(self):
        self.assertEqual(
            {drawing_analysis.CAPABILITY_PROTOTYPE,
             drawing_analysis.CAPABILITY_UNAVAILABLE},
            {"PROTOTYPE", "UNAVAILABLE"})

    def test_capability_is_prototype_by_default(self):
        """Preserved, not deleted: switching it off by default would have
        removed a working user-facing path, which this tranche forbids."""
        self.assertEqual(drawing_analysis.analysis_capability(),
                         drawing_analysis.CAPABILITY_PROTOTYPE)

    def test_capability_can_be_withdrawn_explicitly(self):
        original = os.environ.get(drawing_analysis.PROTOTYPE_ENABLED_ENV)
        os.environ[drawing_analysis.PROTOTYPE_ENABLED_ENV] = "0"
        try:
            self.assertEqual(drawing_analysis.analysis_capability(),
                             drawing_analysis.CAPABILITY_UNAVAILABLE)
        finally:
            if original is None:
                os.environ.pop(drawing_analysis.PROTOTYPE_ENABLED_ENV, None)
            else:
                os.environ[drawing_analysis.PROTOTYPE_ENABLED_ENV] = original

    def test_the_module_says_what_it_is_before_it_says_anything_else(self):
        doc = (drawing_analysis.__doc__ or "")
        self.assertIn("PROTOTYPE", doc.splitlines()[0].upper())


class TheAnalyzeIntentTellsTheTruth(unittest.TestCase):
    """B and E - exercised through the real interpreter, not by source scan."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.artifacts = self.tmp / "artifacts"
        self.artifacts.mkdir()
        self.store = CaseWorkspaceStore(self.tmp / "store")
        self.workspace = self.store.get_or_create("proj-analyze-boundary")
        drawing = _write_image(self.tmp / "sheet.png", (200, 200, 200))
        source = self.store.add_source(
            self.workspace, name="A-01 Plan", file_path=str(drawing),
            kind=SOURCE_KIND_DRAWING, width=400, height=300)
        self.case = self.store.create_case(
            self.workspace, title="Datum review",
            objective="Check datum consistency", created_by="reviewer@example.com")
        self.case["source_ids"].append(source["id"])
        self.store.save(self.workspace)

    def _analyze(self):
        return interpret_message(
            "Analyze this drawing for datum inconsistencies",
            self.workspace, self.case, self.store, self.artifacts,
            "reviewer@example.com", None)

    def test_the_reply_says_it_did_not_read_the_drawing(self):
        result = self._analyze()
        self.assertTrue(result.action_taken.startswith("analysis:"),
                        result.action_taken)
        self.assertIn("PROTOTYPE ANALYSIS", result.reply_text)
        self.assertIn("did NOT read the drawing", result.reply_text)

    def test_the_reply_names_the_engine_that_produced_it(self):
        result = self._analyze()
        self.assertIn(drawing_analysis.ENGINE_NAME, result.reply_text)
        self.assertIn(drawing_analysis.ENGINE_VERSION, result.reply_text)

    def test_the_reply_no_longer_claims_a_bare_completed_analysis(self):
        """The exact sentence that made canned output read as perception."""
        result = self._analyze()
        self.assertNotIn("Analysis complete", result.reply_text)

    def test_what_is_stored_carries_the_prototype_engine_identity(self):
        self._analyze()
        analyses = self.workspace.analyses
        self.assertTrue(analyses)
        self.assertEqual(analyses[-1]["engine_name"], drawing_analysis.ENGINE_NAME)
        self.assertEqual(analyses[-1]["engine_version"],
                         drawing_analysis.ENGINE_VERSION)

    def test_the_existing_action_taken_contract_is_preserved(self):
        """Callers and tests key on these prefixes; the tranche may not move them."""
        result = self._analyze()
        self.assertTrue(result.action_taken.startswith("analysis:"))

    def test_withdrawing_the_capability_returns_an_explicit_state_and_stores_nothing(self):
        before = len(self.workspace.analyses)
        original = os.environ.get(drawing_analysis.PROTOTYPE_ENABLED_ENV)
        os.environ[drawing_analysis.PROTOTYPE_ENABLED_ENV] = "off"
        try:
            result = self._analyze()
        finally:
            if original is None:
                os.environ.pop(drawing_analysis.PROTOTYPE_ENABLED_ENV, None)
            else:
                os.environ[drawing_analysis.PROTOTYPE_ENABLED_ENV] = original
        self.assertEqual(result.action_taken, "analyze_unavailable")
        self.assertIn("No drawing-analysis engine is available", result.reply_text)
        self.assertEqual(len(self.workspace.analyses), before,
                         "an unavailable engine must not store an Analysis")

    def test_a_case_with_no_drawing_still_declines_honestly(self):
        """F - the pre-existing honest decline is untouched."""
        empty = self.store.create_case(
            self.workspace, title="No sources", objective="none",
            created_by="reviewer@example.com")
        result = interpret_message(
            "Analyze this drawing", self.workspace, empty, self.store,
            self.artifacts, "reviewer@example.com", None)
        self.assertEqual(result.action_taken, "analyze_failed")


class TheArchitecturalGapIsRecorded(unittest.TestCase):
    """What this tranche did NOT fix, asserted so it cannot be forgotten."""

    def test_the_architectural_gap_is_recorded(self):
        source = Path("services/conversation_interpreter.py").read_text(encoding="utf-8")
        start = source.index("def _handle_analyze")
        body = source[start:start + 3000]
        self.assertIn("no real drawing-analysis engine", body.lower())
        self.assertIn("positioned TEXT", body)


if __name__ == "__main__":
    unittest.main()
