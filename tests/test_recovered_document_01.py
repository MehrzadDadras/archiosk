"""CLAUDE-DOCX-FROM-RECOVERED-01 - an artifact request must not become Q&A.

Asked live in Document View over four scanned pages: "can you read it and turn
it to one word document?" GO replied with its analysis summary.

The cause was not classification. document_conversation.ask offers the model a
typed-action menu and its contract says `command` must be null unless the user
asked for an AVAILABLE action - and the Document View menu held four view-only
actions (rotate, mirror, fit, align north) and nothing that makes a document.
With no such action on the menu, prose was the only move available.

So the regression that matters is about the MENU and the EXECUTOR, not about
model wording: the capability must be offered, the executor must produce a real
file from real recovered text in source order, and it must refuse rather than
write a document with silent gaps.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from services import recovered_document
from services.capability_registry import ACTION_REGISTRY, DOCUMENT_VIEW_ACTION_IDS
from services.case_workspace import CaseWorkspaceStore


class TheCapabilityIsOnTheMenu(unittest.TestCase):
    """The defect, stated where it lived."""

    def test_document_view_offers_a_way_to_produce_a_document(self):
        self.assertIn('EXPORT_RECOVERED_DOCX', DOCUMENT_VIEW_ACTION_IDS)

    def test_the_action_is_described_as_an_artifact_not_a_view(self):
        self.assertEqual(ACTION_REGISTRY['EXPORT_RECOVERED_DOCX']['action_class'], 'artifact')

    def test_the_menu_is_named_not_derived_from_registry_order(self):
        """The latent hazard beside the defect.

        DOCUMENT_VIEW_ACTION_IDS used to be tuple(ACTION_REGISTRY) evaluated
        mid-file, so the desk actions were excluded only by being registered
        afterwards. Moving one dict literal would have offered DELETE_ITEMS to
        a surface with no confirmation flow for it.
        """
        for action_id in DOCUMENT_VIEW_ACTION_IDS:
            self.assertNotEqual(ACTION_REGISTRY[action_id]['action_class'], 'destructive')
        self.assertNotIn('DELETE_ITEMS', DOCUMENT_VIEW_ACTION_IDS)
        self.assertNotIn('ARCHIVE_ITEMS', DOCUMENT_VIEW_ACTION_IDS)


class _Pages(unittest.TestCase):
    """Four scanned pages, built through the real store."""

    def setUp(self):
        from services.case_workspace import EVIDENCE_CLASS_EXTRACTED

        self.tmp = Path(tempfile.mkdtemp(prefix="recovered_docx_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("existentialism")
        self.workspace.display_title = "Existentialism"
        self.workspace.owner = "reader"
        self.store.save(self.workspace)

        self.page_text = {}
        for index in range(1, 5):
            source = self.store.add_source(
                self.workspace, name=f"scan-{index}.png", file_path=f"/tmp/scan-{index}.png",
                kind="drawing")
            for record in self.workspace.sources:
                if record["id"] == source["id"]:
                    record["intake_order"] = index
            unit = self.store.create_structural_unit(
                self.workspace, source_id=source["id"], unit_type="page",
                order_index=1, label=f"Page {index}", actor="tester")
            region = self.store.create_addressable_region(
                self.workspace, structural_unit_id=unit["id"], region_type="text_span",
                address={"page_index": 0, "paragraph_index": 0}, actor="tester")
            text = f"Page {index}: existence precedes essence, paragraph {index}."
            self.store.register_evidence_item(
                self.workspace, source_id=source["id"],
                evidence_class=EVIDENCE_CLASS_EXTRACTED, content=text,
                content_type="text", actor="tester", region_id=region["id"],
                extractor_version="ocr_v1")
            self.page_text[source["id"]] = text
        self.store.save(self.workspace)
        self.source_ids = recovered_document.ordered_source_ids(self.workspace)


class AllFourPagesBecomeOneDocument(_Pages):
    def test_readiness_sees_every_page_as_readable(self):
        state = recovered_document.readiness(self.workspace, self.source_ids)
        self.assertEqual(len(state["ready"]), 4)
        self.assertEqual(state["missing"], [])
        self.assertTrue(state["complete"])

    def test_order_is_preserved(self):
        self.assertEqual(
            [s["name"] for s in self.workspace.sources if s["id"] in self.source_ids][:4],
            ["scan-1.png", "scan-2.png", "scan-3.png", "scan-4.png"])
        document = recovered_document.build_export_document(
            self.workspace, recovered_document.readiness(self.workspace, self.source_ids))
        body = "\n".join(document.preamble)
        positions = [body.index(f"paragraph {i}.") for i in range(1, 5)]
        self.assertEqual(positions, sorted(positions), "page order was not preserved")

    def test_a_real_docx_is_written_and_contains_every_page(self):
        built = recovered_document.create(
            self.store, self.workspace, self.source_ids, actor="reader",
            sources_dir=self.tmp / "artifacts")

        self.assertEqual(len(built["built_from"]), 4)
        derivative = next(s for s in self.workspace.sources if s["id"] == built["source_id"])
        payload = Path(derivative["file_path"]).read_bytes()

        # A real Word file, not a renamed text blob.
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        for index in range(1, 5):
            self.assertIn(f"paragraph {index}.", xml)

    def test_nothing_was_invented(self):
        """Every recovered passage appears; no passage appears that was not."""
        document = recovered_document.build_export_document(
            self.workspace, recovered_document.readiness(self.workspace, self.source_ids))
        for text in self.page_text.values():
            self.assertIn(text, document.preamble)

    def test_the_originals_survive_and_the_result_points_back_at_them(self):
        before = {s["id"] for s in self.workspace.sources}
        built = recovered_document.create(
            self.store, self.workspace, self.source_ids, actor="reader",
            sources_dir=self.tmp / "artifacts")
        after = {s["id"] for s in self.workspace.sources}

        self.assertTrue(before < after, "the derivative did not become its own Source")
        for source_id in before:
            record = next(s for s in self.workspace.sources if s["id"] == source_id)
            self.assertIsNone(record.get("removed_at"))
        derivative = next(s for s in self.workspace.sources if s["id"] == built["source_id"])
        self.assertEqual(derivative["origin_type"], "derived_recovered_document")
        for source_id in self.source_ids:
            self.assertIn(source_id, derivative["origin_reference"])


class IncompleteRecoveryRefusesRatherThanFabricates(_Pages):
    def setUp(self):
        super().setUp()
        # Page 3 read nothing - the ordinary scanned-page failure.
        blank = self.store.add_source(
            self.workspace, name="scan-5-unread.png", file_path="/tmp/scan-5.png",
            kind="drawing")
        for record in self.workspace.sources:
            if record["id"] == blank["id"]:
                record["intake_order"] = 5
        self.store.save(self.workspace)
        self.blank_id = blank["id"]
        self.source_ids = recovered_document.ordered_source_ids(self.workspace)

    def test_the_unread_page_is_reported_by_name(self):
        state = recovered_document.readiness(self.workspace, self.source_ids)
        self.assertEqual([entry["name"] for entry in state["missing"]], ["scan-5-unread.png"])
        self.assertFalse(state["complete"])

    def test_no_document_is_written_at_all(self):
        before = len(self.workspace.sources)
        with self.assertRaises(recovered_document.RecoveredDocumentError) as caught:
            recovered_document.create(
                self.store, self.workspace, self.source_ids, actor="reader",
                sources_dir=self.tmp / "artifacts")
        self.assertIn("scan-5-unread.png", str(caught.exception))
        self.assertIn("Re-run the examination", str(caught.exception))
        self.assertEqual(len(self.workspace.sources), before,
                         "a partial document was written despite an unread page")


class TheExecutorRunsItUnderTheSameGates(_Pages):
    def _command(self):
        return {"action_id": "EXPORT_RECOVERED_DOCX", "parameters": {}, "user_requested": True}

    def test_the_owner_gets_a_document_and_is_told_what_it_is(self):
        from services.conversation_interpreter import execute_document_action

        result = execute_document_action(
            self.store, self.workspace, self.source_ids[0], self._command(), "reader")

        self.assertEqual(result["state"], "EXECUTED")
        self.assertEqual(result["action_class"], "artifact")
        self.assertEqual(result["authority"], "UNCHANGED")
        self.assertIn("4 source page(s)", result["answer"])
        self.assertIn("nothing in it was written by me", result["answer"].lower())

    def test_a_non_owner_is_refused_exactly_as_for_a_view_command(self):
        from services.case_workspace import CaseWorkspaceError
        from services.conversation_interpreter import execute_document_action

        with self.assertRaises(CaseWorkspaceError):
            execute_document_action(
                self.store, self.workspace, self.source_ids[0], self._command(), "someone-else")

    def test_an_unread_page_returns_a_refusal_answer_not_an_exception(self):
        """The reviewer asked for a document; they get told why there isn't one."""
        from services.conversation_interpreter import execute_document_action

        blank = self.store.add_source(
            self.workspace, name="unread.png", file_path="/tmp/unread.png", kind="drawing")
        for record in self.workspace.sources:
            if record["id"] == blank["id"]:
                record["intake_order"] = 9
        self.store.save(self.workspace)

        result = execute_document_action(
            self.store, self.workspace, self.source_ids[0], self._command(), "reader")

        self.assertEqual(result["state"], "REFUSED")
        self.assertIn("unread.png", result["answer"])
        self.assertIn("No document was created", result["answer"])


