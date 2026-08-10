"""
CLAUDE-CA1D-RIVER-01 (+ CLAUDE-CA1D-RIVER-02, same feature set with an
expanded closing-report requirement, not a different implementation) -
Project Gravity / River Continuity.

The "fourth beat": a genuinely evidence-grounded project-question answer
now offers a small, deterministic, capability-true set of real next
actions ("Make a Task from this" / "Highlight this answer") - reusing
the EXISTING create_task_route/add_tag_occurrence_route completely
unchanged (Section 7's own "reuse existing mechanisms, do not create a
parallel subsystem" - the selection-to-action toolbar those routes
already power was audited and found genuinely implemented, not dormant).
Offered only when result.grounded_in is non-empty - a "not covered"
reply, a policy-denied reply, and a conversational utterance (CA1C-
CONV-FIX-02's own gate intercepts those before this code path is ever
reached) all get none.

Run via:

    python -m unittest tests.test_ca1d_river01_project_gravity -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.conversation_interpreter import _operational_action_label
from services.requirements_registry import RequirementsRegistry


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class OperationalActionLabelTests(unittest.TestCase):
    """Unit-level: the deterministic, contextual label chooser."""

    def test_deadline_question_gets_a_deadline_specific_label(self):
        self.assertEqual(
            _operational_action_label("what are the important deadlines?"),
            "Make a Task to track these deadlines",
        )

    def test_risk_question_gets_a_risk_specific_label(self):
        self.assertEqual(
            _operational_action_label("what is the biggest risk here?"),
            "Make a Task to address this",
        )

    def test_generic_question_gets_the_generic_label(self):
        self.assertEqual(
            _operational_action_label("what is the name of the rfp?"),
            "Make a Task from this",
        )


class RiverContinuityRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_river01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-river01"

        with self.flask_app.app_context():
            db.session.add(User(username="pm_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="The submission deadline is August 28.", category="schedule_milestone", confidence=0.6, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "pm_owner"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.set_project_owner(self.store.get(self.project_id), owner="pm_owner", actor="pm_owner")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ask(self, question, grounded=True):
        answer_json = (
            '{"answer": "The submission deadline is August 28.", '
            '"grounded_in": ["Requirement: submission deadline"], '
            '"not_covered": "", "needs_clarification": false}'
            if grounded else
            '{"answer": "", "grounded_in": [], '
            '"not_covered": "This is not addressed in the extracted evidence.", '
            '"needs_clarification": false}'
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(answer_json)
            return self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": question},
            )

    def test_scenario_a_grounded_answer_offers_real_next_actions_not_inert_prose(self):
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        self.assertEqual(last_reply["action_taken"], "project_qa_answered")
        actions = last_reply["operational_actions"]
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["kind"], "task")
        self.assertEqual(actions[0]["label"], "Make a Task to track these deadlines")
        self.assertEqual(actions[1], {"kind": "tag", "label": "Highlight this answer", "tag_id": "built-in:highlight"})

    def test_ungrounded_answer_offers_no_actions_not_inert_but_not_forced_either(self):
        self._ask("What is the color of the sky in this document?", grounded=False)
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        self.assertEqual(last_reply["operational_actions"], [])

    def test_capability_truth_only_task_and_tag_kinds_ever_appear(self):
        # Finding/Risk-Register/Delegate are NOT genuinely implemented as
        # one-click conversational actions today - must never appear,
        # not merely be disabled.
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        actions = workspace.project_conversation[-1]["operational_actions"]
        kinds = {a["kind"] for a in actions}
        self.assertEqual(kinds, {"task", "tag"})

    def test_greeting_gets_no_operational_actions_conversation_stays_conversation(self):
        # CLAUDE-CA1C-CONV-FIX-02's own gate intercepts this before
        # _handle_project_question ever runs - Conversation != Investigation
        # holds by construction here, not by a second check.
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Thanks."},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertNotIn("case=", resp.headers["Location"])
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        self.assertEqual(last_reply["action_taken"], "conversational_utterance")
        self.assertEqual(last_reply.get("operational_actions", []), [])

    def test_no_investigation_created_by_an_actionable_answer(self):
        # Project Gravity "suggests direction; it does not remove
        # authority" - offering an action must never itself create the
        # downstream object or an Investigation.
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.cases, [])

    def test_operational_action_markup_renders_with_the_whole_message_anchor(self):
        self._ask("What are the important deadlines?")
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertIn('data-ui-ref="chat.operational-actions"', body)
        self.assertIn("Make a Task to track these deadlines", body)
        self.assertIn("Highlight this answer", body)
        self.assertIn('name="anchor_scope" value="project"', body)
        self.assertIn('name="anchor_start_offset" value="0"', body)

    def test_make_task_action_creates_a_real_task_with_provenance(self):
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={
                "anchor_scope": "project",
                "anchor_case_id": "",
                "anchor_message_id": message["id"],
                "anchor_start_offset": "0",
                "anchor_end_offset": str(len(message["text"])),
                "anchor_quote": message["text"],
                "title": "Follow up: What are the important deadlines?",
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"], payload)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.tasks), 1)
        task = workspace.tasks[0]
        self.assertEqual(task["title"], "Follow up: What are the important deadlines?")
        # Durable provenance: project (via store/workspace scoping),
        # originating message, excerpt, and actor are all present on the
        # real, persisted anchor - not merely accepted and discarded.
        self.assertEqual(task["source_anchor"]["message_id"], message["id"])
        self.assertEqual(task["source_anchor"]["scope"], "project")
        self.assertEqual(task["source_anchor"]["quote"], message["text"])
        self.assertEqual(task["created_by"], "pm_owner")

    def test_highlight_action_creates_a_real_tag_occurrence(self):
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "anchor_scope": "project",
                "anchor_case_id": "",
                "anchor_message_id": message["id"],
                "anchor_start_offset": "0",
                "anchor_end_offset": str(len(message["text"])),
                "anchor_quote": message["text"],
                "tag_id": "built-in:highlight",
            },
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["ok"], payload)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.tag_occurrences), 1)
        occurrence = workspace.tag_occurrences[0]
        self.assertEqual(occurrence["tag_id"], "built-in:highlight")
        self.assertEqual(occurrence["source_anchor"]["message_id"], message["id"])

    def test_created_task_persists_and_stays_project_scoped_after_reload(self):
        # Scenario C/D: persistence + project isolation across a fresh
        # store read (simulating navigate-away/refresh).
        self._ask("What are the important deadlines?")
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        self.client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={
                "anchor_scope": "project", "anchor_case_id": "",
                "anchor_message_id": message["id"], "anchor_start_offset": "0",
                "anchor_end_offset": str(len(message["text"])), "anchor_quote": message["text"],
                "title": "Follow up: deadlines",
            },
        )
        fresh_store = CaseWorkspaceStore(self.tmp_dir)
        reloaded = fresh_store.get(self.project_id)
        self.assertEqual(len(reloaded.tasks), 1)
        self.assertEqual(reloaded.tasks[0]["title"], "Follow up: deadlines")
        self.assertEqual(reloaded.project_id, self.project_id)


if __name__ == "__main__":
    unittest.main()
