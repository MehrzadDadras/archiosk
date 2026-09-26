"""GOPILOT CORE step 2 - transition-required intent state.

The intent label now distinguishes three things the old `authorized` boolean
could not:

    NOT_AUTHORIZED        the credential cannot hold that envelope
    IN_ENVELOPE           authorized, and may operate where it was asked
    TRANSITION_REQUIRED   the credential may use the target envelope, but the
                          current envelope must not execute it directly

plus UNRESOLVED for an unknown intent or one with no object to act on.
`transition_required` implies `authorized` and a resolved object - it marks a
permitted move and is never a way around a refusal. Labels only: nothing here
navigates, dispatches or executes, and no route reads these fields yet.
"""
from __future__ import annotations

import unittest

from services.conversation_interpreter import (
    INTENT_STATE_IN_ENVELOPE,
    INTENT_STATE_NOT_AUTHORIZED,
    INTENT_STATE_TRANSITION_REQUIRED,
    INTENT_STATE_UNRESOLVED,
    TRANSITION_CROSS_PROJECT,
    TRANSITION_LEAVE_OVERLAY,
    TRANSITION_NARROW,
    TRANSITION_NAVIGATE,
    TRANSITION_WIDEN,
)
from services.turn_frame import envelope_set_for
from tests.test_gopilot_turn_frame_01 import CUSTOMER, STAFF, classify, frame

DEVELOPER = sorted(envelope_set_for(authenticated=True, customer=False, developer=True))
EVERY_SESSION_ENVELOPE = sorted(set(DEVELOPER) | set(CUSTOMER))

HARBOUR = {"kind": "navigate", "project_id": "p-harbour"}   # an accessible, named project


def state(label):
    return (label["state"], label["authorized"], label["transition_required"])


class RequiredCases(unittest.TestCase):
    def test_1_developer_inspect_plus_project_intent_requires_a_transition(self):
        label = classify("What is open on Harbour Tower?",
                         frame("DEVELOPER_INSPECT", envelope_set=DEVELOPER), target=HARBOUR)
        self.assertEqual(state(label), (INTENT_STATE_TRANSITION_REQUIRED, True, True))
        self.assertEqual(label["target_envelope"], "PROJECT")
        self.assertEqual(label["transition"], TRANSITION_LEAVE_OVERLAY)

    def test_2_project_plus_application_navigation_is_a_navigate_transition(self):
        label = classify("Take me to Help Centre", frame("PROJECT", project_id="p1"))
        self.assertEqual(state(label), (INTENT_STATE_TRANSITION_REQUIRED, True, True))
        self.assertEqual((label["target_envelope"], label["transition"]), ("APPLICATION", TRANSITION_NAVIGATE))

    def test_3_document_plus_a_project_wide_question_widens_within_the_same_project(self):
        label = classify("What is the status of this project?",
                         frame("DOCUMENT_SOURCE", project_id="p1", selected_source_id="s1"))
        self.assertEqual(state(label), (INTENT_STATE_TRANSITION_REQUIRED, True, True))
        self.assertEqual((label["target_envelope"], label["transition"]), ("PROJECT", TRANSITION_WIDEN))
        self.assertIsNone(label["target_project_id"])   # same project, no second project named

    def test_4_project_plus_a_source_intent_on_the_current_source_narrows(self):
        label = classify("What does this say?",
                         frame("PROJECT", project_id="p1", selected_source_id="s1"))
        self.assertEqual(state(label), (INTENT_STATE_TRANSITION_REQUIRED, True, True))
        self.assertEqual((label["target_envelope"], label["transition"]), ("DOCUMENT_SOURCE", TRANSITION_NARROW))
        # With no Source in scope there is nothing to narrow INTO: unresolved, not a transition.
        bare = classify("What does this say?", frame("PROJECT", project_id="p1"))
        self.assertEqual(state(bare), (INTENT_STATE_UNRESOLVED, True, False))

    def test_5_customer_plus_investigation_is_not_authorized_and_not_a_transition(self):
        label = classify("Issue this RFI", frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER,
                                                 project_id="d1"))
        self.assertEqual(state(label), (INTENT_STATE_NOT_AUTHORIZED, False, False))
        self.assertIsNone(label["transition"])

    def test_6_a_stakeholder_token_never_transitions_into_session_or_project_authority(self):
        # Even a forged envelope_set naming every session envelope grants a pass nothing more.
        for envelope_set in (["STAKEHOLDER_TOKEN"], ["STAKEHOLDER_TOKEN"] + EVERY_SESSION_ENVELOPE):
            token = frame("STAKEHOLDER_TOKEN", envelope_set=envelope_set,
                          project_id="p1", selected_source_id="RS501")
            for text, target in (("Take me to Help Centre", None), ("Issue this RFI", None),
                                 ("What is open on Harbour Tower?", HARBOUR)):
                with self.subTest(envelope_set=len(envelope_set), text=text):
                    label = classify(text, token, target=target)
                    self.assertEqual(state(label), (INTENT_STATE_NOT_AUTHORIZED, False, False))
            with self.subTest(envelope_set=len(envelope_set), text="its own sheet"):
                own = classify("What does this say?", token)
                self.assertEqual(state(own), (INTENT_STATE_IN_ENVELOPE, True, False))

    def test_7_an_inaccessible_project_is_never_a_transition(self):
        """The Gateway's access-scoped rule never names it, so there is no target:
        nothing to move into, and no page makes one."""
        words = "What is still open on Zeta Tower?"
        for page, expected in (
                (frame("APPLICATION"), INTENT_STATE_UNRESOLVED),
                (frame("DEVELOPER_INSPECT", envelope_set=DEVELOPER), INTENT_STATE_UNRESOLVED),
                (frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1"),
                 INTENT_STATE_NOT_AUTHORIZED)):
            with self.subTest(page=page["current_envelope"]):
                label = classify(words, page, target=None)
                self.assertEqual(label["state"], expected)
                self.assertFalse(label["transition_required"])
                self.assertIsNone(label["target_project_id"])
        # Inside an open project the words are just words about THAT project -
        # never a cross-project move to the one named.
        inside = classify(words, frame("PROJECT", project_id="p1"), target=None)
        self.assertFalse(inside["transition_required"])
        self.assertIsNone(inside["target_project_id"])
        self.assertNotEqual(inside["transition"], TRANSITION_CROSS_PROJECT)


