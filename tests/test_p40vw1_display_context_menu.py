"""
CLAUDE-P40-VW1 - Restore the On-Demand Display Split Context Menu.

Product-owner walkthrough defect, from the sealed P40-E3B DEFER baseline
(510c4ef): the per-Display right-click menu (#display-context-menu) was
permanently visible near the upper-left corner instead of hidden until a
real right-click, and right-clicking a Display did not visibly open it
at the pointer.

Root cause (confirmed by direct CSS/JS source inspection, not assumed):
`.display-context-menu { display: flex; ... }` in static/css/main.css is
an author-origin class selector of the SAME specificity (0,1,0) as the
browser's own user-agent stylesheet rule `[hidden] { display: none }`.
Per the CSS cascade, an author-origin rule always wins over a
user-agent-origin rule at equal specificity, regardless of source
order - so the JS-toggled `hidden` attribute on #display-context-menu
was being silently defeated on every render, including the very first
one. The JS itself (open/close/target/Escape/outside-click/Apply/Close
dismissal, viewport clamping) was already correct and complete - this
was not a JS bug, and the fix does not touch case_workspace.js.

The top-bar Display Layout/Appearance/User menus never hit this because
they are native <details>/<summary> disclosure widgets, a different,
unaffected visibility mechanism - confirmed by inspection, left
untouched here.

Fix: one added CSS rule, `.display-context-menu[hidden] { display: none; }`,
whose specificity (0,2,0) beats the base rule regardless of source
order, restoring the `hidden` attribute's intended effect without
touching any positioning/z-index/color rule already in place.

No browser/rendering tool exists in this environment - CSS/JS source
assertions verify the structural facts a browser's cascade algorithm
would act on; HTML assertions verify server-rendered markup. Stated
honestly rather than skipped, matching this repo's established
convention (see test_p40e3a_qa_reconciliation.py's own docstring).
"""
from __future__ import annotations

import io
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_CASE_WORKSPACE_HTML_PATH = Path(__file__).resolve().parent.parent / "templates" / "case_workspace.html"
_JS_PATH = Path(__file__).resolve().parent.parent / "static" / "js" / "case_workspace.js"
_CSS_PATH = Path(__file__).resolve().parent.parent / "static" / "css" / "main.css"


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        import tempfile
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40vw1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="vw1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        self.doc = self._ingest(owner="vw1_owner", project_name="Riverside Terminal VW1 Workspace")
        self.project_id = self.doc.project_id

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, owner: str, project_name: str, filename: str = "rfp.txt"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )

        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(b"content", filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner=owner, project_name=project_name,
                )

    def _client_as(self, username, user_id, role="admin"):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = username
            sess["role"] = role
        return client

    def _store(self) -> CaseWorkspaceStore:
        return CaseWorkspaceStore(self.tmp_dir)


# ---------------------------------------------------------------------------
# The menu is hidden on initial render / a fresh request - both on the
# blank main Display and on a populated one.
# ---------------------------------------------------------------------------

class ContextMenuHiddenOnRenderTests(_BaseTestCase):
    # CLAUDE-P40-VW8-QA added data-ui-ref="display.context-menu" between
    # id="display-context-menu" and the hidden attribute these tests
    # look for - widened from a +60 to a +120 character window (still a
    # bounded slice around the opening tag, not a full-tag parse) so it
    # still reaches "hidden" with the extra attribute in between.
    def test_hidden_attribute_present_on_blank_main_display(self):
        client = self._client_as("vw1_owner", 1)
        body = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        menu_tag = body[body.index('id="display-context-menu"') - 60:body.index('id="display-context-menu"') + 120]
        self.assertIn("hidden", menu_tag)

    def test_hidden_attribute_present_on_populated_display(self):
        client = self._client_as("vw1_owner", 1)
        source_id = self._store().get(self.project_id).sources[0]["id"]
        body = client.get(f"/projects/{self.project_id}/workspace?source={source_id}").get_data(as_text=True)
        menu_tag = body[body.index('id="display-context-menu"') - 60:body.index('id="display-context-menu"') + 120]
        self.assertIn("hidden", menu_tag)

    def test_hidden_attribute_survives_a_second_fresh_request_unchanged(self):
        # Guards against any future regression that only hides the menu
        # once (e.g. a client-only fix) rather than on every fresh
        # server render - the same "fresh request" framing as the
        # Stable URL Restoration contract this stage must not disturb.
        client = self._client_as("vw1_owner", 1)
        first = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        second = client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        for body in (first, second):
            menu_tag = body[body.index('id="display-context-menu"') - 60:body.index('id="display-context-menu"') + 120]
            self.assertIn("hidden", menu_tag)


