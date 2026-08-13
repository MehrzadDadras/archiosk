"""
CLAUDE-P40-VW7A-QA - Remove Duplicate Chat Label and Correct Margins.

Two corrections, both to the shared conversation_dock macro
(templates/_macros.html) and its surrounding CSS:

1. A compact "Chat (N)" label that a PRIOR correction (CLAUDE-P40-VW8-QA)
   had moved from the old top-of-panel "PROJECT CONVERSATION" heading
   down to the composer row is removed outright - it duplicated the
   Lists panel's own "Chats" row, which now carries the count instead
   (`lists.project.chats`, "Chats N"). The composer input keeps a real
   accessible name via `aria-label="Message"`, not a visible label.

2. A single shared `--conversation-inset` custom property (declared
   once on `.conversation-dock-panel`) replaces the old per-role
   asymmetric message margins (`.conversation-message.human` indented
   left only, `.system` indented right only) - message text, role
   labels, and the composer now all share the same left AND right
   edges.
"""
from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_CASE_WORKSPACE_HTML_PATH = _REPO_ROOT / "templates" / "case_workspace.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_WORKSPACE_ROUTES_PATH = _REPO_ROOT / "routes" / "workspace.py"


class NoDuplicateChatLabelTests(unittest.TestCase):
    def setUp(self):
        self.macros = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_no_visible_chat_count_label_in_the_composer_row(self):
        self.assertNotIn("conversation-dock-compact-label", self.macros)
        self.assertNotIn("conversation-dock-compact-label", self.css)
        self.assertNotIn("Chat ({{ message_count }})", self.macros)

    def test_composer_input_still_has_a_real_accessible_name(self):
        # Not placeholder-only - a real aria-label, just not a visible
        # duplicate label element.
        self.assertIn('aria-label="Message"', self.macros)
        input_idx = self.macros.index('id="dock-composer-input"')
        input_tag_start = self.macros.rindex("<input", 0, input_idx)
        input_tag_end = self.macros.index(">", input_idx)
        input_tag = self.macros[input_tag_start:input_tag_end]
        self.assertIn("aria-label=", input_tag)

    def test_expand_collapse_toggle_still_present_and_functional(self):
        self.assertIn('id="conversation-size-toggle"', self.macros)
        self.assertIn('aria-pressed="false"', self.macros)

    def test_chat_dock_label_reference_is_retired_not_reused(self):
        map_text = (_REPO_ROOT / "UI_REFERENCE_MAP.md").read_text(encoding="utf-8")
        self.assertIn("chat.dock.label", map_text)
        self.assertIn("retired", map_text[map_text.index("chat.dock.label"):map_text.index("chat.dock.label") + 400])
        # Not present as a live data-ui-ref anywhere in templates.
        self.assertNotIn('data-ui-ref="chat.dock.label"', self.macros)


class ChatsListsRowCarriesTheCountTests(unittest.TestCase):
    """CLAUDE-GO-DNA-01 (Panel Zoning) relocated this row from Lists
    (`lists.project.chats`, base.html) into the Toolbox's own Project
    Intelligence view (`toolbox.conversation`, case_workspace.html) - the
    underlying contract this class protects (one row, carrying the real
    count, no duplicate label) is unchanged, just relocated."""

    def setUp(self):
        self.case_workspace_html = _CASE_WORKSPACE_HTML_PATH.read_text(encoding="utf-8")
        self.routes_source = _WORKSPACE_ROUTES_PATH.read_text(encoding="utf-8")

    def test_chats_row_renders_a_launcher_count_span(self):
        idx = self.case_workspace_html.index('data-ui-ref="toolbox.conversation"')
        row = self.case_workspace_html[idx: idx + 300]
        self.assertIn("Conversation <span class=\"launcher-count\">", row)
        self.assertIn("{{ project_conversation_count }}", row)

    def test_chats_row_identifier_retained(self):
        self.assertIn('data-ui-ref="toolbox.conversation"', self.case_workspace_html)

    def test_route_computes_the_count_from_the_real_conversation_list(self):
        self.assertIn("project_conversation_count=len(workspace.project_conversation)", self.routes_source)


class SharedConversationInsetTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _rule_body(self, selector: str) -> str:
        idx = self.css.index(selector)
        start = self.css.index("{", idx)
        end = self.css.index("}", start)
        return self.css[start:end]

    def test_inset_declared_once_as_a_custom_property(self):
        body = self._rule_body(".conversation-dock-panel {")
        self.assertIn("--conversation-inset: 1.5rem", body)

    def test_thread_and_composer_reference_the_same_variable(self):
        thread_body = self._rule_body(".conversation-thread {")
        composer_body = self._rule_body(".conversation-input-form {")
        for body in (thread_body, composer_body):
            self.assertIn("padding-left: var(--conversation-inset)", body)
            self.assertIn("padding-right: var(--conversation-inset)", body)

    def test_no_leftover_asymmetric_role_margins(self):
        self.assertNotIn("margin-left: 1.5rem", self.css[self.css.index(".conversation-message"):self.css.index(".conversation-message") + 2000])

    def test_resize_handle_divider_unaffected_stays_full_width(self):
        body = self._rule_body(".conversation-dock-resize-handle::before {")
        self.assertIn("left: 0", body)
        self.assertIn("right: 0", body)
        self.assertNotIn("conversation-inset", body)


if __name__ == "__main__":
    unittest.main()
