"""
CLAUDE-SECTION-CUT-FAMILY-01 - few human confirmations, many governed instances.

The assertions that carry weight here are about ECONOMY and about REFUSAL.

Economy, because the whole justification for the mechanism is arithmetic: a
sheet carrying the same section cut many times must ask a person once and store
a handful of crops, not one of each per occurrence. A test that only proved the
clustering worked would not prove the saving was real, so the snapshot count and
the confirmation count are asserted directly.

Refusal, because the dangerous failure is the quiet one. A mark that does not
actually belong in the family must come back to a human rather than inherit a
meaning that is almost right - and the per-instance facts a section cut carries
(which way it points, whether it is mirrored, what it references) must survive
membership untouched, since those decide WHICH view is referenced and the family
never claimed to know that.

The correction worth stating: a DIFFERENT candidate target is deliberately not a
material difference. Two section cuts pointing at different views are exactly
what a family of section cuts looks like; treating that as non-conformance would
flag every member and defeat the mechanism entirely.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services import legend_of_understanding as lou
from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    FAMILY_REPRESENTATIVE_LIMIT,
    FAMILY_ROLE_INSTANCE,
    FAMILY_ROLE_REPRESENTATIVE,
    LEGEND_KIND_NORTH_ARROW,
    LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_SCOPE_PROJECT,
    LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED,
    LEGEND_STATUS_INFORMATIVE,
    LEGEND_STATUS_OVERRIDDEN,
    LEGEND_STATUS_REVIEW_NEEDED,
    SOURCE_KIND_DRAWING,
)
from services.governance import GovernanceLog

SHEET_W, SHEET_H = 612.0, 460.0


def _sheet_pdf() -> bytes:
    """A rasterised sheet, so crops are produced from a real image."""
    drawn = pymupdf.open()
    page = drawn.new_page(width=SHEET_W, height=SHEET_H)
    page.insert_text((40, 60), "E1 POWER PLAN", fontsize=12)
    for row, label in enumerate(("1/E2", "2/E2", "3/E2", "4/E2", "5/E2")):
        page.insert_text((40, 120 + row * 40), label, fontsize=11)
    rasterised = pymupdf.open()
    pix = drawn.load_page(0).get_pixmap(dpi=96)
    out = rasterised.new_page(width=SHEET_W, height=SHEET_H)
    out.insert_image(pymupdf.Rect(0, 0, SHEET_W, SHEET_H), stream=pix.tobytes("png"))
    raw = rasterised.tobytes()
    drawn.close(); rasterised.close()
    return raw


class _FamilyBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_family_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-family")
        self.raw = _sheet_pdf()
        self.crops_taken = []

        path = self.tmp_dir / "E1.pdf"
        path.write_bytes(self.raw)
        self.source = self.store.add_source(
            self.workspace, name="E1.pdf", file_path=str(path),
            kind=SOURCE_KIND_DRAWING, document_id="E1", actor="tester")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, self.source["id"],
            [{"index": 0, "label": "E1 SHEET", "width": SHEET_W, "height": SHEET_H,
              "source_rotation": 0, "metadata": {}}], actor="tester")
        self.page_id = registered["structural_unit_ids"][0]

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    # -- candidates ------------------------------------------------------
    def _cut(self, label, direction, **kw):
        """One observed section-cut mark, before any clustering."""
        candidate = {
            "proposed_kind": LEGEND_KIND_SECTION_REFERENCE,
            "observed_text": label,
            "region": {"x": 40, "y": 120, "width": 44, "height": 44},
            "section_line_direction_degrees": direction,
            "view_direction_degrees": (direction + 90) % 360,
            "instance_mirrored": False,
            "instance_rotation_degrees": 0.0,
            "candidate_target_reference": "E2",
            "nearby_label": label,
        }
        candidate.update(kw)
        return candidate

    def _cuts(self, count=6):
        return [self._cut("%d/E2" % (n + 1), n * 40) for n in range(count)]

    def _snapshot_for(self, member):
        key = "crop-%s" % (member.get("observed_text") or "x").replace("/", "-")
        self.crops_taken.append(key)
        return lou.snapshot_region(
            self.raw, 0, (30, 100, 300, 160),
            str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), key)

    def _register(self, candidates=None, **kw):
        families = lou.cluster_candidates(candidates or self._cuts())
        params = dict(
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            actor="GO", proposed_meaning="section reference to E2",
            interpretation_method="region_ocr_pattern",
            snapshot_for=self._snapshot_for, confidence=0.55,
            governance_log=self.gov)
        params.update(kw)
        return lou.register_family(self.store, self.workspace, families[0], **params)

    def _register_family_dict(self, family, **kw):
        params = dict(
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            actor="GO", proposed_meaning="section reference to E2",
            interpretation_method="region_ocr_pattern",
            snapshot_for=self._snapshot_for, confidence=0.55,
            governance_log=self.gov)
        params.update(kw)
        return lou.register_family(self.store, self.workspace, family, **params)

    def _items(self, **kw):
        return self.store.legend_items_for(self.workspace, **kw)


class ClusteringTests(_FamilyBase):
    """A. Visually equivalent marks become ONE family, not one row each."""

    def test_repeated_section_cuts_collapse_into_a_single_family(self):
        families = lou.cluster_candidates(self._cuts(6))
        self.assertEqual(len(families), 1)
        self.assertEqual(families[0]["member_count"], 6)

    def test_different_labels_pointing_at_different_views_stay_one_family(self):
        # The correction this whole rule turns on: differing targets are the
        # NORMAL case for section cuts, not evidence of a different symbol.
        candidates = [self._cut("1/E2", 0, candidate_target_reference="E2"),
                      self._cut("2/E5", 40, candidate_target_reference="E5")]
        self.assertEqual(len(lou.cluster_candidates(candidates)), 1)

    def test_a_genuinely_different_symbol_forms_its_own_family(self):
        candidates = self._cuts(3) + [{
            "proposed_kind": LEGEND_KIND_NORTH_ARROW, "observed_text": "N",
            "region": {"x": 500, "y": 40, "width": 60, "height": 60}}]
        families = lou.cluster_candidates(candidates)
        self.assertEqual(len(families), 2)
        self.assertEqual(
            {f["proposed_kind"] for f in families},
            {LEGEND_KIND_SECTION_REFERENCE, LEGEND_KIND_NORTH_ARROW})

    def test_label_grammar_not_label_value_decides_membership(self):
        self.assertEqual(lou._label_shape("A/E2"), lou._label_shape("B/E12"))
        self.assertNotEqual(lou._label_shape("3/E2"), lou._label_shape("N"))

    def test_clustering_is_deterministic(self):
        candidates = self._cuts(6)
        first = lou.cluster_candidates(candidates)
        second = lou.cluster_candidates(candidates)
        self.assertEqual([f["signature"] for f in first],
                         [f["signature"] for f in second])
        self.assertEqual(first[0]["representative_indexes"],
                         second[0]["representative_indexes"])


    def test_rotated_and_mirrored_marks_share_one_family(self):
        # Section 6: family equivalence must survive rotation, mirroring and
        # scale. None of those change what a mark MEANS.
        candidates = [
            self._cut("1/E2", 0, instance_rotation_degrees=0.0,
                      instance_mirrored=False),
            self._cut("2/E2", 90, instance_rotation_degrees=90.0,
                      instance_mirrored=False),
            self._cut("3/E2", 180, instance_rotation_degrees=180.0,
                      instance_mirrored=True),
            self._cut("4/E2", 270, instance_rotation_degrees=270.0,
                      instance_mirrored=True,
                      region={"x": 40, "y": 120, "width": 132, "height": 132}),
        ]
        families = lou.cluster_candidates(candidates)
        self.assertEqual(len(families), 1)
        self.assertEqual(families[0]["member_count"], 4)

    def test_a_ninety_degree_rotation_does_not_split_a_rectangular_family(self):
        upright = self._cut("1/E2", 0, region={"x": 0, "y": 0, "width": 40, "height": 160})
        turned = self._cut("2/E2", 90, region={"x": 0, "y": 0, "width": 160, "height": 40})
        self.assertEqual(len(lou.cluster_candidates([upright, turned])), 1)



class RepresentativeTests(_FamilyBase):
    """B. A SMALL representative set - and the saving must be real."""

    def test_only_a_few_representatives_are_selected(self):
        families = lou.cluster_candidates(self._cuts(20))
        self.assertEqual(len(families[0]["representatives"]),
                         FAMILY_REPRESENTATIVE_LIMIT)

    def test_representatives_are_spread_not_the_first_few(self):
        # A reviewer shown three identical crops cannot tell whether the family
        # is uniform. The spread is what makes the sample informative.
        families = lou.cluster_candidates(self._cuts(9))
        directions = [m["section_line_direction_degrees"]
                      for m in families[0]["representatives"]]
        self.assertEqual(len(set(directions)), len(directions))
        self.assertGreater(max(directions) - min(directions), 100)

    def test_a_small_family_uses_every_member_as_a_representative(self):
        families = lou.cluster_candidates(self._cuts(2))
        self.assertEqual(len(families[0]["representatives"]), 2)

    def test_only_representatives_are_cropped(self):
        result = self._register(self._cuts(12))
        self.assertEqual(len(self.crops_taken), FAMILY_REPRESENTATIVE_LIMIT)
        self.assertEqual(result["snapshots_taken"], FAMILY_REPRESENTATIVE_LIMIT)
        self.assertEqual(result["snapshots_avoided"],
                         12 - FAMILY_REPRESENTATIVE_LIMIT)

    def test_a_representative_without_a_crop_is_refused(self):
        # The snapshot exception is for INSTANCES only. A representative is
        # precisely the image the human is being asked to judge.
        with self.assertRaises(lou.LegendError):
            self._register(self._cuts(4), snapshot_for=lambda member: None)

    def test_representative_choice_survives_serialisation(self):
        # Object identity does not survive a round trip through storage, so the
        # choice is positional. A family that forgot which crops a human saw
        # would be a family nobody could audit.
        import json
        family = lou.cluster_candidates(self._cuts(9))[0]
        expected = [family["members"][i]["observed_text"]
                    for i in family["representative_indexes"]]
        # Deliberately WITHOUT a `representatives` list - only the positions
        # survive, which is exactly the state a stored family comes back in.
        round_tripped = json.loads(json.dumps({
            "members": family["members"],
            "representative_indexes": family["representative_indexes"],
            "proposed_kind": family["proposed_kind"],
        }))
        self._register_family_dict(round_tripped)
        cropped = [c.replace("crop-", "").replace("-", "/")
                   for c in self.crops_taken]
        self.assertEqual(cropped, expected)


class InstanceIntegrityTests(_FamilyBase):
    """C. Membership shares meaning and nothing else."""

    def test_per_instance_variance_is_preserved_verbatim(self):
        candidates = [
            self._cut("1/E2", 0, candidate_target_reference="E2",
                      instance_mirrored=False),
            self._cut("2/E5", 180, candidate_target_reference="E5",
                      instance_mirrored=True, instance_rotation_degrees=90.0),
        ]
        self._register(candidates)
        stored = sorted(self._items(), key=lambda i: i["observed_text"])
        self.assertEqual([i["candidate_target_reference"] for i in stored],
                         ["E2", "E5"])
        self.assertEqual([i["instance_mirrored"] for i in stored], [False, True])
        self.assertEqual([i["section_line_direction_degrees"] for i in stored],
                         [0, 180])
        self.assertEqual(stored[1]["instance_rotation_degrees"], 90.0)

    def test_instances_carry_the_family_and_their_role(self):
        result = self._register(self._cuts(8))
        family_id = result["family_id"]
        self.assertEqual(
            len(self._items(family_id=family_id,
                            family_role=FAMILY_ROLE_REPRESENTATIVE)),
            FAMILY_REPRESENTATIVE_LIMIT)
        self.assertEqual(
            len(self._items(family_id=family_id, family_role=FAMILY_ROLE_INSTANCE)),
            8 - FAMILY_REPRESENTATIVE_LIMIT)

    def test_family_is_a_different_axis_from_group(self):
        result = self._register(self._cuts(4))
        item = self._items(family_id=result["family_id"])[0]
        self.assertIsNone(item["group_id"])

    def test_an_instance_without_a_family_is_still_refused_a_snapshot_exemption(self):
        # The exception exists because the family's representative crop is what
        # the human judged. With no family there is no such crop, and the row
        # would be unreviewable.
        with self.assertRaises(CaseWorkspaceError):
            self.store.propose_legend_item(
                self.workspace, source_id=self.source["id"],
                page_structural_unit_id=self.page_id, region={},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="section reference",
                interpretation_method="region_ocr_pattern", actor="GO",
                snapshot_path=None, family_role=FAMILY_ROLE_INSTANCE)

    def test_an_ordinary_row_still_requires_a_snapshot(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.propose_legend_item(
                self.workspace, source_id=self.source["id"],
                page_structural_unit_id=self.page_id, region={},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="section reference",
                interpretation_method="region_ocr_pattern", actor="GO",
                snapshot_path=None)


class OneConfirmationManyInstancesTests(_FamilyBase):
    """D. The point of the whole mechanism, asserted as arithmetic."""

    def test_one_human_answer_governs_every_member(self):
        result = self._register(self._cuts(12))
        outcome = lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer",
            governance_log=self.gov)
        self.assertEqual(len(outcome["applied"]), 12 - FAMILY_REPRESENTATIVE_LIMIT)
        self.assertEqual(outcome["flagged_for_review"], [])
        settled = [i for i in self._items(family_id=result["family_id"])
                   if i["status"] == LEGEND_STATUS_CONFIRMED]
        self.assertEqual(len(settled), 12)

    def test_the_saving_is_real_not_merely_claimed(self):
        result = self._register(self._cuts(20))
        summary = lou.family_meaning(self.store, self.workspace, result["family_id"])
        self.assertEqual(summary["confirmations_asked_of_human"],
                         FAMILY_REPRESENTATIVE_LIMIT)
        self.assertEqual(summary["governed_instances"],
                         20 - FAMILY_REPRESENTATIVE_LIMIT)
        self.assertLess(summary["confirmations_asked_of_human"],
                        summary["governed_instances"])

    def test_a_correction_carries_the_humans_meaning_not_gos(self):
        result = self._register(self._cuts(8))
        lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_OVERRIDDEN, actor="reviewer",
            meaning="detail callout, not a section", governance_log=self.gov)
        for item in self._items(family_id=result["family_id"]):
            self.assertEqual(lou.effective_meaning(item)["meaning"],
                             "detail callout, not a section")
            # GO's original proposal is never rewritten.
            self.assertEqual(item["proposed_meaning"], "section reference to E2")

    def test_scope_defaults_to_the_sheet_not_the_project(self):
        result = self._register(self._cuts(6))
        lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        for item in self._items(family_id=result["family_id"]):
            self.assertEqual(item["scope_kind"], LEGEND_SCOPE_SOURCE)

    def test_a_wider_scope_is_something_a_human_chooses(self):
        result = self._register(self._cuts(6))
        lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer",
            scope_kind=LEGEND_SCOPE_PROJECT)
        for item in self._items(family_id=result["family_id"]):
            self.assertEqual(item["scope_kind"], LEGEND_SCOPE_PROJECT)

    def test_decisions_land_in_the_same_append_only_history(self):
        # No parallel revision model: a family decision is an ordinary
        # decide_legend_item entry, readable exactly like a single-row one.
        result = self._register(self._cuts(6))
        lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        for item in self._items(family_id=result["family_id"]):
            self.assertEqual(len(item["decisions"]), 1)
            self.assertEqual(item["decisions"][0]["actor"], "reviewer")
            self.assertIn("family", (item["decisions"][0]["note"] or "").lower())


class MaterialDifferenceTests(_FamilyBase):
    """E. A mark that does not belong goes BACK to a human. Never forced."""

    def test_a_different_kind_is_material(self):
        reference = self._cut("1/E2", 0)
        odd = dict(reference, proposed_kind=LEGEND_KIND_NORTH_ARROW)
        self.assertTrue(lou.instance_differs_materially(odd, reference))

    def test_a_different_label_grammar_is_material(self):
        reference = self._cut("1/E2", 0)
        odd = dict(reference, observed_text="N", nearby_label="N")
        self.assertTrue(lou.instance_differs_materially(odd, reference))

    def test_a_different_proportion_is_material(self):
        reference = self._cut("1/E2", 0)
        odd = dict(reference, region={"x": 0, "y": 0, "width": 40, "height": 200})
        self.assertTrue(lou.instance_differs_materially(odd, reference))

    def test_pure_scale_difference_is_NOT_material(self):
        # SUPERSEDES an earlier assertion in this file that a size well outside
        # the family was material. That rule split one symbol drawn on a 1:50
        # enlargement from the same symbol on a 1:100 plan, which is the
        # per-occurrence outcome families exist to prevent. Proportion carries
        # meaning; magnitude does not.
        reference = self._cut("1/E2", 0)
        larger = dict(reference, region={"x": 0, "y": 0, "width": 132, "height": 132})
        self.assertEqual(lou.instance_differs_materially(larger, reference), [])

    def test_an_unrecorded_direction_is_material_for_a_section_cut(self):
        reference = self._cut("1/E2", 0)
        odd = dict(reference, section_line_direction_degrees=None,
                   view_direction_degrees=None)
        reasons = lou.instance_differs_materially(odd, reference)
        self.assertTrue(any("direction" in r for r in reasons))

    def test_a_different_target_is_NOT_material(self):
        # Stated as a test because the intuitive rule is wrong and would flag
        # every member of every section-cut family.
        reference = self._cut("1/E2", 0, candidate_target_reference="E2")
        other = self._cut("2/E5", 180, candidate_target_reference="E5")
        self.assertEqual(lou.instance_differs_materially(other, reference), [])

    def test_a_different_direction_alone_is_NOT_material(self):
        reference = self._cut("1/E2", 0)
        rotated = self._cut("2/E2", 270, instance_rotation_degrees=90.0)
        self.assertEqual(lou.instance_differs_materially(rotated, reference), [])

    def test_a_non_conforming_instance_returns_to_review_needed(self):
        candidates = self._cuts(5)
        candidates.append(self._cut("6/E2", 200,
                                    section_line_direction_degrees=None,
                                    view_direction_degrees=None))
        result = self._register(candidates)
        outcome = lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        self.assertEqual(len(outcome["flagged_for_review"]), 1)
        flagged = self._items(family_id=result["family_id"],
                              status=LEGEND_STATUS_REVIEW_NEEDED)
        self.assertEqual(len(flagged), 1)
        self.assertIn("direction", flagged[0]["decisions"][-1]["note"])

    def test_a_flagged_instance_is_not_silently_given_the_family_meaning(self):
        candidates = self._cuts(5)
        candidates.append(self._cut("6/E2", 200,
                                    section_line_direction_degrees=None,
                                    view_direction_degrees=None))
        result = self._register(candidates)
        lou.confirm_family(self.store, self.workspace, result["family_id"],
                           action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        flagged = self._items(family_id=result["family_id"],
                              status=LEGEND_STATUS_REVIEW_NEEDED)[0]
        self.assertNotEqual(flagged["status"], LEGEND_STATUS_CONFIRMED)

    def test_re_applying_does_not_pile_up_duplicate_flags(self):
        candidates = self._cuts(5)
        candidates.append(self._cut("6/E2", 200,
                                    section_line_direction_degrees=None,
                                    view_direction_degrees=None))
        result = self._register(candidates)
        lou.confirm_family(self.store, self.workspace, result["family_id"],
                           action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        before = len(self._items(family_id=result["family_id"],
                                 status=LEGEND_STATUS_REVIEW_NEEDED)[0]["decisions"])
        lou.apply_family_decision(self.store, self.workspace,
                                  result["family_id"], actor="reviewer")
        after = len(self._items(family_id=result["family_id"],
                                status=LEGEND_STATUS_REVIEW_NEEDED)[0]["decisions"])
        self.assertEqual(before, after)


class FamilyAuthorityTests(_FamilyBase):
    """F. The family derives; it never authorizes."""

    def test_an_unconfirmed_family_applies_to_nothing(self):
        result = self._register(self._cuts(6))
        summary = lou.family_meaning(self.store, self.workspace, result["family_id"])
        self.assertEqual(summary["state"], "awaiting_confirmation")
        with self.assertRaises(lou.LegendError):
            lou.apply_family_decision(self.store, self.workspace,
                                      result["family_id"], actor="reviewer")

    def test_representatives_that_disagree_leave_the_family_contested(self):
        result = self._register(self._cuts(9))
        representatives = self._items(
            family_id=result["family_id"],
            family_role=FAMILY_ROLE_REPRESENTATIVE)
        self.store.decide_legend_item(
            self.workspace, representatives[0]["id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer-a")
        self.store.decide_legend_item(
            self.workspace, representatives[1]["id"],
            action=LEGEND_STATUS_OVERRIDDEN, actor="reviewer-b",
            meaning="something else entirely")
        self.store.decide_legend_item(
            self.workspace, representatives[2]["id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer-c")
        summary = lou.family_meaning(self.store, self.workspace, result["family_id"])
        self.assertEqual(summary["state"], "contested")
        self.assertIsNone(summary["meaning"])
        with self.assertRaises(lou.LegendError):
            lou.apply_family_decision(self.store, self.workspace,
                                      result["family_id"], actor="reviewer")

    def test_a_partly_decided_family_applies_to_nothing(self):
        result = self._register(self._cuts(9))
        representative = self._items(
            family_id=result["family_id"],
            family_role=FAMILY_ROLE_REPRESENTATIVE)[0]
        self.store.decide_legend_item(
            self.workspace, representative["id"],
            action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        summary = lou.family_meaning(self.store, self.workspace, result["family_id"])
        self.assertEqual(summary["state"], "partially_confirmed")

    def test_a_members_own_decision_is_never_overwritten(self):
        result = self._register(self._cuts(8))
        instance = self._items(family_id=result["family_id"],
                               family_role=FAMILY_ROLE_INSTANCE)[0]
        self.store.decide_legend_item(
            self.workspace, instance["id"], action=LEGEND_STATUS_INFORMATIVE,
            actor="reviewer")
        lou.confirm_family(self.store, self.workspace, result["family_id"],
                           action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        after = self.store.legend_items_for(
            self.workspace, family_id=result["family_id"])
        kept = next(i for i in after if i["id"] == instance["id"])
        self.assertEqual(kept["status"], LEGEND_STATUS_INFORMATIVE)
        self.assertEqual(len(kept["decisions"]), 1)

    def test_an_unknown_answer_settles_nothing_downstream(self):
        result = self._register(self._cuts(8))
        outcome = lou.confirm_family(
            self.store, self.workspace, result["family_id"],
            action="unknown", actor="reviewer")
        self.assertEqual(outcome["applied"], [])
        instances = self._items(family_id=result["family_id"],
                                family_role=FAMILY_ROLE_INSTANCE)
        self.assertTrue(all(not i["decisions"] for i in instances))

    def test_a_family_with_no_representative_cannot_be_decided(self):
        with self.assertRaises(lou.LegendError):
            lou.confirm_family(self.store, self.workspace, "no-such-family",
                               action=LEGEND_STATUS_CONFIRMED, actor="reviewer")


class ReviewSurfaceTests(_FamilyBase):
    """G. The reviewer sees one question, not twenty."""

    def test_the_table_collapses_a_family_into_one_row(self):
        self._register(self._cuts(12))
        rows = lou.review_rows(self.store, self.workspace,
                               source_id=self.source["id"])
        families = lou.family_review_rows(self.store, self.workspace,
                                          source_id=self.source["id"])
        self.assertEqual(rows, [])
        self.assertEqual(len(families), 1)
        self.assertEqual(families[0]["instance_count"],
                         12 - FAMILY_REPRESENTATIVE_LIMIT)

    def test_the_family_row_shows_real_crops(self):
        self._register(self._cuts(12))
        families = lou.family_review_rows(self.store, self.workspace,
                                          source_id=self.source["id"])
        representatives = families[0]["representatives"]
        self.assertEqual(len(representatives), FAMILY_REPRESENTATIVE_LIMIT)
        self.assertTrue(all(r["has_snapshot"] for r in representatives))

    def test_a_flagged_member_is_never_hidden_inside_its_family(self):
        candidates = self._cuts(5)
        candidates.append(self._cut("6/E2", 200,
                                    section_line_direction_degrees=None,
                                    view_direction_degrees=None))
        result = self._register(candidates)
        lou.confirm_family(self.store, self.workspace, result["family_id"],
                           action=LEGEND_STATUS_CONFIRMED, actor="reviewer")
        rows = lou.review_rows(self.store, self.workspace,
                               source_id=self.source["id"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], LEGEND_STATUS_REVIEW_NEEDED)
        families = lou.family_review_rows(self.store, self.workspace,
                                          source_id=self.source["id"])
        self.assertEqual(families[0]["instances_needing_review"], 1)


class RenderedSurfaceTests(unittest.TestCase):
    """H. The template is actually rendered, not merely written.

    Nothing else in the suite renders `drawing_understanding.html`, so a Jinja
    error in the family block would have surfaced first in front of a user. This
    drives the real route through the real app.
    """

    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_family_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "family-render-project"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="E1.pdf",
            ingested_at="2026-09-07T00:00:00+00:00"))

        self.raw = _sheet_pdf()
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        path = self.tmp_dir / "E1.pdf"
        path.write_bytes(self.raw)
        self.source = self.store.add_source(
            self.workspace, name="E1.pdf", file_path=str(path),
            kind=SOURCE_KIND_DRAWING, document_id="E1", actor="tester")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, self.source["id"],
            [{"index": 0, "label": "E1 SHEET", "width": SHEET_W, "height": SHEET_H,
              "source_rotation": 0, "metadata": {}}], actor="tester")
        self.page_id = registered["structural_unit_ids"][0]

        candidates = [{
            "proposed_kind": LEGEND_KIND_SECTION_REFERENCE,
            "observed_text": "%d/E2" % (n + 1),
            "region": {"x": 40, "y": 120, "width": 44, "height": 44},
            "section_line_direction_degrees": n * 40,
            "view_direction_degrees": (n * 40 + 90) % 360,
            "instance_mirrored": False, "instance_rotation_degrees": 0.0,
            "candidate_target_reference": "E2", "nearby_label": "%d/E2" % (n + 1),
        } for n in range(10)]
        family = lou.cluster_candidates(candidates)[0]
        self.registered = lou.register_family(
            self.store, self.workspace, family,
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            actor="GO", proposed_meaning="section reference to E2",
            interpretation_method="region_ocr_pattern",
            snapshot_for=lambda member: lou.snapshot_region(
                self.raw, 0, (30, 100, 300, 160),
                str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME),
                "crop-%s" % member["observed_text"].replace("/", "-")),
            confidence=0.55)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as session:
            session["user_id"] = 1
            session["username"] = "tester"
            session["role"] = "admin"
        return client

    def test_the_review_page_renders_the_family_table(self):
        response = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.project_id, self.source["id"]))
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("drawing-understanding.family-table", body)
        self.assertIn("Repeated marks", body)
        # The collapsed count is the reviewer-visible proof of the saving.
        self.assertIn("%d other mark(s)" % (10 - FAMILY_REPRESENTATIVE_LIMIT), body)

    def test_the_page_shows_representative_crops_not_every_occurrence(self):
        """A crop per REPRESENTATIVE, never one per occurrence.

        CLAUDE-ASREAD-SURFACE-01 added a case layer above the family bench, so
        the same representatives now carry a crop on each surface. The intent
        this test has always defended - that 10 marks do not produce 10 crops -
        is asserted directly rather than through the single number the previous
        layout happened to produce.
        """
        response = self._client().get(
            "/projects/%s/workspace/sources/%s/understanding"
            % (self.project_id, self.source["id"]))
        body = response.get_data(as_text=True)
        crops = body.count("legend-snapshot")
        self.assertGreaterEqual(crops, FAMILY_REPRESENTATIVE_LIMIT)
        self.assertLess(crops, 10, "never one crop per occurrence")

    def test_one_posted_decision_governs_every_member(self):
        client = self._client()
        response = client.post(
            "/projects/%s/workspace/understanding/family/%s/decide"
            % (self.project_id, self.registered["family_id"]),
            data={"action": LEGEND_STATUS_CONFIRMED, "scope_kind": LEGEND_SCOPE_SOURCE,
                  "source_id": self.source["id"]},
            follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        workspace = self.store.get(self.project_id)
        items = self.store.legend_items_for(
            workspace, family_id=self.registered["family_id"])
        self.assertEqual(len(items), 10)
        self.assertTrue(all(i["status"] == LEGEND_STATUS_CONFIRMED for i in items))


if __name__ == "__main__":
    unittest.main()
