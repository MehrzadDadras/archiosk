"""
CLAUDE-P40-EYE1 (product-owner browser correction) - Remaining Unthemed
Toolbox Scrollbar.

A real-browser screenshot found one nested scroll container inside the
upper-right Toolbox/Findings region still rendering the browser's own
default white-track/gray-thumb scrollbar, despite `.workspace-pane-
toolbox` already carrying a `scrollbar-color` declaration. Root cause:
`scrollbar-color` is the newer, standards-track property - Firefox has
always supported it, but Chromium/Edge only gained support in v121
(January 2024); on anything older, the property is silently ignored
and the browser falls back to its own default rendering, which exactly
matches "still white." Fix: add the WebKit/Chromium `::-webkit-
scrollbar` pseudo-element API (track/thumb/thumb:hover/thumb:active/
corner) ALONGSIDE the existing `scrollbar-color` on every real scroll
container in the app, not just the one specifically reported (Lists,
Thumbnails, Toolbox, Eye's own body and its image-canvas viewport,
Display's `<main>` and its PDF canvas container, Chat's message
thread).

No real browser tool exists in this environment - coverage here is
CSS source inspection.
"""
from __future__ import annotations

import re
from pathlib import Path

import unittest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"

_SCROLL_CONTAINERS = (
    ".lists-pane",
    ".thumbnails-list",
    ".workspace-pane-toolbox",
    ".eye-pane-body",
    ".eye-canvas-viewport",
    "main",
    ".document-viewer-canvas-container",
    ".conversation-thread",
)


def _rule_body(css: str, selector: str) -> str:
    # (?<![\w-]) guards a bare tag selector like "main" from matching
    # inside ".app-main" (a real substring collision, since "main" is a
    # tag selector this repo also uses as a class-name suffix). The
    # trailing ":" exclusion guards against matching a pseudo-element-
    # suffixed variant of the SAME selector (e.g. this file's own new
    # ".foo::-webkit-scrollbar" rules) instead of the bare base rule.
    needle = re.compile(r"(?<![\w-])" + re.escape(selector) + r"(?![\w\-\":])")
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


