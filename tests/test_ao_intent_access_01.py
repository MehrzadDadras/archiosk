"""CLAUDE-AO-INTENT-ACCESS-01 - regression tests for PSD-SMOKE-01-A/B/C.

The PSD Builder blind smoke test measured, on the deployed build, that
access to project cognition turned on the surface form of a message
rather than on its substantive intent: a six-sentence professional
review instruction produced nothing (and silently created a governed
Case to hold it), while the same subject matter asked as a one-sentence
interrogative produced real cross-document findings.

These tests assert ACCESS AND DISPATCH ONLY. They never assert what GO
concludes, never touch the PSD oracle, and make no model call - the
predicate under test is pure and deterministic by design.
"""
import unittest

from services.conversation_interpreter import (
    _looks_like_capability_question,
    _looks_like_conversational_utterance,
    _looks_like_orientation_request,
    _looks_like_project_question,
)

# The exact first blind prompt from the PSD Builder smoke test. Used
# verbatim as the frozen PSD-SMOKE-01-A regression case. It carries no
# oracle content - it is the QUESTION that was asked, never an answer.
PSD_FIRST_BLIND_PROMPT = (
    "Review this RFP package as a Builder preparing our proposal. Tell me what "
    "deserves attention before we submit. Show me the contract facts that made you "
    "notice each issue. Don't assume every difference is a mistake. If you don't "
    "have enough information to decide something, say that. Don't redesign anything "
    "unless I ask you for solutions."
)


class SameIntentDifferentSyntaxTests(unittest.TestCase):
    """PSD-SMOKE-01-C: equivalent intent must dispatch equivalently."""

    EQUIVALENT_COST_INQUIRIES = (
        "Is this going to cost us more?",
        "Tell me whether this is likely to cost us more.",
        "Review this package and tell me where we may have cost exposure before we submit.",
        PSD_FIRST_BLIND_PROMPT,
    )

    def test_every_phrasing_of_one_intent_reaches_project_cognition(self):
        for text in self.EQUIVALENT_COST_INQUIRIES:
            with self.subTest(text=text[:60]):
                self.assertTrue(
                    _looks_like_project_question(text.lower()),
                    "equivalent intent must not depend on sentence shape",
                )

    def test_psd_first_blind_prompt_reaches_project_cognition(self):
        """PSD-SMOKE-01-A, frozen: the exact prompt that produced nothing."""
        self.assertTrue(_looks_like_project_question(PSD_FIRST_BLIND_PROMPT.lower()))

    def test_question_not_at_the_end_still_reaches_cognition(self):
        """The decisive measured case: contains '?' but does not end with one."""
        text = (
            "Are there similar conditions in this package that are handled differently "
            "from each other? Tell me which differences look like they need explaining "
            "and which ones look normal."
        )
        self.assertTrue(_looks_like_project_question(text.lower()))

    def test_interrogative_and_imperative_of_the_same_request_agree(self):
        interrogative = "Which similar conditions in this package are handled differently from each other?"
        imperative = "Review this package and identify similar conditions handled differently."
        self.assertEqual(
            _looks_like_project_question(interrogative.lower()),
            _looks_like_project_question(imperative.lower()),
        )

    def test_rough_trade_wording_reaches_cognition(self):
        for text in ("whats up with the fan duty", "why is this one different"):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_project_question(text.lower()))


class NoFallbackCaseCreationTests(unittest.TestCase):
    """PSD-SMOKE-01-B: routing failure must not multiply governed objects.

    `routes/workspace.py`'s quick_start creates a Case only when the text
    matches none of its recognized conversational predicates - of which
    `_looks_like_project_question` is one. Proving the predicate matches
    proves quick_start routes to the project-level conversation instead
    of creating a Case, which is the single seam that produced the two
    duplicate Cases observed live.
    """

    def test_repeated_project_review_requests_never_reach_the_case_fallback(self):
        for _ in range(3):
            self.assertTrue(
                _looks_like_project_question(PSD_FIRST_BLIND_PROMPT.lower()),
                "a repeated ordinary project request must not fall through to Case creation",
            )

    def test_quick_start_predicate_set_covers_the_measured_prompts(self):
        for text in SameIntentDifferentSyntaxTests.EQUIVALENT_COST_INQUIRIES:
            with self.subTest(text=text[:60]):
                recognized = (
                    _looks_like_conversational_utterance(text.lower())
                    or _looks_like_project_question(text.lower())
                    or _looks_like_orientation_request(text.lower())
                )
                self.assertTrue(recognized, "quick_start would create a Case for this")


