"""
CLAUDE-DOCUMENT-RAIL-SEARCH-01 - Text | Image document discovery for
the left project folder/file rail.

Text mode: filename matching only, extended this stage to real
multi-word AND semantics, quoted-phrase exact-substring matching, and a
cheap exact-phrase-first ranking. A real, repo-wide audit before writing
this (services/bhive_parser.py, services/case_workspace.py) confirmed
no stored extracted document text exists anywhere (BHiveParser.parse()
extracts text once, in memory, to classify requirements, then discards
it) and no existing content-search route - #documents-search-status
states this limitation honestly on a zero-match search rather than
implying full document text was checked.

Image mode: a real, working paste/drop/preview/collapse tray - genuine
capture and state management, not scaffolding. "Search" deliberately
never calls any backend: services/image_intelligence.py's own header
comment ("no facial recognition, no object/defect detection, no OCR
over arbitrary image content... never interprets what an image
DEPICTS") is real, already-established evidence that no image/shape-
search capability exists anywhere in this codebase - governance/spare-
parts-yard.md records the real capability this preserves a UI path
toward, rather than faking results.

No real browser tool exists in this environment - coverage here is
template/CSS/JS source structure, this repo's own established ceiling.
The live interaction (multi-word AND, quoted phrases, marks/tabs
surviving search, Image tray paste/collapse/expand, honest deferred
image-search state) was verified directly on archiosk.com as part of
this stage's own required live proof, not re-asserted here.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BASE_HTML_PATH = _REPO_ROOT / "templates" / "base.html"
_DOCUMENT_MARKS_JS_PATH = _REPO_ROOT / "static" / "js" / "document_marks.js"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
_SPARE_PARTS_YARD_PATH = _REPO_ROOT / "governance" / "spare-parts-yard.md"


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


class MarkupTests(unittest.TestCase):
    def setUp(self):
        self.html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_mode_toggle_present_and_text_is_default_pressed(self):
        match = re.search(r'id="documents-search-mode-text"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn('aria-pressed="true"', match.group(0))
        match2 = re.search(r'id="documents-search-mode-image"[^>]*>', self.html)
        self.assertIsNotNone(match2)
        self.assertIn('aria-pressed="false"', match2.group(0))

    def test_mode_terms_are_text_and_image_not_visual(self):
        idx = self.html.index('id="documents-search-mode-image"')
        snippet = self.html[idx:idx + 200]
        self.assertIn(">Image<", snippet)
        self.assertNotIn("Visual", snippet)

    def test_search_input_present(self):
        self.assertIn('id="documents-search-input"', self.html)
        self.assertIn('type="search"', self.html)

    def test_image_tray_has_all_three_states_markup(self):
        self.assertIn('id="documents-image-search-tray"', self.html)
        self.assertIn('id="documents-image-search-empty"', self.html)
        self.assertIn('id="documents-image-search-preview"', self.html)
        self.assertIn('id="documents-image-search-collapsed"', self.html)

    def test_image_tray_starts_hidden_in_text_mode(self):
        match = re.search(r'<div class="documents-image-search-tray"[^>]*>', self.html)
        self.assertIsNotNone(match)
        self.assertIn("hidden", match.group(0))

    def test_search_field_comes_before_marked_filter(self):
        self.assertLess(
            self.html.index('id="documents-search-input"'),
            self.html.index('id="documents-marked-filter-btn"'),
        )

    def test_row_control_order_unaffected_by_search(self):
        start = self.html.index('<li class="tree-node tree-node-document"')
        end = self.html.index("</li>", start)
        row = self.html[start:end]
        self.assertLess(row.index('class="tree-leaf'), row.index('class="pm-mark-checkbox'))
        self.assertLess(row.index('class="pm-mark-checkbox'), row.index('class="keep-open-btn'))
        self.assertLess(row.index('class="keep-open-btn'), row.index('class="eye-send-btn'))


class TextSearchLogicTests(unittest.TestCase):
    def setUp(self):
        self.js = _DOCUMENT_MARKS_JS_PATH.read_text(encoding="utf-8")

    def test_parse_query_extracts_quoted_phrases_separately_from_bare_terms(self):
        body = self.js[self.js.index("function parseQuery("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn('raw.replace(/"([^"]+)"/g', body)
        self.assertIn("remainder.split(/\\s+/)", body)

    def test_row_matches_query_requires_every_phrase_and_term_and_semantics(self):
        body = self.js[self.js.index("function rowMatchesQuery("):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("for (var i = 0; i < parsed.phrases.length; i++)", body)
        self.assertIn("for (var j = 0; j < parsed.terms.length; j++)", body)
        self.assertIn("return false;", body)

    def test_exact_phrase_ranking_is_a_cheap_stable_sort_not_a_new_architecture(self):
        body = self.js[self.js.index("if (hasQuery) {"):self.js.index("if (hasQuery) {") + 400]
        self.assertIn("visibleEntries.sort(", body)
        self.assertIn("entry.row.parentNode.appendChild(entry.row);", body)

    def test_zero_match_status_is_honest_about_filename_only_scope(self):
        body = self.js[self.js.index("if (searchStatusEl) {"):]
        body = body[:body.index("\n    }\n")]
        self.assertIn("Document content search is not yet available", body)

    def test_search_never_calls_navigation(self):
        idx = self.js.index("function applyFilter()")
        end = self.js.index("if (searchInput) {", idx)
        body = self.js[idx:end]
        self.assertNotIn("location.href", body)

    def test_marked_filter_and_search_compose_with_and_semantics(self):
        body = self.js[self.js.index("function applyFilter()"):]
        body = body[:body.index("\n    }\n\n    if (searchInput)")]
        self.assertIn("var matchesSearch = !hasQuery || rowMatchesQuery(name, parsed);", body)
        self.assertIn("var matchesMarked = !filterActive || isMarked(cb.getAttribute('data-source-id'));", body)
        self.assertIn("var visible = matchesSearch && matchesMarked;", body)


class ImageModeLogicTests(unittest.TestCase):
    def setUp(self):
        self.js = _DOCUMENT_MARKS_JS_PATH.read_text(encoding="utf-8")

    def test_mode_switch_toggles_input_and_tray_visibility_only(self):
        body = self.js[self.js.index("function renderSearchMode()"):]
        body = body[:body.index("\n        }\n\n        function setSearchMode")]
        self.assertIn("searchInput.hidden = isImage;", body)
        self.assertNotIn("location.href", body)

    def test_paste_and_drop_load_a_real_image_file(self):
        self.assertIn("function loadImageFile(file)", self.js)
        self.assertIn("imageTray.addEventListener('paste'", self.js)
        self.assertIn("imageTray.addEventListener('drop'", self.js)
        self.assertIn("new FileReader()", self.js)

    def test_search_run_never_calls_a_backend(self):
        idx = self.js.index("if (imageRunBtn) {")
        body = self.js[idx:idx + 400]
        self.assertNotIn("fetch(", body)
        self.assertIn("imageIsCollapsed = true;", body)
        self.assertIn("imageStatusEl.hidden = false;", body)

    def test_clear_and_replace_never_call_a_backend(self):
        idx = self.js.index("function clearImageQuery()")
        body = self.js[idx:self.js.index("if (imageClearBtn)")]
        self.assertNotIn("fetch(", body)

    def test_expand_restores_full_tray_without_discarding_image(self):
        idx = self.js.index("if (imageExpandBtn)")
        body = self.js[idx:idx + 200]
        self.assertIn("imageIsCollapsed = false;", body)
        self.assertNotIn("imageDataUrl = null", body)


class ImageTraySearchCssTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_image_tray_is_not_a_permanent_enlargement(self):
        body = _rule_body(self.css, ".documents-image-search-tray")
        self.assertIn("min-height", body)
        self.assertNotIn("height: 100%", body)

    def test_search_mode_active_state_is_restrained(self):
        body = _rule_body(self.css, '.documents-search-mode-btn[aria-pressed="true"]')
        self.assertIn("machine-blue", body)

    def test_elements_toggled_via_hidden_respect_the_hidden_attribute(self):
        # Regression guard for the bug live verification on archiosk.com
        # caught immediately: an author `display` declaration on a
        # selector beats the UA stylesheet's own `[hidden] {display:
        # none}` (equal specificity, author rule comes later in cascade
        # order) unless an explicit `[hidden]` override is added - same
        # root cause, same fix, as CLAUDE-DUAL-DOCUMENT-FOCUS-01's own
        # .toolbox-eye-thumbnails-panel[hidden] fix earlier this session.
        # Every one of these selectors both declares its own `display`
        # AND is toggled via `.hidden = ...` in static/js/document_marks.js.
        for selector in (
            ".documents-image-search-tray",
            ".documents-image-search-preview",
            ".documents-image-search-collapsed",
            ".documents-search-input",
            # Found by the SAME live-verification pass: the Marked filter
            # (a CLAUDE-DOCUMENT-RAIL-PROBE-EYE-TOOL-01 feature, one
            # stage earlier) had been silently broken since it first
            # shipped - .tree-node-document's own row.hidden was always
            # set correctly in JS, but never actually hid anything
            # on screen until this fix.
            ".tree-node-document",
        ):
            with self.subTest(selector=selector):
                base_body = _rule_body(self.css, selector)
                self.assertIn("display", base_body, f"{selector} has no display rule to guard")
                override_body = _rule_body(self.css, selector + "[hidden]")
                self.assertIn("display: none", override_body)


class PartsYardRecordTests(unittest.TestCase):
    def test_visual_shape_search_future_reserve_record_exists(self):
        text = _SPARE_PARTS_YARD_PATH.read_text(encoding="utf-8")
        self.assertIn("Real image/shape/visual document search", text)
        self.assertIn("Future", text)
        self.assertIn("services/image_intelligence.py", text)


if __name__ == "__main__":
    unittest.main()
