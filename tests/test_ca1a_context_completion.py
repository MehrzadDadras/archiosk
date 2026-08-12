"""
CLAUDE-POSTCAMEL-CA1A - Conversational Context Completion / See Where I Am.

Completes three items CA1 deferred: ambient/current-view awareness,
token-aware conversation budgeting, and a fuller (but still bounded)
action dispatcher. Implements, as the smallest safe slice:

  - a real context envelope (current_view + selected_source_id) carried
    on the ONE shared conversation composer, re-validated server-side
    against the active Project before ever being trusted;
  - a deterministic (no model call) contextual-reference handler
    resolving "tell me about this"/"what should I do with this"/etc.
    against a real anchor or genuinely-selected Source, with an honest
    "nothing selected" reply when neither is real - never a guessed
    referent, and never an unnecessary model call for a question this
    module already knows it cannot ground;
  - a token-aware (character-budget, not fixed-count) history window;
  - a fuller dispatcher that reuses the EXISTING, already-tested
    `needs_case:` "Start an Investigation from this" escalation rather
    than building a second action-execution path, and only ever offers
    it when no Case is already open (never a surprise Investigation).

Run via:

    python -m unittest tests.test_ca1a_context_completion -v
"""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import (
    ANALYSIS_TRIGGER_USER_INITIATED,
    AnalysisTrigger,
    CaseWorkspaceStore,
)
from services.conversation_interpreter import _looks_like_contextual_reference, _looks_like_what_next
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload
from services.conversational_turn import build_bounded_history as _select_bounded_history


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1a_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="ca1a_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="ca1a_owner", project_name="CA1A Context Test Project")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "founding.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"founding content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "ca1a_owner"
            sess["role"] = "admin"
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)

    def _discuss(self, client, text: str, **extra):
        data = {"text": text}
        data.update(extra)
        return client.post(f"/projects/{self.project_id}/workspace/discuss", data=data)

    def _register_requirement(self, identifier: str = "REQ-1") -> str:
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        workspace = self._store().register_requirement(
            workspace, source_id=source_id, original_requirement_identifier=identifier,
            text_reference=f"The system shall {identifier}.", created_by="ca1a_owner",
            registration_method="human_registered",
        )
        return next(r["id"] for r in self._store().get(self.project_id).requirements
                    if r["original_requirement_identifier"] == identifier)

    def _create_finding(self) -> str:
        store = self._store()
        workspace = store.get(self.project_id)
        case = store.create_case(workspace, title="A Case", objective="", created_by="ca1a_owner")
        workspace = store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        analysis = store.record_analysis(
            workspace, source_ids=[source_id], objective="test",
            engine_name="test-engine", engine_version="1",
            findings=[{"statement": "The datum appears inconsistent.", "machine_confidence": 0.7}],
            trigger=AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="ca1a_owner"),
            case_id=case["id"],
        )
        return analysis["finding_ids"][0]


class PhraseDetectionTests(unittest.TestCase):
    def test_recognizes_contextual_reference_phrases(self):
        for phrase in ("tell me about this", "What am I looking at?", "show me the evidence for this"):
            self.assertTrue(_looks_like_contextual_reference(phrase.lower()), phrase)

    def test_recognizes_what_next_phrases(self):
        for phrase in ("what should i do next", "What should I do?", "what next?"):
            self.assertTrue(_looks_like_what_next(phrase.lower()), phrase)


