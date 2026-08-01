"""
CLAUDE-P40-E1A-VISUAL-CLOSE - De-boxing verification.

No browser/rendering tool exists in this environment, so these tests
cannot verify pixel-level appearance - what they CAN verify, and do,
is that the specific decorative CSS properties the de-boxing addendum
named are actually gone from the rules that used to declare them, and
that the functional boundaries the addendum explicitly asked to keep
(the composer's own input border, selected-row highlighting, focus
states) are still there. A regex/text-level check against the real
stylesheet, not a rendered-page assertion - the practical ceiling for
this kind of change without a browser tool, stated honestly rather
than skipped.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"


def _rule_body(css: str, selector: str) -> str:
    """Returns the {...} body text of the FIRST rule whose selector
    list contains `selector` as an exact token, not as a substring of a
    longer one (".workspace-pane" must not match ".workspace-pane-nav").
    This stylesheet never nests {} inside a property block, so the
    first "}" after the selector's own "{" is always that rule's real
    end - a plain scan, not a full CSS parser, but enough for this
    file's own consistent single-rule-per-concern style."""
    needle = re.compile(re.escape(selector) + r"(?![\w-])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        # Only a real selector-list match if nothing but selector
        # syntax (letters/./,/space/newline/#/[]/"=) sits between this
        # match and the opening brace - otherwise this was just a
        # property value or comment mentioning the same text.
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


class WorkspacePaneDeboxedTests(unittest.TestCase):
    """"remove decorative containers around Project information" -
    .workspace-pane wraps Project information (the nav-pane/reference
    content), an Investigation's own content, Findings, an opened
    document, Project Briefing, and Project State - one shared rule,
    checked once."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.body = _rule_body(self.css, ".workspace-pane")

    def test_no_filled_background(self):
        self.assertNotIn("background:", self.body)

    def test_no_border(self):
        self.assertNotRegex(self.body, r"\bborder\s*:")

    def test_no_border_radius(self):
        self.assertNotIn("border-radius", self.body)

    def test_still_has_a_restrained_divider_between_sections(self):
        # "use... restrained horizontal dividers" - a divider is not a
        # box; a bottom border on the section that came before the next
        # one is the accepted alternative the addendum itself names.
        self.assertIn("border-bottom", self.body)


class InvestigationAndSourceListingDeboxedTests(unittest.TestCase):
    """"remove boxes around Investigation listings" - .case-item (and
    the same shared rule for .source-item)."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.shared_body = _rule_body(self.css, ".source-item, .case-item")

    def test_no_filled_beige_background_on_the_shared_row_rule(self):
        self.assertNotIn("background:", self.shared_body)

    def test_no_full_border_or_radius_on_the_shared_row_rule(self):
        self.assertNotRegex(self.shared_body, r"\bborder\s*:")
        self.assertNotIn("border-radius", self.shared_body)

    def test_active_investigation_row_still_has_a_selected_state(self):
        # "retain boundaries for... selected navigation rows" - the
        # active/selected row is still a real, visible state change.
        active_body = _rule_body(self.css, ".case-item.active")
        self.assertIn("background: var(--surface-selected)", active_body)


class ConversationDockDeboxedTests(unittest.TestCase):
    """"remove the enclosing Project/Investigation Conversation card"
    - #conversation-dock previously had a drop-shadow "lift" effect."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")
        self.body = _rule_body(self.css, "#conversation-dock")

    def test_no_box_shadow_card_lift(self):
        self.assertNotIn("box-shadow", self.body)

    def test_background_is_retained_for_sticky_scroll_legibility(self):
        # Not decorative here - functional: without an opaque
        # background, content scrolling underneath the sticky dock
        # would show through its own text.
        self.assertIn("background:", self.body)


class ConversationMessageDeboxedTests(unittest.TestCase):
    """"remove borders and filled cards around ordinary user and
    Archiosk messages" - .conversation-message and its .human/.system
    modifiers."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_base_message_rule_has_no_background_border_or_radius(self):
        body = _rule_body(self.css, ".conversation-message")
        self.assertNotIn("background:", body)
        self.assertNotRegex(body, r"\bborder\s*:")
        self.assertNotIn("border-radius", body)

    def test_human_modifier_has_no_filled_background(self):
        body = _rule_body(self.css, ".conversation-message.human")
        self.assertNotIn("background", body)

    def test_system_modifier_has_no_background_or_border(self):
        body = _rule_body(self.css, ".conversation-message.system")
        self.assertNotIn("background", body)
        self.assertNotRegex(body, r"\bborder\s*:")

    def test_role_label_still_distinguishes_speaker_without_a_box(self):
        # "use headings, whitespace, indentation" instead - the role
        # label (already uppercase/letter-spaced/color-differentiated)
        # is the substitute distinguishing mechanism, still present.
        self.assertIn(".conversation-message .role-label", self.css)
        self.assertIn(".conversation-message.system .role-label", self.css)


class FunctionalBoundariesRetainedTests(unittest.TestCase):
    """The addendum's own explicit retention list - these must still
    be real, visible boundaries, not swept up in the de-boxing."""

    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_composer_input_still_has_a_visible_border(self):
        body = _rule_body(self.css, '.conversation-input-form input[type="text"]')
        self.assertRegex(body, r"\bborder\s*:")

    def test_focus_visible_outline_still_defined(self):
        self.assertIn(":focus-visible", self.css)
        focus_body = _rule_body(self.css, ":focus-visible")
        self.assertIn("outline", focus_body)

    def test_side_rail_active_row_still_has_a_selected_background(self):
        body = _rule_body(self.css, ".side-rail-link.active")
        self.assertIn("background", body)

    def test_flash_error_warning_still_bordered(self):
        body = _rule_body(self.css, ".flash-error")
        self.assertRegex(body, r"\bborder-color\s*:|\bborder\s*:")

    def test_delegation_choice_confirmation_control_still_boxed(self):
        # A real decision point (Do it for me / Show me first / Cancel),
        # not an ordinary message - deliberately left alone.
        body = _rule_body(self.css, ".delegation-choice, .rfi-preview, .rfi-draft-card")
        self.assertRegex(body, r"\bborder\s*:")


class WorkspacePageStillRendersTests(unittest.TestCase):
    """A bounded sanity check that the de-boxing pass didn't break
    actual page rendering - full functional coverage of the Workspace
    route already exists in tests/test_p40e*.py; this only confirms
    those same pages still render 200 after this stage's CSS-only
    changes (no template/class-name changes were made)."""

    def setUp(self):
        import io
        import shutil
        import tempfile
        import uuid
        from datetime import datetime, timezone
        from pathlib import Path as _Path
        from unittest.mock import patch

        from werkzeug.datastructures import FileStorage
        from werkzeug.security import generate_password_hash

        import app as app_module
        from models import User, db
        from services.bhive_parser import BHiveParser, ParsedDocument
        from services.environment_capabilities import CLIENT_OWNER
        from services.ingestion import ingest_upload

        self.tmp_dir = _Path(tempfile.mkdtemp(prefix="beehive_test_p40e1a_visual_"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp_dir, ignore_errors=True))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="p40e1a_visual_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                self.doc = ingest_upload(
                    FileStorage(stream=io.BytesIO(b"content"), filename="rfp.txt"), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="p40e1a_visual_owner", project_name="Visual Debox Check",
                )

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "p40e1a_visual_owner"
            sess["role"] = "admin"

    def test_project_home_still_renders(self):
        resp = self.client.get(f"/projects/{self.doc.project_id}/workspace")
        self.assertEqual(resp.status_code, 200)

    def test_investigation_view_still_renders(self):
        self.client.post(f"/projects/{self.doc.project_id}/workspace/cases", data={"title": "Draft 1", "objective": ""})
        resp = self.client.get(f"/projects/{self.doc.project_id}/workspace", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Draft 1", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
