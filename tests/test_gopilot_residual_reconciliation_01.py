"""GOPILOT CORE step 3 - residual intent reconciliation.

A turn every deterministic handler declines is interpreted through the existing
residual model classification (classify_residual_admission). Its intent label
used to say UNKNOWN regardless. Now interpret_message hands back the residual it
ACTUALLY used (a sink - no second model call), and classify_intent_envelope
adopts the model's intent class as the envelope - understanding only.
Authorization, transition state, target and landing stay deterministic, and an
ASIDE (the model found no grounding in this project) never resolves to the
current project.
"""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import services.conversation_interpreter as ci
from services.conversational_turn import ConversationalTurnResult
from services.conversation_interpreter import (
    INTENT_STATE_IN_ENVELOPE,
    INTENT_STATE_NOT_AUTHORIZED,
    INTENT_STATE_UNRESOLVED,
)
from tests.test_gopilot_transition_state_01 import DEVELOPER, HARBOUR
from tests.test_gopilot_turn_coverage_01 import _App, capture_labels, labelling_off
from tests.test_gopilot_turn_frame_01 import CUSTOMER, classify, frame

PROJECT_PAGE = frame("PROJECT", project_id="p1")
CASE_PAGE = frame("INVESTIGATION_STUDY", project_id="p1", case_id="c1")
RESIDUAL_WORDS = "Stair pressurization interplay with the atrium smoke exhaust"
ZETA_WORDS = "Zeta Tower lease terms for the parking levels"


def residual(outcome, intent_class=None):
    return SimpleNamespace(outcome=outcome, intent_class=intent_class)


def with_residual(text, page, res, target=None):
    from services.master_commands import application_destinations
    return ci.classify_intent_envelope(text, page, navigation_target=target,
                                       application_destinations=application_destinations(),
                                       residual=res)


class ResidualLabelsDescribeTheInterpretedIntent(unittest.TestCase):
    def test_1_a_confident_residual_no_longer_carries_unknown(self):
        before = classify(RESIDUAL_WORDS, PROJECT_PAGE)
        self.assertEqual(before["envelope"], "UNKNOWN")
        for intent_class, envelope in (("general_answer", "PROJECT"), ("organize_advice", "PROJECT"),
                                       ("external_research", "PROJECT"),
                                       ("propose_work_product_issue", "PROJECT"),
                                       ("contextual_reference", "DOCUMENT_SOURCE"),
                                       ("propose_source_revision", "DOCUMENT_SOURCE"),
                                       ("investigate_requirement", "INVESTIGATION_STUDY"),
                                       ("propose_draft_rfi", "INVESTIGATION_STUDY"),
                                       ("propose_apply_findings", "INVESTIGATION_STUDY")):
            with self.subTest(intent_class=intent_class):
                outcome = "action_proposed" if intent_class.startswith("propose_") else "project_inquiry"
                after = with_residual(RESIDUAL_WORDS, PROJECT_PAGE, residual(outcome, intent_class))
                self.assertEqual(after["envelope"], envelope)
                self.assertEqual(after["classified_by"], "residual_model")

    def test_a_grounded_project_inquiry_operates_in_the_current_project(self):
        label = with_residual(RESIDUAL_WORDS, PROJECT_PAGE, residual("project_inquiry", "general_answer"))
        self.assertEqual(label["state"], INTENT_STATE_IN_ENVELOPE)

    def test_2_deterministic_classification_stays_first_and_unchanged(self):
        for text, page in (("Issue this RFI", CASE_PAGE), ("Take me to Help Centre", PROJECT_PAGE),
                           ("What does this say?", frame("DOCUMENT_SOURCE", project_id="p1",
                                                         selected_source_id="s1"))):
            with self.subTest(text=text):
                plain = classify(text, page)
                offered = with_residual(text, page, residual("action_proposed", "propose_apply_findings"))
                self.assertEqual(offered, plain)
                self.assertEqual(offered["classified_by"], "deterministic")

    def test_3_the_model_creates_no_authority_target_transition_or_landing(self):
        # Authority: a customer's residual RFI proposal stays unauthorized.
        customer = with_residual(RESIDUAL_WORDS, frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER,
                                                       project_id="d1"),
                                 residual("action_proposed", "propose_draft_rfi"))
        self.assertEqual((customer["state"], customer["authorized"]), (INTENT_STATE_NOT_AUTHORIZED, False))
        # A pass token gains nothing from a model's opinion.
        token = with_residual(RESIDUAL_WORDS, frame("STAKEHOLDER_TOKEN", envelope_set=["STAKEHOLDER_TOKEN"],
                                                    selected_source_id="s1"),
                              residual("project_inquiry", "general_answer"))
        self.assertEqual(token["state"], INTENT_STATE_NOT_AUTHORIZED)
        # Target: the model never names a project; only the access-scoped rule can.
        label = with_residual(RESIDUAL_WORDS, frame("APPLICATION"), residual("project_inquiry", "general_answer"))
        self.assertIsNone(label["target_project_id"])
        self.assertEqual(label["state"], INTENT_STATE_UNRESOLVED)   # no project to be in
        # Transition: the developer overlay does not become a project move on a guess.
        dev = with_residual(RESIDUAL_WORDS, frame("DEVELOPER_INSPECT", envelope_set=DEVELOPER),
                            residual("project_inquiry", "general_answer"))
        self.assertFalse(dev["transition_required"])
        # Landing: the label carries none.
        self.assertNotIn("landing", label)

    def test_4_ambiguous_and_unclassified_residuals_stay_unresolved(self):
        for res in (residual("clarification_required"), residual("declined"),
                    residual("project_inquiry", "not_a_real_class"), None):
            with self.subTest(res=res):
                label = with_residual(RESIDUAL_WORDS, PROJECT_PAGE, res)
                self.assertEqual((label["envelope"], label["state"]), ("UNKNOWN", INTENT_STATE_UNRESOLVED))
                self.assertIsNone(label["classified_by"])

    def test_5_an_ungrounded_reference_never_resolves_to_the_current_project(self):
        label = with_residual(ZETA_WORDS, PROJECT_PAGE, residual("conversational_contribution", "general_answer"))
        self.assertEqual(label["envelope"], "PROJECT")
        self.assertEqual(label["state"], INTENT_STATE_UNRESOLVED)
        self.assertFalse(label["context_resolved"])
        self.assertIsNone(label["target_project_id"])
        self.assertFalse(label["transition_required"])


