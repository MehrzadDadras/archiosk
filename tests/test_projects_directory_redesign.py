"""
Projects directory redesign (card presentation, search, sort, human-
readable dates).

Lightweight template/route coverage only -- no domain, persistence, or
governance behavior changed in this tranche. See
tests/test_home_navigation_shell.py for the first-page/nav-shell tranche
this one continues.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ConsistencyFlag, ParsedDocument
from services.requirements_registry import RequirementsRegistry


class ProjectsDirectoryRedesignTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_projects_redesign_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)

        registry = RequirementsRegistry(self.tmp_dir)
        flag = ConsistencyFlag(
            id="flag-1", requirement_a_id="a", requirement_a_text="x",
            requirement_b_id="b", requirement_b_text="y", explanation="conflict",
        )
        registry.save(ParsedDocument(
            project_id="proj-alpha", filename="Alpha_RFP.pdf",
            ingested_at="2026-02-03T14:05:00+00:00",
            consistency_flags=[flag], consistency_checked=True,
        ))
        registry.save(ParsedDocument(
            project_id="proj-beta", filename="Beta_Spec.docx",
            ingested_at="2026-05-01T09:00:00+00:00",
        ))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "tester"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _card_list(self, body):
        match = re.search(r'<ul class="project-card-list">.*?</ul>', body, re.S)
        return match.group(0) if match else ""

    def test_projects_render_as_cards_not_a_table(self):
        response = self.client.get("/projects")
        body = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("project-card-list", body)
        self.assertNotIn("registry-table", body)
        self.assertIn("Alpha_RFP.pdf", body)
        self.assertIn("Beta_Spec.docx", body)

    def test_ingest_document_action_removed_from_directory_heading(self):
        response = self.client.get("/projects")
        body = response.get_data(as_text=True)

        self.assertNotIn("Ingest a new document", body)
        self.assertIn(">New Project<", body)

    def test_dates_rendered_human_readable_not_raw_iso(self):
        response = self.client.get("/projects")
        body = self._card_list(response.get_data(as_text=True))

        self.assertIn("Feb 3, 2026", body)
        self.assertIn("May 1, 2026", body)
        self.assertNotIn("2026-02-03T14:05:00", body)
        self.assertNotIn("2026-05-01T09:00:00", body)

    def test_unresolved_conflict_flag_shown_for_flagged_project(self):
        response = self.client.get("/projects")
        body = self._card_list(response.get_data(as_text=True))

        self.assertIn("entry-flag-red", body)
        self.assertIn("1 unresolved", body)

    def test_search_filters_to_matching_project_only(self):
        response = self.client.get("/projects?q=beta")
        card_list = self._card_list(response.get_data(as_text=True))

        self.assertIn("Beta_Spec.docx", card_list)
        self.assertNotIn("Alpha_RFP.pdf", card_list)

    def test_search_with_no_matches_shows_empty_state_not_ingestion_prompt(self):
        response = self.client.get("/projects?q=nonexistent-project-name")
        body = response.get_data(as_text=True)

        self.assertIn("No projects match", body)
        self.assertNotIn("project-card-list", body)

    def test_sort_by_name_orders_alphabetically(self):
        response = self.client.get("/projects?sort=name")
        card_list = self._card_list(response.get_data(as_text=True))

        self.assertLess(card_list.find("Alpha_RFP.pdf"), card_list.find("Beta_Spec.docx"))

    def test_sort_by_created_orders_newest_first(self):
        response = self.client.get("/projects?sort=created")
        card_list = self._card_list(response.get_data(as_text=True))

        self.assertLess(card_list.find("Beta_Spec.docx"), card_list.find("Alpha_RFP.pdf"))

    def test_default_sort_is_last_updated_newest_first(self):
        response = self.client.get("/projects")
        card_list = self._card_list(response.get_data(as_text=True))

        self.assertLess(card_list.find("Beta_Spec.docx"), card_list.find("Alpha_RFP.pdf"))

    def test_project_id_present_but_secondary_to_name(self):
        response = self.client.get("/projects")
        body = self._card_list(response.get_data(as_text=True))

        self.assertIn('class="project-card-id', body)
        self.assertIn("proj-alpha", body)

    def test_open_project_is_the_primary_card_action(self):
        response = self.client.get("/projects")
        body = self._card_list(response.get_data(as_text=True))

        self.assertIn("/projects/proj-alpha/workspace", body)
        # The legacy Dashboard is retired (redirects into Case Workspace -
        # see routes/portal.py's dashboard()), so Case Workspace is the
        # only card action now, not a de-emphasized second one beside it.
        self.assertNotIn("project-card-secondary", body)

    def test_empty_state_with_no_projects_offers_new_project_not_ingestion(self):
        empty_dir = Path(tempfile.mkdtemp(prefix="beehive_test_projects_empty_"))
        try:
            self.flask_app.config["REGISTRY_STORE_PATH"] = str(empty_dir)
            response = self.client.get("/projects")
            body = response.get_data(as_text=True)

            self.assertIn("No projects yet.", body)
            self.assertIn("Create New Project", body)
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_projects_tree_node_present_in_nav_rail(self):
        # 5-minute tree-prototype pass: there is no more standalone
        # "Projects" page-link to highlight as .active - it's a category
        # node (expand/collapse only) in the sidebar's Projects tree.
        response = self.client.get("/projects")
        body = response.get_data(as_text=True)

        self.assertIn("side-rail-tree-summary", body)
        self.assertIn('id="nav-toggle"', body)


if __name__ == "__main__":
    unittest.main()