# ---------------------------------------------------------------------------
# Root-cause CSS fix: the [hidden] override rule exists and out-specifies
# the base display:flex rule, and no other rule re-introduces the bug.
# ---------------------------------------------------------------------------

class ContextMenuCssHiddenOverrideTests(unittest.TestCase):
    def setUp(self):
        self.css = _CSS_PATH.read_text(encoding="utf-8")

    def test_hidden_override_rule_exists(self):
        self.assertRegex(
            self.css,
            r"\.display-context-menu\[hidden\]\s*\{[^}]*display:\s*none",
        )

    def test_base_rule_still_uses_flex_for_the_open_state(self):
        # The fix must not remove the open-state layout - only add the
        # hidden-state override.
        self.assertRegex(
            self.css,
            r"\.display-context-menu\s*\{[^}]*display:\s*flex",
        )

    def test_only_one_display_context_menu_base_selector_exists(self):
        # No duplicate/conflicting rule was introduced that could
        # re-shadow the [hidden] override depending on source order.
        base_selectors = re.findall(r"^\.display-context-menu\s*\{", self.css, re.M)
        self.assertEqual(len(base_selectors), 1)


# ---------------------------------------------------------------------------
# JS wiring: open/close/target/Escape/outside-click/Apply/Close dismissal
# and viewport clamping remain intact and untouched by this correction.
# ---------------------------------------------------------------------------

class ContextMenuJsWiringUnchangedTests(unittest.TestCase):
    def setUp(self):
        self.js = _JS_PATH.read_text(encoding="utf-8")

    def test_contextmenu_listener_bound_per_division_not_globally(self):
        # Right-clicking outside a Display must not open the menu - the
        # listener lives on each .display-division element, not on
        # document, so the native menu stays intact everywhere else.
        self.assertIn("division.addEventListener('contextmenu'", self.js)
        self.assertNotIn("document.addEventListener('contextmenu'", self.js)

    def test_native_context_menu_suppressed_only_inside_open_menu_handler(self):
        self.assertRegex(
            self.js,
            r"addEventListener\('contextmenu',\s*\(e\)\s*=>\s*\{\s*e\.preventDefault\(\);\s*openMenu\(",
        )

    def test_open_menu_targets_the_clicked_division_and_pointer_position(self):
        self.assertIn("openMenu(e.clientX, e.clientY, parseInt(division.dataset.division, 10))", self.js)

    def test_open_menu_sets_hidden_false_and_clamps_to_viewport(self):
        self.assertIn("menu.hidden = false;", self.js)
        self.assertIn("const maxLeft = window.innerWidth - menu.offsetWidth - margin;", self.js)
        self.assertIn("const maxTop = window.innerHeight - menu.offsetHeight - margin;", self.js)

    def test_close_menu_sets_hidden_true(self):
        self.assertIn("function closeMenu() { menu.hidden = true; menuDivisionIndex = null; }", self.js)

    def test_outside_click_dismisses(self):
        self.assertIn("if (!menu.hidden && !menu.contains(e.target)) closeMenu();", self.js)

    def test_escape_key_dismisses(self):
        self.assertIn("if (e.key === 'Escape' && !menu.hidden) closeMenu();", self.js)

    def test_apply_and_close_both_call_close_menu(self):
        apply_block = self.js[self.js.index("if (applyBtn) applyBtn.addEventListener"):]
        apply_block = apply_block[:apply_block.index("})();")]
        self.assertIn("closeMenu();", apply_block)
        # CLAUDE-P40-VW4: decBtn/incBtn (single shared quantity) renamed
        # to vDec/vInc/hDec/hInc (two independent axes, also present in
        # the EARLIER top-bar IIFE under the same names - search for
        # "if (vDec)" starting from closeBtn's own position, not index
        # 0, or this finds the wrong (top-bar) occurrence). See that
        # stage's own test file for the new steppers' own coverage.
        close_start = self.js.index("if (closeBtn) closeBtn.addEventListener")
        close_block = self.js[close_start:self.js.index("if (vDec)", close_start)]
        self.assertIn("closeMenu();", close_block)

    def test_global_display_layout_menu_control_untouched(self):
        # Existing global Display Layout control (top-bar <details> menu)
        # is a separate mechanism this stage must not alter.
        self.assertIn("wireTopBarLayoutControl", self.js)


if __name__ == "__main__":
    unittest.main()
