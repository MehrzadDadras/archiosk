"""CLAUDE-MOBILE-PRIMARY-RESET-01 - fix the composition, not the widgets.

Product Owner: "The live phone experience is now judged chaotic. Do not add
features to solve this. Reduce and reorganize... Do not optimize individual
widgets while preserving a chaotic composition. Fix the composition first."

THE AUDIT. Six persistent bands stacked before any work was visible on a phone:

  1. .workspace-topbar          identity, hamburger, breadcrumb, doc controls,
                                Display Layout / Appearance / Account
  2. .tray-switcher             Lists | Display | Eye | Toolbox + active label
  3. .tray-composer-grabber     work/composer boundary handle
  4. .conversation-dock-header  New + size toggle
  5. .conversation-input-form   + , text, mic, Send        <- the actual job
  6. .conversation-history-tray Conversations disclosure

Only 1 and 5 earn permanent space. These tests are mostly about what is NO
LONGER THERE, because that is the change - and because a composition quietly
regrows one band at a time.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
MACROS = (ROOT / "templates" / "_macros.html").read_text(encoding="utf-8")
APP_MENU = (ROOT / "templates" / "_app_menu.html").read_text(encoding="utf-8")
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8"), flags=re.S)


def _phone_rules() -> str:
    """Every @media (max-width: 640px) block concatenated - the reset's own
    rules live in the last one, but a band could be re-admitted from any."""
    out = []
    for match in re.finditer(r"@media \(max-width: 640px\)", CSS):
        start = CSS.index("{", match.start())
        depth = 0
        for i in range(start, len(CSS)):
            if CSS[i] == "{":
                depth += 1
            elif CSS[i] == "}":
                depth -= 1
                if depth == 0:
                    out.append(CSS[start:i])
                    break
    return "\n".join(out)


class WhatWasRemovedTests(unittest.TestCase):
    """Reported as importantly as what was added, per the brief."""

    def test_the_four_tray_buttons_no_longer_occupy_the_frame(self):
        """Four competing permanent panes is the compressed-desktop pattern
        that has now been rejected three times."""
        self.assertRegex(_phone_rules(), r"\.tray-switcher-options\s*\{\s*display:\s*none")

    def test_the_dock_header_is_gone_from_the_phone(self):
        """Its New moved into the context bar; its size toggle was redundant
        with the grabber two pixels above it."""
        self.assertRegex(_phone_rules(), r"\.conversation-dock-header\s*\{\s*display:\s*none")

    def test_the_history_tray_left_the_composer(self):
        """It spent a band of the smallest screen answering "which
        conversations exist" - a context question, not a composing one."""
        self.assertNotIn("conversation-history-tray", MACROS)

    def test_secondary_topbar_controls_are_not_permanent_on_a_phone(self):
        phone = _phone_rules()
        for control in (".workspace-topbar-controls", ".workspace-app-activity",
                        ".workspace-topbar-document-controls"):
            with self.subTest(control=control):
                self.assertIn(control, phone)


class NothingGovernedWasRemovedTests(unittest.TestCase):
    """"Preserve all existing governed capabilities, but hide secondary
    controls until deliberately requested." Demotion is not deletion, and the
    difference has to be provable."""

    def test_the_tray_controls_still_exist_on_demand(self):
        for ref in ("menu.view.panel.lists", "menu.view.panel.display",
                    "menu.view.panel.eye", "menu.view.panel.toolbox"):
            with self.subTest(ref=ref):
                self.assertIn(ref, APP_MENU)

    def test_they_reuse_the_existing_mechanism_not_a_second_one(self):
        block = APP_MENU[APP_MENU.index('data-ui-ref="menu.view.panel.lists"'):]
        block = block[: block.index("</button>")]
        self.assertIn('data-tray-focus-btn="lists"', block)

    def test_archive_remains_reachable_but_secondary(self):
        """"Archive secondary, not a primary control." It lives in the Toolbox
        Investigations list and its own confirm page - not beside the
        Composer."""
        workspace_template = (ROOT / "templates" / "case_workspace.html").read_text(encoding="utf-8")
        self.assertIn("confirm_archive_case", workspace_template)
        self.assertNotIn("archive-conversation", MACROS)

    def test_the_composer_keeps_all_four_of_its_controls(self):
        """+ , text, mic, Send - the brief names them explicitly."""
        for control in ('data-ui-ref="chat.composer.attach"', 'id="dock-composer-input"',
                        'id="dock-composer-voice"', 'class="conversation-input-form'):
            with self.subTest(control=control):
                self.assertIn(control, MACROS)


