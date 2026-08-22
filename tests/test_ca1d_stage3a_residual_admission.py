"""CLAUDE-CA1D-COMPOSER-SPINE-01 Stage 3A - Residual Admission Classification.

Product Owner authorized 2026-08-22, deliberately narrower than the
originally scoped Stage 3: the already-built run_conversational_turn seam
is wired into the live dispatch chain FOR ADMISSION ONLY.

Hermetic by construction - `run_conversational_turn` is always patched
with a deterministic fake. No Anthropic call is ever made, per CLAUDE.md's
standing rule for any test path that can reach an external boundary.
"""
import unittest
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import mkdtemp
from unittest.mock import patch

from services import conversation_interpreter as ci
from services.case_workspace import CaseWorkspaceStore
from services.security_policy import DECISION_ALLOW


@dataclass
class _FakeTurn:
    """Mirrors the fields Stage 3A actually reads - nothing else."""

    ran: bool = True
    reply_text: str = ""
    grounded_in: list = field(default_factory=list)
    needs_clarification: bool = False
    candidate_referents: list = field(default_factory=list)
    # Deliberately present and deliberately never read by Stage 3A.
    intent_class: str = "propose_draft_rfi"
    proposed_action: dict = field(default_factory=lambda: {"description": "would be Stage 4"})


class _Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(mkdtemp())
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("proj-3a")
        self.store.add_source(
            self.workspace, name="PSD-RFP-001.md", file_path=str(self.tmp / "a.md"),
            kind="project_document",
        )

    def _admit(self, text, turn, workspace=None):
        allow = type("P", (), {"decision": DECISION_ALLOW, "controlling_layer": "x", "reason": ""})()
        with patch.object(ci, "_evaluate_external_ai_policy", return_value=allow), \
             patch.object(ci, "run_conversational_turn", return_value=turn) as spy:
            result = ci.classify_residual_admission(
                text, workspace or self.workspace, self.store,
            )
        return result, spy


class ResidualOutcomeMappingTests(_Base):
    def test_grounded_answer_is_admitted_as_project_inquiry(self):
        result, _ = self._admit("Revisa este paquete.", _FakeTurn(reply_text="…", grounded_in=["PSD-RFP-001.md"]))
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_INQUIRY)
        self.assertTrue(result.admitted)

    def test_clarification_need_reaches_the_existing_clarification_path(self):
        result, _ = self._admit("No, the other one.", _FakeTurn(reply_text="Which one?", needs_clarification=True))
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_CLARIFY)
        self.assertEqual(result.reply_text, "Which one?")

    def test_multiple_candidate_referents_force_clarification_not_a_guess(self):
        turn = _FakeTurn(
            reply_text="Did you mean the north or south riser?",
            candidate_referents=[{"anchor_type": "source", "anchor_id": "a"},
                                 {"anchor_type": "source", "anchor_id": "b"}],
        )
        result, _ = self._admit("That one.", turn)
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_CLARIFY)

    def test_ungrounded_answered_turn_is_a_conversational_aside(self):
        result, _ = self._admit(
            "The consultant called me this morning.", _FakeTurn(reply_text="Noted."),
        )
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_ASIDE)
        self.assertEqual(result.reply_text, "Noted.")

    def test_seam_that_did_not_run_declines_and_preserves_prior_behaviour(self):
        result, _ = self._admit("anything", _FakeTurn(ran=False))
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_DECLINED)
        self.assertFalse(result.admitted)


class NoRouterProofTests(_Base):
    def test_intent_class_and_proposed_action_are_never_consulted(self):
        """Stage 3A must not become the full intent_class dispatch table.

        The fake returns a CONSEQUENTIAL intent_class and a populated
        proposed_action. If Stage 3A read either, this grounded turn
        would not map to a plain project inquiry.
        """
        turn = _FakeTurn(
            reply_text="…", grounded_in=["x"],
            intent_class="propose_draft_rfi",
            proposed_action={"description": "draft an RFI"},
        )
        result, _ = self._admit("Diga-me se isso vai aumentar o custo.", turn)
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_INQUIRY)

    def test_module_source_never_reads_intent_class_in_the_admission_path(self):
        import inspect

        src = inspect.getsource(ci.classify_residual_admission)
        for forbidden in ("intent_class", "proposed_action", "INTENT_CLASS_"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)


class CostBoundTests(_Base):
    def test_empty_project_never_spends_a_model_call(self):
        empty = self.store.get_or_create("proj-empty")
        result, spy = self._admit("cualquier cosa", _FakeTurn(), workspace=empty)
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_DECLINED)
        spy.assert_not_called()

    def test_policy_denial_never_spends_a_model_call(self):
        deny = type("P", (), {"decision": "deny", "controlling_layer": "baseline", "reason": "no"})()
        with patch.object(ci, "_evaluate_external_ai_policy", return_value=deny), \
             patch.object(ci, "run_conversational_turn") as spy:
            result = ci.classify_residual_admission("x", self.workspace, self.store)
        self.assertEqual(result.outcome, ci.RESIDUAL_ADMISSION_DECLINED)
        spy.assert_not_called()


class DeterministicPrecedenceTests(unittest.TestCase):
    """Stage 3A is residual: anything an earlier handler claims never reaches it."""

    def test_explicit_actions_are_claimed_before_any_residual_call(self):
        for text in ("Draft an RFI from Finding 3.", "Compare A with B.", "Analyze this drawing."):
            with self.subTest(text=text):
                low = text.lower()
                claimed = (
                    low.startswith(("analyze", "analyse"))
                    or low.startswith("compare") or " compare " in f" {low} "
                    or ("draft" in low and "rfi" in low)
                )
                self.assertTrue(claimed)

    def test_acknowledgements_and_greetings_are_claimed_before_residual(self):
        for text in ("Okay thanks.", "hello", "thanks"):
            with self.subTest(text=text):
                self.assertTrue(ci._looks_like_conversational_utterance(text.lower()))

    def test_project_questions_still_resolve_deterministically_without_a_model(self):
        """Punctuation/lexicon matches must not start paying for a model call."""
        for text in ("Is this going to cost us more?", "Review this package and tell me what matters."):
            with self.subTest(text=text):
                self.assertTrue(ci._looks_like_project_question(text.lower()))


class AuthorityBoundaryTests(_Base):
    def test_admission_creates_no_governed_object(self):
        before = (
            len(self.workspace.cases), len(self.workspace.findings),
            len(self.workspace.claims), len(self.workspace.relationships),
            len(self.workspace.requirements), len(self.workspace.tasks),
        )
        for turn in (_FakeTurn(reply_text="…", grounded_in=["x"]),
                     _FakeTurn(reply_text="?", needs_clarification=True),
                     _FakeTurn(reply_text="Noted."),
                     _FakeTurn(ran=False)):
            self._admit("Vuelve al informe geotécnico.", turn)
        after = (
            len(self.workspace.cases), len(self.workspace.findings),
            len(self.workspace.claims), len(self.workspace.relationships),
            len(self.workspace.requirements), len(self.workspace.tasks),
        )
        self.assertEqual(before, after, "semantic admission must create no project authority")


if __name__ == "__main__":
    unittest.main()
