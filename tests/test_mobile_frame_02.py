"""CLAUDE-MOBILE-FRAME-02 - the mobile-first primary workspace frame.

The Product Owner tests ARCHIOSK from an iPhone and named the architecture:

    TOP     fixed compact header  - where am I, what am I working on
    MIDDLE  ONE active work tray  - where the work happens
    BOTTOM  fixed Composer        - how I talk to GO

What was there before was LAY-5A - three columns and a dock, with a 320px
floor on the centre column - compressed into 390px of phone. These tests
guard the frame that replaced it, and, at least as importantly, guard the
things the frame was NOT allowed to cost: no second sizing system, no
duplicate mobile menu, no new "functions" invented alongside the surfaces
that already exist, and no route by which moving a panel around could
touch project truth.

A note on what these tests can and cannot prove. pytest here renders DOM
and reads static files; it does not lay out CSS or run a browser. So the
geometric claims below are asserted as PROPERTIES OF THE RULES (this
selector exists, that floor is lifted at this breakpoint, this control is
hidden there) rather than as measured pixels. Real geometry is the
Product Owner's physical-device acceptance, which is the gate this stage
stops at deliberately.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_HTML = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")
APP_MENU = (ROOT / "templates" / "_app_menu.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8")
TRAYS_JS = (ROOT / "static" / "js" / "workspace_trays.js").read_text(encoding="utf-8")
CASE_JS = (ROOT / "static" / "js" / "case_workspace.js").read_text(encoding="utf-8")
GATEWAY = (ROOT / "templates" / "gateway_shell.html").read_text(encoding="utf-8")

# Several assertions below are about what the RULES say, so a comment that
# happens to mention a selector must not be able to satisfy them - this
# file has been bitten by exactly that before (see
# tests/test_appearance_simplify_01_global_theme.py's own note).
CSS_NO_COMMENTS = re.sub(r"/\*.*?\*/", "", CSS, flags=re.S)


def _strip_js_comments(src: str) -> str:
    """Same hazard, same fix, on the JS side.

    workspace_trays.js documents at length what it deliberately does NOT
    reimplement - `--chat-height`, `launcher-hidden`, the maximize buttons.
    Every one of those names appearing in prose would satisfy a naive
    "this token is absent" assertion and turn the guard into decoration.
    The guards below are about the CODE, so they read the code.
    """
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    return re.sub(r"(?<![:\w])//.*$", "", src, flags=re.M)


TRAYS_CODE = _strip_js_comments(TRAYS_JS)


def _phone_block() -> str:
    """The @media (max-width: 640px) block this stage appended."""
    start = CSS_NO_COMMENTS.index("data-tray-focus")
    tail = CSS_NO_COMMENTS[start:]
    at = tail.index("@media (max-width: 640px)")
    body_start = tail.index("{", at)
    depth = 0
    for i in range(body_start, len(tail)):
        if tail[i] == "{":
            depth += 1
        elif tail[i] == "}":
            depth -= 1
            if depth == 0:
                return tail[body_start:i]
    raise AssertionError("unterminated phone media block")


class TheThreeZonesExistTests(unittest.TestCase):
    """Top header, one active tray, bottom Composer."""

    def test_the_header_carries_a_function_switcher(self):
        self.assertIn('class="tray-switcher"', BASE_HTML)
        self.assertIn('id="tray-active-label"', BASE_HTML)

    def test_the_switcher_sits_above_the_work_area_not_inside_it(self):
        """The header is a zone. If the switcher were inside the tray it
        would disappear with whatever tray it just switched away from."""
        self.assertLess(
            BASE_HTML.index('class="tray-switcher"'),
            BASE_HTML.index('class="app-shell-body"'),
        )

    def test_the_composer_is_anchored_and_is_not_a_tray(self):
        """Section 8: "Do not make Composer another tray the user must
        navigate to." It is a zone - always below the work."""
        self.assertIn("html[data-tray-focus] .chat-region", CSS_NO_COMMENTS)
        rule = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index("html[data-tray-focus] .chat-region"):]
        rule = rule[: rule.index("}")]
        self.assertIn("position: fixed", rule)
        self.assertIn("bottom:", rule)
        # No switcher button targets Chat, and Chat is not a tray key.
        self.assertNotIn('data-tray-focus-btn="chat"', BASE_HTML)
        self.assertNotIn("chat:", TRAYS_JS[TRAYS_JS.index("var TRAYS"): TRAYS_JS.index("var TRAYS") + 400])

    def test_focus_never_hides_the_composer(self):
        """Every tray key hides some siblings. None of them may hide the
        region the Composer lives in - that is the whole point of the
        bottom zone."""
        for key in ("lists", "display", "eye", "toolbox"):
            hide_rules = re.findall(
                r'html\[data-tray-focus="%s"\][^{]*\{[^}]*display:\s*none[^}]*\}' % key,
                CSS_NO_COMMENTS,
            )
            for rule in hide_rules:
                self.assertNotIn("chat-region", rule, f"{key} focus hides the Composer")
                self.assertNotIn("workspace-main-column", rule)


