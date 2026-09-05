"""
The policy-gated seam: assess question fit, record the verdict, cause nothing else.

`services/script_fit.py` is the only place that knows about both
`assess_question_fit` (which is handed no store and so can reach nothing) and
`record_script_fit_verdict` (which stores a verdict). These tests pin what that
join may and may not do.

GOV-P-006 is the governing rule: a model assessment may constrain a governed
transition and may never authorize one. The tests below check both halves -
that a FAIL and a REVIEW_NEEDED block, and that a PASS causes nothing on its
own - plus the two corollaries: an absent assessment is not a pass, and an
assessment that could not run is not a verdict.

POLICY REFUSAL IS NOT A VERDICT

When `ACTION_EXTERNAL_AI_REQUEST` does not permit the call, the model is not
called at all and the outcome is REVIEW_NEEDED. REQUIRE_APPROVAL is deliberately
NOT treated as permission here, matching `routes/workspace.py`'s own reading of
the same gate - an approval that has not been given yet is not an approval.

No test here reaches the network: the environment is pinned and
`anthropic.Anthropic` is patched, and the policy-denied tests assert the client
was never constructed at all.
"""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_ADOPTION_PROPOSED,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_HUMAN_AUTHORED,
    CONTENT_CLASS_TEMPLATE_CONTENT,
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_CHECK_FAIL,
    SCRIPT_CHECK_PASS,
    SCRIPT_CHECK_REVIEW_NEEDED,
    SCRIPT_READINESS_DRAFT,
    SCRIPT_READINESS_REUSABLE,
    SCRIPT_READINESS_VALIDATED,
    SCRIPT_VALIDATION_VALIDATED,
)
from services.script_fit import assess_and_record_question_fit, script_narrative_text
from services.security_policy import (
    DECISION_ALLOW,
    DECISION_DENY,
    DECISION_REQUIRE_APPROVAL,
)

QUESTION = "What is Survival Mode, and is it another kind of Spin?"
HELP_TEXT = "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
SCENE_TEXT = "Survival Mode is a lens on either run, not a third kind of Spin."

_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}


