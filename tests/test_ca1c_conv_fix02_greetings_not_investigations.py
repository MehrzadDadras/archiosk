"""
CLAUDE-CA1C-CONV-FIX-02 - Greetings Must Not Enter Investigation Attention.

A real Product Owner typed "hello"/"hello hello" into Project Home's
composer and watched GO create a brand-new Investigation for it, which
then immediately tripped the four-Investigation attention limit's own
"Attention is full" dialog (static/js/investigation_attention.js,
templates/case_workspace.html's #attention-capacity-dialog) - just to say
hello. That attention mechanism is entirely client-side (a localStorage
set, MAX_ATTENTION = 4 - see tests/test_p40vw7b_vestibule_and_attention.py),
so it cannot be exercised directly from this Flask-test-client suite -
but its trigger condition is opening a NEWLY CREATED Case, which routes/
workspace.py's quick_start decides server-side. Proving a greeting never
creates that Case at all is the necessary and sufficient server-side fact:
with no new Case, there is nothing for the client-side attention strip to
even attempt to open, regardless of how many Investigations are already
attended.

Run via:

    python -m unittest tests.test_ca1c_conv_fix02_greetings_not_investigations -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.conversation_interpreter import (
    _handle_conversational_utterance,
    _looks_like_conversational_utterance,
)
from services.requirements_registry import RequirementsRegistry

# The exact examples this stage's own governing report names, plus the
# two live-reproduced literal inputs ("hello", "hello hello").
GREETINGS = [
    "hello", "hello hello", "hi", "good morning", "how are you?",
    "do you hear me?", "thanks", "okay", "got it",
]


class ConversationalUtteranceDetectionTests(unittest.TestCase):
    """Unit-level: the deterministic classifier itself, independent of
    any route/store plumbing."""

    def test_every_governing_example_is_recognized(self):
        for text in GREETINGS:
            with self.subTest(text=text):
                self.assertTrue(_looks_like_conversational_utterance(text.lower()), text)

    def test_a_real_work_request_is_not_misclassified_as_a_greeting(self):
        work_requests = [
            "Analyze this drawing for datum inconsistencies",
            "Compare the two specifications",
            "Why is this requirement missing electrical scope?",
            "What is the RFP submission deadline?",
            "Can you suggest how to divide the main file?",
        ]
        for text in work_requests:
            with self.subTest(text=text):
                self.assertFalse(_looks_like_conversational_utterance(text.lower()), text)

    def test_handler_personalizes_with_a_real_reviewer_name_and_asks_what_next(self):
        result = _handle_conversational_utterance("mehrzad")
        self.assertEqual(result.action_taken, "conversational_utterance")
        self.assertIn("Mehrzad", result.reply_text)
        self.assertIn("What are you working on?", result.reply_text)

    def test_handler_degrades_gracefully_for_an_anonymous_reviewer(self):
        result = _handle_conversational_utterance("anonymous")
        self.assertEqual(result.reply_text, "Hello. What are you working on?")


class GreetingsDoNotCreateInvestigationsTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1c_conv_fix02_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-conv-fix02"

        with self.flask_app.app_context():
            db.session.add(User(username="mehrzad", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="The system shall do a thing.", category="other", confidence=0.6, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "mehrzad"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.set_project_owner(self.store.get(self.project_id), owner="mehrzad", actor="mehrzad")

        # "even when all four attention slots are occupied" - attention
        # itself is client-side (see this file's own module docstring),
        # but four already-existing real Investigations is the closest,
        # most meaningful server-side proxy for that precondition, and
        # this fix must hold regardless of how many already exist.
        workspace = self.store.get(self.project_id)
        for i in range(4):
            self.store.create_case(workspace, title=f"Pre-existing Investigation {i + 1}", objective="", created_by="mehrzad")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_greeting_creates_a_fifth_investigation(self):
        for text in GREETINGS:
            with self.subTest(text=text):
                resp = self.client.post(
                    f"/projects/{self.project_id}/workspace/quick-start",
                    data={"text": text},
                )
                self.assertEqual(resp.status_code, 302)
                self.assertNotIn("case=", resp.headers["Location"])
                workspace = self.store.get(self.project_id)
                self.assertEqual(len(workspace.cases), 4, f"{text!r} created a Case")

    def test_greeting_gets_the_friendly_reply_not_a_project_evidence_answer(self):
        self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "hello"},
        )
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        self.assertEqual(last_reply["role"], "system")
        self.assertIn("Mehrzad", last_reply["text"])
        self.assertIn("What are you working on?", last_reply["text"])
        self.assertNotIn("Not covered by this project's extracted evidence", last_reply["text"])

    def test_repeated_greeting_word_also_does_not_create_an_investigation(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "hello hello"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("case=", resp.headers["Location"])
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.cases), 4)

    def test_a_real_work_request_still_creates_an_investigation_as_before(self):
        """Non-regression: this gate must not overreach into genuine
        investigative intent."""
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Analyze the electrical drawings for datum inconsistencies"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertIn("case=", resp.headers["Location"])
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.cases), 5)


if __name__ == "__main__":
    unittest.main()
