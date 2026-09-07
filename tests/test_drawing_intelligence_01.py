"""
CLAUDE-DRAWING-CONDITIONS-01 / CLAUDE-DISCIPLINE-ALIGNMENT-01 - the acceptance
contract for the Drawing Intelligence foundation, A through P.

WHAT THESE TESTS ARE ACTUALLY DEFENDING

Two refusals and one economy.

The first refusal is against inference from geometry. Two lines touching on a
drawing say the draftsman put them there. They do not say an air barrier
carries through the junction, and they do not say one element carries the
other. Both of those are asserted here as tests rather than left as comments,
because they are the inferences a plausible-sounding system makes by default
and they are the ones that would put a fabricated load path into a project
record.

The second refusal is against adequacy. This system can say a load path is
incomplete or unrecorded. It can never say a member is sufficient. That line is
GOV-P-006 at the scale of a drawing, and `test_m_*` pins it.

The economy is the snapshot budget. A review image exists so a human can see
the mark; it is not the image an OCR pass should read. `test_b_*` measures the
actual bytes rather than trusting the intent, because the first real E1 run
produced a 1.9 MB crop while the code already "knew" crops were review-sized.
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services import discipline_alignment as align
from services import drawing_conditions as dcond
from services import legend_of_understanding as lou
from services.case_workspace import (
    ALIGNMENT_STATE_ALIGNED,
    ALIGNMENT_STATE_ASSUMPTION_MISMATCH,
    ALIGNMENT_STATE_CONFLICT,
    ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL,
    ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT,
    ALIGNMENT_STATE_UNRECONCILED,
    BOUNDARY_EVIDENCE_HATCH_CHANGE,
    BOUNDARY_EVIDENCE_MATERIAL_CHANGE,
    BOUNDARY_EVIDENCE_MEMBRANE_TRANSITION,
    CONDITION_KIND_ASSEMBLY,
    CONDITION_KIND_DETAIL,
    CONDITION_KIND_ELEMENT,
    CONDITION_KIND_SYSTEM,
    CONTINUITY_STATE_CONTINUOUS,
    CONTINUITY_STATE_REVIEW_NEEDED,
    CONTINUITY_STATE_TRANSFERRED,
    CaseWorkspaceError,
    CaseWorkspaceStore,
    EDGE_BEHAVIOR_CUT,
    EDGE_BEHAVIOR_OVERLAP,
    EDGE_CLASS_CONTINUITY,
    EDGE_CLASS_DISCRETE,
    FUNCTION_AIR_CONTROL,
    FUNCTION_WATER_CONTROL,
    LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_SCOPE_PAGE,
    LEGEND_SCOPE_PROJECT,
    LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED,
    RELATIONSHIP_TYPE_BEARS_ON,
    RELATIONSHIP_TYPE_HOSTED_BY,
    SOURCE_KIND_DRAWING,
    STRUCTURAL_STATE_PATH_INCOMPLETE,
    STRUCTURAL_STATE_REVIEW_NEEDED,
    STRUCTURAL_STATE_SUPPORTED,
    SUPPORT_DEPENDENCY_DEPENDENT,
    SUPPORT_DEPENDENCY_SELF_SUPPORTING,
    THRESHOLD_KIND_CHANGE,
    THRESHOLD_KIND_RESPONSIBILITY_CHANGE,
)
from services.governance import GovernanceLog

SHEET_W, SHEET_H = 612.0, 460.0


def _sheet_pdf(title="A-101 PLAN") -> bytes:
    drawn = pymupdf.open()
    page = drawn.new_page(width=SHEET_W, height=SHEET_H)
    page.insert_text((40, 60), title, fontsize=12)
    page.insert_text((40, 160), "SECTION 3 / A-501", fontsize=11)
    page.insert_text((40, 260), "AIR BARRIER CONTINUOUS", fontsize=10)
    rasterised = pymupdf.open()
    pix = drawn.load_page(0).get_pixmap(dpi=96)
    out = rasterised.new_page(width=SHEET_W, height=SHEET_H)
    out.insert_image(pymupdf.Rect(0, 0, SHEET_W, SHEET_H), stream=pix.tobytes("png"))
    raw = rasterised.tobytes()
    drawn.close(); rasterised.close()
    return raw


class _DrawingBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_di_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-di")
        self.raw = _sheet_pdf()
        self.source, self.page_id = self._sheet("A-101.pdf", "A-101")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sheet(self, name, document_id, workspace=None, raw=None, revision=None):
        workspace = workspace or self.workspace
        raw = raw if raw is not None else self.raw
        path = self.tmp_dir / name
        path.write_bytes(raw)
        source = self.store.add_source(
            workspace, name=name, file_path=str(path), kind=SOURCE_KIND_DRAWING,
            document_id=document_id, actor="tester")
        if revision is not None:
            # The store returns a COPY, so the stored record is what must be
            # touched - mutating the return value would silently do nothing.
            self.store._find(workspace.sources, source["id"])["revision"] = revision
            self.store.save(workspace)
        registered = self.store.register_drawing_sheet_structure(
            workspace, source["id"],
            [{"index": 0, "label": "%s SHEET" % document_id, "width": SHEET_W,
              "height": SHEET_H, "source_rotation": 0, "metadata": {}}],
            actor="tester")
        return source, registered["structural_unit_ids"][0]

    def _condition(self, meaning, kind=CONDITION_KIND_DETAIL, **kw):
        params = dict(
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            region={"x": 40, "y": 120, "width": 120, "height": 90},
            condition_kind=kind, proposed_meaning=meaning,
            interpretation_method="region_reading", actor="GO")
        params.update(kw)
        return self.store.record_drawing_condition(self.workspace, **params)

    def _boundary(self, condition_id, **kw):
        params = dict(
            condition_id=condition_id,
            region={"x": 40, "y": 200, "width": 120, "height": 4},
            boundary_evidence=[BOUNDARY_EVIDENCE_MATERIAL_CHANGE],
            actor="GO")
        params.update(kw)
        return self.store.record_condition_boundary(self.workspace, **params)


# ---------------------------------------------------------------------------
# A / B - snapshots: real, and bounded
# ---------------------------------------------------------------------------

class SnapshotContractTests(_DrawingBase):

    def test_a_every_review_row_carries_a_real_crop(self):
        path = lou.snapshot_region(
            self.raw, 0, (30, 100, 300, 200),
            str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), "row-a")
        self.assertTrue(Path(path).is_file())
        self.assertGreater(Path(path).stat().st_size, 200)

    def test_b_a_large_crop_is_downsampled_to_review_size(self):
        whole_sheet = lou.snapshot_region(
            self.raw, 0, (0, 0, SHEET_W, SHEET_H),
            str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), "whole-sheet")
        pixmap = pymupdf.Pixmap(whole_sheet)
        self.assertLessEqual(max(pixmap.width, pixmap.height),
                             lou.SNAPSHOT_MAX_LONG_SIDE_PX)

    def test_b_aspect_ratio_survives_the_downsample(self):
        rect = (0, 0, SHEET_W, SHEET_H)
        path = lou.snapshot_region(self.raw, 0, rect,
                                   str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), "aspect")
        pixmap = pymupdf.Pixmap(path)
        source_ratio = SHEET_W / SHEET_H
        self.assertAlmostEqual(pixmap.width / pixmap.height, source_ratio, places=1)

    def test_b_a_small_crop_is_never_upscaled(self):
        # Inventing pixels makes a marginal symbol look more legible than the
        # evidence is - the exact misjudgement snapshot-first review prevents.
        rect = (40, 120, 84, 164)      # 44pt square
        path = lou.snapshot_region(self.raw, 0, rect,
                                   str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), "small")
        pixmap = pymupdf.Pixmap(path)
        natural = 44 * (lou.SNAPSHOT_DPI / 72.0)
        self.assertLessEqual(pixmap.width, natural + 2)

    def test_b_the_cap_holds_at_the_real_sheet_proportions(self):
        # REGRESSION. The real 1860 Alstep E1 is 3024x2160 at rotation 270, and
        # a 0.22 x 0.20 body crop of it rendered 1201px against a stated cap of
        # 1200 - the renderer rounds up to whole pixels. The synthetic sheet
        # above never tripped it, which is exactly why this case exists.
        wide = 3024.0 * 0.22
        tall = 2160.0 * 0.20
        scale = lou._review_scale((0, 0, wide, tall), lou.SNAPSHOT_DPI)
        import math
        self.assertLessEqual(math.ceil(wide * scale),
                             lou.SNAPSHOT_MAX_LONG_SIDE_PX)

    def test_b_snapshot_bytes_stay_within_a_reviewable_budget(self):
        # Measured, not asserted from intent: the first real E1 run produced a
        # 1.9 MB crop from code that already believed crops were review-sized.
        sizes = []
        for index, rect in enumerate([(0, 0, SHEET_W, SHEET_H),
                                      (0, 0, SHEET_W, SHEET_H / 2),
                                      (30, 100, 300, 200)]):
            path = lou.snapshot_region(
                self.raw, 0, rect, str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME),
                "budget-%d" % index)
            sizes.append(os.path.getsize(path))
        self.assertLess(max(sizes), 1_000_000,
                        "a permanent review crop should not reach a megabyte")

    def test_b_source_coordinates_are_stored_untouched_by_resizing(self):
        # Resizing an image must never look like rescaling a drawing.
        region = {"x": 40, "y": 120, "width": 480, "height": 300}
        condition = self._condition("wall assembly", region=region)
        self.assertEqual(condition["region"], region)


# ---------------------------------------------------------------------------
# G / H - scope isolation and precedence
# ---------------------------------------------------------------------------

class ScopeAndPrecedenceTests(_DrawingBase):

    def _propose(self, key, **kw):
        params = dict(
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            region={"x": 30, "y": 140, "width": 270, "height": 50},
            proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
            proposed_meaning="section reference", interpretation_method="generic",
            actor="GO", observed_text="SECTION 3 / A-501",
            snapshot_path=lou.snapshot_region(
                self.raw, 0, (30, 140, 300, 190),
                str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), key))
        params.update(kw)
        return self.store.propose_legend_item(self.workspace, **params)

    def test_g_an_instance_scoped_decision_is_never_reused(self):
        item = self._propose("scope-instance")
        self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED,
            actor="reviewer")            # default scope is INSTANCE
        resolved = lou.resolve_meaning(
            self.store, self.workspace, observed_text="SECTION 3 / A-501",
            source_id=self.source["id"], page_id=self.page_id)
        self.assertNotEqual(resolved["tier"], "confirmed_source_set")

    def test_g_a_page_scoped_decision_does_not_reach_another_page(self):
        other_source, other_page = self._sheet("A-102.pdf", "A-102")
        item = self._propose("scope-page")
        self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED,
            actor="reviewer", scope_kind=LEGEND_SCOPE_PAGE)
        here = lou.resolve_meaning(
            self.store, self.workspace, observed_text="SECTION 3 / A-501",
            page_id=self.page_id, source_id=self.source["id"])
        there = lou.resolve_meaning(
            self.store, self.workspace, observed_text="SECTION 3 / A-501",
            page_id=other_page, source_id=other_source["id"])
        self.assertNotEqual(here["tier"], there["tier"])

    def test_g_a_project_scoped_decision_does_reach_another_sheet(self):
        other_source, other_page = self._sheet("A-103.pdf", "A-103")
        item = self._propose("scope-project")
        self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED,
            actor="reviewer", scope_kind=LEGEND_SCOPE_PROJECT)
        there = lou.resolve_meaning(
            self.store, self.workspace, observed_text="SECTION 3 / A-501",
            page_id=other_page, source_id=other_source["id"])
        self.assertEqual(there["tier"], "confirmed_project")

    def test_h_a_generic_reading_cannot_outrank_a_confirmed_project_meaning(self):
        confirmed = self._propose("precedence-confirmed",
                                  proposed_meaning="detail callout to A-501")
        self.store.decide_legend_item(
            self.workspace, confirmed["id"], action=LEGEND_STATUS_CONFIRMED,
            actor="reviewer", scope_kind=LEGEND_SCOPE_PROJECT)
        self._propose("precedence-generic",
                      proposed_meaning="generic section symbol",
                      interpretation_method="generic_symbol_library")
        resolved = lou.resolve_meaning(
            self.store, self.workspace, observed_text="SECTION 3 / A-501",
            source_id=self.source["id"], page_id=self.page_id)
        self.assertEqual(resolved["meaning"], "detail callout to A-501")

    def test_h_legend_evidence_is_found_where_a_legend_actually_lives(self):
        self._sheet("E0 - GENERAL NOTES AND LEGEND.pdf", "E0")
        found = lou.find_legend_evidence(self.store, self.workspace)
        self.assertTrue(found)
        self.assertIn(found[0]["kind"], ("legend", "general_notes"))

    def test_h_no_legend_means_reduced_authority_not_refusal(self):
        readiness = lou.legend_first_readiness(
            self.store, self.workspace, self.source["id"])
        self.assertEqual(readiness["state"], "no_legend_evidence")
        self.assertFalse(readiness["may_interpret_authoritatively"])
        # Ingestion is NOT blocked - only the authority of the reading is capped.
        self.assertIsNotNone(readiness["confidence_ceiling"])


# ---------------------------------------------------------------------------
# I - INFORMATIVE is semantically usable and never measurable
# ---------------------------------------------------------------------------

class InformativeViewTests(_DrawingBase):

    def _view(self, scale_state, **kw):
        params = dict(
            source_id=self.source["id"],
            page_structural_unit_id=self.page_id,
            region={"x": 0, "y": 0, "width": SHEET_W, "height": SHEET_H},
            derivation_reason="whole-sheet plan view",
            scale_state=scale_state, actor="GO")
        params.update(kw)
        return self.store.create_derived_view(self.workspace, **params)

    def test_i_an_informative_view_still_supports_semantic_work(self):
        from services import derived_view as dv
        view = self._view("informative")
        allowed, _reason = dv.may_use_semantically(view)
        self.assertTrue(allowed)

    def test_i_an_informative_view_refuses_measurement(self):
        from services import derived_view as dv
        view = self._view("informative")
        allowed, reason = dv.may_measure(view)
        self.assertFalse(allowed)
        self.assertTrue(reason)

    def test_i_a_quantitative_view_permits_both(self):
        from services import derived_view as dv
        # A QUANTITATIVE view must carry the evidence for its scale - the store
        # refuses one without, and that refusal is the point.
        view = self._view("quantitative", scale_value=50.0,
                          scale_notation="1:50",
                          scale_method="stated_on_sheet_and_checked_against_grid")
        self.assertTrue(dv.may_use_semantically(view)[0])
        self.assertTrue(dv.may_measure(view)[0])

    def test_i_a_quantitative_state_without_evidence_is_refused_outright(self):
        with self.assertRaises(CaseWorkspaceError):
            self._view("quantitative")


# ---------------------------------------------------------------------------
# J / K - boundaries and edge behaviour
# ---------------------------------------------------------------------------

class BoundaryTests(_DrawingBase):

    def test_j_both_sides_of_a_boundary_are_preserved(self):
        condition = self._condition("exterior wall at window head")
        boundary = self._boundary(
            condition["id"],
            side_a={"material": "brick veneer", "thickness_mm": 90},
            side_b={"material": "aluminium window frame"})
        stored = self.store.condition_boundaries_for(
            self.workspace, condition_id=condition["id"])[0]
        self.assertEqual(stored["side_a"]["material"], "brick veneer")
        self.assertEqual(stored["side_b"]["material"], "aluminium window frame")
        self.assertEqual(boundary["boundary_evidence"],
                         [BOUNDARY_EVIDENCE_MATERIAL_CHANGE])

    def test_j_a_boundary_with_no_evidence_is_refused(self):
        condition = self._condition("wall")
        with self.assertRaises(CaseWorkspaceError):
            self._boundary(condition["id"], boundary_evidence=[])

    def test_j_a_one_sided_boundary_is_visible_as_one_sided(self):
        condition = self._condition("wall")
        self._boundary(condition["id"], side_a={"material": "brick"})
        report = dcond.boundary_report(self.store, self.workspace, condition["id"])
        self.assertFalse(report["boundaries"][0]["both_sides_recorded"])

    def test_k_a_continuity_layer_given_a_cut_returns_review_needed(self):
        # The failure this catches: "cut" is a fine answer for brick coursing
        # and a meaningless one for an air barrier, where the real question is
        # what happens to the FUNCTION.
        condition = self._condition("air barrier at slab edge")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            edge_behavior=EDGE_BEHAVIOR_CUT,
            boundary_evidence=[BOUNDARY_EVIDENCE_MEMBRANE_TRANSITION])
        state = dcond.edge_behavior_state(boundary)
        self.assertEqual(state["state"], CONTINUITY_STATE_REVIEW_NEEDED)
        self.assertIn("continuity layer", state["reason"])

    def test_k_a_discrete_edge_given_a_cut_is_coherent(self):
        condition = self._condition("brick coursing at opening")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_DISCRETE,
            edge_behavior=EDGE_BEHAVIOR_CUT)
        self.assertNotEqual(dcond.edge_behavior_state(boundary)["state"],
                            CONTINUITY_STATE_REVIEW_NEEDED)

    def test_k_a_stopped_layer_with_no_stated_transfer_is_review_needed(self):
        condition = self._condition("air barrier at parapet")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            edge_behavior=EDGE_BEHAVIOR_OVERLAP,
            functional_layers=[{"function": FUNCTION_AIR_CONTROL,
                                "intended": True, "continues": False}])
        layers = dcond.functional_layer_continuity(boundary)
        self.assertEqual(layers[0]["state"], CONTINUITY_STATE_REVIEW_NEEDED)

    def test_k_a_stated_and_evidenced_transfer_is_accepted(self):
        condition = self._condition("air barrier to window frame")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            edge_behavior=EDGE_BEHAVIOR_OVERLAP,
            functional_layers=[{
                "function": FUNCTION_AIR_CONTROL, "intended": True,
                "continues": False, "transfer_mechanism": "sealed membrane lap",
                "evidence": "detail 4/A-501 note 3"}])
        layers = dcond.functional_layer_continuity(boundary)
        self.assertEqual(layers[0]["state"], CONTINUITY_STATE_TRANSFERRED)

    def test_k_continuity_asserted_without_evidence_is_not_accepted(self):
        # A drawn termination is not valid merely because it is drawn.
        condition = self._condition("water control layer")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            edge_behavior=EDGE_BEHAVIOR_OVERLAP,
            functional_layers=[{"function": FUNCTION_WATER_CONTROL,
                                "intended": True, "continues": True}])
        self.assertEqual(dcond.functional_layer_continuity(boundary)[0]["state"],
                         CONTINUITY_STATE_REVIEW_NEEDED)

    def test_k_no_repair_is_ever_proposed(self):
        condition = self._condition("air barrier at parapet")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            functional_layers=[{"function": FUNCTION_AIR_CONTROL,
                                "intended": True, "continues": False}])
        for row in dcond.functional_layer_continuity(boundary):
            self.assertFalse(row["repair_proposed"])

    def test_a_threshold_that_changes_responsibility_outranks_a_material_change(self):
        condition = self._condition("existing to new interface")
        high = self._boundary(
            condition["id"],
            threshold_kinds=[THRESHOLD_KIND_RESPONSIBILITY_CHANGE,
                             THRESHOLD_KIND_CHANGE])
        routine = self._boundary(
            condition["id"], threshold_kinds=[THRESHOLD_KIND_CHANGE])
        self.assertEqual(dcond.threshold_priority(high)["priority"], "high")
        self.assertEqual(dcond.threshold_priority(routine)["priority"], "routine")

    def test_an_unconventional_form_is_never_critiqued_only_costed(self):
        condition = self._condition(
            "faceted bay projection", expression_class="design_choice")
        boundary = self._boundary(
            condition["id"], edge_class=EDGE_CLASS_CONTINUITY,
            functional_layers=[{"function": FUNCTION_WATER_CONTROL,
                                "intended": True, "continues": False}])
        outcome = dcond.performance_consequence(condition, boundary)
        self.assertIsNone(outcome["aesthetic_critique"])
        self.assertTrue(outcome["physical_consequences"])


# ---------------------------------------------------------------------------
# Hierarchical membership - island / branch / mainland
# ---------------------------------------------------------------------------

class MembershipTests(_DrawingBase):

    def _chain(self):
        system = self._condition("architectural building system",
                                 kind=CONDITION_KIND_SYSTEM)
        envelope = self._condition("building envelope", kind=CONDITION_KIND_SYSTEM,
                                   parent_condition_id=system["id"])
        wall = self._condition("exterior wall assembly", kind=CONDITION_KIND_ASSEMBLY,
                               parent_condition_id=envelope["id"])
        perimeter = self._condition("window perimeter condition",
                                    kind=CONDITION_KIND_INTERFACE
                                    if False else CONDITION_KIND_ASSEMBLY,
                                    parent_condition_id=wall["id"])
        head = self._condition("window head detail", kind=CONDITION_KIND_DETAIL,
                               parent_condition_id=perimeter["id"])
        return system, envelope, wall, perimeter, head

    def test_local_detail_walks_up_to_its_system(self):
        system, _envelope, _wall, _perimeter, head = self._chain()
        chain = dcond.membership_chain(self.store, self.workspace, head["id"])
        self.assertEqual(chain[0]["proposed_meaning"], "window head detail")
        self.assertEqual(chain[-1]["id"], system["id"])
        self.assertEqual(len(chain), 5)

    def test_the_hierarchy_is_not_flattened(self):
        _s, _e, _w, perimeter, head = self._chain()
        self.assertEqual(
            dcond.membership_chain(self.store, self.workspace, head["id"])[1]["id"],
            perimeter["id"])

    def test_siblings_share_a_parent_not_a_meaning(self):
        _s, _e, _w, perimeter, head = self._chain()
        sill = self._condition("window sill detail", kind=CONDITION_KIND_DETAIL,
                               parent_condition_id=perimeter["id"])
        siblings = dcond.siblings_of(self.store, self.workspace, head["id"])
        self.assertEqual([row["id"] for row in siblings], [sill["id"]])

    def test_descendants_reach_every_level_below(self):
        system, _e, _w, _p, head = self._chain()
        found = dcond.descendants_of(self.store, self.workspace, system["id"])
        self.assertIn(head["id"], [row["id"] for row in found])

    def test_a_circular_parent_chain_is_reported_not_followed(self):
        first = self._condition("a")
        second = self._condition("b", parent_condition_id=first["id"])
        stored = self.store._find(self.workspace.drawing_conditions, first["id"])
        stored["parent_condition_id"] = second["id"]
        self.store.save(self.workspace)
        with self.assertRaises(dcond.DrawingConditionError):
            dcond.membership_chain(self.store, self.workspace, first["id"])

    def test_a_parent_from_another_project_is_refused(self):
        other = self.store.get_or_create("test-project-di-other")
        other_source, other_page = self._sheet("X.pdf", "X", workspace=other)
        foreign = self.store.record_drawing_condition(
            other, source_id=other_source["id"],
            page_structural_unit_id=other_page, region={},
            condition_kind=CONDITION_KIND_DETAIL, proposed_meaning="foreign",
            interpretation_method="region_reading", actor="GO")
        with self.assertRaises(CaseWorkspaceError):
            self._condition("mine", parent_condition_id=foreign["id"])


# ---------------------------------------------------------------------------
# L / M - host materials and load paths
# ---------------------------------------------------------------------------

class SupportTests(_DrawingBase):

    def test_l_a_dependent_material_with_no_host_returns_review_needed(self):
        finish = self._condition("adhered stone veneer", kind=CONDITION_KIND_ELEMENT,
                                 support_dependency=SUPPORT_DEPENDENCY_DEPENDENT)
        state = dcond.host_support_state(self.store, self.workspace, finish["id"])
        self.assertEqual(state["state"], CONTINUITY_STATE_REVIEW_NEEDED)
        self.assertIn("no recorded host", state["reason"])

    def test_l_a_dependent_material_with_a_recorded_host_is_hosted(self):
        backing = self._condition("concrete block backup",
                                  kind=CONDITION_KIND_ELEMENT,
                                  support_dependency=SUPPORT_DEPENDENCY_SELF_SUPPORTING)
        finish = self._condition("adhered stone veneer", kind=CONDITION_KIND_ELEMENT,
                                 support_dependency=SUPPORT_DEPENDENCY_DEPENDENT)
        self.store.record_relationship(
            self.workspace, "drawing_condition", finish["id"],
            "drawing_condition", backing["id"], RELATIONSHIP_TYPE_HOSTED_BY,
            created_by="GO", reason="veneer adhered to block backup")
        state = dcond.host_support_state(self.store, self.workspace, finish["id"])
        self.assertEqual(state["state"], "hosted")

    def test_l_a_host_pointing_at_nothing_is_not_a_host(self):
        finish = self._condition("adhered stone veneer", kind=CONDITION_KIND_ELEMENT,
                                 support_dependency=SUPPORT_DEPENDENCY_DEPENDENT)
        self.store.record_relationship(
            self.workspace, "drawing_condition", finish["id"],
            "drawing_condition", "no-such-condition", RELATIONSHIP_TYPE_HOSTED_BY,
            created_by="GO")
        self.assertEqual(
            dcond.host_support_state(self.store, self.workspace,
                                     finish["id"])["state"],
            CONTINUITY_STATE_REVIEW_NEEDED)

    def test_l_an_unstated_dependency_is_a_question_not_an_assumption(self):
        element = self._condition("ceiling", kind=CONDITION_KIND_ELEMENT)
        state = dcond.host_support_state(self.store, self.workspace, element["id"])
        self.assertEqual(state["state"], CONTINUITY_STATE_REVIEW_NEEDED)

    def test_m_touching_regions_do_not_make_a_load_path(self):
        # The inference this system must never make. Both regions abut exactly.
        lintel = self._condition("steel lintel", kind=CONDITION_KIND_ELEMENT,
                                 region={"x": 40, "y": 100, "width": 120, "height": 20})
        wall = self._condition("masonry wall", kind=CONDITION_KIND_ELEMENT,
                               region={"x": 40, "y": 120, "width": 120, "height": 200},
                               support_dependency=SUPPORT_DEPENDENCY_SELF_SUPPORTING)
        self.assertTrue(dcond.spatially_adjacent(lintel["region"], wall["region"]))
        state = dcond.structural_admission_state(
            self.store, self.workspace, lintel["id"])
        self.assertEqual(state["state"], STRUCTURAL_STATE_REVIEW_NEEDED)
        self.assertIn("adjacency is not a load path", state["reason"])

    def test_m_a_recorded_bearing_edge_does_make_a_path(self):
        wall = self._condition("masonry wall", kind=CONDITION_KIND_ELEMENT,
                               support_dependency=SUPPORT_DEPENDENCY_SELF_SUPPORTING)
        lintel = self._condition("steel lintel", kind=CONDITION_KIND_ELEMENT)
        self.store.record_relationship(
            self.workspace, "drawing_condition", lintel["id"],
            "drawing_condition", wall["id"], RELATIONSHIP_TYPE_BEARS_ON,
            created_by="GO", reason="bearing shown in detail 2/S-201")
        state = dcond.structural_admission_state(
            self.store, self.workspace, lintel["id"])
        self.assertEqual(state["state"], STRUCTURAL_STATE_SUPPORTED)

    def test_m_a_path_ending_at_an_unsupported_dependent_is_incomplete(self):
        hanger = self._condition("hanger", kind=CONDITION_KIND_ELEMENT,
                                 support_dependency=SUPPORT_DEPENDENCY_DEPENDENT)
        ceiling = self._condition("suspended ceiling", kind=CONDITION_KIND_ELEMENT)
        self.store.record_relationship(
            self.workspace, "drawing_condition", ceiling["id"],
            "drawing_condition", hanger["id"], RELATIONSHIP_TYPE_BEARS_ON,
            created_by="GO")
        state = dcond.structural_admission_state(
            self.store, self.workspace, ceiling["id"])
        self.assertEqual(state["state"], STRUCTURAL_STATE_PATH_INCOMPLETE)

    def test_m_adequacy_is_never_claimed(self):
        wall = self._condition("masonry wall", kind=CONDITION_KIND_ELEMENT,
                               support_dependency=SUPPORT_DEPENDENCY_SELF_SUPPORTING)
        lintel = self._condition("steel lintel", kind=CONDITION_KIND_ELEMENT)
        self.store.record_relationship(
            self.workspace, "drawing_condition", lintel["id"],
            "drawing_condition", wall["id"], RELATIONSHIP_TYPE_BEARS_ON,
            created_by="GO")
        state = dcond.structural_admission_state(
            self.store, self.workspace, lintel["id"])
        self.assertFalse(state["adequacy_claimed"])
        self.assertIn("engineer", state["adequacy_note"])


# ---------------------------------------------------------------------------
# N - the disciplines stay apart
# ---------------------------------------------------------------------------

class DisciplineTests(_DrawingBase):

    def _both(self, condition_id, architectural, structural, **kw):
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition_id, discipline="architectural",
            assumption=architectural, actor="arch", **kw.get("arch", {}))
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition_id, discipline="structural",
            assumption=structural, actor="eng", **kw.get("eng", {}))

    def test_n_conflicting_assumptions_are_both_preserved(self):
        condition = self._condition("transfer beam at grid C")
        self._both(condition["id"],
                   "beam depth 600mm, soffit at 2700",
                   "beam depth 900mm, soffit at 2400",
                   arch={"evidence": "A-201 section"},
                   eng={"evidence": "S-301 framing"})
        outcome = align.reconcile(self.store, self.workspace, condition["id"])
        self.assertEqual(outcome["state"], ALIGNMENT_STATE_CONFLICT)
        self.assertEqual(len(outcome["assumptions"]), 2)
        self.assertEqual(sorted(outcome["disciplines"]),
                         ["architectural", "structural"])

    def test_n_neither_discipline_is_declared_correct(self):
        condition = self._condition("transfer beam at grid C")
        self._both(condition["id"], "600 deep", "900 deep",
                   arch={"evidence": "A-201"}, eng={"evidence": "S-301"})
        outcome = align.reconcile(self.store, self.workspace, condition["id"])
        self.assertIn("professional", outcome["professional_authority"].lower())
        self.assertIsNotNone(outcome["coordination_question"])
        for assumption in outcome["assumptions"]:
            self.assertIsNone(assumption["resolved_by"])

    def test_n_agreement_is_derived_not_asserted(self):
        condition = self._condition("slab edge")
        self._both(condition["id"], "slab edge at grid line",
                   "slab edge at grid line",
                   arch={"evidence": "A-101"}, eng={"evidence": "S-101"})
        self.assertEqual(
            align.reconcile(self.store, self.workspace,
                            condition["id"])["state"],
            ALIGNMENT_STATE_ALIGNED)

    def test_n_one_discipline_alone_is_not_coordination(self):
        condition = self._condition("stair framing")
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition["id"],
            discipline="architectural", assumption="open riser stair",
            actor="arch")
        outcome = align.reconcile(self.store, self.workspace, condition["id"])
        self.assertEqual(outcome["state"], ALIGNMENT_STATE_UNRECONCILED)

    def test_n_unevidenced_difference_is_a_mismatch_not_a_conflict(self):
        # These need different coordination responses, so they are different
        # states rather than one "disagreement".
        condition = self._condition("facade support")
        self._both(condition["id"], "supported at each floor",
                   "supported at alternate floors", arch={"evidence": "A-401"})
        self.assertEqual(
            align.reconcile(self.store, self.workspace,
                            condition["id"])["state"],
            ALIGNMENT_STATE_ASSUMPTION_MISMATCH)

    def test_n_working_from_a_superseded_background_reads_as_stale(self):
        background, _page = self._sheet("A-101-rev2.pdf", "A-101", revision="2")
        condition = self._condition("column grid at lobby")
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition["id"],
            discipline="architectural", assumption="grid at 7200",
            actor="arch", evidence="A-101")
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition["id"],
            discipline="structural", assumption="grid at 6800", actor="eng",
            evidence="S-101", informed_by_source_id=background["id"],
            informed_by_revision="1")
        outcome = align.reconcile(self.store, self.workspace, condition["id"])
        self.assertEqual(outcome["state"],
                         ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT)
        self.assertEqual(outcome["stale_inputs"][0]["detail"]["current_revision"],
                         "2")

    def test_n_an_unknown_revision_is_not_reported_as_stale(self):
        background, _page = self._sheet("A-104.pdf", "A-104")
        condition = self._condition("grid")
        self._both(condition["id"], "grid at 7200", "grid at 6800",
                   arch={"evidence": "A-104"},
                   eng={"evidence": "S-104",
                        "informed_by_source_id": background["id"]})
        outcome = align.reconcile(self.store, self.workspace, condition["id"])
        self.assertNotEqual(outcome["state"],
                            ALIGNMENT_STATE_STALE_CROSS_DISCIPLINE_INPUT)

    def test_n_only_a_professional_settles_it(self):
        condition = self._condition("transfer beam")
        self._both(condition["id"], "600 deep", "900 deep",
                   arch={"evidence": "A-201"}, eng={"evidence": "S-301"})
        for assumption in self.store.discipline_assumptions_for(
                self.workspace, condition_id=condition["id"]):
            self.store.resolve_discipline_assumption(
                self.workspace, assumption["id"], actor="engineer-of-record",
                note="900 confirmed; architectural soffit revised.")
        self.assertEqual(
            align.reconcile(self.store, self.workspace,
                            condition["id"])["state"],
            ALIGNMENT_STATE_RESOLVED_BY_PROFESSIONAL)

    def test_n_a_disposition_must_say_what_was_decided(self):
        condition = self._condition("transfer beam")
        self.store.record_discipline_assumption(
            self.workspace, condition_id=condition["id"],
            discipline="structural", assumption="900 deep", actor="eng")
        assumption = self.store.discipline_assumptions_for(
            self.workspace, condition_id=condition["id"])[0]
        with self.assertRaises(CaseWorkspaceError):
            self.store.resolve_discipline_assumption(
                self.workspace, assumption["id"], actor="eng", note="  ")

    def test_the_unreconciled_sweep_finds_where_nobody_has_looked(self):
        aligned = self._condition("slab edge")
        self._both(aligned["id"], "same", "same",
                   arch={"evidence": "A"}, eng={"evidence": "S"})
        self._condition("unexamined interface")
        rows = align.unreconciled_interfaces(
            self.store, self.workspace, source_id=self.source["id"])
        meanings = {row["condition_id"] for row in rows}
        self.assertNotIn(aligned["id"], meanings)
        self.assertTrue(rows)


# ---------------------------------------------------------------------------
# O / P - isolation and evidence integrity
# ---------------------------------------------------------------------------

class IsolationAndIntegrityTests(_DrawingBase):

    def test_o_conditions_never_leak_across_projects(self):
        other = self.store.get_or_create("test-project-di-neighbour")
        other_source, other_page = self._sheet("N.pdf", "N", workspace=other)
        self.store.record_drawing_condition(
            other, source_id=other_source["id"],
            page_structural_unit_id=other_page, region={},
            condition_kind=CONDITION_KIND_DETAIL,
            proposed_meaning="neighbour condition",
            interpretation_method="region_reading", actor="GO")
        self._condition("my condition")

        mine = self.store.drawing_conditions_for(self.workspace)
        theirs = self.store.drawing_conditions_for(other)
        self.assertEqual([row["proposed_meaning"] for row in mine],
                         ["my condition"])
        self.assertEqual([row["proposed_meaning"] for row in theirs],
                         ["neighbour condition"])
        self.assertTrue(all(row["project_id"] == self.workspace.project_id
                            for row in mine))

    def test_o_a_boundary_cannot_be_hung_on_another_projects_condition(self):
        other = self.store.get_or_create("test-project-di-neighbour-2")
        other_source, other_page = self._sheet("N2.pdf", "N2", workspace=other)
        foreign = self.store.record_drawing_condition(
            other, source_id=other_source["id"],
            page_structural_unit_id=other_page, region={},
            condition_kind=CONDITION_KIND_DETAIL, proposed_meaning="foreign",
            interpretation_method="region_reading", actor="GO")
        with self.assertRaises(CaseWorkspaceError):
            self._boundary(foreign["id"])

    def test_o_an_assumption_cannot_be_attached_across_projects(self):
        other = self.store.get_or_create("test-project-di-neighbour-3")
        other_source, other_page = self._sheet("N3.pdf", "N3", workspace=other)
        foreign = self.store.record_drawing_condition(
            other, source_id=other_source["id"],
            page_structural_unit_id=other_page, region={},
            condition_kind=CONDITION_KIND_DETAIL, proposed_meaning="foreign",
            interpretation_method="region_reading", actor="GO")
        with self.assertRaises(CaseWorkspaceError):
            self.store.record_discipline_assumption(
                self.workspace, condition_id=foreign["id"],
                discipline="structural", assumption="x", actor="eng")

    def test_p_reading_a_drawing_never_changes_the_source_file(self):
        path = Path(self.source["file_path"])
        before = path.read_bytes()
        condition = self._condition("wall")
        self._boundary(condition["id"])
        lou.snapshot_region(self.raw, 0, (0, 0, SHEET_W, SHEET_H),
                            str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), "integrity")
        dcond.boundary_report(self.store, self.workspace, condition["id"])
        self.assertEqual(path.read_bytes(), before)

    def test_p_the_recorded_file_hash_is_untouched_by_interpretation(self):
        before = self.store._find(self.workspace.sources,
                                  self.source["id"]).get("file_hash")
        condition = self._condition("wall")
        self.store.decide_drawing_observation(
            self.workspace, condition["id"], action="confirmed", actor="reviewer")
        after = self.store._find(self.workspace.sources,
                                 self.source["id"]).get("file_hash")
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# Decisions append; current state never launders history
# ---------------------------------------------------------------------------

class DecisionHistoryTests(_DrawingBase):

    def test_an_override_never_rewrites_what_go_proposed(self):
        condition = self._condition("brick veneer")
        self.store.decide_drawing_observation(
            self.workspace, condition["id"], action="overridden", actor="reviewer",
            meaning="precast panel")
        stored = self.store._find(self.workspace.drawing_conditions,
                                  condition["id"])
        self.assertEqual(stored["proposed_meaning"], "brick veneer")
        self.assertEqual(stored["decisions"][-1]["meaning"], "precast panel")

    def test_changing_your_mind_twice_leaves_three_readable_states(self):
        condition = self._condition("brick veneer")
        self.store.decide_drawing_observation(
            self.workspace, condition["id"], action="overridden",
            actor="reviewer", meaning="precast panel")
        self.store.decide_drawing_observation(
            self.workspace, condition["id"], action="overridden",
            actor="reviewer", meaning="cast stone")
        stored = self.store._find(self.workspace.drawing_conditions,
                                  condition["id"])
        self.assertEqual(stored["proposed_meaning"], "brick veneer")
        self.assertEqual([d["meaning"] for d in stored["decisions"]],
                         ["precast panel", "cast stone"])

    def test_an_override_must_say_what_it_actually_is(self):
        condition = self._condition("brick veneer")
        with self.assertRaises(CaseWorkspaceError):
            self.store.decide_drawing_observation(
                self.workspace, condition["id"], action="overridden",
                actor="reviewer")

    def test_one_decision_path_serves_conditions_and_boundaries(self):
        condition = self._condition("wall")
        boundary = self._boundary(condition["id"])
        self.store.decide_drawing_observation(
            self.workspace, boundary["id"], action="confirmed", actor="reviewer")
        stored = self.store._find(self.workspace.condition_boundaries,
                                  boundary["id"])
        self.assertEqual(stored["status"], "confirmed")


if __name__ == "__main__":
    unittest.main()
