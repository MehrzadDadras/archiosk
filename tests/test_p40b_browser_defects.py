"""
CLAUDE-P40-B - Product-Owner Browser Defect Closure and First-Use Trust
Repair. Focused tests for each defect confirmed via direct code
inspection/execution against the product owner's real browser
walkthrough (Test 2 / Riverside evidence) - see this stage's own final
report for the full root-cause map.

Stdlib unittest only, matching the existing test convention. Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import BHiveParser, ParsedDocument, RequirementItem
from services.case_workspace import REQUIREMENT_REGISTRATION_HUMAN_REGISTERED, CaseWorkspaceStore, Source
from services.requirements_registry import RequirementsRegistry

_LONG_MILESTONE_TEXT = (
    "Proponents shall submit all required forms as part of the formal Proposal "
    "Submission, including Addendum acknowledgements. An amendment to this "
    "requirement will only be issued in writing by the Sponsor."
)


class MilestoneTruncationTests(unittest.TestCase):
    """3.4 - _derive_milestones previously cut every label at exactly
    120 characters with no ellipsis and no way to see the rest."""

    def test_milestone_label_is_not_truncated(self):
        parser = BHiveParser(anthropic_api_key=None)
        requirements = [
            RequirementItem(id="m1", text=_LONG_MILESTONE_TEXT, category="schedule_milestone", confidence=0.9, source_line=1),
        ]
        milestones = parser._derive_milestones(requirements)
        self.assertEqual(len(milestones), 1)
        self.assertEqual(milestones[0]["label"], _LONG_MILESTONE_TEXT)
        self.assertGreater(len(milestones[0]["label"]), 120)
        # Confirms the exact previously-reported symptom is gone - the
        # text ends on a real word boundary, not a silent mid-word cut.
        self.assertTrue(milestones[0]["label"].endswith("Sponsor."))


class ProjectHomeBrowserDefectTests(unittest.TestCase):
    """3.3, 3.7, 3.8 - exercised through the real route stack."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40b_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-p40b"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id=f"tech-{i}", text=f"The design shall comply with technical requirement {i}.", category="technical_specification", confidence=0.9, source_line=i)
                for i in range(8)
            ],
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store.set_project_owner(self.store.get(self.project_id), owner="owner1", actor="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _page(self):
        return self.client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)

    # -- 3.3: View-all controls actually resolve --------------------------

    def test_requirements_and_key_dates_accordions_have_real_html_ids(self):
        body = self._page()
        self.assertIn('id="requirements"', body)
        self.assertIn('id="temporal-obligations"', body)
        self.assertIn('id="project-conversation"', body)

    def test_view_all_technical_link_uses_a_truthful_count_label(self):
        body = self._page()
        self.assertIn("View all 8 technical submission items", body)
        self.assertIn('href="#requirements"', body)
        self.assertNotIn("Open Technical Submission", body)

    # -- 3.8: header controls ----------------------------------------------

    def test_star_button_has_a_visible_tooltip(self):
        body = self._page()
        self.assertIn('title="Star project"', body)

    def test_starred_project_shows_unstar_tooltip(self):
        self.store.set_starred(self.store.get(self.project_id), True)
        body = self._page()
        self.assertIn('title="Unstar project"', body)

    def test_overflow_menu_has_a_clear_edit_label_not_a_bare_glyph(self):
        body = self._page()
        self.assertIn(">Edit<", body)
        self.assertNotIn("Project administration", body)

    def test_toggle_star_route_still_persists(self):
        # Confirms the underlying control genuinely works end to end -
        # not just relabeled.
        csrf = None
        body = self._page()
        import re
        m = re.search(r'name="csrf_token" value="([^"]+)"', body)
        csrf = m.group(1) if m else None
        self.client.post(f"/projects/{self.project_id}/workspace/star", data={"csrf_token": csrf} if csrf else {})
        self.assertTrue(self.store.get(self.project_id).starred)


class TextOnlyCaseMediumNeutralCopyTests(unittest.TestCase):
    """3.7 - a text-document Case must not be told to analyze a drawing."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40b_medium_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-p40b-medium"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00",
        ))
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")
        self.store.set_project_owner(self.store.get(self.project_id), owner="owner1", actor="owner1")
        self.case = self.store.create_case(self.store.get(self.project_id), title="Text-only Case", objective="", created_by="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _case_page(self):
        return self.client.get(f"/projects/{self.project_id}/workspace?case={self.case['id']}").get_data(as_text=True)

    def test_conversation_empty_state_is_medium_neutral_without_a_drawing(self):
        body = self._case_page()
        self.assertIn("Ask a question or investigate this Source.", body)
        self.assertNotIn("Analyze this drawing for datum inconsistencies.", body)

    def test_composer_placeholder_is_medium_neutral_without_a_drawing(self):
        body = self._case_page()
        self.assertIn("Ask a question or investigate this Source", body)

    def test_findings_empty_state_is_medium_neutral_without_a_drawing(self):
        body = self._case_page()
        self.assertIn("No Findings yet. Investigate a Source to generate or record Findings.", body)
        self.assertNotIn("Ask the conversation to analyze a drawing Source", body)

    def test_drawing_specific_copy_still_appears_when_a_drawing_source_is_actually_attached(self):
        workspace = self.store.get(self.project_id)
        source = Source(id="src-drawing-1", project_id=self.project_id, kind="drawing", name="A101.png", added_at="2026-01-01T00:00:00+00:00")
        workspace.sources.append(asdict(source))
        for case in workspace.cases:
            if case["id"] == self.case["id"]:
                case["source_ids"].append(source.id)
        self.store.save(workspace)

        body = self._case_page()
        self.assertIn("Analyze this drawing for datum inconsistencies", body)
        self.assertIn("No Findings yet. Ask the conversation to analyze a drawing Source to generate some.", body)


if __name__ == "__main__":
    unittest.main()
