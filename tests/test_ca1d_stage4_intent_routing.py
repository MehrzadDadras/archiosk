"""CLAUDE-CA1D-COMPOSER-SPINE-01 Stage 4 - intent routing and proposed actions.

Product Owner authorized 2026-08-23: "Authorize Stage 4 activation - proceed
with intent routing and proposed actions."

Stage 3A wired `run_conversational_turn` into the live dispatch chain for
ADMISSION only, and deliberately never read `intent_class` or
`proposed_action`. Stage 4 reads both. What these tests guard is the line that
does NOT move as a result:

    a model classification may decide how a message is UNDERSTOOD,
    never what is DONE.

Every consequential intent therefore ends in a described proposal and touches
no handler at all, and the reviewer still performs the action themselves
through the real Approval-Gated route.

Hermetic by construction. `residual_admission` is an existing parameter of
`interpret_message`, so these tests hand the routing decision in directly and
never reach an Anthropic call - the classification seam is already covered by
tests/test_ca1d_stage3a_residual_admission.py.
"""
from __future__ import annotations

import inspect
import re
import unittest
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import DEFAULT, patch

from services import conversation_interpreter as ci
from services.case_workspace import CaseWorkspaceStore
from services.conversational_turn import (
    CONSEQUENTIAL_INTENT_CLASSES,
    INTENT_DISPATCH_TABLE,
    SAFETY_CONSEQUENTIAL,
)

def _code_of(func) -> str:
    """Comments describing a boundary must not be able to satisfy a guard
    that the boundary is absent - the router's own comment names
    `record_analysis` precisely to explain why that path writes."""
    src = inspect.getsource(func)
    return re.sub(r"(?m)#.*$", "", src)


# Every handler that writes anything, or reaches an external boundary.
# A consequential turn must reach none of them.
_MUTATING_HANDLERS = (
    "_handle_investigate_requirement",
    "_handle_organize_advice",
    "_handle_contextual_reference",
    "_handle_project_question",
)


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(mkdtemp())
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-s4")
        self.source = self.store.add_source(
            self.workspace, name="PSD-RFP-001.md", file_path=str(self.tmp / "a.md"),
            kind="project_document",
        )

    def _interpret(self, text, admission, case=None, selected_object=None):
        # No `anchor`: one short-circuits at `anchor_acknowledged` well before
        # the residual block, so an anchor-derived referent can never reach the
        # router. `selected_object` is the slot that actually does.
        return ci.interpret_message(
            text, self.workspace, case, self.store, self.tmp, "reviewer",
            None, selected_object=selected_object, residual_admission=admission,
        )

    @staticmethod
    def _admission(outcome, **kw):
        return ci.ResidualAdmission(outcome, **kw)


class ConsequentialIntentsNeverActTests(_Base):
    """The whole point of the stage boundary."""

    def test_no_handler_is_called_for_a_consequential_intent(self):
        for intent in CONSEQUENTIAL_INTENT_CLASSES:
            with self.subTest(intent=intent):
                admission = self._admission(
                    ci.RESIDUAL_ADMISSION_PROPOSAL,
                    intent_class=intent,
                    reflection="Before I proceed: confirm that's right.",
                    proposed_action={"intent_class": intent, "description": "the thing"},
                )
                with patch.multiple(
                    ci, **{name: DEFAULT for name in _MUTATING_HANDLERS}
                ) as spies:
                    result = self._interpret("qqzz", admission)
                for name, spy in spies.items():
                    self.assertFalse(spy.called, f"{intent} reached {name}")
                self.assertEqual(result.action_taken, f"residual_action_proposed:{intent}")

    def test_the_reply_says_it_has_not_acted_and_names_the_real_route(self):
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_PROPOSAL,
            intent_class="propose_draft_rfi",
            reflection="Before I proceed: confirm that's right.",
            proposed_action={"intent_class": "propose_draft_rfi", "description": "draft an RFI about the sill"},
        )
        reply = self._interpret("qqzz", admission).reply_text
        self.assertIn("have not done this", reply)
        self.assertIn("Issue RFI", reply)
        self.assertIn("approval", reply)

    def test_it_does_not_offer_to_act_on_a_yes(self):
        """A yes/no offer implies something is standing by to execute on
        "yes". Nothing is, so the reply must not imply it."""
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_PROPOSAL,
            intent_class="propose_apply_findings",
            proposed_action={"intent_class": "propose_apply_findings", "description": "apply them"},
        )
        reply = self._interpret("qqzz", admission).reply_text.lower()
        for offer in ("shall i", "should i", "would you like me to", "say yes", "confirm and i"):
            with self.subTest(phrase=offer):
                self.assertNotIn(offer, reply)

    def test_the_proposal_branch_names_no_handler_at_all(self):
        """Structural, not behavioural: the branch returns before any handler
        is reachable, so "never execution" is control flow rather than a flag
        that could be misread."""
        src = inspect.getsource(ci.interpret_message)
        branch = src[src.index("RESIDUAL_ADMISSION_PROPOSAL"):]
        branch = branch[: branch.index("RESIDUAL_ADMISSION_INQUIRY")]
        for handler in _MUTATING_HANDLERS:
            with self.subTest(handler=handler):
                self.assertNotIn(handler, branch)

    def test_every_gated_intent_has_a_route_label(self):
        """A proposal that cannot name where the reviewer should go is worse
        than no proposal."""
        for intent, meta in INTENT_DISPATCH_TABLE.items():
            if meta["safety"] != SAFETY_CONSEQUENTIAL:
                continue
            with self.subTest(intent=intent):
                self.assertIn(intent, ci._PROPOSAL_ROUTE_LABELS)


