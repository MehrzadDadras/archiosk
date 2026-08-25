"""
CLAUDE-ROUTING-PRECISION-01 - keywords are evidence of intent, not intent.

Product Owner, from live use:

    "I am trying to draft an RFI for a glazed screen that does not have good
     support and am wondering if a C channel is appropriate or an HHS member."

GO answered: "Focus a Finding first ... then ask me to draft an RFI from it."

The handler was right and the routing was wrong. `_handle_draft_rfi_intent`
drafts an RFI BY INHERITANCE from a focused Finding, pulling its Source/page/
region/Case references, so requiring a Finding is correct for that job. But the
rule that claimed the message was:

    if "draft" in lowered and "rfi" in lowered:

- two words appearing anywhere. The reviewer had supplied their own matter and
asked a professional question; nothing in the sentence asked GO to create
anything.

WHAT THESE TESTS PROTECT

Each of the three narrowed rules gets a PAIR:

  * a true positive  - the explicit command still routes exactly as before;
  * a false positive - ordinary discussion falls through to the semantic spine.

The pairing is the point. A precision fix that only tested the new negative
could silently break the real path, and this repository has been bitten by
one-sided assertions more than once today.

WHAT IS NOT TESTED HERE, DELIBERATELY

No authority or approval semantics. Nothing about `_require_approval`,
ACTION_EXTERNAL_AI_REQUEST, or the Finding requirement itself changed - this
stage altered only WHAT REACHES those handlers. Their own tests still own them.

These assert against the classifier directly rather than through a live turn:
the fall-through path ends in run_conversational_turn, which is a model call, and
a routing test must not depend on one.
"""
from __future__ import annotations

import unittest

from services.conversation_interpreter import _is_instruction_to, _strip_polite_opener

_RFI_VERBS = ("draft", "write", "prepare", "raise", "issue")
_EVIDENCE_VERBS = ("show", "display", "list", "give", "open", "pull")
_COMPARE_VERBS = ("compare",)


class TheReportedDefectTests(unittest.TestCase):
    """The exact sentence, kept verbatim so the regression is unmistakable."""

    REPORTED = (
        "I am trying to draft an RFI for a glazed screen that does not have good "
        "support and am wondering if a C channel is appropriate or an HHS member."
    )

    def test_the_reported_sentence_is_not_an_instruction(self):
        self.assertFalse(_is_instruction_to(self.REPORTED.lower(), _RFI_VERBS))

    def test_it_still_contains_both_trigger_words(self):
        # Proving the fix is about SHAPE, not about the words going away - the
        # old rule would still claim this sentence today.
        lowered = self.REPORTED.lower()
        self.assertIn("draft", lowered)
        self.assertIn("rfi", lowered)

    def test_the_operative_clause_is_a_question(self):
        # "am wondering if X is appropriate or Y" - the ask is technical
        # judgement, and "draft an RFI" is the context it arrives in.
        self.assertIn("am wondering if", self.REPORTED.lower())


class DraftRfiPrecisionTests(unittest.TestCase):
    def test_true_positive_the_explicit_command_still_routes(self):
        for text in (
            "Draft an RFI from Finding 3.",
            "draft an rfi about this",
            "draft an rfi",
            "Write an RFI from this finding",
            "Prepare an RFI for Finding 2",
        ):
            with self.subTest(text=text):
                self.assertTrue(_is_instruction_to(text.lower(), _RFI_VERBS), text)

    def test_true_positive_a_polite_command_is_still_a_command(self):
        # "Please draft an RFI" is as imperative as "Draft an RFI"; refusing it
        # would be a new defect introduced by the fix.
        for text in (
            "Please draft an RFI from Finding 3.",
            "Can you draft an RFI from Finding 2?",
            "Could you please prepare an RFI from this finding",
        ):
            with self.subTest(text=text):
                self.assertTrue(_is_instruction_to(text.lower(), _RFI_VERBS), text)

    def test_false_positive_discussion_falls_through(self):
        for text in (
            "I am trying to draft an RFI for a glazed screen and am wondering if a C channel is appropriate.",
            "We should probably draft an RFI at some point.",
            "The consultant will draft an RFI once the survey is back.",
            "Is an RFI the right route here, or should I just draft a site instruction?",
            "My draft RFI never got a response.",
        ):
            with self.subTest(text=text):
                self.assertFalse(_is_instruction_to(text.lower(), _RFI_VERBS), text)


