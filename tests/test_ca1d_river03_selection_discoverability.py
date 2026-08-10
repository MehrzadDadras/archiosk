"""
CLAUDE-CA1D-RIVER-03 - Make the River Visible.

CLAUDE-CA1D-RIVER-01's own audit found the selection-to-action toolbar
(static/js/case_workspace.js's setUpConversationTagsAndTasks) fully
implemented, not dormant - the real gap was discoverability: a Product
Owner could not learn the mechanism through ordinary use. This stage
adds the smallest quiet affordance: a one-time, localStorage-gated hint
rendered ONLY alongside a genuinely actionable answer (the same
condition that already gates the "fourth beat" operational actions),
never a permanent toolbar - and it hides itself for good the first time
a real text selection actually opens the toolbar.

Server-rendered markup is tested directly (Flask test client). The
client-side reveal/learn logic is tested via JS source inspection, the
same discipline this codebase already uses for this class of client-
only behavior (no real browser runtime in this suite - see e.g.
tests/test_p40vw7b_vestibule_and_attention.py's own AttentionJsSourceTests).
Live reveal/hide behavior was additionally verified in a real browser
this stage's own closing report describes.

Run via:

    python -m unittest tests.test_ca1d_river03_selection_discoverability -v
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import unittest

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


class HintMarkupTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_ca1d_river03_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-river03"

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

    def _ask_grounded_question(self):
        answer_json = (
            '{"answer": "The submission deadline is August 28.", '
            '"grounded_in": ["Requirement: submission deadline"], '
            '"not_covered": "", "needs_clarification": false}'
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(answer_json)
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What are the important deadlines?"},
            )

    def test_hint_renders_hidden_alongside_a_genuinely_actionable_answer(self):
        self._ask_grounded_question()
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        idx = body.index('id="conv-selection-hint"')
        tag = body[body.rindex("<p", 0, idx):body.index(">", idx)]
        self.assertIn("hidden", tag)
        self.assertIn('data-ui-ref="chat.selection-hint"', tag)
        self.assertIn("Tag it, Highlight it, or make a Task from it", body)

    def test_hint_absent_when_no_operational_actions_are_offered(self):
        """CLAUDE-CA1D-RIVER-03's own explicit requirement: the teaching
        moment appears ONLY where the fourth beat itself already appears
        - never a permanent affordance shown regardless of context."""
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "", "grounded_in": [], '
                '"not_covered": "Not addressed in the extracted evidence.", '
                '"needs_clarification": false}'
            )
            self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What is the color of the sky in this document?"},
            )
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('id="conv-selection-hint"', body)

    def test_hint_absent_for_a_plain_greeting(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Thanks."},
        )
        self.assertEqual(resp.status_code, 302)
        body = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn('id="conv-selection-hint"', body)


class HintClientLogicSourceTests(unittest.TestCase):
    """Client-side reveal/learn logic - source-inspection coverage, same
    discipline this codebase already uses for this class of client-only
    behavior (no real browser runtime in this suite)."""

    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_hint_key_is_a_single_global_flag_not_per_project(self):
        # The mechanism itself isn't project-specific, so "having learned
        # it" shouldn't be re-taught per project either.
        self.assertIn("const SELECTION_HINT_SEEN_KEY = 'beehive:selectionHintSeen';", self.js)

    def test_hint_reveal_is_gated_on_never_having_learned_it(self):
        fn = self.js[self.js.index("function revealSelectionHintIfNeverLearned"):self.js.index("})();", self.js.index("function revealSelectionHintIfNeverLearned"))]
        self.assertIn("localStorage.getItem(SELECTION_HINT_SEEN_KEY)", fn)
        self.assertIn("if (alreadyLearned) return;", fn)
        self.assertIn("el.hidden = false", fn)

    def test_learning_sets_the_flag_and_hides_every_hint_on_the_page(self):
        fn = self.js[self.js.index("function markSelectionHintLearned("):self.js.index("(function revealSelectionHintIfNeverLearned")]
        self.assertIn("localStorage.setItem(SELECTION_HINT_SEEN_KEY, '1')", fn)
        self.assertIn("el.hidden = true", fn)

    def test_a_real_selection_opening_the_toolbar_marks_the_hint_learned(self):
        # The actual behavioral trigger - "once learned, quiet again" is
        # earned by USING the mechanism, not merely by dismissing text.
        start = self.js.index("function handleSelectionMaybeChanged")
        end = self.js.index("document.addEventListener('selectionchange'", start)
        fn = self.js[start:end]
        self.assertIn("positionToolbar(range.getBoundingClientRect());", fn)
        self.assertIn("markSelectionHintLearned();", fn)
        # Must come AFTER the toolbar is actually shown, not before -
        # only a genuinely successful open counts as "learned".
        self.assertLess(fn.index("positionToolbar("), fn.index("markSelectionHintLearned();"))

    def test_no_hover_or_focus_driven_reveal_of_the_hint(self):
        # CLAUDE-CA1D-RIVER-03's own "no hover-driven project movement" -
        # the hint's own reveal must be load-time/localStorage-driven
        # only, never tied to mouseenter/mouseover/focus.
        start = self.js.index("const SELECTION_HINT_SEEN_KEY")
        end = self.js.index("(function revealSelectionHintIfNeverLearned")
        end = self.js.index("})();", end) + len("})();")
        block = self.js[start:end]
        self.assertNotIn("mouseenter", block)
        self.assertNotIn("mouseover", block)
        self.assertNotIn("addEventListener('focus'", block)


if __name__ == "__main__":
    unittest.main()
