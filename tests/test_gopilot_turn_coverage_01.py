"""GOPILOT CORE step 1B - every canonical Composer turn is labelled.

Every endpoint the ONE canonical Composer can post to (app.py resolve_go_scope)
now labels its turn through the ONE path, routes/portal.gopilot_turn_labels:
services/turn_frame.build_turn_frame + services/conversation_interpreter.
classify_intent_envelope. Labels only. Each endpoint labels AFTER its own gates
and ignores the result, so these tests prove two things per endpoint: the turn
carries {frame, intent}, and the person sees exactly what they saw before -
proved by re-running the same request with labelling switched off.
"""
from __future__ import annotations

import inspect
import io
import re
import shutil
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import routes.portal as portal
from services import llm_gateway

ROOT = Path(__file__).resolve().parent.parent

# Every endpoint resolve_go_scope can point the canonical Composer at.
CANONICAL_COMPOSER_ENDPOINTS = {
    "portal.gateway_orientation", "portal.developer_home_composer",
    "portal.document_shop_result", "portal.document_shop_bulk",
    "workspace.quick_start", "workspace.post_message",
    "planning_zoning.converse_study",
    "sandbox.turn",   # MORPHOSIS SLICE 1
}

SAME_WORDS = "Draft an RFI for the stair"


@contextmanager
def capture_labels():
    """Record every label the ONE labelling path produces (it still runs)."""
    seen = []
    original = portal.gopilot_turn_labels

    def spy(scope_kind, text, **kwargs):
        labels = original(scope_kind, text, **kwargs)
        seen.append({"scope_kind": scope_kind, "text": text, "kwargs": kwargs, "labels": labels})
        return labels

    with patch.object(portal, "gopilot_turn_labels", spy):
        yield seen


@contextmanager
def labelling_off():
    with patch.object(portal, "gopilot_turn_labels", lambda *a, **k: None):
        yield


class NoCanonicalComposerEndpointIsUnlabelled(unittest.TestCase):
    """Structural convergence: a new Composer endpoint that skips the labelling
    path fails here, and so does a second classifier."""

    def test_resolve_go_scope_targets_exactly_the_known_endpoints(self):
        source = (ROOT / "app.py").read_text(encoding="utf-8")
        body = source[source.index("def resolve_go_scope("):source.index("def _GENERATED_ORIGIN_TYPES")]
        found = set(re.findall(r'post_url=url_for\("([a-z_]+\.[a-z_]+)"', body))
        self.assertEqual(found, CANONICAL_COMPOSER_ENDPOINTS)

    def test_every_canonical_endpoint_reaches_the_one_labelling_path(self):
        from app import create_app
        import routes.workspace as ws

        app = create_app("testing")
        turn = inspect.getsource(ws._run_conversation_turn)
        photo = inspect.getsource(ws._composer_photo_turn)
        self.assertIn("_gopilot_turn_labels(", turn)
        self.assertIn("_gopilot_turn_labels(", photo)
        self.assertIn("gopilot_turn_labels(", inspect.getsource(ws._gopilot_turn_labels))
        for endpoint in sorted(CANONICAL_COMPOSER_ENDPOINTS):
            with self.subTest(endpoint=endpoint):
                view = inspect.getsource(app.view_functions[endpoint])
                if endpoint.startswith("workspace."):
                    self.assertIn("_run_conversation_turn(", view)
                    self.assertIn("_composer_photo_turn(", view)
                else:
                    self.assertIn("gopilot_turn_labels(", view)

    def test_there_is_one_classifier_and_one_caller(self):
        calls, definitions = [], []
        for path in list((ROOT / "routes").glob("*.py")) + list((ROOT / "services").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            definitions += [path.name] * len(re.findall(r"^def classify_intent_envelope\(", text, re.M))
            calls += [path.name] * len(re.findall(r"(?<!def )classify_intent_envelope\(", text))
        self.assertEqual(definitions, ["conversation_interpreter.py"])
        self.assertEqual(calls, ["portal.py"])


def _fake_parse(_self, raw, filename):
    from services.bhive_parser import ParsedDocument

    return ParsedDocument(project_id=str(uuid.uuid4()), filename=filename,
                          ingested_at=datetime.now(timezone.utc).isoformat(),
                          parser_version="test", text_extraction_status="no_native_text")


class _Outcome:
    """Shaped like llm_gateway's own result (as test_document_shop_conversation_01's)."""

    def __init__(self, ran=True, parsed=None, skipped_reason=None):
        self.ran, self.parsed, self.skipped_reason = ran, parsed, skipped_reason
        self.raw_text, self.stop_reason, self.provider, self.model = None, None, "test", "test"


class _App(unittest.TestCase):
    PW = "Cover!2026x"

    def setUp(self):
        from app import create_app
        from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
        from werkzeug.security import generate_password_hash

        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_turn_cover_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("cover_boss", ROLE_ADMIN), ("cover_cust", ROLE_CUSTOMER)):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=role)
                user.password_hash = generate_password_hash(self.PW)
                db.session.add(user)
        db.session.commit()

    def tearDown(self):
        from models import db

        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, name):
        c = self.app.test_client()
        c.post("/login", data={"username": name, "password": self.PW})
        return c

    def upload(self, c, name):
        from PIL import Image
        from services.bhive_parser import BHiveParser

        buf = io.BytesIO()
        Image.new("RGB", (40, 30)).save(buf, "JPEG")
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = c.post("/document-shop", data={"file": (io.BytesIO(buf.getvalue()), "a.jpg"),
                                               "name": name}, content_type="multipart/form-data")
        return r.headers["Location"].rstrip("/").split("/")[-1]

    def last_reply(self, pid, case_id=None):
        from services.case_workspace import CaseWorkspaceStore

        workspace = CaseWorkspaceStore(str(self.tmp)).get(pid)
        messages = (next(c for c in workspace.cases if c["id"] == case_id)["conversation"]
                    if case_id else workspace.project_conversation)
        return [m["text"] for m in messages if m["role"] == "system"][-1]


