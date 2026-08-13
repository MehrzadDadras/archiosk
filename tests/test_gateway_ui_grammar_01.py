"""
CLAUDE-GATEWAY-UI-GRAMMAR-01 -- shared UI grammar consistency on the
pre-project flow (Sign-In, Project Gateway, Open Existing Project, New
Project).

A repository-grounded audit found three concrete, fixable instances of a
page bypassing an existing shared primitive with a local one-off value,
rather than any missing shared component:

  - .gateway-card-compact .gateway-signin-button (Sign-In's primary
    button) had its own padding/border-radius/font-weight, literally
    square-cornered and differently padded than every other .btn-primary
    in the app.
  - .voice-input-button (the mic control shared by the in-project
    composer, Sign-In, and Project Gateway) only ever had a border/
    border-radius supplied by its original parent context
    (.conversation-input-form button) - the two newer instances
    (Sign-In, Gateway), which don't sit inside that parent, were
    silently falling back to unstyled native button chrome.
  - upload.html's project-name field used an inline
    style="max-width:480px" instead of a reusable class.

Covers the fix for all three - never removes a legitimate semantic
difference (the compact card's own block/full-width/margin treatment is
kept), only reconciles values that should have come from a shared
primitive already governing that value elsewhere in the app.
"""
from __future__ import annotations

from pathlib import Path
import unittest


class SigninButtonInheritsSharedBtnStylingTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/css/main.css").read_text(encoding="utf-8")

    def _rule_body(self, selector: str) -> str:
        idx = self.css.index(selector)
        brace_open = self.css.index("{", idx)
        brace_close = self.css.index("}", brace_open)
        return self.css[brace_open + 1:brace_close]

    def test_signin_button_no_longer_overrides_padding_or_border_radius(self):
        body = self._rule_body(".gateway-card-compact .gateway-signin-button")
        self.assertNotIn("padding:", body)
        self.assertNotIn("border-radius:", body)
        self.assertNotIn("font-weight:", body)

    def test_signin_button_keeps_its_genuinely_compact_layout(self):
        # display:block/width:100%/margin - a real, kept difference (the
        # compact card's own full-width button), not part of the fix.
        body = self._rule_body(".gateway-card-compact .gateway-signin-button")
        self.assertIn("display: block", body)
        self.assertIn("width: 100%", body)

    def test_shared_btn_primary_padding_and_radius_are_unchanged(self):
        # The .btn/.btn-primary rules the sign-in button now inherits
        # from must still exist with their own values - this test would
        # fail loudly if a future edit removed them, silently leaving
        # the sign-in button with browser-default styling.
        btn_body = self._rule_body(".btn {")
        self.assertIn("padding: 0.85rem 1.5rem", btn_body)
        self.assertIn("border-radius: 3px", btn_body)


class VoiceInputButtonIsSelfSufficientTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/css/main.css").read_text(encoding="utf-8")

    def test_voice_input_button_carries_its_own_border_and_radius(self):
        idx = self.css.index(".voice-input-button {")
        brace_open = self.css.index("{", idx)
        brace_close = self.css.index("}", brace_open)
        body = self.css[brace_open + 1:brace_close]
        self.assertIn("border-radius: 4px", body)
        self.assertIn("border: 1px solid var(--text-primary)", body)
        self.assertIn("font-weight: 600", body)


class GatewayCardCompactUsesRemNotRawPxTests(unittest.TestCase):
    def setUp(self):
        self.css = Path("static/css/main.css").read_text(encoding="utf-8")
        start = self.css.index(".gateway-card-compact .gateway-brand {")
        end = self.css.index(".gateway-footer {", start)
        self.block = self.css[start:end]

    def test_no_raw_px_values_remain_in_the_compact_card_block(self):
        import re
        self.assertNotRegex(self.block, r":\s*[\d.]+px\b")

    def test_visual_sizes_are_unchanged_not_just_reunited_to_rem(self):
        # 16px/32px/12px/12.8px/19.2px/3px/14px at the app's 16px root
        # font-size - same visual result, different unit.
        self.assertIn("padding: 1rem 2rem 0.75rem", self.block)
        self.assertIn("padding: 0.8rem 2rem 1rem", self.block)
        self.assertIn("margin-bottom: 1.2rem", self.block)


class UploadWideTextInputTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(username="grammar_admin", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "grammar_admin"
            sess["role"] = "admin"

    def test_project_name_field_uses_a_class_not_an_inline_style(self):
        body = self.client.get("/upload").get_data(as_text=True)
        field_start = body.index('name="project_name"')
        tag_start = body.rindex("<input", 0, field_start)
        tag_end = body.index(">", field_start)
        tag = body[tag_start:tag_end]
        self.assertIn("text-input-wide", tag)
        self.assertNotIn("style=", tag)

    def test_text_input_wide_class_defined_in_css(self):
        css = Path("static/css/main.css").read_text(encoding="utf-8")
        self.assertIn(".text-input-wide { max-width: 480px; }", css)


if __name__ == "__main__":
    unittest.main()
