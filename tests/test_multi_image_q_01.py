"""
CLAUDE-MULTI-IMAGE-Q-01 - a Q accumulates materials.

Product Owner: "I authorize Q / Investigation to support multiple images and
other investigation materials as one governed container. Preserve provenance for
each item and do not automatically turn every attachment into authoritative
project evidence."

WHAT THIS STAGE ACTUALLY CHANGED, AND WHAT IT DID NOT

It did not build a container. `case["source_ids"]` has always been a list and
`attach_source_to_case` has always appended to it - a Q could hold many sources
on the day it was written. Nothing ever added a second one, because the only
path that saved a photo was "make a new Q", which by definition made a new Q
every time.

So the change is a missing VERB, not a new noun: a way to say "keep this one, in
the Q I am already in". These tests are written around that distinction, because
it is the thing most likely to be misunderstood later and rebuilt as a parallel
attachment system.

THE DEFAULT REMAINS NOT SAVING. A photo sent without asking is answered and
discarded. That is the Product Owner's own "do not automatically turn every
attachment into authoritative project evidence" and it is asserted here as
hard as the positive case, because it is the half that erodes quietly.

Hermetic: the vision call is spied, never made. An un-mocked call on this path
once cost this repository an 8.5-hour test run.
"""
from __future__ import annotations

import base64
import io
import re
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKSPACE_ROUTES = _REPO_ROOT / "routes" / "workspace.py"
_MACROS = _REPO_ROOT / "templates" / "_macros.html"
_ATTACH_JS = _REPO_ROOT / "static" / "js" / "composer_attach.js"

# A real 1x1 PNG - small enough to be trivial, real enough to be decodable.
_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmM"
    "IQAAAABJRU5ErkJggg=="
)
_DATA_URL = "data:image/png;base64," + _PNG_B64