def _model_returning(outcome: str, reason: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps({"outcome": outcome, "reason": reason})
    response = MagicMock()
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return MagicMock(return_value=client)


class _WiringFixture(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_fitwire_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-fitwire")

        source = self.store.add_source(
            self.workspace, name="spin_and_survival_modes.html",
            file_path="unused-help", kind="document", actor="tester",
        )
        registration = self.store.register_pdf_page_structure(
            self.workspace, source["id"], [HELP_TEXT], actor="tester",
        )
        self.evidence_id = registration["evidence_item_ids"][0]
        self.case = self.store.create_case(
            self.workspace, title="Survival Mode help", objective="one question",
            created_by="tester",
        )
        self.step = self.store.record_investigation_step(
            self.workspace, case_id=self.case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": self.evidence_id},
            question=QUESTION, triggered_by_actor="tester",
        )
        self.claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=self.step["id"],
            statement=SCENE_TEXT, claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="tester",
            evidence_links=[{"object_type": "evidence_item", "object_id": self.evidence_id}],
        )
        self.script = self.store.create_work_product(
            self.workspace, artifact_type="script", title="What Survival Mode is",
            created_by="tester", case_id=self.case["id"],
            source_investigation_step_id=self.step["id"],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=self.script["id"], section_type="scene",
            content={"text": SCENE_TEXT}, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
            author="tester",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )

    def _run(self, policy=DECISION_ALLOW, outcome="pass", reason="assessed", **kwargs):
        factory = _model_returning(outcome, reason)
        with patch.dict(os.environ, _ENV), patch("anthropic.Anthropic", factory):
            record = assess_and_record_question_fit(
                self.store, self.workspace, work_product_id=self.script["id"],
                question=QUESTION, policy_decision=policy, **kwargs,
            )
        return record, factory

    def _readiness(self):
        return self.store.resolve_script_readiness(self.workspace, self.script["id"])

    def _stored(self):
        return self.store.get_work_product(self.workspace, self.script["id"])


class PolicyGateTests(_WiringFixture):
    def test_policy_allowed_lets_the_assessment_run(self):
        record, factory = self._run(policy=DECISION_ALLOW, outcome="pass")
        factory.assert_called_once()
        self.assertEqual(record["outcome"], SCRIPT_CHECK_PASS)
        self.assertTrue(record["ran"])

    def test_policy_denied_never_constructs_a_model_client(self):
        record, factory = self._run(policy=DECISION_DENY)
        factory.assert_not_called()
        self.assertEqual(record["outcome"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertFalse(record["ran"])
        self.assertIn("not permitted", record["reason"])

    def test_require_approval_is_not_permission(self):
        # An approval that has not been given yet is not an approval - the same
        # reading routes/workspace.py's own _external_ai_status applies.
        record, factory = self._run(policy=DECISION_REQUIRE_APPROVAL)
        factory.assert_not_called()
        self.assertEqual(record["outcome"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_a_policy_refusal_is_never_a_pass_or_a_fail(self):
        for policy in (DECISION_DENY, DECISION_REQUIRE_APPROVAL, "something-unknown"):
            record, _ = self._run(policy=policy)
            self.assertNotEqual(record["outcome"], SCRIPT_CHECK_PASS, policy)
            self.assertNotEqual(record["outcome"], SCRIPT_CHECK_FAIL, policy)


class VerdictRecordingTests(_WiringFixture):
    def test_a_pass_is_recorded_but_does_not_validate(self):
        record, _ = self._run(outcome="pass")
        self.assertEqual(record["outcome"], SCRIPT_CHECK_PASS)
        readiness = self._readiness()
        self.assertEqual(readiness["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(readiness["checks"]["human_validation"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_review_needed_verdict_is_recorded_and_blocks(self):
        self._run(outcome="review_needed", reason="incomplete")
        readiness = self._readiness()
        self.assertEqual(readiness["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_fail_verdict_is_recorded_and_blocks(self):
        self._run(outcome="fail", reason="answers a different question")
        readiness = self._readiness()
        self.assertEqual(readiness["checks"]["semantic_fit"], SCRIPT_CHECK_FAIL)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_DRAFT)

    def test_the_recorded_verdict_binds_to_the_current_script_checksum(self):
        record, _ = self._run(outcome="pass")
        self.assertEqual(record["content_checksum"], self._readiness()["content_checksum"])
        self.assertEqual(record["question"], QUESTION)

    def test_editing_the_script_makes_the_recorded_verdict_inapplicable(self):
        self._run(outcome="pass")
        self.assertEqual(self._readiness()["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)

        self.store.add_work_product_section(
            self.workspace, work_product_id=self.script["id"], section_type="scene",
            content={"text": "It also reranks findings."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="tester",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        self.assertEqual(self._readiness()["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_record_false_assesses_without_storing(self):
        factory = _model_returning("pass", "assessed")
        with patch.dict(os.environ, _ENV), patch("anthropic.Anthropic", factory):
            record = assess_and_record_question_fit(
                self.store, self.workspace, work_product_id=self.script["id"],
                question=QUESTION, policy_decision=DECISION_ALLOW, record=False,
            )
        self.assertFalse(record["stored"])
        self.assertIsNone(record["content_checksum"])
        self.assertEqual(self._stored().get("script_fit_verdicts", []), [])


class CausesNothingElseTests(_WiringFixture):
    """GOV-P-006: the assessment may constrain, and may authorize nothing."""

    def test_no_work_product_lifecycle_mutation_occurs(self):
        before = self._stored()["state"]
        self._run(outcome="pass")
        self.assertEqual(self._stored()["state"], before)

    def test_no_claim_adoption_occurs(self):
        self._run(outcome="pass")
        claim = self.store.get_claim(self.workspace, self.claim["id"])
        self.assertEqual(claim["adoption_state"], CLAIM_ADOPTION_PROPOSED)

    def test_no_readiness_field_is_written(self):
        self._run(outcome="pass")
        stored = self._stored()
        for forbidden in ("readiness", "script_readiness", "validated", "reusable"):
            self.assertNotIn(forbidden, stored)

    def test_no_script_validation_is_created(self):
        self._run(outcome="pass")
        self.assertEqual(self._stored().get("script_validations", []), [])

    def test_the_script_sections_are_untouched(self):
        before = self._stored()["sections"]
        self._run(outcome="pass")
        self.assertEqual(self._stored()["sections"], before)

    def test_even_a_pass_plus_adoption_still_needs_a_human_to_validate(self):
        self._run(outcome="pass")
        self.store.accept_claim_as_observation(
            self.workspace, claim_id=self.claim["id"], actor="tester", reason="verified",
        )
        self.assertEqual(self._readiness()["readiness"], SCRIPT_READINESS_DRAFT)

        self.store.record_script_validation(
            self.workspace, work_product_id=self.script["id"],
            decision=SCRIPT_VALIDATION_VALIDATED, actor="reviewer",
        )
        self.assertEqual(self._readiness()["readiness"], SCRIPT_READINESS_REUSABLE)


class NarrativeTextTests(_WiringFixture):
    def test_only_active_scenes_are_submitted_in_order(self):
        # The direction deliberately carries a `text` key. An earlier version of
        # this test used a direction with no text at all, which passed for the
        # wrong reason - the empty-string filter removed it, so the section_type
        # filter was never actually exercised. Mutation testing caught that.
        self.store.add_work_product_section(
            self.workspace, work_product_id=self.script["id"], section_type="direction",
            content={"text": "DIRECTION hold on the toolbox", "seconds": 3},
            content_class=CONTENT_CLASS_TEMPLATE_CONTENT, author="tester",
        )
        text = script_narrative_text(self._stored())
        self.assertIn(SCENE_TEXT, text)
        self.assertNotIn("DIRECTION", text)

    def test_a_removed_scene_is_not_submitted(self):
        # add_work_product_section returns the WORK PRODUCT, not the section -
        # the new section is the last one appended.
        updated = self.store.add_work_product_section(
            self.workspace, work_product_id=self.script["id"], section_type="scene",
            content={"text": "RETRACTED this line was withdrawn."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="tester",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        self.store.remove_work_product_section(
            self.workspace, work_product_id=self.script["id"],
            section_id=updated["sections"][-1]["id"], actor="tester",
        )
        self.assertNotIn("RETRACTED", script_narrative_text(self._stored()))

    def test_the_text_assessed_is_the_text_stored(self):
        captured = {}

        def _capture(question, script_text, evidence_context=None, **kwargs):
            captured["script_text"] = script_text
            from services.cross_modal_investigation import QuestionFitResult

            return QuestionFitResult(outcome=SCRIPT_CHECK_PASS, reason="ok", ran=True)

        with patch("services.script_fit.assess_question_fit", _capture):
            assess_and_record_question_fit(
                self.store, self.workspace, work_product_id=self.script["id"],
                question=QUESTION, policy_decision=DECISION_ALLOW,
            )
        self.assertEqual(captured["script_text"], script_narrative_text(self._stored()))

    def test_an_unknown_work_product_is_refused(self):
        with self.assertRaises(ValueError):
            assess_and_record_question_fit(
                self.store, self.workspace, work_product_id="no-such",
                question=QUESTION, policy_decision=DECISION_ALLOW,
            )


if __name__ == "__main__":
    unittest.main()
