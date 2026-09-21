"""CLAUDE-ANSWER-PRESENTATION-01 - the answer first, the machinery on request.

THE DEFECT. A person asked "Is there any stair in this drawing set?" and the
reply led with evidence admission, then repeated the same source-reference
qualification once per item, then repeated "not established as a project fact"
again for each, then raw OCR fragments. Every sentence was true. The answer was
underneath all of it.

Each test below is one of the Product Owner's acceptance criteria.
"""
import unittest

from services import answer_presentation as ap

# The shape actually reported, with the repetition that provoked this.
REPLY = (
    "Yes - stair-related information was found in the drawing set.\n"
    "This is a source_reference and is not yet established as a project fact.\n"
    "Stair notes appear on sheet A-201.\n"
    "This is a source_reference and is not yet established as a project fact.\n"
    "A stair section appears on sheet A-301.\n"
    "This is a source_reference and is not yet established as a project fact.\n"
    "TREAD 11\" RIS 7\" |||| ~~ 3F8A9C2D1E4B7A60 ~~ ||||\n"
    "state={admitted:3,quarantined:0} source_id=8dd38281 hash=176cad1857bed249"
)


class TheAnswerComesFirst(unittest.TestCase):

    def test_a_simple_question_is_answered_before_any_governance(self):
        view = ap.project(REPLY, grounded_in=["A-201", "A-301"])

        self.assertTrue(view["answer"].startswith("Yes"),
                        "the answer does not lead: %r" % view["answer"][:60])
        self.assertNotIn("not yet established", view["answer"],
                         "a qualification is in front of the answer")
        self.assertNotIn("source_reference", view["answer"])

    def test_where_it_was_found_is_carried_separately(self):
        view = ap.project(REPLY, grounded_in=["A-201", "A-301"])
        self.assertEqual(view["found_in"], ["A-201", "A-301"])


class RepetitionIsSaidOnce(unittest.TestCase):

    def test_identical_source_reference_qualifications_render_once(self):
        view = ap.project(REPLY)

        self.assertEqual(view["status"].lower().count("source_reference"), 1,
                         "the same qualification is still repeated")
        self.assertEqual(view["collapsed_qualifications"], 2,
                         "expected two duplicates to collapse")

    def test_the_status_is_one_concise_statement(self):
        view = ap.project(REPLY)
        self.assertTrue(view["status"])
        self.assertLessEqual(len(view["status"].split(".")), 3,
                             "the status grew back into a paragraph")


class RawResidueLeavesThePrimaryAnswer(unittest.TestCase):

    def test_ocr_fragments_are_not_in_the_default_answer(self):
        view = ap.project(REPLY)

        for fragment in ("||||", "~~", "3F8A9C2D1E4B7A60"):
            self.assertNotIn(fragment, view["answer"],
                             "%r is still in the primary answer" % fragment)
            self.assertNotIn(fragment, view["status"])

    def test_ids_hashes_and_state_payloads_move_to_technical(self):
        view = ap.project(REPLY)
        technical = "\n".join(view["technical"])

        self.assertIn("source_id=8dd38281", technical)
        self.assertIn("hash=176cad1857bed249", technical)
        self.assertNotIn("source_id=", view["answer"])

    def test_ordinary_prose_is_never_mistaken_for_residue(self):
        self.assertFalse(ap.is_residue(
            "A stair section appears on sheet A-301."))
        self.assertFalse(ap.is_residue("Yes."))
        self.assertTrue(ap.is_residue("|||| ~~ 3F8A9C2D1E4B7A60 ~~ ||||"))


class NothingIsLost(unittest.TestCase):

    def test_technical_details_remain_fully_recoverable(self):
        view = ap.project(REPLY)
        self.assertTrue(ap.canonical_is_recoverable(view, REPLY))
        self.assertEqual(view["canonical_text"], REPLY)

    def test_every_moved_line_is_still_reachable(self):
        view = ap.project(REPLY)
        recoverable = view["canonical_text"]
        for line in REPLY.splitlines():
            self.assertIn(line, recoverable,
                          "a line was discarded rather than moved")

    def test_evidence_remains_expandable(self):
        view = ap.project(REPLY, evidence=["A-201 p3 'STAIR 1'",
                                           "A-301 p1 'STAIR SECTION'"])
        self.assertEqual(len(view["evidence"]), 2)


