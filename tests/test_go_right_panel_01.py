"""
CLAUDE-GO-RIGHT-PANEL-01 - the smallest repository-grounded proof that
Composer intelligence can leave the chat stream and become persistent,
tagged right-panel project material: Composer/project intelligence ->
structured finding (services.case_workspace.ComposerFinding) -> tagged
right-panel item (the Toolbox's own new "Findings" branch) -> source
evidence on demand (a real, existing Document-navigation link, never an
auto-snap).

Deliberately NOT the full future Spin architecture - no historical Spin
sets, no Pass/Build adjudication, no Tool Making, no custom-focus
management. See this stage's own governing prompt for the full scope
boundary.

Follows this repo's own hermetic convention (patch("anthropic.Anthropic"))
for every LLM-touching test - never a live model call.

Run via:

    python -m unittest tests.test_go_right_panel_01 -v
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.case_workspace import (
    CONTENT_CLASS_AI_PROPOSED,
    COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED,
    KNOWN_COMPOSER_FINDING_STATES,
    CaseWorkspaceError,
    CaseWorkspaceStore,
)
from services.ingestion import RequirementsRegistry
from services.bhive_parser import ParsedDocument
from services.project_qa import _parse_composer_findings, _MAX_COMPOSER_FINDINGS
from werkzeug.security import generate_password_hash


def _mock_response(text_out: str):
    fake_block = MagicMock()
    fake_block.type = "text"
    fake_block.text = text_out
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    fake_response.stop_reason = "end_turn"
    return fake_response


class ParseComposerFindingsTests(unittest.TestCase):
    def test_valid_item_parsed_with_optional_fields_none(self):
        raw = [{"tag": "Submission deadline", "source_reference": "Sec 3.1",
                "concern": "c", "unresolved_question": "q"}]
        result = _parse_composer_findings(raw)
        self.assertEqual(len(result), 1)
        self.assertIsNone(result[0]["urgency"])
        self.assertIsNone(result[0]["project_stage"])

    def test_item_missing_tag_is_dropped(self):
        self.assertEqual(_parse_composer_findings([{"concern": "c"}]), [])

    def test_non_list_input_returns_empty(self):
        self.assertEqual(_parse_composer_findings("not a list"), [])
        self.assertEqual(_parse_composer_findings(None), [])

    def test_capped_at_max_composer_findings(self):
        raw = [{"tag": f"T{i}", "source_reference": "", "concern": "", "unresolved_question": ""}
               for i in range(_MAX_COMPOSER_FINDINGS + 5)]
        self.assertEqual(len(_parse_composer_findings(raw)), _MAX_COMPOSER_FINDINGS)

    def test_urgency_and_stage_preserved_when_present(self):
        raw = [{"tag": "T", "source_reference": "s", "concern": "c", "unresolved_question": "u",
                "urgency": "High", "project_stage": "Pre-Award"}]
        result = _parse_composer_findings(raw)
        self.assertEqual(result[0]["urgency"], "High")
        self.assertEqual(result[0]["project_stage"], "Pre-Award")


class AddComposerFindingStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_go_right_panel_"))
        self.project_id = "test-project-right-panel"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(
            self.project_id, register_document_source={"filename": "rfp.md"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_creates_a_real_persisted_record_with_default_state(self):
        record = self.store.add_composer_finding(
            self.workspace, tag="Submission deadline", source_reference="Sec 3.1",
            concern="Deadline unclear", unresolved_question="What is the extended date?",
            created_by="owner1",
        )
        self.assertEqual(record["review_state"], COMPOSER_FINDING_STATE_MACHINE_UNREVIEWED)
        self.assertEqual(record["content_class"], CONTENT_CLASS_AI_PROPOSED)
        self.assertIn(record["review_state"], KNOWN_COMPOSER_FINDING_STATES)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.composer_findings), 1)
        self.assertEqual(workspace.composer_findings[0]["id"], record["id"])

    def test_empty_tag_is_rejected(self):
        with self.assertRaises(CaseWorkspaceError):
            self.store.add_composer_finding(
                self.workspace, tag="   ", source_reference="s", concern="c", unresolved_question="q",
            )

    def test_optional_fields_default_to_none(self):
        record = self.store.add_composer_finding(
            self.workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
        )
        self.assertIsNone(record["urgency"])
        self.assertIsNone(record["project_stage"])
        self.assertIsNone(record["source_message_id"])

    def test_no_case_id_field_distinct_from_finding(self):
        """ComposerFinding is deliberately NOT the Case/Analysis-bound
        Finding object - it must never require or carry a case_id."""
        record = self.store.add_composer_finding(
            self.workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
        )
        self.assertNotIn("case_id", record)
        self.assertNotIn("analysis_id", record)

    def test_persists_across_a_fresh_load_refresh(self):
        self.store.add_composer_finding(
            self.workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
        )
        reloaded = self.store.get(self.project_id)
        self.assertEqual(len(reloaded.composer_findings), 1)


class ComposerFindingPromotionTests(unittest.TestCase):
    """Exercises the real conversation_interpreter._handle_project_question
    promotion path end-to-end (mocked anthropic.Anthropic)."""

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_go_right_panel_promo_"))
        self.project_id = "test-project-right-panel-promo"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.workspace = self.store.get_or_create(
            self.project_id, register_document_source={"filename": "rfp.md"},
        )

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _interpret(self, text: str, response_json: str):
        from services.conversation_interpreter import interpret_message

        # Mirrors routes/workspace.py's own _run_conversation_turn, which
        # always persists the human message FIRST and passes its real id
        # as triggering_message_id - needed here to prove
        # ComposerFinding.source_message_id provenance threading actually
        # works, not just that the field exists.
        human_message = self.store.add_message(self.workspace, None, role="human", text=text, actor="owner1")

        artifacts_dir = self.tmp_dir / "workspace_artifacts"
        with patch("anthropic.Anthropic") as MockClient, \
             patch("services.llm_gateway.os.getenv",
                   side_effect=lambda k, d="": "fake-key-for-test" if k == "ANTHROPIC_API_KEY" else d):
            MockClient.return_value.messages.create.return_value = _mock_response(response_json)
            return interpret_message(
                text=text, workspace=self.store.get(self.project_id), case=None, store=self.store,
                artifacts_dir=artifacts_dir, reviewer="owner1", focused_finding_id=None,
                triggering_message_id=human_message["id"], anchor=None,
            )

    def test_discrepancy_question_promotes_real_composer_findings(self):
        response_json = (
            '{"answer": "Several issues found.", "grounded_in": ["Sec 3.1"], '
            '"not_covered": "", "needs_clarification": false, "river_actions": [], '
            '"findings": [{"tag": "Submission deadline", "source_reference": "Sec 3.1", '
            '"concern": "Deadline extended but new date not stated", '
            '"unresolved_question": "What is the confirmed date?", '
            '"urgency": "High", "project_stage": "Pre-Award"}, '
            '{"tag": "Missing schedule evidence", "source_reference": "Sec 12", '
            '"concern": "No milestone schedule attached", '
            '"unresolved_question": "Will the Owner issue one?", "urgency": "", "project_stage": ""}]}'
        )
        result = self._interpret(
            "What discrepancies or unresolved conditions in this RFP could prevent the "
            "proposal from moving forward?",
            response_json,
        )
        self.assertEqual(result.action_taken, "project_qa_answered")
        self.assertEqual(len(result.composer_finding_ids), 2)

        workspace = self.store.get(self.project_id)
        self.assertEqual(len(workspace.composer_findings), 2)
        tags = {cf["tag"] for cf in workspace.composer_findings}
        self.assertEqual(tags, {"Submission deadline", "Missing schedule evidence"})
        deadline = next(cf for cf in workspace.composer_findings if cf["tag"] == "Submission deadline")
        self.assertEqual(deadline["urgency"], "High")
        second = next(cf for cf in workspace.composer_findings if cf["tag"] == "Missing schedule evidence")
        self.assertIsNone(second["urgency"])  # empty string from the model -> None, never a blank-looking value

    def test_ordinary_factual_question_creates_no_findings(self):
        """Section 10.9's own acceptance criterion: ordinary chat must
        never pollute the right panel."""
        response_json = (
            '{"answer": "This RFP is named Project Dossier-Sync.", "grounded_in": ["title"], '
            '"not_covered": "", "needs_clarification": false, "river_actions": [], "findings": []}'
        )
        result = self._interpret("What is the name of this RFP?", response_json)
        self.assertEqual(result.composer_finding_ids, [])

        workspace = self.store.get(self.project_id)
        self.assertEqual(workspace.composer_findings, [])

    def test_source_message_id_provenance_is_recorded(self):
        response_json = (
            '{"answer": "ok", "grounded_in": ["s"], "not_covered": "", '
            '"needs_clarification": false, "river_actions": [], '
            '"findings": [{"tag": "T", "source_reference": "s", "concern": "c", '
            '"unresolved_question": "q", "urgency": "", "project_stage": ""}]}'
        )
        result = self._interpret("What discrepancies exist?", response_json)
        workspace = self.store.get(self.project_id)
        finding = workspace.composer_findings[0]
        self.assertIsNotNone(finding["source_message_id"])
        self.assertEqual(len(result.composer_finding_ids), 1)


class ComposerFindingProjectIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_go_right_panel_iso_"))
        self.store = CaseWorkspaceStore(self.tmp_dir)

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_composer_findings_never_cross_projects(self):
        for pid in ("project-a", "project-b"):
            RequirementsRegistry(self.tmp_dir).save(
                ParsedDocument(project_id=pid, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
            )
        ws_a = self.store.get_or_create("project-a", register_document_source={"filename": "rfp.md"})
        self.store.get_or_create("project-b", register_document_source={"filename": "rfp.md"})

        self.store.add_composer_finding(
            ws_a, tag="Only in A", source_reference="s", concern="c", unresolved_question="q",
        )

        ws_a_reloaded = self.store.get("project-a")
        ws_b_reloaded = self.store.get("project-b")
        self.assertEqual(len(ws_a_reloaded.composer_findings), 1)
        self.assertEqual(len(ws_b_reloaded.composer_findings), 0)


class ToolboxRenderTests(unittest.TestCase):
    """Route-level: proves the Toolbox actually projects
    composer_findings_view, with the right priority (Investigation/
    Document selection still wins), real display ids, and that an empty
    list falls through to the existing neutral empty state rather than
    rendering a broken/empty section."""

    def setUp(self):
        import app as app_module
        from models import User, db

        self.tmp_dir = Path(tempfile.mkdtemp(prefix="beehive_test_go_right_panel_route_"))
        self.flask_app = app_module.create_app("testing")
        self.flask_app.config["REGISTRY_STORE_PATH"] = str(self.tmp_dir)
        self.project_id = "test-project-right-panel-route"

        with self.flask_app.app_context():
            db.session.add(User(username="rp_owner", password_hash=generate_password_hash("x"), role="admin"))
            db.session.commit()

        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=self.project_id, filename="rfp.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client = self.flask_app.test_client()
        with self.client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "rp_owner"
            sess["role"] = "admin"
        self.store = CaseWorkspaceStore(self.tmp_dir)
        self.client.get(f"/projects/{self.project_id}/workspace")  # trigger workspace creation

    def tearDown(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_no_findings_shows_the_existing_empty_state_not_a_broken_section(self):
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertNotIn('data-ui-ref="toolbox.composer-findings"', body)
        self.assertIn('data-ui-ref="toolbox.empty"', body)

    def test_findings_render_with_display_id_and_tag(self):
        workspace = self.store.get(self.project_id)
        self.store.add_composer_finding(
            workspace, tag="Submission deadline", source_reference="Sec 3.1",
            concern="c", unresolved_question="q", created_by="rp_owner",
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.composer-findings"', body)
        self.assertIn("F-001", body)
        self.assertIn("Submission deadline", body)

    def test_open_source_link_present_and_points_at_a_real_document_route(self):
        workspace = self.store.get(self.project_id)
        self.store.add_composer_finding(
            workspace, tag="T", source_reference="s", concern="c", unresolved_question="q",
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertIn('data-ui-ref="toolbox.composer-findings.leaf.open-source"', body)
        self.assertIn(f"/projects/{self.project_id}/workspace?", body)

    def test_project_isolation_at_the_route_level(self):
        other_project_id = "test-project-right-panel-route-other"
        RequirementsRegistry(self.tmp_dir).save(
            ParsedDocument(project_id=other_project_id, filename="other.md", ingested_at="2026-01-01T00:00:00+00:00")
        )
        self.client.get(f"/projects/{other_project_id}/workspace")
        other_workspace = self.store.get(other_project_id)
        self.store.add_composer_finding(
            other_workspace, tag="Only in other project", source_reference="s",
            concern="c", unresolved_question="q",
        )
        resp = self.client.get(f"/projects/{self.project_id}/workspace")
        body = resp.get_data(as_text=True)
        self.assertNotIn("Only in other project", body)


if __name__ == "__main__":
    unittest.main()
