"""
CLAUDE-P40-VW8-QA - Panel-border hierarchy correction.

Product-owner observation: several colored panel borders/divider lines
were visually distracting, most concretely the divider below the top
Menu bar and the Lists-to-Display boundary. Chat's own existing border
treatment (no border-top on .chat-region itself - a single line drawn
by .conversation-dock-resize-handle's own ::before, using the fixed,
mode-invariant --divider-strong token) was named the approved
reference.

Two concrete, verifiable fixes:
1. `.launcher-panel` no longer draws its own `border-right` - the
   adjacent `.panel-divider`'s own `::before` line (4px to its right)
   already drew a second, parallel line ~4-5px away - a real, doubled
   boundary readable directly from the CSS, not a subjective call.
   The narrow-viewport drawer variant keeps its own border-right
   (no adjacent divider element exists at that width).
2. `.workspace-topbar`'s full-width bottom border switched from
   `var(--border)` to `var(--divider-strong)` - the same fixed,
   mode-invariant, deliberately quiet token Chat's own resize-handle
   divider already uses, rather than a token that gets locally
   redefined (and can vary in apparent weight) per appearance mode.

Audited and found ALREADY compliant, so deliberately UNCHANGED:
- The Display-to-Toolbox boundary (`.panel-divider-toolbox`) - a
  single line via the same quiet-resting/accent-on-hover-or-focus
  `.panel-divider` treatment, no redundant second border anywhere
  near it.
- `.panel-divider` itself - already quiet at rest, already brightens to
  `--machine-blue` only on hover/focus (a "meaningful state" per the
  hierarchy), already preserves its full clickable hit area.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"


def _comment_spans(css: str) -> list[tuple[int, int]]:
    spans = []
    idx = 0
    while True:
        start = css.find("/*", idx)
        if start == -1:
            break
        end = css.find("*/", start + 2)
        if end == -1:
            break
        spans.append((start, end + 2))
        idx = end + 2
    return spans


def _inside_any_span(pos: int, spans: list[tuple[int, int]]) -> bool:
    return any(start <= pos < end for start, end in spans)


class PanelBorderHierarchyTests(unittest.TestCase):
    def setUp(self):
        self.css = _MAIN_CSS_PATH.read_text(encoding="utf-8")
        self.comment_spans = _comment_spans(self.css)

    def _rule_body(self, selector: str, occurrence: int = 0) -> str:
        # Matches the selector immediately followed by '{' or ',' (a
        # compound multi-line selector list), allowing whitespace in
        # between, EXCLUDING any match that falls inside a /* ... */
        # comment - a prose mention of the same selector text (this
        # file cross-references real selectors from its own comments
        # constantly) must never be mistaken for the real rule.
        stripped = selector.rstrip("{,").rstrip()
        pattern = re.escape(stripped) + r"\s*[{,]"
        matches = [m for m in re.finditer(pattern, self.css) if not _inside_any_span(m.start(), self.comment_spans)]
        match_end = matches[occurrence].end() - 1
        start = self.css.index("{", match_end)
        end = self.css.index("}", start)
        return self.css[start:end]

    def test_launcher_panel_desktop_rule_has_no_border_right(self):
        # The FIRST .launcher-panel rule is the desktop one (before the
        # @media (max-width: 640px) drawer override further down).
        body = self._rule_body(".launcher-panel {")
        self.assertNotIn("border-right", body)

    def test_narrow_viewport_drawer_still_has_its_own_border_right(self):
        # No adjacent .panel-divider exists at that width (it collapses
        # the panel in the first place) - the drawer needs its own edge.
        media_idx = self.css.index("@media (max-width: 640px)")
        media_body = self.css[media_idx: media_idx + 400]
        self.assertIn(".launcher-panel", media_body)
        self.assertIn("border-right: 1px solid var(--border)", media_body)

    def test_panel_divider_still_draws_exactly_one_line(self):
        # .panel-divider itself must remain the sole line at the Lists/
        # Display and Display/Toolbox boundaries - border:none on the
        # clickable element, one line via its own ::before.
        body = self._rule_body(".panel-divider {")
        self.assertIn("border: none", body)
        before_body = self._rule_body(".panel-divider::before")
        self.assertIn("background: var(--border)", before_body)

    def test_panel_divider_hit_area_and_hover_focus_accent_retained(self):
        # Functional requirements this correction must NOT touch: the
        # divider's own clickable width and its accent-on-hover/focus
        # (a "meaningful state" - keyboard focus / hover of a functional
        # resize handle - explicitly allowed the stronger treatment).
        body = self._rule_body(".panel-divider {")
        self.assertIn("width: 9px", body)
        self.assertIn("cursor: pointer", body)
        hover_focus_body = self._rule_body(".panel-divider:hover::before,")
        self.assertIn("background: var(--machine-blue)", hover_focus_body)

    def test_workspace_topbar_uses_the_mode_invariant_divider_token(self):
        body = self._rule_body(".workspace-topbar {")
        self.assertIn("border-bottom: 1px solid var(--divider-strong)", body)
        self.assertNotIn("border-bottom: 1px solid var(--border);", body)

    def test_chat_region_still_has_no_competing_border_top(self):
        # The approved reference itself must stay untouched by this
        # correction - Chat's own boundary is still the resize-handle's
        # one line, never a second border on the panel itself.
        body = self._rule_body(".chat-region {")
        self.assertNotIn("border-top", body)

    def test_conversation_dock_resize_handle_divider_line_unchanged(self):
        # Chat's own approved treatment, pinned so a future change can't
        # silently drift it while "coordinating" other panels' borders.
        body = self._rule_body(".conversation-dock-resize-handle::before")
        self.assertIn("background: var(--divider-strong)", body)
        hover_body = self._rule_body(".conversation-dock-resize-handle:hover::before,")
        self.assertIn("background: var(--machine-blue)", hover_body)

    def test_divider_strong_token_is_never_redefined_per_appearance_mode(self):
        # The whole point of using it here - it must stay fixed across
        # Light/Black/Midnight Blue/Deep Forest, never locally
        # overridden the way --border/--surface-primary/etc. are.
        appearance_block_start = self.css.index(".workspace-topbar.appearance-dark,")
        appearance_block_end = self.css.index("\n}\n", self.css.index(".chat-region.appearance-deep-forest .conversation-dock-panel"))
        appearance_block = self.css[appearance_block_start:appearance_block_end]
        self.assertNotIn("--divider-strong:", appearance_block)

    def test_no_gradients_or_backdrop_filters_introduced_on_panel_boundaries(self):
        # Panel-border hierarchy correction must stay flat spacing/token
        # borders, never a reflective/glossy replacement decoration.
        for selector in (".panel-divider {", ".workspace-topbar {", ".launcher-panel {", ".chat-region {"):
            body = self._rule_body(selector)
            self.assertNotIn("gradient", body)
            self.assertNotIn("backdrop-filter", body)
            self.assertNotIn("box-shadow", body)

    def test_no_dimension_or_geometry_properties_changed_on_touched_rules(self):
        # Scope guard: this correction only ever removes/retints a
        # border - width/height/flex-basis of the panels themselves
        # must be exactly what they were before.
        launcher_body = self._rule_body(".launcher-panel {")
        self.assertIn("width: 240px", launcher_body)
        topbar_body = self._rule_body(".workspace-topbar {")
        self.assertIn("padding: 0.6rem 0", topbar_body)
        self.assertIn("margin-bottom: 1rem", topbar_body)


if __name__ == "__main__":
    unittest.main()