class OneActiveTrayIsStructuralTests(unittest.TestCase):
    def test_the_state_is_one_attribute_not_several_booleans(self):
        """An attribute holds exactly one value, so "only one active work
        tray" cannot drift the way four independent flags could."""
        self.assertIn("var ATTR = 'data-tray-focus'", TRAYS_JS)
        self.assertIn("html.setAttribute(ATTR, key)", TRAYS_JS)

    def test_the_four_trays_are_existing_surfaces_not_new_functions(self):
        """Section 5: "Do not invent new functions." These are NPT-002/
        003/005/006 - the same surfaces the Appearance menu names."""
        block = TRAYS_JS[TRAYS_JS.index("var TRAYS = {"):]
        block = block[: block.index("}")]
        self.assertIn("#launcher-panel", block)
        self.assertIn(".app-main", block)
        self.assertIn("#eye-pane", block)
        self.assertIn("#workspace-toolbox-panel", block)
        for selector in ("#launcher-panel", "#eye-pane", "#workspace-toolbox-panel"):
            self.assertIn(selector.lstrip("#"), BASE_HTML)

    def test_every_switcher_button_names_a_real_tray(self):
        buttons = set(re.findall(r'data-tray-focus-btn="([a-z]+)"', BASE_HTML))
        keys = set(re.findall(r"^\s+([a-z]+): '", TRAYS_JS[TRAYS_JS.index("var TRAYS = {"):TRAYS_JS.index("};", TRAYS_JS.index("var TRAYS = {"))], re.M))
        self.assertTrue(buttons)
        self.assertEqual(buttons, keys)

    def test_a_dead_control_removes_itself(self):
        """A project-less page has no Eye or Toolbox. A button that cannot
        do anything is worse than no button."""
        self.assertIn("if (!exists(key))", TRAYS_JS)
        self.assertIn("btn.remove()", TRAYS_JS)

    def test_switching_preserves_the_tray_it_leaves(self):
        """Section 17: presentation state survives a switch. Trays are
        hidden, never rebuilt, and scroll is captured explicitly rather
        than hoped for."""
        self.assertIn("rememberScroll", TRAYS_JS)
        self.assertIn("restoreScroll", TRAYS_JS)
        self.assertNotIn("innerHTML", TRAYS_CODE)
        self.assertNotIn(".removeChild", TRAYS_CODE)


