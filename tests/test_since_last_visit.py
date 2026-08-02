"""
"What has just changed?" - a per-reviewer last-visited marker on Project
Home, so a returning reviewer isn't left to reconstruct what's new by
re-reading the whole History log themselves.

Deliberately a single count + timestamp, not per-item "new" tags
scattered across every accordion - see routes/workspace.py's own
comment on why this stays a small, honest signal rather than a larger
UI change made as a side effect.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class SinceLastVisitTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_since_last_visit_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-since-last-visit"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_first_ever_visit_shows_no_since_last_visit_note(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertNotIn("since your last visit", body)
        # but the marker is now recorded for next time
        workspace = self.store.get(self.project_id)
        self.assertIn("owner1", workspace.last_viewed_by)

    def test_second_visit_reports_events_since_the_first(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")  # records the first-visit marker
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "New Investigation", "objective": "x"},
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("1 update since your last visit", body)

    def test_no_new_events_reports_nothing_new(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Nothing new since your last visit", body)

    def test_marker_is_per_reviewer_not_shared(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "New Investigation", "objective": "x"},
        )
        other_client = self.flask_app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "owner2"
            sess["role"] = "admin"
        # owner2 has never visited - no note at all, not "N since never"
        resp = other_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("since your last visit", resp.get_data(as_text=True))

    def test_not_shown_inside_an_open_case(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.client.post(
            f"/projects/{self.project_id}/workspace/cases", data={"title": "Case A", "objective": "x"},
        )
        case = self.store.get(self.project_id).cases[0]
        resp = self.client.get(f"/projects/{self.project_id}/workspace?case={case['id']}")
        self.assertNotIn("since your last visit", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
