"""CLAUDE-GO-GREETING-CONTINUITY-01 - answer a greeting like you were here.

Product Owner, comparing the two products side by side:

    "On my ChatGPT I type: Goodmorning and the answer is 'Good morning. Ready
    to continue from where we left off' and I type 'Good morning' on ARCHIOSK
    application Composer and it says '...Working on your request...' That is
    not intelligence at all."

Two distinct failures behind one example.

1. "Goodmorning" matched NOTHING. The greeting list holds "good morning" with
   a space and compares exactly, so a missing space fell past the
   deterministic gate, cost a full model round-trip, and left them watching
   case_workspace.js's in-flight indicator - the literal
   "...Working on your request..." they reported.

2. The success case was canned: "Hello <name>. What are you working on?" - a
   question the application can already answer for itself. ChatGPT's reply
   landed because it used CONTEXT, and GO had that context and discarded it.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import mkdtemp

from services import conversation_interpreter as ci
from services.case_workspace import CaseWorkspaceStore


class ARunTogetherGreetingIsStillAGreetingTests(unittest.TestCase):
    def test_the_reported_spelling_is_recognised(self):
        self.assertTrue(ci._looks_like_conversational_utterance("goodmorning"))

    def test_other_run_together_forms_follow(self):
        for text in ("goodafternoon", "goodevening", "thankyou", "goodnight"):
            with self.subTest(text=text):
                self.assertTrue(ci._looks_like_conversational_utterance(text))

    def test_it_adds_no_vocabulary_of_its_own(self):
        """Only run-together spellings of phrases ALREADY in the list may
        match - this must not become a fuzzy matcher."""
        for text in ("goodmorningeveryone", "morningg", "gm", "sup"):
            with self.subTest(text=text):
                self.assertFalse(ci._looks_like_conversational_utterance(text))

    def test_a_real_project_message_is_never_swallowed_as_a_greeting(self):
        for text in (
            "what is the smoke control requirement",
            "good morning, can you check the sill detail",
        ):
            with self.subTest(text=text):
                self.assertFalse(ci._looks_like_conversational_utterance(text))


class TheReplyKnowsWhereWeLeftOffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(mkdtemp())
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-greet")

    def test_an_open_investigation_is_named_back(self):
        case = self.store.create_case(
            self.workspace, title="Corroded sill support",
            objective="…", created_by="mehrzad",
        )
        result = ci._handle_conversational_utterance("mehrzad", self.workspace, case)
        self.assertIn("Corroded sill support", result.reply_text)
        self.assertNotIn("What are you working on?", result.reply_text)

    def test_with_nothing_open_the_last_live_one_is_offered(self):
        self.store.create_case(self.workspace, title="Duct penetration", objective="…", created_by="m")
        result = ci._handle_conversational_utterance("mehrzad", self.workspace, None)
        self.assertIn("Duct penetration", result.reply_text)
        self.assertIn("pick that up", result.reply_text)

    def test_an_empty_project_says_something_true_rather_than_nothing(self):
        result = ci._handle_conversational_utterance("mehrzad", self.workspace, None)
        self.assertIn("Nothing registered here yet", result.reply_text)

    def test_it_still_greets_the_reviewer_by_name(self):
        result = ci._handle_conversational_utterance("mehrzad", self.workspace, None)
        self.assertTrue(result.reply_text.startswith("Hello Mehrzad."))

    def test_it_invents_no_history_when_there_is_none(self):
        """Sounding attentive by describing work that did not happen would be
        worse than the canned line it replaces."""
        result = ci._handle_conversational_utterance("mehrzad", None, None)
        self.assertEqual(result.reply_text, "Hello Mehrzad. What are you working on?")

    def test_it_costs_no_model_call(self):
        """The old path's real cost was the wait. This one is deterministic,
        so it is both better and faster than what it replaces."""
        import inspect

        src = inspect.getsource(ci._describe_where_we_left_off)
        for forbidden in ("call_llm_json", "run_conversational_turn", "answer_project_question"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, src)

    def test_an_archived_investigation_is_not_offered_back(self):
        case = self.store.create_case(self.workspace, title="Closed thing", objective="…", created_by="m")
        self.store.archive_case(self.workspace, case["id"], actor="m", actor_role="admin")
        result = ci._handle_conversational_utterance("mehrzad", self.store.get_or_create("proj-greet"), None)
        self.assertNotIn("Closed thing", result.reply_text)


if __name__ == "__main__":
    unittest.main()
