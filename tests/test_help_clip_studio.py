"""
Help Clip Studio — one scenario in, one governed DRAFT clip out.

WHAT THESE TESTS ARE ACTUALLY DEFENDING

Not "the generator works". The interesting property is that making the
machinery invisible did not make it absent: a generated Script is DRAFT, faces
the identical gate, and reaches REUSABLE only through the same two human acts a
hand-authored one needs. Several tests below exist purely to prove a shortcut
was NOT introduced — generation cannot validate, cannot adopt, cannot promote —
because that is exactly what a scenario-first surface would be tempted to do.

GROUNDING IS CHECKED ON OUR SIDE, NOT TRUSTED FROM THE MODEL

The prompt asks for evidence ids drawn only from what was shown. The guarantee
is that `generate_help_clip` re-resolves every returned id against the Help
Library before writing anything, so an invented id becomes a MISSING binding
that the structural gate fails honestly, never a fabricated citation. There is a
test that hands back a fabricated id specifically to prove that.

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
    CaseWorkspaceStore,
    CLAIM_ADOPTION_PROPOSED,
    SCRIPT_CHECK_PASS,
    SCRIPT_READINESS_DRAFT,
    SCRIPT_READINESS_REUSABLE,
    SCRIPT_READINESS_VALIDATED,
)
from services.help_clip_studio import select_help_evidence
from services.help_mode import HELP_LIBRARY_PROJECT_ID

SCENARIO = (
    "Explain Survival Mode to a new ARCHIOSK user. Show where the checkbox is, "
    "explain that it applies to First Spin or Delta Spin, and make clear that it "
    "is not a third kind of Spin."
)

_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}


def _response(payload: dict):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    response = MagicMock()
    response.content = [block]
    return response


def _client_returning(payloads: list):
    """A fake Anthropic client answering a fixed sequence of calls."""
    client = MagicMock()
    client.messages.create.side_effect = [_response(p) for p in payloads]
    return MagicMock(return_value=client)


def _compilation(evidence_ids, unsupported=None):
    """What a well-behaved model returns for the pilot scenario."""
    return {
        "question": "What is Survival Mode, and is it another kind of Spin?",
        "title": "Survival Mode",
        "claims": [
            {"statement": "Survival Mode is a lens, not a third kind of Spin.",
             "evidence_ids": evidence_ids[:1]},
            {"statement": "Survival Mode is a checkbox that applies to either "
                          "First Spin or Delta Spin.",
             "evidence_ids": evidence_ids[:2]},
        ],
        "scenes": [
            {"text": "Survival Mode is a lens on a Spin, not a third kind of Spin.",
             "claim_indexes": [0]},
            {"text": "Tick the Survival Mode checkbox before running either "
                     "First Spin or Delta Spin.",
             "claim_indexes": [1]},
        ],
        "unsupported": unsupported or [],
        "reason": "Grounded in the published Spin and Survival Mode guide.",
    }


_PASS = {"outcome": "pass", "reason": "answers every material part",
         "problem_unit_ids": []}


class HelpClipStudioTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_clipstudio_"))
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

    # -- helpers -----------------------------------------------------------

    def _client(self, username="reviewer"):
        client = self.flask_app.test_client()
        client.post("/login", data={"username": username, "password": "x"},
                    follow_redirects=True)
        return client

    def _open_studio(self, client):
        """Visiting the Studio is what registers the guide evidence."""
        response = client.get("/help/studio")
        self.assertEqual(response.status_code, 200)
        return response

    def _evidence_ids(self, limit=4):
        """The ids the generator will really show the model, in its own order."""
        return [item["id"] for item in select_help_evidence(self.store, SCENARIO)[:limit]]

    def _generate(self, client, payloads=None, scenario=SCENARIO):
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning(
                    payloads or [_compilation(self._evidence_ids()), _PASS, _PASS])):
            response = client.post("/help/studio/generate", data={"scenario": scenario})
        self.assertEqual(response.status_code, 302)
        return response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]

    def _library(self):
        return self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)

    def _readiness(self, script_id):
        return self.store.resolve_script_readiness(self._library(), script_id)

    # -- 1/2/3: one scenario produces a complete draft package -------------

    def test_a_reviewer_enters_one_scenario_and_gets_a_complete_draft(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)

        from services.help_clip_studio import clip_package
        clip = clip_package(self.store, script_id)
        self.assertEqual(clip["question"],
                         "What is Survival Mode, and is it another kind of Spin?")
        self.assertEqual(clip["title"], "Survival Mode")
        self.assertEqual(len(clip["scenes"]), 2)
        self.assertEqual([c["order"] for c in clip["captions"]], [0, 1])
        self.assertTrue(clip["sources"], "the clip cites no governed source")
        self.assertEqual(clip["scenario"], SCENARIO)

    def test_the_reviewer_authored_no_claims_or_units_by_hand(self):
        """The whole product change: no manual construction in the normal path.

        The only request the reviewer made was the scenario, and claims, scenes
        and evidence bindings all exist afterwards.
        """
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)

        workspace = self._library()
        script = self.store.get_work_product(workspace, script_id)
        step_id = script["source_investigation_step_id"]
        claims = [c for c in workspace.claims
                  if c.get("investigation_step_id") == step_id]
        self.assertEqual(len(claims), 2)
        self.assertTrue(all(c["created_by"] == "reviewer" for c in claims))
        scenes = [s for s in script["sections"] if not s["removed"]]
        self.assertEqual(len(scenes), 2)
        self.assertTrue(all(
            any(l["object_type"] == "claim" for l in s["evidence_links"]) for s in scenes))

    # -- 4/5: Help evidence used, customer project context never ----------

    def test_generation_is_grounded_in_the_published_help_guides(self):
        client = self._client()
        self._open_studio(client)
        workspace = self._library()
        names = {s["name"] for s in workspace.sources}
        self.assertIn("help-guide:spin-and-survival-modes", names)
        # The guide's own words made it into addressable evidence.
        corpus = " ".join(str(i.get("content", "")) for i in workspace.evidence_items)
        self.assertIn("third kind of Spin", corpus)

    def test_no_customer_project_evidence_is_ever_selected(self):
        """A customer project holding a perfect keyword match must not be reachable."""
        customer = self.store.get_or_create("customer-project-1")
        source = self.store.add_source(customer, name="customer_secret.pdf",
                                       file_path="x", kind="document", actor="seed")
        self.store.register_plain_text_structure(
            customer, source["id"],
            "Survival Mode Spin checkbox First Delta ARCHIOSK user explain.",
            actor="seed")

        client = self._client()
        self._open_studio(client)
        selected = select_help_evidence(self.store, SCENARIO)
        self.assertTrue(selected)
        library_ids = {i["id"] for i in self._library().evidence_items}
        for item in selected:
            self.assertIn(item["id"], library_ids)
        self.assertNotIn("customer_secret", " ".join(i["text"] for i in selected))

    def test_the_generated_clip_holds_no_customer_project_objects(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)
        customer = self.store.get_or_create("customer-project-1")
        self.assertEqual([w for w in customer.work_products], [])
        self.assertEqual([c for c in customer.claims], [])

    # -- 6/7: both model checks run at the generation checkpoint -----------

    def test_generation_runs_question_fit_and_evidence_consistency_once(self):
        client = self._client()
        self._open_studio(client)
        fake = _client_returning([_compilation(self._evidence_ids()), _PASS, _PASS])
        with patch.dict(os.environ, _ENV), patch("anthropic.Anthropic", fake):
            client.post("/help/studio/generate", data={"scenario": SCENARIO})
        # Exactly three: compile, question fit, evidence consistency. Not a loop.
        self.assertEqual(fake.return_value.messages.create.call_count, 3)

        script_id = [w["id"] for w in self._library().work_products][0]
        checks = self._readiness(script_id)["checks"]
        self.assertEqual(checks["semantic_fit"], SCRIPT_CHECK_PASS)
        self.assertEqual(checks["evidence_consistency"], SCRIPT_CHECK_PASS)

    # -- 8: generation cannot validate, adopt or promote -------------------

    def test_generation_produces_draft_and_cannot_promote(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)

        readiness = self._readiness(script_id)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_DRAFT)
        script = self.store.get_work_product(self._library(), script_id)
        self.assertEqual(script.get("script_validations", []), [],
                         "generation recorded a human validation")
        self.assertEqual(script["state"], "draft")

    def test_generation_leaves_every_claim_unadopted(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)
        workspace = self._library()
        step_id = self.store.get_work_product(workspace, script_id)["source_investigation_step_id"]
        for claim in workspace.claims:
            if claim.get("investigation_step_id") == step_id:
                self.assertEqual(claim["adoption_state"], CLAIM_ADOPTION_PROPOSED)

    # -- 9/10: editing invalidates, re-check is explicit -------------------

    def test_editing_a_generated_clip_retires_its_verdicts(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)
        self.assertEqual(self._readiness(script_id)["checks"]["semantic_fit"],
                         SCRIPT_CHECK_PASS)

        with patch("anthropic.Anthropic") as never:
            client.post("/help/authoring/scripts/%s/scenes" % script_id,
                        data={"text": "A materially different sentence.",
                              "claim_ids": []})
            never.assert_not_called()

        checks = self._readiness(script_id)["checks"]
        self.assertNotEqual(checks["semantic_fit"], SCRIPT_CHECK_PASS)

    def test_no_model_call_happens_outside_a_deliberate_action(self):
        """Opening the Studio and reading a clip spend nothing."""
        client = self._client()
        with patch("anthropic.Anthropic") as never:
            self._open_studio(client)
            never.assert_not_called()
        script_id = self._generate(client)
        with patch("anthropic.Anthropic") as never:
            client.get("/help/studio/%s" % script_id)
            client.get("/help/authoring/scripts/%s" % script_id)
            never.assert_not_called()

    # -- 11/12: the human acts stay human, and stay separate ---------------

    def test_validation_is_human_and_does_not_adopt_claims(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)

        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})
        readiness = self._readiness(script_id)
        self.assertEqual(readiness["checks"]["human_validation"], SCRIPT_CHECK_PASS)
        self.assertEqual(readiness["readiness"], SCRIPT_READINESS_VALIDATED)
        self.assertNotEqual(readiness["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_reusable_needs_adoption_as_well_and_there_is_no_bypass(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)
        client.post("/help/authoring/scripts/%s/validate" % script_id,
                    data={"decision": "validated"})
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_VALIDATED)

        workspace = self._library()
        step_id = self.store.get_work_product(workspace, script_id)["source_investigation_step_id"]
        for claim in list(workspace.claims):
            if claim.get("investigation_step_id") == step_id:
                self.store.accept_claim_as_observation(
                    workspace, claim_id=claim["id"], actor="reviewer")
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_REUSABLE)

    def test_no_route_can_set_readiness_directly(self):
        """There is no 'make reusable' control anywhere on these surfaces."""
        rules = [str(r) for r in self.flask_app.url_map.iter_rules() if "/help" in str(r)]
        for rule in rules:
            self.assertNotIn("reusable", rule.lower())
            self.assertNotIn("promote", rule.lower())
            self.assertNotIn("publish", rule.lower())

    # -- 4 again: the honest-gap behaviour ---------------------------------

    def test_a_fabricated_evidence_id_becomes_a_missing_binding_not_a_citation(self):
        client = self._client()
        self._open_studio(client)
        payload = _compilation(["not-a-real-evidence-id"])
        script_id = self._generate(client, payloads=[payload, _PASS, _PASS])

        workspace = self._library()
        step_id = self.store.get_work_product(workspace, script_id)["source_investigation_step_id"]
        for claim in workspace.claims:
            if claim.get("investigation_step_id") == step_id:
                self.assertEqual(claim["evidence_links"], [],
                                 "an invented evidence id was written as a citation")
        # And the gate says so rather than letting it look fine.
        self.assertEqual(self._readiness(script_id)["readiness"], SCRIPT_READINESS_DRAFT)

    def test_an_unsupported_scenario_names_what_is_missing(self):
        client = self._client()
        self._open_studio(client)
        payload = _compilation(self._evidence_ids(),
                               unsupported=["where the checkbox is on screen"])
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning([payload, _PASS, _PASS])):
            response = client.post("/help/studio/generate", data={"scenario": SCENARIO},
                                   follow_redirects=True)
        self.assertIn(b"where the checkbox is on screen", response.data)

    def test_a_scenario_that_cannot_compile_creates_nothing(self):
        """A failed generation must not leave a half-built Script behind."""
        client = self._client()
        self._open_studio(client)
        broken = MagicMock()
        broken.messages.create.side_effect = RuntimeError("provider down")
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", MagicMock(return_value=broken)):
            response = client.post("/help/studio/generate", data={"scenario": SCENARIO},
                                   follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([w for w in self._library().work_products], [])

    # -- 13/14: isolation and the existing guides still hold ---------------

    def test_help_mode_isolation_still_holds(self):
        client = self._client()
        self._open_studio(client)
        self._generate(client)
        # Nothing the Studio does may create or touch a project workspace.
        self.assertEqual(self.store.get_or_create("customer-project-1").work_products, [])

    def test_the_existing_help_guides_still_work(self):
        client = self._client()
        self.assertEqual(client.get("/help").status_code, 200)
        for guide in ("spin-and-survival-modes", "new-project", "file-types-and-limits"):
            self.assertEqual(client.get("/help/%s" % guide).status_code, 200)

    def test_help_leads_to_the_studio_not_the_raw_editor(self):
        page = self._client().get("/help")
        self.assertIn(b"/help/studio", page.data)

    def test_a_reader_cannot_reach_the_studio(self):
        client = self._client("reader")
        self.assertEqual(client.get("/help/studio").status_code, 403)
        self.assertEqual(client.post("/help/studio/generate",
                                     data={"scenario": SCENARIO}).status_code, 403)

    # -- 15/16: no rendering, no 2D/3D ------------------------------------

    def test_the_clip_package_is_data_and_renders_nothing(self):
        """ACTION 9 stops at the package. A renderer here would have made the
        artifact authoritative instead of the Script."""
        import services.help_clip_studio as studio
        source = Path(studio.__file__).read_text(encoding="utf-8")
        for forbidden in ("ffmpeg", "moviepy", "import cv2", "engine.spatial_compiler",
                          "ifc", "mp4", "codec"):
            self.assertNotIn(forbidden, source.lower(),
                             "the Studio reached into rendering or 2D/3D territory")

    def test_the_reviewer_sees_the_clip_before_any_kernel_vocabulary(self):
        client = self._client()
        self._open_studio(client)
        script_id = self._generate(client)
        page = client.get("/help/studio/%s" % script_id).get_data(as_text=True)
        # The primary view carries the clip; the kernel words live behind the
        # collapsed Advanced section, which must come after them.
        self.assertLess(page.index("Help Clip"), page.index("Advanced review details"))
        self.assertLess(page.index("Sources used"), page.index("semantic_fit"))

    # -- regenerate --------------------------------------------------------

    def test_regenerate_recompiles_the_same_scenario_and_keeps_the_first(self):
        client = self._client()
        self._open_studio(client)
        first = self._generate(client)
        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning(
                    [_compilation(self._evidence_ids()), _PASS, _PASS])):
            response = client.post("/help/studio/%s/regenerate" % first)
        second = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        self.assertNotEqual(first, second)
        self.assertIsNotNone(self.store.get_work_product(self._library(), first))
        script = self.store.get_work_product(self._library(), second)
        self.assertEqual(script["script_scenario"]["scenario"], SCENARIO)


if __name__ == "__main__":
    unittest.main()
