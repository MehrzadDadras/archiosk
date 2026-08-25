"""CLAUDE-MOBILE-SHELL-STABILITY-01 - the shell stays put, on every surface.

Product Owner standing rule: "no whole-page horizontal drift; no accidental
lateral movement of the application shell… the outer application shell itself
remains anchored." And, pointedly:

    "Do not solve this by merely hiding overflow if an underlying component is
    actually wider than the viewport. Find and correct the source of width
    instability."

TWO ROOT CAUSES, both missed by the three previous attempts at this.

1. THE LOCK NEVER REACHED THE LANDING PAGE. CLAUDE-MOBILE-FRAME-PIN-04 locked
   `html, body, .app-shell` - and `.app-shell` exists in exactly ONE of five
   shells. The landing page renders through landing_shell.html, so the first
   surface anyone sees was never locked at all.

2. A COMPONENT GENUINELY WIDER THAN THE VIEWPORT. ocean_field.js sized the
   background canvas from `window.innerWidth` and wrote it back as an explicit
   pixel width, overriding the CSS `width: 100%`. On iOS window.innerWidth is
   the VISUAL viewport and inflates during rubber-band and pinch-zoom, so the
   canvas could become genuinely wider than its container - which is precisely
   the "begins moving sideways before springing back" that was reported.
   `.landing-page`'s own `overflow-x: hidden` was hiding that, not preventing
   it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "static" / "css" / "main.css").read_text(encoding="utf-8"), flags=re.S)
OCEAN = (ROOT / "static" / "js" / "ocean_field.js").read_text(encoding="utf-8")
OCEAN_CODE = re.sub(r"(?<![:\w])//.*$", "", re.sub(r"/\*.*?\*/", "", OCEAN, flags=re.S), flags=re.M)

# Every shell root in the application, and the template each one lives in.
# If a sixth shell is ever added, this list is where it must be declared.
SHELL_ROOTS = {
    ".landing-page": "landing_shell.html",
    ".gateway-shell": "gateway_shell.html",
    ".auth-shell-page": "auth_shell.html",
    ".app-shell": "base.html",
    ".app-main": "panel_shell.html",
}


class TheSourceOfWidthWasFixedNotHiddenTests(unittest.TestCase):
    """Cause 2, and the one the Product Owner explicitly warned against
    papering over."""

    def test_the_canvas_no_longer_measures_the_window(self):
        """window.innerWidth is the VISUAL viewport on iOS and inflates during
        rubber-band and pinch-zoom."""
        resize = OCEAN_CODE[OCEAN_CODE.index("function resize()"):]
        resize = resize[: resize.index("function buildPoints")]
        self.assertNotIn("window.innerWidth", resize)
        self.assertNotIn("window.innerHeight", resize)

    def test_it_measures_the_element_instead(self):
        resize = OCEAN_CODE[OCEAN_CODE.index("function resize()"):]
        resize = resize[: resize.index("function buildPoints")]
        self.assertIn("getBoundingClientRect", resize)

    def test_it_writes_no_pixel_width_at_all(self):
        """An explicit style.width overrides the CSS `width: 100%` with a fixed
        number. Not writing one is what makes exceeding the container
        impossible by construction rather than by clamping."""
        resize = OCEAN_CODE[OCEAN_CODE.index("function resize()"):]
        resize = resize[: resize.index("function buildPoints")]
        self.assertNotIn("style.width", resize)
        self.assertNotIn("style.height", resize)

    def test_the_backing_store_is_still_scaled_for_device_pixels(self):
        """Removing the pixel size must not have cost the retina rendering."""
        resize = OCEAN_CODE[OCEAN_CODE.index("function resize()"):]
        resize = resize[: resize.index("function buildPoints")]
        self.assertIn("devicePixelRatio", resize)
        self.assertIn("canvas.width", resize)
        self.assertIn("setTransform", resize)


class EveryShellRootIsLockedTests(unittest.TestCase):
    """Cause 1. `.app-shell` was one of five."""

    def test_each_shell_root_really_exists_in_its_template(self):
        """A lock on a class nobody renders protects nothing - and one of these
        selectors was invented on the first attempt at this fix."""
        for selector, template in SHELL_ROOTS.items():
            with self.subTest(shell=template):
                markup = (ROOT / "templates" / template).read_text(encoding="utf-8")
                self.assertIn(f'class="{selector.lstrip(".")}', markup)

    def test_each_shell_root_is_width_locked(self):
        for selector in SHELL_ROOTS:
            with self.subTest(shell=selector):
                self.assertRegex(CSS, re.escape(selector) + r"[^{]*\{[^}]*overflow-x")

    def test_the_phone_refuses_the_horizontal_gesture_on_each_shell(self):
        for selector in (".landing-page", ".gateway-shell", ".auth-shell-page", ".app-shell"):
            with self.subTest(shell=selector):
                self.assertRegex(CSS, re.escape(selector) + r"[^{]*\{[^}]*touch-action:\s*pan-y")


class BoundedViewersMayStillPanTests(unittest.TestCase):
    """"Horizontal panning is allowed only inside deliberately bounded content
    that requires it: drawings; large images; wide tables." The shell is
    anchored; the content is not."""

    def test_no_universal_selector_was_used_to_lock_everything(self):
        """`*` would also catch the viewers that legitimately pan. The shell
        roots are a small knowable set and are listed explicitly."""
        self.assertNotRegex(CSS, r"(?m)^\*\s*\{[^}]*touch-action")
        self.assertNotRegex(CSS, r"(?m)^\*\s*\{[^}]*overflow-x")

    def test_the_horizontal_viewers_are_not_in_the_locked_set(self):
        locked = CSS[CSS.index(".landing-page,"):]
        locked = locked[: locked.index("}")]
        for viewer in (".document-viewer-canvas-container", ".table-scroll",
                       ".eye-canvas-viewport", ".thumbnails-list"):
            with self.subTest(viewer=viewer):
                self.assertNotIn(viewer, locked)

    def test_those_viewers_still_declare_their_own_scrolling(self):
        for viewer in (".document-viewer-canvas-container", ".table-scroll", ".eye-canvas-viewport"):
            with self.subTest(viewer=viewer):
                self.assertRegex(CSS, re.escape(viewer) + r"[^{]*\{[^}]*overflow")


class TheLandingPageAgreesWithTheViewportTests(unittest.TestCase):
    def test_it_uses_the_dynamic_viewport_unit(self):
        """100vh on iOS is the URL-bar-retracted height, so a 100vh landing
        page is taller than the screen and invites the rubber-band this whole
        rule exists to stop."""
        block = CSS[CSS.index(".landing-page {", CSS.index("CLAUDE-MOBILE-SHELL-STABILITY-01")
                              if "CLAUDE-MOBILE-SHELL-STABILITY-01" in CSS else 0):]
        self.assertIn("100dvh", CSS)

    def test_the_fixed_canvas_holds_its_own_edge(self):
        """It is positioned against the viewport and therefore sits outside
        every shell root's clipping."""
        rule = CSS[CSS.rindex(".landing-field-canvas {"):]
        rule = rule[: rule.index("}")]
        self.assertIn("max-width: 100vw", rule)


