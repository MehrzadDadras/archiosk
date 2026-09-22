"""CLAUDE-FINDING-CAPTURE-01 - SCREENSHOT CAPTURE != AUTHORITY.

The capability being wired here already existed and was never called from the
investigation path. These tests hold BOTH halves: that it now runs, and that
running it changes nothing about what the claim is worth.
"""
import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services.case_workspace import (
    EVIDENCE_CLASS_EXTRACTED,
    OBJECT_KIND_ADDRESSABLE_REGION,
    CaseWorkspaceStore,
)
from services.finding_capture import (
    SKIPPED_NO_CAPTURE_DIR,
    SKIPPED_NO_REGION,
    SKIPPED_NO_STORED_FILE,
    SKIPPED_REGION_NOT_RECTANGULAR,
    capture_claim_region,
)


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.root / "registry")
        self.workspace = self.store.get_or_create("proj-capture")
        self.capture_dir = self.root / "captures"

    def _drawing(self, with_bytes=True):
        path = self.root / "plan.png"
        if with_bytes:
            buf = io.BytesIO()
            Image.new("RGB", (400, 300), (250, 250, 250)).save(buf, format="PNG")
            path.write_bytes(buf.getvalue())
        return self.store.add_source(
            self.workspace, name="plan.png",
            file_path=str(path) if with_bytes else "",
            kind="drawing", width=400, height=300)

    def _region(self, source, region_type="rectangular"):
        unit = self.store.create_structural_unit(
            self.workspace, source_id=source["id"], unit_type="sheet",
            order_index=1, label="Sheet A-201", actor="tester")
        return self.store.create_addressable_region(
            self.workspace, structural_unit_id=unit["id"], region_type=region_type,
            address={"x": 0.1, "y": 0.1, "width": 0.4, "height": 0.3},
            actor="tester")

    def _claim_citing(self, region_id):
        """A real Claim through the real recorder, citing a real region."""
        case = self.store.create_case(self.workspace, "Capture", "Check the detail")
        step = self.store.record_investigation_step(
            self.workspace, case_id=case["id"], step_kind="cross_modal_investigation",
            anchor={"anchor_type": OBJECT_KIND_ADDRESSABLE_REGION, "anchor_id": region_id},
            question="What does this detail show?", triggered_by_actor="tester")
        return self.store.record_investigation_claim(
            self.workspace, investigation_step_id=step["id"],
            statement="The detail shows a 3.6m setback.",
            claim_class="directly_verified", method="direct_retrieval",
            confidence_state="strong_direct_support",
            author_type="deterministic_process", created_by="tester",
            evidence_links=[{"object_type": OBJECT_KIND_ADDRESSABLE_REGION,
                             "object_id": region_id}])


class ACapturableClaimIsCaptured(_Fixture):
    def test_a_rectangular_region_over_real_bytes_produces_a_derivative(self):
        source = self._drawing()
        region = self._region(source)
        claim = self._claim_citing(region["id"])

        before = len(self.workspace.sources)
        result = capture_claim_region(self.store, self.workspace, claim["id"],
                                      self.capture_dir, actor="tester")

        self.assertTrue(result["captured"], result["skipped_reason"])
        self.assertIsNone(result["skipped_reason"])
        self.assertEqual(result["region_id"], region["id"])
        # A real, governed derivative Source - not a loose file.
        self.assertEqual(len(self.workspace.sources), before + 1)
        derivative = next(s for s in self.workspace.sources
                          if s["id"] == result["derivative_source_id"])
        self.assertEqual(derivative["origin_reference"], region["id"])
        self.assertTrue(Path(derivative["file_path"]).is_file())

    def test_capture_confers_no_authority_on_the_claim(self):
        """The whole point. The claim must be byte-identical afterwards."""
        source = self._drawing()
        region = self._region(source)
        claim = self._claim_citing(region["id"])
        before = dict(next(c for c in self.workspace.claims if c["id"] == claim["id"]))

        capture_claim_region(self.store, self.workspace, claim["id"],
                             self.capture_dir, actor="tester")

        after = next(c for c in self.workspace.claims if c["id"] == claim["id"])
        self.assertEqual(before, after)
        # And the derivative carries no evidence class or adoption state.
        derivative = self.workspace.sources[-1]
        self.assertNotIn("evidence_class", derivative)
        self.assertNotIn("adoption_state", derivative)