class ShowEvidencePrecisionTests(unittest.TestCase):
    def test_true_positive_the_explicit_request_still_routes(self):
        for text in (
            "Show me the evidence supporting Finding 2",
            "show the evidence for this finding",
            "List the evidence behind Finding 4",
        ):
            with self.subTest(text=text):
                self.assertTrue(_is_instruction_to(text.lower(), _EVIDENCE_VERBS), text)

    def test_true_positive_the_interrogative_form_still_routes(self):
        for text in ("What evidence supports this finding?", "Which evidence backs Finding 3?"):
            with self.subTest(text=text):
                stripped = _strip_polite_opener(text.lower())
                self.assertTrue(
                    stripped.startswith(("what evidence", "which evidence", "where is the evidence")),
                    text,
                )

    def test_false_positive_a_statement_of_doubt_falls_through(self):
        # Answering "I don't have evidence for this finding yet" with an
        # evidence panel leaves the actual remark unanswered - the same failure
        # mode as the reported RFI defect, just quieter.
        for text in (
            "I don't have evidence for this finding yet, so I'd rather not raise it.",
            "The finding was based on field evidence rather than the drawings.",
            "There is no evidence in the file supporting that finding.",
        ):
            with self.subTest(text=text):
                lowered = text.lower()
                self.assertIn("evidence", lowered)
                self.assertIn("finding", lowered)
                routed = (
                    _is_instruction_to(lowered, _EVIDENCE_VERBS)
                    or _strip_polite_opener(lowered).startswith(
                        ("what evidence", "which evidence", "where is the evidence")
                    )
                )
                self.assertFalse(routed, text)


class ComparePrecisionTests(unittest.TestCase):
    def test_true_positive_the_explicit_command_still_routes(self):
        for text in ("Compare A with B.", "compare the two schedules", "Please compare these drawings"):
            with self.subTest(text=text):
                self.assertTrue(_is_instruction_to(text.lower(), _COMPARE_VERBS), text)

    def test_false_positive_mentioning_comparison_falls_through(self):
        # The loose ` compare ` clause claimed all of these. Each is a remark
        # that deserves a real answer, not a comparison artifact.
        for text in (
            "It's hard to compare these without the finish schedule.",
            "The consultant will compare the two schedules next week.",
            "I can't compare them because one is missing.",
        ):
            with self.subTest(text=text):
                self.assertIn("compare", text.lower())
                self.assertFalse(_is_instruction_to(text.lower(), _COMPARE_VERBS), text)


class TheShapeRuleItselfTests(unittest.TestCase):
    def test_a_polite_opener_is_stripped_not_matched(self):
        self.assertEqual(_strip_polite_opener("please draft an rfi"), "draft an rfi")
        self.assertEqual(_strip_polite_opener("could you compare these"), "compare these")

    def test_stacked_openers_are_stripped(self):
        self.assertEqual(_strip_polite_opener("please can you draft an rfi"), "draft an rfi")

    def test_a_declarative_opener_is_not_stripped(self):
        # "I am trying to" must NOT be treated as politeness - that is exactly
        # what distinguishes the reported sentence from a command.
        self.assertTrue(_strip_polite_opener("i am trying to draft an rfi").startswith("i am"))

    def test_the_verb_must_lead(self):
        self.assertTrue(_is_instruction_to("compare these", _COMPARE_VERBS))
        self.assertFalse(_is_instruction_to("i would rather compare these", _COMPARE_VERBS))


class HandlersAndGatesAreUntouchedTests(unittest.TestCase):
    """This stage changed WHAT REACHES the handlers, never what they permit."""

    def test_the_finding_requirement_survives(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "services" / "conversation_interpreter.py").read_text(encoding="utf-8")
        # The handler still refuses to draft by inheritance with no Finding.
        self.assertIn("Focus a Finding first", source)
        self.assertIn("rfi_intent_failed", source)

    def test_the_semantic_spine_is_still_the_fall_through(self):
        from pathlib import Path

        source = (Path(__file__).resolve().parent.parent
                  / "services" / "conversation_interpreter.py").read_text(encoding="utf-8")
        self.assertIn("run_conversational_turn", source)


if __name__ == "__main__":
    unittest.main()
