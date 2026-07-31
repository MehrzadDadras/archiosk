"""
CLAUDE-P38-B -- narrative-first project opening: Executive Summary,
Project Brief, Procurement Route, Matters Requiring Early Attention
(real, grounded, policy-gated Anthropic synthesis, mirroring services/
project_qa.py's own pattern) plus deterministic Technical/Financial/
Key Dates/Reading Path sections that need no AI call at all.

Three layers, matching tests/test_requirement_investigation.py's own
split:
  - ProjectBriefingServiceTests: services/project_briefing.py directly,
    network call mocked.
  - DeterministicSectionsTests: the no-AI-needed grouping logic.
  - ProjectBriefingRouteTests: the real route stack.

Run via:

    python -m unittest discover -s tests -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from services.bhive_parser import ParsedDocument, RequirementItem
from services.case_workspace import CaseWorkspaceStore
from services.project_briefing import deterministic_sections, generate_project_briefing
from services.requirements_registry import RequirementsRegistry


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


_SUCCESSFUL_BRIEFING_OUTPUT = (
    '{"executive_summary": "This RFP seeks a Design-Builder for the Riverside renovation.", '
    '"objectives": ["Complete structural upgrades within 18 months."], '
    '"project_brief": "The project covers structural, mechanical, and accessibility work.", '
    '"procurement_route": "", '
    '"matters_requiring_attention": ["Ventilation requirement does not state a specific air-change rate."]}'
)

_CANDIDATE_ITEMS = [
    {"text": "The Design-Builder shall provide all labor and materials.", "category": "scope_of_work"},
    {"text": "All structural steel shall conform to CSA G40.21 350W.", "category": "technical_specification"},
    {"text": "Proposals shall be submitted in a sealed envelope.", "category": "submission_instruction"},
]
_MILESTONES = [{"id": "m1", "label": "Substantial performance within 18 months.", "status": "pending", "source_line": 10}]


class ProjectBriefingServiceTests(unittest.TestCase):
    def test_no_api_key_returns_an_honest_skip_not_a_fabricated_result(self):
        result = generate_project_briefing(
            document_filename="rfp.txt", candidate_requirements=[], governed_requirements=[],
            milestones=[], api_key="",
        )
        self.assertFalse(result.ran)
        self.assertIsNone(result.executive_summary)
        self.assertIn("ANTHROPIC_API_KEY", result.skipped_reason)

    def test_real_call_parses_the_model_json_output_correctly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_BRIEFING_OUTPUT)
            result = generate_project_briefing(
                document_filename="rfp.txt", candidate_requirements=_CANDIDATE_ITEMS,
                governed_requirements=[], milestones=_MILESTONES, api_key="fake-key-for-test",
            )
        self.assertTrue(result.ran)
        self.assertIn("Riverside renovation", result.executive_summary)
        self.assertEqual(result.objectives, ["Complete structural upgrades within 18 months."])
        self.assertIsNone(result.procurement_route)  # empty string -> None
        self.assertEqual(result.provider, "anthropic")

    def test_no_financial_route_established_is_reported_empty_not_guessed(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_BRIEFING_OUTPUT)
            result = generate_project_briefing(
                document_filename="rfp.txt", candidate_requirements=_CANDIDATE_ITEMS,
                governed_requirements=[], milestones=_MILESTONES, api_key="fake-key-for-test",
            )
        self.assertIsNone(result.procurement_route)

    def test_api_exception_degrades_honestly(self):
        with patch("anthropic.Anthropic") as MockClient:
            MockClient.return_value.messages.create.side_effect = RuntimeError("network exploded")
            result = generate_project_briefing(
                document_filename="rfp.txt", candidate_requirements=[], governed_requirements=[],
                milestones=[], api_key="fake-key-for-test",
            )
        self.assertFalse(result.ran)
        self.assertIn("error occurred", result.skipped_reason.lower())


class DeterministicSectionsTests(unittest.TestCase):
    def test_technical_and_financial_are_kept_separate(self):
        items = _CANDIDATE_ITEMS + [{"text": "The total contract value shall not exceed $2,000,000.", "category": "budget_commercial"}]
        sections = deterministic_sections(items, [])
        self.assertEqual(len(sections["technical_submission_items"]), 2)  # technical_specification + submission_instruction
        self.assertEqual(len(sections["financial_submission_items"]), 1)
        self.assertIn("total contract value", sections["financial_submission_items"][0]["text"])

    def test_no_financial_items_yields_an_empty_list_not_a_fabricated_one(self):
        sections = deterministic_sections(_CANDIDATE_ITEMS, [])
        self.assertEqual(sections["financial_submission_items"], [])

    def test_key_dates_come_from_milestones_verbatim(self):
        sections = deterministic_sections([], _MILESTONES)
        self.assertEqual(sections["key_dates"], _MILESTONES)

    def test_reading_path_excludes_categories_with_no_items(self):
        sections = deterministic_sections(_CANDIDATE_ITEMS, [])
        categories_present = {step["category"] for step in sections["reading_path"]}
        self.assertIn("scope_of_work", categories_present)
        self.assertIn("technical_specification", categories_present)
        self.assertNotIn("budget_commercial", categories_present)
        self.assertNotIn("evaluation_criteria", categories_present)


class ProjectBriefingRouteTests(unittest.TestCase):
    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_project_briefing_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-briefing"

        with self.flask_app.app_context():
            db.session.add(User(username="owner1", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(ParsedDocument(
            project_id=self.project_id, filename="rfp.txt", ingested_at="2026-01-01T00:00:00+00:00",
            requirements=[
                RequirementItem(id="i1", text=_CANDIDATE_ITEMS[0]["text"], category="scope_of_work", confidence=0.9, source_line=1),
                RequirementItem(id="i2", text=_CANDIDATE_ITEMS[1]["text"], category="technical_specification", confidence=0.9, source_line=5),
            ],
            milestones=_MILESTONES,
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

    def test_briefing_is_the_first_substantial_content_on_project_home(self):
        body = self._page()
        briefing_pos = body.find("Project Briefing")
        composer_pos = body.find("project-home-composer")
        self.assertGreater(briefing_pos, 0)
        self.assertLess(briefing_pos, composer_pos)

    def test_deterministic_sections_available_with_no_briefing_generated_yet(self):
        body = self._page()
        self.assertIn("No narrative briefing generated yet", body)
        self.assertIn(_CANDIDATE_ITEMS[0]["text"], body)  # scope item, via reading path/technical section
        self.assertIn("No Financial Submission requirements were found", body)

    def test_generating_persists_and_displays_the_briefing(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_BRIEFING_OUTPUT)
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/briefing/generate", follow_redirects=True,
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_data(as_text=True)
        self.assertIn("Riverside renovation", body)
        self.assertIn("Complete structural upgrades", body)
        workspace = self.store.get(self.project_id)
        self.assertIsNotNone(workspace.project_briefing)
        self.assertEqual(workspace.project_briefing_generated_by, "owner1")

    def test_missing_api_key_does_not_persist_a_fabricated_briefing(self):
        resp = self.client.post(
            f"/projects/{self.project_id}/workspace/briefing/generate", follow_redirects=True,
        )
        body = resp.get_data(as_text=True)
        self.assertIn("ANTHROPIC_API_KEY", body)
        workspace = self.store.get(self.project_id)
        self.assertIsNone(workspace.project_briefing)

    def test_policy_denial_makes_zero_provider_calls_and_does_not_persist(self):
        from services.security_governance import CONTROL_SOURCE_ARCHIOSK_DEFAULT, SecurityGovernanceStore
        from services.security_policy import ACTION_EXTERNAL_AI_REQUEST, DECISION_DENY

        security_store = SecurityGovernanceStore(self.tmp_dir)
        record = security_store.get()
        baseline = security_store.create_baseline_draft(record, created_by="owner1")
        security_store.add_control_decision(
            record, baseline_id=baseline["id"], action_id=ACTION_EXTERNAL_AI_REQUEST, decision=DECISION_DENY,
            source_type=CONTROL_SOURCE_ARCHIOSK_DEFAULT, actor="owner1",
        )
        security_store.acknowledge_capability_impact(record, baseline["id"], actor="owner1")
        security_store.activate_baseline(record, baseline["id"], actor="owner1")

        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            resp = self.client.post(
                f"/projects/{self.project_id}/workspace/briefing/generate", follow_redirects=True,
            )
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)
        self.assertIn("not permitted by this", resp.get_data(as_text=True))
        self.assertIsNone(self.store.get(self.project_id).project_briefing)

    def test_stale_notice_appears_after_the_source_set_changes(self):
        with patch("anthropic.Anthropic") as MockClient, \
             patch.dict("os.environ", {"ANTHROPIC_API_KEY": "fake-key-for-test"}):
            MockClient.return_value.messages.create.return_value = _mock_response(_SUCCESSFUL_BRIEFING_OUTPUT)
            self.client.post(f"/projects/{self.project_id}/workspace/briefing/generate")

        body = self._page()
        self.assertNotIn("consider regenerating", body)

        # Add a new Source -- the active set changes.
        self.client.post(
            f"/projects/{self.project_id}/workspace/sources/text-record",
            data={"title": "Addendum 1", "content": "Clarification text."},
        )
        body = self._page()
        self.assertIn("consider regenerating", body)

    def test_extracted_candidates_are_not_described_as_confirmed(self):
        body = self._page()
        # The deterministic sections must read as extracted/candidate,
        # never as governed fact.
        self.assertIn("extracted evidence", body)
        self.assertNotIn("confirmed Technical Submission", body)

    def test_unauthorized_user_cannot_trigger_generation(self):
        from models import User, db

        with self.flask_app.app_context():
            db.session.add(User(username="stranger", password_hash=generate_password_hash("x"), role="read_only"))
            db.session.commit()
        stranger = self.flask_app.test_client()
        with stranger.session_transaction() as sess:
            sess["user_id"] = 2
            sess["username"] = "stranger"
            sess["role"] = "read_only"

        with patch("anthropic.Anthropic") as MockClient:
            resp = stranger.post(f"/projects/{self.project_id}/workspace/briefing/generate")
            self.assertEqual(resp.status_code, 404)
            self.assertEqual(MockClient.return_value.messages.create.call_count, 0)


if __name__ == "__main__":
    unittest.main()
