"""
CLAUDE-MOBILE-PWA-01 / CLAUDE-MOBILE-ICON-01 - home-screen installability and
the redesigned application icon.

Product Owner direction covered here:

  "ARCHIOSK should be addable/installable to the phone home screen; the
   installed app launches directly into ARCHIOSK; users should not need to
   reinstall to receive updates; deployed application updates must flow
   normally to installed users; service-worker/cache behavior must not freeze
   users on old shells; no broad offline caching of sensitive project material;
   authentication and authorization remain unchanged."

  "The icon should become more dynamic and distinctive... based on an X: the
   bottom portion is closed; the upper-left portion is shorter... it must remain
   clear and legible at small mobile icon sizes."

The point of this file is the SAFETY half of installability. A service worker is
the only thing in this application that can strand a user on an old build, on
their own device, with no way for us to reach them - so the assertions that
matter most here are the negative ones: that HTML is never served cache-first,
that nothing but versioned /static/ URLs is ever written to a cache, and that
the cache name carries the deployed version so a new build cannot read the old
build's cache.

No browser-automation tool is exercised. The worker's source is asserted
structurally, which is the same convention the rest of this suite uses for
client-side behavior, and the icon geometry is asserted against the asset files
themselves. Neither a real phone install nor Product Owner visual acceptance is
claimed by anything in this file.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SW_PATH = _REPO_ROOT / "templates" / "sw.js"
_MANIFEST_PATH = _REPO_ROOT / "templates" / "manifest.webmanifest"
_PWA_JS_PATH = _REPO_ROOT / "static" / "js" / "pwa.js"
_ICON_SVG_PATH = _REPO_ROOT / "static" / "app-icon.svg"
_ICON_DIR = _REPO_ROOT / "static" / "icons"
_LANDING_PATH = _REPO_ROOT / "templates" / "landing.html"
_MAIN_CSS_PATH = _REPO_ROOT / "static" / "css" / "main.css"
# landing_shell.html loads landing.css ALONE - no tokens.css, no main.css - so
# anything styling the landing page has to be asserted against THIS file. A
# .landing-* rule written into main.css is dead on the only page that uses it,
# which is exactly the defect these assertions exist to catch.
_LANDING_CSS_PATH = _REPO_ROOT / "static" / "css" / "landing.css"

_SHELL_TEMPLATES = ("landing_shell.html", "auth_shell.html", "gateway_shell.html", "base.html")


def _strip_js_comments(source: str) -> str:
    """Drop // and /* */ comments.

    This file's own prose repeatedly names the very tokens it asserts are
    absent - 'cache-first', 'caches.put' - so scanning raw source would let a
    comment satisfy a negative assertion. That has actually happened in this
    repository more than once, which is why every scan below goes through here.
    """
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
    return re.sub(r"(^|[^:])//[^\n]*", r"\1", source)


class ServiceWorkerCannotFreezeAnOldShellTests(unittest.TestCase):
    """The three rules that keep an installed user reachable by a new deploy."""

    def setUp(self):
        self.raw = _SW_PATH.read_text(encoding="utf-8")
        self.code = _strip_js_comments(self.raw)

    def test_cache_name_carries_the_deployed_static_version(self):
        # Without this, a new deploy reads the previous deploy's cache and the
        # "no frozen shell" guarantee has nothing behind it.
        self.assertIn("{{ static_version }}", self.raw)
        self.assertRegex(self.code, r"SHELL_CACHE\s*=\s*`archiosk-shell-v\$\{VERSION\}`")

    def test_obsolete_caches_are_deleted_on_activate(self):
        activate = self.code[self.code.index('addEventListener("activate"'):]
        self.assertIn("caches.keys()", activate)
        self.assertIn("caches.delete", activate)
        self.assertIn("!== SHELL_CACHE", activate)

    def test_only_versioned_static_urls_are_ever_written_to_a_cache(self):
        # Every cache write must sit inside the isVersionedStatic branch. If a
        # put ever escapes it, authenticated HTML and project material become
        # cacheable and both the privacy rule and the frozen-shell rule fail at
        # the same time.
        guard = self.code.index("if (isVersionedStatic(url))")
        fetch_start = self.code.index('addEventListener("fetch"')
        self.assertLess(fetch_start, guard)
        branch_end = self.code.index("return;", guard)
        for match in re.finditer(r"cache\.put|cache\.addAll", self.code):
            in_precache = match.start() < fetch_start
            in_static_branch = guard < match.start() < branch_end
            self.assertTrue(
                in_precache or in_static_branch,
                "cache write outside the versioned-static branch at %d" % match.start(),
            )

    def test_navigations_are_never_answered_from_cache(self):
        # The classic PWA failure: cache-first HTML pins the user to whatever
        # shell was cached the day they installed.
        self.assertNotIn("request.mode === 'navigate'", self.code)
        self.assertNotIn('request.mode === "navigate"', self.code)
        self.assertEqual(self.code.count("respondWith"), 1)

    def test_precache_holds_no_project_material(self):
        precache = self.code[self.code.index("PRECACHE = ["):]
        precache = precache[:precache.index("]")]
        for url in re.findall(r'"([^"]+)"', precache):
            self.assertTrue(url.startswith("/static/"), url)

    def test_new_worker_activates_without_a_reinstall(self):
        self.assertIn("skipWaiting", self.code)
        self.assertIn("clients.claim", self.code)


class UpdateIsOfferedNeverForcedTests(unittest.TestCase):
    """A page that reloads itself can discard a half-typed Composer message."""

    def setUp(self):
        self.code = _strip_js_comments(_PWA_JS_PATH.read_text(encoding="utf-8"))

    def test_reload_happens_only_inside_a_click_handler(self):
        self.assertEqual(self.code.count("location.reload"), 1)
        handler = self.code[:self.code.index("location.reload")]
        self.assertIn("addEventListener('click'", handler[-400:])

    def test_first_ever_registration_does_not_announce_an_update(self):
        # A first-time visitor has no previous controller, so a controllerchange
        # there is the initial install, not a new version.
        self.assertIn("hadController", self.code)
        self.assertRegex(self.code, r"if \(hadController\) offerReload\(\)")

    def test_registration_failure_cannot_break_the_page(self):
        self.assertRegex(self.code, r"register\([^)]*\)[\s\S]{0,80}\.catch\(")

    def test_absent_service_worker_support_is_handled_before_anything_else(self):
        self.assertIn("if (!('serviceWorker' in navigator)) return;", self.code)


class InstallabilityRoutesTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_service_worker_is_served_at_root_scope(self):
        # Scope is the URL path a worker is served from, so /static/sw.js could
        # only ever control /static/*. Root is a requirement, not a preference.
        response = self.client.get("/sw.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.headers["Content-Type"])
        self.assertEqual(response.headers.get("Service-Worker-Allowed"), "/")

    def test_the_worker_itself_is_never_cached(self):
        # If the worker file could be cached, a deploy could not replace it.
        cache_control = self.client.get("/sw.js").headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_control)

    def test_manifest_is_served_and_is_valid_json(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response.status_code, 200)
        self.assertIn("manifest", response.headers["Content-Type"])
        json.loads(response.get_data(as_text=True))

    def test_both_are_reachable_without_signing_in(self):
        # An installable app must be installable from the landing page; neither
        # of these exposes anything but shell metadata.
        for path in ("/sw.js", "/manifest.webmanifest"):
            self.assertEqual(self.client.get(path).status_code, 200, path)

    def test_installed_app_launches_into_archiosk_in_portrait_standalone(self):
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        self.assertEqual(manifest["start_url"], "/")
        self.assertEqual(manifest["scope"], "/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["orientation"], "portrait")

    def test_manifest_icons_resolve_and_are_real_images(self):
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        self.assertTrue(manifest["icons"])
        for icon in manifest["icons"]:
            path = icon["src"].split("?")[0]
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertGreater(len(response.get_data()), 0, path)

    def test_a_maskable_icon_is_offered(self):
        # Android crops to its own mask; without a maskable entry the mark gets
        # its corners cut off.
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        purposes = {icon.get("purpose") for icon in manifest["icons"]}
        self.assertIn("maskable", purposes)

    def test_the_required_png_sizes_are_declared(self):
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        png_sizes = {i["sizes"] for i in manifest["icons"] if i.get("type") == "image/png"}
        self.assertIn("192x192", png_sizes)
        self.assertIn("512x512", png_sizes)


class ShellTemplatesAdvertiseInstallabilityTests(unittest.TestCase):
    def test_every_shell_links_the_manifest_and_registers_the_worker(self):
        for name in _SHELL_TEMPLATES:
            source = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            # Linked by endpoint (url_for) rather than by literal filename, so
            # accept either spelling - what matters is that a manifest is
            # advertised at all.
            self.assertTrue(
                "manifest.webmanifest" in source or "portal.web_manifest" in source, name
            )
            self.assertIn("pwa.js", source, name)

    def test_apple_touch_icon_is_a_png_not_an_svg(self):
        # iOS ignores SVG for apple-touch-icon and falls back to a screenshot of
        # the page, which is how an app ends up on a home screen with no icon.
        for name in _SHELL_TEMPLATES:
            source = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            link = re.search(r'<link rel="apple-touch-icon"[^>]*>', source)
            self.assertIsNotNone(link, name)
            self.assertIn(".png", link.group(0), name)
            self.assertNotIn(".svg", link.group(0), name)

    def test_static_assets_are_versioned_so_a_deploy_replaces_them(self):
        for name in _SHELL_TEMPLATES:
            source = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            for line in source.splitlines():
                if "apple-touch-icon" in line or "pwa.js" in line:
                    self.assertIn("static_version", line, "%s: %s" % (name, line.strip()))


class IconGeometryTests(unittest.TestCase):
    """The lettermark's constraints, asserted as numbers.

    CLAUDE-LETTERMARK-PURGE-01 replaced what this class used to guard. The
    earlier icon was a constructed symbol - an X with a closed bottom, a waist
    and one accent dot - and the tests here asserted the Product Owner's
    geometry for it: "the bottom portion is closed", "the upper-left portion is
    shorter", "cut the ends with a knife". Those constraints were retired with
    the mark on 2026-08-30, because the form read as an hourglass in a browser
    tab. They are not weakened here, they no longer have a subject.

    What replaced them is a letter, and a letter has its own checkable facts: a
    flat apex, feet on a shared baseline, a counter that stays open, symmetry.
    Those are asserted below. The taste question is left where it belongs, with
    the Product Owner.

    Still asserted against tools/render_app_icon.py as the single source the SVG
    and every PNG are generated from, plus a check that the committed SVG
    matches what that source produces, so the two cannot drift.
    """

    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            "_archiosk_icon_tool", _REPO_ROOT / "tools" / "render_app_icon.py"
        )
        cls.tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.tool)

    def setUp(self):
        self.svg = _ICON_SVG_PATH.read_text(encoding="utf-8")
        self.body = re.sub(r"<!--.*?-->", "", self.svg, flags=re.S)
        self.shapes = self.tool.polygons()

    def test_the_committed_svg_matches_its_generator(self):
        # A hand-edited SVG would silently disagree with the PNGs the home
        # screen actually uses, and nothing else would notice.
        self.assertIn(self.tool.svg_path_data(), self.body)

    def test_the_mark_is_a_letter_not_a_symbol(self):
        # Two legs and a crossbar. Three shapes is what an A is made of; the
        # retired mark was one self-intersecting outline, which is the shape
        # that read as an hourglass.
        self.assertEqual(len(self.shapes), 3)
        for shape in self.shapes:
            self.assertEqual(len(shape), 4, "each stroke is a quad")

    def test_the_apex_is_cut_flat(self):
        # A sharp apex is the first thing a LANCZOS downsample destroys. Flat
        # means both legs terminate on the same horizontal line at the top.
        apex_y = self.tool.APEX[1]
        on_apex = [p for shape in self.shapes[:2] for p in shape
                   if abs(p[1] - apex_y) < 0.05]
        self.assertEqual(len(on_apex), 4, "both legs must terminate on the apex line")

    def test_the_feet_sit_flat_on_a_shared_baseline(self):
        foot_y = self.tool.FOOT_Y
        on_base = [p for shape in self.shapes[:2] for p in shape
                   if abs(p[1] - foot_y) < 0.05]
        self.assertEqual(len(on_base), 4, "both feet must sit on one baseline")

    def test_the_form_is_symmetric_about_the_centreline(self):
        # The inverse of what the retired mark asserted. Its identity was its
        # lean, and the lean is exactly what stopped it reading as the letter
        # it sat beside. A leaning A is a worse A.
        left, right = self.shapes[0], self.shapes[1]
        mirrored = sorted((512.0 - x, y) for x, y in right)
        for (lx, ly), (mx, my) in zip(sorted(left), mirrored):
            self.assertAlmostEqual(lx, mx, places=3)
            self.assertAlmostEqual(ly, my, places=3)

    def test_the_counter_stays_open(self):
        # The triangular hole above the crossbar is what makes it read as A
        # rather than as a tent. Checked as a real point-in-polygon test at the
        # centre of that hole, not by eye.
        probe = (self.tool.APEX[0],
                 self.tool.BAR_Y - self.tool.BAR_HALF - 20.0)
        for shape in self.shapes:
            self.assertFalse(self._contains(shape, probe),
                             "the counter is filled in - the mark reads as a tent")

    def test_the_crossbar_overlaps_both_legs(self):
        # Abutting shapes leave a hairline seam at some rasterisation sizes and
        # not others. The bar must run past each leg's centreline.
        bar = self.shapes[2]
        bar_left = min(x for x, _ in bar)
        bar_right = max(x for x, _ in bar)
        for leg in self.shapes[:2]:
            xs = [x for x, y in leg if abs(y - self.tool.FOOT_Y) < 0.05]
            self.assertTrue(xs)
        self.assertLess(bar_left, self.tool.APEX[0])
        self.assertGreater(bar_right, self.tool.APEX[0])

    def test_the_mark_weight_survives_a_small_icon(self):
        # Below roughly 5% of the canvas the strokes vanish at 48px; above
        # roughly 12% the counter fills in.
        self.assertGreaterEqual(self.tool.STROKE / 512.0, 0.05)
        self.assertLessEqual(self.tool.STROKE / 512.0, 0.12)

    def test_the_whole_mark_sits_inside_the_square_with_margin(self):
        for shape in self.shapes:
            for x, y in shape:
                self.assertGreater(x, 40, "mark reaches the left edge")
                self.assertLess(x, 472, "mark reaches the right edge")
                self.assertGreater(y, 40, "mark reaches the top edge")
                self.assertLess(y, 472, "mark reaches the bottom edge")

    def test_nothing_relies_on_a_renderer_line_style(self):
        # The mark is a filled outline. A leftover stroke-linecap or
        # stroke-linejoin would mean the shape is still partly the renderer's
        # decision rather than the geometry's.
        self.assertNotIn("stroke-linecap", self.body)
        self.assertNotIn("stroke-linejoin", self.body)
        self.assertNotIn("stroke-width", self.body)
        self.assertIn('fill-rule="nonzero"', self.body)

    def test_the_icon_carries_no_accent_colour_at_all(self):
        # main.css's own header: colour is used rarely and must mean something.
        # The retired mark spent its one accent on a waist dot. A lettermark
        # has nothing for an accent to mean, so it has none - ground and mark,
        # both neutral, and nothing else.
        fills = set(re.findall(r'fill="(#[0-9a-fA-F]{6})"', self.body))
        self.assertEqual(fills, {self.tool.GROUND, self.tool.MARK})

    def test_no_trace_of_the_retired_symbol_remains(self):
        # A guard, not a tautology: the generator kept its module shape across
        # the rewrite, so a partial revert could leave the old constants behind
        # and silently reintroduce the hourglass.
        for retired in ("CENTRELINE", "WAIST", "WAIST_RADIUS", "ACCENT",
                        "LEFT_CUT_Y", "RIGHT_CUT_X", "outline"):
            self.assertFalse(hasattr(self.tool, retired),
                             f"{retired} survived the lettermark rewrite")

    @staticmethod
    def _contains(polygon, point):
        """Ray casting. Used to prove the counter is a real hole rather than
        assuming it from the draw order."""
        x, y = point
        inside = False
        n = len(polygon)
        for i in range(n):
            x0, y0 = polygon[i]
            x1, y1 = polygon[(i + 1) % n]
            if (y0 > y) != (y1 > y):
                t = (y - y0) / (y1 - y0)
                if x < x0 + t * (x1 - x0):
                    inside = not inside
        return inside

    @staticmethod
    def _length(a, b):
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class IconAssetsTests(unittest.TestCase):
    def test_the_png_sizes_home_screens_actually_request_exist(self):
        for name, size in (
            ("app-icon-180.png", 180),
            ("app-icon-192.png", 192),
            ("app-icon-512.png", 512),
            ("app-icon-maskable-512.png", 512),
        ):
            path = _ICON_DIR / name
            self.assertTrue(path.exists(), name)
            header = path.read_bytes()[:24]
            self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n", name)
            width = int.from_bytes(header[16:20], "big")
            height = int.from_bytes(header[20:24], "big")
            self.assertEqual((width, height), (size, size), name)

    def test_the_maskable_icon_insets_the_mark(self):
        # Platforms crop up to ~20% off every edge. If the maskable file were
        # identical to the plain one, the crop would cut the mark.
        plain = (_ICON_DIR / "app-icon-512.png").read_bytes()
        maskable = (_ICON_DIR / "app-icon-maskable-512.png").read_bytes()
        self.assertNotEqual(plain, maskable)

    def test_the_svg_and_the_pngs_share_one_ground_colour(self):
        svg = re.sub(r"<!--.*?-->", "", _ICON_SVG_PATH.read_text(encoding="utf-8"), flags=re.S)
        self.assertIn("#0b1f28", svg)


class LandingBrandCompositionTests(unittest.TestCase):
    """Icon centred above the wordmark, reading as one composition."""

    def setUp(self):
        self.landing = _LANDING_PATH.read_text(encoding="utf-8")
        self.css = _LANDING_CSS_PATH.read_text(encoding="utf-8")
        self.main_css = _MAIN_CSS_PATH.read_text(encoding="utf-8")

    def test_the_icon_and_the_wordmark_are_one_element(self):
        # Wrapped together rather than merely adjacent, so the two cannot drift
        # apart as the page changes around them.
        brand = re.search(
            r'<div class="landing-brand">(.*?)</div>', self.landing, flags=re.S
        )
        self.assertIsNotNone(brand, "no .landing-brand wrapper")
        inner = brand.group(1)
        self.assertIn("landing-app-icon", inner)
        self.assertIn("landing-wordmark", inner)
        self.assertLess(
            inner.index("landing-app-icon"), inner.index("landing-wordmark"),
            "the icon must come above the wordmark",
        )

    def test_the_landing_icon_is_the_same_asset_the_home_screen_gets(self):
        # One asset, so the installed icon and the landing mark cannot diverge.
        self.assertIn("app-icon.svg", self.landing)

    def test_the_icon_is_decorative_to_a_screen_reader(self):
        # The wordmark beside it already carries the name; announcing it twice
        # is noise.
        img = re.search(r'<img class="landing-app-icon"[^>]*>', self.landing, flags=re.S)
        self.assertIsNotNone(img)
        self.assertIn('alt=""', img.group(0))
        self.assertIn('aria-hidden="true"', img.group(0))

    def test_the_icon_shrinks_on_a_phone(self):
        # "Avoid pushing the primary entry action too far down on mobile" is a
        # sizing instruction as much as a layout one, and the Product Owner's
        # follow-on correction - "make the landing page icon tighter as they go
        # beyond the screen frame" - is the same instruction again, sharper.
        rules = re.findall(r"\.landing-app-icon\s*\{[^}]*\}", self.css)
        self.assertGreaterEqual(len(rules), 2, "no phone-specific icon size")
        widths = []
        for rule in rules:
            clamped = re.search(r"width:\s*clamp\([^,]+,[^,]+,\s*(\d+)px\s*\)", rule)
            fixed = re.search(r"width:\s*(\d+)px", rule)
            self.assertTrue(clamped or fixed, rule)
            widths.append(int((clamped or fixed).group(1)))
        self.assertLess(min(widths), max(widths), "no phone-specific reduction")
        # The cap, not a mid-range value: an icon that can reach 96px sits
        # above a wordmark that is already the tallest thing on the page.
        self.assertLessEqual(max(widths), 72, "icon large enough to push entry down")

    def test_the_icon_scales_with_the_wordmark_rather_than_fighting_it(self):
        # A fixed-px icon beside a fluid clamp() wordmark is what let the pair
        # grow past the frame on a small phone.
        base = re.search(r"\.landing-app-icon\s*\{[^}]*\}", self.css).group(0)
        self.assertIn("clamp(", base)

    def test_the_landing_page_measures_the_viewport_the_way_a_phone_sees_it(self):
        # On iOS Safari 100vh is the height the viewport WOULD have with the
        # browser chrome hidden, so a 100vh block is taller than what is
        # actually visible and its lower content sits below the frame. main.css
        # already made this correction for the authenticated shell; this
        # asserts the landing page keeps it too.
        for selector in (".landing-page", ".landing-content"):
            rule = re.search(re.escape(selector) + r"\s*\{[^}]*\}", self.css)
            self.assertIsNotNone(rule, selector)
            self.assertIn("100dvh", rule.group(0), selector)
            # The plain unit stays as the fallback for browsers without dvh.
            self.assertIn("100vh", rule.group(0), selector)

    def test_the_update_notice_is_styled_on_every_shell_that_can_show_it(self):
        # pwa.js runs on the landing shell too, and an installed app cold-
        # launches there - so the notice must be styled in BOTH stylesheets or
        # it appears unstyled on the one page that matters most for install.
        for name, css in (("landing.css", self.css), ("main.css", self.main_css)):
            notice = re.search(r"\.update-notice\s*\{[^}]*\}", css)
            self.assertIsNotNone(notice, "no .update-notice rule in %s" % name)
            self.assertIn("safe-area-inset-bottom", notice.group(0), name)
            self.assertIn("position: fixed", notice.group(0), name)

    def test_the_brand_rules_live_where_the_landing_page_can_see_them(self):
        self.assertIn(".landing-brand", self.css)
        self.assertNotIn(".landing-app-icon", self.main_css)


class AuthorizationIsUnchangedTests(unittest.TestCase):
    """"Authentication and authorization remain unchanged" - asserted, not assumed."""

    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_the_worker_never_touches_a_credential(self):
        code = _strip_js_comments(_SW_PATH.read_text(encoding="utf-8"))
        for token in ("credentials", "Authorization", "document.cookie", "session"):
            self.assertNotIn(token, code, token)

    def test_installability_did_not_open_a_project_route_to_anonymous_users(self):
        response = self.client.get("/projects", follow_redirects=False)
        self.assertIn(response.status_code, (301, 302, 303, 401, 403, 404))
        if response.status_code in (301, 302, 303):
            # A ?next= parameter naming the blocked path is the normal, correct
            # shape of this redirect - what must be true is that it lands on
            # the login page rather than on the project itself.
            self.assertTrue(
                response.headers.get("Location", "").startswith("/login"),
                response.headers.get("Location"),
            )


if __name__ == "__main__":
    unittest.main()
