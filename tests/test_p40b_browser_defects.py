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
from services.project_briefing import generate_project_briefing
from services.requirements_registry import RequirementsRegistry

_SUCCESSFUL_BRIEFING_OUTPUT = (
    '{"executive_summary": "Test summary.", "objectives": [], "project_brief": "", '
    '"procurement_route": "", "matters_requiring_attention": []}'
)


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response

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


class BriefingTimeoutScalingTests(unittest.TestCase):
    """3.2 - the exact 30s boundary was confirmed to be an application
    timeout (services/project_briefing.py, sourced from .env's
    ANTHROPIC_TIMEOUT_SECONDS), not HTTP/provider/job-state. A larger
    document's prompt needs proportionally more generation time."""

    def test_short_prompt_stays_at_the_base_timeout(self):
        from services.project_briefing import _scale_timeout_for_prompt_size

        short_prompt = "x" * 500
        self.assertEqual(_scale_timeout_for_prompt_size(30.0, short_prompt), 30.0)

    def test_long_prompt_scales_up_but_stays_capped(self):
        from services.project_briefing import _MAX_TIMEOUT_SECONDS, _scale_timeout_for_prompt_size

        long_prompt = "x" * 50000
        scaled = _scale_timeout_for_prompt_size(30.0, long_prompt)
        self.assertGreater(scaled, 30.0)
        self.assertLessEqual(scaled, _MAX_TIMEOUT_SECONDS)

    def test_scaled_timeout_never_drops_below_the_operator_configured_floor(self):
        from services.project_briefing import _scale_timeout_for_prompt_size

        self.assertGreaterEqual(_scale_timeout_for_prompt_size(30.0, ""), 30.0)

    def test_real_call_uses_a_timeout_scaled_from_the_actual_prompt(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_TIMEOUT_SECONDS": "30"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_BRIEFING_OUTPUT)
            large_items = [
                {"text": f"The Design-Builder shall comply with technical requirement {i} in full.", "category": "technical_specification"}
                for i in range(30)
            ] * 4  # well past a single small-document prompt
            generate_project_briefing(
                document_filename="large.txt", candidate_requirements=large_items,
                governed_requirements=[], milestones=[], api_key="fake-key-for-test",
            )
            call_kwargs = MockClient.call_args.kwargs
        self.assertGreater(call_kwargs["timeout"], 30.0)


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
        # CLAUDE-P40-E3A, Section 5: the bare workspace URL is blank by
        # default now - this Overview-scoped content needs the explicit
        # ?view=overview leaf.
        return self.client.get(f"/projects/{self.project_id}/workspace?view=overview").get_data(as_text=True)

    # -- 3.3: View-all controls actually resolve --------------------------

    def test_requirements_and_key_dates_accordions_have_real_html_ids(self):
        # CLAUDE-POSTCAMEL-ROOT-I1: Requirements relocated to its own
        # page (view=requirements) - this fixture has no governed
        # Requirement yet (only extracted candidates), so
        # id="governed-requirements" (rendered only when
        # requirements_view is non-empty) isn't expected here; the page
        # itself and its stable data-ui-ref are what this test confirms.
        body = self._page()
        self.assertIn('id="temporal-obligations"', body)
        requirements_response = self.client.get(f"/projects/{self.project_id}/workspace?view=requirements")
        self.assertEqual(requirements_response.status_code, 200)
        self.assertIn('data-ui-ref="display.requirements"', requirements_response.get_data(as_text=True))
        # CLAUDE-P40-E1A: the conversation dock's own html_id is now the
        # single shared "conversation-dock" (was "project-conversation")
        # - see macros.conversation_dock.
        self.assertIn('id="conversation-dock"', body)

    def test_view_all_technical_link_uses_a_truthful_count_label(self):
        # CLAUDE-POSTCAMEL-ROOT-I1: this now links cross-page to
        # Requirements' own stable Display surface, not a same-page hash.
        body = self._page()
        self.assertIn("View all 8 technical submission items", body)
        self.assertIn('view=requirements#governed-requirements', body)
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


class ProjectRenameUniquenessTests(unittest.TestCase):
    """3.1 - a real gap found during this stage's own investigation:
    renaming a Project via Edit Project Details never checked
    uniqueness, even though upload-time naming does."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40b_rename_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_a = "test-project-a"
        self.project_b = "test-project-b"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        registry = RequirementsRegistry(self.tmp_dir)
        registry.save(ParsedDocument(project_id=self.project_a, filename="a.txt", ingested_at="2026-01-01T00:00:00+00:00"))
        registry.save(ParsedDocument(project_id=self.project_b, filename="b.txt", ingested_at="2026-01-01T00:00:00+00:00"))

        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "owner1"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_a}/workspace")
        self.client.get(f"/projects/{self.project_b}/workspace")
        self.store.set_project_owner(self.store.get(self.project_a), owner="owner1", actor="owner1")
        self.store.set_project_owner(self.store.get(self.project_b), owner="owner1", actor="owner1")

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_renaming_to_an_existing_projects_name_is_rejected(self):
        self.store.set_project_details(self.store.get(self.project_b), actor="owner1", display_title="Riverside Renovation")

        resp = self.client.post(
            f"/projects/{self.project_a}/workspace/details",
            data={"display_title": "Riverside Renovation"}, follow_redirects=True,
        )
        self.assertIn("Entry names must be unique.", resp.get_data(as_text=True))
        self.assertIsNone(self.store.get(self.project_a).display_title)

    def test_renaming_to_an_existing_projects_filename_is_rejected(self):
        # project_b never got a custom display_title - its effective
        # name is still its raw filename ("b.txt").
        resp = self.client.post(
            f"/projects/{self.project_a}/workspace/details",
            data={"display_title": "b.txt"}, follow_redirects=True,
        )
        self.assertIn("Entry names must be unique.", resp.get_data(as_text=True))

    def test_renaming_to_a_genuinely_new_unique_name_succeeds(self):
        resp = self.client.post(
            f"/projects/{self.project_a}/workspace/details",
            data={"display_title": "A Genuinely New Name"}, follow_redirects=True,
        )
        self.assertIn("Project details updated.", resp.get_data(as_text=True))
        self.assertEqual(self.store.get(self.project_a).display_title, "A Genuinely New Name")

    def test_renaming_a_project_to_its_own_current_name_is_allowed(self):
        self.store.set_project_details(self.store.get(self.project_a), actor="owner1", display_title="My Project")
        resp = self.client.post(
            f"/projects/{self.project_a}/workspace/details",
            data={"display_title": "My Project"}, follow_redirects=True,
        )
        self.assertIn("Project details updated.", resp.get_data(as_text=True))


def _mock_qa_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ProjectQAContinuityTests(unittest.TestCase):
    """3.5, 3.6 - Q&A destination, Ask-vs-Start-Work boundary, and
    document-identity answer precision, exercised through the real
    route stack."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_p40b_qa_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-p40b-qa"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="RFP-2026-PROD-099_Project_Dossier.docx", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text="Master Request for Proposals Package, Project Dossier-Sync, RFP No. RFP-2026-PROD-099.", category="other", confidence=0.6, source_line=1),
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

    # -- 3.5: destination --------------------------------------------------

    def test_discuss_object_redirects_to_the_project_conversation_fragment(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Test answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What is the name of the RFP?"},
            )
        self.assertEqual(resp.status_code, 302)
        # CLAUDE-CA1C-UX-FIX-01: the "#conversation-dock" fragment this
        # redirect used to carry was removed - it was a stale relic of a
        # pre-P40-E2B <details>-based dock (the anchor-open script it
        # relied on only matches `details.accordion-section`, and the dock
        # has been a plain, always-visible <div> since P40-E2B), and its
        # only live effect was a native browser scroll-into-view that
        # raced the JS's own deliberate scroll-to-newest-message logic on
        # a `scroll-behavior: smooth` container - the live-reported "starts
        # too high, stops short of the newest exchange" bug. Scrolling to
        # the newest message is now owned solely by client-side JS.
        self.assertFalse(resp.headers["Location"].endswith("#conversation-dock"))

    # -- 3.5: a plain question does not silently create a Case -------------

    def test_quick_start_with_a_plain_question_does_not_create_a_case(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Test answer.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/quick-start",
                data={"text": "What is the name of this document?"},
            )
        self.assertEqual(resp.status_code, 302)
        # CLAUDE-CA1C-UX-FIX-01: see the matching assertion's own comment above.
        self.assertFalse(resp.headers["Location"].endswith("#conversation-dock"))
        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.cases, [])
        self.assertEqual(len(workspace.project_conversation), 2)  # human + system

    def test_quick_start_with_a_real_work_request_still_creates_a_case(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/quick-start",
            data={"text": "Investigate the schedule conflict between Section 4 and Section 9."},
        )
        self.assertEqual(resp.status_code, 302)
        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.cases), 1)

    # -- 3.6: grounded_in is separate from the answer, not flattened in ----

    def test_grounded_in_is_stored_separately_and_rendered_as_a_disclosure(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "This is Master Request for Proposals Package, Project Dossier-Sync (RFP No. RFP-2026-PROD-099).", '
                '"grounded_in": ["Master Request for Proposals Package, Project Dossier-Sync, RFP No. RFP-2026-PROD-099."], '
                '"not_covered": "", "needs_clarification": false}'
            )
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What is the name of this document?"},
            )
        workspace = self.store.get(self.project_id)
        system_reply = workspace.project_conversation[-1]
        self.assertEqual(system_reply["role"], "system")
        self.assertNotIn("Grounded in:", system_reply["text"])
        self.assertEqual(
            system_reply["grounded_in"],
            ["Master Request for Proposals Package, Project Dossier-Sync, RFP No. RFP-2026-PROD-099."],
        )

        body = self.client.get(f"/projects/{self.project_id}/workspace").get_data(as_text=True)
        self.assertIn("Source grounding", body)
        self.assertIn("RFP No. RFP-2026-PROD-099", body)

    def test_display_title_is_passed_into_the_qa_prompt_when_set(self):
        self.store.set_project_details(
            self.store.get(self.project_id), actor="owner1", display_title="Riverside Library Renovation",
        )
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_qa_response(
                '{"answer": "Riverside Library Renovation.", "grounded_in": [], "not_covered": "", "needs_clarification": false}'
            )
            self.client.post(
                f"/projects/{self.project_id}/workspace/discuss",
                data={"text": "What is the name of the project?"},
            )
            sent_prompt = MockClient.return_value.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Riverside Library Renovation", sent_prompt)
        self.assertIn("display name", sent_prompt)


if __name__ == "__main__":
    unittest.main()
