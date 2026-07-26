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

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import ANALYSIS_TRIGGER_USER_INITIATED, AnalysisTrigger, CaseWorkspaceStore
from services.governance import GovernanceLog
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
        self.assertIn("No projects yet.", body)

    def test_authenticated_home_lists_recent_project_with_governed_counts(self):
        project_id = "home-nav-test-project"
        document = ParsedDocument(
            project_id=project_id,
            filename="rfp.md",
            ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="r1", text="x", category="other", confidence=0.5, source_line=1)
            ],
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        # Promote the candidate into a governed Requirement -- the home
        # page's "requirements" count reflects governed state, not raw
        # extraction candidates, so this is required for a non-zero count.
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get_or_create(project_id)
        source = store.add_source(
            workspace, name="rfp.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )
        case = store.create_case(workspace, title="Review", objective="Promote extracted items")
        store.promote_requirement_item(
            workspace,
            case_id=case["id"],
            source_id=source["id"],
            requirement_item={"id": "r1", "text": "x", "category": "other", "confidence": 0.5, "source_line": 1},
            actor="tester",
            trigger=AnalysisTrigger(trigger_type=ANALYSIS_TRIGGER_USER_INITIATED, triggered_by_actor="tester"),
            governance_log=GovernanceLog(self.tmp_dir),
        )

        client = self.flask_app.test_client()
        self._login(client)
        response = client.get("/")
        body = response.get_data(as_text=True)

        self.assertIn("rfp.md", body)
        self.assertIn("1 requirement(s)", body)
        self.assertNotIn("0 requirement(s)", body)

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
