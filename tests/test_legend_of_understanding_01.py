"""
CLAUDE-LEGEND-OF-UNDERSTANDING-01 - GO proposes, a human confirms, meaning reuses.

The assertions that carry weight are about what is REFUSED and what is
PRESERVED. A row without a snapshot is refused, because asking someone to agree
with a detached label invites them to agree with a plausible sentence. An
override never touches GO's proposal, because the value of the record is that
both readings stay visible. And a generic inference can never outrank a
project's own legend, which is the failure mode that makes symbol libraries
dangerous on real drawing sets.

Snapshots here are produced from a REAL rasterised PDF, so the crop path is
genuinely exercised rather than mocked.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
from pathlib import Path

import pymupdf

from services import legend_of_understanding as lou
from services.case_workspace import (
    CaseWorkspaceError,
    CaseWorkspaceStore,
    LEGEND_KIND_DETAIL_REFERENCE,
    LEGEND_KIND_SECTION_REFERENCE,
    LEGEND_KIND_UNKNOWN_SYMBOL,
    LEGEND_SCOPE_DISCIPLINE,
    LEGEND_SCOPE_INSTANCE,
    LEGEND_SCOPE_PAGE,
    LEGEND_SCOPE_PROJECT,
    LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED,
    LEGEND_STATUS_DEFERRED,
    LEGEND_STATUS_INFORMATIVE,
    LEGEND_STATUS_OVERRIDDEN,
    LEGEND_STATUS_PROPOSED,
    LEGEND_STATUS_REVIEW_NEEDED,
    LEGEND_STATUS_UNKNOWN,
    SOURCE_KIND_DRAWING,
)
from services.governance import GovernanceLog

SHEET_W, SHEET_H = 612.0, 460.0


def _sheet_pdf(label="A-101 PLAN") -> bytes:
    drawn = pymupdf.open()
    page = drawn.new_page(width=SHEET_W, height=SHEET_H)
    page.insert_text((40, 60), label, fontsize=12)
    page.insert_text((40, 160), "SECTION 3 / A-501", fontsize=11)
    page.insert_text((40, 260), "TYP. WELD ALL AROUND", fontsize=10)
    rasterised = pymupdf.open()
    pix = drawn.load_page(0).get_pixmap(dpi=96)
    out = rasterised.new_page(width=SHEET_W, height=SHEET_H)
    out.insert_image(pymupdf.Rect(0, 0, SHEET_W, SHEET_H), stream=pix.tobytes("png"))
    raw = rasterised.tobytes()
    drawn.close(); rasterised.close()
    return raw


class _LegendBase(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="archiosk_lou_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.gov = GovernanceLog(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-lou")
        self.raw = _sheet_pdf()
        self.source, self.page_id = self._sheet("A-101.pdf", "A-101")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _sheet(self, name, document_id):
        path = self.tmp_dir / name
        path.write_bytes(self.raw)
        source = self.store.add_source(
            self.workspace, name=name, file_path=str(path), kind=SOURCE_KIND_DRAWING,
            document_id=document_id, actor="tester")
        registered = self.store.register_drawing_sheet_structure(
            self.workspace, source["id"],
            [{"index": 0, "label": "%s SHEET" % document_id, "width": SHEET_W,
              "height": SHEET_H, "source_rotation": 0, "metadata": {}}], actor="tester")
        return source, registered["structural_unit_ids"][0]

    def _snapshot(self, key, rect=(30, 140, 300, 190)):
        return lou.snapshot_region(self.raw, 0, rect,
                                   str(self.tmp_dir / lou.SNAPSHOT_DIR_NAME), key)

    def _propose(self, key="m1", **kw):
        params = dict(
            source_id=self.source["id"], page_structural_unit_id=self.page_id,
            region={"x": 30, "y": 140, "width": 270, "height": 50},
            proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
            proposed_meaning="section reference to A-501",
            interpretation_method="region_ocr_pattern",
            actor="GO", snapshot_path=self._snapshot(key),
            observed_text="SECTION 3 / A-501", confidence=0.55)
        params.update(kw)
        return self.store.propose_legend_item(self.workspace, **params)

    def _refresh(self):
        self.workspace = self.store.get(self.workspace.project_id)
        return self.workspace


class SnapshotTests(_LegendBase):
    """A. Every row shows the real mark."""

    def test_a_real_crop_is_produced_from_the_pdf(self):
        path = self._snapshot("crop-test")
        self.assertTrue(Path(path).is_file())
        self.assertGreater(Path(path).stat().st_size, 200)

    def test_every_review_row_has_a_snapshot(self):
        self._propose("a"); self._propose("b", proposed_meaning="weld note")
        rows = lou.review_rows(self.store, self._refresh(), source_id=self.source["id"])
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertTrue(row["has_snapshot"], "a review row had no visual evidence")

    def test_a_proposal_without_a_snapshot_is_refused(self):
        """A row that cannot show its evidence cannot be reviewed honestly."""
        with self.assertRaises(CaseWorkspaceError):
            self._propose(snapshot_path=None)

    def test_an_unknown_mark_still_carries_its_picture(self):
        item = self._propose("unk", proposed_kind=LEGEND_KIND_UNKNOWN_SYMBOL,
                             proposed_meaning="unrecognised symbol", confidence=None)
        self.assertTrue(Path(item["snapshot_path"]).is_file())


class ObservationVersusInterpretationTests(_LegendBase):
    """B/C. The proposal survives every correction."""

    def test_a_proposal_starts_unconfirmed(self):
        item = self._propose()
        self.assertEqual(item["status"], LEGEND_STATUS_PROPOSED)
        self.assertEqual(lou.effective_meaning(item)["authority"], "machine_proposal")

    def test_confirming_preserves_the_proposal_as_the_meaning(self):
        item = self._propose()
        decided = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED, actor="pm")
        resolved = lou.effective_meaning(decided)
        self.assertEqual(resolved["authority"], "human_confirmed")
        self.assertEqual(resolved["meaning"], "section reference to A-501")

    def test_an_override_changes_meaning_without_deleting_the_proposal(self):
        item = self._propose()
        decided = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_OVERRIDDEN,
            actor="pm", meaning="weld symbol")
        resolved = lou.effective_meaning(decided)
        self.assertEqual(resolved["meaning"], "weld symbol")
        self.assertEqual(resolved["proposed_meaning"], "section reference to A-501")
        self.assertEqual(decided["proposed_meaning"], "section reference to A-501")

    def test_the_observation_is_never_rewritten_by_a_decision(self):
        item = self._propose()
        before = (item["region"], item["observed_text"], item["snapshot_path"])
        decided = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_OVERRIDDEN,
            actor="pm", meaning="weld symbol")
        self.assertEqual(
            (decided["region"], decided["observed_text"], decided["snapshot_path"]), before)

    def test_changing_your_mind_twice_leaves_three_readable_states(self):
        item = self._propose()
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm")
        final = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_OVERRIDDEN,
            actor="pm2", meaning="weld symbol")
        self.assertEqual(len(final["decisions"]), 2)
        self.assertEqual(final["proposed_meaning"], "section reference to A-501")
        self.assertEqual(lou.effective_meaning(final)["meaning"], "weld symbol")

    def test_an_override_must_say_what_the_mark_actually_is(self):
        item = self._propose()
        with self.assertRaises(CaseWorkspaceError):
            self.store.decide_legend_item(self.workspace, item["id"],
                                          action=LEGEND_STATUS_OVERRIDDEN, actor="pm")

    def test_unknown_stays_unknown(self):
        """I. Marking unknown must not quietly leave GO's guess in force."""
        item = self._propose()
        decided = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_UNKNOWN, actor="pm")
        resolved = lou.effective_meaning(decided)
        self.assertIsNone(resolved["meaning"])
        self.assertEqual(resolved["authority"], "human_unknown")


