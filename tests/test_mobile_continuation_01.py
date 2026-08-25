"""
CLAUDE-MOBILE-CONTINUATION-01 - mobile reaches a boundary, not a dead end.

Product Owner: "Mobile limitation is an intentional product boundary, not
capability loss." A phone asking for work the phone cannot show properly gets
an explanation and one offer to keep it - never a refusal, and never a degraded
half-answer.

THE THREE THINGS THESE TESTS EXIST TO PROTECT

1. DEFERRING IS NOT EXECUTING. A deferred Task records unfinished intent. It is
   not permission, not a queue, and nothing resumes it automatically. The
   Approval Gate that governed the action still governs it afterwards.
2. NO MEANS NOTHING WAS WRITTEN. There is deliberately no server route for
   declining, so "No" cannot create anything - not because a decline endpoint is
   trusted to write nothing, but because no code path exists.
3. THE PROJECT BOUNDARY IS UNCHANGED. A Task lives inside a workspace and is
   reachable only through routes that call can_access_project. A link is not a
   capability.
"""
from __future__ import annotations

import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from services.conversational_turn import (
    CONSEQUENTIAL_INTENT_CLASSES, FULL_WORKSPACE_INTENT_CLASSES,
    INTENT_CLASS_GENERAL_ANSWER, INTENT_CLASS_INVESTIGATE_REQUIREMENT,
    INTENT_CLASS_PROPOSE_APPLY_FINDINGS, INTENT_CLASS_PROPOSE_DRAFT_RFI,
    INTENT_DISPATCH_TABLE, KNOWN_INTENT_CLASSES, requires_full_workspace,
)
from services.conversation_interpreter import (
    SURFACE_MOBILE, _continuation_offer, _continuation_title,
    _should_offer_continuation,
)


class DeviceSuitabilityIsNotAuthority(unittest.TestCase):
    """The Product Owner's decision 5, asserted in both directions rather than
    described. If these two ever collapse into one another, the mechanism has
    silently become 'consequential means desktop-only'."""

    def test_a_safe_intent_can_still_require_the_full_workspace(self):
        # Running an investigation is harmless. Reading its evidence review on a
        # phone is the problem.
        self.assertNotIn(INTENT_CLASS_INVESTIGATE_REQUIREMENT, CONSEQUENTIAL_INTENT_CLASSES)
        self.assertIn(INTENT_CLASS_INVESTIGATE_REQUIREMENT, FULL_WORKSPACE_INTENT_CLASSES)

    def test_a_consequential_intent_can_still_be_fine_on_a_phone(self):
        # It returns a proposal envelope; the Approval Gate governs the commit
        # on whatever surface it happens.
        self.assertIn(INTENT_CLASS_PROPOSE_DRAFT_RFI, CONSEQUENTIAL_INTENT_CLASSES)
        self.assertNotIn(INTENT_CLASS_PROPOSE_DRAFT_RFI, FULL_WORKSPACE_INTENT_CLASSES)

    def test_the_two_axes_are_not_the_same_set(self):
        self.assertNotEqual(set(FULL_WORKSPACE_INTENT_CLASSES),
                            set(CONSEQUENTIAL_INTENT_CLASSES))

    def test_every_known_intent_is_classified(self):
        # A new intent added without a surface would raise here rather than
        # silently defaulting to "phone-capable".
        for intent in KNOWN_INTENT_CLASSES:
            with self.subTest(intent=intent):
                self.assertIn("surface", INTENT_DISPATCH_TABLE[intent])