class Proof(unittest.TestCase):
    def test_developer_to_project_is_transition_required_not_immediately_actionable(self):
        label = classify("What is open on Harbour Tower?",
                         frame("DEVELOPER_INSPECT", envelope_set=DEVELOPER), target=HARBOUR)
        self.assertNotEqual(label["state"], INTENT_STATE_IN_ENVELOPE)
        self.assertTrue(label["transition_required"])

    def test_customer_to_a_staff_envelope_stays_unauthorized(self):
        customer = frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1")
        for text, target in (("Issue this RFI", None), ("What is open on Harbour Tower?", HARBOUR)):
            with self.subTest(text=text):
                self.assertEqual(state(classify(text, customer, target=target)),
                                 (INTENT_STATE_NOT_AUTHORIZED, False, False))

    def test_same_envelope_intent_is_not_transition_required(self):
        for page, text in ((frame("INVESTIGATION_STUDY", project_id="p1", case_id="c1"), "Issue this RFI"),
                           (frame("DOCUMENT_SOURCE", project_id="p1", selected_source_id="s1"), "What does this say?"),
                           (frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1"), "What does this say?"),
                           (frame("APPLICATION"), "Take me to Help Centre")):
            with self.subTest(page=page["current_envelope"], text=text):
                self.assertEqual(state(classify(text, page)), (INTENT_STATE_IN_ENVELOPE, True, False))

    def test_a_permitted_cross_envelope_intent_is_distinguishable_from_a_forbidden_one(self):
        permitted = classify("What is open on Harbour Tower?", frame("PROJECT", project_id="p1"), target=HARBOUR)
        forbidden = classify("What is open on Harbour Tower?",
                             frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1"), target=HARBOUR)
        self.assertEqual(state(permitted), (INTENT_STATE_TRANSITION_REQUIRED, True, True))
        self.assertEqual(permitted["transition"], TRANSITION_CROSS_PROJECT)
        self.assertEqual(state(forbidden), (INTENT_STATE_NOT_AUTHORIZED, False, False))

    def test_project_and_source_transitions_never_acquire_authority_from_page_context_alone(self):
        """A page that says PROJECT, with a project and a Source in view, cannot
        authorize a credential that does not hold those envelopes."""
        page_says_project = frame("PROJECT", envelope_set=CUSTOMER, project_id="p1", selected_source_id="s1")
        for text in ("What is the status of this project?", "Issue this RFI"):
            with self.subTest(text=text):
                self.assertEqual(state(classify(text, page_says_project)),
                                 (INTENT_STATE_NOT_AUTHORIZED, False, False))

    def test_mixed_turn_reports_each_part(self):
        label = classify("Take me to Help Centre and issue this RFI",
                         frame("INVESTIGATION_STUDY", project_id="p1", case_id="c1"))
        self.assertEqual(label["state"], INTENT_STATE_TRANSITION_REQUIRED)
        self.assertIsNone(label["target_envelope"])
        self.assertEqual([(s["envelope"], s["transition_required"], s["transition"]) for s in label["part_states"]],
                         [("APPLICATION", True, TRANSITION_NAVIGATE), ("INVESTIGATION_STUDY", False, None)])

    def test_transition_required_always_implies_authorized(self):
        pages = [frame("APPLICATION"), frame("PROJECT", project_id="p1"),
                 frame("DOCUMENT_SOURCE", project_id="p1", selected_source_id="s1"),
                 frame("INVESTIGATION_STUDY", project_id="p1", case_id="c1"),
                 frame("DEVELOPER_INSPECT", envelope_set=DEVELOPER),
                 frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1"),
                 frame("STAKEHOLDER_TOKEN", envelope_set=["STAKEHOLDER_TOKEN"], selected_source_id="s1")]
        texts = ["Take me to Help Centre", "Issue this RFI", "What does this say?",
                 "What is the status of this project?", "What is open on Harbour Tower?", "maybe later",
                 "Take me to Help Centre and issue this RFI"]
        for page in pages:
            for text in texts:
                for target in (None, HARBOUR):
                    label = classify(text, page, target=target)
                    for part in label["part_states"]:
                        if part["transition_required"]:
                            self.assertTrue(part["authorized"] and part["context_resolved"],
                                            (page["current_envelope"], text, part))
                    if label["transition_required"]:
                        self.assertTrue(label["authorized"])


if __name__ == "__main__":
    unittest.main()