class ScopeTests(_LegendBase):
    """D/E/F. A confirmation reaches exactly as far as the human said."""

    def _confirmed(self, scope, key="s", **kw):
        item = self._propose(key, **kw)
        return self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED,
            actor="pm", scope_kind=scope)

    def test_instance_scope_is_never_reused_elsewhere(self):
        self._confirmed(LEGEND_SCOPE_INSTANCE)
        resolved = lou.resolve_meaning(
            self.store, self._refresh(), observed_text="SECTION 3 / A-501",
            page_id=self.page_id, source_id=self.source["id"])
        self.assertFalse(resolved["resolved"])

    def test_page_scope_applies_to_that_page_only(self):
        self._confirmed(LEGEND_SCOPE_PAGE)
        ws = self._refresh()
        here = lou.resolve_meaning(self.store, ws, observed_text="SECTION 3 / A-501",
                                   page_id=self.page_id, source_id=self.source["id"])
        self.assertTrue(here["resolved"])
        elsewhere = lou.resolve_meaning(self.store, ws, observed_text="SECTION 3 / A-501",
                                        page_id="some-other-page")
        self.assertFalse(elsewhere["resolved"])

    def test_source_scope_reaches_the_whole_sheet(self):
        self._confirmed(LEGEND_SCOPE_SOURCE)
        resolved = lou.resolve_meaning(
            self.store, self._refresh(), observed_text="SECTION 3 / A-501",
            page_id="another-page-of-same-sheet", source_id=self.source["id"])
        self.assertTrue(resolved["resolved"])

    def test_discipline_scope_reaches_only_that_discipline(self):
        self._confirmed(LEGEND_SCOPE_DISCIPLINE,
                        style_context={"discipline": "structural"})
        ws = self._refresh()
        same = lou.resolve_meaning(self.store, ws, observed_text="SECTION 3 / A-501",
                                   discipline="structural")
        other = lou.resolve_meaning(self.store, ws, observed_text="SECTION 3 / A-501",
                                    discipline="mechanical")
        self.assertTrue(same["resolved"])
        self.assertFalse(other["resolved"])

    def test_project_scope_reaches_everywhere_in_this_project(self):
        self._confirmed(LEGEND_SCOPE_PROJECT)
        resolved = lou.resolve_meaning(
            self.store, self._refresh(), observed_text="SECTION 3 / A-501")
        self.assertTrue(resolved["resolved"])

    def test_the_default_scope_is_the_narrowest(self):
        """A convention confirmed on one sheet is not evidence about a whole
        discipline until somebody says so."""
        item = self._propose()
        decided = self.store.decide_legend_item(
            self.workspace, item["id"], action=LEGEND_STATUS_CONFIRMED, actor="pm")
        self.assertEqual(decided["scope_kind"], LEGEND_SCOPE_INSTANCE)