class TheBoundaryFailsTowardAnswering(unittest.TestCase):
    def test_an_unknown_intent_is_never_deferred(self):
        # Guessing "full workspace" for something unrecognized would manufacture
        # a dead end out of ignorance.
        self.assertFalse(requires_full_workspace("something_new"))
        self.assertFalse(requires_full_workspace(None))

    def test_a_laptop_is_never_offered_a_continuation(self):
        self.assertFalse(_should_offer_continuation(None, INTENT_CLASS_INVESTIGATE_REQUIREMENT))
        self.assertFalse(_should_offer_continuation("", INTENT_CLASS_INVESTIGATE_REQUIREMENT))
        self.assertFalse(_should_offer_continuation("desktop", INTENT_CLASS_INVESTIGATE_REQUIREMENT))

    def test_a_phone_is_only_offered_one_for_full_workspace_work(self):
        self.assertTrue(_should_offer_continuation(SURFACE_MOBILE, INTENT_CLASS_INVESTIGATE_REQUIREMENT))
        self.assertFalse(_should_offer_continuation(SURFACE_MOBILE, INTENT_CLASS_GENERAL_ANSWER))

    def test_an_unreported_surface_answers_normally(self):
        # A missing surface must never be read as "phone".
        self.assertFalse(_should_offer_continuation(None, INTENT_CLASS_PROPOSE_APPLY_FINDINGS))


class TheOfferExposesNoMachinery(unittest.TestCase):
    """"The UI should not expose the underlying intent classifier or Task
    machinery" - Product Owner decision 6."""

    def setUp(self):
        self.offer = _continuation_offer(
            "compare the mechanical drawings against the specification",
            INTENT_CLASS_PROPOSE_APPLY_FINDINGS)

    def test_the_reply_names_no_intent_class_and_no_internal_noun(self):
        text = self.offer.reply_text.lower()
        for leak in ["intent", "classifier", "task", "dispatch", "propose_", "spin"]:
            self.assertNotIn(leak, text, "the reply leaks %r" % leak)

    def test_it_says_plainly_that_nothing_ran(self):
        self.assertIn("nothing has been run or changed", self.offer.reply_text.lower())

    def test_it_offers_exactly_one_action(self):
        self.assertEqual(len(self.offer.operational_actions), 1)
        self.assertEqual(self.offer.operational_actions[0]["kind"], "task")

    def test_it_reuses_the_existing_operational_action_seam(self):
        # kind "task" already renders as a POST to the unchanged
        # create_task_route (CLAUDE-CA1D-RIVER-01). No new control, no new
        # surface, no ticket dashboard.
        action = self.offer.operational_actions[0]
        self.assertIn("default_title", action)
        self.assertEqual(action["originating_surface"], SURFACE_MOBILE)
        self.assertTrue(action["deferred_reason"])

    def test_the_title_is_the_persons_own_words(self):
        self.assertEqual(
            _continuation_title("  compare   the drawings\nagainst the spec "),
            "compare the drawings against the spec")

    def test_a_very_long_request_is_truncated_not_dropped(self):
        title = _continuation_title("x" * 400)
        self.assertLessEqual(len(title), 120)
        self.assertTrue(title.endswith("..."))

    def test_an_empty_request_still_produces_a_usable_title(self):
        self.assertTrue(_continuation_title("   "))


class _WorkspaceCase(unittest.TestCase):
    """A real ingested project with a real conversation message to anchor to.

    Ingestion is spied, never run: BHiveParser.parse is replaced with a stub
    returning a plain ParsedDocument. CLAUDE.md's 8.5-hour incident is what that
    rule is made of. A workspace route needs a real registry document and not
    merely a workspace file, which is why the store cannot just be poked.
    """

    def setUp(self):
        import io
        import uuid
        from datetime import datetime, timezone

        import app as app_module
        from models import User, db
        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.case_workspace import CaseWorkspaceStore
        from services.ingestion import ingest_upload
        from werkzeug.datastructures import FileStorage

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            for name, role in [("owner_u", "admin"), ("member_u", "contributor"),
                               ("outsider_u", "contributor")]:
                db.session.add(User(username=name,
                                    password_hash=generate_password_hash("x"), role=role))
            db.session.commit()

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                # Unique per test: the registry enforces unique entry names and
                # the store is shared across tests in a run.
                doc = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"content"), filename="founding.txt"),
                    self.flask_app, operating_environment="client_owner",
                    owner="owner_u",
                    project_name="Continuation Project " + uuid.uuid4().hex[:8],
                )
        self.project_id = doc.project_id
        self.store = CaseWorkspaceStore(self.flask_app.config["REGISTRY_STORE_PATH"])
        self.workspace = self.store.get(self.project_id)
        self.workspace.owner = "owner_u"
        self.workspace.access_allow_list = ["member_u"]
        self.case = self.store.create_case(
            self.workspace, title="Field question", objective="o")
        self.message = self.store.add_message(
            self.workspace, self.case["id"], role="human",
            text="compare the mechanical drawings against the specification")
        self.store.save(self.workspace)

    def _anchor(self):
        return {
            "scope": "case", "case_id": self.case["id"], "message_id": self.message["id"],
            "start_offset": 0, "end_offset": len(self.message["text"]),
            "quote": self.message["text"],
        }

    def _client(self, username, role="contributor", uid=1):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["username"] = username
            sess["role"] = role
        return client


