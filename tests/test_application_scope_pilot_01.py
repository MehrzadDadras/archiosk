"""Focused proof for the narrow TPL-005 Application Knowledge pilot."""

from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from services.case_workspace import CONTENT_CLASS_AI_PROPOSED, CaseWorkspaceStore
from services.conversation_interpreter import InterpretationResult, interpret_message
from services.project_qa import ProjectQAResult


class ApplicationScopePilotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="archiosk_application_pilot_"))
        self.store = CaseWorkspaceStore(self.tmp)
        self.workspace = self.store.get_or_create("pilot-project")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _interpret(self, text, **kwargs):
        return interpret_message(
            text=text,
            workspace=self.workspace,
            case=None,
            store=self.store,
            artifacts_dir=self.tmp,
            reviewer="pilot-admin",
            focused_finding_id=None,
            triggering_message_id="pilot-message",
            **kwargs,
        )

    @property
    def _tpl5_context(self):
        return {"template_identity": {"template_id": "TPL-005", "name": "Project Workspace"}}

    def test_application_question_diverts_only_with_tpl5_developer_context(self):
        fake = ProjectQAResult(ran=True, answer="Composer is in the Developer toolbox.")
        with patch("services.conversation_interpreter.answer_application_question", return_value=fake) as app_call, \
             patch("services.conversation_interpreter._handle_project_question") as project_call:
            result = self._interpret(
                "Where is the Composer on this page?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_called_once()
        project_call.assert_not_called()
        self.assertEqual(result.action_taken, "application_scope_answered")
        self.assertEqual(result.content_class, CONTENT_CLASS_AI_PROPOSED)
        self.assertEqual(result.grounded_in, [])
        self.assertEqual(app_call.call_args.kwargs["developer_context"], self._tpl5_context)
        self.assertNotIn("workspace", app_call.call_args.kwargs)
        self.assertNotIn("store", app_call.call_args.kwargs)
        self.assertNotIn("project_id", app_call.call_args.kwargs)

    def test_tier1_capability_remains_upstream_of_application_pilot(self):
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Can ARCHIOSK send an email?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_not_called()
        self.assertTrue(result.action_taken.startswith("capability_question:"))

    def test_project_question_stays_on_project_path(self):
        project_result = InterpretationResult(
            action_taken="project_scope_answered",
            reply_text="Project evidence answer",
            grounded_in=["RFP section"],
        )
        with patch("services.conversation_interpreter.answer_application_question") as app_call, \
             patch("services.conversation_interpreter._handle_project_question", return_value=project_result) as project_call:
            result = self._interpret(
                "What does the RFP require for smoke control?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_not_called()
        project_call.assert_called_once()
        self.assertEqual(result.grounded_in, ["RFP section"])

    def test_project_anchor_presence_vetoes_application_diversion(self):
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Where is the Composer on this page?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
                anchor={"anchor_type": "source", "anchor_id": "source-1"},
            )
        app_call.assert_not_called()
        self.assertNotEqual(result.action_taken, "application_scope_answered")

    def test_project_selection_in_developer_context_presence_vetoes_diversion(self):
        context = {
            **self._tpl5_context,
            "selected_elements": [{
                "object_type": "source",
                "object_id": "source-1",
                "project_id": "pilot-project",
            }],
        }
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Where is the Composer on this page?",
                developer_context=context,
                developer_mode_active=True,
            )
        app_call.assert_not_called()
        self.assertNotEqual(result.action_taken, "application_scope_answered")

    def test_template_surface_selection_alone_cannot_divert_construction_text(self):
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Add a right side panel to the servery pass.",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
                developer_application_selection={
                    "object_type": "template_surface",
                    "object_id": "TPL-005",
                    "label": "TPL-005 · Project Workspace",
                    "project_id": None,
                },
            )
        app_call.assert_not_called()
        self.assertNotEqual(result.action_taken, "application_scope_answered")

    def test_template_surface_selection_does_not_replace_explicit_composer_evidence(self):
        fake = ProjectQAResult(ran=True, answer="Application answer")
        with patch("services.conversation_interpreter.answer_application_question", return_value=fake) as app_call:
            result = self._interpret(
                "Where is the Composer on this page?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
                developer_application_selection={
                    "object_type": "template_surface",
                    "object_id": "TPL-005",
                    "label": "TPL-005 · Project Workspace",
                    "project_id": None,
                },
            )
        app_call.assert_called_once()
        self.assertEqual(result.action_taken, "application_scope_answered")

    def test_non_developer_or_non_tpl5_context_does_not_divert(self):
        for context, developer_active in (
            (self._tpl5_context, False),
            ({"template_identity": {"template_id": "TPL-001", "name": "Home"}}, True),
        ):
            with self.subTest(context=context, developer_active=developer_active), \
                 patch("services.conversation_interpreter.answer_application_question") as app_call:
                result = self._interpret(
                    "Where is the Composer on this page?",
                    developer_context=context,
                    developer_mode_active=developer_active,
                )
            app_call.assert_not_called()
            self.assertNotEqual(result.action_taken, "application_scope_answered")

    def test_application_model_failure_falls_through(self):
        unavailable = ProjectQAResult(ran=False, skipped_reason="test unavailable")
        project_result = InterpretationResult(
            action_taken="project_scope_answered",
            reply_text="fallback project answer",
        )
        with patch("services.conversation_interpreter.answer_application_question", return_value=unavailable) as app_call, \
             patch("services.conversation_interpreter._handle_project_question", return_value=project_result) as project_call:
            result = self._interpret(
                "Where is the Composer on this page?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_called_once()
        project_call.assert_called_once()
        self.assertEqual(result.reply_text, "fallback project answer")

    def test_physical_panel_question_does_not_divert(self):
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Add a right side panel to the servery pass",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_not_called()
        self.assertNotEqual(result.action_taken, "application_scope_answered")

    def test_submittal_signal_prevents_pure_application_diversion(self):
        with patch("services.conversation_interpreter.answer_application_question") as app_call:
            result = self._interpret(
                "Can ARCHIOSK list the outstanding submittals in a panel?",
                developer_context=self._tpl5_context,
                developer_mode_active=True,
            )
        app_call.assert_not_called()
        self.assertNotEqual(result.action_taken, "application_scope_answered")


if __name__ == "__main__":
    unittest.main()
