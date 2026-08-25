"""CLAUDE-GO-GATEWAY-COGNITION-01 - the project-less Composer can think too.

Product Owner: 'I typed "How do I clean my phone memory so the websites load
freshly" and the response is: "I can help you open an existing project or start
a new one. Open a project to ask about its documents."'

Not an accident. `_classify_gateway_orientation` was a rule-based NAVIGATION
responder with no cognition at all: it matched a project name, or "new
project", and everything else on earth fell into one canned sentence.

Three failures in one reply, worth separating because only the third is really
damning:

  1. it did not answer;
  2. it did not say it could not answer;
  3. it answered a DIFFERENT question instead, which reads as not having
     listened.

The navigation rules keep first refusal - they are deterministic, instant, and
right about what this surface is mainly for. Only the fallback changed.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from unittest.mock import patch

import routes.portal as portal

ROOT = Path(__file__).resolve().parents[1]


def _outcome(answer=None):
    return type("R", (), {
        "ran": bool(answer), "answer": answer,
        "provider": "x", "model": "y", "needs_clarification": False,
    })()


class _Base(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.app = app_module.create_app("testing")

    def ask(self, message, projects=(), can_create=True, model_answer=None):
        with self.app.test_request_context("/"):
            with patch.object(portal, "answer_orientation_question",
                              return_value=_outcome(model_answer)) as spy:
                result = portal._classify_gateway_orientation(
                    message, list(projects), can_create,
                )
        return result, spy


class NavigationStillWinsFirstTests(_Base):
    """Deterministic, instant, and right about what this surface is for. The
    fix must not have cost that."""

    def test_a_project_name_still_opens_it(self):
        result, spy = self.ask(
            "Smoke Detector", projects=[{"display_name": "Smoke Detector", "project_id": "p1"}],
        )
        self.assertEqual(result["kind"], "navigate")
        self.assertFalse(spy.called, "a model call was spent on plain navigation")

    def test_new_project_still_navigates(self):
        result, spy = self.ask("new project")
        self.assertEqual(result["kind"], "navigate")
        self.assertFalse(spy.called)

    def test_an_empty_message_still_prompts(self):
        result, spy = self.ask("   ")
        self.assertEqual(result["kind"], "info")
        self.assertFalse(spy.called)


class ItAnswersWhatItCanTests(_Base):
    def test_a_capability_question_is_answered_without_a_model(self):
        """"How do I upload a photo" needs no project and no model - it is
        already answered with numbered steps."""
        result, spy = self.ask("how do I upload a photo")
        self.assertIn("Tap the + beside the message box", result["text"])
        self.assertFalse(spy.called, "spent a model call on a known answer")

    def test_an_application_question_reaches_the_existing_seam(self):
        result, spy = self.ask("what is a Q in this application",
                               model_answer="A Q is an inquiry you are working.")
        self.assertEqual(result["text"], "A Q is an inquiry you are working.")
        self.assertTrue(spy.called)

    def test_a_very_short_message_does_not_cost_a_model_call(self):
        """Two words are far more likely to be a half-typed project name than
        a question worth transmitting."""
        _, spy = self.ask("hmm ok")
        self.assertFalse(spy.called)


class ItSaysSoWhenItCannotTests(_Base):
    def test_the_reported_message_no_longer_gets_a_non_sequitur(self):
        result, _ = self.ask("How do I clean my phone memory so the websites load freshly")
        text = result["text"]
        # It must say it cannot help BEFORE describing what it can do.
        self.assertIn("not something I can help with", text)
        self.assertLess(text.index("not something I can help with"), text.index("open one of your"))

    def test_it_no_longer_opens_by_offering_to_open_a_project(self):
        """The exact shape that read as not having listened."""
        result, _ = self.ask("How do I clean my phone memory so the websites load freshly")
        self.assertFalse(result["text"].startswith("I can help you open an existing project"))

    def test_a_model_that_declines_falls_through_honestly(self):
        result, spy = self.ask("something entirely unrelated to construction work", model_answer=None)
        self.assertTrue(spy.called)
        self.assertIn("not something I can help with", result["text"])

    def test_a_failing_model_call_never_500s_this_surface(self):
        with self.app.test_request_context("/"):
            with patch.object(portal, "answer_orientation_question", side_effect=RuntimeError("boom")):
                result = portal._classify_gateway_orientation("tell me about something", [], True)
        self.assertEqual(result["kind"], "info")
        self.assertIn("not something I can help with", result["text"])


class TheProjectBoundaryIsUnchangedTests(unittest.TestCase):
    """This is a project-LESS surface. The reason adding cognition here is safe
    is that the seam it reaches cannot touch project state at all."""

    def test_the_gateway_responder_never_opens_a_project(self):
        source = inspect_source()
        for forbidden in ("CaseWorkspaceStore", "get_or_create", "interpret_message",
                          "add_message", "create_case"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, source)

    def test_the_seam_it_uses_takes_no_workspace_or_store(self):
        import inspect as inspect_module

        from services.project_qa import answer_orientation_question

        parameters = inspect_module.signature(answer_orientation_question).parameters
        self.assertNotIn("workspace", parameters)
        self.assertNotIn("store", parameters)


class ItDoesNotBorrowDeveloperModesVoiceTests(unittest.TestCase):
    """CLAUDE-GO-GATEWAY-COGNITION-02. The first version of this fix pointed
    the Gateway at `answer_application_question` - a DEVELOPER MODE function.
    Its system prompt casts the model as a Developer Mode assistant and its
    user prompt carries repository internals: module paths, service names, CSS
    class names.

    The Product Owner saw the symptom ("this question is outside ARCHIOSK's
    application scope" prefixed to a real answer). The leak underneath it was
    not reported because it had not yet been triggered, which is the more
    dangerous half.
    """

    def test_the_gateway_uses_its_own_seam(self):
        source = inspect_source()
        self.assertIn("answer_orientation_question", source)
        self.assertNotIn("answer_application_question", source)

    def test_the_orientation_contract_carries_no_repository_facts(self):
        from services.project_qa import ORIENTATION_CONTRACT

        # "module" is deliberately NOT in this list: the contract's own
        # instruction is "never describe ARCHIOSK's internal code, files,
        # modules, or styling" - the word appears because it is FORBIDDING the
        # leak, not committing it. Same prose-versus-behaviour trap as ever.
        for leak in ("routes/", "services/", ".py", "css", "Developer Mode"):
            with self.subTest(leak=leak):
                self.assertNotIn(leak, ORIENTATION_CONTRACT)

    def test_it_forbids_the_defensive_opener_explicitly(self):
        """Leading with a disclaimer and then answering is the same failure
        CLAUDE-POSTCAMEL-CA1C already ruled on - "opening with 'only you can
        decide' instead of a recommendation". Either answer or decline."""
        from services.project_qa import ORIENTATION_CONTRACT

        self.assertIn("NEVER open with a disclaimer", ORIENTATION_CONTRACT)
        self.assertIn("never both", ORIENTATION_CONTRACT)

    def test_it_is_told_not_to_describe_internals(self):
        from services.project_qa import ORIENTATION_CONTRACT

        self.assertIn("Never describe ARCHIOSK's internal code", ORIENTATION_CONTRACT)

    def test_the_developer_seam_is_still_intact_for_developer_mode(self):
        """Repointing the Gateway must not have damaged the surface that
        legitimately wants that persona."""
        from services.project_qa import answer_application_question

        self.assertTrue(callable(answer_application_question))


def inspect_source() -> str:
    """The responder's own CODE, docstring and comments stripped.

    Its docstring names every boundary it honours, so a bare substring check
    would happily accept the explanation as evidence of the behaviour - a trap
    this session has fallen into repeatedly.
    """
    import ast
    import inspect as inspect_module
    import textwrap

    source = textwrap.dedent(inspect_module.getsource(portal._classify_gateway_orientation))
    tree = ast.parse(source)
    function = tree.body[0]
    if (function.body and isinstance(function.body[0], ast.Expr)
            and isinstance(function.body[0].value, ast.Constant)
            and isinstance(function.body[0].value.value, str)):
        function.body = function.body[1:]
    return ast.unparse(tree)


if __name__ == "__main__":
    unittest.main()
