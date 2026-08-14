"""
Home page / navigation shell (first-page redesign).

Lightweight coverage for the project-first entry point and the shared
two-state navigation rail introduced in this tranche. These are template
and route-level checks only -- no domain/store behavior changed, so no
changes to the governance-kernel test suites were needed.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.requirements_registry import RequirementsRegistry


class HomeNavigationShellTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_home_nav_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _login(self, client, role="admin"):
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = role

    def test_anonymous_home_renders_the_public_landing_page(self):
        # SUPERSEDED twice over:
        # CLAUDE-P40-VW5: an anonymous "/" visit used to render this same
        # index.html template's own minimal identity-line-plus-link
        # branch - "a fresh unauthenticated visit... must begin at
        # Sign-in" changed that to a redirect straight to /login.
        # CLAUDE-CA1D-PUBLIC-LANDING-01: superseded again by explicit,
        # later Product Owner decision - "/" is now a real public front
        # door (templates/landing.html), not an immediate redirect to a
        # bare credentials form. 200, not 302; Sign In is one of the
        # landing page's own actions, still leading to the same /login.
        client = self.flask_app.test_client()
        response = client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("landing-page", body)
        self.assertIn("Sign In", body)
        self.assertNotIn("New Project", body)
        self.assertNotIn("Open Project", body)

    def test_authenticated_home_shows_project_entry_actions(self):
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("New Project", body)
        self.assertIn("Open Project", body)

    def test_home_no_longer_duplicates_the_project_selector(self):
        # 5-minute tree-prototype pass: the sidebar's Projects tree is now
        # the one canonical project selector - Home's own separate
        # "Recent Projects" card list (and its governed-count computation)
        # is gone, not just visually hidden. That counting logic is still
        # covered where it's still rendered - the Projects directory
        # page - see tests/test_projects_directory_redesign.py.
        project_id = "home-nav-test-project"
        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00",
        ))

        client = self.flask_app.test_client()
        self._login(client)
        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertNotIn("entry-recent", body)
        # Checked as the rendered label pattern, not a bare substring,
        # since this app's own explanatory comments legitimately mention
        # the old "Recent Projects" block by name.
        self.assertNotIn('side-rail-context-label">Recent Projects<', body)
        self.assertNotIn('class="workspace-pane-label">Recent Projects<', body)
        # SUPERSEDED (CLAUDE-P40-E3A, Section 2): the product owner
        # reversed P40-E2B1A's pure-root-launcher rule - the ONE panel is
        # a recursive hierarchy now, and DOES legitimately list every
        # authorized Project (including on Home) as a Lists leaf. What
        # this test still protects - no SECOND, duplicate listing
        # alongside it - is checked as an exact-once count instead of an
        # absence.
        self.assertEqual(body.count("rfp.md"), 1)
        # On /projects itself, "rfp.md" legitimately appears twice now:
        # once in Lists (present on every page, Section 2) and once in
        # the actual /projects directory listing this page renders.
        directory_body = client.get("/projects").get_data(as_text=True)
        self.assertEqual(directory_body.count("rfp.md"), 2)

    def test_nav_rail_present_with_toggle(self):
        # CLAUDE-P40-E2B1: the old two-state (icon-only/labeled) side-rail
        # and its own hamburger toggle are retired - the one launcher
        # panel now hides/shows in full via the panel-dividing line
        # (CLAUDE-P40-E3A, Section 7 - #lists-divider, replacing the
        # even-older top-bar toggle button), a reviewer-wide, not
        # per-project, localStorage preference.
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn('id="lists-divider"', body)
        self.assertIn('id="launcher-panel"', body)
        self.assertIn("beehive:panel:launcher", body)
        self.assertNotIn('id="nav-toggle"', body)

    def test_nav_rail_only_links_to_real_destinations(self):
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn(">Projects<", body)
        self.assertIn("+ New Project", body)
        # No global nav links were fabricated for destinations that only
        # exist nested inside a specific project's Case Workspace.
        self.assertNotIn(">Sources<", body)
        self.assertNotIn(">Cases<", body)
        self.assertNotIn(">Investigations<", body)
        self.assertNotIn(">Requirements<", body)
        self.assertNotIn(">RFIs<", body)

    def test_nav_rail_shows_current_project_context_inside_workspace(self):
        project_id = "home-nav-context-project"
        document = ParsedDocument(project_id=project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        client = self.flask_app.test_client()
        self._login(client)
        response = client.get(f"/projects/{project_id}/workspace")
        body = response.get_data(as_text=True)

        # SUPERSEDED (CLAUDE-P40-E3A): current-Project context now shows
        # in the application-wide top bar's breadcrumb
        # (workspace-topbar-project) AND, since Section 2's reversal, as
        # the active Project's own highlighted Lists leaf/branch (no
        # longer a root-launcher-only panel with no per-project
        # highlighting) - there is no literal "Current Project" label
        # anywhere, but the project's own identity is genuinely present
        # throughout.
        # SUPERSEDED AGAIN (CLAUDE-P40-VW7B, Section 3): "launcher-
        # heading" (the "Projects" root) no longer rendered at all while
        # a Project was open - the Foreground Project's own branch
        # (current-project marker + aria-current="true") communicated
        # current-Project context instead.
        # SUPERSEDED AGAIN (CLAUDE-LEFT-RAIL-01): "launcher-heading" is
        # unconditional again - PROJECTS is now the one, always-present
        # live active-project switcher. Both signals coexist now: the
        # PROJECTS toggle itself, and the Foreground Project's own
        # current-project marker + aria-current="true".
        # CLAUDE-GO-DNA-01 (Panel Zoning): the retired "Overview" leaf's
        # own data-root-branch/data-root-label now carry over onto this
        # self-link - see test_global_search_and_header.py's identical
        # note.
        self.assertIn("rfp.md", body)
        self.assertIn(project_id, body)
        self.assertIn("launcher-heading", body)
        self.assertIn('tree-leaf launcher-link current-project" data-ui-ref="lists.project.self" data-root-branch="1.1" data-root-label="Identity &amp; Overview" aria-current="true"', body)

    def test_non_admin_does_not_see_new_project_link(self):
        # BUCKET-B FIX (CLAUDE-P40-E3A): base.html's own recursive-tree
        # "New Project" leaf was rendering unconditionally - a real
        # authorization gap, since portal.upload is @admin_required
        # (routes/portal.py) - a read_only reviewer clicking it would
        # have hit a 403. Now gated behind is_admin, matching Section 4's
        # "unauthorized... branches must never render". "Open Project"
        # (index.html's own dashboard hero CTA, role-independent, out of
        # this stage's shell-only scope) is unaffected and still present.
        client = self.flask_app.test_client()
        self._login(client, role="read_only")

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertNotIn(">New Project<", body)
        self.assertIn(">Open Project<", body)


if __name__ == "__main__":
    unittest.main()
