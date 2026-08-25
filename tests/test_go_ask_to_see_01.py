"""CLAUDE-GO-ASK-TO-SEE-01 - ask for the drawing instead of talking around it.

Product Owner: "Today I was talking to my 365 Copilot about a problem I was
going to make an RFI for and he said 'load your drawing so I can see what you
are talking about'. Make our application to have the same capacity."

The gap was never vision. The "+" already sends a photo and the vision path
already reads it. The gap was that GO never ASKED. Its contract told it to say
so plainly when evidence was insufficient - which it did, as prose, at length,
without ever naming the one action that would have settled the question in
three seconds. The reviewer was left holding a drawing GO could have read.

Copilot's line works because it is specific and actionable: it names what it
needs and what to do about it. So this is not "be more helpful" - it is a
concrete behaviour with a concrete control attached.

A prompt rule cannot be proved by unit test; model behaviour is not
deterministic. What CAN be proved, and is what actually goes wrong with
instructions like this, is that the rule exists in every contract that
generates an answer, that it points at a control that genuinely exists, and
that it is bounded so asking never quietly replaces answering.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MACROS = (ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")

from services.conversational_turn import CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT
from services.project_qa import BEHAVIORAL_CONTRACT

CONTRACTS = {
    "project_qa": BEHAVIORAL_CONTRACT,
    "conversational_turn": CONVERSATIONAL_TURN_BEHAVIORAL_CONTRACT,
}


class EveryAnsweringPathCanAskTests(unittest.TestCase):
    def test_both_contracts_carry_the_rule(self):
        """Two different paths generate answers. A rule in only one of them is
        a behaviour that appears and disappears depending on how the message
        was routed - which is worse than not having it."""
        for name, contract in CONTRACTS.items():
            with self.subTest(contract=name):
                self.assertIn("would require SEEING something", contract)

    def test_it_names_what_it_needs_rather_than_asking_vaguely(self):
        for name, contract in CONTRACTS.items():
            with self.subTest(contract=name):
                self.assertIn("what you would need to see", contract)

    def test_it_names_the_control_that_actually_does_it(self):
        """"Load your drawing" only works if the reviewer knows how. This is
        the same failure that made "make a new Q" undiscoverable."""
        for name, contract in CONTRACTS.items():
            with self.subTest(contract=name):
                self.assertIn("+ beside the message box", contract)


class TheControlItPromisesMustExistTests(unittest.TestCase):
    """The rule tells the reviewer to use a specific control. If that control
    is ever renamed or removed, the instruction becomes GO confidently
    describing something that is not there - which is precisely the class of
    failure the contract's own "never claim to perform an application action
    you cannot actually perform" rule exists to prevent."""

    def test_the_attachment_control_is_really_there(self):
        self.assertIn('data-ui-ref="chat.composer.attach"', MACROS)
        self.assertIn('id="dock-composer-image"', MACROS)

    def test_it_really_accepts_a_drawing_or_photo(self):
        block = MACROS[MACROS.index('id="dock-composer-image"'):]
        block = block[: block.index(">")]
        self.assertIn('accept="image/*"', block)

    def test_the_vision_route_that_reads_it_exists(self):
        route = (ROOT / "routes" / "workspace.py").read_text(encoding="utf-8")
        self.assertIn("_composer_photo_turn", route)
        self.assertIn("image_base64=", route)


class AskingMustNotReplaceAnsweringTests(unittest.TestCase):
    """A request to see something the answer did not depend on is a delay
    wearing the costume of diligence. The Product Owner has already rejected
    one long non-answer; a reflexive "show me your drawing" would be the same
    failure in a shorter sentence."""

    def test_the_rule_is_bounded_by_sufficiency(self):
        for name, contract in CONTRACTS.items():
            with self.subTest(contract=name):
                self.assertIn("IS sufficient, answer", contract)

    def test_it_asks_for_the_smallest_thing_that_would_resolve_it(self):
        for name, contract in CONTRACTS.items():
            with self.subTest(contract=name):
                self.assertIn("smallest thing", contract)

    def test_it_forbids_the_long_hedge_it_replaces(self):
        self.assertIn("do not write a long hedged answer around it", BEHAVIORAL_CONTRACT)

    def test_the_existing_insufficiency_rule_still_stands(self):
        """Asking to see something is an addition to honest insufficiency, not
        a replacement for it - there are questions no photograph settles."""
        self.assertIn("genuinely insufficient", BEHAVIORAL_CONTRACT)


class NoNewCapabilityWasClaimedTests(unittest.TestCase):
    def test_no_new_route_or_model_call_was_added(self):
        """A photo sent after GO asks travels the path that already existed.
        This change is a prompt rule and nothing else."""
        # The pre-existing counts, not "one": project_qa.py has always had two
        # call sites - answer_application_question and answer_project_question -
        # and asserting one was wrong about the baseline rather than about this
        # change. What matters is that a prompt-only change added neither.
        # project_qa.py went 2 -> 3 when CLAUDE-GO-GATEWAY-COGNITION-02 added
        # answer_orientation_question, a real and deliberate third seam - the
        # Gateway's own, replacing its wrong borrowing of the Developer Mode
        # one. Bumped with the reason rather than silently, because the point
        # of this count is that every seam here is named and intended:
        #   answer_application_question   - Developer Mode
        #   answer_orientation_question   - the project-less Gateway
        #   answer_project_question       - grounded project Q&A
        # What THIS stage (ask-to-see) added was a prompt rule and nothing else.
        expected = {"project_qa.py": 3, "conversational_turn.py": 1}
        for filename, count in expected.items():
            source = (ROOT / "services" / filename).read_text(encoding="utf-8")
            code = re.sub(r"(?m)#.*$", "", source)
            with self.subTest(module=filename):
                self.assertEqual(code.count("call_llm_json("), count)


if __name__ == "__main__":
    unittest.main()