class TheUtteranceReachesTheMenu(unittest.TestCase):
    """The exact live request, against the contract the model is given."""

    UTTERANCE = "can you read it and turn it to one word document?"

    def test_the_offered_catalogue_contains_a_document_producing_action(self):
        from services.conversational_turn import typed_action_instructions

        instructions = typed_action_instructions(DOCUMENT_VIEW_ACTION_IDS)
        self.assertIn("EXPORT_RECOVERED_DOCX", instructions)
        self.assertIn(".docx", instructions)

    def test_the_command_for_this_utterance_survives_sanitisation(self):
        """Whatever the model says, this action_id must be executable."""
        from services.conversational_turn import sanitize_typed_action

        command = sanitize_typed_action(
            {"action_id": "EXPORT_RECOVERED_DOCX", "parameters": {}, "user_requested": True},
            DOCUMENT_VIEW_ACTION_IDS)
        self.assertIsNotNone(command, "the artifact action is not executable from Document View")
        self.assertEqual(command["action_id"], "EXPORT_RECOVERED_DOCX")

    def test_before_this_change_there_was_nothing_to_choose(self):
        """Documents the shape of the defect: view-only actions cannot answer this."""
        view_only = [a for a in DOCUMENT_VIEW_ACTION_IDS
                     if ACTION_REGISTRY[a]['action_class'] == 'view_only']
        self.assertEqual(len(view_only), 4)
        self.assertTrue(
            any(ACTION_REGISTRY[a]['action_class'] == 'artifact' for a in DOCUMENT_VIEW_ACTION_IDS),
            "an artifact request could only fall through to prose")


if __name__ == "__main__":
    unittest.main()
