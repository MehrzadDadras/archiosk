"""GOPILOT CORE step 1 - turn frame + intent envelope. Routing proof only.

    credential -> envelope_set -> current_envelope -> context_ids -> intent_envelope

Nothing here activates an action, changes a reply or changes a route. The frame
is data carried with the scope (app.py resolve_go_scope) and with a Composer turn
(routes/workspace.py _run_conversation_turn); the intent envelope is a label
from services/conversation_interpreter.classify_intent_envelope. These tests
prove the labels, and that attaching them changed nothing a person sees.
"""
from __future__ import annotations

import io
import shutil
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from services.conversation_interpreter import (
    INTENT_ENVELOPE_APPLICATION,
    INTENT_ENVELOPE_DOCUMENT_SOURCE,
    INTENT_ENVELOPE_INVESTIGATION_STUDY,
    INTENT_ENVELOPE_MIXED,
    INTENT_ENVELOPE_PROJECT,
    INTENT_ENVELOPE_UNKNOWN,
    classify_intent_envelope,
)
from services.master_commands import application_destinations
from services.turn_frame import envelope_set_for

STAFF = sorted(envelope_set_for(authenticated=True, customer=False, developer=False))
CUSTOMER = sorted(envelope_set_for(authenticated=True, customer=True, developer=False))


def frame(current, envelope_set=STAFF, **context):
    return {"credential": "session", "envelope_set": envelope_set,
            "current_envelope": current, "context_ids": context}


DOCUMENT_PAGE = frame("DOCUMENT_SOURCE", project_id="p1", selected_source_id="s1")
HELP_PAGE = frame("APPLICATION")
CASE_PAGE = frame("INVESTIGATION_STUDY", project_id="p1", case_id="c1")


def classify(text, page, target=None):
    return classify_intent_envelope(text, page, navigation_target=target,
                                    application_destinations=application_destinations())


class IntentEnvelopeRouting(unittest.TestCase):
    """The six required cases, each labelled independently of the page."""

    def test_document_page_take_me_to_help_centre_is_application(self):
        label = classify("Take me to Help Centre", DOCUMENT_PAGE)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_APPLICATION)
        self.assertEqual(label["destination"], "help.centre")
        self.assertTrue(label["authorized"])

    def test_help_plus_a_named_accessible_project_question_is_project(self):
        # The target comes from the Gateway's access-scoped navigation rule.
        label = classify("What is still open on Harbour Tower?", HELP_PAGE,
                         target={"kind": "navigate", "project_id": "p-harbour"})
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_PROJECT)
        self.assertEqual(label["target_project_id"], "p-harbour")
        self.assertTrue(label["authorized"])
        self.assertTrue(label["context_resolved"])

    def test_case_plus_issue_this_rfi_is_investigation_study(self):
        label = classify("Issue this RFI", CASE_PAGE)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_INVESTIGATION_STUDY)
        self.assertTrue(label["context_resolved"])

    def test_document_plus_what_does_this_say_is_document_source(self):
        label = classify("What does this say?", DOCUMENT_PAGE)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_DOCUMENT_SOURCE)
        self.assertTrue(label["context_resolved"])

    def test_navigation_plus_a_project_action_is_mixed(self):
        label = classify("Take me to Help Centre and issue this RFI", CASE_PAGE)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_MIXED)
        self.assertEqual(label["parts"], [INTENT_ENVELOPE_APPLICATION,
                                          INTENT_ENVELOPE_INVESTIGATION_STUDY])

    def test_ambiguous_input_is_unknown(self):
        for text in ("maybe later", "blue", "hmm", ""):
            with self.subTest(text=text):
                label = classify(text, DOCUMENT_PAGE)
                self.assertEqual(label["envelope"], INTENT_ENVELOPE_UNKNOWN)
                self.assertFalse(label["authorized"])

    def test_a_question_about_archiosk_itself_is_application(self):
        for text in ("What can ARCHIOSK do?", "Does ARCHIOSK support IFC files?"):
            with self.subTest(text=text):
                self.assertEqual(classify(text, HELP_PAGE)["envelope"], INTENT_ENVELOPE_APPLICATION)
        # A polite instruction is still an instruction, not a capability question.
        self.assertEqual(classify("Can you compare these two drawings?", CASE_PAGE)["envelope"],
                         INTENT_ENVELOPE_INVESTIGATION_STUDY)
        # And "can you" about the open Source stays with the Source.
        self.assertEqual(classify("Can you explain this?", DOCUMENT_PAGE)["envelope"],
                         INTENT_ENVELOPE_DOCUMENT_SOURCE)

    def test_the_label_does_not_follow_the_page(self):
        """Page location is context, never authority: the same words get the
        same envelope on every page."""
        for page in (DOCUMENT_PAGE, HELP_PAGE, CASE_PAGE):
            with self.subTest(page=page["current_envelope"]):
                self.assertEqual(classify("Take me to Help Centre", page)["envelope"],
                                 INTENT_ENVELOPE_APPLICATION)
                self.assertEqual(classify("Draft an RFI for the stair", page)["envelope"],
                                 INTENT_ENVELOPE_INVESTIGATION_STUDY)

    def test_authority_comes_from_the_credential_not_the_intent(self):
        """A customer asking an investigation question is labelled truthfully and
        is NOT authorized - the classifier never widens a credential to fit."""
        page = frame("CUSTOMER_DOCUMENT_SHOP", envelope_set=CUSTOMER, project_id="d1")
        label = classify("Issue this RFI", page)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_INVESTIGATION_STUDY)
        self.assertFalse(label["authorized"])
        self.assertTrue(classify("What does this say?", page)["authorized"])

    def test_project_intent_without_a_project_is_unresolved_not_invented(self):
        label = classify("What is the status?", HELP_PAGE)
        self.assertEqual(label["envelope"], INTENT_ENVELOPE_PROJECT)
        self.assertIsNone(label["target_project_id"])
        self.assertFalse(label["context_resolved"])


