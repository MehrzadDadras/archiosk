"""
CLAUDE-DOCUMENT-RAIL-PROBE-EYE-TOOL-01 (+ its two follow-up addenda on
document-row control order) - the final left-rail document-row grammar:

    Name (probe) -> [ ] Mark -> > Keep -> Eye -> Tool

Two of Part 2/12's own requirements ("filename click is a transient
probe, not a permanent tab" and "if a keep/open-as-tab mechanism
already exists, preserve it, don't invent a new one") turned out to
already be fully satisfied by static/js/document_tabs.js's own pre-
existing preview/pinned-tab system (confirmed by direct code audit
before writing anything new) - this stage's own genuinely new work is
the PM Mark shortlist, the Marked filter, the Eye dashed-outline visual
(replacing the earlier filled-color treatment), and exposing that
existing pinTab() mechanism as a direct per-row "Keep" control.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source structure, this repo's own established ceiling.
The live interaction (probe replacing probe without destroying a
retained tab, marks surviving navigation, Eye's dashed state, Eye-to-
Main auto-clear, Keep promoting a probe to a retained tab) was verified
directly on archiosk.com as part of this stage's own required live
proof, not re-asserted here.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_DOCUMENT_TABS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_tabs.js"
_DOCUMENT_MARKS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_marks.js"
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


class RowControlOrderTests(unittest.TestCase):
    """Final addendum: Name -> Mark -> Keep -> Eye -> Tool, in that
    exact relative order, on every Document row."""

    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        # Isolate one representative <li> so index comparisons can't
        # accidentally cross into an unrelated row/section.
        start = self.html.index('<li class="tree-node tree-node-document"')
        end = self.html.index("</li>", start)
        self.row = self.html[start:end]

    def test_name_precedes_mark(self):
        self.assertLess(self.row.index('class="tree-leaf'), self.row.index('class="pm-mark-checkbox'))

    def test_mark_precedes_keep(self):
        self.assertLess(self.row.index('class="pm-mark-checkbox'), self.row.index('class="keep-open-btn'))

    def test_keep_precedes_eye(self):
        self.assertLess(self.row.index('class="keep-open-btn'), self.row.index('class="eye-send-btn'))

    def test_eye_precedes_tool(self):
        self.assertLess(self.row.index('class="eye-send-btn'), self.row.index('class="toolbox-send-btn'))

    def test_only_one_checkbox_control_on_the_row(self):
        # "Do not use two square controls" - Keep must be a button
        # (triangle glyph), never a second <input type="checkbox">.
        self.assertEqual(self.row.count('type="checkbox"'), 1)

    def test_keep_button_is_not_a_checkbox(self):
        keep_idx = self.row.index('class="keep-open-btn')
        tag_start = self.row.rindex("<", 0, keep_idx)
        tag = self.row[tag_start:self.row.index(">", tag_start) + 1]
        self.assertIn("<button", tag)

    def test_keep_glyph_is_a_triangle_not_a_square(self):
        match = re.search(r'class="keep-open-btn"[^>]*>([^<]*)</button>', self.row)
        self.assertIsNotNone(match)
        self.assertIn("&#9656;", match.group(0))


class PmMarkStructureTests(unittest.TestCase):
    def setUp(self):
        self.js = _DOCUMENT_MARKS_JS_PATH.read_text(encoding="utf-8")

    def test_marks_scoped_by_username_and_project(self):
        self.assertIn("var MARKS_KEY = 'beehive:marks:' + username + ':' + projectId;", self.js)

    def test_marks_reconciled_against_active_sources_on_load(self):
        body = self.js[self.js.index("var known = activeSourceIds();"):]
        body = body[:body.index("var markedSet")]
        self.assertIn("marks.filter(function (id) { return known[id]; });", body)

    def test_checkbox_change_persists_and_does_not_bubble(self):
        self.assertIn("cb.addEventListener('click', function (e) { e.stopPropagation(); });", self.js)
        self.assertIn("setMarked(cb.getAttribute('data-source-id'), cb.checked);", self.js)

    def test_marked_filter_is_pure_row_hide_no_navigation(self):
        # CLAUDE-DOCUMENT-RAIL-SEARCH-01 folded search into this same
        # function (Marked + search must compose, not compete - see
        # test_document_rail_search_01.py's own coverage of that) - this
        # guard now checks the combined predicate, same "pure row-hide,
        # no navigation" property.
        body = self.js[self.js.index("function applyFilter()"):]
        body = body[:body.index("\n    }\n\n    if (searchInput)")]
        self.assertIn("var matchesMarked = !filterActive || isMarked(cb.getAttribute('data-source-id'));", body)
        self.assertIn("row.hidden = !visible;", body)
        self.assertNotIn("location.href", body)

    def test_exposes_read_only_lookup_for_future_search_integration(self):
        self.assertIn("window.ArchioskDocumentMarks = { isMarked: isMarked, isFilterActive: function () { return filterActive; } };", self.js)


class KeepOpenStructureTests(unittest.TestCase):
    def setUp(self):
        self.js = _DOCUMENT_TABS_JS_PATH.read_text(encoding="utf-8")

    def test_keep_button_click_calls_existing_pin_tab(self):
        idx = self.js.index("Array.prototype.forEach.call(keepOpenButtons, function (btn) {\n        btn.addEventListener")
        body = self.js[idx:idx + 300]
        self.assertIn("pinTab(btn.getAttribute('data-source-id'));", body)

    def test_keep_button_state_synced_from_render(self):
        body = self.js[self.js.index("function render()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("syncKeepOpenButtons();", body)

    def test_sync_reflects_real_pinned_state_not_a_separate_flag(self):
        body = self.js[self.js.index("function syncKeepOpenButtons()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("String(!!findPinned(btn.getAttribute('data-source-id')))", body)


class EyeDashedOutlineTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.eye_pane_js = _EYE_PANE_JS_PATH.read_text(encoding="utf-8")

    def test_eye_projected_is_outline_only_no_filled_background(self):
        body = _rule_body(self.css, ".tree-leaf.eye-projected")
        self.assertIn("dashed", body)
        self.assertNotIn("background", body)

    def test_update_eye_send_button_states_toggles_row_dashed_class(self):
        body = self.eye_pane_js[self.eye_pane_js.index("function updateEyeSendButtonStates()"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("leaf.classList.toggle('eye-projected', isActive);", body)


class ScriptLoadTests(unittest.TestCase):
    def test_document_marks_script_present_on_the_non_panel_only_path(self):
        html = (_REPO_ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
        self.assertIn("js/document_marks.js", html)


if __name__ == "__main__":
    unittest.main()