class TokenAwareHistoryTests(unittest.TestCase):
    def test_budget_favors_recent_turns_and_drops_oldest_first(self):
        history = [{"role": "human", "text": "x" * 500} for _ in range(10)]
        selected = _select_bounded_history(history)
        self.assertLessEqual(len(selected), 10)
        total_chars = sum(len(m["text"]) for m in selected)
        self.assertLessEqual(total_chars, 2000)
        # The LAST selected message must be the most recent original one.
        self.assertEqual(selected[-1]["text"], history[-1]["text"][:300])

    def test_keeps_at_least_one_message_even_if_it_alone_exceeds_budget(self):
        history = [{"role": "human", "text": "y" * 10000}]
        selected = _select_bounded_history(history)
        self.assertEqual(len(selected), 1)

    def test_chronological_order_preserved(self):
        history = [{"role": "human", "text": f"msg{i}"} for i in range(5)]
        selected = _select_bounded_history(history)
        texts = [m["text"] for m in selected]
        self.assertEqual(texts, sorted(texts, key=lambda t: int(t.replace("msg", ""))))


class AnchoredContextTests(_BaseTestCase):
    def test_anchored_requirement_tell_me_about_this(self):
        req_id = self._register_requirement("REQ-1")
        client = self._client()
        self._discuss(client, "tell me about this", anchor_type="requirement", anchor_id=req_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-1", body)
        self.assertIn("Start an Investigation from this", body)

    def test_anchored_finding_tell_me_about_this(self):
        finding_id = self._create_finding()
        client = self._client()
        self._discuss(client, "tell me about this", anchor_type="finding", anchor_id=finding_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("datum appears inconsistent", body)

    def test_stale_cross_project_anchor_is_rejected_honestly(self):
        """A Requirement id from a genuinely different Project must never
        be accepted just because it's submitted while this Project is
        active - the exact Section 3 cross-project injection guard."""
        other_doc = self._ingest(owner="ca1a_owner", project_name="CA1A Other Project")
        foreign_req_id = self._register_requirement_in(other_doc.project_id, "FOREIGN-1")

        client = self._client()
        self._discuss(client, "tell me about this", anchor_type="requirement", anchor_id=foreign_req_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("no longer exists in this Project", body)
        self.assertNotIn("FOREIGN-1", body)

    def _register_requirement_in(self, project_id: str, identifier: str) -> str:
        store = self._store()
        workspace = store.get(project_id)
        source_id = workspace.sources[0]["id"]
        store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier=identifier,
            text_reference=f"The system shall {identifier}.", created_by="ca1a_owner",
            registration_method="human_registered",
        )
        return next(r["id"] for r in store.get(project_id).requirements
                    if r["original_requirement_identifier"] == identifier)

    def test_contextual_reference_phrase_in_main_composer_does_not_create_a_surprise_case(self):
        """Real regression found live during this stage's own Walkthrough
        B: quick_start's own Case-vs-project-level routing check didn't
        know about the new contextual-reference/what-next phrases, so
        "Show me the evidence for this" typed into the MAIN composer
        (with no anchor attached) silently created a brand-new surprise
        Case - the exact same bug class CA1 already fixed once for
        "orient me"."""
        client = self._client()
        client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Show me the evidence for this"},
        )
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.cases, [])

    def test_what_next_phrase_in_main_composer_does_not_create_a_surprise_case(self):
        client = self._client()
        client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "What should I do next?"},
        )
        workspace = self._store().get(self.project_id)
        self.assertEqual(workspace.cases, [])

    def test_no_surprise_investigation_offered_when_case_already_open(self):
        """The needs_case escalation must never be offered when a Case is
        already open - CA1's own quick_start lesson, preserved. Exercised
        directly against interpret_message: post_message (the real
        Case-scoped composer route) has no anchor form fields at all
        today, so this exact combination (an anchor while a Case is
        open) has no live HTTP path to drive it through - the guard
        itself is still real production code, worth testing directly."""
        from pathlib import Path as _Path
        from services.conversation_interpreter import interpret_message

        req_id = self._register_requirement("REQ-2")
        store = self._store()
        workspace = store.get(self.project_id)
        case = store.create_case(workspace, title="Open Case", objective="", created_by="ca1a_owner")

        result = interpret_message(
            text="tell me about this", workspace=workspace, case=case, store=store,
            artifacts_dir=self.tmp_dir, reviewer="ca1a_owner", focused_finding_id=None,
            triggering_message_id="msg-1",
            anchor={"anchor_type": "requirement", "anchor_id": req_id},
        )
        self.assertIn("REQ-2", result.reply_text)
        self.assertFalse(result.action_taken.startswith("needs_case:"))