class VerticalSizingReusesTheOneWritePointTests(unittest.TestCase):
    """Section 6 wants a flexible tray; Section 19 wants ONE model."""

    def test_three_rest_positions_exist(self):
        block = TRAYS_JS[TRAYS_JS.index("var SNAP = {"):]
        block = block[: block.index("}")]
        for state in ("high", "working", "low"):
            self.assertIn(state + ":", block)

    def test_sizing_goes_through_the_existing_chat_splitter(self):
        """Not a second height system. case_workspace.js owns
        --chat-height; this calls into it so the mobile grabber, the
        desktop handle, the Compact/Expand toggle and the linked
        Eye/Toolbox splitter can never disagree."""
        self.assertIn("window.__chatSplitter.setValue", TRAYS_JS)
        self.assertIn("window.__chatSplitter = {", CASE_JS)
        # The single write point stays single: nothing in the new module
        # sets the custom property itself.
        self.assertNotIn("--chat-height", TRAYS_CODE)

    def test_the_composer_controls_have_a_floor(self):
        """Section 10, read in both directions: expansion must not bury
        send/voice, and the tray must not be able to squeeze them out."""
        self.assertIn("COMPOSER_FLOOR_PX", TRAYS_JS)
        self.assertIn("Math.max(COMPOSER_FLOOR_PX", TRAYS_JS)

    def test_the_boundary_is_reachable_without_a_drag(self):
        """Section 22: avoid precision targets. Section 23: keyboard."""
        self.assertIn("cycleSize", TRAYS_JS)
        self.assertIn("ArrowUp", TRAYS_JS)
        self.assertIn("ArrowDown", TRAYS_JS)
        block = BASE_HTML[BASE_HTML.index("tray-composer-grabber"):][:700]
        self.assertIn('role="separator"', block)
        self.assertIn('tabindex="0"', block)

    def test_an_abandoned_drag_is_not_remembered(self):
        block = TRAYS_JS[TRAYS_JS.index("pointermove"):]
        block = block[: block.index("function endDrag")]
        self.assertIn("false", block)  # setComposerPx(..., false) - live, unpersisted


class NoDesktopMenuCompressionOnAPhoneTests(unittest.TestCase):
    """Section 4 rules out all three usual escapes by name."""

    def test_the_eight_menu_row_is_not_displayed_at_phone_widths(self):
        phone = _phone_block()
        self.assertRegex(phone, r"\.workspace-menubar\s*\{\s*display:\s*none")

    def test_it_is_not_solved_by_horizontal_scrolling(self):
        phone = _phone_block()
        menubar_rules = re.findall(r"\.workspace-menubar[^{]*\{[^}]*\}", phone)
        self.assertTrue(menubar_rules)
        for rule in menubar_rules:
            self.assertNotIn("overflow-x: auto", rule)
            self.assertNotIn("overflow-x: scroll", rule)
            self.assertNotIn("flex-wrap: nowrap", rule)

    def test_the_workspace_itself_cannot_scroll_sideways(self):
        phone = _phone_block()
        self.assertRegex(phone, r"\.app-shell-body\s*\{[^}]*overflow-x:\s*hidden")

    def test_the_desktop_centre_column_floor_is_lifted_on_a_phone(self):
        """`.workspace-main-column { min-width: 320px }` is right on a
        desktop - it stops Lists and the right column squeezing Display.
        At 320px of actual viewport it is the guarantee of horizontal
        overflow, and in the frame there is no second column to squeeze."""
        phone = _phone_block()
        self.assertRegex(phone, r"\.workspace-main-column\s*\{[^}]*min-width:\s*0")

    def test_there_is_one_menu_not_two(self):
        """A duplicate mobile menu would be a second implementation of
        every command in it."""
        self.assertEqual(APP_MENU.count('class="workspace-menubar"'), 1)
        self.assertEqual(APP_MENU.count('id="mobile-nav-toggle"'), 1)

    def test_the_toggle_fails_in_the_safe_direction(self):
        """The menubar is visible by default at every width CSS calls
        wide; JS is only ever needed to REVEAL something on a phone. A
        <details> wrapper would have inverted that - desktop would have
        needed JS to force it open, so a JS failure would cost desktop
        its whole menu bar."""
        self.assertIn("html.mobile-nav-open .workspace-menubar", CSS_NO_COMMENTS)
        self.assertNotIn("<details", APP_MENU[APP_MENU.index("mobile-nav-toggle") - 200: APP_MENU.index("mobile-nav-toggle")])
        self.assertRegex(
            CSS_NO_COMMENTS,
            r"@media \(min-width: 641px\)\s*\{[^}]*\.mobile-nav-toggle\s*\{\s*display:\s*none",
        )


