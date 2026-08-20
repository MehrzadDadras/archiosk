"""
CLAUDE-P40-EYE1 - Full-Height Right Column and Eye Structural Scaffold.

Converts the right-side workspace region into a true full-height column
beneath the application header, divided into Toolbox (upper) and a new
Eye pane (lower) - a structural scaffold only, not a completed tool
(Section 4's own explicit boundary: no image editing, annotation, chat/
terminal attachment, AI interpretation, persistence, or ingestion this
stage).

Mirrors CLAUDE-P40-VW7A-QA2's Lists/Thumbnails split on the opposite
side of the shell: .workspace-right-column is now a sibling of Lists
AND .workspace-main-column inside .app-shell-body, so it spans the same
vertical extent as Display+Chat combined, never stopping at the
Display/Chat divider. Toolbox moved out of .workspace-main-column
entirely (it used to share a row there with Display) into this new
column; .workspace-content-row, left with only .app-main as a child
once Toolbox moved out, was removed rather than kept as dead CSS.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source and rendered-HTML structure, the same practical
ceiling this repo's prior stages have already established.
"""
from __future__ import annotations

import io
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import unittest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument
from services.environment_capabilities import CLIENT_OWNER
from services.ingestion import ingest_upload

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_EYE_PANE_JS_PATH = _REPO_ROOT / "static" / "js" / "eye_pane.js"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(re.escape(selector) + r"(?![\w\-\"])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


def _fake_file(content: bytes, filename: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content), filename=filename)


