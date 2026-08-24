"""CLAUDE-GO-COGNITION-FIRST-01 - a click must not cost you an answer.

Product Owner: "This application must start and stop with intelligence
otherwise has 0 value for me."

The measured cause was not the prompt, and not the model. `interpret_message`
runs twenty deterministic branches before the model-backed seam is reached at
all, and one of them returned a canned template whenever an Anchor was set:

    if anchor is not None:
        return InterpretationResult(
            action_taken="anchor_acknowledged",
            reply_text=_describe_anchor_acknowledgment(anchor),
        )

An Anchor is set whenever the reviewer has CLICKED something - which is how
anyone actually asks about a drawing, a Source, a Requirement or a Finding. So
the single most valuable turn in the product, "I am looking at this and I want
to know X", was answered without anything ever reading X. That helper's own
docstring conceded it: "without claiming the message itself was understood."

The reply was not deleted. It was demoted from gatekeeper to fallback. These
tests hold both halves of that: the question now reaches cognition, and the
acknowledgment still answers when cognition genuinely cannot run.

Hermetic - `_handle_project_question` and the residual seam are patched; no
Anthropic call is made.
"""
from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

from services import conversation_interpreter as ci
from services.case_workspace import CaseWorkspaceStore


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(mkdtemp())
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-cf")
        self.source = self.store.add_source(
            self.workspace, name="PSD-A-101.pdf", file_path=str(self.tmp / "a.pdf"),
            kind="drawing",
        )
        self.anchor = {
            "anchor_type": "source",
            "anchor_id": self.source["id"],
            "description": "PSD-A-101.pdf",
        }

    def _interpret(self, text, anchor=None, case=None, admission=None):
        return ci.interpret_message(
            text, self.workspace, case, self.store, self.tmp, "reviewer",
            None, anchor=anchor if anchor is not None else self.anchor,
            residual_admission=admission,
        )


class AClickNoLongerSwallowsTheQuestionTests(_Base):
    def test_an_anchored_question_reaches_cognition(self):
        """The whole point. Before this change the model never saw it."""
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(
                action_taken="project_qa_answered", reply_text="…",
            )
            result = self._interpret("What smoke control provisions apply here?")
        self.assertTrue(qa.called)
        self.assertEqual(result.action_taken, "project_qa_answered")

    def test_the_anchor_still_travels_as_context(self):
        """Demoting the gate must not cost the context the gate proved had
        arrived - it was always being passed, it just was never used."""
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(action_taken="project_qa_answered", reply_text="…")
            self._interpret("What does this drawing show?")
        ui_context = qa.call_args.kwargs.get("ui_context") or {}
        self.assertIn("selected_source_name", ui_context)

    def test_a_message_with_no_anchor_is_unaffected(self):
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(action_taken="project_qa_answered", reply_text="…")
            self._interpret("What are the objectives of this RFP?", anchor=None)
        self.assertTrue(qa.called)


class ItStillDegradesToTheHonestReplyTests(_Base):
    """Two PRE-EXISTING tests caught this being wrong on the first attempt -
    routing anchored turns into cognition meant that when cognition could not
    run, the reviewer got a reply about the QA path being unavailable instead
    of the acknowledgment. That is worse than what they had. The argument for
    keeping those tests is that they found it and inspection did not."""

    def test_an_unavailable_qa_path_falls_back_to_acknowledgment(self):
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(
                action_taken="project_qa_unavailable", reply_text="not available",
            )
            result = self._interpret("What does this show?")
        self.assertEqual(result.action_taken, "anchor_acknowledged")
        self.assertIn("PSD-A-101.pdf", result.reply_text)

    def test_a_policy_denial_falls_back_to_acknowledgment(self):
        """A denial is a governed outcome, not a failure - but it is still not
        an answer, so the acknowledgment is the honest reply."""
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(
                action_taken="project_qa_policy_denied:profile", reply_text="denied",
            )
            result = self._interpret("What does this show?")
        self.assertEqual(result.action_taken, "anchor_acknowledged")

    def test_a_real_answer_is_never_replaced_by_the_fallback(self):
        with patch.object(ci, "_handle_project_question") as qa:
            qa.return_value = ci.InterpretationResult(
                action_taken="project_qa_answered", reply_text="A real, grounded answer.",
            )
            result = self._interpret("What does this show?")
        self.assertEqual(result.action_taken, "project_qa_answered")

    def test_the_fallback_does_nothing_without_an_anchor(self):
        plain = ci.InterpretationResult(action_taken="project_qa_unavailable", reply_text="x")
        self.assertIs(ci._acknowledge_if_unanswerable(plain, None), plain)


class TheOrderingIsTheFixTests(unittest.TestCase):
    def test_the_acknowledgment_now_sits_after_the_cognition_seam(self):
        """Structural: determinism guards the answer instead of pre-empting
        it. If this ever inverts again, the symptom returns exactly as
        reported."""
        import inspect

        src = inspect.getsource(ci.interpret_message)
        seam = src.index("residual = residual_admission")
        ack = src.index('action_taken="anchor_acknowledged"')
        self.assertGreater(ack, seam)

    def test_no_early_return_reintroduces_the_gate(self):
        import inspect
        import re

        src = inspect.getsource(ci.interpret_message)
        head = src[: src.index("residual = residual_admission")]
        # An `if anchor is not None:` that RETURNS before cognition is the bug.
        self.assertIsNone(
            re.search(r"if anchor is not None:\s*\n\s*return", head),
            "the anchor gate has been reintroduced ahead of cognition",
        )


if __name__ == "__main__":
    unittest.main()
