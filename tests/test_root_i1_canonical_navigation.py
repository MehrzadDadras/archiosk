"""
CLAUDE-POSTCAMEL-ROOT-I1: Phase 1 of the canonical project root (ROOT-A1)
- Requirements promoted to a first-class, stable Display surface
(directory_view == 'requirements', branch 3 of the canonical root), and
a machine-legible data-root-branch/data-root-label numbering scaffold
applied across the existing sidebar (branches 1.1/1.2/2.1/2.2/3/4/6/6.3/8).

This is a RELOCATION of existing, already-governed Requirements markup
(register/promote/adjudicate/revise, all pre-existing, all unchanged by
this stage) out of Overview's own accordion stack - not a
reimplementation. Requirement/RequirementAdjudication themselves are
untouched; only navigation.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.case_workspace import (
    CaseWorkspaceStore,
    REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
)


class RootI1NavigationTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_root_i1_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-root-i1"

        document = ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        RequirementsRegistry(self.tmp_dir).save(document)

        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(self.project_id)
        self.store.set_project_owner(self.workspace, owner="owner1", actor="owner1")
        self.store.add_source(self.workspace, name="rfp.md", file_path="/tmp/rfp.md", kind="owner_project_requirements")

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _register_requirement(self, text="Contractor shall provide as-built drawings."):
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace, source_id=source_id, original_requirement_identifier="Section 3.1",
            text_reference=text, created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    # -- 1/2: canonical branch ordering and numbering -------------------------

    def test_sidebar_carries_the_canonical_root_numbering_scaffold(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        for branch, label in [
            ("1.1", "Identity &amp; Overview"),
            ("1.2", "Project Context"),
            ("2.1", "Documents"),
            ("2.2", "Files"),
            ("3", "Requirements"),
            ("4", "Investigations"),
            ("6", "Work Products"),
            ("6.3", "RFIs"),
            ("8", "Action"),
        ]:
            self.assertIn(f'data-root-branch="{branch}"', body)
            self.assertIn(f'data-root-label="{label}"', body)

    def test_requirements_branch_sits_between_files_and_investigations(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        files_pos = body.index('data-root-branch="2.2"')
        requirements_pos = body.index('data-root-branch="3"')
        investigations_pos = body.index('data-root-branch="4"')
        self.assertLess(files_pos, requirements_pos)
        self.assertLess(requirements_pos, investigations_pos)

    # -- 3: Requirements visibility -------------------------------------------

    def test_requirements_sidebar_link_targets_the_new_view(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn(f'href="/projects/{self.project_id}/workspace?view=requirements"', body)
        self.assertIn('data-ui-ref="lists.project.requirements"', body)

    def test_requirements_page_renders_governed_requirement(self):
        self._register_requirement("Contractor shall provide as-built drawings.")
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn("Contractor shall provide as-built drawings.", body)
        self.assertIn("Governed Requirements (1)", body)

    def test_requirements_page_offers_registration_form(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = response.get_data(as_text=True)
        self.assertIn("Register a Requirement", body)
        self.assertIn(f'/projects/{self.project_id}/workspace/requirements/register"', body)

    def test_requirement_breadcrumb_label(self):
        # directory_view_label (STABLE_DIRECTORY_KINDS["requirements"])
        # drives the top-bar breadcrumb, same mechanism Files already uses.
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        body = response.get_data(as_text=True)
        self.assertIn('<span class="workspace-topbar-doc">Requirements</span>', body)

    # -- 4/5: no duplicated governed records from projection ------------------

    def test_overview_no_longer_lists_the_full_governed_requirement_body(self):
        # Overview keeps a short pointer/summary only - the full governed
        # list (with adjudicate/revise/perspective controls) lives
        # exactly once, on the Requirements page.
        self._register_requirement("Contractor shall provide as-built drawings.")
        overview = self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)
        self.assertNotIn("Contractor shall provide as-built drawings.", overview)
        self.assertIn("1 governed Requirement", overview)
        self.assertIn('data-ui-ref="display.overview.requirements-link"', overview)

    def test_registering_a_requirement_creates_exactly_one_governed_record(self):
        self._register_requirement("Contractor shall provide as-built drawings.")
        workspace = self.store.get(self.project_id)
        matching = [r for r in workspace.requirements if r["text_reference"] == "Contractor shall provide as-built drawings."]
        self.assertEqual(len(matching), 1)

    # -- 8/9: empty-state behaviour and project isolation ----------------------

    def test_requirements_branch_shows_zero_count_quietly_when_empty(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn('data-ui-ref="lists.project.requirements" data-view="requirements"', body)
        # A quiet count, not a stack of "No X / No Y / No Z" phrases in the sidebar itself.
        sidebar_start = body.index('data-root-branch="3"')
        sidebar_row = body[sidebar_start:sidebar_start + 400]
        self.assertIn('<span class="launcher-count">0</span>', sidebar_row)

    def test_requirements_are_isolated_per_project(self):
        from services.bhive_parser import ParsedDocument
        from services.requirements_registry import RequirementsRegistry
        other_project_id = "test-project-root-i1-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        other_workspace = self.store.get_or_create(other_project_id)
        self.store.set_project_owner(other_workspace, owner="owner1", actor="owner1")

        self._register_requirement("Contractor shall provide as-built drawings.")

        other_response = self.client.get(f"/projects/{other_project_id}/workspace?view=requirements")
        self.assertEqual(other_response.status_code, 200)
        self.assertNotIn("Contractor shall provide as-built drawings.", other_response.get_data(as_text=True))

    def test_stranger_without_project_access_cannot_reach_requirements_view(self):
        no_access_client = self.flask_app.test_client()
        with no_access_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "stranger"
            sess["role"] = "read_only"
        response = no_access_client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        self.assertEqual(response.status_code, 404)

    # -- 6/10: existing project opening / cockpit behaviour untouched --------

    def test_existing_project_still_opens_normally(self):
        response = self.client.get(f"/projects/{self.project_id}/workspace")
        self.assertEqual(response.status_code, 200)

    def test_recent_focus_requirement_link_points_at_the_requirements_view(self):
        # CLAUDE-POSTCAMEL-ROOT-I1: fixes a pre-existing gap - this link
        # used to omit view=overview entirely (the only place the
        # #requirement-<id> anchor ever rendered), so it never worked.
        # It now correctly targets view=requirements, where the anchor
        # target actually lives post-relocation.
        requirement = self._register_requirement("Contractor shall provide as-built drawings.")
        workspace = self.store.get(self.project_id)
        self.store.add_message(
            workspace, case_id=None, role="human",
            text="Discuss this Requirement", actor="owner1",
            anchor={"anchor_type": "requirement", "anchor_id": requirement["id"], "source_id": None, "location": None, "description": None},
        )
        response = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = response.get_data(as_text=True)
        self.assertIn(f"view=requirements#requirement-{requirement['id']}", body)


if __name__ == "__main__":
    unittest.main()
