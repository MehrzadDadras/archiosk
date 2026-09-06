"""
Generated Help content must never be recorded as human-authored.

WHAT WENT WRONG, AND WHY THIS FILE EXISTS

`generate_help_clip` called `add_help_claim` and `add_help_script_scene` without
overriding their defaults. Those defaults are correct for the reviewer authoring
path they were written for — human author, directly_verified — so model-written
statements entered the governed record as HUMAN, DIRECTLY-VERIFIED observations.
Five Scripts reached production that way before it was caught.

The sharpest part is that the kernel already forbids exactly this. A claim with
`author_type="ai"` may not be `directly_verified`, because that "would claim
deterministic computation for a result that was AI-generated". The guard never
fired — not because it was bypassed, but because generation never told it the
true author. A guard you route around by omission protects nothing.

So these tests assert the negative directly: nothing the machine wrote may carry
human provenance, and no later human act may convert it.

PROVENANCE IS PERMANENT

`WorkProductSection`'s own contract states that `accepted_by`/`accepted_at` are
deliberately separate from `content_class`, so accepting AI content does not
rewrite its origin — it stays `ai_proposed` forever. Validation records a
decision about content; it never restates who wrote it. There is a test below
for that specifically, because "the human signed it off, so now it's human
work" is the most natural wrong turn available here.

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
    CLAIM_CLASS_AI_PROPOSAL,
    CLAIM_CLASS_DIRECTLY_VERIFIED,
    CLAIM_CLASS_UNKNOWN,
    CONTENT_CLASS_AI_PROPOSED,
    CONTENT_CLASS_HUMAN_AUTHORED,
    OBSERVATION_AUTHOR_AI,
    OBSERVATION_AUTHOR_HUMAN,
)
from services.help_mode import HELP_LIBRARY_PROJECT_ID

SCENARIO = "Explain Survival Mode to a new ARCHIOSK user."
_ENV = {"ANTHROPIC_API_KEY": "unit-test-key-never-used", "ANTHROPIC_TIMEOUT_SECONDS": "5"}
_PASS = {"outcome": "pass", "reason": "ok", "problem_unit_ids": []}


def _response(payload):
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    r = MagicMock()
    r.content = [block]
    return r


def _client_returning(payloads):
    c = MagicMock()
    c.messages.create.side_effect = [_response(p) for p in payloads]
    return MagicMock(return_value=c)


class GeneratedProvenanceTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_prov_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="reviewer",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.evidence_id = self._seed_evidence()

    def _seed_evidence(self):
        ws = self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)
        source = self.store.add_source(ws, name="help-guide:spin", file_path="x",
                                       kind="document", actor="seed")
        return self.store.register_plain_text_structure(
            ws, source["id"],
            "Survival Mode is a lens, not a third kind of Spin.",
            actor="seed")["evidence_item_ids"][0]

    def _library(self):
        return self.store.get_or_create(HELP_LIBRARY_PROJECT_ID)

    def _payload(self, evidence_ids):
        return {
            "question": "What is Survival Mode?",
            "title": "Survival Mode",
            "claims": [{"statement": "Survival Mode is a lens, not a third kind of Spin.",
                        "evidence_ids": evidence_ids}],
            "scenes": [{"text": "Survival Mode is a lens on either Spin.",
                        "claim_indexes": [0]}],
            "directions": [],
            "unsupported": [],
        }

    def _generate(self, payload=None):
        from services.help_clip_studio import generate_help_clip

        with patch.dict(os.environ, _ENV), \
                patch("anthropic.Anthropic", _client_returning(
                    [payload or self._payload([self.evidence_id]), _PASS, _PASS])):
            return generate_help_clip(
                self.store, scenario=SCENARIO, actor="reviewer", policy_decision="allow")

    def _script_claims(self, script_id):
        ws = self._library()
        step = self.store.get_work_product(ws, script_id)["source_investigation_step_id"]
        return [c for c in ws.claims if c.get("investigation_step_id") == step]

    def _scenes(self, script_id):
        script = self.store.get_work_product(self._library(), script_id)
        return [s for s in script["sections"]
                if s["section_type"] == "scene" and not s["removed"]]

    # -- the defect, asserted directly -------------------------------------

    def test_generated_scenes_are_ai_proposed_not_human_authored(self):
        result = self._generate()
        for scene in self._scenes(result["script_id"]):
            self.assertEqual(scene["content_class"], CONTENT_CLASS_AI_PROPOSED)
            self.assertNotEqual(scene["content_class"], CONTENT_CLASS_HUMAN_AUTHORED)

    def test_generated_claims_are_authored_by_ai(self):
        result = self._generate()
        claims = self._script_claims(result["script_id"])
        self.assertTrue(claims)
        for claim in claims:
            self.assertEqual(claim["author_type"], OBSERVATION_AUTHOR_AI)
            self.assertNotEqual(claim["author_type"], OBSERVATION_AUTHOR_HUMAN)

    def test_generated_claims_are_never_directly_verified(self):
        """The exact combination the kernel forbids, and the one that shipped."""
        result = self._generate()
        for claim in self._script_claims(result["script_id"]):
            self.assertEqual(claim["claim_class"], CLAIM_CLASS_AI_PROPOSAL)
            self.assertNotEqual(claim["claim_class"], CLAIM_CLASS_DIRECTLY_VERIFIED)

    def test_the_kernel_guard_is_now_armed_rather_than_routed_around(self):
        """Proof the guard would fire if generation ever regressed.

        The defect was not a bypassed check - it was a check that never learned
        the true author. This asserts the kernel really does refuse the bad
        combination, so passing the true author is what protects us.
        """
        from services.case_workspace import CaseWorkspaceError
        from services.help_mode import add_help_claim, create_help_script

        script = create_help_script(self.store, question="q", title="t", actor="reviewer")
        with self.assertRaises(CaseWorkspaceError) as caught:
            add_help_claim(
                self.store, script_id=script["id"], statement="s", actor="reviewer",
                evidence_item_ids=[self.evidence_id],
                claim_class=CLAIM_CLASS_DIRECTLY_VERIFIED,
                author_type=OBSERVATION_AUTHOR_AI,
            )
        self.assertIn("AI-authored claim cannot be classified", str(caught.exception))

    # -- provenance is permanent -------------------------------------------

    def test_human_validation_does_not_convert_generated_provenance(self):
        """Acceptance and authorship are two different facts.

        A reviewer validating a Script is signing off on content; they are not
        becoming its author. If validation rewrote content_class, model prose
        would become human prose by the act of approving it - which is the exact
        thing WorkProductSection's contract forbids.
        """
        result = self._generate()
        script_id = result["script_id"]
        before = [s["content_class"] for s in self._scenes(script_id)]

        ws = self._library()
        self.store.record_script_validation(
            ws, work_product_id=script_id, decision="validated", actor="reviewer")

        after = [s["content_class"] for s in self._scenes(script_id)]
        self.assertEqual(before, after)
        self.assertTrue(all(c == CONTENT_CLASS_AI_PROPOSED for c in after))

    def test_claim_adoption_does_not_convert_authorship(self):
        result = self._generate()
        ws = self._library()
        for claim in self._script_claims(result["script_id"]):
            self.store.accept_claim_as_observation(
                ws, claim_id=claim["id"], actor="reviewer")
        for claim in self._script_claims(result["script_id"]):
            self.assertEqual(claim["author_type"], OBSERVATION_AUTHOR_AI,
                             "adoption rewrote who wrote the claim")
            self.assertEqual(claim["claim_class"], CLAIM_CLASS_AI_PROPOSAL)

    # -- the hand-authoring path keeps its own, correct defaults -----------

    def test_a_reviewer_authoring_by_hand_is_still_recorded_as_human(self):
        """The fix must not overcorrect. A human really did write these."""
        from services.help_mode import add_help_claim, add_help_script_scene, create_help_script

        script = create_help_script(self.store, question="q", title="t", actor="reviewer")
        claim = add_help_claim(
            self.store, script_id=script["id"], statement="A human wrote this.",
            actor="reviewer", evidence_item_ids=[self.evidence_id])
        self.assertEqual(claim["author_type"], OBSERVATION_AUTHOR_HUMAN)
        self.assertEqual(claim["claim_class"], CLAIM_CLASS_DIRECTLY_VERIFIED)

        add_help_script_scene(
            self.store, script_id=script["id"], text="Human prose.", actor="reviewer",
            claim_ids=[claim["id"]])
        scene = self._scenes(script["id"])[0]
        self.assertEqual(scene["content_class"], CONTENT_CLASS_HUMAN_AUTHORED)

    # -- the ungrounded abstention keeps its honest shape ------------------

    def test_an_ungrounded_generated_claim_is_an_ai_authored_abstention(self):
        result = self._generate(payload=self._payload(["not-a-real-evidence-id"]))
        claims = self._script_claims(result["script_id"])
        self.assertTrue(claims)
        for claim in claims:
            self.assertEqual(claim["claim_class"], CLAIM_CLASS_UNKNOWN)
            self.assertEqual(claim["author_type"], OBSERVATION_AUTHOR_AI)
            self.assertEqual(claim["evidence_links"], [])

    # -- the sweep that would have caught it -------------------------------

    def test_no_generated_object_anywhere_carries_human_provenance(self):
        """A whole-workspace sweep rather than a per-field check.

        The original defect was invisible per-call - every individual argument
        looked reasonable, and only the STORED RESULT was wrong. This asserts
        against what actually landed.
        """
        result = self._generate()
        ws = self._library()
        step = self.store.get_work_product(ws, result["script_id"])["source_investigation_step_id"]

        for claim in ws.claims:
            if claim.get("investigation_step_id") == step:
                self.assertNotEqual(claim["author_type"], OBSERVATION_AUTHOR_HUMAN)
        script = self.store.get_work_product(ws, result["script_id"])
        for section in script["sections"]:
            if section["section_type"] == "scene" and not section["removed"]:
                self.assertNotEqual(section["content_class"], CONTENT_CLASS_HUMAN_AUTHORED)


if __name__ == "__main__":
    unittest.main()
