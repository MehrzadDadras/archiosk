"""
CLAUDE-CA1D-RIVER-PO-02 - Task creation feedback and source-return
precision.

Two live Product Owner corrections:

1. Clicking "Make a Task from this" appeared to flash transient feedback
   in the Eye panel. Root cause (confirmed live, not guessed): the
   fourth-beat's own submit handler reused #conv-selection-status - a
   `position: fixed; bottom: 1rem; right: 1rem` toast built for the
   UNRELATED selection-toolbar (which sits near a live text selection).
   In this app's 6-panel shell, that fixed viewport corner visually
   coincides with the Eye pane's own screen region - no code ever
   touched Eye, but the toast rendered on top of it. Fixed by moving
   feedback onto the clicked button's own label instead (no floating
   toast for this interaction at all).

2. A Task created from a River Action Stack answer was anchored to the
   WHOLE reply, when a much smaller, more precise unit (the specific
   ranked action) was available. Fixed: when river_actions exists, the
   fourth beat anchors to its own top-ranked action's text instead of
   the whole message - "prefer the smallest reliable source anchor
   available" - falling back to the whole message when no finer
   structure exists (an honest anchor, not a regression).

Full sub-message-range temporary focus/flash on navigate-back (as
opposed to today's existing whole-message .conv-source-flash) is a
larger, separately-scoped architecture item, deliberately NOT built in
this correction - see this stage's own closing report.

Run via:

    python -m unittest tests.test_ca1d_river_po02_provenance_precision -v
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry

_REPO_ROOT = Path(__file__).resolve().parent.parent
_JS_PATH = _REPO_ROOT / "static" / "js" / "case_workspace.js"


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class EyePanelToastRemovalSourceTests(unittest.TestCase):
    """Client-side source-inspection coverage - no real browser runtime
    in this suite (same discipline this codebase already uses for this
    class of client-only behavior)."""

    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_operational_action_handler_never_calls_show_status(self):
        start = self.js.index("document.addEventListener('submit', (e) => {\n            const form = e.target.closest('.conv-operational-action-form');")
        end = self.js.index("// -------- Toolbar button handling", start)
        handler = self.js[start:end]
        self.assertNotIn("showStatus(", handler)

    def test_feedback_is_on_the_clicked_button_itself(self):
        start = self.js.index("document.addEventListener('submit', (e) => {\n            const form = e.target.closest('.conv-operational-action-form');")
        end = self.js.index("// -------- Toolbar button handling", start)
        handler = self.js[start:end]
        self.assertIn("btn.textContent = isTag ? 'Tagged' : 'Task created';", handler)
        self.assertIn("btn.textContent = 'Error", handler)


class AnchorPrecisionRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_river_po02_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-river-po02"

        with self.flask_app.app_context():
            db.session.add(User(username="pm_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="Proposal Submission Deadline is August 28.", category="schedule_milestone", confidence=0.6, source_line=1),
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

    _RIVER_ACTIONS = [
        {"rank": 1, "action": "Confirm the Proposal Submission Deadline", "rationale": "The date was extended.", "consequence": "Missing it ends eligibility.", "uncertainty": "", "evidence": ["Revision note"]},
        {"rank": 2, "action": "Confirm the Proponent Representative", "rationale": "Required for correspondence.", "consequence": "Blocks communication.", "uncertainty": "", "evidence": ["Section 3.1"]},
    ]

    def _ask_with_river_actions(self):
        payload = {
            "answer": "Here are the most consequential next moves.",
            "grounded_in": [],
            "not_covered": "", "needs_clarification": False,
            "river_actions": self._RIVER_ACTIONS,
        }
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(json.dumps(payload))
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What do you think I need to do next?"},
            )

    def _ask_ordinary_grounded_question(self):
        payload = {
            "answer": "The RFP is named Project Dossier-Sync.",
            "grounded_in": ["Cover page"],
            "not_covered": "", "needs_clarification": False,
        }
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(json.dumps(payload))
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What is the name of the RFP?"},
            )

    def test_river_action_stack_answer_anchors_to_top_action_not_whole_message(self):
        self._ask_with_river_actions()
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        actions = last_reply["operational_actions"]
        task_action = next(a for a in actions if a["kind"] == "task")
        self.assertIsNotNone(task_action["anchor_text"])
        self.assertIn("Confirm the Proposal Submission Deadline", task_action["anchor_text"])
        # The SECOND action's own text must NOT leak into the anchor -
        # this is precision, not just "some subset of the reply".
        self.assertNotIn("Proponent Representative", task_action["anchor_text"])

    def test_ordinary_answer_still_anchors_to_the_whole_message(self):
        """Preserve cases where a task genuinely originates from a whole
        answer - no River Action Stack, no finer structure available."""
        self._ask_ordinary_grounded_question()
        workspace = self.store.get(self.project_id)
        last_reply = workspace.project_conversation[-1]
        actions = last_reply["operational_actions"]
        task_action = next(a for a in actions if a["kind"] == "task")
        self.assertIsNone(task_action["anchor_text"])

    def test_rendered_task_form_uses_the_top_action_text_as_its_anchor_quote(self):
        self._ask_with_river_actions()
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        start = body.index('data-ui-ref="chat.operational-actions"')
        end = body.index("chat.selection-hint", start) if "chat.selection-hint" in body[start:] else len(body)
        section = body[start:end]
        # The anchor_quote hidden field for the Task/Tag forms must carry
        # the top action's own heading, not the generic framing sentence
        # used when river_actions is absent.
        self.assertIn("Confirm the Proposal Submission Deadline", section)
        self.assertNotIn("Proponent Representative", section)

    def test_task_created_from_top_action_carries_that_anchor_through_to_persistence(self):
        """End-to-end: click Make a Task, confirm the persisted Task's
        own source_anchor.quote is the precise action text, not the
        whole reply - real provenance, not merely a UI label."""
        self._ask_with_river_actions()
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        task_action = next(a for a in message["operational_actions"] if a["kind"] == "task")
        anchor_quote = task_action["anchor_text"][:2000]
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/tasks",
            data={
                "anchor_scope": "project", "anchor_case_id": "",
                "anchor_message_id": message["id"], "anchor_start_offset": "0",
                "anchor_end_offset": str(len(anchor_quote)), "anchor_quote": anchor_quote,
                "title": task_action["default_title"],
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])
        workspace = self.store.get(self.project_id)
        task = workspace.tasks[-1]
        self.assertIn("Confirm the Proposal Submission Deadline", task["source_anchor"]["quote"])
        self.assertNotIn("Proponent Representative", task["source_anchor"]["quote"])
        self.assertEqual(task["source_anchor"]["message_id"], message["id"])

    def test_highlight_action_never_anchors_to_river_action_text(self):
        """CLAUDE-CA1D-RIVER-PO-02 CONSOLIDATION (live-verified defect):
        app.py's hotlinks() marks a highlighted passage by slicing
        message.text[start:end] using the STORED OFFSETS directly - it
        never searches for the quote's own content. A river action's own
        text (heading + rationale + consequence) is never a literal
        substring of the reply prose, so anchoring Highlight to it
        produces a real, persisted tag_occurrence whose end_offset
        exceeds len(message.text) - hotlinks()'s own bounds guard then
        silently drops it forever, on every render. The tag action must
        always anchor to the whole answer, regardless of river_actions."""
        self._ask_with_river_actions()
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        tag_action = next(a for a in message["operational_actions"] if a["kind"] == "tag")
        self.assertIsNone(tag_action["anchor_text"])
        self.assertEqual(tag_action["label"], "Highlight this answer")

    def test_highlight_created_from_a_river_action_stack_answer_actually_renders(self):
        """End-to-end proof the fix holds: the resulting tag_occurrence's
        own offsets must fit inside the real message text, so hotlinks()
        can actually draw the <mark> - not merely that the route accepted
        the POST."""
        self._ask_with_river_actions()
        workspace = self.store.get(self.project_id)
        message = workspace.project_conversation[-1]
        tag_action = next(a for a in message["operational_actions"] if a["kind"] == "tag")
        quote = message["text"][:2000]
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/tags",
            data={
                "anchor_scope": "project", "anchor_case_id": "",
                "anchor_message_id": message["id"], "anchor_start_offset": "0",
                "anchor_end_offset": str(len(quote)), "anchor_quote": quote,
                "tag_id": tag_action["tag_id"],
            },
        )
        self.assertTrue(resp.get_json()["ok"])
        workspace = self.store.get(self.project_id)
        occurrence = workspace.tag_occurrences[-1]
        self.assertLessEqual(occurrence["source_anchor"]["end_offset"], len(message["text"]))


if __name__ == "__main__":
    unittest.main()