class EveryEndpointCarriesAFrameAndAnIntent(_App):
    """1, 2, 3 and 8 - a frame and an intent on every endpoint; the same words
    get the same intent everywhere; and the person sees what they saw before."""

    def _label(self, seen):
        self.assertEqual(len(seen), 1, seen)
        labels = seen[0]["labels"]
        self.assertIsNotNone(labels, "the turn was not labelled")
        self.assertIn("current_envelope", labels["frame"])
        self.assertIn("envelope", labels["intent"])
        return labels

    def test_gateway_orientation_both_branches(self):
        boss = self.client("cover_boss")
        with patch.object(portal, "answer_orientation_question", return_value=None):
            for data in ({"message": SAME_WORDS}, {"message": SAME_WORDS, "context": "establish-project"}):
                with self.subTest(context=data.get("context", "orientation")):
                    with capture_labels() as seen:
                        on = boss.post("/gateway/orientation", data=data).get_data()
                    labels = self._label(seen)
                    self.assertEqual(labels["frame"]["current_envelope"], "APPLICATION")
                    self.assertEqual(labels["intent"]["envelope"], "INVESTIGATION_STUDY")
                    with labelling_off():
                        off = boss.post("/gateway/orientation", data=data).get_data()
                    self.assertEqual(on, off)

    def test_workspace_case_turn(self):
        from services.case_workspace import CaseWorkspaceStore

        boss = self.client("cover_boss")
        pid = self.upload(boss, "Cover Project")
        store = CaseWorkspaceStore(str(self.tmp))
        case = store.create_case(store.get(pid), "RFI case", "objective", created_by="cover_boss")
        url = "/projects/%s/workspace/cases/%s/messages" % (pid, case["id"])
        with capture_labels() as seen:
            on = boss.post(url, data={"text": SAME_WORDS})
        labels = self._label(seen)
        self.assertEqual(labels["frame"]["current_envelope"], "INVESTIGATION_STUDY")
        self.assertEqual(labels["intent"]["envelope"], "INVESTIGATION_STUDY")
        reply_on = self.last_reply(pid, case["id"])
        with labelling_off():
            off = boss.post(url, data={"text": SAME_WORDS})
        self.assertEqual((on.status_code, on.headers["Location"]), (off.status_code, off.headers["Location"]))
        self.assertEqual(reply_on, self.last_reply(pid, case["id"]))

    def test_document_shop_document_conversation(self):
        boss = self.client("cover_boss")
        pid = self.upload(boss, "Cover Document")
        url = "/document-shop/jobs/%s" % pid
        with patch.object(llm_gateway, "call_llm_json", lambda **k: _Outcome(parsed={"answer": "stub"})):
            with capture_labels() as seen:
                on = boss.post(url, data={"question": SAME_WORDS})
            with labelling_off():
                off = boss.post(url, data={"question": SAME_WORDS})
        labels = self._label(seen)
        self.assertEqual(labels["frame"]["current_envelope"], "DOCUMENT_SOURCE")
        self.assertEqual(labels["frame"]["context_ids"]["project_id"], pid)
        self.assertEqual(labels["intent"]["envelope"], "INVESTIGATION_STUDY")
        self.assertEqual((on.status_code, on.headers.get("Location")), (off.status_code, off.headers.get("Location")))

    def test_my_documents_selection_command(self):
        boss = self.client("cover_boss")
        pid = self.upload(boss, "Cover Desk")
        data = {"action": "command", "command_text": SAME_WORDS, "project_id": pid,
                "request_id": uuid.uuid4().hex}
        with capture_labels() as seen:
            on = boss.post("/document-shop/bulk", data=data)
        labels = self._label(seen)
        self.assertEqual(labels["frame"]["current_envelope"], "APPLICATION")
        self.assertEqual(labels["frame"]["context_ids"], {"selection_form": "document-bulk"})
        self.assertEqual(labels["intent"]["envelope"], "INVESTIGATION_STUDY")
        with labelling_off():
            off = boss.post("/document-shop/bulk", data=dict(data, request_id=uuid.uuid4().hex))
        self.assertEqual((on.status_code, on.headers.get("Location")), (off.status_code, off.headers.get("Location")))

    def test_developer_composer(self):
        boss = self.client("cover_boss")
        boss.post("/developer-mode/toggle")
        with patch.object(portal, "_developer_model_reply", return_value=("stub", {})):
            with capture_labels() as seen:
                on = boss.post("/developer-composer", data={"message": SAME_WORDS})
            with labelling_off():
                off = boss.post("/developer-composer", data={"message": SAME_WORDS})
        labels = self._label(seen)
        self.assertEqual(labels["frame"]["current_envelope"], "DEVELOPER_INSPECT")
        self.assertEqual(labels["intent"]["envelope"], "INVESTIGATION_STUDY")
        self.assertEqual((on.status_code, on.headers["Location"]), (off.status_code, off.headers["Location"]))