class _BaseTestCase(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_eye1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        with self.flask_app.app_context():
            db.session.add(User(username="eye1_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _ingest(self, project_name, filename, content=b"content"):
        def fake_parse(self_parser, raw_bytes, filename_):
            return ParsedDocument(
                project_id=str(uuid.uuid4()), filename=filename_,
                ingested_at=datetime.now(timezone.utc).isoformat(), parser_version="test",
            )
        with patch.object(BHiveParser, "parse", fake_parse):
            with self.flask_app.app_context():
                return ingest_upload(
                    _fake_file(content, filename), self.flask_app,
                    operating_environment=CLIENT_OWNER, owner="eye1_owner", project_name=project_name,
                )

    def _client(self):
        client = self.flask_app.test_client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "eye1_owner"
            sess["role"] = "admin"
        return client


class RightColumnStructureTests(_BaseTestCase):
    def test_right_column_and_eye_pane_render_in_workspace(self):
        doc = self._ingest("EYE1 Project 1", "spec.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('id="workspace-right-column"', body)
        self.assertIn('id="eye-pane"', body)
        self.assertIn('id="toolbox-eye-divider"', body)
        self.assertIn('id="workspace-toolbox-panel"', body)

    def test_eye_renders_before_divider_before_toolbox_in_dom_order(self):
        # CLAUDE-EYE-TOOLBOX-LAYOUT-01 flipped this order (was Toolbox
        # above/Eye below) - Product Owner: "Eye above = current guidance,
        # comparison state, findings, next-step instruction; Toolbox
        # below = persistent working tool/mode." Renamed from
        # test_toolbox_renders_before_divider_before_eye_in_dom_order
        # rather than left silently reversed - same assertion shape, new
        # expected order.
        doc = self._ingest("EYE1 Project 2", "spec.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        eye_idx = body.index('id="eye-pane"')
        divider_idx = body.index('id="toolbox-eye-divider"')
        toolbox_idx = body.index('id="workspace-toolbox-panel"')
        self.assertLess(eye_idx, divider_idx)
        self.assertLess(divider_idx, toolbox_idx)

    def test_right_column_absent_outside_an_open_workspace(self):
        client = self._client()
        for url in ("/", "/projects", "/upload", "/removed-projects"):
            body = client.get(url).get_data(as_text=True)
            self.assertNotIn('id="workspace-right-column"', body, url)
            self.assertNotIn('id="eye-pane"', body, url)

    def test_right_column_never_stops_at_the_display_chat_divider(self):
        # Section 1's own explicit requirement, verified structurally:
        # .workspace-right-column must be a sibling of BOTH .launcher-
        # panel and .workspace-main-column inside .app-shell-body (never
        # nested inside .workspace-main-column itself, which would
        # confine it to Display's row and exclude Chat's).
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        app_shell_body_idx = html.index('<div class="app-shell-body">')
        main_column_open = html.index('<div class="workspace-main-column">')
        main_column_close = html.index("</div>", html.index('<div class="chat-region"'))
        right_column_open = html.index('<div class="workspace-right-column"')
        self.assertGreater(right_column_open, main_column_close)
        self.assertGreater(main_column_open, app_shell_body_idx)


class RightColumnCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_right_column_is_a_real_full_height_flex_column(self):
        # Anchored to line-start so this matches only the standalone
        # base selector, not html.toolbox-hidden .workspace-right-column
        # (display:none) or the narrow-viewport override, both of which
        # also contain this class name and appear earlier in the file.
        rule = re.search(r"^\.workspace-right-column\s*\{[^}]*\}", self.css, re.M | re.S)
        self.assertIsNotNone(rule, "no base .workspace-right-column rule found")
        body = rule.group(0)
        self.assertIn("display: flex", body)
        self.assertIn("flex-direction: column", body)
        self.assertIn("height: 100%", body)
        self.assertIn("var(--surface-primary)", body)

    def test_toolbox_pane_no_longer_owns_width_or_background(self):
        body = _rule_body(self.css, ".workspace-pane-toolbox")
        self.assertIsNone(re.search(r"(?<!-)\bwidth:", body), body)
        self.assertNotIn("background:", body)
        self.assertIn("var(--toolbox-height", body)

    def test_eye_pane_takes_remaining_space(self):
        body = _rule_body(self.css, ".eye-pane")
        self.assertIn("flex: 1 1 auto", body)

    def test_workspace_content_row_is_gone_not_dead_css(self):
        self.assertNotIn(".workspace-content-row {", self.css)


class ToolboxEyeDividerTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_divider_markup_is_keyboard_operable(self):
        idx = self.html.index('id="toolbox-eye-divider"')
        tag = self.html[self.html.rindex("<div", 0, idx):self.html.index(">", idx)]
        self.assertIn('role="separator"', tag)
        self.assertIn('aria-orientation="horizontal"', tag)
        self.assertIn('tabindex="0"', tag)
        self.assertNotIn("hidden", tag)  # Eye is permanent - never [hidden]

    def test_divider_drag_and_keyboard_logic_present(self):
        script = self.html[self.html.index("var divider = document.getElementById('toolbox-eye-divider')"):]
        script = script[:script.index("})();")]
        self.assertIn("pointerdown", script)
        self.assertIn("pointermove", script)
        self.assertIn("ArrowUp", script)
        self.assertIn("ArrowDown", script)
        self.assertIn("'Home'", script)
        self.assertIn("'End'", script)
        self.assertIn("dblclick", script)

    def test_persistence_uses_localstorage_per_project(self):
        # Section 2's own "remember the user's last practical division
        # using the lightest existing browser-preference mechanism" -
        # matching Toolbox's OWN existing per-Project localStorage
        # scoping (beehive:panel:toolbox:{{ project_id }}), not Lists/
        # Thumbnails' reviewer-wide sessionStorage.
        self.assertIn("var heightKey = 'beehive:panel:toolbox-eye:{{ project_id }}';", self.html)
        self.assertIn("window.localStorage.setItem(heightKey", self.html)

    def test_divider_appearance_is_token_based_not_transparent(self):
        body = _rule_body(self.css, ".toolbox-eye-divider")
        self.assertIn("var(--surface-primary)", body)
        declaration = re.search(r"background:\s*[^;]+;", body).group(0)
        self.assertNotIn("transparent", declaration)

    def test_divider_line_is_persistent_and_uses_the_border_token(self):
        body = _rule_body(self.css, ".toolbox-eye-divider::before")
        self.assertIn("left: 0", body)
        self.assertIn("right: 0", body)
        self.assertIn("height: 1px", body)
        self.assertIn("background: var(--border)", body)
        self.assertIn("opacity: 1", body)

    def test_divider_accent_only_on_hover_focus_or_active_drag(self):
        for selector in (".toolbox-eye-divider:hover::before", ".toolbox-eye-divider:focus-visible::before"):
            body = _rule_body(self.css, selector)
            self.assertIn("var(--machine-blue)", body)
        combined = _rule_body(
            self.css,
            ".toolbox-eye-divider:hover::before,\n.toolbox-eye-divider:focus-visible::before,\n.toolbox-eye-divider.dragging::before",
        )
        self.assertIn("var(--machine-blue)", combined)

    def test_no_opacity_based_parent_trick(self):
        for selector in (".toolbox-eye-divider", ".workspace-right-column", ".eye-pane", ".workspace-pane-toolbox"):
            body = _rule_body(self.css, selector)
            self.assertNotIn("opacity", body, selector)


class ToolboxEyeCollapseRestoreTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_maximize_toolbox_and_maximize_eye_buttons_exist(self):
        self.assertIn('id="toolbox-maximize-btn"', self.html)
        self.assertIn('id="eye-maximize-btn"', self.html)

    def test_maximize_buttons_start_unpressed(self):
        for control_id in ("toolbox-maximize-btn", "eye-maximize-btn"):
            idx = self.html.index(f'id="{control_id}"')
            tag = self.html[self.html.rindex("<button", 0, idx):self.html.index(">", idx)]
            self.assertIn('aria-pressed="false"', tag)

    def test_either_pane_can_be_practically_collapsed_via_min_max(self):
        # Section 2's own "either pane can be reduced to its practical
        # minimum" / "permit Toolbox to be minimized so Eye can occupy
        # almost the entire column" and the reverse - real MIN_PCT/
        # MAX_PCT bounds, not merely a UI label with no effect.
        self.assertIn("var MIN_PCT = 8;", self.html)
        self.assertIn("var MAX_PCT = 92;", self.html)
        self.assertIn("function toggleMaximize(btn, targetPct, restoreLabel, actionLabel)", self.html)


class RightColumnHideShowTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_hidden_rule_targets_the_whole_column(self):
        self.assertIn("display: none", _rule_body(self.css, "html.toolbox-hidden .workspace-right-column"))
        # Not the old, narrower target.
        self.assertNotIn("html.toolbox-hidden .workspace-pane-toolbox", self.css)

    def test_display_reclaims_released_width_automatically(self):
        # No column-count/grid recompute needed - Display (.app-main)
        # is flex:1 inside .app-shell-body, so display:none on its
        # sibling column is sufficient on its own (same mechanism Lists'
        # own hide/show already relies on).
        self.assertIn("flex: 1", _rule_body(self.css, ".app-main"))

    def test_narrow_viewport_drawer_targets_the_whole_column(self):
        media_idx = self.css.rindex("@media (max-width: 640px) {\n    .workspace-right-column {")
        self.assertGreater(media_idx, 0)
        tail = self.css[media_idx:media_idx + 400]
        self.assertIn("position: fixed", tail)
        self.assertNotIn(".workspace-pane-toolbox {\n        position: fixed", self.css)


class EyeScaffoldMarkupTests(_BaseTestCase):
    def test_eye_heading_empty_state_and_drop_target_render(self):
        doc = self._ingest("EYE1 Scaffold Project", "spec.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn(">Eye<", body)
        self.assertIn('id="eye-drop-target"', body)
        self.assertIn('id="eye-drop-target-empty"', body)
        # CLAUDE-EYE-SURFACE-CORRECTION-01 (Product Owner: "Eye is not an
        # image-drop utility... Eye is the persistent secondary working/
        # context surface") superseded the old "Paste or drop an image
        # here to preview it." default text - that copy made paste/drop
        # read as Eye's whole identity rather than one of its
        # capabilities. static/js/eye_pane.js's own updateEmptyStateText()
        # still swaps this for "Choose a document to compare." while
        # Compare is active - see test_appearance_simplify_01_... or the
        # Eye/Compare test coverage for that behavior, unchanged by this
        # correction.
        self.assertIn("Eye — secondary context surface", body)
        self.assertIn("Not saved", body)

    def test_drop_target_is_a_real_focusable_group_not_a_decorative_div(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        idx = html.index('id="eye-drop-target"')
        tag = html[html.rindex("<div", 0, idx):html.index(">", idx)]
        self.assertIn('role="group"', tag)
        self.assertIn('tabindex="0"', tag)
        self.assertIn("aria-label=", tag)

    def test_no_misleading_unbuilt_controls_present(self):
        # Section 4's own explicit "no misleading controls that do not
        # work" - none of the deferred-to-EYE2 feature names should
        # appear as a control id/data-ui-ref anywhere in the Eye pane.
        doc = self._ingest("EYE1 No Misleading Project", "spec.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        eye_start = body.index('id="eye-pane"')
        eye_end = body.index("</div>", body.index("</div>", body.index("</div>", eye_start)))
        eye_region = body[eye_start:eye_end]
        for forbidden in ("annotate", "edit", "attach-to-chat", "attach-terminal", "analyze", "save", "export", "ingest"):
            self.assertNotIn(forbidden, eye_region.lower(), forbidden)


class EyePaneJsTests(unittest.TestCase):
    def setUp(self):
        self.js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")

    def test_real_drag_and_drop_and_paste_handlers_present(self):
        self.assertIn("addEventListener('dragover'", self.js)
        self.assertIn("addEventListener('drop'", self.js)
        self.assertIn("addEventListener('paste'", self.js)

    def test_non_image_input_shows_a_real_error_not_silent_failure(self):
        self.assertIn("Only images are supported here.", self.js)
        self.assertIn("Clipboard did not contain an image.", self.js)

    def test_preview_is_client_side_only_until_the_reviewer_explicitly_saves(self):
        # CLAUDE-MM5 Section 7: "Save to project" is a real, intended
        # network action now - narrowed to the real, still-true
        # invariant: pasting/dropping (handleFile) never itself triggers
        # a network call; fetch() exists in this file now, but only
        # inside saveToProject, reached solely by an explicit click on
        # #eye-save-btn. See tests/test_p40eye1_correction_resize_
        # canvas.py's own matching correction for the fuller rationale.
        code_only = self.js[self.js.index("*/") + 2:]
        self.assertNotIn("XMLHttpRequest", code_only)
        self.assertIn("FileReader", code_only)
        handle_file_fn = self.js[self.js.index("function handleFile("):self.js.index("dropTarget.addEventListener('dragover'")]
        self.assertNotIn("fetch(", handle_file_fn)
        save_fn = self.js[self.js.index("function saveToProject("):self.js.index("// -------- Zoom / fit / pan")]
        self.assertIn("fetch(", save_fn)

    def test_remove_control_returns_to_the_neutral_empty_state(self):
        self.assertIn("function clearPreview()", self.js)
        self.assertIn("emptyState.hidden = false", self.js)

    def test_script_is_included_from_base_html_only_within_an_open_workspace(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        script_idx = html.index("js/eye_pane.js")
        guard_idx = html.rindex("{% if project_id is defined and workspace is defined %}", 0, script_idx)
        endif_idx = html.index("{% endif %}", script_idx)
        self.assertGreater(script_idx, guard_idx)
        self.assertLess(script_idx, endif_idx)


class ExistingBehaviorPreservedTests(_BaseTestCase):
    def test_toolbox_heading_and_content_still_render_unchanged(self):
        doc = self._ingest("EYE1 Preserve Project", "spec.txt")
        client = self._client()
        body = client.get(f"/projects/{doc.project_id}/workspace").get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.heading"', body)
        self.assertIn(">Toolbox<", body)

    def test_chat_composer_bottom_margin_still_intact(self):
        # CLAUDE-P40-VW7A-QA2 (browser correction) fix must survive this
        # stage's own restructuring unchanged.
        css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        body = _rule_body(css, ".conversation-input-form")
        self.assertIn("padding-bottom: var(--conversation-inset)", body)

    def test_pdf_document_controls_still_present(self):
        # CLAUDE-P40-VW7A-QA/-QA2's own document-controls region must be
        # untouched by this stage.
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="workspace-document-controls"', html)
        self.assertIn('id="doc-annotate-undo"', html)

    def test_lists_thumbnails_split_still_present(self):
        html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.assertIn('id="lists-pane"', html)
        self.assertIn('id="thumbnails-pane"', html)


if __name__ == "__main__":
    unittest.main()