class NothingOutsideTheScreenTests(unittest.TestCase):
    """CLAUDE-MOBILE-SHELL-STABILITY-02. Product Owner: "Make sure no text ever
    extends outside phone screen keeping a minimum margins on all sides and
    there is no white area showing behind the phone screen."

    Three separate causes that are easy to mistake for one.
    """

    def test_every_shell_declares_viewport_fit_cover(self):
        """Without it the browser leaves its own white bands in the notch and
        home-indicator areas, whatever the page paints."""
        for template in ("landing_shell", "auth_shell", "gateway_shell", "base", "panel_shell"):
            with self.subTest(shell=template):
                markup = (ROOT / "templates" / f"{template}.html").read_text(encoding="utf-8")
                self.assertIn("viewport-fit=cover", markup)

    def test_every_shell_paints_the_browser_chrome(self):
        for template in ("landing_shell", "auth_shell", "gateway_shell", "base", "panel_shell"):
            with self.subTest(shell=template):
                markup = (ROOT / "templates" / f"{template}.html").read_text(encoding="utf-8")
                self.assertIn('name="theme-color"', markup)

    def test_the_document_itself_is_painted(self):
        """The overscroll area takes its colour from the ROOT element, not from
        any app container - so html must carry it, not just body."""
        for selector in ("html {", "body {"):
            with self.subTest(selector=selector):
                rule = CSS[CSS.rindex(selector):]
                rule = rule[: rule.index("}")]
                self.assertIn("background-color", rule)

    def test_a_minimum_gutter_exists_on_every_shell(self):
        """env() resolves to 0 where there is no inset, so max() gives a real
        margin on every phone and a larger one only where hardware needs it."""
        for selector in (".landing-page", ".gateway-shell", ".auth-shell-page", ".app-shell"):
            with self.subTest(shell=selector):
                self.assertRegex(
                    CSS,
                    re.escape(selector) + r"[^{]*\{[^}]*max\(0\.85rem, env\(safe-area-inset-left\)\)",
                )

    def test_the_fixed_regions_carry_their_own_inset(self):
        """They sit outside the shell's padding box, so a shell gutter does not
        reach them - they would run under the rounded corners."""
        for selector in (".workspace-topbar,", ".chat-region {"):
            with self.subTest(region=selector):
                block = CSS[CSS.rindex(selector):]
                block = block[: block.index("}")]
                self.assertIn("env(safe-area-inset", block)

    def test_the_composer_clears_the_home_indicator(self):
        block = CSS[CSS.rindex(".chat-region {"):]
        block = block[: block.index("}")]
        self.assertIn("padding-bottom: env(safe-area-inset-bottom)", block)

    def test_unbreakable_text_cannot_push_the_shell_wider(self):
        """A long URL, file name or drawing number has no break opportunity, so
        it widens its container and takes the whole shell with it. That is a
        genuine width source, the same class of fault as the canvas - and the
        external-research citations print full URLs, which are exactly this
        shape."""
        block = CSS[CSS.rindex(".conv-message-text,"):]
        block = block[: block.index("}")]
        self.assertIn("overflow-wrap: anywhere", block)
        self.assertIn("word-break: break-word", block)


if __name__ == "__main__":
    unittest.main()
