"""
Visual pressure ("stable geometry, variable emphasis" - see
routes/workspace.py's own comment on the settled/old-news/not-currently-
focused rule): a governed Requirement's TEXT recedes to a quieter token
once it is settled, that settlement predates this reviewer's last visit,
and it isn't something they're personally still engaged with via Recent
Focus. It never changes existence, order, or position - only whether
`row.quiet` (and so the `pressure-quiet-text` CSS class) is set on an
otherwise-identical row.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from services.bhive_parser import ParsedDocument
from services.case_workspace import REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, CaseWorkspaceStore
from services.requirements_registry import RequirementsRegistry


class VisualPressureTests(unittest.TestCase):
    def setUp(self):
        import app as app_module

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_visual_pressure_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-visual-pressure"

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

    def _register_requirement(self):
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")  # registers the auto document Source
        workspace = self.store.get(self.project_id)
        source_id = workspace.sources[0]["id"]
        return self.store.register_requirement(
            workspace,
            source_id=source_id,
            original_requirement_identifier="Section 3.1",
            text_reference="Contractor shall provide as-built drawings.",
            created_by="owner1",
            registration_method=REQUIREMENT_REGISTRATION_HUMAN_REGISTERED,
        )

    def _adjudicate(self, requirement):
        self.client.post(
            f"/projects/{self.project_id}/workspace/requirements/{requirement['id']}/adjudicate",
            data={"outcome": "Satisfied", "reasoning": "As-built set received.", "case_id": ""},
        )

    def test_not_yet_assessed_requirement_never_quiets(self):
        self._register_requirement()
        # First visit establishes the marker; a Requirement that has
        # never been adjudicated stays at full strength no matter how
        # many subsequent visits pass - "settled" is a precondition.
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("pressure-quiet-text", resp.get_data(as_text=True))

    def test_settled_requirement_stays_full_strength_until_a_visit_has_passed(self):
        requirement = self._register_requirement()
        self._adjudicate(requirement)
        # This is the SAME visit the adjudication happened in (no fresh
        # page load establishing a new last-visited marker afterward) -
        # brand new news must never be presented as already-quiet.
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("pressure-quiet-text", resp.get_data(as_text=True))

    def test_settled_requirement_quiets_after_a_later_visit(self):
        requirement = self._register_requirement()
        self._adjudicate(requirement)
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")  # records a visit AFTER the adjudication
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertIn("pressure-quiet-text", resp.get_data(as_text=True))

    def test_requirement_still_renders_in_full_when_quiet(self):
        """Quieting must never remove content - only its text color."""
        requirement = self._register_requirement()
        self._adjudicate(requirement)
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        body = resp.get_data(as_text=True)
        self.assertIn("Contractor shall provide as-built drawings.", body)
        self.assertIn("Satisfied", body)
        self.assertIn(f'id="requirement-{requirement["id"]}"', body)

    def test_settled_requirement_stays_loud_while_this_reviewer_still_discusses_it(self):
        requirement = self._register_requirement()
        self._adjudicate(requirement)
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")  # a visit passes - would otherwise quiet
        self.client.post(
            f"/projects/{self.project_id}/workspace/discuss",
            data={
                "text": "still checking on this one",
                "anchor_type": "requirement",
                "anchor_id": requirement["id"],
                "anchor_description": "Section 3.1",
            },
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("pressure-quiet-text", resp.get_data(as_text=True))

    def test_pressure_is_per_reviewer(self):
        requirement = self._register_requirement()
        self._adjudicate(requirement)
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.client.get(f"/projects/{self.project_id}/workspace?view=overview")

        other_client = self.flask_app.test_client()
        with other_client.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "owner2"
            sess["role"] = "admin"
        # owner2's own first-ever visit - no established "old news"
        # boundary yet, so nothing quiets for them regardless of owner1's
        # visit history.
        resp = other_client.get(f"/projects/{self.project_id}/workspace?view=overview")
        self.assertNotIn("pressure-quiet-text", resp.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