class ApplicationDestinationsComeFromTheRegistry(unittest.TestCase):
    def test_help_centre_is_a_no_project_destination_and_project_commands_are_not(self):
        ids = {d["id"] for d in application_destinations()}
        self.assertIn("help.centre", ids)
        from services.master_commands import COMMANDS, NEED_PROJECT
        from services.master_commands import Ctx
        empty = Ctx(identity={}, endpoint="", args={}, admin=False, developer=False,
                    customer=False, username=None)
        for command in COMMANDS:
            if command.needs and command.href is not None:
                try:
                    reason = command.needs(empty)
                except Exception:
                    continue
                if reason == NEED_PROJECT:
                    with self.subTest(command=command.id):
                        self.assertNotIn(command.id, ids)


def _fake_parse(_self, raw, filename):
    from services.bhive_parser import ParsedDocument

    return ParsedDocument(project_id=str(uuid.uuid4()), filename=filename,
                          ingested_at=datetime.now(timezone.utc).isoformat(),
                          parser_version="test", text_extraction_status="no_native_text")


class _App(unittest.TestCase):
    PW = "Frame!2026x"

    def setUp(self):
        from app import create_app
        from models import ROLE_ADMIN, ROLE_CUSTOMER, User, db
        from werkzeug.security import generate_password_hash

        self.app = create_app("testing")
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_turn_frame_"))
        self.app.config["REGISTRY_STORE_PATH"] = str(self.tmp)
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()
        for name, role in (("frame_boss", ROLE_ADMIN), ("frame_reader", "read_only"),
                           ("frame_cust", ROLE_CUSTOMER)):
            if not User.query.filter_by(username=name).first():
                user = User(username=name, role=role)
                user.password_hash = generate_password_hash(self.PW)
                db.session.add(user)
        db.session.commit()
        self.users = {u.username: u for u in User.query.all()}

    def tearDown(self):
        from models import db

        db.session.remove()
        self.ctx.pop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def client(self, name):
        c = self.app.test_client()
        c.post("/login", data={"username": name, "password": self.PW})
        return c

    def project(self, c, name):
        from PIL import Image
        from services.bhive_parser import BHiveParser
        from services.case_workspace import CaseWorkspaceStore

        buf = io.BytesIO()
        Image.new("RGB", (40, 30)).save(buf, "JPEG")
        with patch.object(BHiveParser, "parse", _fake_parse):
            r = c.post("/document-shop", data={"file": (io.BytesIO(buf.getvalue()), "a.jpg"),
                                               "name": name}, content_type="multipart/form-data")
        pid = r.headers["Location"].rstrip("/").split("/")[-1]
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(pid)
        workspace.container_state = "programmed"   # an ordinary project
        store.save(workspace)
        return pid

    def as_user(self, name, **extra):
        from flask import session

        user = self.users[name]
        rc = self.app.test_request_context("/projects")
        rc.push()
        session["user_id"], session["username"], session["role"] = user.id, user.username, user.role
        session.update(extra)
        return rc


