"""
GO-DECISION-ARCHITECTURE-01 - the parts of the GO Decision Architecture
directive (2026-08-29) that were implemented, plus the guards proving
the parts that were NOT implemented stayed out.

The second half matters as much as the first. The directive asked for a
four-bin unresolved-state vocabulary and for Helix to be redefined as
stakeholder-frame shear. Neither was built: the first would give the
same unresolved state two names alongside vocabularies that are already
closed and tested, and the second contradicts the mandatory invariants
of a CURRENT contract (governance/current/contracts/
CIC-SPIN-INTELLIGENCE-v1.1.md). Tests below pin the existing
vocabularies exactly, so a future session cannot quietly add the
parallel set without a test going red and asking why.

What WAS implemented is framing text over the same single model call -
no new field, no new closed set, no schema or parser change. These
tests read the prompt strings directly, which is the only place the
behaviour lives.
"""
from __future__ import annotations

import unittest

from services.spin import (
    BEHAVIORAL_CONTRACT,
    run_spin,
    HELIX_ABSTAINING_ASSESSMENTS,
    HELIX_ASSERTING_ASSESSMENTS,
    KNOWN_HELIX_ASSESSMENTS,
    KNOWN_HELIX_AXES,
    SPIN_WORLD_OBJECTIVES,
    _build_prompt,
)
from services.case_workspace import (
    KNOWN_SPIN_DELTA_CLASSIFICATIONS,
    SPIN_KIND_FIRST,
    SPIN_WORLD_SURVIVAL,
)


def _survival_prompt() -> str:
    return _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [], world=SPIN_WORLD_SURVIVAL)


def _ordinary_prompt() -> str:
    return _build_prompt(SPIN_KIND_FIRST, "rfp.pdf", [], [], [], world=None)


class SurvivalTriageOrderingTests(unittest.TestCase):
    """Item 4 - Survival Mode as a constrained triage solver."""

    QUESTIONS = (
        "WHAT MUST REMAIN SAFE?",
        "WHAT CANNOT BE ALLOWED TO FAIL?",
        "WHICH UPCOMING CHOICES ARE IRREVERSIBLE?",
        "WHAT IS THE INDISPENSABLE MISSING DATA?",
        "WHICH WORK COULD SAFELY HALT TO BUY DECISION TIME?",
        "WHAT ASSUMPTION, IF FALSE, INVALIDATES THIS RECOVERY PATH?",
    )

    def test_all_six_questions_are_present(self):
        prompt = _survival_prompt()
        for question in self.QUESTIONS:
            self.assertIn(question, prompt)

    def test_questions_appear_in_the_specified_order(self):
        # The ordering IS the mechanism - life-safety must be asked
        # before cost exposure, or the triage is just a longer list.
        prompt = _survival_prompt()
        positions = [prompt.index(question) for question in self.QUESTIONS]
        self.assertEqual(positions, sorted(positions))

    def test_the_original_attention_topics_were_preserved_not_replaced(self):
        # Restructuring must not quietly drop evidenced product content
        # from CLAUDE-HOLODECK-WORLDS-SPIN-01.
        prompt = _survival_prompt()
        for topic in (
            "disqualification or eligibility risk", "mandatory requirements",
            "conflicting instructions", "unresolved addenda",
            "authority ambiguity", "procurement traps", "commissioning gaps",
            "operational incompatibility",
        ):
            self.assertIn(topic, prompt)

    def test_world_objective_is_still_the_product_defined_constant(self):
        self.assertIn(SPIN_WORLD_OBJECTIVES[SPIN_WORLD_SURVIVAL], _survival_prompt())

    def test_games_played_self_report_survived_the_restructure(self):
        prompt = _survival_prompt()
        self.assertIn("games_played", prompt)
        self.assertIn("Change Game", prompt)
        self.assertIn("Never fabricate", prompt)

    def test_anti_padding_guard_survived_the_restructure(self):
        prompt = _survival_prompt()
        self.assertIn("NOT license", prompt)
        self.assertIn("Prioritize by genuine consequence, not by count", prompt)

    def test_halting_work_is_offered_as_an_option_never_directed(self):
        # Question 5 is adjacent to stop-work, which is consequential.
        prompt = _survival_prompt()
        self.assertIn("as an OPTION for a human to weigh", prompt)
        self.assertIn("You are not directing a stop", prompt)

    def test_survival_pass_can_never_conclude_a_project_should_end(self):
        # constitutional-invariants.md #17: project termination is never
        # produced by ordinary viability/recovery analysis.
        self.assertIn("never conclude", _survival_prompt())

    def test_unknown_window_cannot_claim_urgency(self):
        # The temporal failure mode named in the Decision Mechanics
        # charter 4.3: "we do not know when" becoming "it is urgent" is
        # truth-promotion wearing scheduling clothes.
        prompt = _survival_prompt()
        self.assertIn("never let an UNKNOWN window claim urgency", prompt)
        self.assertIn("'we do not know when' is not 'it is urgent'", prompt)

    def test_ordinary_spin_is_completely_unaffected(self):
        prompt = _ordinary_prompt()
        self.assertNotIn("SURVIVAL MODE", prompt)
        self.assertNotIn("games_played", prompt)
        for question in self.QUESTIONS:
            self.assertNotIn(question, prompt)