class GatewayNavigationIsByteForByte(_App):
    """7 - the Gateway's own replies are unchanged, byte for byte."""

    def test_navigation_new_project_and_capability_replies(self):
        boss = self.client("cover_boss")
        pid = self.upload(boss, "Harbour Tower")
        from services.case_workspace import CaseWorkspaceStore
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        workspace.container_state = "programmed"
        store.save(workspace)
        with patch.object(portal, "answer_orientation_question", return_value=None):
            for message in ("Harbour Tower", "open harbour tower", "new project",
                            "can you compare drawings?", "take me to the help centre", ""):
                with self.subTest(message=message):
                    with capture_labels() as seen:
                        on = boss.post("/gateway/orientation", data={"message": message}).get_data()
                    with labelling_off():
                        off = boss.post("/gateway/orientation", data={"message": message}).get_data()
                    self.assertEqual(on, off)
                    self.assertEqual(len(seen), 1)
        navigate = boss.post("/gateway/orientation", data={"message": "Harbour Tower"}).get_json()
        self.assertEqual(set(navigate), {"kind", "url", "text"})   # no project_id leaks into it


class ContainmentAndAuthorityHold(_App):
    def test_4_customer_containment_is_intact(self):
        cust = self.client("cover_cust")
        pid = self.upload(cust, "Customer Doc")
        with patch.object(llm_gateway, "call_llm_json", lambda **k: _Outcome(parsed={"answer": "stub"})):
            with capture_labels() as seen:
                cust.post("/document-shop/jobs/%s" % pid, data={"question": SAME_WORDS})
        frame, intent = seen[0]["labels"]["frame"], seen[0]["labels"]["intent"]
        self.assertEqual(frame["current_envelope"], "CUSTOMER_DOCUMENT_SHOP")
        self.assertEqual(frame["envelope_set"], ["APPLICATION", "CUSTOMER_DOCUMENT_SHOP"])
        self.assertEqual(intent["envelope"], "INVESTIGATION_STUDY")
        self.assertFalse(intent["authorized"])       # labelled truthfully, never widened
        # The customer's existing redirect away from the staff directory is unchanged.
        self.assertEqual(cust.get("/projects").status_code, 302)
        # And a customer cannot label a turn on someone else's document at all:
        boss = self.client("cover_boss")
        other = self.upload(boss, "Staff Doc")
        with capture_labels() as seen:
            self.assertEqual(cust.post("/document-shop/jobs/%s" % other,
                                       data={"question": SAME_WORDS}).status_code, 404)
        self.assertEqual(seen, [])

    def test_5_developer_composer_cannot_acquire_project_authority_from_the_label(self):
        boss = self.client("cover_boss")
        pid = self.upload(boss, "Harbour Tower")
        boss.post("/developer-mode/toggle")
        with patch.object(portal, "_developer_model_reply", return_value=("stub", {})):
            with capture_labels() as seen:
                boss.post("/developer-composer", data={"message": "What is open on Harbour Tower?"})
            with capture_labels() as refused:
                status = boss.post("/developer-composer",
                                   data={"message": "What is open on Harbour Tower?",
                                         "project_id": pid}).status_code
        frame = seen[0]["labels"]["frame"]
        self.assertEqual(frame["current_envelope"], "DEVELOPER_INSPECT")
        self.assertEqual(frame["context_ids"], {})          # no project enters its frame
        self.assertEqual(status, 400)                       # its own gate still refuses a project
        self.assertEqual(refused, [])                       # and a refused turn is never labelled


