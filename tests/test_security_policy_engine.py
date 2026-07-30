"""
CLAUDE-P31 -- pure resolver tests for services.security_policy.
evaluate_action: precedence (floor -> baseline -> profile -> exception),
most-restrictive-wins, the exception ceiling, and the classification ->
control-bundle mapping. No Flask app, no persistence -- these exercise
the resolver directly, matching services/environment_capabilities.py's
own CLAUDE-P30 test-file precedent of testing the pure function
separately from its route wiring.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest

from services.security_policy import (
    ACTION_CROSS_PROJECT_REFERENCE,
    ACTION_EXPORT,
    ACTION_EXTERNAL_AI_REQUEST,
    ACTION_ORGANIZATION_PRIVATE_LEARNING,
    ACTION_SHARED_ARCHIOSK_CONTRIBUTION,
    ACTION_TECHNICAL_TELEMETRY,
    CLASSIFICATION_HIGHLY_RESTRICTED,
    CLASSIFICATION_RESTRICTED,
    CLASSIFICATION_STANDARD,
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_ISOLATE,
    DECISION_REQUIRE_APPROVAL,
    GOVERNED_ACTIONS,
    MANDATORY_FLOOR_DEFAULTS,
    SECURITY_CLAIMS_REGISTRY,
    CLAIM_PROHIBITED_FROM_CLAIMING,
    evaluate_action,
    is_valid_classification,
    profile_decision_for,
)


class MandatoryFloorTests(unittest.TestCase):
    def test_floor_default_applies_with_no_baseline_or_profile(self):
        for action_id in GOVERNED_ACTIONS:
            decision = evaluate_action(action_id)
            self.assertEqual(decision.decision, MANDATORY_FLOOR_DEFAULTS[action_id])
            self.assertEqual(decision.controlling_layer, "floor")

    def test_sensitive_actions_default_safely_when_nothing_resolves_them(self):
        # "A missing answer must not become permission" (Part V) --
        # applied as the actual floor default, not merely a UI hint.
        for action_id in (
            ACTION_CROSS_PROJECT_REFERENCE, ACTION_SHARED_ARCHIOSK_CONTRIBUTION,
        ):
            self.assertEqual(evaluate_action(action_id).decision, DECISION_DENY)
        self.assertEqual(evaluate_action(ACTION_ORGANIZATION_PRIVATE_LEARNING).decision, DECISION_REQUIRE_APPROVAL)

    def test_unsupported_action_id_is_reported_not_silently_allowed(self):
        decision = evaluate_action("not_a_real_action")
        self.assertEqual(decision.decision, "unsupported")

    def test_no_governed_action_exists_for_disabling_authentication_or_csrf(self):
        # The floor's unweakenability comes from these never being
        # expressible as a configurable action at all.
        for forbidden in ("disable_authentication", "disable_csrf", "disable_audit_log", "disable_rate_limiting"):
            self.assertNotIn(forbidden, GOVERNED_ACTIONS)


class BaselineCannotLoosenFloorTests(unittest.TestCase):
    def test_baseline_can_tighten_the_floor(self):
        # floor default for EXTERNAL_AI_REQUEST is ALLOW; a baseline may deny it.
        decision = evaluate_action(ACTION_EXTERNAL_AI_REQUEST, baseline_decision=DECISION_DENY)
        self.assertEqual(decision.decision, DECISION_DENY)
        self.assertEqual(decision.controlling_layer, "baseline")

    def test_baseline_cannot_loosen_the_floor(self):
        # floor default for ACTION_SHARED_ARCHIOSK_CONTRIBUTION is DENY;
        # a baseline claiming ALLOW must not actually loosen it.
        decision = evaluate_action(ACTION_SHARED_ARCHIOSK_CONTRIBUTION, baseline_decision=DECISION_ALLOW)
        self.assertEqual(decision.decision, DECISION_DENY)


class ProfileInheritsAndCannotLoosenTests(unittest.TestCase):
    def test_project_profile_inherits_baseline_when_it_has_no_opinion(self):
        decision = evaluate_action(
            ACTION_EXTERNAL_AI_REQUEST, baseline_decision=DECISION_DENY,
            profile_decision=profile_decision_for(CLASSIFICATION_STANDARD, ACTION_EXTERNAL_AI_REQUEST),
        )
        self.assertEqual(decision.decision, DECISION_DENY)
        self.assertEqual(decision.controlling_layer, "baseline")

    def test_project_profile_can_tighten_baseline(self):
        decision = evaluate_action(
            ACTION_EXPORT, baseline_decision=DECISION_ALLOW,
            profile_decision=profile_decision_for(CLASSIFICATION_HIGHLY_RESTRICTED, ACTION_EXPORT),
        )
        self.assertEqual(decision.decision, DECISION_DENY)
        self.assertEqual(decision.controlling_layer, "profile")

    def test_project_profile_cannot_loosen_baseline_or_floor(self):
        # Baseline denies export; profile (STANDARD -- no opinion on
        # export) must not be able to loosen that back to ALLOW.
        decision = evaluate_action(
            ACTION_EXPORT, baseline_decision=DECISION_DENY,
            profile_decision=profile_decision_for(CLASSIFICATION_STANDARD, ACTION_EXPORT),
        )
        self.assertEqual(decision.decision, DECISION_DENY)

    def test_classification_control_bundle_meaning_is_explicit(self):
        # "Do not use labels without explicit control meaning" (Part II.3).
        self.assertIsNone(profile_decision_for(CLASSIFICATION_STANDARD, ACTION_EXPORT))
        self.assertEqual(profile_decision_for(CLASSIFICATION_RESTRICTED, ACTION_EXTERNAL_AI_REQUEST), DECISION_DENY)
        self.assertEqual(profile_decision_for(CLASSIFICATION_HIGHLY_RESTRICTED, ACTION_EXPORT), DECISION_DENY)

    def test_unknown_classification_is_rejected(self):
        self.assertFalse(is_valid_classification("super_secret"))
        self.assertIsNone(profile_decision_for(None, ACTION_EXPORT))


class ExceptionCeilingTests(unittest.TestCase):
    def test_exception_can_loosen_up_to_but_not_beyond_allow(self):
        decision = evaluate_action(
            ACTION_EXPORT, baseline_decision=DECISION_DENY,
            active_exception={"id": "exc-1", "decision": DECISION_ALLOW, "rationale": "Approved for audit."},
        )
        self.assertEqual(decision.decision, DECISION_ALLOW)
        self.assertEqual(decision.controlling_layer, "exception")
        self.assertEqual(decision.exception_id, "exc-1")

    def test_exception_more_restrictive_than_current_effective_decision_is_ignored(self):
        # Effective is REQUIRE_APPROVAL (floor default for
        # ORGANIZATION_PRIVATE_LEARNING); an "exception" proposing the
        # strictly MORE restrictive DENY is not what exceptions are for
        # (exceptions only ever loosen) -- confirm it has no effect.
        decision = evaluate_action(
            ACTION_ORGANIZATION_PRIVATE_LEARNING,
            active_exception={"id": "exc-2", "decision": DECISION_DENY, "rationale": "x"},
        )
        self.assertEqual(decision.decision, DECISION_REQUIRE_APPROVAL)
        self.assertEqual(decision.controlling_layer, "floor")

    def test_exception_can_loosen_deny_to_isolate(self):
        # ISOLATE sits strictly between ALLOW and DENY on the
        # restrictiveness scale -- a legitimate partial loosening (still
        # not unconditional access) from an otherwise-DENY floor default.
        decision = evaluate_action(
            ACTION_SHARED_ARCHIOSK_CONTRIBUTION,
            active_exception={"id": "exc-3", "decision": DECISION_ISOLATE, "rationale": "x"},
        )
        self.assertEqual(decision.decision, DECISION_ISOLATE)
        self.assertEqual(decision.controlling_layer, "exception")

    def test_no_exception_means_floor_or_baseline_governs_unmodified(self):
        decision = evaluate_action(ACTION_EXPORT, baseline_decision=DECISION_DENY, active_exception=None)
        self.assertEqual(decision.decision, DECISION_DENY)
        self.assertIsNone(decision.exception_id)


class SecurityClaimsRegistryTests(unittest.TestCase):
    def test_prohibited_claims_are_all_explicitly_recorded(self):
        prohibited = {
            "data never leaves a specific country", "customer-managed encryption keys", "air-gapped operation",
            "no AI provider retention", "local AI only", "tamper-proof logs", "complete organization isolation",
            "zero-knowledge support access",
        }
        for claim in prohibited:
            self.assertEqual(SECURITY_CLAIMS_REGISTRY[claim], CLAIM_PROHIBITED_FROM_CLAIMING)

    def test_technical_telemetry_floor_default_is_allow(self):
        # Never gated -- see services.diagnostics.build_technical_telemetry's
        # own "no security evaluation call at all" design.
        self.assertEqual(MANDATORY_FLOOR_DEFAULTS[ACTION_TECHNICAL_TELEMETRY], DECISION_ALLOW)


if __name__ == "__main__":
    unittest.main()
