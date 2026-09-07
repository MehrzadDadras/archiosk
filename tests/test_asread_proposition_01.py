"""CLAUDE-ASREAD-PROPOSITION-01: IDENTITY and TARGET are different questions.

The family mechanism groups marks on a VISUAL signature - kind, label grammar,
proportion - and then carries a confirmed meaning to the members. Sound as a
proposal; unsound as semantic authority, and the distinction had never been
named. On the real E1 sheet a person saw six crops and a meaning was proposed
for thirty-one marks on the strength of proportion buckets.

The load-bearing tests here are the ones that hold that line:

`test_confirming_identity_does_not_confirm_target` - two conclusions, two
answers. A mark can signify a section reference and refer to a different sheet
than its neighbour, and the second question must survive the first being
answered.

`test_visual_cluster_alone_is_not_semantic_authority` - membership of a family
carries nothing by itself. Inheritance requires a HUMAN-SETTLED source
proposition and stated evidence, and refuses without either.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    CaseWorkspaceStore, LEGEND_KIND_SECTION_REFERENCE, LEGEND_SCOPE_SOURCE,
    LEGEND_STATUS_CONFIRMED, LEGEND_STATUS_OVERRIDDEN, LEGEND_STATUS_REVIEW_AGAIN,
    PROPOSITION_IDENTITY, PROPOSITION_TARGET, RELATIONSHIP_TYPE_SAME_SUBJECT_AS,
)
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
from services.legend_of_understanding import (
    LegendError, break_inheritance, decide_proposition, dependents_of_proposition,
    inherit_proposition, legend_proposition, numbered_cases, propose_target,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _file(content: bytes, name: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=name)


class PropositionAxisTests(unittest.TestCase):
    FAMILY = "fam-prop-01"

    def setUp(self):
        import app as app_module

        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_proposition_"))
        self.app = app_module.create_app("testing")
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)

        def fake_parse(_parser, _raw, filename):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename,
                ingested_at=datetime.now(timezone.utc).isoformat(),
                parser_version="test")

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.app.app_context():
                self.document = ingest_upload(
                    _file(b"owner", "owner.txt"), self.app,
                    operating_environment=CLIENT_OWNER, owner="owner",
                    project_name="Proposition Fixture")
        self.project_id = self.document.project_id
        self.store = CaseWorkspaceStore(self.tmp)
        self.source = self.store.get(self.project_id).sources[0]
        self.snapshot = self.tmp / "crop.png"
        self.snapshot.write_bytes(b"\x89PNG\r\n\x1a\n")

        workspace = self.store.get(self.project_id)
        self.unit = self.store.register_drawing_sheet_structure(
            workspace, self.source["id"],
            [{"index": 0, "label": "Sheet", "width": 100.0, "height": 100.0,
              "source_rotation": 0, "metadata": {}}],
            actor="test")["structural_unit_ids"][0]

        # Four marks in ONE visual family - the E1 shape in miniature.
        self.marks = []
        for index in range(4):
            workspace = self.store.get(self.project_id)
            item = self.store.propose_legend_item(
                workspace, source_id=self.source["id"],
                page_structural_unit_id=self.unit,
                region={"x": float(index), "y": 1.0, "width": 5.0, "height": 5.0},
                proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
                proposed_meaning="A section reference marker.",
                interpretation_method="test", actor="GO",
                snapshot_path=str(self.snapshot), confidence=0.55,
                family_id=self.FAMILY, family_role="representative",
                nearby_label="A")
            self.marks.append(item["id"])

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _ws(self):
        return self.store.get(self.project_id)

    def _item(self, item_id):
        return next(i for i in self._ws().legend_items if i["id"] == item_id)

    def _confirm_identity(self, item_id):
        return decide_proposition(
            self.store, self._ws(), item_id, PROPOSITION_IDENTITY,
            action=LEGEND_STATUS_CONFIRMED, actor="Product Owner",
            scope_kind=LEGEND_SCOPE_SOURCE)

    # -- 1. the two propositions are independent -----------------------------

    def test_identity_and_target_are_independently_decidable(self):
        workspace = self._ws()
        propose_target(self.store, workspace, self.marks[0],
                       proposed_value="Section E on sheet E2", confidence=0.4)
        self._confirm_identity(self.marks[0])

        item = self._item(self.marks[0])
        identity = legend_proposition(item, PROPOSITION_IDENTITY)
        target = legend_proposition(item, PROPOSITION_TARGET)
        self.assertTrue(identity["settled"])
        self.assertFalse(target["settled"])
        self.assertEqual(target["proposed_value"], "Section E on sheet E2")

        decide_proposition(self.store, self._ws(), self.marks[0],
                           PROPOSITION_TARGET, action=LEGEND_STATUS_CONFIRMED,
                           actor="Product Owner")
        self.assertTrue(legend_proposition(
            self._item(self.marks[0]), PROPOSITION_TARGET)["settled"])

    def test_confirming_identity_does_not_confirm_target(self):
        workspace = self._ws()
        propose_target(self.store, workspace, self.marks[0],
                       proposed_value="Section E on sheet E2")
        self._confirm_identity(self.marks[0])
        target = legend_proposition(self._item(self.marks[0]), PROPOSITION_TARGET)
        self.assertFalse(target["settled"])
        self.assertEqual(target["status"], "proposed")
        self.assertEqual(target["decisions"], [])

    def test_unproposed_target_is_not_an_unanswered_question(self):
        """No target proposal is a different state from an unsettled one."""
        self._confirm_identity(self.marks[0])
        target = legend_proposition(self._item(self.marks[0]), PROPOSITION_TARGET)
        self.assertFalse(target["proposed"])
        self.assertIsNone(target["status"])
        with self.assertRaises(LegendError):
            decide_proposition(self.store, self._ws(), self.marks[0],
                               PROPOSITION_TARGET, action=LEGEND_STATUS_CONFIRMED,
                               actor="Product Owner")

    def test_same_identity_different_target_is_representable(self):
        self._confirm_identity(self.marks[0])
        workspace = self._ws()
        propose_target(self.store, workspace, self.marks[0],
                       proposed_value="Section E on sheet E2")
        propose_target(self.store, self._ws(), self.marks[1],
                       proposed_value="Section E on sheet E3")
        inherit_proposition(
            self.store, self._ws(), self.marks[1], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0],
            evidence="Same symbol, same label grammar, confirmed convention.",
            confidence=0.8)
        item = self._item(self.marks[1])
        self.assertTrue(legend_proposition(item, PROPOSITION_IDENTITY)["settled"])
        self.assertFalse(legend_proposition(item, PROPOSITION_TARGET)["settled"])
        self.assertEqual(
            legend_proposition(item, PROPOSITION_TARGET)["proposed_value"],
            "Section E on sheet E3")

    # -- 2. visual clustering is a proposal, never authority -----------------

    def test_visual_cluster_alone_is_not_semantic_authority(self):
        """Family membership carries nothing. Inheritance needs a human."""
        workspace = self._ws()
        for item_id in self.marks:
            self.assertFalse(
                legend_proposition(self._item(item_id), PROPOSITION_IDENTITY)["settled"])
        # Same family, but the source was never confirmed by a person.
        with self.assertRaises(LegendError):
            inherit_proposition(
                self.store, workspace, self.marks[1], PROPOSITION_IDENTITY,
                from_legend_item_id=self.marks[0], evidence="same family")

    def test_inheritance_requires_stated_evidence(self):
        self._confirm_identity(self.marks[0])
        with self.assertRaises(LegendError):
            inherit_proposition(
                self.store, self._ws(), self.marks[1], PROPOSITION_IDENTITY,
                from_legend_item_id=self.marks[0], evidence="   ")

    def test_inheritance_may_not_chain(self):
        self._confirm_identity(self.marks[0])
        inherit_proposition(
            self.store, self._ws(), self.marks[1], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0], evidence="same convention")
        with self.assertRaises(LegendError):
            inherit_proposition(
                self.store, self._ws(), self.marks[2], PROPOSITION_IDENTITY,
                from_legend_item_id=self.marks[1], evidence="same again")

    # -- 3. lineage and provenance -------------------------------------------

    def test_inherited_proposition_preserves_the_originating_human_decision(self):
        self._confirm_identity(self.marks[0])
        origin = legend_proposition(self._item(self.marks[0]), PROPOSITION_IDENTITY)
        inherit_proposition(
            self.store, self._ws(), self.marks[1], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0],
            evidence="Same symbol and label grammar on the same sheet.",
            confidence=0.8, actor="GO")
        lineage = self._item(self.marks[1])["proposition_inheritance"][PROPOSITION_IDENTITY]
        self.assertEqual(lineage["from_legend_item_id"], self.marks[0])
        self.assertEqual(lineage["proposition"], PROPOSITION_IDENTITY)
        self.assertEqual(lineage["originating_decided_by"], "Product Owner")
        self.assertEqual(lineage["established_by"], "GO")
        self.assertEqual(lineage["confidence"], 0.8)
        self.assertIn("Same symbol", lineage["evidence"])
        self.assertEqual(lineage["inherited_value"], origin["value"])
        # The source's own decision is untouched.
        self.assertEqual(
            legend_proposition(self._item(self.marks[0]), PROPOSITION_IDENTITY)["decisions"],
            origin["decisions"])

    def test_same_as_is_a_governed_relationship_not_a_string(self):
        self._confirm_identity(self.marks[0])
        inherit_proposition(
            self.store, self._ws(), self.marks[1], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0], evidence="same convention")
        edges = [r for r in self._ws().relationships
                 if r["relationship_type"] == RELATIONSHIP_TYPE_SAME_SUBJECT_AS]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0]["from_id"], self.marks[1])
        self.assertEqual(edges[0]["to_id"], self.marks[0])
        self.assertIn(PROPOSITION_IDENTITY, edges[0]["reason"])
        self.assertFalse(edges[0]["provisional"])
        blob = repr(self._item(self.marks[1])["proposition_inheritance"])
        self.assertNotIn("#0", blob, "lineage must not store a display number")

    # -- 4. display numbering is not identity --------------------------------

    def test_display_numbering_is_derived_not_stored(self):
        self._confirm_identity(self.marks[0])
        inherit_proposition(
            self.store, self._ws(), self.marks[2], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0], evidence="same convention")
        cases = numbered_cases(self.store, self._ws(), source_id=self.source["id"])
        self.assertEqual([c["number"] for c in cases],
                         ["#01", "#02", "#03", "#04"])
        third = next(c for c in cases if c["legend_item_id"] == self.marks[2])
        identity = next(p for p in third["propositions"]
                        if p["proposition"] == PROPOSITION_IDENTITY)
        self.assertEqual(identity["same_as_display"], "#01")
        self.assertEqual(identity["same_as_legend_item_id"], self.marks[0])
        for item in self._ws().legend_items:
            self.assertNotIn("number", item)
            self.assertNotIn("display_ordinal", item)

    def test_lineage_survives_renumbering(self):
        """Reorder the listing; the durable pointer must not move."""
        self._confirm_identity(self.marks[0])
        inherit_proposition(
            self.store, self._ws(), self.marks[3], PROPOSITION_IDENTITY,
            from_legend_item_id=self.marks[0], evidence="same convention")
        workspace = self._ws()
        workspace.legend_items.reverse()
        self.store.save(workspace)
        cases = numbered_cases(self.store, self._ws(), source_id=self.source["id"])
        moved = next(c for c in cases if c["legend_item_id"] == self.marks[3])
        identity = next(p for p in moved["propositions"]
                        if p["proposition"] == PROPOSITION_IDENTITY)
        self.assertEqual(identity["same_as_legend_item_id"], self.marks[0])
        origin = next(c for c in cases if c["legend_item_id"] == self.marks[0])
        self.assertEqual(identity["same_as_display"], origin["number"])
        self.assertNotEqual(origin["number"], "#01")

    # -- 5. correction and downstream reassessment ---------------------------

    def _fan_out(self):
        self._confirm_identity(self.marks[0])
        for item_id in self.marks[1:]:
            inherit_proposition(
                self.store, self._ws(), item_id, PROPOSITION_IDENTITY,
                from_legend_item_id=self.marks[0], evidence="same convention")

    def test_dependents_are_found_for_the_right_proposition_only(self):
        self._fan_out()
        workspace = self._ws()
        identity_dependents = dependents_of_proposition(
            self.store, workspace, self.marks[0], PROPOSITION_IDENTITY)
        self.assertEqual({d["id"] for d in identity_dependents}, set(self.marks[1:]))
        self.assertEqual(
            dependents_of_proposition(self.store, workspace, self.marks[0],
                                      PROPOSITION_TARGET), [])

    def test_local_exception_does_not_reopen_unrelated_dependents(self):
        self._fan_out()
        result = break_inheritance(
            self.store, self._ws(), self.marks[2], PROPOSITION_IDENTITY,
            actor="Product Owner", reason="This one is an elevation marker.",
            broader_distinction=False)
        self.assertEqual(result["broken_as"], "local_exception")
        self.assertEqual(result["reopened"], [])
        for untouched in (self.marks[1], self.marks[3]):
            self.assertTrue(legend_proposition(
                self._item(untouched), PROPOSITION_IDENTITY)["settled"])

    def test_broader_distinction_reopens_only_affected_dependents(self):
        self._fan_out()
        # An unrelated mark that inherited nothing must be left alone.
        workspace = self._ws()
        loner = self.store.propose_legend_item(
            workspace, source_id=self.source["id"],
            page_structural_unit_id=self.unit,
            region={"x": 40.0, "y": 40.0, "width": 5.0, "height": 5.0},
            proposed_kind=LEGEND_KIND_SECTION_REFERENCE,
            proposed_meaning="unrelated", interpretation_method="test",
            actor="GO", snapshot_path=str(self.snapshot))
        result = break_inheritance(
            self.store, self._ws(), self.marks[2], PROPOSITION_IDENTITY,
            actor="Product Owner",
            reason="These are two different symbols after all.",
            broader_distinction=True)
        self.assertEqual(result["broken_as"], "broader_distinction")
        self.assertEqual(set(result["reopened"]), {self.marks[1], self.marks[3]})
        for reopened in (self.marks[1], self.marks[3]):
            self.assertEqual(self._item(reopened)["status"], LEGEND_STATUS_REVIEW_AGAIN)
        self.assertNotEqual(self._item(loner["id"])["status"], LEGEND_STATUS_REVIEW_AGAIN)
        # The ORIGIN's own human decision is never rewritten.
        self.assertEqual(self._item(self.marks[0])["status"], LEGEND_STATUS_CONFIRMED)

    def test_history_is_append_only_through_a_break(self):
        self._fan_out()
        before = len(self._item(self.marks[1])["decisions"])
        break_inheritance(
            self.store, self._ws(), self.marks[2], PROPOSITION_IDENTITY,
            actor="Product Owner", reason="different symbol",
            broader_distinction=True)
        after = self._item(self.marks[1])["decisions"]
        self.assertEqual(len(after), before + 1)
        self.assertEqual(after[-1]["action"], LEGEND_STATUS_REVIEW_AGAIN)
        self.assertIn("NEW DISTINCTION FOUND", after[-1]["note"])
        # And the broken lineage is kept, not deleted.
        lineage = self._item(self.marks[2])["proposition_inheritance"][PROPOSITION_IDENTITY]
        self.assertEqual(lineage["broken_as"], "broader_distinction")
        self.assertEqual(lineage["from_legend_item_id"], self.marks[0])
        self.assertIn("evidence", lineage)

    def test_correcting_a_target_leaves_identity_settled(self):
        self._confirm_identity(self.marks[0])
        propose_target(self.store, self._ws(), self.marks[0],
                       proposed_value="Section E on sheet E2")
        decide_proposition(self.store, self._ws(), self.marks[0],
                           PROPOSITION_TARGET, action=LEGEND_STATUS_OVERRIDDEN,
                           actor="Product Owner", value="Section E on sheet E3")
        item = self._item(self.marks[0])
        self.assertTrue(legend_proposition(item, PROPOSITION_IDENTITY)["settled"])
        self.assertEqual(legend_proposition(item, PROPOSITION_IDENTITY)["value"],
                         "A section reference marker.")
        self.assertEqual(legend_proposition(item, PROPOSITION_TARGET)["value"],
                         "Section E on sheet E3")

    # -- 6. genericity --------------------------------------------------------

    def test_no_sheet_or_project_specific_branch(self):
        service = (_REPO_ROOT / "services" / "legend_of_understanding.py").read_text(
            encoding="utf-8")
        block = service[service.index("def propose_target"):]
        for forbidden in ("E1", "E2", "Alstep", "alstep", "222109"):
            self.assertNotIn(forbidden, block)

    def test_legacy_items_without_the_new_fields_still_read(self):
        workspace = self._ws()
        for item in workspace.legend_items:
            item.pop("target_proposition", None)
            item.pop("proposition_inheritance", None)
        self.store.save(workspace)
        item = self._item(self.marks[0])
        self.assertFalse(legend_proposition(item, PROPOSITION_TARGET)["proposed"])
        self.assertIsNone(legend_proposition(item, PROPOSITION_IDENTITY)["inherited_from"])