class EveryRefusalIsNamed(_Fixture):
    """Skips are the ordinary case and must each be distinguishable."""

    def test_no_capture_directory_is_a_named_skip_not_a_crash(self):
        source = self._drawing()
        claim = self._claim_citing(self._region(source)["id"])
        result = capture_claim_region(self.store, self.workspace, claim["id"], None)
        self.assertFalse(result["captured"])
        self.assertEqual(result["skipped_reason"], SKIPPED_NO_CAPTURE_DIR)

    def test_a_claim_citing_no_region_is_distinguished_from_an_uncroppable_one(self):
        case = self.store.create_case(self.workspace, "C", "O")
        step = self.store.record_investigation_step(
            self.workspace, case_id=case["id"], step_kind="cross_modal_investigation",
            anchor={"anchor_type": "case", "anchor_id": case["id"]},
            question="q", triggered_by_actor="tester")
        claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=step["id"],
            statement="No evidence at all.", claim_class="unknown",
            method="direct_retrieval", confidence_state="insufficient_evidence",
            author_type="deterministic_process", created_by="tester",
            evidence_links=[])
        result = capture_claim_region(self.store, self.workspace, claim["id"],
                                      self.capture_dir)
        self.assertEqual(result["skipped_reason"], SKIPPED_NO_REGION)

    def test_a_text_span_region_reports_not_rectangular(self):
        source = self._drawing()
        region = self._region(source, region_type="text_span")
        claim = self._claim_citing(region["id"])
        result = capture_claim_region(self.store, self.workspace, claim["id"],
                                      self.capture_dir)
        self.assertFalse(result["captured"])
        self.assertEqual(result["skipped_reason"], SKIPPED_REGION_NOT_RECTANGULAR)

    def test_a_source_with_no_stored_file_reports_it_and_does_not_raise(self):
        source = self._drawing(with_bytes=False)
        region = self._region(source)
        claim = self._claim_citing(region["id"])
        result = capture_claim_region(self.store, self.workspace, claim["id"],
                                      self.capture_dir)
        self.assertFalse(result["captured"])
        self.assertEqual(result["skipped_reason"], SKIPPED_NO_STORED_FILE)


class TheEngineCallsIt(_Fixture):
    """The door, not just the room. Four capabilities in this repository were
    built and never called; this test exists so this is not the fifth."""

    def test_the_investigation_engine_reports_captures_and_skips(self):
        from services.cross_modal_investigation import investigate_cross_modal_question

        source = self._drawing()
        region = self._region(source)
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=source["id"],
            evidence_class=EVIDENCE_CLASS_EXTRACTED, content="A detail.",
            content_type="text", actor="tester", region_id=region["id"])
        case = self.store.create_case(self.workspace, "Engine", "Investigate")

        result = investigate_cross_modal_question(
            self.store, self.workspace, question="What is here?", case_id=case["id"],
            anchor_object_type="evidence_item", anchor_object_id=evidence["id"],
            actor="tester", capture_dir=self.capture_dir)

        # The engine's own contract is unchanged, with capture reported beside it.
        self.assertIn("claim_ids", result)
        self.assertIn("region_captures", result)
        self.assertIn("capture_skips", result)
        self.assertEqual(
            len(result["region_captures"]) + len(result["capture_skips"]),
            len(result["claim_ids"]))

    def test_omitting_the_directory_leaves_the_engine_exactly_as_it_was(self):
        from services.cross_modal_investigation import investigate_cross_modal_question

        source = self._drawing()
        evidence = self.store.register_evidence_item(
            self.workspace, source_id=source["id"],
            evidence_class=EVIDENCE_CLASS_EXTRACTED, content="A detail.",
            content_type="text", actor="tester")
        case = self.store.create_case(self.workspace, "Engine", "Investigate")

        result = investigate_cross_modal_question(
            self.store, self.workspace, question="What is here?", case_id=case["id"],
            anchor_object_type="evidence_item", anchor_object_id=evidence["id"],
            actor="tester")

        self.assertEqual(result["region_captures"], [])
        self.assertTrue(all(s["reason"] == SKIPPED_NO_CAPTURE_DIR
                            for s in result["capture_skips"]))


if __name__ == "__main__":
    unittest.main()
