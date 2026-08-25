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

    def test_the_trays_are_existing_surfaces_not_new_functions(self):
        """Section 5: "Do not invent new functions." These are NPT-002/003/006
        - the same surfaces the Appearance menu names. Eye (NPT-005) is
        deliberately absent: it is the foreground LAYER, not a tray."""
        block = TRAYS_JS[TRAYS_JS.index("var TRAYS = {"):]
        block = block[: block.index("}")]
        self.assertIn("#launcher-panel", block)
        self.assertIn(".app-main", block)
        self.assertIn("#workspace-toolbox-panel", block)
        self.assertNotIn("#eye-pane", block)
        for selector in ("#launcher-panel", "#workspace-toolbox-panel", "#eye-pane"):
            self.assertIn(selector.lstrip("#"), BASE_HTML)

    def test_every_switcher_button_names_a_real_tray_or_layer(self):
        """One control set drives both - a switcher entry with no surface
        behind it would be a dead control."""
        def keys_of(name):
            start = TRAYS_JS.index("var %s = {" % name)
            return set(re.findall(r"^\s+([a-z]+): '", TRAYS_JS[start:TRAYS_JS.index("};", start)], re.M))

        buttons = set(re.findall(r'data-tray-focus-btn="([a-z]+)"', BASE_HTML))
        trays, layers = keys_of("TRAYS"), keys_of("LAYERS")
        self.assertTrue(buttons)
        self.assertEqual(buttons, trays | layers)
        # A key cannot be both, or focus() could not tell raise from replace.
        self.assertEqual(trays & layers, set())

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


class TheForegroundLayerTests(unittest.TestCase):
    """CLAUDE-MOBILE-Q-TRIAL-01 Section 4 - "bring it to the foreground, work
    with it, then shovel it back to reveal the main panel exactly where it
    was." A drawing sheet on a desk."""

    def test_eye_is_a_layer_rather_than_a_tray(self):
        block = TRAYS_JS[TRAYS_JS.index("var LAYERS = {"):]
        block = block[: block.index("}")]
        self.assertIn("#eye-pane", block)

    def test_a_layer_covers_the_work_and_never_replaces_it(self):
        """This is what makes "exactly where it was" structural: no rule may
        hide the base trays while the layer is up, so there is no state to
        restore because none was taken away."""
        rules = re.findall(r"html\[data-tray-layer[^{]*\{[^}]*\}", CSS_NO_COMMENTS)
        self.assertTrue(rules)
        hidden = [r for r in rules if re.search(r"display:\s*none", r)]
        for rule in hidden:
            selector = rule[: rule.index("{")]
            for base in (".app-main", ".launcher-panel"):
                self.assertNotIn(base, selector, f"layer hides a base tray: {selector}")

    def test_raising_the_layer_touches_no_tray_state(self):
        block = TRAYS_CODE[TRAYS_CODE.index("function setLayer"):]
        block = block[: block.index("function exists")]
        self.assertNotIn("rememberScroll", block)
        self.assertNotIn("removeAttribute(ATTR)", block)
        self.assertNotIn("persist(", block)

    def test_the_composer_stays_below_the_layer(self):
        """The reviewer must be able to ask GO about the drawing they are
        looking at without putting it down - the reason no "Open in Composer"
        handoff is needed."""
        rule = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index('html[data-tray-layer="eye"] #eye-pane {'):]
        rule = rule[: rule.index("}")]
        self.assertIn("--chat-height", rule)
        self.assertIn("bottom:", rule)

    def test_the_same_control_raises_and_lowers_it(self):
        """No second switcher entry, and no separate close button to hunt
        for - Section 11's "do not overload the interface"."""
        self.assertIn("key === currentLayer() ? null : key", TRAYS_CODE)

    def test_a_dismiss_affordance_exists_where_the_work_is(self):
        self.assertIn('id="eye-layer-dismiss"', BASE_HTML)
        self.assertIn("eye-layer-dismiss", TRAYS_CODE)
        # Present only while the sheet is up, never a dead control beside
        # Maximize.
        self.assertIn(".eye-layer-dismiss { display: none; }", CSS_NO_COMMENTS)

    def test_escape_lowers_the_layer_before_the_work_beneath_it(self):
        block = TRAYS_CODE[TRAYS_CODE.index("if (event.key !== 'Escape') return;"):]
        block = block[: block.index("clear();") + 10]
        self.assertLess(block.index("currentLayer()"), block.index("clear()"))

    def test_a_preference_stored_while_eye_was_a_tray_is_retired(self):
        """Eye was a tray in the build immediately before this one, so a real
        reviewer can have "eye" persisted as a tray focus."""
        self.assertIn("isLayer(restored)", TRAYS_CODE)


