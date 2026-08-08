"""
Requirement revision (Addendum handling) route wiring.

CaseWorkspaceStore.revise_requirement was fully built and tested at the
store layer - its own docstring names its primary purpose explicitly
("An Addendum amending/qualifying/superseding an earlier requirement is
exactly this call") - but had no route at all. This covers the first
wiring: workspace.revise_requirement_route, the requirements_view filter
that stops showing a superseded predecessor as if it were still current,
and the "Revision history" disclosure in case_workspace.html.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import CaseWorkspaceStore, REQUIREMENT_STATUS_ACTIVE, REQUIREMENT_STATUS_SUPERSEDED
from services.requirements_registry import RequirementsRegistry


class RequirementRevisionWiringTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_requirement_revision_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-requirement-revision"

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.store = CaseWorkspaceStore(self.tmp_dir)
        source = self.store.add_source(
            self.store.get(self.project_id), name="RFP.md", file_path="/tmp/rfp.md",
            kind="owner_project_requirements",
        )
        self.requirement = self.store.register_requirement(
            self.store.get(self.project_id), source_id=source["id"],
            original_requirement_identifier="3.1", text_reference="Original wording",
            created_by="owner1", registration_method="human_registered",
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _revise(self, **overrides):
        data = {"text_reference": "Revised wording", "reason": "Addendum 2"}
        data.update(overrides)
        return self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{self.requirement['id']}/revise",
            data=data,
        )

    def test_revision_creates_a_new_active_requirement_and_supersedes_the_old(self):
        self._revise()
        requirements = self.store.requirements_for_project(self.store.get(self.project_id))
        self.assertEqual(len(requirements), 2)
        old = next(r for r in requirements if r["id"] == self.requirement["id"])
        new = next(r for r in requirements if r["id"] != self.requirement["id"])
        self.assertEqual(old["status"], REQUIREMENT_STATUS_SUPERSEDED)
        self.assertEqual(new["status"], REQUIREMENT_STATUS_ACTIVE)
        self.assertEqual(new["text_reference"], "Revised wording")
        # unrevised fields carry forward unchanged from the predecessor
        self.assertEqual(new["original_requirement_identifier"], "3.1")

    def test_superseded_requirement_no_longer_shown_as_a_separate_current_entry(self):
        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements moved from Overview to
        # its own stable Display surface - same markup, real URL.
        self._revise()
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = resp.get_data(as_text=True)
        self.assertIn("Revised wording", body)
        # "Original wording" legitimately still appears once, inside the
        # Revision history disclosure (see the next test) - the point of
        # this test is that it's not ALSO shown as its own top-level,
        # still-current Governed Requirement entry.
        self.assertIn("Governed Requirements (1)", body)
        self.assertEqual(body.count("Original wording"), 1)

    def test_revision_history_shows_the_prior_text_and_reason(self):
        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements moved to its own page.
        self._revise()
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = resp.get_data(as_text=True)
        self.assertIn("Revision history (1)", body)
        # only visible once the disclosure is opened, but the content is
        # still in the static HTML (native <details>, no JS-only reveal)
        self.assertIn("Original wording", body.split("Revision history (1)")[1][:800])
        self.assertIn("Addendum 2", body)

    def test_missing_reason_is_rejected(self):
        self._revise(reason="")
        requirements = self.store.requirements_for_project(self.store.get(self.project_id))
        self.assertEqual(len(requirements), 1)  # nothing created


if __name__ == "__main__":
    unittest.main()