class YesCreatesOneTaskAndNoCreatesNothing(_WorkspaceCase):
    def test_no_has_no_server_route_at_all(self):
        # The strongest possible guarantee that declining writes nothing: there
        # is no endpoint to decline with. Not pressing the button is the No.
        from routes import workspace as workspace_routes
        source = open(workspace_routes.__file__, encoding="utf-8").read()
        for invented in ["decline_task_route", "dismiss_continuation",
                         "decline_continuation", "reject_task_route"]:
            self.assertNotIn(invented, source)

    def test_merely_being_offered_a_continuation_creates_nothing(self):
        before = len(self.store.get(self.project_id).tasks)
        _continuation_offer("anything at all", INTENT_CLASS_PROPOSE_APPLY_FINDINGS)
        self.assertEqual(len(self.store.get(self.project_id).tasks), before)

    def test_yes_creates_exactly_one_task_carrying_both_new_facts(self):
        client = self._client("owner_u", role="admin")
        resp = client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={**{"anchor_scope": "case", "anchor_case_id": self.case["id"],
                     "anchor_message_id": self.message["id"], "anchor_start_offset": "0",
                     "anchor_end_offset": str(len(self.message["text"])),
                     "anchor_quote": self.message["text"]},
                  "title": "compare the drawings against the spec",
                  "deferred_reason": "Needs the full workspace",
                  "originating_surface": "mobile"})
        self.assertEqual(resp.status_code, 200)
        tasks = self.store.get(self.project_id).tasks
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["deferred_reason"], "Needs the full workspace")
        self.assertEqual(tasks[0]["originating_surface"], "mobile")
        self.assertEqual(tasks[0]["status"], "open")

    def test_pressing_twice_does_not_leave_two_continuations(self):
        # A phone losing signal mid-POST and the person pressing again is a real
        # failure mode, not a hypothetical one.
        client = self._client("owner_u", role="admin")
        payload = {"anchor_scope": "case", "anchor_case_id": self.case["id"],
                   "anchor_message_id": self.message["id"], "anchor_start_offset": "0",
                   "anchor_end_offset": str(len(self.message["text"])),
                   "anchor_quote": self.message["text"],
                   "title": "compare the drawings against the spec",
                   "deferred_reason": "Needs the full workspace",
                   "originating_surface": "mobile"}
        first = client.post(f"/projects/{self.project_id}/workspace/tasks", data=payload).get_json()
        second = client.post(f"/projects/{self.project_id}/workspace/tasks", data=payload).get_json()
        self.assertEqual(len(self.store.get(self.project_id).tasks), 1)
        self.assertEqual(first["task"]["id"], second["task"]["id"])

    def test_an_ordinary_task_is_unaffected_by_the_extension(self):
        # Every pre-existing caller omits both fields.
        task = self.store.create_task(
            self.workspace, self._anchor(), title="ordinary", actor="owner_u")
        self.assertIsNone(task["deferred_reason"])
        self.assertIsNone(task["originating_surface"])


class DeferringIsNotAuthorization(_WorkspaceCase):
    def test_creating_a_deferred_task_runs_no_handler(self):
        # The offer is produced BEFORE dispatch, so nothing analytical executes.
        with patch("services.conversation_interpreter._route_safe_intent") as routed:
            _continuation_offer("investigate this", INTENT_CLASS_INVESTIGATE_REQUIREMENT)
        routed.assert_not_called()

    def test_a_deferred_task_carries_no_approval_and_no_execution_state(self):
        task = self.store.create_task(
            self.workspace, self._anchor(), title="deferred", actor="owner_u",
            deferred_reason="Needs the full workspace", originating_surface="mobile")
        for forbidden in ["approved", "approval", "authorized", "execute",
                          "executed", "assignee", "due_date", "notify",
                          "notification", "channel"]:
            self.assertNotIn(forbidden, task, "Task gained a %r field" % forbidden)

    def test_the_approval_gate_is_untouched_by_this_stage(self):
        from routes import workspace as workspace_routes
        source = open(workspace_routes.__file__, encoding="utf-8").read()
        self.assertIn("_require_approval", source)
        # The continuation must not have acquired a bypass.
        self.assertNotIn("skip_approval", source)
        self.assertNotIn("_require_approval(", source.split("def create_task_route")[1][:900])


