"""CLAUDE-ARTIFACT-REPLY-BOUNDARY-01 - an action proposal is not a malformed reply.

Live, in Document View, against four scanned pages:

    "combine the document into one Word document"
    -> "GO answered, but not in a form I could read, so I have not shown it.
        Nothing about your document has changed. Asking again usually works."

Nothing about the request was wrong, so asking again could not work. The model
proposed EXPORT_RECOVERED_DOCX correctly; document_conversation.ask read
parsed["answer"], found it empty, returned MALFORMED_MESSAGE and threw the
command away before the route could execute it.

THE CAUSE IS A SCHEMA CONFLICT. SYSTEM_PROMPT ends 'Answer as JSON:
{"answer": "your reply"}'; typed_action_instructions is appended AFTER it and
says to include "command". A model asked to act returns the command and no
prose, which was then classified as unusable.

Both required states are proven here against the exact utterance:
incomplete recovery must give the explicit refusal, and complete recovery must
give a readable success carrying the .docx - neither may be the generic
"asking again usually works" fallback.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import services.llm_gateway as gateway
from services import document_conversation as dc
from services import recovered_document
from services.case_workspace import CaseWorkspaceStore

UTTERANCE = "combine the document into one Word document"

COMMAND = {"action_id": "EXPORT_RECOVERED_DOCX", "parameters": {}, "user_requested": True}


class _Outcome:
    """A provider reply that carries a command and no prose - the live shape."""

    ran = True
    parse_status = None
    skipped_reason = None
    raw_text = '{"command": {...}}'

    def __init__(self, parsed):
        self.parsed = parsed


class _Case(unittest.TestCase):
    """A real document case, built through the real store."""

    def setUp(self):
        import app as app_module
        from services.case_workspace import EVIDENCE_CLASS_EXTRACTED

        self.tmp = Path(tempfile.mkdtemp(prefix="artifact_reply_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.flask_app.config["ANTHROPIC_API_KEY"] = "test-key"

        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("existentialism")
        self.workspace.display_title = "Existentialism"
        self.workspace.owner = "reader"
        self.store.save(self.workspace)

        self.evidence_class = EVIDENCE_CLASS_EXTRACTED
        self.sources = []
        for index in range(1, 5):
            source = self.store.add_source(
                self.workspace, name=f"Existentialism {index}",
                file_path=f"/tmp/scan-{index}.png", kind="drawing")
            for record in self.workspace.sources:
                if record["id"] == source["id"]:
                    # The real shape: founding page unnumbered, attachments 1..3.
                    record["intake_order"] = None if index == 1 else index - 1
            self.sources.append(source)
        self.store.save(self.workspace)

    def _recover(self, source, index):
        """Give one page usable recovered text, the way examination would."""
        unit = self.store.create_structural_unit(
            self.workspace, source_id=source["id"], unit_type="page",
            order_index=1, label=f"Page {index}", actor="tester")
        region = self.store.create_addressable_region(
            self.workspace, structural_unit_id=unit["id"], region_type="text_span",
            address={"page_index": 0, "paragraph_index": 0}, actor="tester")
        self.store.register_evidence_item(
            self.workspace, source_id=source["id"],
            evidence_class=self.evidence_class,
            content=f"Page {index}: existence precedes essence.",
            content_type="text", actor="tester", region_id=region["id"],
            extractor_version="ocr_v1")
        self.store.save(self.workspace)

    def _ask(self, parsed):
        with patch.object(gateway, "call_llm_json", return_value=_Outcome(parsed)), \
             patch.object(dc, "build_context", return_value={"recovered_text": ""}), \
             patch.object(dc, "render_prompt", return_value="prompt"):
            with self.flask_app.app_context():
                return dc.ask(None, self.workspace, {"source_id": self.sources[0]["id"]},
                              UTTERANCE, app=self.flask_app,
                              action_ids=("EXPORT_RECOVERED_DOCX",))


class ACommandWithNoProseSurvivesTheReplyBoundary(_Case):
    """The defect, stated as the property that must never hold again."""

    def test_the_command_is_not_discarded(self):
        reply = self._ask({"command": COMMAND})
        self.assertIsNotNone(reply.get("command"),
                             "a valid action proposal was thrown away as malformed")
        self.assertEqual(reply["command"]["action_id"], "EXPORT_RECOVERED_DOCX")

    def test_the_generic_retry_fallback_is_not_shown(self):
        reply = self._ask({"command": COMMAND})
        self.assertNotEqual(reply["answer"], dc.MALFORMED_MESSAGE)
        self.assertNotIn("Asking again usually works", reply["answer"])
        self.assertNotEqual(reply.get("reason"), "empty_answer")

    def test_a_reply_with_neither_prose_nor_command_is_still_malformed(self):
        """The check was not removed, only reordered."""
        reply = self._ask({"answer": "   "})
        self.assertEqual(reply["answer"], dc.MALFORMED_MESSAGE)
        self.assertEqual(reply["reason"], "empty_answer")

    def test_an_answer_with_a_command_still_carries_both(self):
        reply = self._ask({"answer": "Building it now.", "command": COMMAND})
        self.assertIsNotNone(reply.get("command"))
        self.assertEqual(reply.get("proposed_answer"), "Building it now.")


class IncompleteRecoveryGivesTheExplicitRefusal(_Case):
    """State one: no page has recovered text - the live Existentialism case."""

    def test_the_executor_refuses_and_names_every_unread_page(self):
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execution = execute_document_action(
            self.store, self.workspace, self.sources[0]["id"],
            reply["command"], "reader")

        self.assertEqual(execution["state"], "REFUSED")
        self.assertIn("No document was created", execution["answer"])
        for index in range(1, 5):
            self.assertIn(f"Existentialism {index}", execution["answer"])

    def test_the_refusal_is_not_the_generic_fallback(self):
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execution = execute_document_action(
            self.store, self.workspace, self.sources[0]["id"],
            reply["command"], "reader")
        self.assertNotIn("Asking again usually works", execution["answer"])
        self.assertIn("Re-run the examination", execution["answer"])

    def test_no_document_is_written(self):
        from services.conversation_interpreter import execute_document_action

        before = len(self.workspace.sources)
        reply = self._ask({"command": COMMAND})
        execute_document_action(self.store, self.workspace, self.sources[0]["id"],
                                reply["command"], "reader")
        self.assertEqual(len(self.store.get("existentialism").sources), before)


class CompleteRecoveryGivesAReadableArtifact(_Case):
    """State two: every page readable - a real .docx, and a readable answer."""

    def setUp(self):
        super().setUp()
        for index, source in enumerate(self.sources, start=1):
            self._recover(source, index)

    def test_the_executor_produces_a_docx_and_says_so_readably(self):
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execution = execute_document_action(
            self.store, self.workspace, self.sources[0]["id"],
            reply["command"], "reader")

        self.assertEqual(execution["state"], "EXECUTED")
        self.assertEqual(execution["action_class"], "artifact")
        self.assertIn("4 source page(s)", execution["answer"])
        self.assertNotIn("Asking again usually works", execution["answer"])

    def test_the_word_document_exists_and_holds_every_page_in_order(self):
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execution = execute_document_action(
            self.store, self.workspace, self.sources[0]["id"],
            reply["command"], "reader")

        workspace = self.store.get("existentialism")
        derivative = next(s for s in workspace.sources if s["id"] == execution["source_id"])
        self.assertTrue(derivative["name"].endswith(".docx"))
        payload = Path(derivative["file_path"]).read_bytes()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            xml = archive.read("word/document.xml").decode("utf-8")
        positions = [xml.index(f"Page {i}: existence precedes essence.") for i in range(1, 5)]
        self.assertEqual(positions, sorted(positions), "pages are out of order in the .docx")

    def test_the_originals_are_preserved(self):
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execute_document_action(self.store, self.workspace, self.sources[0]["id"],
                                reply["command"], "reader")
        workspace = self.store.get("existentialism")
        for source in self.sources:
            record = next(s for s in workspace.sources if s["id"] == source["id"])
            self.assertIsNone(record.get("removed_at"))

    def test_the_file_is_reachable_through_the_existing_download_route(self):
        """No new endpoint: it is a Source, so source_file already serves it."""
        from services.conversation_interpreter import execute_document_action

        reply = self._ask({"command": COMMAND})
        execution = execute_document_action(
            self.store, self.workspace, self.sources[0]["id"],
            reply["command"], "reader")
        workspace = self.store.get("existentialism")
        derivative = next(s for s in workspace.sources if s["id"] == execution["source_id"])
        self.assertTrue(Path(derivative["file_path"]).is_file())
        self.assertEqual(derivative["origin_type"], "derived_recovered_document")


class TheTwoInstructionsNoLongerContradict(unittest.TestCase):
    def test_the_action_block_requires_the_answer_field_too(self):
        from services.conversational_turn import typed_action_instructions

        text = typed_action_instructions(("EXPORT_RECOVERED_DOCX",))
        self.assertIn('ALWAYS include the "answer" field', text)


if __name__ == "__main__":
    unittest.main()