class CognitiveStoppingTests(unittest.TestCase):
    """Item 1 - stop expanding when reasoning stops reducing uncertainty."""

    def test_stopping_rule_is_stated(self):
        self.assertIn("Know when to stop", BEHAVIORAL_CONTRACT)
        self.assertIn("stops changing what you can honestly conclude", BEHAVIORAL_CONTRACT)

    def test_stopping_is_framed_as_a_result_not_a_failure(self):
        self.assertIn("Stopping honestly is a result, not a failure", BEHAVIORAL_CONTRACT)

    def test_residue_is_recorded_in_the_vocabulary_that_already_exists(self):
        # The whole point: the unresolved state has ONE name, not two.
        self.assertIn("'indeterminate'", BEHAVIORAL_CONTRACT)
        self.assertIn("abstaining", BEHAVIORAL_CONTRACT)

    def test_the_stopping_rule_reaches_every_spin(self):
        # Not survival-only. BEHAVIORAL_CONTRACT is the SYSTEM prompt at
        # services/spin.py's single call site, passed unconditionally -
        # so this asserts the real delivery mechanism rather than
        # looking for the text in _build_prompt, which never carries it.
        from unittest.mock import patch

        for world in (None, SPIN_WORLD_SURVIVAL):
            with patch("services.spin.call_llm_json") as mock_call:
                mock_call.return_value = type(
                    "Outcome", (),
                    {"ran": False, "skipped_reason": "stubbed", "parsed": None,
                     "raw_text": None, "provider": None, "model": None,
                     "requested_at": None, "stop_reason": None},
                )()
                run_spin(
                    spin_kind=SPIN_KIND_FIRST, document_filename="rfp.pdf",
                    candidate_requirements=[], governed_requirements=[],
                    milestones=[], world=world,
                )
            system_prompt = mock_call.call_args.kwargs["system_prompt"]
            self.assertIs(system_prompt, BEHAVIORAL_CONTRACT)
            self.assertIn("Know when to stop", system_prompt)
            self.assertIn("only against what was knowable when it was", system_prompt)


class TemporalAntiSmugglingTests(unittest.TestCase):
    """Item 2 - judge against the horizon knowable at the time."""

    def test_past_decisions_are_judged_on_what_was_knowable_then(self):
        self.assertIn("only against what was knowable when it was", BEHAVIORAL_CONTRACT)

    def test_the_three_horizon_terms_are_named(self):
        # evidence available, time remaining, authority held.
        for term in ("evidence then available", "time then remaining", "authority the decider then held"):
            self.assertIn(term, BEHAVIORAL_CONTRACT)

    def test_hindsight_is_explicitly_forbidden(self):
        self.assertIn("Never use later evidence to", BEHAVIORAL_CONTRACT)
        self.assertIn("not a fault", BEHAVIORAL_CONTRACT)


