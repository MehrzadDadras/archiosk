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

    def test_anonymous_home_shows_project_question_and_sign_in_only(self):
        client = self.flask_app.test_client()
        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("What project are we working on?", body)
        self.assertIn("Sign in to get started", body)
        self.assertNotIn("New Project", body)
        self.assertNotIn("Open Project", body)

    def test_authenticated_home_shows_project_entry_actions(self):
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("What project are we working on?", body)
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
        # The project still appears exactly once - as an object node in
        # the sidebar's Projects tree, not a second time in page content.
        self.assertEqual(body.count("rfp.md"), 1)

    def test_nav_rail_present_with_collapsed_default_and_toggle(self):
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn('id="nav-toggle"', body)
        self.assertIn("side-rail", body)
        self.assertIn("beehive:nav:expanded", body)
        self.assertIn("nav-expanded", body)

    def test_nav_rail_only_links_to_real_destinations(self):
        client = self.flask_app.test_client()
        self._login(client)

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn(">Home<", body)
        self.assertIn(">Projects<", body)
        self.assertIn(">New Project<", body)
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

        self.assertIn("Current Project", body)
        self.assertIn(project_id, body)

    def test_non_admin_does_not_see_new_project_link(self):
        client = self.flask_app.test_client()
        self._login(client, role="read_only")

        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertNotIn(">New Project<", body)
        self.assertIn(">Open Project<", body)


if __name__ == "__main__":
    unittest.main()
