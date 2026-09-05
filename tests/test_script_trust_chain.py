"""
The Script trust chain, exercised as a sequence through one entry point.

Question → fit → consistency → readiness. Each stage already has its own tests;
these exist because two of the defects found while building them were
INTERACTION defects rather than faults inside any stage — a claims fingerprint
that retired a verdict on the very human adoption the gate was asking for, and a
check that only became reachable once another had recorded. Stages exercised
only in isolation do not surface that class of problem, which is the whole
argument for this file.

WHAT THE ORCHESTRATOR MAY DO

Run the stages, resolve readiness, report. It validates nothing, adopts nothing,
promotes nothing, and touches neither WorkProduct lifecycle nor Script content.
Human validation is deliberately not a stage: an orchestrator that could
validate would be an orchestrator that could promote, and GOV-P-006 puts that
boundary with a human.

No test here reaches the network.
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
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_CHECK_FAIL,
    SCRIPT_CHECK_PASS,
    SCRIPT_CHECK_REVIEW_NEEDED,
    SCRIPT_READINESS_DRAFT,
    SCRIPT_READINESS_REUSABLE,
    SCRIPT_VALIDATION_VALIDATED,
)
from services.script_fit import run_script_trust_chain
from services.security_policy import DECISION_ALLOW, DECISION_DENY

QUESTION = "What is Survival Mode, and is it another kind of Spin?"
HELP_TEXT = "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
CLAIM_SAYS = "Survival Mode is a lens, not a third kind of Spin."

_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}


def _sequenced_client(verdicts):
    """One stubbed client whose successive calls return successive verdicts -
    the fit call first, then the consistency call. Sequencing them through a
    single factory is also how the 'exactly two model calls' assertion stays
    honest: a third call would exhaust the list."""
    responses = []
    for outcome, reason in verdicts:
        block = MagicMock()
        block.type = "text"
        block.text = json.dumps(
            {"outcome": outcome, "reason": reason, "problem_unit_ids": []}
        )
        response = MagicMock()
        response.content = [block]
        responses.append(response)
    client = MagicMock()
    client.messages.create.side_effect = responses
    return MagicMock(return_value=client), client


class _ChainFixture(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_chain_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-chain")
        src = self.store.add_source(self.workspace, name="help.html", file_path="x",
                                    kind="document", actor="t")
        self.evidence_id = self.store.register_pdf_page_structure(
            self.workspace, src["id"], [HELP_TEXT], actor="t")["evidence_item_ids"][0]
        self.case = self.store.create_case(self.workspace, title="c", objective="o",
                                           created_by="t")
        self.step = self.store.record_investigation_step(
            self.workspace, case_id=self.case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": self.evidence_id},
            question=QUESTION, triggered_by_actor="t",
        )
        self.claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=self.step["id"], statement=CLAIM_SAYS,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="t",
            evidence_links=[{"object_type": "evidence_item", "object_id": self.evidence_id}],
        )

    def _script(self, text, step=None):
        script = self.store.create_work_product(
            self.workspace, artifact_type="script", title="s", created_by="t",
            case_id=self.case["id"],
            source_investigation_step_id=(step or self.step)["id"] if step is not False else None,
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": text}, content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="t",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        return script

    def _run(self, script, verdicts, policy=DECISION_ALLOW):
        factory, client = _sequenced_client(verdicts)
        with patch.dict(os.environ, _ENV), patch("anthropic.Anthropic", factory):
            result = run_script_trust_chain(
                self.store, self.workspace, work_product_id=script["id"],
                policy_decision=policy,
            )
        return result, factory, client

    def _stored(self, script):
        return self.store.get_work_product(self.workspace, script["id"])


class SequenceTests(_ChainFixture):
    def test_1_correct_script_passes_both_stages_and_still_waits_for_a_human(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        result, _, _ = self._run(script, [("pass", "answers both parts"),
                                          ("pass", "restates the claim")])

        self.assertEqual(result["question"], QUESTION)
        self.assertEqual(result["stages"]["question_fit"]["outcome"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["stages"]["evidence_consistency"]["outcome"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["blocked_by"], [])
        # Both model stages green and it is still DRAFT - the human is the gate.
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)
        self.assertEqual(result["checks"]["human_validation"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_1b_the_same_script_reaches_reusable_once_a_human_acts(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        self.store.accept_claim_as_observation(
            self.workspace, claim_id=self.claim["id"], actor="t", reason="verified")
        self.store.record_script_validation(
            self.workspace, work_product_id=script["id"],
            decision=SCRIPT_VALIDATION_VALIDATED, actor="reviewer",
        )
        readiness = self.store.resolve_script_readiness(self.workspace, script["id"])
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_2_partial_script_blocks_at_fit(self):
        script = self._script("Survival Mode is a lens you can apply when running a Spin.")
        result, _, _ = self._run(script, [("review_needed", "does not say whether it is another Spin"),
                                          ("pass", "consistent as far as it goes")])
        self.assertEqual(result["stages"]["question_fit"]["outcome"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(result["blocked_by"], ["question_fit"])
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_3_contradictory_script_passes_fit_and_blocks_at_consistency(self):
        # The case the whole chain exists for: it answers the question, and the
        # answer contradicts its own evidence.
        script = self._script("Survival Mode is the third kind of Spin available in the Toolbox.")
        result, _, _ = self._run(script, [("pass", "explicitly answers both parts"),
                                          ("fail", "contradicts the claim it cites")])
        self.assertEqual(result["stages"]["question_fit"]["outcome"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["stages"]["evidence_consistency"]["outcome"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["blocked_by"], ["evidence_consistency"])
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_both_stages_run_even_when_the_first_does_not_pass(self):
        # A reviewer wants everything wrong with a Script, not the first thing.
        script = self._script("Survival Mode is the third kind of Spin.")
        result, factory, _ = self._run(script, [("fail", "wrong question"),
                                                ("fail", "contradicts its claim")])
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(sorted(result["blocked_by"]), ["evidence_consistency", "question_fit"])


class FailureBehaviourTests(_ChainFixture):
    def test_4_policy_denied_degrades_both_stages_without_calling_out(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        result, factory, _ = self._run(script, [], policy=DECISION_DENY)
        factory.assert_not_called()
        for stage in ("question_fit", "evidence_consistency"):
            self.assertEqual(result["stages"][stage]["outcome"], SCRIPT_CHECK_REVIEW_NEEDED)
            self.assertFalse(result["stages"][stage]["ran"])
        self.assertEqual(sorted(result["could_not_run"]),
                         ["evidence_consistency", "question_fit"])
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_which_stage_could_not_run_is_never_hidden(self):
        # Fit runs and passes; consistency hits a transport error. The result
        # must distinguish "assessed and fine" from "never assessed".
        script = self._script("Survival Mode is not a third kind of Spin.")
        block = MagicMock(); block.type = "text"
        block.text = json.dumps({"outcome": "pass", "reason": "ok"})
        good = MagicMock(); good.content = [block]
        client = MagicMock()
        client.messages.create.side_effect = [good, RuntimeError("connection reset")]
        with patch.dict(os.environ, _ENV), patch("anthropic.Anthropic", MagicMock(return_value=client)):
            result = run_script_trust_chain(
                self.store, self.workspace, work_product_id=script["id"],
                policy_decision=DECISION_ALLOW,
            )
        self.assertTrue(result["stages"]["question_fit"]["ran"])
        self.assertFalse(result["stages"]["evidence_consistency"]["ran"])
        self.assertEqual(result["could_not_run"], ["evidence_consistency"])
        self.assertEqual(result["blocked_by"], ["evidence_consistency"])
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_script_with_no_originating_question_is_reported_not_guessed(self):
        script = self.store.create_work_product(
            self.workspace, artifact_type="script", title="orphan", created_by="t",
            case_id=self.case["id"],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": "Something."}, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
            author="t", evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        result, factory, _ = self._run(script, [("pass", "unused")])
        self.assertIsNone(result["question"])
        self.assertEqual(result["stages"]["question_fit"]["outcome"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertIn("does not resolve to an originating question",
                      result["stages"]["question_fit"]["reason"])

    def test_an_unknown_script_is_refused(self):
        with self.assertRaises(ValueError):
            run_script_trust_chain(
                self.store, self.workspace, work_product_id="nope",
                policy_decision=DECISION_ALLOW,
            )


class OrchestratorDecidesNothingTests(_ChainFixture):
    def test_5_exactly_two_model_calls_are_made(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        _, factory, client = self._run(script, [("pass", "a"), ("pass", "b")])
        self.assertEqual(factory.call_count, 2)
        self.assertEqual(client.messages.create.call_count, 2)

    def test_6_no_lifecycle_mutation_occurs(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        before = self._stored(script)
        self._run(script, [("pass", "a"), ("pass", "b")])
        after = self._stored(script)
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["sections"], before["sections"])
        self.assertEqual(after["version"], before["version"])

    def test_7_no_claim_adoption_occurs(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        self.assertEqual(
            self.store.get_claim(self.workspace, self.claim["id"])["adoption_state"],
            CLAIM_ADOPTION_PROPOSED,
        )

    def test_no_validation_is_ever_created_by_the_chain(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        self.assertEqual(self._stored(script).get("script_validations", []), [])

    def test_no_readiness_field_is_written(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        stored = self._stored(script)
        for forbidden in ("readiness", "script_readiness", "validated", "reusable"):
            self.assertNotIn(forbidden, stored)


class VersionBindingTests(_ChainFixture):
    def test_8_both_recorded_verdicts_bind_to_the_current_script_version(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        result, _, _ = self._run(script, [("pass", "a"), ("pass", "b")])
        stored = self._stored(script)
        checksum = result["content_checksum"]
        self.assertEqual(stored["script_fit_verdicts"][-1]["content_checksum"], checksum)
        self.assertEqual(stored["script_consistency_verdicts"][-1]["content_checksum"], checksum)
        self.assertEqual(
            stored["script_consistency_verdicts"][-1]["claims_fingerprint"],
            self.store.script_cited_claims_fingerprint(self.workspace, stored),
        )

    def test_editing_the_script_retires_everything_the_chain_recorded(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": "It also reranks findings."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="t",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        readiness = self.store.resolve_script_readiness(self.workspace, script["id"])
        self.assertEqual(readiness["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(readiness["checks"]["evidence_consistency"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_re_running_the_chain_after_an_edit_restores_both_verdicts(self):
        script = self._script("Survival Mode is not a third kind of Spin.")
        self._run(script, [("pass", "a"), ("pass", "b")])
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": "It is a checkbox on either run."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="t",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        result, _, _ = self._run(script, [("pass", "a2"), ("pass", "b2")])
        self.assertEqual(result["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["evidence_consistency"], SCRIPT_CHECK_PASS)


if __name__ == "__main__":
    unittest.main()