class ContradictionsNeverCollapse(unittest.TestCase):
    """Compression works by noticing two sentences say the same thing. Two that
    DISAGREE look repetitive and are the opposite of it."""

    CONFLICTING = (
        "Stair riser height is 7 inches on A-201.\n"
        "This is a source_reference and is not yet established as a project fact.\n"
        "However A-301 shows a riser height of 7.5 inches, which contradicts A-201.\n"
        "This is a source_reference and is not yet established as a project fact."
    )

    def test_a_disagreement_survives_compression(self):
        view = ap.project(self.CONFLICTING)

        self.assertEqual(len(view["contradictions"]), 1)
        self.assertIn("contradicts", view["contradictions"][0])
        self.assertIn("7.5", view["contradictions"][0])

    def test_a_contradiction_is_never_folded_into_the_status_line(self):
        view = ap.project(self.CONFLICTING)
        self.assertNotIn("contradicts", view["status"])

    def test_two_qualifiers_still_collapse_around_it(self):
        view = ap.project(self.CONFLICTING)
        self.assertEqual(view["collapsed_qualifications"], 1)

    def test_a_contradictory_sentence_is_exempt_even_when_repeated(self):
        repeated = ("A-201 contradicts A-301.\n"
                    "A-201 contradicts A-301.")
        view = ap.project(repeated)
        self.assertEqual(len(view["contradictions"]), 2,
                         "a repeated disagreement was collapsed")


class PresentationOnly(unittest.TestCase):

    def test_the_projection_stores_nothing(self):
        """No provider, no store, no writes - it is a pure function."""
        import inspect

        source = inspect.getsource(ap)
        for forbidden in ("store.", "open(", "requests", "llm_gateway",
                          "register_evidence_item", "record_supersession"):
            self.assertNotIn(forbidden, source,
                             "%r suggests this module does more than present"
                             % forbidden)

    def test_it_does_not_mutate_its_input(self):
        before = REPLY
        ap.project(REPLY)
        self.assertEqual(REPLY, before)

    def test_an_empty_or_missing_reply_is_handled(self):
        for value in (None, "", "   "):
            view = ap.project(value)
            self.assertEqual(view["answer"], "")
            self.assertEqual(view["canonical_text"], str(value or ""))

    def test_an_answer_that_is_only_a_qualification_still_leads_with_something(self):
        view = ap.project(
            "This is a source_reference and is not yet established as a "
            "project fact.")
        self.assertTrue(view["answer"],
                        "an empty heading was left above a status line")


class TheDocumentShopConsumesIt(unittest.TestCase):
    """The projection has a real caller - the failure this repository keeps
    producing is a capability wired to nothing."""

    def test_conversation_for_attaches_a_view_to_go_turns_only(self):
        from services import document_conversation as dc

        class _WS:
            project_conversation = [
                {"role": dc.ROLE_HUMAN, "text": "Is there any stair?",
                 "created_at": "t1"},
                {"role": "assistant", "text": REPLY, "created_at": "t2"},
            ]

        turns = dc.conversation_for(_WS())
        self.assertIsNone(turns[0]["view"], "the person's own words were re-ordered")
        self.assertIsNotNone(turns[1]["view"])
        self.assertTrue(turns[1]["view"]["answer"].startswith("Yes"))

    def test_the_stored_text_is_unchanged_by_rendering(self):
        from services import document_conversation as dc

        class _WS:
            project_conversation = [
                {"role": "assistant", "text": REPLY, "created_at": "t"},
            ]

        turns = dc.conversation_for(_WS())
        self.assertEqual(turns[0]["text"], REPLY,
                         "rendering altered the stored message")
        self.assertEqual(_WS.project_conversation[0]["text"], REPLY)

    def test_rendering_runs_no_analysis(self):
        """Reload must not re-run anything: the projection is pure text work."""
        import inspect

        from services import document_conversation as dc

        source = inspect.getsource(dc.conversation_for)
        for forbidden in ("ask(", "call_llm", "examine", "build_result"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
