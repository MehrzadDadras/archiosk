"""
CLAUDE-MAIN-DISPLAY-SCROLL-SIMPLIFICATION-01 - one scroll owner for the
Main document area.

Root cause: main's own general-purpose `overflow-y: auto`
(CLAUDE-P40-VW8-QA - "the ONE scroll region for every page's actual
content") became a redundant SECOND vertical scrolling surface
whenever a PDF Document was the active Display content, since
.document-viewer-canvas-container already provides its own real,
independently-bounded (fixed 70vh height) internal scroll region for
the rendered page. "The document moves. The workspace does not."

Fix is scoped narrowly, via :has() (an already-established technique
in this file), to the PDF-viewing content shape specifically - every
other page (Investigation/Overview/forms/Project Data Management/etc)
keeps main's own whole-content scroll exactly as CLAUDE-P40-VW8-QA
intended.

No real browser tool exists in this environment - coverage here is
CSS source structure, the same practical ceiling this repo's prior
layout stages already use.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


def _rule_body(css: str, selector: str) -> str:
    needle = re.compile(re.escape(selector) + r"(?![\w\-\"])")
    pos = 0
    while True:
        match = needle.search(css, pos)
        assert match, f"no CSS rule found for selector {selector!r}"
        brace_open = css.index("{", match.end())
        between = css[match.end():brace_open]
        if re.fullmatch(r'[\w\s,.#\[\]"=\-:>()]*', between):
            brace_close = css.index("}", brace_open)
            return css[brace_open + 1:brace_close]
        pos = match.end()


class MainScrollOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_base_main_still_scrolls_for_every_other_page(self):
        # CLAUDE-P40-VW8-QA's own rule must survive unchanged for
        # Investigation/Overview/forms/etc - only narrowed, not removed.
        body = _rule_body(self.css, "\nmain ")
        self.assertIn("overflow-y: auto", body)

    def test_main_scroll_is_a_real_removal_not_cosmetic_when_pdf_active(self):
        body = _rule_body(self.css, "main:has(.document-viewer-canvas-container)")
        self.assertIn("overflow-y: hidden", body)
        # A real mechanism removal, not scrollbar-only cosmetics (no
        # scrollbar-width/::-webkit-scrollbar hiding trick substituted).
        self.assertNotIn("scrollbar-width", body)

    def test_document_viewer_canvas_container_keeps_its_own_independent_scroll(self):
        # The RED (keep) scrollbar - unaffected by this stage, still a
        # real, independently-bounded (fixed height, not flex-grown from
        # main) scroll region of its own.
        body = _rule_body(self.css, "\n.document-viewer-canvas-container ")
        self.assertIn("overflow: auto", body)
        self.assertIn("height: 70vh", body)

    def test_app_main_remains_a_pure_non_scrolling_layout_wrapper(self):
        # Unaffected ancestor - still never a scroll context of its own.
        body = _rule_body(self.css, ".app-main")
        self.assertIn("overflow: hidden", body)


if __name__ == "__main__":
    unittest.main()
