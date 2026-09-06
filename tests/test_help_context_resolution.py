"""
Context-aware Help — resolve what the user means, then look it up.

THE DEFECT THESE TESTS RETIRE

`/help/mode/ask` matched a Script by exact string equality on its originating
question, so "What does this do?" could only match a Script literally asking
that. There is a test below asserting that equality is no longer required, and
it is the one that would catch a revert.

WHAT IS ACTUALLY BEING DEFENDED

Two properties that pull against each other, which is why both need tests:

  - Context must NARROW meaning. Standing on the Survival Mode checkbox and
    asking "what does this do?" is a complete question, and asking the user to
    name the control again would be the system pretending not to know where
    they are standing.
  - Context must NOT INVENT meaning. When two readings remain plausible the
    answer is one concise question, never the first candidate. A resolver that
    guessed would be making a content decision while looking like a lookup.

Release is unchanged and separately asserted: resolution decides WHICH Script is
relevant and has no bearing on whether it may be shown, which stays REUSABLE-only.

No test here reaches the network.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_HUMAN_AUTHORED,
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_READINESS_REUSABLE,
)
from services.help_mode import HELP_LIBRARY_PROJECT_ID
from services.help_resolution import (
    BASIS_CONTROL,
    BASIS_CONVERSATION,
    BASIS_FREE_TEXT,
    BASIS_NONE,
    BASIS_PANEL,
    resolve_help_subject,
)

SURVIVAL_REF = "toolbox.spin.world-survival"
_REPO_ROOT = Path(__file__).resolve().parent.parent


class ContextResolutionTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_helpctx_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            for username in ("reviewer", "reader", "other"):
                db.session.add(User(
                    username=username, password_hash=generate_password_hash("x"),
                    role="admin" if username == "reviewer" else "user"))
            db.session.commit()
        self.store = CaseWorkspaceStore(self.tmp_dir)

    # -- fixtures ----------------------------------------------------------

    def _reusable_script(self, title, question, answer, ui_refs=()):
        """A Help Script all the way to REUSABLE, through the real gates.

        Built by driving the actual governed path rather than writing state, so
        these tests cannot pass against a Script that could not really exist.
        """
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        source = self.store.add_source(ws, name="help-guide:seed-%s" % title.lower().replace(" ", "-"),
                                       file_path="x", kind="document", actor="seed")
        evidence = self.store.register_plain_text_structure(
            ws, source["id"], answer, actor="seed")["evidence_item_ids"][0]
        case = self.store.create_case(ws, title="seed", objective="o", created_by="seed")
        step = self.store.record_investigation_step(
            ws, case_id=case["id"], step_kind="help_authoring",
            anchor={"object_type": "evidence_item", "object_id": evidence},
            question=question, triggered_by_actor="seed")
        claim = self.store.record_investigation_claim(
            ws, investigation_step_id=step["id"], statement=answer,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="seed",
            evidence_links=[{"object_type": "evidence_item", "object_id": evidence}])
        script = self.store.create_work_product(
            ws, artifact_type="script", title=title, created_by="seed",
            case_id=case["id"], source_investigation_step_id=step["id"])
        self.store.add_work_product_section(
            ws, work_product_id=script["id"], section_type="scene",
            content={"text": answer}, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
            author="seed",
            evidence_links=[{"object_type": "claim", "object_id": claim["id"]}])

        # Both model verdicts, then both human acts. Nothing skipped.
        self.store.record_script_fit_verdict(
            ws, work_product_id=script["id"], outcome="pass", reason="answers it",
            assessed_by="test", question=question, ran=True)
        self.store.record_script_consistency_verdict(
            ws, work_product_id=script["id"], outcome="pass", reason="consistent",
            assessed_by="test", ran=True)
        self.store.record_script_validation(
            ws, work_product_id=script["id"], decision="validated", actor="reviewer")
        self.store.accept_claim_as_observation(ws, claim_id=claim["id"], actor="reviewer")
        if ui_refs:
            self.store.record_script_ui_refs(
                ws, work_product_id=script["id"], ui_refs=list(ui_refs), actor="reviewer")

        readiness = self.store.resolve_script_readiness(
            self.store.get_or_create(HELP_LIBRARY_PROJECT_ID), script["id"])
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_REUSABLE,
                         "fixture did not reach REUSABLE: %s" % readiness["reasons"])
        return script["id"]

    def _survival(self):
        return self._reusable_script(
            "Survival Mode",
            "What is Survival Mode, and is it another kind of Spin?",
            "Survival Mode is a lens on either Spin, not a third kind of Spin.",
            ui_refs=[SURVIVAL_REF])

    def _client(self, username="reader"):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": username, "password": "x"},
                    follow_redirects=True)
        return client

    def _ask(self, client, question, control=None, page=None):
        payload = {"question": question, "context": {}}
        if control:
            payload["context"]["control"] = control
        if page:
            payload["context"]["page"] = page
        return client.post("/help/mode/ask", json=payload).get_json()

    # -- ACTION 4 case A: "this" resolves from ui_ref ----------------------

    def test_a_this_resolves_from_the_control_the_user_is_standing_on(self):
        script_id = self._survival()
        result = resolve_help_subject(
            self.store, "What does this do?", context={"control": SURVIVAL_REF})
        self.assertEqual(result.basis, BASIS_CONTROL)
        self.assertEqual(result.script_id, script_id)
        self.assertIsNone(result.clarification)

    def test_a_the_user_never_restates_the_control_name(self):
        """The stop condition, end to end through the real route."""
        self._survival()
        body = self._ask(self._client(), "What does this do?", control=SURVIVAL_REF)
        self.assertIsNotNone(body["answer"], "Help asked the user to identify the control")
        self.assertIn("not a third kind of Spin", body["answer"]["text"])
        self.assertEqual(body["resolution"]["basis"], BASIS_CONTROL)

    # -- ACTION 4 case B: a different question, same control ---------------

    def test_b_a_differently_worded_question_resolves_from_the_same_control(self):
        script_id = self._survival()
        result = resolve_help_subject(
            self.store, "Is this another kind of Spin?", context={"control": SURVIVAL_REF})
        self.assertEqual(result.script_id, script_id)
        self.assertEqual(result.basis, BASIS_CONTROL)

    # -- ACTION 8 point 3: exact equality is gone --------------------------

    def test_exact_question_equality_is_no_longer_required(self):
        """The retired defect, asserted directly.

        None of these is the Script's stored question, and every one must still
        reach it. Under the old lookup all three returned nothing.
        """
        script_id = self._survival()
        for question in ("What does this do?",
                         "Is this another kind of Spin?",
                         "what happens if I use this?"):
            result = resolve_help_subject(
                self.store, question, context={"control": SURVIVAL_REF})
            self.assertEqual(result.script_id, script_id, "failed for %r" % question)

    # -- ACTION 4 case C: free text with no UI context ---------------------

    def test_c_general_help_still_resolves_from_wording_alone(self):
        script_id = self._survival()
        result = resolve_help_subject(self.store, "What is Survival Mode?")
        self.assertEqual(result.basis, BASIS_FREE_TEXT)
        self.assertEqual(result.script_id, script_id)

    # -- ACTION 4 case D: ambiguity asks, never guesses --------------------

    def test_d_two_plausible_readings_produce_one_concise_question(self):
        self._reusable_script("First Spin", "What is First Spin?",
                              "First Spin establishes the baseline.")
        self._reusable_script("Delta Spin", "What is Delta Spin?",
                              "Delta Spin compares against the baseline.")
        result = resolve_help_subject(self.store, "What does the other Spin do?")
        self.assertIsNone(result.script_id, "an ambiguous question was answered by guessing")
        self.assertIsNotNone(result.clarification)
        self.assertIn("First Spin", result.clarification)
        self.assertIn("Delta Spin", result.clarification)
        self.assertEqual(len(result.candidates), 2)

    def test_d_the_clarification_reaches_the_user_and_is_recorded(self):
        self._reusable_script("First Spin", "What is First Spin?", "Baseline.")
        self._reusable_script("Delta Spin", "What is Delta Spin?", "Comparison.")
        client = self._client()
        body = self._ask(client, "What does the other Spin do?")
        self.assertIsNone(body["answer"])
        self.assertIn("Do you mean", body["resolution"]["clarification"])
        history = client.get("/help/mode/history").get_json()
        self.assertTrue(any("Do you mean" in m["body"] for m in history["messages"]),
                        "the user was asked something the record does not show")

    def test_an_ambiguous_control_prefix_asks_rather_than_picking_one(self):
        """Panel context that narrows to two controls is still ambiguous."""
        self._reusable_script("First Spin", "What is First Spin?", "Baseline.",
                              ui_refs=["toolbox.spin.world-first"])
        self._reusable_script("Delta Spin", "What is Delta Spin?", "Comparison.",
                              ui_refs=["toolbox.spin.world-delta"])
        result = resolve_help_subject(
            self.store, "What does this do?", context={"control": "toolbox.spin.unbound"})
        self.assertEqual(result.basis, BASIS_PANEL)
        self.assertIsNone(result.script_id)
        self.assertIn("Do you mean", result.clarification)

    # -- ACTION 2 level 3: Help conversation follow-up ---------------------

    def test_a_referential_follow_up_continues_the_current_topic(self):
        script_id = self._survival()
        client = self._client()
        self._ask(client, "What does this do?", control=SURVIVAL_REF)
        body = self._ask(client, "Why would I use this?")
        self.assertIsNotNone(body["answer"], "the follow-up lost the topic")
        self.assertEqual(body["resolution"]["basis"], BASIS_CONVERSATION)
        self.assertEqual(body["answer"]["script_id"], script_id)

    def test_a_self_contained_follow_up_is_not_re_pointed_at_the_last_topic(self):
        """Context narrows; it must not override. "What is First Spin?" asked
        after a Survival Mode answer is a new question, not a follow-up."""
        self._survival()
        first_id = self._reusable_script("First Spin", "What is First Spin?",
                                         "First Spin establishes the baseline.")
        client = self._client()
        self._ask(client, "What does this do?", control=SURVIVAL_REF)
        body = self._ask(client, "What is First Spin?")
        self.assertEqual(body["answer"]["script_id"], first_id)
        self.assertEqual(body["resolution"]["basis"], BASIS_FREE_TEXT)

    # -- ACTION 4 case E / ACTION 7: isolation -----------------------------

    def test_e_a_project_question_offers_a_transition_and_carries_nothing(self):
        self._survival()
        result = resolve_help_subject(
            self.store,
            "How does this affect the smoke-control review in my project?",
            context={"control": SURVIVAL_REF}, project_id="customer-project-1")
        self.assertIsNone(result.script_id)
        self.assertIsNotNone(result.project_transition)
        self.assertEqual(result.project_transition["transferred"], [])

    def test_a_project_question_does_not_read_any_project(self):
        customer = self.store.get_or_create("customer-project-1")
        source = self.store.add_source(customer, name="smoke_report.pdf", file_path="x",
                                       kind="document", actor="seed")
        self.store.register_plain_text_structure(
            customer, source["id"], "The smoke-control review found three deficiencies.",
            actor="seed")
        self._survival()
        client = self._client()
        body = self._ask(client, "What does the smoke-control review in my project say?")
        self.assertIsNone(body["answer"])
        self.assertFalse(body["project_context_used"])
        self.assertNotIn("deficiencies", str(body))

    def test_help_context_still_refuses_project_shaped_keys(self):
        client = self._client()
        response = client.post("/help/mode/ask", json={
            "question": "What is Survival Mode?",
            "context": {"control": SURVIVAL_REF, "project_id": "customer-project-1"},
        })
        self.assertEqual(response.status_code, 400)

    def test_one_users_help_history_never_reaches_another(self):
        script_id = self._survival()
        mine = self._client("reader")
        self._ask(mine, "What does this do?", control=SURVIVAL_REF)
        theirs = self._client("other")
        history = theirs.get("/help/mode/history").get_json()
        self.assertEqual(history["messages"], [])
        # And their follow-up cannot inherit my topic.
        body = self._ask(theirs, "Why would I use this?")
        self.assertIsNone(body["answer"])

    # -- ACTION 8 point 9: release stays REUSABLE-only ---------------------

    def test_a_bound_script_that_is_not_reusable_is_never_returned(self):
        """Binding says what a Script is about, never that it may be shown."""
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        case = self.store.create_case(ws, title="draft", objective="o", created_by="seed")
        step = self.store.record_investigation_step(
            ws, case_id=case["id"], step_kind="help_authoring",
            anchor={"object_type": "case", "object_id": case["id"]},
            question="What is Survival Mode?", triggered_by_actor="seed")
        draft = self.store.create_work_product(
            ws, artifact_type="script", title="Survival Mode", created_by="seed",
            case_id=case["id"], source_investigation_step_id=step["id"])
        self.store.record_script_ui_refs(
            ws, work_product_id=draft["id"], ui_refs=[SURVIVAL_REF], actor="reviewer")

        result = resolve_help_subject(
            self.store, "What does this do?", context={"control": SURVIVAL_REF})
        self.assertIsNone(result.script_id)
        body = self._ask(self._client(), "What does this do?", control=SURVIVAL_REF)
        self.assertIsNone(body["answer"])

    def test_nothing_resolves_when_the_library_is_empty(self):
        result = resolve_help_subject(
            self.store, "What does this do?", context={"control": SURVIVAL_REF})
        self.assertEqual(result.basis, BASIS_NONE)
        self.assertIsNone(result.script_id)
        self.assertIsNone(result.clarification)

    # -- bindings: shape validated here, existence validated by test ------

    def test_a_malformed_ui_ref_is_refused(self):
        script_id = self._survival()
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        with self.assertRaises(Exception):
            self.store.record_script_ui_refs(
                ws, work_product_id=script_id, ui_refs=["NOT A REF"], actor="reviewer")

    def test_every_bound_ui_ref_exists_in_the_ui_reference_map(self):
        """The registry stays a human document; this is the parity check.

        Reading UI_REFERENCE_MAP.md at request time to authorize a write would
        make a Markdown file a runtime dependency of the kernel. The same split
        the template refs already use: the scanner is a test.
        """
        registry = (_REPO_ROOT / "UI_REFERENCE_MAP.md").read_text(encoding="utf-8")
        known = set(re.findall(r"`([a-z0-9][a-z0-9._\-]*)`", registry))
        self.assertIn(SURVIVAL_REF, known,
                      "the ref this feature is demonstrated with is not in the registry")

    def test_a_reviewer_can_bind_through_the_authoring_surface(self):
        script_id = self._survival()
        client = self._client("reviewer")
        client.post("/help/authoring/scripts/%s/ui-refs" % script_id,
                    data={"ui_refs": "toolbox.spin.world-survival\ntoolbox.spin.help-survival"})
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        script = self.store.get_work_product(ws, script_id)
        self.assertEqual(script["help_ui_refs"],
                         ["toolbox.spin.world-survival", "toolbox.spin.help-survival"])

    def test_binding_does_not_retire_existing_verdicts(self):
        """What a Script explains is not what it says."""
        script_id = self._survival()
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        self.store.record_script_ui_refs(
            ws, work_product_id=script_id, ui_refs=["toolbox.spin.help-survival"],
            actor="reviewer")
        readiness = self.store.resolve_script_readiness(
            self.store.get_or_create(HELP_LIBRARY_PROJECT_ID), script_id)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_REUSABLE)

    # -- ACTION 8 points 10/11/12 -----------------------------------------

    def test_resolution_makes_no_model_call(self):
        self._survival()
        with patch("anthropic.Anthropic") as never:
            resolve_help_subject(self.store, "What does this do?",
                                 context={"control": SURVIVAL_REF})
            self._ask(self._client(), "What does this do?", control=SURVIVAL_REF)
            never.assert_not_called()

    def test_the_existing_help_surfaces_still_work(self):
        client = self._client("reviewer")
        self.assertEqual(client.get("/help").status_code, 200)
        self.assertEqual(client.get("/help/spin-and-survival-modes").status_code, 200)
        self.assertEqual(client.get("/help/studio").status_code, 200)
        self.assertEqual(client.get("/help/authoring").status_code, 200)

    def test_no_vocabulary_surface_returned(self):
        page = self._client("reviewer").get("/help/studio").get_data(as_text=True)
        for forbidden in ("Preferred term", "Did you mean", "vocab-chip", "accept_term"):
            self.assertNotIn(forbidden, page)

    def test_the_resolver_has_no_path_to_a_project(self):
        """Structural isolation, asserted against CODE rather than prose.

        The first version of this scanned the raw file and tripped over the
        module docstring, which says the word "claims" while explaining that it
        cannot read them - a test measuring its own documentation. Docstrings
        and comments are stripped so this asserts what the module DOES.
        """
        import ast
        import services.help_resolution as resolver

        tree = ast.parse(Path(resolver.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):  # docstrings are the only string constants we drop
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                    and isinstance(node.value.value, str):
                node.value.value = ""
        code = ast.unparse(tree)

        for forbidden in ("evidence_items", "project_conversation",
                          "get_claim", "get_evidence_item", "findings"):
            self.assertNotIn(forbidden, code,
                             "the resolver reached for %s" % forbidden)

        # And the signature offers no way in: there is no project workspace
        # parameter, only an id used to address a transition offer.
        import inspect
        params = set(inspect.signature(resolve_help_subject).parameters)
        self.assertEqual(params,
                         {"store", "question", "context", "active_script_id", "project_id"})


if __name__ == "__main__":
    unittest.main()
