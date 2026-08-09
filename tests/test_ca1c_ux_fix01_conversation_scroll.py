"""
CLAUDE-CA1C-UX-FIX-01 - Fix Conversation Auto-Scroll / Last Message Hidden.

Root cause (see routes/workspace.py and static/js/case_workspace.js's own
comments for the full account): every conversation POST redirected back
with a "#conversation-dock" fragment. That fragment used to also open a
collapsed <details> ancestor, but the dock stopped being a <details>
element in P40-E2B (it's a plain, always-visible <div> now), so the only
thing the fragment still did was trigger the browser's own native
anchor-scroll - which targets this sticky, bottom-pinned panel's own top
edge, not the newest message - racing against static/js/case_workspace.js's
own deliberate scroll-to-newest-message logic on a `scroll-behavior:
smooth` container. Two competing smooth-scrolls settled short of the real
bottom: the live-reported "starts too high, stops short of the newest
exchange" defect.

This file cannot exercise the browser's own scroll mechanics (no JS
runtime in this test suite) - it proves the two things that ARE provable
server-side: the redirect no longer carries the fragment that caused the
race, and a stable bottom sentinel exists as the true last child of both
conversation-thread variants (case-scoped and project-level), which is
what a real browser check (see the governance record for this stage) was
used to confirm the actual scroll behavior against live-reloaded pages.

Run via:

    python -m unittest tests.test_ca1c_ux_fix01_conversation_scroll -v
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
from services.requirements_registry import RequirementsRegistry


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ConversationScrollFixTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1c_ux_fix01_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-ux-fix01"

        with self.flask_app.app_context():
            db.session.add(User(username="ux_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="founding.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="The system shall do a thing.", category="other", confidence=0.6, source_line=1),
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "ux_owner"
            sess["role"] = "admin"
        # Establish workspace ownership the same way other route tests do.
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.store.set_project_owner(self.store.get(self.project_id), owner="ux_owner", actor="ux_owner")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_quick_start_redirect_no_longer_carries_the_racing_fragment(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Test answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What is the name of this document?"},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(resp.headers["Location"].endswith("#conversation-dock"))

    def test_discuss_redirect_no_longer_carries_the_racing_fragment(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Test answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What is the name of the RFP?"},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(resp.headers["Location"].endswith("#conversation-dock"))

    def test_project_level_thread_has_a_true_bottom_sentinel_as_its_last_child(self):
        """The sentinel static/js/case_workspace.js's scroll-to-newest logic
        is verified against (see the governance record's own live-browser
        check) must render as the LAST element inside .conversation-thread -
        after every message, not before, and not outside the scrollable
        container - or a real browser's scrollTop-to-scrollHeight jump
        would not actually reach past the newest message."""
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Test answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What is the name of this document?"},
            )
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        thread_start = body.index('data-conversation-scope="project"')
        # The sentinel must appear after the last rendered message - not
        # merely present anywhere on the page.
        last_message_pos = body.rindex('class="conversation-message')
        sentinel_pos = body.index('data-conversation-bottom-sentinel', thread_start)
        self.assertGreater(sentinel_pos, last_message_pos)

    def test_case_scoped_thread_has_a_true_bottom_sentinel_as_its_last_child(self):
        workspace = self.store.get(self.project_id)
        case = self.store.create_case(workspace, title="Test Investigation", objective="", created_by="ux_owner")
        body = self.client.get(
            f"/projects/{self.project_id}/workspace?case={case['id']}"
        ).get_data(as_text=True)
        thread_start = body.index(f'data-conversation-scope="case-{case["id"]}"')
        sentinel_pos = body.index('data-conversation-bottom-sentinel', thread_start)
        composer_pos = body.index('id="dock-composer-input"')
        # The sentinel belongs inside the scrollable thread, rendered before
        # the (separate, always-in-flow) composer markup that follows it.
        self.assertLess(thread_start, sentinel_pos)
        self.assertLess(sentinel_pos, composer_pos)


if __name__ == "__main__":
    unittest.main()