class PortraitAndKeyboardTests(unittest.TestCase):
    def test_the_shell_uses_the_dynamic_viewport_unit(self):
        """100vh on iOS Safari is the height with browser chrome
        RETRACTED, so a bottom-anchored Composer starts below the fold."""
        phone = _phone_block()
        self.assertIn("100dvh", phone)
        # The plain vh line stays as the fallback, and must come first.
        shell_rule = phone[phone.index(".app-shell {"):]
        shell_rule = shell_rule[: shell_rule.index("}")]
        self.assertLess(shell_rule.index("100vh"), shell_rule.index("100dvh"))

    def test_the_keyboard_inset_is_measured_not_guessed(self):
        """Section 15. iOS does not shrink the layout viewport when the
        keyboard opens; visualViewport reports what is actually visible."""
        self.assertIn("visualViewport", TRAYS_JS)
        self.assertIn("--kb-inset", TRAYS_JS)
        self.assertIn("var(--kb-inset", CSS_NO_COMMENTS)

    def test_rotation_does_not_rebuild_the_workspace(self):
        """Section 14: returning from a landscape photograph to portrait
        must not reset the workspace."""
        self.assertIn("orientationchange", TRAYS_JS)
        block = TRAYS_JS[TRAYS_JS.index("orientationchange"):]
        block = block[: block.index("narrowDefault();") + 200]
        self.assertNotIn("location.reload", block)
        self.assertNotIn("innerHTML", block)

    def test_switch_targets_are_touch_sized(self):
        phone = _phone_block()
        rule = phone[phone.index(".tray-switcher-btn {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("min-height: 40px", rule)


class DesktopKeepsItsCompositionTests(unittest.TestCase):
    """Section 18: desktop gets more room, not different semantics."""

    def test_the_multi_column_composition_is_untouched_when_nothing_is_focused(self):
        """Every frame rule is gated behind the data-tray-focus attribute.
        With no tray focused, LAY-5A renders exactly as before."""
        frame = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index("html[data-tray-focus] .chat-region"):]
        # Everything in the frame block that changes layout is either
        # attribute-gated or lives inside the phone media query.
        phone_at = frame.index("@media (max-width: 640px)")
        unconditional = frame[:phone_at]
        for line in unconditional.splitlines():
            line = line.strip()
            if not line.endswith(",") and not line.endswith("{"):
                continue
            selector = line.rstrip("{,").strip()
            if not selector or selector.startswith("@"):
                continue
            layout_surface = any(
                token in selector
                for token in (
                    "app-shell-body", "workspace-main-column", "app-main",
                    "launcher-panel", "workspace-right-column", "chat-region",
                    "eye-pane", "workspace-pane-toolbox", "panel-divider",
                )
            )
            if layout_surface:
                self.assertIn("data-tray-focus", selector, f"ungated layout rule: {selector}")

    def test_desktop_can_restore_from_a_focused_tray(self):
        """Section 19: expand one temporarily, then come back."""
        self.assertIn("return isNarrow() ? false : apply(null)", TRAYS_JS)
        self.assertIn("'Escape'", TRAYS_JS)

    def test_escape_yields_to_a_real_escape_first(self):
        """Never a trap, but never at the cost of closing a menu or
        leaving a text field either."""
        block = TRAYS_JS[TRAYS_JS.index("if (event.key !== 'Escape'"):]
        block = block[: block.index("clear();") + 20]
        self.assertIn("input, textarea, select", block)
        self.assertIn("details[open]", block)

    def test_the_existing_collapse_and_maximize_mechanisms_are_not_replaced(self):
        """The panel dividers and the Eye/Toolbox maximize buttons are
        intra-column controls and stay exactly as they were."""
        self.assertIn("launcher-hidden", BASE_HTML)
        self.assertIn("toolbox-hidden", BASE_HTML)
        self.assertIn("eye-maximize-btn", BASE_HTML)
        self.assertIn("toolbox-maximize-btn", BASE_HTML)
        for token in ("launcher-hidden", "toolbox-hidden", "eye-maximize", "toolbox-maximize"):
            self.assertNotIn(token, TRAYS_CODE, f"{token} reimplemented in the new module")


class PresentationIsNotProjectStateTests(unittest.TestCase):
    """Part K. The strongest guarantee available here is structural: the
    module that moves panels around has no way to reach a route."""

    def test_the_frame_module_cannot_talk_to_the_server(self):
        for forbidden in ("fetch(", "XMLHttpRequest", "FormData", "navigator.sendBeacon", ".submit()", "action="):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, TRAYS_CODE)

    def test_it_persists_only_a_reviewer_preference(self):
        """localStorage, reviewer-wide, alongside the existing
        beehive:panel:* preferences - never a project record."""
        self.assertIn("'beehive:tray:focus'", TRAYS_JS)
        writes = re.findall(r"localStorage\.(setItem|removeItem)\(([^,)]+)", TRAYS_CODE)
        self.assertTrue(writes)
        for _, key in writes:
            self.assertIn("STORAGE_KEY", key)

    def test_no_evidence_or_authorization_vocabulary_leaks_in(self):
        for forbidden in ("finding", "evidence", "adjudicat", "authoriz", "project_id", "csrf"):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, TRAYS_CODE.lower())


