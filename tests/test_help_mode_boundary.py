"""
Help / Learning Mode must not contaminate the project.

A user in Help is learning how ARCHIOSK works. That conversation must not touch
the project they happen to have open — not its evidence, claims, decisions,
WorkProducts, conversation, memory, or provenance.

THE BOUNDARY IS ONE THE KERNEL ALREADY ENFORCES

Help is a conversation held in a workspace that is not the user's project.
`constitutional-invariants.md` #8 makes project boundaries strict, a
`ProjectWorkspace` is exactly one project, and `_resolve_mm6_endpoint` already
refuses any object whose `project_id` does not match. So every protection that
already keeps two customers apart applies unchanged between Help and a project,
because to the kernel that is precisely what this is. No second conversation
platform was built.

TWO STRUCTURAL GUARANTEES, NOT TWO RULES

`HelpContext` has no field for a project id, source, claim or case — a caller
*cannot* pass project evidence into Help because the structure has nowhere to
put it. And `record_help_message` is never given a project workspace, so there
is no path from a Help message to a project record. Both are the same argument
the assessment functions use: make the wrong thing unrepresentable rather than
forbidden.

A project-shaped context is REFUSED rather than silently dropped. Dropping it
would leave the caller believing Help had received project context, and the next
reader guessing whether that was intended.
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    CONTENT_CLASS_HUMAN_AUTHORED,
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_VALIDATION_VALIDATED,
)
from services.help_mode import (
    HELP_LIBRARY_PROJECT_ID,
    HelpContext,
    HelpModeError,
    assert_context_is_help_shaped,
    help_session_project_id,
    is_help_workspace,
    propose_project_transition,
    read_help_conversation,
    record_help_message,
)

QUESTION = "What is Survival Mode, and is it another kind of Spin?"
PROJECT_QUESTION = "How does Survival Mode apply to this project's smoke-control review?"
HELP_TEXT = "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
ANSWER = "Survival Mode is a lens on either run, not a third kind of Spin."


class ContextShapeTests(unittest.TestCase):
    """The boundary as a dataclass, not as a rule."""

    def test_help_context_has_no_project_shaped_field(self):
        fields = set(HelpContext().to_dict()) | set(HelpContext.__dataclass_fields__)
        for forbidden in ("project_id", "source_id", "claim_id", "case_id",
                          "evidence", "work_product_id", "memory"):
            self.assertNotIn(forbidden, fields)

    def test_help_context_carries_what_help_legitimately_needs(self):
        context = HelpContext(page="workspace", control="toolbox.spin",
                              app_version="156", role="admin").to_dict()
        self.assertEqual(
            set(context), {"page", "control", "app_version", "role"})

    def test_project_material_in_a_context_is_refused_not_dropped(self):
        for bad in ({"project_id": "p1"}, {"claim_id": "c1"}, {"evidence": ["e"]},
                    {"conversation": []}, {"memory": {}}):
            with self.assertRaises(HelpModeError, msg=str(bad)):
                assert_context_is_help_shaped(bad)

    def test_the_refusal_names_what_was_wrong(self):
        with self.assertRaises(HelpModeError) as caught:
            assert_context_is_help_shaped({"project_id": "p", "claim_id": "c", "page": "ok"})
        message = str(caught.exception)
        self.assertIn("claim_id", message)
        self.assertIn("project_id", message)
        self.assertIn("Project Mode", message)

    def test_help_workspaces_are_identifiable(self):
        self.assertTrue(is_help_workspace(HELP_LIBRARY_PROJECT_ID))
        self.assertTrue(is_help_workspace(help_session_project_id("ana")))
        self.assertFalse(is_help_workspace("7400d6a3-ab54-4c84-9c10-96d89b023d93"))

    def test_a_help_conversation_must_belong_to_someone(self):
        for bad in ("", "   ", "!!!"):
            with self.assertRaises(HelpModeError):
                help_session_project_id(bad)


class StorageSeparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_helpmode_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "customer-project-1"
        self.project = self.store.get_or_create(self.project_id)

    def test_1_a_help_message_attaches_nothing_to_the_project(self):
        record_help_message(self.store, "ana", author="ana", body=QUESTION,
                            context=HelpContext(page="workspace", control="toolbox.spin"))
        project = self.store.get_or_create(self.project_id)
        self.assertEqual(project.project_conversation, [])
        self.assertEqual(project.sources, [])
        self.assertEqual(project.claims, [])
        self.assertEqual(project.work_products, [])
        self.assertEqual(project.evidence_items, [])

    def test_2_help_history_does_not_appear_in_project_chat_history(self):
        record_help_message(self.store, "ana", author="ana", body=QUESTION)
        self.assertTrue(read_help_conversation(self.store, "ana"))
        self.assertEqual(self.store.get_or_create(self.project_id).project_conversation, [])

    def test_3_project_history_does_not_appear_in_help(self):
        project = self.store.get_or_create(self.project_id)
        project.project_conversation.append(
            {"id": "m1", "author": "ana", "body": "project-only note"})
        self.store.save(project)

        history = read_help_conversation(self.store, "ana")
        self.assertEqual(history, [])
        record_help_message(self.store, "ana", author="ana", body=QUESTION)
        bodies = [m["body"] for m in read_help_conversation(self.store, "ana")]
        self.assertNotIn("project-only note", bodies)

    def test_4_help_content_never_becomes_project_evidence_or_memory(self):
        record_help_message(self.store, "ana", author="help", body=ANSWER)
        project = self.store.get_or_create(self.project_id)
        for collection in ("sources", "evidence_items", "claims", "derived_observations",
                           "findings", "work_products", "relationships"):
            self.assertEqual(getattr(project, collection), [], collection)

    def test_5_ui_control_identity_still_reaches_help(self):
        message = record_help_message(
            self.store, "ana", author="ana", body=QUESTION,
            context=HelpContext(page="workspace", control="toolbox.spin",
                                app_version="156", role="user"))
        self.assertEqual(message["help_context"]["control"], "toolbox.spin")
        self.assertEqual(message["help_context"]["page"], "workspace")

    def test_7_one_users_help_conversation_is_not_anothers(self):
        record_help_message(self.store, "ana", author="ana", body="ana's question")
        record_help_message(self.store, "ben", author="ben", body="ben's question")
        ana = [m["body"] for m in read_help_conversation(self.store, "ana")]
        ben = [m["body"] for m in read_help_conversation(self.store, "ben")]
        self.assertEqual(ana, ["ana's question"])
        self.assertEqual(ben, ["ben's question"])

    def test_help_session_and_library_are_different_workspaces(self):
        self.assertNotEqual(help_session_project_id("ana"), HELP_LIBRARY_PROJECT_ID)
        record_help_message(self.store, "ana", author="ana", body=QUESTION)
        library = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        self.assertEqual(library.project_conversation, [])


class TransitionTests(unittest.TestCase):
    def test_a_project_specific_question_gets_an_offer_not_an_answer(self):
        offer = propose_project_transition(PROJECT_QUESTION, "customer-project-1")
        self.assertEqual(offer["offer"], "Continue this in Project Mode?")
        self.assertEqual(offer["question"], PROJECT_QUESTION)

    def test_6_the_transition_transfers_nothing(self):
        offer = propose_project_transition(PROJECT_QUESTION, "customer-project-1")
        # Reported explicitly rather than omitted, so a reader cannot mistake
        # silence for "nothing to report" when it means "nothing moved".
        self.assertEqual(offer["transferred"], [])
        self.assertIn("does not read project evidence", offer["reason"])


class HelpModeRouteTests(unittest.TestCase):
    """The real routes, with a real session."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_helproute_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="learner",
                                password_hash=generate_password_hash("x"), role="user"))
            db.session.commit()
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "customer-project-1"
        self.store.get_or_create(self.project_id)

    def _client(self):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": "learner", "password": "x"},
                    follow_redirects=True)
        return client

    def _seed_answerable_script(self):
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        src = self.store.add_source(ws, name="help.html", file_path="x",
                                    kind="document", actor="seed")
        ev = self.store.register_pdf_page_structure(
            ws, src["id"], [HELP_TEXT], actor="seed")["evidence_item_ids"][0]
        case = self.store.create_case(ws, title="c", objective="o", created_by="seed")
        step = self.store.record_investigation_step(
            ws, case_id=case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": ev},
            question=QUESTION, triggered_by_actor="seed")
        claim = self.store.record_investigation_claim(
            ws, investigation_step_id=step["id"], statement=ANSWER,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="seed",
            evidence_links=[{"object_type": "evidence_item", "object_id": ev}])
        script = self.store.create_work_product(
            ws, artifact_type="script", title="Survival Mode", created_by="seed",
            source_investigation_step_id=step["id"])
        self.store.add_work_product_section(
            ws, work_product_id=script["id"], section_type="scene",
            content={"text": ANSWER}, content_class=CONTENT_CLASS_HUMAN_AUTHORED,
            author="seed", evidence_links=[{"object_type": "claim", "object_id": claim["id"]}])
        self.store.record_script_fit_verdict(
            ws, work_product_id=script["id"], outcome="pass", reason="answers", question=QUESTION)
        self.store.record_script_consistency_verdict(
            ws, work_product_id=script["id"], outcome="pass", reason="consistent")
        self.store.accept_claim_as_observation(
            ws, claim_id=claim["id"], actor="reviewer", reason="verified")
        self.store.record_script_validation(
            ws, work_product_id=script["id"],
            decision=SCRIPT_VALIDATION_VALIDATED, actor="reviewer")
        return script

    def test_asking_in_help_mode_answers_from_the_library_and_touches_no_project(self):
        self._seed_answerable_script()
        client = self._client()
        response = client.post("/help/mode/ask", json={
            "question": QUESTION,
            "context": {"page": "workspace", "control": "toolbox.spin"},
        })
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["mode"], "help")
        self.assertFalse(body["project_context_used"])
        self.assertIn("not a third kind of Spin", body["answer"]["text"])
        self.assertEqual(body["context"]["control"], "toolbox.spin")

        project = self.store.get_or_create(self.project_id)
        self.assertEqual(project.project_conversation, [])
        self.assertEqual(project.work_products, [])

    def test_a_request_carrying_project_material_is_refused(self):
        client = self._client()
        response = client.post("/help/mode/ask", json={
            "question": QUESTION,
            "context": {"page": "workspace", "project_id": self.project_id},
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("project material", response.get_json()["error"])

    def test_help_history_is_returned_and_is_help_scoped(self):
        client = self._client()
        client.post("/help/mode/ask", json={"question": QUESTION})
        body = client.get("/help/mode/history").get_json()
        self.assertEqual(body["mode"], "help")
        self.assertTrue(any(m["body"] == QUESTION for m in body["messages"]))
        for message in body["messages"]:
            self.assertEqual(message["scope"], "help")

    def test_an_unanswerable_question_gets_an_honest_nothing(self):
        client = self._client()
        body = client.post("/help/mode/ask", json={"question": "What is quantum foam?"}).get_json()
        self.assertIsNone(body["answer"])

    def test_a_draft_script_is_never_served_as_a_help_answer(self):
        # Seeded but never validated - machine checks alone must not release text.
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        self.store.create_work_product(
            ws, artifact_type="script", title="unvalidated", created_by="seed")
        client = self._client()
        body = client.post("/help/mode/ask", json={"question": QUESTION}).get_json()
        self.assertIsNone(body["answer"])

    def test_the_transition_route_offers_and_transfers_nothing(self):
        client = self._client()
        body = client.post("/help/mode/transition", json={
            "question": PROJECT_QUESTION, "project_id": self.project_id}).get_json()
        self.assertEqual(body["offer"], "Continue this in Project Mode?")
        self.assertEqual(body["transferred"], [])
        project = self.store.get_or_create(self.project_id)
        self.assertEqual(project.project_conversation, [])

    def test_help_mode_requires_authentication(self):
        anonymous = self.flask_app.test_client()
        for call in (lambda: anonymous.post("/help/mode/ask", json={"question": "x"}),
                     lambda: anonymous.get("/help/mode/history")):
            self.assertIn(call().status_code, (302, 401, 403))

    def test_8_the_existing_help_centre_still_works(self):
        client = self._client()
        self.assertEqual(client.get("/help").status_code, 200)
        self.assertEqual(client.get("/help/spin-and-survival-modes").status_code, 200)

    def test_8b_the_reserved_help_library_status_route_still_works(self):
        script = self._seed_answerable_script()
        client = self._client()
        body = client.get("/help/scripts/%s/status" % script["id"]).get_json()
        self.assertEqual(body["status"], "ready")


if __name__ == "__main__":
    unittest.main()
