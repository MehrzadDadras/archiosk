"""
CLAUDE-VIEW-REFERENCE-01 - a callout is a pointer, never the view it points at.

The load-bearing assertion in this file is a NEGATIVE one: registering a section
callout on a plan must not bring a Section view into existence. A project that
acquires a section with no geometry behind it has acquired a fiction, and every
later reader inherits it.

The rest follows from resolution being DERIVED rather than stored: a reference to
a sheet nobody has uploaded is unresolved today and resolved the moment the sheet
arrives, with its original record untouched - which is tested directly rather
than assumed, because "no reprocessing needed" is the sort of claim that is easy
to believe and easy to be wrong about.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from services import view_reference as vr
from services.case_workspace import (
    CaseWorkspaceStore,
    OBJECT_KIND_DERIVED_VIEW,
    OBJECT_KIND_SOURCE,
    RESOLUTION_STATUS_AMBIGUOUS,
    RESOLUTION_STATUS_RESOLVED_EXACT,
    RESOLUTION_STATUS_TARGET_NOT_FOUND,
    SCALE_METHOD_PRINTED_NOTATION,
    SCALE_STATE_INFORMATIVE,
    SCALE_STATE_QUANTITATIVE,
    SOURCE_KIND_DRAWING,
)
from services.governance import GovernanceLog


def _png(w=80, h=60):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (40, 80, 140)).save(buf, format="PNG")
    return buf.getvalue()


class _RefBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_vr_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-vr")
        self.plan_source, self.plan_page = self._sheet("E-1.pdf", "E-1", "E-1 PLAN")
        self.plan_view = self.store.create_derived_view(
            self.workspace, source_id=self.plan_source["id"],
            page_structural_unit_id=self.plan_page,
            region={"x": 0, "y": 0, "width": 40, "height": 30},
            derivation_reason="overall plan", actor="tester")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sheet(self, name, document_id, label):
        path = self.tmp_dir / name
        path.write_bytes(_png())
        source = self.store.add_source(
            self.workspace, name=name, file_path=str(path), kind=SOURCE_KIND_DRAWING,
            document_id=document_id, actor="tester")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, source["id"],
            [{"index": 0, "label": label, "width": 80, "height": 60,
              "source_rotation": 0, "metadata": {}}], actor="tester")
        return source, registered["structural_unit_ids"][0]

    def _callout(self, text="Detail 3 / E-2", kind=vr.VIEW_REFERENCE_SECTION, **kw):
        params = dict(source_id=self.plan_source["id"], text=text,
                      reference_kind=kind,
                      parent_derived_view_id=self.plan_view["id"],
                      region={"x": 10, "y": 10, "width": 4, "height": 4},
                      actor="tester")
        params.update(kw)
        created = vr.register_view_reference(self.store, self.workspace, **params)
        return created

    def _refresh(self):
        self.workspace = self.store.get(self.workspace.project_id)
        return self.workspace


class ViewVersusReferenceTests(_RefBase):
    """A. The distinction, and the mistake it prevents."""

    def test_every_callout_kind_classifies_as_a_reference(self):
        for kind in vr.KNOWN_VIEW_REFERENCE_KINDS:
            with self.subTest(kind=kind):
                self.assertEqual(vr.classify_marker(kind), vr.MARKER_VIEW_REFERENCE)

    def test_a_section_callout_creates_no_section_view(self):
        """The whole point: the section is drawn on ANOTHER sheet."""
        before = len(self.store.derived_views_for(self.workspace))
        self._callout()
        after = len(self.store.derived_views_for(self._refresh()))
        self.assertEqual(after, before,
                         "a callout brought a view into existence that has no geometry")

    def test_registering_a_physical_view_kind_as_a_reference_is_refused(self):
        with self.assertRaises(ValueError):
            self._callout(kind="plan")

    def test_the_reference_records_the_parent_view_it_sits_on(self):
        created = self._callout()
        context = created[0]["origin_context"]
        self.assertEqual(context["parent_derived_view_id"], self.plan_view["id"])
        self.assertEqual(context["marker_class"], vr.MARKER_VIEW_REFERENCE)

    def test_references_can_be_listed_from_their_parent_view(self):
        self._callout()
        found = vr.references_from_view(self.store, self._refresh(), self.plan_view["id"])
        self.assertEqual(len(found), 1)


class MissingTargetTests(_RefBase):
    """C/D. Unresolved today, resolved when the sheet arrives - no rewrite."""

    def test_a_reference_to_an_absent_sheet_is_unresolved_not_an_error(self):
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)
        self.assertEqual(result["target_ids"], [])

    def test_the_reference_survives_with_its_text_intact(self):
        created = self._callout("Detail 3 / E-2")
        stored = next(r for r in self._refresh().source_references
                      if r["id"] == created[0]["id"])
        self.assertIn("E-2", stored["reference_text"])

    def test_a_later_uploaded_target_resolves_the_earlier_reference(self):
        created = self._callout("Detail 3 / E-2")
        reference_id = created[0]["id"]
        before = vr.resolve_view_reference(self.store, self._refresh(), reference_id)
        self.assertEqual(before["status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)

        self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        after = vr.resolve_view_reference(self.store, self._refresh(), reference_id)
        self.assertEqual(after["status"], RESOLUTION_STATUS_RESOLVED_EXACT)

    def test_resolution_never_mutates_the_stored_record(self):
        """Creation history is preserved BY CONSTRUCTION, because nothing was
        ever written down as resolved."""
        created = self._callout("Detail 3 / E-2")
        original = dict(next(r for r in self._refresh().source_references
                             if r["id"] == created[0]["id"]))
        self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        stored = next(r for r in self._refresh().source_references
                      if r["id"] == created[0]["id"])
        self.assertEqual(stored["created_at"], original["created_at"])
        self.assertEqual(stored["reference_text"], original["reference_text"])
        self.assertEqual(stored["resolution_status"], original["resolution_status"])


class TargetResolutionTests(_RefBase):
    """B/E/I. Sheet, then view - and never a guess."""

    def test_it_resolves_to_the_target_sheet(self):
        target, _page = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(result["target_ids"], [target["id"]])

    def test_a_sheet_with_no_matching_view_reports_target_view_unresolved(self):
        """Better than inventing a view boundary nobody established."""
        self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["target_type"], OBJECT_KIND_SOURCE)
        self.assertEqual(result["target_view_state"], vr.TARGET_VIEW_UNRESOLVED)

    def test_it_resolves_to_the_specific_target_view_when_one_exists(self):
        target, page = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        view = self.store.create_derived_view(
            self.workspace, source_id=target["id"], page_structural_unit_id=page,
            region={"x": 0, "y": 0, "width": 20, "height": 20},
            derivation_reason="section 3", actor="tester")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["target_type"], OBJECT_KIND_DERIVED_VIEW)
        self.assertEqual(result["target_ids"], [view["id"]])

    def test_an_informative_target_view_still_resolves(self):
        """I. Scale has nothing to do with whether a reference points somewhere."""
        target, page = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        view = self.store.create_derived_view(
            self.workspace, source_id=target["id"], page_structural_unit_id=page,
            region={"x": 0, "y": 0, "width": 20, "height": 20},
            derivation_reason="section 3", actor="tester",
            scale_state=SCALE_STATE_INFORMATIVE, scale_notation="NTS")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["target_ids"], [view["id"]])

    def test_a_removed_sheet_is_never_a_candidate(self):
        target, _page = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        self.store.remove_source(self.workspace, target["id"], actor="pm",
                                 actor_role="admin", reason="superseded")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)

    def test_a_sheet_never_resolves_to_itself(self):
        created = self._callout("Detail 3 / E-1")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)


class AmbiguityTests(_RefBase):
    """E. Two candidates is an answer, not a coin toss."""

    def test_two_matching_sheets_stay_ambiguous(self):
        self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        self._sheet("E-2-rev.pdf", "E-2", "E-2 SECTIONS REV B")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_AMBIGUOUS)
        self.assertEqual(len(result["target_ids"]), 2)

    def test_ambiguity_is_not_resolved_by_recency_or_filename(self):
        self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        self._sheet("zzz-newest-E-2.pdf", "E-2", "E-2 LATEST")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_AMBIGUOUS)
        self.assertIn("guess", result["reason"])

    def test_both_candidates_are_preserved_for_a_human(self):
        a, _ = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        b, _ = self._sheet("E-2b.pdf", "E-2", "E-2 SECTIONS B")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(sorted(result["target_ids"]), sorted([a["id"], b["id"]]))


class HumanConfirmationTests(_RefBase):
    """J/12. Confirmation sits beside the evidence, never over it."""

    def test_a_confirmation_resolves_an_ambiguous_reference(self):
        a, _ = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        self._sheet("E-2b.pdf", "E-2", "E-2 SECTIONS B")
        created = self._callout("Detail 3 / E-2")
        reference_id = created[0]["id"]
        self.assertEqual(
            vr.resolve_view_reference(self.store, self._refresh(), reference_id)["status"],
            RESOLUTION_STATUS_AMBIGUOUS)

        vr.confirm_target(self.store, self._refresh(), reference_id,
                          target_type=OBJECT_KIND_SOURCE, target_id=a["id"], actor="pm")
        result = vr.resolve_view_reference(self.store, self._refresh(), reference_id)
        self.assertEqual(result["status"], RESOLUTION_STATUS_RESOLVED_EXACT)
        self.assertEqual(result["target_ids"], [a["id"]])
        self.assertEqual(result["resolution_method"], "human_confirmation")

    def test_the_extracted_evidence_is_not_erased_by_confirmation(self):
        a, _ = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        created = self._callout("Detail 3 / E-2")
        original_text = created[0]["reference_text"]
        vr.confirm_target(self.store, self._refresh(), created[0]["id"],
                          target_type=OBJECT_KIND_SOURCE, target_id=a["id"], actor="pm")
        stored = next(r for r in self._refresh().source_references
                      if r["id"] == created[0]["id"])
        self.assertEqual(stored["reference_text"], original_text)

    def test_a_confirmation_is_a_governed_attributable_edge(self):
        a, _ = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        created = self._callout("Detail 3 / E-2")
        edge = vr.confirm_target(self.store, self._refresh(), created[0]["id"],
                                 target_type=OBJECT_KIND_SOURCE, target_id=a["id"],
                                 actor="pm")
        self.assertFalse(edge["provisional"])
        self.assertEqual(edge["created_by"], "pm")


class DirectionTests(_RefBase):
    """G. Viewing direction is not North and not view rotation."""

    def test_direction_is_preserved_independently(self):
        created = self._callout(direction_degrees=270.0)
        context = created[0]["origin_context"]
        self.assertEqual(context["direction_degrees"], 270.0)

    def test_direction_does_not_appear_as_a_north_value_anywhere(self):
        """A section arrow says which way you look, not where north is."""
        self._callout(direction_degrees=270.0)
        views = self.store.derived_views_for(self._refresh())
        for view in views:
            self.assertIsNone(view.get("true_north_degrees"))
            self.assertIsNone(view.get("project_north_degrees"))
            self.assertEqual(view["north_state"], "unknown")

    def test_a_reference_without_direction_records_none_rather_than_zero(self):
        created = self._callout()
        self.assertIsNone(created[0]["origin_context"]["direction_degrees"])


class IsolationAndIntegrityTests(_RefBase):
    """F/G/H."""

    def test_a_target_in_another_project_is_never_considered(self):
        other = self.store.get_or_create("test-project-vr-other")
        path = self.tmp_dir / "foreign-E-2.pdf"
        path.write_bytes(_png())
        self.store.add_source(other, name="E-2.pdf", file_path=str(path),
                              kind=SOURCE_KIND_DRAWING, document_id="E-2", actor="tester")
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["status"], RESOLUTION_STATUS_TARGET_NOT_FOUND)

    def test_registering_a_reference_does_not_touch_the_source_file(self):
        path = self.tmp_dir / "E-1.pdf"
        before = path.read_bytes()
        self._callout()
        self.assertEqual(path.read_bytes(), before)

    def test_title_block_inheritance_on_the_parent_view_is_unaffected(self):
        before = dict(self.plan_view["inherited_title_block"])
        self._callout()
        view = next(v for v in self.store.derived_views_for(self._refresh())
                    if v["id"] == self.plan_view["id"])
        self.assertEqual(view["inherited_title_block"], before)


class VectorCompatibilityTests(_RefBase):
    """K. The section line will be geometry; its MEANING stays a reference."""

    def test_the_reference_keeps_its_region_for_a_future_line_primitive(self):
        created = self._callout()
        region = created[0]["origin_context"]["region"]
        self.assertEqual(region["width"], 4)

    def test_the_chain_from_parent_view_to_target_view_is_walkable(self):
        target, page = self._sheet("E-2.pdf", "E-2", "E-2 SECTIONS")
        target_view = self.store.create_derived_view(
            self.workspace, source_id=target["id"], page_structural_unit_id=page,
            region={"x": 0, "y": 0, "width": 20, "height": 20},
            derivation_reason="section 3", actor="tester",
            scale_state=SCALE_STATE_QUANTITATIVE, scale_value=20.0,
            scale_notation="1:20", scale_method=SCALE_METHOD_PRINTED_NOTATION)
        created = self._callout("Detail 3 / E-2")
        result = vr.resolve_view_reference(self.store, self._refresh(), created[0]["id"])
        self.assertEqual(result["parent_derived_view_id"], self.plan_view["id"])
        self.assertEqual(result["target_ids"], [target_view["id"]])
        self.assertEqual(result["marker_class"], vr.MARKER_VIEW_REFERENCE,
                         "the mark must stay a reference even once it is geometry")


if __name__ == "__main__":
    unittest.main()
