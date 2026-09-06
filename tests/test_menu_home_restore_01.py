"""
Archiosk > Home shows the landing page, and the icon is the constructed mark.

CLAUDE-MENU-HOME-RESTORE-01 / CLAUDE-MARK-RESTORE-01, 2026-09-06.

BOTH OF THESE CORRECT A SUBSTITUTE THAT HAD BECOME APPARENT AUTHORITY.

Home. 329f5cd pointed the menu item at /projects and wrote "Product Owner,
explicit" into the template comment, with four tests updated to pin it and one
renamed from test_it_still_routes_to_the_landing_page. Commit messages here are
Claude-authored, so that paraphrase was the only evidence for the authority it
claimed. The Product Owner has since stated it was never the intent. 329f5cd's
DIAGNOSIS was right - "/" splits on auth and cannot serve a signed-in user the
landing page - which is why the fix is a new route rather than reverting to
portal.index.

Icon. 9d16b8c replaced the constructed mark with a letter A. Its evidence was
real but size-specific (bowtie at 16px, hourglass in a tab); the verdict was
applied at every size. It also reinstated a form 98086b6 records the Product
Owner rejecting by name - "stop presenting the generic yellow-square 'A' as
ARCHIOSK's primary mark" - without surfacing that.

WHAT IS DELIBERATELY UNCHANGED

Half one of the purge STANDS: chrome is wordmark-only on sign-in, gateway and
the app menu. The mark returns only where an icon is genuinely required. These
tests assert that separation in both directions, because restoring a symbol is
exactly the moment someone re-adds it beside a small label.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ICON_SVG = _REPO_ROOT / "static" / "app-icon.svg"
_TEMPLATES = _REPO_ROOT / "templates"


class HomeDestinationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_homerestore_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def _client(self, signed_in=True):
        client = self.flask_app.test_client()
        if signed_in:
            client.post("/login", data={"username": "admin", "password": "x"},
                        follow_redirects=True)
        return client

    def test_a_signed_in_user_reaches_the_landing_page(self):
        """The whole point: signed in, Home shows the landing page."""
        response = self._client().get("/home")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("landing-wordmark", body)
        self.assertIn("landing-app-icon", body)

    def test_the_menu_item_points_there(self):
        body = self._client().get("/projects").get_data(as_text=True)
        tag = re.search(r'<a[^>]*data-ui-ref="menu\.archiosk\.home"[^>]*>', body)
        self.assertIsNotNone(tag, "the Home item did not render")
        self.assertIn('href="/home"', tag.group(0))
        self.assertNotIn('href="/projects"', tag.group(0))

    def test_signed_out_slash_is_unchanged(self):
        """329f5cd was right that "/" must keep its two behaviours."""
        response = self._client(signed_in=False).get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("landing-wordmark", response.get_data(as_text=True))

    def test_signed_in_slash_still_goes_to_the_directory(self):
        """Only the menu item moved. "/" is untouched, so nothing that depends
        on its post-sign-in behaviour changes."""
        response = self._client().get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/projects", response.headers["Location"])

    def test_the_projects_directory_is_still_reachable(self):
        """Home moving must not cost the directory its entry point."""
        body = self._client().get("/projects").get_data(as_text=True)
        tag = re.search(r'<a[^>]*data-ui-ref="menu\.file\.all-projects"[^>]*>', body)
        self.assertIsNotNone(tag, "All Projects disappeared")
        self.assertIn('href="/projects"', tag.group(0))

    def test_home_does_not_redirect_at_all(self):
        """A loop here would be invisible in a 200-only assertion."""
        response = self._client().get("/home", follow_redirects=False)
        self.assertEqual(response.status_code, 200)

    def test_the_stale_substitute_comment_is_gone(self):
        """The comment told future readers not to restore this. It must not
        outlive the decision it defended."""
        markup = (_TEMPLATES / "_app_menu.html").read_text(encoding="utf-8")
        self.assertNotIn("Do not \"restore\" portal.index", markup)
        self.assertIn("CLAUDE-MENU-HOME-RESTORE-01", markup)


class RestoredMarkTests(unittest.TestCase):
    def test_the_icon_is_the_constructed_mark_not_a_letterform(self):
        svg = _ICON_SVG.read_text(encoding="utf-8")
        self.assertIn("<circle", svg, "the accent dot is part of this mark")
        # The letterform had a crossbar quad and no accent; the constructed
        # mark is one path plus the dot.
        self.assertEqual(svg.count("<path"), 1)

    def test_the_svg_still_matches_its_generator(self):
        """The drift guard that predates both decisions and survives them."""
        import subprocess
        import sys

        before = _ICON_SVG.read_bytes()
        subprocess.run([sys.executable, str(_REPO_ROOT / "tools" / "render_app_icon.py")],
                       cwd=str(_REPO_ROOT), capture_output=True, check=True)
        self.assertEqual(_ICON_SVG.read_bytes(), before,
                         "committed SVG disagrees with tools/render_app_icon.py")

    def test_ui_chrome_stays_wordmark_only(self):
        """Half one of the purge STANDS. Restoring the mark is not permission
        to put it back beside a 16px chrome label - that is the one place its
        recorded failure was real."""
        for name in ("auth_shell.html", "gateway_shell.html", "_app_menu.html"):
            markup = (_TEMPLATES / name).read_text(encoding="utf-8")
            self.assertNotIn("archiosk_mark", markup, "%s re-added the symbol" % name)
            self.assertNotIn("<svg", markup, "%s has an inline mark" % name)

    def test_the_landing_hero_shows_the_icon_above_the_wordmark(self):
        markup = (_TEMPLATES / "landing.html").read_text(encoding="utf-8")
        icon = markup.index("landing-app-icon")
        wordmark = markup.index("landing-wordmark")
        self.assertLess(icon, wordmark, "the icon must sit above the wordmark")
        css = (_REPO_ROOT / "static" / "css" / "landing.css").read_text(encoding="utf-8")
        brand = css[css.index(".landing-brand"):css.index(".landing-brand") + 220]
        self.assertIn("column", brand)


if __name__ == "__main__":
    unittest.main()