class PrecedenceTests(_LegendBase):
    """J. Explicit project evidence outranks a generic guess."""

    def test_an_explicit_legend_outranks_a_generic_inference(self):
        generic = self._propose("g", proposed_meaning="generic section marker",
                                evidence_tier="generic_inference")
        self.store.decide_legend_item(self.workspace, generic["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm",
                                      scope_kind=LEGEND_SCOPE_PROJECT)
        explicit = self._propose("e", proposed_meaning="weld all around (sheet legend)",
                                 evidence_tier="explicit_legend")
        self.store.decide_legend_item(self.workspace, explicit["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm",
                                      scope_kind=LEGEND_SCOPE_PROJECT)
        resolved = lou.resolve_meaning(
            self.store, self._refresh(), observed_text="SECTION 3 / A-501")
        self.assertEqual(resolved["tier"], "explicit_legend")
        self.assertIn("sheet legend", resolved["meaning"])

    def test_nothing_confirmed_means_unresolved_not_a_guess(self):
        self._propose()
        resolved = lou.resolve_meaning(
            self.store, self._refresh(), observed_text="SECTION 3 / A-501",
            page_id=self.page_id)
        self.assertFalse(resolved["resolved"])
        self.assertEqual(resolved["tier"], "unresolved")


class GroupReuseTests(_LegendBase):
    """G/H. Ask once per family; a contradiction stops inheritance."""

    def test_a_confirmed_understanding_inherits_to_a_sibling_sheet(self):
        item = self._propose("grp", group_id="amx-set")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm",
                                      scope_kind=LEGEND_SCOPE_SOURCE)
        sibling, sibling_page = self._sheet("A-102.pdf", "A-102")
        created = lou.inherit_group_understanding(
            self.store, self._refresh(), "amx-set", sibling["id"], sibling_page,
            actor="GO")
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]["inherited_from_item_id"], item["id"])

    def test_inheritance_is_marked_so_it_is_not_mistaken_for_own_evidence(self):
        item = self._propose("grp2", group_id="amx-set")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm")
        sibling, sibling_page = self._sheet("A-103.pdf", "A-103")
        created = lou.inherit_group_understanding(
            self.store, self._refresh(), "amx-set", sibling["id"], sibling_page,
            actor="GO")
        rows = lou.review_rows(self.store, self._refresh(), source_id=sibling["id"])
        self.assertTrue(rows[0]["inherited"])

    def test_an_unconfirmed_item_is_never_inherited(self):
        self._propose("grp3", group_id="amx-set")
        sibling, sibling_page = self._sheet("A-104.pdf", "A-104")
        created = lou.inherit_group_understanding(
            self.store, self._refresh(), "amx-set", sibling["id"], sibling_page,
            actor="GO")
        self.assertEqual(created, [])

    def test_a_page_contradiction_triggers_review_needed(self):
        item = self._propose("grp4", group_id="amx-set")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm")
        sibling, sibling_page = self._sheet("A-105.pdf", "A-105")
        created = lou.inherit_group_understanding(
            self.store, self._refresh(), "amx-set", sibling["id"], sibling_page,
            actor="GO")
        inherited = created[0]
        self.assertTrue(lou.contradicts_group(inherited, "SECTION 9 / A-999", None))
        flagged = self.store.flag_legend_item_review(
            self._refresh(), inherited["id"], reason="page disagrees with the set")
        self.assertEqual(flagged["status"], LEGEND_STATUS_REVIEW_NEEDED)

    def test_a_matching_page_does_not_contradict(self):
        item = self._propose("grp5", group_id="amx-set")
        self.assertFalse(lou.contradicts_group(item, "SECTION 3 / A-501",
                                               LEGEND_KIND_SECTION_REFERENCE))


