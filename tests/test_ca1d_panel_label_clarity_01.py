"""
CLAUDE-CA1D-PANEL-LABEL-CLARITY-01 - remove redundant visible text from
panel maximize/expand toggle buttons.

Covers a live product-owner observation: the Thumbnails, Toolbox, and Eye
panel headers, plus the Composer's own size toggle, each carried a plain-
text label stating the obvious ("Maximize", "Maximize Toolbox",
"Maximize Eye", "Expand") right next to a panel whose name/heading is
already visible immediately beside it. Fixed by replacing the VISIBLE
text with a small resize-icon glyph (U+2922 NORTH EAST AND SOUTH WEST
ARROW / U+2921 NORTH WEST AND SOUTH EAST ARROW for the two toggle
states) while leaving every aria-label completely unchanged - this is a
visible-clutter fix, not an accessibility change; the accessible name a
screen reader announces is identical to before.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import unittest
from pathlib import Path

_BASE_HTML_PATH = Path(__file__).parent.parent / "templates" / "base.html"
_MACROS_HTML_PATH = Path(__file__).parent.parent / "templates" / "_macros.html"
_CASE_WORKSPACE_JS_PATH = Path(__file__).parent.parent / "static" / "js" / "case_workspace.js"

# Templates use the numeric HTML entity form; case_workspace.js (a plain
# JS string literal, not markup) uses the literal Unicode character - both
# resolve to the same two glyphs (verified via Python's unicodedata: U+2922
# NORTH EAST AND SOUTH WEST ARROW / U+2921 NORTH WEST AND SOUTH EAST ARROW).
EXPAND_ICON_ENTITY = "&#10530;"
COMPACT_ICON_ENTITY = "&#10529;"
EXPAND_ICON = "⤢"
COMPACT_ICON = "⤡"


class PanelToggleVisibleTextRemovedTests(unittest.TestCase):
    """Static template/JS assertions - no app context needed, these are
    plain source-file checks like this codebase's other CSS/markup
    regression tests (e.g. test_p40eye1_correction_resize_canvas.py)."""

    def setUp(self):
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")
        self.macros_html = _MACROS_HTML_PATH.read_text(encoding="utf-8")
        self.case_workspace_js = _CASE_WORKSPACE_JS_PATH.read_text(encoding="utf-8")

    def test_no_bare_maximize_or_expand_word_remains_visible(self):
        for leaked_word in (">Maximize<", ">Maximize Toolbox<", ">Maximize Eye<", ">Expand<"):
            self.assertNotIn(leaked_word, self.base_html, leaked_word)
            self.assertNotIn(leaked_word, self.macros_html, leaked_word)

    def test_thumbnails_button_shows_icon_and_keeps_its_aria_label(self):
        start = self.base_html.index('id="thumbnails-maximize-btn"')
        end = self.base_html.index("</button>", start)
        tag = self.base_html[start:end]
        self.assertIn(EXPAND_ICON_ENTITY, tag)
        self.assertIn('aria-label="Maximize the Thumbnails pane"', tag)

    def test_toolbox_button_shows_icon_and_keeps_its_aria_label(self):
        start = self.base_html.index('id="toolbox-maximize-btn"')
        end = self.base_html.index("</button>", start)
        tag = self.base_html[start:end]
        self.assertIn(EXPAND_ICON_ENTITY, tag)
        self.assertIn('aria-label="Maximize Toolbox"', tag)

    def test_eye_button_shows_icon_and_keeps_its_aria_label(self):
        start = self.base_html.index('id="eye-maximize-btn"')
        end = self.base_html.index("</button>", start)
        tag = self.base_html[start:end]
        self.assertIn(EXPAND_ICON_ENTITY, tag)
        self.assertIn('aria-label="Maximize Eye"', tag)

    def test_composer_toggle_shows_icon_and_has_an_explicit_initial_aria_label(self):
        start = self.macros_html.index('id="conversation-size-toggle"')
        end = self.macros_html.index("</button>", start)
        tag = self.macros_html[start:end]
        self.assertIn(EXPAND_ICON_ENTITY, tag)
        self.assertIn('aria-label="Expand the conversation panel"', tag)

    def test_toggle_js_swaps_icons_not_words_while_aria_labels_stay_descriptive(self):
        # Thumbnails toggle (inline script in base.html)
        self.assertIn(f"maximizeBtn.textContent = '{EXPAND_ICON}';", self.base_html)
        self.assertIn(f"maximizeBtn.textContent = '{COMPACT_ICON}';", self.base_html)
        self.assertIn("maximizeBtn.setAttribute('aria-label', 'Maximize the Thumbnails pane');", self.base_html)
        self.assertIn("maximizeBtn.setAttribute('aria-label', 'Restore the Lists/Thumbnails split');", self.base_html)

        # Shared Toolbox/Eye toggleMaximize() - the icon replaces the word,
        # but the label params (actionLabel/restoreLabel) still build the
        # exact same aria-label text as before this tranche.
        self.assertIn(f"btn.textContent = '{EXPAND_ICON}';", self.base_html)
        self.assertIn(f"btn.textContent = '{COMPACT_ICON}';", self.base_html)
        self.assertIn("btn.setAttribute('aria-label', actionLabel + ' the right column');", self.base_html)
        self.assertIn("btn.setAttribute('aria-label', restoreLabel + ' the Toolbox/Eye split');", self.base_html)

        # Eye's own dedicated toggleEyeMaximize()
        self.assertIn(f"eyeMaximizeBtn.textContent = '{EXPAND_ICON}';", self.base_html)
        self.assertIn(f"eyeMaximizeBtn.textContent = '{COMPACT_ICON}';", self.base_html)
        self.assertIn("eyeMaximizeBtn.setAttribute('aria-label', 'Maximize Eye');", self.base_html)
        self.assertIn("eyeMaximizeBtn.setAttribute('aria-label', 'Restore Eye');", self.base_html)

    def test_composer_size_toggle_js_swaps_icons_while_aria_label_stays_descriptive(self):
        self.assertIn(
            f"sizeToggle.textContent = isExpanded ? '{COMPACT_ICON}' : '{EXPAND_ICON}';",
            self.case_workspace_js,
        )
        self.assertIn(
            "sizeToggle.setAttribute('aria-label', isExpanded ? 'Compact the conversation panel' : 'Expand the conversation panel');",
            self.case_workspace_js,
        )


class PanelDividersRemainIconOnlyPrecedentTests(unittest.TestCase):
    """Confirms this tranche didn't have to touch the Lists/Toolbox
    collapse dividers - they were already icon-only (empty button
    content, aria-label only), the exact pattern this tranche now
    extends to the maximize/expand toggles."""

    def setUp(self):
        self.base_html = _BASE_HTML_PATH.read_text(encoding="utf-8")

    def test_panel_dividers_already_had_no_visible_text(self):
        for div_id in ("lists-divider", "toolbox-divider"):
            start = self.base_html.index(f'id="{div_id}"')
            end = self.base_html.index("</button>", start)
            tag_and_gap = self.base_html[start:end]
            # The divider's own opening tag has no text node before
            # </button> - i.e. it closes immediately after its attributes.
            self.assertTrue(tag_and_gap.rstrip().endswith(">"))


if __name__ == "__main__":
    unittest.main()
