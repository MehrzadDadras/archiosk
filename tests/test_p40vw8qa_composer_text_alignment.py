"""
CLAUDE-P40-VW8-QA / CLAUDE-P40-VW7A-QA - Conversation composer/thread
horizontal alignment.

Original (VW8-QA) fix: the composer's own left padding was bumped from
0.9rem to 1.5rem to match `.conversation-message.human`'s margin-left,
so a typed message's text started at the same x-position once posted.

CLAUDE-P40-VW7A-QA superseded that mechanism outright (not layered on
top of it): "inconsistent horizontal alignment... left edges must
align... right margin must visually balance the left margin" named the
OLD per-role asymmetric margin scheme itself (`.conversation-message.human`
indented left only, `.system` indented right only) as the actual
problem. The fix is now ONE shared `--conversation-inset` custom
property, declared once on `.conversation-dock-panel` (the thread and
composer's common ancestor) and applied as left+right padding on both
`.conversation-thread` and `.conversation-input-form` - so every piece
of Chat content (role labels, message text, composer input, Send)
shares the exact same left AND right edges, and the composer input's
own internal padding goes back to a plain symmetric 0.7rem/0.9rem
(no longer needs its own asymmetric compensation).

CLAUDE-CA1D-RIVER-PO-02 (Section 18, "composer visual chrome"): the
input's own all-around border/background box was replaced with a
single bottom rule ("a disciplined lane, not a boxed widget") - the
internal horizontal padding dropped from 0.9rem to 0.2rem (there is no
longer a border to keep text clear of) and the background became
transparent (the panel's own theme-aware surface shows through). The
shared-inset mechanism above, which is what actually keeps the
composer's left/right edges aligned with the thread's, is unchanged.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_MACROS_HTML_PATH = _REPO_ROOT / "templates" / "_macros.html"

_INSET_VALUE = "1.5rem"


class ComposerTextAlignmentTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def _rule_body(self, selector: str, occurrence: int = 0) -> str:
        idx = -1
        for _ in range(occurrence + 1):
            idx = self.css.index(selector, idx + 1)
        start = self.css.index("{", idx)
        end = self.css.index("}", start)
        return self.css[start:end]

    def test_shared_inset_declared_once_on_the_common_ancestor(self):
        body = self._rule_body(".conversation-dock-panel {")
        self.assertIn(f"--conversation-inset: {_INSET_VALUE}", body)

    def test_conversation_thread_uses_the_shared_inset_on_both_sides(self):
        body = self._rule_body(".conversation-thread {")
        self.assertIn("padding-left: var(--conversation-inset)", body)
        self.assertIn("padding-right: var(--conversation-inset)", body)

    def test_composer_form_uses_the_same_shared_inset_on_both_sides(self):
        body = self._rule_body(".conversation-input-form {")
        self.assertIn("padding-left: var(--conversation-inset)", body)
        self.assertIn("padding-right: var(--conversation-inset)", body)

    def test_no_hardcoded_inset_literal_duplicated_outside_the_one_declaration(self):
        # The value 1.5rem must be declared exactly once (on the shared
        # custom property) - .conversation-thread/.conversation-input-form
        # reference var(--conversation-inset), never a second literal
        # "1.5rem" of their own that could silently drift from it.
        thread_body = self._rule_body(".conversation-thread {")
        composer_body = self._rule_body(".conversation-input-form {")
        self.assertNotIn("1.5rem", thread_body)
        self.assertNotIn("1.5rem", composer_body)

    def test_per_role_asymmetric_message_margins_removed(self):
        # CLAUDE-P40-VW7A-QA: .human/.system no longer carry their own
        # margin-left/margin-right - every message now starts at the
        # thread's own shared inset, regardless of role.
        self.assertNotIn(".conversation-message.human { margin-left:", self.css)
        self.assertNotIn(".conversation-message.system { margin-right:", self.css)

    def test_composer_input_padding_is_symmetric_not_compensating_for_role_margins(self):
        # CLAUDE-CA1D-RIVER-PO-02 (Section 18, "composer visual chrome"):
        # the horizontal value dropped from 0.9rem to 0.2rem when the
        # input's own all-around border/box was replaced with a single
        # bottom rule (there is no longer a border to keep text clear
        # of) - the invariant this test actually protects, "symmetric,
        # not a per-role asymmetric compensation hack," still holds; it
        # is just a smaller symmetric value now.
        body = self._rule_body('.conversation-input-form input[type="text"] {')
        match = re.search(r"padding:\s*([0-9.]+rem)\s+([0-9.]+rem)\s*;", body)
        self.assertIsNotNone(match, f"expected a plain 2-value padding shorthand, got: {body}")
        top, right = match.groups()
        self.assertEqual(top, "0.7rem")
        self.assertEqual(right, "0.2rem")

    def test_composer_input_keeps_flexible_width_send_button_position_unaffected(self):
        body = self._rule_body('.conversation-input-form input[type="text"] {')
        self.assertIn("flex: 1", body)

    def test_resize_handle_divider_stays_full_width_not_inset(self):
        # The shared inset is deliberately NOT applied to the resize-
        # handle's own divider line - it must stay edge-to-edge, an
        # explicit design decision (see main.css's own comment).
        body = self._rule_body(".conversation-dock-resize-handle::before {")
        self.assertIn("left: 0", body)
        self.assertIn("right: 0", body)

    def test_single_shared_composer_macro_covers_both_project_chat_and_investigation_discussion(self):
        # One macro, one CSS rule - no per-context duplication that
        # could silently diverge between the two composers.
        macros_source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.assertEqual(macros_source.count('class="conversation-input-form conversation-dock-composer"'), 1)

    def test_chat_composer_input_ui_reference_is_unchanged(self):
        macros_source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('data-ui-ref="chat.composer.input"', macros_source)

    def test_composer_input_has_a_real_accessible_label_not_placeholder_only(self):
        # CLAUDE-P40-VW7A-QA: aria-label, not a visible <label> (which
        # would recreate the duplicate-Chat-count-near-the-composer
        # defect this same stage removes) - but still a REAL accessible
        # name, not placeholder text alone.
        macros_source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('aria-label="Message"', macros_source)

    def test_no_duplicate_chat_count_label_rendered_near_the_composer(self):
        macros_source = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.assertNotIn("conversation-dock-compact-label", macros_source)
        self.assertNotIn("conversation-dock-compact-label", self.css)

    def test_appearance_scoped_input_text_color_still_theme_aware(self):
        # CLAUDE-CA1D-RIVER-PO-02 (Section 18): the input's own
        # background is now deliberately transparent (the "disciplined
        # lane, not a boxed widget" correction removed the filled box
        # entirely) rather than an explicit var(--surface-primary) - it
        # inherits whatever theme surface .conversation-dock-panel/
        # .chat-region.appearance-* already paint underneath, which stay
        # theme-aware exactly as before. What must still hold is the
        # text color itself remaining theme-aware, and the box being
        # genuinely gone (not a leftover fixed background this stage
        # forgot to update).
        body = self._rule_body('.conversation-input-form input[type="text"] {')
        self.assertIn("var(--text-primary)", body)
        self.assertIn("background: transparent", body)


if __name__ == "__main__":
    unittest.main()
