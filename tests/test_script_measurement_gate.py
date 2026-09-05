"""
The Script measurement gate — DRAFT → VALIDATED → REUSABLE.

Nothing here promotes a Script. `resolve_script_readiness` measures and
reports; readiness is DERIVED from the five checks on every call and is not a
field anywhere, which is what makes "a DRAFT must never become REUSABLE without
passing the gate" structurally true rather than a rule someone has to remember.
There is no field to set, so there is no way to set it — the same read-time
discipline `resolve_claim_status` and `resolve_relationship_status` already use.

WHAT SEPARATES VALIDATED FROM REUSABLE

The four content checks (question fit, evidence fidelity, unsupported claims,
current applicability) ask whether a Script is sound *for the question it was
made for*. Reuse asks a harder question, and it is the one that needs a human:
every substantive claim must actually have been adopted, not merely proposed.
A Script rests happily on proposals while it answers its own question; the
moment it is handed to someone asking a different one, an unadopted proposal
has quietly become a fact. That is the whole distinction, and it is why
reuse_eligibility returns `review_needed` rather than `fail` — nothing is
wrong, something is merely unfinished.

THE PILOT

"What is Survival Mode, and is it another kind of Spin?" — grounded only in
current ARCHIOSK Help, not invented for the test.
`templates/help/spin_and_survival_modes.html` says, of Survival Mode: "A lens,
not a third kind of Spin. It is a checkbox on either" run. The workspace
Toolbox says the same thing in its own words. So the correct answer is
knowable, checkable, and already written down — which is the only honest basis
for a fixture that claims to measure whether a Script answers a question.

WHAT THIS DOES NOT DO

No renderer, no playback, no video, no voice, no Question Taxonomy, no Clip
library. Measurement only, and no repair: a Script that fails a check stays
exactly as it is and is reported, never quietly corrected.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CLAIM_CLASS_SUPPORTED_INTERPRETATION,
    CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE,
    CONFIDENCE_STATE_PARTIAL_SUPPORT,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_HUMAN_AUTHORED,
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_CHECK_FAIL,
    SCRIPT_CHECK_PASS,
    SCRIPT_CHECK_REVIEW_NEEDED,
    SCRIPT_READINESS_DRAFT,
    SCRIPT_READINESS_REUSABLE,
    SCRIPT_READINESS_VALIDATED,
    SCRIPT_VALIDATION_REJECTED,
    SCRIPT_VALIDATION_VALIDATED,
)

QUESTION = "What is Survival Mode, and is it another kind of Spin?"

# Verbatim from templates/help/spin_and_survival_modes.html - the Script is
# grounded in current Help, not in anything invented here.
HELP_TEXT = (
    "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
)


class _GateFixture(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_gate_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create("test-project-gate")

        self.source = self.store.add_source(
            self.workspace, name="spin_and_survival_modes.html",
            file_path="unused-help", kind="document", actor="tester",
        )
        registration = self.store.register_pdf_page_structure(
            self.workspace, self.source["id"], [HELP_TEXT], actor="tester",
        )
        self.evidence_id = registration["evidence_item_ids"][0]

        self.case = self.store.create_case(
            self.workspace, title="Survival Mode help",
            objective="answer one help question", created_by="tester",
        )
        self.step = self.store.record_investigation_step(
            self.workspace, case_id=self.case["id"],
            step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": self.evidence_id},
            question=QUESTION, triggered_by_actor="tester",
        )

    def _claim(self, statement, claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
               confidence=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT, evidence=True, step=None):
        return self.store.record_investigation_claim(
            self.workspace, investigation_step_id=(step or self.step)["id"],
            statement=statement, claim_class=claim_class,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL, confidence_state=confidence,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="tester",
            evidence_links=([{"object_type": "evidence_item", "object_id": self.evidence_id}]
                            if evidence else None),
        )

    def _script(self, title="What Survival Mode is", step=None):
        return self.store.create_work_product(
            self.workspace, artifact_type="script", title=title, created_by="tester",
            case_id=self.case["id"],
            source_investigation_step_id=(step or self.step)["id"],
        )

    def _scene(self, script, text, claim=None, content_class=CONTENT_CLASS_HUMAN_AUTHORED):
        return self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": text}, content_class=content_class, author="tester",
            evidence_links=([{"object_type": "claim", "object_id": claim["id"]}] if claim else None),
        )

    def _adopt(self, claim):
        return self.store.accept_claim_as_observation(
            self.workspace, claim_id=claim["id"], actor="tester", reason="verified against Help",
        )

    def _fit(self, script, outcome=SCRIPT_CHECK_PASS, reason="assessed"):
        return self.store.record_script_fit_verdict(
            self.workspace, work_product_id=script["id"], outcome=outcome,
            reason=reason, question=QUESTION,
        )

    def _validate(self, script, decision=SCRIPT_VALIDATION_VALIDATED, comments=None):
        return self.store.record_script_validation(
            self.workspace, work_product_id=script["id"], decision=decision,
            actor="reviewer", comments=comments,
        )

    def _cleared(self, script):
        """A Script taken through the full gate: assessed and validated."""
        self._fit(script)
        self._validate(script)
        return script

    def _readiness(self, script):
        return self.store.resolve_script_readiness(self.workspace, script["id"])


class CorrectScriptPassesTests(_GateFixture):
    """The pilot, answered correctly and grounded in current Help."""

    def test_a_sound_unadopted_but_assessed_and_validated_script_is_validated(self):
        # SUPERSEDED EXPECTATION, recorded rather than quietly rewritten: this
        # test used to reach VALIDATED on the four structural checks alone.
        # The lifecycle now requires a semantic fit verdict AND a human
        # validation before VALIDATED, so structural soundness is necessary and
        # no longer sufficient. The old assertion was not wrong; the gate moved.
        claim = self._claim("Survival Mode is a lens on either Spin run, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens on either run, not a third kind of Spin.", claim)
        self._cleared(script)

        result = self._readiness(script)
        self.assertEqual(result["question"], QUESTION)
        self.assertEqual(result["checks"]["question_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["evidence_fidelity"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["unsupported_claims"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["current_applicability"], SCRIPT_CHECK_PASS)
        # Sound for its own question; not yet signed off for anyone else's.
        self.assertEqual(result["checks"]["reuse_eligibility"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_VALIDATED)

    def test_the_same_script_becomes_reusable_once_a_human_adopts_the_claim(self):
        claim = self._claim("Survival Mode is a lens on either Spin run, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens on either run, not a third kind of Spin.", claim)
        self._cleared(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_VALIDATED)

        self._adopt(claim)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["reuse_eligibility"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_a_marked_inference_is_allowed_alongside_a_sourced_assertion(self):
        sourced = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        inferred = self._claim(
            "It is therefore most useful when comparing two runs.",
            claim_class=CLAIM_CLASS_SUPPORTED_INTERPRETATION,
            confidence=CONFIDENCE_STATE_PARTIAL_SUPPORT,
        )
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", sourced)
        # Marked as AI-proposed, which is what makes it honest rather than laundered.
        self._scene(script, "It is therefore most useful when comparing runs.", inferred,
                    content_class=CONTENT_CLASS_AI_PROPOSED)
        self._adopt(sourced)
        self._adopt(inferred)
        self._cleared(script)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["evidence_fidelity"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_REUSABLE)


class GateBlocksTests(_GateFixture):
    """Each failure mode the gate exists to catch, one per test."""

    def test_an_unsupported_assertion_fails_and_blocks_promotion(self):
        claim = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", claim)
        self._scene(script, "It also doubles the analysis budget.")  # no citation at all

        result = self._readiness(script)
        self.assertEqual(result["checks"]["unsupported_claims"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)
        self.assertTrue(any("no cited basis" in r for r in result["reasons"]))

    def test_a_claim_resting_on_insufficient_evidence_fails(self):
        weak = self._claim("Survival Mode changes the delta classifications.",
                           confidence=CONFIDENCE_STATE_INSUFFICIENT_EVIDENCE)
        script = self._script()
        self._scene(script, "Survival Mode changes the delta classifications.", weak)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["unsupported_claims"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_stale_source_blocks_reuse(self):
        claim = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", claim)
        self._adopt(claim)
        self._cleared(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_REUSABLE)

        # The Help page is revised. register_source_revision is the real
        # mechanism - it sets Source.superseded_by_source_id, which is the
        # pointer resolve_region_citation actually reads. Generalised beyond
        # drawings by CLAUDE-POSTCAMEL-COMM-I4A, so a help document can be
        # formally revised at all.
        self.store.register_source_revision(
            self.workspace, old_source_id=self.source["id"],
            name="spin_and_survival_modes.html", file_path="unused-help-v2",
            actor="tester", reason="Help guide revised",
        )

        result = self._readiness(script)
        self.assertEqual(result["checks"]["current_applicability"], SCRIPT_CHECK_FAIL)
        self.assertNotEqual(result["readiness"], SCRIPT_READINESS_REUSABLE)
        self.assertTrue(any("stale" in r for r in result["reasons"]))

    def test_an_ungrounded_inference_presented_as_fact_fails(self):
        # The laundering case: an interpretation dressed as human-authored fact.
        inferred = self._claim(
            "Survival Mode was added because Delta Spin was too slow.",
            claim_class=CLAIM_CLASS_SUPPORTED_INTERPRETATION,
            confidence=CONFIDENCE_STATE_PARTIAL_SUPPORT,
        )
        script = self._script()
        self._scene(script, "Survival Mode exists because Delta Spin was too slow.", inferred,
                    content_class=CONTENT_CLASS_HUMAN_AUTHORED)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["evidence_fidelity"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)
        self.assertTrue(any("as authored fact rather than inference" in r for r in result["reasons"]))

    def test_a_script_answering_a_different_question_fails_question_fit(self):
        other_step = self.store.record_investigation_step(
            self.workspace, case_id=self.case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": self.evidence_id},
            question="What file types can I upload?", triggered_by_actor="tester",
        )
        foreign_claim = self._claim("PDF and XLSX are accepted.", step=other_step)
        script = self._script()  # anchored to the Survival Mode question
        self._scene(script, "PDF and XLSX are accepted.", foreign_claim)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["question_fit"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_an_empty_script_is_never_validated(self):
        result = self._readiness(self._script())
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)
        self.assertEqual(result["checks"]["question_fit"], SCRIPT_CHECK_FAIL)


class ModelCannotPromoteTests(_GateFixture):
    """The governing rule: a stored fit verdict may block or require review,
    and may never validate, adopt or make anything reusable."""

    def _sound_script(self):
        claim = self._claim("Survival Mode is a lens on either Spin run, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens on either run, not a third kind of Spin.", claim)
        return script, claim

    def test_a_pass_alone_does_not_produce_validated(self):
        script, _ = self._sound_script()
        self._fit(script, SCRIPT_CHECK_PASS)
        result = self._readiness(script)
        self.assertEqual(result["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["human_validation"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_human_validation_without_a_verdict_does_not_produce_validated(self):
        script, _ = self._sound_script()
        self._validate(script)
        result = self._readiness(script)
        self.assertEqual(result["checks"]["human_validation"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_fail_verdict_blocks_even_with_human_validation(self):
        script, _ = self._sound_script()
        self._fit(script, SCRIPT_CHECK_FAIL, reason="answers a different question")
        self._validate(script)
        result = self._readiness(script)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)
        self.assertTrue(any("different question" in r for r in result["reasons"]))

    def test_a_review_needed_verdict_blocks_even_with_human_validation(self):
        script, _ = self._sound_script()
        self._fit(script, SCRIPT_CHECK_REVIEW_NEEDED, reason="incomplete")
        self._validate(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_DRAFT)

    def test_pass_plus_human_validation_produces_validated(self):
        script, _ = self._sound_script()
        self._fit(script, SCRIPT_CHECK_PASS)
        self._validate(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_VALIDATED)

    def test_no_verdict_at_all_still_requires_review(self):
        # "Nobody has looked" is not "it is fine".
        script, _ = self._sound_script()
        self._validate(script)
        self.assertEqual(self._readiness(script)["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_a_human_rejection_blocks_outright(self):
        script, claim = self._sound_script()
        self._fit(script, SCRIPT_CHECK_PASS)
        self._adopt(claim)
        self._validate(script, SCRIPT_VALIDATION_REJECTED, comments="tone is wrong for Help")
        result = self._readiness(script)
        self.assertEqual(result["checks"]["human_validation"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_validated_does_not_imply_reusable(self):
        script, _ = self._sound_script()
        self._cleared(script)
        result = self._readiness(script)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_VALIDATED)
        self.assertEqual(result["checks"]["reuse_eligibility"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_reusable_additionally_requires_adopted_claims(self):
        script, claim = self._sound_script()
        self._cleared(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_VALIDATED)
        self._adopt(claim)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_REUSABLE)


class VersionSafetyTests(_GateFixture):
    """A decision describes the text it was made about. Edit the text and the
    decision stops applying - it is not deleted, expired or rewritten."""

    def _validated_script(self):
        claim = self._claim("Survival Mode is a lens on either Spin run, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens on either run, not a third kind of Spin.", claim)
        self._adopt(claim)
        self._cleared(script)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_REUSABLE)
        return script, claim

    def test_editing_the_script_invalidates_the_prior_fit_verdict(self):
        script, claim = self._validated_script()
        self._scene(script, "It also changes how findings are ranked.", claim)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertNotEqual(result["readiness"], SCRIPT_READINESS_REUSABLE)
        self.assertTrue(any("as it now stands" in r for r in result["reasons"]))

    def test_editing_the_script_invalidates_the_prior_human_validation(self):
        script, claim = self._validated_script()
        self._scene(script, "It also changes how findings are ranked.", claim)

        result = self._readiness(script)
        self.assertEqual(result["checks"]["human_validation"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_the_superseded_decisions_are_kept_not_deleted(self):
        script, claim = self._validated_script()
        self._scene(script, "It also changes how findings are ranked.", claim)
        stored = self.store.get_work_product(self.workspace, script["id"])
        self.assertEqual(len(stored["script_validations"]), 1)
        self.assertEqual(len(stored["script_fit_verdicts"]), 1)

    def test_re_assessing_and_re_validating_the_edited_script_restores_it(self):
        script, claim = self._validated_script()
        self._scene(script, "It also changes how findings are ranked.", claim)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_DRAFT)

        self._cleared(script)  # assessed and validated again, against the new text
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_the_checksum_reported_is_the_governed_content_checksum(self):
        script, _ = self._validated_script()
        reported = self._readiness(script)["content_checksum"]
        stored = self.store.get_work_product(self.workspace, script["id"])
        self.assertEqual(reported, stored["script_validations"][-1]["content_checksum"])


class RecordValidationTests(_GateFixture):
    def test_an_unrecognised_decision_is_refused(self):
        script = self._script()
        with self.assertRaises(Exception):
            self._validate(script, "looks-fine")

    def test_a_validation_must_name_who_made_it(self):
        script = self._script()
        with self.assertRaises(Exception):
            self.store.record_script_validation(
                self.workspace, work_product_id=script["id"],
                decision=SCRIPT_VALIDATION_VALIDATED, actor="   ",
            )

    def test_an_unrecognised_fit_outcome_is_refused(self):
        script = self._script()
        with self.assertRaises(Exception):
            self.store.record_script_fit_verdict(
                self.workspace, work_product_id=script["id"],
                outcome="excellent", reason="r",
            )

    def test_recording_a_verdict_never_changes_work_product_state(self):
        script = self._script()
        before = self.store.get_work_product(self.workspace, script["id"])["state"]
        self._fit(script, SCRIPT_CHECK_PASS)
        self._validate(script)
        after = self.store.get_work_product(self.workspace, script["id"])["state"]
        self.assertEqual(before, after)


class LifecycleIntegrityTests(_GateFixture):
    """DRAFT cannot skip the gate, and measuring never repairs."""

    def test_draft_cannot_reach_reusable_without_passing_every_check(self):
        claim = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", claim)
        self._scene(script, "And it silently rewrites the baseline.")  # unsupported
        self._adopt(claim)
        self._cleared(script)

        result = self._readiness(script)
        # Reuse eligibility alone is satisfied - and it still is not enough.
        self.assertEqual(result["checks"]["reuse_eligibility"], SCRIPT_CHECK_PASS)
        self.assertEqual(result["checks"]["unsupported_claims"], SCRIPT_CHECK_FAIL)
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)

    def test_readiness_is_derived_and_not_a_stored_field_anyone_can_set(self):
        claim = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", claim)
        self._cleared(script)
        stored = self.store.get_work_product(self.workspace, script["id"])
        for forbidden in ("readiness", "script_readiness", "reusable", "validated"):
            self.assertNotIn(forbidden, stored)
        self.assertEqual(self._readiness(script)["readiness"], SCRIPT_READINESS_VALIDATED)

    def test_measuring_never_repairs_the_script(self):
        claim = self._claim("Survival Mode is a lens, not a third kind of Spin.")
        script = self._script()
        self._scene(script, "Survival Mode is a lens, not a third kind of Spin.", claim)
        self._scene(script, "Unsupported.")
        before = self.store.get_work_product(self.workspace, script["id"])

        self._readiness(script)
        self._readiness(script)

        self.assertEqual(self.store.get_work_product(self.workspace, script["id"]), before)

    def test_an_unknown_script_reports_draft_rather_than_raising(self):
        result = self.store.resolve_script_readiness(self.workspace, "no-such-work-product")
        self.assertFalse(result["resolved"])
        self.assertEqual(result["readiness"], SCRIPT_READINESS_DRAFT)


if __name__ == "__main__":
    unittest.main()