class TheProjectBoundaryHolds(_WorkspaceCase):
    def test_a_member_can_reach_their_own_projects_tasks(self):
        client = self._client("member_u", uid=2)
        self.assertEqual(
            client.get(f"/projects/{self.project_id}/workspace").status_code, 200)

    def test_an_outsider_cannot_open_the_project_at_all(self):
        client = self._client("outsider_u", uid=3)
        self.assertIn(
            client.get(f"/projects/{self.project_id}/workspace").status_code, (302, 403, 404))

    def test_a_deep_link_does_not_bypass_the_access_check(self):
        # A link is not a capability: the resume URL carries case/source ids,
        # and the gate runs on LOAD, not on the link.
        client = self._client("outsider_u", uid=3)
        resp = client.get(
            f"/projects/{self.project_id}/workspace?case=" + self.case["id"] + "&source=x")
        self.assertIn(resp.status_code, (302, 403, 404))

    def test_losing_access_closes_the_continuation_link(self):
        client = self._client("member_u", uid=2)
        self.assertEqual(client.get(f"/projects/{self.project_id}/workspace").status_code, 200)
        workspace = self.store.get(self.project_id)
        workspace.access_allow_list = []
        self.store.save(workspace)
        resp = client.get(
            f"/projects/{self.project_id}/workspace?case=" + self.case["id"])
        self.assertIn(resp.status_code, (302, 403, 404),
                      "a revoked member kept access through the continuation link")

    def test_an_outsider_cannot_create_a_task_in_someone_elses_project(self):
        client = self._client("outsider_u", uid=3)
        resp = client.post(f"/projects/{self.project_id}/workspace/tasks", data={
            "anchor_scope": "case", "anchor_case_id": self.case["id"],
            "anchor_message_id": self.message["id"], "anchor_start_offset": "0",
            "anchor_end_offset": "5", "anchor_quote": self.message["text"][:5],
            "title": "not mine", "deferred_reason": "x", "originating_surface": "mobile"})
        self.assertNotEqual(resp.status_code, 200)
        self.assertEqual(len(self.store.get(self.project_id).tasks), 0)

    def test_membership_does_not_confer_membership_management(self):
        # True today by absence rather than by rule, which is safer but
        # invisible - asserted so it stays true.
        from routes import workspace as workspace_routes
        from routes import portal as portal_routes
        for module in (workspace_routes, portal_routes):
            source = open(module.__file__, encoding="utf-8").read()
            for granting in ["access_allow_list.append", "access_allow_list +=",
                             "def invite_", "def add_member"]:
                self.assertNotIn(granting, source)


class NoNotificationWasIntroduced(unittest.TestCase):
    """Product Owner decision 9: seam preserved, delivery NOT built."""

    def test_this_stage_added_no_delivery(self):
        from services import case_workspace, conversation_interpreter
        from routes import workspace as workspace_routes
        for module in (case_workspace, conversation_interpreter, workspace_routes):
            source = open(module.__file__, encoding="utf-8").read()
            with self.subTest(module=module.__name__):
                self.assertNotIn("send_email", source)
                self.assertNotIn("push_notification", source)

    def test_no_speculative_notification_field_was_added_to_task(self):
        # The prohibition was lifted; that is not a reason to add fields.
        import inspect
        from services.case_workspace import Task
        source = inspect.getsource(Task)
        for speculative in ["notification_channel", "notify_", "assignee", "due_date"]:
            self.assertNotIn(speculative, source.split('"""')[-1])


if __name__ == "__main__":
    unittest.main()
