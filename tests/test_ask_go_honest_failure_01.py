"""CLAUDE-ASK-GO-HONEST-FAILURE-01 - a reply that arrived is not an absent
service, and Ask GO said it was.

THE LIVE DEFECT. The Product Owner asked "What are the structures on this
property?" and the page answered "I could not answer just now - the assistant
service did not respond." The provider had responded: HTTP 200, in well under a
second, with a correct answer beginning "GO read two structures on this
property: 1. 1-storey brick dwelling...". It simply was not in the shape this
caller requires, so the gateway returned ran=False - and every ran=False mapped
to the same sentence.

That wording sends a person to retry a service that was never down and points
diagnosis at the provider when the fault is on this side.

WHAT IS DELIBERATELY NOT FIXED HERE. The answer text is in `outcome.raw_text`
and is still discarded. `LLMCallOutcome` states that those fields are
diagnostic evidence only and that `ran=False` still means unusable; Product
Owner decision, 2026-09-17, was to keep that invariant intact and correct the
sentence instead. A test below pins that the gateway was not relaxed.
"""
import unittest
from unittest.mock import patch

from services import document_conversation as dc
from services import llm_gateway


class _Outcome:
    def __init__(self, ran=False, parsed=None, parse_status=None,
                 raw_text=None, skipped_reason=None):
        self.ran = ran
        self.parsed = parsed
        self.parse_status = parse_status
        self.raw_text = raw_text
        self.skipped_reason = skipped_reason


class _App:
    config = {"ANTHROPIC_API_KEY": "test-key", "ANTHROPIC_MODEL": "m"}


class _Doc:
    filename = "1 Castille Ave -Survey.jpg"
    requirements = []
    tables = []


def _ask(outcome):
    with patch.object(dc, "build_context", lambda *a, **k: {"question": "q"}), \
         patch.object(dc, "render_prompt", lambda ctx: "prompt"), \
         patch.object(llm_gateway, "call_llm_json", lambda **kw: outcome):
        return dc.ask(_Doc(), object(), {}, "What are the structures?",
                      app=_App())


class TheMessageMatchesWhatHappened(unittest.TestCase):

    def test_a_reply_that_could_not_be_read_is_not_called_unresponsive(self):
        """The exact live case: HTTP 200, good prose, wrong shape."""
        reply = _ask(_Outcome(
            ran=False, parse_status=llm_gateway.PARSE_MALFORMED,
            raw_text="GO read two structures on this property: ...",
            skipped_reason="Model returned malformed output."))

        self.assertFalse(reply["ok"])
        self.assertEqual(reply["answer"], dc.MALFORMED_MESSAGE)
        self.assertNotIn("did not respond", reply["answer"],
                         "a service that answered was reported as silent")

    def test_a_cut_off_answer_says_so(self):
        reply = _ask(_Outcome(ran=False,
                              parse_status=llm_gateway.PARSE_TRUNCATED))
        self.assertEqual(reply["answer"], dc.TRUNCATED_MESSAGE)
        self.assertIn("cut off", reply["answer"])

    def test_a_genuinely_absent_service_still_says_did_not_respond(self):
        """The original sentence is correct for the case it was written for,
        and keeping it is the point of distinguishing at all."""
        reply = _ask(_Outcome(ran=False, parse_status=None,
                              skipped_reason="timeout"))
        self.assertEqual(reply["answer"], dc.UNAVAILABLE_MESSAGE)
        self.assertIn("did not respond", reply["answer"])

    def test_a_well_formed_reply_with_no_answer_is_not_unresponsive_either(self):
        reply = _ask(_Outcome(ran=True, parsed={"answer": "   "},
                              parse_status=llm_gateway.PARSE_OK))
        self.assertEqual(reply["answer"], dc.MALFORMED_MESSAGE)
        self.assertEqual(reply["reason"], "empty_answer")

    def test_a_good_answer_still_comes_through(self):
        reply = _ask(_Outcome(ran=True, parsed={"answer": "Two structures."},
                              parse_status=llm_gateway.PARSE_OK))
        self.assertTrue(reply["ok"])
        self.assertEqual(reply["proposed_answer"], "Two structures.")
        self.assertNotIn("Two structures.", reply["answer"])
        self.assertTrue(reply["qualification_preserved"])


class NoInternalsReachThePerson(unittest.TestCase):

    def test_the_messages_name_no_machinery(self):
        for message in (dc.MALFORMED_MESSAGE, dc.TRUNCATED_MESSAGE,
                        dc.UNAVAILABLE_MESSAGE):
            low = message.lower()
            for leak in ("json", "parse", "schema", "http", "200", "api",
                         "anthropic", "claude", "token", "gateway", "status"):
                self.assertNotIn(leak, low,
                                 "%r leaked into a customer-facing message"
                                 % leak)

    def test_each_message_tells_the_person_what_to_do(self):
        self.assertIn("again", dc.MALFORMED_MESSAGE.lower())
        self.assertIn("question", dc.TRUNCATED_MESSAGE.lower())
        self.assertIn("again", dc.UNAVAILABLE_MESSAGE.lower())

    def test_every_message_says_the_document_is_unaffected(self):
        """A failed question must never read as though it damaged something."""
        for message in (dc.MALFORMED_MESSAGE, dc.TRUNCATED_MESSAGE,
                        dc.UNAVAILABLE_MESSAGE):
            self.assertRegex(message.lower(), r"unaffected|has changed|not shown")


class TheGatewayContractWasNotRelaxed(unittest.TestCase):
    """The tempting fix was to use `raw_text` as the answer. It was declined,
    and this pins that decision so a later change has to argue with it."""

    def test_raw_text_is_never_used_as_an_answer(self):
        prose = "GO read two structures on this property: a dwelling and a garage."
        reply = _ask(_Outcome(ran=False,
                              parse_status=llm_gateway.PARSE_MALFORMED,
                              raw_text=prose))

        self.assertNotIn("dwelling", reply["answer"],
                         "diagnostic raw_text was promoted to an answer")

    def test_the_gateway_still_declares_those_fields_diagnostic_only(self):
        import inspect

        source = inspect.getsource(llm_gateway.LLMCallOutcome)
        self.assertIn("DIAGNOSTIC EVIDENCE ONLY", source)
        self.assertIn("ran=False", source)


if __name__ == "__main__":
    unittest.main()
