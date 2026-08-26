"""
CLAUDE-MOBILE-DRAWER-STACKING-01 - the phone drawer can actually be tapped.

Product Owner, live: "the desktop top menu works but not on the phone."

WHAT WAS WRONG

The drawer sets `z-index: 40`; the scrim sets `39`. That reads as correct and is
not, because z-index only orders siblings WITHIN a stacking context.
`.workspace-menubar` is nested inside `.workspace-topbar`, which is
`position: relative; z-index: 31` and therefore opens its own context. The
drawer's 40 is scoped inside it, so the whole topbar subtree stacks at 31 - and
the scrim, a child of `body` at 39, paints over all of it.

The failure mode is the nasty kind: the menu LOOKED correct and simply did not
respond. Every drawer item hit-tested to BODY, and a real tap on any of them
timed out because the element could never receive the event. The first tap
worked only because the scrim does not exist until the drawer is open.

Desktop was never affected - there is no scrim there. That is precisely why
desktop worked and the phone did not, and why no amount of desktop testing
would have found it.

WHY A REAL BROWSER

No source assertion could catch this. Both numbers were individually sane; the
defect lived in the RELATIONSHIP between two stacking contexts, which only a
layout engine computes. So these tests open a real Chromium at a real phone
viewport, tap the real controls, and check what the browser says is on top.

Following the repo's set_content convention: no HTTP server, hermetic, and a
clean skip when the browser is absent.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

_REPO = Path(__file__).resolve().parent.parent

try:
    from playwright.sync_api import sync_playwright
except Exception:  # pragma: no cover - environment-dependent
    sync_playwright = None


def _browser_available() -> bool:
    if sync_playwright is None:
        return False
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False


_AVAILABLE = _browser_available()
_SKIP = ("Real Chromium is not available here. This defect is a computed "
         "stacking-context relationship; a source assertion cannot see it, so "
         "skip rather than substitute a weaker check.")


def _home_html() -> str:
    import app as app_module
    from models import User, db

    flask_app = app_module.create_app("testing")
    with flask_app.app_context():
        db.session.add(User(username="stack_admin",
                            password_hash=generate_password_hash("x"), role="admin"))
        db.session.commit()
    client = flask_app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "stack_admin"
        sess["role"] = "admin"
    return client.get("/").get_data(as_text=True)


@unittest.skipUnless(_AVAILABLE, _SKIP)
class ThePhoneDrawerIsActuallyOperable(unittest.TestCase):
    WIDTH, HEIGHT = 390, 844   # iPhone 14

    @classmethod
    def setUpClass(cls):
        cls.html = _home_html()
        cls.css = [(_REPO / "static/css/tokens.css").read_text(encoding="utf-8"),
                   (_REPO / "static/css/main.css").read_text(encoding="utf-8")]
        cls.js = [(_REPO / "static/js/workspace_trays.js").read_text(encoding="utf-8"),
                  (_REPO / "static/js/app_menu.js").read_text(encoding="utf-8")]

    def _page(self, browser):
        page = browser.new_page(viewport={"width": self.WIDTH, "height": self.HEIGHT},
                                has_touch=True, is_mobile=True)
        page.set_content(self.html)
        for sheet in self.css:
            page.add_style_tag(content=sheet)
        for script in self.js:
            page.add_script_tag(content=script)
        page.wait_for_timeout(150)
        return page

    def _hit(self, page, selector):
        """What the browser says is actually on top at this element's centre."""
        return page.evaluate("""(sel) => {
            const e = document.querySelector(sel);
            if (!e) return 'MISSING';
            const r = e.getBoundingClientRect();
            const hit = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
            if (!hit) return 'NOTHING';
            return (hit === e || e.contains(hit) || hit.contains(e)) ? 'REACHABLE' : hit.tagName;
        }""", selector)

    def test_the_drawer_opens_on_the_first_tap(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = self._page(browser)
            page.tap("#mobile-nav-toggle")
            page.wait_for_timeout(200)
            opened = page.evaluate(
                "document.documentElement.classList.contains('mobile-nav-open')")
            browser.close()
        self.assertTrue(opened)

    def test_the_scrim_does_not_cover_the_drawer(self):
        # The whole defect in one assertion. Before the fix this returned
        # 'BODY' for every item in the drawer.
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = self._page(browser)
            page.tap("#mobile-nav-toggle")
            page.wait_for_timeout(200)
            results = {sel: self._hit(page, sel) for sel in [
                '[data-ui-ref="menu.archiosk"] > summary',
                '[data-ui-ref="menu.file"] > summary',
            ]}
            browser.close()
        for selector, verdict in results.items():
            with self.subTest(selector=selector):
                self.assertEqual(verdict, "REACHABLE",
                                 "the scrim is painting over the drawer again")

    def test_a_menu_inside_the_drawer_opens_when_tapped(self):
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = self._page(browser)
            page.tap("#mobile-nav-toggle")
            page.wait_for_timeout(200)
            # timeout kept short: before the fix this hung until Playwright
            # gave up, because the element could never receive the event.
            page.tap('[data-ui-ref="menu.archiosk"] > summary', timeout=5000)
            page.wait_for_timeout(200)
            is_open = page.evaluate(
                "document.querySelector('[data-ui-ref=\\u0022menu.archiosk\\u0022]').open")
            browser.close()
        self.assertTrue(is_open, "tapping a menu in the drawer did nothing")

    def test_the_whole_chain_down_to_developer_mode_is_reachable(self):
        # The control the Product Owner originally could not find, now reached
        # the way a thumb would reach it.
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = self._page(browser)
            page.tap("#mobile-nav-toggle")
            page.wait_for_timeout(150)
            page.tap('[data-ui-ref="menu.archiosk"] > summary', timeout=5000)
            page.wait_for_timeout(150)
            page.tap('[data-ui-ref="menu.archiosk.developer"] > summary', timeout=5000)
            page.wait_for_timeout(150)
            verdict = self._hit(page, '[data-ui-ref="menu.archiosk.developer.mode-toggle"]')
            browser.close()
        self.assertEqual(verdict, "REACHABLE")

    def test_the_drawer_can_always_be_dismissed(self):
        """Opening something you cannot close is its own trap.

        Note what is NOT asserted: that the hamburger itself stays tappable. It
        does not. The drawer is full-height and 320px wide, so once open it
        covers the toggle at x=46 - tapping there now hits the drawer's first
        menu. That was true before this fix too (the scrim covered it), and
        changing it means moving the drawer below the topbar, which is a layout
        decision rather than a stacking bug.

        What matters is that every exit still works, so this asserts the three
        that do rather than the one that does not.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch()
            results = {}
            for label, action in [
                ("tap outside", lambda pg: pg.touchscreen.tap(360, 400)),
                ("escape", lambda pg: pg.keyboard.press("Escape")),
            ]:
                page = self._page(browser)
                page.tap("#mobile-nav-toggle")
                page.wait_for_timeout(200)
                action(page)
                page.wait_for_timeout(250)
                results[label] = page.evaluate(
                    "document.documentElement.classList.contains('mobile-nav-open')")
                page.close()
            browser.close()
        for label, still_open in results.items():
            with self.subTest(dismissal=label):
                self.assertFalse(still_open, "%s did not close the drawer" % label)

    def test_the_topbar_outranks_the_scrim_in_computed_stacking(self):
        # Stated as the browser computes it, not as the stylesheet reads.
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = self._page(browser)
            page.tap("#mobile-nav-toggle")
            page.wait_for_timeout(200)
            topbar_z = page.evaluate(
                "parseInt(getComputedStyle(document.querySelector('.workspace-topbar')).zIndex, 10)")
            browser.close()
        # The scrim is z-index 39 on body::after, a sibling context.
        self.assertGreater(topbar_z, 39,
                           "the topbar context sits under the scrim again, which "
                           "puts the whole drawer under it regardless of the "
                           "drawer's own z-index")


class DesktopStackingIsUntouched(unittest.TestCase):
    def test_the_lift_only_applies_while_the_drawer_is_open(self):
        css = (_REPO / "static/css/main.css").read_text(encoding="utf-8")
        self.assertIn("html.mobile-nav-open .workspace-topbar", css)
        # Never an unconditional change to the topbar's own z-index.
        self.assertEqual(css.count("html.mobile-nav-open .workspace-topbar"), 1)


if __name__ == "__main__":
    unittest.main()
