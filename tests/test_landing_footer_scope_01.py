"""
The public landing page carries no marketing feature-list footer.

CLAUDE-LANDING-FOOTER-SCOPE-01, 2026-09-06. Product Owner direction, with an
independent marketing review concurring: the three-column block introduced
internal terminology, project-specific information and compliance assertions
before a visitor had any reason to parse them.

THE PRIVACY FINDING, WHICH IS THE PART WITH TEETH

One footer line read "Pilot: 1860 Alstep Dr (by invitation)" - a real project
street address - and it rendered on the SIGNED-OUT landing page. A live
project's existence and location were public. It also announced that project to
every authenticated user regardless of their access, which is the one thing
services/project_access.py exists to prevent.

templates/auth_shell.html had already reasoned its way to this exact risk for
the sign-in page: "A footer naming 'Pilot: 1860 Alstep Dr' on the sign-in page
is that defect returning through a different door." The risk was recognised for
one public surface and missed on another equally public one. These tests assert
against ALL public surfaces rather than the one that was reported.

WHY THE MINIMAL FOOTER LINKS NEITHER PRIVACY NOR TERMS

Neither page exists. The footer component's founding rule is that every link
points at something real, and adding two dead links in the edit meant to
tighten it would have broken that rule to satisfy a convention.
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from werkzeug.security import generate_password_hash

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATES = _REPO_ROOT / "templates"

# Everything the landing page must no longer say.
_REMOVED = (
    "ARCHIOSK Platform",
    "Practice &amp; Projects",
    "Standards &amp; Security",
    "Vector coordination desk",
    "Split-pane comparison",
    "Proactive grounding officer",
    "Architect of record",
    "Structural &amp; MEP coordination",
    "Alstep",
    "OBC",
    "Project RBAC drawing confidentiality",
    "site-footer-columns",
)


class LandingFooterScopeTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_footerscope_"))
        self.addCleanup(shutil.rmtree, self.tmp_dir, ignore_errors=True)
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.flask_app.config["WTF_CSRF_ENABLED"] = False
        with self.flask_app.app_context():
            db.session.add(User(username="admin",
                                password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

    def _public(self, path):
        return self.flask_app.test_client().get(path).get_data(as_text=True)

    # -- the directed change ----------------------------------------------

    def test_the_landing_page_carries_no_feature_list(self):
        body = self._public("/")
        for term in _REMOVED:
            self.assertNotIn(term, body, "landing page still shows %r" % term)

    def test_home_carries_no_feature_list_either(self):
        """/home renders the same template and is equally public."""
        body = self._public("/home")
        for term in _REMOVED:
            self.assertNotIn(term, body, "/home still shows %r" % term)

    def test_the_minimal_footer_still_carries_legal_and_support(self):
        body = self._public("/")
        self.assertIn("site-footer-legal", body)
        self.assertIn("site-footer-aux", body)
        self.assertIn("footer.support", body)

    def test_it_links_no_page_that_does_not_exist(self):
        """The component's founding rule, applied to the variant that replaced
        the block. Privacy and terms have no routes, so they are absent rather
        than dead."""
        body = self._public("/")
        self.assertNotIn('href="/privacy"', body)
        self.assertNotIn('href="/terms"', body)
        self.assertNotIn('href="/trust"', body)

    # -- what must be preserved -------------------------------------------

    def test_the_landing_hero_and_actions_are_untouched(self):
        body = self._public("/")
        self.assertLess(body.index("landing-app-icon"), body.index("landing-wordmark"))
        for ref in ("landing.explore", "landing.start-trial", "landing.sign-in"):
            self.assertIn(ref, body, "%s disappeared" % ref)

    def test_no_empty_footer_shell_is_left_behind(self):
        """Removing the columns must not leave a bordered empty box."""
        body = self._public("/")
        footer = body[body.index('class="site-footer"'):]
        self.assertNotIn("<nav", footer[:400],
                         "an empty footer nav survived the removal")
        self.assertIn("site-footer-legal", footer)

    # -- the privacy finding, asserted across every public surface --------

    def test_no_real_project_identifier_on_any_public_surface(self):
        """Not just the reported page. The sign-in page had already reasoned
        its way to this risk; the landing page shipped it anyway."""
        for path in ("/", "/home", "/login"):
            body = self._public(path)
            self.assertNotIn("Alstep", body, "%s exposes a real project address" % path)
            self.assertNotIn("1860", body, "%s exposes a real project number" % path)

    def test_the_component_no_longer_contains_the_address_as_markup(self):
        """A Jinja comment explaining the removal is fine; a rendered <li> is
        not. This asserts against the markup, not the prose."""
        source = (_TEMPLATES / "components" / "public_footer.html").read_text(encoding="utf-8")
        without_comments = re.sub(r"\{#.*?#\}", "", source, flags=re.S)
        self.assertNotIn("Alstep", without_comments)
        self.assertNotIn("Proactive grounding officer", without_comments)

    def test_no_bare_compliance_claim_is_published_publicly(self):
        """"OBC / code compliance" as a bare noun phrase is an assertion the
        product cannot stand behind in marketing copy."""
        for path in ("/", "/home"):
            self.assertNotIn("OBC", self._public(path))


class AuthenticatedFooterScopeTests(unittest.TestCase):
    """CLAUDE-AUTH-FOOTER-SCOPE-01: no operational surface carries the block.

    The footer was trailing chrome on all eight - after </article> or
    </section>, never inside guide content - so removing it took no
    instructional material with it. A deliberate link back to Explore remains,
    because the objection was a persistent marketing block, not the route.
    """

    def _consumers(self):
        root = _REPO_ROOT / "templates"
        return sorted(p for p in root.rglob("*.html")
                      if p.name != "public_footer.html"
                      and "public_footer.html" in p.read_text(encoding="utf-8"))

    def test_every_consumer_uses_the_minimal_variant(self):
        found = self._consumers()
        self.assertGreaterEqual(len(found), 8, "consumer scan found too few files")
        for path in found:
            self.assertIn("footer_minimal", path.read_text(encoding="utf-8"),
                          "%s still renders the marketing block" % path.name)

    def test_the_full_branch_has_no_consumer_and_is_kept_anyway(self):
        """Kept because it carries the classified content and the record of
        where each item belongs. Its return must be deliberate, not drift."""
        component = (_REPO_ROOT / "templates" / "components"
                     / "public_footer.html").read_text(encoding="utf-8")
        self.assertIn("site-footer-columns", component)
        self.assertIn("Vector coordination desk", component)

    def test_operational_surfaces_keep_a_route_back_to_explore(self):
        for name in ("projects.html", "help/index.html"):
            markup = (_REPO_ROOT / "templates" / name).read_text(encoding="utf-8")
            self.assertIn("footer_explore", markup)

    def test_the_landing_page_does_not_duplicate_explore(self):
        """Explore is already one of the landing page's three primary actions."""
        markup = (_REPO_ROOT / "templates" / "landing.html").read_text(encoding="utf-8")
        self.assertNotIn("footer_explore", markup)


if __name__ == "__main__":
    unittest.main()