def _turn(intent_class, *, grounded_in=(), reply="An aside reply.", proposed=None):
    return ConversationalTurnResult(ran=True, intent_class=intent_class, reply_text=reply,
                                    grounded_in=list(grounded_in), proposed_action=proposed)


class ThroughTheRealRoutes(_App):
    """The interpreted turn and its label, end to end - and the reply unchanged."""

    def setUp(self):
        super().setUp()
        from services.case_workspace import CaseWorkspaceStore

        self.boss = self.client("cover_boss")
        self.pid = self.upload(self.boss, "Residual Project")
        self.store = CaseWorkspaceStore(str(self.tmp))
        self.case = self.store.create_case(self.store.get(self.pid), "Case", "objective",
                                           created_by="cover_boss")
        self.url = "/projects/%s/workspace/cases/%s/messages" % (self.pid, self.case["id"])

    def _post(self, text, turn):
        def project_qa_must_not_run(*a, **k):
            raise AssertionError("current-project evidence was consulted")

        with patch.object(ci, "run_conversational_turn", return_value=turn) as model, \
                patch.object(ci, "answer_project_question", side_effect=project_qa_must_not_run):
            with capture_labels() as seen:
                self.boss.post(self.url, data={"text": text})
            reply_on = self.last_reply(self.pid, self.case["id"])
            with labelling_off():
                self.boss.post(self.url, data={"text": text})
            reply_off = self.last_reply(self.pid, self.case["id"])
        return seen[0]["labels"]["intent"], reply_on, reply_off, model

    def test_an_inaccessible_reference_is_an_ungrounded_aside_not_current_project_evidence(self):
        intent, on, off, model = self._post(ZETA_WORDS, _turn("general_answer", reply="I can't place Zeta Tower."))
        self.assertEqual((intent["envelope"], intent["state"]), ("PROJECT", INTENT_STATE_UNRESOLVED))
        self.assertEqual(intent["classified_by"], "residual_model")
        self.assertIsNone(intent["target_project_id"])
        self.assertEqual(on, off)                    # 6: the reply is unchanged
        self.assertEqual(model.call_count, 2)        # one model call per turn - no second one for the label

    def test_a_residual_proposal_is_labelled_as_the_same_intent_and_nothing_executes(self):
        proposed = {"intent_class": "propose_draft_rfi", "description": "Draft an RFI on stair pressurization"}
        turn = _turn("propose_draft_rfi", reply="Shall I draft an RFI?", proposed=proposed)
        captured = []
        import routes.workspace as ws
        original = ws.interpret_message

        def keep(**kwargs):
            result = original(**kwargs)
            captured.append(result)
            return result

        with patch.object(ws, "interpret_message", side_effect=keep):
            intent, on, off, _ = self._post(RESIDUAL_WORDS, turn)
        self.assertTrue(captured[0].action_taken.startswith("residual_action_proposed:propose_draft_rfi"))
        self.assertEqual(intent["envelope"], "INVESTIGATION_STUDY")        # the SAME intent
        self.assertEqual(intent["classified_by"], "residual_model")
        self.assertEqual(intent["state"], INTENT_STATE_IN_ENVELOPE)
        self.assertEqual(on, off)
        self.assertEqual(self.store.get(self.pid).rfi_drafts, [])   # proposed, never drafted

    def test_a_deterministic_turn_never_consults_the_residual(self):
        with patch.object(ci, "run_conversational_turn") as model:
            with capture_labels() as seen:
                self.boss.post(self.url, data={"text": "Draft an RFI for the stair"})
        self.assertFalse(model.called)
        self.assertEqual(seen[0]["labels"]["intent"]["classified_by"], "deterministic")

    def test_quick_start_carries_its_precomputed_residual_into_the_label(self):
        url = "/projects/%s/workspace/quick-start" % self.pid
        with patch.object(ci, "run_conversational_turn",
                          return_value=_turn("general_answer", reply="Unplaced.")) as model:
            with capture_labels() as seen:
                self.boss.post(url, data={"text": ZETA_WORDS})
        labelled = [s for s in seen if s["labels"]]
        self.assertEqual(len(labelled), 1)
        self.assertEqual(labelled[0]["labels"]["intent"]["classified_by"], "residual_model")
        self.assertEqual(model.call_count, 1)        # no second model call for the label


if __name__ == "__main__":
    unittest.main()