class TheFrameComesFromTheCredential(_App):
    def test_staff_customer_and_developer_envelope_sets(self):
        from services.turn_frame import build_turn_frame

        for name, extra, kind, expected_current, has_developer in (
                ("frame_reader", {}, "DOCUMENT", "DOCUMENT_SOURCE", False),
                ("frame_cust", {}, "DOCUMENT", "CUSTOMER_DOCUMENT_SHOP", False),
                ("frame_boss", {"developer_mode": True}, "APPLICATION", "DEVELOPER_INSPECT", True)):
            with self.subTest(user=name):
                rc = self.as_user(name, **extra)
                try:
                    built = build_turn_frame(kind, developer_scope=has_developer,
                                             context={"project_id": "p1"})
                finally:
                    rc.pop()
                self.assertEqual(built["credential"], "session")
                self.assertEqual(built["current_envelope"], expected_current)
                self.assertEqual("DEVELOPER_INSPECT" in built["envelope_set"], has_developer)
                self.assertNotIn("STAKEHOLDER_TOKEN", built["envelope_set"])
                if name == "frame_cust":
                    self.assertNotIn("PROJECT", built["envelope_set"])

    def test_resolve_go_scope_carries_the_frame_without_changing_the_dock(self):
        from app import resolve_go_scope

        rc = self.as_user("frame_boss")
        try:
            scope = resolve_go_scope({})
        finally:
            rc.pop()
        self.assertEqual(scope["kind"], "APPLICATION")
        self.assertEqual(scope["frame"]["current_envelope"], "APPLICATION")
        self.assertNotIn("frame", scope["dock"])   # the rendered Composer is untouched


class AnInaccessibleProjectIsNeverNamed(_App):
    def test_naming_a_project_you_cannot_open_produces_no_target(self):
        from routes.portal import _environment_projects, _gateway_navigation_target
        from services.case_workspace import CaseWorkspaceStore
        from services.ingestion import get_registry

        boss = self.client("frame_boss")
        harbour = self.project(boss, "Harbour Tower")
        zeta = self.project(boss, "Zeta Tower")
        store = CaseWorkspaceStore(str(self.tmp))
        workspace = store.get(harbour)
        workspace.access_allow_list = ["frame_reader"]
        store.save(workspace)

        rc = self.as_user("frame_reader")
        try:
            projects = _environment_projects(get_registry(self.app), store)
            names = {p["display_name"] for p in projects}
            reader_frame = {"credential": "session", "envelope_set": STAFF,
                            "current_envelope": "APPLICATION", "context_ids": {}}
            zeta_label = classify("What is still open on Zeta Tower?", reader_frame,
                                  _gateway_navigation_target("What is still open on Zeta Tower?",
                                                             projects, False))
            harbour_label = classify("What is still open on Harbour Tower?", reader_frame,
                                     _gateway_navigation_target("What is still open on Harbour Tower?",
                                                                projects, False))
        finally:
            rc.pop()
        self.assertIn("Harbour Tower", names)
        self.assertNotIn("Zeta Tower", names)
        # Named, but not openable: no target, and the turn has nothing to act on.
        self.assertIsNone(zeta_label["target_project_id"])
        self.assertNotEqual(zeta_label["target_project_id"], zeta)
        self.assertFalse(zeta_label["context_resolved"])
        # The control: the one the reader CAN open is targeted.
        self.assertEqual(harbour_label["target_project_id"], harbour)


class ATurnCarriesItsLabelsAndNothingElseChanges(_App):
    def test_a_real_case_turn_is_labelled_and_its_reply_is_unchanged(self):
        import routes.workspace as ws
        from services.case_workspace import CaseWorkspaceStore

        boss = self.client("frame_boss")
        pid = self.project(boss, "Labelled Project")
        store = CaseWorkspaceStore(str(self.tmp))
        case = store.create_case(store.get(pid), "RFI case", "objective", created_by="frame_boss")

        captured = []
        original = ws.interpret_message

        def capture(**kwargs):
            result = original(**kwargs)
            captured.append(result)
            return result

        with patch.object(ws, "interpret_message", side_effect=capture):
            boss.post("/projects/%s/workspace/cases/%s/messages" % (pid, case["id"]),
                      data={"text": "Draft an RFI for the stair"})
        self.assertEqual(len(captured), 1)
        result = captured[0]
        self.assertEqual(result.turn_frame["current_envelope"], "INVESTIGATION_STUDY")
        self.assertEqual(result.turn_frame["context_ids"]["case_id"], case["id"])
        self.assertEqual(result.intent_envelope["envelope"], INTENT_ENVELOPE_INVESTIGATION_STUDY)
        # Unchanged: the reply stored is the interpreter's own, exactly.
        conversation = next(c for c in store.get(pid).cases if c["id"] == case["id"])["conversation"]
        self.assertEqual(conversation[-1]["text"], result.reply_text)
        self.assertEqual(conversation[-1]["role"], "system")


if __name__ == "__main__":
    unittest.main()