class SafeIntentsReachTheirExistingHandlerTests(_Base):
    def test_contextual_reference_routes_to_its_own_handler(self):
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_INQUIRY, intent_class="contextual_reference",
        )
        with patch.object(ci, "_handle_contextual_reference") as spy, \
             patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", admission)
        self.assertTrue(spy.called)
        self.assertFalse(qa.called)

    def test_organize_advice_routes_to_its_own_handler(self):
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_INQUIRY, intent_class="organize_advice",
        )
        with patch.object(ci, "_handle_organize_advice") as spy, \
             patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", admission)
        self.assertTrue(spy.called)
        self.assertFalse(qa.called)

    def test_general_answer_still_falls_through_to_grounded_project_qa(self):
        """Stage 4 adds routes; it does not take the default away."""
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_INQUIRY, intent_class="general_answer",
        )
        with patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", admission)
        self.assertTrue(qa.called)

    def test_an_unset_intent_class_falls_through_rather_than_erroring(self):
        """Stage 3A admissions carried no intent_class at all. A stored or
        in-flight one must not break the router."""
        admission = self._admission(ci.RESIDUAL_ADMISSION_INQUIRY)
        with patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", admission)
        self.assertTrue(qa.called)


class TheOneSafeIntentThatWritesTests(_Base):
    """`investigate_requirement` is classified SAFE (record_analysis is
    governed but provisional, with no Approval Gate) - but it is still the
    only safe intent that WRITES. The deterministic path reaches it only with
    a Requirement question AND a Requirement anchor; a model classification
    must clear the same bar, or a misread turn could record an Analysis
    against the wrong thing.
    """

    def _admission_for(self):
        return self._admission(
            ci.RESIDUAL_ADMISSION_INQUIRY, intent_class="investigate_requirement",
        )

    def test_it_declines_without_an_open_case(self):
        """No Case means no honest place to put a Finding."""
        with patch.object(ci, "_handle_investigate_requirement") as spy, \
             patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", self._admission_for(), case=None)
        self.assertFalse(spy.called)
        self.assertTrue(qa.called)

    def test_it_declines_without_a_resolvable_requirement_referent(self):
        case = {"id": "c1", "source_ids": [], "conversation": []}
        with patch.object(ci, "_handle_investigate_requirement") as spy, \
             patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", self._admission_for(), case=case)
        self.assertFalse(spy.called)
        self.assertTrue(qa.called)

    def test_a_selected_source_is_not_mistaken_for_a_requirement(self):
        """The referent must be a Requirement specifically - an open Source is
        not one, and must not be investigated as though it were."""
        case = {"id": "c1", "source_ids": [], "conversation": []}
        selected = {"anchor_type": "source", "anchor_id": self.source["id"], "description": "the RFP"}
        with patch.object(ci, "_handle_investigate_requirement") as spy, \
             patch.object(ci, "_handle_project_question") as qa:
            self._interpret("qqzz", self._admission_for(), case=case, selected_object=selected)
        self.assertFalse(spy.called)
        self.assertTrue(qa.called)


class BoundariesThatDidNotMoveTests(_Base):
    def test_clarification_still_wins_and_still_acts_on_nothing(self):
        admission = self._admission(
            ci.RESIDUAL_ADMISSION_CLARIFY, reply_text="Which one did you mean?",
        )
        with patch.multiple(ci, **{n: DEFAULT for n in _MUTATING_HANDLERS}) as spies:
            result = self._interpret("qqzz", admission)
        for name, spy in spies.items():
            self.assertFalse(spy.called, f"clarification reached {name}")
        self.assertEqual(result.action_taken, "residual_clarification_requested")

    def test_the_router_creates_no_governed_object(self):
        src = _code_of(ci._route_safe_intent)
        for forbidden in ("record_", "add_finding", "apply_", "_require_approval", "store.save"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)

    def test_the_router_calls_only_handlers_that_already_existed(self):
        """Stage 4 introduces no new mutating code path of its own - it routes
        to handlers the deterministic grammar already reached."""
        src = _code_of(ci._route_safe_intent)
        called = {name for name in _MUTATING_HANDLERS if name + "(" in src}
        self.assertTrue(called)
        for name in called:
            self.assertTrue(hasattr(ci, name))


if __name__ == "__main__":
    unittest.main()