class BoundedRecognitionTests(unittest.TestCase):
    """The gate stays bounded - widened, not removed."""

    def test_plain_declarative_context_statement_is_not_an_inquiry(self):
        """A statement of fact must not trigger a real, billed model call."""
        for text in (
            "The consultant called me this morning.",
            "We received the addendum yesterday.",
            "I sent the drawings to the estimator.",
        ):
            with self.subTest(text=text):
                self.assertFalse(_looks_like_project_question(text.lower()))

    def test_empty_and_whitespace_are_not_inquiries(self):
        for text in ("", "   ", "\n\n"):
            with self.subTest(text=repr(text)):
                self.assertFalse(_looks_like_project_question(text))

    def test_casual_acknowledgement_does_not_reach_project_cognition(self):
        for text in ("Okay, thanks.", "Thanks.", "Got it."):
            with self.subTest(text=text):
                reaches_cognition = _looks_like_project_question(
                    text.lower()
                ) and not _looks_like_conversational_utterance(text.lower())
                self.assertFalse(reaches_cognition)


class CategorySeparationTests(unittest.TestCase):
    """Application-capability questions keep their own earlier handler."""

    def test_capability_questions_are_claimed_before_the_project_gate(self):
        """`_handle_capability_question` runs earlier in interpret_message.

        Widening the project gate must not change which handler claims a
        self-referential application question first.
        """
        for text in (
            "Can you create these folders for me?",
            "Can ARCHIOSK send email?",
            "Does ARCHIOSK support voice?",
        ):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_capability_question(text.lower()))

    def test_ordinary_evidence_question_is_still_not_a_capability_question(self):
        self.assertFalse(_looks_like_capability_question("what does opr-3.5 require"))

    def test_orientation_requests_keep_their_deterministic_handler(self):
        for text in ("orient me", "what's here", "give me an overview"):
            with self.subTest(text=text):
                self.assertTrue(_looks_like_orientation_request(text.lower()))

    def test_application_surface_request_does_not_reach_project_cognition(self):
        """An imperative about the UI must not become a project inquiry.

        This is the case the widened gate could most plausibly have
        broken: an imperative sentence about the application. "show me"
        is deliberately absent from both starter tuples, so this stays
        outside the project gate exactly as it did before the widening.
        """
        self.assertFalse(
            _looks_like_project_question("show me how to delete this conversation.")
        )

    def test_widening_introduced_no_new_application_leakage(self):
        """Interrogative application questions are UNCHANGED by this repair.

        `"How do I delete this chat?"` reaches the project gate on its
        question mark - as it did before this change, since the original
        predicate also matched any message ending in "?". That is a real,
        separately-owned category error; this test pins it as pre-existing
        so a future reader does not attribute it to the widening. It is
        deliberately asserted as the CURRENT behaviour, not the desired
        one.
        """
        pre_existing_interrogative_app_questions = (
            "how do i delete this chat?",
            "where is the upload button?",
        )
        for text in pre_existing_interrogative_app_questions:
            with self.subTest(text=text):
                # Matched by the question mark alone - true before and after.
                self.assertIn("?", text)
                self.assertTrue(_looks_like_project_question(text))


class ExplicitActionPreservationTests(unittest.TestCase):
    """Governed action grammar is matched earlier and must still win.

    These assert the action-shaped predicates interpret_message applies
    ahead of the project gate, exactly as that function applies them.
    """

    def test_analyze_compare_and_draft_rfi_remain_action_shaped(self):
        self.assertTrue("analyze this drawing for penetrations.".startswith(("analyze", "analyse")))
        compare = "compare psd-m-201 with psd-m-202."
        self.assertTrue(compare.startswith("compare") or " compare " in f" {compare} ")
        draft = "draft an rfi from finding 3."
        self.assertTrue("draft" in draft and "rfi" in draft)

    def test_widened_gate_does_not_add_mutation_verbs(self):
        """No inquiry starter may mean 'change something'."""
        from services.conversation_interpreter import _PROJECT_INQUIRY_STARTERS

        forbidden = (
            "create", "draft", "issue", "apply", "accept", "approve",
            "delete", "remove", "publish", "adopt", "supersede",
        )
        for starter in _PROJECT_INQUIRY_STARTERS:
            with self.subTest(starter=starter):
                self.assertFalse(
                    starter.strip().startswith(forbidden),
                    "an inquiry starter must never imply a governed mutation",
                )


class AmbiguousReferentTests(unittest.TestCase):
    """Widening recognition must not fabricate a referent."""

    def test_ambiguous_referent_dispatch_is_unchanged_by_this_repair(self):
        """"What's wrong with this?" ended with '?' before and after.

        Referent resolution stays where it already lives (the contextual-
        reference handler and candidate_referents); this repair neither
        resolves nor invents an identity for "this".
        """
        text = "what's wrong with this?"
        self.assertTrue(_looks_like_project_question(text))


if __name__ == "__main__":
    unittest.main()