class _QTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        import tempfile
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_multi_image_q_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        with self.flask_app.app_context():
            db.session.add(User(username="q_owner",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest()
        self.project_id = self.doc.project_id
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "q_owner"
            sess["role"] = "admin"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    FileStorage(stream=io.BytesIO(b"c"), filename="rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="q_owner",
                    project_name="Multi Image Q Project",
                )

    def _store(self):
        return CaseWorkspaceStore(self.tmp_dir)

    def _send_photo(self, text, case_id=None):
        """One composer turn carrying a photo, hermetically.

        CLAUDE-COMPOSER-EVIDENCE-JOIN-01: the photo turn now reasons through the
        shared conversational spine, so the double patches
        `services.conversational_turn.call_llm_json` - the BOUND name in the
        module that calls it. Patching `services.llm_gateway.call_llm_json`
        would no longer intercept anything, because that module binds the symbol
        at import time; this test would have gone silently un-hermetic, which is
        the failure mode that once cost this repository an 8.5-hour run.

        Candidate naming keeps its own patch: `_propose_capture_names` imports
        inside the function, so it resolves through services.llm_gateway at call
        time.
        """
        from services.llm_gateway import LLMCallOutcome

        def fake_turn(**kwargs):
            # The SPINE's schema now, not the retired {reply, proposed_names}.
            return LLMCallOutcome(
                ran=True,
                parsed={
                    "reply_text": "A wall junction.",
                    "intent_class": "general_answer",
                    "candidate_referents": [],
                },
            )

        def fake_names(**kwargs):
            return LLMCallOutcome(ran=True, parsed={"proposed_names": ["Wall Junction Detail"]})

        # Two real entry points, deliberately exercised as the product does:
        # quick-start is the project-level Composer (no Q open yet), and
        # cases/<id>/messages is the Composer inside an open Q.
        if case_id:
            url = f"/projects/{self.project_id}/workspace/cases/{case_id}/messages"
        else:
            url = f"/projects/{self.project_id}/workspace/quick-start"
        data = {"text": text, "image_data_url": _DATA_URL}
        with patch("services.conversational_turn.call_llm_json", side_effect=lambda **kw: fake_turn(**kw)), \
                patch("services.llm_gateway.call_llm_json", side_effect=lambda **kw: fake_names(**kw)):
            return self.client.post(url, data=data, follow_redirects=True)

    def _case(self, case_id):
        workspace = self._store().get(self.project_id)
        return next((c for c in workspace.cases if c["id"] == case_id), None)


class TheContainerAlreadyExistedTests(unittest.TestCase):
    """Guard the architectural fact, so nobody builds a parallel one later."""

    def test_a_case_holds_a_list_of_sources_not_a_single_one(self):
        source = (_REPO_ROOT / "services" / "case_workspace.py").read_text(encoding="utf-8")
        attach = source[source.index("def attach_source_to_case"):]
        attach = attach[:attach.index("\n    def ")]
        self.assertIn('case["source_ids"].append(source_id)', attach)
        # Deduplicated, so the same photo twice does not double-count.
        self.assertIn("if source_id not in", attach)

    def test_no_parallel_attachment_collection_was_introduced(self):
        routes = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        for invented in ("q_images", "case_images", "investigation_materials", "attachments ="):
            self.assertNotIn(invented, routes, invented)

    def test_adding_reuses_the_governed_capture_path(self):
        # register_eye_capture is the EXIF-stripping, GPS-presence-only pathway
        # that "make a new Q" already used. A second photo must not arrive by a
        # weaker route than the first.
        routes = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        turn = routes[routes.index("def _composer_photo_turn"):]
        turn = turn[:turn.index("\n@workspace_bp.route")]
        # Both save paths - "make a new Q" and "add to this Q" - import and
        # call it. What matters is that neither writes an image by any other
        # route, not the exact literal count.
        self.assertGreaterEqual(turn.count("register_eye_capture"), 4)
        self.assertNotIn("open(", turn)
        self.assertNotIn("write_bytes", turn)


class AddingToTheCurrentQTests(_QTestCase):
    def test_a_second_photo_is_kept_in_the_same_q(self):
        self._send_photo("Make a new Q")
        workspace = self._store().get(self.project_id)
        self.assertEqual(len(workspace.cases), 1)
        case_id = workspace.cases[0]["id"]
        first_count = len(self._case(case_id)["source_ids"])

        self._send_photo("Add this to this Q", case_id=case_id)
        self.assertEqual(len(self._case(case_id)["source_ids"]), first_count + 1)

    def test_adding_does_not_create_another_q(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        self._send_photo("Add this to this Q", case_id=case_id)
        self.assertEqual(len(self._store().get(self.project_id).cases), 1)

    def test_several_materials_accumulate_in_one_q(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        for phrase in ("Add this to this Q", "another angle", "keep this"):
            self._send_photo(phrase, case_id=case_id)
        self.assertGreaterEqual(len(self._case(case_id)["source_ids"]), 4)

    def test_the_reviewer_is_told_it_was_kept(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        self._send_photo("Add this to this Q", case_id=case_id)
        messages = self._case(case_id)["conversation"]
        self.assertTrue(any("Kept in this investigation" in (m.get("text") or "")
                            for m in messages))


class NotEveryAttachmentBecomesEvidenceTests(_QTestCase):
    """The half that erodes quietly, asserted as hard as the positive case."""

    def test_an_ordinary_photo_question_saves_nothing(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        before = len(self._case(case_id)["source_ids"])

        self._send_photo("What is this?", case_id=case_id)
        self.assertEqual(len(self._case(case_id)["source_ids"]), before)

    def test_saving_is_read_from_the_reviewers_own_words_not_inferred(self):
        routes = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        self.assertIn("_ADD_TO_Q_PHRASES", routes)
        # A phrase list, not a model call: nothing asks an LLM whether to persist.
        recogniser = routes[routes.index("def _asked_to_add_to_this_investigation"):]
        recogniser = recogniser[:recogniser.index("\n\n")]
        self.assertNotIn("call_llm", recogniser)

    def test_a_saved_item_is_a_source_not_a_finding(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        self._send_photo("Add this to this Q", case_id=case_id)
        workspace = self._store().get(self.project_id)
        # Nothing here creates a Finding - saving material is not concluding.
        self.assertEqual(workspace.findings, [])

    def test_add_outside_a_q_cannot_invent_one(self):
        # "Add this to this Q" from the project conversation has no "this Q" to
        # mean. It must answer, not silently create or attach.
        self._send_photo("Add this to this Q")
        self.assertEqual(len(self._store().get(self.project_id).cases), 0)


class ProvenanceIsPreservedPerItemTests(_QTestCase):
    def test_each_saved_item_records_its_own_actor_and_description(self):
        self._send_photo("Make a new Q")
        case_id = self._store().get(self.project_id).cases[0]["id"]
        self._send_photo("Add this to this Q - north elevation", case_id=case_id)

        workspace = self._store().get(self.project_id)
        source_ids = self._case(case_id)["source_ids"]
        sources = {s.get("id"): s for s in workspace.sources}
        kept = [sources[sid] for sid in source_ids if sid in sources]
        self.assertGreaterEqual(len(kept), 2, "the Q did not accumulate two sources")

        # Each item is a real Source in its own right - not an anonymous blob
        # hanging off the Q.
        for source in kept:
            self.assertTrue(source.get("id"))

        # The words the reviewer sent it with are preserved as a separate
        # USER-ENTERED evidence item anchored to the Source, NOT as a field on
        # the Source. That is register_eye_capture's own model and it is
        # stronger than a description string: what a person typed is evidence
        # with its own class and provenance, distinguishable from anything the
        # machine produced about the same image.
        from services.case_workspace import EVIDENCE_CLASS_USER_ENTERED

        kept_ids = {s.get("id") for s in kept}
        user_entered = [
            item for item in workspace.evidence_items
            if item.get("evidence_class") == EVIDENCE_CLASS_USER_ENTERED
            and item.get("source_id") in kept_ids
        ]
        self.assertTrue(user_entered, "no user-entered evidence recorded for the kept items")
        texts = " ".join(str(item.get("content") or item.get("text") or "") for item in user_entered)
        self.assertIn("north elevation", texts)


class TheAffordanceTests(unittest.TestCase):
    def setUp(self):
        self.macros = _MACROS.read_text(encoding="utf-8")
        self.js = _ATTACH_JS.read_text(encoding="utf-8")

    def test_the_button_exists_only_inside_an_open_q(self):
        block = self.macros[self.macros.index("dock-composer-add-to-q") - 900:]
        block = block[:block.index("dock-composer-add-to-q") + 200]
        self.assertIn("{% if case_id %}", block)

    def test_the_button_sends_a_phrase_the_server_actually_recognises(self):
        phrase = re.search(r"sendAs\('(Add this to this Q)'\)", self.js)
        self.assertIsNotNone(phrase, "button does not send a recognised phrase")
        routes = _WORKSPACE_ROUTES.read_text(encoding="utf-8")
        phrases = routes[routes.index("_ADD_TO_Q_PHRASES = ("):]
        phrases = phrases[:phrases.index(")")]
        self.assertIn(phrase.group(1).lower(), phrases)

    def test_the_button_is_a_shortcut_to_words_not_a_second_mechanism(self):
        # It fills the message box and submits the ordinary form - no separate
        # endpoint, so a typed phrase and a tap travel the identical path.
        self.assertIn("messageBox.value = phrase", self.js)
        self.assertNotIn("fetch(", self.js)

    def test_both_actions_share_one_submit_helper(self):
        self.assertEqual(self.js.count("function sendAs("), 1)
        self.assertEqual(self.js.count("sendAs("), 3)  # definition + two callers


if __name__ == "__main__":
    unittest.main()