class SelectedSourceContextTests(_BaseTestCase):
    def test_investigation_escalation_replays_the_original_selected_source(self):
        """Real regression found live during this stage's own Walkthrough
        A: escalating a Source-selection-grounded reply into a new
        Investigation (start_investigation_from_aperture) used to lose
        the original selected_source_id entirely (only `anchor` was ever
        replayed), so the re-run silently produced the honest-but-wrong
        "nothing specific selected" reply instead of the original,
        correct, Source-grounded one."""
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        source_name = workspace.sources[0]["name"]
        client = self._client()
        self._discuss(client, "what can i do with this", selected_source_id=source_id)

        workspace = self._store().get(self.project_id)
        message_id = next(
            m["id"] for m in workspace.project_conversation if m["text"] == "what can i do with this"
        )
        resp = client.post(f"/projects/{self.project_id}/workspace/apertures/{message_id}/start-investigation")
        self.assertEqual(resp.status_code, 302)

        case_id = resp.headers["Location"].split("case=")[-1]
        body = client.get(f"/projects/{self.project_id}/workspace?case={case_id}").get_data(as_text=True)
        self.assertIn(source_name, body)
        self.assertNotIn("don&#39;t have anything specific selected", body)

    def test_selected_source_answers_what_should_i_do_with_this(self):
        workspace = self._store().get(self.project_id)
        source_id = workspace.sources[0]["id"]
        source_name = workspace.sources[0]["name"]
        client = self._client()
        self._discuss(client, "what should i do with this", selected_source_id=source_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn(source_name, body)

    def test_stale_selected_source_id_degrades_to_no_selection(self):
        client = self._client()
        self._discuss(client, "tell me about this", selected_source_id="not-a-real-id")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("don&#39;t have anything specific selected", body)

    def test_selected_source_id_never_crosses_projects(self):
        other_doc = self._ingest(owner="ca1a_owner", project_name="CA1A Another Project")
        other_source_id = self._store().get(other_doc.project_id).sources[0]["id"]

        client = self._client()
        self._discuss(client, "tell me about this", selected_source_id=other_source_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("don&#39;t have anything specific selected", body)


class AmbiguousReferenceTests(_BaseTestCase):
    def test_ambiguous_this_with_no_selection_is_honest_not_guessed(self):
        client = self._client()
        self._discuss(client, "tell me about this")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("don&#39;t have anything specific selected", body)
        self.assertIn("Open Files", body)


class WhatShouldIDoNextTests(_BaseTestCase):
    def test_falls_back_to_orientation_with_no_context(self):
        client = self._client()
        self._discuss(client, "what should i do next")
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("registered project source", body)

    def test_uses_anchor_context_when_available(self):
        req_id = self._register_requirement("REQ-3")
        client = self._client()
        self._discuss(client, "what should i do next", anchor_type="requirement", anchor_id=req_id)
        body = client.get(f"/projects/{self.project_id}/workspace?view=conversation").get_data(as_text=True)
        self.assertIn("REQ-3", body)


class CurrentViewInPromptTests(_BaseTestCase):
    def test_current_view_appears_in_the_real_prompt(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "Answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            client = self._client()
            self._discuss(client, "What are the objectives of this RFP?", current_view="files")

            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertIn("Current Display view: files", prompt)

    def test_unknown_current_view_is_not_trusted(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv", side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(
                '{"answer": "Answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            client = self._client()
            self._discuss(client, "What are the objectives of this RFP?", current_view="some-fabricated-view")

            prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
            self.assertNotIn("some-fabricated-view", prompt)


if __name__ == "__main__":
    unittest.main()
