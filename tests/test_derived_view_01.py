"""
CLAUDE-DERIVED-VIEW-01 - scaled/oriented views within one drawing page.

This is an ARCHITECTURE PROOF, not a feature test. Nothing here detects a scale,
finds a North arrow or derives geometry - that is future work and must arrive as
evidence carrying a method. What is proven is that the model can hold those
facts, and that it REFUSES to be used when it cannot.

The refusals carry the weight. A scaled drawing region is exactly where a
plausible number is dangerous: 1:50 read off the wrong detail, or two plans
overlaid across different Norths, are wrong confidently and quietly.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import derived_view as dv
from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    NORTH_CORROBORATION_CORROBORATED,
    NORTH_CORROBORATION_INCONSISTENT,
    NORTH_CORROBORATION_UNRESOLVED,
    NORTH_KIND_CONFLICTED,
    NORTH_KIND_PROJECT,
    NORTH_KIND_TRUE,
    NORTH_KIND_VIEW_ORIENTATION,
    ORIENTATION_STATE_NORTH_KNOWN,
    ORIENTATION_STATE_NOT_APPLICABLE,
    SCALE_METHOD_GRAPHIC_SCALE_BAR,
    SCALE_METHOD_PRINTED_NOTATION,
    SCALE_STATE_KNOWN,
    SCALE_STATE_NTS,
    SCALE_STATE_REVIEW_NEEDED,
    SCALE_STATE_UNKNOWN,
)
from services.governance import GovernanceLog


def _png(w=80, h=60):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (30, 90, 160)).save(buf, format="PNG")
    return buf.getvalue()


class _ViewBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_dv_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-dv")

        path = self.tmp_dir / "A-101.png"
        path.write_bytes(_png())
        self.source = self.store.add_drawing_source(
            self.workspace, name="A-101.png", file_path=str(path), width=80, height=60,
            document_id="A-101", revision="3", issuer="Dadras Architects")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, self.source["id"],
            [{"index": 0, "label": "A-101 GROUND FLOOR PLAN", "width": 80, "height": 60,
              "source_rotation": 0, "metadata": {"discipline": "architectural"}}],
            actor="tester")
        self.page_unit_id = registered["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _view(self, **kw):
        params = dict(
            source_id=self.source["id"],
            page_structural_unit_id=self.page_unit_id,
            region={"x": 0.0, "y": 0.0, "width": 40.0, "height": 30.0},
            derivation_reason="overall plan", actor="tester")
        params.update(kw)
        return self.store.create_derived_view(self.workspace, **params)


class MultiScalePageTests(_ViewBase):
    """6A/6B. One page, several independently scaled views."""

    def test_one_page_carries_several_views_at_different_scales(self):
        overall = self._view(derivation_reason="overall plan",
                             scale_state=SCALE_STATE_KNOWN, scale_value=100.0,
                             scale_notation="1:100",
                             scale_method=SCALE_METHOD_PRINTED_NOTATION,
                             unit_system="metric")
        detail = self._view(derivation_reason="enlarged detail",
                            region={"x": 40.0, "y": 0.0, "width": 20.0, "height": 15.0},
                            scale_state=SCALE_STATE_KNOWN, scale_value=10.0,
                            scale_notation="1:10",
                            scale_method=SCALE_METHOD_PRINTED_NOTATION,
                            unit_system="metric")
        views = self.store.derived_views_for(
            self.workspace, page_structural_unit_id=self.page_unit_id)
        self.assertEqual(len(views), 2)
        self.assertNotEqual(overall["scale_value"], detail["scale_value"])

    def test_no_page_wide_scale_is_implied(self):
        """The page unit itself must gain no scale - that is the whole point."""
        self._view(scale_state=SCALE_STATE_KNOWN, scale_value=50.0,
                   scale_notation="1:50", scale_method=SCALE_METHOD_PRINTED_NOTATION)
        refreshed = self.store.get(self.workspace.project_id)
        page = next(u for u in refreshed.structural_units if u["id"] == self.page_unit_id)
        blob = repr(page).lower()
        self.assertNotIn("scale_value", blob)

    def test_a_known_scale_must_say_how_it_was_established(self):
        """A number without evidence is a guess wearing a number."""
        with self.assertRaises(CaseWorkspaceError):
            self._view(scale_state=SCALE_STATE_KNOWN, scale_value=50.0,
                       scale_notation="1:50")

    def test_every_scale_state_is_representable(self):
        for state in (SCALE_STATE_UNKNOWN, SCALE_STATE_REVIEW_NEEDED, SCALE_STATE_NTS):
            with self.subTest(state=state):
                view = self._view(scale_state=state)
                self.assertEqual(view["scale_state"], state)

    def test_scale_evidence_methods_are_recorded_distinctly(self):
        bar = self._view(scale_state=SCALE_STATE_KNOWN, scale_value=200.0,
                         scale_notation="1:200",
                         scale_method=SCALE_METHOD_GRAPHIC_SCALE_BAR)
        self.assertEqual(bar["scale_method"], SCALE_METHOD_GRAPHIC_SCALE_BAR)


class MeasurementGuardTests(_ViewBase):
    """6B. NTS must never be measured; unknown must never be guessed."""

    def test_an_nts_view_refuses_measurement_with_its_own_reason(self):
        view = self._view(scale_state=SCALE_STATE_NTS, scale_notation="NTS")
        allowed, reason = dv.may_measure(view)
        self.assertFalse(allowed)
        self.assertIn("NOT TO SCALE", reason)

    def test_an_unknown_scale_refuses_measurement(self):
        self.assertFalse(dv.may_measure(self._view())[0])

    def test_review_needed_is_not_treated_as_good_enough(self):
        self.assertFalse(dv.may_measure(self._view(scale_state=SCALE_STATE_REVIEW_NEEDED))[0])

    def test_a_fully_evidenced_scale_is_measurable(self):
        view = self._view(scale_state=SCALE_STATE_KNOWN, scale_value=50.0,
                          scale_notation="1:50",
                          scale_method=SCALE_METHOD_PRINTED_NOTATION)
        self.assertTrue(dv.may_measure(view)[0])


class OrientationAndNorthTests(_ViewBase):
    """6C/6I. True and project North are independent and never merged."""

    def test_both_norths_are_preserved_independently(self):
        view = self._view(
            orientation_state=ORIENTATION_STATE_NORTH_KNOWN, north_state=NORTH_KIND_TRUE,
            true_north_degrees=12.5, true_north_method="north_arrow",
            project_north_degrees=0.0, project_north_method="project_grid")
        self.assertEqual(view["true_north_degrees"], 12.5)
        self.assertEqual(view["project_north_degrees"], 0.0)

    def test_the_north_reference_says_WHICH_north_it_is(self):
        view = self._view(north_state=NORTH_KIND_PROJECT, project_north_degrees=0.0,
                          project_north_method="project_grid")
        reference = dv.north_reference(view)
        self.assertTrue(reference["usable"])
        self.assertEqual(reference["kind"], NORTH_KIND_PROJECT)

    def test_view_orientation_alone_is_not_a_north_reference(self):
        view = self._view(north_state=NORTH_KIND_VIEW_ORIENTATION,
                          source_rotation_degrees=90.0)
        reference = dv.north_reference(view)
        self.assertFalse(reference["usable"])
        self.assertIn("not a North reference", reference["reason"])

    def test_not_applicable_is_distinct_from_unknown(self):
        """A section has no North; that is not the same as failing to find one."""
        section = self._view(derivation_reason="section A-A",
                             orientation_state=ORIENTATION_STATE_NOT_APPLICABLE)
        self.assertEqual(section["orientation_state"], ORIENTATION_STATE_NOT_APPLICABLE)


class NorthReconciliationTests(_ViewBase):
    """6G/6H. A disagreement is a finding, not a tie to break."""

    def _other_source(self, name="survey.png"):
        path = self.tmp_dir / name
        path.write_bytes(_png())
        return self.store.add_drawing_source(
            self.workspace, name=name, file_path=str(path), width=80, height=60)

    def test_uncorroborated_north_is_unresolved_not_corroborated(self):
        view = self._view(north_state=NORTH_KIND_TRUE, true_north_degrees=10.0,
                          true_north_method="north_arrow")
        self.assertEqual(dv.north_corroboration_state(view), NORTH_CORROBORATION_UNRESOLVED)

    def test_agreement_from_a_survey_corroborates(self):
        view = self._view(north_state=NORTH_KIND_TRUE, true_north_degrees=10.0,
                          true_north_method="north_arrow")
        survey = self._other_source()
        updated = self.store.record_north_corroboration(
            self.workspace, view["id"], against_source_id=survey["id"],
            agrees=True, method="site_geometry", actor="tester")
        self.assertEqual(dv.north_corroboration_state(updated),
                         NORTH_CORROBORATION_CORROBORATED)

    def test_a_conflicting_drawing_sets_conflicted_and_keeps_both_chains(self):
        view = self._view(north_state=NORTH_KIND_TRUE, true_north_degrees=10.0,
                          true_north_method="north_arrow")
        civil = self._other_source("civil.png")
        updated = self.store.record_north_corroboration(
            self.workspace, view["id"], against_source_id=civil["id"],
            agrees=False, method="survey_reference",
            note="Civil plan shows North 40 degrees off.", actor="tester")
        self.assertEqual(updated["north_state"], NORTH_KIND_CONFLICTED)
        # The local reading is still there - nothing was overwritten.
        self.assertEqual(updated["true_north_degrees"], 10.0)
        self.assertEqual(len(updated["north_corroboration"]), 1)
        self.assertEqual(dv.north_corroboration_state(updated),
                         NORTH_CORROBORATION_INCONSISTENT)

    def test_a_conflicted_view_refuses_to_hand_back_a_direction(self):
        view = self._view(north_state=NORTH_KIND_TRUE, true_north_degrees=10.0,
                          true_north_method="north_arrow")
        civil = self._other_source("civil2.png")
        updated = self.store.record_north_corroboration(
            self.workspace, view["id"], against_source_id=civil["id"],
            agrees=False, method="survey_reference", actor="tester")
        reference = dv.north_reference(updated)
        self.assertFalse(reference["usable"])
        self.assertIsNone(reference["degrees"])

    def test_one_disagreement_is_not_outvoted_by_agreements(self):
        """A conflict is not resolved by counting."""
        view = self._view(north_state=NORTH_KIND_TRUE, true_north_degrees=10.0,
                          true_north_method="north_arrow")
        for index, agrees in enumerate((True, True, False)):
            other = self._other_source("doc%d.png" % index)
            view = self.store.record_north_corroboration(
                self.workspace, view["id"], against_source_id=other["id"],
                agrees=agrees, method="site_geometry", actor="tester")
        self.assertEqual(dv.north_corroboration_state(view),
                         NORTH_CORROBORATION_INCONSISTENT)


class RotatedViewTests(_ViewBase):
    """6D. Both coordinate systems reconstructable; the page is never rotated."""

    def test_the_source_page_is_never_rotated_by_deriving_a_view(self):
        before = next(u for u in self.store.get(self.workspace.project_id).structural_units
                      if u["id"] == self.page_unit_id)
        rotation_before = (before.get("modality_metadata") or {}).get("source_rotation")
        self._view(source_rotation_degrees=90.0, normalized_rotation_degrees=0.0)
        after = next(u for u in self.store.get(self.workspace.project_id).structural_units
                     if u["id"] == self.page_unit_id)
        self.assertEqual((after.get("modality_metadata") or {}).get("source_rotation"),
                         rotation_before)

    def test_coordinates_round_trip_between_page_and_view(self):
        view = self._view(source_rotation_degrees=90.0, normalized_rotation_degrees=0.0)
        page_point = (25.0, 12.0)
        in_view = dv.to_view_coordinates(view, *page_point)
        back = dv.to_source_coordinates(view, *in_view)
        self.assertAlmostEqual(back[0], page_point[0], places=6)
        self.assertAlmostEqual(back[1], page_point[1], places=6)

    def test_an_unrecorded_rotation_refuses_rather_than_assuming_zero(self):
        view = self._view()
        with self.assertRaises(ValueError):
            dv.to_view_coordinates(view, 1.0, 1.0)

    def test_two_plans_with_different_north_are_separate_views(self):
        """One governed view must not carry two North references."""
        a = self._view(derivation_reason="plan A", north_state=NORTH_KIND_TRUE,
                       true_north_degrees=0.0, true_north_method="north_arrow")
        b = self._view(derivation_reason="plan B",
                       region={"x": 40.0, "y": 0.0, "width": 40.0, "height": 30.0},
                       north_state=NORTH_KIND_TRUE, true_north_degrees=45.0,
                       true_north_method="north_arrow")
        self.assertNotEqual(a["id"], b["id"])
        self.assertNotEqual(a["true_north_degrees"], b["true_north_degrees"])


class TitleBlockInheritanceTests(_ViewBase):
    """6E. Derived views inherit sheet identity; overrides sit beside it."""

    def test_a_derived_view_inherits_the_sheet_identity(self):
        view = self._view()
        inherited = view["inherited_title_block"]
        self.assertEqual(inherited["document_id"], "A-101")
        self.assertEqual(inherited["revision"], "3")
        self.assertEqual(inherited["issuer"], "Dadras Architects")
        self.assertEqual(inherited["sheet_label"], "A-101 GROUND FLOOR PLAN")
        self.assertEqual(inherited["sheet_fields"]["discipline"], "architectural")

    def test_deriving_a_view_does_not_mint_a_new_issued_drawing(self):
        view = self._view()
        self.assertEqual(view["inherited_title_block"]["document_id"], "A-101")
        self.assertEqual(view["title_block_overrides"], {})

    def test_a_human_override_never_overwrites_the_inherited_record(self):
        view = self._view()
        updated = self.store.override_derived_view(
            self.workspace, view["id"], actor="pm",
            overrides={"sheet_label": "A-101 GROUND FLOOR PLAN (enlarged NE corner)"})
        self.assertEqual(updated["inherited_title_block"]["sheet_label"],
                         "A-101 GROUND FLOOR PLAN")
        self.assertEqual(updated["title_block_overrides"]["sheet_label"],
                         "A-101 GROUND FLOOR PLAN (enlarged NE corner)")

    def test_the_effective_title_block_composes_both_at_read_time(self):
        view = self._view()
        updated = self.store.override_derived_view(
            self.workspace, view["id"], actor="pm", overrides={"sheet_label": "Corrected"})
        effective = dv.effective_title_block(updated)
        self.assertEqual(effective["sheet_label"], "Corrected")
        self.assertEqual(effective["document_id"], "A-101")
        provenance = dv.title_block_provenance(updated)
        self.assertEqual(provenance["overridden_fields"], ["sheet_label"])
        self.assertEqual(provenance["overridden_by"], "pm")


class SpatialComparisonGuardTests(_ViewBase):
    """6K. Compatibility must be proven before any quantitative alignment."""

    def _plan(self, scale=100.0, north=0.0, **kw):
        params = dict(scale_state=SCALE_STATE_KNOWN, scale_value=scale,
                      scale_notation="1:%d" % scale,
                      scale_method=SCALE_METHOD_PRINTED_NOTATION, unit_system="metric",
                      north_state=NORTH_KIND_TRUE, true_north_degrees=north,
                      true_north_method="north_arrow",
                      source_rotation_degrees=0.0, normalized_rotation_degrees=0.0)
        params.update(kw)
        return self._view(**params)

    def test_two_compatible_plans_may_be_compared(self):
        self.assertTrue(dv.may_compare_spatially(self._plan(), self._plan())[0])

    def test_different_scales_are_refused(self):
        allowed, reason = dv.may_compare_spatially(self._plan(100.0), self._plan(50.0))
        self.assertFalse(allowed)
        self.assertIn("different scales", reason)

    def test_true_north_and_project_north_are_never_mixed(self):
        true_plan = self._plan()
        project_plan = self._plan(north_state=NORTH_KIND_PROJECT,
                                  project_north_degrees=0.0,
                                  project_north_method="project_grid")
        allowed, reason = dv.may_compare_spatially(true_plan, project_plan)
        self.assertFalse(allowed)
        self.assertIn("transform", reason)

    def test_disagreeing_north_directions_are_refused(self):
        allowed, reason = dv.may_compare_spatially(self._plan(north=0.0), self._plan(north=45.0))
        self.assertFalse(allowed)
        self.assertIn("different North", reason)

    def test_an_nts_view_can_never_be_compared(self):
        nts = self._view(scale_state=SCALE_STATE_NTS)
        self.assertFalse(dv.may_compare_spatially(self._plan(), nts)[0])

    def test_different_unit_systems_are_refused(self):
        allowed, _reason = dv.may_compare_spatially(
            self._plan(), self._plan(unit_system="imperial"))
        self.assertFalse(allowed)

    def test_cross_project_comparison_is_refused(self):
        a = self._plan()
        b = dict(self._plan())
        b["project_id"] = "some-other-project"
        self.assertFalse(dv.may_compare_spatially(a, b)[0])


class VectorTraceabilityTests(_ViewBase):
    """6F. The chain a future vector primitive must be able to walk back."""

    def test_the_full_chain_is_reconstructable_from_the_record(self):
        view = self._view(
            scale_state=SCALE_STATE_KNOWN, scale_value=50.0, scale_notation="1:50",
            scale_method=SCALE_METHOD_PRINTED_NOTATION, unit_system="metric",
            orientation_state=ORIENTATION_STATE_NORTH_KNOWN, north_state=NORTH_KIND_TRUE,
            true_north_degrees=12.0, true_north_method="north_arrow",
            source_rotation_degrees=90.0, normalized_rotation_degrees=0.0)
        chain = dv.traceability(view)
        self.assertEqual(chain["source_id"], self.source["id"])
        self.assertEqual(chain["page_structural_unit_id"], self.page_unit_id)
        self.assertEqual(chain["derived_view_id"], view["id"])
        self.assertTrue(chain["scale"]["measurable"])
        self.assertEqual(chain["scale"]["method"], SCALE_METHOD_PRINTED_NOTATION)
        self.assertTrue(chain["north"]["usable"])
        self.assertEqual(chain["orientation"]["applied_rotation_degrees"], -90.0)
        self.assertIsNotNone(chain["region"])

    def test_the_chain_reports_when_geometry_would_not_be_usable(self):
        chain = dv.traceability(self._view(scale_state=SCALE_STATE_NTS))
        self.assertFalse(chain["scale"]["measurable"])
        self.assertFalse(chain["north"]["usable"])


class ProjectIsolationTests(_ViewBase):
    """Boundary, same as everywhere else."""

    def test_a_view_cannot_be_derived_from_another_projects_page(self):
        other = self.store.get_or_create("test-project-dv-other")
        path = self.tmp_dir / "other.png"
        path.write_bytes(_png())
        foreign = self.store.add_drawing_source(
            other, name="other.png", file_path=str(path), width=80, height=60)
        with self.assertRaises(CaseWorkspaceError):
            self.store.create_derived_view(
                self.workspace, source_id=foreign["id"],
                page_structural_unit_id=self.page_unit_id,
                region={"x": 0, "y": 0}, derivation_reason="cross-project", actor="tester")

    def test_views_do_not_leak_between_projects(self):
        self._view()
        other = self.store.get_or_create("test-project-dv-other2")
        self.assertEqual(self.store.derived_views_for(other), [])


if __name__ == "__main__":
    unittest.main()