class WhatReplacedThemTests(unittest.TestCase):
    def test_one_context_bar_answers_all_three_questions(self):
        """"Where am I", "what else is there", "start fresh" - in one band
        instead of three."""
        self.assertIn('data-ui-ref="shell.context.identity"', BASE)
        self.assertIn('data-ui-ref="shell.context.identity.leaf"', BASE)
        self.assertIn('data-ui-ref="shell.context.new-chat"', BASE)

    def test_project_and_conversation_identity_are_both_shown(self):
        """"project/Q identity always obvious"."""
        block = BASE[BASE.index('data-ui-ref="shell.context.identity"'):]
        block = block[: block.index("</summary>")]
        self.assertIn("context-identity-project", block)
        self.assertIn("context-identity-current", block)

    def test_the_history_opens_over_the_page_rather_than_pushing_it_down(self):
        """A disclosure that reflows the frame is exactly why the old tray read
        as another band."""
        rule = CSS[CSS.index(".context-identity-list {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("position: absolute", rule)
        self.assertIn("max-height", rule)

    def test_switching_conversation_is_navigation_only(self):
        block = BASE[BASE.index('data-ui-ref="shell.context.identity"'):]
        block = block[: block.index("</details>")]
        # "archived" appears as a LOOP FILTER here (skip concluded
        # conversations), which is not an archive action - the first version of
        # this test could not tell the difference.
        for forbidden in ("method=\"post\"", "archive_case", "confirm_archive", "delete"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, block)

    def test_it_marks_which_conversation_you_are_in(self):
        """Carried over from the retired history-tray tests: the list answers
        "where else can I go" AND "where am I" - a list that does not say which
        entry is current makes the reader work it out."""
        block = BASE[BASE.index('data-ui-ref="shell.context.identity"'):]
        block = block[: block.index("</details>")]
        self.assertIn("context-identity-current-item", block)

    def test_the_project_conversation_is_always_offered(self):
        """Also carried over. The old tray needed an empty state; this list
        cannot be empty, because the project conversation is always a
        destination."""
        block = BASE[BASE.index('data-ui-ref="shell.context.identity"'):]
        block = block[: block.index("</details>")]
        self.assertIn("Project conversation", block)

    def test_it_reuses_the_existing_navigation_links(self):
        """The same workspace.show_workspace route the Toolbox list uses - not
        a second navigation model."""
        block = BASE[BASE.index('data-ui-ref="shell.context.identity"'):]
        block = block[: block.index("</details>")]
        self.assertEqual(block.count("workspace.show_workspace"), 2)

    def test_its_targets_are_touch_sized(self):
        for selector in (".context-identity-summary {", ".context-identity-item {",
                         ".context-new-btn {"):
            with self.subTest(selector=selector):
                rule = CSS[CSS.index(selector):]
                rule = rule[: rule.index("}")]
                found = re.search(r"min-height:\s*(\d+)px", rule)
                self.assertIsNotNone(found, f"{selector} has no touch target")
                self.assertGreaterEqual(int(found.group(1)), 36)


class TheTargetStructureHoldsTests(unittest.TestCase):
    """One fixed top bar, one scrolling page, one fixed Composer."""

    def test_the_composer_is_still_anchored(self):
        self.assertRegex(_phone_rules(), r"\.chat-region\s*\{[^}]*position:\s*fixed")

    def test_the_page_still_cannot_drift_sideways(self):
        self.assertIn("overflow-x: clip", CSS)
        self.assertIn("touch-action: pan-y", CSS)

    def test_the_foreground_layer_still_returns_to_prior_state(self):
        """"drawings/photos may temporarily occupy foreground and return to
        prior state" - the layer covers, it does not replace."""
        self.assertIn('html[data-tray-layer="eye"] #eye-pane', CSS)

    def test_no_band_was_added_back(self):
        """The composition is the deliverable. If a future change re-admits a
        permanent band on a phone, this is where it should fail."""
        phone = _phone_rules()
        for removed in (".tray-switcher-options", ".conversation-dock-header"):
            with self.subTest(band=removed):
                # The selector appears more than once across the phone blocks
                # (an earlier layout rule, then the reset's own removal), so
                # match the RULE that hides it rather than the first mention.
                self.assertRegex(
                    phone,
                    re.escape(removed) + r"\s*\{\s*display:\s*none",
                )


if __name__ == "__main__":
    unittest.main()