class ScrollbarColorPresentEverywhereTests(unittest.TestCase):
    """The standards-track property - present on all 8 containers since
    this stage. CLAUDE-LEFTPANEL-CALM-01 then CLAUDE-PANEL-CALM-02 made it
    quiet-by-default/hover-reveal everywhere (a real Product Owner report
    named the whole app "too agitated," starting with the left panel and
    then confirmed extending the same fix to every panel) - see
    AllPanelsScrollbarHoverRevealTests below for the full hover-reveal
    assertions; this class now just locks in that the property is still
    genuinely present (with real theme tokens on the :hover variant, not
    removed outright) everywhere it always was."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_every_real_scroll_container_has_transparent_default_and_themed_hover(self):
        for selector in _SCROLL_CONTAINERS:
            body = _rule_body(self.css, selector)
            self.assertIn("scrollbar-color: transparent transparent", body, selector)
            hover_body = _rule_body(self.css, f"{selector}:hover")
            self.assertIn("scrollbar-color:", hover_body, selector)
            self.assertIn("var(--border-strong)", hover_body, selector)
            self.assertIn("var(--surface-primary)", hover_body, selector)


class WebkitScrollbarPseudoElementTests(unittest.TestCase):
    """The actual fix for the reported bug - scrollbar-color alone is
    silently ignored on any Chromium build older than v121."""

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_every_container_has_webkit_scrollbar_width_declared(self):
        for selector in _SCROLL_CONTAINERS:
            # The last selector in the combined list has no trailing
            # comma (it's followed by " {" instead) - accept either.
            self.assertRegex(self.css, re.escape(f"{selector}::-webkit-scrollbar") + r"[,\s]", selector)

    def test_track_and_corner_use_theme_tokens_not_hardcoded_white(self):
        # CLAUDE-PANEL-CALM-02: track is transparent by default now (see
        # AllPanelsScrollbarHoverRevealTests for that), themed only on
        # :hover - the "real theme token, never a hardcoded hex" property
        # this test guards still holds, just on the :hover variant.
        hover_track_rule = re.search(
            r":hover::-webkit-scrollbar-track,\s*\n(?:.*:hover::-webkit-scrollbar-track,\s*\n)*.*:hover::-webkit-scrollbar-track\s*\{([^}]*)\}",
            self.css,
        )
        self.assertIsNotNone(hover_track_rule, "no combined :hover::-webkit-scrollbar-track rule found")
        self.assertIn("var(--surface-primary)", hover_track_rule.group(1))
        self.assertNotRegex(hover_track_rule.group(1), r"#[0-9a-fA-F]{3,8}")

        # The corner is never revealed on hover (LEFTPANEL-CALM-01's own
        # original design, kept by PANEL-CALM-02) - it stays transparent
        # unconditionally, which is itself the point: no hardcoded white.
        corner_rule = re.search(r"::-webkit-scrollbar-corner,\s*\n(?:.*::-webkit-scrollbar-corner,\s*\n)*.*::-webkit-scrollbar-corner\s*\{([^}]*)\}", self.css)
        self.assertIsNotNone(corner_rule, "no combined ::-webkit-scrollbar-corner rule found")
        self.assertIn("transparent", corner_rule.group(1))
        self.assertNotRegex(corner_rule.group(1), r"#[0-9a-fA-F]{3,8}")

    def test_thumb_uses_theme_token_not_default_gray(self):
        # CLAUDE-PANEL-CALM-02: the thumb is transparent by default now -
        # themed only on :hover of the panel itself (a separate rule from
        # the thumb's OWN :hover/:active, tested below). Anchored to this
        # stage's own combined :hover reveal block specifically.
        anchor = self.css.index(".lists-pane:hover::-webkit-scrollbar-thumb,")
        thumb_rule = re.search(r"::-webkit-scrollbar-thumb\s*\{([^}]*)\}", self.css[anchor:])
        self.assertIsNotNone(thumb_rule)
        self.assertIn("var(--border-strong)", thumb_rule.group(1))
        self.assertNotRegex(thumb_rule.group(1), r"#[0-9a-fA-F]{3,8}")

    def test_thumb_hover_and_active_states_present(self):
        self.assertIn("::-webkit-scrollbar-thumb:hover,", self.css)
        self.assertIn("::-webkit-scrollbar-thumb:active,", self.css)
        # Anchored past CLAUDE-P40-DTAB1's own .document-tab-list hover/
        # active rule (same shape, appears earlier in the file) - see
        # test_thumb_uses_theme_token_not_default_gray's own comment.
        anchor = self.css.index(".thumbnails-list::-webkit-scrollbar-thumb,")
        hover_active_rule = re.search(
            r"::-webkit-scrollbar-thumb:hover,[\s\S]*?::-webkit-scrollbar-thumb:active\s*\{([^}]*)\}",
            self.css[anchor:],
        )
        self.assertIsNotNone(hover_active_rule)
        self.assertIn("var(--machine-blue)", hover_active_rule.group(1))

    def test_thumb_has_proportional_inset_not_a_flush_block(self):
        # background-clip:padding-box + a transparent border is what
        # keeps the thumb visually inset from the track edges while
        # still using the browser's own real, proportional thumb-length
        # calculation (never faked/hardcoded). Anchored the same way as
        # test_thumb_uses_theme_token_not_default_gray above.
        anchor = self.css.index(".thumbnails-list::-webkit-scrollbar-thumb,")
        thumb_rule = re.search(r"::-webkit-scrollbar-thumb\s*\{([^}]*)\}", self.css[anchor:])
        self.assertIn("background-clip: padding-box", thumb_rule.group(1))
        self.assertIn("border: 2px solid transparent", thumb_rule.group(1))

    def test_no_hardcoded_white_track_or_gray_thumb_anywhere(self):
        webkit_section_start = self.css.index("::-webkit-scrollbar,")
        webkit_section_end = self.css.index("::-webkit-scrollbar-corner {", webkit_section_start)
        webkit_section_end = self.css.index("}", webkit_section_end)
        section = self.css[webkit_section_start - 200:webkit_section_end]
        self.assertNotRegex(section, r"#[0-9a-fA-F]{3,8}")
        self.assertNotIn("gray", section.lower())
        self.assertNotIn("grey", section.lower())


class ScrollBehaviorPreservedTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_overflow_property_unchanged_on_every_container(self):
        # This correction must only add scrollbar PAINTING - never touch
        # the overflow/scroll mechanics themselves.
        for selector, expected in (
            (".lists-pane", "overflow-y: auto"),
            (".thumbnails-list", "overflow-y: auto"),
            (".workspace-pane-toolbox", "overflow-y: auto"),
            (".eye-pane-body", "overflow-y: auto"),
            (".eye-canvas-viewport", "overflow: auto"),
            ("main", "overflow-y: auto"),
            (".document-viewer-canvas-container", "overflow: auto"),
            (".conversation-thread", "overflow-y: auto"),
        ):
            body = _rule_body(self.css, selector)
            self.assertIn(expected, body, selector)

    def test_no_opacity_used_in_scrollbar_rules(self):
        webkit_section_start = self.css.index("::-webkit-scrollbar,")
        webkit_section_end = self.css.index("::-webkit-scrollbar-corner {", webkit_section_start)
        webkit_section_end = self.css.index("}", webkit_section_end)
        section = self.css[webkit_section_start - 200:webkit_section_end]
        self.assertNotIn("opacity", section)


class AllPanelsScrollbarHoverRevealTests(unittest.TestCase):
    """CLAUDE-LEFTPANEL-CALM-01 built this first for .lists-pane alone,
    after a real Product Owner report named the left panel specifically
    as "too agitated." CLAUDE-PANEL-CALM-02 then generalized the EXACT
    same treatment to every other real panel-scale scroll container in
    the 6-panel shell, after the Product Owner confirmed the left-panel
    fix and asked for it everywhere - so .lists-pane is no longer a
    special case split out from the rest; it's one member of one shared
    group, tested here uniformly with the other 7."""

    PANEL_CONTAINERS = (
        ".lists-pane", ".thumbnails-list", ".workspace-pane-toolbox",
        ".eye-pane-body", ".eye-canvas-viewport", "main",
        ".document-viewer-canvas-container", ".conversation-thread",
    )
    RAIL_CONTAINERS = (".document-tab-list", ".attention-strip-list")

    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_every_panel_scrollbar_color_is_transparent_by_default(self):
        for selector in self.PANEL_CONTAINERS:
            body = _rule_body(self.css, selector)
            self.assertIn("scrollbar-color: transparent transparent", body, selector)
            # overflow mechanics must be completely untouched - only the
            # painting changes.
            self.assertTrue("overflow-y: auto" in body or "overflow: auto" in body, selector)

    def test_every_panel_hover_reveals_scrollbar_color(self):
        for selector in self.PANEL_CONTAINERS:
            body = _rule_body(self.css, f"{selector}:hover")
            self.assertIn("scrollbar-color: var(--border-strong) var(--surface-primary)", body, selector)

    def test_every_panel_webkit_track_and_thumb_are_transparent_by_default(self):
        for selector in self.PANEL_CONTAINERS:
            track_body = _rule_body(self.css, f"{selector}::-webkit-scrollbar-track")
            self.assertIn("background: transparent", track_body, selector)
            thumb_body = _rule_body(self.css, f"{selector}::-webkit-scrollbar-thumb")
            self.assertIn("background-color: transparent", thumb_body, selector)

    def test_every_panel_hover_reveals_webkit_track_and_thumb(self):
        for selector in self.PANEL_CONTAINERS:
            track_body = _rule_body(self.css, f"{selector}:hover::-webkit-scrollbar-track")
            self.assertIn("var(--surface-primary)", track_body, selector)
            thumb_body = _rule_body(self.css, f"{selector}:hover::-webkit-scrollbar-thumb")
            self.assertIn("var(--border-strong)", thumb_body, selector)

    def test_panel_thumb_hover_and_active_still_use_accent_color(self):
        # The thumb's OWN :hover/:active (once it's already visible via
        # the panel hover above) keeps the same accent-color convention
        # every container uses - one shared rule covering all of them.
        anchor = self.css.index(".lists-pane::-webkit-scrollbar-thumb:hover,")
        rule = re.search(r"\{([^}]*)\}", self.css[anchor:])
        self.assertIsNotNone(rule)
        self.assertIn("var(--machine-blue)", rule.group(1))
        # And every panel selector is genuinely named in that one rule,
        # not just the first.
        rule_text = self.css[anchor:anchor + self.css[anchor:].index("{")]
        for selector in self.PANEL_CONTAINERS:
            self.assertIn(f"{selector}::-webkit-scrollbar-thumb:hover", rule_text, selector)

    def test_panel_scrollbar_width_unchanged_no_layout_shift(self):
        # The reserved gutter (width/height) must stay in ONE always-
        # applied combined rule, completely unaffected by the color-only
        # hover-reveal change - this is what guarantees no layout shift.
        idx = self.css.index(".lists-pane::-webkit-scrollbar,")
        full_rule = self.css[idx:self.css.index("}", idx)]
        self.assertIn("width: 10px", full_rule)
        self.assertIn("height: 10px", full_rule)
        for selector in self.PANEL_CONTAINERS:
            self.assertIn(f"{selector}::-webkit-scrollbar", full_rule, selector)

    def test_horizontal_rails_share_the_identical_hover_reveal_pattern(self):
        # CLAUDE-PANEL-CALM-02: the two horizontal overflow rails (tab/
        # attention strips) behave the same way as vertical scrollbars -
        # own, smaller sizing (8px/1px inset), same transparent-default/
        # hover-reveal color treatment.
        idx = self.css.index(".document-tab-list::-webkit-scrollbar,")
        width_rule = self.css[idx:self.css.index("}", idx)]
        self.assertIn("height: 8px", width_rule)
        for selector in self.RAIL_CONTAINERS:
            self.assertIn(f"{selector}::-webkit-scrollbar", width_rule, selector)
            base_thumb = _rule_body(self.css, f"{selector}::-webkit-scrollbar-thumb")
            self.assertIn("background-color: transparent", base_thumb, selector)
            hover_thumb = _rule_body(self.css, f"{selector}:hover::-webkit-scrollbar-thumb")
            self.assertIn("var(--border-strong)", hover_thumb, selector)


if __name__ == "__main__":
    unittest.main()
