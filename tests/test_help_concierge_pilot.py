"""
The Help concierge path, end to end, on the real Survival Mode question.

This is the first time the Script trust chain is reachable by a person rather
than only by a test: a real route, a real session, a real governed Script in the
reserved Help library workspace.

THE HYBRID TRIGGER MODEL

The chain runs at meaningful checkpoints — a candidate saved, submitted, or an
explicit reviewer Re-check — and never continuously while someone edits. A
material edit retires the prior verdicts by design, so an edit-triggered chain
would spend two model calls per keystroke to tell nobody anything actionable
yet. That the verdicts go stale is exactly what makes the deferred re-check
safe: a stale Script cannot quietly read as checked.

WHAT A READER IS TOLD

Four statuses, not seven checks. A Help reader is not troubleshooting a gate;
they need to know whether they can rely on what they are reading. `checks` and
`reasons` appear only for an admin, who is the only person for whom "which of
seven" is actionable. The Script's own text is released only at REUSABLE —
the state that means a human signed it off for reuse beyond the question it was
written for.

No test here reaches the network.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
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
from services.script_fit import (
    HELP_STATUS_BLOCKED_EVIDENCE,
    HELP_STATUS_CHECK_UNAVAILABLE,
    HELP_STATUS_NEEDS_REVIEW,
    HELP_STATUS_READY,
    HELP_STATUS_READY_FOR_REVIEW,
    help_status_for,
)

QUESTION = "What is Survival Mode, and is it another kind of Spin?"
HELP_TEXT = "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
CLAIM_SAYS = "Survival Mode is a lens, not a third kind of Spin."
ANSWER = "Survival Mode is a lens on either run, not a third kind of Spin."

_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}


def _sequenced_client(verdicts):
    responses = []
    for outcome, reason in verdicts:
        block = MagicMock()
        block.type = "text"
        block.text = json.dumps({"outcome": outcome, "reason": reason, "problem_unit_ids": []})
        response = MagicMock()
        response.content = [block]
        responses.append(response)
    client = MagicMock()
    client.messages.create.side_effect = responses
    return MagicMock(return_value=client)


class StatusTranslationTests(unittest.TestCase):
    """The reader-facing translation, on its own - no Flask, no store."""

    def _readiness(self, readiness, **checks):
        base = {name: SCRIPT_CHECK_PASS for name in (
            "question_fit", "evidence_fidelity", "unsupported_claims",
            "current_applicability", "semantic_fit", "evidence_consistency",
            "reuse_eligibility")}
        base.update(checks)
        return {"readiness": readiness, "checks": base}

    def test_reusable_reads_as_ready_and_releases_the_answer(self):
        result = help_status_for(self._readiness(SCRIPT_READINESS_REUSABLE))
        self.assertEqual(result["status"], HELP_STATUS_READY)
        self.assertTrue(result["answerable"])

    def test_machine_checks_clear_but_awaiting_a_human_reads_as_ready_for_review(self):
        result = help_status_for(self._readiness(
            SCRIPT_READINESS_DRAFT, reuse_eligibility=SCRIPT_CHECK_REVIEW_NEEDED))
        self.assertEqual(result["status"], HELP_STATUS_READY_FOR_REVIEW)
        self.assertFalse(result["answerable"])

    def test_an_evidence_mismatch_is_named_rather_than_folded_into_needs_review(self):
        # The one failure a reader must not read as ordinary incompleteness:
        # the text disagrees with what it cites.
        result = help_status_for(self._readiness(
            SCRIPT_READINESS_DRAFT, evidence_consistency=SCRIPT_CHECK_FAIL))
        self.assertEqual(result["status"], HELP_STATUS_BLOCKED_EVIDENCE)
        self.assertEqual(result["label"], "Blocked by evidence mismatch")

    def test_anything_else_reads_as_needs_review_without_enumerating_why(self):
        result = help_status_for(self._readiness(
            SCRIPT_READINESS_DRAFT, semantic_fit=SCRIPT_CHECK_REVIEW_NEEDED))
        self.assertEqual(result["status"], HELP_STATUS_NEEDS_REVIEW)

    def test_a_check_that_could_not_run_outranks_every_other_status(self):
        # "We could not look" is not "we looked and it is not ready". Even a
        # would-be READY collapses to unavailable, because an outage must never
        # read as a verdict.
        result = help_status_for(
            self._readiness(SCRIPT_READINESS_REUSABLE), could_not_run=["question_fit"])
        self.assertEqual(result["status"], HELP_STATUS_CHECK_UNAVAILABLE)
        self.assertFalse(result["answerable"])

    def test_an_evidence_mismatch_outranks_readiness(self):
        result = help_status_for(self._readiness(
            SCRIPT_READINESS_REUSABLE, evidence_consistency=SCRIPT_CHECK_FAIL))
        self.assertEqual(result["status"], HELP_STATUS_BLOCKED_EVIDENCE)


class HelpConciergeRouteTests(unittest.TestCase):
    """The real route, real session, real governed Script."""

    def setUp(self):
        import app as app_module
        from models import User, db
        from routes.help_center import HELP_LIBRARY_PROJECT_ID

        self.project_id = HELP_LIBRARY_PROJECT_ID
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_help_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            for username, role in (("help_admin", "admin"), ("help_reader", "user")):
                db.session.add(User(username=username,
                                    password_hash=generate_password_hash("x"), role=role))
            db.session.commit()

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        src = self.store.add_source(self.workspace, name="spin_and_survival_modes.html",
                                    file_path="x", kind="document", actor="seed")
        ev = self.store.register_pdf_page_structure(
            self.workspace, src["id"], [HELP_TEXT], actor="seed")["evidence_item_ids"][0]
        case = self.store.create_case(self.workspace, title="Survival Mode",
                                      objective="help", created_by="seed")
        self.step = self.store.record_investigation_step(
            self.workspace, case_id=case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": ev},
            question=QUESTION, triggered_by_actor="seed",
        )
        self.claim = self.store.record_investigation_claim(
            self.workspace, investigation_step_id=self.step["id"], statement=CLAIM_SAYS,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="seed",
            evidence_links=[{"object_type": "evidence_item", "object_id": ev}],
        )
        self.script = self._script(ANSWER)

    def _script(self, text):
        script = self.store.create_work_product(
            self.workspace, artifact_type="script", title="Survival Mode",
            created_by="seed", source_investigation_step_id=self.step["id"],
        )
        self.store.add_work_product_section(
            self.workspace, work_product_id=script["id"], section_type="scene",
            content={"text": text}, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
            author="seed",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}],
        )
        return script

    def _reload(self):
        """Re-read the workspace after a route has written to it.

        The route builds its own store and workspace per request, so this
        test's in-memory copy goes stale the moment a recheck records a
        verdict - and the store's optimistic-concurrency guard correctly
        refuses a write against a stale version. Reloading is what a second
        writer is supposed to do; the guard caught the test, not the code.
        """
        self.workspace = self.store.get_or_create(self.project_id)
        return self.workspace

    def _client(self, username="help_admin"):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": username, "password": "x"},
                    follow_redirects=True)
        return client

    # -- the pilot flow ---------------------------------------------------

    def test_the_full_survival_mode_flow_end_to_end(self):
        client = self._client()

        # Checkpoint 1: the reviewer runs the chain. Both stages pass.
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client(
                    [("pass", "answers both parts"), ("pass", "restates the claim")])):
            recheck = client.post("/help/scripts/%s/recheck" % self.script["id"])
        self.assertEqual(recheck.status_code, 200)
        body = recheck.get_json()
        self.assertEqual(body["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(body["checks"]["evidence_consistency"], SCRIPT_CHECK_PASS)
        # Machine checks clear; a human has not acted, so it is NOT answerable.
        self.assertEqual(body["label"], "Ready for review")
        self.assertEqual(body["readiness"], SCRIPT_READINESS_DRAFT)

        status = client.get("/help/scripts/%s/status" % self.script["id"]).get_json()
        self.assertEqual(status["status"], HELP_STATUS_READY_FOR_REVIEW)
        self.assertNotIn("answer", status)

        # The two human acts. Neither is performed by the chain.
        self._reload()
        self.store.accept_claim_as_observation(
            self.workspace, claim_id=self.claim["id"], actor="reviewer", reason="verified")
        self.store.record_script_validation(
            self.workspace, work_product_id=self.script["id"],
            decision=SCRIPT_VALIDATION_VALIDATED, actor="reviewer")

        status = client.get("/help/scripts/%s/status" % self.script["id"]).get_json()
        self.assertEqual(status["status"], HELP_STATUS_READY)
        self.assertEqual(status["question"], QUESTION)
        self.assertIn("not a third kind of Spin", status["answer"])

    def test_a_contradictory_script_is_blocked_by_evidence_mismatch(self):
        script = self._script("Survival Mode is the third kind of Spin in the Toolbox.")
        client = self._client()
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client(
                    [("pass", "explicitly answers both parts"),
                     ("fail", "contradicts the claim it cites")])):
            body = client.post("/help/scripts/%s/recheck" % script["id"]).get_json()
        self.assertEqual(body["label"], "Blocked by evidence mismatch")
        self.assertEqual(body["blocked_by"], ["evidence_consistency"])
        self.assertEqual(body["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_policy_refusal_reads_as_check_could_not_run(self):
        client = self._client()
        with patch("routes.help_center._external_ai_decision", return_value="deny"), \
                patch("anthropic.Anthropic") as anthropic_client:
            body = client.post("/help/scripts/%s/recheck" % self.script["id"]).get_json()
        anthropic_client.assert_not_called()
        self.assertEqual(body["label"], "Check could not run")
        self.assertEqual(sorted(body["could_not_run"]),
                         ["evidence_consistency", "question_fit"])

    # -- what the machinery must not do -----------------------------------

    def test_a_material_edit_makes_a_ready_script_need_review_again(self):
        # The stale-verdict rule is what makes deferring the re-check safe.
        client = self._client()
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % self.script["id"])
        self._reload()
        self.store.accept_claim_as_observation(
            self.workspace, claim_id=self.claim["id"], actor="r", reason="v")
        self.store.record_script_validation(
            self.workspace, work_product_id=self.script["id"],
            decision=SCRIPT_VALIDATION_VALIDATED, actor="r")
        self.assertEqual(
            client.get("/help/scripts/%s/status" % self.script["id"]).get_json()["status"],
            HELP_STATUS_READY)

        self._reload()
        self.store.add_work_product_section(
            self.workspace, work_product_id=self.script["id"], section_type="scene",
            content={"text": "It also reranks findings."},
            content_class=CONTENT_CLASS_HUMAN_AUTHORED, author="editor",
            evidence_links=[{"object_type": "claim", "object_id": self.claim["id"]}])

        after = client.get("/help/scripts/%s/status" % self.script["id"]).get_json()
        self.assertEqual(after["status"], HELP_STATUS_NEEDS_REVIEW)
        self.assertNotIn("answer", after)

    def test_the_recheck_never_validates_adopts_or_promotes(self):
        client = self._client()
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % self.script["id"])
        self._reload()
        stored = self.store.get_work_product(self.workspace, self.script["id"])
        self.assertEqual(stored.get("script_validations", []), [])
        self.assertEqual(
            self.store.get_claim(self.workspace, self.claim["id"])["adoption_state"], "proposed")
        self.assertEqual(
            self.store.resolve_script_readiness(
                self.workspace, self.script["id"])["readiness"], SCRIPT_READINESS_DRAFT)

    def test_a_non_admin_cannot_spend_model_calls_or_see_gate_detail(self):
        reader = self._client("help_reader")
        with patch("anthropic.Anthropic") as anthropic_client:
            self.assertEqual(
                reader.post("/help/scripts/%s/recheck" % self.script["id"]).status_code, 403)
        anthropic_client.assert_not_called()

        body = reader.get("/help/scripts/%s/status" % self.script["id"]).get_json()
        self.assertIn("label", body)
        self.assertNotIn("checks", body)
        self.assertNotIn("reasons", body)

    def test_status_requires_authentication(self):
        anonymous = self.flask_app.test_client()
        response = anonymous.get("/help/scripts/%s/status" % self.script["id"])
        self.assertIn(response.status_code, (302, 401, 403))

    def test_a_non_script_work_product_is_not_reachable_through_help(self):
        report = self.store.create_work_product(
            self.workspace, artifact_type="report", title="not a script", created_by="seed")
        client = self._client()
        self.assertEqual(
            client.get("/help/scripts/%s/status" % report["id"]).status_code, 404)


if __name__ == "__main__":
    unittest.main()