class NoDeadControlsTests(unittest.TestCase):
    """Four defects caught in self-review before deployment. Each one
    rendered a real, pressable control that could not do its job."""

    def test_the_menu_drawer_toggle_works_on_gateway_too(self):
        """_app_menu.html is included by BOTH base.html and
        gateway_shell.html, so the toggle renders on Gateway - which
        loaded app_menu.js but not the module that drives the drawer."""
        self.assertIn("mobile-nav-toggle", APP_MENU)
        self.assertIn("workspace_trays.js", GATEWAY)
        self.assertIn("workspace_trays.js", BASE_HTML)

    def test_composer_height_is_only_reserved_where_a_composer_exists(self):
        """The Composer is gated on project_id/workspace. Reserving its
        height on a project-less page left a dead strip below the work
        area with nothing in it."""
        self.assertIn(
            "html[data-tray-focus] .app-shell-body:has(.chat-region)",
            CSS_NO_COMMENTS,
        )
        self.assertNotRegex(
            CSS_NO_COMMENTS,
            r"html\[data-tray-focus\] \.app-shell-body\s*\{",
        )

    def test_the_grabber_follows_the_established_splitter_semantics(self):
        """The existing #conversation-dock-resize-handle is the pattern:
        role=separator with a real value range, not a bare role=slider
        with nothing behind it."""
        block = BASE_HTML[BASE_HTML.index("tray-composer-grabber"):][:700]
        self.assertIn('role="separator"', block)
        self.assertIn("aria-valuemin", block)
        self.assertIn("aria-valuemax", block)
        self.assertNotIn('role="slider"', block)
        self.assertIn("aria-valuenow", TRAYS_CODE)

    def test_the_drawer_closes_on_an_outside_tap(self):
        """app_menu.js's own outside-click convention covers <details>
        popups; the drawer is a class on <html>, so it needed its own."""
        block = TRAYS_CODE[TRAYS_CODE.index("function wireMobileNav"):]
        block = block[: block.index("function wire(")]
        self.assertIn("mobile-nav-open", block)
        self.assertIn("addEventListener('click'", block)
        self.assertIn("setOpen(false)", block)


class ItRendersForAnAuthorizedUserTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db
        from werkzeug.security import generate_password_hash

        self.flask_app = app_module.create_app("testing")
        with self.flask_app.app_context():
            db.session.add(User(
                username="frame", password_hash=generate_password_hash("x"), role="admin",
            ))
            db.session.commit()
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "frame"
            sess["role"] = "admin"

    def test_the_frame_is_not_exposed_to_an_anonymous_visitor(self):
        anon = self.flask_app.test_client()
        body = anon.get("/").get_data(as_text=True)
        self.assertNotIn("tray-switcher", body)
        self.assertNotIn("mobile-nav-toggle", body)

    def test_an_authenticated_page_renders_the_switcher(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("tray-switcher", body)
        self.assertIn("workspace_trays.js", body)

    def test_a_project_less_page_offers_only_the_trays_it_has(self):
        """Eye and Toolbox render only inside an open Workspace, so their
        buttons must not be server-rendered anywhere else."""
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn('data-tray-focus-btn="lists"', body)
        self.assertIn('data-tray-focus-btn="display"', body)
        self.assertNotIn('data-tray-focus-btn="eye"', body)
        self.assertNotIn('data-tray-focus-btn="toolbox"', body)


if __name__ == "__main__":
    unittest.main()
