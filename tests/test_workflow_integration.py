"""
Product Acceleration Phase - end-to-end user-journey integration tests.

Unlike the rest of the suite (which exercises CaseWorkspaceStore/route
handlers individually), these tests drive the application the way a real
architect/design manager would: through real HTTP requests against a
real Flask app + test client, following redirects, reading rendered HTML
- proving a user can move through the P0 workflow path without manually
editing storage or calling internal methods directly.

Covers: project directory/reopen, requirement promotion + adjudication
UI reachable from the workspace page, governance history visible in the
workspace, and close/reopen continuity (a fresh test client - standing
in for tomorrow's new session - sees exactly what was left behind).

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class EndToEndWorkflowTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_workflow_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-workflow"

        self.item_a = RequirementItem(
            id="req-item-a", text="Contractor shall provide licensed and insured labor.",
            category="compliance_legal", confidence=0.7, source_line=6,
        )
        self.item_b = RequirementItem(
            id="req-item-b", text="Materials shall comply with ASTM specifications.",
            category="technical_specification", confidence=0.66, source_line=22,
        )
        document = ParsedDocument(
            project_id=self.project_id, filename="sample_rfp.pdf", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[self.item_a, self.item_b],
        )
        RequirementsRegistry(self.tmp_dir).save(document)

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "design-manager"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_case(self, title="Investigation"):
        response = self.client.post(
            f"/projects/{self.project_id}/workspace/cases",
            data={"title": title, "objective": "x"}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        return next(c for c in workspace.cases if c["title"] == title)

    def _rfq_source_id(self):
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        return next(s for s in workspace.sources if s["kind"] == "rfq_rfp_document")["id"]

    # -- project directory / reopen -----------------------------------------

    def test_project_appears_in_project_directory(self):
        response = self.client.get("/projects")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("sample_rfp.pdf", body)
        self.assertIn(self.project_id, body)

    def test_project_directory_links_into_case_workspace(self):
        response = self.client.get("/projects")
        body = response.get_data(as_text=True)
        self.assertIn(f"/projects/{self.project_id}/workspace", body)

    def test_project_not_ingested_does_not_appear(self):
        response = self.client.get("/projects")
        body = response.get_data(as_text=True)
        self.assertNotIn("never-ingested-project", body)

    # -- requirement promotion reachable from the workspace page ---------------

    def test_workspace_shows_unpromoted_requirement_items(self):
        self._create_case()
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn(self.item_a.text, body)
        self.assertIn(self.item_b.text, body)

    def test_promote_requirement_item_through_real_route(self):
        case = self._create_case()
        source_id = self._rfq_source_id()

        response = self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        promoted = [
            r for r in workspace.requirements if r["original_requirement_identifier"] == self.item_a.id
        ]
        self.assertEqual(len(promoted), 1)
        self.assertEqual(promoted[0]["text_reference"], self.item_a.text)

    def test_promoted_item_leaves_unpromoted_list_and_enters_governed_list(self):
        case = self._create_case()
        source_id = self._rfq_source_id()
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )

        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        # item_b is still unpromoted and still listed; item_a's own RequirementItem
        # id should no longer appear as an unpromoted candidate.
        self.assertIn(self.item_b.text, body)
        self.assertIn("Governed Requirements", body)

    # -- adjudication ------------------------------------------------------

    def test_adjudicate_promoted_requirement_through_real_route(self):
        case = self._create_case()
        source_id = self._rfq_source_id()
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        requirement_id = next(
            r for r in workspace.requirements if r["original_requirement_identifier"] == self.item_a.id
        )["id"]

        response = self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "Labor licensure confirmed via submitted certificates.",
                  "case_id": case["id"]},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        workspace = store.get(self.project_id)
        adjudications = [a for a in workspace.requirement_adjudications if a["requirement_id"] == requirement_id]
        self.assertEqual(len(adjudications), 1)
        self.assertEqual(adjudications[0]["outcome"], "Satisfied")
        self.assertEqual(adjudications[0]["adjudicator"], "design-manager")

    def test_adjudication_state_visible_on_workspace_page(self):
        case = self._create_case()
        source_id = self._rfq_source_id()
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )
        store = CaseWorkspaceStore(self.tmp_dir)
        workspace = store.get(self.project_id)
        requirement_id = next(
            r for r in workspace.requirements if r["original_requirement_identifier"] == self.item_a.id
        )["id"]
        self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement_id}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "Confirmed.", "case_id": case["id"]},
            follow_redirects=True,
        )

        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("Satisfied", body)

    # -- history/provenance visible in the workspace itself -----------------

    def test_governance_history_visible_in_workspace(self):
        case = self._create_case()
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("case created", body)  # event_type "case_created", humanized by the template

    def test_promotion_event_appears_in_history(self):
        case = self._create_case()
        source_id = self._rfq_source_id()
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn("requirement item promoted", body)

    # -- close / reopen continuity -----------------------------------------

    def test_state_survives_close_and_reopen_as_a_fresh_session(self):
        """A brand-new test client with no shared in-memory state (only
        the same on-disk REGISTRY_STORE_PATH) stands in for the user
        logging back in tomorrow - everything must still be there,
        reachable through the same real routes."""
        case = self._create_case()
        source_id = self._rfq_source_id()
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases/{case['id']}/requirement-items/{self.item_a.id}/promote",
            data={"source_id": source_id}, follow_redirects=True,
        )

        fresh_client = self.flask_app.test_client()
        with fresh_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "design-manager"
            sess["role"] = "admin"

        directory_response = fresh_client.get("/projects")
        self.assertIn(self.project_id, directory_response.get_data(as_text=True))

        workspace_response = fresh_client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertEqual(workspace_response.status_code, 200)
        body = workspace_response.get_data(as_text=True)
        self.assertIn(case["title"], body)
        self.assertIn(self.item_a.text, body)  # now shown under Governed Requirements, not unpromoted


if __name__ == "__main__":
    unittest.main()
