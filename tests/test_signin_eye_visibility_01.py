"""
CLAUDE-SIGNIN-EYE-VISIBILITY-01 - sign-in password toggle icon visibility fix.

A live walkthrough found the sign-in password-reveal control's two icons
(open eye / eye-with-slash) rendering superimposed on each other at all
times ("the toggle eyes are beside each other which is confusing").
Root cause: static/js/login.js used to toggle the SVGs' `hidden` DOM
property, but `hidden` has no effect on SVG elements in Chromium (SVG's
own UA stylesheet does not define a `[hidden]` rule the way html.css
does for HTML elements) - both icons stayed visible at once regardless
of state. Fixed by driving icon visibility from the button's own
aria-pressed attribute via CSS (static/css/main.css's
`.password-toggle[aria-pressed=...] .password-toggle-icon-*` rules),
with login.js only responsible for keeping aria-pressed correct.

These tests are markup/asset-content checks only (Flask test client,
no browser) - they can't exercise the CSS cascade itself, but they lock
in the two things that regressed: the dead `hidden`-property approach
must not come back, and the CSS rule + markup contract it depends on
(aria-pressed on the button, matching class names on both icons) must
stay present.
"""
from __future__ import annotations

import unittest
from pathlib import Path


class SigninPasswordToggleVisibilityTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_hide_icon_no_longer_carries_a_static_hidden_attribute(self):
        # The `hidden` attribute never actually hid the SVG (Chromium
        # quirk) - visibility is now CSS-driven off aria-pressed instead,
        # so the markup must not rely on the dead attribute any more.
        body = self.client.get("/login").get_data(as_text=True)
        hide_icon_start = body.index('class="password-toggle-icon-hide"')
        tag_end = body.index(">", hide_icon_start)
        icon_tag = body[hide_icon_start:tag_end]
        # "aria-hidden" (a real, separate, deliberately-kept decorative-icon
        # attribute) legitimately contains the substring "hidden" - only the
        # bare boolean `hidden` attribute token must be gone.
        attr_tokens = icon_tag.replace("=", " ").split()
        self.assertNotIn("hidden", attr_tokens)

    def test_toggle_button_starts_with_aria_pressed_false(self):
        # The CSS contract (`main.css`) keys visibility off this exact
        # attribute/value - the initial server-rendered state must match
        # what static/css/main.css's `[aria-pressed="false"]` rule expects.
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('id="password-toggle"', body)
        toggle_start = body.index('id="password-toggle"')
        button_open_tag = body.rindex("<button", 0, toggle_start)
        button_close_tag = body.index(">", toggle_start)
        button_tag = body[button_open_tag:button_close_tag]
        self.assertIn('aria-pressed="false"', button_tag)

    def test_both_icon_classes_still_present_for_css_to_key_off(self):
        body = self.client.get("/login").get_data(as_text=True)
        self.assertIn('class="password-toggle-icon-show"', body)
        self.assertIn('class="password-toggle-icon-hide"', body)


class LoginJsNoLongerSetsSvgHiddenPropertyTests(unittest.TestCase):
    """The actual root-cause regression guard: login.js must never go back
    to setting .hidden on the icon SVGs directly - that IDL property has
    no effect on SVGElement in Chromium and silently no-ops, which is
    exactly how both icons ended up rendered at once."""

    def setUp(self):
        self.login_js = Path("static/js/login.js").read_text(encoding="utf-8")

    def test_does_not_set_hidden_property_on_the_icons(self):
        # Checks for the functional assignment specifically (not just the
        # substring), since this file's own explanatory comment legitimately
        # names the old, dead approach in prose.
        self.assertNotIn("showIcon.hidden =", self.login_js)
        self.assertNotIn("hideIcon.hidden =", self.login_js)

    def test_still_toggles_aria_pressed_and_input_type(self):
        self.assertIn("toggle.setAttribute('aria-pressed'", self.login_js)
        self.assertIn("input.type = revealed", self.login_js)


class MainCssIconVisibilityRuleTests(unittest.TestCase):
    """Locks in the CSS contract login.html/login.js now depend on."""

    def setUp(self):
        self.main_css = Path("static/css/main.css").read_text(encoding="utf-8")

    def test_icon_visibility_is_driven_by_aria_pressed(self):
        self.assertIn('.password-toggle[aria-pressed="false"] .password-toggle-icon-hide', self.main_css)
        self.assertIn('.password-toggle[aria-pressed="true"] .password-toggle-icon-show', self.main_css)


if __name__ == "__main__":
    unittest.main()