class StyleContextTests(_LegendBase):
    """Era/office informs confidence, never meaning."""

    def test_style_context_is_preserved(self):
        item = self._propose("sty", style_context={
            "discipline": "structural", "office": "AMX Steel",
            "era": "scanned_legacy", "drafting": "hand_drafted"})
        self.assertEqual(item["style_context"]["era"], "scanned_legacy")

    def test_style_context_alone_never_resolves_a_meaning(self):
        self._propose("sty2", style_context={"discipline": "structural"})
        resolved = lou.resolve_meaning(self.store, self._refresh(),
                                       observed_text="SECTION 3 / A-501",
                                       discipline="structural")
        self.assertFalse(resolved["resolved"],
                         "style context decided a meaning on its own")


class ReportTests(_LegendBase):
    """8/10. Compact, and honest about what is being held back."""

    def test_the_report_counts_what_awaits_a_human(self):
        self._propose("r1"); self._propose("r2", proposed_meaning="weld note")
        report = lou.understanding_report(self.store, self._refresh(), self.source["id"])
        self.assertEqual(report["proposed_items"], 2)
        self.assertEqual(report["awaiting_confirmation"], 2)

    def test_the_report_names_the_work_it_is_deferring(self):
        self._propose("r3")
        report = lou.understanding_report(self.store, self._refresh(), self.source["id"])
        self.assertTrue(report["deferred_work"])
        self.assertTrue(any("Vector" in reason or "vector" in reason
                            for reason in report["deferred_work"]))

    def test_deferring_a_row_does_not_count_as_settling_it(self):
        item = self._propose("r4")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_DEFERRED, actor="pm")
        report = lou.understanding_report(self.store, self._refresh(), self.source["id"])
        self.assertEqual(report["awaiting_confirmation"], 1)

    def test_marking_not_important_does_settle_it(self):
        item = self._propose("r5")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_INFORMATIVE, actor="pm")
        report = lou.understanding_report(self.store, self._refresh(), self.source["id"])
        self.assertEqual(report["awaiting_confirmation"], 0)


class IntegrityTests(_LegendBase):
    """K/L."""

    def test_the_source_file_is_never_modified(self):
        path = self.tmp_dir / "A-101.pdf"
        before = path.read_bytes()
        item = self._propose("int")
        self.store.decide_legend_item(self.workspace, item["id"],
                                      action=LEGEND_STATUS_CONFIRMED, actor="pm")
        self.assertEqual(path.read_bytes(), before)

    def test_cross_project_isolation(self):
        self._propose("iso")
        other = self.store.get_or_create("test-project-lou-other")
        self.assertEqual(self.store.legend_items_for(other), [])
        self.assertFalse(lou.resolve_meaning(
            self.store, other, observed_text="SECTION 3 / A-501")["resolved"])

    def test_a_proposal_cannot_reference_another_projects_source(self):
        other = self.store.get_or_create("test-project-lou-other2")
        with self.assertRaises(CaseWorkspaceError):
            self.store.propose_legend_item(
                other, source_id=self.source["id"],
                page_structural_unit_id=self.page_id, region={},
                proposed_kind=LEGEND_KIND_DETAIL_REFERENCE, proposed_meaning="x",
                interpretation_method="test", actor="GO", snapshot_path="/tmp/x.png")


if __name__ == "__main__":
    unittest.main()