class ObservableConstraintsOnlyTests(unittest.TestCase):
    """Item 2 - no speculation about motive, intent, or state of mind."""

    def test_motive_speculation_is_forbidden(self):
        self.assertIn("Never speculate about anyone's motives", BEHAVIORAL_CONTRACT)

    def test_malice_and_carelessness_are_named_specifically(self):
        self.assertIn("carelessness or bad faith", BEHAVIORAL_CONTRACT)

    def test_the_rule_carries_a_worked_contrast(self):
        # A rule with an example is followed; a rule without one is
        # agreed with and then not followed.
        self.assertIn(
            "'The addendum is not reflected in the mechanical drawings' is a finding",
            BEHAVIORAL_CONTRACT,
        )
        self.assertIn(
            "'the mechanical team ignored the addendum' is an accusation the evidence "
            "does not support",
            BEHAVIORAL_CONTRACT,
        )


class BoundedExecutionAuthorityTests(unittest.TestCase):
    """Item 5 - already enforced before this directive; pinned so it
    stays that way. Nothing was added for this item."""

    def test_spin_can_never_decide_anything(self):
        self.assertIn("You are never authorized to decide anything here", BEHAVIORAL_CONTRACT)

    def test_only_a_human_creates_governed_records(self):
        # Inherited verbatim from services/project_qa.py's own contract.
        self.assertIn("you never create one yourself", BEHAVIORAL_CONTRACT)
        self.assertIn(
            "only the human project manager does that, through ARCHIOSK's own governed",
            BEHAVIORAL_CONTRACT,
        )


class NoParallelVocabularyTests(unittest.TestCase):
    """
    The guard on what was deliberately NOT built.

    The directive asked for [KNOWN] | [UNKNOWN] | [CONTRADICTED] |
    [TIME-CRITICAL] bins. These are pinned exactly so that adding that
    set alongside them turns a test red rather than passing silently.
    """

    def test_delta_classification_vocabulary_is_unchanged(self):
        self.assertEqual(
            set(KNOWN_SPIN_DELTA_CLASSIFICATIONS),
            {
                "new", "strengthened", "weakened", "resolved", "unchanged",
                "superseded", "indeterminate", "new_verification_gap",
            },
        )

    def test_no_four_bin_vocabulary_was_introduced(self):
        for bin_name in ("[KNOWN]", "[UNKNOWN]", "[CONTRADICTED]", "[TIME-CRITICAL]"):
            self.assertNotIn(bin_name, BEHAVIORAL_CONTRACT)
            self.assertNotIn(bin_name, _survival_prompt())

    def test_helix_vocabulary_is_unchanged(self):
        # CIC-SPIN-INTELLIGENCE v1.1 is CURRENT and its mandatory
        # invariants bind Helix to an interface/convergence model. The
        # directive's stakeholder-shear redefinition is not implemented,
        # and this pins the vocabulary that would have had to change.
        self.assertEqual(
            set(KNOWN_HELIX_ASSESSMENTS),
            {
                "converged", "dimension_conflict", "positional_conflict",
                "semantic_mismatch", "handshake_deficit", "propagation_lag",
                "stage_maturity_mismatch", "residual_ambiguity",
                "evidence_unavailable", "legitimate_deferred",
            },
        )
        self.assertEqual(KNOWN_HELIX_AXES, ("horizontal", "longitudinal", "both"))
        self.assertEqual(
            HELIX_ASSERTING_ASSESSMENTS | HELIX_ABSTAINING_ASSESSMENTS,
            set(KNOWN_HELIX_ASSESSMENTS),
        )

    def test_no_hard_coded_stakeholder_frames_reached_the_prompt(self):
        # CIC-SPIN-INTELLIGENCE v1.1 forbids Helix becoming a hard-coded
        # trade hierarchy. A fixed Architect/GC/Owner observer set is
        # adjacent enough to that to need contract revision first.
        prompt = _survival_prompt()
        for frame in ("Architect,", "General Contractor", "Shear(", "observer frame"):
            self.assertNotIn(frame, prompt)


if __name__ == "__main__":
    unittest.main()
