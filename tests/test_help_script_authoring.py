"""
Help Script authoring — the reviewer surface that removes the scratchpad script.

Until now a Help Script could only be created by code. These tests exercise the
real Help Center routes: create, edit, save, re-check, validate.

SAVE IS NOT A MODEL CHECKPOINT

Creating a Script or adding a narrative unit persists content and spends no
external-AI call. Re-check is the one deliberate action that does. That is what
makes "no continuous model calls" true by construction rather than by restraint,
and it costs nothing in safety — a material edit already retires the prior
verdicts, so an edited Script cannot read as checked while it waits.

NO NEW OBJECT FAMILY

A Help Script is still `WorkProduct(artifact_type="script")` with ordered
`WorkProductSection`s citing `Claim`s, in the reserved Help Library workspace.
Authoring composes existing primitives; a parallel Help-content family would
have had to reinvent provenance, versioning and staleness and keep them in step.

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

from werkzeug.security import generate_password_hash

from services.case_workspace import (
    ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
    CaseWorkspaceStore,
    CLAIM_ADOPTION_PROPOSED,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
    OBSERVATION_AUTHOR_HUMAN,
    SCRIPT_CHECK_PASS,
    SCRIPT_CHECK_REVIEW_NEEDED,
    SCRIPT_READINESS_DRAFT,
    SCRIPT_READINESS_REUSABLE,
    SCRIPT_READINESS_VALIDATED,
)
from services.help_mode import HELP_LIBRARY_PROJECT_ID, help_session_project_id

QUESTION = "What is Survival Mode, and is it another kind of Spin?"
HELP_TEXT = "Survival Mode: A lens, not a third kind of Spin. It is a checkbox on either run."
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


class AuthoringSurfaceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_authoring_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            for username, role in (("reviewer", "admin"), ("reader", "user")):
                db.session.add(User(username=username,
                                    password_hash=generate_password_hash("x"), role=role))
            db.session.commit()

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.project_id = "customer-project-1"
        self.store.get_or_create(self.project_id)
        self.claim = self._seed_claim()

    def _seed_claim(self):
        """One governed Claim in the Help Library for a Script to cite."""
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        src = self.store.add_source(ws, name="spin_and_survival_modes.html",
                                    file_path="x", kind="document", actor="seed")
        ev = self.store.register_pdf_page_structure(
            ws, src["id"], [HELP_TEXT], actor="seed")["evidence_item_ids"][0]
        self.evidence_id = ev
        case = self.store.create_case(ws, title="seed", objective="o", created_by="seed")
        step = self.store.record_investigation_step(
            ws, case_id=case["id"], step_kind="cross_modal_investigation",
            anchor={"object_type": "evidence_item", "object_id": ev},
            question=QUESTION, triggered_by_actor="seed")
        return self.store.record_investigation_claim(
            ws, investigation_step_id=step["id"], statement=ANSWER,
            claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
            method=ANALYTICAL_METHOD_DIRECT_RETRIEVAL,
            confidence_state=CONFIDENCE_STATE_STRONG_DIRECT_SUPPORT,
            author_type=OBSERVATION_AUTHOR_HUMAN, created_by="seed",
            evidence_links=[{"object_type": "evidence_item", "object_id": ev}])

    def _client(self, username="reviewer"):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": username, "password": "x"},
                    follow_redirects=True)
        return client

    def _create(self, client, question=QUESTION, title="Survival Mode"):
        response = client.post("/help/authoring/scripts",
                               data={"question": question, "title": title})
        self.assertEqual(response.status_code, 302)
        return response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    def _author_claim(self, client, script_id, statement=ANSWER):
        """Record a claim through the surface, against THIS Script's question.

        A reviewer must do this rather than cite a claim recorded elsewhere:
        `question_fit` requires a Script to cite a claim produced by its own
        originating question, which is the guard against a Script assembled
        from another question's claims. Discovering that through a failing test
        is what added this authoring step.
        """
        before = {c["id"] for c in self._library().claims}
        client.post("/help/authoring/scripts/%s/claims" % script_id,
                    data={"statement": statement,
                          "evidence_item_ids": [self.evidence_id]})
        after = {c["id"] for c in self._library().claims}
        new_ids = after - before
        self.assertEqual(len(new_ids), 1, "claim was not recorded")
        return new_ids.pop()

    def _library(self):
        return self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)

    def _readiness(self, script_id):
        return self.store.resolve_script_readiness(self._library(), script_id)

    # -- create / edit / save ---------------------------------------------

    def test_a_reviewer_can_create_a_draft_help_script(self):
        client = self._client()
        script_id = self._create(client)
        script = self.store.get_work_product(self._library(), script_id)
        self.assertEqual(script["artifact_type"], "script")
        self.assertEqual(script["state"], "draft")
        self.assertEqual(self._readiness(script_id)["question"], QUESTION)

    def test_creating_and_saving_spend_no_model_call(self):
        # The load-bearing property of the hybrid model: Save is not a
        # checkpoint, so nothing here can quietly cost two API calls.
        client = self._client()
        with patch("anthropic.Anthropic") as anthropic_client:
            script_id = self._create(client)
            client.post("/help/authoring/scripts/%s/scenes" % script_id,
                        data={"text": ANSWER, "claim_ids": [self.claim["id"]]})
        anthropic_client.assert_not_called()

    def test_a_reviewer_can_open_and_edit_an_existing_script(self):
        client = self._client()
        script_id = self._create(client)
        page = client.get("/help/authoring/scripts/%s" % script_id)
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"Survival Mode", page.data)

        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [self.claim["id"]]})
        script = self.store.get_work_product(self._library(), script_id)
        scenes = [s for s in script["sections"] if not s["removed"]]
        self.assertEqual(len(scenes), 1)
        self.assertEqual(scenes[0]["content"]["text"], ANSWER)
        self.assertEqual(scenes[0]["evidence_links"][0]["object_id"], self.claim["id"])

    def test_citing_another_questions_claim_fails_question_fit(self):
        """The guard that added the claim-authoring step, asserted directly.

        `self.claim` was recorded against a DIFFERENT investigation step. Citing
        it produces a structurally sound Script that is nonetheless answering
        from the wrong investigation, and question_fit says so.
        """
        client = self._client()
        script_id = self._create(client)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [self.claim["id"]]})
        readiness = self._readiness(script_id)
        self.assertEqual(readiness["checks"]["question_fit"], "fail")
        self.assertTrue(any("produced by the originating question" in r
                            for r in readiness["reasons"]))

    def test_the_editor_only_offers_claims_from_this_scripts_own_question(self):
        client = self._client()
        script_id = self._create(client)
        own = self._author_claim(client, script_id)
        from services.help_mode import help_script_detail

        offered = {c["id"] for c in help_script_detail(self.store, script_id)["available_claims"]}
        self.assertIn(own, offered)
        self.assertNotIn(self.claim["id"], offered)

    def test_a_scene_cannot_cite_a_claim_that_does_not_exist(self):
        client = self._client()
        script_id = self._create(client)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": "Invented.", "claim_ids": ["no-such-claim"]})
        script = self.store.get_work_product(self._library(), script_id)
        self.assertEqual([s for s in script["sections"] if not s["removed"]], [])

    # -- the checkpoint behaviour -----------------------------------------

    def test_recheck_records_verdicts_and_returns_derived_readiness(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client(
                    [("pass", "answers both parts"), ("pass", "restates the claim")])):
            body = client.post("/help/scripts/%s/recheck" % script_id).get_json()
        self.assertEqual(body["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(body["checks"]["evidence_consistency"], SCRIPT_CHECK_PASS)
        self.assertEqual(body["label"], "Ready for review")

    def test_a_material_edit_makes_prior_verdicts_inapplicable(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % script_id)
        self.assertEqual(self._readiness(script_id)["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)

        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": "It also reranks findings.", "claim_ids": [claim_id]})

        checks = self._readiness(script_id)["checks"]
        self.assertEqual(checks["semantic_fit"], SCRIPT_CHECK_REVIEW_NEEDED)
        self.assertEqual(checks["evidence_consistency"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_the_editor_shows_which_verdicts_went_stale(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": "Another line.", "claim_ids": [claim_id]})

        page = client.get("/help/authoring/scripts/%s" % script_id)
        self.assertIn(b"Stale after edit", page.data)

    # -- human authority ---------------------------------------------------

    def test_validation_is_a_separate_act_and_does_not_adopt_claims(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % script_id)
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})

        # Validated, but the claim is still merely proposed - so NOT reusable.
        self.assertEqual(
            self.store.get_claim(self._library(), self.claim["id"])["adoption_state"],
            CLAIM_ADOPTION_PROPOSED)
        readiness = self._readiness(script_id)
        self.assertEqual(readiness["checks"]["human_validation"], SCRIPT_CHECK_PASS)
        # VALIDATED, not REUSABLE: the writing is signed off, the claim beneath
        # it is not. Those are two separate human acts and one click does not
        # perform both.
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_VALIDATED)
        self.assertEqual(readiness["checks"]["reuse_eligibility"], SCRIPT_CHECK_REVIEW_NEEDED)

    def test_the_full_pilot_reaches_reusable_only_after_both_human_acts(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % script_id)
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})
        # Validated by a human, and still not reusable - adoption is the second act.
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_VALIDATED)

        self.store.accept_claim_as_observation(
            self._library(), claim_id=claim_id, actor="reviewer", reason="verified")
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_a_rejection_blocks(self):
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _sequenced_client([("pass", "a"), ("pass", "b")])):
            client.post("/help/scripts/%s/recheck" % script_id)
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "rejected", "comments": "tone is wrong"})
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_DRAFT)

    def test_no_readiness_field_is_ever_written(self):
        client = self._client()
        script_id = self._create(client)
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})
        stored = self.store.get_work_product(self._library(), script_id)
        for forbidden in ("readiness", "script_readiness", "reusable", "validated"):
            self.assertNotIn(forbidden, stored)

    # -- boundaries --------------------------------------------------------

    def test_authoring_never_touches_a_customer_project(self):
        client = self._client()
        script_id = self._create(client)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [self.claim["id"]]})
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})

        project = self.store.get_or_create(self.project_id)
        for collection in ("work_products", "claims", "sources", "evidence_items",
                           "cases", "project_conversation", "findings"):
            self.assertEqual(getattr(project, collection), [], collection)

    def test_authoring_does_not_write_to_a_help_session_workspace(self):
        client = self._client()
        self._create(client)
        session_ws = self.store.get_or_create(help_session_project_id("reviewer"))
        self.assertEqual(session_ws.work_products, [])
        self.assertEqual(session_ws.project_conversation, [])

    def test_a_non_reviewer_cannot_reach_the_authoring_surface(self):
        reader = self._client("reader")
        for call in (
            lambda: reader.get("/help/authoring"),
            lambda: reader.post("/help/authoring/scripts",
                                data={"question": "q", "title": "t"}),
        ):
            self.assertEqual(call().status_code, 403)

    def test_authoring_requires_authentication(self):
        anonymous = self.flask_app.test_client()
        self.assertIn(anonymous.get("/help/authoring").status_code, (302, 401, 403))

    # -- re-check from the editor -----------------------------------------

    def test_recheck_from_the_editor_returns_to_the_editor(self):
        """The reviewer presses a button and gets their page back.

        The JSON `/help/scripts/<id>/recheck` serves the concierge and is not
        wrong; it is simply not what a browser form should land on. Wiring the
        button to it would have left a reviewer staring at a JSON document with
        no way back, which is why this asserts the redirect target and not just
        that verdicts were recorded.
        """
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": ANSWER, "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV),                 patch("anthropic.Anthropic", _sequenced_client(
                    [("pass", "answers both parts"), ("pass", "restates the claim")])):
            response = client.post("/help/authoring/scripts/%s/recheck" % script_id)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].endswith(
            "/help/authoring/scripts/%s" % script_id))
        self.assertNotIn("application/json", response.headers.get("Content-Type", ""))

        readiness = self._readiness(script_id)
        self.assertEqual(readiness["checks"]["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(readiness["checks"]["evidence_consistency"], SCRIPT_CHECK_PASS)

    def test_a_blocked_recheck_names_the_stage_that_blocked_it(self):
        """"Blocked" without a name sends the reviewer back to re-read everything."""
        client = self._client()
        script_id = self._create(client)
        claim_id = self._author_claim(client, script_id)
        client.post("/help/authoring/scripts/%s/scenes" % script_id,
                    data={"text": "Survival Mode is a third kind of Spin.",
                          "claim_ids": [claim_id]})
        with patch.dict(os.environ, _ENV),                 patch("anthropic.Anthropic", _sequenced_client(
                    [("fail", "does not address whether it is a kind of Spin")])):
            client.post("/help/authoring/scripts/%s/recheck" % script_id)
            page = client.get("/help/authoring/scripts/%s" % script_id)
        self.assertIn(b"Blocked by", page.data)
        self.assertNotEqual(self._readiness(script_id)["readiness"],
                            SCRIPT_READINESS_REUSABLE)

    def test_the_editor_recheck_button_does_not_point_at_the_json_route(self):
        """A regression guard on the wiring itself, not on the route it calls."""
        client = self._client()
        script_id = self._create(client)
        page = client.get("/help/authoring/scripts/%s" % script_id)
        self.assertIn(b"/help/authoring/scripts/%s/recheck" % script_id.encode(), page.data)
        self.assertNotIn(b'action="/help/scripts/', page.data)

    def test_a_reviewer_can_reach_manual_authoring_from_the_help_index(self):
        """The surface has to be findable, or it is a URL only its author knows.

        The route changed when the Clip Studio became the entrance
        (CLAUDE-HELP-CLIP-STUDIO-01): /help now leads to the Studio, and manual
        authoring is reached from there. The intent this test was written to
        defend is unchanged and is asserted along the whole chain rather than
        against the old destination - checking only the first hop would let the
        editor become unreachable while this stayed green.
        """
        client = self._client()
        index = client.get("/help")
        self.assertIn(b"/help/studio", index.data)
        studio = client.get("/help/studio")
        self.assertEqual(studio.status_code, 200)
        self.assertIn(b"/help/authoring", studio.data)

    def test_a_reader_is_not_shown_the_authoring_entrance(self):
        """And the reader sees neither hop."""
        page = self._client("reader").get("/help")
        self.assertNotIn(b"/help/authoring", page.data)
        self.assertNotIn(b"/help/studio", page.data)

    def test_hiding_the_link_is_not_the_gate(self):
        """A reader who types the URL is refused by the route, not by the template.

        Worth its own test because the previous two would both still pass if the
        gate were only the hidden link - which is how a UI-only control becomes
        an authorization hole.
        """
        client = self._client("reader")
        self.assertEqual(client.get("/help/authoring").status_code, 403)
        self.assertEqual(client.post("/help/authoring/scripts",
                                     data={"question": "q", "title": "t"}).status_code, 403)

    def test_the_editor_is_not_a_one_way_door(self):
        """The scenario-first path must be walkable in both directions.

        A reviewer reaches the editor from a clip via "Edit Script". Before
        this, the only way out was "Back to authoring" - the manual index -
        so the primary workflow dead-ended in the secondary one and the clip
        you were reviewing became unreachable without the back button.
        """
        client = self._client()
        script_id = self._create(client)
        page = client.get("/help/authoring/scripts/%s" % script_id).get_data(as_text=True)
        self.assertIn("/help/studio/%s" % script_id, page, "no way back to the clip")
        self.assertIn('"/help/studio"', page, "no way back to the Studio")

    def test_the_authoring_index_can_return_to_the_studio(self):
        page = self._client().get("/help/authoring").get_data(as_text=True)
        self.assertIn('"/help/studio"', page)

    def test_the_existing_help_centre_still_works(self):
        client = self._client()
        self.assertEqual(client.get("/help").status_code, 200)
        self.assertEqual(client.get("/help/spin-and-survival-modes").status_code, 200)

    def test_a_script_needs_both_a_question_and_a_title(self):
        client = self._client()
        before = len([w for w in self._library().work_products
                      if w.get("artifact_type") == "script"])
        client.post("/help/authoring/scripts", data={"question": "", "title": "t"})
        client.post("/help/authoring/scripts", data={"question": "q", "title": ""})
        after = len([w for w in self._library().work_products
                     if w.get("artifact_type") == "script"])
        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