class TheFrameIsPinnedWithoutJavascriptTests(unittest.TestCase):
    """CLAUDE-MOBILE-FRAME-PIN-01. Product Owner, from live phone use: "the
    chat.composer is not fixed at the bottom... the page menu is not fixed on
    top."

    Root cause of both: the frame was made conditional on things it should
    never have depended on. The Composer's anchoring was gated on
    `data-tray-focus`, a JS-set attribute, so any page or moment without it
    fell back to the desktop `position: sticky` rule - anchored to a column,
    not to the viewport. And the header relied on .app-shell's fixed-height
    flex column without .workspace-topbar carrying a shrink guard, which is
    exactly the child a flex container compresses first because it is the one
    that wraps.
    """

    def test_the_composer_is_anchored_without_any_application_state(self):
        """At phone widths the frame IS the layout. If the script never runs,
        the Composer must still be at the bottom."""
        phone = _phone_block()
        rule = phone[phone.index(".chat-region {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("position: fixed", rule)
        self.assertIn("bottom:", rule)
        # The rule itself must not be gated on the attribute.
        selector_line = phone[: phone.index(".chat-region {")].splitlines()[-1]
        self.assertNotIn("data-tray-focus", selector_line)

    def test_the_composer_height_is_still_reserved_only_where_one_exists(self):
        phone = _phone_block()
        self.assertIn(".app-shell-body:has(.chat-region)", phone)

    def test_the_header_carries_a_shrink_guard(self):
        """.app-shell is a fixed-height flex column with overflow:hidden, so
        anything that must not move needs flex-shrink:0."""
        phone = _phone_block()
        rule = phone[phone.index(".workspace-topbar,"):]
        rule = rule[: rule.index("}")]
        self.assertIn(".tray-switcher", rule)
        self.assertIn("flex-shrink: 0", rule)

    def test_the_document_agrees_with_the_shell_about_where_the_bottom_is(self):
        """body resolves height:100% against the LAYOUT viewport, which on iOS
        is the URL-bar-retracted height - taller than what is visible."""
        phone = _phone_block()
        rule = phone[phone.index("html,"):]
        rule = rule[: rule.index("}")]
        self.assertIn("100dvh", rule)
        self.assertLess(rule.index("100vh"), rule.index("100dvh"))

    def test_desktop_focus_mode_still_anchors_the_composer_too(self):
        """The un-gating is additive - the desktop focused-tray behaviour is
        unchanged, not replaced."""
        self.assertIn("html[data-tray-focus] .chat-region", CSS_NO_COMMENTS)


class TheDocumentItselfCannotBeDraggedTests(unittest.TestCase):
    """CLAUDE-MOBILE-FRAME-PIN-02. Product Owner: "when I move the upper part
    of the page up and down the full page moves up and down... when I move the
    composer it moves up and down as well."

    Both reports were the same bug. `overflow: hidden` does not stop iOS
    rubber-banding the document on a touch-drag, and while the document is
    displaced everything positioned against the viewport travels with it - so
    the header looked unpinned and the fixed Composer looked like it moved.
    No amount of pinning could have fixed that; the document has to be out of
    flow.
    """

    def test_the_document_is_taken_out_of_flow(self):
        """The difference between "this does not scroll" and "there is nothing
        here to scroll"."""
        phone = _phone_block()
        # Anchored on the OWNING SELECTOR, not on the first `inset: 0`.
        #
        # The previous anchor took the first `inset: 0` in the phone block and
        # walked back to its opening brace. That held only while exactly one
        # rule in the block used the shorthand. CLAUDE-MOBILE-MENU-REPAIR-01's
        # drawer scrim (html.mobile-nav-open body::after) legitimately uses it
        # too and happens to sit earlier in the file, so the assertion started
        # describing the scrim instead of the document.
        #
        # This finds the rule whose selector is exactly `body` and asserts
        # against that, which is what the test was always about. It is now
        # indifferent to how many other rules use inset, and to their order.
        import re as _re

        body_rules = [
            match for match in _re.finditer(r"(^|[;}])\s*body\s*\{([^}]*)\}", phone)
            if "inset: 0" in match.group(2)
        ]
        self.assertTrue(body_rules, "no phone-block `body` rule using inset")
        declarations = body_rules[0].group(2)
        self.assertIn("position: fixed", declarations)
        self.assertIn("inset: 0", declarations)

    def test_the_document_refuses_overscroll(self):
        """No regex here on purpose: the earlier version needed an escaped
        newline to span the `html,` / `body {` selector pair, and an escape
        inside a shell-authored patch is exactly what corrupted this file
        once already."""
        phone = _phone_block()
        rule = phone[phone.index("overscroll-behavior: none"):]
        # Walk back to the selector that owns this declaration.
        owner = phone[: phone.index("overscroll-behavior: none")]
        owner = owner[owner.rindex("}") + 1:]
        self.assertIn("html", owner)
        self.assertIn("body", owner)

    def test_every_real_scroll_region_ends_its_own_gesture(self):
        """Scroll chaining is the default, and it is what handed a drag that
        ran out of conversation thread to the page underneath."""
        phone = _phone_block()
        contain = phone[phone.index("overscroll-behavior: contain") - 900:]
        contain = contain[: contain.index("overscroll-behavior: contain") + 40]
        for region in ("main", ".conversation-thread", ".lists-pane",
                       ".workspace-pane-toolbox", ".eye-pane-body"):
            with self.subTest(region=region):
                self.assertIn(region, contain)

    def test_the_breathing_room_is_on_the_content_not_the_composer(self):
        """A margin on the Composer would open a transparent strip with the
        scrolling work showing through underneath it."""
        phone = _phone_block()
        composer = phone[phone.index(".chat-region {"):]
        composer = composer[: composer.index("}")]
        self.assertNotIn("margin", composer)

        main_rule = phone[phone.rindex("    main {"):]
        main_rule = main_rule[: main_rule.index("}")]
        self.assertIn("padding-top", main_rule)
        self.assertIn("padding-bottom", main_rule)

    def test_the_reserved_strip_clears_the_composer_with_room_to_spare(self):
        phone = _phone_block()
        # Exactly one such rule in the phone block - two would drift apart.
        self.assertEqual(phone.count(".app-shell-body:has(.chat-region)"), 1)
        rule = phone[phone.index(".app-shell-body:has(.chat-region)"):]
        rule = rule[: rule.index("}")]
        self.assertIn("calc(var(--chat-height", rule)


class TheShellCannotDriftSidewaysTests(unittest.TestCase):
    """CLAUDE-MOBILE-FRAME-PIN-04. Product Owner: "Right now there is a little
    left and right drift. Lock the main app shell."

    PIN-03 refused the horizontal pan GESTURE, but refusing a gesture does not
    remove an overflow that genuinely exists - it only closes one way of
    reaching it. Something was still wider than the viewport.
    """

    # Built from chr(10) rather than written as an escape: a heredoc rewrote
    # this needle once already and broke the file.
    SHELL_RULE = "html," + chr(10) + "body," + chr(10) + ".app-shell {"
    EDGE_RULE = ".workspace-topbar," + chr(10) + ".tray-switcher,"

    def _shell_block(self):
        block = CSS_NO_COMMENTS[CSS_NO_COMMENTS.rindex(self.SHELL_RULE):]
        return block[: block.index("}")]

    def test_the_flex_item_that_could_not_shrink_now_can(self):
        """A flex item's automatic minimum size is its CONTENT size, not zero,
        so `flex: 1` without `min-width: 0` refuses to shrink below its
        intrinsic width and pushes its whole row wider than the container. The
        composer row gained a 44px "+" and a "Make a new Q" row, and the drift
        appeared - the button was not the bug, it was the straw."""
        needle = ".conversation-input-form textarea," + chr(10)
        rule = CSS_NO_COMMENTS[CSS_NO_COMMENTS.index(needle):]
        rule = rule[: rule.index("}")]
        self.assertIn("min-width: 0", rule)

    def test_the_shell_is_locked_at_every_width(self):
        """"The main app shell" is not a mobile-only statement, and a narrowed
        desktop window had the same drift available to it - so this rule sits
        OUTSIDE the phone media query."""
        block = self._shell_block()
        self.assertIn("overflow-x", block)
        self.assertIn("max-width: 100%", block)
        # Outside the media query: the phone block ends before this rule starts.
        phone_end = CSS_NO_COMMENTS.index(self.SHELL_RULE)
        self.assertGreater(phone_end, CSS_NO_COMMENTS.index("@media (max-width: 640px)"))

    def test_clip_is_preferred_over_hidden_with_a_fallback(self):
        """`hidden` makes the element a scroll CONTAINER, still scrollable
        programmatically; `clip` refuses outright. `hidden` stays first for
        anything without clip support."""
        block = self._shell_block()
        self.assertLess(block.index("overflow-x: hidden"), block.index("overflow-x: clip"))

    def test_inner_scroll_regions_keep_their_own_horizontal_scroll(self):
        """A wide table, a drawing or a PDF page must still scroll sideways
        inside its own box - this stops the SHELL moving, not the content."""
        block = CSS_NO_COMMENTS[CSS_NO_COMMENTS.rindex(self.EDGE_RULE):]
        block = block[: block.index("}")]
        for inner in (".document-viewer-canvas-container", ".table-scroll", ".eye-canvas-viewport"):
            with self.subTest(region=inner):
                self.assertNotIn(inner, block)

if __name__ == "__main__":
    unittest.main()