class NoSecondClassifierPhraseTables(unittest.TestCase):
    def test_the_deictic_table_exists_once(self):
        hits = [p.name for p in list((ROOT / "routes").glob("*.py")) + list((ROOT / "services").glob("*.py"))
                if "_SOURCE_DEICTIC_PHRASES = (" in p.read_text(encoding="utf-8")]
        self.assertEqual(hits, ["conversation_interpreter.py"])


# -- 6: Planning Study - pytest, reusing the planning export fixture ---------
import pytest  # noqa: E402

from tests.test_planning_word_export_405 import setup_export, sign_in  # noqa: E402,F401
from tests.test_planning_composer import turn  # noqa: E402


def test_6_planning_study_stays_bound_to_its_study_and_project(setup_export):
    from services import planning_composer as composer, planning_studies as studies

    app, store, result, _ = setup_export
    client = sign_in(app)
    working = studies.WorkingResults(store.store_path)
    key = working.put("p", "export-planner", composer.initialize([result]))
    allow = SimpleNamespace(decision="allow")
    with patch("services.conversation_interpreter._evaluate_external_ai_policy", return_value=allow), \
            patch("services.conversational_turn.run_conversational_turn", return_value=turn({"kind": "scenario"})):
        with capture_labels() as seen:
            on = client.post(f"/planning-zoning/projects/p/working/{key}/conversation",
                             data={"text": SAME_WORDS})
    assert on.status_code == 302
    frame, intent = seen[0]["labels"]["frame"], seen[0]["labels"]["intent"]
    assert frame["current_envelope"] == "INVESTIGATION_STUDY"
    assert frame["context_ids"] == {"project_id": "p", "run_id": key}
    assert intent["envelope"] == "INVESTIGATION_STUDY" and intent["context_resolved"]
    # A study belonging to another project is refused by its own gate, unlabelled.
    foreign = working.put("other", "export-planner", composer.initialize([result]))
    with patch("services.conversational_turn.run_conversational_turn") as go:
        with capture_labels() as refused:
            status = client.post(f"/planning-zoning/projects/p/working/{foreign}/conversation",
                                 data={"text": SAME_WORDS}).status_code
    assert status == 409 and refused == [] and not go.called


if __name__ == "__main__":
    unittest.main()
