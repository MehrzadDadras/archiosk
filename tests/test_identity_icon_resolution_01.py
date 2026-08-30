"""
CLAUDE-IDENTITY-ICON-RESOLVE-01 - every identity icon the application declares
(or that a browser asks for without being told to) actually resolves, carries
its own geometry inside its own viewBox, and reserves its own space.

WHY THIS FILE EXISTS SEPARATELY FROM test_mobile_pwa_icon_01.py

That file asserts the app icon's GEOMETRY against its generator - the Product
Owner's "bottom is closed / upper-left is shorter / knife cuts" constraints as
numbers. It does not ask whether the URLs those assets live at answer, and that
turned out to be the gap: `/favicon.ico` was a 404, and `static/favicon.svg`
was still committed carrying the 6-unit bottleneck gap that
CLAUDE-BOTTLENECK-ADOPTION-01 had explicitly rejected as reading like a plain
letter X, while its own header comment claimed to be "same path data as
templates/_macros.html's archiosk_mark". A correct mark nobody serves and a
rejected mark nobody deleted are both invisible to a geometry test.

So the assertions here are about RESOLUTION and CONTAINMENT, not about taste:

  - does the URL answer, and answer unauthenticated;
  - is the drawn geometry actually inside the viewBox that frames it;
  - does every in-page identity image state its own width and height, so it
    reserves space before it loads rather than shoving the layout when it does;
  - is there exactly ONE mark family, with no second file quietly holding an
    older one.

No browser automation is exercised and no visual acceptance is claimed. Layout
shift is asserted structurally - as "the element declares intrinsic dimensions"
- which is the property that actually prevents it, not a measured CLS score.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_STATIC = _REPO_ROOT / "static"
_TEMPLATES = _REPO_ROOT / "templates"
_ICON_SVG_PATH = _STATIC / "app-icon.svg"
_ICON_ICO_PATH = _STATIC / "icons" / "app-icon.ico"
_MACROS_PATH = _TEMPLATES / "_macros.html"

# The four page shells, plus the standalone help pages, are every template that
# declares a rel="icon" of its own.
_SHELL_TEMPLATES = ("landing_shell.html", "auth_shell.html", "gateway_shell.html", "base.html")


def _strip_html_comments(source: str) -> str:
    """Drop {# jinja #} and <!-- html --> comments.

    Same discipline as test_mobile_pwa_icon_01.py's own comment stripper: the
    templates here carry long explanatory comments that name the very filenames
    these tests assert are absent, so a raw-source scan would let prose satisfy
    a negative assertion.
    """
    source = re.sub(r"<!--.*?-->", "", source, flags=re.S)
    return re.sub(r"\{#.*?#\}", "", source, flags=re.S)


def _numbers(text: str) -> list[float]:
    return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", text)]


class RootFaviconResolvesTests(unittest.TestCase):
    """The request a browser makes on its own initiative."""

    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def test_favicon_ico_answers_at_the_site_root(self):
        # This was a 404 before this stage. A browser asks for /favicon.ico
        # whatever <link rel="icon"> says - for non-HTML responses, for
        # bookmarks and pinned tiles, and from clients that do not take SVG.
        response = self.client.get("/favicon.ico")
        self.assertEqual(response.status_code, 200)

    def test_it_is_served_as_an_icon_not_as_html(self):
        response = self.client.get("/favicon.ico")
        self.assertIn("icon", response.headers["Content-Type"])
        self.assertEqual(response.get_data()[:4], b"\x00\x00\x01\x00", "not an ICO header")

    def test_it_is_reachable_without_signing_in(self):
        # The client has no session here. An identity asset behind auth means a
        # sign-in page with no tab icon, which is the state a browser caches.
        self.assertEqual(self.client.get("/favicon.ico").status_code, 200)

    def test_it_is_cacheable_but_not_forever(self):
        # The browser invents this request, so nothing can append ?v= to it and
        # STATIC_VERSION cannot flush it. Expiry is the only control there is.
        cache_control = self.client.get("/favicon.ico").headers.get("Cache-Control", "")
        self.assertIn("max-age=", cache_control)
        self.assertNotIn("immutable", cache_control)


class DeclaredIconUrlsResolveTests(unittest.TestCase):
    """Every icon URL a real rendered page declares, fetched for real."""

    def setUp(self):
        import app as app_module
        self.flask_app = app_module.create_app("testing")
        self.client = self.flask_app.test_client()

    def _icon_hrefs(self, path: str) -> list[str]:
        html = self.client.get(path).get_data(as_text=True)
        hrefs = re.findall(r'<link[^>]*rel="[^"]*icon[^"]*"[^>]*href="([^"]+)"', html)
        self.assertTrue(hrefs, f"no rel=icon declared on {path}")
        return hrefs

    def test_landing_shell_icons_resolve(self):
        # The public front door - the first page a stranger's browser meets.
        for href in self._icon_hrefs("/"):
            self.assertEqual(self.client.get(href).status_code, 200, href)

    def test_auth_shell_icons_resolve(self):
        for href in self._icon_hrefs("/login"):
            self.assertEqual(self.client.get(href).status_code, 200, href)

    def test_every_manifest_icon_resolves(self):
        manifest = json.loads(self.client.get("/manifest.webmanifest").get_data(as_text=True))
        self.assertTrue(manifest["icons"])
        for icon in manifest["icons"]:
            self.assertEqual(self.client.get(icon["src"]).status_code, 200, icon["src"])

    def test_every_service_worker_precache_entry_resolves(self):
        # A precache miss is swallowed on purpose (an install must not fail on
        # one), so a broken entry here is silent at runtime by design.
        worker = self.client.get("/sw.js").get_data(as_text=True)
        entries = re.findall(r'"(/static/[^"]+)"\s*\+\s*VERSION', worker)
        self.assertTrue(entries)
        for entry in entries:
            self.assertEqual(self.client.get(entry).status_code, 200, entry)


class OneMarkFamilyTests(unittest.TestCase):
    """No second file quietly holding an older mark."""

    def test_the_superseded_favicon_svg_is_gone(self):
        # It carried the pre-widening 6-unit bottleneck gap - the reading
        # CLAUDE-BOTTLENECK-ADOPTION-01 rejected - long after every shell had
        # been repointed at app-icon.svg, and nothing referenced it.
        self.assertFalse((_STATIC / "favicon.svg").exists())

    def test_no_template_references_it(self):
        for path in _TEMPLATES.rglob("*.html"):
            body = _strip_html_comments(path.read_text(encoding="utf-8"))
            self.assertNotIn("favicon.svg", body, path)

    def test_the_committed_ico_matches_its_generator(self):
        # Same guarantee test_mobile_pwa_icon_01.py gives the SVG and the PNGs:
        # a hand-placed binary nobody can regenerate is how the tab icon and
        # the home-screen icon drift apart without anything noticing.
        spec = importlib.util.spec_from_file_location(
            "_archiosk_icon_tool_ico", _REPO_ROOT / "tools" / "render_app_icon.py"
        )
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)

        import io

        frames = [tool.render(size) for size in sorted(tool.ICO_SIZES, reverse=True)]
        buffer = io.BytesIO()
        frames[0].save(
            buffer,
            format="ICO",
            sizes=[(size, size) for size in tool.ICO_SIZES],
            append_images=frames[1:],
        )
        self.assertEqual(_ICON_ICO_PATH.read_bytes(), buffer.getvalue())

    def test_the_ico_carries_every_size_it_claims(self):
        # Pillow's ICO writer DROPS any requested size larger than the base
        # image without erroring - a one-frame .ico reported as a success.
        from PIL import Image

        with Image.open(_ICON_ICO_PATH) as image:
            self.assertEqual(sorted(image.ico.sizes()), [(16, 16), (32, 32), (48, 48), (64, 64)])


class ViewBoxContainmentTests(unittest.TestCase):
    """Nothing drawn falls outside the box that frames it."""

    def test_the_app_icon_geometry_sits_inside_its_viewbox(self):
        svg = re.sub(r"<!--.*?-->", "", _ICON_SVG_PATH.read_text(encoding="utf-8"), flags=re.S)
        viewbox = _numbers(re.search(r'viewBox="([^"]+)"', svg).group(1))
        self.assertEqual(viewbox, [0.0, 0.0, 512.0, 512.0])

        # CLAUDE-LETTERMARK-PURGE-01: one path, now carrying three subpaths
        # (two legs and a crossbar), and no <circle> - the retired mark's
        # accent dot went with it. Every coordinate in the path is checked
        # rather than a sampled subset.
        coords = _numbers(re.search(r'<path[^>]*\sd="([^"]+)"', svg).group(1))
        xs, ys = coords[0::2], coords[1::2]
        self.assertTrue(xs, "no path geometry found in the app icon")
        self.assertNotIn("<circle", svg, "the accent dot was retired with the old mark")

        self.assertGreaterEqual(min(xs), viewbox[0])
        self.assertGreaterEqual(min(ys), viewbox[1])
        self.assertLessEqual(max(xs), viewbox[2])
        self.assertLessEqual(max(ys), viewbox[3])

    # CLAUDE-LETTERMARK-PURGE-01: test_the_chrome_mark_stroke_sits_inside_its_
    # viewbox was removed here, not weakened. It checked that the inline
    # archiosk_mark's STROKE stayed inside its own 64-unit viewBox; that macro
    # was retired on 2026-08-30 and there is no longer a stroked chrome mark
    # anywhere in the product for it to measure. The app-icon check above is
    # the only viewBox containment that still has a subject.


class NoLayoutShiftTests(unittest.TestCase):
    """Identity images reserve their space before they load."""

    def _identity_images(self):
        for path in _TEMPLATES.rglob("*.html"):
            body = _strip_html_comments(path.read_text(encoding="utf-8"))
            for tag in re.findall(r"<img\b[^>]*>", body, flags=re.S):
                if "app-icon" in tag:
                    yield path, tag

    def test_every_identity_image_declares_width_and_height(self):
        # Without both, the browser lays the page out with a zero-height box
        # and reflows everything below the mark the moment the asset arrives.
        found = list(self._identity_images())
        self.assertTrue(found, "no identity <img> found - the scan is wrong")
        for path, tag in found:
            self.assertRegex(tag, r'\swidth="[^"]+"', f"{path}: {tag}")
            self.assertRegex(tag, r'\sheight="[^"]+"', f"{path}: {tag}")

    def test_every_identity_image_is_square(self):
        # The asset is a square tile. A non-square reservation would reserve
        # the wrong box and shift anyway, which is the defect, not the fix.
        for path, tag in self._identity_images():
            width = re.search(r'\swidth="([^"]+)"', tag).group(1)
            height = re.search(r'\sheight="([^"]+)"', tag).group(1)
            self.assertEqual(width, height, f"{path}: {tag}")

    # CLAUDE-LETTERMARK-PURGE-01: test_the_shared_chrome_mark_declares_its_own_
    # size was removed here. It asserted the inline archiosk_mark macro
    # rendered width/height from its own `size` argument so the menu bar
    # reserved space before paint. The macro is retired; the two <img> tests
    # above still cover every identity image that remains, which is the whole
    # of the layout-shift risk now.


class ShellDeclarationsAreConsistentTests(unittest.TestCase):
    """All four shells name the same mark, not three of four."""

    def test_every_shell_points_rel_icon_at_the_canonical_asset(self):
        for name in _SHELL_TEMPLATES:
            body = _strip_html_comments((_TEMPLATES / name).read_text(encoding="utf-8"))
            icons = re.findall(r'<link[^>]*rel="icon"[^>]*>', body)
            self.assertEqual(len(icons), 1, f"{name}: expected exactly one rel=icon")
            self.assertIn("app-icon.svg", icons[0], name)

    def test_every_shell_declares_an_apple_touch_icon(self):
        # iOS ignores SVG here and falls back to a screenshot of the page.
        for name in _SHELL_TEMPLATES:
            body = _strip_html_comments((_TEMPLATES / name).read_text(encoding="utf-8"))
            self.assertIn("apple-touch-icon", body, name)
            self.assertIn("icons/app-icon-180.png", body, name)


if __name__ == "__main__":
    unittest.main()
